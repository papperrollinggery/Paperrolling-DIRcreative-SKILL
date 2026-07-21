#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dircreative_route import load_policy, route_request, self_test as route_self_test


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = ROOT / "skills/dircreative/SKILL.md"
MAIN_SKILL = SOURCE_SKILL if SOURCE_SKILL.exists() else ROOT / "SKILL.md"
STATE_SCHEMA = ROOT / "skills/dircreative/runtime/state-snapshot.schema.json"
RUNTIME_INDEX = ROOT / "docs/film-preproduction/runtime-contracts.md"
FORBIDDEN_FAST_TERMS = (
    "thread-orchestration-protocol.md",
    "adco-integration-contract.md",
    "goal-autorun-completion-protocol.md",
    "finaldelivery",
    "client-film-hard-gates.md",
)
LEGACY_ACTIVE_CONTEXT = {
    "docs/film-preproduction/professional-agent-voice-standard.md",
    "docs/film-preproduction/schemas/director-role-harness.yaml",
    "docs/film-preproduction/capability-aware-generation-policy.md",
    "docs/film-preproduction/client-film-hard-gates.md",
    "docs/film-preproduction/adco-integration-contract.md",
    "skills/dircreative/script-treatment/SKILL.md",
    "skills/dircreative/shot-design/SKILL.md",
    "skills/dircreative/video-model-adapter/SKILL.md",
    "skills/dircreative/director-room/SKILL.md",
    "skills/dircreative/generation-qa/SKILL.md",
}
WARM_ROUTE_P95_BUDGET_MS = 25.0
COLD_ROUTE_P95_BUDGET_MS = 300.0


def audit() -> tuple[list[str], dict[str, Any]]:
    failures = route_self_test()
    policy = load_policy()
    expected_contract_owners = {
        "activation": "skills/dircreative/agents/openai.yaml",
        "routing": "skills/dircreative/runtime/routing-policy.yaml",
        "interaction_and_external_gates": "skills/dircreative/runtime/routing-policy.yaml",
        "compact_state": "skills/dircreative/runtime/state-snapshot.schema.json",
        "fast_execution": "skills/dircreative/routes/fast-task.md",
        "studio_execution": "skills/dircreative/routes/studio-development.md",
        "delivery_execution": "skills/dircreative/routes/delivery-audit.md",
        "director_perspective_selection": "docs/film-preproduction/director-room-routing.md",
        "prompt_ir": "docs/film-preproduction/schemas/prompt-ir.schema.json",
        "model_adapter_interface": "scripts/dircreative_adapters/base.py",
        "specialist_exchange": "docs/film-preproduction/schemas/adco-specialist-descriptor.json",
        "legacy_thread_evidence": "docs/film-preproduction/thread-orchestration-protocol.md",
    }
    if policy.get("contract_owners") != expected_contract_owners:
        failures.append("runtime contract owner registry drifted or contains duplicate definitions")
    for contract_id, relative in expected_contract_owners.items():
        if not (ROOT / relative).is_file():
            failures.append(f"runtime contract owner is missing: {contract_id} -> {relative}")
    if not RUNTIME_INDEX.is_file():
        failures.append("canonical runtime contract index is missing")
        runtime_index_text = ""
    else:
        runtime_index_text = RUNTIME_INDEX.read_text(encoding="utf-8")
    for contract_id, relative in expected_contract_owners.items():
        if relative not in runtime_index_text:
            failures.append(f"runtime contract index omits owner: {contract_id}")
    supporting_guides = {
        "docs/film-preproduction/chat-co-creation-interface.md": "v2 presentation guide",
        "docs/film-preproduction/live-chat-start-protocol.md": "v2 first-response presentation guide",
        "docs/film-preproduction/chat-stage-gate-integrity.md": "v2 integrity guide",
        "docs/film-preproduction/runtime-state-governance.md": "supporting guide for resume",
        "docs/film-preproduction/adco-integration-contract.md": "provider integration guide",
        "docs/film-preproduction/thread-orchestration-protocol.md": "legacy v1 evidence reader",
        "docs/film-preproduction/05-skill-integration-architecture.md": "historical architecture",
    }
    for relative, status_phrase in supporting_guides.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        if status_phrase not in text:
            failures.append(f"supporting guide lacks non-owner status: {relative}")
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
    for phrase in (
        "only to validate an ADCO handoff",
        "not a mandatory creative preflight",
        "obvious Fast or Studio request needs no router tool call",
    ):
        if phrase.casefold() not in main_text.casefold():
            failures.append(f"main SKILL lost zero-tool obvious-route rule: {phrase}")

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
    route_context_metrics: dict[str, dict[str, Any]] = {}
    budgets = policy.get("performance_budgets", {})
    for route_id, config in routes.items():
        if config.get("route_card") != route_cards.get(config.get("mode")):
            failures.append(f"{route_id}: route card does not match mode")
        required = config.get("required_files", [])
        mode = config.get("mode")
        mode_budget = budgets.get(mode, {})
        task_files_max = int(mode_budget.get("task_files_max", 0))
        if len(required) > task_files_max:
            failures.append(f"{route_id}: {mode} route exceeds {task_files_max} task files")
        legacy = sorted(set(required + config.get("optional_files", [])) & LEGACY_ACTIVE_CONTEXT)
        if legacy:
            failures.append(f"{route_id}: active v2 route loads legacy-heavy context: {legacy}")
        if mode in {"fast", "studio"}:
            non_craft = [item for item in required if not item.startswith("skills/dircreative/references/")]
            if non_craft:
                failures.append(f"{route_id}: {mode} route loads non-craft runtime context: {non_craft}")
        for relative in required + config.get("optional_files", []):
            target = ROOT / relative
            if not target.exists() and relative.endswith("/SKILL.md"):
                target = target.with_name("INTERNAL_SKILL.md")
            if not target.exists():
                failures.append(f"{route_id}: missing routed file {relative}")
        adco_refs = [item for item in required if item.endswith("adco-integration-contract.md")]
        if adco_refs and route_id != "adco_specialist_exchange":
            failures.append(f"{route_id}: ADCO integration contract is outside valid handoff route")

        relative_paths = [config.get("route_card"), *required]
        resolved_paths = [MAIN_SKILL]
        for relative in relative_paths:
            target = ROOT / relative
            if not target.exists() and str(relative).endswith("/SKILL.md"):
                target = target.with_name("INTERNAL_SKILL.md")
            if target.is_file():
                resolved_paths.append(target)
        loaded_bytes = sum(len(path.read_bytes()) for path in resolved_paths)
        loaded_lines = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in resolved_paths)
        loaded_files = len(resolved_paths)
        max_bytes = int(mode_budget.get("loaded_context_bytes_max", 0))
        max_files = int(mode_budget.get("loaded_context_files_max", 0))
        if loaded_bytes > max_bytes:
            failures.append(f"{route_id}: loaded context {loaded_bytes} bytes exceeds {max_bytes}")
        if loaded_files > max_files:
            failures.append(f"{route_id}: loaded context {loaded_files} files exceeds {max_files}")
        route_context_metrics[route_id] = {
            "mode": mode,
            "files": loaded_files,
            "bytes": loaded_bytes,
            "lines": loaded_lines,
            "bytes_budget": max_bytes,
            "task_files": len(required),
        }

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

    fast = budgets.get("fast", {})
    expected_fast = {
        "threads": 0,
        "director_room": 0,
        "external_user_gates_max": 1,
        "full_receipt": False,
        "full_project_validation": False,
        "adco_documents": 0,
        "route_cards": 1,
        "task_files_max": 1,
        "loaded_context_files_max": 3,
        "loaded_context_bytes_max": 14000,
        "pre_artifact_routing_or_audit_tool_calls_max": 0,
        "task_context_reads_max": 2,
        "useful_content_ratio_min": 0.75,
        "process_narration_ratio_max": 0.10,
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
        "task_files_max": 1,
        "loaded_context_files_max": 3,
        "loaded_context_bytes_max": 20000,
        "pre_artifact_routing_or_audit_tool_calls_max": 0,
        "task_context_reads_max": 2,
        "useful_content_ratio_min": 0.70,
        "process_narration_ratio_max": 0.15,
        "full_project_validation": False,
    }.items():
        if studio.get(key) != expected:
            failures.append(f"Studio performance budget {key} drifted")
    delivery = budgets.get("delivery", {})
    if delivery.get("duplicate_state_owners_allowed") is not False:
        failures.append("Delivery allows duplicate state owners")
    for key, expected in {
        "task_files_max": 2,
        "loaded_context_files_max": 4,
        "loaded_context_bytes_max": 30000,
        "scoped_validation_required": True,
    }.items():
        if delivery.get(key) != expected:
            failures.append(f"Delivery performance budget {key} drifted")
    for key, expected in {
        "obvious_route_without_router_tool": True,
        "scoped_validation_policy": "current_task_and_direct_dependencies_only",
        "unrelated_global_debt_blocks_scoped_work": False,
    }.items():
        if interaction.get(key) != expected:
            failures.append(f"interaction content-first policy {key} drifted")

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

    cold_samples: list[float] = []
    for request in (latency_requests * 4):
        started = time.perf_counter_ns()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/dircreative_route.py"), request],
            cwd=ROOT,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
        cold_samples.append((time.perf_counter_ns() - started) / 1_000_000)
        if proc.returncode != 0:
            failures.append(f"cold route process failed: {proc.stderr.strip()}")
            break
    cold_samples.sort()
    cold_p95_index = max(0, int(len(cold_samples) * 0.95) - 1)
    route_cold_p95_ms = round(cold_samples[cold_p95_index], 4) if cold_samples else -1.0
    if route_cold_p95_ms > COLD_ROUTE_P95_BUDGET_MS:
        failures.append(
            f"cold route p95 latency {route_cold_p95_ms}ms exceeds {COLD_ROUTE_P95_BUDGET_MS}ms"
        )

    metrics: dict[str, Any] = {
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
        "cold_route_samples": len(cold_samples),
        "cold_route_p95_ms": route_cold_p95_ms,
        "cold_route_p95_budget_ms": COLD_ROUTE_P95_BUDGET_MS,
        "runtime_contract_owners": len(expected_contract_owners),
        "route_contexts": route_context_metrics,
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
