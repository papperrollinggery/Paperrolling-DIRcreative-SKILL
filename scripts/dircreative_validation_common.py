#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]

from dircreative_state_audit import _builtin_schema_errors


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add_error(errors: list[str], code: str, detail: str) -> None:
    errors.append(f"{code}: {detail}")


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_relative_path(raw: Any) -> bool:
    return (
        isinstance(raw, str)
        and bool(raw)
        and not raw.startswith("/")
        and "\\" not in raw
        and all(part not in {"", ".", ".."} for part in raw.split("/"))
    )


def schema_errors(document: dict[str, Any], schema_path: Path) -> list[str]:
    schema = load_json(schema_path)
    if Draft202012Validator is None or os.environ.get(
        "DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"
    ):
        return [
            f"schema_error: {error}"
            for error in _builtin_schema_errors(document, schema, schema, "$")
        ]
    validator = Draft202012Validator(schema)
    return [
        "schema_error: "
        + "/".join(str(item) for item in error.absolute_path)
        + f": {error.message}"
        for error in sorted(
            validator.iter_errors(document),
            key=lambda item: list(item.absolute_path),
        )
    ]


def pointer_parent(document: Any, pointer: str) -> tuple[Any, str]:
    parts = [
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer.split("/")[1:]
    ]
    target = document
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    return target, parts[-1]


def apply_mutations(
    document: dict[str, Any],
    mutations: list[dict[str, Any]],
) -> dict[str, Any]:
    result = copy.deepcopy(document)
    for mutation in mutations:
        parent, key = pointer_parent(result, mutation["path"])
        index: int | str = int(key) if isinstance(parent, list) and key != "-" else key
        if mutation["op"] == "replace":
            parent[index] = mutation["value"]
        elif mutation["op"] == "remove":
            del parent[index]
        elif mutation["op"] == "add":
            if isinstance(parent, list):
                if index == "-":
                    parent.append(mutation["value"])
                else:
                    parent.insert(int(index), mutation["value"])
            else:
                parent[index] = mutation["value"]
        else:
            raise ValueError(f"unsupported fixture mutation: {mutation['op']}")
    return result
