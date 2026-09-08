from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "skills/dircreative/references/product-cg"
EXAMPLES = ROOT / "examples/product-cg-style-library"
RECORD = ROOT / "docs/film-preproduction/research/product-cg-transfer-validation-2026-09-08.json"


class ProductCgLibraryTests(unittest.TestCase):
    def test_catalog_and_capsules_link_two_distinct_target_scenarios(self):
        catalog = json.loads((LIBRARY / "catalog.json").read_text())
        cases = json.loads((EXAMPLES / "cases.json").read_text())["cases"]
        record = json.loads(RECORD.read_text())
        evidence = {item["case_id"]: item for item in record["cases"]}
        ids = [item["id"] for item in catalog["families"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 6)
        self.assertEqual(len(cases), 12)
        self.assertEqual(len(evidence), len(cases))
        for family in catalog["families"]:
            path = (LIBRARY / family["capsule"]).resolve()
            self.assertTrue(path.is_relative_to(LIBRARY.resolve()))
            capsule = json.loads(path.read_text())
            self.assertEqual(capsule["id"], family["id"])
            self.assertEqual(capsule["style_capsule"], "1.0")
            self.assertEqual(capsule["status"], "validated")
            self.assertIs(capsule["adoption_approved"], False)
            self.assertIs(capsule["source_summary"]["raw_images_stored"], False)
            tests = [item for item in cases if item["family"] == family["id"]]
            self.assertEqual(len(tests), 2)
            self.assertEqual(len({item["scenario"] for item in tests}), 2)
            self.assertEqual(len(capsule["validation"]["prompts"]), 2)
            self.assertEqual({x["case_id"] for x in capsule["validation"]["evidence"]}, {x["case_id"] for x in tests})
            for item in tests:
                spec = json.loads((EXAMPLES / item["spec"]).read_text())
                self.assertEqual(spec["inputs"], [])
                self.assertEqual(evidence[item["case_id"]]["reference_images_in_native_call"], 0)
                self.assertEqual(evidence[item["case_id"]]["scenario"], item["scenario"])

    def test_evidence_keeps_failures_and_does_not_claim_full_output_or_video_acceptance(self):
        record = json.loads(RECORD.read_text())
        self.assertEqual({x["case_id"] for x in record["initial_failures"]}, {"powder-compact", "artist-pigment"})
        for item in record["cases"]:
            self.assertRegex(item["image"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(item["prompt"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(item["temporal_verification"], "not_run")
            self.assertEqual(item["spec_canvas_intent"], {"width": 1920, "height": 1080})
            self.assertEqual((item["image"]["width"], item["image"]["height"]), (1672, 941))
            self.assertIs(item["native_size_argument_sent"], False)
            self.assertTrue(item["technical_conformance"].startswith("partial:"))
            for path in (item["image"]["relative_path"], item["prompt"]["relative_path"]):
                self.assertFalse(Path(path).is_absolute())
                self.assertNotIn("..", Path(path).parts)
        powder = next(x for x in record["cases"] if x["case_id"] == "powder-compact")
        self.assertIn("crop", powder["technical_conformance"])

    def test_public_capsules_are_source_image_free_and_not_management_prompts(self):
        for path in LIBRARY.rglob("*.json"):
            text = path.read_text()
            self.assertNotRegex(text, r"/Users/|/home/|codex://threads/|data:image/")
            if path.parent.name == "capsules":
                capsule = json.loads(text)
                rendered_rules = json.dumps(capsule["visual_rules"], ensure_ascii=False)
                self.assertNotIn("companion direction guide", rendered_rules)
                self.assertTrue(capsule["transfer_rules"])
                self.assertTrue(capsule["forbidden_transfer"])
        self.assertFalse(list(LIBRARY.rglob("*.png")))


if __name__ == "__main__":
    unittest.main()
