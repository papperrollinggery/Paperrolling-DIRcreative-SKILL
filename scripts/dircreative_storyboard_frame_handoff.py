#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import os
import struct
import tempfile
import zlib
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]

from dircreative_script_to_seedance_handoff import apply_mutations, load_json
from dircreative_state_audit import _builtin_schema_errors
from dircreative_review_trust import (
    default_review_trust_registry_path,
    verify_detached_review_artifact,
)
from dircreative_media_forward_audit import (
    parse_host_trace_prefix,
    png_dimensions,
)
from dircreative_storyboard_coverage import (
    MAX_JSON_BYTES,
    validate as validate_storyboard_coverage,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/storyboard-frame-to-jingzao.schema.json"
VALID_PATH = ROOT / "tests/fixtures/storyboard-frame-jingzao/valid-chain.json"
CASES_PATH = ROOT / "tests/fixtures/storyboard-frame-jingzao/cases.json"
DYNAMIC_FIELDS = (
    "action_vector_counterforce",
    "crop_pressure",
    "parallax_occlusion",
    "exaggeration",
)
ACTION_CLASSES = {"action", "transition"}
GENERIC_NA_REASONS = {"n/a", "na", "none", "not applicable", "not_applicable", "无", "不适用"}
MAX_HOST_TRACE_PREFIX_BYTES = 512 * 1024 * 1024
MAX_HOST_TRACE_LINE_BYTES = 64 * 1024 * 1024
SCENE_SOVEREIGN_FIELDS = {
    "background",
    "ground_surface",
    "scene_geography",
    "support_relation",
}
LAYOUT_SOVEREIGN_FIELDS = {
    "character_identity",
    "prop_identity",
    "material",
    "texture",
    "final_art_style",
}
SPATIAL_CONSTRAINT_MODES = {"spatial_mockup", "depth_layout", "multi_view"}
ROLE_CONTROL_FIELDS = {
    "identity": ["character_identity"],
    "wardrobe": ["wardrobe_identity"],
    "vehicle": ["vehicle_identity"],
    "prop": ["prop_identity"],
    "camera_action": ["camera_action"],
    "style": ["final_art_style"],
    "palette": ["palette"],
    "clean_frame_state": ["clean_frame_state"],
}
LAYOUT_CONTROL_FIELDS = ["geometry", "composition", "occlusion", "scale", "support_relation"]


def default_jingzao_provider_catalog_paths() -> tuple[Path, ...]:
    return (
        Path.home() / ".codex/skills/jingzao-image-forge",
        Path.home() / ".agents/skills/jingzao-image-forge",
        Path.home() / ".skillshub/jingzao-image-forge",
    )


def provider_trust_errors(
    artifact_root: Path,
    provider_root: Path,
    trusted_catalog_paths: tuple[Path, ...] | None,
) -> list[str]:
    try:
        resolved_artifact = artifact_root.resolve(strict=True)
        resolved_provider = provider_root.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        return ["provider_root_invalid: path does not resolve"]
    if (
        resolved_provider.is_relative_to(resolved_artifact)
        or resolved_artifact.is_relative_to(resolved_provider)
    ):
        return ["provider_artifact_root_overlap: resolved roots overlap"]
    candidates: set[Path] = set()
    for candidate in (
        default_jingzao_provider_catalog_paths()
        if trusted_catalog_paths is None
        else trusted_catalog_paths
    ):
        try:
            resolved = candidate.expanduser().resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            continue
        if resolved.is_dir():
            candidates.add(resolved)
    if resolved_provider not in candidates:
        return [f"provider_root_not_installed: {resolved_provider}"]
    return []


def add_error(errors: list[str], code: str, detail: str) -> None:
    errors.append(f"{code}: {detail}")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fixture_png_bytes() -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + name
            + payload
            + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def schema_errors(document: dict[str, Any]) -> list[str]:
    schema = load_json(SCHEMA_PATH)
    if Draft202012Validator is None or os.environ.get("DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"):
        return [
            f"schema_error: {error}"
            for error in _builtin_schema_errors(document, schema, schema, "$")
        ]
    validator = Draft202012Validator(schema)
    return [
        "schema_error: "
        + "/".join(str(item) for item in error.absolute_path)
        + f": {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    ]


def safe_relative_path(raw: Any) -> bool:
    if not isinstance(raw, str) or not raw or "\\" in raw or raw.startswith("/"):
        return False
    parts = raw.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def contained_file(root: Path, raw: Any) -> Path | None:
    if not safe_relative_path(raw):
        return None
    try:
        resolved_root = root.resolve(strict=True)
        candidate = (resolved_root / str(raw)).resolve(strict=True)
        candidate.relative_to(resolved_root)
    except (FileNotFoundError, RuntimeError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def verify_artifact_file(
    binding: dict[str, Any],
    root: Path,
    label: str,
    errors: list[str],
) -> Path | None:
    relative_path = binding.get("relative_path")
    if not safe_relative_path(relative_path):
        add_error(errors, "artifact_path_invalid", f"{label}:{relative_path}")
        return None
    path = contained_file(root, relative_path)
    if path is None:
        add_error(errors, "artifact_file_missing", f"{label}:{relative_path}")
        return None
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != binding.get("sha256"):
        add_error(errors, "artifact_hash_mismatch", f"{label}:{relative_path}")
    return path


def validate_panel_bindings(
    document: dict[str, Any], artifact_root: Path | None
) -> list[str]:
    errors: list[str] = []
    for frame in document.get("frames", []):
        if not isinstance(frame, dict):
            continue
        context = frame.get("panel_context")
        if context is None:
            continue
        frame_id = str(frame.get("frame_id"))
        if not isinstance(context, dict):
            continue
        panel_id = str(context.get("panel_id"))
        if frame_id != panel_id:
            add_error(errors, "panel_context_frame_id_mismatch", panel_id)
        if artifact_root is None:
            add_error(errors, "panel_context_artifact_root_required", panel_id)
            continue
        coverage_file = context.get("coverage_file")
        try:
            coverage_path = contained_file(artifact_root, coverage_file)
        except OSError:
            coverage_path = None
        if coverage_path is None:
            add_error(errors, "panel_context_coverage_path_invalid", panel_id)
            continue
        try:
            if coverage_path.stat().st_size > MAX_JSON_BYTES:
                add_error(errors, "panel_context_coverage_too_large", panel_id)
                continue
            payload = coverage_path.read_bytes()
        except OSError:
            add_error(errors, "panel_context_coverage_file_invalid", panel_id)
            continue
        if hashlib.sha256(payload).hexdigest() != context.get("coverage_sha256"):
            add_error(errors, "panel_context_coverage_hash_mismatch", panel_id)
            continue
        try:
            coverage_document = json.loads(payload.decode("utf-8"))
            if not isinstance(coverage_document, dict):
                raise ValueError("coverage must be a JSON object")
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            add_error(errors, "panel_context_coverage_json_invalid", panel_id)
            continue
        coverage_result = validate_storyboard_coverage(
            coverage_document, artifact_root, "design"
        )
        if coverage_result.get("status") != "valid":
            add_error(errors, "panel_context_coverage_invalid", panel_id)
        panels = coverage_document.get("panels")
        matches = (
            [item for item in panels if isinstance(item, dict) and item.get("panel_id") == panel_id]
            if isinstance(panels, list)
            else []
        )
        if not matches:
            add_error(errors, "panel_context_panel_missing", panel_id)
            continue
        if len(matches) != 1:
            add_error(errors, "panel_context_panel_ambiguous", panel_id)
            continue
        panel = matches[0]
        requirements = {
            item.get("requirement_id"): item
            for item in coverage_document.get("requirements", [])
            if isinstance(item, dict)
        }
        requirement = requirements.get(panel.get("requirement_id"))
        if (
            isinstance(requirement, dict)
            and requirement.get("risk") == "high"
            and not isinstance(frame.get("truth_contract"), dict)
        ):
            add_error(errors, "high_risk_truth_contract_required", panel_id)
        truth = frame.get("truth_contract")
        if isinstance(truth, dict) and isinstance(requirement, dict) and truth.get("risk") != requirement.get("risk"):
            add_error(errors, "truth_contract_risk_mismatch", panel_id)
        for field in ("shot_id", "phase", "at_seconds", "state"):
            declared = frame.get(field) if field == "shot_id" else context.get(field)
            if panel.get(field) != declared:
                add_error(errors, f"panel_context_{field}_mismatch", panel_id)
    return errors


def validate_prompt_manifest(
    path: Path | None,
    expected_frame_ids: set[str],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    prompt_contract_by_frame: dict[str, dict[str, Any]] = {}
    if path is None:
        return prompt_contract_by_frame
    try:
        payload = load_json(path)
    except (json.JSONDecodeError, OSError):
        add_error(errors, "prompt_manifest_invalid", str(path))
        return prompt_contract_by_frame
    frame_prompts = payload.get("frame_prompts") if isinstance(payload, dict) else None
    if not isinstance(frame_prompts, list):
        add_error(errors, "prompt_manifest_frame_prompts_missing", str(path))
        return prompt_contract_by_frame
    for item in frame_prompts:
        if not isinstance(item, dict):
            add_error(errors, "prompt_manifest_frame_entry_invalid", str(path))
            continue
        frame_id = item.get("frame_id")
        prompt = item.get("prompt")
        if (
            not isinstance(frame_id, str)
            or not isinstance(prompt, str)
            or not prompt.strip()
        ):
            add_error(errors, "prompt_manifest_frame_entry_invalid", str(item))
            continue
        actual_prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if item.get("prompt_sha256") != actual_prompt_hash:
            add_error(errors, "prompt_manifest_prompt_hash_mismatch", frame_id)
        if frame_id in prompt_contract_by_frame:
            add_error(errors, "prompt_manifest_frame_duplicate", frame_id)
        reference_inputs = item.get("reference_inputs")
        if reference_inputs is not None and not isinstance(reference_inputs, list):
            add_error(errors, "prompt_manifest_reference_inputs_invalid", frame_id)
            reference_inputs = None
        reference_authority = item.get("reference_authority")
        if reference_authority is not None and not isinstance(reference_authority, list):
            add_error(errors, "prompt_manifest_reference_authority_invalid", frame_id)
            reference_authority = None
        prompt_contract_by_frame[frame_id] = {
            "prompt": prompt,
            "prompt_sha256": actual_prompt_hash,
            "reference_inputs": copy.deepcopy(reference_inputs),
            "reference_authority": copy.deepcopy(reference_authority),
        }
    if set(prompt_contract_by_frame) != expected_frame_ids:
        add_error(
            errors,
            "prompt_manifest_frame_coverage_invalid",
            f"expected={sorted(expected_frame_ids)} actual={sorted(prompt_contract_by_frame)}",
        )
    return prompt_contract_by_frame


def truth_attachment_inputs(
    frame: dict[str, Any],
    artifact_root: Path,
    errors: list[str],
) -> list[dict[str, str]]:
    frame_id = str(frame["frame_id"])
    truth = frame["truth_contract"]
    role_by_id = {str(item["asset_id"]): item for item in frame["reference_roles"]}
    inputs: list[dict[str, str]] = []
    for asset_id in truth["required_attachment_ids"]:
        role = role_by_id.get(str(asset_id))
        attachment = role.get("attachment") if role else None
        if not isinstance(attachment, dict):
            code = (
                "required_scene_attachment_missing"
                if asset_id == truth["scene_asset_id"]
                else "required_attachment_missing"
            )
            add_error(errors, code, f"{frame_id}:{asset_id}")
            continue
        verify_artifact_file(attachment, artifact_root, f"truth_attachment:{frame_id}:{asset_id}", errors)
        inputs.append({
            "source_id": str(asset_id),
            "role": str(role["role"]),
            "relative_path": str(attachment["relative_path"]),
            "sha256": str(attachment["sha256"]),
        })
    return inputs


def truth_reference_authority(frame: dict[str, Any]) -> list[dict[str, Any]]:
    truth = frame["truth_contract"]
    role_by_id = {str(item["asset_id"]): item for item in frame["reference_roles"]}
    result: list[dict[str, Any]] = []
    for asset_id in truth["required_attachment_ids"]:
        role = role_by_id.get(str(asset_id))
        if not role:
            continue
        role_name = str(role["role"])
        may_control = (
            sorted(SCENE_SOVEREIGN_FIELDS)
            if role_name == "scene"
            else sorted(LAYOUT_CONTROL_FIELDS)
            if role_name == "layout"
            else ROLE_CONTROL_FIELDS.get(role_name, [role_name])
        )
        result.append({
            "source_id": str(asset_id),
            "role": role_name,
            "may_control": may_control,
            "must_not_control": sorted(role["must_not_control"]),
        })
    return result


def validate_prompt_authority_review(
    document: dict[str, Any],
    artifact_root: Path,
    prompt_contracts: dict[str, dict[str, Any]],
    review_trust_registry_path: Path | None,
) -> list[str]:
    errors: list[str] = []
    high_frames = [
        frame
        for frame in document.get("frames", [])
        if isinstance(frame, dict)
        and isinstance(frame.get("truth_contract"), dict)
        and frame["truth_contract"].get("risk") == "high"
    ]
    if not high_frames:
        return errors
    output_spec = document.get("output_spec", {})
    relative = output_spec.get("prompt_authority_review_relative_path")
    signature_relative = output_spec.get("prompt_authority_review_signature_relative_path")
    if not safe_relative_path(relative) or not safe_relative_path(signature_relative):
        add_error(errors, "prompt_authority_review_missing", "high-risk handoff")
        return errors
    review_path = contained_file(artifact_root, relative)
    signature_path = contained_file(artifact_root, signature_relative)
    if review_path is None or signature_path is None:
        add_error(errors, "prompt_authority_review_missing", str(relative))
        return errors
    try:
        if review_path.stat().st_size > MAX_JSON_BYTES:
            raise ValueError
        raw = review_path.read_bytes()
    except (OSError, ValueError):
        add_error(errors, "prompt_authority_review_invalid", str(relative))
        return errors
    if hashlib.sha256(raw).hexdigest() != output_spec.get("prompt_authority_review_sha256"):
        add_error(errors, "prompt_authority_review_hash_mismatch", str(relative))
        return errors
    try:
        review = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        add_error(errors, "prompt_authority_review_invalid", str(relative))
        return errors
    if not isinstance(review, dict) or (
        review.get("contract_id") != "prompt_authority_semantic_review_v1"
        or review.get("purpose") != "prompt_authority_review"
        or review.get("source") != "independent_review"
        or not isinstance(review.get("frames"), list)
    ):
        add_error(errors, "prompt_authority_review_invalid", str(relative))
        return errors
    trust_errors = verify_detached_review_artifact(
        review_path,
        signature_path,
        authority_id=review.get("authority_id"),
        actor=review.get("actor"),
        purpose="prompt_authority_review",
        source="independent_review",
        registry_path=review_trust_registry_path,
        artifact_root=artifact_root,
    )
    errors.extend(f"prompt_authority_{item}" for item in trust_errors)
    review_by_frame = {
        str(item.get("frame_id")): item
        for item in review["frames"]
        if isinstance(item, dict)
    }
    expected_ids = {str(frame["frame_id"]) for frame in high_frames}
    if set(review_by_frame) != expected_ids or len(review_by_frame) != len(review["frames"]):
        add_error(errors, "prompt_authority_review_coverage_mismatch", str(sorted(expected_ids)))
    for frame in high_frames:
        frame_id = str(frame["frame_id"])
        item = review_by_frame.get(frame_id, {})
        prompt_contract = prompt_contracts.get(frame_id, {})
        expected = {
            "prompt_sha256": prompt_contract.get("prompt_sha256"),
            "reference_authority_sha256": canonical_sha256(prompt_contract.get("reference_authority")),
            "truth_revision_sha256": canonical_sha256(frame["truth_contract"]),
            "coverage_sha256": frame.get("panel_context", {}).get("coverage_sha256"),
        }
        if any(item.get(key) != value for key, value in expected.items()):
            add_error(errors, "prompt_authority_review_binding_mismatch", frame_id)
        if (
            item.get("verdict") != "pass"
            or item.get("forbidden_control_conflict") is not False
            or item.get("conflicts") != []
        ):
            add_error(errors, "prompt_authority_review_failed", frame_id)
    return errors


def validate_truth_contracts(
    document: dict[str, Any],
    artifact_root: Path | None,
    host_event_log: Path | None,
    trusted_host_log_root: Path | None,
    review_trust_registry_path: Path,
) -> list[str]:
    errors: list[str] = []
    truth_frames = [
        frame
        for frame in document.get("frames", [])
        if isinstance(frame, dict) and isinstance(frame.get("truth_contract"), dict)
    ]
    if not truth_frames:
        return errors
    if artifact_root is None:
        add_error(errors, "truth_artifact_root_required", "truth-bound handoff")
        return errors

    frame_by_id = {str(frame["frame_id"]): frame for frame in truth_frames}
    expected_inputs_by_frame: dict[str, list[dict[str, str]]] = {}
    for frame in truth_frames:
        frame_id = str(frame["frame_id"])
        truth = frame["truth_contract"]
        if not isinstance(frame.get("panel_context"), dict):
            add_error(errors, "truth_contract_risk_source_missing", frame_id)
        canonical = set(frame["canonical_asset_ids"])
        required_ids = set(truth["required_attachment_ids"])
        scene_asset_id = truth["scene_asset_id"]
        roles = frame["reference_roles"]
        role_by_id = {str(item["asset_id"]): item for item in roles}

        if truth["status"] != "ready":
            add_error(errors, "truth_frame_not_ready", frame_id)
        if scene_asset_id not in canonical or scene_asset_id not in required_ids:
            add_error(errors, "scene_truth_unbound", f"{frame_id}:{scene_asset_id}")
        scene_roles = [role for role in roles if role["role"] == "scene"]
        scene_role = role_by_id.get(str(scene_asset_id))
        if len(scene_roles) != 1:
            add_error(errors, "scene_truth_role_ambiguous", frame_id)
        elif not scene_role or scene_role["role"] != "scene":
            add_error(errors, "scene_truth_role_invalid", f"{frame_id}:{scene_asset_id}")
        missing_required = required_ids - canonical
        if missing_required:
            add_error(errors, "required_attachment_not_canonical", f"{frame_id}:{','.join(sorted(missing_required))}")

        constraint = truth["constraint_input"]
        constraint_mode = constraint["mode"]
        constraint_asset_id = constraint["asset_id"]
        for role in roles:
            if role["role"] == "scene":
                continue
            if role["role"] == "layout":
                missing_fields = LAYOUT_SOVEREIGN_FIELDS - set(role["must_not_control"])
                code = "layout_identity_authority_unbounded"
                if constraint_mode not in SPATIAL_CONSTRAINT_MODES or role["asset_id"] != constraint_asset_id:
                    add_error(errors, "layout_constraint_binding_invalid", f"{frame_id}:{role['asset_id']}")
            else:
                missing_fields = SCENE_SOVEREIGN_FIELDS - set(role["must_not_control"])
                code = "reference_background_authority_unbounded"
            if missing_fields:
                detail = f"{frame_id}:{role['asset_id']}:{','.join(sorted(missing_fields))}"
                add_error(errors, code, detail)

        support = truth["support"]
        if support["status"] == "required":
            subject, anchor = support["subject_asset_id"], support["anchor_asset_id"]
            if subject not in canonical or anchor not in canonical or subject == anchor:
                add_error(errors, "support_truth_unbound", frame_id)
            if subject not in required_ids or anchor not in required_ids:
                add_error(errors, "support_truth_attachment_missing", frame_id)
            if support["visibility"] != "explicit_in_frame":
                add_error(errors, "support_truth_not_visible", frame_id)
            if support["relationship"].casefold() in {"unknown", "not_required", "n/a"}:
                add_error(errors, "support_truth_relationship_invalid", frame_id)

        if truth["risk"] == "high" and constraint_mode == "none":
            add_error(errors, "constraint_input_required", frame_id)
        expected_role = "scene" if constraint_mode == "scene_reference" else "layout"
        constraint_role = role_by_id.get(str(constraint_asset_id))
        if constraint_mode == "none":
            if constraint_asset_id is not None:
                add_error(errors, "constraint_input_binding_invalid", frame_id)
        elif (
            not constraint_role
            or constraint_role["role"] != expected_role
            or constraint_asset_id not in required_ids
        ):
            add_error(errors, "constraint_input_binding_invalid", frame_id)
        expected_inputs_by_frame[frame_id] = truth_attachment_inputs(frame, artifact_root, errors)

    for frame_id, frame in frame_by_id.items():
        for parent_id in frame["truth_contract"]["parent_frame_ids"]:
            parent = frame_by_id.get(str(parent_id))
            if parent is None:
                add_error(errors, "parent_truth_missing", f"{frame_id}:{parent_id}")
            elif parent["truth_contract"]["status"] != "ready":
                add_error(errors, "parent_truth_not_ready", f"{frame_id}:{parent_id}")
    output_spec = document.get("output_spec", {})
    prompt_manifest_path = verify_artifact_file(
        {
            "relative_path": output_spec.get("prompt_manifest_relative_path"),
            "sha256": output_spec.get("prompt_manifest_sha256"),
        },
        artifact_root, "truth_prompt_manifest", errors,
    )
    prompt_contracts = validate_prompt_manifest(
        prompt_manifest_path, {str(frame.get("frame_id")) for frame in document.get("frames", [])}, errors,
    )
    for frame_id, expected_inputs in expected_inputs_by_frame.items():
        prompt_contract = prompt_contracts.get(frame_id, {})
        if prompt_contract.get("reference_inputs") != expected_inputs:
            add_error(errors, "execution_attachment_manifest_mismatch", frame_id)
        if prompt_contract.get("reference_authority") != truth_reference_authority(frame_by_id[frame_id]):
            add_error(errors, "prompt_reference_authority_mismatch", frame_id)
    errors.extend(
        validate_prompt_authority_review(
            document,
            artifact_root,
            prompt_contracts,
            review_trust_registry_path,
        )
    )

    consumption = document.get("delivery_consumption", {})
    if consumption.get("status") != "observed_unverified":
        return errors
    if host_event_log is None:
        add_error(errors, "truth_host_event_log_required", "observed truth-bound handoff")
        return errors
    try:
        resolved_log = host_event_log.expanduser().resolve(strict=True)
        resolved_artifact = artifact_root.resolve(strict=True)
        resolved_trusted = (trusted_host_log_root or Path.home() / ".codex/sessions").resolve(strict=True)
        if resolved_log.is_relative_to(resolved_artifact) or not resolved_log.is_relative_to(resolved_trusted):
            raise ValueError
    except (FileNotFoundError, RuntimeError, ValueError):
        add_error(errors, "truth_host_event_log_invalid", str(host_event_log))
        return errors
    evidence, host_errors = parse_host_trace_prefix(
        resolved_log,
        consumption.get("host_trace", {}),
        label="generation host trace",
    )
    errors.extend(f"truth_{item}" for item in host_errors)
    if evidence.get("thread_id") != consumption.get("host_trace", {}).get("thread_id"):
        add_error(errors, "truth_host_trace_thread_mismatch", str(resolved_log))
    actual_requests = [
        event["request"]
        for event in evidence.get("generation_events", {}).values()
        if isinstance(event.get("request"), dict)
    ]
    for frame_id, expected_inputs in expected_inputs_by_frame.items():
        expected_prompt = prompt_contracts.get(frame_id, {}).get("prompt")
        expected_paths = [str((artifact_root / item["relative_path"]).resolve()) for item in expected_inputs]
        if any(
            item.get("prompt") == expected_prompt
            and item.get("referenced_image_paths") == expected_paths
            for item in actual_requests
        ):
            continue
        prompt_matched = any(item.get("prompt") == expected_prompt for item in actual_requests)
        code = (
            "execution_attachment_manifest_mismatch"
            if prompt_matched
            else "execution_prompt_manifest_mismatch"
        )
        add_error(errors, code, frame_id)
    return errors


def parse_host_generation_events(
    path: Path,
    descriptor: dict[str, Any],
    artifact_root: Path,
    trusted_host_log_root: Path | None = None,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    expanded = path.expanduser()
    if not expanded.is_absolute():
        return {}, ["host_event_log_invalid: path must be absolute"]
    try:
        resolved_log = expanded.resolve(strict=True)
        resolved_artifact_root = artifact_root.resolve(strict=True)
        resolved_log.relative_to(resolved_artifact_root)
    except ValueError:
        pass
    except (FileNotFoundError, RuntimeError) as exc:
        return {}, [f"host_event_log_invalid: {exc}"]
    else:
        return {}, ["host_event_log_trust_domain_invalid: host log is inside artifact root"]
    trusted_root = trusted_host_log_root or (Path.home() / ".codex/sessions")
    try:
        resolved_trusted_root = trusted_root.resolve(strict=True)
        resolved_log.relative_to(resolved_trusted_root)
    except (FileNotFoundError, RuntimeError, ValueError):
        return {}, ["host_event_log_trust_domain_invalid: path is outside Codex sessions"]

    prefix_bytes = descriptor.get("prefix_bytes")
    if (
        not isinstance(prefix_bytes, int)
        or prefix_bytes <= 0
        or prefix_bytes > MAX_HOST_TRACE_PREFIX_BYTES
    ):
        return {}, ["host_trace_descriptor_invalid: prefix_bytes"]
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        return {}, ["host_event_log_invalid: O_NOFOLLOW is unavailable"]
    try:
        fd = os.open(resolved_log, os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        return {}, [f"host_event_log_invalid: {exc}"]

    events: dict[str, dict[str, Any]] = {}
    thread_id: str | None = None
    digest = hashlib.sha256()
    remaining = prefix_bytes
    try:
        with os.fdopen(fd, "rb", closefd=False) as handle:
            while remaining:
                raw_line = handle.readline(min(remaining + 1, MAX_HOST_TRACE_LINE_BYTES + 1))
                if not raw_line:
                    errors.append("host_trace_prefix_truncated: event log ended early")
                    break
                if len(raw_line) > remaining:
                    errors.append("host_trace_prefix_boundary_invalid: prefix ends inside a record")
                    break
                if len(raw_line) > MAX_HOST_TRACE_LINE_BYTES:
                    errors.append("host_trace_line_too_large: one record exceeds the limit")
                    break
                digest.update(raw_line)
                remaining -= len(raw_line)
                try:
                    record = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    errors.append("host_trace_record_invalid: record is not UTF-8 JSON")
                    continue
                if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
                    continue
                payload = record["payload"]
                if record.get("type") == "session_meta":
                    observed = payload.get("id") or payload.get("session_id")
                    if isinstance(observed, str):
                        if thread_id not in {None, observed}:
                            errors.append("host_trace_thread_ambiguous: multiple session identities")
                        thread_id = observed
                if record.get("type") != "event_msg" or payload.get("type") != "image_generation_end":
                    continue
                call_id = payload.get("call_id")
                raw_result = payload.get("result")
                if (
                    payload.get("status") != "completed"
                    or not isinstance(call_id, str)
                    or not isinstance(raw_result, str)
                ):
                    continue
                try:
                    image_bytes = base64.b64decode(raw_result, validate=True)
                except binascii.Error:
                    errors.append(f"host_generation_result_invalid: {call_id}")
                    continue
                if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                    errors.append(f"host_generation_result_not_png: {call_id}")
                    continue
                if call_id in events:
                    errors.append(f"host_generation_call_duplicate: {call_id}")
                    continue
                revised_prompt = payload.get("revised_prompt")
                events[call_id] = {
                    "output_sha256": hashlib.sha256(image_bytes).hexdigest(),
                    "prompt_sha256": (
                        hashlib.sha256(revised_prompt.encode("utf-8")).hexdigest()
                        if isinstance(revised_prompt, str)
                        else None
                    ),
                    "saved_path": payload.get("saved_path"),
                }
    finally:
        os.close(fd)
    if remaining == 0 and digest.hexdigest() != descriptor.get("prefix_sha256"):
        errors.append("host_trace_prefix_hash_mismatch: descriptor does not match host bytes")
    if thread_id != descriptor.get("thread_id"):
        errors.append("host_trace_thread_mismatch: descriptor does not match session_meta")
    return events, errors


def production_provenance_errors(
    document: dict[str, Any],
    artifact_root: Path | None,
    provider_root: Path | None,
    host_event_log: Path | None,
    trusted_host_log_root: Path | None,
    trusted_provider_catalog_paths: tuple[Path, ...] | None,
) -> list[str]:
    if document.get("fixture_only") is True:
        return []
    errors: list[str] = []
    if artifact_root is None:
        add_error(errors, "artifact_root_required", "non-fixture handoff")
    if provider_root is None:
        add_error(errors, "provider_root_required", "non-fixture handoff")
    if (
        document.get("delivery_consumption", {}).get("status") == "observed_unverified"
        and host_event_log is None
    ):
        add_error(errors, "host_event_log_required", "observed non-fixture handoff")
    if artifact_root is None or provider_root is None:
        return errors
    trust_errors = provider_trust_errors(
        artifact_root,
        provider_root,
        trusted_provider_catalog_paths,
    )
    errors.extend(trust_errors)
    if trust_errors:
        return errors

    provider_skill = document.get("provider_skill", {})
    provider_skill_path = contained_file(provider_root, "SKILL.md")
    if provider_skill_path is None:
        add_error(errors, "provider_skill_file_missing", "SKILL.md")
    elif hashlib.sha256(provider_skill_path.read_bytes()).hexdigest() != provider_skill.get("sha256"):
        add_error(errors, "provider_skill_hash_mismatch", "SKILL.md")

    for item in document.get("reference_reads", []):
        relative_path = item.get("relative_path")
        if not safe_relative_path(relative_path) or not str(relative_path).startswith("references/"):
            add_error(errors, "reference_path_invalid", str(relative_path))
            continue
        path = contained_file(provider_root, relative_path)
        if path is None:
            add_error(errors, "reference_file_missing", str(relative_path))
            continue
        payload = path.read_bytes()
        if len(payload) != item.get("bytes"):
            add_error(errors, "reference_bytes_mismatch", str(relative_path))
        if hashlib.sha256(payload).hexdigest() != item.get("sha256"):
            add_error(errors, "reference_hash_mismatch", str(relative_path))

    input_spec = document.get("input_spec", {})
    output_spec = document.get("output_spec", {})
    consumption = document.get("delivery_consumption", {})
    verify_artifact_file(input_spec, artifact_root, "input_spec", errors)
    verify_artifact_file(output_spec, artifact_root, "output_spec", errors)
    prompt_manifest = {
        "relative_path": output_spec.get("prompt_manifest_relative_path"),
        "sha256": output_spec.get("prompt_manifest_sha256"),
    }
    prompt_manifest_path = verify_artifact_file(
        prompt_manifest,
        artifact_root,
        "prompt_manifest",
        errors,
    )
    prompt_contract_by_frame = validate_prompt_manifest(
        prompt_manifest_path,
        {str(item.get("frame_id")) for item in document.get("frames", [])},
        errors,
    )

    if consumption.get("status") == "observed_unverified":
        if host_event_log is None:
            return errors
        host_events, host_errors = parse_host_generation_events(
            host_event_log,
            consumption.get("host_trace", {}),
            artifact_root,
            trusted_host_log_root,
        )
        errors.extend(host_errors)

        seen_call_ids: set[str] = set()
        for output in consumption.get("frame_outputs", []):
            frame_id = str(output.get("frame_id"))
            prompt_hash = prompt_contract_by_frame.get(frame_id, {}).get("prompt_sha256")
            receipt_binding = output.get("execution_receipt", {})
            generated_binding = output.get("generated_artifact", {})
            receipt_path = verify_artifact_file(
                receipt_binding,
                artifact_root,
                f"execution_receipt:{frame_id}",
                errors,
            )
            generated_path = verify_artifact_file(
                generated_binding,
                artifact_root,
                f"generated_artifact:{frame_id}",
                errors,
            )
            if generated_path is not None:
                try:
                    png_dimensions(generated_path)
                except ValueError as exc:
                    add_error(errors, "generated_artifact_png_invalid", f"{frame_id}:{exc}")
            if receipt_path is None:
                continue
            try:
                receipt = load_json(receipt_path)
            except (json.JSONDecodeError, OSError):
                add_error(errors, "execution_receipt_invalid", str(receipt_path))
                continue
            if not isinstance(receipt, dict):
                add_error(errors, "execution_receipt_invalid", str(receipt_path))
                continue
            if receipt.get("frame_id") != frame_id:
                add_error(errors, "execution_receipt_frame_mismatch", frame_id)
            if receipt.get("tool") != "image_gen.imagegen" or receipt.get("outcome") != "completed":
                add_error(errors, "execution_receipt_tool_outcome_invalid", frame_id)
            if (
                receipt.get("consumed_spec_id") != output_spec.get("artifact_id")
                or receipt.get("consumed_spec_sha256") != output_spec.get("sha256")
            ):
                add_error(errors, "execution_receipt_spec_mismatch", frame_id)
            if receipt.get("output_ref") != generated_binding.get("relative_path"):
                add_error(errors, "execution_receipt_output_mismatch", frame_id)
            if receipt.get("result_sha256") != generated_binding.get("sha256"):
                add_error(errors, "execution_receipt_result_hash_mismatch", frame_id)
            if prompt_hash is None or receipt.get("prompt_sha256") != prompt_hash:
                add_error(errors, "execution_receipt_prompt_hash_mismatch", frame_id)
            call_id = receipt.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id:
                add_error(errors, "execution_receipt_tool_call_missing", frame_id)
                continue
            if call_id in seen_call_ids:
                add_error(errors, "execution_receipt_tool_call_duplicate", call_id)
            seen_call_ids.add(call_id)
            event = host_events.get(call_id)
            if event is None:
                add_error(errors, "execution_receipt_missing_from_host_trace", call_id)
                continue
            if event.get("output_sha256") != generated_binding.get("sha256"):
                add_error(errors, "host_generation_result_hash_mismatch", frame_id)
            if prompt_hash is None or event.get("prompt_sha256") != prompt_hash:
                add_error(errors, "host_generation_prompt_hash_mismatch", frame_id)
    return errors


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    output_spec = document.get("output_spec", {})
    consumption = document.get("delivery_consumption", {})
    if (
        consumption.get("consumed_spec_id") != output_spec.get("artifact_id")
        or consumption.get("consumed_spec_sha256") != output_spec.get("sha256")
    ):
        add_error(errors, "delivery_spec_provenance_mismatch", "Delivery must echo Jingzao spec ID and hash")
    has_observation = "host_trace" in consumption or "frame_outputs" in consumption
    if has_observation and consumption.get("status") != "observed_unverified":
        add_error(errors, "delivery_observation_status_invalid", str(consumption.get("status")))

    reference_paths: set[str] = set()
    for item in document.get("reference_reads", []):
        path = item.get("relative_path")
        if not safe_relative_path(path) or not str(path).startswith("references/"):
            add_error(errors, "reference_path_invalid", str(path))
        if path in reference_paths:
            add_error(errors, "reference_read_duplicate", str(path))
        reference_paths.add(path)

    frame_ids: set[str] = set()
    shot_ids: set[str] = set()
    for frame in document.get("frames", []):
        frame_id = str(frame.get("frame_id"))
        shot_id = str(frame.get("shot_id"))
        if frame_id in frame_ids:
            add_error(errors, "frame_id_duplicate", frame_id)
        if shot_id in shot_ids:
            add_error(errors, "frame_shot_duplicate", shot_id)
        frame_ids.add(frame_id)
        shot_ids.add(shot_id)

        canonical = set(frame.get("canonical_asset_ids", []))
        role_assets = [item.get("asset_id") for item in frame.get("reference_roles", [])]
        if canonical != set(role_assets) or len(role_assets) != len(set(role_assets)):
            add_error(errors, "reference_asset_coverage_invalid", frame_id)

        for field in DYNAMIC_FIELDS:
            value = frame.get(field)
            if frame.get("shot_class") in ACTION_CLASSES and not isinstance(value, str):
                add_error(errors, "action_frame_dynamic_missing", f"{frame_id}:{field}")
            if isinstance(value, dict):
                reason = str(value.get("reason", "")).strip()
                if reason.casefold() in GENERIC_NA_REASONS or len(reason) < 24:
                    add_error(errors, "dynamic_na_reason_invalid", f"{frame_id}:{field}")
    if consumption.get("status") == "observed_unverified":
        output_frame_ids = [
            str(item.get("frame_id"))
            for item in consumption.get("frame_outputs", [])
            if isinstance(item, dict)
        ]
        if set(output_frame_ids) != frame_ids or len(output_frame_ids) != len(set(output_frame_ids)):
            add_error(
                errors,
                "output_frame_coverage_invalid",
                f"expected={sorted(frame_ids)} actual={sorted(output_frame_ids)}",
            )
    return errors


def validate(
    document: dict[str, Any],
    *,
    artifact_root: Path | None = None,
    provider_root: Path | None = None,
    host_event_log: Path | None = None,
    trusted_host_log_root: Path | None = None,
    _review_trust_registry_path: Path | None = None,
    _trusted_provider_catalog_roots: tuple[Path, ...] | None = None,
) -> list[str]:
    structural = schema_errors(document)
    if structural:
        return structural
    return (
        semantic_errors(document)
        + validate_panel_bindings(document, artifact_root)
        + validate_truth_contracts(
            document,
            artifact_root,
            host_event_log,
            trusted_host_log_root,
            _review_trust_registry_path,
        )
        + production_provenance_errors(
            document,
            artifact_root,
            provider_root,
            host_event_log,
            trusted_host_log_root,
            _trusted_provider_catalog_roots,
        )
    )


def self_test() -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    valid = load_json(VALID_PATH)
    valid_errors = validate(valid)
    if valid_errors:
        failures.append(f"valid fixture rejected: {valid_errors[:3]}")
    cases = load_json(CASES_PATH).get("cases", [])
    rejected = 0
    for case in cases:
        errors = validate(apply_mutations(valid, case["mutations"]))
        expected = case["expected_error"]
        if any(error.startswith(expected + ":") for error in errors):
            rejected += 1
        else:
            failures.append(f"{case['case_id']}: expected {expected}, got {errors[:3]}")

    production_observation_fixture_passed = False
    with tempfile.TemporaryDirectory(prefix="dircreative-jingzao-provenance-") as temp_dir:
        temp_root = Path(temp_dir)
        artifact_root = temp_root / "artifacts"
        provider_root = temp_root / "provider"
        trusted_host_root = temp_root / "trusted-sessions"
        artifact_root.mkdir()
        (provider_root / "references").mkdir(parents=True)
        trusted_host_root.mkdir()
        production = copy.deepcopy(valid)
        production["fixture_only"] = False

        skill_payload = b"fixture jingzao skill\n"
        (provider_root / "SKILL.md").write_bytes(skill_payload)
        production["provider_skill"]["sha256"] = hashlib.sha256(skill_payload).hexdigest()
        for index, item in enumerate(production["reference_reads"]):
            payload = f"reference {index}\n".encode("utf-8")
            path = provider_root / item["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            item["bytes"] = len(payload)
            item["sha256"] = hashlib.sha256(payload).hexdigest()

        artifact_bindings = [
            (production["input_spec"], b"dir input\n"),
            (production["output_spec"], b"jingzao output\n"),
        ]
        for binding, payload in artifact_bindings:
            path = artifact_root / binding["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            binding["sha256"] = hashlib.sha256(payload).hexdigest()
        prompt_text_by_frame = {
            str(frame["frame_id"]): f"fixture cinematic prompt for {frame['frame_id']}"
            for frame in production["frames"]
        }
        prompt_payload = (
            json.dumps(
                {
                    "frame_prompts": [
                        {
                            "frame_id": frame_id,
                            "prompt": prompt_text,
                            "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
                        }
                        for frame_id, prompt_text in prompt_text_by_frame.items()
                    ]
                },
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        prompt_path = artifact_root / production["output_spec"]["prompt_manifest_relative_path"]
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_bytes(prompt_payload)
        production["output_spec"]["prompt_manifest_sha256"] = hashlib.sha256(prompt_payload).hexdigest()
        production["delivery_consumption"]["consumed_spec_sha256"] = production["output_spec"]["sha256"]

        generated_payload = fixture_png_bytes()
        host_records: list[dict[str, Any]] = [
            {
                "timestamp": "2026-08-21T00:00:00Z",
                "type": "session_meta",
                "payload": {"id": "fixture-thread"},
            }
        ]
        generated_paths: list[Path] = []
        for index, output in enumerate(production["delivery_consumption"]["frame_outputs"], start=1):
            frame_id = output["frame_id"]
            prompt_text = prompt_text_by_frame[frame_id]
            prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
            call_id = f"exec-fixture-{index}"
            generated_binding = output["generated_artifact"]
            generated_path = artifact_root / generated_binding["relative_path"]
            generated_path.parent.mkdir(parents=True, exist_ok=True)
            generated_path.write_bytes(generated_payload)
            generated_paths.append(generated_path)
            generated_binding["sha256"] = hashlib.sha256(generated_payload).hexdigest()
            receipt_binding = output["execution_receipt"]
            receipt = {
                "frame_id": frame_id,
                "tool": "image_gen.imagegen",
                "tool_call_id": call_id,
                "outcome": "completed",
                "consumed_spec_id": production["output_spec"]["artifact_id"],
                "consumed_spec_sha256": production["output_spec"]["sha256"],
                "prompt_sha256": prompt_hash,
                "output_ref": generated_binding["relative_path"],
                "result_sha256": generated_binding["sha256"],
            }
            receipt_path = artifact_root / receipt_binding["relative_path"]
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
            receipt_binding["sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            host_records.append(
                {
                    "timestamp": f"2026-08-21T00:00:0{index}Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "image_generation_end",
                        "call_id": call_id,
                        "status": "completed",
                        "revised_prompt": prompt_text,
                        "result": base64.b64encode(generated_payload).decode("ascii"),
                        "saved_path": f"/host/generated/{call_id}.png",
                    },
                }
            )
        host_log = trusted_host_root / "host-events.jsonl"
        host_log.write_bytes(
            b"".join(
                (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
                for record in host_records
            )
        )
        production["delivery_consumption"]["host_trace"] = {
            "thread_id": "fixture-thread",
            "prefix_bytes": host_log.stat().st_size,
            "prefix_sha256": hashlib.sha256(host_log.read_bytes()).hexdigest(),
        }

        production_errors = validate(
            production,
            artifact_root=artifact_root,
            provider_root=provider_root,
            _trusted_provider_catalog_roots=(provider_root,),
            host_event_log=host_log,
            trusted_host_log_root=trusted_host_root,
        )
        production_observation_fixture_passed = not production_errors
        if production_errors:
            failures.append(f"host-observation fixture rejected: {production_errors[:3]}")

        planned = copy.deepcopy(production)
        planned["delivery_consumption"]["status"] = "planned"
        planned["delivery_consumption"].pop("host_trace", None)
        planned["delivery_consumption"].pop("frame_outputs", None)
        first_id = next(iter(prompt_text_by_frame))
        valid_entries = [
            {
                "frame_id": frame_id,
                "prompt": prompt_text,
                "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            }
            for frame_id, prompt_text in prompt_text_by_frame.items()
        ]
        planned_manifest_cases = [
            ({}, "prompt_manifest_frame_prompts_missing"),
            ({"frame_prompts": [valid_entries[0]]}, "prompt_manifest_frame_coverage_invalid"),
            (
                {"frame_prompts": [valid_entries[0], valid_entries[0], valid_entries[1]]},
                "prompt_manifest_frame_duplicate",
            ),
            (
                {
                    "frame_prompts": [
                        {**valid_entries[0], "prompt_sha256": "f" * 64},
                        valid_entries[1],
                    ]
                },
                "prompt_manifest_prompt_hash_mismatch",
            ),
            (
                {
                    "frame_prompts": [
                        {
                            "frame_id": first_id,
                            "prompt": "   ",
                            "prompt_sha256": hashlib.sha256(b"   ").hexdigest(),
                        },
                        valid_entries[1],
                    ]
                },
                "prompt_manifest_frame_entry_invalid",
            ),
        ]
        for manifest_payload, expected_code in planned_manifest_cases:
            prompt_path.write_text(
                json.dumps(manifest_payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            planned["output_spec"]["prompt_manifest_sha256"] = hashlib.sha256(
                prompt_path.read_bytes()
            ).hexdigest()
            planned_errors = validate(
                planned,
                artifact_root=artifact_root,
                provider_root=provider_root,
                _trusted_provider_catalog_roots=(provider_root,),
            )
            if not any(error.startswith(expected_code + ":") for error in planned_errors):
                failures.append(
                    f"planned manifest case expected {expected_code}, got {planned_errors[:3]}"
                )
        prompt_path.write_bytes(prompt_payload)

        generated_paths[0].write_bytes(b"tampered image\n")
        tampered_errors = validate(
            production,
            artifact_root=artifact_root,
            provider_root=provider_root,
            _trusted_provider_catalog_roots=(provider_root,),
            host_event_log=host_log,
            trusted_host_log_root=trusted_host_root,
        )
        if not any(error.startswith("artifact_hash_mismatch:") for error in tampered_errors):
            failures.append(f"tampered generated artifact accepted: {tampered_errors[:3]}")
        generated_paths[0].write_bytes(generated_payload)
        self_issued_host_log = artifact_root / "self-issued-host-events.jsonl"
        self_issued_host_log.write_bytes(host_log.read_bytes())
        self_issued_errors = validate(
            production,
            artifact_root=artifact_root,
            provider_root=provider_root,
            _trusted_provider_catalog_roots=(provider_root,),
            host_event_log=self_issued_host_log,
            trusted_host_log_root=trusted_host_root,
        )
        if not any(
            error.startswith("host_event_log_trust_domain_invalid:")
            for error in self_issued_errors
        ):
            failures.append(f"artifact-root host evidence accepted: {self_issued_errors[:3]}")
        external_fake_log = temp_root / "producer-written-host-events.jsonl"
        external_fake_log.write_bytes(host_log.read_bytes())
        external_fake_errors = validate(
            production,
            artifact_root=artifact_root,
            provider_root=provider_root,
            _trusted_provider_catalog_roots=(provider_root,),
            host_event_log=external_fake_log,
            trusted_host_log_root=trusted_host_root,
        )
        if not any(
            error.startswith("host_event_log_trust_domain_invalid:")
            for error in external_fake_errors
        ):
            failures.append(f"untrusted external host evidence accepted: {external_fake_errors[:3]}")
    return failures, {
        "valid_fixture_passed": not valid_errors,
        "frame_count": len(valid.get("frames", [])),
        "reference_read_count": len(valid.get("reference_reads", [])),
        "negative_case_count": len(cases),
        "negative_cases_rejected": rejected,
        "delivery_provenance_bound": not valid_errors,
        "generation_claim_allowed": False,
        "planned_prompt_manifest_controls": True,
        "production_observation_fixture_passed": production_observation_fixture_passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIRcreative-to-Jingzao frame handoffs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--artifact-root", type=Path)
    validate_parser.add_argument("--provider-root", type=Path)
    validate_parser.add_argument("--host-event-log", type=Path)
    validate_parser.add_argument("--review-trust-registry", type=Path)
    args = parser.parse_args()

    if args.command == "self-test":
        failures, summary = self_test()
        print(json.dumps({**summary, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"DIRCREATIVE_STORYBOARD_FRAME_HANDOFF_AUDIT: {'PASS' if not failures else 'FAIL'}")
        return 0 if not failures else 1

    errors = validate(
        load_json(args.path),
        artifact_root=args.artifact_root,
        provider_root=args.provider_root,
        host_event_log=args.host_event_log,
        _review_trust_registry_path=args.review_trust_registry,
    )
    registry_path = args.review_trust_registry or default_review_trust_registry_path()
    trust_blocked = any(
        "review_trust_registry_" in error or "review_authority_unconfigured:" in error
        for error in errors
    )
    print(json.dumps({
        "status": "TOOL_BLOCKED" if trust_blocked else "valid" if not errors else "invalid",
        "path": str(args.path),
        "review_trust_registry_path": str(registry_path),
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 2 if trust_blocked else 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
