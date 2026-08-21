#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - repository validation provides jsonschema
    Draft202012Validator = None  # type: ignore[assignment]

from dircreative_state_audit import _builtin_schema_errors


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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add_error(errors: list[str], code: str, detail: str) -> None:
    errors.append(f"{code}: {detail}")


def schema_errors(document: dict[str, Any]) -> list[str]:
    schema = load_json(SCHEMA_PATH)
    if Draft202012Validator is None or os.environ.get("DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"):
        return [
            f"schema_error: {error}"
            for error in _builtin_schema_errors(document, schema, schema, "$")
        ]
    validator = Draft202012Validator(schema)
    return [
        "schema_error: "
        + "/".join(str(item) for item in error.absolute_path)
        + f": {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    ]


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


def validate(document: dict[str, Any]) -> list[str]:
    structural = schema_errors(document)
    if structural:
        return structural
    return semantic_errors(document)


def pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    target = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    return target, parts[-1]


def apply_mutations(document: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    for mutation in mutations:
        parent, key = pointer_parent(result, mutation["path"])
        index: int | str = int(key) if isinstance(parent, list) and key != "-" else key
        if mutation["op"] == "replace":
            parent[index] = mutation["value"]
        elif mutation["op"] == "remove":
            del parent[index]
        elif mutation["op"] == "add":
            if isinstance(parent, list):
                if index == "-":
                    parent.append(mutation["value"])
                else:
                    parent.insert(int(index), mutation["value"])
            else:
                parent[index] = mutation["value"]
        else:
            raise ValueError(f"unsupported fixture mutation: {mutation['op']}")
    return result


def self_test() -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    valid = load_json(VALID_PATH)
    valid_errors = validate(valid)
    if valid_errors:
        failures.append(f"valid fixture rejected: {valid_errors[:3]}")

    cases = load_json(CASES_PATH).get("cases", [])
    rejected = 0
    for case in cases:
        mutated = apply_mutations(valid, case["mutations"])
        errors = validate(mutated)
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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIRcreative script-to-Seedance handoffs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    args = parser.parse_args()

    if args.command == "self-test":
        failures, summary = self_test()
        print(json.dumps({**summary, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"DIRCREATIVE_SCRIPT_TO_SEEDANCE_HANDOFF_AUDIT: {'PASS' if not failures else 'FAIL'}")
        return 0 if not failures else 1

    document = load_json(args.path)
    errors = validate(document)
    print(json.dumps({"path": str(args.path), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
