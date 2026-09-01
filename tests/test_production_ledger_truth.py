from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ai_film_production_ledger as ledger  # noqa: E402
import dircreative_storyboard_coverage as storyboard_coverage  # noqa: E402
import tests.test_panel_jingzao_binding as panel_fixture  # noqa: E402


class ProductionLedgerTruthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handoff_runtime: dict[Path, dict] = {}

    def selected_document(self) -> dict:
        document = json.loads(
            (ROOT / "tests/fixtures/production-ledger/valid-ledger.json").read_text(encoding="utf-8")
        )
        document["project_id"] = "binding-test"
        for item in document["attempts"]:
            item["project_id"] = "binding-test"
            item["scene_id"] = "FOUNDRY-B"
            item["shot_id"] = "S07"
        attempt = document["attempts"][0]
        attempt["source_status"] = "project"
        attempt["authorized_execution_state"] = "authorized"
        attempt["asset_bindings"].append({
            "asset_id": "BELL-01",
            "version": "v1",
            "relative_path": "assets/bell-01.png",
            "sha256": "e" * 64,
            "source_status": "available",
            "attached": True,
        })
        attempt["asset_bindings"].append({
            "asset_id": "FOUNDRY-B",
            "version": "v1",
            "relative_path": "assets/foundry-b.png",
            "sha256": "b" * 64,
            "source_status": "available",
            "attached": True,
        })
        attempt["output_manifest"] = [{
            "output_id": "S07-P01-v1",
            "relative_path": "outputs/S07-P01-v1.png",
            "sha256": "c" * 64,
            "receipt_source": "external_verified",
            "receipt_id": "RECEIPT-GEN",
        }]
        attempt["review_evidence"] = [{
            "review_id": "REVIEW-S07-P01",
            "verdict": "accept",
            "sha256": "d" * 64,
            "source": "independent_review",
            "receipt_id": "RECEIPT-REVIEW",
        }]
        document["state_events"] = [
            {"event_id": "E1", "attempt_id": "ATTEMPT-001", "state": "planned", "evidence_source": "none", "evidence_refs": [], "review_verdict": "not_applicable", "created_at": "2026-08-24T00:00:00Z", "actor": "dircreative"},
            {"event_id": "E2", "attempt_id": "ATTEMPT-001", "state": "attached", "evidence_source": "producer", "evidence_refs": ["PROMPT-GU01-v1"], "review_verdict": "not_applicable", "created_at": "2026-08-24T00:00:01Z", "actor": "dircreative"},
            {"event_id": "E3", "attempt_id": "ATTEMPT-001", "state": "executed", "evidence_source": "host_observation", "evidence_refs": ["RECEIPT-EXEC"], "review_verdict": "not_applicable", "created_at": "2026-08-24T00:00:02Z", "actor": "media-host"},
            {"event_id": "E4", "attempt_id": "ATTEMPT-001", "state": "generated_verified", "evidence_source": "external_verified", "evidence_refs": ["RECEIPT-GEN"], "review_verdict": "not_applicable", "created_at": "2026-08-24T00:00:03Z", "actor": "media-host"},
            {"event_id": "E5", "attempt_id": "ATTEMPT-001", "state": "selected", "evidence_source": "independent_review", "evidence_refs": ["RECEIPT-REVIEW"], "review_verdict": "accept", "created_at": "2026-08-24T00:00:04Z", "actor": "reviewer"},
            document["state_events"][1],
        ]
        document["genesis_sha256"] = ledger.genesis_sha256(document)
        return document

    def full_handoff_packet(self, document: dict, artifact_root: Path) -> dict:
        key = artifact_root.resolve()
        if key in self.handoff_runtime:
            return self.handoff_runtime[key]["packet"]
        builder = panel_fixture.PanelJingzaoBindingTests(methodName="runTest")
        builder.setUp()
        self.addCleanup(builder.doCleanups)
        packet, _ = builder.truth_document(artifact_root)
        packet_path = artifact_root / "handoff/full-storyboard-frame-packet.json"
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_payload = (json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        packet_path.write_bytes(packet_payload)
        registry = builder.review_runtime[artifact_root.resolve()]["registry"]
        self.handoff_runtime[key] = {
            "packet": packet,
            "packet_path": packet_path,
            "packet_sha256": hashlib.sha256(packet_payload).hexdigest(),
            "registry": registry,
        }
        attempt = document["attempts"][0]
        target = next(frame for frame in packet["frames"] if frame["frame_id"] == "S07-P01")
        prompt_manifest = json.loads(
            (artifact_root / packet["output_spec"]["prompt_manifest_relative_path"]).read_text(encoding="utf-8")
        )
        prompt_entry = next(item for item in prompt_manifest["frame_prompts"] if item["frame_id"] == "S07-P01")
        attempt["prompt_artifact"]["prompt_text"] = prompt_entry["prompt"]
        attempt["prompt_artifact"]["prompt_sha256"] = prompt_entry["prompt_sha256"]
        role_by_id = {item["asset_id"]: item for item in target["reference_roles"]}
        for asset_id in ("BELL-01", "FOUNDRY-B"):
            role = role_by_id[asset_id]
            binding = next(item for item in attempt["asset_bindings"] if item["asset_id"] == asset_id)
            binding["relative_path"] = role["attachment"]["relative_path"]
            binding["sha256"] = role["attachment"]["sha256"]
        return packet

    def execution_manifest(
        self,
        document: dict,
        artifact_root: Path,
        *,
        status: str = "ready",
    ) -> dict:
        attempt = document["attempts"][0]
        packet = self.full_handoff_packet(document, artifact_root)
        runtime = self.handoff_runtime[artifact_root.resolve()]
        frame = next(item for item in packet["frames"] if item["frame_id"] == "S07-P01")
        prompt_manifest_path = artifact_root / packet["output_spec"]["prompt_manifest_relative_path"]
        prompt_manifest = json.loads(prompt_manifest_path.read_text(encoding="utf-8"))
        prompt_entry = next(item for item in prompt_manifest["frame_prompts"] if item["frame_id"] == "S07-P01")
        support = frame["truth_contract"]["support"]
        truth = {
            "revision_id": "S07-TRUTH-v2",
            "revision_sha256": ledger.canonical_sha256(frame["truth_contract"]),
            "status": status,
            "scene_asset_id": frame["truth_contract"]["scene_asset_id"],
            "support": {
                key: support[key]
                for key in ("status", "subject_asset_id", "anchor_asset_id", "visibility")
            },
            "parent_attempt_ids": [],
            "handoff_truth_artifact": {
                "relative_path": str(runtime["packet_path"].relative_to(artifact_root)),
                "sha256": runtime["packet_sha256"],
                "frame_id": frame["frame_id"],
            },
        }
        attachments = [
            {
                "asset_id": item["source_id"],
                "role": item["role"],
                "relative_path": item["relative_path"],
                "sha256": item["sha256"],
            }
            for item in prompt_entry["reference_inputs"]
        ]
        return {
            "prompt_sha256": attempt["prompt_artifact"]["prompt_sha256"],
            "ordered_attachments": attachments,
            "attachment_manifest_sha256": ledger.canonical_sha256(attachments),
            "scene_support_truth": truth,
        }

    def make_production_packet(self, document: dict, artifact_root: Path) -> Path:
        packet = self.full_handoff_packet(document, artifact_root)
        runtime = self.handoff_runtime[artifact_root.resolve()]
        provider_temp = tempfile.TemporaryDirectory(prefix="dircreative-handoff-provider-")
        self.addCleanup(provider_temp.cleanup)
        provider_root = Path(provider_temp.name)
        skill_payload = b"fixture jingzao provider\n"
        (provider_root / "SKILL.md").write_bytes(skill_payload)
        packet["provider_skill"]["sha256"] = hashlib.sha256(skill_payload).hexdigest()
        for index, item in enumerate(packet["reference_reads"]):
            payload = f"provider reference {index}\n".encode("utf-8")
            path = provider_root / item["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            item["bytes"] = len(payload)
            item["sha256"] = hashlib.sha256(payload).hexdigest()
        for binding, payload in (
            (packet["input_spec"], b"production DIR input spec\n"),
            (packet["output_spec"], b"production Jingzao output spec\n"),
        ):
            path = artifact_root / binding["relative_path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            binding["sha256"] = hashlib.sha256(payload).hexdigest()
        packet["delivery_consumption"]["consumed_spec_sha256"] = packet["output_spec"]["sha256"]
        packet["fixture_only"] = False
        packet_payload = (json.dumps(packet, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        runtime["packet_path"].write_bytes(packet_payload)
        runtime["packet_sha256"] = hashlib.sha256(packet_payload).hexdigest()
        return provider_root

    def semantic_review(
        self,
        document: dict,
        *,
        scene_truth: str = "pass",
        support_visible: str = "pass",
        contamination: str = "absent",
        parent_checks: list[dict] | None = None,
    ) -> dict:
        attempt = document["attempts"][0]
        payload = {
            "output_sha256": attempt["output_manifest"][0]["sha256"],
            "truth_revision_sha256": attempt["execution_input_manifest"]["scene_support_truth"]["revision_sha256"],
            "scene_truth": scene_truth,
            "support_visible": support_visible,
            "forbidden_background_ground_contamination": contamination,
            "parent_checks": parent_checks or [],
        }
        payload["review_sha256"] = ledger.canonical_sha256(payload)
        return payload

    def bind_risk(
        self,
        document: dict,
        artifact_root: Path,
        *,
        actual_risk: str = "high",
        declared_risk: str | None = None,
    ) -> None:
        attempt = document["attempts"][0]
        if actual_risk == "high":
            packet = self.full_handoff_packet(document, artifact_root)
            frame = next(item for item in packet["frames"] if item["frame_id"] == "S07-P01")
            coverage_relative = frame["panel_context"]["coverage_file"]
            document["attempts"][0]["execution_risk_binding"] = {
                "source_contract_id": "storyboard_coverage_v1",
                "relative_path": coverage_relative,
                "sha256": frame["panel_context"]["coverage_sha256"],
                "panel_id": frame["panel_context"]["panel_id"],
                "requirement_id": "S07-P01-truth",
                "declared_risk": declared_risk or actual_risk,
            }
            return
        shot_id = attempt["shot_id"]
        cards = {"cards": [{"shot_id": shot_id, "timecode": "00:00-00:03"}]}
        cards_path = artifact_root / "coverage/S07-cards.json"
        cards_path.parent.mkdir(parents=True, exist_ok=True)
        cards_path.write_text(json.dumps(cards), encoding="utf-8")
        coverage = {
            "schema_version": "1.0",
            "project_id": attempt["project_id"],
            "frame_rate_fps": 25,
            "scope": "whole_film",
            "shot_cards_file": "coverage/S07-cards.json",
            "shot_cards_sha256": storyboard_coverage.json_hash(cards),
            "requirements": [{
                "requirement_id": "S07-support",
                "source_anchor": f"cards:{shot_id}",
                "kind": "action",
                "shot_ids": [shot_id],
                "phases": ["contact"],
                "risk": actual_risk,
                "image_required": True,
            }],
            "panels": [{
                "panel_id": "S07-P01",
                "shot_id": shot_id,
                "requirement_id": "S07-support",
                "phase": "contact",
                "at_seconds": 1.0,
                "state": "bell visibly suspended",
                "camera_setup": "wide",
                "view_subject": "bell",
                "gaze_target": "foundry overhead",
                "axis_id": "foundry",
                "axis_side": "north",
                "look_direction": "center",
                "image": {"status": "planned"},
            }],
        }
        payload = (json.dumps(coverage, sort_keys=True) + "\n").encode("utf-8")
        path = artifact_root / "coverage/S07.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        document["attempts"][0]["execution_risk_binding"] = {
            "source_contract_id": "storyboard_coverage_v1",
            "relative_path": "coverage/S07.json",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "panel_id": "S07-P01",
            "requirement_id": "S07-support",
            "declared_risk": declared_risk or actual_risk,
        }

    def errors(
        self,
        document: dict,
        artifact_root: Path | None = None,
        *,
        handoff_provider_root: Path | None = None,
        trusted_provider_catalog_roots: tuple[Path, ...] | None = None,
    ) -> list[str]:
        document["genesis_sha256"] = ledger.genesis_sha256(document)
        runtime = self.handoff_runtime.get(artifact_root.resolve()) if artifact_root else None
        return ledger.validate(
            document,
            artifact_root=artifact_root,
            _review_trust_registry_path=(runtime["registry"] if runtime else None),
            handoff_provider_root=handoff_provider_root,
            _trusted_handoff_provider_catalog_roots=trusted_provider_catalog_roots,
        )

    def test_high_risk_selected_candidate_requires_exact_execution_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            errors = self.errors(document, root)
            self.assertTrue(any(error.startswith("selected_execution_input_manifest_missing:") for error in errors))

            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            manifest["prompt_sha256"] = "f" * 64
            document["attempts"][0]["execution_input_manifest"] = manifest
            self.assertTrue(any(error.startswith("execution_prompt_hash_mismatch:") for error in self.errors(document, root)))

            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            manifest["attachment_manifest_sha256"] = "f" * 64
            document["attempts"][0]["execution_input_manifest"] = manifest
            self.assertTrue(any(error.startswith("execution_attachment_manifest_hash_mismatch:") for error in self.errors(document, root)))

    def test_high_risk_cannot_claim_low_or_omit_upstream_binding(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root, actual_risk="high", declared_risk="low")
            self.assertTrue(any(error.startswith("execution_risk_mismatch:") for error in self.errors(document, root)))

            document = self.selected_document()
            document["attempts"][0]["execution_input_manifest"] = self.execution_manifest(document, root)
            self.assertTrue(any(error.startswith("selected_execution_risk_binding_missing:") for error in self.errors(document, root)))

            document = self.selected_document()
            self.assertTrue(any(error.startswith("selected_execution_risk_binding_missing:") for error in self.errors(document, root)))

            document = self.selected_document()
            self.bind_risk(document, root)
            document["attempts"][0]["execution_risk_binding"]["relative_path"] = "coverage/missing.json"
            self.assertTrue(any(error.startswith("execution_risk_source_invalid:") for error in self.errors(document, root)))

    def test_risk_binding_rejects_cross_project_and_shot_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for field, value in (("project_id", "PROJECT-OTHER"), ("shot_id", "SH99")):
                document = self.selected_document()
                self.bind_risk(document, root)
                binding = document["attempts"][0]["execution_risk_binding"]
                risk_path = root / binding["relative_path"]
                risk_source = json.loads(risk_path.read_text(encoding="utf-8"))
                if field == "project_id":
                    risk_source["project_id"] = value
                else:
                    second_shot = risk_source["requirements"][1]["shot_ids"][0]
                    cards = {"cards": [
                        {"shot_id": value, "timecode": "00:00-00:03"},
                        {"shot_id": second_shot, "timecode": "00:03-00:06"},
                    ]}
                    (root / risk_source["shot_cards_file"]).write_text(json.dumps(cards), encoding="utf-8")
                    risk_source["shot_cards_sha256"] = storyboard_coverage.json_hash(cards)
                    risk_source["requirements"][0]["shot_ids"] = [value]
                    risk_source["panels"][0]["shot_id"] = value
                payload = (json.dumps(risk_source, sort_keys=True) + "\n").encode("utf-8")
                risk_path.write_bytes(payload)
                binding["sha256"] = hashlib.sha256(payload).hexdigest()
                self.assertTrue(any(
                    error.startswith("execution_risk_scope_mismatch:")
                    for error in self.errors(document, root)
                ))

            document = self.selected_document()
            self.bind_risk(document, root)
            binding = document["attempts"][0]["execution_risk_binding"]
            risk_path = root / binding["relative_path"]
            invalid_coverage = json.loads(risk_path.read_text(encoding="utf-8"))
            invalid_coverage.pop("shot_cards_file")
            payload = (json.dumps(invalid_coverage, sort_keys=True) + "\n").encode("utf-8")
            risk_path.write_bytes(payload)
            binding["sha256"] = hashlib.sha256(payload).hexdigest()
            self.assertTrue(any(error.startswith("execution_risk_source_invalid:") for error in self.errors(document, root)))

    def test_full_handoff_packet_required_and_revalidated(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            document["attempts"][0]["execution_input_manifest"] = manifest
            self.assertFalse(any(
                error.startswith("execution_handoff_")
                for error in self.errors(document, root)
            ))

            runtime = self.handoff_runtime[root.resolve()]
            wrapper = {
                "contract_id": "storyboard_frame_to_jingzao_v1",
                "frame_id": "S07-P01",
                "truth_contract": {"risk": "high"},
            }
            payload = (json.dumps(wrapper, sort_keys=True) + "\n").encode("utf-8")
            runtime["packet_path"].write_bytes(payload)
            manifest["scene_support_truth"]["handoff_truth_artifact"]["sha256"] = hashlib.sha256(payload).hexdigest()
            self.assertTrue(any(
                error.startswith("execution_handoff_packet_invalid:")
                for error in self.errors(document, root)
            ))

    def test_production_packet_requires_explicit_handoff_provider_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            provider_root = self.make_production_packet(document, root)
            manifest = self.execution_manifest(document, root)
            document["attempts"][0]["execution_input_manifest"] = manifest
            packet = self.handoff_runtime[root.resolve()]["packet"]
            self.assertIs(packet["fixture_only"], False)
            self.assertTrue(any(
                error.startswith("execution_handoff_packet_invalid:")
                for error in self.errors(document, root)
            ))
            self.assertFalse(any(
                error.startswith("execution_handoff_")
                for error in self.errors(
                    document,
                    root,
                    handoff_provider_root=provider_root,
                    trusted_provider_catalog_roots=(provider_root,),
                )
            ))
            document["genesis_sha256"] = ledger.genesis_sha256(document)
            ledger_path = root / "production-ledger.json"
            previous_path = root / "production-ledger-previous.json"
            ledger_path.write_text(json.dumps(document), encoding="utf-8")
            previous_path.write_text(json.dumps(document), encoding="utf-8")
            registry = self.handoff_runtime[root.resolve()]["registry"]
            command = [
                sys.executable,
                str(ROOT / "scripts/ai_film_production_ledger.py"),
                "validate",
                str(ledger_path),
                "--previous",
                str(previous_path),
                "--artifact-root",
                str(root),
                "--review-trust-registry",
                str(registry),
            ]
            without_provider = json.loads(subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
            ).stdout)
            self.assertTrue(any(error.startswith("execution_handoff_packet_invalid:") for error in without_provider["errors"]))
            with_provider = json.loads(subprocess.run(
                [*command, "--handoff-provider-root", str(provider_root)],
                capture_output=True,
                check=False,
                text=True,
            ).stdout)
            self.assertTrue(any(error.startswith("execution_handoff_packet_invalid:") for error in with_provider["errors"]))

    def test_production_provider_must_be_installed_and_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            artifact_root = base / "artifacts"
            artifact_root.mkdir()
            document = self.selected_document()
            self.bind_risk(document, artifact_root)
            provider_root = self.make_production_packet(document, artifact_root)
            document["attempts"][0]["execution_input_manifest"] = self.execution_manifest(document, artifact_root)

            unregistered = self.errors(
                document,
                artifact_root,
                handoff_provider_root=provider_root,
                trusted_provider_catalog_roots=(),
            )
            self.assertTrue(any("provider_root_not_installed" in error for error in unregistered))

            registered = self.errors(
                document,
                artifact_root,
                handoff_provider_root=provider_root,
                trusted_provider_catalog_roots=(provider_root,),
            )
            self.assertFalse(any(error.startswith("execution_handoff_") for error in registered))

            inside_provider = artifact_root / "provider"
            inside_provider.mkdir()
            inside_errors = self.errors(
                document,
                artifact_root,
                handoff_provider_root=inside_provider,
                trusted_provider_catalog_roots=(inside_provider,),
            )
            self.assertTrue(any("provider_artifact_root_overlap" in error for error in inside_errors))

            containing_provider = base / "containing-provider"
            nested_artifact = containing_provider / "artifacts"
            nested_artifact.mkdir(parents=True)
            nested_document = self.selected_document()
            self.bind_risk(nested_document, nested_artifact)
            self.make_production_packet(nested_document, nested_artifact)
            nested_document["attempts"][0]["execution_input_manifest"] = self.execution_manifest(nested_document, nested_artifact)
            containing_errors = self.errors(
                nested_document,
                nested_artifact,
                handoff_provider_root=containing_provider,
                trusted_provider_catalog_roots=(containing_provider,),
            )
            self.assertTrue(any("provider_artifact_root_overlap" in error for error in containing_errors))

            symlink_target = artifact_root / "symlink-provider-target"
            symlink_target.mkdir()
            provider_link = base / "provider-link"
            provider_link.symlink_to(symlink_target, target_is_directory=True)
            symlink_errors = self.errors(
                document,
                artifact_root,
                handoff_provider_root=provider_link,
                trusted_provider_catalog_roots=(provider_link,),
            )
            self.assertTrue(any("provider_artifact_root_overlap" in error for error in symlink_errors))

    def test_ledger_cli_accepts_explicit_host_review_registry(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            help_result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/ai_film_production_ledger.py"), "validate", "--help"],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertIn("--handoff-provider-root", help_result.stdout)
            document = self.selected_document()
            self.bind_risk(document, root)
            document["attempts"][0]["execution_input_manifest"] = self.execution_manifest(document, root)
            document["genesis_sha256"] = ledger.genesis_sha256(document)
            ledger_path = root / "ledger.json"
            previous_path = root / "previous.json"
            ledger_path.write_text(json.dumps(document), encoding="utf-8")
            previous_path.write_text(json.dumps(document), encoding="utf-8")
            missing_registry = root / "missing-registry.json"
            command = [
                sys.executable,
                str(ROOT / "scripts/ai_film_production_ledger.py"),
                "validate",
                str(ledger_path),
                "--previous",
                str(previous_path),
                "--artifact-root",
                str(root),
            ]
            blocked = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                env={**os.environ, "DIRCREATIVE_REVIEW_TRUST_REGISTRY": str(missing_registry)},
            )
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(json.loads(blocked.stdout)["status"], "TOOL_BLOCKED")
            registry = self.handoff_runtime[root.resolve()]["registry"]
            explicit = subprocess.run(
                [*command, "--review-trust-registry", str(registry)],
                capture_output=True,
                check=False,
                text=True,
            )
            explicit_payload = json.loads(explicit.stdout)
            self.assertNotEqual(explicit_payload["status"], "TOOL_BLOCKED")
            self.assertEqual(explicit_payload["review_trust_registry_path"], str(registry))

    def test_full_handoff_packet_wrong_frame_hash_and_prompt_review_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            document["attempts"][0]["execution_input_manifest"] = manifest
            manifest["scene_support_truth"]["handoff_truth_artifact"]["frame_id"] = "S07-P99"
            self.assertTrue(any(
                error.startswith("execution_handoff_scope_mismatch:")
                for error in self.errors(document, root)
            ))

            manifest["scene_support_truth"]["handoff_truth_artifact"]["sha256"] = "f" * 64
            self.assertTrue(any(
                error.startswith("execution_handoff_truth_hash_mismatch:")
                for error in self.errors(document, root)
            ))

            self.handoff_runtime.pop(root.resolve())
            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            document["attempts"][0]["execution_input_manifest"] = manifest
            packet = self.handoff_runtime[root.resolve()]["packet"]
            review_path = root / packet["output_spec"]["prompt_authority_review_relative_path"]
            review_path.write_bytes(review_path.read_bytes() + b"tampered\n")
            self.assertTrue(any(
                error.startswith("execution_handoff_packet_invalid:")
                for error in self.errors(document, root)
            ))

    def test_full_packet_prompt_and_ordered_inputs_are_execution_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            document["attempts"][0]["execution_input_manifest"] = manifest
            self.assertFalse(any(
                error.startswith(("execution_packet_prompt_mismatch:", "execution_packet_attachment_mismatch:"))
                for error in self.errors(document, root)
            ))

            attempt = document["attempts"][0]
            attempt["prompt_artifact"]["prompt_text"] = "DIFFERENT UNREVIEWED PROMPT"
            different_hash = hashlib.sha256(attempt["prompt_artifact"]["prompt_text"].encode("utf-8")).hexdigest()
            attempt["prompt_artifact"]["prompt_sha256"] = different_hash
            manifest["prompt_sha256"] = different_hash
            self.assertTrue(any(
                error.startswith("execution_packet_prompt_mismatch:")
                for error in self.errors(document, root)
            ))

            packet = self.handoff_runtime[root.resolve()]["packet"]
            prompt_manifest = json.loads(
                (root / packet["output_spec"]["prompt_manifest_relative_path"]).read_text(encoding="utf-8")
            )
            source_entry = next(item for item in prompt_manifest["frame_prompts"] if item["frame_id"] == "S07-P01")
            attempt["prompt_artifact"]["prompt_text"] = source_entry["prompt"]
            attempt["prompt_artifact"]["prompt_sha256"] = source_entry["prompt_sha256"]
            manifest["prompt_sha256"] = source_entry["prompt_sha256"]
            manifest["ordered_attachments"] = list(reversed(manifest["ordered_attachments"]))
            manifest["attachment_manifest_sha256"] = ledger.canonical_sha256(manifest["ordered_attachments"])
            self.assertTrue(any(
                error.startswith("execution_packet_attachment_mismatch:")
                for error in self.errors(document, root)
            ))

            manifest["ordered_attachments"][0] = {
                **manifest["ordered_attachments"][0],
                "relative_path": "assets/replaced-reference.png",
                "sha256": "f" * 64,
            }
            manifest["attachment_manifest_sha256"] = ledger.canonical_sha256(manifest["ordered_attachments"])
            self.assertTrue(any(
                error.startswith("execution_packet_attachment_mismatch:")
                for error in self.errors(document, root)
            ))

    def test_low_risk_legacy_selected_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root, actual_risk="low")
            gate_errors = [
                error
                for error in self.errors(document, root)
                if error.startswith("selected_execution_")
                or error.startswith("selected_scene_")
                or error.startswith("selected_parent_truth_")
                or error.startswith("selected_semantic_")
            ]
            self.assertEqual(gate_errors, [])

    def test_selected_candidate_rejects_missing_scene_attachment_and_failed_parent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            manifest["ordered_attachments"] = [
                item for item in manifest["ordered_attachments"] if item["asset_id"] != "BELL-01"
            ]
            manifest["attachment_manifest_sha256"] = ledger.canonical_sha256(manifest["ordered_attachments"])
            document["attempts"][0]["execution_input_manifest"] = manifest
            self.assertTrue(any(error.startswith("selected_support_subject_missing:") for error in self.errors(document, root)))

            document = self.selected_document()
            self.bind_risk(document, root)
            manifest = self.execution_manifest(document, root)
            manifest["ordered_attachments"] = [
                item for item in manifest["ordered_attachments"] if item["asset_id"] != "FOUNDRY-B"
            ]
            manifest["attachment_manifest_sha256"] = ledger.canonical_sha256(manifest["ordered_attachments"])
            document["attempts"][0]["execution_input_manifest"] = manifest
            errors = self.errors(document, root)
            self.assertTrue(any(error.startswith("selected_scene_attachment_missing:") for error in errors))
            self.assertTrue(any(error.startswith("selected_support_anchor_missing:") for error in errors))

            document = self.selected_document()
            self.bind_risk(document, root)
            child_manifest = self.execution_manifest(document, root)
            child_manifest["scene_support_truth"]["parent_attempt_ids"] = ["ATTEMPT-002"]
            document["attempts"][0]["execution_input_manifest"] = child_manifest
            parent = document["attempts"][1]
            parent["execution_input_manifest"] = self.execution_manifest(document, root, status="failed")
            self.assertTrue(any(error.startswith("selected_parent_truth_not_ready:") for error in self.errors(document, root)))

    def test_high_risk_generic_accept_and_tabletop_false_accept_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            document["attempts"][0]["execution_input_manifest"] = self.execution_manifest(document, root)
            self.assertTrue(any(
                error.startswith("selected_semantic_truth_review_missing:")
                for error in self.errors(document, root)
            ))

            document["attempts"][0]["review_evidence"][0]["semantic_truth_review"] = self.semantic_review(
                document,
                contamination="present",
            )
            self.assertTrue(any(
                error.startswith("selected_semantic_truth_review_failed:")
                for error in self.errors(document, root)
            ))

            document = self.selected_document()
            self.bind_risk(document, root)
            document["attempts"][0]["execution_input_manifest"] = self.execution_manifest(document, root)
            review = document["attempts"][0]["review_evidence"][0]
            review["semantic_truth_review"] = self.semantic_review(document)
            review["verdict"] = "reject"
            review["source"] = "producer"
            review["receipt_id"] = "UNREFERENCED-REVIEW"
            self.assertTrue(any(
                error.startswith("selected_semantic_truth_review_untrusted:")
                for error in self.errors(document, root)
            ))

    def test_high_risk_selected_rejects_parent_latest_rejected_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.selected_document()
            self.bind_risk(document, root)
            child_manifest = self.execution_manifest(document, root)
            child_manifest["scene_support_truth"]["parent_attempt_ids"] = ["ATTEMPT-002"]
            document["attempts"][0]["execution_input_manifest"] = child_manifest
            document["attempts"][1]["execution_input_manifest"] = self.execution_manifest(document, root)
            document["state_events"].append({
                "event_id": "PARENT-REJECTED",
                "attempt_id": "ATTEMPT-002",
                "state": "rejected",
                "evidence_source": "producer",
                "evidence_refs": [],
                "review_verdict": "reject",
                "created_at": "2026-08-24T00:01:01Z",
                "actor": "dircreative",
            })
            document["attempts"][0]["review_evidence"][0]["semantic_truth_review"] = self.semantic_review(
                document,
                parent_checks=[{
                    "attempt_id": "ATTEMPT-002",
                    "latest_state": "rejected",
                    "truth_review_status": "rejected",
                }],
            )
            self.assertTrue(any(
                error.startswith("selected_parent_latest_state_invalid:")
                for error in self.errors(document, root)
            ))

            document = self.selected_document()
            child = document["attempts"][0]
            child_manifest = self.execution_manifest(document, root)
            child_manifest["scene_support_truth"]["parent_attempt_ids"] = ["ATTEMPT-002"]
            child["execution_input_manifest"] = child_manifest
            parent = document["attempts"][1]
            parent["execution_input_manifest"] = self.execution_manifest(document, root)
            parent["output_manifest"] = [dict(child["output_manifest"][0])]
            parent_semantic = {
                "output_sha256": parent["output_manifest"][0]["sha256"],
                "truth_revision_sha256": parent["execution_input_manifest"]["scene_support_truth"]["revision_sha256"],
                "scene_truth": "pass",
                "support_visible": "pass",
                "forbidden_background_ground_contamination": "absent",
                "parent_checks": [],
            }
            parent_semantic["review_sha256"] = ledger.semantic_review_digest(parent_semantic)
            parent_review = {
                "review_id": "PARENT-REVIEW",
                "verdict": "reject",
                "sha256": "d" * 64,
                "source": "producer",
                "receipt_id": "PARENT-RECEIPT",
                "semantic_truth_review": parent_semantic,
            }
            parent["review_evidence"] = [parent_review]
            child_semantic = self.semantic_review(
                document,
                parent_checks=[{
                    "attempt_id": "ATTEMPT-002",
                    "latest_state": "selected",
                    "truth_review_status": "pass",
                }],
            )
            errors = ledger.semantic_truth_review_errors(
                child,
                {"semantic_truth_review": child_semantic},
                {item["attempt_id"]: item for item in document["attempts"]},
                {"ATTEMPT-002": "selected"},
                {"ATTEMPT-002": [{"state": "selected", "evidence_refs": []}]},
                {
                    "PARENT-RECEIPT": {
                        "receipt_id": "PARENT-RECEIPT",
                        "purpose": "review",
                        "attempt_id": "ATTEMPT-002",
                        "subject_sha256": ledger.review_subject_sha256(parent, parent_review),
                        "source": "producer",
                        "sha256": "d" * 64,
                        "actor": "reviewer",
                    }
                },
                {"PARENT-RECEIPT"},
            )
            self.assertTrue(any(error.startswith("selected_parent_truth_review_invalid:") for error in errors))


if __name__ == "__main__":
    unittest.main()
