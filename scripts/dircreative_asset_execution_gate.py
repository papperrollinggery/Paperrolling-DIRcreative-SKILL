#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import dircreative_prompt_compiler as prompt_compiler
import dircreative_storyboard_frame_handoff as storyboard_handoff
import dircreative_visual_asset_jingzao_handoff as visual_asset_jingzao_handoff
from dircreative_character_master_visual_gate import (
    load_character_master_receipt,
    load_headless_review_authorization,
    load_visual_review_authorization,
)
from dircreative_verify_release import read_relative_regular_file_once
from dircreative_prompt_compiler import (
    build_asset_role_prompt as build_role_prompt,
    build_character_prompt_from_contract,
    build_character_master_prompt,
    build_character_master_prompt_from_contract,
)
from dircreative_visual_asset_plan import (
    VISUAL_QA_RULESET,
    contained_file,
    inspect_raster,
    receipt_sha256,
    validate_plan,
    validate_technical_receipt,
    validate_visual_qa_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID = "asset_execution_gate_v1"
MAX_VISUAL_PLAN_BYTES = 8 * 1024 * 1024
MAX_PACKET_BYTES = 512 * 1024
MAX_PROMPT_CHARS = 65536
MAX_DEPENDENCIES = 256
MAX_JINGZAO_HANDOFF_BYTES = 8 * 1024 * 1024
MAX_JINGZAO_PROMPT_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_JINGZAO_SEALED_FILE_BYTES = 32 * 1024 * 1024
MAX_JINGZAO_SEALED_TOTAL_BYTES = 256 * 1024 * 1024
APPROVED_DEPENDENCY_STATES = {"visual_qa_pass", "user_locked", "reused_locked"}
JINGZAO_PROMPT_ROLES = {
    "storyboard_frame",
    "clean_first_frame",
    "clean_key_frame",
    "clean_end_frame",
}
JINGZAO_FORMAL_ASSET_ROLES = {
    "character_identity_reference",
    "product_identity_board",
    "prop_continuity_board",
    "scene_geography_camera_fov_reference",
    "lighting_material_style_board",
}
DETERMINISTIC_ASSEMBLY_ROLES = {"professional_storyboard_motion_map"}
DEPENDENT_ASSET_ROLES = {
    "storyboard_frame",
    "professional_storyboard_motion_map",
    "clean_first_frame",
    "clean_key_frame",
    "clean_end_frame",
}
ROLE_STAGE_CONTRACTS = {
    "character_identity_reference": (
        "identity_state",
        "skills/dircreative/references/character-master-sheet.md",
    ),
    "product_identity_board": (
        "production_design",
        "skills/dircreative/references/asset-foundation-pass.md",
    ),
    "prop_continuity_board": (
        "production_design",
        "skills/dircreative/references/asset-foundation-pass.md",
    ),
    "scene_geography_camera_fov_reference": (
        "camera_geography",
        "skills/dircreative/references/asset-foundation-pass.md",
    ),
    "lighting_material_style_board": (
        "material_response",
        "skills/dircreative/references/asset-foundation-pass.md",
    ),
    "storyboard_frame": (
        "frame_compile",
        "skills/dircreative/references/storyboard-frame-to-jingzao.md",
    ),
    "professional_storyboard_motion_map": (
        "frame_compile",
        "skills/dircreative/references/storyboard-frame-to-jingzao.md",
    ),
    "clean_first_frame": (
        "frame_compile",
        "skills/dircreative/references/storyboard-frame-to-jingzao.md",
    ),
    "clean_key_frame": (
        "frame_compile",
        "skills/dircreative/references/storyboard-frame-to-jingzao.md",
    ),
    "clean_end_frame": (
        "frame_compile",
        "skills/dircreative/references/storyboard-frame-to-jingzao.md",
    ),
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_packet_sha256(packet: Any) -> str:
    return hashlib.sha256(
        json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_prompt_authority(
    asset: dict[str, Any],
    prompt_sha256: str,
    *,
    jingzao_handoff_sha256: str | None = None,
    jingzao_provider_skill_sha256: str | None = None,
    jingzao_prompt_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    role = asset.get("role")
    provider_compiled = jingzao_handoff_sha256 is not None
    compiler_id = (
        "jingzao-image-forge:storyboard_frame_to_jingzao_v1"
        if provider_compiled and role in JINGZAO_PROMPT_ROLES
        else "jingzao-image-forge:visual_asset_to_jingzao_v1"
        if provider_compiled
        else "character-master-sheet-v3"
        if role == "character_identity_reference"
        else "dircreative-prompt-compiler-v1"
    )
    authority = {
        "contract_id": "asset_prompt_authority_v1",
        "compiler_id": compiler_id,
        "compiler_source_sha256": (
            jingzao_provider_skill_sha256
            if provider_compiled
            else _file_sha256(Path(prompt_compiler.__file__))
        ),
        "active_asset_truth_sha256": asset.get("truth_sha256"),
        "authoritative_purpose_sha256": sha256_text(str(asset.get("purpose", ""))),
        "prompt_sha256": prompt_sha256,
        "override_policy": "exact_compiler_output_only",
    }
    if provider_compiled:
        authority["provider_handoff_sha256"] = jingzao_handoff_sha256
        authority["provider_prompt_manifest_sha256"] = jingzao_prompt_manifest_sha256
    return authority


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def character_plan_binding_errors(
    master: dict[str, Any],
    active_asset: dict[str, Any],
    visual_plan: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    mode = master.get("mode")
    expected_mode = active_asset.get("character_mode")
    if mode != expected_mode:
        errors.append("character_master_mode_truth_mismatch")
    source_id = master.get("derived_from_asset_id")
    source_sha = master.get("approved_source_master_sha256")
    if source_id != active_asset.get("derived_from_asset_id") or source_sha != active_asset.get(
        "approved_source_master_sha256"
    ):
        errors.append("character_master_source_truth_mismatch")
    if mode in {"headed_state", "headless_safe"}:
        source_asset = next(
            (
                item
                for item in visual_plan.get("assets", [])
                if isinstance(item, dict) and item.get("asset_id") == source_id
            ),
            None,
        )
        if active_asset.get("inherits_from") != [source_id]:
            errors.append("character_master_source_inheritance_mismatch")
        if (
            not isinstance(source_asset, dict)
            or source_asset.get("role") != "character_identity_reference"
            or source_asset.get("character_mode") != "headed_master"
            or source_asset.get("status") not in {"generated_candidate", "user_locked", "reused_locked"}
            or source_asset.get("generated_sha256") != source_sha
        ):
            errors.append("character_master_source_evidence_mismatch")
    return errors


def _sealed_jingzao_validation(
    document: dict[str, Any],
    *,
    project_root: Path,
    provider_root: Path,
    errors: list[str],
) -> dict[str, bytes] | None:
    artifact_files: dict[str, bytes] = {}
    provider_files: dict[str, bytes] = {}
    total_bytes = 0

    def seal(
        root: Path,
        destination: dict[str, bytes],
        relative: Any,
        expected_sha256: Any,
        label: str,
        *,
        expected_bytes: Any = None,
    ) -> None:
        nonlocal total_bytes
        if not isinstance(relative, str):
            raise ValueError(f"{label} path invalid")
        payload = read_relative_regular_file_once(
            root,
            relative,
            max_bytes=MAX_JINGZAO_SEALED_FILE_BYTES,
            label=label,
        )
        if expected_sha256 is not None and hashlib.sha256(payload).hexdigest() != expected_sha256:
            raise ValueError(f"{label} hash mismatch")
        if expected_bytes is not None and len(payload) != expected_bytes:
            raise ValueError(f"{label} byte count mismatch")
        previous = destination.get(relative)
        if previous is not None and previous != payload:
            raise ValueError(f"{label} duplicate path conflict")
        if previous is None:
            total_bytes += len(payload)
            if total_bytes > MAX_JINGZAO_SEALED_TOTAL_BYTES:
                raise ValueError("Jingzao sealed input set exceeds total size limit")
            destination[relative] = payload

    try:
        provider = document.get("provider_skill", {})
        seal(
            provider_root,
            provider_files,
            "SKILL.md",
            provider.get("sha256"),
            "Jingzao provider Skill",
        )
        for item in document.get("reference_reads", []):
            seal(
                provider_root,
                provider_files,
                item.get("relative_path"),
                item.get("sha256"),
                "Jingzao provider reference",
                expected_bytes=item.get("bytes"),
            )
        input_spec = document.get("input_spec", {})
        output_spec = document.get("output_spec", {})
        for binding, label in ((input_spec, "DIR input spec"), (output_spec, "Jingzao output spec")):
            seal(
                project_root,
                artifact_files,
                binding.get("relative_path"),
                binding.get("sha256"),
                label,
            )
        seal(
            project_root,
            artifact_files,
            output_spec.get("prompt_manifest_relative_path"),
            output_spec.get("prompt_manifest_sha256"),
            "Jingzao prompt manifest",
        )
        review_relative = output_spec.get("prompt_authority_review_relative_path")
        if review_relative is not None:
            seal(
                project_root,
                artifact_files,
                review_relative,
                output_spec.get("prompt_authority_review_sha256"),
                "Jingzao prompt authority review",
            )
            seal(
                project_root,
                artifact_files,
                output_spec.get("prompt_authority_review_signature_relative_path"),
                None,
                "Jingzao prompt authority review signature",
            )
        for frame in document.get("frames", []):
            panel = frame.get("panel_context") if isinstance(frame, dict) else None
            if isinstance(panel, dict):
                seal(
                    project_root,
                    artifact_files,
                    panel.get("coverage_file"),
                    panel.get("coverage_sha256"),
                    "storyboard coverage",
                )
            for role in frame.get("reference_roles", []) if isinstance(frame, dict) else []:
                attachment = role.get("attachment") if isinstance(role, dict) else None
                if isinstance(attachment, dict):
                    seal(
                        project_root,
                        artifact_files,
                        attachment.get("relative_path"),
                        attachment.get("sha256"),
                        "Jingzao truth attachment",
                    )
    except (OSError, ValueError):
        errors.append("jingzao_sealed_input_validation_failed")
        return None

    with tempfile.TemporaryDirectory(prefix="dircreative-jingzao-sealed-") as raw:
        snapshot = Path(raw)
        artifact_snapshot = snapshot / "artifacts"
        provider_snapshot = snapshot / "provider"
        artifact_snapshot.mkdir()
        provider_snapshot.mkdir()
        for relative, payload in artifact_files.items():
            target = artifact_snapshot.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        for relative, payload in provider_files.items():
            target = provider_snapshot.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        handoff_errors = storyboard_handoff.validate(
            document,
            artifact_root=artifact_snapshot,
            provider_root=provider_snapshot,
            _trusted_provider_catalog_roots=(provider_snapshot,),
        )
    if handoff_errors:
        errors.append("jingzao_handoff_validation_failed")
        return None
    return artifact_files


def _verified_jingzao_prompt(
    packet: dict[str, Any],
    active_asset: dict[str, Any],
    visual_plan: dict[str, Any],
    *,
    project_root: Path,
    trusted_provider_roots: tuple[Path, ...] | None,
    errors: list[str],
) -> str | None:
    binding = packet.get("jingzao_handoff")
    if not isinstance(binding, dict):
        errors.append("jingzao_handoff_missing")
        return None
    relative = binding.get("path")
    if not isinstance(relative, str):
        errors.append("jingzao_handoff_path_invalid")
        return None
    try:
        handoff_bytes = read_relative_regular_file_once(
            project_root,
            relative,
            max_bytes=MAX_JINGZAO_HANDOFF_BYTES,
            label="Jingzao handoff",
        )
        if hashlib.sha256(handoff_bytes).hexdigest() != binding.get("sha256"):
            errors.append("jingzao_handoff_hash_mismatch")
            return None
        document = json.loads(handoff_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        errors.append("jingzao_handoff_file_invalid")
        return None
    if not isinstance(document, dict) or document.get("fixture_only") is not False:
        errors.append("jingzao_handoff_not_production")
        return None
    output_spec = document.get("output_spec", {})
    if (
        binding.get("provider_skill_sha256") != document.get("provider_skill", {}).get("sha256")
        or binding.get("prompt_manifest_sha256") != output_spec.get("prompt_manifest_sha256")
    ):
        errors.append("jingzao_handoff_authority_binding_mismatch")
        return None
    catalog = (
        storyboard_handoff.default_jingzao_provider_catalog_paths()
        if trusted_provider_roots is None
        else trusted_provider_roots
    )
    provider_root: Path | None = None
    expected_provider_sha = document.get("provider_skill", {}).get("sha256")
    for candidate in catalog:
        try:
            skill_bytes = read_relative_regular_file_once(
                candidate,
                "SKILL.md",
                max_bytes=1024 * 1024,
                label="Jingzao provider Skill",
            )
        except (OSError, ValueError):
            continue
        if hashlib.sha256(skill_bytes).hexdigest() == expected_provider_sha:
            provider_root = candidate
            break
    if provider_root is None:
        errors.append("jingzao_provider_not_installed_or_hash_mismatch")
        return None
    if document.get("delivery_consumption", {}).get("status") != "planned":
        errors.append("jingzao_handoff_not_pre_execution_planned")
        return None
    sealed_artifacts = _sealed_jingzao_validation(
        document,
        project_root=project_root,
        provider_root=provider_root,
        errors=errors,
    )
    if sealed_artifacts is None:
        return None
    input_spec = document.get("input_spec", {})
    try:
        input_bytes = sealed_artifacts[input_spec.get("relative_path")]
        input_payload = json.loads(input_bytes.decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        errors.append("jingzao_input_spec_invalid")
        return None
    if hashlib.sha256(input_bytes).hexdigest() != input_spec.get("sha256"):
        errors.append("jingzao_input_spec_hash_mismatch")
        return None
    manifest_relative = output_spec.get("prompt_manifest_relative_path")
    try:
        manifest_bytes = sealed_artifacts[manifest_relative]
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        errors.append("jingzao_prompt_manifest_invalid")
        return None
    if hashlib.sha256(manifest_bytes).hexdigest() != output_spec.get("prompt_manifest_sha256"):
        errors.append("jingzao_prompt_manifest_hash_mismatch")
        return None
    covered_shots = active_asset.get("coverage", {}).get("shot_ids", [])
    if not isinstance(covered_shots, list) or len(covered_shots) != 1:
        errors.append("jingzao_asset_requires_exactly_one_shot")
        return None
    shot_id = str(covered_shots[0])
    frame = next(
        (item for item in document.get("frames", []) if item.get("shot_id") == shot_id),
        None,
    )
    truth = next(
        (item for item in visual_plan.get("shot_truth", []) if item.get("shot_id") == shot_id),
        None,
    )
    if (
        not isinstance(frame, dict)
        or not isinstance(truth, dict)
        or frame.get("narrative_purpose") != truth.get("narrative_purpose")
        or frame.get("generation_unit_id") != truth.get("generation_unit_id")
    ):
        errors.append("jingzao_frame_truth_mismatch")
        return None
    input_frame = next(
        (
            item
            for item in input_payload.get("frames", [])
            if isinstance(item, dict) and item.get("frame_id") == frame.get("frame_id")
        ),
        None,
    ) if isinstance(input_payload, dict) else None
    expected_truth_sha = canonical_json_sha256(truth)
    if (
        not isinstance(input_payload, dict)
        or input_payload.get("contract_id") != "dircreative_jingzao_input_v1"
        or not isinstance(input_frame, dict)
        or input_frame.get("asset_id") != active_asset.get("asset_id")
        or input_frame.get("asset_role") != active_asset.get("role")
        or input_frame.get("active_asset_truth_sha256") != active_asset.get("truth_sha256")
        or input_frame.get("shot_truth_sha256") != expected_truth_sha
        or input_frame.get("shot_truth") != truth
        or input_frame.get("frame_contract") != frame
    ):
        errors.append("jingzao_input_spec_active_truth_mismatch")
        return None
    expected_dependencies = active_asset.get("inherits_from", [])
    frame_dependencies = frame.get("canonical_asset_ids", [])
    if frame_dependencies != expected_dependencies:
        errors.append("jingzao_frame_dependency_mismatch")
        return None
    prompt_entry = next(
        (
            item
            for item in manifest.get("frame_prompts", [])
            if isinstance(item, dict) and item.get("frame_id") == frame.get("frame_id")
        ),
        None,
    )
    prompt = prompt_entry.get("prompt") if isinstance(prompt_entry, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append("jingzao_compiled_prompt_missing")
        return None
    if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != prompt_entry.get("prompt_sha256"):
        errors.append("jingzao_compiled_prompt_hash_mismatch")
        return None
    if (
        prompt_entry.get("asset_id") != active_asset.get("asset_id")
        or prompt_entry.get("asset_role") != active_asset.get("role")
        or prompt_entry.get("active_asset_truth_sha256") != active_asset.get("truth_sha256")
        or prompt_entry.get("shot_truth_sha256") != expected_truth_sha
        or prompt_entry.get("dependency_asset_ids") != expected_dependencies
    ):
        errors.append("jingzao_prompt_active_asset_binding_mismatch")
        return None
    required_prompt_truth = [
        truth.get("scene_id"),
        *truth.get("character_ids", []),
        *truth.get("appearance_state_ids", []),
        *truth.get("product_ids", []),
        *truth.get("prop_ids", []),
        truth.get("narrative_purpose"),
        truth.get("timecode"),
        str(truth.get("duration_seconds")),
        truth.get("shot_design"),
        truth.get("action"),
        truth.get("sound_edit"),
        truth.get("continuity_model"),
    ]
    if any(str(value) not in prompt for value in required_prompt_truth if value not in {None, ""}):
        errors.append("jingzao_prompt_missing_active_shot_truth")
        return None
    if active_asset.get("role") in {"clean_first_frame", "clean_key_frame", "clean_end_frame"}:
        clean_markers = (
            "no visible title",
            "no text",
            "no label",
            "no arrow",
            "no border",
            "no panel",
            "Direct video input policy: allowed",
        )
        if any(marker not in prompt for marker in clean_markers):
            errors.append("jingzao_clean_prompt_contract_missing")
            return None
    return prompt


def _verified_visual_asset_jingzao_prompt(
    packet: dict[str, Any],
    active_asset: dict[str, Any],
    *,
    project_root: Path,
    trusted_provider_roots: tuple[Path, ...] | None,
    allow_unsandboxed_test_replay: bool,
    errors: list[str],
) -> str | None:
    binding = packet.get("jingzao_asset_handoff")
    if not isinstance(binding, dict) or set(binding) != {
        "path",
        "sha256",
        "provider_skill_sha256",
        "compiled_prompt_manifest_sha256",
        "skill_stack_receipt_sha256",
    }:
        errors.append("jingzao_asset_handoff_missing")
        return None
    relative = binding.get("path")
    if not isinstance(relative, str):
        errors.append("jingzao_asset_handoff_path_invalid")
        return None
    try:
        payload = read_relative_regular_file_once(
            project_root,
            relative,
            max_bytes=MAX_JINGZAO_HANDOFF_BYTES,
            label="visual asset Jingzao handoff",
        )
        if hashlib.sha256(payload).hexdigest() != binding.get("sha256"):
            errors.append("jingzao_asset_handoff_hash_mismatch")
            return None
        document = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        errors.append("jingzao_asset_handoff_file_invalid")
        return None
    if not isinstance(document, dict) or document.get("fixture_only") is not False:
        errors.append("jingzao_asset_handoff_not_production")
        return None
    output = document.get("output_spec", {})
    stack_binding = document.get("skill_stack_receipt", {})
    active = document.get("active_asset", {})
    plan_binding = packet.get("visual_plan", {})
    if (
        binding.get("provider_skill_sha256")
        != document.get("provider_skill", {}).get("sha256")
        or binding.get("compiled_prompt_manifest_sha256")
        != output.get("compiled_prompt_manifest", {}).get("sha256")
        or binding.get("skill_stack_receipt_sha256") != stack_binding.get("sha256")
    ):
        errors.append("jingzao_asset_handoff_authority_binding_mismatch")
        return None
    if (
        active.get("asset_id") != active_asset.get("asset_id")
        or active.get("role") != active_asset.get("role")
        or active.get("truth_sha256") != active_asset.get("truth_sha256")
        or active.get("purpose_sha256")
        != sha256_text(str(active_asset.get("purpose", "")))
        or active.get("visual_plan_sha256") != plan_binding.get("sha256")
    ):
        errors.append("jingzao_asset_handoff_active_asset_mismatch")
        return None
    catalog = (
        visual_asset_jingzao_handoff.default_provider_roots()
        if trusted_provider_roots is None
        else trusted_provider_roots
    )
    provider_root: Path | None = None
    expected_provider_sha = document.get("provider_skill", {}).get("sha256")
    for candidate in catalog:
        try:
            skill_bytes = read_relative_regular_file_once(
                candidate,
                "SKILL.md",
                max_bytes=1024 * 1024,
                label="Jingzao provider Skill",
            )
        except (OSError, ValueError):
            continue
        if hashlib.sha256(skill_bytes).hexdigest() == expected_provider_sha:
            provider_root = candidate
            break
    if provider_root is None:
        errors.append("jingzao_asset_provider_not_installed_or_hash_mismatch")
        return None
    handoff_errors, prompt = visual_asset_jingzao_handoff.validate(
        document,
        project_root=project_root,
        provider_root=provider_root,
        trusted_provider_roots=(provider_root,),
        allow_unsandboxed_test_replay=allow_unsandboxed_test_replay,
    )
    if handoff_errors:
        errors.append("jingzao_asset_handoff_validation_failed")
        return None
    return prompt


def _bound_visual_plan(
    packet: dict[str, Any],
    *,
    project_root: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    binding = packet.get("visual_plan")
    if not isinstance(binding, dict):
        errors.append("visual_plan_binding_missing")
        return None
    relative = binding.get("path")
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        errors.append("visual_plan_path_invalid")
        return None
    try:
        root = project_root.resolve(strict=True)
        candidate = root.joinpath(*relative.split("/"))
        data = read_relative_regular_file_once(
            root,
            relative,
            max_bytes=MAX_VISUAL_PLAN_BYTES,
            label="visual asset plan",
        )
        if binding.get("sha256") != hashlib.sha256(data).hexdigest():
            errors.append("visual_plan_hash_mismatch")
            return None
        plan = json.loads(data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RuntimeError):
        errors.append("visual_plan_file_invalid")
        return None
    plan_errors, _metrics = validate_plan(plan, base_dir=candidate.parent)
    if plan_errors:
        errors.append("visual_plan_invalid")
        return None
    plan["_bound_plan_dir"] = candidate.parent.as_posix()
    return plan


def _review_manifest_evidence_map(
    receipt: dict[str, Any],
    visual_plan: dict[str, Any],
    *,
    base_dir: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    relative = receipt.get("review_manifest_file")
    try:
        raw = read_relative_regular_file_once(
            base_dir,
            relative,
            max_bytes=8 * 1024 * 1024,
            label="dependency review manifest",
        )
        if hashlib.sha256(raw).hexdigest() != receipt.get("review_manifest_sha256"):
            raise ValueError("manifest hash mismatch")
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return {}, ["dependency_review_manifest_unreadable"]
    entries = manifest.get("assets") if isinstance(manifest, dict) else None
    if not isinstance(entries, list):
        return {}, ["dependency_review_manifest_assets_invalid"]
    plan_assets = {
        str(item.get("asset_id")): item
        for item in visual_plan.get("assets", [])
        if isinstance(item, dict)
    }
    evidence_map: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for entry in entries:
        asset_id = str(entry.get("asset_id")) if isinstance(entry, dict) else ""
        asset = plan_assets.get(asset_id)
        path = contained_file(asset.get("generated_file"), base_dir) if isinstance(asset, dict) else None
        evidence, _reason = inspect_raster(path) if path is not None else (None, "missing")
        if (
            not isinstance(asset, dict)
            or evidence is None
            or asset.get("status") not in {"generated_candidate", "user_locked", "reused_locked"}
            or asset.get("generated_sha256") != evidence["sha256"]
            or asset.get("generated_pixel_sha256") != evidence["pixel_sha256"]
            or validate_technical_receipt(
                asset.get("technical_receipt"),
                asset_id=asset_id,
                evidence=evidence,
                truth_locked_at=str(visual_plan.get("truth_locked_at")),
            )
            is not None
        ):
            errors.append(f"dependency_review_manifest_evidence_invalid:{asset_id}")
            continue
        evidence_map[asset_id] = evidence
    return evidence_map, errors


def validate_packet(
    packet: Any,
    *,
    repo_root: Path = ROOT,
    project_root: Path | None = None,
    execution_task_id: str | None = None,
    _trusted_jingzao_provider_roots: tuple[Path, ...] | None = None,
    _allow_unsandboxed_jingzao_replay_for_tests: bool = False,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(packet, dict):
        return ["packet_must_be_object"]
    if packet.get("contract_id") != CONTRACT_ID:
        errors.append("contract_id_invalid")
    role = packet.get("asset_role")
    project_root = project_root or repo_root
    visual_plan = _bound_visual_plan(packet, project_root=project_root, errors=errors)
    active_plan_asset: dict[str, Any] | None = None
    bound_plan_dir: Path | None = None
    if visual_plan is not None:
        bound_plan_dir = Path(str(visual_plan.pop("_bound_plan_dir")))
        active_plan_asset = next(
            (
                asset
                for asset in visual_plan.get("assets", [])
                if isinstance(asset, dict) and asset.get("asset_id") == packet.get("asset_id")
            ),
            None,
        )
        if active_plan_asset is None:
            errors.append(f"active_asset_missing_from_visual_plan:{packet.get('asset_id')}")
        elif active_plan_asset.get("role") != role:
            errors.append(f"active_asset_role_mismatch:{packet.get('asset_id')}")
        elif packet.get("active_asset_truth_sha256") != active_plan_asset.get("truth_sha256"):
            errors.append(f"active_asset_truth_mismatch:{packet.get('asset_id')}")
    expected = ROLE_STAGE_CONTRACTS.get(str(role))
    stage = packet.get("stage_contract")
    if expected is None:
        errors.append(f"asset_role_stage_contract_unknown:{role}")
    elif not isinstance(stage, dict):
        errors.append("stage_contract_missing")
    else:
        expected_stage, expected_reference = expected
        if stage.get("stage_id") != expected_stage:
            errors.append(f"stage_contract_id_mismatch:{role}")
        if stage.get("reference") != expected_reference:
            errors.append(f"stage_contract_reference_mismatch:{role}")
        reference_path = repo_root / expected_reference
        if not reference_path.is_file() or stage.get("sha256") != _file_sha256(reference_path):
            errors.append(f"stage_contract_not_read_back:{role}")

    authorization = packet.get("authorization")
    if not isinstance(authorization, dict):
        errors.append("authorization_missing")
    else:
        if packet.get("media_scope") == "pre_video_assets":
            if authorization.get("image_generation") is not True:
                errors.append("pre_video_assets_requires_image_authorization")
            if authorization.get("video_generation") is not False:
                errors.append("pre_video_assets_must_defer_video_generation")
        if authorization.get("source") != "validated_route_context":
            errors.append("authorization_source_not_route_context")

    dependencies = packet.get("dependencies")
    if not isinstance(dependencies, list) or len(dependencies) > MAX_DEPENDENCIES:
        errors.append("dependencies_invalid")
    else:
        visual_manifest_cache: dict[
            str,
            tuple[dict[str, Any], dict[str, dict[str, Any]], str | None],
        ] = {}
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                errors.append("dependency_invalid")
                continue
            asset_id = dependency.get("asset_id")
            status = dependency.get("status")
            if status not in APPROVED_DEPENDENCY_STATES:
                errors.append(f"dependency_not_approved:{asset_id}:{status}")
            review_sha = dependency.get("visual_qa_receipt_sha256")
            if status in APPROVED_DEPENDENCY_STATES and (
                not isinstance(review_sha, str)
                or len(review_sha) != 64
                or any(char not in "0123456789abcdef" for char in review_sha)
            ):
                errors.append(f"dependency_review_receipt_missing:{asset_id}")
        if role in DEPENDENT_ASSET_ROLES and not dependencies:
            errors.append(f"dependent_asset_requires_reviewed_parents:{role}")
        if active_plan_asset is not None:
            expected_dependency_ids = list(active_plan_asset.get("inherits_from", []))
            actual_dependency_ids = [
                dependency.get("asset_id")
                for dependency in dependencies
                if isinstance(dependency, dict)
            ]
            if actual_dependency_ids != expected_dependency_ids:
                errors.append(
                    f"dependency_ids_do_not_match_visual_plan:{packet.get('asset_id')}"
                )
            plan_assets = {
                str(asset.get("asset_id")): asset
                for asset in visual_plan.get("assets", [])
                if isinstance(asset, dict)
            } if visual_plan is not None else {}
            for dependency in dependencies:
                if not isinstance(dependency, dict):
                    continue
                dependency_id = str(dependency.get("asset_id"))
                planned_dependency = plan_assets.get(dependency_id)
                visual_receipt = (
                    planned_dependency.get("visual_qa_receipt")
                    if isinstance(planned_dependency, dict)
                    else None
                )
                plan_status = planned_dependency.get("status") if isinstance(planned_dependency, dict) else None
                evidence_ok = False
                if (
                    isinstance(planned_dependency, dict)
                    and bound_plan_dir is not None
                    and plan_status in {"generated_candidate", "user_locked", "reused_locked"}
                    and isinstance(visual_receipt, dict)
                ):
                    generated_path = contained_file(
                        planned_dependency.get("generated_file"),
                        bound_plan_dir,
                    )
                    evidence, _reason = (
                        inspect_raster(generated_path)
                        if generated_path is not None
                        else (None, "missing")
                    )
                    technical_problem = (
                        validate_technical_receipt(
                            planned_dependency.get("technical_receipt"),
                            asset_id=dependency_id,
                            evidence=evidence,
                            truth_locked_at=str(visual_plan.get("truth_locked_at")),
                        )
                        if evidence is not None
                        else "missing"
                    )
                    evidence_ok = (
                        evidence is not None
                        and planned_dependency.get("generated_sha256") == evidence["sha256"]
                        and planned_dependency.get("generated_pixel_sha256") == evidence["pixel_sha256"]
                        and planned_dependency.get("generated_perceptual_hash") == evidence["perceptual_hash"]
                        and technical_problem is None
                        and visual_receipt.get("asset_id") == dependency_id
                        and visual_receipt.get("file_sha256") == evidence["sha256"]
                        and visual_receipt.get("pixel_sha256") == evidence["pixel_sha256"]
                        and visual_receipt.get("truth_sha256") == planned_dependency.get("truth_sha256")
                        and visual_receipt.get("ruleset") == VISUAL_QA_RULESET
                        and visual_receipt.get("status") == "visual_qa_pass"
                        and visual_receipt.get("receipt_sha256") == receipt_sha256(visual_receipt)
                    )
                if not evidence_ok:
                    errors.append(f"dependency_plan_state_not_approved:{dependency_id}")
                    continue
                manifest_evidence, manifest_evidence_errors = _review_manifest_evidence_map(
                    visual_receipt,
                    visual_plan,
                    base_dir=bound_plan_dir,
                )
                if manifest_evidence_errors:
                    errors.extend(manifest_evidence_errors)
                    continue
                visual_problem = validate_visual_qa_receipt(
                    visual_receipt,
                    asset=planned_dependency,
                    evidence=evidence,
                    truth_locked_at=str(visual_plan.get("truth_locked_at")),
                    base_dir=bound_plan_dir,
                    payload=visual_plan,
                    evidence_by_asset=manifest_evidence,
                    manifest_cache=visual_manifest_cache,
                )
                if visual_problem:
                    errors.append(
                        f"dependency_visual_review_manifest_invalid:{dependency_id}:{visual_problem}"
                    )
                    continue
                _visual_authorization, visual_authorization_errors = (
                    load_visual_review_authorization(
                        planned_dependency,
                        base_dir=bound_plan_dir,
                        image_evidence=evidence,
                        expected_execution_task_id=execution_task_id,
                    )
                )
                if visual_authorization_errors:
                    errors.append(
                        f"dependency_visual_review_not_host_authorized:{dependency_id}"
                    )
                    continue
                if planned_dependency.get("role") == "character_identity_reference":
                    structure_receipt, structure_errors = load_character_master_receipt(
                        planned_dependency,
                        base_dir=bound_plan_dir,
                        image_evidence=evidence,
                    )
                    headless_review_errors: list[str] = []
                    if (
                        isinstance(structure_receipt, dict)
                        and planned_dependency.get("character_mode") == "headless_safe"
                        and structure_receipt.get("status") == "applied_unverified"
                    ):
                        _review, headless_review_errors = load_headless_review_authorization(
                            planned_dependency,
                            base_dir=bound_plan_dir,
                            image_evidence=evidence,
                        )
                    if (
                        structure_errors or headless_review_errors
                        or not isinstance(structure_receipt, dict)
                        or not (
                            structure_receipt.get("status") == "pass"
                            or (
                                planned_dependency.get("character_mode") == "headless_safe"
                                and structure_receipt.get("status") == "applied_unverified"
                                and not headless_review_errors
                            )
                        )
                    ):
                        errors.append(
                            f"dependency_character_master_structure_not_approved:{dependency_id}"
                        )
                        continue
                if dependency.get("visual_qa_receipt_sha256") != canonical_packet_sha256(visual_receipt):
                    errors.append(f"dependency_review_receipt_mismatch:{dependency_id}")

    execution = packet.get("execution")
    if not isinstance(execution, dict):
        errors.append("execution_contract_missing")
    elif role == "character_identity_reference" and (
        execution.get("mode") != "serial_review_gated"
        or execution.get("parallel_group") is not None
    ):
        errors.append("foundation_asset_requires_serial_review_gate")
    if role in DETERMINISTIC_ASSEMBLY_ROLES:
        errors.append("professional_storyboard_requires_deterministic_assembly")

    prompt = packet.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append("prompt_missing")
    elif len(prompt) > MAX_PROMPT_CHARS:
        errors.append("prompt_too_large")
    elif packet.get("prompt_sha256") != sha256_text(prompt):
        errors.append("prompt_sha256_mismatch")
    if (
        active_plan_asset is not None
        and isinstance(prompt, str)
        and role not in JINGZAO_PROMPT_ROLES
        and str(active_plan_asset.get("purpose", "")) not in prompt
    ):
        errors.append("active_asset_purpose_missing_from_prompt")
    authority = packet.get("prompt_authority")
    if active_plan_asset is None or not isinstance(authority, dict):
        errors.append("prompt_authority_contract_missing")
    else:
        purpose = str(active_plan_asset.get("purpose", ""))
        storyboard_binding = (
            packet.get("jingzao_handoff", {})
            if isinstance(packet.get("jingzao_handoff"), dict)
            else {}
        )
        asset_binding = (
            packet.get("jingzao_asset_handoff", {})
            if isinstance(packet.get("jingzao_asset_handoff"), dict)
            else {}
        )
        provider_binding = storyboard_binding or asset_binding
        expected_authority = build_prompt_authority(
            active_plan_asset,
            str(packet.get("prompt_sha256")),
            jingzao_handoff_sha256=(
                provider_binding.get("sha256")
            ),
            jingzao_provider_skill_sha256=(
                provider_binding.get("provider_skill_sha256")
            ),
            jingzao_prompt_manifest_sha256=(
                provider_binding.get("prompt_manifest_sha256")
                or provider_binding.get("compiled_prompt_manifest_sha256")
            ),
        )
        if authority != expected_authority:
            errors.append("prompt_authority_contract_mismatch")

    compile_route = (
        active_plan_asset.get("compile_route")
        if isinstance(active_plan_asset, dict)
        else None
    )
    if compile_route == "direct_concise" and packet.get("jingzao_asset_handoff") is not None:
        errors.append("asset_compile_route_handoff_mismatch")
    formal_asset_jingzao_prompt: str | None = None
    uses_formal_asset_jingzao = (
        role in JINGZAO_FORMAL_ASSET_ROLES
        and compile_route == "selected_skill_handoff"
    )
    if uses_formal_asset_jingzao and active_plan_asset is not None:
        formal_asset_jingzao_prompt = _verified_visual_asset_jingzao_prompt(
            packet,
            active_plan_asset,
            project_root=project_root,
            trusted_provider_roots=_trusted_jingzao_provider_roots,
            allow_unsandboxed_test_replay=_allow_unsandboxed_jingzao_replay_for_tests,
            errors=errors,
        )

    if role == "character_identity_reference":
        master = packet.get("character_master")
        mode = master.get("mode") if isinstance(master, dict) else None
        canonical_master = (
            isinstance(master, dict)
            and mode in {"headed_master", "headed_state", "headless_safe"}
            and master.get("layout") == "single_horizontal_row"
            and master.get("portrait_position") == "far_left"
            and master.get("full_body_views")
            == ["front", "left_profile", "right_profile", "back"]
            and master.get("min_subject_height_ratio") == 0.75
            and master.get("body_scale") == "equal"
            and master.get("ground_line") == "shared"
            and bool(master.get("identity_facts"))
            and bool(master.get("wardrobe_facts"))
            and bool(master.get("wardrobe_materials"))
            and isinstance(master.get("side_specific_details"), list)
            and (
                mode == "headed_master"
                or (
                    isinstance(master.get("approved_source_master_sha256"), str)
                    and len(master["approved_source_master_sha256"]) == 64
                    and isinstance(master.get("derived_from_asset_id"), str)
                    and bool(master["derived_from_asset_id"])
                )
            )
            and (mode != "headed_state" or bool(master.get("state_facts")))
            and (mode != "headless_safe" or master.get("body_mode") == "fully_headless")
        )
        prompt_markers = [
            "three-quarter face close-up",
            "far left",
            "single horizontal row",
            "Panel 1 front",
            "Panel 2 left profile",
            "Panel 3 right profile",
            "Panel 4 back",
            "at least 75% of the canvas height",
            "identical scale",
            "shared ground line",
            "no 2x2 grid",
        ]
        if mode == "headless_safe":
            prompt_markers.extend(("fully headless", "only readable face", "rear collar"))
        elif mode == "headed_state":
            prompt_markers.extend(("headed character state derivative", "Change only the declared visible state"))
        else:
            prompt_markers.append("full-body headed views")
        if not canonical_master or not isinstance(prompt, str) or (
            not uses_formal_asset_jingzao
            and any(marker.lower() not in prompt.lower() for marker in prompt_markers)
        ):
            errors.append("character_master_prompt_contract_missing")
        if canonical_master and active_plan_asset is not None and visual_plan is not None:
            errors.extend(
                character_plan_binding_errors(master, active_plan_asset, visual_plan)
            )
        if canonical_master and isinstance(prompt, str):
            lowered_prompt = prompt.lower()
            bound_details = [
                *master.get("wardrobe_materials", []),
                *master.get("side_specific_details", []),
            ]
            if any(
                str(detail).lower() not in lowered_prompt
                for detail in bound_details
            ):
                errors.append("character_master_material_or_side_detail_missing")
            identity_and_wardrobe = [
                *master.get("identity_facts", []),
                *master.get("wardrobe_facts", []),
            ]
            if any(
                str(detail).lower() not in lowered_prompt
                for detail in identity_and_wardrobe
            ):
                errors.append("character_master_identity_or_wardrobe_fact_missing")
            authoritative_purpose = str(
                (active_plan_asset or {}).get("purpose", "")
            ).lower()
            if any(
                str(detail).lower() not in authoritative_purpose
                for detail in [
                    *identity_and_wardrobe,
                    *master.get("wardrobe_materials", []),
                    *master.get("side_specific_details", []),
                ]
            ):
                errors.append("character_master_facts_not_bound_to_active_truth")
        if canonical_master and active_plan_asset is not None and isinstance(prompt, str):
            expected_prompt = (
                formal_asset_jingzao_prompt
                if uses_formal_asset_jingzao
                else build_character_prompt_from_contract(
                    str(active_plan_asset.get("purpose", "")),
                    master,
                )
            )
            if prompt != expected_prompt:
                errors.append("prompt_not_deterministically_compiled")
    elif formal_asset_jingzao_prompt is not None and isinstance(prompt, str):
        if prompt != formal_asset_jingzao_prompt:
            errors.append("prompt_not_exact_jingzao_asset_manifest_output")
    elif (
        role in JINGZAO_PROMPT_ROLES
        and active_plan_asset is not None
        and visual_plan is not None
        and isinstance(prompt, str)
    ):
        expected_prompt = _verified_jingzao_prompt(
            packet,
            active_plan_asset,
            visual_plan,
            project_root=project_root,
            trusted_provider_roots=_trusted_jingzao_provider_roots,
            errors=errors,
        )
        if expected_prompt is not None and prompt != expected_prompt:
            errors.append("prompt_not_exact_jingzao_manifest_output")
    elif (
        role not in DETERMINISTIC_ASSEMBLY_ROLES
        and active_plan_asset is not None
        and visual_plan is not None
        and isinstance(prompt, str)
    ):
        try:
            expected_prompt = build_role_prompt(active_plan_asset, visual_plan)
        except ValueError:
            errors.append("deterministic_role_prompt_unavailable")
        else:
            if prompt != expected_prompt:
                errors.append("prompt_not_deterministically_compiled")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one DIRcreative asset execution packet before a media call.")
    parser.add_argument("packet", type=Path)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--execution-task-id")
    args = parser.parse_args()
    try:
        if args.packet.stat().st_size > MAX_PACKET_BYTES:
            raise ValueError("packet_too_large")
        packet_bytes = read_relative_regular_file_once(
            args.packet.parent.resolve(strict=True),
            args.packet.name,
            max_bytes=MAX_PACKET_BYTES,
            label="asset execution packet",
        )
        packet = json.loads(packet_bytes.decode("utf-8"))
        errors = validate_packet(
            packet,
            repo_root=args.repo_root.resolve(),
            project_root=args.project_root.resolve(),
            execution_task_id=args.execution_task_id,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        errors = [f"packet_unreadable:{type(exc).__name__}"]
    print(
        json.dumps(
            {
                "preflight_status": "ready" if not errors else "blocked",
                "authorization_authority": "none",
                "packet_sha256": canonical_packet_sha256(packet) if not errors else None,
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
