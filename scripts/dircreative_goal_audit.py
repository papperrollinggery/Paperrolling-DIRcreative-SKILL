#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dircreative_validation_harness import ROOT, has_terms, read

ACCEPTANCE_RECEIPT = ROOT / ".dircreative" / "runs" / "live-user-acceptance.yaml"
ACCEPTANCE_TEMPLATE = ROOT / "docs" / "film-preproduction" / "templates" / "live-user-acceptance.template.yaml"
REQUIRED_ACCEPTED_SCOPE = {
    "chat_first_flow",
    "director_room_collaboration",
    "professional_script",
    "dynamic_shot_design",
    "reference_pack_roles",
    "pre_generation_contracts",
    "image_prompt_summaries",
    "model_specific_video_prompts",
    "qa_retry_rules",
    "prompt_only_boundary",
    "assisted_generation_preflight",
    "installed_skill_behavior",
    "gstack_visual_dogfood",
    "council_adversarial_review_boundary",
    "thread_orchestration_cleanup",
}


@dataclass
class AuditItem:
    label: str
    status: str
    evidence: str


def load_yaml(path: Path) -> Any:
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}


def pass_if(label: str, ok: bool, evidence: str) -> AuditItem:
    return AuditItem(label, "PASS" if ok else "MISSING", evidence)


def live_acceptance_template_item() -> AuditItem:
    if not ACCEPTANCE_TEMPLATE.exists():
        return AuditItem(
            "live user acceptance receipt template",
            "MISSING",
            "docs/film-preproduction/templates/live-user-acceptance.template.yaml",
        )

    data = load_yaml(ACCEPTANCE_TEMPLATE)
    acceptance = data.get("user_acceptance", {})
    accepted_scope = data.get("accepted_scope", {})
    template_policy = data.get("acceptance_run", {}).get("template_policy", {})
    checklist = set(accepted_scope.get("checklist", []))
    ok = (
        data.get("artifact", {}).get("status") == "template"
        and acceptance.get("status") == "not_accepted"
        and acceptance.get("accepted_by_user") is False
        and acceptance.get("real_user_co_creation_verified") is False
        and template_policy.get("copy_only_after_real_user_acceptance") is True
        and template_policy.get("simulated_fixture_allowed") is False
        and REQUIRED_ACCEPTED_SCOPE.issubset(checklist)
        and data.get("qa_gate", {}).get("status") == "needs_user"
    )
    return AuditItem(
        "live user acceptance receipt template",
        "PASS" if ok else "MISSING",
        "docs/film-preproduction/templates/live-user-acceptance.template.yaml",
    )


def validate_live_user_acceptance(data: dict[str, Any]) -> tuple[bool, str]:
    acceptance = data.get("user_acceptance", {})
    acceptance_run = data.get("acceptance_run", {})
    chat_evidence = data.get("chat_evidence", {})
    council = chat_evidence.get("council_adversarial_review", {})
    thread = chat_evidence.get("thread_orchestration", {})
    accepted_scope = data.get("accepted_scope", {})
    unresolved = data.get("unresolved_blockers", {})
    qa_gate = data.get("qa_gate", {})

    required_pairs = [
        (data.get("artifact", {}).get("status") == "approved", "artifact.status must be approved"),
        (acceptance.get("status") == "accepted", "user_acceptance.status must be accepted"),
        (acceptance.get("accepted_by_user") is True, "accepted_by_user must be true"),
        (acceptance.get("real_user_co_creation_verified") is True, "real_user_co_creation_verified must be true"),
        (bool(acceptance.get("accepted_at")), "accepted_at is required"),
        (bool(acceptance.get("user_acceptance_statement")), "user_acceptance_statement is required"),
        (bool(acceptance.get("user_prompt_used_for_acceptance")), "user_prompt_used_for_acceptance is required"),
        (bool(acceptance.get("transcript_summary")), "transcript_summary is required"),
        (acceptance_run.get("run_type") == "live_user_acceptance", "acceptance_run.run_type must be live_user_acceptance"),
        (chat_evidence.get("evidence_source") == "real_user_chat", "chat_evidence.evidence_source must be real_user_chat"),
        (bool(chat_evidence.get("observed_stages")), "observed_stages are required"),
        (bool(chat_evidence.get("user_decisions_recorded")), "user_decisions_recorded are required"),
        (bool(chat_evidence.get("chat_transcript_artifacts")), "chat_transcript_artifacts are required"),
        (chat_evidence.get("installed_skill_checked") is True, "installed_skill_checked must be true"),
        (set(council.get("viewpoints", [])) == {"user", "professional_film_expert", "product_manager", "skill_developer", "code_researcher"}, "council viewpoints must be recorded"),
        (thread.get("thread_audit_passed") is True, "thread_audit_passed must be true"),
        (thread.get("disposable_workers_archived") is True, "disposable_workers_archived must be true"),
        (thread.get("unintended_worker_worktrees_present") is False, "unintended_worker_worktrees_present must be false"),
        (bool(thread.get("main_controller_thread_id")), "main_controller_thread_id is required"),
        (unresolved.get("items") == [], "unresolved_blockers.items must be empty"),
        (qa_gate.get("status") == "pass", "qa_gate.status must be pass"),
    ]
    for ok, reason in required_pairs:
        if not ok:
            return False, reason

    accepted_items = set(accepted_scope.get("accepted_items", []))
    missing_scope = sorted(REQUIRED_ACCEPTED_SCOPE - accepted_items)
    if missing_scope:
        return False, f"accepted_items missing: {', '.join(missing_scope)}"
    return True, ".dircreative/runs/live-user-acceptance.yaml"


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def live_user_acceptance_item(path: Path) -> AuditItem:
    if not path.exists():
        return AuditItem(
            "live user acceptance of chat experience",
            "NEEDS_USER",
            f"{display_path(path)} is not present; use docs/film-preproduction/templates/live-user-acceptance.template.yaml after real user acceptance",
        )

    data = load_yaml(path)
    ok, evidence = validate_live_user_acceptance(data)
    return AuditItem(
        "live user acceptance of chat experience",
        "PASS" if ok else "INVALID",
        evidence if ok else f"{display_path(path)}: {evidence}",
    )


def installed_skill_item(require_installed: bool) -> AuditItem:
    installed_skill = Path.home() / ".codex" / "skills" / "dircreative" / "SKILL.md"
    if installed_skill.exists() and "Live Chat Start Contract" in installed_skill.read_text(encoding="utf-8"):
        return AuditItem("installed local skill package", "PASS", str(installed_skill))
    if require_installed:
        return AuditItem("installed local skill package", "MISSING", str(installed_skill))
    return AuditItem(
        "installed local skill package",
        "PASS",
        "repo audit mode; release gate performs install and installed validation",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative against the active goal.")
    parser.add_argument(
        "--require-installed",
        action="store_true",
        help="Fail technical readiness if ~/.codex/skills/dircreative is missing or stale.",
    )
    parser.add_argument(
        "--acceptance-receipt",
        default=str(ACCEPTANCE_RECEIPT),
        help="Path to a live-user acceptance receipt. Defaults to .dircreative/runs/live-user-acceptance.yaml.",
    )
    args = parser.parse_args()
    acceptance_receipt = Path(args.acceptance_receipt)
    if not acceptance_receipt.is_absolute():
        acceptance_receipt = ROOT / acceptance_receipt

    root_skill = read("skills/dircreative/SKILL.md")
    rough_chat = read("examples/live-user-sim-noodle/16-chat-interface-demo.md")
    complete_chat = read("examples/complete-idea-segmentation-test/02-chat-transcript.md")
    goal_simulation = read("examples/goal-mode-simulation-test/01-chat-transcript.md")
    goal_rough_simulation = read("examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md")
    goal_simulation_protocol = read("docs/film-preproduction/goal-mode-simulation-protocol.md")
    complete_shots = read("examples/complete-idea-segmentation-test/03-shot-list.yaml")
    video_manifest = read("examples/live-user-sim-noodle/11-video-prompt-manifest.yaml")
    assisted_receipt = read("tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml")
    gstack_receipt = read("tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml")
    goal_mode_visual_receipt = read("tests/fixtures/runtime/runs/goal-mode-simulation-visual-dogfood-receipt.yaml")
    goal_mode_rough_visual_receipt = read("tests/fixtures/runtime/runs/goal-mode-rough-idea-visual-dogfood-receipt.yaml")
    quality_proc = subprocess.run(
        ["python3", "scripts/dircreative_quality_audit.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    quality_output = quality_proc.stdout + "\n" + quality_proc.stderr
    creative_production_proc = subprocess.run(
        ["python3", "scripts/dircreative_creative_production_audit.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    creative_production_output = creative_production_proc.stdout + "\n" + creative_production_proc.stderr
    goal_autorun_proc = subprocess.run(
        ["python3", "scripts/dircreative_goal_autorun_audit.py"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    goal_autorun_output = goal_autorun_proc.stdout + "\n" + goal_autorun_proc.stderr

    items = [
        pass_if(
            "chat-first rough idea flow",
            has_terms(rough_chat, ["阶段: 想法读取", "阶段: 导演组会议", "阶段: 5镜头分镜", "QA 与重试规则"]),
            "examples/live-user-sim-noodle/16-chat-interface-demo.md",
        ),
        pass_if(
            "complete idea segmentation flow",
            has_terms(complete_chat, ["阶段: 完整想法读取", "阶段: 导演组会议", "阶段: 专业分镜确认", "当前没有生成真实图片或视频"]),
            "examples/complete-idea-segmentation-test/02-chat-transcript.md",
        ),
        pass_if(
            "live chat start contract",
            has_terms(root_skill, ["Live Chat Start Contract", "阶段: 想法读取", "阶段: 完整想法读取", "pre_generation_contract.status: pass"]),
            "skills/dircreative/SKILL.md",
        ),
        pass_if(
            "goal-mode simulated user flow",
            has_terms(
                f"{root_skill}\n{goal_simulation_protocol}\n{goal_simulation}",
                [
                    "goal_context",
                    "阶段: 目标模式模拟测试",
                    "模拟用户选择",
                    "阶段: 出图执行建议",
                    "阶段: 出图执行建议",
                    "阶段: 视频生成建议",
                    "阶段: 模拟测试结论",
                    "不计入真实验收",
                    "live-user-acceptance.yaml",
                ],
            ),
            "docs/film-preproduction/goal-mode-simulation-protocol.md + examples/goal-mode-simulation-test/01-chat-transcript.md",
        ),
        pass_if(
            "goal-mode rough idea simulated flow",
            has_terms(
                f"{goal_simulation_protocol}\n{goal_rough_simulation}",
                [
                    "阶段: 想法读取",
                    "阶段: 导演组会议",
                    "阶段: 分镜头确认",
                    "阶段: 出图执行建议",
                    "阶段: 出图执行建议",
                    "阶段: 视频生成建议",
                    "阶段: 模拟测试结论",
                ],
            ),
            "examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md",
        ),
        pass_if(
            "professional dynamic shot density",
            has_terms(complete_shots, ["shot_count_rationale", "narrative_purpose", "shot_size", "lens", "camera_motion", "audio", "model_notes"]),
            "examples/complete-idea-segmentation-test/03-shot-list.yaml",
        ),
        pass_if(
            "model-specific video prompts",
            has_terms(video_manifest, ["seedance", "kling", "runway", "veo", "audio_policy", "retry_rules"]),
            "examples/live-user-sim-noodle/11-video-prompt-manifest.yaml",
        ),
        pass_if(
            "assisted generation preflight blocks unsafe media",
            has_terms(assisted_receipt, ["visual_output_mode: assisted_generation", "reject_for_revision", "user_lock_required_before_video: true"]),
            "tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml",
        ),
        pass_if(
            "gstack visual dogfood evidence",
            has_terms(gstack_receipt, ["tool: gstack browse", "console_status: no_console_messages", "gstack_opened_pages: true"]),
            "tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml",
        ),
        pass_if(
            "goal-mode simulation browser dogfood evidence",
            has_terms(goal_mode_visual_receipt, ["tool: local_browser_playwright", "goal_mode_simulation_page", "console_status: no_console_messages", "live_acceptance_not_claimed: true"]),
            "tests/fixtures/runtime/runs/goal-mode-simulation-visual-dogfood-receipt.yaml",
        ),
        pass_if(
            "goal-mode rough idea browser dogfood evidence",
            has_terms(goal_mode_rough_visual_receipt, ["tool: local_browser_playwright", "goal_mode_rough_idea_page", "console_status: no_console_messages", "live_acceptance_not_claimed: true"]),
            "tests/fixtures/runtime/runs/goal-mode-rough-idea-visual-dogfood-receipt.yaml",
        ),
        pass_if(
            "film/commercial quality audit",
            quality_proc.returncode == 0 and has_terms(quality_output, ["QUALITY_AUDIT: PASS", "film_grade_ready: true", "commercial_grade_ready: true"]),
            "scripts/dircreative_quality_audit.py",
        ),
        pass_if(
            "Creative Production adapter audit",
            creative_production_proc.returncode == 0
            and has_terms(creative_production_output, ["CREATIVE_PRODUCTION_AUDIT: PASS", "adapter_source_of_truth: dircreative_artifacts", "render_moodboard_board_widget"]),
            "scripts/dircreative_creative_production_audit.py",
        ),
        pass_if(
            "Goal autorun dry-run audit",
            goal_autorun_proc.returncode == 0
            and has_terms(goal_autorun_output, ["GOAL_AUTORUN_AUDIT: PASS", "goal_autorun_dry_run_complete: true", "real_media_generated: false"]),
            "scripts/dircreative_goal_autorun_audit.py",
        ),
        installed_skill_item(args.require_installed),
        live_acceptance_template_item(),
        live_user_acceptance_item(acceptance_receipt),
    ]

    invalid_acceptance = any(item.status == "INVALID" for item in items)
    technical_statuses = [
        item.status
        for item in items
        if item.label != "live user acceptance of chat experience"
    ]
    technical_ready = all(status == "PASS" for status in technical_statuses)
    goal_complete = technical_ready and all(item.status == "PASS" for item in items)

    print("DIRcreative Goal Completion Audit")
    print("=" * 72)
    for item in items:
        print(f"[{item.status}] {item.label}")
        print(f"       evidence: {item.evidence}")
    print(f"TECHNICAL_READINESS: {'PASS' if technical_ready else 'FAIL'}")
    print(f"GOAL_COMPLETE: {'YES' if goal_complete else 'NO'}")
    if not goal_complete:
        print("NEXT_REQUIRED_ACTION: run a real chat acceptance pass with the user and record live-user-acceptance.yaml")
    if invalid_acceptance:
        print("INVALID_ACCEPTANCE_RECEIPT: fix or remove .dircreative/runs/live-user-acceptance.yaml")
    return 0 if technical_ready and not invalid_acceptance else 1


if __name__ == "__main__":
    raise SystemExit(main())
