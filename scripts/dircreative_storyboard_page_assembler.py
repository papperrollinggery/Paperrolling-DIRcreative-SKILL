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
import dircreative_storyboard_coverage as storyboard_coverage

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    Image = ImageDraw = ImageFont = ImageOps = None  # type: ignore[assignment]


CONTRACT_ID = "professional_storyboard_assembly_v1"
MAX_PLAN_BYTES = 8 * 1024 * 1024
MAX_FRAME_BYTES = 128 * 1024 * 1024
MAX_CELLS = 6
FONT_CANDIDATES = (
    "/System/Library/PrivateFrameworks/FontServices.framework/Versions/A/Resources/Reserved/PingFangUI.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
USER_CJK_FONT_RELATIVE_PATHS = (
    Path("Library/Application Support/com.electron.lark.font_workaround/PingFang.ttc"),
    Path("Library/Fonts/PingFang.ttc"),
    Path("Library/Fonts/NotoSansCJK-Regular.ttc"),
)
MOTION_CJK_TEXT = "动作分镜规划板实线人物位移折线弧线轨迹摄影机运动固定机位"
MOTION_BOARD_CONTRACT_ID = "motion_storyboard_board_v1"
SHEET_EXTRACTION_CONTRACT_ID = "storyboard_clean_sheet_extraction_v1"
MAX_MOTION_CELLS = 9


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


def _font_has_glyphs(font: Any, text: str) -> bool:
    """Reject fonts that replace the required CJK text with one missing-glyph box."""
    try:
        missing = bytes(font.getmask("\U0010ffff"))
        return all(bytes(font.getmask(character)) != missing for character in text)
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def _motion_font(size: int):
    """Return a CJK-capable font for the motion-board labels, or no font at all."""
    assert ImageFont is not None
    candidates = [Path(candidate) for candidate in FONT_CANDIDATES]
    candidates.extend(Path.home() / relative for relative in USER_CJK_FONT_RELATIVE_PATHS)
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            font = ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
        if _font_has_glyphs(font, MOTION_CJK_TEXT):
            return font
    return None


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


def _new_project_paths(
    *, project_root: Path, output_path: Path, receipt_path: Path
) -> tuple[Path, Path, Path] | None:
    """Resolve two new regular output names without following project escape paths."""
    try:
        resolved_root = project_root.resolve(strict=True)
        raw_root = Path(os.path.abspath(project_root)).resolve(strict=True)
        raw_output = Path(os.path.abspath(output_path)).resolve(strict=False)
        raw_receipt = Path(os.path.abspath(receipt_path)).resolve(strict=False)
        raw_output.relative_to(raw_root)
        raw_receipt.relative_to(raw_root)
        output = raw_output.parent.resolve(strict=True) / raw_output.name
        receipt = raw_receipt.parent.resolve(strict=True) / raw_receipt.name
        output.relative_to(resolved_root)
        receipt.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    if output == receipt or output.exists() or output.is_symlink() or receipt.exists() or receipt.is_symlink():
        return None
    return resolved_root, output, receipt


def _planning_image_bytes(
    panel: dict[str, Any], *, project_root: Path, errors: list[str]
) -> tuple[bytes, dict[str, Any]] | None:
    panel_id = str(panel.get("panel_id"))
    image = panel.get("planning_image")
    if not isinstance(image, dict):
        errors.append(f"motion_planning_image_invalid:{panel_id}")
        return None
    try:
        payload = read_relative_regular_file_once(
            project_root, image.get("path"), max_bytes=MAX_FRAME_BYTES,
            label=f"motion planning image {panel_id}",
        )
    except (OSError, TypeError, ValueError):
        errors.append(f"motion_planning_image_file_invalid:{panel_id}")
        return None
    byte_hash = hashlib.sha256(payload).hexdigest()
    if byte_hash != image.get("sha256"):
        errors.append(f"motion_planning_image_sha256_mismatch:{panel_id}")
        return None
    try:
        with Image.open(io.BytesIO(payload)) as source:
            source.load()
            if source.format != "PNG":
                raise ValueError("not_png")
            evidence = {"width": source.width, "height": source.height}
    except (OSError, ValueError):
        errors.append(f"motion_planning_image_not_png:{panel_id}")
        return None
    return payload, {"sha256": byte_hash, **evidence}


def _normalized_point(point: Any) -> tuple[float, float] | None:
    if not isinstance(point, list) or len(point) != 2:
        return None
    x, y = finite_number(point[0]), finite_number(point[1])
    if x is None or y is None or not (0 <= x <= 1 and 0 <= y <= 1):
        return None
    return x, y


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        value = float(value)
    except (ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def _draw_arrow(draw: Any, points: list[tuple[float, float]], *, kind: str) -> None:
    if len(points) < 2:
        return
    width = 7 if kind == "actor_path" else 5
    if kind == "camera":
        for first, second in zip(points, points[1:]):
            dx, dy = second[0] - first[0], second[1] - first[1]
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            step = 18
            for offset in range(0, int(length), step * 2):
                start = (first[0] + dx * offset / length, first[1] + dy * offset / length)
                end_offset = min(offset + step, length)
                end = (first[0] + dx * end_offset / length, first[1] + dy * end_offset / length)
                draw.line((start, end), fill=(0, 0, 0), width=width)
    else:
        draw.line(points, fill=(0, 0, 0), width=width, joint="curve")
    penultimate, tip = points[-2], points[-1]
    angle = math.atan2(tip[1] - penultimate[1], tip[0] - penultimate[0])
    wing = 17
    for delta in (2.55, -2.55):
        end = (tip[0] + wing * math.cos(angle + delta), tip[1] + wing * math.sin(angle + delta))
        draw.line((tip, end), fill=(0, 0, 0), width=width)


def _draw_motion_annotations(
    draw: Any, annotations: list[dict[str, Any]], *, image_rect: tuple[int, int, int, int], font: Any
) -> None:
    left, top, right, bottom = image_rect
    width, height = right - left, bottom - top
    for annotation in annotations:
        kind = annotation["kind"]
        label = annotation["label"]
        if kind == "camera" and annotation.get("stationary"):
            draw.text((left + 12, top + 12), f"摄影机：固定｜{label}", fill=(0, 0, 0), font=font)
            continue
        normalized = [_normalized_point(point) for point in annotation["points"]]
        points = [
            (left + point[0] * width, top + point[1] * height)
            for point in normalized if point is not None
        ]
        _draw_arrow(draw, points, kind=kind)
        label_position = _normalized_point(annotation.get("label_position"))
        position = (
            (left + label_position[0] * width, top + label_position[1] * height)
            if label_position is not None else points[min(1, len(points) - 1)]
        )
        draw.text((position[0] + 7, position[1] + 5), label, fill=(0, 0, 0), font=font)


def assemble_motion_board(
    sealed_coverage_bytes: bytes,
    *,
    project_root: Path,
    panel_ids: list[str],
    columns: int,
    output_path: Path,
    receipt_path: Path,
) -> dict[str, Any]:
    """Assemble an unapproved black-and-white motion planning board from sealed line art."""
    if Image is None or ImageDraw is None or ImageFont is None or ImageOps is None:
        return {"status": "TOOL_BLOCKED", "errors": ["pillow_unavailable"]}
    if not 1 <= len(panel_ids) <= MAX_MOTION_CELLS or len(set(panel_ids)) != len(panel_ids):
        return {"status": "blocked", "errors": ["motion_panel_ids_invalid"]}
    if not 1 <= columns <= 3:
        return {"status": "blocked", "errors": ["motion_columns_invalid"]}
    try:
        coverage = json.loads(sealed_coverage_bytes.decode("utf-8"))
        root = project_root.resolve(strict=True)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "blocked", "errors": ["motion_coverage_bytes_invalid"]}
    if not isinstance(coverage, dict):
        return {"status": "blocked", "errors": ["motion_coverage_root_invalid"]}
    paths = _new_project_paths(project_root=root, output_path=output_path, receipt_path=receipt_path)
    if paths is None:
        return {"status": "blocked", "errors": ["motion_output_or_receipt_path_invalid_or_not_new"]}
    resolved_root, output_path, receipt_path = paths
    design = storyboard_coverage.validate(coverage, resolved_root, "design")
    if design.get("status") != "valid":
        return {"status": "blocked", "errors": [f"motion_coverage_design_invalid:{error}" for error in design.get("errors", [])]}
    validator = getattr(storyboard_coverage, "validate_motion_planning", None)
    input_hasher = getattr(storyboard_coverage, "motion_inputs_sha256", None)
    if not callable(validator) or not callable(input_hasher):
        return {"status": "blocked", "errors": ["motion_coverage_runtime_unavailable"]}
    planning = validator(coverage, resolved_root, require_review=False, panel_ids=panel_ids)
    if planning.get("status") != "valid":
        return {"status": "blocked", "errors": [f"motion_planning_invalid:{error}" for error in planning.get("errors", []) + planning.get("missing", [])]}
    panels = {str(panel.get("panel_id")): panel for panel in coverage.get("panels", []) if isinstance(panel, dict)}
    selected = [panels.get(panel_id) for panel_id in panel_ids]
    if any(panel is None for panel in selected):
        return {"status": "blocked", "errors": ["motion_panel_not_found"]}
    if any(isinstance(panel, dict) and panel.get("planning_image", {}).get("annotation_source") == "model_generated" for panel in selected):
        return {"status": "blocked", "errors": ["motion_model_generated_board_preserved_without_overlay"]}
    errors: list[str] = []
    sealed_panels: list[tuple[dict[str, Any], bytes, dict[str, Any]]] = []
    for panel in selected:
        assert isinstance(panel, dict)
        verified = _planning_image_bytes(panel, project_root=resolved_root, errors=errors)
        if verified is not None:
            payload, evidence = verified
            sealed_panels.append((panel, payload, evidence))
    if errors or len(sealed_panels) != len(panel_ids):
        return {"status": "blocked", "errors": errors or ["motion_planning_images_incomplete"]}
    try:
        planning_input_sha256 = input_hasher(coverage, panel_ids=panel_ids)
    except (TypeError, ValueError):
        return {"status": "blocked", "errors": ["motion_input_hash_invalid"]}
    title_font, meta_font, label_font = _motion_font(50), _motion_font(30), _motion_font(25)
    if title_font is None or meta_font is None or label_font is None:
        return {"status": "TOOL_BLOCKED", "errors": ["motion_cjk_font_unavailable"]}

    rows = math.ceil(len(sealed_panels) / columns)
    canvas_width = max(2400, columns * 900)
    margin, gap, header, footer = 64, 30, 190, 130
    cell_width = (canvas_width - margin * 2 - gap * (columns - 1)) // columns
    cell_height = 720
    canvas_height = header + footer + margin + rows * cell_height + gap * (rows - 1)
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 40), "动作分镜规划板", fill="black", font=title_font)
    draw.text((margin, 105), "实线：人物位移　折线/弧线：动作轨迹　虚线：摄影机运动　｜　固定机位仅标注固定", fill="black", font=meta_font)
    panel_receipts: list[dict[str, Any]] = []
    for index, (panel, payload, evidence) in enumerate(sealed_panels):
        row, column = divmod(index, columns)
        left = margin + column * (cell_width + gap)
        top = header + row * (cell_height + gap)
        right, bottom = left + cell_width, top + cell_height
        draw.rectangle((left, top, right, bottom), outline="black", width=4)
        annotations = panel["motion_annotations"]
        meta = f"{panel['panel_id']} ｜ {panel['shot_id']} ｜ {panel['phase']} ｜ {panel['at_seconds']}s"
        draw.text((left + 15, top + 12), _fit_text(draw, meta, font=label_font, max_width=cell_width - 30), fill="black", font=label_font)
        draw.text((left + 15, top + 48), _fit_text(draw, str(panel["camera_setup"]), font=label_font, max_width=cell_width - 30), fill="black", font=label_font)
        image_top = top + 92
        image_rect = (left + 14, image_top, right - 14, bottom - 16)
        with Image.open(io.BytesIO(payload)) as source:
            source.load()
            contained = ImageOps.contain(source.convert("RGB"), (image_rect[2] - image_rect[0], image_rect[3] - image_rect[1]), method=Image.Resampling.LANCZOS)
        paste_x = image_rect[0] + (image_rect[2] - image_rect[0] - contained.width) // 2
        paste_y = image_rect[1] + (image_rect[3] - image_rect[1] - contained.height) // 2
        canvas.paste(contained, (paste_x, paste_y))
        actual_rect = (paste_x, paste_y, paste_x + contained.width, paste_y + contained.height)
        _draw_motion_annotations(draw, annotations, image_rect=actual_rect, font=label_font)
        panel_receipts.append({
            "panel_id": panel["panel_id"], "shot_id": panel["shot_id"], "phase": panel["phase"],
            "planning_image_sha256": evidence["sha256"], "motion_annotations": annotations,
            "rect": {"left": left, "top": top, "right": right, "bottom": bottom},
            "image_rect": {"left": actual_rect[0], "top": actual_rect[1], "right": actual_rect[2], "bottom": actual_rect[3]},
        })
    encoded = io.BytesIO()
    canvas.save(encoded, format="PNG", optimize=False, compress_level=9)
    output_bytes = encoded.getvalue()
    output_identity: tuple[int, int] | None = None
    receipt_identity: tuple[int, int] | None = None
    try:
        output_identity = _write_new_file(output_path, output_bytes)
        final_output = read_relative_regular_file_once(resolved_root, output_path.relative_to(resolved_root).as_posix(), max_bytes=MAX_FRAME_BYTES, label="motion storyboard board")
    except (OSError, ValueError):
        _remove_if_identity(output_path, output_identity)
        return {"status": "blocked", "errors": ["motion_output_write_or_readback_failed"]}
    if final_output != output_bytes:
        _remove_if_identity(output_path, output_identity)
        return {"status": "blocked", "errors": ["motion_output_readback_mismatch"]}
    receipt = {
        "contract_id": MOTION_BOARD_CONTRACT_ID, "status": "assembled", "visual_quality": "unverified",
        "coverage_sha256": hashlib.sha256(sealed_coverage_bytes).hexdigest(), "motion_inputs_sha256": planning_input_sha256,
        "panel_ids": panel_ids, "panels": panel_receipts,
        "layout": {"columns": columns, "rows": rows, "width": canvas_width, "height": canvas_height},
        "output_relative_path": output_path.relative_to(resolved_root).as_posix(), "output_sha256": hashlib.sha256(final_output).hexdigest(),
        "assembled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "generation_tool_used": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    receipt_bytes = (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        receipt_identity = _write_new_file(receipt_path, receipt_bytes)
        final_receipt = read_relative_regular_file_once(resolved_root, receipt_path.relative_to(resolved_root).as_posix(), max_bytes=MAX_PLAN_BYTES, label="motion storyboard receipt")
    except (OSError, ValueError):
        _remove_if_identity(receipt_path, receipt_identity)
        _remove_if_identity(output_path, output_identity)
        return {"status": "blocked", "errors": ["motion_receipt_write_or_readback_failed_output_rolled_back"]}
    if final_receipt != receipt_bytes:
        _remove_if_identity(receipt_path, receipt_identity)
        _remove_if_identity(output_path, output_identity)
        return {"status": "blocked", "errors": ["motion_receipt_readback_mismatch_output_rolled_back"]}
    return receipt


def assemble_model_annotation_layout(
    sealed_coverage_bytes: bytes, *, project_root: Path, panel_ids: list[str], columns: int,
    output_path: Path, receipt_path: Path, cell_size: tuple[int, int] = (1024, 768),
    legend_crop: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lay out existing model-annotated PNGs; no drawing, lettering or generation."""
    if Image is None:
        return {"status": "TOOL_BLOCKED", "errors": ["pillow_unavailable"]}
    paths = _new_project_paths(project_root=project_root, output_path=output_path, receipt_path=receipt_path)
    if paths is None:
        return {"status": "blocked", "errors": ["model_layout_output_or_receipt_not_new"]}
    root, output_path, receipt_path = paths
    try:
        plan = json.loads(sealed_coverage_bytes.decode("utf-8"))
        if not isinstance(plan, dict):
            raise ValueError("model_layout_coverage_invalid")
        canvas, metadata = storyboard_coverage.render_model_annotation_layout(
            plan, project_root=root, panel_ids=panel_ids, columns=columns, cell_size=cell_size, legend_crop=legend_crop,
        )
        encoded = io.BytesIO()
        canvas.save(encoded, format="PNG", optimize=False, compress_level=9)
        output_bytes = encoded.getvalue()
    except (OSError, UnicodeDecodeError, ValueError, TypeError, KeyError) as exc:
        return {"status": "blocked", "errors": [str(exc)]}
    receipt = {
        "contract_id": storyboard_coverage.MODEL_ANNOTATION_LAYOUT_CONTRACT_ID, "status": "assembled",
        "assembled": True, "generated": False, "annotation_source": "model_generated",
        "generation_tool_used": False, "visual_quality": "unverified",
        "coverage_sha256": hashlib.sha256(sealed_coverage_bytes).hexdigest(),
        "motion_inputs_sha256": storyboard_coverage.motion_inputs_sha256(plan, panel_ids),
        **metadata, "output_relative_path": output_path.relative_to(root).as_posix(),
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "assembled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    receipt_bytes = (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    output_identity = receipt_identity = None
    try:
        output_identity = _write_new_file(output_path, output_bytes)
        if read_relative_regular_file_once(root, receipt["output_relative_path"], max_bytes=MAX_FRAME_BYTES, label="model annotation layout") != output_bytes:
            raise ValueError("model_layout_output_readback_mismatch")
        receipt_identity = _write_new_file(receipt_path, receipt_bytes)
        if read_relative_regular_file_once(root, receipt_path.relative_to(root).as_posix(), max_bytes=MAX_PLAN_BYTES, label="model annotation layout receipt") != receipt_bytes:
            raise ValueError("model_layout_receipt_readback_mismatch")
    except (OSError, ValueError) as exc:
        _remove_if_identity(receipt_path, receipt_identity)
        _remove_if_identity(output_path, output_identity)
        return {"status": "blocked", "errors": [str(exc)]}
    return receipt


def _read_absolute_regular_file_once(path: Path, *, max_bytes: int, label: str) -> tuple[Path, bytes]:
    raw = path.expanduser()
    if raw.is_symlink():
        raise ValueError(f"{label}_symlink_invalid")
    resolved = raw.resolve(strict=True)
    payload = read_relative_regular_file_once(
        resolved.parent, resolved.name, max_bytes=max_bytes, label=label,
    )
    return resolved, payload


def _sheet_cells(cell_map: Any, *, source_sha256: str, width: int, height: int) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(cell_map, dict) or cell_map.get("sheet_sha256") != source_sha256:
        return [], ["sheet_map_sha256_mismatch"]
    cells = cell_map.get("cells")
    if not isinstance(cells, list) or not 1 <= len(cells) <= MAX_MOTION_CELLS:
        return [], ["sheet_map_cells_invalid"]
    normalized: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    rectangles: list[tuple[int, int, int, int]] = []
    for index, cell in enumerate(cells):
        panel_id = cell.get("panel_id") if isinstance(cell, dict) else None
        rect = cell.get("rect") if isinstance(cell, dict) else None
        if not isinstance(panel_id, str) or not storyboard_coverage.is_id(panel_id) or panel_id in identifiers:
            errors.append(f"sheet_map_panel_id_invalid:{index}")
            continue
        if not isinstance(rect, list) or len(rect) != 4 or any(isinstance(value, bool) or not isinstance(value, int) for value in rect):
            errors.append(f"sheet_map_rect_invalid:{panel_id}")
            continue
        left, top, right, bottom = rect
        if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
            errors.append(f"sheet_map_rect_out_of_bounds:{panel_id}")
            continue
        identifiers.add(panel_id)
        rectangles.append((left, top, right, bottom))
        normalized.append({"panel_id": panel_id, "rect": (left, top, right, bottom)})
    for index, first in enumerate(rectangles):
        for second in rectangles[index + 1:]:
            if first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]:
                errors.append("sheet_map_rectangles_overlap")
                break
        if "sheet_map_rectangles_overlap" in errors:
            break
    return normalized, errors


def extract_clean_sheet(
    *, sheet_path: Path, cell_map_path: Path, output_dir: Path, receipt_path: Path,
) -> dict[str, Any]:
    """Extract ordered, unannotated PNG cells from one sealed source sheet."""
    if Image is None:
        return {"status": "TOOL_BLOCKED", "errors": ["pillow_unavailable"]}
    try:
        source_path, source_bytes = _read_absolute_regular_file_once(sheet_path, max_bytes=MAX_FRAME_BYTES, label="source sheet")
        _map_path, map_bytes = _read_absolute_regular_file_once(cell_map_path, max_bytes=MAX_PLAN_BYTES, label="sheet cell map")
        cell_map = json.loads(map_bytes.decode("utf-8"))
        raw_output_dir = output_dir.expanduser()
        if raw_output_dir.is_symlink():
            raise ValueError("sheet_output_dir_symlink_invalid")
        resolved_output_dir = raw_output_dir.resolve(strict=True)
        if not resolved_output_dir.is_dir():
            raise ValueError("sheet_output_dir_invalid")
        with Image.open(io.BytesIO(source_bytes)) as source:
            source.load()
            if source.format != "PNG":
                raise ValueError("sheet_source_not_png")
            source_width, source_height = source.size
            source_image = source.copy()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {"status": "blocked", "errors": ["sheet_input_invalid"]}
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    cells, errors = _sheet_cells(cell_map, source_sha256=source_sha256, width=source_width, height=source_height)
    if errors:
        return {"status": "blocked", "errors": errors}
    try:
        raw_receipt = receipt_path.expanduser()
        if raw_receipt.is_symlink():
            raise ValueError("receipt_symlink")
        normalized_receipt = raw_receipt.parent.resolve(strict=True) / raw_receipt.name
        normalized_receipt.relative_to(resolved_output_dir)
        if normalized_receipt.parent != resolved_output_dir:
            raise ValueError("sheet_receipt_parent_invalid")
    except (OSError, ValueError):
        return {"status": "blocked", "errors": ["sheet_receipt_path_invalid"]}
    outputs = [resolved_output_dir / f"{cell['panel_id']}.clean.png" for cell in cells]
    if normalized_receipt in outputs or normalized_receipt.exists() or normalized_receipt.is_symlink() or any(path.exists() or path.is_symlink() for path in outputs):
        return {"status": "blocked", "errors": ["sheet_output_or_receipt_must_be_new"]}

    output_identities: list[tuple[Path, tuple[int, int] | None]] = []
    receipt_identity: tuple[int, int] | None = None
    receipt_cells: list[dict[str, Any]] = []
    try:
        for cell, output in zip(cells, outputs):
            cropped = source_image.crop(cell["rect"])
            encoded = io.BytesIO()
            cropped.save(encoded, format="PNG", optimize=False, compress_level=9)
            output_bytes = encoded.getvalue()
            identity = _write_new_file(output, output_bytes)
            output_identities.append((output, identity))
            final_bytes = read_relative_regular_file_once(resolved_output_dir, output.name, max_bytes=MAX_FRAME_BYTES, label=f"clean sheet cell {cell['panel_id']}")
            if final_bytes != output_bytes:
                raise ValueError("sheet_cell_readback_mismatch")
            with Image.open(io.BytesIO(final_bytes)) as final_image:
                final_image.load()
                if final_image.size != (cell["rect"][2] - cell["rect"][0], cell["rect"][3] - cell["rect"][1]):
                    raise ValueError("sheet_cell_dimensions_mismatch")
            receipt_cells.append({
                "panel_id": cell["panel_id"], "rect": list(cell["rect"]),
                "output_relative_path": output.name, "output_sha256": hashlib.sha256(final_bytes).hexdigest(),
                "width": cell["rect"][2] - cell["rect"][0], "height": cell["rect"][3] - cell["rect"][1],
            })
    except (OSError, ValueError):
        for output, identity in reversed(output_identities):
            _remove_if_identity(output, identity)
        return {"status": "blocked", "errors": ["sheet_output_write_or_readback_failed"]}
    receipt = {
        "contract_id": SHEET_EXTRACTION_CONTRACT_ID, "status": "extracted",
        "source_sheet_relative_path": source_path.name, "source_sheet_sha256": source_sha256,
        "cell_map_sha256": hashlib.sha256(map_bytes).hexdigest(),
        "source_width": source_width, "source_height": source_height,
        "coordinate_system": "source_png_top_left_pixels_half_open", "cells": receipt_cells,
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    receipt_bytes = (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        receipt_identity = _write_new_file(normalized_receipt, receipt_bytes)
        final_receipt = read_relative_regular_file_once(resolved_output_dir, normalized_receipt.name, max_bytes=MAX_PLAN_BYTES, label="sheet extraction receipt")
        if final_receipt != receipt_bytes:
            raise ValueError("sheet_receipt_readback_mismatch")
    except (OSError, ValueError):
        _remove_if_identity(normalized_receipt, receipt_identity)
        for output, identity in reversed(output_identities):
            _remove_if_identity(output, identity)
        return {"status": "blocked", "errors": ["sheet_receipt_write_or_readback_failed_output_rolled_back"]}
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a professional storyboard overview from approved frame PNGs.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--plan", type=Path)
    source.add_argument("--coverage", type=Path)
    source.add_argument("--extract-sheet", type=Path)
    parser.add_argument("--asset-id")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--panel-ids", nargs="+", help="Ordered IDs, separated by spaces or commas.")
    parser.add_argument("--columns", type=int)
    parser.add_argument("--cell-map", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--execution-task-id")
    parser.add_argument("--layout-only", action="store_true", help="Only place existing model-annotated PNGs on white; no new marks or upscaling.")
    parser.add_argument("--cell-size", help="Layout-only maximum cell WIDTHxHEIGHT; defaults to 1024x768.")
    parser.add_argument("--legend-crop", type=Path, help="Layout-only JSON: panel_id, optional source=source_sheet, and lossless pixel rect.")
    args = parser.parse_args()
    try:
        if (args.layout_only or args.cell_size is not None or args.legend_crop is not None) and args.coverage is None:
            raise ValueError("model_layout_requires_coverage")
        if (args.cell_size is not None or args.legend_crop is not None) and not args.layout_only:
            raise ValueError("model_layout_options_require_layout_only")
        if args.extract_sheet is not None:
            if any(value is not None for value in (args.asset_id, args.project_root, args.panel_ids, args.columns, args.output)) or args.cell_map is None or args.output_dir is None:
                raise ValueError("sheet_extraction_arguments_invalid")
            result = extract_clean_sheet(
                sheet_path=args.extract_sheet, cell_map_path=args.cell_map,
                output_dir=args.output_dir, receipt_path=args.receipt,
            )
        elif args.coverage is not None:
            if args.asset_id is not None or args.project_root is None or not args.panel_ids or args.columns is None or args.output is None or args.cell_map is not None or args.output_dir is not None:
                raise ValueError("motion_arguments_invalid")
            project_root = args.project_root.expanduser().resolve(strict=True)
            coverage_path = args.coverage.expanduser().resolve(strict=True)
            coverage_relative = coverage_path.relative_to(project_root).as_posix()
            coverage_bytes = read_relative_regular_file_once(project_root, coverage_relative, max_bytes=MAX_PLAN_BYTES, label="storyboard coverage")
            if args.layout_only:
                size = tuple(int(value) for value in (args.cell_size or "1024x768").split("x"))
                legend = None
                if args.legend_crop is not None:
                    raw_legend = args.legend_crop.expanduser()
                    if raw_legend.is_symlink():
                        raise ValueError("model_layout_legend_file_symlink_invalid")
                    legend_path = raw_legend.resolve(strict=True)
                    legend = json.loads(read_relative_regular_file_once(project_root, legend_path.relative_to(project_root).as_posix(), max_bytes=MAX_PLAN_BYTES, label="model layout legend crop").decode("utf-8"))
                result = assemble_model_annotation_layout(coverage_bytes, project_root=project_root,
                    panel_ids=[item for group in args.panel_ids for item in group.split(",")], columns=args.columns, cell_size=size, legend_crop=legend,
                    output_path=args.output.expanduser().resolve(strict=False), receipt_path=args.receipt.expanduser().resolve(strict=False))
            else:
                result = assemble_motion_board(
                    coverage_bytes, project_root=project_root,
                    panel_ids=[item for group in args.panel_ids for item in group.split(",")], columns=args.columns,
                    output_path=args.output.expanduser().resolve(strict=False), receipt_path=args.receipt.expanduser().resolve(strict=False),
                )
        else:
            if args.asset_id is None or args.project_root is not None or args.panel_ids is not None or args.columns is not None or args.output is None or args.cell_map is not None or args.output_dir is not None:
                raise ValueError("assembly_arguments_invalid")
            plan_path = args.plan.expanduser().resolve(strict=True)
            base_dir = plan_path.parent
            plan_bytes = read_relative_regular_file_once(base_dir, plan_path.name, max_bytes=MAX_PLAN_BYTES, label="visual asset plan")
            output_path = args.output.expanduser().resolve(strict=False)
            receipt_path = args.receipt.expanduser().resolve(strict=False)
            output_path.relative_to(base_dir)
            receipt_path.relative_to(base_dir)
            result = assemble(plan_bytes, base_dir=base_dir, asset_id=args.asset_id, output_path=output_path, receipt_path=receipt_path, execution_task_id=args.execution_task_id)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        result = {"status": "blocked", "errors": [f"input_or_output_invalid:{type(exc).__name__}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"assembled", "extracted"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
