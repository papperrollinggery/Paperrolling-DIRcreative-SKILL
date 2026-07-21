#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "docs/film-preproduction/schemas/director-role-harness.yaml"
RESULT_PATH = ROOT / "docs/film-preproduction/schemas/director-room.yaml"
PERSPECTIVES = {"narrative_strategy", "visual_production", "model_continuity"}
LEGACY_ROLE_IDS = {
    "producer",
    "creative_director",
    "director",
    "screenwriter",
    "cinematographer",
    "production_designer",
    "editor",
    "sound_designer",
    "model_prompt_engineer",
    "continuity_qa",
}
LEGACY_FIXTURES = (
    "tests/fixtures/invalid-director-harness-missing-role-contract.yaml",
    "tests/fixtures/invalid-director-harness-role-contract-section-not-mapping.yaml",
    "tests/fixtures/invalid-director-harness-simple-request-escalated.yaml",
    "tests/fixtures/invalid-director-harness-role-list-only.yaml",
    "tests/fixtures/invalid-director-harness-duplicate-lane-seat.yaml",
    "tests/fixtures/invalid-director-harness-empty-role-card.yaml",
    "tests/fixtures/invalid-director-harness-recommendation.yaml",
    "tests/fixtures/invalid-director-harness-resolution.yaml",
    "tests/fixtures/invalid-director-harness-disagreement.yaml",
    "tests/fixtures/invalid-director-harness-explicit-threads-simulated.yaml",
    "tests/fixtures/invalid-director-harness-real-thread-evidence.yaml",
    "tests/fixtures/invalid-director-harness-orchestrated-worker-scope.yaml",
)
KNOWN_LEGACY_FIXTURE_TYPES = {
    "missing_role_contract",
    "role_contract_section_not_mapping",
    "simple_request_escalated",
    "role_list_only",
    "duplicate_lane_seat",
    "empty_role_card",
    "invalid_recommendation",
    "invalid_resolution",
    "invalid_disagreement",
    "explicit_threads_simulated",
    "real_thread_incomplete_evidence",
    "orchestrated_worker_scope",
}


def load_yaml(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(target)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"YAML parse failed for {target}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise RuntimeError(f"YAML top level must be a mapping: {target}")
    return data


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists() and path.endswith("/SKILL.md"):
        target = target.with_name("INTERNAL_SKILL.md")
    return target.read_text(encoding="utf-8")


def nonempty_strings(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item.strip() for item in value)


def selection_cases(harness: dict[str, Any]) -> list[dict[str, Any]]:
    policy = harness.get("selection_policy", {})
    cases = policy.get("cases", []) if isinstance(policy, dict) else []
    return [case for case in cases if isinstance(case, dict)]


def select_perspectives(request: str, harness: dict[str, Any]) -> dict[str, Any]:
    normalized = " ".join(request.split()).casefold()
    for case in selection_cases(harness):
        signals = case.get("signals", [])
        if any(isinstance(signal, str) and signal.casefold() in normalized for signal in signals):
            return {
                "mode": case.get("mode"),
                "director_room_used": case.get("director_room"),
                "selected_perspectives": case.get("perspectives", []),
                "optional_perspectives": case.get("optional_perspectives", []),
                "reason_code": case.get("id"),
            }
    return {
        "mode": "fast",
        "director_room_used": False,
        "selected_perspectives": [],
        "optional_perspectives": [],
        "reason_code": "no_director_room_evidence",
    }


def validate_harness(harness: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if harness.get("schema_version") != "2.0.0":
        failures.append("director harness schema_version must be 2.0.0")
    if harness.get("default_result_schema_version") != "2.0.0":
        failures.append("new director results must default to v2")

    perspectives = harness.get("perspectives")
    if not isinstance(perspectives, dict) or set(perspectives) != PERSPECTIVES:
        failures.append("director harness must define exactly three dynamic perspectives")
    else:
        for perspective_id, contract in perspectives.items():
            if not isinstance(contract, dict):
                failures.append(f"perspective {perspective_id} contract must be a mapping")
                continue
            for field in ("maps_from_roles", "handles", "outputs"):
                if not nonempty_strings(contract.get(field)):
                    failures.append(f"perspective {perspective_id} missing {field}")

    policy = harness.get("selection_policy")
    if not isinstance(policy, dict):
        failures.append("director harness missing selection_policy")
        policy = {}
    if policy.get("maximum_perspectives") != 3:
        failures.append("selection policy maximum_perspectives must be 3")
    if policy.get("director_room_only_for_studio") is not True:
        failures.append("Director Room must be limited to Studio")
    if policy.get("fast_uses_direct_judgments_without_council") is not True:
        failures.append("Fast must use direct judgments without Council")

    expected_cases = {
        "local_copy_revision": ("fast", False, ["narrative_strategy"]),
        "local_storyboard_review": ("fast", False, ["visual_production", "model_continuity"]),
        "complete_advertising_film": (
            "studio",
            True,
            ["narrative_strategy", "visual_production", "model_continuity"],
        ),
        "prompt_compilation": ("fast", False, ["visual_production", "model_continuity"]),
        "existing_script_local_revision": ("fast", False, ["narrative_strategy"]),
    }
    actual_cases = {case.get("id"): case for case in selection_cases(harness)}
    if set(actual_cases) != set(expected_cases):
        failures.append("director selection behavior cases drifted")
    for case_id, (mode, room_used, selected) in expected_cases.items():
        case = actual_cases.get(case_id, {})
        if (case.get("mode"), case.get("director_room"), case.get("perspectives")) != (
            mode,
            room_used,
            selected,
        ):
            failures.append(f"director selection case mismatch: {case_id}")
        if len(case.get("perspectives", [])) > 3:
            failures.append(f"director selection case exceeds three perspectives: {case_id}")
    for request in (
        "开发一支完整 TVC，交付脚本、分镜和视觉资产计划",
        "开发一支 60 秒 16:9 广播 TVC，覆盖全部镜头",
    ):
        selected = select_perspectives(request, harness)
        if (
            selected.get("mode") != "studio"
            or selected.get("director_room_used") is not True
            or selected.get("selected_perspectives")
            != ["narrative_strategy", "visual_production", "model_continuity"]
        ):
            failures.append(f"complete TVC request skipped adaptive Studio perspectives: {request}")

    execution = harness.get("v2_execution")
    if not isinstance(execution, dict):
        failures.append("director harness missing v2_execution")
    else:
        expected_execution = {
            "controlling_agents": 1,
            "threads_default": 0,
            "maximum_perspectives": 3,
            "independent_critics_max": 1,
            "nested_dispatch_allowed": False,
        }
        for field, expected in expected_execution.items():
            if execution.get(field) != expected:
                failures.append(f"v2 execution {field} must be {expected}")

    output = harness.get("v2_output_contract")
    if not isinstance(output, dict):
        failures.append("director harness missing v2_output_contract")
    else:
        expected_output = {
            "recommendation_first": True,
            "perspective_judgments_max": 3,
            "user_visible_role_cards": False,
            "minimum_disagreements": 0,
            "no_material_conflict_allowed": True,
            "disagreement_only_for_material_conflict": True,
            "numbered_options_only_when_user_requests_choice": True,
            "direct_revision_returns_revised_artifact": True,
        }
        for field, expected in expected_output.items():
            if output.get(field) != expected:
                failures.append(f"v2 output {field} must be {expected}")
        order = output.get("presentation_order", [])
        if not order or order[0] != "recommendation":
            failures.append("v2 output must present recommendation first")

    legacy = harness.get("legacy_read_only")
    if not isinstance(legacy, dict):
        failures.append("director harness missing v1 compatibility contract")
    else:
        if legacy.get("accepted_schema_version") != "1.0.0" or legacy.get("write_allowed") is not False:
            failures.append("legacy v1 compatibility must be read-only")
    legacy_roles = harness.get("legacy_v1_role_contracts")
    if not isinstance(legacy_roles, dict) or set(legacy_roles) != LEGACY_ROLE_IDS:
        failures.append("legacy v1 role contracts must preserve all ten role ids")
    legacy_execution = harness.get("legacy_v1_council_execution")
    if (
        not isinstance(legacy_execution, dict)
        or legacy_execution.get("compatibility_status") != "read_only"
        or legacy_execution.get("active_for_new_runs") is not False
    ):
        failures.append("fixed-seat v1 execution must be inactive and read-only")
    return failures


def validate_result_contract(root: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    if root.get("schema_version") != "2.0.0" or root.get("artifact_type") != "dynamic_perspective_result":
        failures.append("director-room result schema must default to dynamic v2")
    if root.get("default_for_new_runs") is not True:
        failures.append("director-room v2 must be default for new runs")
    legacy = root.get("legacy_v1_compatibility")
    if not isinstance(legacy, dict) or legacy.get("mode") != "read_only" or legacy.get("write_allowed") is not False:
        failures.append("director-room v1 compatibility must be read-only")
    elif set(legacy.get("fixed_role_ids", [])) != LEGACY_ROLE_IDS:
        failures.append("director-room v1 role id compatibility drifted")

    contract = root.get("result_contract")
    if not isinstance(contract, dict):
        failures.append("director-room v2 result_contract missing")
    else:
        if set(contract.get("perspective_ids", [])) != PERSPECTIVES:
            failures.append("director-room v2 perspective ids mismatch")
        if contract.get("maximum_perspectives") != 3 or contract.get("maximum_independent_critics") != 1:
            failures.append("director-room v2 perspective or critic budget drifted")

    example = root.get("canonical_example")
    if not isinstance(example, dict):
        return failures + ["director-room v2 canonical_example missing"], {}
    selected = example.get("selected_perspectives")
    if not isinstance(selected, list) or not set(selected).issubset(PERSPECTIVES) or len(selected) > 3:
        failures.append("canonical example selected perspectives invalid")
        selected = []
    judgments = example.get("perspective_judgments")
    if not isinstance(judgments, dict) or set(judgments) != set(selected):
        failures.append("canonical example judgments must match selected perspectives")
    if example.get("conflict_status") == "no_material_conflict" and example.get("disagreements") != []:
        failures.append("no_material_conflict must keep disagreements empty")
    if example.get("user_options_requested") is False and example.get("user_facing_options") != []:
        failures.append("unrequested user options must stay empty")
    order = example.get("presentation_order", [])
    if not order or order[0] != "recommendation":
        failures.append("canonical example must present recommendation first")
    execution = example.get("execution", {})
    if execution.get("threads_used") != 0 or execution.get("nested_dispatch_used") is not False:
        failures.append("canonical v2 example must use zero Threads and no nested dispatch")
    return failures, example


def validate_docs() -> list[str]:
    failures: list[str] = []
    required = {
        "skills/dircreative/director-room/SKILL.md": [
            "Fast tasks do not enter Director Room",
            "narrative_strategy",
            "visual_production",
            "model_continuity",
            "no_material_conflict",
            "Do not expose ten role cards",
        ],
        "docs/film-preproduction/director-room-routing.md": [
            "Director Room Adaptive Routing",
            "at most three perspectives",
            "There is no minimum disagreement count",
            "Existing script local revision",
            "Prompt compilation",
        ],
        "docs/film-preproduction/director-room-council-protocol.md": [
            "Adaptive Perspective Protocol",
            "Threads default to zero",
            "No fixed role count",
            "No minimum disagreement count",
            "recommendation or revised artifact first",
        ],
    }
    for path, terms in required.items():
        text = read(path)
        missing = [term for term in terms if term not in text]
        if missing:
            failures.append(f"{path} missing terms: {', '.join(missing)}")
    forbidden = (
        "at least two useful disagreements",
        "Each director room run must include these seats",
        "minimum_role_cards: 10",
        "minimum_disagreements: 2",
        "Default live mode is Codex Thread-backed",
    )
    for path in required:
        text = read(path)
        residuals = [term for term in forbidden if term in text]
        if residuals:
            failures.append(f"{path} retains active fixed-council wording: {', '.join(residuals)}")
    return failures


def readable_legacy_fixture(path: str | Path) -> tuple[bool, str]:
    data = load_yaml(path)
    fixture_type = data.get("fixture_type")
    expected = data.get("expected_failure_contains")
    expected_ok = isinstance(expected, str) and bool(expected.strip())
    expected_ok = expected_ok or (
        isinstance(expected, list) and bool(expected) and all(isinstance(item, str) and item.strip() for item in expected)
    )
    if fixture_type not in KNOWN_LEGACY_FIXTURE_TYPES:
        return False, f"unknown legacy fixture type: {fixture_type}"
    if not expected_ok:
        return False, "legacy invalid fixture lacks its expected failure contract"
    return True, str(fixture_type)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative v2 adaptive Director Room contracts.")
    parser.add_argument("--route", help="Select v2 professional perspectives for one request.")
    parser.add_argument("--verify-invalid-fixture", type=Path, help="Read one legacy v1 invalid fixture without rewriting it.")
    args = parser.parse_args()

    harness_root = load_yaml(HARNESS_PATH).get("director_role_harness", {})
    result_root = load_yaml(RESULT_PATH).get("director_room", {})
    if not isinstance(harness_root, dict) or not isinstance(result_root, dict):
        print("DIRECTOR_HARNESS_AUDIT: FAIL")
        print("- director harness or result root is unavailable")
        return 1

    if args.route is not None:
        print(json.dumps(select_perspectives(args.route, harness_root), ensure_ascii=False, indent=2))
        return 0
    if args.verify_invalid_fixture is not None:
        ok, detail = readable_legacy_fixture(args.verify_invalid_fixture)
        print(f"DIRECTOR_HARNESS_INVALID_FIXTURE: {'PASS' if ok else 'FAIL'}")
        print(f"legacy_v1_read_only: {str(ok).lower()}")
        print(f"detail: {detail}")
        return 0 if ok else 1

    harness_failures = validate_harness(harness_root)
    result_failures, example = validate_result_contract(result_root)
    docs_failures = validate_docs()
    legacy_failures: list[str] = []
    legacy_read = 0
    for path in LEGACY_FIXTURES:
        ok, detail = readable_legacy_fixture(path)
        if ok:
            legacy_read += 1
        else:
            legacy_failures.append(f"{path}: {detail}")

    cases = selection_cases(harness_root)
    fast_cases = [case for case in cases if case.get("mode") == "fast"]
    fast_bypasses = sum(case.get("director_room") is False for case in fast_cases)
    selected = example.get("selected_perspectives", []) if isinstance(example, dict) else []
    output = harness_root.get("v2_output_contract", {})
    print("DIRcreative Adaptive Director Harness Audit")
    print("=" * 72)
    print(f"schema_version: {harness_root.get('schema_version', '')}")
    print(f"dynamic_perspectives: {', '.join(sorted(PERSPECTIVES))}")
    print(f"selection_cases: {len(cases)}")
    print(f"fast_director_room_bypasses: {fast_bypasses}/{len(fast_cases)}")
    print(f"maximum_perspectives: {harness_root.get('selection_policy', {}).get('maximum_perspectives')}")
    print(f"minimum_disagreements: {output.get('minimum_disagreements')}")
    print(f"user_visible_role_cards: {str(output.get('user_visible_role_cards')).lower()}")
    print(f"canonical_selected_perspectives: {len(selected)}")
    print(f"canonical_conflict_status: {example.get('conflict_status', '') if isinstance(example, dict) else ''}")
    print(f"legacy_v1_fixtures_read: {legacy_read}/{len(LEGACY_FIXTURES)}")
    failures = harness_failures + result_failures + docs_failures + legacy_failures
    if failures:
        print("DIRECTOR_HARNESS_AUDIT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("DIRECTOR_HARNESS_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
