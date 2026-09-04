from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_humanization_execution_gate as gate  # noqa: E402


class HumanizationExecutionGateTests(unittest.TestCase):
    def plan(self) -> dict:
        return {
            "status": "ready",
            "resolved_operation": "write",
            "execution_status": "not_run",
            "text_revision_applied": False,
            "completion_claim_allowed": False,
            "provider_steps": [
                {"provider": "sepia", "authority": "new_draft", "operation": "write"},
                {
                    "provider": "dircreative",
                    "validator": "humanizer-zh",
                    "authority": "diagnostic_only",
                    "operation": "review",
                },
            ],
        }

    def test_ready_plan_without_execution_is_not_completion(self):
        result = gate.evaluate(self.plan(), None, base_dir=ROOT)
        self.assertEqual(result["execution_status"], "not_run")
        self.assertFalse(result["text_revision_applied"])
        self.assertFalse(result["completion_claim_allowed"])

    def test_missing_required_provider_execution_is_blocked(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            draft = root / "draft.md"
            final = root / "final.md"
            draft.write_text("机械的第一稿。", encoding="utf-8")
            final.write_text("修改后的文本。", encoding="utf-8")
            receipt = self.receipt(root, draft, final)
            receipt["provider_runs"] = [receipt["provider_runs"][1]]
            result = gate.evaluate(self.plan(), receipt, base_dir=root)
        self.assertEqual(result["execution_status"], "blocked")
        self.assertIn("required_provider_not_executed:sepia", result["reason_codes"])

    def test_bound_before_after_execution_remains_unverified(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            draft = root / "draft.md"
            final = root / "final.md"
            draft.write_text("机械的第一稿。", encoding="utf-8")
            final.write_text("她停了一下，才把后半句说完。", encoding="utf-8")
            result = gate.evaluate(
                self.plan(),
                self.receipt(root, draft, final),
                base_dir=root,
            )
        self.assertEqual(result["execution_status"], "applied_unverified")
        self.assertTrue(result["text_revision_applied"])
        self.assertFalse(result["completion_claim_allowed"])
        self.assertEqual(result["evidence_authority"], "self_reported_local_receipt")

    def receipt(self, root: Path, draft: Path, final: Path) -> dict:
        draft_hash = hashlib.sha256(draft.read_bytes()).hexdigest()
        final_hash = hashlib.sha256(final.read_bytes()).hexdigest()
        plan_hash = gate.canonical_sha256(self.plan())
        return {
            "contract_id": "humanization_execution_gate_v1",
            "plan_sha256": plan_hash,
            "draft_file": draft.relative_to(root).as_posix(),
            "draft_sha256": draft_hash,
            "result_file": final.relative_to(root).as_posix(),
            "result_sha256": final_hash,
            "provider_runs": [
                {
                    "provider": "sepia",
                    "authority": "new_draft",
                    "status": "executed",
                    "output_sha256": final_hash,
                },
                {
                    "provider": "humanizer-zh",
                    "authority": "diagnostic_only",
                    "status": "executed",
                    "output_sha256": final_hash,
                },
            ],
            "protected_content_diff": "pass",
            "overcorrection_check": "pass",
            "read_aloud_review": "pass",
            "status": "applied",
        }


if __name__ == "__main__":
    unittest.main()
