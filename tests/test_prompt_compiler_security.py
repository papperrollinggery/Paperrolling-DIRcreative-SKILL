from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_prompt_compiler as compiler  # noqa: E402


class PromptCompilerSecurityTests(unittest.TestCase):
    def valid_payload(self) -> dict:
        return json.loads(
            (ROOT / "tests/fixtures/prompt-system/valid/minimal-character-scene-10s.json").read_text(
                encoding="utf-8"
            )
        )

    def test_project_file_rejects_parent_escape(self):
        payload = self.valid_payload()
        asset = payload["intake"]["supplied_assets"][0]
        asset.update(
            {
                "source_kind": "project_file",
                "source_locator": "../VERSION",
                "source_hash": "0" * 64,
            }
        )
        errors = compiler.semantic_errors(payload)
        self.assertTrue(any("project_file asset is invalid" in error for error in errors))

    def test_project_file_rejects_absolute_path(self):
        payload = self.valid_payload()
        asset = payload["intake"]["supplied_assets"][0]
        asset.update(
            {
                "source_kind": "project_file",
                "source_locator": "/etc/passwd",
                "source_hash": "0" * 64,
            }
        )
        errors = compiler.semantic_errors(payload)
        self.assertTrue(any("project_file asset is invalid" in error for error in errors))

    def test_prompt_ir_read_is_bounded(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "oversized.json"
            path.write_bytes(b"x" * (compiler.MAX_PROMPT_IR_BYTES + 1))
            with self.assertRaisesRegex(compiler.PromptContractError, "exceeds size limit"):
                compiler.load_prompt_ir(path)


if __name__ == "__main__":
    unittest.main()
