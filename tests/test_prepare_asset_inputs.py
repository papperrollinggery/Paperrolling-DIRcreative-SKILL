from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_prepare_asset as prepare_asset  # noqa: E402


PLAN = "tests/fixtures/asset-execution/character-plan.json"
CHARACTER_ID = "identity-character-protagonist-protagonist-office-look"
PRODUCT_ID = "identity-product-coldbrew-bottle"


class PrepareAssetInputExplanationTests(unittest.TestCase):
    def test_character_explanation_uses_existing_stage_shape_without_execution(self) -> None:
        result = prepare_asset.explain_inputs(
            project_root=ROOT,
            plan_path=PLAN,
            asset_id=CHARACTER_ID,
        )

        self.assertEqual(result["status"], "input_requirements")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["provider_executed"])
        self.assertEqual(result["files_written"], [])
        self.assertEqual(result["stage"]["stage_id"], "identity_state")
        self.assertEqual(
            result["stage"]["design_artifact"]["payload_required_fields"],
            ["asset_descriptors", "state_families"],
        )
        self.assertTrue(result["character_contract"]["required"])
        shape = result["character_contract"]["editable_shape"]
        from dircreative_asset_execution_gate import character_master_contract_errors
        shape.update(identity_facts=["adult woman"], wardrobe_facts=["work jacket"], wardrobe_materials=["woven cloth"])
        self.assertEqual(character_master_contract_errors(shape), [])
        source = result["source_spec"]["editable_shape"]
        self.assertEqual(source["visual_generation_spec"], "1.0")
        self.assertNotEqual(source["canvas"]["aspect_ratio"], "auto")
        self.assertEqual(result["stage"]["design_artifact"]["editable_shape"]["payload"]["asset_descriptors"], [CHARACTER_ID])
        self.assertIn("--design-artifact", result["next_commands"]["prepare_with_authored_design"])

    def test_noncharacter_explanation_does_not_require_character_contract(self) -> None:
        result = prepare_asset.explain_inputs(
            project_root=ROOT,
            plan_path=PLAN,
            asset_id=PRODUCT_ID,
        )
        self.assertFalse(result["character_contract"]["required"])
        self.assertNotIn("--character-contract", result["next_commands"]["prepare_with_authored_design"])
        self.assertEqual(result["source_spec"]["required_values"]["mode"], "create")

    def test_cli_only_needs_project_plan_and_asset(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "scripts/dircreative_prepare_asset.py",
                "--project-root", str(ROOT),
                "--plan", PLAN,
                "--asset-id", CHARACTER_ID,
                "--explain-inputs",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["files_written"], [])
