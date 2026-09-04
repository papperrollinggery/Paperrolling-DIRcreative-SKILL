from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_compact_state_migrate as migrate  # noqa: E402


class CompactStateMigrationTests(unittest.TestCase):
    def legacy(self, authorized: bool) -> dict:
        return {
            "project_id": "legacy-project",
            "mode": "delivery",
            "current_route": "generation_authorization",
            "locked_facts": [],
            "working_assumptions": [],
            "active_outputs": [],
            "stale_outputs": [],
            "open_questions": [],
            "generation_authorized": authorized,
            "client_delivery_approved": False,
        }

    def test_false_legacy_authorization_migrates_to_planning_only(self):
        result = migrate.migrate_v20(self.legacy(False))
        self.assertEqual(result["media_scope"], "planning_only")
        self.assertFalse(result["image_generation_authorized"])
        self.assertFalse(result["video_generation_authorized"])
        schema = json.loads(
            (ROOT / "skills/dircreative/runtime/state-snapshot.schema.json").read_text()
        )
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(result)), [])

    def test_true_legacy_authorization_fails_closed_to_scope_conflict(self):
        result = migrate.migrate_v20(self.legacy(True))
        self.assertEqual(result["media_scope"], "scope_conflict")
        self.assertFalse(result["image_generation_authorized"])
        self.assertFalse(result["video_generation_authorized"])
        self.assertIn("media scope", " ".join(result["open_questions"]).lower())


if __name__ == "__main__":
    unittest.main()
