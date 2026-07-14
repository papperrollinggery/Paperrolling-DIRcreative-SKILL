#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_GATE_TYPES = [
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


class RunError(Exception):
    pass


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
        raise RunError(f"yaml parse failed for {rel(path)}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def example_dir(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / value
    if path.is_file():
        path = path.parent
    if not path.exists():
        raise RunError(f"missing example path: {value}")
    return path


def co_creation_path(example: Path) -> Path:
    path = example / "15-co-creation-run.yaml"
    if not path.exists():
        raise RunError(f"missing co-creation run file: {rel(path)}")
    return path


def assisted_generation_receipts(example: Path) -> list[tuple[Path, dict[str, Any]]]:
    example_key = rel(example)
    run_dir = ROOT / ".dircreative" / "runs"
    receipts: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(run_dir.glob("*.yaml")):
        data = load_yaml(path)
        run_data = data.get("run", {})
        if run_data.get("source_example") == example_key:
            receipts.append((path, data))
    return receipts


def validate_gate_run(data: dict[str, Any]) -> list[str]:
    run = data.get("co_creation_run", {})
    gates = data.get("gates", [])
    errors: list[str] = []
    gate_types = {gate.get("gate_type") for gate in gates}
    missing = [gate for gate in REQUIRED_GATE_TYPES if gate not in gate_types]
    if missing:
        errors.append(f"missing gates: {', '.join(missing)}")

    run_type = run.get("run_type")
    simulated_allowed = run.get("simulated_choices_allowed")
    real_user_verified = run.get("real_user_co_creation_verified")
    if run_type == "live_user_run" and simulated_allowed:
        errors.append("live_user_run cannot allow simulated choices")
    if run_type == "live_user_run" and not real_user_verified:
        errors.append("live_user_run must verify real user co-creation")
    if run_type == "dry_run_fixture" and real_user_verified:
        errors.append("dry_run_fixture cannot claim real user co-creation")

    for gate in gates:
        gate_id = gate.get("gate_id", "unknown")
        source = gate.get("decision_source")
        status = gate.get("status")
        if gate.get("gate_type") in REQUIRED_GATE_TYPES and source == "system_default":
            errors.append(f"{gate_id} uses system_default for a creative gate")
        if status == "approved" and source == "pending":
            errors.append(f"{gate_id} is approved but decision source is pending")
        if source == "simulated_fixture" and run_type != "dry_run_fixture":
            errors.append(f"{gate_id} uses simulated_fixture outside a dry run")
        if status == "pending" and "media_generation" not in gate.get("blocks", []):
            if gate.get("gate_type") in {"clean_frame_gate", "video_prompt_gate"}:
                errors.append(f"{gate_id} must block media_generation while pending")
    return errors


def status(args: argparse.Namespace) -> int:
    example = example_dir(args.example)
    data = load_yaml(co_creation_path(example))
    receipts = assisted_generation_receipts(example)
    errors = validate_gate_run(data)
    run = data["co_creation_run"]
    gates = data.get("gates", [])

    print(f"PROJECT: {run.get('project_title')}")
    print(f"RUN_TYPE: {run.get('run_type')}")
    print(f"VISUAL_OUTPUT_MODE: {run.get('visual_output_mode')}")
    print(f"LONGFORM_MODE: {run.get('longform_generation_mode')}")
    print(f"REAL_USER_CO_CREATION_VERIFIED: {run.get('real_user_co_creation_verified')}")
    print("")
    print("GATES:")
    for gate in gates:
        marker = "BLOCKS_MEDIA" if "media_generation" in gate.get("blocks", []) else "ok"
        print(
            f"- {gate.get('gate_type')}: {gate.get('status')} "
            f"[{gate.get('decision_source')}] {marker}"
        )
        selected = gate.get("selected_option")
        if selected:
            print(f"  selected: {selected}")
    if receipts:
        print("")
        print("ASSISTED_GENERATION_RECEIPTS:")
        for receipt_path, receipt_data in receipts:
            artifact = receipt_data.get("artifact", {})
            receipt_run = receipt_data.get("run", {})
            human_review = receipt_data.get("human_review", {})
            assets = receipt_data.get("assets", [])
            direct_ready = [
                asset.get("asset_id")
                for asset in assets
                if asset.get("direct_video_input") is True
                and asset.get("user_lock_status") not in {"rejected_for_revision", "rejected"}
                and asset.get("usable_for_next_step") is not False
            ]
            rejected = [
                asset.get("asset_id")
                for asset in assets
                if asset.get("user_lock_status") in {"rejected_for_revision", "rejected"}
            ]
            print(f"- {artifact.get('artifact_id')}: {artifact.get('status')}")
            print(f"  receipt: {rel(receipt_path)}")
            print(f"  visual_output_mode: {receipt_run.get('visual_output_mode')}")
            print(f"  assets_registered: {len(assets)}")
            print(f"  human_review_verdict: {human_review.get('verdict')}")
            print(f"  rejected_assets: {', '.join(rejected) if rejected else 'none'}")
            print(f"  direct_video_candidates: {', '.join(direct_ready) if direct_ready else 'none'}")
            print(f"  video_generated: {receipt_run.get('video_generated')}")
            print(f"  user_lock_required_before_video: {receipt_run.get('user_lock_required_before_video')}")
    print("")
    if errors:
        print("STATUS: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("STATUS: PASS")
    if run.get("run_type") == "dry_run_fixture":
        print("NOTE: fixture proves file flow only. Live user co-creation is not verified.")
    if receipts:
        print("NOTE: generated image candidates are registered. Rejected assets cannot be used for video.")
    pending = [gate for gate in gates if gate.get("status") == "pending"]
    if receipts:
        receipt_question = receipts[0][1].get("next_user_decision", {}).get("question")
        print("NEXT_USER_DECISION:")
        print(f"- {receipt_question}")
    elif pending:
        print("NEXT_USER_DECISION:")
        first = pending[0]
        print(f"- {first.get('gate_type')}: choose one option before media generation")
        for option in first.get("options_presented", []):
            print(f"  - {option}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect DIRcreative co-creation run state.")
    sub = parser.add_subparsers(dest="command", required=True)
    status_parser = sub.add_parser("status", help="Show workflow gates and whether media is blocked.")
    status_parser.add_argument("--example", required=True, help="Example directory or co-creation run file.")
    status_parser.set_defaults(func=status)
    args = parser.parse_args()
    try:
        return args.func(args)
    except RunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
