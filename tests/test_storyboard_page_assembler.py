from __future__ import annotations

import copy
import hashlib
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


if __name__ == "__main__":
    unittest.main()
