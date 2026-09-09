from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_visual_asset_plan as visual_plan  # noqa: E402


PLAN_PATH = ROOT / "tests/fixtures/asset-execution/character-plan.json"


class FoundationFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))

    def test_lists_only_root_foundations_without_claiming_generation_or_qa(self) -> None:
        errors, _metrics = visual_plan.validate_plan(self.plan, base_dir=PLAN_PATH.parent)
        self.assertEqual(errors, [])

        frontier = visual_plan.foundation_frontier(self.plan)
        candidates = frontier["foundation_candidates"]
        candidate_ids = {item["asset_id"] for item in candidates}

        self.assertEqual(candidate_ids, {
            "identity-character-protagonist-protagonist-office-look",
            "identity-product-coldbrew-bottle",
            "continuity-prop-ice-cup-state",
            "scene-office-desk",
        })
        for item in candidates:
            self.assertEqual(item["preparation_state"], "design_inputs_required")
            self.assertEqual(item["dependency_blockers"], [])
            self.assertFalse(item["generated"])
            self.assertFalse(item["visual_qa_approved"])
            self.assertIn("--explain-inputs", item["next_command"])

        blocked = frontier["foundation_assets_blocked_by_dependencies"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["asset_id"], "look-whole-film")
        self.assertEqual(blocked[0]["dependency_blockers"], ["scene-office-desk"])

    def test_cli_validates_before_reporting_frontier(self) -> None:
        proc = subprocess.run(
            [sys.executable, "scripts/dircreative_visual_asset_plan.py", "--plan", str(PLAN_PATH), "--foundation-frontier"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.JSONDecoder().raw_decode(proc.stdout)[0]
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(
            report["foundation_frontier"]["foundation_candidates"][0]["preparation_state"],
            "design_inputs_required",
        )

