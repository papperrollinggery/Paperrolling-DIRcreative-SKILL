#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from dircreative_visual_asset_plan import (
    GENERATED_STATUSES,
    TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED,
    load_json,
    validate_plan,
    contained_file,
    inspect_raster,
)
from dircreative_character_master_visual_gate import (
    load_character_master_receipt,
    load_headless_review_authorization,
)
from dircreative_storyboard_coverage import (
    contained_regular_file as contained_storyboard_coverage_file,
    legacy_binding_errors,
    load_json_object as load_storyboard_coverage_json,
    validate as validate_storyboard_coverage,
    validate_motion_planning,
)
import dircreative_storyboard_frame_handoff as storyboard_frame_handoff
import dircreative_prompt_compiler as prompt_compiler


ROOT = Path(__file__).resolve().parents[1]
MEDIA_SCOPES = {"prompt_only", "dry_run_fixture", "pre_video_assets"}


def annotated_reference_prompt_ir_errors(
    unit: dict[str, Any],
    board_asset: dict[str, Any],
    prompt_ir: dict[str, Any],
    *,
    prompt_root: Path,
) -> list[str]:
    """Bind one approved generated annotated board to one existing Prompt IR unit."""
    unit_id = str(unit.get("unit_id"))
    errors: list[str] = []
    expected_shots = unit.get("shot_ids")
    if not isinstance(expected_shots, list):
        return [f"annotated_prompt_unit_invalid:{unit_id}"]
    prompt_units = (
        prompt_ir.get("generation_plan", {}).get("units", [])
        if isinstance(prompt_ir, dict) else []
    )
    matching_units = [
        item for item in prompt_units
        if isinstance(item, dict) and item.get("unit_id") == unit_id
    ]
    if len(matching_units) != 1 or matching_units[0].get("shot_ids") != expected_shots:
        errors.append(f"annotated_prompt_unit_coverage_mismatch:{unit_id}")

    expected_file = board_asset.get("generated_file")
    expected_hash = board_asset.get("generated_sha256")
    supplied_assets = (
        prompt_ir.get("intake", {}).get("supplied_assets", [])
        if isinstance(prompt_ir, dict) else []
    )
    candidates = [
        asset for asset in supplied_assets
        if isinstance(asset, dict)
        and asset.get("role") == "storyboard_motion"
        and asset.get("source_kind") == "project_file"
        and asset.get("source_authorization") == "project_owned"
        and asset.get("locked") is True
        and asset.get("source_locator") == expected_file
        and asset.get("source_hash") == expected_hash
    ]
    if len(candidates) != 1:
        errors.append(f"annotated_prompt_asset_binding_invalid:{unit_id}")
        return errors
    candidate = candidates[0]
    board_path = contained_file(expected_file, prompt_root)
    if board_path is None or hashlib.sha256(board_path.read_bytes()).hexdigest() != expected_hash:
        errors.append(f"annotated_prompt_board_bytes_mismatch:{unit_id}")

    references = prompt_ir.get("references", []) if isinstance(prompt_ir, dict) else []
    matched_references = [
        reference for reference in references
        if isinstance(reference, dict) and reference.get("asset_id") == candidate.get("asset_id")
    ]
    if len(matched_references) != 1:
        errors.append(f"annotated_prompt_reference_binding_invalid:{unit_id}")
    else:
        reference = matched_references[0]
        if (
            reference.get("attached_to_run") is not True
            or reference.get("required_for_shot") is not True
            or reference.get("direct_input_policy") != "conditional"
            or not reference.get("anti_misread")
        ):
            errors.append(f"annotated_prompt_reference_policy_invalid:{unit_id}")
    try:
        prompt_compiler.validate_prompt_ir(
            prompt_ir, verify_project_files=True, project_root=prompt_root
        )
    except prompt_compiler.PromptContractError:
        errors.append(f"annotated_prompt_ir_invalid:{unit_id}")
    return errors


def annotated_reference_coverage_errors(
    unit: dict[str, Any], board_asset: dict[str, Any], storyboard_coverage: dict[str, Any]
) -> list[str]:
    """Require the reviewed model board to cover exactly this annotated unit."""
    unit_id = str(unit.get("unit_id"))
    shot_ids = unit.get("shot_ids")
    if not isinstance(shot_ids, list):
        return [f"annotated_storyboard_coverage_invalid:{unit_id}"]
    panels = [
        panel for panel in storyboard_coverage.get("panels", [])
        if isinstance(panel, dict) and panel.get("shot_id") in shot_ids
    ]
    panel_ids = [str(panel.get("panel_id")) for panel in panels]
    if not panels or {str(panel.get("shot_id")) for panel in panels} != set(shot_ids):
        return [f"annotated_storyboard_coverage_unit_incomplete:{unit_id}"]
    boards = (
        storyboard_coverage.get("motion_planning", {}).get("boards", [])
        if isinstance(storyboard_coverage.get("motion_planning"), dict) else []
    )
    matching = [
        board for board in boards
        if isinstance(board, dict)
        and board.get("annotation_source") == "model_generated"
        and board.get("acquisition", "native_generate") == unit.get("storyboard_acquisition", "native_generate")
        and board.get("panel_ids") == panel_ids
        and isinstance(board.get("image"), dict)
        and board["image"].get("path") == board_asset.get("generated_file")
        and board["image"].get("sha256") == board_asset.get("generated_sha256")
    ]
    return [] if len(matching) == 1 else [
        f"annotated_storyboard_coverage_board_mismatch:{unit_id}"
    ]


def annotated_reference_gate_errors(
    plan: dict[str, Any], *, prompt_irs: list[tuple[Path, dict[str, Any]]] | None,
    storyboard_coverage: dict[str, Any] | None = None,
) -> list[str]:
    """Require one current conditional Prompt IR binding for every annotated unit."""
    annotated_units = [
        unit for unit in plan.get("generation_units", [])
        if isinstance(unit, dict)
        and unit.get("storyboard_strategy", "individual_frames") == "annotated_reference"
    ]
    if not annotated_units:
        return []
    if not prompt_irs:
        return ["annotated_prompt_ir_missing"]
    errors: list[str] = []
    for unit in annotated_units:
        unit_id = str(unit.get("unit_id"))
        assembled_panels = unit.get("storyboard_acquisition", "native_generate") == "assembled_model_panels"
        boards = [
            asset for asset in plan.get("assets", [])
            if isinstance(asset, dict)
            and asset.get("role") == "professional_storyboard_motion_map"
            and asset.get("action") == ("assemble" if assembled_panels else "generate")
            and (not assembled_panels or asset.get("compile_route") == "deterministic_assembly")
            and asset.get("coverage", {}).get("generation_unit_ids") == [unit_id]
            and asset.get("coverage", {}).get("shot_ids") == unit.get("shot_ids")
        ]
        if len(boards) != 1:
            errors.append(f"annotated_storyboard_asset_binding_invalid:{unit_id}")
            continue
        if assembled_panels and storyboard_coverage is None:
            errors.append(f"annotated_layout_coverage_missing:{unit_id}")
            continue
        if storyboard_coverage is not None:
            errors.extend(
                annotated_reference_coverage_errors(unit, boards[0], storyboard_coverage)
            )
        candidate_errors = [
            annotated_reference_prompt_ir_errors(unit, boards[0], payload, prompt_root=path.parent)
            for path, payload in prompt_irs
        ]
        if not any(not item for item in candidate_errors):
            errors.extend(candidate_errors[0] if candidate_errors else [
                f"annotated_prompt_ir_missing:{unit_id}"
            ])
    return list(dict.fromkeys(errors))


def contained_cli_storyboard_coverage_file(root: Path, raw: Path) -> Path | None:
    """Validate raw CLI path components before resolving a coverage sidecar."""
    try:
        root_resolved = root.resolve(strict=True)
    except OSError:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(root_resolved)
        except ValueError:
            return None
    return contained_storyboard_coverage_file(root_resolved, candidate.as_posix())


def action_image_required_panels(storyboard_coverage: Any) -> list[dict[str, Any]]:
    if not isinstance(storyboard_coverage, dict):
        return []
    requirements = {
        item.get("requirement_id"): item
        for item in storyboard_coverage.get("requirements", [])
        if isinstance(item, dict)
        and item.get("kind") == "action"
        and item.get("image_required") is True
    }
    return [
        panel
        for panel in storyboard_coverage.get("panels", [])
        if isinstance(panel, dict)
        and panel.get("requirement_id") in requirements
        and isinstance(panel.get("image"), dict)
        and panel["image"].get("status") == "available"
    ]


DESIGN_PANEL_FIELDS = (
    "panel_id",
    "shot_id",
    "requirement_id",
    "phase",
    "at_seconds",
    "state",
    "camera_setup",
    "view_subject",
    "gaze_target",
    "axis_id",
    "axis_side",
    "look_direction",
)


def storyboard_handoff_errors(
    plan: dict[str, Any],
    *,
    base_dir: Path,
    storyboard_coverage: Any,
    storyboard_frame_handoffs: list[Any] | None,
    provider_root: Path | None,
    host_event_log: Path | None,
    excluded_shot_ids: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    excluded_shot_ids = excluded_shot_ids or set()
    panels = [
        panel for panel in action_image_required_panels(storyboard_coverage)
        if str(panel.get("shot_id")) not in excluded_shot_ids
    ]
    if not panels:
        return [], []
    if not storyboard_frame_handoffs:
        return ["storyboard_frame_handoff_missing"], [str(panel.get("panel_id")) for panel in panels]
    if provider_root is None or host_event_log is None:
        return ["storyboard_frame_handoff_validation_context_missing"], [str(panel.get("panel_id")) for panel in panels]

    errors: list[str] = []
    matching_outputs: dict[str, list[dict[str, Any]]] = {
        str(panel.get("panel_id")): [] for panel in panels
    }
    panel_by_id = {str(panel.get("panel_id")): panel for panel in panels}
    design_cache: dict[tuple[str, str], dict[str, Any] | None] = {}

    def design_for_context(context: Any, handoff_index: int) -> dict[str, Any] | None:
        if not isinstance(context, dict):
            errors.append(f"storyboard_frame_handoff_design_binding_invalid:{handoff_index}")
            return None
        relative_path = context.get("coverage_file")
        expected_hash = context.get("coverage_sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            errors.append(f"storyboard_frame_handoff_design_binding_invalid:{handoff_index}")
            return None
        cache_key = (relative_path, expected_hash)
        if cache_key in design_cache:
            return design_cache[cache_key]
        design_path = contained_storyboard_coverage_file(base_dir, relative_path)
        if design_path is None:
            errors.append(f"storyboard_frame_handoff_design_file_invalid:{handoff_index}")
            design_cache[cache_key] = None
            return None
        try:
            payload = design_path.read_bytes()
            design = load_storyboard_coverage_json(design_path)
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            errors.append(f"storyboard_frame_handoff_design_file_invalid:{handoff_index}")
            design_cache[cache_key] = None
            return None
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            errors.append(f"storyboard_frame_handoff_design_hash_mismatch:{handoff_index}")
            design_cache[cache_key] = None
            return None
        design_result = validate_storyboard_coverage(design, base_dir, "design")
        design_errors = list(design_result.get("errors", [])) + legacy_binding_errors(
            design, plan, base_dir
        )
        if design_errors:
            errors.extend(
                f"storyboard_frame_handoff_design_invalid:{handoff_index}:{error}"
                for error in dict.fromkeys(design_errors)
            )
            design_cache[cache_key] = None
            return None
        design_cache[cache_key] = design
        return design

    def design_matches_assets(
        design: dict[str, Any], panel: dict[str, Any], handoff_index: int
    ) -> bool:
        panel_id = str(panel.get("panel_id"))
        design_panels = [
            item for item in design.get("panels", [])
            if isinstance(item, dict) and item.get("panel_id") == panel_id
        ]
        if len(design_panels) != 1:
            errors.append(f"storyboard_frame_handoff_design_panel_missing:{panel_id}")
            return False
        design_panel = design_panels[0]
        if any(design_panel.get(field) != panel.get(field) for field in DESIGN_PANEL_FIELDS):
            errors.append(f"storyboard_frame_handoff_design_panel_mismatch:{panel_id}")
            return False
        requirement_id = panel.get("requirement_id")
        design_requirements = [
            item for item in design.get("requirements", [])
            if isinstance(item, dict) and item.get("requirement_id") == requirement_id
        ]
        asset_requirements = [
            item for item in storyboard_coverage.get("requirements", [])
            if isinstance(item, dict) and item.get("requirement_id") == requirement_id
        ]
        if (
            len(design_requirements) != 1
            or len(asset_requirements) != 1
            or design_requirements[0] != asset_requirements[0]
        ):
            errors.append(f"storyboard_frame_handoff_design_requirement_mismatch:{panel_id}")
            return False
        return True

    for index, handoff in enumerate(storyboard_frame_handoffs):
        if not isinstance(handoff, dict):
            errors.append(f"storyboard_frame_handoff_invalid:{index}:object_required")
            continue
        if handoff.get("fixture_only") is True:
            errors.append(f"storyboard_frame_handoff_fixture_only:{index}")
            continue
        consumption = handoff.get("delivery_consumption")
        if not isinstance(consumption, dict) or consumption.get("status") != "observed_unverified":
            errors.append(f"storyboard_frame_handoff_not_observed_generation:{index}")
            continue
        validation_errors = storyboard_frame_handoff.validate(
            handoff,
            artifact_root=base_dir,
            provider_root=provider_root,
            host_event_log=host_event_log,
        )
        if validation_errors:
            errors.extend(
                f"storyboard_frame_handoff_invalid:{index}:{error}"
                for error in validation_errors
            )
            continue
        frames = {
            str(frame.get("frame_id")): frame
            for frame in handoff.get("frames", [])
            if isinstance(frame, dict)
        }
        for output in consumption.get("frame_outputs", []):
            if not isinstance(output, dict):
                continue
            panel_id = str(output.get("frame_id"))
            panel = panel_by_id.get(panel_id)
            if panel is None:
                continue
            frame = frames.get(panel_id)
            context = frame.get("panel_context") if isinstance(frame, dict) else None
            design = design_for_context(context, index)
            design_panel = next(
                (
                    item
                    for item in design.get("panels", [])
                    if isinstance(item, dict) and item.get("panel_id") == panel_id
                ),
                None,
            ) if isinstance(design, dict) else None
            image = panel.get("image")
            generated = output.get("generated_artifact")
            if (
                not isinstance(frame, dict)
                or design is None
                or not isinstance(design_panel, dict)
                or not isinstance(context, dict)
                or not design_matches_assets(design, panel, index)
                or frame.get("shot_id") != panel.get("shot_id")
                or any(
                    context.get(field) != design_panel.get(field)
                    for field in ("phase", "at_seconds", "state")
                )
                or context.get("panel_id") != panel_id
            ):
                errors.append(f"storyboard_frame_handoff_panel_binding_mismatch:{panel_id}")
                continue
            if (
                not isinstance(image, dict)
                or not isinstance(generated, dict)
                or generated.get("relative_path") != image.get("path")
                or generated.get("sha256") != image.get("sha256")
            ):
                errors.append(f"storyboard_frame_handoff_output_binding_mismatch:{panel_id}")
                continue
            matching_outputs[panel_id].append(output)

    for panel_id, outputs in matching_outputs.items():
        if not outputs:
            errors.append(f"storyboard_frame_handoff_panel_missing:{panel_id}")
        elif len(outputs) > 1:
            errors.append(f"storyboard_frame_handoff_panel_duplicate:{panel_id}")
    for shot_id in {str(panel.get("shot_id")) for panel in panels}:
        legacy_assets = [
            asset
            for asset in plan.get("assets", [])
            if isinstance(asset, dict)
            and asset.get("role") == "storyboard_frame"
            and isinstance(asset.get("coverage"), dict)
            and shot_id in asset["coverage"].get("shot_ids", [])
        ]
        if len(legacy_assets) != 1:
            errors.append(f"storyboard_representative_asset_binding_invalid:{shot_id}")
            continue
        legacy_asset = legacy_assets[0]
        matching_panels = [
            panel
            for panel in panels
            if str(panel.get("shot_id")) == shot_id
            and panel.get("image", {}).get("path") == legacy_asset.get("generated_file")
        ]
        if legacy_asset.get("status") not in GENERATED_STATUSES or len(matching_panels) != 1:
            errors.append(f"storyboard_representative_asset_binding_invalid:{shot_id}")
    return list(dict.fromkeys(errors)), [
        panel_id for panel_id, outputs in matching_outputs.items() if not outputs
    ]


def evaluate(
    plan: Any,
    *,
    base_dir: Path,
    media_scope: str,
    image_generation_authorized: bool,
    video_generation_authorized: bool,
    storyboard_coverage: Any = None,
    storyboard_frame_handoffs: list[Any] | None = None,
    provider_root: Path | None = None,
    host_event_log: Path | None = None,
    prompt_irs: list[tuple[Path, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    required_assets = [
        asset
        for asset in plan.get("assets", [])
        if isinstance(asset, dict) and asset.get("required") is True
    ] if isinstance(plan, dict) else []
    generated_assets = [
        asset
        for asset in required_assets
        if asset.get("status") in GENERATED_STATUSES
    ]
    missing_asset_ids = [
        str(asset.get("asset_id"))
        for asset in required_assets
        if asset.get("status") not in GENERATED_STATUSES
    ]
    base = {
        "media_scope": media_scope,
        "required_asset_count": len(required_assets),
        "generated_asset_count": len(generated_assets),
        "missing_asset_ids": missing_asset_ids,
        "generated_asset_set_complete": False,
        "visual_assets_complete": False,
        "storyboard_coverage_required": False,
        "storyboard_coverage_status": "not_required",
        "missing_panels": [],
        "missing_motion_planning": [],
        "storyboard_coverage_visual_quality": "unverified",
        "storyboard_handoff_status": "not_required",
        "missing_handoff_panels": [],
        "reason_codes": [],
        "validation_errors": [],
    }
    if media_scope not in MEDIA_SCOPES:
        return {**base, "status": "invalid", "reason_codes": ["media_scope_invalid"]}
    if media_scope in {"prompt_only", "dry_run_fixture"}:
        return {**base, "status": "not_applicable"}
    if image_generation_authorized is not True:
        return {
            **base,
            "status": "invalid",
            "reason_codes": ["pre_video_assets_requires_image_authorization"],
        }
    if video_generation_authorized is not False:
        return {
            **base,
            "status": "invalid",
            "reason_codes": ["pre_video_assets_must_defer_video_generation"],
        }

    structural_errors, _metrics = validate_plan(plan, base_dir=base_dir)
    if structural_errors:
        return {
            **base,
            "status": "invalid",
            "reason_codes": ["visual_asset_plan_invalid"],
            "validation_errors": structural_errors,
        }
    coverage_required = plan.get("scope") in {"whole_film", "sequence"}
    annotated_units = [
        unit for unit in plan.get("generation_units", [])
        if isinstance(unit, dict) and unit.get("storyboard_strategy") == "annotated_reference"
    ]
    annotated_shot_ids = {
        str(shot_id) for unit in annotated_units for shot_id in unit.get("shot_ids", [])
    }
    if coverage_required:
        coverage_base = {
            **base,
            "storyboard_coverage_required": True,
        }
        if storyboard_coverage is None:
            return {
                **coverage_base,
                "status": "blocked",
                "storyboard_coverage_status": "missing",
                "reason_codes": ["storyboard_coverage_required", "storyboard_coverage_missing"],
            }
        coverage_result = validate_storyboard_coverage(
            storyboard_coverage,
            base_dir,
            "assets",
            production_image_exempt_shot_ids=annotated_shot_ids,
        )
        coverage_errors = list(coverage_result.get("errors", []))
        coverage_errors.extend(
            legacy_binding_errors(storyboard_coverage, plan, base_dir)
        )
        coverage_errors = list(dict.fromkeys(coverage_errors))
        missing_panels = list(coverage_result.get("missing_images", []))
        coverage_base.update(
            {
                "storyboard_coverage_status": coverage_result.get("status", "invalid"),
                "missing_panels": missing_panels,
                "missing_motion_planning": list(coverage_result.get("missing_planning", [])),
                "storyboard_coverage_visual_quality": coverage_result.get(
                    "visual_quality", "unverified"
                ),
            }
        )
        if coverage_errors:
            return {
                **coverage_base,
                "status": "blocked",
                "storyboard_coverage_status": "invalid",
                "reason_codes": ["storyboard_coverage_invalid"],
                "validation_errors": coverage_errors,
            }
        if coverage_result.get("status") != "valid":
            return {
                **coverage_base,
                "status": "blocked",
                "reason_codes": ["storyboard_coverage_assets_incomplete"],
                "validation_errors": missing_panels,
            }
        for unit in annotated_units:
            motion_result = validate_motion_planning(
                storyboard_coverage,
                base_dir,
                require_review=True,
                panel_ids=[
                    str(panel.get("panel_id"))
                    for panel in storyboard_coverage.get("panels", [])
                    if isinstance(panel, dict) and panel.get("shot_id") in unit.get("shot_ids", [])
                ],
            )
            if motion_result.get("status") != "valid":
                return {
                    **coverage_base,
                    "status": "blocked",
                    "reason_codes": ["annotated_storyboard_motion_review_invalid"],
                    "validation_errors": list(motion_result.get("errors", []))
                    + list(motion_result.get("missing", [])),
                }
        base = coverage_base
        handoff_errors, missing_handoff_panels = storyboard_handoff_errors(
            plan,
            base_dir=base_dir,
            storyboard_coverage=storyboard_coverage,
            storyboard_frame_handoffs=storyboard_frame_handoffs,
            provider_root=provider_root,
            host_event_log=host_event_log,
            excluded_shot_ids=annotated_shot_ids,
        )
        if action_image_required_panels(storyboard_coverage):
            base = {
                **base,
                "storyboard_handoff_status": "valid" if not handoff_errors else "invalid",
                "missing_handoff_panels": missing_handoff_panels,
            }
        if handoff_errors:
            return {
                **base,
                "status": "blocked",
                "reason_codes": ["storyboard_frame_handoff_invalid"],
                "validation_errors": handoff_errors,
            }
    if missing_asset_ids:
        return {
            **base,
            "status": "blocked",
            "reason_codes": ["pre_video_assets_requires_verified_images"],
        }

    evidence_plan = copy.deepcopy(plan)
    evidence_plan["completion_claim"] = (
        "sample_visual_assets_complete"
        if evidence_plan.get("scope") == "representative_sample"
        else "visual_assets_complete"
    )
    evidence_errors, _metrics = validate_plan(evidence_plan, base_dir=base_dir)
    permitted_non_acceptance_errors = {
        TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED,
        "independent_ai_review_cannot_grant_visual_assets_complete_without_human_or_authorized_review",
    }
    blocking_evidence_errors = [
        error for error in evidence_errors if error not in permitted_non_acceptance_errors
    ]
    if blocking_evidence_errors:
        return {
            **base,
            "status": "blocked",
            "reason_codes": ["generated_asset_evidence_incomplete"],
            "validation_errors": blocking_evidence_errors,
        }
    character_structure_errors: list[str] = []
    for asset in required_assets:
        if asset.get("role") != "character_identity_reference":
            continue
        image_path = contained_file(asset.get("generated_file"), base_dir)
        evidence, _reason = inspect_raster(image_path) if image_path is not None else (None, "missing")
        if evidence is None:
            character_structure_errors.append(str(asset.get("asset_id")))
            continue
        receipt, receipt_errors = load_character_master_receipt(
            asset,
            base_dir=base_dir,
            image_evidence=evidence,
        )
        headless_review_errors: list[str] = []
        if (
            isinstance(receipt, dict)
            and asset.get("character_mode") == "headless_safe"
            and receipt.get("status") == "applied_unverified"
        ):
            _review, headless_review_errors = load_headless_review_authorization(
                asset,
                base_dir=base_dir,
                image_evidence=evidence,
            )
        structure_status_ok = (
            isinstance(receipt, dict)
            and (
                receipt.get("status") == "pass"
                or (
                    asset.get("character_mode") == "headless_safe"
                    and receipt.get("status") == "applied_unverified"
                    and not headless_review_errors
                )
            )
        )
        if receipt_errors or headless_review_errors or not structure_status_ok:
            character_structure_errors.append(str(asset.get("asset_id")))
    if character_structure_errors:
        return {
            **base,
            "status": "blocked",
            "reason_codes": ["character_master_visual_structure_incomplete"],
            "validation_errors": character_structure_errors,
        }
    annotated_prompt_errors = annotated_reference_gate_errors(
        plan, prompt_irs=prompt_irs, storyboard_coverage=storyboard_coverage
    )
    if annotated_prompt_errors:
        return {
            **base,
            "status": "blocked",
            "reason_codes": ["annotated_reference_prompt_ir_invalid"],
            "validation_errors": annotated_prompt_errors,
        }
    return {
        **base,
        "status": "ready_for_user_review",
        "generated_asset_set_complete": True,
        "reason_codes": ["trusted_host_adoption_and_user_lock_pending"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that an authorized pre-video workflow produced real reviewed image assets."
    )
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--media-scope", required=True, choices=sorted(MEDIA_SCOPES))
    parser.add_argument("--image-generation-authorized", action="store_true")
    parser.add_argument("--video-generation-authorized", action="store_true")
    parser.add_argument(
        "--storyboard-coverage",
        type=Path,
        help="Panel-level storyboard coverage sidecar under the visual asset plan directory.",
    )
    parser.add_argument("--storyboard-frame-handoff", action="append", type=Path)
    parser.add_argument("--prompt-ir", action="append", type=Path)
    parser.add_argument("--provider-root", type=Path)
    parser.add_argument("--host-event-log", type=Path)
    args = parser.parse_args()
    try:
        plan_path = args.plan.expanduser().resolve(strict=True)
        plan = load_json(plan_path)
        storyboard_coverage = None
        if args.storyboard_coverage is not None:
            coverage_path = contained_cli_storyboard_coverage_file(
                plan_path.parent,
                args.storyboard_coverage,
            )
            if coverage_path is None:
                result = {
                    "status": "invalid",
                    "reason_codes": [
                        "storyboard_coverage_file_invalid_or_outside_plan_root"
                    ],
                    "validation_errors": [],
                }
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
                return 1
            storyboard_coverage = load_storyboard_coverage_json(coverage_path)
        storyboard_frame_handoffs = []
        for raw_handoff in args.storyboard_frame_handoff or []:
            handoff_path = contained_cli_storyboard_coverage_file(
                plan_path.parent,
                raw_handoff,
            )
            if handoff_path is None:
                result = {
                    "status": "invalid",
                    "reason_codes": [
                        "storyboard_frame_handoff_file_invalid_or_outside_plan_root"
                    ],
                    "validation_errors": [],
                }
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
                return 1
            storyboard_frame_handoffs.append(load_storyboard_coverage_json(handoff_path))
        prompt_irs: list[tuple[Path, dict[str, Any]]] = []
        for raw_prompt_ir in args.prompt_ir or []:
            prompt_path = contained_cli_storyboard_coverage_file(
                plan_path.parent, raw_prompt_ir
            )
            if prompt_path is None:
                result = {
                    "status": "invalid",
                    "reason_codes": ["prompt_ir_file_invalid_or_outside_plan_root"],
                    "validation_errors": [],
                }
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
                return 1
            prompt_irs.append((prompt_path, prompt_compiler.load_prompt_ir(prompt_path)))
        provider_root = (
            args.provider_root.expanduser().resolve(strict=True)
            if args.provider_root is not None
            else None
        )
        host_event_log = (
            args.host_event_log.expanduser().resolve(strict=True)
            if args.host_event_log is not None
            else None
        )
        result = evaluate(
            plan,
            base_dir=plan_path.parent,
            media_scope=args.media_scope,
            image_generation_authorized=args.image_generation_authorized,
            video_generation_authorized=args.video_generation_authorized,
            storyboard_coverage=storyboard_coverage,
            storyboard_frame_handoffs=storyboard_frame_handoffs,
            provider_root=provider_root,
            host_event_log=host_event_log,
            prompt_irs=prompt_irs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        result = {
            "status": "invalid",
            "reason_codes": ["input_unreadable"],
            "validation_errors": [f"{type(exc).__name__}:{exc}"],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] in {"not_applicable", "ready_for_user_review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
