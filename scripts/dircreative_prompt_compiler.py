#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dircreative_state_audit import _builtin_schema_errors
from dircreative_model_capability_audit import REGISTRY_PATH, load_yaml


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/prompt-ir.schema.json"
REFERENCE_TOKEN_RE = re.compile(r"@(Image|Video|Audio)\s*([0-9]+)", re.IGNORECASE)
CANONICAL_REFERENCE_SLOT_RE = re.compile(r"@(Image|Video|Audio) [1-9][0-9]*", re.IGNORECASE)
INTERNAL_SURFACE_PATTERNS = {
    "internal_shot_or_asset_label": re.compile(r"\b(?:R|S|SHOT|SCENE|ASSET)[-_ ]?0*[0-9]+\b", re.IGNORECASE),
    "internal_asset_id": re.compile(r"\basset_[A-Za-z0-9_-]+\b", re.IGNORECASE),
    "local_path": re.compile(r"(?:/Users/|/home/|/private/|outputs/|docs/film-preproduction/|examples/)", re.IGNORECASE),
    "sha256": re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE),
    "internal_field": re.compile(r"\b(?:schema_version|source_hash|failure_id|retry_rules|manifest)\b", re.IGNORECASE),
    "internal_control_language": re.compile(
        r"\b(?:QA|quality[ -]?assurance|retry|rerun|failure(?:_id)?|pass signal|pass when|"
        r"direct video input policy|pre-generation contract|generation receipt|next_action)\b",
        re.IGNORECASE,
    ),
}


class PromptContractError(Exception):
    pass


@dataclass(frozen=True)
class CompileResult:
    prompt: str
    unit_prompts: list[str]
    adapter: str
    attached_slots: list[str]
    postproduction_audio: list[str]
    unit_postproduction_audio: list[list[str]]
    structural_score: int


def _schema_errors(payload: object) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return _builtin_schema_errors(payload, schema, schema, "$")
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    ]


def _time_value(raw: Any) -> float:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(float(raw)):
        return float(raw)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid time value: {raw!r}")
    value = raw.strip()
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError(f"invalid time value: {raw!r}")
        return float(parts[0]) * 60 + float(parts[1])
    return float(value)


def _surface_errors(text: str, allowed_slots: set[str]) -> list[str]:
    errors: list[str] = []
    for code, pattern in INTERNAL_SURFACE_PATTERNS.items():
        match = pattern.search(text)
        if match:
            errors.append(f"{code}: {match.group(0)}")
    used_slots = {
        f"@{kind.title()} {index}"
        for kind, index in REFERENCE_TOKEN_RE.findall(text)
    }
    phantom = sorted(used_slots - allowed_slots)
    missing = sorted(allowed_slots - used_slots)
    if phantom:
        errors.append(f"phantom_reference_slots: {', '.join(phantom)}")
    if missing:
        errors.append(f"attached_reference_slots_missing_from_prompt: {', '.join(missing)}")
    return errors


def terminal_surface_errors(text: str, allowed_slots: set[str] | None = None) -> list[str]:
    return _surface_errors(text, allowed_slots or set())


def semantic_errors(payload: dict[str, Any], *, verify_project_files: bool = True) -> list[str]:
    errors = _schema_errors(payload)
    if errors:
        return errors

    assets = payload["intake"]["supplied_assets"]
    asset_ids = [item["asset_id"] for item in assets]
    if len(asset_ids) != len(set(asset_ids)):
        errors.append("asset_id values must be unique")
    asset_map = {item["asset_id"]: item for item in assets}
    for asset in assets:
        if asset["source_kind"] == "project_file":
            if not asset.get("source_hash"):
                errors.append(f"project_file asset requires source_hash: {asset['asset_id']}")
            if verify_project_files:
                path = ROOT / asset["source_locator"]
                if not path.is_file():
                    errors.append(f"project_file asset is missing: {asset['source_locator']}")
                elif asset.get("source_hash"):
                    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                    if actual_hash != asset["source_hash"]:
                        errors.append(f"project_file asset hash mismatch: {asset['asset_id']}")

    references = payload["references"]
    slots = [item["platform_slot"] for item in references]
    if len(slots) != len(set(slots)):
        errors.append("platform_slot values must be unique")
    for item in references:
        asset = asset_map.get(item["asset_id"])
        if asset is None:
            errors.append(f"reference uses unknown asset_id: {item['asset_id']}")
            continue
        if item["attached_to_run"] and item["direct_input_policy"] == "planning_only":
            errors.append(f"planning-only reference cannot be attached: {item['platform_slot']}")
        if item["required_for_shot"] and not item["attached_to_run"]:
            errors.append(f"required reference is not attached: {item['platform_slot']}")
        if item["attached_to_run"] and not asset["locked"]:
            errors.append(f"attached reference asset is not locked: {item['asset_id']}")

    entities = payload["entities"]
    entity_ids = [item["entity_id"] for item in entities]
    if len(entity_ids) != len(set(entity_ids)):
        errors.append("entity_id values must be unique")
    entity_map = {item["entity_id"]: item for item in entities}
    for entity in entities:
        for asset_id in entity["reference_asset_ids"]:
            if asset_id not in asset_map:
                errors.append(f"entity {entity['entity_id']} uses unknown reference asset: {asset_id}")
        owner = entity.get("owner_entity_id")
        if owner and owner not in entity_map:
            errors.append(f"entity {entity['entity_id']} has unknown owner: {owner}")
        for code, pattern in INTERNAL_SURFACE_PATTERNS.items():
            if code in {"internal_field", "sha256"}:
                continue
            if pattern.search(entity["external_name"]):
                errors.append(f"entity external_name exposes {code}: {entity['entity_id']}")
    for entity in entities:
        visited: set[str] = set()
        cursor = entity.get("owner_entity_id")
        while cursor:
            if cursor == entity["entity_id"] or cursor in visited:
                errors.append(f"entity ownership cycle includes: {entity['entity_id']}")
                break
            visited.add(cursor)
            cursor = entity_map.get(cursor, {}).get("owner_entity_id")

    shots = payload["shot_blocks"]
    shot_ids = [item["shot_id"] for item in shots]
    if len(shot_ids) != len(set(shot_ids)):
        errors.append("shot_id values must be unique")
    try:
        shot_times = [(_time_value(item["time_start"]), _time_value(item["time_end"]), item) for item in shots]
    except ValueError as exc:
        errors.append(str(exc))
        shot_times = []
    if shot_times:
        shot_times.sort(key=lambda item: item[0])
        cursor = 0.0
        for start, end, shot in shot_times:
            if end <= start:
                errors.append(f"shot has non-positive duration: {shot['shot_id']}")
            if not math.isclose(start, cursor, abs_tol=0.001):
                errors.append(f"shot timeline gap or overlap before {shot['shot_id']}: expected {cursor:.2f}, got {start:.2f}")
            cursor = end
            action_owners = [action["owner_entity_id"] for action in shot["entity_actions"]]
            duplicate_owners = sorted({owner for owner in action_owners if action_owners.count(owner) > 1})
            if duplicate_owners:
                errors.append(f"shot {shot['shot_id']} has conflicting actions for owners: {', '.join(duplicate_owners)}")
            for action in shot["entity_actions"]:
                owner = action["owner_entity_id"]
                target = action.get("target_entity_id")
                if owner not in entity_map:
                    errors.append(f"shot {shot['shot_id']} action has unknown owner: {owner}")
                if target and target not in entity_map:
                    errors.append(f"shot {shot['shot_id']} action has unknown target: {target}")
            for cue in shot["audio_cues"]:
                if not isinstance(cue, dict):
                    continue
                for field in ("speaker_entity_id", "source_entity_id"):
                    entity_id = cue.get(field)
                    if entity_id and entity_id not in entity_map:
                        errors.append(f"shot {shot['shot_id']} audio cue has unknown {field}: {entity_id}")
                try:
                    cue_time = _time_value(cue["time"])
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if cue_time < start - 0.001 or cue_time > end + 0.001:
                        errors.append(f"shot {shot['shot_id']} audio cue falls outside shot: {cue['time']}")
        target = float(payload["output"]["target_duration_sec"])
        if not math.isclose(cursor, target, abs_tol=0.001):
            errors.append(f"shot timeline ends at {cursor:.2f}, expected {target:.2f}")

    units = payload["generation_plan"]["units"]
    unit_ids = [item["unit_id"] for item in units]
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("generation unit_id values must be unique")
    try:
        unit_times = [(_time_value(item["time_start"]), _time_value(item["time_end"]), item) for item in units]
    except ValueError as exc:
        errors.append(str(exc))
        unit_times = []
    if unit_times:
        unit_times.sort(key=lambda item: item[0])
        cursor = 0.0
        max_unit = float(payload["output"]["generation_unit_sec"])
        assigned_shots: list[str] = []
        for unit_index, (start, end, unit) in enumerate(unit_times):
            if not math.isclose(start, cursor, abs_tol=0.001):
                errors.append(f"generation unit gap or overlap before {unit['unit_id']}")
            if end <= start or end - start > max_unit + 0.001:
                errors.append(f"generation unit exceeds allowed duration: {unit['unit_id']}")
            unknown = sorted(set(unit["shot_ids"]) - set(shot_ids))
            if unknown:
                errors.append(f"generation unit {unit['unit_id']} uses unknown shots: {', '.join(unknown)}")
            assigned_shots.extend(unit["shot_ids"])
            for shot_id in unit["shot_ids"]:
                if shot_id not in shot_ids:
                    continue
                shot_start, shot_end, _ = next(item for item in shot_times if item[2]["shot_id"] == shot_id)
                if shot_start < start - 0.001 or shot_end > end + 0.001:
                    errors.append(f"generation unit {unit['unit_id']} does not contain shot {shot_id}")
            if unit_index + 1 < len(unit_times):
                next_unit = unit_times[unit_index + 1][2]
                if unit["outgoing_handoff_key"] != next_unit["incoming_handoff_key"]:
                    errors.append(f"generation unit handoff key mismatch: {unit['unit_id']} -> {next_unit['unit_id']}")
                if _clean(unit["outgoing_state"]).lower() != _clean(next_unit["incoming_state"]).lower():
                    errors.append(f"generation unit handoff state mismatch: {unit['unit_id']} -> {next_unit['unit_id']}")
            cursor = end
        missing_shots = sorted(set(shot_ids) - set(assigned_shots))
        duplicate_shots = sorted({shot_id for shot_id in assigned_shots if assigned_shots.count(shot_id) > 1})
        if missing_shots:
            errors.append(f"generation units do not cover shots: {', '.join(missing_shots)}")
        if duplicate_shots:
            errors.append(f"generation units assign shots more than once: {', '.join(duplicate_shots)}")
        target = float(payload["output"]["target_duration_sec"])
        if not math.isclose(cursor, target, abs_tol=0.001):
            errors.append(f"generation units end at {cursor:.2f}, expected {target:.2f}")
        if target > max_unit and len(unit_times) < 2:
            errors.append("target duration exceeds one generation unit but generation_plan does not split the work")

    adapter = payload["generation_plan"]["selected_adapter"]
    if adapter != payload["capability"]["model_key"] and adapter != "generic":
        errors.append("generation_plan.selected_adapter does not match capability.model_key")
    attached = [item for item in references if item["attached_to_run"]]
    if adapter == "seedance":
        bad_slots = [item["platform_slot"] for item in attached if not CANONICAL_REFERENCE_SLOT_RE.fullmatch(item["platform_slot"])]
        if bad_slots:
            errors.append(f"Seedance attached references require explicit @ slots: {', '.join(bad_slots)}")
    if adapter in {"sora", "runway"} and len(attached) > 1:
        errors.append(f"{adapter} compiler route accepts one direct visual input; compose or select one anchor before compilation")
    if payload["audio_plan"]["generation_route"] == "reference_audio":
        attached_audio = [
            item for item in attached
            if asset_map.get(item["asset_id"], {}).get("role") == "audio"
        ]
        if not attached_audio:
            errors.append("reference_audio route requires an attached audio reference")

    try:
        registry = load_yaml(REGISTRY_PATH)
        cards = {card["capability_card_id"]: card for card in registry.get("models", [])}
        selected = cards.get(payload["capability"]["capability_card_id"])
        if selected is None:
            errors.append("capability_card_id does not resolve in model-sources registry")
        else:
            expected = {
                "model_key": selected.get("model_key"),
                "version": str(selected.get("version")),
                "provider_surface": selected.get("provider_surface"),
            }
            for field, value in expected.items():
                if str(payload["capability"].get(field)) != str(value):
                    errors.append(f"capability {field} does not match resolved card")
            if selected.get("status") != "current":
                errors.append("capability card is not current")
            duration_contract = selected.get("duration", {})
            for start, end, unit in unit_times:
                duration = end - start
                kind = duration_contract.get("kind")
                if kind == "discrete" and duration not in [float(value) for value in duration_contract.get("supported_values_sec", [])]:
                    errors.append(f"generation unit duration is unsupported by capability card: {unit['unit_id']}")
                elif kind == "range":
                    minimum = float(duration_contract.get("minimum_sec", 0))
                    maximum = float(duration_contract.get("maximum_sec", 0))
                    if duration < minimum - 0.001 or duration > maximum + 0.001:
                        errors.append(f"generation unit duration is unsupported by capability card: {unit['unit_id']}")
                elif kind == "version_scoped":
                    supported_range = duration_contract.get("researched_range_sec", [])
                    if len(supported_range) == 2 and not (
                        float(supported_range[0]) - 0.001 <= duration <= float(supported_range[1]) + 0.001
                    ):
                        errors.append(f"generation unit duration is unsupported by capability card: {unit['unit_id']}")

            route = payload["audio_plan"]["generation_route"]
            audio_contract = selected.get("audio_route", {})
            if route == "unresolved":
                errors.append("audio generation route must be resolved before compilation")
            elif route == "native" and audio_contract.get("native_audio_supported") is not True:
                errors.append("native audio is not verified for the resolved capability card")
            elif route == "reference_audio" and audio_contract.get("audio_reference_supported") is not True:
                errors.append("audio reference is not supported by the resolved capability card")
    except Exception as exc:  # fail closed when the durable registry cannot be read
        errors.append(f"capability registry could not be resolved: {exc}")
    return errors


def validate_prompt_ir(payload: dict[str, Any], *, verify_project_files: bool = True) -> None:
    errors = semantic_errors(payload, verify_project_files=verify_project_files)
    if errors:
        raise PromptContractError("; ".join(errors))


def structural_score(payload: dict[str, Any]) -> int:
    """Score ten independently observable contract dimensions; never trust authored QA scores."""
    checks = [
        bool(payload.get("references")),
        all(entity.get("reference_asset_ids") for entity in payload.get("entities", [])),
        all(shot.get("entity_actions") for shot in payload.get("shot_blocks", [])),
        all(shot.get("environment_action") for shot in payload.get("shot_blocks", [])),
        all(shot.get("camera") for shot in payload.get("shot_blocks", [])),
        all("audio_cues" in shot for shot in payload.get("shot_blocks", [])),
        bool(payload.get("audio_plan", {}).get("generation_route")),
        bool(payload.get("generation_plan", {}).get("units")),
        all(layer in payload.get("render_look", {}) for layer in ("lighting", "optics", "atmosphere", "grade")),
        not semantic_errors(payload, verify_project_files=False),
    ]
    return sum(10 for passed in checks if passed)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().rstrip(".")


def _time_label(raw: Any) -> str:
    return f"{_time_value(raw):05.2f}"


def _look_text(layer: dict[str, Any]) -> str:
    if layer.get("intensity") == "none":
        return ""
    ordered = [
        layer.get("condition"),
        layer.get("effect"),
        layer.get("physical_behavior"),
        layer.get("source_direction_quality"),
        layer.get("contrast_shadow"),
        layer.get("medium"),
        layer.get("density_scale"),
        layer.get("light_path_visibility"),
        layer.get("movement"),
        layer.get("white_balance_anchor"),
        layer.get("contrast_gamma"),
        layer.get("black_level"),
        layer.get("highlight_rolloff"),
        layer.get("saturation_density"),
        layer.get("palette_separation"),
        layer.get("grain_halation"),
    ]
    parts = [_clean(item) for item in ordered if item and _clean(item).lower() != "none by design"]
    return "; ".join(parts)


def compile_prompt(payload: dict[str, Any], *, verify_project_files: bool = True) -> CompileResult:
    validate_prompt_ir(payload, verify_project_files=verify_project_files)
    adapter = payload["generation_plan"]["selected_adapter"]
    attached = [item for item in payload["references"] if item["attached_to_run"]]
    handoff_slots = {item["platform_slot"] for item in attached}
    allowed_slots = {item["platform_slot"] for item in attached} if adapter == "seedance" else set()
    entity_names = {item["entity_id"]: item["external_name"] for item in payload["entities"]}

    sections: list[str] = []
    if attached:
        reference_lines = []
        for index, item in enumerate(attached, start=1):
            preserve = "; ".join(_clean(value) for value in item["preserve"])
            anti = "; ".join(_clean(value) for value in item["anti_misread"])
            if adapter == "seedance":
                reference_name = item["platform_slot"]
            elif adapter == "sora":
                reference_name = "The attached first-frame image"
            elif adapter == "runway":
                reference_name = "The input image"
            else:
                reference_name = f"Attached reference image {index}"
            line = f"{reference_name} is {_clean(item['role'])}. Preserve {preserve}."
            if anti:
                line += f" Keep the reference role limited to this job: {anti}."
            reference_lines.append(line)
        sections.append("References:\n" + "\n".join(reference_lines))

    output = payload["output"]
    project = payload["project"]
    composition = payload["composition"]
    duration_phrase = f"{_clean(output['target_duration_sec'])}-second"
    intended_use = _clean(project["intended_use"])
    if duration_phrase.lower() not in intended_use.lower():
        intended_use = f"{duration_phrase} {intended_use}"
    sections.append(
        f"Create a {intended_use} in {_clean(output['aspect_ratio'])}. "
        f"Purpose: {_clean(composition['narrative_purpose'])}."
    )

    entity_lines = []
    for entity in payload["entities"]:
        immutable = "; ".join(_clean(value) for value in entity["immutable"])
        entity_lines.append(
            f"{_clean(entity['external_name'])}: starts {_clean(entity['starting_state'])}, positioned {_clean(entity['screen_position'])}. "
            f"Keep {immutable}."
        )
    sections.append(("Motion subjects:\n" if adapter == "runway" else "Subjects and assets:\n") + "\n".join(entity_lines))

    lock_values: list[str] = []
    native_audio = payload["audio_plan"]["generation_route"] in {"native", "reference_audio"}
    for lock_name, values in payload["global_locks"].items():
        if lock_name == "audio_spine" and not native_audio:
            continue
        lock_values.extend(_clean(value) for value in values if _clean(value))
    sections.append("Continuity:\n" + "; ".join(lock_values) + ".")

    timeline_lines = []
    timeline_bodies: dict[str, str] = {}
    postproduction_audio: list[str] = []
    for shot in sorted(payload["shot_blocks"], key=lambda item: _time_value(item["time_start"])):
        parts = [
            _clean(shot["story_beat"]),
            _clean(shot["emotional_or_attention_beat"]),
        ]
        for action in shot["entity_actions"]:
            owner = _clean(entity_names[action["owner_entity_id"]])
            target = action.get("target_entity_id")
            target_text = f" toward {_clean(entity_names[target])}" if target else ""
            action_text = (
                f"{owner} starts {_clean(action['initial_state'])}. After {_clean(action['trigger'])}, "
                f"{_clean(action['path'])}{target_text}. End with {_clean(action['final_state'])}"
            )
            if action.get("physical_consequence"):
                action_text += f". Physical result: {_clean(action['physical_consequence'])}"
            parts.append(action_text)
        environment = shot["environment_action"]
        environment_parts = [_clean(value) for value in environment.values() if _clean(value)]
        if environment_parts:
            parts.append("Environment: " + "; ".join(environment_parts))
        camera = shot["camera"]
        parts.append(
            "Camera: "
            f"{_clean(camera['shot_size'])}, {_clean(camera['angle_height_axis'])}, {_clean(camera['support'])}; "
            f"start on {_clean(camera['start_target'])}, {_clean(camera['path'])}, end on {_clean(camera['end_target'])}; "
            f"{_clean(camera['speed_easing'])}; focus {_clean(camera['focus'])}. The move is motivated by {_clean(camera['motivation'])}"
        )
        parts.append("Composition: " + _clean(shot["composition_state"]))
        if shot.get("look_delta") and _clean(shot["look_delta"]).lower() != "none by design":
            parts.append("Look change: " + _clean(shot["look_delta"]))
        cue_texts = []
        for cue in shot["audio_cues"]:
            if isinstance(cue, str):
                cue_text = _clean(cue)
            else:
                speaker = cue.get("speaker_entity_id") or cue.get("source_entity_id")
                speaker_text = f" from {_clean(entity_names[speaker])}" if speaker else ""
                cue_text = f"{_clean(cue['time'])} {_clean(cue['kind'])}{speaker_text}: {_clean(cue['cue'])}, {_clean(cue['perspective'])}"
            if native_audio:
                cue_texts.append(cue_text)
            else:
                postproduction_audio.append(cue_text)
        if cue_texts:
            parts.append("Audio: " + "; ".join(cue_texts))
        timeline_bodies[shot["shot_id"]] = ". ".join(parts) + "."
        timeline_lines.append(f"{_time_label(shot['time_start'])}-{_time_label(shot['time_end'])}: {timeline_bodies[shot['shot_id']]}")
    sections.append("Timeline:\n" + "\n".join(timeline_lines))

    look = payload["render_look"]
    look_lines = []
    for label in ("lighting", "optics", "atmosphere", "grade"):
        value = _look_text(look[label])
        if value:
            look_lines.append(f"{label.title()}: {value}.")
    if look_lines and adapter != "runway":
        look_lines.append("Preserve " + "; ".join(_clean(value) for value in look["preserve"]) + ".")
        look_lines.append(_clean(look["exit_or_continuity"]) + ".")
        sections.append("Look:\n" + "\n".join(look_lines))

    transitions = payload.get("transition_plan", [])
    if transitions:
        transition_lines = []
        for item in transitions:
            line = f"{_clean(item['visual_bridge'])}; preserve {_clean(item['continuity_state'])}."
            transition_lines.append(line)
            if item.get("audio_bridge") and not native_audio:
                postproduction_audio.append(_clean(item["audio_bridge"]))
        sections.append("Transitions:\n" + "\n".join(transition_lines))

    prompt = "\n\n".join(section for section in sections if section).strip() + "\n"
    surface_errors = _surface_errors(prompt, allowed_slots)
    if surface_errors:
        raise PromptContractError("; ".join(surface_errors))
    unit_prompts: list[str] = []
    unit_postproduction_audio: list[list[str]] = []
    target_duration = float(payload["output"]["target_duration_sec"])
    prefix_sections = [section for section in sections if not section.startswith("Timeline:") and not section.startswith("Look:") and not section.startswith("Transitions:")]
    look_sections = [section for section in sections if section.startswith("Look:")]
    shot_map = {shot["shot_id"]: shot for shot in payload["shot_blocks"]}
    for unit in sorted(payload["generation_plan"]["units"], key=lambda item: _time_value(item["time_start"])):
        unit_start = _time_value(unit["time_start"])
        unit_end = _time_value(unit["time_end"])
        unit_duration = unit_end - unit_start
        duration_source = f"{_clean(output['target_duration_sec'])}-second"
        duration_target = f"{unit_duration:g}-second"
        local_prefix: list[str] = []
        for section in prefix_sections:
            if section.startswith("Subjects and assets:") or section.startswith("Motion subjects:"):
                unit_entity_lines = []
                for entity in payload["entities"]:
                    immutable = "; ".join(_clean(value) for value in entity["immutable"])
                    unit_entity_lines.append(f"{_clean(entity['external_name'])}: preserve {immutable}.")
                local_prefix.append("Subjects and assets:\n" + "\n".join(unit_entity_lines))
            else:
                local_prefix.append(section.replace(duration_source, duration_target))
        handoff_lines = [
            f"Begin with {_clean(unit['incoming_state'])}.",
            f"End with {_clean(unit['outgoing_state'])}.",
        ]
        unit_audio: list[str] = []
        if native_audio:
            handoff_lines.append(f"Carry the audio boundary as {_clean(unit['audio_handoff'])}.")
        else:
            unit_audio.append(_clean(unit["audio_handoff"]))
        local_timeline: list[str] = []
        for shot_id in unit["shot_ids"]:
            shot = shot_map[shot_id]
            local_start = _time_value(shot["time_start"]) - unit_start
            local_end = _time_value(shot["time_end"]) - unit_start
            local_timeline.append(f"{_time_label(local_start)}-{_time_label(local_end)}: {timeline_bodies[shot_id]}")
        unit_sections = [
            *local_prefix,
            "State continuity:\n" + "\n".join(handoff_lines),
            "Timeline:\n" + "\n".join(local_timeline),
            *look_sections,
        ]
        unit_prompt = "\n\n".join(unit_sections).strip() + "\n"
        unit_surface_errors = _surface_errors(unit_prompt, allowed_slots)
        if unit_surface_errors:
            raise PromptContractError("; ".join(unit_surface_errors))
        unit_prompts.append(unit_prompt)
        unit_postproduction_audio.append(unit_audio)

    score = structural_score(payload)
    return CompileResult(
        prompt=prompt,
        unit_prompts=unit_prompts,
        adapter=adapter,
        attached_slots=sorted(handoff_slots),
        postproduction_audio=postproduction_audio,
        unit_postproduction_audio=unit_postproduction_audio,
        structural_score=score,
    )


def load_prompt_ir(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptContractError(f"cannot read Prompt IR {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PromptContractError("Prompt IR root must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and compile DIRcreative Prompt IR without executing media generation.")
    parser.add_argument("action", choices=("validate", "compile", "inspect"))
    parser.add_argument("prompt_ir", type=Path)
    parser.add_argument("--skip-project-file-check", action="store_true")
    parser.add_argument("--unit-index", type=int, help="One-based generation-unit index for multi-unit compilation.")
    args = parser.parse_args()
    path = args.prompt_ir if args.prompt_ir.is_absolute() else ROOT / args.prompt_ir
    try:
        payload = load_prompt_ir(path)
        if args.action == "validate":
            validate_prompt_ir(payload, verify_project_files=not args.skip_project_file_check)
            print(json.dumps({"status": "PASS", "prompt_ir": str(path)}, ensure_ascii=False, indent=2))
        else:
            result = compile_prompt(payload, verify_project_files=not args.skip_project_file_check)
            if args.action == "compile":
                if len(result.unit_prompts) > 1 and args.unit_index is None:
                    raise PromptContractError("multi-unit Prompt IR requires --unit-index; compile and paste one generation unit at a time")
                if args.unit_index is not None:
                    if args.unit_index < 1 or args.unit_index > len(result.unit_prompts):
                        raise PromptContractError("--unit-index is outside the generation plan")
                    print(result.unit_prompts[args.unit_index - 1], end="")
                else:
                    print(result.prompt, end="")
            else:
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    except PromptContractError as exc:
        print(json.dumps({"status": "FAIL", "prompt_ir": str(path), "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
