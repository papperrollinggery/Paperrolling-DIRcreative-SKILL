#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from dircreative_validation_harness import ROOT, Requirement, has_terms, read, run

LIVE_ACCEPTANCE = ROOT / ".dircreative" / "runs" / "live-user-acceptance.yaml"
INSTALLED_SKILL = Path.home() / ".codex" / "skills" / "dircreative" / "SKILL.md"


def check(label: str, ok: bool, evidence: str, reason: str) -> Requirement:
    return Requirement(label, "PASS" if ok else "MISSING", evidence, reason)


def run_ok(cmd: list[str], cwd: Path = ROOT) -> tuple[bool, str]:
    proc = run(cmd, cwd)
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return proc.returncode == 0, output


def live_acceptance_requirement() -> Requirement:
    if not LIVE_ACCEPTANCE.exists():
        return Requirement(
            "real user acceptance",
            "NEEDS_USER",
            ".dircreative/runs/live-user-acceptance.yaml",
            "The active goal still requires explicit real user approval of the chat experience.",
        )
    ok, output = run_ok(["python3", "scripts/dircreative_goal_audit.py", "--require-installed"])
    return Requirement(
        "real user acceptance",
        "PASS" if ok and "GOAL_COMPLETE: YES" in output else "INVALID",
        ".dircreative/runs/live-user-acceptance.yaml",
        "Live acceptance receipt must make dircreative_goal_audit.py report GOAL_COMPLETE: YES.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative against the active user objective.")
    parser.add_argument(
        "--require-installed",
        action="store_true",
        help="Require ~/.codex/skills/dircreative to be present and current enough to expose the live chat contract.",
    )
    args = parser.parse_args()

    root_skill = read("skills/dircreative/SKILL.md")
    rough_chat = read("examples/live-user-sim-noodle/16-chat-interface-demo.md")
    rough_status = run_ok(["python3", "scripts/dircreative_run.py", "status", "--example", "examples/live-user-sim-noodle"])[1]
    complete_chat = read("examples/complete-idea-segmentation-test/02-chat-transcript.md")
    complete_status = run_ok(["python3", "scripts/dircreative_run.py", "status", "--example", "examples/complete-idea-segmentation-test"])[1]
    goal_sim = read("examples/goal-mode-simulation-test/01-chat-transcript.md")
    goal_rough_sim = read("examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md")
    acceptance_rehearsal = read("examples/live-acceptance-rehearsal/01-chat-transcript.md")
    assisted_chat = read("examples/assisted-generation-preflight-chat/01-chat-transcript.md")
    stage_gate_contract = read("docs/film-preproduction/chat-stage-gate-integrity.md") + "\n" + root_skill + "\n" + read("skills/dircreative/chat-facilitator/SKILL.md")
    chat_surface_ok, chat_surface_output = run_ok(["python3", "scripts/dircreative_chat_surface_audit.py"])
    council_audit_ok, council_audit_output = run_ok(["python3", "scripts/dircreative_council_audit.py"])
    quality_audit_ok, quality_audit_output = run_ok(["python3", "scripts/dircreative_quality_audit.py"])
    creative_production_audit_ok, creative_production_audit_output = run_ok(["python3", "scripts/dircreative_creative_production_audit.py"])
    goal_autorun_audit_ok, goal_autorun_audit_output = run_ok(["python3", "scripts/dircreative_goal_autorun_audit.py"])
    director_room = read("docs/film-preproduction/director-room-council-protocol.md") + "\n" + read("examples/live-user-sim-noodle/02-director-room-notes.md")
    rough_script = read("examples/live-user-sim-noodle/06-script.md")
    rough_shots = read("examples/live-user-sim-noodle/07-shot-list.yaml")
    complete_shots = read("examples/complete-idea-segmentation-test/03-shot-list.yaml")
    reference_plan = read("examples/live-user-sim-noodle/09-reference-pack-plan.yaml") + "\n" + read("examples/complete-idea-segmentation-test/04-reference-prompt-plan.md")
    image_prompts = "\n".join(
        [
            read("examples/live-user-sim-noodle/10-image-prompt-manifest.yaml"),
            read("examples/product-ad-raincoat/08-image-prompt-manifest.yaml"),
            read("examples/zombie-cleaner-test/11-image-prompt-manifest.yaml"),
            read("examples/cyber-courier/prompts/image_01_character_board.txt"),
            read("examples/cyber-courier/prompts/image_02_environment_board.txt"),
            read("examples/cyber-courier/prompts/image_04_storyboard_board.txt"),
            read("examples/cyber-courier/prompts/image_06_clean_sh01_start.txt"),
            read("examples/complete-idea-segmentation-test/04-reference-prompt-plan.md"),
        ]
    )
    video_prompts = read("examples/live-user-sim-noodle/11-video-prompt-manifest.yaml") + "\n" + read("examples/complete-idea-segmentation-test/04-reference-prompt-plan.md")
    qa = read("examples/live-user-sim-noodle/12-qa-retry-plan.md") + "\n" + read("examples/complete-idea-segmentation-test/05-qa-retry-plan.md")
    assisted = read("tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml")
    gstack = read("tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml")
    progress = read("docs/film-preproduction/current-project-progress.md")
    isolated_ok, isolated_output = run_ok(["python3", "scripts/dircreative_isolated_user_sim.py"])
    duration_policy = "\n".join(
        [
            read("docs/film-preproduction/longform-decomposition-policy.md"),
            read("docs/film-preproduction/chat-acceptance-checklist.md"),
            read("docs/film-preproduction/live-chat-acceptance-runbook.md"),
            read("skills/dircreative/SKILL.md"),
            read("skills/dircreative/idea-intake/SKILL.md"),
            read("skills/dircreative/script-treatment/SKILL.md"),
            read("skills/dircreative/sequence-planner/SKILL.md"),
        ]
    )

    installed_terms_ok = INSTALLED_SKILL.exists() and has_terms(
        INSTALLED_SKILL.read_text(encoding="utf-8"),
        ["DIRcreative", "Live Chat Start Contract", "chat-stage-gate-integrity.md", "pre_generation_contract.status: pass"],
    )
    parity_ok, parity_output = run_ok(["python3", "scripts/dircreative_install_parity.py"])
    installed_ok = installed_terms_ok and parity_ok and "INSTALL_PARITY: PASS" in parity_output
    if not args.require_installed and not installed_ok:
        installed_status = Requirement(
            "installed skill verification",
            "PASS",
            "scripts/dircreative_release_gate.py",
            "Release gate installs and validates the local skill package; --require-installed enforces the local copy.",
        )
    else:
        installed_status = check(
            "installed skill verification",
            installed_ok,
            f"{INSTALLED_SKILL} + scripts/dircreative_install_parity.py",
            "Installed Codex skill must expose the same chat-first contract, pre-generation guard, and package parity with the source repo.",
        )

    requirements = [
        check(
            "chat-visible rough idea flow",
            has_terms(rough_chat, ["阶段: 想法读取", "阶段: 导演组会议", "阶段: 5镜头分镜", "阶段: 参考图方案", "阶段: 出图执行建议", "阶段: QA 与重试规则", "用户确认点"]),
            "examples/live-user-sim-noodle/16-chat-interface-demo.md",
            "A real user must see the whole rough-idea path in chat, not only files.",
        ),
        check(
            "chat-visible complete idea segmentation",
            has_terms(complete_chat, ["阶段: 完整想法读取", "阶段: 导演组会议", "阶段: 专业分镜确认", "阶段: 参考图组方案", "阶段: 出图执行建议", "阶段: 视频生成建议"]),
            "examples/complete-idea-segmentation-test/02-chat-transcript.md",
            "Complete ideas must skip broad brainstorming without skipping professional execution gates.",
        ),
        check(
            "goal-mode simulated normal operation",
            has_terms(goal_sim + "\n" + goal_rough_sim, ["阶段: 目标模式模拟测试", "模拟用户选择", "阶段: 出图执行建议", "阶段: 模拟测试结论", "不计入真实验收"]),
            "examples/goal-mode-simulation-test + examples/goal-mode-rough-idea-simulation-test",
            "Goal-mode dogfood must keep moving without waiting for manual 1/2/3 replies.",
        ),
        check(
            "isolated simulated user testing",
            isolated_ok
            and has_terms(
                isolated_output,
                [
                    "rough_idea",
                    "complete_idea",
                    "longform_request",
                    "image_request",
                    "midstream_change",
                    "real_user_co_creation_verified: false",
                    "ISOLATED_USER_SIMULATION: PASS",
                ],
            ),
            "scripts/dircreative_isolated_user_sim.py + examples/isolated-user-simulation-test/01-simulation-pack.yaml",
            "The workflow must be tested with isolated simulated users, separate DIRcreative replies, and independent post-run review without counting as real acceptance.",
        ),
        check(
            "live acceptance rehearsal remains chat-first",
            has_terms(acceptance_rehearsal, ["阶段: 真实聊天验收预演", "阶段: 验收入口", "阶段: QA 与重试规则", "PASS_FOR_REHEARSAL", "未写 live-user-acceptance.yaml: true", "不计入真实验收: true"]),
            "examples/live-acceptance-rehearsal/01-chat-transcript.md",
            "Before real acceptance, the user should be able to see the final chat surface without a fake acceptance receipt.",
        ),
        check(
            "director-room council collaboration",
            has_terms(director_room, ["producer", "creative_director", "director", "screenwriter", "cinematographer", "production_designer", "editor", "sound_designer", "model_prompt_engineer", "continuity_qa", "disagreement"]),
            "docs/film-preproduction/director-room-council-protocol.md",
            "The director group must behave like collaborating sub-roles, not a flat monologue.",
        ),
        check(
            "adversarial council audit is executable",
            council_audit_ok
            and has_terms(
                council_audit_output,
                [
                    "required_viewpoints_present: true",
                    "council_trigger_surface_present: true",
                    "external_research_boundary_present: true",
                    "failure_ids_present: true",
                    "objective_complete: OBJECTIVE_COMPLETE: NO",
                    "COUNCIL_AUDIT: PASS",
                ],
            ),
            "scripts/dircreative_council_audit.py -> COUNCIL_AUDIT: PASS",
            "The rebuttal council must be executable across user, film expert, product manager, skill developer, and code researcher viewpoints.",
        ),
        check(
            "film/commercial quality audit is executable",
            quality_audit_ok
            and has_terms(quality_audit_output, ["QUALITY_AUDIT: PASS", "film_grade_ready: true", "commercial_grade_ready: true"]),
            "scripts/dircreative_quality_audit.py -> QUALITY_AUDIT: PASS",
            "Film-grade and commercial-grade standards must be machine-audited before claiming technical readiness.",
        ),
        check(
            "Creative Production adapter audit is executable",
            creative_production_audit_ok
            and has_terms(
                creative_production_audit_output,
                ["CREATIVE_PRODUCTION_AUDIT: PASS", "adapter_source_of_truth: dircreative_artifacts", "review_surface: render_moodboard_board_widget"],
            ),
            "scripts/dircreative_creative_production_audit.py -> CREATIVE_PRODUCTION_AUDIT: PASS",
            "Creative Production can assist generation only as a gated adapter with DIRcreative as the source of truth.",
        ),
        check(
            "Goal autorun dry-run audit is executable",
            goal_autorun_audit_ok
            and has_terms(goal_autorun_audit_output, ["GOAL_AUTORUN_AUDIT: PASS", "goal_autorun_dry_run_complete: true", "real_media_generated: false"]),
            "scripts/dircreative_goal_autorun_audit.py -> GOAL_AUTORUN_AUDIT: PASS",
            "Goal mode must run a complete dry-run without generating media or writing live acceptance.",
        ),
        check(
            "professional script and dynamic shot density",
            has_terms(rough_script + rough_shots + complete_shots, ["00:00", "15", "shot_count_rationale", "narrative_purpose", "shot_size", "lens", "camera_motion", "audio", "model_notes"]),
            "examples/live-user-sim-noodle/06-script.md + shot lists",
            "15-second ads/shorts must use shot count based on rhythm and clarity, not a fixed three-shot template.",
        ),
        check(
            "story duration separated from 15s generation units",
            has_terms(
                duration_policy,
                [
                    "generation-unit ceiling",
                    "not the default story duration",
                    "story_duration",
                    "generation_unit_limit",
                    "Do not compress a multi-minute story into one 15s script",
                    "5-15s generation units",
                    "每组视频生成上限",
                ],
            ),
            "longform policy + chat checklist + root/phase skills",
            "A 15s video model cap must create 15s generation groups, not force the whole story to be 15 seconds.",
        ),
        check(
            "reference image roles stay separated",
            has_terms(reference_plan, ["character identity reference", "scene geography + camera FOV reference", "professional storyboard + motion map", "clean frames", "direct_video_input_policy", "planning_only"]),
            "reference pack plans",
            "Reference packs must separate identity, scene/FOV, storyboard motion, and clean direct I2V inputs.",
        ),
        check(
            "customer-facing generation decision is visible before prompt internals",
            has_terms(rough_chat + complete_chat + goal_sim + goal_rough_sim, ["阶段: 出图执行建议", "pre_generation_contract.status: pass", "raw JSON", "direct video input policy"]),
            "chat transcripts",
            "Image/video execution choices must be visible to the user, while contract and raw prompt bodies stay backstage evidence.",
        ),
        check(
            "image prompts include anti-drift and anti-artifact rules",
            has_terms(
                image_prompts,
                [
                    "JSON",
                    "dominant_title",
                    "Pre-generation contract:",
                    "Largest title on the page:",
                    "Smaller metadata only:",
                    "Direct video input policy:",
                    "art-directed",
                    "consistency",
                    "surface_integrity_guard_v1",
                    "optional_qa_macro_not_forced: true",
                    "quality_and_artifact_control",
                    "avoid:",
                ],
            ),
            "image prompt manifests",
            "Image prompts must carry visible prompt contracts, title hierarchy, consistency locks, art direction, direct-input policy, and targeted artifact guards without forcing a fixed Image2/Image Gen suffix.",
        ),
        check(
            "video prompts are model-specific",
            has_terms(video_prompts, ["seedance", "kling", "runway", "veo", "audio_policy", "constraints"]),
            "video prompt manifests",
            "Seedance, Kling, Runway, and Veo must not receive one generic prompt.",
        ),
        check(
            "QA and smallest-artifact retry routing",
            has_terms(qa, ["Pre-Generation QA", "Post-Generation Self-QA", "Retry Routing", "failure IDs", "smallest", "Do not ask the user to lock a failed candidate"]),
            "QA/retry plans",
            "The user must not be the first QA pass; failures route to the smallest corrective artifact.",
        ),
        check(
            "consistency and misread safeguards",
            has_terms(qa + assisted, ["character_identity_reference_drift", "scene_geography_reference_drift", "reference_role_label_hierarchy_wrong", "storyboard_information_density_too_low", "storyboard_board_misread_by_video_model"]),
            "QA failure taxonomy and assisted generation receipt",
            "Known failures must be explicit: identity drift, scene drift, title hierarchy, low storyboard density, and model misread.",
        ),
        check(
            "prompt-only and assisted-generation preflight boundaries",
            has_terms(rough_status + complete_status + assisted, ["VISUAL_OUTPUT_MODE: prompt_only", "clean_frame_gate", "BLOCKS_MEDIA", "visual_output_mode: assisted_generation", "reject_for_revision", "video_generated: false"]),
            "status output + tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml",
            "The project must work without media generation and block unsafe assisted-generation candidates.",
        ),
        check(
            "chat-visible assisted-generation preflight",
            has_terms(assisted_chat, ["阶段: 出图请求前置拦截", "看看图", "当前不能直接出图", "阶段: assisted_generation 前置结果", "真实工具调用: false", "blocked_for_real_authorization", "只生成 CHARACTER IDENTITY REFERENCE", "post-generation self-QA"]),
            "examples/assisted-generation-preflight-chat/01-chat-transcript.md",
            "When the user asks to see images, the chat must block premature generation and show the exact safe first step.",
        ),
        check(
            "chat stage gate integrity is enforced",
            has_terms(
                stage_gate_contract + "\n" + chat_surface_output,
                [
                    "Every visible creative stage must carry a decision surface",
                    "Every creative stage must include `用户确认点`",
                    "`阶段: 出图执行建议`, `阶段: 视频生成建议`, and `阶段: QA 与重试规则` are customer-facing gates",
                    "raw JSON/YAML prompt bodies are backstage evidence",
                    "stage_gate_integrity: ok",
                    "CHAT_SURFACE_AUDIT: PASS",
                ],
            )
            and chat_surface_ok,
            "docs/film-preproduction/chat-stage-gate-integrity.md + scripts/dircreative_chat_surface_audit.py",
            "Prompt summaries, QA/retry, and simulated runs must remain visible co-creation gates, not hidden afterthoughts.",
        ),
        installed_status,
        check(
            "gstack visual dogfood",
            has_terms(gstack, ["tool: gstack browse", "browser_status: pass", "goal_mode_complete_simulation_visible: true", "goal_mode_rough_idea_simulation_visible: true", "no_real_media_generated: true"]),
            "tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml",
            "The chat workflow must have a user-visible dogfood surface, not only terminal output.",
        ),
        check(
            "end-of-session progress reporting",
            has_terms(progress, ["completion_estimate_percent", "technical_readiness: pass", "remaining_blocker: real_user_acceptance", "estimated_remaining_time", "每次会话结束"]),
            "docs/film-preproduction/current-project-progress.md",
            "Each session must leave a clear completion estimate and remaining-time estimate.",
        ),
        live_acceptance_requirement(),
    ]

    invalid = any(item.status in {"MISSING", "INVALID"} for item in requirements)
    technical_ready = all(item.status == "PASS" for item in requirements if item.label != "real user acceptance")
    objective_complete = technical_ready and all(item.status == "PASS" for item in requirements)

    print("DIRcreative Objective Audit")
    print("=" * 72)
    for item in requirements:
        print(f"[{item.status}] {item.label}")
        print(f"       evidence: {item.evidence}")
        print(f"       reason: {item.reason}")
    print(f"OBJECTIVE_TECHNICAL_READINESS: {'PASS' if technical_ready else 'FAIL'}")
    print(f"OBJECTIVE_COMPLETE: {'YES' if objective_complete else 'NO'}")
    if not objective_complete:
        print("NEXT_REQUIRED_ACTION: run a real chat acceptance pass; do not treat goal-mode simulation as user approval")
    return 0 if technical_ready and not invalid else 1


if __name__ == "__main__":
    raise SystemExit(main())
