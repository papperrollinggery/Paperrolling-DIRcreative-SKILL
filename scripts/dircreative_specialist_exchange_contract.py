#!/usr/bin/env python3
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dircreative_state_audit import _builtin_schema_errors


ROOT = Path(__file__).resolve().parents[1]
V2_HANDOFF_SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/adco-specialist-handoff-v2.schema.json"
V2_RECEIPT_SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/adco-specialist-receipt-v2.schema.json"


@lru_cache(maxsize=1)
def v2_handoff_schema() -> dict[str, Any]:
    schema = json.loads(V2_HANDOFF_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("ADCO v2 handoff schema must be an object")
    return schema


@lru_cache(maxsize=1)
def v2_receipt_schema() -> dict[str, Any]:
    schema = json.loads(V2_RECEIPT_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("ADCO v2 receipt schema must be an object")
    return schema


def v2_handoff_schema_errors(handoff: object) -> list[str]:
    schema = v2_handoff_schema()
    errors = _builtin_schema_errors(handoff, schema, schema, "$")
    if not isinstance(handoff, dict):
        return errors
    for field, identity_key in (
        ("locked_decisions", "artifact_id"),
        ("requested_outputs", "output_id"),
    ):
        values = handoff.get(field)
        if not isinstance(values, list):
            continue
        identities = [
            str(item.get(identity_key, ""))
            for item in values
            if isinstance(item, dict) and item.get(identity_key)
        ]
        if len(identities) != len(set(identities)):
            errors.append(f"$.{field} {identity_key} values must be unique")
    requested = handoff.get("requested_outputs")
    if isinstance(requested, list):
        output_types = [
            str(item.get("type", ""))
            for item in requested
            if isinstance(item, dict) and item.get("type")
        ]
        if len(output_types) != len(set(output_types)):
            errors.append("$.requested_outputs type values must be unique")
    return errors


def v2_receipt_schema_errors(receipt: object) -> list[str]:
    schema = v2_receipt_schema()
    return _builtin_schema_errors(receipt, schema, schema, "$")


def valid_v2_handoff(handoff: object) -> bool:
    return not v2_handoff_schema_errors(handoff)
