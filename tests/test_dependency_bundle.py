from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_dependency_bundle as bundle  # noqa: E402


class DependencyBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="dir-bundle-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.skills = self.base / "skills"

    def manifest(self, contents: str, *, version: str = "1.0.0", destination: str = "linked-skill") -> Path:
        source_dir = self.source / "bundle-source"
        target = source_dir / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
        document = {
            "schema_version": 1, "bundle_id": "test-bundle", "skills": [{
                "skill_id": "linked-skill", "version": version,
                "source": {"directory": "bundle-source", "reference": "local-test"},
                "relative_directory": destination,
                "files": [{"path": "SKILL.md", "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "executable": False}],
            }],
        }
        path = self.base / "manifest.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def one(self, result):
        self.assertEqual(len(result["skills"]), 1)
        return result["skills"][0]

    def test_payload_alias_restores_skill_without_exposing_bundle_entry(self):
        manifest = self.manifest("skill contents\n")
        (self.source / "bundle-source/SKILL.md").rename(self.source / "bundle-source/SKILL.payload")
        document = json.loads(manifest.read_text())
        item = document["skills"][0]["files"][0]
        item["source_path"] = "SKILL.payload"
        manifest.write_text(json.dumps(document))
        self.assertEqual(list(self.source.rglob("SKILL.md")), [])
        self.assertEqual(bundle.install_bundle(manifest, self.skills, source_root=self.source)["status"], "ok")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_text(), "skill contents\n")
        self.assertEqual(bundle.check_bundle(manifest, self.skills, source_root=self.source)["status"], "ok")
        item["source_path"] = "../SKILL.payload"
        manifest.write_text(json.dumps(document))
        self.assertEqual(bundle.install_bundle(manifest, self.skills, source_root=self.source)["status"], "blocked")

    def test_clean_install_then_exact_repeat_is_up_to_date(self):
        manifest = self.manifest("first\n")
        installed = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(installed["status"], "ok")
        self.assertEqual(self.one(installed)["status"], "installed")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_text(), "first\n")
        self.assertTrue((self.skills / bundle.CONTROL_DIRECTORY / "receipts/linked-skill.json").is_file())

        repeated = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(repeated["status"], "ok")
        self.assertEqual(self.one(repeated)["status"], "up_to_date")
        checked = bundle.check_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(self.one(checked)["status"], "up_to_date")

    def test_inventory_order_matches_manifest_for_file_and_same_prefix_directory(self):
        source = self.source / "bundle-source"
        files = {
            "SKILL.md": "root\n",
            "references/style-capsules.md": "index\n",
            "references/style-capsules/azure.json": "child\n",
        }
        for relative, contents in files.items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        document = {"schema_version": 1, "bundle_id": "test-bundle", "skills": [{
            "skill_id": "linked-skill", "version": "1.0.0",
            "source": {"directory": "bundle-source"}, "relative_directory": "linked-skill",
            "files": [{"path": relative, "sha256": hashlib.sha256(contents.encode()).hexdigest(), "executable": False}
                      for relative, contents in files.items()],
        }]}
        manifest = self.base / "prefix-manifest.json"
        manifest.write_text(json.dumps(document))
        self.assertEqual(self.one(bundle.install_bundle(manifest, self.skills, source_root=self.source))["status"], "installed")
        checked = bundle.check_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(self.one(checked)["status"], "up_to_date")

    def test_matching_managed_snapshot_can_update(self):
        first = self.manifest("first\n")
        bundle.install_bundle(first, self.skills, source_root=self.source)
        second = self.manifest("second\n", version="2.0.0")
        result = bundle.install_bundle(second, self.skills, source_root=self.source)
        self.assertEqual(self.one(result)["status"], "installed")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_text(), "second\n")
        receipt = json.loads((self.skills / bundle.CONTROL_DIRECTORY / "receipts/linked-skill.json").read_text())
        self.assertEqual(receipt["version"], "2.0.0")

    def test_newer_standard_semver_and_local_development_versions_are_preserved(self):
        newer = self.manifest("newer\n", version="1.9.0")
        bundle.install_bundle(newer, self.skills, source_root=self.source)
        older = self.manifest("older\n", version="1.8.0")
        result = bundle.install_bundle(older, self.skills, source_root=self.source)
        self.assertEqual(self.one(result)["status"], "preserved")
        self.assertEqual(self.one(result)["reason"], "managed_newer_version")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_text(), "newer\n")

        local = self.manifest("local\n", version="2.0.0-local")
        fresh = self.base / "local-skills"
        bundle.install_bundle(local, fresh, source_root=self.source)
        lower = self.manifest("lower\n", version="1.9.9")
        local_result = bundle.install_bundle(lower, fresh, source_root=self.source)
        self.assertEqual(self.one(local_result)["status"], "preserved")
        self.assertEqual((fresh / "linked-skill/SKILL.md").read_text(), "local\n")

    def test_unknown_version_order_is_preserved(self):
        first = self.manifest("first\n", version="vendor-build")
        self.assertEqual(self.one(bundle.install_bundle(first, self.skills, source_root=self.source))["status"], "installed")
        second = self.manifest("second\n", version="next-vendor-build")
        result = bundle.install_bundle(second, self.skills, source_root=self.source)
        self.assertEqual(self.one(result)["status"], "preserved")
        self.assertEqual(self.one(result)["reason"], "unknown_version_order")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_text(), "first\n")

    def test_modified_and_unmanaged_directories_are_preserved(self):
        manifest = self.manifest("first\n")
        bundle.install_bundle(manifest, self.skills, source_root=self.source)
        installed = self.skills / "linked-skill"
        (installed / "SKILL.md").write_text("local edit\n")
        changed = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(self.one(changed)["status"], "conflict")
        self.assertEqual((installed / "SKILL.md").read_text(), "local edit\n")

        other = self.base / "other-skills"
        (other / "linked-skill").mkdir(parents=True)
        (other / "linked-skill/SKILL.md").write_text("foreign\n")
        unmanaged = bundle.install_bundle(manifest, other, source_root=self.source)
        self.assertEqual(self.one(unmanaged)["status"], "preserved")
        self.assertEqual((other / "linked-skill/SKILL.md").read_text(), "foreign\n")

    def test_unexpected_files_and_symlinks_are_conflicts_without_replacement(self):
        manifest = self.manifest("first\n")
        bundle.install_bundle(manifest, self.skills, source_root=self.source)
        installed = self.skills / "linked-skill"
        (installed / "notes.txt").write_text("keep me\n")
        unexpected = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(self.one(unexpected)["status"], "conflict")
        self.assertTrue((installed / "notes.txt").exists())

        other = self.base / "symlink-skills"
        outside = self.base / "outside"
        outside.mkdir()
        (other).mkdir()
        (other / "linked-skill").symlink_to(outside, target_is_directory=True)
        linked = bundle.install_bundle(manifest, other, source_root=self.source)
        self.assertEqual(self.one(linked)["status"], "conflict")
        self.assertTrue((other / "linked-skill").is_symlink())

    def test_path_traversal_and_hash_mismatch_are_blocked_before_copying(self):
        manifest = self.manifest("trusted\n", destination="../escape")
        traversal = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(traversal["status"], "blocked")
        self.assertFalse(self.skills.exists())

        manifest = self.manifest("trusted\n")
        (self.source / "bundle-source/SKILL.md").write_text("changed\n")
        mismatch = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(mismatch["status"], "blocked")
        self.assertFalse((self.skills / "linked-skill").exists())

    def test_manifest_cannot_claim_another_receipt_or_control_directory(self):
        manifest = self.manifest("trusted\n", destination="another-skill")
        mismatch = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(mismatch["status"], "blocked")
        self.assertEqual(mismatch["error"], "skill_id_relative_directory_mismatch")

        manifest = self.manifest("trusted\n", destination=bundle.CONTROL_DIRECTORY)
        reserved = bundle.install_bundle(manifest, self.skills, source_root=self.source)
        self.assertEqual(reserved["status"], "blocked")
        self.assertEqual(reserved["error"], "relative_directory_reserved")

    def test_replacement_failure_rolls_back_old_managed_directory(self):
        first = self.manifest("first\n")
        bundle.install_bundle(first, self.skills, source_root=self.source)
        second = self.manifest("second\n", version="2.0.0")
        calls = 0

        def fail_target(source, destination):
            nonlocal calls
            calls += 1
            if Path(destination) == self.skills / "linked-skill" and calls == 2:
                raise OSError("simulated replacement failure")
            return original_replace(source, destination)

        original_replace = __import__("os").replace
        result = bundle.install_bundle(second, self.skills, source_root=self.source, replace=fail_target)
        self.assertEqual(self.one(result)["status"], "conflict")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_text(), "first\n")
        receipt = json.loads((self.skills / bundle.CONTROL_DIRECTORY / "receipts/linked-skill.json").read_text())
        self.assertEqual(receipt["version"], "1.0.0")

    def test_first_rename_and_receipt_failures_keep_old_target_and_receipt(self):
        first = self.manifest("first\n")
        bundle.install_bundle(first, self.skills, source_root=self.source)
        original_skill = (self.skills / "linked-skill/SKILL.md").read_bytes()
        receipt_path = self.skills / bundle.CONTROL_DIRECTORY / "receipts/linked-skill.json"
        original_receipt = receipt_path.read_bytes()
        second = self.manifest("second\n", version="2.0.0")
        original_replace = __import__("os").replace

        def fail_first_rename(source, destination):
            if Path(destination).name.startswith(".linked-skill.bundle-backup-"):
                raise OSError("simulated first rename failure")
            return original_replace(source, destination)

        rename_failure = bundle.install_bundle(second, self.skills, source_root=self.source, replace=fail_first_rename)
        self.assertEqual(self.one(rename_failure)["status"], "conflict")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_bytes(), original_skill)
        self.assertEqual(receipt_path.read_bytes(), original_receipt)

        def fail_receipt_write(source, destination):
            if Path(destination) == receipt_path:
                raise OSError("simulated receipt write failure")
            return original_replace(source, destination)

        receipt_failure = bundle.install_bundle(second, self.skills, source_root=self.source, replace=fail_receipt_write)
        self.assertEqual(self.one(receipt_failure)["status"], "conflict")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_bytes(), original_skill)
        self.assertEqual(receipt_path.read_bytes(), original_receipt)

    def test_target_changed_after_staging_is_not_overwritten(self):
        first = self.manifest("first\n")
        bundle.install_bundle(first, self.skills, source_root=self.source)
        second = self.manifest("second\n", version="2.0.0")
        original_stage = bundle._stage

        def stage_then_edit(*args, **kwargs):
            staged = original_stage(*args, **kwargs)
            (self.skills / "linked-skill/SKILL.md").write_text("changed during stage\n")
            return staged

        with mock.patch.object(bundle, "_stage", side_effect=stage_then_edit):
            result = bundle.install_bundle(second, self.skills, source_root=self.source)
        self.assertEqual(self.one(result)["status"], "conflict")
        self.assertEqual((self.skills / "linked-skill/SKILL.md").read_text(), "changed during stage\n")



class CombinedInstallerTests(unittest.TestCase):
    def test_combined_entrypoint_reports_dependencies_and_returns_correct_status(self):
        import install_local_skill as installer
        for remote_status, exit_code in (("ok", 0), ("attention", 2)):
            with self.subTest(status=remote_status), tempfile.TemporaryDirectory(prefix="dir-combined-") as raw:
                root = Path(raw) / "skills"
                output = io.StringIO()
                with mock.patch.object(sys, "argv", ["install_local_skill.py", "--skills-root", str(root), "--with-dependencies"]), \
                     mock.patch.object(installer.jingzao_updater, "sync_jingzao", return_value={"status": remote_status}) as sync, \
                     redirect_stdout(output):
                    code = installer.main()
                self.assertEqual(code, exit_code)
                sync.assert_called_once_with(root)
                text = output.getvalue()
                start = text.index('{\n  "dependencies"')
                report, _ = json.JSONDecoder().raw_decode(text[start:])
                self.assertEqual(report["dependencies"]["jingzao"]["status"], remote_status)
                self.assertEqual(report["dependencies"]["licensed_offline"]["status"], "ok")
                self.assertTrue((root / "dircreative/SKILL.md").is_file())
                self.assertTrue((root / "humanizer-zh/SKILL.md").is_file())
                self.assertIn("verify with:", text)


if __name__ == "__main__":
    unittest.main()
