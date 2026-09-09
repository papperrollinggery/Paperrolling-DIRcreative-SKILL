#!/usr/bin/env python3
"""Validate explicit, panel-level storyboard coverage without changing asset plans.

This sidecar deliberately treats technical shots, within-shot panels, clean inputs,
and generation units as separate concepts.  It only validates declared coverage.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import re
import stat
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from dircreative_visual_asset_plan import inspect_raster, validate_plan as validate_legacy_plan
from dircreative_verify_release import read_relative_regular_file_once

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]


SCHEMA_VERSION = "1.0"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
TIMECODE_RE = re.compile(
    r"^(?P<sm>\d{2,}):(?P<ss>[0-5]\d(?:\.\d+)?)-(?P<em>\d{2,}):(?P<es>[0-5]\d(?:\.\d+)?)$"
)
KINDS = {"action", "dialogue", "reaction", "reveal", "establish", "transition", "hold"}
RISKS = {"low", "medium", "high"}
IMAGE_STATUSES = {"planned", "available"}
LOOKS = {"left", "right", "center", "not_applicable"}
SCOPES = {"whole_film", "sequence"}
MAX_JSON_BYTES = 16 * 1024 * 1024
ANNOTATION_SOURCES = {"manual_overlay", "model_generated"}
MODEL_ANNOTATION_KINDS = {
    "action", "actor_path", "camera", "environment", "lighting", "sound", "emotion",
}
SHEET_EXTRACTION_CONTRACT_ID = "storyboard_clean_sheet_extraction_v1"
MODEL_ANNOTATION_LAYOUT_CONTRACT_ID = "model_annotation_layout_v1"


def describe_input() -> dict[str, Any]:
    """Return the editable coverage shape without inspecting or changing a project.

    Keep enum values sourced from the validator constants so this discovery output
    cannot become a parallel authoring contract.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "--describe-input",
        "read_only": True,
        "notes": [
            "Read this once before authoring an unfamiliar coverage file; then batch author the requirements and panels.",
            "This describes declared coverage only. Planned images and planning evidence are not generated or accepted production images.",
        ],
        "allowed_values": {
            "scope": sorted(SCOPES),
            "requirement.kind": sorted(KINDS),
            "requirement.risk": sorted(RISKS),
            "panel.image.status": sorted(IMAGE_STATUSES),
            "panel.look_direction": sorted(LOOKS),
        },
        "look_direction": {
            "left": "The viewed subject looks toward screen left.",
            "right": "The viewed subject looks toward screen right.",
            "center": "The subject has no lateral screen look, for example faces camera.",
            "not_applicable": "No meaningful gaze direction applies to this panel.",
            "eyeline_pairs": "A conventional reverse pair needs left/right values that oppose each other; use axis_break_reason for a deliberate exception.",
        },
        "minimum_editable_object": {
            "schema_version": SCHEMA_VERSION,
            "project_id": "PROJECT_ID",
            "frame_rate_fps": 24,
            "scope": "sequence",
            "shot_cards_file": "shot-cards.json",
            "shot_cards_sha256": "CANONICAL_JSON_SHA256",
            "requirements": [{
                "requirement_id": "REQ_01",
                "source_anchor": "script-or-cards anchor",
                "kind": "action",
                "shot_ids": ["S01"],
                "phases": ["start", "contact", "result"],
                "risk": "medium",
                "image_required": True,
            }],
            "panels": [{
                "panel_id": "P01",
                "shot_id": "S01",
                "requirement_id": "REQ_01",
                "phase": "start",
                "at_seconds": 0.0,
                "state": "visible starting state",
                "camera_setup": "camera position and framing",
                "view_subject": "visible subject",
                "gaze_target": "gaze target",
                "axis_id": "shared axis",
                "axis_side": "declared side",
                "look_direction": "left",
                "image": {"status": "planned"},
            }],
        },
        "field_rules": {
            "ids": "IDs are 1-128 characters matching ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$.",
            "phases": "Requirement and panel phases are author-defined non-empty strings; every declared requirement phase needs a panel.",
            "available_image": "An available image additionally needs a project-relative PNG path and its lowercase SHA-256. A planned image must not bind path or sha256.",
            "high_risk": "High-risk requirements must set image_required to true.",
        },
    }


def json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return None
    return result if math.isfinite(result) else None


def parse_timecode(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    match = TIMECODE_RE.fullmatch(value.strip())
    if match is None:
        return None
    try:
        start = Decimal(match["sm"]) * 60 + Decimal(match["ss"])
        end = Decimal(match["em"]) * 60 + Decimal(match["es"])
    except InvalidOperation:
        return None
    try:
        start_float, end_float = float(start), float(end)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(start_float) or not math.isfinite(end_float) or start < 0 or end <= start:
        return None
    return start_float, end_float


def is_id(value: Any) -> bool:
    return isinstance(value, str) and ID_RE.fullmatch(value) is not None


def nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def duplicate(values: list[str]) -> set[str]:
    seen: set[str] = set()
    result: set[str] = set()
    for value in values:
        if value in seen:
            result.add(value)
        seen.add(value)
    return result


def contained_regular_file(root: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        return None
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    try:
        root_resolved = root.resolve(strict=True)
        candidate = root_resolved
        for part in relative.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                return None
        resolved = (root / relative).resolve(strict=True)
        resolved.relative_to(root_resolved)
        mode = resolved.stat().st_mode
    except (OSError, ValueError):
        return None
    return resolved if stat.S_ISREG(mode) else None


def load_json_object(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("json_file_too_large")
    payload = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_object_required")
    return payload


def contained_input_file(root: Path, raw: Path | str) -> Path | None:
    raw_path = Path(raw)
    if raw_path.is_absolute():
        try:
            raw = raw_path.resolve(strict=True).relative_to(root.resolve(strict=True)).as_posix()
        except (OSError, ValueError):
            return None
    else:
        raw = raw_path.as_posix()
    return contained_regular_file(root, raw)


def source_shots(root: Path, raw_file: Any, expected_hash: Any) -> tuple[dict[str, tuple[float, float]], list[str], list[str]]:
    errors: list[str] = []
    path = contained_regular_file(root, raw_file)
    if path is None:
        return {}, [], ["shot_cards_file_invalid_or_outside_project_root"]
    try:
        payload = load_json_object(path)
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}, [], ["shot_cards_json_invalid"]
    if not isinstance(payload.get("cards"), list):
        return {}, [], ["shot_cards_shape_invalid"]
    if not isinstance(expected_hash, str) or SHA256_RE.fullmatch(expected_hash) is None:
        errors.append("shot_cards_sha256_invalid")
    elif expected_hash != json_hash(payload):
        errors.append("shot_cards_sha256_mismatch")
    shots: dict[str, tuple[float, float]] = {}
    order: list[str] = []
    prior_end = -1.0
    for card in payload["cards"]:
        if not isinstance(card, dict) or not is_id(card.get("shot_id")):
            errors.append("shot_card_identity_invalid")
            continue
        shot_id = card["shot_id"]
        interval = parse_timecode(card.get("timecode"))
        if shot_id in shots:
            errors.append(f"shot_card_duplicate:{shot_id}")
        elif interval is None or interval[0] < prior_end:
            errors.append(f"shot_card_timing_invalid:{shot_id}")
        else:
            shots[shot_id] = interval
            order.append(shot_id)
            prior_end = interval[1]
    if not shots:
        errors.append("shot_cards_empty")
    return shots, order, errors


def source_aspect_ratio(root: Path, raw_file: Any) -> str | None:
    path = contained_regular_file(root, raw_file)
    if path is None:
        return None
    try:
        payload = load_json_object(path)
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    profile = payload.get("delivery_profile")
    ratio = profile.get("aspect_ratio") if isinstance(profile, dict) else None
    return ratio if isinstance(ratio, str) else None


def ratio_value(value: Any) -> float | None:
    if not isinstance(value, str) or value.count(":") != 1:
        return None
    left, right = value.split(":")
    try:
        numerator, denominator = float(left), float(right)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(numerator) or not math.isfinite(denominator) or numerator <= 0 or denominator <= 0:
        return None
    return numerator / denominator


def motion_panel_ids(plan: dict[str, Any]) -> list[str]:
    """Infer rehearsal needs from declared story risk, not a frame-count quota."""
    requirements = {
        item.get("requirement_id") for item in plan.get("requirements", [])
        if isinstance(item, dict) and (
            item.get("planning_required") is True
            or (item.get("kind") == "action" and item.get("risk") in ("medium", "high"))
        )
    }
    explicit = plan.get("motion_planning", {})
    selected = explicit.get("panel_ids", []) if isinstance(explicit, dict) else []
    selected = {value for value in selected if is_id(value)} if isinstance(selected, list) else set()
    known = {panel.get("panel_id") for panel in plan.get("panels", [])
             if isinstance(panel, dict) and is_id(panel.get("panel_id"))}
    boards = explicit.get("boards", []) if isinstance(explicit, dict) else []
    for board in boards if isinstance(boards, list) else []:
        if isinstance(board, dict) and board.get("annotation_source") == "model_generated":
            ids = board.get("panel_ids")
            if isinstance(ids, list):
                selected.update(value for value in ids if is_id(value) and value in known)
    return [
        panel["panel_id"] for panel in plan.get("panels", [])
        if isinstance(panel, dict) and is_id(panel.get("panel_id")) and (
            panel.get("requirement_id") in requirements or panel["panel_id"] in selected
        )
    ]


def motion_inputs_sha256(plan: dict[str, Any], panel_ids: list[str] | None = None) -> str:
    """Bind the drawing and annotations to the existing source, excluding outputs."""
    selected = set(motion_panel_ids(plan) if panel_ids is None else panel_ids)
    return json_hash({
        "project_id": plan.get("project_id"),
        "shot_cards_file": plan.get("shot_cards_file"),
        "shot_cards_sha256": plan.get("shot_cards_sha256"),
        "aspect_ratio": plan.get("aspect_ratio"),
        "panels": [
            {key: value for key, value in panel.items() if key != "image"}
            for panel in plan.get("panels", [])
            if isinstance(panel, dict) and panel.get("panel_id") in selected
        ],
    })


def motion_review_sha256(plan: dict[str, Any]) -> str:
    """A drawing review includes the actual pages at their reviewed reading size."""
    planning = plan.get("motion_planning", {})
    return json_hash({"inputs": motion_inputs_sha256(plan),
                      "legend": planning.get("legend") if isinstance(planning, dict) else None,
                      "boards": planning.get("boards", []) if isinstance(planning, dict) else []})


def _motion_receipt_matches(receipt: dict[str, Any], plan: dict[str, Any], ids: list[str], raster: dict[str, Any]) -> bool:
    layout, rows = receipt.get("layout"), receipt.get("panels")
    if receipt.get("contract_id") != "motion_storyboard_board_v1" or not isinstance(layout, dict) or not isinstance(rows, list) or len(rows) != len(ids):
        return False
    columns = layout.get("columns")
    if isinstance(columns, bool) or not isinstance(columns, int) or not 1 <= columns <= 3 or not 1 <= len(ids) <= 9:
        return False
    if layout.get("rows") != math.ceil(len(ids) / columns) or layout.get("width") != raster["width"] or layout.get("height") != raster["height"]:
        return False
    if receipt.get("receipt_sha256") != json_hash({key: value for key, value in receipt.items() if key != "receipt_sha256"}):
        return False
    panels = {panel["panel_id"]: panel for panel in plan["panels"]}
    for panel_id, row in zip(ids, rows):
        panel = panels[panel_id]
        if panel.get("planning_image", {}).get("annotation_source", "manual_overlay") != "manual_overlay":
            return False
        if not isinstance(row, dict) or row.get("panel_id") != panel_id or row.get("shot_id") != panel["shot_id"] or row.get("phase") != panel["phase"] or row.get("planning_image_sha256") != panel.get("planning_image", {}).get("sha256") or row.get("motion_annotations") != panel.get("motion_annotations"):
            return False
        rectangles = []
        for key in ("rect", "image_rect"):
            rect = row.get(key)
            if not isinstance(rect, dict) or any(finite_number(rect.get(field)) is None for field in ("left", "top", "right", "bottom")):
                return False
            if not 0 <= rect["left"] < rect["right"] <= raster["width"] or not 0 <= rect["top"] < rect["bottom"] <= raster["height"]:
                return False
            rectangles.append(rect)
        outer, inner = rectangles
        if inner["left"] < outer["left"] or inner["top"] < outer["top"] or inner["right"] > outer["right"] or inner["bottom"] > outer["bottom"]:
            return False
    return True


def _bound_planning_file(root: Path, binding: Any) -> Path | None:
    if not isinstance(binding, dict):
        return None
    path = contained_regular_file(root, binding.get("path"))
    if path is None or not isinstance(binding.get("sha256"), str):
        return None
    try:
        if path.stat().st_size > 128 * 1024 * 1024:
            return None
        return path if hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"] else None
    except OSError:
        return None


def _normalized_point(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and all(
        finite_number(number) is not None and 0 <= number <= 1 for number in value
    )


def _pixel_rect(value: Any, *, width: int, height: int) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4 or any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        return None
    left, top, right, bottom = value
    return value if 0 <= left < right <= width and 0 <= top < bottom <= height else None


def _model_legend_errors(plan: dict[str, Any], kinds: set[str]) -> list[str]:
    if not kinds:
        return []
    planning = plan.get("motion_planning")
    legend = planning.get("legend") if isinstance(planning, dict) else None
    if not isinstance(legend, dict):
        return ["motion_model_legend_invalid"]
    errors: list[str] = []
    for kind in kinds:
        entry = legend.get(kind)
        if not isinstance(entry, dict) or not nonempty_text(entry.get("color")) or not nonempty_text(entry.get("label")):
            errors.append(f"motion_model_legend_missing:{kind}")
    return errors


def _model_generated_board_matches(
    receipt: dict[str, Any], *, plan: dict[str, Any], ids: list[str], raster: dict[str, Any],
    project_root: Path, receipt_path: Path, source_path: Path,
) -> bool:
    if Image is None:
        return False
    if not isinstance(ids, list) or not ids or not all(is_id(panel_id) for panel_id in ids) or duplicate(ids):
        return False
    if receipt.get("contract_id") != SHEET_EXTRACTION_CONTRACT_ID or receipt.get("status") != "extracted":
        return False
    if receipt.get("receipt_sha256") != json_hash({key: value for key, value in receipt.items() if key != "receipt_sha256"}):
        return False
    if (
        receipt.get("source_sheet_sha256") != raster.get("sha256")
        or receipt.get("source_width") != raster.get("width")
        or receipt.get("source_height") != raster.get("height")
        or receipt.get("coordinate_system") != "source_png_top_left_pixels_half_open"
    ):
        return False
    cells = receipt.get("cells")
    if not isinstance(cells, list) or len(cells) != len(ids):
        return False
    panels = {panel.get("panel_id"): panel for panel in plan.get("panels", []) if isinstance(panel, dict) and is_id(panel.get("panel_id"))}
    try:
        with Image.open(source_path) as source:
            source.load()
            if source.format != "PNG" or source.size != (raster["width"], raster["height"]):
                return False
            for panel_id, cell in zip(ids, cells):
                panel = panels.get(panel_id)
                binding = panel.get("planning_image") if isinstance(panel, dict) else None
                if not isinstance(cell, dict) or not isinstance(binding, dict) or cell.get("panel_id") != panel_id or binding.get("annotation_source") != "model_generated":
                    return False
                rect = _pixel_rect(cell.get("rect"), width=raster["width"], height=raster["height"])
                relative = cell.get("output_relative_path")
                if rect is None or not isinstance(relative, str) or cell.get("output_sha256") != binding.get("sha256"):
                    return False
                expected_crop = contained_regular_file(receipt_path.parent, relative)
                bound_crop = _bound_planning_file(project_root, binding)
                if expected_crop is None or bound_crop is None or expected_crop != bound_crop:
                    return False
                try:
                    if expected_crop.stat().st_size > 128 * 1024 * 1024 or hashlib.sha256(expected_crop.read_bytes()).hexdigest() != cell["output_sha256"]:
                        return False
                except OSError:
                    return False
                crop, _reason = inspect_raster(
                    expected_crop,
                    allow_derived_planning_crop=True,
                )
                if crop is None or crop.get("width") != cell.get("width") or crop.get("height") != cell.get("height") or crop["width"] != rect[2] - rect[0] or crop["height"] != rect[3] - rect[1]:
                    return False
                with Image.open(expected_crop) as candidate:
                    candidate.load()
                    if source.crop(tuple(rect)).convert("RGBA").tobytes() != candidate.convert("RGBA").tobytes():
                        return False
    except (OSError, ValueError):
        return False
    return True


def _derived_model_generated_crop_evidence(
    *,
    plan: dict[str, Any],
    project_root: Path,
    panel_id: str,
    binding: dict[str, Any],
    path: Path,
) -> dict[str, Any] | None:
    """Return a below-minimum crop only when a sealed source board proves it.

    The source board still passes the normal canonical raster inspection.  This
    helper only selects the narrow planning-crop exception after the receipt
    binds the panel id, crop path/hash, exact source rectangle, and decoded
    source/crop pixels.  It is intentionally not used by production checks.
    """
    planning = plan.get("motion_planning")
    boards = planning.get("boards") if isinstance(planning, dict) else None
    if (
        not isinstance(boards, list)
        or _bound_planning_file(project_root, binding) != path
    ):
        return None
    for board in boards:
        if (
            not isinstance(board, dict)
            or board.get("annotation_source") != "model_generated"
            or not isinstance(board.get("panel_ids"), list)
            or panel_id not in board["panel_ids"]
        ):
            continue
        source_path = _bound_planning_file(project_root, board.get("image"))
        receipt_path = _bound_planning_file(project_root, board.get("receipt"))
        if source_path is None or receipt_path is None:
            continue
        source_raster, _reason = inspect_raster(source_path)
        if source_raster is None or source_raster.get("format") != "PNG":
            continue
        try:
            receipt = load_json_object(receipt_path)
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not _model_generated_board_matches(
            receipt,
            plan=plan,
            ids=board["panel_ids"],
            raster=source_raster,
            project_root=project_root,
            receipt_path=receipt_path,
            source_path=source_path,
        ):
            continue
        evidence, _reason = inspect_raster(
            path,
            allow_derived_planning_crop=True,
        )
        if evidence is not None and evidence.get("format") == "PNG":
            return evidence
    return None


def _layout_legend_source_sheet(plan: dict[str, Any], project_root: Path, panel_id: str) -> tuple[Path, dict[str, str], str]:
    """Find one native sheet whose lossless extraction proves the anchor panel."""
    candidates: list[tuple[Path, dict[str, str], str]] = []
    planning = plan.get("motion_planning", {})
    boards = planning.get("boards", []) if isinstance(planning, dict) else []
    for board in boards if isinstance(boards, list) else []:
        if (
            not isinstance(board, dict) or board.get("annotation_source") != "model_generated"
            or board.get("acquisition", "native_generate") != "native_generate"
            or not isinstance(board.get("panel_ids"), list) or not all(is_id(value) for value in board["panel_ids"])
            or panel_id not in board.get("panel_ids", [])
        ):
            continue
        image_path = _bound_planning_file(project_root, board.get("image"))
        receipt_path = _bound_planning_file(project_root, board.get("receipt"))
        if image_path is None or receipt_path is None:
            continue
        raster, _ = inspect_raster(image_path)
        if raster is None:
            continue
        try:
            receipt = load_json_object(receipt_path)
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if _model_generated_board_matches(receipt, plan=plan, ids=board["panel_ids"], raster=raster,
                                          project_root=project_root, receipt_path=receipt_path, source_path=image_path):
            candidates.append((image_path, {"path": receipt_path.relative_to(project_root).as_posix(), "sha256": board["receipt"]["sha256"]}, board["image"]["sha256"]))
    if len(candidates) != 1:
        raise ValueError("layout_legend_source_sheet_missing_or_ambiguous")
    return candidates[0]


def render_model_annotation_layout(
    plan: dict[str, Any], *, project_root: Path, panel_ids: list[str], columns: int,
    cell_size: tuple[int, int] = (1024, 768), legend_crop: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Pure document layout: copy/contain native PNGs on white, never draw marks."""
    if Image is None:
        raise ValueError("pillow_unavailable")
    project_root = project_root.resolve(strict=True)
    if (
        not isinstance(panel_ids, list) or not panel_ids or not all(is_id(item) for item in panel_ids) or duplicate(panel_ids)
        or isinstance(columns, bool) or not isinstance(columns, int) or not 1 <= columns <= len(panel_ids)
        or not isinstance(cell_size, (tuple, list)) or len(cell_size) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in cell_size)
    ):
        raise ValueError("model_layout_arguments_invalid")
    if validate(plan, project_root, "design").get("status") != "valid":
        raise ValueError("model_layout_design_invalid")
    available = validate_motion_planning(plan, project_root, require_review=False, panel_ids=panel_ids)
    if available.get("status") != "valid":
        raise ValueError("model_layout_inputs_invalid:" + ",".join(available.get("errors", []) + available.get("missing", [])))
    panel_map = {panel["panel_id"]: panel for panel in plan["panels"]}
    if panel_ids != [panel["panel_id"] for panel in plan["panels"] if panel["panel_id"] in set(panel_ids)]:
        raise ValueError("model_layout_panel_order_invalid")
    sources: dict[str, tuple[bytes, dict[str, Any]]] = {}
    total_bytes = 0
    for panel_id in panel_ids:
        binding = panel_map[panel_id]["planning_image"]
        if binding.get("annotation_source") != "model_generated":
            raise ValueError("model_layout_requires_native_annotations")
        payload = read_relative_regular_file_once(project_root, binding["path"], max_bytes=128 * 1024 * 1024, label="native layout panel")
        if hashlib.sha256(payload).hexdigest() != binding["sha256"]:
            raise ValueError("model_layout_source_hash_mismatch")
        total_bytes += len(payload)
        if total_bytes > 256 * 1024 * 1024:
            raise ValueError("model_layout_sources_too_large")
        with Image.open(io.BytesIO(payload)) as source:
            source.load()
            if source.format != "PNG":
                raise ValueError("model_layout_source_not_png")
            sources[panel_id] = (payload, {"panel_id": panel_id, "shot_id": panel_map[panel_id]["shot_id"],
                "phase": panel_map[panel_id]["phase"], "source_relative_path": binding["path"], "source_sha256": binding["sha256"],
                "source_width": source.width, "source_height": source.height})
    legend_data: bytes | None = None
    legend: dict[str, Any] | None = None
    normalized_legend: dict[str, Any] | None = None
    if legend_crop is not None:
        if (
            not isinstance(legend_crop, dict) or set(legend_crop) not in ({"panel_id", "rect"}, {"panel_id", "source", "rect"})
            or legend_crop.get("panel_id") not in sources
            or legend_crop.get("source", "planning_image") not in {"planning_image", "source_sheet"}
        ):
            raise ValueError("model_layout_legend_binding_invalid")
        panel_id = legend_crop["panel_id"]
        source_kind = legend_crop.get("source", "planning_image")
        native_receipt = None
        if source_kind == "source_sheet":
            path, native_receipt, expected_sheet_hash = _layout_legend_source_sheet(plan, project_root, panel_id)
            relative = path.relative_to(project_root).as_posix()
            legend_data = read_relative_regular_file_once(project_root, relative, max_bytes=128 * 1024 * 1024, label="native legend source sheet")
            if hashlib.sha256(legend_data).hexdigest() != expected_sheet_hash:
                raise ValueError("model_layout_legend_source_hash_mismatch")
        else:
            legend_data, source_record = sources[panel_id]
            relative = source_record["source_relative_path"]
        with Image.open(io.BytesIO(legend_data)) as source:
            source.load()
            rect = _pixel_rect(legend_crop.get("rect"), width=source.width, height=source.height)
            if rect is None:
                raise ValueError("model_layout_legend_rect_invalid")
            normalized_legend = {"panel_id": panel_id, "source": source_kind, "rect": rect}
            legend = {"panel_id": panel_id, "source": source_kind, "source_relative_path": relative,
                      "source_sha256": hashlib.sha256(legend_data).hexdigest(), "source_width": source.width,
                      "source_height": source.height, "source_rect": rect, "source_extraction_receipt": native_receipt}
    cell_width, cell_height = cell_size
    rows = math.ceil(len(panel_ids) / columns)
    margin = gap = 24
    grid_width = columns * cell_width + (columns - 1) * gap
    grid_height = rows * cell_height + (rows - 1) * gap
    legend_width = legend["source_rect"][2] - legend["source_rect"][0] if legend else 0
    legend_height = legend["source_rect"][3] - legend["source_rect"][1] if legend else 0
    width = max(640, grid_width + 2 * margin, legend_width + 2 * margin)
    height = max(360, grid_height + 2 * margin + (gap + legend_height if legend else 0))
    if width * height > 100_000_000:
        raise ValueError("model_layout_canvas_too_large")
    canvas = Image.new("RGBA", (width, height), "white")
    grid_left = (width - grid_width) // 2
    placed = []
    for index, panel_id in enumerate(panel_ids):
        payload, row = sources[panel_id]
        with Image.open(io.BytesIO(payload)) as source:
            source.load()
            rendered = source.convert("RGBA")
            rendered.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS, reducing_gap=None)
            x = grid_left + (index % columns) * (cell_width + gap) + (cell_width - rendered.width) // 2
            y = margin + (index // columns) * (cell_height + gap) + (cell_height - rendered.height) // 2
            canvas.alpha_composite(rendered, (x, y))
            placed.append({**row, "source_rect": [0, 0, row["source_width"], row["source_height"]],
                           "placed_rect": [x, y, x + rendered.width, y + rendered.height]})
    if legend is not None and legend_data is not None:
        with Image.open(io.BytesIO(legend_data)) as source:
            source.load()
            cropped = source.crop(tuple(legend["source_rect"])).convert("RGBA")
            x, y = (width - cropped.width) // 2, margin + grid_height + gap
            canvas.alpha_composite(cropped, (x, y))
            legend["placed_rect"] = [x, y, x + cropped.width, y + cropped.height]
    metadata = {"panel_ids": panel_ids, "panels": placed, "legend_crop": normalized_legend, "legend": legend,
                "layout": {"columns": columns, "rows": rows, "cell_width": cell_width, "cell_height": cell_height,
                           "width": width, "height": height, "margin": margin, "gap": gap,
                           "resample": "lanczos", "background": "white", "alpha_composite": "over_white", "allow_upscale": False}}
    return canvas.convert("RGB"), metadata


def _model_annotation_layout_matches(
    receipt: dict[str, Any], *, plan: dict[str, Any], ids: list[str], raster: dict[str, Any],
    project_root: Path, source_path: Path,
) -> bool:
    try:
        project_root = project_root.resolve(strict=True)
        output_relative = source_path.relative_to(project_root).as_posix()
    except (OSError, ValueError):
        return False
    if (
        receipt.get("contract_id") != MODEL_ANNOTATION_LAYOUT_CONTRACT_ID or receipt.get("status") != "assembled"
        or receipt.get("assembled") is not True or receipt.get("generated") is not False
        or receipt.get("annotation_source") != "model_generated" or receipt.get("generation_tool_used") is not False
        or receipt.get("receipt_sha256") != json_hash({key: value for key, value in receipt.items() if key != "receipt_sha256"})
        or receipt.get("panel_ids") != ids or receipt.get("motion_inputs_sha256") != motion_inputs_sha256(plan, ids)
        or receipt.get("output_sha256") != raster.get("sha256")
        or receipt.get("output_relative_path") != output_relative
    ):
        return False
    try:
        layout = receipt["layout"]
        expected, metadata = render_model_annotation_layout(plan, project_root=project_root, panel_ids=ids,
            columns=layout["columns"], cell_size=(layout["cell_width"], layout["cell_height"]), legend_crop=receipt.get("legend_crop"))
        if any(receipt.get(key) != value for key, value in metadata.items()):
            return False
        with Image.open(source_path) as actual:
            actual.load()
            return actual.size == expected.size and actual.convert("RGBA").tobytes() == expected.convert("RGBA").tobytes()
    except (OSError, ValueError, TypeError, KeyError):
        return False


def validate_motion_planning(
    plan: dict[str, Any], project_root: Path, *, require_review: bool = True,
    panel_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Check planning evidence; an AI review file is not trusted visual approval."""
    errors: list[str] = []
    missing: list[str] = []
    required = motion_panel_ids(plan)
    selected = required if panel_ids is None else panel_ids
    panels = {item.get("panel_id"): item for item in plan.get("panels", [])
              if isinstance(item, dict) and is_id(item.get("panel_id"))}
    if not isinstance(selected, list) or not all(is_id(value) for value in selected) or duplicate(selected):
        return {"status": "invalid", "errors": ["motion_panel_ids_invalid"], "missing": []}
    declared = plan.get("motion_planning")
    if declared is not None and not isinstance(declared, dict):
        errors.append("motion_planning_invalid")
    elif isinstance(declared, dict) and "panel_ids" in declared:
        ids = declared["panel_ids"]
        if not isinstance(ids, list) or not all(is_id(value) and value in panels for value in ids) or duplicate(ids):
            errors.append("motion_panel_ids_invalid")
    if not selected:
        return {"status": "invalid" if errors else "valid", "errors": errors, "missing": [], "required": False, "visual_quality": "unverified"}
    source_ratio = ratio_value(plan.get("aspect_ratio")) or ratio_value(source_aspect_ratio(project_root, plan.get("shot_cards_file")))
    action_images: dict[tuple[str, str], set[str]] = {}
    model_annotation_kinds: set[str] = set()
    for panel_id in selected:
        panel = panels.get(panel_id)
        if panel is None:
            errors.append(f"motion_panel_unknown:{panel_id}")
            continue
        binding = panel.get("planning_image")
        if not isinstance(binding, dict) or binding.get("status") == "planned":
            missing.append(f"motion_drawing:{panel_id}")
            continue
        if binding.get("status") != "available" or binding.get("presentation") not in ("line_art", "hand_drawn"):
            errors.append(f"motion_drawing_presentation_invalid:{panel_id}")
        annotation_source = binding.get("annotation_source", "manual_overlay")
        if annotation_source not in ANNOTATION_SOURCES:
            errors.append(f"motion_annotation_source_invalid:{panel_id}")
        path = _bound_planning_file(project_root, binding)
        if path is None:
            errors.append(f"motion_drawing_binding_invalid:{panel_id}")
            continue
        evidence, reason = inspect_raster(path)
        if (
            evidence is None
            and reason == "dimensions_below_minimum"
            and annotation_source == "model_generated"
        ):
            evidence = _derived_model_generated_crop_evidence(
                plan=plan,
                project_root=project_root,
                panel_id=panel_id,
                binding=binding,
                path=path,
            )
            reason = None if evidence is not None else reason
        if evidence is None or evidence.get("format") != "PNG":
            errors.append(f"motion_drawing_png_invalid:{panel_id}:{reason}")
            continue
        if annotation_source == "model_generated":
            # An annotated reference can include notes or unequal detail panels.
            # The movie output ratio is not a literal-frame rule for this input.
            if "frame_rect" in binding and _pixel_rect(binding["frame_rect"], width=evidence["width"], height=evidence["height"]) is None:
                errors.append(f"motion_drawing_frame_rect_invalid:{panel_id}")
        elif source_ratio is not None and abs(evidence["width"] / evidence["height"] - source_ratio) > 0.02:
            frame_rect = _pixel_rect(binding.get("frame_rect"), width=evidence["width"], height=evidence["height"])
            if frame_rect is None or abs((frame_rect[2] - frame_rect[0]) / (frame_rect[3] - frame_rect[1]) - source_ratio) > 0.02:
                errors.append(f"motion_drawing_aspect_ratio_mismatch:{panel_id}")
        action_images.setdefault((str(panel.get("requirement_id")), binding["sha256"]), set()).add(str(panel.get("phase")))
        annotations = panel.get("motion_annotations")
        if not isinstance(annotations, list) or not annotations:
            missing.append(f"motion_annotations:{panel_id}")
            continue
        has_camera = False
        for index, annotation in enumerate(annotations):
            if not isinstance(annotation, dict):
                errors.append(f"motion_annotation_invalid:{panel_id}:{index}")
                continue
            kind = annotation.get("kind")
            fixed = kind == "camera" and annotation.get("stationary") is True
            points = annotation.get("points")
            valid_points = (points is None or points == []) if fixed else (
                isinstance(points, list) and 2 <= len(points) <= 12
                and all(_normalized_point(point) for point in points) and len({tuple(point) for point in points}) > 1
            )
            if annotation_source == "model_generated":
                if kind not in MODEL_ANNOTATION_KINDS or not nonempty_text(annotation.get("subject")) or not nonempty_text(annotation.get("label")) or len(str(annotation.get("label"))) > 120 or (points is not None and points != [] and not valid_points) or ("label_position" in annotation and not _normalized_point(annotation["label_position"])) or (annotation.get("stationary") is True and not fixed):
                    errors.append(f"motion_annotation_invalid:{panel_id}:{index}")
                elif isinstance(kind, str):
                    model_annotation_kinds.add(kind)
                continue
            if kind not in ("actor_path", "action", "camera") or not nonempty_text(annotation.get("subject")) or not nonempty_text(annotation.get("label")) or len(str(annotation.get("label"))) > 120 or not valid_points or (
                "label_position" in annotation and not _normalized_point(annotation["label_position"])
            ) or (annotation.get("stationary") is True and not fixed):
                errors.append(f"motion_annotation_invalid:{panel_id}:{index}")
            has_camera = has_camera or kind == "camera"
        if annotation_source != "model_generated" and not has_camera:
            missing.append(f"motion_camera_annotation:{panel_id}")
    for (requirement_id, image_hash), phases in action_images.items():
        if len(phases) > 1:
            errors.append(f"motion_phase_image_reuse:{requirement_id}:{image_hash}")
    errors.extend(_model_legend_errors(plan, model_annotation_kinds))
    input_hash = motion_inputs_sha256(plan, selected)
    if require_review:
        planning = plan.get("motion_planning")
        if not isinstance(planning, dict):
            planning = {}
        if not nonempty_text(planning.get("reason")):
            missing.append("motion_planning_reason")
        covered: set[str] = set()
        boards = planning.get("boards", [])
        if not isinstance(boards, list):
            errors.append("motion_boards_invalid")
            boards = []
        for index, board in enumerate(boards):
            if not isinstance(board, dict):
                errors.append(f"motion_board_invalid:{index}")
                continue
            ids = board.get("panel_ids")
            if not isinstance(ids, list) or not ids or not all(is_id(value) and value in panels for value in ids) or duplicate(ids):
                errors.append(f"motion_board_panels_invalid:{index}")
                continue
            image_path = _bound_planning_file(project_root, board.get("image"))
            receipt_path = _bound_planning_file(project_root, board.get("receipt"))
            if image_path is None or receipt_path is None:
                errors.append(f"motion_board_binding_invalid:{index}")
                continue
            raster, _reason = inspect_raster(image_path)
            if raster is None or raster.get("format") != "PNG":
                errors.append(f"motion_board_png_invalid:{index}")
                continue
            try:
                receipt = load_json_object(receipt_path)
            except (OSError, ValueError, UnicodeDecodeError):
                errors.append(f"motion_board_receipt_invalid:{index}")
                continue
            annotation_source = board.get("annotation_source", "manual_overlay")
            if annotation_source not in ANNOTATION_SOURCES:
                errors.append(f"motion_board_annotation_source_invalid:{index}")
                continue
            if annotation_source == "model_generated":
                if board.get("acquisition", "native_generate") == "assembled_model_panels":
                    valid = _model_annotation_layout_matches(receipt, plan=plan, ids=ids, raster=raster,
                        project_root=project_root, source_path=image_path)
                elif board.get("acquisition", "native_generate") == "native_generate":
                    valid = _model_generated_board_matches(
                        receipt, plan=plan, ids=ids, raster=raster,
                        project_root=project_root, receipt_path=receipt_path, source_path=image_path,
                    )
                else:
                    valid = False
            else:
                valid = receipt.get("status") == "assembled" and receipt.get("motion_inputs_sha256") == motion_inputs_sha256(plan, ids) and receipt.get("panel_ids") == ids and receipt.get("output_sha256") == board["image"]["sha256"] and _motion_receipt_matches(receipt, plan, ids, raster)
            if not valid:
                errors.append(f"motion_board_receipt_mismatch:{index}")
                continue
            covered.update(ids)
        missing.extend(f"motion_board:{panel_id}" for panel_id in selected if panel_id not in covered)
        review = planning.get("review", {})
        if not isinstance(review, dict) or review.get("status") != "reviewed":
            missing.append("motion_visual_review")
        elif review.get("kind") not in ("ai", "human") or review.get("inputs_sha256") != motion_review_sha256(plan) or _bound_planning_file(project_root, review) is None:
            errors.append("motion_review_binding_invalid")
    return {"status": "invalid" if errors else "partial" if missing else "valid", "errors": errors,
            "missing": missing, "required": True, "panel_ids": selected,
            "motion_inputs_sha256": input_hash, "visual_quality": "unverified"}


def validate(
    plan: Any, project_root: Path, phase: str, *, production_image_exempt_shot_ids: set[str] | None = None
) -> dict[str, Any]:
    errors: list[str] = []
    production_image_exempt_shot_ids = production_image_exempt_shot_ids or set()
    missing_images: list[str] = []
    if not isinstance(plan, dict):
        return report("invalid", ["sidecar_json_object_required"], [], {}, 0, 0)
    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    if not nonempty_text(plan.get("project_id")):
        errors.append("project_id_invalid")
    frame_rate = finite_number(plan.get("frame_rate_fps"))
    if frame_rate is None or frame_rate <= 0:
        errors.append("frame_rate_fps_invalid")
    scope = plan.get("scope")
    if not isinstance(scope, str) or scope not in SCOPES:
        errors.append("scope_invalid")
    shots, shot_order, source_errors = source_shots(project_root, plan.get("shot_cards_file"), plan.get("shot_cards_sha256"))
    errors.extend(source_errors)
    expected_ratio = ratio_value(plan.get("aspect_ratio"))
    if plan.get("aspect_ratio") is not None and expected_ratio is None:
        errors.append("aspect_ratio_invalid")
    if expected_ratio is None:
        expected_ratio = ratio_value(source_aspect_ratio(project_root, plan.get("shot_cards_file")))
    raw_requirements = plan.get("requirements")
    requirements: dict[str, dict[str, Any]] = {}
    required_pairs: set[tuple[str, str]] = set()
    if not isinstance(raw_requirements, list):
        errors.append("requirements_invalid")
        raw_requirements = []
    for item in raw_requirements:
        if not isinstance(item, dict) or not is_id(item.get("requirement_id")):
            errors.append("requirement_identity_invalid")
            continue
        requirement_id = item["requirement_id"]
        if requirement_id in requirements:
            errors.append(f"requirement_duplicate:{requirement_id}")
            continue
        shot_ids = item.get("shot_ids")
        phases = item.get("phases")
        valid_shots = isinstance(shot_ids, list) and bool(shot_ids) and all(is_id(value) and value in shots for value in shot_ids) and not duplicate(shot_ids)
        valid_phases = isinstance(phases, list) and bool(phases) and all(nonempty_text(value) for value in phases) and not duplicate(phases)
        kind, risk = item.get("kind"), item.get("risk")
        if not nonempty_text(item.get("source_anchor")) or not isinstance(kind, str) or kind not in KINDS or not isinstance(risk, str) or risk not in RISKS or not isinstance(item.get("image_required"), bool) or not valid_shots or not valid_phases:
            errors.append(f"requirement_fields_invalid:{requirement_id}")
            continue
        if item["risk"] == "high" and not item["image_required"]:
            errors.append(f"high_risk_requirement_needs_image:{requirement_id}")
        requirements[requirement_id] = item
        required_pairs.update((requirement_id, item_phase) for item_phase in phases)
    raw_panels = plan.get("panels")
    planning_rasters = []
    if isinstance(raw_panels, list):
        bindings = [panel.get("planning_image") for panel in raw_panels if isinstance(panel, dict)]
        motion = plan.get("motion_planning")
        if isinstance(motion, dict) and isinstance(motion.get("boards"), list):
            bindings.extend(board.get("image") for board in motion["boards"] if isinstance(board, dict))
        for binding in bindings:
            path = _bound_planning_file(project_root, binding)
            if path is not None:
                evidence, _reason = inspect_raster(path)
                if evidence:
                    planning_rasters.append(evidence)
    panels: dict[str, dict[str, Any]] = {}
    covered_pairs: set[tuple[str, str]] = set()
    shot_panels: set[str] = set()
    panel_order: list[tuple[int, float, str]] = []
    hash_states: dict[tuple[str, str], set[str]] = {}
    action_phase_hashes: dict[tuple[str, str], set[str]] = {}
    available_shots: set[str] = set()
    if not isinstance(raw_panels, list):
        errors.append("panels_invalid")
        raw_panels = []
    for item in raw_panels:
        if not isinstance(item, dict) or not is_id(item.get("panel_id")):
            errors.append("panel_identity_invalid")
            continue
        panel_id = item["panel_id"]
        if panel_id in panels:
            errors.append(f"panel_duplicate:{panel_id}")
            continue
        panels[panel_id] = item
        shot_id, requirement_id, item_phase = item.get("shot_id"), item.get("requirement_id"), item.get("phase")
        at_seconds = finite_number(item.get("at_seconds"))
        required_text_fields = ("state", "camera_setup", "view_subject", "gaze_target", "axis_id", "axis_side")
        look_direction = item.get("look_direction")
        if not is_id(shot_id) or shot_id not in shots or not is_id(requirement_id) or requirement_id not in requirements or not nonempty_text(item_phase) or at_seconds is None or any(not nonempty_text(item.get(field)) for field in required_text_fields) or not isinstance(look_direction, str) or look_direction not in LOOKS:
            errors.append(f"panel_fields_invalid:{panel_id}")
            continue
        requirement = requirements[requirement_id]
        if shot_id not in requirement["shot_ids"] or item_phase not in requirement["phases"]:
            errors.append(f"panel_requirement_binding_invalid:{panel_id}")
        start, end = shots[shot_id]
        if at_seconds < start or at_seconds > end:
            errors.append(f"panel_time_outside_shot:{panel_id}")
        covered_pairs.add((requirement_id, item_phase))
        shot_panels.add(shot_id)
        panel_order.append((shot_order.index(shot_id), at_seconds, panel_id))
        image = item.get("image")
        if not isinstance(image, dict) or not isinstance(image.get("status"), str) or image.get("status") not in IMAGE_STATUSES:
            errors.append(f"panel_image_invalid:{panel_id}")
            continue
        image_status = image["status"]
        if image_status == "planned":
            if image.get("path") is not None or image.get("sha256") is not None:
                errors.append(f"planned_image_must_not_bind_file:{panel_id}")
            if (
                phase == "assets" and requirement["image_required"]
                and shot_id not in production_image_exempt_shot_ids
            ):
                missing_images.append(panel_id)
        else:
            image_path = contained_regular_file(project_root, image.get("path"))
            image_hash = image.get("sha256")
            if image_path is None or not isinstance(image_hash, str) or SHA256_RE.fullmatch(image_hash) is None:
                errors.append(f"available_image_binding_invalid:{panel_id}")
                continue
            evidence, reason = inspect_raster(image_path)
            if evidence is None or evidence.get("format") != "PNG":
                errors.append(f"available_image_not_valid_png:{panel_id}:{reason or 'unknown'}")
                continue
            if evidence.get("sha256") != image_hash:
                errors.append(f"available_image_sha256_mismatch:{panel_id}")
                continue
            if any(evidence["sha256"] == planning["sha256"] or evidence["pixel_sha256"] == planning["pixel_sha256"] for planning in planning_rasters):
                errors.append(f"planning_image_cannot_count_as_production:{panel_id}")
                continue
            if expected_ratio is not None and abs(evidence["width"] / evidence["height"] - expected_ratio) > 0.02:
                errors.append(f"available_image_aspect_ratio_mismatch:{panel_id}")
            else:
                available_shots.add(shot_id)
            hash_states.setdefault((shot_id, image_hash), set()).add(item["state"])
            if requirement["kind"] == "action":
                action_phase_hashes.setdefault((requirement_id, image_hash), set()).add(
                    item_phase
                )
    if panel_order != sorted(panel_order):
        errors.append("panels_not_in_source_time_order")
    for requirement_id, item_phase in sorted(required_pairs - covered_pairs):
        errors.append(f"missing_requirement_phase_panel:{requirement_id}:{item_phase}")
    if scope == "whole_film":
        for shot_id in shot_order:
            if shot_id not in shot_panels:
                errors.append(f"missing_whole_film_shot_panel:{shot_id}")
            if (
                phase == "assets" and shot_id not in available_shots
                and shot_id not in production_image_exempt_shot_ids
            ):
                missing_images.append(f"primary:{shot_id}")
    for (shot_id, image_hash), states in hash_states.items():
        if len(states) > 1:
            errors.append(f"same_image_hash_multiple_states:{shot_id}:{image_hash}")
    for (requirement_id, image_hash), phases in action_phase_hashes.items():
        if len(phases) > 1:
            errors.append(
                f"action_requirement_phase_image_reuse:{requirement_id}:{image_hash}"
            )
    validate_eyeline_pairs(plan.get("eyeline_pairs"), panels, errors)
    planning = validate_motion_planning(plan, project_root, require_review=phase != "design") if not errors else None
    if planning is not None:
        errors.extend(planning["errors"])
    planning_missing = planning["missing"] if planning is not None and phase != "design" else []
    status = "invalid" if errors else "partial" if missing_images or planning_missing else "valid"
    result = report(status, errors, sorted(missing_images), {"source_shots": len(shots), "covered_shots": len(shot_panels), "requirements": len(requirements), "panels": len(panels), "declared_requirement_phases": len(required_pairs), "covered_requirement_phases": len(covered_pairs)}, len(shots), len(shot_panels))
    result["motion_planning"] = planning
    result["missing_planning"] = planning_missing
    return result


def validate_with_legacy(plan: Any, project_root: Path, phase: str, legacy_plan: Path | str) -> dict[str, Any]:
    design_result = validate(plan, project_root, "design")
    active_result = validate(plan, project_root, phase) if phase != "design" else design_result
    errors = list(dict.fromkeys(design_result["errors"] + active_result["errors"]))
    legacy_metrics: dict[str, Any] = {}
    legacy_path = contained_input_file(project_root, legacy_plan)
    if legacy_path is None:
        errors.append("legacy_plan_file_invalid_or_outside_project_root")
    else:
        try:
            legacy_payload = load_json_object(legacy_path)
            legacy_errors, legacy_metrics = validate_legacy_plan(legacy_payload, base_dir=project_root)
            errors.extend(legacy_errors)
            errors.extend(legacy_binding_errors(plan, legacy_payload, project_root))
        except (OSError, ValueError, TypeError, OverflowError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"legacy_plan_invalid:{type(exc).__name__}")
    errors = list(dict.fromkeys(errors))
    result = dict(active_result)
    result["errors"] = errors
    result["status"] = "invalid" if errors else "partial" if result["missing_images"] or result.get("missing_planning") else "valid"
    result["legacy"] = {
        "completion_claim": legacy_metrics.get("completion_claim"),
        "whole_film_visual_assets_complete": legacy_metrics.get("whole_film_visual_assets_complete"),
    }
    return result


def legacy_binding_errors(sidecar: Any, legacy: dict[str, Any], project_root: Path) -> list[str]:
    if not isinstance(sidecar, dict):
        return ["legacy_sidecar_not_object"]
    errors: list[str] = []
    if sidecar.get("project_id") != legacy.get("project_id"):
        errors.append("legacy_project_id_mismatch")
    scope = sidecar.get("scope")
    if scope != legacy.get("scope"):
        errors.append("legacy_scope_mismatch")
    if sidecar.get("shot_cards_sha256") != legacy.get("shot_cards_sha256"):
        errors.append("legacy_shot_cards_sha256_mismatch")
    sidecar_cards = contained_regular_file(project_root, sidecar.get("shot_cards_file"))
    legacy_cards = contained_regular_file(project_root, legacy.get("shot_cards_file"))
    if sidecar_cards is None or legacy_cards is None or sidecar_cards != legacy_cards:
        errors.append("legacy_shot_cards_file_mismatch")
    shots, _, _ = source_shots(project_root, sidecar.get("shot_cards_file"), sidecar.get("shot_cards_sha256"))
    legacy_shot_ids = legacy.get("shot_ids")
    if not isinstance(legacy_shot_ids, list) or not all(is_id(shot_id) for shot_id in legacy_shot_ids):
        errors.append("legacy_shot_coverage_incompatible")
        return errors
    if scope == "whole_film":
        expected_shots = set(shots)
        compatible = set(legacy_shot_ids) == expected_shots
    else:
        expected_shots: set[str] = set()
        raw_requirements = sidecar.get("requirements")
        if isinstance(raw_requirements, list):
            for requirement in raw_requirements:
                if isinstance(requirement, dict) and isinstance(requirement.get("shot_ids"), list):
                    expected_shots.update(shot_id for shot_id in requirement["shot_ids"] if is_id(shot_id))
        compatible = expected_shots.issubset(set(legacy_shot_ids))
    if not compatible:
        errors.append("legacy_shot_coverage_incompatible")
    return errors


def resolve_planning_image_target(
    motion_planning: Any, *, visual_plan_binding: dict[str, Any], project_root: Path,
) -> dict[str, Any]:
    """Derive a coverage-owned drawing target; never add it to the canonical plan.

    Design/compile resolution grants no media authorization. The execution gate
    separately checks the original request before using the returned target.
    """
    if (
        not isinstance(motion_planning, dict)
        or set(motion_planning) != {"target", "scope_asset_id", "coverage_file", "coverage_sha256", "panel_ids"}
        or motion_planning.get("target") != "coverage.planning_image"
        or not is_id(motion_planning.get("scope_asset_id"))
        or not isinstance(visual_plan_binding, dict)
        or set(visual_plan_binding) != {"relative_path", "sha256"}
    ):
        raise ValueError("planning_target_binding_invalid")

    def read(relative: Any, expected_hash: Any) -> dict[str, Any]:
        data = read_relative_regular_file_once(
            project_root, relative, max_bytes=MAX_JSON_BYTES, label="planning target source",
        )
        if not isinstance(expected_hash, str) or hashlib.sha256(data).hexdigest() != expected_hash:
            raise ValueError("planning_target_source_hash_mismatch")
        value = json.loads(data.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("planning_target_source_not_object")
        return value

    plan = read(visual_plan_binding["relative_path"], visual_plan_binding["sha256"])
    plan_dir = (project_root / visual_plan_binding["relative_path"]).parent
    if validate_legacy_plan(copy.deepcopy(plan), base_dir=plan_dir)[0]:
        raise ValueError("planning_target_visual_plan_invalid")
    coverage = read(motion_planning["coverage_file"], motion_planning["coverage_sha256"])
    if validate(coverage, project_root, "design").get("status") != "valid":
        raise ValueError("planning_target_coverage_design_invalid")
    if (
        coverage.get("project_id") != plan.get("project_id")
        or coverage.get("scope") != plan.get("scope")
        or coverage.get("shot_cards_sha256") != plan.get("shot_cards_sha256")
        or contained_regular_file(project_root, coverage.get("shot_cards_file"))
        != contained_regular_file(plan_dir, plan.get("shot_cards_file"))
    ):
        raise ValueError("planning_target_source_mismatch")
    assets = {asset["asset_id"]: asset for asset in plan["assets"]}
    anchor = assets.get(motion_planning["scope_asset_id"])
    if not isinstance(anchor, dict) or anchor.get("role") != "professional_storyboard_motion_map":
        raise ValueError("planning_target_scope_asset_invalid")
    requested = motion_planning["panel_ids"]
    if not isinstance(requested, list) or not requested or not all(is_id(item) for item in requested) or duplicate(requested):
        raise ValueError("planning_target_panel_ids_invalid")
    requested_set = set(requested)
    panels = [panel for panel in coverage["panels"] if panel["panel_id"] in requested_set]
    shot_ids = list(dict.fromkeys(panel["shot_id"] for panel in panels))
    if (
        requested != [panel["panel_id"] for panel in panels]
        or not set(shot_ids).issubset(set(plan["shot_ids"]))
        or not set(shot_ids).intersection(anchor["coverage"]["shot_ids"])
    ):
        raise ValueError("planning_target_panel_scope_mismatch")
    # Presentation pages are not semantic scope boundaries. A selected action can
    # cross pages; the whole bound plan/cards/coverage remains authoritative.
    truths = {item["shot_id"]: item for item in plan["shot_truth"]}
    target_coverage = {field: list(dict.fromkeys(
        value for shot_id in shot_ids for value in truths[shot_id].get(field, [])
    )) for field in ("character_ids", "appearance_state_ids", "product_ids", "prop_ids")}
    target_coverage.update(
        shot_ids=shot_ids,
        scene_ids=list(dict.fromkeys(truths[item]["scene_id"] for item in shot_ids)),
        generation_unit_ids=list(dict.fromkeys(truths[item]["generation_unit_id"] for item in shot_ids)),
    )
    parents: list[str] = []
    units_by_id = {unit["unit_id"]: unit for unit in plan["generation_units"]}
    for shot_id in shot_ids:
        owners = [asset for asset in plan["assets"] if shot_id in asset["coverage"]["shot_ids"] and (
            asset["role"] == "storyboard_frame"
            or (asset["role"] == "professional_storyboard_motion_map"
                and units_by_id[truths[shot_id]["generation_unit_id"]].get("storyboard_strategy") == "annotated_reference")
        )]
        if not owners:
            raise ValueError("planning_target_shot_owner_missing")
        for owner in owners:
            parents.extend(item for item in owner["inherits_from"] if item not in parents)
    truth_sha = json_hash({
        "visual_plan": visual_plan_binding, "motion_planning": motion_planning,
        "scope_asset_truth_sha256": anchor["truth_sha256"],
        "shot_cards_sha256": plan["shot_cards_sha256"], "panels": panels,
    })
    purpose = "Draw annotated motion-planning panels " + ", ".join(requested) + "."
    target = {
        "asset_id": "motion-planning-" + truth_sha,
        "role": "professional_storyboard_motion_map", "truth_sha256": truth_sha,
        "purpose": purpose, "purpose_sha256": hashlib.sha256(purpose.encode()).hexdigest(),
        "visual_plan_sha256": visual_plan_binding["sha256"], "operation": "styleboard",
        "action": "generate", "compile_route": "selected_skill_handoff",
        "planning_only": True, "direct_video_input": False, "status": "planned",
        "coverage": target_coverage, "inherits_from": parents,
    }
    if target["asset_id"] in assets:
        raise ValueError("planning_target_must_not_be_canonical_asset")
    return {
        "asset": target, "panels": copy.deepcopy(panels),
        "dependencies": [{"asset_id": item, "status": assets[item]["status"]} for item in parents],
        "motion_planning": copy.deepcopy(motion_planning), "visual_plan": copy.deepcopy(visual_plan_binding),
    }


def planning_image_spec_errors(spec: Any, panels: list[dict[str, Any]]) -> list[str]:
    """Check native drawing duties against the selected source panels."""
    board = spec.get("styleboard") if isinstance(spec, dict) else None
    if (
        not isinstance(spec, dict) or spec.get("mode") != "styleboard"
        or not isinstance(board, dict) or board.get("presentation") not in {"line_art", "hand_drawn"}
        or board.get("generation_strategy") not in {"sheet_direct", "hybrid"}
    ):
        return ["motion_planning_spec_not_drawing"]
    frames = board.get("frames")
    if (
        not isinstance(frames, list) or len(frames) != len(panels)
        or board.get("frame_count") != len(panels)
        or any(not isinstance(frame, dict) for frame in frames)
    ):
        return ["motion_planning_spec_panel_mismatch"]
    for frame, panel in zip(frames, panels):
        if (
            frame.get("id") != panel["panel_id"]
            or frame.get("story_moment") != panel["state"]
            # A custom phase stays in coverage; its exact state carries meaning.
            or (panel["phase"] in {"prepare", "initiate", "contact", "response", "hold"}
                and frame.get("action_phase") != panel["phase"])
        ):
            return ["motion_planning_spec_panel_mismatch"]
    return []


def validate_eyeline_pairs(raw_pairs: Any, panels: dict[str, dict[str, Any]], errors: list[str]) -> None:
    if raw_pairs is None:
        return
    if not isinstance(raw_pairs, list):
        errors.append("eyeline_pairs_invalid")
        return
    for index, item in enumerate(raw_pairs):
        if not isinstance(item, dict) or not is_id(item.get("panel_a")) or not is_id(item.get("panel_b")):
            errors.append(f"eyeline_pair_invalid:{index}")
            continue
        first, second = panels.get(item["panel_a"]), panels.get(item["panel_b"])
        if first is None or second is None or first is second:
            errors.append(f"eyeline_pair_unknown_panel:{index}")
            continue
        if first.get("shot_id") == second.get("shot_id") or first.get("camera_setup") == second.get("camera_setup"):
            errors.append(f"eyeline_pair_not_reverse_shots:{index}")
        if first.get("view_subject") != second.get("gaze_target") or first.get("gaze_target") != second.get("view_subject"):
            errors.append(f"eyeline_pair_not_reciprocal:{index}")
        first_look, second_look = first.get("look_direction"), second.get("look_direction")
        if not isinstance(first_look, str) or not isinstance(second_look, str) or {first_look, second_look} != {"left", "right"}:
            errors.append(f"eyeline_pair_look_direction_invalid:{index}")
        if first.get("axis_id") != second.get("axis_id"):
            errors.append(f"eyeline_pair_axis_id_mismatch:{index}")
        if first.get("axis_side") != second.get("axis_side") and not nonempty_text(item.get("axis_break_reason")):
            errors.append(f"eyeline_pair_axis_side_mismatch:{index}")


def report(status: str, errors: list[str], missing_images: list[str], coverage: dict[str, int], source_shots: int, covered_shots: int) -> dict[str, Any]:
    return {"status": status, "errors": errors, "missing_images": missing_images, "coverage": coverage or {"source_shots": source_shots, "covered_shots": covered_shots}, "visual_quality": "unverified"}


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--describe-input":
        print(json.dumps(describe_input(), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "resolve-planning-target":
        parser = argparse.ArgumentParser(
            description="Resolve a coverage-owned motion drawing target without generating or changing plans.",
            epilog="For the coverage input shape and allowed values, run --describe-input.",
        )
        parser.add_argument("resolve-planning-target")
        parser.add_argument("coverage", type=Path)
        parser.add_argument("--project-root", type=Path, required=True)
        parser.add_argument("--visual-plan", type=Path, required=True)
        parser.add_argument("--scope-asset", required=True)
        parser.add_argument("--panel-ids", nargs="+", required=True)
        args = parser.parse_args()
        try:
            root = args.project_root.resolve(strict=True)
            plan_path = contained_input_file(root, args.visual_plan)
            coverage_path = contained_input_file(root, args.coverage)
            if plan_path is None or coverage_path is None:
                raise ValueError("planning_target_source_outside_project")
            def binding(path: Path) -> dict[str, str]:
                relative = path.relative_to(root).as_posix()
                data = read_relative_regular_file_once(root, relative, max_bytes=MAX_JSON_BYTES, label="planning target CLI source")
                return {"relative_path": relative, "sha256": hashlib.sha256(data).hexdigest()}
            coverage_binding = binding(coverage_path)
            motion = {"target": "coverage.planning_image", "scope_asset_id": args.scope_asset,
                      "coverage_file": coverage_binding["relative_path"], "coverage_sha256": coverage_binding["sha256"],
                      "panel_ids": args.panel_ids}
            result = {"status": "ready", **resolve_planning_image_target(motion, visual_plan_binding=binding(plan_path), project_root=root)}
        except (OSError, ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
            result = {"status": "blocked", "errors": [str(exc)]}
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["status"] == "ready" else 1
    parser = argparse.ArgumentParser(
        description="Validate DIRcreative explicit storyboard panel coverage.",
        epilog="For the coverage input shape and allowed values, run --describe-input.",
    )
    parser.add_argument("validate", nargs="?", help="required command")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--phase", choices=("design", "planning", "assets"), required=True)
    parser.add_argument("--legacy-plan", type=Path, help="Optional legacy visual asset plan under --project-root.")
    args = parser.parse_args()
    if args.validate != "validate":
        parser.error(
            "usage: validate PLAN --project-root ROOT --phase design|planning|assets; "
            "run --describe-input for the editable input shape and allowed values"
        )
    try:
        root = args.project_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("project root is not a directory")
        plan_path = args.plan.resolve(strict=True)
        plan_path.relative_to(root)
        plan = load_json_object(plan_path)
        result = validate_with_legacy(plan, root, args.phase, args.legacy_plan) if args.legacy_plan else validate(plan, root, args.phase)
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result = report("invalid", [f"input_invalid:{exc}"], [], {}, 0, 0)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "valid" or (args.phase != "planning" and result["status"] == "partial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
