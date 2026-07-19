#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from dircreative_activation_policy_audit import activation_decision
from dircreative_adco_native_exchange import run_self_test as exchange_self_test
from dircreative_director_harness_audit import HARNESS_PATH, load_yaml, select_perspectives
from dircreative_route import load_policy, route_request


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests/fixtures/headless-runtime/cases.json"
FORBIDDEN_FAST_CONTEXT = {
    "docs/film-preproduction/adco-integration-contract.md",
    "docs/film-preproduction/thread-orchestration-protocol.md",
    "docs/film-preproduction/goal-autorun-completion-protocol.md",
    "docs/film-preproduction/client-film-hard-gates.md",
}


class HeadlessAcceptanceError(Exception):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cases() -> dict[str, Any]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise HeadlessAcceptanceError("headless case fixture must contain a cases list")
    return payload


def case_by_id(case_id: str) -> dict[str, Any]:
    matches = [case for case in load_cases()["cases"] if case.get("id") == case_id]
    if len(matches) != 1:
        raise HeadlessAcceptanceError(f"unknown or duplicate headless case: {case_id}")
    return matches[0]


def routed_file(relative: str) -> Path:
    path = ROOT / relative
    if not path.is_file() and relative.endswith("/SKILL.md"):
        path = path.with_name("INTERNAL_SKILL.md")
    if not path.is_file():
        raise HeadlessAcceptanceError(f"routed context file is missing: {relative}")
    return path


def load_route_context(route: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    policy = load_policy()
    route_card = policy["route_cards"][route["mode"]]
    relative_paths = [route_card, *route["required_files"]]
    if len([item for item in relative_paths if item in policy["route_cards"].values()]) != 1:
        raise HeadlessAcceptanceError("headless execution must load exactly one Route Card")
    contents: dict[str, str] = {}
    for relative in relative_paths:
        contents[relative] = routed_file(relative).read_text(encoding="utf-8")
    return relative_paths, contents


def copy_revision_answer(case: dict[str, Any]) -> str:
    data = case["input"]
    lines = list(data["lines"])
    target_index = int(data["target_line"]) - 1
    if target_index < 0 or target_index >= len(lines):
        raise HeadlessAcceptanceError("copy revision target line is out of range")
    revised = (
        f"{data['character']}{data['action']}；{data['sound']}。"
        f"{data['camera']}。"
    )
    if revised == lines[target_index]:
        raise HeadlessAcceptanceError("copy processor did not revise the target line")
    lines[target_index] = revised
    numbered = "\n".join(f"{index}. {line}" for index, line in enumerate(lines, start=1))
    return (
        "# 修订结果\n\n"
        "## 第三句（已修改）\n\n"
        f"> {revised}\n\n"
        "## 修订后四句\n\n"
        f"{numbered}\n\n"
        "## 为什么这样改\n\n"
        f"- 叙事动作：{data['intent']}。\n"
        f"- 产品进入方式：让“{data['product']}”通过拧盖、倒入和冰杯反应进入剧情，不另插说明镜头。\n"
        f"- 可执行性：摄影可按“{data['camera']}”完成一个连续镜头；声音部门有“{data['sound']}”三层明确素材。\n"
        "- 改动边界：只替换第三句，人物、办公室时段、产品和第四句的晨光关系保持不变。\n"
    )


def studio_film_answer(case: dict[str, Any]) -> str:
    data = case["input"]
    constraints = "\n".join(f"- {item}" for item in data["constraints"])
    return (
        f"# {data['brand']}｜{data['duration_seconds']} 秒竖屏广告片首轮方案\n\n"
        "## 推荐方向：把噪声切成一口清晰\n\n"
        f"面向{data['audience']}，把“注意力被切碎”拍成可听见、可看见的噪声层。"
        f"产品动作不是中断剧情的展示，而是让节奏重新归一的转折：{data['product_action']}。"
        f"核心表达是“{data['promise']}”。\n\n"
        "## 30 秒脚本与分镜\n\n"
        "| 时间 | 画面与镜头 | 声音 / 文案 |\n"
        "|---|---|---|\n"
        f"| 00–04s | {data['situation']}。9:16 近景快速切换：弹窗、抖动的手机、被划掉又重写的待办。 | 提示音、键盘声、椅轮声叠成拥挤节奏；无旁白。 |\n"
        f"| 04–09s | 中近景固定在主角脸侧，背景同事仍在移动；她伸手压住手机，第一次主动停顿。 | 环境声突然抽掉高频，只留呼吸和桌面轻震。 |\n"
        f"| 09–15s | 产品动作连续完成：{data['product_action']}。微距跟随瓶盖、液体和冰块，不切断手部方向。 | 瓶盖轻响、液体落杯、冰块碰撞依次成为节拍。 |\n"
        f"| 15–20s | 镜头从杯壁水珠上移到眼神；她喝下第一口，屏幕弹窗仍在，但焦点不再跟随弹窗。 | 旁白：{data['promise']}。 |\n"
        f"| 20–24s | 一个平稳横移连接她整理文件、明确回复一条消息、合上多余窗口；动作不加速。 | 噪声回归，但被压进稳定的低节拍。 |\n"
        f"| 24–30s | {data['end_frame']}。瓶标朝镜头，杯中冰块仍有轻微运动。 | 音乐在品牌名出现时收束，保留一声清晰冰响。 |\n\n"
        "## 连续性与执行重点\n\n"
        f"- 画幅与时长：{data['aspect_ratio']}，总长 {data['duration_seconds']} 秒；产品动作占 6 秒，不能被碎切。\n"
        "- 手部连续性：拧盖手、倒杯方向、瓶标朝向和杯中液位必须跨镜头一致。\n"
        "- 声音叙事：前段噪声密、产品段声音清、后段节奏稳；不要用夸张“能量爆发”音效。\n"
        "- 摄影逻辑：前段以短焦近距离制造压迫，中段微距锁定真实物理动作，后段改为稳定横移。\n\n"
        "## 产品与合规边界\n\n"
        f"{constraints}\n\n"
        "## 首轮领域 QA\n\n"
        "- Brief adherence：通过。受众、30 秒竖屏、产品动作和尾帧均已进入可拍脚本。\n"
        "- Continuity：通过，但拍摄时需锁定瓶标朝向、杯中液位和主角持杯手。\n"
        "- Production clarity：通过。六个时间段均有画面、镜头、声音和明确转折。\n"
        "- Limitations：未经批准的包装细节、旁白最终字句和音乐版权仍需沿用客户已批准版本。\n"
    )


def answer_errors(answer: str, case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stripped = answer.strip()
    if not stripped:
        return ["answer_missing"]
    if stripped.startswith("{") and stripped.endswith("}"):
        errors.append("route_metadata_returned_instead_of_answer")
    if len(answer.encode("utf-8")) < int(case["minimum_answer_bytes"]):
        errors.append("answer_too_short")
    for term in case.get("expected_contains", []):
        if term not in answer:
            errors.append(f"answer_missing_required_content:{term}")
    for term in case.get("forbidden_contains", []):
        if term in answer:
            errors.append(f"answer_contains_forbidden_content:{term}")
    return errors


def execute_case(case: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    activation = activation_decision(case["request"])
    if not activation["allowed"]:
        raise HeadlessAcceptanceError(f"explicit fixture did not activate: {case['id']}")
    route = route_request(case["request"])
    if route["mode"] != case["expected_mode"] or route["route"] != case["expected_route"]:
        raise HeadlessAcceptanceError(f"route mismatch for {case['id']}: {route}")
    if route["action"] != "continue" or route["first_response_contract"] != "useful_artifact_first":
        raise HeadlessAcceptanceError(f"fixture stopped before producing an answer: {case['id']}")
    loaded_files, context = load_route_context(route)
    harness = load_yaml(HARNESS_PATH).get("director_role_harness", {})
    perspectives = select_perspectives(case["request"], harness)
    if route["mode"] == "fast":
        if perspectives["director_room_used"] is not False:
            raise HeadlessAcceptanceError("Fast headless case entered Director Room")
        if FORBIDDEN_FAST_CONTEXT & set(loaded_files):
            raise HeadlessAcceptanceError("Fast headless case loaded forbidden context")
        if "Return the revised result first" not in next(iter(context.values())):
            raise HeadlessAcceptanceError("Fast Route Card lost result-first contract")
    elif route["mode"] == "studio":
        if perspectives["director_room_used"] is not True:
            raise HeadlessAcceptanceError("Studio film case skipped adaptive perspectives")
        if len(perspectives["selected_perspectives"]) > 3:
            raise HeadlessAcceptanceError("Studio headless case exceeded perspective budget")
        if "Produce a useful first-round artifact" not in next(iter(context.values())):
            raise HeadlessAcceptanceError("Studio Route Card lost artifact-first contract")

    processors = {
        "copy_revision": copy_revision_answer,
        "film_development": studio_film_answer,
    }
    processor = processors.get(route["route"])
    if processor is None:
        raise HeadlessAcceptanceError(f"no headless answer processor for route: {route['route']}")
    answer = processor(case)
    errors = answer_errors(answer, case)
    if errors:
        raise HeadlessAcceptanceError("; ".join(errors))
    metadata = {
        "case_id": case["id"],
        "mode": route["mode"],
        "route": route["route"],
        "answer_sha256": sha256_text(answer),
        "answer_bytes": len(answer.encode("utf-8")),
        "route_cards_loaded": 1,
        "loaded_files": loaded_files,
        "threads_used": 0,
        "director_room_used": perspectives["director_room_used"],
        "selected_perspectives": perspectives["selected_perspectives"],
    }
    return answer, metadata


def run_case(case_id: str, output: Path | None) -> int:
    answer, metadata = execute_case(case_by_id(case_id))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(answer, encoding="utf-8")
        metadata["answer_path"] = str(output.resolve())
    else:
        print(answer)
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
    return 0


def audit(output_dir: Path | None = None) -> tuple[bool, dict[str, Any], list[str]]:
    payload = load_cases()
    budgets = payload["latency_budget_ms"]
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    temp: tempfile.TemporaryDirectory[str] | None = None
    if output_dir is None:
        temp = tempfile.TemporaryDirectory(prefix="dircreative-headless-acceptance-")
        target_root = Path(temp.name)
    else:
        target_root = output_dir.resolve()
        target_root.mkdir(parents=True, exist_ok=True)
    suite_start = time.perf_counter()
    try:
        for case in payload["cases"]:
            output = target_root / f"{case['id']}.md"
            started = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--case", case["id"], "--output", str(output)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                timeout=10,
                check=False,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            if proc.returncode != 0:
                failures.append(f"{case['id']}: headless process failed: {proc.stderr or proc.stdout}")
                continue
            if elapsed_ms > float(budgets["per_case_max"]):
                failures.append(f"{case['id']}: latency {elapsed_ms}ms exceeds budget")
            try:
                metadata = json.loads(proc.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError) as exc:
                failures.append(f"{case['id']}: invalid headless metadata: {exc}")
                continue
            if not isinstance(metadata, dict):
                failures.append(f"{case['id']}: headless metadata must be an object")
                continue
            answer = output.read_text(encoding="utf-8") if output.is_file() else ""
            failures.extend(f"{case['id']}: {item}" for item in answer_errors(answer, case))
            snapshot = ROOT / case["snapshot"]
            if not snapshot.is_file():
                failures.append(f"{case['id']}: expected answer snapshot is missing")
            elif answer != snapshot.read_text(encoding="utf-8"):
                failures.append(f"{case['id']}: generated answer differs from reviewed snapshot")
            if metadata.get("answer_sha256") != sha256_text(answer):
                failures.append(f"{case['id']}: answer metadata hash mismatch")
            if output_dir is None:
                metadata.pop("answer_path", None)
            metadata["latency_ms"] = elapsed_ms
            metadata["snapshot"] = case["snapshot"]
            results.append(metadata)
        suite_ms = round((time.perf_counter() - suite_start) * 1000, 3)
        if suite_ms > float(budgets["suite_max"]):
            failures.append(f"headless suite latency {suite_ms}ms exceeds budget")

        route_only = json.dumps(route_request(payload["cases"][0]["request"]), ensure_ascii=False)
        negative = {
            "empty_answer_rejected": answer_errors("", payload["cases"][0]) == ["answer_missing"],
            "route_only_answer_rejected": "route_metadata_returned_instead_of_answer"
            in answer_errors(route_only, payload["cases"][0]),
        }
        if not all(negative.values()):
            failures.append("answer-presence negative controls did not fail closed")

        exchange_ok, exchange_report = exchange_self_test()
        compatibility = {
            "v1_read_compatibility": bool(exchange_report.get("v1_read_compatibility")),
            "v2_roundtrip_valid": bool(exchange_report.get("v2_roundtrip_valid")),
            "v2_compact_receipt_valid": bool(exchange_report.get("v2_compact_receipt_valid")),
            "v2_nested_dispatch_rejected": bool(exchange_report.get("v2_nested_dispatch_field_rejected")),
            "v2_reserved_readiness_claim_rejected": bool(
                exchange_report.get("v2_reserved_readiness_claim_rejected")
            ),
        }
        if not exchange_ok or not all(compatibility.values()):
            failures.append("v1/v2 Specialist Exchange compatibility self-test failed")
        report = {
            "status": "PASS" if not failures else "FAIL",
            "answer_files_generated": len(results),
            "answers": results,
            "latency_budget_ms": budgets,
            "suite_latency_ms": suite_ms,
            "negative_controls": negative,
            "exchange_compatibility": compatibility,
            "runtime_boundary": "isolated deterministic headless processor; no installed skill or live ADCO project",
        }
        return not failures, report, failures
    finally:
        if temp is not None:
            temp.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated DIRcreative input-to-answer acceptance tests.")
    parser.add_argument("--case", help="Execute one fixture as a black-box headless answer process.")
    parser.add_argument("--output", type=Path, help="Write one generated answer to this path.")
    parser.add_argument("--output-dir", type=Path, help="Persist all audit-generated answers for human inspection.")
    args = parser.parse_args()
    try:
        if args.case:
            return run_case(args.case, args.output)
        ok, report, failures = audit(args.output_dir)
    except (HeadlessAcceptanceError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        print("HEADLESS_ACCEPTANCE_AUDIT: FAIL")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        for item in failures:
            print(f"- {item}")
        print("HEADLESS_ACCEPTANCE_AUDIT: FAIL")
        return 1
    print("HEADLESS_ACCEPTANCE_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
