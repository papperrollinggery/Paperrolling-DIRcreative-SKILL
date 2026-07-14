#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from dircreative_validation_harness import Check, ROOT, add_check, read, require_terms


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


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
        raise AssertionError(f"YAML parse failed for {target}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def require_subprocess_pass(label: str, cmd: list[str], terms: list[str]) -> None:
    proc = run(cmd)
    output = proc.stdout + "\n" + proc.stderr
    if proc.returncode != 0:
        raise AssertionError(f"{label} failed:\n{output.strip()}")
    require_terms(output, terms, label)


def require_subprocess_rejects(label: str, cmd: list[str], terms: list[str]) -> None:
    proc = run(cmd)
    output = proc.stdout + "\n" + proc.stderr
    if proc.returncode == 0:
        raise AssertionError(f"{label} unexpectedly passed:\n{output.strip()}")
    require_terms(output, terms, label)


def validate_typed_action_observation_contract() -> None:
    dispatch = load_yaml("tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-06.yaml")
    co_creation = load_yaml("examples/goal-mode-autorun-commercial-cp-test/15-co-creation-run.yaml")
    live_template = load_yaml("docs/film-preproduction/templates/live-user-acceptance.template.yaml")
    image_manifest = load_yaml("examples/live-user-sim-noodle/10-image-prompt-manifest.yaml")

    dispatches = dispatch.get("dispatches", [])
    if not dispatches:
        raise AssertionError("thread dispatch receipt has no dispatches")
    for item in dispatches:
        for field in [
            "thread_id",
            "thread_class",
            "read_scope",
            "write_scope",
            "allowed_actions",
            "expected_output",
            "stop_condition",
            "output_status",
        ]:
            if not item.get(field):
                raise AssertionError(f"dispatch missing typed field: {field}")
        if item.get("output_status") in {"consumed", "adopted"} and not item.get("findings_summary"):
            raise AssertionError("consumed/adopted dispatch missing observations in findings_summary")

    gates = co_creation.get("gates", [])
    if len(gates) < 11:
        raise AssertionError("goal autorun co-creation run must cover every gate")
    for gate in gates:
        for field in [
            "gate_id",
            "gate_type",
            "status",
            "decision_source",
            "options_presented",
            "selected_option",
            "rationale",
        ]:
            if not gate.get(field):
                raise AssertionError(f"co-creation gate missing typed field: {field}")

    chat_evidence = live_template.get("chat_evidence", {})
    for field in ["observed_stages", "user_decisions_recorded"]:
        if field not in chat_evidence or not isinstance(chat_evidence.get(field), list):
            raise AssertionError(f"live acceptance template missing typed observation list: {field}")

    images = image_manifest.get("images", [])
    if not images:
        raise AssertionError("image prompt manifest has no images")
    for image in images:
        status = image.get("asset_output", {}).get("status")
        observations = image.get("style_config", {}).get("self_update", {}).get("qa_observations")
        if not status:
            raise AssertionError("image prompt asset missing asset_output.status")
        if not isinstance(observations, list):
            raise AssertionError("image prompt asset missing style_config.self_update.qa_observations list")


def validate_receipt_persistence_contract() -> None:
    root_skill = read("skills/dircreative/SKILL.md")
    integration = read("docs/film-preproduction/05-skill-integration-architecture.md")
    receipt_paths = [
        "tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-06.yaml",
        "tests/fixtures/runtime/runs/release-gate-technical-readiness-2026-06-06.yaml",
        "tests/fixtures/runtime/runs/objective-requirement-audit-2026-06-06.yaml",
        "docs/film-preproduction/templates/live-user-acceptance.template.yaml",
        "examples/goal-mode-autorun-commercial-cp-test/15-co-creation-run.yaml",
    ]
    require_terms(
        root_skill + "\n" + integration,
        [
            "`skill_run_receipt`",
            "Every sub-skill writes a receipt",
            "They do not communicate through hidden conversation memory.",
            ".dircreative/runs/",
        ],
        "receipt persistence docs",
        case_sensitive=False,
    )
    for path in receipt_paths:
        data = load_yaml(path)
        if "skill_run_receipt" not in data:
            raise AssertionError(f"{path} missing skill_run_receipt")


def validate_retry_loop_contract() -> None:
    taxonomy = load_yaml("docs/film-preproduction/qa/failure-taxonomy.yaml")
    retry = read("docs/film-preproduction/qa/retry-rules.md")
    required_ids = {
        "thread_control_incomplete",
        "goal_autorun_claimed_live_acceptance",
        "creative_production_widget_used_as_truth",
        "prompt_contract_incomplete",
        "multi_variable_retry",
        "missing_falsifiable_success_criteria",
    }
    taxonomy_ids = {item.get("id") for item in taxonomy.get("failure_types", [])}
    missing_taxonomy = sorted(required_ids - taxonomy_ids)
    if missing_taxonomy:
        raise AssertionError(f"failure taxonomy missing ids: {missing_taxonomy}")
    missing_retry = sorted(failure_id for failure_id in required_ids if f"`{failure_id}`" not in retry)
    if missing_retry:
        raise AssertionError(f"retry rules missing ids: {missing_retry}")
    require_terms(
        retry,
        [
            "Retry only the smallest artifact",
            "smallest artifact",
            "one variable changed",
            "next QA check",
            "falsifiable success criteria",
        ],
        "retry rules",
        case_sensitive=False,
    )


def validate_thread_boundary_contract() -> None:
    data = load_yaml("tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-06.yaml")
    policy = data.get("thread_class_policy", {})
    boundary = data.get("completion_boundary", {})
    dispatches = data.get("dispatches", [])
    if "isolated_worktree_worker" not in policy.get("allowed_thread_classes", []):
        raise AssertionError("thread policy must allow isolated_worktree_worker")
    if policy.get("substantive_output_default_thread_class") != "isolated_worktree_worker":
        raise AssertionError("substantive output must default to isolated_worktree_worker")
    if policy.get("read_only_worker_use") != "review_research_cold_review_only":
        raise AssertionError("read-only workers must be limited to review, research, and cold review")
    if policy.get("main_controller_write_boundary") != "receipts_adoption_merge_rollback_validation_only":
        raise AssertionError("main-controller write boundary must stay receipt/adoption/validation only")
    if boundary.get("completion_claim_allowed") is not False or boundary.get("objective_complete") is not False:
        raise AssertionError("thread boundary cannot allow objective completion")
    if any(item.get("may_mark_goal_complete") is not False for item in dispatches):
        raise AssertionError("dispatch may mark goal complete")
    invalid = load_yaml("tests/fixtures/invalid-thread-dispatch-worker-can-complete.yaml")
    if not any(item.get("may_mark_goal_complete") is True for item in invalid.get("dispatches", [])):
        raise AssertionError("negative thread fixture no longer covers worker completion claim")
    require_terms(
        read("scripts/dircreative_thread_audit.py") + "\n" + read("scripts/validate_project.py"),
        [
            "worker dispatch may mark goal complete",
            "isolated worktree worker must write only in its worktree",
            "git worktree audit found unexpected worktrees",
        ],
        "thread audit executable boundary",
    )


def validate_second_level_dispatch_contract() -> None:
    require_subprocess_pass(
        "second-level dispatch audit",
        ["python3", "scripts/dircreative_second_level_dispatch_audit.py"],
        [
            "DIRcreative Second-Level Dispatch Audit",
            "stateless_subagent_tool_verdict: available_when_explicitly_authorized",
            "negative_fixture_rejected: true",
            "second_level_subagents_are_durable_truth: false",
            "second_level_subagents_may_write_live_acceptance: false",
            "second_level_subagents_may_mark_goal_complete: false",
            "SECOND_LEVEL_DISPATCH_AUDIT: PASS",
        ],
    )


def validate_council_review_contract() -> None:
    require_subprocess_pass(
        "council audit",
        ["python3", "scripts/dircreative_council_audit.py"],
        [
            "COUNCIL_AUDIT: PASS",
            "required_viewpoints_present: true",
            "external_research_boundary_present: true",
            "objective_complete: OBJECTIVE_COMPLETE: NO",
            "live user acceptance is still required",
        ],
    )


def validate_goal_autorun_boundary() -> None:
    require_subprocess_pass(
        "goal autorun audit",
        ["python3", "scripts/dircreative_goal_autorun_audit.py"],
        [
            "GOAL_AUTORUN_AUDIT: PASS",
            "goal_autorun_dry_run_complete: true",
            "real_media_generated: false",
            "live_acceptance_required: true",
        ],
    )


def validate_live_acceptance_boundary() -> None:
    require_subprocess_pass(
        "acceptance preflight",
        ["python3", "scripts/dircreative_acceptance_preflight.py"],
        [
            "receipt_creation_allowed: false",
            "acceptance_mode: real_chat_only",
            "objective_still_blocked: pass",
        ],
    )
    require_subprocess_rejects(
        "simulated acceptance fixture",
        [
            "python3",
            "scripts/dircreative_goal_audit.py",
            "--acceptance-receipt",
            "tests/fixtures/invalid-live-user-acceptance-simulated-source.yaml",
        ],
        [
            "INVALID_ACCEPTANCE_RECEIPT",
            "acceptance_run.run_type must be live_user_acceptance",
            "GOAL_COMPLETE: NO",
        ],
    )


def validate_quality_claim_boundary() -> None:
    require_terms(
        read("docs/film-preproduction/live-user-acceptance-gate.md")
        + "\n"
        + read("docs/film-preproduction/council-adversarial-review.md"),
        [
            "Technical gates can prove readiness. They cannot prove user satisfaction.",
            "Use council review when the workflow could plausibly pass validation while still failing the user.",
            "Does `scripts/validate_project.py` check the new durable contract without pretending keyword checks prove quality?",
        ],
        "quality approval boundary docs",
    )


def main() -> int:
    checks: list[Check] = []
    add_check(checks, "typed action/observation contract", "schemas, receipts, prompt manifests", validate_typed_action_observation_contract)
    add_check(checks, "receipt persistence contract", "skill docs and .dircreative receipts", validate_receipt_persistence_contract)
    add_check(checks, "retry loop contract", "failure taxonomy and retry rules", validate_retry_loop_contract)
    add_check(checks, "council review contract", "scripts/dircreative_council_audit.py", validate_council_review_contract)
    add_check(checks, "Codex Thread boundary contract", "scripts/dircreative_thread_audit.py", validate_thread_boundary_contract)
    add_check(checks, "second-level dispatch contract", "scripts/dircreative_second_level_dispatch_audit.py", validate_second_level_dispatch_contract)
    add_check(checks, "Goal autorun dry-run boundary", "scripts/dircreative_goal_autorun_audit.py", validate_goal_autorun_boundary)
    add_check(checks, "live acceptance boundary", "scripts/dircreative_acceptance_preflight.py + goal audit fixture", validate_live_acceptance_boundary)
    add_check(checks, "quality approval boundary", "live acceptance and council docs", validate_quality_claim_boundary)

    print("DIRcreative Loop Engineering Audit")
    print("=" * 72)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.label}")
        print(f"       evidence: {check.evidence}")
    failures = [check for check in checks if not check.ok]
    if failures:
        print("LOOP_ENGINEERING_AUDIT: FAIL")
        return 1
    print("typed_action_observation_contract: true")
    print("receipt_persistence_contract: true")
    print("retry_loop_contract: true")
    print("council_review_contract: true")
    print("codex_thread_boundary_contract: true")
    print("second_level_dispatch_contract: true")
    print("goal_autorun_dry_run_boundary: true")
    print("live_acceptance_boundary: true")
    print("creative_quality_approval_claimed: false")
    print("LOOP_ENGINEERING_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
