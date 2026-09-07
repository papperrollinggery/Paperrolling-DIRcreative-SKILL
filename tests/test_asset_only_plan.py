from __future__ import annotations

import json
import sys
import tempfile
import unittest
import struct
import zlib
import subprocess
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_visual_asset_plan as visual_plan  # noqa: E402
import dircreative_prompt_compiler as prompt_compiler  # noqa: E402


class AssetOnlyPlanTests(unittest.TestCase):
    def inventory(self, name: str) -> dict:
        is_character = name.startswith("character")
        return {
            "schema_version": "2.3",
            "project_id": "asset-only-character" if is_character else "asset-only-product",
            "truth_revision": "brief-v1",
            "truth_locked_at": "2026-09-04T19:18:03Z",
            "creative_source_file": "creative-source.json",
            "creative_source_sha256": "",
            "shot_cards_file": "shot-cards.json",
            "shot_cards_sha256": "",
            "scope": "asset_only",
            "duration_seconds": None,
            "delivery_profile": {
                "medium": "still",
                "aspect_ratio": "3:1" if is_character else "1:1",
                "raster_width": 3072 if is_character else 1024,
                "raster_height": 1024,
                "frame_rate_fps": None,
                "audio_sample_rate_hz": None,
                "action_safe_percent": 100,
                "title_safe_percent": 100,
                "brand_endframe_min_seconds": 0,
                "target_master_spec_status": "requires_target_spec",
            },
            "characters": [
                {
                    "id": "weather-technician",
                    "purpose": "Chinese weather-tower technician, gray-blue cotton workwear, neutral studio background, four matching body views and one far-left face close-up.",
                    "compile_route": "selected_skill_handoff",
                }
            ] if is_character else [],
            "appearance_states": [
                {
                    "id": "weather-technician-base",
                    "character_id": "weather-technician",
                    "purpose": "Gray-blue cotton workwear, gray inner shirt, black safety shoes.",
                }
            ] if is_character else [],
            "products": [] if is_character else [
                {
                    "id": "white-ceramic-cup",
                    "purpose": "A plain white ceramic cup on a pure white background with soft natural light and no text or branding.",
                    "compile_route": "direct_concise",
                }
            ],
            "props": [],
            "scenes": [],
            "shots": [],
            "rhythm_points": [],
            "style_reference_required": False,
            "generation_units": [],
        }

    def materialize(self, inventory_name: str) -> tuple[tempfile.TemporaryDirectory[str], Path, dict]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        inventory = self.inventory(inventory_name)
        creative_source = {
            "schema_version": "1.0",
            "project_id": inventory["project_id"],
            "brief": {"request": "Generate one truthful still asset.", "media": "one PNG still image", "supplied_references": []},
            "story_beats": [],
            "script_lines": [],
        }
        shot_cards = {"schema_version": "1.0", "inventory": inventory_name, "cards": []}
        (root / inventory["creative_source_file"]).write_text(json.dumps(creative_source), encoding="utf-8")
        (root / inventory["shot_cards_file"]).write_text(json.dumps(shot_cards), encoding="utf-8")
        inventory["creative_source_sha256"] = visual_plan.canonical_json_sha256(creative_source)
        inventory["shot_cards_sha256"] = visual_plan.canonical_json_sha256(shot_cards)
        path = root / inventory_name
        path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
        return temp, path, inventory

    def test_product_asset_only_plan_allows_zero_shot_zero_png(self):
        temp, path, inventory = self.materialize("product-still-inventory.json")
        with temp:
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            errors, _metrics = visual_plan.validate_plan(plan, base_dir=path.parent)
        self.assertEqual(errors, [])
        self.assertEqual(plan["completion_claim"], "asset_only_plan_complete")
        self.assertEqual(plan["shot_ids"], [])
        self.assertEqual(plan["assets"][0]["role"], "product_identity_board")

    def test_character_asset_only_plan_keeps_master_contract(self):
        temp, path, inventory = self.materialize("character-still-inventory.json")
        with temp:
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            errors, _metrics = visual_plan.validate_plan(plan, base_dir=path.parent)
        self.assertEqual(errors, [])
        character = next(asset for asset in plan["assets"] if asset["role"] == "character_identity_reference")
        self.assertEqual(character["character_mode"], "headed_master")
        self.assertEqual(character["compile_route"], "selected_skill_handoff")

    def test_nonhuman_character_is_a_character_identity_not_a_prop_workaround(self):
        temp, path, inventory = self.materialize("character-still-inventory.json")
        with temp:
            inventory["characters"][0].update(
                identity_kind="nonhuman",
                purpose="A recurring blue fire bird with copper feather edges, ember eyes, and a distinctive split tail for story continuity.",
            )
            path.write_text(json.dumps(inventory), encoding="utf-8")
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            errors, _metrics = visual_plan.validate_plan(plan, base_dir=path.parent)
        self.assertEqual(errors, [])
        character = next(asset for asset in plan["assets"] if asset["role"] == "character_identity_reference")
        self.assertEqual(character["identity_kind"], "nonhuman")

    def test_unknown_character_identity_kind_is_rejected(self):
        temp, path, inventory = self.materialize("character-still-inventory.json")
        with temp:
            inventory["characters"][0]["identity_kind"] = "mythic"
            with self.assertRaisesRegex(ValueError, "identity_kind"):
                visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)

    def test_nonhuman_candidate_checklist_uses_entity_views_not_human_body_checks(self):
        asset = {"role": "character_identity_reference", "identity_kind": "nonhuman"}
        checks = visual_plan.candidate_check_ids(asset)
        self.assertIn("front_reference_view", checks)
        self.assertIn("left_reference_view", checks)
        self.assertNotIn("frontal_portrait", checks)
        self.assertNotIn("front_body", checks)

    def test_character_identity_kind_tamper_cannot_bypass_inventory_truth(self):
        temp, path, inventory = self.materialize("character-still-inventory.json")
        with temp:
            inventory["characters"][0]["identity_kind"] = "nonhuman"
            path.write_text(json.dumps(inventory), encoding="utf-8")
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            plan["assets"][0]["identity_kind"] = "human"
            errors, _metrics = visual_plan.validate_plan(plan, base_dir=path.parent)
        self.assertIn("character_contract_sha256_mismatch:" + plan["assets"][0]["asset_id"], errors)

    def test_first_asset_only_output_registers_and_can_be_reviewed_without_claiming_completion(self):
        temp, path, inventory = self.materialize("product-still-inventory.json")
        with temp:
            root = path.parent
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=root)
            raw = json.dumps(plan).encode()
            (root/'plan.json').write_bytes(raw)
            (root/'output.png').write_bytes(visual_plan.test_png_bytes(width=1024,height=1024))
            command = [sys.executable,str(ROOT/'scripts/dircreative_asset_execution_gate.py'),
                       '--project-root',str(root)]
            result = subprocess.run(command+['--record-output','--plan','plan.json','--expected-plan-sha256',
                hashlib.sha256(raw).hexdigest(),'--asset-id',plan['assets'][0]['asset_id'],
                '--image','output.png','--execution-task-id','first-still','--output','generated.json'],
                capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            candidate=json.loads((root/'generated.json').read_text())
            self.assertEqual(candidate['completion_claim'],'none')
            self.assertEqual(visual_plan.validate_plan(candidate,base_dir=root)[0],[])
            review=json.loads(result.stdout)['self_check_template']
            asset=candidate['assets'][0]
            review.update(reviewed_at=asset['technical_receipt']['checked_at'],reviewer_id='test',review_task_id='batch-review')
            review['assets'][0]['decision']='checked'
            for item in review['assets'][0]['observations']:
                item.update(result='pass',observed='Test fixture observation for '+item['check_id'])
            (root/'review.json').write_text(json.dumps(review))
            checked=subprocess.run(command+['--check-output','--plan','generated.json','--asset-id',asset['asset_id'],
                '--self-check-manifest','review.json','--output','checked.json'],capture_output=True,text=True)
            self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr)

    def test_standalone_product_prompt_does_not_invent_visible_project_labels(self):
        temp, path, inventory = self.materialize("product-still-inventory.json")
        with temp:
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            asset = plan["assets"][0]
            prompt = prompt_compiler.build_asset_role_prompt(asset, plan)
        self.assertIn(asset["purpose"], prompt)
        self.assertIn("1:1", prompt)
        for metadata in ("Largest title", "Project:", asset["asset_id"], asset["truth_sha256"]):
            self.assertNotIn(metadata, prompt)

    def test_asset_only_plan_cannot_claim_film_scope(self):
        temp, path, inventory = self.materialize("product-still-inventory.json")
        with temp:
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            plan["scope"] = "representative_sample"
            errors, _metrics = visual_plan.validate_plan(plan, base_dir=path.parent)
        self.assertTrue(errors)

    def test_asset_only_character_requires_appearance_state(self):
        temp, path, inventory = self.materialize("character-still-inventory.json")
        with temp:
            inventory["appearance_states"] = []
            with self.assertRaisesRegex(ValueError, "appearance_states"):
                visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)

    def test_asset_only_truth_tamper_is_rejected(self):
        temp, path, inventory = self.materialize("product-still-inventory.json")
        with temp:
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            plan["assets"][0]["truth_sha256"] = "0" * 64
            errors, _metrics = visual_plan.validate_plan(plan, base_dir=path.parent)
        self.assertIn("asset_semantic_drift:identity-product-white-ceramic-cup:truth_sha256", errors)

    def test_asset_only_generated_states_require_actual_evidence(self):
        for status in ("generated_candidate", "user_locked", "reused_locked"):
            with self.subTest(status=status):
                temp, path, inventory = self.materialize("product-still-inventory.json")
                with temp:
                    plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
                    plan["assets"][0]["status"] = status
                    errors, _ = visual_plan.validate_plan(plan, base_dir=path.parent)
                self.assertTrue(any("file_missing" in error for error in errors), errors)

    def test_asset_only_claim_cannot_label_a_film(self):
        path = ROOT / "tests/fixtures/visual-asset-plan/valid-coverage-unit.json"
        plan = json.loads(path.read_text())
        plan["completion_claim"] = "asset_only_plan_complete"
        errors, _ = visual_plan.validate_plan(plan, base_dir=path.parent)
        self.assertIn("asset_only_plan_complete_requires_asset_only_scope", errors)

    def test_generated_candidate_and_planned_asset_can_coexist(self):
        temp, path, inventory = self.materialize("product-still-inventory.json")
        with temp:
            inventory["products"].append({"id": "second-cup", "purpose": "A second plain ceramic cup reference for an independent still study."})
            path.write_text(json.dumps(inventory))
            plan = visual_plan.derive_plan(inventory, inventory_file=path.name, base_dir=path.parent)
            width, height = 640, 640
            rows = b"".join(b"\0" + b"".join(bytes((x % 256, y % 256, (x + y) % 256)) for x in range(width)) for y in range(height))
            def chunk(kind, data):
                return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
            image = path.parent / "cup.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
            asset = plan["assets"][0]
            asset.update(status="generated_candidate", generated_file=image.name)
            stamped = visual_plan.stamp_plan_evidence(plan, base_dir=path.parent)
            errors, metrics = visual_plan.validate_plan(stamped, base_dir=path.parent)
            self.assertEqual(errors, [])
            self.assertEqual(metrics["evidence_files_verified"], 1)
            self.assertEqual(stamped["assets"][1]["status"], "planned")
            self.assertFalse(metrics["whole_film_visual_assets_complete"])
            stamped["assets"][0]["status"] = "user_locked"
            errors, _ = visual_plan.validate_plan(stamped, base_dir=path.parent)
            self.assertTrue(any("not_visual_qa_approved" in error for error in errors), errors)

    def test_film_scope_still_requires_frame_rate_and_audio(self):
        plan_path = ROOT / "tests/fixtures/visual-asset-plan/valid-coverage-unit.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["delivery_profile"]["frame_rate_fps"] = None
        plan["delivery_profile"]["audio_sample_rate_hz"] = None
        errors, _metrics = visual_plan.validate_plan(plan, base_dir=plan_path.parent)
        self.assertIn("delivery_profile_frame_rate_invalid", errors)
        self.assertIn("delivery_profile_audio_rate_invalid", errors)


if __name__ == "__main__":
    unittest.main()
