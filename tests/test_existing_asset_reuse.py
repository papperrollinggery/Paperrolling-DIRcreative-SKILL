from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_visual_asset_plan as plans
import dircreative_asset_execution_gate as gate


class ExistingAssetReuseTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[dict, list[str]]:
        source = ROOT / "tests/fixtures/asset-execution"
        for name in ("character-inventory.json", "character-creative-source.json", "character-shot-cards.json"):
            shutil.copyfile(source / name, root / name)
        inventory = json.loads((root / "character-inventory.json").read_text())
        inventory["scope"] = "whole_film"
        character = inventory["characters"][0]
        appearance = inventory["appearance_states"][0]
        inventory["characters"] = [{**character, "id": f"actor-{letter}"} for letter in "abc"]
        inventory["appearance_states"] = [
            {**appearance, "id": f"look-{letter}", "character_id": f"actor-{letter}"} for letter in "abc"
        ]
        for shot in inventory["shots"]:
            shot["character_ids"] = [f"actor-{letter}" for letter in "abc"]
            shot["appearance_state_ids"] = [f"look-{letter}" for letter in "abc"]
        ids = [f"identity-character-actor-{letter}-look-{letter}" for letter in "abc"] + ["continuity-prop-ice-cup-state", "scene-office-desk"]
        sources = []
        for index, asset_id in enumerate(ids):
            relative = f"existing-{index}.png"
            image = plans.test_png_bytes(seed=index + 1)
            (root / relative).write_bytes(image)
            sources.append({"asset_id": asset_id, "relative_path": relative, "sha256": hashlib.sha256(image).hexdigest()})
        inventory["existing_sources"] = sources
        self.write_inventory(root, inventory)
        return inventory, ids

    @staticmethod
    def write_inventory(root: Path, inventory: dict) -> None:
        (root / "character-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n")

    def test_existing_five_foundation_pngs_derive_reuse_without_generation_or_acceptance(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); inventory, ids = self.fixture(root)
            plan = plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root)
            assets = {asset["asset_id"]: asset for asset in plan["assets"]}
            for source in inventory["existing_sources"]:
                asset = assets[source["asset_id"]]
                self.assertEqual(asset["action"], "reuse")
                self.assertEqual(asset["generated_file"], source["relative_path"])
                self.assertEqual(asset["status"], "planned")
                self.assertIsNone(asset["technical_receipt"])
                self.assertIsNone(asset["visual_qa_receipt"])
            self.assertEqual(assets["identity-product-coldbrew-bottle"]["action"], "generate")
            self.assertEqual(plans.validate_plan(plan, base_dir=root)[0], [])
            self.assertEqual(plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root), plan)

    def test_reuse_target_cannot_trigger_new_generation_but_ordinary_target_still_can(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); inventory, _ids = self.fixture(root)
            asset_id = "identity-product-coldbrew-bottle"

            def packet_for_current_inventory() -> dict:
                plan = plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root)
                self.assertEqual(plans.validate_plan(plan, base_dir=root)[0], [])
                asset = next(row for row in plan["assets"] if row["asset_id"] == asset_id)
                plan_path = root / "plan.json"
                plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
                prompt = gate.build_role_prompt(asset, plan)
                stage_id, relative = gate.ROLE_STAGE_CONTRACTS[asset["role"]]
                return {
                    "contract_id": gate.CONTRACT_ID, "asset_id": asset_id, "asset_role": asset["role"],
                    "media_scope": "pre_video_assets", "authorization": {
                        "source": "validated_route_context", "image_generation": True, "video_generation": False,
                    },
                    "visual_plan": {"path": plan_path.name, "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest()},
                    "active_asset_truth_sha256": asset["truth_sha256"],
                    "stage_contract": {"stage_id": stage_id, "reference": relative,
                                       "sha256": hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()},
                    "dependencies": [], "execution": {"adapter": "imagegen", "mode": "serial_review_gated", "parallel_group": None},
                    "prompt": prompt, "prompt_sha256": gate.sha256_text(prompt),
                    "prompt_authority": gate.build_prompt_authority(asset, gate.sha256_text(prompt)),
                }

            generated_packet = packet_for_current_inventory()
            self.assertEqual(gate.validate_packet(generated_packet, repo_root=ROOT, project_root=root), [])
            source = root / "existing-product.png"; source.write_bytes(plans.test_png_bytes(seed=90))
            inventory["existing_sources"].append({"asset_id": asset_id, "relative_path": source.name,
                                                  "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
            self.write_inventory(root, inventory)
            reused_packet = packet_for_current_inventory()
            self.assertEqual(gate.validate_packet(reused_packet, repo_root=ROOT, project_root=root),
                             ["existing_asset_reuse_requires_readback_not_generation"])

    def test_partial_stamp_reads_only_selected_five_and_does_not_claim_full_completion(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); inventory, ids = self.fixture(root)
            plan = plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root)
            stamped = plans.stamp_plan_evidence(plan, base_dir=root, asset_ids=ids)
            original = {asset["asset_id"]: asset for asset in plan["assets"]}
            for asset in stamped["assets"]:
                if asset["asset_id"] in ids:
                    actual, reason = plans.inspect_raster(root / asset["generated_file"])
                    self.assertIsNone(reason)
                    self.assertEqual(asset["generated_sha256"], actual["sha256"])
                    self.assertEqual(asset["generated_pixel_sha256"], actual["pixel_sha256"])
                    self.assertIsNone(plans.validate_technical_receipt(asset["technical_receipt"], asset_id=asset["asset_id"], evidence=actual, truth_locked_at=stamped["truth_locked_at"]))
                    self.assertEqual(asset["status"], "planned")
                    self.assertIsNone(asset["visual_qa_receipt"])
                else:
                    self.assertEqual(asset, original[asset["asset_id"]])
            errors, metrics = plans.validate_plan(stamped, base_dir=root)
            self.assertEqual(errors, [])
            self.assertFalse(metrics["whole_film_visual_assets_complete"])

    def test_joint_reuse_and_assembly_review_reads_both_without_reading_future_assets(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); inventory, ids = self.fixture(root)
            plan = plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root)
            page = next(asset for asset in plan["assets"] if asset["role"] == "professional_storyboard_motion_map")
            self.assertEqual(page["action"], "assemble")
            page["generated_file"] = "fixture-page.png"
            page["status"] = "generated_candidate"
            (root / page["generated_file"]).write_bytes(plans.test_png_bytes(seed=78))
            stamped = plans.stamp_plan_evidence(plan, base_dir=root, asset_ids=[*ids, page["asset_id"]])
            assets = {asset["asset_id"]: asset for asset in stamped["assets"]}
            reviewed_ids = ["continuity-prop-ice-cup-state", page["asset_id"]]
            reviewed_at = assets[reviewed_ids[0]]["technical_receipt"]["checked_at"]
            subject = plans.visual_review_subject_sha256(stamped, scope_asset_ids=reviewed_ids)
            manifest = {
                "schema_version": plans.SCOPED_VISUAL_REVIEW_MANIFEST_VERSION,
                "ruleset": plans.VISUAL_QA_RULESET,
                "scope_asset_ids": reviewed_ids,
                "review_subject_sha256": subject,
                "reviewed_at": reviewed_at,
                "reviewer_type": "independent_ai",
                "reviewer_id": "fixture-only-reviewer",
                "review_task_id": "fixture-joint-reuse-assembly",
                "assets": [
                    {
                        "asset_id": asset_id, "role": assets[asset_id]["role"],
                        "file_sha256": assets[asset_id]["generated_sha256"],
                        "pixel_sha256": assets[asset_id]["generated_pixel_sha256"],
                        "truth_sha256": assets[asset_id]["truth_sha256"],
                        "rubric_id": plans.visual_review_rubric_id(assets[asset_id]["role"]),
                        "rubric": {key: True for key in (
                            "truth_and_role_match", "coverage_and_continuity_match",
                            "composition_readable", "artifact_free", "downstream_use_fit",
                        )},
                        "decision": "pass",
                        "notes": "Fixture-only review binding; not evidence of real generated image quality.",
                    }
                    for asset_id in reviewed_ids
                ],
            }
            manifest_path = root / "fixture-review.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            for asset_id in reviewed_ids:
                asset = assets[asset_id]
                receipt = {
                    "receipt_version": plans.VISUAL_QA_RECEIPT_VERSION,
                    "asset_id": asset_id, "file_sha256": asset["generated_sha256"],
                    "pixel_sha256": asset["generated_pixel_sha256"], "truth_sha256": asset["truth_sha256"],
                    "ruleset": plans.VISUAL_QA_RULESET, "reviewed_at": reviewed_at,
                    "reviewer_type": "independent_ai", "reviewer_id": manifest["reviewer_id"],
                    "review_task_id": manifest["review_task_id"],
                    "review_manifest_file": manifest_path.name, "review_manifest_sha256": manifest_hash,
                    "review_subject_sha256": subject, "status": "visual_qa_pass",
                }
                receipt["receipt_sha256"] = plans.receipt_sha256(receipt)
                asset["visual_qa_receipt"] = receipt

            errors, metrics = plans.validate_plan(stamped, base_dir=root)
            self.assertEqual(errors, [])
            self.assertEqual(metrics["evidence_files_verified"], 6)
            self.assertFalse(metrics["whole_film_visual_assets_complete"])
            future = [asset for asset in stamped["assets"] if asset["asset_id"] not in {*ids, page["asset_id"]}]
            self.assertTrue(future)
            self.assertTrue(all(asset["status"] == "planned" and asset["technical_receipt"] is None for asset in future))

            (root / page["generated_file"]).write_bytes(plans.test_png_bytes(seed=79))
            errors, _metrics = plans.validate_plan(stamped, base_dir=root)
            self.assertIn(f"required_asset_hash_mismatch:{page['asset_id']}", errors)

    def test_no_declaration_keeps_generation_and_declared_path_changes_asset_truth(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); inventory, ids = self.fixture(root)
            reused = plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root)
            without = copy.deepcopy(inventory); without.pop("existing_sources")
            self.write_inventory(root, without)
            generated = plans.derive_plan(without, inventory_file="character-inventory.json", base_dir=root)
            first = next(asset for asset in generated["assets"] if asset["asset_id"] == ids[0])
            self.assertEqual(first["action"], "generate")
            self.assertEqual(first["generated_file"], "")
            original = next(asset for asset in reused["assets"] if asset["asset_id"] == ids[0])
            self.assertNotEqual(first["truth_sha256"], original["truth_sha256"])
            changed = copy.deepcopy(inventory)
            shutil.copyfile(root / changed["existing_sources"][0]["relative_path"], root / "alternate-source.png")
            changed["existing_sources"][0]["relative_path"] = "alternate-source.png"
            self.write_inventory(root, changed)
            updated = plans.derive_plan(changed, inventory_file="character-inventory.json", base_dir=root)
            updated_first = next(asset for asset in updated["assets"] if asset["asset_id"] == ids[0])
            self.assertNotEqual(updated_first["truth_sha256"], original["truth_sha256"])
            self.assertTrue(plans.validate_plan(reused, base_dir=root)[0])

    def test_existing_sources_reject_unbound_unsupported_or_invalid_files(self):
        for case in ("unknown", "storyboard", "hash", "escape", "symlink", "fake_png", "duplicate", "extra_claim"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as raw:
                root = Path(raw) / "project"; root.mkdir()
                inventory, ids = self.fixture(root)
                item = inventory["existing_sources"][0]
                if case == "unknown": item["asset_id"] = "unknown-asset"
                elif case == "storyboard": item["asset_id"] = "storyboard-frame-S01"
                elif case == "hash": item["sha256"] = "0" * 64
                elif case == "escape":
                    shutil.copyfile(root / item["relative_path"], root.parent / "outside.png")
                    item["relative_path"] = "../outside.png"
                elif case == "symlink":
                    (root / "linked.png").symlink_to(root / item["relative_path"])
                    item["relative_path"] = "linked.png"
                elif case == "fake_png":
                    payload = plans.padded_fake_png_bytes()
                    (root / item["relative_path"]).write_bytes(payload)
                    item["sha256"] = hashlib.sha256(payload).hexdigest()
                elif case == "duplicate": inventory["existing_sources"].append(copy.deepcopy(item))
                else: item["visual_qa_approved"] = True
                self.write_inventory(root, inventory)
                with self.assertRaisesRegex(ValueError, "existing_source"):
                    plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root)

    def test_changed_source_and_forged_recorded_pixels_fail_readback(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); inventory, ids = self.fixture(root)
            plan = plans.derive_plan(inventory, inventory_file="character-inventory.json", base_dir=root)
            stamped = plans.stamp_plan_evidence(plan, base_dir=root, asset_ids=ids)
            forged = copy.deepcopy(stamped)
            next(asset for asset in forged["assets"] if asset["asset_id"] == ids[0])["generated_pixel_sha256"] = "0" * 64
            self.assertIn(f"required_asset_pixel_hash_mismatch:{ids[0]}", plans.validate_plan(forged, base_dir=root)[0])
            substituted = copy.deepcopy(stamped)
            next(asset for asset in substituted["assets"] if asset["asset_id"] == ids[0])["generated_file"] = inventory["existing_sources"][1]["relative_path"]
            self.assertIn(f"existing_source_path_mismatch:{ids[0]}", plans.validate_plan(substituted, base_dir=root)[0])
            (root / inventory["existing_sources"][0]["relative_path"]).write_bytes(plans.test_png_bytes(seed=99))
            errors, _ = plans.validate_plan(stamped, base_dir=root)
            self.assertTrue(any(error.startswith("inventory_invalid:existing_source_hash_mismatch") for error in errors), errors)

    def test_partial_stamp_cli_requires_selection_and_leaves_future_assets_unstamped(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); inventory, ids = self.fixture(root)
            script = ROOT / "scripts/dircreative_visual_asset_plan.py"
            expanded = root / "visual-plan.json"; stamped_path = root / "partial-plan.json"
            derive = subprocess.run([sys.executable, str(script), "--inventory", str(root / "character-inventory.json"), "--output", str(expanded)], capture_output=True, text=True, check=False)
            self.assertEqual(derive.returncode, 0, derive.stdout + derive.stderr)
            partial = subprocess.run([sys.executable, str(script), "--plan", str(expanded), "--stamp-evidence", "--output", str(stamped_path), *[argument for asset_id in ids for argument in ("--asset-id", asset_id)]], capture_output=True, text=True, check=False)
            self.assertEqual(partial.returncode, 0, partial.stdout + partial.stderr)
            stamped = json.loads(stamped_path.read_text())
            self.assertEqual({asset["asset_id"] for asset in stamped["assets"] if asset["technical_receipt"] is not None}, set(ids))
            self.assertEqual(stamped["completion_claim"], "plan_complete")
            plan = json.loads(expanded.read_text())
            with self.assertRaisesRegex(ValueError, "missing or escaped"):
                plans.stamp_plan_evidence(plan, base_dir=root)
            for selection in ([], ["unknown"], [ids[0], ids[0]]):
                with self.subTest(selection=selection), self.assertRaisesRegex(ValueError, "asset_ids"):
                    plans.stamp_plan_evidence(plan, base_dir=root, asset_ids=selection)
            stamped["completion_claim"] = "visual_assets_complete"
            errors, metrics = plans.validate_plan(stamped, base_dir=root)
            self.assertTrue(errors)
            self.assertIn(plans.TRUSTED_VISUAL_REVIEW_ADOPTION_REQUIRED, errors)
            self.assertFalse(metrics["whole_film_visual_assets_complete"])


if __name__ == "__main__":
    unittest.main()
