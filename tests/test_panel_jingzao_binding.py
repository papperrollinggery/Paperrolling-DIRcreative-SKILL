from __future__ import annotations

import copy
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_storyboard_coverage as coverage  # noqa: E402
import dircreative_storyboard_frame_handoff as handoff  # noqa: E402
import dircreative_media_forward_audit as media_forward  # noqa: E402
import dircreative_review_trust as review_trust  # noqa: E402


class PanelJingzaoBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.review_runtime: dict[Path, dict[str, Path]] = {}

    @staticmethod
    def canonical_hash(value) -> str:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def setup_review_authority(self, artifact_root: Path) -> None:
        key = artifact_root.resolve()
        if key in self.review_runtime:
            return
        openssl = shutil.which("openssl")
        if openssl is None:
            self.skipTest("openssl is required for prompt-authority review tests")
        trust_temp = tempfile.TemporaryDirectory(prefix="dircreative-prompt-review-trust-")
        self.addCleanup(trust_temp.cleanup)
        trust_root = Path(trust_temp.name)
        private_key = trust_root / "review-private.pem"
        public_key = trust_root / "review-public.pem"
        subprocess.run(
            [openssl, "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private_key)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            [openssl, "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
            capture_output=True,
            check=True,
        )
        registry = trust_root / "review-trust-registry.json"
        registry.write_text(
            json.dumps({
                "schema_version": "1.0.0",
                "authority": "host_configuration_only",
                "review_authorities": [{
                    "authority_id": "PROMPT-REVIEW-001",
                    "authority_kind": "human_reviewer",
                    "actor_id": "prompt-reviewer",
                    "allowed_purposes": ["prompt_authority_review"],
                    "allowed_sources": ["independent_review"],
                    "status": "active",
                    "public_key_relative_path": public_key.name,
                    "public_key_sha256": hashlib.sha256(public_key.read_bytes()).hexdigest(),
                }],
            }, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.review_runtime[key] = {
            "private_key": private_key,
            "registry": registry,
            "openssl": Path(openssl),
        }

    def refresh_prompt_review(
        self,
        root: Path,
        document: dict,
        entries: list[dict],
        *,
        failed_conflicts: dict[str, list[str]] | None = None,
    ) -> None:
        self.setup_review_authority(root)
        runtime = self.review_runtime[root.resolve()]
        by_frame = {entry["frame_id"]: entry for entry in entries}
        reviews = []
        for frame in document["frames"]:
            truth = frame.get("truth_contract")
            if not isinstance(truth, dict) or truth.get("risk") != "high":
                continue
            entry = by_frame[frame["frame_id"]]
            conflicts = (failed_conflicts or {}).get(frame["frame_id"], [])
            reviews.append({
                "frame_id": frame["frame_id"],
                "prompt_sha256": entry["prompt_sha256"],
                "reference_authority_sha256": self.canonical_hash(entry["reference_authority"]),
                "truth_revision_sha256": self.canonical_hash(truth),
                "coverage_sha256": frame["panel_context"]["coverage_sha256"],
                "verdict": "fail" if conflicts else "pass",
                "forbidden_control_conflict": bool(conflicts),
                "conflicts": conflicts,
            })
        review = {
            "contract_id": "prompt_authority_semantic_review_v1",
            "purpose": "prompt_authority_review",
            "source": "independent_review",
            "authority_id": "PROMPT-REVIEW-001",
            "actor": "prompt-reviewer",
            "frames": reviews,
        }
        payload = (json.dumps(review, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        relative = "compiled_prompts/prompt-authority-review.json"
        signature_relative = "compiled_prompts/prompt-authority-review.sig"
        path = root / relative
        signature = root / signature_relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        subprocess.run(
            [str(runtime["openssl"]), "dgst", "-sha256", "-sign", str(runtime["private_key"]), "-out", str(signature), str(path)],
            capture_output=True,
            check=True,
        )
        document["output_spec"].update({
            "prompt_authority_review_relative_path": relative,
            "prompt_authority_review_sha256": hashlib.sha256(payload).hexdigest(),
            "prompt_authority_review_signature_relative_path": signature_relative,
        })

    def validate_handoff(self, document: dict, root: Path, **kwargs) -> list[str]:
        runtime = self.review_runtime.get(root.resolve())
        return handoff.validate(
            document,
            artifact_root=root,
            _review_trust_registry_path=(runtime["registry"] if runtime else review_trust.DEFAULT_REGISTRY_PATH),
            **kwargs,
        )

    def coverage_plan(self, root: Path) -> tuple[dict, str]:
        cards = {"cards": [{"shot_id": "S01", "timecode": "00:00-00:03"}]}
        (root / "cards.json").write_text(json.dumps(cards), encoding="utf-8")
        plan = {
            "schema_version": "1.0",
            "project_id": "binding-test",
            "frame_rate_fps": 25,
            "scope": "whole_film",
            "shot_cards_file": "cards.json",
            "shot_cards_sha256": coverage.json_hash(cards),
            "requirements": [{
                "requirement_id": "act",
                "source_anchor": "cards:S01",
                "kind": "action",
                "shot_ids": ["S01"],
                "phases": ["contact"],
                "risk": "medium",
                "image_required": False,
            }],
            "panels": [{
                "panel_id": "p1",
                "shot_id": "S01",
                "requirement_id": "act",
                "phase": "contact",
                "at_seconds": 1.25,
                "state": "hand contact",
                "camera_setup": "close",
                "view_subject": "lin",
                "gaze_target": "father",
                "axis_id": "river",
                "axis_side": "north",
                "look_direction": "left",
                "image": {"status": "planned"},
            }],
        }
        payload = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        (root / "coverage.json").write_bytes(payload)
        return plan, hashlib.sha256(payload).hexdigest()

    def bound_document(self, root: Path) -> dict:
        _, coverage_hash = self.coverage_plan(root)
        document = json.loads(
            (ROOT / "tests/fixtures/storyboard-frame-jingzao/valid-chain.json").read_text(encoding="utf-8")
        )
        document["delivery_consumption"]["status"] = "planned"
        document["delivery_consumption"].pop("host_trace")
        document["delivery_consumption"].pop("frame_outputs")
        frame = document["frames"][0]
        frame["frame_id"] = "p1"
        frame["panel_context"] = {
            "coverage_file": "coverage.json",
            "coverage_sha256": coverage_hash,
            "panel_id": "p1",
            "phase": "contact",
            "at_seconds": 1.25,
            "state": "hand contact",
        }
        return document

    def test_production_panel_requires_actual_motion_planning_before_consumption(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.bound_document(root)
            document["fixture_only"] = False
            self.assertIn("panel_context_motion_planning_incomplete: p1", handoff.validate_panel_bindings(document, root))
            plan = json.loads((root / "coverage.json").read_bytes())
            plan["requirements"][0]["kind"] = "hold"
            plan["requirements"][0]["risk"] = "low"
            payload = json.dumps(plan).encode()
            (root / "coverage.json").write_bytes(payload)
            document["frames"][0]["panel_context"]["coverage_sha256"] = hashlib.sha256(payload).hexdigest()
            self.assertEqual(handoff.validate_panel_bindings(document, root), [])

    def truth_document(self, root: Path) -> tuple[dict, list[dict]]:
        root.mkdir(parents=True, exist_ok=True)
        document = self.bound_document(root)
        frames = document["frames"]
        frame_specs = [
            (frames[0], "S07-P01", "S07", []),
            (frames[1], "S07-P02", "S08", ["S07-P01"]),
        ]
        cards = {"cards": [
            {"shot_id": "S07", "timecode": "00:00-00:03"},
            {"shot_id": "S08", "timecode": "00:03-00:06"},
        ]}
        (root / "truth-cards.json").write_text(json.dumps(cards), encoding="utf-8")
        truth_coverage = {
            "schema_version": "1.0",
            "project_id": "binding-test",
            "frame_rate_fps": 25,
            "scope": "whole_film",
            "shot_cards_file": "truth-cards.json",
            "shot_cards_sha256": coverage.json_hash(cards),
            "requirements": [],
            "panels": [],
        }
        attachment_specs = [
            ("BELL-01", "prop", "assets/bell-01.png", b"bell identity reference\n"),
            ("FOUNDRY-B", "scene", "assets/foundry-b.png", b"foundry b scene reference\n"),
        ]
        attachment_bindings = []
        for asset_id, role, relative_path, payload in attachment_specs:
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            attachment_bindings.append({
                "source_id": asset_id,
                "role": role,
                "relative_path": relative_path,
                "sha256": hashlib.sha256(payload).hexdigest(),
            })

        prompt_entries = []
        for frame, frame_id, shot_id, parent_ids in frame_specs:
            frame["frame_id"] = frame_id
            frame["shot_id"] = shot_id
            requirement_id = f"{frame_id}-truth"
            truth_coverage["requirements"].append({
                "requirement_id": requirement_id,
                "source_anchor": f"cards:{shot_id}",
                "kind": "action",
                "shot_ids": [shot_id],
                "phases": ["contact"],
                "risk": "high",
                "image_required": True,
            })
            truth_coverage["panels"].append({
                "panel_id": frame_id,
                "shot_id": shot_id,
                "requirement_id": requirement_id,
                "phase": "contact",
                "at_seconds": 1.0 if shot_id == "S07" else 4.0,
                "state": "bell visibly suspended",
                "camera_setup": "wide",
                "view_subject": "bell",
                "gaze_target": "foundry overhead",
                "axis_id": "foundry",
                "axis_side": "north",
                "look_direction": "center",
                "image": {"status": "planned"},
            })
            frame["canonical_asset_ids"] = ["BELL-01", "FOUNDRY-B"]
            frame["reference_roles"] = [
                {
                    "asset_id": "BELL-01",
                    "role": "prop",
                    "must_not_control": [
                        "background",
                        "ground_surface",
                        "scene_geography",
                        "support_relation",
                    ],
                    "attachment": {
                        "relative_path": attachment_bindings[0]["relative_path"],
                        "sha256": attachment_bindings[0]["sha256"],
                    },
                },
                {
                    "asset_id": "FOUNDRY-B",
                    "role": "scene",
                    "must_not_control": ["prop_identity", "camera_action"],
                    "attachment": {
                        "relative_path": attachment_bindings[1]["relative_path"],
                        "sha256": attachment_bindings[1]["sha256"],
                    },
                },
            ]
            frame["truth_contract"] = {
                "risk": "high",
                "status": "ready",
                "scene_asset_id": "FOUNDRY-B",
                "required_attachment_ids": ["BELL-01", "FOUNDRY-B"],
                "support": {
                    "status": "required",
                    "subject_asset_id": "BELL-01",
                    "anchor_asset_id": "FOUNDRY-B",
                    "relationship": "suspended_from_overhead_structure",
                    "visibility": "explicit_in_frame",
                },
                "parent_frame_ids": parent_ids,
                "constraint_input": {
                    "mode": "scene_reference",
                    "asset_id": "FOUNDRY-B",
                },
            }
            prompt = f"{frame_id}: bell suspended inside foundry-b; no table or neutral ground."
            prompt_entries.append({
                "frame_id": frame_id,
                "prompt": prompt,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "reference_inputs": copy.deepcopy(attachment_bindings),
                "reference_authority": [
                    {
                        "source_id": "BELL-01",
                        "role": "prop",
                        "may_control": ["prop_identity"],
                        "must_not_control": sorted(frame["reference_roles"][0]["must_not_control"]),
                    },
                    {
                        "source_id": "FOUNDRY-B",
                        "role": "scene",
                        "may_control": sorted([
                            "background",
                            "ground_surface",
                            "scene_geography",
                            "support_relation",
                        ]),
                        "must_not_control": sorted(frame["reference_roles"][1]["must_not_control"]),
                    },
                ],
            })

        coverage_payload = (
            json.dumps(truth_coverage, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8")
        (root / "truth-coverage.json").write_bytes(coverage_payload)
        coverage_hash = hashlib.sha256(coverage_payload).hexdigest()
        for frame, panel in zip(frames, truth_coverage["panels"]):
            frame["panel_context"] = {
                "coverage_file": "truth-coverage.json",
                "coverage_sha256": coverage_hash,
                "panel_id": panel["panel_id"],
                "phase": panel["phase"],
                "at_seconds": panel["at_seconds"],
                "state": panel["state"],
            }

        prompt_payload = (
            json.dumps({"frame_prompts": prompt_entries}, ensure_ascii=False, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        prompt_path = root / document["output_spec"]["prompt_manifest_relative_path"]
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_bytes(prompt_payload)
        document["output_spec"]["prompt_manifest_sha256"] = hashlib.sha256(prompt_payload).hexdigest()
        self.refresh_prompt_review(root, document, prompt_entries)
        return document, prompt_entries

    def rewrite_prompt_manifest(self, root: Path, document: dict, entries: list[dict]) -> None:
        payload = (
            json.dumps({"frame_prompts": entries}, ensure_ascii=False, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        path = root / document["output_spec"]["prompt_manifest_relative_path"]
        path.write_bytes(payload)
        document["output_spec"]["prompt_manifest_sha256"] = hashlib.sha256(payload).hexdigest()

    def observed_truth_document(
        self,
        artifact_root: Path,
        trusted_root: Path,
        *,
        mutate_request=None,
    ) -> tuple[dict, Path]:
        document, prompt_entries = self.truth_document(artifact_root)
        records = [{
            "timestamp": "2026-09-01T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": "truth-fixture-thread"},
        }]
        for index, entry in enumerate(prompt_entries, start=1):
            request = {
                "prompt": entry["prompt"],
                "referenced_image_paths": [
                    str((artifact_root / item["relative_path"]).resolve())
                    for item in entry["reference_inputs"]
                ],
            }
            if mutate_request is not None:
                mutate_request(index, request)
            records.extend([
                {
                    "timestamp": f"2026-09-01T00:00:0{index}Z",
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call",
                        "name": "exec",
                        "id": f"request-{index}",
                        "call_id": f"outer-{index}",
                        "input": media_forward.imagegen_trace_source(request),
                    },
                },
                {
                    "timestamp": f"2026-09-01T00:00:1{index}Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "image_generation_end",
                        "call_id": f"imagegen-{index}",
                        "status": "completed",
                        "result": base64.b64encode(handoff.fixture_png_bytes()).decode("ascii"),
                    },
                },
            ])
        payload = b"".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            for record in records
        )
        trusted_root.mkdir(parents=True, exist_ok=True)
        host_log = trusted_root / "truth-host.jsonl"
        host_log.write_bytes(payload)
        document["delivery_consumption"].update({
            "status": "observed_unverified",
            "host_trace": {
                "thread_id": "truth-fixture-thread",
                "prefix_bytes": len(payload),
                "prefix_sha256": hashlib.sha256(payload).hexdigest(),
            },
            "frame_outputs": [
                {
                    "frame_id": frame["frame_id"],
                    "execution_receipt": {
                        "artifact_id": f"receipt-{index}",
                        "relative_path": f"receipts/{index}.json",
                        "sha256": "a" * 64,
                    },
                    "generated_artifact": {
                        "artifact_id": f"output-{index}",
                        "relative_path": f"outputs/{index}.png",
                        "sha256": "b" * 64,
                    },
                }
                for index, frame in enumerate(document["frames"], start=1)
            ],
        })
        return document, host_log

    def test_legacy_handoff_is_unaffected(self) -> None:
        document = json.loads(
            (ROOT / "tests/fixtures/storyboard-frame-jingzao/valid-chain.json").read_text(encoding="utf-8")
        )
        self.assertEqual(handoff.validate(document), [])

    def test_valid_binding_uses_actual_coverage_source_and_preserves_legacy_frame(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.bound_document(root)
            self.assertTrue(any(
                error.startswith("panel_context_artifact_root_required:")
                for error in handoff.validate(document)
            ))
            self.assertEqual(self.validate_handoff(document, root), [])

    def test_panel_context_rejects_hash_and_declared_panel_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            cases = {
                "hash": ("coverage_sha256", "0" * 64, "panel_context_coverage_hash_mismatch:"),
                "phase": ("phase", "start", "panel_context_phase_mismatch:"),
                "time": ("at_seconds", 1.5, "panel_context_at_seconds_mismatch:"),
                "state": ("state", "other", "panel_context_state_mismatch:"),
            }
            for _, (field, value, expected) in cases.items():
                document = self.bound_document(root)
                document["frames"][0]["panel_context"][field] = value
                self.assertTrue(any(error.startswith(expected) for error in handoff.validate(document, artifact_root=root)))
            document = self.bound_document(root)
            document["frames"][0]["shot_id"] = "S02"
            self.assertTrue(any(error.startswith("panel_context_shot_id_mismatch:") for error in handoff.validate(document, artifact_root=root)))

    def test_panel_context_rejects_escape_ambiguous_missing_and_frame_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.bound_document(root)
            document["frames"][0]["panel_context"]["coverage_file"] = "../coverage.json"
            self.assertTrue(any(error.startswith("panel_context_coverage_path_invalid:") for error in handoff.validate(document, artifact_root=root)))

            document = self.bound_document(root)
            (root / "coverage.json").write_bytes(b"x" * (coverage.MAX_JSON_BYTES + 1))
            self.assertTrue(any(error.startswith("panel_context_coverage_too_large:") for error in handoff.validate(document, artifact_root=root)))

            document = self.bound_document(root)
            plan, _ = self.coverage_plan(root)
            plan["panels"].append(copy.deepcopy(plan["panels"][0]))
            payload = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            (root / "coverage.json").write_bytes(payload)
            document["frames"][0]["panel_context"]["coverage_sha256"] = hashlib.sha256(payload).hexdigest()
            self.assertTrue(any(error.startswith("panel_context_panel_ambiguous:") for error in handoff.validate(document, artifact_root=root)))

            document = self.bound_document(root)
            document["frames"][0]["panel_context"]["panel_id"] = "missing"
            self.assertTrue(any(error.startswith("panel_context_panel_missing:") for error in handoff.validate(document, artifact_root=root)))

            document = self.bound_document(root)
            document["frames"][0]["frame_id"] = "FRAME-S01"
            self.assertTrue(any(error.startswith("panel_context_frame_id_mismatch:") for error in handoff.validate(document, artifact_root=root)))

    def test_legacy_duplicate_technical_shot_remains_rejected(self) -> None:
        document = json.loads(
            (ROOT / "tests/fixtures/storyboard-frame-jingzao/valid-chain.json").read_text(encoding="utf-8")
        )
        document["frames"][1]["shot_id"] = document["frames"][0]["shot_id"]
        self.assertTrue(any(error.startswith("frame_shot_duplicate:") for error in handoff.validate(document)))

    def test_hashed_bytes_are_parsed_without_reopening_changed_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.bound_document(root)
            target = (root / "coverage.json").resolve()
            original_read = Path.read_bytes
            reads = []

            def replace_after_read(path):
                data = original_read(path)
                if path == target:
                    reads.append(path)
                    target.write_text('{"panels": []}', encoding="utf-8")
                return data

            with patch.object(Path, "read_bytes", replace_after_read):
                self.assertEqual(handoff.validate_panel_bindings(document, root), [])
            self.assertEqual(len(reads), 1)
            self.assertTrue(any(error.startswith("panel_context_coverage_hash_mismatch:")
                                for error in handoff.validate_panel_bindings(document, root)))

    def test_os_path_error_returns_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.bound_document(root)
            with patch.object(handoff, "contained_file", side_effect=OSError("name too long")):
                errors = handoff.validate_panel_bindings(document, root)
            self.assertTrue(any(error.startswith("panel_context_coverage_path_invalid:") for error in errors))

    def test_high_risk_truth_contract_binds_scene_support_and_execution_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, _ = self.truth_document(root)
            self.assertEqual(self.validate_handoff(document, root), [])

            document["frames"][0]["truth_contract"]["risk"] = "low"
            self.assertTrue(any(
                error.startswith("truth_contract_risk_mismatch:")
                for error in self.validate_handoff(document, root)
            ))

            document, _ = self.truth_document(root)
            document["frames"][0].pop("panel_context")
            self.assertTrue(any(
                error.startswith("truth_contract_risk_source_missing:")
                for error in self.validate_handoff(document, root)
            ))

    def test_high_risk_panel_binding_requires_truth_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document = self.bound_document(root)
            plan = json.loads((root / "coverage.json").read_text(encoding="utf-8"))
            plan["requirements"][0]["risk"] = "high"
            plan["panels"][0]["panel_id"] = "S07-P01"
            payload = (json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            (root / "coverage.json").write_bytes(payload)
            frame = document["frames"][0]
            frame["frame_id"] = "S07-P01"
            frame["panel_context"]["panel_id"] = "S07-P01"
            frame["panel_context"]["coverage_sha256"] = hashlib.sha256(payload).hexdigest()
            errors = self.validate_handoff(document, root)
            self.assertTrue(any(error.startswith("high_risk_truth_contract_required:") for error in errors))

    def test_truth_contract_rejects_reference_background_authority_and_missing_scene_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, _ = self.truth_document(root)
            document["frames"][0]["reference_roles"][0]["must_not_control"].remove("background")
            self.assertTrue(any(
                error.startswith("reference_background_authority_unbounded:")
                for error in self.validate_handoff(document, root)
            ))

            document, _ = self.truth_document(root)
            document["frames"][0]["reference_roles"][1].pop("attachment")
            self.assertTrue(any(
                error.startswith("required_scene_attachment_missing:")
                for error in self.validate_handoff(document, root)
            ))

    def test_bound_spatial_layout_controls_geometry_but_not_identity_or_style(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, entries = self.truth_document(root)
            payload = b"s07 spatial layout\n"
            (root / "assets/s07-layout.png").write_bytes(payload)
            attachment = {
                "source_id": "LAYOUT-S07",
                "role": "layout",
                "relative_path": "assets/s07-layout.png",
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            frame = document["frames"][0]
            frame["canonical_asset_ids"].append("LAYOUT-S07")
            frame["reference_roles"].append({
                "asset_id": "LAYOUT-S07",
                "role": "layout",
                "must_not_control": [
                    "character_identity",
                    "prop_identity",
                    "material",
                    "texture",
                    "final_art_style",
                ],
                "attachment": {
                    "relative_path": attachment["relative_path"],
                    "sha256": attachment["sha256"],
                },
            })
            frame["truth_contract"]["required_attachment_ids"].append("LAYOUT-S07")
            frame["truth_contract"]["constraint_input"] = {
                "mode": "spatial_mockup",
                "asset_id": "LAYOUT-S07",
            }
            entries[0]["reference_inputs"].append(attachment)
            entries[0]["reference_authority"].append({
                "source_id": "LAYOUT-S07",
                "role": "layout",
                "may_control": sorted([
                    "geometry",
                    "composition",
                    "occlusion",
                    "scale",
                    "support_relation",
                ]),
                "must_not_control": sorted(frame["reference_roles"][-1]["must_not_control"]),
            })
            self.rewrite_prompt_manifest(root, document, entries)
            self.refresh_prompt_review(root, document, entries)
            self.assertEqual(self.validate_handoff(document, root), [])

            frame["reference_roles"][-1]["must_not_control"].remove("character_identity")
            self.assertTrue(any(
                error.startswith("layout_identity_authority_unbounded:")
                for error in self.validate_handoff(document, root)
            ))

    def test_prompt_authority_cannot_reverse_reference_sovereignty(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, entries = self.truth_document(root)
            entries[0]["reference_authority"][0]["may_control"].append("background")
            self.rewrite_prompt_manifest(root, document, entries)
            self.assertTrue(any(
                error.startswith("prompt_reference_authority_mismatch:")
                for error in self.validate_handoff(document, root)
            ))

    def test_signed_prompt_semantic_review_blocks_prop_and_layout_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, entries = self.truth_document(root)
            self.assertEqual(self.validate_handoff(document, root), [])

            missing = copy.deepcopy(document)
            missing["output_spec"].pop("prompt_authority_review_relative_path")
            self.assertTrue(any(
                error.startswith("prompt_authority_review_missing:")
                for error in self.validate_handoff(missing, root)
            ))

            review_path = root / document["output_spec"]["prompt_authority_review_relative_path"]
            review_path.write_bytes(review_path.read_bytes() + b"tampered\n")
            self.assertTrue(any(
                error.startswith("prompt_authority_review_hash_mismatch:")
                for error in self.validate_handoff(document, root)
            ))

            document, entries = self.truth_document(root)
            entries[0]["prompt"] = "Copy the BELL-01 reference background and tabletop ground exactly."
            entries[0]["prompt_sha256"] = hashlib.sha256(entries[0]["prompt"].encode("utf-8")).hexdigest()
            self.rewrite_prompt_manifest(root, document, entries)
            self.refresh_prompt_review(
                root,
                document,
                entries,
                failed_conflicts={"S07-P01": ["prop_background_ground"]},
            )
            self.assertTrue(any(
                error.startswith("prompt_authority_review_failed:")
                for error in self.validate_handoff(document, root)
            ))

    def test_handoff_cli_reports_host_registry_tool_blocked_and_accepts_explicit_registry(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, _ = self.truth_document(root)
            packet = root / "handoff-packet.json"
            packet.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            missing_registry = root / "missing-host-registry.json"
            env = {**os.environ, "DIRCREATIVE_REVIEW_TRUST_REGISTRY": str(missing_registry)}
            blocked = subprocess.run(
                [sys.executable, str(ROOT / "scripts/dircreative_storyboard_frame_handoff.py"), "validate", str(packet), "--artifact-root", str(root)],
                capture_output=True,
                check=False,
                text=True,
                env=env,
            )
            self.assertEqual(blocked.returncode, 2)
            blocked_payload = json.loads(blocked.stdout)
            self.assertEqual(blocked_payload["status"], "TOOL_BLOCKED")
            self.assertEqual(blocked_payload["review_trust_registry_path"], str(missing_registry))

            registry = self.review_runtime[root.resolve()]["registry"]
            valid = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/dircreative_storyboard_frame_handoff.py"),
                    "validate",
                    str(packet),
                    "--artifact-root",
                    str(root),
                    "--review-trust-registry",
                    str(registry),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            self.assertEqual(json.loads(valid.stdout)["status"], "valid")

    def test_signed_prompt_semantic_review_blocks_layout_material_style_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, entries = self.truth_document(root)
            payload = b"layout semantic review\n"
            (root / "assets/review-layout.png").write_bytes(payload)
            frame = document["frames"][0]
            frame["canonical_asset_ids"].append("LAYOUT-REVIEW")
            frame["reference_roles"].append({
                "asset_id": "LAYOUT-REVIEW",
                "role": "layout",
                "must_not_control": ["character_identity", "prop_identity", "material", "texture", "final_art_style"],
                "attachment": {
                    "relative_path": "assets/review-layout.png",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                },
            })
            frame["truth_contract"]["required_attachment_ids"].append("LAYOUT-REVIEW")
            frame["truth_contract"]["constraint_input"] = {
                "mode": "spatial_mockup",
                "asset_id": "LAYOUT-REVIEW",
            }
            entries[0]["reference_inputs"].append({
                "source_id": "LAYOUT-REVIEW",
                "role": "layout",
                "relative_path": "assets/review-layout.png",
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
            entries[0]["reference_authority"].append({
                "source_id": "LAYOUT-REVIEW",
                "role": "layout",
                "may_control": sorted(["geometry", "composition", "occlusion", "scale", "support_relation"]),
                "must_not_control": sorted(frame["reference_roles"][-1]["must_not_control"]),
            })
            entries[0]["prompt"] = "Copy the layout reference material, texture, and final style exactly."
            entries[0]["prompt_sha256"] = hashlib.sha256(entries[0]["prompt"].encode("utf-8")).hexdigest()
            self.rewrite_prompt_manifest(root, document, entries)
            self.refresh_prompt_review(
                root,
                document,
                entries,
                failed_conflicts={"S07-P01": ["layout_identity_material_style"]},
            )
            self.assertTrue(any(
                error.startswith("prompt_authority_review_failed:")
                for error in self.validate_handoff(document, root)
            ))

    def test_truth_contract_requires_one_scene_role_matching_scene_asset(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, entries = self.truth_document(root)
            payload = b"second scene reference\n"
            (root / "assets/other-scene.png").write_bytes(payload)
            frame = document["frames"][0]
            frame["canonical_asset_ids"].append("OTHER-SCENE")
            frame["truth_contract"]["required_attachment_ids"].append("OTHER-SCENE")
            frame["reference_roles"].append({
                "asset_id": "OTHER-SCENE",
                "role": "scene",
                "must_not_control": ["prop_identity"],
                "attachment": {
                    "relative_path": "assets/other-scene.png",
                    "sha256": hashlib.sha256(payload).hexdigest(),
                },
            })
            entries[0]["reference_inputs"].append({
                "source_id": "OTHER-SCENE",
                "role": "scene",
                "relative_path": "assets/other-scene.png",
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
            entries[0]["reference_authority"].append({
                "source_id": "OTHER-SCENE",
                "role": "scene",
                "may_control": sorted([
                    "background",
                    "ground_surface",
                    "scene_geography",
                    "support_relation",
                ]),
                "must_not_control": ["prop_identity"],
            })
            self.rewrite_prompt_manifest(root, document, entries)
            self.assertTrue(any(
                error.startswith("scene_truth_role_ambiguous:")
                for error in self.validate_handoff(document, root)
            ))

    def test_truth_contract_rejects_invisible_support_and_missing_constraint_input(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, _ = self.truth_document(root)
            document["frames"][0]["truth_contract"]["support"]["visibility"] = "not_visible"
            self.assertTrue(any(
                error.startswith("support_truth_not_visible:")
                for error in self.validate_handoff(document, root)
            ))

            document, _ = self.truth_document(root)
            document["frames"][0]["truth_contract"]["constraint_input"]["mode"] = "none"
            self.assertTrue(any(
                error.startswith("constraint_input_required:")
                for error in self.validate_handoff(document, root)
            ))

    def test_truth_contract_rejects_prompt_attachment_manifest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, entries = self.truth_document(root)
            entries[0]["reference_inputs"] = entries[0]["reference_inputs"][:1]
            self.rewrite_prompt_manifest(root, document, entries)
            self.assertTrue(any(
                error.startswith("execution_attachment_manifest_mismatch:")
                for error in self.validate_handoff(document, root)
            ))

    def test_truth_contract_rejects_child_inheriting_failed_parent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            document, _ = self.truth_document(root)
            document["frames"][0]["truth_contract"]["status"] = "failed"
            errors = self.validate_handoff(document, root)
            self.assertTrue(any(error.startswith("truth_frame_not_ready:") for error in errors))
            self.assertTrue(any(error.startswith("parent_truth_not_ready:") for error in errors))

    def test_observed_execution_request_must_match_prompt_and_attachment_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            artifact_root = base / "artifacts"
            trusted_root = base / "trusted"

            def change_prompt(index, request):
                if index == 1:
                    request["prompt"] += " Put the bell on a table."

            document, host_log = self.observed_truth_document(
                artifact_root,
                trusted_root,
                mutate_request=change_prompt,
            )
            errors = self.validate_handoff(
                document,
                artifact_root,
                host_event_log=host_log,
                trusted_host_log_root=trusted_root,
            )
            self.assertTrue(any(error.startswith("execution_prompt_manifest_mismatch:") for error in errors))

            def drop_scene(index, request):
                if index == 1:
                    request["referenced_image_paths"] = request["referenced_image_paths"][:1]

            document, host_log = self.observed_truth_document(
                artifact_root,
                trusted_root,
                mutate_request=drop_scene,
            )
            errors = self.validate_handoff(
                document,
                artifact_root,
                host_event_log=host_log,
                trusted_host_log_root=trusted_root,
            )
            self.assertTrue(any(error.startswith("execution_attachment_manifest_mismatch:") for error in errors))


if __name__ == "__main__":
    unittest.main()
