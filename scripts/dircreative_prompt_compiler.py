#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dircreative_state_audit import _builtin_schema_errors
from dircreative_model_capability_audit import REGISTRY_PATH, load_yaml
from dircreative_adapters import AdapterContractError, get_adapter, shared_surface_errors
from dircreative_adapters.base import INTERNAL_SURFACE_PATTERNS, clean as _clean


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/prompt-ir.schema.json"


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


def terminal_surface_errors(text: str, allowed_slots: set[str] | None = None) -> list[str]:
    return shared_surface_errors(text, allowed_slots or set())


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
    try:
        errors.extend(get_adapter(adapter).validate_capability(payload))
    except AdapterContractError as exc:
        errors.append(str(exc))
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
            if selected.get("model_key") == "seedance":
                reference_modes = selected.get("reference_modes", {})
                for media_label, field_name in (
                    ("Image", "maximum_image_references"),
                    ("Video", "maximum_video_references"),
                    ("Audio", "maximum_audio_references"),
                ):
                    limit = reference_modes.get(field_name)
                    count = sum(
                        str(item.get("platform_slot", "")).startswith(f"@{media_label} ")
                        for item in attached
                    )
                    if isinstance(limit, int) and count > limit:
                        errors.append(
                            f"{media_label.lower()} reference count is unsupported by capability card: {count} > {limit}"
                        )
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
                elif kind == "upper_bound":
                    maximum = float(duration_contract.get("maximum_sec", 0))
                    if duration > maximum + 0.001:
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


def compile_prompt(payload: dict[str, Any], *, verify_project_files: bool = True) -> CompileResult:
    validate_prompt_ir(payload, verify_project_files=verify_project_files)
    adapter_name = payload["generation_plan"]["selected_adapter"]
    attached = [item for item in payload["references"] if item["attached_to_run"]]
    units = sorted(
        payload["generation_plan"]["units"],
        key=lambda item: _time_value(item["time_start"]),
    )
    try:
        adapter = get_adapter(adapter_name)
        prompt = adapter.compile_full(payload)
        unit_prompts = [adapter.compile_unit(payload, unit) for unit in units]
        postproduction_audio = adapter.postproduction_audio(payload)
        unit_postproduction_audio = [
            adapter.unit_postproduction_audio(payload, unit)
            for unit in units
        ]
    except AdapterContractError as exc:
        raise PromptContractError(str(exc)) from exc

    return CompileResult(
        prompt=prompt,
        unit_prompts=unit_prompts,
        adapter=adapter_name,
        attached_slots=sorted(item["platform_slot"] for item in attached),
        postproduction_audio=postproduction_audio,
        unit_postproduction_audio=unit_postproduction_audio,
        structural_score=structural_score(payload),
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
