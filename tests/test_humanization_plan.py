from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_humanization_plan as humanization  # noqa: E402


class HumanizationPlanTests(unittest.TestCase):
    @staticmethod
    def preservation(*, document_type="report", status="ready"):
        source_text = "版本号保持为 0.7.1。\n本说明用于解释这次改动解决了什么问题。"
        if document_type == "screenplay":
            source_text += "\n角色问：何为长生？"
        coverage = {
            "facts": "covered",
            "claims": "not_present",
            "intent": "covered",
            "quotations": "not_present",
            "dialogue": "not_present",
            "protected_spans": "not_present",
        }
        entries = [
            {
                "entry_id": "FACT-001",
                "kind": "fact",
                "text": "版本号保持为 0.7.1。",
                "text_sha256": hashlib.sha256("版本号保持为 0.7.1。".encode()).hexdigest(),
                "evidence_quote": "版本号保持为 0.7.1。",
                "evidence_start": source_text.index("版本号保持为 0.7.1。"),
                "evidence_end": source_text.index("版本号保持为 0.7.1。")
                + len("版本号保持为 0.7.1。"),
            },
            {
                "entry_id": "INTENT-001",
                "kind": "intent",
                "text": "解释这次改动解决了什么问题。",
                "text_sha256": hashlib.sha256(
                    "解释这次改动解决了什么问题。".encode()
                ).hexdigest(),
                "evidence_quote": "解释这次改动解决了什么问题",
                "evidence_start": source_text.index("解释这次改动解决了什么问题"),
                "evidence_end": source_text.index("解释这次改动解决了什么问题")
                + len("解释这次改动解决了什么问题"),
            },
        ]
        if document_type == "screenplay":
            dialogue = "何为长生？"
            entries.append(
                {
                    "entry_id": "DIALOGUE-001",
                    "kind": "dialogue",
                    "text": dialogue,
                    "text_sha256": hashlib.sha256(dialogue.encode()).hexdigest(),
                    "evidence_quote": dialogue,
                    "evidence_start": source_text.index(dialogue),
                    "evidence_end": source_text.index(dialogue) + len(dialogue),
                }
            )
            coverage["dialogue"] = "covered"
        if status == "missing":
            coverage = {field: "not_present" for field in coverage}
        payload = {
            "status": status,
            "set_id": "PRESERVE-001" if status == "ready" else None,
            "source_text": source_text if status == "ready" else None,
            "source_text_sha256": (
                hashlib.sha256(source_text.encode()).hexdigest()
                if status == "ready"
                else None
            ),
            "coverage": coverage,
            "entries": entries if status == "ready" else [],
        }
        payload["set_sha256"] = (
            hashlib.sha256(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            if status == "ready"
            else None
        )
        return payload

    def spec(self, **overrides):
        base = {
            "schema_version": "1.0",
            "target_id": "TEXT-001",
            "operation": "auto",
            "text_kind": "professional",
            "document_type": "report",
            "language": "zh",
            "scope": "passage",
            "length_chars": 240,
            "structural_defects": "local",
            "source_mode": "existing",
            "voice_profile_status": "locked",
            "venue_corpus_status": "available",
            "sepia_requested": False,
            "validation_required": True,
            "voice_skill_explicit": False,
            "bounded_preference": "auto",
            "preservation": self.preservation(),
            "author_model": {
                "family": "unknown",
                "version": "unknown",
                "source": "unknown",
            },
            "executor_model": {
                "family": "OpenAI GPT",
                "version": "5.6",
                "source": "system",
            },
        }
        base.update(overrides)
        return base

    def test_short_local_chinese_revision_stays_bounded(self):
        plan = humanization.build_plan(self.spec())
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["strategy"], "bounded_human_language")
        self.assertEqual(plan["resolved_operation"], "refactor")
        self.assertEqual(plan["provider_steps"][0]["provider"], "shuorenhua")
        self.assertFalse(any(step["provider"] == "sepia" for step in plan["provider_steps"]))

    def test_short_chinese_review_uses_diagnosis_only_scenario(self):
        plan = humanization.build_plan(self.spec(operation="review"))
        self.assertEqual(plan["provider_steps"][0]["scenario_id"], "human_language_diagnosis")
        self.assertEqual(plan["provider_steps"][0]["provider"], "dircreative")
        self.assertEqual(plan["provider_steps"][0]["validator"], "humanizer-zh")
        self.assertEqual(plan["provider_steps"][0]["authority"], "diagnostic_only")

    def test_document_screenplay_uses_layered_sepias_without_injecting_corpus_moves(self):
        plan = humanization.build_plan(
            self.spec(
                operation="refactor",
                text_kind="narrative",
                document_type="screenplay",
                scope="document",
                length_chars=9000,
                structural_defects="systemic",
                preservation=self.preservation(document_type="screenplay"),
            )
        )
        self.assertEqual(plan["strategy"], "sepia_layered_humanization")
        self.assertEqual(plan["provider_steps"][0]["provider"], "sepia")
        self.assertEqual(plan["provider_steps"][0]["operation"], "review")
        self.assertEqual(plan["provider_steps"][0]["authority"], "diagnostic_only")
        self.assertEqual(plan["provider_steps"][1]["operation"], "refactor")
        self.assertEqual(
            plan["provider_steps"][1]["authority"],
            "pending_evidence_bound_edit",
        )
        self.assertEqual(plan["humanization_profile"], "narrative")
        self.assertIn("subplot_insertion", plan["humanization_guard"]["forbidden_auto_moves"])
        self.assertIn(
            "nonlinear_time_injection",
            plan["humanization_guard"]["forbidden_auto_moves"],
        )
        self.assertIn(
            "rarity_move_injection",
            plan["humanization_guard"]["forbidden_auto_moves"],
        )
        self.assertEqual(
            plan["provider_steps"][1]["humanization_guard_sha256"],
            plan["humanization_guard"]["guard_sha256"],
        )
        self.assertTrue(plan["calibration"]["cluster_before_rewrite"])
        self.assertNotIn("human_leaning_move_budget", plan["calibration"])

    def test_release_review_loads_domain_and_never_edits(self):
        plan = humanization.build_plan(
            self.spec(
                operation="review",
                document_type="release_notes",
                scope="document",
                length_chars=1400,
                sepia_requested=True,
            )
        )
        self.assertEqual(plan["humanization_profile"], "release_notes")
        self.assertIn("references/domains/release-notes.md", plan["reference_pack"])
        self.assertEqual(plan["provider_steps"][0]["authority"], "diagnostic_only")
        self.assertEqual(plan["pass_order"][-1], "stop_without_edit")

    def test_recreate_requires_locked_fact_claim_and_intent_set(self):
        plan = humanization.build_plan(
            self.spec(
                operation="recreate",
                scope="document",
                length_chars=2200,
                sepia_requested=True,
                preservation=self.preservation(status="missing"),
            )
        )
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("recreate_preservation_set_required", plan["reason_codes"])

    def test_new_text_auto_selects_write_and_architecture_before_draft(self):
        plan = humanization.build_plan(
            self.spec(
                source_mode="new",
                operation="auto",
                text_kind="narrative",
                document_type="treatment",
                scope="document",
                length_chars=0,
                structural_defects="unknown",
            )
        )
        self.assertEqual(plan["resolved_operation"], "write")
        self.assertLess(plan["pass_order"].index("domain_and_architecture"), plan["pass_order"].index("draft"))
        self.assertIn(
            "rarity_move_injection",
            plan["humanization_guard"]["forbidden_auto_moves"],
        )

    def test_model_identity_is_never_inferred_from_target_prose(self):
        plan = humanization.build_plan(
            self.spec(
                author_model={
                    "family": "Claude",
                    "version": "Fable 5.1",
                    "source": "inferred_from_text",
                }
            )
        )
        self.assertEqual(plan["status"], "invalid")
        self.assertTrue(any(error.startswith("model_identity_source_invalid:") for error in plan["errors"]))

    def test_recreate_binds_verified_preservation_content_and_source(self):
        preservation = self.preservation()
        plan = humanization.build_plan(
            self.spec(
                operation="recreate",
                scope="document",
                length_chars=2200,
                structural_defects="systemic",
                sepia_requested=True,
                preservation=preservation,
            )
        )
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["preservation"]["set_sha256"], preservation["set_sha256"])
        self.assertEqual(
            plan["provider_steps"][1]["preservation_set_sha256"],
            preservation["set_sha256"],
        )
        self.assertEqual(
            plan["provider_steps"][1]["source_text_sha256"],
            preservation["source_text_sha256"],
        )

    def test_recreate_rejects_self_claimed_ready_set_with_tampered_entry(self):
        preservation = self.preservation()
        preservation["entries"][0]["text"] = "版本号改成 9.9.9。"
        plan = humanization.build_plan(
            self.spec(operation="recreate", scope="document", preservation=preservation)
        )
        self.assertEqual(plan["status"], "invalid")
        self.assertTrue(
            any(error.startswith("preservation_entry_hash_mismatch:") for error in plan["errors"])
        )

    def test_recreate_rejects_empty_source_even_with_self_consistent_hashes(self):
        preservation = self.preservation()
        preservation["source_text"] = ""
        preservation["source_text_sha256"] = hashlib.sha256(b"").hexdigest()
        preservation["set_sha256"] = humanization.canonical_sha256(
            {key: value for key, value in preservation.items() if key != "set_sha256"}
        )
        plan = humanization.build_plan(
            self.spec(operation="recreate", scope="document", preservation=preservation)
        )
        self.assertEqual(plan["status"], "invalid")
        self.assertTrue(
            any(error.startswith("preservation_source_text_required:") for error in plan["errors"])
        )

    def test_layered_chinese_validation_diagnoses_without_second_rewrite(self):
        plan = humanization.build_plan(
            self.spec(
                operation="refactor",
                scope="document",
                length_chars=1800,
                structural_defects="systemic",
                sepia_requested=True,
            )
        )
        rewrite_steps = [
            step for step in plan["provider_steps"] if step["authority"] != "diagnostic_only"
        ]
        validation = plan["provider_steps"][-1]
        self.assertEqual(len([s for s in rewrite_steps if s["provider"] == "shuorenhua"]), 1)
        self.assertEqual(validation["provider"], "dircreative")
        self.assertEqual(validation["validator"], "humanizer-zh")
        self.assertEqual(validation["scenario_id"], "human_language_diagnosis")
        self.assertEqual(validation["authority"], "diagnostic_only")

    def test_bounded_fidelity_preference_routes_de_ai_writing_for_chinese(self):
        plan = humanization.build_plan(self.spec(bounded_preference="fidelity"))
        self.assertEqual(plan["strategy"], "bounded_human_language")
        self.assertEqual(plan["provider_steps"][0]["provider"], "de-AI-writing")
        self.assertEqual(plan["provider_steps"][0]["scenario_id"], "bounded_fidelity_revision")

    def test_bounded_english_uses_internal_method_not_chinese_provider(self):
        plan = humanization.build_plan(self.spec(language="en"))
        self.assertEqual(plan["strategy"], "bounded_human_language")
        self.assertEqual(plan["provider_steps"][0]["provider"], "dircreative")
        self.assertEqual(
            plan["provider_steps"][0]["scenario_id"],
            "bounded_english_human_language",
        )
        self.assertEqual(plan["provider_steps"][0]["mode"], "fast")

    def test_model_fingerprint_matching_is_exact_not_substring(self):
        for family, version in (
            ("notgpt", "5.6"),
            ("OpenAI GPT", "15.60"),
            ("Claude", "Fable 5.10"),
        ):
            with self.subTest(family=family, version=version):
                plan = humanization.build_plan(
                    self.spec(
                        executor_model={
                            "family": family,
                            "version": version,
                            "source": "system",
                        }
                    )
                )
                self.assertNotEqual(
                    plan["model_identity"]["executor"]["prose_layer"], "operative"
                )

    def test_document_narrative_edit_waits_for_real_voice_profile(self):
        plan = humanization.build_plan(
            self.spec(
                operation="refactor",
                text_kind="narrative",
                document_type="screenplay",
                scope="document",
                length_chars=2400,
                voice_profile_status="missing",
                preservation=self.preservation(document_type="screenplay"),
            )
        )
        self.assertEqual(plan["status"], "blocked")
        self.assertIn(
            "narrative_voice_profile_required_before_edit",
            plan["reason_codes"],
        )

    def test_guard_rejects_caller_added_overcorrection_rule(self):
        guard = humanization.build_humanization_guard("screenplay")
        guard["forbidden_auto_moves"].append("remove_all_metaphor")
        guard["guard_sha256"] = humanization.canonical_sha256(
            {key: value for key, value in guard.items() if key != "guard_sha256"}
        )
        errors, _normalized = humanization.validate_humanization_guard(
            guard,
            "screenplay",
        )
        self.assertTrue(
            any(error.startswith("humanization_guard_moves_not_canonical:") for error in errors)
        )

    def test_text_kind_and_document_type_cannot_select_conflicting_profile(self):
        plan = humanization.build_plan(
            self.spec(text_kind="narrative", document_type="release_notes")
        )
        self.assertEqual(plan["status"], "invalid")
        self.assertTrue(
            any(error.startswith("text_kind_document_mismatch:") for error in plan["errors"])
        )


if __name__ == "__main__":
    unittest.main()
