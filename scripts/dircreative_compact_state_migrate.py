#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dircreative_validation_common import schema_errors


MAX_STATE_BYTES = 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
STATE_SCHEMA = ROOT / "skills/dircreative/runtime/state-snapshot.schema.json"
LEGACY_FIELDS = {
    "project_id",
    "mode",
    "current_route",
    "locked_facts",
    "working_assumptions",
    "active_outputs",
    "stale_outputs",
    "open_questions",
    "generation_authorized",
    "client_delivery_approved",
}


def migrate_v20(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict) or set(state) != LEGACY_FIELDS:
        raise ValueError("legacy_compact_state_shape_invalid")
    legacy_authorized = state.get("generation_authorized")
    if not isinstance(legacy_authorized, bool):
        raise ValueError("legacy_generation_authorized_invalid")
    if not isinstance(state.get("project_id"), str) or not state["project_id"]:
        raise ValueError("legacy_project_id_invalid")
    if state.get("mode") not in {"fast", "studio", "delivery"}:
        raise ValueError("legacy_mode_invalid")
    if not isinstance(state.get("current_route"), str) or not state["current_route"]:
        raise ValueError("legacy_route_invalid")
    for field in (
        "locked_facts",
        "working_assumptions",
        "active_outputs",
        "stale_outputs",
        "open_questions",
    ):
        if not isinstance(state.get(field), list) or not all(
            isinstance(item, str) for item in state[field]
        ):
            raise ValueError(f"legacy_{field}_invalid")
    if not isinstance(state.get("client_delivery_approved"), bool):
        raise ValueError("legacy_client_delivery_approved_invalid")
    open_questions = list(state.get("open_questions", []))
    if legacy_authorized:
        open_questions.append(
            "Legacy generation authorization had no media scope; reconfirm image versus final-video authorization."
        )
    migrated = {
        "project_id": state["project_id"],
        "mode": state["mode"],
        "current_route": state["current_route"],
        "media_scope": "scope_conflict" if legacy_authorized else "planning_only",
        "image_generation_authorized": False,
        "video_generation_authorized": False,
        "active_stage": None,
        "active_asset_id": None,
        "active_asset_role": None,
        "stage_contract_reference": None,
        "stage_contract_sha256": None,
        "asset_execution_gate_status": "not_required",
        "locked_facts": list(state.get("locked_facts", [])),
        "working_assumptions": list(state.get("working_assumptions", [])),
        "active_outputs": list(state.get("active_outputs", [])),
        "stale_outputs": list(state.get("stale_outputs", [])),
        "open_questions": open_questions,
        "client_delivery_approved": state["client_delivery_approved"],
    }
    failures = schema_errors(migrated, STATE_SCHEMA)
    if failures:
        raise ValueError("migrated_compact_state_invalid:" + failures[0])
    return migrated


def write_new_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a DIRcreative compact state 2.0 snapshot to scoped media state 2.1.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.source.stat().st_size > MAX_STATE_BYTES:
            raise ValueError("legacy_compact_state_too_large")
        source = json.loads(args.source.read_text(encoding="utf-8"))
        if args.source.resolve() == args.output.resolve(strict=False):
            raise ValueError("migration_output_must_not_replace_source")
        migrated = migrate_v20(source)
        write_new_output(args.output, migrated)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "PASS", "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
