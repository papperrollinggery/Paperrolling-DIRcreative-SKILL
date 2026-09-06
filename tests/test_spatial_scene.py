from __future__ import annotations

import copy
import json
import hashlib
import sys
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_spatial_scene as spatial


class SpatialSceneTests(unittest.TestCase):
    def scene(self):
        return json.loads((ROOT / "examples/spatial-dialogue/scene.json").read_text())

    def test_reverse_shots_change_projection_not_world_positions(self):
        scene = self.scene()
        before = copy.deepcopy(scene)
        views = [spatial.project_scene(scene, shot, "initial") for shot in ("S02", "S03")]
        self.assertEqual(scene, before)
        self.assertEqual(views[0]["axis_side"], views[1]["axis_side"])
        self.assertLess(views[0]["eyelines"]["B"], 0)
        self.assertGreater(views[1]["eyelines"]["A"], 0)
        self.assertNotEqual(views[0]["frame"], views[1]["frame"])

    def test_local_path_revision_invalidates_old_export_preserves_others(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "scene.json"
            before = self.scene()
            path.write_text(json.dumps(before))
            binding = spatial.export_reference(path, root, "S01", "initial", root / "refs")
            self.assertEqual(spatial.validate_export(binding, root), [])
            changed = spatial.revise_path(before, "A", [[.32, .52], [.2, .35], [.15, .85]], "乙说完后", "r2")
            self.assertEqual(changed["room"], before["room"])
            self.assertEqual(changed["entities"], before["entities"])
            self.assertEqual(spatial.entities_at(changed, "final")[1], before["entities"][1])
            path.write_text(json.dumps(changed))
            self.assertIn("spatial_scene_source_stale", spatial.validate_export(binding, root))

    def test_export_is_current_camera_text_free_and_real_decodable_png(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "scene.json"
            path.write_text(json.dumps(self.scene()))
            binding = spatial.export_reference(path, root, "S02", "initial", root / "refs")
            image = Image.open(root / binding["reference"]["relative_path"])
            image.load()
            self.assertEqual(image.size, (1280, 720))
            svg = (root / binding["svg"]["relative_path"]).read_text()
            self.assertNotIn("<text", svg)
            self.assertNotIn("<script", svg)
            self.assertEqual(binding["reference"]["role"], "layout")
            self.assertFalse(binding["literal_frame_eligible"])

    def test_cross_axis_requires_reason_and_unknown_ids_fail(self):
        scene = self.scene()
        scene["cameras"][1]["position"] = [.2, .8]
        self.assertIn("camera_axis_crossing_without_reason:S02", spatial.validate_scene(scene))
        scene["cameras"][1]["crossing_reason"] = "甲离开后有意越轴揭示门口"
        self.assertEqual(spatial.validate_scene(scene), [])
        scene["entities"][0]["gaze_target"] = "missing"
        self.assertIn("entity_gaze_target_missing:A", spatial.validate_scene(scene))

    def test_wrong_camera_png_cannot_be_resealed_as_current_layout(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "scene.json"
            path.write_text(json.dumps(self.scene()))
            master = spatial.export_reference(path, root, "S01", "initial", root / "refs")
            reverse = spatial.export_reference(path, root, "S02", "initial", root / "refs")
            target = root / master["reference"]["relative_path"]
            target.write_bytes((root / reverse["reference"]["relative_path"]).read_bytes())
            master["reference"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertIn("spatial_png_projection_mismatch", spatial.validate_export(master, root))

    def test_existing_visual_plan_consumes_scene_binding_and_rejects_staleness(self):
        import dircreative_visual_asset_plan as plans
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fixture = ROOT / "tests/fixtures/visual-asset-plan"
            for name in ("valid-coverage-unit-inventory.json", "valid-coverage-unit-shot-cards.json", "valid-coverage-unit-creative-source.json"):
                shutil.copyfile(fixture / name, root / name)
            scene = self.scene()
            scene["scene_id"] = "office-desk"
            scene_path = root / "scene.json"
            scene_path.write_text(json.dumps(scene))
            cards_path = root / "valid-coverage-unit-shot-cards.json"
            cards = json.loads(cards_path.read_text())
            cards["cards"][0]["scene_state_source"] = {"relative_path": "scene.json", "sha256": spatial.sha256(scene_path)}
            cards_path.write_text(json.dumps(cards))
            inventory_path = root / "valid-coverage-unit-inventory.json"
            inventory = json.loads(inventory_path.read_text())
            inventory["shot_cards_sha256"] = plans.canonical_json_sha256(cards)
            inventory_path.write_text(json.dumps(inventory))
            plan = plans.derive_plan(inventory, inventory_file=inventory_path.name, base_dir=root)
            errors, _ = plans.validate_plan(plan, base_dir=root)
            self.assertEqual(errors, [])
            self.assertEqual(plan["shot_truth"][0]["scene_state_source"], cards["cards"][0]["scene_state_source"])
            scene["revision"] = "r2"
            scene_path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "scene_state_source is stale"):
                plans.derive_plan(inventory, inventory_file=inventory_path.name, base_dir=root)

    def test_handoff_updates_prop_holder_and_keeps_third_person(self):
        scene = self.scene()
        scene["entities"].extend([
            {"id": "C", "label": "丙", "kind": "character", "position": [.5, .8], "facing": [0, -1], "gaze_target": "A", "height": .28, "support": "floor", "color": "#7b8f6a", "color_name": "灰绿", "asset_id": "C-identity"},
            {"id": "KEY", "label": "钥匙", "kind": "prop", "position": [.47, .52], "elevation": .15, "holder": "A", "support": "A", "color": "#9a8865", "color_name": "灰金", "asset_id": "key"},
        ])
        scene["transfers"] = [{"prop_id": "KEY", "from_holder": "A", "to_holder": "B", "position": [.5, .52, .15], "trigger": "甲伸手交出钥匙，乙接稳"}]
        self.assertEqual(spatial.validate_scene(scene), [])
        after = {entity["id"]: entity for entity in spatial.entities_at(scene, "final")}
        self.assertEqual(after["KEY"]["holder"], "B")
        self.assertEqual(after["C"], scene["entities"][2])
        view = spatial.project_scene(scene, "S02", "final")
        self.assertEqual(set(view["entity_positions"]), {"A", "B", "C", "KEY"})

    def test_actor_and_path_cannot_go_through_solid_table(self):
        scene = self.scene()
        scene["entities"][0]["position"] = [.5, .52]
        self.assertIn("entity_inside_fixed_feature:A:TABLE", spatial.validate_scene(scene))
        scene = self.scene()
        with self.assertRaisesRegex(ValueError, "path_crosses_fixed_feature:A:TABLE"):
            spatial.revise_path(scene, "A", [[.32, .52], [.8, .52]], "说完后", "r2")

    def test_roundtrip_handoff_and_walk_carry_the_prop_with_current_holder(self):
        scene = self.scene()
        scene["entities"].append({"id": "KEY", "label": "钥匙", "kind": "prop", "position": [.36, .52], "elevation": .15, "holder": "A", "support": "A", "color": "#9a8865", "color_name": "灰金", "asset_id": "key"})
        scene["transfers"] = [
            {"prop_id": "KEY", "from_holder": "A", "to_holder": "B", "position": [.64, .52, .15], "trigger": "甲递出", "to_hand": "left"},
            {"prop_id": "KEY", "from_holder": "B", "to_holder": "A", "position": [.36, .52, .15], "trigger": "乙归还", "to_hand": "right"},
        ]
        scene = spatial.revise_path(scene, "A", [[.32, .52], [.2, .35], [.15, .85]], "收好后离开", "r2")
        phase_one = {e["id"]: e for e in spatial.entities_at(scene, "transfer-1")}
        phase_two = {e["id"]: e for e in spatial.entities_at(scene, "transfer-2")}
        final = {e["id"]: e for e in spatial.entities_at(scene, "final")}
        self.assertEqual(phase_one["KEY"]["holder"], "B")
        self.assertEqual(phase_two["KEY"]["holder"], "A")
        self.assertAlmostEqual(final["KEY"]["position"][0]-final["A"]["position"][0], .04)
        self.assertAlmostEqual(final["KEY"]["position"][1], final["A"]["position"][1])
        scene["paths"][0]["stow_prop_ids"] = ["KEY"]
        final = {e["id"]: e for e in spatial.entities_at(scene, "final")}
        self.assertFalse(final["KEY"]["visible"])

    def test_move_then_transfer_replays_in_explicit_order(self):
        scene = self.scene()
        scene["entities"][1]["position"] = [.26, .85]
        scene["cameras"] = scene["cameras"][:1]
        scene["entities"].append({"id": "KEY", "label": "钥匙", "kind": "prop", "position": [.36, .52], "elevation": .15, "holder": "A", "support": "A", "color": "#9a8865", "color_name": "灰金", "asset_id": "key"})
        scene["paths"] = [{"entity_id": "A", "points": [[.32, .52], [.15, .85]], "trigger": "先走到门边", "order": 1}]
        scene["transfers"] = [{"prop_id": "KEY", "from_holder": "A", "to_holder": "B", "position": [.2, .85, .15], "trigger": "到了门边再交出", "order": 2}]
        self.assertEqual(spatial.validate_scene(scene), [])
        self.assertEqual(spatial.phases(scene), ["initial", "path-1", "transfer-1", "final"])
        state = {e["id"]: e for e in spatial.entities_at(scene, "transfer-1")}
        self.assertEqual(state["A"]["position"], [.15, .85])
        self.assertEqual(state["KEY"]["holder"], "B")
        self.assertEqual(spatial.project_scene(scene, "S01", "transfer-1")["entity_positions"]["A"], [.15, .85])

    def test_invalid_path_stow_and_partial_event_order_fail_at_source(self):
        scene = self.scene()
        scene["paths"] = [None]
        self.assertIn("spatial_paths_must_be_object_list", spatial.validate_scene(scene))
        scene = spatial.revise_path(self.scene(), "A", [[.32, .52], [.15, .85]], "离开", "r2")
        scene["paths"][0]["stow_prop_ids"] = ["UNKNOWN"]
        self.assertIn("spatial_stow_props_invalid", spatial.validate_scene(scene))

    def test_handoff_then_walk_cannot_leave_carried_key_outside_scene(self):
        scene = self.scene()
        scene["entities"].append({"id": "KEY", "label": "钥匙", "kind": "prop", "position": [.36, .52], "elevation": .15, "holder": "A", "support": "A", "color": "#9a8865", "color_name": "灰金", "asset_id": "key"})
        scene["transfers"] = [{"prop_id": "KEY", "from_holder": "A", "to_holder": "B", "position": [.5, .52, .15], "trigger": "交给乙", "order": 1}]
        scene["paths"] = [{"entity_id": "B", "points": [[.68, .52], [.75, .8], [.1, .87]], "trigger": "乙走到门边", "order": 2}]
        self.assertIn("spatial_event_position_outside_scene:path-1:KEY", spatial.validate_scene(scene))
        scene["paths"][0]["stow_prop_ids"] = ["KEY"]
        self.assertEqual(spatial.validate_scene(scene), [])
        final = {e["id"]: e for e in spatial.entities_at(scene, "final")}
        self.assertFalse(final["KEY"]["visible"])
        self.assertEqual(final["KEY"]["position"], final["B"]["position"])

    def test_local_path_revision_preserves_order_stow_and_other_events(self):
        scene = json.loads((ROOT / "examples/spatial-dialogue/three-person-handoff.json").read_text())
        scene["paths"][1]["stow_prop_ids"] = ["KEY"]
        changed = spatial.revise_path(scene, "B", [[.67, .52], [.8, .75], [.24, .88]], "乙走另一条绕桌路线", "r2")
        self.assertEqual(changed["paths"][0], scene["paths"][0])
        self.assertEqual(changed["transfers"], scene["transfers"])
        self.assertEqual(changed["paths"][1]["order"], 3)
        self.assertEqual(changed["paths"][1]["stow_prop_ids"], ["KEY"])
        self.assertEqual(changed["room"], scene["room"])
        self.assertEqual(changed["entities"], scene["entities"])
        self.assertFalse({e["id"]: e for e in spatial.entities_at(changed, "final")}["KEY"]["visible"])

    def test_revise_one_of_multiple_paths_for_same_actor_by_phase_id(self):
        scene = json.loads((ROOT / "examples/spatial-dialogue/three-person-handoff.json").read_text())
        scene["paths"].append({"entity_id": "C", "points": [[.1, .78], [.08, .7]], "trigger": "再退半步", "order": 4})
        changed = spatial.revise_path(scene, "C", [[.1, .78], [.06, .65]], "再让出一点空间", "r2", path_id="path-3")
        self.assertEqual(changed["paths"][:2], scene["paths"][:2])
        self.assertEqual(changed["paths"][2]["order"], 4)
        self.assertEqual(changed["paths"][2]["points"][-1], [.06, .65])
        with self.assertRaisesRegex(ValueError, "event_not_found"):
            spatial.revise_path(scene, "C", [[.1, .78], [.06, .65]], "让开", "r2", path_id="path-2")

    def test_floorplan_discussion_needs_no_camera_height_or_axis(self):
        scene = self.scene()
        del scene["cameras"]
        del scene["relationship_axis"]
        for entity in scene["entities"]:
            del entity["height"]
            del entity["facing"]
        self.assertEqual(spatial.validate_scene(scene), [])
        view = spatial.view_payload(scene)["views"][0]
        self.assertEqual(view["shot_id"], "overview")
        self.assertEqual(view["frame"], [])
        self.assertEqual(view["entity_states"], scene["entities"])
        with self.assertRaisesRegex(ValueError, "spatial_shot_missing"):
            spatial.project_scene(scene, "S01")


if __name__ == "__main__":
    unittest.main()
