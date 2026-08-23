#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from dircreative_validation_common import safe_relative_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = ROOT / "skills/dircreative/runtime/review-trust-registry.json"
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
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    artifact_root: Path | None = None,
) -> tuple[Path | None, str | None, dict[str, Any] | None, list[str]]:
    errors: list[str] = []
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
