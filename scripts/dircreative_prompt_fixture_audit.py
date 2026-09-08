#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from dircreative_prompt_compiler import (
    PromptContractError,
    compile_prompt,
    load_prompt_ir,
    semantic_errors,
    terminal_surface_errors,
)
from dircreative_adapters import get_adapter
from dircreative_model_capability_audit import REGISTRY_PATH, load_yaml


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/prompt-system"
VALID_ROOT = FIXTURE_ROOT / "valid"
INVALID_CASES = FIXTURE_ROOT / "invalid-cases.json"
ADAPTER_CASES = FIXTURE_ROOT / "adapter-cases.json"
ADAPTER_NEGATIVE_CASES = FIXTURE_ROOT / "adapter-negative-cases.json"
ADAPTER_CONTRACT_MATRIX = FIXTURE_ROOT / "adapter-contract-matrix.json"
MIRROR_ROOT = ROOT / "examples/seedance-mirror-turn-10s"


class AuditFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditFailure(message)


def read_json(path: Path) -> Any:
    require(path.is_file(), f"missing JSON fixture: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditFailure(f"invalid JSON fixture {path}: {exc}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_path(payload: Any, path: list[Any], value: Any) -> None:
    target = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def audit_valid_fixture(path: Path) -> dict[str, Any]:
    payload = load_prompt_ir(path)
    errors = semantic_errors(payload, verify_project_files=False)
    require(not errors, f"valid fixture failed {path.name}: {'; '.join(errors)}")
    result = compile_prompt(payload, verify_project_files=False)
    require(result.structural_score == payload["qa"]["structural_score"], f"computed score mismatch: {path.name}")
    require(not terminal_surface_errors(result.prompt, set(result.attached_slots) if result.adapter == "seedance" else set()), f"terminal surface leak: {path.name}")

    if payload["fixture_id"] == "minimal-character-scene-10s":
        require(len(payload["intake"]["supplied_assets"]) == 2, "minimal fixture must use character + scene only")
        require(len(result.attached_slots) == 2, "minimal fixture must attach exactly two references")
        require(not any(item["role"] in {"style_material", "storyboard_motion", "clean_start", "clean_end"} for item in payload["intake"]["supplied_assets"]), "minimal fixture added unnecessary planning assets")
    elif payload["fixture_id"] == "multi-character-assets-15s":
        require(len(payload["entities"]) == 3, "multi-entity fixture must contain two people and one product")
        speakers = [cue.get("speaker_entity_id") for shot in payload["shot_blocks"] for cue in shot["audio_cues"] if isinstance(cue, dict) and cue.get("kind") == "dialogue"]
        require(speakers == ["woman"], "dialogue speaker binding drifted")
        require(payload["entities"][2].get("owner_entity_id") == "woman", "case ownership must remain bound to the woman")
    elif payload["fixture_id"] == "longform-30s-split":
        units = payload["generation_plan"]["units"]
        require(len(units) == 3, "30-second fixture must split into three generation units")
        require(all(float(item["time_end"]) - float(item["time_start"]) <= 10 for item in units), "30-second fixture unit exceeds 10 seconds")
        require("30-second model" not in result.prompt.lower(), "fixture must not claim an unsupported 30-second model")
        require(len(result.unit_prompts) == 3, "30-second fixture must compile three pasteable unit prompts")
        require(all("10-second" in prompt and "30-second" not in prompt for prompt in result.unit_prompts), "unit prompts must request their actual ten-second duration")
        require(all("State continuity:" in prompt for prompt in result.unit_prompts), "unit prompts must carry incoming and outgoing state")
        require(all("00.00-10.00" in prompt for prompt in result.unit_prompts), "unit prompt timelines must be rebased to local time")
        require(all(result.unit_postproduction_audio), "post-production audio handoff must remain deliverable for every unit")
        require("standing beside the bicycle at home" not in result.unit_prompts[1], "later unit prompt leaked the global entity starting state")
        require("Begin with rider moving left to right with bag in basket" in result.unit_prompts[1], "later unit prompt did not inherit the exact prior outgoing state")

    return {
        "fixture_id": payload["fixture_id"],
        "duration_sec": payload["output"]["target_duration_sec"],
        "entities": len(payload["entities"]),
        "attached_references": len(result.attached_slots),
        "generation_units": len(payload["generation_plan"]["units"]),
        "computed_score": result.structural_score,
    }


def audit_invalid_cases() -> list[str]:
    cases = read_json(INVALID_CASES)
    require(isinstance(cases, list) and cases, "invalid case list must be non-empty")
    rejected: list[str] = []
    for case in cases:
        expected = case["expected"]
        if case["kind"] == "mutation":
            base_path = FIXTURE_ROOT / case["base"]
            payload = copy.deepcopy(read_json(base_path))
            if "mutations" in case:
                for mutation in case["mutations"]:
                    set_path(payload, mutation["path"], mutation["value"])
            else:
                set_path(payload, case["path"], case["value"])
            message = "; ".join(semantic_errors(payload, verify_project_files=bool(case.get("verify_project_files", False))))
        elif case["kind"] == "surface":
            message = "; ".join(terminal_surface_errors(case["text"], set(case["allowed_slots"])))
        else:
            raise AuditFailure(f"unknown invalid case kind: {case['kind']}")
        require(expected in message, f"negative fixture did not fail as expected: {case['case_id']}: {message}")
        rejected.append(case["case_id"])
    return rejected


def prepare_adapter_payload(case: dict[str, Any], cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = copy.deepcopy(read_json(FIXTURE_ROOT / case["base"]))
    minimum_reference_count = int(case.get("minimum_reference_count", 0))
    while len(payload["references"]) < minimum_reference_count:
        next_index = len(payload["references"]) + 1
        asset = copy.deepcopy(payload["intake"]["supplied_assets"][-1])
        asset["asset_id"] = f"adapter_extra_asset_{next_index}"
        payload["intake"]["supplied_assets"].append(asset)
        reference = copy.deepcopy(payload["references"][-1])
        reference["asset_id"] = asset["asset_id"]
        reference["platform_slot"] = f"adapter_reference_{next_index}"
        payload["references"].append(reference)

    payload["capability"]["model_key"] = case.get("capability_model_key", case["adapter"])
    payload["capability"]["capability_card_id"] = case["capability_card_id"]
    card = cards[case["capability_card_id"]]
    payload["capability"]["version"] = str(card["version"])
    payload["capability"]["provider_surface"] = card["provider_surface"]
    payload["generation_plan"]["selected_adapter"] = case["adapter"]
    target_duration = float(case["duration_sec"])
    payload["output"]["target_duration_sec"] = target_duration
    payload["output"]["generation_unit_sec"] = float(
        case.get("declared_generation_unit_sec", target_duration)
    )
    payload["generation_plan"]["units"][-1]["time_end"] = f"{target_duration:.2f}"
    payload["shot_blocks"][-1]["time_end"] = f"{target_duration:.2f}"
    platform_slot_type = case.get("platform_slot_type")
    platform_slots = (
        [f"@{platform_slot_type} {index}" for index in range(1, len(payload["references"]) + 1)]
        if platform_slot_type
        else case.get("platform_slots", [])
    )
    for index, reference in enumerate(payload["references"]):
        reference["attached_to_run"] = index < case["attached_reference_count"]
        reference["required_for_shot"] = reference["attached_to_run"]
        if index < len(platform_slots):
            reference["platform_slot"] = platform_slots[index]
    payload["audio_plan"]["generation_route"] = case["audio_route"]
    if case.get("inflate_path"):
        set_path(payload, case["inflate_path"], "x" * int(case["inflate_chars"]))
    return payload


def audit_adapter_cases() -> list[dict[str, Any]]:
    cases = read_json(ADAPTER_CASES)
    require(isinstance(cases, list) and cases, "adapter case list must be non-empty")
    results: list[dict[str, Any]] = []
    cards = {card["capability_card_id"]: card for card in load_yaml(REGISTRY_PATH).get("models", [])}
    for case in cases:
        payload = prepare_adapter_payload(case, cards)
        result = compile_prompt(payload, verify_project_files=False)
        require(case["expected_text"] in result.prompt, f"adapter fixture missing expected surface: {case['case_id']}")
        for forbidden in case["forbidden_text"]:
            inspected = result.prompt
            if forbidden == "Audio:" and payload["audio_plan"]["generation_route"] not in {"native", "reference_audio"}:
                from dircreative_video_quality import build_video_quality_prefix

                prefix = build_video_quality_prefix(payload) + "\n\n"
                # The requested quality structure explicitly declares silence.
                # Keep checking the concrete shot body for forbidden native cues.
                if inspected.startswith(prefix):
                    audio_line = next(line for line in prefix.splitlines() if line.startswith("Audio:"))
                    require(audio_line in {"Audio: silent picture; no generated audio.", "Audio: silent picture; sound is supplied separately."}, "non-native quality prefix requested audible output")
                    inspected = inspected[len(prefix):]
            require(forbidden not in inspected, f"adapter fixture leaked forbidden surface {forbidden}: {case['case_id']}")
        results.append({"case_id": case["case_id"], "adapter": case["adapter"], "attached_references": len(result.attached_slots)})
    return results


def audit_adapter_negative_cases() -> list[str]:
    cases = read_json(ADAPTER_NEGATIVE_CASES)
    require(isinstance(cases, list) and cases, "adapter negative case list must be non-empty")
    cards = {card["capability_card_id"]: card for card in load_yaml(REGISTRY_PATH).get("models", [])}
    rejected: list[str] = []
    for case in cases:
        if case["kind"] == "surface":
            message = "; ".join(
                get_adapter(case["adapter"]).surface_errors(case["text"], {"references": []})
            )
        elif case["kind"] == "compile":
            payload = prepare_adapter_payload(case, cards)
            try:
                compile_prompt(payload, verify_project_files=False)
            except PromptContractError as exc:
                message = str(exc)
            else:
                message = ""
        else:
            raise AuditFailure(f"unknown adapter negative case kind: {case['kind']}")
        require(case["expected"] in message, f"adapter negative fixture failed for wrong reason: {case['case_id']}: {message}")
        rejected.append(case["case_id"])

    adapters = {"seedance", "kling", "runway", "sora", "veo", "generic"}
    positive_coverage = {case["adapter"] for case in read_json(ADAPTER_CASES)}
    negative_coverage = {case["adapter"] for case in cases}
    require(positive_coverage == adapters, f"adapter positive coverage drifted: {sorted(positive_coverage)}")
    require(negative_coverage == adapters, f"adapter negative coverage drifted: {sorted(negative_coverage)}")
    for name in sorted(adapters):
        adapter = get_adapter(name)
        contract = adapter.CONTRACT
        require(contract.reference_count and contract.reference_syntax, f"{name} missing reference contract")
        require(contract.timeline_syntax and contract.multi_shot_support, f"{name} missing timeline/multi-shot contract")
        require(contract.camera_handling and contract.audio_handling, f"{name} missing camera/audio contract")
        require(contract.look_handling and contract.negative_handling, f"{name} missing look/negative contract")
        require(contract.unsupported_fields, f"{name} missing unsupported field contract")
        require(adapter.prompt_budget().max_chars > 0, f"{name} missing prompt budget")
        require(adapter.prompt_budget().compression_order, f"{name} missing compression order")
        for method in ("validate_capability", "compile_full", "compile_unit", "surface_errors", "prompt_budget"):
            require(callable(getattr(adapter, method, None)), f"{name} missing adapter interface method: {method}")
    return rejected


def adapter_contract_payload(
    adapter_name: str,
    *,
    attached_references: int,
    duration_sec: float,
    audio_route: str = "post_production",
) -> dict[str, Any]:
    references = [
        {
            "attached_to_run": True,
            "platform_slot": f"@Image {index}" if adapter_name == "seedance" else f"reference_{index}",
        }
        for index in range(1, attached_references + 1)
    ]
    return {
        "references": references,
        "generation_plan": {
            "units": [
                {
                    "time_start": "0.00",
                    "time_end": f"{duration_sec:.2f}",
                }
            ]
        },
        "audio_plan": {"generation_route": audio_route},
    }


def audit_adapter_contract_matrix() -> list[dict[str, Any]]:
    matrix = read_json(ADAPTER_CONTRACT_MATRIX)
    require(isinstance(matrix, list) and matrix, "adapter contract matrix must be non-empty")
    expected_adapters = {"seedance", "kling", "runway", "sora", "veo", "generic"}
    require({item.get("adapter") for item in matrix} == expected_adapters, "adapter contract matrix coverage drifted")
    positive_coverage = {case["adapter"] for case in read_json(ADAPTER_CASES)}
    results: list[dict[str, Any]] = []
    for row in matrix:
        name = row["adapter"]
        adapter = get_adapter(name)
        maximum = adapter.CONTRACT.maximum_references
        require(maximum is not None, f"{name} lacks a finite reference-count negative boundary")
        valid_payload = adapter_contract_payload(
            name,
            attached_references=0,
            duration_sec=float(row["valid_duration_sec"]),
        )
        require(not adapter.validate_capability(valid_payload), f"{name} valid capability fixture failed")

        overflow_payload = adapter_contract_payload(
            name,
            attached_references=maximum + 1,
            duration_sec=float(row["valid_duration_sec"]),
        )
        overflow_errors = "; ".join(adapter.validate_capability(overflow_payload))
        require(
            "reference count is unsupported" in overflow_errors,
            f"{name} did not reject invalid reference count: {overflow_errors}",
        )

        budget = adapter.prompt_budget()
        over_budget = "Timeline:\n00.00-01.00: " + ("x" * (budget.max_chars + 1))
        budget_errors = "; ".join(adapter.surface_errors(over_budget, {"references": []}))
        require("prompt_budget_exceeded" in budget_errors, f"{name} did not reject prompt budget overflow")
        timeline_errors = "; ".join(
            adapter.surface_errors("A camera follows the subject.", {"references": []})
        )
        require("timeline_syntax_invalid" in timeline_errors, f"{name} did not reject missing timeline")

        unsupported = row["unsupported"]
        unsupported_payload = adapter_contract_payload(
            name,
            attached_references=0,
            duration_sec=(
                float(unsupported["value"])
                if unsupported["kind"] == "duration"
                else float(row["valid_duration_sec"])
            ),
            audio_route="native" if unsupported["kind"] == "native_audio" else "post_production",
        )
        unsupported_errors = "; ".join(adapter.validate_capability(unsupported_payload))
        require(
            unsupported["expected"] in unsupported_errors,
            f"{name} did not reject unsupported capability: {unsupported_errors}",
        )
        results.append(
            {
                "adapter": name,
                "valid_prompt": name in positive_coverage,
                "invalid_reference_count_rejected": True,
                "prompt_budget_rejected": True,
                "timeline_rejected": True,
                "unsupported_capability_rejected": True,
            }
        )
    return results


def audit_mirror_fixture() -> dict[str, Any]:
    ir_path = MIRROR_ROOT / "prompt-ir.json"
    payload = load_prompt_ir(ir_path)
    project_file_assets = [
        asset
        for asset in payload["intake"]["supplied_assets"]
        if asset["source_kind"] == "project_file"
    ]
    project_files_present = all((ROOT / asset["source_locator"]).is_file() for asset in project_file_assets)
    result = compile_prompt(payload, verify_project_files=project_files_present)

    for asset in project_file_assets if project_files_present else []:
        source = ROOT / asset["source_locator"]
        require(source.is_file(), f"mirror fixture source missing: {source}")
        require(sha256(source) == asset["source_hash"], f"mirror fixture source hash mismatch: {asset['asset_id']}")

    attached = {item["platform_slot"] for item in payload["references"] if item["attached_to_run"]}
    planning = {item["platform_slot"] for item in payload["references"] if item["direct_input_policy"] == "planning_only"}
    require(attached == {"@Image 1", "@Image 2", "@Image 3"}, "mirror fixture must use only three direct references")
    require(not (attached & planning), "planning-only mirror references leaked into attached slots")
    require("@Video" not in result.prompt and "@Audio" not in result.prompt, "phantom media reference leaked into mirror prompt")

    prompt_path = MIRROR_ROOT / "prompts/video_seedance_2_0.txt"
    require(prompt_path.read_text(encoding="utf-8") == result.prompt, "checked-in mirror prompt is not compiler-derived")
    score = read_json(MIRROR_ROOT / "qa/prompt-score.json")
    require(score["scores"]["video_prompt"]["score"] == result.structural_score, "mirror prompt score is not compiler-derived")
    require(score["receipt"]["generation_route"] == "prompt_only", "mirror receipt must remain prompt-only")
    require(score["receipt"]["live_acceptance"] == "pending", "mirror receipt must keep live acceptance pending")
    for artifact_id, artifact_hash in zip(score["receipt"]["artifact_ids"], score["receipt"]["artifact_hashes"]):
        artifact_path = MIRROR_ROOT / artifact_id
        if not artifact_path.is_file():
            artifact_path = MIRROR_ROOT / "prompts" / artifact_id
        require(artifact_path.is_file(), f"mirror receipt artifact missing: {artifact_id}")
        require(sha256(artifact_path) == artifact_hash, f"mirror receipt hash mismatch: {artifact_id}")

    image_prompts = sorted((MIRROR_ROOT / "prompts").glob("image_*.txt"))
    require(len(image_prompts) == 6, "mirror fixture must preserve six authored image prompts")
    for path in image_prompts:
        text = path.read_text(encoding="utf-8")
        surface = terminal_surface_errors(text, set())
        require(not surface, f"image terminal prompt leaks internal production controls: {path.name}: {'; '.join(surface)}")

    return {
        "fixture_id": payload["fixture_id"],
        "supplied_assets": len(payload["intake"]["supplied_assets"]),
        "attached_references": len(result.attached_slots),
        "planning_references_not_attached": len(planning),
        "computed_score": result.structural_score,
        "external_generation_verified": False,
        "project_file_hash_check": "passed" if project_files_present else "skipped_optional_media_not_packaged",
    }


def audit() -> dict[str, Any]:
    valid_paths = sorted(VALID_ROOT.glob("*.json"))
    require(valid_paths, "no valid prompt-system fixtures found")
    valid = [audit_valid_fixture(path) for path in valid_paths]
    invalid = audit_invalid_cases()
    adapters = audit_adapter_cases()
    adapter_negative = audit_adapter_negative_cases()
    adapter_contract_matrix = audit_adapter_contract_matrix()
    mirror = audit_mirror_fixture()
    return {
        "status": "PASS",
        "schema": str((ROOT / "docs/film-preproduction/schemas/prompt-ir.schema.json").relative_to(ROOT)),
        "valid_fixtures": valid,
        "negative_fixtures_rejected": invalid,
        "adapter_fixtures": adapters,
        "adapter_negative_fixtures_rejected": adapter_negative,
        "adapter_contract_matrix": adapter_contract_matrix,
        "mirror_fixture": mirror,
        "boundaries": {
            "terminal_prompt_internal_ids": "rejected",
            "phantom_reference_slots": "rejected",
            "planning_only_direct_attachment": "rejected",
            "qa_retry_in_terminal_prompt": "rejected",
            "real_media_generation": "not_executed"
        }
    }


def main() -> int:
    try:
        result = audit()
    except (AuditFailure, PromptContractError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PROMPT_FIXTURE_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
