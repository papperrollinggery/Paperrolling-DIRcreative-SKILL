#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = "examples/live-user-sim-noodle"


class DemoError(Exception):
    pass


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def resolve_example(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise DemoError(f"missing example directory: {value}")
    if not path.is_dir():
        raise DemoError(f"example must be a directory: {value}")
    return path


def require_file(example: Path, name: str) -> Path:
    path = example / name
    if not path.exists():
        raise DemoError(f"missing file: {rel(path)}")
    return path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
        raise DemoError(f"yaml parse failed for {rel(path)}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*\n(?P<body>.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    body = match.group("body")
    for marker in ["\nskill_run_receipt:", "\nartifact:"]:
        if marker in body:
            body = body.split(marker, 1)[0]
    return body.strip()


def subsection(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^### {re.escape(heading)}\s*\n(?P<body>.*?)(?=^## |^### |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    body = match.group("body")
    for marker in ["\nskill_run_receipt:", "\nartifact:"]:
        if marker in body:
            body = body.split(marker, 1)[0]
    return body.strip()


def compact(value: str, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def indent_lines(text: str, prefix: str = "  ") -> list[str]:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    return [prefix + line if line else "" for line in lines]


def gate_by_type(co_run: dict[str, Any], gate_type: str) -> dict[str, Any]:
    for gate in co_run.get("gates", []):
        if gate.get("gate_type") == gate_type:
            return gate
    return {}


def yn(value: bool) -> str:
    return "是" if value else "否"


def print_header(title: str) -> None:
    print("")
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_subheader(title: str) -> None:
    print("")
    print(f"## {title}")


def print_options(gate: dict[str, Any]) -> None:
    for idx, option in enumerate(gate.get("options_presented", []), start=1):
        print(f"  {idx}. {option}")
    print(f"  [模拟用户选择] {gate.get('selected_option', '')}")
    if gate.get("rationale"):
        print(f"  选择理由: {gate['rationale']}")


def direct_input_note(asset: dict[str, Any]) -> str:
    policy = asset.get("direct_input_policy", {})
    risky = []
    for model in ["seedance", "kling", "runway", "veo"]:
        value = policy.get(model)
        if value in {"forbidden", "planning_only", "reference_only", "element_only", "conditional"}:
            risky.append(f"{model}: {value}")
    if not risky:
        return "可作为直接参考输入，仍需遵守提示词里的反误读说明。"
    return "不能直接喂给所有视频模型；限制: " + ", ".join(risky)


def prompt_summary(prompt: str) -> str:
    lines = [line.strip() for line in prompt.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return compact(" ".join(lines), 260)


def blocking_summary(blocking: Any) -> str:
    if not isinstance(blocking, dict):
        return str(blocking or "")
    parts = [
        f"起点 {blocking.get('start_position', '')}",
        f"终点 {blocking.get('end_position', '')}",
        f"路径 {blocking.get('path', '')}",
        f"视线 {blocking.get('eyeline', '')}",
        f"方向 {blocking.get('screen_direction', '')}",
        f"轴线 {blocking.get('axis_note', '')}",
    ]
    return compact("; ".join(part for part in parts if part.strip()), 260)


def scene_summary(scene: Any) -> str:
    if not isinstance(scene, dict):
        return ""
    parts = [
        f"前景 {scene.get('foreground', '')}",
        f"中景 {scene.get('midground', '')}",
        f"背景 {scene.get('background', '')}",
        f"光线 {scene.get('lighting', '')}",
    ]
    return compact("; ".join(part for part in parts if part.strip()), 220)


def audio_summary(audio: Any) -> str:
    if not isinstance(audio, dict):
        return str(audio or "")
    cues: list[str] = []
    for key, label in [
        ("ambience", "环境"),
        ("sfx", "SFX"),
        ("foley", "Foley"),
        ("dialogue", "对白"),
        ("voiceover", "VO"),
    ]:
        value = audio.get(key)
        if isinstance(value, list) and value:
            cues.append(f"{label}: {', '.join(str(item) for item in value)}")
    if audio.get("music"):
        cues.append(f"音乐: {audio['music']}")
    if audio.get("silence"):
        cues.append(f"留白: {audio['silence']}")
    return compact("; ".join(cues), 240)


def model_summary(model_notes: Any) -> str:
    if not isinstance(model_notes, dict):
        return ""
    parts = []
    for model in ["seedance", "kling", "runway", "veo"]:
        if model_notes.get(model):
            parts.append(f"{model}: {model_notes[model]}")
    return compact("; ".join(parts), 260)


def print_shot_cards(shots: list[dict[str, Any]], label: str) -> None:
    print_subheader(label)
    print("[智能体创作内容]")
    for shot in shots:
        print(
            f"  {shot.get('shot_id')} {shot.get('timecode', '')} | "
            f"{shot.get('story_beat', '')} | {shot.get('shot_type', '')}"
        )
        print(
            f"    画面功能: {shot.get('narrative_purpose') or shot.get('purpose', '')}"
        )
        print(
            f"    摄影: {shot.get('shot_size')} / {shot.get('camera_angle')} / "
            f"{shot.get('lens')}；{shot.get('camera_support', '')}；"
            f"{shot.get('camera_motion')}；焦点: {shot.get('focus', '')}"
        )
        if shot.get("lens_reason"):
            print(f"    镜头理由: {shot.get('lens_reason')}")
        print(f"    调度: {blocking_summary(shot.get('blocking'))}")
        if shot.get("composition"):
            print(f"    构图: {shot.get('composition')}")
        scene_text = scene_summary(shot.get("scene"))
        if scene_text:
            print(f"    画面层次: {scene_text}")
        print(f"    动作: {shot.get('subject_action')}")
        print(f"    声音: {audio_summary(shot.get('audio'))}")
        model_text = model_summary(shot.get("model_notes"))
        if model_text:
            print(f"    生成备注: {model_text}")


def run_complete_idea_demo(example: Path) -> None:
    idea_text = read_text(require_file(example, "01-complete-idea.md"))
    chat_text = read_text(require_file(example, "02-chat-transcript.md"))
    shot_data = load_yaml(require_file(example, "03-shot-list.yaml"))
    ref_text = read_text(require_file(example, "04-reference-prompt-plan.md"))
    qa_text = read_text(require_file(example, "05-qa-retry-plan.md"))
    co_run_data = load_yaml(require_file(example, "15-co-creation-run.yaml"))

    co_run = co_run_data.get("co_creation_run", {})
    concept_gate = gate_by_type(co_run_data, "concept_options_gate")
    story_gate = gate_by_type(co_run_data, "story_approval_gate")
    shot_gate = gate_by_type(co_run_data, "shot_list_approval_gate")
    ref_gate = gate_by_type(co_run_data, "global_reference_pack_gate")
    clean_gate = gate_by_type(co_run_data, "clean_frame_gate")
    video_gate = gate_by_type(co_run_data, "video_prompt_gate")

    project = co_run.get("project_title") or "Complete idea demo"
    print_header(f"DIRcreative Demo: {project}")
    print(f"示例路径: {rel(example)}")
    print(f"运行类型: {co_run.get('run_type', 'unknown')}")
    print(f"输出模式: {co_run.get('visual_output_mode', 'unknown')}")
    print(f"真实用户共创已验证: {yn(bool(co_run.get('real_user_co_creation_verified')))}")
    print("说明: 这是完整想法切分演示。用户已有故事，不强行头脑风暴。")

    print_subheader("原始想法")
    print("[用户输入]")
    for line in indent_lines(section(idea_text, "User Input")):
        print(line)

    print_subheader("完整想法读取")
    print("[智能体创作内容]")
    print("  专业判断: 用户已经给出片名、时长、格式、故事目标、气质和禁止项。这里不进入创意发散。")
    print("  已锁定: Fog Route Cleaner / 15 秒 / 9:16 / 市政清道夫 / 雾中污染街道 / 救护车通道 / 无血腥无喜剧。")
    print("  执行影响: 仍然保留故事逻辑、脚本节奏、动态分镜、参考图组、出图执行建议和模型提示词 gate。")

    print_subheader("导演组会议")
    print("[智能体创作内容] 完整想法模式也要触发导演组；这里只校验执行，不改写用户故事。")
    print("  - producer: 保留用户片名、时长、故事目标和禁止项，把确认点放在节奏、分镜、参考图和生成模式。")
    print("  - creative_director: 锁定人性克制的市政现实主义，不走丧尸动作片。")
    print("  - director: 任务逻辑是堵塞、启动工具、推进清道、控制风险、救护车通过、安静收尾。")
    print("  - screenwriter: 不加对白和解释性字幕，靠动作、声音和剪辑讲清楚。")
    print("  - cinematographer: 先锁街道轴线、救护车位置、雾中光源和镜头视场。")
    print("  - production_designer: 人物/设备参考必须是一张单一身份来源。")
    print("  - editor: 三镜头会把信息压爆；六镜头由内容节奏决定，不是固定模板。")
    print("  - sound_designer: 分镜必须写远警笛、湿路、推车电机、喷雾、靴子踩水、救护车远去。")
    print("  - model_prompt_engineer: V2 sequential 顺序是人物身份参考 -> 场景空间+镜头视场 -> 专业故事版+镜头运动 -> clean frames。")
    print("  - continuity_qa: 视频前必须锁人物一致性、场景一致性、标题层级和参考图职责。")
    print("  导演组分歧:")
    print("  - 不给新故事方向，只给执行方案，因为用户已经给了完整设定。")
    print("  - 6 镜头通过，因为故事有建立、设备证明、推进、风险、放行、证明六个必要任务。")
    print("  - 采用 V2 sequential，先锁单一人物身份和单一场景/FOV，再做专业分镜运动页。")
    print("  给你的 3 个执行方案:")
    print("  1. 六镜头市政现实主义；2. 四镜头慢节奏；3. 八镜头快剪。")
    print("  [用户确认点] 接受六镜头市政现实主义方案，还是改成 4 镜头慢节奏或 8 镜头快剪？")
    print("  [模拟用户选择] 接受六镜头市政现实主义方案。")

    print_subheader("创意方向")
    print("[用户确认点] 完整想法模式下跳过广泛创意方向，但必须显式记录跳过原因:")
    print_options(concept_gate)

    print_subheader("故事与节奏确认")
    print("[用户确认点]")
    print_options(story_gate)
    print("  [模拟用户选择] 6 镜头节奏通过")

    shots = shot_data.get("shot_list", {}).get("shots", [])
    print_shot_cards(shots, f"{len(shots)}镜头分镜")
    print(f"  shot_count_rationale: {shot_data.get('shot_list', {}).get('shot_count_rationale', '')}")
    print("  [用户确认点] 分镜通过后才进入参考图方案。")
    print(f"  [模拟用户选择] {shot_gate.get('selected_option', '')}")

    print_subheader("参考图方案")
    print("[用户确认点]")
    print(f"  方案选择: {ref_gate.get('selected_option', '')}")
    ref_plan = section(ref_text, "Reference Image Plan")
    for line in indent_lines(ref_plan, "  "):
        print(line)
    print("  关键规则: 先锁人物身份，再锁场景/FOV，再锁专业分镜运动页，最后才生成 clean frames。")
    print("  不能直接喂给视频模型: 人物板、场景/FOV 图、专业分镜页都是 planning/reference，不能当 Kling/Runway 首帧。")

    print_subheader("出图执行建议")
    print("[prompt-only产物]")
    contract = ref_text.split("```yaml", 1)[1].split("```", 1)[0] if "```yaml" in ref_text else ""
    for line in indent_lines(contract.strip(), "  "):
        print(line)
    print("  prompt 绑定规则:")
    for required in [
        "Largest title on the page: 人物身份参考图 / CHARACTER IDENTITY REFERENCE",
        "Smaller metadata only: Project: Fog Route Cleaner",
        "Do not make FOG ROUTE CLEANER the largest title.",
    ]:
        print(f"  - {required}")

    print_subheader("出图执行建议")
    print("[prompt-only产物]")
    prompt_outputs = ref_text.split("Prompt-only outputs:", 1)[1].split("## Video Prompt Summaries", 1)[0] if "Prompt-only outputs:" in ref_text else ""
    for line in indent_lines(prompt_outputs.strip(), "  "):
        print(line)

    print_subheader("视频生成建议")
    print("[prompt-only产物] 每个视频模型有独立写法，不共用一个通用 prompt。")
    for heading, display in [
        ("Seedance", "Seedance"),
        ("Kling", "Kling（可灵）"),
        ("Runway", "Runway"),
        ("Veo", "Veo"),
    ]:
        body = subsection(ref_text, heading)
        print(f"  - {display}")
        for line in indent_lines(body, "    "):
            print(line)

    print_subheader("生成状态")
    print("[还没有生成的真实图片/视频]")
    print("当前没有生成真实图片或视频")
    print(f"  clean_frame_gate: {clean_gate.get('status')} -> media_generation blocked")
    print(f"  video_prompt_gate: {video_gate.get('status')} -> {video_gate.get('selected_option', '')}")

    print_subheader("QA 与重试规则")
    print("[智能体创作内容] 生成图/视频前后都有 QA gate，用户不是第一道质检。")
    print("  当前媒体状态:")
    for line in indent_lines(section(qa_text, "Current Media State"), "    "):
        print(line)
    print("  Pre-Generation QA / 生成前 QA:")
    for line in indent_lines(section(qa_text, "Pre-Generation QA"), "    "):
        print(line)
    print("  Post-Generation Self-QA / 生成后 self-QA:")
    for line in indent_lines(section(qa_text, "Post-Generation Self-QA"), "    "):
        print(line)
    print("  Retry Routing / 最小重试路由:")
    for line in indent_lines(section(qa_text, "Retry Routing"), "    "):
        print(line)
    print("  [用户确认点] 是否同意按顺序生成并逐步 QA: 人物身份 -> 场景/FOV -> 分镜运动页 -> clean frames -> 单模型视频测试？")
    print("  [模拟用户选择] 同意顺序生成；本 demo 仍保持 prompt-only，不生成真实图片或视频。")

    print_subheader("下一步真实用户应该确认什么")
    print("[用户确认点]")
    print("  1. 是否按 V2 顺序先生成人物身份参考图。")
    print("  2. 人物身份锁定后，是否生成场景空间+镜头视场参考图。")
    print("  3. 场景/FOV 锁定后，是否生成专业分镜头+镜头运动图。")
    print("  4. 三张 planning/reference 通过后，是否生成 S01/S06 clean frames。")

    print_subheader("边界")
    print("  - 智能体创作内容: 完整想法读取、故事节奏、专业分镜、参考图方案、提示词。")
    print("  - 模拟用户选择: 本 demo 用 simulated_fixture 标记，不等于真实用户确认。")
    print("  - prompt-only产物: 可复制给外部工具，但本地没有新媒体文件。")
    print("  - assisted_generation: 被 clean_frame_gate 阻止，直到真实用户授权。")


def run_demo(example: Path) -> None:
    if (example / "01-complete-idea.md").exists():
        run_complete_idea_demo(example)
        return

    idea_text = read_text(require_file(example, "01-idea-intake.md"))
    concept_text = read_text(require_file(example, "03-concept-options.md"))
    script_text = read_text(require_file(example, "06-script.md"))
    shot_data = load_yaml(require_file(example, "07-shot-list.yaml"))
    ref_data = load_yaml(require_file(example, "09-reference-pack-plan.yaml"))
    image_data = load_yaml(require_file(example, "10-image-prompt-manifest.yaml"))
    video_data = load_yaml(require_file(example, "11-video-prompt-manifest.yaml"))
    co_run_data = load_yaml(require_file(example, "15-co-creation-run.yaml"))
    qa_text = read_text(example / "12-qa-retry-plan.md") if (example / "12-qa-retry-plan.md").exists() else ""

    co_run = co_run_data.get("co_creation_run", {})
    concept_gate = gate_by_type(co_run_data, "concept_options_gate")
    visual_gate = gate_by_type(co_run_data, "visual_direction_gate")
    sequence_gate = gate_by_type(co_run_data, "sequence_plan_gate")
    ref_gate = gate_by_type(co_run_data, "global_reference_pack_gate")
    clean_gate = gate_by_type(co_run_data, "clean_frame_gate")
    video_gate = gate_by_type(co_run_data, "video_prompt_gate")

    project = co_run.get("project_title") or "DIRcreative demo"
    visual_mode = co_run.get("visual_output_mode", "unknown")
    run_type = co_run.get("run_type", "unknown")

    print_header(f"DIRcreative Demo: {project}")
    print(f"示例路径: {rel(example)}")
    print(f"运行类型: {run_type}")
    print(f"输出模式: {visual_mode}")
    print(f"真实用户共创已验证: {yn(bool(co_run.get('real_user_co_creation_verified')))}")
    print("说明: 这是终端演示报告，不是 raw YAML dump。")

    print_subheader("原始想法")
    print("[用户输入]")
    raw_idea = section(idea_text, "Raw User Idea")
    print(f"  {raw_idea}")

    print_subheader("创意方向")
    print("[智能体创作内容] 导演组给出 3 个方向:")
    print_options(concept_gate)
    concept_body = section(concept_text, "What The User Would See")
    if concept_body:
        print("  可见提案摘要:")
        for line in indent_lines(concept_body, "    "):
            print(line)

    print_subheader("视觉风格")
    print("[用户确认点] 视觉风格给出 3 个方向:")
    print_options(visual_gate)

    print_subheader("15秒脚本")
    print("[智能体创作内容]")
    script_body = section(script_text, "15s Script")
    for line in indent_lines(script_body):
        print(line)

    shots = shot_data.get("shot_list", {}).get("shots", [])
    print_shot_cards(shots, f"{len(shots)}镜头分镜")

    print_subheader("参考图方案")
    print("[用户确认点]")
    print(f"  方案选择: {ref_gate.get('selected_option', '')}")
    ref_images = ref_data.get("reference_pack", {}).get("images", [])
    assets = ref_data.get("reference_pack_manifest", {}).get("assets", [])
    print(f"  共 {len(ref_images)} 张/组参考图:")
    for item in ref_images:
        print(f"  - {item.get('image_id')} | {item.get('role')}")
        print(f"    用途: {item.get('purpose')}")
        if item.get("board_risk"):
            print(f"    风险: {item.get('board_risk')}")
    print("  哪些不能直接喂给视频模型:")
    for asset in assets:
        print(f"  - {asset.get('asset_id')} | {asset.get('role')}: {direct_input_note(asset)}")
        if asset.get("must_not_animate"):
            print(f"    must_not_animate: {', '.join(asset.get('must_not_animate', []))}")

    print_subheader("出图执行建议")
    print("[prompt-only产物] 这里只导出提示词，没有调用生图。")
    for image in image_data.get("images", []):
        labels = ", ".join(image.get("exact_text_labels", []))
        print(f"  - {image.get('image_id')} | {image.get('type')}")
        print(f"    用途: {image.get('purpose')}")
        print(f"    关键文字: {labels}")
        print(f"    提示词摘要: {prompt_summary(image.get('prompt', ''))}")

    print_subheader("视频生成建议")
    print("[prompt-only产物] 每个视频模型有独立写法，不共用一个通用 prompt。")
    model_names = {
        "seedance": "Seedance",
        "kling": "Kling（可灵）",
        "runway": "Runway",
        "veo": "Veo",
    }
    for key in ["seedance", "kling", "runway", "veo"]:
        entry = video_data.get("model_prompts", {}).get(key, {})
        print(f"  - {model_names[key]}")
        print(f"    适合: {entry.get('best_for', '')}")
        print(f"    摘要: {prompt_summary(entry.get('prompt', ''))}")
        print(f"    参考图警告: {entry.get('reference_warning', '')}")

    print_subheader("生成状态")
    image_cap = video_data.get("execution_capabilities", {}).get("image_generation", {})
    video_cap = video_data.get("execution_capabilities", {}).get("video_generation", {})
    if not image_cap.get("available") and not video_cap.get("available"):
        print("[还没有生成的真实图片/视频]")
        print("当前没有生成真实图片或视频")
    else:
        print(f"图片生成可用: {yn(bool(image_cap.get('available')))}")
        print(f"视频生成可用: {yn(bool(video_cap.get('available')))}")
    print(f"  clean_frame_gate: {clean_gate.get('status')} -> {clean_gate.get('selected_option', '')}")
    print(f"  video_prompt_gate: {video_gate.get('status')} -> {video_gate.get('selected_option', '')}")

    if qa_text:
        print_subheader("出图执行建议")
        print("[prompt-only产物] assisted_generation 前必须先过合同，不直接生图。")
        contract = qa_text.split("```yaml", 1)[1].split("```", 1)[0] if "```yaml" in qa_text else ""
        for line in indent_lines(contract.strip(), "  "):
            print(line)

        print_subheader("QA 与重试规则")
        print("[智能体创作内容] 用户不是第一道质检；生成后必须先 self-QA。")
        print("  Pre-Generation QA / 生成前 QA:")
        for line in indent_lines(section(qa_text, "Pre-Generation QA"), "    "):
            print(line)
        print("  Post-Generation Self-QA / 生成后 self-QA:")
        for line in indent_lines(section(qa_text, "Post-Generation Self-QA"), "    "):
            print(line)
        print("  Retry Routing / 最小重试路由:")
        for line in indent_lines(section(qa_text, "Retry Routing"), "    "):
            print(line)
        print("  [用户确认点] 是否同意顺序生成并逐步 QA: product identity -> office source -> style board -> storyboard -> clean frames -> model test？")
        print("  [模拟用户选择] 同意顺序；本 demo 仍保持 prompt-only，不生成真实图片或视频。")

    print_subheader("下一步真实用户应该确认什么")
    print("[用户确认点]")
    print("  1. 是否生成或导入 clean frame: N01 桌面起始帧、N05 产品结束帧。")
    print("  2. 是否锁定 product board / office board / lighting-material-style board / storyboard board 的实际生成结果。")
    print("  3. 第一个实测视频模型选 Seedance、Kling（可灵）、Runway 还是 Veo。")
    print("  4. 是否继续 prompt-only，或授权进入 assisted_generation。")

    print_subheader("边界")
    print("  - 智能体创作内容: 概念、脚本、分镜、参考图方案、图片提示词、视频提示词。")
    print("  - 模拟用户选择: 本 demo 用 simulated_fixture 标记，不等于真实用户确认。")
    print("  - prompt-only产物: 可复制给外部生成工具，但本地没有媒体文件。")
    print("  - 还没有生成的真实图片/视频: 需要用户授权后才能进入。")


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a human-readable DIRcreative demo flow.")
    parser.add_argument("--example", default=DEFAULT_EXAMPLE, help="Example directory to render.")
    args = parser.parse_args()
    try:
        run_demo(resolve_example(args.example))
    except DemoError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
