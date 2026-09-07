from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_script_to_seedance_handoff as handoff  # noqa: E402
import dircreative_skill_stack as stack  # noqa: E402
import dircreative_prompt_compiler as compiler  # noqa: E402


class MrLiV2IntegrationTests(unittest.TestCase):
    def packet(self):
        result = json.loads(handoff.VALID_PATH.read_text())
        result["method_application"].update(metadata_version="2.0", observed_metadata_version="2.0")
        result["authoritative_script"]["next_source_start"] = None
        return result

    def test_audited_v2_is_selected_with_production_references_and_dir_ownership(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stack._write_mock_skill(root, "mr-li-seedance-25")
            skill = root / "mr-li-seedance-25/SKILL.md"
            skill.write_text(skill.read_text().replace('version: "1.9.0"', 'version: "2.0"'))
            registry = stack.load_registry()
            catalog, _ = stack.discover_roots([("codex_skill", root)], registry)
            case = next(x for x in json.loads(stack.CASES_PATH.read_text())["cases"] if x["id"] == "p17_seedance_direct")
            result = stack.select_stack(
                stack._fixture_intent(case), registry, stack.load_routing(), catalog,
                route_context=stack._fixture_route_context(case),
                body_loader=stack.body_loader_for_roots([("codex_skill", root)], registry),
            )
        self.assertEqual(result["priority_method_provider"], "mr-li-seedance-25")
        self.assertEqual(result["priority_method_provider_version"], "2.0")
        self.assertEqual(result["host_adoption_status"], "unverified")
        self.assertEqual(result["craft_owner"]["application_contract"]["asset_contract_owner"], "dircreative")
        references = {x["relative_path"] for x in result["reference_read_requests"] if x["skill_id"] == "mr-li-seedance-25"}
        self.assertEqual(references, {
            "references/prompt-writing.md", "references/continuity-and-duration.md",
            "references/context-protocol.md", "references/segment-ending.md",
        })
        self.assertLess(result["context"]["isolated_craft_context_bytes"], 65536)

    def test_current_v2_method_packet_keeps_actual_source_complete_status(self):
        self.assertEqual(handoff.method_application_errors(self.packet()), [])

    def test_seedance20_surface_does_not_require_the_seedance25_method(self):
        packet = self.packet()
        packet["model_surface"]["version"] = "2.0"
        packet.pop("method_application")
        self.assertEqual(handoff.method_application_errors(packet), [])

    def test_character_medium_does_not_become_photorealistic(self):
        for mode in ("headed_master", "headed_state", "headless_safe"):
            with self.subTest(mode=mode):
                prompt = compiler.build_character_prompt_from_contract(
                    "二维赛璐璐成年角色，稳定线条和分层色块。", {"mode": mode},
                )
                self.assertIn("二维赛璐璐", prompt)
                self.assertNotIn("photorealistic", prompt.lower())
                self.assertIn("left profile", prompt)
                self.assertIn("right profile", prompt)
                self.assertIn("75%", prompt)

    def test_last_exported_unit_does_not_mean_scene_complete(self):
        packet = self.packet()
        text = "环体脱离攻击范围。"
        packet["authoritative_script"]["next_source_start"] = {
            "source_line_number": 5, "text": text,
            "source_line_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        last = packet["method_application"]["capacity_preflight"][-1]
        last.update(scene_completion_claim="segment_only", next_source_start="source_line:5")
        self.assertEqual(handoff.method_application_errors(packet), [])
        last.update(scene_completion_claim="scene_complete", next_source_start=None)
        self.assertIn("capacity_next_source_or_completion_mismatch:GU02", handoff.method_application_errors(packet))

    def test_source_cursor_is_not_invented_from_packet_end(self):
        packet = self.packet()
        packet["authoritative_script"].pop("next_source_start")
        self.assertIn("authoritative_next_source_start_required", handoff.method_application_errors(packet))

    def test_remaining_source_cursor_matches_real_source_line(self):
        packet = self.packet()
        packet["authoritative_script"]["next_source_start"] = {
            "source_line_number": 4, "text": "编造的下一场。", "source_line_sha256": "0" * 64,
        }
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / packet["authoritative_script"]["source_relative_path"]
            source.parent.mkdir()
            source.write_bytes((handoff.VALID_PATH.parent / "source/SCRIPT-001.md").read_bytes())
            errors = handoff.authoritative_script_errors(packet, project_root=root)
        self.assertIn("authoritative_next_source_line_mismatch", errors)
        self.assertIn("authoritative_next_source_line_hash_mismatch", errors)

    def test_source_cursor_cannot_repeat_an_already_consumed_dialogue_line(self):
        packet = self.packet()
        line = packet["authoritative_script"]["dialogue_lines"][0]
        packet["authoritative_script"]["next_source_start"] = {
            key: line[key] for key in ("source_line_number", "source_line_sha256", "text")
        }
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / packet["authoritative_script"]["source_relative_path"]
            source.parent.mkdir()
            source.write_bytes((handoff.VALID_PATH.parent / "source/SCRIPT-001.md").read_bytes())
            errors = handoff.authoritative_script_errors(packet, project_root=root)
        self.assertIn("authoritative_next_source_already_consumed", errors)

    def test_scoped_voice_variants_are_aggregated_per_speaking_unit(self):
        packet = self.packet()
        line = dict(packet["authoritative_script"]["dialogue_lines"][0])
        line.update(dialogue_line_id="DLG-EARLY", shot_ids=["SH01"])
        packet["authoritative_script"]["dialogue_lines"].append(line)
        packet["method_application"]["capacity_preflight"][0].update(scene_type="mixed", dialogue_characters=5)
        for i in (1, 2):
            binding_id, unit_id = f"VOICE-{i}", f"GU0{i}"
            packet["bindings"].append({
                "binding_id": binding_id, "media_type": "audio", "voice_owner_entity_id": "pilot",
                "status": "available", "direct_input_policy": "allowed", "attached_to_run": True,
                "unit_ids": [unit_id],
            })
            packet["prompt_units"][i - 1]["binding_ids"].append(binding_id)
        self.assertEqual(handoff.method_application_errors(packet), [])
        packet["prompt_units"][1]["binding_ids"].remove("VOICE-2")
        self.assertIn("known_voice_binding_missing:pilot:GU02", handoff.method_application_errors(packet))

    def test_known_speaking_voice_cannot_be_omitted_or_attached_to_silent_unit(self):
        packet = self.packet()
        voice = {
            "binding_id": "VOICE-PILOT", "asset_id": "A-PILOT", "media_type": "audio",
            "voice_owner_entity_id": "pilot", "status": "available",
            "direct_input_policy": "allowed", "attached_to_run": False,
            "unit_ids": ["GU02"], "local_order_by_gu": {},
        }
        packet["bindings"].append(voice)
        self.assertIn("known_voice_binding_missing:pilot:GU02", handoff.method_application_errors(packet))
        voice["attached_to_run"] = True
        packet["prompt_units"][-1]["binding_ids"].append("VOICE-PILOT")
        self.assertNotIn("known_voice_binding_missing:pilot:GU02", handoff.method_application_errors(packet))
        packet["prompt_units"][0]["binding_ids"].append("VOICE-PILOT")
        self.assertIn("voice_binding_without_speech:pilot:GU01", handoff.method_application_errors(packet))

    def test_unavailable_voice_does_not_force_binding_or_new_permission(self):
        packet = self.packet()
        packet["bindings"].append({
            "binding_id": "VOICE-PILOT", "media_type": "audio", "voice_owner_entity_id": "pilot",
            "status": "planned", "direct_input_policy": "planning_only", "attached_to_run": False,
            "unit_ids": ["GU02"],
        })
        self.assertEqual(handoff.method_application_errors(packet), [])


if __name__ == "__main__":
    unittest.main()
