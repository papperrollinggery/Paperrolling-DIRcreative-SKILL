#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from dircreative_route import load_policy, route_request, self_test as route_self_test


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = ROOT / "skills/dircreative/SKILL.md"
MAIN_SKILL = SOURCE_SKILL if SOURCE_SKILL.exists() else ROOT / "SKILL.md"
STATE_SCHEMA = ROOT / "skills/dircreative/runtime/state-snapshot.schema.json"
FORBIDDEN_FAST_TERMS = (
    "thread-orchestration-protocol.md",
    "adco-integration-contract.md",
    "goal-autorun-completion-protocol.md",
    "finaldelivery",
    "client-film-hard-gates.md",
)
WARM_ROUTE_P95_BUDGET_MS = 25.0


def audit() -> tuple[list[str], dict[str, int | float | bool]]:
    failures = route_self_test()
    policy = load_policy()
    main_text = MAIN_SKILL.read_text(encoding="utf-8")
    main_lines = len(main_text.splitlines())
    main_bytes = len(main_text.encode("utf-8"))
    if main_lines > 220:
        failures.append(f"main SKILL exceeds 220 lines: {main_lines}")
    if main_bytes > 16 * 1024:
        failures.append(f"main SKILL exceeds 16 KiB: {main_bytes}")
    unconditional = re.findall(r"^\s*- Unconditional read:", main_text, flags=re.MULTILINE)
    if len(unconditional) > 3:
        failures.append(f"main SKILL has more than three unconditional reads: {len(unconditional)}")
    if "read exactly one selected route card" not in main_text.casefold():
        failures.append("main SKILL does not constrain execution to one Route Card")

    route_cards = policy.get("route_cards", {})
    if set(route_cards) != {"fast", "studio", "delivery"}:
        failures.append("routing policy must declare exactly fast/studio/delivery Route Cards")
    card_paths = {mode: ROOT / value for mode, value in route_cards.items()}
    for mode, path in card_paths.items():
        if not path.is_file():
            failures.append(f"missing {mode} Route Card: {path.relative_to(ROOT)}")
    if all(path.is_file() for path in card_paths.values()):
        fast_text = card_paths["fast"].read_text(encoding="utf-8").casefold()
        for term in FORBIDDEN_FAST_TERMS:
            if term.casefold() in fast_text:
                failures.append(f"Fast Route Card loads forbidden contract: {term}")
        studio_text = card_paths["studio"].read_text(encoding="utf-8").casefold()
        if "finaldelivery" in studio_text or "client-film-hard-gates.md" in studio_text:
            failures.append("Studio Route Card loads final-delivery contracts")

    routes = policy.get("routes", {})
    for route_id, config in routes.items():
        if config.get("route_card") != route_cards.get(config.get("mode")):
            failures.append(f"{route_id}: route card does not match mode")
        required = config.get("required_files", [])
        if config.get("mode") == "fast" and len(required) > 3:
            failures.append(f"{route_id}: Fast route exceeds three task files")
        for relative in required + config.get("optional_files", []):
            target = ROOT / relative
            if not target.exists() and relative.endswith("/SKILL.md"):
                target = target.with_name("INTERNAL_SKILL.md")
            if not target.exists():
                failures.append(f"{route_id}: missing routed file {relative}")
        adco_refs = [item for item in required if item.endswith("adco-integration-contract.md")]
        if adco_refs and route_id != "adco_specialist_exchange":
            failures.append(f"{route_id}: ADCO integration contract is outside valid handoff route")

    interaction = policy.get("interaction_contract", {})
    if interaction.get("external_user_gates") != [
        "concept_lock",
        "generation_authorization",
        "client_delivery_approval",
    ]:
        failures.append("v2 external user gate set drifted")
    if interaction.get("reversible_internal_states") != [
        "story_state",
        "script_state",
        "shot_state",
        "visual_state",
        "reference_state",
        "prompt_state",
        "qa_state",
    ]:
        failures.append("v2 reversible internal state set drifted")
    if interaction.get("state_persistence") != {
        "fast": "memory_only",
        "studio": "pause_cross_session_or_multi_file_only",
        "delivery": "required",
    }:
        failures.append("compact state persistence policy drifted")

    card_values = set(route_cards.values())
    for mode, path in card_paths.items():
        if not path.is_file():
            continue
        references = set(re.findall(r"(?:skills|docs)/[A-Za-z0-9_./-]+", path.read_text(encoding="utf-8")))
        if references & card_values:
            failures.append(f"{mode}: Route Card references another Route Card")

    schema = json.loads(STATE_SCHEMA.read_text(encoding="utf-8"))
    expected_state_fields = {
        "project_id", "mode", "current_route", "locked_facts", "working_assumptions",
        "active_outputs", "stale_outputs", "open_questions", "generation_authorized",
        "client_delivery_approved",
    }
    if set(schema.get("required", [])) != expected_state_fields:
        failures.append("compact state snapshot required fields drifted")

    budgets = policy.get("performance_budgets", {})
    fast = budgets.get("fast", {})
    expected_fast = {
        "threads": 0,
        "director_room": 0,
        "external_user_gates_max": 1,
        "full_receipt": False,
        "full_project_validation": False,
        "adco_documents": 0,
        "route_cards": 1,
        "task_files_max": 3,
    }
    for key, expected in expected_fast.items():
        if fast.get(key) != expected:
            failures.append(f"Fast performance budget {key} drifted")
    studio = budgets.get("studio", {})
    for key, expected in {
        "threads_default": 0,
        "perspectives_max": 3,
        "independent_critics_max": 1,
        "route_cards": 1,
    }.items():
        if studio.get(key) != expected:
            failures.append(f"Studio performance budget {key} drifted")
    delivery = budgets.get("delivery", {})
    if delivery.get("duplicate_state_owners_allowed") is not False:
        failures.append("Delivery allows duplicate state owners")

    latency_requests = [
        "$dircreative 修改脚本第三句",
        "$dircreative 开发完整广告片，brief 已完整",
        "$dircreative 准备客户交付",
    ]
    latency_samples: list[float] = []
    for index in range(300):
        started = time.perf_counter_ns()
        route_request(latency_requests[index % len(latency_requests)])
        latency_samples.append((time.perf_counter_ns() - started) / 1_000_000)
    latency_samples.sort()
    p95_index = max(0, int(len(latency_samples) * 0.95) - 1)
    route_warm_p95_ms = round(latency_samples[p95_index], 4)
    if route_warm_p95_ms > WARM_ROUTE_P95_BUDGET_MS:
        failures.append(
            f"warm route p95 latency {route_warm_p95_ms}ms exceeds {WARM_ROUTE_P95_BUDGET_MS}ms"
        )

    metrics: dict[str, int | float | bool] = {
        "main_skill_lines": main_lines,
        "main_skill_bytes": main_bytes,
        "unconditional_startup_reads": len(unconditional),
        "route_cards_per_run": 1,
        "fast_threads": fast.get("threads", -1),
        "fast_director_room": fast.get("director_room", -1),
        "fast_full_receipt": bool(fast.get("full_receipt")),
        "fast_full_project_validation": bool(fast.get("full_project_validation")),
        "fast_adco_documents": fast.get("adco_documents", -1),
        "studio_perspectives_max": studio.get("perspectives_max", -1),
        "studio_independent_critics_max": studio.get("independent_critics_max", -1),
        "warm_route_samples": len(latency_samples),
        "warm_route_p95_ms": route_warm_p95_ms,
        "warm_route_p95_budget_ms": WARM_ROUTE_P95_BUDGET_MS,
    }
    return failures, metrics


def main() -> int:
    failures, metrics = audit()
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        print("DIRCREATIVE_CONTEXT_BUDGET_AUDIT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("DIRCREATIVE_CONTEXT_BUDGET_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
