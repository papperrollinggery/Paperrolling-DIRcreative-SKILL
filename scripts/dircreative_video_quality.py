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
    """Return exactly twelve ordered prefix lines for one video submission.

    `video_quality` is an optional explicit twelve-key override map, not a
    mandatory schema field. Existing PromptIR facts remain the source for look,
    camera, continuity and audio.
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
    human_present = any(entity.get("entity_type") in {"human", "character", "person"} for entity in payload.get("entities", []) if isinstance(entity, dict))
    # Preserve existing medium statements without requiring an extra override.
    # Conservatively retain the source wording even when it mentions a medium
    # as an exclusion; never invert it into a mandatory photoreal treatment.
    medium_source = [_text(payload.get("project", {}).get("intended_use")),
                     *_items(look.get("preserve")), *_items(locks.get("palette_material"))]
    medium_pattern = re.compile(
        r"\b(?:photoreal(?:istic)?[_ -]?cg|stylized[_ -]?cg|animat\w*|anime|cartoon|"
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
    explicit_style = _text(overrides.get("style"))
    alternate_medium = bool(stated_medium or medium_pattern.search(explicit_style))
    values = {
        "style": "8K IMAX photoreal cinema, live-action presence, not 3D or game-cutscene rendering",
        "cinematography": (
            "camera shares physical space with performers; painterly silhouette and motivated observation"
            if human_present else
            "camera observes the declared subject and material in physical or virtual space; motivated framing and readable surface detail"
        ),
        "lighting": (lighting + (f"; atmosphere: {atmosphere}" if atmosphere else "")) or "natural sky or window motivated key, backlight, shadow-side camera placement and gentle atmospheric haze",
        "color": (grade + "; maintain a 60:30:10 palette hierarchy") if grade else "60:30:10 palette hierarchy anchored to declared wardrobe, props and environment",
        "camera": "; ".join(item for item in (optics, lens, "cinematic 180-degree-shutter motion character, motivated movement and stable spatial axis") if item),
        "skin": "visible pores, fine vellus hair, asymmetric lived-in detail and natural micro-redness" if human_present else "material-appropriate microtexture, asymmetric detail and physically credible surface response",
        "acting": "accurate eyelines, readable listener reactions, brief pauses, moist eye catchlights and breathing" if human_present else "declared attention, reaction timing and motion cues remain readable",
        "physics": "gravity, inertia, weight transfer, contact, cloth and object consequences remain physically legible",
        "composition": "; ".join(dict.fromkeys(item for item in (
            *(_text(composition.get(key)) for key in ("visual_center", "subject_hierarchy", "foreground_midground_background", "negative_space", "movement_room", "screen_direction", "balance_symmetry", "leading_lines_occlusion_parallax", "perspective_depth")),
            "painterly thirds or golden-ratio relationships within the declared composition",
            "from the first frame, sustain the declared action or restrained living stillness",
        ) if item)),
        "continuity": "; ".join(item for item in (*all_locks, *_items(look.get("preserve")), _text(look.get("exit_or_continuity"))) if item) or "preserve declared identity, props, environment, screen direction and exit state across cuts",
        "technical": "requested 24 fps smooth cinematic motion with 8K-detail intent, stable focus and no jitter",
        "audio": _audio_text(payload, unit),
    }
    if alternate_medium:
        if not explicit_style:
            values["style"] = "; ".join(stated_medium) + "; preserve this declared visual treatment and coherent detail"
        values["skin"] = "preserve the declared character and surface rendering; detail follows the chosen medium and shot scale"
        values["technical"] = "preserve declared cadence and detail treatment; coherent motion and stable framing"
    rendered = []
    for label, key in ORDER:
        value = _text(overrides.get(key)) or values[key]
        if key == "audio" and route not in NATIVE_AUDIO_ROUTES:
            value = values[key]
        rendered.append(f"{label}: {value}.")
    return "\n".join(rendered)


def wrap_video_prompt(payload: dict[str, Any], prompt: str, unit: dict[str, Any] | None = None) -> str:
    """Prefix one submission while moving top-level Look/Continuity into it."""
    if not isinstance(prompt, str):
        raise ValueError("video_prompt_must_be_string")
    body = _remove_redundant_sections(prompt)
    return build_video_quality_prefix(payload, unit) + ("\n\n" + body if body else "")
