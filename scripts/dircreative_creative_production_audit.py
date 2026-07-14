#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from dircreative_validation_harness import ROOT, Check, add_check, read, require_terms


ALLOWED_STATUSES = {
    "prompt_ready",
    "generated_candidate",
    "user_locked",
    "rejected",
    "external_pending",
    "external_imported",
}
LOCKED_GATES = [
    "story_locked",
    "script_locked",
    "shot_list_locked",
    "reference_pack_locked",
]


def load_yaml(path: str) -> dict[str, Any]:
    target = ROOT / path
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(target)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"YAML parse failed for {path}: {proc.stderr}")
    return json.loads(proc.stdout)


def validate_cp_receipt(path: str) -> None:
    data = load_yaml(path)
    adapter = data.get("creative_production_adapter", {})
    if not adapter:
        raise AssertionError(f"{path} missing creative_production_adapter")
    if adapter.get("visual_output_mode") != "assisted_generation":
        raise AssertionError(f"{path} must be assisted_generation")
    if adapter.get("creative_production_path") not in {"Mood boards", "Scenes", "Offers", "Ads", "Shots", "Generative Polish"}:
        raise AssertionError(f"{path} has invalid Creative Production path")

    authorization = adapter.get("user_authorization", {})
    if authorization.get("explicit") is not True:
        raise AssertionError(f"{path} missing explicit user authorization")

    gate_state = adapter.get("dircreative_gate_state", {})
    missing_locks = [gate for gate in LOCKED_GATES if gate_state.get(gate) is not True]
    if missing_locks:
        raise AssertionError(f"{path} missing locked upstream gates: {missing_locks}")
    if gate_state.get("pre_generation_contract_status") != "pass":
        raise AssertionError(f"{path} pre_generation_contract_status must be pass")

    review_surface = adapter.get("review_surface", {})
    if review_surface.get("primary") != "render_moodboard_board_widget":
        raise AssertionError(f"{path} must use render_moodboard_board_widget")
    if review_surface.get("widget_is_truth_source") is not False:
        raise AssertionError(f"{path} widget cannot be truth source")

    truth_source = adapter.get("truth_source", {})
    if truth_source.get("source_of_truth") != "dircreative_artifacts":
        raise AssertionError(f"{path} source_of_truth must be dircreative_artifacts")
    if truth_source.get("writeback_required") is not True:
        raise AssertionError(f"{path} must require writeback")

    candidates = adapter.get("generated_candidates", [])
    if not candidates:
        raise AssertionError(f"{path} must include generated candidates")
    for candidate in candidates:
        status = candidate.get("asset_output_status")
        if status not in ALLOWED_STATUSES:
            raise AssertionError(f"{path} invalid candidate status: {status}")
        if candidate.get("user_lock_status") == "locked" and candidate.get("qa_status") != "pass":
            raise AssertionError(f"{path} candidate locked before QA pass")
        if status == "generated_candidate" and candidate.get("user_lock_status") == "locked":
            raise AssertionError(f"{path} generated_candidate cannot also be user locked")

    qa = adapter.get("qa", {})
    for key in [
        "pre_generation_contract_checked",
        "widget_not_truth_source",
        "generated_candidate_not_user_locked",
        "self_qa_before_user_lock",
        "simulated_fixture_not_live_acceptance",
        "no_real_media_generated",
    ]:
        if qa.get(key) is not True:
            raise AssertionError(f"{path} QA missing or false: {key}")


def must_fail(path: str) -> None:
    try:
        validate_cp_receipt(path)
    except AssertionError:
        return
    raise AssertionError(f"{path} unexpectedly passed")


def main() -> int:
    checks: list[Check] = []

    add_check(
        checks,
        "Creative Production integration contract",
        "docs/film-preproduction/creative-production-integration.md",
        lambda: require_terms(
            read("docs/film-preproduction/creative-production-integration.md"),
            [
                "Creative Production is an execution and review adapter",
                "render_moodboard_board_widget",
                "widget_is_truth_source: false",
                "source_of_truth: dircreative_artifacts",
                "generated_candidate",
                "user_locked",
                "simulated_fixture",
                "GOAL_COMPLETE: YES",
            ],
            "creative production integration doc",
        ),
    )
    add_check(
        checks,
        "valid Creative Production receipt",
        "tests/fixtures/runtime/runs/creative-production-assisted-generation-fixture.yaml",
        lambda: validate_cp_receipt("tests/fixtures/runtime/runs/creative-production-assisted-generation-fixture.yaml"),
    )
    for path in [
        "tests/fixtures/invalid-creative-production-pre-gate.yaml",
        "tests/fixtures/invalid-creative-production-widget-truth.yaml",
        "tests/fixtures/invalid-creative-production-unreviewed-lock.yaml",
    ]:
        add_check(checks, f"negative fixture rejected: {Path(path).name}", path, lambda p=path: must_fail(p))
    add_check(
        checks,
        "root and prompt skills mention Creative Production boundary",
        "skills/dircreative + prompt/video/QA skills",
        lambda: require_terms(
            "\n".join(
                [
                    read("skills/dircreative/SKILL.md"),
                    read("skills/dircreative/image-prompt-compiler/SKILL.md"),
                    read("skills/dircreative/video-model-adapter/SKILL.md"),
                    read("skills/dircreative/generation-qa/SKILL.md"),
                ]
            ),
            [
                "creative-production-integration.md",
                "Creative Production",
                "render_moodboard_board_widget",
                "not the source of truth",
                "generated_candidate",
            ],
            "Creative Production skill boundary",
        ),
    )

    print("DIRcreative Creative Production Audit")
    print("=" * 72)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.label}")
        print(f"       evidence: {check.evidence}")
    failures = [check for check in checks if not check.ok]
    if failures:
        print("CREATIVE_PRODUCTION_AUDIT: FAIL")
        return 1
    print("adapter_source_of_truth: dircreative_artifacts")
    print("review_surface: render_moodboard_board_widget")
    print("live_acceptance_required: true")
    print("CREATIVE_PRODUCTION_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
