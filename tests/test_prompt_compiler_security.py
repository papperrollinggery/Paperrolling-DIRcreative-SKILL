from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_prompt_compiler as compiler  # noqa: E402


class PromptCompilerSecurityTests(unittest.TestCase):
    def valid_payload(self) -> dict:
        return json.loads(
            (ROOT / "tests/fixtures/prompt-system/valid/minimal-character-scene-10s.json").read_text(
                encoding="utf-8"
            )
        )

    def test_project_file_rejects_parent_escape(self):
        payload = self.valid_payload()
        asset = payload["intake"]["supplied_assets"][0]
        asset.update(
            {
                "source_kind": "project_file",
                "source_locator": "../VERSION",
                "source_hash": "0" * 64,
            }
        )
        errors = compiler.semantic_errors(payload)
        self.assertTrue(any("project_file asset is invalid" in error for error in errors))

    def test_project_file_rejects_absolute_path(self):
        payload = self.valid_payload()
        asset = payload["intake"]["supplied_assets"][0]
        asset.update(
            {
                "source_kind": "project_file",
                "source_locator": "/etc/passwd",
                "source_hash": "0" * 64,
            }
        )
        errors = compiler.semantic_errors(payload)
        self.assertTrue(any("project_file asset is invalid" in error for error in errors))

    def test_prompt_ir_read_is_bounded(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "oversized.json"
            path.write_bytes(b"x" * (compiler.MAX_PROMPT_IR_BYTES + 1))
            with self.assertRaisesRegex(compiler.PromptContractError, "exceeds size limit"):
                compiler.load_prompt_ir(path)

    def test_tapnow_seedance_surface_compiles_documented_8_and_13_second_units(self):
        payload = self.valid_payload()
        payload["capability"].update(
            capability_card_id="seedance_2_5_tapnow_canvas_2026_09_06",
            model_key="seedance",
            version="2.5",
            provider_surface="TapNow Canvas video node, Seedance 2.5",
        )
        payload["audio_plan"]["generation_route"] = "postproduction"
        for duration in (8, 13):
            with self.subTest(duration=duration):
                candidate = copy.deepcopy(payload)
                candidate["output"]["target_duration_sec"] = duration
                candidate["output"]["generation_unit_sec"] = duration
                candidate["shot_blocks"][1]["time_end"] = str(duration)
                candidate["generation_plan"]["units"][0]["time_end"] = str(duration)
                self.assertEqual(compiler.semantic_errors(candidate), [])

    def test_tapnow_seedance_unknown_duration_card_still_blocks_compilation(self):
        payload = self.valid_payload()
        payload["capability"].update(
            capability_card_id="seedance_2_5_tapnow_canvas_2026_09_06",
            model_key="seedance", version="2.5",
            provider_surface="TapNow Canvas video node, Seedance 2.5",
        )
        payload["audio_plan"]["generation_route"] = "postproduction"
        registry = compiler.load_yaml(compiler.REGISTRY_PATH)
        for card in registry["models"]:
            if card["capability_card_id"] == "seedance_2_5_tapnow_canvas_2026_09_06":
                card["duration"] = {"kind": "unverified"}
        with mock.patch.object(compiler, "load_yaml", return_value=registry):
            errors = compiler.semantic_errors(payload)
        self.assertTrue(any("duration is unverified" in error for error in errors), errors)

    def test_annotated_narrative_storyboard_is_a_conditional_reference_not_a_clean_frame(self):
        payload = self.valid_payload()
        payload["intake"]["supplied_assets"].append(
            {
                "asset_id": "action_board",
                "source_kind": "conversation_media",
                "source_locator": "conversation://annotated-action-board",
                "source_authorization": "user_provided",
                "role": "storyboard_motion",
                "locked": True,
                "reuse_action": "direct_reference",
                "preserve": ["shot order", "action path", "camera direction"],
                "may_change": ["drawing texture"],
                "do_not_copy_or_animate": ["caption text", "panel borders", "board layout"],
                "downstream_slots": ["@Image 3"],
            }
        )
        payload["references"].append(
            {
                "platform_slot": "@Image 3", "asset_id": "action_board",
                "role": "annotated narrative storyboard for shot order, action path, and camera direction",
                "direct_input_policy": "conditional", "attached_to_run": True,
                "required_for_shot": False,
                "preserve": ["shot order", "action path", "camera direction"],
                "anti_misread": ["do not render captions, grid panels, borders, or board layout in the video"],
            }
        )
        result = compiler.compile_prompt(payload)
        self.assertEqual(result.upload_mapping[-1]["asset_id"], "action_board")
        self.assertIn("annotated narrative storyboard", result.prompt)
        literal = copy.deepcopy(payload)
        literal["references"][-1]["role"] = "literal clean first frame from the storyboard"
        errors = compiler.semantic_errors(literal)
        self.assertIn("storyboard reference cannot be a literal clean frame: @Image 3", errors)

    def test_bounded_prompt_edit_does_not_require_a_storyboard_reference(self):
        payload = self.valid_payload()
        payload["composition"]["narrative_purpose"] = "make the existing decision beat more concise"
        self.assertEqual(compiler.semantic_errors(payload), [])

    def test_current_spatial_export_layout_is_resolved_from_prompt_project_root(self):
        payload = self.valid_payload()
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            layout = project / "spatial/layout-S01.png"
            layout.parent.mkdir()
            layout.write_bytes(b"layout png")
            export_path = project / "spatial/export-S01.json"
            export_path.write_text("{}", encoding="utf-8")
            binding = {
                "relative_path": "spatial/export-S01.json",
                "sha256": hashlib.sha256(export_path.read_bytes()).hexdigest(),
            }
            payload["intake"]["supplied_assets"].append(
                {
                    "asset_id": "layout-S01",
                    "source_kind": "project_file",
                    "source_locator": "spatial/layout-S01.png",
                    "source_hash": hashlib.sha256(layout.read_bytes()).hexdigest(),
                    "spatial_source": binding,
                    "spatial_context": {"shot_id": "S01", "phase": "initial"},
                    "source_authorization": "project_owned",
                    "role": "layout_reference",
                    "locked": True,
                    "reuse_action": "direct_reference",
                    "preserve": ["position", "pose", "occlusion"],
                    "may_change": [],
                    "do_not_copy_or_animate": ["character identity", "material", "final art style"],
                    "downstream_slots": ["@Image 3"],
                }
            )
            payload["references"].append(
                {
                    "platform_slot": "@Image 3",
                    "upload_order": 3,
                    "asset_id": "layout-S01",
                    "role": "layout reference for position, pose and occlusion",
                    "direct_input_policy": "allowed",
                    "attached_to_run": True,
                    "required_for_shot": True,
                    "preserve": ["position", "pose", "occlusion"],
                    "anti_misread": ["do not control identity or final art style"],
                }
            )
            payload["references"][0]["upload_order"] = 1
            payload["references"][1]["upload_order"] = 2
            fake_engine = types.ModuleType("dircreative_spatial_scene")
            fake_engine.validate_export = lambda received, root: []
            fake_engine.read_export = lambda path, root: {
                "shot_id": "S01",
                "phase": "initial",
                "reference": {
                    "relative_path": "spatial/layout-S01.png",
                    "sha256": hashlib.sha256(layout.read_bytes()).hexdigest(),
                    "role": "layout",
                    "media_class": "layout_reference",
                }
            }
            with mock.patch.dict(sys.modules, {"dircreative_spatial_scene": fake_engine}):
                errors = compiler.semantic_errors(payload, project_root=project)
            self.assertEqual(errors, [])
            layout_reference = payload["references"].pop()
            payload["references"].insert(1, layout_reference)
            payload["references"][1]["platform_slot"] = "@Image 2"
            payload["references"][1]["upload_order"] = 2
            payload["references"][2]["platform_slot"] = "@Image 3"
            payload["references"][2]["upload_order"] = 3
            with mock.patch.dict(sys.modules, {"dircreative_spatial_scene": fake_engine}):
                errors = compiler.semantic_errors(payload, project_root=project)
            self.assertEqual(errors, [])
            with mock.patch.dict(sys.modules, {"dircreative_spatial_scene": fake_engine}):
                result = compiler.compile_prompt(payload, project_root=project)
            self.assertEqual(result.attached_slots, ["@Image 1", "@Image 2", "@Image 3"])
            self.assertEqual(
                result.upload_mapping,
                [
                    {
                        "upload_order": 1,
                        "platform_slot": "@Image 1",
                        "asset_id": "character_source",
                        "role": "identity reference for the woman in the cobalt coat",
                        "source_locator": "conversation://character-1",
                    },
                    {
                        "upload_order": 2,
                        "platform_slot": "@Image 2",
                        "asset_id": "layout-S01",
                        "role": "layout reference for position, pose and occlusion",
                        "source_locator": "spatial/layout-S01.png",
                    },
                    {
                        "upload_order": 3,
                        "platform_slot": "@Image 3",
                        "asset_id": "scene_source",
                        "role": "room geography and camera-axis reference",
                        "source_locator": "conversation://scene-1",
                    },
                ],
            )
            payload["references"][1]["upload_order"] = 3
            with mock.patch.dict(sys.modules, {"dircreative_spatial_scene": fake_engine}):
                errors = compiler.semantic_errors(payload, project_root=project)
            self.assertIn("spatial upload_order does not match platform slot: @Image 2", errors)


if __name__ == "__main__":
    unittest.main()
