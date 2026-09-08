from __future__ import annotations

import copy
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dircreative_video_quality import build_video_quality_prefix, wrap_video_prompt  # noqa: E402
from dircreative_adapters import get_adapter  # noqa: E402
from dircreative_adapters.base import AdapterContractError  # noqa: E402
from dircreative_package_layout import sanitize_package_bytes  # noqa: E402


class VideoQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads((ROOT / "examples/seedance-mirror-turn-10s/prompt-ir.json").read_text())
        self.unit = self.payload["generation_plan"]["units"][0]

    def test_release_sanitization_keeps_all_host_path_guards_effective(self):
        relative = "scripts/dircreative_adapters/base.py"
        packaged = sanitize_package_bytes(relative, (ROOT / relative).read_bytes(), {})
        module = types.ModuleType("_dircreative_packaged_path_guard_test")
        with patch.dict(sys.modules, {module.__name__: module}):
            exec(compile(packaged, relative, "exec"), module.__dict__)
            for prefix in ("Users", "home", "private"):
                with self.subTest(prefix=prefix):
                    host_path = "/".join(("", prefix, "example", "frame.png"))
                    errors = module.shared_surface_errors("continue from " + host_path, set())
                    self.assertTrue(any(item.startswith("local_path:") for item in errors))
            self.assertEqual(module.shared_surface_errors("Follow the cup as it rolls.", set()), [])

    def test_real_prompt_ir_keeps_only_ordered_source_directions(self):
        text = build_video_quality_prefix(self.payload, self.unit)
        labels = [line.split(":", 1)[0] for line in text.splitlines()]
        self.assertEqual(labels, ["Lighting", "Color", "Camera", "Composition", "Continuity", "Audio"])
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
        self.assertNotIn("declared subject and material", text)

    def test_negative_cg_language_does_not_count_as_positive_medium(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "10-second product film; do not use CG or 3D"
        text = build_video_quality_prefix(item)
        self.assertIn("Style: 10-second product film; do not use CG or 3D.", text)
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
        self.assertIn("Style: 10秒产品广告，不要产品CG.", negative_text)
        self.assertNotIn("8K IMAX photoreal cinema", negative_text)

    def test_excluding_3d_preserves_the_declared_flat_vector_statement(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "flat vector product film, no 3D"
        text = build_video_quality_prefix(item)
        self.assertIn("Style: flat vector product film, no 3D.", text)
        self.assertNotIn("8K IMAX photoreal cinema", text)

    def test_human_scene_does_not_receive_an_unrequested_performer_default(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "10-second live-action product film"
        item["entities"] = [{"entity_type": "person"}]
        text = build_video_quality_prefix(item)
        self.assertNotIn("camera shares physical space with performers", text)

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

    def test_unmanned_2d_typography_only_uses_declared_directions(self):
        item = copy.deepcopy(self.payload)
        item["project"]["intended_use"] = "8-second flat 2D kinetic typography title card"
        item["entities"] = []
        item["render_look"] = {
            "lighting": {"intensity": "none"},
            "optics": {"intensity": "none"},
            "atmosphere": {"intensity": "none"},
            "grade": {"intensity": "none"},
            "preserve": [],
            "exit_or_continuity": "none",
        }
        item["global_locks"] = {key: [] for key in item["global_locks"]}
        item["composition"] = {}
        text = build_video_quality_prefix(item)
        self.assertEqual(text.splitlines(), ["Style: 8-second flat 2D kinetic typography title card.", "Audio: silent picture; sound is supplied separately."])
        self.assertNotRegex(text.lower(), r"skin|pore|haze|3d|24 fps|pause|stillness|180-degree|golden")

    def test_explicit_complete_quality_override_stays_ordered_without_defaults(self):
        item = copy.deepcopy(self.payload)
        item["audio_plan"]["generation_route"] = "native"
        item["video_quality"] = {
            key: f"declared {key} direction" for _, key in (
                ("Style", "style"), ("Cinematography", "cinematography"),
                ("Lighting", "lighting"), ("Color", "color"), ("Camera", "camera"),
                ("Skin", "skin"), ("Acting", "acting"), ("Physics", "physics"),
                ("Composition", "composition"), ("Continuity", "continuity"),
                ("Technical", "technical"), ("Audio", "audio"),
            )
        }
        text = build_video_quality_prefix(item)
        self.assertEqual([line.split(":", 1)[0] for line in text.splitlines()], [label for label, _ in (
            ("Style", "style"), ("Cinematography", "cinematography"), ("Lighting", "lighting"),
            ("Color", "color"), ("Camera", "camera"), ("Skin", "skin"), ("Acting", "acting"),
            ("Physics", "physics"), ("Composition", "composition"), ("Continuity", "continuity"),
            ("Technical", "technical"), ("Audio", "audio"),
        )])
        self.assertIn("Technical: declared technical direction.", text)

    def test_adapter_surfaces_shot_handoffs_and_native_transition_audio_without_internal_ids(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        payload["audio_plan"]["generation_route"] = "native"
        adapter = get_adapter("seedance")
        full = adapter.compile_full(payload)
        journey = adapter.compile_unit(payload, payload["generation_plan"]["units"][1])
        self.assertIn("Enter via match wheel rotation from the previous unit", full)
        self.assertIn("Exit via foreground pole occludes the frame", full)
        self.assertIn("Preserve shot continuity: identity; bike; bag; direction; light progression", full)
        self.assertIn("Audio bridge: freewheel continues", full)
        self.assertIn("Audio bridge: tire texture continues then fades", full)
        self.assertIn("00.00-10.00:", journey)
        self.assertIn("Enter via match wheel rotation from the previous unit", journey)
        self.assertNotIn("prepare and depart", journey)
        self.assertNotIn("arrival and payoff", journey)
        self.assertNotRegex(full + journey, r"\b(?:prepare|journey|arrival)_(?:to|unit)|sha256|/Users/")

    def test_postproduction_transition_audio_stays_out_of_video_prompt(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        adapter = get_adapter("seedance")
        full = adapter.compile_full(payload)
        self.assertNotIn("Audio bridge: freewheel continues", full)
        self.assertIn("freewheel continues", adapter.postproduction_audio(payload))

    def test_wrapper_preserves_authored_fast_tail_and_slow_camera_direction(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        arrival = payload["shot_blocks"][-1]
        arrival["entity_actions"][0]["path"] = "accelerate through the entrance without stopping"
        arrival["entity_actions"][0]["final_state"] = "still moving past the entrance at speed"
        arrival["camera"]["speed_easing"] = "slow deliberate pull-back while the rider accelerates"
        prompt = wrap_video_prompt(payload, get_adapter("seedance").compile_full(payload))
        self.assertIn("accelerate through the entrance without stopping", prompt)
        self.assertIn("End with still moving past the entrance at speed", prompt)
        self.assertIn("slow deliberate pull-back while the rider accelerates", prompt)

    def test_canonical_shot_reference_is_crosswalked_by_time_and_unknown_reference_fails(self):
        payload = copy.deepcopy(self.payload)
        payload["audio_plan"]["generation_route"] = "native"
        payload["shot_blocks"][1]["transition_in"] = "continue the specular bridge from S01"
        prompt = get_adapter("seedance").compile_full(payload)
        self.assertIn("continue the specular bridge from view 1 (00.00-02.50)", prompt)
        self.assertNotIn("S01", prompt)
        payload["shot_blocks"][1]["transition_in"] = "continue the specular bridge from S99"
        with self.assertRaisesRegex(AdapterContractError, "unresolved_prompt_shot_reference"):
            get_adapter("seedance").compile_full(payload)
        # Build a synthetic host path at runtime so release privacy sanitization
        # does not rewrite the negative-test input into a permitted fixture path.
        host_path = "/".join(("", "Users", "example", "approved-frame.png"))
        payload["shot_blocks"][1]["transition_in"] = "continue from " + host_path
        with self.assertRaisesRegex(AdapterContractError, "local_path"):
            get_adapter("seedance").compile_full(payload)
        payload["shot_blocks"][1]["transition_in"] = "continue from " + "a" * 64
        with self.assertRaisesRegex(AdapterContractError, "sha256"):
            get_adapter("seedance").compile_full(payload)

    def test_unit_resolves_transition_endpoints_without_transition_plan_order(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        payload["transition_plan"].reverse()
        payload["generation_plan"]["units"][0]["shot_ids"] = ["prepare", "journey"]
        payload["generation_plan"]["units"][0]["time_end"] = "20.00"
        prompt = get_adapter("seedance").compile_unit(payload, payload["generation_plan"]["units"][0])
        self.assertIn("the first wheel rotation matches into the moving side profile", prompt)
        self.assertNotIn("foreground pole creates an occlusion wipe", prompt)

    def test_unit_rebases_native_audio_times_and_omits_global_starting_state(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        payload["audio_plan"]["generation_route"] = "native"
        payload["shot_blocks"][1]["audio_cues"] = [{
            "time": "11.00", "kind": "sfx", "cue": "one passing bell", "perspective": "street-left",
        }]
        prompt = get_adapter("seedance").compile_unit(payload, payload["generation_plan"]["units"][1])
        self.assertIn("01.00 sfx: one passing bell", prompt)
        self.assertNotIn("11.00 sfx: one passing bell", prompt)
        self.assertNotIn("starts standing beside the bicycle at home", prompt)
        self.assertIn("Begin with rider moving left to right with bag in basket", prompt)

    def test_legacy_transition_boundary_remains_valid_for_full_and_full_range_unit(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        payload["transition_plan"][0]["boundary"] = "wheel_match_bridge"
        adapter = get_adapter("seedance")
        self.assertIn("the first wheel rotation matches", adapter.compile_full(payload))
        unit = payload["generation_plan"]["units"][0]
        unit.update(time_end="30.00", shot_ids=["prepare", "journey", "arrival"])
        self.assertIn("the first wheel rotation matches", adapter.compile_unit(payload, unit))

    def test_partial_unit_omits_opaque_legacy_transition_without_failing(self):
        import dircreative_prompt_compiler as compiler
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        payload["transition_plan"][0]["boundary"] = "wheel_match_bridge"
        result = compiler.compile_prompt(payload, verify_project_files=False)
        self.assertIn("the first wheel rotation matches", result.prompt)
        self.assertNotIn("the first wheel rotation matches", result.unit_prompts[0])

    def test_unit_crosswalks_known_references_to_local_time_or_external_context(self):
        payload = copy.deepcopy(self.payload)
        unit = payload["generation_plan"]["units"][0]
        unit.update(time_start="02.50", time_end="10.00", shot_ids=["S02", "S03"])
        payload["shot_blocks"][2]["transition_in"] = "continue from S02"
        prompt = get_adapter("seedance").compile_unit(payload, unit)
        self.assertIn("continue from view 1 (00.00-03.00)", prompt)
        self.assertIn("external continuity context", prompt)
        self.assertNotIn("view 2 (02.50-05.50)", prompt)
        self.assertNotIn("view 1 (00.00-02.50)", prompt)

    def test_timeline_keeps_each_shot_lens_reason(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        prompt = get_adapter("seedance").compile_full(payload)
        self.assertIn("Lens rationale: moderate compression separates rider from background traffic", prompt)
        self.assertIn("Lens rationale: normal perspective preserves rider and bicycle proportions", prompt)

    def test_native_unit_audio_keeps_authored_global_plan_and_current_shot_cues(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        payload["audio_plan"].update(
            generation_route="native",
            dialogue="Start moving. Keep going.",
            ambience="shared dawn traffic ambience",
            music="shared pulse score",
            foley="all-route bicycle foley",
        )
        payload["shot_blocks"][0]["audio_cues"] = [{
            "time": "01.00", "kind": "dialogue", "cue": "Start moving.", "perspective": "on-screen",
        }]
        payload["shot_blocks"][1]["audio_cues"] = [{
            "time": "11.00", "kind": "dialogue", "cue": "Keep going.", "perspective": "on-screen",
        }]
        unit = payload["generation_plan"]["units"][1]
        prompt = wrap_video_prompt(payload, get_adapter("seedance").compile_unit(payload, unit), unit)
        audio = next(line for line in prompt.splitlines() if line.startswith("Audio:"))
        self.assertIn("Keep going", audio)
        self.assertIn("Start moving", audio)
        self.assertIn("shared dawn traffic ambience", audio)
        self.assertIn("shared pulse score", audio)
        self.assertIn("all-route bicycle foley", audio)

    def test_native_split_unit_keeps_global_only_speech_voiceover_foley_and_silence(self):
        payload = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text())
        payload["audio_plan"].update(
            generation_route="native",
            dialogue="Global only dialogue",
            voiceover="Global only voiceover",
            foley="Global only foley",
            sfx="Global only sound effect",
            silence="Global only final silence",
        )
        unit = payload["generation_plan"]["units"][1]
        prompt = wrap_video_prompt(payload, get_adapter("seedance").compile_unit(payload, unit), unit)
        audio = next(line for line in prompt.splitlines() if line.startswith("Audio:"))
        for expected in (
            "Global only dialogue", "Global only voiceover", "Global only foley",
            "Global only sound effect", "Global only final silence",
        ):
            self.assertIn(expected, audio)


if __name__ == "__main__":
    unittest.main()
