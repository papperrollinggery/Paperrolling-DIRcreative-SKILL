#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "skills/dircreative/runtime/routing-policy.yaml"
CASES_PATH = ROOT / "tests/fixtures/routing/cases.json"
V2_HANDOFF_FIELDS = {
    "protocol_id",
    "contract_version",
    "task",
    "brief_snapshot",
    "locked_decisions",
    "requested_outputs",
    "quality_targets",
    "execution_mode",
}


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(POLICY_PATH)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"routing policy parse failed: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("routing policy must be a mapping")
    return data


def valid_v2_handoff(handoff: object) -> bool:
    if not isinstance(handoff, dict) or set(handoff) != V2_HANDOFF_FIELDS:
        return False
    return (
        handoff.get("protocol_id") == "adco.specialist-exchange"
        and handoff.get("contract_version") == "2.0"
        and handoff.get("execution_mode") == "inline"
        and all(isinstance(handoff.get(field), str) and handoff[field].strip() for field in ("task", "brief_snapshot"))
        and all(isinstance(handoff.get(field), list) for field in ("locked_decisions", "requested_outputs", "quality_targets"))
    )


def has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def classify_route(request: str, handoff: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    if handoff is not None:
        if valid_v2_handoff(handoff):
            return "adco_specialist_exchange", ["valid_adco_v2_handoff", "inline_execution"]
        return "source_maintenance", ["invalid_adco_handoff", "skill_runtime_forbidden"]

    text = " ".join(request.split())
    maintenance_target = has(
        text,
        r"(?:DIRcreative\s+Skill\s*(?:本身)?|DIR\s*(?:的)?\s*SKILL\.md|DIR\s*安装器|"
        r"DIRcreative\s*(?:源码|源代码|仓库)|Paperrolling-DIRcreative-SKILL|source\s+repo)",
    )
    maintenance_action = has(text, r"维护|优化|审查|调试|重构|测试|评估|修改|maintain|review|debug|refactor|test|evaluate|modify")
    if maintenance_target and maintenance_action:
        return "source_maintenance", ["repository_maintenance", "skill_runtime_forbidden"]

    if has(text, r"客户交付|客户可见|正式交付|client[- ]visible|client delivery|send[- ]ready"):
        return "client_delivery", ["client_delivery_intent"]
    if has(text, r"真实生成|生成授权|授权生成|generation authorization|authorize (?:real )?generation") or (
        has(text, r"(?:现在|立即|直接|马上|开始|(?<!申)请)\s*(?:真实)?生成|generate\s+now|start\s+generation")
        and not has(text, r"Prompt|提示词|方案|计划|plan")
    ):
        return "generation_authorization", ["real_generation_requires_authorization"]

    if has(
        text,
        r"方向(?:互不兼容|不可兼容|冲突)|不可兼容(?:的)?(?:创意)?方向|incompatible (?:creative )?directions?|material concept conflict",
    ):
        return "film_development", ["incompatible_creative_directions", "concept_lock_required"]

    bounded = has(
        text,
        r"第三句|一句|一段|单镜头|这个镜头|一个镜头|少量分镜|局部分镜|局部|"
        r"one sentence|one paragraph|single shot|this shot|few storyboards|bounded",
    )
    revision = has(text, r"修改|优化|调整|润色|改写|评审|补充|revise|rewrite|polish|adjust|review|improve")
    complete = has(text, r"完整|全套|多产物|概念\s*\+|故事\s*\+|脚本\s*\+\s*分镜|full|complete|multi[- ]artifact")

    if revision and (bounded or not complete):
        if has(text, r"Prompt|提示词"):
            return "prompt_revision", ["bounded_revision", "prompt_target"]
        if has(text, r"分镜|storyboard") and not has(text, r"脚本\s*\+\s*分镜"):
            return "storyboard_review", ["bounded_review", "storyboard_target"]
        if has(text, r"镜头|shot"):
            return "shot_optimization", ["bounded_revision", "shot_target"]
        if has(text, r"句|段|文案|脚本|copy|line|paragraph|script"):
            return "copy_revision", ["bounded_revision", "copy_target"]
        return "bounded_revision", ["bounded_revision"]

    if complete or has(text, r"广告片|品牌片|短片|film|commercial|故事|脚本|story|script"):
        return "film_development", ["multi_artifact_or_complete_creation"]
    return "bounded_revision", ["single_output_default"]


def route_request(request: str, handoff: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = load_policy()
    route, reason_codes = classify_route(request, handoff)
    config = policy["routes"][route]
    execution_context = (
        "orchestrated_worker"
        if route == "adco_specialist_exchange"
        else "repository_maintenance"
        if route == "source_maintenance"
        else "standalone_chat"
    )
    external_user_gate = config["external_user_gate"]
    if route == "film_development" and "incompatible_creative_directions" not in reason_codes:
        external_user_gate = None
        reason_codes = [*reason_codes, "no_material_blocker"]
    if route == "generation_authorization" and has(
        request,
        r"(?:现在|立即|直接|马上|开始|(?<!申)请)\s*(?:真实)?生成|(?:已|确认|明确)?授权(?:真实)?生成|"
        r"generate\s+now|start\s+generation|generation\s+authorized",
    ):
        external_user_gate = None
        reason_codes = [*reason_codes, "authorization_satisfied_by_current_request"]
    if route == "client_delivery" and has(
        request,
        r"(?:现在|立即|直接|正式)\s*(?:交付|发送|发给)客户|批准客户交付|客户交付已批准|"
        r"send\s+to\s+(?:the\s+)?client\s+now|client\s+delivery\s+approved",
    ):
        external_user_gate = None
        reason_codes = [*reason_codes, "approval_satisfied_by_current_request"]
    action = (
        "stop_skill_runtime"
        if route == "source_maintenance"
        else "stop_for_external_gate"
        if external_user_gate
        else "continue"
    )
    persistence = policy["interaction_contract"]["state_persistence"][config["mode"]]
    return {
        "execution_context": execution_context,
        "mode": config["mode"],
        "route": route,
        "required_files": config["required_files"],
        "optional_files": config["optional_files"],
        "external_user_gate": external_user_gate,
        "action": action,
        "first_response_contract": (
            "not_applicable"
            if action == "stop_skill_runtime"
            else "gate_question"
            if action == "stop_for_external_gate"
            else "useful_artifact_first"
        ),
        "reuse_known_brief": True,
        "state_persistence": persistence,
        "threads_allowed": config["threads_allowed"],
        "full_receipt_required": config["full_receipt_required"],
        "reason_codes": reason_codes,
    }


def self_test() -> list[str]:
    failures: list[str] = []
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        result = route_request(case["input"])
        for field in (
            "mode",
            "route",
            "external_user_gate",
            "action",
            "first_response_contract",
            "state_persistence",
        ):
            if field not in case:
                continue
            if result[field] != case[field]:
                failures.append(f"{case['id']}: {field}={result[field]} expected={case[field]}")
    handoff_path = ROOT / "tests/fixtures/activation-policy/valid-adco-v2-handoff.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    result = route_request("", handoff)
    if result["execution_context"] != "orchestrated_worker" or result["route"] != "adco_specialist_exchange":
        failures.append(f"valid ADCO handoff route mismatch: {result}")
    invalid = dict(handoff, execution_mode="codex_thread")
    if route_request("", invalid)["execution_context"] == "orchestrated_worker":
        failures.append("invalid ADCO handoff entered orchestrated_worker")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve one DIRcreative v2 route as stable JSON.")
    parser.add_argument("request", nargs="?", default="", help="User request text.")
    parser.add_argument("--handoff", type=Path, help="Specialist Exchange handoff JSON.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        if failures:
            print("DIRCREATIVE_ROUTE_SELF_TEST: FAIL")
            for failure in failures:
                print(f"- {failure}")
            return 1
        print("DIRCREATIVE_ROUTE_SELF_TEST: PASS")
        return 0
    handoff = json.loads(args.handoff.read_text(encoding="utf-8")) if args.handoff else None
    print(json.dumps(route_request(args.request, handoff), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
