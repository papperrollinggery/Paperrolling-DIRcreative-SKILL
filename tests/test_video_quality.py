from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dircreative_video_quality import build_video_quality_prefix, wrap_video_prompt  # noqa: E402


class VideoQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads((ROOT / "examples/seedance-mirror-turn-10s/prompt-ir.json").read_text())
        self.unit = self.payload["generation_plan"]["units"][0]

    def test_real_prompt_ir_has_one_ordered_twelve_part_prefix_and_keeps_sources(self):
        text = build_video_quality_prefix(self.payload, self.unit)
        labels = [line.split(":", 1)[0] for line in text.splitlines()]
        self.assertEqual(labels, ["Style", "Cinematography", "Lighting", "Color", "Camera", "Skin", "Acting", "Physics", "Composition", "Continuity", "Technical", "Audio"])
        self.assertEqual(text.count("Style:"), 1)
        self.assertIn("deep-burgundy edge source", text)
        self.assertIn("Sparse haze", text)
        self.assertIn("spherical", text)
        self.assertIn("black satin detail", text)
        self.assertIn("sound is supplied separately", text)

    def test_postproduction_audio_does_not_claim_native_dialogue_or_music(self):
        item = copy.deepcopy(self.payload)
        item["audio_plan"].update(dialogue="spoken line", music="authorized score")
        audio = next(line for line in build_video_quality_prefix(item, self.unit).splitlines() if line.startswith("Audio:"))
        self.assertIn("sound is supplied separately", audio)
        self.assertNotIn("spoken line", audio)
        self.assertNotIn("authorized score", audio)

    def test_native_audio_keeps_dialogue_music_and_exact_text_does_not_gain_no_subtitles(self):
        item = copy.deepcopy(self.payload)
        item["audio_plan"].update(generation_route="native", dialogue="Mira: stay close", music="authorized score")
        item["output"]["text_policy"] = "exact_text"
        audio = next(line for line in build_video_quality_prefix(item, self.unit).splitlines() if line.startswith("Audio:"))
        self.assertIn("Mira: stay close", audio)
        self.assertIn("authorized score", audio)
        self.assertNotIn("no subtitles", audio)

    def test_explicit_style_night_override_and_no_haze_remain_authoritative(self):
        item = copy.deepcopy(self.payload)
        item["render_look"]["atmosphere"] = {"intensity": "none"}
        item["render_look"]["exit_or_continuity"] = "grade stays continuous through the final clean hold"
        item["video_quality"] = {"style": "stylized cel animation", "lighting": "night firelight only"}
        text = build_video_quality_prefix(item, self.unit)
        self.assertIn("Style: stylized cel animation.", text)
        self.assertIn("Lighting: night firelight only.", text)
        self.assertNotIn("haze", text.lower())
        self.assertNotIn("sky", text.lower())

    def test_wrap_removes_only_top_level_look_and_continuity(self):
        prompt = "References:\nref.\n\nContinuity:\nold locks.\n\nTimeline:\nCamera: remains here. Audio: remains here. Look change: remains here.\n\nLook:\nold look."
        wrapped = wrap_video_prompt(self.payload, prompt, self.unit)
        self.assertEqual(wrapped.count("Continuity:"), 1)
        self.assertEqual(wrapped.count("Lighting:"), 1)
        self.assertIn("Camera: remains here", wrapped)
        self.assertIn("Audio: remains here", wrapped)
        self.assertIn("Look change: remains here", wrapped)
        self.assertNotIn("old locks", wrapped)
        self.assertNotIn("old look", wrapped)

    def test_real_compiler_prefixes_once_and_keeps_optional_override_out_of_image_prompts(self):
        import dircreative_prompt_compiler as compiler
        item = copy.deepcopy(self.payload)
        item["video_quality"] = {"style": "photographic film costume scene", "lighting": "window backlight&#x20;with readable shadows", "audio": "environmental foley without music"}
        result = compiler.compile_prompt(item, verify_project_files=False)
        for prompt in (result.prompt, *result.unit_prompts):
            self.assertTrue(prompt.startswith("Style: photographic film costume scene."))
            self.assertEqual(prompt.count("\nLighting:"), 1)
            self.assertEqual(prompt.count("\nContinuity:"), 1)
            self.assertLess(prompt.index("Audio:"), prompt.index("Timeline:"))
            self.assertNotIn("&#x20;", prompt)
        self.assertIn("environmental foley without music", result.postproduction_audio)
        self.assertEqual(item["generation_plan"], self.payload["generation_plan"])

    def test_existing_animation_intent_without_new_override_is_not_forced_photoreal(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "10-second stop-motion clay animation"
        text = build_video_quality_prefix(item)
        self.assertIn("stop-motion clay animation", text.splitlines()[0])
        self.assertNotIn("photoreal cinema", text)
        self.assertNotIn("visible pores", text)
        self.assertNotIn("24 fps", text)

    def test_product_cg_medium_is_preserved_and_does_not_inject_live_action_or_performer_language(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "10-second photoreal_cg product material macro"
        item["entities"] = [{"entity_type": "product"}]
        text = build_video_quality_prefix(item)
        self.assertIn("photoreal_cg", text.splitlines()[0])
        self.assertNotIn("not 3D", text)
        self.assertNotIn("camera shares physical space with performers", text)
        self.assertIn("declared subject and material", text)

    def test_negative_cg_language_does_not_count_as_positive_medium(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "10-second product film; do not use CG or 3D"
        text = build_video_quality_prefix(item)
        self.assertIn("Style: 10-second product film; do not use CG or 3D; preserve this declared visual treatment", text)
        self.assertNotIn("8K IMAX photoreal cinema", text)

    def test_chinese_product_cg_medium_is_positive_but_chinese_negation_is_not(self):
        positive = copy.deepcopy(self.payload)
        positive["project"]["intended_use"] = "10秒产品CG广告"
        positive_text = build_video_quality_prefix(positive)
        self.assertIn("产品CG广告", positive_text.splitlines()[0])
        self.assertNotIn("not 3D", positive_text)

        negative = copy.deepcopy(self.payload)
        negative["project"]["intended_use"] = "10秒产品广告，不要产品CG"
        negative_text = build_video_quality_prefix(negative)
        self.assertIn("Style: 10秒产品广告，不要产品CG; preserve this declared visual treatment", negative_text)
        self.assertNotIn("8K IMAX photoreal cinema", negative_text)

    def test_excluding_3d_preserves_the_declared_flat_vector_statement(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "flat vector product film, no 3D"
        text = build_video_quality_prefix(item)
        self.assertIn("Style: flat vector product film, no 3D; preserve this declared visual treatment", text)
        self.assertNotIn("8K IMAX photoreal cinema", text)

    def test_human_scene_keeps_live_action_performer_default(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "10-second live-action product film"
        item["entities"] = [{"entity_type": "person"}]
        text = build_video_quality_prefix(item)
        self.assertIn("camera shares physical space with performers", text)

    def test_stylized_cg_override_keeps_explicit_style_and_medium_safe_defaults(self):
        item = copy.deepcopy(self.payload)
        item["video_quality"] = {"style": "stylized_cg product commercial"}
        item["entities"] = [{"entity_type": "product"}]
        text = build_video_quality_prefix(item)
        self.assertIn("Style: stylized_cg product commercial.", text)
        self.assertNotIn("not 3D", text)
        self.assertNotIn("camera shares physical space with performers", text)

    def test_gpt_image_adapter_never_receives_video_quality_prefix(self):
        from unittest import mock
        import dircreative_prompt_compiler as compiler
        item = copy.deepcopy(self.payload)
        item["generation_plan"]["selected_adapter"] = "gpt_image"
        # Isolate compiler dispatch from the fixture's video-only model card.
        # The unmodified image adapter still performs its own surface checks.
        with mock.patch.object(compiler, "validate_prompt_ir"):
            result = compiler.compile_prompt(item, verify_project_files=False)
        self.assertFalse(result.prompt.startswith("Style:"))
        self.assertNotIn("Technical:", result.prompt)
        self.assertNotIn("24 fps", result.prompt)


if __name__ == "__main__":
    unittest.main()
