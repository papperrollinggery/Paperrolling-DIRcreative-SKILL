#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    Image = ImageFilter = ImageOps = None  # type: ignore[assignment]

from dircreative_verify_release import (
    open_pinned_directory,
    read_relative_regular_file_once,
    regular_file_open_flags,
)
from dircreative_visual_asset_plan import inspect_raster
from dircreative_review_trust import (
    default_review_trust_registry_path,
    verify_detached_review_artifact,
)
from dircreative_media_forward_audit import parse_host_trace_prefix


ROOT = Path(__file__).resolve().parents[1]
SWIFT_HELPER = ROOT / "scripts/dircreative_character_master_vision.swift"
SYSTEM_SWIFT = Path("/usr/bin/swift")
SYSTEM_CODESIGN = Path("/usr/bin/codesign")
CONTRACT_ID = "character_master_visual_gate_v1"
MAX_IMAGE_BYTES = 128 * 1024 * 1024
EXPECTED_FULL_BODY_COUNT = 4
MIN_FULL_BODY_JOINT_SPAN = 0.50
MIN_FULL_BODY_SUBJECT_HEIGHT = 0.75
MIN_FULL_BODY_HEAD_EXTENT = 0.04
MIN_FULL_BODY_FRAME_EDGE_CLEARANCE = 0.005
MIN_FULL_BODY_VISIBLE_WRISTS = 1
MIN_FULL_BODY_VISIBLE_ELBOWS = 1
MIN_FULL_BODY_VISIBLE_UPPER_LIMB_JOINTS = 2
MIN_TERMINAL_SLOT_VISIBLE_UPPER_LIMB_JOINTS = 4
MAX_FULL_BODY_RECTANGLE_IOU = 0.25
MIN_BODY_CENTER_X = 0.28
MIN_BODY_CENTER_GAP = 0.055
CHARACTER_MODES = {"headed_master", "headed_state", "headless_safe"}
SHA256_RE = __import__("re").compile(r"^[a-f0-9]{64}$")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def vision_helper_sha256() -> str:
    payload = read_relative_regular_file_once(
        ROOT,
        "scripts/dircreative_character_master_vision.swift",
        max_bytes=1024 * 1024,
        label="character Vision helper",
    )
    return hashlib.sha256(payload).hexdigest()


def swift_tool_identity() -> dict[str, str]:
    if not SYSTEM_SWIFT.is_file() or not SYSTEM_CODESIGN.is_file():
        raise ValueError("Apple Swift tool unavailable")
    metadata = SYSTEM_SWIFT.stat(follow_symlinks=False)
    if metadata.st_uid != 0 or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError("Apple Swift tool ownership invalid")
    verify = subprocess.run(
        [str(SYSTEM_CODESIGN), "--verify", "--strict", str(SYSTEM_SWIFT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    details = subprocess.run(
        [str(SYSTEM_CODESIGN), "-dv", "--verbose=4", str(SYSTEM_SWIFT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    signature_text = details.stdout + details.stderr
    if (
        verify.returncode != 0
        or details.returncode != 0
        or "Authority=Apple Root CA" not in signature_text
        or "Platform identifier=" not in signature_text
    ):
        raise ValueError("Apple Swift tool signature invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(SYSTEM_SWIFT, flags)
    try:
        opened = os.fstat(descriptor)
        payload = bytearray()
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > 1024 * 1024:
                raise ValueError("Apple Swift tool exceeds size limit")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ValueError("Apple Swift tool changed while hashing")
    return {
        "path": str(SYSTEM_SWIFT),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "signature_policy": "apple-root-platform-binary",
    }


def evaluate_probe(probe: Any, *, mode: str = "headed_master") -> list[str]:
    if not isinstance(probe, dict):
        return ["vision_probe_invalid"]
    errors: list[str] = []
    if mode not in CHARACTER_MODES:
        return ["character_master_mode_invalid"]
    bodies = probe.get("full_bodies")
    if probe.get("backend") != "apple-vision-human-body-pose-v1":
        errors.append("vision_backend_invalid")
    if mode == "headless_safe":
        if probe.get("right_full_height_component_count") != EXPECTED_FULL_BODY_COUNT:
            errors.append("headless_master_requires_four_full_body_silhouettes")
        if probe.get("right_face_count") != 0:
            errors.append("headless_master_contains_body_face")
        bodies = probe.get("right_full_height_components", [])
    elif probe.get("full_body_count") != EXPECTED_FULL_BODY_COUNT or not isinstance(bodies, list):
        errors.append("character_master_requires_four_full_bodies")
        bodies = []
    centers: list[float] = []
    human_rectangle_indices: list[int] = []
    human_rectangle_ranges: list[tuple[float, float]] = []
    for body_index, body in enumerate(bodies):
        if not isinstance(body, dict):
            errors.append("full_body_observation_invalid")
            continue
        center = body.get("center_x")
        joint_span = body.get("joint_span")
        subject_height = body.get("subject_height")
        head_extent = body.get("head_extent_above_shoulders")
        top_clearance = body.get("subject_top_clearance")
        bottom_clearance = body.get("subject_bottom_clearance")
        visible_wrist_count = body.get("visible_wrist_count")
        visible_elbow_count = body.get("visible_elbow_count")
        visible_upper_limb_joint_count = body.get("visible_upper_limb_joint_count")
        human_rect_index = body.get("human_rect_index")
        human_rect_min_x = body.get("human_rect_min_x")
        human_rect_max_x = body.get("human_rect_max_x")
        if not isinstance(center, (int, float)) or center <= MIN_BODY_CENTER_X:
            errors.append("full_body_must_follow_left_portrait")
        else:
            centers.append(float(center))
        if mode != "headless_safe" and (
            not isinstance(joint_span, (int, float)) or joint_span < MIN_FULL_BODY_JOINT_SPAN
        ):
            errors.append("full_body_joint_span_below_detection_floor")
        if (
            not isinstance(subject_height, (int, float))
            or subject_height < MIN_FULL_BODY_SUBJECT_HEIGHT
        ):
            errors.append("full_body_subject_height_below_75_percent")
        if mode != "headless_safe" and (
            not isinstance(head_extent, (int, float))
            or head_extent < MIN_FULL_BODY_HEAD_EXTENT
        ):
            errors.append("full_body_head_extent_incomplete")
        if mode != "headless_safe" and (
            not isinstance(top_clearance, (int, float))
            or not isinstance(bottom_clearance, (int, float))
            or top_clearance < MIN_FULL_BODY_FRAME_EDGE_CLEARANCE
            or bottom_clearance < MIN_FULL_BODY_FRAME_EDGE_CLEARANCE
        ):
            errors.append("full_body_touches_frame_edge")
        if mode != "headless_safe":
            if not isinstance(human_rect_index, int) or human_rect_index < 0:
                errors.append("full_body_human_rectangle_invalid")
            else:
                human_rectangle_indices.append(human_rect_index)
            if (
                not isinstance(human_rect_min_x, (int, float))
                or not isinstance(human_rect_max_x, (int, float))
                or not 0 <= human_rect_min_x < human_rect_max_x <= 1
            ):
                errors.append("full_body_human_rectangle_invalid")
            else:
                human_rectangle_ranges.append(
                    (float(human_rect_min_x), float(human_rect_max_x))
                )
            required_upper_limb_joints = (
                MIN_TERMINAL_SLOT_VISIBLE_UPPER_LIMB_JOINTS
                if body_index in {0, EXPECTED_FULL_BODY_COUNT - 1}
                else MIN_FULL_BODY_VISIBLE_UPPER_LIMB_JOINTS
            )
            required_wrist_count = 2 if body_index in {0, EXPECTED_FULL_BODY_COUNT - 1} else 1
            required_elbow_count = 2 if body_index in {0, EXPECTED_FULL_BODY_COUNT - 1} else 1
            if (
                not isinstance(visible_wrist_count, int)
                or visible_wrist_count < required_wrist_count
                or not isinstance(visible_elbow_count, int)
                or visible_elbow_count < required_elbow_count
                or not isinstance(visible_upper_limb_joint_count, int)
                or visible_upper_limb_joint_count < required_upper_limb_joints
            ):
                errors.append("full_body_upper_limb_endpoint_incomplete")
    if centers != sorted(centers) or any(
        right - left < MIN_BODY_CENTER_GAP for left, right in zip(centers, centers[1:])
    ):
        errors.append("full_body_horizontal_separation_invalid")
    if mode != "headless_safe":
        if len(human_rectangle_indices) != EXPECTED_FULL_BODY_COUNT or len(
            set(human_rectangle_indices)
        ) != EXPECTED_FULL_BODY_COUNT:
            errors.append("full_body_human_rectangle_not_unique")
        for index, (left_min, left_max) in enumerate(human_rectangle_ranges):
            for right_min, right_max in human_rectangle_ranges[index + 1 :]:
                intersection = max(0.0, min(left_max, right_max) - max(left_min, right_min))
                union = max(left_max, right_max) - min(left_min, right_min)
                if union <= 0 or intersection / union > MAX_FULL_BODY_RECTANGLE_IOU:
                    errors.append("full_body_human_rectangle_overlap_invalid")
    if probe.get("left_closeup_face_count", 0) < 1:
        errors.append("far_left_closeup_face_not_detected")
    if probe.get("left_portrait_subject_height", 0) < MIN_FULL_BODY_SUBJECT_HEIGHT:
        errors.append("left_portrait_subject_height_below_75_percent")
    return list(dict.fromkeys(errors))


def expected_receipt_path(image_path: Path) -> Path:
    return image_path.with_suffix(".character-master-visual.json")


def character_master_alpha_facts(image_evidence: dict[str, Any]) -> dict[str, int] | None:
    values = {
        "alpha_min": image_evidence.get("alpha_min"),
        "alpha_max": image_evidence.get("alpha_max"),
        "alpha_nonopaque_pixel_count": image_evidence.get("alpha_nonopaque_pixel_count"),
    }
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values.values()):
        return None
    return values  # type: ignore[return-value]


def character_master_alpha_errors(image_evidence: dict[str, Any]) -> list[str]:
    alpha = character_master_alpha_facts(image_evidence)
    if alpha is None:
        return ["character_master_alpha_evidence_missing"]
    if (
        alpha["alpha_min"] != 255
        or alpha["alpha_max"] != 255
        or alpha["alpha_nonopaque_pixel_count"] != 0
    ):
        return ["character_master_requires_opaque_background"]
    return []


def validate_receipt(
    receipt: Any,
    *,
    asset_id: str,
    asset_truth_sha256: str,
    image_evidence: dict[str, Any],
    expected_mode: str,
    expected_derived_from_asset_id: str | None,
    expected_approved_source_master_sha256: str | None,
) -> list[str]:
    if not isinstance(receipt, dict):
        return ["character_master_visual_receipt_invalid"]
    expected_fields = {
        "contract_id",
        "status",
        "asset_id",
        "asset_truth_sha256",
        "mode",
        "derived_from_asset_id",
        "approved_source_master_sha256",
        "image_sha256",
        "pixel_sha256",
        "raster_alpha",
        "checked_at",
        "vision_helper_sha256",
        "measurement_contract",
        "vision_tool_identity",
        "vision_probe",
        "errors",
        "visual_orientation_material_review_required",
        "completion_claim_allowed",
        "receipt_sha256",
    }
    errors: list[str] = []
    if set(receipt) != expected_fields:
        errors.append("character_master_visual_receipt_shape_invalid")
        return errors
    if receipt.get("receipt_sha256") != canonical_sha256(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    ):
        errors.append("character_master_visual_receipt_hash_invalid")
    if receipt.get("contract_id") != CONTRACT_ID:
        errors.append("character_master_visual_contract_invalid")
    if (
        receipt.get("mode") != expected_mode
        or receipt.get("derived_from_asset_id") != expected_derived_from_asset_id
        or receipt.get("approved_source_master_sha256")
        != expected_approved_source_master_sha256
    ):
        errors.append("character_master_visual_mode_source_binding_invalid")
    if receipt.get("measurement_contract") != {
        "full_body_subject_height_floor": MIN_FULL_BODY_SUBJECT_HEIGHT,
        "left_portrait_subject_height_floor": MIN_FULL_BODY_SUBJECT_HEIGHT,
        "full_body_joint_span_detection_floor": MIN_FULL_BODY_JOINT_SPAN,
        "full_body_head_extent_floor": MIN_FULL_BODY_HEAD_EXTENT,
        "full_body_frame_edge_clearance_floor": MIN_FULL_BODY_FRAME_EDGE_CLEARANCE,
        "full_body_visible_wrist_floor": MIN_FULL_BODY_VISIBLE_WRISTS,
        "full_body_visible_elbow_floor": MIN_FULL_BODY_VISIBLE_ELBOWS,
        "full_body_visible_upper_limb_joint_floor": MIN_FULL_BODY_VISIBLE_UPPER_LIMB_JOINTS,
        "full_body_terminal_slot_visible_upper_limb_joint_floor": MIN_TERMINAL_SLOT_VISIBLE_UPPER_LIMB_JOINTS,
        "full_body_human_rectangle_iou_ceiling": MAX_FULL_BODY_RECTANGLE_IOU,
        "subject_height_source": "VNDetectHumanRectanglesRequest.boundingBox.height",
        "head_extent_source": "human rectangle top minus highest detected shoulder; neck required",
        "frame_edge_clearance_source": "VNDetectHumanRectanglesRequest.boundingBox minY/maxY",
        "upper_limb_source": "canonical sorted slots: front/back require both wrists and elbows; side slots allow far-arm occlusion",
        "distinct_body_source": "unique matched VNDetectHumanRectanglesRequest index and horizontal IoU",
        "headless_silhouette_source": "four fixed right-side slots with foreground component heuristics; never self-passing",
        "portrait_height_source": "left-slot foreground component containing the detected face center",
    }:
        errors.append("character_master_visual_measurement_contract_invalid")
    try:
        tool_identity = swift_tool_identity()
    except (OSError, subprocess.TimeoutExpired, ValueError):
        tool_identity = None
    if receipt.get("vision_tool_identity") != tool_identity:
        errors.append("character_master_visual_tool_identity_invalid")
    try:
        helper_sha256 = vision_helper_sha256()
    except (OSError, ValueError):
        helper_sha256 = None
    if receipt.get("vision_helper_sha256") != helper_sha256:
        errors.append("character_master_visual_helper_binding_invalid")
    if receipt.get("asset_id") != asset_id or receipt.get("asset_truth_sha256") != asset_truth_sha256:
        errors.append("character_master_visual_truth_binding_invalid")
    if (
        receipt.get("image_sha256") != image_evidence.get("sha256")
        or receipt.get("pixel_sha256") != image_evidence.get("pixel_sha256")
    ):
        errors.append("character_master_visual_image_binding_invalid")
    alpha_facts = character_master_alpha_facts(image_evidence)
    if receipt.get("raster_alpha") != alpha_facts:
        errors.append("character_master_visual_alpha_binding_invalid")
    probe_errors = evaluate_probe(
        receipt.get("vision_probe"),
        mode=str(receipt.get("mode")),
    )
    expected_receipt_errors = [*probe_errors, *character_master_alpha_errors(image_evidence)]
    if receipt.get("errors") != expected_receipt_errors:
        errors.append("character_master_visual_error_set_invalid")
    expected_status = (
        "blocked"
        if expected_receipt_errors
        else "applied_unverified"
        if receipt.get("mode") == "headless_safe"
        else "pass"
    )
    if receipt.get("status") != expected_status:
        errors.append("character_master_visual_status_invalid")
    if receipt.get("visual_orientation_material_review_required") is not True:
        errors.append("character_master_visual_semantic_review_boundary_invalid")
    if receipt.get("completion_claim_allowed") is not False:
        errors.append("character_master_visual_completion_authority_invalid")
    return list(dict.fromkeys(errors))


def make_receipt(
    *,
    asset_id: str,
    asset_truth_sha256: str,
    image_evidence: dict[str, Any],
    probe: dict[str, Any],
    checked_at: str,
    mode: str = "headed_master",
    derived_from_asset_id: str | None = None,
    approved_source_master_sha256: str | None = None,
) -> dict[str, Any]:
    probe_errors = evaluate_probe(probe, mode=mode)
    receipt_errors = [*probe_errors, *character_master_alpha_errors(image_evidence)]
    receipt = {
        "contract_id": CONTRACT_ID,
        "status": (
            "blocked"
            if receipt_errors
            else "applied_unverified"
            if mode == "headless_safe"
            else "pass"
        ),
        "asset_id": asset_id,
        "asset_truth_sha256": asset_truth_sha256,
        "mode": mode,
        "derived_from_asset_id": derived_from_asset_id,
        "approved_source_master_sha256": approved_source_master_sha256,
        "image_sha256": image_evidence["sha256"],
        "pixel_sha256": image_evidence["pixel_sha256"],
        "raster_alpha": character_master_alpha_facts(image_evidence),
        "checked_at": checked_at,
        "vision_helper_sha256": vision_helper_sha256(),
        "measurement_contract": {
            "full_body_subject_height_floor": MIN_FULL_BODY_SUBJECT_HEIGHT,
            "left_portrait_subject_height_floor": MIN_FULL_BODY_SUBJECT_HEIGHT,
            "full_body_joint_span_detection_floor": MIN_FULL_BODY_JOINT_SPAN,
            "full_body_head_extent_floor": MIN_FULL_BODY_HEAD_EXTENT,
            "full_body_frame_edge_clearance_floor": MIN_FULL_BODY_FRAME_EDGE_CLEARANCE,
            "full_body_visible_wrist_floor": MIN_FULL_BODY_VISIBLE_WRISTS,
            "full_body_visible_elbow_floor": MIN_FULL_BODY_VISIBLE_ELBOWS,
            "full_body_visible_upper_limb_joint_floor": MIN_FULL_BODY_VISIBLE_UPPER_LIMB_JOINTS,
            "full_body_terminal_slot_visible_upper_limb_joint_floor": MIN_TERMINAL_SLOT_VISIBLE_UPPER_LIMB_JOINTS,
            "full_body_human_rectangle_iou_ceiling": MAX_FULL_BODY_RECTANGLE_IOU,
            "subject_height_source": "VNDetectHumanRectanglesRequest.boundingBox.height",
            "head_extent_source": "human rectangle top minus highest detected shoulder; neck required",
            "frame_edge_clearance_source": "VNDetectHumanRectanglesRequest.boundingBox minY/maxY",
            "upper_limb_source": "canonical sorted slots: front/back require both wrists and elbows; side slots allow far-arm occlusion",
            "distinct_body_source": "unique matched VNDetectHumanRectanglesRequest index and horizontal IoU",
            "headless_silhouette_source": "four fixed right-side slots with foreground component heuristics; never self-passing",
            "portrait_height_source": "left-slot foreground component containing the detected face center",
        },
        "vision_tool_identity": swift_tool_identity(),
        "vision_probe": probe,
        "errors": receipt_errors,
        "visual_orientation_material_review_required": True,
        "completion_claim_allowed": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def load_character_master_receipt(
    asset: dict[str, Any],
    *,
    base_dir: Path,
    image_evidence: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    generated_file = asset.get("generated_file")
    if not isinstance(generated_file, str) or not generated_file:
        return None, ["character_master_visual_image_path_invalid"]
    relative = Path(generated_file).with_suffix(".character-master-visual.json").as_posix()
    try:
        image_bytes = read_relative_regular_file_once(
            base_dir,
            generated_file,
            max_bytes=MAX_IMAGE_BYTES,
            label="character master image",
        )
        raw = read_relative_regular_file_once(
            base_dir,
            relative,
            max_bytes=1024 * 1024,
            label="character master visual receipt",
        )
        receipt = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, ["character_master_visual_receipt_missing_or_invalid"]
    observed_probe, probe_error = run_probe(image_bytes)
    if probe_error is not None:
        return receipt, [probe_error]
    if receipt.get("vision_probe") != observed_probe:
        return receipt, ["character_master_visual_probe_readback_mismatch"]
    return receipt, validate_receipt(
        receipt,
        asset_id=str(asset.get("asset_id")),
        asset_truth_sha256=str(asset.get("truth_sha256")),
        image_evidence=image_evidence,
        expected_mode=str(asset.get("character_mode")),
        expected_derived_from_asset_id=asset.get("derived_from_asset_id"),
        expected_approved_source_master_sha256=asset.get("approved_source_master_sha256"),
    )


def load_headless_review_authorization(
    asset: dict[str, Any],
    *,
    base_dir: Path,
    image_evidence: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    generated_file = asset.get("generated_file")
    if not isinstance(generated_file, str) or not generated_file:
        return None, ["headless_review_image_path_invalid"]
    base = Path(generated_file).with_suffix("")
    review_relative = base.as_posix() + ".headless-review.json"
    signature_relative = review_relative + ".sig"
    try:
        review_bytes = read_relative_regular_file_once(
            base_dir,
            review_relative,
            max_bytes=1024 * 1024,
            label="headless review authorization",
        )
        signature_bytes = read_relative_regular_file_once(
            base_dir,
            signature_relative,
            max_bytes=1024 * 1024,
            label="headless review signature",
        )
        review = json.loads(review_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, ["headless_review_authorization_missing_or_invalid"]
    expected_fields = {
        "contract_id",
        "purpose",
        "source",
        "authority_id",
        "actor",
        "asset_id",
        "asset_truth_sha256",
        "image_sha256",
        "pixel_sha256",
        "mode",
        "decision",
        "receipt_sha256",
    }
    if not isinstance(review, dict) or set(review) != expected_fields:
        return review if isinstance(review, dict) else None, ["headless_review_authorization_shape_invalid"]
    errors: list[str] = []
    if review.get("receipt_sha256") != canonical_sha256(
        {key: value for key, value in review.items() if key != "receipt_sha256"}
    ):
        errors.append("headless_review_authorization_hash_invalid")
    if (
        review.get("contract_id") != "headless_character_review_v1"
        or review.get("purpose") != "headless_character_review"
        or review.get("source") != "independent_review"
        or review.get("asset_id") != asset.get("asset_id")
        or review.get("asset_truth_sha256") != asset.get("truth_sha256")
        or review.get("image_sha256") != image_evidence.get("sha256")
        or review.get("pixel_sha256") != image_evidence.get("pixel_sha256")
        or review.get("mode") != "headless_safe"
        or review.get("decision") != "pass"
    ):
        errors.append("headless_review_authorization_binding_invalid")
    if errors:
        return review, errors
    with tempfile.TemporaryDirectory(prefix="dircreative-headless-review-") as raw:
        review_path = Path(raw) / "review.json"
        signature_path = Path(raw) / "review.sig"
        review_path.write_bytes(review_bytes)
        signature_path.write_bytes(signature_bytes)
        trust_errors = verify_detached_review_artifact(
            review_path,
            signature_path,
            authority_id=review.get("authority_id"),
            actor=review.get("actor"),
            purpose="headless_character_review",
            source="independent_review",
            registry_path=default_review_trust_registry_path(),
            artifact_root=base_dir,
        )
    return review, [f"headless_review_{error}" for error in trust_errors]


def load_visual_review_authorization(
    asset: dict[str, Any],
    *,
    base_dir: Path,
    image_evidence: dict[str, Any],
    expected_execution_task_id: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    host_review, host_errors = load_visual_review_host_authorization(
        asset,
        base_dir=base_dir,
        image_evidence=image_evidence,
        expected_execution_task_id=expected_execution_task_id,
    )
    if not host_errors:
        return host_review, []
    generated_file = asset.get("generated_file")
    if not isinstance(generated_file, str) or not generated_file:
        return None, ["visual_review_authorization_image_path_invalid"]
    base = Path(generated_file).with_suffix("")
    review_relative = base.as_posix() + ".visual-review-authorization.json"
    signature_relative = review_relative + ".sig"
    try:
        review_bytes = read_relative_regular_file_once(
            base_dir,
            review_relative,
            max_bytes=1024 * 1024,
            label="visual review authorization",
        )
        signature_bytes = read_relative_regular_file_once(
            base_dir,
            signature_relative,
            max_bytes=1024 * 1024,
            label="visual review authorization signature",
        )
        review = json.loads(review_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, ["visual_review_authorization_missing_or_invalid"]
    expected_fields = {
        "contract_id",
        "purpose",
        "source",
        "authority_id",
        "actor",
        "asset_id",
        "asset_role",
        "asset_truth_sha256",
        "image_sha256",
        "pixel_sha256",
        "decision",
        "receipt_sha256",
    }
    if not isinstance(review, dict) or set(review) != expected_fields:
        return review if isinstance(review, dict) else None, ["visual_review_authorization_shape_invalid"]
    errors: list[str] = []
    if review.get("receipt_sha256") != canonical_sha256(
        {key: value for key, value in review.items() if key != "receipt_sha256"}
    ):
        errors.append("visual_review_authorization_hash_invalid")
    if (
        review.get("contract_id") != "visual_asset_review_authorization_v1"
        or review.get("purpose") != "visual_asset_downstream_authorization"
        or review.get("source") != "independent_review"
        or review.get("asset_id") != asset.get("asset_id")
        or review.get("asset_role") != asset.get("role")
        or review.get("asset_truth_sha256") != asset.get("truth_sha256")
        or review.get("image_sha256") != image_evidence.get("sha256")
        or review.get("pixel_sha256") != image_evidence.get("pixel_sha256")
        or review.get("decision") != "pass"
    ):
        errors.append("visual_review_authorization_binding_invalid")
    if errors:
        return review, errors
    with tempfile.TemporaryDirectory(prefix="dircreative-visual-review-") as raw:
        review_path = Path(raw) / "review.json"
        signature_path = Path(raw) / "review.sig"
        review_path.write_bytes(review_bytes)
        signature_path.write_bytes(signature_bytes)
        trust_errors = verify_detached_review_artifact(
            review_path,
            signature_path,
            authority_id=review.get("authority_id"),
            actor=review.get("actor"),
            purpose="visual_asset_downstream_authorization",
            source="independent_review",
            registry_path=default_review_trust_registry_path(),
            artifact_root=base_dir,
        )
    return review, [f"visual_review_{error}" for error in trust_errors]


def load_visual_review_host_authorization(
    asset: dict[str, Any],
    *,
    base_dir: Path,
    image_evidence: dict[str, Any],
    expected_execution_task_id: str | None = None,
    _trusted_host_root: Path | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    generated_file = asset.get("generated_file")
    if not isinstance(generated_file, str) or not generated_file:
        return None, ["visual_host_review_image_path_invalid"]
    relative = Path(generated_file).with_suffix("").as_posix() + ".visual-review-host.json"
    try:
        raw = read_relative_regular_file_once(
            base_dir,
            relative,
            max_bytes=1024 * 1024,
            label="visual host review authorization",
        )
        review = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None, ["visual_host_review_authorization_missing_or_invalid"]
    expected_fields = {
        "contract_id",
        "purpose",
        "source",
        "reviewer_task_id",
        "execution_task_id",
        "asset_id",
        "asset_role",
        "asset_truth_sha256",
        "image_sha256",
        "pixel_sha256",
        "decision",
        "host_trace",
        "receipt_sha256",
    }
    if not isinstance(review, dict) or set(review) != expected_fields:
        return review if isinstance(review, dict) else None, ["visual_host_review_authorization_shape_invalid"]
    core = {
        key: value
        for key, value in review.items()
        if key not in {"host_trace", "receipt_sha256"}
    }
    expected_claim = canonical_sha256(core)
    trace = review.get("host_trace")
    errors: list[str] = []
    if review.get("receipt_sha256") != canonical_sha256(
        {key: value for key, value in review.items() if key != "receipt_sha256"}
    ):
        errors.append("visual_host_review_receipt_hash_invalid")
    if (
        review.get("contract_id") != "visual_asset_host_review_authorization_v1"
        or review.get("purpose") != "visual_asset_downstream_authorization"
        or review.get("source") != "independent_host_review"
        or not isinstance(expected_execution_task_id, str)
        or not expected_execution_task_id
        or review.get("execution_task_id") != expected_execution_task_id
        or review.get("execution_task_id") == review.get("reviewer_task_id")
        or review.get("asset_id") != asset.get("asset_id")
        or review.get("asset_role") != asset.get("role")
        or review.get("asset_truth_sha256") != asset.get("truth_sha256")
        or review.get("image_sha256") != image_evidence.get("sha256")
        or review.get("pixel_sha256") != image_evidence.get("pixel_sha256")
        or review.get("decision") != "pass"
        or not isinstance(trace, dict)
        or trace.get("thread_id") != review.get("reviewer_task_id")
        or trace.get("review_claim_sha256") != expected_claim
    ):
        errors.append("visual_host_review_authorization_binding_invalid")
    if errors:
        return review, errors
    trusted_root = (_trusted_host_root or (Path.home() / ".codex/sessions")).resolve(strict=True)
    host_relative = trace.get("host_log_relative_path")
    if (
        not isinstance(host_relative, str)
        or host_relative.startswith("/")
        or "\\" in host_relative
        or any(part in {"", ".", ".."} for part in host_relative.split("/"))
    ):
        return review, ["visual_host_review_log_path_invalid"]
    try:
        host_log = trusted_root.joinpath(*host_relative.split("/")).resolve(strict=True)
        host_log.relative_to(trusted_root)
        host_bytes = read_relative_regular_file_once(
            trusted_root,
            host_relative,
            max_bytes=16 * 1024 * 1024,
            label="visual asset host review trace",
        )
        parser_trace = {
            key: trace.get(key)
            for key in (
                "thread_id",
                "prefix_bytes",
                "prefix_sha256",
                "review_request_event_id",
                "view_event_ids",
                "review_claim_sha256",
                "evidence_level",
                "cryptographically_signed",
            )
        }
        evidence, trace_errors = parse_host_trace_prefix(
            host_log,
            parser_trace,
            label="visual asset host review trace",
        )
    except (OSError, ValueError):
        return review, ["visual_host_review_trace_invalid"]
    if trace_errors:
        return review, [f"visual_host_review_{error}" for error in trace_errors]
    request_payload = {
        "contract_id": "visual_asset_review_request_v1",
        "execution_task_id": review.get("execution_task_id"),
        "asset_id": review.get("asset_id"),
        "asset_role": review.get("asset_role"),
        "asset_truth_sha256": review.get("asset_truth_sha256"),
        "image_sha256": review.get("image_sha256"),
        "pixel_sha256": review.get("pixel_sha256"),
    }
    request_text = "DIRCREATIVE_ASSET_REVIEW_REQUEST " + json.dumps(
        request_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if trace.get("review_request_sha256") != hashlib.sha256(request_text.encode("utf-8")).hexdigest():
        return review, ["visual_host_review_request_hash_invalid"]
    request_event_id = trace.get("review_request_event_id")
    request_found = False
    request_line: int | None = None
    claim_lines: list[int] = []
    view_call_ids: dict[str, str] = {}
    view_output_lines: list[int] = []
    view_hashes: list[str] = []
    selected_view_ids = set(trace.get("view_event_ids", []))
    for line_number, raw_line in enumerate(
        host_bytes[: int(trace.get("prefix_bytes", 0))].splitlines(),
        start=1,
    ):
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        if (
            record.get("type") == "response_item"
            and payload.get("type") == "message"
            and payload.get("id") == request_event_id
            and payload.get("role") == "user"
        ):
            texts = [
                item.get("text")
                for item in payload.get("content", [])
                if isinstance(item, dict) and item.get("type") in {"input_text", "output_text"}
            ]
            request_found = texts == [request_text]
            if request_found:
                request_line = line_number
        if (
            record.get("type") == "response_item"
            and payload.get("type") == "custom_tool_call"
            and payload.get("id") in selected_view_ids
            and isinstance(payload.get("call_id"), str)
        ):
            view_call_ids[payload["call_id"]] = payload["id"]
        if (
            record.get("type") == "response_item"
            and payload.get("type") == "custom_tool_call_output"
            and payload.get("call_id") in view_call_ids
        ):
            hashes: list[str] = []
            for item in payload.get("output", []):
                if not isinstance(item, dict) or item.get("type") not in {"input_image", "image"}:
                    continue
                raw_url = item.get("image_url")
                try:
                    if isinstance(raw_url, str) and raw_url.startswith("data:") and ";base64," in raw_url:
                        viewed_bytes = base64.b64decode(raw_url.split(";base64,", 1)[1], validate=True)
                    elif isinstance(item.get("data"), str):
                        viewed_bytes = base64.b64decode(item["data"], validate=True)
                    else:
                        continue
                except (binascii.Error, ValueError):
                    continue
                hashes.append(hashlib.sha256(viewed_bytes).hexdigest())
            if hashes:
                view_output_lines.append(line_number)
                view_hashes.extend(hashes)
        if (
            record.get("type") == "event_msg"
            and payload.get("type") == "agent_message"
            and str(payload.get("message", "")).strip()
            == "DIRCREATIVE_VISUAL_REVIEW_CLAIM " + expected_claim
        ):
            claim_lines.append(line_number)
    if not request_found:
        return review, ["visual_host_review_sealed_request_missing"]
    if (
        request_line is None
        or len(view_output_lines) != len(selected_view_ids)
        or not view_hashes
        or any(digest != image_evidence.get("sha256") for digest in view_hashes)
        or len(claim_lines) != 1
        or not all(request_line < line < claim_lines[0] for line in view_output_lines)
    ):
        return review, ["visual_host_review_order_or_pixel_evidence_invalid"]
    view_ids = trace.get("view_event_ids")
    views = evidence.get("view_events", {})
    expected_path = str((base_dir / generated_file).resolve(strict=True))
    if (
        evidence.get("thread_id") != review.get("reviewer_task_id")
        or expected_claim not in evidence.get("review_claims", set())
        or not isinstance(view_ids, list)
        or not view_ids
        or any(views.get(event_id) != expected_path for event_id in view_ids)
    ):
        return review, ["visual_host_review_trace_binding_invalid"]
    execution_trace = trace.get("execution_trace")
    if not isinstance(execution_trace, dict):
        return review, ["visual_host_execution_trace_missing"]
    execution_relative = execution_trace.get("host_log_relative_path")
    if (
        not isinstance(execution_relative, str)
        or execution_relative.startswith("/")
        or "\\" in execution_relative
        or any(part in {"", ".", ".."} for part in execution_relative.split("/"))
    ):
        return review, ["visual_host_execution_log_path_invalid"]
    try:
        execution_bytes = read_relative_regular_file_once(
            trusted_root,
            execution_relative,
            max_bytes=16 * 1024 * 1024,
            label="visual asset execution trace",
        )
    except (OSError, ValueError):
        return review, ["visual_host_execution_trace_invalid"]
    execution_prefix = execution_trace.get("prefix_bytes")
    if (
        not isinstance(execution_prefix, int)
        or execution_prefix <= 0
        or execution_prefix > len(execution_bytes)
        or hashlib.sha256(execution_bytes[:execution_prefix]).hexdigest()
        != execution_trace.get("prefix_sha256")
    ):
        return review, ["visual_host_execution_prefix_invalid"]
    observed_execution_task: str | None = None
    generated_hashes: set[str] = set()
    for raw_line in execution_bytes[:execution_prefix].splitlines():
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        if record.get("type") == "session_meta":
            candidate = payload.get("id") or payload.get("session_id")
            if isinstance(candidate, str):
                observed_execution_task = candidate
        if record.get("type") == "event_msg" and payload.get("type") == "image_generation_end":
            result = payload.get("result")
            if isinstance(result, str):
                try:
                    generated_hashes.add(
                        hashlib.sha256(base64.b64decode(result, validate=True)).hexdigest()
                    )
                except binascii.Error:
                    pass
    if (
        observed_execution_task != expected_execution_task_id
        or execution_trace.get("thread_id") != expected_execution_task_id
        or image_evidence.get("sha256") not in generated_hashes
    ):
        return review, ["visual_host_execution_trace_binding_invalid"]
    return review, []


def run_probe(image_bytes: bytes) -> tuple[dict[str, Any] | None, str | None]:
    try:
        tool_identity = swift_tool_identity()
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None, "apple_vision_probe_unavailable"
    if not SWIFT_HELPER.is_file():
        return None, "apple_vision_probe_unavailable"
    with tempfile.TemporaryDirectory(prefix="dircreative-character-vision-") as raw:
        image_path = Path(raw) / "character.png"
        helper_path = Path(raw) / "character_vision.swift"
        image_path.write_bytes(image_bytes)
        try:
            helper_bytes = read_relative_regular_file_once(
                ROOT,
                "scripts/dircreative_character_master_vision.swift",
                max_bytes=1024 * 1024,
                label="character Vision helper",
            )
        except (OSError, ValueError):
            return None, "apple_vision_probe_unavailable"
        helper_path.write_bytes(helper_bytes)
        proc = subprocess.run(
            [tool_identity["path"], str(helper_path), str(image_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    if proc.returncode != 0:
        return None, "apple_vision_probe_failed"
    try:
        probe = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, "apple_vision_probe_invalid_json"
    try:
        probe.update(foreground_layout(image_bytes, probe))
    except (OSError, ValueError):
        return None, "foreground_layout_probe_failed"
    return probe, None


def foreground_layout(image_bytes: bytes, vision_probe: dict[str, Any]) -> dict[str, Any]:
    if Image is None or ImageFilter is None or ImageOps is None:
        raise ValueError("Pillow unavailable")
    with Image.open(__import__("io").BytesIO(image_bytes)) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((320, 320), Image.Resampling.LANCZOS)
    width, height = image.size

    def region_components(start_x: int, end_x: int) -> list[dict[str, float]]:
        crop = image.crop((start_x, 0, end_x, height))
        region_width = crop.width
        pixels = crop.load()
        border = [
            pixels[x, y]
            for x, y in (
                [(x, 0) for x in range(region_width)]
                + [(x, height - 1) for x in range(region_width)]
                + [(0, y) for y in range(height)]
                + [(region_width - 1, y) for y in range(height)]
            )
        ]
        background = tuple(
            sorted(pixel[channel] for pixel in border)[len(border) // 2]
            for channel in range(3)
        )
        mask = Image.new("L", crop.size)
        source_pixels = (
            crop.get_flattened_data()
            if hasattr(crop, "get_flattened_data")
            else crop.getdata()
        )
        mask.putdata(
            [
                255
                if sum(
                    (pixel[channel] - background[channel]) ** 2
                    for channel in range(3)
                )
                > 42**2
                else 0
                for pixel in source_pixels
            ]
        )
        mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        data = mask.load()
        visited: set[tuple[int, int]] = set()
        result: list[dict[str, float]] = []
        for y in range(height):
            for x in range(region_width):
                if data[x, y] == 0 or (x, y) in visited:
                    continue
                stack = [(x, y)]
                visited.add((x, y))
                min_x = max_x = x
                min_y = max_y = y
                area = 0
                while stack:
                    current_x, current_y = stack.pop()
                    area += 1
                    min_x, max_x = min(min_x, current_x), max(max_x, current_x)
                    min_y, max_y = min(min_y, current_y), max(max_y, current_y)
                    for next_x, next_y in (
                        (current_x - 1, current_y),
                        (current_x + 1, current_y),
                        (current_x, current_y - 1),
                        (current_x, current_y + 1),
                    ):
                        if (
                            0 <= next_x < region_width
                            and 0 <= next_y < height
                            and data[next_x, next_y] != 0
                            and (next_x, next_y) not in visited
                        ):
                            visited.add((next_x, next_y))
                            stack.append((next_x, next_y))
                box_width = max_x - min_x + 1
                box_height = max_y - min_y + 1
                if area < region_width * height * 0.01:
                    continue
                result.append(
                    {
                        "center_x": (start_x + (min_x + max_x) / 2) / width,
                        "min_x": (start_x + min_x) / width,
                        "max_x": (start_x + max_x) / width,
                        "min_y": min_y / height,
                        "max_y": max_y / height,
                        "subject_height": box_height / height,
                        "slot_width_ratio": box_width / region_width,
                        "area_ratio": area / (region_width * height),
                        "fill_ratio": area / (box_width * box_height),
                        "bottom": max_y / max(1, height - 1),
                    }
                )
        return result

    faces = vision_probe.get("faces", [])
    right_faces = sum(
        1
        for item in faces
        if isinstance(item, dict) and item.get("center_x", 0) > MIN_BODY_CENTER_X
    )
    slot_components: list[dict[str, float]] = []
    valid_slot_count = 0
    for index in range(4):
        start_x = int(width * (0.30 + index * 0.175))
        end_x = min(width, int(width * (0.30 + (index + 1) * 0.175)))
        candidates = [
            item
            for item in region_components(start_x, end_x)
            if item["subject_height"] >= MIN_FULL_BODY_SUBJECT_HEIGHT
            and item["slot_width_ratio"] >= 0.24
            and item["area_ratio"] >= 0.075
            and item["fill_ratio"] >= 0.20
            and item["fill_ratio"] <= 0.82
            and item["bottom"] >= 0.84
        ]
        if len(candidates) == 1:
            valid_slot_count += 1
            slot_components.append(candidates[0])
    portrait_candidates = [
        item
        for item in region_components(0, int(width * 0.30))
        if item["subject_height"] >= MIN_FULL_BODY_SUBJECT_HEIGHT
        and item["slot_width_ratio"] >= 0.35
        and item["area_ratio"] >= 0.10
        and item["fill_ratio"] >= 0.20
    ]
    closeup_faces = vision_probe.get("left_closeup_faces", [])
    portrait_height = max(
        (
            component["subject_height"]
            for component in portrait_candidates
            if any(
                isinstance(face, dict)
                and component["min_x"] <= float(face.get("center_x", -1)) <= component["max_x"]
                and component["min_y"]
                <= 1.0 - float(face.get("center_y", 2))
                <= component["max_y"]
                for face in closeup_faces
            )
        ),
        default=0.0,
    )
    return {
        "left_portrait_components": portrait_candidates,
        "right_full_height_components": slot_components,
        "right_full_height_component_count": valid_slot_count,
        "left_portrait_subject_height": portrait_height,
        "right_face_count": right_faces,
    }


def write_new_receipt(path: Path, payload: bytes) -> None:
    with open_pinned_directory(path.parent) as pinned:
        descriptor = os.open(
            path.name,
            regular_file_open_flags(write=True, create=True),
            0o600,
            dir_fd=pinned.fd,
        )
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        pinned.revalidate(label="character master visual receipt")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the headed character-master layout before visual approval.")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--asset-truth-sha256", required=True)
    parser.add_argument("--mode", choices=sorted(CHARACTER_MODES), default="headed_master")
    parser.add_argument("--derived-from-asset-id")
    parser.add_argument("--approved-source-master-sha256")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        if not SHA256_RE.fullmatch(args.asset_truth_sha256):
            raise ValueError("asset truth hash invalid")
        if args.mode == "headed_master":
            if args.derived_from_asset_id is not None or args.approved_source_master_sha256 is not None:
                raise ValueError("base master cannot declare a derived source")
        elif (
            not args.derived_from_asset_id
            or not isinstance(args.approved_source_master_sha256, str)
            or not SHA256_RE.fullmatch(args.approved_source_master_sha256)
        ):
            raise ValueError("derived mode requires an approved source asset and hash")
        image_path = args.image.expanduser().resolve(strict=True)
        image_bytes = read_relative_regular_file_once(
            image_path.parent,
            image_path.name,
            max_bytes=MAX_IMAGE_BYTES,
            label="character master image",
        )
        with tempfile.NamedTemporaryFile(suffix=".png") as temp:
            temp.write(image_bytes)
            temp.flush()
            evidence, reason = inspect_raster(Path(temp.name))
        if evidence is None:
            print(
                json.dumps(
                    {
                        "status": "blocked",
                        "errors": [f"character_master_raster_invalid:{reason}"],
                        "completion_claim_allowed": False,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 1
        probe, tool_error = run_probe(image_bytes)
        if tool_error is not None:
            print(json.dumps({"status": "TOOL_BLOCKED", "errors": [tool_error]}, sort_keys=True))
            return 2
        receipt = make_receipt(
            asset_id=args.asset_id,
            asset_truth_sha256=args.asset_truth_sha256,
            image_evidence=evidence,
            probe=probe,
            checked_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            mode=args.mode,
            derived_from_asset_id=args.derived_from_asset_id,
            approved_source_master_sha256=args.approved_source_master_sha256,
        )
        receipt_path = (
            args.receipt.expanduser().resolve(strict=False)
            if args.receipt is not None
            else expected_receipt_path(image_path)
        )
        if receipt_path != expected_receipt_path(image_path):
            raise ValueError("receipt path must use the canonical image sidecar name")
        write_new_receipt(
            receipt_path,
            (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if receipt["status"] == "pass" else 1
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(json.dumps({"status": "blocked", "errors": [f"input_or_receipt_invalid:{type(exc).__name__}"]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
