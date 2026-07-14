#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "examples" / "isolated-user-simulation-test" / "01-simulation-pack.yaml"
REQUIRED_TYPES = {
    "rough_idea",
    "complete_idea",
    "longform_request",
    "image_request",
    "midstream_change",
}


class SimulationError(Exception):
    pass


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
        raise SimulationError(proc.stderr.strip())
    return json.loads(proc.stdout)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SimulationError(message)


def has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def validate_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    root = pack.get("simulation_pack", {})
    require(root.get("run_type") == "isolated_simulation_fixture", "run_type must be isolated_simulation_fixture")
    require(root.get("real_user_co_creation_verified") is False, "simulation cannot verify real user co-creation")
    require(root.get("live_user_acceptance_receipt_written") is False, "simulation cannot write live acceptance receipt")
    require(root.get("real_media_generated") is False, "simulation cannot generate real media")
    require(root.get("scoring_hidden_from_dircreative") is True, "scoring must be hidden from DIRcreative")
    require(root.get("standard_answer_hidden_from_dircreative") is True, "standard answers must be hidden from DIRcreative")

    scenarios = root.get("scenarios", [])
    require(len(scenarios) >= 5, "simulation must include at least five scenarios")
    found_types = {scenario.get("test_type") for scenario in scenarios}
    missing_types = REQUIRED_TYPES - found_types
    require(not missing_types, f"missing scenario types: {sorted(missing_types)}")

    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        sid = scenario.get("id", "")
        require(sid, "scenario missing id")
        require(scenario.get("user_messages"), f"{sid} missing user messages")
        response = scenario.get("dircreative_response", "")
        require("阶段:" in response, f"{sid} missing visible stage")
        require("智能体创作内容" in response, f"{sid} missing creative content")
        require("专业判断" in response, f"{sid} missing professional judgment")
        require("用户确认点" in response, f"{sid} missing user confirmation point")
        require(scenario.get("simulated_user_feedback", {}).get("satisfied") in {True, False}, f"{sid} missing simulated satisfaction")
        review = scenario.get("independent_review", {})
        require("root_cause" in review, f"{sid} missing reviewer root cause")
        require(review.get("repair_required") in {True, False}, f"{sid} missing repair decision")

        if scenario.get("test_type") == "longform_request":
            require(
                has_all(response, ["故事总时长", "每组视频生成上限", "5-15秒"]),
                "longform response must separate story duration from 15s generation units",
            )
        if scenario.get("test_type") == "image_request":
            require(
                has_all(response, ["当前不能直接出图", "pre_generation_contract.status: pass", "当前无真实图片/视频生成"]),
                "image request response must block real media and name the contract",
            )
        if scenario.get("test_type") == "midstream_change":
            require(
                has_all(response, ["核心前提变更", "stale", "不能继续拿去生成"]),
                "midstream change response must invalidate downstream artifacts",
            )

        results.append(
            {
                "id": sid,
                "type": scenario.get("test_type"),
                "satisfied": scenario.get("simulated_user_feedback", {}).get("satisfied"),
                "repair_required": review.get("repair_required"),
            }
        )

    return results


def main() -> int:
    pack = load_yaml(PACK)
    results = validate_pack(pack)
    root = pack["simulation_pack"]
    summary = root.get("reviewer_summary", {})

    print("DIRcreative Isolated User Simulation")
    print("=" * 72)
    print(f"run_id: {root.get('run_id')}")
    print("real_user_co_creation_verified: false")
    print("live_user_acceptance_receipt_written: false")
    print("real_media_generated: false")
    print(f"overall_verdict: {summary.get('overall_verdict')}")
    print()
    print("Scenarios")
    for result in results:
        print(
            f"- {result['id']}: type={result['type']} "
            f"satisfied={str(result['satisfied']).lower()} "
            f"repair_required={str(result['repair_required']).lower()}"
        )
    print()
    print("Repairs Made")
    for item in summary.get("repairs_made", []):
        print(f"- {item}")
    print()
    print("Remaining Risks")
    for item in summary.get("remaining_risks", []):
        print(f"- {item}")
    print("ISOLATED_USER_SIMULATION: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SimulationError as exc:
        print(f"ISOLATED_USER_SIMULATION: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1)
