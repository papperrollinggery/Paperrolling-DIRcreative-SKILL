#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
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
from dircreative_visual_asset_plan import derive_plan, validate_plan


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests/fixtures/headless-runtime/cases.json"
FORBIDDEN_FAST_CONTEXT = {
    "docs/film-preproduction/adco-integration-contract.md",
    "docs/film-preproduction/thread-orchestration-protocol.md",
    "docs/film-preproduction/goal-autorun-completion-protocol.md",
    "docs/film-preproduction/client-film-hard-gates.md",
}
TIMECODE_RE = re.compile(
    r"^(\d{2}):([0-5]\d(?:\.\d+)?)-(\d{2}):([0-5]\d(?:\.\d+)?)$"
)


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


def client_story_answer(case: dict[str, Any]) -> str:
    data = case["input"]
    direction_sections: list[str] = []
    for index, direction in enumerate(data["directions"], start=1):
        direction_sections.append(
            f"## 方向{index}｜{direction['title']}\n\n"
            f"**观众变化**：{direction['audience_change']}\n\n"
            f"**开场**：{direction['start']}\n\n"
            f"**唯一核心动作**：{direction['action']}\n\n"
            f"**品牌因果角色**：{direction['brand_role']}\n\n"
            f"**结尾**：{direction['end']}\n\n"
            f"**声画推进**：{direction['sound_edit']}\n\n"
            f"**必须守住的规则**：{direction['world_rule']}\n"
        )
    pending = "\n".join(f"- {item}：待 ADCO 绑定客户原始证据；DIR 不推导、不代填。" for item in data["claims_pending"])
    return (
        f"# {data['brand']}｜双方向客户故事提案\n\n"
        f"面向{data['audience']}，本版只回答“观众会经历什么、品牌为什么不可替代”。"
        "两个方向各自保持完整的起点、行动和结果，不提前展开技术制作。\n\n"
        + "\n\n".join(direction_sections)
        + "\n\n## 两个方向的差异\n\n"
        f"- 方向一把重点放在“{data['directions'][0]['decision_value']}”，让观众先理解进入门槛如何被移除。\n"
        f"- 方向二把重点放在“{data['directions'][1]['decision_value']}”，让观众感受经营开始运转后的规模想象。\n"
        "- 二者不能混成一个中间方案：前者靠一个明确选择推进，后者靠跨时区的连续响应推进。\n\n"
        "## 客户事实边界\n\n"
        f"{pending}\n\n"
        "## 当前完成边界\n\n"
        "本版已形成可供客户比较的两条完整故事。结构完整只代表领域提案可讨论；"
        "不代表客户批准、资产获权、PPT 完成、FinalDelivery 就绪或可外发。\n"
    )
def load_json_object(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HeadlessAcceptanceError(f"cannot load TVC acceptance input {relative}: {exc}") from exc
    if not isinstance(payload, dict):
        raise HeadlessAcceptanceError(f"TVC acceptance input must be an object: {relative}")
    return payload


def tvc_case_data(
    case: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    data = case["input"]
    inventory_path = str(data["inventory"])
    inventory = load_json_object(inventory_path)
    shot_payload = load_json_object(str(data["shot_cards"]))
    if shot_payload.get("inventory") != inventory_path:
        raise HeadlessAcceptanceError("TVC shot cards are not bound to the selected inventory")
    cards = shot_payload.get("cards")
    if not isinstance(cards, list):
        raise HeadlessAcceptanceError("TVC shot card fixture must contain a cards list")
    expected_fields = {
        "shot_id",
        "timecode",
        "duration_seconds",
        "shot_design",
        "action",
        "sound_edit",
        "continuity_model",
    }
    inventory_shots = inventory.get("shots", [])
    expected_ids = [shot.get("shot_id") for shot in inventory_shots if isinstance(shot, dict)]
    actual_ids: list[str] = []
    duration = 0.0
    cursor = 0.0
    frame_rate = inventory.get("delivery_profile", {}).get("frame_rate_fps")
    if not isinstance(frame_rate, (int, float)) or isinstance(frame_rate, bool) or frame_rate <= 0:
        raise HeadlessAcceptanceError("TVC fixture has no valid frame rate")
    for index, card in enumerate(cards):
        if not isinstance(card, dict) or set(card) != expected_fields:
            raise HeadlessAcceptanceError(f"invalid TVC director shot card at index {index}")
        for field in expected_fields - {"duration_seconds"}:
            if not isinstance(card[field], str) or not card[field].strip():
                raise HeadlessAcceptanceError(f"empty TVC director shot-card field: {index}:{field}")
        seconds = card["duration_seconds"]
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
            raise HeadlessAcceptanceError(f"invalid TVC shot duration at index {index}")
        timecode_match = TIMECODE_RE.fullmatch(card["timecode"])
        if timecode_match is None:
            raise HeadlessAcceptanceError(f"invalid TVC timecode at index {index}")
        start = int(timecode_match.group(1)) * 60 + float(timecode_match.group(2))
        end = int(timecode_match.group(3)) * 60 + float(timecode_match.group(4))
        if abs(start - cursor) > 0.0001:
            raise HeadlessAcceptanceError(
                f"TVC timecode gap or overlap before {card['shot_id']}: {cursor} -> {start}"
            )
        if abs((end - start) - float(seconds)) > 0.0001:
            raise HeadlessAcceptanceError(
                f"TVC timecode duration mismatch on {card['shot_id']}"
            )
        frames = float(seconds) * float(frame_rate)
        if abs(frames - round(frames)) > 0.0001:
            raise HeadlessAcceptanceError(
                f"TVC shot duration is not frame-aligned at {frame_rate:g}fps: {card['shot_id']}"
            )
        actual_ids.append(card["shot_id"])
        duration += float(seconds)
        cursor = end
    if actual_ids != expected_ids or len(cards) != 24:
        raise HeadlessAcceptanceError("TVC director shot cards must cover S01-S24 exactly once and in order")
    if abs(duration - float(inventory.get("duration_seconds", 0))) > 0.001:
        raise HeadlessAcceptanceError(f"TVC director shot cards total {duration} seconds instead of 60")
    if abs(cursor - float(inventory.get("duration_seconds", 0))) > 0.001:
        raise HeadlessAcceptanceError(f"TVC final timecode ends at {cursor} seconds instead of 60")
    if sum(float(card["duration_seconds"]) for card in cards[-2:]) < 4.0:
        raise HeadlessAcceptanceError("TVC brand end frame is shorter than four seconds")
    shot_scenes = {
        shot["shot_id"]: shot["scene_id"]
        for shot in inventory_shots
        if isinstance(shot, dict) and isinstance(shot.get("shot_id"), str)
    }
    for unit in inventory.get("generation_units", []):
        if not isinstance(unit, dict):
            raise HeadlessAcceptanceError("invalid TVC generation unit")
        unit_scenes = {shot_scenes.get(shot_id) for shot_id in unit.get("shot_ids", [])}
        if None in unit_scenes or len(unit_scenes) != 1:
            raise HeadlessAcceptanceError(
                f"TVC generation unit crosses scene anchors: {unit.get('unit_id', 'unknown')}"
            )

    plan_base_dir = ROOT / Path(inventory_path).parent
    plan = derive_plan(
        inventory,
        inventory_file=Path(inventory_path).name,
        base_dir=plan_base_dir,
    )
    plan_errors, metrics = validate_plan(plan, base_dir=plan_base_dir)
    if plan_errors:
        raise HeadlessAcceptanceError("TVC visual asset plan is invalid: " + "; ".join(plan_errors))
    expected_metrics = {
        "duration_seconds": 60,
        "scenes": 4,
        "characters": 2,
        "shots": 24,
        "rhythm_points": 32,
        "assets": 50,
        "storyboard_frames": 24,
        "director_storyboard_pages": 4,
        "clean_video_inputs": 10,
    }
    drift = {
        key: (metrics.get(key), expected)
        for key, expected in expected_metrics.items()
        if metrics.get(key) != expected
    }
    if drift:
        raise HeadlessAcceptanceError(f"TVC acceptance scale drifted: {drift}")
    metrics["frame_aligned_shots"] = len(cards)
    return inventory, cards, plan, metrics


def studio_film_answer(case: dict[str, Any]) -> str:
    data = case["input"]
    inventory, cards, plan, metrics = tvc_case_data(case)
    constraints = "\n".join(f"- {item}" for item in data["constraints"])
    shot_rows = [
        "| 镜号 / 时间 | 摄影与构图 | 人物 / 产品动作 | 声音与剪辑 | 连续性 / 模型风险 |",
        "|---|---|---|---|---|",
    ]
    for card in cards:
        shot_rows.append(
            f"| {card['shot_id']} · {card['timecode']} · {card['duration_seconds']:g}s "
            f"| {card['shot_design']} | {card['action']} | {card['sound_edit']} "
            f"| {card['continuity_model']} |"
        )

    scene_names = {
        "radio-studio-night": "深夜电台",
        "station-concourse-rain": "雨夜车站",
        "night-bus-interior": "夜班巴士",
        "riverside-dawn": "黎明河岸",
    }
    scene_rows = []
    for scene in inventory["scenes"]:
        covered = [
            shot["shot_id"]
            for shot in inventory["shots"]
            if shot["scene_id"] == scene["id"]
        ]
        scene_rows.append(
            f"| {scene_names.get(scene['id'], scene['id'])} | {', '.join(covered)} | {scene['purpose']} |"
        )

    director_pages = []
    for asset in plan["assets"]:
        if asset["role"] == "professional_storyboard_motion_map":
            director_pages.append(
                f"- {asset['asset_id']}：{', '.join(asset['coverage']['shot_ids'])}；"
                "每格含时间码、景别/焦段、机位运动、调度、声画剪辑、连续性和模型风险。"
            )
    clean_inputs = []
    for asset in plan["assets"]:
        if asset["role"].startswith("clean_"):
            clean_inputs.append(
                f"- {asset['coverage']['generation_unit_ids'][0]}：{asset['role']}，"
                f"取自 {asset['coverage']['shot_ids'][0]}，无标题、字幕、镜号或 UI。"
            )
    generation_unit_ids = [unit["unit_id"] for unit in inventory["generation_units"]]
    generation_unit_range = f"{generation_unit_ids[0]}-{generation_unit_ids[-1]}"

    return (
        f"# {data['brand']}｜60 秒 16:9 广播 TVC 首轮完整方案\n\n"
        "## 推荐方向：赶上日出，也赶上彼此\n\n"
        f"面向{data['audience']}，把一次看似普通的收工变成一场有真实阻力的赴约。"
        f"核心表达是“{data['promise']}”。{data['story']}"
        "冷萃不是让人物突然获得能量的开关，而是父女两条时间线之间可见、可追踪的邀请物。\n\n"
        "## 交付基线\n\n"
        "- 介质：broadcast TVC；时长 60 秒；画幅 16:9；基线 1920x1080 / 25fps / 48kHz。\n"
        "- 安全区：action safe 90%，title safe 80%；S23-S24 连续构成 4.6 秒品牌尾帧。\n"
        "- 剪辑时间：24 镜时间码首尾连续，全部时长落在 25fps 整帧边界。\n"
        f"- 结构规模：4 个场景、2 名持续角色、24 个正式镜头、32 个节奏点 R01-R32、{metrics['generation_units']} 个场景内视频生成单元。\n"
        "- 当前状态：创意、逐镜和视觉资产计划为 `plan_complete`；目标电视台/平台母版参数仍需锁定。\n\n"
        "## 60 秒故事与节奏\n\n"
        "- 00:00-00:15.4 / R01-R08：深夜电台。直播倒计时、父亲留言、纸条与冷萃迫使林澈作出离开的选择。\n"
        "- 00:15.4-00:29.0 / R09-R16：雨夜车站。红伞建立视觉动机，错过列车形成真实挫折，末班巴士给出第二条行动路径。\n"
        "- 00:29.0-00:42.0 / R17-R24：夜班巴士。节奏降下来，第一口冷萃与父亲声音同步，但不产生功效式转变；夜色连续过渡至蓝调时刻。\n"
        "- 00:42.0-01:00.0 / R25-R32：黎明河岸。相见、两瓶并置、纸条回收，最后用 4.6 秒广播可读尾帧完成品牌收束。\n\n"
        "## 24 镜导演级脚本 / 分镜规格\n\n"
        + "\n".join(shot_rows)
        + "\n\n## 四个场景图必须锁定的空间\n\n"
        "| 场景图 | 覆盖镜头 | 必须锁定 |\n|---|---|---|\n"
        + "\n".join(scene_rows)
        + f"\n\n## 全片必须生成的 {metrics['assets']} 项视觉资产\n\n"
        f"- {metrics['character_identity_references']} 张角色 / appearance-state 身份参考图："
        "林澈的棚内、雨夜转场、黎明状态与父亲黎明状态分别锁定；同一角色跨状态保持脸、体型、发型和持物手一致。\n"
        f"- 1 张产品身份板：瓶型、黑盖、深色液体、白色标签、已开/未开状态。\n"
        f"- 2 张道具连续性板：纸条的折叠/展开/收入口袋状态；红伞的折叠/打开/湿润与右手归属。\n"
        f"- 4 张场景地理 / Camera-FOV 图：每个场景一张，不能用逐镜分镜图替代。\n"
        f"- 1 张全片灯光 / 材质 / 色彩风格板：夜红、雨面反射、巴士蓝调、黎明暖色连续过渡。\n"
        f"- 24 张逐镜分镜图：S01-S24 每镜恰好一张，不能用六格拼图代替独立文件。\n"
        f"- 4 页导演故事板 / motion map：每页 6 镜，覆盖 S01-S24，不得漏镜或重复。\n"
        f"- {metrics['clean_video_inputs']} 张干净视频输入帧：{generation_unit_range} 每个场景内生成单元一张已锁定首帧、关键帧或尾帧。\n"
        f"- 合计 {metrics['assets']} 项；场景图、逐镜分镜图、导演故事板与视频模型输入帧是四类不同交付物。\n\n"
        "## 导演故事板分页\n\n"
        + "\n".join(director_pages)
        + "\n\n## 视频生成单元与干净输入\n\n"
        + "\n".join(clean_inputs)
        + "\n\n## 声音结构\n\n"
        "- 电台段：台标、控制台底噪、父亲留言和纸张/开盖声形成信息层级；父亲只说必要的一句。\n"
        "- 车站段：雨、广播、关门警报与脚步建立阻力；列车门闭合时音乐缩成单一低脉冲。\n"
        "- 巴士段：引擎、雨刷、轮胎声构成慢节拍；第一口只承接情绪释放，不制造提神式音效。\n"
        "- 河岸段：河风、鸟声、脚步停止和两瓶落在栏杆上的声音接管叙事；尾帧品牌 mnemonic 在 48kHz 路径收束。\n\n"
        "## 产品、文字与合规边界\n\n"
        f"{constraints}\n\n"
        "## 首轮领域 QA 与完成边界\n\n"
        "- Brief adherence：通过。60 秒、16:9、四场景、两角色、24 镜、32 节奏点、广播尾帧与声音结构均已落入可执行方案。\n"
        f"- Coverage：通过。资产矩阵逐项覆盖场景、身份、S01-S24、四页导演故事板和 {generation_unit_range} 干净输入；生成单元不跨场景锚点。\n"
        "- Continuity：计划级通过。人物、产品、纸条、红伞、左右手、屏幕方向与夜到黎明状态均有明确锁点。\n"
        f"- Completion：当前只能声明 `plan_complete`。只有 {metrics['assets']} 项真实文件全部存在、逐项 QA 通过并与清单绑定后，才能声明全片生成完成；代表性样片不能声明全片生成完成。\n"
        "- Acceptance：电视台/平台的最终母版、响度、字幕、法律行和品牌批准尚未提供，因此不能声明 `accepted`。\n"
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
    if case.get("expected_deliverable_layer") and route["deliverable_layer"] != case["expected_deliverable_layer"]:
        raise HeadlessAcceptanceError(f"deliverable-layer mismatch for {case['id']}: {route}")
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
        if "Deliver a recommended concept and a usable first-round artifact" not in next(iter(context.values())):
            raise HeadlessAcceptanceError("Studio Route Card lost artifact-first contract")

    processors = {
        ("copy_revision", "bounded_output"): copy_revision_answer,
        ("film_development", "client_story"): client_story_answer,
        ("film_development", "full_preproduction"): studio_film_answer,
        ("film_development", "technical_production"): studio_film_answer,
    }
    processor = processors.get((route["route"], route["deliverable_layer"]))
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
        "deliverable_layer": route["deliverable_layer"],
        "shot_matrix_allowed": route["shot_matrix_allowed"],
        "answer_sha256": sha256_text(answer),
        "answer_bytes": len(answer.encode("utf-8")),
        "route_cards_loaded": 1,
        "loaded_files": loaded_files,
        "threads_used": 0,
        "director_room_used": perspectives["director_room_used"],
        "selected_perspectives": perspectives["selected_perspectives"],
    }
    if route["route"] == "film_development" and route["deliverable_layer"] in {
        "full_preproduction",
        "technical_production",
    }:
        inventory, cards, _plan, metrics = tvc_case_data(case)
        metadata.update(
            {
                "duration_seconds": inventory["duration_seconds"],
                "formal_shots": len(cards),
                "frame_aligned_shots": metrics["frame_aligned_shots"],
                "rhythm_points": metrics["rhythm_points"],
                "visual_assets_planned": metrics["assets"],
                "scene_references": metrics["scene_references"],
                "storyboard_frames": metrics["storyboard_frames"],
                "director_storyboard_pages": metrics["director_storyboard_pages"],
                "clean_video_inputs": metrics["clean_video_inputs"],
                "tvc_landscape_profile": inventory["delivery_profile"]["aspect_ratio"] == "16:9",
            }
        )
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

        tvc_case = next(case for case in payload["cases"] if case["id"] == "studio_complete_tvc")
        source_cards = load_json_object(str(tvc_case["input"]["shot_cards"]))
        timing_negative_controls: dict[str, bool] = {}
        with tempfile.TemporaryDirectory(prefix="dircreative-tvc-timing-") as timing_raw:
            timing_root = Path(timing_raw)
            timing_mutations = {
                "fractional_frame_rejected": (
                    0,
                    {"timecode": "00:00.0-00:02.5", "duration_seconds": 2.5},
                    "not frame-aligned",
                ),
                "timecode_gap_rejected": (
                    1,
                    {"timecode": "00:02.6-00:05.2"},
                    "gap or overlap",
                ),
            }
            for control_id, (card_index, mutation, expected_error) in timing_mutations.items():
                mutated_cards = copy.deepcopy(source_cards)
                mutated_cards["cards"][card_index].update(mutation)
                mutated_path = timing_root / f"{control_id}.json"
                mutated_path.write_text(
                    json.dumps(mutated_cards, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                mutated_case = copy.deepcopy(tvc_case)
                mutated_case["input"]["shot_cards"] = str(mutated_path)
                try:
                    tvc_case_data(mutated_case)
                except HeadlessAcceptanceError as exc:
                    timing_negative_controls[control_id] = expected_error in str(exc)
                else:
                    timing_negative_controls[control_id] = False
        if not all(timing_negative_controls.values()):
            failures.append("TVC timing negative controls did not fail closed")

        exchange_ok, exchange_report = exchange_self_test()
        compatibility = {
            "v1_read_compatibility": bool(exchange_report.get("v1_read_compatibility")),
            "v1_free_text_readiness_claims_rejected": bool(
                exchange_report.get("v1_free_text_readiness_claims_rejected")
            ),
            "v1_non_list_qa_fields_rejected": bool(
                exchange_report.get("v1_non_list_qa_fields_rejected")
            ),
            "v1_compound_readiness_assertions_in_questions_rejected": bool(
                exchange_report.get(
                    "v1_compound_readiness_assertions_in_questions_rejected"
                )
            ),
            "v1_actual_readiness_questions_allowed": bool(
                exchange_report.get("v1_actual_readiness_questions_allowed")
            ),
            "v2_roundtrip_valid": bool(exchange_report.get("v2_roundtrip_valid")),
            "v2_compact_receipt_valid": bool(exchange_report.get("v2_compact_receipt_valid")),
            "v2_nested_dispatch_rejected": bool(exchange_report.get("v2_nested_dispatch_field_rejected")),
            "v2_reserved_readiness_claim_rejected": bool(
                exchange_report.get("v2_reserved_readiness_claim_rejected")
            ),
            "v2_all_reserved_readiness_claims_rejected": bool(
                exchange_report.get("v2_all_reserved_readiness_claims_rejected")
            ),
            "v2_nested_reserved_readiness_claims_rejected": bool(
                exchange_report.get("v2_nested_reserved_readiness_claims_rejected")
            ),
            "v2_natural_language_readiness_claims_rejected": bool(
                exchange_report.get("v2_natural_language_readiness_claims_rejected")
            ),
            "v2_positive_readiness_claims_in_limitations_rejected": bool(
                exchange_report.get(
                    "v2_positive_readiness_claims_in_limitations_rejected"
                )
            ),
            "v2_negative_readiness_limitations_allowed": bool(
                exchange_report.get("v2_negative_readiness_limitations_allowed")
            ),
            "v2_declarative_readiness_claims_in_questions_rejected": bool(
                exchange_report.get(
                    "v2_declarative_readiness_claims_in_questions_rejected"
                )
            ),
            "v2_actual_readiness_questions_allowed": bool(
                exchange_report.get("v2_actual_readiness_questions_allowed")
            ),
            "v2_unknown_and_chinese_domain_checks_rejected": bool(
                exchange_report.get("v2_unknown_and_chinese_domain_checks_rejected")
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
            "tvc_timing_negative_controls": timing_negative_controls,
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
