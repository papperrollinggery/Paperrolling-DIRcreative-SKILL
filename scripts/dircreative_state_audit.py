#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat as stat_module
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CURRENT_SCHEMA_VERSION = "1.0.0"
DEFAULT_STATE_PATH = Path(".dircreative/state/current.json")
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/runtime-state.schema.json"
THREAD_PROOF_MAX_AGE = timedelta(hours=24)
LIFECYCLES = {"active", "superseded", "withdrawn", "archived", "removed"}
STORAGE_CLASSES = {"final", "necessary_archive", "regenerable_cache", "delete_candidate"}
STAGE_STATUSES = {"active", "needs_user", "blocked", "complete"}
ACCEPTANCE_STATUSES = {"not_requested", "pending", "accepted", "rejected"}
RECORD_KINDS = {
    "artifact",
    "run",
    "checkpoint",
    "receipt",
    "manifest",
    "generation_authorization",
    "thread",
    "reference_media",
    "generated_media",
    "preview",
    "cache",
    "final_delivery",
    "archive",
}
CONTROL_RECORD_KINDS = {"run", "checkpoint", "receipt", "manifest", "generation_authorization", "thread"}
OUTPUT_RECORD_KINDS = {
    "artifact",
    "reference_media",
    "generated_media",
    "preview",
    "final_delivery",
    "archive",
}
ARTIFACT_RECORD_KINDS = OUTPUT_RECORD_KINDS | {"cache"}


@dataclass(frozen=True)
class Finding:
    lane: str
    severity: str
    code: str
    message: str


def add(findings: list[Finding], lane: str, severity: str, code: str, message: str) -> None:
    findings.append(Finding(lane, severity, code, message))


def parse_rfc3339(value: Any) -> datetime | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})",
        value,
    ):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _json_type_matches(value: object, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def _resolve_schema_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported external runtime-state schema ref: {ref}")
    value: Any = root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"unresolved runtime-state schema ref: {ref}")
        value = value[part]
    if not isinstance(value, dict):
        raise ValueError(f"runtime-state schema ref is not an object: {ref}")
    return value


def _canonical_item(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_equal(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, (int, float)) and not isinstance(left, bool):
        return isinstance(right, (int, float)) and not isinstance(right, bool) and left == right
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and set(left) == set(right)
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    return type(left) is type(right) and left == right


def _schema_path(parent: str, key: object) -> str:
    return f"{parent}[{key}]" if isinstance(key, int) else f"{parent}.{key}"


def _builtin_schema_errors(
    value: object,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str,
) -> list[str]:
    errors: list[str] = []
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return _builtin_schema_errors(value, _resolve_schema_ref(root, ref), root, path)

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for item in all_of:
            if isinstance(item, dict):
                errors.extend(_builtin_schema_errors(value, item, root, path))

    condition = schema.get("if")
    if isinstance(condition, dict):
        condition_matches = not _builtin_schema_errors(value, condition, root, path)
        selected = schema.get("then") if condition_matches else schema.get("else")
        if isinstance(selected, dict):
            errors.extend(_builtin_schema_errors(value, selected, root, path))

    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        alternatives = [
            _builtin_schema_errors(value, item, root, path)
            for item in one_of
            if isinstance(item, dict)
        ]
        matching = [items for items in alternatives if not items]
        if len(matching) != 1:
            detail = min(alternatives, key=len)[0] if alternatives else "no valid branch"
            return [f"{path}: oneOf failed ({detail})"]

    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        alternatives = [
            _builtin_schema_errors(value, item, root, path)
            for item in any_of
            if isinstance(item, dict)
        ]
        if not any(not items for items in alternatives):
            detail = min(alternatives, key=len)[0] if alternatives else "no valid branch"
            return [f"{path}: anyOf failed ({detail})"]

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        expected_types = [expected_type]
    elif isinstance(expected_type, list):
        expected_types = [item for item in expected_type if isinstance(item, str)]
    else:
        expected_types = []
    if expected_types and not any(_json_type_matches(value, item) for item in expected_types):
        return [f"{path}: expected type {'|'.join(expected_types)}"]

    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append(f"{path}: value does not match const")
    enum = schema.get("enum")
    if isinstance(enum, list) and not any(_json_equal(value, item) for item in enum):
        errors.append(f"{path}: value is not in enum")

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    errors.append(f"{path}: missing required property {key}")
        properties = schema.get("properties")
        property_map = properties if isinstance(properties, dict) else {}
        for key, item_value in value.items():
            item_schema = property_map.get(key)
            if isinstance(item_schema, dict):
                errors.extend(_builtin_schema_errors(item_value, item_schema, root, _schema_path(path, key)))
            elif schema.get("additionalProperties", True) is False:
                errors.append(f"{path}: additional property not allowed: {key}")

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            errors.append(f"{path}: expected at least {min_items} items")
        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and len(value) > max_items:
            errors.append(f"{path}: expected at most {max_items} items")
        if schema.get("uniqueItems") is True:
            items = [_canonical_item(item) for item in value]
            if len(items) != len(set(items)):
                errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(_builtin_schema_errors(item, item_schema, root, _schema_path(path, index)))

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            errors.append(f"{path}: string is shorter than {min_length}")
        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            errors.append(f"{path}: string is longer than {max_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{path}: string does not match pattern")
        if schema.get("format") == "date-time" and parse_rfc3339(value) is None:
            errors.append(f"{path}: date-time must be RFC3339 with timezone")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        exclusive_minimum = schema.get("exclusiveMinimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}: number is below minimum {minimum}")
        if isinstance(exclusive_minimum, (int, float)) and value <= exclusive_minimum:
            errors.append(f"{path}: number must be above {exclusive_minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path}: number is above maximum {maximum}")
    return errors


def runtime_schema_errors(payload: object, *, force_builtin: bool = False) -> list[str]:
    nonfinite: list[str] = []

    def walk(value: object, path: str) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            nonfinite.append(f"{path}: non-finite JSON number is forbidden")
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, _schema_path(path, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, _schema_path(path, index))

    walk(payload, "$")
    if nonfinite:
        return nonfinite
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not force_builtin and not os.environ.get("DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"):
        try:
            from jsonschema import Draft202012Validator, FormatChecker
        except ImportError:
            pass
        else:
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            return [
                f"{'.'.join(str(item) for item in error.absolute_path) or '$'}: {error.message}"
                for error in sorted(
                    validator.iter_errors(payload),
                    key=lambda item: [str(part) for part in item.absolute_path],
                )
            ]
    return _builtin_schema_errors(payload, schema, schema, "$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_regular_file(path: Path) -> tuple[os.stat_result, str]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        stat = os.fstat(descriptor)
        if not stat_module.S_ISREG(stat.st_mode):
            raise ValueError("not a regular file")
        digest = hashlib.sha256()
        with os.fdopen(os.dup(descriptor), "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return stat, digest.hexdigest()
    finally:
        os.close(descriptor)


def inspect_regular_file_bytes(path: Path) -> tuple[os.stat_result, str, bytes]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        stat = os.fstat(descriptor)
        if not stat_module.S_ISREG(stat.st_mode):
            raise ValueError("not a regular file")
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        with os.fdopen(os.dup(descriptor), "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                chunks.append(chunk)
        return stat, digest.hexdigest(), b"".join(chunks)
    finally:
        os.close(descriptor)


def parse_semantic_legacy_document(data: bytes, suffix: str) -> tuple[Any | None, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "invalid_utf8"
    if suffix.casefold() == ".json":
        try:
            return (
                json.loads(
                    text,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError(f"non-finite JSON number: {value}")
                    ),
                ),
                "parsed",
            )
        except (json.JSONDecodeError, ValueError):
            return None, "invalid_json"
    if suffix.casefold() in {".yaml", ".yml"}:
        ruby = (
            "require 'yaml'; require 'json'; "
            "data = YAML.safe_load(STDIN.read, permitted_classes: [], permitted_symbols: [], aliases: false); "
            "STDOUT.write(JSON.generate(data))"
        )
        proc = subprocess.run(
            ["ruby", "-e", ruby],
            input=text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            return None, "invalid_yaml"
        try:
            return json.loads(proc.stdout), "parsed"
        except json.JSONDecodeError:
            return None, "invalid_yaml_json_projection"
    return None, "unsupported_format"


def canonical_authorization_scope(payload: dict[str, Any]) -> str:
    scope = {
        "work_id": payload.get("work_id"),
        "asset_ids": sorted(payload.get("asset_ids", [])),
        "expected_output_kinds": sorted(payload.get("expected_output_kinds", [])),
        "model_ids": sorted(payload.get("model_ids", [])),
    }
    canonical = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def bound_payload_file_matches(project_root: Path, record: dict[str, Any], field: str) -> bool:
    target = safe_project_path(project_root, record.get("canonical_path"))
    if target is None or target.suffix.casefold() != ".json":
        return False
    try:
        payload_file = load_state(target)
    except ValueError:
        return False
    return payload_file == {
        "record_id": record.get("record_id"),
        "kind": record.get("kind"),
        "payload": record.get(field),
    }


def build_thread_snapshot_index(
    snapshot: dict[str, Any] | None,
    findings: list[Finding],
) -> dict[str, dict[str, Any]]:
    if snapshot is None:
        return {}
    captured_at = parse_rfc3339(snapshot.get("captured_at")) if isinstance(snapshot, dict) else None
    now = datetime.now(timezone.utc)
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("schema_version") != "1.0.0"
        or snapshot.get("provider") != "codex_app.list_threads"
        or captured_at is None
        or captured_at > now + timedelta(minutes=5)
        or now - captured_at > timedelta(minutes=10)
        or not isinstance(snapshot.get("threads"), list)
    ):
        add(findings, "current", "P0", "invalid_thread_snapshot", "host thread snapshot is missing, stale, or malformed")
        return {}
    index: dict[str, dict[str, Any]] = {}
    for position, item in enumerate(snapshot["threads"]):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("thread_id"), str)
            or not item.get("thread_id")
            or not isinstance(item.get("host_id"), str)
            or item.get("status") not in {"active", "idle", "completed", "failed", "interrupted"}
            or not isinstance(item.get("archived"), bool)
            or not isinstance(item.get("confirmations"), list)
        ):
            add(findings, "current", "P0", "invalid_thread_snapshot", f"threads[{position}] is malformed")
            continue
        thread_id = item["thread_id"]
        if thread_id in index:
            add(findings, "current", "P0", "duplicate_snapshot_thread", f"duplicate host thread: {thread_id}")
            continue
        confirmation_index: dict[str, dict[str, Any]] = {}
        malformed_confirmation = False
        for confirmation in item["confirmations"]:
            if (
                not isinstance(confirmation, dict)
                or not isinstance(confirmation.get("confirmation_id"), str)
                or not confirmation.get("confirmation_id")
                or confirmation.get("actor_type") not in {"human", "client", "controller"}
                or not isinstance(confirmation.get("actor_id"), str)
                or not confirmation.get("actor_id")
            ):
                malformed_confirmation = True
                break
            confirmation_index[confirmation["confirmation_id"]] = confirmation
        if malformed_confirmation or len(confirmation_index) != len(item["confirmations"]):
            add(findings, "current", "P0", "invalid_thread_snapshot", f"threads[{position}] confirmations are malformed")
            continue
        item = dict(item)
        item["_confirmation_index"] = confirmation_index
        index[thread_id] = item
    return index


def safe_project_path(project_root: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = project_root / relative
    try:
        candidate.resolve(strict=False).relative_to(project_root.resolve())
    except ValueError:
        return None
    return candidate


def load_state(path: Path) -> dict[str, Any]:
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except FileNotFoundError as exc:
        raise ValueError(f"missing runtime state: {path}") from exc
    except OSError as exc:
        raise ValueError(f"unsafe runtime state path {path}: {exc}") from exc
    try:
        stat = os.fstat(descriptor)
        if not stat_module.S_ISREG(stat.st_mode) or stat.st_nlink != 1:
            raise ValueError(f"runtime state must be a regular non-hardlinked file: {path}")
        with os.fdopen(os.dup(descriptor), "r", encoding="utf-8") as handle:
            data = json.load(
                handle,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"non-finite JSON number: {value}")),
            )
    except (json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        raise ValueError(f"invalid JSON in runtime state {path}: {exc}") from exc
    finally:
        os.close(descriptor)
    if not isinstance(data, dict):
        raise ValueError("runtime state top level must be an object")
    return data


def record_index(records: Any, findings: list[Finding]) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        add(findings, "current", "P0", "records_not_array", "records must be an array")
        return {}
    index: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            add(findings, "current", "P0", "record_not_object", f"records[{position}] must be an object")
            continue
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            add(findings, "current", "P0", "missing_record_id", f"records[{position}] has no record_id")
            continue
        if record_id in index:
            add(findings, "current", "P0", "duplicate_record_id", f"duplicate record_id: {record_id}")
            continue
        index[record_id] = record
    return index


def validate_record_shape(record_id: str, record: dict[str, Any], findings: list[Finding]) -> None:
    if record.get("kind") not in RECORD_KINDS:
        add(findings, "current", "P0", "invalid_record_kind", f"{record_id} has invalid kind")
    revision = record.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        add(findings, "current", "P0", "invalid_revision", f"{record_id} revision must be a positive integer")
    lifecycle = record.get("lifecycle")
    if lifecycle not in LIFECYCLES:
        add(findings, "current", "P0", "invalid_lifecycle", f"{record_id} has invalid lifecycle")
    if record.get("storage_class") not in STORAGE_CLASSES:
        add(findings, "current", "P0", "invalid_storage_class", f"{record_id} has invalid storage_class")
    if not isinstance(record.get("logical_id"), str) or not record.get("logical_id"):
        add(findings, "current", "P0", "missing_logical_id", f"{record_id} has no logical_id")
    if not isinstance(record.get("durable"), bool) or not isinstance(record.get("regenerable"), bool):
        add(findings, "current", "P0", "invalid_durability", f"{record_id} durability flags must be booleans")
    if record.get("durable") is True and not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256") or "")):
        add(findings, "current", "P0", "missing_durable_hash", f"{record_id} durable file requires a SHA-256")
    if record.get("storage_class") == "final" and record.get("regenerable") is True:
        add(findings, "current", "P0", "final_marked_regenerable", f"{record_id} final storage cannot be regenerable")
    if record.get("storage_class") == "necessary_archive" and record.get("regenerable") is True:
        add(findings, "current", "P0", "archive_marked_regenerable", f"{record_id} necessary archive cannot be regenerable")
    if record.get("storage_class") == "regenerable_cache" and record.get("regenerable") is not True:
        add(findings, "current", "P0", "cache_not_regenerable", f"{record_id} regenerable cache must be regenerable")
    if record.get("kind") == "cache" and record.get("storage_class") != "regenerable_cache":
        add(findings, "current", "P0", "cache_misclassified", f"{record_id} cache kind must use regenerable_cache")
    for field in ("canonical_path", "original_path"):
        value = record.get(field)
        if value is not None and (
            not isinstance(value, str)
            or not value.strip()
            or Path(value).is_absolute()
            or ".." in Path(value).parts
        ):
            add(findings, "current", "P0", "unsafe_record_path", f"{record_id} has unsafe {field}")
    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        add(findings, "current", "P0", "missing_evidence", f"{record_id} has no typed evidence object")
    elif evidence.get("task_visibility") not in {"verified", "unverified", "not_applicable"}:
        add(findings, "current", "P0", "invalid_task_visibility", f"{record_id} has invalid task_visibility")
    kind_payloads = {
        "receipt": ("receipt", record.get("receipt")),
        "manifest": ("manifest", record.get("manifest")),
        "thread": ("thread", record.get("thread")),
        "generation_authorization": ("generation_authorization", record.get("generation_authorization")),
    }
    for owner_kind, (field, payload) in kind_payloads.items():
        if record.get("kind") == owner_kind and not isinstance(payload, dict):
            add(findings, "current", "P0", "missing_typed_payload", f"{record_id} {owner_kind} requires {field} payload")
        if record.get("kind") != owner_kind and payload is not None:
            add(findings, "current", "P0", "unexpected_typed_payload", f"{record_id} cannot carry {field} payload")
    thread = record.get("thread")
    if isinstance(thread, dict):
        output_status = thread.get("output_status")
        terminal_reason = thread.get("terminal_reason")
        terminal_reasons = {
            "completed",
            "adopted",
            "rejected",
            "failed",
            "system_error",
            "interrupted",
            "duplicate",
            "superseded",
            "abandoned",
        }
        if output_status == "active" and terminal_reason is not None:
            add(findings, "current", "P0", "active_thread_has_terminal_reason", f"{record_id} active thread cannot have a terminal reason")
        if output_status != "active" and terminal_reason not in terminal_reasons:
            add(findings, "current", "P0", "terminal_thread_missing_reason", f"{record_id} terminal thread requires a typed terminal reason")
        if output_status == "failed" and terminal_reason not in {"failed", "system_error"}:
            add(findings, "current", "P0", "failed_thread_reason_mismatch", f"{record_id} failed thread has an incompatible terminal reason")
        if output_status == "interrupted" and terminal_reason != "interrupted":
            add(findings, "current", "P0", "interrupted_thread_reason_mismatch", f"{record_id} interrupted thread must use terminal_reason interrupted")
    tombstone = record.get("tombstone")
    if lifecycle == "active" and tombstone is not None:
        add(findings, "current", "P0", "active_record_tombstoned", f"{record_id} is active but has a tombstone")
    if lifecycle in LIFECYCLES - {"active"}:
        if not isinstance(tombstone, dict) or not tombstone.get("reason") or not tombstone.get("recorded_at"):
            add(findings, "current", "P0", "missing_tombstone", f"{record_id} is non-active without a complete tombstone")
    if lifecycle == "removed" and (
        not isinstance(record.get("original_path"), str) or not record.get("original_path", "").strip()
    ):
        add(findings, "current", "P0", "removed_without_original_path", f"{record_id} removed record must retain original_path")
    if lifecycle == "removed":
        add(
            findings,
            "current",
            "P0",
            "live_removal_attestation_required",
            f"{record_id} removal cannot be authorized by a self-written tombstone; live host/controller evidence is required",
        )


def validate_supersession(
    index: dict[str, dict[str, Any]],
    projection: list[str],
    findings: list[Finding],
) -> None:
    projected = set(projection)
    for record_id, record in index.items():
        lifecycle = record.get("lifecycle")
        if lifecycle == "active" and record_id not in projected:
            add(findings, "current", "P0", "active_record_hidden", f"{record_id} is active but absent from current_projection")
        if lifecycle != "active" and record_id in projected:
            add(findings, "current", "P0", "tombstone_pollutes_current", f"{record_id} pollutes current projection")

        predecessor_id = record.get("supersedes_record_id")
        successor_id = record.get("superseded_by_record_id")
        if predecessor_id:
            predecessor = index.get(predecessor_id)
            if predecessor is None:
                add(findings, "current", "P0", "missing_superseded_record", f"{record_id} supersedes missing {predecessor_id}")
            else:
                if predecessor.get("superseded_by_record_id") != record_id:
                    add(findings, "current", "P0", "broken_supersession_link", f"{record_id} predecessor link is not reciprocal")
                if predecessor.get("logical_id") != record.get("logical_id"):
                    add(findings, "current", "P0", "cross_logical_supersession", f"{record_id} changes logical identity")
                if predecessor.get("lifecycle") != "superseded":
                    add(findings, "current", "P0", "invalid_predecessor_lifecycle", f"{predecessor_id} must be superseded")
                if not isinstance(predecessor.get("revision"), int) or predecessor.get("revision", 0) >= record.get("revision", 0):
                    add(findings, "current", "P0", "nonmonotonic_revision", f"{record_id} revision must exceed {predecessor_id}")
        if successor_id:
            successor = index.get(successor_id)
            if successor is None:
                add(findings, "current", "P0", "missing_successor_record", f"{record_id} points to missing {successor_id}")
            elif successor.get("supersedes_record_id") != record_id:
                add(findings, "current", "P0", "broken_supersession_link", f"{record_id} successor link is not reciprocal")
            if lifecycle != "superseded":
                add(findings, "current", "P0", "successor_on_nonsuperseded_record", f"{record_id} has a successor but is not superseded")
        elif lifecycle == "superseded":
            add(findings, "current", "P0", "superseded_without_successor", f"{record_id} is superseded without a successor")

    visited: set[str] = set()
    for start_id in index:
        if start_id in visited:
            continue
        chain: list[str] = []
        chain_index: dict[str, int] = {}
        current_id = start_id
        while current_id in index and current_id not in visited:
            if current_id in chain_index:
                cycle = chain[chain_index[current_id] :]
                add(
                    findings,
                    "current",
                    "P0",
                    "supersession_cycle",
                    "supersession cycle includes: " + ", ".join(cycle),
                )
                break
            chain_index[current_id] = len(chain)
            chain.append(current_id)
            successor = index[current_id].get("superseded_by_record_id")
            if not isinstance(successor, str) or successor not in index:
                break
            current_id = successor
        visited.update(chain)


def validate_current_receipt_thread_authorization(
    project_root: Path,
    state: dict[str, Any],
    index: dict[str, dict[str, Any]],
    projection: list[str],
    current_records: list[dict[str, Any]],
    thread_snapshot_index: dict[str, dict[str, Any]],
    findings: list[Finding],
) -> None:
    current = state["current"]
    projected = set(projection)
    requirements = current.get("completion_requirements", {})
    required_kinds = set(requirements.get("required_record_kinds", []))
    required_logical_ids = set(requirements.get("required_logical_ids", []))
    invalid_required_kinds = sorted(required_kinds - OUTPUT_RECORD_KINDS)
    if invalid_required_kinds:
        add(
            findings,
            "current",
            "P0",
            "invalid_completion_output_kind",
            "completion requirements contain non-output kinds: " + ", ".join(invalid_required_kinds),
        )
    required_output_ids = {
        record_id
        for record_id in projection
        if record_id in index
        and index[record_id].get("kind") in OUTPUT_RECORD_KINDS
        and (
            index[record_id].get("kind") in required_kinds
            or index[record_id].get("logical_id") in required_logical_ids
        )
    }
    current_thread_ids = set(current.get("thread_record_ids", []))
    external_proof_required = bool(
        current_thread_ids
        or current.get("generation_authorization_ids")
        or current.get("acceptance", {}).get("status") == "accepted"
    )
    if external_proof_required and not thread_snapshot_index:
        add(
            findings,
            "current",
            "P0",
            "thread_snapshot_required",
            "current thread, acceptance, or generation authorization requires a fresh codex_app.list_threads snapshot",
        )
    if external_proof_required:
        add(
            findings,
            "current",
            "P0",
            "live_host_attestation_required",
            "a JSON snapshot is diagnostic only; final thread, acceptance, and authorization proof requires a live codex_app host-tool check in the controller task",
        )

    acceptance = current["acceptance"]
    receipt_id = acceptance.get("receipt_record_id")
    if acceptance.get("status") == "accepted":
        receipt = index.get(receipt_id) if isinstance(receipt_id, str) else None
        payload = receipt.get("receipt") if isinstance(receipt, dict) else None
        evidence_ref = payload.get("evidence_ref", "") if isinstance(payload, dict) else ""
        receipt_thread = payload.get("thread_id") if isinstance(payload, dict) else None
        host_thread = thread_snapshot_index.get(receipt_thread) if isinstance(receipt_thread, str) else None
        confirmation_id = payload.get("confirmation_id") if isinstance(payload, dict) else None
        confirmation = (
            host_thread.get("_confirmation_index", {}).get(confirmation_id)
            if isinstance(host_thread, dict) and isinstance(confirmation_id, str)
            else None
        )
        accepted_record_ids = payload.get("accepted_record_ids", []) if isinstance(payload, dict) else []
        accepted_outputs = [
            index.get(item)
            for item in accepted_record_ids
            if isinstance(item, str)
        ]
        if (
            receipt_id not in projected
            or not receipt
            or receipt.get("kind") != "receipt"
            or receipt.get("durable") is not True
            or not bound_payload_file_matches(project_root, receipt, "receipt")
            or not isinstance(payload, dict)
            or payload.get("receipt_type") != "live_acceptance"
            or payload.get("decision") != "accepted"
            or evidence_ref not in {f"user_confirmation:{confirmation_id}", f"client_confirmation:{confirmation_id}"}
            or receipt_thread not in {
                index[item]["thread"].get("thread_id")
                for item in current_thread_ids
                if item in index and isinstance(index[item].get("thread"), dict)
            }
            or not isinstance(host_thread, dict)
            or not isinstance(confirmation, dict)
            or payload.get("accepted_by") != confirmation.get("actor_id")
            or payload.get("accepted_by_type") != confirmation.get("actor_type")
            or payload.get("accepted_by_type") not in {"human", "client"}
            or not accepted_record_ids
            or any(item not in projected or item == receipt_id for item in accepted_record_ids)
            or any(
                not isinstance(record, dict)
                or record.get("kind") not in OUTPUT_RECORD_KINDS
                or record.get("durable") is not True
                or record.get("lifecycle") != "active"
                for record in accepted_outputs
            )
            or not required_output_ids.issubset(set(accepted_record_ids))
        ):
            add(
                findings,
                "current",
                "P0",
                "accepted_without_bound_receipt",
                "accepted state requires a current durable, hash-bound live-acceptance receipt",
            )

    manifest_payloads: dict[str, dict[str, Any]] = {}
    for field, expected_kind in [
        ("manifest_record_ids", "manifest"),
        ("generation_authorization_ids", "generation_authorization"),
        ("thread_record_ids", "thread"),
    ]:
        values = current.get(field)
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values) or len(values) != len(set(values)):
            add(findings, "current", "P0", f"invalid_{field}", f"current.{field} must be a unique string array")
            continue
        for record_id in values:
            record = index.get(record_id)
            if record_id not in projected or not record or record.get("kind") != expected_kind:
                add(findings, "current", "P0", f"stale_{field}", f"{record_id} is not a current {expected_kind}")
                continue
            if record.get("durable") is not True:
                add(findings, "current", "P0", f"nondurable_{field}", f"{record_id} current {expected_kind} must be durable")
            if expected_kind == "manifest":
                manifest = record.get("manifest")
                manifest_record_ids = manifest.get("record_ids", []) if isinstance(manifest, dict) else []
                valid_manifest_records = [index.get(item) for item in manifest_record_ids if isinstance(item, str)]
                if (
                    not isinstance(manifest, dict)
                    or not bound_payload_file_matches(project_root, record, "manifest")
                    or not manifest_record_ids
                    or any(item not in projected or item == record_id for item in manifest_record_ids)
                    or any(
                        not isinstance(item, dict)
                        or item.get("kind") not in OUTPUT_RECORD_KINDS
                        or item.get("durable") is not True
                        or item.get("lifecycle") != "active"
                        for item in valid_manifest_records
                    )
                ):
                    add(findings, "current", "P0", "invalid_current_manifest", f"{record_id} is not a hash-bound manifest of current outputs")
                else:
                    manifest_payloads[record_id] = manifest
            if expected_kind == "thread":
                evidence = record.get("evidence")
                thread = record.get("thread")
                checked_at = thread.get("checked_at") if isinstance(thread, dict) else None
                checked = parse_rfc3339(checked_at)
                now = datetime.now(timezone.utc)
                host_thread = thread_snapshot_index.get(thread.get("thread_id")) if isinstance(thread, dict) else None
                expected_host_statuses = {
                    "active": {"active", "idle"},
                    "completed": {"idle", "completed"},
                    "failed": {"failed"},
                    "interrupted": {"interrupted", "idle"},
                }
                if (
                    not isinstance(evidence, dict)
                    or evidence.get("task_visibility") != "verified"
                    or evidence.get("checked_at") != checked_at
                    or checked is None
                    or checked > now + timedelta(minutes=5)
                    or now - checked > THREAD_PROOF_MAX_AGE
                    or not bound_payload_file_matches(project_root, record, "thread")
                    or not isinstance(host_thread, dict)
                    or host_thread.get("host_id") != thread.get("host_id")
                    or host_thread.get("status") not in expected_host_statuses.get(thread.get("output_status"), set())
                    or host_thread.get("archived") is not (thread.get("archive_state") == "archived")
                ):
                    add(findings, "current", "P0", "thread_visibility_stale", f"{record_id} lacks fresh host task reconciliation")
            if expected_kind == "generation_authorization":
                authorization = record.get("generation_authorization")
                authorized_at = parse_rfc3339(authorization.get("authorized_at")) if isinstance(authorization, dict) else None
                expires_at = parse_rfc3339(authorization.get("expires_at")) if isinstance(authorization, dict) and authorization.get("expires_at") else None
                confirmation_id = authorization.get("confirmation_id") if isinstance(authorization, dict) else None
                authorization_thread = authorization.get("thread_id") if isinstance(authorization, dict) else None
                host_thread = thread_snapshot_index.get(authorization_thread) if isinstance(authorization_thread, str) else None
                confirmation = (
                    host_thread.get("_confirmation_index", {}).get(confirmation_id)
                    if isinstance(host_thread, dict) and isinstance(confirmation_id, str)
                    else None
                )
                if (
                    not isinstance(authorization, dict)
                    or authorization.get("work_id") != state.get("project_id")
                    or authorization.get("status") != "active"
                    or authorization.get("authorized_by_type") not in {"human", "controller"}
                    or authorization.get("evidence_ref") not in {
                        f"user_confirmation:{confirmation_id}",
                        f"client_confirmation:{confirmation_id}",
                        f"controller_confirmation:{confirmation_id}",
                    }
                    or authorization.get("scope_hash") != canonical_authorization_scope(authorization)
                    or authorized_at is None
                    or authorized_at > datetime.now(timezone.utc) + timedelta(minutes=5)
                    or (expires_at is not None and expires_at < datetime.now(timezone.utc))
                    or not bound_payload_file_matches(project_root, record, "generation_authorization")
                    or not isinstance(confirmation, dict)
                    or authorization.get("authorized_by") != confirmation.get("actor_id")
                    or authorization.get("authorized_by_type") != confirmation.get("actor_type")
                ):
                    add(findings, "current", "P0", "invalid_generation_authorization", f"{record_id} is not a current exact human/controller authorization")

    authorization_ids = set(current.get("generation_authorization_ids", []))
    now = datetime.now(timezone.utc)
    for record in current_records:
        if record.get("kind") != "generated_media":
            continue
        evidence = record.get("evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        authorization_id = evidence.get("authorization_record_id")
        authorization_record = index.get(authorization_id) if isinstance(authorization_id, str) else None
        authorization = authorization_record.get("generation_authorization") if isinstance(authorization_record, dict) else None
        expires_at = parse_rfc3339(authorization.get("expires_at")) if isinstance(authorization, dict) and authorization.get("expires_at") else None
        valid = (
            authorization_id in authorization_ids
            and isinstance(authorization_record, dict)
            and authorization_record.get("kind") == "generation_authorization"
            and authorization_record.get("durable") is True
            and isinstance(authorization, dict)
            and authorization.get("status") == "active"
            and authorization.get("work_id") == state.get("project_id")
            and evidence.get("asset_id") in authorization.get("asset_ids", [])
            and evidence.get("model_id") in authorization.get("model_ids", [])
            and record.get("kind") in authorization.get("expected_output_kinds", [])
            and evidence.get("authorization_scope_hash") == authorization.get("scope_hash")
            and authorization.get("scope_hash") == canonical_authorization_scope(authorization)
            and (expires_at is None or expires_at >= now)
        )
        if not valid:
            add(findings, "current", "P0", "generated_media_unauthorized", f"{record.get('record_id')} lacks an exact current authorization binding")

    stage = current["stage"]
    if stage.get("status") == "complete":
        requirements = current["completion_requirements"]
        current_kinds = {record.get("kind") for record in current_records}
        current_logical_ids = {record.get("logical_id") for record in current_records}
        completion_receipt_id = stage.get("completion_receipt_record_id")
        completion_receipt = index.get(completion_receipt_id) if isinstance(completion_receipt_id, str) else None
        completion_payload = completion_receipt.get("receipt") if isinstance(completion_receipt, dict) else None
        completion_accepted_ids = set(
            completion_payload.get("accepted_record_ids", []) if isinstance(completion_payload, dict) else []
        )
        manifest_ids = set(current.get("manifest_record_ids", []))
        manifest_output_ids = {
            item
            for manifest_id in manifest_ids
            for item in manifest_payloads.get(manifest_id, {}).get("record_ids", [])
        }
        required_completion_bindings = set(required_output_ids)
        if requirements["manifest_required"]:
            required_completion_bindings.update(manifest_ids)
        contract_has_output_requirements = bool(required_kinds or required_logical_ids)
        if (
            not contract_has_output_requirements
            or not required_output_ids
            or any(
                index.get(item, {}).get("kind") not in OUTPUT_RECORD_KINDS
                or index.get(item, {}).get("durable") is not True
                or index.get(item, {}).get("lifecycle") != "active"
                for item in required_output_ids
            )
            or not required_kinds.issubset(current_kinds)
            or not required_logical_ids.issubset(current_logical_ids)
            or (requirements["manifest_required"] and not current.get("manifest_record_ids"))
            or (requirements["manifest_required"] and not required_output_ids.issubset(manifest_output_ids))
            or (requirements["acceptance_required"] and acceptance.get("status") != "accepted")
            or completion_receipt_id not in projected
            or not isinstance(completion_receipt, dict)
            or completion_receipt.get("kind") != "receipt"
            or completion_receipt.get("durable") is not True
            or not bound_payload_file_matches(project_root, completion_receipt, "receipt")
            or not isinstance(completion_payload, dict)
            or completion_payload.get("receipt_type") not in {"execution", "validation", "delivery"}
            or completion_payload.get("decision") not in {"completed", "accepted"}
            or not completion_accepted_ids
            or not required_completion_bindings.issubset(completion_accepted_ids)
            or any(
                item not in projected
                or item == completion_receipt_id
                or index.get(item, {}).get("kind") not in OUTPUT_RECORD_KINDS | {"manifest"}
                or index.get(item, {}).get("durable") is not True
                or index.get(item, {}).get("lifecycle") != "active"
                for item in completion_accepted_ids
            )
        ):
            add(findings, "current", "P0", "empty_or_unproven_completion", "complete stage does not satisfy its typed completion contract")


def reconcile_storage(
    project_root: Path,
    index: dict[str, dict[str, Any]],
    projection: list[str],
    storage: dict[str, Any],
    findings: list[Finding],
) -> dict[str, Any]:
    managed_paths: dict[str, str] = {}
    inode_owners: dict[tuple[int, int], str] = {}
    content_owners: dict[str, list[str]] = {}
    bytes_by_class = {name: 0 for name in STORAGE_CLASSES}
    counted_inodes: set[tuple[int, int]] = set()
    managed_bytes = 0
    expected_class_policies = {
        "final": {"retention": "preserve", "user_confirmation_required_before_delete": True},
        "necessary_archive": {"retention": "review", "user_confirmation_required_before_delete": True},
        "regenerable_cache": {"retention": "regenerate_then_remove", "user_confirmation_required_before_delete": False},
        "delete_candidate": {"retention": "remove_after_confirmation", "user_confirmation_required_before_delete": True},
    }
    if storage.get("classes") != expected_class_policies:
        add(
            findings,
            "current",
            "P0",
            "invalid_storage_class_policy",
            "storage class retention and confirmation policy must match the v1 lifecycle contract",
        )

    def resolved_roots(values: list[str], label: str) -> list[Path]:
        roots: list[Path] = []
        for value in values:
            root = safe_project_path(project_root, value)
            parts = Path(value).parts
            if (
                root is None
                or value in {"", "."}
                or not parts
                or parts[0] == ".git"
                or tuple(parts[:2]) == (".dircreative", "state")
                or (root.exists() and root.is_symlink())
            ):
                add(findings, "current", "P0", f"unsafe_{label}_root", f"unsafe {label} root: {value}")
                continue
            roots.append(root.resolve(strict=False))
        return roots

    artifact_root_paths = resolved_roots(storage.get("artifact_roots", []), "artifact")
    control_root_paths = resolved_roots(storage.get("control_roots", []), "control")
    for artifact_root in artifact_root_paths:
        for control_root in control_root_paths:
            if (
                artifact_root == control_root
                or artifact_root.is_relative_to(control_root)
                or control_root.is_relative_to(artifact_root)
            ):
                add(
                    findings,
                    "current",
                    "P0",
                    "overlapping_storage_roots",
                    f"artifact and control roots must be disjoint: {artifact_root} <> {control_root}",
                )

    def within(path: Path, roots: list[Path]) -> bool:
        resolved = path.resolve(strict=False)
        return any(resolved == root or resolved.is_relative_to(root) for root in roots)

    for record_id, record in index.items():
        if record.get("storage_class") == "delete_candidate" and record.get("lifecycle") not in {"withdrawn", "removed"}:
            add(findings, "current", "P0", "invalid_delete_candidate_lifecycle", f"{record_id} delete candidate must be withdrawn or removed")
        if record.get("durable") is not True or record.get("lifecycle") == "removed":
            continue
        canonical = record.get("canonical_path")
        target = safe_project_path(project_root, canonical)
        if target is None:
            add(findings, "current", "P0", "unsafe_managed_path", f"{record_id} has no safe canonical path")
            continue
        in_artifact_root = within(target, artifact_root_paths)
        in_control_root = within(target, control_root_paths)
        expected_control = record.get("kind") in CONTROL_RECORD_KINDS
        expected_artifact = record.get("kind") in ARTIFACT_RECORD_KINDS
        if not in_artifact_root and not in_control_root:
            add(findings, "current", "P0", "managed_path_outside_roots", f"{record_id} is outside declared roots")
        if expected_control and not in_control_root:
            add(findings, "current", "P0", "control_record_outside_control_root", f"{record_id} control record is outside control_roots")
        if expected_control and in_artifact_root:
            add(findings, "current", "P0", "control_record_in_artifact_root", f"{record_id} control record cannot live in artifact_roots")
        if expected_artifact and not in_artifact_root:
            add(findings, "current", "P0", "artifact_record_outside_artifact_root", f"{record_id} output/cache record is outside artifact_roots")
        if expected_artifact and in_control_root:
            add(findings, "current", "P0", "artifact_record_in_control_root", f"{record_id} output/cache record cannot live in control_roots")
        if in_control_root and record.get("storage_class") in {"delete_candidate", "regenerable_cache"}:
            add(findings, "current", "P0", "unsafe_control_storage_class", f"{record_id} control evidence cannot be cache/delete_candidate")
        relative = target.relative_to(project_root).as_posix()
        previous_path_owner = managed_paths.get(relative)
        if previous_path_owner and previous_path_owner != record_id:
            add(findings, "current", "P0", "managed_path_reuse", f"{record_id} and {previous_path_owner} reuse {relative}")
        else:
            managed_paths[relative] = record_id
        try:
            stat, actual_hash = inspect_regular_file(target)
        except FileNotFoundError:
            lane = "current" if record_id in projection else "legacy"
            severity = "P0" if lane == "current" else "P1"
            add(findings, lane, severity, "missing_managed_file", f"{record_id} missing: {relative}")
            continue
        except (OSError, ValueError) as exc:
            add(findings, "current", "P0", "unsafe_managed_file", f"{record_id} cannot be inspected safely: {exc}")
            continue
        if stat.st_nlink != 1:
            add(findings, "current", "P0", "hardlinked_managed_file", f"{record_id} has link count {stat.st_nlink}")
        inode_key = (stat.st_dev, stat.st_ino)
        previous_inode_owner = inode_owners.get(inode_key)
        if previous_inode_owner and previous_inode_owner != record_id:
            add(findings, "current", "P0", "physical_output_reuse", f"{record_id} and {previous_inode_owner} share one physical file")
        else:
            inode_owners[inode_key] = record_id
        if actual_hash != record.get("sha256"):
            lane = "current" if record_id in projection else "legacy"
            severity = "P0" if lane == "current" else "P1"
            add(findings, lane, severity, "managed_hash_mismatch", f"{record_id} SHA-256 mismatch")
        content_owners.setdefault(actual_hash, []).append(record_id)
        if inode_key not in counted_inodes:
            counted_inodes.add(inode_key)
            managed_bytes += stat.st_size
            storage_class = record.get("storage_class")
            if storage_class in bytes_by_class:
                bytes_by_class[storage_class] += stat.st_size

    duplicate_groups = [owners for owners in content_owners.values() if len(owners) > 1]
    for owners in duplicate_groups:
        add(findings, "current", "P1", "duplicate_managed_content", "same content stored by: " + ", ".join(sorted(owners)))

    untracked: set[str] = set()
    disk_bytes = 0
    artifact_extra_bytes = 0
    disk_inodes: set[tuple[int, int]] = set()
    zip_files = 0
    observed_directories: set[str] = set()
    observed_zip_bases: set[str] = set()
    scan_roots = [
        *( (value, "artifact") for value in storage.get("artifact_roots", []) ),
        *( (value, "control") for value in storage.get("control_roots", []) ),
    ]
    for raw_root, root_class in scan_roots:
        root = safe_project_path(project_root, raw_root)
        if root is None:
            add(findings, "current", "P0", f"unsafe_{root_class}_root", f"unsafe {root_class} root: {raw_root}")
            continue
        if not root.exists():
            continue
        if root.is_symlink() or not root.is_dir():
            add(findings, "current", "P0", f"unsafe_{root_class}_root", f"{root_class} root must be a real directory: {raw_root}")
            continue
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            directory_path = Path(directory)
            observed_directories.add(directory_path.relative_to(project_root).as_posix())
            symlink_dirs = [name for name in dirnames if (directory_path / name).is_symlink()]
            for name in symlink_dirs:
                add(findings, "current", "P0", f"symlink_in_{root_class}_root", str((directory_path / name).relative_to(project_root)))
                dirnames.remove(name)
            for name in filenames:
                path = directory_path / name
                relative = path.relative_to(project_root).as_posix()
                if name == ".keep":
                    continue
                try:
                    stat, _ = inspect_regular_file(path)
                except (OSError, ValueError) as exc:
                    add(findings, "current", "P0", f"unsafe_{root_class}_file", f"{relative}: {exc}")
                    continue
                inode_key = (stat.st_dev, stat.st_ino)
                if inode_key not in disk_inodes:
                    disk_inodes.add(inode_key)
                    disk_bytes += stat.st_size
                    if inode_key not in counted_inodes:
                        artifact_extra_bytes += stat.st_size
                if path.suffix.casefold() == ".zip":
                    zip_files += 1
                    observed_zip_bases.add(path.with_suffix("").relative_to(project_root).as_posix())
                if relative not in managed_paths:
                    untracked.add(relative)
    for relative in sorted(untracked):
        add(findings, "current", "P0", "untracked_artifact", f"unclassified artifact requires reconcile: {relative}")
    parallel_directory_zips = sorted(observed_directories & observed_zip_bases)
    for relative in parallel_directory_zips:
        add(findings, "current", "P1", "directory_zip_parallel_storage", f"directory and ZIP are both retained: {relative}")

    budget = storage.get("budget_bytes")
    warn_ratio = storage.get("warn_at_ratio")
    actual_budget_bytes = managed_bytes + artifact_extra_bytes
    if actual_budget_bytes > budget:
        add(findings, "current", "P0", "storage_budget_exceeded", f"managed artifact bytes {actual_budget_bytes} exceed budget {budget}")
    elif actual_budget_bytes >= budget * warn_ratio:
        add(findings, "current", "P1", "storage_budget_warning", f"managed artifact bytes {actual_budget_bytes} reached warning ratio")

    return {
        "total_managed_durable_bytes": managed_bytes,
        "artifact_root_disk_bytes": disk_bytes,
        "total_observed_storage_bytes": actual_budget_bytes,
        "bytes_by_storage_class": bytes_by_class,
        "untracked_artifact_count": len(untracked),
        "duplicate_content_group_count": len(duplicate_groups),
        "zip_file_count": zip_files,
        "directory_zip_parallel_count": len(parallel_directory_zips),
    }


def validate_state(
    project_root: Path,
    state: dict[str, Any],
    *,
    thread_snapshot: dict[str, Any] | None = None,
) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    schema_failures = runtime_schema_errors(state)
    if schema_failures:
        for failure in schema_failures[:50]:
            add(findings, "current", "P0", "schema_validation_failed", failure)
        return findings, {
            "project_id": state.get("project_id") if isinstance(state, dict) else None,
            "schema_version": state.get("schema_version") if isinstance(state, dict) else None,
            "current_record_count": 0,
            "record_count": 0,
            "legacy_debt_count": 0,
            "total_current_durable_bytes": 0,
            "total_managed_durable_bytes": 0,
            "bytes_by_storage_class": {name: 0 for name in STORAGE_CLASSES},
            "untracked_artifact_count": 0,
        }
    if state.get("schema_version") != CURRENT_SCHEMA_VERSION:
        add(
            findings,
            "current",
            "P0",
            "unsupported_schema_version",
            f"schema_version must be {CURRENT_SCHEMA_VERSION}",
        )
    if not isinstance(state.get("project_id"), str) or not state.get("project_id"):
        add(findings, "current", "P0", "missing_project_id", "project_id is required")
    if not isinstance(state.get("updated_at"), str) or not state.get("updated_at"):
        add(findings, "current", "P0", "missing_updated_at", "updated_at is required")
    else:
        updated_at = parse_rfc3339(state.get("updated_at"))
        now = datetime.now(timezone.utc)
        if updated_at is None or updated_at > now + timedelta(minutes=5):
            add(findings, "current", "P0", "state_reconciliation_stale", "runtime state must be reconciled within the last 24 hours")
        elif state.get("current", {}).get("state_kind") == "live_session" and now - updated_at > THREAD_PROOF_MAX_AGE:
            add(findings, "current", "P0", "state_reconciliation_stale", "live runtime state must be reconciled within the last 24 hours")

    current = state.get("current")
    if not isinstance(current, dict):
        add(findings, "current", "P0", "missing_current", "current must be an object")
        current = {}
    stage = current.get("stage")
    if not isinstance(stage, dict) or stage.get("status") not in STAGE_STATUSES or not stage.get("id"):
        add(findings, "current", "P0", "invalid_current_stage", "current.stage must have typed id and status")
    if not isinstance(current.get("session_id"), str) or not current.get("session_id"):
        add(findings, "current", "P0", "missing_session_id", "current.session_id is required")
    if current.get("state_kind") not in {"repository_baseline", "live_session"}:
        add(findings, "current", "P0", "invalid_state_kind", "current.state_kind must identify repository_baseline or live_session")
    acceptance = current.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("status") not in ACCEPTANCE_STATUSES:
        add(findings, "current", "P0", "invalid_acceptance", "current.acceptance must have a typed status")
        acceptance = {}

    index = record_index(state.get("records"), findings)
    for record_id, record in index.items():
        validate_record_shape(record_id, record, findings)

    projection = state.get("current_projection")
    if not isinstance(projection, list) or any(not isinstance(item, str) for item in projection):
        add(findings, "current", "P0", "invalid_current_projection", "current_projection must be an array of record IDs")
        projection = []
    if len(projection) != len(set(projection)):
        add(findings, "current", "P0", "duplicate_projection_record", "current_projection contains duplicates")
    if current.get("state_kind") == "repository_baseline" and (
        projection
        or state.get("records")
        or current.get("manifest_record_ids")
        or current.get("generation_authorization_ids")
        or current.get("thread_record_ids")
        or acceptance.get("status") != "not_requested"
    ):
        add(findings, "current", "P0", "baseline_claims_live_state", "repository baseline cannot carry live records, authorizations, threads, or acceptance")

    current_records: list[dict[str, Any]] = []
    current_logical_ids: set[str] = set()
    current_paths: set[str] = set()
    inode_owners: dict[tuple[int, int], str] = {}
    total_current_bytes = 0

    for record_id in projection:
        record = index.get(record_id)
        if record is None:
            add(findings, "current", "P0", "projection_record_missing", f"current record not found: {record_id}")
            continue
        current_records.append(record)
        if record.get("lifecycle") != "active":
            add(findings, "current", "P0", "nonactive_record_in_projection", f"{record_id} is not active")
        if record.get("storage_class") == "delete_candidate":
            add(findings, "current", "P0", "delete_candidate_in_projection", f"{record_id} cannot be both current and a delete candidate")
        if record.get("kind") == "final_delivery" and record.get("storage_class") != "final":
            add(findings, "current", "P0", "final_delivery_misclassified", f"{record_id} final delivery must use storage_class final")
        logical_id = record.get("logical_id")
        if logical_id in current_logical_ids:
            add(findings, "current", "P0", "duplicate_current_logical_id", f"duplicate current logical_id: {logical_id}")
        elif isinstance(logical_id, str):
            current_logical_ids.add(logical_id)

        canonical = record.get("canonical_path")
        if canonical is not None:
            if canonical in current_paths:
                add(findings, "current", "P0", "duplicate_current_path", f"duplicate current canonical_path: {canonical}")
            elif isinstance(canonical, str):
                current_paths.add(canonical)

        if canonical is not None and record.get("durable") is not True:
            target = safe_project_path(project_root, canonical)
            if target is None:
                add(findings, "current", "P0", "unsafe_current_path", f"{record_id} has an unsafe current path")
            else:
                try:
                    stat, _ = inspect_regular_file(target)
                except FileNotFoundError:
                    add(findings, "current", "P0", "missing_current_file", f"{record_id} missing: {canonical}")
                except (OSError, ValueError) as exc:
                    add(findings, "current", "P0", "unsafe_current_file", f"{record_id} cannot be read safely: {exc}")
                else:
                    if stat.st_nlink != 1:
                        add(findings, "current", "P0", "hardlinked_current_file", f"{record_id} must not be hardlinked")

        if record.get("durable") is True:
            target = safe_project_path(project_root, canonical)
            if target is None:
                add(findings, "current", "P0", "unsafe_current_path", f"{record_id} has an unsafe or missing canonical_path")
                continue
            try:
                stat, actual_hash = inspect_regular_file(target)
            except FileNotFoundError:
                add(findings, "current", "P0", "missing_current_file", f"{record_id} missing: {canonical}")
                continue
            except (OSError, ValueError) as exc:
                add(findings, "current", "P0", "unsafe_current_file", f"{record_id} cannot be read safely: {exc}")
                continue
            if stat.st_nlink != 1:
                add(findings, "current", "P0", "hardlinked_current_file", f"{record_id} must not be hardlinked")
            inode_key = (stat.st_dev, stat.st_ino)
            previous = inode_owners.get(inode_key)
            if previous and previous != record_id:
                add(findings, "current", "P0", "physical_output_reuse", f"{record_id} and {previous} share one physical file")
            else:
                inode_owners[inode_key] = record_id
            total_current_bytes += stat.st_size
            expected_hash = record.get("sha256")
            if actual_hash != expected_hash:
                add(findings, "current", "P0", "current_hash_mismatch", f"{record_id} SHA-256 mismatch")

    validate_supersession(index, projection, findings)
    thread_snapshot_index = build_thread_snapshot_index(thread_snapshot, findings)
    validate_current_receipt_thread_authorization(
        project_root,
        state,
        index,
        projection,
        current_records,
        thread_snapshot_index,
        findings,
    )

    migrations = state["migrations"]
    excluded_control_paths = current_control_paths(project_root, state, index)
    try:
        discovered_migrations = {
            row["source"]: row
            for row in migration_plan(project_root, exclude_current_paths=excluded_control_paths)
        }
    except (OSError, ValueError) as exc:
        add(findings, "current", "P0", "legacy_discovery_failed", str(exc))
        discovered_migrations = {}
    migration_ids: set[str] = set()
    migration_sources: set[str] = set()
    for position, migration in enumerate(migrations):
        migration_id = migration["migration_id"]
        source = migration["source"]
        if migration_id in migration_ids:
            add(findings, "current", "P0", "duplicate_migration_id", f"duplicate migration_id: {migration_id}")
        migration_ids.add(migration_id)
        if source in migration_sources:
            add(findings, "current", "P0", "duplicate_migration_source", f"duplicate migration source: {source}")
        migration_sources.add(source)
        if safe_project_path(project_root, source) is None:
            add(findings, "current", "P0", "unsafe_migration_source", f"migrations[{position}] source is unsafe")
        discovered = discovered_migrations.get(source)
        if not discovered:
            add(findings, "current", "P0", "migration_source_missing", f"{migration_id} source is not present in legacy discovery")
        elif migration.get("source_sha256") != discovered.get("source_sha256"):
            add(findings, "current", "P0", "migration_source_hash_mismatch", f"{migration_id} does not bind the current source bytes")
        if discovered and migration.get("from_schema_version") != discovered.get("source_schema_version"):
            add(
                findings,
                "current",
                "P0",
                "migration_source_version_mismatch",
                f"{migration_id} from_schema_version does not match the fully parsed source",
            )
        if migration["mode"] == "already_current" and (
            not discovered
            or discovered.get("source_schema_version") != CURRENT_SCHEMA_VERSION
            or discovered.get("semantic_parse_status") != "parsed"
            or discovered.get("semantic_current_schema_valid") is not True
            or migration.get("from_schema_version") != CURRENT_SCHEMA_VERSION
        ):
            add(findings, "current", "P0", "legacy_marked_current", f"{migration_id} source is not demonstrably current schema")
        if migration["mode"] == "already_current" and discovered:
            source_record_ids = set(discovered.get("semantic_current_record_ids", []))
            source_record_hashes = discovered.get("semantic_current_record_hashes", {})
            mapped_record_ids = set(migration.get("record_ids", []))
            current_record_hashes = {
                record_id: hashlib.sha256(_canonical_item(index[record_id]).encode("utf-8")).hexdigest()
                for record_id in mapped_record_ids
                if record_id in index
            }
            if (
                mapped_record_ids != source_record_ids
                or set(source_record_hashes) != source_record_ids
                or current_record_hashes != source_record_hashes
            ):
                add(
                    findings,
                    "current",
                    "P0",
                    "already_current_record_binding_mismatch",
                    f"{migration_id} record_ids/content do not exactly match the source current projection",
                )
        if migration["mode"] == "quarantined" and migration["record_ids"]:
            add(findings, "current", "P0", "quarantine_references_records", f"{migration_id} quarantine must not adopt records")
        if migration["mode"] in {"transformed", "already_current"} and not migration["record_ids"]:
            add(findings, "current", "P0", "migration_without_records", f"{migration_id} must bind converted records")
        for record_id in migration["record_ids"]:
            if record_id not in index:
                add(findings, "current", "P0", "migration_record_missing", f"{migration_id} references missing {record_id}")
        if migration["mode"] == "transformed" and any(
            record_id in projection or index.get(record_id, {}).get("lifecycle") == "active"
            for record_id in migration["record_ids"]
        ):
            add(
                findings,
                "current",
                "P0",
                "transformed_record_not_isolated",
                f"{migration_id} transformed legacy records must remain non-active and outside current_projection until a separate live adoption",
            )
        transformation_receipt_id = migration.get("transformation_receipt_record_id")
        if migration["mode"] == "transformed":
            transformation_receipt = index.get(transformation_receipt_id) if isinstance(transformation_receipt_id, str) else None
            transformation_payload = (
                transformation_receipt.get("receipt") if isinstance(transformation_receipt, dict) else None
            )
            if (
                not isinstance(transformation_receipt, dict)
                or transformation_receipt.get("kind") != "receipt"
                or transformation_receipt.get("durable") is not True
                or not bound_payload_file_matches(project_root, transformation_receipt, "receipt")
                or not isinstance(transformation_payload, dict)
                or transformation_payload.get("receipt_type") != "validation"
                or transformation_payload.get("decision") != "completed"
                or transformation_payload.get("evidence_ref") != f"migration:{migration_id}"
                or set(transformation_payload.get("accepted_record_ids", [])) != set(migration["record_ids"])
            ):
                add(findings, "current", "P0", "transformation_receipt_missing", f"{migration_id} lacks a durable transformation receipt")
        elif transformation_receipt_id is not None:
            add(findings, "current", "P0", "unexpected_transformation_receipt", f"{migration_id} mode cannot carry a transformation receipt")

    fixture_migration = state["fixture_migration"]
    fixture_source_count = fixture_migration["source_count"]
    if fixture_source_count:
        manifest_path = safe_project_path(project_root, fixture_migration["manifest_path"])
        if manifest_path is None:
            add(findings, "current", "P0", "unsafe_fixture_manifest", "fixture migration manifest path is unsafe")
        else:
            try:
                manifest_stat, manifest_hash, manifest_bytes = inspect_regular_file_bytes(manifest_path)
                manifest = json.loads(manifest_bytes)
            except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
                add(findings, "current", "P0", "fixture_manifest_unavailable", str(exc))
            else:
                if manifest_stat.st_nlink != 1 or manifest_hash != fixture_migration["manifest_sha256"]:
                    add(findings, "current", "P0", "fixture_manifest_hash_mismatch", "fixture migration manifest is not bound to current state")
                authority = {
                    "fixture_authority": "none",
                    "live_state_authority": False,
                    "live_acceptance_authority": False,
                    "host_attestation_authority": False,
                }
                if any(manifest.get(key) != value for key, value in authority.items()):
                    add(findings, "current", "P0", "fixture_manifest_has_authority", "fixture migration manifest must have no live authority")
                entries = manifest.get("entries")
                if not isinstance(entries, list) or len(entries) != fixture_source_count:
                    add(findings, "current", "P0", "fixture_manifest_count_mismatch", "fixture migration source_count does not match manifest entries")
                    entries = []
                seen_sources: set[str] = set()
                seen_destinations: set[str] = set()
                for position, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        add(findings, "current", "P0", "invalid_fixture_migration_entry", f"fixture migration entry {position} is not an object")
                        continue
                    source = entry.get("original_path")
                    destination = entry.get("destination_path")
                    if not isinstance(source, str) or source in seen_sources:
                        add(findings, "current", "P0", "duplicate_fixture_migration_source", f"invalid or duplicate fixture source: {source}")
                    else:
                        seen_sources.add(source)
                    if not isinstance(destination, str) or destination in seen_destinations:
                        add(findings, "current", "P0", "duplicate_fixture_migration_destination", f"invalid or duplicate fixture destination: {destination}")
                        continue
                    seen_destinations.add(destination)
                    live_source = safe_project_path(project_root, source)
                    if live_source is None or not source.startswith(".dircreative/"):
                        add(findings, "current", "P0", "unsafe_fixture_migration_source", f"fixture source is unsafe: {source}")
                    elif live_source.exists():
                        add(findings, "current", "P0", "legacy_source_still_live", f"migrated legacy source remains live: {source}")
                    destination_path = safe_project_path(project_root, destination)
                    if destination_path is None or not (
                        destination.startswith("tests/fixtures/runtime/")
                        or destination == "docs/film-preproduction/templates/live-user-acceptance.template.yaml"
                    ):
                        add(findings, "current", "P0", "unsafe_fixture_migration_destination", f"fixture destination is unsafe: {destination}")
                        continue
                    try:
                        destination_stat, destination_hash = inspect_regular_file(destination_path)
                    except (FileNotFoundError, OSError, ValueError) as exc:
                        add(findings, "current", "P0", "fixture_destination_unavailable", f"{destination}: {exc}")
                    else:
                        if destination_stat.st_nlink != 1 or destination_hash != entry.get("destination_sha256"):
                            add(findings, "current", "P0", "fixture_destination_hash_mismatch", f"fixture destination changed: {destination}")

    debt = state["legacy_debt"]
    current_resolved_paths: set[Path] = set()
    current_inodes: set[tuple[int, int]] = set()
    for record_id in projection:
        record = index.get(record_id)
        if not isinstance(record, dict):
            continue
        for value in (record.get("canonical_path"), record.get("original_path")):
            target = safe_project_path(project_root, value)
            if target is None:
                continue
            current_resolved_paths.add(target.resolve(strict=False))
            try:
                stat, _ = inspect_regular_file(target)
            except (FileNotFoundError, OSError, ValueError):
                continue
            current_inodes.add((stat.st_dev, stat.st_ino))
    for position, item in enumerate(debt):
        related_ids = item["record_ids"]
        debt_target = safe_project_path(project_root, item["source"])
        debt_inode: tuple[int, int] | None = None
        debt_path_invalid = debt_target is None or debt_target.is_symlink() or not debt_target.exists()
        if not debt_path_invalid and debt_target is not None:
            try:
                debt_stat, _ = inspect_regular_file(debt_target)
            except (OSError, ValueError):
                debt_path_invalid = True
            else:
                debt_inode = (debt_stat.st_dev, debt_stat.st_ino)
        calculated_overlap = (
            bool(set(related_ids) & set(projection))
            or (debt_target is not None and debt_target.resolve(strict=False) in current_resolved_paths)
            or (debt_inode is not None and debt_inode in current_inodes)
        )
        active_related = [record_id for record_id in related_ids if record_id in index and index[record_id].get("lifecycle") == "active"]
        missing_related = [record_id for record_id in related_ids if record_id not in index]
        if (
            item.get("affects_current_projection") is True
            or item.get("isolated") is not True
            or calculated_overlap
            or active_related
            or missing_related
            or debt_path_invalid
        ):
            add(
                findings,
                "current",
                "P0",
                "legacy_debt_not_isolated",
                f"{item.get('debt_id', position)} is not provably isolated from current projection",
            )
        else:
            add(findings, "legacy", item["severity"], "legacy_debt", f"{item.get('debt_id')}: {item.get('reason')}")

    validate_migration_coverage(
        project_root,
        state,
        findings,
        exclude_current_paths=excluded_control_paths,
    )
    storage_summary = reconcile_storage(project_root, index, projection, state["storage_policy"], findings)

    summary = {
        "project_id": state.get("project_id"),
        "schema_version": state.get("schema_version"),
        "current_record_count": len(projection),
        "record_count": len(index),
        "legacy_debt_count": len(debt),
        "total_current_durable_bytes": total_current_bytes,
        **storage_summary,
    }
    return findings, summary


def current_control_paths(
    project_root: Path,
    state: dict[str, Any],
    index: dict[str, dict[str, Any]],
) -> set[str]:
    paths: set[str] = set()
    payload_fields = {
        "receipt": "receipt",
        "manifest": "manifest",
        "generation_authorization": "generation_authorization",
        "thread": "thread",
    }
    for record in index.values():
        kind = record.get("kind")
        field = payload_fields.get(kind)
        canonical = record.get("canonical_path")
        if field is None or not isinstance(canonical, str) or record.get("durable") is not True:
            continue
        target = safe_project_path(project_root, canonical)
        if target is None:
            continue
        try:
            stat, actual_hash = inspect_regular_file(target)
        except (FileNotFoundError, OSError, ValueError):
            continue
        if (
            stat.st_nlink == 1
            and actual_hash == record.get("sha256")
            and bound_payload_file_matches(project_root, record, field)
        ):
            paths.add(canonical)
    return paths


def migration_plan(project_root: Path, *, exclude_current_paths: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude_current_paths or set()
    candidates: list[Path] = []
    control_root = project_root / ".dircreative"
    if control_root.is_symlink():
        raise ValueError(f"legacy control root must not be a symlink: {control_root}")
    run_dir = project_root / ".dircreative" / "runs"
    if run_dir.exists():
        if run_dir.is_symlink():
            raise ValueError(f"legacy runs root must not be a symlink: {run_dir}")
        for directory, dirnames, filenames in os.walk(run_dir, followlinks=False):
            directory_path = Path(directory)
            symlink_dirs = [name for name in dirnames if (directory_path / name).is_symlink()]
            if symlink_dirs:
                raise ValueError(f"legacy runs contain symlink directories: {symlink_dirs}")
            for name in filenames:
                path = directory_path / name
                if path.is_symlink():
                    raise ValueError(f"legacy run must not be a symlink: {path}")
                if path.suffix.casefold() in {".yaml", ".yml", ".json"}:
                    candidates.append(path)
    for relative in [".dircreative/timeline.jsonl", ".dircreative/learnings.jsonl"]:
        target = project_root / relative
        if target.exists():
            if target.is_symlink():
                raise ValueError(f"legacy source must not be a symlink: {target}")
            candidates.append(target)
    checkpoint_dir = project_root / ".dircreative" / "checkpoints"
    if checkpoint_dir.exists():
        if checkpoint_dir.is_symlink():
            raise ValueError(f"legacy checkpoints root must not be a symlink: {checkpoint_dir}")
        for directory, dirnames, filenames in os.walk(checkpoint_dir, followlinks=False):
            directory_path = Path(directory)
            symlink_dirs = [name for name in dirnames if (directory_path / name).is_symlink()]
            if symlink_dirs:
                raise ValueError(f"legacy checkpoints contain symlink directories: {symlink_dirs}")
            for name in filenames:
                path = directory_path / name
                if path.is_symlink():
                    raise ValueError(f"legacy checkpoint must not be a symlink: {path}")
                if name != ".keep":
                    candidates.append(path)

    rows: list[dict[str, Any]] = []
    for path in sorted(set(candidates)):
        relative = path.relative_to(project_root).as_posix()
        if relative in excluded:
            continue
        stat, source_hash, source_bytes = inspect_regular_file_bytes(path)
        if stat.st_nlink != 1:
            raise ValueError(f"legacy source must not be hardlinked: {path}")
        parsed, semantic_parse_status = parse_semantic_legacy_document(source_bytes, path.suffix)
        source_schema_version = parsed.get("schema_version") if isinstance(parsed, dict) else None
        semantic_current_schema_valid = bool(
            isinstance(parsed, dict)
            and source_schema_version == CURRENT_SCHEMA_VERSION
            and not runtime_schema_errors(parsed)
        )
        semantic_current_record_ids: list[str] = []
        semantic_current_record_hashes: dict[str, str] = {}
        if semantic_current_schema_valid and isinstance(parsed, dict):
            source_records = {
                record.get("record_id"): record
                for record in parsed.get("records", [])
                if isinstance(record, dict) and isinstance(record.get("record_id"), str)
            }
            semantic_current_record_ids = sorted(parsed.get("current_projection", []))
            semantic_current_record_hashes = {
                record_id: hashlib.sha256(
                    _canonical_item(source_records[record_id]).encode("utf-8")
                ).hexdigest()
                for record_id in semantic_current_record_ids
                if record_id in source_records
            }
        if semantic_current_schema_valid:
            disposition = "already_current_or_transform_with_full_semantic_proof"
        elif semantic_parse_status == "parsed":
            disposition = "transform_requires_explicit_semantic_mapping"
        else:
            disposition = "quarantine_until_explicit_semantic_mapping"
        rows.append(
            {
                "source": relative,
                "source_sha256": source_hash,
                "source_schema_version": source_schema_version,
                "semantic_parse_status": semantic_parse_status,
                "semantic_current_schema_valid": semantic_current_schema_valid,
                "semantic_current_record_ids": semantic_current_record_ids,
                "semantic_current_record_hashes": semantic_current_record_hashes,
                "disposition": disposition,
            }
        )
    return rows


def validate_migration_coverage(
    project_root: Path,
    state: dict[str, Any],
    findings: list[Finding],
    *,
    exclude_current_paths: set[str] | None = None,
) -> None:
    try:
        planned_sources = {
            row["source"]
            for row in migration_plan(project_root, exclude_current_paths=exclude_current_paths)
        }
    except (OSError, ValueError) as exc:
        add(findings, "current", "P0", "legacy_discovery_failed", str(exc))
        return
    migrations = state.get("migrations", [])
    mapped_sources = {
        item.get("source")
        for item in migrations
        if isinstance(item, dict) and item.get("mode") in {"transformed", "quarantined", "already_current"}
    }
    for source in sorted(planned_sources - mapped_sources):
        add(
            findings,
            "current",
            "P0",
            "unmapped_legacy_source",
            f"legacy source has no explicit semantic migration: {source}",
        )


def write_state_once(project_root: Path, state_path: Path, state: dict[str, Any]) -> None:
    try:
        state_path.resolve(strict=False).relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError("state path must stay inside project root") from exc
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if state_path.parent.is_symlink():
        raise ValueError("runtime state directory cannot be a symlink")
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    handle, raw_temp = tempfile.mkstemp(prefix=".current.", suffix=".json", dir=state_path.parent)
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temp_path, state_path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ValueError(f"refusing to overwrite existing runtime state: {state_path}") from exc
        except OSError as exc:
            raise ValueError(f"cannot publish runtime state atomically: {exc}") from exc
        directory_fd = os.open(state_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def print_report(findings: list[Finding], summary: dict[str, Any], *, as_json: bool) -> None:
    current = [finding for finding in findings if finding.lane == "current"]
    legacy = [finding for finding in findings if finding.lane == "legacy"]
    current_failed = any(finding.severity == "P0" for finding in current)
    if as_json:
        print(
            json.dumps(
                {
                    "current_integrity": "FAIL" if current_failed else "PASS",
                    "legacy_debt": "PRESENT" if legacy else "NONE",
                    "summary": summary,
                    "findings": [asdict(finding) for finding in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    print("DIRcreative Runtime State Audit")
    print("=" * 72)
    print(f"project_id: {summary.get('project_id', '')}")
    print(f"schema_version: {summary.get('schema_version', '')}")
    print(f"current_records: {summary.get('current_record_count', 0)}")
    print(f"legacy_debt_items: {summary.get('legacy_debt_count', 0)}")
    print(f"current_durable_bytes: {summary.get('total_current_durable_bytes', 0)}")
    print(f"CURRENT_INTEGRITY: {'FAIL' if current_failed else 'PASS'}")
    print(f"LEGACY_DEBT: {'PRESENT' if legacy else 'NONE'}")
    for finding in findings:
        print(f"- [{finding.severity}] {finding.lane}/{finding.code}: {finding.message}")


def current_index(project_root: Path, state: dict[str, Any], thread_snapshot: dict[str, Any] | None = None) -> int:
    findings, _ = validate_state(project_root, state, thread_snapshot=thread_snapshot)
    if any(finding.lane == "current" and finding.severity == "P0" for finding in findings):
        print("CURRENT_INDEX: BLOCKED_BY_INTEGRITY_FAILURE")
        return 1
    index = {record["record_id"]: record for record in state.get("records", [])}
    print("CURRENT_INDEX: READY")
    print(f"stage: {state['current']['stage']['id']} [{state['current']['stage']['status']}]")
    for record_id in state.get("current_projection", []):
        record = index[record_id]
        canonical = record.get("canonical_path")
        if canonical:
            print(f"- {record['kind']} {record['logical_id']}: {(project_root / canonical).resolve()}")
        else:
            print(f"- {record['kind']} {record['logical_id']}: no-file")
    return 0


def sample_state(project_root: Path) -> dict[str, Any]:
    artifact = project_root / "deliverables" / "story.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("current story\n", encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project_id": "self-test",
        "updated_at": now,
        "current": {
            "session_id": "session-1",
            "state_kind": "live_session",
            "stage": {"id": "story-development", "status": "needs_user", "completion_receipt_record_id": None},
            "acceptance": {"status": "not_requested", "receipt_record_id": None},
            "completion_requirements": {
                "required_record_kinds": [],
                "required_logical_ids": [],
                "manifest_required": False,
                "acceptance_required": False,
            },
            "manifest_record_ids": [],
            "generation_authorization_ids": [],
            "thread_record_ids": [],
        },
        "records": [
            {
                "record_id": "story-r1",
                "logical_id": "story",
                "kind": "artifact",
                "revision": 1,
                "lifecycle": "active",
                "canonical_path": "deliverables/story.md",
                "original_path": "deliverables/story.md",
                "sha256": sha256_file(artifact),
                "storage_class": "final",
                "durable": True,
                "regenerable": False,
                "evidence": {
                    "task_visibility": "not_applicable",
                    "checked_at": None,
                    "authorization_record_id": None,
                    "asset_id": None,
                    "authorization_scope_hash": None,
                    "model_id": None,
                },
                "receipt": None,
                "manifest": None,
                "thread": None,
                "generation_authorization": None,
                "supersedes_record_id": None,
                "superseded_by_record_id": None,
                "tombstone": None,
            }
        ],
        "current_projection": ["story-r1"],
        "migrations": [],
        "fixture_migration": {
            "manifest_path": "tests/fixtures/runtime/migration-manifest.json",
            "manifest_sha256": "0" * 64,
            "source_count": 0,
            "completed_at": now,
            "fixture_authority": "none",
            "live_state_authority": False,
            "live_acceptance_authority": False,
            "host_attestation_authority": False,
        },
        "legacy_debt": [],
        "storage_policy": {
            "budget_bytes": 1024 * 1024,
            "warn_at_ratio": 0.8,
            "artifact_roots": ["deliverables"],
            "control_roots": [".dircreative/runs"],
            "classes": {
                "final": {"retention": "preserve", "user_confirmation_required_before_delete": True},
                "necessary_archive": {"retention": "review", "user_confirmation_required_before_delete": True},
                "regenerable_cache": {"retention": "regenerate_then_remove", "user_confirmation_required_before_delete": False},
                "delete_candidate": {"retention": "remove_after_confirmation", "user_confirmation_required_before_delete": True},
            },
        },
    }


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="dircreative-state-") as raw:
        project_root = Path(raw)
        valid = sample_state(project_root)

        def persist_payload(record: dict[str, Any], field: str) -> Path:
            target = project_root / str(record["canonical_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(
                    {
                        "record_id": record["record_id"],
                        "kind": record["kind"],
                        "payload": record[field],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            record["sha256"] = sha256_file(target)
            return target

        assert not runtime_schema_errors(valid)
        assert not runtime_schema_errors(valid, force_builtin=True)
        findings, _ = validate_state(project_root, valid)
        assert not any(finding.lane == "current" and finding.severity == "P0" for finding in findings)

        dangling_projection = json.loads(json.dumps(valid))
        dangling_projection["current_projection"].append("missing-record")
        findings, _ = validate_state(project_root, dangling_projection)
        assert any(finding.code == "projection_record_missing" for finding in findings)

        invalid_final_policy = json.loads(json.dumps(valid))
        invalid_final_policy["storage_policy"]["classes"]["final"] = {
            "retention": "remove_after_confirmation",
            "user_confirmation_required_before_delete": False,
        }
        findings, _ = validate_state(project_root, invalid_final_policy)
        assert any(finding.code in {"schema_validation_failed", "invalid_storage_class_policy"} for finding in findings)

        bool_as_integer = json.loads(json.dumps(valid))
        bool_as_integer["storage_policy"]["classes"]["final"]["user_confirmation_required_before_delete"] = 1
        assert runtime_schema_errors(bool_as_integer, force_builtin=True)
        findings, _ = validate_state(project_root, bool_as_integer)
        assert any(finding.code == "schema_validation_failed" for finding in findings)

        overlapping_roots = json.loads(json.dumps(valid))
        overlapping_roots["storage_policy"]["control_roots"] = ["deliverables/control"]
        findings, _ = validate_state(project_root, overlapping_roots)
        assert any(finding.code == "overlapping_storage_roots" for finding in findings)

        artifact_in_control = json.loads(json.dumps(valid))
        original_artifact = project_root / "deliverables" / "story.md"
        hidden_artifact = project_root / ".dircreative" / "runs" / "story.md"
        hidden_artifact.parent.mkdir(parents=True, exist_ok=True)
        hidden_artifact.write_text(original_artifact.read_text(encoding="utf-8"), encoding="utf-8")
        original_artifact.unlink()
        artifact_in_control["records"][0]["canonical_path"] = ".dircreative/runs/story.md"
        artifact_in_control["records"][0]["original_path"] = ".dircreative/runs/story.md"
        artifact_in_control["records"][0]["sha256"] = sha256_file(hidden_artifact)
        findings, _ = validate_state(project_root, artifact_in_control)
        assert any(finding.code == "artifact_record_outside_artifact_root" for finding in findings)
        hidden_artifact.unlink()
        original_artifact.write_text("current story\n", encoding="utf-8")

        malformed_manifest = json.loads(json.dumps(valid))
        malformed_manifest["current"]["manifest_record_ids"] = [{}]
        findings, _ = validate_state(project_root, malformed_manifest)
        assert any(finding.code == "schema_validation_failed" for finding in findings)

        malformed_evidence = json.loads(json.dumps(valid))
        malformed_evidence["records"][0]["evidence"] = []
        findings, _ = validate_state(project_root, malformed_evidence)
        assert any(finding.code == "schema_validation_failed" for finding in findings)

        null_hash = json.loads(json.dumps(valid))
        null_hash["records"][0]["sha256"] = None
        findings, _ = validate_state(project_root, null_hash)
        assert any(finding.code in {"schema_validation_failed", "missing_durable_hash"} for finding in findings)

        nonfinite = json.loads(json.dumps(valid))
        nonfinite["storage_policy"]["warn_at_ratio"] = float("nan")
        findings, _ = validate_state(project_root, nonfinite)
        assert any(finding.code == "schema_validation_failed" for finding in findings)

        empty_complete = json.loads(json.dumps(valid))
        empty_complete["records"] = []
        empty_complete["current_projection"] = []
        empty_complete["current"]["stage"] = {
            "id": "delivery",
            "status": "complete",
            "completion_receipt_record_id": None,
        }
        findings, _ = validate_state(project_root, empty_complete)
        assert any(finding.code == "empty_or_unproven_completion" for finding in findings)

        complete = json.loads(json.dumps(valid))
        complete["current"]["completion_requirements"] = {
            "required_record_kinds": ["artifact"],
            "required_logical_ids": ["story"],
            "manifest_required": True,
            "acceptance_required": False,
        }
        manifest_record = json.loads(json.dumps(valid["records"][0]))
        manifest_record.update(
            {
                "record_id": "manifest-r1",
                "logical_id": "current-manifest",
                "kind": "manifest",
                "canonical_path": ".dircreative/runs/manifest.json",
                "original_path": ".dircreative/runs/manifest.json",
                "storage_class": "necessary_archive",
                "manifest": {
                    "manifest_type": "artifact_set",
                    "record_ids": ["story-r1"],
                    "created_at": valid["updated_at"],
                },
            }
        )
        manifest_path = persist_payload(manifest_record, "manifest")
        completion_record = json.loads(json.dumps(valid["records"][0]))
        completion_record.update(
            {
                "record_id": "completion-r1",
                "logical_id": "stage-completion",
                "kind": "receipt",
                "canonical_path": ".dircreative/runs/completion.json",
                "original_path": ".dircreative/runs/completion.json",
                "storage_class": "necessary_archive",
                "receipt": {
                    "receipt_type": "validation",
                    "decision": "completed",
                    "evidence_ref": "validation:self-test",
                    "confirmation_id": None,
                    "thread_id": None,
                    "accepted_record_ids": ["story-r1", "manifest-r1"],
                    "accepted_by": None,
                    "accepted_by_type": "not_applicable",
                    "recorded_at": valid["updated_at"],
                },
            }
        )
        completion_path = persist_payload(completion_record, "receipt")
        complete["records"].extend([manifest_record, completion_record])
        complete["current_projection"].extend(["manifest-r1", "completion-r1"])
        complete["current"]["manifest_record_ids"] = ["manifest-r1"]
        complete["current"]["stage"] = {
            "id": "delivery",
            "status": "complete",
            "completion_receipt_record_id": "completion-r1",
        }
        findings, _ = validate_state(project_root, complete)
        assert not any(finding.lane == "current" and finding.severity == "P0" for finding in findings)

        quarantined_current_control = json.loads(json.dumps(complete))
        quarantined_current_control["migrations"] = [
            {
                "migration_id": "migration-current-control",
                "source": ".dircreative/runs/manifest.json",
                "source_sha256": sha256_file(manifest_path),
                "from_schema_version": None,
                "to_schema_version": CURRENT_SCHEMA_VERSION,
                "mode": "quarantined",
                "record_ids": [],
                "transformation_receipt_record_id": None,
                "applied_at": valid["updated_at"],
            }
        ]
        findings, _ = validate_state(project_root, quarantined_current_control)
        assert any(finding.code == "migration_source_missing" for finding in findings)

        opaque_manifest = json.loads(json.dumps(complete))
        manifest_path.write_text("opaque manifest text\n", encoding="utf-8")
        opaque_manifest["records"][1]["sha256"] = sha256_file(manifest_path)
        findings, _ = validate_state(project_root, opaque_manifest)
        assert any(finding.code == "invalid_current_manifest" for finding in findings)

        persist_payload(manifest_record, "manifest")
        unbound_completion = json.loads(json.dumps(complete))
        unbound_completion_record = unbound_completion["records"][2]
        unbound_completion_record["receipt"]["accepted_record_ids"] = []
        persist_payload(unbound_completion_record, "receipt")
        findings, _ = validate_state(project_root, unbound_completion)
        assert any(finding.code == "empty_or_unproven_completion" for finding in findings)

        nondurable_completion = json.loads(json.dumps(complete))
        nondurable_completion["records"] = [
            record for record in nondurable_completion["records"] if record["record_id"] != "manifest-r1"
        ]
        nondurable_completion["current_projection"] = ["story-r1", "completion-r1"]
        nondurable_completion["current"]["manifest_record_ids"] = []
        nondurable_completion["current"]["completion_requirements"]["manifest_required"] = False
        nondurable_story = nondurable_completion["records"][0]
        nondurable_story.update(
            {
                "durable": False,
                "canonical_path": None,
                "original_path": None,
                "sha256": None,
            }
        )
        nondurable_receipt = nondurable_completion["records"][1]
        nondurable_receipt["receipt"]["accepted_record_ids"] = ["story-r1"]
        persist_payload(nondurable_receipt, "receipt")
        original_story_path = project_root / "deliverables" / "story.md"
        original_story_path.unlink()
        findings, _ = validate_state(project_root, nondurable_completion)
        assert any(finding.code == "empty_or_unproven_completion" for finding in findings)
        original_story_path.write_text("current story\n", encoding="utf-8")
        manifest_path.unlink()
        completion_path.unlink()

        missing = json.loads(json.dumps(valid))
        missing["records"][0]["canonical_path"] = "deliverables/missing.md"
        findings, _ = validate_state(project_root, missing)
        assert any(finding.code == "missing_current_file" for finding in findings)

        tombstone = json.loads(json.dumps(valid))
        tombstone["records"][0]["lifecycle"] = "removed"
        tombstone["records"][0]["tombstone"] = {
            "reason": "manual removal",
            "recorded_at": "2026-07-10T00:00:00Z",
        }
        findings, _ = validate_state(project_root, tombstone)
        assert any(finding.code == "nonactive_record_in_projection" for finding in findings)
        assert any(finding.code == "live_removal_attestation_required" for finding in findings)

        removed_without_origin = json.loads(json.dumps(tombstone))
        removed_without_origin["records"][0]["original_path"] = None
        findings, _ = validate_state(project_root, removed_without_origin)
        assert any(finding.code == "removed_without_original_path" for finding in findings)

        debt_source = project_root / ".dircreative" / "legacy" / "old.yaml"
        debt_source.parent.mkdir(parents=True, exist_ok=True)
        debt_source.write_text("status: legacy\n", encoding="utf-8")
        debt = json.loads(json.dumps(valid))
        debt["legacy_debt"] = [
            {
                "debt_id": "legacy-1",
                "severity": "P2",
                "source": ".dircreative/legacy/old.yaml",
                "record_ids": [],
                "reason": "old receipt lacks schema_version",
                "isolated": True,
                "affects_current_projection": False,
            }
        ]
        findings, _ = validate_state(project_root, debt)
        assert not any(finding.lane == "current" and finding.severity == "P0" for finding in findings)
        assert any(finding.lane == "legacy" for finding in findings)
        debt_source.unlink()

        stale_thread = json.loads(json.dumps(valid))
        thread_path = project_root / ".dircreative" / "runs" / "thread.json"
        thread_path.parent.mkdir(parents=True, exist_ok=True)
        thread_path.write_text("{}\n", encoding="utf-8")
        thread_record = json.loads(json.dumps(valid["records"][0]))
        thread_record.update(
            {
                "record_id": "thread-r1",
                "logical_id": "thread-worker-1",
                "kind": "thread",
                "canonical_path": ".dircreative/runs/thread.json",
                "original_path": ".dircreative/runs/thread.json",
                "sha256": sha256_file(thread_path),
                "storage_class": "necessary_archive",
                "evidence": {
                    "task_visibility": "verified",
                    "checked_at": "1970-01-01T00:00:00Z",
                    "authorization_record_id": None,
                    "asset_id": None,
                    "authorization_scope_hash": None,
                    "model_id": None,
                },
                "thread": {
                    "thread_id": "thread-1",
                    "thread_class": "execution_worker",
                    "host_id": "local",
                    "output_status": "completed",
                    "terminal_reason": "completed",
                    "adoption_target": "story-r1",
                    "archive_state": "archived",
                    "checked_at": "1970-01-01T00:00:00Z",
                },
            }
        )
        stale_thread["records"].append(thread_record)
        stale_thread["current_projection"].append("thread-r1")
        stale_thread["current"]["thread_record_ids"].append("thread-r1")
        findings, _ = validate_state(project_root, stale_thread)
        assert any(finding.code == "thread_visibility_stale" for finding in findings)
        thread_path.unlink()

        fresh_fake_thread = json.loads(json.dumps(stale_thread))
        fresh_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        fresh_fake_thread["updated_at"] = fresh_time
        fake_thread_record = fresh_fake_thread["records"][1]
        fake_thread_record["evidence"]["checked_at"] = fresh_time
        fake_thread_record["thread"]["checked_at"] = fresh_time
        thread_path.write_text(
            json.dumps(
                {
                    "record_id": "thread-r1",
                    "kind": "thread",
                    "payload": fake_thread_record["thread"],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        fake_thread_record["sha256"] = sha256_file(thread_path)
        findings, _ = validate_state(project_root, fresh_fake_thread)
        assert any(finding.code == "thread_snapshot_required" for finding in findings)
        thread_path.unlink()

        unrelated_acceptance = json.loads(json.dumps(valid))
        accepted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        unrelated_acceptance["updated_at"] = accepted_at
        bound_thread = json.loads(json.dumps(valid["records"][0]))
        bound_thread.update(
            {
                "record_id": "thread-r1",
                "logical_id": "acceptance-thread",
                "kind": "thread",
                "canonical_path": ".dircreative/runs/thread.json",
                "original_path": ".dircreative/runs/thread.json",
                "storage_class": "necessary_archive",
                "evidence": {
                    "task_visibility": "verified",
                    "checked_at": accepted_at,
                    "authorization_record_id": None,
                    "asset_id": None,
                    "authorization_scope_hash": None,
                    "model_id": None,
                },
                "thread": {
                    "thread_id": "thread-acceptance",
                    "thread_class": "controller",
                    "host_id": "local",
                    "output_status": "completed",
                    "terminal_reason": "completed",
                    "adoption_target": "story-r1",
                    "archive_state": "archived",
                    "checked_at": accepted_at,
                },
            }
        )
        bound_thread_path = persist_payload(bound_thread, "thread")
        bound_acceptance = json.loads(json.dumps(valid["records"][0]))
        bound_acceptance.update(
            {
                "record_id": "acceptance-r1",
                "logical_id": "live-acceptance",
                "kind": "receipt",
                "canonical_path": ".dircreative/runs/acceptance.json",
                "original_path": ".dircreative/runs/acceptance.json",
                "storage_class": "necessary_archive",
                "receipt": {
                    "receipt_type": "live_acceptance",
                    "decision": "accepted",
                    "evidence_ref": "user_confirmation:confirm-1",
                    "confirmation_id": "confirm-1",
                    "thread_id": "thread-acceptance",
                    "accepted_record_ids": ["thread-r1"],
                    "accepted_by": "user-1",
                    "accepted_by_type": "human",
                    "recorded_at": accepted_at,
                },
            }
        )
        bound_acceptance_path = persist_payload(bound_acceptance, "receipt")
        unrelated_acceptance["records"].extend([bound_thread, bound_acceptance])
        unrelated_acceptance["current_projection"].extend(["thread-r1", "acceptance-r1"])
        unrelated_acceptance["current"]["thread_record_ids"] = ["thread-r1"]
        unrelated_acceptance["current"]["acceptance"] = {
            "status": "accepted",
            "receipt_record_id": "acceptance-r1",
        }
        acceptance_snapshot = {
            "schema_version": "1.0.0",
            "provider": "codex_app.list_threads",
            "captured_at": accepted_at,
            "threads": [
                {
                    "thread_id": "thread-acceptance",
                    "host_id": "local",
                    "status": "completed",
                    "archived": True,
                    "confirmations": [
                        {
                            "confirmation_id": "confirm-1",
                            "actor_type": "human",
                            "actor_id": "user-1",
                        }
                    ],
                }
            ],
        }
        findings, _ = validate_state(
            project_root,
            unrelated_acceptance,
            thread_snapshot=acceptance_snapshot,
        )
        assert any(finding.code == "accepted_without_bound_receipt" for finding in findings)
        assert any(finding.code == "live_host_attestation_required" for finding in findings)
        bound_thread_path.unlink()
        bound_acceptance_path.unlink()

        false_acceptance = json.loads(json.dumps(valid))
        receipt_record = json.loads(json.dumps(valid["records"][0]))
        receipt_record.update(
            {
                "record_id": "acceptance-r1",
                "logical_id": "live-acceptance",
                "kind": "receipt",
                "canonical_path": None,
                "original_path": None,
                "sha256": None,
                "durable": False,
                "storage_class": "necessary_archive",
                "receipt": {
                    "receipt_type": "live_acceptance",
                    "decision": "accepted",
                    "evidence_ref": "user_confirmation:test",
                    "confirmation_id": "test",
                    "thread_id": "thread-missing",
                    "accepted_record_ids": ["story-r1"],
                    "accepted_by": "fake-user",
                    "accepted_by_type": "human",
                    "recorded_at": valid["updated_at"],
                },
            }
        )
        false_acceptance["records"].append(receipt_record)
        false_acceptance["current_projection"].append("acceptance-r1")
        false_acceptance["current"]["acceptance"] = {"status": "accepted", "receipt_record_id": "acceptance-r1"}
        findings, _ = validate_state(project_root, false_acceptance)
        assert any(finding.code == "accepted_without_bound_receipt" for finding in findings)

        auth_path = project_root / ".dircreative" / "runs" / "authorization.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        media_path = project_root / "deliverables" / "generated.png"
        media_path.write_bytes(b"generated-media")
        invalid_authorization = json.loads(json.dumps(valid))
        authorization_record = json.loads(json.dumps(valid["records"][0]))
        authorization_record.update(
            {
                "record_id": "auth-r1",
                "logical_id": "generation-auth",
                "kind": "generation_authorization",
                "canonical_path": ".dircreative/runs/authorization.json",
                "original_path": ".dircreative/runs/authorization.json",
                "sha256": None,
                "storage_class": "necessary_archive",
                "generation_authorization": {
                    "work_id": "self-test",
                    "asset_ids": ["asset-a"],
                    "expected_output_kinds": ["generated_media"],
                    "model_ids": ["model-a"],
                    "scope_hash": "",
                    "status": "active",
                    "authorized_by": "user:test",
                    "authorized_by_type": "human",
                    "authorized_at": valid["updated_at"],
                    "evidence_ref": "user_confirmation:auth-confirmation",
                    "confirmation_id": "auth-confirmation",
                    "thread_id": "auth-thread",
                    "expires_at": None,
                },
            }
        )
        authorization_record["generation_authorization"]["scope_hash"] = canonical_authorization_scope(
            authorization_record["generation_authorization"]
        )
        auth_path.write_text(
            json.dumps(
                {
                    "record_id": "auth-r1",
                    "kind": "generation_authorization",
                    "payload": authorization_record["generation_authorization"],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        authorization_record["sha256"] = sha256_file(auth_path)
        generated_record = json.loads(json.dumps(valid["records"][0]))
        generated_record.update(
            {
                "record_id": "media-r1",
                "logical_id": "generated-asset-a",
                "kind": "generated_media",
                "canonical_path": "deliverables/generated.png",
                "original_path": "deliverables/generated.png",
                "sha256": sha256_file(media_path),
                "evidence": {
                    "task_visibility": "not_applicable",
                    "checked_at": None,
                    "authorization_record_id": "auth-r1",
                    "asset_id": "asset-b",
                    "authorization_scope_hash": authorization_record["generation_authorization"]["scope_hash"],
                    "model_id": "model-a",
                },
            }
        )
        invalid_authorization["records"].extend([authorization_record, generated_record])
        invalid_authorization["current_projection"].extend(["auth-r1", "media-r1"])
        invalid_authorization["current"]["generation_authorization_ids"].append("auth-r1")
        snapshot = {
            "schema_version": "1.0.0",
            "provider": "codex_app.list_threads",
            "captured_at": valid["updated_at"],
            "threads": [
                {
                    "thread_id": "auth-thread",
                    "host_id": "local",
                    "status": "idle",
                    "archived": False,
                    "confirmations": [
                        {
                            "confirmation_id": "auth-confirmation",
                            "actor_type": "human",
                            "actor_id": "user:test",
                        }
                    ],
                }
            ],
        }
        findings, _ = validate_state(project_root, invalid_authorization, thread_snapshot=snapshot)
        assert any(finding.code == "generated_media_unauthorized" for finding in findings)

        forged_scope = json.loads(json.dumps(invalid_authorization))
        forged_auth = next(item for item in forged_scope["records"] if item["record_id"] == "auth-r1")
        forged_media = next(item for item in forged_scope["records"] if item["record_id"] == "media-r1")
        forged_auth["generation_authorization"]["scope_hash"] = "b" * 64
        forged_media["evidence"]["asset_id"] = "asset-a"
        forged_media["evidence"]["authorization_scope_hash"] = "b" * 64
        auth_path.write_text(
            json.dumps(
                {
                    "record_id": "auth-r1",
                    "kind": "generation_authorization",
                    "payload": forged_auth["generation_authorization"],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        forged_auth["sha256"] = sha256_file(auth_path)
        findings, _ = validate_state(project_root, forged_scope, thread_snapshot=snapshot)
        assert any(finding.code == "invalid_generation_authorization" for finding in findings)
        auth_path.unlink()
        media_path.unlink()

        untracked_path = project_root / "deliverables" / "manual.txt"
        untracked_path.write_text("manual\n", encoding="utf-8")
        findings, _ = validate_state(project_root, valid)
        assert any(finding.code == "untracked_artifact" for finding in findings)
        untracked_path.unlink()

        original_story = project_root / "deliverables" / "story.md"
        external_source = project_root / "external-source.md"
        external_source.write_text("current story\n", encoding="utf-8")
        original_story.unlink()
        os.link(external_source, original_story)
        hardlink_state = json.loads(json.dumps(valid))
        hardlink_state["records"][0]["sha256"] = sha256_file(original_story)
        findings, _ = validate_state(project_root, hardlink_state)
        assert any(finding.code in {"hardlinked_current_file", "hardlinked_managed_file"} for finding in findings)
        original_story.unlink()
        original_story.write_text("current story\n", encoding="utf-8")
        external_source.unlink()

        second_path = project_root / "deliverables" / "story-v2.md"
        second_path.write_text("next story\n", encoding="utf-8")
        cyclic = json.loads(json.dumps(valid))
        first_record = cyclic["records"][0]
        first_record["supersedes_record_id"] = "story-r2"
        first_record["superseded_by_record_id"] = "story-r2"
        second_record = json.loads(json.dumps(first_record))
        second_record.update(
            {
                "record_id": "story-r2",
                "logical_id": "different-story",
                "revision": 2,
                "canonical_path": "deliverables/story-v2.md",
                "original_path": "deliverables/story-v2.md",
                "sha256": sha256_file(second_path),
                "supersedes_record_id": "story-r1",
                "superseded_by_record_id": "story-r1",
            }
        )
        cyclic["records"].append(second_record)
        cyclic["current_projection"].append("story-r2")
        findings, _ = validate_state(project_root, cyclic)
        assert any(finding.code == "supersession_cycle" for finding in findings)
        assert any(finding.code == "cross_logical_supersession" for finding in findings)
        second_path.unlink()

        long_index: dict[str, dict[str, Any]] = {}
        long_count = 1500
        for position in range(long_count):
            record_id = f"long-{position}"
            long_index[record_id] = {
                "record_id": record_id,
                "logical_id": "long-history",
                "revision": position + 1,
                "lifecycle": "active" if position == long_count - 1 else "superseded",
                "supersedes_record_id": f"long-{position - 1}" if position else None,
                "superseded_by_record_id": f"long-{position + 1}" if position < long_count - 1 else None,
            }
        long_findings: list[Finding] = []
        validate_supersession(long_index, [f"long-{long_count - 1}"], long_findings)
        assert not any(finding.code == "supersession_cycle" for finding in long_findings)

        invalid_migration = json.loads(json.dumps(valid))
        invalid_migration["migrations"] = [{"source": ".dircreative/runs/old.yaml"}]
        findings, _ = validate_state(project_root, invalid_migration)
        assert any(finding.code == "schema_validation_failed" for finding in findings)

        nested_run = project_root / ".dircreative" / "runs" / "nested" / "old.yaml"
        nested_run.parent.mkdir(parents=True, exist_ok=True)
        nested_run.write_text("status: old\n", encoding="utf-8")
        assert any(row["source"] == ".dircreative/runs/nested/old.yaml" for row in migration_plan(project_root))
        findings, _ = validate_state(project_root, valid)
        assert any(finding.code == "unmapped_legacy_source" for finding in findings)

        wrong_mode = json.loads(json.dumps(valid))
        wrong_mode["migrations"] = [
            {
                "migration_id": "migration-old",
                "source": ".dircreative/runs/nested/old.yaml",
                "source_sha256": sha256_file(nested_run),
                "from_schema_version": CURRENT_SCHEMA_VERSION,
                "to_schema_version": CURRENT_SCHEMA_VERSION,
                "mode": "already_current",
                "record_ids": ["story-r1"],
                "transformation_receipt_record_id": None,
                "applied_at": valid["updated_at"],
            }
        ]
        findings, _ = validate_state(project_root, wrong_mode)
        assert any(finding.code == "legacy_marked_current" for finding in findings)
        assert any(finding.code == "migration_source_version_mismatch" for finding in findings)

        current_source = project_root / ".dircreative" / "runs" / "current-source.json"
        source_only = json.loads(json.dumps(valid))
        source_only["records"][0]["record_id"] = "source-only"
        source_only["current_projection"] = ["source-only"]
        current_source.write_text(
            json.dumps(source_only, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        current_source_row = next(
            row for row in migration_plan(project_root) if row["source"] == ".dircreative/runs/current-source.json"
        )
        assert current_source_row["semantic_current_schema_valid"] is True
        mismatched_current_binding = json.loads(json.dumps(valid))
        mismatched_current_binding["migrations"] = [
            {
                "migration_id": "migration-current-binding",
                "source": ".dircreative/runs/current-source.json",
                "source_sha256": current_source_row["source_sha256"],
                "from_schema_version": CURRENT_SCHEMA_VERSION,
                "to_schema_version": CURRENT_SCHEMA_VERSION,
                "mode": "already_current",
                "record_ids": ["story-r1"],
                "transformation_receipt_record_id": None,
                "applied_at": valid["updated_at"],
            }
        ]
        findings, _ = validate_state(project_root, mismatched_current_binding)
        assert any(finding.code == "already_current_record_binding_mismatch" for finding in findings)
        current_source.unlink()

        bad_transform = json.loads(json.dumps(valid))
        transform_receipt = json.loads(json.dumps(valid["records"][0]))
        transform_receipt.update(
            {
                "record_id": "transform-receipt-r1",
                "logical_id": "migration-transform-receipt",
                "kind": "receipt",
                "canonical_path": ".dircreative/runs/transform.json",
                "original_path": ".dircreative/runs/transform.json",
                "storage_class": "necessary_archive",
                "receipt": {
                    "receipt_type": "execution",
                    "decision": "completed",
                    "evidence_ref": "migration:migration-transform",
                    "confirmation_id": None,
                    "thread_id": None,
                    "accepted_record_ids": ["story-r1"],
                    "accepted_by": None,
                    "accepted_by_type": "not_applicable",
                    "recorded_at": valid["updated_at"],
                },
            }
        )
        transform_receipt_path = persist_payload(transform_receipt, "receipt")
        bad_transform["records"].append(transform_receipt)
        bad_transform["current_projection"].append("transform-receipt-r1")
        bad_transform["migrations"] = [
            {
                "migration_id": "migration-transform",
                "source": ".dircreative/runs/nested/old.yaml",
                "source_sha256": sha256_file(nested_run),
                "from_schema_version": None,
                "to_schema_version": CURRENT_SCHEMA_VERSION,
                "mode": "transformed",
                "record_ids": ["story-r1"],
                "transformation_receipt_record_id": "transform-receipt-r1",
                "applied_at": valid["updated_at"],
            }
        ]
        findings, _ = validate_state(project_root, bad_transform)
        assert any(finding.code == "transformation_receipt_missing" for finding in findings)
        assert any(finding.code == "transformed_record_not_isolated" for finding in findings)
        transform_receipt_path.unlink()

        missing_quarantine = json.loads(json.dumps(valid))
        missing_quarantine["migrations"] = [
            {
                "migration_id": "migration-missing",
                "source": ".dircreative/runs/does-not-exist.yaml",
                "source_sha256": "0" * 64,
                "from_schema_version": None,
                "to_schema_version": CURRENT_SCHEMA_VERSION,
                "mode": "quarantined",
                "record_ids": [],
                "transformation_receipt_record_id": None,
                "applied_at": valid["updated_at"],
            }
        ]
        findings, _ = validate_state(project_root, missing_quarantine)
        assert any(finding.code == "migration_source_missing" for finding in findings)

        spoofed_current = project_root / ".dircreative" / "runs" / "spoofed-current.yaml"
        spoofed_current.write_text('schema_version: "1.0.0"\nrecords: [\n', encoding="utf-8")
        spoofed_row = next(
            row for row in migration_plan(project_root) if row["source"] == ".dircreative/runs/spoofed-current.yaml"
        )
        assert spoofed_row["semantic_current_schema_valid"] is False
        spoofed_mapping = json.loads(json.dumps(valid))
        spoofed_mapping["migrations"] = [
            {
                "migration_id": "migration-spoofed",
                "source": ".dircreative/runs/spoofed-current.yaml",
                "source_sha256": spoofed_row["source_sha256"],
                "from_schema_version": CURRENT_SCHEMA_VERSION,
                "to_schema_version": CURRENT_SCHEMA_VERSION,
                "mode": "already_current",
                "record_ids": ["story-r1"],
                "transformation_receipt_record_id": None,
                "applied_at": valid["updated_at"],
            }
        ]
        findings, _ = validate_state(project_root, spoofed_mapping)
        assert any(finding.code == "legacy_marked_current" for finding in findings)
        spoofed_current.unlink()

        quarantine_adopts_current = json.loads(json.dumps(valid))
        quarantine_adopts_current["migrations"] = [
            {
                "migration_id": "migration-quarantine",
                "source": ".dircreative/runs/nested/old.yaml",
                "source_sha256": sha256_file(nested_run),
                "from_schema_version": None,
                "to_schema_version": CURRENT_SCHEMA_VERSION,
                "mode": "quarantined",
                "record_ids": ["story-r1"],
                "transformation_receipt_record_id": None,
                "applied_at": valid["updated_at"],
            }
        ]
        findings, _ = validate_state(project_root, quarantine_adopts_current)
        assert any(finding.code == "quarantine_references_records" for finding in findings)
        nested_run.unlink()

        alias_debt = json.loads(json.dumps(valid))
        alias_debt["legacy_debt"] = [
            {
                "debt_id": "alias-current",
                "severity": "P1",
                "source": "deliverables/./story.md",
                "record_ids": [],
                "reason": "alias attempt",
                "isolated": True,
                "affects_current_projection": False,
            }
        ]
        findings, _ = validate_state(project_root, alias_debt)
        assert any(finding.code == "legacy_debt_not_isolated" for finding in findings)

        git_config = project_root / ".git" / "config"
        git_config.parent.mkdir(parents=True, exist_ok=True)
        git_config.write_text("[core]\n", encoding="utf-8")
        unsafe_managed = json.loads(json.dumps(valid))
        unsafe_record = json.loads(json.dumps(valid["records"][0]))
        unsafe_record.update(
            {
                "record_id": "unsafe-r1",
                "logical_id": "unsafe-cache",
                "revision": 1,
                "lifecycle": "archived",
                "canonical_path": ".git/config",
                "original_path": ".git/config",
                "sha256": sha256_file(git_config),
                "storage_class": "delete_candidate",
                "tombstone": {"reason": "test", "recorded_at": valid["updated_at"]},
            }
        )
        unsafe_managed["records"].append(unsafe_record)
        findings, _ = validate_state(project_root, unsafe_managed)
        assert any(finding.code in {"managed_path_outside_roots", "invalid_delete_candidate_lifecycle"} for finding in findings)
        git_config.unlink()

        runs_root = project_root / ".dircreative" / "runs"
        if runs_root.exists():
            for directory in sorted(runs_root.glob("*"), reverse=True):
                if directory.is_dir():
                    directory.rmdir()
            runs_root.rmdir()
        with tempfile.TemporaryDirectory(prefix="dircreative-external-runs-") as external_raw:
            external_root = Path(external_raw)
            (external_root / "outside.yaml").write_text("status: outside\n", encoding="utf-8")
            runs_root.symlink_to(external_root, target_is_directory=True)
            try:
                migration_plan(project_root)
            except ValueError as exc:
                assert "must not be a symlink" in str(exc)
            else:
                raise AssertionError("symlinked legacy root was traversed")
            runs_root.unlink()
        runs_root.mkdir(parents=True, exist_ok=True)

        migration_findings: list[Finding] = []
        validate_migration_coverage(project_root, valid, migration_findings)
        assert not migration_findings
        state_path = project_root / DEFAULT_STATE_PATH
        write_state_once(project_root, state_path, valid)
        assert load_state(state_path)["schema_version"] == CURRENT_SCHEMA_VERSION
        try:
            write_state_once(project_root, state_path, valid)
        except ValueError as exc:
            assert "refusing to overwrite" in str(exc)
        else:
            raise AssertionError("migration writer overwrote an existing state file")

    print("DIRCREATIVE_STATE_AUDIT_SELF_TEST=PASS")
    return 0


def resolve_state_path(project_root: Path, value: str | None) -> Path:
    if value:
        candidate = Path(value).expanduser()
        return candidate if candidate.is_absolute() else project_root / candidate
    return project_root / DEFAULT_STATE_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DIRcreative current state separately from legacy debt.")
    parser.add_argument("command", choices=["audit", "current-index", "migration-plan", "migrate", "self-test"])
    parser.add_argument("--project-root", default=".", help="Standalone DIRcreative project root.")
    parser.add_argument("--state", help="Runtime state path; defaults to .dircreative/state/current.json.")
    parser.add_argument("--mapping", help="Complete v1 runtime state JSON used by the migrate command.")
    parser.add_argument(
        "--thread-snapshot",
        help="Fresh JSON exported from codex_app.list_threads, including host confirmation IDs when required.",
    )
    parser.add_argument("--write", action="store_true", help="Write a validated migration once; never overwrites existing state.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON for audit or migration-plan.")
    args = parser.parse_args()

    if args.command == "self-test":
        return self_test()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        print(f"ERROR: project root does not exist: {project_root}")
        return 2

    thread_snapshot: dict[str, Any] | None = None
    if args.thread_snapshot:
        snapshot_path = Path(args.thread_snapshot).expanduser()
        if not snapshot_path.is_absolute():
            snapshot_path = project_root / snapshot_path
        try:
            thread_snapshot = load_state(snapshot_path)
        except ValueError as exc:
            print(f"THREAD_SNAPSHOT: FAIL\n- {exc}")
            return 1

    if args.command == "migration-plan":
        excluded_paths: set[str] = set()
        current_state_path = resolve_state_path(project_root, args.state)
        if current_state_path.exists():
            try:
                current_state = load_state(current_state_path)
            except ValueError as exc:
                print(f"MIGRATION_PLAN: FAIL\n- current state cannot be read safely: {exc}")
                return 1
            if runtime_schema_errors(current_state):
                print("MIGRATION_PLAN: FAIL\n- current state schema is invalid; refusing to hide any control source")
                return 1
            current_findings: list[Finding] = []
            current_index_map = record_index(current_state.get("records"), current_findings)
            excluded_paths = current_control_paths(project_root, current_state, current_index_map)
        try:
            rows = migration_plan(project_root, exclude_current_paths=excluded_paths)
        except (OSError, ValueError) as exc:
            print(f"MIGRATION_PLAN: FAIL\n- {exc}")
            return 1
        if args.json:
            print(json.dumps({"project_root": str(project_root), "sources": rows}, ensure_ascii=False, indent=2))
        else:
            print("DIRcreative Semantic Migration Plan")
            print("=" * 72)
            print(f"legacy_sources: {len(rows)}")
            for row in rows:
                print(f"- {row['source']}: {row['disposition']}")
            print("MIGRATION_WRITE_ALLOWED: false_without_explicit_mapping")
        return 0

    if args.command == "migrate":
        if not args.mapping:
            print("MIGRATION_READY: NO\n- [P0] current/mapping_required: --mapping is required")
            return 2
        mapping_path = Path(args.mapping).expanduser()
        if not mapping_path.is_absolute():
            mapping_path = project_root / mapping_path
        try:
            candidate = load_state(mapping_path)
        except ValueError as exc:
            print(f"MIGRATION_READY: NO\n- [P0] current/mapping_invalid: {exc}")
            return 1
        findings, summary = validate_state(project_root, candidate, thread_snapshot=thread_snapshot)
        print_report(findings, summary, as_json=args.json)
        if any(finding.lane == "current" and finding.severity == "P0" for finding in findings):
            print("MIGRATION_READY: NO")
            return 1
        print("MIGRATION_READY: YES")
        if not args.write:
            print("MIGRATION_WRITE: SKIPPED_DRY_RUN")
            return 0
        state_path = resolve_state_path(project_root, args.state)
        canonical_state_path = project_root / DEFAULT_STATE_PATH
        if state_path.resolve(strict=False) != canonical_state_path.resolve(strict=False):
            print(f"MIGRATION_WRITE: FAIL\n- write target must be canonical: {canonical_state_path}")
            return 1
        try:
            write_state_once(project_root, state_path, candidate)
        except ValueError as exc:
            print(f"MIGRATION_WRITE: FAIL\n- {exc}")
            return 1
        print(f"MIGRATION_WRITE: PASS\nstate_path: {state_path}")
        return 0

    state_path = resolve_state_path(project_root, args.state)
    try:
        state = load_state(state_path)
    except ValueError as exc:
        print(f"CURRENT_INTEGRITY: FAIL\n- [P0] current/state_unavailable: {exc}")
        return 1

    if args.command == "current-index":
        return current_index(project_root, state, thread_snapshot)

    findings, summary = validate_state(project_root, state, thread_snapshot=thread_snapshot)
    print_report(findings, summary, as_json=args.json)
    return 1 if any(finding.lane == "current" and finding.severity == "P0" for finding in findings) else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
