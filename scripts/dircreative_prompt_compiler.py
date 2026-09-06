#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dircreative_state_audit import _builtin_schema_errors
from dircreative_model_capability_audit import REGISTRY_PATH, load_yaml
from dircreative_adapters import AdapterContractError, get_adapter, shared_surface_errors
from dircreative_adapters.base import (
    INTERNAL_SURFACE_PATTERNS,
    clean as _clean,
    ordered_attached_references,
)
from dircreative_verify_release import read_relative_regular_file_once


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/prompt-ir.schema.json"
MAX_PROMPT_IR_BYTES = 4 * 1024 * 1024
MAX_PROJECT_FILE_BYTES = 32 * 1024 * 1024

ASSET_ROLE_LABELS = {
    "product_identity_board": "产品身份参考图 / PRODUCT IDENTITY REFERENCE",
    "prop_continuity_board": "道具连续性参考图 / PROP CONTINUITY REFERENCE",
    "scene_geography_camera_fov_reference": "场景空间+镜头视场参考图 / SCENE GEOGRAPHY + CAMERA FOV REFERENCE",
    "lighting_material_style_board": "灯光+材质风格参考图 / LIGHTING + MATERIAL STYLE REFERENCE",
}
ASSET_ROLE_RULES = {
    "product_identity_board": "Preserve exact silhouette, scale, construction, material and function. Keep approved packaging marks readable; add no unrelated scene, person, panel or invented label.",
    "prop_continuity_board": "Preserve exact shape, interface, material, orientation and state. This board cannot control a future scene, ground surface, support, camera or lighting.",
    "scene_geography_camera_fov_reference": "Preserve fixed architecture, landmarks, entrances, axes, scale, support relations and ground surface. Keep the scene empty of characters and temporary action.",
    "lighting_material_style_board": "Control only palette, exposure, contrast, highlight rolloff, atmosphere and material response. Do not redesign identity, geometry, action or props.",
}
JINGZAO_COMPILED_ROLES = {
    "storyboard_frame",
    "clean_first_frame",
    "clean_key_frame",
    "clean_end_frame",
}
DETERMINISTIC_LAYOUT_ROLES = {"professional_storyboard_motion_map"}
def character_pose_lock(details: list[str]) -> str:
    pose_details = [
        item
        for item in details
        if re.search(r"\bpose\b", item.lower()) is not None or "姿势" in item
    ]
    if pose_details:
        return "; ".join(pose_details)
    return (
        "neutral 20-degree A-pose, straight elbows, both hands fully visible, feet apart, "
        "clear arm-to-torso gaps and an anatomically legible back view"
    )


def build_character_master_prompt(
    *,
    identity: str,
    wardrobe: str,
    materials: str,
    side_specific: str,
    pose_lock: str,
) -> str:
    return " ".join(
        (
            "Create one professional photorealistic headed character master sheet from the approved identity and wardrobe facts.",
            identity.strip(),
            wardrobe.strip(),
            materials.strip(),
            side_specific.strip(),
            "Use one fully opaque wide physical image on a neutral mid-gray seamless background with soft even studio light and no cinematic grade.",
            "Place one dominant high-resolution front-facing face close-up framed crown-to-neck at the far left, head level and facing the camera with both eyes and both sides of the face visible.",
            "After it, use one single horizontal row of four full-body headed views at identical scale and one shared ground line: Panel 1 front; Panel 2 left profile; Panel 3 right profile; Panel 4 back.",
            "Panel 2 shows the subject's anatomical left side to camera and the nose points frame-left; Panel 3 shows the anatomical right side and the nose points frame-right. Panels 2 and 3 are not interchangeable or mirror substitutes.",
            "The portrait and every full-body subject must each span at least 75% of the canvas height.",
            "Keep the same face, body proportions, hair, outfit construction, materials, accessories, footwear, hands and side-specific placements in every view.",
            f"Pose lock: {pose_lock.strip()}. Do not relax, mirror or replace the approved pose.",
            "Keep every named left/right detail on the subject's anatomical side and at its declared garment or body anchor in front, profile and back views.",
            "Accurate anatomy and complete head-to-toe framing. Do not add any prop, tool or accessory absent from the approved facts, including clips, carabiners, holsters, pouches, waist tools or dangling equipment. No 2x2 grid, alternate identity, costume variant, text, labels, borders, logos or watermark.",
        )
    )


def build_character_master_prompt_from_contract(
    authoritative_purpose: str,
    contract: dict[str, Any],
) -> str:
    details = [str(item) for item in contract.get("side_specific_details", [])]
    pose_lock = character_pose_lock(details)
    return build_character_master_prompt(
        identity=authoritative_purpose,
        wardrobe="; ".join(str(item) for item in contract.get("wardrobe_facts", [])),
        materials="; ".join(str(item) for item in contract.get("wardrobe_materials", [])),
        side_specific="; ".join(details),
        pose_lock=pose_lock,
    )


def build_headed_state_prompt_from_contract(
    authoritative_purpose: str,
    contract: dict[str, Any],
) -> str:
    details = [str(item) for item in contract.get("side_specific_details", [])]
    pose_lock = character_pose_lock(details)
    return " ".join(
        (
            "Create one professional photorealistic headed character state derivative from the approved headed master.",
            "Use the attached approved headed master as the sole identity and wardrobe reference.",
            authoritative_purpose.strip(),
            "; ".join(str(item) for item in contract.get("state_facts", [])),
            "Change only the declared visible state; preserve the same identity, body, hair, outfit construction, materials, accessories, footwear and side-specific placements.",
            "Use one fully opaque wide physical image on a neutral mid-gray seamless background with soft even studio light and no cinematic grade.",
            "Place one dominant high-resolution front-facing face close-up framed crown-to-neck at the far left, head level and facing the camera with both eyes and both sides of the face visible.",
            "After it, use one single horizontal row of four full-body headed views at identical scale and one shared ground line: Panel 1 front; Panel 2 left profile; Panel 3 right profile; Panel 4 back.",
            "Panel 2 shows the subject's anatomical left side to camera and the nose points frame-left; Panel 3 shows the anatomical right side and the nose points frame-right. Panels 2 and 3 are not interchangeable or mirror substitutes.",
            "The portrait and every full-body subject must each span at least 75% of the canvas height.",
            f"Pose lock: {pose_lock}. Do not relax, mirror or replace the approved pose.",
            "Keep every named left/right detail on the subject's anatomical side and declared anchor. Accurate anatomy and complete head-to-toe framing. Do not add any prop, tool or accessory absent from the approved facts, including clips, carabiners, holsters, pouches, waist tools or dangling equipment. No 2x2 grid, alternate identity, unrelated damage, costume variant, text, labels, logos or watermark.",
        )
    )


def build_headless_safe_prompt_from_contract(
    authoritative_purpose: str,
    contract: dict[str, Any],
) -> str:
    return " ".join(
        (
            "Create one professional photorealistic headless-safe character sheet derived only from the approved headed master.",
            "Use the attached approved headed master as the sole identity and wardrobe reference.",
            authoritative_purpose.strip(),
            "Preserve identical body proportions, outfit construction, materials, accessories, footwear, hands, cuffs and left/right placements.",
            "Use one fully opaque wide physical image on a neutral mid-gray seamless background with soft even studio light and no cinematic grade.",
            "Place one dominant high-resolution front-facing face close-up framed crown-to-neck at the far left, head level and facing the camera; it is the only readable face.",
            "After it, use one single horizontal row of four fully headless full-body silhouettes at identical scale and one shared ground line: Panel 1 front; Panel 2 left profile; Panel 3 right profile; Panel 4 back. Panels 2 and 3 are not interchangeable or mirror substitutes.",
            "The portrait and every full-body subject must each span at least 75% of the canvas height.",
            "Remove every body head from the neck opening upward while preserving natural hands, rear collar, inner back neckline and collar-ring continuity.",
            "No 2x2 grid, mannequin head, tiny body face, alternate identity, missing hand, erased collar, props, text, labels, logos or watermark.",
        )
    )


def build_character_prompt_from_contract(
    authoritative_purpose: str,
    contract: dict[str, Any],
) -> str:
    mode = contract.get("mode")
    if mode == "headed_master":
        return build_character_master_prompt_from_contract(authoritative_purpose, contract)
    if mode == "headed_state":
        return build_headed_state_prompt_from_contract(authoritative_purpose, contract)
    if mode == "headless_safe":
        return build_headless_safe_prompt_from_contract(authoritative_purpose, contract)
    raise ValueError(f"unsupported character master mode: {mode}")


def build_asset_role_prompt(asset: dict[str, Any], visual_plan: dict[str, Any]) -> str:
    role = str(asset.get("role"))
    if role in JINGZAO_COMPILED_ROLES:
        raise ValueError(
            f"{role} requires a validated storyboard_frame_to_jingzao_v1 prompt manifest"
        )
    if role in DETERMINISTIC_LAYOUT_ROLES:
        raise ValueError(
            f"{role} must be assembled from approved storyboard frames, not generated by imagegen"
        )
    purpose = str(asset.get("purpose"))
    label = ASSET_ROLE_LABELS.get(role)
    rule = ASSET_ROLE_RULES.get(role)
    if label is None or rule is None:
        raise ValueError(f"unsupported asset prompt role: {role}")
    if visual_plan.get("scope") == "asset_only":
        aspect = visual_plan.get("delivery_profile", {}).get("aspect_ratio")
        return f"{purpose}\nImage aspect ratio: {aspect}. {rule}"
    # Identity/hashes remain bound in the execution packet. The image model
    # needs visual instructions and the real attachments, not control metadata.
    aspect = visual_plan.get("delivery_profile", {}).get("aspect_ratio")
    canvas = f"Image aspect ratio: {aspect}. " if aspect else ""
    return (
        f"Create a reference board. Largest title on the page: {label}. "
        f"{canvas}{purpose} {rule}"
    )



class PromptContractError(Exception):
    pass


@dataclass(frozen=True)
class CompileResult:
    prompt: str
    unit_prompts: list[str]
    adapter: str
    attached_slots: list[str]
    upload_mapping: list[dict[str, Any]]
    postproduction_audio: list[str]
    unit_postproduction_audio: list[list[str]]
    structural_score: int


def _schema_errors(payload: object) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return _builtin_schema_errors(payload, schema, schema, "$")
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    ]


def _time_value(raw: Any) -> float:
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


def terminal_surface_errors(text: str, allowed_slots: set[str] | None = None) -> list[str]:
    return shared_surface_errors(text, allowed_slots or set())


def spatial_export_prompt_ir_bindings(
    export_binding: dict[str, Any], project_root: Path, *, platform_slot: str, upload_order: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert one verified spatial export into existing IR asset/reference shapes."""
    from dircreative_spatial_scene import read_export, validate_export

    root = project_root.resolve(strict=True)
    path = (root / str(export_binding["relative_path"])).resolve(strict=True)
    path.relative_to(root)
    if hashlib.sha256(path.read_bytes()).hexdigest() != export_binding.get("sha256"):
        raise ValueError("spatial export source hash mismatch")
    export = read_export(path, root)
    if validate_export(export, root):
        raise ValueError("spatial export is invalid")
    reference = export["reference"]
    asset_id = str(reference["asset_id"])
    asset = {
        "asset_id": asset_id, "source_kind": "project_file", "source_locator": reference["relative_path"],
        "source_hash": reference["sha256"], "spatial_source": dict(export_binding),
        "spatial_context": {"shot_id": export["shot_id"], "phase": export["phase"]},
        "source_authorization": "project_owned", "role": "layout_reference", "locked": True,
        "reuse_action": "direct_reference", "preserve": ["position", "pose", "occlusion"], "may_change": [],
        "do_not_copy_or_animate": ["character identity", "prop identity", "material", "final art style"],
        "downstream_slots": [platform_slot],
    }
    reference_binding = {
        "platform_slot": platform_slot, "upload_order": upload_order, "asset_id": asset_id,
        "role": "layout reference for position, pose, occlusion, and camera-side staging",
        "direct_input_policy": "allowed", "attached_to_run": True, "required_for_shot": True,
        "preserve": ["position", "pose", "occlusion"],
        "anti_misread": ["do not control identity, material, or final art style"],
    }
    return asset, reference_binding


def semantic_errors(
    payload: dict[str, Any], *, verify_project_files: bool = True, project_root: Path = ROOT
) -> list[str]:
    errors = _schema_errors(payload)
    if errors:
        return errors

    assets = payload["intake"]["supplied_assets"]
    asset_ids = [item["asset_id"] for item in assets]
    if len(asset_ids) != len(set(asset_ids)):
        errors.append("asset_id values must be unique")
    asset_map = {item["asset_id"]: item for item in assets}
    try:
        resolved_project_root = project_root.expanduser().resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        return ["project root is invalid"]
    for asset in assets:
        if asset["source_kind"] == "project_file":
            if not asset.get("source_hash"):
                errors.append(f"project_file asset requires source_hash: {asset['asset_id']}")
            if verify_project_files:
                locator = asset["source_locator"]
                try:
                    payload_bytes = read_relative_regular_file_once(
                        resolved_project_root,
                        locator,
                        max_bytes=MAX_PROJECT_FILE_BYTES,
                        label=f"project_file asset {asset['asset_id']}",
                    )
                except (OSError, ValueError):
                    errors.append(f"project_file asset is invalid: {locator}")
                else:
                    actual_hash = hashlib.sha256(payload_bytes).hexdigest()
                    if asset.get("source_hash") and actual_hash != asset["source_hash"]:
                        errors.append(f"project_file asset hash mismatch: {asset['asset_id']}")
        if asset.get("role") == "layout_reference":
            spatial_source = asset.get("spatial_source")
            if (
                asset.get("source_kind") != "project_file"
                or asset.get("source_authorization") != "project_owned"
                or asset.get("locked") is not True
                or not isinstance(spatial_source, dict)
            ):
                errors.append(f"layout reference lacks a bound current spatial export: {asset['asset_id']}")
                continue
            try:
                from dircreative_spatial_scene import read_export, validate_export

                export_path = (resolved_project_root / spatial_source["relative_path"]).resolve(strict=True)
                export_path.relative_to(resolved_project_root)
                if hashlib.sha256(export_path.read_bytes()).hexdigest() != spatial_source.get("sha256"):
                    raise ValueError("spatial export source hash mismatch")
                export = read_export(export_path, resolved_project_root)
                export_errors = validate_export(export, resolved_project_root)
                reference = export.get("reference", {})
                if not isinstance(reference, dict):
                    raise ValueError("spatial export layout reference is invalid")
            except (ImportError, KeyError, OSError, RuntimeError, ValueError):
                errors.append(f"layout reference spatial export is invalid: {asset['asset_id']}")
                continue
            if export_errors:
                errors.extend(f"layout reference spatial export: {error}" for error in export_errors)
                continue
            context = asset.get("spatial_context")
            if not isinstance(context, dict) or (
                export.get("shot_id") != context.get("shot_id")
                or export.get("phase") != context.get("phase")
            ):
                errors.append(f"layout reference spatial context does not match current export: {asset['asset_id']}")
                continue
            if (
                reference.get("relative_path") != asset.get("source_locator")
                or reference.get("sha256") != asset.get("source_hash")
                or reference.get("role") != "layout"
                or reference.get("media_class") != "layout_reference"
            ):
                errors.append(f"layout reference does not match current export: {asset['asset_id']}")

    references = payload["references"]
    slots = [item["platform_slot"] for item in references]
    if len(slots) != len(set(slots)):
        errors.append("platform_slot values must be unique")
    for item in references:
        asset = asset_map.get(item["asset_id"])
        if asset is None:
            errors.append(f"reference uses unknown asset_id: {item['asset_id']}")
            continue
        if item["attached_to_run"] and item["direct_input_policy"] == "planning_only":
            errors.append(f"planning-only reference cannot be attached: {item['platform_slot']}")
        if item["required_for_shot"] and not item["attached_to_run"]:
            errors.append(f"required reference is not attached: {item['platform_slot']}")
        if item["attached_to_run"] and not asset["locked"]:
            errors.append(f"attached reference asset is not locked: {item['asset_id']}")
    attached = [item for item in references if item["attached_to_run"]]
    uses_layout = any(asset_map.get(item["asset_id"], {}).get("role") == "layout_reference" for item in attached)
    if uses_layout:
        upload_orders = [item.get("upload_order") for item in attached]
        if any(not isinstance(order, int) or isinstance(order, bool) for order in upload_orders):
            errors.append("spatial upload mapping requires upload_order for every attached reference")
        elif sorted(upload_orders) != list(range(1, len(attached) + 1)):
            errors.append("spatial upload_order values must be continuous and unique")
        for item in attached:
            slot = str(item.get("platform_slot", ""))
            match = re.fullmatch(r"@Image\s+(\d+)", slot)
            if match and item.get("upload_order") != int(match.group(1)):
                errors.append(f"spatial upload_order does not match platform slot: {slot}")

    entities = payload["entities"]
    entity_ids = [item["entity_id"] for item in entities]
    if len(entity_ids) != len(set(entity_ids)):
        errors.append("entity_id values must be unique")
    entity_map = {item["entity_id"]: item for item in entities}
    for entity in entities:
        for asset_id in entity["reference_asset_ids"]:
            if asset_id not in asset_map:
                errors.append(f"entity {entity['entity_id']} uses unknown reference asset: {asset_id}")
        owner = entity.get("owner_entity_id")
        if owner and owner not in entity_map:
            errors.append(f"entity {entity['entity_id']} has unknown owner: {owner}")
        for code, pattern in INTERNAL_SURFACE_PATTERNS.items():
            if code in {"internal_field", "sha256"}:
                continue
            if pattern.search(entity["external_name"]):
                errors.append(f"entity external_name exposes {code}: {entity['entity_id']}")
    for entity in entities:
        visited: set[str] = set()
        cursor = entity.get("owner_entity_id")
        while cursor:
            if cursor == entity["entity_id"] or cursor in visited:
                errors.append(f"entity ownership cycle includes: {entity['entity_id']}")
                break
            visited.add(cursor)
            cursor = entity_map.get(cursor, {}).get("owner_entity_id")

    shots = payload["shot_blocks"]
    shot_ids = [item["shot_id"] for item in shots]
    if len(shot_ids) != len(set(shot_ids)):
        errors.append("shot_id values must be unique")
    try:
        shot_times = [(_time_value(item["time_start"]), _time_value(item["time_end"]), item) for item in shots]
    except ValueError as exc:
        errors.append(str(exc))
        shot_times = []
    if shot_times:
        shot_times.sort(key=lambda item: item[0])
        cursor = 0.0
        for start, end, shot in shot_times:
            if end <= start:
                errors.append(f"shot has non-positive duration: {shot['shot_id']}")
            if not math.isclose(start, cursor, abs_tol=0.001):
                errors.append(f"shot timeline gap or overlap before {shot['shot_id']}: expected {cursor:.2f}, got {start:.2f}")
            cursor = end
            action_owners = [action["owner_entity_id"] for action in shot["entity_actions"]]
            duplicate_owners = sorted({owner for owner in action_owners if action_owners.count(owner) > 1})
            if duplicate_owners:
                errors.append(f"shot {shot['shot_id']} has conflicting actions for owners: {', '.join(duplicate_owners)}")
            for action in shot["entity_actions"]:
                owner = action["owner_entity_id"]
                target = action.get("target_entity_id")
                if owner not in entity_map:
                    errors.append(f"shot {shot['shot_id']} action has unknown owner: {owner}")
                if target and target not in entity_map:
                    errors.append(f"shot {shot['shot_id']} action has unknown target: {target}")
            for cue in shot["audio_cues"]:
                if not isinstance(cue, dict):
                    continue
                for field in ("speaker_entity_id", "source_entity_id"):
                    entity_id = cue.get(field)
                    if entity_id and entity_id not in entity_map:
                        errors.append(f"shot {shot['shot_id']} audio cue has unknown {field}: {entity_id}")
                try:
                    cue_time = _time_value(cue["time"])
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if cue_time < start - 0.001 or cue_time > end + 0.001:
                        errors.append(f"shot {shot['shot_id']} audio cue falls outside shot: {cue['time']}")
        target = float(payload["output"]["target_duration_sec"])
        if not math.isclose(cursor, target, abs_tol=0.001):
            errors.append(f"shot timeline ends at {cursor:.2f}, expected {target:.2f}")

    units = payload["generation_plan"]["units"]
    unit_ids = [item["unit_id"] for item in units]
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("generation unit_id values must be unique")
    try:
        unit_times = [(_time_value(item["time_start"]), _time_value(item["time_end"]), item) for item in units]
    except ValueError as exc:
        errors.append(str(exc))
        unit_times = []
    if unit_times:
        unit_times.sort(key=lambda item: item[0])
        cursor = 0.0
        max_unit = float(payload["output"]["generation_unit_sec"])
        assigned_shots: list[str] = []
        for unit_index, (start, end, unit) in enumerate(unit_times):
            if not math.isclose(start, cursor, abs_tol=0.001):
                errors.append(f"generation unit gap or overlap before {unit['unit_id']}")
            if end <= start or end - start > max_unit + 0.001:
                errors.append(f"generation unit exceeds allowed duration: {unit['unit_id']}")
            unknown = sorted(set(unit["shot_ids"]) - set(shot_ids))
            if unknown:
                errors.append(f"generation unit {unit['unit_id']} uses unknown shots: {', '.join(unknown)}")
            assigned_shots.extend(unit["shot_ids"])
            for shot_id in unit["shot_ids"]:
                if shot_id not in shot_ids:
                    continue
                shot_start, shot_end, _ = next(item for item in shot_times if item[2]["shot_id"] == shot_id)
                if shot_start < start - 0.001 or shot_end > end + 0.001:
                    errors.append(f"generation unit {unit['unit_id']} does not contain shot {shot_id}")
            if unit_index + 1 < len(unit_times):
                next_unit = unit_times[unit_index + 1][2]
                if unit["outgoing_handoff_key"] != next_unit["incoming_handoff_key"]:
                    errors.append(f"generation unit handoff key mismatch: {unit['unit_id']} -> {next_unit['unit_id']}")
                if _clean(unit["outgoing_state"]).lower() != _clean(next_unit["incoming_state"]).lower():
                    errors.append(f"generation unit handoff state mismatch: {unit['unit_id']} -> {next_unit['unit_id']}")
            cursor = end
        missing_shots = sorted(set(shot_ids) - set(assigned_shots))
        duplicate_shots = sorted({shot_id for shot_id in assigned_shots if assigned_shots.count(shot_id) > 1})
        if missing_shots:
            errors.append(f"generation units do not cover shots: {', '.join(missing_shots)}")
        if duplicate_shots:
            errors.append(f"generation units assign shots more than once: {', '.join(duplicate_shots)}")
        target = float(payload["output"]["target_duration_sec"])
        if not math.isclose(cursor, target, abs_tol=0.001):
            errors.append(f"generation units end at {cursor:.2f}, expected {target:.2f}")
        if target > max_unit and len(unit_times) < 2:
            errors.append("target duration exceeds one generation unit but generation_plan does not split the work")

    adapter = payload["generation_plan"]["selected_adapter"]
    if adapter != payload["capability"]["model_key"] and adapter != "generic":
        errors.append("generation_plan.selected_adapter does not match capability.model_key")
    attached = [item for item in references if item["attached_to_run"]]
    try:
        errors.extend(get_adapter(adapter).validate_capability(payload))
    except AdapterContractError as exc:
        errors.append(str(exc))
    if payload["audio_plan"]["generation_route"] == "reference_audio":
        attached_audio = [
            item for item in attached
            if asset_map.get(item["asset_id"], {}).get("role") == "audio"
        ]
        if not attached_audio:
            errors.append("reference_audio route requires an attached audio reference")

    try:
        registry = load_yaml(REGISTRY_PATH)
        cards = {card["capability_card_id"]: card for card in registry.get("models", [])}
        selected = cards.get(payload["capability"]["capability_card_id"])
        if selected is None:
            errors.append("capability_card_id does not resolve in model-sources registry")
        else:
            expected = {
                "model_key": selected.get("model_key"),
                "version": str(selected.get("version")),
                "provider_surface": selected.get("provider_surface"),
            }
            for field, value in expected.items():
                if str(payload["capability"].get(field)) != str(value):
                    errors.append(f"capability {field} does not match resolved card")
            if selected.get("status") != "current":
                errors.append("capability card is not current")
            storyboard_references = [
                item for item in attached
                if asset_map.get(item.get("asset_id"), {}).get("role") == "storyboard_motion"
            ]
            for item in storyboard_references:
                role_text = str(item.get("role", "")).lower()
                if item.get("direct_input_policy") != "conditional":
                    errors.append(f"storyboard reference must use conditional policy: {item['platform_slot']}")
                if any(term in role_text for term in (
                    "first frame", "clean first", "last frame", "clean end", "clean_start", "clean_end",
                    "首帧", "尾帧", "第一帧", "末帧",
                )):
                    errors.append(f"storyboard reference cannot be a literal clean frame: {item['platform_slot']}")
                if not item.get("anti_misread"):
                    errors.append(f"storyboard reference needs an anti-misread clause: {item['platform_slot']}")
                if selected.get("reference_modes", {}).get("storyboard_reference") not in {
                    "conditional_with_explicit_role_binding", "conditional_inferred_from_omni_reference"
                }:
                    errors.append(f"selected provider surface does not support conditional storyboard reference: {item['platform_slot']}")
            if selected.get("model_key") == "seedance":
                reference_modes = selected.get("reference_modes", {})
                for media_label, field_name in (
                    ("Image", "maximum_image_references"),
                    ("Video", "maximum_video_references"),
                    ("Audio", "maximum_audio_references"),
                ):
                    limit = reference_modes.get(field_name)
                    count = sum(
                        str(item.get("platform_slot", "")).startswith(f"@{media_label} ")
                        for item in attached
                    )
                    if isinstance(limit, int) and count > limit:
                        errors.append(
                            f"{media_label.lower()} reference count is unsupported by capability card: {count} > {limit}"
                        )
            duration_contract = selected.get("duration", {})
            for start, end, unit in unit_times:
                duration = end - start
                kind = duration_contract.get("kind")
                if kind == "discrete" and duration not in [float(value) for value in duration_contract.get("supported_values_sec", [])]:
                    errors.append(f"generation unit duration is unsupported by capability card: {unit['unit_id']}")
                elif kind == "range":
                    minimum = float(duration_contract.get("minimum_sec", 0))
                    maximum = float(duration_contract.get("maximum_sec", 0))
                    if duration < minimum - 0.001 or duration > maximum + 0.001:
                        errors.append(f"generation unit duration is unsupported by capability card: {unit['unit_id']}")
                elif kind == "upper_bound":
                    maximum = float(duration_contract.get("maximum_sec", 0))
                    if duration > maximum + 0.001:
                        errors.append(f"generation unit duration is unsupported by capability card: {unit['unit_id']}")
                elif kind == "version_scoped":
                    supported_range = duration_contract.get("researched_range_sec", [])
                    if len(supported_range) == 2 and not (
                        float(supported_range[0]) - 0.001 <= duration <= float(supported_range[1]) + 0.001
                    ):
                        errors.append(f"generation unit duration is unsupported by capability card: {unit['unit_id']}")
                elif kind == "unverified":
                    errors.append(f"generation unit duration is unverified for the selected provider surface: {unit['unit_id']}")

            route = payload["audio_plan"]["generation_route"]
            audio_contract = selected.get("audio_route", {})
            if route == "unresolved":
                errors.append("audio generation route must be resolved before compilation")
            elif route == "native" and audio_contract.get("native_audio_supported") is not True:
                errors.append("native audio is not verified for the resolved capability card")
            elif route == "reference_audio" and audio_contract.get("audio_reference_supported") is not True:
                errors.append("audio reference is not supported by the resolved capability card")
    except Exception as exc:  # fail closed when the durable registry cannot be read
        errors.append(f"capability registry could not be resolved: {exc}")
    return errors


def validate_prompt_ir(
    payload: dict[str, Any], *, verify_project_files: bool = True, project_root: Path = ROOT
) -> None:
    errors = semantic_errors(payload, verify_project_files=verify_project_files, project_root=project_root)
    if errors:
        raise PromptContractError("; ".join(errors))


def structural_score(payload: dict[str, Any]) -> int:
    """Score ten independently observable contract dimensions; never trust authored QA scores."""
    checks = [
        bool(payload.get("references")),
        all(entity.get("reference_asset_ids") for entity in payload.get("entities", [])),
        all(shot.get("entity_actions") for shot in payload.get("shot_blocks", [])),
        all(shot.get("environment_action") for shot in payload.get("shot_blocks", [])),
        all(shot.get("camera") for shot in payload.get("shot_blocks", [])),
        all("audio_cues" in shot for shot in payload.get("shot_blocks", [])),
        bool(payload.get("audio_plan", {}).get("generation_route")),
        bool(payload.get("generation_plan", {}).get("units")),
        all(layer in payload.get("render_look", {}) for layer in ("lighting", "optics", "atmosphere", "grade")),
        not semantic_errors(payload, verify_project_files=False),
    ]
    return sum(10 for passed in checks if passed)


def compile_prompt(
    payload: dict[str, Any], *, verify_project_files: bool = True, project_root: Path = ROOT
) -> CompileResult:
    validate_prompt_ir(payload, verify_project_files=verify_project_files, project_root=project_root)
    adapter_name = payload["generation_plan"]["selected_adapter"]
    attached = ordered_attached_references(payload)
    assets_by_id = {item["asset_id"]: item for item in payload["intake"]["supplied_assets"]}
    units = sorted(
        payload["generation_plan"]["units"],
        key=lambda item: _time_value(item["time_start"]),
    )
    try:
        adapter = get_adapter(adapter_name)
        prompt = adapter.compile_full(payload)
        unit_prompts = [adapter.compile_unit(payload, unit) for unit in units]
        postproduction_audio = adapter.postproduction_audio(payload)
        unit_postproduction_audio = [
            adapter.unit_postproduction_audio(payload, unit)
            for unit in units
        ]
    except AdapterContractError as exc:
        raise PromptContractError(str(exc)) from exc

    return CompileResult(
        prompt=prompt,
        unit_prompts=unit_prompts,
        adapter=adapter_name,
        attached_slots=[item["platform_slot"] for item in attached],
        upload_mapping=[
            {
                "upload_order": item.get("upload_order"),
                "platform_slot": item["platform_slot"],
                "asset_id": item["asset_id"],
                "role": item["role"],
                "source_locator": assets_by_id[item["asset_id"]]["source_locator"],
            }
            for item in attached
        ],
        postproduction_audio=postproduction_audio,
        unit_postproduction_audio=unit_postproduction_audio,
        structural_score=structural_score(payload),
    )


def load_prompt_ir(path: Path) -> dict[str, Any]:
    try:
        raw = read_relative_regular_file_once(
            path.parent.resolve(strict=True),
            path.name,
            max_bytes=MAX_PROMPT_IR_BYTES,
            label="Prompt IR",
        )
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise PromptContractError(f"cannot read Prompt IR {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PromptContractError("Prompt IR root must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and compile DIRcreative Prompt IR without executing media generation.")
    parser.add_argument("action", choices=("validate", "compile", "inspect"))
    parser.add_argument("prompt_ir", type=Path)
    parser.add_argument("--skip-project-file-check", action="store_true")
    parser.add_argument("--unit-index", type=int, help="One-based generation-unit index for multi-unit compilation.")
    args = parser.parse_args()
    path = args.prompt_ir if args.prompt_ir.is_absolute() else ROOT / args.prompt_ir
    try:
        payload = load_prompt_ir(path)
        if args.action == "validate":
            validate_prompt_ir(payload, verify_project_files=not args.skip_project_file_check, project_root=path.parent)
            print(json.dumps({"status": "PASS", "prompt_ir": str(path)}, ensure_ascii=False, indent=2))
        else:
            result = compile_prompt(payload, verify_project_files=not args.skip_project_file_check, project_root=path.parent)
            if args.action == "compile":
                if len(result.unit_prompts) > 1 and args.unit_index is None:
                    raise PromptContractError("multi-unit Prompt IR requires --unit-index; compile and paste one generation unit at a time")
                if args.unit_index is not None:
                    if args.unit_index < 1 or args.unit_index > len(result.unit_prompts):
                        raise PromptContractError("--unit-index is outside the generation plan")
                    print(result.unit_prompts[args.unit_index - 1], end="")
                else:
                    print(result.prompt, end="")
            else:
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    except PromptContractError as exc:
        print(json.dumps({"status": "FAIL", "prompt_ir": str(path), "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
