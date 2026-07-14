#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "runtime" / "runs"
CLEANUP_RECEIPT = FIXTURE_ROOT / "thread-orchestration-cleanup-2026-06-06.yaml"
OBJECTIVE_RECEIPT = FIXTURE_ROOT / "objective-requirement-audit-2026-06-06.yaml"
RELEASE_RECEIPT = FIXTURE_ROOT / "release-gate-technical-readiness-2026-06-06.yaml"
FORBIDDEN_MAIN_CONTROLLER_WRITE_CLAIMS = [
    "main-controller thread owns final writes",
    "main-controller owns final writes",
    "main controller thread owns final writes",
    "main controller owns final writes",
    "owns final repository writes",
    "main-controller final repository writes",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def load_yaml(path: Path) -> Any:
    proc = run(
        [
            "ruby",
            "-e",
            "require 'yaml'; require 'json'; data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); puts JSON.generate(data)",
            str(path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to parse {path}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def git_worktrees(cleanup: dict[str, Any]) -> tuple[list[str], str]:
    proc = run(["git", "worktree", "list", "--porcelain"])
    if proc.returncode != 0 and "not a git repository" in proc.stderr:
        worktree_summary = cleanup.get("run", {}).get("worktree_evidence", {}).get("result_summary", "")
        if "Only " in worktree_summary and " was listed" in worktree_summary:
            recorded = worktree_summary.removeprefix("Only ").removesuffix(" was listed.").strip()
            if recorded.endswith(" on main"):
                recorded = recorded.removesuffix(" on main").strip()
            return [recorded], "recorded_receipt"
        return [], "not_git_repository"
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    worktrees: list[str] = []
    for line in proc.stdout.splitlines():
        if line.startswith("worktree "):
            worktrees.append(line.removeprefix("worktree ").strip())
    return worktrees, "git"


def build_failures(cleanup: dict[str, Any], objective: dict[str, Any], release: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []

    cleanup_run = cleanup.get("run", {})
    cleanup_qa = cleanup.get("qa", {})
    dispatch_record = cleanup.get("thread_dispatch_record", {})
    thread_policy = cleanup.get("thread_class_policy", {})
    thread_budget = cleanup.get("thread_budget", {})
    dispatches = cleanup.get("dispatches", [])
    completion_boundary = cleanup.get("completion_boundary", {})
    objective_standard = objective.get("run", {}).get("authoritative_completion_standard", {})
    objective_qa = objective.get("qa", {})
    release_boundary = release.get("run", {}).get("completion_boundary", {})
    release_qa = release.get("qa", {})
    worktrees, worktree_source = git_worktrees(cleanup)
    expected_main_worktree = cleanup.get("worktree_audit", {}).get("expected_main_worktree") or str(ROOT)
    allowed_worktrees = {str(ROOT), str(expected_main_worktree)}
    unexpected_worktrees = [worktree for worktree in worktrees if worktree not in allowed_worktrees]

    if cleanup_run.get("main_controller_thread", {}).get("pinned") is not True:
        failures.append("main controller thread is not recorded as pinned")
    if cleanup_qa.get("disposable_workers_archived") is not True:
        failures.append("disposable worker cleanup is not recorded as complete")
    if dispatch_record.get("main_controller_thread_id") != cleanup_run.get("main_controller_thread", {}).get("thread_id"):
        failures.append("thread dispatch record does not match main-controller thread id")
    if thread_policy.get("hidden_thread_state_is_truth") is not False:
        failures.append("thread class policy must forbid hidden thread state as truth")
    if thread_policy.get("substantive_output_default_thread_class") != "isolated_worktree_worker":
        failures.append("substantive output must default to isolated worktree worker")
    if thread_policy.get("read_only_worker_use") != "review_research_cold_review_only":
        failures.append("read-only workers must be limited to review, research, and cold review")
    if thread_policy.get("main_controller_write_boundary") != "receipts_adoption_merge_rollback_validation_only":
        failures.append("main-controller write boundary must be receipts/adoption/merge/rollback/validation only")
    if thread_budget.get("max_active_workers") != 3:
        failures.append("thread budget must cap max_active_workers at 3")
    if thread_budget.get("approval_required_above") != 5:
        failures.append("thread budget must require approval above 5 workers")
    active_worker_count = thread_budget.get("active_worker_count")
    if not isinstance(active_worker_count, int) or active_worker_count < 0:
        failures.append("thread budget active_worker_count must be non-negative integer")
    elif active_worker_count > thread_budget.get("max_active_workers", 0) and not thread_budget.get("over_budget_reason"):
        failures.append("thread budget over max_active_workers requires over_budget_reason")
    if isinstance(active_worker_count, int) and active_worker_count > 5:
        failures.append("thread budget active_worker_count exceeds approval threshold")
    if not dispatches:
        failures.append("thread dispatch record has no dispatches")
    main_dispatches = [item for item in dispatches if item.get("thread_class") == "pinned_user_facing_controller"]
    disposable_dispatches = [item for item in dispatches if item.get("thread_class") == "disposable_read_only_worker"]
    if len(main_dispatches) != 1 or main_dispatches[0].get("pinned") is not True:
        failures.append("thread dispatch record must have exactly one pinned user-facing controller")
    if len(main_dispatches) == 1 and dispatch_record.get("main_controller_thread_id") != main_dispatches[0].get("thread_id"):
        failures.append("main_controller_thread_id must match pinned controller dispatch")
    thread_ids = [item.get("thread_id") for item in dispatches if item.get("thread_id")]
    if any(thread_ids.count(thread_id) > 1 for thread_id in thread_ids):
        failures.append("thread_id reused across dispatches")
    for item in dispatches:
        if not item.get("professional_identity"):
            failures.append("thread dispatch missing professional_identity")
        if not item.get("allowed_actions"):
            failures.append("thread dispatch missing allowed_actions")
        if not item.get("stop_condition"):
            failures.append("thread dispatch missing stop_condition")
        if item.get("thread_class") != "pinned_user_facing_controller" and item.get("pinned") is True:
            failures.append("only main-controller thread may be pinned")
        if item.get("thread_class") == "pinned_user_facing_controller":
            allowed_actions_text = " ".join(str(action) for action in item.get("allowed_actions", []))
            controller_contract_text = " ".join(
                [
                    str(item.get("role", "")),
                    str(item.get("expected_output", "")),
                    allowed_actions_text,
                    " ".join(str(finding) for finding in item.get("findings_summary", [])),
                ]
            ).lower()
            if any(phrase in controller_contract_text for phrase in FORBIDDEN_MAIN_CONTROLLER_WRITE_CLAIMS):
                failures.append("main-controller may only write receipts/adoption/merge/rollback/validation records")
        if item.get("thread_class") == "disposable_read_only_worker":
            if item.get("write_scope") != "none":
                failures.append("disposable read-only worker must have write_scope none")
            if item.get("worktree_path"):
                failures.append("disposable read-only worker must not claim a worktree path")
        if (
            item.get("thread_class") != "pinned_user_facing_controller"
            and item.get("output_status") in {"consumed", "adopted"}
            and item.get("findings_summary")
            and not item.get("adopted_into")
        ):
            failures.append("consumed or adopted worker findings must be reconciled into durable artifacts")
    if any(item.get("cleanup_rule") != "archive_after_consumed" or item.get("archived") is not True for item in disposable_dispatches):
        failures.append("all disposable read-only workers must be archived after consumed")
    if any(item.get("may_mark_goal_complete") is not False for item in dispatches):
        failures.append("worker dispatch may mark goal complete")
    if cleanup_qa.get("unintended_worker_worktrees_present") is not False:
        failures.append("cleanup receipt allows unintended worker worktrees")
    if completion_boundary.get("completion_claim_allowed") is not False or completion_boundary.get("objective_complete") is not False:
        failures.append("thread dispatch record completion boundary is unsafe")
    if cleanup.get("worktree_audit", {}).get("stale_worker_checkout_present") is True:
        failures.append("stale worker checkout present")
    if worktree_source == "git" and unexpected_worktrees:
        failures.append("git worktree audit found unexpected worktrees: " + ", ".join(unexpected_worktrees))
    if worktree_source == "not_git_repository":
        failures.append("git worktree audit unavailable and no recorded cleanup evidence exists")
    if objective_standard.get("current_result") != "OBJECTIVE_COMPLETE: NO":
        failures.append("objective receipt does not preserve OBJECTIVE_COMPLETE: NO")
    if objective_qa.get("goal_should_remain_active") is not True:
        failures.append("objective receipt does not keep goal active")
    if release_boundary.get("completion_claim_allowed") is not False:
        failures.append("release receipt allows completion claim")
    if release_qa.get("goal_should_remain_active") is not True:
        failures.append("release receipt does not keep goal active")

    details = {
        "cleanup_run": cleanup_run,
        "cleanup_qa": cleanup_qa,
        "dispatch_record": dispatch_record,
        "thread_policy": thread_policy,
        "thread_budget": thread_budget,
        "dispatches": dispatches,
        "main_dispatches": main_dispatches,
        "worktrees": worktrees,
        "unexpected_worktrees": unexpected_worktrees,
        "worktree_source": worktree_source,
        "objective_standard": objective_standard,
        "release_boundary": release_boundary,
    }
    return failures, details


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative Codex Thread dispatch cleanup evidence.")
    parser.add_argument("--dispatch-record", default=str(CLEANUP_RECEIPT), help="YAML dispatch/cleanup record to audit.")
    parser.add_argument("--expect-failure", default="", help="Return success only if this failure text is present.")
    parser.add_argument(
        "--current-state",
        action="store_true",
        help="Audit current.json and current git worktree visibility without treating historical fixture receipts as live authority.",
    )
    parser.add_argument(
        "--check-git-worktrees",
        action="store_true",
        help="Kept for explicit caller intent; git worktree audit is always checked when available.",
    )
    args = parser.parse_args()

    if args.current_state:
        installed_package_layout = (ROOT / "SKILL.md").exists() and not (ROOT / ".git").exists()
        if installed_package_layout:
            runtime_files = sorted(
                path.relative_to(ROOT).as_posix()
                for path in (ROOT / ".dircreative").rglob("*")
                if path.is_file()
            )
            expected = [".dircreative/checkpoints/.keep", ".dircreative/runs/.keep"]
            current_ok = runtime_files == expected
            print("DIRcreative Current Thread/Worktree Audit")
            print("=" * 72)
            print("current_integrity: PACKAGE_RUNTIME_SENTINELS_ONLY")
            print("legacy_debt: PACKAGE_RUNTIME_SENTINELS_ONLY")
            print("current_thread_record_count: 0")
            print("git_worktree_evidence_source: not_applicable_installed_package")
            print("git_worktree_count: 0")
            print(f"THREAD_CURRENT_AUDIT: {'PASS' if current_ok else 'FAIL'}")
            return 0 if current_ok else 1

        state_proc = run(["python3", "scripts/dircreative_state_audit.py", "audit", "--json"])
        worktree_proc = run(["git", "worktree", "list", "--porcelain"])
        worktrees = [
            line.removeprefix("worktree ").strip()
            for line in worktree_proc.stdout.splitlines()
            if line.startswith("worktree ")
        ]
        try:
            state_report = json.loads(state_proc.stdout)
        except json.JSONDecodeError:
            state_report = {}
        current_ok = (
            state_proc.returncode == 0
            and state_report.get("current_integrity") == "PASS"
            and state_report.get("legacy_debt") == "NONE"
            and state_report.get("findings") == []
            and worktree_proc.returncode == 0
        )
        print("DIRcreative Current Thread/Worktree Audit")
        print("=" * 72)
        print(f"current_integrity: {state_report.get('current_integrity', 'UNKNOWN')}")
        print(f"legacy_debt: {state_report.get('legacy_debt', 'UNKNOWN')}")
        print(f"current_thread_record_count: {len(state_report.get('summary', {}).get('thread_record_ids', []))}")
        print("git_worktree_evidence_source: git")
        print(f"git_worktree_count: {len(worktrees)}")
        for worktree in worktrees:
            print(f"- {worktree}")
        print(f"THREAD_CURRENT_AUDIT: {'PASS' if current_ok else 'FAIL'}")
        return 0 if current_ok else 1

    cleanup = load_yaml(Path(args.dispatch_record))
    objective = load_yaml(OBJECTIVE_RECEIPT)
    release = load_yaml(RELEASE_RECEIPT)
    failures, details = build_failures(cleanup, objective, release)

    cleanup_run = details["cleanup_run"]
    cleanup_qa = details["cleanup_qa"]
    dispatch_record = details["dispatch_record"]
    thread_policy = details["thread_policy"]
    thread_budget = details["thread_budget"]
    dispatches = details["dispatches"]
    main_dispatches = details["main_dispatches"]
    worktrees = details["worktrees"]
    unexpected_worktrees = details["unexpected_worktrees"]
    worktree_source = details["worktree_source"]
    objective_standard = details["objective_standard"]
    release_boundary = details["release_boundary"]

    print("DIRcreative Thread Audit")
    print("=" * 72)
    print(f"dispatch_record_path: {Path(args.dispatch_record)}")
    print(f"main_controller_thread: {cleanup_run.get('main_controller_thread', {}).get('thread_id', '')}")
    print(f"main_controller_pinned: {str(cleanup_run.get('main_controller_thread', {}).get('pinned') is True).lower()}")
    print(f"disposable_workers_archived: {str(cleanup_qa.get('disposable_workers_archived') is True).lower()}")
    print(f"dispatch_record_present: {str(bool(dispatch_record)).lower()}")
    print(f"dispatch_count: {len(dispatches)}")
    print(f"pinned_controller_count: {len(main_dispatches)}")
    print(f"thread_budget_max_active_workers: {thread_budget.get('max_active_workers', '')}")
    print(f"thread_budget_active_worker_count: {thread_budget.get('active_worker_count', '')}")
    print(f"substantive_output_default_thread_class: {thread_policy.get('substantive_output_default_thread_class', '')}")
    print(f"read_only_worker_use: {thread_policy.get('read_only_worker_use', '')}")
    print(f"dispatches_have_professional_identity: {str(all(bool(item.get('professional_identity')) for item in dispatches)).lower()}")
    print(f"dispatches_have_stop_condition: {str(all(bool(item.get('stop_condition')) for item in dispatches)).lower()}")
    print(f"unintended_worker_worktrees_present: {str(cleanup_qa.get('unintended_worker_worktrees_present') is True).lower()}")
    print(f"git_worktree_evidence_source: {worktree_source}")
    print(f"git_worktree_count: {len(worktrees)}")
    print(f"unexpected_git_worktree_count: {len(unexpected_worktrees)}")
    print(f"objective_complete: {objective_standard.get('current_result', '')}")
    print(f"completion_claim_allowed: {str(release_boundary.get('completion_claim_allowed') is True).lower()}")
    if args.expect_failure:
        matched = any(args.expect_failure in failure for failure in failures)
        print(f"expected_failure: {args.expect_failure}")
        print(f"EXPECTED_FAILURE_MATCHED: {str(matched).lower()}")
        if failures:
            print("THREAD_AUDIT: FAIL")
            for failure in failures:
                print(f"- {failure}")
        return 0 if matched else 1
    if failures:
        print("THREAD_AUDIT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("THREAD_AUDIT: PASS")
    print("NOTE: Codex app thread visibility still requires main-controller tool check via list_threads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
