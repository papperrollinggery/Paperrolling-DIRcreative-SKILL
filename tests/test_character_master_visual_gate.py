from __future__ import annotations

import sys
import os
import tempfile
import unittest
import io
import json
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_character_master_visual_gate as gate  # noqa: E402
import dircreative_media_forward_audit as media_audit  # noqa: E402


def probe(full_body_count: int) -> dict:
    bodies = [
        {
            "center_x": 0.38 + index * 0.14,
            "joint_span": 0.66,
            "subject_height": 0.80,
            "min_y": 0.08,
            "max_y": 0.86,
            "head_extent_above_shoulders": 0.11,
            "subject_top_clearance": 0.04,
            "subject_bottom_clearance": 0.04,
            "visible_wrist_count": 2,
            "visible_elbow_count": 2,
            "visible_upper_limb_joint_count": 4,
            "human_rect_index": index,
            "human_rect_min_x": 0.33 + index * 0.14,
            "human_rect_max_x": 0.43 + index * 0.14,
        }
        for index in range(full_body_count)
    ]
    return {
        "backend": "apple-vision-human-body-pose-v1",
        "body_pose_count": full_body_count + 1,
        "face_count": 4,
        "faces": [],
        "human_rectangle_count": full_body_count,
        "full_body_count": full_body_count,
        "full_bodies": bodies,
        "left_closeup_face_count": 1,
        "left_closeup_faces": [{"center_x": 0.15, "center_y": 0.55, "width": 0.18, "height": 0.28}],
        "left_portrait_subject_height": 0.82,
        "right_face_count": 3,
        "right_full_height_component_count": full_body_count,
        "right_full_height_components": bodies,
    }


class CharacterMasterVisualGateTests(unittest.TestCase):
    def test_two_full_bodies_cannot_be_claimed_as_four_view_master(self):
        errors = gate.evaluate_probe(probe(2))
        self.assertIn("character_master_requires_four_full_bodies", errors)

    def test_four_separated_full_bodies_and_left_portrait_pass_structure(self):
        self.assertEqual(gate.evaluate_probe(probe(4)), [])

    def test_missing_left_closeup_face_blocks(self):
        value = probe(4)
        value["left_closeup_face_count"] = 0
        self.assertIn("far_left_closeup_face_not_detected", gate.evaluate_probe(value))

    def test_subject_below_declared_75_percent_height_is_blocked(self):
        value = probe(4)
        value["full_bodies"][0]["subject_height"] = 0.70
        self.assertIn("full_body_subject_height_below_75_percent", gate.evaluate_probe(value))

    def test_cropped_head_body_is_blocked_without_requiring_a_face(self):
        value = probe(4)
        value["full_bodies"][3]["head_extent_above_shoulders"] = 0.02
        value["full_bodies"][3]["subject_top_clearance"] = 0.0
        errors = gate.evaluate_probe(value)
        self.assertIn("full_body_head_extent_incomplete", errors)
        self.assertIn("full_body_touches_frame_edge", errors)

    def test_missing_forearms_and_hands_are_blocked(self):
        value = probe(4)
        value["full_bodies"][1]["visible_wrist_count"] = 0
        value["full_bodies"][1]["visible_elbow_count"] = 0
        value["full_bodies"][1]["visible_upper_limb_joint_count"] = 0
        errors = gate.evaluate_probe(value)
        self.assertIn("full_body_upper_limb_endpoint_incomplete", errors)

    def test_nonprofile_body_requires_both_visible_forearms(self):
        value = probe(4)
        body = value["full_bodies"][0]
        body["visible_wrist_count"] = 1
        body["visible_elbow_count"] = 1
        body["visible_upper_limb_joint_count"] = 2
        self.assertIn(
            "full_body_upper_limb_endpoint_incomplete",
            gate.evaluate_probe(value),
        )

    def test_middle_profile_slot_allows_one_occluded_arm(self):
        value = probe(4)
        body = value["full_bodies"][1]
        body["visible_wrist_count"] = 1
        body["visible_elbow_count"] = 1
        body["visible_upper_limb_joint_count"] = 2
        self.assertEqual(gate.evaluate_probe(value), [])

    def test_duplicate_human_rectangle_cannot_count_as_two_bodies(self):
        value = probe(4)
        value["full_bodies"][1]["human_rect_index"] = 0
        value["full_bodies"][1]["human_rect_min_x"] = value["full_bodies"][0][
            "human_rect_min_x"
        ]
        value["full_bodies"][1]["human_rect_max_x"] = value["full_bodies"][0][
            "human_rect_max_x"
        ]
        errors = gate.evaluate_probe(value)
        self.assertIn("full_body_human_rectangle_not_unique", errors)

    def test_small_left_portrait_is_blocked(self):
        value = probe(4)
        value["left_portrait_subject_height"] = 0.50
        self.assertIn("left_portrait_subject_height_below_75_percent", gate.evaluate_probe(value))

    def test_headless_mode_uses_silhouettes_and_rejects_body_faces(self):
        value = probe(4)
        self.assertIn(
            "headless_master_contains_body_face",
            gate.evaluate_probe(value, mode="headless_safe"),
        )
        value["right_face_count"] = 0
        self.assertEqual(gate.evaluate_probe(value, mode="headless_safe"), [])
        receipt = gate.make_receipt(
            asset_id="CHAR-HEADLESS",
            asset_truth_sha256="d" * 64,
            image_evidence={"sha256": "a" * 64, "pixel_sha256": "b" * 64},
            probe=value,
            checked_at="2026-09-04T00:00:00Z",
            mode="headless_safe",
            derived_from_asset_id="CHAR-BASE",
            approved_source_master_sha256="c" * 64,
        )
        self.assertEqual(receipt["status"], "applied_unverified")

    def test_four_thin_vertical_outlines_are_not_headless_bodies(self):
        image = Image.new("RGB", (1600, 900), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((70, 80, 390, 820), fill=(70, 90, 100))
        for index in range(4):
            left = 500 + index * 275
            draw.rectangle((left, 90, left + 12, 820), outline="black", width=4)
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        vision = probe(0)
        vision["faces"] = []
        vision["right_face_count"] = 0
        vision.update(gate.foreground_layout(encoded.getvalue(), vision))
        self.assertLess(vision["right_full_height_component_count"], 4)
        self.assertIn(
            "headless_master_requires_four_full_body_silhouettes",
            gate.evaluate_probe(vision, mode="headless_safe"),
        )

    def test_four_solid_rectangles_are_not_headless_bodies(self):
        image = Image.new("RGB", (1600, 900), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((70, 80, 390, 820), fill=(70, 90, 100))
        for index in range(4):
            left = 500 + index * 275
            draw.rectangle((left, 80, left + 140, 820), fill="black")
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        vision = probe(0)
        vision["faces"] = []
        vision.update(gate.foreground_layout(encoded.getvalue(), vision))
        self.assertLess(vision["right_full_height_component_count"], 4)

    def test_portrait_face_must_overlap_component_in_both_axes(self):
        image = Image.new("RGB", (1600, 900), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((70, 220, 390, 880), fill=(70, 90, 100))
        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        vision = probe(0)
        vision["left_closeup_faces"] = [
            {"center_x": 0.15, "center_y": 0.94, "width": 0.12, "height": 0.18}
        ]
        layout = gate.foreground_layout(encoded.getvalue(), vision)
        self.assertEqual(layout["left_portrait_subject_height"], 0.0)

    def test_receipt_cannot_grant_completion_or_skip_semantic_review(self):
        evidence = {"sha256": "a" * 64, "pixel_sha256": "b" * 64}
        receipt = {
            "contract_id": gate.CONTRACT_ID,
            "status": "pass",
            "asset_id": "CHAR-001",
            "asset_truth_sha256": "c" * 64,
            "mode": "headed_master",
            "derived_from_asset_id": None,
            "approved_source_master_sha256": None,
            "image_sha256": evidence["sha256"],
            "pixel_sha256": evidence["pixel_sha256"],
            "checked_at": "2026-09-04T00:00:00Z",
            "vision_helper_sha256": gate.vision_helper_sha256(),
            "measurement_contract": {
                "full_body_subject_height_floor": gate.MIN_FULL_BODY_SUBJECT_HEIGHT,
                "left_portrait_subject_height_floor": gate.MIN_FULL_BODY_SUBJECT_HEIGHT,
                "full_body_joint_span_detection_floor": gate.MIN_FULL_BODY_JOINT_SPAN,
                "full_body_head_extent_floor": gate.MIN_FULL_BODY_HEAD_EXTENT,
                "full_body_frame_edge_clearance_floor": gate.MIN_FULL_BODY_FRAME_EDGE_CLEARANCE,
                "full_body_visible_wrist_floor": gate.MIN_FULL_BODY_VISIBLE_WRISTS,
                "full_body_visible_elbow_floor": gate.MIN_FULL_BODY_VISIBLE_ELBOWS,
                "full_body_visible_upper_limb_joint_floor": gate.MIN_FULL_BODY_VISIBLE_UPPER_LIMB_JOINTS,
                "full_body_terminal_slot_visible_upper_limb_joint_floor": gate.MIN_TERMINAL_SLOT_VISIBLE_UPPER_LIMB_JOINTS,
                "full_body_human_rectangle_iou_ceiling": gate.MAX_FULL_BODY_RECTANGLE_IOU,
                "subject_height_source": "VNDetectHumanRectanglesRequest.boundingBox.height",
                "head_extent_source": "human rectangle top minus highest detected shoulder; neck required",
                "frame_edge_clearance_source": "VNDetectHumanRectanglesRequest.boundingBox minY/maxY",
                "upper_limb_source": "canonical sorted slots: front/back require both wrists and elbows; side slots allow far-arm occlusion",
                "distinct_body_source": "unique matched VNDetectHumanRectanglesRequest index and horizontal IoU",
                "headless_silhouette_source": "four fixed right-side slots with foreground component heuristics; never self-passing",
                "portrait_height_source": "left-slot foreground component containing the detected face center",
            },
            "vision_tool_identity": gate.swift_tool_identity(),
            "vision_probe": probe(4),
            "errors": [],
            "visual_orientation_material_review_required": True,
            "completion_claim_allowed": False,
        }
        receipt["receipt_sha256"] = gate.canonical_sha256(receipt)
        self.assertEqual(
            gate.validate_receipt(
                receipt,
                asset_id="CHAR-001",
                asset_truth_sha256="c" * 64,
                image_evidence=evidence,
                expected_mode="headed_master",
                expected_derived_from_asset_id=None,
                expected_approved_source_master_sha256=None,
            ),
            [],
        )
        receipt["completion_claim_allowed"] = True
        receipt["receipt_sha256"] = gate.canonical_sha256(
            {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        )
        self.assertIn(
            "character_master_visual_completion_authority_invalid",
            gate.validate_receipt(
                receipt,
                asset_id="CHAR-001",
                asset_truth_sha256="c" * 64,
                image_evidence=evidence,
                expected_mode="headed_master",
                expected_derived_from_asset_id=None,
                expected_approved_source_master_sha256=None,
            ),
        )

    def test_path_shadow_cannot_replace_system_swift(self):
        with tempfile.TemporaryDirectory() as raw:
            fake = Path(raw) / "swift"
            fake.write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
            fake.chmod(0o755)
            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{raw}:{old_path}"
            try:
                identity = gate.swift_tool_identity()
            finally:
                os.environ["PATH"] = old_path
        self.assertEqual(identity["path"], "/usr/bin/swift")

    def test_headless_reviewer_label_without_detached_authorization_cannot_unlock(self):
        with tempfile.TemporaryDirectory() as raw:
            _review, errors = gate.load_headless_review_authorization(
                {
                    "asset_id": "CHAR-HEADLESS",
                    "truth_sha256": "c" * 64,
                    "generated_file": "headless.png",
                },
                base_dir=Path(raw),
                image_evidence={"sha256": "a" * 64, "pixel_sha256": "b" * 64},
            )
        self.assertIn("headless_review_authorization_missing_or_invalid", errors)

    def test_visual_manifest_without_detached_authorization_cannot_unlock(self):
        with tempfile.TemporaryDirectory() as raw:
            _review, errors = gate.load_visual_review_authorization(
                {
                    "asset_id": "SB-001",
                    "role": "storyboard_frame",
                    "truth_sha256": "c" * 64,
                    "generated_file": "frame.png",
                },
                base_dir=Path(raw),
                image_evidence={"sha256": "a" * 64, "pixel_sha256": "b" * 64},
            )
        self.assertIn("visual_review_authorization_missing_or_invalid", errors)

    def test_separate_host_view_and_claim_can_authorize_without_private_key(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as host_raw:
            root = Path(raw).resolve()
            trusted = Path(host_raw).resolve()
            image = root / "frame.png"
            image.write_bytes(b"fixture")
            asset = {
                "asset_id": "SB-001",
                "role": "storyboard_frame",
                "truth_sha256": "c" * 64,
                "generated_file": image.name,
            }
            viewed_payload = b"fixture"
            evidence = {
                "sha256": hashlib.sha256(viewed_payload).hexdigest(),
                "pixel_sha256": "b" * 64,
            }
            core = {
                "contract_id": "visual_asset_host_review_authorization_v1",
                "purpose": "visual_asset_downstream_authorization",
                "source": "independent_host_review",
                "reviewer_task_id": "review-task-001",
                "execution_task_id": "execution-task-001",
                "asset_id": asset["asset_id"],
                "asset_role": asset["role"],
                "asset_truth_sha256": asset["truth_sha256"],
                "image_sha256": evidence["sha256"],
                "pixel_sha256": evidence["pixel_sha256"],
                "decision": "pass",
            }
            claim = gate.canonical_sha256(core)
            request_payload = {
                "contract_id": "visual_asset_review_request_v1",
                "execution_task_id": core["execution_task_id"],
                "asset_id": core["asset_id"],
                "asset_role": core["asset_role"],
                "asset_truth_sha256": core["asset_truth_sha256"],
                "image_sha256": core["image_sha256"],
                "pixel_sha256": core["pixel_sha256"],
            }
            request_text = "DIRCREATIVE_ASSET_REVIEW_REQUEST " + json.dumps(
                request_payload, sort_keys=True, separators=(",", ":")
            )
            records = [
                {"type": "session_meta", "payload": {"id": "review-task-001"}},
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "id": "review-request-001",
                        "role": "user",
                        "content": [{"type": "input_text", "text": request_text}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call",
                        "name": "exec",
                        "id": "view-event-001",
                        "call_id": "view-call-001",
                        "input": media_audit.visual_view_trace_source(str(image)),
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call_output",
                        "id": "view-output-001",
                        "call_id": "view-call-001",
                        "output": [
                            {
                                "type": "input_image",
                                "image_url": "data:image/png;base64,"
                                + __import__("base64").b64encode(viewed_payload).decode(),
                            }
                        ],
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "agent_message",
                        "message": media_audit.VISUAL_REVIEW_CLAIM_MARKER + claim,
                    },
                },
            ]
            host_bytes = b"".join(
                (json.dumps(item, separators=(",", ":")) + "\n").encode()
                for item in records
            )
            host_log = trusted / "review.jsonl"
            host_log.write_bytes(host_bytes)
            execution_records = [
                {"type": "session_meta", "payload": {"id": "execution-task-001"}},
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "image_generation_end",
                        "result": __import__("base64").b64encode(viewed_payload).decode(),
                    },
                },
            ]
            execution_bytes = b"".join(
                (json.dumps(item, separators=(",", ":")) + "\n").encode()
                for item in execution_records
            )
            execution_log = trusted / "execution.jsonl"
            execution_log.write_bytes(execution_bytes)
            review = {
                **core,
                "host_trace": {
                    "host_log_relative_path": host_log.name,
                    "thread_id": "review-task-001",
                    "prefix_bytes": len(host_bytes),
                    "prefix_sha256": hashlib.sha256(host_bytes).hexdigest(),
                    "review_claim_sha256": claim,
                    "view_event_ids": ["view-event-001"],
                    "review_request_event_id": "review-request-001",
                    "review_request_sha256": hashlib.sha256(request_text.encode()).hexdigest(),
                    "evidence_level": "unsigned_host_trace",
                    "cryptographically_signed": False,
                    "execution_trace": {
                        "host_log_relative_path": execution_log.name,
                        "thread_id": "execution-task-001",
                        "prefix_bytes": len(execution_bytes),
                        "prefix_sha256": hashlib.sha256(execution_bytes).hexdigest(),
                    },
                },
            }
            review["receipt_sha256"] = gate.canonical_sha256(review)
            (root / "frame.visual-review-host.json").write_text(
                json.dumps(review), encoding="utf-8"
            )
            _loaded, errors = gate.load_visual_review_host_authorization(
                asset,
                base_dir=root,
                image_evidence=evidence,
                expected_execution_task_id="execution-task-001",
                _trusted_host_root=trusted,
            )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
