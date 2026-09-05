from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_prompt_compiler as compiler


class AssetPromptSurfaceTests(unittest.TestCase):
    def test_film_asset_prompts_keep_truth_in_packet_not_model_text(self):
        plan = {"project_id": "private-project-817", "scope": "whole_film", "delivery_profile": {"aspect_ratio": "16:9"}}
        for role in compiler.ASSET_ROLE_LABELS:
            asset = {"asset_id": "ASSET-PRIVATE-817", "truth_sha256": "c" * 64, "role": role, "purpose": "A red enamel rain bell suspended from a bare timber beam."}
            original = copy.deepcopy(asset)
            with self.subTest(role=role):
                prompt = compiler.build_asset_role_prompt(asset, plan)
                for internal in (asset["asset_id"], asset["truth_sha256"], plan["project_id"]):
                    self.assertNotIn(internal, prompt)
                self.assertIn(asset["purpose"], prompt)
                self.assertIn(compiler.ASSET_ROLE_LABELS[role], prompt)
                self.assertIn("16:9", prompt)
                self.assertEqual(asset, original)

    def test_character_derivatives_reference_actual_attachment_not_hash_text(self):
        for mode in ("headed_state", "headless_safe"):
            contract = {"mode": mode, "approved_source_master_sha256": "d" * 64, "state_facts": ["rain-soaked fabric"]}
            with self.subTest(mode=mode):
                prompt = compiler.build_character_prompt_from_contract("Same adult actor in a red raincoat.", contract)
                self.assertNotIn("d" * 64, prompt)
                self.assertIn("attached", prompt)
                self.assertIn("left", prompt)
                self.assertIn("right", prompt)
                self.assertEqual(contract["approved_source_master_sha256"], "d" * 64)

    def test_standalone_product_study_retains_no_title_behavior(self):
        asset = {"role": "product_identity_board", "purpose": "A white ceramic cup with a square handle."}
        prompt = compiler.build_asset_role_prompt(asset, {"scope": "asset_only", "delivery_profile": {"aspect_ratio": "1:1"}})
        self.assertIn("1:1", prompt)
        self.assertNotIn("Largest title", prompt)


if __name__ == "__main__":
    unittest.main()
