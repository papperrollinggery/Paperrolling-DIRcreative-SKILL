#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from dircreative_validation_common import (
    add_error,
    apply_mutations,
    load_json,
    schema_errors as validate_schema,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/script-to-seedance-handoff.schema.json"
VALID_PATH = ROOT / "tests/fixtures/script-to-seedance/valid-handoff.json"
CASES_PATH = ROOT / "tests/fixtures/script-to-seedance/cases.json"
CONVERTER_SLOT_RE = re.compile(r"^【(图片|音频|视频)([1-9][0-9]*)】$")
PLATFORM_SLOT_RE = re.compile(r"^@(Image|Audio|Video) ([1-9][0-9]*)$")
PROMPT_PLATFORM_SLOT_RE = re.compile(r"@(Image|Audio|Video)\s+([1-9][0-9]*)")
MEDIA_LABELS = {
    "image": ("图片", "Image"),
    "audio": ("音频", "Audio"),
    "video": ("视频", "Video"),
}
PLANNING_SOURCES = {"human_planning_board", "narrative_frame"}
SOURCE_KIND_BY_MEDIA = {
    "image": {
        "identity_reference",
        "scene_anchor",
        "model_layout_reference",
        "human_planning_board",
        "narrative_frame",
        "clean_frame",
    },
    "audio": {"audio_asset"},
    "video": {"video_asset"},
}


def schema_errors(document: dict[str, Any]) -> list[str]:
    return validate_schema(document, SCHEMA_PATH)


def unique_map(
    items: list[dict[str, Any]],
    key: str,
    duplicate_code: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        value = item.get(key)
        if not isinstance(value, str):
            continue
        if value in result:
            add_error(errors, duplicate_code, value)
        result[value] = item
    return result


def seconds(value: str) -> float:
    minutes, seconds_value = value.split(":", 1)
    parsed_seconds = float(seconds_value)
    if parsed_seconds < 0 or parsed_seconds >= 60:
        raise ValueError("seconds component must be between 00 and 59")
    return int(minutes) * 60 + parsed_seconds


def asset_gate_errors(
    document: dict[str, Any],
    *,
    asset_foundation_path: Path | None,
    asset_stress_path: Path | None,
    asset_artifact_root: Path | None,
    asset_review_receipt: Path | None,
    asset_review_signature: Path | None,
    asset_trust_registry_path: Path | None,
) -> list[str]:
    from ai_film_asset_stress_test import validate as validate_stress_report
    from dircreative_asset_foundation_pass import validate as validate_foundation_pass

    errors: list[str] = []
    gate = document.get("asset_foundation_gate", {})
    verdict = gate.get("stress_verdict")
    requested = set(gate.get("requested_shot_ids", []))
    allowed = set(gate.get("allowed_shot_ids", []))
    blocked = set(gate.get("blocked_shot_ids", []))
    shot_ids = {
        str(item.get("shot_id"))
        for item in document.get("shots", [])
        if isinstance(item, dict)
    }
    required_bound_assets = {
        str(item.get("asset_id"))
        for item in document.get("bindings", [])
        if isinstance(item, dict)
        and item.get("media_type") == "image"
        and item.get("status") == "available"
        and item.get("attached_to_run") is True
        and item.get("direct_input_policy") in {"allowed", "conditional"}
    }
    covered_assets = set(gate.get("covered_asset_ids", []))
    if not required_bound_assets.issubset(covered_assets):
        add_error(
            errors,
            "asset_binding_stress_coverage_missing",
            ",".join(sorted(required_bound_assets - covered_assets)),
        )
    if verdict not in {"certified", "conditional"}:
        add_error(errors, "asset_stress_verdict_not_compilable", str(verdict))
    if requested != shot_ids or not requested.issubset(allowed) or bool(requested & blocked):
        add_error(errors, "asset_scope_not_allowed", ",".join(sorted(requested)))
    if asset_foundation_path is None or asset_stress_path is None:
        add_error(errors, "asset_foundation_evidence_required", str(gate.get("pass_id")))
        return errors
    try:
        foundation_bytes = asset_foundation_path.read_bytes()
        stress_bytes = asset_stress_path.read_bytes()
        foundation = json.loads(foundation_bytes.decode("utf-8"))
        stress = json.loads(stress_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        add_error(errors, "asset_foundation_evidence_unreadable", str(gate.get("pass_id")))
        return errors
    if hashlib.sha256(foundation_bytes).hexdigest() != gate.get("pass_artifact_sha256"):
        add_error(errors, "asset_foundation_file_hash_mismatch", str(asset_foundation_path))
    if hashlib.sha256(stress_bytes).hexdigest() != gate.get("stress_report_sha256"):
        add_error(errors, "asset_stress_file_hash_mismatch", str(asset_stress_path))

    foundation_errors = validate_foundation_pass(
        foundation,
        artifact_root=asset_artifact_root,
    )
    if foundation_errors:
        add_error(errors, "asset_foundation_pass_invalid", foundation_errors[0])
    stress_kwargs: dict[str, Any] = {
        "artifact_root": asset_artifact_root,
        "review_receipt_path": asset_review_receipt,
        "review_signature_path": asset_review_signature,
    }
    if asset_trust_registry_path is not None:
        stress_kwargs["_trust_registry_path"] = asset_trust_registry_path
    stress_errors = validate_stress_report(stress, **stress_kwargs)
    if stress_errors:
        add_error(errors, "asset_stress_report_invalid", stress_errors[0])

    stress_binding = foundation.get("stress_test_binding", {}) if isinstance(foundation, dict) else {}
    compile_gate = foundation.get("compile_gate", {}) if isinstance(foundation, dict) else {}
    stress_asset_ids = {
        str(item.get("asset_id"))
        for item in stress.get("assets", [])
        if isinstance(item, dict)
    }
    foundation_sources = {
        str(item.get("asset_id")): item
        for item in foundation.get("source_assets", [])
        if isinstance(item, dict) and item.get("source_kind") == "canonical_asset"
    }
    stress_assets = {
        str(item.get("asset_id")): item
        for item in stress.get("assets", [])
        if isinstance(item, dict)
    }
    for binding in document.get("bindings", []):
        if not isinstance(binding, dict) or str(binding.get("asset_id")) not in required_bound_assets:
            continue
        asset_id = str(binding.get("asset_id"))
        relative = binding.get("relative_path")
        source = foundation_sources.get(asset_id)
        stress_asset = stress_assets.get(asset_id)
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or "\\" in relative
            or any(part in {"", ".", ".."} for part in relative.split("/"))
            or not isinstance(binding.get("asset_version"), str)
            or not isinstance(binding.get("sha256"), str)
        ):
            add_error(errors, "binding_asset_artifact_missing", asset_id)
            continue
        if asset_artifact_root is None:
            add_error(errors, "binding_asset_artifact_root_required", asset_id)
        else:
            try:
                root = asset_artifact_root.resolve(strict=True)
                path = (root / relative).resolve(strict=True)
                path.relative_to(root)
            except (FileNotFoundError, RuntimeError, ValueError):
                add_error(errors, "binding_asset_file_missing", asset_id)
            else:
                if hashlib.sha256(path.read_bytes()).hexdigest() != binding.get("sha256"):
                    add_error(errors, "binding_asset_hash_mismatch", asset_id)
        if (
            source is None
            or stress_asset is None
            or source.get("relative_path") != relative
            or source.get("sha256") != binding.get("sha256")
            or stress_asset.get("canonical_relative_path") != relative
            or stress_asset.get("canonical_sha256") != binding.get("sha256")
            or stress_asset.get("asset_version") != binding.get("asset_version")
        ):
            add_error(errors, "binding_asset_provenance_mismatch", asset_id)
    if (
        document.get("project_id") != gate.get("project_id")
        or foundation.get("project_id") != gate.get("project_id")
        or stress.get("project_id") != gate.get("project_id")
    ):
        add_error(errors, "asset_project_binding_mismatch", str(gate.get("project_id")))
    if (
        foundation.get("pass_id") != gate.get("pass_id")
        or foundation.get("status") != "complete"
        or compile_gate.get("status") != "allowed"
        or set(compile_gate.get("requested_shot_ids", [])) != requested
        or set(foundation.get("canonical_asset_ids", [])) != covered_assets
    ):
        add_error(errors, "asset_foundation_binding_mismatch", str(gate.get("pass_id")))
    if (
        stress.get("stress_test_id") != gate.get("stress_test_id")
        or stress.get("verdict", {}).get("status") != verdict
        or stress_binding.get("stress_test_id") != gate.get("stress_test_id")
        or stress_binding.get("report_sha256") != hashlib.sha256(stress_bytes).hexdigest()
        or stress_binding.get("verdict") != verdict
        or set(stress_binding.get("allowed_shot_scope", [])) != allowed
        or set(stress_binding.get("blocked_shot_scope", [])) != blocked
        or set(stress_binding.get("covered_asset_ids", [])) != covered_assets
        or stress_asset_ids != covered_assets
    ):
        add_error(errors, "asset_stress_binding_mismatch", str(gate.get("stress_test_id")))
    return errors


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = [item for item in document.get("narrative_nodes", []) if isinstance(item, dict)]
    shots = [item for item in document.get("shots", []) if isinstance(item, dict)]
    units = [item for item in document.get("generation_units", []) if isinstance(item, dict)]
    states = [item for item in document.get("continuity_states", []) if isinstance(item, dict)]
    bindings = [item for item in document.get("bindings", []) if isinstance(item, dict)]
    prompt_units = [item for item in document.get("prompt_units", []) if isinstance(item, dict)]
    ownership = [item for item in document.get("entity_ownership", []) if isinstance(item, dict)]

    node_map = unique_map(nodes, "node_id", "narrative_node_duplicate", errors)
    shot_map = unique_map(shots, "shot_id", "shot_id_duplicate", errors)
    unit_map = unique_map(units, "generation_unit_id", "generation_unit_duplicate", errors)
    state_map = unique_map(states, "state_id", "continuity_state_duplicate", errors)
    binding_map = unique_map(bindings, "binding_id", "binding_id_duplicate", errors)
    prompt_map = unique_map(prompt_units, "generation_unit_id", "prompt_unit_duplicate", errors)
    prompt_artifact_map = unique_map(prompt_units, "artifact_id", "prompt_artifact_id_duplicate", errors)
    ownership_map = unique_map(ownership, "entity_id", "entity_ownership_duplicate", errors)

    model_surface = document.get("model_surface", {})
    version = str(model_surface.get("version", "")).casefold()
    capability_card = str(model_surface.get("capability_card_id", "")).casefold()
    if model_surface.get("verification_status") != "verified":
        add_error(errors, "model_surface_unverified", str(model_surface.get("model_key")))
    if any(token in {version, capability_card} for token in {"latest", "family", "preview"}) or any(
        token in version for token in ("latest", "preview", "family-alias")
    ):
        add_error(errors, "model_surface_not_exact", str(model_surface.get("version")))

    node_shot_ids = [
        shot_id
        for node in nodes
        for shot_id in node.get("shot_ids", [])
        if isinstance(shot_id, str)
    ]
    if sorted(node_shot_ids) != sorted(shot_map):
        add_error(errors, "narrative_shot_coverage_invalid", "shots must appear in exactly one node")

    for node in nodes:
        for shot_id in node.get("shot_ids", []):
            shot = shot_map.get(shot_id)
            if shot is None:
                add_error(errors, "narrative_shot_unresolved", f"{node.get('node_id')}->{shot_id}")
            elif shot.get("node_id") != node.get("node_id"):
                add_error(errors, "narrative_shot_owner_mismatch", f"{node.get('node_id')}->{shot_id}")

    for item in ownership:
        entity_id = item.get("entity_id")
        if item.get("owner") == document.get("target_owner"):
            add_error(errors, "entity_owner_is_compiler", str(entity_id))
        for shot_id in item.get("shot_ids", []):
            if shot_id not in shot_map:
                add_error(errors, "entity_ownership_shot_unresolved", f"{entity_id}->{shot_id}")
        for unit_id in item.get("generation_unit_ids", []):
            if unit_id not in unit_map:
                add_error(errors, "entity_ownership_unit_unresolved", f"{entity_id}->{unit_id}")

    shot_entity_ids = {
        str(shot.get("shot_id")): {
            entity_id for entity_id in shot.get("entity_ids", []) if isinstance(entity_id, str)
        }
        for shot in shots
    }
    referenced_entities = set().union(*shot_entity_ids.values()) if shot_entity_ids else set()
    for unit in units:
        referenced_entities.update(unit.get("continuity_in", {}).keys())
        referenced_entities.update(unit.get("continuity_out", {}).keys())

    script = document.get("authoritative_script", {})
    dialogue_lines = [
        line for line in script.get("dialogue_lines", []) if isinstance(line, dict)
    ]
    unique_map(dialogue_lines, "dialogue_line_id", "dialogue_line_id_duplicate", errors)
    for line in dialogue_lines:
        speaker = line.get("speaker_entity_id")
        if isinstance(speaker, str):
            referenced_entities.add(speaker)
        if speaker not in ownership_map:
            add_error(errors, "dialogue_speaker_unowned", str(speaker))
        for shot_id in line.get("shot_ids", []):
            if shot_id not in shot_map:
                add_error(errors, "dialogue_shot_unresolved", f"{speaker}->{shot_id}")

    if set(ownership_map) != referenced_entities:
        add_error(errors, "entity_ownership_coverage_invalid", "ownership must cover all referenced entities")
    for entity_id, item in ownership_map.items():
        expected_shots = {
            shot_id for shot_id, entity_ids in shot_entity_ids.items() if entity_id in entity_ids
        }
        declared_shots = set(item.get("shot_ids", []))
        if declared_shots != expected_shots:
            add_error(errors, "entity_ownership_shot_coverage_invalid", str(entity_id))
        expected_units = {
            str(shot_map[shot_id].get("generation_unit_id"))
            for shot_id in expected_shots
            if shot_id in shot_map
        }
        if set(item.get("generation_unit_ids", [])) != expected_units:
            add_error(errors, "entity_ownership_unit_coverage_invalid", str(entity_id))

    previous_end: float | None = None
    seen_shots_in_units: list[str] = []
    for shot in shots:
        shot_id = shot.get("shot_id")
        if shot.get("node_id") not in node_map:
            add_error(errors, "shot_node_unresolved", str(shot_id))
        if shot.get("generation_unit_id") not in unit_map:
            add_error(errors, "shot_generation_unit_unresolved", str(shot_id))
        try:
            start = seconds(str(shot.get("time_start")))
            end = seconds(str(shot.get("time_end")))
        except (TypeError, ValueError):
            continue
        if end <= start:
            add_error(errors, "shot_time_invalid", str(shot_id))
        if previous_end is not None and abs(start - previous_end) > 0.001:
            add_error(errors, "shot_timeline_gap", f"{shot_id}:{start} after {previous_end}")
        previous_end = end

    for unit in units:
        unit_id = unit.get("generation_unit_id")
        unit_shots = unit.get("shot_ids", [])
        seen_shots_in_units.extend(item for item in unit_shots if isinstance(item, str))
        duration = 0.0
        for shot_id in unit_shots:
            shot = shot_map.get(shot_id)
            if shot is None:
                add_error(errors, "generation_unit_shot_unresolved", f"{unit_id}->{shot_id}")
                continue
            if shot.get("generation_unit_id") != unit_id:
                add_error(errors, "generation_unit_shot_owner_mismatch", f"{unit_id}->{shot_id}")
            duration += seconds(shot["time_end"]) - seconds(shot["time_start"])
        if abs(duration - float(unit.get("duration_seconds", 0))) > 0.01:
            add_error(errors, "generation_unit_duration_mismatch", str(unit_id))

        continuity_in = unit.get("continuity_in", {})
        continuity_out = unit.get("continuity_out", {})
        for entity_id, input_state_id in continuity_in.items():
            output_state_id = continuity_out.get(entity_id)
            input_state = state_map.get(input_state_id)
            output_state = state_map.get(output_state_id)
            if input_state is None or input_state.get("entity_id") != entity_id:
                add_error(errors, "continuity_input_unresolved", f"{unit_id}:{entity_id}:{input_state_id}")
            if output_state is None or output_state.get("entity_id") != entity_id:
                add_error(errors, "continuity_output_unresolved", f"{unit_id}:{entity_id}:{output_state_id}")
                continue
            if output_state_id != input_state_id and input_state_id not in output_state.get("allowed_predecessors", []):
                add_error(errors, "continuity_transition_invalid", f"{unit_id}:{input_state_id}->{output_state_id}")
        if set(continuity_in) != set(continuity_out):
            add_error(errors, "continuity_entity_set_mismatch", str(unit_id))

    if sorted(seen_shots_in_units) != sorted(shot_map):
        add_error(errors, "generation_unit_shot_coverage_invalid", "shots must appear exactly once")

    for previous, current in zip(units, units[1:]):
        if previous.get("continuity_out") != current.get("continuity_in"):
            add_error(
                errors,
                "continuity_handoff_mismatch",
                f"{previous.get('generation_unit_id')}->{current.get('generation_unit_id')}",
            )

    slot_numbers: set[tuple[str, int]] = set()
    asset_ids: set[str] = set()
    for binding in bindings:
        binding_id = str(binding.get("binding_id"))
        asset_id = binding.get("asset_id")
        if isinstance(asset_id, str):
            if asset_id in asset_ids:
                add_error(errors, "binding_asset_id_duplicate", asset_id)
            asset_ids.add(asset_id)
        media_type = binding.get("media_type")
        global_number = binding.get("global_number")
        converter_match = CONVERTER_SLOT_RE.fullmatch(str(binding.get("converter_slot")))
        platform_match = PLATFORM_SLOT_RE.fullmatch(str(binding.get("platform_slot")))
        if media_type in MEDIA_LABELS and converter_match and platform_match:
            converter_label, platform_label = MEDIA_LABELS[media_type]
            numbers = (int(converter_match.group(2)), int(platform_match.group(2)))
            if (
                converter_match.group(1) != converter_label
                or platform_match.group(1) != platform_label
                or numbers != (global_number, global_number)
            ):
                add_error(errors, "binding_slot_number_mismatch", binding_id)
        slot_key = (str(media_type), int(global_number)) if isinstance(global_number, int) else None
        if slot_key is not None:
            if slot_key in slot_numbers:
                add_error(errors, "binding_global_number_duplicate", f"{media_type}:{global_number}")
            slot_numbers.add(slot_key)

        attached = binding.get("attached_to_run") is True
        status = binding.get("status")
        source_kind = binding.get("source_kind")
        if source_kind not in SOURCE_KIND_BY_MEDIA.get(str(media_type), set()):
            add_error(errors, "binding_media_source_kind_mismatch", binding_id)
        if attached and status != "available":
            add_error(errors, "binding_nonavailable_attached", binding_id)
        if attached and binding.get("rights_status") != "verified":
            add_error(errors, "binding_rights_not_verified", binding_id)
        if attached and binding.get("direct_input_policy") in {"forbidden", "planning_only"}:
            add_error(errors, "binding_direct_input_forbidden", binding_id)
        if attached and binding.get("user_lock_status") == "planning_only":
            add_error(errors, "binding_planning_lock_attached", binding_id)
        if (
            attached
            and binding.get("user_lock_status") == "internal_candidate"
            and not binding.get("approval_receipt_id")
        ):
            add_error(errors, "binding_candidate_approval_missing", binding_id)
        if source_kind in PLANNING_SOURCES and (attached or binding.get("literal_frame_boolean") is True):
            add_error(errors, "planning_source_promoted", binding_id)
        if binding.get("literal_frame_boolean") is True and source_kind != "clean_frame":
            add_error(errors, "literal_frame_not_clean", binding_id)
        binding_shots = binding.get("shot_ids", [])
        binding_units = binding.get("unit_ids", [])
        for shot_id in binding_shots:
            if shot_id not in shot_map:
                add_error(errors, "binding_shot_unresolved", f"{binding_id}->{shot_id}")
            elif shot_map[shot_id].get("generation_unit_id") not in binding_units:
                add_error(errors, "binding_shot_unit_scope_mismatch", f"{binding_id}->{shot_id}")
        for unit_id in binding_units:
            if unit_id not in unit_map:
                add_error(errors, "binding_unit_unresolved", f"{binding_id}->{unit_id}")
        for unit_id, order in binding.get("local_order_by_gu", {}).items():
            if unit_id not in unit_map:
                add_error(errors, "binding_local_unit_unresolved", f"{binding_id}->{unit_id}")
            if unit_id not in binding_units:
                add_error(errors, "binding_local_order_outside_unit_scope", f"{binding_id}->{unit_id}")
            if not isinstance(order, int):
                add_error(errors, "binding_local_order_invalid", f"{binding_id}->{unit_id}")

    max_references = int(document.get("provider_limits", {}).get("max_references_per_unit", 0))
    used_units_by_binding: dict[str, set[str]] = {binding_id: set() for binding_id in binding_map}
    for prompt_unit in prompt_units:
        unit_id = prompt_unit.get("generation_unit_id")
        binding_ids = prompt_unit.get("binding_ids", [])
        prompt_text = str(prompt_unit.get("prompt_text", ""))
        prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        if prompt_unit.get("prompt_sha256") != prompt_hash:
            add_error(errors, "prompt_payload_hash_mismatch", str(unit_id))
        if prompt_unit.get("status") != document.get("status"):
            add_error(errors, "prompt_status_mismatch", str(unit_id))
        if "\n\n\n" not in prompt_text:
            add_error(errors, "prompt_paragraph_separator_missing", str(unit_id))
        if unit_id not in unit_map:
            add_error(errors, "prompt_generation_unit_unresolved", str(unit_id))
        if len(binding_ids) > max_references:
            add_error(errors, "provider_reference_budget_exceeded", str(unit_id))
        local_orders: list[int] = []
        for binding_id in binding_ids:
            if isinstance(binding_id, str) and isinstance(unit_id, str):
                used_units_by_binding.setdefault(binding_id, set()).add(unit_id)
            binding = binding_map.get(binding_id)
            if binding is None:
                add_error(errors, "prompt_binding_unresolved", f"{unit_id}->{binding_id}")
                continue
            if binding.get("attached_to_run") is not True or binding.get("status") != "available":
                add_error(errors, "prompt_binding_not_attachable", f"{unit_id}->{binding_id}")
            if unit_id not in binding.get("unit_ids", []):
                add_error(errors, "prompt_binding_unit_scope_mismatch", f"{unit_id}->{binding_id}")
            order = binding.get("local_order_by_gu", {}).get(unit_id)
            if order is None:
                add_error(errors, "prompt_binding_local_order_missing", f"{unit_id}->{binding_id}")
            elif isinstance(order, int):
                local_orders.append(order)
        if len(local_orders) != len(set(local_orders)):
            add_error(errors, "prompt_local_order_duplicate", str(unit_id))
        if local_orders and sorted(local_orders) != list(range(1, len(local_orders) + 1)):
            add_error(errors, "prompt_local_order_noncontiguous", str(unit_id))

        expected_prompt_slots: set[tuple[str, int]] = set()
        for binding_id in binding_ids:
            binding = binding_map.get(binding_id)
            if binding is None or not isinstance(unit_id, str):
                continue
            order = binding.get("local_order_by_gu", {}).get(unit_id)
            media_type = binding.get("media_type")
            if isinstance(order, int) and media_type in MEDIA_LABELS:
                expected_prompt_slots.add((MEDIA_LABELS[media_type][1], order))
        actual_prompt_slots = {
            (match.group(1), int(match.group(2)))
            for match in PROMPT_PLATFORM_SLOT_RE.finditer(prompt_text)
        }
        if actual_prompt_slots != expected_prompt_slots:
            add_error(
                errors,
                "prompt_reference_slot_scope_mismatch",
                f"{unit_id}:expected={sorted(expected_prompt_slots)} actual={sorted(actual_prompt_slots)}",
            )

    for binding_id, binding in binding_map.items():
        local_units = set(binding.get("local_order_by_gu", {}))
        if local_units != used_units_by_binding.get(binding_id, set()):
            add_error(errors, "binding_local_order_prompt_scope_mismatch", binding_id)

    if set(prompt_map) != set(unit_map):
        add_error(errors, "prompt_unit_coverage_invalid", "every generation unit needs one prompt unit")

    if len(prompt_artifact_map) != len(prompt_units):
        add_error(errors, "prompt_artifact_coverage_invalid", "every prompt needs a unique artifact ID")

    expected_dialogue_counts: dict[tuple[str, str], int] = {}
    expected_units_by_dialogue: dict[str, set[str]] = {}
    for line in dialogue_lines:
        dialogue = line.get("text")
        if not isinstance(dialogue, str) or not dialogue:
            continue
        expected_units = {
            str(shot_map[shot_id].get("generation_unit_id"))
            for shot_id in line.get("shot_ids", [])
            if shot_id in shot_map
        }
        expected_units_by_dialogue.setdefault(dialogue, set()).update(expected_units)
        for unit_id in expected_units:
            key = (dialogue, unit_id)
            expected_dialogue_counts[key] = expected_dialogue_counts.get(key, 0) + 1

    for dialogue, expected_units in expected_units_by_dialogue.items():
        occurrences = {
            str(prompt.get("generation_unit_id")): str(prompt.get("prompt_text", "")).count(dialogue)
            for prompt in prompt_units
        }
        if sum(occurrences.values()) == 0:
            add_error(errors, "prompt_dialogue_missing", dialogue)
            continue
        outside = {
            unit_id for unit_id, count in occurrences.items() if count and unit_id not in expected_units
        }
        if outside:
            add_error(errors, "prompt_dialogue_scope_invalid", f"{dialogue}->{sorted(outside)}")
        for unit_id in expected_units:
            expected_count = expected_dialogue_counts[(dialogue, unit_id)]
            if occurrences.get(unit_id, 0) != expected_count:
                add_error(
                    errors,
                    "prompt_dialogue_count_mismatch",
                    f"{dialogue}:{unit_id}:expected={expected_count} actual={occurrences.get(unit_id, 0)}",
                )
    return errors


def validate(
    document: dict[str, Any],
    *,
    asset_foundation_path: Path | None = None,
    asset_stress_path: Path | None = None,
    asset_artifact_root: Path | None = None,
    asset_review_receipt: Path | None = None,
    asset_review_signature: Path | None = None,
    _asset_trust_registry_path: Path | None = None,
) -> list[str]:
    structural = schema_errors(document)
    if structural:
        return structural
    return semantic_errors(document) + asset_gate_errors(
        document,
        asset_foundation_path=asset_foundation_path,
        asset_stress_path=asset_stress_path,
        asset_artifact_root=asset_artifact_root,
        asset_review_receipt=asset_review_receipt,
        asset_review_signature=asset_review_signature,
        asset_trust_registry_path=_asset_trust_registry_path,
    )


def self_test() -> tuple[list[str], dict[str, Any]]:
    from ai_film_asset_stress_test import materialize_fixture as materialize_stress_fixture
    from dircreative_asset_foundation_pass import materialize_fixture as materialize_foundation_fixture

    failures: list[str] = []
    cases = load_json(CASES_PATH).get("cases", [])
    with tempfile.TemporaryDirectory(prefix="dircreative-seedance-asset-gate-") as temp_dir:
        temp_root = Path(temp_dir)
        artifact_root = temp_root / "asset-evidence"
        review_root = temp_root / "reviews"
        trust_root = temp_root / "trust"
        artifact_root.mkdir()
        review_root.mkdir()
        trust_root.mkdir()
        stress_template = load_json(
            ROOT / "tests/fixtures/asset-stress-test/valid-report.json"
        )
        base_asset = stress_template["assets"][0]
        base_cases = stress_template["test_cases"]
        asset_specs = [
            ("VE-RING-ID-v01", "vehicle", "RING-IDENTITY", "RING-BASE"),
            ("CF-GU01-END-v01", "state", "RING-CLEAN-FRAME", "GU01-END"),
            ("GEO-RING-LAYOUT-v01", "scene", "RING-GEOGRAPHY", "RING-GEO-BASE"),
        ]
        stress_template["assets"] = []
        stress_template["test_cases"] = []
        for asset_index, (asset_id, asset_kind, state_family, state_id) in enumerate(asset_specs, 1):
            asset = copy.deepcopy(base_asset)
            asset["asset_id"] = asset_id
            asset["asset_kind"] = asset_kind
            asset["asset_version"] = "v1"
            asset["canonical_relative_path"] = f"canonical/{asset_id}.png"
            asset["state_family"] = state_family
            asset["state_id"] = state_id
            asset["descriptor_text"] = f"Fixture descriptor for {asset_id}."
            asset["required_combinations"] = []
            for reference_index, reference in enumerate(asset["references"], 1):
                reference["reference_id"] = f"REF-{asset_index}-{reference_index}"
                reference["relative_path"] = f"references/asset-{asset_index}-{reference_index}.png"
                reference["source_kind"] = "scene_anchor" if asset_kind == "scene" else "vehicle_reference"
            stress_template["assets"].append(asset)
            for case_index, base_case in enumerate(base_cases, 1):
                case = copy.deepcopy(base_case)
                case["test_case_id"] = f"TC-{asset_index}-{case_index}"
                case["asset_id"] = asset_id
                case["state_family"] = state_family
                case["combination_ids"] = []
                for evidence in case["evidence"]:
                    evidence["evidence_id"] = f"EV-{asset_index}-{case_index}"
                    evidence["relative_path"] = f"evidence/asset-{asset_index}-case-{case_index}.png"
                stress_template["test_cases"].append(case)
        stress_template["matrix_config"]["minimum_case_count"] = len(stress_template["test_cases"])
        stress_template["verdict"]["status"] = "certified"
        stress_template["verdict"]["allowed_shot_scope"] = list(
            {
                shot_class
                for asset in stress_template["assets"]
                for shot_class in asset["intended_shot_classes"]
            }
        )
        stress_template["verdict"]["blocked_shot_scope"] = []
        stress, review_receipt, review_signature, trust_registry_path = materialize_stress_fixture(
            stress_template,
            artifact_root,
            review_root,
            trust_root,
        )
        foundation = load_json(
            ROOT / "tests/fixtures/asset-foundation/valid-pass.json"
        )
        foundation["canonical_asset_ids"] = [item["asset_id"] for item in stress["assets"]]
        planning_source = next(
            item
            for item in foundation["source_assets"]
            if item["source_kind"] == "planning_only"
        )
        foundation["source_assets"] = [
            {
                "asset_id": asset_id,
                "source_kind": "canonical_asset",
                "role": "canonical",
                "relative_path": f"canonical/{asset_id}.png",
                "sha256": "0" * 64,
            }
            for asset_id in foundation["canonical_asset_ids"]
        ] + [planning_source]
        all_shots = ["SH01", "SH02", "SH03", "SH04"]
        foundation["target_shot_ids"] = all_shots
        foundation["stress_test_binding"] = {
            "stress_test_id": stress["stress_test_id"],
            "covered_asset_ids": [item["asset_id"] for item in stress["assets"]],
            "report_relative_path": "stress/stress-report.json",
            "report_sha256": "0" * 64,
            "verdict": "certified",
            "validation_status": "passed",
            "allowed_shot_scope": all_shots,
            "blocked_shot_scope": [],
        }
        foundation["compile_gate"] = {
            "requested_shot_ids": all_shots,
            "status": "allowed",
            "reason_codes": [],
        }
        stress_path = artifact_root / foundation["stress_test_binding"]["report_relative_path"]
        stress_path.parent.mkdir(parents=True, exist_ok=True)
        stress_path.write_text(
            json.dumps(stress, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        foundation = materialize_foundation_fixture(foundation, artifact_root)
        foundation["stress_test_binding"]["report_sha256"] = hashlib.sha256(
            stress_path.read_bytes()
        ).hexdigest()
        foundation_path = temp_root / "asset-foundation-pass.json"
        foundation_path.write_text(
            json.dumps(foundation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        valid = load_json(VALID_PATH)
        source_map = {
            item["asset_id"]: item
            for item in foundation["source_assets"]
            if item["source_kind"] == "canonical_asset"
        }
        stress_asset_map = {item["asset_id"]: item for item in stress["assets"]}
        for binding in valid["bindings"]:
            if binding["asset_id"] not in source_map:
                continue
            binding["asset_version"] = stress_asset_map[binding["asset_id"]]["asset_version"]
            binding["relative_path"] = source_map[binding["asset_id"]]["relative_path"]
            binding["sha256"] = source_map[binding["asset_id"]]["sha256"]
        valid["asset_foundation_gate"] = {
            "project_id": foundation["project_id"],
            "pass_id": foundation["pass_id"],
            "pass_artifact_sha256": hashlib.sha256(foundation_path.read_bytes()).hexdigest(),
            "stress_test_id": stress["stress_test_id"],
            "stress_report_sha256": hashlib.sha256(stress_path.read_bytes()).hexdigest(),
            "stress_verdict": "certified",
            "requested_shot_ids": all_shots,
            "allowed_shot_ids": all_shots,
            "blocked_shot_ids": [],
            "covered_asset_ids": foundation["stress_test_binding"]["covered_asset_ids"],
        }
        valid_errors = validate(
            valid,
            asset_foundation_path=foundation_path,
            asset_stress_path=stress_path,
            asset_artifact_root=artifact_root,
            asset_review_receipt=review_receipt,
            asset_review_signature=review_signature,
            _asset_trust_registry_path=trust_registry_path,
        )
        if valid_errors:
            failures.append(f"valid fixture rejected: {valid_errors[:3]}")

        rejected = 0
        for case in cases:
            case_foundation = copy.deepcopy(foundation)
            case_stress = copy.deepcopy(stress)
            dependency_mutations = case.get("dependency_mutations", {})
            if dependency_mutations.get("stress"):
                case_stress = apply_mutations(case_stress, dependency_mutations["stress"])
            case_stress_path = artifact_root / "stress" / f"{case['case_id']}-stress.json"
            case_stress_path.write_text(
                json.dumps(case_stress, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            case_foundation["stress_test_binding"]["report_sha256"] = hashlib.sha256(
                case_stress_path.read_bytes()
            ).hexdigest()
            case_foundation["stress_test_binding"]["report_relative_path"] = str(
                case_stress_path.relative_to(artifact_root)
            )
            if dependency_mutations.get("foundation"):
                case_foundation = apply_mutations(
                    case_foundation,
                    dependency_mutations["foundation"],
                )
            case_foundation_path = temp_root / f"{case['case_id']}-foundation.json"
            case_foundation_path.write_text(
                json.dumps(case_foundation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            case_document = copy.deepcopy(valid)
            case_document["asset_foundation_gate"]["pass_artifact_sha256"] = hashlib.sha256(
                case_foundation_path.read_bytes()
            ).hexdigest()
            case_document["asset_foundation_gate"]["stress_report_sha256"] = hashlib.sha256(
                case_stress_path.read_bytes()
            ).hexdigest()
            case_document = apply_mutations(case_document, case.get("mutations", []))
            errors = validate(
                case_document,
                asset_foundation_path=case_foundation_path,
                asset_stress_path=case_stress_path,
                asset_artifact_root=artifact_root,
                asset_review_receipt=review_receipt,
                asset_review_signature=review_signature,
                _asset_trust_registry_path=trust_registry_path,
            )
            expected = case["expected_error"]
            if any(error.startswith(expected + ":") for error in errors):
                rejected += 1
            else:
                failures.append(
                    f"{case['case_id']}: expected {expected}, got {errors[:3]}"
                )
    return failures, {
        "valid_fixture_passed": not valid_errors,
        "negative_case_count": len(cases),
        "negative_cases_rejected": rejected,
        "node_count": len(valid.get("narrative_nodes", [])),
        "shot_count": len(valid.get("shots", [])),
        "generation_unit_count": len(valid.get("generation_units", [])),
        "binding_count": len(valid.get("bindings", [])),
        "asset_foundation_gate_validated": not any(
            error.startswith("asset_") for error in valid_errors
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIRcreative script-to-Seedance handoffs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--asset-foundation-pass", type=Path)
    validate_parser.add_argument("--asset-stress-report", type=Path)
    validate_parser.add_argument("--asset-artifact-root", type=Path)
    validate_parser.add_argument("--asset-review-receipt", type=Path)
    validate_parser.add_argument("--asset-review-signature", type=Path)
    args = parser.parse_args()

    if args.command == "self-test":
        failures, summary = self_test()
        print(json.dumps({**summary, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"DIRCREATIVE_SCRIPT_TO_SEEDANCE_HANDOFF_AUDIT: {'PASS' if not failures else 'FAIL'}")
        return 0 if not failures else 1

    document = load_json(args.path)
    errors = validate(
        document,
        asset_foundation_path=args.asset_foundation_pass,
        asset_stress_path=args.asset_stress_report,
        asset_artifact_root=args.asset_artifact_root,
        asset_review_receipt=args.asset_review_receipt,
        asset_review_signature=args.asset_review_signature,
    )
    print(json.dumps({"path": str(args.path), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
