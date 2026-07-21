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
SCHEMA_VERSION = "2.2"
FUTURE_TIMESTAMP_TOLERANCE_SECONDS = 300

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
DELIVERY_FRAME_ROLES = {
    "scene_geography_camera_fov_reference",
    "lighting_material_style_board",
    "storyboard_frame",
    *DIRECT_ROLES,
}
DELIVERY_ASPECT_RATIO_TOLERANCE = 0.02
GENERATED_STATUSES = {"generated_candidate", "user_locked", "reused_locked"}
COMPLETION_CLAIMS = {
    "none",
    "plan_complete",
    "sample_plan_complete",
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
}
COVERAGE_FIELDS = {
    "scene_ids",
    "character_ids",
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


def normalized_raster_evidence(width: int, height: int, rgba: bytes) -> dict[str, str]:
    expected_bytes = width * height * 4
    if len(rgba) != expected_bytes or expected_bytes > MAX_DECODED_BYTES:
        raise ValueError("normalized_pixel_buffer_invalid")
    return {
        "pixel_sha256": normalized_pixel_sha256(width, height, rgba),
        "perceptual_hash": normalized_perceptual_hash(width, height, rgba),
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


def inspect_raster(path: Path) -> tuple[dict[str, Any] | None, str | None]:
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
    if result["width"] < MIN_RASTER_WIDTH or result["height"] < MIN_RASTER_HEIGHT:
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


def visual_review_subject_sha256(payload: dict[str, Any]) -> str:
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
        if isinstance(asset, dict) and asset.get("required") is True
    ]
    assets.sort(key=lambda item: str(item.get("asset_id")))
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
    if not isinstance(manifest, dict) or set(manifest) != root_fields:
        return {}, "manifest_shape"
    subject_hash = visual_review_subject_sha256(payload)
    root_checks = {
        "manifest_version": manifest.get("schema_version")
        == VISUAL_REVIEW_MANIFEST_VERSION,
        "manifest_ruleset": manifest.get("ruleset") == VISUAL_QA_RULESET,
        "manifest_subject": manifest.get("review_subject_sha256") == subject_hash,
        "manifest_timestamp": timestamp_in_review_window(
            manifest.get("reviewed_at"),
            not_before=truth_locked_at,
        ),
        "manifest_reviewer_type": manifest.get("reviewer_type")
        in {"human", "independent_ai", "authorized_reviewer"},
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
    required_ids = sorted(str(asset.get("asset_id")) for asset in required_assets)
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
        if not isinstance(entry, dict) or set(entry) != entry_fields:
            return {}, "manifest_entry_shape"
        asset_id = str(entry["asset_id"])
        asset = asset_map[asset_id]
        evidence = evidence_by_asset.get(asset_id)
        rubric = entry.get("rubric")
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
        in {"human", "independent_ai", "authorized_reviewer"},
        "reviewer_id": isinstance(receipt.get("reviewer_id"), str)
        and ID_RE.fullmatch(receipt["reviewer_id"]) is not None,
        "review_task_id": isinstance(receipt.get("review_task_id"), str)
        and ID_RE.fullmatch(receipt["review_task_id"]) is not None,
        "review_manifest_file": isinstance(receipt.get("review_manifest_file"), str)
        and bool(receipt["review_manifest_file"]),
        "review_manifest_sha256": isinstance(receipt.get("review_manifest_sha256"), str)
        and SHA256_RE.fullmatch(receipt["review_manifest_sha256"]) is not None,
        "review_subject_sha256": receipt.get("review_subject_sha256")
        == visual_review_subject_sha256(payload),
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
        "generated_file": "",
        "generated_sha256": "",
        "generated_pixel_sha256": "",
        "generated_perceptual_hash": "",
        "truth_sha256": canonical_json_sha256(truth_payload),
        "technical_receipt": None,
        "visual_qa_receipt": None,
    }


def validate_delivery_profile(profile: Any, errors: list[str]) -> None:
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
        "shot_cards_file",
        "shot_cards_sha256",
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
    if set(inventory) != required or inventory.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("visual asset inventory field set or version is invalid")
    for field in ("project_id", "truth_revision"):
        if not isinstance(inventory.get(field), str) or not ID_RE.fullmatch(inventory[field]):
            raise ValueError(f"inventory {field} is invalid")
    if inventory.get("scope") not in {"whole_film", "sequence", "representative_sample"}:
        raise ValueError("inventory scope is invalid")
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
    if (
        set(shot_cards) != {"schema_version", "inventory", "cards"}
        or shot_cards.get("schema_version") != "1.0"
        or not isinstance(shot_cards.get("inventory"), str)
    ):
        raise ValueError("shot cards root is invalid")
    duration = inventory.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        raise ValueError("inventory duration is invalid")
    profile_errors: list[str] = []
    validate_delivery_profile(inventory.get("delivery_profile"), profile_errors)
    if profile_errors:
        raise ValueError("inventory delivery profile is invalid: " + ",".join(profile_errors))
    if not isinstance(inventory.get("style_reference_required"), bool):
        raise ValueError("inventory style-reference policy is invalid")
    rhythm_ids = inventory.get("rhythm_point_ids")
    if (
        not isinstance(rhythm_ids, list)
        or not rhythm_ids
        or not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in rhythm_ids)
        or duplicate_values(rhythm_ids)
    ):
        raise ValueError("inventory rhythm points are invalid")

    def entity_map(label: str) -> dict[str, dict[str, Any]]:
        values = inventory.get(label)
        if not isinstance(values, list):
            raise ValueError(f"inventory {label} must be a list")
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
                or PLACEHOLDER_RE.search(purpose)
            ):
                raise ValueError(f"inventory {label} identity or purpose is invalid")
            result[entity_id] = item
        return result

    character_map = entity_map("characters")
    product_map = entity_map("products")
    prop_map = entity_map("props")
    scene_map = entity_map("scenes")

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
        if not isinstance(unit, dict) or set(unit) != expected:
            raise ValueError("inventory generation unit is invalid")
        unit_id = unit.get("unit_id")
        shot_ids = unit.get("shot_ids")
        minimum = unit.get("direct_input_min")
        maximum = unit.get("direct_input_max")
        roles = unit.get("direct_input_roles")
        reason = unit.get("direct_input_not_required_reason")
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
            "product_ids",
            "prop_ids",
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
        if not isinstance(card, dict) or set(card) != card_fields:
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

    shot_truth = [
        {
            "shot_id": shot_id,
            "scene_id": shot_map[shot_id]["scene_id"],
            "character_ids": list(shot_map[shot_id]["character_ids"]),
            "product_ids": list(shot_map[shot_id]["product_ids"]),
            "prop_ids": list(shot_map[shot_id]["prop_ids"]),
            "generation_unit_id": shot_map[shot_id]["generation_unit_id"],
            "narrative_purpose": shot_map[shot_id]["narrative_purpose"],
            "timecode": card_map[shot_id]["timecode"],
            "duration_seconds": card_map[shot_id]["duration_seconds"],
            "shot_design": card_map[shot_id]["shot_design"],
            "action": card_map[shot_id]["action"],
            "sound_edit": card_map[shot_id]["sound_edit"],
            "continuity_model": card_map[shot_id]["continuity_model"],
        }
        for shot_id in shot_ids
    ]

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


def derive_plan(
    inventory: dict[str, Any],
    *,
    inventory_file: str,
    base_dir: Path,
) -> dict[str, Any]:
    parsed = parse_inventory(inventory, base_dir=base_dir)
    character_map = parsed["character_map"]
    product_map = parsed["product_map"]
    prop_map = parsed["prop_map"]
    scene_map = parsed["scene_map"]
    unit_map = parsed["unit_map"]
    shot_map = parsed["shot_map"]
    shot_ids = parsed["shot_ids"]
    shot_truth = parsed["shot_truth"]
    shot_truth_map = {item["shot_id"]: item for item in shot_truth}

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
        assets.append(
            planned_asset(
                asset_id,
                "character_identity_reference",
                item["purpose"],
                truth_payload={
                    "entity": item,
                    "shots": [
                        shot_truth_map[shot_id]
                        for shot_id in shot_ids
                        if entity_id in shot_map[shot_id]["character_ids"]
                    ],
                },
                coverage=coverage,
                inherits_from=[],
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
                truth_payload={"scenes": list(scene_map.values()), "shots": shot_truth},
                coverage=coverage,
                inherits_from=list(scene_asset_ids.values()),
            )
        )

    for shot_id in shot_ids:
        shot = shot_map[shot_id]
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
            )
        )

    for page_index in range(0, len(shot_ids), 6):
        page_shots = shot_ids[page_index : page_index + 6]
        page_number = page_index // 6 + 1
        coverage = empty_coverage()
        coverage["scene_ids"] = list(dict.fromkeys(shot_map[item]["scene_id"] for item in page_shots))
        coverage["character_ids"] = list(
            dict.fromkeys(value for item in page_shots for value in shot_map[item]["character_ids"])
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
                    inherits_from=[f"storyboard-frame-{selected_shot}"],
                    action="derive",
                    planning_only=False,
                )
            )

    output_units = [
        {
            "unit_id": unit["unit_id"],
            "shot_ids": list(unit["shot_ids"]),
            "direct_input_min": unit["direct_input_min"],
            "direct_input_max": unit["direct_input_max"],
            "direct_input_roles": list(unit["direct_input_roles"]),
            "direct_input_not_required_reason": unit["direct_input_not_required_reason"],
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
        "shot_cards_file": inventory["shot_cards_file"],
        "shot_cards_sha256": parsed["shot_cards_sha256"],
        "shot_truth_sha256": parsed["shot_truth_sha256"],
        "scope": inventory["scope"],
        "duration_seconds": inventory["duration_seconds"],
        "delivery_profile": copy.deepcopy(inventory["delivery_profile"]),
        "scene_ids": list(scene_map),
        "character_ids": list(character_map),
        "product_ids": list(product_map),
        "prop_ids": list(prop_map),
        "shot_ids": list(shot_ids),
        "shot_truth": shot_truth,
        "rhythm_point_ids": list(inventory["rhythm_point_ids"]),
        "style_reference_required": inventory["style_reference_required"],
        "generation_units": output_units,
        "assets": assets,
        "completion_claim": (
            "sample_plan_complete"
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
    if scope not in {"whole_film", "sequence", "representative_sample"}:
        errors.append("scope_invalid")
    duration = payload.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
        errors.append("duration_invalid")
    completion_claim = payload.get("completion_claim")
    if completion_claim not in COMPLETION_CLAIMS:
        errors.append(f"completion_claim_invalid:{completion_claim}")
    delivery_profile = payload.get("delivery_profile")
    validate_delivery_profile(delivery_profile, errors)
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
    for field in ("shot_cards_sha256", "shot_truth_sha256"):
        value = payload.get(field)
        if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
            errors.append(f"{field}_invalid")
    if expected_plan is not None:
        for field in (
            "project_id",
            "truth_revision",
            "truth_locked_at",
            "inventory_sha256",
            "shot_cards_file",
            "shot_cards_sha256",
            "shot_truth_sha256",
            "scope",
            "duration_seconds",
            "delivery_profile",
            "scene_ids",
            "character_ids",
            "product_ids",
            "prop_ids",
            "shot_ids",
            "shot_truth",
            "rhythm_point_ids",
            "style_reference_required",
            "generation_units",
        ):
            if payload.get(field) != expected_plan.get(field):
                errors.append(f"plan_inventory_field_mismatch:{field}")

    scene_ids = validate_id_list(
        payload.get("scene_ids"),
        "scene_ids",
        errors,
        nonempty=scope != "representative_sample",
    )
    character_ids = validate_id_list(payload.get("character_ids"), "character_ids", errors)
    product_ids = validate_id_list(payload.get("product_ids"), "product_ids", errors)
    prop_ids = validate_id_list(payload.get("prop_ids"), "prop_ids", errors)
    shot_ids = validate_id_list(payload.get("shot_ids"), "shot_ids", errors, nonempty=True)
    rhythm_ids = validate_id_list(
        payload.get("rhythm_point_ids"),
        "rhythm_point_ids",
        errors,
        nonempty=True,
    )
    if len(rhythm_ids) < len(shot_ids):
        errors.append("rhythm_points_fewer_than_shots")
    if not isinstance(payload.get("style_reference_required"), bool):
        errors.append("style_reference_required_invalid")

    raw_truth = payload.get("shot_truth")
    truth_map: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_truth, list) or not raw_truth:
        errors.append("shot_truth_missing")
        raw_truth = []
    for index, truth in enumerate(raw_truth):
        expected_fields = {
            "shot_id",
            "scene_id",
            "character_ids",
            "product_ids",
            "prop_ids",
            "generation_unit_id",
            "narrative_purpose",
            "timecode",
            "duration_seconds",
            "shot_design",
            "action",
            "sound_edit",
            "continuity_model",
        }
        if not isinstance(truth, dict) or set(truth) != expected_fields:
            errors.append(f"shot_truth_invalid:{index}")
            continue
        shot_id = truth.get("shot_id")
        if not isinstance(shot_id, str) or not ID_RE.fullmatch(shot_id) or shot_id in truth_map:
            errors.append(f"shot_truth_id_invalid:{index}")
            continue
        for field in ("character_ids", "product_ids", "prop_ids"):
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
    if not isinstance(generation_units, list) or not generation_units:
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
        if not isinstance(unit, dict) or set(unit) != expected_fields:
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
        "product_ids": set(product_ids),
        "prop_ids": set(prop_ids),
        "shot_ids": set(shot_ids),
        "generation_unit_ids": set(unit_ids),
    }
    for index, asset in enumerate(assets_raw):
        if not isinstance(asset, dict) or set(asset) != ASSET_FIELDS:
            errors.append(f"asset_field_set_mismatch:{index}")
            continue
        asset_id = asset.get("asset_id")
        if not isinstance(asset_id, str) or not ID_RE.fullmatch(asset_id):
            errors.append(f"asset_id_invalid:{index}")
            continue
        assets.append(asset)
        asset_ids.append(asset_id)
        role = asset.get("role")
        if role not in ROLES:
            errors.append(f"asset_role_invalid:{asset_id}")
            continue
        role_assets[role].append(asset)
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
                    "product_ids": list(truth["product_ids"]),
                    "prop_ids": list(truth["prop_ids"]),
                    "shot_ids": [truth["shot_id"]],
                    "generation_unit_ids": [truth["generation_unit_id"]],
                }
                if coverage != expected_coverage:
                    errors.append(f"storyboard_truth_mismatch:{asset_id}")
        if role == "professional_storyboard_motion_map":
            if asset.get("action") != "assemble":
                errors.append(f"director_storyboard_must_assemble:{asset_id}")
            page_shots = safe_coverage_ids(asset, "shot_ids")
            if not 1 <= len(page_shots) <= 6:
                errors.append(f"director_storyboard_page_density_invalid:{asset_id}")
            elif all(shot_id in truth_map for shot_id in page_shots):
                expected_page_coverage = {
                    "scene_ids": list(dict.fromkeys(truth_map[item]["scene_id"] for item in page_shots)),
                    "character_ids": list(
                        dict.fromkeys(value for item in page_shots for value in truth_map[item]["character_ids"])
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
                    "product_ids": list(truth["product_ids"]),
                    "prop_ids": list(truth["prop_ids"]),
                    "shot_ids": [truth["shot_id"]],
                    "generation_unit_ids": [truth["generation_unit_id"]],
                }
                if coverage != expected_clean_coverage:
                    errors.append(f"clean_input_truth_mismatch:{asset_id}")
                if asset.get("inherits_from") != [f"storyboard-frame-{truth['shot_id']}"]:
                    errors.append(f"clean_input_dependency_mismatch:{asset_id}")

    for duplicate in duplicate_values(asset_ids):
        errors.append(f"duplicate_asset_id:{duplicate}")
    asset_by_id = {asset["asset_id"]: asset for asset in assets}
    for asset in assets:
        for source in safe_id_list(asset.get("inherits_from")):
            if source not in asset_by_id:
                errors.append(f"asset_inheritance_unknown:{asset['asset_id']}:{source}")
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
            ):
                if actual.get(field) == expected.get(field):
                    continue
                if field == "coverage" and expected["role"] == "storyboard_frame":
                    errors.append(f"storyboard_truth_mismatch:{asset_id}")
                elif field == "inherits_from":
                    errors.append(f"asset_dependency_mismatch:{asset_id}")
                else:
                    errors.append(f"asset_semantic_drift:{asset_id}:{field}")

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
        "product_coverage_missing",
        [key for key, value in product_counts.items() if value == 0],
    )
    add_coverage_error(errors, "prop_coverage_missing", [key for key, value in prop_counts.items() if value == 0])
    add_coverage_error(errors, "scene_coverage_missing", [key for key, value in scene_counts.items() if value == 0])
    exact_coverage(
        "character_identity_reference",
        "character_ids",
        character_ids,
        "character_identity_coverage_invalid",
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

    storyboard_counts = _coverage_counts(assets, "storyboard_frame", "shot_ids", shot_ids)
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

    evidence_by_asset: dict[str, dict[str, Any]] = {}
    if completion_claim in GENERATED_CLAIMS:
        for asset in assets:
            if asset.get("required") is not True:
                continue
            asset_id = asset["asset_id"]
            if asset.get("status") not in GENERATED_STATUSES:
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
            if asset.get("role") in DELIVERY_FRAME_ROLES and target_frame_ratio is not None:
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

        manifest_cache: dict[
            str,
            tuple[dict[str, Any], dict[str, dict[str, Any]], str | None],
        ] = {}
        for asset in assets:
            if asset.get("required") is not True:
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
    semantic_probe["completion_claim"] = "none"
    semantic_errors, _ = validate_plan(semantic_probe, base_dir=base_dir)
    if semantic_errors:
        raise ValueError("cannot stamp an invalid visual plan: " + ";".join(semantic_errors))
    for asset in stamped["assets"]:
        if asset.get("required") is not True:
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
        next(asset for asset in duplicate_identity["assets"] if asset["asset_id"] == "identity-character-lin-che")
    )
    duplicate_character["asset_id"] = "identity-character-lin-che-duplicate"
    duplicate_identity["assets"].append(duplicate_character)
    duplicate_identity_errors, _ = validate_plan(duplicate_identity, base_dir=TVC_INVENTORY_PATH.parent)
    duplicate_identity_negative_control = "character_identity_coverage_invalid:lin-che:2" in duplicate_identity_errors
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
    multiple_direct_inputs_positive_control = False
    multiple_direct_inputs_dependency_negative_control = False
    generated_evidence_control = False
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
        generated_errors, generated_metrics = validate_plan(
            generated,
            base_dir=temp_root,
            evidence_cache=raster_cache,
        )
        generated_evidence_control = not generated_errors and generated_metrics.get(
            "whole_film_visual_assets_complete"
        ) is True
        if not generated_evidence_control:
            failures.append(f"generated whole-film visual evidence did not pass: {generated_errors}")

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
            not portable_errors
            and portable_metrics.get("whole_film_visual_assets_complete") is True
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
        "generated_evidence_control": generated_evidence_control,
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
            "Full-decode every required generated raster and bind technical receipts; "
            "this never grants visual QA approval."
        ),
    )
    parser.add_argument("--checked-at", help="RFC3339 UTC timestamp for reproducible evidence stamping.")
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
