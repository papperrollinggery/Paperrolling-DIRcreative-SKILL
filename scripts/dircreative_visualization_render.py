#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from dircreative_visualization_spec import customer_stage_label, load_document, validate_document

ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "skills/dircreative/assets/visualizations"
CSS_PATH = ASSET_ROOT / "decision-surface.css"
JS_PATH = ASSET_ROOT / "decision-surface.js"
FIXTURE_ROOT = ROOT / "tests/fixtures/chat-visualization"
TITLE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_FRAGMENT_BYTES = 2_000_000
STAGES = ["需求", "方向", "故事", "脚本", "分镜", "视觉", "生成", "QA"]
STAGE_INDEX = {
    "idea_intake_gate": 0,
    "concept_options_gate": 1,
    "story_approval_gate": 2,
    "script_approval_gate": 3,
    "shot_list_approval_gate": 4,
    "sequence_plan_gate": 4,
    "visual_direction_gate": 5,
    "visual_bible_approval_gate": 5,
    "global_reference_pack_gate": 5,
    "sequence_reference_pack_gate": 5,
    "clean_frame_gate": 6,
    "video_prompt_gate": 6,
    "generation_qa_gate": 7,
    "retry_gate": 7,
    "acceptance_gate": 7,
    "checkpoint_gate": 7,
}
STORY_FIELD_LABELS = {
    "beginning": "建立",
    "turn": "转折",
    "proof": "证明",
    "ending": "收束",
}


class RenderError(Exception):
    pass


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        values = []
        for item in value:
            if isinstance(item, dict):
                values.append(str(item.get("label") or item.get("name") or item.get("id") or ""))
            else:
                values.append(str(item))
        return "、".join(item for item in values if item)
    if isinstance(value, dict):
        return "；".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


def safe_inline_json(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def image_data_uri(artifact: dict[str, Any], project_root: Path) -> str:
    path = (project_root / artifact["path"]).resolve()
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise RenderError("image path escaped the verified project root") from exc
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
        raise RenderError("image changed after validation; rebuild the review spec")
    payload = base64.b64encode(data).decode("ascii")
    return f'data:{artifact["mime_type"]};base64,{payload}'


def render_previews(document: dict[str, Any], selected_id: str, project_root: Path) -> str:
    previews = document["presentation"].get("previews", [])
    if not previews:
        return ""
    artifacts = {item["artifact_id"]: item for item in document["source_truth"]["artifacts"]}
    figures = []
    for preview in previews:
        artifact = artifacts[preview["artifact_id"]]
        selected = preview["option_id"] == selected_id
        classification = artifact["review_classification"]
        badge = "真实候选" if classification == "real_candidate" else "演示参考图"
        annotations = "".join(
            f'<li><strong>{esc(item["region"])}</strong><span>{esc(item["note"])}</span></li>'
            for item in preview.get("annotations", [])
        )
        figures.append(
            f'<figure class="dc-image-preview{" is-selected" if selected else ""}" '
            f'data-dc-image-preview="{esc(preview["option_id"])}"{"" if selected else " hidden"}>'
            '<div class="dc-image-frame">'
            f'<img src="{image_data_uri(artifact, project_root)}" alt="{esc(preview["alt"])}">'
            f'<span class="viz-badge dc-image-classification is-{esc(classification)}">{esc(badge)}</span>'
            '</div>'
            f'<figcaption><strong>{esc(preview["label"])}</strong><span>{esc(preview["caption"])}</span></figcaption>'
            f'<ul class="dc-image-annotations">{annotations}</ul>'
            '</figure>'
        )
    return (
        '<div class="dc-image-review" role="region" aria-label="候选图片审阅" '
        f'aria-live="polite" aria-atomic="true">{"".join(figures)}</div>'
    )


def field_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field["id"]: field for field in document["presentation"]["fields"]}


def stage_rail(document: dict[str, Any]) -> str:
    current = STAGE_INDEX.get(document["stage_gate"]["type"], 0)
    items = []
    for index, label in enumerate(STAGES):
        classes = ["dc-stage", "text-small"]
        attributes = ""
        if index < current:
            classes.append("is-done")
        elif index == current:
            classes.append("is-current")
            attributes = ' aria-current="step"'
        items.append(f'<li class="{" ".join(classes)}"{attributes}>{esc(label)}</li>')
    summary = f"项目阶段，当前处于{document['view']['customer_stage_label']}"
    return f'<ol class="dc-stage-rail" aria-label="{esc(summary)}">{"".join(items)}</ol>'


def render_facts(document: dict[str, Any]) -> str:
    facts = []
    for field in document["presentation"]["fields"]:
        if field["id"] == "current_stage":
            continue
        facts.append(
            '<div class="dc-fact">'
            f'<dt class="text-small">{esc(field["label"])}</dt>'
            f'<dd>{esc(display_value(field["value"]))}</dd>'
            "</div>"
        )
    if not facts:
        return ""
    return f'<dl class="card dc-facts">{"".join(facts)}</dl>'


def render_comparison(document: dict[str, Any]) -> str:
    options = document["presentation"].get("options", [])
    if not options:
        return render_facts(document)
    recommendation = document["presentation"].get("recommendation") or {}
    selected_id = recommendation.get("option_id") or options[0]["id"]
    selected = next((option for option in options if option["id"] == selected_id), options[0])
    choices = []
    for option in options:
        pressed = "true" if option["id"] == selected["id"] else "false"
        choices.append(
            f'<button type="button" class="btn viz-tile" data-dc-choice="{esc(option["id"])}" '
            f'aria-pressed="{pressed}">{esc(option["label"])}</button>'
        )
    reason = recommendation.get("reason")
    recommended = next((option for option in options if option["id"] == recommendation.get("option_id")), None)
    recommendation_html = ""
    if recommended and reason:
        recommendation_html = (
            f'<aside class="dc-recommendation" data-dc-recommendation '
            f'data-dc-recommended-option="{esc(recommended["id"])}">'
            '<span class="text-small text-muted">初始推荐</span>'
            f'<strong data-dc-recommendation-name>{esc(recommended["label"])}</strong>'
            f'<span data-dc-recommendation-reason>{esc(reason)}</span></aside>'
        )
    option_details = []
    detail_registry = {}
    for option in options:
        for detail in option.get("details", []):
            detail_registry.setdefault(detail["id"], detail["label"])
    selected_details = {detail["id"]: detail for detail in selected.get("details", [])}
    for detail_id, detail_label in detail_registry.items():
        detail = selected_details.get(detail_id)
        hidden = "" if detail else " hidden"
        value = detail["value"] if detail else ""
        option_details.append(
            f'<div class="dc-detail-row" data-dc-detail-row="{esc(detail_id)}"{hidden}>'
            f'<span>{esc(detail_label)}</span>'
            f'<span data-dc-detail-value="{esc(detail_id)}">{esc(value)}</span></div>'
        )
    extra_rows = []
    fields = field_map(document)
    for field_id in ("blocker", "passed_locks", "failed_locks", "smallest_retry", "preserved_artifacts"):
        if field_id in fields:
            field = fields[field_id]
            extra_rows.append(
                f'<div class="dc-detail-row"><span>{esc(field["label"])}</span>'
                f'<span>{esc(display_value(field["value"]))}</span></div>'
            )
    return (
        f'<div class="viz-grid dc-choice-grid" role="group" aria-label="{esc(document["view"]["decision_prompt"])}">'
        f'{"".join(choices)}</div>'
        '<div class="card dc-choice-detail" aria-live="polite">'
        '<span class="text-small text-muted">当前查看</span>'
        f'<strong data-dc-detail-name>{esc(selected["label"])}</strong>'
        f'<div class="dc-detail-row"><span>这个方向</span><span data-dc-detail-summary>{esc(selected["summary"])}</span></div>'
        f'<div class="dc-detail-row"><span>导演判断</span><span data-dc-detail-tradeoff>{esc(selected["tradeoff"])}</span></div>'
        f'{"".join(option_details)}{"".join(extra_rows)}{recommendation_html}</div>'
    )


def render_story_ribbon(document: dict[str, Any]) -> str:
    fields = field_map(document)
    steps = []
    for field_id, label in STORY_FIELD_LABELS.items():
        if field_id not in fields:
            continue
        steps.append(
            '<li class="dc-ribbon-step">'
            f'<span class="text-small text-muted">{esc(label)}</span>'
            f'<div class="dc-ribbon-value">{esc(display_value(fields[field_id]["value"]))}</div>'
            "</li>"
        )
    if len(steps) < 3:
        return render_facts(document)
    summary = "故事从建立、转折、证明到收束的节拍顺序"
    return f'<ol class="dc-ribbon" aria-label="{esc(summary)}">{"".join(steps)}</ol>'


def render_story_curve(document: dict[str, Any]) -> str:
    curve = field_map(document).get("story_curve", {}).get("value")
    if not isinstance(curve, dict) or not isinstance(curve.get("series"), list):
        return render_story_ribbon(document)
    series = curve["series"]
    source_label = "创作推演" if curve.get("source_kind") == "creative_projection" else "已确认数据"
    summary = curve.get("summary") or "、".join(str(item.get("insight", "")) for item in series if item.get("insight"))
    controls = []
    for index, item in enumerate(series):
        pressed = "true" if index == 0 else "false"
        controls.append(
            f'<button type="button" class="btn dc-curve-key dc-series-{index + 1}" '
            f'data-dc-curve-series="{esc(item["id"])}" aria-pressed="{pressed}">'
            f'<span class="dc-curve-swatch" aria-hidden="true"></span>{esc(item["label"])}</button>'
        )
    initial_insight = series[0].get("insight") or summary
    annotation_labels = []
    for index, annotation in enumerate(curve.get("annotations", [])[:5]):
        annotation_labels.append(
            f'<span><strong>{index + 1}</strong> {esc(annotation["label"])} · {float(annotation["time"]):g}s</span>'
        )
    return (
        '<div class="dc-curve-shell">'
        f'<div class="viz-row dc-curve-controls" aria-label="曲线焦点">{"".join(controls)}'
        f'<span class="text-small text-muted">{esc(source_label)}</span></div>'
        f'<svg class="dc-story-curve" data-dc-story-curve role="img" aria-label="{esc(summary)}">'
        f'<title>{esc(summary)}</title><desc>横轴为秒，纵轴为相对强度零到一百。</desc></svg>'
        f'<div class="dc-curve-annotations" aria-label="故事节拍">{"".join(annotation_labels)}</div>'
        f'<div class="dc-curve-insight" data-dc-curve-insight role="status">{esc(initial_insight)}</div>'
        '</div>'
    )


def timeline_items(document: dict[str, Any]) -> list[dict[str, Any]]:
    fields = field_map(document)
    for field_id in ("time_bands", "timeline", "shots"):
        value = fields.get(field_id, {}).get("value")
        if isinstance(value, list) and value:
            return [item for item in value if isinstance(item, dict)]
    return []


def render_timeline(document: dict[str, Any]) -> str:
    items = timeline_items(document)
    if not items:
        return render_facts(document)
    normalized: list[dict[str, Any]] = []
    cursor = 0.0
    for index, item in enumerate(items):
        start = float(item.get("start", cursor))
        if "end" in item:
            end = float(item["end"])
        else:
            end = start + float(item.get("duration", 1))
        if end <= start:
            raise RenderError(f"timeline item {index} must end after start")
        cursor = end
        normalized.append({**item, "start": start, "end": end})
    total = max(item["end"] for item in normalized)
    rows = []
    for index, item in enumerate(normalized):
        left = item["start"] / total * 100
        width = (item["end"] - item["start"]) / total * 100
        label = item.get("label") or item.get("name") or item.get("id") or f"段落 {index + 1}"
        time_label = f'{item["start"]:g}–{item["end"]:g}s'
        accessible = f"{time_label}，{label}"
        rows.append(
            '<div class="dc-timeline-row">'
            f'<span class="text-small text-muted">{esc(time_label)}</span>'
            f'<div class="dc-track" role="img" aria-label="{esc(accessible)}">'
            f'<div class="dc-band" style="--dc-left:{left:.3f}%;--dc-width:{width:.3f}%">{esc(label)}</div>'
            "</div></div>"
        )
    summary = f"共 {len(normalized)} 个时间段，总时长 {total:g} 秒"
    return f'<div class="dc-timeline" aria-label="{esc(summary)}">{"".join(rows)}</div>'


def render_shot_rhythm(document: dict[str, Any]) -> str:
    rhythm = field_map(document).get("shot_rhythm", {}).get("value")
    if not isinstance(rhythm, dict) or not isinstance(rhythm.get("shots"), list):
        return render_timeline(document)
    shots = rhythm["shots"]
    summary = rhythm.get("summary") or f"{len(shots)} 个镜头，共 {float(rhythm['duration']):g} 秒"
    controls = []
    mobile_rows = []
    for index, shot in enumerate(shots):
        pressed = "true" if index == 0 else "false"
        controls.append(
            f'<button type="button" class="btn" data-dc-shot="{esc(shot["id"])}" aria-pressed="{pressed}">'
            f'{esc(shot["id"].upper())}</button>'
        )
        mobile_rows.append(
            f'<div class="dc-shot-mobile-row{" is-selected" if index == 0 else ""}" data-dc-shot-mobile="{esc(shot["id"])}">'
            f'<div><strong>{esc(shot["id"].upper())}</strong> '
            f'<span class="text-small text-muted">{float(shot["start"]):g}–{float(shot["end"]):g}s</span></div>'
            f'<div>{esc(shot["label"])}</div>'
            f'<div class="text-small">{esc(shot["size"])} · {esc(shot["movement"])} · {esc(shot["action"])}</div>'
            f'<div class="text-small">声音：{esc(shot["audio"])} · 风险：{esc(shot["risk"])}</div>'
            '</div>'
        )
    first = shots[0]
    initial_detail = (
        f'{first["id"].upper()} {float(first["start"]):g}–{float(first["end"]):g}s · '
        f'{first["size"]}/{first["movement"]} · {first["label"]} · 风险：{first["risk"]}'
    )
    return (
        '<div class="dc-shot-rhythm-shell">'
        f'<div class="viz-row dc-shot-controls" aria-label="选择镜头查看">{"".join(controls)}</div>'
        f'<svg class="dc-shot-rhythm" data-dc-shot-rhythm role="img" aria-label="{esc(summary)}">'
        f'<title>{esc(summary)}</title><desc>所有轨道共享同一时间轴，依次显示镜头、景别、运动、动作、声音和风险。</desc></svg>'
        f'<div class="dc-shot-mobile">{"".join(mobile_rows)}</div>'
        f'<div class="dc-shot-detail" data-dc-shot-detail role="status">{esc(initial_detail)}</div>'
        '</div>'
    )


def render_lock_matrix(document: dict[str, Any]) -> str:
    locks = field_map(document).get("locks", {}).get("value")
    if not isinstance(locks, list) or not locks:
        return render_facts(document)
    rows = []
    for lock in locks:
        if not isinstance(lock, dict):
            continue
        dimension = lock.get("dimension") or lock.get("label") or lock.get("id") or "未命名维度"
        value = lock.get("value") or "未记录"
        status = lock.get("status") or "pending"
        risk = lock.get("risk") or "无额外风险"
        rows.append(
            '<div class="dc-matrix-row" role="row">'
            f'<span class="dc-row-label" role="rowheader">{esc(dimension)}</span>'
            f'<span role="cell">{esc(value)}</span>'
            f'<span role="cell"><span class="viz-badge">{esc(status)}</span></span>'
            f'<span role="cell">{esc(risk)}</span>'
            '</div>'
        )
    return f'<div class="dc-matrix" role="table" aria-label="视觉连续性锁与漂移风险">{"".join(rows)}</div>'


def render_asset_graph(document: dict[str, Any]) -> str:
    assets = field_map(document).get("assets", {}).get("value")
    if not isinstance(assets, list) or not assets:
        return render_facts(document)
    rows = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        label = asset.get("label") or asset.get("asset_id") or "未命名资产"
        role = asset.get("role") or "未声明职责"
        status = asset.get("status") or "pending"
        bindings = asset.get("shot_bindings") or asset.get("bindings") or []
        binding_text = "、".join(str(item) for item in bindings) if isinstance(bindings, list) else str(bindings)
        if asset.get("direct_video_input") is True:
            usage = "视频模型直接输入"
        elif asset.get("planning_only") is True:
            usage = "仅用于规划"
        else:
            usage = "参考用途"
        rows.append(
            '<div class="dc-asset-row" role="row">'
            f'<span class="dc-row-label" role="rowheader">{esc(label)}</span>'
            f'<span role="cell">{esc(role)}</span>'
            f'<span role="cell"><span class="viz-badge">{esc(status)}</span> {esc(usage)}</span>'
            f'<span role="cell">{esc(binding_text or "全局")}</span>'
            '</div>'
        )
    return f'<div class="dc-asset-graph" role="table" aria-label="参考资产职责、状态、用途和镜头绑定">{"".join(rows)}</div>'


def render_asset_dependency_graph(document: dict[str, Any]) -> str:
    graph = field_map(document).get("asset_graph", {}).get("value")
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        return render_asset_graph(document)
    nodes = graph["nodes"]
    assets = [node for node in nodes if node.get("type") == "asset"]
    shots = [node for node in nodes if node.get("type") == "shot"]
    if not assets or not shots:
        return render_asset_graph(document)
    node_labels = {node["id"]: node["label"] for node in nodes}
    first = assets[0]
    connected = []
    for edge in graph.get("edges", []):
        if edge.get("source") == first["id"]:
            connected.append(node_labels.get(edge.get("target"), edge.get("target", "")))
        elif edge.get("target") == first["id"]:
            connected.append(node_labels.get(edge.get("source"), edge.get("source", "")))
    initial_detail = f'{first["label"]}：{first["detail"]}；关联 {"、".join(connected) if connected else "无"}。'

    def render_nodes(items: list[dict[str, Any]], selected_id: str) -> str:
        buttons = []
        for node in items:
            pressed = "true" if node["id"] == selected_id else "false"
            buttons.append(
                f'<button type="button" class="btn btn-block dc-graph-node" data-dc-graph-node="{esc(node["id"])}" '
                f'data-dc-graph-type="{esc(node["type"])}" aria-pressed="{pressed}">{esc(node["label"])}</button>'
            )
        return "".join(buttons)

    summary = graph.get("summary") or "参考素材与镜头之间的直接使用和策划参考关系"
    return (
        '<div class="dc-asset-graph-shell">'
        '<div class="viz-row dc-graph-legend" aria-label="关系图例">'
        '<span><span class="dc-edge-key is-direct" aria-hidden="true"></span>直接使用</span>'
        '<span><span class="dc-edge-key is-planning" aria-hidden="true"></span>仅策划参考</span></div>'
        '<div class="dc-graph-stage" data-dc-graph-stage>'
        f'<svg class="dc-graph-edges" data-dc-graph-edges role="img" aria-label="{esc(summary)}">'
        f'<title>{esc(summary)}</title></svg>'
        '<div class="dc-graph-column" aria-label="参考素材">'
        '<span class="text-small text-muted">参考素材</span>'
        f'{render_nodes(assets, first["id"])}</div>'
        '<div class="dc-graph-column" aria-label="受影响镜头">'
        '<span class="text-small text-muted">受影响镜头</span>'
        f'{render_nodes(shots, first["id"])}</div></div>'
        f'<div class="dc-graph-detail" data-dc-graph-detail role="status">{esc(initial_detail)}</div>'
        '</div>'
    )


def render_qa_delta(document: dict[str, Any], project_root: Path) -> str:
    qa = field_map(document).get("qa_delta", {}).get("value")
    if not isinstance(qa, dict) or not isinstance(qa.get("candidates"), list):
        return render_comparison(document)
    options = document["presentation"].get("options", [])
    option_map = {option["id"]: option for option in options}
    candidates = qa["candidates"]
    recommendation = document["presentation"].get("recommendation") or {}
    selected_id = recommendation.get("option_id") or candidates[0]["id"]
    selected = next((candidate for candidate in candidates if candidate["id"] == selected_id), candidates[0])
    selected_option = option_map[selected["id"]]
    controls = []
    for candidate in candidates:
        pressed = "true" if candidate["id"] == selected["id"] else "false"
        controls.append(
            f'<button type="button" class="btn" data-dc-choice="{esc(candidate["id"])}" '
            f'data-dc-qa-candidate="{esc(candidate["id"])}" aria-pressed="{pressed}">{esc(candidate["label"])}</button>'
        )
    header_cells = ['<span class="text-small text-muted" role="columnheader">检查维度</span>', '<span class="text-small text-muted" role="columnheader">目标</span>']
    for candidate in candidates:
        selected_class = " is-selected" if candidate["id"] == selected["id"] else ""
        header_cells.append(
            f'<strong class="dc-qa-candidate-column{selected_class}" data-dc-qa-column="{esc(candidate["id"])}" '
            f'role="columnheader">{esc(candidate["label"])}</strong>'
        )
    rows = [f'<div class="dc-qa-row dc-qa-header" role="row">{"".join(header_cells)}</div>']
    status_labels = {"pass": "通过", "warn": "需注意", "fail": "失败"}
    for dimension in qa.get("dimensions", []):
        cells = [
            f'<strong role="rowheader">{esc(dimension["label"])}</strong>',
            f'<span role="cell">{esc(dimension["target"])}</span>',
        ]
        for candidate in candidates:
            result = dimension["results"][candidate["id"]]
            selected_class = " is-selected" if candidate["id"] == selected["id"] else ""
            cells.append(
                f'<span class="dc-qa-result{selected_class}" data-dc-qa-column="{esc(candidate["id"])}" role="cell">'
                f'<span class="viz-badge dc-qa-status is-{esc(result["status"])}">{status_labels[result["status"]]}</span> '
                f'{esc(result["value"])}</span>'
            )
        rows.append(f'<div class="dc-qa-row" role="row">{"".join(cells)}</div>')
    recommended_option = option_map.get(recommendation.get("option_id"))
    recommendation_html = ""
    if recommended_option and recommendation.get("reason"):
        recommendation_html = (
            f'<aside class="dc-recommendation" data-dc-recommendation '
            f'data-dc-recommended-option="{esc(recommended_option["id"])}">'
            '<span class="text-small text-muted">初始推荐</span>'
            f'<strong data-dc-recommendation-name>{esc(recommended_option["label"])}</strong>'
            f'<span data-dc-recommendation-reason>{esc(recommendation["reason"])}</span></aside>'
        )
    return (
        '<div class="dc-qa-shell">'
        f'<div class="viz-row dc-qa-controls" aria-label="候选对比">{"".join(controls)}</div>'
        f'<div class="text-small text-muted dc-qa-media-status">{esc(qa.get("media_status", ""))}</div>'
        f'{render_previews(document, selected["id"], project_root)}'
        f'<div class="dc-qa-table" role="table" aria-label="候选差异检查">{"".join(rows)}</div>'
        '<div class="card dc-qa-detail" aria-live="polite">'
        '<span class="text-small text-muted">当前查看</span>'
        f'<strong data-dc-detail-name>{esc(selected_option["label"])}</strong>'
        f'<div class="dc-detail-row"><span>整体结果</span><span data-dc-detail-summary>{esc(selected_option["summary"])}</span></div>'
        f'<div class="dc-detail-row"><span>处理代价</span><span data-dc-detail-tradeoff>{esc(selected_option["tradeoff"])}</span></div>'
        f'<div class="dc-detail-row"><span>专业判断</span><span data-dc-qa-judgment>{esc(selected["judgment"])}</span></div>'
        f'<div class="dc-detail-row"><span>当前阻塞</span><span data-dc-qa-blocker>{esc(selected["blocker"])}</span></div>'
        f'<div class="dc-detail-row"><span>最小处理</span><span data-dc-qa-retry>{esc(selected["retry"])}</span></div>'
        f'<div class="dc-detail-row"><span>继续沿用</span><span data-dc-qa-preserve>{esc(selected["preserve"])}</span></div>'
        f'{recommendation_html}</div></div>'
    )


def render_visual_board(document: dict[str, Any]) -> str:
    board = field_map(document).get("visual_board", {}).get("value")
    if not isinstance(board, dict) or not isinstance(board.get("directions"), list):
        return render_comparison(document)
    options = document["presentation"].get("options", [])
    option_map = {option["id"]: option for option in options}
    recommendation = document["presentation"].get("recommendation") or {}
    selected_id = recommendation.get("option_id") or board["directions"][0]["id"]
    selected = next((direction for direction in board["directions"] if direction["id"] == selected_id), board["directions"][0])
    selected_option = option_map[selected["id"]]
    controls = []
    for direction in board["directions"]:
        pressed = "true" if direction["id"] == selected["id"] else "false"
        controls.append(
            f'<button type="button" class="btn viz-tile" data-dc-choice="{esc(direction["id"])}" '
            f'data-dc-board-direction="{esc(direction["id"])}" aria-pressed="{pressed}">{esc(option_map[direction["id"]]["label"])}</button>'
        )

    def palette_html(direction: dict[str, Any]) -> str:
        return "".join(
            '<span class="dc-swatch-item">'
            f'<span class="dc-swatch" style="--dc-swatch:{esc(color["color"])}" aria-hidden="true"></span>'
            f'<span class="text-small">{esc(color["label"])}</span></span>'
            for color in direction["palette"]
        )

    def token_html(values: list[str]) -> str:
        return "".join(f'<span class="viz-badge">{esc(value)}</span>' for value in values)

    recommended_option = option_map.get(recommendation.get("option_id"))
    recommendation_html = ""
    if recommended_option and recommendation.get("reason"):
        recommendation_html = (
            f'<aside class="dc-recommendation" data-dc-recommendation data-dc-recommended-option="{esc(recommended_option["id"])}">'
            '<span class="text-small text-muted">初始推荐</span>'
            f'<strong data-dc-recommendation-name>{esc(recommended_option["label"])}</strong>'
            f'<span data-dc-recommendation-reason>{esc(recommendation["reason"])}</span></aside>'
        )
    return (
        '<div class="dc-visual-board-shell">'
        f'<div class="viz-grid dc-board-controls" aria-label="视觉方向">{"".join(controls)}</div>'
        f'<div class="text-small text-muted dc-board-media-status">{esc(board.get("media_status", ""))}</div>'
        '<div class="dc-board-layout">'
        '<section class="dc-board-section dc-board-palette-section"><span class="text-small text-muted">色板</span>'
        f'<div class="dc-board-palette" data-dc-board-palette>{palette_html(selected)}</div></section>'
        '<section class="dc-board-section"><span class="text-small text-muted">光线</span>'
        f'<strong data-dc-board-lighting>{esc(selected["lighting"])}</strong></section>'
        '<section class="dc-board-section"><span class="text-small text-muted">材质</span>'
        f'<div class="dc-board-tokens" data-dc-board-materials>{token_html(selected["materials"])}</div></section>'
        '<section class="dc-board-section"><span class="text-small text-muted">镜头语言</span>'
        f'<div class="dc-board-tokens" data-dc-board-optics>{token_html(selected["optics"])}</div></section>'
        '<section class="dc-board-section"><span class="text-small text-muted">允许</span>'
        f'<div class="dc-board-tokens" data-dc-board-allow>{token_html(selected["allow"])}</div></section>'
        '<section class="dc-board-section"><span class="text-small text-muted">避开</span>'
        f'<div class="dc-board-tokens" data-dc-board-avoid>{token_html(selected["avoid"])}</div></section>'
        '</div>'
        '<div class="card dc-board-detail" aria-live="polite">'
        '<span class="text-small text-muted">当前查看</span>'
        f'<strong data-dc-detail-name>{esc(selected_option["label"])}</strong>'
        f'<div class="dc-detail-row"><span>核心感觉</span><span data-dc-detail-summary>{esc(selected_option["summary"])}</span></div>'
        f'<div class="dc-detail-row"><span>制作权衡</span><span data-dc-detail-tradeoff>{esc(selected_option["tradeoff"])}</span></div>'
        f'<div class="dc-detail-row"><span>导演判断</span><span data-dc-board-judgment>{esc(selected["judgment"])}</span></div>'
        f'<div class="dc-detail-row"><span>后续影响</span><span data-dc-board-impact>{esc(selected["impact"])}</span></div>'
        f'{recommendation_html}</div></div>'
    )


def render_primary_visual(document: dict[str, Any], project_root: Path) -> str:
    gate_type = document["stage_gate"]["type"]
    if gate_type in {"generation_qa_gate", "retry_gate"} and "qa_delta" in field_map(document):
        return render_qa_delta(document, project_root)
    if gate_type == "visual_direction_gate" and "visual_board" in field_map(document):
        return render_visual_board(document)
    if document["presentation"].get("options"):
        return render_comparison(document)
    if gate_type == "visual_bible_approval_gate":
        return render_lock_matrix(document)
    if gate_type in {"global_reference_pack_gate", "sequence_reference_pack_gate", "clean_frame_gate"}:
        return render_asset_dependency_graph(document)
    if gate_type == "story_approval_gate":
        return render_story_curve(document)
    if gate_type in {"shot_list_approval_gate", "sequence_plan_gate"} and "shot_rhythm" in field_map(document):
        return render_shot_rhythm(document)
    if document["view"]["intent"] == "timeline":
        return render_timeline(document)
    return render_facts(document)


def render_effects(document: dict[str, Any]) -> str:
    effects = document["presentation"].get("downstream_effects", [])
    if not effects:
        return ""
    badges = []
    for index, effect in enumerate(effects):
        if index:
            badges.append('<span class="text-muted" aria-hidden="true">→</span>')
        badges.append(f'<span class="viz-badge">{esc(customer_stage_label(effect["stage"]))}：{esc(effect["effect"])}</span>')
    return (
        '<div class="dc-effect-row"><div class="dc-effects">'
        '<span class="text-small text-muted">接下来会影响</span>'
        f'{"".join(badges)}</div></div>'
    )


def render_actions(document: dict[str, Any]) -> str:
    actions = document["interactions"]["actions"]
    buttons = []
    for index in reversed(range(len(actions))):
        action = actions[index]
        classes = "btn btn-primary" if index == 0 else "btn"
        buttons.append(
            f'<button type="button" class="{classes}" data-dc-action="{esc(action["id"])}">'
            f'{esc(action["label"])}</button>'
        )
    return f'<div class="dc-action-row">{"".join(buttons)}</div>'


def render_fragment(document: dict[str, Any], project_root: Path = ROOT) -> str:
    project_root = project_root.expanduser().resolve()
    errors = validate_document(document, project_root=project_root)
    if errors:
        raise RenderError("invalid spec: " + "; ".join(errors))
    if document["execution_context"] != "standalone_chat" or not document["controller"]["user_facing"]:
        raise RenderError("provider-hidden orchestrated_worker specs must be surfaced by ADCO, not DIRcreative")
    digest = hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]
    root_id = f"dircreative-view-{digest}"
    data_id = f"dircreative-data-{digest}"
    css = CSS_PATH.read_text(encoding="utf-8").strip()
    script = JS_PATH.read_text(encoding="utf-8").replace("__ROOT_ID__", root_id).replace("__DATA_ID__", data_id).strip()
    header = (
        '<div class="dc-header"><div>'
        '<span class="viz-badge">当前决策</span> '
        f'<span>{esc(document["view"]["decision_prompt"])}</span>'
        '</div><span class="text-small text-muted">预览选择，发送后再确认</span></div>'
    )
    status = "选择会先回到对话，确认当前进度后再继续。"
    fragment = (
        f'<div id="{root_id}" data-dircreative-visual="1">\n'
        f'<style>\n{css}\n</style>\n'
        f'{stage_rail(document)}\n{header}\n{render_primary_visual(document, project_root)}\n'
        f'{render_effects(document)}\n{render_actions(document)}\n'
        f'<div class="dc-status text-small" data-dc-status role="status">{esc(status)}</div>\n'
        f'<script type="application/json" id="{data_id}">{safe_inline_json(document)}</script>\n'
        f'<script>\n{script}\n</script>\n'
        '</div>\n'
    )
    if len(fragment.encode("utf-8")) > MAX_FRAGMENT_BYTES:
        raise RenderError("rendered fragment exceeds 2 MB; create smaller review thumbnails")
    return fragment


def validate_output_path(path: Path, test_output: bool) -> None:
    if path.suffix != ".html" or not TITLE_RE.fullmatch(path.stem):
        raise RenderError("output must use a lowercase ASCII hyphenated .html filename")
    if not test_output:
        parts = set(path.expanduser().resolve().parts)
        if ".codex" not in parts or "visualizations" not in parts:
            raise RenderError("production output must be inside the thread-scoped .codex/visualizations directory")


def write_fragment(
    document: dict[str, Any],
    output: Path,
    test_output: bool,
    force: bool,
    project_root: Path = ROOT,
) -> None:
    validate_output_path(output, test_output)
    if output.exists() and not force:
        raise RenderError(f"refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_fragment(document, project_root), encoding="utf-8")


def self_test() -> list[str]:
    failures: list[str] = []
    fixture_names = [
        "valid-idea-brief-inline.json",
        "valid-director-compare-inline.json",
        "valid-story-beat-ribbon-inline.json",
        "valid-script-timing-bands-inline.json",
        "valid-shot-timeline-fullscreen.json",
        "valid-visual-direction-compare-inline.json",
        "valid-visual-lock-matrix-inline.json",
        "valid-reference-asset-graph-fullscreen.json",
        "valid-generation-qa-inline.json",
        "valid-image-prompt-handoff-inline.json",
        "valid-video-route-capability-inline.json",
    ]
    with tempfile.TemporaryDirectory(prefix="dircreative-visual-render-") as tmp:
        for filename in fixture_names:
            document = load_document(FIXTURE_ROOT / filename)
            output = Path(tmp) / filename.replace(".json", ".html")
            try:
                write_fragment(document, output, test_output=True, force=False)
            except RenderError as exc:
                failures.append(f"{filename}: {exc}")
                continue
            text = output.read_text(encoding="utf-8")
            for forbidden in ("<!doctype", "<html", "<head", "<body", "fetch(", "XMLHttpRequest", "WebSocket"):
                if forbidden in text:
                    failures.append(f"{filename}: forbidden fragment token {forbidden}")
            if "sendFollowUpMessage" not in text or "writes_authoritative_state" not in text:
                failures.append(f"{filename}: missing interaction or write-boundary evidence")
    worker = load_document(FIXTURE_ROOT / "valid-adco-worker-fallback.json")
    try:
        render_fragment(worker)
        failures.append("orchestrated_worker fixture rendered directly instead of failing closed")
    except RenderError as exc:
        if "provider-hidden" not in str(exc):
            failures.append(f"orchestrated_worker rejected for wrong reason: {exc}")
    hostile = json.loads((FIXTURE_ROOT / "valid-idea-brief-inline.json").read_text(encoding="utf-8"))
    hostile["presentation"]["fields"][1]["value"] = '</script><script>window.__dcInjected = true</script>'
    hostile_fragment = render_fragment(hostile)
    if "<script>window.__dcInjected" in hostile_fragment or "</script><script>" in hostile_fragment:
        failures.append("hostile presentation value escaped the data boundary")
    if "&lt;/script&gt;" not in hostile_fragment or "\\u003c/script\\u003e" not in hostile_fragment:
        failures.append("hostile presentation value missing static and JSON escaping evidence")
    with tempfile.TemporaryDirectory(prefix="dircreative-render-project-root-") as raw:
        project_root = Path(raw)
        media_root = project_root / "media"
        media_root.mkdir()
        external_project = load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json")
        for artifact in external_project["source_truth"]["artifacts"]:
            artifact_path_key = "path" if artifact.get("path") else "evidence_path" if artifact.get("evidence_path") else None
            if artifact_path_key is None:
                continue
            source = ROOT / artifact[artifact_path_key]
            relative = Path("media") / source.name
            (project_root / relative).write_bytes(source.read_bytes())
            artifact[artifact_path_key] = relative.as_posix()
        try:
            external_fragment = render_fragment(external_project, project_root)
            if external_fragment.count('<img src="data:image/') != 2:
                failures.append("external project image render did not embed both previews")
        except RenderError as exc:
            failures.append(f"external project image render failed: {exc}")

        large_image = project_root / external_project["source_truth"]["artifacts"][2]["path"]
        large_image.write_bytes(b"\x89PNG\r\n\x1a\n" + (b"x" * 400_000))
        external_project["source_truth"]["artifacts"][2]["sha256"] = hashlib.sha256(large_image.read_bytes()).hexdigest()
        try:
            render_fragment(external_project, project_root)
            failures.append("oversized image review asset was not rejected")
        except RenderError as exc:
            if "image exceeds 325000 bytes" not in str(exc):
                failures.append(f"oversized image rejected for wrong reason: {exc}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Render validated DIRcreative chat visualization fragments.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    render_parser = subparsers.add_parser("render-html")
    render_parser.add_argument("spec")
    render_parser.add_argument("--output", required=True)
    render_parser.add_argument("--test-output", action="store_true")
    render_parser.add_argument("--force", action="store_true")
    render_parser.add_argument("--project-root")
    subparsers.add_parser("self-test")
    args = parser.parse_args()

    if args.command == "self-test":
        failures = self_test()
        print(f"CHAT_VISUALIZATION_RENDER: {'PASS' if not failures else 'FAIL'}")
        for failure in failures:
            print(f"- {failure}")
        return 0 if not failures else 1

    spec_path = Path(args.spec)
    if not spec_path.is_absolute():
        spec_path = ROOT / spec_path
    output = Path(args.output).expanduser()
    try:
        document = load_document(spec_path)
        project_root = Path(args.project_root).expanduser().resolve() if args.project_root else ROOT
        write_fragment(
            document,
            output,
            test_output=args.test_output,
            force=args.force,
            project_root=project_root,
        )
    except Exception as exc:
        print(f"CHAT_VISUALIZATION_RENDER: FAIL\n- {exc}")
        return 1
    print("CHAT_VISUALIZATION_RENDER: PASS")
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
