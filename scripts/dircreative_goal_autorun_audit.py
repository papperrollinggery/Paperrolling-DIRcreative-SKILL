#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from typing import Any

from dircreative_validation_harness import Check, ROOT, add_check, read, require_terms


TRANSCRIPT = "examples/goal-mode-autorun-commercial-cp-test/01-chat-transcript.md"
RUN = "examples/goal-mode-autorun-commercial-cp-test/15-co-creation-run.yaml"


def load_yaml(path: str) -> dict[str, Any]:
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(ROOT / path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"YAML parse failed for {path}: {proc.stderr}")
    return json.loads(proc.stdout)


def every_confirmation_has_simulated_choice(text: str) -> None:
    stage_blocks = text.split("阶段:")
    missing: list[str] = []
    for block in stage_blocks:
        has_user_confirmation = any(line.strip().startswith("用户确认点:") for line in block.splitlines())
        if has_user_confirmation and "模拟用户选择:" not in block:
            title = block.splitlines()[0].strip() if block.splitlines() else "unknown"
            missing.append(title)
    if missing:
        raise AssertionError(f"stages missing simulated choice: {missing}")


def validate_autorun_run(path: str) -> None:
    data = load_yaml(path)
    run = data.get("co_creation_run", {})
    if run.get("run_type") != "dry_run_fixture":
        raise AssertionError(f"{path} must be dry_run_fixture")
    if run.get("simulated_choices_allowed") is not True:
        raise AssertionError(f"{path} must allow simulated choices")
    if run.get("real_user_co_creation_verified") is not False:
        raise AssertionError(f"{path} cannot verify real user co-creation")
    if run.get("live_user_acceptance_receipt_written") is not False:
        raise AssertionError(f"{path} cannot write live acceptance")
    if run.get("real_media_generated") is not False:
        raise AssertionError(f"{path} cannot generate real media")
    if run.get("creative_production_preflight_included") is not True:
        raise AssertionError(f"{path} must include Creative Production preflight")

    gates = data.get("gates", [])
    if len(gates) < 11:
        raise AssertionError(f"{path} must include all required co-creation gates")
    for gate in gates:
        if gate.get("decision_source") != "simulated_fixture":
            raise AssertionError(f"{path} gate {gate.get('gate_id')} must use simulated_fixture")
    qa = data.get("qa", {})
    for key in [
        "all_required_gates_present",
        "simulated_choices_labeled",
        "creative_production_preflight_without_execution",
        "no_real_media_generated",
        "live_acceptance_not_claimed",
    ]:
        if qa.get(key) is not True:
            raise AssertionError(f"{path} QA missing or false: {key}")


def invalid_autorun_must_fail() -> None:
    data = load_yaml("tests/fixtures/invalid-goal-autorun-live-acceptance.yaml")
    run = data.get("co_creation_run", {})
    qa = data.get("qa", {})
    invalid = (
        run.get("run_type") == "dry_run_fixture"
        and (
            run.get("real_user_co_creation_verified") is True
            or run.get("live_user_acceptance_receipt_written") is True
            or qa.get("live_acceptance_not_claimed") is False
        )
    )
    if not invalid:
        raise AssertionError("invalid goal autorun fixture did not express the forbidden live acceptance claim")


def main() -> int:
    checks: list[Check] = []

    add_check(
        checks,
        "autorun protocol exists",
        "docs/film-preproduction/goal-autorun-completion-protocol.md",
        lambda: require_terms(
            read("docs/film-preproduction/goal-autorun-completion-protocol.md"),
            [
                "Goal Autorun Completion Protocol",
                "rough idea path",
                "complete idea segmentation path",
                "commercial/product-ad path",
                "Creative Production generation preflight path",
                "未生成真实图片/视频: true",
                "不计入真实验收: true",
                "dircreative_goal_autorun_audit.py",
            ],
            "goal autorun protocol",
        ),
    )
    add_check(
        checks,
        "autorun transcript covers required stages",
        TRANSCRIPT,
        lambda: require_terms(
            read(TRANSCRIPT),
            [
                "阶段: 目标模式模拟测试",
                "阶段: 想法读取",
                "阶段: 完整想法读取",
                "阶段: 导演组会议",
                "阶段: 故事逻辑确认",
                "阶段: 专业分镜确认",
                "阶段: 参考图组方案",
                "阶段: 出图执行建议",
                "Creative Production",
                "render_moodboard_board_widget",
                "阶段: 视频生成建议",
                "阶段: QA 与重试规则",
                "阶段: 模拟测试结论",
                "结果: PASS",
                "未生成真实图片/视频: true",
                "不计入真实验收: true",
                "下一步真实用户确认点",
            ],
            "goal autorun transcript",
        ),
    )
    add_check(
        checks,
        "every user confirmation has simulated choice",
        TRANSCRIPT,
        lambda: every_confirmation_has_simulated_choice(read(TRANSCRIPT)),
    )
    add_check(checks, "autorun co-creation run is valid", RUN, lambda: validate_autorun_run(RUN))
    add_check(
        checks,
        "forbidden live acceptance claim is covered by negative fixture",
        "tests/fixtures/invalid-goal-autorun-live-acceptance.yaml",
        invalid_autorun_must_fail,
    )
    add_check(
        checks,
        "goal audit still requires real acceptance",
        "live acceptance boundary docs",
        lambda: require_terms(
            read("docs/film-preproduction/live-user-acceptance-gate.md")
            + "\n"
            + read("docs/film-preproduction/current-project-progress.md"),
            [
                "real user acceptance",
                "GOAL_COMPLETE: YES",
                "GOAL_COMPLETE: NO",
                "OBJECTIVE_COMPLETE: NO",
            ],
            "live acceptance boundary docs",
        ),
    )

    print("DIRcreative Goal Autorun Audit")
    print("=" * 72)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.label}")
        print(f"       evidence: {check.evidence}")
    failures = [check for check in checks if not check.ok]
    if failures:
        print("GOAL_AUTORUN_AUDIT: FAIL")
        return 1
    print("goal_autorun_dry_run_complete: true")
    print("real_media_generated: false")
    print("live_acceptance_required: true")
    print("GOAL_AUTORUN_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
