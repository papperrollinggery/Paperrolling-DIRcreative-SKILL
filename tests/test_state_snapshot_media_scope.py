from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))

from dircreative_state_audit import _builtin_schema_errors


class StateSnapshotMediaScopeTests(unittest.TestCase):
    def schema(self) -> dict:
        path = ROOT / "skills/dircreative/runtime/state-snapshot.schema.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def snapshot(self) -> dict:
        return {
            "project_id": "state-test",
            "mode": "delivery",
            "current_route": "generation_authorization",
            "media_scope": "pre_video_assets",
            "image_generation_authorized": True,
            "video_generation_authorized": False,
            "active_stage": "identity_state",
            "active_asset_id": "ID-CH01",
            "active_asset_role": "character_identity_reference",
            "stage_contract_reference": "skills/dircreative/references/character-master-sheet.md",
            "stage_contract_sha256": "a" * 64,
            "asset_execution_gate_status": "pass",
            "locked_facts": [],
            "working_assumptions": [],
            "active_outputs": [],
            "stale_outputs": [],
            "open_questions": [],
            "client_delivery_approved": False,
        }

    def test_state_requires_scoped_media_and_active_asset_contract(self):
        required = set(self.schema()["required"])
        for field in (
            "media_scope",
            "image_generation_authorized",
            "video_generation_authorized",
            "active_stage",
            "active_asset_id",
            "active_asset_role",
            "stage_contract_reference",
            "stage_contract_sha256",
            "asset_execution_gate_status",
        ):
            self.assertIn(field, required)
        self.assertNotIn("generation_authorized", required)

    def test_pre_video_scope_cannot_authorize_video(self):
        snapshot = self.snapshot()
        snapshot["video_generation_authorized"] = True
        schema = self.schema()
        errors = _builtin_schema_errors(snapshot, schema, schema, "$")
        self.assertTrue(errors)

    def test_valid_scoped_state_passes_schema(self):
        schema = self.schema()
        errors = _builtin_schema_errors(self.snapshot(), schema, schema, "$")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
