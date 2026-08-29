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
}
VALID_PATH = ROOT / "tests/fixtures/asset-stress-test/valid-report.json"
VALID_V1_PATH = ROOT / "tests/fixtures/asset-stress-test/valid-report-v1.json"
CASES_PATH = ROOT / "tests/fixtures/asset-stress-test/cases.json"
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


def semantic_errors(
    document: dict[str, Any],
    *,
    artifact_root: Path | None,
    review_receipt_path: Path | None,
    review_signature_path: Path | None,
    trust_registry_path: Path,
) -> list[str]:
    errors: list[str] = []
    strict_character_roles = document.get("contract_id") == "ai_film_asset_stress_test_v2"
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
        if strict_character_roles and item.get("case_kind") == "headless_wardrobe":
            invariants = " ".join(str(value).casefold() for value in item.get("expected_invariants", []))
            if "headless" not in invariants or "face" not in invariants:
                add_error(
                    errors,
                    "headless_wardrobe_invariant_missing",
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
        for reference in asset["references"]:
            path = artifact_root / reference["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(PNG_FIXTURE_BYTES + reference["reference_id"].encode("utf-8"))
            reference["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
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
        "matrix_case_count": len(valid.get("test_cases", [])),
        "negative_case_count": len(cases) + len(trust_cases) + 3,
        "negative_cases_rejected": rejected,
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
