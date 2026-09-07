from __future__ import annotations

import copy
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_pre_video_assets_gate as gate  # noqa: E402
import dircreative_visual_asset_plan as visual  # noqa: E402
import dircreative_character_master_visual_gate as character_gate  # noqa: E402
import dircreative_storyboard_coverage as coverage  # noqa: E402
import dircreative_prompt_compiler as prompt_compiler  # noqa: E402


class PreVideoAssetsGateTests(unittest.TestCase):
    def planned_plan(self) -> dict:
        path = ROOT / "tests/fixtures/visual-asset-plan/valid-coverage-unit.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def storyboard_coverage(
        self,
        root: Path,
        plan: dict,
        files_by_shot: dict[str, str],
    ) -> dict:
        cards = json.loads((root / plan["shot_cards_file"]).read_text(encoding="utf-8"))
        requirements = []
        panels = []
        for index, card in enumerate(cards["cards"]):
            shot_id = card["shot_id"]
            start, _end = coverage.parse_timecode(card["timecode"])
            assert start is not None
            requirement_id = f"requirement-{shot_id}"
            phases = ["approach", "contact", "result"] if index == 0 else ["hold"]
            requirements.append(
                {
                    "requirement_id": requirement_id,
                    "source_anchor": f"shot-cards:{shot_id}",
                    "kind": "action" if index == 0 else "hold",
                    "shot_ids": [shot_id],
                    "phases": phases,
                    "risk": "medium",
                    "image_required": index == 0,
                }
            )
            for phase_index, phase in enumerate(phases):
                if index == 0 and phase_index == 0:
                    image_path = root / files_by_shot[shot_id]
                    image_relative_path = files_by_shot[shot_id]
                    state = f"{shot_id}-{phase}-state"
                elif index == 0:
                    image_path = root / f"coverage-{shot_id}-{phase}.png"
                    image_path.write_bytes(visual.test_png_bytes(100 + phase_index))
                    image_relative_path = image_path.name
                    state = f"{shot_id}-{phase}-state"
                else:
                    image_path = root / files_by_shot[shot_id]
                    image_relative_path = files_by_shot[shot_id]
                    state = f"{shot_id}-state"
                image_hash = coverage.hashlib.sha256(image_path.read_bytes()).hexdigest()
                panels.append(
                    {
                        "panel_id": f"panel-{shot_id}-{phase}",
                        "shot_id": shot_id,
                        "requirement_id": requirement_id,
                        "phase": phase,
                        "at_seconds": start + 0.5 + phase_index,
                        "state": state,
                        "camera_setup": f"camera-{shot_id}-{phase}",
                        "view_subject": "fighter",
                        "gaze_target": "opponent",
                        "axis_id": "duel-axis",
                        "axis_side": "north",
                        "look_direction": "left",
                        "image": {
                            "status": "available",
                            "path": image_relative_path,
                            "sha256": image_hash,
                        },
                    }
                )
        return {
            "schema_version": coverage.SCHEMA_VERSION,
            "project_id": plan["project_id"],
            "frame_rate_fps": 25,
            "scope": plan["scope"],
            "shot_cards_file": plan["shot_cards_file"],
            "shot_cards_sha256": plan["shot_cards_sha256"],
            "requirements": requirements,
            "panels": panels,
        }

    @staticmethod
    def write_design_coverage(root: Path, storyboard_coverage: dict) -> dict[str, str]:
        design = copy.deepcopy(storyboard_coverage)
        for panel in design["panels"]:
            panel["image"] = {"status": "planned"}
        path = root / "design-coverage.json"
        payload = (json.dumps(design, ensure_ascii=False, sort_keys=True) + "\n").encode()
        path.write_bytes(payload)
        return {"relative_path": path.name, "sha256": hashlib.sha256(payload).hexdigest()}

    @staticmethod
    def write_assets_coverage(root: Path, storyboard_coverage: dict) -> tuple[Path, str]:
        path = root / "assets-coverage.json"
        payload = (json.dumps(storyboard_coverage, ensure_ascii=False, sort_keys=True) + "\n").encode()
        path.write_bytes(payload)
        return path, hashlib.sha256(payload).hexdigest()

    def storyboard_handoffs(
        self,
        storyboard_coverage: dict,
        design_binding: dict[str, str],
    ) -> list[dict]:
        requirements = {
            item["requirement_id"]: item
            for item in storyboard_coverage["requirements"]
            if item["kind"] == "action" and item["image_required"] is True
        }
        panels = [
            panel
            for panel in storyboard_coverage["panels"]
            if panel["requirement_id"] in requirements
        ]
        return [
            {
                "contract_id": "storyboard_frame_to_jingzao_v1",
                "fixture_only": False,
                "frames": [
                    {
                        "frame_id": panel["panel_id"],
                        "shot_id": panel["shot_id"],
                        "panel_context": {
                            "coverage_file": design_binding["relative_path"],
                            "coverage_sha256": design_binding["sha256"],
                            "panel_id": panel["panel_id"],
                            "phase": panel["phase"],
                            "at_seconds": panel["at_seconds"],
                            "state": panel["state"],
                        },
                    }
                    for panel in panels
                ],
                "delivery_consumption": {
                    "status": "observed_unverified",
                    "frame_outputs": [
                        {
                            "frame_id": panel["panel_id"],
                            "generated_artifact": {
                                "relative_path": panel["image"]["path"],
                                "sha256": panel["image"]["sha256"],
                            },
                        }
                        for panel in panels
                    ],
                },
            }
        ]

    @staticmethod
    def annotated_structure_probe() -> dict:
        """Boundary data for the character receipt, not a vision implementation mock."""
        bodies = [
            {
                "center_x": 0.38 + index * 0.14,
                "joint_span": 0.66,
                "subject_height": 0.80,
                "min_y": 0.08,
                "max_y": 0.86,
                "head_extent_above_shoulders": 0.11,
                "subject_top_clearance": 0.04,
                "subject_bottom_clearance": 0.04,
                "visible_wrist_count": 2,
                "visible_elbow_count": 2,
                "visible_upper_limb_joint_count": 4,
                "human_rect_index": index,
                "human_rect_min_x": 0.33 + index * 0.14,
                "human_rect_max_x": 0.43 + index * 0.14,
            }
            for index in range(4)
        ]
        return {
            "backend": "apple-vision-human-body-pose-v1",
            "body_pose_count": 5,
            "face_count": 4,
            "faces": [],
            "human_rectangle_count": 4,
            "full_body_count": 4,
            "full_bodies": bodies,
            "left_closeup_face_count": 1,
            "left_closeup_faces": [{"center_x": 0.15, "center_y": 0.55, "width": 0.18, "height": 0.28}],
            "left_portrait_subject_height": 0.82,
            "right_face_count": 3,
            "right_full_height_component_count": 4,
            "right_full_height_components": bodies,
        }

    def prepared_annotated_reference_fixture(self, root: Path, *, acquisition: str = "native_generate") -> dict:
        """Build bounded fixture evidence; PNGs exercise bindings, not image generation or visual acceptance."""
        import dircreative_storyboard_page_assembler as board_assembler

        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        for name in (
            "valid-coverage-unit-inventory.json",
            "valid-coverage-unit-creative-source.json",
            "valid-coverage-unit-shot-cards.json",
        ):
            shutil.copy2(fixture_root / name, root / name)
        inventory_path = root / "valid-coverage-unit-inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory["generation_units"][0]["storyboard_strategy"] = "annotated_reference"
        if acquisition != "native_generate":
            inventory["generation_units"][0]["storyboard_acquisition"] = acquisition
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        plan = visual.derive_plan(inventory, inventory_file=inventory_path.name, base_dir=root)

        board_asset = next(
            asset for asset in plan["assets"]
            if asset["asset_id"] == "annotated-storyboard-unit-G01"
        )
        board_path = root / f"{board_asset['asset_id']}.png"
        sheet = board_assembler.Image.new("RGB", (1280, 720), "white")
        drawing = board_assembler.ImageDraw.Draw(sheet)
        for index, color in enumerate(((220, 40, 40), (40, 220, 40), (40, 40, 220), (220, 140, 40))):
            left, top = (index % 2) * 640, (index // 2) * 360
            drawing.rectangle((left, top, left + 639, top + 359), fill=color)
            drawing.line((left + 30, top + 40, left + 580, top + 300), fill="black", width=8)
        sheet.save(board_path, format="PNG")

        files_by_asset: dict[str, str] = {}
        seed = 1
        for asset in plan["assets"]:
            target = root / f"{asset['asset_id']}.png"
            if asset["asset_id"] == board_asset["asset_id"]:
                target = board_path
            elif asset["role"] in visual.DIRECT_ROLES:
                target.write_bytes((root / files_by_asset[asset["inherits_from"][0]]).read_bytes())
            else:
                target.write_bytes(visual.test_png_bytes(seed))
                seed += 1
            asset["status"] = "generated_candidate"
            asset["generated_file"] = target.name
            files_by_asset[asset["asset_id"]] = target.name

        files_by_shot = {
            shot_id: files_by_asset.get(f"storyboard-frame-{shot_id}", board_path.name)
            for shot_id in plan["shot_ids"]
        }
        storyboard_coverage = self.storyboard_coverage(root, plan, files_by_shot)
        annotated_panels = [
            panel for panel in storyboard_coverage["panels"]
            if panel["shot_id"] in {"S01", "S02"}
        ]
        board_hash = hashlib.sha256(board_path.read_bytes()).hexdigest()
        cells = [
            {
                "panel_id": panel["panel_id"],
                "rect": [(index % 2) * 640, (index // 2) * 360, (index % 2 + 1) * 640, (index // 2 + 1) * 360],
            }
            for index, panel in enumerate(annotated_panels)
        ]
        cell_map = root / "annotated-board-cells.json"
        cell_map.write_text(json.dumps({"sheet_sha256": board_hash, "cells": cells}), encoding="utf-8")
        extraction = board_assembler.extract_clean_sheet(
            sheet_path=board_path,
            cell_map_path=cell_map,
            output_dir=root,
            receipt_path=root / "annotated-board-cells.receipt.json",
        )
        self.assertEqual(extraction["status"], "extracted", extraction)
        extracted = {item["panel_id"]: item for item in extraction["cells"]}
        kinds = ("action", "lighting", "environment", "camera")
        for panel, kind in zip(annotated_panels, kinds):
            item = extracted[panel["panel_id"]]
            panel["image"] = {"status": "planned"}
            panel["planning_image"] = {
                "status": "available", "presentation": "line_art", "annotation_source": "model_generated",
                "path": item["output_relative_path"], "sha256": item["output_sha256"],
            }
            panel["motion_annotations"] = [{"kind": kind, "subject": "model visual cue", "label": f"{kind} baked into board"}]
        review = root / "annotated-board-review.md"
        review.write_text("Fixture binding only; visual quality remains unverified.", encoding="utf-8")
        storyboard_coverage["motion_planning"] = {
            "reason": "generated annotated board supplies the unit planning evidence",
            "panel_ids": [panel["panel_id"] for panel in annotated_panels],
            "legend": {kind: {"color": color, "label": kind} for kind, color in zip(kinds, ("red", "green", "blue", "orange"))},
            "boards": [{
                "annotation_source": "model_generated",
                "panel_ids": [panel["panel_id"] for panel in annotated_panels],
                "image": {"path": board_path.name, "sha256": board_hash},
                "receipt": {"path": "annotated-board-cells.receipt.json", "sha256": hashlib.sha256((root / "annotated-board-cells.receipt.json").read_bytes()).hexdigest()},
            }],
            "review": {"status": "reviewed", "kind": "ai", "path": review.name, "sha256": hashlib.sha256(review.read_bytes()).hexdigest(), "inputs_sha256": "pending"},
        }
        if acquisition == "assembled_model_panels":
            layout_path = root / "assembled-annotated.png"
            layout_receipt_path = root / "assembled-annotated.receipt.json"
            laid_out = board_assembler.assemble_model_annotation_layout(
                json.dumps(storyboard_coverage).encode(), project_root=root,
                panel_ids=[panel["panel_id"] for panel in annotated_panels], columns=2, cell_size=(640, 360),
                output_path=layout_path, receipt_path=layout_receipt_path,
            )
            self.assertEqual(laid_out["status"], "assembled", laid_out)
            storyboard_coverage["motion_planning"]["boards"].append({
                "annotation_source": "model_generated", "acquisition": "assembled_model_panels",
                "panel_ids": [panel["panel_id"] for panel in annotated_panels],
                "image": {"path": layout_path.name, "sha256": laid_out["output_sha256"]},
                "receipt": {"path": layout_receipt_path.name, "sha256": hashlib.sha256(layout_receipt_path.read_bytes()).hexdigest()},
            })
            board_asset["generated_file"] = layout_path.name
            board_path, board_hash = layout_path, laid_out["output_sha256"]
        storyboard_coverage["motion_planning"]["review"]["inputs_sha256"] = coverage.motion_review_sha256(storyboard_coverage)

        checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = visual.stamp_plan_evidence(plan, base_dir=root, checked_at=checked_at)
        evidence_by_asset = {}
        entries = []
        for asset in plan["assets"]:
            evidence, reason = visual.inspect_raster(root / asset["generated_file"])
            self.assertIsNone(reason)
            assert evidence is not None
            evidence_by_asset[asset["asset_id"]] = evidence
            entries.append({
                "asset_id": asset["asset_id"], "role": asset["role"], "file_sha256": evidence["sha256"],
                "pixel_sha256": evidence["pixel_sha256"], "truth_sha256": asset["truth_sha256"],
                "rubric_id": visual.visual_review_rubric_id(asset["role"]),
                "rubric": {"truth_and_role_match": True, "coverage_and_continuity_match": True, "composition_readable": True, "artifact_free": True, "downstream_use_fit": True},
                "decision": "pass", "notes": "Independent fixture review covers bound pixels only.",
            })
        subject = visual.visual_review_subject_sha256(plan)
        manifest = {
            "schema_version": visual.VISUAL_REVIEW_MANIFEST_VERSION, "ruleset": visual.VISUAL_QA_RULESET,
            "review_subject_sha256": subject, "reviewed_at": checked_at, "reviewer_type": "independent_ai",
            "reviewer_id": "pre-video-gate-fixture-reviewer", "review_task_id": "annotated-public-gate",
            "assets": entries,
        }
        manifest_path = root / "visual-review-manifest.json"
        visual.atomic_write_json(manifest_path, manifest)
        manifest_sha = visual.sha256_file(manifest_path)
        probe = self.annotated_structure_probe()
        for asset in plan["assets"]:
            evidence = evidence_by_asset[asset["asset_id"]]
            receipt = {
                "receipt_version": visual.VISUAL_QA_RECEIPT_VERSION, "asset_id": asset["asset_id"],
                "file_sha256": evidence["sha256"], "pixel_sha256": evidence["pixel_sha256"],
                "truth_sha256": asset["truth_sha256"], "ruleset": visual.VISUAL_QA_RULESET,
                "reviewed_at": checked_at, "reviewer_type": "independent_ai", "reviewer_id": manifest["reviewer_id"],
                "review_task_id": manifest["review_task_id"], "review_manifest_file": manifest_path.name,
                "review_manifest_sha256": manifest_sha, "review_subject_sha256": subject, "status": "visual_qa_pass",
            }
            receipt["receipt_sha256"] = visual.receipt_sha256(receipt)
            asset["visual_qa_receipt"] = receipt
            if asset["role"] == "character_identity_reference":
                with mock.patch.object(character_gate, "swift_tool_identity", return_value={"path": "/fixture/swift", "sha256": "f" * 64, "signature_policy": "fixture"}):
                    structure_receipt = character_gate.make_receipt(
                        asset_id=asset["asset_id"], asset_truth_sha256=asset["truth_sha256"], image_evidence=evidence,
                        probe=probe, checked_at=checked_at, mode="headed_master",
                    )
                visual.atomic_write_json((root / asset["generated_file"]).with_suffix(".character-master-visual.json"), structure_receipt)
        plan["completion_claim"] = "plan_complete"

        prompt = json.loads((ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json").read_text(encoding="utf-8"))
        blocks = []
        for index in range(6):
            block = copy.deepcopy(prompt["shot_blocks"][index // 2])
            block["shot_id"] = f"S{index + 1:02d}"
            block["time_start"] = f"{index * 5:02d}.00"
            block["time_end"] = f"{(index + 1) * 5:02d}.00"
            blocks.append(block)
        prompt["shot_blocks"] = blocks
        for index, unit in enumerate(prompt["generation_plan"]["units"]):
            unit["unit_id"] = f"G{index + 1:02d}"
            unit["shot_ids"] = [f"S{index * 2 + 1:02d}", f"S{index * 2 + 2:02d}"]
        prompt["intake"]["supplied_assets"].append({
            "asset_id": "annotated_board", "source_kind": "project_file", "source_locator": board_path.name,
            "source_hash": board_hash, "source_authorization": "project_owned", "role": "storyboard_motion", "locked": True,
            "reuse_action": "direct_reference", "preserve": ["shot order"], "may_change": ["cinematic rendering"],
            "do_not_copy_or_animate": ["labels", "arrows", "legend"], "downstream_slots": ["@Image 3"],
        })
        prompt["references"].append({
            "platform_slot": "@Image 3", "asset_id": "annotated_board",
            "role": "annotated storyboard motion reference for shot order and camera path", "direct_input_policy": "conditional",
            "attached_to_run": True, "required_for_shot": True, "preserve": ["shot order"],
            "anti_misread": ["do not render labels, arrows, legend, borders, or panels"],
        })
        prompt_compiler.validate_prompt_ir(prompt, verify_project_files=True, project_root=root)
        return {"plan": plan, "storyboard_coverage": storyboard_coverage, "prompt": prompt, "probe": probe}

    def evaluate_annotated_fixture(self, root: Path, prepared: dict) -> dict:
        with mock.patch.object(character_gate, "run_probe", return_value=(prepared["probe"], None)), mock.patch.object(
            character_gate, "swift_tool_identity", return_value={"path": "/fixture/swift", "sha256": "f" * 64, "signature_policy": "fixture"}
        ):
            return gate.evaluate(
                prepared["plan"], base_dir=root, media_scope="pre_video_assets",
                image_generation_authorized=True, video_generation_authorized=False,
                storyboard_coverage=prepared["storyboard_coverage"], prompt_irs=[(root / "prompt-ir.json", prepared["prompt"])],
            )

    def test_annotated_reference_public_gate_reaches_review_without_legacy_frames(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prepared = self.prepared_annotated_reference_fixture(root)
            plan = prepared["plan"]
            result = self.evaluate_annotated_fixture(root, prepared)

        self.assertEqual(result["status"], "ready_for_user_review")
        self.assertTrue(result["generated_asset_set_complete"])
        self.assertFalse(result["visual_assets_complete"])
        self.assertEqual(result["validation_errors"], [])
        self.assertFalse(any(
            asset["role"] == "storyboard_frame"
            and asset["coverage"]["generation_unit_ids"] == ["G01"]
            for asset in plan["assets"]
        ))
        self.assertEqual(
            [asset["asset_id"] for asset in plan["assets"] if asset["role"] == "professional_storyboard_motion_map" and asset["coverage"]["generation_unit_ids"] == ["G01"]],
            ["annotated-storyboard-unit-G01"],
        )

    def test_explicit_model_panel_layout_reaches_user_review_without_claiming_native_page_generation(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prepared = self.prepared_annotated_reference_fixture(root, acquisition="assembled_model_panels")
            board = next(asset for asset in prepared["plan"]["assets"] if asset["asset_id"] == "annotated-storyboard-unit-G01")
            self.assertEqual(board["action"], "assemble")
            self.assertEqual(board["compile_route"], "deterministic_assembly")
            result = self.evaluate_annotated_fixture(root, prepared)
            self.assertEqual(result["status"], "ready_for_user_review", result)
            self.assertFalse(result["visual_assets_complete"])

    def test_layout_path_keeps_review_prompt_and_mixed_unit_requirements(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            baseline = self.prepared_annotated_reference_fixture(root, acquisition="assembled_model_panels")
            for case in ("missing_review", "missing_layout_receipt", "other_unit_frame", "clean_input", "prompt_hash", "native_masquerade"):
                with self.subTest(case=case):
                    prepared = copy.deepcopy(baseline)
                    if case == "missing_review": prepared["storyboard_coverage"]["motion_planning"].pop("review")
                    elif case == "missing_layout_receipt": prepared["storyboard_coverage"]["motion_planning"]["boards"][-1].pop("receipt")
                    elif case in {"other_unit_frame", "clean_input"}:
                        asset_id = "storyboard-frame-S03" if case == "other_unit_frame" else "clean-input-G02"
                        next(asset for asset in prepared["plan"]["assets"] if asset["asset_id"] == asset_id)["status"] = "planned"
                    elif case == "prompt_hash":
                        next(asset for asset in prepared["prompt"]["intake"]["supplied_assets"] if asset["role"] == "storyboard_motion")["source_hash"] = "0" * 64
                    else: prepared["storyboard_coverage"]["motion_planning"]["boards"][-1]["acquisition"] = "native_generate"
                    result = self.evaluate_annotated_fixture(root, prepared)
                    self.assertEqual(result["status"], "blocked", result)
                    self.assertFalse(result["visual_assets_complete"])

    def test_panel_layout_acquisition_cannot_be_added_to_individual_frame_strategy(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = ROOT / "tests/fixtures/visual-asset-plan"
            for name in ("valid-coverage-unit-inventory.json", "valid-coverage-unit-creative-source.json", "valid-coverage-unit-shot-cards.json"):
                shutil.copyfile(source / name, root / name)
            path = root / "valid-coverage-unit-inventory.json"
            inventory = json.loads(path.read_text())
            inventory["generation_units"][0]["storyboard_acquisition"] = "assembled_model_panels"
            path.write_text(json.dumps(inventory))
            with self.assertRaisesRegex(ValueError, "input strategy"):
                visual.derive_plan(inventory, inventory_file=path.name, base_dir=root)

    def test_annotated_reference_public_gate_rejects_low_hold_without_board_review_or_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prepared = self.prepared_annotated_reference_fixture(root)
            for requirement in prepared["storyboard_coverage"]["requirements"]:
                if set(requirement["shot_ids"]).issubset({"S01", "S02"}):
                    requirement["kind"] = "hold"
                    requirement["risk"] = "low"
            prepared["storyboard_coverage"]["motion_planning"].pop("review")
            prepared["storyboard_coverage"]["motion_planning"]["boards"][0].pop("receipt")
            result = self.evaluate_annotated_fixture(root, prepared)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason_codes"], ["storyboard_coverage_invalid"])
        self.assertIn("motion_board_binding_invalid:0", result["validation_errors"])

    def test_annotated_reference_public_gate_keeps_other_unit_and_clean_input_requirements(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prepared = self.prepared_annotated_reference_fixture(root)
            missing_other_unit = copy.deepcopy(prepared)
            missing_other_unit["plan"] = copy.deepcopy(prepared["plan"])
            next(
                asset for asset in missing_other_unit["plan"]["assets"]
                if asset["asset_id"] == "storyboard-frame-S03"
            )["status"] = "planned"
            missing_frame_result = self.evaluate_annotated_fixture(root, missing_other_unit)

            missing_clean_input = copy.deepcopy(prepared)
            missing_clean_input["plan"] = copy.deepcopy(prepared["plan"])
            next(
                asset for asset in missing_clean_input["plan"]["assets"]
                if asset["asset_id"] == "clean-input-G02"
            )["status"] = "planned"
            missing_clean_result = self.evaluate_annotated_fixture(root, missing_clean_input)

        for result, asset_id in (
            (missing_frame_result, "storyboard-frame-S03"),
            (missing_clean_result, "clean-input-G02"),
        ):
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason_codes"], ["pre_video_assets_requires_verified_images"])
            self.assertIn(asset_id, result["missing_asset_ids"])

    def test_annotated_low_risk_review_binds_board_panels_without_explicit_selection(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prepared = self.prepared_annotated_reference_fixture(root)
            sidecar = prepared["storyboard_coverage"]
            for requirement in sidecar["requirements"]:
                requirement.update(kind="hold", risk="low")
            planning = sidecar["motion_planning"]
            planning.pop("panel_ids", None)
            original_hash = coverage.motion_review_sha256(sidecar)
            planning["review"]["inputs_sha256"] = original_hash
            self.assertEqual(self.evaluate_annotated_fixture(root, prepared)["status"], "ready_for_user_review")

            sidecar["panels"][0]["state"] = "changed after the bound review"
            sidecar["panels"][0]["motion_annotations"][0]["label"] = "changed motion"
            self.assertNotEqual(coverage.motion_review_sha256(sidecar), original_hash)
            result = self.evaluate_annotated_fixture(root, prepared)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("motion_review_binding_invalid", result["validation_errors"])

    def test_pre_video_assets_requires_coverage_before_all_planned_required_assets(self):
        result = gate.evaluate(
            self.planned_plan(),
            base_dir=ROOT / "tests/fixtures/visual-asset-plan",
            media_scope="pre_video_assets",
            image_generation_authorized=True,
            video_generation_authorized=False,
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["generated_asset_count"], 0)
        self.assertFalse(result["generated_asset_set_complete"])
        self.assertIn("storyboard_coverage_missing", result["reason_codes"])
        self.assertEqual(result["storyboard_coverage_status"], "missing")

    def test_prompt_only_allows_zero_images_without_asset_completion(self):
        result = gate.evaluate(
            self.planned_plan(),
            base_dir=ROOT / "tests/fixtures/visual-asset-plan",
            media_scope="prompt_only",
            image_generation_authorized=False,
            video_generation_authorized=False,
        )
        self.assertEqual(result["status"], "not_applicable")
        self.assertFalse(result["generated_asset_set_complete"])
        self.assertFalse(result["visual_assets_complete"])
        self.assertFalse(result["storyboard_coverage_required"])

    def test_representative_sample_does_not_require_whole_storyboard_coverage(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, root / name)
            inventory_path = root / "valid-coverage-unit-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["scope"] = "representative_sample"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            plan = visual.derive_plan(
                inventory,
                inventory_file=inventory_path.name,
                base_dir=root,
            )
            result = gate.evaluate(
                plan,
                base_dir=root,
                media_scope="pre_video_assets",
                image_generation_authorized=True,
                video_generation_authorized=False,
            )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("pre_video_assets_requires_verified_images", result["reason_codes"])
        self.assertFalse(result["storyboard_coverage_required"])
        self.assertEqual(result["storyboard_coverage_status"], "not_required")

    def test_annotated_reference_unit_uses_one_generated_board_without_legacy_storyboard_frames(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, root / name)
            inventory_path = root / "valid-coverage-unit-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["generation_units"][0]["storyboard_strategy"] = "annotated_reference"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

            plan = visual.derive_plan(
                inventory, inventory_file=inventory_path.name, base_dir=root
            )
            errors, _metrics = visual.validate_plan(plan, base_dir=root)

        self.assertEqual(errors, [])
        annotated_assets = [
            asset for asset in plan["assets"]
            if asset["role"] == "professional_storyboard_motion_map"
            and asset["coverage"]["generation_unit_ids"] == ["G01"]
        ]
        self.assertEqual(len(annotated_assets), 1)
        self.assertEqual(annotated_assets[0]["action"], "generate")
        self.assertEqual(annotated_assets[0]["compile_route"], "selected_skill_handoff")
        self.assertFalse(any(
            asset["role"] == "storyboard_frame"
            and asset["coverage"]["generation_unit_ids"] == ["G01"]
            for asset in plan["assets"]
        ))
        self.assertTrue(any(
            asset["role"] == "storyboard_frame"
            and asset["coverage"]["generation_unit_ids"] == ["G02"]
            for asset in plan["assets"]
        ))
        self.assertTrue(any(
            asset["role"] == "clean_first_frame"
            and asset["coverage"]["generation_unit_ids"] == ["G01"]
            for asset in plan["assets"]
        ))

    def test_annotated_reference_rejects_board_missing_one_unit_shot(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, root / name)
            inventory_path = root / "valid-coverage-unit-inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["generation_units"][0]["storyboard_strategy"] = "annotated_reference"
            plan = visual.derive_plan(
                inventory, inventory_file=inventory_path.name, base_dir=root
            )
            board = next(
                asset for asset in plan["assets"]
                if asset["asset_id"] == "annotated-storyboard-unit-G01"
            )
            board["coverage"]["shot_ids"] = ["S01"]
            errors, _metrics = visual.validate_plan(plan, base_dir=root)

        self.assertIn(
            "annotated_storyboard_unit_coverage_invalid:annotated-storyboard-unit-G01",
            errors,
        )

    def test_annotated_reference_requires_current_model_board_for_exact_unit_panels(self):
        unit = {
            "unit_id": "G01",
            "shot_ids": ["S01", "S02"],
            "storyboard_strategy": "annotated_reference",
        }
        board = {
            "generated_file": "annotated-board.png",
            "generated_sha256": "a" * 64,
        }
        sidecar = {
            "panels": [
                {"panel_id": "p1", "shot_id": "S01"},
                {"panel_id": "p2", "shot_id": "S02"},
            ],
            "motion_planning": {
                "boards": [{
                    "annotation_source": "model_generated",
                    "panel_ids": ["p1", "p2"],
                    "image": {"path": "annotated-board.png", "sha256": "a" * 64},
                }]
            },
        }

        errors = gate.annotated_reference_coverage_errors(unit, board, sidecar)
        sidecar["motion_planning"]["boards"][0]["image"]["sha256"] = "b" * 64
        hash_errors = gate.annotated_reference_coverage_errors(unit, board, sidecar)

        self.assertEqual(errors, [])
        self.assertIn("annotated_storyboard_coverage_board_mismatch:G01", hash_errors)


    def test_annotated_reference_requires_matching_conditional_prompt_ir_attachment(self):
        fixture = ROOT / "tests/fixtures/prompt-system/valid/longform-30s-split.json"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            board = root / "annotated-board.png"
            board.write_bytes(visual.test_png_bytes(17))
            board_hash = hashlib.sha256(board.read_bytes()).hexdigest()
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            payload["intake"]["supplied_assets"].append(
                {
                    "asset_id": "annotated_board",
                    "source_kind": "project_file",
                    "source_locator": board.name,
                    "source_hash": board_hash,
                    "source_authorization": "project_owned",
                    "role": "storyboard_motion",
                    "locked": True,
                    "reuse_action": "direct_reference",
                    "preserve": ["shot order", "action phases", "camera path"],
                    "may_change": ["cinematic rendering"],
                    "do_not_copy_or_animate": ["labels", "arrows", "legend"],
                    "downstream_slots": ["@Image 3"],
                }
            )
            payload["references"].append(
                {
                    "platform_slot": "@Image 3",
                    "asset_id": "annotated_board",
                    "role": "annotated storyboard motion reference for shot order and camera path",
                    "direct_input_policy": "conditional",
                    "attached_to_run": True,
                    "required_for_shot": True,
                    "preserve": ["shot order", "action phases", "camera path"],
                    "anti_misread": ["do not render labels, arrows, legend, borders, or panels"],
                }
            )
            prompt_compiler.validate_prompt_ir(
                payload, verify_project_files=True, project_root=root
            )
            unit = {
                "unit_id": "departure_unit",
                "shot_ids": ["prepare"],
                "storyboard_strategy": "annotated_reference",
            }
            board_asset = {
                "asset_id": "annotated-storyboard-unit-departure_unit",
                "role": "professional_storyboard_motion_map",
                "action": "generate",
                "generated_file": board.name,
                "generated_sha256": board_hash,
                "status": "user_locked",
                "coverage": {"generation_unit_ids": ["departure_unit"], "shot_ids": ["prepare"]},
            }

            errors = gate.annotated_reference_prompt_ir_errors(
                unit, board_asset, payload, prompt_root=root
            )
            gate_errors = gate.annotated_reference_gate_errors(
                {"generation_units": [unit], "assets": [board_asset]},
                prompt_irs=[(root / "prompt-ir.json", payload)],
            )
            missing_prompt_errors = gate.annotated_reference_gate_errors(
                {"generation_units": [unit], "assets": [board_asset]},
                prompt_irs=None,
            )
            payload["references"][-1]["direct_input_policy"] = "planning_only"
            policy_errors = gate.annotated_reference_prompt_ir_errors(
                unit, board_asset, payload, prompt_root=root
            )
            board.write_bytes(visual.test_png_bytes(18))
            byte_errors = gate.annotated_reference_prompt_ir_errors(
                unit, board_asset, payload, prompt_root=root
            )

        self.assertEqual(errors, [])
        self.assertEqual(gate_errors, [])
        self.assertEqual(missing_prompt_errors, ["annotated_prompt_ir_missing"])
        self.assertIn("annotated_prompt_reference_policy_invalid:departure_unit", policy_errors)
        self.assertIn("annotated_prompt_board_bytes_mismatch:departure_unit", byte_errors)

    def test_image_authorization_never_authorizes_video(self):
        result = gate.evaluate(
            self.planned_plan(),
            base_dir=ROOT / "tests/fixtures/visual-asset-plan",
            media_scope="pre_video_assets",
            image_generation_authorized=True,
            video_generation_authorized=True,
        )
        self.assertEqual(result["status"], "invalid")
        self.assertIn("pre_video_assets_must_defer_video_generation", result["reason_codes"])

    def test_cli_rejects_storyboard_coverage_outside_plan_directory(self):
        plan_path = ROOT / "tests/fixtures/visual-asset-plan/valid-coverage-unit.json"
        with tempfile.TemporaryDirectory() as raw:
            outside_coverage = Path(raw) / "coverage.json"
            outside_coverage.write_text("{}", encoding="utf-8")
            output = io.StringIO()
            with mock.patch.object(
                sys,
                "argv",
                [
                    "dircreative_pre_video_assets_gate.py",
                    "--plan",
                    str(plan_path),
                    "--media-scope",
                    "pre_video_assets",
                    "--image-generation-authorized",
                    "--storyboard-coverage",
                    str(outside_coverage),
                ],
            ), redirect_stdout(output):
                exit_code = gate.main()
        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(result["status"], "invalid")
        self.assertIn(
            "storyboard_coverage_file_invalid_or_outside_plan_root",
            result["reason_codes"],
        )

    def test_cli_rejects_absolute_and_relative_storyboard_coverage_symlinks(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            temp_root = Path(raw)
            project = temp_root / "project"
            project.mkdir()
            for name in (
                "valid-coverage-unit.json",
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, project / name)
            outside = temp_root / "outside"
            outside.mkdir()
            (outside / "coverage.json").write_text("{}", encoding="utf-8")
            file_link = project / "coverage-link.json"
            file_link.symlink_to(outside / "coverage.json")
            directory_link = project / "coverage-dir-link"
            directory_link.symlink_to(outside, target_is_directory=True)
            results = []
            for coverage_arg in (
                str(file_link),
                file_link.name,
                f"{directory_link.name}/coverage.json",
            ):
                output = io.StringIO()
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "dircreative_pre_video_assets_gate.py",
                        "--plan",
                        str(project / "valid-coverage-unit.json"),
                        "--media-scope",
                        "pre_video_assets",
                        "--image-generation-authorized",
                        "--storyboard-coverage",
                        coverage_arg,
                    ],
                ), redirect_stdout(output):
                    results.append((gate.main(), json.loads(output.getvalue())))
        for exit_code, result in results:
            self.assertEqual(exit_code, 1)
            self.assertEqual(result["status"], "invalid")
            self.assertIn(
                "storyboard_coverage_file_invalid_or_outside_plan_root",
                result["reason_codes"],
            )

    def test_planned_rows_are_not_counted_as_generated(self):
        plan = self.planned_plan()
        plan["assets"][0]["generated_file"] = "made-up.png"
        result = gate.evaluate(
            plan,
            base_dir=ROOT / "tests/fixtures/visual-asset-plan",
            media_scope="pre_video_assets",
            image_generation_authorized=True,
            video_generation_authorized=False,
        )
        self.assertEqual(result["generated_asset_count"], 0)
        self.assertIn(plan["assets"][0]["asset_id"], result["missing_asset_ids"])

    def test_action_panel_handoffs_require_validated_unique_current_outputs(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, root / name)
            plan = self.planned_plan()
            files_by_shot = {}
            for index, shot_id in enumerate(plan["shot_ids"]):
                path = root / f"{shot_id}.png"
                path.write_bytes(visual.test_png_bytes(index + 1))
                files_by_shot[shot_id] = path.name
            sidecar = self.storyboard_coverage(root, plan, files_by_shot)
            design_binding = self.write_design_coverage(root, sidecar)
            assets_path, assets_hash = self.write_assets_coverage(root, sidecar)
            self.assertNotEqual(design_binding["sha256"], assets_hash)
            sidecar = json.loads(assets_path.read_text(encoding="utf-8"))
            handoffs = self.storyboard_handoffs(sidecar, design_binding)
            handoff_plan = copy.deepcopy(plan)
            representative_asset = next(
                asset
                for asset in handoff_plan["assets"]
                if asset["role"] == "storyboard_frame"
                and asset["coverage"]["shot_ids"] == ["S01"]
            )
            representative_asset.update(
                {
                    "status": "generated_candidate",
                    "generated_file": sidecar["panels"][0]["image"]["path"],
                }
            )
            provider_root = Path("/fixture/provider")
            host_event_log = Path("/fixture/host-events.jsonl")
            with mock.patch.object(
                gate.storyboard_frame_handoff,
                "validate",
                return_value=[],
            ) as validate_handoff:
                valid_errors, valid_missing = gate.storyboard_handoff_errors(
                    handoff_plan,
                    base_dir=root,
                    storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=handoffs,
                    provider_root=provider_root,
                    host_event_log=host_event_log,
                )
                missing_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan,
                    base_dir=root,
                    storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=None,
                    provider_root=provider_root,
                    host_event_log=host_event_log,
                )
                wrong_phase = copy.deepcopy(handoffs)
                wrong_phase[0]["frames"][0]["panel_context"]["phase"] = "wrong"
                wrong_phase_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=wrong_phase,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
                wrong_camera = copy.deepcopy(sidecar)
                wrong_camera["panels"][0]["camera_setup"] = "camera-drift"
                wrong_camera_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=wrong_camera,
                    storyboard_frame_handoffs=handoffs,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
                wrong_id = copy.deepcopy(handoffs)
                wrong_id[0]["delivery_consumption"]["frame_outputs"][0]["frame_id"] = "other-panel"
                wrong_id_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=wrong_id,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
                wrong_hash = copy.deepcopy(handoffs)
                wrong_hash[0]["delivery_consumption"]["frame_outputs"][0]["generated_artifact"]["sha256"] = "0" * 64
                wrong_hash_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=wrong_hash,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
                fixture_only = copy.deepcopy(handoffs)
                fixture_only[0]["fixture_only"] = True
                fixture_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=fixture_only,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
                planned_handoff = copy.deepcopy(handoffs)
                planned_handoff[0]["delivery_consumption"]["status"] = "planned"
                planned_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=planned_handoff,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
                duplicate = copy.deepcopy(handoffs)
                duplicate[0]["delivery_consumption"]["frame_outputs"].append(
                    copy.deepcopy(duplicate[0]["delivery_consumption"]["frame_outputs"][0])
                )
                duplicate_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=duplicate,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
                source_handoffs = copy.deepcopy(handoffs)
                design_path = root / design_binding["relative_path"]
                altered_design = json.loads(design_path.read_text(encoding="utf-8"))
                altered_design["project_id"] = "other-project"
                altered_payload = (json.dumps(altered_design, sort_keys=True) + "\n").encode()
                design_path.write_bytes(altered_payload)
                altered_hash = hashlib.sha256(altered_payload).hexdigest()
                for frame in source_handoffs[0]["frames"]:
                    frame["panel_context"]["coverage_sha256"] = altered_hash
                source_errors, _ = gate.storyboard_handoff_errors(
                    handoff_plan, base_dir=root, storyboard_coverage=sidecar,
                    storyboard_frame_handoffs=source_handoffs,
                    provider_root=provider_root, host_event_log=host_event_log,
                )
        self.assertEqual(valid_errors, [])
        self.assertEqual(valid_missing, [])
        validate_handoff.assert_any_call(
            handoffs[0], artifact_root=root, provider_root=provider_root,
            host_event_log=host_event_log,
        )
        self.assertIn("storyboard_frame_handoff_missing", missing_errors)
        self.assertTrue(any(error.startswith("storyboard_frame_handoff_panel_binding_mismatch:") for error in wrong_phase_errors))
        self.assertTrue(any(error.startswith("storyboard_frame_handoff_design_panel_mismatch:") for error in wrong_camera_errors))
        self.assertTrue(any(error.startswith("storyboard_frame_handoff_panel_missing:") for error in wrong_id_errors))
        self.assertTrue(any(error.startswith("storyboard_frame_handoff_output_binding_mismatch:") for error in wrong_hash_errors))
        self.assertTrue(any(error.startswith("storyboard_frame_handoff_panel_duplicate:") for error in duplicate_errors))
        self.assertIn("storyboard_frame_handoff_fixture_only:0", fixture_errors)
        self.assertIn("storyboard_frame_handoff_not_observed_generation:0", planned_errors)
        self.assertTrue(any("legacy_project_id_mismatch" in error for error in source_errors))

    def test_reviewed_generated_set_reaches_user_review_without_claiming_acceptance(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, root / name)
            plan = copy.deepcopy(self.planned_plan())
            plan["completion_claim"] = "visual_assets_complete"
            file_by_asset: dict[str, str] = {}
            seed = 1
            for asset in plan["assets"]:
                target = root / f"{asset['asset_id']}.png"
                if asset["role"] in visual.DIRECT_ROLES:
                    target.write_bytes((root / file_by_asset[asset["inherits_from"][0]]).read_bytes())
                else:
                    target.write_bytes(visual.test_png_bytes(seed))
                    seed += 1
                asset["status"] = "generated_candidate"
                asset["generated_file"] = target.name
                file_by_asset[asset["asset_id"]] = target.name
            files_by_shot = {
                shot_id: file_by_asset[f"storyboard-frame-{shot_id}"]
                for shot_id in plan["shot_ids"]
            }
            storyboard_coverage = self.storyboard_coverage(root, plan, files_by_shot)
            # Fixture drawings exercise the real assembly/binding path only.
            # They are not film imagery or a claim of artistic acceptance.
            import dircreative_storyboard_page_assembler as board_assembler
            rehearsal_ids = coverage.motion_panel_ids(storyboard_coverage)
            for index, panel in enumerate(storyboard_coverage["panels"]):
                if panel["panel_id"] not in rehearsal_ids:
                    continue
                sketch = root / f"planning-{index}.png"
                sketch.write_bytes(visual.test_png_bytes(150 + index))
                panel["planning_image"] = {"status": "available", "presentation": "line_art", "path": sketch.name, "sha256": hashlib.sha256(sketch.read_bytes()).hexdigest()}
                panel["motion_annotations"] = [{"kind": "camera", "subject": "camera", "label": "固定", "stationary": True}]
            board_path, board_receipt_path = root / "planning-board.png", root / "planning-board.json"
            board_receipt = board_assembler.assemble_motion_board(
                json.dumps(storyboard_coverage).encode(), project_root=root,
                panel_ids=rehearsal_ids, columns=3,
                output_path=board_path, receipt_path=board_receipt_path,
            )
            self.assertEqual(board_receipt["status"], "assembled", board_receipt)
            review = root / "planning-review.md"
            review.write_text("Fixture binding only; visual quality unverified.")
            storyboard_coverage["motion_planning"] = {
                "reason": "contact rehearsal fixture", "panel_ids": rehearsal_ids,
                "boards": [{"panel_ids": rehearsal_ids,
                            "image": {"path": board_path.name, "sha256": board_receipt["output_sha256"]},
                            "receipt": {"path": board_receipt_path.name, "sha256": hashlib.sha256(board_receipt_path.read_bytes()).hexdigest()}}],
                "review": {"status": "reviewed", "kind": "ai", "path": review.name,
                           "sha256": hashlib.sha256(review.read_bytes()).hexdigest(),
                           "inputs_sha256": "pending"},
            }
            storyboard_coverage["motion_planning"]["review"]["inputs_sha256"] = coverage.motion_review_sha256(storyboard_coverage)
            design_binding = self.write_design_coverage(root, storyboard_coverage)
            storyboard_handoffs = self.storyboard_handoffs(
                storyboard_coverage,
                design_binding,
            )
            checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            plan = visual.stamp_plan_evidence(plan, base_dir=root, checked_at=checked_at)
            entries = []
            evidence_by_asset = {}
            for asset in plan["assets"]:
                evidence, reason = visual.inspect_raster(root / asset["generated_file"])
                self.assertIsNone(reason)
                assert evidence is not None
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
                        "notes": "Independent fixture review covers this role and its bound pixels.",
                    }
                )
            subject = visual.visual_review_subject_sha256(plan)
            manifest = {
                "schema_version": visual.VISUAL_REVIEW_MANIFEST_VERSION,
                "ruleset": visual.VISUAL_QA_RULESET,
                "review_subject_sha256": subject,
                "reviewed_at": checked_at,
                "reviewer_type": "independent_ai",
                "reviewer_id": "pre-video-gate-fixture-reviewer",
                "review_task_id": "pre-video-gate-positive",
                "assets": entries,
            }
            manifest_path = root / "visual-review-manifest.json"
            visual.atomic_write_json(manifest_path, manifest)
            manifest_sha = visual.sha256_file(manifest_path)
            for asset in plan["assets"]:
                evidence = evidence_by_asset[asset["asset_id"]]
                receipt = {
                    "receipt_version": visual.VISUAL_QA_RECEIPT_VERSION,
                    "asset_id": asset["asset_id"],
                    "file_sha256": evidence["sha256"],
                    "pixel_sha256": evidence["pixel_sha256"],
                    "truth_sha256": asset["truth_sha256"],
                    "ruleset": visual.VISUAL_QA_RULESET,
                    "reviewed_at": checked_at,
                    "reviewer_type": "independent_ai",
                    "reviewer_id": manifest["reviewer_id"],
                    "review_task_id": manifest["review_task_id"],
                    "review_manifest_file": manifest_path.name,
                    "review_manifest_sha256": manifest_sha,
                    "review_subject_sha256": subject,
                    "status": "visual_qa_pass",
                }
                receipt["receipt_sha256"] = visual.receipt_sha256(receipt)
                asset["visual_qa_receipt"] = receipt
                if asset["role"] == "character_identity_reference":
                    structure_probe = {
                        "backend": "apple-vision-human-body-pose-v1",
                        "body_pose_count": 5,
                        "face_count": 4,
                        "faces": [],
                        "human_rectangle_count": 4,
                        "full_body_count": 4,
                        "full_bodies": [
                            {
                                "center_x": 0.38 + index * 0.14,
                                "joint_span": 0.66,
                                "subject_height": 0.80,
                                "min_y": 0.08,
                                "max_y": 0.86,
                                "head_extent_above_shoulders": 0.11,
                                "subject_top_clearance": 0.04,
                                "subject_bottom_clearance": 0.04,
                                "visible_wrist_count": 2,
                                "visible_elbow_count": 2,
                                "visible_upper_limb_joint_count": 4,
                                "human_rect_index": index,
                                "human_rect_min_x": 0.33 + index * 0.14,
                                "human_rect_max_x": 0.43 + index * 0.14,
                            }
                            for index in range(4)
                        ],
                        "left_closeup_face_count": 1,
                        "left_closeup_faces": [
                            {
                                "center_x": 0.15,
                                "center_y": 0.55,
                                "width": 0.18,
                                "height": 0.28,
                            }
                        ],
                        "left_portrait_subject_height": 0.82,
                        "right_face_count": 3,
                        "right_full_height_component_count": 4,
                        "right_full_height_components": [
                            {
                                "center_x": 0.38 + index * 0.14,
                                "joint_span": 0.66,
                                "subject_height": 0.80,
                                "min_y": 0.08,
                                "max_y": 0.86,
                            }
                            for index in range(4)
                        ],
                    }
                    with mock.patch.object(
                        character_gate,
                        "swift_tool_identity",
                        return_value={
                            "path": "/fixture/swift",
                            "sha256": "f" * 64,
                            "signature_policy": "fixture",
                        },
                    ):
                        structure_receipt = character_gate.make_receipt(
                            asset_id=asset["asset_id"],
                            asset_truth_sha256=asset["truth_sha256"],
                            image_evidence=evidence,
                            probe=structure_probe,
                            checked_at=checked_at,
                            mode="headed_master",
                        )
                    visual.atomic_write_json(
                        (root / asset["generated_file"]).with_suffix(
                            ".character-master-visual.json"
                        ),
                        structure_receipt,
                    )
            plan["completion_claim"] = "plan_complete"
            with mock.patch.object(
                character_gate,
                "run_probe",
                return_value=(structure_probe, None),
            ), mock.patch.object(
                gate.storyboard_frame_handoff,
                "validate",
                return_value=[],
            ), mock.patch.object(
                character_gate,
                "swift_tool_identity",
                return_value={
                    "path": "/fixture/swift",
                    "sha256": "f" * 64,
                    "signature_policy": "fixture",
                },
            ):
                result = gate.evaluate(
                    plan,
                    base_dir=root,
                    media_scope="pre_video_assets",
                    image_generation_authorized=True,
                    video_generation_authorized=False,
                    storyboard_coverage=storyboard_coverage,
                    storyboard_frame_handoffs=storyboard_handoffs,
                    provider_root=Path("/fixture/provider"),
                    host_event_log=Path("/fixture/host-events.jsonl"),
                )
                character_asset = next(
                    asset for asset in plan["assets"] if asset["role"] == "character_identity_reference"
                )
                (root / character_asset["generated_file"]).with_suffix(
                    ".character-master-visual.json"
                ).unlink()
                missing_structure_result = gate.evaluate(
                    plan,
                    base_dir=root,
                    media_scope="pre_video_assets",
                    image_generation_authorized=True,
                    video_generation_authorized=False,
                    storyboard_coverage=storyboard_coverage,
                    storyboard_frame_handoffs=storyboard_handoffs,
                    provider_root=Path("/fixture/provider"),
                    host_event_log=Path("/fixture/host-events.jsonl"),
                )
        self.assertEqual(result["status"], "ready_for_user_review")
        self.assertTrue(result["generated_asset_set_complete"])
        self.assertFalse(result["visual_assets_complete"])
        self.assertEqual(result["validation_errors"], [])
        self.assertEqual(missing_structure_result["status"], "blocked")
        self.assertIn(
            "generated_asset_evidence_incomplete",
            missing_structure_result["reason_codes"],
        )
        self.assertTrue(
            any(
                "required_character_master_visual_structure_invalid" in error
                for error in missing_structure_result["validation_errors"]
            )
        )

    def test_storyboard_coverage_rejects_missing_contact_panel_or_real_image(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, root / name)
            plan = self.planned_plan()
            files_by_shot = {}
            for index, shot_id in enumerate(plan["shot_ids"]):
                path = root / f"{shot_id}.png"
                path.write_bytes(visual.test_png_bytes(index + 1))
                files_by_shot[shot_id] = path.name
            sidecar = self.storyboard_coverage(root, plan, files_by_shot)
            sidecar["panels"] = [
                panel for panel in sidecar["panels"] if panel["phase"] != "contact"
            ]
            missing_phase = gate.evaluate(
                plan,
                base_dir=root,
                media_scope="pre_video_assets",
                image_generation_authorized=True,
                video_generation_authorized=False,
                storyboard_coverage=sidecar,
            )
            sidecar = self.storyboard_coverage(root, plan, files_by_shot)
            contact = next(panel for panel in sidecar["panels"] if panel["phase"] == "contact")
            contact["image"] = {"status": "planned"}
            missing_image = gate.evaluate(
                plan,
                base_dir=root,
                media_scope="pre_video_assets",
                image_generation_authorized=True,
                video_generation_authorized=False,
                storyboard_coverage=sidecar,
            )
        self.assertEqual(missing_phase["status"], "blocked")
        self.assertIn("storyboard_coverage_invalid", missing_phase["reason_codes"])
        self.assertIn(
            "missing_requirement_phase_panel:requirement-S01:contact",
            missing_phase["validation_errors"],
        )
        self.assertEqual(missing_image["status"], "blocked")
        self.assertIn("storyboard_coverage_assets_incomplete", missing_image["reason_codes"])
        self.assertIn("panel-S01-contact", missing_image["missing_panels"])

    def test_storyboard_coverage_cannot_be_borrowed_from_other_plan_identity(self):
        fixture_root = ROOT / "tests/fixtures/visual-asset-plan"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (
                "valid-coverage-unit-inventory.json",
                "valid-coverage-unit-creative-source.json",
                "valid-coverage-unit-shot-cards.json",
            ):
                shutil.copy2(fixture_root / name, root / name)
            plan = self.planned_plan()
            files_by_shot = {}
            for index, shot_id in enumerate(plan["shot_ids"]):
                path = root / f"{shot_id}.png"
                path.write_bytes(visual.test_png_bytes(index + 1))
                files_by_shot[shot_id] = path.name
            sidecar = self.storyboard_coverage(root, plan, files_by_shot)
            sidecar["project_id"] = "other-project"
            project_mismatch = gate.evaluate(
                plan, base_dir=root, media_scope="pre_video_assets",
                image_generation_authorized=True, video_generation_authorized=False,
                storyboard_coverage=sidecar,
            )
            sidecar = self.storyboard_coverage(root, plan, files_by_shot)
            sidecar["scope"] = "whole_film"
            scope_mismatch = gate.evaluate(
                plan, base_dir=root, media_scope="pre_video_assets",
                image_generation_authorized=True, video_generation_authorized=False,
                storyboard_coverage=sidecar,
            )
            sidecar = self.storyboard_coverage(root, plan, files_by_shot)
            sidecar["shot_cards_sha256"] = "0" * 64
            cards_mismatch = gate.evaluate(
                plan, base_dir=root, media_scope="pre_video_assets",
                image_generation_authorized=True, video_generation_authorized=False,
                storyboard_coverage=sidecar,
            )
        self.assertIn("legacy_project_id_mismatch", project_mismatch["validation_errors"])
        self.assertEqual(project_mismatch["storyboard_coverage_status"], "invalid")
        self.assertIn("legacy_scope_mismatch", scope_mismatch["validation_errors"])
        self.assertIn("legacy_shot_cards_sha256_mismatch", cards_mismatch["validation_errors"])


if __name__ == "__main__":
    unittest.main()
