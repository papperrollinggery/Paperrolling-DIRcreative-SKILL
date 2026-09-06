from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


REFERENCE_TOKEN_RE = re.compile(r"@(Image|Video|Audio)\s*([0-9]+)", re.IGNORECASE)
INTERNAL_SURFACE_PATTERNS = {
    "internal_shot_or_asset_label": re.compile(r"\b(?:R|S|SHOT|SCENE|ASSET)[-_ ]?0*[0-9]+\b", re.IGNORECASE),
    "internal_asset_id": re.compile(r"\basset_[A-Za-z0-9_-]+\b", re.IGNORECASE),
    "local_path": re.compile(r"(?:/Users/|/home/|/private/|outputs/|docs/film-preproduction/|examples/)", re.IGNORECASE),
    "sha256": re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE),
    "internal_field": re.compile(r"\b(?:schema_version|source_hash|failure_id|retry_rules|manifest)\b", re.IGNORECASE),
    "internal_control_language": re.compile(
        r"\b(?:QA|quality[ -]?assurance|retry|rerun|failure(?:_id)?|pass signal|pass when|"
        r"direct video input policy|pre-generation contract|generation receipt|next_action)\b",
        re.IGNORECASE,
    ),
}


class AdapterContractError(Exception):
    pass


@dataclass(frozen=True)
class PromptBudget:
    max_chars: int
    compression_order: tuple[str, ...]


@dataclass(frozen=True)
class AdapterContract:
    adapter: str
    reference_count: str
    reference_syntax: str
    maximum_references: int | None
    reference_slot_pattern: str | None
    timeline_syntax: str
    multi_shot_support: str
    allowed_unit_lengths_sec: tuple[float, ...]
    minimum_unit_sec: float | None
    maximum_unit_sec: float | None
    camera_handling: str
    audio_handling: str
    look_handling: str
    negative_handling: str
    unsupported_fields: tuple[str, ...]
    prompt_budget: PromptBudget
    native_audio_allowed: bool


@dataclass(frozen=True)
class AdapterRender:
    prompt: str
    sections: tuple[str, ...]
    timeline_bodies: dict[str, str]
    postproduction_audio: tuple[str, ...]
    native_audio: bool


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().rstrip(".")


def ordered_attached_references(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return attachments in the actual upload order.

    Spatial layouts bind to ``upload_order`` rather than the accidental order
    of entries in JSON.  Contracts without that field retain their authored
    order for compatibility with existing adapters.
    """
    attached = [
        (index, item)
        for index, item in enumerate(payload.get("references", []))
        if isinstance(item, dict) and item.get("attached_to_run")
    ]

    def key(entry: tuple[int, dict[str, Any]]) -> tuple[int, int]:
        index, item = entry
        order = item.get("upload_order")
        if isinstance(order, int) and not isinstance(order, bool) and order >= 1:
            return (0, order)
        return (1, index)

    return [item for _, item in sorted(attached, key=key)]


def time_value(raw: Any) -> float:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(float(raw)):
        return float(raw)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid time value: {raw!r}")
    value = raw.strip()
    if ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError(f"invalid time value: {raw!r}")
        return float(parts[0]) * 60 + float(parts[1])
    return float(value)


def time_label(raw: Any) -> str:
    return f"{time_value(raw):05.2f}"


def look_text(layer: dict[str, Any]) -> str:
    if layer.get("intensity") == "none":
        return ""
    ordered = [
        layer.get("condition"),
        layer.get("effect"),
        layer.get("physical_behavior"),
        layer.get("source_direction_quality"),
        layer.get("contrast_shadow"),
        layer.get("medium"),
        layer.get("density_scale"),
        layer.get("light_path_visibility"),
        layer.get("movement"),
        layer.get("white_balance_anchor"),
        layer.get("contrast_gamma"),
        layer.get("black_level"),
        layer.get("highlight_rolloff"),
        layer.get("saturation_density"),
        layer.get("palette_separation"),
        layer.get("grain_halation"),
    ]
    return "; ".join(
        clean(item)
        for item in ordered
        if item and clean(item).lower() != "none by design"
    )


def shared_surface_errors(text: str, allowed_slots: set[str]) -> list[str]:
    errors: list[str] = []
    for code, pattern in INTERNAL_SURFACE_PATTERNS.items():
        match = pattern.search(text)
        if match:
            errors.append(f"{code}: {match.group(0)}")
    used_slots = {
        f"@{kind.title()} {index}"
        for kind, index in REFERENCE_TOKEN_RE.findall(text)
    }
    phantom = sorted(used_slots - allowed_slots)
    missing = sorted(allowed_slots - used_slots)
    if phantom:
        errors.append(f"phantom_reference_slots: {', '.join(phantom)}")
    if missing:
        errors.append(f"attached_reference_slots_missing_from_prompt: {', '.join(missing)}")
    return errors


class PromptAdapter:
    CONTRACT: AdapterContract

    def __init__(self, adapter_name: str | None = None) -> None:
        self.name = adapter_name or self.CONTRACT.adapter

    def prompt_budget(self) -> PromptBudget:
        return self.CONTRACT.prompt_budget

    def validate_capability(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        attached = ordered_attached_references(payload)
        maximum = self.CONTRACT.maximum_references
        if maximum is not None and len(attached) > maximum:
            errors.append(
                f"{self.name} adapter reference count is unsupported: {len(attached)} > {maximum}"
            )
        pattern = self.CONTRACT.reference_slot_pattern
        if pattern:
            invalid = [
                item.get("platform_slot", "")
                for item in attached
                if re.fullmatch(pattern, str(item.get("platform_slot", ""))) is None
            ]
            if invalid:
                errors.append(
                    f"{self.name.title()} attached references require explicit @ slots: {', '.join(invalid)}"
                )

        allowed = self.CONTRACT.allowed_unit_lengths_sec
        minimum = self.CONTRACT.minimum_unit_sec
        maximum_unit = self.CONTRACT.maximum_unit_sec
        for unit in payload.get("generation_plan", {}).get("units", []):
            try:
                duration = time_value(unit["time_end"]) - time_value(unit["time_start"])
            except (KeyError, ValueError) as exc:
                errors.append(f"{self.name} adapter timeline is invalid: {exc}")
                continue
            if allowed and not any(math.isclose(duration, item, abs_tol=0.001) for item in allowed):
                errors.append(
                    f"generation unit duration is unsupported by {self.name} adapter: {duration:g} seconds"
                )
            if minimum is not None and duration < minimum - 0.001:
                errors.append(
                    f"generation unit duration is unsupported by {self.name} adapter: {duration:g} < {minimum:g}"
                )
            if maximum_unit is not None and duration > maximum_unit + 0.001:
                errors.append(
                    f"generation unit duration is unsupported by {self.name} adapter: {duration:g} > {maximum_unit:g}"
                )

        audio_route = payload.get("audio_plan", {}).get("generation_route")
        if audio_route in {"native", "reference_audio"} and not self.CONTRACT.native_audio_allowed:
            errors.append(f"native audio is not verified for {self.name} adapter")
        return errors

    def reference_label(self, item: dict[str, Any], index: int) -> str:
        return f"Attached reference image {index}"

    def subject_heading(self) -> str:
        return "Subjects and assets:"

    def include_look(self) -> bool:
        return True

    def allowed_surface_slots(self, payload: dict[str, Any]) -> set[str]:
        return set()

    def surface_errors(self, text: str, payload: dict[str, Any]) -> list[str]:
        errors = shared_surface_errors(text, self.allowed_surface_slots(payload))
        if "Timeline:\n" not in text:
            errors.append(f"timeline_syntax_invalid: expected {self.CONTRACT.timeline_syntax}")
        budget = self.prompt_budget()
        if len(text) > budget.max_chars:
            errors.append(
                "prompt_budget_exceeded: "
                f"adapter={self.name} chars={len(text)} max={budget.max_chars} "
                f"compression_order={','.join(budget.compression_order)}"
            )
        return errors

    def compile_full(self, payload: dict[str, Any]) -> str:
        render = self._render(payload)
        errors = self.surface_errors(render.prompt, payload)
        if errors:
            raise AdapterContractError("; ".join(errors))
        return render.prompt

    def compile_unit(self, payload: dict[str, Any], unit: dict[str, Any]) -> str:
        render = self._render(payload)
        output = payload["output"]
        unit_start = time_value(unit["time_start"])
        unit_end = time_value(unit["time_end"])
        unit_duration = unit_end - unit_start
        duration_source = f"{clean(output['target_duration_sec'])}-second"
        duration_target = f"{unit_duration:g}-second"
        prefix_sections = [
            section
            for section in render.sections
            if not section.startswith("Timeline:")
            and not section.startswith("Look:")
            and not section.startswith("Transitions:")
        ]
        look_sections = [section for section in render.sections if section.startswith("Look:")]
        local_prefix: list[str] = []
        for section in prefix_sections:
            if section.startswith("Subjects and assets:") or section.startswith("Motion subjects:"):
                unit_entity_lines = []
                for entity in payload["entities"]:
                    immutable = "; ".join(clean(value) for value in entity["immutable"])
                    unit_entity_lines.append(f"{clean(entity['external_name'])}: preserve {immutable}.")
                local_prefix.append("Subjects and assets:\n" + "\n".join(unit_entity_lines))
            else:
                local_prefix.append(section.replace(duration_source, duration_target))
        handoff_lines = [
            f"Begin with {clean(unit['incoming_state'])}.",
            f"End with {clean(unit['outgoing_state'])}.",
        ]
        if render.native_audio:
            handoff_lines.append(f"Carry the audio boundary as {clean(unit['audio_handoff'])}.")
        shot_map = {shot["shot_id"]: shot for shot in payload["shot_blocks"]}
        local_timeline: list[str] = []
        for shot_id in unit["shot_ids"]:
            shot = shot_map[shot_id]
            local_start = time_value(shot["time_start"]) - unit_start
            local_end = time_value(shot["time_end"]) - unit_start
            local_timeline.append(
                f"{time_label(local_start)}-{time_label(local_end)}: {render.timeline_bodies[shot_id]}"
            )
        sections = [
            *local_prefix,
            "State continuity:\n" + "\n".join(handoff_lines),
            "Timeline:\n" + "\n".join(local_timeline),
            *look_sections,
        ]
        prompt = "\n\n".join(sections).strip() + "\n"
        errors = self.surface_errors(prompt, payload)
        if errors:
            raise AdapterContractError("; ".join(errors))
        return prompt

    def postproduction_audio(self, payload: dict[str, Any]) -> list[str]:
        return list(self._render(payload).postproduction_audio)

    def unit_postproduction_audio(self, payload: dict[str, Any], unit: dict[str, Any]) -> list[str]:
        if self._render(payload).native_audio:
            return []
        return [clean(unit["audio_handoff"])]

    def _render(self, payload: dict[str, Any]) -> AdapterRender:
        attached = ordered_attached_references(payload)
        entity_names = {item["entity_id"]: item["external_name"] for item in payload["entities"]}
        sections: list[str] = []
        if attached:
            reference_lines = []
            for index, item in enumerate(attached, start=1):
                preserve = "; ".join(clean(value) for value in item["preserve"])
                anti = "; ".join(clean(value) for value in item["anti_misread"])
                label = self.reference_label(item, index)
                line = f"{label} is {clean(item['role'])}. Preserve {preserve}."
                if anti:
                    line += f" Keep the reference role limited to this job: {anti}."
                reference_lines.append(line)
            sections.append("References:\n" + "\n".join(reference_lines))

        output = payload["output"]
        project = payload["project"]
        composition = payload["composition"]
        duration_phrase = f"{clean(output['target_duration_sec'])}-second"
        intended_use = clean(project["intended_use"])
        if duration_phrase.lower() not in intended_use.lower():
            intended_use = f"{duration_phrase} {intended_use}"
        sections.append(
            f"Create a {intended_use} in {clean(output['aspect_ratio'])}. "
            f"Purpose: {clean(composition['narrative_purpose'])}."
        )

        entity_lines = []
        for entity in payload["entities"]:
            immutable = "; ".join(clean(value) for value in entity["immutable"])
            entity_lines.append(
                f"{clean(entity['external_name'])}: starts {clean(entity['starting_state'])}, "
                f"positioned {clean(entity['screen_position'])}. Keep {immutable}."
            )
        sections.append(self.subject_heading() + "\n" + "\n".join(entity_lines))

        native_audio = payload["audio_plan"]["generation_route"] in {"native", "reference_audio"}
        lock_values: list[str] = []
        for lock_name, values in payload["global_locks"].items():
            if lock_name == "audio_spine" and not native_audio:
                continue
            lock_values.extend(clean(value) for value in values if clean(value))
        sections.append("Continuity:\n" + "; ".join(lock_values) + ".")

        timeline_lines: list[str] = []
        timeline_bodies: dict[str, str] = {}
        postproduction_audio: list[str] = []
        for shot in sorted(payload["shot_blocks"], key=lambda item: time_value(item["time_start"])):
            parts = [clean(shot["story_beat"]), clean(shot["emotional_or_attention_beat"])]
            for action in shot["entity_actions"]:
                owner = clean(entity_names[action["owner_entity_id"]])
                target = action.get("target_entity_id")
                target_text = f" toward {clean(entity_names[target])}" if target else ""
                action_text = (
                    f"{owner} starts {clean(action['initial_state'])}. After {clean(action['trigger'])}, "
                    f"{clean(action['path'])}{target_text}. End with {clean(action['final_state'])}"
                )
                if action.get("physical_consequence"):
                    action_text += f". Physical result: {clean(action['physical_consequence'])}"
                parts.append(action_text)
            environment = shot["environment_action"]
            environment_parts = [clean(value) for value in environment.values() if clean(value)]
            if environment_parts:
                parts.append("Environment: " + "; ".join(environment_parts))
            camera = shot["camera"]
            parts.append(
                "Camera: "
                f"{clean(camera['shot_size'])}, {clean(camera['angle_height_axis'])}, {clean(camera['support'])}; "
                f"start on {clean(camera['start_target'])}, {clean(camera['path'])}, end on {clean(camera['end_target'])}; "
                f"{clean(camera['speed_easing'])}; focus {clean(camera['focus'])}. "
                f"The move is motivated by {clean(camera['motivation'])}"
            )
            parts.append("Composition: " + clean(shot["composition_state"]))
            if shot.get("look_delta") and clean(shot["look_delta"]).lower() != "none by design":
                parts.append("Look change: " + clean(shot["look_delta"]))
            cue_texts = []
            for cue in shot["audio_cues"]:
                if isinstance(cue, str):
                    cue_text = clean(cue)
                else:
                    speaker = cue.get("speaker_entity_id") or cue.get("source_entity_id")
                    speaker_text = f" from {clean(entity_names[speaker])}" if speaker else ""
                    cue_text = (
                        f"{clean(cue['time'])} {clean(cue['kind'])}{speaker_text}: "
                        f"{clean(cue['cue'])}, {clean(cue['perspective'])}"
                    )
                if native_audio:
                    cue_texts.append(cue_text)
                else:
                    postproduction_audio.append(cue_text)
            if cue_texts:
                parts.append("Audio: " + "; ".join(cue_texts))
            timeline_bodies[shot["shot_id"]] = ". ".join(parts) + "."
            timeline_lines.append(
                f"{time_label(shot['time_start'])}-{time_label(shot['time_end'])}: "
                f"{timeline_bodies[shot['shot_id']]}"
            )
        sections.append("Timeline:\n" + "\n".join(timeline_lines))

        look = payload["render_look"]
        look_lines = []
        for label in ("lighting", "optics", "atmosphere", "grade"):
            value = look_text(look[label])
            if value:
                look_lines.append(f"{label.title()}: {value}.")
        if look_lines and self.include_look():
            look_lines.append("Preserve " + "; ".join(clean(value) for value in look["preserve"]) + ".")
            look_lines.append(clean(look["exit_or_continuity"]) + ".")
            sections.append("Look:\n" + "\n".join(look_lines))

        transitions = payload.get("transition_plan", [])
        if transitions:
            transition_lines = []
            for item in transitions:
                transition_lines.append(
                    f"{clean(item['visual_bridge'])}; preserve {clean(item['continuity_state'])}."
                )
                if item.get("audio_bridge") and not native_audio:
                    postproduction_audio.append(clean(item["audio_bridge"]))
            sections.append("Transitions:\n" + "\n".join(transition_lines))

        prompt = "\n\n".join(section for section in sections if section).strip() + "\n"
        return AdapterRender(
            prompt=prompt,
            sections=tuple(sections),
            timeline_bodies=timeline_bodies,
            postproduction_audio=tuple(postproduction_audio),
            native_audio=native_audio,
        )
