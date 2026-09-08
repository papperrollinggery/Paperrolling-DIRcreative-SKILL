"""Model-facing, once-per-video cinematic quality prefix for PromptIR outputs."""
from __future__ import annotations

from typing import Any
from html import unescape
import re

from dircreative_adapters.base import clean, look_text

ORDER = (("Style", "style"), ("Cinematography", "cinematography"), ("Lighting", "lighting"), ("Color", "color"), ("Camera", "camera"), ("Skin", "skin"), ("Acting", "acting"), ("Physics", "physics"), ("Composition", "composition"), ("Continuity", "continuity"), ("Technical", "technical"), ("Audio", "audio"))
NATIVE_AUDIO_ROUTES = {"native", "reference_audio"}


def _text(value: Any) -> str:
    return clean(unescape(value)) if isinstance(value, str) and value.strip() else ""


def _planned(value: Any) -> str:
    """PromptIR uses `none` as a structured no-content declaration."""
    text = _text(value)
    return "" if text.lower() == "none" or text.lower().startswith("none;") else text


def _items(value: Any) -> list[str]:
    return [_text(item) for item in value if _text(item)] if isinstance(value, list) else []


MEDIUM_NEGATION_RE = re.compile(
    r"(?:\b(?:no|not|without|avoid|exclude)\b\s*|"
    r"\bdo\s+not(?:\s+(?:use|render|include))?\s+|\bdon't(?:\s+use)?\s*)"
    r"(?:the\s+)?(?:[a-z0-9_-]*cg[a-z0-9_-]*|3d|cgi|stylized|stylised|动画|插画|定格|漫画|水彩|手绘|像素画|游戏引擎|过场动画)"
    r"(?:\s+or\s+(?:[a-z0-9_-]*cg[a-z0-9_-]*|3d|cgi|stylized|stylised))?",
    re.IGNORECASE,
)
MEDIUM_CHINESE_NEGATION_RE = re.compile(
    r"(?:禁止|不要|不含|无需|不用|避免)\s*"
    r"(?:产品\s*)?(?:cg|cgi|3d|动画|插画|定格|漫画|水彩|手绘|像素画|游戏引擎|过场动画)",
    re.IGNORECASE,
)


def _unit_shots(payload: dict[str, Any], unit: dict[str, Any] | None) -> list[dict[str, Any]]:
    shots = [shot for shot in payload.get("shot_blocks", []) if isinstance(shot, dict)]
    wanted = unit.get("shot_ids") if isinstance(unit, dict) else None
    if not isinstance(wanted, list):
        return shots
    return [shot for shot in shots if shot.get("shot_id") in set(item for item in wanted if isinstance(item, str))]


def _audio_text(payload: dict[str, Any], unit: dict[str, Any] | None) -> str:
    audio = payload.get("audio_plan", {}) if isinstance(payload.get("audio_plan"), dict) else {}
    if audio.get("generation_route") == "none":
        return "silent picture; no generated audio"
    if audio.get("generation_route") not in NATIVE_AUDIO_ROUTES:
        return "silent picture; sound is supplied separately"
    parts = []
    for label in ("dialogue", "voiceover", "ambience", "foley", "sfx", "silence"):
        if value := _planned(audio.get(label)):
            parts.append(f"{label}: {value}")
    if music := _planned(audio.get("music")):
        parts.append(f"music: {music}")
    else:
        parts.append("no score")
    all_shot_ids = {shot.get("shot_id") for shot in payload.get("shot_blocks", []) if isinstance(shot, dict)}
    unit_shot_ids = set(unit.get("shot_ids", [])) if isinstance(unit, dict) else set()
    if unit is not None and unit_shot_ids != all_shot_ids:
        entities = {
            item.get("entity_id"): _text(item.get("external_name"))
            for item in payload.get("entities", [])
            if isinstance(item, dict)
        }
        scoped_events = []
        for shot in _unit_shots(payload, unit):
            for cue in shot.get("audio_cues", []):
                if isinstance(cue, str) and _planned(cue):
                    scoped_events.append(f"sound event: {_planned(cue)}")
                elif isinstance(cue, dict) and _planned(cue.get("cue")):
                    source_id = cue.get("speaker_entity_id") or cue.get("source_entity_id")
                    source = entities.get(source_id, "")
                    source_text = f" from {source}" if source else ""
                    scoped_events.append(
                        f"{_planned(cue.get('kind')) or 'sound event'}{source_text}: {_planned(cue.get('cue'))}"
                    )
        parts.extend(dict.fromkeys(scoped_events))
    if payload.get("output", {}).get("text_policy") != "exact_text":
        parts.append("no subtitles")
    return "; ".join(parts) or "no generated audio content"


def _remove_redundant_sections(prompt: str) -> str:
    """Keep Timeline-internal camera/audio/look text; remove only full sections."""
    return "\n\n".join(section for section in prompt.split("\n\n") if not section.startswith("Continuity:\n") and not section.startswith("Look:\n")).strip()


def _optics_text(layer: Any) -> str:
    if not isinstance(layer, dict):
        return ""
    values = [_text(layer.get("lens_family")), _text(layer.get("filtration")), look_text(layer)]
    return "; ".join(value for value in values if value)


def build_video_quality_prefix(payload: dict[str, Any], unit: dict[str, Any] | None = None) -> str:
    """Render only the relevant, authored quality directions for a submission.

    ``video_quality`` may explicitly supply any of the ordered directions.  In
    its absence, PromptIR facts are forwarded without inventing a camera,
    cadence, human detail, or visual medium.
    """
    if not isinstance(payload, dict):
        raise ValueError("prompt_ir_payload_required")
    overrides = payload.get("video_quality", {})
    if not isinstance(overrides, dict):
        raise ValueError("video_quality_override_must_be_object")
    look = payload.get("render_look", {}) if isinstance(payload.get("render_look"), dict) else {}
    locks = payload.get("global_locks", {}) if isinstance(payload.get("global_locks"), dict) else {}
    composition = payload.get("composition", {}) if isinstance(payload.get("composition"), dict) else {}
    atmosphere = look_text(look.get("atmosphere", {})) if isinstance(look.get("atmosphere"), dict) else ""
    lighting = look_text(look.get("lighting", {})) if isinstance(look.get("lighting"), dict) else ""
    grade = look_text(look.get("grade", {})) if isinstance(look.get("grade"), dict) else ""
    optics = _optics_text(look.get("optics"))
    lens = "; ".join(_items(locks.get("lens_grammar")))
    all_locks: list[str] = []
    for key in ("identity", "product_or_prop", "scene", "composition_axis", "palette_material", "lens_grammar"):
        all_locks.extend(_items(locks.get(key)))
    route = (payload.get("audio_plan") or {}).get("generation_route") if isinstance(payload.get("audio_plan"), dict) else None
    if route in NATIVE_AUDIO_ROUTES:
        all_locks.extend(_items(locks.get("audio_spine")))
    # Preserve source medium statements without converting them into a generic
    # photoreal or live-action requirement.
    medium_source = [_text(payload.get("project", {}).get("intended_use")),
                     *_items(look.get("preserve")), *_items(locks.get("palette_material"))]
    medium_pattern = re.compile(
        r"\b(?:photoreal(?:istic)?[_ -]?cg|stylized[_ -]?cg|animat\w*|anime|cartoon|2d|"
        r"illustrat\w*|stop[- ]?motion|claymation|watercolo[u]?r|pixel[- ]art|hand[- ]drawn|"
        r"stylized|stylised|3d|cgi|cg|cel[- ]shad\w*|game[- ](?:engine|cutscene))\b|"
        r"产品\s*(?:cg|cgi)|(?:cg|cgi)\s*(?:产品|广告|材质|微距)|动画|插画|定格|漫画|水彩|手绘|像素画|游戏引擎|过场动画",
        re.I,
    )
    stated_medium = [
        item for item in medium_source
        if medium_pattern.search(item)
        or MEDIUM_NEGATION_RE.search(item)
        or MEDIUM_CHINESE_NEGATION_RE.search(item)
    ]
    values: dict[str, str] = {}
    if stated_medium:
        values["style"] = "; ".join(dict.fromkeys(stated_medium))
    if lighting or atmosphere:
        values["lighting"] = "; ".join(item for item in (lighting, f"atmosphere: {atmosphere}" if atmosphere else "") if item)
    if grade:
        values["color"] = grade
    if optics or lens:
        values["camera"] = "; ".join(item for item in (optics, lens) if item)
    composition_values = [
        _planned(composition.get(key))
        for key in (
            "visual_center", "subject_hierarchy", "foreground_midground_background",
            "negative_space", "movement_room", "screen_direction", "balance_symmetry",
            "leading_lines_occlusion_parallax", "perspective_depth",
        )
    ]
    if any(composition_values):
        values["composition"] = "; ".join(dict.fromkeys(item for item in composition_values if item))
    continuity_values = [
        *all_locks,
        *_items(look.get("preserve")),
        _planned(look.get("exit_or_continuity")),
    ]
    if any(continuity_values):
        values["continuity"] = "; ".join(dict.fromkeys(item for item in continuity_values if item))
    if isinstance(payload.get("audio_plan"), dict):
        values["audio"] = _audio_text(payload, unit)
    rendered = []
    for label, key in ORDER:
        value = _text(overrides.get(key)) or values.get(key)
        if not value:
            continue
        if key == "audio" and route not in NATIVE_AUDIO_ROUTES:
            value = _audio_text(payload, unit)
        rendered.append(f"{label}: {value}.")
    return "\n".join(rendered)


def wrap_video_prompt(payload: dict[str, Any], prompt: str, unit: dict[str, Any] | None = None) -> str:
    """Prefix one submission while moving top-level Look/Continuity into it."""
    if not isinstance(prompt, str):
        raise ValueError("video_prompt_must_be_string")
    body = _remove_redundant_sections(prompt)
    return build_video_quality_prefix(payload, unit) + ("\n\n" + body if body else "")
