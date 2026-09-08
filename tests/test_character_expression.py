from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_prompt_compiler as compiler  # noqa: E402


class CharacterExpressionPromptTests(unittest.TestCase):
    def test_declared_adult_body_and_garment_facts_survive_master_compilation(self):
        contract = {
            "identity_facts": ["adult woman with pale-blue irises", "relaxed shoulders, defined waist, natural hip and leg proportions"],
            "wardrobe_facts": ["crimson fitted bodice with a vertical V opening to the navel", "solid shaped chest panels", "long skirt panels", "high boots", "single shoulder pauldron"],
            "wardrobe_materials": ["light-transmitting gauze sleeves", "opaque crimson bodice panels"],
            "side_specific_details": ["narrow stand collar only at the rear neck sides"],
        }
        prompt = compiler.build_character_master_prompt_from_contract("approved adult crimson ceremonial look", contract)
        for fact in (*contract["identity_facts"], *contract["wardrobe_facts"], *contract["wardrobe_materials"], *contract["side_specific_details"]):
            self.assertIn(fact, prompt)
        self.assertIn("natural, stable garment-display stance", prompt)
        self.assertIn("four full-body headed views", prompt)

    def test_explicit_pose_lock_wins_over_natural_default(self):
        contract = {"identity_facts": [], "wardrobe_facts": [], "wardrobe_materials": [],
                    "side_specific_details": ["strict 30-degree A-pose with straight elbows"]}
        prompt = compiler.build_character_master_prompt_from_contract("adult character", contract)
        self.assertIn("Pose lock: strict 30-degree A-pose with straight elbows", prompt)
        self.assertNotIn("natural, stable garment-display stance", prompt)

    def test_explicit_chinese_stance_lock_wins_over_natural_default(self):
        contract = {"identity_facts": [], "wardrobe_facts": [], "wardrobe_materials": [],
                    "side_specific_details": ["站姿锁定：右脚前、左手自然垂放"]}
        prompt = compiler.build_character_master_prompt_from_contract("adult character", contract)
        self.assertIn("Pose lock: 站姿锁定：右脚前、左手自然垂放", prompt)
        self.assertNotIn("natural, stable garment-display stance", prompt)

    def test_plain_character_does_not_gain_unrequested_exposure_or_body_template(self):
        contract = {"identity_facts": ["adult archivist"], "wardrobe_facts": ["gray wool coat"],
                    "wardrobe_materials": ["matte wool"], "side_specific_details": []}
        prompt = compiler.build_character_master_prompt_from_contract("approved archivist", contract).lower()
        self.assertNotIn("deep v", prompt)
        self.assertNotIn("navel", prompt)
        self.assertNotIn("sensual", prompt)


if __name__ == "__main__":
    unittest.main()
