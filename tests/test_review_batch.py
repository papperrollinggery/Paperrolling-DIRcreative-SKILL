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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_review_batch as batch
import dircreative_visual_asset_plan as plans
import dircreative_asset_execution_gate as gate


class BatchReviewTests(unittest.TestCase):
    def test_template_help_exposes_conditional_rejection_inputs(self):
        help_text = batch.review_input_help({"assets": [{"asset_id": "C01", "role": "character_identity_reference"}]}, ["C01"])
        self.assertIn("executor", help_text["reviewer_type_values"])
        self.assertEqual(help_text["rubric_values"], [True, False, None])
        self.assertIn("right_profile", help_text["check_ids_by_asset"]["C01"])
        self.assertEqual(set(help_text["retry_or_reject_requires"]["defects"][0]), {"check_id", "observed"})

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture = ROOT / "tests/fixtures/asset-execution"
        for name in ("character-plan.json", "character-inventory.json", "character-creative-source.json", "character-shot-cards.json"):
            shutil.copyfile(fixture / name, self.root / name)
        self.plan = json.loads((self.root / "character-plan.json").read_text())
        self.ids = [a["asset_id"] for a in self.plan["assets"] if a["role"] in {"product_identity_board", "prop_continuity_board"}][:2]
        self.assertEqual(len(self.ids), 2)
        for i, asset_id in enumerate(self.ids):
            image = self.root / f"test-{i}.png"
            image.write_bytes(plans.test_png_bytes(i + 5, width=800, height=450))
            self.plan = plans.record_candidate_output(self.plan, base_dir=self.root, asset_id=asset_id, image_path=image, execution_task_id="source-task")

    def reviewed(self):
        draft = batch.make_template(self.plan, base_dir=self.root, asset_ids=self.ids)
        draft.update(reviewer_type="executor", reviewer_id="source-task", review_task_id="source-task")
        for row in draft["assets"]:
            row.update(decision="pass", notes="Explicit test observation of geometry, material, source facts and intended reference use.")
            row["rubric"] = {key: True for key in batch.RUBRIC}
        return draft

    def test_one_batch_review_replaces_duplicate_executor_check_without_granting_lock(self):
        pending = batch.make_template(self.plan, base_dir=self.root, asset_ids=self.ids)
        self.assertTrue(all(r["decision"] == "pending" and all(v is None for v in r["rubric"].values()) for r in pending["assets"]))
        review = self.reviewed()
        updated, result = batch.record_review(self.plan, review, base_dir=self.root, output_dir=self.root / "reviews")
        self.assertEqual(result["reviewed_asset_ids"], self.ids)
        self.assertEqual(plans.pending_candidate_self_checks(updated, base_dir=self.root, execution_task_id="another-task", asset_ids=set(self.ids)), [])
        for row in updated["assets"]:
            if row["asset_id"] in self.ids:
                self.assertEqual(row["status"], "generated_candidate")
                self.assertIsNone(row.get("candidate_self_check"))
        again, _ = batch.record_review(self.plan, review, base_dir=self.root, output_dir=self.root / "reviews")
        self.assertEqual(updated, again)
        locked = copy.deepcopy(updated)
        next(a for a in locked["assets"] if a["asset_id"] == self.ids[0])["status"] = "user_locked"
        self.assertIn("executor_review_cannot_grant_asset_lock:" + self.ids[0], plans.validate_plan(locked, base_dir=self.root)[0])
        completed = copy.deepcopy(updated); completed["completion_claim"] = "visual_assets_complete"
        self.assertIn("executor_review_cannot_grant_visual_assets_complete", plans.validate_plan(completed, base_dir=self.root)[0])

    def packet_for_frame(self, plan):
        plans.atomic_write_json(self.root / "reviewed-plan.json", plan)
        asset = next(a for a in plan["assets"] if a["asset_id"] == "storyboard-frame-S03")
        assets = {a["asset_id"]: a for a in plan["assets"]}
        stage, ref = gate.ROLE_STAGE_CONTRACTS[asset["role"]]
        return {"contract_id": gate.CONTRACT_ID, "asset_id": asset["asset_id"], "asset_role": asset["role"],
                "active_asset_truth_sha256": asset["truth_sha256"],
                "visual_plan": {"path": "reviewed-plan.json", "sha256": plans.sha256_file(self.root / "reviewed-plan.json")},
                "stage_contract": {"stage_id": stage, "reference": ref, "sha256": plans.sha256_file(ROOT / ref)},
                "media_scope": "pre_video_assets", "authorization": {"source": "validated_route_context", "image_generation": True, "video_generation": False},
                "execution": {"adapter": "imagegen", "mode": "batch_then_review", "parallel_group": None},
                "prompt": asset["purpose"], "prompt_sha256": hashlib.sha256(asset["purpose"].encode()).hexdigest(),
                "dependencies": [{"asset_id": i, "status": "visual_qa_pass", "visual_qa_receipt_sha256": (assets[i].get("visual_qa_receipt") or {}).get("receipt_sha256", "0" * 64)} for i in asset["inherits_from"]]}

    def test_draft_dependencies_reuse_review_but_forged_and_independent_claims_do_not(self):
        updated, _ = batch.record_review(self.plan, self.reviewed(), base_dir=self.root, output_dir=self.root / "draft")
        # This fixture deliberately leaves the frame's other parents and compile
        # pending. Verify these two real reviewed parents only, not full readiness.
        with mock.patch.object(gate, "load_visual_review_authorization", return_value=(None, ["fixture_missing_authorization"])) as authority:
            errors = gate.validate_packet(self.packet_for_frame(updated), project_root=self.root, execution_task_id="consumer-task")
            self.assertFalse(any(e.startswith("dependency_visual_review_not_host_authorized:" + self.ids[0]) for e in errors), errors)
            self.assertFalse(any(e.startswith("dependency_plan_state_not_approved:" + self.ids[0]) for e in errors), errors)
            authority.assert_not_called()
        changed = copy.deepcopy(updated)
        next(a for a in changed["assets"] if a["asset_id"] == self.ids[0])["visual_qa_receipt"]["receipt_sha256"] = "f" * 64
        errors = gate.validate_packet(self.packet_for_frame(changed), project_root=self.root, execution_task_id="consumer-task")
        self.assertTrue(any(e.startswith("dependency_plan_state_not_approved:" + self.ids[0]) for e in errors), errors)
        review = self.reviewed(); review.update(reviewer_type="independent_ai", reviewer_id="other-task", review_task_id="other-task")
        independent, _ = batch.record_review(self.plan, review, base_dir=self.root, output_dir=self.root / "independent")
        with mock.patch.object(gate, "load_visual_review_authorization", return_value=(None, ["fixture_missing_authorization"])) as authority:
            errors = gate.validate_packet(self.packet_for_frame(independent), project_root=self.root, execution_task_id="consumer-task")
            self.assertIn("dependency_visual_review_not_host_authorized:" + self.ids[0], errors)
            self.assertTrue(authority.call_args_list)
            self.assertTrue(all(c.kwargs["expected_execution_task_id"] == "source-task" for c in authority.call_args_list))

    def test_changed_batch_member_does_not_revoke_other_member_review(self):
        updated, _ = batch.record_review(self.plan, self.reviewed(), base_dir=self.root, output_dir=self.root / "reviews")
        changed = next(a for a in updated["assets"] if a["asset_id"] == self.ids[1])
        (self.root / changed["generated_file"]).write_bytes(plans.test_png_bytes(88, width=800, height=450))
        self.assertEqual(plans.candidate_visual_review_errors(updated, asset_id=self.ids[0], base_dir=self.root), [])
        self.assertTrue(plans.candidate_visual_review_errors(updated, asset_id=self.ids[1], base_dir=self.root))

    def test_local_review_ignores_unrelated_metadata_but_keeps_its_own_use_and_dependencies(self):
        updated, _ = batch.record_review(self.plan, self.reviewed(), base_dir=self.root, output_dir=self.root / "local")
        updated["inventory_sha256"] = "a" * 64
        updated["shot_cards_sha256"] = "b" * 64
        updated["truth_revision"] = "admin-route-update"
        self.assertEqual(plans.candidate_visual_review_errors(updated, asset_id=self.ids[0], base_dir=self.root), [])
        next(a for a in updated["assets"] if a["asset_id"] == self.ids[0])["purpose"] += " different use"
        self.assertTrue(plans.candidate_visual_review_errors(updated, asset_id=self.ids[0], base_dir=self.root))
        # Plan validation still checks current inventory/card content; a local
        # review does not legalize these intentionally forged plan hashes.
        self.assertTrue(plans.validate_plan(updated, base_dir=self.root)[0])

    def test_stale_pixels_purpose_and_missing_observations_fail(self):
        for change in ("pixels", "purpose", "notes", "rubric"):
            with self.subTest(change=change):
                plan = copy.deepcopy(self.plan); review = self.reviewed()
                if change == "purpose":
                    next(a for a in plan["assets"] if a["asset_id"] == self.ids[0])["purpose"] += " new use"
                elif change == "pixels":
                    review["assets"][0]["file_sha256"] = "a" * 64
                elif change == "notes":
                    review["assets"][0]["notes"] = ""
                else:
                    review["assets"][0]["rubric"]["artifact_free"] = False
                with self.assertRaises(ValueError):
                    batch.record_review(plan, review, base_dir=self.root, output_dir=self.root / change)

    def test_failed_observation_is_saved_without_pass_and_unchanged_work_continues(self):
        review = self.reviewed(); review["assets"][1].update(decision="retry", notes="Test: the connector orientation is visibly wrong and needs a bounded repair.",
            defects=[{"check_id": "shape_interface_and_orientation", "observed": "Test: connector turns toward the wrong side in this saved image."}])
        updated, result = batch.record_review(self.plan, review, base_dir=self.root, output_dir=self.root / "mixed")
        self.assertEqual(result["needs_attention"], [self.ids[1]])
        self.assertIsNone(next(a for a in updated["assets"] if a["asset_id"] == self.ids[1])["visual_qa_receipt"])
        self.assertTrue(plans.pending_candidate_self_checks(updated, base_dir=self.root, execution_task_id="source-task", asset_ids={self.ids[1]}))
        self.assertEqual(plans.candidate_visual_review_errors(updated, asset_id=self.ids[0], base_dir=self.root), [])
        plans.atomic_write_json(self.root / "reviewed-plan.json", updated)
        binding = {"relative_path": "reviewed-plan.json", "sha256": plans.sha256_file(self.root / "reviewed-plan.json")}
        repair = plans.build_candidate_repair_source(project_root=self.root, visual_plan_binding=binding,
            asset_id=self.ids[1], changes=[{"check_id": "shape_interface_and_orientation", "instruction": "Correct only the connector orientation to match its source."}])
        self.assertEqual(repair["asset_id"], self.ids[1])
        failed_binding = next(a for a in updated["assets"] if a["asset_id"] == self.ids[1])["candidate_self_check"]
        failed = json.loads((self.root / failed_binding["relative_path"]).read_text())
        failed["assets"][0]["decision"] = "checked"
        self.assertTrue(plans.validate_candidate_self_check(failed, payload=updated, asset_id=self.ids[1], base_dir=self.root))

    def test_cli_template_and_record_need_no_custom_receipt_script(self):
        plans.atomic_write_json(self.root / "current.json", self.plan)
        command = [sys.executable, str(ROOT / "scripts/dircreative_review_batch.py")]
        result = subprocess.run(command + ["template", "--plan", str(self.root / "current.json"), "--output", str(self.root / "review.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plans.atomic_write_json(self.root / "review.json", self.reviewed())
        result = subprocess.run(command + ["record", "--plan", str(self.root / "current.json"), "--review", str(self.root / "review.json"), "--output", str(self.root / "reviewed.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "review_recorded")
        again = subprocess.run(command + ["template", "--plan", str(self.root / "reviewed.json"), "--output", str(self.root / "unneeded-review.json")], capture_output=True, text=True)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(json.loads(again.stdout)["status"], "no_review_required")
        self.assertFalse((self.root / "unneeded-review.json").exists())

    def test_compact_output_registration_does_not_ask_for_another_per_image_checklist(self):
        original = self.root / "character-plan.json"
        result = subprocess.run([sys.executable, str(ROOT / "scripts/dircreative_asset_execution_gate.py"),
            "--project-root", str(self.root), "--record-output", "--batch-review", "--plan", str(original),
            "--expected-plan-sha256", plans.sha256_file(original), "--asset-id", self.ids[0],
            "--image", "test-0.png", "--execution-task-id", "source-task", "--output", str(self.root / "compact.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["status"], "batch_review_pending")
        self.assertNotIn("self_check_template", data)
        self.assertFalse(data["visual_qa_approved"])


if __name__ == "__main__":
    unittest.main()
