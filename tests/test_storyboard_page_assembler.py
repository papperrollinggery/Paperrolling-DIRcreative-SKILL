from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_storyboard_page_assembler as assembler  # noqa: E402
import dircreative_visual_asset_plan as visual  # noqa: E402
import dircreative_asset_execution_gate as asset_gate  # noqa: E402


class StoryboardPageAssemblerTests(unittest.TestCase):
    def prepared_plan(self, root: Path) -> tuple[dict, dict]:
        fixture_root = ROOT / "tests/fixtures/asset-execution"
        for name in (
            "character-inventory.json",
            "character-creative-source.json",
            "character-shot-cards.json",
        ):
            shutil.copy2(fixture_root / name, root / name)
        plan = copy.deepcopy(
            json.loads(
                (fixture_root / "character-plan.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        target = next(
            item
            for item in plan["assets"]
            if item["role"] == "professional_storyboard_motion_map"
        )
        parent_ids = set(target["inherits_from"])
        for index, asset in enumerate(plan["assets"], start=1):
            if asset["asset_id"] not in parent_ids:
                continue
            path = root / f"{asset['asset_id']}.png"
            path.write_bytes(visual.test_png_bytes(index))
            asset["status"] = "generated_candidate"
            asset["generated_file"] = path.name
        checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        evidence_by_asset: dict[str, dict] = {}
        entries: list[dict] = []
        for asset in plan["assets"]:
            if asset["asset_id"] not in parent_ids:
                continue
            evidence, reason = visual.inspect_raster(root / asset["generated_file"])
            self.assertIsNone(reason)
            assert evidence is not None
            asset["generated_sha256"] = evidence["sha256"]
            asset["generated_pixel_sha256"] = evidence["pixel_sha256"]
            asset["generated_perceptual_hash"] = evidence["perceptual_hash"]
            asset["technical_receipt"] = visual.make_technical_receipt(
                asset["asset_id"],
                evidence,
                checked_at=checked_at,
            )
            evidence_by_asset[asset["asset_id"]] = evidence
            entries.append(
                {
                    "asset_id": asset["asset_id"],
                    "role": asset["role"],
                    "file_sha256": evidence["sha256"],
                    "pixel_sha256": evidence["pixel_sha256"],
                    "truth_sha256": asset["truth_sha256"],
                    "rubric_id": visual.visual_review_rubric_id(asset["role"]),
                    "rubric": {
                        "truth_and_role_match": True,
                        "coverage_and_continuity_match": True,
                        "composition_readable": True,
                        "artifact_free": True,
                        "downstream_use_fit": True,
                    },
                    "decision": "pass",
                    "notes": "Independent scoped review approves this exact storyboard frame.",
                }
            )
        scope_asset_ids = sorted(parent_ids)
        subject = visual.visual_review_subject_sha256(
            plan,
            scope_asset_ids=scope_asset_ids,
        )
        manifest = {
            "schema_version": visual.SCOPED_VISUAL_REVIEW_MANIFEST_VERSION,
            "ruleset": visual.VISUAL_QA_RULESET,
            "review_subject_sha256": subject,
            "reviewed_at": checked_at,
            "reviewer_type": "independent_ai",
            "reviewer_id": "storyboard-assembler-reviewer",
            "review_task_id": "storyboard-assembler-positive",
            "scope_asset_ids": scope_asset_ids,
            "assets": entries,
        }
        manifest_path = root / "storyboard-frame-review-manifest.json"
        visual.atomic_write_json(manifest_path, manifest)
        manifest_sha = visual.sha256_file(manifest_path)
        for asset in plan["assets"]:
            if asset["asset_id"] not in parent_ids:
                continue
            evidence = evidence_by_asset[asset["asset_id"]]
            review = {
                "receipt_version": visual.VISUAL_QA_RECEIPT_VERSION,
                "asset_id": asset["asset_id"],
                "file_sha256": evidence["sha256"],
                "pixel_sha256": evidence["pixel_sha256"],
                "truth_sha256": asset["truth_sha256"],
                "ruleset": visual.VISUAL_QA_RULESET,
                "reviewed_at": checked_at,
                "reviewer_type": manifest["reviewer_type"],
                "reviewer_id": manifest["reviewer_id"],
                "review_task_id": manifest["review_task_id"],
                "review_manifest_file": manifest_path.name,
                "review_manifest_sha256": manifest_sha,
                "review_subject_sha256": subject,
                "status": "visual_qa_pass",
            }
            review["receipt_sha256"] = visual.receipt_sha256(review)
            asset["visual_qa_receipt"] = review
        return plan, target

    @unittest.skipUnless(assembler.Image is not None, "Pillow is required for storyboard assembly")
    def test_assembles_real_png_and_content_addressed_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = self.prepared_plan(root)
            plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode()
            output = root / "director-storyboard.png"
            receipt_path = root / "director-storyboard.receipt.json"
            with mock.patch.object(
                assembler,
                "load_visual_review_authorization",
                return_value=({}, []),
            ):
                receipt = assembler.assemble(
                    plan_bytes,
                    base_dir=root,
                    asset_id=target["asset_id"],
                    output_path=output,
                    receipt_path=receipt_path,
                )
            evidence, reason = visual.inspect_raster(output)
        self.assertEqual(receipt["status"], "assembled")
        self.assertFalse(receipt["generation_tool_used"])
        self.assertEqual(receipt["shot_ids"], target["coverage"]["shot_ids"])
        self.assertEqual(receipt["visual_plan_sha256"], hashlib.sha256(plan_bytes).hexdigest())
        self.assertEqual(len(receipt["parent_frames"]), 6)
        self.assertIsNone(reason)
        assert evidence is not None
        self.assertEqual((evidence["width"], evidence["height"]), (1920, 1080))
        self.assertEqual(receipt["output_sha256"], evidence["sha256"])

    @unittest.skipUnless(assembler.Image is not None, "Pillow is required for storyboard assembly")
    def test_missing_parent_visual_review_blocks_assembly(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = self.prepared_plan(root)
            parent = next(item for item in plan["assets"] if item["asset_id"] == target["inherits_from"][0])
            parent["visual_qa_receipt"] = None
            plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode()
            result = assembler.assemble(
                plan_bytes,
                base_dir=root,
                asset_id=target["asset_id"],
                output_path=root / "blocked.png",
                receipt_path=root / "blocked.json",
            )
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("parent_frame_visual_review_invalid" in error for error in result["errors"]))

    def test_multi_asset_scoped_manifest_builds_complete_dependency_evidence_map(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = self.prepared_plan(root)
            parent = next(
                item for item in plan["assets"] if item["asset_id"] == target["inherits_from"][0]
            )
            evidence_map, errors = asset_gate._review_manifest_evidence_map(
                parent["visual_qa_receipt"],
                plan,
                base_dir=root,
            )
        self.assertEqual(errors, [])
        self.assertEqual(set(evidence_map), set(target["inherits_from"]))

    @unittest.skipUnless(assembler.Image is not None, "Pillow is required for storyboard assembly")
    def test_output_and_receipt_must_be_distinct_new_files(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = self.prepared_plan(root)
            collision = root / "same.png"
            plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode()
            result = assembler.assemble(
                plan_bytes,
                base_dir=root,
                asset_id=target["asset_id"],
                output_path=collision,
                receipt_path=collision,
            )
            self.assertEqual(result["status"], "blocked")
            self.assertIn("assembly_output_receipt_collision", result["errors"])
            self.assertFalse(collision.exists())

    @unittest.skipUnless(assembler.Image is not None, "Pillow is required for storyboard assembly")
    def test_existing_parent_frame_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = self.prepared_plan(root)
            parent = next(item for item in plan["assets"] if item["asset_id"] == target["inherits_from"][0])
            parent_path = root / parent["generated_file"]
            original = parent_path.read_bytes()
            plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode()
            result = assembler.assemble(
                plan_bytes,
                base_dir=root,
                asset_id=target["asset_id"],
                output_path=parent_path,
                receipt_path=root / "new-receipt.json",
            )
            current = parent_path.read_bytes()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("assembly_output_must_be_new", result["errors"])
        self.assertEqual(current, original)

    @unittest.skipUnless(assembler.Image is not None, "Pillow is required for storyboard assembly")
    def test_receipt_write_failure_rolls_back_new_output(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = self.prepared_plan(root)
            plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode()
            output = root / "rollback-output.png"
            receipt = root / "rollback-receipt.json"
            original_writer = assembler._write_new_file
            calls = 0

            def fail_second(path: Path, payload: bytes):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated receipt write failure")
                return original_writer(path, payload)

            with mock.patch.object(
                assembler,
                "load_visual_review_authorization",
                return_value=({}, []),
            ), mock.patch.object(assembler, "_write_new_file", side_effect=fail_second):
                result = assembler.assemble(
                    plan_bytes,
                    base_dir=root,
                    asset_id=target["asset_id"],
                    output_path=output,
                    receipt_path=receipt,
                )
            self.assertEqual(result["status"], "blocked")
            self.assertIn("assembly_receipt_write_or_readback_failed_output_rolled_back", result["errors"])
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())

    def test_pillow_unavailable_is_tool_blocked_without_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = self.prepared_plan(root)
            plan_bytes = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode()
            output = root / "unavailable.png"
            receipt = root / "unavailable.receipt.json"
            with mock.patch.object(assembler, "Image", None), mock.patch.object(
                assembler, "ImageDraw", None
            ), mock.patch.object(assembler, "ImageFont", None), mock.patch.object(
                assembler, "ImageOps", None
            ):
                result = assembler.assemble(
                    plan_bytes,
                    base_dir=root,
                    asset_id=target["asset_id"],
                    output_path=output,
                    receipt_path=receipt,
                )
            self.assertEqual(result["status"], "TOOL_BLOCKED")
            self.assertFalse(output.exists())
            self.assertFalse(receipt.exists())

    def test_parent_symlink_swap_cannot_redirect_output(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(raw).resolve()
            outside = Path(outside_raw).resolve()
            output_dir = root / "output"
            output_dir.mkdir()
            output = output_dir / "page.png"

            def replace_parent() -> None:
                output_dir.rename(root / "output-old")
                output_dir.symlink_to(outside, target_is_directory=True)

            with self.assertRaises((OSError, ValueError)):
                assembler._write_new_file(output, b"sealed", race_hook=replace_parent)
            self.assertFalse((outside / "page.png").exists())
            self.assertFalse((root / "output-old/page.png").exists())


@unittest.skipUnless(assembler.Image is not None, "Pillow is required for storyboard assembly")
class MotionBoardAssemblerTests(unittest.TestCase):
    def model_panel_coverage(self, root: Path, count: int = 2) -> dict:
        plan = self.coverage(root, count)
        for panel in plan["panels"]:
            panel["planning_image"]["annotation_source"] = "model_generated"
        plan["motion_planning"] = {
            "reason": "Fixture layout of existing model-annotated PNGs; no artistic approval.",
            "panel_ids": [panel["panel_id"] for panel in plan["panels"]],
            "legend": {kind: {"color": "black", "label": kind} for kind in ("actor_path", "action", "camera")},
        }
        return plan

    def test_layout_only_preserves_native_pixels_and_needs_no_page_review_to_start(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.model_panel_coverage(root)
            originals = {panel["panel_id"]: (root / panel["planning_image"]["path"]).read_bytes() for panel in plan["panels"]}
            output, receipt_path = root / "native-layout.png", root / "native-layout.json"
            result = assembler.assemble_model_annotation_layout(
                json.dumps(plan).encode(), project_root=root, panel_ids=["p1", "p2"], columns=2,
                cell_size=(1600, 1600), output_path=output, receipt_path=receipt_path,
            )
            self.assertEqual(result["status"], "assembled", result)
            self.assertIs(result["assembled"], True)
            self.assertIs(result["generated"], False)
            self.assertEqual(result["annotation_source"], "model_generated")
            with assembler.Image.open(output) as page:
                for row in result["panels"]:
                    source_path = root / row["source_relative_path"]
                    self.assertEqual(source_path.read_bytes(), originals[row["panel_id"]])
                    with assembler.Image.open(source_path) as source:
                        self.assertEqual(page.crop(tuple(row["placed_rect"])).convert("RGBA").tobytes(), source.convert("RGBA").tobytes())

    def bind_layout_review(self, root: Path, plan: dict, result: dict, receipt_path: Path) -> None:
        planning = plan["motion_planning"]
        planning.setdefault("boards", []).append({
            "annotation_source": "model_generated", "acquisition": "assembled_model_panels",
            "panel_ids": result["panel_ids"], "image": {"path": result["output_relative_path"], "sha256": result["output_sha256"]},
            "receipt": {"path": receipt_path.name, "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest()},
        })
        review = root / "layout-review.md"; review.write_text("Synthetic fixture checks binding only; not artistic or user approval.")
        planning["review"] = {"status": "reviewed", "kind": "ai", "path": review.name,
                              "sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
                              "inputs_sha256": assembler.storyboard_coverage.motion_review_sha256(plan)}

    def test_layout_shrinks_without_upscaling_and_resealed_pixel_or_recipe_tampering_fails(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.model_panel_coverage(root)
            output, receipt_path = root / "layout.png", root / "layout.json"
            result = assembler.assemble_model_annotation_layout(json.dumps(plan).encode(), project_root=root,
                panel_ids=["p1", "p2"], columns=2, cell_size=(512, 460),
                legend_crop={"panel_id": "p1", "rect": [0, 0, 200, 80]}, output_path=output, receipt_path=receipt_path)
            self.assertEqual(result["status"], "assembled", result)
            for row in result["panels"]:
                width = row["placed_rect"][2] - row["placed_rect"][0]
                height = row["placed_rect"][3] - row["placed_rect"][1]
                self.assertLessEqual(width, row["source_width"])
                self.assertLessEqual(height, row["source_height"])
                self.assertAlmostEqual(width / height, row["source_width"] / row["source_height"], delta=.01)
            self.bind_layout_review(root, plan, result, receipt_path)
            self.assertEqual(assembler.storyboard_coverage.validate_motion_planning(plan, root)["status"], "valid")
            original_bytes = output.read_bytes()
            for change in ("placed_rect", "source_hash", "extra_line", "legend_swap"):
                with self.subTest(change=change):
                    mutated = copy.deepcopy(result); current = copy.deepcopy(plan)
                    output.write_bytes(original_bytes)
                    if change == "placed_rect": mutated["panels"][0]["placed_rect"][0] += 1
                    elif change == "source_hash": mutated["panels"][0]["source_sha256"] = "0" * 64
                    elif change == "legend_swap": mutated["legend_crop"]["panel_id"] = "p2"
                    else:
                        with assembler.Image.open(output) as old:
                            altered = old.copy()
                        assembler.ImageDraw.Draw(altered).line((0, 0, 100, 0), fill="red", width=2)
                        altered.save(output)
                    mutated["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
                    mutated["receipt_sha256"] = assembler.canonical_sha256({key: value for key, value in mutated.items() if key != "receipt_sha256"})
                    receipt_path.write_text(json.dumps(mutated))
                    board = current["motion_planning"]["boards"][-1]
                    board["image"]["sha256"] = mutated["output_sha256"]
                    board["receipt"]["sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
                    current["motion_planning"]["review"]["inputs_sha256"] = assembler.storyboard_coverage.motion_review_sha256(current)
                    checked = assembler.storyboard_coverage.validate_motion_planning(current, root)
                    self.assertEqual(checked["status"], "invalid", checked)
                    self.assertIn("motion_board_receipt_mismatch:0", checked["errors"])

    def test_layout_legend_uses_unique_verified_native_sheet_and_keeps_small_crops(self):
        from tests.test_storyboard_coverage import StoryboardCoverageTests
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); factory = StoryboardCoverageTests(); plan = factory.plan(root)
            factory.model_generated_fixture(root, plan, small_lossless_crops=True)
            before = {path.name: path.read_bytes() for path in root.glob("*.png")}
            output, receipt_path = root / "small-layout.png", root / "small-layout.json"
            rect = [4, 443, 100, 520]  # Outside p2's crop, still in its verified original sheet.
            result = assembler.assemble_model_annotation_layout(json.dumps(plan).encode(), project_root=root,
                panel_ids=["p1", "p2", "p3"], columns=3, cell_size=(512, 460),
                legend_crop={"panel_id": "p2", "source": "source_sheet", "rect": rect}, output_path=output, receipt_path=receipt_path)
            self.assertEqual(result["status"], "assembled", result)
            self.assertIsNotNone(result["legend"]["source_extraction_receipt"])
            with assembler.Image.open(root / "model-annotated-board.png") as source, assembler.Image.open(output) as page:
                self.assertEqual(page.crop(tuple(result["legend"]["placed_rect"])).convert("RGBA").tobytes(), source.crop(tuple(rect)).convert("RGBA").tobytes())
            self.assertTrue(all((root / name).read_bytes() == payload for name, payload in before.items()))
            self.bind_layout_review(root, plan, result, receipt_path)
            self.assertEqual(assembler.storyboard_coverage.validate_motion_planning(plan, root)["status"], "valid")
            plan["motion_planning"]["boards"].insert(0, copy.deepcopy(plan["motion_planning"]["boards"][0]))
            blocked = assembler.assemble_model_annotation_layout(json.dumps(plan).encode(), project_root=root,
                panel_ids=["p1", "p2", "p3"], columns=3,
                legend_crop={"panel_id": "p2", "source": "source_sheet", "rect": rect},
                output_path=root / "ambiguous.png", receipt_path=root / "ambiguous.json")
            self.assertEqual(blocked["status"], "blocked")
            self.assertIn("layout_legend_source_sheet_missing_or_ambiguous", blocked["errors"])

    def test_layout_cli_accepts_spaced_ids_and_rejects_manual_or_unknown_legend_sources(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); plan = self.model_panel_coverage(root)
            coverage_path = root / "coverage.json"; coverage_path.write_text(json.dumps(plan))
            legend_path = root / "legend.json"; legend_path.write_text(json.dumps({"panel_id": "p1", "rect": [0, 0, 100, 80]}))
            proc = subprocess.run([sys.executable, str(ROOT / "scripts/dircreative_storyboard_page_assembler.py"),
                "--coverage", str(coverage_path), "--project-root", str(root), "--panel-ids", "p1", "p2",
                "--columns", "2", "--layout-only", "--cell-size", "512x460", "--legend-crop", str(legend_path),
                "--output", str(root / "cli.png"), "--receipt", str(root / "cli.json")], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse(json.loads(proc.stdout)["generated"])
            for case in ("manual", "hash", "unknown_legend", "no_bound_source_sheet"):
                with self.subTest(case=case):
                    current = copy.deepcopy(plan); legend = None
                    if case == "manual": current["panels"][0]["planning_image"]["annotation_source"] = "manual_overlay"
                    elif case == "hash": current["panels"][0]["planning_image"]["sha256"] = "0" * 64
                    elif case == "unknown_legend": legend = {"panel_id": "not-bound", "rect": [0, 0, 10, 10]}
                    else: legend = {"panel_id": "p1", "source": "source_sheet", "rect": [0, 0, 10, 10]}
                    output, receipt = root / f"{case}.png", root / f"{case}.json"
                    result = assembler.assemble_model_annotation_layout(json.dumps(current).encode(), project_root=root,
                        panel_ids=["p1", "p2"], columns=2, legend_crop=legend, output_path=output, receipt_path=receipt)
                    self.assertEqual(result["status"], "blocked", result)
                    self.assertFalse(output.exists())
                    self.assertFalse(receipt.exists())


    def coverage(self, root: Path, count: int = 9) -> dict:
        shot_count = (count + 2) // 3
        cards = {"cards": [
            {"shot_id": f"S{index + 1:02d}", "timecode": f"00:{index * 3:02d}-00:{(index + 1) * 3:02d}"}
            for index in range(shot_count)
        ]}
        (root / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
        panels = []
        for index in range(count):
            image_path = root / f"line-{index}.png"
            size = (1200, 680) if index % 2 == 0 else (680, 1200)
            image = assembler.Image.new("RGB", size, "white")
            drawer = assembler.ImageDraw.Draw(image)
            drawer.rectangle((2, 2, size[0] - 3, size[1] - 3), outline="black", width=2)
            drawer.line((20 + index * 12, 30, 120 + index * 12, 90), fill="black", width=3)
            image.save(image_path, format="PNG")
            payload = image_path.read_bytes()
            annotations = [
                {"kind": "actor_path", "subject": "角色", "label": "前进", "points": [[.1, .2], [.7, .7]]},
                {"kind": "action", "subject": "手", "label": "挥动", "points": [[.2, .8], [.5, .4], [.8, .7]]},
                ({"kind": "camera", "subject": "摄影机", "label": "固定", "stationary": True}
                 if index == 0 else {"kind": "camera", "subject": "摄影机", "label": "推近", "points": [[.1, .5], [.8, .5]]}),
            ]
            panels.append({
                "panel_id": f"p{index + 1}", "shot_id": f"S{index // 3 + 1:02d}", "requirement_id": "action", "phase": f"phase-{index + 1}",
                "at_seconds": (index // 3) * 3 + (index % 3) + 0.5, "state": f"动作状态 {index + 1}", "camera_setup": "中景，固定机位", "view_subject": "角色", "gaze_target": "目标", "axis_id": "axis", "axis_side": "north", "look_direction": "left", "image": {"status": "planned"}, "motion_annotations": annotations,
                "planning_image": {"status": "available", "presentation": "line_art", "path": image_path.name, "sha256": hashlib.sha256(payload).hexdigest()},
            })
        return {"schema_version": "1.0", "project_id": "fixture", "frame_rate_fps": 24, "scope": "whole_film", "shot_cards_file": "cards.json", "shot_cards_sha256": assembler.storyboard_coverage.json_hash(cards), "requirements": [{"requirement_id": "action", "source_anchor": "fixture", "kind": "action", "shot_ids": [f"S{index + 1:02d}" for index in range(shot_count)], "phases": [f"phase-{index + 1}" for index in range(count)], "risk": "medium", "image_required": False}], "panels": panels}

    def test_motion_font_proves_cjk_glyphs_when_available(self):
        font = assembler._motion_font(24)
        if font is not None:
            self.assertTrue(assembler._font_has_glyphs(font, assembler.MOTION_CJK_TEXT))
        else:
            # CJK-free CI remains supported: rendering is explicitly tool-blocked below.
            self.assertIsNone(font)

    def test_missing_glyph_font_is_not_accepted_as_cjk_font(self):
        class MissingGlyphFont:
            def getmask(self, _text):
                return b"tofu"

        self.assertFalse(assembler._font_has_glyphs(MissingGlyphFont(), assembler.MOTION_CJK_TEXT))
        with mock.patch.object(assembler.ImageFont, "truetype", return_value=MissingGlyphFont()):
            self.assertIsNone(assembler._motion_font(24))

    def test_assembles_nine_contained_annotated_panels(self):
        if assembler._motion_font(24) is None:
            self.skipTest("no verified CJK font; motion rendering must tool-block")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            coverage = self.coverage(root)
            payload = json.dumps(coverage, ensure_ascii=False).encode()
            output, receipt_path = root / "board.png", root / "board.json"
            receipt = assembler.assemble_motion_board(payload, project_root=root, panel_ids=[f"p{i}" for i in range(1, 10)], columns=3, output_path=output, receipt_path=receipt_path)
            with assembler.Image.open(output) as result:
                self.assertGreaterEqual(max(result.size), 2400)
                # The white letterbox around alternating source aspect ratios proves contain, not crop/stretch.
                self.assertEqual(result.getpixel((receipt["panels"][0]["image_rect"]["left"] - 1, receipt["panels"][0]["image_rect"]["top"])), (255, 255, 255))
                rect = receipt["panels"][0]["image_rect"]
                # This point is inside an otherwise blank source image and lies on the actor-path arrow.
                midpoint = (int(rect["left"] + .5 * (rect["right"] - rect["left"])), int(rect["top"] + .533 * (rect["bottom"] - rect["top"])))
                self.assertTrue(any(result.getpixel((midpoint[0] + dx, midpoint[1] + dy)) == (0, 0, 0) for dx in range(-3, 4) for dy in range(-3, 4)))
            self.assertEqual(receipt["status"], "assembled")
            self.assertEqual(receipt["visual_quality"], "unverified")
            self.assertEqual(len(receipt["panels"]), 9)
            self.assertEqual(receipt["layout"]["columns"], 3)
            self.assertTrue(any(item["motion_annotations"][0]["label"] == "前进" for item in receipt["panels"]))
            self.assertEqual(receipt["output_sha256"], hashlib.sha256(output.read_bytes()).hexdigest())

    def test_bad_motion_coordinates_are_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            coverage = self.coverage(root, 1)
            coverage["panels"][0]["motion_annotations"][0]["points"][0] = [1.2, .2]
            output, receipt_path = root / "bad.png", root / "bad.json"
            result = assembler.assemble_motion_board(json.dumps(coverage).encode(), project_root=root, panel_ids=["p1"], columns=1, output_path=output, receipt_path=receipt_path)
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(output.exists())
            self.assertFalse(receipt_path.exists())

    def test_planning_image_sha_mismatch_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            coverage = self.coverage(root, 1)
            coverage["panels"][0]["planning_image"]["sha256"] = "0" * 64
            output, receipt_path = root / "bad.png", root / "bad.json"
            result = assembler.assemble_motion_board(json.dumps(coverage).encode(), project_root=root, panel_ids=["p1"], columns=1, output_path=output, receipt_path=receipt_path)
            self.assertEqual(result["status"], "blocked")
            self.assertTrue(any("motion_drawing_binding_invalid:p1" in item for item in result["errors"]))
            self.assertFalse(output.exists())

    def test_no_verified_cjk_font_blocks_without_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            coverage = self.coverage(root, 1)
            output, receipt_path = root / "blocked.png", root / "blocked.json"
            with mock.patch.object(assembler, "_motion_font", return_value=None):
                result = assembler.assemble_motion_board(
                    json.dumps(coverage).encode(), project_root=root, panel_ids=["p1"],
                    columns=1, output_path=output, receipt_path=receipt_path,
                )
            self.assertEqual(result["status"], "TOOL_BLOCKED")
            self.assertIn("motion_cjk_font_unavailable", result["errors"])
            self.assertFalse(output.exists())
            self.assertFalse(receipt_path.exists())

    def test_model_generated_panels_are_not_redrawn_by_manual_overlay_assembler(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            coverage = self.coverage(root, 1)
            coverage["panels"][0]["planning_image"]["annotation_source"] = "model_generated"
            output, receipt_path = root / "must-not-overlay.png", root / "must-not-overlay.json"
            with mock.patch.object(assembler.storyboard_coverage, "validate", return_value={"status": "valid", "errors": []}), mock.patch.object(assembler.storyboard_coverage, "validate_motion_planning", return_value={"status": "valid", "errors": [], "missing": []}):
                result = assembler.assemble_motion_board(
                    json.dumps(coverage).encode(), project_root=root, panel_ids=["p1"],
                    columns=1, output_path=output, receipt_path=receipt_path,
                )
            self.assertEqual(result["status"], "blocked")
            self.assertIn("motion_model_generated_board_preserved_without_overlay", result["errors"])
            self.assertFalse(output.exists())

    def test_legacy_approved_frame_assembly_still_uses_its_old_gate(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            plan, target = StoryboardPageAssemblerTests().prepared_plan(root)
            parent = next(item for item in plan["assets"] if item["asset_id"] == target["inherits_from"][0])
            parent["visual_qa_receipt"] = None
            result = assembler.assemble((json.dumps(plan) + "\n").encode(), base_dir=root, asset_id=target["asset_id"], output_path=root / "old.png", receipt_path=root / "old.json")
            self.assertEqual(result["status"], "blocked")
            self.assertTrue(any("parent_frame_visual_review_invalid" in item for item in result["errors"]))


@unittest.skipUnless(assembler.Image is not None, "Pillow is required for sheet extraction")
class SheetExtractionTests(unittest.TestCase):
    def source_and_map(self, root: Path) -> tuple[Path, Path, dict]:
        source = root / "source.png"
        image = assembler.Image.new("RGB", (100, 100), "white")
        draw = assembler.ImageDraw.Draw(image)
        draw.rectangle((0, 0, 49, 19), fill=(220, 10, 10))
        draw.rectangle((0, 70, 49, 99), fill=(10, 10, 220))
        draw.rectangle((50, 40, 99, 69), fill=(10, 180, 10))
        image.save(source, format="PNG")
        cell_map = {
            "sheet_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "cells": [
                {"panel_id": "P04", "rect": [0, 0, 50, 20]},
                {"panel_id": "P09", "rect": [0, 70, 50, 100]},
                {"panel_id": "P02", "rect": [50, 40, 100, 70]},
            ],
        }
        map_path = root / "cells.json"
        map_path.write_text(json.dumps(cell_map), encoding="utf-8")
        return source, map_path, cell_map

    def extract(self, root: Path, source: Path, cell_map: Path):
        output_dir = root / "out"
        output_dir.mkdir()
        return assembler.extract_clean_sheet(
            sheet_path=source, cell_map_path=cell_map, output_dir=output_dir,
            receipt_path=output_dir / "receipt.json",
        ), output_dir

    def test_extracts_explicit_nonsequential_top_left_cells_without_transform(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source, map_path, _cell_map = self.source_and_map(root)
            receipt, output_dir = self.extract(root, source, map_path)
            self.assertEqual(receipt["status"], "extracted")
            self.assertEqual([cell["panel_id"] for cell in receipt["cells"]], ["P04", "P09", "P02"])
            self.assertEqual([cell["rect"] for cell in receipt["cells"]], [[0, 0, 50, 20], [0, 70, 50, 100], [50, 40, 100, 70]])
            expected = {"P04": ((50, 20), (220, 10, 10)), "P09": ((50, 30), (10, 10, 220)), "P02": ((50, 30), (10, 180, 10))}
            for panel_id, (size, color) in expected.items():
                with assembler.Image.open(output_dir / f"{panel_id}.clean.png") as extracted:
                    self.assertEqual(extracted.size, size)
                    self.assertEqual(extracted.getpixel((3, 3)), color)
            self.assertEqual(receipt["coordinate_system"], "source_png_top_left_pixels_half_open")

    def test_rejects_bad_sheet_hash_before_writing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source, map_path, cell_map = self.source_and_map(root)
            cell_map["sheet_sha256"] = "0" * 64
            map_path.write_text(json.dumps(cell_map), encoding="utf-8")
            receipt, output_dir = self.extract(root, source, map_path)
            self.assertEqual(receipt["status"], "blocked")
            self.assertIn("sheet_map_sha256_mismatch", receipt["errors"])
            self.assertEqual(list(output_dir.iterdir()), [])

    def test_rejects_out_of_bounds_duplicate_and_overlapping_cells(self):
        cases = {
            "outside": [{"panel_id": "P04", "rect": [0, 0, 101, 20]}],
            "duplicate": [{"panel_id": "P04", "rect": [0, 0, 50, 20]}, {"panel_id": "P04", "rect": [50, 20, 100, 40]}],
            "overlap": [{"panel_id": "P04", "rect": [0, 0, 50, 50]}, {"panel_id": "P09", "rect": [25, 25, 75, 75]}],
        }
        for name, cells in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                source, map_path, cell_map = self.source_and_map(root)
                cell_map["cells"] = cells
                map_path.write_text(json.dumps(cell_map), encoding="utf-8")
                receipt, output_dir = self.extract(root, source, map_path)
                self.assertEqual(receipt["status"], "blocked")
                self.assertEqual(list(output_dir.iterdir()), [])

    def test_existing_clean_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source, map_path, _cell_map = self.source_and_map(root)
            output_dir = root / "out"
            output_dir.mkdir()
            existing = output_dir / "P04.clean.png"
            existing.write_bytes(b"user-owned")
            result = assembler.extract_clean_sheet(
                sheet_path=source, cell_map_path=map_path, output_dir=output_dir,
                receipt_path=output_dir / "receipt.json",
            )
            self.assertEqual(result["status"], "blocked")
            self.assertIn("sheet_output_or_receipt_must_be_new", result["errors"])
            self.assertEqual(existing.read_bytes(), b"user-owned")


if __name__ == "__main__":
    unittest.main()
