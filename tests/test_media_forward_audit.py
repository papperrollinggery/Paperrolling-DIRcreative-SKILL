from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_media_forward_audit as media_forward  # noqa: E402


V2_MAX_PREFIX_BYTES = 16 * 1024 * 1024
V2_MAX_LINE_BYTES = 15 * 1024 * 1024
V2_MAX_INLINE_PNG_BYTES = 10 * 1024 * 1024
MAX_STREAM_READ_BYTES = 64 * 1024


class MediaForwardHostTraceLimitTests(unittest.TestCase):
    @staticmethod
    def generation_descriptor(prefix: bytes) -> dict[str, object]:
        return {
            "thread_id": "trace-limit-test",
            "prefix_bytes": len(prefix),
            "prefix_sha256": hashlib.sha256(prefix).hexdigest(),
        }

    def parse(self, payload: bytes) -> tuple[dict[str, object], list[str]]:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "host-trace.jsonl"
            path.write_bytes(payload)
            return media_forward.parse_host_trace_prefix(
                path,
                self.generation_descriptor(payload),
                label="generation host trace",
            )

    def test_v2_limits_are_small_enough_for_desktop_host_traces(self) -> None:
        self.assertEqual(media_forward.MAX_HOST_TRACE_PREFIX_BYTES, V2_MAX_PREFIX_BYTES)
        self.assertEqual(media_forward.MAX_HOST_TRACE_LINE_BYTES, V2_MAX_LINE_BYTES)
        self.assertEqual(media_forward.MAX_HOST_TRACE_INLINE_PNG_BYTES, V2_MAX_INLINE_PNG_BYTES)

    def test_rejects_a_pre_v2_prefix_with_a_sealed_prefix_migration_error(self) -> None:
        descriptor = self.generation_descriptor(b"x")
        descriptor["prefix_bytes"] = V2_MAX_PREFIX_BYTES + 1
        failures = media_forward.trace_descriptor_failures(
            descriptor,
            expected_fields=media_forward.GENERATION_HOST_TRACE_FIELDS,
            label="generation host trace",
        )
        self.assertEqual(
            failures,
            [
                "generation host trace.prefix_bytes exceeds the v2 sealed-prefix limit "
                "(16 MiB); re-export a smaller prefix"
            ],
        )

    def test_rejects_a_record_one_byte_over_the_v2_line_limit(self) -> None:
        prefix = b'{"payload":{"type":"event_msg","message":"'
        suffix = b'"}}'
        line = prefix + (b"x" * (V2_MAX_LINE_BYTES + 1 - len(prefix) - len(suffix))) + suffix
        _, failures = self.parse(line + b"\n")
        self.assertEqual(
            failures,
            [
                "generation host trace line 1 exceeds the v2 audit limit (15 MiB); "
                "re-export a sealed trace with each inline result record below 15 MiB"
            ],
        )

    def test_accepts_a_bounded_inline_png_generation_result(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + (b"x" * (3 * 1024 * 1024))
        request = {"prompt": "trace limit fixture", "referenced_image_paths": []}
        records = [
            {
                "timestamp": "2026-09-04T00:00:00Z",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "id": "request-1",
                    "call_id": "outer-1",
                    "input": media_forward.imagegen_trace_source(request),
                },
            },
            {
                "timestamp": "2026-09-04T00:00:01Z",
                "payload": {
                    "type": "image_generation_end",
                    "call_id": "imagegen-1",
                    "status": "completed",
                    "result": base64.b64encode(png).decode("ascii"),
                },
            },
        ]
        payload = b"".join(
            json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n"
            for record in records
        )

        evidence, failures = self.parse(payload)

        self.assertEqual(failures, [])
        self.assertIn("imagegen-1", evidence["generation_events"])

    def test_inline_png_above_trace_limit_has_specific_error(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + (b"x" * V2_MAX_INLINE_PNG_BYTES)
        request = {"prompt": "trace limit fixture", "referenced_image_paths": []}
        records = [
            {
                "timestamp": "2026-09-04T00:00:00Z",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "id": "request-1",
                    "call_id": "outer-1",
                    "input": media_forward.imagegen_trace_source(request),
                },
            },
            {
                "timestamp": "2026-09-04T00:00:01Z",
                "payload": {
                    "type": "image_generation_end",
                    "call_id": "imagegen-1",
                    "status": "completed",
                    "result": base64.b64encode(png).decode("ascii"),
                },
            },
        ]
        payload = b"".join(
            json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n"
            for record in records
        )
        _evidence, failures = self.parse(payload)
        self.assertEqual(
            failures,
            ["generation host trace inline PNG exceeds the 10 MiB trace limit; larger inline results are unsupported by host-trace audit"],
        )

    def test_reads_a_sealed_prefix_in_small_streaming_chunks(self) -> None:
        records = [
            {"payload": {"type": "event_msg", "message": "x" * 40_000}}
            for _ in range(3)
        ]
        payload = b"".join(
            json.dumps(record, separators=(",", ":")).encode("utf-8") + b"\n"
            for record in records
        )
        reads: list[int] = []
        original_read = os.read

        def bounded_read(fd: int, amount: int) -> bytes:
            reads.append(amount)
            self.assertLessEqual(amount, MAX_STREAM_READ_BYTES)
            return original_read(fd, amount)

        with patch.object(media_forward.os, "read", side_effect=bounded_read):
            evidence, failures = self.parse(payload)

        self.assertEqual(failures, [])
        self.assertIsNone(evidence["thread_id"])
        self.assertGreater(len(reads), 1)

    def test_tool_output_cannot_mint_visual_review_claim(self) -> None:
        claim = "a" * 64
        records = [
            {"type": "session_meta", "payload": {"id": "review-task"}},
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "id": "tool-output",
                    "call_id": "tool-call",
                    "output": media_forward.VISUAL_REVIEW_CLAIM_MARKER + claim,
                },
            },
        ]
        payload = b"".join(
            json.dumps(record, separators=(",", ":")).encode() + b"\n"
            for record in records
        )
        descriptor = {
            "thread_id": "review-task",
            "prefix_bytes": len(payload),
            "prefix_sha256": hashlib.sha256(payload).hexdigest(),
            "review_request_event_id": "request-event",
            "view_event_ids": ["view-event"],
            "review_claim_sha256": claim,
            "evidence_level": "unsigned_host_trace",
            "cryptographically_signed": False,
        }
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "review.jsonl"
            path.write_bytes(payload)
            evidence, failures = media_forward.parse_host_trace_prefix(
                path,
                descriptor,
                label="review host trace",
            )
        self.assertEqual(failures, [])
        self.assertEqual(evidence["review_claims"], set())


if __name__ == "__main__":
    unittest.main()
