#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/ai-film-production-ledger.schema.json"
VALID_PATH = ROOT / "tests/fixtures/production-ledger/valid-ledger.json"
CASES_PATH = ROOT / "tests/fixtures/production-ledger/cases.json"
TRANSITIONS = {
    "planned": {"attached", "rejected", "superseded"},
    "attached": {"executed", "rejected", "superseded"},
    "executed": {"observed_unverified", "generated_verified", "rejected", "superseded"},
    "observed_unverified": {"generated_verified", "rejected", "superseded"},
    "generated_verified": {"selected", "rejected", "superseded"},
    "selected": {"delivered", "superseded"},
    "rejected": {"superseded"},
    "superseded": set(),
    "delivered": set(),
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def generation_candidate_sha256(attempt: dict[str, Any]) -> str:
    keys = (
        "attempt_id",
        "attempt_kind",
        "parent_attempt_id",
        "project_id",
        "scene_id",
        "shot_id",
        "generation_unit_id",
        "asset_bindings",
        "prompt_artifact",
        "model_snapshot",
        "authorized_execution_state",
        "expected_visible_proof",
        "primary_delta",
        "preserved_successes",
    )
    return canonical_sha256({key: attempt.get(key) for key in keys})


def generated_subject_sha256(attempt: dict[str, Any]) -> str:
    return canonical_sha256(
        {
            "generation_candidate_sha256": generation_candidate_sha256(attempt),
            "output_manifest": attempt.get("output_manifest", []),
        }
    )


def cost_subject_sha256(attempt: dict[str, Any]) -> str:
    cost = attempt.get("cost_credits", {})
    return canonical_sha256(
        {
            "attempt_id": attempt.get("attempt_id"),
            "amount": cost.get("amount"),
            "currency": cost.get("currency"),
        }
    )


def genesis_sha256(document: dict[str, Any]) -> str:
    attempts = document.get("attempts", [])
    first_attempt = attempts[0] if attempts and isinstance(attempts[0], dict) else {}
    return canonical_sha256(
        {
            "project_id": document.get("project_id"),
            "ledger_id": document.get("ledger_id"),
            "first_generation_candidate_sha256": generation_candidate_sha256(first_attempt),
        }
    )


def schema_errors(document: dict[str, Any]) -> list[str]:
    return validate_schema(document, SCHEMA_PATH)


def append_only_errors(current: dict[str, Any], previous: dict[str, Any] | None) -> list[str]:
    if previous is None:
        return []
    errors: list[str] = []
    if previous.get("project_id") != current.get("project_id"):
        add_error(errors, "append_only_project_mismatch", str(current.get("project_id")))
        return errors
    if (
        previous.get("ledger_id") != current.get("ledger_id")
        or previous.get("genesis_sha256") != current.get("genesis_sha256")
    ):
        add_error(errors, "append_only_genesis_mismatch", str(current.get("ledger_id")))
    prior_attempts = previous.get("attempts", [])
    current_attempts = current.get("attempts", [])
    if len(current_attempts) < len(prior_attempts):
        add_error(errors, "append_only_attempt_mutation", "attempts")
    immutable_keys = {
        "attempt_id",
        "attempt_kind",
        "parent_attempt_id",
        "project_id",
        "scene_id",
        "shot_id",
        "generation_unit_id",
        "asset_bindings",
        "prompt_artifact",
        "model_snapshot",
        "authorized_execution_state",
        "expected_visible_proof",
        "primary_delta",
        "preserved_successes",
        "edit_timeline_placement",
        "created_at",
        "actor",
        "source_status",
    }
    for index, prior in enumerate(prior_attempts):
        if index >= len(current_attempts) or not isinstance(prior, dict) or not isinstance(current_attempts[index], dict):
            add_error(errors, "append_only_attempt_mutation", f"attempts[{index}]")
            continue
        current_attempt = current_attempts[index]
        if any(prior.get(key) != current_attempt.get(key) for key in immutable_keys):
            add_error(errors, "append_only_attempt_mutation", str(prior.get("attempt_id")))
        for key in ("output_manifest", "review_evidence"):
            prior_items = prior.get(key, [])
            current_items = current_attempt.get(key, [])
            if len(current_items) < len(prior_items) or current_items[: len(prior_items)] != prior_items:
                add_error(errors, "append_only_attempt_mutation", f"{prior.get('attempt_id')}:{key}")
        prior_cost = prior.get("cost_credits", {})
        current_cost = current_attempt.get("cost_credits", {})
        if (
            prior_cost.get("status") == "verified"
            and current_cost != prior_cost
        ) or (
            prior_cost.get("status") == "unverified"
            and current_cost.get("status") not in {"unverified", "verified"}
        ) or (
            prior_cost.get("status") == "unverified"
            and current_cost.get("status") == "unverified"
            and current_cost != prior_cost
        ):
            add_error(errors, "append_only_attempt_mutation", f"{prior.get('attempt_id')}:cost_credits")
    for key, code in (
        ("receipt_manifest", "append_only_receipt_mutation"),
        ("state_events", "append_only_event_mutation"),
    ):
        prior_items = previous.get(key, [])
        current_items = current.get(key, [])
        if len(current_items) < len(prior_items) or current_items[: len(prior_items)] != prior_items:
            add_error(errors, code, key)
    return errors


def semantic_errors(
    document: dict[str, Any],
    *,
    previous: dict[str, Any] | None,
    artifact_root: Path | None,
    initial_ledger: bool,
    trust_registry_path: Path,
) -> list[str]:
    errors = append_only_errors(document, previous)
    if previous is None and not initial_ledger:
        add_error(errors, "append_only_previous_required", "use --previous or explicitly declare --initial-ledger")
    sensitive = sensitive_paths(document)
    if sensitive:
        add_error(errors, "sensitive_value_forbidden", sensitive[0])
    project_id = document.get("project_id")
    attempts = [item for item in document.get("attempts", []) if isinstance(item, dict)]
    if genesis_sha256(document) != document.get("genesis_sha256"):
        add_error(errors, "genesis_hash_mismatch", str(document.get("ledger_id")))
    attempt_ids = [str(item.get("attempt_id")) for item in attempts]
    if len(attempt_ids) != len(set(attempt_ids)):
        add_error(errors, "attempt_id_duplicate", str(attempt_ids))
    attempt_map: dict[str, dict[str, Any]] = {}
    output_hash_owners: dict[str, str] = {}
    output_id_owners: dict[str, str] = {}
    receipts = [item for item in document.get("receipt_manifest", []) if isinstance(item, dict)]
    receipt_ids = [str(item.get("receipt_id")) for item in receipts]
    if len(receipt_ids) != len(set(receipt_ids)):
        add_error(errors, "receipt_id_duplicate", str(receipt_ids))
    receipt_map = {str(item.get("receipt_id")): item for item in receipts}
    key_cache: dict[str, tuple[Path | None, str | None, dict[str, Any] | None]] = {}
    for receipt_id, receipt in receipt_map.items():
        relative = receipt.get("relative_path")
        if not safe_relative_path(relative):
            add_error(errors, "receipt_path_invalid", f"{receipt_id}:{relative}")
            continue
        if artifact_root is None:
            add_error(errors, "receipt_artifact_root_required", receipt_id)
            continue
        signature_relative = receipt.get("signature_relative_path")
        if not safe_relative_path(signature_relative):
            add_error(errors, "receipt_signature_path_invalid", f"{receipt_id}:{signature_relative}")
            continue
        try:
            root = artifact_root.resolve(strict=True)
            path = (root / str(relative)).resolve(strict=True)
            path.relative_to(root)
            signature_path = (root / str(signature_relative)).resolve(strict=True)
            signature_path.relative_to(root)
        except (FileNotFoundError, RuntimeError, ValueError):
            add_error(errors, "receipt_file_missing", f"{receipt_id}:{relative}")
        else:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != receipt.get("sha256"):
                add_error(errors, "receipt_file_hash_mismatch", f"{receipt_id}:{relative}")
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                add_error(errors, "receipt_payload_invalid", receipt_id)
            else:
                binding_keys = (
                    "receipt_id",
                    "authority_id",
                    "purpose",
                    "attempt_id",
                    "subject_sha256",
                    "observed_at",
                    "source",
                    "actor",
                )
                if (
                    not isinstance(payload, dict)
                    or set(payload) != set(binding_keys)
                    or any(payload.get(key) != receipt.get(key) for key in binding_keys)
                ):
                    add_error(errors, "receipt_payload_binding_mismatch", receipt_id)
                receipt_sensitive = sensitive_paths(payload)
                if receipt_sensitive:
                    add_error(errors, "receipt_payload_sensitive_value", receipt_sensitive[0])
                try:
                    datetime.fromisoformat(str(payload.get("observed_at", "")).replace("Z", "+00:00"))
                except ValueError:
                    add_error(errors, "receipt_observed_at_invalid", receipt_id)
            authority_id = str(receipt.get("authority_id"))
            if authority_id not in key_cache:
                public_key, openssl, authority_policy, trust_errors = resolve_review_key(
                    authority_id,
                    registry_path=trust_registry_path,
                    artifact_root=artifact_root,
                )
                errors.extend(trust_errors)
                key_cache[authority_id] = (public_key, openssl, authority_policy)
            receipt_key, openssl, authority_policy = key_cache[authority_id]
            if authority_policy is not None and (
                authority_policy.get("actor_id") != receipt.get("actor")
                or receipt.get("purpose") not in authority_policy.get("allowed_purposes", [])
                or receipt.get("source") not in authority_policy.get("allowed_sources", [])
                or (
                    receipt.get("purpose") == "ledger_genesis"
                    and authority_policy.get("authority_kind") != "ledger_host"
                )
                or (
                    receipt.get("purpose") in {"execution", "generation"}
                    and authority_policy.get("authority_kind") != "media_provider"
                )
                or (
                    receipt.get("purpose") == "review"
                    and authority_policy.get("authority_kind") != "human_reviewer"
                )
                or (
                    receipt.get("purpose") == "delivery"
                    and authority_policy.get("authority_kind") != "delivery_host"
                )
                or (
                    receipt.get("purpose") == "billing"
                    and authority_policy.get("authority_kind") != "billing_provider"
                )
            ):
                add_error(errors, "receipt_authority_scope_invalid", receipt_id)
            if receipt_key is not None and openssl is not None:
                result = subprocess.run(
                    [
                        openssl,
                        "dgst",
                        "-sha256",
                        "-verify",
                        str(receipt_key),
                        "-signature",
                        str(signature_path),
                        str(path),
                    ],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                if result.returncode != 0:
                    add_error(errors, "receipt_signature_invalid", receipt_id)
    for index, attempt in enumerate(attempts):
        attempt_id = str(attempt.get("attempt_id"))
        if attempt.get("project_id") != project_id:
            add_error(errors, "attempt_project_mismatch", attempt_id)
        parent_id = attempt.get("parent_attempt_id")
        if attempt.get("attempt_kind") == "initial" and parent_id is not None:
            add_error(errors, "initial_attempt_has_parent", attempt_id)
        if attempt.get("attempt_kind") == "retry":
            if not isinstance(parent_id, str) or parent_id not in attempt_map:
                add_error(errors, "retry_parent_missing", attempt_id)
            else:
                parent = attempt_map[parent_id]
                scope_fields = ("project_id", "scene_id", "shot_id", "generation_unit_id")
                if any(attempt.get(field) != parent.get(field) for field in scope_fields):
                    add_error(errors, "retry_scope_mismatch", attempt_id)
            if not attempt.get("preserved_successes"):
                add_error(errors, "retry_preserved_successes_missing", attempt_id)
        prompt = attempt.get("prompt_artifact", {})
        text = str(prompt.get("prompt_text", ""))
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != prompt.get("prompt_sha256"):
            add_error(errors, "prompt_hash_mismatch", attempt_id)
        for binding in attempt.get("asset_bindings", []):
            if binding.get("attached") is not True or binding.get("source_status") != "available":
                add_error(errors, "asset_binding_not_available", f"{attempt_id}:{binding.get('asset_id')}")
            relative = binding.get("relative_path")
            if not safe_relative_path(relative):
                add_error(errors, "asset_binding_path_invalid", f"{attempt_id}:{relative}")
            elif artifact_root is None:
                add_error(errors, "asset_artifact_root_required", f"{attempt_id}:{binding.get('asset_id')}")
            else:
                try:
                    root = artifact_root.resolve(strict=True)
                    path = (root / str(relative)).resolve(strict=True)
                    path.relative_to(root)
                except (FileNotFoundError, RuntimeError, ValueError):
                    add_error(errors, "asset_binding_file_missing", f"{attempt_id}:{relative}")
                else:
                    if hashlib.sha256(path.read_bytes()).hexdigest() != binding.get("sha256"):
                        add_error(errors, "asset_binding_hash_mismatch", f"{attempt_id}:{relative}")
        cost = attempt.get("cost_credits", {})
        if cost.get("status") == "verified":
            if cost.get("amount") is None or not cost.get("currency"):
                add_error(errors, "verified_cost_incomplete", attempt_id)
            cost_receipt = receipt_map.get(str(cost.get("receipt_id")))
            if cost_receipt is None:
                add_error(errors, "verified_cost_receipt_missing", attempt_id)
            elif (
                cost_receipt.get("purpose") != "billing"
                or cost_receipt.get("attempt_id") != attempt_id
                or cost_receipt.get("subject_sha256") != cost_subject_sha256(attempt)
                or cost_receipt.get("source") != "external_verified"
                or cost_receipt.get("actor") == attempt.get("actor")
            ):
                add_error(errors, "verified_cost_receipt_invalid", attempt_id)
        elif cost.get("receipt_id") is not None:
            add_error(errors, "unverified_cost_has_receipt", attempt_id)
        for output in attempt.get("output_manifest", []):
            output_id = str(output.get("output_id"))
            prior_output_owner = output_id_owners.get(output_id)
            if prior_output_owner is not None:
                add_error(errors, "output_id_duplicate", f"{prior_output_owner}->{attempt_id}:{output_id}")
            output_id_owners[output_id] = attempt_id
            relative = output.get("relative_path")
            if not safe_relative_path(relative):
                add_error(errors, "output_path_invalid", f"{attempt_id}:{relative}")
                continue
            output_hash = output.get("sha256")
            if isinstance(output_hash, str):
                prior_owner = output_hash_owners.get(output_hash)
                if prior_owner is not None and prior_owner != attempt_id:
                    add_error(errors, "output_hash_reused", f"{prior_owner}->{attempt_id}")
                output_hash_owners[output_hash] = attempt_id
            receipt = receipt_map.get(str(output.get("receipt_id")))
            if receipt is None:
                add_error(errors, "output_receipt_unresolved", f"{attempt_id}:{output.get('receipt_id')}")
            elif (
                receipt.get("purpose") != "generation"
                or receipt.get("attempt_id") != attempt_id
                or receipt.get("subject_sha256")
                != generated_subject_sha256(attempt)
                or receipt.get("source") != output.get("receipt_source")
                or receipt.get("actor") == attempt.get("actor")
            ):
                add_error(errors, "output_receipt_binding_invalid", f"{attempt_id}:{output.get('receipt_id')}")
            if artifact_root is None:
                add_error(errors, "output_artifact_root_required", attempt_id)
            if artifact_root is not None:
                try:
                    root = artifact_root.resolve(strict=True)
                    path = (root / str(relative)).resolve(strict=True)
                    path.relative_to(root)
                except (FileNotFoundError, RuntimeError, ValueError):
                    add_error(errors, "output_file_missing", f"{attempt_id}:{relative}")
                else:
                    if hashlib.sha256(path.read_bytes()).hexdigest() != output_hash:
                        add_error(errors, "output_file_hash_mismatch", f"{attempt_id}:{relative}")
        attempt_map[attempt_id] = attempt

    events = [item for item in document.get("state_events", []) if isinstance(item, dict)]
    genesis_receipt = next(
        (receipt for receipt in receipts if receipt.get("purpose") == "ledger_genesis"),
        None,
    )
    if initial_ledger and (
        len(attempts) != 1
        or attempts[0].get("attempt_kind") != "initial"
        or attempts[0].get("parent_attempt_id") is not None
        or bool(attempts[0].get("output_manifest"))
        or bool(attempts[0].get("review_evidence"))
        or len(receipts) != 1
        or genesis_receipt is None
        or genesis_receipt.get("attempt_id") != attempts[0].get("attempt_id")
        or genesis_receipt.get("subject_sha256") != document.get("genesis_sha256")
        or genesis_receipt.get("source") != "host_observation"
        or len(events) != 1
        or events[0].get("attempt_id") != attempts[0].get("attempt_id")
        or events[0].get("state") != "planned"
        or events[0].get("evidence_source") != "host_observation"
        or events[0].get("evidence_refs") != [genesis_receipt.get("receipt_id")]
        or events[0].get("actor") != genesis_receipt.get("actor")
        or events[0].get("created_at") != genesis_receipt.get("observed_at")
    ):
        add_error(errors, "initial_ledger_shape_invalid", str(document.get("ledger_id")))
    event_ids = [str(item.get("event_id")) for item in events]
    if len(event_ids) != len(set(event_ids)):
        add_error(errors, "event_id_duplicate", str(event_ids))
    states_by_attempt: dict[str, list[dict[str, Any]]] = {attempt_id: [] for attempt_id in attempt_map}
    for event in events:
        attempt_id = str(event.get("attempt_id"))
        if attempt_id not in attempt_map:
            add_error(errors, "event_attempt_unresolved", attempt_id)
            continue
        states_by_attempt[attempt_id].append(event)
    for attempt_id, attempt_events in states_by_attempt.items():
        if not attempt_events or attempt_events[0].get("state") != "planned":
            add_error(errors, "attempt_missing_planned_state", attempt_id)
            continue
        for previous_event, current_event in zip(attempt_events, attempt_events[1:]):
            previous_state = str(previous_event.get("state"))
            current_state = str(current_event.get("state"))
            if current_state not in TRANSITIONS.get(previous_state, set()):
                add_error(errors, "state_transition_invalid", f"{attempt_id}:{previous_state}->{current_state}")
        attempt = attempt_map[attempt_id]
        for event in attempt_events:
            state = event.get("state")
            evidence_source = event.get("evidence_source")
            evidence_refs = event.get("evidence_refs", [])
            resolved_receipts = [receipt_map.get(str(receipt_id)) for receipt_id in evidence_refs]
            if state in {"executed", "generated_verified", "selected", "delivered"} and (
                not evidence_refs or any(receipt is None for receipt in resolved_receipts)
            ):
                add_error(errors, "state_receipt_unresolved", f"{attempt_id}:{state}")
            expected_receipt = {
                "executed": ("execution", {"host_observation", "external_verified"}),
                "generated_verified": ("generation", {"external_verified"}),
                "selected": ("review", {"independent_review", "human_review"}),
                "delivered": ("delivery", {"external_verified"}),
            }.get(str(state))
            if expected_receipt is not None:
                purpose, sources = expected_receipt
                expected_subject_sha256 = (
                    generation_candidate_sha256(attempt)
                    if state == "executed"
                    else generated_subject_sha256(attempt)
                )
                if any(
                    receipt is not None
                    and (
                        receipt.get("purpose") != purpose
                        or receipt.get("attempt_id") != attempt_id
                        or receipt.get("subject_sha256") != expected_subject_sha256
                        or receipt.get("source") not in sources
                        or receipt.get("source") != evidence_source
                        or receipt.get("actor") == attempt.get("actor")
                    )
                    for receipt in resolved_receipts
                ):
                    add_error(errors, "state_receipt_binding_invalid", f"{attempt_id}:{state}")
                if any(
                    receipt is not None and receipt.get("actor") != event.get("actor")
                    for receipt in resolved_receipts
                ):
                    add_error(errors, "state_receipt_actor_mismatch", f"{attempt_id}:{state}")
                if any(
                    receipt is not None and receipt.get("observed_at") != event.get("created_at")
                    for receipt in resolved_receipts
                ):
                    add_error(errors, "state_receipt_time_mismatch", f"{attempt_id}:{state}")
            if state not in {"planned", "attached"} and attempt.get("source_status") == "fixture":
                add_error(errors, "fixture_attempt_cannot_advance", f"{attempt_id}:{state}")
            if state == "executed" and attempt.get("authorized_execution_state") != "authorized":
                add_error(errors, "execution_without_authorization", attempt_id)
            if state == "generated_verified" and (
                evidence_source != "external_verified" or not evidence_refs
            ):
                add_error(errors, "generated_without_external_receipt", attempt_id)
            if state in {"generated_verified", "selected", "delivered"} and not attempt.get(
                "output_manifest"
            ):
                add_error(errors, "generated_output_missing", attempt_id)
            if state in {"generated_verified", "selected", "delivered"} and artifact_root is None:
                add_error(errors, "artifact_root_required_for_verified_state", attempt_id)
            if state == "delivered" and (
                evidence_source != "external_verified" or not evidence_refs
            ):
                add_error(errors, "delivered_without_external_receipt", attempt_id)
            if state == "selected" and (
                evidence_source not in {"independent_review", "human_review"}
                or not evidence_refs
                or event.get("review_verdict") != "accept"
                or not attempt.get("review_evidence")
            ):
                add_error(errors, "selected_without_review", attempt_id)
            if state == "selected":
                for review in attempt.get("review_evidence", []):
                    receipt = receipt_map.get(str(review.get("receipt_id")))
                    if receipt is None:
                        add_error(errors, "review_receipt_unresolved", f"{attempt_id}:{review.get('receipt_id')}")
                    elif (
                        receipt.get("purpose") != "review"
                        or receipt.get("attempt_id") != attempt_id
                        or receipt.get("subject_sha256")
                        != generated_subject_sha256(attempt)
                        or receipt.get("source") != review.get("source")
                        or receipt.get("sha256") != review.get("sha256")
                        or receipt.get("actor") == attempt.get("actor")
                    ):
                        add_error(errors, "review_receipt_binding_invalid", f"{attempt_id}:{review.get('receipt_id')}")
    return errors


def validate(
    document: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
    artifact_root: Path | None = None,
    initial_ledger: bool = False,
    _trust_registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> list[str]:
    structural = schema_errors(document)
    if structural:
        return structural
    return semantic_errors(
        document,
        previous=previous,
        artifact_root=artifact_root,
        initial_ledger=initial_ledger,
        trust_registry_path=_trust_registry_path,
    )


def materialize_asset_bindings(document: dict[str, Any], artifact_root: Path) -> None:
    for attempt in document.get("attempts", []):
        for binding in attempt.get("asset_bindings", []):
            path = artifact_root / binding["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(
                    f"{binding['asset_id']}:{binding['version']}\n".encode("utf-8")
                )
            binding["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def self_test() -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    fixture_temp = tempfile.TemporaryDirectory(prefix="dircreative-ledger-fixture-")
    fixture_root = Path(fixture_temp.name)
    fixture_artifact_root = fixture_root / "artifacts"
    fixture_trust_root = fixture_root / "trust"
    fixture_artifact_root.mkdir()
    fixture_trust_root.mkdir()
    openssl = shutil.which("openssl")
    if openssl is None:
        raise RuntimeError("openssl is required for the signed-ledger self-test")
    genesis_authority_id = "LEDGER-HOST-GENESIS"
    genesis_private_key = fixture_trust_root / "ledger-host-private.pem"
    genesis_public_key = fixture_trust_root / "ledger-host-public.pem"
    subprocess.run(
        [openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(genesis_private_key)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [openssl, "pkey", "-in", str(genesis_private_key), "-pubout", "-out", str(genesis_public_key)],
        capture_output=True,
        check=True,
    )
    fixture_registry_path = fixture_trust_root / "review-trust-registry.json"
    fixture_registry_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "authority": "host_configuration_only",
                "review_authorities": [
                    {
                        "authority_id": genesis_authority_id,
                        "authority_kind": "ledger_host",
                        "actor_id": "ledger-host",
                        "allowed_purposes": ["ledger_genesis"],
                        "allowed_sources": ["host_observation"],
                        "status": "active",
                        "public_key_relative_path": genesis_public_key.name,
                        "public_key_sha256": hashlib.sha256(genesis_public_key.read_bytes()).hexdigest(),
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    valid = load_json(VALID_PATH)
    materialize_asset_bindings(valid, fixture_artifact_root)
    valid["genesis_sha256"] = genesis_sha256(valid)
    genesis = {
        **copy.deepcopy(valid),
        "attempts": [copy.deepcopy(valid["attempts"][0])],
        "receipt_manifest": [],
        "state_events": [copy.deepcopy(valid["state_events"][0])],
    }
    genesis["genesis_sha256"] = genesis_sha256(genesis)
    genesis_receipt_relative = "receipts/ledger-genesis.json"
    genesis_signature_relative = "receipts/ledger-genesis.sig"
    genesis_receipt_path = fixture_artifact_root / genesis_receipt_relative
    genesis_signature_path = fixture_artifact_root / genesis_signature_relative
    genesis_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    genesis_observed_at = genesis["state_events"][0]["created_at"]
    genesis_payload = {
        "receipt_id": "RECEIPT-GENESIS",
        "authority_id": genesis_authority_id,
        "purpose": "ledger_genesis",
        "attempt_id": genesis["attempts"][0]["attempt_id"],
        "subject_sha256": genesis["genesis_sha256"],
        "observed_at": genesis_observed_at,
        "source": "host_observation",
        "actor": "ledger-host",
    }
    genesis_receipt_path.write_text(json.dumps(genesis_payload, sort_keys=True) + "\n", encoding="utf-8")
    subprocess.run(
        [openssl, "dgst", "-sha256", "-sign", str(genesis_private_key), "-out", str(genesis_signature_path), str(genesis_receipt_path)],
        capture_output=True,
        check=True,
    )
    genesis_receipt = {
        **genesis_payload,
        "relative_path": genesis_receipt_relative,
        "signature_relative_path": genesis_signature_relative,
        "sha256": hashlib.sha256(genesis_receipt_path.read_bytes()).hexdigest(),
    }
    genesis["receipt_manifest"] = [genesis_receipt]
    genesis["state_events"][0]["evidence_source"] = "host_observation"
    genesis["state_events"][0]["evidence_refs"] = [genesis_receipt["receipt_id"]]
    genesis["state_events"][0]["actor"] = "ledger-host"
    valid["genesis_sha256"] = genesis["genesis_sha256"]
    valid["receipt_manifest"] = [copy.deepcopy(genesis_receipt)]
    valid["state_events"][0] = copy.deepcopy(genesis["state_events"][0])
    genesis_errors = validate(
        genesis,
        artifact_root=fixture_artifact_root,
        initial_ledger=True,
        _trust_registry_path=fixture_registry_path,
    )
    if genesis_errors:
        failures.append(f"valid genesis rejected: {genesis_errors[:3]}")
    valid_errors = validate(
        valid,
        artifact_root=fixture_artifact_root,
        previous=genesis,
        _trust_registry_path=fixture_registry_path,
    )
    if valid_errors:
        failures.append(f"valid fixture rejected: {valid_errors[:3]}")
    cases = load_json(CASES_PATH).get("cases", [])
    rejected = 0
    for case in cases:
        errors = validate(
            apply_mutations(valid, case["mutations"]),
            artifact_root=fixture_artifact_root,
            previous=genesis,
            _trust_registry_path=fixture_registry_path,
        )
        expected = case["expected_error"]
        if any(error.startswith(expected + ":") for error in errors):
            rejected += 1
        else:
            failures.append(f"{case['case_id']}: expected {expected}, got {errors[:3]}")
    previous = genesis
    append_errors = validate(
        valid,
        previous=previous,
        artifact_root=fixture_artifact_root,
        _trust_registry_path=fixture_registry_path,
    )
    append_only_positive = not append_errors
    if append_errors:
        failures.append(f"valid append rejected: {append_errors[:3]}")
    overwritten = json.loads(canonical(valid))
    overwritten["attempts"][0]["prompt_artifact"]["prompt_text"] = "overwritten parent"
    overwrite_errors = validate(
        overwritten,
        previous=previous,
        artifact_root=fixture_artifact_root,
        _trust_registry_path=fixture_registry_path,
    )
    append_only_parent_protection = any(
        error.startswith("append_only_attempt_mutation:") for error in overwrite_errors
    )
    if not append_only_parent_protection:
        failures.append(f"parent overwrite accepted: {overwrite_errors[:3]}")
    missing_previous_errors = validate(
        valid,
        artifact_root=fixture_artifact_root,
        _trust_registry_path=fixture_registry_path,
    )
    previous_required = any(
        error.startswith("append_only_previous_required:") for error in missing_previous_errors
    )
    if not previous_required:
        failures.append(f"missing previous ledger accepted: {missing_previous_errors[:3]}")
    reset_attempt = copy.deepcopy(genesis)
    reset_attempt["attempts"][0]["prompt_artifact"]["prompt_text"] = "rewritten parent"
    reset_attempt["attempts"][0]["prompt_artifact"]["prompt_sha256"] = hashlib.sha256(
        b"rewritten parent"
    ).hexdigest()
    reset_attempt["genesis_sha256"] = genesis_sha256(reset_attempt)
    reset_errors = validate(
        reset_attempt,
        artifact_root=fixture_artifact_root,
        initial_ledger=True,
        _trust_registry_path=fixture_registry_path,
    )
    initial_reset_rejected = any(
        error.startswith("initial_ledger_shape_invalid:") for error in reset_errors
    )
    if not initial_reset_rejected:
        failures.append(f"non-genesis reset accepted: {reset_errors[:3]}")
    with tempfile.TemporaryDirectory(prefix="dircreative-ledger-") as temp_dir:
        temp_root = Path(temp_dir)
        artifact_root = temp_root / "artifacts"
        trust_root = temp_root / "trust"
        artifact_root.mkdir()
        trust_root.mkdir()
        advanced_genesis = copy.deepcopy(genesis)
        attempt = advanced_genesis["attempts"][0]
        attempt["authorized_execution_state"] = "authorized"
        attempt["source_status"] = "external_import"
        advanced_genesis["genesis_sha256"] = genesis_sha256(advanced_genesis)
        advanced = copy.deepcopy(advanced_genesis)
        attempt = advanced["attempts"][0]
        output_path = artifact_root / "outputs/attempt-001.png"
        output_path.parent.mkdir(parents=True)
        output_path.write_bytes(b"fixture output bytes\n")
        materialize_asset_bindings(advanced, artifact_root)
        attempt["output_manifest"] = [
            {
                "output_id": "OUTPUT-001",
                "relative_path": "outputs/attempt-001.png",
                "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
                "receipt_source": "external_verified",
                "receipt_id": "RECEIPT-GEN",
            }
        ]
        attempt["cost_credits"] = {
            "status": "verified",
            "amount": 4,
            "currency": "credits",
            "receipt_id": "RECEIPT-BILLING",
        }
        openssl = shutil.which("openssl")
        if openssl is None:
            raise RuntimeError("openssl is required for the signed-ledger self-test")
        authority_specs = [
            ("LEDGER-HOST-ADVANCED", "ledger_host", "ledger-host", ["ledger_genesis"], ["host_observation"]),
            ("MEDIA-HOST-001", "media_provider", "tapnow-host", ["execution", "generation"], ["host_observation", "external_verified"]),
            ("HUMAN-REVIEW-001", "human_reviewer", "reviewer-01", ["review"], ["independent_review"]),
            ("DELIVERY-HOST-001", "delivery_host", "delivery-host", ["delivery"], ["external_verified"]),
            ("BILLING-HOST-001", "billing_provider", "billing-host", ["billing"], ["external_verified"]),
        ]
        private_keys: dict[str, Path] = {}
        registry_entries: list[dict[str, Any]] = []
        for authority_id, authority_kind, actor_id, purposes, sources in authority_specs:
            private_key_path = trust_root / f"{authority_id.lower()}-private.pem"
            public_key_path = trust_root / f"{authority_id.lower()}-public.pem"
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
            private_keys[authority_id] = private_key_path
            registry_entries.append(
                {
                    "authority_id": authority_id,
                    "authority_kind": authority_kind,
                    "actor_id": actor_id,
                    "allowed_purposes": purposes,
                    "allowed_sources": sources,
                    "status": "active",
                    "public_key_relative_path": public_key_path.name,
                    "public_key_sha256": hashlib.sha256(public_key_path.read_bytes()).hexdigest(),
                }
            )
        trust_registry_path = trust_root / "review-trust-registry.json"
        trust_registry_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "authority": "host_configuration_only",
                    "review_authorities": registry_entries,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        advanced_genesis_relative = "receipts/ledger-genesis.json"
        advanced_genesis_signature_relative = "receipts/ledger-genesis.sig"
        advanced_genesis_path = artifact_root / advanced_genesis_relative
        advanced_genesis_signature_path = artifact_root / advanced_genesis_signature_relative
        advanced_genesis_path.parent.mkdir(parents=True, exist_ok=True)
        advanced_genesis_payload = {
            "receipt_id": "RECEIPT-GENESIS",
            "authority_id": "LEDGER-HOST-ADVANCED",
            "purpose": "ledger_genesis",
            "attempt_id": attempt["attempt_id"],
            "subject_sha256": advanced_genesis["genesis_sha256"],
            "observed_at": advanced_genesis["state_events"][0]["created_at"],
            "source": "host_observation",
            "actor": "ledger-host",
        }
        advanced_genesis_path.write_text(
            json.dumps(advanced_genesis_payload, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                openssl,
                "dgst",
                "-sha256",
                "-sign",
                str(private_keys["LEDGER-HOST-ADVANCED"]),
                "-out",
                str(advanced_genesis_signature_path),
                str(advanced_genesis_path),
            ],
            capture_output=True,
            check=True,
        )
        advanced_genesis_receipt = {
            **advanced_genesis_payload,
            "relative_path": advanced_genesis_relative,
            "signature_relative_path": advanced_genesis_signature_relative,
            "sha256": hashlib.sha256(advanced_genesis_path.read_bytes()).hexdigest(),
        }
        advanced_genesis["receipt_manifest"] = [advanced_genesis_receipt]
        advanced_genesis["state_events"][0]["evidence_source"] = "host_observation"
        advanced_genesis["state_events"][0]["evidence_refs"] = ["RECEIPT-GENESIS"]
        advanced_genesis["state_events"][0]["actor"] = "ledger-host"
        advanced["receipt_manifest"] = [copy.deepcopy(advanced_genesis_receipt)]
        advanced["state_events"][0] = copy.deepcopy(advanced_genesis["state_events"][0])
        output_subject_sha256 = generated_subject_sha256(attempt)
        candidate_subject_sha256 = generation_candidate_sha256(attempt)
        receipt_specs = [
            ("RECEIPT-EXEC", "MEDIA-HOST-001", "execution", "host_observation", "tapnow-host", "2026-08-24T00:00:02Z", candidate_subject_sha256),
            ("RECEIPT-GEN", "MEDIA-HOST-001", "generation", "external_verified", "tapnow-host", "2026-08-24T00:00:03Z", output_subject_sha256),
            ("RECEIPT-REVIEW", "HUMAN-REVIEW-001", "review", "independent_review", "reviewer-01", "2026-08-24T00:00:04Z", output_subject_sha256),
            ("RECEIPT-DELIVERY", "DELIVERY-HOST-001", "delivery", "external_verified", "delivery-host", "2026-08-24T00:00:05Z", output_subject_sha256),
            ("RECEIPT-BILLING", "BILLING-HOST-001", "billing", "external_verified", "billing-host", "2026-08-24T00:00:06Z", cost_subject_sha256(attempt)),
        ]
        advanced["receipt_manifest"] = [copy.deepcopy(advanced_genesis_receipt)]
        for receipt_id, authority_id, purpose, source, actor, observed_at, subject_sha256 in receipt_specs:
            relative = f"receipts/{receipt_id.lower()}.json"
            signature_relative = f"receipts/{receipt_id.lower()}.sig"
            path = artifact_root / relative
            signature_path = artifact_root / signature_relative
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "receipt_id": receipt_id,
                "authority_id": authority_id,
                "purpose": purpose,
                "attempt_id": attempt["attempt_id"],
                "subject_sha256": subject_sha256,
                "observed_at": observed_at,
                "source": source,
                "actor": actor,
            }
            path.write_text(
                json.dumps(payload, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            subprocess.run(
                [openssl, "dgst", "-sha256", "-sign", str(private_keys[authority_id]), "-out", str(signature_path), str(path)],
                capture_output=True,
                check=True,
            )
            advanced["receipt_manifest"].append(
                {
                    "receipt_id": receipt_id,
                    "authority_id": authority_id,
                    "purpose": purpose,
                    "attempt_id": attempt["attempt_id"],
                    "subject_sha256": subject_sha256,
                    "observed_at": observed_at,
                    "relative_path": relative,
                    "signature_relative_path": signature_relative,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source": source,
                    "actor": actor,
                }
            )
        review_receipt = next(
            item for item in advanced["receipt_manifest"] if item["receipt_id"] == "RECEIPT-REVIEW"
        )
        attempt["review_evidence"] = [
            {
                "review_id": "REVIEW-001",
                "verdict": "accept",
                "sha256": review_receipt["sha256"],
                "source": "independent_review",
                "receipt_id": "RECEIPT-REVIEW",
            }
        ]
        advanced["attempts"] = [attempt]
        advanced["state_events"] = [
            copy.deepcopy(advanced_genesis["state_events"][0]),
            {"event_id":"E2","attempt_id":"ATTEMPT-001","state":"attached","evidence_source":"producer","evidence_refs":[],"review_verdict":"not_applicable","created_at":"2026-08-24T00:00:01Z","actor":"dircreative"},
            {"event_id":"E3","attempt_id":"ATTEMPT-001","state":"executed","evidence_source":"host_observation","evidence_refs":["RECEIPT-EXEC"],"review_verdict":"not_applicable","created_at":"2026-08-24T00:00:02Z","actor":"tapnow-host"},
            {"event_id":"E4","attempt_id":"ATTEMPT-001","state":"generated_verified","evidence_source":"external_verified","evidence_refs":["RECEIPT-GEN"],"review_verdict":"not_applicable","created_at":"2026-08-24T00:00:03Z","actor":"tapnow-host"},
            {"event_id":"E5","attempt_id":"ATTEMPT-001","state":"selected","evidence_source":"independent_review","evidence_refs":["RECEIPT-REVIEW"],"review_verdict":"accept","created_at":"2026-08-24T00:00:04Z","actor":"reviewer-01"},
            {"event_id":"E6","attempt_id":"ATTEMPT-001","state":"delivered","evidence_source":"external_verified","evidence_refs":["RECEIPT-DELIVERY"],"review_verdict":"accept","created_at":"2026-08-24T00:00:05Z","actor":"delivery-host"}
        ]
        advanced_errors = validate(
            advanced,
            artifact_root=artifact_root,
            previous=advanced_genesis,
            _trust_registry_path=trust_registry_path,
        )
        advanced_lineage_positive = not advanced_errors
        verified_cost_positive = advanced_lineage_positive and any(
            receipt.get("purpose") == "billing"
            for receipt in advanced.get("receipt_manifest", [])
        )
        if advanced_errors:
            failures.append(f"valid verified lineage rejected: {advanced_errors[:3]}")
        untrusted_errors = validate(
            advanced,
            artifact_root=artifact_root,
            previous=advanced_genesis,
        )
        unconfigured_authority_rejected = any(
            error.startswith("review_authority_unconfigured:") for error in untrusted_errors
        )
        if not unconfigured_authority_rejected:
            failures.append(f"unconfigured receipt authority accepted: {untrusted_errors[:3]}")
        escalated = copy.deepcopy(advanced)
        next(
            receipt
            for receipt in escalated["receipt_manifest"]
            if receipt["receipt_id"] == "RECEIPT-DELIVERY"
        )["authority_id"] = "MEDIA-HOST-001"
        escalation_errors = validate(
            escalated,
            artifact_root=artifact_root,
            previous=advanced_genesis,
            _trust_registry_path=trust_registry_path,
        )
        authority_escalation_rejected = any(
            error.startswith("receipt_authority_scope_invalid:") for error in escalation_errors
        )
        if authority_escalation_rejected:
            rejected += 1
        else:
            failures.append(f"receipt authority escalation accepted: {escalation_errors[:3]}")
        actor_spoof = copy.deepcopy(advanced)
        actor_spoof["state_events"][2]["actor"] = "mallory"
        actor_errors = validate(
            actor_spoof,
            artifact_root=artifact_root,
            previous=advanced_genesis,
            _trust_registry_path=trust_registry_path,
        )
        actor_spoof_rejected = any(
            error.startswith("state_receipt_actor_mismatch:") for error in actor_errors
        )
        if actor_spoof_rejected:
            rejected += 1
        else:
            failures.append(f"state-event actor spoof accepted: {actor_errors[:3]}")
        secret_ledger = copy.deepcopy(advanced)
        execution_receipt = next(
            receipt
            for receipt in secret_ledger["receipt_manifest"]
            if receipt["receipt_id"] == "RECEIPT-EXEC"
        )
        execution_path = artifact_root / execution_receipt["relative_path"]
        execution_signature_path = artifact_root / execution_receipt["signature_relative_path"]
        secret_payload = json.loads(execution_path.read_text(encoding="utf-8"))
        secret_payload["Authorization"] = "Bearer fixture-secret-material"
        execution_path.write_text(json.dumps(secret_payload, sort_keys=True) + "\n", encoding="utf-8")
        subprocess.run(
            [
                openssl,
                "dgst",
                "-sha256",
                "-sign",
                str(private_keys["MEDIA-HOST-001"]),
                "-out",
                str(execution_signature_path),
                str(execution_path),
            ],
            capture_output=True,
            check=True,
        )
        execution_receipt["sha256"] = hashlib.sha256(execution_path.read_bytes()).hexdigest()
        secret_errors = validate(
            secret_ledger,
            artifact_root=artifact_root,
            previous=advanced_genesis,
            _trust_registry_path=trust_registry_path,
        )
        secret_receipt_rejected = any(
            error.startswith("receipt_payload_sensitive_value:") for error in secret_errors
        )
        if secret_receipt_rejected:
            rejected += 1
        else:
            failures.append(f"sensitive signed ledger receipt accepted: {secret_errors[:3]}")
    fixture_temp.cleanup()
    return failures, {
        "valid_fixture_passed": not valid_errors,
        "attempt_count": len(valid.get("attempts", [])),
        "negative_case_count": len(cases) + 3,
        "negative_cases_rejected": rejected,
        "append_only_positive": append_only_positive,
        "append_only_parent_protection": append_only_parent_protection,
        "previous_or_initial_required": previous_required,
        "initial_reset_rejected": initial_reset_rejected,
        "verified_lineage_positive": advanced_lineage_positive,
        "verified_cost_positive": verified_cost_positive,
        "unconfigured_authority_rejected": unconfigured_authority_rejected,
        "authority_escalation_rejected": authority_escalation_rejected,
        "actor_spoof_rejected": actor_spoof_rejected,
        "secret_receipt_rejected": secret_receipt_rejected,
        "media_generation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate append-only AI-film production ledgers.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    baseline = validate_parser.add_mutually_exclusive_group(required=True)
    baseline.add_argument("--previous", type=Path)
    baseline.add_argument("--initial-ledger", action="store_true")
    validate_parser.add_argument("--artifact-root", type=Path)
    args = parser.parse_args()
    if args.command == "self-test":
        failures, summary = self_test()
        print(json.dumps({**summary, "failures": failures}, ensure_ascii=False, indent=2, sort_keys=True))
        print(f"AI_FILM_PRODUCTION_LEDGER_AUDIT: {'PASS' if not failures else 'FAIL'}")
        return 0 if not failures else 1
    previous = load_json(args.previous) if args.previous else None
    errors = validate(
        load_json(args.path),
        previous=previous,
        artifact_root=args.artifact_root,
        initial_ledger=args.initial_ledger,
    )
    print(json.dumps({"path": str(args.path), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
