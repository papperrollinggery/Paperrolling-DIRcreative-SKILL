from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_pre_video_assets_gate as gate  # noqa: E402
import dircreative_visual_asset_plan as visual  # noqa: E402
import dircreative_character_master_visual_gate as character_gate  # noqa: E402


class PreVideoAssetsGateTests(unittest.TestCase):
    def planned_plan(self) -> dict:
        path = ROOT / "tests/fixtures/visual-asset-plan/valid-coverage-unit.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_pre_video_assets_blocks_all_planned_required_assets(self):
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
        self.assertIn("pre_video_assets_requires_verified_images", result["reason_codes"])

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


if __name__ == "__main__":
    unittest.main()
