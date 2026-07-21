#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from dircreative_specialist_exchange_contract import (
    v2_handoff_schema_errors,
    v2_receipt_schema_errors,
)


ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR_PATH = ROOT / "docs/film-preproduction/schemas/adco-specialist-descriptor.json"


def root_skill_path() -> Path:
    source_layout = ROOT / "skills/dircreative/SKILL.md"
    if source_layout.is_file():
        return source_layout
    installed_layout = ROOT / "SKILL.md"
    if installed_layout.is_file():
        return installed_layout
    return source_layout


ROOT_SKILL = root_skill_path()
PROTOCOL_ID = "adco.specialist-exchange"
V1_CONTRACT_VERSION = "1.0"
V2_CONTRACT_VERSION = "2.0"
SUPPORTED_CONTRACT_VERSIONS = (V1_CONTRACT_VERSION, V2_CONTRACT_VERSION)
PROFILE_ID = "dircreative.film-preproduction"
PROVIDER_ID = "dircreative"
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
PROTECTED_PATH_ROOTS = {
    "AD-creative/orchestrator",
    "AD-creative/ppt/exports",
    "05_最终交付_FinalDelivery",
}
REQUIRED_FORBIDDEN_PATHS = {
    "AD-creative/orchestrator/current_truth.md",
    "AD-creative/orchestrator/version_map.csv",
    "AD-creative/orchestrator/artifact_index.csv",
    "AD-creative/orchestrator/gate_log.csv",
    "AD-creative/ppt/exports",
    "05_最终交付_FinalDelivery",
}
AUTHORITY_FIELDS = {
    "client_interaction",
    "artifact_adoption",
    "client_readiness",
    "final_export",
    "nested_dispatch",
}
RESERVED_CLAIMS = {
    "client_ready",
    "ppt_ready",
    "final_delivery_ready",
    "send_ready",
    "project_complete",
    "control_plane_updated",
}
DOMAIN_EXTENSION = {"id": "dircreative.domain-delivery", "version": "1.0"}
VERDICTS = {
    "domain_accepted",
    "draft_accepted_with_limitations",
    "needs_user",
    "needs_revision",
    "blocked",
}
V2_STATUSES = {"completed", "needs_user", "blocked", "failed"}
V2_HANDOFF_FIELDS = {
    "protocol_id",
    "contract_version",
    "task",
    "brief_snapshot",
    "locked_decisions",
    "requested_outputs",
    "quality_targets",
    "execution_mode",
}
V2_RECEIPT_FIELDS = {
    "protocol_id",
    "contract_version",
    "status",
    "outputs",
    "domain_qa",
    "open_questions",
}
V2_OUTPUT_FIELDS = {"output_id", "type", "path", "sha256"}
V2_QA_FIELDS = {"status", "checks", "limitations"}
V2_FORBIDDEN_CONTROL_FIELDS = {
    "current_truth",
    "goal",
    "versions",
    "user_confirmations",
    "client_readiness",
    "cleanup_state",
    "nested_dispatch",
    "claims",
    "client_ready",
    "ppt_ready",
    "final_delivery_ready",
    "send_ready",
    "project_complete",
    "adoption",
    "visibility",
    "completion",
}
ARTIFACT_IDS = {
    "film.story_package": "DIR-STORY-PACKAGE-001",
    "film.treatment": "DIR-TREATMENT-001",
    "film.script": "DIR-SCRIPT-001",
    "film.shot_plan": "DIR-SHOT-PLAN-001",
    "film.visual_bible": "DIR-VISUAL-BIBLE-001",
    "film.reference_prompt_plan": "DIR-REFERENCE-PROMPT-001",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid_json: {target}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_json_shape: {target} must contain an object")
    return payload


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def receipt_thread_ids(text: str) -> list[str]:
    values: list[str] = []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        direct = payload.get("thread_id")
        evidence = payload.get("execution_evidence")
        nested = evidence.get("thread_id") if isinstance(evidence, dict) else None
        for value in [direct, nested]:
            if isinstance(value, str) and value.strip():
                values.append(value.strip())
        if values:
            return list(dict.fromkeys(values))
    pattern = re.compile(
        r"(?im)^\s*(?:[-*]\s*)?(?:receipt\.)?(?:thread_id|real_thread_id)\s*[:=]\s*([^\s,;]+)\s*$"
    )
    return list(dict.fromkeys(match.group(1).strip() for match in pattern.finditer(text)))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_new_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Create one JSON file atomically without following or replacing a target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ValueError(f"receipt path already exists: {path}")
    casefold_matches = [
        item
        for item in path.parent.iterdir()
        if item.name.casefold() == path.name.casefold()
    ]
    if casefold_matches:
        raise ValueError(f"receipt path case alias already exists: {casefold_matches[0]}")

    temporary = path.parent / f".{path.name}.tmp-{uuid.uuid4().hex}"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd: int | None = None
    try:
        fd = os.open(temporary, flags, 0o600)
        data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with os.fdopen(fd, "wb", closefd=True) as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(path.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except FileExistsError as exc:
        raise ValueError(f"receipt path already exists: {path}") from exc
    finally:
        if fd is not None:
            os.close(fd)
        temporary.unlink(missing_ok=True)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_string_list(value: Any, *, allow_empty: bool = True) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(nonempty(item) for item in value)


def normalized_path(value: str) -> str:
    return str(Path(value.replace("\\", "/"))).replace("\\", "/").rstrip("/")


def has_parent_traversal(value: str) -> bool:
    return ".." in value.replace("\\", "/").split("/")


def path_has_symlink_component(project_root: Path, value: str) -> bool:
    if not nonempty(value) or Path(value).is_absolute() or has_parent_traversal(value):
        return False
    current = project_root.resolve()
    for part in Path(value.replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        current = current / part
        if current.is_symlink():
            return True
    return False


def scopes_overlap(left: str, right: str) -> bool:
    # Treat case aliases as the same scope. This is conservative on case-sensitive
    # filesystems and closes a real overlap bypass on default macOS volumes.
    left_normalized = normalized_path(left).casefold()
    right_normalized = normalized_path(right).casefold()
    return (
        left_normalized == right_normalized
        or left_normalized.startswith(right_normalized + "/")
        or right_normalized.startswith(left_normalized + "/")
    )


def protected_scope_overlap(value: str) -> bool:
    normalized = normalized_path(value).casefold()
    return any(scopes_overlap(normalized, normalized_path(root).casefold()) for root in PROTECTED_PATH_ROOTS)


def path_in_scopes(value: str, scopes: list[str]) -> bool:
    normalized = normalized_path(value).casefold()
    return any(
        normalized == normalized_path(scope).casefold()
        or normalized.startswith(normalized_path(scope).casefold() + "/")
        for scope in scopes
    )


def relative_path_is_within(relative_path: str, root: str) -> bool:
    path_parts = tuple(part.casefold() for part in Path(relative_path).parts)
    root_parts = tuple(part.casefold() for part in Path(root.rstrip("/")).parts)
    return len(path_parts) >= len(root_parts) and path_parts[: len(root_parts)] == root_parts


def specialist_scope_manifest(project_root: Path, excluded_roots: list[str]) -> dict[str, str]:
    roots = [root.strip().rstrip("/") for root in excluded_roots if root.strip()]
    files: dict[str, str] = {}
    for path in sorted(project_root.rglob("*")):
        relative = path.relative_to(project_root).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            continue
        if any(relative_path_is_within(relative, root) for root in roots):
            continue
        if path.is_symlink():
            files[relative] = "symlink:" + str(path.readlink())
        elif path.is_file():
            files[relative] = sha256(path)
    return files


def manifest_digest(files: dict[str, str]) -> str:
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def project_path(project_root: Path, value: Any, label: str) -> Path | None:
    if not nonempty(value) or Path(str(value)).is_absolute() or has_parent_traversal(str(value)):
        return None
    root = project_root.resolve()
    candidate = (root / str(value)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def v2_exchange_registration(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path | None,
    descriptor: dict[str, Any],
) -> tuple[dict[str, str] | None, list[str]]:
    """Bind a compact v2 handoff to ADCO's host-owned exchange ledger."""
    failures: list[str] = []
    root = project_root.resolve()
    if handoff_path is None:
        return None, [failure("missing_handoff_registration", "v2 handoff path is required")]
    try:
        handoff_relative = handoff_path.resolve().relative_to(root).as_posix()
    except ValueError:
        return None, [failure("handoff_identity_mismatch", "handoff path escapes project")]
    if (
        path_has_symlink_component(root, handoff_relative)
        or not handoff_path.is_file()
        or handoff_path.stat().st_size == 0
        or handoff_path.stat().st_nlink != 1
    ):
        return None, [failure("handoff_identity_mismatch", "handoff must be one regular project file")]
    try:
        persisted = load_json(handoff_path)
    except ValueError as exc:
        return None, [failure("handoff_identity_mismatch", str(exc))]
    if persisted != handoff:
        failures.append(failure("handoff_identity_mismatch", "handoff file differs from validation input"))

    index_relative = "AD-creative/orchestrator/specialist_exchange/exchange_index.csv"
    index_path = root / index_relative
    if (
        path_has_symlink_component(root, index_relative)
        or not index_path.is_file()
        or index_path.stat().st_nlink != 1
    ):
        return None, [*failures, failure("missing_handoff_registration", "ADCO exchange index is unavailable")]
    rows = [
        row
        for row in read_csv_dicts(index_path)
        if normalized_path(row.get("handoff_path", "")) == normalized_path(handoff_relative)
    ]
    if len(rows) != 1:
        return None, [
            *failures,
            failure("missing_handoff_registration", f"expected one ADCO exchange row, found {len(rows)}"),
        ]
    row = rows[0]
    expected_descriptor_hash = canonical_descriptor_hash(descriptor)
    expected = {
        "provider_id": PROVIDER_ID,
        "profile_id": PROFILE_ID,
        "contract_version": V2_CONTRACT_VERSION,
        "compatibility_status": "compatible",
        "handoff_sha256": sha256(handoff_path),
        "descriptor_sha256": expected_descriptor_hash,
    }
    for field, expected_value in expected.items():
        if row.get(field) != expected_value:
            failures.append(failure("handoff_registration_mismatch", field))

    descriptor_relative = (
        "AD-creative/orchestrator/specialist_exchange/descriptors/"
        f"descriptor_{expected_descriptor_hash}.json"
    )
    descriptor_snapshot = root / descriptor_relative
    if (
        path_has_symlink_component(root, descriptor_relative)
        or not descriptor_snapshot.is_file()
        or descriptor_snapshot.stat().st_nlink != 1
    ):
        failures.append(failure("descriptor_snapshot_mismatch", "registered descriptor snapshot is unavailable"))
    else:
        try:
            if load_json(descriptor_snapshot) != descriptor:
                failures.append(failure("descriptor_snapshot_mismatch", "snapshot content differs"))
        except ValueError as exc:
            failures.append(failure("descriptor_snapshot_mismatch", str(exc)))

    receipt_value = row.get("receipt_path", "")
    receipt_path = project_path(root, receipt_value, "receipt")
    requested = handoff.get("requested_outputs")
    requested_items = requested if isinstance(requested, list) else []
    output_parents = {
        normalized_path(str(Path(str(item.get("path_root", ""))).parent))
        for item in requested_items
        if isinstance(item, dict) and nonempty(item.get("path_root"))
    }
    receipt_parent = normalized_path(str(Path(receipt_value).parent)) if nonempty(receipt_value) else ""
    if (
        receipt_path is None
        or path_has_symlink_component(root, receipt_value)
        or protected_scope_overlap(receipt_value)
        or len(output_parents) != 1
        or receipt_parent not in output_parents
    ):
        failures.append(failure("invalid_registered_receipt_path", receipt_value or "missing"))
    return row, failures


def register_v2_fixture_handoff(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path,
    descriptor: dict[str, Any],
    *,
    receipt_path: str,
) -> None:
    """Create only the host identity records needed by isolated v2 tests."""
    root = project_root.resolve()
    relative = handoff_path.resolve().relative_to(root).as_posix()
    descriptor_hash = canonical_descriptor_hash(descriptor)
    snapshot = (
        root
        / "AD-creative/orchestrator/specialist_exchange/descriptors"
        / f"descriptor_{descriptor_hash}.json"
    )
    write_json(snapshot, descriptor)
    index = root / "AD-creative/orchestrator/specialist_exchange/exchange_index.csv"
    index.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "provider_id",
        "profile_id",
        "contract_version",
        "descriptor_sha256",
        "handoff_sha256",
        "compatibility_status",
        "handoff_path",
        "receipt_path",
    ]
    write_header = not index.exists() or index.stat().st_size == 0
    with index.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "provider_id": PROVIDER_ID,
                "profile_id": PROFILE_ID,
                "contract_version": V2_CONTRACT_VERSION,
                "descriptor_sha256": descriptor_hash,
                "handoff_sha256": sha256(handoff_path),
                "compatibility_status": "compatible",
                "handoff_path": relative,
                "receipt_path": receipt_path,
            }
        )


def canonical_descriptor_hash(descriptor: dict[str, Any]) -> str:
    canonical = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def failure(code: str, detail: str) -> str:
    return f"{code}: {detail}"


def failure_ids(failures: list[str]) -> set[str]:
    return {item.split(":", 1)[0] for item in failures}


def descriptor_profile(descriptor: dict[str, Any]) -> dict[str, Any]:
    profiles = descriptor.get("profiles")
    if not isinstance(profiles, list):
        return {}
    return next(
        (
            item
            for item in profiles
            if isinstance(item, dict) and item.get("profile_id") == PROFILE_ID
        ),
        {},
    )


def validate_descriptor(descriptor: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if descriptor.get("protocol_id") != PROTOCOL_ID:
        failures.append(failure("invalid_protocol", "descriptor protocol_id mismatch"))
    if descriptor.get("message_type") != "descriptor":
        failures.append(failure("invalid_message_type", "descriptor message_type mismatch"))
    if descriptor.get("descriptor_version") != V1_CONTRACT_VERSION:
        failures.append(failure("unsupported_descriptor_version", "descriptor_version must be 1.0"))
    if descriptor.get("supported_contract_versions") != list(SUPPORTED_CONTRACT_VERSIONS):
        failures.append(
            failure(
                "unsupported_contract_version",
                "descriptor must support contract versions 1.0 and 2.0 in order",
            )
        )
    provider = descriptor.get("provider")
    if not isinstance(provider, dict) or provider.get("id") != PROVIDER_ID or not nonempty(provider.get("display_name")):
        failures.append(failure("invalid_provider", "descriptor provider must identify DIRcreative"))
        provider = {}
    declared_path = provider.get("skill_path")
    if declared_path != "skills/dircreative/SKILL.md" or not ROOT_SKILL.is_file():
        failures.append(failure("invalid_skill_identity", "descriptor skill_path must identify the loaded root skill"))
    if provider.get("skill_sha256") != sha256(ROOT_SKILL):
        failures.append(failure("invalid_skill_identity", "descriptor skill_sha256 is stale"))
    profile = descriptor_profile(descriptor)
    if not profile:
        failures.append(failure("missing_profile", f"descriptor lacks {PROFILE_ID}"))
        return failures
    capabilities = profile.get("capabilities")
    execution_modes = profile.get("execution_modes")
    workspace_modes = profile.get("workspace_modes")
    if not valid_string_list(capabilities, allow_empty=False) or "film.story_package" not in capabilities:
        failures.append(failure("invalid_profile_capabilities", "profile must provide film.story_package"))
    if not valid_string_list(execution_modes, allow_empty=False) or set(execution_modes) != {
        "inline",
        "codex_thread",
        "external_handoff",
    }:
        failures.append(failure("invalid_execution_modes", "descriptor execution modes drifted"))
    if not valid_string_list(workspace_modes, allow_empty=False) or set(workspace_modes) != {
        "isolated_workspace",
        "worktree",
        "read_only",
    }:
        failures.append(failure("invalid_workspace_modes", "descriptor workspace modes drifted"))
    authority = profile.get("authority")
    if not isinstance(authority, dict):
        failures.append(failure("authority_escalation", "profile authority is missing"))
    else:
        for field in AUTHORITY_FIELDS:
            if authority.get(field) is not False:
                failures.append(failure("authority_escalation", f"descriptor authority.{field} must be false"))
    receipt_extension = profile.get("receipt_extension")
    if not isinstance(receipt_extension, dict) or any(
        receipt_extension.get(key) != value for key, value in DOMAIN_EXTENSION.items()
    ) or receipt_extension.get("required") is not True:
        failures.append(
            failure(
                "invalid_receipt_extension",
                "DIR domain-delivery receipt extension must be required at version 1.0",
            )
        )
    v2_contract = profile.get("v2_contract")
    expected_v2_contract = {
        "execution_mode": "inline",
        "nested_dispatch": False,
        "receipt_shape": "domain_outputs_and_qa_only",
        "handoff_schema": "docs/film-preproduction/schemas/adco-specialist-handoff-v2.schema.json",
        "receipt_schema": "docs/film-preproduction/schemas/adco-specialist-receipt-v2.schema.json",
    }
    if v2_contract != expected_v2_contract:
        failures.append(failure("invalid_v2_contract", "descriptor v2 contract declaration drifted"))
    return failures


def validate_thread_proof(project_root: Path, handoff: dict[str, Any]) -> list[str]:
    execution = handoff.get("execution")
    if not isinstance(execution, dict) or execution.get("mode") != "codex_thread":
        return []
    failures: list[str] = []
    registry_path = project_root / "AD-creative/orchestrator/thread_registry.csv"
    rows = read_csv_dicts(registry_path)
    lane_id = str(execution.get("lane_id") or "")
    work_id = str(handoff.get("work_id") or "")
    matches = [row for row in rows if row.get("lane_id") == lane_id and row.get("work_id") == work_id]
    if len(matches) != 1:
        return [failure("invalid_worker_thread_id", "ThreadOps registry proof is missing or ambiguous")]
    row = matches[0]
    thread_id = str(execution.get("thread_id") or "")
    valid_ids = {value for value in [row.get("real_thread_id", ""), row.get("rescue_thread_id", "")] if value}
    if thread_id not in valid_ids:
        failures.append(failure("invalid_worker_thread_id", "handoff thread id is not the registered worker"))
    if execution.get("workspace_mode") != "isolated_workspace":
        failures.append(failure("invalid_worker_thread_id", "codex_thread requires isolated_workspace"))
    if execution.get("lane_run_id") != row.get("lane_run_id") or row.get("lane_run_id") != f"{work_id}:{lane_id}":
        failures.append(failure("invalid_worker_thread_id", "lane_run_id is not bound to work and lane"))
    if row.get("dispatch_status", "").strip().lower() not in {"dispatched", "running"}:
        failures.append(failure("invalid_worker_thread_id", "ThreadOps dispatch is not active"))
    if row.get("mode", "").strip() != "execution_worker" or row.get("environment", "").strip() != "isolated_workspace":
        failures.append(failure("invalid_worker_thread_id", "ThreadOps lane class or environment is invalid"))
    dispatch_ref = row.get("dispatch_receipt_path", "").strip()
    if thread_id and thread_id == row.get("rescue_thread_id", "").strip():
        dispatch_ref = row.get("rescue_dispatch_receipt_path", "").strip()
    dispatch_path = project_path(project_root, dispatch_ref, "ThreadOps dispatch receipt")
    if path_has_symlink_component(project_root, dispatch_ref):
        failures.append(failure("invalid_worker_thread_id", "ThreadOps dispatch receipt uses a symlink"))
    elif dispatch_path is None or not dispatch_path.is_file():
        failures.append(failure("invalid_worker_thread_id", "ThreadOps dispatch receipt is missing"))
    elif receipt_thread_ids(dispatch_path.read_text(encoding="utf-8", errors="ignore")) != [thread_id]:
        failures.append(failure("invalid_worker_thread_id", "ThreadOps dispatch receipt identity mismatch"))
    return failures


def validate_v1_handoff(
    project_root: Path,
    handoff: dict[str, Any],
    descriptor: dict[str, Any],
) -> list[str]:
    failures = validate_descriptor(descriptor)
    if handoff.get("protocol_id") != PROTOCOL_ID:
        failures.append(failure("invalid_protocol", "handoff protocol_id mismatch"))
    if handoff.get("contract_version") != V1_CONTRACT_VERSION:
        failures.append(failure("unsupported_contract_version", "handoff contract_version must be 1.0"))
    if handoff.get("message_type") != "handoff":
        failures.append(failure("invalid_message_type", "handoff message_type mismatch"))
    for field in ["exchange_id", "handoff_id", "work_id", "provider_id", "profile_id"]:
        if not nonempty(handoff.get(field)):
            failures.append(failure("missing_handoff_identity", f"handoff.{field} is required"))
    if handoff.get("provider_id") != PROVIDER_ID:
        failures.append(failure("invalid_provider", "handoff provider_id must identify DIRcreative"))
    if handoff.get("profile_id") != PROFILE_ID:
        failures.append(failure("invalid_profile", f"handoff profile must be {PROFILE_ID}"))
    attempt = handoff.get("attempt")
    if not isinstance(attempt, int) or attempt not in {1, 2}:
        failures.append(failure("invalid_attempt", "handoff attempt must be 1 or 2"))

    descriptor_ref = handoff.get("descriptor_ref")
    expected_descriptor_hash = canonical_descriptor_hash(descriptor)
    if (
        not isinstance(descriptor_ref, dict)
        or descriptor_ref.get("provider_id") != PROVIDER_ID
        or descriptor_ref.get("sha256") != expected_descriptor_hash
    ):
        failures.append(failure("unverified_descriptor", "handoff descriptor_ref does not bind the DIR descriptor"))

    profile = descriptor_profile(descriptor)
    profile_capabilities = set(profile.get("capabilities", [])) if profile else set()
    task = handoff.get("task")
    if not isinstance(task, dict):
        failures.append(failure("invalid_task", "handoff task must be an object"))
        task = {}
    if not nonempty(task.get("objective")):
        failures.append(failure("invalid_task", "handoff task objective is required"))
    required_capabilities = task.get("required_capabilities")
    expected_output_kinds = task.get("expected_output_kinds")
    if not valid_string_list(required_capabilities):
        failures.append(failure("invalid_task", "required_capabilities must contain strings"))
        required_capabilities = []
    if not valid_string_list(expected_output_kinds, allow_empty=False):
        failures.append(failure("invalid_task", "expected_output_kinds must contain strings"))
        expected_output_kinds = []
    if len(expected_output_kinds) != len(set(expected_output_kinds)):
        failures.append(failure("duplicate_output_kind", "expected output kinds must be unique"))
    missing_capabilities = set(required_capabilities) - profile_capabilities
    unsupported_outputs = set(expected_output_kinds) - profile_capabilities
    if missing_capabilities or unsupported_outputs:
        failures.append(
            failure(
                "missing_profile_capability",
                ",".join(sorted(missing_capabilities | unsupported_outputs)),
            )
        )

    source_truth = handoff.get("source_truth")
    artifacts = source_truth.get("artifacts") if isinstance(source_truth, dict) else None
    if not isinstance(artifacts, list) or not artifacts:
        failures.append(failure("missing_source_truth", "source_truth.artifacts cannot be empty"))
        artifacts = []
    source_paths: list[str] = []
    source_ids: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            failures.append(failure("invalid_source_artifact", "source artifact entries must be objects"))
            continue
        artifact_id = item.get("artifact_id")
        path_value = item.get("path")
        digest = item.get("sha256")
        if not nonempty(artifact_id) or artifact_id in source_ids:
            failures.append(failure("invalid_source_artifact", "source artifact ids must be non-empty and unique"))
        else:
            source_ids.add(artifact_id)
        if not nonempty(path_value) or not nonempty(item.get("version")) or not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
            failures.append(failure("invalid_source_artifact", f"source artifact is incomplete: {artifact_id}"))
            continue
        source_paths.append(path_value)
        source_path = project_path(project_root, path_value, "source artifact")
        if path_has_symlink_component(project_root, path_value):
            failures.append(failure("invalid_source_artifact", f"source artifact uses a symlink: {path_value}"))
        elif source_path is None:
            failures.append(failure("path_escape", f"source artifact escapes project: {path_value}"))
        elif not source_path.is_file():
            failures.append(failure("missing_source_artifact", f"source artifact does not exist: {path_value}"))
        elif source_path.stat().st_size == 0 or source_path.stat().st_nlink != 1:
            failures.append(failure("invalid_source_artifact", f"source artifact must be non-empty and not hardlinked: {path_value}"))
        elif sha256(source_path) != digest:
            failures.append(failure("stale_input_artifact", str(artifact_id)))

    execution = handoff.get("execution")
    if not isinstance(execution, dict):
        failures.append(failure("invalid_execution", "handoff execution must be an object"))
        execution = {}
    mode = execution.get("mode")
    workspace_mode = execution.get("workspace_mode")
    if mode not in profile.get("execution_modes", []):
        failures.append(failure("invalid_execution", f"unsupported execution mode: {mode}"))
    if workspace_mode not in profile.get("workspace_modes", []):
        failures.append(failure("invalid_execution", f"unsupported workspace mode: {workspace_mode}"))
    if execution.get("nested_dispatch_allowed") is not False:
        failures.append(failure("nested_dispatch_forbidden", "native v1 forbids nested dispatch"))
    thread_id = execution.get("thread_id")
    if mode == "codex_thread":
        if not isinstance(thread_id, str) or not UUID_RE.fullmatch(thread_id):
            failures.append(failure("invalid_worker_thread_id", "codex_thread requires a real worker UUID"))
        if not nonempty(execution.get("lane_id")):
            failures.append(failure("invalid_worker_thread_id", "codex_thread requires lane_id"))
        failures.extend(validate_thread_proof(project_root, handoff))
    elif thread_id not in {None, ""}:
        failures.append(failure("invalid_worker_thread_id", "non-thread handoff cannot claim a thread id"))

    scope = handoff.get("scope")
    if not isinstance(scope, dict):
        failures.append(failure("invalid_scope", "handoff scope must be an object"))
        scope = {}
    read_scope = scope.get("read")
    write_scope = scope.get("write")
    forbidden = scope.get("forbidden")
    receipt_path = scope.get("receipt_path")
    for field, value, allow_empty in [
        ("read", read_scope, False),
        ("write", write_scope, False),
        ("forbidden", forbidden, False),
    ]:
        if not valid_string_list(value, allow_empty=allow_empty):
            failures.append(failure("invalid_scope", f"scope.{field} must contain non-empty strings"))
    read_scope = read_scope if isinstance(read_scope, list) else []
    write_scope = write_scope if isinstance(write_scope, list) else []
    forbidden = forbidden if isinstance(forbidden, list) else []
    if not nonempty(receipt_path) or receipt_path not in write_scope:
        failures.append(failure("invalid_scope", "scope.receipt_path must be an exact writable path"))
    host_baseline = scope.get("host_baseline")
    if not isinstance(host_baseline, dict):
        failures.append(failure("missing_host_baseline", "scope.host_baseline is required"))
    else:
        baseline_path = host_baseline.get("path")
        baseline_file = project_path(project_root, baseline_path, "host baseline")
        if nonempty(baseline_path) and path_has_symlink_component(project_root, baseline_path):
            failures.append(failure("invalid_host_baseline", "host baseline path uses a symlink"))
        elif baseline_file is None:
            failures.append(failure("invalid_host_baseline", "host baseline path must stay inside the project"))
        for field in ["sha256", "manifest_sha256"]:
            value = host_baseline.get(field)
            if not isinstance(value, str) or not SHA_RE.fullmatch(value):
                failures.append(failure("invalid_host_baseline", f"host baseline {field} is invalid"))
        if baseline_file is not None:
            if not baseline_file.is_file() or baseline_file.stat().st_nlink != 1:
                failures.append(failure("invalid_host_baseline", "host baseline file is missing or hardlinked"))
            elif sha256(baseline_file) != host_baseline.get("sha256"):
                failures.append(failure("invalid_host_baseline", "host baseline file hash mismatch"))
            else:
                try:
                    baseline_payload = load_json(baseline_file)
                except ValueError as exc:
                    failures.append(failure("invalid_host_baseline", str(exc)))
                else:
                    baseline_files = baseline_payload.get("files")
                    baseline_exclusions = baseline_payload.get("excluded_roots")
                    manifest_sha = hashlib.sha256(
                        json.dumps(baseline_files, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    ).hexdigest() if isinstance(baseline_files, dict) else None
                    required_exclusions = {
                        "AD-creative/orchestrator/specialist_exchange",
                        *[normalized_path(item) for item in write_scope],
                    }
                    if (
                        baseline_payload.get("protocol_id") != PROTOCOL_ID
                        or baseline_payload.get("contract_version") != V1_CONTRACT_VERSION
                        or baseline_payload.get("message_type") != "host_scope_baseline"
                        or baseline_payload.get("handoff_id") != handoff.get("handoff_id")
                        or baseline_payload.get("manifest_sha256") != host_baseline.get("manifest_sha256")
                        or manifest_sha != host_baseline.get("manifest_sha256")
                        or not valid_string_list(baseline_exclusions, allow_empty=False)
                        or not required_exclusions.issubset(
                            {normalized_path(item) for item in baseline_exclusions}
                        )
                    ):
                        failures.append(failure("invalid_host_baseline", "host baseline content or manifest mismatch"))
    normalized_forbidden = {normalized_path(item) for item in forbidden if isinstance(item, str)}
    if not REQUIRED_FORBIDDEN_PATHS.issubset(normalized_forbidden):
        failures.append(failure("missing_protected_scope", "handoff omits canonical protected paths"))
    for source_path in source_paths:
        if source_path not in read_scope:
            failures.append(failure("source_outside_read_scope", source_path))
    for value in read_scope + write_scope + forbidden:
        if project_path(project_root, value, "scope") is None:
            failures.append(failure("path_escape", f"invalid project-relative scope: {value}"))
    for value in read_scope + write_scope:
        if path_has_symlink_component(project_root, value):
            failures.append(failure("symlink_scope", f"scope uses a symlink component: {value}"))
    output_roots = [item for item in write_scope if item != receipt_path]
    if workspace_mode == "read_only" and output_roots:
        failures.append(failure("read_only_write_scope", "read_only handoff cannot grant output roots"))
    if workspace_mode != "read_only" and not output_roots:
        failures.append(failure("missing_output_scope", "writable handoff requires an output root"))
    for writable in write_scope:
        if protected_scope_overlap(writable):
            failures.append(failure("protected_scope_write", f"write overlaps protected path: {writable}"))

    acceptance = handoff.get("acceptance")
    if not isinstance(acceptance, dict):
        failures.append(failure("authority_escalation", "handoff acceptance is missing"))
    else:
        if acceptance.get("visibility") != "internal_only" or acceptance.get("provider_recommendation_only") is not True:
            failures.append(failure("authority_escalation", "provider output must remain internal and recommendation-only"))
        if not valid_string_list(acceptance.get("stop_on"), allow_empty=False) or not {
            "needs_user",
            "blocked",
            "failed",
        }.issubset(set(acceptance.get("stop_on", []))):
            failures.append(failure("invalid_acceptance", "handoff stop_on contract is incomplete"))
        required_extensions = acceptance.get("required_receipt_extensions")
        if required_extensions != [DOMAIN_EXTENSION]:
            failures.append(
                failure(
                    "invalid_receipt_extension",
                    "handoff must negotiate the required DIR domain-delivery extension",
                )
            )

    authorization = handoff.get("authorization")
    if not isinstance(authorization, dict):
        failures.append(failure("invalid_authorization", "handoff authorization is missing"))
    else:
        generation_mode = authorization.get("generation_mode")
        authorized = authorization.get("authorized")
        authorization_ref = authorization.get("authorization_ref")
        if authorization.get("external_upload") is not False:
            failures.append(failure("authority_escalation", "external upload must remain false"))
        if generation_mode != "prompt_only":
            failures.append(
                failure(
                    "unsupported_generation_mode",
                    "dircreative.film-preproduction v1 is prompt-only; real media needs a separately negotiated profile",
                )
            )
        if authorized is not False or authorization_ref not in {None, ""}:
            failures.append(
                failure(
                    "invalid_authorization",
                    "prompt-only handoff must not claim generation authorization or an authorization reference",
                )
            )
    return failures


def verdict_contract(verdict: str) -> tuple[str, str, str]:
    if verdict == "domain_accepted":
        return "completed", "pass", "adopt_for_adco_gate"
    if verdict == "draft_accepted_with_limitations":
        return "completed", "pass", "partial_adopt_internal"
    if verdict == "needs_user":
        return "needs_user", "needs_user", "return_questions_to_adco"
    if verdict == "needs_revision":
        return "failed", "fail", "reject_for_revision"
    return "blocked", "blocked", "defer_blocked"


def build_v1_receipt(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path,
    artifact_paths: dict[str, str],
    *,
    verdict: str,
    limitations: list[str] | None = None,
    open_questions: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], Path]:
    if verdict not in VERDICTS:
        raise ValueError(f"invalid domain verdict: {verdict}")
    limitations = limitations or []
    open_questions = open_questions or []
    outcome, qa_status, recommendation = verdict_contract(verdict)
    source_truth = handoff["source_truth"]
    execution = handoff["execution"]
    if project_path(project_root, str(handoff_path.relative_to(project_root)), "handoff") != handoff_path.resolve():
        raise ValueError("handoff path escapes project")
    if not handoff_path.is_file() or load_json(handoff_path) != handoff:
        raise ValueError("handoff file does not match the validated handoff")
    outputs: list[dict[str, Any]] = []
    for kind, value in artifact_paths.items():
        if path_has_symlink_component(project_root, value):
            raise ValueError(f"output artifact uses a symlink: {value}")
        path = project_path(project_root, value, "output artifact")
        if path is None or not path.is_file():
            raise ValueError(f"output artifact missing or out of project: {value}")
        outputs.append(
            {
                "provider_artifact_id": ARTIFACT_IDS.get(kind, "DIR-" + re.sub(r"[^A-Z0-9]+", "-", kind.upper()).strip("-")),
                "kind": kind,
                "version": "1",
                "path": value,
                "sha256": sha256(path),
                "visibility": "internal_only",
                "source_input_ids": [item["artifact_id"] for item in source_truth["artifacts"]],
            }
        )
    domain_delivery = {
        "contract_id": "dircreative.domain-delivery/1.0",
        "domain_verdict": verdict,
        "discussion_ready": verdict in {"domain_accepted", "draft_accepted_with_limitations"},
        "specialist_handoff_ready": verdict in {"domain_accepted", "draft_accepted_with_limitations"},
        "generation_ready": False,
        "client_ready": False,
        "final_export_allowed": False,
        "hard_blockers": limitations if verdict in {"draft_accepted_with_limitations", "blocked"} else [],
    }
    required_extensions = handoff.get("acceptance", {}).get("required_receipt_extensions", [])
    extensions = [
        {
            "id": item["id"],
            "version": item["version"],
            "payload": domain_delivery if item == DOMAIN_EXTENSION else {},
        }
        for item in required_extensions
    ]
    receipt: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID,
        "contract_version": V1_CONTRACT_VERSION,
        "message_type": "receipt",
        "receipt_id": "SPR-" + str(uuid.uuid4()),
        "exchange_id": handoff["exchange_id"],
        "handoff_id": handoff["handoff_id"],
        "work_id": handoff["work_id"],
        "provider_id": PROVIDER_ID,
        "profile_id": PROFILE_ID,
        "descriptor_sha256": handoff["descriptor_ref"]["sha256"],
        "handoff_sha256": sha256(handoff_path),
        "outcome": outcome,
        "stage_gate": {"type": "film_preproduction", "status": qa_status, "decision_owner": "worker"},
        "consumed_inputs": [
            {"artifact_id": item["artifact_id"], "version": item["version"], "sha256": item["sha256"]}
            for item in source_truth["artifacts"]
        ],
        "output_artifacts": outputs,
        "qa": {"status": qa_status, "checks": ["dircreative_domain_qa"], "limitations": limitations},
        "open_questions": open_questions,
        "specialist_recommendation": recommendation,
        "execution_evidence": {
            "mode": execution["mode"],
            "thread_id": execution.get("thread_id") if execution["mode"] == "codex_thread" else None,
            "nested_dispatch_used": False,
            "out_of_scope_writes": [],
        },
        "claims": {field: False for field in sorted(RESERVED_CLAIMS)},
        "extensions": extensions,
        "domain_delivery": domain_delivery,
    }
    receipt_path = project_path(project_root, handoff["scope"]["receipt_path"], "receipt")
    if receipt_path is None:
        raise ValueError("receipt path escapes project")
    write_json(receipt_path, receipt)
    return receipt, receipt_path


def validate_v1_receipt(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path,
    receipt: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    for key, expected in [
        ("protocol_id", PROTOCOL_ID),
        ("contract_version", V1_CONTRACT_VERSION),
        ("message_type", "receipt"),
        ("exchange_id", handoff.get("exchange_id")),
        ("handoff_id", handoff.get("handoff_id")),
        ("work_id", handoff.get("work_id")),
        ("provider_id", PROVIDER_ID),
        ("profile_id", PROFILE_ID),
    ]:
        if receipt.get(key) != expected:
            failures.append(failure("receipt_identity_mismatch", key))
    if not nonempty(receipt.get("receipt_id")):
        failures.append(failure("receipt_identity_mismatch", "receipt_id is required"))
    descriptor_ref = handoff.get("descriptor_ref")
    expected_descriptor_sha = descriptor_ref.get("sha256") if isinstance(descriptor_ref, dict) else None
    if receipt.get("descriptor_sha256") != expected_descriptor_sha:
        failures.append(failure("receipt_identity_mismatch", "descriptor_sha256"))
    if not handoff_path.is_file() or receipt.get("handoff_sha256") != sha256(handoff_path):
        failures.append(failure("receipt_identity_mismatch", "handoff_sha256"))
    claims = receipt.get("claims")
    if not isinstance(claims, dict) or set(claims) != RESERVED_CLAIMS or any(
        claims.get(field) is not False for field in RESERVED_CLAIMS
    ):
        failures.append(failure("authority_escalation", "provider readiness claims must all be false"))
    execution = handoff.get("execution", {})
    evidence = receipt.get("execution_evidence")
    if not isinstance(evidence, dict):
        failures.append(failure("invalid_execution_evidence", "execution_evidence is missing"))
        evidence = {}
    if evidence.get("mode") != execution.get("mode"):
        failures.append(failure("invalid_execution_evidence", "execution mode mismatch"))
    if evidence.get("nested_dispatch_used") is not False:
        failures.append(failure("nested_dispatch_forbidden", "receipt claims nested dispatch"))
    if evidence.get("out_of_scope_writes") != []:
        failures.append(failure("out_of_scope_write", "receipt reports out-of-scope writes"))
    if execution.get("mode") == "codex_thread":
        if evidence.get("thread_id") != execution.get("thread_id"):
            failures.append(failure("invalid_worker_thread_id", "receipt thread id mismatch"))
    elif evidence.get("thread_id") not in {None, ""}:
        failures.append(failure("invalid_worker_thread_id", "non-thread receipt claims thread id"))

    source_artifacts = handoff.get("source_truth", {}).get("artifacts", [])
    expected_consumed = {
        (item.get("artifact_id"), item.get("version"), item.get("sha256")) for item in source_artifacts
    }
    consumed = receipt.get("consumed_inputs")
    actual_consumed = {
        (item.get("artifact_id"), item.get("version"), item.get("sha256"))
        for item in consumed
        if isinstance(item, dict)
    } if isinstance(consumed, list) else set()
    if actual_consumed != expected_consumed:
        failures.append(failure("stale_input_artifact", "receipt consumed_inputs do not match handoff"))

    task = handoff.get("task", {})
    expected_kinds = set(task.get("expected_output_kinds", []))
    outputs = receipt.get("output_artifacts")
    if not isinstance(outputs, list):
        failures.append(failure("invalid_output_artifacts", "output_artifacts must be a list"))
        outputs = []
    outcome = receipt.get("outcome")
    if outcome == "completed" and not outputs:
        failures.append(failure("empty_completed_receipt", "completed receipt requires output artifacts"))
    ids: set[str] = set()
    kinds: set[str] = set()
    paths: set[str] = set()
    physical_outputs: set[tuple[int, int]] = set()
    write_scopes = [item for item in handoff.get("scope", {}).get("write", []) if item != handoff.get("scope", {}).get("receipt_path")]
    source_ids = {item.get("artifact_id") for item in source_artifacts}
    for item in outputs:
        if not isinstance(item, dict):
            failures.append(failure("invalid_output_artifacts", "output entries must be objects"))
            continue
        artifact_id = item.get("provider_artifact_id")
        kind = item.get("kind")
        value = item.get("path")
        if not nonempty(artifact_id) or artifact_id in ids:
            failures.append(failure("duplicate_output_artifact", "provider artifact ids must be unique"))
        else:
            ids.add(artifact_id)
        if not nonempty(kind) or kind in kinds or kind not in expected_kinds:
            failures.append(failure("unrequested_output_kind", str(kind)))
        else:
            kinds.add(kind)
        normalized_value = normalized_path(value) if isinstance(value, str) else ""
        if not nonempty(value) or normalized_value in paths or not path_in_scopes(value, write_scopes):
            failures.append(failure("output_outside_scope", str(value)))
        else:
            paths.add(normalized_value)
        target = project_path(project_root, value, "output")
        if target is None or not target.is_file():
            failures.append(failure("missing_output_artifact", str(value)))
        elif path_has_symlink_component(project_root, str(value)):
            failures.append(failure("invalid_output_artifact", f"output must not be a symlink: {value}"))
        elif target.stat().st_size == 0 or target.stat().st_nlink != 1:
            failures.append(failure("invalid_output_artifact", f"output must be non-empty and not hardlinked: {value}"))
        elif (target.stat().st_dev, target.stat().st_ino) in physical_outputs:
            failures.append(failure("duplicate_output_artifact", f"physical output file is reused: {value}"))
        elif item.get("sha256") != sha256(target):
            failures.append(failure("output_hash_mismatch", str(artifact_id)))
        else:
            physical_outputs.add((target.stat().st_dev, target.stat().st_ino))
        if item.get("visibility") != "internal_only":
            failures.append(failure("authority_escalation", "provider output visibility must be internal_only"))
        source_input_ids = item.get("source_input_ids")
        if not valid_string_list(source_input_ids, allow_empty=False) or not set(source_input_ids).issubset(source_ids):
            failures.append(failure("invalid_output_lineage", str(artifact_id)))
    if outcome == "completed" and kinds != expected_kinds:
        failures.append(failure("missing_requested_output", ",".join(sorted(expected_kinds - kinds))))

    domain = receipt.get("domain_delivery")
    if not isinstance(domain, dict) or domain.get("contract_id") != "dircreative.domain-delivery/1.0":
        failures.append(failure("missing_domain_delivery", "DIR domain_delivery extension is required"))
        domain = {}
    verdict = domain.get("domain_verdict")
    if verdict not in VERDICTS:
        failures.append(failure("invalid_domain_verdict", str(verdict)))
    else:
        expected_outcome, expected_qa, expected_recommendation = verdict_contract(verdict)
        if outcome != expected_outcome:
            failures.append(failure("domain_state_conflict", "outcome does not match domain verdict"))
        qa = receipt.get("qa")
        if not isinstance(qa, dict) or qa.get("status") != expected_qa:
            failures.append(failure("domain_state_conflict", "qa status does not match domain verdict"))
        if receipt.get("specialist_recommendation") != expected_recommendation:
            failures.append(failure("domain_state_conflict", "recommendation does not match domain verdict"))
    for field in ["client_ready", "final_export_allowed", "generation_ready"]:
        if domain.get(field) is not False:
            failures.append(failure("authority_escalation", f"domain_delivery.{field} must be false"))
    if verdict in {"domain_accepted", "draft_accepted_with_limitations"}:
        if domain.get("discussion_ready") is not True or domain.get("specialist_handoff_ready") is not True:
            failures.append(failure("domain_state_conflict", "accepted result must be discussion/handoff ready"))
    if verdict == "draft_accepted_with_limitations" and not receipt.get("qa", {}).get("limitations"):
        failures.append(failure("missing_limitations", "limited draft must list limitations"))
    required_extensions = handoff.get("acceptance", {}).get("required_receipt_extensions", [])
    extensions = receipt.get("extensions")
    if not isinstance(extensions, list):
        failures.append(failure("missing_receipt_extension", "receipt extensions must be a list"))
        extensions = []
    extension_pairs: set[tuple[str, str]] = set()
    for item in extensions:
        if not isinstance(item, dict) or not nonempty(item.get("id")) or not nonempty(item.get("version")):
            failures.append(failure("invalid_receipt_extension", "receipt extension entries are invalid"))
            continue
        pair = (item["id"], item["version"])
        if pair in extension_pairs:
            failures.append(failure("invalid_receipt_extension", f"duplicate receipt extension: {pair[0]}"))
        extension_pairs.add(pair)
        if pair == (DOMAIN_EXTENSION["id"], DOMAIN_EXTENSION["version"]) and item.get("payload") != domain:
            failures.append(failure("invalid_receipt_extension", "DIR extension payload differs from domain_delivery"))
    required_pairs = {
        (item.get("id"), item.get("version"))
        for item in required_extensions
        if isinstance(item, dict)
    }
    if not required_pairs.issubset(extension_pairs):
        failures.append(failure("missing_receipt_extension", "required receipt extension is missing"))
    questions = receipt.get("open_questions")
    if not isinstance(questions, list):
        failures.append(failure("invalid_open_questions", "open_questions must be a list"))
        questions = []
    if outcome == "needs_user":
        question_ids = [item.get("id") for item in questions if isinstance(item, dict)]
        if not questions or len(question_ids) != len(set(question_ids)) or not all(
            isinstance(item, dict) and nonempty(item.get("id")) and nonempty(item.get("question"))
            for item in questions
        ):
            failures.append(failure("invalid_open_questions", "needs_user requires non-empty unique structured questions"))
    return failures


def validate_v1_adoption(
    project_root: Path,
    handoff: dict[str, Any],
    receipt_path: Path,
    receipt: dict[str, Any],
    adoption: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    if adoption.get("protocol_id") != PROTOCOL_ID or adoption.get("contract_version") != V1_CONTRACT_VERSION:
        failures.append(failure("invalid_protocol", "adoption protocol/version mismatch"))
    if adoption.get("message_type") != "adoption" or adoption.get("decision_owner") != "adco":
        failures.append(failure("invalid_adoption_owner", "ADCO must own the adoption record"))
    if adoption.get("handoff_id") != receipt.get("handoff_id") or adoption.get("receipt_id") != receipt.get("receipt_id"):
        failures.append(failure("adoption_identity_mismatch", "adoption does not bind receipt/handoff"))
    if adoption.get("receipt_sha256") != sha256(receipt_path):
        failures.append(failure("adoption_receipt_hash_mismatch", "adoption receipt hash mismatch"))
    decision = adoption.get("decision")
    verdict = receipt.get("domain_delivery", {}).get("domain_verdict")
    allowed_decisions = {
        "domain_accepted": {"adopt", "reject", "defer"},
        "draft_accepted_with_limitations": {"partial_adopt", "reject", "defer"},
        "needs_user": {"partial_adopt", "reject", "defer"},
        "needs_revision": {"reject", "defer"},
        "blocked": {"reject", "defer"},
    }.get(verdict, set())
    if decision not in allowed_decisions:
        failures.append(failure("adoption_domain_state_conflict", f"{verdict} cannot use {decision}"))
    output_by_id = {
        item.get("provider_artifact_id"): item
        for item in receipt.get("output_artifacts", [])
        if isinstance(item, dict)
    }
    adopted = adoption.get("adopted_outputs")
    if not isinstance(adopted, list):
        failures.append(failure("invalid_adoption_outputs", "adopted_outputs must be a list"))
        adopted = []
    adopted_ids: set[str] = set()
    for item in adopted:
        if not isinstance(item, dict):
            failures.append(failure("invalid_adoption_outputs", "adopted output entries must be objects"))
            continue
        provider_id = item.get("provider_artifact_id")
        source = output_by_id.get(provider_id)
        target_value = item.get("target_path")
        if source is None or provider_id in adopted_ids:
            failures.append(failure("invalid_adoption_outputs", str(provider_id)))
            continue
        adopted_ids.add(provider_id)
        if not nonempty(target_value) or protected_scope_overlap(str(target_value)):
            failures.append(failure("protected_adoption_target", str(target_value)))
            continue
        if path_has_symlink_component(project_root, target_value):
            failures.append(failure("protected_adoption_target", f"symlink target: {target_value}"))
            continue
        target = project_path(project_root, target_value, "adoption target")
        if target is None or not target.is_file():
            failures.append(failure("missing_adoption_target", str(target_value)))
        elif item.get("sha256") != source.get("sha256") or sha256(target) != source.get("sha256"):
            failures.append(failure("adoption_hash_mismatch", str(provider_id)))
    if decision == "adopt" and adopted_ids != set(output_by_id):
        failures.append(failure("incomplete_adoption", "full adoption must map every output"))
    if decision == "partial_adopt" and not adopted_ids and receipt.get("outcome") != "needs_user":
        failures.append(failure("incomplete_adoption", "partial adoption must map at least one output"))
    if decision in {"reject", "defer"} and adopted_ids:
        failures.append(failure("invalid_adoption_outputs", "reject/defer cannot adopt outputs"))
    if verdict == "draft_accepted_with_limitations" and decision == "partial_adopt":
        if adoption.get("limitations_carried_forward") != receipt.get("qa", {}).get("limitations"):
            failures.append(failure("missing_limitations", "partial adoption must preserve all DIR limitations"))
    validations = adoption.get("adco_validation")
    if not valid_string_list(validations, allow_empty=False) or not {
        "protocol",
        "identity",
        "scope",
        "host_scope_manifest",
        "hash",
        "authority",
        "output_contract",
    }.issubset(set(validations)):
        failures.append(failure("missing_adco_validation", "adoption validation evidence is incomplete"))
    proof = adoption.get("host_scope_proof")
    baseline = handoff.get("scope", {}).get("host_baseline")
    if not isinstance(proof, dict) or not isinstance(baseline, dict):
        failures.append(failure("missing_host_scope_proof", "adoption host scope proof is missing"))
    else:
        baseline_path = project_path(project_root, baseline.get("path"), "host baseline")
        baseline_payload: dict[str, Any] = {}
        if baseline_path is None or not baseline_path.is_file() or sha256(baseline_path) != baseline.get("sha256"):
            failures.append(failure("invalid_host_scope_proof", "host baseline file or hash is invalid at adoption"))
        else:
            try:
                baseline_payload = load_json(baseline_path)
            except ValueError as exc:
                failures.append(failure("invalid_host_scope_proof", str(exc)))
        baseline_files = baseline_payload.get("files")
        excluded_roots = baseline_payload.get("excluded_roots")
        if not isinstance(baseline_files, dict) or not valid_string_list(excluded_roots):
            failures.append(failure("invalid_host_scope_proof", "host baseline manifest is malformed"))
        else:
            baseline_digest = manifest_digest(baseline_files)
            adopted_target_paths = [
                str(item.get("target_path"))
                for item in adopted
                if isinstance(item, dict) and nonempty(item.get("target_path"))
            ]
            post_adoption_exclusions = [
                *excluded_roots,
                "AD-creative/orchestrator/artifact_index.csv",
                *adopted_target_paths,
            ]
            observed_files = specialist_scope_manifest(project_root, post_adoption_exclusions)
            baseline_comparable = {
                path: digest
                for path, digest in baseline_files.items()
                if not any(relative_path_is_within(path, root) for root in post_adoption_exclusions)
            }
            changed_paths = sorted(
                path
                for path in set(observed_files) | set(baseline_comparable)
                if observed_files.get(path) != baseline_comparable.get(path)
            )
            if (
                baseline_digest != baseline.get("manifest_sha256")
                or changed_paths
                or proof.get("baseline_path") != baseline.get("path")
                or proof.get("baseline_sha256") != baseline.get("sha256")
                or proof.get("baseline_manifest_sha256") != baseline.get("manifest_sha256")
                or proof.get("observed_manifest_sha256") != baseline.get("manifest_sha256")
                or proof.get("changed_paths") != []
            ):
                failures.append(
                    failure("invalid_host_scope_proof", "adoption host scope proof does not close the observed baseline")
                )
    gate_effect = adoption.get("gate_effect")
    if not isinstance(gate_effect, dict):
        failures.append(failure("invalid_gate_effect", "adoption gate_effect is missing"))
    else:
        expected_advance = receipt.get("outcome") == "completed" and decision in {"adopt", "partial_adopt"}
        if gate_effect.get("advance_allowed") is not expected_advance:
            failures.append(failure("invalid_gate_effect", "adoption gate effect conflicts with receipt outcome"))
        if gate_effect.get("next_gate") != "creative-quality-gate":
            failures.append(failure("invalid_gate_effect", "specialist adoption must return to the creative quality gate"))
    return failures


def validate_v2_handoff(
    project_root: Path,
    handoff: dict[str, Any],
    descriptor: dict[str, Any],
) -> list[str]:
    failures = validate_descriptor(descriptor)
    failures.extend(
        failure("invalid_v2_handoff_shape", item)
        for item in v2_handoff_schema_errors(handoff)
    )
    missing = V2_HANDOFF_FIELDS - set(handoff)
    extra = set(handoff) - V2_HANDOFF_FIELDS
    if (missing or extra) and not any(
        item.startswith("invalid_v2_handoff_shape:") for item in failures
    ):
        failures.append(
            failure(
                "invalid_v2_handoff_shape",
                f"missing={sorted(missing)} extra={sorted(extra)}",
            )
        )
    if "nested_dispatch" in extra or handoff.get("nested_dispatch") is not None:
        failures.append(failure("nested_dispatch_forbidden", "v2 forbids nested dispatch fields"))
    reserved = extra & V2_FORBIDDEN_CONTROL_FIELDS
    if reserved:
        failures.append(
            failure(
                "reserved_control_field",
                f"v2 handoff copies ADCO-owned fields: {','.join(sorted(reserved))}",
            )
        )
    if handoff.get("protocol_id") != PROTOCOL_ID:
        failures.append(failure("invalid_protocol", "handoff protocol_id mismatch"))
    if handoff.get("contract_version") != V2_CONTRACT_VERSION:
        failures.append(failure("unsupported_contract_version", "handoff contract_version must be 2.0"))

    locked = handoff.get("locked_decisions")
    locked_paths: set[str] = set()
    if isinstance(locked, list):
        for item in locked:
            if not isinstance(item, dict):
                continue
            artifact_id = str(item.get("artifact_id", ""))
            value = item.get("path")
            if not isinstance(value, str):
                continue
            normalized = normalized_path(value)
            normalized_identity = normalized.casefold()
            if normalized_identity in locked_paths:
                failures.append(failure("duplicate_locked_decision", normalized))
                continue
            locked_paths.add(normalized_identity)
            target = project_path(project_root, value, "locked decision")
            if target is None or path_has_symlink_component(project_root, value):
                failures.append(failure("invalid_locked_decision", artifact_id or value))
            elif not target.is_file():
                failures.append(failure("missing_locked_decision", artifact_id or value))
            elif target.stat().st_size == 0 or target.stat().st_nlink != 1:
                failures.append(failure("invalid_locked_decision", artifact_id or value))
            elif item.get("sha256") != sha256(target):
                failures.append(failure("stale_locked_decision", artifact_id or value))
    brief_snapshot = handoff.get("brief_snapshot")
    if (
        isinstance(brief_snapshot, str)
        and normalized_path(brief_snapshot).casefold() not in locked_paths
    ):
        failures.append(
            failure("unbound_brief_snapshot", "brief_snapshot must name one hash-bound locked decision")
        )

    requested = handoff.get("requested_outputs")
    profile = descriptor_profile(descriptor)
    supported = set(profile.get("capabilities", [])) if profile else set()
    if isinstance(requested, list):
        valid_requests = [item for item in requested if isinstance(item, dict)]
        output_ids = [str(item.get("output_id", "")) for item in valid_requests]
        if len(output_ids) != len(set(output_ids)):
            failures.append(failure("invalid_v2_handoff_shape", "requested output_id values must be unique"))
        output_types = [str(item.get("type", "")) for item in valid_requests]
        if len(output_types) != len(set(output_types)):
            failures.append(
                failure(
                    "duplicate_requested_output_type",
                    "requested output type values must be unique for TYPE=PATH receipt binding",
                )
            )
        unsupported = {
            str(item.get("type", "")) for item in valid_requests
        } - supported
        unsupported.discard("")
        if unsupported:
            failures.append(failure("missing_profile_capability", ",".join(sorted(unsupported))))
        for item in valid_requests:
            output_id = str(item.get("output_id", ""))
            path_root = item.get("path_root")
            if not isinstance(path_root, str):
                continue
            normalized_root = normalized_path(path_root)
            if (
                normalized_root in {"", "."}
                or project_path(project_root, path_root, "output root") is None
                or path_has_symlink_component(project_root, path_root)
            ):
                failures.append(failure("invalid_output_scope", output_id or path_root))
            elif protected_scope_overlap(path_root):
                failures.append(failure("protected_output_scope", output_id or path_root))
            elif any(scopes_overlap(path_root, locked_path) for locked_path in locked_paths):
                failures.append(failure("locked_input_output_overlap", output_id or path_root))
    if handoff.get("execution_mode") != "inline":
        failures.append(failure("nested_dispatch_forbidden", "v2 execution_mode must be inline"))
    return failures


def v2_status_from_verdict(verdict: str) -> str:
    mapping = {
        "domain_accepted": "completed",
        "draft_accepted_with_limitations": "completed",
        "needs_user": "needs_user",
        "needs_revision": "blocked",
        "blocked": "blocked",
    }
    try:
        return mapping[verdict]
    except KeyError as exc:
        raise ValueError(f"invalid domain verdict: {verdict}") from exc


def build_v2_receipt(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path,
    artifact_paths: dict[str, str],
    *,
    verdict: str | None = None,
    v2_status: str | None = None,
    limitations: list[str] | None = None,
    open_questions: list[str] | None = None,
    receipt_output: str | None = None,
) -> tuple[dict[str, Any], Path]:
    limitations = limitations or []
    open_questions = open_questions or []
    status = v2_status or (v2_status_from_verdict(verdict) if verdict is not None else None)
    if status not in V2_STATUSES:
        raise ValueError(f"invalid v2 receipt status: {status}")
    descriptor = load_json(DESCRIPTOR_PATH)
    handoff_failures = validate_handoff(
        project_root,
        handoff,
        descriptor,
        handoff_path=handoff_path,
    )
    if handoff_failures:
        raise ValueError("v2 handoff is not currently valid: " + "; ".join(handoff_failures))
    registration, registration_failures = v2_exchange_registration(
        project_root,
        handoff,
        handoff_path,
        descriptor,
    )
    if registration is None or registration_failures:
        raise ValueError("v2 handoff is not registered: " + "; ".join(registration_failures))
    try:
        handoff_relative = handoff_path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("handoff path escapes project") from exc
    if project_path(project_root, handoff_relative, "handoff") != handoff_path.resolve():
        raise ValueError("handoff path escapes project")
    if not handoff_path.is_file() or load_json(handoff_path) != handoff:
        raise ValueError("handoff file does not match the validated handoff")
    requested_outputs = handoff.get("requested_outputs")
    if not isinstance(requested_outputs, list):
        raise ValueError("v2 handoff requested_outputs must be a list")
    request_by_type = {
        str(item.get("type", "")): item
        for item in requested_outputs
        if isinstance(item, dict) and nonempty(item.get("type"))
    }
    requested_types = set(request_by_type)
    supplied_types = set(artifact_paths)
    if status == "completed":
        if supplied_types != requested_types:
            raise ValueError("completed v2 receipt must contain every requested output type")
        if open_questions:
            raise ValueError("completed v2 receipt cannot contain open questions")
    else:
        if artifact_paths:
            raise ValueError(f"{status} v2 receipt cannot contain outputs")
        if status == "needs_user" and not open_questions:
            raise ValueError("needs_user v2 receipt requires at least one open question")
        if status != "needs_user" and open_questions:
            raise ValueError(f"{status} v2 receipt cannot contain open questions")
        if status in {"blocked", "failed"} and not limitations:
            raise ValueError(f"{status} v2 receipt requires at least one limitation")
    outputs: list[dict[str, str]] = []
    physical_outputs: set[tuple[int, int]] = set()
    for kind, value in artifact_paths.items():
        request = request_by_type.get(kind)
        if request is None:
            raise ValueError(f"unrequested output kind: {kind}")
        if path_has_symlink_component(project_root, value):
            raise ValueError(f"output artifact uses a symlink: {value}")
        if protected_scope_overlap(value):
            raise ValueError(f"output artifact targets ADCO-owned state: {value}")
        path = project_path(project_root, value, "output artifact")
        if path is None or not path.is_file():
            raise ValueError(f"output artifact missing or out of project: {value}")
        output_root = project_path(project_root, request.get("path_root"), "output root")
        if output_root is None or (path != output_root and output_root not in path.parents):
            raise ValueError(f"output artifact is outside requested scope: {value}")
        if path.stat().st_size == 0 or path.stat().st_nlink != 1:
            raise ValueError(f"output artifact must be non-empty and not hardlinked: {value}")
        identity = (path.stat().st_dev, path.stat().st_ino)
        if identity in physical_outputs:
            raise ValueError(f"physical output file is reused: {value}")
        physical_outputs.add(identity)
        outputs.append(
            {
                "output_id": str(request["output_id"]),
                "type": kind,
                "path": normalized_path(value),
                "sha256": sha256(path),
            }
        )
    qa_value = {
        "completed": "pass",
        "needs_user": "needs_user",
        "blocked": "blocked",
        "failed": "fail",
    }[status]
    structured_questions = [
        {"id": f"Q-{index:03d}", "question": question}
        for index, question in enumerate(open_questions, start=1)
    ]
    receipt: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID,
        "contract_version": V2_CONTRACT_VERSION,
        "status": status,
        "outputs": outputs,
        "domain_qa": {
            "status": qa_value,
            "checks": ["brief_adherence", "continuity", "production_clarity"],
            "limitations": limitations,
        },
        "open_questions": structured_questions,
    }
    if receipt_output is None:
        raise ValueError("v2 receipt requires the explicit ADCO-registered receipt path")
    registered_receipt = registration.get("receipt_path", "")
    if normalized_path(receipt_output) != normalized_path(registered_receipt):
        raise ValueError("receipt path does not match the ADCO exchange registration")
    receipt_path = project_path(project_root, receipt_output, "receipt")
    if receipt_path is None:
        raise ValueError("receipt path escapes project")
    collision_paths = [
        handoff_relative,
        *[
            str(item.get("path", ""))
            for item in handoff.get("locked_decisions", [])
            if isinstance(item, dict)
        ],
        *artifact_paths.values(),
        *[
            str(item.get("path_root", ""))
            for item in requested_outputs
            if isinstance(item, dict)
        ],
    ]
    if (
        protected_scope_overlap(receipt_output)
        or any(nonempty(value) and scopes_overlap(receipt_output, value) for value in collision_paths)
        or path_has_symlink_component(project_root, receipt_output)
    ):
        raise ValueError("receipt path overlaps protected handoff, input, or output state")
    prewrite_failures = [
        item
        for item in validate_v2_receipt(
            project_root,
            handoff,
            handoff_path,
            receipt,
            receipt_path=None,
        )
        if not item.startswith("missing_receipt_file:")
    ]
    if prewrite_failures:
        raise ValueError("invalid v2 receipt before write: " + "; ".join(prewrite_failures))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    if path_has_symlink_component(project_root, receipt_output):
        raise ValueError("receipt path uses a symlink component")
    write_new_json_atomic(receipt_path, receipt)
    return receipt, receipt_path


def validate_v2_receipt(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path,
    receipt: dict[str, Any],
    receipt_path: Path | None = None,
) -> list[str]:
    failures = [
        failure("invalid_v2_receipt_shape", item)
        for item in v2_receipt_schema_errors(receipt)
    ]
    missing = V2_RECEIPT_FIELDS - set(receipt)
    extra = set(receipt) - V2_RECEIPT_FIELDS
    if (missing or extra) and not failures:
        failures.append(
            failure(
                "invalid_v2_receipt_shape",
                f"missing={sorted(missing)} extra={sorted(extra)}",
            )
        )
    if "nested_dispatch" in extra:
        failures.append(failure("nested_dispatch_forbidden", "v2 receipt cannot claim nested dispatch"))
    reserved = extra & V2_FORBIDDEN_CONTROL_FIELDS
    if reserved:
        failures.append(
            failure(
                "reserved_readiness_claim",
                f"v2 receipt contains ADCO-owned fields: {','.join(sorted(reserved))}",
            )
        )
    if receipt.get("protocol_id") != PROTOCOL_ID:
        failures.append(failure("invalid_protocol", "receipt protocol_id mismatch"))
    if receipt.get("contract_version") != V2_CONTRACT_VERSION:
        failures.append(failure("unsupported_contract_version", "receipt contract_version must be 2.0"))
    status = receipt.get("status")
    if not isinstance(status, str) or status not in V2_STATUSES:
        failures.append(failure("invalid_v2_status", str(status)))
        status = ""
    try:
        descriptor = load_json(DESCRIPTOR_PATH)
        failures.extend(
            validate_handoff(
                project_root,
                handoff,
                descriptor,
                handoff_path=handoff_path,
            )
        )
    except ValueError as exc:
        failures.append(failure("invalid_handoff_at_receipt", str(exc)))
        descriptor = {}
    registration, registration_failures = v2_exchange_registration(
        project_root,
        handoff,
        handoff_path,
        descriptor,
    )
    failures.extend(registration_failures)
    if receipt_path is None:
        failures.append(failure("missing_receipt_file", "v2 receipt path is required"))
    else:
        try:
            receipt_relative = receipt_path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            receipt_relative = ""
        registered_receipt = registration.get("receipt_path", "") if registration else ""
        if (
            not receipt_relative
            or normalized_path(receipt_relative) != normalized_path(registered_receipt)
            or path_has_symlink_component(project_root, receipt_relative)
            or not receipt_path.is_file()
            or receipt_path.stat().st_size == 0
            or receipt_path.stat().st_nlink != 1
        ):
            failures.append(failure("receipt_file_identity_mismatch", receipt_relative or str(receipt_path)))
        else:
            try:
                if load_json(receipt_path) != receipt:
                    failures.append(failure("receipt_file_identity_mismatch", "file content differs"))
            except ValueError as exc:
                failures.append(failure("receipt_file_identity_mismatch", str(exc)))
            if stat.S_IMODE(receipt_path.stat().st_mode) != 0o600:
                failures.append(failure("receipt_file_permissions", "v2 receipt must use mode 0600"))
    try:
        handoff_relative = handoff_path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        handoff_relative = ""
    if (
        not handoff_relative
        or project_path(project_root, handoff_relative, "handoff") != handoff_path.resolve()
        or not handoff_path.is_file()
        or load_json(handoff_path) != handoff
    ):
        failures.append(failure("handoff_identity_mismatch", "handoff file does not match validation input"))

    requested_values = handoff.get("requested_outputs")
    requested = {
        str(item.get("output_id", "")): item
        for item in requested_values
        if isinstance(requested_values, list)
        and isinstance(item, dict)
        and nonempty(item.get("output_id"))
    } if isinstance(requested_values, list) else {}
    outputs = receipt.get("outputs")
    if not isinstance(outputs, list):
        failures.append(failure("invalid_output_artifacts", "outputs must be a list"))
        outputs = []
    if status == "completed" and not outputs:
        failures.append(failure("empty_completed_receipt", "completed receipt requires outputs"))
    if status in {"needs_user", "blocked", "failed"} and outputs:
        failures.append(failure("invalid_status_outputs", f"{status} receipt cannot contain outputs"))
    ids: set[str] = set()
    paths: set[str] = set()
    physical_outputs: set[tuple[int, int]] = set()
    for item in outputs:
        if not isinstance(item, dict):
            failures.append(failure("invalid_output_artifacts", "output entries must be objects"))
            continue
        if set(item) != V2_OUTPUT_FIELDS:
            failures.append(
                failure(
                    "invalid_v2_output_shape",
                    f"output fields must be {sorted(V2_OUTPUT_FIELDS)}",
                )
            )
        output_id = item.get("output_id")
        output_type = item.get("type")
        value = item.get("path")
        digest = item.get("sha256")
        if not nonempty(output_id) or output_id in ids:
            failures.append(failure("duplicate_output_artifact", str(output_id)))
        else:
            ids.add(str(output_id))
        request = requested.get(str(output_id))
        if request is None or output_type != request.get("type"):
            failures.append(failure("unrequested_output_kind", str(output_type)))
        else:
            output_root = project_path(project_root, request.get("path_root"), "output root")
            target_for_scope = project_path(project_root, value, "output")
            if (
                output_root is None
                or target_for_scope is None
                or (target_for_scope != output_root and output_root not in target_for_scope.parents)
            ):
                failures.append(failure("output_scope_mismatch", str(value)))
        normalized_value = normalized_path(value) if isinstance(value, str) else ""
        if not nonempty(value) or normalized_value in paths:
            failures.append(failure("duplicate_output_artifact", str(value)))
        else:
            paths.add(normalized_value)
        if isinstance(value, str) and protected_scope_overlap(value):
            failures.append(failure("protected_output_target", value))
        target = project_path(project_root, value, "output")
        if target is None or not target.is_file():
            failures.append(failure("missing_output_artifact", str(value)))
        elif path_has_symlink_component(project_root, str(value)):
            failures.append(failure("invalid_output_artifact", f"output must not be a symlink: {value}"))
        elif target.stat().st_size == 0 or target.stat().st_nlink != 1:
            failures.append(failure("invalid_output_artifact", f"output must be non-empty and not hardlinked: {value}"))
        elif (target.stat().st_dev, target.stat().st_ino) in physical_outputs:
            failures.append(failure("duplicate_output_artifact", f"physical output file is reused: {value}"))
        elif not isinstance(digest, str) or not SHA_RE.fullmatch(digest) or digest != sha256(target):
            failures.append(failure("output_hash_mismatch", str(output_id)))
        else:
            physical_outputs.add((target.stat().st_dev, target.stat().st_ino))
    if status == "completed" and ids != set(requested):
        failures.append(failure("missing_requested_output", ",".join(sorted(set(requested) - ids))))

    domain_qa = receipt.get("domain_qa")
    if not isinstance(domain_qa, dict) or set(domain_qa) != V2_QA_FIELDS:
        failures.append(failure("invalid_domain_qa", "domain_qa must use the compact v2 shape"))
        domain_qa = {}
    qa_status = domain_qa.get("status")
    expected_qa = {
        "completed": "pass",
        "needs_user": "needs_user",
        "blocked": "blocked",
        "failed": "fail",
    }.get(status)
    if qa_status not in {"pass", "fail", "blocked", "needs_user"} or qa_status != expected_qa:
        failures.append(failure("invalid_domain_qa", "domain_qa.status conflicts with receipt status"))
    if not valid_string_list(domain_qa.get("checks"), allow_empty=False) or not valid_string_list(
        domain_qa.get("limitations")
    ):
        failures.append(
            failure(
                "invalid_domain_qa",
                "domain_qa checks must be non-empty strings and limitations must be strings",
            )
        )
    questions = receipt.get("open_questions")
    if not isinstance(questions, list):
        failures.append(failure("invalid_open_questions", "open_questions must be a list"))
        questions = []
    question_ids = [
        str(item.get("id", ""))
        for item in questions
        if isinstance(item, dict) and nonempty(item.get("id"))
    ]
    if len(question_ids) != len(questions) or len(question_ids) != len(set(question_ids)):
        failures.append(failure("invalid_open_questions", "open question ids must be present and unique"))
    if status == "needs_user" and not questions:
        failures.append(failure("invalid_open_questions", "needs_user requires at least one question"))
    if status in {"completed", "blocked", "failed"} and questions:
        failures.append(failure("invalid_open_questions", f"{status} receipt cannot contain open questions"))
    limitations = domain_qa.get("limitations") if isinstance(domain_qa, dict) else None
    if status in {"blocked", "failed"} and (not isinstance(limitations, list) or not limitations):
        failures.append(failure("missing_status_limitation", f"{status} requires at least one limitation"))
    return failures


def validate_handoff(
    project_root: Path,
    handoff: dict[str, Any],
    descriptor: dict[str, Any],
    *,
    handoff_path: Path | None = None,
) -> list[str]:
    validators = {
        V1_CONTRACT_VERSION: validate_v1_handoff,
        V2_CONTRACT_VERSION: validate_v2_handoff,
    }
    validator = validators.get(handoff.get("contract_version"))
    if validator is None:
        return [failure("unsupported_contract_version", str(handoff.get("contract_version")))]
    failures = validator(project_root, handoff, descriptor)
    if handoff.get("contract_version") == V2_CONTRACT_VERSION:
        _, registration_failures = v2_exchange_registration(
            project_root,
            handoff,
            handoff_path,
            descriptor,
        )
        failures.extend(registration_failures)
    return failures


def build_receipt(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path,
    artifact_paths: dict[str, str],
    *,
    verdict: str | None = None,
    v2_status: str | None = None,
    limitations: list[str] | None = None,
    open_questions: list[Any] | None = None,
    receipt_output: str | None = None,
) -> tuple[dict[str, Any], Path]:
    version = handoff.get("contract_version")
    if version == V1_CONTRACT_VERSION:
        if verdict is None or v2_status is not None:
            raise ValueError("v1 receipt requires --domain-verdict and does not accept --status")
        if receipt_output is not None:
            raise ValueError("v1 receipt path is owned by handoff.scope.receipt_path")
        return build_v1_receipt(
            project_root,
            handoff,
            handoff_path,
            artifact_paths,
            verdict=verdict,
            limitations=limitations,
            open_questions=open_questions,
        )
    if version == V2_CONTRACT_VERSION:
        if open_questions is not None and not all(isinstance(item, str) for item in open_questions):
            raise ValueError("v2 open questions must be strings")
        return build_v2_receipt(
            project_root,
            handoff,
            handoff_path,
            artifact_paths,
            verdict=verdict,
            v2_status=v2_status,
            limitations=limitations,
            open_questions=open_questions,
            receipt_output=receipt_output,
        )
    raise ValueError(f"unsupported contract version: {version}")


def validate_receipt(
    project_root: Path,
    handoff: dict[str, Any],
    handoff_path: Path,
    receipt: dict[str, Any],
    *,
    receipt_path: Path | None = None,
) -> list[str]:
    version = handoff.get("contract_version")
    if receipt.get("contract_version") != version:
        return [failure("receipt_identity_mismatch", "contract_version")]
    validators = {
        V1_CONTRACT_VERSION: validate_v1_receipt,
        V2_CONTRACT_VERSION: validate_v2_receipt,
    }
    validator = validators.get(version)
    if validator is None:
        return [failure("unsupported_contract_version", str(version))]
    if version == V2_CONTRACT_VERSION:
        return validate_v2_receipt(
            project_root,
            handoff,
            handoff_path,
            receipt,
            receipt_path,
        )
    return validator(project_root, handoff, handoff_path, receipt)


def validate_adoption(
    project_root: Path,
    handoff: dict[str, Any],
    receipt_path: Path,
    receipt: dict[str, Any],
    adoption: dict[str, Any],
) -> list[str]:
    version = handoff.get("contract_version")
    if version == V1_CONTRACT_VERSION:
        return validate_v1_adoption(project_root, handoff, receipt_path, receipt, adoption)
    if version == V2_CONTRACT_VERSION:
        return [failure("v2_adoption_owned_by_adco", "DIRcreative does not write or validate v2 adoption state")]
    return [failure("unsupported_contract_version", str(version))]


def make_fixture_handoff(project: Path, descriptor: dict[str, Any]) -> dict[str, Any]:
    source = project / "AD-creative/proposal_architecture/specialist_input.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "Brand: Northline Cold Brew\nDeliverable: 60-second vertical film\nTone: precise morning momentum.\n",
        encoding="utf-8",
    )
    output_root = "AD-creative/workspaces/WORK-SPX-001/specialists/SPH-001/outputs"
    receipt_path = "AD-creative/workspaces/WORK-SPX-001/specialists/SPH-001/receipt.json"
    baseline_path = project / "AD-creative/orchestrator/specialist_exchange/baselines/SPH-001.json"
    baseline_payload = {
        "protocol_id": PROTOCOL_ID,
        "contract_version": V1_CONTRACT_VERSION,
        "message_type": "host_scope_baseline",
        "handoff_id": "SPH-001",
        "excluded_roots": [
            "AD-creative/orchestrator/specialist_exchange",
            output_root,
            receipt_path,
        ],
        "files": {"AD-creative/proposal_architecture/specialist_input.md": sha256(source)},
    }
    baseline_payload["manifest_sha256"] = manifest_digest(baseline_payload["files"])
    write_json(baseline_path, baseline_payload)
    return {
        "protocol_id": PROTOCOL_ID,
        "contract_version": V1_CONTRACT_VERSION,
        "message_type": "handoff",
        "exchange_id": "SPX-001",
        "handoff_id": "SPH-001",
        "attempt": 1,
        "supersedes_handoff_id": None,
        "work_id": "WORK-SPX-001",
        "provider_id": PROVIDER_ID,
        "profile_id": PROFILE_ID,
        "descriptor_ref": {"provider_id": PROVIDER_ID, "sha256": canonical_descriptor_hash(descriptor)},
        "task": {
            "objective": "Create an internal film story package for a 60-second vertical cold-brew ad.",
            "required_capabilities": ["film.story_package"],
            "expected_output_kinds": ["film.story_package"],
        },
        "source_truth": {
            "artifacts": [
                {
                    "artifact_id": "ART-INPUT-001",
                    "version": "v001",
                    "path": "AD-creative/proposal_architecture/specialist_input.md",
                    "sha256": sha256(source),
                    "visibility": "internal_only",
                }
            ],
            "locks": [],
        },
        "execution": {
            "mode": "inline",
            "workspace_mode": "isolated_workspace",
            "lane_id": None,
            "thread_id": None,
            "nested_dispatch_allowed": False,
        },
        "scope": {
            "read": ["AD-creative/proposal_architecture/specialist_input.md"],
            "write": [output_root, receipt_path],
            "receipt_path": receipt_path,
            "host_baseline": {
                "path": str(baseline_path.relative_to(project)),
                "sha256": sha256(baseline_path),
                "manifest_sha256": baseline_payload["manifest_sha256"],
            },
            "forbidden": [
                "AD-creative/orchestrator/current_truth.md",
                "AD-creative/orchestrator/version_map.csv",
                "AD-creative/orchestrator/artifact_index.csv",
                "AD-creative/orchestrator/gate_log.csv",
                "AD-creative/ppt/exports/",
                "05_最终交付_FinalDelivery/",
            ],
        },
        "authorization": {
            "generation_mode": "prompt_only",
            "authorized": False,
            "authorization_ref": None,
            "external_upload": False,
        },
        "acceptance": {
            "visibility": "internal_only",
            "provider_recommendation_only": True,
            "required_receipt_extensions": [DOMAIN_EXTENSION],
            "stop_on": ["needs_user", "blocked", "failed"],
        },
    }


def write_story_package(project: Path, handoff: dict[str, Any]) -> str:
    if handoff.get("contract_version") == V2_CONTRACT_VERSION:
        requests = handoff.get("requested_outputs")
        if not isinstance(requests, list):
            raise ValueError("v2 handoff requested_outputs must be a list")
        request = next(
            item
            for item in requests
            if isinstance(item, dict) and item.get("type") == "film.story_package"
        )
        output_root = str(request["path_root"])
    else:
        output_root = next(
            item for item in handoff["scope"]["write"] if item != handoff["scope"]["receipt_path"]
        )
    path = project / output_root / "story_package.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Northline Cold Brew — 60s Vertical Film Story Package\n\n"
        "## Treatment\nMorning pressure becomes visible rhythm: elevator doors, calendar blocks, ice and coffee. "
        "The product is the deliberate pause that turns noise into forward motion.\n\n"
        "## Story Beats\n0-12s friction; 12-30s product ritual; 30-50s controlled momentum; 50-60s end-card resolve.\n\n"
        "## Shot Plan\n12 distinct vertical shots with product legibility, hand continuity, and motivated camera movement.\n\n"
        "## Production Constraints\nLogo, packaging, mandatory copy, music rights, and end-card language remain ADCO/client locks.\n",
        encoding="utf-8",
    )
    return str(path.relative_to(project))


def run_v1_self_test() -> tuple[bool, dict[str, Any]]:
    descriptor = load_json(DESCRIPTOR_PATH)
    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-selftest-") as raw:
        project = Path(raw)
        handoff = make_fixture_handoff(project, descriptor)
        handoff_path = project / "AD-creative/orchestrator/specialist_exchange/handoffs/SPH-001.json"
        write_json(handoff_path, handoff)
        handoff_failures = validate_handoff(
            project,
            handoff,
            descriptor,
            handoff_path=handoff_path,
        )
        story_path = write_story_package(project, handoff)
        receipt, receipt_path = build_receipt(
            project,
            handoff,
            handoff_path,
            {"film.story_package": story_path},
            verdict="draft_accepted_with_limitations",
            limitations=["Logo and mandatory end-card copy remain unlocked."],
        )
        receipt_failures = validate_receipt(
            project, handoff, handoff_path, receipt, receipt_path=receipt_path
        )
        target = project / "AD-creative/film/story_package_v001.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project / story_path, target)
        adoption = {
            "protocol_id": PROTOCOL_ID,
            "contract_version": V1_CONTRACT_VERSION,
            "message_type": "adoption",
            "adoption_id": "SPA-SPH-001",
            "handoff_id": handoff["handoff_id"],
            "receipt_id": receipt["receipt_id"],
            "receipt_sha256": sha256(receipt_path),
            "decision_owner": "adco",
            "decision": "partial_adopt",
            "reason": "Internal draft accepted with limitations.",
            "adopted_outputs": [
                {
                    "provider_artifact_id": receipt["output_artifacts"][0]["provider_artifact_id"],
                    "target_artifact_id": "ART-SPA-001",
                    "target_path": "AD-creative/film/story_package_v001.md",
                    "sha256": receipt["output_artifacts"][0]["sha256"],
                    "visibility": "internal_only",
                }
            ],
            "rejected_outputs": [],
            "limitations_carried_forward": receipt["qa"]["limitations"],
            "adco_validation": [
                "protocol",
                "identity",
                "scope",
                "host_scope_manifest",
                "hash",
                "authority",
                "output_contract",
            ],
            "host_scope_proof": {
                "baseline_path": handoff["scope"]["host_baseline"]["path"],
                "baseline_sha256": handoff["scope"]["host_baseline"]["sha256"],
                "baseline_manifest_sha256": handoff["scope"]["host_baseline"]["manifest_sha256"],
                "observed_manifest_sha256": handoff["scope"]["host_baseline"]["manifest_sha256"],
                "changed_paths": [],
            },
            "gate_effect": {"advance_allowed": True, "next_gate": "creative-quality-gate"},
            "created_at": "2026-07-10T00:00:00Z",
        }
        adoption_failures = validate_adoption(project, handoff, receipt_path, receipt, adoption)
        negative: dict[str, bool] = {}
        mutated_descriptor = copy.deepcopy(descriptor)
        mutated_descriptor["profiles"][0].pop("receipt_extension")
        negative["missing_descriptor_extension_rejected"] = "invalid_receipt_extension" in failure_ids(
            validate_descriptor(mutated_descriptor)
        )
        mutated = copy.deepcopy(receipt)
        mutated["claims"]["client_ready"] = True
        negative["authority_escalation_rejected"] = "authority_escalation" in failure_ids(
            validate_receipt(project, handoff, handoff_path, mutated)
        )
        mutated = copy.deepcopy(receipt)
        mutated["output_artifacts"][0]["kind"] = "film.unrequested_payload"
        negative["unrequested_output_rejected"] = "unrequested_output_kind" in failure_ids(
            validate_receipt(project, handoff, handoff_path, mutated)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["execution"]["mode"] = "codex_thread"
        mutated_handoff["execution"]["lane_id"] = "LANE-FILM"
        mutated_handoff["execution"]["lane_run_id"] = "WORK-SPX-001:LANE-FILM"
        mutated_handoff["execution"]["thread_id"] = "11111111-1111-4111-8111-111111111111"
        negative["invalid_worker_thread_rejected"] = "invalid_worker_thread_id" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["scope"]["host_baseline"]["sha256"] = "0" * 64
        negative["invalid_host_baseline_rejected"] = "invalid_host_baseline" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor)
        )
        symlink_scope = project / "AD-creative/workspaces/scope-link"
        symlink_scope.parent.mkdir(parents=True, exist_ok=True)
        symlink_scope.symlink_to(project / "AD-creative/orchestrator", target_is_directory=True)
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["scope"]["write"][0] = "AD-creative/workspaces/scope-link/outputs"
        negative["symlink_scope_rejected"] = "symlink_scope" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor)
        )
        symlink_scope.unlink()
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["authorization"] = {
            "generation_mode": "banana",
            "authorized": True,
            "authorization_ref": handoff["source_truth"]["artifacts"][0]["path"],
            "external_upload": False,
        }
        negative["unsupported_generation_mode_rejected"] = "unsupported_generation_mode" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["execution"]["nested_dispatch_allowed"] = True
        negative["nested_dispatch_rejected"] = "nested_dispatch_forbidden" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor)
        )
        mutated = copy.deepcopy(receipt)
        mutated["handoff_sha256"] = "0" * 64
        negative["handoff_hash_mismatch_rejected"] = "receipt_identity_mismatch" in failure_ids(
            validate_receipt(project, handoff, handoff_path, mutated)
        )
        mutated = copy.deepcopy(receipt)
        mutated["extensions"] = []
        negative["missing_negotiated_extension_rejected"] = "missing_receipt_extension" in failure_ids(
            validate_receipt(project, handoff, handoff_path, mutated)
        )
        mutated = copy.deepcopy(receipt)
        mutated["output_artifacts"] = []
        negative["empty_completed_receipt_rejected"] = "empty_completed_receipt" in failure_ids(
            validate_receipt(project, handoff, handoff_path, mutated)
        )
        needs_user = copy.deepcopy(receipt)
        needs_user["outcome"] = "needs_user"
        needs_user["qa"]["status"] = "needs_user"
        needs_user["specialist_recommendation"] = "return_questions_to_adco"
        needs_user["domain_delivery"].update(
            {
                "domain_verdict": "needs_user",
                "discussion_ready": False,
                "specialist_handoff_ready": False,
            }
        )
        needs_user["extensions"][0]["payload"] = copy.deepcopy(needs_user["domain_delivery"])
        needs_user["open_questions"] = []
        negative["empty_needs_user_questions_rejected"] = "invalid_open_questions" in failure_ids(
            validate_receipt(project, handoff, handoff_path, needs_user)
        )
        alias_handoff = copy.deepcopy(handoff)
        alias_handoff["task"]["expected_output_kinds"] = ["film.story_package", "film.treatment"]
        alias_receipt = copy.deepcopy(receipt)
        aliased_output = copy.deepcopy(alias_receipt["output_artifacts"][0])
        aliased_output["provider_artifact_id"] = "DIR-TREATMENT-001"
        aliased_output["kind"] = "film.treatment"
        aliased_output["path"] = "./" + aliased_output["path"]
        alias_receipt["output_artifacts"].append(aliased_output)
        negative["physical_output_alias_rejected"] = "duplicate_output_artifact" in failure_ids(
            validate_receipt(project, alias_handoff, handoff_path, alias_receipt)
        )
        output_symlink = (project / story_path).with_name("story_package_symlink.md")
        output_symlink.symlink_to(project / story_path)
        symlink_receipt = copy.deepcopy(receipt)
        symlink_receipt["output_artifacts"][0]["path"] = str(output_symlink.relative_to(project))
        negative["symlink_output_rejected"] = "invalid_output_artifact" in failure_ids(
            validate_receipt(project, handoff, handoff_path, symlink_receipt)
        )
        output_symlink.unlink()
        mutated_adoption = copy.deepcopy(adoption)
        mutated_adoption["adopted_outputs"][0]["target_path"] = (
            "AD-creative/film/../orchestrator/current_truth.md"
        )
        negative["control_plane_adoption_rejected"] = bool(
            {"protected_adoption_target", "missing_adoption_target"}
            & failure_ids(validate_adoption(project, handoff, receipt_path, receipt, mutated_adoption))
        )
        mutated_adoption = copy.deepcopy(adoption)
        mutated_adoption["host_scope_proof"]["observed_manifest_sha256"] = "0" * 64
        negative["host_scope_mismatch_rejected"] = "invalid_host_scope_proof" in failure_ids(
            validate_adoption(project, handoff, receipt_path, receipt, mutated_adoption)
        )
        mutated_adoption = copy.deepcopy(adoption)
        mutated_adoption["limitations_carried_forward"] = []
        negative["dropped_limitations_rejected"] = "missing_limitations" in failure_ids(
            validate_adoption(project, handoff, receipt_path, receipt, mutated_adoption)
        )
        unreported = project / "AD-creative/orchestrator/current_truth.md"
        unreported.parent.mkdir(parents=True, exist_ok=True)
        unreported.write_text("unreported host mutation\n", encoding="utf-8")
        negative["unreported_host_write_rejected"] = "invalid_host_scope_proof" in failure_ids(
            validate_adoption(project, handoff, receipt_path, receipt, adoption)
        )
        unreported.unlink()
        target.unlink()
        rejected_adoption = copy.deepcopy(adoption)
        rejected_adoption["decision"] = "reject"
        rejected_adoption["adopted_outputs"] = []
        rejected_adoption["rejected_outputs"] = [
            receipt["output_artifacts"][0]["provider_artifact_id"]
        ]
        rejected_adoption["gate_effect"]["advance_allowed"] = False
        negative["adco_reject_authority_preserved"] = not validate_adoption(
            project,
            handoff,
            receipt_path,
            receipt,
            rejected_adoption,
        )
        ok = not handoff_failures and not receipt_failures and not adoption_failures and all(negative.values())
        return ok, {
            "descriptor_valid": not validate_descriptor(descriptor),
            "handoff_valid": not handoff_failures,
            "receipt_valid": not receipt_failures,
            "adoption_valid": not adoption_failures,
            **negative,
            "handoff_failures": handoff_failures,
            "receipt_failures": receipt_failures,
            "adoption_failures": adoption_failures,
        }


def make_v2_fixture_handoff() -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "contract_version": V2_CONTRACT_VERSION,
        "task": "Create a film story package for a 60-second vertical cold-brew ad.",
        "brief_snapshot": "brief/brief.md",
        "locked_decisions": [
            {
                "artifact_id": "ART-BRIEF-001",
                "type": "creative_brief",
                "path": "brief/brief.md",
                "sha256": "a" * 64,
            }
        ],
        "requested_outputs": [
            {
                "output_id": "OUT-01",
                "type": "film.story_package",
                "path_root": "exchange/outputs",
            }
        ],
        "quality_targets": ["clear story progression", "continuous product handling"],
        "execution_mode": "inline",
    }


def run_v2_self_test() -> tuple[bool, dict[str, Any]]:
    descriptor = load_json(DESCRIPTOR_PATH)
    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-v2-selftest-") as raw:
        project = Path(raw)
        brief_path = project / "brief/brief.md"
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text("Evidence-bound cold-brew brief.", encoding="utf-8")
        handoff = make_v2_fixture_handoff()
        handoff["locked_decisions"][0]["sha256"] = sha256(brief_path)
        handoff_path = project / "exchange/v2-handoff.json"
        write_json(handoff_path, handoff)
        register_v2_fixture_handoff(
            project,
            handoff,
            handoff_path,
            descriptor,
            receipt_path="exchange/v2-receipt.json",
        )
        handoff_failures = validate_handoff(
            project,
            handoff,
            descriptor,
            handoff_path=handoff_path,
        )
        output_path = project / "exchange/outputs/story-package.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "# Northline Cold Brew Story Package\n\n"
            "Morning pressure resolves through a deliberate cold-brew ritual. "
            "The product remains visible through setup, pour, first sip, and end beat.\n",
            encoding="utf-8",
        )
        output_relative = output_path.relative_to(project).as_posix()
        receipt, receipt_path = build_receipt(
            project,
            handoff,
            handoff_path,
            {"film.story_package": output_relative},
            verdict="domain_accepted",
            receipt_output="exchange/v2-receipt.json",
        )
        receipt_failures = validate_receipt(
            project, handoff, handoff_path, receipt, receipt_path=receipt_path
        )

        negative: dict[str, bool] = {}
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["nested_dispatch"] = True
        negative["nested_dispatch_field_rejected"] = "nested_dispatch_forbidden" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["execution_mode"] = "codex_thread"
        negative["non_inline_execution_rejected"] = "nested_dispatch_forbidden" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["current_truth"] = {"status": "client_ready"}
        negative["copied_control_plane_rejected"] = "reserved_control_field" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["locked_decisions"][0]["sha256"] = "0" * 64
        negative["stale_locked_decision_rejected"] = "stale_locked_decision" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["brief_snapshot"] = "brief/unbound.md"
        negative["unbound_brief_snapshot_rejected"] = "unbound_brief_snapshot" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["requested_outputs"][0]["path_root"] = "05_最终交付_FinalDelivery"
        negative["protected_output_scope_rejected"] = "protected_output_scope" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["requested_outputs"][0]["path_root"] = "brief"
        negative["locked_input_output_overlap_rejected"] = "locked_input_output_overlap" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        mutated_handoff["requested_outputs"][0]["path_root"] = "BRIEF"
        negative["case_alias_locked_overlap_rejected"] = "locked_input_output_overlap" in failure_ids(
            validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
        )
        mutated_handoff = copy.deepcopy(handoff)
        duplicate_request = copy.deepcopy(mutated_handoff["requested_outputs"][0])
        duplicate_request["output_id"] = "OUT-02"
        duplicate_request["path_root"] = "exchange/outputs-two"
        mutated_handoff["requested_outputs"].append(duplicate_request)
        negative["duplicate_requested_output_type_rejected"] = (
            "duplicate_requested_output_type"
            in failure_ids(
                validate_handoff(project, mutated_handoff, descriptor, handoff_path=handoff_path)
            )
        )
        unregistered_path = project / "exchange/unregistered-handoff.json"
        write_json(unregistered_path, handoff)
        negative["unregistered_handoff_rejected"] = "missing_handoff_registration" in failure_ids(
            validate_handoff(project, handoff, descriptor, handoff_path=unregistered_path)
        )
        mutated_receipt = copy.deepcopy(receipt)
        mutated_receipt["client_ready"] = False
        negative["reserved_readiness_claim_rejected"] = "reserved_readiness_claim" in failure_ids(
            validate_receipt(
                project, handoff, handoff_path, mutated_receipt, receipt_path=receipt_path
            )
        )
        mutated_receipt = copy.deepcopy(receipt)
        mutated_receipt["domain_qa"]["client_ready"] = False
        negative["nested_domain_control_claim_rejected"] = "invalid_domain_qa" in failure_ids(
            validate_receipt(
                project, handoff, handoff_path, mutated_receipt, receipt_path=receipt_path
            )
        )
        mutated_receipt = copy.deepcopy(receipt)
        mutated_receipt["domain_qa"]["checks"] = [{"claim": "pass"}]
        negative["non_string_domain_check_rejected"] = "invalid_domain_qa" in failure_ids(
            validate_receipt(
                project, handoff, handoff_path, mutated_receipt, receipt_path=receipt_path
            )
        )
        mutated_receipt = copy.deepcopy(receipt)
        mutated_receipt["outputs"][0]["sha256"] = "0" * 64
        negative["output_hash_mismatch_rejected"] = "output_hash_mismatch" in failure_ids(
            validate_receipt(
                project, handoff, handoff_path, mutated_receipt, receipt_path=receipt_path
            )
        )
        mutated_receipt = copy.deepcopy(receipt)
        mutated_receipt["outputs"] = []
        negative["empty_completed_receipt_rejected"] = "empty_completed_receipt" in failure_ids(
            validate_receipt(
                project, handoff, handoff_path, mutated_receipt, receipt_path=receipt_path
            )
        )
        needs_user_handoff = copy.deepcopy(handoff)
        needs_user_handoff["requested_outputs"][0]["path_root"] = "needs-user/outputs"
        needs_user_handoff_path = project / "exchange/v2-needs-user-handoff.json"
        write_json(needs_user_handoff_path, needs_user_handoff)
        register_v2_fixture_handoff(
            project,
            needs_user_handoff,
            needs_user_handoff_path,
            descriptor,
            receipt_path="needs-user/receipt.json",
        )
        needs_user, needs_user_path = build_receipt(
            project,
            needs_user_handoff,
            needs_user_handoff_path,
            {},
            verdict="needs_user",
            open_questions=["Which approved end-card line should the specialist use?"],
            receipt_output="needs-user/receipt.json",
        )
        needs_user_failures = validate_receipt(
            project,
            needs_user_handoff,
            needs_user_handoff_path,
            needs_user,
            receipt_path=needs_user_path,
        )
        failed_handoff = copy.deepcopy(handoff)
        failed_handoff["requested_outputs"][0]["path_root"] = "failed/outputs"
        failed_handoff_path = project / "exchange/v2-failed-handoff.json"
        write_json(failed_handoff_path, failed_handoff)
        register_v2_fixture_handoff(
            project,
            failed_handoff,
            failed_handoff_path,
            descriptor,
            receipt_path="failed/receipt.json",
        )
        failed, failed_path = build_receipt(
            project,
            failed_handoff,
            failed_handoff_path,
            {},
            v2_status="failed",
            limitations=["Specialist processing failed before producing an artifact."],
            receipt_output="failed/receipt.json",
        )
        failed_receipt_failures = validate_receipt(
            project,
            failed_handoff,
            failed_handoff_path,
            failed,
            receipt_path=failed_path,
        )
        try:
            build_receipt(
                project,
                handoff,
                handoff_path,
                {"film.story_package": output_relative},
                verdict="domain_accepted",
            )
        except ValueError as exc:
            negative["implicit_v2_receipt_path_rejected"] = "explicit ADCO-registered" in str(exc)
        else:
            negative["implicit_v2_receipt_path_rejected"] = False
        try:
            build_receipt(
                project,
                handoff,
                handoff_path,
                {"film.story_package": output_relative},
                verdict="domain_accepted",
                receipt_output="exchange/v2-receipt.json",
            )
        except ValueError as exc:
            negative["existing_v2_receipt_rejected"] = "already exists" in str(exc)
        else:
            negative["existing_v2_receipt_rejected"] = False
        try:
            build_receipt(
                project,
                handoff,
                handoff_path,
                {"film.story_package": output_relative},
                verdict="domain_accepted",
                receipt_output="Exchange/v2-receipt.json",
            )
        except ValueError as exc:
            negative["receipt_case_alias_rejected"] = "does not match" in str(exc)
        else:
            negative["receipt_case_alias_rejected"] = False
        invalid_handoff = copy.deepcopy(handoff)
        invalid_handoff["requested_outputs"][0]["path_root"] = "invalid/outputs"
        invalid_handoff_path = project / "exchange/v2-invalid-handoff.json"
        write_json(invalid_handoff_path, invalid_handoff)
        register_v2_fixture_handoff(
            project,
            invalid_handoff,
            invalid_handoff_path,
            descriptor,
            receipt_path="invalid/receipt.json",
        )
        invalid_receipt_path = project / "invalid/receipt.json"
        try:
            build_receipt(
                project,
                invalid_handoff,
                invalid_handoff_path,
                {},
                verdict="needs_user",
                open_questions=[""],
                receipt_output="invalid/receipt.json",
            )
        except ValueError as exc:
            negative["invalid_receipt_not_persisted"] = (
                "before write" in str(exc) and not invalid_receipt_path.exists()
            )
        else:
            negative["invalid_receipt_not_persisted"] = False
        original_brief = brief_path.read_text(encoding="utf-8")
        brief_path.write_text("tampered locked brief", encoding="utf-8")
        negative["locked_input_tamper_rejected_at_receipt"] = "stale_locked_decision" in failure_ids(
            validate_receipt(
                project, handoff, handoff_path, receipt, receipt_path=receipt_path
            )
        )
        brief_path.write_text(original_brief, encoding="utf-8")
        mutated_receipt = copy.deepcopy(receipt)
        mutated_receipt["open_questions"] = [{"id": "Q-001", "question": "Unexpected question"}]
        negative["completed_questions_rejected"] = "invalid_open_questions" in failure_ids(
            validate_receipt(
                project, handoff, handoff_path, mutated_receipt, receipt_path=receipt_path
            )
        )
        mutated_receipt = copy.deepcopy(failed)
        mutated_receipt["outputs"] = copy.deepcopy(receipt["outputs"])
        negative["failed_outputs_rejected"] = "invalid_status_outputs" in failure_ids(
            validate_receipt(
                project,
                failed_handoff,
                failed_handoff_path,
                mutated_receipt,
                receipt_path=failed_path,
            )
        )
        adoption_failures = validate_adoption(project, handoff, receipt_path, receipt, {})
        compact_handoff = set(handoff) == V2_HANDOFF_FIELDS
        compact_receipt = set(receipt) == V2_RECEIPT_FIELDS
        output_hashes_only = (
            "handoff_sha256" not in receipt
            and "descriptor_sha256" not in receipt
            and set(receipt["outputs"][0]) == V2_OUTPUT_FIELDS
            and receipt["outputs"][0]["sha256"] == sha256(output_path)
        )
        control_fields_absent = not (
            (set(handoff) | set(receipt)) & V2_FORBIDDEN_CONTROL_FIELDS
        )
        ok = all(
            [
                not handoff_failures,
                not receipt_failures,
                not needs_user_failures,
                not failed_receipt_failures,
                receipt_path.is_file(),
                needs_user_path.is_file(),
                failed_path.is_file(),
                compact_handoff,
                compact_receipt,
                output_hashes_only,
                control_fields_absent,
                "v2_adoption_owned_by_adco" in failure_ids(adoption_failures),
                *negative.values(),
            ]
        )
        return ok, {
            "descriptor_supports_v1_v2": descriptor.get("supported_contract_versions")
            == list(SUPPORTED_CONTRACT_VERSIONS),
            "handoff_valid": not handoff_failures,
            "compact_handoff_valid": compact_handoff,
            "receipt_valid": not receipt_failures,
            "compact_receipt_valid": compact_receipt,
            "needs_user_receipt_valid": not needs_user_failures,
            "explicit_failed_receipt_valid": not failed_receipt_failures,
            "output_hashes_only": output_hashes_only,
            "adco_control_fields_absent": control_fields_absent,
            "adoption_owned_by_adco": "v2_adoption_owned_by_adco" in failure_ids(adoption_failures),
            **negative,
            "handoff_failures": handoff_failures,
            "receipt_failures": receipt_failures,
            "needs_user_failures": needs_user_failures,
            "failed_receipt_failures": failed_receipt_failures,
        }


def run_self_test() -> tuple[bool, dict[str, Any]]:
    v1_ok, v1_report = run_v1_self_test()
    v2_ok, v2_report = run_v2_self_test()
    return v1_ok and v2_ok, {
        "v1_read_compatibility": v1_ok,
        "v2_roundtrip_valid": v2_ok,
        **{f"v1_{key}": value for key, value in v1_report.items() if isinstance(value, bool)},
        **{f"v2_{key}": value for key, value in v2_report.items() if isinstance(value, bool)},
        "handoff_failures": [
            *[f"v1: {item}" for item in v1_report.get("handoff_failures", [])],
            *[f"v2: {item}" for item in v2_report.get("handoff_failures", [])],
        ],
        "receipt_failures": [
            *[f"v1: {item}" for item in v1_report.get("receipt_failures", [])],
            *[f"v2: {item}" for item in v2_report.get("receipt_failures", [])],
            *[f"v2 needs_user: {item}" for item in v2_report.get("needs_user_failures", [])],
            *[f"v2 failed: {item}" for item in v2_report.get("failed_receipt_failures", [])],
        ],
        "adoption_failures": v1_report.get("adoption_failures", []),
    }


def import_adco(adco_repo: Path) -> Any:
    tools_path = adco_repo / "tools"
    if not (tools_path / "ad_creative_operator.py").is_file():
        raise ValueError(f"ADCO tools not found: {tools_path}")
    sys.path.insert(0, str(tools_path))
    sys.modules.pop("ad_creative_operator", None)
    return importlib.import_module("ad_creative_operator")


def ensure_adco_exchange_project(adco: Any, project: Path) -> None:
    ensure_delivery = getattr(adco, "ensure_delivery_project", None)
    if callable(ensure_delivery):
        ensure_delivery(project)
        return
    adco.ensure_project(project)


def adco_exchange_receipt_output(adco: Any, project: Path, handoff_path: Path) -> str | None:
    handoff = load_json(handoff_path)
    handoff_relative = handoff_path.relative_to(project).as_posix()
    _, rows = adco.read_csv_rows(
        project / "AD-creative/orchestrator/specialist_exchange/exchange_index.csv"
    )
    matches = [row for row in rows if row.get("handoff_path") == handoff_relative]
    if len(matches) != 1 or not matches[0].get("receipt_path"):
        raise ValueError("ADCO exchange index does not identify one receipt path")
    receipt_output = str(matches[0]["receipt_path"])
    if handoff.get("contract_version") == V1_CONTRACT_VERSION:
        owned_receipt = handoff.get("scope", {}).get("receipt_path")
        if not nonempty(owned_receipt) or normalized_path(receipt_output) != normalized_path(owned_receipt):
            raise ValueError("ADCO v1 exchange index receipt path disagrees with handoff scope")
        return None
    return receipt_output


def receipt_output_entries(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    field = "outputs" if receipt.get("contract_version") == V2_CONTRACT_VERSION else "output_artifacts"
    entries = receipt.get(field)
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise ValueError(f"receipt {field} must contain output objects")
    return entries


def receipt_output_id(entry: dict[str, Any]) -> str:
    value = entry.get("output_id") or entry.get("provider_artifact_id")
    if not nonempty(value):
        raise ValueError("receipt output identity is missing")
    return str(value)


def add_adco_work_and_input(adco: Any, project: Path) -> str:
    source = project / "AD-creative/proposal_architecture/specialist_input.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "Brand: Northline Cold Brew\nDeliverable: 60-second vertical film\n"
        "Audience: urban professionals\nConstraint: no unapproved logo, packaging, or mandatory copy.\n",
        encoding="utf-8",
    )
    work_path = project / "AD-creative/orchestrator/work_items.csv"
    work_fields, work_rows = adco.read_csv_rows(work_path)
    work_rows.append(
        {
            "work_id": "WORK-SPX-DIR-001",
            "stage": "specialist_handoff",
            "title": "DIRcreative cold-brew film story package",
            "objective": "Create a bounded internal 60-second vertical film story package.",
            "owner_agent": "Main Controller",
            "status": "ready",
            "priority": "high",
            "input_refs": "ART-DIR-INPUT-001",
            "output_artifacts": "",
            "linked_requirements": "",
            "linked_source_events": "",
            "linked_references": "",
            "linked_assets": "",
            "linked_slides": "",
            "blocked_by": "",
            "gate_required": "creative-quality-gate",
            "client_visibility": "internal_only",
            "created_at": "2026-07-10T00:00:00Z",
            "updated_at": "2026-07-10T00:00:00Z",
            "supersedes_work_id": "",
        }
    )
    adco.write_csv_rows(work_path, work_fields, work_rows)
    artifact_path = project / "AD-creative/orchestrator/artifact_index.csv"
    fields, rows = adco.read_csv_rows(artifact_path)
    rows.append(
        {
            "artifact_id": "ART-DIR-INPUT-001",
            "artifact_type": "proposal_structure",
            "path": str(source.relative_to(project)),
            "stage": "proposal_architecture",
            "version": "v001",
            "status": "done",
            "visibility": "internal_only",
            "source_event_ids": "",
            "linked_requirements": "",
            "linked_work_items": "WORK-SPX-DIR-001",
            "linked_references": "",
            "linked_assets": "",
            "gate_status": "PASS",
            "supersedes_artifact_id": "",
            "created_at": "2026-07-10T00:00:00Z",
            "updated_at": "2026-07-10T00:00:00Z",
            "sha256": sha256(source),
            "size_bytes": str(source.stat().st_size),
            "derived_from_artifact_id": "",
            "derived_from_sha256": "",
        }
    )
    adco.write_csv_rows(artifact_path, fields, rows)
    return "ART-DIR-INPUT-001"


def run_adco_bilateral(adco_repo: Path) -> tuple[bool, dict[str, Any]]:
    adco = import_adco(adco_repo.resolve())
    descriptor = load_json(DESCRIPTOR_PATH)
    report: dict[str, Any] = {}
    positive_contract_version = ""
    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-bilateral-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        handoff, handoff_path = adco.create_specialist_handoff(
            project,
            work_id="WORK-SPX-DIR-001",
            profile_id=PROFILE_ID,
            objective="Create a bounded internal 60-second vertical film story package.",
            input_artifact_ids=[input_id],
            expected_output_kinds=["film.story_package"],
            required_capabilities=["film.story_package"],
            descriptor_path=DESCRIPTOR_PATH,
            execution_mode="inline",
            workspace_mode="isolated_workspace",
        )
        positive_contract_version = str(handoff.get("contract_version", ""))
        handoff_failures = validate_handoff(
            project,
            handoff,
            descriptor,
            handoff_path=handoff_path,
        )
        story_path = write_story_package(project, handoff)
        receipt, receipt_path = build_receipt(
            project,
            handoff,
            handoff_path,
            {"film.story_package": story_path},
            verdict="draft_accepted_with_limitations",
            limitations=["Logo and mandatory end-card copy remain unlocked."],
            receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
        )
        receipt_failures = validate_receipt(
            project, handoff, handoff_path, receipt, receipt_path=receipt_path
        )
        output = receipt_output_entries(receipt)[0]
        adoption, adoption_path = adco.adopt_specialist_receipt(
            project,
            handoff_path=handoff_path,
            receipt_path=receipt_path,
            decision="partial_adopt",
            reason="Accept the internal film draft with explicit client locks.",
            output_mappings={
                receipt_output_id(output): "AD-creative/film/story_package_v001.md"
            },
        )
        adoption_failures = (
            []
            if handoff.get("contract_version") == V2_CONTRACT_VERSION
            else validate_adoption(project, handoff, receipt_path, receipt, adoption)
        )
        if handoff.get("contract_version") == V2_CONTRACT_VERSION and adoption.get("decision_owner") != "adco":
            adoption_failures.append(failure("invalid_adoption_owner", "v2 adoption must remain ADCO-owned"))
        validation_errors, _ = adco.validate(project)
        report.update(
            {
                "positive_handoff_valid": not handoff_failures,
                "positive_receipt_valid": not receipt_failures,
                "positive_adoption_valid": not adoption_failures,
                "adco_project_validation_valid": not validation_errors,
                "adoption_path_exists": adoption_path is not None and adoption_path.is_file(),
                "handoff_failures": handoff_failures,
                "receipt_failures": receipt_failures,
                "adoption_failures": adoption_failures,
                "adco_validation_errors": validation_errors,
            }
        )

    def adco_rejects_adoption_target(target: str) -> bool:
        with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-target-") as raw:
            project = Path(raw)
            ensure_adco_exchange_project(adco, project)
            input_id = add_adco_work_and_input(adco, project)
            handoff, handoff_path = adco.create_specialist_handoff(
                project,
                work_id="WORK-SPX-DIR-001",
                profile_id=PROFILE_ID,
                objective="Create a bounded story package.",
                input_artifact_ids=[input_id],
                expected_output_kinds=["film.story_package"],
                required_capabilities=["film.story_package"],
                descriptor_path=DESCRIPTOR_PATH,
                execution_mode="inline",
                workspace_mode="isolated_workspace",
            )
            story_path = write_story_package(project, handoff)
            receipt, receipt_path = build_receipt(
                project,
                handoff,
                handoff_path,
                {"film.story_package": story_path},
                verdict="domain_accepted",
                receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
            )
            output = receipt_output_entries(receipt)[0]
            try:
                adco.adopt_specialist_receipt(
                    project,
                    handoff_path=handoff_path,
                    receipt_path=receipt_path,
                    decision="adopt",
                    reason="negative protocol target test",
                    output_mappings={receipt_output_id(output): target},
                )
            except (ValueError, OSError, StopIteration):
                return True
            return False

    def adco_rejects_single_output_alias(alias_kind: str) -> bool:
        with tempfile.TemporaryDirectory(prefix=f"dircreative-adco-native-{alias_kind}-") as raw:
            project = Path(raw)
            ensure_adco_exchange_project(adco, project)
            input_id = add_adco_work_and_input(adco, project)
            handoff, handoff_path = adco.create_specialist_handoff(
                project,
                work_id="WORK-SPX-DIR-001",
                profile_id=PROFILE_ID,
                objective="Create a bounded story package.",
                input_artifact_ids=[input_id],
                expected_output_kinds=["film.story_package"],
                required_capabilities=["film.story_package"],
                descriptor_path=DESCRIPTOR_PATH,
                execution_mode="inline",
                workspace_mode="isolated_workspace",
            )
            story_path = write_story_package(project, handoff)
            receipt, receipt_path = build_receipt(
                project,
                handoff,
                handoff_path,
                {"film.story_package": story_path},
                verdict="domain_accepted",
                receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
            )
            source_path = project / story_path
            alias_path = source_path.with_name(f"story_package_{alias_kind}.md")
            if alias_kind == "symlink":
                alias_path.symlink_to(source_path)
            else:
                alias_path.hardlink_to(source_path)
            bad = copy.deepcopy(receipt)
            bad_output = receipt_output_entries(bad)[0]
            bad_output["path"] = str(alias_path.relative_to(project))
            write_json(receipt_path, bad)
            try:
                adco.adopt_specialist_receipt(
                    project,
                    handoff_path=handoff_path,
                    receipt_path=receipt_path,
                    decision="adopt",
                    reason=f"negative {alias_kind} output test",
                    output_mappings={
                        receipt_output_id(bad_output): f"AD-creative/film/{alias_kind}.md"
                    },
                )
            except (ValueError, OSError, StopIteration):
                return True
            return False

    def provider_rejects_mismatched_v1_receipt_index() -> bool:
        with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-v1-index-") as raw:
            project = Path(raw)
            ensure_adco_exchange_project(adco, project)
            input_id = add_adco_work_and_input(adco, project)
            handoff, handoff_path = adco.create_specialist_handoff(
                project,
                work_id="WORK-SPX-DIR-001",
                profile_id=PROFILE_ID,
                objective="Verify v1 receipt ownership.",
                input_artifact_ids=[input_id],
                expected_output_kinds=["film.story_package"],
                required_capabilities=["film.story_package"],
                descriptor_path=DESCRIPTOR_PATH,
                execution_mode="inline",
                workspace_mode="isolated_workspace",
            )
            if handoff.get("contract_version") != V1_CONTRACT_VERSION:
                raise ValueError("v1 receipt-index check is not applicable to a v2 handoff")
            index_path = project / "AD-creative/orchestrator/specialist_exchange/exchange_index.csv"
            fields, rows = adco.read_csv_rows(index_path)
            handoff_relative = handoff_path.relative_to(project).as_posix()
            row = next(item for item in rows if item.get("handoff_path") == handoff_relative)
            row["receipt_path"] = "AD-creative/workspaces/WORK-SPX-DIR-001/specialists/tampered.json"
            adco.write_csv_rows(index_path, fields, rows)
            try:
                adco_exchange_receipt_output(adco, project, handoff_path)
            except ValueError as exc:
                return "receipt path disagrees with handoff scope" in str(exc)
            return False

    upstream_safety: dict[str, bool] = {
        "adco_rejects_control_plane_adoption": adco_rejects_adoption_target(
            "AD-creative/film/../orchestrator/injected.md"
        ),
        "adco_rejects_final_delivery_adoption": adco_rejects_adoption_target(
            "./05_最终交付_FinalDelivery/injected.md"
        ),
        "adco_rejects_symlink_output": adco_rejects_single_output_alias("symlink"),
        "adco_rejects_hardlink_output": adco_rejects_single_output_alias("hardlink"),
    }
    if positive_contract_version == V1_CONTRACT_VERSION:
        upstream_safety["provider_rejects_mismatched_v1_receipt_index"] = (
            provider_rejects_mismatched_v1_receipt_index()
        )
    else:
        report["v1_receipt_index_check"] = "not_applicable_v2_run"
    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-negative-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        handoff, handoff_path = adco.create_specialist_handoff(
            project,
            work_id="WORK-SPX-DIR-001",
            profile_id=PROFILE_ID,
            objective="Create a bounded story package.",
            input_artifact_ids=[input_id],
            expected_output_kinds=["film.story_package"],
            required_capabilities=["film.story_package"],
            descriptor_path=DESCRIPTOR_PATH,
            execution_mode="inline",
            workspace_mode="isolated_workspace",
        )
        story_path = write_story_package(project, handoff)
        receipt, receipt_path = build_receipt(
            project,
            handoff,
            handoff_path,
            {"film.story_package": story_path},
            verdict="domain_accepted",
            receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
        )
        bad = copy.deepcopy(receipt)
        bad_output = receipt_output_entries(bad)[0]
        bad_output["type" if handoff.get("contract_version") == V2_CONTRACT_VERSION else "kind"] = (
            "film.unrequested_payload"
        )
        write_json(receipt_path, bad)
        try:
            adco.adopt_specialist_receipt(
                project,
                handoff_path=handoff_path,
                receipt_path=receipt_path,
                decision="adopt",
                reason="negative protocol test",
                output_mappings={receipt_output_id(bad_output): "AD-creative/film/unrequested.md"},
            )
        except (ValueError, OSError, StopIteration):
            upstream_safety["adco_rejects_unrequested_output"] = True
        else:
            upstream_safety["adco_rejects_unrequested_output"] = False

    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-outputless-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        handoff, handoff_path = adco.create_specialist_handoff(
            project,
            work_id="WORK-SPX-DIR-001",
            profile_id=PROFILE_ID,
            objective="Create a bounded story package.",
            input_artifact_ids=[input_id],
            expected_output_kinds=["film.story_package"],
            required_capabilities=["film.story_package"],
            descriptor_path=DESCRIPTOR_PATH,
            execution_mode="inline",
            workspace_mode="isolated_workspace",
        )
        try:
            receipt, receipt_path = build_receipt(
                project,
                handoff,
                handoff_path,
                {},
                verdict="domain_accepted",
                receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
            )
        except ValueError:
            upstream_safety["provider_rejects_outputless_completion"] = (
                handoff.get("contract_version") == V2_CONTRACT_VERSION
            )
        else:
            try:
                adco.adopt_specialist_receipt(
                    project,
                    handoff_path=handoff_path,
                    receipt_path=receipt_path,
                    decision="adopt",
                    reason="negative protocol test",
                    output_mappings={},
                )
            except (ValueError, OSError, StopIteration):
                upstream_safety["adco_rejects_outputless_completion"] = True
            else:
                upstream_safety["adco_rejects_outputless_completion"] = False

    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-questions-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        handoff, handoff_path = adco.create_specialist_handoff(
            project,
            work_id="WORK-SPX-DIR-001",
            profile_id=PROFILE_ID,
            objective="Return unresolved client choices as structured questions.",
            input_artifact_ids=[input_id],
            expected_output_kinds=["film.story_package"],
            required_capabilities=["workflow.needs_user_return"],
            descriptor_path=DESCRIPTOR_PATH,
            execution_mode="inline",
            workspace_mode="isolated_workspace",
        )
        story_path = write_story_package(project, handoff)
        duplicate_questions: list[Any] = [
            "Confirm duration.",
            "Confirm product format.",
        ]
        if handoff.get("contract_version") == V1_CONTRACT_VERSION:
            duplicate_questions = [
                {"id": "Q-DUPLICATE", "question": "Confirm duration."},
                {"id": "Q-DUPLICATE", "question": "Confirm product format."},
            ]
        receipt, receipt_path = build_receipt(
            project,
            handoff,
            handoff_path,
            {}
            if handoff.get("contract_version") == V2_CONTRACT_VERSION
            else {"film.story_package": story_path},
            verdict="needs_user",
            open_questions=duplicate_questions,
            receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
        )
        if handoff.get("contract_version") == V2_CONTRACT_VERSION:
            receipt["open_questions"][1]["id"] = receipt["open_questions"][0]["id"]
            write_json(receipt_path, receipt)
        upstream_safety["provider_rejects_duplicate_question_ids"] = (
            "invalid_open_questions"
            in failure_ids(
                validate_receipt(
                    project, handoff, handoff_path, receipt, receipt_path=receipt_path
                )
            )
        )

    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-physical-output-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        handoff, handoff_path = adco.create_specialist_handoff(
            project,
            work_id="WORK-SPX-DIR-001",
            profile_id=PROFILE_ID,
            objective="Create a story package and treatment as distinct artifacts.",
            input_artifact_ids=[input_id],
            expected_output_kinds=["film.story_package", "film.treatment"],
            required_capabilities=["film.story_package", "film.treatment"],
            descriptor_path=DESCRIPTOR_PATH,
            execution_mode="inline",
            workspace_mode="isolated_workspace",
        )
        story_path = write_story_package(project, handoff)
        if handoff.get("contract_version") == V2_CONTRACT_VERSION:
            treatment_request = next(
                item
                for item in handoff["requested_outputs"]
                if isinstance(item, dict) and item.get("type") == "film.treatment"
            )
            treatment_path = project / str(treatment_request["path_root"]) / "treatment.md"
        else:
            treatment_path = (project / story_path).with_name("treatment.md")
        treatment_path.parent.mkdir(parents=True, exist_ok=True)
        treatment_path.write_text("Distinct treatment before alias mutation.\n", encoding="utf-8")
        treatment_relative = treatment_path.relative_to(project).as_posix()
        receipt, receipt_path = build_receipt(
            project,
            handoff,
            handoff_path,
            {"film.story_package": story_path, "film.treatment": treatment_relative},
            verdict="domain_accepted",
            receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
        )
        treatment_path.unlink()
        treatment_path.hardlink_to(project / story_path)
        outputs = receipt_output_entries(receipt)
        outputs[1]["sha256"] = sha256(treatment_path)
        write_json(receipt_path, receipt)
        try:
            adco.adopt_specialist_receipt(
                project,
                handoff_path=handoff_path,
                receipt_path=receipt_path,
                decision="adopt",
                reason="negative physical output reuse test",
                output_mappings={
                    receipt_output_id(outputs[0]): "AD-creative/film/story.md",
                    receipt_output_id(outputs[1]): "AD-creative/film/treatment.md",
                },
            )
        except (ValueError, OSError, StopIteration):
            upstream_safety["adco_rejects_physical_output_reuse"] = True
        else:
            upstream_safety["adco_rejects_physical_output_reuse"] = False

    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-auth-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        try:
            adco.create_specialist_handoff(
                project,
                work_id="WORK-SPX-DIR-001",
                profile_id=PROFILE_ID,
                objective="Generate a real asset.",
                input_artifact_ids=[input_id],
                expected_output_kinds=["film.story_package"],
                required_capabilities=["film.story_package"],
                descriptor_path=DESCRIPTOR_PATH,
                execution_mode="inline",
                workspace_mode="isolated_workspace",
                generation_mode="real_media",
                generation_authorized=True,
                authorization_ref="AD-creative/orchestrator/missing-authorization.json",
            )
        except (ValueError, OSError):
            upstream_safety["adco_rejects_missing_generation_authorization"] = True
        else:
            upstream_safety["adco_rejects_missing_generation_authorization"] = False

    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-readonly-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        handoff, handoff_path = adco.create_specialist_handoff(
            project,
            work_id="WORK-SPX-DIR-001",
            profile_id=PROFILE_ID,
            objective="Review the story package without writable output.",
            input_artifact_ids=[input_id],
            expected_output_kinds=["film.story_package"],
            required_capabilities=["film.story_package"],
            descriptor_path=DESCRIPTOR_PATH,
            execution_mode="inline",
            workspace_mode="read_only",
        )
        read_only_failures = validate_handoff(
            project,
            handoff,
            descriptor,
            handoff_path=handoff_path,
        )
        upstream_safety["adco_v2_omits_workspace_control"] = (
            handoff.get("contract_version") != V2_CONTRACT_VERSION
            or (
                handoff.get("execution_mode") == "inline"
                and "workspace_mode" not in handoff
            )
        )
        if read_only_failures:
            upstream_safety["adco_read_only_return_roundtrip_valid"] = False
        else:
            read_only_questions: list[Any] = [
                "Which client lock should ADCO resolve before a writable story pass?"
            ]
            if handoff.get("contract_version") == V1_CONTRACT_VERSION:
                read_only_questions = [
                    {
                        "id": "Q-READ-ONLY-1",
                        "question": "Which client lock should ADCO resolve before a writable story pass?",
                    }
                ]
            receipt, receipt_path = build_receipt(
                project,
                handoff,
                handoff_path,
                {},
                verdict="needs_user",
                open_questions=read_only_questions,
                receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
            )
            receipt_failures = validate_receipt(
                project, handoff, handoff_path, receipt, receipt_path=receipt_path
            )
            try:
                adoption, _ = adco.adopt_specialist_receipt(
                    project,
                    handoff_path=handoff_path,
                    receipt_path=receipt_path,
                    decision="defer",
                    reason="Return the structured question without adopting an output.",
                    output_mappings={},
                )
            except (ValueError, OSError, StopIteration):
                upstream_safety["adco_read_only_return_roundtrip_valid"] = False
            else:
                adoption_valid = (
                    True
                    if handoff.get("contract_version") == V2_CONTRACT_VERSION
                    else not validate_adoption(project, handoff, receipt_path, receipt, adoption)
                )
                upstream_safety["adco_read_only_return_roundtrip_valid"] = (
                    not receipt_failures
                    and adoption_valid
                    and not adco.validate(project)[0]
                )

    with tempfile.TemporaryDirectory(prefix="dircreative-adco-native-hostscope-") as raw:
        project = Path(raw)
        ensure_adco_exchange_project(adco, project)
        input_id = add_adco_work_and_input(adco, project)
        handoff, handoff_path = adco.create_specialist_handoff(
            project,
            work_id="WORK-SPX-DIR-001",
            profile_id=PROFILE_ID,
            objective="Create a bounded story package.",
            input_artifact_ids=[input_id],
            expected_output_kinds=["film.story_package"],
            required_capabilities=["film.story_package"],
            descriptor_path=DESCRIPTOR_PATH,
            execution_mode="inline",
            workspace_mode="isolated_workspace",
        )
        story_path = write_story_package(project, handoff)
        receipt, receipt_path = build_receipt(
            project,
            handoff,
            handoff_path,
            {"film.story_package": story_path},
            verdict="domain_accepted",
            receipt_output=adco_exchange_receipt_output(adco, project, handoff_path),
        )
        output = receipt_output_entries(receipt)[0]
        current_truth = project / "AD-creative/orchestrator/current_truth.md"
        current_truth.write_text(current_truth.read_text(encoding="utf-8") + "\nunreported mutation\n", encoding="utf-8")
        try:
            adco.adopt_specialist_receipt(
                project,
                handoff_path=handoff_path,
                receipt_path=receipt_path,
                decision="adopt",
                reason="negative host scope test",
                output_mappings={
                    receipt_output_id(output): "AD-creative/film/hostscope-negative.md"
                },
            )
        except (ValueError, OSError, StopIteration):
            upstream_safety["adco_rejects_unreported_host_write"] = True
        else:
            upstream_safety["adco_rejects_unreported_host_write"] = False

    report.update(upstream_safety)
    positive = all(
        report[field]
        for field in [
            "positive_handoff_valid",
            "positive_receipt_valid",
            "positive_adoption_valid",
            "adco_project_validation_valid",
            "adoption_path_exists",
        ]
    )
    report["positive_roundtrip_valid"] = positive
    report["upstream_safety_valid"] = all(upstream_safety.values())
    return positive and report["upstream_safety_valid"], report


def print_report(title: str, ok: bool, report: dict[str, Any], marker: str) -> None:
    print(title)
    print("=" * 72)
    for key, value in report.items():
        if isinstance(value, bool):
            print(f"{key}: {str(value).lower()}")
    for key in ["handoff_failures", "receipt_failures", "adoption_failures", "adco_validation_errors"]:
        for item in report.get(key, []):
            print(f"- {key}: {item}")
    print(f"{marker}: {'PASS' if ok else 'BLOCKED'}")


def parse_artifacts(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--artifact must use KIND=project/relative/path")
        kind, path = value.split("=", 1)
        if not kind.strip() or not path.strip() or kind in result:
            raise ValueError("--artifact values must have unique non-empty kinds and paths")
        result[kind.strip()] = path.strip()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="DIRcreative provider bridge for ADCO specialist exchange v1/v2.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--adco-repo", help="Run a real temp-project roundtrip against this ADCO checkout.")
    subparsers = parser.add_subparsers(dest="command")

    handoff_parser = subparsers.add_parser("validate-handoff")
    handoff_parser.add_argument("--project-root", required=True)
    handoff_parser.add_argument("--handoff", required=True)
    handoff_parser.add_argument("--descriptor", default=str(DESCRIPTOR_PATH))

    receipt_parser = subparsers.add_parser("build-receipt")
    receipt_parser.add_argument("--project-root", required=True)
    receipt_parser.add_argument("--handoff", required=True)
    receipt_parser.add_argument("--descriptor", default=str(DESCRIPTOR_PATH))
    receipt_parser.add_argument("--artifact", action="append", default=[])
    receipt_state = receipt_parser.add_mutually_exclusive_group(required=True)
    receipt_state.add_argument("--domain-verdict", choices=sorted(VERDICTS))
    receipt_state.add_argument("--status", choices=sorted(V2_STATUSES), help="v2 compact receipt status")
    receipt_parser.add_argument("--receipt-output", help="v2 project-relative receipt path")
    receipt_parser.add_argument("--limitation", action="append", default=[])
    receipt_parser.add_argument("--open-question", action="append", default=[])

    receipt_validate_parser = subparsers.add_parser("validate-receipt")
    receipt_validate_parser.add_argument("--project-root", required=True)
    receipt_validate_parser.add_argument("--handoff", required=True)
    receipt_validate_parser.add_argument("--receipt", required=True)
    receipt_validate_parser.add_argument("--descriptor", default=str(DESCRIPTOR_PATH))

    adoption_parser = subparsers.add_parser("validate-adoption")
    adoption_parser.add_argument("--project-root", required=True)
    adoption_parser.add_argument("--handoff", required=True)
    adoption_parser.add_argument("--receipt", required=True)
    adoption_parser.add_argument("--adoption", required=True)
    adoption_parser.add_argument("--descriptor", default=str(DESCRIPTOR_PATH))

    args = parser.parse_args()
    if args.self_test:
        ok, report = run_self_test()
        print_report("DIRcreative ADCO Native Exchange Self-Test", ok, report, "ADCO_NATIVE_SELF_TEST")
        return 0 if ok else 1
    if args.adco_repo:
        try:
            ok, report = run_adco_bilateral(Path(args.adco_repo).expanduser().resolve())
        except Exception as exc:  # noqa: BLE001 - audit must report moving upstream failures
            print("DIRcreative ADCO Native Bilateral Audit")
            print("=" * 72)
            print(f"- bilateral_execution_error: {exc}")
            print("ADCO_NATIVE_BILATERAL: BLOCKED")
            return 1
        print_report("DIRcreative ADCO Native Bilateral Audit", ok, report, "ADCO_NATIVE_BILATERAL")
        return 0 if ok else 1
    if not args.command:
        parser.print_help()
        return 2
    project = Path(args.project_root).expanduser().resolve()
    handoff_path = Path(args.handoff).expanduser().resolve()
    handoff = load_json(handoff_path)
    descriptor = load_json(args.descriptor)
    handoff_failures = validate_handoff(
        project,
        handoff,
        descriptor,
        handoff_path=handoff_path,
    )
    if args.command == "validate-handoff":
        ok = not handoff_failures
        print_report("DIRcreative ADCO Native Handoff Audit", ok, {"handoff_valid": ok, "handoff_failures": handoff_failures}, "ADCO_NATIVE_HANDOFF")
        return 0 if ok else 1
    if handoff_failures:
        print_report("DIRcreative ADCO Native Exchange", False, {"handoff_failures": handoff_failures}, "ADCO_NATIVE_EXCHANGE")
        return 1
    if args.command == "build-receipt":
        if handoff.get("contract_version") == V2_CONTRACT_VERSION:
            questions: list[Any] = list(args.open_question)
        else:
            questions = [
                {"id": f"Q-{number}", "question": value}
                for number, value in enumerate(args.open_question, start=1)
            ]
        receipt, path = build_receipt(
            project,
            handoff,
            handoff_path,
            parse_artifacts(args.artifact),
            verdict=args.domain_verdict,
            v2_status=args.status,
            limitations=args.limitation,
            open_questions=questions,
            receipt_output=args.receipt_output,
        )
        failures = validate_receipt(
            project, handoff, handoff_path, receipt, receipt_path=path
        )
        print(f"RECEIPT={path}")
        print_report("DIRcreative ADCO Native Receipt Build", not failures, {"receipt_valid": not failures, "receipt_failures": failures}, "ADCO_NATIVE_RECEIPT")
        return 0 if not failures else 1
    receipt_path = Path(args.receipt).expanduser().resolve()
    receipt = load_json(receipt_path)
    receipt_failures = validate_receipt(
        project, handoff, handoff_path, receipt, receipt_path=receipt_path
    )
    if args.command == "validate-receipt":
        ok = not receipt_failures
        print_report("DIRcreative ADCO Native Receipt Audit", ok, {"receipt_valid": ok, "receipt_failures": receipt_failures}, "ADCO_NATIVE_RECEIPT")
        return 0 if ok else 1
    adoption = load_json(args.adoption)
    adoption_failures = validate_adoption(project, handoff, receipt_path, receipt, adoption)
    ok = not receipt_failures and not adoption_failures
    print_report(
        "DIRcreative ADCO Native Adoption Audit",
        ok,
        {"receipt_valid": not receipt_failures, "adoption_valid": not adoption_failures, "receipt_failures": receipt_failures, "adoption_failures": adoption_failures},
        "ADCO_NATIVE_ADOPTION",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
