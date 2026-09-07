from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_storyboard_coverage as coverage  # noqa: E402
from dircreative_visual_asset_plan import inspect_raster_cached, test_png_bytes  # noqa: E402


class StoryboardCoverageTests(unittest.TestCase):
    def test_small_native_crop_with_nested_board_panel_ids_is_invalid_not_exception(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.model_generated_fixture(root, plan, small_lossless_crops=True)
            plan["motion_planning"]["boards"][0]["panel_ids"][0] = ["p2"]
            result = coverage.validate_motion_planning(plan, root)
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(result["errors"])

    def test_planning_target_cli_and_cross_page_action_use_plan_scope(self):
        from dircreative_visual_asset_plan import derive_plan
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
            for name in ("tvc-60s-inventory.json", "tvc-60s-shot-cards.json", "tvc-60s-creative-source.json"):
                shutil.copyfile(fixture_root / name, root / name)
            inventory_path = root / "tvc-60s-inventory.json"
            inventory = json.loads(inventory_path.read_text()); inventory["scope"] = "sequence"
            inventory_path.write_text(json.dumps(inventory))
            plan = derive_plan(inventory, inventory_file=inventory_path.name, base_dir=root)
            plan_path = root / "visual-plan.json"; plan_path.write_text(json.dumps(plan))
            times, _, errors = coverage.source_shots(root, plan["shot_cards_file"], plan["shot_cards_sha256"])
            self.assertEqual(errors, [])
            selected_shots = plan["shot_ids"][5:7]
            anchor = next(item for item in plan["assets"] if item["role"] == "professional_storyboard_motion_map")
            self.assertIn(selected_shots[0], anchor["coverage"]["shot_ids"])
            self.assertNotIn(selected_shots[1], anchor["coverage"]["shot_ids"])
            panels = [self.panel(f"p{index}", shot, f"r{index}", "contact", times[shot][0] + 0.1, "visible contact")
                      for index, shot in enumerate(selected_shots)]
            sidecar = {"schema_version": "1.0", "project_id": plan["project_id"], "scope": "sequence", "frame_rate_fps": 25,
                       "shot_cards_file": plan["shot_cards_file"], "shot_cards_sha256": plan["shot_cards_sha256"], "panels": panels,
                       "requirements": [{"requirement_id": f"r{index}", "source_anchor": f"cards:{shot}", "kind": "action",
                                         "shot_ids": [shot], "phases": ["contact"], "risk": "medium", "image_required": True}
                                        for index, shot in enumerate(selected_shots)]}
            sidecar_path = root / "coverage.json"; sidecar_path.write_text(json.dumps(sidecar))
            before = plan_path.read_bytes()
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/dircreative_storyboard_coverage.py"), "resolve-planning-target",
                 str(sidecar_path), "--project-root", str(root), "--visual-plan", str(plan_path),
                 "--scope-asset", anchor["asset_id"], "--panel-ids", "p0", "p1"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            resolved = json.loads(proc.stdout)
            self.assertEqual(resolved["asset"]["coverage"]["shot_ids"], selected_shots)
            self.assertEqual([item["panel_id"] for item in resolved["panels"]], ["p0", "p1"])
            self.assertEqual(plan_path.read_bytes(), before)
            altered = copy.deepcopy(resolved["motion_planning"]); altered["panel_ids"].reverse()
            with self.assertRaisesRegex(ValueError, "planning_target_panel_scope_mismatch"):
                coverage.resolve_planning_image_target(altered, visual_plan_binding=resolved["visual_plan"], project_root=root)

    def test_planning_target_rejects_wrong_source_hash_and_wrong_anchor(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan_path, sidecar = self.legacy_fixture(root)
            plan = json.loads(plan_path.read_text()); scope = next(item for item in plan["assets"] if item["role"] == "professional_storyboard_motion_map")
            path = root / "coverage.json"; path.write_text(json.dumps(sidecar))
            plan_binding = {"relative_path": plan_path.name, "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest()}
            baseline = {"target": "coverage.planning_image", "scope_asset_id": scope["asset_id"], "coverage_file": path.name,
                        "coverage_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "panel_ids": ["opening"]}
            for case in ("hash", "anchor", "duplicate", "escape"):
                with self.subTest(case=case):
                    binding = copy.deepcopy(baseline)
                    if case == "hash": binding["coverage_sha256"] = "0" * 64
                    elif case == "anchor": binding["scope_asset_id"] = "nonexistent-page"
                    elif case == "duplicate": binding["panel_ids"] = ["opening", "opening"]
                    elif case == "escape": binding["coverage_file"] = "../coverage.json"
                    with self.assertRaises((ValueError, OSError)):
                        coverage.resolve_planning_image_target(binding, visual_plan_binding=plan_binding, project_root=root)

    def test_planning_image_target_is_derived_without_mutating_formal_page(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan_path, sidecar = self.legacy_fixture(root)
            plan_before = plan_path.read_bytes()
            plan = json.loads(plan_before)
            anchor = next(item for item in plan["assets"] if item["role"] == "professional_storyboard_motion_map")
            coverage_path = root / "coverage-design.json"
            coverage_path.write_text(json.dumps(sidecar))
            binding = {"target": "coverage.planning_image", "scope_asset_id": anchor["asset_id"],
                       "coverage_file": coverage_path.name, "coverage_sha256": hashlib.sha256(coverage_path.read_bytes()).hexdigest(),
                       "panel_ids": ["opening"]}
            result = coverage.resolve_planning_image_target(
                binding, project_root=root,
                visual_plan_binding={"relative_path": plan_path.name, "sha256": hashlib.sha256(plan_before).hexdigest()},
            )
            target = result["asset"]
            self.assertNotIn(target["asset_id"], {item["asset_id"] for item in plan["assets"]})
            self.assertEqual(target["role"], "professional_storyboard_motion_map")
            self.assertEqual(target["operation"], "styleboard")
            self.assertEqual(result["motion_planning"]["target"], "coverage.planning_image")
            self.assertEqual([item["panel_id"] for item in result["panels"]], ["opening"])
            self.assertNotEqual(target["purpose"], anchor["purpose"])
            self.assertEqual(anchor["action"], "assemble")
            self.assertEqual(anchor["compile_route"], "deterministic_assembly")
            self.assertEqual(plan_path.read_bytes(), plan_before)

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

    def test_action_requirement_phases_need_distinct_available_images(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan = self.plan(root)
            action_image = root / "action.png"
            action_image.write_bytes(test_png_bytes(1))
            action_hash = coverage.hashlib.sha256(action_image.read_bytes()).hexdigest()
            hold_image = root / "hold.png"
            hold_image.write_bytes(test_png_bytes(2))
            hold_hash = coverage.hashlib.sha256(hold_image.read_bytes()).hexdigest()
            for panel in plan["panels"][:3]:
                panel["state"] = "shared-static-state"
                panel["image"] = {
                    "status": "available",
                    "path": action_image.name,
                    "sha256": action_hash,
                }
            plan["panels"][3]["image"] = {
                "status": "available",
                "path": hold_image.name,
                "sha256": hold_hash,
            }
            result = coverage.validate(plan, root, "assets")
        self.assertEqual(result["status"], "invalid")
        self.assertIn(
            f"action_requirement_phase_image_reuse:act:{action_hash}",
            result["errors"],
        )
        self.assertNotIn(
            f"same_image_hash_multiple_states:S01:{action_hash}",
            result["errors"],
        )

    def test_static_images_can_be_reused_across_separate_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan = self.plan(root)
            plan["requirements"][0]["risk"] = "low"
            for index, panel in enumerate(plan["panels"]):
                image = root / f"panel-{index}.png"
                image.write_bytes(test_png_bytes(index + 1))
                panel["image"] = {
                    "status": "available",
                    "path": image.name,
                    "sha256": coverage.hashlib.sha256(image.read_bytes()).hexdigest(),
                }
            shared_image = root / "static-reuse.png"
            shared_image.write_bytes(test_png_bytes(20))
            shared_hash = coverage.hashlib.sha256(shared_image.read_bytes()).hexdigest()
            plan["panels"][3].update(
                {
                    "state": "shared-static-state",
                    "image": {
                        "status": "available",
                        "path": shared_image.name,
                        "sha256": shared_hash,
                    },
                }
            )
            plan["requirements"].append(
                {
                    "requirement_id": "static-reuse",
                    "source_anchor": "cards:S02-static",
                    "kind": "establish",
                    "shot_ids": ["S02"],
                    "phases": ["hold"],
                    "risk": "low",
                    "image_required": False,
                }
            )
            static_panel = self.panel(
                "p5", "S02", "static-reuse", "hold", 5.0, "shared-static-state"
            )
            static_panel["image"] = {
                "status": "available",
                "path": shared_image.name,
                "sha256": shared_hash,
            }
            plan["panels"].append(static_panel)
            result = coverage.validate(plan, root, "assets")
        self.assertEqual(result["status"], "valid")

    def test_action_design_can_start_without_drawings_but_color_readiness_cannot(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan = self.plan(root)
            self.assertEqual(coverage.validate(plan, root, "design")["status"], "valid")
            planning = coverage.validate(plan, root, "planning")
            self.assertEqual(planning["status"], "partial")
            self.assertIn("motion_drawing:p2", planning["missing_planning"])
            self.assertEqual(planning["missing_images"], [])
            plan["requirements"][0]["risk"] = "low"
            self.assertEqual(coverage.validate(plan, root, "planning")["status"], "valid")
            plan["requirements"][1]["planning_required"] = True
            self.assertEqual(coverage.motion_panel_ids(plan), ["p4"])

    def planning_fixture(self, root: Path, plan: dict) -> None:
        for index, panel in enumerate(plan["panels"][:3]):
            drawing = root / f"sketch-{index}.png"
            drawing.write_bytes(test_png_bytes(index + 30))
            panel["planning_image"] = {"status": "available", "presentation": "line_art", "path": drawing.name, "sha256": coverage.hashlib.sha256(drawing.read_bytes()).hexdigest()}
            panel["motion_annotations"] = [
                {"kind": "camera", "subject": "camera", "label": "固定机位", "stationary": True},
                {"kind": "action", "subject": "lin hand", "label": "手向目标移动", "points": [[0.2, 0.5], [0.6, 0.5]]},
            ]
        # Exercise the real assembler with synthetic inputs, not drawing quality.
        import dircreative_storyboard_page_assembler as assembler
        board = root / "board.png"
        ids = ["p1", "p2", "p3"]
        receipt = root / "board.json"
        result = assembler.assemble_motion_board(json.dumps(plan).encode(), project_root=root, panel_ids=ids, columns=3, output_path=board, receipt_path=receipt)
        if result.get("status") == "TOOL_BLOCKED" and result.get("errors") == ["motion_cjk_font_unavailable"]:
            self.skipTest("Manual overlay needs a CJK font; generated-board checks do not.")
        self.assertEqual(result["status"], "assembled", result)
        board_hash = result["output_sha256"]
        review = root / "review.md"
        review.write_text("Fixture review binding only; no visual approval.")
        plan["motion_planning"] = {"reason": "contact needs rehearsal", "panel_ids": ids, "boards": [{"panel_ids": ids, "image": {"path": board.name, "sha256": board_hash}, "receipt": {"path": receipt.name, "sha256": coverage.hashlib.sha256(receipt.read_bytes()).hexdigest()}}]}
        plan["motion_planning"]["review"] = {"status": "reviewed", "kind": "ai", "path": review.name, "sha256": coverage.hashlib.sha256(review.read_bytes()).hexdigest(), "inputs_sha256": coverage.motion_review_sha256(plan)}

    def model_generated_fixture(
        self,
        root: Path,
        plan: dict,
        *,
        small_lossless_crops: bool = False,
    ) -> None:
        import dircreative_storyboard_page_assembler as assembler
        plan["aspect_ratio"] = "16:9"
        source = root / "model-annotated-board.png"
        cells = (
            [
                {"panel_id": "p2", "rect": [643, 4, 1142, 438]},
                {"panel_id": "p1", "rect": [4, 443, 591, 871]},
                {"panel_id": "p3", "rect": [1148, 443, 1668, 871]},
            ]
            if small_lossless_crops
            else [
                {"panel_id": "p2", "rect": [0, 0, 640, 900]},
                {"panel_id": "p1", "rect": [640, 0, 1280, 900]},
                {"panel_id": "p3", "rect": [1280, 0, 1920, 900]},
            ]
        )
        sheet = assembler.Image.new(
            "RGB",
            (1672, 941) if small_lossless_crops else (1920, 900),
            "white",
        )
        draw = assembler.ImageDraw.Draw(sheet)
        for cell, color in zip(cells, ((220, 40, 40), (40, 220, 40), (40, 40, 220))):
            left, top, right, bottom = cell["rect"]
            draw.rectangle((left, top, right - 1, bottom - 1), fill=color)
            draw.line((left + 20, top + 30, right - 20, bottom - 30), fill="black", width=8)  # model-baked annotation
        sheet.save(source, format="PNG")
        source_hash = coverage.hashlib.sha256(source.read_bytes()).hexdigest()
        cell_map = root / "model-cells.json"
        cell_map.write_text(json.dumps({"sheet_sha256": source_hash, "cells": cells}), encoding="utf-8")
        extraction = assembler.extract_clean_sheet(
            sheet_path=source, cell_map_path=cell_map, output_dir=root,
            receipt_path=root / "model-cells.receipt.json",
        )
        self.assertEqual(extraction["status"], "extracted", extraction)
        extracted = {item["panel_id"]: item for item in extraction["cells"]}
        kinds = ("action", "lighting", "environment")
        for panel, kind in zip(plan["panels"][:3], kinds):
            item = extracted[panel["panel_id"]]
            panel["planning_image"] = {
                "status": "available", "presentation": "line_art", "annotation_source": "model_generated",
                "path": item["output_relative_path"], "sha256": item["output_sha256"],
                **({} if small_lossless_crops else {"frame_rect": [0, 100, 640, 460]}),
            }
            panel["motion_annotations"] = [{"kind": kind, "subject": "model visual cue", "label": f"{kind} 已在图中标注"}]
        ids = ["p2", "p1", "p3"]
        receipt = root / "model-cells.receipt.json"
        plan["motion_planning"] = {
            "reason": "model board is the annotation source", "panel_ids": ids,
            "legend": {kind: {"color": color, "label": kind} for kind, color in zip(kinds, ("red", "green", "blue"))},
            "boards": [{"annotation_source": "model_generated", "panel_ids": ids, "image": {"path": source.name, "sha256": source_hash}, "receipt": {"path": receipt.name, "sha256": coverage.hashlib.sha256(receipt.read_bytes()).hexdigest()}}],
        }
        review = root / "model-review.md"
        review.write_text("Fixture binding only; visual quality remains unverified.")
        plan["motion_planning"]["review"] = {"status": "reviewed", "kind": "ai", "path": review.name, "sha256": coverage.hashlib.sha256(review.read_bytes()).hexdigest(), "inputs_sha256": coverage.motion_review_sha256(plan)}

    def test_lossless_small_model_generated_planning_crops_require_source_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.model_generated_fixture(root, plan, small_lossless_crops=True)
            crop = root / plan["panels"][0]["planning_image"]["path"]
            self.assertEqual(coverage.inspect_raster(crop)[1], "dimensions_below_minimum")
            canonical_cache = {}
            self.assertEqual(
                inspect_raster_cached(crop, canonical_cache)[1],
                "dimensions_below_minimum",
            )
            planning = coverage.validate(plan, root, "planning")
            self.assertEqual(planning["status"], "valid", planning)
            self.assertEqual(coverage.validate_motion_planning(plan, root, require_review=False)["status"], "valid")
            self.assertEqual(
                inspect_raster_cached(crop, canonical_cache)[1],
                "dimensions_below_minimum",
            )
            plan["panels"][0]["image"] = {
                "status": "available",
                "path": crop.name,
                "sha256": coverage.hashlib.sha256(crop.read_bytes()).hexdigest(),
            }
            production = coverage.validate(plan, root, "assets")
            self.assertIn(
                "available_image_not_valid_png:p1:dimensions_below_minimum",
                production["errors"],
            )

    def test_small_model_generated_crop_rejects_missing_receipt_fake_source_and_pixel_swap(self):
        for case in ("missing_receipt", "fake_source", "pixel_swap"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as raw:
                root = Path(raw); plan = self.plan(root)
                self.model_generated_fixture(root, plan, small_lossless_crops=True)
                board = plan["motion_planning"]["boards"][0]
                if case == "missing_receipt":
                    board["receipt"] = {"path": "missing.json", "sha256": "0" * 64}
                elif case == "fake_source":
                    import dircreative_storyboard_page_assembler as assembler
                    fake = root / "fake-source.png"
                    assembler.Image.new("RGB", (1672, 941), "black").save(fake, format="PNG")
                    board["image"] = {"path": fake.name, "sha256": coverage.hashlib.sha256(fake.read_bytes()).hexdigest()}
                else:
                    import dircreative_storyboard_page_assembler as assembler
                    crop = root / plan["panels"][0]["planning_image"]["path"]
                    with assembler.Image.open(crop) as image:
                        altered = image.copy()
                    assembler.ImageDraw.Draw(altered).rectangle((5, 5, 25, 25), fill="black")
                    altered.save(crop, format="PNG")
                    new_hash = coverage.hashlib.sha256(crop.read_bytes()).hexdigest()
                    plan["panels"][0]["planning_image"]["sha256"] = new_hash
                    receipt_path = root / "model-cells.receipt.json"
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    next(cell for cell in receipt["cells"] if cell["panel_id"] == "p1")["output_sha256"] = new_hash
                    receipt["receipt_sha256"] = coverage.json_hash({key: value for key, value in receipt.items() if key != "receipt_sha256"})
                    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                    board["receipt"]["sha256"] = coverage.hashlib.sha256(receipt_path.read_bytes()).hexdigest()
                    plan["motion_planning"]["review"]["inputs_sha256"] = coverage.motion_review_sha256(plan)
                result = coverage.validate(plan, root, "planning")
                self.assertEqual(result["status"], "invalid", result)
                self.assertIn("motion_drawing_png_invalid:p1:dimensions_below_minimum", result["errors"])

    def test_model_generated_board_preserves_baked_annotations_and_validates_mapping(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.model_generated_fixture(root, plan)
            result = coverage.validate(plan, root, "planning")
            self.assertEqual(result["status"], "valid", result)
            self.assertEqual(result["visual_quality"], "unverified")
            self.assertEqual(plan["motion_planning"]["boards"][0]["annotation_source"], "model_generated")
            self.assertNotIn("points", plan["panels"][0]["motion_annotations"][0])
            import dircreative_storyboard_page_assembler as assembler
            duplicate_overlay = assembler.assemble_motion_board(
                json.dumps(plan).encode(), project_root=root, panel_ids=["p1", "p2", "p3"],
                columns=3, output_path=root / "must-not-overlay.png", receipt_path=root / "must-not-overlay.json",
            )
            self.assertEqual(duplicate_overlay["status"], "blocked")
            self.assertIn("motion_model_generated_board_preserved_without_overlay", duplicate_overlay["errors"])

    def test_model_generated_legend_and_mapping_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.model_generated_fixture(root, plan)
            plan["motion_planning"]["legend"].pop("lighting")
            result = coverage.validate(plan, root, "planning")
            self.assertIn("motion_model_legend_missing:lighting", result["errors"])
            other = root / "mapping-drift"; other.mkdir()
            plan = self.plan(other); self.model_generated_fixture(other, plan)
            plan["motion_planning"]["boards"][0]["panel_ids"] = ["p1", "p2", "p3"]
            result = coverage.validate(plan, other, "planning")
            self.assertIn("motion_board_receipt_mismatch:0", result["errors"])

    def test_model_generated_crop_swap_and_stale_review_fail_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.model_generated_fixture(root, plan)
            first, second = plan["panels"][0]["planning_image"], plan["panels"][1]["planning_image"]
            first["path"], second["path"] = second["path"], first["path"]
            first["sha256"], second["sha256"] = second["sha256"], first["sha256"]
            result = coverage.validate(plan, root, "planning")
            self.assertIn("motion_board_receipt_mismatch:0", result["errors"])
            self.assertIn("motion_review_binding_invalid", result["errors"])
            changed_root = root / "changed-source"; changed_root.mkdir()
            changed_plan = self.plan(changed_root); self.model_generated_fixture(changed_root, changed_plan)
            import dircreative_storyboard_page_assembler as assembler
            source = changed_root / "model-annotated-board.png"
            with assembler.Image.open(source) as image:
                altered = image.copy()
            assembler.ImageDraw.Draw(altered).rectangle((10, 10, 20, 20), fill="black")
            altered.save(source, format="PNG")
            changed_plan["motion_planning"]["boards"][0]["image"]["sha256"] = coverage.hashlib.sha256(source.read_bytes()).hexdigest()
            result = coverage.validate(changed_plan, changed_root, "planning")
            self.assertIn("motion_board_receipt_mismatch:0", result["errors"])

    def test_model_generated_crop_pixel_substitution_fails_after_all_hashes_are_resealed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.model_generated_fixture(root, plan)
            import dircreative_storyboard_page_assembler as assembler
            crop = root / plan["panels"][0]["planning_image"]["path"]
            with assembler.Image.open(crop) as image:
                altered = image.copy()
            assembler.ImageDraw.Draw(altered).rectangle((5, 5, 25, 25), fill="black")
            altered.save(crop, format="PNG")
            new_hash = coverage.hashlib.sha256(crop.read_bytes()).hexdigest()
            plan["panels"][0]["planning_image"]["sha256"] = new_hash
            receipt_path = root / "model-cells.receipt.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            item = next(cell for cell in receipt["cells"] if cell["panel_id"] == "p1")
            item["output_sha256"] = new_hash
            receipt["receipt_sha256"] = coverage.json_hash({key: value for key, value in receipt.items() if key != "receipt_sha256"})
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            board = plan["motion_planning"]["boards"][0]
            board["receipt"]["sha256"] = coverage.hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            review = plan["motion_planning"]["review"]
            review["inputs_sha256"] = coverage.motion_review_sha256(plan)
            result = coverage.validate(plan, root, "planning")
            self.assertIn("motion_board_receipt_mismatch:0", result["errors"])

    def test_annotated_reference_extent_is_not_a_literal_movie_frame(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.model_generated_fixture(root, plan)
            for panel in plan["panels"][:3]:
                panel["planning_image"].pop("frame_rect", None)
            plan["motion_planning"]["review"]["inputs_sha256"] = coverage.motion_review_sha256(plan)
            self.assertEqual(coverage.validate(plan, root, "planning")["status"], "valid")
            plan["panels"][0]["planning_image"]["frame_rect"] = [-1, 0, 100, 100]
            self.assertIn("motion_drawing_frame_rect_invalid:p1", coverage.validate(plan, root, "planning")["errors"])
            plan["panels"][0]["planning_image"].pop("frame_rect")
            import dircreative_storyboard_page_assembler as assembler
            path = root / "portrait-production.png"
            assembler.Image.new("RGB", (640, 900), (41, 52, 63)).save(path)
            plan["panels"][0]["image"] = {"status": "available", "path": path.name, "sha256": coverage.hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertIn("available_image_aspect_ratio_mismatch:p1", coverage.validate(plan, root, "assets")["errors"])

    def test_model_generated_panels_cannot_relabel_a_manual_assembly_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.plan(root)
            self.planning_fixture(root, plan)
            for panel in plan["panels"][:3]:
                panel["planning_image"]["annotation_source"] = "model_generated"
            planning = plan["motion_planning"]
            planning["legend"] = {"action": {"color": "red", "label": "action"}, "camera": {"color": "blue", "label": "camera"}}
            receipt_path = root / "board.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["motion_inputs_sha256"] = coverage.motion_inputs_sha256(plan, ["p1", "p2", "p3"])
            receipt["receipt_sha256"] = coverage.json_hash({key: value for key, value in receipt.items() if key != "receipt_sha256"})
            receipt_path.write_text(json.dumps(receipt))
            planning["boards"][0]["receipt"]["sha256"] = coverage.hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            planning["review"]["inputs_sha256"] = coverage.motion_review_sha256(plan)
            result = coverage.validate(plan, root, "planning")
            self.assertIn("motion_board_receipt_mismatch:0", result["errors"])

    def test_planning_png_cannot_be_copied_or_reencoded_as_production(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan = self.plan(root)
            self.planning_fixture(root, plan)
            for panel in plan["panels"][:3]:
                panel["image"] = {key: value for key, value in panel["planning_image"].items() if key != "presentation"}
            result = coverage.validate(plan, root, "assets")
            self.assertIn("planning_image_cannot_count_as_production:p1", result["errors"])
            import dircreative_storyboard_page_assembler as assembler
            with assembler.Image.open(root / "sketch-0.png") as image:
                image.save(root / "reencoded.png", compress_level=0)
            plan["panels"][0]["image"].update(path="reencoded.png", sha256=coverage.hashlib.sha256((root / "reencoded.png").read_bytes()).hexdigest())
            self.assertIn("planning_image_cannot_count_as_production:p1", coverage.validate(plan, root, "assets")["errors"])

    def test_review_binds_rendered_pages_and_rejects_non_image_board(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan = self.plan(root)
            self.planning_fixture(root, plan)
            subject_hash = coverage.motion_review_sha256(plan)
            plan["panels"][0]["image"] = {"status": "available", "path": "different.png", "sha256": "0" * 64}
            self.assertEqual(subject_hash, coverage.motion_review_sha256(plan))
            plan["panels"][0]["image"] = {"status": "planned"}
            import dircreative_storyboard_page_assembler as assembler
            page = root / "second.png"
            receipt = root / "second.json"
            assembled = assembler.assemble_motion_board(json.dumps(plan).encode(), project_root=root, panel_ids=["p1", "p2", "p3"], columns=1, output_path=page, receipt_path=receipt)
            self.assertEqual(assembled["status"], "assembled", assembled)
            board = plan["motion_planning"]["boards"][0]
            board["image"] = {"path": page.name, "sha256": assembled["output_sha256"]}
            board["receipt"] = {"path": receipt.name, "sha256": coverage.hashlib.sha256(receipt.read_bytes()).hexdigest()}
            self.assertIn("motion_review_binding_invalid", coverage.validate(plan, root, "planning")["errors"])
            page.write_text("This is not a storyboard image.")
            board["image"]["sha256"] = coverage.hashlib.sha256(page.read_bytes()).hexdigest()
            self.assertIn("motion_board_png_invalid:0", coverage.validate(plan, root, "planning")["errors"])

    def test_bound_motion_drawings_and_review_do_not_complete_production_images(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan = self.plan(root)
            self.planning_fixture(root, plan)
            self.assertEqual(coverage.validate(plan, root, "planning")["status"], "valid")
            assets = coverage.validate(plan, root, "assets")
            self.assertEqual(assets["status"], "partial")
            self.assertIn("p2", assets["missing_images"])
            self.assertEqual(assets["motion_planning"]["visual_quality"], "unverified")
            plan["panels"][1]["state"] = "changed contact location"
            stale = coverage.validate(plan, root, "planning")
            self.assertIn("motion_board_receipt_mismatch:0", stale["errors"])
            self.assertIn("motion_review_binding_invalid", stale["errors"])

    def test_motion_annotations_reject_invalid_points_camera_omissions_and_changed_png(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan = self.plan(root)
            self.planning_fixture(root, plan)
            plan["panels"][0]["motion_annotations"][1]["points"][0][0] = 1.1
            result = coverage.validate_motion_planning(plan, root, require_review=False)
            self.assertIn("motion_annotation_invalid:p1:1", result["errors"])
            plan["panels"][0]["motion_annotations"].pop(0)
            result = coverage.validate_motion_planning(plan, root, require_review=False)
            self.assertIn("motion_camera_annotation:p1", result["missing"])
            (root / "sketch-1.png").write_bytes(test_png_bytes(50))
            result = coverage.validate_motion_planning(plan, root, require_review=False)
            self.assertIn("motion_drawing_binding_invalid:p2", result["errors"])

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
