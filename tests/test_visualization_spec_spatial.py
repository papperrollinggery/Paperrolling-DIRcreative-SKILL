from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dircreative_visualization_spec import validate_document


class SpatialSnapshotContractTests(unittest.TestCase):
    def complete_presentation_spec(self) -> dict:
        scene_path = ROOT / "examples/spatial-dialogue/scene.json"
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        scene_hash = hashlib.sha256(scene_path.read_bytes()).hexdigest()
        snapshot = copy.deepcopy(scene)
        snapshot.update(
            source_refs=[f"{scene['scene_id']}#/revision"],
            scene_state_sha256=scene_hash,
        )
        return {
            "spec_version": "1.1",
            "interaction_mode": "presentation_only",
            "view_id": "blocking-camera-full-snapshot",
            "execution_context": "standalone_chat",
            "controller": {"surface_owner": "dircreative", "user_facing": True},
            "view": {"intent": "blocking_camera", "display_mode": "inline", "customer_stage_label": "站位与镜位"},
            "source_truth": {
                "artifacts": [{
                    "artifact_id": scene["scene_id"],
                    "version": scene["revision"],
                    "sha256": scene_hash,
                    "evidence_path": "examples/spatial-dialogue/scene.json",
                    "lifecycle_status": "current",
                }]
            },
            "presentation": {"spatial_scene": snapshot},
            "interactions": {"local": ["select"], "actions": [], "max_actions": 2, "deep_navigation": False, "nested_scroll": False},
            "write_boundary": {
                "preview_only": True,
                "confirmation_required": False,
                "writes_authoritative_state": False,
                "write_owner": "dircreative",
                "possible_write_targets": [],
                "forbidden_claims": ["lock", "readiness", "acceptance", "completion", "generation_authorization"],
            },
            "fallback": {"format": "markdown", "content": scene["description"]},
        }

    def test_complete_snapshot_matches_bound_evidence_json(self) -> None:
        self.assertEqual(validate_document(self.complete_presentation_spec(), project_root=ROOT), [])

    def test_complete_snapshot_rejects_changed_entity_under_unchanged_hash(self) -> None:
        spec = self.complete_presentation_spec()
        spec["presentation"]["spatial_scene"]["entities"][0]["position"] = [0.1, 0.1]
        self.assertIn(
            "presentation spatial_scene snapshot does not match bound evidence JSON",
            validate_document(spec, project_root=ROOT),
        )

    def test_complete_snapshot_requires_real_evidence_path(self) -> None:
        spec = self.complete_presentation_spec()
        del spec["source_truth"]["artifacts"][0]["evidence_path"]
        self.assertIn(
            "presentation spatial_scene snapshot requires an evidence_path source artifact",
            validate_document(spec, project_root=ROOT),
        )

    def test_binding_fields_without_renderable_scene_are_rejected(self) -> None:
        spec = self.complete_presentation_spec()
        source = spec["presentation"]["spatial_scene"]
        spec["presentation"]["spatial_scene"] = {key: source[key] for key in ("scene_id", "source_refs", "scene_state_sha256")}
        self.assertTrue(any("presentation spatial_scene invalid:" in error for error in validate_document(spec, project_root=ROOT)))


if __name__ == "__main__":
    unittest.main()
