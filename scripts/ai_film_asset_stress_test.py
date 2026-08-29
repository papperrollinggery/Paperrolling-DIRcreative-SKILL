#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from dircreative_review_trust import DEFAULT_REGISTRY_PATH, resolve_review_key, sensitive_paths
from dircreative_validation_common import (
    add_error,
    apply_mutations,
    canonical_sha256,
    load_json,
    safe_relative_path,
    schema_errors as validate_schema,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATHS = {
    "ai_film_asset_stress_test_v1": ROOT
    / "docs/film-preproduction/schemas/ai-film-asset-stress-test.schema.json",
    "ai_film_asset_stress_test_v2": ROOT
    / "docs/film-preproduction/schemas/ai-film-asset-stress-test-v2.schema.json",
    "ai_film_asset_stress_test_v3": ROOT
    / "docs/film-preproduction/schemas/ai-film-asset-stress-test-v3.schema.json",
}
VALID_PATH = ROOT / "tests/fixtures/asset-stress-test/valid-report.json"
VALID_V1_PATH = ROOT / "tests/fixtures/asset-stress-test/valid-report-v1.json"
VALID_V3_PATH = ROOT / "tests/fixtures/asset-stress-test/valid-report-v3-headed.json"
CASES_PATH = ROOT / "tests/fixtures/asset-stress-test/cases.json"
V3_CASES_PATH = ROOT / "tests/fixtures/asset-stress-test/v3-cases.json"
COMPLETION_VERDICTS = {"certified", "conditional"}
PNG_FIXTURE_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def review_subject_sha256(document: dict[str, Any]) -> str:
    subject = copy.deepcopy(document)
    subject.get("verdict", {}).get("reviewer", {}).pop("receipt_sha256", None)
    return canonical_sha256(subject)


def schema_errors(document: dict[str, Any]) -> list[str]:
    schema_path = SCHEMA_PATHS.get(str(document.get("contract_id")))
    if schema_path is None:
        return ["schema_error: unsupported asset stress-test contract_id"]
    return validate_schema(document, schema_path)


def contained_file(root: Path, relative: Any) -> Path | None:
    if not safe_relative_path(relative):
        return None
    try:
        resolved_root = root.resolve(strict=True)
        candidate = (resolved_root / str(relative)).resolve(strict=True)
        candidate.relative_to(resolved_root)
    except (FileNotFoundError, RuntimeError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def verify_file(
    root: Path,
    relative: Any,
    expected_sha: Any,
    label: str,
    errors: list[str],
    *,
    require_media: bool = False,
) -> None:
    path = contained_file(root, relative)
    if path is None:
        add_error(errors, "evidence_file_missing", f"{label}:{relative}")
        return
    content = path.read_bytes()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha:
        add_error(errors, "evidence_hash_mismatch", f"{label}:{relative}")
    if require_media and not (
        content.startswith(b"\x89PNG\r\n\x1a\n")
        or content.startswith(b"\xff\xd8\xff")
        or (content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    ):
        add_error(errors, "evidence_media_invalid", f"{label}:{relative}")


def verify_review_signature(
    signature_path: Path | None,
    receipt_path: Path,
    *,
    authority_id: Any,
    reviewer_actor_id: Any,
    reviewer_source: Any,
    trust_registry_path: Path,
    artifact_root: Path | None,
    errors: list[str],
) -> None:
    if signature_path is None:
        add_error(errors, "trusted_review_signature_required", "detached signature")
        return
    public_key, openssl, authority_policy, trust_errors = resolve_review_key(
        authority_id,
        registry_path=trust_registry_path,
        artifact_root=artifact_root,
    )
    errors.extend(trust_errors)
    if public_key is None or openssl is None or authority_policy is None:
        return
    if (
        authority_policy.get("authority_kind") not in {"asset_reviewer", "human_reviewer"}
        or authority_policy.get("actor_id") != reviewer_actor_id
        or "asset_stress_review" not in authority_policy.get("allowed_purposes", [])
        or reviewer_source not in authority_policy.get("allowed_sources", [])
    ):
        add_error(errors, "review_authority_scope_invalid", str(authority_id))
        return
    try:
        signature = signature_path.resolve(strict=True)
        if artifact_root is not None:
            signature.relative_to(artifact_root.resolve(strict=True))
    except ValueError:
        pass
    except (FileNotFoundError, RuntimeError):
        add_error(errors, "trusted_review_material_missing", str(signature_path))
        return
    else:
        add_error(errors, "trusted_review_material_not_detached", str(signature_path))
        return
    result = subprocess.run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-verify",
            str(public_key),
            "-signature",
            str(signature),
            str(receipt_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        add_error(errors, "review_signature_invalid", str(receipt_path))


V3_FULL_BODY_VIEWS = {"front", "left_profile", "right_profile", "back"}
V3_HEADED_VIEW_ROLES = {
    "portrait_three_quarter",
    "full_body_front",
    "full_body_left_profile",
    "full_body_right_profile",
    "full_body_back",
}
V3_HEADLESS_VIEW_ROLES = {
    "portrait_three_quarter",
    "headless_full_body_front",
    "headless_full_body_left_profile",
    "headless_full_body_right_profile",
    "headless_full_body_back",
}
V3_EXACT_GRAPHIC_KINDS = {"logo", "emblem", "text"}
V3_GENERATION_INPUT_KINDS = {
    "character_full_generation_input",
    "character_identity_generation_input",
    "character_wardrobe_body_generation_input",
}
V3_CHARACTER_SIGNAL_KINDS = V3_GENERATION_INPUT_KINDS | {
    "character_master_sheet",
    "character_state_sheet",
    "character_headless_sheet",
    "character_detail_sheet",
}
V3_ALLOWED_HEADED_VIEW_ROLES = V3_HEADED_VIEW_ROLES | {
    "portrait_front",
    "portrait_left_profile",
    "portrait_right_profile",
}


def validate_v3_character_sheet(
    asset: dict[str, Any],
    asset_references: list[dict[str, Any]],
    errors: list[str],
) -> None:
    asset_id = str(asset.get("asset_id"))
    reference_map = {
        str(reference.get("reference_id")): reference for reference in asset_references
    }
    contract = asset.get("character_sheet_contract")
    if not isinstance(contract, dict):
        add_error(errors, "character_sheet_contract_required", asset_id)
        return

    mode = contract.get("mode")
    generation_input_ids = [
        str(reference_id)
        for reference_id in contract.get("generation_input_reference_ids", [])
    ]
    generation_input_references = [
        reference
        for reference in asset_references
        if reference.get("source_kind") in V3_GENERATION_INPUT_KINDS
    ]
    if any(
        reference.get("role") != "planning_only"
        for reference in generation_input_references
    ):
        add_error(errors, "character_generation_input_role_invalid", asset_id)
    if any(
        reference.get("rights_status") != "verified"
        for reference in generation_input_references
    ):
        add_error(errors, "character_generation_input_rights_invalid", asset_id)

    full_body_view_order = contract.get("full_body_views", [])
    full_body_views = set(full_body_view_order)
    if full_body_views != V3_FULL_BODY_VIEWS:
        add_error(errors, "character_sheet_full_body_views_invalid", asset_id)
    if (
        len(full_body_view_order) != 4
        or full_body_view_order[0] != "front"
        or full_body_view_order[-1] != "back"
        or set(full_body_view_order[1:3]) != {"left_profile", "right_profile"}
    ):
        add_error(errors, "character_sheet_view_order_invalid", asset_id)
    if "three_quarter" not in set(contract.get("portrait_views", [])):
        add_error(errors, "character_sheet_three_quarter_portrait_required", asset_id)
    if contract.get("portrait_framing") != "face_close_up":
        add_error(errors, "character_sheet_face_close_up_required", asset_id)
    if contract.get("portrait_panel_priority") != "dominant":
        add_error(errors, "character_sheet_dominant_portrait_required", asset_id)

    source_master_id = str(contract.get("source_master_reference_id"))
    active_reference_id = str(contract.get("active_reference_id"))
    source_master = reference_map.get(source_master_id)
    active_reference = reference_map.get(active_reference_id)
    master_references = [
        reference
        for reference in asset_references
        if reference.get("source_kind") == "character_master_sheet"
    ]
    if len(master_references) != 1 or source_master not in master_references:
        add_error(errors, "character_master_sheet_required", asset_id)
        source_master = None
    if active_reference is None:
        add_error(errors, "character_sheet_active_reference_unresolved", asset_id)
    elif active_reference.get("sha256") != asset.get("canonical_sha256"):
        add_error(errors, "character_sheet_canonical_hash_mismatch", asset_id)
    if active_reference is not None and active_reference.get("rights_status") != "verified":
        add_error(errors, "character_active_reference_rights_invalid", asset_id)

    if source_master is not None:
        if source_master.get("rights_status") != "verified":
            add_error(errors, "character_master_rights_invalid", asset_id)
        source_master_views = set(source_master.get("view_roles", []))
        missing_master_views = V3_HEADED_VIEW_ROLES - source_master_views
        if missing_master_views:
            add_error(
                errors,
                "character_master_sheet_views_missing",
                f"{asset_id}:{','.join(sorted(missing_master_views))}",
            )
        if not source_master_views.issubset(V3_ALLOWED_HEADED_VIEW_ROLES):
            add_error(errors, "character_master_sheet_view_roles_invalid", asset_id)

    body_head_policy = contract.get("body_head_policy")
    if mode == "headed_master":
        generation_reference_ids = {
            str(reference.get("reference_id"))
            for reference in generation_input_references
        }
        if set(generation_input_ids) != generation_reference_ids:
            add_error(errors, "character_generation_input_set_mismatch", asset_id)
        generation_kinds = {
            str(reference.get("source_kind"))
            for reference in generation_input_references
        }
        full_input_mode = (
            len(generation_input_references) == 1
            and generation_kinds == {"character_full_generation_input"}
        )
        paired_input_mode = (
            len(generation_input_references) == 2
            and generation_kinds
            == {
                "character_identity_generation_input",
                "character_wardrobe_body_generation_input",
            }
        )
        if not (full_input_mode or paired_input_mode):
            add_error(errors, "character_generation_input_mode_invalid", asset_id)
        if source_master_id in generation_input_ids:
            add_error(errors, "headed_master_cannot_self_generate", asset_id)
        if contract.get("approved_source_master_sha256") is not None:
            add_error(errors, "headed_master_approval_hash_forbidden", asset_id)
        if contract.get("generation_method") != "unified_generation":
            add_error(errors, "headed_master_generation_method_invalid", asset_id)
        if body_head_policy != "headed":
            add_error(errors, "headed_master_policy_mismatch", asset_id)
        if active_reference_id != source_master_id:
            add_error(errors, "headed_master_must_be_active", asset_id)
        if source_master is not None and source_master.get("role") != "canonical":
            add_error(errors, "headed_master_not_canonical", asset_id)
        if any(
            reference.get("source_kind") == "character_headless_sheet"
            for reference in asset_references
        ):
            add_error(errors, "headed_asset_contains_competing_headless_sheet", asset_id)
    elif mode == "headed_state":
        if generation_input_ids != [source_master_id]:
            add_error(errors, "headed_state_generation_inputs_invalid", asset_id)
        if generation_input_references:
            add_error(errors, "headed_state_historical_generation_inputs_forbidden", asset_id)
        if contract.get("generation_method") != "derived_generation":
            add_error(errors, "headed_state_generation_method_invalid", asset_id)
        if body_head_policy != "headed":
            add_error(errors, "headed_state_policy_mismatch", asset_id)
        if source_master is not None and source_master.get("role") != "supporting":
            add_error(errors, "headed_state_source_master_must_be_supporting", asset_id)
        state_references = [
            reference
            for reference in asset_references
            if reference.get("source_kind") == "character_state_sheet"
        ]
        if len(state_references) != 1:
            add_error(errors, "headed_state_sheet_count_invalid", asset_id)
        if (
            active_reference is None
            or active_reference.get("source_kind") != "character_state_sheet"
            or active_reference.get("role") != "canonical"
            or active_reference.get("derived_from_reference_id") != source_master_id
        ):
            add_error(errors, "headed_state_derivation_invalid", asset_id)
        elif not V3_HEADED_VIEW_ROLES.issubset(
            set(active_reference.get("view_roles", []))
        ):
            add_error(errors, "headed_state_sheet_views_missing", asset_id)
        if (
            source_master is not None
            and contract.get("approved_source_master_sha256")
            != source_master.get("sha256")
        ):
            add_error(errors, "headed_state_approved_master_hash_mismatch", asset_id)
        if any(
            reference.get("source_kind") == "character_headless_sheet"
            for reference in asset_references
        ):
            add_error(errors, "headed_state_contains_competing_headless_sheet", asset_id)
    elif mode == "headless_safe":
        if generation_input_ids != [source_master_id]:
            add_error(errors, "headless_generation_inputs_invalid", asset_id)
        if generation_input_references:
            add_error(errors, "headless_historical_generation_inputs_forbidden", asset_id)
        if contract.get("generation_method") != "derived_generation":
            add_error(errors, "headless_generation_method_invalid", asset_id)
        headless_references = [
            reference
            for reference in asset_references
            if reference.get("source_kind") == "character_headless_sheet"
        ]
        if len(headless_references) != 1:
            add_error(errors, "headless_sheet_count_invalid", asset_id)
        if body_head_policy != "headless":
            add_error(errors, "headless_safe_policy_mismatch", asset_id)
        if source_master is not None and source_master.get("role") != "supporting":
            add_error(errors, "headless_source_master_must_be_supporting", asset_id)
        if (
            source_master is not None
            and contract.get("approved_source_master_sha256")
            != source_master.get("sha256")
        ):
            add_error(errors, "headless_approved_master_hash_mismatch", asset_id)
        if (
            active_reference is None
            or active_reference.get("source_kind") != "character_headless_sheet"
            or active_reference.get("role") != "canonical"
        ):
            add_error(errors, "headless_sheet_must_be_active_canonical", asset_id)
        elif active_reference.get("derived_from_reference_id") != source_master_id:
            add_error(errors, "headless_sheet_derivation_invalid", asset_id)
        if active_reference is not None:
            active_headless_views = set(active_reference.get("view_roles", []))
            if active_headless_views != V3_HEADLESS_VIEW_ROLES:
                missing_views = V3_HEADLESS_VIEW_ROLES - active_headless_views
                extra_views = active_headless_views - V3_HEADLESS_VIEW_ROLES
                add_error(
                    errors,
                    "headless_sheet_view_roles_invalid",
                    f"{asset_id}:missing={','.join(sorted(missing_views))};extra={','.join(sorted(extra_views))}",
                )

    detail_requirements = [
        requirement
        for requirement in contract.get("detail_requirements", [])
        if isinstance(requirement, dict)
    ]
    detail_ids = [str(requirement.get("detail_id")) for requirement in detail_requirements]
    if len(detail_ids) != len(set(detail_ids)):
        add_error(errors, "character_detail_id_duplicate", asset_id)
    detail_reference_id = contract.get("detail_reference_id")
    detail_references = [
        reference
        for reference in asset_references
        if reference.get("source_kind") == "character_detail_sheet"
    ]
    detail_reference = (
        reference_map.get(str(detail_reference_id))
        if detail_reference_id is not None
        else None
    )
    if detail_requirements and (detail_reference is None or len(detail_references) != 1):
        add_error(errors, "character_detail_sheet_required", asset_id)
    if not detail_requirements and detail_references:
        add_error(errors, "character_detail_sheet_without_requirements", asset_id)
    detail_derivation_source_id = (
        active_reference_id if mode == "headed_state" else source_master_id
    )
    if detail_reference is not None:
        if (
            detail_reference.get("source_kind") != "character_detail_sheet"
            or detail_reference.get("role") != "supporting"
            or detail_reference.get("derived_from_reference_id")
            != detail_derivation_source_id
        ):
            add_error(errors, "character_detail_sheet_binding_invalid", asset_id)
        if set(detail_reference.get("view_roles", [])) != {"detail_close_up"}:
            add_error(errors, "character_detail_sheet_view_roles_invalid", asset_id)
        missing_details = set(detail_ids) - set(
            detail_reference.get("covered_detail_ids", [])
        )
        if missing_details:
            add_error(
                errors,
                "character_detail_callout_missing",
                f"{asset_id}:{','.join(sorted(missing_details))}",
            )

    for requirement in detail_requirements:
        detail_id = str(requirement.get("detail_id"))
        source_policy = requirement.get("source_policy")
        source_reference_id = requirement.get("source_reference_id")
        exact_graphic_required = requirement.get("detail_kind") in V3_EXACT_GRAPHIC_KINDS
        if exact_graphic_required and source_policy != "exact_graphic":
            add_error(errors, "exact_graphic_source_required", f"{asset_id}:{detail_id}")
            continue
        if source_policy == "exact_graphic":
            source_reference = (
                reference_map.get(str(source_reference_id))
                if source_reference_id is not None
                else None
            )
            if (
                source_reference is None
                or source_reference.get("source_kind") != "exact_graphic_reference"
                or source_reference.get("rights_status") != "verified"
            ):
                add_error(
                    errors,
                    "exact_graphic_reference_invalid",
                    f"{asset_id}:{detail_id}",
                )
        elif source_reference_id is not None:
            add_error(
                errors,
                "visual_detail_source_reference_forbidden",
                f"{asset_id}:{detail_id}",
            )

    required_case_kinds = set(asset.get("required_case_kinds", []))
    sheet_cases = {
        "character_sheet_views",
        "character_sheet_readable_scale",
        "character_sheet_body_consistency",
    }
    if not sheet_cases.issubset(required_case_kinds):
        add_error(errors, "character_sheet_required_case_missing", asset_id)
    if detail_requirements and "character_sheet_detail_callouts" not in required_case_kinds:
        add_error(errors, "character_detail_required_case_missing", asset_id)
    if mode == "headless_safe" and not {
        "headless_wardrobe",
        "headless_sheet_single_face",
    }.issubset(required_case_kinds):
        add_error(errors, "headless_sheet_required_case_missing", asset_id)


def semantic_errors(
    document: dict[str, Any],
    *,
    artifact_root: Path | None,
    review_receipt_path: Path | None,
    review_signature_path: Path | None,
    trust_registry_path: Path,
) -> list[str]:
    errors: list[str] = []
    contract_id = document.get("contract_id")
    strict_character_roles = contract_id == "ai_film_asset_stress_test_v2"
    unified_character_sheets = contract_id == "ai_film_asset_stress_test_v3"
    assets = [item for item in document.get("assets", []) if isinstance(item, dict)]
    asset_ids = [str(item.get("asset_id")) for item in assets]
    if len(asset_ids) != len(set(asset_ids)):
        add_error(errors, "asset_id_duplicate", str(asset_ids))
    asset_map = {str(item.get("asset_id")): item for item in assets}
    if canonical_sha256(assets) != document.get("input_spec_sha256"):
        add_error(errors, "input_spec_hash_mismatch", str(document.get("stress_test_id")))
    references: list[dict[str, Any]] = []
    for asset in assets:
        descriptor = str(asset.get("descriptor_text", ""))
        if hashlib.sha256(descriptor.encode("utf-8")).hexdigest() != asset.get("descriptor_sha256"):
            add_error(errors, "descriptor_hash_mismatch", str(asset.get("asset_id")))
        asset_references = [
            item for item in asset.get("references", []) if isinstance(item, dict)
        ]
        references.extend(asset_references)
        face_references = [
            item
            for item in asset_references
            if item.get("source_kind") == "face_identity_reference"
        ]
        wardrobe_references = [
            item
            for item in asset_references
            if item.get("source_kind") == "headless_wardrobe_reference"
        ]
        legacy_identity_references = [
            item
            for item in asset_references
            if item.get("source_kind") == "identity_reference"
        ]
        required_case_kinds = set(asset.get("required_case_kinds", []))
        v3_sheet_kinds = V3_CHARACTER_SIGNAL_KINDS
        v3_character_signal = isinstance(
            asset.get("character_sheet_contract"), dict
        ) or any(
            reference.get("source_kind") in v3_sheet_kinds
            for reference in asset_references
        )
        v3_character_state = asset.get("asset_kind") == "state" and (
            v3_character_signal
        )
        if (
            unified_character_sheets
            and v3_character_signal
            and asset.get("asset_kind") not in {"character", "state"}
        ):
            add_error(errors, "character_sheet_asset_kind_invalid", str(asset.get("asset_id")))
        if unified_character_sheets and (
            asset.get("asset_kind") == "character" or v3_character_state
        ):
            validate_v3_character_sheet(asset, asset_references, errors)
        if strict_character_roles:
            asset_kind = asset.get("asset_kind")
            human_state = asset_kind == "state" and bool(
                face_references
                or wardrobe_references
                or legacy_identity_references
                or required_case_kinds & {"face_close_up", "headless_wardrobe"}
            )
            strict_human_asset = asset_kind == "character" or human_state
            if len(face_references) > 1:
                add_error(errors, "multiple_face_identity_sources", str(asset.get("asset_id")))
            if face_references and legacy_identity_references:
                add_error(
                    errors,
                    "ambiguous_identity_reference_forbidden",
                    str(asset.get("asset_id")),
                )
            if any(reference.get("role") != "canonical" for reference in face_references):
                add_error(
                    errors,
                    "face_identity_reference_not_canonical",
                    str(asset.get("asset_id")),
                )
            if strict_human_asset:
                if legacy_identity_references:
                    add_error(
                        errors,
                        "legacy_identity_reference_forbidden",
                        str(asset.get("asset_id")),
                    )
                if len(face_references) != 1:
                    add_error(errors, "face_identity_reference_required", str(asset.get("asset_id")))
                if not wardrobe_references:
                    add_error(
                        errors,
                        "headless_wardrobe_reference_required",
                        str(asset.get("asset_id")),
                    )
                for case_kind in ("face_close_up", "headless_wardrobe"):
                    if case_kind not in required_case_kinds:
                        add_error(
                            errors,
                            "character_required_case_missing",
                            f"{asset.get('asset_id')}:{case_kind}",
                        )
            if asset_kind == "wardrobe":
                if face_references:
                    add_error(
                        errors,
                        "wardrobe_face_reference_forbidden",
                        str(asset.get("asset_id")),
                    )
                if legacy_identity_references:
                    add_error(
                        errors,
                        "wardrobe_identity_reference_forbidden",
                        str(asset.get("asset_id")),
                    )
                if not wardrobe_references:
                    add_error(
                        errors,
                        "headless_wardrobe_reference_required",
                        str(asset.get("asset_id")),
                    )
    if unified_character_sheets:
        state_family_master_hashes: dict[str, str] = {}
        for asset in assets:
            contract = asset.get("character_sheet_contract")
            if not isinstance(contract, dict):
                continue
            reference_map = {
                str(reference.get("reference_id")): reference
                for reference in asset.get("references", [])
                if isinstance(reference, dict)
            }
            source_master = reference_map.get(
                str(contract.get("source_master_reference_id"))
            )
            if source_master is None:
                continue
            state_family = str(asset.get("state_family"))
            master_hash = str(source_master.get("sha256"))
            prior_hash = state_family_master_hashes.get(state_family)
            if prior_hash is not None and prior_hash != master_hash:
                add_error(errors, "state_family_master_sheet_drift", state_family)
            state_family_master_hashes[state_family] = master_hash
    reference_ids = [str(item.get("reference_id")) for item in references]
    if len(reference_ids) != len(set(reference_ids)):
        add_error(errors, "reference_id_duplicate", str(reference_ids))
    reference_roles_by_path: dict[str, tuple[Any, Any]] = {}
    reference_roles_by_hash: dict[str, tuple[Any, Any]] = {}
    for reference in references:
        role = (reference.get("source_kind"), reference.get("role"))
        for identity, role_map in (
            (str(reference.get("relative_path")), reference_roles_by_path),
            (str(reference.get("sha256")), reference_roles_by_hash),
        ):
            prior_role = role_map.get(identity)
            if prior_role is not None and prior_role != role:
                add_error(errors, "reference_alias_role_conflict", str(reference.get("reference_id")))
            role_map[identity] = role
        if reference.get("source_kind") == "planning_only" and reference.get("role") != "planning_only":
            add_error(errors, "planning_reference_promoted", str(reference.get("reference_id")))

    cases = [item for item in document.get("test_cases", []) if isinstance(item, dict)]
    case_ids = [str(item.get("test_case_id")) for item in cases]
    if len(case_ids) != len(set(case_ids)):
        add_error(errors, "test_case_id_duplicate", str(case_ids))
    evidence_id_owners: dict[str, str] = {}
    evidence_hash_owners: dict[str, str] = {}
    for item in cases:
        case_id = str(item.get("test_case_id"))
        for evidence in item.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            evidence_id = str(evidence.get("evidence_id"))
            if evidence_id in evidence_id_owners:
                add_error(
                    errors,
                    "evidence_id_duplicate",
                    f"{evidence_id_owners[evidence_id]}->{case_id}:{evidence_id}",
                )
            evidence_id_owners[evidence_id] = case_id
            evidence_hash = evidence.get("sha256")
            if isinstance(evidence_hash, str):
                prior_case = evidence_hash_owners.get(evidence_hash)
                if prior_case is not None and prior_case != case_id:
                    add_error(errors, "evidence_hash_reused", f"{prior_case}->{case_id}")
                evidence_hash_owners[evidence_hash] = case_id
    case_kinds = {str(item.get("case_kind")) for item in cases}
    matrix = document.get("matrix_config", {})
    required_kinds = set(matrix.get("required_case_kinds", []))
    if not required_kinds.issubset(case_kinds) or len(cases) < int(matrix.get("minimum_case_count", 0)):
        add_error(errors, "matrix_case_coverage_missing", ",".join(sorted(required_kinds - case_kinds)))
    for item in cases:
        asset = asset_map.get(str(item.get("asset_id")))
        if asset is None:
            add_error(errors, "test_case_asset_unresolved", str(item.get("test_case_id")))
        elif item.get("state_family") != asset.get("state_family"):
            add_error(errors, "test_case_state_family_mismatch", str(item.get("test_case_id")))
        elif strict_character_roles and item.get("case_kind") == "face_close_up" and asset.get("asset_kind") not in {
            "character",
            "state",
        }:
            add_error(errors, "face_case_asset_kind_invalid", str(item.get("test_case_id")))
        elif strict_character_roles and item.get("case_kind") == "headless_wardrobe" and asset.get("asset_kind") not in {
            "character",
            "wardrobe",
            "state",
        }:
            add_error(
                errors,
                "headless_wardrobe_case_asset_kind_invalid",
                str(item.get("test_case_id")),
            )
        elif unified_character_sheets and item.get("case_kind") in {
            "character_sheet_views",
            "character_sheet_readable_scale",
            "character_sheet_body_consistency",
            "character_sheet_detail_callouts",
            "headless_sheet_single_face",
        } and asset.get("asset_kind") not in {"character", "state"}:
            add_error(
                errors,
                "character_sheet_case_asset_kind_invalid",
                str(item.get("test_case_id")),
            )
        if strict_character_roles and item.get("case_kind") == "headless_wardrobe":
            invariants = " ".join(str(value).casefold() for value in item.get("expected_invariants", []))
            if "headless" not in invariants or "face" not in invariants:
                add_error(
                    errors,
                    "headless_wardrobe_invariant_missing",
                    str(item.get("test_case_id")),
                )
        if unified_character_sheets and item.get("case_kind") == "headless_sheet_single_face":
            invariants = " ".join(
                str(value).casefold() for value in item.get("expected_invariants", [])
            )
            if "one readable face" not in invariants or "headless" not in invariants:
                add_error(
                    errors,
                    "headless_sheet_single_face_invariant_missing",
                    str(item.get("test_case_id")),
                )
        if unified_character_sheets and item.get("case_kind") == "headless_wardrobe":
            invariants = " ".join(
                str(value).casefold() for value in item.get("expected_invariants", [])
            )
            if not all(term in invariants for term in ("headless", "wrists", "hands")):
                add_error(
                    errors,
                    "headless_wardrobe_anatomy_invariant_missing",
                    str(item.get("test_case_id")),
                )
            if "rear collar" not in invariants or "back neckline" not in invariants:
                add_error(
                    errors,
                    "headless_wardrobe_collar_invariant_missing",
                    str(item.get("test_case_id")),
                )
        if item.get("status") == "pass" and (
            item.get("severity") != "none"
            or bool(item.get("observed_deviations"))
            or bool(item.get("blocked_shot_scope"))
            or not set(item.get("shot_scope", [])).issubset(set(item.get("allowed_shot_scope", [])))
        ):
            add_error(errors, "test_case_result_inconsistent", str(item.get("test_case_id")))
        if item.get("status") != "pass" and item.get("allowed_shot_scope"):
            add_error(errors, "test_case_result_inconsistent", str(item.get("test_case_id")))
    for asset_id, asset in asset_map.items():
        asset_cases = [item for item in cases if item.get("asset_id") == asset_id]
        asset_case_kinds = {
            str(item.get("case_kind")) for item in asset_cases if item.get("status") == "pass"
        }
        asset_required = set(asset.get("required_case_kinds", []))
        if asset.get("intended_lighting"):
            asset_required.add("target_lighting")
        if "group" in asset.get("intended_shot_classes", []):
            asset_required.add("group_composition")
        if not asset_required.issubset(asset_case_kinds):
            add_error(errors, "asset_matrix_coverage_missing", asset_id)
        if "group" in asset.get("intended_shot_classes", []) and "group_composition" not in asset_case_kinds:
            add_error(errors, "group_composition_coverage_missing", asset_id)
        tested_combinations = {
            combination_id
            for item in asset_cases
            if item.get("status") == "pass"
            for combination_id in item.get("combination_ids", [])
        }
        missing_combinations = set(asset.get("required_combinations", [])) - tested_combinations
        if missing_combinations:
            add_error(
                errors,
                "required_combination_coverage_missing",
                f"{asset_id}:{','.join(sorted(missing_combinations))}",
            )
        tested_lighting = {
            lighting
            for item in asset_cases
            if item.get("case_kind") == "target_lighting" and item.get("status") == "pass"
            for lighting in item.get("lighting", [])
        }
        missing_lighting = set(asset.get("intended_lighting", [])) - tested_lighting
        if missing_lighting:
            add_error(errors, "target_lighting_coverage_missing", f"{asset_id}:{','.join(sorted(missing_lighting))}")

    verdict = document.get("verdict", {})
    verdict_status = verdict.get("status")
    complete_claim = verdict_status in COMPLETION_VERDICTS
    if complete_claim and document.get("fixture_only") is True:
        add_error(errors, "fixture_cannot_certify", str(document.get("stress_test_id")))
    if verdict_status == "conditional" and (
        not verdict.get("allowed_shot_scope") or not verdict.get("blocked_shot_scope")
    ):
        add_error(errors, "conditional_scope_missing", str(document.get("stress_test_id")))
    if set(verdict.get("allowed_shot_scope", [])) & set(verdict.get("blocked_shot_scope", [])):
        add_error(errors, "verdict_scope_overlap", str(document.get("stress_test_id")))
    intended_scope = {
        shot_class for asset in assets for shot_class in asset.get("intended_shot_classes", [])
    }
    case_allowed = {scope for item in cases if item.get("status") == "pass" for scope in item.get("allowed_shot_scope", [])}
    case_blocked = {
        scope
        for item in cases
        for scope in (
            item.get("blocked_shot_scope", [])
            if item.get("status") == "pass"
            else list(set(item.get("blocked_shot_scope", [])) | set(item.get("shot_scope", [])))
        )
    }
    verdict_allowed = set(verdict.get("allowed_shot_scope", []))
    verdict_blocked = set(verdict.get("blocked_shot_scope", []))
    for asset_id, asset in asset_map.items():
        asset_case_allowed = {
            scope
            for item in cases
            if item.get("asset_id") == asset_id and item.get("status") == "pass"
            for scope in item.get("allowed_shot_scope", [])
        }
        required_asset_scope = set(asset.get("intended_shot_classes", [])) & verdict_allowed
        if not required_asset_scope.issubset(asset_case_allowed):
            add_error(
                errors,
                "asset_scope_coverage_missing",
                f"{asset_id}:{','.join(sorted(required_asset_scope - asset_case_allowed))}",
            )
    if not verdict_allowed.issubset(case_allowed) or not case_blocked.issubset(verdict_blocked) or verdict_allowed & case_blocked:
        add_error(errors, "verdict_scope_conflict", str(document.get("stress_test_id")))
    if verdict_status == "certified" and (
        intended_scope - verdict_allowed
        or verdict.get("blocked_shot_scope")
    ):
        add_error(errors, "certified_scope_incomplete", str(document.get("stress_test_id")))

    reviewer = verdict.get("reviewer", {})
    if complete_claim and (
        reviewer.get("actor_id") == document.get("producer_actor_id")
        or reviewer.get("reviewer_type") == "producer"
        or reviewer.get("receipt_source") == "producer"
    ):
        add_error(errors, "producer_receipt_cannot_certify", str(document.get("stress_test_id")))
    try:
        datetime.fromisoformat(str(reviewer.get("timestamp", "")).replace("Z", "+00:00"))
    except ValueError:
        add_error(errors, "review_timestamp_invalid", str(reviewer.get("timestamp")))

    if not document.get("fixture_only") and artifact_root is None:
        add_error(errors, "artifact_root_required", str(document.get("stress_test_id")))
    if artifact_root is not None:
        for asset in assets:
            verify_file(
                artifact_root,
                asset.get("canonical_relative_path"),
                asset.get("canonical_sha256"),
                f"canonical:{asset.get('asset_id')}",
                errors,
                require_media=True,
            )
        for reference in references:
            verify_file(
                artifact_root,
                reference.get("relative_path"),
                reference.get("sha256"),
                f"reference:{reference.get('reference_id')}",
                errors,
                require_media=True,
            )
        for item in cases:
            evidence = [entry for entry in item.get("evidence", []) if isinstance(entry, dict)]
            if complete_claim and item.get("status") == "pass" and not evidence:
                add_error(errors, "test_case_evidence_missing", str(item.get("test_case_id")))
            for entry in evidence:
                if complete_claim and entry.get("receipt_source") != "external_verified":
                    add_error(errors, "test_case_evidence_unverified", str(item.get("test_case_id")))
                verify_file(
                    artifact_root,
                    entry.get("relative_path"),
                    entry.get("sha256"),
                    f"test:{item.get('test_case_id')}",
                    errors,
                    require_media=True,
                )
    elif complete_claim:
        add_error(errors, "test_case_evidence_missing", str(document.get("stress_test_id")))

    if complete_claim:
        incomplete = [
            str(item.get("test_case_id"))
            for item in cases
            if item.get("case_kind") in set(asset_map.get(str(item.get("asset_id")), {}).get("required_case_kinds", []))
            and item.get("status") != "pass"
        ]
        if incomplete:
            add_error(errors, "stress_matrix_incomplete", ",".join(incomplete))
        if review_receipt_path is None:
            add_error(errors, "independent_review_receipt_required", str(document.get("stress_test_id")))
        else:
            try:
                receipt_resolved = review_receipt_path.resolve(strict=True)
                if artifact_root is not None:
                    receipt_resolved.relative_to(artifact_root.resolve(strict=True))
            except ValueError:
                pass
            except (FileNotFoundError, RuntimeError):
                add_error(errors, "review_receipt_missing", str(review_receipt_path))
                receipt_resolved = None
            else:
                add_error(errors, "producer_receipt_cannot_certify", "review receipt is inside artifact root")
                receipt_resolved = None
            if receipt_resolved is not None:
                verify_review_signature(
                    review_signature_path,
                    receipt_resolved,
                    authority_id=reviewer.get("review_authority_id"),
                    reviewer_actor_id=reviewer.get("actor_id"),
                    reviewer_source=reviewer.get("receipt_source"),
                    trust_registry_path=trust_registry_path,
                    artifact_root=artifact_root,
                    errors=errors,
                )
                receipt_bytes = receipt_resolved.read_bytes()
                if hashlib.sha256(receipt_bytes).hexdigest() != reviewer.get("receipt_sha256"):
                    add_error(errors, "review_receipt_hash_mismatch", str(review_receipt_path))
                try:
                    receipt = json.loads(receipt_bytes.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    add_error(errors, "review_receipt_invalid", str(review_receipt_path))
                else:
                    receipt_keys = {
                        "stress_test_id",
                        "project_id",
                        "input_spec_sha256",
                        "verdict",
                        "reviewer_actor_id",
                        "review_authority_id",
                        "observed_at",
                        "asset_ids",
                        "test_case_ids",
                        "case_results_sha256",
                        "report_subject_sha256",
                        "allowed_shot_scope",
                        "blocked_shot_scope",
                    }
                    if not isinstance(receipt, dict) or set(receipt) != receipt_keys:
                        add_error(errors, "review_receipt_invalid", str(review_receipt_path))
                    receipt_sensitive = sensitive_paths(receipt)
                    if receipt_sensitive:
                        add_error(errors, "review_receipt_sensitive_value", receipt_sensitive[0])
                    if (
                        receipt.get("stress_test_id") != document.get("stress_test_id")
                        or receipt.get("project_id") != document.get("project_id")
                        or receipt.get("input_spec_sha256") != document.get("input_spec_sha256")
                        or receipt.get("verdict") != verdict_status
                        or receipt.get("reviewer_actor_id") != reviewer.get("actor_id")
                        or receipt.get("review_authority_id") != reviewer.get("review_authority_id")
                        or receipt.get("observed_at") != reviewer.get("timestamp")
                        or set(receipt.get("asset_ids", [])) != set(asset_ids)
                        or set(receipt.get("test_case_ids", [])) != set(case_ids)
                        or receipt.get("case_results_sha256") != canonical_sha256(cases)
                        or receipt.get("report_subject_sha256") != review_subject_sha256(document)
                        or set(receipt.get("allowed_shot_scope", [])) != verdict_allowed
                        or set(receipt.get("blocked_shot_scope", [])) != verdict_blocked
                    ):
                        add_error(errors, "review_receipt_binding_mismatch", str(review_receipt_path))
    return errors


def validate(
    document: dict[str, Any],
    *,
    artifact_root: Path | None = None,
    review_receipt_path: Path | None = None,
    review_signature_path: Path | None = None,
    _trust_registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> list[str]:
    structural = schema_errors(document)
    if structural:
        return structural
    return semantic_errors(
        document,
        artifact_root=artifact_root,
        review_receipt_path=review_receipt_path,
        review_signature_path=review_signature_path,
        trust_registry_path=_trust_registry_path,
    )


def materialize_fixture(
    template: dict[str, Any],
    artifact_root: Path,
    review_root: Path,
    trust_root: Path,
) -> tuple[dict[str, Any], Path, Path, Path]:
    document = copy.deepcopy(template)
    for asset in document["assets"]:
        canonical_path = artifact_root / asset["canonical_relative_path"]
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_path.write_bytes(PNG_FIXTURE_BYTES + asset["asset_id"].encode("utf-8"))
        asset["canonical_sha256"] = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
        active_reference_id = (
            asset.get("character_sheet_contract", {}).get("active_reference_id")
            if isinstance(asset.get("character_sheet_contract"), dict)
            else None
        )
        for reference in asset["references"]:
            path = artifact_root / reference["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if reference.get("reference_id") == active_reference_id:
                path.write_bytes(canonical_path.read_bytes())
            else:
                path.write_bytes(
                    PNG_FIXTURE_BYTES + reference["reference_id"].encode("utf-8")
                )
            reference["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        contract = asset.get("character_sheet_contract")
        if isinstance(contract, dict) and contract.get("mode") in {
            "headed_state",
            "headless_safe",
        }:
            reference_map = {
                str(reference.get("reference_id")): reference
                for reference in asset["references"]
            }
            source_master = reference_map.get(
                str(contract.get("source_master_reference_id"))
            )
            if source_master is not None:
                contract["approved_source_master_sha256"] = source_master["sha256"]
        asset["descriptor_sha256"] = hashlib.sha256(
            asset["descriptor_text"].encode("utf-8")
        ).hexdigest()
    document["input_spec_sha256"] = canonical_sha256(document["assets"])
    for item in document["test_cases"]:
        for evidence in item["evidence"]:
            path = artifact_root / evidence["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(PNG_FIXTURE_BYTES + item["test_case_id"].encode("utf-8"))
            evidence["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    openssl = shutil.which("openssl")
    if openssl is None:
        raise RuntimeError("openssl is required for the signed-review self-test")
    private_key_path = trust_root / "review-private-key.pem"
    public_key_path = trust_root / "review-public-key.pem"
    signature_path = trust_root / "stress-review.sig"
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key_path)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [openssl, "pkey", "-in", str(private_key_path), "-pubout", "-out", str(public_key_path)],
        capture_output=True,
        check=True,
    )
    receipt = {
        "stress_test_id": document["stress_test_id"],
        "project_id": document["project_id"],
        "input_spec_sha256": document["input_spec_sha256"],
        "verdict": document["verdict"]["status"],
        "reviewer_actor_id": document["verdict"]["reviewer"]["actor_id"],
        "review_authority_id": document["verdict"]["reviewer"]["review_authority_id"],
        "observed_at": document["verdict"]["reviewer"]["timestamp"],
        "asset_ids": [item["asset_id"] for item in document["assets"]],
        "test_case_ids": [item["test_case_id"] for item in document["test_cases"]],
        "case_results_sha256": canonical_sha256(document["test_cases"]),
        "report_subject_sha256": review_subject_sha256(document),
        "allowed_shot_scope": document["verdict"]["allowed_shot_scope"],
        "blocked_shot_scope": document["verdict"]["blocked_shot_scope"],
    }
    receipt_path = review_root / "stress-review.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    document["verdict"]["reviewer"]["receipt_sha256"] = hashlib.sha256(
        receipt_path.read_bytes()
    ).hexdigest()
    subprocess.run(
        [openssl, "dgst", "-sha256", "-sign", str(private_key_path), "-out", str(signature_path), str(receipt_path)],
        capture_output=True,
        check=True,
    )
    trusted_key_sha256 = hashlib.sha256(public_key_path.read_bytes()).hexdigest()
    registry_path = trust_root / "review-trust-registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "authority": "host_configuration_only",
                "review_authorities": [
                    {
                        "authority_id": document["verdict"]["reviewer"]["review_authority_id"],
                        "authority_kind": "asset_reviewer",
                        "actor_id": document["verdict"]["reviewer"]["actor_id"],
                        "allowed_purposes": ["asset_stress_review"],
                        "allowed_sources": [document["verdict"]["reviewer"]["receipt_source"]],
                        "status": "active",
                        "public_key_relative_path": public_key_path.name,
                        "public_key_sha256": trusted_key_sha256,
                    }
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return document, receipt_path, signature_path, registry_path


def self_test() -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    template = load_json(VALID_PATH)
    cases = load_json(CASES_PATH).get("cases", [])
    v3_payload = load_json(V3_CASES_PATH)
    v3_cases = v3_payload.get("cases", [])
    with tempfile.TemporaryDirectory(prefix="dircreative-asset-stress-") as temp_dir:
        temp_root = Path(temp_dir)
        artifact_root = temp_root / "artifacts"
        review_root = temp_root / "reviews"
        trust_root = temp_root / "trust"
        artifact_root.mkdir()
        review_root.mkdir()
        trust_root.mkdir()
        valid, receipt_path, signature_path, registry_path = materialize_fixture(
            template,
            artifact_root,
            review_root,
            trust_root,
        )
        valid_errors = validate(
            valid,
            artifact_root=artifact_root,
            review_receipt_path=receipt_path,
            review_signature_path=signature_path,
            _trust_registry_path=registry_path,
        )
        if valid_errors:
            failures.append(f"valid fixture rejected: {valid_errors[:3]}")
        v1_artifact_root = temp_root / "v1-artifacts"
        v1_review_root = temp_root / "v1-reviews"
        v1_trust_root = temp_root / "v1-trust"
        v1_artifact_root.mkdir()
        v1_review_root.mkdir()
        v1_trust_root.mkdir()
        v1, v1_receipt, v1_signature, v1_registry = materialize_fixture(
            load_json(VALID_V1_PATH),
            v1_artifact_root,
            v1_review_root,
            v1_trust_root,
        )
        v1_errors = validate(
            v1,
            artifact_root=v1_artifact_root,
            review_receipt_path=v1_receipt,
            review_signature_path=v1_signature,
            _trust_registry_path=v1_registry,
        )
        if v1_errors:
            failures.append(f"valid v1 fixture rejected: {v1_errors[:3]}")
        v3_artifact_root = temp_root / "v3-artifacts"
        v3_review_root = temp_root / "v3-reviews"
        v3_trust_root = temp_root / "v3-trust"
        v3_artifact_root.mkdir()
        v3_review_root.mkdir()
        v3_trust_root.mkdir()
        v3_headed, v3_receipt, v3_signature, v3_registry = materialize_fixture(
            load_json(VALID_V3_PATH),
            v3_artifact_root,
            v3_review_root,
            v3_trust_root,
        )
        v3_headed_errors = validate(
            v3_headed,
            artifact_root=v3_artifact_root,
            review_receipt_path=v3_receipt,
            review_signature_path=v3_signature,
            _trust_registry_path=v3_registry,
        )
        if v3_headed_errors:
            failures.append(f"valid v3 headed fixture rejected: {v3_headed_errors[:3]}")
        v3_full_input_artifact_root = temp_root / "v3-full-input-artifacts"
        v3_full_input_review_root = temp_root / "v3-full-input-reviews"
        v3_full_input_trust_root = temp_root / "v3-full-input-trust"
        v3_full_input_artifact_root.mkdir()
        v3_full_input_review_root.mkdir()
        v3_full_input_trust_root.mkdir()
        v3_full_input_template = load_json(VALID_V3_PATH)
        v3_full_input_template["stress_test_id"] = "STRESS-V3-FULL-INPUT"
        full_input_reference = v3_full_input_template["assets"][0]["references"][3]
        full_input_reference["reference_id"] = "REF-FULL-GENERATION-INPUT"
        full_input_reference["relative_path"] = "references/roco-full-generation-input.png"
        full_input_reference["source_kind"] = "character_full_generation_input"
        del v3_full_input_template["assets"][0]["references"][4]
        v3_full_input_template["assets"][0]["character_sheet_contract"][
            "generation_input_reference_ids"
        ] = ["REF-FULL-GENERATION-INPUT"]
        (
            v3_full_input,
            v3_full_input_receipt,
            v3_full_input_signature,
            v3_full_input_registry,
        ) = materialize_fixture(
            v3_full_input_template,
            v3_full_input_artifact_root,
            v3_full_input_review_root,
            v3_full_input_trust_root,
        )
        v3_full_input_errors = validate(
            v3_full_input,
            artifact_root=v3_full_input_artifact_root,
            review_receipt_path=v3_full_input_receipt,
            review_signature_path=v3_full_input_signature,
            _trust_registry_path=v3_full_input_registry,
        )
        if v3_full_input_errors:
            failures.append(
                f"valid v3 full-input fixture rejected: {v3_full_input_errors[:3]}"
            )
        v3_headless_artifact_root = temp_root / "v3-headless-artifacts"
        v3_headless_review_root = temp_root / "v3-headless-reviews"
        v3_headless_trust_root = temp_root / "v3-headless-trust"
        v3_headless_artifact_root.mkdir()
        v3_headless_review_root.mkdir()
        v3_headless_trust_root.mkdir()
        v3_headless_template = apply_mutations(
            load_json(VALID_V3_PATH),
            v3_payload.get("headless_valid_mutations", []),
        )
        v3_headless, v3_headless_receipt, v3_headless_signature, v3_headless_registry = (
            materialize_fixture(
                v3_headless_template,
                v3_headless_artifact_root,
                v3_headless_review_root,
                v3_headless_trust_root,
            )
        )
        v3_headless_errors = validate(
            v3_headless,
            artifact_root=v3_headless_artifact_root,
            review_receipt_path=v3_headless_receipt,
            review_signature_path=v3_headless_signature,
            _trust_registry_path=v3_headless_registry,
        )
        if v3_headless_errors:
            failures.append(
                f"valid v3 headless fixture rejected: {v3_headless_errors[:3]}"
            )
        v3_state_artifact_root = temp_root / "v3-state-artifacts"
        v3_state_review_root = temp_root / "v3-state-reviews"
        v3_state_trust_root = temp_root / "v3-state-trust"
        v3_state_artifact_root.mkdir()
        v3_state_review_root.mkdir()
        v3_state_trust_root.mkdir()
        v3_state_template = apply_mutations(
            load_json(VALID_V3_PATH),
            v3_payload.get("state_valid_mutations", []),
        )
        v3_state, v3_state_receipt, v3_state_signature, v3_state_registry = (
            materialize_fixture(
                v3_state_template,
                v3_state_artifact_root,
                v3_state_review_root,
                v3_state_trust_root,
            )
        )
        v3_state_errors = validate(
            v3_state,
            artifact_root=v3_state_artifact_root,
            review_receipt_path=v3_state_receipt,
            review_signature_path=v3_state_signature,
            _trust_registry_path=v3_state_registry,
        )
        if v3_state_errors:
            failures.append(
                f"valid v3 headed-state fixture rejected: {v3_state_errors[:3]}"
            )
        rejected = 0
        for case in cases:
            mutated = apply_mutations(valid, case["mutations"])
            errors = validate(
                mutated,
                artifact_root=artifact_root,
                review_receipt_path=receipt_path,
                review_signature_path=signature_path,
                _trust_registry_path=registry_path,
            )
            expected = case["expected_error"]
            if any(error.startswith(expected + ":") for error in errors):
                rejected += 1
            else:
                failures.append(f"{case['case_id']}: expected {expected}, got {errors[:3]}")
        v3_rejected = 0
        for case in v3_cases:
            if case.get("base") == "headless":
                base_document = v3_headless
                base_artifact_root = v3_headless_artifact_root
                base_receipt = v3_headless_receipt
                base_signature = v3_headless_signature
                base_registry = v3_headless_registry
            elif case.get("base") == "state":
                base_document = v3_state
                base_artifact_root = v3_state_artifact_root
                base_receipt = v3_state_receipt
                base_signature = v3_state_signature
                base_registry = v3_state_registry
            else:
                base_document = v3_headed
                base_artifact_root = v3_artifact_root
                base_receipt = v3_receipt
                base_signature = v3_signature
                base_registry = v3_registry
            mutated = apply_mutations(base_document, case["mutations"])
            errors = validate(
                mutated,
                artifact_root=base_artifact_root,
                review_receipt_path=base_receipt,
                review_signature_path=base_signature,
                _trust_registry_path=base_registry,
            )
            expected = case["expected_error"]
            if any(error.startswith(expected + ":") for error in errors):
                v3_rejected += 1
            else:
                failures.append(
                    f"{case['case_id']}: expected {expected}, got {errors[:3]}"
                )
        state_drift = copy.deepcopy(v3_headed)
        drift_asset = copy.deepcopy(state_drift["assets"][0])
        drift_asset["asset_id"] = "CHAR-ROCO-V3-WET"
        drift_asset["asset_version"] = "v3-wet"
        drift_asset["state_id"] = "ROCO-WET"
        drift_asset["canonical_relative_path"] = "canonical/char-roco-v3-wet.png"
        drift_asset["canonical_sha256"] = "f" * 64
        reference_id_map: dict[str, str] = {}
        for reference in drift_asset["references"]:
            old_id = str(reference["reference_id"])
            new_id = old_id + "-WET"
            reference_id_map[old_id] = new_id
            reference["reference_id"] = new_id
            reference["relative_path"] = "references/wet-" + Path(
                str(reference["relative_path"])
            ).name
            reference["sha256"] = "f" * 64
        drift_contract = drift_asset["character_sheet_contract"]
        drift_contract["generation_input_reference_ids"] = [
            reference_id_map[str(reference_id)]
            for reference_id in drift_contract["generation_input_reference_ids"]
        ]
        drift_contract["active_reference_id"] = reference_id_map[
            str(drift_contract["active_reference_id"])
        ]
        drift_contract["source_master_reference_id"] = reference_id_map[
            str(drift_contract["source_master_reference_id"])
        ]
        if drift_contract.get("detail_reference_id") is not None:
            drift_contract["detail_reference_id"] = reference_id_map[
                str(drift_contract["detail_reference_id"])
            ]
        for requirement in drift_contract.get("detail_requirements", []):
            source_reference_id = requirement.get("source_reference_id")
            if source_reference_id is not None:
                requirement["source_reference_id"] = reference_id_map[
                    str(source_reference_id)
                ]
        for reference in drift_asset["references"]:
            derived_from = reference.get("derived_from_reference_id")
            if derived_from is not None:
                reference["derived_from_reference_id"] = reference_id_map[
                    str(derived_from)
                ]
        state_drift["assets"].append(drift_asset)
        state_drift["input_spec_sha256"] = canonical_sha256(state_drift["assets"])
        state_drift_errors = validate(
            state_drift,
            artifact_root=v3_artifact_root,
            review_receipt_path=v3_receipt,
            review_signature_path=v3_signature,
            _trust_registry_path=v3_registry,
        )
        if any(
            error.startswith("state_family_master_sheet_drift:")
            for error in state_drift_errors
        ):
            v3_rejected += 1
        else:
            failures.append(
                "state_family_master_sheet_drift: expected state family source drift rejection"
            )
        trust_cases = [
            (
                "missing_host_pinned_signature",
                validate(
                    valid,
                    artifact_root=artifact_root,
                    review_receipt_path=receipt_path,
                    review_signature_path=None,
                    _trust_registry_path=registry_path,
                ),
                "trusted_review_signature_required",
            ),
            (
                "unconfigured_review_authority",
                validate(
                    valid,
                    artifact_root=artifact_root,
                    review_receipt_path=receipt_path,
                    review_signature_path=signature_path,
                ),
                "review_authority_unconfigured",
            ),
        ]
        for case_id, errors, expected in trust_cases:
            if any(error.startswith(expected + ":") for error in errors):
                rejected += 1
            else:
                failures.append(f"{case_id}: expected {expected}, got {errors[:3]}")
        multi_asset = copy.deepcopy(valid)
        second_asset = copy.deepcopy(multi_asset["assets"][0])
        second_asset["asset_id"] = "CHAR-SECONDARY"
        second_asset["state_family"] = "SECONDARY-APPEARANCE"
        second_asset["state_id"] = "SECONDARY-BASE"
        second_asset["required_case_kinds"] = ["face_close_up"]
        second_asset["required_combinations"] = []
        for index, reference in enumerate(second_asset["references"], 1):
            reference["reference_id"] = f"REF-SECONDARY-{index}"
        multi_asset["assets"].append(second_asset)
        second_case = copy.deepcopy(multi_asset["test_cases"][0])
        second_case["test_case_id"] = "TC-SECONDARY-FACE"
        second_case["asset_id"] = second_asset["asset_id"]
        second_case["state_family"] = second_asset["state_family"]
        second_case["allowed_shot_scope"] = []
        second_case["evidence"][0]["evidence_id"] = "EV-SECONDARY-FACE"
        multi_asset["test_cases"].append(second_case)
        multi_asset["input_spec_sha256"] = canonical_sha256(multi_asset["assets"])
        multi_errors = validate(
            multi_asset,
            artifact_root=artifact_root,
            review_receipt_path=receipt_path,
            review_signature_path=signature_path,
            _trust_registry_path=registry_path,
        )
        multi_scope_rejected = any(
            error.startswith("asset_scope_coverage_missing:") for error in multi_errors
        )
        if multi_scope_rejected:
            rejected += 1
        else:
            failures.append(f"cross-asset scope borrowing accepted: {multi_errors[:3]}")
        reused_evidence = copy.deepcopy(valid)
        reused_evidence["test_cases"][1]["evidence"][0]["relative_path"] = (
            reused_evidence["test_cases"][0]["evidence"][0]["relative_path"]
        )
        reused_evidence["test_cases"][1]["evidence"][0]["sha256"] = (
            reused_evidence["test_cases"][0]["evidence"][0]["sha256"]
        )
        reused_errors = validate(
            reused_evidence,
            artifact_root=artifact_root,
            review_receipt_path=receipt_path,
            review_signature_path=signature_path,
            _trust_registry_path=registry_path,
        )
        evidence_reuse_rejected = any(
            error.startswith("evidence_hash_reused:") for error in reused_errors
        )
        if evidence_reuse_rejected:
            rejected += 1
        else:
            failures.append(f"cross-case evidence hash reuse accepted: {reused_errors[:3]}")
        secret_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        secret_receipt["Authorization"] = "Bearer fixture-secret-material"
        receipt_path.write_text(
            json.dumps(secret_receipt, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                str(shutil.which("openssl")),
                "dgst",
                "-sha256",
                "-sign",
                str(trust_root / "review-private-key.pem"),
                "-out",
                str(signature_path),
                str(receipt_path),
            ],
            capture_output=True,
            check=True,
        )
        secret_document = copy.deepcopy(valid)
        secret_document["verdict"]["reviewer"]["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        secret_errors = validate(
            secret_document,
            artifact_root=artifact_root,
            review_receipt_path=receipt_path,
            review_signature_path=signature_path,
            _trust_registry_path=registry_path,
        )
        secret_receipt_rejected = any(
            error.startswith("review_receipt_sensitive_value:") for error in secret_errors
        )
        if secret_receipt_rejected:
            rejected += 1
        else:
            failures.append(f"sensitive signed review receipt accepted: {secret_errors[:3]}")
    return failures, {
        "valid_fixture_passed": not valid_errors,
        "valid_v1_fixture_passed": not v1_errors,
        "valid_v3_headed_fixture_passed": not v3_headed_errors,
        "valid_v3_full_input_fixture_passed": not v3_full_input_errors,
        "valid_v3_headless_fixture_passed": not v3_headless_errors,
        "valid_v3_headed_state_fixture_passed": not v3_state_errors,
        "matrix_case_count": len(valid.get("test_cases", [])),
        "v3_headed_matrix_case_count": len(v3_headed.get("test_cases", [])),
        "v3_headless_matrix_case_count": len(v3_headless.get("test_cases", [])),
        "negative_case_count": len(cases) + len(trust_cases) + 3,
        "negative_cases_rejected": rejected,
        "v3_negative_case_count": len(v3_cases) + 1,
        "v3_negative_cases_rejected": v3_rejected,
        "verdict": valid.get("verdict", {}).get("status"),
        "media_generation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-film asset stress-test reports.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--artifact-root", type=Path)
    validate_parser.add_argument("--review-receipt", type=Path)
    validate_parser.add_argument("--review-signature", type=Path)
    args = parser.parse_args()
    if args.command == "self-test":
        failures, summary = self_test()
        print(json.dumps({**summary, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"AI_FILM_ASSET_STRESS_TEST_AUDIT: {'PASS' if not failures else 'FAIL'}")
        return 0 if not failures else 1
    errors = validate(
        load_json(args.path),
        artifact_root=args.artifact_root,
        review_receipt_path=args.review_receipt,
        review_signature_path=args.review_signature,
    )
    print(json.dumps({"path": str(args.path), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
