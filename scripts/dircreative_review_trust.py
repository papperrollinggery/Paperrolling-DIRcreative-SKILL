#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from dircreative_validation_common import safe_relative_path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_REGISTRY_PATH = ROOT / "skills/dircreative/runtime/review-trust-registry.json"
REVIEW_TRUST_REGISTRY_ENV = "DIRCREATIVE_REVIEW_TRUST_REGISTRY"


def default_review_trust_registry_path() -> Path:
    configured = os.environ.get(REVIEW_TRUST_REGISTRY_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex/dircreative/review-trust-registry.json"


DEFAULT_REGISTRY_PATH = default_review_trust_registry_path()
SENSITIVE_KEY_RE = re.compile(
    r"(?:api[_-]?key|password|secret|token|credential|private[_-]?key|authorization|cookie|session(?:[_-]?(?:id|key|cookie))?)",
    re.I,
)
SENSITIVE_VALUE_RE = re.compile(
    r"(?:\bAKIA[0-9A-Z]{16}\b|\b(?:sk|ghp|github_pat)[_-][A-Za-z0-9_-]{16,}|\bBearer\s+\S+|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
    re.I,
)


def sensitive_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if SENSITIVE_KEY_RE.search(str(key)):
                found.append(child)
            found.extend(sensitive_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(sensitive_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str) and SENSITIVE_VALUE_RE.search(value):
        found.append(path)
    return found


def resolve_review_key(
    authority_id: Any,
    *,
    registry_path: Path | None = None,
    artifact_root: Path | None = None,
) -> tuple[Path | None, str | None, dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    registry_path = registry_path or default_review_trust_registry_path()
    try:
        registry_resolved = registry_path.resolve(strict=True)
        registry = json.loads(registry_resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, None, [f"review_trust_registry_invalid: {registry_path}"]
    if (
        not isinstance(registry, dict)
        or registry.get("schema_version") != "1.0.0"
        or registry.get("authority") != "host_configuration_only"
        or not isinstance(registry.get("review_authorities"), list)
    ):
        return None, None, None, [f"review_trust_registry_invalid: {registry_path}"]
    entries = [item for item in registry["review_authorities"] if isinstance(item, dict)]
    ids = [str(item.get("authority_id")) for item in entries]
    if len(ids) != len(set(ids)):
        return None, None, None, ["review_trust_authority_duplicate: registry"]
    entry = next((item for item in entries if item.get("authority_id") == authority_id), None)
    if entry is None or entry.get("status") != "active":
        return None, None, None, [f"review_authority_unconfigured: {authority_id}"]
    if (
        entry.get("authority_kind")
        not in {"asset_reviewer", "ledger_host", "media_provider", "human_reviewer", "delivery_host", "billing_provider"}
        or not isinstance(entry.get("actor_id"), str)
        or not entry.get("actor_id")
        or not isinstance(entry.get("allowed_purposes"), list)
        or not entry.get("allowed_purposes")
        or not isinstance(entry.get("allowed_sources"), list)
        or not entry.get("allowed_sources")
    ):
        return None, None, None, [f"review_authority_policy_invalid: {authority_id}"]
    relative = entry.get("public_key_relative_path")
    if not safe_relative_path(relative):
        return None, None, None, [f"review_public_key_path_invalid: {relative}"]
    try:
        public_key = (registry_resolved.parent / str(relative)).resolve(strict=True)
        public_key.relative_to(registry_resolved.parent)
    except ValueError:
        return None, None, None, [f"review_public_key_path_invalid: {relative}"]
    except (FileNotFoundError, RuntimeError):
        return None, None, None, [f"review_public_key_missing: {relative}"]
    if artifact_root is not None:
        try:
            public_key.relative_to(artifact_root.resolve(strict=True))
        except ValueError:
            pass
        except (FileNotFoundError, RuntimeError):
            return None, None, None, [f"review_artifact_root_invalid: {artifact_root}"]
        else:
            return None, None, None, [f"review_public_key_not_detached: {relative}"]
    expected_sha256 = entry.get("public_key_sha256")
    if hashlib.sha256(public_key.read_bytes()).hexdigest() != expected_sha256:
        return None, None, None, [f"review_public_key_hash_mismatch: {authority_id}"]
    openssl = shutil.which("openssl")
    if openssl is None:
        return None, None, None, ["review_signature_verifier_unavailable: openssl"]
    return public_key, openssl, entry, errors


def verify_detached_review_artifact(
    payload_path: Path,
    signature_path: Path,
    *,
    authority_id: Any,
    actor: Any,
    purpose: str,
    source: str,
    registry_path: Path | None = None,
    artifact_root: Path | None = None,
) -> list[str]:
    public_key, openssl, policy, errors = resolve_review_key(
        authority_id,
        registry_path=registry_path,
        artifact_root=artifact_root,
    )
    if errors:
        return errors
    if policy is None or (
        policy.get("authority_kind") != "human_reviewer"
        or policy.get("actor_id") != actor
        or purpose not in policy.get("allowed_purposes", [])
        or source not in policy.get("allowed_sources", [])
    ):
        return [f"review_authority_scope_invalid: {authority_id}"]
    if public_key is None or openssl is None:
        return ["review_signature_verifier_unavailable: openssl"]
    result = subprocess.run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-verify",
            str(public_key),
            "-signature",
            str(signature_path),
            str(payload_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    return [] if result.returncode == 0 else [f"review_signature_invalid: {authority_id}"]


def load_registry(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "invalid"
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != "1.0.0"
        or payload.get("authority") != "host_configuration_only"
        or not isinstance(payload.get("review_authorities"), list)
    ):
        return None, "invalid"
    return payload, None


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def cli_status(path: Path) -> int:
    registry, error = load_registry(path)
    capabilities = {
        "prompt_authority_review": False,
        "signed_review_validation": False,
    }
    if error:
        print(json.dumps({
            "status": "TOOL_BLOCKED",
            "reason": f"review_trust_registry_{error}",
            "registry_path": str(path),
            "template_path": str(TEMPLATE_REGISTRY_PATH),
            "capabilities": capabilities,
        }, sort_keys=True))
        return 2
    entries = [item for item in registry["review_authorities"] if isinstance(item, dict)]
    if not entries:
        print(json.dumps({
            "status": "TOOL_BLOCKED",
            "reason": "review_trust_registry_empty",
            "registry_path": str(path),
            "authority_count": 0,
            "capabilities": capabilities,
        }, sort_keys=True))
        return 2
    audit_errors: list[str] = []
    for entry in entries:
        _, _, _, errors = resolve_review_key(entry.get("authority_id"), registry_path=path)
        audit_errors.extend(errors)
    print(json.dumps({
        "status": "TOOL_BLOCKED" if audit_errors else "ready",
        "registry_path": str(path),
        "authority_count": len(entries),
        "authority_ids": sorted(str(item.get("authority_id")) for item in entries),
        "errors": audit_errors,
        "capabilities": {
            "prompt_authority_review": not audit_errors,
            "signed_review_validation": not audit_errors,
        },
    }, sort_keys=True))
    return 2 if audit_errors else 0


def cli_provision(args: argparse.Namespace) -> int:
    registry_path = args.registry or default_review_trust_registry_path()
    public_key = args.public_key.expanduser()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:+-]*", args.authority_id):
        print(json.dumps({"status": "blocked", "reason": "authority_id_invalid"}))
        return 2
    try:
        public_resolved = public_key.resolve(strict=True)
    except OSError:
        print(json.dumps({"status": "blocked", "reason": "public_key_missing"}))
        return 2
    openssl = shutil.which("openssl")
    if openssl is None:
        print(json.dumps({"status": "blocked", "reason": "public_key_invalid"}))
        return 2
    key_check = subprocess.run(
        [openssl, "pkey", "-pubin", "-in", str(public_resolved), "-noout"],
        capture_output=True,
        check=False,
    )
    normalized = subprocess.run(
        [openssl, "pkey", "-pubin", "-in", str(public_resolved), "-pubout"],
        capture_output=True,
        check=False,
    )
    cmp_binary = shutil.which("cmp")
    canonical_public = (
        subprocess.run(
            [cmp_binary, "-s", str(public_resolved), "-"],
            input=normalized.stdout,
            capture_output=True,
            check=False,
        )
        if cmp_binary is not None and normalized.returncode == 0
        else None
    )
    if key_check.returncode != 0 or canonical_public is None or canonical_public.returncode != 0:
        print(json.dumps({"status": "blocked", "reason": "public_key_invalid"}))
        return 2
    public_bytes = public_resolved.read_bytes()
    existing, error = load_registry(registry_path)
    if error == "invalid":
        print(json.dumps({"status": "blocked", "reason": "review_trust_registry_invalid", "registry_path": str(registry_path)}))
        return 2
    registry = existing or {
        "schema_version": "1.0.0",
        "authority": "host_configuration_only",
        "review_authorities": [],
    }
    entries = registry["review_authorities"]
    if any(item.get("authority_id") == args.authority_id for item in entries if isinstance(item, dict)):
        print(json.dumps({"status": "blocked", "reason": "authority_already_exists", "authority_id": args.authority_id}))
        return 2
    key_relative = f"keys/{args.authority_id}.pem"
    entry = {
        "authority_id": args.authority_id,
        "authority_kind": args.authority_kind,
        "actor_id": args.actor_id,
        "allowed_purposes": list(dict.fromkeys(args.allowed_purpose)),
        "allowed_sources": list(dict.fromkeys(args.allowed_source)),
        "status": "active",
        "public_key_relative_path": key_relative,
        "public_key_sha256": hashlib.sha256(public_bytes).hexdigest(),
    }
    print(json.dumps({
        "status": "apply_ready" if args.apply else "dry_run",
        "registry_path": str(registry_path),
        "public_key_destination": str(registry_path.parent / key_relative),
        "entry": entry,
        "private_key_generated": False,
    }, sort_keys=True))
    if not args.apply:
        return 0
    key_destination = registry_path.parent / key_relative
    if key_destination.exists():
        print(json.dumps({"status": "blocked", "reason": "public_key_destination_exists", "path": str(key_destination)}))
        return 2
    atomic_write(key_destination, public_bytes)
    registry["review_authorities"] = [*entries, entry]
    atomic_write(
        registry_path,
        (json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage host-owned DIRcreative review trust public keys.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--registry", type=Path)
    provision = subparsers.add_parser("provision-public-key")
    provision.add_argument("--registry", type=Path)
    provision.add_argument("--authority-id", required=True)
    provision.add_argument("--actor-id", required=True)
    provision.add_argument("--authority-kind", default="human_reviewer", choices=["human_reviewer", "asset_reviewer"])
    provision.add_argument("--public-key", type=Path, required=True)
    provision.add_argument("--allowed-purpose", action="append", required=True)
    provision.add_argument("--allowed-source", action="append", required=True)
    provision.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "status":
        return cli_status(args.registry or default_review_trust_registry_path())
    return cli_provision(args)


if __name__ == "__main__":
    raise SystemExit(main())
