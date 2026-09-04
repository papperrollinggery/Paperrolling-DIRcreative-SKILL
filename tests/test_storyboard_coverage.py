from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_storyboard_coverage as coverage  # noqa: E402
from dircreative_visual_asset_plan import test_png_bytes  # noqa: E402


class StoryboardCoverageTests(unittest.TestCase):
    def test_contained_input_file_accepts_relative_path_object(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "legacy.json"
            target.write_text("{}\n", encoding="utf-8")
            self.assertEqual(
                coverage.contained_input_file(root, Path("legacy.json")),
                target.resolve(),
            )

    def write_cards(self, root: Path) -> str:
        cards = {"cards": [
            {"shot_id": "S01", "timecode": "00:00-00:03", "duration_seconds": 3},
            {"shot_id": "S02", "timecode": "00:03-00:06", "duration_seconds": 3},
        ]}
        (root / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
        return coverage.json_hash(cards)

    def plan(self, root: Path) -> dict:
        source_hash = self.write_cards(root)
        return {
            "schema_version": "1.0", "project_id": "coverage-test", "frame_rate_fps": 25,
            "scope": "whole_film", "shot_cards_file": "cards.json", "shot_cards_sha256": source_hash,
            "requirements": [
                {"requirement_id": "act", "source_anchor": "cards:S01", "kind": "action", "shot_ids": ["S01"], "phases": ["start", "contact", "result"], "risk": "medium", "image_required": True},
                {"requirement_id": "hold", "source_anchor": "cards:S02", "kind": "hold", "shot_ids": ["S02"], "phases": ["hold"], "risk": "low", "image_required": False},
            ],
            "panels": [
                self.panel("p1", "S01", "act", "start", 0.2, "hand away"),
                self.panel("p2", "S01", "act", "contact", 1.2, "hand contact"),
                self.panel("p3", "S01", "act", "result", 2.2, "hand complete"),
                self.panel("p4", "S02", "hold", "hold", 4.0, "shared frame"),
            ],
        }

    def legacy_fixture(self, root: Path) -> tuple[Path, dict]:
        fixture_root = ROOT / "tests" / "fixtures" / "visual-asset-plan"
        names = (
            "valid-coverage-unit.json",
            "valid-coverage-unit-inventory.json",
            "valid-coverage-unit-creative-source.json",
            "valid-coverage-unit-shot-cards.json",
        )
        for name in names:
            shutil.copy2(fixture_root / name, root / name)
        legacy_path = root / "valid-coverage-unit.json"
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        sidecar = {
            "schema_version": "1.0", "project_id": legacy["project_id"], "frame_rate_fps": 25,
            "scope": legacy["scope"], "shot_cards_file": legacy["shot_cards_file"],
            "shot_cards_sha256": legacy["shot_cards_sha256"],
            "requirements": [{"requirement_id": "opening", "source_anchor": "cards:S01", "kind": "establish", "shot_ids": ["S01"], "phases": ["hold"], "risk": "medium", "image_required": True}],
            "panels": [self.panel("opening", "S01", "opening", "hold", 1.0, "office establishes")],
        }
        return legacy_path, sidecar

    @staticmethod
    def panel(panel_id: str, shot_id: str, requirement_id: str, phase: str, at_seconds: float, state: str) -> dict:
        return {"panel_id": panel_id, "shot_id": shot_id, "requirement_id": requirement_id, "phase": phase, "at_seconds": at_seconds, "state": state, "camera_setup": f"camera-{panel_id}", "view_subject": "lin", "gaze_target": "father", "axis_id": "river", "axis_side": "north", "look_direction": "left", "image": {"status": "planned"}}

    def test_same_shot_action_panels_and_static_shared_frame_have_no_quota(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result = coverage.validate(self.plan(Path(raw)), Path(raw), "design")
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["coverage"]["panels"], 4)

    def test_missing_phase_and_whole_film_shot_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            plan = self.plan(Path(raw)); plan["panels"] = plan["panels"][:2]
            result = coverage.validate(plan, Path(raw), "design")
        self.assertEqual(result["status"], "invalid")
        self.assertIn("missing_requirement_phase_panel:act:result", result["errors"])
        self.assertIn("missing_whole_film_shot_panel:S02", result["errors"])

    def test_requirement_phases_can_span_allowed_shots_without_cartesian_panels(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            cards = {"cards": [
                {"shot_id": "S01", "timecode": "00:00-00:03"},
                {"shot_id": "S02", "timecode": "00:03-00:06"},
                {"shot_id": "S03", "timecode": "00:06-00:09"},
            ]}
            (root / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
            plan = {"schema_version": "1.0", "project_id": "spanning-action", "frame_rate_fps": 25, "scope": "whole_film", "shot_cards_file": "cards.json", "shot_cards_sha256": coverage.json_hash(cards), "requirements": [{"requirement_id": "action", "source_anchor": "beat:1", "kind": "action", "shot_ids": ["S01", "S02", "S03"], "phases": ["prepare", "contact", "consequence"], "risk": "medium", "image_required": False}], "panels": [self.panel("a", "S01", "action", "prepare", 1, "before"), self.panel("b", "S02", "action", "contact", 4, "touch"), self.panel("c", "S03", "action", "consequence", 7, "after")]}
            self.assertEqual(coverage.validate(plan, root, "design")["status"], "valid")
            plan["panels"].pop()
            result = coverage.validate(plan, root, "design")
        self.assertIn("missing_requirement_phase_panel:action:consequence", result["errors"])
        self.assertIn("missing_whole_film_shot_panel:S03", result["errors"])

    def test_reverse_pair_rejects_wrong_gaze_or_side(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            plan = self.plan(Path(raw))
            reverse = self.panel("p5", "S02", "hold", "hold", 5.0, "father listening")
            reverse.update({"camera_setup": "reverse-camera", "view_subject": "father", "gaze_target": "lin", "look_direction": "right", "axis_side": "south"})
            plan["panels"].append(reverse); plan["eyeline_pairs"] = [{"panel_a": "p1", "panel_b": "p5"}]
            result = coverage.validate(plan, Path(raw), "design")
        self.assertIn("eyeline_pair_axis_side_mismatch:0", result["errors"])
        self.assertNotIn("eyeline_pair_not_reciprocal:0", result["errors"])
        reverse["gaze_target"] = "someone-else"
        with tempfile.TemporaryDirectory() as second_raw:
            root = Path(second_raw); plan = self.plan(root)
            bad_reverse = copy.deepcopy(reverse)
            plan["panels"].append(bad_reverse); plan["eyeline_pairs"] = [{"panel_a": "p1", "panel_b": "p5"}]
            result = coverage.validate(plan, root, "design")
        self.assertIn("eyeline_pair_not_reciprocal:0", result["errors"])
        self.assertEqual(result["status"], "invalid")

    def test_assets_phase_reports_planned_required_images_as_partial(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result = coverage.validate(self.plan(Path(raw)), Path(raw), "assets")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["missing_images"], ["p1", "p2", "p3", "primary:S01", "primary:S02"])

    def test_assets_need_one_real_available_png_per_whole_film_shot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            for requirement in plan["requirements"]:
                requirement["image_required"] = False
            result = coverage.validate(plan, root, "assets")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["missing_images"], ["primary:S01", "primary:S02"])

    def test_tampered_source_image_and_outside_path_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            image = root / "frame.png"; image.write_bytes(test_png_bytes(1))
            bound = plan["panels"][0]["image"] = {"status": "available", "path": "frame.png", "sha256": coverage.hashlib.sha256(image.read_bytes()).hexdigest()}
            self.assertEqual(coverage.validate(plan, root, "assets")["status"], "partial")
            image.write_bytes(test_png_bytes(2))
            self.assertIn("available_image_sha256_mismatch:p1", coverage.validate(plan, root, "assets")["errors"])
            bound["path"] = "../outside.png"
            self.assertIn("available_image_binding_invalid:p1", coverage.validate(plan, root, "assets")["errors"])
            (root / "a").mkdir(); (root / "linked").mkdir()
            linked_frame = root / "linked" / "frame.png"; linked_frame.write_bytes(test_png_bytes(3))
            (root / "a" / "a").symlink_to(root / "linked", target_is_directory=True)
            bound.update({"path": "a/a/frame.png", "sha256": coverage.hashlib.sha256(linked_frame.read_bytes()).hexdigest()})
            self.assertIn("available_image_binding_invalid:p1", coverage.validate(plan, root, "assets")["errors"])
            cards = json.loads((root / "cards.json").read_text(encoding="utf-8"))
            cards["cards"][0]["timecode"] = "00:00-00:02"
            (root / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
            self.assertIn("shot_cards_sha256_mismatch", coverage.validate(plan, root, "design")["errors"])

    def test_malformed_enums_huge_numbers_and_timebox_return_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            plan["scope"] = []
            plan["frame_rate_fps"] = 10 ** 10000
            plan["requirements"][0]["kind"] = []
            plan["panels"][0]["image"]["status"] = []
            result = coverage.validate(plan, root, "design")
            self.assertEqual(result["status"], "invalid")
            self.assertIn("frame_rate_fps_invalid", result["errors"])
            self.assertIn("scope_invalid", result["errors"])
            self.assertIn("requirement_fields_invalid:act", result["errors"])
            self.assertIn("panel_fields_invalid:p1", result["errors"])
            plan = self.plan(root)
            plan["frame_rate_fps"] = 0
            plan["panels"][0]["at_seconds"] = 99
            result = coverage.validate(plan, root, "design")
            self.assertIn("frame_rate_fps_invalid", result["errors"])
            self.assertIn("panel_time_outside_shot:p1", result["errors"])
            oversized = root / "oversized.json"
            with oversized.open("wb") as handle:
                handle.seek(coverage.MAX_JSON_BYTES)
                handle.write(b"x")
            with self.assertRaisesRegex(ValueError, "too_large"):
                coverage.load_json_object(oversized)

    def test_legacy_fixture_joint_validation_exposes_non_completion(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); legacy_path, sidecar = self.legacy_fixture(root)
            result = coverage.validate_with_legacy(sidecar, root, "design", legacy_path)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["legacy"], {"completion_claim": "plan_complete", "whole_film_visual_assets_complete": False})

    def test_legacy_bindings_reject_hash_path_and_project_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); legacy_path, sidecar = self.legacy_fixture(root)
            sidecar["shot_cards_sha256"] = "0" * 64
            self.assertIn("legacy_shot_cards_sha256_mismatch", coverage.validate_with_legacy(sidecar, root, "design", legacy_path)["errors"])
            legacy_path, sidecar = self.legacy_fixture(root)
            shutil.copy2(root / sidecar["shot_cards_file"], root / "other-cards.json")
            sidecar["shot_cards_file"] = "other-cards.json"
            self.assertIn("legacy_shot_cards_file_mismatch", coverage.validate_with_legacy(sidecar, root, "design", legacy_path)["errors"])
            legacy_path, sidecar = self.legacy_fixture(root)
            sidecar["project_id"] = "different-project"
            self.assertIn("legacy_project_id_mismatch", coverage.validate_with_legacy(sidecar, root, "design", legacy_path)["errors"])

    def test_legacy_errors_are_preserved_and_assets_partial_propagates(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); legacy_path, sidecar = self.legacy_fixture(root)
            with patch.object(coverage, "validate_legacy_plan", return_value=(["legacy_required_asset_failure"], {"completion_claim": "plan_complete", "whole_film_visual_assets_complete": False})):
                result = coverage.validate_with_legacy(sidecar, root, "design", legacy_path)
            self.assertEqual(result["status"], "invalid")
            self.assertIn("legacy_required_asset_failure", result["errors"])
            result = coverage.validate_with_legacy(sidecar, root, "assets", legacy_path)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["missing_images"], ["opening"])
        self.assertFalse(result["legacy"]["whole_film_visual_assets_complete"])


if __name__ == "__main__":
    unittest.main()
