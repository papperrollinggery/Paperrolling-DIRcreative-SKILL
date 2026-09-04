#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dircreative_verify_release import (
    open_pinned_directory,
    read_relative_regular_file_once,
    regular_file_open_flags,
)
from dircreative_visual_asset_plan import (
    GENERATED_STATUSES,
    inspect_raster,
    validate_technical_receipt,
    validate_plan,
    validate_visual_qa_receipt,
)
from dircreative_character_master_visual_gate import load_visual_review_authorization

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    Image = ImageDraw = ImageFont = ImageOps = None  # type: ignore[assignment]


CONTRACT_ID = "professional_storyboard_assembly_v1"
MAX_PLAN_BYTES = 8 * 1024 * 1024
MAX_FRAME_BYTES = 128 * 1024 * 1024
MAX_CELLS = 6
FONT_CANDIDATES = (
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_new_file(
    path: Path,
    payload: bytes,
    *,
    race_hook: Any = None,
) -> tuple[int, int]:
    temp_name = f".{path.name}.{uuid.uuid4().hex}.tmp"
    with open_pinned_directory(path.parent) as pinned:
        descriptor = os.open(
            temp_name,
            regular_file_open_flags(write=True, create=True),
            0o600,
            dir_fd=pinned.fd,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if race_hook is not None:
                race_hook()
            pinned.revalidate(label="storyboard output before commit")
            os.link(
                temp_name,
                path.name,
                src_dir_fd=pinned.fd,
                dst_dir_fd=pinned.fd,
                follow_symlinks=False,
            )
            linked = os.stat(path.name, dir_fd=pinned.fd, follow_symlinks=False)
            pinned.revalidate(label="storyboard output after commit")
            return linked.st_dev, linked.st_ino
        finally:
            try:
                os.unlink(temp_name, dir_fd=pinned.fd)
            except FileNotFoundError:
                pass


def _remove_if_identity(path: Path, identity: tuple[int, int] | None) -> bool:
    if identity is None:
        return True
    try:
        with open_pinned_directory(path.parent) as pinned:
            current = os.stat(path.name, dir_fd=pinned.fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != identity:
                return False
            os.unlink(path.name, dir_fd=pinned.fd)
            pinned.revalidate(label="storyboard rollback")
            return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _font(size: int):
    assert ImageFont is not None
    for candidate in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_text(draw: Any, value: str, *, font: Any, max_width: int) -> str:
    if draw.textbbox((0, 0), value, font=font)[2] <= max_width:
        return value
    suffix = "…"
    low, high = 0, len(value)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = value[:middle].rstrip() + suffix
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            low = middle
        else:
            high = middle - 1
    return value[:low].rstrip() + suffix


def _reviewed_frame_bytes(
    asset: dict[str, Any],
    *,
    base_dir: Path,
    truth_locked_at: str,
    errors: list[str],
) -> tuple[bytes, dict[str, Any]] | None:
    asset_id = str(asset.get("asset_id"))
    relative = asset.get("generated_file")
    if asset.get("status") not in GENERATED_STATUSES:
        errors.append(f"parent_frame_not_generated:{asset_id}")
        return None
    try:
        payload = read_relative_regular_file_once(
            base_dir,
            relative,
            max_bytes=MAX_FRAME_BYTES,
            label=f"storyboard frame {asset_id}",
        )
    except (OSError, TypeError, ValueError):
        errors.append(f"parent_frame_file_invalid:{asset_id}")
        return None
    with tempfile.NamedTemporaryFile(suffix=".png") as temp:
        temp.write(payload)
        temp.flush()
        evidence, reason = inspect_raster(Path(temp.name))
    if evidence is None:
        errors.append(f"parent_frame_raster_invalid:{asset_id}:{reason}")
        return None
    if (
        asset.get("generated_sha256") != evidence["sha256"]
        or asset.get("generated_pixel_sha256") != evidence["pixel_sha256"]
        or asset.get("generated_perceptual_hash") != evidence["perceptual_hash"]
    ):
        errors.append(f"parent_frame_evidence_mismatch:{asset_id}")
        return None
    technical_error = validate_technical_receipt(
        asset.get("technical_receipt"),
        asset_id=asset_id,
        evidence=evidence,
        truth_locked_at=truth_locked_at,
    )
    if technical_error is not None:
        errors.append(f"parent_frame_technical_receipt_invalid:{asset_id}")
        return None
    return payload, evidence


def assemble(
    sealed_plan_bytes: bytes,
    *,
    base_dir: Path,
    asset_id: str,
    output_path: Path,
    receipt_path: Path,
    execution_task_id: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        plan = json.loads(sealed_plan_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "blocked", "errors": ["visual_plan_bytes_invalid"]}
    if not isinstance(plan, dict):
        return {"status": "blocked", "errors": ["visual_plan_root_invalid"]}
    plan_sha256 = hashlib.sha256(sealed_plan_bytes).hexdigest()
    if Image is None or ImageDraw is None or ImageFont is None or ImageOps is None:
        return {"status": "TOOL_BLOCKED", "errors": ["pillow_unavailable"]}
    assets = {
        str(item.get("asset_id")): item
        for item in plan.get("assets", [])
        if isinstance(item, dict)
    }
    plan_errors, _metrics = validate_plan(plan, base_dir=base_dir)
    if plan_errors:
        return {
            "status": "blocked",
            "errors": [f"visual_plan_invalid:{error}" for error in plan_errors],
        }
    target = assets.get(asset_id)
    if not isinstance(target, dict) or (
        target.get("role") != "professional_storyboard_motion_map"
        or target.get("action") != "assemble"
    ):
        return {"status": "blocked", "errors": ["assembly_target_invalid"]}
    try:
        resolved_base = base_dir.resolve(strict=True)
        raw_base = Path(os.path.abspath(base_dir))
        raw_output = Path(os.path.abspath(output_path))
        raw_receipt = Path(os.path.abspath(receipt_path))
        raw_output.relative_to(raw_base)
        raw_receipt.relative_to(raw_base)
        normalized_output = raw_output.parent.resolve(strict=True) / raw_output.name
        normalized_receipt = raw_receipt.parent.resolve(strict=True) / raw_receipt.name
        normalized_output.relative_to(resolved_base)
        normalized_receipt.relative_to(resolved_base)
    except (OSError, ValueError):
        return {"status": "blocked", "errors": ["assembly_output_path_invalid"]}
    if normalized_output == normalized_receipt:
        return {"status": "blocked", "errors": ["assembly_output_receipt_collision"]}
    if normalized_output.exists() or normalized_output.is_symlink():
        return {"status": "blocked", "errors": ["assembly_output_must_be_new"]}
    if normalized_receipt.exists() or normalized_receipt.is_symlink():
        return {"status": "blocked", "errors": ["assembly_receipt_must_be_new"]}
    output_path = normalized_output
    receipt_path = normalized_receipt
    shot_ids = target.get("coverage", {}).get("shot_ids", [])
    parent_ids = target.get("inherits_from", [])
    if (
        not isinstance(shot_ids, list)
        or not isinstance(parent_ids, list)
        or not 1 <= len(shot_ids) <= MAX_CELLS
        or len(parent_ids) != len(shot_ids)
    ):
        return {"status": "blocked", "errors": ["assembly_coverage_invalid"]}
    truth_by_id = {
        str(item.get("shot_id")): item
        for item in plan.get("shot_truth", [])
        if isinstance(item, dict)
    }
    frames: list[tuple[dict[str, Any], dict[str, Any], bytes, dict[str, Any]]] = []
    for shot_id, parent_id in zip(shot_ids, parent_ids):
        parent = assets.get(str(parent_id))
        if not isinstance(parent, dict) or (
            parent.get("role") != "storyboard_frame"
            or parent.get("coverage", {}).get("shot_ids") != [shot_id]
            or shot_id not in truth_by_id
        ):
            errors.append(f"assembly_parent_order_or_truth_invalid:{parent_id}:{shot_id}")
            continue
        verified = _reviewed_frame_bytes(
            parent,
            base_dir=base_dir,
            truth_locked_at=str(plan.get("truth_locked_at")),
            errors=errors,
        )
        if verified is not None:
            payload, evidence = verified
            frames.append((truth_by_id[shot_id], parent, payload, evidence))
    if errors or len(frames) != len(shot_ids):
        return {"status": "blocked", "errors": errors or ["assembly_parent_coverage_incomplete"]}
    evidence_by_asset = {
        str(parent["asset_id"]): evidence for _truth, parent, _payload, evidence in frames
    }
    manifest_cache: dict[
        str,
        tuple[dict[str, Any], dict[str, dict[str, Any]], str | None],
    ] = {}
    for _truth, parent, _payload, evidence in frames:
        problem = validate_visual_qa_receipt(
            parent.get("visual_qa_receipt"),
            asset=parent,
            evidence=evidence,
            truth_locked_at=str(plan.get("truth_locked_at")),
            base_dir=base_dir,
            payload=plan,
            evidence_by_asset=evidence_by_asset,
            manifest_cache=manifest_cache,
        )
        if problem:
            errors.append(f"parent_frame_visual_review_invalid:{parent['asset_id']}:{problem}")
            continue
        _authorization, authorization_errors = load_visual_review_authorization(
            parent,
            base_dir=base_dir,
            image_evidence=evidence,
            expected_execution_task_id=execution_task_id,
        )
        if authorization_errors:
            errors.append(f"parent_frame_visual_review_not_host_authorized:{parent['asset_id']}")
    if errors:
        return {"status": "blocked", "errors": errors}

    profile = plan.get("delivery_profile", {})
    width = int(profile.get("raster_width", 1920))
    height = int(profile.get("raster_height", 1080))
    if width < 1280 or height < 720:
        return {"status": "blocked", "errors": ["assembly_raster_too_small"]}
    canvas = Image.new("RGB", (width, height), (17, 19, 23))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(max(24, width // 55))
    meta_font = _font(max(15, width // 105))
    label_font = _font(max(14, width // 118))
    body_font = _font(max(12, width // 145))
    margin = max(24, width // 60)
    header_height = max(88, height // 10)
    draw.text((margin, margin), "PROFESSIONAL STORYBOARD + MOTION MAP", fill=(242, 239, 230), font=title_font)
    project = str(plan.get("project_id"))
    draw.text(
        (margin, margin + title_font.size + 8),
        f"Project: {project}   |   Asset: {asset_id}   |   Shots: {', '.join(shot_ids)}",
        fill=(151, 158, 168),
        font=meta_font,
    )
    columns = 3 if len(frames) > 2 else len(frames)
    rows = math.ceil(len(frames) / columns)
    gap = max(14, width // 100)
    footer_height = max(34, height // 30)
    cell_width = (width - 2 * margin - gap * (columns - 1)) // columns
    cell_height = (height - header_height - footer_height - margin - gap * (rows - 1)) // rows
    image_height = int(cell_height * 0.58)
    parent_receipts: list[dict[str, Any]] = []
    for index, (truth, _parent, payload, evidence) in enumerate(frames):
        row, column = divmod(index, columns)
        left = margin + column * (cell_width + gap)
        top = header_height + row * (cell_height + gap)
        right, bottom = left + cell_width, top + cell_height
        draw.rounded_rectangle((left, top, right, bottom), radius=10, fill=(29, 32, 38), outline=(69, 75, 86), width=2)
        with Image.open(io.BytesIO(payload)) as source:
            source.load()
            frame_image = ImageOps.fit(source.convert("RGB"), (cell_width - 4, image_height - 2), method=Image.Resampling.LANCZOS)
        canvas.paste(frame_image, (left + 2, top + 2))
        text_left = left + 12
        text_top = top + image_height + 8
        max_text_width = cell_width - 24
        draw.text((text_left, text_top), f"{truth['shot_id']}  {truth['timecode']}  |  {truth['duration_seconds']}s", fill=(224, 176, 80), font=label_font)
        lines = (
            ("Narrative purpose", truth["narrative_purpose"]),
            ("Lens/support/movement", truth["shot_design"]),
            ("Blocking/path", truth["action"]),
            ("Continuity", truth["continuity_model"]),
            ("Sound/edit", truth["sound_edit"]),
            ("Transition", truth["sound_edit"]),
            ("Model risk", f"identity, geometry or action drift against {truth['continuity_model']}"),
        )
        line_y = text_top + label_font.size + 7
        line_height = body_font.size + 4
        for label, value in lines:
            draw.text(
                (text_left, line_y),
                _fit_text(draw, f"{label}: {value}", font=body_font, max_width=max_text_width),
                fill=(206, 209, 214),
                font=body_font,
            )
            line_y += line_height
        parent_receipts.append(
            {
                "shot_id": truth["shot_id"],
                "file_sha256": evidence["sha256"],
                "pixel_sha256": evidence["pixel_sha256"],
            }
        )
    draw.text(
        (margin, height - footer_height),
        "Planning overview only · individual approved frames remain the visual source of truth · not a direct video input",
        fill=(112, 120, 132),
        font=meta_font,
    )
    encoded = io.BytesIO()
    canvas.save(encoded, format="PNG", optimize=False, compress_level=9)
    output_bytes = encoded.getvalue()
    output_identity: tuple[int, int] | None = None
    receipt_identity: tuple[int, int] | None = None
    try:
        output_identity = _write_new_file(output_path, output_bytes)
        final_output = read_relative_regular_file_once(
            resolved_base,
            output_path.relative_to(resolved_base).as_posix(),
            max_bytes=MAX_FRAME_BYTES,
            label="assembled storyboard page",
        )
    except (OSError, ValueError):
        rolled_back = _remove_if_identity(output_path, output_identity)
        return {
            "status": "blocked" if rolled_back else "partial",
            "errors": [
                "assembly_output_write_or_readback_failed"
                if rolled_back
                else "assembly_partial_output_requires_manual_reconciliation"
            ],
        }
    if final_output != output_bytes:
        rolled_back = _remove_if_identity(output_path, output_identity)
        return {
            "status": "blocked" if rolled_back else "partial",
            "errors": [
                "assembly_output_readback_mismatch"
                if rolled_back
                else "assembly_partial_output_requires_manual_reconciliation"
            ],
        }
    receipt = {
        "contract_id": CONTRACT_ID,
        "status": "assembled",
        "project_id": project,
        "visual_plan_sha256": plan_sha256,
        "asset_id": asset_id,
        "asset_truth_sha256": target.get("truth_sha256"),
        "shot_ids": shot_ids,
        "parent_frames": parent_receipts,
        "layout": {"columns": columns, "rows": rows, "width": width, "height": height},
        "output_relative_path": output_path.relative_to(resolved_base).as_posix(),
        "output_sha256": hashlib.sha256(final_output).hexdigest(),
        "assembled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generation_tool_used": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    receipt_bytes = (
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        receipt_identity = _write_new_file(receipt_path, receipt_bytes)
        final_receipt = read_relative_regular_file_once(
            resolved_base,
            receipt_path.relative_to(resolved_base).as_posix(),
            max_bytes=MAX_PLAN_BYTES,
            label="storyboard assembly receipt",
        )
    except (OSError, ValueError):
        receipt_rolled_back = _remove_if_identity(receipt_path, receipt_identity)
        output_rolled_back = _remove_if_identity(output_path, output_identity)
        rolled_back = receipt_rolled_back and output_rolled_back
        return {
            "status": "blocked" if rolled_back else "partial",
            "errors": [
                "assembly_receipt_write_or_readback_failed_output_rolled_back"
                if rolled_back
                else "assembly_partial_pair_requires_manual_reconciliation"
            ],
        }
    if final_receipt != receipt_bytes:
        receipt_rolled_back = _remove_if_identity(receipt_path, receipt_identity)
        output_rolled_back = _remove_if_identity(output_path, output_identity)
        rolled_back = receipt_rolled_back and output_rolled_back
        return {
            "status": "blocked" if rolled_back else "partial",
            "errors": [
                "assembly_receipt_readback_mismatch_output_rolled_back"
                if rolled_back
                else "assembly_partial_pair_requires_manual_reconciliation"
            ],
        }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a professional storyboard overview from approved frame PNGs.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--execution-task-id")
    args = parser.parse_args()
    try:
        plan_path = args.plan.expanduser().resolve(strict=True)
        base_dir = plan_path.parent
        plan_bytes = read_relative_regular_file_once(
            base_dir,
            plan_path.name,
            max_bytes=MAX_PLAN_BYTES,
            label="visual asset plan",
        )
        plan = json.loads(plan_bytes.decode("utf-8"))
        output_path = args.output.expanduser().resolve(strict=False)
        receipt_path = args.receipt.expanduser().resolve(strict=False)
        output_path.relative_to(base_dir)
        receipt_path.relative_to(base_dir)
        result = assemble(
            plan_bytes,
            base_dir=base_dir,
            asset_id=args.asset_id,
            output_path=output_path,
            receipt_path=receipt_path,
            execution_task_id=args.execution_task_id,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        result = {"status": "blocked", "errors": [f"input_or_output_invalid:{type(exc).__name__}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "assembled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
