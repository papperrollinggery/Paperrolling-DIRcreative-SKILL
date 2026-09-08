from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_prompt_compiler as compiler  # noqa: E402


class ProductCgVideoExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "examples/product-cg-style-library/prompt-ir.json"
        self.payload = json.loads(self.path.read_text(encoding="utf-8"))

    def test_real_prompt_ir_validates_and_compiles_as_prompt_only(self) -> None:
        compiler.validate_prompt_ir(self.payload, verify_project_files=False)
        result = compiler.compile_prompt(self.payload, verify_project_files=False)
        self.assertEqual(result.adapter, "seedance")
        self.assertEqual(self.payload["output"]["visual_output_mode"], "prompt_only")
        self.assertEqual(result.prompt.count("Style:"), 1)
        self.assertIn("photoreal CG product film", result.prompt)
        self.assertIn("powder core stays complete; fine powder expands once and falls back", result.prompt)
        self.assertEqual(len(result.unit_prompts), 1)
        self.assertEqual(result.unit_prompts[0].count("Style:"), 1)
        rendered = (ROOT / "examples/product-cg-style-library/video-prompt.txt").read_text(encoding="utf-8").rstrip("\n")
        self.assertEqual(rendered, result.prompt)

    def test_four_shots_form_a_continuous_nine_second_progression(self) -> None:
        shots = self.payload["shot_blocks"]
        self.assertEqual([shot["shot_id"] for shot in shots], ["S01", "S02", "S03", "S04"])
        self.assertEqual(
            [(shot["time_start"], shot["time_end"]) for shot in shots],
            [("00.00", "01.80"), ("01.80", "04.60"), ("04.60", "07.00"), ("07.00", "09.00")],
        )
        self.assertEqual(self.payload["output"]["target_duration_sec"], 9)
        self.assertEqual(self.payload["generation_plan"]["units"][0]["time_end"], "09.00")
        for shot in shots:
            self.assertTrue(shot["entity_actions"])
            self.assertTrue(shot["transition_in"])
            self.assertTrue(shot["transition_out"])
            self.assertTrue(shot["continuity_locks"])
        self.assertTrue(any("contact" in shot["story_beat"] for shot in shots))
        self.assertTrue(any("spread" in shot["story_beat"] or "scatter" in shot["story_beat"] for shot in shots))
        self.assertTrue(any("hero" in shot["story_beat"] for shot in shots))

    def test_graphic_contrast_keeps_declared_medium_without_forcing_photoreal(self) -> None:
        graphic = copy.deepcopy(self.payload)
        graphic["project"]["intended_use"] = "9-second flat graphic vector product film"
        graphic["video_quality"]["style"] = "flat graphic vector product film; no photoreal surface claim"
        compiler.validate_prompt_ir(graphic, verify_project_files=False)
        result = compiler.compile_prompt(graphic, verify_project_files=False)
        self.assertIn("flat graphic vector product film", result.prompt.splitlines()[0])
        self.assertNotIn("8K IMAX photoreal cinema", result.prompt)

    def test_precision_drive_contrast_has_no_powder_or_scatter_and_keeps_camera_in_camera(self) -> None:
        path = ROOT / "examples/product-cg-style-library/precision-prompt-ir.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        compiler.validate_prompt_ir(payload, verify_project_files=False)
        result = compiler.compile_prompt(payload, verify_project_files=False)
        lowered = result.prompt.lower()
        self.assertNotIn("powder", lowered)
        self.assertNotIn("scatter", lowered)
        self.assertIn("usb-c port", lowered)
        self.assertTrue(all("camera" in shot and "camera" not in json.dumps(shot["environment_action"]).lower() for shot in payload["shot_blocks"]))
        rendered = (ROOT / "examples/product-cg-style-library/precision-video-prompt.txt").read_text(encoding="utf-8").rstrip("\n")
        self.assertEqual(rendered, result.prompt)


if __name__ == "__main__":
    unittest.main()
