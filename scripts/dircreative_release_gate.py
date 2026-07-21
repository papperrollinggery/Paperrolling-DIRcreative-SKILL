#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


@dataclass
class Step:
    label: str
    cmd: list[str]
    cwd: Path
    env: dict[str, str] | None = None
    depends_on: str | None = None


def run_step(step: Step) -> tuple[bool, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if step.env:
        env.update(step.env)
    proc = subprocess.run(
        step.cmd,
        cwd=step.cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode == 0, output


def read_head() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    value = proc.stdout.strip()
    if proc.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError(proc.stderr.strip() or "cannot resolve one exact release commit")
    return value


def sealed_head_unchanged(
    sealed_commit: str,
    *,
    reader: Callable[[], str] = read_head,
) -> bool:
    try:
        return reader() == sealed_commit
    except ValueError:
        return False


def validate_explicit_staging_target(target: Path) -> None:
    temporary_root = Path(tempfile.gettempdir()).resolve(strict=False)
    resolved = target.expanduser().resolve(strict=False)
    source_root = ROOT.resolve(strict=False)
    if resolved.exists() or resolved.is_symlink():
        raise ValueError("explicit release staging target must not already exist")
    try:
        resolved.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ValueError("explicit release staging target must not be inside the source package root")
    try:
        source_root.relative_to(resolved)
    except ValueError:
        pass
    else:
        raise ValueError("explicit release staging target must not contain the source package root")
    try:
        relative = resolved.relative_to(temporary_root)
    except ValueError as exc:
        raise ValueError(
            f"explicit release staging target must be inside the OS temporary root: {temporary_root}"
        ) from exc
    if not relative.parts:
        raise ValueError("explicit release staging target must be a child of the OS temporary root")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DIRcreative release gate.")
    parser.add_argument(
        "--install-target",
        help="Optional absent path inside the OS temp root. Defaults to an isolated temporary staging target.",
    )
    parser.add_argument(
        "--adco-repo",
        help="Optional ADCO checkout for the real bilateral compatibility gate.",
    )
    parser.add_argument(
        "--media-forward-receipt",
        help="Absolute receipt for a real image-generation forward test bound to this candidate.",
    )
    parser.add_argument(
        "--media-review-receipt",
        help="Absolute independent visual-review receipt bound to the media execution receipt.",
    )
    parser.add_argument(
        "--media-host-event-log",
        help="Absolute Codex JSONL task log for the candidate execution trace prefix.",
    )
    parser.add_argument(
        "--media-review-host-event-log",
        help="Absolute Codex JSONL task log from the separate visual-review task.",
    )
    parser.add_argument(
        "--require-media-forward",
        action="store_true",
        help="Fail unless a valid real-media forward-test receipt is supplied.",
    )
    parser.add_argument(
        "--media-c2patool",
        help="Absolute pinned c2patool verifier required with --media-forward-receipt.",
    )
    parser.add_argument(
        "--require-tag",
        action="store_true",
        help="Require v<VERSION> to point to the exact release commit.",
    )
    parser.add_argument(
        "--allow-unpublished",
        action="store_true",
        help="CI/development only: skip main and origin/main equality while retaining clean-tree checks.",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        help="Directory for the exact-commit release artifact.",
    )
    args = parser.parse_args()
    if args.require_tag and args.allow_unpublished:
        parser.error("--require-tag and --allow-unpublished are mutually exclusive")
    if args.require_media_forward and (
        not args.media_forward_receipt
        or not args.media_review_receipt
        or not args.media_host_event_log
        or not args.media_review_host_event_log
    ):
        parser.error(
            "--require-media-forward requires both media receipts and both host event logs"
        )
    if args.media_review_receipt and not args.media_forward_receipt:
        parser.error("--media-review-receipt requires --media-forward-receipt")
    if (args.media_host_event_log or args.media_review_host_event_log) and not args.media_forward_receipt:
        parser.error("media host event logs require --media-forward-receipt")
    if args.media_forward_receipt and not Path(args.media_forward_receipt).expanduser().is_absolute():
        parser.error("--media-forward-receipt must be an absolute path")
    if args.media_review_receipt and not Path(args.media_review_receipt).expanduser().is_absolute():
        parser.error("--media-review-receipt must be an absolute path")
    for option, value in (
        ("--media-host-event-log", args.media_host_event_log),
        ("--media-review-host-event-log", args.media_review_host_event_log),
    ):
        if value and not Path(value).expanduser().is_absolute():
            parser.error(f"{option} must be an absolute path")
    if args.media_forward_receipt and not args.media_c2patool:
        parser.error("--media-forward-receipt requires --media-c2patool")
    if args.media_c2patool and not Path(args.media_c2patool).expanduser().is_absolute():
        parser.error("--media-c2patool must be an absolute path")
    if args.install_target:
        target = Path(args.install_target).expanduser().resolve(strict=False)
        try:
            validate_explicit_staging_target(target)
        except ValueError as exc:
            parser.error(str(exc))
        with tempfile.TemporaryDirectory(prefix="dircreative-release-scratch-") as scratch:
            result = run_gate(args, target, Path(scratch))
        print("release_scratch_cleanup: complete")
        return result
    with (
        tempfile.TemporaryDirectory(prefix="dircreative-release-stage-") as raw,
        tempfile.TemporaryDirectory(prefix="dircreative-release-scratch-") as scratch,
    ):
        result = run_gate(args, Path(raw) / "dircreative", Path(scratch))
    print("staged_install_cleanup: complete")
    print("release_scratch_cleanup: complete")
    return result


def run_gate(
    args: argparse.Namespace,
    target: Path,
    scratch: Path,
    *,
    sealed_commit: str | None = None,
    head_reader: Callable[[], str] = read_head,
) -> int:
    sealed_commit = sealed_commit or head_reader()
    if not re.fullmatch(r"[0-9a-f]{40}", sealed_commit):
        raise ValueError("release gate requires one full lowercase sealed commit SHA")
    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    artifact = output_dir / f"dircreative-{version}.tar.gz"
    checksums = output_dir / "SHA256SUMS"
    archive_install_target = scratch / "archive-installed"

    preflight_cmd = [
        "python3",
        "scripts/dircreative_release_preflight.py",
        "--expected-commit",
        sealed_commit,
    ]
    build_cmd = [
        "python3",
        "scripts/dircreative_build_release.py",
        "--output-dir",
        str(output_dir),
        "--expected-commit",
        sealed_commit,
    ]
    require_tag = not args.allow_unpublished
    if require_tag:
        preflight_cmd.append("--require-tag")
        build_cmd.append("--require-tag")
    if args.allow_unpublished:
        preflight_cmd.append("--allow-unpublished")
        build_cmd.append("--allow-unpublished")
    formal_install_cmd = [
        "python3",
        "scripts/install_local_skill.py",
        "--target",
        str(archive_install_target),
        "--formal-install",
        "--artifact",
        str(artifact),
        "--checksums",
        str(checksums),
        "--expected-commit",
        sealed_commit,
        "--expected-tag",
        f"v{version}",
        "--reproducible-source",
        str(ROOT),
    ]
    if args.allow_unpublished:
        formal_install_cmd.append("--allow-unpublished")

    steps = [
        Step("exact commit release preflight", preflight_cmd, ROOT),
        Step("repo validation", ["python3", "scripts/validate_project.py"], ROOT),
        Step("project AGENTS audit", ["python3", "scripts/dircreative_project_agents.py", "audit-repo"], ROOT),
        Step("rough idea status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/live-user-sim-noodle"], ROOT),
        Step("complete idea status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/complete-idea-segmentation-test"], ROOT),
        Step("goal-mode simulation status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/goal-mode-simulation-test"], ROOT),
        Step("goal-mode rough idea status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/goal-mode-rough-idea-simulation-test"], ROOT),
        Step("readiness audit", ["python3", "scripts/dircreative_readiness_audit.py"], ROOT),
        Step("film/commercial quality audit", ["python3", "scripts/dircreative_quality_audit.py"], ROOT),
        Step("Creative Production adapter audit", ["python3", "scripts/dircreative_creative_production_audit.py"], ROOT),
        Step("ADCO native exchange audit", ["python3", "scripts/dircreative_adco_native_exchange.py", "--self-test"], ROOT),
        Step("Goal autorun dry-run audit", ["python3", "scripts/dircreative_goal_autorun_audit.py"], ROOT),
        Step("loop engineering audit", ["python3", "scripts/dircreative_loop_engineering_audit.py"], ROOT),
        Step("second-level dispatch audit", ["python3", "scripts/dircreative_second_level_dispatch_audit.py"], ROOT),
        Step("director-room harness behavior audit", ["python3", "scripts/dircreative_director_harness_audit.py"], ROOT),
        Step("creative copy deck behavior audit", ["python3", "scripts/dircreative_creative_copy_deck_audit.py"], ROOT),
        Step("model capability behavior audit", ["python3", "scripts/dircreative_model_capability_audit.py"], ROOT),
        Step("runtime state audit", ["python3", "scripts/dircreative_state_audit.py", "self-test"], ROOT),
        Step(
            "runtime state builtin-validator audit",
            ["python3", "scripts/dircreative_state_audit.py", "self-test"],
            ROOT,
            {"DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR": "1"},
        ),
        Step("visual dogfood pages", ["python3", "scripts/dircreative_visual_dogfood.py"], ROOT),
        Step("install local skill", ["python3", "scripts/install_local_skill.py", "--target", str(target)], ROOT),
        Step("installed parity audit", ["python3", "scripts/dircreative_install_parity.py", "--target", str(target)], ROOT),
        Step("installed skill validation", ["python3", "scripts/validate_project.py"], target),
        Step("installed rough idea status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/live-user-sim-noodle"], target),
        Step("installed complete idea status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/complete-idea-segmentation-test"], target),
        Step("installed goal-mode simulation status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/goal-mode-simulation-test"], target),
        Step("installed goal-mode rough idea status", ["python3", "scripts/dircreative_run.py", "status", "--example", "examples/goal-mode-rough-idea-simulation-test"], target),
        Step("goal completion audit (boundary-only)", ["python3", "scripts/dircreative_goal_audit.py"], ROOT),
        Step("objective completion audit (boundary-only)", ["python3", "scripts/dircreative_objective_audit.py"], ROOT),
        Step("progress report", ["python3", "scripts/dircreative_progress_report.py"], ROOT),
        Step("acceptance boundary preflight", ["python3", "scripts/dircreative_acceptance_preflight.py"], ROOT),
        Step("council audit", ["python3", "scripts/dircreative_council_audit.py"], ROOT),
        Step("thread audit", ["python3", "scripts/dircreative_thread_audit.py"], ROOT),
        Step("chat surface order audit", ["python3", "scripts/dircreative_chat_surface_audit.py"], ROOT),
        Step("diff whitespace check", ["git", "diff", "--check"], ROOT),
        Step("release artifact build", build_cmd, ROOT),
        Step(
            "verified formal artifact install",
            formal_install_cmd,
            ROOT,
            depends_on="release artifact build",
        ),
        Step(
            "release artifact install parity",
            [
                "python3",
                "scripts/dircreative_install_parity.py",
                "--target",
                str(archive_install_target),
            ],
            ROOT,
            depends_on="verified formal artifact install",
        ),
        Step(
            "release artifact installed validation",
            ["python3", "scripts/validate_project.py"],
            archive_install_target,
            depends_on="release artifact install parity",
        ),
    ]
    if args.media_forward_receipt:
        receipt = Path(args.media_forward_receipt).expanduser()
        media_cmd = [
            "python3",
            "scripts/dircreative_media_forward_audit.py",
            "--receipt",
            str(receipt),
            "--expected-commit",
            sealed_commit,
            "--c2patool",
            str(Path(args.media_c2patool).expanduser()),
        ]
        if args.media_review_receipt:
            media_cmd.extend(
                [
                    "--review-receipt",
                    str(Path(args.media_review_receipt).expanduser()),
                ]
            )
        if args.media_host_event_log:
            media_cmd.extend(
                ["--host-event-log", str(Path(args.media_host_event_log).expanduser())]
            )
        if args.media_review_host_event_log:
            media_cmd.extend(
                [
                    "--review-host-event-log",
                    str(Path(args.media_review_host_event_log).expanduser()),
                ]
            )
        if args.require_media_forward:
            media_cmd.append("--require-candidate-skill-execution")
        insertion_index = next(
            index for index, step in enumerate(steps) if step.label == "Goal autorun dry-run audit"
        )
        steps.insert(
            insertion_index,
            Step(
                "real image media-forward audit",
                media_cmd,
                ROOT,
            ),
        )
    if args.adco_repo:
        adco_repo = Path(args.adco_repo).expanduser().resolve()
        insertion_index = next(
            index for index, step in enumerate(steps) if step.label == "Goal autorun dry-run audit"
        )
        steps.insert(
            insertion_index,
            Step(
                "ADCO native bilateral audit",
                [
                    "python3",
                    "scripts/dircreative_adco_native_exchange.py",
                    "--adco-repo",
                    str(adco_repo),
                ],
                ROOT,
            ),
        )
        archive_bilateral_index = next(
            index
            for index, step in enumerate(steps)
            if step.label == "release artifact installed validation"
        ) + 1
        steps.insert(
            archive_bilateral_index,
            Step(
                "release artifact installed ADCO bilateral",
                [
                    "python3",
                    "scripts/dircreative_adco_native_exchange.py",
                    "--adco-repo",
                    str(adco_repo),
                ],
                archive_install_target,
                depends_on="release artifact installed validation",
            ),
        )

    print("DIRcreative Release Gate")
    print("=" * 72)
    print(
        "RELEASE_GATE_SCOPE: BILATERAL"
        if args.adco_repo
        else "RELEASE_GATE_SCOPE: DIR_ONLY (ADCO bilateral audit not run)"
    )
    print(
        "MEDIA_FORWARD_SCOPE: UNSIGNED_HOST_TRACE_IMAGE_PLUS_INDEPENDENT_REVIEW"
        if args.require_media_forward
        else "MEDIA_FORWARD_SCOPE: PROVENANCE_ONLY_ALLOWED"
        if args.media_forward_receipt
        else "MEDIA_FORWARD_SCOPE: NOT_RUN"
    )
    failures: list[tuple[Step, str]] = []
    step_results: dict[str, bool] = {}
    for step in steps:
        if step.label == "release artifact build" and failures:
            print("[SKIP] release artifact build (one or more pre-artifact gates failed)")
            step_results[step.label] = False
            continue
        if step.depends_on and not step_results.get(step.depends_on, False):
            print(f"[SKIP] {step.label} (dependency failed: {step.depends_on})")
            step_results[step.label] = False
            continue
        ok, output = run_step(step)
        step_results[step.label] = ok
        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {step.label}")
        if output:
            important_lines = [
                line
                for line in output.splitlines()
                if line.startswith(("ok ", "STATUS:", "READINESS:", "QUALITY_AUDIT:", "CREATIVE_PRODUCTION_AUDIT:", "ADCO_NATIVE_", "DIRCREATIVE_MEDIA_FORWARD_AUDIT:", "media_provenance:", "candidate_skill_execution:", "tool_request_binding:", "independent_visual_review:", "continuity_quality:", "video_verified:", "GOAL_AUTORUN_AUDIT:", "LOOP_ENGINEERING_AUDIT:", "SECOND_LEVEL_DISPATCH_AUDIT:", "DIRCREATIVE_DIRECTOR_HARNESS_AUDIT:", "DIRCREATIVE_CREATIVE_COPY_DECK_AUDIT:", "DIRCREATIVE_MODEL_CAPABILITY_AUDIT:", "DIRCREATIVE_STATE_AUDIT_SELF_TEST=", "RELEASE_PREFLIGHT:", "RELEASE_BUILD:", "RELEASE_ARTIFACT_VERIFY:", "formal_release_commit:", "formal_artifact_sha256:", "formal_manifest_sha256:", "FORMAL_INSTALL_MODE:", "PROJECT_AGENTS_AUDIT:", "film_grade_ready:", "commercial_grade_ready:", "adapter_source_of_truth:", "review_surface:", "goal_autorun_dry_run_complete:", "real_media_generated:", "typed_action_observation_contract:", "receipt_persistence_contract:", "retry_loop_contract:", "council_review_contract:", "codex_thread_boundary_contract:", "second_level_dispatch_contract:", "goal_autorun_dry_run_boundary:", "live_acceptance_boundary:", "creative_quality_approval_claimed:", "stateless_subagent_tool_verdict:", "negative_fixture_rejected:", "second_level_subagents_are_durable_truth:", "second_level_subagents_may_write_live_acceptance:", "second_level_subagents_may_mark_goal_complete:", "VISUAL_DOGFOOD_PAGES:", "INSTALL_PARITY:", "TECHNICAL_READINESS:", "GOAL_COMPLETE:", "OBJECTIVE_TECHNICAL_READINESS:", "OBJECTIVE_COMPLETE:", "COUNCIL_AUDIT:", "THREAD_AUDIT:", "CHAT_SURFACE_AUDIT:", "NEXT_REQUIRED_ACTION:", "completion_estimate_percent:", "technical_readiness:", "objective_complete:", "remaining_blocker:", "estimated_remaining_time:", "latest_commit:", "worktree_state:", "required_viewpoints_present:", "council_trigger_surface_present:", "external_research_boundary_present:", "failure_ids_present:", "main_controller_pinned:", "disposable_workers_archived:", "unintended_worker_worktrees_present:", "git_worktree_count:", "completion_claim_allowed:", "runbook_present:", "template_guarded:", "live_receipt_absent:", "technical_readiness_pass:", "objective_still_blocked:", "receipt_creation_allowed:", "acceptance_mode:", "require_installed:", "installed DIRcreative", "NOTE:", "NEXT_USER_DECISION:"))
            ]
            for line in important_lines[-8:]:
                print(f"       {line}")
        if not ok:
            failures.append((step, output))

    seal_step = Step("sealed commit final readback", ["git", "rev-parse", "HEAD"], ROOT)
    seal_ok = sealed_head_unchanged(sealed_commit, reader=head_reader)
    print(f"[{'PASS' if seal_ok else 'FAIL'}] {seal_step.label}")
    if not seal_ok:
        failures.append((seal_step, "HEAD changed during the release gate"))

    if failures:
        gate_marker = (
            "BILATERAL_MEDIA_RELEASE_GATE"
            if args.adco_repo and args.require_media_forward
            else "BILATERAL_RELEASE_GATE"
            if args.adco_repo
            else "DIR_MEDIA_RELEASE_GATE"
            if args.require_media_forward
            else "DIR_RELEASE_GATE"
        )
        print(f"{gate_marker}: FAIL")
        print("PRE_RELEASE_GATE: FAIL" if args.allow_unpublished else "RELEASE_GATE: FAIL")
        for step, output in failures:
            print(f"\n--- {step.label} output ---")
            print(output)
        return 1

    gate_marker = (
        "BILATERAL_MEDIA_RELEASE_GATE"
        if args.adco_repo and args.require_media_forward
        else "BILATERAL_RELEASE_GATE"
        if args.adco_repo
        else "DIR_MEDIA_RELEASE_GATE"
        if args.require_media_forward
        else "DIR_RELEASE_GATE"
    )
    print(f"{gate_marker}: PASS")
    print("PRE_RELEASE_GATE: PASS" if args.allow_unpublished else "RELEASE_GATE: PASS")
    print(f"staged_install_target: {target}")
    print(f"release_artifact: {artifact}")
    print(f"release_checksums: {checksums}")
    print(f"verified_archive_install: {archive_install_target}")
    print("visual_dogfood_index: /tmp/dircreative-visual-dogfood/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
