from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dircreative_state_audit import canonical_authorization_scope, sample_state, sha256_file
from dircreative_visualization_writeback import validate_receipt


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WritebackAuthorizationTests(unittest.TestCase):
    def build_case(self, root: Path) -> tuple[dict, Path, Path]:
        scene_path = root / "scene.json"
        shutil.copy2(ROOT / "examples/spatial-dialogue/scene.json", scene_path)
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        scene_hash = digest(scene_path)
        spatial = copy.deepcopy(scene)
        spatial.update(source_refs=[f"{scene['scene_id']}#/revision"], scene_state_sha256=scene_hash)
        spec = {
            "spec_version": "1.1", "interaction_mode": "adopt_and_generate", "view_id": "auth-blocking-camera",
            "execution_context": "standalone_chat", "controller": {"surface_owner": "dircreative", "user_facing": True},
            "view": {"intent": "blocking_camera", "display_mode": "inline", "customer_stage_label": "站位与镜位", "decision_prompt": "采用当前站位并生成参考。"},
            "source_truth": {"artifacts": [{"artifact_id": scene["scene_id"], "version": scene["revision"], "sha256": scene_hash, "evidence_path": "scene.json", "lifecycle_status": "current"}]},
            "presentation": {"fields": [{"id": "current_stage", "label": "当前阶段", "value": "站位", "classification": "presentation_only", "source_ref": None}], "options": [], "downstream_effects": [], "spatial_scene": spatial},
            "interactions": {"local": ["select"], "actions": [{"id": "adopt-generate", "label": "采用并生成", "kind": "adopt_and_generate", "conversation_intent": "用户采用站位并请求既有范围内生成。"}], "max_actions": 2, "deep_navigation": False, "nested_scroll": False},
            "write_boundary": {"preview_only": True, "confirmation_required": True, "writes_authoritative_state": False, "write_owner": "dircreative", "possible_write_targets": ["scene/ROOM-01"], "forbidden_claims": ["lock", "readiness", "acceptance", "completion", "generation_authorization"]},
            "fallback": {"format": "markdown", "content": scene["description"], "required_visible_fields": ["current_stage", "decision_prompt", "downstream_effects", "spatial_scene"], "decision_question": "采用当前站位并生成参考。"},
        }
        spec_path = root / "source-spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        output = root / "artifacts" / "adoption.json"
        output.parent.mkdir(exist_ok=True)
        linkage = {"scene_id": scene["scene_id"], "revision": scene["revision"], "scene_state_sha256": scene_hash, "source_refs": spatial["source_refs"]}
        output.write_text(json.dumps({"source_scene": linkage}), encoding="utf-8")

        state = sample_state(root)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        state["updated_at"] = now
        auth_payload = {
            "work_id": state["project_id"], "asset_ids": [scene["scene_id"], "A-identity"],
            "expected_output_kinds": ["generated_media"], "model_ids": ["imagegen-test"], "scope_hash": "",
            "status": "active", "authorized_by": "user:fixture", "authorized_by_type": "human",
            "authorized_at": now, "evidence_ref": "user_confirmation:auth-confirmation",
            "confirmation_id": "auth-confirmation", "thread_id": "auth-thread", "expires_at": None,
        }
        auth_payload["scope_hash"] = canonical_authorization_scope(auth_payload)
        auth_path = root / ".dircreative" / "runs" / "authorization.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(json.dumps({"record_id": "auth-r1", "kind": "generation_authorization", "payload": auth_payload}, sort_keys=True), encoding="utf-8")
        record = copy.deepcopy(state["records"][0])
        record.update({"record_id": "auth-r1", "logical_id": "generation-auth", "kind": "generation_authorization", "revision": 2, "canonical_path": ".dircreative/runs/authorization.json", "original_path": ".dircreative/runs/authorization.json", "sha256": sha256_file(auth_path), "storage_class": "necessary_archive", "durable": True, "regenerable": False, "evidence": {"task_visibility": "not_applicable", "checked_at": None, "authorization_record_id": None, "asset_id": None, "authorization_scope_hash": None, "model_id": None}, "generation_authorization": auth_payload, "receipt": None, "manifest": None, "thread": None})
        state["records"].append(record)
        state["current_projection"].append("auth-r1")
        state["current"]["generation_authorization_ids"].append("auth-r1")
        state_path = root / "runtime-state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        snapshot = {"schema_version": "1.0.0", "provider": "codex_app.list_threads", "captured_at": now, "threads": [{"thread_id": "auth-thread", "host_id": "local", "status": "idle", "archived": False, "confirmations": [{"confirmation_id": "auth-confirmation", "actor_type": "human", "actor_id": "user:fixture"}]}]}
        snapshot_path = root / "thread-snapshot.json"
        snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
        receipt = {
            "receipt_version": "dircreative.chat-visualization-writeback@1.1", "interaction_mode": "adopt_and_generate", "receipt_id": "auth-writeback", "execution_context": "standalone_chat", "controller": {"write_owner": "dircreative", "recorded_by": "dircreative", "user_facing": True},
            "source_view": {"spec_path": "source-spec.json", "spec_sha256": digest(spec_path), "view_id": spec["view_id"], "gate_id": None},
            "conversation_intent": {"action_id": "adopt-generate", "action_kind": "adopt_and_generate", "selected_option_id": None, "submitted_text": "采用当前站位并生成本场参考。", "decision_source": "real_user", "user_confirmation_id": "view-confirmation"},
            "adoption_evidence": {"source_refs": spatial["source_refs"], "source_revision": scene["revision"], "write_evidence_refs": ["adoption"]},
            "generation_authorization": {"authorization_id": "auth-r1", "record_revision": 2, "state_path": "runtime-state.json", "state_sha256": digest(state_path), "thread_snapshot_path": "thread-snapshot.json", "thread_snapshot_sha256": digest(snapshot_path), "scope_hash": auth_payload["scope_hash"], "status": "inherited", "controller_check": {"thread_id": "auth-thread", "confirmation_id": "auth-confirmation", "authorized_by": "user:fixture", "authorized_by_type": "human"}},
            "generation_request": {"scene_id": scene["scene_id"], "shot_ids": ["S02"], "asset_ids": [scene["scene_id"], "A-identity"], "expected_output_kind": "generated_media", "model_id": "imagegen-test"},
            "artifact_writes": [{"artifact_id": "adoption", "label": "场景采用", "path": "artifacts/adoption.json", "change_kind": "created", "before_sha256": None, "after_sha256": digest(output), "source_scene": linkage}],
            "downstream_effects": {"stale": [], "preserved": [], "blocked": []}, "next_stage": {"id": "reference-pack", "label": "参考图", "status": "ready"},
            "authority": {"visual_action_wrote_state": False, "controller_revalidated_source": True, "artifact_hashes_verified": True, "generation_authorized": True},
        }
        return receipt, state_path, auth_path

    def test_accepts_current_exact_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            receipt, _, _ = self.build_case(Path(raw))
            self.assertEqual(validate_receipt(receipt, Path(raw)), [])

    def test_rejects_wrong_scene_or_shot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            receipt, _, _ = self.build_case(Path(raw))
            receipt["generation_request"]["scene_id"] = "OTHER"
            receipt["generation_request"]["shot_ids"] = ["S99"]
            errors = validate_receipt(receipt, Path(raw))
            self.assertIn("generation request scene does not match adopted spatial scene", errors)
            self.assertIn("generation request shots are not current adopted spatial shots", errors)

    def test_rejects_revoked_or_tampered_authority_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            receipt, state_path, auth_path = self.build_case(root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["records"][1]["generation_authorization"]["status"] = "revoked"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            receipt["generation_authorization"]["state_sha256"] = digest(state_path)
            self.assertIn("generation authorization state integrity failed", validate_receipt(receipt, root))
            receipt, _, auth_path = self.build_case(root)
            auth_path.write_text("{}", encoding="utf-8")
            self.assertIn("generation authorization state integrity failed", validate_receipt(receipt, root))

    def test_rejects_hash_only_spatial_source_for_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            receipt, _, _ = self.build_case(root)
            spec_path = root / "source-spec.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            del spec["source_truth"]["artifacts"][0]["evidence_path"]
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            receipt["source_view"]["spec_sha256"] = digest(spec_path)
            errors = validate_receipt(receipt, root)
            self.assertTrue(any("adoption visualization requires current evidence_path source artifacts" in error for error in errors))

    def test_rejects_write_content_not_linked_to_adopted_revision(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            receipt, _, _ = self.build_case(root)
            artifact_path = root / "artifacts" / "adoption.json"
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            payload["source_scene"]["revision"] = "other-revision"
            artifact_path.write_text(json.dumps(payload), encoding="utf-8")
            receipt["artifact_writes"][0]["after_sha256"] = digest(artifact_path)
            self.assertIn(
                "adoption write content is not linked to the adopted scene revision",
                validate_receipt(receipt, root),
            )


if __name__ == "__main__":
    unittest.main()
