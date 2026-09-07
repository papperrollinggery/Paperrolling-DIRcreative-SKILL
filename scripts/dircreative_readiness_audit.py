#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from dircreative_validation_harness import ROOT, Check, add_check, read, require_terms
MEDIA_FILE_KINDS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".wav",
    ".mp3",
    ".m4a",
}


def run(cmd: list[str]) -> str:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"{' '.join(cmd)} failed:\n{proc.stderr}\n{proc.stdout}")
    return proc.stdout


def installed_package_layout() -> bool:
    return (ROOT / "SKILL.md").exists() and not (ROOT / ".git").exists()


def validate_runtime_readiness() -> None:
    if installed_package_layout():
        installed_runtime = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / ".dircreative").rglob("*")
            if path.is_file()
        )
        expected = [".dircreative/checkpoints/.keep", ".dircreative/runs/.keep"]
        if installed_runtime != expected:
            raise AssertionError(
                "installed package runtime must contain only lifecycle sentinels: "
                + ", ".join(installed_runtime)
            )
        return
    require_terms(
        run(["python3", "scripts/dircreative_state_audit.py", "audit", "--json"]),
        ['"current_integrity": "PASS"', '"legacy_debt": "NONE"', '"findings": []'],
        "current runtime state audit",
    )


def main() -> int:
    checks: list[Check] = []

    add_check(
        checks,
        "current runtime integrity is authoritative",
        ".dircreative/state/current.json -> CURRENT_INTEGRITY: PASS, or installed package lifecycle sentinels only",
        validate_runtime_readiness,
    )

    add_check(
        checks,
        "rough idea chat path is user-visible",
        "examples/live-user-sim-noodle/16-chat-interface-demo.md",
        lambda: require_terms(
            read("examples/live-user-sim-noodle/16-chat-interface-demo.md"),
            [
                "阶段: 想法读取",
                "阶段: 导演组会议",
                "阶段: 15秒脚本",
                "阶段: 5镜头分镜",
                "阶段: 参考图方案",
                "阶段: 出图执行建议",
                "阶段: 视频生成建议",
                "阶段: QA 与重试规则",
                "用户确认点",
                "模拟用户选择",
                "当前没有生成真实图片或视频",
            ],
            "live-user-sim-noodle chat demo",
        ),
    )

    add_check(
        checks,
        "complete idea chat path is user-visible",
        "examples/complete-idea-segmentation-test/02-chat-transcript.md",
        lambda: require_terms(
            read("examples/complete-idea-segmentation-test/02-chat-transcript.md"),
            [
                "阶段: 完整想法读取",
                "阶段: 导演组会议",
                "阶段: 故事逻辑确认",
                "阶段: 专业分镜确认",
                "阶段: 参考图组方案",
                "阶段: 出图执行建议",
                "阶段: 视频生成建议",
                "阶段: QA 与重试规则",
                "用户确认点",
                "模拟用户选择",
                "当前没有生成真实图片或视频",
            ],
            "complete idea chat transcript",
        ),
    )

    add_check(
        checks,
        "source runtime has a result-first start and generation boundary",
        "root Skill, start protocol, and compact generation card",
        lambda: require_terms(
            "\n".join(
                [
                    read("skills/dircreative/SKILL.md"),
                    read("skills/dircreative/chat-facilitator/SKILL.md"),
                    read("skills/dircreative/routes/delivery-audit.md"),
                    read("skills/dircreative/references/generation-delivery.md"),
                    read("docs/film-preproduction/live-chat-start-protocol.md"),
                ]
            ),
            [
                "Live Chat Start Protocol",
                "first reply",
                "production-room gate",
                "阶段: 想法读取",
                "阶段: 完整想法读取",
                "earliest unresolved creative gate",
                "智能体创作内容",
                "专业判断",
                "用户确认点",
                "the exact provider surface and model/version",
                "rights/consent",
                "Call an available compatible media tool now",
                "identity evidence before dependent",
                "dependency layer",
                "repair actual failed variables",
                "explicitly delegated test or smoke evaluation",
                "saved path and scoped QA status",
            ],
            "live chat start contract evidence",
        ),
    )

    add_check(
        checks,
        "goal-mode simulation does not wait for manual choices",
        "docs/film-preproduction/goal-mode-simulation-protocol.md + goal-mode simulation transcript",
        lambda: require_terms(
            "\n".join(
                [
                    read("docs/film-preproduction/goal-mode-simulation-protocol.md"),
                    read("docs/film-preproduction/chat-co-creation-interface.md"),
                    read("docs/film-preproduction/live-chat-start-protocol.md"),
                    read("skills/dircreative/chat-facilitator/SKILL.md"),
                    read("examples/goal-mode-simulation-test/01-chat-transcript.md"),
                ]
            ),
            [
                "Goal Mode Simulation Protocol",
                "goal_context",
                "目标模式模拟测试",
                "用户确认点",
                "模拟用户选择",
                "阶段: 出图执行建议",
                "阶段: 视频生成建议",
                "阶段: 模拟测试结论",
                "live-user-acceptance.yaml",
                "不计入真实验收",
            ],
            "goal-mode simulation evidence",
        ),
    )

    add_check(
        checks,
        "goal-mode rough idea simulation covers one-sentence intake",
        "examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md + 15-co-creation-run.yaml",
        lambda: require_terms(
            "\n".join(
                [
                    read("examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md"),
                    read("examples/goal-mode-rough-idea-simulation-test/15-co-creation-run.yaml"),
                ]
            ),
            [
                "阶段: 想法读取",
                "阶段: 导演组会议",
                "阶段: 分镜头确认",
                "阶段: 出图执行建议",
                "阶段: 视频生成建议",
                "阶段: 模拟测试结论",
                "rough_idea_path_covered: true",
                "clean_frame_gate",
                "media_generation",
            ],
            "goal-mode rough idea simulation evidence",
        ),
    )

    add_check(
        checks,
        "director-room adaptive perspectives are bounded",
        "adaptive Director Room docs and v2 harness",
        lambda: require_terms(
            "\n".join(
                [
                    read("docs/film-preproduction/director-room-council-protocol.md"),
                    read("docs/film-preproduction/director-room-routing.md"),
                    read("docs/film-preproduction/schemas/director-role-harness.yaml"),
                    read("skills/dircreative/director-room/SKILL.md"),
                ]
            ),
            [
                "narrative_strategy",
                "visual_production",
                "model_continuity",
                "Fast tasks do not enter Director Room",
                "threads_default: 0",
                "maximum_perspectives: 3",
                "minimum_disagreements: 0",
                "user_visible_role_cards: false",
                "legacy_v1_role_contracts",
            ],
            "adaptive director-room evidence",
        ),
    )

    add_check(
        checks,
        "adversarial council audit is executable",
        "scripts/dircreative_council_audit.py -> COUNCIL_AUDIT: PASS",
        lambda: require_terms(
            run(["python3", "scripts/dircreative_council_audit.py"]),
            [
                "required_viewpoints_present: true",
                "council_trigger_surface_present: true",
                "external_research_boundary_present: true",
                "failure_ids_present: true",
                "objective_complete: OBJECTIVE_COMPLETE: NO",
                "COUNCIL_AUDIT: PASS",
            ],
            "adversarial council audit output",
        ),
    )

    add_check(
        checks,
        "film/commercial quality audit is executable",
        "scripts/dircreative_quality_audit.py -> QUALITY_AUDIT: PASS",
        lambda: require_terms(
            run(["python3", "scripts/dircreative_quality_audit.py"]),
            [
                "film_grade_ready: true",
                "commercial_grade_ready: true",
                "live_acceptance_required: true",
                "QUALITY_AUDIT: PASS",
            ],
            "film/commercial quality audit output",
        ),
    )

    add_check(
        checks,
        "Creative Production adapter audit is executable",
        "scripts/dircreative_creative_production_audit.py -> CREATIVE_PRODUCTION_AUDIT: PASS",
        lambda: require_terms(
            run(["python3", "scripts/dircreative_creative_production_audit.py"]),
            [
                "adapter_source_of_truth: dircreative_artifacts",
                "review_surface: render_moodboard_board_widget",
                "live_acceptance_required: true",
                "CREATIVE_PRODUCTION_AUDIT: PASS",
            ],
            "Creative Production audit output",
        ),
    )

    add_check(
        checks,
        "Goal autorun dry-run audit is executable",
        "scripts/dircreative_goal_autorun_audit.py -> GOAL_AUTORUN_AUDIT: PASS",
        lambda: require_terms(
            run(["python3", "scripts/dircreative_goal_autorun_audit.py"]),
            [
                "goal_autorun_dry_run_complete: true",
                "real_media_generated: false",
                "live_acceptance_required: true",
                "GOAL_AUTORUN_AUDIT: PASS",
            ],
            "Goal autorun audit output",
        ),
    )

    add_check(
        checks,
        "professional dynamic shot design is present",
        "examples/live-user-sim-noodle/07-shot-list.yaml + examples/complete-idea-segmentation-test/03-shot-list.yaml",
        lambda: require_terms(
            "\n".join(
                [
                    read("examples/live-user-sim-noodle/07-shot-list.yaml"),
                    read("examples/complete-idea-segmentation-test/03-shot-list.yaml"),
                ]
            ),
            [
                "shot_count_rationale",
                "narrative_purpose",
                "shot_size",
                "lens",
                "camera_motion",
                "blocking",
                "composition",
                "audio",
                "model_notes",
                "Three shots would overload",
            ],
            "shot-list evidence",
        ),
    )

    add_check(
        checks,
        "reference roles, title hierarchy, and pre-generation contracts are visible",
        "examples/live-user-sim-noodle/12-qa-retry-plan.md + complete reference prompt plan",
        lambda: require_terms(
            "\n".join(
                [
                    read("examples/live-user-sim-noodle/12-qa-retry-plan.md"),
                    read("examples/complete-idea-segmentation-test/04-reference-prompt-plan.md"),
                ]
            ),
            [
                "pre_generation_contract",
                "dominant_title",
                "role_purity",
                "direct_video_input_policy",
                "Largest title on the page",
                "Smaller metadata only",
                "Do not make",
                "NOT DIRECT VIDEO INPUT",
                "PLANNING ONLY",
            ],
            "contract evidence",
        ),
    )

    add_check(
        checks,
        "model-specific video prompt adapters are not generic copies",
        "examples/live-user-sim-noodle/11-video-prompt-manifest.yaml + complete prompt plan",
        lambda: require_terms(
            "\n".join(
                [
                    read("examples/live-user-sim-noodle/11-video-prompt-manifest.yaml"),
                    read("examples/complete-idea-segmentation-test/04-reference-prompt-plan.md"),
                ]
            ),
            [
                "seedance",
                "kling",
                "runway",
                "veo",
                "reference_warning",
                "audio_policy",
                "retry_rules",
                "Do not show storyboard panels",
                "Best mode: direct I2V from clean frames",
            ],
            "video adapter evidence",
        ),
    )

    add_check(
        checks,
        "QA and smallest retry route are user-visible",
        "examples/live-user-sim-noodle/12-qa-retry-plan.md + complete QA plan",
        lambda: require_terms(
            "\n".join(
                [
                    read("examples/live-user-sim-noodle/12-qa-retry-plan.md"),
                    read("examples/complete-idea-segmentation-test/05-qa-retry-plan.md"),
                ]
            ),
            [
                "Pre-Generation QA",
                "Post-Generation Self-QA",
                "Retry Routing",
                "self-QA",
                "smallest artifact",
                "Do not ask the user to lock",
                "character_identity_reference_drift",
                "scene_geography_reference_drift",
                "reference_role_label_hierarchy_wrong",
                "storyboard_information_density_too_low",
                "fish_scale_material_artifact",
                "board_used_as_direct_i2v_input_when_forbidden",
                "copied_video_prompt_across_models",
                "missing_audio_policy",
            ],
            "QA/retry evidence",
        ),
    )

    add_check(
        checks,
        "assisted-generation preflight and rejection are recorded",
        "tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml + negative fixtures",
        lambda: require_terms(
            "\n".join(
                [
                    read("tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml"),
                    read("tests/fixtures/invalid-assisted-image-manifest-missing-contract.yaml"),
                    read("tests/fixtures/invalid-assisted-image-manifest-weak-contract.yaml"),
                    read("tests/fixtures/invalid-assisted-image-manifest-contract-prompt-mismatch.yaml"),
                ]
            ),
            [
                "visual_output_mode: assisted_generation",
                "needs_revision",
                "reject_for_revision",
                "sequential_gated_assisted_generation",
                "user_lock_required_before_video: true",
                "image_generation_called_without_pre_generation_contract",
                "reference_role_label_hierarchy_wrong",
            ],
            "assisted-generation evidence",
        ),
    )

    add_check(
        checks,
        "demo runner proves rough idea and complete idea flows",
        "scripts/dircreative_demo.py --example live-user-sim-noodle / complete-idea",
        lambda: (
            require_terms(
                run(["python3", "scripts/dircreative_demo.py", "--example", "examples/live-user-sim-noodle"]),
                [
                    "15秒脚本",
                    "5镜头分镜",
                    "出图执行建议",
                    "QA 与重试规则",
                    "Seedance",
                    "Kling",
                    "当前没有生成真实图片或视频",
                ],
                "rough idea demo output",
            ),
            require_terms(
                run(["python3", "scripts/dircreative_demo.py", "--example", "examples/complete-idea-segmentation-test"]),
                [
                    "完整想法读取",
                    "导演组会议",
                    "6镜头分镜",
                    "出图执行建议",
                    "QA 与重试规则",
                    "Seedance",
                    "Kling",
                    "当前没有生成真实图片或视频",
                ],
                "complete idea demo output",
            ),
        ),
    )

    add_check(
        checks,
        "release gate covers repo, installed skill, status, visual dogfood, and diff checks",
        "scripts/dircreative_release_gate.py",
        lambda: require_terms(
            read("scripts/dircreative_release_gate.py"),
            [
                "repo validation",
                "rough idea status",
                "complete idea status",
                "readiness audit",
                "film/commercial quality audit",
                "Creative Production adapter audit",
                "Goal autorun dry-run audit",
                "visual dogfood pages",
                "install local skill",
                "installed skill validation",
                "installed rough idea status",
                "installed complete idea status",
                "diff whitespace check",
                "RELEASE_GATE: PASS",
            ],
            "release gate script",
        ),
    )

    add_check(
        checks,
        "repository example-fixture hygiene excludes live media; this is not a project asset-completion claim",
        "examples/**/* media scan",
        lambda: (_ for _ in ()).throw(
            AssertionError(
                "real media assets found: "
                + ", ".join(
                    path.relative_to(ROOT).as_posix()
                    for path in (ROOT / "examples").rglob("*")
                    if path.is_file() and path.suffix.lower() in MEDIA_FILE_KINDS
                )
            )
        )
        if any(
            path.is_file() and path.suffix.lower() in MEDIA_FILE_KINDS
            for path in (ROOT / "examples").rglob("*")
        )
        else None,
    )

    if os.environ.get("DIRCREATIVE_SKIP_VISUAL_DOGFOOD") != "1":
        add_check(
            checks,
            "visual dogfood pages are reproducible",
            "scripts/dircreative_visual_dogfood.py -> /tmp/dircreative-visual-dogfood",
            lambda: require_terms(
                run(["python3", "scripts/dircreative_visual_dogfood.py"]),
                [
                    "DIRcreative Visual Dogfood Pages",
                    "one-idea.html",
                    "complete-idea.html",
                    "goal-mode-simulation.html",
                    "goal-mode-rough-idea.html",
                    "readiness-audit.html",
                    "VISUAL_DOGFOOD_PAGES: PASS",
                ],
                "visual dogfood output",
            ),
        )

    add_check(
        checks,
        "gstack visual dogfood receipt records browser evidence",
        "tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml",
        lambda: require_terms(
            read("tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml"),
            [
                "tool: gstack browse",
                "console_status: no_console_messages",
                "browser_status: pass",
                "screenshot_reviewed_by_agent: true",
                "gstack_opened_pages: true",
                "goal_mode_complete_simulation_visible: true",
                "goal_mode_rough_idea_simulation_visible: true",
                "screenshots_saved: true",
                "console_errors_absent: true",
                "goal_audit_visible: true",
                "no_real_media_generated: true",
                "DIRcreative Visual Dogfood",
                "READINESS: PASS",
                "GOAL_COMPLETE:",
            ],
            "gstack visual dogfood receipt",
        ),
    )

    add_check(
        checks,
        "goal-mode simulation page has browser-smoke evidence",
        "tests/fixtures/runtime/runs/goal-mode-simulation-visual-dogfood-receipt.yaml",
        lambda: require_terms(
            read("tests/fixtures/runtime/runs/goal-mode-simulation-visual-dogfood-receipt.yaml"),
            [
                "tool: local_browser_playwright",
                "console_status: no_console_messages",
                "browser_status: pass",
                "goal_mode_simulation_page",
                "阶段: 目标模式模拟测试",
                "模拟用户选择",
                "阶段: 出图执行建议",
                "阶段: 模拟测试结论",
                "live_acceptance_not_claimed: true",
            ],
            "goal-mode visual dogfood receipt",
        ),
    )

    add_check(
        checks,
        "goal-mode rough idea page has browser-smoke evidence",
        "tests/fixtures/runtime/runs/goal-mode-rough-idea-visual-dogfood-receipt.yaml",
        lambda: require_terms(
            read("tests/fixtures/runtime/runs/goal-mode-rough-idea-visual-dogfood-receipt.yaml"),
            [
                "tool: local_browser_playwright",
                "console_status: no_console_messages",
                "browser_status: pass",
                "goal_mode_rough_idea_page",
                "阶段: 想法读取",
                "模拟用户选择",
                "阶段: 出图执行建议",
                "阶段: 模拟测试结论",
                "live_acceptance_not_claimed: true",
            ],
            "goal-mode rough idea visual dogfood receipt",
        ),
    )

    installed = Path.home() / ".codex" / "skills" / "dircreative"
    if installed.exists():
        installed_state = "present"
        installed_required = [
            installed / "scripts" / "validate_project.py",
            installed / "examples" / "live-user-sim-noodle" / "12-qa-retry-plan.md",
            installed / "examples" / "complete-idea-segmentation-test" / "05-qa-retry-plan.md",
            installed / "examples" / "goal-mode-simulation-test" / "15-co-creation-run.yaml",
            installed / "examples" / "goal-mode-rough-idea-simulation-test" / "15-co-creation-run.yaml",
        ]
        if all(path.exists() for path in installed_required):
            installed_state += " and contains current QA artifacts"
        else:
            missing = [str(path) for path in installed_required if not path.exists()]
            installed_state += f" but is missing {missing}"
    else:
        installed_state = "not present; run scripts/install_local_skill.py"

    print("DIRcreative Readiness Audit")
    print("=" * 72)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.label}")
        print(f"       evidence: {check.evidence}")
    print(f"[INFO] installed skill package: {installed_state}")
    print("[INFO] gstack dogfood target: /tmp/dircreative-visual-dogfood/index.html")

    failures = [check for check in checks if not check.ok]
    if failures:
        print("READINESS: FAIL")
        return 1
    print("READINESS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
