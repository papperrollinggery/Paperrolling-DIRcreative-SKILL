#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "skills/dircreative/runtime/visual-asset-plan.schema.json"
CASES_PATH = ROOT / "tests/fixtures/visual-asset-plan/cases.json"
TVC_INVENTORY_PATH = ROOT / "tests/fixtures/visual-asset-plan/tvc-60s-inventory.json"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PLACEHOLDER_RE = re.compile(
    r"(?:\bTB" r"D\b|\bTO" r"DO\b|\bFIX" r"ME\b|待" r"定|占" r"位|place" r"holder)",
    re.IGNORECASE,
)
MIN_RASTER_WIDTH = 640
MIN_RASTER_HEIGHT = 360
MIN_RASTER_BYTES = 4096
RASTER_HEADER_SCAN_BYTES = 4 * 1024 * 1024

ROLES = {
    "character_identity_reference",
    "product_identity_board",
    "prop_continuity_board",
    "scene_geography_camera_fov_reference",
    "lighting_material_style_board",
    "storyboard_frame",
    "professional_storyboard_motion_map",
    "clean_first_frame",
    "clean_key_frame",
    "clean_end_frame",
}
PLANNING_ROLES = {
    "character_identity_reference",
    "product_identity_board",
    "prop_continuity_board",
    "scene_geography_camera_fov_reference",
    "lighting_material_style_board",
    "storyboard_frame",
    "professional_storyboard_motion_map",
}
DIRECT_ROLES = {"clean_first_frame", "clean_key_frame", "clean_end_frame"}
GENERATED_STATUSES = {"generated_candidate", "user_locked", "reused_locked"}
ACCEPTED_STATUSES = {"user_locked", "reused_locked"}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def safe_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    if not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in value):
        return []
    return value


def safe_coverage_ids(asset: dict[str, Any], field: str) -> list[str]:
    coverage = asset.get("coverage")
    if not isinstance(coverage, dict):
        return []
    return safe_id_list(coverage.get(field))


def validate_id_list(value: Any, label: str, errors: list[str], *, nonempty: bool = False) -> list[str]:
    values = safe_id_list(value)
    if not isinstance(value, list) or len(values) != len(value):
        errors.append(f"invalid_id_list:{label}")
        return []
    if nonempty and not values:
        errors.append(f"empty_id_list:{label}")
    for duplicate in duplicate_values(values):
        errors.append(f"duplicate_id:{label}:{duplicate}")
    return values


def resolved_generated_file(raw: Any, base_dir: Path) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    try:
        resolved = path.resolve(strict=True)
        return resolved if resolved.is_file() else None
    except OSError:
        return None


def raster_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            data = handle.read(RASTER_HEADER_SCAN_BYTES)
    except OSError:
        return None
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        flavor = data[12:16]
        if flavor == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
        if flavor == b"VP8L" and data[20:21] == b"/":
            bits = int.from_bytes(data[21:25], "little")
            return 1 + (bits & 0x3FFF), 1 + ((bits >> 14) & 0x3FFF)
        if flavor == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            return width, height
    if len(data) >= 4 and data[:2] == b"\xff\xd8":
        index = 2
        sof_markers = {
            0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
        }
        while index + 4 <= len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            while index < len(data) and data[index] == 0xFF:
                index += 1
            if index >= len(data):
                break
            marker = data[index]
            index += 1
            if marker in {0x01, *range(0xD0, 0xDA)}:
                continue
            if index + 2 > len(data):
                break
            segment_length = int.from_bytes(data[index:index + 2], "big")
            if segment_length < 2 or index + segment_length > len(data):
                break
            if marker in sof_markers and segment_length >= 7:
                height = int.from_bytes(data[index + 3:index + 5], "big")
                width = int.from_bytes(data[index + 5:index + 7], "big")
                return width, height
            index += segment_length
    return None


def file_is_real(raw: Any, base_dir: Path) -> bool:
    path = resolved_generated_file(raw, base_dir)
    if path is None:
        return False
    try:
        size = path.stat().st_size
        if size < MIN_RASTER_BYTES:
            return False
        with path.open("rb") as handle:
            prefix = handle.read(12)
            handle.seek(-12, 2)
            suffix = handle.read(12)
    except OSError:
        return False
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        if suffix != b"\x00\x00\x00\x00IEND\xaeB`\x82":
            return False
    elif prefix.startswith(b"\xff\xd8"):
        if not suffix.endswith(b"\xff\xd9"):
            return False
    elif prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        if int.from_bytes(prefix[4:8], "little") + 8 != size:
            return False
    else:
        return False
    dimensions = raster_dimensions(path)
    return bool(
        dimensions
        and dimensions[0] >= MIN_RASTER_WIDTH
        and dimensions[1] >= MIN_RASTER_HEIGHT
    )


def test_png_bytes(width: int = MIN_RASTER_WIDTH, height: int = MIN_RASTER_HEIGHT) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    rows = []
    for y in range(height):
        pixel = bytes((y % 251, (y * 3) % 253, (y * 7) % 255))
        rows.append(b"\x00" + pixel * width)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), level=1))
        + chunk(b"IEND", b"")
    )


def add_coverage_error(errors: list[str], prefix: str, missing: list[str]) -> None:
    if missing:
        errors.append(f"{prefix}:{','.join(missing)}")


def empty_coverage() -> dict[str, list[str]]:
    return {
        "scene_ids": [],
        "character_ids": [],
        "product_ids": [],
        "prop_ids": [],
        "shot_ids": [],
        "generation_unit_ids": [],
    }


def planned_asset(
    asset_id: str,
    role: str,
    purpose: str,
    *,
    coverage: dict[str, list[str]],
    inherits_from: list[str],
    action: str = "generate",
    planning_only: bool = True,
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "role": role,
        "required": True,
        "action": action,
        "purpose": purpose,
        "coverage": coverage,
        "inherits_from": inherits_from,
        "planning_only": planning_only,
        "direct_video_input": not planning_only,
        "status": "planned",
        "qa_status": "not_run",
        "generated_file": "",
    }


def derive_plan(inventory: dict[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "project_id",
        "scope",
        "duration_seconds",
        "delivery_profile",
        "characters",
        "products",
        "props",
        "scenes",
        "shots",
        "rhythm_point_ids",
        "style_reference_required",
        "generation_units",
    }
    if set(inventory) != required or inventory.get("schema_version") != "1.0":
        raise ValueError("visual asset inventory field set or version is invalid")
    characters = inventory.get("characters")
    products = inventory.get("products")
    props = inventory.get("props")
    scenes = inventory.get("scenes")
    shots = inventory.get("shots")
    units = inventory.get("generation_units")
    for label, values in (
        ("characters", characters),
        ("products", products),
        ("props", props),
        ("scenes", scenes),
        ("shots", shots),
        ("generation_units", units),
    ):
        if not isinstance(values, list):
            raise ValueError(f"inventory {label} must be a list")

    def entity_map(values: list[Any], label: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in values:
            if not isinstance(item, dict) or set(item) != {"id", "purpose"}:
                raise ValueError(f"inventory {label} item is invalid")
            entity_id = item.get("id")
            purpose = item.get("purpose")
            if (
                not isinstance(entity_id, str)
                or not ID_RE.fullmatch(entity_id)
                or entity_id in result
                or not isinstance(purpose, str)
                or len(purpose.strip()) < 12
            ):
                raise ValueError(f"inventory {label} identity or purpose is invalid")
            result[entity_id] = item
        return result

    character_map = entity_map(characters, "characters")
    product_map = entity_map(products, "products")
    prop_map = entity_map(props, "props")
    scene_map = entity_map(scenes, "scenes")
    unit_map: dict[str, dict[str, Any]] = {}
    output_units: list[dict[str, Any]] = []
    for unit in units:
        expected = {
            "unit_id", "shot_ids", "direct_input_required",
            "direct_input_not_required_reason", "direct_input_role",
        }
        if not isinstance(unit, dict) or set(unit) != expected:
            raise ValueError("inventory generation unit is invalid")
        unit_id = unit.get("unit_id")
        role = unit.get("direct_input_role")
        if (
            not isinstance(unit_id, str)
            or not ID_RE.fullmatch(unit_id)
            or unit_id in unit_map
            or role not in DIRECT_ROLES
        ):
            raise ValueError("inventory generation unit identity or role is invalid")
        unit_shot_ids = unit.get("shot_ids")
        if (
            not isinstance(unit_shot_ids, list)
            or not unit_shot_ids
            or not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in unit_shot_ids)
            or duplicate_values(unit_shot_ids)
        ):
            raise ValueError(f"inventory generation unit {unit_id} shot_ids are invalid")
        direct_required = unit.get("direct_input_required")
        not_required_reason = unit.get("direct_input_not_required_reason")
        if not isinstance(direct_required, bool) or not isinstance(not_required_reason, str):
            raise ValueError(f"inventory generation unit {unit_id} direct-input policy is invalid")
        if direct_required and not_required_reason.strip():
            raise ValueError(f"inventory generation unit {unit_id} has a contradictory direct-input reason")
        if not direct_required and len(not_required_reason.strip()) < 12:
            raise ValueError(f"inventory generation unit {unit_id} needs a direct-input exemption reason")
        unit_map[unit_id] = unit
        output_units.append({key: unit[key] for key in (
            "unit_id", "shot_ids", "direct_input_required", "direct_input_not_required_reason"
        )})

    shot_map: dict[str, dict[str, Any]] = {}
    shot_ids: list[str] = []
    for shot in shots:
        expected = {
            "shot_id", "scene_id", "character_ids", "product_ids", "prop_ids",
            "generation_unit_id", "narrative_purpose",
        }
        if not isinstance(shot, dict) or set(shot) != expected:
            raise ValueError("inventory shot item is invalid")
        shot_id = shot.get("shot_id")
        if not isinstance(shot_id, str) or not ID_RE.fullmatch(shot_id) or shot_id in shot_map:
            raise ValueError("inventory shot id is invalid or duplicated")
        if shot.get("scene_id") not in scene_map or shot.get("generation_unit_id") not in unit_map:
            raise ValueError(f"inventory shot {shot_id} has unknown scene or generation unit")
        for field, known in (
            ("character_ids", character_map),
            ("product_ids", product_map),
            ("prop_ids", prop_map),
        ):
            values = shot.get(field)
            if not isinstance(values, list) or set(values) - set(known):
                raise ValueError(f"inventory shot {shot_id} has invalid {field}")
        purpose = shot.get("narrative_purpose")
        if not isinstance(purpose, str) or len(purpose.strip()) < 12:
            raise ValueError(f"inventory shot {shot_id} has no usable narrative purpose")
        shot_map[shot_id] = shot
        shot_ids.append(shot_id)

    declared_unit_for_shot: dict[str, str] = {}
    for unit_id, unit in unit_map.items():
        for shot_id in unit["shot_ids"]:
            if shot_id not in shot_map:
                raise ValueError(f"inventory generation unit {unit_id} references unknown shot {shot_id}")
            if shot_id in declared_unit_for_shot:
                raise ValueError(
                    f"inventory shot {shot_id} appears in multiple generation units: "
                    f"{declared_unit_for_shot[shot_id]},{unit_id}"
                )
            declared_unit_for_shot[shot_id] = unit_id
            if shot_map[shot_id]["generation_unit_id"] != unit_id:
                raise ValueError(
                    f"inventory shot {shot_id} generation-unit membership disagrees with its shot record"
                )
    missing_unit_membership = sorted(set(shot_map) - set(declared_unit_for_shot))
    if missing_unit_membership:
        raise ValueError(
            "inventory shots missing generation-unit membership: " + ",".join(missing_unit_membership)
        )
    for unit_id, unit in unit_map.items():
        scene_ids = {shot_map[shot_id]["scene_id"] for shot_id in unit["shot_ids"]}
        if len(scene_ids) != 1:
            raise ValueError(
                f"inventory generation unit {unit_id} crosses scene anchors: "
                + ",".join(sorted(scene_ids))
            )

    assets: list[dict[str, Any]] = []
    character_asset_ids: dict[str, str] = {}
    product_asset_ids: dict[str, str] = {}
    prop_asset_ids: dict[str, str] = {}
    scene_asset_ids: dict[str, str] = {}
    for entity_id, item in character_map.items():
        asset_id = f"identity-character-{entity_id}"
        character_asset_ids[entity_id] = asset_id
        coverage = empty_coverage()
        coverage["character_ids"] = [entity_id]
        assets.append(planned_asset(asset_id, "character_identity_reference", item["purpose"], coverage=coverage, inherits_from=[]))
    for entity_id, item in product_map.items():
        asset_id = f"identity-product-{entity_id}"
        product_asset_ids[entity_id] = asset_id
        coverage = empty_coverage()
        coverage["product_ids"] = [entity_id]
        assets.append(planned_asset(asset_id, "product_identity_board", item["purpose"], coverage=coverage, inherits_from=[]))
    for entity_id, item in prop_map.items():
        asset_id = f"continuity-prop-{entity_id}"
        prop_asset_ids[entity_id] = asset_id
        coverage = empty_coverage()
        coverage["prop_ids"] = [entity_id]
        coverage["shot_ids"] = [shot_id for shot_id in shot_ids if entity_id in shot_map[shot_id]["prop_ids"]]
        assets.append(planned_asset(asset_id, "prop_continuity_board", item["purpose"], coverage=coverage, inherits_from=[]))
    for entity_id, item in scene_map.items():
        asset_id = f"scene-{entity_id}"
        scene_asset_ids[entity_id] = asset_id
        coverage = empty_coverage()
        coverage["scene_ids"] = [entity_id]
        coverage["shot_ids"] = [shot_id for shot_id in shot_ids if shot_map[shot_id]["scene_id"] == entity_id]
        assets.append(planned_asset(asset_id, "scene_geography_camera_fov_reference", item["purpose"], coverage=coverage, inherits_from=[]))

    style_asset_id = "look-whole-film"
    if inventory.get("style_reference_required") is True:
        coverage = empty_coverage()
        coverage["scene_ids"] = list(scene_map)
        coverage["shot_ids"] = shot_ids
        assets.append(
            planned_asset(
                style_asset_id,
                "lighting_material_style_board",
                "Lock the whole-film lighting, material, atmosphere, optics, and grade transition without duplicating scene geography.",
                coverage=coverage,
                inherits_from=list(scene_asset_ids.values()),
            )
        )

    storyboard_asset_ids: list[str] = []
    for shot_id in shot_ids:
        shot = shot_map[shot_id]
        asset_id = f"storyboard-frame-{shot_id}"
        storyboard_asset_ids.append(asset_id)
        coverage = empty_coverage()
        coverage["scene_ids"] = [shot["scene_id"]]
        coverage["character_ids"] = list(shot["character_ids"])
        coverage["product_ids"] = list(shot["product_ids"])
        coverage["prop_ids"] = list(shot["prop_ids"])
        coverage["shot_ids"] = [shot_id]
        coverage["generation_unit_ids"] = [shot["generation_unit_id"]]
        inherits = [scene_asset_ids[shot["scene_id"]]]
        inherits.extend(character_asset_ids[item] for item in shot["character_ids"])
        inherits.extend(product_asset_ids[item] for item in shot["product_ids"])
        inherits.extend(prop_asset_ids[item] for item in shot["prop_ids"])
        if inventory.get("style_reference_required") is True:
            inherits.append(style_asset_id)
        assets.append(
            planned_asset(
                asset_id,
                "storyboard_frame",
                f"Visualize {shot_id}: {shot['narrative_purpose']}",
                coverage=coverage,
                inherits_from=inherits,
            )
        )

    for page_index in range(0, len(shot_ids), 6):
        page_shots = shot_ids[page_index : page_index + 6]
        page_number = page_index // 6 + 1
        coverage = empty_coverage()
        coverage["scene_ids"] = list(dict.fromkeys(shot_map[item]["scene_id"] for item in page_shots))
        coverage["character_ids"] = list(dict.fromkeys(value for item in page_shots for value in shot_map[item]["character_ids"]))
        coverage["product_ids"] = list(dict.fromkeys(value for item in page_shots for value in shot_map[item]["product_ids"]))
        coverage["prop_ids"] = list(dict.fromkeys(value for item in page_shots for value in shot_map[item]["prop_ids"]))
        coverage["shot_ids"] = page_shots
        coverage["generation_unit_ids"] = list(dict.fromkeys(shot_map[item]["generation_unit_id"] for item in page_shots))
        assets.append(
            planned_asset(
                f"director-storyboard-page-{page_number:02d}",
                "professional_storyboard_motion_map",
                f"Assemble director storyboard page {page_number} with full shot-card, blocking, continuity, sound, edit, and model-risk fields.",
                coverage=coverage,
                inherits_from=[f"storyboard-frame-{item}" for item in page_shots],
                action="assemble",
            )
        )

    for unit_id, unit in unit_map.items():
        if unit["direct_input_required"] is not True:
            continue
        role = unit["direct_input_role"]
        unit_shots = unit["shot_ids"]
        selected_shot = unit_shots[0] if role == "clean_first_frame" else unit_shots[-1] if role == "clean_end_frame" else unit_shots[len(unit_shots) // 2]
        shot = shot_map[selected_shot]
        coverage = empty_coverage()
        coverage["scene_ids"] = [shot["scene_id"]]
        coverage["character_ids"] = list(shot["character_ids"])
        coverage["product_ids"] = list(shot["product_ids"])
        coverage["prop_ids"] = list(shot["prop_ids"])
        coverage["shot_ids"] = [selected_shot]
        coverage["generation_unit_ids"] = [unit_id]
        assets.append(
            planned_asset(
                f"clean-input-{unit_id}",
                role,
                f"Provide the text-free model input for generation unit {unit_id} from approved shot {selected_shot}.",
                coverage=coverage,
                inherits_from=[f"storyboard-frame-{selected_shot}"],
                action="derive",
                planning_only=False,
            )
        )

    return {
        "schema_version": "1.0",
        "project_id": inventory["project_id"],
        "scope": inventory["scope"],
        "duration_seconds": inventory["duration_seconds"],
        "delivery_profile": inventory["delivery_profile"],
        "scene_ids": list(scene_map),
        "character_ids": list(character_map),
        "product_ids": list(product_map),
        "prop_ids": list(prop_map),
        "shot_ids": shot_ids,
        "rhythm_point_ids": inventory["rhythm_point_ids"],
        "style_reference_required": inventory["style_reference_required"],
        "generation_units": output_units,
        "assets": assets,
        "completion_claim": "plan_complete",
    }


def validate_delivery_profile(profile: Any, completion_claim: Any, errors: list[str]) -> None:
    if not isinstance(profile, dict):
        errors.append("delivery_profile_missing")
        return
    required = {
        "medium",
        "aspect_ratio",
        "raster_width",
        "raster_height",
        "frame_rate_fps",
        "audio_sample_rate_hz",
        "action_safe_percent",
        "title_safe_percent",
        "brand_endframe_min_seconds",
        "target_master_spec_status",
    }
    if set(profile) != required:
        errors.append("delivery_profile_field_set_mismatch")
        return
    medium = profile.get("medium")
    if medium not in {"broadcast_tvc", "cinema", "web", "social", "other"}:
        errors.append("delivery_profile_medium_invalid")
    aspect_ratio = profile.get("aspect_ratio")
    ratio_match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?):([0-9]+(?:\.[0-9]+)?)", str(aspect_ratio))
    if ratio_match is None or float(ratio_match.group(1)) <= 0 or float(ratio_match.group(2)) <= 0:
        errors.append("delivery_profile_aspect_ratio_invalid")
    width = profile.get("raster_width")
    height = profile.get("raster_height")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or not isinstance(height, int)
        or isinstance(height, bool)
        or width <= 0
        or height <= 0
    ):
        errors.append("delivery_profile_raster_invalid")
    frame_rate = profile.get("frame_rate_fps")
    if not isinstance(frame_rate, (int, float)) or isinstance(frame_rate, bool) or frame_rate <= 0:
        errors.append("delivery_profile_frame_rate_invalid")
    audio_rate = profile.get("audio_sample_rate_hz")
    if not isinstance(audio_rate, int) or isinstance(audio_rate, bool) or audio_rate <= 0:
        errors.append("delivery_profile_audio_rate_invalid")
    action_safe = profile.get("action_safe_percent")
    title_safe = profile.get("title_safe_percent")
    if (
        not isinstance(action_safe, (int, float))
        or isinstance(action_safe, bool)
        or not isinstance(title_safe, (int, float))
        or isinstance(title_safe, bool)
        or not 0 < title_safe <= action_safe <= 100
    ):
        errors.append("delivery_profile_safe_area_invalid")
    endframe = profile.get("brand_endframe_min_seconds")
    if not isinstance(endframe, (int, float)) or isinstance(endframe, bool) or endframe < 0:
        errors.append("delivery_profile_brand_endframe_invalid")
    if profile.get("target_master_spec_status") not in {
        "fixture_baseline",
        "requires_target_spec",
        "locked_target",
    }:
        errors.append("delivery_profile_target_status_invalid")
    if profile.get("medium") == "broadcast_tvc":
        if profile.get("aspect_ratio") != "16:9":
            errors.append("broadcast_tvc_requires_16_9")
        if not isinstance(width, int) or not isinstance(height, int) or width < 1920 or height < 1080:
            errors.append("broadcast_tvc_raster_below_1080")
        elif abs(width / height - 16 / 9) > 0.01:
            errors.append("broadcast_tvc_raster_ratio_mismatch")
        if profile.get("audio_sample_rate_hz") != 48000:
            errors.append("broadcast_tvc_audio_must_be_48khz")
        if not isinstance(action_safe, (int, float)) or not isinstance(title_safe, (int, float)):
            errors.append("broadcast_tvc_safe_area_invalid")
        elif not 0 < title_safe <= action_safe <= 100:
            errors.append("broadcast_tvc_safe_area_invalid")
        if not isinstance(endframe, (int, float)) or endframe <= 0:
            errors.append("broadcast_tvc_brand_endframe_missing")
    if completion_claim == "accepted" and profile.get("target_master_spec_status") != "locked_target":
        errors.append("accepted_tvc_requires_locked_target_master_spec")


def validate_plan(payload: Any, *, base_dir: Path | None = None) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["plan_must_be_object"], {}
    base_dir = base_dir or ROOT
    schema = load_json(SCHEMA_PATH)
    required_fields = set(schema.get("required", []))
    if set(payload) != required_fields:
        errors.append("plan_field_set_mismatch")

    if payload.get("schema_version") != "1.0":
        errors.append("schema_version_invalid")
    project_id = payload.get("project_id")
    if not isinstance(project_id, str) or not ID_RE.fullmatch(project_id):
        errors.append("project_id_invalid")
    scope = payload.get("scope")
    if scope not in {"whole_film", "sequence", "representative_sample"}:
        errors.append("scope_invalid")
    duration = payload.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        errors.append("duration_invalid")
    completion_claim = payload.get("completion_claim")
    if completion_claim not in {"none", "plan_complete", "sample_complete", "generation_complete", "accepted"}:
        errors.append("completion_claim_invalid")
    validate_delivery_profile(payload.get("delivery_profile"), completion_claim, errors)

    scene_ids = validate_id_list(payload.get("scene_ids"), "scene_ids", errors, nonempty=scope != "representative_sample")
    character_ids = validate_id_list(payload.get("character_ids"), "character_ids", errors)
    product_ids = validate_id_list(payload.get("product_ids"), "product_ids", errors)
    prop_ids = validate_id_list(payload.get("prop_ids"), "prop_ids", errors)
    shot_ids = validate_id_list(payload.get("shot_ids"), "shot_ids", errors, nonempty=True)
    rhythm_point_ids = validate_id_list(payload.get("rhythm_point_ids"), "rhythm_point_ids", errors, nonempty=True)
    if not isinstance(payload.get("style_reference_required"), bool):
        errors.append("style_reference_required_invalid")
    if len(rhythm_point_ids) < len(shot_ids):
        errors.append("rhythm_points_fewer_than_shots")

    generation_units = payload.get("generation_units")
    if not isinstance(generation_units, list) or not generation_units:
        errors.append("generation_units_missing")
        generation_units = []
    unit_ids: list[str] = []
    unit_shots: dict[str, set[str]] = {}
    unit_shot_coverage: set[str] = set()
    unit_membership_counts = {shot_id: 0 for shot_id in shot_ids}
    direct_required_units: set[str] = set()
    for index, unit in enumerate(generation_units):
        if not isinstance(unit, dict) or set(unit) != {
            "unit_id", "shot_ids", "direct_input_required", "direct_input_not_required_reason"
        }:
            errors.append(f"generation_unit_invalid:{index}")
            continue
        unit_id = unit.get("unit_id")
        if not isinstance(unit_id, str) or not ID_RE.fullmatch(unit_id):
            errors.append(f"generation_unit_id_invalid:{index}")
            continue
        unit_ids.append(unit_id)
        covered = validate_id_list(unit.get("shot_ids"), f"generation_units[{unit_id}].shot_ids", errors, nonempty=True)
        unit_shots[unit_id] = set(covered)
        unknown = sorted(set(covered) - set(shot_ids))
        add_coverage_error(errors, f"generation_unit_unknown_shots:{unit_id}", unknown)
        for shot_id in covered:
            if shot_id in unit_membership_counts:
                unit_membership_counts[shot_id] += 1
        unit_shot_coverage.update(covered)
        direct_required = unit.get("direct_input_required")
        reason = unit.get("direct_input_not_required_reason")
        if not isinstance(direct_required, bool) or not isinstance(reason, str):
            errors.append(f"generation_unit_direct_input_invalid:{unit_id}")
        elif direct_required:
            direct_required_units.add(unit_id)
            if reason.strip():
                errors.append(f"generation_unit_required_has_not_required_reason:{unit_id}")
        elif len(reason.strip()) < 12:
            errors.append(f"generation_unit_not_required_reason_missing:{unit_id}")
    for duplicate in duplicate_values(unit_ids):
        errors.append(f"duplicate_generation_unit:{duplicate}")
    add_coverage_error(errors, "generation_unit_shot_coverage_missing", sorted(set(shot_ids) - unit_shot_coverage))
    for shot_id, count in unit_membership_counts.items():
        if count != 1:
            errors.append(f"generation_unit_shot_membership_invalid:{shot_id}:{count}")

    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("assets_missing")
        assets = []
    asset_ids: list[str] = []
    role_assets: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    storyboard_scene_by_shot: dict[str, str] = {}
    clean_assets: list[dict[str, Any]] = []
    valid_coverage = {
        "scene_ids": set(scene_ids),
        "character_ids": set(character_ids),
        "product_ids": set(product_ids),
        "prop_ids": set(prop_ids),
        "shot_ids": set(shot_ids),
        "generation_unit_ids": set(unit_ids),
    }
    asset_required_fields = {
        "asset_id", "role", "required", "action", "purpose", "coverage", "inherits_from",
        "planning_only", "direct_video_input", "status", "qa_status", "generated_file",
    }
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict) or set(asset) != asset_required_fields:
            errors.append(f"asset_field_set_mismatch:{index}")
            continue
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not ID_RE.fullmatch(asset_id):
            errors.append(f"asset_id_invalid:{index}")
            continue
        asset_ids.append(asset_id)
        role = asset.get("role")
        if role not in ROLES:
            errors.append(f"asset_role_invalid:{asset_id}")
            continue
        role_assets[role].append(asset)
        purpose = asset.get("purpose")
        if not isinstance(purpose, str) or len(purpose.strip()) < 12 or PLACEHOLDER_RE.search(purpose):
            errors.append(f"asset_purpose_invalid:{asset_id}")
        if not isinstance(asset.get("required"), bool):
            errors.append(f"asset_required_invalid:{asset_id}")
        if asset.get("action") not in {"reuse", "derive", "generate", "assemble"}:
            errors.append(f"asset_action_invalid:{asset_id}")
        if asset.get("status") not in {"planned", "prompt_ready", "generated_candidate", "user_locked", "reused_locked", "rejected"}:
            errors.append(f"asset_status_invalid:{asset_id}")
        if asset.get("qa_status") not in {"not_run", "pass", "fail"}:
            errors.append(f"asset_qa_status_invalid:{asset_id}")
        if asset.get("required") is True and asset.get("status") == "rejected":
            errors.append(f"required_asset_rejected:{asset_id}")
        if role in PLANNING_ROLES and (asset.get("planning_only") is not True or asset.get("direct_video_input") is not False):
            errors.append(f"planning_asset_direct_input_invalid:{asset_id}")
        if role in DIRECT_ROLES and (asset.get("planning_only") is not False or asset.get("direct_video_input") is not True):
            errors.append(f"clean_input_policy_invalid:{asset_id}")

        coverage = asset.get("coverage")
        if not isinstance(coverage, dict) or set(coverage) != set(valid_coverage):
            errors.append(f"asset_coverage_shape_invalid:{asset_id}")
            continue
        normalized_coverage: dict[str, list[str]] = {}
        for key, allowed in valid_coverage.items():
            values = validate_id_list(coverage.get(key), f"assets[{asset_id}].coverage.{key}", errors)
            normalized_coverage[key] = values
            unknown = sorted(set(values) - allowed)
            add_coverage_error(errors, f"asset_coverage_unknown:{asset_id}:{key}", unknown)
        inherits = validate_id_list(asset.get("inherits_from"), f"assets[{asset_id}].inherits_from", errors)
        if asset_id in inherits:
            errors.append(f"asset_self_inheritance:{asset_id}")

        if role == "character_identity_reference" and len(normalized_coverage["character_ids"]) != 1:
            errors.append(f"character_identity_scope_invalid:{asset_id}")
        if role == "product_identity_board" and len(normalized_coverage["product_ids"]) != 1:
            errors.append(f"product_identity_scope_invalid:{asset_id}")
        if role == "prop_continuity_board" and len(normalized_coverage["prop_ids"]) != 1:
            errors.append(f"prop_continuity_scope_invalid:{asset_id}")
        if role == "scene_geography_camera_fov_reference" and len(normalized_coverage["scene_ids"]) != 1:
            errors.append(f"scene_reference_scope_invalid:{asset_id}")
        if role == "storyboard_frame":
            asset_shots = normalized_coverage["shot_ids"]
            asset_units = normalized_coverage["generation_unit_ids"]
            asset_scenes = normalized_coverage["scene_ids"]
            if len(asset_shots) != 1:
                errors.append(f"storyboard_frame_scope_invalid:{asset_id}")
            if len(asset_scenes) != 1:
                errors.append(f"storyboard_frame_scene_scope_invalid:{asset_id}")
            if len(asset_units) != 1:
                errors.append(f"storyboard_frame_generation_unit_invalid:{asset_id}")
            elif asset_shots and asset_shots[0] not in unit_shots.get(asset_units[0], set()):
                errors.append(f"storyboard_frame_shot_outside_unit:{asset_id}")
            if len(asset_shots) == 1 and len(asset_scenes) == 1:
                storyboard_scene_by_shot[asset_shots[0]] = asset_scenes[0]
        if role == "professional_storyboard_motion_map":
            if asset.get("action") != "assemble":
                errors.append(f"director_storyboard_must_assemble:{asset_id}")
            if not 1 <= len(normalized_coverage["shot_ids"]) <= 6:
                errors.append(f"director_storyboard_page_density_invalid:{asset_id}")
        if role in DIRECT_ROLES:
            clean_assets.append(asset)
            asset_shots = normalized_coverage["shot_ids"]
            asset_units = normalized_coverage["generation_unit_ids"]
            asset_scenes = normalized_coverage["scene_ids"]
            if len(asset_shots) != 1 or len(asset_units) != 1 or len(asset_scenes) != 1:
                errors.append(f"clean_input_scope_invalid:{asset_id}")
            elif asset_shots[0] not in unit_shots.get(asset_units[0], set()):
                errors.append(f"clean_input_shot_outside_unit:{asset_id}")
    for duplicate in duplicate_values(asset_ids):
        errors.append(f"duplicate_asset_id:{duplicate}")
    known_asset_ids = set(asset_ids)
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        for source in safe_id_list(asset.get("inherits_from")):
            if source not in known_asset_ids:
                errors.append(f"asset_inheritance_unknown:{asset.get('asset_id')}:{source}")

    def covered_entities(role: str, field: str) -> set[str]:
        return {
            value
            for asset in role_assets[role]
            if asset.get("required") is True
            for value in safe_coverage_ids(asset, field)
        }

    def coverage_counts(role: str, field: str, ids: list[str]) -> dict[str, int]:
        counts = {value: 0 for value in ids}
        for asset in role_assets[role]:
            if asset.get("required") is not True:
                continue
            for value in safe_coverage_ids(asset, field):
                if value in counts:
                    counts[value] += 1
        return counts

    def require_exact_entity_coverage(role: str, field: str, ids: list[str], prefix: str) -> None:
        for value, count in coverage_counts(role, field, ids).items():
            if count != 1:
                errors.append(f"{prefix}:{value}:{count}")

    add_coverage_error(errors, "character_coverage_missing", sorted(set(character_ids) - covered_entities("character_identity_reference", "character_ids")))
    add_coverage_error(errors, "product_coverage_missing", sorted(set(product_ids) - covered_entities("product_identity_board", "product_ids")))
    add_coverage_error(errors, "prop_coverage_missing", sorted(set(prop_ids) - covered_entities("prop_continuity_board", "prop_ids")))
    add_coverage_error(errors, "scene_coverage_missing", sorted(set(scene_ids) - covered_entities("scene_geography_camera_fov_reference", "scene_ids")))
    require_exact_entity_coverage(
        "character_identity_reference", "character_ids", character_ids,
        "character_identity_coverage_invalid",
    )
    require_exact_entity_coverage(
        "product_identity_board", "product_ids", product_ids,
        "product_identity_coverage_invalid",
    )
    require_exact_entity_coverage(
        "prop_continuity_board", "prop_ids", prop_ids,
        "prop_continuity_coverage_invalid",
    )
    require_exact_entity_coverage(
        "scene_geography_camera_fov_reference", "scene_ids", scene_ids,
        "scene_identity_coverage_invalid",
    )

    storyboard_counts = {shot_id: 0 for shot_id in shot_ids}
    director_counts = {shot_id: 0 for shot_id in shot_ids}
    scene_reference_counts = {shot_id: 0 for shot_id in shot_ids}
    scene_reference_by_shot: dict[str, str] = {}
    for asset in role_assets["scene_geography_camera_fov_reference"]:
        if asset.get("required") is True:
            covered_scenes = safe_coverage_ids(asset, "scene_ids")
            for shot_id in safe_coverage_ids(asset, "shot_ids"):
                if shot_id in scene_reference_counts:
                    scene_reference_counts[shot_id] += 1
                    if len(covered_scenes) == 1:
                        scene_reference_by_shot[shot_id] = covered_scenes[0]
    for asset in role_assets["storyboard_frame"]:
        if asset.get("required") is True:
            for shot_id in safe_coverage_ids(asset, "shot_ids"):
                if shot_id in storyboard_counts:
                    storyboard_counts[shot_id] += 1
    for asset in role_assets["professional_storyboard_motion_map"]:
        if asset.get("required") is True:
            for shot_id in safe_coverage_ids(asset, "shot_ids"):
                if shot_id in director_counts:
                    director_counts[shot_id] += 1
    for shot_id, count in scene_reference_counts.items():
        if count != 1:
            errors.append(f"scene_reference_shot_coverage_invalid:{shot_id}:{count}")
    for shot_id, count in storyboard_counts.items():
        if count != 1:
            errors.append(f"storyboard_frame_coverage_invalid:{shot_id}:{count}")
    for shot_id in shot_ids:
        storyboard_scene = storyboard_scene_by_shot.get(shot_id)
        reference_scene = scene_reference_by_shot.get(shot_id)
        if storyboard_scene and reference_scene and storyboard_scene != reference_scene:
            errors.append(
                f"storyboard_scene_mismatch:{shot_id}:{storyboard_scene}:{reference_scene}"
            )
    missing_director = [shot_id for shot_id, count in director_counts.items() if count == 0]
    duplicate_director = [shot_id for shot_id, count in director_counts.items() if count > 1]
    add_coverage_error(errors, "director_storyboard_coverage_missing", missing_director)
    add_coverage_error(errors, "director_storyboard_coverage_duplicate", duplicate_director)

    if payload.get("style_reference_required") is True and not any(
        asset.get("required") is True for asset in role_assets["lighting_material_style_board"]
    ):
        errors.append("style_reference_required_but_missing")
    required_style_count = sum(
        asset.get("required") is True
        for asset in role_assets["lighting_material_style_board"]
    )
    expected_style_count = 1 if payload.get("style_reference_required") is True else 0
    if required_style_count != expected_style_count:
        errors.append(
            f"style_reference_count_invalid:{required_style_count}:{expected_style_count}"
        )

    for unit_id, covered_shots in unit_shots.items():
        covered_scenes = {
            scene_reference_by_shot[shot_id]
            for shot_id in covered_shots
            if shot_id in scene_reference_by_shot
        }
        if len(covered_scenes) > 1:
            errors.append(
                f"generation_unit_crosses_scene_anchors:{unit_id}:"
                + ",".join(sorted(covered_scenes))
            )

    direct_input_counts = {unit_id: 0 for unit_id in unit_ids}
    for asset in clean_assets:
        if asset.get("required") is not True or asset.get("direct_video_input") is not True:
            continue
        covered_units = safe_coverage_ids(asset, "generation_unit_ids")
        covered_shots = safe_coverage_ids(asset, "shot_ids")
        covered_scenes = safe_coverage_ids(asset, "scene_ids")
        for unit_id in covered_units:
            if unit_id in direct_input_counts:
                direct_input_counts[unit_id] += 1
        if len(covered_shots) == 1 and len(covered_scenes) == 1:
            expected_scene = scene_reference_by_shot.get(covered_shots[0])
            if expected_scene and covered_scenes[0] != expected_scene:
                errors.append(
                    f"clean_input_scene_mismatch:{asset.get('asset_id')}:"
                    f"{covered_scenes[0]}:{expected_scene}"
                )
    for unit_id, count in direct_input_counts.items():
        expected = 1 if unit_id in direct_required_units else 0
        if count != expected:
            errors.append(f"generation_unit_direct_input_count_invalid:{unit_id}:{count}:{expected}")

    if scope == "representative_sample" and completion_claim in {"plan_complete", "generation_complete", "accepted"}:
        errors.append("sample_cannot_claim_whole_film_plan_complete")
    if completion_claim == "sample_complete" and scope != "representative_sample":
        errors.append("sample_complete_requires_sample_scope")

    generated_claim = completion_claim in {"sample_complete", "generation_complete", "accepted"}
    if generated_claim:
        required_statuses = ACCEPTED_STATUSES if completion_claim == "accepted" else GENERATED_STATUSES
        generated_files: dict[tuple[int, int], str] = {}
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("required") is not True:
                continue
            asset_id = asset.get("asset_id", "unknown")
            if asset.get("status") not in required_statuses:
                errors.append(f"required_asset_not_generated:{asset_id}")
            if asset.get("qa_status") != "pass":
                errors.append(f"required_asset_qa_not_passed:{asset_id}")
            generated_path = resolved_generated_file(asset.get("generated_file"), base_dir)
            if generated_path is not None:
                try:
                    stat_result = generated_path.stat()
                except OSError:
                    generated_path = None
                else:
                    identity = (stat_result.st_dev, stat_result.st_ino)
                    previous = generated_files.get(identity)
                    if previous is not None:
                        errors.append(f"required_asset_file_reused:{previous}:{asset_id}")
                    else:
                        generated_files[identity] = str(asset_id)
            if not file_is_real(asset.get("generated_file"), base_dir):
                errors.append(f"required_asset_file_missing:{asset_id}")

    whole_film_complete = (
        scope == "whole_film"
        and completion_claim in {"generation_complete", "accepted"}
        and not errors
    )
    metrics = {
        "scope": scope,
        "duration_seconds": duration,
        "scenes": len(scene_ids),
        "characters": len(character_ids),
        "products": len(product_ids),
        "props": len(prop_ids),
        "shots": len(shot_ids),
        "rhythm_points": len(rhythm_point_ids),
        "generation_units": len(unit_ids),
        "assets": len(asset_ids),
        "character_identity_references": len(role_assets["character_identity_reference"]),
        "product_identity_boards": len(role_assets["product_identity_board"]),
        "prop_continuity_boards": len(role_assets["prop_continuity_board"]),
        "scene_references": len(role_assets["scene_geography_camera_fov_reference"]),
        "style_boards": len(role_assets["lighting_material_style_board"]),
        "storyboard_frames": len(role_assets["storyboard_frame"]),
        "director_storyboard_pages": len(role_assets["professional_storyboard_motion_map"]),
        "clean_video_inputs": sum(len(role_assets[role]) for role in DIRECT_ROLES),
        "completion_claim": completion_claim,
        "whole_film_complete": whole_film_complete,
    }
    return errors, metrics


def apply_mutation(payload: dict[str, Any], mutation: str) -> dict[str, Any]:
    value = copy.deepcopy(payload)
    if mutation == "none":
        return value
    kind, separator, detail = mutation.partition(":")
    if not separator:
        raise ValueError(f"unknown mutation: {mutation}")
    if kind == "remove":
        value["assets"] = [asset for asset in value["assets"] if asset.get("asset_id") != detail]
    elif kind == "scope":
        value["scope"] = detail
    elif kind == "claim":
        value["completion_claim"] = detail
    else:
        raise ValueError(f"unknown mutation: {mutation}")
    return value


def self_test() -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    cases = load_json(CASES_PATH)
    source = ROOT / str(cases.get("source", ""))
    base = load_json(source)
    results: list[dict[str, Any]] = []
    for case in cases.get("cases", []):
        case_id = str(case.get("id"))
        payload = apply_mutation(base, str(case.get("mutation")))
        errors, metrics = validate_plan(payload, base_dir=source.parent)
        expected = case.get("expect")
        expected_error = case.get("expect_error")
        passed = (expected == "pass" and not errors) or (
            isinstance(expected_error, str) and any(error == expected_error for error in errors)
        )
        if not passed:
            failures.append(f"{case_id}: expected {expected or expected_error}, got {errors}")
        results.append({"id": case_id, "passed": passed, "errors": errors, "metrics": metrics})

    schema = load_json(SCHEMA_PATH)
    schema_roles = set(
        schema["properties"]["assets"]["items"]["properties"]["role"]["enum"]
    )
    if schema_roles != ROLES:
        failures.append("schema role enum drifted from validator")

    tvc_inventory = load_json(TVC_INVENTORY_PATH)
    tvc_plan = derive_plan(tvc_inventory)
    tvc_errors, tvc_metrics = validate_plan(tvc_plan, base_dir=TVC_INVENTORY_PATH.parent)
    if tvc_errors:
        failures.append(f"TVC acceptance plan failed validation: {tvc_errors}")
    tvc_checks = {
        "duration_at_least_60": tvc_plan.get("duration_seconds", 0) >= 60,
        "landscape_broadcast_profile": tvc_plan.get("delivery_profile", {}).get("medium") == "broadcast_tvc"
        and tvc_plan.get("delivery_profile", {}).get("aspect_ratio") == "16:9",
        "scenes_at_least_4": len(tvc_plan.get("scene_ids", [])) >= 4,
        "recurring_characters_at_least_2": len(tvc_plan.get("character_ids", [])) >= 2,
        "formal_shots_at_least_24": len(tvc_plan.get("shot_ids", [])) >= 24,
        "rhythm_points_at_least_30": len(tvc_plan.get("rhythm_point_ids", [])) >= 30,
        "generation_units_scene_coherent": all(
            len(
                {
                    shot["scene_id"]
                    for shot in tvc_inventory["shots"]
                    if shot["shot_id"] in unit["shot_ids"]
                }
            )
            == 1
            for unit in tvc_inventory["generation_units"]
        ),
    }
    if not all(tvc_checks.values()):
        failures.append(f"TVC acceptance fixture is too small: {tvc_checks}")
    expected_tvc_asset_counts = {
        "character_identity_references": 2,
        "product_identity_boards": 1,
        "prop_continuity_boards": 2,
        "scene_references": 4,
        "style_boards": 1,
        "storyboard_frames": 24,
        "director_storyboard_pages": 4,
        "clean_video_inputs": 10,
        "assets": 48,
    }
    for key, expected in expected_tvc_asset_counts.items():
        if tvc_metrics.get(key) != expected:
            failures.append(
                f"TVC acceptance asset count drifted for {key}: {tvc_metrics.get(key)} != {expected}"
            )

    mismatched_membership = copy.deepcopy(tvc_inventory)
    mismatched_membership["generation_units"][0]["shot_ids"] = ["S01", "S02"]
    try:
        derive_plan(mismatched_membership)
    except ValueError as exc:
        membership_negative_control = "missing generation-unit membership" in str(exc)
    else:
        membership_negative_control = False
    if not membership_negative_control:
        failures.append("generation-unit membership negative control was accepted")

    cross_scene_unit = copy.deepcopy(tvc_inventory)
    cross_scene_unit["shots"][13]["scene_id"] = "riverside-dawn"
    try:
        derive_plan(cross_scene_unit)
    except ValueError as exc:
        scene_coherence_negative_control = "crosses scene anchors" in str(exc)
    else:
        scene_coherence_negative_control = False
    if not scene_coherence_negative_control:
        failures.append("cross-scene generation-unit negative control was accepted")

    vertical_tvc = copy.deepcopy(tvc_plan)
    vertical_tvc["delivery_profile"]["aspect_ratio"] = "9:16"
    vertical_tvc["delivery_profile"]["raster_width"] = 1080
    vertical_tvc["delivery_profile"]["raster_height"] = 1920
    vertical_errors, _ = validate_plan(vertical_tvc, base_dir=TVC_INVENTORY_PATH.parent)
    vertical_tvc_negative_control = "broadcast_tvc_requires_16_9" in vertical_errors
    if not vertical_tvc_negative_control:
        failures.append("vertical TVC negative control was accepted")

    duplicate_unit_membership = copy.deepcopy(tvc_plan)
    duplicate_unit_membership["generation_units"][0]["shot_ids"].append("S04")
    duplicate_unit_errors, _ = validate_plan(
        duplicate_unit_membership,
        base_dir=TVC_INVENTORY_PATH.parent,
    )
    duplicate_unit_membership_negative_control = (
        "generation_unit_shot_membership_invalid:S04:2" in duplicate_unit_errors
    )
    if not duplicate_unit_membership_negative_control:
        failures.append("duplicate generation-unit membership negative control was accepted")

    cross_scene_plan = copy.deepcopy(tvc_plan)
    cross_scene_plan["generation_units"][0]["shot_ids"].append("S07")
    cross_scene_plan["generation_units"][2]["shot_ids"].remove("S07")
    s07_storyboard = next(
        asset
        for asset in cross_scene_plan["assets"]
        if asset["asset_id"] == "storyboard-frame-S07"
    )
    s07_storyboard["coverage"]["generation_unit_ids"] = ["G01"]
    cross_scene_plan_errors, _ = validate_plan(
        cross_scene_plan,
        base_dir=TVC_INVENTORY_PATH.parent,
    )
    cross_scene_plan_negative_control = any(
        error.startswith("generation_unit_crosses_scene_anchors:G01:")
        for error in cross_scene_plan_errors
    )
    if not cross_scene_plan_negative_control:
        failures.append("hand-authored cross-scene plan negative control was accepted")

    duplicate_direct_input = copy.deepcopy(tvc_plan)
    duplicate_clean = copy.deepcopy(
        next(asset for asset in duplicate_direct_input["assets"] if asset["asset_id"] == "clean-input-G01")
    )
    duplicate_clean["asset_id"] = "clean-input-G01-duplicate"
    duplicate_direct_input["assets"].append(duplicate_clean)
    duplicate_direct_errors, _ = validate_plan(
        duplicate_direct_input,
        base_dir=TVC_INVENTORY_PATH.parent,
    )
    duplicate_direct_input_negative_control = (
        "generation_unit_direct_input_count_invalid:G01:2:1" in duplicate_direct_errors
    )
    if not duplicate_direct_input_negative_control:
        failures.append("duplicate required clean-input negative control was accepted")

    mismatched_storyboard_scene = copy.deepcopy(tvc_plan)
    s01_storyboard = next(
        asset
        for asset in mismatched_storyboard_scene["assets"]
        if asset["asset_id"] == "storyboard-frame-S01"
    )
    s01_storyboard["coverage"]["scene_ids"] = ["station-concourse-rain"]
    storyboard_scene_errors, _ = validate_plan(
        mismatched_storyboard_scene,
        base_dir=TVC_INVENTORY_PATH.parent,
    )
    storyboard_scene_negative_control = (
        "storyboard_scene_mismatch:S01:station-concourse-rain:radio-studio-night"
        in storyboard_scene_errors
    )
    if not storyboard_scene_negative_control:
        failures.append("storyboard scene-anchor mismatch negative control was accepted")

    duplicate_identity = copy.deepcopy(tvc_plan)
    duplicate_character = copy.deepcopy(
        next(
            asset
            for asset in duplicate_identity["assets"]
            if asset["asset_id"] == "identity-character-lin-che"
        )
    )
    duplicate_character["asset_id"] = "identity-character-lin-che-duplicate"
    duplicate_identity["assets"].append(duplicate_character)
    duplicate_identity_errors, _ = validate_plan(
        duplicate_identity,
        base_dir=TVC_INVENTORY_PATH.parent,
    )
    duplicate_identity_negative_control = (
        "character_identity_coverage_invalid:lin-che:2" in duplicate_identity_errors
    )
    if not duplicate_identity_negative_control:
        failures.append("duplicate required character identity negative control was accepted")

    fake_raster_negative_control = False
    reused_file_negative_control = False
    clean_membership_negative_control = False
    scene_shot_negative_control = False
    with tempfile.TemporaryDirectory(prefix="dircreative-visual-asset-plan-") as raw:
        temp_root = Path(raw)
        generated = copy.deepcopy(tvc_plan)
        generated["completion_claim"] = "generation_complete"
        media_bytes = test_png_bytes()
        for asset in generated["assets"]:
            target = temp_root / f"{asset['asset_id']}.png"
            target.write_bytes(media_bytes)
            asset["status"] = "generated_candidate"
            asset["qa_status"] = "pass"
            asset["generated_file"] = target.name
        generated_errors, generated_metrics = validate_plan(generated, base_dir=temp_root)
        if generated_errors or not generated_metrics.get("whole_film_complete"):
            failures.append(f"generated whole-film evidence did not pass: {generated_errors}")

        fake_raster = copy.deepcopy(generated)
        fake_target = temp_root / fake_raster["assets"][0]["generated_file"]
        fake_target.write_bytes(b"\x89PNG\r\n\x1a\nnot-a-real-raster")
        fake_errors, _ = validate_plan(fake_raster, base_dir=temp_root)
        fake_raster_negative_control = any(
            error == f"required_asset_file_missing:{fake_raster['assets'][0]['asset_id']}"
            for error in fake_errors
        )
        if not fake_raster_negative_control:
            failures.append("fake-raster generation-complete evidence was accepted")
        fake_target.write_bytes(media_bytes)

        reused_file = copy.deepcopy(generated)
        reused_file["assets"][1]["generated_file"] = reused_file["assets"][0]["generated_file"]
        reused_errors, _ = validate_plan(reused_file, base_dir=temp_root)
        reused_file_negative_control = any(
            error.startswith("required_asset_file_reused:") for error in reused_errors
        )
        if not reused_file_negative_control:
            failures.append("one raster reused as multiple required assets was accepted")

        wrong_clean_input = copy.deepcopy(generated)
        clean_asset = next(
            asset for asset in wrong_clean_input["assets"] if asset["role"] in DIRECT_ROLES
        )
        clean_asset["coverage"]["shot_ids"] = ["S24"]
        clean_errors, _ = validate_plan(wrong_clean_input, base_dir=temp_root)
        clean_membership_negative_control = any(
            error.startswith("clean_input_shot_outside_unit:") for error in clean_errors
        )
        if not clean_membership_negative_control:
            failures.append("clean input outside its generation unit was accepted")

        missing_scene_shot = copy.deepcopy(generated)
        scene_asset = next(
            asset
            for asset in missing_scene_shot["assets"]
            if asset["role"] == "scene_geography_camera_fov_reference"
        )
        removed_shot = scene_asset["coverage"]["shot_ids"].pop()
        scene_errors, _ = validate_plan(missing_scene_shot, base_dir=temp_root)
        scene_shot_negative_control = (
            f"scene_reference_shot_coverage_invalid:{removed_shot}:0" in scene_errors
        )
        if not scene_shot_negative_control:
            failures.append("scene reference with missing shot coverage was accepted")

    return failures, {
        "cases": results,
        "tvc_acceptance": tvc_checks,
        "tvc_metrics": tvc_metrics,
        "generation_unit_membership_negative_control": membership_negative_control,
        "generation_unit_scene_coherence_negative_control": scene_coherence_negative_control,
        "duplicate_unit_membership_negative_control": duplicate_unit_membership_negative_control,
        "cross_scene_plan_negative_control": cross_scene_plan_negative_control,
        "duplicate_direct_input_negative_control": duplicate_direct_input_negative_control,
        "storyboard_scene_negative_control": storyboard_scene_negative_control,
        "duplicate_identity_negative_control": duplicate_identity_negative_control,
        "vertical_tvc_negative_control": vertical_tvc_negative_control,
        "generated_evidence_control": not any("generated whole-film evidence" in item for item in failures),
        "fake_raster_negative_control": fake_raster_negative_control,
        "reused_file_negative_control": reused_file_negative_control,
        "clean_input_membership_negative_control": clean_membership_negative_control,
        "scene_shot_coverage_negative_control": scene_shot_negative_control,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIRcreative whole-film visual asset coverage.")
    parser.add_argument("--plan", type=Path, help="JSON visual asset plan to validate.")
    parser.add_argument("--inventory", type=Path, help="JSON film inventory to expand and validate.")
    parser.add_argument("--output", type=Path, help="Write the expanded plan from --inventory.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    selected = sum(bool(value) for value in (args.self_test, args.plan, args.inventory))
    if selected != 1:
        parser.error("choose exactly one of --self-test, --plan, or --inventory")
    if args.output and not args.inventory:
        parser.error("--output requires --inventory")
    try:
        if args.self_test:
            errors, report = self_test()
        elif args.plan:
            assert args.plan is not None
            path = args.plan.expanduser().resolve()
            errors, metrics = validate_plan(load_json(path), base_dir=path.parent)
            report = {"plan": str(path), "metrics": metrics}
        else:
            assert args.inventory is not None
            path = args.inventory.expanduser().resolve()
            expanded = derive_plan(load_json(path))
            errors, metrics = validate_plan(expanded, base_dir=path.parent)
            report = {"inventory": str(path), "metrics": metrics}
            if args.output:
                output = args.output.expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(expanded, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                report["output"] = str(output)
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        print("DIRCREATIVE_VISUAL_ASSET_PLAN_AUDIT: FAIL")
        return 1
    report["status"] = "PASS" if not errors else "FAIL"
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if errors:
        for error in errors:
            print(f"- {error}")
        print("DIRCREATIVE_VISUAL_ASSET_PLAN_AUDIT: FAIL")
        return 1
    print("DIRCREATIVE_VISUAL_ASSET_PLAN_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
