#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = "docs/film-preproduction/schemas/director-role-harness.yaml"
CANONICAL_RESULT_PATH = "docs/film-preproduction/schemas/director-room.yaml"
NEGATIVE_FIXTURES = (
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
REQUIRED_ROLE_IDS = {
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
REQUIRED_ROLE_FIELDS = (
    "responsibilities",
    "trigger_conditions",
    "inputs",
    "outputs",
    "evidence_and_tools",
    "professional_judgment",
    "prohibited_actions",
    "quality_gate",
    "handoff",
    "failure_and_retry",
)
REQUIRED_ROLE_SECTION_FIELDS = {
    "evidence_and_tools": ("evidence_required", "tools_or_sources"),
    "quality_gate": ("pass_conditions", "fail_when"),
    "handoff": ("to", "required_fields", "stop_condition"),
    "failure_and_retry": ("failure_signals", "smallest_retry", "stop_when"),
}
REQUIRED_ROLE_CARD_FIELDS = (
    "inputs",
    "evidence",
    "judgment",
    "quality",
    "handoff",
    "retry",
    "execution",
)
ROLE_CARD_FIELD_TYPES = {
    "inputs": "non_empty_string_list",
    "evidence": "non_empty_source_finding_list",
    "judgment": "non_empty_string",
    "quality": "typed_quality_mapping",
    "handoff": "typed_handoff_mapping",
    "retry": "typed_retry_mapping",
    "execution": "typed_execution_mapping",
}
REQUIRED_ROLE_CARD_SECTION_FIELDS = {
    "quality": ("status", "reasons"),
    "handoff": ("to", "payload"),
    "retry": ("failure_signals", "smallest_retry", "stop_condition"),
    "execution": ("lane_id", "mode"),
}
ROLE_LANE_MAP = {
    "producer": "production_image_lane",
    "creative_director": "creative_story_lane",
    "director": "creative_story_lane",
    "screenwriter": "creative_story_lane",
    "cinematographer": "production_image_lane",
    "production_designer": "production_image_lane",
    "editor": "production_image_lane",
    "sound_designer": "production_image_lane",
    "model_prompt_engineer": "model_continuity_lane",
    "continuity_qa": "model_continuity_lane",
}
REAL_THREAD_RECORD_FIELDS = (
    "lane_id",
    "thread_id",
    "thread_class",
    "dispatch_record",
    "worker_receipt",
    "adoption_decision",
    "cleanup_status",
)
REAL_THREAD_LANE_IDS = set(ROLE_LANE_MAP.values())
ALLOWED_QUALITY_STATUSES = {"pass", "needs_user", "blocked"}
ALLOWED_EXECUTION_MODES = {
    "codex_thread_role_lanes",
    "simulated_role_passes_fallback",
    "orchestrated_worker_handoff",
}
REQUIRED_RESULT_FIELDS = (
    "schema_version",
    "artifact_type",
    "automatic_routing_decision",
    "stage_gate",
    "execution",
    "open_questions",
    "role_cards",
    "discussion_rounds",
    "disagreements",
    "arbitration",
    "resolution_notes",
    "user_facing_options",
    "recommendation",
    "user_confirmation",
    "final_direction_locked",
)
REQUIRED_ROUTING_DECISION_ORDER = (
    "absolute_non_creation_exception",
    "complex_multi_artifact_request",
    "bounded_lightweight_request",
    "non_trivial_creative_request",
    "default",
)


def load_yaml(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    ruby = "require 'yaml'; require 'json'; data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); puts JSON.generate(data)"
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
        internal = target.with_name("INTERNAL_SKILL.md")
        if internal.exists():
            target = internal
    if not target.exists() and path == "skills/dircreative/SKILL.md" and (ROOT / "SKILL.md").exists():
        target = ROOT / "SKILL.md"
    return target.read_text(encoding="utf-8")


def nonempty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, (dict, list, tuple, set)) and bool(value)


def valid_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_string_list(value: Any, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(valid_string(item) for item in value)
    )


def valid_uuid(value: Any) -> bool:
    if not valid_string(value):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def contains_any(text: str, signals: Any) -> bool:
    if not isinstance(signals, list):
        return False
    lowered = text.casefold()
    return any(isinstance(signal, str) and signal.casefold() in lowered for signal in signals)


def distinct_artifact_group_count(text: str, routing: dict[str, Any]) -> int:
    policy = routing.get("complex_intent_policy")
    if not isinstance(policy, dict):
        return 0
    groups = policy.get("artifact_groups")
    if not isinstance(groups, dict):
        return 0
    return sum(1 for signals in groups.values() if contains_any(text, signals))


def matches_typed_lightweight_exception(
    text: str,
    routing: dict[str, Any],
    *,
    priority: str | None = None,
) -> bool:
    policy = routing.get("typed_lightweight_exceptions")
    if not isinstance(policy, dict):
        return False
    rules = policy.get("rules")
    if not isinstance(rules, list):
        return False
    lowered = text.casefold()
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("route") != "lightweight":
            continue
        rule_priority = rule.get("priority", "bounded")
        if priority is not None and rule_priority != priority:
            continue
        terms = rule.get("all_of")
        if isinstance(terms, list) and terms and all(
            isinstance(term, str) and term.casefold() in lowered for term in terms
        ):
            return True
    return False


def route_request(request: str, routing: dict[str, Any]) -> str:
    """Return the two stable routing outcomes used by the chat harness."""
    text = request.strip()
    # An explicit non-creation instruction is absolute. Other bounded semantic
    # exceptions are evaluated after the overall multi-artifact intent so that a
    # course/distribution subject cannot swallow a real promo + script + board job.
    if matches_typed_lightweight_exception(text, routing, priority="absolute_non_creation"):
        return "lightweight"

    has_domain = contains_any(text, routing.get("creative_domain_signals"))
    has_creation_intent = contains_any(text, routing.get("artifact_creation_intent_signals"))
    policy = routing.get("complex_intent_policy")
    minimum_groups = policy.get("minimum_distinct_artifact_groups") if isinstance(policy, dict) else None
    is_complex_multi_artifact = (
        isinstance(minimum_groups, int)
        and minimum_groups > 0
        and distinct_artifact_group_count(text, routing) >= minimum_groups
    )

    # Overall multi-artifact intent outranks incidental bounded words. A request for
    # an ad film + script + storyboard must not become lightweight merely because it
    # also asks for a title or one line of copy.
    if has_domain and has_creation_intent and is_complex_multi_artifact:
        return "director_room"
    if matches_typed_lightweight_exception(text, routing):
        return "lightweight"
    if contains_any(text, routing.get("lightweight_intent_signals")):
        return "lightweight"
    if contains_any(text, routing.get("single_point_question_signals")) and not has_creation_intent:
        return "lightweight"
    if has_domain and has_creation_intent:
        return "director_room"
    return "lightweight"


def validate_role_contracts(roles: Any, *, require_all_roles: bool) -> list[str]:
    failures: list[str] = []
    if not isinstance(roles, dict):
        return ["roles must be a mapping"]

    if require_all_roles:
        missing_roles = sorted(REQUIRED_ROLE_IDS - set(roles))
        unexpected_roles = sorted(set(roles) - REQUIRED_ROLE_IDS)
        if missing_roles:
            failures.append("role harness missing roles: " + ", ".join(missing_roles))
        if unexpected_roles:
            failures.append("role harness has unexpected roles: " + ", ".join(unexpected_roles))

    for role_id, role in roles.items():
        if not isinstance(role, dict):
            failures.append(f"role {role_id} must be a mapping")
            continue
        for field in REQUIRED_ROLE_FIELDS:
            if not nonempty(role.get(field)):
                failures.append(f"role {role_id} missing {field}")

        for section, required_fields in REQUIRED_ROLE_SECTION_FIELDS.items():
            section_value = role.get(section)
            if not isinstance(section_value, dict):
                failures.append(f"role {role_id} {section} must be a mapping")
                continue
            for field in required_fields:
                if not nonempty(section_value.get(field)):
                    failures.append(f"role {role_id} missing {section}.{field}")
    return failures


def validate_typed_lightweight_exceptions(policy: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(policy, dict):
        return ["routing typed_lightweight_exceptions must be a mapping"]
    if policy.get("schema_version") != "1.0.0":
        failures.append("routing typed_lightweight_exceptions schema_version must be 1.0.0")
    rules = policy.get("rules")
    if not isinstance(rules, list) or not rules:
        return failures + ["routing typed_lightweight_exceptions.rules must be a non-empty list"]
    for rule in rules:
        if not isinstance(rule, dict):
            failures.append("routing typed lightweight exception rule must be a mapping")
            continue
        if not nonempty(rule.get("exception_id")):
            failures.append("routing typed lightweight exception missing exception_id")
        terms = rule.get("all_of")
        if not isinstance(terms, list) or len(terms) < 2 or any(not isinstance(term, str) or not term for term in terms):
            failures.append("routing typed lightweight exception all_of must contain at least two terms")
        if rule.get("route") != "lightweight":
            failures.append("routing typed lightweight exception route must be lightweight")
        if rule.get("priority", "bounded") not in {"bounded", "absolute_non_creation"}:
            failures.append("routing typed lightweight exception priority is invalid")
        if not nonempty(rule.get("rationale")):
            failures.append("routing typed lightweight exception missing rationale")
    return failures


def validate_complex_intent_policy(policy: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(policy, dict):
        return ["routing complex_intent_policy must be a mapping"]
    if policy.get("schema_version") != "1.0.0":
        failures.append("routing complex_intent_policy schema_version must be 1.0.0")
    if policy.get("priority") != "before_generic_lightweight_signals":
        failures.append("complex multi-artifact intent must run before generic lightweight signals")
    minimum = policy.get("minimum_distinct_artifact_groups")
    if not isinstance(minimum, int) or minimum < 2:
        failures.append("complex_intent_policy minimum_distinct_artifact_groups must be at least 2")
    groups = policy.get("artifact_groups")
    if not isinstance(groups, dict) or len(groups) < 4:
        failures.append("complex_intent_policy artifact_groups must define at least four groups")
    else:
        for group_id, signals in groups.items():
            if not isinstance(group_id, str) or not group_id or not isinstance(signals, list) or not signals:
                failures.append("complex_intent_policy artifact groups must be named non-empty signal lists")
                continue
            if any(not isinstance(signal, str) or not signal.strip() for signal in signals):
                failures.append(f"complex_intent_policy artifact group {group_id} has an invalid signal")
    return failures


def routing_case_failures(case: Any, routing: dict[str, Any]) -> list[str]:
    if not isinstance(case, dict):
        return ["routing behavior case must be a mapping"]
    failures: list[str] = []
    case_id = case.get("id", "unknown")
    request = case.get("request")
    expected_route = case.get("expected_route")
    if not isinstance(request, str) or not request:
        return [f"routing case {case_id} missing request"]
    if expected_route not in {"director_room", "lightweight"}:
        failures.append(f"routing case {case_id} has invalid expected_route")
    actual_route = route_request(request, routing)
    if expected_route != actual_route:
        failures.append(f"routing case {case_id} expected {expected_route}, got {actual_route}")
    expected_stage = "阶段: 导演组会议" if actual_route == "director_room" else "轻量响应"
    if case.get("expected_stage") != expected_stage:
        failures.append(f"routing case {case_id} expected stage {expected_stage}")
    if actual_route == "director_room" and case.get("role_names_supplied_by_user") is not False:
        failures.append(f"routing case {case_id} does not prove automatic role entry")
    return failures


def validate_routing(routing: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(routing, dict):
        return ["routing must be a mapping"]
    if routing.get("default_route") != "lightweight":
        failures.append("routing default_route must be lightweight")
    if routing.get("role_naming_required") is not False:
        failures.append("routing must not require user-supplied role names")
    for field in (
        "decision_order",
        "creative_domain_signals",
        "artifact_creation_intent_signals",
        "lightweight_intent_signals",
        "single_point_question_signals",
        "typed_lightweight_exceptions",
        "complex_intent_policy",
        "behavior_cases",
    ):
        if not nonempty(routing.get(field)):
            failures.append(f"routing missing {field}")

    decision_order = routing.get("decision_order")
    decision_ids = [item.get("id") for item in decision_order if isinstance(item, dict)] if isinstance(
        decision_order, list
    ) else []
    if decision_ids != list(REQUIRED_ROUTING_DECISION_ORDER):
        failures.append("routing decision_order must preserve absolute-negation, complex-intent, bounded, creative, default priority")

    failures.extend(validate_typed_lightweight_exceptions(routing.get("typed_lightweight_exceptions")))
    failures.extend(validate_complex_intent_policy(routing.get("complex_intent_policy")))

    cases = routing.get("behavior_cases", [])
    if not isinstance(cases, list):
        return failures + ["routing behavior_cases must be a list"]
    case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids):
        failures.append("routing behavior case ids must be non-empty strings")
    if len(case_ids) != len(set(case_ids)):
        failures.append("routing behavior case ids must be unique")
    for case in cases:
        failures.extend(routing_case_failures(case, routing))
    return failures


def validate_role_cards(
    role_cards: Any,
    result_mode: str | None = None,
    thread_by_lane: dict[str, str] | None = None,
) -> list[str]:
    if not isinstance(role_cards, dict):
        return ["director-room result missing role_cards mapping"]
    failures: list[str] = []
    missing_roles = sorted(REQUIRED_ROLE_IDS - set(role_cards))
    unexpected_roles = sorted(set(role_cards) - REQUIRED_ROLE_IDS)
    if missing_roles:
        failures.append("director-room result missing role cards: " + ", ".join(missing_roles))
    if unexpected_roles:
        failures.append("director-room result has unknown role cards: " + ", ".join(unexpected_roles))

    expected_card_mode = {
        "codex_thread_role_lanes": "codex_thread_role_lane",
        "simulated_role_passes_fallback": "simulated_role_pass",
        "orchestrated_worker_handoff": "orchestrated_worker_handoff",
    }.get(result_mode)
    for role_id, card in role_cards.items():
        if not isinstance(card, dict) or not card:
            failures.append(f"role card {role_id} must be a non-empty mapping")
            continue
        for field in REQUIRED_ROLE_CARD_FIELDS:
            if not nonempty(card.get(field)):
                failures.append(f"role card {role_id} missing {field}")
        if not valid_string_list(card.get("inputs")):
            failures.append(f"role card {role_id} inputs must be a non-empty string list")
        if not valid_string(card.get("judgment")):
            failures.append(f"role card {role_id} judgment must be a non-empty string")
        evidence = card.get("evidence")
        if isinstance(evidence, list) and evidence:
            if any(
                not isinstance(item, dict)
                or not valid_string(item.get("source"))
                or not valid_string(item.get("finding"))
                for item in evidence
            ):
                failures.append(f"role card {role_id} evidence must contain source and finding")
        elif evidence is not None:
            failures.append(f"role card {role_id} evidence must be a non-empty list")

        for section, fields in REQUIRED_ROLE_CARD_SECTION_FIELDS.items():
            value = card.get(section)
            if not isinstance(value, dict):
                failures.append(f"role card {role_id} {section} must be a mapping")
                continue
            for field in fields:
                if not nonempty(value.get(field)):
                    failures.append(f"role card {role_id} missing {section}.{field}")
        quality = card.get("quality")
        if isinstance(quality, dict):
            if quality.get("status") not in ALLOWED_QUALITY_STATUSES:
                failures.append(f"role card {role_id} quality.status is invalid")
            if not valid_string_list(quality.get("reasons")):
                failures.append(f"role card {role_id} quality.reasons must be a non-empty string list")
        handoff = card.get("handoff")
        if isinstance(handoff, dict):
            if not valid_string_list(handoff.get("to")):
                failures.append(f"role card {role_id} handoff.to must be a non-empty string list")
            if not valid_string_list(handoff.get("payload")):
                failures.append(f"role card {role_id} handoff.payload must be a non-empty string list")
        retry = card.get("retry")
        if isinstance(retry, dict):
            if not valid_string_list(retry.get("failure_signals")):
                failures.append(f"role card {role_id} retry.failure_signals must be a non-empty string list")
            if not valid_string(retry.get("smallest_retry")):
                failures.append(f"role card {role_id} retry.smallest_retry must be a non-empty string")
            if not valid_string(retry.get("stop_condition")):
                failures.append(f"role card {role_id} retry.stop_condition must be a non-empty string")
        execution = card.get("execution")
        if isinstance(execution, dict):
            if not valid_string(execution.get("lane_id")) or not valid_string(execution.get("mode")):
                failures.append(f"role card {role_id} execution fields must be non-empty strings")
            if execution.get("lane_id") != ROLE_LANE_MAP.get(role_id):
                failures.append(f"role card {role_id} execution lane_id mismatch")
            if expected_card_mode and execution.get("mode") != expected_card_mode:
                failures.append(f"role card {role_id} execution mode mismatch")
            if result_mode == "codex_thread_role_lanes":
                expected_thread_id = (thread_by_lane or {}).get(ROLE_LANE_MAP.get(role_id, ""))
                if not valid_uuid(execution.get("thread_id")) or execution.get("thread_id") != expected_thread_id:
                    failures.append(f"role card {role_id} execution thread_id does not match its lane receipt")
    return failures


def validate_disagreements(disagreements: Any) -> tuple[list[str], set[str]]:
    failures: list[str] = []
    if not isinstance(disagreements, list) or len(disagreements) < 2:
        return ["director-room result missing two useful disagreements"], set()
    disagreement_ids: set[str] = set()
    for index, item in enumerate(disagreements):
        if not isinstance(item, dict):
            failures.append(f"director-room disagreement[{index}] must be a mapping")
            continue
        disagreement_id = item.get("disagreement_id")
        if not isinstance(disagreement_id, str) or not disagreement_id or disagreement_id in disagreement_ids:
            failures.append("director-room disagreements need unique non-empty disagreement_id values")
        else:
            disagreement_ids.add(disagreement_id)
        if not valid_string(item.get("topic")) or not valid_string(item.get("decision_pressure")):
            failures.append(f"director-room disagreement {disagreement_id or index} missing topic or decision_pressure")
        positions = item.get("positions")
        if not isinstance(positions, list) or len(positions) < 2:
            failures.append(f"director-room disagreement {disagreement_id or index} needs two typed positions")
            continue
        role_ids: list[str] = []
        statements: list[str] = []
        for position in positions:
            if not isinstance(position, dict):
                failures.append(f"director-room disagreement {disagreement_id or index} position must be a mapping")
                continue
            role_id = position.get("role_id")
            statement = position.get("position")
            if (
                not isinstance(role_id, str)
                or role_id not in REQUIRED_ROLE_IDS
                or not isinstance(statement, str)
                or not statement.strip()
                or not valid_string(position.get("evidence_ref"))
            ):
                failures.append(
                    f"director-room disagreement {disagreement_id or index} positions need a known role, position, and evidence_ref"
                )
                continue
            role_ids.append(role_id)
            statements.append(statement.strip())
        if len(role_ids) != len(set(role_ids)) or len(statements) != len(set(statements)):
            failures.append(f"director-room disagreement {disagreement_id or index} positions must be distinct")
    return failures, disagreement_ids


def validate_arbitration(arbitration: Any, disagreement_ids: set[str]) -> tuple[list[str], set[str]]:
    failures: list[str] = []
    if not isinstance(arbitration, list) or not arbitration:
        return ["director-room result missing arbitration"], set()
    arbitration_ids: set[str] = set()
    for index, item in enumerate(arbitration):
        if not isinstance(item, dict):
            failures.append(f"director-room arbitration[{index}] must be a mapping")
            continue
        arbitration_id = item.get("arbitration_id")
        if not isinstance(arbitration_id, str) or not arbitration_id or arbitration_id in arbitration_ids:
            failures.append("director-room arbitration needs unique non-empty arbitration_id values")
        else:
            arbitration_ids.add(arbitration_id)
        source_disagreement_id = item.get("disagreement_id")
        if not isinstance(source_disagreement_id, str) or source_disagreement_id not in disagreement_ids:
            failures.append(f"director-room arbitration {arbitration_id or index} references an unknown disagreement")
        for field in ("ruling", "rationale", "downstream_owner"):
            if not valid_string(item.get(field)):
                failures.append(f"director-room arbitration {arbitration_id or index} missing {field}")
    return failures, arbitration_ids


def validate_resolution_notes(
    resolution_notes: Any,
    disagreement_ids: set[str],
    arbitration_ids: set[str],
) -> tuple[list[str], set[str]]:
    failures: list[str] = []
    if not isinstance(resolution_notes, list) or len(resolution_notes) < 2:
        return ["director-room result missing two typed resolution_notes"], set()
    resolution_ids: set[str] = set()
    for index, item in enumerate(resolution_notes):
        if not isinstance(item, dict):
            failures.append(f"director-room resolution[{index}] must be a mapping")
            continue
        resolution_id = item.get("resolution_id")
        if not isinstance(resolution_id, str) or not resolution_id or resolution_id in resolution_ids:
            failures.append("director-room resolutions need unique non-empty resolution_id values")
        else:
            resolution_ids.add(resolution_id)
        source_ids = item.get("source_disagreement_ids")
        if (
            not isinstance(source_ids, list)
            or not source_ids
            or any(not isinstance(source_id, str) or source_id not in disagreement_ids for source_id in source_ids)
        ):
            failures.append(f"director-room resolution {resolution_id or index} references an unknown disagreement")
        arbitration_id = item.get("arbitration_id")
        if not isinstance(arbitration_id, str) or arbitration_id not in arbitration_ids:
            failures.append(f"director-room resolution {resolution_id or index} references an unknown arbitration")
        for field in ("production_rule", "rationale", "downstream_owner", "handoff_effect"):
            if not valid_string(item.get(field)):
                failures.append(f"director-room resolution {resolution_id or index} missing {field}")
    return failures, resolution_ids


def validate_user_facing_options(options: Any) -> tuple[list[str], set[str]]:
    failures: list[str] = []
    if not isinstance(options, list) or not 2 <= len(options) <= 3:
        return ["director-room result needs two or three user_facing_options"], set()
    option_ids: set[str] = set()
    required_fields = (
        "option_id",
        "concept_name",
        "one_line_story",
        "visual_promise",
        "why_it_works",
        "tradeoff",
        "production_risk",
        "reference_pack_implication",
    )
    for option in options:
        if not isinstance(option, dict) or any(not valid_string(option.get(field)) for field in required_fields):
            failures.append("director-room option lacks typed story, rationale, tradeoff, risk, or reference implication")
            continue
        option_id = option.get("option_id")
        if not isinstance(option_id, str):
            failures.append("director-room option_id values must be non-empty strings")
            continue
        if option_id in option_ids:
            failures.append("director-room option_id values must be unique")
        option_ids.add(option_id)
    return failures, option_ids


def validate_recommendation(recommendation: Any, option_ids: set[str], resolution_ids: set[str]) -> list[str]:
    if not isinstance(recommendation, dict) or not recommendation:
        return ["director-room result missing recommendation mapping"]
    failures: list[str] = []
    option_id = recommendation.get("option_id")
    if not isinstance(option_id, str) or option_id not in option_ids:
        failures.append("director-room recommendation option_id must reference a user-facing option")
    if not valid_string(recommendation.get("reason")):
        failures.append("director-room recommendation missing reason")
    if not valid_string_list(recommendation.get("evidence_refs")):
        failures.append("director-room recommendation missing evidence_refs")
    refs = recommendation.get("resolution_refs")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in resolution_ids for ref in refs):
        failures.append("director-room recommendation resolution_refs must reference valid resolutions")
    return failures


def validate_result_execution(execution: Any, open_questions: Any) -> list[str]:
    if not isinstance(execution, dict):
        return ["director-room result missing execution mapping"]
    failures: list[str] = []
    context = execution.get("context")
    mode = execution.get("mode")
    explicit_threads = execution.get("explicit_true_threads_requested")
    if context not in {"standalone_chat", "orchestrated_worker"}:
        failures.append("director-room execution context is invalid")
    if mode not in ALLOWED_EXECUTION_MODES:
        failures.append("director-room execution mode is invalid")
    if not isinstance(explicit_threads, bool):
        failures.append("director-room execution explicit_true_threads_requested must be boolean")
    if not isinstance(open_questions, list):
        failures.append("director-room result missing open_questions list")
    if execution.get("nested_dispatch") is not False:
        failures.append("director-room execution must record nested_dispatch false")

    thread_records = execution.get("thread_records")
    if explicit_threads is True and mode != "codex_thread_role_lanes":
        failures.append("explicit true Threads cannot use simulated or orchestrated fallback")
    if mode == "codex_thread_role_lanes":
        if context != "standalone_chat":
            failures.append("real director-room lane dispatch is owned by standalone_chat controller only")
        if not isinstance(thread_records, list) or not thread_records:
            failures.append("real Threads execution requires thread records")
        else:
            thread_ids: set[str] = set()
            lane_ids: set[str] = set()
            for index, record in enumerate(thread_records):
                if not isinstance(record, dict):
                    failures.append(f"real Threads record[{index}] must be a mapping")
                    continue
                for field in REAL_THREAD_RECORD_FIELDS:
                    if not valid_string(record.get(field)):
                        failures.append(f"real Threads record[{index}] missing {field}")
                thread_id = record.get("thread_id")
                if valid_string(thread_id):
                    if not valid_uuid(thread_id):
                        failures.append(f"real Threads record[{index}] thread_id must be a UUID")
                    elif thread_id in thread_ids:
                        failures.append(f"real Threads record[{index}] thread_id must be unique")
                    else:
                        thread_ids.add(thread_id)
                lane_id = record.get("lane_id")
                if valid_string(lane_id):
                    if lane_id not in REAL_THREAD_LANE_IDS:
                        failures.append(f"real Threads record[{index}] lane_id is invalid")
                    elif lane_id in lane_ids:
                        failures.append(f"real Threads record[{index}] lane_id must be unique")
                    else:
                        lane_ids.add(lane_id)
                adoption_decision = record.get("adoption_decision")
                if valid_string(adoption_decision) and adoption_decision not in {"adopted", "rejected", "deferred"}:
                    failures.append(f"real Threads record[{index}] adoption_decision is invalid")
                cleanup_status = record.get("cleanup_status")
                if valid_string(cleanup_status) and cleanup_status not in {"archived", "retained_reusable", "cleanup_complete"}:
                    failures.append(f"real Threads record[{index}] cleanup_status is invalid")
            missing_lanes = sorted(REAL_THREAD_LANE_IDS - lane_ids)
            if missing_lanes:
                failures.append("real Threads execution missing lane records: " + ", ".join(missing_lanes))
    elif mode == "simulated_role_passes_fallback":
        if context != "standalone_chat":
            failures.append("simulated role passes are allowed only in standalone_chat")
        if explicit_threads is not False:
            failures.append("simulated role passes require explicit_true_threads_requested false")
        if execution.get("standalone_small_gate") is not True:
            failures.append("simulated role passes require a standalone small gate")
        if execution.get("durable_artifact_work") is not False:
            failures.append("simulated role passes cannot perform durable artifact work")
        if not valid_string(execution.get("fallback_reason")):
            failures.append("simulated role passes require a fallback_reason")
        if thread_records not in ([], None):
            failures.append("simulated role passes cannot claim real thread records")
    elif mode == "orchestrated_worker_handoff":
        selected = execution.get("handoff_selected_subskill")
        executed = execution.get("executed_subskills")
        if context != "orchestrated_worker":
            failures.append("orchestrated_worker_handoff mode requires orchestrated_worker context")
        if not valid_string(selected) or executed != [selected]:
            failures.append("orchestrated_worker must execute only the handoff-selected subskill")
        if isinstance(open_questions, list) and any(
            not isinstance(question, dict)
            or not valid_string(question.get("question"))
            or question.get("decision_owner") != "adco"
            for question in open_questions
        ):
            failures.append("orchestrated_worker open_questions must be structured ADCO decision requests")
        if thread_records not in ([], None):
            failures.append("orchestrated_worker forbids nested director-room thread dispatch")
    return failures


def validate_council_result(result: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(result, dict):
        return ["director-room result must be a mapping"]
    missing_result_fields = [field for field in REQUIRED_RESULT_FIELDS if field not in result]
    if missing_result_fields:
        failures.append("director-room result missing fields: " + ", ".join(missing_result_fields))
    if result.get("schema_version") != "2.0.0":
        failures.append("director-room result schema_version must be 2.0.0")
    if result.get("artifact_type") != "canonical_typed_council_result":
        failures.append("director-room result artifact_type must be canonical_typed_council_result")
    if result.get("automatic_routing_decision") != "director_room":
        failures.append("director-room result automatic_routing_decision must be director_room")
    stage_gate = result.get("stage_gate")
    if (
        not isinstance(stage_gate, dict)
        or stage_gate.get("type") != "idea"
        or stage_gate.get("status") != "needs_user"
        or stage_gate.get("decision_owner") not in {"user", "simulated_fixture", "controller"}
    ):
        failures.append("director-room result stage_gate must be a typed needs_user idea gate")

    execution = result.get("execution")
    mode = execution.get("mode") if isinstance(execution, dict) else None
    failures.extend(validate_result_execution(execution, result.get("open_questions")))
    thread_by_lane: dict[str, str] = {}
    thread_records = execution.get("thread_records") if isinstance(execution, dict) else None
    if isinstance(thread_records, list):
        thread_by_lane = {
            record["lane_id"]: record["thread_id"]
            for record in thread_records
            if isinstance(record, dict)
            and valid_string(record.get("lane_id"))
            and valid_string(record.get("thread_id"))
        }
    failures.extend(validate_role_cards(result.get("role_cards"), mode, thread_by_lane))

    discussion_rounds = result.get("discussion_rounds")
    required_round_ids = {"role_brief_read", "disagreement_and_pressure_test", "resolution"}
    if not isinstance(discussion_rounds, list) or len(discussion_rounds) < 3:
        failures.append("director-room result missing discussion_rounds")
    else:
        round_ids = {
            item.get("round_id")
            for item in discussion_rounds
            if isinstance(item, dict) and valid_string(item.get("round_id"))
        }
        if not required_round_ids.issubset(round_ids):
            failures.append("director-room result missing required typed discussion rounds")
        for item in discussion_rounds:
            if (
                not isinstance(item, dict)
                or not valid_string_list(item.get("participants"))
                or not valid_string(item.get("result"))
            ):
                failures.append("director-room discussion rounds need participants and result")
                break

    disagreement_failures, disagreement_ids = validate_disagreements(result.get("disagreements"))
    failures.extend(disagreement_failures)
    arbitration_failures, arbitration_ids = validate_arbitration(result.get("arbitration"), disagreement_ids)
    failures.extend(arbitration_failures)
    resolution_failures, resolution_ids = validate_resolution_notes(
        result.get("resolution_notes"), disagreement_ids, arbitration_ids
    )
    failures.extend(resolution_failures)
    option_failures, option_ids = validate_user_facing_options(result.get("user_facing_options"))
    failures.extend(option_failures)
    failures.extend(validate_recommendation(result.get("recommendation"), option_ids, resolution_ids))

    confirmation = result.get("user_confirmation")
    allowed_option_ids = confirmation.get("allowed_option_ids") if isinstance(confirmation, dict) else None
    if (
        not isinstance(confirmation, dict)
        or confirmation.get("status") != "needs_user"
        or not valid_string(confirmation.get("question"))
        or not isinstance(allowed_option_ids, list)
        or any(not isinstance(option_id, str) for option_id in allowed_option_ids)
        or set(allowed_option_ids) != option_ids
    ):
        failures.append("director-room result missing a valid needs_user confirmation")
    if result.get("final_direction_locked") is not False:
        failures.append("director-room result must leave final direction unlocked before user choice")
    return failures


def validate_default_lanes(lanes: Any) -> list[str]:
    if not isinstance(lanes, list) or len(lanes) != 3:
        return ["council_execution must define three bounded default lanes"]

    failures: list[str] = []
    seat_counts: dict[str, int] = {}
    for position, lane in enumerate(lanes):
        if not isinstance(lane, dict):
            failures.append(f"council_execution default_lanes[{position}] must be a mapping")
            continue
        if not nonempty(lane.get("lane_id")):
            failures.append(f"council_execution default_lanes[{position}] missing lane_id")
        seats = lane.get("seats")
        if not isinstance(seats, list) or not seats:
            failures.append(f"council_execution default_lanes[{position}] seats must be a non-empty list")
            continue
        for seat in seats:
            if not isinstance(seat, str) or not seat:
                failures.append(f"council_execution default_lanes[{position}] has an invalid seat")
                continue
            seat_counts[seat] = seat_counts.get(seat, 0) + 1

    missing = sorted(REQUIRED_ROLE_IDS - set(seat_counts))
    unexpected = sorted(set(seat_counts) - REQUIRED_ROLE_IDS)
    duplicates = sorted(seat for seat, count in seat_counts.items() if count != 1)
    if missing:
        failures.append("council_execution lane seats missing required role: " + ", ".join(missing))
    if unexpected:
        failures.append("council_execution lane seats contain unknown role: " + ", ".join(unexpected))
    for seat in duplicates:
        failures.append(f"council_execution lane seat appears more than once: {seat}")
    return failures


def validate_thread_unavailable_policy(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["council_execution thread_unavailable_policy must be a mapping"]
    failures: list[str] = []
    explicit = policy.get("explicit_true_threads_requested")
    if not isinstance(explicit, dict):
        failures.append("thread_unavailable_policy missing explicit_true_threads_requested")
    else:
        if explicit.get("outcome") != "TOOL_BLOCKED":
            failures.append("explicit true Threads request must return TOOL_BLOCKED when unavailable")
        if explicit.get("simulated_fallback_allowed") is not False:
            failures.append("explicit true Threads request must forbid simulated fallback")
        if explicit.get("required_mode_when_available") != "codex_thread_role_lanes":
            failures.append("explicit true Threads request must require codex_thread_role_lanes when available")
        if explicit.get("required_evidence") != list(REAL_THREAD_RECORD_FIELDS):
            failures.append("explicit true Threads evidence must cover thread/dispatch/receipt/adoption/cleanup")
    ordinary = policy.get("ordinary_fallback")
    if not isinstance(ordinary, dict) or ordinary.get("outcome") != "simulated_role_passes_fallback":
        failures.append("thread_unavailable_policy missing ordinary simulated fallback contract")
    else:
        if ordinary.get("allowed_execution_context") != "standalone_chat":
            failures.append("ordinary simulated fallback must be standalone_chat only")
        if ordinary.get("small_chat_only_gate") is not True:
            failures.append("ordinary simulated fallback must be limited to a small chat-only gate")
        if ordinary.get("durable_artifact_work_allowed") is not False:
            failures.append("ordinary simulated fallback must forbid durable artifact work")
        if ordinary.get("explicit_true_threads_requested") is not False:
            failures.append("ordinary simulated fallback must require no explicit true Threads request")
        if ordinary.get("fallback_reason_required") is not True:
            failures.append("ordinary simulated fallback must require fallback_reason")
    return failures


def validate_execution_context_policy(policy: Any) -> list[str]:
    if not isinstance(policy, dict):
        return ["council_execution execution_context_policy must be a mapping"]
    failures: list[str] = []
    standalone = policy.get("standalone_chat")
    if not isinstance(standalone, dict):
        failures.append("execution_context_policy missing standalone_chat")
    else:
        if standalone.get("controller_owns_dispatch_adoption_cleanup") is not True:
            failures.append("standalone_chat controller must own dispatch/adoption/cleanup")
    orchestrated = policy.get("orchestrated_worker")
    if not isinstance(orchestrated, dict):
        failures.append("execution_context_policy missing orchestrated_worker")
    else:
        if orchestrated.get("nested_dispatch_allowed") is not False:
            failures.append("orchestrated_worker must forbid nested dispatch")
        if orchestrated.get("only_handoff_selected_subskill") is not True:
            failures.append("orchestrated_worker must execute only the handoff-selected subskill")
        if orchestrated.get("open_questions_required") is not True:
            failures.append("orchestrated_worker must return open_questions")
        if orchestrated.get("controller_owns_adoption_cleanup") != "adco":
            failures.append("orchestrated_worker adoption and cleanup owner must be adco")
    return failures


def validate_harness(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    harness = data.get("director_role_harness")
    if not isinstance(harness, dict):
        return ["director_role_harness root mapping missing"]
    if harness.get("schema_version") != "1.0.0":
        failures.append("director role harness schema_version must be 1.0.0")

    routing = harness.get("routing")
    failures.extend(validate_routing(routing))
    failures.extend(validate_role_contracts(harness.get("roles"), require_all_roles=True))

    council = harness.get("council_execution")
    if not isinstance(council, dict):
        failures.append("council_execution missing")
    else:
        if council.get("entry_stage") != "阶段: 导演组会议":
            failures.append("council_execution must enter 阶段: 导演组会议")
        failures.extend(validate_default_lanes(council.get("default_lanes")))
        failures.extend(validate_thread_unavailable_policy(council.get("thread_unavailable_policy")))
        failures.extend(validate_execution_context_policy(council.get("execution_context_policy")))
        contract = council.get("output_contract")
        if not isinstance(contract, dict):
            failures.append("council_execution missing output_contract")
        else:
            for field in (
                "role_cards_required",
                "discussion_rounds_required",
                "disagreements_required",
                "arbitration_required",
                "resolution_notes_required",
                "user_facing_options_required",
                "user_confirmation_required",
                "open_questions_required",
                "typed_role_cards_required",
            ):
                if contract.get(field) is not True:
                    failures.append(f"council output_contract must set {field} true")
            if contract.get("final_direction_locked_before_user_choice") is not False:
                failures.append("council output_contract must keep final direction unlocked before user choice")
            if contract.get("minimum_role_cards") != 10:
                failures.append("council output_contract minimum_role_cards must be 10")
            if contract.get("minimum_disagreements") != 2:
                failures.append("council output_contract minimum_disagreements must be 2")
            if contract.get("minimum_user_facing_options") != 2 or contract.get("maximum_user_facing_options") != 3:
                failures.append("council output_contract user-facing option range must be two to three")
        if not nonempty(council.get("retry_contract")):
            failures.append("council_execution missing retry_contract")
    canonical = harness.get("canonical_council_result")
    if not isinstance(canonical, dict):
        failures.append("director role harness missing canonical_council_result reference")
    else:
        if canonical.get("path") != CANONICAL_RESULT_PATH:
            failures.append("canonical_council_result path must point to director-room.yaml")
        if canonical.get("root_key") != "director_room.canonical_example":
            failures.append("canonical_council_result root_key mismatch")
        if canonical.get("schema_version") != "2.0.0":
            failures.append("canonical_council_result schema_version must be 2.0.0")
    return failures


def validate_canonical_file(data: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    root = data.get("director_room")
    if not isinstance(root, dict):
        return ["director-room.yaml missing director_room mapping"], {}
    if root.get("schema_version") != "2.0.0":
        failures.append("director-room.yaml schema_version must be 2.0.0")
    if root.get("artifact_type") != "canonical_typed_council_result":
        failures.append("director-room.yaml must own the canonical typed council result")
    contract = root.get("canonical_result_contract")
    if not isinstance(contract, dict):
        failures.append("director-room.yaml missing canonical_result_contract")
    else:
        if set(contract.get("required_role_ids", [])) != REQUIRED_ROLE_IDS:
            failures.append("canonical result contract required_role_ids mismatch")
        if contract.get("required_result_fields") != list(REQUIRED_RESULT_FIELDS):
            failures.append("canonical result contract required_result_fields mismatch")
        role_card = contract.get("role_card")
        if not isinstance(role_card, dict):
            failures.append("canonical result contract missing role_card")
        else:
            if role_card.get("required_fields") != list(REQUIRED_ROLE_CARD_FIELDS):
                failures.append("canonical role_card required_fields mismatch")
            if role_card.get("field_types") != ROLE_CARD_FIELD_TYPES:
                failures.append("canonical role_card field_types mismatch")
            if role_card.get("conditional_execution_fields") != {"codex_thread_role_lane": ["thread_id"]}:
                failures.append("canonical role_card conditional thread execution fields mismatch")
            if set(role_card.get("quality_statuses", [])) != ALLOWED_QUALITY_STATUSES:
                failures.append("canonical role_card quality_statuses mismatch")
        execution = contract.get("execution")
        if not isinstance(execution, dict):
            failures.append("canonical result contract missing execution")
        else:
            if set(execution.get("allowed_modes", [])) != ALLOWED_EXECUTION_MODES:
                failures.append("canonical execution allowed_modes mismatch")
            real_threads = execution.get("real_threads")
            if not isinstance(real_threads, dict) or real_threads.get("required_record_fields") != list(
                REAL_THREAD_RECORD_FIELDS
            ):
                failures.append("canonical real Threads contract must require thread/dispatch/receipt/adoption/cleanup")
            simulated = execution.get("simulated")
            if (
                not isinstance(simulated, dict)
                or simulated.get("allowed_context") != "standalone_chat"
                or simulated.get("small_chat_only_gate") is not True
                or simulated.get("durable_artifact_work_allowed") is not False
                or simulated.get("explicit_true_threads_requested") is not False
            ):
                failures.append("canonical simulated execution boundary mismatch")
            orchestrated = execution.get("orchestrated_worker")
            if (
                not isinstance(orchestrated, dict)
                or orchestrated.get("nested_dispatch_allowed") is not False
                or orchestrated.get("only_handoff_selected_subskill") is not True
                or orchestrated.get("open_questions_required") is not True
            ):
                failures.append("canonical orchestrated_worker boundary mismatch")
    example = root.get("canonical_example")
    failures.extend(validate_council_result(example))
    return failures, example if isinstance(example, dict) else {}


def validate_docs() -> list[str]:
    failures: list[str] = []
    required_terms = {
        "skills/dircreative/SKILL.md": (
            "dircreative_route.py",
            "source_maintenance",
            "Fast",
            "Studio",
            "Delivery",
            "zero unconditional protocol reads",
            "open_questions",
        ),
        "skills/dircreative/runtime/routing-policy.yaml": (
            "director-room-routing.md",
            "director-role-harness.yaml",
            "fast-task.md",
            "studio-development.md",
            "delivery-audit.md",
        ),
        "skills/dircreative/director-room/SKILL.md": (
            "Automatic Entry And Role Harness",
            "director-role-harness.yaml",
            "The user does not need to name Producer, Director",
            "at least two useful disagreements",
            "arbitration/ruling",
            "TOOL_BLOCKED",
            "canonical typed council result",
            "screenwriter",
        ),
        "docs/film-preproduction/director-room-council-protocol.md": (
            "Automatic Entry Routing",
            "director-room-routing.md",
            "director-role-harness.yaml",
            "arbitration/ruling",
            "lightweight path",
            "TOOL_BLOCKED",
            "director-room.yaml",
            "worker receipt",
            "cleanup",
        ),
        "docs/film-preproduction/director-room-routing.md": (
            "Director-Room Automatic Routing",
            "Do not ask the user to name Producer",
            "lightweight exceptions",
            "at least two useful disagreements",
            "arbitration/ruling",
            "typed lightweight exceptions",
            "TOOL_BLOCKED",
            "multi-artifact intent",
            "director-room.yaml",
        ),
        "docs/film-preproduction/schemas/director-room.yaml": (
            "canonical_typed_council_result",
            "inputs",
            "evidence",
            "judgment",
            "quality",
            "handoff",
            "retry",
            "execution",
            "screenwriter",
            "open_questions",
        ),
    }
    for path, terms in required_terms.items():
        text = read(path)
        lowered = text.casefold()
        missing = [term for term in terms if term.casefold() not in lowered]
        if missing:
            failures.append(f"{path} missing terms: {', '.join(missing)}")
    return failures


def validate_invalid_fixture(data: dict[str, Any], routing: dict[str, Any]) -> list[str]:
    fixture_type = data.get("fixture_type")
    if fixture_type == "missing_role_contract":
        return validate_role_contracts(data.get("roles"), require_all_roles=False)
    if fixture_type == "role_contract_section_not_mapping":
        return validate_role_contracts(data.get("roles"), require_all_roles=False)
    if fixture_type == "simple_request_escalated":
        case = data.get("routing_case")
        if not isinstance(case, dict):
            return ["invalid simple-request fixture missing routing_case"]
        request = case.get("request")
        declared_route = case.get("declared_route")
        if not isinstance(request, str):
            return ["invalid simple-request fixture routing_case missing request"]
        actual_route = route_request(request, routing)
        if actual_route != "lightweight":
            return [f"simple request classifier returned {actual_route}"]
        if declared_route != actual_route:
            return [f"lightweight request declared {declared_route}; classifier returned {actual_route}"]
        return ["simple request fixture failed to express an invalid escalation"]
    if fixture_type == "role_list_only":
        return validate_council_result(data.get("director_room_result"))
    if fixture_type == "duplicate_lane_seat":
        return validate_default_lanes(data.get("default_lanes"))
    if fixture_type == "empty_role_card":
        return validate_role_cards(data.get("role_cards"), data.get("result_mode"))
    if fixture_type == "invalid_recommendation":
        return validate_recommendation(
            data.get("recommendation"),
            set(data.get("option_ids", [])),
            set(data.get("resolution_ids", [])),
        )
    if fixture_type == "invalid_resolution":
        failures, _ = validate_resolution_notes(
            data.get("resolution_notes"),
            set(data.get("disagreement_ids", [])),
            set(data.get("arbitration_ids", [])),
        )
        return failures
    if fixture_type == "invalid_disagreement":
        failures, _ = validate_disagreements(data.get("disagreements"))
        return failures
    if fixture_type in {
        "explicit_threads_simulated",
        "real_thread_incomplete_evidence",
        "orchestrated_worker_scope",
    }:
        return validate_result_execution(data.get("execution"), data.get("open_questions"))
    return [f"unknown director harness fixture_type: {fixture_type}"]


def verify_invalid_fixture(path: str | Path, routing: dict[str, Any]) -> tuple[bool, list[str]]:
    data = load_yaml(path)
    failures = validate_invalid_fixture(data, routing)
    expected = data.get("expected_failure_contains")
    if isinstance(expected, str):
        return any(expected in failure for failure in failures), failures
    if isinstance(expected, list) and expected and all(isinstance(item, str) for item in expected):
        return all(any(item in failure for failure in failures) for item in expected), failures
    return False, failures


def route_response(request: str, routing: dict[str, Any]) -> dict[str, Any]:
    route = route_request(request, routing)
    if route == "director_room":
        return {
            "status": "success",
            "summary": "Non-trivial film-preproduction request routed to the director room.",
            "next_actions": ["enter 阶段: 导演组会议", "collect bounded role judgments", "show options and one user decision question"],
            "artifacts": [HARNESS_PATH, CANONICAL_RESULT_PATH, "docs/film-preproduction/director-room-routing.md"],
            "route": route,
        }
    return {
        "status": "success",
        "summary": "Request remains on the lightweight path.",
        "next_actions": ["answer the bounded rewrite or single question", "do not manufacture a director-room council"],
        "artifacts": [HARNESS_PATH],
        "route": route,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative automatic director-room routing and role harness contracts.")
    parser.add_argument("--route", help="Classify one user request and print a deterministic route response.")
    parser.add_argument(
        "--verify-invalid-fixture",
        metavar="PATH",
        help="Return success only when the named invalid fixture is rejected for its declared reason.",
    )
    args = parser.parse_args()

    harness_data = load_yaml(HARNESS_PATH)
    canonical_data = load_yaml(CANONICAL_RESULT_PATH)
    harness = harness_data.get("director_role_harness", {})
    routing = harness.get("routing") if isinstance(harness, dict) else None
    if not isinstance(routing, dict):
        print("DIRECTOR_HARNESS_AUDIT: FAIL")
        print("- harness routing is unavailable")
        return 1

    if args.route is not None:
        print(json.dumps(route_response(args.route, routing), ensure_ascii=False, indent=2))
        return 0

    if args.verify_invalid_fixture:
        ok, failures = verify_invalid_fixture(args.verify_invalid_fixture, routing)
        print(f"DIRECTOR_HARNESS_INVALID_FIXTURE: {'PASS' if ok else 'FAIL'}")
        for failure in failures:
            print(f"- {failure}")
        return 0 if ok else 1

    canonical_failures, canonical_example = validate_canonical_file(canonical_data)
    schema_failures = validate_harness(harness_data) + canonical_failures
    docs_failures = validate_docs()
    invalid_fixture_failures: list[str] = []
    rejected_count = 0
    for path in NEGATIVE_FIXTURES:
        ok, failures = verify_invalid_fixture(path, routing)
        if ok:
            rejected_count += 1
        else:
            invalid_fixture_failures.append(f"{path} was not rejected for the expected reason: {'; '.join(failures)}")

    cases = routing.get("behavior_cases", [])
    auto_cases = [case for case in cases if isinstance(case, dict) and case.get("expected_route") == "director_room"]
    lightweight_cases = [case for case in cases if isinstance(case, dict) and case.get("expected_route") == "lightweight"]
    passed_auto_cases = sum(not routing_case_failures(case, routing) for case in auto_cases)
    passed_lightweight_cases = sum(not routing_case_failures(case, routing) for case in lightweight_cases)
    passed_routing_cases = sum(not routing_case_failures(case, routing) for case in cases)
    council = harness.get("council_execution", {})
    print("DIRcreative Director Harness Audit")
    print("=" * 72)
    print(f"schema_version: {harness.get('schema_version', '')}")
    print(f"role_contracts_complete: {str(not validate_role_contracts(harness.get('roles'), require_all_roles=True)).lower()}")
    print(f"typed_lightweight_exceptions_valid: {str(not validate_typed_lightweight_exceptions(routing.get('typed_lightweight_exceptions'))).lower()}")
    print(f"complex_intent_priority_valid: {str(not validate_complex_intent_policy(routing.get('complex_intent_policy'))).lower()}")
    print(f"lane_seats_unique: {str(not validate_default_lanes(council.get('default_lanes'))).lower() if isinstance(council, dict) else 'false'}")
    print(f"routing_behavior_cases: {len(cases)}")
    print(f"positive_auto_routes: {passed_auto_cases}/{len(auto_cases)}")
    print(f"lightweight_bypasses: {passed_lightweight_cases}/{len(lightweight_cases)}")
    print(f"routing_cases_passed: {passed_routing_cases}/{len(cases)}")
    print(f"positive_council_output: {str(not validate_council_result(canonical_example)).lower()}")
    print(f"negative_fixtures_rejected: {rejected_count}/{len(NEGATIVE_FIXTURES)}")
    if schema_failures or docs_failures or invalid_fixture_failures:
        print("DIRECTOR_HARNESS_AUDIT: FAIL")
        for failure in schema_failures + docs_failures + invalid_fixture_failures:
            print(f"- {failure}")
        return 1
    print("DIRECTOR_HARNESS_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
