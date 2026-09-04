from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_request_scope_contract as contract  # noqa: E402


class RequestScopeContractTests(unittest.TestCase):
    def packet(self, delegated_prompt: str) -> dict:
        source = "直到生成视频之前的全部流程都要做完，剧本、图片资产、工作流和台账都实际产出；不生成最终视频。"
        return {
            "contract_id": "dircreative_request_scope_v1",
            "source_messages": [
                {
                    "message_id": "user-1",
                    "text": source,
                    "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                }
            ],
            "delegated_prompt": delegated_prompt,
            "delegated_prompt_sha256": hashlib.sha256(delegated_prompt.encode("utf-8")).hexdigest(),
            "declared_scope": {
                "media_scope": "pre_video_assets",
                "image_generation_authorized": True,
                "video_generation_authorized": False,
            },
        }

    def test_bad_dispatch_that_forbids_images_is_rejected(self):
        packet = self.packet("完整走到视频生成之前。不要生成图片或视频。")
        errors = contract.validate_packet(packet)
        self.assertIn("delegated_media_scope_mismatch", errors)
        self.assertIn("source_scope_excerpt_missing_from_delegation", errors)

    def test_verbatim_scope_and_matching_flags_pass(self):
        source = self.packet("")["source_messages"][0]["text"]
        delegated = f"原始用户范围：{source}\n按此范围执行，不扩大到最终视频生成。"
        self.assertEqual(contract.validate_packet(self.packet(delegated)), [])
        assessment = contract.assess_packet(self.packet(delegated))
        self.assertEqual(assessment["scope_consistency_status"], "pass")
        self.assertEqual(assessment["source_provenance"], "unverified")
        self.assertEqual(assessment["authorization_authority"], "none")

    def test_tampered_source_message_hash_is_rejected(self):
        source = self.packet("")["source_messages"][0]["text"]
        packet = self.packet(f"原始用户范围：{source}")
        packet["source_messages"][0]["sha256"] = "0" * 64
        self.assertIn("source_message_hash_mismatch:user-1", contract.validate_packet(packet))

    def test_required_method_cannot_disappear_from_delegation(self):
        source = self.packet("")["source_messages"][0]["text"]
        packet = self.packet(f"原始用户范围：{source}")
        packet["required_methods"] = ["sepia"]
        self.assertIn("required_method_missing:sepia", contract.validate_packet(packet))

    def test_oversized_source_message_is_rejected_before_scope_parsing(self):
        packet = self.packet("valid")
        packet["source_messages"][0]["text"] = "大" * (contract.MAX_SOURCE_MESSAGE_CHARS + 1)
        packet["source_messages"][0]["sha256"] = hashlib.sha256(
            packet["source_messages"][0]["text"].encode("utf-8")
        ).hexdigest()
        self.assertIn("source_message_too_large:user-1", contract.validate_packet(packet))

    def test_oversized_cli_packet_returns_json_failure_without_traceback(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "oversized.json"
            path.write_bytes(b"x" * (contract.MAX_PACKET_BYTES + 1))
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/dircreative_request_scope_contract.py"), str(path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn('"scope_consistency_status": "fail"', proc.stdout)


if __name__ == "__main__":
    unittest.main()
