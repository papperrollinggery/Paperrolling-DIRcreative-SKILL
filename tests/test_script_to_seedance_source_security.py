from __future__ import annotations

import hashlib
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_script_to_seedance_handoff as handoff  # noqa: E402
from dircreative_verify_release import read_relative_regular_file_once  # noqa: E402


class ScriptSourceSecurityTests(unittest.TestCase):
    def document(self, relative: str, digest: str) -> dict:
        return {
            "authoritative_script": {
                "script_id": "SCRIPT-SECURITY",
                "source_relative_path": relative,
                "sha256": digest,
            }
        }

    def test_parent_symlink_cannot_escape_project_root(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(raw)
            outside = Path(outside_raw)
            source = outside / "script.md"
            source.write_text("outside script", encoding="utf-8")
            (root / "linked").symlink_to(outside, target_is_directory=True)
            errors = handoff.authoritative_script_errors(
                self.document("linked/script.md", hashlib.sha256(source.read_bytes()).hexdigest()),
                project_root=root,
            )
        self.assertTrue(any("authoritative_script_file_invalid" in error for error in errors))

    def test_hardlinked_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "script.md"
            alias = root / "alias.md"
            source.write_text("script", encoding="utf-8")
            os.link(source, alias)
            errors = handoff.authoritative_script_errors(
                self.document("script.md", hashlib.sha256(source.read_bytes()).hexdigest()),
                project_root=root,
            )
        self.assertTrue(any("authoritative_script_file_invalid" in error for error in errors))

    def test_typed_reference_budget_rejects_image_overflow_below_total_limit(self):
        bindings = {
            "I1": {"media_type": "image"},
            "I2": {"media_type": "image"},
            "A1": {"media_type": "audio"},
        }
        limits = {
            "max_references_per_unit": 5,
            "max_image_references_per_unit": 1,
            "max_video_references_per_unit": 2,
            "max_audio_references_per_unit": 2,
        }
        errors = handoff.reference_budget_errors(
            ["I1", "I2", "A1"],
            bindings,
            limits,
            "GU-TEST",
        )
        self.assertIn("provider_image_reference_budget_exceeded: GU-TEST", errors)

    def test_oversized_handoff_cli_returns_structured_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            handoff_path = root / "oversized.json"
            handoff_path.write_bytes(b"x" * (handoff.MAX_HANDOFF_BYTES + 1))
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/dircreative_script_to_seedance_handoff.py"),
                    "validate",
                    str(handoff_path),
                    "--project-root",
                    str(root),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("handoff_too_large", proc.stdout)

    def test_pinned_relative_read_rejects_parent_directory_replacement(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside_raw:
            root = Path(raw)
            outside = Path(outside_raw)
            parent = root / "source"
            parent.mkdir()
            (parent / "script.md").write_text("trusted", encoding="utf-8")
            (outside / "script.md").write_text("outside", encoding="utf-8")

            def replace_parent(_phase: str, _relative: str) -> None:
                parent.rename(root / "source-old")
                parent.symlink_to(outside, target_is_directory=True)

            with self.assertRaises((OSError, ValueError)):
                read_relative_regular_file_once(
                    root,
                    "source/script.md",
                    max_bytes=1024,
                    label="authoritative script",
                    race_hook=replace_parent,
                )

    def test_seedance25_converter_fallback_can_record_non_adoption(self):
        document = json.loads(handoff.VALID_PATH.read_text(encoding="utf-8"))
        method = document["method_application"]
        method.update(
            status="not_applied",
            metadata_version=None,
            observed_metadata_version="1.8.2",
            authority="converter_fallback",
            non_adoption_reason="version_mismatch",
        )
        self.assertEqual(handoff.schema_errors(document), [])
        self.assertEqual(handoff.method_application_errors(document), [])

    def test_method_fields_are_derived_from_units_and_clean_prompt_surface(self):
        document = json.loads(handoff.VALID_PATH.read_text(encoding="utf-8"))
        bad = copy.deepcopy(document)
        bad["method_application"]["capacity_preflight"][0].update(
            scene_type="dialogue",
            estimated_seconds=1,
            draft_review_seconds=1,
            scene_completion_claim="scene_complete",
            next_source_start="NOT-A-SOURCE-BEAT",
        )
        errors = handoff.method_application_errors(bad)
        self.assertTrue(any(error.startswith("capacity_scene_type_mismatch") for error in errors))
        self.assertTrue(any(error.startswith("capacity_limit_exceeded") for error in errors))
        self.assertTrue(
            any(error.startswith("capacity_next_source_or_completion_mismatch") for error in errors)
        )
        for leaked_heading in (
            "# Work title: SPACE BATTLE\nDirector: Example",
            "## Camera",
            "【全局视觉】",
            "DIRECTOR — Example",
        ):
            surfaced = copy.deepcopy(document)
            surfaced["prompt_units"][0]["prompt_text"] += "\n" + leaked_heading
            self.assertTrue(
                any(
                    error.startswith("formal_prompt_surface_not_clean")
                    for error in handoff.method_application_errors(surfaced)
                ),
                leaked_heading,
            )

    def test_dialogue_line_is_counted_once_per_generation_unit(self):
        document = json.loads(handoff.VALID_PATH.read_text(encoding="utf-8"))
        document["authoritative_script"]["dialogue_lines"][0]["shot_ids"] = [
            "SH03",
            "SH04",
        ]
        errors = handoff.method_application_errors(document)
        self.assertFalse(any(error.startswith("capacity_dialogue_count_mismatch") for error in errors))


if __name__ == "__main__":
    unittest.main()
