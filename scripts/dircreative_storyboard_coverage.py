#!/usr/bin/env python3
"""Validate explicit, panel-level storyboard coverage without changing asset plans.

This sidecar deliberately treats technical shots, within-shot panels, clean inputs,
and generation units as separate concepts.  It only validates declared coverage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from dircreative_visual_asset_plan import inspect_raster, validate_plan as validate_legacy_plan


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
MAX_JSON_BYTES = 16 * 1024 * 1024


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


def validate(plan: Any, project_root: Path, phase: str) -> dict[str, Any]:
    errors: list[str] = []
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
    if not isinstance(scope, str) or scope not in {"whole_film", "sequence"}:
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
    panels: dict[str, dict[str, Any]] = {}
    covered_pairs: set[tuple[str, str]] = set()
    shot_panels: set[str] = set()
    panel_order: list[tuple[int, float, str]] = []
    hash_states: dict[tuple[str, str], set[str]] = {}
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
            if phase == "assets" and requirement["image_required"]:
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
            if expected_ratio is not None and abs(evidence["width"] / evidence["height"] - expected_ratio) > 0.02:
                errors.append(f"available_image_aspect_ratio_mismatch:{panel_id}")
            else:
                available_shots.add(shot_id)
            hash_states.setdefault((shot_id, image_hash), set()).add(item["state"])
    if panel_order != sorted(panel_order):
        errors.append("panels_not_in_source_time_order")
    for requirement_id, item_phase in sorted(required_pairs - covered_pairs):
        errors.append(f"missing_requirement_phase_panel:{requirement_id}:{item_phase}")
    if scope == "whole_film":
        for shot_id in shot_order:
            if shot_id not in shot_panels:
                errors.append(f"missing_whole_film_shot_panel:{shot_id}")
            if phase == "assets" and shot_id not in available_shots:
                missing_images.append(f"primary:{shot_id}")
    for (shot_id, image_hash), states in hash_states.items():
        if len(states) > 1:
            errors.append(f"same_image_hash_multiple_states:{shot_id}:{image_hash}")
    validate_eyeline_pairs(plan.get("eyeline_pairs"), panels, errors)
    status = "invalid" if errors else "partial" if missing_images else "valid"
    return report(status, errors, sorted(missing_images), {"source_shots": len(shots), "covered_shots": len(shot_panels), "requirements": len(requirements), "panels": len(panels), "declared_requirement_phases": len(required_pairs), "covered_requirement_phases": len(covered_pairs)}, len(shots), len(shot_panels))


def validate_with_legacy(plan: Any, project_root: Path, phase: str, legacy_plan: Path | str) -> dict[str, Any]:
    design_result = validate(plan, project_root, "design")
    active_result = validate(plan, project_root, phase) if phase == "assets" else design_result
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
    result["status"] = "invalid" if errors else "partial" if result["missing_images"] else "valid"
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
    parser = argparse.ArgumentParser(description="Validate DIRcreative explicit storyboard panel coverage.")
    parser.add_argument("validate", nargs="?", help="required command")
    parser.add_argument("plan", type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--phase", choices=("design", "assets"), required=True)
    parser.add_argument("--legacy-plan", type=Path, help="Optional legacy visual asset plan under --project-root.")
    args = parser.parse_args()
    if args.validate != "validate":
        parser.error("usage: validate PLAN --project-root ROOT --phase design|assets")
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
    return 0 if result["status"] != "invalid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
