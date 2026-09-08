from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_jingzao_updater as updater  # noqa: E402


class JingzaoUpdaterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="jingzao-updater-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "skills"

    @staticmethod
    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            [], 0,
            "a" * 40 + "\trefs/tags/v1.9.0\n" + "c" * 40 + "\trefs/tags/v1.9.0^{}\n",
            "",
        )

    @staticmethod
    def archive() -> bytes:
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w:gz") as tar:
            for name, body in (("jingzao-image-forge-ccc/SKILL.md", b"---\nname: jingzao-image-forge\n---\n# Jingzao\n"),
                               ("jingzao-image-forge-ccc/README.md", b"official\n")):
                info = tarfile.TarInfo(name)
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
        return raw.getvalue()

    def opener(self, request, timeout):
        self.assertEqual(timeout, 30)
        url = request.full_url if hasattr(request, "full_url") else request
        if url.endswith("/releases/latest"):
            data = b'{"tag_name":"v1.9.0","draft":false,"prerelease":false}'
        else:
            self.assertIn("/archive/" + "c" * 40 + ".tar.gz", url)
            data = self.archive()

        class Response:
            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def read(self): return data
        return Response()

    def test_check_reads_highest_official_stable_tag(self):
        result = updater.check_jingzao(self.root, runner=self.runner, opener=self.opener)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["official"]["tag"], "v1.9.0")
        self.assertEqual(result["official"]["revision"], "c" * 40)
        self.assertEqual(result["local"]["status"], "missing")

    def test_sync_installs_archive_without_executing_it(self):
        result = updater.sync_jingzao(self.root, runner=self.runner, opener=self.opener)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["install"]["skills"][0]["status"], "installed")
        self.assertEqual((self.root / "jingzao-image-forge/SKILL.md").read_text(), "---\nname: jingzao-image-forge\n---\n# Jingzao\n")

    def test_unmanaged_local_install_is_preserved(self):
        target = self.root / "jingzao-image-forge"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("local 1.8.1-local\n")
        result = updater.sync_jingzao(self.root, runner=self.runner, opener=self.opener)
        self.assertEqual(result["status"], "attention")
        self.assertEqual(result["install"]["skills"][0]["status"], "preserved")
        self.assertEqual((target / "SKILL.md").read_text(), "local 1.8.1-local\n")

    def test_latest_published_release_does_not_select_higher_unpublished_tag(self):
        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 0,
                "a" * 40 + "\trefs/tags/v1.9.0\n" + "b" * 40 + "\trefs/tags/v9.0.0\n", "")

        result = updater.check_jingzao(self.root, runner=runner, opener=self.opener)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["official"]["tag"], "v1.9.0")

    def test_draft_prerelease_and_invalid_revision_are_blocked(self):
        def release_opener(payload):
            def opener(request, timeout):
                data = payload if hasattr(request, "full_url") else self.archive()
                class Response:
                    def __enter__(self): return self
                    def __exit__(self, *_args): return False
                    def read(self): return data
                return Response()
            return opener

        for payload in (b'{"tag_name":"v1.9.0","draft":true,"prerelease":false}',
                        b'{"tag_name":"v1.9.0","draft":false,"prerelease":true}'):
            with self.subTest(payload=payload):
                result = updater.check_jingzao(self.root, runner=self.runner, opener=release_opener(payload))
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["error"], "official_stable_release_invalid")

        def bad_runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 0, "not-a-sha\trefs/tags/v1.9.0\n", "")
        result = updater.check_jingzao(self.root, runner=bad_runner, opener=self.opener)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["error"], "official_tag_revision_invalid")

    def test_local_edits_and_empty_receipt_are_conflicts_on_check(self):
        self.assertEqual(updater.sync_jingzao(self.root, runner=self.runner, opener=self.opener)["status"], "ok")
        target = self.root / updater.SKILL_ID / "SKILL.md"
        target.write_text("edited\n")
        edited = updater.check_jingzao(self.root, runner=self.runner, opener=self.opener)
        self.assertEqual(edited["local"]["status"], "conflict")
        self.assertEqual(edited["local"]["reason"], "local_edits_or_unexpected_files")
        target.write_text("---\nname: jingzao-image-forge\n---\n# Jingzao\n")
        receipt = self.root / updater.bundles.CONTROL_DIRECTORY / "receipts" / f"{updater.SKILL_ID}.json"
        document = __import__("json").loads(receipt.read_text())
        document["files"] = []
        receipt.write_text(__import__("json").dumps(document))
        invalid = updater.check_jingzao(self.root, runner=self.runner, opener=self.opener)
        self.assertEqual(invalid["local"]["status"], "conflict")
        self.assertEqual(invalid["local"]["reason"], "receipt_invalid")


if __name__ == "__main__":
    unittest.main()
