#!/usr/bin/env python3
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from dircreative_state_audit import _builtin_schema_errors


ROOT = Path(__file__).resolve().parents[1]
V2_HANDOFF_SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/adco-specialist-handoff-v2.schema.json"


@lru_cache(maxsize=1)
def v2_handoff_schema() -> dict[str, Any]:
    schema = json.loads(V2_HANDOFF_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError("ADCO v2 handoff schema must be an object")
    return schema


def v2_handoff_schema_errors(handoff: object) -> list[str]:
    schema = v2_handoff_schema()
    return _builtin_schema_errors(handoff, schema, schema, "$")


def valid_v2_handoff(handoff: object) -> bool:
    return not v2_handoff_schema_errors(handoff)
