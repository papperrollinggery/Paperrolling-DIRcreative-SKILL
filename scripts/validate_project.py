#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ALLOW_DEVELOPMENT_INSTALL = False
INSTALLED_PACKAGE_VALIDATION = False
sys.dont_write_bytecode = True
PLACEHOLDER_RE = re.compile(r"TB[D]|TO[D]O|待[定]|占[位]|x[x]x|FIX[ME]")
THREAD_CONTRACT_TEXT_PATHS = [
    "docs/film-preproduction/thread-orchestration-protocol.md",
    "docs/film-preproduction/production-prompt-discipline.md",
    "docs/film-preproduction/production-demo-retrospective.md",
    "docs/film-preproduction/council-adversarial-review.md",
    "docs/film-preproduction/chat-co-creation-interface.md",
    "docs/film-preproduction/current-project-progress.md",
    "docs/film-preproduction/qa/retry-rules.md",
    "docs/film-preproduction/qa/failure-taxonomy.yaml",
    "docs/film-preproduction/live-chat-acceptance-runbook.md",
    "skills/dircreative/SKILL.md",
    "skills/dircreative/director-room/SKILL.md",
]
FORBIDDEN_THREAD_CONTRACT_PHRASES = [
    "main-controller thread owns final writes",
    "main-controller owns final writes",
    "main controller thread owns final writes",
    "main controller owns final writes",
    "owns final repository writes",
    "main-controller final repository writes",
    "use a main-controller thread for project truth",
]
TEXT_FILE_KINDS = {
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".py",
}
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
VISUAL_OUTPUT_MODES = {"prompt_only", "assisted_generation", "external_generation"}
LONGFORM_MODES = {"hybrid", "stepwise", "batch", "single_sequence"}
REQUIRED_VIDEO_MODELS = ["seedance", "kling", "runway", "veo"]
ASSET_OUTPUT_STATUSES = {
    "prompt_ready",
    "generated_candidate",
    "user_locked",
    "external_pending",
    "external_imported",
    "rejected",
}
IMAGE_SURFACE_GUARD_SUFFIX = (
    "The image is clean and transparent, with complete and natural materials, "
    "smooth and uniform texture, and the main subject Be clear, with distinct "
    "background layers, and avoid excessive sharpening, color spots, and noise "
    "Cracks, collapse, and distortion"
)
IMAGE_AUDIO_GENERATION_TERMS = [
    "dialogue",
    "voiceover",
    "voice-over",
    "music",
    "sound effect",
    "sfx",
    "foley",
    "audio cue",
    "audio plan",
    "sound cue",
    "对白",
    "人声",
    "旁白",
    "音乐",
    "音效",
    "声音提示",
]
EMPTY_QUALITY_WORDING = {
    "high detail",
    "masterpiece",
    "best quality",
    "cinematic",
    "beautiful",
    "premium",
}
LEGACY_V1_CO_CREATION_RUN_TYPES = {"dry_run_fixture", "live_user_run"}
LEGACY_V1_CO_CREATION_GATE_TYPES = [
    "concept_options_gate",
    "story_approval_gate",
    "script_approval_gate",
    "shot_list_approval_gate",
    "visual_direction_gate",
    "visual_bible_approval_gate",
    "sequence_plan_gate",
    "global_reference_pack_gate",
    "sequence_reference_pack_gate",
    "clean_frame_gate",
    "video_prompt_gate",
]
LEGACY_V1_CO_CREATION_GATE_STATUSES = {"pending", "approved", "needs_revision", "skipped_with_risk"}
LEGACY_V1_CO_CREATION_DECISION_SOURCES = {"real_user", "simulated_fixture", "pending", "system_default"}
LEGACY_V1_MEDIA_BLOCKING_GATES = {"clean_frame_gate", "video_prompt_gate"}
V2_EXTERNAL_USER_GATES = ["concept_lock", "generation_authorization", "client_delivery_approval"]
V2_REVERSIBLE_INTERNAL_STATES = [
    "story_state",
    "script_state",
    "shot_state",
    "visual_state",
    "reference_state",
    "prompt_state",
    "qa_state",
]
CLIENT_FILM_STAGE_GATES = ["story", "script", "shot", "asset_reference", "prompt_generation", "client_language"]
CLIENT_FILM_FORBIDDEN_VISIBLE_TERMS = [
    "prompt",
    "thread",
    "worker",
    "gate",
    "AI",
    "执行过程",
    "内部",
    "素材权限",
    "可授权",
    "需确认",
    "客户稿里标成",
]
CLIENT_FILM_ASSET_SOURCE_DECISIONS = {
    "live_action",
    "ugc",
    "reference_video",
    "existing_grok_image",
    "existing_chatgpt_image",
    "existing_imagegen_image",
    "prompt_only",
    "new_image_prompt",
}
CLIENT_FILM_PROMPT_OUTPUT_MODES = {"prompt_only", "new_generation"}
PROFESSIONAL_SHOT_LISTS = {
    "examples/live-user-sim-noodle/07-shot-list.yaml",
    "examples/product-ad-raincoat/06-shot-list.yaml",
    "examples/cyber-courier/13-shot-list.yaml",
    "examples/complete-idea-segmentation-test/03-shot-list.yaml",
}
CHAT_SURFACE_SKILLS = [
    "skills/dircreative/idea-intake/SKILL.md",
    "skills/dircreative/director-room/SKILL.md",
    "skills/dircreative/story-development/SKILL.md",
    "skills/dircreative/script-treatment/SKILL.md",
    "skills/dircreative/shot-design/SKILL.md",
    "skills/dircreative/visual-bible/SKILL.md",
    "skills/dircreative/reference-image-planner/SKILL.md",
    "skills/dircreative/image-prompt-compiler/SKILL.md",
    "skills/dircreative/video-model-adapter/SKILL.md",
]


class ValidationError(Exception):
    pass


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def is_blank(value: Any) -> bool:
    return value is None or value == "" or value == []


def required_path_candidate(root: Path, path: str, *, installed_mode: bool) -> Path:
    target = root / path
    if installed_mode and path.startswith("skills/") and path.endswith("/SKILL.md"):
        target = target.with_name("INTERNAL_SKILL.md")
    return target


def require_path(path: str) -> Path:
    target = required_path_candidate(
        ROOT,
        path,
        installed_mode=INSTALLED_PACKAGE_VALIDATION,
    )
    require(target.exists(), f"missing required path: {path}")
    return target


def internal_skill_paths() -> list[Path]:
    return sorted(
        list((ROOT / "skills/dircreative").glob("*/SKILL.md"))
        + list((ROOT / "skills/dircreative").glob("*/INTERNAL_SKILL.md"))
    )


def split_reference(path_ref: str) -> tuple[str, str | None]:
    path_part, marker, fragment = path_ref.partition("#")
    require(path_part.strip(), f"invalid empty reference path: {path_ref}")
    if not marker:
        return path_part, None
    require(fragment.strip(), f"invalid empty reference fragment: {path_ref}")
    return path_part, fragment


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_yaml(path: Path) -> Any:
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = run(["ruby", "-e", ruby, str(path)])
    if proc.returncode != 0:
        raise ValidationError(f"yaml parse failed for {rel(path)}: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"ruby yaml json conversion failed for {rel(path)}: {exc}") from exc


def read_prompt_reference(path_ref: str, seen: set[str] | None = None) -> str:
    seen = seen or set()
    require(path_ref not in seen, f"prompt fragment reference loop detected: {path_ref}")
    seen.add(path_ref)
    path_part, fragment = split_reference(path_ref)
    target = require_path(path_part)
    if fragment is None:
        return target.read_text(encoding="utf-8")
    require(target.suffix in {".yaml", ".yml"}, f"prompt fragment references require YAML source: {path_ref}")
    data = load_yaml(target)
    images = data.get("images", [])
    matches = [image for image in images if image.get("image_id") == fragment]
    if len(matches) == 1:
        image = matches[0]
        inline_prompt = image.get("prompt")
        if isinstance(inline_prompt, str) and inline_prompt.strip():
            return inline_prompt
        nested_ref = image.get("prompt_file") or image.get("asset_output", {}).get("prompt_file")
        require(nested_ref and nested_ref != path_ref, f"prompt fragment has no inline prompt: {path_ref}")
        return read_prompt_reference(nested_ref, seen)
    model_prompt = data.get("model_prompts", {}).get(fragment, {}).get("prompt")
    if isinstance(model_prompt, str) and model_prompt.strip():
        return model_prompt
    require(False, f"prompt fragment not found or not unique: {path_ref}")
    return ""


def validate_reference_binding_prompt_file(path: str, binding: dict[str, Any]) -> None:
    prompt_file = binding.get("prompt_file")
    require(prompt_file, f"{path} reference binding missing prompt_file")
    prompt_path, prompt_fragment = split_reference(prompt_file)
    prompt_target = require_path(prompt_path)
    if prompt_target.suffix in {".yaml", ".yml"}:
        prompt_data = load_yaml(prompt_target)
        if prompt_data.get("model_prompts"):
            require(
                prompt_fragment == binding.get("model"),
                f"{path} reference binding prompt_file must target matching model prompt fragment",
            )
    read_prompt_reference(prompt_file)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"json parse failed for {rel(path)}: {exc}") from exc


def iter_repo_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file():
            files.append(path)
    return files


def validate_required_paths() -> None:
    required = [
        "README.md",
        "VERSION",
        "CHANGELOG.md",
        "docs/film-preproduction/06-gstack-execution-goal.md",
        "docs/film-preproduction/04-goal-mode-handoff.md",
        "docs/film-preproduction/05-skill-integration-architecture.md",
        "docs/film-preproduction/adco-integration-contract.md",
        "docs/film-preproduction/runtime-contracts.md",
        "docs/film-preproduction/phase-contracts.yaml",
        "docs/film-preproduction/schemas/skill-orchestration.yaml",
        "docs/film-preproduction/schemas/adco-specialist-descriptor.json",
        "docs/film-preproduction/schemas/adco-specialist-handoff-v2.schema.json",
        "docs/film-preproduction/schemas/adco-specialist-receipt-v2.schema.json",
        "docs/film-preproduction/schemas/media-forward-execution-v2.schema.json",
        "docs/film-preproduction/schemas/media-visual-review-v1.schema.json",
        "docs/film-preproduction/schemas/asset-foundation-pass.schema.json",
        "docs/film-preproduction/schemas/ai-film-asset-stress-test.schema.json",
        "docs/film-preproduction/schemas/ai-film-asset-stress-test-v2.schema.json",
        "docs/film-preproduction/schemas/ai-film-production-ledger.schema.json",
        "docs/film-preproduction/schemas/script-to-seedance-handoff.schema.json",
        "docs/film-preproduction/schemas/storyboard-frame-to-jingzao.schema.json",
        "skills/dircreative/agents/openai.yaml",
        "skills/dircreative/runtime/review-trust-registry.json",
        "skills/dircreative/runtime/routing-policy.yaml",
        "skills/dircreative/runtime/visual-skill-policy.json",
        "skills/dircreative/runtime/state-snapshot.schema.json",
        "skills/dircreative/runtime/visual-asset-plan.schema.json",
        "skills/dircreative/routes/fast-task.md",
        "skills/dircreative/routes/studio-development.md",
        "skills/dircreative/routes/delivery-audit.md",
        "skills/dircreative/references/copy-script.md",
        "skills/dircreative/references/shot-storyboard.md",
        "skills/dircreative/references/film-development.md",
        "skills/dircreative/references/prompt-model.md",
        "skills/dircreative/references/generation-delivery.md",
        "skills/dircreative/references/specialist-exchange.md",
        "skills/dircreative/references/asset-foundation-pass.md",
        "skills/dircreative/references/script-to-seedance.md",
        "skills/dircreative/references/storyboard-frame-to-jingzao.md",
        "skills/dircreative/references/visual-skill-stack.md",
        "tests/fixtures/activation-policy/cases.json",
        "tests/fixtures/activation-policy/valid-adco-v2-handoff.json",
        "tests/fixtures/routing/cases.json",
        "tests/fixtures/skill-stack/cases.json",
        "tests/fixtures/skill-stack/host-catalog.json",
        "tests/fixtures/asset-foundation/valid-pass.json",
        "tests/fixtures/asset-foundation/cases.json",
        "tests/fixtures/asset-stress-test/valid-report.json",
        "tests/fixtures/asset-stress-test/valid-report-v1.json",
        "tests/fixtures/asset-stress-test/cases.json",
        "tests/fixtures/production-ledger/valid-ledger.json",
        "tests/fixtures/production-ledger/cases.json",
        "tests/fixtures/script-to-seedance/valid-handoff.json",
        "tests/fixtures/script-to-seedance/cases.json",
        "tests/fixtures/storyboard-frame-jingzao/valid-chain.json",
        "tests/fixtures/storyboard-frame-jingzao/cases.json",
        "tests/fixtures/headless-runtime/cases.json",
        "tests/fixtures/headless-runtime/expected/fast-copy-revision.md",
        "tests/fixtures/headless-runtime/expected/studio-complete-film.md",
        "tests/fixtures/headless-runtime/expected/studio-client-story-dual-direction.md",
        "tests/fixtures/headless-runtime/tvc-60s-shot-cards.json",
        "tests/fixtures/visual-asset-plan/valid-coverage-unit.json",
        "tests/fixtures/visual-asset-plan/valid-coverage-unit-inventory.json",
        "tests/fixtures/visual-asset-plan/valid-coverage-unit-shot-cards.json",
        "tests/fixtures/visual-asset-plan/tvc-60s-inventory.json",
        "tests/fixtures/visual-asset-plan/tvc-60s-shot-cards.json",
        "tests/fixtures/visual-asset-plan/cases.json",
        "tests/fixtures/content-first/cases.json",
        "scripts/dircreative_adapters/__init__.py",
        "scripts/dircreative_adapters/base.py",
        "scripts/dircreative_adapters/seedance.py",
        "scripts/dircreative_adapters/kling.py",
        "scripts/dircreative_adapters/runway.py",
        "scripts/dircreative_adapters/sora.py",
        "scripts/dircreative_adapters/veo.py",
        "scripts/dircreative_adapters/generic.py",
        "tests/fixtures/prompt-system/adapter-negative-cases.json",
        "tests/fixtures/prompt-system/adapter-contract-matrix.json",
        "scripts/dircreative_headless_acceptance_audit.py",
        "scripts/dircreative_visual_asset_plan.py",
        "scripts/dircreative_workspace.py",
        "scripts/dircreative_delivery_boundary_audit.py",
        "scripts/dircreative_content_first_audit.py",
        "scripts/dircreative_live_model_eval.py",
        "docs/film-preproduction/prompt-pattern-registry.json",
        "docs/film-preproduction/templates/image-prompt-style-config.template.json",
        "docs/film-preproduction/qa/qa-checklist.md",
        "docs/film-preproduction/qa/failure-taxonomy.yaml",
        "docs/film-preproduction/qa/retry-rules.md",
        "docs/film-preproduction/production-demo-retrospective.md",
        "docs/film-preproduction/council-adversarial-review.md",
        "docs/film-preproduction/production-prompt-discipline.md",
        "docs/film-preproduction/thread-orchestration-protocol.md",
        "docs/film-preproduction/workspace-cleanliness-protocol.md",
        "skills/dircreative/references/project-hygiene.md",
        "docs/film-preproduction/runtime-state-governance.md",
        "docs/film-preproduction/schemas/runtime-state.schema.json",
        "docs/film-preproduction/templates/runtime-state.template.json",
        "docs/film-preproduction/sources/model-sources.yaml",
        "docs/film-preproduction/sources/prompt-sources.yaml",
        "docs/film-preproduction/research/model-reference-behavior.md",
        "docs/film-preproduction/research/tapnow-agentic-canvas-lessons.md",
        "docs/film-preproduction/research/thread-orchestration-community-lessons.md",
        "docs/film-preproduction/research/ai-video-prompt-community-lessons.md",
        "docs/film-preproduction/reference-locking-policy.md",
        "docs/film-preproduction/reference-consistency-gate.md",
        "docs/film-preproduction/longform-decomposition-policy.md",
        "docs/film-preproduction/capability-aware-generation-policy.md",
        "docs/film-preproduction/co-creation-gate-policy.md",
        "docs/film-preproduction/chat-co-creation-interface.md",
        "docs/film-preproduction/chat-inline-visualization-interface.md",
        "docs/film-preproduction/chat-inline-visualization-plan.md",
        "docs/film-preproduction/chat-stage-gate-integrity.md",
        "docs/film-preproduction/chat-surface-contract.yaml",
        "docs/film-preproduction/live-chat-start-protocol.md",
        "docs/film-preproduction/customer-visible-production-gates.md",
        "docs/film-preproduction/client-film-hard-gates.md",
        "docs/film-preproduction/goal-mode-simulation-protocol.md",
        "docs/film-preproduction/live-user-acceptance-gate.md",
        "docs/film-preproduction/live-chat-acceptance-runbook.md",
        "docs/film-preproduction/isolated-user-simulation-protocol.md",
        "docs/film-preproduction/chat-acceptance-checklist.md",
        "docs/film-preproduction/current-project-progress.md",
        "docs/film-preproduction/professional-agent-voice-standard.md",
        "docs/film-preproduction/director-room-council-protocol.md",
        "docs/film-preproduction/ad-reference-pack-generation-gate.md",
        "docs/film-preproduction/shot-language-standard.md",
        "docs/film-preproduction/clean-frame-export-policy.md",
        "docs/film-preproduction/schemas/reference-pack-manifest.yaml",
        "docs/film-preproduction/schemas/client-film-gate-contract.yaml",
        "docs/film-preproduction/schemas/sequence-plan.yaml",
        "docs/film-preproduction/schemas/longform-reference-pack.yaml",
        "docs/film-preproduction/schemas/co-creation-run.yaml",
        "docs/film-preproduction/schemas/chat-visualization-spec.schema.json",
        "docs/film-preproduction/schemas/chat-visualization-spec.template.yaml",
        "docs/film-preproduction/schemas/chat-visualization-writeback.schema.json",
        "skills/dircreative/assets/visualizations/stage-surface-registry.json",
        "skills/dircreative/assets/visualizations/decision-surface.css",
        "skills/dircreative/assets/visualizations/decision-surface.js",
        "docs/film-preproduction/schemas/thread-dispatch-record.yaml",
        "docs/film-preproduction/schemas/thread-dispatch-record.template.yaml",
        "docs/film-preproduction/workbench-product-spec.md",
        "docs/film-preproduction/workbench-data-flow.md",
        "docs/film-preproduction/workbench-interface-plan.md",
        "docs/film-preproduction/film-commercial-quality-standard.md",
        "docs/film-preproduction/creative-production-integration.md",
        "docs/film-preproduction/goal-autorun-completion-protocol.md",
        "tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml",
        "tests/fixtures/runtime/runs/creative-production-assisted-generation-fixture.yaml",
        "tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml",
        "tests/fixtures/runtime/runs/goal-mode-simulation-visual-dogfood-receipt.yaml",
        "tests/fixtures/runtime/runs/goal-mode-rough-idea-visual-dogfood-receipt.yaml",
        "docs/film-preproduction/templates/live-user-acceptance.template.yaml",
        "tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-06.yaml",
        "tests/fixtures/runtime/runs/objective-requirement-audit-2026-06-06.yaml",
        "tests/fixtures/runtime/runs/release-gate-technical-readiness-2026-06-06.yaml",
        "tests/fixtures/invalid-live-user-acceptance-missing-scope.yaml",
        "tests/fixtures/invalid-live-user-acceptance-simulated-source.yaml",
        "tests/fixtures/invalid-thread-dispatch-worker-can-complete.yaml",
        "tests/fixtures/invalid-thread-dispatch-same-directory-write.yaml",
        "tests/fixtures/invalid-thread-dispatch-missing-professional-identity.yaml",
        "tests/fixtures/invalid-thread-dispatch-over-default-budget-no-reason.yaml",
        "tests/fixtures/invalid-thread-dispatch-over-budget.yaml",
        "tests/fixtures/invalid-thread-dispatch-second-level-completion.yaml",
        "tests/fixtures/invalid-creative-production-pre-gate.yaml",
        "tests/fixtures/invalid-creative-production-widget-truth.yaml",
        "tests/fixtures/invalid-creative-production-unreviewed-lock.yaml",
        "tests/fixtures/invalid-goal-autorun-live-acceptance.yaml",
        "tests/fixtures/invalid-chat-transcript-missing-user-confirmation.md",
        "tests/fixtures/invalid-chat-transcript-missing-simulated-choice.md",
        "tests/fixtures/invalid-video-prompt-manifest-duplicated-model-prompts.yaml",
        "tests/fixtures/invalid-video-prompt-missing-inline-anti-misread.yaml",
        "tests/fixtures/invalid-video-prompt-missing-reference-bindings.yaml",
        "tests/fixtures/invalid-video-prompt-binding-wrong-model-fragment.yaml",
        "tests/fixtures/invalid-co-creation-needs-revision-downstream.yaml",
        "tests/fixtures/invalid-reference-pack-duplicate-role.yaml",
        "tests/fixtures/invalid-reference-pack-storyboard-direct-input.yaml",
        "tests/fixtures/invalid-shot-list-low-information-density.yaml",
        "tests/fixtures/invalid-shot-list-duration-mismatch.yaml",
        "tests/fixtures/invalid-shot-list-timecode-gap.yaml",
        "tests/fixtures/valid-client-film-gate-contract.yaml",
        "tests/fixtures/invalid-client-film-direct-prompt.yaml",
        "tests/fixtures/invalid-client-film-missing-vo-timecode.yaml",
        "tests/fixtures/invalid-client-film-missing-shot-timecode.yaml",
        "tests/fixtures/invalid-client-film-internal-terms.yaml",
        "tests/fixtures/invalid-client-film-missing-asset-contract.yaml",
        "tests/fixtures/invalid-client-film-twelve-sections-as-shots.yaml",
        "tests/fixtures/invalid-assisted-image-manifest-project-title-as-dominant.yaml",
        "tests/fixtures/invalid-image-manifest-generated-without-capability.yaml",
        "tests/fixtures/invalid-image-manifest-audio-leak.yaml",
        "tests/fixtures/invalid-image-manifest-bad-prompt-fragment.yaml",
        "tests/fixtures/invalid-video-prompt-direct-input-unlocked.yaml",
        "tests/fixtures/invalid-generation-qa-character-drift-approved.yaml",
        "scripts/dircreative_adco_native_exchange.py",
        "scripts/dircreative_specialist_exchange_contract.py",
        "scripts/dircreative_activation_policy_audit.py",
        "scripts/dircreative_route.py",
        "scripts/dircreative_context_budget_audit.py",
        "scripts/dircreative_skill_stack.py",
        "scripts/dircreative_review_trust.py",
        "scripts/dircreative_validation_common.py",
        "scripts/dircreative_asset_foundation_pass.py",
        "scripts/ai_film_asset_stress_test.py",
        "scripts/ai_film_production_ledger.py",
        "scripts/dircreative_script_to_seedance_handoff.py",
        "scripts/dircreative_storyboard_frame_handoff.py",
        "scripts/dircreative_run.py",
        "scripts/dircreative_demo.py",
        "scripts/dircreative_readiness_audit.py",
        "scripts/dircreative_goal_audit.py",
        "scripts/dircreative_objective_audit.py",
        "scripts/dircreative_progress_report.py",
        "scripts/dircreative_acceptance_preflight.py",
        "scripts/dircreative_council_audit.py",
        "scripts/dircreative_thread_audit.py",
        "scripts/dircreative_quality_audit.py",
        "scripts/dircreative_creative_production_audit.py",
        "scripts/dircreative_goal_autorun_audit.py",
        "scripts/dircreative_loop_engineering_audit.py",
        "scripts/dircreative_second_level_dispatch_audit.py",
        "scripts/dircreative_validation_harness.py",
        "scripts/dircreative_chat_contract.py",
        "scripts/dircreative_chat_surface_audit.py",
        "scripts/dircreative_visualization_spec.py",
        "scripts/dircreative_visualization_audit.py",
        "scripts/dircreative_visualization_render.py",
        "scripts/dircreative_visualization_dogfood.py",
        "scripts/dircreative_visualization_browser_audit.cjs",
        "scripts/dircreative_visualization_writeback.py",
        "scripts/dircreative_visualization_adco_audit.py",
        "scripts/dircreative_install_parity.py",
        "scripts/dircreative_state_audit.py",
        "scripts/dircreative_media_forward_audit.py",
        "scripts/dircreative_release_gate.py",
        "scripts/dircreative_release_preflight.py",
        "scripts/dircreative_build_release.py",
        "scripts/dircreative_package_layout.py",
        "scripts/dircreative_verify_release.py",
        "scripts/dircreative_visual_dogfood.py",
        "scripts/dircreative_isolated_user_sim.py",
        "scripts/install_local_skill.py",
        "skills/ai-film-asset-stress-test/SKILL.md",
        "skills/ai-film-asset-stress-test/agents/openai.yaml",
        "skills/ai-film-production-ledger/SKILL.md",
        "skills/ai-film-production-ledger/agents/openai.yaml",
        "examples/cyber-courier/23-generation-qa-template.yaml",
        "examples/product-ad-raincoat/01-idea-intake.md",
        "examples/product-ad-raincoat/02-director-room-notes.md",
        "examples/product-ad-raincoat/03-concept-options.md",
        "examples/product-ad-raincoat/04-selected-concept.md",
        "examples/product-ad-raincoat/05-ad-structure.md",
        "examples/product-ad-raincoat/06-shot-list.yaml",
        "examples/product-ad-raincoat/07-reference-pack-plan.yaml",
        "examples/product-ad-raincoat/08-image-prompt-manifest.yaml",
        "examples/product-ad-raincoat/09-video-prompt-manifest.yaml",
        "examples/product-ad-raincoat/10-sequence-plan.yaml",
        "examples/product-ad-raincoat/11-longform-reference-pack.yaml",
        "examples/zombie-cleaner-test/00-source-study.md",
        "examples/zombie-cleaner-test/01-idea-intake.md",
        "examples/zombie-cleaner-test/02-director-room-notes.md",
        "examples/zombie-cleaner-test/03-concept-options.md",
        "examples/zombie-cleaner-test/04-selected-concept.md",
        "examples/zombie-cleaner-test/05-story-package.md",
        "examples/zombie-cleaner-test/06-script.md",
        "examples/zombie-cleaner-test/07-shot-list.yaml",
        "examples/zombie-cleaner-test/08-sequence-plan.yaml",
        "examples/zombie-cleaner-test/09-visual-bible.md",
        "examples/zombie-cleaner-test/10-reference-pack-plan.yaml",
        "examples/zombie-cleaner-test/11-image-prompt-manifest.yaml",
        "examples/zombie-cleaner-test/12-longform-reference-pack.yaml",
        "examples/zombie-cleaner-test/13-video-prompt-manifest.yaml",
        "examples/zombie-cleaner-test/14-workflow-run-trace.md",
        "examples/zombie-cleaner-test/15-co-creation-run.yaml",
        "examples/live-user-sim-noodle/01-idea-intake.md",
        "examples/live-user-sim-noodle/02-director-room-notes.md",
        "examples/live-user-sim-noodle/03-concept-options.md",
        "examples/live-user-sim-noodle/04-selected-concept.md",
        "examples/live-user-sim-noodle/05-story-package.md",
        "examples/live-user-sim-noodle/06-script.md",
        "examples/live-user-sim-noodle/07-shot-list.yaml",
        "examples/live-user-sim-noodle/08-visual-bible.md",
        "examples/live-user-sim-noodle/09-reference-pack-plan.yaml",
        "examples/live-user-sim-noodle/10-image-prompt-manifest.yaml",
        "examples/live-user-sim-noodle/11-video-prompt-manifest.yaml",
        "examples/live-user-sim-noodle/12-qa-retry-plan.md",
        "examples/live-user-sim-noodle/14-user-experience-trace.md",
        "examples/live-user-sim-noodle/15-co-creation-run.yaml",
        "examples/live-user-sim-noodle/16-chat-interface-demo.md",
        "examples/live-user-sim-noodle/17-ad-reference-pack-repair.md",
        "examples/complete-idea-segmentation-test/01-complete-idea.md",
        "examples/complete-idea-segmentation-test/02-director-room-notes.md",
        "examples/complete-idea-segmentation-test/02-chat-transcript.md",
        "examples/complete-idea-segmentation-test/03-shot-list.yaml",
        "examples/complete-idea-segmentation-test/04-reference-prompt-plan.md",
        "examples/complete-idea-segmentation-test/05-qa-retry-plan.md",
        "examples/complete-idea-segmentation-test/15-co-creation-run.yaml",
        "examples/goal-mode-simulation-test/01-chat-transcript.md",
        "examples/goal-mode-simulation-test/15-co-creation-run.yaml",
        "examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md",
        "examples/goal-mode-rough-idea-simulation-test/15-co-creation-run.yaml",
        "examples/goal-mode-autorun-commercial-cp-test/01-chat-transcript.md",
        "examples/goal-mode-autorun-commercial-cp-test/15-co-creation-run.yaml",
        "examples/isolated-user-simulation-test/01-simulation-pack.yaml",
        "examples/independent-agent-scent-brand-test/01-full-flow-transcript.md",
        "examples/independent-agent-scent-brand-test/02-independent-review.md",
        "examples/live-acceptance-rehearsal/01-chat-transcript.md",
        "examples/assisted-generation-preflight-chat/01-chat-transcript.md",
    ]
    if not (ROOT / "SKILL.md").exists():
        required.append(".github/workflows/ci.yml")
    skills = [
        "skills/dircreative/SKILL.md",
        "skills/dircreative/chat-facilitator/SKILL.md",
        "skills/dircreative/co-creation-gate-runtime/SKILL.md",
        "skills/dircreative/idea-intake/SKILL.md",
        "skills/dircreative/director-room/SKILL.md",
        "skills/dircreative/story-development/SKILL.md",
        "skills/dircreative/script-treatment/SKILL.md",
        "skills/dircreative/script-breakdown/SKILL.md",
        "skills/dircreative/shot-design/SKILL.md",
        "skills/dircreative/visual-bible/SKILL.md",
        "skills/dircreative/reference-image-planner/SKILL.md",
        "skills/dircreative/sequence-planner/SKILL.md",
        "skills/dircreative/longform-reference-planner/SKILL.md",
        "skills/dircreative/image-prompt-compiler/SKILL.md",
        "skills/dircreative/video-model-adapter/SKILL.md",
        "skills/dircreative/edit-assembly-planner/SKILL.md",
        "skills/dircreative/generation-qa/SKILL.md",
        "skills/dircreative/learn/SKILL.md",
        "skills/dircreative/update/SKILL.md",
        "skills/dircreative/checkpoint/SKILL.md",
    ]
    dirs = [
        ".dircreative/checkpoints",
        ".dircreative/runs",
    ]
    for path in required + skills + dirs:
        require_path(path)


def validate_yaml_and_json_parse() -> None:
    yaml_files = [
        path
        for path in iter_repo_files()
        if path.suffix in {".yaml", ".yml"} and ".git" not in path.parts
    ]
    for path in yaml_files:
        load_yaml(path)

    json_files = [
        "docs/film-preproduction/prompt-pattern-registry.json",
        "docs/film-preproduction/schemas/image-prompt-style-config.schema.json",
        "docs/film-preproduction/schemas/runtime-state.schema.json",
        "docs/film-preproduction/templates/image-prompt-style-config.template.json",
        "docs/film-preproduction/templates/runtime-state.template.json",
    ]
    for path in json_files:
        load_json(require_path(path))


def is_allowed_placeholder(path: Path, line: str) -> bool:
    allowed_thread_placeholder = "TB" + "D_THREAD_ID_IF_UNKNOWN"
    return rel(path) == "tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-19.yaml" and allowed_thread_placeholder in line


def validate_placeholder_scan() -> None:
    matches: list[str] = []
    for path in iter_repo_files():
        if path.suffix not in TEXT_FILE_KINDS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if PLACEHOLDER_RE.search(line) and not is_allowed_placeholder(path, line):
                matches.append(f"{rel(path)}:{line_no}: {line.strip()}")
    require(not matches, "placeholder markers found:\n" + "\n".join(matches[:20]))


def registry_pattern_ids() -> set[str]:
    registry = load_json(require_path("docs/film-preproduction/prompt-pattern-registry.json"))
    patterns = registry.get("patterns", [])
    ids = {item.get("pattern_id") for item in patterns}
    require(all(ids), "prompt registry contains pattern without pattern_id")
    required = {
        "art_directed_asymmetric_layout_v1",
        "json_config_prompt_v1",
        "surface_integrity_guard_v1",
        "multi_panel_identity_lock_v1",
        "search_remix_update_loop_v1",
        "forensic_visual_breakdown_v1",
    }
    require(required.issubset(ids), f"prompt registry missing required IDs: {sorted(required - ids)}")
    surface = next(item for item in patterns if item.get("pattern_id") == "surface_integrity_guard_v1")
    suffix = (
        surface.get("json_delta", {})
        .get("quality_and_artifact_control", {})
        .get("surface_integrity_guard", {})
        .get("prompt_suffix_for_image2_or_image_gen")
    )
    require(suffix == IMAGE_SURFACE_GUARD_SUFFIX, "surface_integrity_guard_v1 missing its optional internal QA macro text")
    prompt_sources = load_yaml(require_path("docs/film-preproduction/sources/prompt-sources.yaml"))
    source_rows = prompt_sources.get("sources", [])
    require(isinstance(source_rows, list), "prompt source registry sources must be a list")
    macro_rows = [row for row in source_rows if isinstance(row, dict) and row.get("source_key") == "user_surface_integrity_guard"]
    require(len(macro_rows) == 1, "prompt source registry must contain one surface-integrity macro source")
    macro_source = macro_rows[0]
    require(macro_source.get("status") == "optional_internal_qa_macro", "surface-integrity macro must remain optional")
    require(
        macro_source.get("activation_policy", {}).get("default_application") is False,
        "surface-integrity macro must default off",
    )
    require(
        "appended_to_every_image_prompt" in macro_source.get("activation_policy", {}).get("forbidden_when", []),
        "surface-integrity macro must forbid universal prompt injection",
    )

    template = load_json(require_path("docs/film-preproduction/templates/image-prompt-style-config.template.json"))
    template_ids = set(template.get("self_update", {}).get("registry_pattern_ids", []))
    require(template_ids.issubset(ids), f"template references unknown pattern IDs: {sorted(template_ids - ids)}")
    require(
        "forensic_visual_breakdown_v1" in template_ids,
        "template must include forensic_visual_breakdown_v1 registry pattern",
    )
    for field in ["evidence_policy", "visual_decomposition", "prompt_layers", "type_treatment", "style_tags"]:
        require(template.get(field), f"template missing {field}")
    decomposition = template.get("visual_decomposition", {})
    required_decomposition = {
        "subject",
        "action_pose_or_blocking",
        "details_appearance",
        "environment_background",
        "lighting_atmosphere",
        "composition_framing",
        "style_camera",
        "colors_palette",
        "materials_texture",
        "proportion_scale",
        "generation_intent",
    }
    require(
        required_decomposition.issubset(set(decomposition)),
        f"template missing visual decomposition fields: {sorted(required_decomposition - set(decomposition))}",
    )
    prompt_layers = template.get("prompt_layers", {})
    require(
        {"director_recreation_prompt", "prompt_core", "negative_prompt"}.issubset(set(prompt_layers)),
        "template missing prompt layer fields",
    )
    quality_flags = {str(item).lower() for item in template.get("quality_and_artifact_control", {}).get("quality_flags", [])}
    banned_quality = sorted(quality_flags & EMPTY_QUALITY_WORDING)
    require(not banned_quality, f"template uses empty quality wording: {banned_quality}")
    return ids


def prompt_text_from_video_entry(entry: dict[str, Any]) -> str:
    prompt = entry.get("prompt", "")
    prompt_file = entry.get("prompt_file", "")
    if prompt_file:
        prompt = read_prompt_reference(prompt_file)
    return prompt.strip()


def requests_assisted_image_generation(
    manifest: dict[str, Any],
    image_generation_capability: dict[str, Any],
    asset_output: dict[str, Any],
) -> bool:
    return (
        manifest.get("visual_output_mode") == "assisted_generation"
        or (
            image_generation_capability.get("available") is True
            and image_generation_capability.get("allowed_by_user") is True
        )
        or asset_output.get("source_tool") in {"image_gen", "image2"}
    )


def validate_image_generation_capability_consistency(
    path: str,
    image_id: str,
    manifest: dict[str, Any],
    image_generation_capability: dict[str, Any],
    asset_output: dict[str, Any],
) -> None:
    mode = manifest.get("visual_output_mode")
    image_generation_available = image_generation_capability.get("available") is True
    image_generation_allowed = image_generation_capability.get("allowed_by_user") is True
    claims_generated_asset = asset_output.get("status") == "generated_candidate"
    claims_native_generation_tool = asset_output.get("source_tool") in {"image_gen", "image2"}

    if mode == "assisted_generation":
        require(
            image_generation_available and image_generation_allowed,
            f"{path} image {image_id} assisted_generation requires image generation capability and user authorization",
        )
    if claims_generated_asset:
        require(
            mode == "assisted_generation",
            f"{path} image {image_id} generated_candidate requires assisted_generation mode",
        )
        require(
            image_generation_available and image_generation_allowed,
            f"{path} image {image_id} generated_candidate requires image generation capability and user authorization",
        )
    if claims_native_generation_tool:
        require(
            mode == "assisted_generation",
            f"{path} image {image_id} source_tool {asset_output.get('source_tool')} requires assisted_generation mode",
        )
        require(
            image_generation_available and image_generation_allowed,
            f"{path} image {image_id} source_tool {asset_output.get('source_tool')} requires image generation capability and user authorization",
        )


def validate_pre_generation_contract(path: str, image_id: str, image: dict[str, Any], prompt_text: str) -> None:
    pre_contract = image.get("pre_generation_contract")
    require(isinstance(pre_contract, dict), f"{path} image {image_id} missing pre_generation_contract for assisted image generation")
    require(pre_contract.get("status") == "pass", f"{path} image {image_id} pre_generation_contract.status must be pass before image generation")
    require(pre_contract.get("image_generation_allowed") is True, f"{path} image {image_id} pre_generation_contract must set image_generation_allowed: true")
    require(pre_contract.get("asset_id") == image_id, f"{path} image {image_id} pre_generation_contract.asset_id must match image_id")
    require(pre_contract.get("asset_role") == image.get("type"), f"{path} image {image_id} pre_generation_contract.asset_role must match image type")

    dominant_title = pre_contract.get("dominant_title")
    require(isinstance(dominant_title, str) and dominant_title.strip(), f"{path} image {image_id} pre_generation_contract.dominant_title missing")
    require(
        dominant_title != "FOG ROUTE CLEANER" and "REFERENCE" in dominant_title.upper(),
        f"{path} image {image_id} pre_generation_contract.dominant_title must be the reference role label, not the project title",
    )
    require(pre_contract.get("secondary_project_metadata"), f"{path} image {image_id} pre_generation_contract.secondary_project_metadata missing")

    title_hierarchy = pre_contract.get("title_hierarchy", {})
    require(title_hierarchy.get("role_label_largest") is True, f"{path} image {image_id} title_hierarchy.role_label_largest must be true")
    require(title_hierarchy.get("project_title_secondary") is True, f"{path} image {image_id} title_hierarchy.project_title_secondary must be true")
    forbidden_largest_text = title_hierarchy.get("forbidden_largest_text", [])
    require(isinstance(forbidden_largest_text, list) and forbidden_largest_text, f"{path} image {image_id} title_hierarchy.forbidden_largest_text missing")

    role_purity = pre_contract.get("role_purity", {})
    require(role_purity.get("primary_job"), f"{path} image {image_id} role_purity.primary_job missing")
    require(role_purity.get("must_not_do"), f"{path} image {image_id} role_purity.must_not_do missing")

    inheritance = pre_contract.get("inheritance", {})
    require("character_identity_source" in inheritance, f"{path} image {image_id} inheritance.character_identity_source missing")
    require("scene_geography_source" in inheritance, f"{path} image {image_id} inheritance.scene_geography_source missing")

    direct_policy = pre_contract.get("direct_video_input_policy", {})
    declared_direct = image.get("direct_video_input", {}).get("allowed")
    if declared_direct in {True, False}:
        require(direct_policy.get("allowed") is declared_direct, f"{path} image {image_id} direct_video_input_policy.allowed must match direct_video_input.allowed")
    else:
        require(direct_policy.get("allowed") in {True, False}, f"{path} image {image_id} direct_video_input_policy.allowed missing")
    require(direct_policy.get("reason"), f"{path} image {image_id} direct_video_input_policy.reason missing")

    prompt_lint = pre_contract.get("prompt_lint", {})
    for key in [
        "exact_role_label_present",
        "title_hierarchy_instruction_present",
        "forbidden_poster_hierarchy_present",
        "no_unowned_scene_or_character_redesign",
    ]:
        require(prompt_lint.get(key) is True, f"{path} image {image_id} prompt_lint.{key} must be true")

    require(dominant_title in prompt_text, f"{path} image {image_id} prompt must contain pre_generation_contract.dominant_title")
    require(str(pre_contract.get("secondary_project_metadata")) in prompt_text, f"{path} image {image_id} prompt must contain secondary_project_metadata")
    prompt_lower = prompt_text.lower()
    require("largest title" in prompt_lower or "最大标题" in prompt_text, f"{path} image {image_id} prompt must explicitly instruct dominant_title as largest title")
    require("secondary" in prompt_lower or "次级" in prompt_text or "小号" in prompt_text, f"{path} image {image_id} prompt must explicitly keep project metadata secondary")
    for forbidden in forbidden_largest_text:
        if isinstance(forbidden, str) and forbidden.strip() and forbidden.lower() not in {"film title", "project title"}:
            require(forbidden in prompt_text, f"{path} image {image_id} prompt must name forbidden largest text: {forbidden}")


def validate_prompt_text_contract(path: str, image_id: str, image: dict[str, Any], prompt_text: str, project_title: str) -> None:
    image_type = image.get("type", "")
    text_policy = image.get("text_policy")
    is_clean_frame = image_type in {"clean_first_frame", "clean_key_frame", "clean_end_frame"} or text_policy == "no_text"
    is_storyboard = "storyboard" in image_type
    require(
        "Pre-generation contract:" in prompt_text or "Clean frame contract:" in prompt_text,
        f"{path} image {image_id} prompt must include a visible pre-generation contract",
    )
    require("Direct video input policy:" in prompt_text, f"{path} image {image_id} prompt missing Direct video input policy")
    if not is_storyboard:
        prompt_lower = prompt_text.lower()
        leaked_terms = [term for term in IMAGE_AUDIO_GENERATION_TERMS if term in prompt_lower or term in prompt_text]
        require(
            not leaked_terms,
            f"{path} image {image_id} non-storyboard image prompt must not include audio generation terms: {leaked_terms}",
        )
    if is_clean_frame:
        require("no visible title" in prompt_text.lower(), f"{path} clean frame {image_id} prompt must forbid visible titles")
        require("labels" in prompt_text.lower() and "panels" in prompt_text.lower(), f"{path} clean frame {image_id} prompt must forbid labels and panels")
        require("allowed" in prompt_text.lower(), f"{path} clean frame {image_id} prompt must state direct video input is allowed")
    else:
        require("Largest title on the page:" in prompt_text, f"{path} image {image_id} prompt missing largest-title instruction")
        require("Smaller metadata only:" in prompt_text, f"{path} image {image_id} prompt missing smaller-metadata instruction")
        require(project_title in prompt_text, f"{path} image {image_id} prompt must name project title as secondary metadata")
        require("Do not make" in prompt_text and "largest title" in prompt_text, f"{path} image {image_id} prompt must forbid poster-title hierarchy")
        require(
            any(term in prompt_text for term in ["NOT DIRECT VIDEO INPUT", "PLANNING ONLY", "reference only", "planning-only"]),
            f"{path} image {image_id} prompt must state board is not a direct video frame",
        )
    if is_storyboard:
        for term in ["timecode", "duration", "camera movement", "model risk"]:
            require(term in prompt_text.lower(), f"{path} storyboard image {image_id} prompt missing {term}")
        require("sound" in prompt_text.lower() or "audio" in prompt_text.lower(), f"{path} storyboard image {image_id} prompt missing sound/audio")


def validate_optional_surface_guard_contract(
    path: str,
    image_id: str,
    style_config: dict[str, Any],
    prompt_text: str,
) -> None:
    guard = (
        style_config.get("quality_and_artifact_control", {})
        .get("surface_integrity_guard", {})
    )
    require(isinstance(guard, dict), f"{path} image {image_id} surface-integrity guard must be a mapping")
    suffix_present = IMAGE_SURFACE_GUARD_SUFFIX in prompt_text
    enabled = guard.get("optional_internal_qa_macro") is True
    activation = guard.get("activation", "off")
    failure_id = guard.get("failure_id", "")
    if enabled:
        require(
            activation in {"observed_failure", "internal_ab_eval"},
            f"{path} image {image_id} optional surface macro has invalid activation",
        )
        require(isinstance(failure_id, str) and failure_id.strip(), f"{path} image {image_id} optional surface macro lacks failure ID")
        require(suffix_present, f"{path} image {image_id} enabled optional surface macro is absent from prompt")
    else:
        require(activation in {None, "", "off"}, f"{path} image {image_id} disabled surface macro has active activation")
        require(not failure_id, f"{path} image {image_id} disabled surface macro must not claim a failure ID")
        require(not suffix_present, f"{path} image {image_id} fixed surface macro was injected without activation")


def validate_image_manifest(path: str, pattern_ids: set[str]) -> None:
    data = load_yaml(require_path(path))
    manifest = data.get("image_prompt_manifest", {})
    project_title = manifest.get("project_title", "")
    require(manifest.get("authoring_mode") == "json_first", f"{path} must use json_first authoring")
    require(manifest.get("visual_output_mode") in VISUAL_OUTPUT_MODES, f"{path} missing valid visual_output_mode")
    require(manifest.get("longform_generation_mode") in LONGFORM_MODES, f"{path} missing valid longform_generation_mode")
    capabilities = data.get("execution_capabilities", {})
    image_generation_capability = capabilities.get("image_generation", {})
    require(image_generation_capability.get("available") in {True, False}, f"{path} missing image generation capability receipt")
    selected_ids = set(manifest.get("style_system", {}).get("selected_pattern_ids", []))
    require(selected_ids, f"{path} has no selected pattern IDs")
    require(selected_ids.issubset(pattern_ids), f"{path} references unknown pattern IDs: {sorted(selected_ids - pattern_ids)}")

    images = data.get("images", [])
    require(images, f"{path} has no images")
    for image in images:
        image_id = image.get("image_id", "unknown")
        image_type = image.get("type", "")
        text_policy = image.get("text_policy")
        is_clean_frame = image_type in {"clean_first_frame", "clean_key_frame", "clean_end_frame"} or text_policy == "no_text"
        style_config = image.get("style_config", {})
        source_patterns = set(style_config.get("source_patterns", []))
        local_ids = set(style_config.get("self_update", {}).get("registry_pattern_ids", []))
        qa = image.get("qa", {})
        require(image.get("purpose"), f"{path} image {image_id} missing purpose")
        if is_clean_frame:
            require(image.get("exact_text_labels", []) == [], f"{path} clean frame {image_id} must not declare text labels")
            require(text_policy == "no_text", f"{path} clean frame {image_id} must use text_policy: no_text")
            direct = image.get("direct_video_input", {})
            require(direct.get("allowed") is True, f"{path} clean frame {image_id} must be direct video input")
            require(direct.get("shot_id"), f"{path} clean frame {image_id} missing direct video shot_id")
            require(direct.get("model_slots"), f"{path} clean frame {image_id} missing model slots")
        else:
            require(image.get("exact_text_labels"), f"{path} image {image_id} missing exact text labels")
        asset_output = image.get("asset_output", {})
        require(asset_output.get("status") in ASSET_OUTPUT_STATUSES, f"{path} image {image_id} missing valid asset_output status")
        if manifest.get("visual_output_mode") in {"prompt_only", "external_generation"}:
            require(asset_output.get("external_instructions"), f"{path} image {image_id} missing external instructions for non-assisted mode")
        validate_image_generation_capability_consistency(path, image_id, manifest, image_generation_capability, asset_output)
        require(source_patterns.issubset(pattern_ids), f"{path} image {image_id} unknown source patterns: {sorted(source_patterns - pattern_ids)}")
        require(local_ids.issubset(pattern_ids), f"{path} image {image_id} unknown registry IDs: {sorted(local_ids - pattern_ids)}")
        require(style_config.get("art_direction_policy"), f"{path} image {image_id} missing art direction policy")
        require(style_config.get("quality_and_artifact_control"), f"{path} image {image_id} missing artifact control")
        common_qa = ["role_clear", "continuity_locks_present", "output_mode_supported", "asset_output_status_present", "video_model_safe"]
        require(all(qa.get(key) is True for key in common_qa), f"{path} image {image_id} common QA flags not all true")
        if is_clean_frame:
            require(qa.get("text_absent") is True, f"{path} clean frame {image_id} must confirm text_absent")
            require(qa.get("panels_absent") is True, f"{path} clean frame {image_id} must confirm panels_absent")
        else:
            require(all(qa.get(key) is True for key in ["text_readable", "panels_large_enough"]), f"{path} image {image_id} board QA flags not all true")
        prompt_file = image.get("prompt_file")
        inline_prompt = image.get("prompt")
        prompt_text = ""
        if prompt_file:
            prompt_text = read_prompt_reference(prompt_file)
        else:
            require(isinstance(inline_prompt, str) and inline_prompt.strip(), f"{path} image {image_id} missing prompt text or prompt file")
            prompt_text = inline_prompt
        asset_prompt_file = asset_output.get("prompt_file")
        if asset_prompt_file:
            asset_path_part, asset_fragment = split_reference(asset_prompt_file)
            if asset_fragment and asset_path_part == path:
                require(asset_fragment == image_id, f"{path} image {image_id} asset_output.prompt_file fragment must match image_id")
            asset_prompt_text = read_prompt_reference(asset_prompt_file)
            if asset_fragment and asset_path_part == path and isinstance(inline_prompt, str) and inline_prompt.strip():
                require(
                    asset_prompt_text.strip() == inline_prompt.strip(),
                    f"{path} image {image_id} asset_output.prompt_file must resolve to this image prompt",
                )
        validate_optional_surface_guard_contract(path, image_id, style_config, prompt_text)
        validate_prompt_text_contract(path, image_id, image, prompt_text, project_title)
        if requests_assisted_image_generation(manifest, image_generation_capability, asset_output):
            validate_pre_generation_contract(path, image_id, image, prompt_text)


def validate_video_manifest(path: str) -> None:
    data = load_yaml(require_path(path))
    manifest = data.get("video_prompt_manifest", {})
    require(manifest.get("visual_output_mode") in VISUAL_OUTPUT_MODES, f"{path} missing valid visual_output_mode")
    require(manifest.get("longform_generation_mode") in LONGFORM_MODES, f"{path} missing valid longform_generation_mode")
    strategy = manifest.get("selected_reference_strategy")
    require(strategy in {"all_reference_sequence", "hybrid", "per_shot_i2v", "minimal_test"}, f"{path} missing valid selected_reference_strategy")
    video_generation_capability = data.get("execution_capabilities", {}).get("video_generation", {})
    require(video_generation_capability.get("available") in {True, False}, f"{path} missing video generation capability receipt")
    reference_map = data.get("reference_map", [])
    require(reference_map, f"{path} missing reference_map")
    reference_status_by_id: dict[str, str] = {}
    for ref in reference_map:
        ref_id = ref.get("ref_id", "unknown")
        require(ref.get("asset_output_status") in ASSET_OUTPUT_STATUSES, f"{path} ref {ref_id} missing valid asset_output_status")
        reference_status_by_id[ref_id] = ref.get("asset_output_status")
        if manifest.get("visual_output_mode") in {"prompt_only", "external_generation"}:
            require(ref.get("external_generation_instructions"), f"{path} ref {ref_id} missing external generation instructions")
    bindings = data.get("reference_bindings", [])
    require(bindings, f"{path} selected reference strategy requires reference_bindings")
    binding_models: set[str] = set()
    binding_ref_ids: set[str] = set()
    for binding in bindings:
        require(binding.get("model") in set(REQUIRED_VIDEO_MODELS), f"{path} invalid reference binding model")
        require(binding.get("ref_id"), f"{path} reference binding missing ref_id")
        require(binding.get("upload_slot"), f"{path} reference binding missing upload_slot")
        require(binding.get("role") in {"primary_direct_input", "secondary_reference", "planning_only", "style_reference", "element_reference"}, f"{path} invalid reference binding role")
        validate_reference_binding_prompt_file(path, binding)
        ref_id = binding.get("ref_id")
        require(ref_id in reference_status_by_id, f"{path} reference binding points to unknown ref_id: {ref_id}")
        binding_models.add(binding.get("model"))
        binding_ref_ids.add(ref_id)
        if binding.get("role") == "primary_direct_input" and binding.get("required_for_generation") is True:
            ref_status = reference_status_by_id.get(ref_id)
            if ref_status not in {"user_locked", "external_imported"}:
                require(
                    video_generation_capability.get("available") is False,
                    f"{path} primary direct input {ref_id} must be user_locked or external_imported before video generation is available",
                )
                risk_note = str(binding.get("risk_note", "")).lower()
                require(
                    all(term in risk_note for term in ["blocked", "generated", "locked"]),
                    f"{path} primary direct input {ref_id} must state blocked until generated/imported and user locked",
                )
    require(set(REQUIRED_VIDEO_MODELS).issubset(binding_models), f"{path} reference_bindings must cover every video model")
    require(set(reference_status_by_id).issubset(binding_ref_ids), f"{path} every reference_map ref_id must appear in reference_bindings")
    require(data.get("universal_anti_misread_clause"), f"{path} missing anti-misread clause")
    model_prompts = data.get("model_prompts", {})
    prompts: dict[str, str] = {}
    for model in REQUIRED_VIDEO_MODELS:
        entry = model_prompts.get(model, {})
        require(entry.get("enabled") is True, f"{path} model {model} not enabled")
        require(entry.get("reference_warning"), f"{path} model {model} missing reference warning")
        require(entry.get("audio_policy"), f"{path} model {model} missing audio policy")
        require(entry.get("risk_notes"), f"{path} model {model} missing risk notes")
        require(entry.get("retry_rules"), f"{path} model {model} missing retry rules")
        prompt = prompt_text_from_video_entry(entry)
        require(prompt, f"{path} model {model} missing prompt text")
        prompt_lower = prompt.lower()
        require(
            "board" in prompt_lower
            and any(term in prompt_lower for term in ["do not show", "not show", "avoid", "not the board"])
            and any(term in prompt_lower for term in ["label", "panel", "layout", "arrow", "grid"]),
            f"{path} model {model} prompt must include inline anti-misread instruction for reference boards",
        )
        prompts[model] = prompt
    hashes = {model: hashlib.sha256(text.encode("utf-8")).hexdigest() for model, text in prompts.items()}
    require(len(set(hashes.values())) == len(REQUIRED_VIDEO_MODELS), f"{path} contains duplicated model prompt text")
    require(data.get("qa", {}).get("model_prompts_differ_materially") is True, f"{path} QA does not confirm model prompt difference")
    for key in ["visual_output_mode_valid", "capability_receipt_present", "missing_generated_assets_blocked", "longform_sequence_refs_valid"]:
        require(data.get("qa", {}).get(key) is True, f"{path} video QA missing or false: {key}")
    for key in ["reference_bindings_present", "selected_reference_strategy_present"]:
        require(data.get("qa", {}).get(key) is True, f"{path} video QA missing or false: {key}")


def validate_reference_pack_manifest(path: str) -> None:
    data = load_yaml(require_path(path))
    manifest = data.get("reference_pack_manifest", {})
    require(manifest, f"{path} missing reference_pack_manifest")
    require(manifest.get("strategy") == "compressed_model_safe_pack", f"{path} must use compressed_model_safe_pack")
    require(manifest.get("visual_output_mode") in VISUAL_OUTPUT_MODES, f"{path} missing valid visual_output_mode")
    require(manifest.get("longform_generation_mode") in LONGFORM_MODES, f"{path} missing valid longform_generation_mode")
    require(manifest.get("execution_capabilities", {}).get("image_generation", {}).get("available") in {True, False}, f"{path} missing execution capability receipt")
    strategy = manifest.get("reference_strategy", {})
    if strategy:
        require(strategy.get("selected") in {"all_reference_sequence", "hybrid", "per_shot_i2v", "minimal_test"}, f"{path} invalid reference strategy")
        require(strategy.get("rationale"), f"{path} reference strategy missing rationale")
        require(strategy.get("shot_count_policy"), f"{path} reference strategy missing shot_count_policy")
        require(strategy.get("clean_frame_policy") in {"not_required", "selected_key_frames", "every_shot", "start_end_only"}, f"{path} invalid clean_frame_policy")

    gate = manifest.get("user_decision_gate", {})
    require(gate.get("required") is True, f"{path} user decision gate not required")
    require(gate.get("status") == "approved", f"{path} user decision gate must be approved for fixture")
    require(gate.get("user_lock_required_before_video_adapter") is True, f"{path} missing user lock requirement")

    assets = manifest.get("assets", [])
    require(assets, f"{path} has no reference assets")
    roles = [asset.get("role") for asset in assets]
    role_set = set(roles)
    required_roles = {"identity_product_board", "environment_camera_board", "storyboard_motion_board", "clean_first_frame"}
    unique_primary_roles = required_roles | {"style_material_board", "master_reference_board", "prop_continuity_board", "vehicle_continuity_board"}
    require(required_roles.issubset(role_set), f"{path} missing required reference roles: {sorted(required_roles - role_set)}")
    primary_role_counts = {role: roles.count(role) for role in role_set if role}
    duplicate_primary_roles = {
        role: count
        for role, count in primary_role_counts.items()
        if count > 1 and role in unique_primary_roles
    }
    require(not duplicate_primary_roles, f"{path} duplicate primary reference roles: {duplicate_primary_roles}")

    dense_roles = {"master_reference_board", "environment_camera_board", "storyboard_motion_board"}
    for asset in assets:
        asset_id = asset.get("asset_id", "unknown")
        role = asset.get("role")
        direct_policy = asset.get("direct_input_policy", {})
        qa = asset.get("qa", {})
        require(asset.get("primary_job"), f"{path} asset {asset_id} missing primary_job")
        require(asset.get("status") in {"candidate", "selected", "locked", "superseded"}, f"{path} asset {asset_id} invalid status")
        asset_output = asset.get("asset_output", {})
        require(asset_output.get("status") in ASSET_OUTPUT_STATUSES, f"{path} asset {asset_id} missing valid asset_output status")
        if manifest.get("visual_output_mode") in {"prompt_only", "external_generation"}:
            require(asset_output.get("external_instructions"), f"{path} asset {asset_id} missing external instructions")
        require(all(model in direct_policy for model in ["seedance", "kling", "runway", "veo"]), f"{path} asset {asset_id} missing direct input policy")
        require(qa.get("one_primary_job") is True, f"{path} asset {asset_id} does not confirm one primary job")
        require(qa.get("readable_at_video_resolution") is True, f"{path} asset {asset_id} not readable at video resolution")
        if role in dense_roles:
            require(direct_policy.get("kling") in {"forbidden", "planning_only", "element_only"}, f"{path} dense asset {asset_id} unsafe for Kling")
            require(direct_policy.get("runway") in {"forbidden", "planning_only", "reference_only"}, f"{path} dense asset {asset_id} unsafe for Runway")
            require(asset.get("must_not_animate"), f"{path} dense asset {asset_id} missing must_not_animate")
            require(qa.get("anti_misread_clause_required") is True, f"{path} dense asset {asset_id} should require anti-misread clause")
        if role == "clean_first_frame":
            require(direct_policy.get("kling") == "allowed", f"{path} clean first frame not allowed for Kling")
            require(direct_policy.get("runway") == "allowed", f"{path} clean first frame not allowed for Runway")
            require(asset.get("text_policy") == "no_text", f"{path} clean first frame must have no text policy")
            prompts = asset.get("clean_frame_prompts", [])
            if asset_output.get("status") == "prompt_ready":
                require(prompts or asset_output.get("prompt_file"), f"{path} clean first frame prompt_ready requires prompt files")
            for prompt in prompts:
                require(prompt.get("shot_id"), f"{path} clean frame prompt missing shot_id")
                require(prompt.get("frame_role") in {"clean_first_frame", "clean_key_frame", "clean_end_frame"}, f"{path} clean frame prompt has invalid frame_role")
                require_path(prompt.get("prompt_file", ""))
                require(prompt.get("primary_model_slots"), f"{path} clean frame prompt missing model slots")

    recipes = manifest.get("model_pack_recipes", {})
    for model in ["seedance", "kling", "runway", "veo"]:
        recipe = recipes.get(model, {})
        require(recipe.get("enabled") is True, f"{path} missing enabled recipe for {model}")
    require(recipes.get("seedance", {}).get("required_bindings"), f"{path} missing Seedance bindings")
    require(recipes.get("kling", {}).get("prefer_clean_first_frame") is True, f"{path} Kling must prefer clean first frame")
    require("storyboard_motion_board" in recipes.get("kling", {}).get("forbidden_primary_input_roles", []), f"{path} Kling must forbid storyboard board primary input")
    require(recipes.get("runway", {}).get("prefer_clean_first_frame") is True, f"{path} Runway must prefer clean first frame")
    require(recipes.get("veo", {}).get("reference_map_required") is True, f"{path} Veo must require reference map")

    qa = manifest.get("qa", {})
    for key in ["roles_unique", "dense_board_policy_present", "clean_first_frame_policy_present", "visual_output_mode_valid", "capability_receipt_present", "asset_output_statuses_present", "longform_mode_valid", "model_budget_ok", "video_model_safe"]:
        require(qa.get(key) is True, f"{path} reference pack QA missing or false: {key}")


def validate_sequence_plan(path: str) -> None:
    data = load_yaml(require_path(path))
    plan = data.get("sequence_plan", {})
    require(plan, f"{path} missing sequence_plan")
    require(plan.get("visual_output_mode") in VISUAL_OUTPUT_MODES, f"{path} missing valid visual_output_mode")
    require(plan.get("longform_generation_mode") in LONGFORM_MODES, f"{path} missing valid longform_generation_mode")
    capabilities = data.get("execution_capabilities", {})
    require(capabilities.get("image_generation", {}).get("available") in {True, False}, f"{path} missing image generation capability")
    policy = data.get("generation_unit_policy", {})
    min_unit = policy.get("min_unit_sec")
    max_unit = policy.get("max_unit_sec")
    require(min_unit and max_unit and min_unit <= max_unit <= 15, f"{path} invalid generation unit policy")
    sequences = data.get("sequences", [])
    require(sequences, f"{path} has no sequences")
    total = 0
    for sequence in sequences:
        seq_id = sequence.get("sequence_id", "unknown")
        duration = sequence.get("duration_sec")
        require(isinstance(duration, int) and min_unit <= duration <= max_unit, f"{path} sequence {seq_id} invalid duration")
        total += duration
        require(sequence.get("dramatic_function"), f"{path} sequence {seq_id} missing dramatic function")
        require(sequence.get("required_reference_pack_id"), f"{path} sequence {seq_id} missing reference pack id")
        require(sequence.get("user_gate", {}).get("required") is True, f"{path} sequence {seq_id} missing user gate")
        require(sequence.get("edit_handoff", {}).get("audio_handoff"), f"{path} sequence {seq_id} missing audio handoff")
    require(total == plan.get("target_duration_sec"), f"{path} sequence durations {total} do not match target {plan.get('target_duration_sec')}")
    qa = data.get("qa", {})
    for key in ["duration_matches_target", "sequence_units_within_model_limit", "global_anchors_present", "user_gates_match_mode", "prompt_only_supported"]:
        require(qa.get(key) is True, f"{path} sequence QA missing or false: {key}")


def validate_longform_reference_pack(path: str) -> None:
    data = load_yaml(require_path(path))
    pack = data.get("longform_reference_pack", {})
    require(pack, f"{path} missing longform_reference_pack")
    require(pack.get("visual_output_mode") in VISUAL_OUTPUT_MODES, f"{path} missing valid visual_output_mode")
    require(pack.get("longform_generation_mode") in LONGFORM_MODES, f"{path} missing valid longform_generation_mode")
    global_assets = data.get("global_pack", {}).get("assets", [])
    sequence_packs = data.get("sequence_packs", [])
    selected_cards = data.get("capability_resolution", {}).get("selected_cards", [])
    require(isinstance(selected_cards, list) and selected_cards, f"{path} missing exact capability-card resolution")
    selected_card_ids = [row.get("capability_card_id") for row in selected_cards if isinstance(row, dict)]
    require(
        len(selected_card_ids) == len(selected_cards)
        and all(isinstance(card_id, str) and card_id.strip() for card_id in selected_card_ids)
        and len(set(selected_card_ids)) == len(selected_card_ids),
        f"{path} capability-card resolution has blank, malformed, or duplicate IDs",
    )
    selected_card_id_set = set(selected_card_ids)
    require(global_assets, f"{path} missing global assets")
    require(sequence_packs, f"{path} missing sequence packs")
    for collection_name, assets in [("global", global_assets)]:
        for asset in assets:
            asset_id = asset.get("asset_id", "unknown")
            asset_output = asset.get("asset_output", {})
            require(asset.get("primary_job"), f"{path} {collection_name} asset {asset_id} missing primary job")
            require(asset_output.get("status") in ASSET_OUTPUT_STATUSES, f"{path} {collection_name} asset {asset_id} missing valid output status")
    for sequence_pack in sequence_packs:
        seq_id = sequence_pack.get("sequence_id", "unknown")
        require(sequence_pack.get("user_gate", {}).get("required") is True, f"{path} sequence pack {seq_id} missing user gate")
        require(sequence_pack.get("continuity_reuse", {}).get("global_asset_ids"), f"{path} sequence pack {seq_id} missing global asset reuse")
        require("model_targets" not in sequence_pack, f"{path} sequence pack {seq_id} retains legacy family-level model_targets")
        capability_targets = sequence_pack.get("capability_targets", [])
        require(isinstance(capability_targets, list) and capability_targets, f"{path} sequence pack {seq_id} missing capability targets")
        target_ids: set[str] = set()
        for target in capability_targets:
            require(isinstance(target, dict), f"{path} sequence pack {seq_id} capability target must be a mapping")
            require(
                "model_family" not in target and "model_key" not in target,
                f"{path} sequence pack {seq_id} capability target must not use a family alias",
            )
            card_id = target.get("capability_card_id")
            require(
                card_id in selected_card_id_set and card_id not in target_ids,
                f"{path} sequence pack {seq_id} capability target is unresolved or duplicated: {card_id}",
            )
            require(target.get("operation") in {"generate", "edit", "extend"}, f"{path} sequence pack {seq_id} target {card_id} has invalid operation")
            require(isinstance(target.get("enabled"), bool), f"{path} sequence pack {seq_id} target {card_id} missing boolean enabled")
            reference_policy = target.get("reference_policy")
            require(isinstance(reference_policy, dict), f"{path} sequence pack {seq_id} target {card_id} missing reference policy")
            for key in [
                "board_input_allowed",
                "clean_start_frame_required",
                "clean_end_frame_preferred",
                "element_reference_preferred",
                "structured_reference_map_required",
            ]:
                require(
                    isinstance(reference_policy.get(key), bool),
                    f"{path} sequence pack {seq_id} target {card_id} reference policy missing boolean {key}",
                )
            target_ids.add(card_id)
        require(
            target_ids == selected_card_id_set,
            f"{path} sequence pack {seq_id} capability targets do not cover the exact selected cards",
        )
        assets = sequence_pack.get("assets", [])
        require(assets, f"{path} sequence pack {seq_id} missing assets")
        for asset in assets:
            asset_id = asset.get("asset_id", "unknown")
            asset_output = asset.get("asset_output", {})
            direct_input_policy = asset.get("direct_input_policy", [])
            require(
                isinstance(direct_input_policy, list) and direct_input_policy,
                f"{path} sequence asset {asset_id} missing exact-card direct-input policy",
            )
            policy_ids: set[str] = set()
            for policy in direct_input_policy:
                require(isinstance(policy, dict), f"{path} sequence asset {asset_id} direct-input policy must be a mapping")
                card_id = policy.get("capability_card_id")
                require(
                    card_id in target_ids and card_id not in policy_ids,
                    f"{path} sequence asset {asset_id} direct-input policy card is unresolved or duplicated: {card_id}",
                )
                require(
                    policy.get("input_mode") in {"allowed", "conditional", "forbidden", "planning_only", "element_only", "reference_only"},
                    f"{path} sequence asset {asset_id} has invalid direct-input mode",
                )
                policy_ids.add(card_id)
            require(policy_ids == target_ids, f"{path} sequence asset {asset_id} direct-input policy does not cover exact targets")
            require(asset_output.get("status") in ASSET_OUTPUT_STATUSES, f"{path} sequence asset {asset_id} missing valid output status")
            require(asset.get("qa", {}).get("one_primary_job") is True, f"{path} sequence asset {asset_id} missing primary job QA")
            require(asset.get("qa", {}).get("video_model_safe") is True, f"{path} sequence asset {asset_id} not video model safe")
    qa = data.get("qa", {})
    for key in ["global_pack_locked_or_prompt_ready", "per_sequence_policy_valid", "output_statuses_present", "model_budget_ok", "video_model_safe"]:
        require(qa.get(key) is True, f"{path} longform QA missing or false: {key}")


def validate_co_creation_run(path: str) -> None:
    """Read a frozen v1 fixture; never use this validator as a v2 run template."""
    data = load_yaml(require_path(path))
    run = data.get("co_creation_run", {})
    require(run, f"{path} missing co_creation_run")
    run_type = run.get("run_type")
    require(run.get("version") in {None, "1.0.0"}, f"{path} legacy fixture must remain v1")
    require(run_type in LEGACY_V1_CO_CREATION_RUN_TYPES, f"{path} invalid run_type: {run_type}")
    require(run.get("visual_output_mode") in VISUAL_OUTPUT_MODES, f"{path} missing valid visual_output_mode")
    require(run.get("longform_generation_mode") in LONGFORM_MODES, f"{path} missing valid longform_generation_mode")

    if run_type == "dry_run_fixture":
        require(run.get("simulated_choices_allowed") is True, f"{path} dry run must allow simulated choices")
        require(run.get("real_user_co_creation_verified") is False, f"{path} dry run cannot claim real user co-creation")
    if run_type == "live_user_run":
        require(run.get("simulated_choices_allowed") is False, f"{path} live run cannot allow simulated choices")
        require(run.get("real_user_co_creation_verified") is True, f"{path} live run must verify real user co-creation")

    policy = data.get("gate_policy", {})
    required_policy_gates = set(policy.get("required_gates", []))
    required_gates = set(LEGACY_V1_CO_CREATION_GATE_TYPES)
    require(required_gates.issubset(required_policy_gates), f"{path} gate policy missing gates: {sorted(required_gates - required_policy_gates)}")

    gates = data.get("gates", [])
    require(gates, f"{path} missing gates")
    gate_types = [gate.get("gate_type") for gate in gates]
    missing = [gate_type for gate_type in LEGACY_V1_CO_CREATION_GATE_TYPES if gate_type not in gate_types]
    require(not missing, f"{path} missing required gates: {missing}")
    gate_ids = [gate.get("gate_id") for gate in gates]
    require(len(gate_ids) == len(set(gate_ids)), f"{path} duplicate gate ids")

    simulated_count = 0
    pending_media_count = 0
    resolved_media_count = 0
    for gate in gates:
        gate_id = gate.get("gate_id", "unknown")
        gate_type = gate.get("gate_type")
        status = gate.get("status")
        source = gate.get("decision_source")
        require(gate_type in LEGACY_V1_CO_CREATION_GATE_TYPES, f"{path} gate {gate_id} has invalid gate_type {gate_type}")
        require(status in LEGACY_V1_CO_CREATION_GATE_STATUSES, f"{path} gate {gate_id} has invalid status {status}")
        require(source in LEGACY_V1_CO_CREATION_DECISION_SOURCES, f"{path} gate {gate_id} has invalid decision_source {source}")
        require(isinstance(gate.get("options_presented"), list) and gate.get("options_presented"), f"{path} gate {gate_id} must present options")

        if source == "system_default":
            raise ValidationError(f"{path} gate {gate_id} uses system_default for creative decision")
        if source == "simulated_fixture":
            simulated_count += 1
            require(run_type == "dry_run_fixture", f"{path} gate {gate_id} uses simulated_fixture outside dry run")
        if run_type == "live_user_run" and status == "approved":
            require(source == "real_user", f"{path} live approved gate {gate_id} must use real_user")
        if status == "approved":
            require(source in {"real_user", "simulated_fixture"}, f"{path} approved gate {gate_id} has non-final source {source}")
            require(bool(gate.get("selected_option")), f"{path} approved gate {gate_id} missing selected_option")
            if gate_type in LEGACY_V1_MEDIA_BLOCKING_GATES:
                resolved_media_count += 1
        if status == "skipped_with_risk":
            require(source in {"real_user", "simulated_fixture"}, f"{path} skipped gate {gate_id} has non-final source {source}")
            require(bool(gate.get("selected_option")), f"{path} skipped gate {gate_id} missing selected_option")
            if gate_type in LEGACY_V1_MEDIA_BLOCKING_GATES:
                resolved_media_count += 1
        if status == "needs_revision":
            require(source in {"real_user", "simulated_fixture"}, f"{path} needs_revision gate {gate_id} must identify a real or simulated reviewer")
            require(not gate.get("downstream_artifacts"), f"{path} needs_revision gate {gate_id} cannot declare writable downstream artifacts")
            require(gate.get("blocks"), f"{path} needs_revision gate {gate_id} must block downstream work")
            require(
                any(block in gate.get("blocks", []) for block in ["downstream_artifact_write", "media_generation"]),
                f"{path} needs_revision gate {gate_id} must block downstream artifact writes or media generation",
            )
        if status == "pending":
            require(source == "pending", f"{path} pending gate {gate_id} must use pending source")
            if gate_type in LEGACY_V1_MEDIA_BLOCKING_GATES:
                require("media_generation" in gate.get("blocks", []), f"{path} pending media gate {gate_id} must block media_generation")
                pending_media_count += 1

    if run_type == "dry_run_fixture":
        require(simulated_count > 0, f"{path} dry run should include labeled simulated gates")
        require(
            pending_media_count > 0 or resolved_media_count == len(LEGACY_V1_MEDIA_BLOCKING_GATES),
            f"{path} dry run must either block pending media gates or explicitly resolve them",
        )

    qa = data.get("qa", {})
    for key in [
        "all_required_gates_present",
        "simulated_choices_labeled",
        "live_user_choices_required",
        "pending_gates_block_media",
        "no_creative_system_defaults",
    ]:
        require(qa.get(key) is True, f"{path} co-creation QA missing or false: {key}")
    receipt = data.get("skill_run_receipt", {})
    require(receipt.get("skill_id") == "co-creation-gate-runtime", f"{path} receipt must name co-creation-gate-runtime")


def shot_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(data.get("shots"), list):
        return data["shots"]
    shot_list = data.get("shot_list", {})
    if isinstance(shot_list, dict) and isinstance(shot_list.get("shots"), list):
        return shot_list["shots"]
    return []


def parse_seconds(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        match = re.fullmatch(r"(\d+)\s*s(?:ec(?:ond)?s?)?", text)
        if match:
            return int(match.group(1))
    return None


def parse_timecode_range(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})\s*", value)
    if not match:
        return None
    start_minutes, start_seconds, end_minutes, end_seconds = [int(part) for part in match.groups()]
    start = start_minutes * 60 + start_seconds
    end = end_minutes * 60 + end_seconds
    if end <= start:
        return None
    return start, end


def declared_shot_list_duration(data: dict[str, Any]) -> int | None:
    shot_list = data.get("shot_list", {})
    candidates: list[Any] = []
    if isinstance(shot_list, dict):
        candidates.extend([
            shot_list.get("total_duration"),
            shot_list.get("target_duration"),
            shot_list.get("duration_total_sec"),
            shot_list.get("target_duration_sec"),
        ])
    candidates.extend([
        data.get("total_duration"),
        data.get("target_duration"),
        data.get("duration_total_sec"),
        data.get("target_duration_sec"),
    ])
    for candidate in candidates:
        parsed = parse_seconds(candidate)
        if parsed is not None:
            return parsed
    return None


def validate_shot_list(path: str) -> None:
    data = load_yaml(require_path(path))
    shots = shot_items(data)
    require(shots, f"{path} has no shots")
    total_duration = 0
    expected_timecode_start = 0
    has_timecodes = any(shot.get("timecode") for shot in shots)
    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        required = ["duration", "shot_size", "camera_angle", "lens", "camera_motion", "subject_action", "blocking", "audio"]
        missing = [field for field in required if not shot.get(field)]
        purpose_present = shot.get("purpose") or shot.get("narrative_purpose")
        if not purpose_present:
            missing.append("purpose_or_narrative_purpose")
        require(not missing, f"{path} shot {shot_id} missing fields: {missing}")
        duration_sec = parse_seconds(shot.get("duration"))
        require(duration_sec is not None, f"{path} shot {shot_id} has invalid duration {shot.get('duration')}")
        total_duration += duration_sec
        if has_timecodes:
            timecode = parse_timecode_range(shot.get("timecode"))
            require(timecode is not None, f"{path} shot {shot_id} has invalid timecode {shot.get('timecode')}")
            start, end = timecode
            require(start == expected_timecode_start, f"{path} shot {shot_id} timecode starts at {start}s, expected {expected_timecode_start}s")
            require(end - start == duration_sec, f"{path} shot {shot_id} timecode duration {end - start}s does not match duration {duration_sec}s")
            expected_timecode_start = end
        if path in PROFESSIONAL_SHOT_LISTS:
            validate_professional_shot_card(path, shot)
    declared_duration = declared_shot_list_duration(data)
    if declared_duration is not None:
        require(total_duration == declared_duration, f"{path} shot durations {total_duration}s do not match declared duration {declared_duration}s")


def require_nonempty_dict_fields(path: str, shot_id: str, value: Any, fields: list[str], name: str) -> None:
    require(isinstance(value, dict), f"{path} shot {shot_id} {name} must be a structured mapping")
    missing = [field for field in fields if not value.get(field)]
    require(not missing, f"{path} shot {shot_id} {name} missing fields: {missing}")


def audio_has_content(audio: dict[str, Any]) -> bool:
    for key in ["dialogue", "voiceover", "ambience", "sfx", "foley"]:
        value = audio.get(key)
        if isinstance(value, list) and value:
            return True
    return bool(audio.get("music") or audio.get("silence"))


def validate_professional_shot_card(path: str, shot: dict[str, Any]) -> None:
    shot_id = shot.get("shot_id", "unknown")
    required = [
        "timecode",
        "duration",
        "story_beat",
        "narrative_purpose",
        "shot_type",
        "shot_size",
        "camera_angle",
        "lens",
        "lens_reason",
        "camera_support",
        "camera_motion",
        "focus",
        "composition",
        "subject_action",
        "transition_in",
        "transition_out",
    ]
    missing = [field for field in required if not shot.get(field)]
    require(not missing, f"{path} shot {shot_id} professional card missing fields: {missing}")
    require_nonempty_dict_fields(
        path,
        shot_id,
        shot.get("blocking"),
        ["start_position", "end_position", "path", "eyeline", "screen_direction", "axis_note"],
        "blocking",
    )
    require_nonempty_dict_fields(
        path,
        shot_id,
        shot.get("scene"),
        ["location", "foreground", "midground", "background", "lighting"],
        "scene",
    )
    require(isinstance(shot.get("continuity"), dict), f"{path} shot {shot_id} continuity must be structured")
    require(isinstance(shot.get("audio"), dict), f"{path} shot {shot_id} audio must be structured")
    require(audio_has_content(shot["audio"]), f"{path} shot {shot_id} audio has no usable cues")
    require_nonempty_dict_fields(
        path,
        shot_id,
        shot.get("model_notes"),
        ["seedance", "kling", "runway", "veo"],
        "model_notes",
    )


def validate_activation_policy() -> None:
    proc = run(["python3", "scripts/dircreative_activation_policy_audit.py"])
    require(proc.returncode == 0, f"activation policy audit failed:\n{proc.stderr}\n{proc.stdout}")
    require(
        "DIRCREATIVE_ACTIVATION_POLICY_AUDIT: PASS" in proc.stdout,
        "activation policy audit missing PASS marker",
    )


def validate_context_budget() -> None:
    proc = run(["python3", "scripts/dircreative_context_budget_audit.py"])
    require(proc.returncode == 0, f"context budget audit failed:\n{proc.stderr}\n{proc.stdout}")
    require(
        "DIRCREATIVE_CONTEXT_BUDGET_AUDIT: PASS" in proc.stdout,
        "context budget audit missing PASS marker",
    )


def validate_skill_stack() -> None:
    proc = run(["python3", "scripts/dircreative_skill_stack.py", "self-test"])
    require(proc.returncode == 0, f"Skill Stack audit failed:\n{proc.stderr}\n{proc.stdout}")
    for marker in [
        "DIRCREATIVE_SKILL_STACK_AUDIT: PASS",
        '"positive_cases": 55',
        '"negative_cases": 39',
        '"scenario_count": 43',
        '"provider_policy_count": 52',
        '"realistic_smoke_cases": 26',
        '"two_phase_host_binding": true',
        '"trusted_primary_route_controls": true',
        '"artifact_output_guard_controls": true',
        '"future_capability_provider_control": true',
        '"deterministic_candidate_pool": true',
        '"explicit_overlay_order_preserved": true',
        '"installed_layout_resolution": true',
        '"runtime_path_containment_controls": true',
        '"unverified_cost_adapter_blocked": true',
        '"delivery_single_body_reservation": true',
        '"isolated_execution_adapter_budget_bytes": 24576',
        '"isolated_craft_context_budget_bytes": 131072',
        '"isolated_validator_context_budget_bytes": 65536',
        '"host_managed_imagegen_path": true',
    ]:
        require(marker in proc.stdout, f"Skill Stack audit missing marker: {marker}")


def validate_visual_asset_plan() -> None:
    proc = run(["python3", "scripts/dircreative_visual_asset_plan.py", "--self-test"])
    require(
        proc.returncode == 0,
        f"whole-film visual asset plan audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "DIRCREATIVE_VISUAL_ASSET_PLAN_AUDIT: PASS",
        '"duration_at_least_60": true',
        '"landscape_broadcast_profile": true',
        '"formal_shots_at_least_24": true',
        '"rhythm_points_at_least_30": true',
        '"generation_units_scene_coherent": true',
        '"assets": 50',
        '"storyboard_frames": 24',
        '"director_storyboard_pages": 4',
        '"self_attested_visual_completion_rejected_control": true',
        '"payload_reviewer_labels_cannot_grant_completion_control": true',
        '"fake_raster_negative_control": true',
        '"reused_file_negative_control": true',
        '"pixel_duplicate_metadata_negative_control": true',
        '"shot_truth_negative_control": true',
        '"storyboard_purpose_negative_control": true',
        '"director_dependency_negative_control": true',
        '"clean_dependency_negative_control": true',
        '"accepted_claim_negative_control": true',
        '"json_schema_negative_control": true',
        '"technical_receipt_binding_negative_control": true',
        '"visual_qa_receipt_binding_negative_control": true',
        '"visual_review_manifest_binding_negative_control": true',
        '"user_locked_requires_review_negative_control": true',
        '"decoder_portability_control": true',
        '"visual_frame_aspect_negative_control": true',
        '"non_png_evidence_negative_control": true',
        '"manifest_snapshot_binding_control": true',
        '"receipt_timestamp_negative_control": true',
        '"technical_stamp_cannot_complete_negative_control": true',
        '"evidence_root_negative_control": true',
        '"inventory_staleness_negative_control": true',
        '"creative_source_staleness_negative_control": true',
        '"shot_cards_staleness_negative_control": true',
        '"multiple_direct_inputs_positive_control": true',
        '"multiple_direct_inputs_dependency_negative_control": true',
        '"stdlib_png_decode_control": true',
        '"stdlib_png_trns_negative_control": true',
        '"stdlib_schema_fallback_control": true',
        '"timecode_overlap_negative_control": true',
        '"frame_alignment_negative_control": true',
        '"sample_plan_positive_control": true',
        '"clean_input_membership_negative_control": true',
        '"scene_shot_coverage_negative_control": true',
        '"duplicate_unit_membership_negative_control": true',
        '"cross_scene_plan_negative_control": true',
        '"duplicate_direct_input_negative_control": true',
        '"storyboard_scene_negative_control": true',
        '"duplicate_identity_negative_control": true',
    ]:
        require(marker in proc.stdout, f"visual asset plan audit missing evidence: {marker}")


def validate_asset_foundation_pass() -> None:
    proc = run(["python3", "scripts/dircreative_asset_foundation_pass.py", "self-test"])
    require(
        proc.returncode == 0,
        f"asset foundation pass audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "DIRCREATIVE_ASSET_FOUNDATION_PASS_AUDIT: PASS",
        '"valid_fixture_passed": true',
        '"stage_count": 6',
        '"negative_case_count": 13',
        '"negative_cases_rejected": 13',
        '"compile_gate_status": "allowed"',
    ]:
        require(marker in proc.stdout, f"asset foundation pass audit missing marker: {marker}")


def validate_ai_film_asset_stress_test() -> None:
    proc = run(["python3", "scripts/ai_film_asset_stress_test.py", "self-test"])
    require(
        proc.returncode == 0,
        f"AI-film asset stress-test audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "AI_FILM_ASSET_STRESS_TEST_AUDIT: PASS",
        '"valid_fixture_passed": true',
        '"valid_v1_fixture_passed": true',
        '"matrix_case_count": 11',
        '"negative_case_count": 33',
        '"negative_cases_rejected": 33',
        '"media_generation_performed": false',
    ]:
        require(marker in proc.stdout, f"asset stress-test audit missing marker: {marker}")


def validate_ai_film_production_ledger() -> None:
    proc = run(["python3", "scripts/ai_film_production_ledger.py", "self-test"])
    require(
        proc.returncode == 0,
        f"AI-film production ledger audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "AI_FILM_PRODUCTION_LEDGER_AUDIT: PASS",
        '"valid_fixture_passed": true',
        '"attempt_count": 2',
        '"negative_case_count": 23',
        '"negative_cases_rejected": 23',
        '"previous_or_initial_required": true',
        '"unconfigured_authority_rejected": true',
        '"authority_escalation_rejected": true',
        '"actor_spoof_rejected": true',
        '"secret_receipt_rejected": true',
        '"verified_lineage_positive": true',
        '"verified_cost_positive": true',
        '"append_only_positive": true',
        '"append_only_parent_protection": true',
        '"initial_reset_rejected": true',
        '"media_generation_performed": false',
    ]:
        require(marker in proc.stdout, f"production ledger audit missing marker: {marker}")


def validate_script_to_seedance_handoff() -> None:
    proc = run(["python3", "scripts/dircreative_script_to_seedance_handoff.py", "self-test"])
    require(
        proc.returncode == 0,
        f"script-to-Seedance handoff audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "DIRCREATIVE_SCRIPT_TO_SEEDANCE_HANDOFF_AUDIT: PASS",
        '"valid_fixture_passed": true',
        '"negative_case_count": 42',
        '"negative_cases_rejected": 42',
        '"generation_unit_count": 2',
        '"asset_foundation_gate_validated": true',
    ]:
        require(marker in proc.stdout, f"script-to-Seedance handoff audit missing marker: {marker}")


def validate_storyboard_frame_handoff() -> None:
    proc = run(["python3", "scripts/dircreative_storyboard_frame_handoff.py", "self-test"])
    require(
        proc.returncode == 0,
        f"storyboard-frame handoff audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "DIRCREATIVE_STORYBOARD_FRAME_HANDOFF_AUDIT: PASS",
        '"valid_fixture_passed": true',
        '"frame_count": 2',
        '"reference_read_count": 6',
        '"negative_case_count": 15',
        '"negative_cases_rejected": 15',
        '"delivery_provenance_bound": true',
        '"generation_claim_allowed": false',
        '"planned_prompt_manifest_controls": true',
        '"production_observation_fixture_passed": true',
    ]:
        require(marker in proc.stdout, f"storyboard-frame handoff audit missing marker: {marker}")


def validate_workspace_hygiene_runtime() -> None:
    proc = run(["python3", "scripts/dircreative_workspace.py", "self-test"])
    require(
        proc.returncode == 0,
        f"workspace hygiene runtime failed:\n{proc.stderr}\n{proc.stdout}",
    )
    require(
        "DIRCREATIVE_WORKSPACE_SELF_TEST: PASS" in proc.stdout,
        "workspace hygiene runtime missing PASS marker",
    )


def validate_headless_acceptance() -> None:
    proc = run(["python3", "scripts/dircreative_headless_acceptance_audit.py"])
    require(
        proc.returncode == 0,
        f"headless input-to-answer acceptance failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "HEADLESS_ACCEPTANCE_AUDIT: PASS",
        '"answer_files_generated": 3',
        '"empty_answer_rejected": true',
        '"route_only_answer_rejected": true',
        '"v1_read_compatibility": true',
        '"v1_free_text_readiness_claims_rejected": true',
        '"v1_non_list_qa_fields_rejected": true',
        '"v1_compound_readiness_assertions_in_questions_rejected": true',
        '"v1_actual_readiness_questions_allowed": true',
        '"v2_compact_receipt_valid": true',
        '"formal_shots": 24',
        '"frame_aligned_shots": 24',
        '"visual_assets_planned": 50',
        '"tvc_landscape_profile": true',
        '"fractional_frame_rejected": true',
        '"timecode_gap_rejected": true',
        '"deliverable_layer": "client_story"',
        '"shot_matrix_allowed": false',
        '"v2_all_reserved_readiness_claims_rejected": true',
        '"v2_nested_reserved_readiness_claims_rejected": true',
        '"v2_natural_language_readiness_claims_rejected": true',
        '"v2_positive_readiness_claims_in_limitations_rejected": true',
        '"v2_negative_readiness_limitations_allowed": true',
        '"v2_declarative_readiness_claims_in_questions_rejected": true',
        '"v2_actual_readiness_questions_allowed": true',
        '"v2_unknown_and_chinese_domain_checks_rejected": true',
    ]:
        require(marker in proc.stdout, f"headless acceptance missing evidence: {marker}")


def validate_delivery_boundaries() -> None:
    proc = run(["python3", "scripts/dircreative_delivery_boundary_audit.py"])
    require(
        proc.returncode == 0,
        f"delivery boundary audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    for marker in [
        "DIRCREATIVE_DELIVERY_BOUNDARY_AUDIT: PASS",
        '"match_cut_missing_first_frame_unverified": true',
        '"match_cut_rejects_fake_image_and_self_attestation": true',
        '"match_cut_rejects_truncated_png": true',
        '"match_cut_rejects_wrong_png_scanlines": true',
        '"match_cut_rejects_noncanonical_indexed_png": true',
        '"match_cut_requires_trusted_visual_readback": true',
        '"match_cut_rejects_dotdot_evidence_escape": true',
        '"match_cut_rejects_intermediate_symlink_escape": true',
        '"match_cut_rejects_moved_intermediate_directory": true',
        '"match_cut_computes_endpoint_comparability": true',
        '"claim_evidence_ref_must_resolve": true',
        '"local_evidence_cannot_authorize_sensitive_claim": true',
        '"all_sensitive_creative_claims_rejected": true',
        '"frame_content_columns_separated": true',
        '"camera_action_cannot_replace_storyline": true',
        '"studio_foundation_blocks_matrix_when_incomplete": true',
        '"runtime_agents_nonwrite": true',
    ]:
        require(marker in proc.stdout, f"delivery boundary audit missing evidence: {marker}")


def validate_content_first_behavior() -> None:
    content = run(["python3", "scripts/dircreative_content_first_audit.py"])
    require(
        content.returncode == 0,
        f"content-first answer audit failed:\n{content.stderr}\n{content.stdout}",
    )
    for marker in [
        "DIRCREATIVE_CONTENT_FIRST_AUDIT: PASS",
        '"negative_control_rejected": true',
        '"process_narration_ratio": 0.0',
    ]:
        require(marker in content.stdout, f"content-first audit missing evidence: {marker}")

    live_harness = run(["python3", "scripts/dircreative_live_model_eval.py", "--self-test"])
    require(
        live_harness.returncode == 0,
        f"live model eval harness self-test failed:\n{live_harness.stderr}\n{live_harness.stdout}",
    )
    require(
        "DIRCREATIVE_LIVE_MODEL_EVAL_SELF_TEST: PASS" in live_harness.stdout,
        "live model eval harness missing PASS marker",
    )


def validate_v2_interaction_contract() -> None:
    policy = load_yaml(require_path("skills/dircreative/runtime/routing-policy.yaml"))
    interaction = policy.get("interaction_contract", {})
    require(interaction.get("external_user_gates") == V2_EXTERNAL_USER_GATES, "v2 external gate set drifted")
    require(
        interaction.get("reversible_internal_states") == V2_REVERSIBLE_INTERNAL_STATES,
        "v2 reversible internal state set drifted",
    )
    require(interaction.get("first_response_contract") == "useful_artifact_first", "v2 is not result-first")
    require(interaction.get("known_brief_policy") == "reuse_without_reasking", "v2 re-asks known briefs")
    require(interaction.get("obvious_route_without_router_tool") is True, "obvious routes require a router tool")
    require(
        interaction.get("scoped_validation_policy") == "current_task_and_direct_dependencies_only",
        "scoped validation boundary drifted",
    )
    require(
        interaction.get("unrelated_global_debt_blocks_scoped_work") is False,
        "unrelated global debt can block scoped work",
    )
    require(interaction.get("state_persistence") == {
        "fast": "memory_only",
        "studio": "pause_cross_session_or_multi_file_only",
        "delivery": "required",
    }, "v2 compact-state persistence policy drifted")
    require(policy.get("external_user_gates") == V2_EXTERNAL_USER_GATES, "routing gate allowlist drifted")

    phase = load_yaml(require_path("docs/film-preproduction/phase-contracts.yaml")).get("runtime_contract_v2", {})
    require(phase.get("status") == "active_for_new_runs", "phase contract does not activate v2 runtime")
    require(phase.get("external_gate_count") == 3, "phase contract external gate count drifted")
    require(phase.get("legacy_v1_write_allowed") is False, "phase contract allows new v1 writes")
    require(phase.get("full_state_audit_triggers") == [
        "resume",
        "handoff",
        "delivery",
        "completion_claim",
    ], "full state audit trigger set drifted")
    for key, expected in {
        "continue_without_real_blocker": True,
        "bounded_revision_restarts_idea_intake": False,
        "known_brief_is_reasked": False,
        "direct_artifact_first_response": True,
        "full_state_audit_per_reply": False,
    }.items():
        require(phase.get("behavior", {}).get(key) is expected, f"v2 behavior drifted: {key}")

    snapshot = load_json(require_path("skills/dircreative/runtime/state-snapshot.schema.json"))
    require(set(snapshot.get("required", [])) == {
        "project_id",
        "mode",
        "current_route",
        "locked_facts",
        "working_assumptions",
        "active_outputs",
        "stale_outputs",
        "open_questions",
        "generation_authorized",
        "client_delivery_approved",
    }, "compact state snapshot fields drifted")

    legacy_schema = load_yaml(require_path("docs/film-preproduction/schemas/co-creation-run.yaml"))
    compatibility = legacy_schema.get("compatibility", {})
    require(compatibility.get("status") == "legacy_read_only", "v1 co-creation schema is not read-only")
    require(compatibility.get("new_runs_allowed") is False, "v1 co-creation schema allows new runs")

    active_docs = [
        "docs/film-preproduction/chat-co-creation-interface.md",
        "docs/film-preproduction/live-chat-start-protocol.md",
        "docs/film-preproduction/chat-stage-gate-integrity.md",
        "skills/dircreative/chat-facilitator/SKILL.md",
    ]
    combined = "\n".join(require_path(path).read_text(encoding="utf-8") for path in active_docs)
    for term in [
        "useful artifact",
        "reuse",
        "concept_lock",
        "generation_authorization",
        "client_delivery_approval",
        "story_state",
        "qa_state",
        "继续",
        "优化这个镜头",
        "修改第三句",
        "read-only",
    ]:
        require(term.casefold() in combined.casefold(), f"v2 chat contract missing {term}")
    for path in active_docs[:3]:
        text = require_path(path).read_text(encoding="utf-8")
        active_text = text.split("## Legacy", 1)[0]
        leaked = [gate for gate in LEGACY_V1_CO_CREATION_GATE_TYPES if gate in active_text]
        require(not leaked, f"{path} activates legacy gates: {leaked}")

    route_test = run(["python3", "scripts/dircreative_route.py", "--self-test"])
    require(route_test.returncode == 0, f"v2 route behavior self-test failed:\n{route_test.stderr}\n{route_test.stdout}")
    cases = {case["id"]: case for case in load_json(require_path("tests/fixtures/routing/cases.json"))["cases"]}
    for case_id in [
        "continue",
        "third_line",
        "single_shot",
        "complete_ad",
        "concept_conflict",
        "real_generation",
        "explicit_generation_authorization",
        "client_delivery",
        "explicit_client_delivery_approval",
    ]:
        require(case_id in cases, f"missing v2 interaction case: {case_id}")
    for case_id in ["continue", "third_line", "single_shot", "complete_ad"]:
        require(cases[case_id]["action"] == "continue", f"{case_id} must continue without a gate")
        require(cases[case_id]["first_response_contract"] == "useful_artifact_first", f"{case_id} is not result-first")
    require(cases["concept_conflict"]["external_user_gate"] == "concept_lock", "concept conflict gate mismatch")
    require(cases["real_generation"]["external_user_gate"] == "generation_authorization", "generation gate mismatch")
    require(
        cases["explicit_generation_authorization"]["action"] == "continue"
        and cases["explicit_generation_authorization"]["external_user_gate"] is None,
        "explicit generation authorization is asked twice",
    )
    require(cases["client_delivery"]["external_user_gate"] == "client_delivery_approval", "delivery gate mismatch")
    require(
        cases["explicit_client_delivery_approval"]["action"] == "continue"
        and cases["explicit_client_delivery_approval"]["external_user_gate"] is None,
        "explicit client delivery approval is asked twice",
    )


def validate_skills() -> None:
    root_skill = require_path("skills/dircreative/SKILL.md")
    root_text = root_skill.read_text(encoding="utf-8")
    require(len(root_text.splitlines()) <= 220, "root skill exceeds 220-line router budget")
    require(len(root_text.encode("utf-8")) <= 16 * 1024, "root skill exceeds 16 KiB router budget")
    for heading in [
        "## Invocation Boundary",
        "## Router Contract",
        "## Startup Reads",
        "## Execution Context",
        "## Modes",
        "## External User Gates",
        "## Compact State",
        "## Sub-Capability Dispatch",
        "## Result Contract",
    ]:
        require(heading in root_text, f"root router missing {heading}")
    for term in [
        "$dircreative",
        "dircreative_route.py",
        "Read exactly one selected Route Card",
        "source_maintenance",
        "Fast",
        "Studio",
        "Delivery",
        "concept_lock",
        "generation_authorization",
        "client_delivery_approval",
        "zero unconditional protocol reads",
        "at most three dynamic professional perspectives",
    ]:
        require(term in root_text, f"root router missing v2 contract term: {term}")
    for path in internal_skill_paths():
        text = path.read_text(encoding="utf-8")
        for heading in ["## Required Knowledge", "## Inputs", "## Outputs", "## Rules", "## skill_run_receipt"]:
            require(heading in text, f"{rel(path)} missing {heading}")
        require("docs/film-preproduction/" in text, f"{rel(path)} does not cite docs/film-preproduction knowledge")
    for skill_id, required_terms in {
        "ai-film-asset-stress-test": [
            "validation_only",
            "ai-film-asset-stress-test.schema.json",
            "ai_film_asset_stress_test.py",
            "unverified",
        ],
        "ai-film-production-ledger": [
            "record_only",
            "ai-film-production-ledger.schema.json",
            "ai_film_production_ledger.py",
            "append-only",
        ],
    }.items():
        skill_path = require_path(f"skills/{skill_id}/SKILL.md")
        text = skill_path.read_text(encoding="utf-8")
        expected_entry_name = (
            "INTERNAL_SKILL.md" if INSTALLED_PACKAGE_VALIDATION else "SKILL.md"
        )
        require(
            skill_path.name == expected_entry_name,
            f"{skill_id} entrypoint layout does not match validation mode",
        )
        if INSTALLED_PACKAGE_VALIDATION:
            require(
                not text.startswith("---\n"),
                f"{skill_id} installed internal entry still exposes YAML frontmatter",
            )
        else:
            require(text.startswith("---\n"), f"{skill_id} missing YAML frontmatter")
            frontmatter = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
            require(frontmatter is not None, f"{skill_id} has invalid YAML frontmatter")
            header = frontmatter.group(1) if frontmatter else ""
            require(f"name: {skill_id}" in header, f"{skill_id} frontmatter name mismatch")
            require("description:" in header, f"{skill_id} missing description")
        require(len(skill_id) <= 64, f"{skill_id} exceeds Skill name limit")
        unfinished_marker = "[" + "TO" + "DO:"
        require(unfinished_marker not in text, f"{skill_id} contains an unfinished placeholder")
        require(len(text.splitlines()) <= 120, f"{skill_id} entrypoint is not narrow")
        for term in required_terms:
            require(term in text, f"{skill_id} missing contract term: {term}")
        openai_text = require_path(f"skills/{skill_id}/agents/openai.yaml").read_text(
            encoding="utf-8"
        )
        require(
            f"${skill_id}" in openai_text,
            f"{skill_id} default prompt does not name the Skill",
        )
    with tempfile.TemporaryDirectory(prefix="dircreative-skill-layout-") as tmp:
        probe_root = Path(tmp)
        probe_dir = probe_root / "skills/probe-skill"
        probe_dir.mkdir(parents=True)
        internal = probe_dir / "INTERNAL_SKILL.md"
        internal.write_text("# internal\n", encoding="utf-8")
        source_candidate = required_path_candidate(
            probe_root,
            "skills/probe-skill/SKILL.md",
            installed_mode=False,
        )
        require(
            source_candidate.name == "SKILL.md" and not source_candidate.exists(),
            "source validation accepted an INTERNAL_SKILL.md alias",
        )
        internal.unlink()
        public = probe_dir / "SKILL.md"
        public.write_text("---\nname: probe-skill\n---\n", encoding="utf-8")
        installed_candidate = required_path_candidate(
            probe_root,
            "skills/probe-skill/SKILL.md",
            installed_mode=True,
        )
        require(
            installed_candidate.name == "INTERNAL_SKILL.md"
            and not installed_candidate.exists(),
            "installed validation accepted a public SKILL.md alias",
        )
    for skill_path in CHAT_SURFACE_SKILLS:
        text = require_path(skill_path).read_text(encoding="utf-8")
        require("## Chat Surface" in text, f"{skill_path} missing Chat Surface")
        if skill_path == "skills/dircreative/director-room/SKILL.md":
            for term in [
                "Fast tasks do not enter Director Room",
                "recommendation appear before any process note",
                "no_material_conflict",
                "Do not expose ten role cards",
            ]:
                require(term in text, f"{skill_path} missing adaptive chat term: {term}")
            continue
        require("docs/film-preproduction/chat-co-creation-interface.md" in text, f"{skill_path} missing chat interface knowledge")
        if skill_path == "skills/dircreative/chat-facilitator/SKILL.md":
            require("docs/film-preproduction/chat-stage-gate-integrity.md" in text, "chat facilitator missing stage gate integrity knowledge")
            for term in [
                "useful artifact or revision first",
                "concept_lock",
                "generation_authorization",
                "client_delivery_approval",
                "reversible internal state",
                "继续",
                "修改第三句",
            ]:
                require(term in text, f"chat facilitator missing v2 behavior: {term}")
        for term in ["阶段:", "智能体创作内容", "用户确认点"]:
            require(term in text, f"{skill_path} missing chat surface term: {term}")

    prompt_compiler = require_path("skills/dircreative/image-prompt-compiler/SKILL.md").read_text(encoding="utf-8")
    video_adapter = require_path("skills/dircreative/video-model-adapter/SKILL.md").read_text(encoding="utf-8")
    for skill_name, text in [
        ("image prompt compiler", prompt_compiler),
        ("video model adapter", video_adapter),
    ]:
        for term in [
            "production-prompt-discipline.md",
            "pre-delivery harness",
            "model constraints",
            "prompt-window hygiene",
            "falsifiable success criteria",
            "one variable at a time",
        ]:
            require(term in text, f"{skill_name} missing production prompt discipline term: {term}")


def validate_adco_native_integration_contract() -> None:
    root_path = ROOT / "skills/dircreative/SKILL.md"
    if not root_path.exists():
        root_path = ROOT / "SKILL.md"
    require(root_path.exists(), "missing root DIRcreative skill entry")
    root_text = root_path.read_text(encoding="utf-8")
    doc_text = require_path("docs/film-preproduction/adco-integration-contract.md").read_text(encoding="utf-8")
    architecture_text = require_path("docs/film-preproduction/05-skill-integration-architecture.md").read_text(
        encoding="utf-8"
    )
    thread_text = require_path("docs/film-preproduction/thread-orchestration-protocol.md").read_text(encoding="utf-8")
    readme_text = require_path("README.md").read_text(encoding="utf-8")
    release_text = require_path("scripts/dircreative_release_gate.py").read_text(encoding="utf-8")

    per_surface_terms = {
        "root skill": (
            root_text,
            [
                "standalone_chat",
                "orchestrated_worker",
                "adco.specialist-exchange",
                "dircreative.film-preproduction",
                "ADCO owns host",
                "DIR returns only requested film artifacts, domain QA, status, and open questions",
                "Nested dispatch is forbidden",
            ],
        ),
        "ADCO integration doc": (
            doc_text,
            [
                "Active Compact Transport (v2)",
                "adco.specialist-exchange",
                "provider descriptor",
                "v1 Read Compatibility",
                "domain artifacts and domain QA",
                "ADCO owns adoption",
                "claims.client_ready: false",
                "claims.control_plane_updated: false",
                "host-baseline",
                "dircreative.domain-delivery@1.0",
                "cross-repository temp-project roundtrip",
            ],
        ),
        "integration architecture": (
            architecture_text,
            [
                "External Orchestrator Adapter",
                "adco.specialist-exchange",
                "provider descriptor",
                "V2 receipts contain only status",
            ],
        ),
        "thread protocol": (
            thread_text,
            [
                "Status: legacy v1 evidence reader",
                "Fast uses zero Threads",
                "Studio uses one controller and zero Threads by default",
                "adco.specialist-exchange@2.0",
                "rejects nested dispatch",
            ],
        ),
        "README": (
            readme_text,
            [
                "## ADCO Integration",
                "adco.specialist-exchange",
                "contract_version: \"2.0\"",
                "v1 handoff/receipt/adoption",
                "dircreative_adco_native_exchange.py --self-test",
            ],
        ),
        "release gate": (
            release_text,
            [
                "ADCO native exchange audit",
                "ADCO native bilateral audit",
                "dircreative_adco_native_exchange.py",
                "--adco-repo",
                "RELEASE_GATE_SCOPE: DIR_ONLY",
            ],
        ),
    }
    for label, (text, terms) in per_surface_terms.items():
        missing = [term for term in terms if term not in text]
        require(not missing, f"{label} missing ADCO native integration terms: {missing}")

    descriptor = load_json(require_path("docs/film-preproduction/schemas/adco-specialist-descriptor.json"))
    require(descriptor.get("protocol_id") == "adco.specialist-exchange", "ADCO descriptor protocol mismatch")
    require(descriptor.get("message_type") == "descriptor", "ADCO descriptor message type mismatch")
    require(descriptor.get("descriptor_version") == "1.0", "ADCO descriptor version mismatch")
    require(
        descriptor.get("supported_contract_versions") == ["1.0", "2.0"],
        "ADCO descriptor must declare ordered v1/v2 support",
    )
    provider = descriptor.get("provider", {})
    require(provider.get("id") == "dircreative", "ADCO descriptor provider mismatch")
    require(provider.get("skill_sha256") == hashlib.sha256(root_path.read_bytes()).hexdigest(), "ADCO descriptor skill hash is stale")
    profiles = descriptor.get("profiles", [])
    profile = next(
        (item for item in profiles if item.get("profile_id") == "dircreative.film-preproduction"),
        None,
    )
    require(profile is not None, "ADCO descriptor missing DIRcreative profile")
    require("film.story_package" in profile.get("capabilities", []), "DIRcreative profile lacks story package capability")
    require(
        {"inline", "codex_thread", "external_handoff"}.issubset(set(profile.get("execution_modes", []))),
        "DIRcreative profile execution modes drifted",
    )
    require(
        {"isolated_workspace", "worktree", "read_only"}.issubset(set(profile.get("workspace_modes", []))),
        "DIRcreative profile workspace modes drifted",
    )
    authority = profile.get("authority", {})
    for field in ["client_interaction", "artifact_adoption", "client_readiness", "final_export", "nested_dispatch"]:
        require(authority.get(field) is False, f"DIRcreative descriptor authority escalation: {field}")
    require(
        profile.get("receipt_extension")
        == {"id": "dircreative.domain-delivery", "version": "1.0", "required": True},
        "DIRcreative descriptor receipt extension drifted",
    )
    require(
        profile.get("v2_contract")
        == {
            "execution_mode": "inline",
            "nested_dispatch": False,
            "receipt_shape": "domain_outputs_and_qa_only",
            "handoff_schema": "docs/film-preproduction/schemas/adco-specialist-handoff-v2.schema.json",
            "receipt_schema": "docs/film-preproduction/schemas/adco-specialist-receipt-v2.schema.json",
        },
        "DIRcreative descriptor v2 contract drifted",
    )

    handoff_schema = load_json(
        require_path("docs/film-preproduction/schemas/adco-specialist-handoff-v2.schema.json")
    )
    receipt_schema = load_json(
        require_path("docs/film-preproduction/schemas/adco-specialist-receipt-v2.schema.json")
    )
    require(handoff_schema.get("additionalProperties") is False, "v2 handoff schema must stay compact")
    require(
        handoff_schema.get("properties", {}).get("contract_version", {}).get("const") == "2.0",
        "v2 handoff schema version drifted",
    )
    require(
        handoff_schema.get("properties", {}).get("execution_mode", {}).get("const") == "inline",
        "v2 handoff must remain inline",
    )
    require(receipt_schema.get("additionalProperties") is False, "v2 receipt schema must stay compact")
    require(
        receipt_schema.get("properties", {}).get("contract_version", {}).get("const") == "2.0",
        "v2 receipt schema version drifted",
    )
    require(
        set(receipt_schema.get("properties", {}))
        == {"protocol_id", "contract_version", "status", "outputs", "domain_qa", "open_questions"},
        "v2 receipt schema contains control-plane fields",
    )

    orchestration = load_yaml(require_path("docs/film-preproduction/schemas/skill-orchestration.yaml"))
    external = orchestration.get("external_orchestrators", {}).get("adco", {})
    require(external.get("protocol_id") == "adco.specialist-exchange", "skill orchestration protocol drift")
    require(external.get("profile_id") == "dircreative.film-preproduction", "skill orchestration profile drift")
    require(external.get("failure_policy") == "fail_closed", "ADCO adapter must fail closed")
    require(external.get("supported_contract_versions") == ["1.0", "2.0"], "skill orchestration lacks v2")
    require(
        external.get("v2_transport")
        == {
            "execution_mode": "inline",
            "nested_dispatch": False,
            "response_scope": "domain_outputs_and_qa_only",
            "handoff_schema": "docs/film-preproduction/schemas/adco-specialist-handoff-v2.schema.json",
            "receipt_schema": "docs/film-preproduction/schemas/adco-specialist-receipt-v2.schema.json",
        },
        "skill orchestration v2 transport drifted",
    )
    declared_subskills = {item.get("skill_id") for item in orchestration.get("subskills", [])}
    actual_subskills = {path.parent.name for path in internal_skill_paths()}
    require(declared_subskills == actual_subskills, f"subskill registry drift: declared={sorted(declared_subskills)} actual={sorted(actual_subskills)}")

    proc = run(["python3", "scripts/dircreative_adco_native_exchange.py", "--self-test"])
    require(proc.returncode == 0, f"ADCO native exchange self-test failed:\n{proc.stdout}\n{proc.stderr}")
    require("ADCO_NATIVE" in proc.stdout and "PASS" in proc.stdout, "ADCO native self-test lacks PASS marker")


def run_project_agents(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return run(["python3", "scripts/dircreative_project_agents.py", *args])


def validate_project_agents_script() -> None:
    script = require_path("scripts/dircreative_project_agents.py")
    text = script.read_text(encoding="utf-8")
    required_terms = [
        "AGENTS.dircreative.proposed.md",
        "BEGIN_MARKER",
        "END_MARKER",
        "mode:propose-agents-md",
        "mode:create-agents-md",
        "mode:append-dircreative-section",
        "mode:replace-dircreative-section",
        "audit:missing-active-agents",
        "audit:missing-required-dircreative-terms",
        "audit:docs-mention-generation-without-implementation",
        "audit:informational-by-default",
        "auth:authorization-required-for-active-agents-write",
        "--authorization-text",
        "--authorization-receipt",
        "--require-active",
        "test:detect-accidental-agents-overwrite",
        "target_project_needs_agents_missing_active_rules",
        "active_agents_missing_required_dircreative_terms",
        "docs_mention_agents_generation_but_implementation_missing",
        "active_agents_write_requires_host_controller_scoped_patch_only",
        "agents_hierarchy_conflict",
        "caller_forged_authorization_must_be_rejected",
        "idea intake -> director room -> story -> script -> script breakdown -> shot design -> visual bible -> reference pack -> image prompt -> video model adapter -> QA/retry",
        "Source of truth",
        "worker thread output is advisory",
        "中文优先、简洁、先给结论",
        "THREAD_DISPATCH_RECEIPT",
        "target project-bound worker",
        "cos_main_overexecution",
        "rejected_evidence",
        "live-user-acceptance.yaml",
        "Validation commands",
        "film-craft provider only",
        "AD-creative/AGENTS.md",
        "target_project_must_exist",
        "agents_hierarchy_changed_before_proposal",
        "agents_hierarchy_changed_during_proposal",
    ]
    missing = [term for term in required_terms if term not in text]
    require(not missing, f"project AGENTS script missing terms: {missing}")

    repo_audit = run_project_agents("audit-repo")
    require(repo_audit.returncode == 0, f"project AGENTS repo audit failed:\n{repo_audit.stderr}\n{repo_audit.stdout}")
    require("PROJECT_AGENTS_AUDIT: PASS" in repo_audit.stdout, "project AGENTS repo audit must pass")

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "target-project"
        target.mkdir()
        (target / ".dircreative" / "runs").mkdir(parents=True)
        child_agents = target / "AD-creative" / "AGENTS.md"
        child_agents.parent.mkdir()
        child_agents.write_text("# ADCO child rules\n\nkeep child precedence\n", encoding="utf-8")
        child_agents_hash = hashlib.sha256(child_agents.read_bytes()).hexdigest()

        informational_audit = run_project_agents("audit", str(target))
        require(informational_audit.returncode == 0, "default project AGENTS audit must be informational when AGENTS.md is absent")
        require(
            "active_agents: absent" in informational_audit.stdout,
            "default project AGENTS audit must report absent AGENTS.md without failing",
        )

        missing_active = run_project_agents("audit", str(target), "--require-active")
        require(missing_active.returncode != 0, "project AGENTS audit --require-active must fail when DIRcreative project lacks active AGENTS.md")
        require(
            "target_project_needs_agents_missing_active_rules" in missing_active.stdout,
            "project AGENTS audit must name missing active rules",
        )

        agents_path = target / "AGENTS.md"
        sentinel = "# Existing Project Rules\n\nkeep this sentinel\n"
        agents_path.write_text(sentinel, encoding="utf-8")
        sentinel_hash = hashlib.sha256(agents_path.read_bytes()).hexdigest()
        child_hash_before = hashlib.sha256(child_agents.read_bytes()).hexdigest()
        forged = json.dumps(
            {
                "explicit_user_authorization": True,
                "source": "current_user_request",
                "target_project": str(target.resolve()),
                "operation": "append-section",
            }
        )
        receipt_path = target / "forged-authorization.json"
        receipt_path.write_text(forged, encoding="utf-8")
        for mode in ("create", "append-section", "replace-section"):
            for flag, value in (
                ("--authorization-text", forged),
                ("--authorization-receipt", str(receipt_path)),
            ):
                active = run_project_agents(
                    "generate", str(target), "--mode", mode, flag, value
                )
                require(active.returncode != 0, f"caller-controlled authorization activated {mode}")
                require(
                    "active_agents_write_requires_host_controller_scoped_patch_only"
                    in active.stdout,
                    f"active mode {mode} failed for the wrong reason",
                )
                require(
                    hashlib.sha256(agents_path.read_bytes()).hexdigest() == sentinel_hash,
                    f"active mode {mode} changed root AGENTS.md",
                )
                require(
                    hashlib.sha256(child_agents.read_bytes()).hexdigest() == child_hash_before,
                    f"active mode {mode} changed child AGENTS.md",
                )
        default_propose = run_project_agents("generate", str(target))
        require(default_propose.returncode == 0, f"default proposal write failed:\n{default_propose.stderr}\n{default_propose.stdout}")
        require(
            hashlib.sha256(agents_path.read_bytes()).hexdigest() == sentinel_hash,
            "default proposal mode accidentally overwrote AGENTS.md",
        )
        propose = run_project_agents("generate", str(target), "--mode", "propose")
        require(propose.returncode == 0, f"proposal write failed:\n{propose.stderr}\n{propose.stdout}")
        require(agents_path.read_text(encoding="utf-8") == sentinel, "proposal mode accidentally overwrote AGENTS.md")
        require(hashlib.sha256(agents_path.read_bytes()).hexdigest() == sentinel_hash, "proposal mode changed existing AGENTS.md hash")
        proposed_path = target / "AGENTS.dircreative.proposed.md"
        require(proposed_path.exists(), "proposal mode must write AGENTS.dircreative.proposed.md")
        proposed_text = proposed_path.read_text(encoding="utf-8")
        require("INACTIVE PROPOSAL" in proposed_text, "proposal must state inactive status")
        require("keep this sentinel" in proposed_text, "proposal must preserve existing root policy")
        require("<!-- DIRcreative:BEGIN project-rules -->" in proposed_text, "proposal must include a scoped DIRcreative block")

        informational_missing_terms = run_project_agents("audit", str(target))
        require(informational_missing_terms.returncode == 0, "default audit must not fail on incomplete active AGENTS.md")
        missing_terms = run_project_agents("audit", str(target), "--require-active")
        require(missing_terms.returncode != 0, "audit --require-active must fail when active AGENTS.md misses DIRcreative terms")
        require(
            "active_agents_missing_required_dircreative_terms" in missing_terms.stdout,
            "audit must name missing required DIRcreative terms",
        )

        agents_path.write_text("# Existing Project Rules\n\nNever use DIRcreative here.\n", encoding="utf-8")
        conflict_hash = hashlib.sha256(agents_path.read_bytes()).hexdigest()
        proposed_path.unlink()
        conflict = run_project_agents("generate", str(target), "--mode", "propose")
        require(conflict.returncode != 0, "explicit hierarchy conflict must stop proposal")
        require("agents_hierarchy_conflict:" in conflict.stdout, "hierarchy conflict failed for the wrong reason")
        require(hashlib.sha256(agents_path.read_bytes()).hexdigest() == conflict_hash, "conflict check changed root AGENTS.md")
        require(not proposed_path.exists(), "conflict check wrote a proposal")
        require(hashlib.sha256(child_agents.read_bytes()).hexdigest() == child_agents_hash, "proposal or conflict check changed child AGENTS.md")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "docs").mkdir(parents=True)
        (repo / "docs" / "agents.md").write_text(
            "This project documents project-level AGENTS.md generation for DIRcreative.\n",
            encoding="utf-8",
        )
        missing_impl = run_project_agents(
            "audit-repo",
            "--repo-root",
            str(repo),
            "--implementation-script",
            "scripts/missing_project_agents.py",
        )
        require(missing_impl.returncode != 0, "repo audit must fail when docs mention generation but implementation is missing")
        require(
            "docs_mention_agents_generation_but_implementation_missing" in missing_impl.stdout,
            "repo audit must name missing implementation",
        )


def validate_source_registries() -> None:
    model_sources = load_yaml(require_path("docs/film-preproduction/sources/model-sources.yaml"))
    prompt_sources = load_yaml(require_path("docs/film-preproduction/sources/prompt-sources.yaml"))
    model_keys = {item.get("model_key") for item in model_sources.get("models", [])}
    require({"seedance", "kling", "runway", "veo", "tapnow_canvas"}.issubset(model_keys), "model source registry missing required model keys")
    for item in model_sources.get("models", []):
        require(item.get("primary_url"), f"model source {item.get('model_key')} missing primary_url")
        require(item.get("official_or_primary_facts"), f"model source {item.get('model_key')} missing facts")
        require(item.get("inferred_adapter_behavior"), f"model source {item.get('model_key')} missing inferred adapter behavior")

    active_ids = set()
    for item in prompt_sources.get("sources", []):
        active_ids.update(item.get("active_pattern_ids", []))
        require("reuse_policy" in item, f"prompt source {item.get('source_key')} missing reuse policy")
    require(active_ids, "prompt source registry has no active pattern IDs")


def validate_reference_policy_docs() -> None:
    behavior = require_path("docs/film-preproduction/research/model-reference-behavior.md").read_text(encoding="utf-8").lower()
    locking = require_path("docs/film-preproduction/reference-locking-policy.md").read_text(encoding="utf-8").lower()
    consistency = require_path("docs/film-preproduction/reference-consistency-gate.md").read_text(encoding="utf-8").lower()
    shot_language = require_path("docs/film-preproduction/shot-language-standard.md").read_text(encoding="utf-8").lower()
    longform = require_path("docs/film-preproduction/longform-decomposition-policy.md").read_text(encoding="utf-8").lower()
    capability = require_path("docs/film-preproduction/capability-aware-generation-policy.md").read_text(encoding="utf-8").lower()
    co_creation = require_path("docs/film-preproduction/co-creation-gate-policy.md").read_text(encoding="utf-8").lower()
    required_terms = [
        "seedance",
        "kling",
        "runway",
        "veo",
        "tapnow",
        "clean first frame",
        "anti-misread",
        "direct input policy",
        "user co-creation gates",
        "stale downstream artifacts",
        "visual_output_mode",
        "prompt_only",
        "assisted_generation",
        "external_generation",
        "longform_generation_mode",
        "hybrid",
        "sequence pack",
        "asset_output.status",
        "co-creation",
        "simulated_fixture",
        "real_user",
        "clean_frame_gate",
        "video_prompt_gate",
        "character consistency",
        "scene consistency",
        "character_identity_lock",
        "scene_geography_camera_lock",
        "professional_storyboard_motion_map",
        "storyboard_information_density_too_low",
        "dominant page title",
        "film title",
        "pre-generation contract",
        "pre_generation_contract",
        "shot image",
        "focal length",
        "sound",
    ]
    combined = "\n".join([behavior, locking, consistency, shot_language, longform, capability, co_creation])
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"reference policy docs missing terms: {missing}")


def validate_production_prompt_discipline() -> None:
    path = "docs/film-preproduction/production-prompt-discipline.md"
    text = require_path(path).read_text(encoding="utf-8")
    lower = text.lower()
    required_terms = [
        "dircreative separates prompt construction from execution",
        "pre-delivery harness",
        "lock-order check",
        "material selection",
        "material-selection check",
        "mode check",
        "authorization check",
        "prompt contract",
        "reference binding",
        "model constraints",
        "negative check",
        "prompt-window hygiene",
        "falsifiable success rubric",
        "model: which target model",
        "camera: one motivated camera behavior",
        "subject:",
        "look: lighting",
        "action:",
        "camera + subject + action + setting + style + lighting",
        "retries change one production variable at a time",
        "adding an mcp dependency",
        "thread history",
        ".dircreative/runs/",
        "skill_run_receipt",
        "professional storyboard/motion map",
        "character design",
        "scene layout",
        "prop continuity",
        "camera movement",
        "subject movement path",
        "shot-card text",
        "narrative purpose",
        "lens/support/movement",
        "material choices",
        "main-controller thread",
        "isolated worktree",
        "same-directory worker is read-only",
        "failed worktree initialization",
        "archive completed, failed, duplicate, and superseded worker threads",
        "objective_complete: no",
    ]
    missing = [term for term in required_terms if term not in lower]
    require(not missing, f"{path} missing discipline terms: {missing}")

    root = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    delivery_route = require_path("skills/dircreative/routes/delivery-audit.md").read_text(encoding="utf-8")
    image = require_path("skills/dircreative/image-prompt-compiler/SKILL.md").read_text(encoding="utf-8")
    video = require_path("skills/dircreative/video-model-adapter/SKILL.md").read_text(encoding="utf-8")
    for skill_path, skill_text in [
        ("skills/dircreative/image-prompt-compiler/SKILL.md", image),
        ("skills/dircreative/video-model-adapter/SKILL.md", video),
    ]:
        require("production-prompt-discipline.md" in skill_text, f"{skill_path} missing production prompt discipline knowledge")
        require("pre-delivery harness" in skill_text, f"{skill_path} missing pre-delivery harness rule")
    require(
        "Use strict evidence only when a real side effect" in root,
        "root router missing proportional Delivery audit boundary",
    )
    for term in ["Add evidence only for a real side effect", "Hash and version only actual delivery inputs and outputs"]:
        require(term in delivery_route, f"Delivery Route Card missing proportional audit rule: {term}")
    require("which material to make next" in image, "image prompt compiler missing material selection gate")
    require("Do not infer the material type from a vague image request" in image, "image prompt compiler missing vague material request guard")
    for term in ["character design locks", "scene layout locks", "prop continuity", "camera movement", "subject movement path", "emotional beat", "compact professional shot-card text", "lens/support/movement", "blocking/path", "sound or edit cue"]:
        require(term in image, f"image prompt compiler missing storyboard/motion field: {term}")
    require("change one variable at a time" in image, "image prompt compiler missing single-variable retry rule")
    require("change one variable at a time" in video, "video model adapter missing single-variable retry rule")
    require("five-layer check" in video, "video model adapter missing five-layer prompt check")
    require("six-slot check" in video, "video model adapter missing six-slot scene check")

    taxonomy = load_yaml(require_path("docs/film-preproduction/qa/failure-taxonomy.yaml"))
    id_list = [item.get("id") for item in taxonomy.get("failure_types", [])]
    ids = set(id_list)
    duplicates = sorted({failure_id for failure_id in id_list if id_list.count(failure_id) > 1})
    require(not duplicates, f"failure taxonomy has duplicate ids: {duplicates}")
    required_failures = {
        "plausibility_over_verification",
        "prompt_contract_incomplete",
        "multi_variable_retry",
        "stale_reference_context",
        "missing_falsifiable_success_criteria",
        "material_selection_missing",
        "thread_control_incomplete",
        "community_recipe_overfit",
    }
    require(required_failures.issubset(ids), f"failure taxonomy missing prompt discipline failures: {sorted(required_failures - ids)}")
    retry_text = require_path("docs/film-preproduction/qa/retry-rules.md").read_text(encoding="utf-8")
    missing_retry = [failure_id for failure_id in required_failures if failure_id not in retry_text]
    require(not missing_retry, f"retry rules missing prompt discipline failures: {missing_retry}")


def validate_ai_video_prompt_community_lessons() -> None:
    path = "docs/film-preproduction/research/ai-video-prompt-community-lessons.md"
    research = require_path(path).read_text(encoding="utf-8")
    root = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    image = require_path("skills/dircreative/image-prompt-compiler/SKILL.md").read_text(encoding="utf-8")
    video = require_path("skills/dircreative/video-model-adapter/SKILL.md").read_text(encoding="utf-8")
    prompt_discipline = require_path("docs/film-preproduction/production-prompt-discipline.md").read_text(encoding="utf-8")
    taxonomy = require_path("docs/film-preproduction/qa/failure-taxonomy.yaml").read_text(encoding="utf-8")
    retry = require_path("docs/film-preproduction/qa/retry-rules.md").read_text(encoding="utf-8")
    combined = "\n".join([research, root, image, video, prompt_discipline, taxonomy, retry])
    required_terms = [
        "Higgsfield community prompt skill",
        "github.com/OSideMedia/higgsfield-ai-prompt-skill",
        "github.com/higgsfield-ai/skills",
        "x.com/D_studioproject/status/2062078290249253134",
        "cookbook.openai.com/examples/sora/sora2_prompting_guide",
        "boords.com/storyboard-template",
        "reddit.com/r/PromptEngineering",
        "MCSLA",
        "prompt construction from execution",
        "six-slot scene check",
        "micro-scene beat sheet",
        "initial visible state",
        "trigger or pressure",
        "subject action path",
        "camera start target",
        "camera end target",
        "final visible state",
        "professional storyboard cell",
        "shot-card language",
        "material selection",
        "community_recipe_overfit",
        "weak community signals",
        "Do not add a Higgsfield MCP",
        "Use community recipes only as reusable structure",
        "falsifiable success criteria",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"{path} missing community prompt lesson terms: {missing}")
    for skill_path, skill_text in [
        ("skills/dircreative/image-prompt-compiler/SKILL.md", image),
        ("skills/dircreative/video-model-adapter/SKILL.md", video),
    ]:
        require("ai-video-prompt-community-lessons.md" in skill_text, f"{skill_path} missing community prompt lessons knowledge")
    require("community_recipe_overfit" in taxonomy, "failure taxonomy missing community_recipe_overfit")
    require("community_recipe_overfit" in retry, "retry rules missing community_recipe_overfit")


def validate_duration_unit_policy() -> None:
    combined = "\n".join(
        [
            require_path("docs/film-preproduction/longform-decomposition-policy.md").read_text(encoding="utf-8"),
            require_path("docs/film-preproduction/chat-acceptance-checklist.md").read_text(encoding="utf-8"),
            require_path("docs/film-preproduction/live-chat-acceptance-runbook.md").read_text(encoding="utf-8"),
            require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8"),
            require_path("skills/dircreative/idea-intake/SKILL.md").read_text(encoding="utf-8"),
            require_path("skills/dircreative/script-treatment/SKILL.md").read_text(encoding="utf-8"),
            require_path("skills/dircreative/sequence-planner/SKILL.md").read_text(encoding="utf-8"),
        ]
    )
    required_terms = [
        "generation-unit ceiling",
        "not the default story duration",
        "story_duration",
        "generation_unit_limit",
        "ambiguous_duration",
        "Do not compress a multi-minute story into one 15s script",
        "story duration",
        "generation-unit limit",
        "5-15s sequence units",
        "5-15s generation units",
        "每组视频生成上限",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"duration/unit policy missing terms: {missing}")


def validate_reference_failure_types() -> None:
    taxonomy = load_yaml(require_path("docs/film-preproduction/qa/failure-taxonomy.yaml"))
    raw_ids = [item.get("id") for item in taxonomy.get("failure_types", [])]
    ids = set(raw_ids)
    duplicates = sorted({failure_id for failure_id in raw_ids if raw_ids.count(failure_id) > 1})
    require(not duplicates, f"failure taxonomy contains duplicate IDs: {duplicates}")
    required = {
        "reference_board_too_dense_for_model",
        "clean_first_frame_missing",
        "reference_role_conflict",
        "unreadable_reference_text",
        "element_reference_missing",
        "first_frame_does_not_match_shot",
        "model_pack_budget_exceeded",
        "board_used_as_direct_i2v_input_when_forbidden",
        "visual_output_mode_missing",
        "missing_asset_output_status",
        "unauthorized_assisted_generation",
        "longform_sequence_plan_missing",
        "sequence_pack_overloaded",
        "batch_mode_risk_unaccepted",
        "external_generation_instructions_missing",
        "character_identity_reference_drift",
        "scene_geography_reference_drift",
        "reference_asset_duplicate_conflict",
        "reference_asset_role_label_missing",
        "reference_role_label_hierarchy_wrong",
        "image_generation_called_without_pre_generation_contract",
        "storyboard_information_density_too_low",
        "image_prompt_missing_visual_decomposition",
        "image_prompt_missing_prompt_layers",
        "invented_visual_fact",
        "empty_quality_wording",
    }
    require(required.issubset(ids), f"failure taxonomy missing reference failures: {sorted(required - ids)}")
    retry_text = require_path("docs/film-preproduction/qa/retry-rules.md").read_text(encoding="utf-8")
    missing_retry = [failure_id for failure_id in required if failure_id not in retry_text]
    require(not missing_retry, f"retry rules missing reference failures: {missing_retry}")

def validate_tapnow_canvas_lessons() -> None:
    docs = [
        require_path("docs/film-preproduction/research/tapnow-agentic-canvas-lessons.md"),
        require_path("docs/film-preproduction/research/model-reference-behavior.md"),
        require_path("docs/film-preproduction/capability-aware-generation-policy.md"),
        require_path("docs/film-preproduction/05-skill-integration-architecture.md"),
        require_path("skills/dircreative/reference-image-planner/SKILL.md"),
        require_path("skills/dircreative/video-model-adapter/SKILL.md"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in docs)
    required_terms = [
        "tapnow",
        "agentic canvas",
        "canvas graph receipt",
        "asset nodes",
        "direct video input",
        "planning-only",
        "prompt optimizer provenance",
        "start/end frames",
        "clean start/end frames",
        "do not copy blindly",
        "graph edges",
        "video nodes",
    ]
    missing = [term for term in required_terms if term.lower() not in combined]
    require(not missing, f"TapNow canvas lessons missing terms: {missing}")


def validate_professional_agent_voice() -> None:
    docs = [
        require_path("docs/film-preproduction/professional-agent-voice-standard.md"),
        require_path("docs/film-preproduction/customer-visible-production-gates.md"),
        require_path("docs/film-preproduction/shot-language-standard.md"),
        require_path("skills/dircreative/SKILL.md"),
        require_path("skills/dircreative/chat-facilitator/SKILL.md"),
        require_path("skills/dircreative/director-room/SKILL.md"),
        require_path("skills/dircreative/image-prompt-compiler/SKILL.md"),
        require_path("skills/dircreative/story-development/SKILL.md"),
        require_path("skills/dircreative/script-treatment/SKILL.md"),
        require_path("skills/dircreative/shot-design/SKILL.md"),
        require_path("skills/dircreative/visual-bible/SKILL.md"),
        require_path("examples/independent-agent-scent-brand-test/01-full-flow-transcript.md"),
        require_path("examples/independent-agent-scent-brand-test/02-independent-review.md"),
        require_path("examples/live-user-sim-noodle/16-chat-interface-demo.md"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in docs)
    required_terms = [
        "professional judgment",
        "专业判断",
        "取舍",
        "执行影响",
        "channel fit",
        "hook timing",
        "story clarity",
        "visual grammar",
        "edit logic",
        "reference strategy",
        "model risk",
        "叙事任务",
        "机位/镜头",
        "主体调度",
        "构图层次",
        "声音剪辑",
        "模型风险",
        "客户可见预览",
        "brand_assets",
        "product_lock",
        "human_strategy",
        "delivery_priority",
        "PRODUCT IDENTITY REFERENCE",
        "FUNCTION DETAIL REFERENCE",
        "USAGE POSITION REFERENCE",
        "mouse",
        "soap",
        "jewelry box",
        "support/environment hardware",
        "New Chinese / Eastern Style Risk Gate",
    ]
    missing = [term for term in required_terms if term.lower() not in combined]
    require(not missing, f"professional agent voice missing terms: {missing}")


def validate_story_script_tension_rules() -> None:
    story = require_path("skills/dircreative/story-development/SKILL.md").read_text(encoding="utf-8")
    script = require_path("skills/dircreative/script-treatment/SKILL.md").read_text(encoding="utf-8")
    root = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    taxonomy = require_path("docs/film-preproduction/qa/failure-taxonomy.yaml").read_text(encoding="utf-8")
    retry = require_path("docs/film-preproduction/qa/retry-rules.md").read_text(encoding="utf-8")
    combined = "\n".join([story, script, root, taxonomy, retry])
    required_terms = [
        "story engine",
        "external pressure",
        "hidden relationship engine",
        "irreversible choice",
        "escalation",
        "visible ending action",
        "setting is a plot device",
        "conflict pressure",
        "turn/reveal",
        "visual_generation_before_story_lock",
        "story_development_skipped",
        "script_depth_insufficient",
        "Do not use visual polish",
        "mark downstream visual assets as not locked",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"story/script tension rules missing terms: {missing}")


def client_visible_forbidden_terms(text: str) -> list[str]:
    found: list[str] = []
    for term in CLIENT_FILM_FORBIDDEN_VISIBLE_TERMS:
        if term == "AI":
            if re.search(r"(?<![A-Za-z])AI(?![A-Za-z])", text):
                found.append(term)
            continue
        if term.isascii():
            if re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", text, re.IGNORECASE):
                found.append(term)
            continue
        if term in text:
            found.append(term)
    return found


def validate_client_visible_language(path: str, blocks: Any) -> None:
    require(isinstance(blocks, list) and blocks, f"{path} missing client_visible_text_blocks")
    violations: list[str] = []
    for index, block in enumerate(blocks, start=1):
        require(isinstance(block, str) and block.strip(), f"{path} client visible block {index} is empty")
        terms = client_visible_forbidden_terms(block)
        if terms:
            violations.append(f"block {index}: {terms}")
    require(not violations, f"{path} customer-visible text contains internal terms: {violations}")


def validate_client_film_acceptance_boundary(path: str, boundary: dict[str, Any]) -> None:
    require(boundary.get("validation_scope") == "structural_contract_only", f"{path} acceptance boundary must be structural_contract_only")
    for key in [
        "structural_pass_not_client_deliverable",
        "structural_pass_not_copy_quality",
        "structural_pass_not_visual_quality",
        "structural_pass_not_asset_authorization",
        "structural_pass_not_live_acceptance",
    ]:
        require(boundary.get(key) is True, f"{path} acceptance boundary missing {key}: true")


def validate_client_film_prompt_order(path: str, contract: dict[str, Any]) -> None:
    prompt_gate = contract.get("prompt_generation", {})
    prompts = prompt_gate.get("prompts", [])
    status = prompt_gate.get("status")
    if status == "pass" or prompts:
        locked = prompt_gate.get("input_gates_locked", {})
        missing_locks = [gate for gate in ["story", "script", "shot", "asset_reference"] if locked.get(gate) is not True]
        require(
            not missing_locks,
            f"{path} prompt generation requires locked story/script/shot/asset gates before prompts: {missing_locks}",
        )
        gate_status = contract.get("gate_status", {})
        not_pass = [gate for gate in ["story", "script", "shot", "asset_reference"] if gate_status.get(gate) != "pass"]
        require(
            not not_pass,
            f"{path} prompt generation cannot pass before upstream gate_status pass: {not_pass}",
        )


def validate_client_film_script_gate(path: str, script_gate: dict[str, Any], target_duration_sec: int | None) -> None:
    if target_duration_sec is None or target_duration_sec < 60:
        return
    budget = script_gate.get("time_budget", {})
    require(parse_seconds(budget.get("total_sec")) == target_duration_sec, f"{path} 60s script requires a matching time budget")
    vo_lines = script_gate.get("vo_budget", {}).get("lines", [])
    require(vo_lines, f"{path} 60s script requires VO budget lines with shot/second coverage")
    for line in vo_lines:
        vo_id = line.get("vo_id", "unknown")
        text = str(line.get("text", "")).strip()
        require(text, f"{path} VO line {vo_id} missing readable text")
        forbidden_placeholders = ["VO marks this shot segment", "VO标注本镜头句段", "本镜头句段"]
        require(
            not any(term in text for term in forbidden_placeholders),
            f"{path} VO line {vo_id} contains internal placeholder text",
        )
        start = parse_seconds(line.get("start_sec"))
        end = parse_seconds(line.get("end_sec"))
        require(start is not None and end is not None and end > start, f"{path} VO line {vo_id} missing valid start/end seconds")
        require(line.get("covered_shot_ids"), f"{path} VO line {vo_id} missing covered_shot_ids")
        require(line.get("covered_seconds"), f"{path} VO line {vo_id} missing covered_seconds")


def validate_client_film_shot_gate(path: str, shot_gate: dict[str, Any], target_duration_sec: int | None) -> set[str]:
    shots = shot_gate.get("shots", [])
    require(isinstance(shots, list) and shots, f"{path} shot gate has no shots")
    story_sections = parse_seconds(shot_gate.get("story_sections_count"))
    rhythm_points = parse_seconds(shot_gate.get("rhythm_points_count"))
    if target_duration_sec is not None and target_duration_sec >= 60:
        require(rhythm_points is not None and rhythm_points >= 30, f"{path} 60s film requires 30+ shot/rhythm points")
        require(len(shots) >= 30, f"{path} 60s film cannot treat 12 story sections as the complete shot list")
        require(
            story_sections is None or rhythm_points > story_sections,
            f"{path} story sections must be distinct from shot/rhythm points",
        )
    shot_ids: set[str] = set()
    required_fields = [
        "shot_id",
        "timecode",
        "start_sec",
        "end_sec",
        "shot_size",
        "camera_position",
        "camera_movement",
        "subject_action",
        "emotional_function",
        "props_characters",
        "asset_source",
        "vertical_framing",
    ]
    for shot in shots:
        shot_id = shot.get("shot_id", "unknown")
        missing = [field for field in required_fields if is_blank(shot.get(field))]
        require(not missing, f"{path} shot {shot_id} missing client-film fields: {missing}")
        shot_ids.add(str(shot_id))
        start = parse_seconds(shot.get("start_sec"))
        end = parse_seconds(shot.get("end_sec"))
        require(start is not None and end is not None and end > start, f"{path} shot {shot_id} missing valid start/end seconds")
        require(parse_timecode_range(shot.get("timecode")) is not None, f"{path} shot {shot_id} missing valid timecode")
        if shot.get("hero_or_expression_critical") is True:
            require(
                shot.get("reference_motion") or shot.get("reference_video"),
                f"{path} hero/expression shot {shot_id} missing reference motion or video",
            )
    storyboard_pages = shot_gate.get("storyboard_pages", [])
    require(storyboard_pages, f"{path} missing storyboard page requirements")
    for page in storyboard_pages:
        page_id = page.get("page_id", "unknown")
        image_count = parse_seconds(page.get("image_count"))
        require(image_count is not None and 3 <= image_count <= 6, f"{path} storyboard page {page_id} must use 3-6 images")
        require(page.get("image_aspect_ratio"), f"{path} storyboard page {page_id} missing image aspect ratio")
        crop_policy = str(page.get("crop_policy", "")).lower()
        require("no_stretch" in crop_policy or "crop" in crop_policy, f"{path} storyboard page {page_id} must forbid stretch distortion")
        require(parse_seconds(page.get("min_image_width_px")) is not None, f"{path} storyboard page {page_id} missing min image width")
        caption = page.get("caption_standard", {})
        for key in ["story_first", "camera_second", "source_or_confirmation_last"]:
            require(caption.get(key) is True, f"{path} storyboard page {page_id} caption_standard missing {key}")
    return shot_ids


def validate_client_film_asset_gate(path: str, asset_gate: dict[str, Any], shot_ids: set[str]) -> None:
    contracts = asset_gate.get("per_shot_asset_contract", [])
    require(isinstance(contracts, list) and contracts, f"{path} missing per-shot asset contract")
    contract_by_shot: dict[str, dict[str, Any]] = {}
    for item in contracts:
        shot_id = item.get("shot_id")
        require(shot_id, f"{path} asset contract item missing shot_id")
        contract_by_shot[str(shot_id)] = item
        require(item.get("source_decision") in CLIENT_FILM_ASSET_SOURCE_DECISIONS, f"{path} shot {shot_id} invalid asset source decision")
        require(item.get("source_status"), f"{path} shot {shot_id} missing source_status")
        require(item.get("use_case") in {"planning", "client_preview", "direct_video_input", "ppt_storyboard"}, f"{path} shot {shot_id} missing valid use_case")
        require(item.get("usage_page"), f"{path} shot {shot_id} missing usage_page")
    if shot_ids:
        missing_contracts = sorted(shot_ids - set(contract_by_shot))
        require(not missing_contracts, f"{path} missing per-shot asset contract for shots: {missing_contracts[:10]}")
    if asset_gate.get("user_claims_existing_browser_images") is True:
        intake = asset_gate.get("browser_or_local_intake", {})
        completed = intake.get("completed") is True
        tool_blocked = "TOOL_BLOCKED" in str(intake.get("blocked_reason", ""))
        require(completed or tool_blocked, f"{path} existing browser/local images require intake or TOOL_BLOCKED")
        if completed:
            require(intake.get("inspected_sources"), f"{path} completed intake must list inspected sources")
    ref = asset_gate.get("reference_video_music", {})
    require(ref.get("music_tracks"), f"{path} missing music source/usage/lock status")
    for track in ref.get("music_tracks", []):
        require(track.get("source") and track.get("usage") and track.get("lock_status"), f"{path} music track missing source, usage, or lock status")


def validate_client_film_prompt_gate(path: str, prompt_gate: dict[str, Any], shot_ids: set[str]) -> None:
    if prompt_gate.get("status") != "pass":
        return
    prompts = prompt_gate.get("prompts", [])
    require(prompts, f"{path} prompt_generation pass requires prompts")
    required_fields = [
        "prompt_id",
        "from_locked_shot_id",
        "character_or_role",
        "prop",
        "action",
        "shot_size",
        "camera_angle",
        "composition",
        "orientation",
        "usage_page",
        "output_mode",
    ]
    for prompt in prompts:
        prompt_id = prompt.get("prompt_id", "unknown")
        missing = [field for field in required_fields if is_blank(prompt.get(field))]
        require(not missing, f"{path} prompt {prompt_id} missing locked-shot fields: {missing}")
        shot_id = str(prompt.get("from_locked_shot_id"))
        require(shot_id in shot_ids, f"{path} prompt {prompt_id} must bind to a locked shot")
        require(prompt.get("output_mode") in CLIENT_FILM_PROMPT_OUTPUT_MODES, f"{path} prompt {prompt_id} invalid output mode")
        combined = " ".join(str(prompt.get(field, "")) for field in required_fields).lower()
        require("clean image" not in combined and "清洁图" not in combined, f"{path} prompt {prompt_id} is a generic clean image prompt")


def validate_client_film_story_gate(path: str, story_gate: dict[str, Any]) -> None:
    preview = story_gate.get("customer_readable_story_preview", [])
    require(isinstance(preview, list) and len(preview) >= 2, f"{path} story gate requires 2+ customer-readable story paragraphs")
    short = [index for index, paragraph in enumerate(preview, start=1) if len(str(paragraph).strip()) < 40]
    require(not short, f"{path} story preview paragraphs are too short to be customer-readable: {short}")
    require(story_gate.get("preserved_brief_requirements"), f"{path} missing preserved_brief_requirements")
    require(
        story_gate.get("omitted_requirements_without_user_removal", []) == [],
        f"{path} has brief requirements omitted without user removal",
    )
    ellipsis = story_gate.get("prop_ellipsis_rule", {})
    if ellipsis.get("source_has_ellipsis") is True:
        expansions = ellipsis.get("expansions", [])
        required_count = parse_seconds(ellipsis.get("required_friend_count")) or 0
        require(len(expansions) >= required_count, f"{path} prop ellipsis expansion does not cover every required friend")
        for item in expansions:
            missing = [field for field in ["role_identity", "prop", "action", "shot_function"] if not item.get(field)]
            require(not missing, f"{path} prop ellipsis expansion missing fields: {missing}")


def validate_client_film_thread_discipline(path: str, contract: dict[str, Any]) -> None:
    thread = contract.get("thread_discipline", {})
    if thread.get("codex_threads_requested") is True:
        require(thread.get("real_thread_dispatch_required") is True, f"{path} requested Codex Threads must require real dispatch")
        require(
            thread.get("dispatch_receipt_adoption_cleanup_required") is True,
            f"{path} requested Codex Threads must require receipt/adoption/cleanup",
        )
        require(
            thread.get("fallback_to_simulated_workers_allowed") is False,
            f"{path} requested Codex Threads must forbid simulated worker fallback",
        )


def validate_client_film_gate_contract(path: str) -> None:
    data = load_yaml(require_path(path))
    contract = data.get("client_film_gate_contract", {})
    require(contract, f"{path} missing client_film_gate_contract")
    gate_status = contract.get("gate_status", {})
    for gate in CLIENT_FILM_STAGE_GATES:
        require(gate_status.get(gate) in {"pending", "pass", "fail", "blocked"}, f"{path} invalid gate status for {gate}")
    validate_client_film_prompt_order(path, contract)
    validate_client_visible_language(path, contract.get("client_visible_text_blocks", []))
    validate_client_film_acceptance_boundary(path, contract.get("acceptance_boundary", {}))
    target_duration_sec = parse_seconds(contract.get("target_duration_sec"))
    validate_client_film_script_gate(path, contract.get("script_gate", {}), target_duration_sec)
    shot_ids: set[str] = set()
    if gate_status.get("shot") == "pass":
        shot_ids = validate_client_film_shot_gate(path, contract.get("shot_gate", {}), target_duration_sec)
    if gate_status.get("asset_reference") == "pass":
        validate_client_film_asset_gate(path, contract.get("asset_reference_gate", {}), shot_ids)
    validate_client_film_prompt_gate(path, contract.get("prompt_generation", {}), shot_ids)
    if gate_status.get("story") == "pass":
        validate_client_film_story_gate(path, contract.get("story_gate", {}))
    validate_client_film_thread_discipline(path, contract)
    qa = data.get("qa", {})
    require(qa.get("client_film_gate_contract") == "pass", f"{path} qa.client_film_gate_contract must be pass")


def validate_invalid_client_film_fixture(path: str, expected_terms: list[str]) -> None:
    try:
        validate_client_film_gate_contract(path)
    except ValidationError as exc:
        message = str(exc)
        require(all(term in message for term in expected_terms), f"{path} failed for the wrong reason: {exc}")
        return
    raise ValidationError(f"{path} must reject invalid client film gate contract")


def validate_client_film_hard_gates_docs() -> None:
    paths = [
        "docs/film-preproduction/client-film-hard-gates.md",
        "docs/film-preproduction/schemas/client-film-gate-contract.yaml",
        "skills/dircreative/SKILL.md",
        "skills/dircreative/story-development/SKILL.md",
        "skills/dircreative/script-treatment/SKILL.md",
        "skills/dircreative/shot-design/SKILL.md",
        "skills/dircreative/reference-image-planner/SKILL.md",
        "skills/dircreative/image-prompt-compiler/SKILL.md",
    ]
    combined = "\n".join(require_path(path).read_text(encoding="utf-8") for path in paths)
    required_terms = [
        "customer-readable story preview",
        "preserved_brief_requirements",
        "omitted_requirements_without_user_removal",
        "Prop ellipsis",
        "VO budget",
        "covered_shot_ids",
        "12 customer story sections",
        "at least 30 shot/rhythm points",
        "per-shot asset/reference contract",
        "existing Grok",
        "existing ChatGPT",
        "browser/local intake",
        "locked shot ID",
        "prompt_only",
        "Customer-visible copy must not expose",
        "3-6 images",
        "reference video",
        "music",
        "real Codex Thread dispatch",
        "TOOL_BLOCKED",
        "structural validation",
        "A validated structure is not the same thing as a client-sendable deck",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"client film hard gates missing terms: {missing}")


def validate_client_film_gate_contract_fixtures() -> None:
    validate_client_film_gate_contract("tests/fixtures/valid-client-film-gate-contract.yaml")
    validate_invalid_client_film_fixture(
        "tests/fixtures/invalid-client-film-direct-prompt.yaml",
        ["prompt generation requires locked story/script/shot/asset gates"],
    )
    validate_invalid_client_film_fixture(
        "tests/fixtures/invalid-client-film-missing-vo-timecode.yaml",
        ["60s script requires VO budget lines"],
    )
    validate_invalid_client_film_fixture(
        "tests/fixtures/invalid-client-film-missing-shot-timecode.yaml",
        ["missing client-film fields", "timecode"],
    )
    validate_invalid_client_film_fixture(
        "tests/fixtures/invalid-client-film-internal-terms.yaml",
        ["customer-visible text contains internal terms"],
    )
    validate_invalid_client_film_fixture(
        "tests/fixtures/invalid-client-film-missing-asset-contract.yaml",
        ["missing per-shot asset contract"],
    )
    validate_invalid_client_film_fixture(
        "tests/fixtures/invalid-client-film-twelve-sections-as-shots.yaml",
        ["60s film requires 30+ shot/rhythm points"],
    )


def validate_production_demo_retrospective() -> None:
    path = "docs/film-preproduction/production-demo-retrospective.md"
    retrospective = require_path(path).read_text(encoding="utf-8")
    root = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    story = require_path("skills/dircreative/story-development/SKILL.md").read_text(encoding="utf-8")
    script = require_path("skills/dircreative/script-treatment/SKILL.md").read_text(encoding="utf-8")
    shot = require_path("skills/dircreative/shot-design/SKILL.md").read_text(encoding="utf-8")
    image = require_path("skills/dircreative/image-prompt-compiler/SKILL.md").read_text(encoding="utf-8")
    combined = "\n".join([retrospective, root, story, script, shot, image])
    required_terms = [
        "not live acceptance",
        "OBJECTIVE_COMPLETE: NO",
        "live-user-acceptance.yaml",
        "story_development_skipped",
        "script_depth_insufficient",
        "visual_generation_before_story_lock",
        "storyboard_information_density_too_low",
        "prompt_contract_incomplete",
        "material_selection_missing",
        "thread_control_incomplete",
        "material selection gate",
        "professional shot-card text",
        "character design locks",
        "scene layout locks",
        "prop continuity",
        "camera movement",
        "subject movement path",
        "blocking/path",
        "model risk",
        "thread-orchestration-protocol.md",
        "main-controller thread",
        "failed worktree initialization",
        ".dircreative/runs/",
        "skill_run_receipt",
        "mark downstream visual assets as not locked",
        "Intent routing gate",
        "visual exploration",
        "story rebuild",
        "formal lockable material",
        "dramatic pressure card",
        "Tactic:",
        "Subtext:",
        "scene beat card",
        "Tactic change",
        "Visible shot-card template",
        "S03 00:18-00:24 | Narrative purpose:",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"{path} missing retrospective terms: {missing}")

    for skill_path, skill_text in [
        ("skills/dircreative/story-development/SKILL.md", story),
        ("skills/dircreative/script-treatment/SKILL.md", script),
        ("skills/dircreative/shot-design/SKILL.md", shot),
        ("skills/dircreative/image-prompt-compiler/SKILL.md", image),
    ]:
        require("production-demo-retrospective.md" in skill_text, f"{skill_path} missing production demo retrospective knowledge")
        require("council-adversarial-review.md" in skill_text, f"{skill_path} missing council adversarial review knowledge")


def validate_council_adversarial_review() -> None:
    path = "docs/film-preproduction/council-adversarial-review.md"
    review = require_path(path).read_text(encoding="utf-8")
    root = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    taxonomy = require_path("docs/film-preproduction/qa/failure-taxonomy.yaml").read_text(encoding="utf-8")
    retry = require_path("docs/film-preproduction/qa/retry-rules.md").read_text(encoding="utf-8")
    combined = "\n".join([review, root, taxonomy, retry])
    required_terms = [
        "User Viewpoint",
        "Professional Film Expert Viewpoint",
        "Product Manager Viewpoint",
        "Skill Developer Viewpoint",
        "Code Researcher Viewpoint",
        "storyboarding and previsualization",
        "character identity reference",
        "scene/FOV reference",
        "storyboard/motion map",
        "clean frame",
        "camera/lens/blocking/movement",
        "agent guardrails",
        "handoffs",
        "tools",
        "tracing",
        "hidden chat memory",
        "material_selection_missing",
        "thread_control_incomplete",
        "failed worktree initialization",
        "same-directory worker writes",
        "archived",
        "main-controller thread pinned",
        "OBJECTIVE_COMPLETE: NO",
        "live user acceptance",
        "smallest repo change",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"{path} missing council review terms: {missing}")


def validate_thread_orchestration_protocol() -> None:
    path = "docs/film-preproduction/thread-orchestration-protocol.md"
    protocol = require_path(path).read_text(encoding="utf-8")
    root = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    prompt_discipline = require_path("docs/film-preproduction/production-prompt-discipline.md").read_text(encoding="utf-8")
    research = require_path("docs/film-preproduction/research/thread-orchestration-community-lessons.md").read_text(encoding="utf-8")
    schema = require_path("docs/film-preproduction/schemas/thread-dispatch-record.yaml").read_text(encoding="utf-8")
    template = require_path("docs/film-preproduction/schemas/thread-dispatch-record.template.yaml").read_text(encoding="utf-8")
    cleanup = load_yaml(require_path("tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-06.yaml"))
    cleanup_text = require_path("tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-06.yaml").read_text(encoding="utf-8")
    combined = "\n".join([protocol, root, prompt_discipline, research, schema, template, cleanup_text])
    required_terms = [
        "Status: legacy v1 evidence reader",
        "Fast uses zero Threads",
        "Studio uses one controller and zero Threads by default",
        "No current route implicitly creates a Thread",
        "adco.specialist-exchange@2.0",
        "inline",
        "rejects nested dispatch",
        "Existing v1 handoffs remain readable",
        "Legacy V1 Evidence Shape",
        "thread_id",
        "lane_run_id",
        "local snapshot is not treated as trusted live host attestation",
        "thread-dispatch-record.yaml",
        "thread-dispatch-record.template.yaml",
        "thread_dispatch_record",
        "allowed_thread_classes",
        "pinned_user_facing_controller",
        "archive_after_consumed",
        "may_mark_goal_complete: false",
        "thread-orchestration-cleanup-2026-06-06",
        "disposable_workers_archived",
        "second_level_subagents",
        "TOOL_BLOCKED",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"thread orchestration protocol missing terms: {missing}")
    residuals: list[str] = []
    for contract_path in THREAD_CONTRACT_TEXT_PATHS:
        text = require_path(contract_path).read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_THREAD_CONTRACT_PHRASES:
            if phrase in text:
                residuals.append(f"{contract_path}: forbidden thread-contract residual: {phrase}")
    require(not residuals, "thread contract residual wording found:\n" + "\n".join(residuals))

    run = cleanup.get("run", {})
    qa = cleanup.get("qa", {})
    receipt = cleanup.get("skill_run_receipt", {})
    dispatch_record = cleanup.get("thread_dispatch_record", {})
    dispatches = cleanup.get("dispatches", [])
    policy = cleanup.get("thread_class_policy", {})
    boundary = cleanup.get("completion_boundary", {})
    require(run.get("run_type") == "real_thread_cleanup_record", "thread cleanup receipt must be a real cleanup record")
    require(run.get("main_controller_thread", {}).get("pinned") is True, "main controller must be pinned in cleanup receipt")
    require(len(run.get("disposable_workers_archived", [])) >= 2, "cleanup receipt must record archived disposable workers")
    require(dispatch_record.get("main_controller_thread_id") == run.get("main_controller_thread", {}).get("thread_id"), "dispatch record must match main controller")
    require(policy.get("hidden_thread_state_is_truth") is False, "thread policy must forbid hidden thread state truth")
    require(len(dispatches) >= 3, "thread dispatch record must include main controller and consumed workers")
    require(sum(1 for item in dispatches if item.get("thread_class") == "pinned_user_facing_controller" and item.get("pinned") is True) == 1, "thread dispatch record must have one pinned controller")
    require(all(item.get("may_mark_goal_complete") is False for item in dispatches), "thread dispatches must not be able to mark goal complete")
    require(boundary.get("completion_claim_allowed") is False and boundary.get("objective_complete") is False, "thread dispatch boundary must not allow completion")
    require(qa.get("disposable_workers_archived") is True, "cleanup receipt must mark disposable workers archived")
    require(qa.get("unintended_worker_worktrees_present") is False, "cleanup receipt must show no unintended worker worktrees")
    require(qa.get("live_user_acceptance_written") is False, "cleanup receipt must not write live acceptance")
    require(qa.get("objective_complete_claimed") is False, "cleanup receipt must not claim objective complete")
    require(receipt.get("qa_gate", {}).get("status") == "needs_user", "thread cleanup receipt must keep qa_gate needs_user")


def validate_second_level_dispatch_record(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    policy = data.get("thread_class_policy", {}).get("second_level_subagents", {})
    dispatches = data.get("dispatches", [])
    has_invocations = any(item.get("second_level_subagents") for item in dispatches)
    if not policy and not has_invocations:
        return failures

    allowed_hosts = {
        "disposable_read_only_worker",
        "isolated_worktree_worker",
        "reusable_research_thread",
    }
    allowed_modes = {
        "prompt_decomposition",
        "reference_check",
        "risk_inventory",
        "candidate_ranking",
        "source_or_contract_triage",
    }
    forbidden_actions = {
        "write_files",
        "write_live_acceptance",
        "change_write_scope",
        "verify_cleanup",
        "mark_goal_complete",
        "mark_objective_complete",
        "become_durable_truth",
    }

    if policy.get("allowed") is not True:
        failures.append("second-level subagents policy must set allowed true")
    if policy.get("default_authorized") is not False:
        failures.append("second-level subagents must default to unauthorized")
    if set(policy.get("host_thread_classes", [])) != allowed_hosts:
        failures.append("second-level host thread classes mismatch")
    if not allowed_modes.issubset(set(policy.get("allowed_task_modes", []))):
        failures.append("second-level allowed task modes incomplete")
    if not forbidden_actions.issubset(set(policy.get("forbidden_actions", []))):
        failures.append("second-level forbidden actions incomplete")

    for item in dispatches:
        second_level = item.get("second_level_subagents")
        if not second_level:
            continue
        authorized = second_level.get("authorized") is True
        item_modes = set(second_level.get("allowed_task_modes", []))
        if authorized and item.get("thread_class") not in allowed_hosts:
            failures.append("second-level subagent authorized on invalid host thread class")
        if not authorized and second_level.get("invocations"):
            failures.append("second-level invocations require explicit authorization")
        if not item_modes.issubset(allowed_modes):
            failures.append("second-level dispatch allowed_task_modes contains invalid mode")
        for invocation in second_level.get("invocations", []):
            task_mode = invocation.get("task_mode")
            if task_mode not in allowed_modes or task_mode not in item_modes:
                failures.append("second-level invocation task_mode not authorized")
            if invocation.get("agent_type") not in {"stateless_read_only", "ephemeral_readonly"}:
                failures.append("second-level invocation must be stateless read-only")
            if not invocation.get("input_question"):
                failures.append("second-level invocation missing input_question")
            if invocation.get("closed_status") == "tool_blocked":
                if invocation.get("subagent_id") != "TOOL_BLOCKED":
                    failures.append("second-level TOOL_BLOCKED invocation must record TOOL_BLOCKED")
            elif not invocation.get("subagent_id"):
                failures.append("second-level invocation missing subagent_id")
            if not invocation.get("output_summary"):
                failures.append("second-level invocation missing output_summary")
            if invocation.get("closed_status") not in {"not_used", "completed_closed", "tool_blocked"}:
                failures.append("second-level invocation invalid closed_status")
            if invocation.get("adoption_decision") not in {"not_used", "adopted", "rejected", "deferred"}:
                failures.append("second-level invocation invalid adoption_decision")
            if invocation.get("adoption_decision") == "adopted" and not invocation.get("adopted_into"):
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


def validate_thread_dispatch_record(data: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    dispatch_record = data.get("thread_dispatch_record", {})
    policy = data.get("thread_class_policy", {})
    dispatches = data.get("dispatches", [])
    worktree = data.get("worktree_audit", {})
    boundary = data.get("completion_boundary", {})
    qa = data.get("qa", {})
    budget = data.get("thread_budget", {})

    allowed = {
        "pinned_user_facing_controller",
        "disposable_read_only_worker",
        "isolated_worktree_worker",
        "reusable_research_thread",
    }
    output_statuses = {"pending", "consumed", "rejected", "adopted", "deferred"}
    if dispatch_record.get("main_controller_thread_id") == "":
        failures.append("missing main_controller_thread_id")
    if policy.get("hidden_thread_state_is_truth") is not False:
        failures.append("hidden_thread_state_is_truth must be false")
    if set(policy.get("allowed_thread_classes", [])) != allowed:
        failures.append("allowed_thread_classes mismatch")
    if policy.get("substantive_output_default_thread_class") != "isolated_worktree_worker":
        failures.append("substantive output must default to isolated worktree worker")
    if policy.get("read_only_worker_use") != "review_research_cold_review_only":
        failures.append("read-only workers must be limited to review, research, and cold review")
    if policy.get("main_controller_write_boundary") != "receipts_adoption_merge_rollback_validation_only":
        failures.append("main-controller write boundary must be receipts/adoption/merge/rollback/validation only")
    max_active = budget.get("max_active_workers")
    active_count = budget.get("active_worker_count")
    approval_required_above = budget.get("approval_required_above")
    if max_active != 3:
        failures.append("thread budget max_active_workers must be 3")
    if approval_required_above != 5:
        failures.append("thread budget approval_required_above must be 5")
    if not isinstance(active_count, int) or active_count < 0:
        failures.append("thread budget active_worker_count must be non-negative integer")
    elif isinstance(max_active, int) and active_count > max_active and not budget.get("over_budget_reason"):
        failures.append("thread budget over max_active_workers requires over_budget_reason")
    if isinstance(active_count, int) and active_count > 5:
        failures.append("thread budget active_worker_count exceeds approval threshold")
    main = [item for item in dispatches if item.get("thread_class") == "pinned_user_facing_controller"]
    if len(main) != 1 or main[0].get("pinned") is not True or main[0].get("cleanup_rule") != "keep_pinned":
        failures.append("must have exactly one pinned main-controller thread")
    if len(main) == 1 and dispatch_record.get("main_controller_thread_id") != main[0].get("thread_id"):
        failures.append("main_controller_thread_id must match pinned controller dispatch")
    if any(item.get("may_mark_goal_complete") is not False for item in dispatches):
        failures.append("worker dispatch may mark goal complete")
    thread_ids = [item.get("thread_id") for item in dispatches if item.get("thread_id")]
    duplicate_thread_ids = sorted({thread_id for thread_id in thread_ids if thread_ids.count(thread_id) > 1})
    if duplicate_thread_ids:
        failures.append("thread_id reused across dispatches")
    for item in dispatches:
        thread_class = item.get("thread_class")
        if not item.get("thread_id"):
            failures.append("missing thread_id")
        if not item.get("role"):
            failures.append("missing role")
        if not item.get("professional_identity"):
            failures.append("missing professional_identity")
        if not item.get("viewpoint"):
            failures.append("missing viewpoint")
        if not item.get("read_scope"):
            failures.append("missing read_scope")
        if not item.get("allowed_actions"):
            failures.append("missing allowed_actions")
        if not item.get("expected_output"):
            failures.append("missing expected_output")
        if not item.get("stop_condition"):
            failures.append("missing stop_condition")
        if item.get("output_status") not in output_statuses:
            failures.append("invalid output_status")
        if thread_class != "pinned_user_facing_controller" and item.get("pinned") is True:
            failures.append("only main-controller thread may be pinned")
        if item.get("output_status") in {"consumed", "adopted"} and not item.get("findings_summary"):
            failures.append("consumed or adopted dispatch must summarize findings")
        if (
            thread_class != "pinned_user_facing_controller"
            and item.get("output_status") in {"consumed", "adopted"}
            and item.get("findings_summary")
            and not item.get("adopted_into")
        ):
            failures.append("consumed or adopted worker findings must be reconciled into durable artifacts")
        if thread_class not in allowed:
            failures.append(f"invalid thread_class: {thread_class}")
        if thread_class == "pinned_user_facing_controller":
            if item.get("write_scope") != "main_controller_only":
                failures.append("main-controller thread must have write_scope main_controller_only")
            if item.get("archived") is True:
                failures.append("main-controller thread must not be archived")
            allowed_actions_text = " ".join(str(action) for action in item.get("allowed_actions", []))
            controller_contract_text = " ".join(
                [
                    str(item.get("role", "")),
                    str(item.get("expected_output", "")),
                    allowed_actions_text,
                    " ".join(str(finding) for finding in item.get("findings_summary", [])),
                ]
            ).lower()
            if any(phrase in controller_contract_text for phrase in FORBIDDEN_THREAD_CONTRACT_PHRASES):
                failures.append("main-controller may only write receipts/adoption/merge/rollback/validation records")
        if thread_class == "disposable_read_only_worker":
            if item.get("write_scope") != "none":
                failures.append("disposable read-only worker must have write_scope none")
            if item.get("worktree_path"):
                failures.append("disposable read-only worker must not claim a worktree path")
            if item.get("cleanup_rule") != "archive_after_consumed" or item.get("archived") is not True:
                failures.append("disposable read-only worker must be archived after consumed")
            if item.get("pinned") is True:
                failures.append("disposable read-only worker must not be pinned")
        if thread_class == "isolated_worktree_worker":
            if item.get("write_scope") != "isolated_worktree_only" or not item.get("worktree_path"):
                failures.append("isolated worktree worker must write only in its worktree")
            if item.get("cleanup_rule") != "archive_after_adoption_or_rejection":
                failures.append("isolated worktree worker must archive after adoption/rejection")
            if item.get("worktree_path") == worktree.get("expected_main_worktree"):
                failures.append("isolated worktree worker must not use main worktree path")
        if thread_class == "reusable_research_thread":
            if item.get("write_scope") != "none":
                failures.append("reusable research thread must be read-only")
            if item.get("cleanup_rule") != "keep_reusable_until_research_captured":
                failures.append("reusable research thread cleanup rule mismatch")
            if item.get("output_status") in {"consumed", "adopted"} and not item.get("adopted_into"):
                failures.append("reusable research thread must be captured into durable note")
    if worktree.get("unintended_worker_worktrees_present") is not False:
        failures.append("unintended worker worktrees present")
    if worktree.get("stale_worker_checkout_present") is True:
        failures.append("stale worker checkout present")
    if boundary.get("completion_claim_allowed") is not False or boundary.get("objective_complete") is not False:
        failures.append("completion boundary permits completion")
    if qa.get("no_hidden_thread_truth") is not True:
        failures.append("qa.no_hidden_thread_truth must be true")
    if qa.get("no_completion_claim") is not True:
        failures.append("qa.no_completion_claim must be true")
    failures.extend(validate_second_level_dispatch_record(data))
    return failures


def validate_thread_dispatch_record_fixtures() -> None:
    valid = load_yaml(require_path("tests/fixtures/runtime/runs/thread-orchestration-cleanup-2026-06-06.yaml"))
    valid_failures = validate_thread_dispatch_record(valid)
    require(not valid_failures, f"valid thread dispatch record failed: {valid_failures}")
    invalids = {
        "tests/fixtures/invalid-thread-dispatch-worker-can-complete.yaml": "worker dispatch may mark goal complete",
        "tests/fixtures/invalid-thread-dispatch-same-directory-write.yaml": "disposable read-only worker must have write_scope none",
        "tests/fixtures/invalid-thread-dispatch-missing-professional-identity.yaml": "missing professional_identity",
        "tests/fixtures/invalid-thread-dispatch-over-default-budget-no-reason.yaml": "thread budget over max_active_workers requires over_budget_reason",
        "tests/fixtures/invalid-thread-dispatch-over-budget.yaml": "thread budget active_worker_count exceeds approval threshold",
        "tests/fixtures/invalid-thread-dispatch-second-level-completion.yaml": "second-level subagent may mark goal complete",
    }
    for path, expected in invalids.items():
        data = load_yaml(require_path(path))
        failures = validate_thread_dispatch_record(data)
        require(expected in failures, f"{path} did not fail for expected reason: {expected}; got {failures}")


def validate_workspace_cleanliness_protocol() -> None:
    doc = require_path("docs/film-preproduction/workspace-cleanliness-protocol.md").read_text(encoding="utf-8")
    root = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    thread_protocol = require_path("docs/film-preproduction/thread-orchestration-protocol.md").read_text(encoding="utf-8")
    validate_script = require_path("scripts/validate_project.py").read_text(encoding="utf-8")
    release_gate = require_path("scripts/dircreative_release_gate.py").read_text(encoding="utf-8")
    visual_dogfood = require_path("scripts/dircreative_visual_dogfood.py").read_text(encoding="utf-8")
    readiness = require_path("scripts/dircreative_readiness_audit.py").read_text(encoding="utf-8")
    combined = "\n".join([doc, root, thread_protocol, validate_script, release_gate, visual_dogfood, readiness])
    required_terms = [
        "Workspace Cleanliness Protocol",
        "git status --short",
        "git worktree list --porcelain",
        "user_owned_dirty",
        "task_owned_dirty",
        "generated_cache",
        "worker_residue",
        "PYTHONDONTWRITEBYTECODE",
        "__pycache__",
        "remove only task-owned",
        "Leave user-owned dirty files untouched",
        "git diff --check",
        "dircreative_thread_audit.py --dispatch-record",
        "sys.dont_write_bytecode = True",
        "env[\"PYTHONDONTWRITEBYTECODE\"] = \"1\"",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"workspace cleanliness protocol missing terms: {missing}")


def validate_runtime_state_governance() -> None:
    doc = require_path("docs/film-preproduction/runtime-state-governance.md").read_text(encoding="utf-8")
    schema = load_json(require_path("docs/film-preproduction/schemas/runtime-state.schema.json"))
    template = load_json(require_path("docs/film-preproduction/templates/runtime-state.template.json"))
    required_terms = [
        "V2 Persistence Policy",
        "Fast keeps the compact snapshot in memory",
        "Studio persists it only for a pause, cross-session resume, or multi-file output",
        "Delivery always persists it",
        "Standalone execution does not read ADCO documents",
        "Do not run the full state audit before every response",
        "completion claim",
        ".dircreative/state/current.json",
        "current_projection",
        "current.completion_requirements",
        "superseded_by_record_id",
        "tombstone",
        "acyclic chain",
        "Semantic migration",
        "source SHA-256",
        "cannot be declared `already_current`",
        "full UTF-8 JSON/YAML parse",
        "CURRENT_INTEGRITY: PASS | FAIL",
        "LEGACY_DEBT: NONE | PRESENT",
        "generated media without a current authorization record",
        "Verify real Codex task visibility",
        "--thread-snapshot",
        "diagnostic input, not a signed host attestation",
        "transformed records remain non-active",
        "self-written tombstone cannot authorize physical deletion",
        "no older than 24 hours",
        "regenerable_cache",
        "delete_candidate",
        "artifact_roots",
        "control_roots",
        "non-overlapping",
        "durable manifest JSON envelopes",
        "atomic no-clobber link",
        "Synthetic fixtures prove contracts only",
        "fixture_authority: none",
        "terminal reason",
        "Release and install packages retain only",
    ]
    missing = [term for term in required_terms if term not in doc]
    require(not missing, f"runtime state governance missing terms: {missing}")
    require(schema.get("properties", {}).get("schema_version", {}).get("const") == "1.0.0", "runtime schema must pin 1.0.0")
    require(template.get("schema_version") == "1.0.0", "runtime state template must use schema 1.0.0")
    require(template.get("storage_policy", {}).get("artifact_roots") == ["deliverables"], "runtime template must declare bounded artifact roots")
    require(template.get("storage_policy", {}).get("control_roots") == [".dircreative/runs"], "runtime template must declare bounded control roots")
    require(template.get("current", {}).get("completion_requirements", {}).get("acceptance_required") is False, "runtime template must type completion requirements")
    require(template.get("current", {}).get("state_kind") == "repository_baseline", "runtime template must identify repository baseline state")
    require(template.get("fixture_migration", {}).get("live_state_authority") is False, "runtime template fixture migration must have no live-state authority")
    require(set(template.get("storage_policy", {}).get("classes", {})) == {
        "final",
        "necessary_archive",
        "regenerable_cache",
        "delete_candidate",
    }, "runtime state template storage classes mismatch")

    self_test = run(["python3", "scripts/dircreative_state_audit.py", "self-test"])
    require(self_test.returncode == 0, f"runtime state self-test failed:\n{self_test.stderr}\n{self_test.stdout}")
    require("DIRCREATIVE_STATE_AUDIT_SELF_TEST=PASS" in self_test.stdout, "runtime state self-test missing PASS marker")

    builtin_env = os.environ.copy()
    builtin_env["PYTHONDONTWRITEBYTECODE"] = "1"
    builtin_env["DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"] = "1"
    builtin_self_test = subprocess.run(
        ["python3", "scripts/dircreative_state_audit.py", "self-test"],
        cwd=ROOT,
        env=builtin_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(
        builtin_self_test.returncode == 0,
        "runtime state builtin-validator self-test failed:\n"
        + builtin_self_test.stderr
        + "\n"
        + builtin_self_test.stdout,
    )
    require(
        "DIRCREATIVE_STATE_AUDIT_SELF_TEST=PASS" in builtin_self_test.stdout,
        "runtime state builtin-validator self-test missing PASS marker",
    )

    installed_package_layout = (ROOT / "SKILL.md").exists() and not (ROOT / ".git").exists()
    if installed_package_layout:
        from dircreative_package_layout import PACKAGE_RUNTIME_FILES

        installed_runtime = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / ".dircreative").rglob("*")
            if path.is_file()
        )
        require(
            installed_runtime == sorted(PACKAGE_RUNTIME_FILES),
            "installed package runtime must contain only lifecycle sentinels: "
            + ", ".join(installed_runtime),
        )
    else:
        current_audit = run(["python3", "scripts/dircreative_state_audit.py", "audit", "--json"])
        require(current_audit.returncode == 0, f"current runtime audit failed:\n{current_audit.stderr}\n{current_audit.stdout}")
        current_report = json.loads(current_audit.stdout)
        require(current_report.get("current_integrity") == "PASS", "current runtime state must pass current integrity")
        require(current_report.get("legacy_debt") == "NONE", "migrated live runtime must have no legacy debt")
        require(current_report.get("findings") == [], "current runtime audit must not publish fixture debt as current findings")

    no_authority = {
        "fixture_authority": "none",
        "live_state_authority": False,
        "live_acceptance_authority": False,
        "host_attestation_authority": False,
    }
    for fixture_path in sorted((ROOT / "tests/fixtures/runtime/runs").glob("*.yaml")):
        fixture = load_yaml(fixture_path)
        require(
            all(fixture.get(key) == value for key, value in no_authority.items()),
            f"runtime fixture claims live authority: {rel(fixture_path)}",
        )
    for history_path in sorted((ROOT / "tests/fixtures/runtime/history").glob("*.jsonl")):
        for line_number, line in enumerate(history_path.read_text(encoding="utf-8").splitlines(), start=1):
            entry = json.loads(line)
            require(
                all(entry.get(key) == value for key, value in no_authority.items()),
                f"runtime history fixture claims live authority: {rel(history_path)}:{line_number}",
            )

    migration = run(["python3", "scripts/dircreative_state_audit.py", "migration-plan"])
    require(migration.returncode == 0, f"runtime migration plan failed:\n{migration.stderr}\n{migration.stdout}")
    require("MIGRATION_WRITE_ALLOWED: false_without_explicit_mapping" in migration.stdout, "migration plan must fail closed on write")


def validate_objective_requirement_audit_receipt() -> None:
    path = "tests/fixtures/runtime/runs/objective-requirement-audit-2026-06-06.yaml"
    receipt = load_yaml(require_path(path))
    text = require_path(path).read_text(encoding="utf-8")
    run = receipt.get("run", {})
    standard = run.get("authoritative_completion_standard", {})
    matrix = run.get("requirement_matrix", [])
    qa = receipt.get("qa", {})
    skill_receipt = receipt.get("skill_run_receipt", {})

    required_terms = [
        "Full active DIRcreative Goal objective, not a narrowed technical-readiness subtask.",
        "OBJECTIVE_COMPLETE: NO",
        "completion_claim_allowed: false",
        "real_user_acceptance_missing",
        ".dircreative/runs/live-user-acceptance.yaml is absent",
        "Correct the previous premature Goal completion behavior.",
        "Clean failed or duplicate Codex worker threads used for this DIRcreative run.",
        "Define thread role, pinning, disposable, reusable, and cleanup rules in the skill.",
        "Review production demo failures and mature the skill before more demo generation.",
        "Use council adversarial review from user, film expert, product manager, skill developer, and code researcher viewpoints.",
        "scripts/dircreative_council_audit.py",
        "docs/film-preproduction/research/ai-video-prompt-community-lessons.md",
        "Improve prompt and storyboard structure, including material choice, character design, camera, paths, and professional shot-card text.",
        "Do not mark complete unless objective audit reports OBJECTIVE_COMPLETE: YES or real user acceptance is completed.",
    ]
    missing = [term for term in required_terms if term not in text]
    require(not missing, f"{path} missing objective audit terms: {missing}")

    require(run.get("run_type") == "requirement_by_requirement_goal_audit", "objective requirement audit must be requirement-by-requirement")
    require(standard.get("requires_live_acceptance_receipt") is True, "objective audit receipt must require live acceptance")
    require(standard.get("current_result") == "OBJECTIVE_COMPLETE: NO", "objective audit receipt must preserve OBJECTIVE_COMPLETE: NO")
    require(standard.get("completion_claim_allowed") is False, "objective audit receipt must forbid completion claim")
    require(len(matrix) >= 8, "objective audit receipt must cover the major Goal requirements")
    require(qa.get("live_user_acceptance_receipt_exists") is False, "objective audit receipt must show live acceptance is absent")
    require(qa.get("objective_complete_expected") is False, "objective audit receipt must expect objective incomplete")
    require(qa.get("goal_should_remain_active") is True, "objective audit receipt must keep goal active")
    require(skill_receipt.get("qa_gate", {}).get("status") == "needs_user", "objective audit skill receipt must need user")


def validate_release_gate_technical_readiness_receipt() -> None:
    path = "tests/fixtures/runtime/runs/release-gate-technical-readiness-2026-06-06.yaml"
    receipt = load_yaml(require_path(path))
    text = require_path(path).read_text(encoding="utf-8")
    run = receipt.get("run", {})
    boundary = run.get("completion_boundary", {})
    qa = receipt.get("qa", {})
    skill_receipt = receipt.get("skill_run_receipt", {})
    required_terms = [
        "release_gate_technical_readiness",
        "RELEASE_GATE: PASS",
        "GOAL_COMPLETE: NO",
        "OBJECTIVE_COMPLETE: NO",
        "live_receipt_absent: true",
        "receipt_creation_allowed: false",
        "completion_claim_allowed: false",
        "council_audit: pass",
        "scripts/dircreative_council_audit.py",
        "real_user_acceptance_missing",
        "Release gate passed, but objective completion remains blocked by missing real user acceptance.",
    ]
    missing = [term for term in required_terms if term not in text]
    require(not missing, f"{path} missing release gate receipt terms: {missing}")
    require(run.get("result") == "RELEASE_GATE: PASS", "release gate receipt must record PASS")
    require(boundary.get("goal_completion_audit") == "GOAL_COMPLETE: NO", "release gate receipt must keep GOAL_COMPLETE: NO")
    require(boundary.get("objective_completion_audit") == "OBJECTIVE_COMPLETE: NO", "release gate receipt must keep OBJECTIVE_COMPLETE: NO")
    require(boundary.get("live_receipt_absent") is True, "release gate receipt must show live receipt absent")
    require(boundary.get("completion_claim_allowed") is False, "release gate receipt must forbid completion claim")
    require(qa.get("release_gate_passed") is True, "release gate receipt must show release gate passed")
    require(run.get("technical_readiness", {}).get("council_audit") == "pass", "release gate receipt must show council audit passed")
    require(qa.get("objective_complete") is False, "release gate receipt must show objective incomplete")
    require(qa.get("goal_should_remain_active") is True, "release gate receipt must keep goal active")
    require(skill_receipt.get("qa_gate", {}).get("status") == "needs_user", "release gate skill receipt must need user")


def validate_director_room_fixture() -> None:
    legacy_roles = {
        "producer",
        "creative_director",
        "director",
        "screenwriter",
        "cinematographer",
        "production_designer",
        "editor",
        "sound_designer",
        "model_prompt_engineer",
        "continuity_qa",
    }
    fixture_paths = [
        "examples/product-ad-raincoat/02-director-room-notes.md",
        "examples/zombie-cleaner-test/02-director-room-notes.md",
        "examples/live-user-sim-noodle/02-director-room-notes.md",
        "examples/complete-idea-segmentation-test/02-director-room-notes.md",
    ]
    for fixture_path in fixture_paths:
        text = require_path(fixture_path).read_text(encoding="utf-8")
        require(
            legacy_roles.issubset({role for role in legacy_roles if role in text}),
            f"{fixture_path} is no longer readable as a legacy v1 director-room fixture",
        )

    harness = load_yaml(require_path("docs/film-preproduction/schemas/director-role-harness.yaml"))[
        "director_role_harness"
    ]
    require(harness.get("schema_version") == "2.0.0", "Director Room must default to harness v2")
    require(
        set(harness.get("perspectives", {}))
        == {"narrative_strategy", "visual_production", "model_continuity"},
        "Director Room v2 perspective set drifted",
    )
    require(
        set(harness.get("legacy_v1_role_contracts", {})) == legacy_roles,
        "Director Room v1 role contracts are not preserved read-only",
    )
    output = harness.get("v2_output_contract", {})
    require(output.get("minimum_disagreements") == 0, "Director Room still forces disagreements")
    require(output.get("user_visible_role_cards") is False, "Director Room still exposes fixed role cards")
    proc = run(["python3", "scripts/dircreative_director_harness_audit.py"])
    require(proc.returncode == 0, f"adaptive Director Room audit failed:\n{proc.stderr}\n{proc.stdout}")
    for term in [
        "fast_director_room_bypasses: 4/4",
        "maximum_perspectives: 3",
        "minimum_disagreements: 0",
        "user_visible_role_cards: false",
        "legacy_v1_fixtures_read: 12/12",
        "DIRECTOR_HARNESS_AUDIT: PASS",
    ]:
        require(term in proc.stdout, f"adaptive Director Room audit missing: {term}")


def validate_ad_reference_pack_fixtures() -> None:
    ad_paths = [
        "examples/product-ad-raincoat/07-reference-pack-plan.yaml",
        "examples/live-user-sim-noodle/09-reference-pack-plan.yaml",
    ]
    for path in ad_paths:
        text = require_path(path).read_text(encoding="utf-8").lower()
        required_terms = [
            "style_material_board",
            "lighting",
            "material",
            "style",
            "identity_product_board",
            "storyboard_motion_board",
            "clean_first_frame",
        ]
        missing = [term for term in required_terms if term not in text]
        require(not missing, f"{path} missing forced ad reference pack terms: {missing}")


def validate_workbench_docs() -> None:
    docs = [
        require_path("docs/film-preproduction/workbench-product-spec.md"),
        require_path("docs/film-preproduction/workbench-data-flow.md"),
        require_path("docs/film-preproduction/workbench-interface-plan.md"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in docs)
    required_terms = [
        "cyber-courier",
        "rainlock",
        "artifact",
        "skill_run_receipt",
        "provenance",
        "lock",
        "regeneration",
        "seedance",
        "kling",
        "runway",
        "veo",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"workbench docs missing required planning terms: {missing}")


def validate_chat_interface() -> None:
    docs = [
        require_path("docs/film-preproduction/chat-co-creation-interface.md"),
        require_path("docs/film-preproduction/live-chat-start-protocol.md"),
        require_path("docs/film-preproduction/isolated-user-simulation-protocol.md"),
        require_path("docs/film-preproduction/goal-mode-simulation-protocol.md"),
        require_path("examples/live-user-sim-noodle/16-chat-interface-demo.md"),
        require_path("examples/goal-mode-simulation-test/01-chat-transcript.md"),
        require_path("examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md"),
        require_path("examples/live-user-sim-noodle/12-qa-retry-plan.md"),
        require_path("examples/live-user-sim-noodle/17-ad-reference-pack-repair.md"),
        require_path("skills/dircreative/chat-facilitator/SKILL.md"),
        require_path("skills/dircreative/SKILL.md"),
        require_path("skills/dircreative/reference-image-planner/SKILL.md"),
        require_path("skills/dircreative/image-prompt-compiler/SKILL.md"),
        require_path("docs/film-preproduction/ad-reference-pack-generation-gate.md"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in docs)
    required_terms = [
        "chat-first",
        "artifact-backed",
        "useful artifact",
        "first response",
        "continue",
        "reuse",
        "concept_lock",
        "generation_authorization",
        "client_delivery_approval",
        "story_state",
        "script_state",
        "shot_state",
        "visual_state",
        "reference_state",
        "prompt_state",
        "qa_state",
        "用户确认点",
        "模拟用户选择",
        "prompt-only",
        "当前没有生成真实图片或视频",
        "do not dump raw yaml",
        "legacy v1",
        "read-only",
        "goal mode simulation",
        "post-generation self-qa",
        "stale",
    ]
    missing = [term for term in required_terms if term.lower() not in combined]
    require(not missing, f"chat interface docs missing required terms: {missing}")


def validate_chat_visualization_contract() -> None:
    interface = require_path("docs/film-preproduction/chat-inline-visualization-interface.md").read_text(encoding="utf-8")
    root_skill = require_path("skills/dircreative/SKILL.md").read_text(encoding="utf-8")
    adco = require_path("docs/film-preproduction/adco-integration-contract.md").read_text(encoding="utf-8")
    schema = require_path("docs/film-preproduction/schemas/chat-visualization-spec.schema.json").read_text(encoding="utf-8")
    writeback_schema = require_path("docs/film-preproduction/schemas/chat-visualization-writeback.schema.json").read_text(encoding="utf-8")
    combined = f"{interface}\n{root_skill}\n{adco}\n{schema}\n{writeback_schema}"
    required_terms = [
        "dircreative.chat-visualization@1.0",
        "one primary action",
        "at most one secondary action",
        "preview_only",
        "writes_authoritative_state",
        "Markdown/table/Mermaid fallback",
        "controller.user_facing: false",
        "write_boundary.write_owner: ad-creative-orchestrator",
        "optional presentation capability",
        "dircreative.chat-visualization-writeback@1.0",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"chat visualization contract missing terms: {missing}")

    visual_skills = [
        "chat-facilitator",
        "co-creation-gate-runtime",
        "story-development",
        "script-treatment",
        "shot-design",
        "visual-bible",
        "reference-image-planner",
        "image-prompt-compiler",
        "video-model-adapter",
        "generation-qa",
        "checkpoint",
    ]
    for skill_id in visual_skills:
        skill_text = require_path(f"skills/dircreative/{skill_id}/SKILL.md").read_text(encoding="utf-8")
        require(
            "chat-inline-visualization-interface.md" in skill_text,
            f"visual skill {skill_id} missing interface contract",
        )
        require(
            "stage-surface-registry.json#" in skill_text,
            f"visual skill {skill_id} missing stage surface registry entry",
        )

    template_proc = run(
        [
            "python3",
            "scripts/dircreative_visualization_spec.py",
            "validate",
            "docs/film-preproduction/schemas/chat-visualization-spec.template.yaml",
        ]
    )
    require(
        template_proc.returncode == 0,
        f"chat visualization template validation failed:\n{template_proc.stderr}\n{template_proc.stdout}",
    )
    audit_proc = run(["python3", "scripts/dircreative_visualization_audit.py"])
    require(
        audit_proc.returncode == 0,
        f"chat visualization audit failed:\n{audit_proc.stderr}\n{audit_proc.stdout}",
    )
    render_proc = run(["python3", "scripts/dircreative_visualization_render.py", "self-test"])
    require(
        render_proc.returncode == 0,
        f"chat visualization render self-test failed:\n{render_proc.stderr}\n{render_proc.stdout}",
    )
    writeback_proc = run(["python3", "scripts/dircreative_visualization_writeback.py", "self-test"])
    require(
        writeback_proc.returncode == 0,
        f"chat visualization writeback self-test failed:\n{writeback_proc.stderr}\n{writeback_proc.stdout}",
    )
    adco_projection_proc = run(["python3", "scripts/dircreative_visualization_adco_audit.py", "--self-test"])
    require(
        adco_projection_proc.returncode == 0,
        f"ADCO visualization projection self-test failed:\n{adco_projection_proc.stderr}\n{adco_projection_proc.stdout}",
    )
    dogfood_proc = run(["python3", "scripts/dircreative_visualization_dogfood.py"])
    require(
        dogfood_proc.returncode == 0,
        f"chat visualization dogfood generation failed:\n{dogfood_proc.stderr}\n{dogfood_proc.stdout}",
    )
    if os.environ.get("DIRCREATIVE_REQUIRE_BROWSER_VISUAL_AUDIT") == "1":
        browser_proc = run(["node", "scripts/dircreative_visualization_browser_audit.cjs"])
        require(
            browser_proc.returncode == 0,
            f"chat visualization browser audit failed:\n{browser_proc.stderr}\n{browser_proc.stdout}",
        )


def validate_chat_acceptance_checklist() -> None:
    text = require_path("docs/film-preproduction/chat-acceptance-checklist.md").read_text(encoding="utf-8").lower()
    required_terms = [
        "earliest unresolved gate",
        "live-chat-start-protocol",
        "story, script, shot, and visual bible gates",
        "one user decision at a time",
        "professional film language",
        "complete user idea",
        "complete-idea scenario requirement",
        "shot count is dynamic",
        "story duration",
        "generation-unit limit",
        "5-15s sequence units",
        "reference image count is dynamic",
        "dense storyboard boards",
        "clean frames",
        "pre-generation contract",
        "prompt-only mode",
        "simulated fixture decisions",
        "goal mode simulation",
        "阶段: 模拟测试结论",
        "separate from live acceptance",
        "qa and retry rules",
        "self-qa",
        "failure ids",
        "smallest-artifact retry route",
        "阶段: 中途改需求处理",
        "stale",
        "revision-scope question",
    ]
    missing = [term for term in required_terms if term.lower() not in text]
    require(not missing, f"chat acceptance checklist missing terms: {missing}")


def validate_goal_mode_simulation_protocol() -> None:
    sources = [
        "docs/film-preproduction/goal-mode-simulation-protocol.md",
        "docs/film-preproduction/chat-co-creation-interface.md",
        "docs/film-preproduction/live-chat-start-protocol.md",
        "docs/film-preproduction/04-goal-mode-handoff.md",
        "skills/dircreative/SKILL.md",
        "skills/dircreative/chat-facilitator/SKILL.md",
        "examples/goal-mode-simulation-test/01-chat-transcript.md",
        "examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md",
    ]
    combined = "\n".join(require_path(path).read_text(encoding="utf-8") for path in sources)
    required_terms = [
        "Goal Mode Simulation Protocol",
        "goal_context",
        "目标模式状态下我不会给你发1",
        "阶段: 目标模式模拟测试",
        "用户确认点",
        "模拟用户选择",
        "阶段: 模拟测试结论",
        "simulate user normal operation",
        "simulated_fixture",
        "real_user_co_creation_verified: true",
        "live-user-acceptance.yaml",
        "do not wait for `1`",
        "不生成真实图片或视频",
        "不计入真实验收",
        "阶段: 想法读取",
                "阶段: 出图执行建议",
        "阶段: 视频生成建议",
        "rough-idea path",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"goal-mode simulation protocol missing terms: {missing}")


def validate_isolated_user_simulation() -> None:
    protocol = require_path("docs/film-preproduction/isolated-user-simulation-protocol.md").read_text(encoding="utf-8")
    pack_path = require_path("examples/isolated-user-simulation-test/01-simulation-pack.yaml")
    pack_text = pack_path.read_text(encoding="utf-8")
    pack = load_yaml(pack_path)
    root = pack.get("simulation_pack", {})
    scenarios = root.get("scenarios", [])
    scenario_types = {scenario.get("test_type") for scenario in scenarios}
    required_types = {
        "rough_idea",
        "complete_idea",
        "longform_request",
        "image_request",
        "midstream_change",
    }
    require(root.get("run_type") == "isolated_simulation_fixture", "isolated simulation must be fixture-only")
    require(root.get("real_user_co_creation_verified") is False, "isolated simulation cannot verify real user co-creation")
    require(root.get("live_user_acceptance_receipt_written") is False, "isolated simulation cannot write live acceptance receipt")
    require(root.get("real_media_generated") is False, "isolated simulation cannot generate real media")
    require(root.get("scoring_hidden_from_dircreative") is True, "isolated simulation must hide scoring from DIRcreative")
    require(root.get("standard_answer_hidden_from_dircreative") is True, "isolated simulation must hide standard answers from DIRcreative")
    require(required_types <= scenario_types, f"isolated simulation missing scenario types: {sorted(required_types - scenario_types)}")

    combined = protocol + "\n" + pack_text
    required_terms = [
        "simulated_user",
        "dircreative",
        "independent_reviewer",
        "rough_idea",
        "complete_idea",
        "longform_request",
        "image_request",
        "midstream_change",
        "阶段: 中途改需求处理",
        "stale",
        "repair_required: true",
        "simulated_feedback_is_real_acceptance: false",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"isolated simulation artifacts missing terms: {missing}")

    proc = run(["python3", "scripts/dircreative_isolated_user_sim.py"])
    require(proc.returncode == 0, f"isolated user simulation failed:\n{proc.stderr}\n{proc.stdout}")
    output_terms = [
        "DIRcreative Isolated User Simulation",
        "rough_idea",
        "complete_idea",
        "longform_request",
        "image_request",
        "midstream_change",
        "real_user_co_creation_verified: false",
        "real_media_generated: false",
        "ISOLATED_USER_SIMULATION: PASS",
    ]
    missing_output = [term for term in output_terms if term not in proc.stdout]
    require(not missing_output, f"isolated user simulation output missing terms: {missing_output}")


def validate_complete_idea_segmentation_test() -> None:
    transcript = require_path("examples/complete-idea-segmentation-test/02-chat-transcript.md").read_text(encoding="utf-8")
    prompt_plan = require_path("examples/complete-idea-segmentation-test/04-reference-prompt-plan.md").read_text(encoding="utf-8")
    qa_plan = require_path("examples/complete-idea-segmentation-test/05-qa-retry-plan.md").read_text(encoding="utf-8")
    combined = f"{transcript}\n{prompt_plan}\n{qa_plan}"
    required_terms = [
        "完整想法读取",
        "不进入创意发散",
        "阶段: 导演组会议",
        "producer",
        "creative_director",
        "director",
        "screenwriter",
        "cinematographer",
        "production_designer",
        "editor",
        "sound_designer",
        "model_prompt_engineer",
        "continuity_qa",
        "导演组分歧",
        "完整想法执行",
        "专业判断",
        "取舍",
        "执行影响",
        "6 镜头",
        "叙事任务",
        "机位/镜头",
        "主体调度",
        "构图层次",
        "声音剪辑",
        "模型风险",
        "参考图组",
        "V2 sequential",
        "阶段: 出图执行建议",
        "character identity reference",
        "scene geography + camera FOV reference",
        "professional storyboard + motion map",
        "Character consistency",
        "scene consistency",
        "pre_generation_contract",
        "dominant_title",
        "Largest title on the page",
        "Smaller metadata only",
        "Do not make FOG ROUTE CLEANER the largest title",
        "出图执行建议",
        "Seedance",
        "Kling",
        "Runway",
        "Veo",
        "当前没有生成真实图片或视频",
        "clean_frame_gate",
        "media_generation",
        "QA 与重试规则",
        "Pre-Generation QA",
        "Post-Generation Self-QA",
        "Retry Routing",
        "self-QA",
        "smallest artifact",
        "Do not ask the user to lock a failed candidate",
        "character_identity_reference_drift",
        "scene_geography_reference_drift",
        "reference_role_label_hierarchy_wrong",
        "storyboard_information_density_too_low",
        "fish_scale_material_artifact",
        "board_used_as_direct_i2v_input_when_forbidden",
        "copied_video_prompt_across_models",
        "missing_audio_policy",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"complete idea segmentation chat fixture missing terms: {missing}")

    shot_data = load_yaml(require_path("examples/complete-idea-segmentation-test/03-shot-list.yaml"))
    shots = shot_items(shot_data)
    require(len(shots) == 6, "complete idea segmentation fixture must prove dynamic six-shot segmentation")
    rationale = shot_data.get("shot_list", {}).get("shot_count_rationale", "")
    require("Three shots would overload" in rationale, "complete idea fixture missing shot count rationale")

    run_data = load_yaml(require_path("examples/complete-idea-segmentation-test/15-co-creation-run.yaml"))
    gates = run_data.get("gates", [])
    concept_gate = next((gate for gate in gates if gate.get("gate_type") == "concept_options_gate"), {})
    clean_gate = next((gate for gate in gates if gate.get("gate_type") == "clean_frame_gate"), {})
    require(concept_gate.get("status") == "skipped_with_risk", "complete idea fixture must skip concept gate with visible risk")
    require("complete idea" in concept_gate.get("rationale", "").lower(), "complete idea concept skip needs rationale")
    require(clean_gate.get("status") == "pending", "complete idea fixture must leave clean frame gate pending")
    require("media_generation" in clean_gate.get("blocks", []), "complete idea clean frame gate must block media generation")


def validate_assisted_generation_receipt() -> None:
    path = "tests/fixtures/runtime/runs/fog-route-cleaner-assisted-generation.yaml"
    data = load_yaml(require_path(path))
    artifact = data.get("artifact", {})
    require(artifact.get("status") == "needs_revision", f"{path} must record current generated assets as needs_revision")
    run_data = data.get("run", {})
    require(run_data.get("authorization_source") == "real_user", f"{path} must record real user authorization")
    require(run_data.get("visual_output_mode") == "assisted_generation", f"{path} must record assisted_generation mode")
    require(run_data.get("video_generated") is False, f"{path} must not claim video generation")
    require(run_data.get("user_lock_required_before_video") is True, f"{path} must require user lock before video")

    human_review = data.get("human_review", {})
    require(human_review.get("verdict") == "reject_for_revision", f"{path} must record user rejection for revision")
    required_failures = {
        "character_identity_reference_drift",
        "reference_asset_role_label_missing",
        "storyboard_information_density_too_low",
    }
    failures = set(human_review.get("failure_ids", []))
    require(required_failures.issubset(failures), f"{path} missing human review failures: {sorted(required_failures - failures)}")

    v2 = data.get("v2_regeneration_strategy", {})
    require(v2.get("mode") == "sequential_gated_assisted_generation", f"{path} must require sequential gated V2 regeneration")
    require(v2.get("lock_order") == [
        "character_identity_lock",
        "scene_geography_camera_fov_lock",
        "professional_storyboard_motion_page_lock",
        "selected_clean_frame_generation",
    ], f"{path} V2 lock order is wrong")
    v2_assets = v2.get("required_core_assets", [])
    v2_roles = {asset.get("role") for asset in v2_assets}
    require(
        {"character_identity_reference", "scene_geography_camera_fov_reference", "professional_storyboard_motion_map"}.issubset(v2_roles),
        f"{path} V2 core assets missing required roles",
    )
    storyboard_asset = next((asset for asset in v2_assets if asset.get("role") == "professional_storyboard_motion_map"), {})
    required_storyboard_fields = {
        "shot_id",
        "timecode",
        "duration",
        "shot_image_region",
        "detailed_frame_description",
        "shot_size",
        "focal_length",
        "camera_position",
        "camera_movement_start_end",
        "subject_blocking_start_end",
        "foreground_midground_background",
        "lighting_cue",
        "sound_description",
        "transition",
        "model_risk",
    }
    storyboard_fields = set(storyboard_asset.get("per_shot_cell_required_fields", []))
    require(required_storyboard_fields.issubset(storyboard_fields), f"{path} V2 storyboard page missing fields: {sorted(required_storyboard_fields - storyboard_fields)}")
    consistency_rules = v2.get("consistency_rules", {})
    for key in [
        "character_consistency_required",
        "scene_consistency_required",
        "duplicate_visual_truth_forbidden",
        "repeated_content_must_inherit_locked_source",
        "asset_role_label_must_be_dominant_title",
    ]:
        require(consistency_rules.get(key) is True, f"{path} V2 consistency rule missing or false: {key}")
    require(consistency_rules.get("batch_generate_all_assets_before_locks") is False, f"{path} V2 must forbid batch generation before locks")

    trial_attempts = data.get("v2_trial_attempts", [])
    require(trial_attempts, f"{path} must record V2 trial attempts")
    hierarchy_attempt = next((attempt for attempt in trial_attempts if "reference_role_label_hierarchy_wrong" in attempt.get("failure_ids", [])), {})
    require(hierarchy_attempt, f"{path} must record role-label hierarchy rejection")
    require(hierarchy_attempt.get("status") == "rejected_for_revision", f"{path} hierarchy attempt must be rejected")
    require("image_generation_called_without_pre_generation_contract" in hierarchy_attempt.get("failure_ids", []), f"{path} hierarchy attempt must record missing pre-generation contract")
    pre_contract = hierarchy_attempt.get("pre_generation_contract", {})
    require(pre_contract.get("status") == "fail", f"{path} hierarchy attempt pre-generation contract must fail")
    require(pre_contract.get("existed_before_generation") is False, f"{path} must record that pre-generation contract was missing before generation")
    require(pre_contract.get("image_generation_allowed") is False, f"{path} missing contract must forbid image generation")
    require(pre_contract.get("required_before_retry") is True, f"{path} retry must require pre-generation contract")
    missing_or_failed = set(pre_contract.get("missing_or_failed_checks", []))
    required_missing = {
        "dominant_title",
        "secondary_project_metadata",
        "title_hierarchy.role_label_largest",
        "title_hierarchy.project_title_secondary",
        "title_hierarchy.forbidden_largest_text",
        "prompt_lint.forbidden_poster_hierarchy_present",
    }
    require(required_missing.issubset(missing_or_failed), f"{path} missing pre-generation failed checks: {sorted(required_missing - missing_or_failed)}")
    attempt_file = Path(hierarchy_attempt.get("generated_file", ""))
    require(attempt_file.is_absolute(), f"{path} hierarchy attempt generated_file must be an absolute path")
    if not attempt_file.exists():
        require(
            hierarchy_attempt.get("generated_file_availability") == "external_generated_image_missing_ok",
            f"{path} hierarchy attempt file does not exist",
        )

    assets = data.get("assets", [])
    require(len(assets) == 6, f"{path} must register exactly six assets")
    roles = {asset.get("role") for asset in assets}
    required_roles = {
        "identity_equipment_board",
        "environment_geography_board",
        "lighting_material_style_board",
        "storyboard_motion_board",
        "clean_first_frame",
        "clean_end_frame",
    }
    require(required_roles == roles, f"{path} asset roles mismatch: {sorted(required_roles - roles)}")

    dense_roles = {
        "identity_equipment_board",
        "environment_geography_board",
        "lighting_material_style_board",
        "storyboard_motion_board",
    }
    direct_roles = {"clean_first_frame", "clean_end_frame"}
    for asset in assets:
        asset_id = asset.get("asset_id", "unknown")
        role = asset.get("role")
        file_path = Path(asset.get("file_path", ""))
        require(file_path.is_absolute(), f"{path} asset {asset_id} file_path must be absolute")
        if not file_path.exists():
            require(
                asset.get("file_availability") == "external_generated_image_missing_ok",
                f"{path} asset {asset_id} file does not exist: {file_path}",
            )
        require(asset.get("user_lock_status") == "rejected_for_revision", f"{path} asset {asset_id} must be rejected for revision")
        require(asset.get("usable_for_next_step") is False, f"{path} asset {asset_id} must be blocked from next step")
        require(asset.get("rejection_reasons"), f"{path} asset {asset_id} must record rejection reasons")
        require(asset.get("prompt_source") == "examples/complete-idea-segmentation-test/04-reference-prompt-plan.md", f"{path} asset {asset_id} prompt source mismatch")
        if role in dense_roles:
            require(asset.get("direct_video_input") is False, f"{path} dense asset {asset_id} must not be direct video input")
            require(asset.get("forbidden_use"), f"{path} dense asset {asset_id} missing forbidden use")
            require(asset.get("role_label_required_in_image"), f"{path} dense asset {asset_id} missing required role label")
        if role in direct_roles:
            require(asset.get("direct_video_input") is True, f"{path} clean asset {asset_id} must be direct video input")
            require(asset.get("shot_id") in {"FRC01", "FRC06"}, f"{path} clean asset {asset_id} missing shot id")
            require(asset.get("role_label_required_in_manifest"), f"{path} clean asset {asset_id} missing manifest role label")

    handoff = data.get("model_handoff", {})
    for model in ["seedance", "kling", "runway", "veo"]:
        require(handoff.get(model, {}).get("anti_misread_required") is True, f"{path} model {model} must require anti-misread")
        require(handoff.get(model, {}).get("recommended_mode"), f"{path} model {model} missing recommended mode")
        require(handoff.get(model, {}).get("blocked_by_human_review") is True, f"{path} model {model} must be blocked by human review")
    require("frc_ref_04_storyboard_motion_board" in handoff.get("kling", {}).get("forbidden_primary_assets", []), f"{path} must forbid storyboard board as Kling primary asset")

    qa = data.get("qa", {})
    validate_generation_qa_consistency(path, data)
    for key in [
        "image_generation_authorized",
        "real_files_exist",
        "asset_count_is_six",
        "dense_boards_not_direct_i2v",
        "clean_frames_direct_i2v",
        "video_generation_blocked_until_user_lock",
        "no_video_generated",
        "no_media_copied_into_examples",
        "user_review_required",
    ]:
        require(qa.get(key) is True, f"{path} QA missing or false: {key}")
    for key in ["approved_for_video_prompt_test", "character_consistency_passed", "role_labels_passed", "storyboard_density_passed"]:
        require(qa.get(key) is False, f"{path} QA should fail current candidate: {key}")
    require(required_failures.issubset(set(qa.get("failures", []))), f"{path} QA missing failures: {sorted(required_failures - set(qa.get('failures', [])))}")

    receipt = data.get("skill_run_receipt", {})
    require(receipt.get("skill_id") == "generation-qa", f"{path} receipt must name generation-qa")
    require(receipt.get("qa_gate", {}).get("status") == "fail", f"{path} receipt should fail current generated candidates")
    require(receipt.get("next_recommended_skill") == "reference-image-planner", f"{path} should route back to reference-image-planner")


def validate_generation_qa_consistency(path: str, data: dict[str, Any]) -> None:
    qa = data.get("qa", {})
    receipt = data.get("skill_run_receipt", {})
    failures = set(qa.get("failures", [])) | set(data.get("human_review", {}).get("failure_ids", []))
    drift_failures = {"character_identity_reference_drift", "scene_geography_reference_drift", "continuity_drift"}
    if failures & drift_failures:
        require(qa.get("approved_for_video_prompt_test") is False, f"{path} drift failures must block video prompt approval")
        require(receipt.get("qa_gate", {}).get("status") == "fail", f"{path} drift failures must fail generation QA")
        require(receipt.get("next_recommended_skill") == "reference-image-planner", f"{path} drift failures must route back to reference-image-planner")
    if "character_identity_reference_drift" in failures:
        require(qa.get("character_consistency_passed") is False, f"{path} character drift must set character_consistency_passed false")
    if "scene_geography_reference_drift" in failures and "scene_consistency_passed" in qa:
        require(qa.get("scene_consistency_passed") is False, f"{path} scene drift must set scene_consistency_passed false")
    if data.get("run", {}).get("video_generated") is False:
        require(qa.get("no_video_generated") is True, f"{path} must confirm no_video_generated when run.video_generated is false")


def validate_generation_qa_character_drift_approved_fixture() -> None:
    path = "tests/fixtures/invalid-generation-qa-character-drift-approved.yaml"
    data = load_yaml(require_path(path))
    try:
        validate_generation_qa_consistency(path, data)
    except ValidationError as exc:
        require(
            "drift failures must block video prompt approval" in str(exc)
            or "character drift must set character_consistency_passed false" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject approved generation QA with character drift")


def validate_pre_generation_contract_negative_fixture() -> None:
    path = "tests/fixtures/invalid-assisted-image-manifest-missing-contract.yaml"
    try:
        validate_image_manifest(path, registry_pattern_ids())
    except ValidationError as exc:
        require(
            "pre_generation_contract" in str(exc) or "pre-generation contract" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject assisted image generation without pre_generation_contract")


def validate_pre_generation_contract_weak_fixture() -> None:
    path = "tests/fixtures/invalid-assisted-image-manifest-weak-contract.yaml"
    try:
        validate_image_manifest(path, registry_pattern_ids())
    except ValidationError as exc:
        require(
            "dominant_title" in str(exc) or "title_hierarchy" in str(exc) or "pre-generation contract" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject weak pre_generation_contract")


def validate_pre_generation_contract_prompt_mismatch_fixture() -> None:
    path = "tests/fixtures/invalid-assisted-image-manifest-contract-prompt-mismatch.yaml"
    try:
        validate_image_manifest(path, registry_pattern_ids())
    except ValidationError as exc:
        require(
            ("prompt" in str(exc) and "dominant_title" in str(exc)) or "pre-generation contract" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject prompts that omit pre_generation_contract title instructions")


def validate_pre_generation_contract_project_title_dominant_fixture() -> None:
    path = "tests/fixtures/invalid-assisted-image-manifest-project-title-as-dominant.yaml"
    try:
        validate_image_manifest(path, registry_pattern_ids())
    except ValidationError as exc:
        require(
            "dominant_title must be the reference role label" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject project title as dominant title")


def validate_image_generation_capability_negative_fixture() -> None:
    path = "tests/fixtures/invalid-image-manifest-generated-without-capability.yaml"
    try:
        validate_image_manifest(path, registry_pattern_ids())
    except ValidationError as exc:
        require(
            "requires assisted_generation mode" in str(exc)
            or "requires image generation capability and user authorization" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject generated image claims without generation capability")


def validate_image_prompt_audio_leak_negative_fixture() -> None:
    path = "tests/fixtures/invalid-image-manifest-audio-leak.yaml"
    try:
        validate_image_manifest(path, registry_pattern_ids())
    except ValidationError as exc:
        require(
            "non-storyboard image prompt must not include audio generation terms" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject audio generation terms in non-storyboard image prompts")


def validate_image_prompt_bad_fragment_negative_fixture() -> None:
    path = "tests/fixtures/invalid-image-manifest-bad-prompt-fragment.yaml"
    try:
        validate_image_manifest(path, registry_pattern_ids())
    except ValidationError as exc:
        require(
            "prompt fragment" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject prompt_file fragments that do not resolve to an image prompt")


def validate_video_prompt_missing_reference_bindings_fixture() -> None:
    path = "tests/fixtures/invalid-video-prompt-missing-reference-bindings.yaml"
    try:
        validate_video_manifest(path)
    except ValidationError as exc:
        require(
            "reference_bindings" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject video prompts without explicit model reference bindings")


def validate_video_prompt_binding_wrong_model_fragment_fixture() -> None:
    path = "tests/fixtures/invalid-video-prompt-binding-wrong-model-fragment.yaml"
    try:
        validate_video_manifest(path)
    except ValidationError as exc:
        require(
            "matching model prompt fragment" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject reference bindings that point to another model prompt")


def validate_co_creation_needs_revision_downstream_fixture() -> None:
    path = "tests/fixtures/invalid-co-creation-needs-revision-downstream.yaml"
    try:
        validate_co_creation_run(path)
    except ValidationError as exc:
        require(
            "needs_revision gate" in str(exc) and "downstream" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject needs_revision gates that write downstream artifacts")


def validate_video_prompt_duplicate_fixture() -> None:
    path = "tests/fixtures/invalid-video-prompt-manifest-duplicated-model-prompts.yaml"
    try:
        validate_video_manifest(path)
    except ValidationError as exc:
        require(
            "duplicated model prompt text" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject duplicated model prompt text")


def validate_video_prompt_inline_anti_misread_fixture() -> None:
    path = "tests/fixtures/invalid-video-prompt-missing-inline-anti-misread.yaml"
    try:
        validate_video_manifest(path)
    except ValidationError as exc:
        require(
            "inline anti-misread instruction" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject model prompts without inline anti-misread instructions")


def validate_video_prompt_unlocked_direct_input_fixture() -> None:
    path = "tests/fixtures/invalid-video-prompt-direct-input-unlocked.yaml"
    try:
        validate_video_manifest(path)
    except ValidationError as exc:
        require(
            "primary direct input" in str(exc) and "before video generation is available" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject unlocked primary direct input when video generation is available")


def validate_reference_pack_storyboard_direct_input_fixture() -> None:
    path = "tests/fixtures/invalid-reference-pack-storyboard-direct-input.yaml"
    try:
        validate_reference_pack_manifest(path)
    except ValidationError as exc:
        require(
            "dense asset invalid_storyboard_direct unsafe for Kling" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject storyboard_motion_board as Kling direct input")


def validate_reference_pack_duplicate_role_fixture() -> None:
    path = "tests/fixtures/invalid-reference-pack-duplicate-role.yaml"
    try:
        validate_reference_pack_manifest(path)
    except ValidationError as exc:
        require(
            "duplicate primary reference roles" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject duplicate primary reference roles")


def validate_shot_list_duration_mismatch_fixture() -> None:
    path = "tests/fixtures/invalid-shot-list-duration-mismatch.yaml"
    try:
        validate_shot_list(path)
    except ValidationError as exc:
        require(
            "shot durations" in str(exc) and "declared duration" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject shot lists whose durations do not match the target")


def validate_shot_list_timecode_gap_fixture() -> None:
    path = "tests/fixtures/invalid-shot-list-timecode-gap.yaml"
    try:
        validate_shot_list(path)
    except ValidationError as exc:
        require(
            "timecode starts" in str(exc) or "timecode duration" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject shot lists with timecode gaps or overlaps")


def validate_shot_list_low_information_density_fixture() -> None:
    path = "tests/fixtures/invalid-shot-list-low-information-density.yaml"
    data = load_yaml(require_path(path))
    shots = shot_items(data)
    require(shots, f"{path} fixture must contain at least one shot")
    try:
        validate_professional_shot_card(path, shots[0])
    except ValidationError as exc:
        require(
            "professional card missing fields" in str(exc) or "blocking must be a structured mapping" in str(exc),
            f"{path} failed for the wrong reason: {exc}",
        )
        return
    raise ValidationError(f"{path} must reject low-density shot cards")


def validate_no_media_assets() -> None:
    media = [rel(path) for path in (ROOT / "examples").rglob("*") if path.is_file() and path.suffix.lower() in MEDIA_FILE_KINDS]
    require(not media, "real media assets are not allowed in examples during this goal:\n" + "\n".join(media))


def validate_demo_runner() -> None:
    proc = run(["python3", "scripts/dircreative_demo.py", "--example", "examples/live-user-sim-noodle"])
    require(proc.returncode == 0, f"demo runner failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "原始想法",
        "创意方向",
        "模拟用户选择",
        "15秒脚本",
        "5镜头分镜",
        "参考图方案",
        "Seedance",
        "Kling",
        "当前没有生成真实图片或视频",
        "出图执行建议",
        "QA 与重试规则",
        "self-QA",
        "Pre-Generation QA",
        "Retry Routing",
        "pre_generation_contract",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"demo runner output missing terms: {missing}")

    complete_proc = run(["python3", "scripts/dircreative_demo.py", "--example", "examples/complete-idea-segmentation-test"])
    require(complete_proc.returncode == 0, f"complete idea demo runner failed:\n{complete_proc.stderr}\n{complete_proc.stdout}")
    complete_required_terms = [
        "完整想法切分演示",
        "完整想法读取",
        "不进入创意发散",
        "导演组会议",
        "producer",
        "model_prompt_engineer",
        "continuity_qa",
        "导演组分歧",
        "V2 sequential",
        "6镜头分镜",
        "出图执行建议",
        "Largest title on the page",
        "Smaller metadata only",
        "Do not make FOG ROUTE CLEANER the largest title",
        "Seedance",
        "Kling",
        "当前没有生成真实图片或视频",
        "QA 与重试规则",
        "self-QA",
        "Pre-Generation QA",
        "Retry Routing",
        "smallest artifact",
    ]
    complete_missing = [term for term in complete_required_terms if term not in complete_proc.stdout]
    require(not complete_missing, f"complete idea demo runner output missing terms: {complete_missing}")


def validate_readiness_audit() -> None:
    proc = run(["python3", "scripts/dircreative_readiness_audit.py"])
    require(proc.returncode == 0, f"readiness audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Readiness Audit",
        "rough idea chat path is user-visible",
        "complete idea chat path is user-visible",
        "source runtime has a result-first start and generation boundary",
        "goal-mode simulation does not wait for manual choices",
        "goal-mode rough idea simulation covers one-sentence intake",
        "director-room adaptive perspectives",
        "adversarial council audit is executable",
        "COUNCIL_AUDIT: PASS",
        "film/commercial quality audit is executable",
        "QUALITY_AUDIT: PASS",
        "Creative Production adapter audit is executable",
        "CREATIVE_PRODUCTION_AUDIT: PASS",
        "Goal autorun dry-run audit is executable",
        "GOAL_AUTORUN_AUDIT: PASS",
        "professional dynamic shot design",
        "reference roles, title hierarchy",
        "model-specific video prompt adapters",
        "QA and smallest retry route",
        "assisted-generation preflight",
        "demo runner proves rough idea and complete idea flows",
        "visual dogfood pages are reproducible",
        "goal-mode simulation page has browser-smoke evidence",
        "goal-mode rough idea page has browser-smoke evidence",
        "READINESS: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"readiness audit output missing terms: {missing}")


def validate_quality_audit() -> None:
    proc = run(["python3", "scripts/dircreative_quality_audit.py"])
    require(proc.returncode == 0, f"quality audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Quality Audit",
        "film and commercial quality standard exists",
        "director-room exposes film and commercial tradeoff",
        "commercial proof and product safeguards are present",
        "quality failure ids have retry surface",
        "quality audit is wired into validation text",
        "quality audit does not close goal",
        "film_grade_ready: true",
        "commercial_grade_ready: true",
        "live_acceptance_required: true",
        "QUALITY_AUDIT: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"quality audit output missing terms: {missing}")


def validate_creative_production_audit() -> None:
    proc = run(["python3", "scripts/dircreative_creative_production_audit.py"])
    require(proc.returncode == 0, f"Creative Production audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Creative Production Audit",
        "Creative Production integration contract",
        "valid Creative Production receipt",
        "negative fixture rejected: invalid-creative-production-pre-gate.yaml",
        "negative fixture rejected: invalid-creative-production-widget-truth.yaml",
        "negative fixture rejected: invalid-creative-production-unreviewed-lock.yaml",
        "root and prompt skills mention Creative Production boundary",
        "adapter_source_of_truth: dircreative_artifacts",
        "review_surface: render_moodboard_board_widget",
        "live_acceptance_required: true",
        "CREATIVE_PRODUCTION_AUDIT: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"Creative Production audit output missing terms: {missing}")


def validate_goal_autorun_audit() -> None:
    proc = run(["python3", "scripts/dircreative_goal_autorun_audit.py"])
    require(proc.returncode == 0, f"Goal autorun audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Goal Autorun Audit",
        "autorun protocol exists",
        "autorun transcript covers required stages",
        "every user confirmation has simulated choice",
        "autorun co-creation run is valid",
        "forbidden live acceptance claim is covered by negative fixture",
        "goal audit still requires real acceptance",
        "goal_autorun_dry_run_complete: true",
        "real_media_generated: false",
        "live_acceptance_required: true",
        "GOAL_AUTORUN_AUDIT: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"Goal autorun audit output missing terms: {missing}")


def validate_loop_engineering_audit() -> None:
    proc = run(["python3", "scripts/dircreative_loop_engineering_audit.py"])
    require(proc.returncode == 0, f"Loop engineering audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Loop Engineering Audit",
        "typed action/observation contract",
        "receipt persistence contract",
        "retry loop contract",
        "council review contract",
        "Codex Thread boundary contract",
        "second-level dispatch contract",
        "Goal autorun dry-run boundary",
        "live acceptance boundary",
        "quality approval boundary",
        "typed_action_observation_contract: true",
        "receipt_persistence_contract: true",
        "retry_loop_contract: true",
        "council_review_contract: true",
        "codex_thread_boundary_contract: true",
        "second_level_dispatch_contract: true",
        "goal_autorun_dry_run_boundary: true",
        "live_acceptance_boundary: true",
        "creative_quality_approval_claimed: false",
        "LOOP_ENGINEERING_AUDIT: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"Loop engineering audit output missing terms: {missing}")


def validate_second_level_dispatch_audit() -> None:
    proc = run(["python3", "scripts/dircreative_second_level_dispatch_audit.py"])
    require(proc.returncode == 0, f"second-level dispatch audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Second-Level Dispatch Audit",
        "stateless_subagent_tool_verdict: available_when_explicitly_authorized",
        "negative_fixture_rejected: true",
        "second_level_subagents_are_durable_truth: false",
        "second_level_subagents_may_write_live_acceptance: false",
        "second_level_subagents_may_mark_goal_complete: false",
        "SECOND_LEVEL_DISPATCH_AUDIT: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"second-level dispatch audit output missing terms: {missing}")


def validate_visual_dogfood_pages() -> None:
    proc = run(["python3", "scripts/dircreative_visual_dogfood.py"])
    require(proc.returncode == 0, f"visual dogfood page generation failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Visual Dogfood Pages",
        "index:",
        "one-idea.html",
        "complete-idea.html",
        "goal-mode-simulation.html",
        "goal-mode-rough-idea.html",
        "readiness-audit.html",
        "goal-audit.html",
        "VISUAL_DOGFOOD_PAGES: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"visual dogfood output missing terms: {missing}")

    base = Path("/tmp/dircreative-visual-dogfood")
    page_requirements = {
        "index.html": ["DIRcreative Visual Dogfood", "one-idea.html", "complete-idea.html", "goal-mode-simulation.html", "goal-mode-rough-idea.html", "readiness-audit.html", "goal-audit.html"],
        "one-idea.html": ["DIRcreative 一句话想法流程可视检查", "出图执行建议", "QA 与重试规则"],
        "complete-idea.html": ["DIRcreative 完整想法流程可视检查", "导演组会议", "6镜头分镜", "QA 与重试规则"],
        "goal-mode-simulation.html": ["DIRcreative Goal 模式模拟测试", "阶段: 目标模式模拟测试", "模拟用户选择", "阶段: 出图执行建议", "阶段: 模拟测试结论"],
        "goal-mode-rough-idea.html": ["DIRcreative Goal 模式一句话想法模拟测试", "阶段: 想法读取", "模拟用户选择", "阶段: 出图执行建议", "阶段: 模拟测试结论"],
        "readiness-audit.html": ["DIRcreative Readiness Audit", "READINESS: PASS", "assisted-generation preflight"],
        "goal-audit.html": ["DIRcreative Goal Completion Audit", "TECHNICAL_READINESS: PASS", "GOAL_COMPLETE:"],
        "manifest.json": ['"status": "pass"', "one-idea.html", "complete-idea.html", "goal-mode-simulation.html", "goal-mode-rough-idea.html", "readiness-audit.html", "goal-audit.html"],
    }
    for filename, terms in page_requirements.items():
        path = base / filename
        require(path.exists(), f"visual dogfood missing {path}")
        text = path.read_text(encoding="utf-8")
        missing_terms = [term for term in terms if term not in text]
        require(not missing_terms, f"{path} missing terms: {missing_terms}")


def validate_visual_dogfood_gstack_receipt() -> None:
    path = "tests/fixtures/runtime/runs/visual-dogfood-gstack-receipt.yaml"
    data = load_yaml(require_path(path))
    artifact = data.get("artifact", {})
    run_data = data.get("run", {})
    pages = data.get("pages_checked", [])
    qa = data.get("qa", {})
    receipt = data.get("skill_run_receipt", {})

    require(artifact.get("status") == "approved", f"{path} artifact.status must be approved")
    require(artifact.get("owner_skill") == "gstack", f"{path} artifact.owner_skill must be gstack")
    require(run_data.get("tool") == "gstack browse", f"{path} run.tool must be gstack browse")
    require(run_data.get("console_status") == "no_console_messages", f"{path} console_status must be clean")
    require(run_data.get("browser_status") == "pass", f"{path} browser_status must be pass")
    require(run_data.get("real_media_generated") is False, f"{path} must record that no real media was generated")
    require(str(run_data.get("visual_dogfood_index", "")).endswith("/index.html"), f"{path} visual_dogfood_index must point to index.html")

    require(len(pages) == 7, f"{path} must record seven gstack/browser-checked pages")
    expected_page_ids = {
        "visual_dogfood_index",
        "one_idea_flow",
        "complete_idea_flow",
        "goal_mode_complete_simulation",
        "goal_mode_rough_idea_simulation",
        "readiness_audit",
        "goal_completion_audit",
    }
    seen_page_ids = {page.get("page_id") for page in pages}
    require(seen_page_ids == expected_page_ids, f"{path} page ids mismatch: {sorted(expected_page_ids - seen_page_ids)}")
    for page in pages:
        page_id = page.get("page_id", "unknown")
        require(page.get("status") == 200, f"{path} page {page_id} status must be 200")
        require(page.get("console_status") == "no_console_messages", f"{path} page {page_id} console_status must be clean")
        screenshot_path = page.get("screenshot_path", "")
        require(isinstance(screenshot_path, str) and screenshot_path.endswith(".png"), f"{path} page {page_id} screenshot_path must be png")
        terms = page.get("required_visible_terms", [])
        require(isinstance(terms, list) and terms, f"{path} page {page_id} must record visible terms")

    for key in [
        "visual_dogfood_pages_generated",
        "gstack_opened_pages",
        "screenshots_saved",
        "console_errors_absent",
        "one_idea_flow_visible",
        "complete_idea_flow_visible",
        "goal_mode_complete_simulation_visible",
        "goal_mode_rough_idea_simulation_visible",
        "readiness_audit_visible",
        "goal_audit_visible",
        "no_real_media_generated",
    ]:
        require(qa.get(key) is True, f"{path} qa.{key} must be true")
    require(qa.get("failures") == [], f"{path} qa.failures must be empty")

    require(receipt.get("qa_gate", {}).get("status") == "pass", f"{path} skill_run_receipt.qa_gate.status must be pass")
    require(receipt.get("next_recommended_skill") == "checkpoint", f"{path} must recommend checkpoint after visual dogfood")


def validate_goal_mode_visual_dogfood_receipt() -> None:
    path = "tests/fixtures/runtime/runs/goal-mode-simulation-visual-dogfood-receipt.yaml"
    data = load_yaml(require_path(path))
    artifact = data.get("artifact", {})
    run_data = data.get("run", {})
    page = data.get("page_checked", {})
    qa = data.get("qa", {})
    receipt = data.get("skill_run_receipt", {})

    require(artifact.get("status") == "approved", f"{path} artifact.status must be approved")
    require(run_data.get("tool") == "local_browser_playwright", f"{path} must record local browser smoke tool")
    require(run_data.get("console_status") == "no_console_messages", f"{path} console_status must be clean")
    require(run_data.get("browser_status") == "pass", f"{path} browser_status must be pass")
    require(run_data.get("real_media_generated") is False, f"{path} must record no real media")
    require(run_data.get("live_user_acceptance_receipt_written") is False, f"{path} must not write live acceptance")
    require(page.get("page_id") == "goal_mode_simulation_page", f"{path} page id mismatch")
    require(page.get("missing_visible_terms") == [], f"{path} must have no missing visible terms")
    for term in ["阶段: 目标模式模拟测试", "模拟用户选择", "阶段: 出图执行建议", "阶段: 模拟测试结论", "不计入真实验收"]:
        require(term in page.get("required_visible_terms", []), f"{path} missing required visible term: {term}")
    for key in [
        "goal_mode_page_generated",
        "browser_opened_page",
        "screenshots_saved",
        "console_errors_absent",
        "no_real_media_generated",
        "live_acceptance_not_claimed",
    ]:
        require(qa.get(key) is True, f"{path} qa.{key} must be true")
    require(receipt.get("qa_gate", {}).get("status") == "pass", f"{path} skill_run_receipt.qa_gate.status must be pass")


def validate_goal_mode_rough_idea_visual_dogfood_receipt() -> None:
    path = "tests/fixtures/runtime/runs/goal-mode-rough-idea-visual-dogfood-receipt.yaml"
    data = load_yaml(require_path(path))
    artifact = data.get("artifact", {})
    run_data = data.get("run", {})
    page = data.get("page_checked", {})
    qa = data.get("qa", {})
    receipt = data.get("skill_run_receipt", {})

    require(artifact.get("status") == "approved", f"{path} artifact.status must be approved")
    require(run_data.get("tool") == "local_browser_playwright", f"{path} must record local browser smoke tool")
    require(run_data.get("console_status") == "no_console_messages", f"{path} console_status must be clean")
    require(run_data.get("browser_status") == "pass", f"{path} browser_status must be pass")
    require(run_data.get("real_media_generated") is False, f"{path} must record no real media")
    require(run_data.get("live_user_acceptance_receipt_written") is False, f"{path} must not write live acceptance")
    require(page.get("page_id") == "goal_mode_rough_idea_page", f"{path} page id mismatch")
    require(page.get("missing_visible_terms") == [], f"{path} must have no missing visible terms")
    for term in ["阶段: 想法读取", "模拟用户选择", "阶段: 分镜头确认", "阶段: 出图执行建议", "阶段: 模拟测试结论", "不计入真实验收"]:
        require(term in page.get("required_visible_terms", []), f"{path} missing required visible term: {term}")
    for key in [
        "goal_mode_rough_idea_page_generated",
        "browser_opened_page",
        "screenshots_saved",
        "console_errors_absent",
        "no_real_media_generated",
        "live_acceptance_not_claimed",
    ]:
        require(qa.get(key) is True, f"{path} qa.{key} must be true")
    require(receipt.get("qa_gate", {}).get("status") == "pass", f"{path} skill_run_receipt.qa_gate.status must be pass")


def validate_media_forward_audit_script() -> None:
    execution_schema = load_json(
        require_path("docs/film-preproduction/schemas/media-forward-execution-v2.schema.json")
    )
    review_schema = load_json(
        require_path("docs/film-preproduction/schemas/media-visual-review-v1.schema.json")
    )
    require(
        execution_schema.get("properties", {}).get("schema_version", {}).get("const") == "2.0.0",
        "media execution schema must identify v2",
    )
    require(
        review_schema.get("properties", {}).get("reviewer", {}).get("properties", {}).get(
            "review_method", {}
        ).get("const")
        == "independent_visual_review",
        "media review schema must require an independent visual reviewer",
    )
    require(
        execution_schema.get("properties", {}).get("host_trace", {}).get("properties", {}).get(
            "evidence_level", {}
        ).get("const")
        == "unsigned_host_trace",
        "media execution schema must bind an honestly labeled host trace",
    )
    require(
        "view_event_ids"
        in review_schema.get("properties", {}).get("host_trace", {}).get("required", []),
        "media review schema must bind completed visual-view events",
    )
    proc = run(["python3", "scripts/dircreative_media_forward_audit.py", "--self-test"])
    require(
        proc.returncode == 0 and "DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: PASS" in proc.stdout,
        f"media-forward audit self-test failed:\n{proc.stderr}\n{proc.stdout}",
    )


def validate_release_gate_script() -> None:
    import contextlib
    import io
    from types import SimpleNamespace

    text = require_path("scripts/dircreative_release_gate.py").read_text(encoding="utf-8")
    required_terms = [
        "DIRcreative Release Gate",
        "scripts/validate_project.py",
        "scripts/dircreative_run.py",
        "examples/live-user-sim-noodle",
        "examples/complete-idea-segmentation-test",
        "examples/goal-mode-simulation-test",
        "examples/goal-mode-rough-idea-simulation-test",
        "goal-mode simulation status",
        "goal-mode rough idea status",
        "scripts/dircreative_readiness_audit.py",
        "scripts/dircreative_quality_audit.py",
        "scripts/dircreative_creative_production_audit.py",
        "scripts/dircreative_goal_autorun_audit.py",
        "scripts/dircreative_loop_engineering_audit.py",
        "scripts/dircreative_second_level_dispatch_audit.py",
        "scripts/dircreative_director_harness_audit.py",
        "scripts/dircreative_creative_copy_deck_audit.py",
        "scripts/dircreative_model_capability_audit.py",
        "scripts/dircreative_state_audit.py",
        "DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR",
        "scripts/dircreative_project_agents.py",
        "scripts/dircreative_goal_audit.py",
        "scripts/dircreative_objective_audit.py",
        "scripts/dircreative_council_audit.py",
        "scripts/dircreative_chat_surface_audit.py",
        "scripts/dircreative_thread_audit.py",
        "scripts/dircreative_install_parity.py",
        "scripts/dircreative_visual_dogfood.py",
        "scripts/dircreative_release_preflight.py",
        "scripts/dircreative_build_release.py",
        "scripts/dircreative_media_forward_audit.py",
        "--media-forward-receipt",
        "--media-review-receipt",
        "--media-host-event-log",
        "--media-review-host-event-log",
        "--require-media-forward",
        "--media-c2patool",
        "--require-candidate-skill-execution",
        "UNSIGNED_HOST_TRACE_IMAGE_PLUS_INDEPENDENT_REVIEW",
        "--expected-commit",
        "sealed commit final readback",
        "BILATERAL_MEDIA_RELEASE_GATE",
        "DIR_RELEASE_GATE",
        "verified formal artifact install",
        "--artifact",
        "--checksums",
        "--expected-tag",
        "--reproducible-source",
        "scripts/install_local_skill.py",
        "validate_explicit_staging_target",
        "tempfile.TemporaryDirectory",
        "depends_on",
        "installed skill validation",
        "installed parity audit",
        "installed goal-mode simulation status",
        "installed goal-mode rough idea status",
        "git",
        "diff",
        "--check",
        "goal completion audit",
        "objective completion audit",
        "council audit",
        "chat surface order audit",
        "thread audit",
        "project AGENTS audit",
        "GOAL_COMPLETE:",
        "OBJECTIVE_COMPLETE:",
        "COUNCIL_AUDIT:",
        "QUALITY_AUDIT:",
        "CREATIVE_PRODUCTION_AUDIT:",
        "GOAL_AUTORUN_AUDIT:",
        "LOOP_ENGINEERING_AUDIT:",
        "SECOND_LEVEL_DISPATCH_AUDIT:",
        "THREAD_AUDIT:",
        "CHAT_SURFACE_AUDIT:",
        "INSTALL_PARITY:",
        "PROJECT_AGENTS_AUDIT:",
        "RELEASE_PREFLIGHT:",
        "RELEASE_BUILD:",
        "RELEASE_ARTIFACT_VERIFY:",
        "release artifact install",
        "release artifact install parity",
        "release artifact installed validation",
        "RELEASE_GATE: PASS",
    ]
    missing = [term for term in required_terms if term not in text]
    require(not missing, f"release gate script missing terms: {missing}")

    import dircreative_release_gate as release_gate

    with tempfile.TemporaryDirectory(prefix="dircreative-release-staging-policy-") as raw:
        temporary_root = Path(raw)
        release_gate.validate_explicit_staging_target(temporary_root / "new-stage")
        unsafe_staging_targets = [
            temporary_root,
            ROOT,
            ROOT / "nested-stage",
            Path.home() / ".skillshub" / "dircreative",
            Path.home() / ".skillshub" / "DIRCREATIVE",
        ]
        for unsafe_target in unsafe_staging_targets:
            try:
                release_gate.validate_explicit_staging_target(unsafe_target)
            except ValueError:
                pass
            else:
                raise ValidationError(f"release gate accepted unsafe staging target: {unsafe_target}")

    original_run_step = release_gate.run_step
    forbidden_artifact_steps = {
        "release artifact build",
        "verified formal artifact install",
        "release artifact install parity",
        "release artifact installed validation",
    }

    def run_dependency_case(failing_label: str) -> tuple[int, set[str]]:
        executed: set[str] = set()

        def fake_run_step(step: Any) -> tuple[bool, str]:
            executed.add(step.label)
            return step.label != failing_label, ""

        release_gate.run_step = fake_run_step
        with tempfile.TemporaryDirectory(prefix="dircreative-release-gate-dependency-") as raw:
            args = SimpleNamespace(
                output_dir="dist-test",
                require_tag=False,
                allow_unpublished=True,
                adco_repo=None,
                media_forward_receipt=None,
                media_review_receipt=None,
                media_host_event_log=None,
                media_review_host_event_log=None,
                require_media_forward=False,
                media_c2patool=None,
            )
            with contextlib.redirect_stdout(io.StringIO()):
                result = release_gate.run_gate(
                    args,
                    Path(raw) / "source-stage",
                    Path(raw) / "scratch",
                    sealed_commit="a" * 40,
                    head_reader=lambda: "a" * 40,
                )
        return result, executed

    try:
        preflight_result, preflight_executed = run_dependency_case("repo validation")
        build_result, build_executed = run_dependency_case("release artifact build")
    finally:
        release_gate.run_step = original_run_step
    require(preflight_result == 1, "release gate must fail when a pre-artifact gate fails")
    require(
        forbidden_artifact_steps.isdisjoint(preflight_executed),
        "release gate built or installed an artifact after a failed pre-artifact gate",
    )
    require(build_result == 1, "release gate dependency self-test must fail when artifact build fails")
    require(
        (forbidden_artifact_steps - {"release artifact build"}).isdisjoint(build_executed),
        "release gate executed unverified artifact steps after a failed build",
    )

    captured_commands: dict[str, list[str]] = {}

    def capture_formal_step(step: Any) -> tuple[bool, str]:
        captured_commands[step.label] = step.cmd
        return True, ""

    release_gate.run_step = capture_formal_step
    try:
        with tempfile.TemporaryDirectory(prefix="dircreative-formal-release-gate-") as raw:
            formal_args = SimpleNamespace(
                output_dir="dist-test",
                require_tag=False,
                allow_unpublished=False,
                adco_repo=None,
                media_forward_receipt=None,
                media_review_receipt=None,
                media_host_event_log=None,
                media_review_host_event_log=None,
                require_media_forward=False,
                media_c2patool=None,
            )
            with contextlib.redirect_stdout(io.StringIO()):
                formal_result = release_gate.run_gate(
                    formal_args,
                    Path(raw) / "source-stage",
                    Path(raw) / "scratch",
                    sealed_commit="a" * 40,
                    head_reader=lambda: "a" * 40,
                )
    finally:
        release_gate.run_step = original_run_step
    require(formal_result == 0, "formal release gate capture must complete")
    require(
        "--require-tag" in captured_commands.get("exact commit release preflight", []),
        "formal release gate must require the exact annotated tag by default",
    )
    require(
        "--allow-unpublished" not in captured_commands.get("verified formal artifact install", []),
        "formal release gate must not relax canonical remote tag verification",
    )
    require(
        "--expected-tag" in captured_commands.get("verified formal artifact install", []),
        "formal release gate must bind formal installation to the expected tag",
    )
    require(
        "--verify-remote-tag"
        in captured_commands.get("release artifact install parity", []),
        "formal release gate parity must independently verify the canonical remote tag",
    )
    require(
        "--allow-development-install"
        in captured_commands.get("installed skill validation", []),
        "pre-artifact installed validation must explicitly identify the development install",
    )
    require(
        "--installed-package" in captured_commands.get("installed skill validation", []),
        "pre-artifact installed validation must use installed-package mode",
    )

    unpublished_commands: dict[str, list[str]] = {}

    def capture_unpublished_step(step: Any) -> tuple[bool, str]:
        unpublished_commands[step.label] = step.cmd
        return True, ""

    release_gate.run_step = capture_unpublished_step
    try:
        with tempfile.TemporaryDirectory(prefix="dircreative-unpublished-release-gate-") as raw:
            unpublished_args = SimpleNamespace(
                output_dir="dist-test",
                require_tag=False,
                allow_unpublished=True,
                adco_repo=None,
                media_forward_receipt=None,
                media_review_receipt=None,
                media_host_event_log=None,
                media_review_host_event_log=None,
                require_media_forward=False,
                media_c2patool=None,
            )
            with contextlib.redirect_stdout(io.StringIO()):
                unpublished_result = release_gate.run_gate(
                    unpublished_args,
                    Path(raw) / "source-stage",
                    Path(raw) / "scratch",
                    sealed_commit="a" * 40,
                    head_reader=lambda: "a" * 40,
                )
    finally:
        release_gate.run_step = original_run_step
    require(unpublished_result == 0, "unpublished release gate capture must complete")
    require(
        "--verify-remote-tag"
        not in unpublished_commands.get("release artifact install parity", []),
        "unpublished release gate parity must not require a canonical remote tag",
    )
    require(
        "--allow-development-install"
        not in captured_commands.get("release artifact installed validation", []),
        "formal artifact validation must not relax release metadata requirements",
    )
    require(
        "--installed-package"
        in captured_commands.get("release artifact installed validation", []),
        "formal artifact validation must use installed-package mode",
    )
    require(
        release_gate.sealed_head_unchanged("a" * 40, reader=lambda: "b" * 40) is False,
        "release gate must reject a final HEAD that differs from the sealed commit",
    )


def validate_goal_audit() -> None:
    proc = run(["python3", "scripts/dircreative_goal_audit.py"])
    require(proc.returncode == 0, f"goal audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Goal Completion Audit",
        "chat-first rough idea flow",
        "complete idea segmentation flow",
        "live chat start contract",
        "goal-mode simulated user flow",
        "goal-mode rough idea simulated flow",
        "professional dynamic shot density",
        "model-specific video prompts",
        "assisted generation preflight blocks unsafe media",
        "gstack visual dogfood evidence",
        "goal-mode simulation browser dogfood evidence",
        "goal-mode rough idea browser dogfood evidence",
        "film/commercial quality audit",
        "Creative Production adapter audit",
        "Goal autorun dry-run audit",
        "installed local skill package",
        "live user acceptance receipt template",
        "live user acceptance of chat experience",
        "TECHNICAL_READINESS: PASS",
        "GOAL_COMPLETE:",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"goal audit output missing terms: {missing}")
    if "GOAL_COMPLETE: NO" in proc.stdout:
        require("NEXT_REQUIRED_ACTION" in proc.stdout, "goal audit incomplete state must name NEXT_REQUIRED_ACTION")
    elif "GOAL_COMPLETE: YES" not in proc.stdout:
        raise ValidationError("goal audit must print GOAL_COMPLETE: NO or GOAL_COMPLETE: YES")

    invalid_proc = run(
        [
            "python3",
            "scripts/dircreative_goal_audit.py",
            "--acceptance-receipt",
            "tests/fixtures/invalid-live-user-acceptance-missing-scope.yaml",
        ]
    )
    require(invalid_proc.returncode != 0, "goal audit must fail for invalid live-user acceptance fixture")
    invalid_required_terms = [
        "[INVALID] live user acceptance of chat experience",
        "accepted_items missing:",
        "INVALID_ACCEPTANCE_RECEIPT",
        "GOAL_COMPLETE: NO",
    ]
    invalid_missing = [term for term in invalid_required_terms if term not in invalid_proc.stdout]
    require(not invalid_missing, f"invalid live-user acceptance fixture output missing terms: {invalid_missing}")

    simulated_proc = run(
        [
            "python3",
            "scripts/dircreative_goal_audit.py",
            "--acceptance-receipt",
            "tests/fixtures/invalid-live-user-acceptance-simulated-source.yaml",
        ]
    )
    require(simulated_proc.returncode != 0, "goal audit must fail for simulated live-user acceptance fixture")
    simulated_required_terms = [
        "[INVALID] live user acceptance of chat experience",
        "acceptance_run.run_type must be live_user_acceptance",
        "INVALID_ACCEPTANCE_RECEIPT",
        "GOAL_COMPLETE: NO",
    ]
    simulated_missing = [term for term in simulated_required_terms if term not in simulated_proc.stdout]
    require(not simulated_missing, f"simulated live-user acceptance fixture output missing terms: {simulated_missing}")


def validate_objective_audit() -> None:
    proc = run(["python3", "scripts/dircreative_objective_audit.py"])
    require(proc.returncode == 0, f"objective audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Objective Audit",
        "chat-visible rough idea flow",
        "chat-visible complete idea segmentation",
        "goal-mode simulated normal operation",
        "isolated simulated user testing",
        "live acceptance rehearsal remains chat-first",
        "director-room adaptive perspective collaboration",
        "adversarial council audit is executable",
        "film/commercial quality audit is executable",
        "Creative Production adapter audit is executable",
        "Goal autorun dry-run audit is executable",
        "professional script and dynamic shot density",
        "story duration separated from 15s generation units",
        "reference image roles stay separated",
        "customer-facing generation decision is visible before prompt internals",
        "image prompts include anti-drift and anti-artifact rules",
        "video prompts are model-specific",
        "QA and smallest-artifact retry routing",
        "consistency and misread safeguards",
        "prompt-only and assisted-generation preflight boundaries",
        "chat-visible assisted-generation preflight",
        "chat stage gate integrity is enforced",
        "installed skill verification",
        "gstack visual dogfood",
        "end-of-session progress reporting",
        "real user acceptance",
        "OBJECTIVE_TECHNICAL_READINESS: PASS",
        "COUNCIL_AUDIT: PASS",
        "OBJECTIVE_COMPLETE: NO",
        "NEXT_REQUIRED_ACTION",
        "do not treat goal-mode simulation as user approval",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"objective audit output missing terms: {missing}")


def validate_current_project_progress() -> None:
    path = "docs/film-preproduction/current-project-progress.md"
    text = require_path(path).read_text(encoding="utf-8")
    required_terms = [
        "Current Completion Progress",
        "completion_estimate_percent",
        "technical_readiness: pass",
        "objective_complete: no",
        "remaining_blocker: real_user_acceptance",
        "estimated_remaining_time",
        "story duration",
        "15s generation-unit limits",
        "Isolated simulated user testing",
        "midstream change stale-artifact handling",
        "Production prompt discipline",
        "Council adversarial review",
        "Codex thread orchestration",
        "pinned main-controller thread",
        "disposable read-only workers",
        "isolated worktree workers",
        "reusable research threads",
        "objective-requirement-audit-2026-06-06.yaml",
        "OBJECTIVE_COMPLETE: NO",
        "每次会话结束",
    ]
    missing = [term for term in required_terms if term not in text]
    require(not missing, f"{path} missing progress terms: {missing}")


def validate_progress_report() -> None:
    proc = run(["python3", "scripts/dircreative_progress_report.py"])
    require(proc.returncode == 0, f"progress report failed:\n{proc.stderr}\n{proc.stdout}")
    progress_text = require_path("docs/film-preproduction/current-project-progress.md").read_text(encoding="utf-8")
    match = re.search(r"^completion_estimate_percent:\s*(\d+)\s*$", progress_text, re.MULTILINE)
    require(match is not None, "current project progress missing completion_estimate_percent value")
    required_terms = [
        "DIRcreative Progress Report",
        f"completion_estimate_percent: {match.group(1)}",
        "technical_readiness: pass",
        "objective_complete: no",
        "remaining_blocker: real_user_acceptance",
        "estimated_remaining_time:",
        "latest_commit:",
        "worktree_state:",
        "next_required_action:",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"progress report output missing terms: {missing}")


def validate_acceptance_preflight() -> None:
    proc = run(["python3", "scripts/dircreative_acceptance_preflight.py"])
    require(proc.returncode == 0, f"acceptance preflight failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Acceptance Preflight",
        "runbook_present: pass",
        "template_guarded: pass",
        "live_receipt_absent: pass",
        "installed_skill_present: pass",
        "install_parity_pass: pass",
        "technical_readiness_pass: pass",
        "objective_still_blocked: pass",
        "receipt_creation_allowed: false",
        "acceptance_mode: real_chat_only",
        "require_installed: false",
        "operator_prompt:",
        "我要做一次 DIRcreative 真实聊天验收。",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"acceptance preflight output missing terms: {missing}")


def validate_council_audit() -> None:
    proc = run(["python3", "scripts/dircreative_council_audit.py"])
    require(proc.returncode == 0, f"council audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Council Audit",
        "required_viewpoints_present: true",
        "council_trigger_surface_present: true",
        "smallest_change_rule_present: true",
        "external_research_boundary_present: true",
        "failure_ids_present: true",
        "objective_complete: OBJECTIVE_COMPLETE: NO",
        "COUNCIL_AUDIT: PASS",
        "live user acceptance is still required",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"council audit output missing terms: {missing}")


def validate_thread_audit() -> None:
    proc = run(["python3", "scripts/dircreative_thread_audit.py", "--current-state", "--check-git-worktrees"])
    require(proc.returncode == 0, f"thread audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Current Thread/Worktree Audit",
        "current_thread_record_count: 0",
        "THREAD_CURRENT_AUDIT: PASS",
    ]
    if (ROOT / "SKILL.md").exists() and not (ROOT / ".git").exists():
        required_terms.extend(
            [
                "current_integrity: PACKAGE_RUNTIME_SENTINELS_ONLY",
                "legacy_debt: PACKAGE_RUNTIME_SENTINELS_ONLY",
                "git_worktree_evidence_source: not_applicable_installed_package",
            ]
        )
    else:
        required_terms.extend(
            [
                "current_integrity: PASS",
                "legacy_debt: NONE",
                "git_worktree_evidence_source: git",
            ]
        )
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"thread audit output missing terms: {missing}")


def validate_chat_surface_contract() -> None:
    contract = load_yaml(require_path("docs/film-preproduction/chat-surface-contract.yaml"))
    required_top_level = {
        "version",
        "customer_facing_stages",
        "customer_preview_stages",
        "backstage_evidence_terms",
        "forbidden_frontstage_artifacts",
        "stage_gate",
        "checks",
    }
    require(required_top_level.issubset(contract), "chat surface contract missing required top-level keys")

    stages = contract.get("customer_facing_stages", [])
    for term in ["阶段: 出图执行建议", "阶段: 视频生成建议", "阶段: QA 与重试规则"]:
        require(term in stages, f"chat surface contract missing customer-facing stage: {term}")

    preview_stages = contract.get("customer_preview_stages", [])
    for term in ["阶段: 出图执行建议", "阶段: 视频生成建议"]:
        require(term in preview_stages, f"chat surface contract missing customer preview stage: {term}")

    forbidden = contract.get("forbidden_frontstage_artifacts", [])
    for term in ["raw JSON", "YAML", "pre_generation_contract", "prompt bodies"]:
        require(term in forbidden, f"chat surface contract missing forbidden frontstage artifact: {term}")

    checks = contract.get("checks", [])
    require(isinstance(checks, list) and checks, "chat surface contract checks must be a non-empty list")
    check_paths = {check.get("path") for check in checks}
    expected_paths = {
        "examples/live-user-sim-noodle/16-chat-interface-demo.md",
        "examples/complete-idea-segmentation-test/02-chat-transcript.md",
        "examples/goal-mode-simulation-test/01-chat-transcript.md",
        "examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md",
        "examples/live-acceptance-rehearsal/01-chat-transcript.md",
        "examples/assisted-generation-preflight-chat/01-chat-transcript.md",
    }
    require(expected_paths.issubset(check_paths), f"chat surface contract missing check paths: {sorted(expected_paths - check_paths)}")
    for check in checks:
        check_id = check.get("id")
        ordered = check.get("ordered_stages", [])
        required_terms = check.get("required_terms", [])
        require("阶段: 出图执行建议" in ordered, f"{check_id} missing 出图执行建议 ordered stage")
        require("阶段: QA 与重试规则" in ordered, f"{check_id} missing QA 与重试规则 ordered stage")
        if check_id != "assisted_generation_preflight":
            require("阶段: 视频生成建议" in ordered, f"{check_id} missing 视频生成建议 ordered stage")
        require("用户确认点" in required_terms, f"{check_id} missing 用户确认点 required term")


def validate_chat_surface_audit() -> None:
    proc = run(["python3", "scripts/dircreative_chat_surface_audit.py"])
    require(proc.returncode == 0, f"chat surface audit failed:\n{proc.stderr}\n{proc.stdout}")
    required_terms = [
        "DIRcreative Chat Surface Audit",
        "examples/live-user-sim-noodle/16-chat-interface-demo.md",
        "examples/complete-idea-segmentation-test/02-chat-transcript.md",
        "examples/goal-mode-simulation-test/01-chat-transcript.md",
        "examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md",
        "examples/live-acceptance-rehearsal/01-chat-transcript.md",
        "examples/assisted-generation-preflight-chat/01-chat-transcript.md",
        "contract_before_prompts: ok",
        "content_terms: ok",
        "decision_counts: ok",
        "stage_gate_integrity: ok",
        "customer_preview: ok",
        "CHAT_SURFACE_AUDIT: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"chat surface audit output missing terms: {missing}")

    invalid_confirmation = run(
        [
            "python3",
            "scripts/dircreative_chat_surface_audit.py",
            "--check-stage-gate",
            "tests/fixtures/invalid-chat-transcript-missing-user-confirmation.md",
        ]
    )
    require(invalid_confirmation.returncode != 0, "chat stage gate audit must reject missing 用户确认点")
    require("missing 用户确认点" in invalid_confirmation.stdout, "missing confirmation fixture failed for the wrong reason")

    invalid_simulated = run(
        [
            "python3",
            "scripts/dircreative_chat_surface_audit.py",
            "--check-stage-gate",
            "tests/fixtures/invalid-chat-transcript-missing-simulated-choice.md",
            "--simulated",
        ]
    )
    require(invalid_simulated.returncode != 0, "chat stage gate audit must reject missing 模拟用户选择")
    require("missing 模拟用户选择" in invalid_simulated.stdout, "missing simulated choice fixture failed for the wrong reason")

    invalid_preview = run(
        [
            "python3",
            "scripts/dircreative_chat_surface_audit.py",
            "--check-customer-preview",
            "tests/fixtures/invalid-chat-transcript-internal-before-customer-preview.md",
        ]
    )
    require(invalid_preview.returncode != 0, "chat customer preview audit must reject internal state before 客户可见预览")
    require("exposes internal production state before 客户可见预览" in invalid_preview.stdout, "customer preview fixture failed for the wrong reason")


def installed_metadata_errors(root: Path, *, allow_development_install: bool) -> list[str]:
    installed_runtime_layout = (root / "SKILL.md").is_file() and not (
        root / "skills/dircreative/SKILL.md"
    ).exists()
    if not installed_runtime_layout:
        return []
    metadata_path = root / "RELEASE-METADATA.json"
    if not metadata_path.is_file():
        return [] if allow_development_install else [
            "formal installed layout requires RELEASE-METADATA.json"
        ]
    try:
        metadata = load_json(metadata_path)
    except (json.JSONDecodeError, OSError) as exc:
        return [f"installed release metadata is unreadable: {exc}"]
    if not isinstance(metadata, dict):
        return ["installed release metadata must be an object"]
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        root_skill_sha256 = hashlib.sha256((root / "SKILL.md").read_bytes()).hexdigest()
    except OSError as exc:
        return [f"installed release metadata inputs are unreadable: {exc}"]
    expected_fields = {
        "schema_version",
        "product",
        "version",
        "tag",
        "commit_sha",
        "commit_timestamp",
        "root_skill_sha256",
        "source",
        "release_status",
    }
    errors: list[str] = []
    if set(metadata) != expected_fields:
        errors.append("installed release metadata field set mismatch")
    required_metadata = {
        "schema_version": "1.1.0",
        "product": "DIRcreative",
        "version": version,
        "tag": f"v{version}",
        "source": "git archive of exact commit",
        "root_skill_sha256": root_skill_sha256,
    }
    for key, expected in required_metadata.items():
        if metadata.get(key) != expected:
            errors.append(f"installed release metadata {key} mismatch")
    if not isinstance(metadata.get("commit_sha"), str) or re.fullmatch(
        r"[0-9a-f]{40}", metadata.get("commit_sha", "")
    ) is None:
        errors.append("installed release metadata commit_sha is invalid")
    timestamp = metadata.get("commit_timestamp")
    try:
        parsed_timestamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        parsed_timestamp = None
    if parsed_timestamp is None or parsed_timestamp.tzinfo is None:
        errors.append("installed release metadata commit_timestamp is invalid")
    if metadata.get("release_status") not in {
        "UNPUBLISHED_LOCAL_CANDIDATE",
        "CANONICAL_REMOTE_TAG",
    }:
        errors.append("installed release metadata release_status is invalid")
    return errors


def validate_installed_metadata() -> None:
    errors = installed_metadata_errors(
        ROOT,
        allow_development_install=ALLOW_DEVELOPMENT_INSTALL,
    )
    require(not errors, errors[0] if errors else "installed metadata validation failed")
    installed_runtime_layout = (ROOT / "SKILL.md").is_file() and not (
        ROOT / "skills/dircreative/SKILL.md"
    ).exists()
    metadata_path = ROOT / "RELEASE-METADATA.json"
    if installed_runtime_layout and metadata_path.is_file():
        self_attestation_proc = run(
            [
                "python3",
                "scripts/dircreative_install_parity.py",
                "--target",
                str(ROOT),
                "--source-root",
                str(ROOT),
            ]
        )
        require(
            self_attestation_proc.returncode != 0
            and "an installed copy cannot certify itself" in self_attestation_proc.stdout,
            "installed layout must keep parity self-attestation fail-closed",
        )


def validate_install_parity_audit() -> None:
    from dircreative_package_layout import (
        HOST_USER_PATH_RE,
        PACKAGE_ITEMS,
        PACKAGE_RUNTIME_FILES,
        sanitize_package_bytes,
    )
    from dircreative_install_parity import validate_canonical_tag_refs

    historical_commit = "a" * 40
    advanced_main_refs = {
        "refs/heads/main": "b" * 40,
        "refs/tags/v9.9.9": "c" * 40,
        "refs/tags/v9.9.9^{}": historical_commit,
    }
    require(
        not validate_canonical_tag_refs(
            advanced_main_refs, "v9.9.9", historical_commit
        ),
        "historical annotated release tag became invalid after main advanced",
    )
    require(
        validate_canonical_tag_refs(
            {"refs/tags/v9.9.9": historical_commit},
            "v9.9.9",
            historical_commit,
        ),
        "lightweight canonical tag was accepted without a peeled annotated ref",
    )

    require(".dircreative" not in PACKAGE_ITEMS, "release package must not copy the complete runtime state directory")
    require(
        PACKAGE_RUNTIME_FILES == [".dircreative/checkpoints/.keep", ".dircreative/runs/.keep"],
        "release package runtime allowlist must contain only empty lifecycle sentinels",
    )
    with tempfile.TemporaryDirectory(prefix="dircreative-metadata-mode-") as temp_dir:
        installed_root = Path(temp_dir)
        (installed_root / "SKILL.md").write_text("fixture skill\n", encoding="utf-8")
        (installed_root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
        require(
            installed_metadata_errors(installed_root, allow_development_install=False)
            == ["formal installed layout requires RELEASE-METADATA.json"],
            "metadata-free installed layout must fail formal validation",
        )
        require(
            not installed_metadata_errors(installed_root, allow_development_install=True),
            "metadata-free installed layout must pass only explicit development mode",
        )
        valid_metadata = {
            "schema_version": "1.1.0",
            "product": "DIRcreative",
            "version": "9.9.9",
            "tag": "v9.9.9",
            "commit_sha": "a" * 40,
            "commit_timestamp": "2026-08-21T00:00:00Z",
            "root_skill_sha256": hashlib.sha256((installed_root / "SKILL.md").read_bytes()).hexdigest(),
            "source": "git archive of exact commit",
            "release_status": "UNPUBLISHED_LOCAL_CANDIDATE",
        }
        metadata_path = installed_root / "RELEASE-METADATA.json"
        metadata_path.write_text(json.dumps(valid_metadata) + "\n", encoding="utf-8")
        require(
            not installed_metadata_errors(installed_root, allow_development_install=False),
            "valid formal metadata must pass installed validation",
        )
        invalid_metadata = dict(valid_metadata)
        invalid_metadata["unexpected"] = True
        metadata_path.write_text(json.dumps(invalid_metadata) + "\n", encoding="utf-8")
        require(
            "installed release metadata field set mismatch"
            in installed_metadata_errors(installed_root, allow_development_install=True),
            "development flag must not weaken present formal metadata validation",
        )
        invalid_metadata = dict(valid_metadata)
        invalid_metadata["release_status"] = "DEVELOPMENT"
        metadata_path.write_text(json.dumps(invalid_metadata) + "\n", encoding="utf-8")
        require(
            "installed release metadata release_status is invalid"
            in installed_metadata_errors(installed_root, allow_development_install=False),
            "installed metadata must reject unknown release status",
        )
    installer_text = require_path("scripts/install_local_skill.py").read_text(encoding="utf-8")
    installer_terms = [
        "tempfile.mkdtemp",
        "os.replace",
        "backup",
        "sanitize_package_bytes",
        "HOST_USER_PATH_RE",
        "THREAD_ID_RE",
    ]
    missing_installer_terms = [term for term in installer_terms if term not in installer_text]
    require(not missing_installer_terms, f"atomic sanitized installer missing terms: {missing_installer_terms}")
    with tempfile.TemporaryDirectory(prefix="dircreative-install-parity-") as tmp:
        install_proc = run(["python3", "scripts/install_local_skill.py", "--target", tmp])
        require(install_proc.returncode == 0, f"temporary install for parity audit failed:\n{install_proc.stderr}\n{install_proc.stdout}")
        tmp_root = Path(tmp)
        exposed_skill_files = sorted(path.relative_to(tmp_root).as_posix() for path in tmp_root.rglob("SKILL.md"))
        require(exposed_skill_files == ["SKILL.md"], f"temporary install exposed duplicate skill files: {exposed_skill_files}")
        internal_frontmatter = []
        for path in sorted((tmp_root / "skills").rglob("INTERNAL_SKILL.md")):
            text = path.read_text(encoding="utf-8")
            if text.startswith("---\n") and ("name:" in text[:200] or "description:" in text[:300]):
                internal_frontmatter.append(path.relative_to(tmp_root).as_posix())
        require(not internal_frontmatter, f"internal installed skills still expose skill frontmatter: {internal_frontmatter[:20]}")
        installed_runtime = sorted(
            path.relative_to(tmp_root).as_posix()
            for path in (tmp_root / ".dircreative").rglob("*")
            if path.is_file()
        )
        require(
            installed_runtime == sorted(PACKAGE_RUNTIME_FILES),
            "installed runtime fixture allowlist mismatch: " + ", ".join(installed_runtime),
        )
        packaged_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in tmp_root.rglob("*")
            if path.is_file()
        )
        require(HOST_USER_PATH_RE.search(packaged_text) is None, "installed package leaks a host user path")
        require(
            re.search(r"\b019[a-f0-9]{5}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b", packaged_text, re.IGNORECASE) is None,
            "installed package leaks a live Codex thread id",
        )
        proc = run(["python3", "scripts/dircreative_install_parity.py", "--target", tmp])
        require(proc.returncode == 0, f"install parity audit failed:\n{proc.stderr}\n{proc.stdout}")
        self_attestation_proc = run(
            [
                "python3",
                str(tmp_root / "scripts" / "dircreative_install_parity.py"),
                "--target",
                tmp,
            ]
        )
        require(
            self_attestation_proc.returncode != 0,
            "an installed copy must not certify its own parity",
        )
        require(
            "an installed copy cannot certify itself" in self_attestation_proc.stdout,
            "installed-copy self-attestation failed for the wrong reason",
        )
        commit_proc = run(["git", "rev-parse", "HEAD"])
        if commit_proc.returncode == 0:
            release_metadata_path = tmp_root / "RELEASE-METADATA.json"
            version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
            valid_release_metadata = {
                "schema_version": "1.1.0",
                "product": "DIRcreative",
                "version": version,
                "tag": f"v{version}",
                "commit_sha": commit_proc.stdout.strip(),
                "root_skill_sha256": hashlib.sha256((tmp_root / "SKILL.md").read_bytes()).hexdigest(),
                "source": "git archive of exact commit",
                "commit_timestamp": "2026-01-01T00:00:00Z",
                "release_status": "UNPUBLISHED_LOCAL_CANDIDATE",
            }
            release_metadata_path.write_text(
                json.dumps(valid_release_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            invalid_release_metadata = dict(valid_release_metadata)
            invalid_release_metadata["commit_sha"] = "0" * 40
            release_metadata_path.write_text(
                json.dumps(invalid_release_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            invalid_metadata_proc = run(["python3", "scripts/dircreative_install_parity.py", "--target", tmp])
            require(invalid_metadata_proc.returncode != 0, "install parity accepted stale release metadata")
            require(
                "invalid installed release metadata: commit_sha does not match source HEAD" in invalid_metadata_proc.stdout,
                "stale release metadata failed for the wrong reason",
            )
            fake_release_metadata = dict(valid_release_metadata)
            fake_release_metadata["published"] = True
            release_metadata_path.write_text(
                json.dumps(fake_release_metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            fake_metadata_proc = run(["python3", "scripts/dircreative_install_parity.py", "--target", tmp])
            require(fake_metadata_proc.returncode != 0, "install parity accepted an extra published field")
            require(
                "invalid installed release metadata: field set mismatch" in fake_metadata_proc.stdout,
                "extra release metadata field failed for the wrong reason",
            )
            release_metadata_path.unlink()

            with tempfile.TemporaryDirectory(
                prefix="dircreative-clean-parity-source-"
            ) as clean_raw, tempfile.TemporaryDirectory(
                prefix="dircreative-clean-parity-target-"
            ) as clean_target_raw:
                clean_source = Path(clean_raw) / "source"
                shutil.copytree(
                    ROOT,
                    clean_source,
                    symlinks=True,
                    ignore=shutil.ignore_patterns(
                        ".git", "dist", "__pycache__", "*.pyc", "*.pyo", ".DS_Store"
                    ),
                )
                for command in (
                    ["git", "-C", str(clean_source), "init", "-q"],
                    ["git", "-C", str(clean_source), "add", "-A", "-f"],
                    [
                        "git",
                        "-C",
                        str(clean_source),
                        "-c",
                        "user.name=DIRcreative Test",
                        "-c",
                        "user.email=dircreative-test@example.invalid",
                        "commit",
                        "-q",
                        "-m",
                        "sealed parity fixture",
                    ],
                ):
                    git_proc = run(command)
                    require(
                        git_proc.returncode == 0,
                        f"clean parity fixture git setup failed: {git_proc.stderr}",
                    )
                clean_install_proc = run(
                    [
                        "python3",
                        str(clean_source / "scripts" / "install_local_skill.py"),
                        "--target",
                        clean_target_raw,
                    ]
                )
                require(
                    clean_install_proc.returncode == 0,
                    "clean parity fixture install failed:\n"
                    f"{clean_install_proc.stderr}\n{clean_install_proc.stdout}",
                )
                clean_commit = run(
                    ["git", "-C", str(clean_source), "rev-parse", "HEAD"]
                ).stdout.strip()
                clean_epoch = int(
                    run(
                        ["git", "-C", str(clean_source), "show", "-s", "--format=%ct", "HEAD"]
                    ).stdout.strip()
                )
                clean_timestamp = datetime.fromtimestamp(
                    clean_epoch, tz=timezone.utc
                ).isoformat().replace("+00:00", "Z")
                clean_target = Path(clean_target_raw)
                clean_metadata = {
                    "schema_version": "1.1.0",
                    "product": "DIRcreative",
                    "version": version,
                    "tag": f"v{version}",
                    "commit_sha": clean_commit,
                    "root_skill_sha256": hashlib.sha256(
                        (clean_target / "SKILL.md").read_bytes()
                    ).hexdigest(),
                    "source": "git archive of exact commit",
                    "commit_timestamp": clean_timestamp,
                    "release_status": "UNPUBLISHED_LOCAL_CANDIDATE",
                }
                (clean_target / "RELEASE-METADATA.json").write_text(
                    json.dumps(clean_metadata, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                clean_parity_proc = run(
                    [
                        "python3",
                        str(clean_source / "scripts" / "dircreative_install_parity.py"),
                        "--target",
                        clean_target_raw,
                        "--source-root",
                        str(clean_source),
                    ]
                )
                require(
                    clean_parity_proc.returncode == 0,
                    "clean exact-commit metadata parity failed:\n"
                    f"{clean_parity_proc.stderr}\n{clean_parity_proc.stdout}",
                )
                canonical_without_tag = dict(clean_metadata)
                canonical_without_tag["release_status"] = "CANONICAL_REMOTE_TAG"
                (clean_target / "RELEASE-METADATA.json").write_text(
                    json.dumps(
                        canonical_without_tag,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                unverified_canonical_proc = run(
                    [
                        "python3",
                        str(clean_source / "scripts" / "dircreative_install_parity.py"),
                        "--target",
                        clean_target_raw,
                        "--source-root",
                        str(clean_source),
                    ]
                )
                require(
                    unverified_canonical_proc.returncode != 0
                    and "CANONICAL_REMOTE_TAG requires remote tag verification"
                    in unverified_canonical_proc.stdout,
                    "canonical release metadata passed without remote tag evidence:\n"
                    f"{unverified_canonical_proc.stderr}\n{unverified_canonical_proc.stdout}",
                )
                (clean_target / "RELEASE-METADATA.json").write_text(
                    json.dumps(clean_metadata, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                dirty_probe = clean_source / "PARITY_DIRTY_SOURCE_PROBE.txt"
                dirty_probe.write_text("untracked\n", encoding="utf-8")
                dirty_status = run(
                    [
                        "git",
                        "-C",
                        str(clean_source),
                        "status",
                        "--porcelain=v1",
                        "--untracked-files=all",
                    ]
                )
                require(
                    dirty_status.returncode == 0 and dirty_status.stdout.strip(),
                    "dirty parity fixture did not become dirty",
                )
                dirty_parity_proc = run(
                    [
                        "python3",
                        str(clean_source / "scripts" / "dircreative_install_parity.py"),
                        "--target",
                        clean_target_raw,
                        "--source-root",
                        str(clean_source),
                    ]
                )
                require(
                    dirty_parity_proc.returncode != 0
                    and "source checkout is dirty or not a Git worktree"
                    in dirty_parity_proc.stdout,
                    "dirty source forged exact-commit release metadata was not rejected:\n"
                    f"{dirty_parity_proc.stderr}\n{dirty_parity_proc.stdout}",
                )
        unknown_root = tmp_root / "AGENTS.md"
        unknown_root.write_text("untracked\n", encoding="utf-8")
        unknown_root_proc = run(["python3", "scripts/dircreative_install_parity.py", "--target", tmp])
        require(unknown_root_proc.returncode != 0, "install parity must reject an unknown root file")
        require("extra installed files: AGENTS.md" in unknown_root_proc.stdout, "unknown root file failed for the wrong reason")
        unknown_root.unlink()
        unknown_runtime = tmp_root / ".dircreative" / "runs" / "UNTRACKED.yaml"
        unknown_runtime.write_text("status: stale\n", encoding="utf-8")
        unknown_runtime_proc = run(["python3", "scripts/dircreative_install_parity.py", "--target", tmp])
        require(unknown_runtime_proc.returncode != 0, "install parity must reject an untracked runtime receipt")
        require(
            "extra installed files: .dircreative/runs/UNTRACKED.yaml" in unknown_runtime_proc.stdout,
            "untracked runtime receipt failed for the wrong reason",
        )
        unknown_runtime.unlink()
        unexpected_metadata = tmp_root / "UNEXPECTED-RELEASE-METADATA.json"
        unexpected_metadata.write_text('{"commit_sha":"tampered"}\n', encoding="utf-8")
        metadata_proc = run(["python3", "scripts/dircreative_install_parity.py", "--target", tmp])
        require(metadata_proc.returncode != 0, "install parity must reject unexpected or stale release metadata")
        require(
            "extra installed files: UNEXPECTED-RELEASE-METADATA.json" in metadata_proc.stdout,
            "unexpected release metadata failed for the wrong reason",
        )
        unexpected_metadata.unlink()
        protected_file = tmp_root / "scripts" / "validate_project.py"
        protected_bytes = protected_file.read_bytes()
        hardlink_source = tmp_root / "hardlink-source.bin"
        hardlink_source.write_bytes(protected_bytes)
        protected_file.unlink()
        os.link(hardlink_source, protected_file)
        hardlink_proc = run(["python3", "scripts/dircreative_install_parity.py", "--target", tmp])
        require(hardlink_proc.returncode != 0, "install parity must reject hardlinked package files")
        require(
            "hardlink_or_reused_inode" in hardlink_proc.stdout,
            "hardlinked package file failed for the wrong reason",
        )
        protected_file.unlink()
        hardlink_source.unlink()
        protected_file.write_bytes(protected_bytes)
        bridge_proc = run(
            [
                "python3",
                str(tmp_root / "scripts/dircreative_adco_native_exchange.py"),
                "--self-test",
            ]
        )
        require(
            bridge_proc.returncode == 0,
            "installed ADCO native exchange self-test failed:\n"
            + bridge_proc.stderr
            + "\n"
            + bridge_proc.stdout,
        )
        require(
            "ADCO_NATIVE_SELF_TEST: PASS" in bridge_proc.stdout,
            "installed ADCO native exchange self-test did not report PASS",
        )
    slash = "/"
    backslash = chr(92)
    host_path_samples = [
        slash + "Users" + slash + "alice/private/file.txt",
        slash + "Users" + slash + "John Doe/private/file.txt",
        slash + "Users" + slash + "高进/private/file.txt",
        slash + "home/alice/private/file.txt",
        slash + "root/private/file.txt",
        slash + "private/var/root/private/file.txt",
        slash + "mnt/c/Users/Alice/private/file.txt",
        "C:" + backslash + "Users" + backslash + "Alice" + backslash + "private" + backslash + "file.txt",
        "C:" + backslash + "Users" + backslash + "John Doe" + backslash + "private" + backslash + "file.txt",
        "C:" + backslash * 2 + "Users" + backslash * 2 + "Alice" + backslash * 2 + "private" + backslash * 2 + "file.txt",
        "C:" + slash + "Users" + slash + "Alice/private/file.txt",
        backslash * 2 + "server" + backslash + "share" + backslash + "Users" + backslash + "John Doe" + backslash + "private" + backslash + "file.txt",
        backslash * 2 + "server" + backslash + "share" + backslash + "高进" + backslash + "private" + backslash + "file.txt",
        slash * 2 + "server/share/Alice/private/file.txt",
        backslash * 2 + "wsl$" + backslash + "Ubuntu" + backslash + "home" + backslash + "Alice" + backslash + "private" + backslash + "file.txt",
        slash * 2 + "wsl.localhost/Ubuntu/home/alice/private/file.txt",
    ]
    for index, sample in enumerate(host_path_samples):
        require(HOST_USER_PATH_RE.search(sample) is not None, f"host path detector missed fixture {index}")
        sanitized = sanitize_package_bytes(f"host-path-{index}", sample.encode("utf-8"), {}).decode("utf-8")
        require(HOST_USER_PATH_RE.search(sanitized) is None, f"host path sanitizer missed fixture {index}")
        require(
            not any(secret in sanitized.lower() for secret in ("alice", "john doe", "高进")),
            f"host path sanitizer retained username in fixture {index}",
        )
    for public_url in ("https://example.com/Users/Alice/public", "https://example.com/home/alice/page"):
        require(HOST_USER_PATH_RE.search(public_url) is None, f"host path matcher corrupts public URL: {public_url}")
    installer_self_test = run(["python3", "scripts/install_local_skill.py", "--self-test"])
    require(
        installer_self_test.returncode == 0,
        f"installer recovery self-test failed:\n{installer_self_test.stderr}\n{installer_self_test.stdout}",
    )
    require(
        "DIRCREATIVE_INSTALLER_SELF_TEST: PASS" in installer_self_test.stdout,
        "installer recovery self-test missing PASS marker",
    )
    required_terms = [
        "DIRcreative Install Parity",
        "source:",
        "target:",
        "source_files:",
        "target_files:",
        "INSTALL_PARITY: PASS",
    ]
    missing = [term for term in required_terms if term not in proc.stdout]
    require(not missing, f"install parity audit output missing terms: {missing}")


def validate_release_distribution_contract() -> None:
    version = require_path("VERSION").read_text(encoding="utf-8").strip()
    require(re.fullmatch(r"\d+\.\d+\.\d+", version) is not None, "VERSION must be semantic x.y.z")
    readme = require_path("README.md").read_text(encoding="utf-8")
    changelog = require_path("CHANGELOG.md").read_text(encoding="utf-8")
    require(f"v{version}" in readme, f"README must declare v{version}")
    require(f"## {version}" in changelog, f"CHANGELOG must contain {version}")
    require("--expected-commit \"$EXPECTED_COMMIT\"" in readme, "formal install docs must bind archive metadata to the remote tag commit")
    require("refs/tags/$TAG^{}" in readme, "formal install docs must resolve the annotated remote tag commit")
    require("--formal-install" in readme, "formal install docs must explicitly authorize replacing the canonical installation")
    for option in (
        "--artifact",
        "--checksums",
        "--expected-tag",
        "--reproducible-source",
        "--allow-unpublished",
    ):
        require(option in readme, f"formal install docs must describe {option}")
    require(
        "不能运行归档内的 installer" in readme,
        "formal install docs must reject the extracted-installer trust bypass",
    )

    sources = {
        "release preflight": require_path("scripts/dircreative_release_preflight.py").read_text(encoding="utf-8"),
        "release builder": require_path("scripts/dircreative_build_release.py").read_text(encoding="utf-8"),
        "release verifier": require_path("scripts/dircreative_verify_release.py").read_text(encoding="utf-8"),
        "package layout": require_path("scripts/dircreative_package_layout.py").read_text(encoding="utf-8"),
        "installer": require_path("scripts/install_local_skill.py").read_text(encoding="utf-8"),
        "install parity": require_path("scripts/dircreative_install_parity.py").read_text(encoding="utf-8"),
    }
    source_layout = not (ROOT / "SKILL.md").exists()
    if source_layout:
        sources["CI workflow"] = require_path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    required_by_source = {
        "release preflight": [
            "git_worktree_count",
            "origin/main",
            "release worktree is not clean",
            "--require-tag",
            "--expected-commit",
            "sealed_commit",
            "sealed commit does not equal origin/main",
            "HEAD changed during release preflight",
            "EXPECTED_ORIGIN_SLUG",
            "origin_push_url",
            "remote_tag_target",
            "remote_tag_annotated",
            "hidden_index_entry_count",
            "sparse_checkout",
        ],
        "release builder": [
            "git_bytes(\"archive\"",
            "candidate_still_valid",
            "remove_release_outputs",
            "FAIL_POSTCHECK",
            "RELEASE_BUILD_SELF_TEST: PASS",
            "RELEASE-METADATA.json",
            "root_skill_sha256",
            "dircreative_install_parity.py",
            "SHA256SUMS",
            "RELEASE_BUILD: PASS",
        ],
        "release verifier": [
            "checksum_for",
            "unsafe release member path",
            "root skill hash mismatch",
            "HOST_USER_PATH_RE",
            "THREAD_ID_RE",
            "ArchiveLimits",
            "max_archive_bytes",
            "max_total_file_bytes",
            "max_tar_stream_bytes",
            "forbidden extended metadata",
            "duplicate release member",
            "verify_reproducible_build",
            "verify_canonical_remote_tag",
            "reject_hidden_index_state",
            "--no-hardlinks",
            "copy_regular_file_once",
            "O_NOFOLLOW",
            "canonical USTAR",
            "release artifact does not match the reproducible exact-commit build",
            "ArchiveManifestEntry",
            "archive_manifest_sha256",
            "assert_tree_matches_manifest",
            "provenance_scope",
            "local_exact_commit_rebuild_only",
            "canonical_remote_tag",
            "RELEASE_ARTIFACT_VERIFY_SELF_TEST: PASS",
            "RELEASE_ARTIFACT_VERIFY: PASS",
        ],
        "package layout": [
            "PACKAGE_RUNTIME_FILES",
            "sanitize_package_bytes",
            "SANITIZED_FIXTURE_HEADER",
            "HOST_USER_PATH_RE",
            "THREAD_ID_RE",
            "(?:Users|home)",
        ],
        "installer": [
            "except BaseException",
            "install_completed",
            "previous install is retained at",
            "DIRCREATIVE_INSTALLER_SELF_TEST: PASS",
            "formal DIRcreative installation requires explicit --formal-install authorization",
            "formal DIRcreative installation requires a verified artifact",
            "FORMAL_REQUIRED_OPTIONS",
            "verify_release_detailed",
            "assert_tree_matches_manifest",
            "archive_manifest_sha256",
            "UNPUBLISHED_LOCAL_CANDIDATE",
            "CANONICAL_REMOTE_TAG",
            "install target must not be a symlink",
            ".codex\" / \"dev-skills",
        ],
        "install parity": [
            "collect_target_manifest",
            "invalid installed entries",
            "extra installed files",
            "RELEASE-METADATA.json",
        ],
    }
    if source_layout:
        required_by_source["CI workflow"] = [
            "scripts/validate_project.py",
            "scripts/install_local_skill.py",
            "scripts/dircreative_build_release.py",
            "scripts/dircreative_adco_native_exchange.py",
            "dircreative-archive-installed",
            "c19e3f92bdf4d311ab4ed79831b344979f1df01f",
            "101132984166d9580589b2ba2c6590d7f88d7509",
            "ADCO_TESTED_SHA",
            "ADCO_V2_TESTED_SHA",
            "--formal-install",
            "FORMAL_ARGS",
            "--artifact",
            "--checksums",
            "--expected-tag",
            "--reproducible-source",
            "--allow-unpublished",
            'python-version: ["3.10", "3.12", "3.14"]',
            "dist-umask-077",
            "compare-reproducibility",
            "reproducibility-macos",
        ]
    for name, required_terms in required_by_source.items():
        missing = [term for term in required_terms if term not in sources[name]]
        require(not missing, f"{name} missing release contract terms: {missing}")
    if source_layout:
        require(
            re.search(r"uses:\s+actions/[^@\s]+@v\d", sources["CI workflow"]) is None,
            "CI workflow must pin third-party actions to immutable commit SHAs",
        )

    verifier = run(["python3", "scripts/dircreative_verify_release.py", "--self-test"])
    require(
        verifier.returncode == 0,
        f"release artifact verifier self-test failed:\n{verifier.stderr}\n{verifier.stdout}",
    )
    require(
        "RELEASE_ARTIFACT_VERIFY_SELF_TEST: PASS" in verifier.stdout,
        "release artifact verifier self-test missing PASS marker",
    )
    builder = run(["python3", "scripts/dircreative_build_release.py", "--self-test"])
    require(
        builder.returncode == 0,
        f"release builder self-test failed:\n{builder.stderr}\n{builder.stdout}",
    )
    require(
        "RELEASE_BUILD_SELF_TEST: PASS" in builder.stdout,
        "release builder self-test missing PASS marker",
    )


def validate_specialized_capability_behavior_audits() -> None:
    audits = [
        ("director harness", "scripts/dircreative_director_harness_audit.py", "DIRECTOR_HARNESS_AUDIT: PASS"),
        ("creative copy deck", "scripts/dircreative_creative_copy_deck_audit.py", "CREATIVE_COPY_DECK_AUDIT: PASS"),
        ("model capability", "scripts/dircreative_model_capability_audit.py", "MODEL_CAPABILITY_AUDIT: PASS"),
    ]
    for label, script, marker in audits:
        require_path(script)
        proc = run(["python3", script])
        require(
            proc.returncode == 0,
            f"{label} behavior audit failed:\n{proc.stderr}\n{proc.stdout}",
        )
        require(marker in proc.stdout, f"{label} behavior audit missing PASS marker")


def validate_live_acceptance_rehearsal() -> None:
    text = require_path("examples/live-acceptance-rehearsal/01-chat-transcript.md").read_text(encoding="utf-8")
    required_terms = [
        "阶段: 真实聊天验收预演",
        "阶段: 验收入口",
        "阶段: 想法读取",
        "阶段: 导演组会议",
        "阶段: 故事确认",
        "阶段: 脚本确认",
        "阶段: 分镜头确认",
        "阶段: 参考图方案",
        "阶段: 出图执行建议",
        "阶段: 视频生成建议",
        "阶段: QA 与重试规则",
        "反驳型议会审核",
        "用户视角、影视专家视角、产品经理视角、Skill 开发者视角、代码研究员视角",
        "一次性 worker 用完会归档",
        "模拟用户选择",
        "不写 live-user-acceptance.yaml",
        "未写 live-user-acceptance.yaml: true",
        "不计入真实验收: true",
        "PASS_FOR_REHEARSAL",
        "character_identity_reference_drift",
        "scene_geography_reference_drift",
        "reference_role_label_hierarchy_wrong",
        "storyboard_information_density_too_low",
        "storyboard_board_misread_by_video_model",
        "固定材质防伪影后缀默认关闭",
        "Seedance",
        "Kling",
        "Runway",
        "Veo",
        "skill_run_receipt",
    ]
    missing = [term for term in required_terms if term not in text]
    require(not missing, f"live acceptance rehearsal missing terms: {missing}")


def validate_assisted_generation_preflight_chat() -> None:
    text = require_path("examples/assisted-generation-preflight-chat/01-chat-transcript.md").read_text(encoding="utf-8")
    required_terms = [
        "阶段: 出图请求前置拦截",
        "看看图",
        "当前不能直接出图",
        "最早未确认的创意 gate",
        "阶段: 分镜头确认",
        "阶段: 参考图方案",
        "阶段: 出图执行建议",
        "pre_generation_contract.status: pass",
        "后台证据已准备",
        "不让用户审批 raw JSON/YAML",
        "CHARACTER IDENTITY REFERENCE",
        "direct video input policy",
        "阶段: assisted_generation 前置结果",
        "真实工具调用: false",
        "assisted_generation_status: blocked_for_real_authorization",
        "blocked_media: image_generation, video_generation",
        "只生成 CHARACTER IDENTITY REFERENCE",
        "post-generation self-QA",
        "character_identity_reference_drift",
        "reference_role_label_hierarchy_wrong",
        "fish_scale_material_artifact",
        "storyboard/motion page 不能作为 Kling/Runway direct I2V input",
        "失败图不能进入用户锁定",
        "PASS",
    ]
    missing = [term for term in required_terms if term not in text]
    require(not missing, f"assisted generation preflight chat missing terms: {missing}")


def validate_live_user_acceptance_gate() -> None:
    gate = require_path("docs/film-preproduction/live-user-acceptance-gate.md").read_text(encoding="utf-8")
    runbook = require_path("docs/film-preproduction/live-chat-acceptance-runbook.md").read_text(encoding="utf-8")
    template_path = require_path("docs/film-preproduction/templates/live-user-acceptance.template.yaml")
    template = load_yaml(template_path)
    combined = f"{gate}\n{runbook}\n{template_path.read_text(encoding='utf-8')}"
    required_terms = [
        "real user acceptance pass",
        "live-user-acceptance.yaml",
        "live-user-acceptance.template.yaml",
        "Operator Prompt",
        "Required Chat Stages To Show",
        "User Decision Requirements",
        "Receipt Creation Rule",
        "Final Verification",
        "反驳型议会审核",
        "Codex worker thread",
        "一次性 worker 用完会归档",
        "GOAL_COMPLETE: YES",
        "GOAL_COMPLETE: NO",
        "Not Enough To Close",
        "simulated_fixture",
        "terminal demo",
        "explicitly accepts",
        "council_adversarial_review",
        "thread_orchestration",
        "thread_audit_passed",
        "council_adversarial_review_boundary",
        "thread_orchestration_cleanup",
    ]
    missing = [term for term in required_terms if term not in combined]
    require(not missing, f"live user acceptance gate missing terms: {missing}")
    gate_scope_terms = [
        "council adversarial review evidence",
        "Codex thread orchestration evidence",
        "`council_adversarial_review_boundary`",
        "`thread_orchestration_cleanup`",
    ]
    missing_gate_scope = [term for term in gate_scope_terms if term not in gate]
    require(not missing_gate_scope, f"live user acceptance gate doc missing scope terms: {missing_gate_scope}")

    acceptance = template.get("user_acceptance", {})
    chat_evidence = template.get("chat_evidence", {})
    council = chat_evidence.get("council_adversarial_review", {})
    thread = chat_evidence.get("thread_orchestration", {})
    accepted_scope = template.get("accepted_scope", {})
    policy = template.get("acceptance_run", {}).get("template_policy", {})
    require(template.get("artifact", {}).get("status") == "template", "acceptance template must keep artifact.status: template")
    require(template.get("chat_evidence", {}).get("evidence_source") == "", "acceptance template evidence_source must start empty")
    require(acceptance.get("status") == "not_accepted", "acceptance template must not be accepted")
    require(acceptance.get("accepted_by_user") is False, "acceptance template accepted_by_user must be false")
    require(acceptance.get("real_user_co_creation_verified") is False, "acceptance template real_user_co_creation_verified must be false")
    require(set(council.get("viewpoints", [])) == {"user", "professional_film_expert", "product_manager", "skill_developer", "code_researcher"}, "acceptance template must include council viewpoints")
    require(thread.get("thread_audit_passed") is False, "acceptance template thread audit must start false")
    require(thread.get("disposable_workers_archived") is False, "acceptance template worker archive status must start false")
    require(thread.get("unintended_worker_worktrees_present") is False, "acceptance template unintended worktree status must start false")
    require("council_adversarial_review_boundary" in accepted_scope.get("checklist", []), "acceptance template missing council accepted scope")
    require("thread_orchestration_cleanup" in accepted_scope.get("checklist", []), "acceptance template missing thread accepted scope")
    require(policy.get("copy_only_after_real_user_acceptance") is True, "acceptance template must require real user acceptance")
    require(policy.get("simulated_fixture_allowed") is False, "acceptance template must forbid simulated fixture")
    require(policy.get("terminal_only_demo_allowed") is False, "acceptance template must forbid terminal-only demo")
    require(template.get("qa_gate", {}).get("status") == "needs_user", "acceptance template qa_gate must need user")


def validate_prompt_system_fixture() -> None:
    proc = run(["python3", "scripts/dircreative_prompt_fixture_audit.py"])
    require(
        proc.returncode == 0,
        f"prompt-system fixture audit failed:\n{proc.stderr}\n{proc.stdout}",
    )
    require("PROMPT_FIXTURE_AUDIT: PASS" in proc.stdout, "prompt fixture audit missing PASS marker")
    for adapter in ["seedance", "kling", "runway", "sora", "veo", "generic"]:
        require(f'"adapter": "{adapter}"' in proc.stdout, f"prompt fixture audit lacks {adapter} matrix")


def main() -> int:
    global ALLOW_DEVELOPMENT_INSTALL, INSTALLED_PACKAGE_VALIDATION
    parser = argparse.ArgumentParser(description="Validate the DIRcreative source or installed package.")
    parser.add_argument(
        "--allow-development-install",
        action="store_true",
        help="Allow only a metadata-free non-formal staging install; formal metadata remains strict.",
    )
    parser.add_argument(
        "--installed-package",
        action="store_true",
        help="Validate installed runtime behavior; source-only parity is verified by the caller.",
    )
    args = parser.parse_args()
    installed_runtime_layout = (ROOT / "SKILL.md").is_file() and not (
        ROOT / "skills/dircreative/SKILL.md"
    ).exists()
    if args.allow_development_install and not args.installed_package:
        parser.error("--allow-development-install requires --installed-package")
    if args.installed_package and not installed_runtime_layout:
        parser.error("--installed-package requires an installed runtime layout")
    ALLOW_DEVELOPMENT_INSTALL = args.allow_development_install
    INSTALLED_PACKAGE_VALIDATION = args.installed_package
    checks = [
        ("required paths", validate_required_paths),
        ("YAML and JSON parse", validate_yaml_and_json_parse),
        ("placeholder scan", validate_placeholder_scan),
        ("source registries", validate_source_registries),
        ("reference policy docs", validate_reference_policy_docs),
        ("production prompt discipline", validate_production_prompt_discipline),
        ("AI video prompt community lessons", validate_ai_video_prompt_community_lessons),
        ("duration unit policy", validate_duration_unit_policy),
        ("reference failure types", validate_reference_failure_types),
        ("TapNow canvas lessons", validate_tapnow_canvas_lessons),
        ("professional agent voice", validate_professional_agent_voice),
        ("story/script tension rules", validate_story_script_tension_rules),
        ("client film hard gates", validate_client_film_hard_gates_docs),
        ("production demo retrospective", validate_production_demo_retrospective),
        ("council adversarial review", validate_council_adversarial_review),
        ("thread orchestration protocol", validate_thread_orchestration_protocol),
        ("thread dispatch record fixtures", validate_thread_dispatch_record_fixtures),
        ("workspace cleanliness protocol", validate_workspace_cleanliness_protocol),
        ("runtime state governance", validate_runtime_state_governance),
        ("objective requirement audit receipt", validate_objective_requirement_audit_receipt),
        ("release gate technical readiness receipt", validate_release_gate_technical_readiness_receipt),
        ("skills", validate_skills),
        ("activation policy", validate_activation_policy),
        ("routing and context budget", validate_context_budget),
        ("dynamic visual Skill Stack", validate_skill_stack),
        ("staged asset foundation pass", validate_asset_foundation_pass),
        ("AI-film asset stress test", validate_ai_film_asset_stress_test),
        ("AI-film production ledger", validate_ai_film_production_ledger),
        ("script-to-Seedance handoff", validate_script_to_seedance_handoff),
        ("storyboard-frame Jingzao handoff", validate_storyboard_frame_handoff),
        ("whole-film visual asset plan", validate_visual_asset_plan),
        ("workspace hygiene runtime", validate_workspace_hygiene_runtime),
        ("headless input-to-answer acceptance", validate_headless_acceptance),
        ("delivery and ownership boundaries", validate_delivery_boundaries),
        ("content-first answer behavior", validate_content_first_behavior),
        ("v2 interaction contract", validate_v2_interaction_contract),
        ("ADCO native integration contract", validate_adco_native_integration_contract),
        ("project AGENTS generator", validate_project_agents_script),
        ("director room fixture", validate_director_room_fixture),
        ("ad reference pack fixtures", validate_ad_reference_pack_fixtures),
        ("workbench docs", validate_workbench_docs),
        ("chat interface", validate_chat_interface),
        ("chat visualization contract", validate_chat_visualization_contract),
        ("chat acceptance checklist", validate_chat_acceptance_checklist),
        ("goal-mode simulation protocol", validate_goal_mode_simulation_protocol),
        ("isolated user simulation", validate_isolated_user_simulation),
        ("complete idea segmentation test", validate_complete_idea_segmentation_test),
        ("assisted generation receipt", validate_assisted_generation_receipt),
        ("generation QA character drift approved fixture", validate_generation_qa_character_drift_approved_fixture),
        ("pre-generation contract negative fixture", validate_pre_generation_contract_negative_fixture),
        ("pre-generation contract weak fixture", validate_pre_generation_contract_weak_fixture),
        ("pre-generation contract prompt mismatch fixture", validate_pre_generation_contract_prompt_mismatch_fixture),
        ("pre-generation contract project title dominant fixture", validate_pre_generation_contract_project_title_dominant_fixture),
        ("image generation capability negative fixture", validate_image_generation_capability_negative_fixture),
        ("image prompt audio leak negative fixture", validate_image_prompt_audio_leak_negative_fixture),
        ("image prompt bad fragment negative fixture", validate_image_prompt_bad_fragment_negative_fixture),
        ("video prompt missing reference bindings fixture", validate_video_prompt_missing_reference_bindings_fixture),
        ("video prompt binding wrong model fragment fixture", validate_video_prompt_binding_wrong_model_fragment_fixture),
        ("co-creation needs revision downstream fixture", validate_co_creation_needs_revision_downstream_fixture),
        ("video prompt duplicate fixture", validate_video_prompt_duplicate_fixture),
        ("video prompt inline anti-misread fixture", validate_video_prompt_inline_anti_misread_fixture),
        ("video prompt unlocked direct input fixture", validate_video_prompt_unlocked_direct_input_fixture),
        ("reference pack duplicate role fixture", validate_reference_pack_duplicate_role_fixture),
        ("reference pack storyboard direct input fixture", validate_reference_pack_storyboard_direct_input_fixture),
        ("shot list duration mismatch fixture", validate_shot_list_duration_mismatch_fixture),
        ("shot list timecode gap fixture", validate_shot_list_timecode_gap_fixture),
        ("shot list low information density fixture", validate_shot_list_low_information_density_fixture),
        ("client film gate contract fixtures", validate_client_film_gate_contract_fixtures),
        (
            "shot lists",
            lambda: [
                validate_shot_list(path)
                for path in [
                    "examples/cyber-courier/13-shot-list.yaml",
                    "examples/product-ad-raincoat/06-shot-list.yaml",
                    "examples/zombie-cleaner-test/07-shot-list.yaml",
                    "examples/live-user-sim-noodle/07-shot-list.yaml",
                    "examples/complete-idea-segmentation-test/03-shot-list.yaml",
                ]
            ],
        ),
        (
            "prompt manifests",
            lambda: [
                validate_image_manifest("examples/cyber-courier/20-image-prompt-manifest.yaml", registry_pattern_ids()),
                validate_image_manifest("examples/product-ad-raincoat/08-image-prompt-manifest.yaml", registry_pattern_ids()),
                validate_video_manifest("examples/cyber-courier/21-video-prompt-manifest.yaml"),
                validate_video_manifest("examples/product-ad-raincoat/09-video-prompt-manifest.yaml"),
                validate_reference_pack_manifest("examples/cyber-courier/18-reference-pack-plan.yaml"),
                validate_reference_pack_manifest("examples/product-ad-raincoat/07-reference-pack-plan.yaml"),
                validate_sequence_plan("examples/product-ad-raincoat/10-sequence-plan.yaml"),
                validate_longform_reference_pack("examples/product-ad-raincoat/11-longform-reference-pack.yaml"),
                validate_image_manifest("examples/zombie-cleaner-test/11-image-prompt-manifest.yaml", registry_pattern_ids()),
                validate_video_manifest("examples/zombie-cleaner-test/13-video-prompt-manifest.yaml"),
                validate_reference_pack_manifest("examples/zombie-cleaner-test/10-reference-pack-plan.yaml"),
                validate_sequence_plan("examples/zombie-cleaner-test/08-sequence-plan.yaml"),
                validate_longform_reference_pack("examples/zombie-cleaner-test/12-longform-reference-pack.yaml"),
                validate_image_manifest("examples/live-user-sim-noodle/10-image-prompt-manifest.yaml", registry_pattern_ids()),
                validate_video_manifest("examples/live-user-sim-noodle/11-video-prompt-manifest.yaml"),
                validate_reference_pack_manifest("examples/live-user-sim-noodle/09-reference-pack-plan.yaml"),
            ],
        ),
        ("prompt-system fixture", validate_prompt_system_fixture),
        ("co-creation run", lambda: validate_co_creation_run("examples/zombie-cleaner-test/15-co-creation-run.yaml")),
        ("live user simulation run", lambda: validate_co_creation_run("examples/live-user-sim-noodle/15-co-creation-run.yaml")),
        ("complete idea co-creation run", lambda: validate_co_creation_run("examples/complete-idea-segmentation-test/15-co-creation-run.yaml")),
        ("goal-mode simulation co-creation run", lambda: validate_co_creation_run("examples/goal-mode-simulation-test/15-co-creation-run.yaml")),
        ("goal-mode rough idea co-creation run", lambda: validate_co_creation_run("examples/goal-mode-rough-idea-simulation-test/15-co-creation-run.yaml")),
        ("goal autorun commercial CP co-creation run", lambda: validate_co_creation_run("examples/goal-mode-autorun-commercial-cp-test/15-co-creation-run.yaml")),
        ("demo runner", validate_demo_runner),
        ("film/commercial quality audit", validate_quality_audit),
        ("Creative Production adapter audit", validate_creative_production_audit),
        ("Goal autorun audit", validate_goal_autorun_audit),
        ("loop engineering audit", validate_loop_engineering_audit),
        ("second-level dispatch audit", validate_second_level_dispatch_audit),
        ("readiness audit", validate_readiness_audit),
        ("goal completion audit", validate_goal_audit),
        ("objective completion audit", validate_objective_audit),
        ("current project progress", validate_current_project_progress),
        ("progress report", validate_progress_report),
        ("acceptance preflight", validate_acceptance_preflight),
        ("council audit", validate_council_audit),
        ("thread audit", validate_thread_audit),
        ("chat surface contract", validate_chat_surface_contract),
        ("chat surface order audit", validate_chat_surface_audit),
        ("installed release metadata", validate_installed_metadata),
        ("install parity audit", validate_install_parity_audit),
        ("release distribution contract", validate_release_distribution_contract),
        ("specialized capability behavior audits", validate_specialized_capability_behavior_audits),
        ("live acceptance rehearsal", validate_live_acceptance_rehearsal),
        ("assisted generation preflight chat", validate_assisted_generation_preflight_chat),
        ("live user acceptance gate", validate_live_user_acceptance_gate),
        ("visual dogfood pages", validate_visual_dogfood_pages),
        ("visual dogfood gstack receipt", validate_visual_dogfood_gstack_receipt),
        ("goal-mode visual dogfood receipt", validate_goal_mode_visual_dogfood_receipt),
        ("goal-mode rough idea visual dogfood receipt", validate_goal_mode_rough_idea_visual_dogfood_receipt),
        ("media-forward audit script", validate_media_forward_audit_script),
        ("release gate script", validate_release_gate_script),
        ("no media assets", validate_no_media_assets),
    ]
    if INSTALLED_PACKAGE_VALIDATION:
        checks = [item for item in checks if item[0] != "install parity audit"]
    try:
        for name, check in checks:
            check()
            print(f"ok {name}")
    except ValidationError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("ok DIRcreative project validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
