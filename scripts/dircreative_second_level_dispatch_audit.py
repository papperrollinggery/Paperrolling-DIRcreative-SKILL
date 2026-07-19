#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True

ALLOWED_HOST_CLASSES = {
    "disposable_read_only_worker",
    "isolated_worktree_worker",
    "reusable_research_thread",
}
ALLOWED_TASK_MODES = {
    "prompt_decomposition",
    "reference_check",
    "risk_inventory",
    "candidate_ranking",
    "source_or_contract_triage",
}
REQUIRED_FORBIDDEN_ACTIONS = {
    "write_files",
    "write_live_acceptance",
    "change_write_scope",
    "verify_cleanup",
    "mark_goal_complete",
    "mark_objective_complete",
    "become_durable_truth",
}


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def load_yaml(path: str | Path) -> Any:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT / target
    proc = run(
        [
            "ruby",
            "-e",
            "require 'yaml'; require 'json'; data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); puts JSON.generate(data)",
            str(target),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to parse {target}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists() and path.startswith("skills/") and path.endswith("/SKILL.md"):
        target = target.with_name("INTERNAL_SKILL.md")
    return target.read_text(encoding="utf-8")


def require_terms(label: str, text: str, terms: list[str]) -> list[str]:
    return [f"{label} missing term: {term}" for term in terms if term not in text]


def validate_record(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    policy = data.get("thread_class_policy", {}).get("second_level_subagents", {})
    dispatches = data.get("dispatches", [])

    if policy.get("allowed") is not True:
        failures.append("second-level subagents policy must set allowed true")
    if policy.get("default_authorized") is not False:
        failures.append("second-level subagents must default to unauthorized")
    if set(policy.get("host_thread_classes", [])) != ALLOWED_HOST_CLASSES:
        failures.append("second-level host thread classes mismatch")
    if "pinned_user_facing_controller" in policy.get("host_thread_classes", []):
        failures.append("main-controller thread cannot host second-level production subagents")
    if not ALLOWED_TASK_MODES.issubset(set(policy.get("allowed_task_modes", []))):
        failures.append("second-level allowed task modes incomplete")
    if not REQUIRED_FORBIDDEN_ACTIONS.issubset(set(policy.get("forbidden_actions", []))):
        failures.append("second-level forbidden actions incomplete")

    for item in dispatches:
        second_level = item.get("second_level_subagents")
        if not second_level:
            continue
        thread_class = item.get("thread_class")
        authorized = second_level.get("authorized") is True
        invocations = second_level.get("invocations", [])
        allowed_modes = set(second_level.get("allowed_task_modes", []))
        if authorized and thread_class not in ALLOWED_HOST_CLASSES:
            failures.append("second-level subagent authorized on invalid host thread class")
        if not authorized and invocations:
            failures.append("second-level invocations require explicit authorization")
        if not allowed_modes.issubset(ALLOWED_TASK_MODES):
            failures.append("second-level dispatch allowed_task_modes contains invalid mode")
        for invocation in invocations:
            task_mode = invocation.get("task_mode")
            closed_status = invocation.get("closed_status")
            adoption = invocation.get("adoption_decision")
            if task_mode not in ALLOWED_TASK_MODES or task_mode not in allowed_modes:
                failures.append("second-level invocation task_mode not authorized")
            if invocation.get("agent_type") not in {"stateless_read_only", "ephemeral_readonly"}:
                failures.append("second-level invocation must be stateless read-only")
            if not invocation.get("input_question"):
                failures.append("second-level invocation missing input_question")
            if closed_status == "tool_blocked":
                if invocation.get("subagent_id") != "TOOL_BLOCKED":
                    failures.append("second-level TOOL_BLOCKED invocation must record TOOL_BLOCKED")
            elif not invocation.get("subagent_id"):
                failures.append("second-level invocation missing subagent_id")
            if not invocation.get("output_summary"):
                failures.append("second-level invocation missing output_summary")
            if closed_status not in {"not_used", "completed_closed", "tool_blocked"}:
                failures.append("second-level invocation invalid closed_status")
            if adoption not in {"not_used", "adopted", "rejected", "deferred"}:
                failures.append("second-level invocation invalid adoption_decision")
            if adoption == "adopted" and not invocation.get("adopted_into"):
                failures.append("adopted second-level finding must be reconciled into durable artifact")
            adopted_targets = " ".join(str(target) for target in invocation.get("adopted_into", []))
            if "live-user-acceptance.yaml" in adopted_targets:
                failures.append("second-level subagent may not write live acceptance")
            if invocation.get("durable_truth") is not False:
                failures.append("second-level subagent cannot be durable truth")
            if invocation.get("may_write_live_acceptance") is not False:
                failures.append("second-level subagent may not write live acceptance")
            if invocation.get("may_mark_goal_complete") is not False:
                failures.append("second-level subagent may mark goal complete")
    return failures


def main() -> int:
    docs_failures: list[str] = []
    combined_docs = "\n".join(
        [
            read("skills/dircreative/SKILL.md"),
            read("docs/film-preproduction/thread-orchestration-protocol.md"),
            read("docs/film-preproduction/05-skill-integration-architecture.md"),
            read("docs/film-preproduction/06-gstack-execution-goal.md"),
            read("docs/film-preproduction/schemas/thread-dispatch-record.yaml"),
            read("docs/film-preproduction/schemas/thread-dispatch-record.template.yaml"),
        ]
    )
    docs_failures.extend(
        require_terms(
            "second-level dispatch docs",
            combined_docs,
            [
                "Second-level subagents are local tools inside a first-level Codex Thread worker",
                "second_level_subagents",
                "prompt_decomposition",
                "reference_check",
                "risk_inventory",
                "candidate_ranking",
                "source_or_contract_triage",
                "TOOL_BLOCKED",
                "durable_truth: false",
                "may_write_live_acceptance: false",
                "may_mark_goal_complete: false",
            ],
        )
    )

    schema_failures = validate_record(load_yaml("docs/film-preproduction/schemas/thread-dispatch-record.yaml"))
    template_failures = validate_record(load_yaml("docs/film-preproduction/schemas/thread-dispatch-record.template.yaml"))
    invalid_failures = validate_record(load_yaml("tests/fixtures/invalid-thread-dispatch-second-level-completion.yaml"))
    expected_invalid_terms = {
        "second-level subagent may mark goal complete",
        "second-level subagent may not write live acceptance",
        "second-level subagent cannot be durable truth",
    }
    missing_expected = [term for term in expected_invalid_terms if term not in invalid_failures]

    print("DIRcreative Second-Level Dispatch Audit")
    print("=" * 72)
    print("stateless_subagent_tool_verdict: available_when_explicitly_authorized")
    print("host_thread_classes: disposable_read_only_worker, isolated_worktree_worker, reusable_research_thread")
    print("forbidden_actions: write_live_acceptance, mark_goal_complete, mark_objective_complete, become_durable_truth")
    print(f"schema_contract_valid: {str(not schema_failures).lower()}")
    print(f"template_contract_valid: {str(not template_failures).lower()}")
    print(f"negative_fixture_rejected: {str(not missing_expected).lower()}")
    failures = docs_failures + schema_failures + template_failures
    if missing_expected:
        failures.append("negative fixture did not reject expected second-level completion/live-acceptance/durable-truth claims")
    if failures:
        print("SECOND_LEVEL_DISPATCH_AUDIT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("second_level_subagents_are_durable_truth: false")
    print("second_level_subagents_may_write_live_acceptance: false")
    print("second_level_subagents_may_mark_goal_complete: false")
    print("SECOND_LEVEL_DISPATCH_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
