from __future__ import annotations

import json
import io
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_review_trust as review_trust  # noqa: E402


class ReviewTrustHostConfigTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts/dircreative_review_trust.py"), *args],
            capture_output=True,
            check=False,
            text=True,
        )

    def test_default_path_uses_host_config_and_missing_status_is_tool_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            registry = Path(raw) / "host/review-trust-registry.json"
            with patch.dict(os.environ, {"DIRCREATIVE_REVIEW_TRUST_REGISTRY": str(registry)}):
                self.assertEqual(review_trust.default_review_trust_registry_path(), registry)
            self.assertFalse(str(registry).startswith(str(ROOT / "skills/dircreative")))
            result = self.run_cli("status", "--registry", str(registry))
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "TOOL_BLOCKED")
            self.assertEqual(payload["registry_path"], str(registry))

    def test_public_key_provisioning_is_dry_run_then_atomic_apply(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            registry = root / "host/review-trust-registry.json"
            private_key = root / "review-private.pem"
            public_key = root / "review-public.pem"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
                capture_output=True,
                check=True,
            )
            common = (
                "provision-public-key",
                "--registry", str(registry),
                "--authority-id", "PROMPT-REVIEW-001",
                "--actor-id", "prompt-reviewer",
                "--public-key", str(public_key),
                "--allowed-purpose", "prompt_authority_review",
                "--allowed-source", "independent_review",
            )
            dry_run = self.run_cli(*common)
            self.assertEqual(dry_run.returncode, 0)
            self.assertFalse(registry.exists())
            applied = self.run_cli(*common, "--apply")
            self.assertEqual(applied.returncode, 0)
            self.assertTrue(registry.exists())
            self.assertNotIn("PRIVATE KEY", registry.read_text(encoding="utf-8"))
            status = self.run_cli("status", "--registry", str(registry))
            self.assertEqual(status.returncode, 0)
            self.assertEqual(json.loads(status.stdout)["authority_count"], 1)

    def test_private_key_rejected_before_python_reads_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            private_key = root / "review-private.pem"
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
                capture_output=True,
                check=True,
            )
            reads = 0
            original_read_bytes = Path.read_bytes

            def monitored_read_bytes(path: Path) -> bytes:
                nonlocal reads
                reads += 1
                return original_read_bytes(path)

            args = Namespace(
                registry=root / "host/review-trust-registry.json",
                authority_id="PROMPT-REVIEW-PRIVATE",
                actor_id="prompt-reviewer",
                authority_kind="human_reviewer",
                public_key=private_key,
                allowed_purpose=["prompt_authority_review"],
                allowed_source=["independent_review"],
                apply=False,
            )
            with patch.object(Path, "read_bytes", monitored_read_bytes), redirect_stdout(io.StringIO()):
                result = review_trust.cli_provision(args)
            self.assertEqual(result, 2)
            self.assertEqual(reads, 0)

    def test_shipped_empty_template_status_is_tool_blocked(self) -> None:
        result = self.run_cli(
            "status",
            "--registry",
            str(review_trust.TEMPLATE_REGISTRY_PATH),
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "TOOL_BLOCKED")
        self.assertEqual(payload["reason"], "review_trust_registry_empty")
        self.assertFalse(payload["capabilities"]["prompt_authority_review"])


if __name__ == "__main__":
    unittest.main()
