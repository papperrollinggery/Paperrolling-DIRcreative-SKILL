#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import struct
import tempfile
import warnings
import zlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from dircreative_verify_release import read_relative_regular_file_once

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only on dependency-poor hosts
    Draft202012Validator = None  # type: ignore[assignment]

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # pragma: no cover - PNG still has a stdlib full-decode path
    Image = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]
    UnidentifiedImageError = OSError  # type: ignore[assignment,misc]


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "skills/dircreative/runtime/visual-asset-plan.schema.json"
CASES_PATH = ROOT / "tests/fixtures/visual-asset-plan/cases.json"
TVC_INVENTORY_PATH = ROOT / "tests/fixtures/visual-asset-plan/tvc-60s-inventory.json"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
UTC_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
TIMECODE_SCHEMA_PATTERN = (
    r"^[0-9]{2,}:[0-5][0-9](?:\.[0-9]+)?-"
    r"[0-9]{2,}:[0-5][0-9](?:\.[0-9]+)?$"
)
TIMECODE_RANGE_RE = re.compile(
    r"^(?P<start_minutes>[0-9]{2,}):(?P<start_seconds>[0-5][0-9](?:\.[0-9]+)?)"
    r"-(?P<end_minutes>[0-9]{2,}):(?P<end_seconds>[0-5][0-9](?:\.[0-9]+)?)$"
)
PLACEHOLDER_RE = re.compile(
    r"(?:\bTB" r"D\b|\bTO" r"DO\b|\bFIX" r"ME\b|待" r"定|占" r"位|place" r"holder)",
    re.IGNORECASE,
)
MIN_RASTER_WIDTH = 640
MIN_RASTER_HEIGHT = 360
MIN_RASTER_BYTES = 256
MAX_RASTER_FILE_BYTES = 250 * 1024 * 1024
MAX_RASTER_PIXELS = 100_000_000
MAX_DECODED_BYTES = 512 * 1024 * 1024
NORMALIZATION_PROFILE = "rgba8-oriented-v1"
EVIDENCE_FORMATS = {"PNG"}
TECHNICAL_RULESET = "dircreative-raster-evidence-v4"
TECHNICAL_RECEIPT_VERSION = "2.0"
VISUAL_QA_RULESET = "dircreative-role-truth-review-v2"
VISUAL_QA_RECEIPT_VERSION = "2.0"
VISUAL_REVIEW_MANIFEST_VERSION = "1.0"
SCOPED_VISUAL_REVIEW_MANIFEST_VERSION = "1.1"
LOCAL_VISUAL_REVIEW_MANIFEST_VERSION = "1.2"
SELF_CHECK_MANIFEST_VERSION = "1.2"
SELF_CHECK_RULESET = "dircreative-executor-role-self-check-v1"
FAILED_BATCH_OBSERVATIONS_VERSION = "1.3"
FAILED_BATCH_OBSERVATIONS_RULESET = "dircreative-failed-batch-observations-v1"
SCHEMA_VERSION = "2.3"
FUTURE_TIMESTAMP_TOLERANCE_SECONDS = 300
TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED = (
    "visual_assets_complete_requires_trusted_host_review_adoption"
)

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
STORYBOARD_STRATEGIES = {"individual_frames", "annotated_reference"}
STORYBOARD_ACQUISITIONS = {"native_generate", "assembled_model_panels"}
DELIVERY_FRAME_ROLES = {
    "scene_geography_camera_fov_reference",
    "lighting_material_style_board",
    "storyboard_frame",
    *DIRECT_ROLES,
}
DELIVERY_ASPECT_RATIO_TOLERANCE = 0.02
GENERATED_STATUSES = {"generated_candidate", "user_locked", "reused_locked"}
EXISTING_SOURCE_ROLES = {
    "character_identity_reference", "product_identity_board", "prop_continuity_board",
    "scene_geography_camera_fov_reference", "lighting_material_style_board",
}
COMPLETION_CLAIMS = {
    "none",
    "plan_complete",
    "sample_plan_complete",
    "asset_only_plan_complete",
    "sample_visual_assets_complete",
    "visual_assets_complete",
}
GENERATED_CLAIMS = {"sample_visual_assets_complete", "visual_assets_complete"}
ASSET_FIELDS = {
    "asset_id",
    "role",
    "required",
    "action",
    "purpose",
    "coverage",
    "inherits_from",
    "planning_only",
    "direct_video_input",
    "status",
    "generated_file",
    "generated_sha256",
    "generated_pixel_sha256",
    "generated_perceptual_hash",
    "truth_sha256",
    "technical_receipt",
    "visual_qa_receipt",
    "compile_route",
}
ASSET_OPTIONAL_FIELDS = {
    "character_mode",
    "identity_kind",
    "derived_from_asset_id",
    "approved_source_master_sha256",
    "character_contract_sha256",
}
ASSET_EXECUTION_FIELDS = {"execution_task_id", "candidate_self_check", "candidate_repair_source"}
CHARACTER_MODES = {"headed_master", "headed_state", "headless_safe"}
IDENTITY_KINDS = {"human", "nonhuman"}
COMPILE_ROUTES = {"direct_concise", "selected_skill_handoff", "deterministic_assembly"}
COVERAGE_FIELDS = {
    "scene_ids",
    "character_ids",
    "appearance_state_ids",
    "product_ids",
    "prop_ids",
    "shot_ids",
    "generation_unit_ids",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload


def load_json_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return payload, hashlib.sha256(data).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


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


def validate_id_list(
    value: Any,
    label: str,
    errors: list[str],
    *,
    nonempty: bool = False,
) -> list[str]:
    values = safe_id_list(value)
    if not isinstance(value, list) or len(values) != len(value):
        errors.append(f"invalid_id_list:{label}")
        return []
    if nonempty and not values:
        errors.append(f"empty_id_list:{label}")
    for duplicate in duplicate_values(values):
        errors.append(f"duplicate_id:{label}:{duplicate}")
    return values


def add_coverage_error(errors: list[str], prefix: str, missing: list[str]) -> None:
    if missing:
        errors.append(f"{prefix}:{','.join(missing)}")


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _stdlib_schema_errors(payload: Any, schema: dict[str, Any]) -> list[str]:
    """Validate the schema subset used by this contract without site-packages.

    The release remains self-contained on clean Python hosts.  The full
    Draft202012 validator is used when available; this fail-closed fallback
    covers every keyword present in visual-asset-plan.schema.json.
    """

    def resolve(fragment: dict[str, Any]) -> dict[str, Any]:
        reference = fragment.get("$ref")
        if not isinstance(reference, str):
            return fragment
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise ValueError(f"unsupported schema reference: {reference}")
        name = reference[len(prefix) :]
        resolved = schema.get("$defs", {}).get(name)
        if not isinstance(resolved, dict):
            raise ValueError(f"unknown schema reference: {reference}")
        return resolved

    def walk(value: Any, fragment: dict[str, Any], path: str) -> list[str]:
        fragment = resolve(fragment)
        found: list[str] = []
        branches = fragment.get("oneOf")
        if isinstance(branches, list):
            matches = 0
            for branch in branches:
                if isinstance(branch, dict) and not walk(value, branch, path):
                    matches += 1
            if matches != 1:
                return [f"json_schema:{path}:oneOf"]
            return []

        expected_type = fragment.get("type")
        if isinstance(expected_type, str) and not _schema_type_matches(value, expected_type):
            return [f"json_schema:{path}:type"]
        if "const" in fragment and value != fragment["const"]:
            found.append(f"json_schema:{path}:const")
        enum = fragment.get("enum")
        if isinstance(enum, list) and value not in enum:
            found.append(f"json_schema:{path}:enum")
        pattern = fragment.get("pattern")
        if isinstance(value, str) and isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            found.append(f"json_schema:{path}:pattern")
        minimum_length = fragment.get("minLength")
        if isinstance(value, str) and isinstance(minimum_length, int) and len(value) < minimum_length:
            found.append(f"json_schema:{path}:minLength")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            minimum = fragment.get("minimum")
            maximum = fragment.get("maximum")
            exclusive_minimum = fragment.get("exclusiveMinimum")
            if isinstance(minimum, (int, float)) and value < minimum:
                found.append(f"json_schema:{path}:minimum")
            if isinstance(maximum, (int, float)) and value > maximum:
                found.append(f"json_schema:{path}:maximum")
            if isinstance(exclusive_minimum, (int, float)) and value <= exclusive_minimum:
                found.append(f"json_schema:{path}:exclusiveMinimum")
        if isinstance(value, list):
            minimum_items = fragment.get("minItems")
            if isinstance(minimum_items, int) and len(value) < minimum_items:
                found.append(f"json_schema:{path}:minItems")
            if fragment.get("uniqueItems") is True:
                fingerprints = [canonical_json_sha256(item) for item in value]
                if len(set(fingerprints)) != len(fingerprints):
                    found.append(f"json_schema:{path}:uniqueItems")
            item_schema = fragment.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    found.extend(walk(item, item_schema, f"{path}.{index}"))
        if isinstance(value, dict):
            required = fragment.get("required")
            if isinstance(required, list):
                for key in required:
                    if key not in value:
                        found.append(f"json_schema:{path}:required")
            properties = fragment.get("properties")
            if isinstance(properties, dict):
                if fragment.get("additionalProperties") is False:
                    for key in value:
                        if key not in properties:
                            found.append(f"json_schema:{path}:additionalProperties")
                for key, child_schema in properties.items():
                    if key in value and isinstance(child_schema, dict):
                        child_path = key if path == "$" else f"{path}.{key}"
                        found.extend(walk(value[key], child_schema, child_path))
        return found

    return list(dict.fromkeys(walk(payload, schema, "$")))


def schema_errors(payload: Any) -> list[str]:
    schema = load_json(SCHEMA_PATH)
    if Draft202012Validator is None:
        return _stdlib_schema_errors(payload, schema)
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for issue in sorted(
        validator.iter_errors(payload),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    ):
        path = ".".join(str(part) for part in issue.absolute_path) or "$"
        errors.append(f"json_schema:{path}:{issue.validator}")
    return errors


def contained_file(raw: Any, base_dir: Path) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    relative = Path(raw)
    if relative.is_absolute():
        return None
    try:
        root = base_dir.resolve(strict=True)
        resolved = (root / relative).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def _png_passes(width: int, height: int, interlace: int) -> list[tuple[int, int]]:
    if interlace == 0:
        return [(width, height)]
    passes = [
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    ]
    result: list[tuple[int, int]] = []
    for x0, y0, dx, dy in passes:
        pass_width = 0 if width <= x0 else (width - x0 + dx - 1) // dx
        pass_height = 0 if height <= y0 else (height - y0 + dy - 1) // dy
        if pass_width and pass_height:
            result.append((pass_width, pass_height))
    return result


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    diagonal_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= diagonal_distance:
        return left
    if above_distance <= diagonal_distance:
        return above
    return upper_left


def _unfilter_png_rows(
    decoded: bytes,
    *,
    width: int,
    height: int,
    channels: int,
) -> bytes:
    row_bytes = width * channels
    expected = height * (row_bytes + 1)
    if len(decoded) != expected:
        raise ValueError("png_scanline_layout_invalid")
    rows: list[bytes] = []
    cursor = 0
    previous = bytes(row_bytes)
    for _ in range(height):
        filter_type = decoded[cursor]
        cursor += 1
        encoded = decoded[cursor : cursor + row_bytes]
        cursor += row_bytes
        reconstructed = bytearray(row_bytes)
        for index, value in enumerate(encoded):
            left = reconstructed[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            elif filter_type == 4:
                predictor = _paeth_predictor(left, above, upper_left)
            else:
                raise ValueError("png_filter_invalid")
            reconstructed[index] = (value + predictor) & 0xFF
        row = bytes(reconstructed)
        rows.append(row)
        previous = row
    return b"".join(rows)


def _rgba_from_png_samples(samples: bytes, color_type: int) -> bytes:
    if color_type == 6:
        return samples
    channels = {0: 1, 2: 3, 4: 2}[color_type]
    pixels = len(samples) // channels
    rgba = bytearray(pixels * 4)
    if color_type == 0:
        rgba[0::4] = samples
        rgba[1::4] = samples
        rgba[2::4] = samples
        rgba[3::4] = b"\xff" * pixels
    elif color_type == 2:
        rgba[0::4] = samples[0::3]
        rgba[1::4] = samples[1::3]
        rgba[2::4] = samples[2::3]
        rgba[3::4] = b"\xff" * pixels
    else:
        gray = samples[0::2]
        rgba[0::4] = gray
        rgba[1::4] = gray
        rgba[2::4] = gray
        rgba[3::4] = samples[1::2]
    return bytes(rgba)


def normalized_pixel_sha256(width: int, height: int, rgba: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(f"{width}x{height}:RGBA:".encode("ascii"))
    digest.update(rgba)
    return digest.hexdigest()


def normalized_perceptual_hash(width: int, height: int, rgba: bytes) -> str:
    sample_size = 16
    luminance: list[int] = []
    for sample_y in range(sample_size):
        source_y = min(height - 1, (sample_y * height + height // 2) // sample_size)
        for sample_x in range(sample_size):
            source_x = min(width - 1, (sample_x * width + width // 2) // sample_size)
            offset = (source_y * width + source_x) * 4
            red, green, blue, alpha = rgba[offset : offset + 4]
            opaque_luma = (299 * red + 587 * green + 114 * blue) // 1000
            luminance.append((opaque_luma * alpha + 255 * (255 - alpha)) // 255)
    average = sum(luminance) / len(luminance)
    bits = 0
    for value in luminance:
        bits = (bits << 1) | int(value >= average)
    return f"{bits:064x}"


def normalized_raster_evidence(width: int, height: int, rgba: bytes) -> dict[str, Any]:
    expected_bytes = width * height * 4
    if len(rgba) != expected_bytes or expected_bytes > MAX_DECODED_BYTES:
        raise ValueError("normalized_pixel_buffer_invalid")
    alpha = rgba[3::4]
    return {
        "pixel_sha256": normalized_pixel_sha256(width, height, rgba),
        "perceptual_hash": normalized_perceptual_hash(width, height, rgba),
        "alpha_min": min(alpha),
        "alpha_max": max(alpha),
        "alpha_nonopaque_pixel_count": sum(value != 255 for value in alpha),
    }


def canonical_png_structure(
    path: Path,
) -> tuple[int, int, int, int, int, list[bytes]]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("png_signature_invalid")
    offset = 8
    ihdr: tuple[int, int, int, int, int] | None = None
    idat_parts: list[bytes] = []
    saw_iend = False
    chunk_index = 0
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("png_chunk_truncated")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        crc_end = payload_end + 4
        if crc_end > len(data):
            raise ValueError("png_chunk_length_invalid")
        payload = data[payload_start:payload_end]
        expected_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        actual_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if expected_crc != actual_crc:
            raise ValueError("png_crc_invalid")
        if chunk_index == 0 and kind != b"IHDR":
            raise ValueError("png_ihdr_not_first")
        if kind == b"IHDR":
            if ihdr is not None or length != 13:
                raise ValueError("png_ihdr_invalid")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if width <= 0 or height <= 0 or width * height > MAX_RASTER_PIXELS:
                raise ValueError("png_dimensions_invalid")
            if bit_depth != 8 or color_type not in {0, 2, 4, 6}:
                raise ValueError("png_color_model_invalid")
            if compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError("png_encoding_method_invalid")
            ihdr = (width, height, bit_depth, color_type, interlace)
        elif kind == b"IDAT":
            if ihdr is None:
                raise ValueError("png_idat_before_ihdr")
            idat_parts.append(payload)
        elif kind == b"IEND":
            if length != 0 or crc_end != len(data):
                raise ValueError("png_iend_invalid")
            saw_iend = True
        elif kind == b"tRNS":
            # Pillow applies tRNS while the dependency-free decoder cannot yet
            # normalize it identically. Reject it on every host instead of
            # producing environment-dependent pixel identities.
            raise ValueError("png_trns_normalization_unsupported")
        elif kind == b"eXIf":
            # PNG orientation metadata would require the same transform in the
            # stdlib and Pillow paths. Canonical evidence PNGs must be baked.
            raise ValueError("png_exif_orientation_unsupported")
        elif kind and 65 <= kind[0] <= 90 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            raise ValueError("png_unknown_critical_chunk")
        offset = crc_end
        chunk_index += 1
        if saw_iend:
            break
    if ihdr is None or not idat_parts or not saw_iend:
        raise ValueError("png_required_chunk_missing")
    width, height, bit_depth, color_type, interlace = ihdr
    return width, height, bit_depth, color_type, interlace, idat_parts


def decode_png_stdlib(path: Path) -> dict[str, Any]:
    width, height, bit_depth, color_type, interlace, idat_parts = canonical_png_structure(path)
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    pass_shapes = _png_passes(width, height, interlace)
    row_layout: list[tuple[int, int]] = []
    expected_size = 0
    for pass_width, pass_height in pass_shapes:
        row_bytes = (pass_width * channels * bit_depth + 7) // 8
        expected_size += pass_height * (row_bytes + 1)
        row_layout.append((pass_height, row_bytes))
    if expected_size <= 0 or expected_size > MAX_DECODED_BYTES:
        raise ValueError("png_decoded_size_invalid")
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(b"".join(idat_parts), expected_size + 1)
    decoded += decoder.flush()
    if (
        len(decoded) != expected_size
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
    ):
        raise ValueError("png_pixel_stream_invalid")
    cursor = 0
    for pass_height, row_bytes in row_layout:
        for _ in range(pass_height):
            if decoded[cursor] not in {0, 1, 2, 3, 4}:
                raise ValueError("png_filter_invalid")
            cursor += row_bytes + 1
    if cursor != len(decoded):
        raise ValueError("png_scanline_layout_invalid")
    samples = _unfilter_png_rows(
        decoded,
        width=width,
        height=height,
        channels=channels,
    )
    rgba = _rgba_from_png_samples(samples, color_type)
    return {
        "format": "PNG",
        "width": width,
        "height": height,
        "decoder": "stdlib-png-full-decode",
        "normalization_profile": NORMALIZATION_PROFILE,
        **normalized_raster_evidence(width, height, rgba),
    }


def inspect_raster(
    path: Path,
    *,
    allow_derived_planning_crop: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    """Fully decode a canonical evidence PNG.

    The default minimum dimensions apply to every canonical or production image.
    ``allow_derived_planning_crop`` only lets a caller inspect the raster part of
    a planning crop after that caller has independently proven its source-board
    extraction receipt.  It deliberately carries no provenance claim itself.
    """
    try:
        before = path.stat()
        size = before.st_size
    except OSError:
        return None, "stat_failed"
    if size < MIN_RASTER_BYTES:
        return None, "file_too_small"
    if size > MAX_RASTER_FILE_BYTES:
        return None, "file_too_large"
    try:
        with path.open("rb") as handle:
            signature = handle.read(8)
    except OSError:
        return None, "read_failed"
    result: dict[str, Any] | None = None
    is_png = signature == b"\x89PNG\r\n\x1a\n"
    if is_png:
        # Enforce the subset whose Pillow and stdlib paths normalize to the
        # same RGBA8 pixels, including identical tRNS/eXIf rejection.
        try:
            canonical_png_structure(path)
        except (OSError, ValueError, zlib.error) as exc:
            return None, re.sub(r"[^A-Za-z0-9_.-]+", "_", str(exc) or type(exc).__name__)[:96]
    if Image is not None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                with Image.open(path) as probe:
                    image_format = str(probe.format or "").upper()
                    width, height = probe.size
                    if image_format not in EVIDENCE_FORMATS:
                        raise ValueError("format_not_allowed")
                    if width <= 0 or height <= 0 or width * height > MAX_RASTER_PIXELS:
                        raise ValueError("dimensions_invalid")
                    probe.verify()
                with Image.open(path) as decoded:
                    decoded.load()
                    normalized = ImageOps.exif_transpose(decoded).convert("RGBA")
                    width, height = normalized.size
                    rgba = normalized.tobytes()
            result = {
                "format": image_format,
                "width": width,
                "height": height,
                "decoder": "pillow-full-decode",
                "normalization_profile": NORMALIZATION_PROFILE,
                **normalized_raster_evidence(width, height, rgba),
            }
        except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Warning) as exc:
            return None, re.sub(r"[^A-Za-z0-9_.-]+", "_", str(exc) or type(exc).__name__)[:96]
    elif is_png:
        try:
            result = decode_png_stdlib(path)
        except (OSError, ValueError, zlib.error) as exc:
            return None, re.sub(r"[^A-Za-z0-9_.-]+", "_", str(exc) or type(exc).__name__)[:96]
    else:
        return None, "non_png_decoder_unavailable"
    if (
        not allow_derived_planning_crop
        and (result["width"] < MIN_RASTER_WIDTH or result["height"] < MIN_RASTER_HEIGHT)
    ):
        return None, "dimensions_below_minimum"
    try:
        result["sha256"] = sha256_file(path)
    except OSError:
        return None, "hash_failed"
    try:
        after = path.stat()
    except OSError:
        return None, "file_changed_during_decode"
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if after_identity != before_identity:
        return None, "file_changed_during_decode"
    return result, None


def inspect_raster_cached(
    path: Path,
    cache: dict[
        tuple[str, int, int, int, int, int],
        tuple[dict[str, Any] | None, str | None],
    ]
    | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if cache is None:
        return inspect_raster(path)
    try:
        before = path.stat()
        key = (
            str(path.resolve(strict=True)),
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
    except OSError:
        return None, "stat_failed"
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = inspect_raster(path)
    try:
        after = path.stat()
    except OSError:
        return None, "file_changed_during_decode"
    after_key = (
        str(path.resolve(strict=True)),
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if after_key != key:
        return None, "file_changed_during_decode"
    cache[key] = result
    return result


def receipt_sha256(receipt: dict[str, Any]) -> str:
    return canonical_json_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )


def make_technical_receipt(
    asset_id: str,
    evidence: dict[str, Any],
    *,
    checked_at: str,
) -> dict[str, Any]:
    receipt = {
        "receipt_version": TECHNICAL_RECEIPT_VERSION,
        "asset_id": asset_id,
        "file_sha256": evidence["sha256"],
        "pixel_sha256": evidence["pixel_sha256"],
        "perceptual_hash": evidence["perceptual_hash"],
        "ruleset": TECHNICAL_RULESET,
        "checked_at": checked_at,
        "decoder": evidence["decoder"],
        "normalization_profile": evidence["normalization_profile"],
        "format": evidence["format"],
        "width": evidence["width"],
        "height": evidence["height"],
        "status": "technical_evidence_pass",
    }
    receipt["receipt_sha256"] = receipt_sha256(receipt)
    return receipt


def valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not UTC_TIMESTAMP_RE.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def parsed_utc_timestamp(value: Any) -> datetime | None:
    if not valid_utc_timestamp(value):
        return None
    return datetime.fromisoformat(str(value)[:-1] + "+00:00")


def timestamp_in_review_window(value: Any, *, not_before: str) -> bool:
    parsed = parsed_utc_timestamp(value)
    floor = parsed_utc_timestamp(not_before)
    if parsed is None or floor is None or parsed < floor:
        return False
    now = datetime.now(timezone.utc).timestamp()
    return parsed.timestamp() <= now + FUTURE_TIMESTAMP_TOLERANCE_SECONDS


def validate_technical_receipt(
    receipt: Any,
    *,
    asset_id: str,
    evidence: dict[str, Any],
    truth_locked_at: str,
) -> str | None:
    expected_fields = {
        "receipt_version",
        "asset_id",
        "file_sha256",
        "pixel_sha256",
        "perceptual_hash",
        "ruleset",
        "checked_at",
        "decoder",
        "normalization_profile",
        "format",
        "width",
        "height",
        "status",
        "receipt_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_fields:
        return "shape"
    checks = {
        "version": receipt.get("receipt_version") == TECHNICAL_RECEIPT_VERSION,
        "asset": receipt.get("asset_id") == asset_id,
        "hash": receipt.get("file_sha256") == evidence["sha256"],
        "pixel_hash": receipt.get("pixel_sha256") == evidence["pixel_sha256"],
        "perceptual_hash": receipt.get("perceptual_hash") == evidence["perceptual_hash"],
        "ruleset": receipt.get("ruleset") == TECHNICAL_RULESET,
        "timestamp": timestamp_in_review_window(
            receipt.get("checked_at"),
            not_before=truth_locked_at,
        ),
        # Decoder is diagnostic provenance. Pixel identity is defined by the
        # normalization profile and hashes, so a receipt remains portable
        # across equivalent decoder implementations.
        "decoder": receipt.get("decoder")
        in {"pillow-full-decode", "stdlib-png-full-decode"},
        "normalization_profile": receipt.get("normalization_profile")
        == evidence["normalization_profile"]
        == NORMALIZATION_PROFILE,
        "format": receipt.get("format") == evidence["format"],
        "width": receipt.get("width") == evidence["width"],
        "height": receipt.get("height") == evidence["height"],
        "status": receipt.get("status") == "technical_evidence_pass",
        "receipt_hash": receipt.get("receipt_sha256") == receipt_sha256(receipt),
    }
    return next((key for key, passed in checks.items() if not passed), None)


def visual_review_subject_sha256(
    payload: dict[str, Any],
    *,
    scope_asset_ids: list[str] | None = None,
    asset_local: bool = False,
) -> str:
    scope = set(scope_asset_ids) if scope_asset_ids is not None else None
    assets = [
        {
            "asset_id": asset.get("asset_id"),
            "role": asset.get("role"),
            "purpose": asset.get("purpose"),
            "coverage": asset.get("coverage"),
            "inherits_from": asset.get("inherits_from"),
            "truth_sha256": asset.get("truth_sha256"),
            "file_sha256": asset.get("generated_sha256"),
            "pixel_sha256": asset.get("generated_pixel_sha256"),
            "perceptual_hash": asset.get("generated_perceptual_hash"),
        }
        for asset in payload.get("assets", [])
        if isinstance(asset, dict)
        and asset.get("required") is True
        and (scope is None or asset.get("asset_id") in scope)
    ]
    assets.sort(key=lambda item: str(item.get("asset_id")))
    if asset_local:
        if scope is None:
            raise ValueError("asset_local_review_requires_scope")
        by_id = {a["asset_id"]: a for a in payload.get("assets", []) if isinstance(a, dict)}
        closure = set(scope)
        pending = list(scope)
        while pending:
            row = by_id.get(pending.pop(), {})
            for parent in row.get("inherits_from", []):
                if parent not in closure:
                    closure.add(parent); pending.append(parent)
        contract_fields = (
            "asset_id", "role", "purpose", "coverage", "inherits_from", "truth_sha256",
            "generated_sha256", "generated_pixel_sha256", "generated_perceptual_hash",
            "planning_only", "direct_video_input", "character_mode", "identity_kind",
            "character_master_requirements", "derived_from_asset_id", "approved_source_master_sha256",
        )
        contracts = [{key: by_id.get(i, {}).get(key) for key in contract_fields} for i in sorted(closure)]
        spatial_roles = DELIVERY_FRAME_ROLES | {"professional_storyboard_motion_map", "scene_geography_camera_fov_reference"}
        shot_ids = {shot for i in scope if by_id.get(i, {}).get("role") in spatial_roles
                    for shot in by_id[i].get("coverage", {}).get("shot_ids", [])}
        return canonical_json_sha256({
            "scheme": "asset-local-review-v1", "schema_version": payload.get("schema_version"),
            "project_id": payload.get("project_id"), "scope_asset_ids": sorted(scope),
            "delivery_profile": ({key: payload.get("delivery_profile", {}).get(key)
                                  for key in ("medium", "aspect_ratio", "raster_width", "raster_height")}
                                 if payload.get("scope") == "asset_only" or any(by_id.get(i, {}).get("role") in DELIVERY_FRAME_ROLES for i in scope) else None),
            "contracts": contracts,
            "shot_truth": [row for row in payload.get("shot_truth", []) if row.get("shot_id") in shot_ids],
        })
    return canonical_json_sha256(
        {
            "schema_version": payload.get("schema_version"),
            "project_id": payload.get("project_id"),
            "truth_revision": payload.get("truth_revision"),
            "inventory_sha256": payload.get("inventory_sha256"),
            "shot_cards_sha256": payload.get("shot_cards_sha256"),
            "shot_truth_sha256": payload.get("shot_truth_sha256"),
            "assets": assets,
        }
    )


def visual_review_rubric_id(role: str) -> str:
    return f"dircreative-{role}-review-v1"


def candidate_check_ids(asset: dict[str, Any]) -> list[str]:
    common = ["saved_pixels_and_detail", "truth_and_reference_match", "artifacts_and_downstream_fit"]
    if asset.get("role") == "character_identity_reference" and asset.get("identity_kind", "human") == "nonhuman":
        return common + [
            "recognition_closeup", "front_reference_view", "left_reference_view", "right_reference_view", "back_reference_view",
            "recognition_features_anatomy_or_structure", "materials_and_appearance_state",
        ]
    by_role = {
        "character_identity_reference": ["frontal_portrait", "front_body", "left_profile", "right_profile", "back_body", "identity_and_proportions", "wardrobe_material_and_side_details", "mode_and_source_preservation"],
        "product_identity_board": ["silhouette_scale_and_construction", "material_function_and_exact_graphics"],
        "prop_continuity_board": ["shape_interface_and_orientation", "state_and_custody", "reference_role_boundary"],
        "scene_geography_camera_fov_reference": ["landmarks_entrances_and_scale", "axis_camera_and_support", "empty_scene_and_projection"],
        "lighting_material_style_board": ["light_sources_and_material_response", "palette_exposure_and_role_boundary"],
        "professional_storyboard_motion_map": ["panel_coverage_and_phase", "camera_and_spatial_continuity", "contact_counterforce_and_consequence", "annotations_and_reference_boundary"],
        "storyboard_frame": ["camera_depth_and_frozen_phase", "action_contact_and_environment", "neighbor_custody_and_persistent_state"],
        "clean_first_frame": ["camera_depth_and_frozen_phase", "action_contact_and_environment", "neighbor_custody_and_persistent_state", "clean_input_preserves_intended_effects"],
        "clean_key_frame": ["camera_depth_and_frozen_phase", "action_contact_and_environment", "neighbor_custody_and_persistent_state", "clean_input_preserves_intended_effects"],
        "clean_end_frame": ["camera_depth_and_frozen_phase", "action_contact_and_environment", "neighbor_custody_and_persistent_state", "clean_input_preserves_intended_effects"],
    }
    role = asset.get("role")
    if role not in by_role:
        raise ValueError("candidate_self_check_role_unknown")
    return [*common, *by_role[role]]


def record_candidate_output(
    payload: dict[str, Any], *, base_dir: Path, asset_id: str,
    image_path: Path, execution_task_id: str, checked_at: str | None = None,
    repair_source: dict[str, Any] | None = None, project_root: Path | None = None,
) -> dict[str, Any]:
    """Register saved bytes in the existing plan. Even failed visual candidates remain real."""
    if not isinstance(execution_task_id, str) or not ID_RE.fullmatch(execution_task_id):
        raise ValueError("execution_task_id_invalid")
    truth = copy.deepcopy(payload)
    truth["completion_claim"] = "none"
    if validate_plan(truth, base_dir=base_dir, _validate_recorded_assets=False)[0]:
        raise ValueError("visual_asset_plan_invalid")
    candidate = copy.deepcopy(payload)
    asset = next((item for item in candidate["assets"] if item["asset_id"] == asset_id), None)
    if asset is None or asset.get("action") not in {"generate", "derive"}:
        raise ValueError("candidate_output_requires_generated_asset")
    if asset.get("status") in {"user_locked", "reused_locked"}:
        raise ValueError("locked_asset_requires_a_new_candidate_version")
    root = base_dir.resolve(strict=True)
    # Validate the supplied lexical path too: resolving it first would conceal symlinks.
    if image_path.is_absolute():
        try:
            relative = image_path.relative_to(base_dir.absolute()).as_posix()
        except ValueError:
            relative = image_path.relative_to(root).as_posix()
    else:
        relative = image_path.as_posix()
    raw = read_relative_regular_file_once(root, relative, max_bytes=MAX_RASTER_FILE_BYTES, label="saved image")
    evidence, reason = inspect_raster(root / relative)
    if evidence is None or evidence["sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError("candidate_raster_invalid:" + str(reason or "changed_during_read"))
    if asset.get("generated_pixel_sha256") and (
        evidence["sha256"] == asset.get("generated_sha256")
        or evidence["pixel_sha256"] == asset["generated_pixel_sha256"]
        or relative == asset.get("generated_file")
    ):
        raise ValueError("candidate_requires_new_output_pixels_and_path")
    if repair_source is not None:
        source_root = (project_root or base_dir).resolve(strict=True)
        expected = build_candidate_repair_source(
            project_root=source_root, visual_plan_binding=repair_source.get("source_plan"),
            asset_id=asset_id, changes=repair_source.get("changes"),
            base_plan_binding=repair_source.get("base_plan"),
        )
        if repair_source != expected:
            raise ValueError("candidate_repair_source_binding_mismatch")
        if evidence["pixel_sha256"] == expected["source_image"]["pixel_sha256"]:
            raise ValueError("candidate_repair_requires_new_output_pixels")
        old_raw = read_relative_regular_file_once(source_root, expected["source_plan"]["relative_path"], max_bytes=8 * 1024 * 1024, label="repair source plan")
        if json.loads(old_raw) != payload or (source_root / expected["source_plan"]["relative_path"]).parent != root:
            raise ValueError("candidate_repair_record_plan_mismatch")
        asset["candidate_repair_source"] = copy.deepcopy(expected)
    else:
        asset.pop("candidate_repair_source", None)
    now = checked_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not timestamp_in_review_window(now, not_before=str(payload["truth_locked_at"])):
        raise ValueError("candidate_timestamp_invalid")
    asset.update(status="generated_candidate", generated_file=relative,
                 generated_sha256=evidence["sha256"], generated_pixel_sha256=evidence["pixel_sha256"],
                 generated_perceptual_hash=evidence["perceptual_hash"],
                 technical_receipt=make_technical_receipt(asset_id, evidence, checked_at=now),
                 visual_qa_receipt=None, execution_task_id=execution_task_id, candidate_self_check=None)
    candidate["completion_claim"] = "none"
    return candidate


def candidate_self_check_template(payload: dict[str, Any], asset_id: str) -> dict[str, Any]:
    """An explicit pending template, never a prefilled passing review."""
    asset = next(item for item in payload["assets"] if item["asset_id"] == asset_id)
    return {
        "schema_version": SELF_CHECK_MANIFEST_VERSION, "ruleset": SELF_CHECK_RULESET,
        "review_subject_sha256": visual_review_subject_sha256(payload, scope_asset_ids=[asset_id]),
        "scope_asset_ids": [asset_id], "reviewed_at": None,
        "reviewer_type": "executor_self_check", "reviewer_id": None,
        "review_task_id": None,
        "assets": [{
            "asset_id": asset_id, "role": asset["role"], "file_sha256": asset["generated_sha256"],
            "pixel_sha256": asset["generated_pixel_sha256"], "truth_sha256": asset["truth_sha256"],
            "rubric_id": visual_review_rubric_id(asset["role"]),
            "decision": "pending", "viewed_file": asset["generated_file"],
            "observations": [{"check_id": key, "result": "unverified", "observed": ""}
                             for key in candidate_check_ids(asset)],
        }],
    }


def validate_candidate_self_check(
    manifest: Any, *, payload: dict[str, Any], asset_id: str, base_dir: Path,
) -> list[str]:
    """Validate recorded observations and machine checks; does not grant visual QA authority."""
    if not isinstance(payload, dict) or not isinstance(payload.get("assets"), list):
        return ["candidate_self_check_plan_invalid"]
    asset = next((item for item in payload["assets"] if isinstance(item, dict) and item.get("asset_id") == asset_id), None)
    if not isinstance(asset, dict) or not isinstance(manifest, dict):
        return ["candidate_self_check_invalid"]
    if not isinstance(asset.get("technical_receipt"), dict):
        return ["candidate_self_check_technical_missing"]
    expected = candidate_self_check_template(payload, asset_id)
    failed_batch = manifest.get("schema_version") == FAILED_BATCH_OBSERVATIONS_VERSION
    if failed_batch:
        # Failed observations authorize only a bounded repair, never a pass.
        expected.update(schema_version=FAILED_BATCH_OBSERVATIONS_VERSION,
                        ruleset=FAILED_BATCH_OBSERVATIONS_RULESET, reviewer_type="batch_review")
    if set(manifest) != set(expected) or any(manifest.get(key) != expected[key] for key in (
        "schema_version", "ruleset", "review_subject_sha256", "scope_asset_ids", "reviewer_type",
    )):
        return ["candidate_self_check_identity_or_truth_mismatch"]
    if (not isinstance(manifest.get("reviewer_id"), str) or not ID_RE.fullmatch(manifest["reviewer_id"])
        or not isinstance(manifest.get("review_task_id"), str) or not ID_RE.fullmatch(manifest["review_task_id"])
        or not timestamp_in_review_window(manifest.get("reviewed_at"), not_before=str(asset.get("technical_receipt", {}).get("checked_at")))):
        return ["candidate_self_check_reviewer_or_timestamp_invalid"]
    entries = manifest.get("assets")
    if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
        return ["candidate_self_check_coverage_invalid"]
    entry = entries[0]; template = expected["assets"][0]
    if set(entry) != set(template) or any(entry.get(key) != template[key] for key in (
        "asset_id", "role", "file_sha256", "pixel_sha256", "truth_sha256", "rubric_id", "viewed_file",
    )):
        return ["candidate_self_check_asset_binding_invalid"]
    observations = entry.get("observations")
    if not isinstance(observations, list) or any(not isinstance(item, dict) for item in observations):
        return ["candidate_self_check_observations_missing"]
    required = candidate_check_ids(asset)
    observation_ids = [item.get("check_id") for item in observations]
    if (failed_batch and (not observation_ids or len(set(observation_ids)) != len(observation_ids) or any(key not in required for key in observation_ids))
        or not failed_batch and observation_ids != required):
        return ["candidate_self_check_role_coverage_invalid"]
    for item in observations:
        if (set(item) != {"check_id", "result", "observed"}
            or item.get("result") not in {"pass", "fail", "not_applicable"}
            or not isinstance(item.get("observed"), str) or len(item["observed"].strip()) < 12):
            return ["candidate_self_check_observation_invalid"]
        if failed_batch and item["result"] != "fail":
            return ["failed_batch_observations_cannot_claim_pass"]
        if item["result"] == "not_applicable" and (
            asset.get("role") == "character_identity_reference"
            or item["check_id"] in {"saved_pixels_and_detail", "truth_and_reference_match", "artifacts_and_downstream_fit"}
        ):
            return ["candidate_self_check_required_observation_not_applicable"]
    if entry.get("decision") not in {"checked", "retry", "reject"}:
        return ["candidate_self_check_decision_invalid"]
    if failed_batch and entry["decision"] == "checked":
        return ["failed_batch_observations_cannot_claim_pass"]
    if entry["decision"] == "checked" and any(item["result"] == "fail" for item in observations):
        return ["candidate_self_check_failed_observation"]
    image = contained_file(asset.get("generated_file"), base_dir)
    evidence, reason = inspect_raster(image) if image is not None else (None, "missing")
    if evidence is None or evidence["sha256"] != asset.get("generated_sha256") or evidence["pixel_sha256"] != asset.get("generated_pixel_sha256"):
        return ["candidate_self_check_pixels_changed:" + str(reason or "hash")]
    technical = validate_technical_receipt(asset.get("technical_receipt"), asset_id=asset_id, evidence=evidence, truth_locked_at=str(payload["truth_locked_at"]))
    if technical:
        return ["candidate_self_check_technical_invalid:" + technical]
    if entry["decision"] != "checked":
        return ["candidate_self_check_requires_repair"]
    profile = payload.get("delivery_profile", {})
    if payload.get("scope") == "asset_only" or asset.get("role") in DELIVERY_FRAME_ROLES:
        width, height = profile.get("raster_width"), profile.get("raster_height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            if abs((evidence["width"] / evidence["height"]) / (width / height) - 1) > DELIVERY_ASPECT_RATIO_TOLERANCE:
                return ["candidate_self_check_delivery_aspect_mismatch"]
    # This records visual observations, not formal character acceptance.
    # Structure evidence belongs to the batch/dependency/final review, where it
    # is already validated. A detector result must not force per-image repair.
    return []


def pending_candidate_self_checks(
    payload: dict[str, Any], *, base_dir: Path, execution_task_id: str,
    asset_ids: set[str] | None = None,
) -> list[str]:
    """Pending candidates belong to this active plan, not to a caller-chosen task ID.

    Older assets without a registration remain readable through their existing
    QA/dependency checks. A resumed task cannot hide a newly registered candidate.
    """
    errors: list[str] = []
    for asset in payload.get("assets", []):
        if asset_ids is not None and asset.get("asset_id") not in asset_ids:
            continue
        if "execution_task_id" not in asset:
            continue
        # One valid substantive review is enough for these exact pixels and
        # facts. Do not demand a second executor checklist after batch review.
        if asset.get("visual_qa_receipt") is not None and not candidate_visual_review_errors(
            payload, asset_id=asset["asset_id"], base_dir=base_dir,
        ):
            continue
        binding = asset.get("candidate_self_check")
        asset_id = asset["asset_id"]
        if not isinstance(binding, dict) or set(binding) != {"relative_path", "sha256"}:
            errors.append(f"candidate_postcheck_required:{asset_id}"); continue
        try:
            raw = read_relative_regular_file_once(base_dir, binding["relative_path"], max_bytes=1024 * 1024, label="candidate self-check")
            if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
                raise ValueError("hash mismatch")
            problems = validate_candidate_self_check(json.loads(raw), payload=payload, asset_id=asset_id, base_dir=base_dir)
        except (OSError, ValueError, TypeError, KeyError):
            problems = ["candidate_self_check_unreadable_or_changed"]
        errors.extend(f"candidate_postcheck_failed:{asset_id}:{problem}" for problem in problems)
    return errors


def build_candidate_repair_source(
    *, project_root: Path, visual_plan_binding: Any, asset_id: str, changes: Any,
    base_plan_binding: Any = None,
) -> dict[str, Any]:
    """Bind a same-asset edit base to an actual current retry, without approval or a self-DAG."""
    if not isinstance(visual_plan_binding, dict) or set(visual_plan_binding) != {"relative_path", "sha256"}:
        raise ValueError("candidate_repair_plan_binding_invalid")
    root = project_root.resolve(strict=True)
    raw = read_relative_regular_file_once(root, visual_plan_binding["relative_path"], max_bytes=8 * 1024 * 1024, label="candidate repair plan")
    if hashlib.sha256(raw).hexdigest() != visual_plan_binding["sha256"]:
        raise ValueError("candidate_repair_plan_changed")
    plan = json.loads(raw)
    base = (root / visual_plan_binding["relative_path"]).parent
    if validate_plan(plan, base_dir=base)[0]:
        raise ValueError("candidate_repair_plan_invalid")
    asset = next((item for item in plan["assets"] if item["asset_id"] == asset_id), None)
    if (not isinstance(asset, dict) or asset.get("status") != "generated_candidate"
        or asset.get("action") not in {"generate", "derive"}
        or asset.get("role") not in {"character_identity_reference", "product_identity_board", "prop_continuity_board", "scene_geography_camera_fov_reference", "lighting_material_style_board"}
        or asset.get("visual_qa_receipt") is not None):
        raise ValueError("candidate_repair_requires_unapproved_current_asset")
    if asset.get("role") == "character_identity_reference" and asset.get("character_mode") != "headed_master":
        raise ValueError("candidate_repair_character_requires_current_headed_master")
    review_binding = asset.get("candidate_self_check")
    if not isinstance(review_binding, dict) or set(review_binding) != {"relative_path", "sha256"}:
        raise ValueError("candidate_repair_requires_recorded_self_check")
    review_raw = read_relative_regular_file_once(base, review_binding["relative_path"], max_bytes=1024 * 1024, label="candidate repair self-check")
    if hashlib.sha256(review_raw).hexdigest() != review_binding["sha256"]:
        raise ValueError("candidate_repair_self_check_changed")
    review = json.loads(review_raw)
    if validate_candidate_self_check(review, payload=plan, asset_id=asset_id, base_dir=base) != ["candidate_self_check_requires_repair"]:
        raise ValueError("candidate_repair_self_check_invalid")
    entry = review["assets"][0]
    if entry["decision"] != "retry":
        raise ValueError("candidate_repair_requires_retry_decision")
    failed = {item["check_id"] for item in entry["observations"] if item["result"] == "fail"}
    base_failed: set[str] = set()
    source_asset, source_dir = asset, base
    if base_plan_binding is not None:
        if not isinstance(base_plan_binding, dict) or set(base_plan_binding) != {"relative_path", "sha256"}:
            raise ValueError("candidate_repair_base_plan_binding_invalid")
        base_raw = read_relative_regular_file_once(root, base_plan_binding["relative_path"], max_bytes=8 * 1024 * 1024, label="repair base plan")
        if hashlib.sha256(base_raw).hexdigest() != base_plan_binding["sha256"]:
            raise ValueError("candidate_repair_base_plan_changed")
        source_plan = json.loads(base_raw)
        source_dir = (root / base_plan_binding["relative_path"]).parent
        if validate_plan(source_plan, base_dir=source_dir)[0] or source_plan.get("project_id") != plan["project_id"]:
            raise ValueError("candidate_repair_base_plan_invalid")
        source_asset = next((item for item in source_plan["assets"] if item["asset_id"] == asset_id), None)
        if not isinstance(source_asset, dict) or any(source_asset.get(key) != asset.get(key) for key in (
            "truth_sha256", "role", "purpose", "character_mode", "coverage",
        )):
            raise ValueError("candidate_repair_base_truth_mismatch")
        review_ref = source_asset.get("candidate_self_check")
        if not isinstance(review_ref, dict):
            raise ValueError("candidate_repair_base_requires_observations")
        base_review_raw = read_relative_regular_file_once(source_dir, review_ref["relative_path"], max_bytes=1024 * 1024, label="repair base review")
        if hashlib.sha256(base_review_raw).hexdigest() != review_ref["sha256"]:
            raise ValueError("candidate_repair_base_review_changed")
        base_review = json.loads(base_review_raw)
        base_problems = validate_candidate_self_check(base_review, payload=source_plan, asset_id=asset_id, base_dir=source_dir)
        if base_problems not in ([], ["candidate_self_check_requires_repair"]):
            raise ValueError("candidate_repair_base_review_invalid")
        base_failed = {item["check_id"] for item in base_review["assets"][0]["observations"] if item["result"] == "fail"}
        failed.update(base_failed)
    if asset.get("candidate_repair_source") and (
        base_plan_binding is None or source_asset.get("generated_pixel_sha256") == asset.get("generated_pixel_sha256")
    ):
        raise ValueError("candidate_repair_chain_requires_best_base_or_fresh_generation")
    if (not isinstance(changes, list) or not changes or len(changes) > len(failed)
        or any(not isinstance(item, dict) or set(item) != {"check_id", "instruction"}
               or not isinstance(item.get("check_id"), str) or item["check_id"] not in failed
               or not isinstance(item.get("instruction"), str) or not 12 <= len(item["instruction"].strip()) <= 4096 for item in changes)
        or len({item["check_id"] for item in changes}) != len(changes)):
        raise ValueError("candidate_repair_changes_must_target_observed_failures")
    if not base_failed.issubset({item["check_id"] for item in changes}):
        raise ValueError("candidate_repair_changes_must_cover_base_defects")
    relative_image = (source_dir / source_asset["generated_file"]).relative_to(root).as_posix()
    image_raw = read_relative_regular_file_once(root, relative_image, max_bytes=MAX_RASTER_FILE_BYTES, label="candidate repair image")
    if hashlib.sha256(image_raw).hexdigest() != source_asset["generated_sha256"]:
        raise ValueError("candidate_repair_image_changed")
    result = {
        "contract_id": "candidate_repair_source_v1", "project_id": plan["project_id"],
        "asset_id": asset_id, "truth_sha256": asset["truth_sha256"],
        "source_plan": copy.deepcopy(visual_plan_binding),
        "source_image": {"relative_path": relative_image, "sha256": source_asset["generated_sha256"], "pixel_sha256": source_asset["generated_pixel_sha256"]},
        "self_check": {"relative_path": (base / review_binding["relative_path"]).relative_to(root).as_posix(), "sha256": review_binding["sha256"]},
        "changes": copy.deepcopy(changes),
    }
    if base_plan_binding is not None:
        result["base_plan"] = copy.deepcopy(base_plan_binding)
    return result


def validate_visual_review_manifest(
    manifest: Any,
    *,
    payload: dict[str, Any],
    evidence_by_asset: dict[str, dict[str, Any]],
    truth_locked_at: str,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    root_fields = {
        "schema_version",
        "ruleset",
        "review_subject_sha256",
        "reviewed_at",
        "reviewer_type",
        "reviewer_id",
        "review_task_id",
        "assets",
    }
    scoped_fields = root_fields | {"scope_asset_ids"}
    if not isinstance(manifest, dict) or frozenset(manifest) not in {
        frozenset(root_fields),
        frozenset(scoped_fields),
    }:
        return {}, "manifest_shape"
    version = manifest.get("schema_version")
    scope_asset_ids = manifest.get("scope_asset_ids")
    is_scoped = version in {SCOPED_VISUAL_REVIEW_MANIFEST_VERSION, LOCAL_VISUAL_REVIEW_MANIFEST_VERSION}
    if is_scoped:
        if (
            not isinstance(scope_asset_ids, list)
            or not scope_asset_ids
            or len(scope_asset_ids) != len(set(scope_asset_ids))
            or not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in scope_asset_ids)
        ):
            return {}, "manifest_scope"
    elif "scope_asset_ids" in manifest:
        return {}, "manifest_scope_version"
    subject_hash = visual_review_subject_sha256(
        payload,
        scope_asset_ids=scope_asset_ids if is_scoped else None,
        asset_local=version == LOCAL_VISUAL_REVIEW_MANIFEST_VERSION,
    )
    root_checks = {
        "manifest_version": version
        in {VISUAL_REVIEW_MANIFEST_VERSION, SCOPED_VISUAL_REVIEW_MANIFEST_VERSION, LOCAL_VISUAL_REVIEW_MANIFEST_VERSION},
        "manifest_ruleset": manifest.get("ruleset") == VISUAL_QA_RULESET,
        "manifest_subject": manifest.get("review_subject_sha256") == subject_hash,
        "manifest_timestamp": timestamp_in_review_window(
            manifest.get("reviewed_at"),
            not_before=truth_locked_at,
        ),
        "manifest_reviewer_type": manifest.get("reviewer_type")
        in {"human", "independent_ai", "authorized_reviewer", "executor"},
        "manifest_reviewer_id": isinstance(manifest.get("reviewer_id"), str)
        and ID_RE.fullmatch(manifest["reviewer_id"]) is not None,
        "manifest_review_task_id": isinstance(manifest.get("review_task_id"), str)
        and ID_RE.fullmatch(manifest["review_task_id"]) is not None,
        "manifest_assets": isinstance(manifest.get("assets"), list),
    }
    root_problem = next((key for key, passed in root_checks.items() if not passed), None)
    if root_problem:
        return {}, root_problem

    required_assets = [
        asset
        for asset in payload.get("assets", [])
        if isinstance(asset, dict) and asset.get("required") is True
    ]
    all_required_ids = sorted(str(asset.get("asset_id")) for asset in required_assets)
    if is_scoped and not set(scope_asset_ids).issubset(all_required_ids):
        return {}, "manifest_scope_unknown_asset"
    required_ids = sorted(scope_asset_ids) if is_scoped else all_required_ids
    entries = manifest["assets"]
    entry_ids = [entry.get("asset_id") for entry in entries if isinstance(entry, dict)]
    if len(entry_ids) != len(entries) or sorted(entry_ids) != required_ids or duplicate_values(entry_ids):
        return {}, "manifest_asset_coverage"
    asset_map = {str(asset["asset_id"]): asset for asset in required_assets}
    entry_map: dict[str, dict[str, Any]] = {}
    entry_fields = {
        "asset_id",
        "role",
        "file_sha256",
        "pixel_sha256",
        "truth_sha256",
        "rubric_id",
        "rubric",
        "decision",
        "notes",
    }
    rubric_fields = {
        "truth_and_role_match",
        "coverage_and_continuity_match",
        "composition_readable",
        "artifact_free",
        "downstream_use_fit",
    }
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) not in (entry_fields, entry_fields | {"probe_resolution"}):
            return {}, "manifest_entry_shape"
        asset_id = str(entry["asset_id"])
        asset = asset_map[asset_id]
        evidence = evidence_by_asset.get(asset_id)
        rubric = entry.get("rubric")
        resolution = entry.get("probe_resolution")
        if "probe_resolution" in entry and (
            asset.get("role") != "character_identity_reference"
            or asset.get("identity_kind", "human") != "human"
            or asset.get("character_mode") not in {"headed_master", "headed_state"}
            or not isinstance(resolution, dict) or set(resolution) != {"receipt_sha256", "observed"}
            or not isinstance(resolution.get("receipt_sha256"), str)
            or not SHA256_RE.fullmatch(resolution["receipt_sha256"])
            or not isinstance(resolution.get("observed"), str) or len(resolution["observed"].strip()) < 20
        ):
            return {}, f"manifest_probe_resolution_invalid:{asset_id}"
        checks = {
            "manifest_entry_evidence": evidence is not None,
            "manifest_entry_role": entry.get("role") == asset.get("role"),
            "manifest_entry_file_hash": evidence is not None
            and entry.get("file_sha256") == evidence["sha256"],
            "manifest_entry_pixel_hash": evidence is not None
            and entry.get("pixel_sha256") == evidence["pixel_sha256"],
            "manifest_entry_truth_hash": entry.get("truth_sha256")
            == asset.get("truth_sha256"),
            "manifest_entry_rubric_id": entry.get("rubric_id")
            == visual_review_rubric_id(str(asset.get("role"))),
            "manifest_entry_rubric": isinstance(rubric, dict)
            and set(rubric) == rubric_fields
            and all(rubric.get(field) is True for field in rubric_fields),
            "manifest_entry_decision": entry.get("decision") == "pass",
            "manifest_entry_notes": isinstance(entry.get("notes"), str)
            and len(entry["notes"].strip()) >= 12,
        }
        problem = next((key for key, passed in checks.items() if not passed), None)
        if problem:
            return {}, f"{problem}:{asset_id}"
        entry_map[asset_id] = entry
    return entry_map, None


def character_probe_resolved_by_review(
    asset: dict[str, Any], probe_receipt: Any, *, base_dir: Path,
) -> bool:
    """Resolve a valid detector disagreement in the existing batch review.

    Callers must still validate the full QA manifest/authority. This never turns
    the detector result into pass and cannot excuse a missing/tampered probe,
    transparent image or headless source requirement.
    """
    if (asset.get("character_mode") not in {"headed_master", "headed_state"}
        or not isinstance(probe_receipt, dict) or probe_receipt.get("status") != "blocked"
        or probe_receipt.get("image_sha256") != asset.get("generated_sha256")
        or probe_receipt.get("asset_truth_sha256") != asset.get("truth_sha256")):
        return False
    from dircreative_character_master_visual_gate import character_master_alpha_errors
    alpha = probe_receipt.get("raster_alpha")
    if not isinstance(alpha, dict) or character_master_alpha_errors(alpha):
        return False
    qa = asset.get("visual_qa_receipt")
    if not isinstance(qa, dict):
        return False
    try:
        raw = read_relative_regular_file_once(base_dir, qa["review_manifest_file"], max_bytes=8 * 1024 * 1024, label="character batch review")
        if hashlib.sha256(raw).hexdigest() != qa["review_manifest_sha256"]:
            return False
        manifest = json.loads(raw)
        entry = next(item for item in manifest["assets"] if item["asset_id"] == asset["asset_id"])
        resolution = entry.get("probe_resolution", {})
        return (isinstance(resolution, dict)
                and isinstance(probe_receipt.get("receipt_sha256"), str)
                and entry.get("decision") == "pass"
                and entry.get("file_sha256") == asset.get("generated_sha256")
                and entry.get("truth_sha256") == asset.get("truth_sha256")
                and resolution.get("receipt_sha256") == probe_receipt.get("receipt_sha256")
                and isinstance(resolution.get("observed"), str) and len(resolution["observed"].strip()) >= 20)
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return False


def validate_visual_qa_receipt(
    receipt: Any,
    *,
    asset: dict[str, Any],
    evidence: dict[str, Any],
    truth_locked_at: str,
    base_dir: Path,
    payload: dict[str, Any],
    evidence_by_asset: dict[str, dict[str, Any]],
    manifest_cache: dict[str, tuple[dict[str, Any], dict[str, dict[str, Any]], str | None]],
) -> str | None:
    expected_fields = {
        "receipt_version",
        "asset_id",
        "file_sha256",
        "pixel_sha256",
        "truth_sha256",
        "ruleset",
        "reviewed_at",
        "reviewer_type",
        "reviewer_id",
        "review_task_id",
        "review_manifest_file",
        "review_manifest_sha256",
        "review_subject_sha256",
        "status",
        "receipt_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_fields:
        return "shape"
    checks = {
        "version": receipt.get("receipt_version") == VISUAL_QA_RECEIPT_VERSION,
        "asset": receipt.get("asset_id") == asset.get("asset_id"),
        "file_hash": receipt.get("file_sha256") == evidence["sha256"],
        "pixel_hash": receipt.get("pixel_sha256") == evidence["pixel_sha256"],
        "truth_hash": receipt.get("truth_sha256") == asset.get("truth_sha256"),
        "ruleset": receipt.get("ruleset") == VISUAL_QA_RULESET,
        "timestamp": timestamp_in_review_window(
            receipt.get("reviewed_at"),
            not_before=truth_locked_at,
        ),
        "reviewer_type": receipt.get("reviewer_type")
        in {"human", "independent_ai", "authorized_reviewer", "executor"},
        "reviewer_id": isinstance(receipt.get("reviewer_id"), str)
        and ID_RE.fullmatch(receipt["reviewer_id"]) is not None,
        "review_task_id": isinstance(receipt.get("review_task_id"), str)
        and ID_RE.fullmatch(receipt["review_task_id"]) is not None,
        "review_manifest_file": isinstance(receipt.get("review_manifest_file"), str)
        and bool(receipt["review_manifest_file"]),
        "review_manifest_sha256": isinstance(receipt.get("review_manifest_sha256"), str)
        and SHA256_RE.fullmatch(receipt["review_manifest_sha256"]) is not None,
        "status": receipt.get("status") == "visual_qa_pass",
        "receipt_hash": receipt.get("receipt_sha256") == receipt_sha256(receipt),
    }
    basic_problem = next((key for key, passed in checks.items() if not passed), None)
    if basic_problem:
        return basic_problem
    manifest_path = contained_file(receipt["review_manifest_file"], base_dir)
    if manifest_path is None:
        return "review_manifest_missing_or_outside_evidence_root"
    try:
        manifest, manifest_hash = load_json_snapshot(manifest_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return "review_manifest_invalid_json"
    if receipt.get("review_manifest_sha256") != manifest_hash:
        return "review_manifest_hash"
    scope_asset_ids = (
        manifest.get("scope_asset_ids")
        if manifest.get("schema_version") in {SCOPED_VISUAL_REVIEW_MANIFEST_VERSION, LOCAL_VISUAL_REVIEW_MANIFEST_VERSION}
        else None
    )
    expected_subject = visual_review_subject_sha256(
        payload,
        scope_asset_ids=scope_asset_ids,
        asset_local=manifest.get("schema_version") == LOCAL_VISUAL_REVIEW_MANIFEST_VERSION,
    )
    if receipt.get("review_subject_sha256") != expected_subject:
        return "review_subject"
    cache_key = f"{manifest_path}:{manifest_hash}"
    if cache_key not in manifest_cache:
        entry_map, manifest_problem = validate_visual_review_manifest(
            manifest,
            payload=payload,
            evidence_by_asset=evidence_by_asset,
            truth_locked_at=truth_locked_at,
        )
        manifest_cache[cache_key] = (manifest, entry_map, manifest_problem)
    manifest, entry_map, manifest_problem = manifest_cache[cache_key]
    if manifest_problem:
        return manifest_problem
    if any(
        receipt.get(field) != manifest.get(field)
        for field in (
            "reviewed_at",
            "reviewer_type",
            "reviewer_id",
            "review_task_id",
        )
    ):
        return "review_manifest_identity"
    entry = entry_map.get(str(asset.get("asset_id")))
    if entry is None:
        return "review_manifest_asset_missing"
    if any(
        receipt.get(receipt_field) != entry.get(entry_field)
        for receipt_field, entry_field in (
            ("asset_id", "asset_id"),
            ("file_sha256", "file_sha256"),
            ("pixel_sha256", "pixel_sha256"),
            ("truth_sha256", "truth_sha256"),
        )
    ):
        return "review_manifest_asset_binding"
    return None


def candidate_visual_review_errors(
    payload: dict[str, Any], *, asset_id: str, base_dir: Path,
) -> list[str]:
    """Read existing review evidence, never create a review or grant adoption."""
    try:
        assets = {row["asset_id"]: row for row in payload["assets"]}
        asset = assets[asset_id]
        receipt = asset["visual_qa_receipt"]
        raw = read_relative_regular_file_once(
            base_dir, receipt["review_manifest_file"], max_bytes=8 * 1024 * 1024,
            label="candidate batch review",
        )
        if hashlib.sha256(raw).hexdigest() != receipt["review_manifest_sha256"]:
            return ["candidate_visual_review_manifest_changed"]
        manifest = json.loads(raw)
        evidence_map = {}
        for entry in manifest["assets"]:
            row = assets[entry["asset_id"]]
            path = contained_file(row.get("generated_file"), base_dir)
            evidence, reason = inspect_raster(path) if path else (None, "missing")
            if evidence is None or row.get("generated_sha256") != evidence["sha256"] or row.get("generated_pixel_sha256") != evidence["pixel_sha256"]:
                return ["candidate_visual_review_pixels_changed:" + str(reason or row["asset_id"])]
            problem = validate_technical_receipt(
                row.get("technical_receipt"), asset_id=row["asset_id"], evidence=evidence,
                truth_locked_at=str(payload["truth_locked_at"]),
            )
            if problem:
                return ["candidate_visual_review_technical_invalid:" + problem]
            evidence_map[row["asset_id"]] = evidence
        problem = validate_visual_qa_receipt(
            receipt, asset=asset, evidence=evidence_map[asset_id],
            truth_locked_at=str(payload["truth_locked_at"]), base_dir=base_dir,
            payload=payload, evidence_by_asset=evidence_map, manifest_cache={},
        )
        return ["candidate_visual_review_invalid:" + problem] if problem else []
    except (OSError, ValueError, KeyError, TypeError):
        return ["candidate_visual_review_unreadable"]


def test_png_bytes(
    seed: int = 0,
    width: int = MIN_RASTER_WIDTH,
    height: int = MIN_RASTER_HEIGHT,
) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    rows = []
    for y in range(height):
        pixel = bytes(
            (
                (seed * 17 + y) % 251,
                (seed * 29 + y * 3) % 253,
                (seed * 43 + y * 7) % 255,
            )
        )
        rows.append(b"\x00" + pixel * width)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows), level=1))
        + chunk(b"IEND", b"")
    )


def padded_fake_png_bytes(width: int = 1920, height: int = 1080) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"X" * 5000
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def png_with_text_metadata(data: bytes, key: str, value: str) -> bytes:
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or not data.endswith(
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    ):
        raise ValueError("metadata test requires a canonical PNG")
    payload = key.encode("latin-1") + b"\x00" + value.encode("latin-1")
    kind = b"tEXt"
    chunk = (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )
    return data[:-12] + chunk + data[-12:]


def png_with_trns_chunk(data: bytes) -> bytes:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("tRNS test requires a PNG")
    offset = 8
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        if kind == b"IDAT":
            payload = b"\x00\x00\x00\x00\x00\x00"
            chunk = (
                struct.pack(">I", len(payload))
                + b"tRNS"
                + payload
                + struct.pack(">I", zlib.crc32(b"tRNS" + payload) & 0xFFFFFFFF)
            )
            return data[:offset] + chunk + data[offset:]
        offset += length + 12
    raise ValueError("tRNS test PNG has no IDAT chunk")


def empty_coverage() -> dict[str, list[str]]:
    return {
        "scene_ids": [],
        "character_ids": [],
        "appearance_state_ids": [],
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
    truth_payload: Any,
    coverage: dict[str, list[str]],
    inherits_from: list[str],
    action: str = "generate",
    planning_only: bool = True,
    compile_route: str = "direct_concise",
    identity_kind: str = "human",
) -> dict[str, Any]:
    asset = {
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
        "generated_file": "",
        "generated_sha256": "",
        "generated_pixel_sha256": "",
        "generated_perceptual_hash": "",
        "truth_sha256": canonical_json_sha256(truth_payload),
        "technical_receipt": None,
        "visual_qa_receipt": None,
        "compile_route": compile_route,
    }
    if role == "character_identity_reference":
        contract = {
            "character_mode": "headed_master",
            "identity_kind": identity_kind,
            "derived_from_asset_id": None,
            "approved_source_master_sha256": None,
            "coverage": coverage,
            "inherits_from": inherits_from,
            "purpose": purpose,
        }
        asset.update(contract)
        asset["character_contract_sha256"] = canonical_json_sha256(contract)
    return asset


def validate_delivery_profile(
    profile: Any,
    errors: list[str],
    *,
    asset_only: bool = False,
) -> None:
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
    if medium not in {"broadcast_tvc", "cinema", "web", "social", "other", "still"}:
        errors.append("delivery_profile_medium_invalid")
    aspect_ratio = profile.get("aspect_ratio")
    ratio_match = re.fullmatch(
        r"([0-9]+(?:\.[0-9]+)?):([0-9]+(?:\.[0-9]+)?)",
        str(aspect_ratio),
    )
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
    if asset_only and frame_rate is not None:
        errors.append("asset_only_frame_rate_must_be_null")
    elif not asset_only and (
        not isinstance(frame_rate, (int, float)) or isinstance(frame_rate, bool) or frame_rate <= 0
    ):
        errors.append("delivery_profile_frame_rate_invalid")
    audio_rate = profile.get("audio_sample_rate_hz")
    if asset_only and audio_rate is not None:
        errors.append("asset_only_audio_rate_must_be_null")
    elif not asset_only and (
        not isinstance(audio_rate, int) or isinstance(audio_rate, bool) or audio_rate <= 0
    ):
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
    if asset_only:
        if medium != "still":
            errors.append("asset_only_requires_still_medium")
        if endframe != 0:
            errors.append("asset_only_brand_endframe_must_be_zero")
    if medium == "broadcast_tvc":
        if aspect_ratio != "16:9":
            errors.append("broadcast_tvc_requires_16_9")
        if not isinstance(width, int) or not isinstance(height, int) or width < 1920 or height < 1080:
            errors.append("broadcast_tvc_raster_below_1080")
        elif abs(width / height - 16 / 9) > 0.01:
            errors.append("broadcast_tvc_raster_ratio_mismatch")
        if audio_rate != 48000:
            errors.append("broadcast_tvc_audio_must_be_48khz")
        if not isinstance(endframe, (int, float)) or endframe <= 0:
            errors.append("broadcast_tvc_brand_endframe_missing")


def parse_timecode_range(value: str) -> tuple[Decimal, Decimal]:
    match = TIMECODE_RANGE_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("shot card timecode format is invalid")
    try:
        start = Decimal(match.group("start_minutes")) * 60 + Decimal(
            match.group("start_seconds")
        )
        end = Decimal(match.group("end_minutes")) * 60 + Decimal(
            match.group("end_seconds")
        )
    except InvalidOperation as exc:
        raise ValueError("shot card timecode format is invalid") from exc
    if end <= start:
        raise ValueError("shot card timecode range is not positive")
    return start, end


def timecode_seconds(value: str) -> float:
    minutes, seconds = value.split(":", 1)
    return int(minutes) * 60 + float(seconds)


def validate_shot_card_timeline(
    cards: list[dict[str, Any]],
    *,
    duration_seconds: int | float,
    frame_rate_fps: int | float,
) -> None:
    tolerance = Decimal("0.000001")
    expected_start = Decimal(0)
    frame_rate = Decimal(str(frame_rate_fps))
    total_duration = Decimal(str(duration_seconds))

    def close(left: Decimal, right: Decimal) -> bool:
        return abs(left - right) <= tolerance

    def frame_aligned(value: Decimal) -> bool:
        frames = value * frame_rate
        return close(frames, frames.to_integral_value())

    for card in cards:
        shot_id = str(card.get("shot_id"))
        start, end = parse_timecode_range(str(card.get("timecode")))
        card_duration = Decimal(str(card.get("duration_seconds")))
        if not close(start, expected_start):
            raise ValueError(f"shot card timeline is discontinuous at {shot_id}")
        if not close(end - start, card_duration):
            raise ValueError(f"shot card timecode and duration disagree at {shot_id}")
        if not all(frame_aligned(value) for value in (start, end, card_duration)):
            raise ValueError(f"shot card timeline is not frame aligned at {shot_id}")
        expected_start = end
    if not close(expected_start, total_duration):
        raise ValueError("shot card timeline does not end at inventory duration")


def parse_inventory(
    inventory: dict[str, Any],
    *,
    base_dir: Path,
) -> dict[str, Any]:
    required = {
        "schema_version",
        "project_id",
        "truth_revision",
        "truth_locked_at",
        "creative_source_file",
        "creative_source_sha256",
        "shot_cards_file",
        "shot_cards_sha256",
        "scope",
        "duration_seconds",
        "delivery_profile",
        "characters",
        "appearance_states",
        "products",
        "props",
        "scenes",
        "shots",
        "rhythm_points",
        "style_reference_required",
        "generation_units",
    }
    if (
        not required.issubset(inventory)
        or set(inventory) - required - {"style_compile_route", "existing_sources"}
        or inventory.get("schema_version") != SCHEMA_VERSION
    ):
        raise ValueError("visual asset inventory field set or version is invalid")
    if inventory.get("style_compile_route", "direct_concise") not in {
        "direct_concise",
        "selected_skill_handoff",
    }:
        raise ValueError("inventory style compile route is invalid")
    for field in ("project_id", "truth_revision"):
        if not isinstance(inventory.get(field), str) or not ID_RE.fullmatch(inventory[field]):
            raise ValueError(f"inventory {field} is invalid")
    if inventory.get("scope") not in {"whole_film", "sequence", "representative_sample", "asset_only"}:
        raise ValueError("inventory scope is invalid")
    asset_only = inventory.get("scope") == "asset_only"
    truth_locked_at = inventory.get("truth_locked_at")
    if (
        not valid_utc_timestamp(truth_locked_at)
        or parsed_utc_timestamp(truth_locked_at) is None
        or parsed_utc_timestamp(truth_locked_at).timestamp()
        > datetime.now(timezone.utc).timestamp() + FUTURE_TIMESTAMP_TOLERANCE_SECONDS
    ):
        raise ValueError("inventory truth_locked_at is invalid")
    shot_cards_path = contained_file(inventory.get("shot_cards_file"), base_dir)
    if shot_cards_path is None:
        raise ValueError("inventory shot cards are missing or outside the evidence root")
    shot_cards = load_json(shot_cards_path)
    actual_shot_cards_hash = canonical_json_sha256(shot_cards)
    if inventory.get("shot_cards_sha256") != actual_shot_cards_hash:
        raise ValueError("inventory shot_cards_sha256 mismatch")
    if (
        not isinstance(inventory.get("shot_cards_sha256"), str)
        or SHA256_RE.fullmatch(inventory["shot_cards_sha256"]) is None
    ):
        raise ValueError("inventory shot_cards_sha256 is invalid")
    creative_source_path = contained_file(inventory.get("creative_source_file"), base_dir)
    if creative_source_path is None:
        raise ValueError("inventory creative source is missing or outside the evidence root")
    creative_source = load_json(creative_source_path)
    actual_creative_source_hash = canonical_json_sha256(creative_source)
    if inventory.get("creative_source_sha256") != actual_creative_source_hash:
        raise ValueError("inventory creative_source_sha256 mismatch")
    if (
        not isinstance(inventory.get("creative_source_sha256"), str)
        or SHA256_RE.fullmatch(inventory["creative_source_sha256"]) is None
    ):
        raise ValueError("inventory creative_source_sha256 is invalid")
    if (
        set(creative_source) != {"schema_version", "project_id", "brief", "story_beats", "script_lines"}
        or creative_source.get("schema_version") != "1.0"
        or creative_source.get("project_id") != inventory.get("project_id")
        or not isinstance(creative_source.get("brief"), dict)
        or not creative_source["brief"]
    ):
        raise ValueError("creative source root is invalid")

    def creative_item_map(
        label: str,
        fields: set[str],
        *,
        allow_empty: bool = False,
    ) -> dict[str, dict[str, Any]]:
        values = creative_source.get(label)
        if not isinstance(values, list) or (not values and not allow_empty):
            raise ValueError(f"creative source {label} must be a non-empty list")
        mapped: dict[str, dict[str, Any]] = {}
        for item in values:
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError(f"creative source {label} item is invalid")
            item_id = item.get("id")
            if not isinstance(item_id, str) or not ID_RE.fullmatch(item_id) or item_id in mapped:
                raise ValueError(f"creative source {label} id is invalid")
            for field in fields - {"id"}:
                value = item.get(field)
                if not isinstance(value, str) or len(value.strip()) < 2 or PLACEHOLDER_RE.search(value):
                    raise ValueError(f"creative source {label} {item_id} has invalid {field}")
            mapped[item_id] = item
        return mapped

    story_beat_map = creative_item_map(
        "story_beats", {"id", "summary"}, allow_empty=asset_only
    )
    script_line_map = creative_item_map(
        "script_lines", {"id", "speaker", "text"}, allow_empty=asset_only
    )
    if (
        set(shot_cards) != {"schema_version", "inventory", "cards"}
        or shot_cards.get("schema_version") != "1.0"
        or not isinstance(shot_cards.get("inventory"), str)
    ):
        raise ValueError("shot cards root is invalid")
    duration = inventory.get("duration_seconds")
    if asset_only and duration is not None:
        raise ValueError("asset_only duration must be null")
    if not asset_only and (
        not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0
    ):
        raise ValueError("inventory duration is invalid")
    profile_errors: list[str] = []
    validate_delivery_profile(
        inventory.get("delivery_profile"), profile_errors, asset_only=asset_only
    )
    if profile_errors:
        raise ValueError("inventory delivery profile is invalid: " + ",".join(profile_errors))
    if not isinstance(inventory.get("style_reference_required"), bool):
        raise ValueError("inventory style-reference policy is invalid")
    raw_rhythm_points = inventory.get("rhythm_points")
    if not isinstance(raw_rhythm_points, list) or (not raw_rhythm_points and not asset_only):
        raise ValueError("inventory rhythm points are invalid")
    rhythm_ids: list[str] = []
    for point in raw_rhythm_points:
        if not isinstance(point, dict) or set(point) != {
            "id",
            "timecode",
            "shot_ids",
            "action",
            "sound_transition",
        }:
            raise ValueError("inventory rhythm point item is invalid")
        point_id = point.get("id")
        if not isinstance(point_id, str) or not ID_RE.fullmatch(point_id) or point_id in rhythm_ids:
            raise ValueError("inventory rhythm point id is invalid")
        if (
            not isinstance(point.get("timecode"), str)
            or re.fullmatch(r"[0-9]{2,}:[0-5][0-9](?:\.[0-9]+)?", point["timecode"]) is None
        ):
            raise ValueError(f"inventory rhythm point {point_id} timecode is invalid")
        for field in ("action", "sound_transition"):
            value = point.get(field)
            if not isinstance(value, str) or len(value.strip()) < 12 or PLACEHOLDER_RE.search(value):
                raise ValueError(f"inventory rhythm point {point_id} {field} is invalid")
        rhythm_ids.append(point_id)

    def entity_map(label: str) -> dict[str, dict[str, Any]]:
        values = inventory.get(label)
        if not isinstance(values, list):
            raise ValueError(f"inventory {label} must be a list")
        result: dict[str, dict[str, Any]] = {}
        for item in values:
            if (
                not isinstance(item, dict)
                or not {"id", "purpose"}.issubset(item)
                or set(item) - ({"id", "purpose", "compile_route", "identity_kind"} if label == "characters" else {"id", "purpose", "compile_route"})
            ):
                raise ValueError(f"inventory {label} item is invalid")
            entity_id = item.get("id")
            purpose = item.get("purpose")
            if (
                not isinstance(entity_id, str)
                or not ID_RE.fullmatch(entity_id)
                or entity_id in result
                or not isinstance(purpose, str)
                or len(purpose.strip()) < 12
                or PLACEHOLDER_RE.search(purpose)
            ):
                raise ValueError(f"inventory {label} identity or purpose is invalid")
            if item.get("compile_route", "direct_concise") not in {
                "direct_concise",
                "selected_skill_handoff",
            }:
                raise ValueError(f"inventory {label} compile route is invalid")
            if label == "characters":
                identity_kind = item.get("identity_kind", "human")
                if identity_kind not in IDENTITY_KINDS:
                    raise ValueError("inventory character identity_kind is invalid")
            result[entity_id] = item
        return result

    character_map = entity_map("characters")
    raw_appearance_states = inventory.get("appearance_states")
    if not isinstance(raw_appearance_states, list) or (
        not raw_appearance_states and character_map
    ):
        raise ValueError("inventory appearance_states must be a non-empty list for characters")
    appearance_state_map: dict[str, dict[str, Any]] = {}
    for item in raw_appearance_states:
        if not isinstance(item, dict) or set(item) != {"id", "character_id", "purpose"}:
            raise ValueError("inventory appearance state item is invalid")
        state_id = item.get("id")
        purpose = item.get("purpose")
        if (
            not isinstance(state_id, str)
            or not ID_RE.fullmatch(state_id)
            or state_id in appearance_state_map
            or item.get("character_id") not in character_map
            or not isinstance(purpose, str)
            or len(purpose.strip()) < 12
            or PLACEHOLDER_RE.search(purpose)
        ):
            raise ValueError("inventory appearance state identity or purpose is invalid")
        appearance_state_map[state_id] = item
    if set(character_map) - {item["character_id"] for item in appearance_state_map.values()}:
        raise ValueError("inventory character lacks an appearance state")
    product_map = entity_map("products")
    prop_map = entity_map("props")
    scene_map = entity_map("scenes")

    if asset_only:
        if (
            inventory.get("shots") != []
            or raw_rhythm_points != []
            or inventory.get("generation_units") != []
            or shot_cards.get("cards") != []
            or story_beat_map
            or script_line_map
        ):
            raise ValueError("asset_only inventory cannot declare film timeline content")
        if not (character_map or product_map or prop_map or scene_map):
            raise ValueError("asset_only inventory requires at least one asset entity")
        return {
            "character_map": character_map,
            "appearance_state_map": appearance_state_map,
            "product_map": product_map,
            "prop_map": prop_map,
            "scene_map": scene_map,
            "unit_map": {},
            "shot_map": {},
            "shot_ids": [],
            "shot_cards": shot_cards,
            "shot_cards_sha256": actual_shot_cards_hash,
            "shot_truth": [],
            "shot_truth_sha256": canonical_json_sha256([]),
            "creative_source": creative_source,
            "creative_source_sha256": actual_creative_source_hash,
            "rhythm_points": [],
        }

    raw_units = inventory.get("generation_units")
    if not isinstance(raw_units, list) or not raw_units:
        raise ValueError("inventory generation_units must be a non-empty list")
    unit_map: dict[str, dict[str, Any]] = {}
    for unit in raw_units:
        expected = {
            "unit_id",
            "shot_ids",
            "direct_input_min",
            "direct_input_max",
            "direct_input_roles",
            "direct_input_not_required_reason",
        }
        if not isinstance(unit, dict) or set(unit) - {"storyboard_strategy", "storyboard_acquisition"} != expected:
            raise ValueError("inventory generation unit is invalid")
        unit_id = unit.get("unit_id")
        shot_ids = unit.get("shot_ids")
        minimum = unit.get("direct_input_min")
        maximum = unit.get("direct_input_max")
        roles = unit.get("direct_input_roles")
        reason = unit.get("direct_input_not_required_reason")
        storyboard_strategy = unit.get("storyboard_strategy", "individual_frames")
        if (
            not isinstance(unit_id, str)
            or not ID_RE.fullmatch(unit_id)
            or unit_id in unit_map
            or not isinstance(shot_ids, list)
            or not shot_ids
            or not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in shot_ids)
            or duplicate_values(shot_ids)
        ):
            raise ValueError("inventory generation unit identity or shots are invalid")
        if (
            not isinstance(minimum, int)
            or isinstance(minimum, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or not 0 <= minimum <= maximum
        ):
            raise ValueError(f"inventory generation unit {unit_id} input range is invalid")
        if (
            not isinstance(roles, list)
            or not all(role in DIRECT_ROLES for role in roles)
            or duplicate_values(roles)
            or not isinstance(reason, str)
            or storyboard_strategy not in STORYBOARD_STRATEGIES
            or not isinstance(unit.get("storyboard_acquisition", "native_generate"), str)
            or unit.get("storyboard_acquisition", "native_generate") not in STORYBOARD_ACQUISITIONS
            or ("storyboard_acquisition" in unit and storyboard_strategy != "annotated_reference")
        ):
            raise ValueError(f"inventory generation unit {unit_id} input strategy is invalid")
        if maximum > 0 and not roles:
            raise ValueError(f"inventory generation unit {unit_id} has no allowed input role")
        if minimum > 0 and reason.strip():
            raise ValueError(f"inventory generation unit {unit_id} has a contradictory no-input reason")
        if minimum == 0 and len(reason.strip()) < 12:
            raise ValueError(f"inventory generation unit {unit_id} needs a no-input reason")
        unit_map[unit_id] = unit

    raw_shots = inventory.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("inventory shots must be a non-empty list")
    shot_map: dict[str, dict[str, Any]] = {}
    shot_ids: list[str] = []
    for shot in raw_shots:
        expected = {
            "shot_id",
            "scene_id",
            "character_ids",
            "appearance_state_ids",
            "product_ids",
            "prop_ids",
            "story_beat_ids",
            "script_line_ids",
            "generation_unit_id",
            "narrative_purpose",
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
            ("appearance_state_ids", appearance_state_map),
            ("product_ids", product_map),
            ("prop_ids", prop_map),
        ):
            values = shot.get(field)
            if (
                not isinstance(values, list)
                or not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in values)
                or duplicate_values(values)
                or set(values) - set(known)
            ):
                raise ValueError(f"inventory shot {shot_id} has invalid {field}")
        appearance_characters = [
            appearance_state_map[state_id]["character_id"]
            for state_id in shot["appearance_state_ids"]
        ]
        if duplicate_values(appearance_characters) or set(appearance_characters) != set(shot["character_ids"]):
            raise ValueError(f"inventory shot {shot_id} appearance states do not map one-to-one to characters")
        for field, known in (
            ("story_beat_ids", story_beat_map),
            ("script_line_ids", script_line_map),
        ):
            values = shot.get(field)
            if (
                not isinstance(values, list)
                or (field == "story_beat_ids" and not values)
                or not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in values)
                or duplicate_values(values)
                or set(values) - set(known)
            ):
                raise ValueError(f"inventory shot {shot_id} has invalid {field}")
        purpose = shot.get("narrative_purpose")
        if (
            not isinstance(purpose, str)
            or len(purpose.strip()) < 12
            or PLACEHOLDER_RE.search(purpose)
        ):
            raise ValueError(f"inventory shot {shot_id} has no usable narrative purpose")
        shot_map[shot_id] = shot
        shot_ids.append(shot_id)

    raw_cards = shot_cards.get("cards")
    if not isinstance(raw_cards, list) or not raw_cards:
        raise ValueError("shot cards must contain a non-empty cards list")
    card_map: dict[str, dict[str, Any]] = {}
    card_ids: list[str] = []
    card_fields = {
        "shot_id",
        "timecode",
        "duration_seconds",
        "shot_design",
        "action",
        "sound_edit",
        "continuity_model",
    }
    for card in raw_cards:
        if not isinstance(card, dict) or set(card) - {"scene_state_source"} != card_fields:
            raise ValueError("shot card field set is invalid")
        shot_id = card.get("shot_id")
        duration_seconds = card.get("duration_seconds")
        if (
            not isinstance(shot_id, str)
            or not ID_RE.fullmatch(shot_id)
            or shot_id in card_map
            or not isinstance(card.get("timecode"), str)
            or TIMECODE_RANGE_RE.fullmatch(card["timecode"].strip()) is None
            or not isinstance(duration_seconds, (int, float))
            or isinstance(duration_seconds, bool)
            or duration_seconds <= 0
        ):
            raise ValueError("shot card identity, timecode, or duration is invalid")
        for field in ("shot_design", "action", "sound_edit", "continuity_model"):
            value = card.get(field)
            if (
                not isinstance(value, str)
                or len(value.strip()) < 12
                or PLACEHOLDER_RE.search(value)
            ):
                raise ValueError(f"shot card {shot_id} has invalid {field}")
        card_map[shot_id] = card
        card_ids.append(shot_id)
    if card_ids != shot_ids:
        raise ValueError("shot cards order or coverage does not match inventory shots")
    validate_shot_card_timeline(
        raw_cards,
        duration_seconds=duration,
        frame_rate_fps=inventory["delivery_profile"]["frame_rate_fps"],
    )
    covered_story_beats = {value for shot in raw_shots for value in shot["story_beat_ids"]}
    covered_script_lines = {value for shot in raw_shots for value in shot["script_line_ids"]}
    if covered_story_beats != set(story_beat_map):
        raise ValueError("inventory shots do not cover every creative story beat")
    if covered_script_lines != set(script_line_map):
        raise ValueError("inventory shots do not cover every approved script line")
    previous_rhythm_time = -1.0
    for point in raw_rhythm_points:
        point_shots = point.get("shot_ids")
        if (
            not isinstance(point_shots, list)
            or not point_shots
            or duplicate_values(point_shots)
            or not all(isinstance(item, str) and item in shot_map for item in point_shots)
        ):
            raise ValueError(f"inventory rhythm point {point['id']} has invalid shot coverage")
        point_time = timecode_seconds(point["timecode"])
        if point_time < previous_rhythm_time or point_time > float(duration):
            raise ValueError(f"inventory rhythm point {point['id']} is out of timeline order")
        previous_rhythm_time = point_time

    shot_truth = [
        {
            "shot_id": shot_id,
            "scene_id": shot_map[shot_id]["scene_id"],
            "character_ids": list(shot_map[shot_id]["character_ids"]),
            "appearance_state_ids": list(shot_map[shot_id]["appearance_state_ids"]),
            "product_ids": list(shot_map[shot_id]["product_ids"]),
            "prop_ids": list(shot_map[shot_id]["prop_ids"]),
            "story_beat_ids": list(shot_map[shot_id]["story_beat_ids"]),
            "script_line_ids": list(shot_map[shot_id]["script_line_ids"]),
            "generation_unit_id": shot_map[shot_id]["generation_unit_id"],
            "narrative_purpose": shot_map[shot_id]["narrative_purpose"],
            "timecode": card_map[shot_id]["timecode"],
            "duration_seconds": card_map[shot_id]["duration_seconds"],
            "shot_design": card_map[shot_id]["shot_design"],
            "action": card_map[shot_id]["action"],
            "sound_edit": card_map[shot_id]["sound_edit"],
            "continuity_model": card_map[shot_id]["continuity_model"],
            **({"scene_state_source": card_map[shot_id]["scene_state_source"]} if "scene_state_source" in card_map[shot_id] else {}),
        }
        for shot_id in shot_ids
    ]

    for truth in shot_truth:
        if "scene_state_source" not in truth:
            continue
        from dircreative_spatial_scene import contained, require_scene, sha256 as spatial_sha256
        source = truth["scene_state_source"]
        if not isinstance(source, dict) or set(source) != {"relative_path", "sha256"}:
            raise ValueError("shot scene_state_source must bind one scene file")
        scene_path = contained(base_dir, source["relative_path"])
        if spatial_sha256(scene_path) != source["sha256"]:
            raise ValueError("shot scene_state_source is stale")
        scene_state = load_json(scene_path)
        require_scene(scene_state)
        if scene_state["scene_id"] != truth["scene_id"] or truth["shot_id"] not in {c["shot_id"] for c in scene_state["cameras"]}:
            raise ValueError("shot scene_state_source scene or camera mismatch")

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
    missing_membership = sorted(set(shot_map) - set(declared_unit_for_shot))
    if missing_membership:
        raise ValueError(
            "inventory shots missing generation-unit membership: " + ",".join(missing_membership)
        )
    for unit_id, unit in unit_map.items():
        scene_ids = {shot_map[shot_id]["scene_id"] for shot_id in unit["shot_ids"]}
        if len(scene_ids) != 1:
            raise ValueError(
                f"inventory generation unit {unit_id} crosses scene anchors: "
                + ",".join(sorted(scene_ids))
            )
    if len(rhythm_ids) < len(shot_ids):
        raise ValueError("inventory rhythm points are fewer than shots")
    return {
        "character_map": character_map,
        "appearance_state_map": appearance_state_map,
        "product_map": product_map,
        "prop_map": prop_map,
        "scene_map": scene_map,
        "unit_map": unit_map,
        "shot_map": shot_map,
        "shot_ids": shot_ids,
        "shot_cards": shot_cards,
        "shot_cards_sha256": actual_shot_cards_hash,
        "shot_truth": shot_truth,
        "shot_truth_sha256": canonical_json_sha256(shot_truth),
        "creative_source": creative_source,
        "creative_source_sha256": actual_creative_source_hash,
        "rhythm_points": copy.deepcopy(raw_rhythm_points),
    }


def selected_input_shot(role: str, shot_ids: list[str], ordinal: int, total: int) -> str:
    if role == "clean_first_frame":
        return shot_ids[0]
    if role == "clean_end_frame":
        return shot_ids[-1]
    if len(shot_ids) == 1:
        return shot_ids[0]
    position = round((ordinal + 1) * (len(shot_ids) - 1) / (total + 1))
    return shot_ids[max(0, min(position, len(shot_ids) - 1))]


def _bind_existing_sources(assets: list[dict[str, Any]], raw_sources: Any, base_dir: Path) -> None:
    """Bind explicitly supplied PNGs into design truth without creating generation/QA events."""
    if not isinstance(raw_sources, list):
        raise ValueError("existing_sources must be a list")
    assets_by_id = {asset["asset_id"]: asset for asset in assets}
    seen: set[str] = set()
    root = base_dir.resolve(strict=True)
    for source in raw_sources:
        if not isinstance(source, dict) or set(source) != {"asset_id", "relative_path", "sha256"}:
            raise ValueError("existing_source field set is invalid")
        asset_id = source.get("asset_id")
        if not isinstance(asset_id, str) or asset_id in seen or asset_id not in assets_by_id:
            raise ValueError(f"existing_source asset is unknown or duplicated: {asset_id}")
        seen.add(asset_id)
        asset = assets_by_id[asset_id]
        if asset["role"] not in EXISTING_SOURCE_ROLES:
            raise ValueError(f"existing_source role is not reusable: {asset_id}")
        relative = source.get("relative_path")
        expected_hash = source.get("sha256")
        if (
            not isinstance(relative, str) or not relative or "\x00" in relative or "\\" in relative
            or Path(relative).is_absolute() or ".." in Path(relative).parts
            or not isinstance(expected_hash, str) or SHA256_RE.fullmatch(expected_hash) is None
        ):
            raise ValueError(f"existing_source path or hash is invalid: {asset_id}")

        def contained_source() -> Path:
            candidate = root
            for part in Path(relative).parts:
                candidate = candidate / part
                if candidate.is_symlink():
                    raise ValueError(f"existing_source symlink is forbidden: {asset_id}")
            path = contained_file(relative, root)
            if path is None:
                raise ValueError(f"existing_source file is missing or outside root: {asset_id}")
            return path

        path = contained_source()
        evidence, reason = inspect_raster(path)
        if evidence is None or evidence.get("format") != "PNG":
            raise ValueError(f"existing_source is not a valid PNG: {asset_id}: {reason}")
        # Inspecting and re-deriving must not silently adopt swapped source bytes.
        if evidence["sha256"] != expected_hash or sha256_file(contained_source()) != expected_hash:
            raise ValueError(f"existing_source hash mismatch: {asset_id}")
        asset["action"] = "reuse"
        asset["generated_file"] = relative
        asset["truth_sha256"] = canonical_json_sha256({
            "design_truth_sha256": asset["truth_sha256"], "existing_source": source,
        })


def derive_plan(
    inventory: dict[str, Any],
    *,
    inventory_file: str,
    base_dir: Path,
) -> dict[str, Any]:
    parsed = parse_inventory(inventory, base_dir=base_dir)
    character_map = parsed["character_map"]
    appearance_state_map = parsed["appearance_state_map"]
    product_map = parsed["product_map"]
    prop_map = parsed["prop_map"]
    scene_map = parsed["scene_map"]
    unit_map = parsed["unit_map"]
    shot_map = parsed["shot_map"]
    shot_ids = parsed["shot_ids"]
    shot_truth = parsed["shot_truth"]
    shot_truth_map = {item["shot_id"]: item for item in shot_truth}

    assets: list[dict[str, Any]] = []
    appearance_asset_ids: dict[str, str] = {}
    product_asset_ids: dict[str, str] = {}
    prop_asset_ids: dict[str, str] = {}
    scene_asset_ids: dict[str, str] = {}
    for state_id, state in appearance_state_map.items():
        entity_id = state["character_id"]
        item = character_map[entity_id]
        asset_id = f"identity-character-{entity_id}-{state_id}"
        appearance_asset_ids[state_id] = asset_id
        coverage = empty_coverage()
        coverage["character_ids"] = [entity_id]
        coverage["appearance_state_ids"] = [state_id]
        assets.append(
            planned_asset(
                asset_id,
                "character_identity_reference",
                f"{item['purpose']} Appearance state: {state['purpose']}",
                truth_payload={
                    "entity": item,
                    "appearance_state": state,
                    "shots": [
                        shot_truth_map[shot_id]
                        for shot_id in shot_ids
                        if state_id in shot_map[shot_id]["appearance_state_ids"]
                    ],
                },
                coverage=coverage,
                inherits_from=[],
                compile_route="selected_skill_handoff",
                identity_kind=item.get("identity_kind", "human"),
            )
        )
    for entity_id, item in product_map.items():
        asset_id = f"identity-product-{entity_id}"
        product_asset_ids[entity_id] = asset_id
        coverage = empty_coverage()
        coverage["product_ids"] = [entity_id]
        assets.append(
            planned_asset(
                asset_id,
                "product_identity_board",
                item["purpose"],
                truth_payload={
                    "entity": item,
                    "shots": [
                        shot_truth_map[shot_id]
                        for shot_id in shot_ids
                        if entity_id in shot_map[shot_id]["product_ids"]
                    ],
                },
                coverage=coverage,
                inherits_from=[],
                compile_route=item.get("compile_route", "direct_concise"),
            )
        )
    for entity_id, item in prop_map.items():
        asset_id = f"continuity-prop-{entity_id}"
        prop_asset_ids[entity_id] = asset_id
        coverage = empty_coverage()
        coverage["prop_ids"] = [entity_id]
        coverage["shot_ids"] = [
            shot_id for shot_id in shot_ids if entity_id in shot_map[shot_id]["prop_ids"]
        ]
        assets.append(
            planned_asset(
                asset_id,
                "prop_continuity_board",
                item["purpose"],
                truth_payload={
                    "entity": item,
                    "shots": [
                        shot_truth_map[shot_id]
                        for shot_id in shot_ids
                        if entity_id in shot_map[shot_id]["prop_ids"]
                    ],
                },
                coverage=coverage,
                inherits_from=[],
                compile_route=item.get("compile_route", "direct_concise"),
            )
        )
    for entity_id, item in scene_map.items():
        asset_id = f"scene-{entity_id}"
        scene_asset_ids[entity_id] = asset_id
        coverage = empty_coverage()
        coverage["scene_ids"] = [entity_id]
        coverage["shot_ids"] = [
            shot_id for shot_id in shot_ids if shot_map[shot_id]["scene_id"] == entity_id
        ]
        assets.append(
            planned_asset(
                asset_id,
                "scene_geography_camera_fov_reference",
                item["purpose"],
                truth_payload={
                    "entity": item,
                    "shots": [
                        shot_truth_map[shot_id]
                        for shot_id in shot_ids
                        if shot_map[shot_id]["scene_id"] == entity_id
                    ],
                },
                coverage=coverage,
                inherits_from=[],
                compile_route=item.get("compile_route", "direct_concise"),
            )
        )

    style_asset_id = "look-whole-film"
    if inventory["style_reference_required"] is True:
        coverage = empty_coverage()
        coverage["scene_ids"] = list(scene_map)
        coverage["shot_ids"] = list(shot_ids)
        assets.append(
            planned_asset(
                style_asset_id,
                "lighting_material_style_board",
                "Lock whole-film lighting, material, atmosphere, optics, and grade "
                "transitions without replacing scene geography.",
                truth_payload={
                    "scenes": list(scene_map.values()),
                    "shots": shot_truth,
                    "compile_route": inventory.get("style_compile_route", "direct_concise"),
                },
                coverage=coverage,
                inherits_from=list(scene_asset_ids.values()),
                compile_route=inventory.get("style_compile_route", "direct_concise"),
            )
        )

    for shot_id in shot_ids:
        shot = shot_map[shot_id]
        unit = unit_map[shot["generation_unit_id"]]
        if unit.get("storyboard_strategy", "individual_frames") == "annotated_reference":
            continue
        coverage = empty_coverage()
        coverage["scene_ids"] = [shot["scene_id"]]
        coverage["character_ids"] = list(shot["character_ids"])
        coverage["appearance_state_ids"] = list(shot["appearance_state_ids"])
        coverage["product_ids"] = list(shot["product_ids"])
        coverage["prop_ids"] = list(shot["prop_ids"])
        coverage["shot_ids"] = [shot_id]
        coverage["generation_unit_ids"] = [shot["generation_unit_id"]]
        inherits = [scene_asset_ids[shot["scene_id"]]]
        inherits.extend(appearance_asset_ids[item] for item in shot["appearance_state_ids"])
        inherits.extend(product_asset_ids[item] for item in shot["product_ids"])
        inherits.extend(prop_asset_ids[item] for item in shot["prop_ids"])
        if inventory["style_reference_required"] is True:
            inherits.append(style_asset_id)
        assets.append(
            planned_asset(
                f"storyboard-frame-{shot_id}",
                "storyboard_frame",
                f"Visualize {shot_id}: {shot['narrative_purpose']}",
                truth_payload=shot_truth_map[shot_id],
                coverage=coverage,
                inherits_from=inherits,
                compile_route="selected_skill_handoff",
            )
        )

    legacy_shot_ids = [
        shot_id for shot_id in shot_ids
        if unit_map[shot_map[shot_id]["generation_unit_id"]].get(
            "storyboard_strategy", "individual_frames"
        ) == "individual_frames"
    ]
    for page_index in range(0, len(legacy_shot_ids), 6):
        page_shots = legacy_shot_ids[page_index : page_index + 6]
        page_number = page_index // 6 + 1
        coverage = empty_coverage()
        coverage["scene_ids"] = list(dict.fromkeys(shot_map[item]["scene_id"] for item in page_shots))
        coverage["character_ids"] = list(
            dict.fromkeys(value for item in page_shots for value in shot_map[item]["character_ids"])
        )
        coverage["appearance_state_ids"] = list(
            dict.fromkeys(value for item in page_shots for value in shot_map[item]["appearance_state_ids"])
        )
        coverage["product_ids"] = list(
            dict.fromkeys(value for item in page_shots for value in shot_map[item]["product_ids"])
        )
        coverage["prop_ids"] = list(
            dict.fromkeys(value for item in page_shots for value in shot_map[item]["prop_ids"])
        )
        coverage["shot_ids"] = page_shots
        coverage["generation_unit_ids"] = list(
            dict.fromkeys(shot_map[item]["generation_unit_id"] for item in page_shots)
        )
        assets.append(
            planned_asset(
                f"director-storyboard-page-{page_number:02d}",
                "professional_storyboard_motion_map",
                f"Assemble director storyboard page {page_number} with shot-card, "
                "blocking, continuity, sound, edit, and model-risk fields.",
                truth_payload=[shot_truth_map[item] for item in page_shots],
                coverage=coverage,
                inherits_from=[f"storyboard-frame-{item}" for item in page_shots],
                action="assemble",
                compile_route="deterministic_assembly",
            )
        )

    for unit_id, unit in unit_map.items():
        if unit.get("storyboard_strategy", "individual_frames") != "annotated_reference":
            continue
        assembled_panels = unit.get("storyboard_acquisition", "native_generate") == "assembled_model_panels"
        unit_shots = list(unit["shot_ids"])
        coverage = empty_coverage()
        coverage["scene_ids"] = list(
            dict.fromkeys(shot_map[item]["scene_id"] for item in unit_shots)
        )
        coverage["character_ids"] = list(
            dict.fromkeys(value for item in unit_shots for value in shot_map[item]["character_ids"])
        )
        coverage["appearance_state_ids"] = list(
            dict.fromkeys(value for item in unit_shots for value in shot_map[item]["appearance_state_ids"])
        )
        coverage["product_ids"] = list(
            dict.fromkeys(value for item in unit_shots for value in shot_map[item]["product_ids"])
        )
        coverage["prop_ids"] = list(
            dict.fromkeys(value for item in unit_shots for value in shot_map[item]["prop_ids"])
        )
        coverage["shot_ids"] = unit_shots
        coverage["generation_unit_ids"] = [unit_id]
        inherits = list(dict.fromkeys(
            scene_asset_ids[shot_map[item]["scene_id"]] for item in unit_shots
        ))
        inherits.extend(
            appearance_asset_ids[state]
            for item in unit_shots for state in shot_map[item]["appearance_state_ids"]
        )
        inherits.extend(
            product_asset_ids[product]
            for item in unit_shots for product in shot_map[item]["product_ids"]
        )
        inherits.extend(
            prop_asset_ids[prop]
            for item in unit_shots for prop in shot_map[item]["prop_ids"]
        )
        if inventory["style_reference_required"] is True:
            inherits.append(style_asset_id)
        assets.append(
            planned_asset(
                f"annotated-storyboard-unit-{unit_id}",
                "professional_storyboard_motion_map",
                (f"Assemble native annotated panel layout for generation unit {unit_id}." if assembled_panels
                 else f"Generate annotated action storyboard reference for generation unit {unit_id}."),
                truth_payload={"unit": unit, "shots": [shot_truth_map[item] for item in unit_shots]},
                coverage=coverage,
                inherits_from=list(dict.fromkeys(inherits)),
                action="assemble" if assembled_panels else "generate",
                compile_route="deterministic_assembly" if assembled_panels else "selected_skill_handoff",
            )
        )

    for unit_id, unit in unit_map.items():
        minimum = unit["direct_input_min"]
        roles = unit["direct_input_roles"]
        for ordinal in range(minimum):
            role = roles[ordinal % len(roles)]
            selected_shot = selected_input_shot(role, unit["shot_ids"], ordinal, minimum)
            shot = shot_map[selected_shot]
            coverage = empty_coverage()
            coverage["scene_ids"] = [shot["scene_id"]]
            coverage["character_ids"] = list(shot["character_ids"])
            coverage["appearance_state_ids"] = list(shot["appearance_state_ids"])
            coverage["product_ids"] = list(shot["product_ids"])
            coverage["prop_ids"] = list(shot["prop_ids"])
            coverage["shot_ids"] = [selected_shot]
            coverage["generation_unit_ids"] = [unit_id]
            suffix = "" if minimum == 1 else f"-{ordinal + 1:02d}"
            assets.append(
                planned_asset(
                    f"clean-input-{unit_id}{suffix}",
                    role,
                    f"Provide a text-free {role} model input for generation unit "
                    f"{unit_id} from approved shot {selected_shot}.",
                    truth_payload={
                        "shot": shot_truth_map[selected_shot],
                        "unit": unit,
                        "direct_input_role": role,
                    },
                    coverage=coverage,
                    inherits_from=[
                        f"annotated-storyboard-unit-{unit_id}"
                        if unit.get("storyboard_strategy", "individual_frames") == "annotated_reference"
                        else f"storyboard-frame-{selected_shot}"
                    ],
                    action="derive",
                    planning_only=False,
                    compile_route="selected_skill_handoff",
                )
            )

    _bind_existing_sources(assets, inventory.get("existing_sources", []), base_dir)
    output_units = [
        {
            "unit_id": unit["unit_id"],
            "shot_ids": list(unit["shot_ids"]),
            "direct_input_min": unit["direct_input_min"],
            "direct_input_max": unit["direct_input_max"],
            "direct_input_roles": list(unit["direct_input_roles"]),
            "direct_input_not_required_reason": unit["direct_input_not_required_reason"],
            **(
                {"storyboard_strategy": "annotated_reference"}
                if unit.get("storyboard_strategy") == "annotated_reference"
                else {}
            ),
            **({"storyboard_acquisition": "assembled_model_panels"}
               if unit.get("storyboard_acquisition") == "assembled_model_panels" else {}),
        }
        for unit in unit_map.values()
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": inventory["project_id"],
        "truth_revision": inventory["truth_revision"],
        "truth_locked_at": inventory["truth_locked_at"],
        "inventory_file": inventory_file,
        "inventory_sha256": canonical_json_sha256(inventory),
        "creative_source_file": inventory["creative_source_file"],
        "creative_source_sha256": parsed["creative_source_sha256"],
        "shot_cards_file": inventory["shot_cards_file"],
        "shot_cards_sha256": parsed["shot_cards_sha256"],
        "shot_truth_sha256": parsed["shot_truth_sha256"],
        "scope": inventory["scope"],
        "duration_seconds": inventory["duration_seconds"],
        "delivery_profile": copy.deepcopy(inventory["delivery_profile"]),
        "scene_ids": list(scene_map),
        "character_ids": list(character_map),
        "appearance_state_ids": list(appearance_state_map),
        "product_ids": list(product_map),
        "prop_ids": list(prop_map),
        "shot_ids": list(shot_ids),
        "shot_truth": shot_truth,
        "rhythm_point_ids": [point["id"] for point in parsed["rhythm_points"]],
        "rhythm_points": parsed["rhythm_points"],
        "style_reference_required": inventory["style_reference_required"],
        "generation_units": output_units,
        "assets": assets,
        "completion_claim": (
            "asset_only_plan_complete"
            if inventory["scope"] == "asset_only"
            else "sample_plan_complete"
            if inventory["scope"] == "representative_sample"
            else "plan_complete"
        ),
    }


def _coverage_counts(
    assets: list[dict[str, Any]],
    role: str,
    field: str,
    ids: list[str],
) -> dict[str, int]:
    counts = {value: 0 for value in ids}
    for asset in assets:
        if asset.get("role") != role or asset.get("required") is not True:
            continue
        for value in safe_coverage_ids(asset, field):
            if value in counts:
                counts[value] += 1
    return counts


def _inheritance_cycle(asset_by_id: dict[str, dict[str, Any]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(asset_id: str, trail: list[str]) -> list[str] | None:
        if asset_id in visiting:
            return trail[trail.index(asset_id) :] + [asset_id]
        if asset_id in visited:
            return None
        visiting.add(asset_id)
        trail.append(asset_id)
        for source in safe_id_list(asset_by_id[asset_id].get("inherits_from")):
            if source in asset_by_id:
                cycle = visit(source, trail)
                if cycle:
                    return cycle
        trail.pop()
        visiting.remove(asset_id)
        visited.add(asset_id)
        return None

    for asset_id in asset_by_id:
        cycle = visit(asset_id, [])
        if cycle:
            return cycle
    return None


def validate_plan(
    payload: Any,
    *,
    base_dir: Path | None = None,
    evidence_cache: dict[
        tuple[str, int, int, int, int, int],
        tuple[dict[str, Any] | None, str | None],
    ]
    | None = None,
    _validate_recorded_assets: bool = True,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["plan_must_be_object"], {}
    errors.extend(schema_errors(payload))
    base_dir = (base_dir or ROOT).resolve()
    schema = load_json(SCHEMA_PATH)
    required_fields = set(schema.get("required", []))
    if set(payload) != required_fields:
        errors.append("plan_field_set_mismatch")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_invalid")
    project_id = payload.get("project_id")
    if not isinstance(project_id, str) or not ID_RE.fullmatch(project_id):
        errors.append("project_id_invalid")
    truth_revision = payload.get("truth_revision")
    if not isinstance(truth_revision, str) or not ID_RE.fullmatch(truth_revision):
        errors.append("truth_revision_invalid")
    truth_locked_at = payload.get("truth_locked_at")
    if (
        not isinstance(truth_locked_at, str)
        or parsed_utc_timestamp(truth_locked_at) is None
        or parsed_utc_timestamp(truth_locked_at).timestamp()
        > datetime.now(timezone.utc).timestamp() + FUTURE_TIMESTAMP_TOLERANCE_SECONDS
    ):
        errors.append("truth_locked_at_invalid")
    scope = payload.get("scope")
    if scope not in {"whole_film", "sequence", "representative_sample", "asset_only"}:
        errors.append("scope_invalid")
    duration = payload.get("duration_seconds")
    if scope == "asset_only":
        if duration is not None:
            errors.append("asset_only_duration_must_be_null")
    elif not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        errors.append("duration_invalid")
    completion_claim = payload.get("completion_claim")
    if completion_claim not in COMPLETION_CLAIMS:
        errors.append(f"completion_claim_invalid:{completion_claim}")
    delivery_profile = payload.get("delivery_profile")
    validate_delivery_profile(delivery_profile, errors, asset_only=scope == "asset_only")
    target_frame_ratio: float | None = None
    if isinstance(delivery_profile, dict):
        target_width = delivery_profile.get("raster_width")
        target_height = delivery_profile.get("raster_height")
        if (
            isinstance(target_width, int)
            and not isinstance(target_width, bool)
            and isinstance(target_height, int)
            and not isinstance(target_height, bool)
            and target_width > 0
            and target_height > 0
        ):
            target_frame_ratio = target_width / target_height

    inventory: dict[str, Any] | None = None
    expected_plan: dict[str, Any] | None = None
    inventory_path = contained_file(payload.get("inventory_file"), base_dir)
    if inventory_path is None:
        errors.append("inventory_file_missing_or_outside_evidence_root")
    else:
        try:
            inventory = load_json(inventory_path)
            actual_inventory_hash = canonical_json_sha256(inventory)
            if payload.get("inventory_sha256") != actual_inventory_hash:
                errors.append("inventory_sha256_mismatch")
            expected_plan = derive_plan(
                inventory,
                inventory_file=str(payload.get("inventory_file")),
                base_dir=base_dir,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(
                "inventory_invalid:"
                + re.sub(r"[^A-Za-z0-9_.-]+", "_", str(exc))[:120]
            )
    if not isinstance(payload.get("inventory_sha256"), str) or not SHA256_RE.fullmatch(
        payload.get("inventory_sha256", "")
    ):
        errors.append("inventory_sha256_invalid")
    for field in ("creative_source_sha256", "shot_cards_sha256", "shot_truth_sha256"):
        value = payload.get(field)
        if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
            errors.append(f"{field}_invalid")
    if expected_plan is not None:
        for field in (
            "project_id",
            "truth_revision",
            "truth_locked_at",
            "inventory_sha256",
            "creative_source_file",
            "creative_source_sha256",
            "shot_cards_file",
            "shot_cards_sha256",
            "shot_truth_sha256",
            "scope",
            "duration_seconds",
            "delivery_profile",
            "scene_ids",
            "character_ids",
            "appearance_state_ids",
            "product_ids",
            "prop_ids",
            "shot_ids",
            "shot_truth",
            "rhythm_point_ids",
            "rhythm_points",
            "style_reference_required",
            "generation_units",
        ):
            if payload.get(field) != expected_plan.get(field):
                errors.append(f"plan_inventory_field_mismatch:{field}")

    scene_ids = validate_id_list(
        payload.get("scene_ids"),
        "scene_ids",
        errors,
        nonempty=scope not in {"representative_sample", "asset_only"},
    )
    character_ids = validate_id_list(payload.get("character_ids"), "character_ids", errors)
    appearance_state_ids = validate_id_list(
        payload.get("appearance_state_ids"),
        "appearance_state_ids",
        errors,
    )
    product_ids = validate_id_list(payload.get("product_ids"), "product_ids", errors)
    prop_ids = validate_id_list(payload.get("prop_ids"), "prop_ids", errors)
    shot_ids = validate_id_list(
        payload.get("shot_ids"), "shot_ids", errors, nonempty=scope != "asset_only"
    )
    rhythm_ids = validate_id_list(
        payload.get("rhythm_point_ids"),
        "rhythm_point_ids",
        errors,
        nonempty=scope != "asset_only",
    )
    if scope != "asset_only" and len(rhythm_ids) < len(shot_ids):
        errors.append("rhythm_points_fewer_than_shots")
    rhythm_points = payload.get("rhythm_points")
    if not isinstance(rhythm_points, list) or (not rhythm_points and scope != "asset_only"):
        errors.append("rhythm_points_missing")
        rhythm_points = []
    parsed_rhythm_ids: list[str] = []
    previous_rhythm_time = -1.0
    for index, point in enumerate(rhythm_points):
        expected_fields = {"id", "timecode", "shot_ids", "action", "sound_transition"}
        if not isinstance(point, dict) or set(point) != expected_fields:
            errors.append(f"rhythm_point_invalid:{index}")
            continue
        point_id = point.get("id")
        if not isinstance(point_id, str) or not ID_RE.fullmatch(point_id):
            errors.append(f"rhythm_point_id_invalid:{index}")
            continue
        parsed_rhythm_ids.append(point_id)
        point_shots = validate_id_list(
            point.get("shot_ids"),
            f"rhythm_points[{point_id}].shot_ids",
            errors,
            nonempty=True,
        )
        add_coverage_error(
            errors,
            f"rhythm_point_unknown_shots:{point_id}",
            sorted(set(point_shots) - set(shot_ids)),
        )
        point_timecode = point.get("timecode")
        if not isinstance(point_timecode, str) or re.fullmatch(
            r"[0-9]{2,}:[0-5][0-9](?:\.[0-9]+)?",
            point_timecode,
        ) is None:
            errors.append(f"rhythm_point_timecode_invalid:{point_id}")
        else:
            point_time = timecode_seconds(point_timecode)
            if point_time < previous_rhythm_time or (
                isinstance(duration, (int, float)) and point_time > float(duration)
            ):
                errors.append(f"rhythm_point_timeline_invalid:{point_id}")
            previous_rhythm_time = point_time
        for field in ("action", "sound_transition"):
            value = point.get(field)
            if not isinstance(value, str) or len(value.strip()) < 12 or PLACEHOLDER_RE.search(value):
                errors.append(f"rhythm_point_text_invalid:{point_id}:{field}")
    if parsed_rhythm_ids != rhythm_ids:
        errors.append("rhythm_point_ids_mismatch")
    if not isinstance(payload.get("style_reference_required"), bool):
        errors.append("style_reference_required_invalid")

    raw_truth = payload.get("shot_truth")
    truth_map: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_truth, list) or (not raw_truth and scope != "asset_only"):
        errors.append("shot_truth_missing")
        raw_truth = []
    for index, truth in enumerate(raw_truth):
        expected_fields = {
            "shot_id",
            "scene_id",
            "character_ids",
            "appearance_state_ids",
            "product_ids",
            "prop_ids",
            "story_beat_ids",
            "script_line_ids",
            "generation_unit_id",
            "narrative_purpose",
            "timecode",
            "duration_seconds",
            "shot_design",
            "action",
            "sound_edit",
            "continuity_model",
        }
        if not isinstance(truth, dict) or set(truth) - {"scene_state_source"} != expected_fields:
            errors.append(f"shot_truth_invalid:{index}")
            continue
        shot_id = truth.get("shot_id")
        if not isinstance(shot_id, str) or not ID_RE.fullmatch(shot_id) or shot_id in truth_map:
            errors.append(f"shot_truth_id_invalid:{index}")
            continue
        for field in (
            "character_ids",
            "appearance_state_ids",
            "product_ids",
            "prop_ids",
            "story_beat_ids",
            "script_line_ids",
        ):
            validate_id_list(truth.get(field), f"shot_truth[{shot_id}].{field}", errors)
        for field in (
            "narrative_purpose",
            "timecode",
            "shot_design",
            "action",
            "sound_edit",
            "continuity_model",
        ):
            value = truth.get(field)
            if (
                not isinstance(value, str)
                or len(value.strip()) < 9
                or PLACEHOLDER_RE.search(value)
            ):
                errors.append(f"shot_truth_text_invalid:{shot_id}:{field}")
        truth_duration = truth.get("duration_seconds")
        if (
            not isinstance(truth_duration, (int, float))
            or isinstance(truth_duration, bool)
            or truth_duration <= 0
        ):
            errors.append(f"shot_truth_duration_invalid:{shot_id}")
        truth_map[shot_id] = truth
    if list(truth_map) != shot_ids:
        errors.append("shot_truth_order_or_coverage_mismatch")
    if isinstance(raw_truth, list) and payload.get("shot_truth_sha256") != canonical_json_sha256(raw_truth):
        errors.append("shot_truth_sha256_mismatch")

    generation_units = payload.get("generation_units")
    if not isinstance(generation_units, list) or (not generation_units and scope != "asset_only"):
        errors.append("generation_units_missing")
        generation_units = []
    unit_ids: list[str] = []
    unit_map: dict[str, dict[str, Any]] = {}
    unit_membership_counts = {shot_id: 0 for shot_id in shot_ids}
    for index, unit in enumerate(generation_units):
        expected_fields = {
            "unit_id",
            "shot_ids",
            "direct_input_min",
            "direct_input_max",
            "direct_input_roles",
            "direct_input_not_required_reason",
        }
        if not isinstance(unit, dict) or set(unit) - {"storyboard_strategy", "storyboard_acquisition"} != expected_fields:
            errors.append(f"generation_unit_invalid:{index}")
            continue
        unit_id = unit.get("unit_id")
        if not isinstance(unit_id, str) or not ID_RE.fullmatch(unit_id):
            errors.append(f"generation_unit_id_invalid:{index}")
            continue
        unit_ids.append(unit_id)
        unit_map[unit_id] = unit
        covered = validate_id_list(
            unit.get("shot_ids"),
            f"generation_units[{unit_id}].shot_ids",
            errors,
            nonempty=True,
        )
        unknown = sorted(set(covered) - set(shot_ids))
        add_coverage_error(errors, f"generation_unit_unknown_shots:{unit_id}", unknown)
        for shot_id in covered:
            if shot_id in unit_membership_counts:
                unit_membership_counts[shot_id] += 1
        minimum = unit.get("direct_input_min")
        maximum = unit.get("direct_input_max")
        roles = unit.get("direct_input_roles")
        reason = unit.get("direct_input_not_required_reason")
        storyboard_strategy = unit.get("storyboard_strategy", "individual_frames")
        if (
            not isinstance(minimum, int)
            or isinstance(minimum, bool)
            or not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or not 0 <= minimum <= maximum
        ):
            errors.append(f"generation_unit_direct_input_range_invalid:{unit_id}")
        if (
            not isinstance(roles, list)
            or not all(role in DIRECT_ROLES for role in roles)
            or duplicate_values(roles)
            or not isinstance(reason, str)
            or storyboard_strategy not in STORYBOARD_STRATEGIES
            or not isinstance(unit.get("storyboard_acquisition", "native_generate"), str)
            or unit.get("storyboard_acquisition", "native_generate") not in STORYBOARD_ACQUISITIONS
            or ("storyboard_acquisition" in unit and storyboard_strategy != "annotated_reference")
        ):
            errors.append(f"generation_unit_direct_input_strategy_invalid:{unit_id}")
        elif isinstance(maximum, int) and maximum > 0 and not roles:
            errors.append(f"generation_unit_direct_input_roles_missing:{unit_id}")
        if isinstance(minimum, int) and minimum > 0 and isinstance(reason, str) and reason.strip():
            errors.append(f"generation_unit_required_has_not_required_reason:{unit_id}")
        if isinstance(minimum, int) and minimum == 0 and isinstance(reason, str) and len(reason.strip()) < 12:
            errors.append(f"generation_unit_not_required_reason_missing:{unit_id}")
    for duplicate in duplicate_values(unit_ids):
        errors.append(f"duplicate_generation_unit:{duplicate}")
    for shot_id, count in unit_membership_counts.items():
        if count != 1:
            errors.append(f"generation_unit_shot_membership_invalid:{shot_id}:{count}")

    assets_raw = payload.get("assets")
    if not isinstance(assets_raw, list) or not assets_raw:
        errors.append("assets_missing")
        assets_raw = []
    assets: list[dict[str, Any]] = []
    asset_ids: list[str] = []
    role_assets: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    valid_coverage = {
        "scene_ids": set(scene_ids),
        "character_ids": set(character_ids),
        "appearance_state_ids": set(appearance_state_ids),
        "product_ids": set(product_ids),
        "prop_ids": set(prop_ids),
        "shot_ids": set(shot_ids),
        "generation_unit_ids": set(unit_ids),
    }
    for index, asset in enumerate(assets_raw):
        if (
            not isinstance(asset, dict)
            or not ASSET_FIELDS.issubset(asset)
            or set(asset) - ASSET_FIELDS - ASSET_OPTIONAL_FIELDS - ASSET_EXECUTION_FIELDS
        ):
            errors.append(f"asset_field_set_mismatch:{index}")
            continue
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not ID_RE.fullmatch(asset_id):
            errors.append(f"asset_id_invalid:{index}")
            continue
        assets.append(asset)
        if "execution_task_id" in asset and (
            not isinstance(asset["execution_task_id"], str) or not ID_RE.fullmatch(asset["execution_task_id"])
        ):
            errors.append(f"asset_execution_task_id_invalid:{asset_id}")
        if asset.get("candidate_self_check") is not None:
            binding = asset["candidate_self_check"]
            if (not isinstance(binding, dict) or set(binding) != {"relative_path", "sha256"}
                or not isinstance(binding.get("relative_path"), str)
                or not isinstance(binding.get("sha256"), str) or not SHA256_RE.fullmatch(binding["sha256"])
                or "execution_task_id" not in asset):
                errors.append(f"asset_candidate_self_check_binding_invalid:{asset_id}")
        if "candidate_repair_source" in asset:
            source = asset["candidate_repair_source"]
            if (not isinstance(source, dict) or source.get("contract_id") != "candidate_repair_source_v1"
                or source.get("project_id") != payload.get("project_id")
                or source.get("asset_id") != asset_id or source.get("truth_sha256") != asset.get("truth_sha256")
                or not isinstance(source.get("source_image"), dict)
                or source["source_image"].get("pixel_sha256") == asset.get("generated_pixel_sha256")):
                errors.append(f"asset_candidate_repair_lineage_invalid:{asset_id}")
        asset_ids.append(asset_id)
        role = asset.get("role")
        if role not in ROLES:
            errors.append(f"asset_role_invalid:{asset_id}")
            continue
        compile_route = asset.get("compile_route")
        if compile_route not in COMPILE_ROUTES:
            errors.append(f"asset_compile_route_invalid:{asset_id}")
        elif role in {
            "character_identity_reference",
            "storyboard_frame",
            "clean_first_frame",
            "clean_key_frame",
            "clean_end_frame",
        } and compile_route != "selected_skill_handoff":
            errors.append(f"asset_compile_route_role_mismatch:{asset_id}")
        elif role == "professional_storyboard_motion_map" and compile_route not in {
            "deterministic_assembly", "selected_skill_handoff"
        }:
            errors.append(f"asset_compile_route_role_mismatch:{asset_id}")
        elif role not in {
            "professional_storyboard_motion_map",
            "character_identity_reference",
            "storyboard_frame",
            "clean_first_frame",
            "clean_key_frame",
            "clean_end_frame",
        } and compile_route == "deterministic_assembly":
            errors.append(f"asset_compile_route_role_mismatch:{asset_id}")
        role_assets[role].append(asset)
        if role == "character_identity_reference":
            mode = asset.get("character_mode")
            identity_kind = asset.get("identity_kind", "human")
            source_id = asset.get("derived_from_asset_id")
            source_sha = asset.get("approved_source_master_sha256")
            contract = {
                "character_mode": mode,
                "derived_from_asset_id": source_id,
                "approved_source_master_sha256": source_sha,
                "coverage": asset.get("coverage"),
                "inherits_from": asset.get("inherits_from"),
                "purpose": asset.get("purpose"),
            }
            if "identity_kind" in asset:
                contract["identity_kind"] = identity_kind
            if mode not in CHARACTER_MODES:
                errors.append(f"character_mode_invalid:{asset_id}")
            if identity_kind not in IDENTITY_KINDS:
                errors.append(f"character_identity_kind_invalid:{asset_id}")
            if mode == "headless_safe" and (
                identity_kind != "human"
            ):
                errors.append(f"headless_character_contract_invalid:{asset_id}")
            if mode == "headed_master":
                if source_id is not None or source_sha is not None:
                    errors.append(f"base_character_source_must_be_empty:{asset_id}")
            elif (
                not isinstance(source_id, str)
                or not ID_RE.fullmatch(source_id)
                or not isinstance(source_sha, str)
                or not SHA256_RE.fullmatch(source_sha)
            ):
                errors.append(f"derived_character_source_invalid:{asset_id}")
            if asset.get("character_contract_sha256") != canonical_json_sha256(contract):
                errors.append(f"character_contract_sha256_mismatch:{asset_id}")
        elif any(field in asset for field in ASSET_OPTIONAL_FIELDS):
            errors.append(f"non_character_contract_fields_invalid:{asset_id}")
        purpose = asset.get("purpose")
        if (
            not isinstance(purpose, str)
            or len(purpose.strip()) < 12
            or PLACEHOLDER_RE.search(purpose)
        ):
            errors.append(f"asset_purpose_invalid:{asset_id}")
        if not isinstance(asset.get("required"), bool):
            errors.append(f"asset_required_invalid:{asset_id}")
        if asset.get("action") not in {"reuse", "derive", "generate", "assemble"}:
            errors.append(f"asset_action_invalid:{asset_id}")
        if asset.get("status") not in {
            "planned",
            "prompt_ready",
            "generated_candidate",
            "user_locked",
            "reused_locked",
            "rejected",
        }:
            errors.append(f"asset_status_invalid:{asset_id}")
        if asset.get("required") is True and asset.get("status") == "rejected":
            errors.append(f"required_asset_rejected:{asset_id}")
        if (asset.get("status") in {"user_locked", "reused_locked"}
            and isinstance(asset.get("visual_qa_receipt"), dict)
            and asset["visual_qa_receipt"].get("reviewer_type") == "executor"):
            errors.append(f"executor_review_cannot_grant_asset_lock:{asset_id}")
        for field in ("generated_sha256", "generated_pixel_sha256"):
            value = asset.get(field)
            if not isinstance(value, str) or (value and SHA256_RE.fullmatch(value) is None):
                errors.append(f"asset_{field}_invalid:{asset_id}")
        perceptual_hash = asset.get("generated_perceptual_hash")
        if (
            not isinstance(perceptual_hash, str)
            or (perceptual_hash and SHA256_RE.fullmatch(perceptual_hash) is None)
        ):
            errors.append(f"asset_generated_perceptual_hash_invalid:{asset_id}")
        truth_hash = asset.get("truth_sha256")
        if not isinstance(truth_hash, str) or SHA256_RE.fullmatch(truth_hash) is None:
            errors.append(f"asset_truth_sha256_invalid:{asset_id}")
        if role in PLANNING_ROLES and (
            asset.get("planning_only") is not True or asset.get("direct_video_input") is not False
        ):
            errors.append(f"planning_asset_direct_input_invalid:{asset_id}")
        if role in DIRECT_ROLES and (
            asset.get("planning_only") is not False or asset.get("direct_video_input") is not True
        ):
            errors.append(f"clean_input_policy_invalid:{asset_id}")
        coverage = asset.get("coverage")
        if not isinstance(coverage, dict) or set(coverage) != COVERAGE_FIELDS:
            errors.append(f"asset_coverage_shape_invalid:{asset_id}")
            continue
        for field, allowed in valid_coverage.items():
            values = validate_id_list(
                coverage.get(field),
                f"assets[{asset_id}].coverage.{field}",
                errors,
            )
            add_coverage_error(
                errors,
                f"asset_coverage_unknown:{asset_id}:{field}",
                sorted(set(values) - allowed),
            )
        inherits = validate_id_list(
            asset.get("inherits_from"),
            f"assets[{asset_id}].inherits_from",
            errors,
        )
        if asset_id in inherits:
            errors.append(f"asset_self_inheritance:{asset_id}")
        if role == "character_identity_reference" and len(safe_coverage_ids(asset, "character_ids")) != 1:
            errors.append(f"character_identity_scope_invalid:{asset_id}")
        if role == "character_identity_reference" and len(safe_coverage_ids(asset, "appearance_state_ids")) != 1:
            errors.append(f"character_identity_appearance_scope_invalid:{asset_id}")
        if role == "product_identity_board" and len(safe_coverage_ids(asset, "product_ids")) != 1:
            errors.append(f"product_identity_scope_invalid:{asset_id}")
        if role == "prop_continuity_board" and len(safe_coverage_ids(asset, "prop_ids")) != 1:
            errors.append(f"prop_continuity_scope_invalid:{asset_id}")
        if role == "scene_geography_camera_fov_reference" and len(safe_coverage_ids(asset, "scene_ids")) != 1:
            errors.append(f"scene_reference_scope_invalid:{asset_id}")
        if role == "storyboard_frame":
            storyboard_shots = safe_coverage_ids(asset, "shot_ids")
            if len(storyboard_shots) != 1:
                errors.append(f"storyboard_frame_scope_invalid:{asset_id}")
            if len(safe_coverage_ids(asset, "scene_ids")) != 1:
                errors.append(f"storyboard_frame_scene_scope_invalid:{asset_id}")
            if len(safe_coverage_ids(asset, "generation_unit_ids")) != 1:
                errors.append(f"storyboard_frame_generation_unit_invalid:{asset_id}")
            if len(storyboard_shots) == 1 and storyboard_shots[0] in truth_map:
                truth = truth_map[storyboard_shots[0]]
                expected_coverage = {
                    "scene_ids": [truth["scene_id"]],
                    "character_ids": list(truth["character_ids"]),
                    "appearance_state_ids": list(truth["appearance_state_ids"]),
                    "product_ids": list(truth["product_ids"]),
                    "prop_ids": list(truth["prop_ids"]),
                    "shot_ids": [truth["shot_id"]],
                    "generation_unit_ids": [truth["generation_unit_id"]],
                }
                if coverage != expected_coverage:
                    errors.append(f"storyboard_truth_mismatch:{asset_id}")
        if role == "professional_storyboard_motion_map":
            page_shots = safe_coverage_ids(asset, "shot_ids")
            unit_coverage = safe_coverage_ids(asset, "generation_unit_ids")
            annotated_unit = (
                len(unit_coverage) == 1
                and unit_map.get(unit_coverage[0], {}).get(
                    "storyboard_strategy", "individual_frames"
                ) == "annotated_reference"
            )
            if annotated_unit:
                unit_id = unit_coverage[0]
                expected_shots = safe_id_list(unit_map[unit_id].get("shot_ids"))
                assembled_panels = unit_map[unit_id].get("storyboard_acquisition", "native_generate") == "assembled_model_panels"
                if asset.get("action") != ("assemble" if assembled_panels else "generate"):
                    errors.append(f"annotated_storyboard_must_{'assemble' if assembled_panels else 'generate'}:{asset_id}")
                if asset.get("compile_route") != ("deterministic_assembly" if assembled_panels else "selected_skill_handoff"):
                    errors.append(f"annotated_storyboard_compile_route_invalid:{asset_id}")
                if page_shots != expected_shots:
                    errors.append(f"annotated_storyboard_unit_coverage_invalid:{asset_id}")
            else:
                if asset.get("action") != "assemble":
                    errors.append(f"director_storyboard_must_assemble:{asset_id}")
                if asset.get("compile_route") != "deterministic_assembly":
                    errors.append(f"director_storyboard_compile_route_invalid:{asset_id}")
                if not 1 <= len(page_shots) <= 6:
                    errors.append(f"director_storyboard_page_density_invalid:{asset_id}")
            if page_shots and all(shot_id in truth_map for shot_id in page_shots):
                expected_page_coverage = {
                    "scene_ids": list(dict.fromkeys(truth_map[item]["scene_id"] for item in page_shots)),
                    "character_ids": list(
                        dict.fromkeys(value for item in page_shots for value in truth_map[item]["character_ids"])
                    ),
                    "appearance_state_ids": list(
                        dict.fromkeys(value for item in page_shots for value in truth_map[item]["appearance_state_ids"])
                    ),
                    "product_ids": list(
                        dict.fromkeys(value for item in page_shots for value in truth_map[item]["product_ids"])
                    ),
                    "prop_ids": list(
                        dict.fromkeys(value for item in page_shots for value in truth_map[item]["prop_ids"])
                    ),
                    "shot_ids": page_shots,
                    "generation_unit_ids": list(
                        dict.fromkeys(truth_map[item]["generation_unit_id"] for item in page_shots)
                    ),
                }
                if coverage != expected_page_coverage:
                    errors.append(f"director_storyboard_truth_mismatch:{asset_id}")
                if not annotated_unit:
                    expected_page_dependencies = [f"storyboard-frame-{item}" for item in page_shots]
                    if asset.get("inherits_from") != expected_page_dependencies:
                        errors.append(f"director_storyboard_dependency_mismatch:{asset_id}")
        if role in DIRECT_ROLES:
            clean_shots = safe_coverage_ids(asset, "shot_ids")
            if (
                len(clean_shots) != 1
                or len(safe_coverage_ids(asset, "scene_ids")) != 1
                or len(safe_coverage_ids(asset, "generation_unit_ids")) != 1
            ):
                errors.append(f"clean_input_scope_invalid:{asset_id}")
            elif clean_shots[0] in truth_map:
                truth = truth_map[clean_shots[0]]
                expected_clean_coverage = {
                    "scene_ids": [truth["scene_id"]],
                    "character_ids": list(truth["character_ids"]),
                    "appearance_state_ids": list(truth["appearance_state_ids"]),
                    "product_ids": list(truth["product_ids"]),
                    "prop_ids": list(truth["prop_ids"]),
                    "shot_ids": [truth["shot_id"]],
                    "generation_unit_ids": [truth["generation_unit_id"]],
                }
                if coverage != expected_clean_coverage:
                    errors.append(f"clean_input_truth_mismatch:{asset_id}")
                expected_parent = (
                    f"annotated-storyboard-unit-{truth['generation_unit_id']}"
                    if unit_map.get(truth["generation_unit_id"], {}).get(
                        "storyboard_strategy", "individual_frames"
                    ) == "annotated_reference"
                    else f"storyboard-frame-{truth['shot_id']}"
                )
                if asset.get("inherits_from") != [expected_parent]:
                    errors.append(f"clean_input_dependency_mismatch:{asset_id}")

    for duplicate in duplicate_values(asset_ids):
        errors.append(f"duplicate_asset_id:{duplicate}")
    asset_by_id = {asset["asset_id"]: asset for asset in assets}
    for asset in assets:
        for source in safe_id_list(asset.get("inherits_from")):
            if source not in asset_by_id:
                errors.append(f"asset_inheritance_unknown:{asset['asset_id']}:{source}")
        if asset.get("role") == "character_identity_reference" and asset.get("character_mode") in {
            "headed_state",
            "headless_safe",
        }:
            source_id = asset.get("derived_from_asset_id")
            source_asset = asset_by_id.get(str(source_id))
            if asset.get("action") != "derive":
                errors.append(f"derived_character_action_invalid:{asset['asset_id']}")
            if asset.get("inherits_from") != [source_id]:
                errors.append(f"derived_character_inheritance_mismatch:{asset['asset_id']}")
            if (
                not isinstance(source_asset, dict)
                or source_asset.get("role") != "character_identity_reference"
                or source_asset.get("character_mode") != "headed_master"
                or source_asset.get("identity_kind", "human") != asset.get("identity_kind", "human")
                or source_asset.get("status") not in GENERATED_STATUSES
                or source_asset.get("generated_sha256")
                != asset.get("approved_source_master_sha256")
                or source_asset.get("coverage", {}).get("character_ids")
                != asset.get("coverage", {}).get("character_ids")
            ):
                errors.append(f"derived_character_source_evidence_mismatch:{asset['asset_id']}")
    cycle = _inheritance_cycle(asset_by_id)
    if cycle:
        errors.append("asset_inheritance_cycle:" + ",".join(cycle))

    if expected_plan is not None:
        expected_assets = {
            asset["asset_id"]: asset for asset in expected_plan["assets"] if asset["required"] is True
        }
        for asset_id, expected in expected_assets.items():
            actual = asset_by_id.get(asset_id)
            if actual is None or actual.get("required") is not True:
                errors.append(f"required_asset_missing:{asset_id}")
                continue
            for field in (
                "role",
                "action",
                "purpose",
                "coverage",
                "inherits_from",
                "planning_only",
                "direct_video_input",
                "truth_sha256",
                "compile_route",
                "identity_kind",
            ):
                if (
                    expected.get("role") == "character_identity_reference"
                    and actual.get("character_mode") in {"headed_state", "headless_safe"}
                    and field in {"action", "inherits_from"}
                    and actual.get("action") == "derive"
                ):
                    continue
                if field == "identity_kind" and actual.get(field, "human") == expected.get(field, "human"):
                    continue
                if actual.get(field) == expected.get(field):
                    continue
                if field == "coverage" and expected["role"] == "storyboard_frame":
                    errors.append(f"storyboard_truth_mismatch:{asset_id}")
                elif field == "inherits_from":
                    errors.append(f"asset_dependency_mismatch:{asset_id}")
                else:
                    errors.append(f"asset_semantic_drift:{asset_id}:{field}")
            if expected.get("action") == "reuse" and actual.get("generated_file") != expected.get("generated_file"):
                errors.append(f"existing_source_path_mismatch:{asset_id}")

    if scope == "asset_only":
        if completion_claim not in {"none", "asset_only_plan_complete"}:
            errors.append("asset_only_completion_claim_invalid")
        if any((shot_ids, rhythm_ids, raw_truth, generation_units)):
            errors.append("asset_only_timeline_content_present")
        forbidden_roles = {
            "storyboard_frame",
            "professional_storyboard_motion_map",
            *DIRECT_ROLES,
        }
        if any(asset.get("role") in forbidden_roles for asset in assets):
            errors.append("asset_only_video_asset_present")

    def exact_coverage(role: str, field: str, ids: list[str], prefix: str) -> None:
        for value, count in _coverage_counts(assets, role, field, ids).items():
            if count != 1:
                errors.append(f"{prefix}:{value}:{count}")

    character_counts = _coverage_counts(
        assets,
        "character_identity_reference",
        "character_ids",
        character_ids,
    )
    appearance_counts = _coverage_counts(
        assets,
        "character_identity_reference",
        "appearance_state_ids",
        appearance_state_ids,
    )
    product_counts = _coverage_counts(assets, "product_identity_board", "product_ids", product_ids)
    prop_counts = _coverage_counts(assets, "prop_continuity_board", "prop_ids", prop_ids)
    scene_counts = _coverage_counts(
        assets,
        "scene_geography_camera_fov_reference",
        "scene_ids",
        scene_ids,
    )
    add_coverage_error(
        errors,
        "character_coverage_missing",
        [key for key, value in character_counts.items() if value == 0],
    )
    add_coverage_error(
        errors,
        "appearance_state_coverage_missing",
        [key for key, value in appearance_counts.items() if value == 0],
    )
    add_coverage_error(
        errors,
        "product_coverage_missing",
        [key for key, value in product_counts.items() if value == 0],
    )
    add_coverage_error(errors, "prop_coverage_missing", [key for key, value in prop_counts.items() if value == 0])
    add_coverage_error(errors, "scene_coverage_missing", [key for key, value in scene_counts.items() if value == 0])
    exact_coverage(
        "character_identity_reference",
        "appearance_state_ids",
        appearance_state_ids,
        "appearance_state_identity_coverage_invalid",
    )
    exact_coverage(
        "product_identity_board",
        "product_ids",
        product_ids,
        "product_identity_coverage_invalid",
    )
    exact_coverage(
        "prop_continuity_board",
        "prop_ids",
        prop_ids,
        "prop_continuity_coverage_invalid",
    )
    exact_coverage(
        "scene_geography_camera_fov_reference",
        "scene_ids",
        scene_ids,
        "scene_identity_coverage_invalid",
    )

    legacy_storyboard_shot_ids = [
        shot_id for shot_id in shot_ids
        if unit_map.get(truth_map.get(shot_id, {}).get("generation_unit_id"), {}).get(
            "storyboard_strategy", "individual_frames"
        ) == "individual_frames"
    ]
    storyboard_counts = _coverage_counts(
        assets, "storyboard_frame", "shot_ids", legacy_storyboard_shot_ids
    )
    director_counts = _coverage_counts(
        assets,
        "professional_storyboard_motion_map",
        "shot_ids",
        shot_ids,
    )
    scene_reference_counts = _coverage_counts(
        assets,
        "scene_geography_camera_fov_reference",
        "shot_ids",
        shot_ids,
    )
    for shot_id, count in scene_reference_counts.items():
        if count != 1:
            errors.append(f"scene_reference_shot_coverage_invalid:{shot_id}:{count}")
    for shot_id, count in storyboard_counts.items():
        if count != 1:
            errors.append(f"storyboard_frame_coverage_invalid:{shot_id}:{count}")
    add_coverage_error(
        errors,
        "director_storyboard_coverage_missing",
        [shot_id for shot_id, count in director_counts.items() if count == 0],
    )
    add_coverage_error(
        errors,
        "director_storyboard_coverage_duplicate",
        [shot_id for shot_id, count in director_counts.items() if count > 1],
    )

    style_count = sum(
        asset.get("required") is True
        for asset in role_assets["lighting_material_style_board"]
    )
    expected_style_count = 1 if payload.get("style_reference_required") is True else 0
    if style_count != expected_style_count:
        errors.append(f"style_reference_count_invalid:{style_count}:{expected_style_count}")

    for unit_id, unit in unit_map.items():
        unit_shots = safe_id_list(unit.get("shot_ids"))
        scenes = {
            truth_map[shot_id]["scene_id"]
            for shot_id in unit_shots
            if shot_id in truth_map
        }
        if len(scenes) > 1:
            errors.append(
                f"generation_unit_crosses_scene_anchors:{unit_id}:"
                + ",".join(sorted(scenes))
            )
        direct_assets = [
            asset
            for asset in assets
            if asset.get("required") is True
            and asset.get("role") in DIRECT_ROLES
            and safe_coverage_ids(asset, "generation_unit_ids") == [unit_id]
        ]
        minimum = unit.get("direct_input_min")
        maximum = unit.get("direct_input_max")
        if isinstance(minimum, int) and isinstance(maximum, int) and not minimum <= len(direct_assets) <= maximum:
            errors.append(
                f"generation_unit_direct_input_count_invalid:{unit_id}:{len(direct_assets)}:{minimum}:{maximum}"
            )
        allowed_roles = unit.get("direct_input_roles") if isinstance(unit.get("direct_input_roles"), list) else []
        for asset in direct_assets:
            if asset.get("role") not in allowed_roles:
                errors.append(f"generation_unit_direct_input_role_invalid:{unit_id}:{asset['asset_id']}")
            covered_shots = safe_coverage_ids(asset, "shot_ids")
            if len(covered_shots) == 1 and covered_shots[0] not in unit_shots:
                errors.append(f"clean_input_shot_outside_unit:{asset['asset_id']}")

    if scope == "representative_sample" and completion_claim in {"plan_complete", "visual_assets_complete"}:
        errors.append("sample_cannot_claim_whole_film_plan_complete")
    if completion_claim == "sample_plan_complete" and scope != "representative_sample":
        errors.append("sample_plan_complete_requires_sample_scope")
    if completion_claim == "sample_visual_assets_complete" and scope != "representative_sample":
        errors.append("sample_visual_assets_complete_requires_sample_scope")
    if completion_claim == "asset_only_plan_complete" and scope != "asset_only":
        errors.append("asset_only_plan_complete_requires_asset_only_scope")

    evidence_by_asset: dict[str, dict[str, Any]] = {}
    all_images_required = completion_claim in GENERATED_CLAIMS
    has_recorded_reuse_evidence = _validate_recorded_assets and any(
        asset.get("required") is True and asset.get("action") == "reuse"
        and asset.get("technical_receipt") is not None for asset in assets
    )
    if all_images_required or (scope == "asset_only" and _validate_recorded_assets) or has_recorded_reuse_evidence:
        recorded_assets = [
            asset for asset in assets
            if asset.get("required") is True
            and (all_images_required or (scope == "asset_only" and asset.get("status") in GENERATED_STATUSES)
                 or (asset.get("action") == "reuse" and asset.get("technical_receipt") is not None)
                 # A joint review also needs its reviewed generated/assembled
                 # members; unreviewed future assets stay outside this readback.
                 or (has_recorded_reuse_evidence and asset.get("visual_qa_receipt") is not None))
        ]
        for asset in recorded_assets:
            asset_id = asset["asset_id"]
            pending_reuse = asset.get("action") == "reuse" and asset.get("status") in {"planned", "prompt_ready"}
            if asset.get("status") not in GENERATED_STATUSES and not (pending_reuse and not all_images_required):
                errors.append(f"required_asset_not_generated:{asset_id}")
            path = contained_file(asset.get("generated_file"), base_dir)
            if path is None:
                errors.append(f"required_asset_file_missing_or_outside_evidence_root:{asset_id}")
                continue
            evidence, reason = inspect_raster_cached(path, evidence_cache)
            if evidence is None:
                errors.append(f"required_asset_raster_invalid:{asset_id}:{reason}")
                continue
            evidence_by_asset[asset_id] = evidence
            if (scope == "asset_only" or asset.get("role") in DELIVERY_FRAME_ROLES) and target_frame_ratio is not None:
                actual_ratio = evidence["width"] / evidence["height"]
                relative_drift = abs(actual_ratio - target_frame_ratio) / target_frame_ratio
                if relative_drift > DELIVERY_ASPECT_RATIO_TOLERANCE:
                    errors.append(
                        f"required_asset_delivery_aspect_ratio_mismatch:{asset_id}:"
                        f"{evidence['width']}x{evidence['height']}"
                    )
            if asset.get("generated_sha256") != evidence["sha256"]:
                errors.append(f"required_asset_hash_mismatch:{asset_id}")
            if asset.get("generated_pixel_sha256") != evidence["pixel_sha256"]:
                errors.append(f"required_asset_pixel_hash_mismatch:{asset_id}")
            if asset.get("generated_perceptual_hash") != evidence["perceptual_hash"]:
                errors.append(f"required_asset_perceptual_hash_mismatch:{asset_id}")
            receipt_problem = validate_technical_receipt(
                asset.get("technical_receipt"),
                asset_id=asset_id,
                evidence=evidence,
                truth_locked_at=str(truth_locked_at),
            )
            if receipt_problem:
                errors.append(
                    f"required_asset_technical_receipt_invalid:{asset_id}:{receipt_problem}"
                )
            review_claimed = all_images_required or asset.get("status") in {"user_locked", "reused_locked"} or asset.get("visual_qa_receipt") is not None
            if asset.get("role") == "character_identity_reference" and review_claimed and asset.get("identity_kind", "human") == "human":
                try:
                    from dircreative_character_master_visual_gate import (
                        load_headless_review_authorization,
                        load_character_master_receipt,
                    )

                    structure_receipt, structure_errors = load_character_master_receipt(
                        asset,
                        base_dir=base_dir,
                        image_evidence=evidence,
                    )
                except (ImportError, OSError, ValueError):
                    structure_receipt, structure_errors = None, [
                        "character_master_visual_gate_unavailable"
                    ]
                headless_review_errors: list[str] = []
                if (
                    isinstance(structure_receipt, dict)
                    and asset.get("character_mode") == "headless_safe"
                    and structure_receipt.get("status") == "applied_unverified"
                ):
                    _review, headless_review_errors = load_headless_review_authorization(
                        asset,
                        base_dir=base_dir,
                        image_evidence=evidence,
                    )
                structure_status_ok = (
                    isinstance(structure_receipt, dict)
                    and (
                        structure_receipt.get("status") == "pass"
                        or (
                            asset.get("character_mode") == "headless_safe"
                            and structure_receipt.get("status") == "applied_unverified"
                            and not headless_review_errors
                        )
                    )
                )
                if not structure_errors and character_probe_resolved_by_review(asset, structure_receipt, base_dir=base_dir):
                    structure_status_ok = True
                if structure_errors or headless_review_errors or not structure_status_ok:
                    errors.append(
                        f"required_character_master_visual_structure_invalid:{asset_id}:"
                        + ",".join(structure_errors or ["structure_not_passed"])
                    )

        manifest_cache: dict[
            str,
            tuple[dict[str, Any], dict[str, dict[str, Any]], str | None],
        ] = {}
        for asset in recorded_assets:
            if not all_images_required and asset.get("visual_qa_receipt") is None and (
                asset.get("status") == "generated_candidate"
                or (asset.get("action") == "reuse" and asset.get("status") in {"planned", "prompt_ready"})
            ):
                continue
            asset_id = asset["asset_id"]
            evidence = evidence_by_asset.get(asset_id)
            if evidence is None:
                continue
            visual_receipt = asset.get("visual_qa_receipt")
            if visual_receipt is None:
                errors.append(f"required_asset_not_visual_qa_approved:{asset_id}")
                continue
            visual_problem = validate_visual_qa_receipt(
                visual_receipt,
                asset=asset,
                evidence=evidence,
                truth_locked_at=str(truth_locked_at),
                base_dir=base_dir,
                payload=payload,
                evidence_by_asset=evidence_by_asset,
                manifest_cache=manifest_cache,
            )
            if visual_problem:
                errors.append(
                    f"required_asset_visual_qa_receipt_invalid:{asset_id}:{visual_problem}"
                )
        if all_images_required and any(
            isinstance(asset.get("visual_qa_receipt"), dict)
            and asset["visual_qa_receipt"].get("reviewer_type") == "executor"
            for asset in assets if asset.get("required") is True
        ):
            errors.append("executor_review_cannot_grant_visual_assets_complete")
        if all_images_required and any(
            isinstance(asset.get("visual_qa_receipt"), dict)
            and asset["visual_qa_receipt"].get("reviewer_type") == "independent_ai"
            for asset in assets
            if asset.get("required") is True
        ):
            errors.append(
                "independent_ai_review_cannot_grant_visual_assets_complete_without_human_or_authorized_review"
            )
        if completion_claim == "visual_assets_complete":
            errors.append(TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED)

        content_groups: dict[str, list[str]] = {}
        for asset_id, evidence in evidence_by_asset.items():
            content_groups.setdefault(evidence["pixel_sha256"], []).append(asset_id)
        for digest, group in content_groups.items():
            if len(group) < 2:
                continue
            roots: list[str] = []
            for asset_id in group:
                asset = asset_by_id[asset_id]
                inherited_same_content = any(
                    source in group for source in safe_id_list(asset.get("inherits_from"))
                )
                if asset.get("action") in {"derive", "reuse"} and inherited_same_content:
                    continue
                roots.append(asset_id)
            for duplicate in roots[1:]:
                errors.append(
                    f"required_asset_content_reused_without_dependency:{roots[0]}:{duplicate}:{digest[:12]}"
                )

    whole_film_visual_assets_complete = (
        scope == "whole_film"
        and completion_claim == "visual_assets_complete"
        and not errors
    )
    metrics = {
        "scope": scope,
        "duration_seconds": duration,
        "scenes": len(scene_ids),
        "characters": len(character_ids),
        "appearance_states": len(appearance_state_ids),
        "products": len(product_ids),
        "props": len(prop_ids),
        "shots": len(shot_ids),
        "rhythm_points": len(rhythm_ids),
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
        "evidence_files_verified": len(evidence_by_asset),
        "unique_file_hashes": len({item["sha256"] for item in evidence_by_asset.values()}),
        "unique_pixel_hashes": len(
            {item["pixel_sha256"] for item in evidence_by_asset.values()}
        ),
        "whole_film_visual_assets_complete": whole_film_visual_assets_complete,
    }
    return list(dict.fromkeys(errors)), metrics


def stamp_plan_evidence(
    payload: dict[str, Any],
    *,
    base_dir: Path,
    checked_at: str | None = None,
    asset_ids: list[str] | None = None,
    evidence_cache: dict[
        tuple[str, int, int, int, int, int],
        tuple[dict[str, Any] | None, str | None],
    ]
    | None = None,
) -> dict[str, Any]:
    checked_at = checked_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not valid_utc_timestamp(checked_at):
        raise ValueError("checked_at must be an RFC3339 UTC timestamp")
    stamped = copy.deepcopy(payload)
    semantic_probe = copy.deepcopy(stamped)
    asset_only = payload.get("scope") == "asset_only"
    semantic_probe["completion_claim"] = "asset_only_plan_complete" if asset_only else "none"
    # Validate truth before computing evidence; stamping itself never grants QA.
    semantic_errors, _ = validate_plan(
        semantic_probe, base_dir=base_dir, _validate_recorded_assets=False,
    )
    if semantic_errors:
        raise ValueError("cannot stamp an invalid visual plan: " + ";".join(semantic_errors))
    selected_ids: set[str] | None = None
    if asset_ids is not None:
        required_ids = {asset["asset_id"] for asset in stamped["assets"] if asset.get("required") is True}
        if (
            not isinstance(asset_ids, list) or not asset_ids
            or not all(isinstance(asset_id, str) for asset_id in asset_ids)
            or len(set(asset_ids)) != len(asset_ids) or not set(asset_ids).issubset(required_ids)
        ):
            raise ValueError("stamp asset_ids must be unique known required assets")
        selected_ids = set(asset_ids)
    for asset in stamped["assets"]:
        if asset.get("required") is not True:
            continue
        if selected_ids is not None and asset["asset_id"] not in selected_ids:
            continue
        if asset_only and asset.get("status") not in GENERATED_STATUSES and not asset.get("generated_file"):
            continue
        asset_id = asset["asset_id"]
        path = contained_file(asset.get("generated_file"), base_dir)
        if path is None:
            raise ValueError(f"cannot stamp missing or escaped file for {asset_id}")
        evidence, reason = inspect_raster_cached(path, evidence_cache)
        if evidence is None:
            raise ValueError(f"cannot stamp invalid raster for {asset_id}: {reason}")
        asset["generated_sha256"] = evidence["sha256"]
        asset["generated_pixel_sha256"] = evidence["pixel_sha256"]
        asset["generated_perceptual_hash"] = evidence["perceptual_hash"]
        asset["technical_receipt"] = make_technical_receipt(
            asset_id,
            evidence,
            checked_at=checked_at,
        )
    return stamped


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
            isinstance(expected_error, str) and expected_error in errors
        )
        if not passed:
            failures.append(f"{case_id}: expected {expected or expected_error}, got {errors}")
        results.append({"id": case_id, "passed": passed, "errors": errors, "metrics": metrics})

    schema = load_json(SCHEMA_PATH)
    schema_roles = set(schema["properties"]["assets"]["items"]["properties"]["role"]["enum"])
    if schema_roles != ROLES:
        failures.append("schema role enum drifted from validator")
    schema_claims = set(schema["properties"]["completion_claim"]["enum"])
    if schema_claims != COMPLETION_CLAIMS:
        failures.append("schema completion claim enum drifted from validator")
    schema_asset = schema["properties"]["assets"]["items"]
    if set(schema_asset["required"]) != ASSET_FIELDS:
        failures.append("schema asset fields drifted from validator")
    if not ASSET_OPTIONAL_FIELDS.issubset(schema_asset["properties"]):
        failures.append("schema character contract fields drifted from validator")
    schema_statuses = set(schema_asset["properties"]["status"]["enum"])
    if schema_statuses != {
        "planned",
        "prompt_ready",
        "generated_candidate",
        "user_locked",
        "reused_locked",
        "rejected",
    }:
        failures.append("schema asset status enum drifted from validator")
    schema_actions = set(schema_asset["properties"]["action"]["enum"])
    if schema_actions != {"reuse", "derive", "generate", "assemble"}:
        failures.append("schema asset action enum drifted from validator")
    schema_direct_roles = set(
        schema["properties"]["generation_units"]["items"]["properties"]
        ["direct_input_roles"]["items"]["enum"]
    )
    if schema_direct_roles != DIRECT_ROLES:
        failures.append("schema direct-input roles drifted from validator")
    if schema["properties"]["schema_version"].get("const") != SCHEMA_VERSION:
        failures.append("schema version drifted from validator")
    if (
        schema["properties"]["shot_truth"]["items"]["properties"]["timecode"].get("pattern")
        != TIMECODE_SCHEMA_PATTERN
    ):
        failures.append("schema timecode pattern drifted from validator")
    schema_technical_fields = set(schema["$defs"]["technicalReceipt"]["required"])
    if schema_technical_fields != {
        "receipt_version",
        "asset_id",
        "file_sha256",
        "pixel_sha256",
        "perceptual_hash",
        "ruleset",
        "checked_at",
        "decoder",
        "normalization_profile",
        "format",
        "width",
        "height",
        "status",
        "receipt_sha256",
    }:
        failures.append("schema technical receipt fields drifted from validator")
    if {
        schema["$defs"]["technicalReceipt"]["properties"]["format"].get("const")
    } != EVIDENCE_FORMATS:
        failures.append("schema evidence format drifted from validator")
    schema_visual_fields = set(schema["$defs"]["visualQaReceipt"]["required"])
    if schema_visual_fields != {
        "receipt_version",
        "asset_id",
        "file_sha256",
        "pixel_sha256",
        "truth_sha256",
        "ruleset",
        "reviewed_at",
        "reviewer_type",
        "reviewer_id",
        "review_task_id",
        "review_manifest_file",
        "review_manifest_sha256",
        "review_subject_sha256",
        "status",
        "receipt_sha256",
    }:
        failures.append("schema visual receipt fields drifted from validator")
    tvc_inventory = load_json(TVC_INVENTORY_PATH)
    tvc_plan = derive_plan(
        tvc_inventory,
        inventory_file=TVC_INVENTORY_PATH.name,
        base_dir=TVC_INVENTORY_PATH.parent,
    )
    tvc_errors, tvc_metrics = validate_plan(tvc_plan, base_dir=TVC_INVENTORY_PATH.parent)
    if tvc_errors:
        failures.append(f"TVC acceptance plan failed validation: {tvc_errors}")
    fallback_schema_control = not _stdlib_schema_errors(tvc_plan, schema)
    if not fallback_schema_control:
        failures.append("stdlib JSON Schema fallback rejected the valid TVC plan")
    tvc_checks = {
        "duration_at_least_60": tvc_plan.get("duration_seconds", 0) >= 60,
        "landscape_broadcast_profile": tvc_plan.get("delivery_profile", {}).get("medium") == "broadcast_tvc"
        and tvc_plan.get("delivery_profile", {}).get("aspect_ratio") == "16:9",
        "scenes_at_least_4": len(tvc_plan.get("scene_ids", [])) >= 4,
        "recurring_characters_at_least_2": len(tvc_plan.get("character_ids", [])) >= 2,
        "appearance_states_at_least_4": len(tvc_plan.get("appearance_state_ids", [])) >= 4,
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
        "character_identity_references": 4,
        "product_identity_boards": 1,
        "prop_continuity_boards": 2,
        "scene_references": 4,
        "style_boards": 1,
        "storyboard_frames": 24,
        "director_storyboard_pages": 4,
        "clean_video_inputs": 10,
        "assets": 50,
    }
    for key, expected in expected_tvc_asset_counts.items():
        if tvc_metrics.get(key) != expected:
            failures.append(f"TVC acceptance asset count drifted for {key}: {tvc_metrics.get(key)} != {expected}")

    mismatched_membership = copy.deepcopy(tvc_inventory)
    mismatched_membership["generation_units"][0]["shot_ids"] = ["S01", "S02"]
    try:
        derive_plan(
            mismatched_membership,
            inventory_file=TVC_INVENTORY_PATH.name,
            base_dir=TVC_INVENTORY_PATH.parent,
        )
    except ValueError as exc:
        membership_negative_control = "missing generation-unit membership" in str(exc)
    else:
        membership_negative_control = False
    if not membership_negative_control:
        failures.append("generation-unit membership negative control was accepted")

    cross_scene_unit = copy.deepcopy(tvc_inventory)
    cross_scene_unit["shots"][13]["scene_id"] = "riverside-dawn"
    try:
        derive_plan(
            cross_scene_unit,
            inventory_file=TVC_INVENTORY_PATH.name,
            base_dir=TVC_INVENTORY_PATH.parent,
        )
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
    duplicate_unit_errors, _ = validate_plan(duplicate_unit_membership, base_dir=TVC_INVENTORY_PATH.parent)
    duplicate_unit_membership_negative_control = (
        "generation_unit_shot_membership_invalid:S04:2" in duplicate_unit_errors
    )
    if not duplicate_unit_membership_negative_control:
        failures.append("duplicate generation-unit membership negative control was accepted")

    cross_scene_plan = copy.deepcopy(tvc_plan)
    cross_scene_plan["generation_units"][0]["shot_ids"].append("S07")
    cross_scene_plan["generation_units"][2]["shot_ids"].remove("S07")
    cross_scene_plan_errors, _ = validate_plan(cross_scene_plan, base_dir=TVC_INVENTORY_PATH.parent)
    cross_scene_plan_negative_control = any(
        error.startswith("generation_unit_crosses_scene_anchors:G01:") for error in cross_scene_plan_errors
    )
    if not cross_scene_plan_negative_control:
        failures.append("hand-authored cross-scene plan negative control was accepted")

    duplicate_direct_input = copy.deepcopy(tvc_plan)
    duplicate_clean = copy.deepcopy(
        next(asset for asset in duplicate_direct_input["assets"] if asset["asset_id"] == "clean-input-G01")
    )
    duplicate_clean["asset_id"] = "clean-input-G01-duplicate"
    duplicate_direct_input["assets"].append(duplicate_clean)
    duplicate_direct_errors, _ = validate_plan(duplicate_direct_input, base_dir=TVC_INVENTORY_PATH.parent)
    duplicate_direct_input_negative_control = (
        "generation_unit_direct_input_count_invalid:G01:2:1:1" in duplicate_direct_errors
    )
    if not duplicate_direct_input_negative_control:
        failures.append("duplicate required clean-input negative control was accepted")

    mismatched_storyboard = copy.deepcopy(tvc_plan)
    storyboard = next(
        asset
        for asset in mismatched_storyboard["assets"]
        if asset["asset_id"] == "storyboard-frame-S03"
    )
    storyboard["coverage"]["character_ids"] = []
    storyboard["coverage"]["product_ids"] = []
    storyboard["coverage"]["prop_ids"] = []
    storyboard["inherits_from"] = []
    storyboard_errors, _ = validate_plan(mismatched_storyboard, base_dir=TVC_INVENTORY_PATH.parent)
    shot_truth_negative_control = "storyboard_truth_mismatch:storyboard-frame-S03" in storyboard_errors
    if not shot_truth_negative_control:
        failures.append("per-shot truth erasure negative control was accepted")

    mismatched_storyboard_purpose = copy.deepcopy(tvc_plan)
    purpose_storyboard = next(
        asset
        for asset in mismatched_storyboard_purpose["assets"]
        if asset["asset_id"] == "storyboard-frame-S03"
    )
    purpose_storyboard["purpose"] = (
        "Visualize an unrelated tropical vacation with no connection to the approved shot."
    )
    purpose_errors, _ = validate_plan(
        mismatched_storyboard_purpose,
        base_dir=TVC_INVENTORY_PATH.parent,
    )
    storyboard_purpose_negative_control = (
        "asset_semantic_drift:storyboard-frame-S03:purpose" in purpose_errors
    )
    if not storyboard_purpose_negative_control:
        failures.append("storyboard purpose drifted away from its approved shot card")

    missing_director_dependencies = copy.deepcopy(tvc_plan)
    director = next(
        asset for asset in missing_director_dependencies["assets"]
        if asset["role"] == "professional_storyboard_motion_map"
    )
    director["inherits_from"] = []
    director_errors, _ = validate_plan(missing_director_dependencies, base_dir=TVC_INVENTORY_PATH.parent)
    director_dependency_negative_control = f"asset_dependency_mismatch:{director['asset_id']}" in director_errors
    if not director_dependency_negative_control:
        failures.append("director storyboard dependency negative control was accepted")

    missing_clean_dependencies = copy.deepcopy(tvc_plan)
    clean = next(asset for asset in missing_clean_dependencies["assets"] if asset["role"] in DIRECT_ROLES)
    clean["inherits_from"] = []
    clean_errors, _ = validate_plan(missing_clean_dependencies, base_dir=TVC_INVENTORY_PATH.parent)
    clean_dependency_negative_control = f"asset_dependency_mismatch:{clean['asset_id']}" in clean_errors
    if not clean_dependency_negative_control:
        failures.append("clean-input dependency negative control was accepted")

    wrong_clean_membership = copy.deepcopy(tvc_plan)
    wrong_clean = next(asset for asset in wrong_clean_membership["assets"] if asset["role"] in DIRECT_ROLES)
    wrong_clean["coverage"]["shot_ids"] = ["S24"]
    wrong_clean_errors, _ = validate_plan(wrong_clean_membership, base_dir=TVC_INVENTORY_PATH.parent)
    clean_input_membership_negative_control = any(
        error.startswith("clean_input_shot_outside_unit:") for error in wrong_clean_errors
    )
    if not clean_input_membership_negative_control:
        failures.append("clean input outside its generation unit was accepted")

    wrong_storyboard_scene = copy.deepcopy(tvc_plan)
    scene_storyboard = next(
        asset for asset in wrong_storyboard_scene["assets"] if asset["asset_id"] == "storyboard-frame-S01"
    )
    scene_storyboard["coverage"]["scene_ids"] = ["station-concourse-rain"]
    wrong_storyboard_errors, _ = validate_plan(wrong_storyboard_scene, base_dir=TVC_INVENTORY_PATH.parent)
    storyboard_scene_negative_control = "storyboard_truth_mismatch:storyboard-frame-S01" in wrong_storyboard_errors
    if not storyboard_scene_negative_control:
        failures.append("storyboard scene-anchor mismatch negative control was accepted")

    missing_scene_shot = copy.deepcopy(tvc_plan)
    scene_asset = next(
        asset for asset in missing_scene_shot["assets"]
        if asset["role"] == "scene_geography_camera_fov_reference"
    )
    removed_scene_shot = scene_asset["coverage"]["shot_ids"].pop()
    missing_scene_errors, _ = validate_plan(missing_scene_shot, base_dir=TVC_INVENTORY_PATH.parent)
    scene_shot_coverage_negative_control = (
        f"scene_reference_shot_coverage_invalid:{removed_scene_shot}:0" in missing_scene_errors
    )
    if not scene_shot_coverage_negative_control:
        failures.append("scene reference with missing shot coverage was accepted")

    duplicate_identity = copy.deepcopy(tvc_plan)
    duplicate_character = copy.deepcopy(
        next(
            asset
            for asset in duplicate_identity["assets"]
            if asset["asset_id"] == "identity-character-lin-che-lin-che-studio-coat"
        )
    )
    duplicate_character["asset_id"] = "identity-character-lin-che-studio-coat-duplicate"
    duplicate_identity["assets"].append(duplicate_character)
    duplicate_identity_errors, _ = validate_plan(duplicate_identity, base_dir=TVC_INVENTORY_PATH.parent)
    duplicate_identity_negative_control = (
        "appearance_state_identity_coverage_invalid:lin-che-studio-coat:2"
        in duplicate_identity_errors
    )
    if not duplicate_identity_negative_control:
        failures.append("duplicate required character identity negative control was accepted")

    accepted_plan = copy.deepcopy(tvc_plan)
    accepted_plan["completion_claim"] = "accepted"
    accepted_errors, _ = validate_plan(accepted_plan, base_dir=TVC_INVENTORY_PATH.parent)
    accepted_claim_negative_control = "completion_claim_invalid:accepted" in accepted_errors
    json_schema_negative_control = "json_schema:completion_claim:enum" in accepted_errors
    if not accepted_claim_negative_control:
        failures.append("visual plan accepted finished-delivery authority")
    if not json_schema_negative_control:
        failures.append("JSON Schema validation did not reject an invalid completion enum")

    fake_raster_negative_control = False
    reused_file_negative_control = False
    technical_receipt_binding_negative_control = False
    visual_qa_receipt_binding_negative_control = False
    receipt_timestamp_negative_control = False
    technical_stamp_cannot_complete_negative_control = False
    pixel_duplicate_metadata_negative_control = False
    shot_cards_staleness_negative_control = False
    evidence_root_negative_control = False
    inventory_staleness_negative_control = False
    creative_source_staleness_negative_control = False
    multiple_direct_inputs_positive_control = False
    multiple_direct_inputs_dependency_negative_control = False
    self_attested_visual_completion_rejected_control = False
    payload_reviewer_labels_cannot_grant_completion_control = False
    stdlib_png_decode_control = False
    stdlib_png_trns_negative_control = False
    user_locked_requires_review_negative_control = False
    visual_review_manifest_binding_negative_control = False
    decoder_portability_control = False
    visual_frame_aspect_negative_control = False
    non_png_evidence_negative_control = False
    manifest_snapshot_binding_control = False
    timecode_overlap_negative_control = False
    frame_alignment_negative_control = False
    sample_plan_positive_control = False
    with tempfile.TemporaryDirectory(prefix="dircreative-visual-asset-plan-") as raw:
        temp_root = Path(raw)
        inventory_file = temp_root / "inventory.json"
        shot_cards_fixture = load_json(
            TVC_INVENTORY_PATH.parent / str(tvc_inventory["shot_cards_file"])
        )
        creative_source_fixture = load_json(
            TVC_INVENTORY_PATH.parent / str(tvc_inventory["creative_source_file"])
        )
        creative_source_file = temp_root / str(tvc_inventory["creative_source_file"])
        creative_source_file.write_text(
            json.dumps(creative_source_fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        shot_cards_file = temp_root / str(tvc_inventory["shot_cards_file"])
        shot_cards_file.write_text(
            json.dumps(shot_cards_fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        overlap_cards = copy.deepcopy(shot_cards_fixture)
        overlap_cards["cards"][1]["timecode"] = "00:00.0-00:02.6"
        shot_cards_file.write_text(
            json.dumps(overlap_cards, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        overlap_inventory = copy.deepcopy(tvc_inventory)
        overlap_inventory["shot_cards_sha256"] = canonical_json_sha256(overlap_cards)
        try:
            derive_plan(
                overlap_inventory,
                inventory_file=inventory_file.name,
                base_dir=temp_root,
            )
        except ValueError as exc:
            timecode_overlap_negative_control = "timeline is discontinuous" in str(exc)
        if not timecode_overlap_negative_control:
            failures.append("overlapping shot-card timecodes were accepted")

        off_frame_cards = copy.deepcopy(shot_cards_fixture)
        off_frame_cards["cards"][0]["timecode"] = "00:00.0-00:02.41"
        off_frame_cards["cards"][0]["duration_seconds"] = 2.41
        off_frame_cards["cards"][1]["timecode"] = "00:02.41-00:05.0"
        off_frame_cards["cards"][1]["duration_seconds"] = 2.59
        shot_cards_file.write_text(
            json.dumps(off_frame_cards, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        off_frame_inventory = copy.deepcopy(tvc_inventory)
        off_frame_inventory["shot_cards_sha256"] = canonical_json_sha256(off_frame_cards)
        try:
            derive_plan(
                off_frame_inventory,
                inventory_file=inventory_file.name,
                base_dir=temp_root,
            )
        except ValueError as exc:
            frame_alignment_negative_control = "not frame aligned" in str(exc)
        if not frame_alignment_negative_control:
            failures.append("off-frame shot-card timecodes were accepted")

        shot_cards_file.write_text(
            json.dumps(shot_cards_fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        inventory_file.write_text(json.dumps(tvc_inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sample_inventory = copy.deepcopy(tvc_inventory)
        sample_inventory["scope"] = "representative_sample"
        inventory_file.write_text(
            json.dumps(sample_inventory, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sample_plan = derive_plan(
            sample_inventory,
            inventory_file=inventory_file.name,
            base_dir=temp_root,
        )
        sample_errors, _ = validate_plan(sample_plan, base_dir=temp_root)
        sample_plan_positive_control = (
            not sample_errors and sample_plan["completion_claim"] == "sample_plan_complete"
        )
        if not sample_plan_positive_control:
            failures.append(f"representative sample plan could not reach its bounded claim: {sample_errors}")
        inventory_file.write_text(
            json.dumps(tvc_inventory, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        creative_bound_plan = derive_plan(
            tvc_inventory,
            inventory_file=inventory_file.name,
            base_dir=temp_root,
        )
        stale_creative_source = copy.deepcopy(creative_source_fixture)
        stale_creative_source["brief"]["story"] = (
            "A different Mars mission story that must invalidate the old visual plan."
        )
        creative_source_file.write_text(
            json.dumps(stale_creative_source, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale_creative_errors, _ = validate_plan(
            creative_bound_plan,
            base_dir=temp_root,
        )
        creative_source_staleness_negative_control = any(
            "creative_source_sha256_mismatch" in error
            for error in stale_creative_errors
        )
        if not creative_source_staleness_negative_control:
            failures.append("a changed upstream brief/story/script left the old visual plan valid")
        creative_source_file.write_text(
            json.dumps(creative_source_fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stdlib_png_path = temp_root / "stdlib-control.png"
        stdlib_png_path.write_bytes(test_png_bytes(999))
        try:
            stdlib_png_decode_control = decode_png_stdlib(stdlib_png_path)["width"] == MIN_RASTER_WIDTH
        except (OSError, ValueError, zlib.error):
            stdlib_png_decode_control = False
        if not stdlib_png_decode_control:
            failures.append("stdlib PNG full-decode fallback rejected a valid raster")
        stdlib_trns_path = temp_root / "stdlib-trns-negative.png"
        stdlib_trns_path.write_bytes(png_with_trns_chunk(test_png_bytes(1000)))
        _, trns_reason = inspect_raster(stdlib_trns_path)
        stdlib_png_trns_negative_control = (
            trns_reason == "png_trns_normalization_unsupported"
        )
        if not stdlib_png_trns_negative_control:
            failures.append("PNG tRNS normalization drift was not rejected consistently")
        non_png_evidence_negative_control = EVIDENCE_FORMATS == {"PNG"}
        if Image is not None:
            jpeg_path = temp_root / "non-png-evidence-negative.jpg"
            Image.new("RGB", (MIN_RASTER_WIDTH, MIN_RASTER_HEIGHT), (40, 80, 120)).save(
                jpeg_path,
                format="JPEG",
            )
            jpeg_evidence, jpeg_reason = inspect_raster(jpeg_path)
            non_png_evidence_negative_control = (
                non_png_evidence_negative_control
                and jpeg_evidence is None
                and jpeg_reason == "format_not_allowed"
            )
        if not non_png_evidence_negative_control:
            failures.append("non-PNG media was accepted as portable completion evidence")
        generated = derive_plan(
            tvc_inventory,
            inventory_file=inventory_file.name,
            base_dir=temp_root,
        )
        generated["completion_claim"] = "visual_assets_complete"
        file_by_asset: dict[str, str] = {}
        source_index = 0
        import dircreative_character_master_visual_gate as character_visual_gate

        original_character_probe = character_visual_gate.run_probe
        original_swift_tool_identity = character_visual_gate.swift_tool_identity
        character_visual_gate.swift_tool_identity = lambda: {
            "path": "/fixture/swift",
            "sha256": "f" * 64,
            "signature_policy": "fixture",
        }
        for asset in generated["assets"]:
            target = temp_root / f"{asset['asset_id']}.png"
            if asset["role"] in DIRECT_ROLES:
                source_id = asset["inherits_from"][0]
                target.write_bytes((temp_root / file_by_asset[source_id]).read_bytes())
            else:
                target.write_bytes(test_png_bytes(source_index))
                source_index += 1
            asset["status"] = "generated_candidate"
            asset["generated_file"] = target.name
            file_by_asset[asset["asset_id"]] = target.name
        raster_cache: dict[
            tuple[str, int, int, int, int, int],
            tuple[dict[str, Any] | None, str | None],
        ] = {}
        generated = stamp_plan_evidence(
            generated,
            base_dir=temp_root,
            checked_at="2026-07-21T00:00:00Z",
            evidence_cache=raster_cache,
        )
        technical_only_errors, technical_only_metrics = validate_plan(
            generated,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        technical_stamp_cannot_complete_negative_control = (
            any(
                error.startswith("required_asset_not_visual_qa_approved:")
                for error in technical_only_errors
            )
            and technical_only_metrics.get("whole_film_visual_assets_complete") is False
        )
        if not technical_stamp_cannot_complete_negative_control:
            failures.append("technical raster stamping granted visual completion authority")

        user_locked_without_review = copy.deepcopy(generated)
        for asset in user_locked_without_review["assets"]:
            if asset.get("required") is True:
                asset["status"] = "user_locked"
        user_locked_errors, user_locked_metrics = validate_plan(
            user_locked_without_review,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        user_locked_requires_review_negative_control = (
            any(
                error.startswith("required_asset_not_visual_qa_approved:")
                for error in user_locked_errors
            )
            and user_locked_metrics.get("whole_film_visual_assets_complete") is False
        )
        if not user_locked_requires_review_negative_control:
            failures.append("a self-declared user_locked status bypassed visual review")

        review_evidence_by_asset: dict[str, dict[str, Any]] = {}
        review_entries: list[dict[str, Any]] = []
        for asset in generated["assets"]:
            if asset.get("required") is not True:
                continue
            evidence, reason = inspect_raster_cached(
                temp_root / asset["generated_file"],
                raster_cache,
            )
            if evidence is None:
                failures.append(
                    f"visual review setup could not inspect {asset['asset_id']}: {reason}"
                )
                continue
            review_evidence_by_asset[asset["asset_id"]] = evidence
            review_entries.append(
                {
                    "asset_id": asset["asset_id"],
                    "role": asset["role"],
                    "file_sha256": evidence["sha256"],
                    "pixel_sha256": evidence["pixel_sha256"],
                    "truth_sha256": asset["truth_sha256"],
                    "rubric_id": visual_review_rubric_id(asset["role"]),
                    "rubric": {
                        "truth_and_role_match": True,
                        "coverage_and_continuity_match": True,
                        "composition_readable": True,
                        "artifact_free": True,
                        "downstream_use_fit": True,
                    },
                    "decision": "pass",
                    "notes": "Fixture review confirms the role-bound visual evidence.",
                }
            )
        review_subject = visual_review_subject_sha256(generated)
        review_manifest = {
            "schema_version": VISUAL_REVIEW_MANIFEST_VERSION,
            "ruleset": VISUAL_QA_RULESET,
            "review_subject_sha256": review_subject,
            "reviewed_at": "2026-07-21T00:00:00Z",
            "reviewer_type": "independent_ai",
            "reviewer_id": "fixture-reviewer",
            "review_task_id": "visual-evidence-self-test",
            "assets": review_entries,
        }
        review_manifest_file = temp_root / "visual-review-manifest.json"
        atomic_write_json(review_manifest_file, review_manifest)
        review_manifest_hash = sha256_file(review_manifest_file)
        snapshot_manifest, snapshot_manifest_hash = load_json_snapshot(review_manifest_file)
        manifest_snapshot_binding_control = (
            snapshot_manifest == review_manifest
            and snapshot_manifest_hash == review_manifest_hash
        )
        if not manifest_snapshot_binding_control:
            failures.append("review manifest was not parsed from its hash-bound byte snapshot")
        for asset in generated["assets"]:
            if asset.get("required") is not True:
                continue
            evidence = review_evidence_by_asset[asset["asset_id"]]
            receipt = {
                "receipt_version": VISUAL_QA_RECEIPT_VERSION,
                "asset_id": asset["asset_id"],
                "file_sha256": evidence["sha256"],
                "pixel_sha256": evidence["pixel_sha256"],
                "truth_sha256": asset["truth_sha256"],
                "ruleset": VISUAL_QA_RULESET,
                "reviewed_at": review_manifest["reviewed_at"],
                "reviewer_type": review_manifest["reviewer_type"],
                "reviewer_id": review_manifest["reviewer_id"],
                "review_task_id": review_manifest["review_task_id"],
                "review_manifest_file": review_manifest_file.name,
                "review_manifest_sha256": review_manifest_hash,
                "review_subject_sha256": review_subject,
                "status": "visual_qa_pass",
            }
            receipt["receipt_sha256"] = receipt_sha256(receipt)
            asset["visual_qa_receipt"] = receipt
            if asset.get("role") == "character_identity_reference":
                from dircreative_character_master_visual_gate import make_receipt

                structure_probe = {
                    "backend": "apple-vision-human-body-pose-v1",
                    "body_pose_count": 5,
                    "face_count": 4,
                    "faces": [],
                    "human_rectangle_count": 4,
                    "full_body_count": 4,
                    "full_bodies": [
                        {
                            "center_x": 0.38 + index * 0.14,
                            "joint_span": 0.66,
                            "subject_height": 0.80,
                            "min_y": 0.08,
                            "max_y": 0.86,
                            "head_extent_above_shoulders": 0.11,
                            "subject_top_clearance": 0.04,
                            "subject_bottom_clearance": 0.04,
                            "visible_wrist_count": 2,
                            "visible_elbow_count": 2,
                            "visible_upper_limb_joint_count": 4,
                            "human_rect_index": index,
                            "human_rect_min_x": 0.33 + index * 0.14,
                            "human_rect_max_x": 0.43 + index * 0.14,
                        }
                        for index in range(4)
                    ],
                    "left_closeup_face_count": 1,
                    "left_closeup_faces": [
                        {
                            "center_x": 0.15,
                            "center_y": 0.55,
                            "width": 0.18,
                            "height": 0.28,
                        }
                    ],
                    "left_portrait_subject_height": 0.82,
                    "right_face_count": 3,
                    "right_full_height_component_count": 4,
                    "right_full_height_components": [
                        {
                            "center_x": 0.38 + index * 0.14,
                            "joint_span": 0.66,
                            "subject_height": 0.80,
                            "min_y": 0.08,
                            "max_y": 0.86,
                        }
                        for index in range(4)
                    ],
                }
                structure_receipt = make_receipt(
                    asset_id=asset["asset_id"],
                    asset_truth_sha256=asset["truth_sha256"],
                    image_evidence=evidence,
                    probe=structure_probe,
                    checked_at=review_manifest["reviewed_at"],
                    mode="headed_master",
                )
                atomic_write_json(
                    (temp_root / asset["generated_file"]).with_suffix(
                        ".character-master-visual.json"
                    ),
                    structure_receipt,
                )
        character_visual_gate.run_probe = lambda _image_bytes: (structure_probe, None)
        generated_errors, generated_metrics = validate_plan(
            generated,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        self_attested_visual_completion_rejected_control = (
            "independent_ai_review_cannot_grant_visual_assets_complete_without_human_or_authorized_review"
            in generated_errors
            and TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED in generated_errors
            and generated_metrics.get("whole_film_visual_assets_complete") is False
            and generated_metrics.get("evidence_files_verified") == len(generated["assets"])
        )
        if not self_attested_visual_completion_rejected_control:
            failures.append(
                "self-generated independent-AI receipts granted final visual completion: "
                f"{generated_errors}"
            )

        payload_reviewer_labels_cannot_grant_completion_control = True
        for reviewer_type in ("human", "authorized_reviewer"):
            self_claimed_review = copy.deepcopy(generated)
            self_claimed_manifest = copy.deepcopy(review_manifest)
            self_claimed_manifest["reviewer_type"] = reviewer_type
            self_claimed_manifest["reviewer_id"] = f"fixture-{reviewer_type}"
            self_claimed_manifest["review_task_id"] = f"self-claimed-{reviewer_type}"
            self_claimed_manifest_file = temp_root / f"{reviewer_type}-review-manifest.json"
            atomic_write_json(self_claimed_manifest_file, self_claimed_manifest)
            self_claimed_manifest_hash = sha256_file(self_claimed_manifest_file)
            for asset in self_claimed_review["assets"]:
                if asset.get("required") is not True:
                    continue
                receipt = asset["visual_qa_receipt"]
                receipt["reviewer_type"] = reviewer_type
                receipt["reviewer_id"] = self_claimed_manifest["reviewer_id"]
                receipt["review_task_id"] = self_claimed_manifest["review_task_id"]
                receipt["review_manifest_file"] = self_claimed_manifest_file.name
                receipt["review_manifest_sha256"] = self_claimed_manifest_hash
                receipt["receipt_sha256"] = receipt_sha256(receipt)
            self_claimed_errors, self_claimed_metrics = validate_plan(
                self_claimed_review,
                base_dir=temp_root,
                evidence_cache=raster_cache,
            )
            reviewer_label_blocked = (
                TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED in self_claimed_errors
                and self_claimed_metrics.get("whole_film_visual_assets_complete") is False
            )
            payload_reviewer_labels_cannot_grant_completion_control = (
                payload_reviewer_labels_cannot_grant_completion_control
                and reviewer_label_blocked
            )
        if not payload_reviewer_labels_cannot_grant_completion_control:
            failures.append(
                "payload reviewer labels granted completion without trusted host adoption"
            )

        vertical_plan = copy.deepcopy(generated)
        vertical_asset = next(
            asset for asset in vertical_plan["assets"] if asset["role"] == "storyboard_frame"
        )
        vertical_path = temp_root / "vertical-storyboard-control.png"
        vertical_path.write_bytes(test_png_bytes(2001, width=640, height=960))
        vertical_evidence, vertical_reason = inspect_raster(vertical_path)
        if vertical_evidence is None:
            failures.append(f"vertical raster control could not be decoded: {vertical_reason}")
        else:
            vertical_asset["generated_file"] = vertical_path.name
            vertical_asset["generated_sha256"] = vertical_evidence["sha256"]
            vertical_asset["generated_pixel_sha256"] = vertical_evidence["pixel_sha256"]
            vertical_asset["generated_perceptual_hash"] = vertical_evidence["perceptual_hash"]
            vertical_asset["technical_receipt"] = make_technical_receipt(
                vertical_asset["asset_id"],
                vertical_evidence,
                checked_at="2026-07-21T00:00:00Z",
            )
            vertical_errors, _ = validate_plan(
                vertical_plan,
                base_dir=temp_root,
                evidence_cache={},
            )
            visual_frame_aspect_negative_control = any(
                error.startswith("required_asset_delivery_aspect_ratio_mismatch:")
                for error in vertical_errors
            )
        if not visual_frame_aspect_negative_control:
            failures.append("a vertical storyboard raster satisfied a landscape TVC completion claim")

        fake_raster = copy.deepcopy(generated)
        fake_asset = fake_raster["assets"][0]
        fake_path = temp_root / fake_asset["generated_file"]
        original_bytes = fake_path.read_bytes()
        fake_bytes = padded_fake_png_bytes()
        fake_path.write_bytes(fake_bytes)
        fake_hash = hashlib.sha256(fake_bytes).hexdigest()
        fake_asset["generated_sha256"] = fake_hash
        fake_evidence = {
            "sha256": fake_hash,
            "pixel_sha256": "0" * 64,
            "perceptual_hash": "0" * 64,
            "format": "PNG",
            "width": 1920,
            "height": 1080,
            "decoder": "pillow-full-decode",
            "normalization_profile": NORMALIZATION_PROFILE,
        }
        fake_asset["generated_pixel_sha256"] = fake_evidence["pixel_sha256"]
        fake_asset["generated_perceptual_hash"] = fake_evidence["perceptual_hash"]
        fake_asset["technical_receipt"] = make_technical_receipt(
            fake_asset["asset_id"],
            fake_evidence,
            checked_at="2026-07-21T00:00:00Z",
        )
        fake_errors, _ = validate_plan(
            fake_raster,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        fake_raster_negative_control = any(
            error.startswith(f"required_asset_raster_invalid:{fake_asset['asset_id']}:")
            for error in fake_errors
        )
        if not fake_raster_negative_control:
            failures.append("header-only fake raster was accepted")
        fake_path.write_bytes(original_bytes)

        reused_content = copy.deepcopy(generated)
        first, second = reused_content["assets"][0], reused_content["assets"][1]
        second_path = temp_root / second["generated_file"]
        second_original = second_path.read_bytes()
        first_bytes = (temp_root / first["generated_file"]).read_bytes()
        second_path.write_bytes(
            png_with_text_metadata(first_bytes, "asset-id", second["asset_id"])
        )
        reused_content = stamp_plan_evidence(
            reused_content,
            base_dir=temp_root,
            checked_at="2026-07-21T00:00:00Z",
            evidence_cache=raster_cache,
        )
        reused_errors, _ = validate_plan(
            reused_content,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        reused_file_negative_control = any(
            error.startswith("required_asset_content_reused_without_dependency:")
            for error in reused_errors
        )
        first_reused_evidence, _ = inspect_raster_cached(
            temp_root / first["generated_file"],
            raster_cache,
        )
        second_reused_evidence, _ = inspect_raster_cached(second_path, raster_cache)
        pixel_duplicate_metadata_negative_control = (
            first_reused_evidence is not None
            and second_reused_evidence is not None
            and first_reused_evidence["sha256"] != second_reused_evidence["sha256"]
            and first_reused_evidence["pixel_sha256"]
            == second_reused_evidence["pixel_sha256"]
            and reused_file_negative_control
        )
        if not reused_file_negative_control:
            failures.append("same content at different independent asset paths was accepted")
        if not pixel_duplicate_metadata_negative_control:
            failures.append("same pixels with different PNG metadata escaped duplicate detection")
        second_path.write_bytes(second_original)

        bad_receipt = copy.deepcopy(generated)
        bad_technical = bad_receipt["assets"][0]["technical_receipt"]
        bad_technical["normalization_profile"] = "rgba8-incompatible-v9"
        bad_technical["receipt_sha256"] = receipt_sha256(bad_technical)
        receipt_errors, _ = validate_plan(
            bad_receipt,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        technical_receipt_binding_negative_control = any(
            error.startswith("required_asset_technical_receipt_invalid:")
            and error.endswith(":normalization_profile")
            for error in receipt_errors
        )
        if not technical_receipt_binding_negative_control:
            failures.append("a mismatched pixel normalization profile was accepted")

        portable_decoder_receipt = copy.deepcopy(generated)
        portable_technical = portable_decoder_receipt["assets"][0]["technical_receipt"]
        portable_technical["decoder"] = (
            "stdlib-png-full-decode"
            if portable_technical["decoder"] == "pillow-full-decode"
            else "pillow-full-decode"
        )
        portable_technical["receipt_sha256"] = receipt_sha256(portable_technical)
        portable_errors, portable_metrics = validate_plan(
            portable_decoder_receipt,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        decoder_portability_control = (
            portable_errors
            == [
                "independent_ai_review_cannot_grant_visual_assets_complete_without_human_or_authorized_review",
                TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED,
            ]
            and portable_metrics.get("whole_film_visual_assets_complete") is False
            and portable_metrics.get("evidence_files_verified") == len(portable_decoder_receipt["assets"])
        )
        if not decoder_portability_control:
            failures.append("equivalent decoder provenance broke a normalized receipt")

        bad_visual_receipt = copy.deepcopy(generated)
        visual_receipt = bad_visual_receipt["assets"][0]["visual_qa_receipt"]
        visual_receipt["truth_sha256"] = "0" * 64
        visual_receipt["receipt_sha256"] = receipt_sha256(visual_receipt)
        visual_receipt_errors, _ = validate_plan(
            bad_visual_receipt,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        visual_qa_receipt_binding_negative_control = any(
            error.startswith("required_asset_visual_qa_receipt_invalid:")
            and error.endswith(":truth_hash")
            for error in visual_receipt_errors
        )
        if not visual_qa_receipt_binding_negative_control:
            failures.append("rehashed visual QA receipt escaped shot-truth binding")

        bad_manifest_binding = copy.deepcopy(generated)
        manifest_receipt = bad_manifest_binding["assets"][0]["visual_qa_receipt"]
        manifest_receipt["review_manifest_sha256"] = "0" * 64
        manifest_receipt["receipt_sha256"] = receipt_sha256(manifest_receipt)
        manifest_binding_errors, _ = validate_plan(
            bad_manifest_binding,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        visual_review_manifest_binding_negative_control = any(
            error.startswith("required_asset_visual_qa_receipt_invalid:")
            and error.endswith(":review_manifest_hash")
            for error in manifest_binding_errors
        )
        if not visual_review_manifest_binding_negative_control:
            failures.append("visual QA receipt escaped its external manifest hash")

        future_receipt = copy.deepcopy(generated)
        future_technical = future_receipt["assets"][0]["technical_receipt"]
        future_technical["checked_at"] = "2099-12-31T23:59:59Z"
        future_technical["receipt_sha256"] = receipt_sha256(future_technical)
        future_errors, _ = validate_plan(
            future_receipt,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        receipt_timestamp_negative_control = any(
            error.startswith("required_asset_technical_receipt_invalid:")
            and error.endswith(":timestamp")
            for error in future_errors
        )
        if not receipt_timestamp_negative_control:
            failures.append("rehashed future-dated technical receipt was accepted")

        escaped_path = copy.deepcopy(generated)
        escaped_path["assets"][0]["generated_file"] = str(
            (temp_root / escaped_path["assets"][0]["generated_file"]).resolve()
        )
        escaped_errors, _ = validate_plan(
            escaped_path,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        evidence_root_negative_control = any(
            error.startswith("required_asset_file_missing_or_outside_evidence_root:")
            for error in escaped_errors
        )
        if not evidence_root_negative_control:
            failures.append("absolute evidence path escaped the package root")

        stale_plan = copy.deepcopy(generated)
        stale_inventory = copy.deepcopy(tvc_inventory)
        stale_inventory["truth_revision"] = "approved-r2"
        inventory_file.write_text(json.dumps(stale_inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stale_errors, _ = validate_plan(
            stale_plan,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        inventory_staleness_negative_control = "inventory_sha256_mismatch" in stale_errors
        if not inventory_staleness_negative_control:
            failures.append("stale plan survived an inventory revision")
        inventory_file.write_text(json.dumps(tvc_inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        stale_shot_cards_plan = copy.deepcopy(generated)
        stale_shot_cards = copy.deepcopy(shot_cards_fixture)
        stale_shot_cards["cards"][0]["action"] = (
            "An unrelated tropical holiday replaces the approved broadcast action."
        )
        shot_cards_file.write_text(
            json.dumps(stale_shot_cards, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale_shot_cards_errors, _ = validate_plan(
            stale_shot_cards_plan,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        shot_cards_staleness_negative_control = any(
            "shot_cards_sha256_mismatch" in error for error in stale_shot_cards_errors
        )
        if not shot_cards_staleness_negative_control:
            failures.append("approved shot cards changed without invalidating the visual plan")
        shot_cards_file.write_text(
            json.dumps(shot_cards_fixture, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        character_visual_gate.run_probe = original_character_probe
        character_visual_gate.swift_tool_identity = original_swift_tool_identity

        multi_inventory = copy.deepcopy(tvc_inventory)
        multi_inventory["generation_units"][0]["direct_input_min"] = 2
        multi_inventory["generation_units"][0]["direct_input_max"] = 2
        multi_inventory["generation_units"][0]["direct_input_roles"] = [
            "clean_first_frame",
            "clean_end_frame",
        ]
        inventory_file.write_text(json.dumps(multi_inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        multi_plan = derive_plan(
            multi_inventory,
            inventory_file=inventory_file.name,
            base_dir=temp_root,
        )
        multi_errors, multi_metrics = validate_plan(multi_plan, base_dir=temp_root)
        multiple_direct_inputs_positive_control = not multi_errors and multi_metrics.get("clean_video_inputs") == 11
        if not multiple_direct_inputs_positive_control:
            failures.append(f"multiple direct-input strategy failed: {multi_errors}")
        broken_multi_plan = copy.deepcopy(multi_plan)
        second_multi_input = next(
            asset
            for asset in broken_multi_plan["assets"]
            if asset["asset_id"] == "clean-input-G01-02"
        )
        second_multi_input["inherits_from"] = []
        broken_multi_errors, _ = validate_plan(broken_multi_plan, base_dir=temp_root)
        multiple_direct_inputs_dependency_negative_control = (
            "clean_input_dependency_mismatch:clean-input-G01-02" in broken_multi_errors
        )
        if not multiple_direct_inputs_dependency_negative_control:
            failures.append("optional second direct input lost its exact storyboard dependency")

    return failures, {
        "cases": results,
        "tvc_acceptance": tvc_checks,
        "tvc_metrics": tvc_metrics,
        "generation_unit_membership_negative_control": membership_negative_control,
        "generation_unit_scene_coherence_negative_control": scene_coherence_negative_control,
        "duplicate_unit_membership_negative_control": duplicate_unit_membership_negative_control,
        "cross_scene_plan_negative_control": cross_scene_plan_negative_control,
        "duplicate_direct_input_negative_control": duplicate_direct_input_negative_control,
        "shot_truth_negative_control": shot_truth_negative_control,
        "storyboard_purpose_negative_control": storyboard_purpose_negative_control,
        "director_dependency_negative_control": director_dependency_negative_control,
        "clean_dependency_negative_control": clean_dependency_negative_control,
        "clean_input_membership_negative_control": clean_input_membership_negative_control,
        "storyboard_scene_negative_control": storyboard_scene_negative_control,
        "scene_shot_coverage_negative_control": scene_shot_coverage_negative_control,
        "duplicate_identity_negative_control": duplicate_identity_negative_control,
        "vertical_tvc_negative_control": vertical_tvc_negative_control,
        "accepted_claim_negative_control": accepted_claim_negative_control,
        "json_schema_negative_control": json_schema_negative_control,
        "self_attested_visual_completion_rejected_control": self_attested_visual_completion_rejected_control,
        "payload_reviewer_labels_cannot_grant_completion_control": payload_reviewer_labels_cannot_grant_completion_control,
        "technical_stamp_cannot_complete_negative_control": technical_stamp_cannot_complete_negative_control,
        "fake_raster_negative_control": fake_raster_negative_control,
        "reused_file_negative_control": reused_file_negative_control,
        "pixel_duplicate_metadata_negative_control": pixel_duplicate_metadata_negative_control,
        "technical_receipt_binding_negative_control": technical_receipt_binding_negative_control,
        "visual_qa_receipt_binding_negative_control": visual_qa_receipt_binding_negative_control,
        "visual_review_manifest_binding_negative_control": visual_review_manifest_binding_negative_control,
        "user_locked_requires_review_negative_control": user_locked_requires_review_negative_control,
        "decoder_portability_control": decoder_portability_control,
        "visual_frame_aspect_negative_control": visual_frame_aspect_negative_control,
        "non_png_evidence_negative_control": non_png_evidence_negative_control,
        "manifest_snapshot_binding_control": manifest_snapshot_binding_control,
        "receipt_timestamp_negative_control": receipt_timestamp_negative_control,
        "evidence_root_negative_control": evidence_root_negative_control,
        "inventory_staleness_negative_control": inventory_staleness_negative_control,
        "creative_source_staleness_negative_control": creative_source_staleness_negative_control,
        "shot_cards_staleness_negative_control": shot_cards_staleness_negative_control,
        "multiple_direct_inputs_positive_control": multiple_direct_inputs_positive_control,
        "multiple_direct_inputs_dependency_negative_control": multiple_direct_inputs_dependency_negative_control,
        "stdlib_png_decode_control": stdlib_png_decode_control,
        "stdlib_png_trns_negative_control": stdlib_png_trns_negative_control,
        "stdlib_schema_fallback_control": fallback_schema_control,
        "timecode_overlap_negative_control": timecode_overlap_negative_control,
        "frame_alignment_negative_control": frame_alignment_negative_control,
        "sample_plan_positive_control": sample_plan_positive_control,
    }


def relative_inventory_path(inventory_path: Path, plan_dir: Path) -> str:
    try:
        return inventory_path.resolve(strict=True).relative_to(
            plan_dir.resolve(strict=False)
        ).as_posix()
    except (OSError, ValueError) as exc:
        raise ValueError("inventory must be inside the persisted plan evidence root") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Derive, stamp, and validate DIRcreative whole-film visual asset coverage."
    )
    parser.add_argument("--plan", type=Path, help="JSON visual asset plan to validate or stamp.")
    parser.add_argument("--inventory", type=Path, help="JSON film inventory to expand and validate.")
    parser.add_argument("--output", type=Path, help="Write an expanded plan or stamped evidence plan.")
    parser.add_argument(
        "--stamp-evidence",
        action="store_true",
        help=(
            "Full-decode required rasters, or only repeated --asset-id selections, "
            "and bind technical receipts without granting visual QA approval."
        ),
    )
    parser.add_argument("--checked-at", help="RFC3339 UTC timestamp for reproducible evidence stamping.")
    parser.add_argument("--asset-id", action="append", dest="asset_ids", help="Stamp only this existing required asset; repeat for a partial batch. Never grants visual approval.")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    selected = sum(bool(value) for value in (args.self_test, args.plan, args.inventory))
    if selected != 1:
        parser.error("choose exactly one of --self-test, --plan, or --inventory")
    if args.stamp_evidence and (not args.plan or not args.output):
        parser.error("--stamp-evidence requires --plan and --output")
    if args.output and not args.inventory and not args.stamp_evidence:
        parser.error("--output requires --inventory or --stamp-evidence")
    if args.checked_at and not args.stamp_evidence:
        parser.error("--checked-at requires --stamp-evidence")
    if args.asset_ids is not None and not args.stamp_evidence:
        parser.error("--asset-id requires --stamp-evidence")
    try:
        if args.self_test:
            errors, report = self_test()
        elif args.plan:
            plan_path = args.plan.expanduser().resolve()
            payload = load_json(plan_path)
            if args.stamp_evidence:
                output = args.output.expanduser().resolve()
                if output.parent != plan_path.parent:
                    raise ValueError("stamped plan output must stay in the same evidence root")
                payload = stamp_plan_evidence(
                    payload,
                    base_dir=plan_path.parent,
                    checked_at=args.checked_at,
                    asset_ids=args.asset_ids,
                )
                errors, metrics = validate_plan(payload, base_dir=plan_path.parent)
                if not errors:
                    atomic_write_json(output, payload)
                report = {"plan": str(plan_path), "output": str(output), "metrics": metrics}
            else:
                errors, metrics = validate_plan(payload, base_dir=plan_path.parent)
                report = {"plan": str(plan_path), "metrics": metrics}
        else:
            inventory_path = args.inventory.expanduser().resolve()
            inventory = load_json(inventory_path)
            plan_dir = args.output.expanduser().resolve().parent if args.output else inventory_path.parent
            inventory_file = relative_inventory_path(inventory_path, plan_dir)
            expanded = derive_plan(
                inventory,
                inventory_file=inventory_file,
                base_dir=plan_dir,
            )
            errors, metrics = validate_plan(expanded, base_dir=plan_dir)
            report = {"inventory": str(inventory_path), "metrics": metrics}
            if args.output:
                output = args.output.expanduser().resolve()
                atomic_write_json(output, expanded)
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
