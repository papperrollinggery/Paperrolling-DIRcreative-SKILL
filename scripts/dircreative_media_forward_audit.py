#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import os
import re
import ssl
import stat
import struct
import subprocess
import sys
import tempfile
import zlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REFERENCE_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
MAX_PNG_FILE_BYTES = 128 * 1024 * 1024
MAX_PNG_PIXELS = 100_000_000
MAX_DECODED_PNG_BYTES = 512 * 1024 * 1024
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_C2PATOOL_BYTES = 256 * 1024 * 1024
MAX_HOST_TRACE_PREFIX_BYTES = 512 * 1024 * 1024
MAX_HOST_TRACE_LINE_BYTES = 64 * 1024 * 1024
C2PATOOL_ALLOWED_SHA256 = frozenset(
    {
        # contentauth/c2pa-rs c2patool-v0.27.0 universal-apple-darwin binary.
        "3f4c145151498980533da1588872aa32c852abdf1ac4e37f25ca6656fa9ede52",
    }
)
OPENAI_SIGNING_CA_SHA256 = frozenset(
    {
        # Pinned intermediates observed in independently signed OpenAI Media
        # Service outputs. c2patool still validates the leaf, claim, and data hash.
        "d54896be1e48e09109e02c7596d0371611288e4c9679376a1fa0045432dc36f1",
        "fdfa38815cb29c848de68918b772457bb364a32ecc06e4f32cbdd3dd95a51928",
    }
)
REQUIRED_C2PA_SUCCESS_CODES = frozenset(
    {
        "claimSignature.validated",
        "assertion.dataHash.match",
        "assertion.hashedURI.match",
    }
)
REQUIRED_MEDIA_CONTRACT_PATHS = frozenset(
    {
        "docs/film-preproduction/capability-aware-generation-policy.md",
        "docs/film-preproduction/qa/retry-rules.md",
        "docs/film-preproduction/reference-locking-policy.md",
        "skills/dircreative/references/generation-delivery.md",
        "skills/dircreative/routes/delivery-audit.md",
    }
)
PNG_BIT_DEPTHS = {
    0: {1, 2, 4, 8, 16},
    2: {8, 16},
    3: {1, 2, 4, 8},
    4: {8, 16},
    6: {8, 16},
}
PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
LEGACY_RECEIPT_FIELDS = {
    "schema_version",
    "product",
    "candidate_commit",
    "tested_commit",
    "media_type",
    "tool",
    "real_tool_execution",
    "video_verified",
    "verified_contract_paths",
    "references",
    "attempts",
    "multi_shot_evidence",
    "limitations",
}
V2_RECEIPT_FIELDS = {
    "schema_version",
    "product",
    "media_type",
    "candidate",
    "host_trace",
    "host_execution",
    "reference_assets",
    "continuity_lock",
    "generation_calls",
    "attempts",
    "shots",
    "video_verified",
    "limitations",
}
V2_CANDIDATE_FIELDS = {"commit", "observed_skill_paths"}
V2_HOST_TRACE_FIELDS = {
    "thread_id",
    "prefix_bytes",
    "prefix_sha256",
    "invocation_event_id",
    "candidate_observation_event_id",
    "evidence_level",
    "cryptographically_signed",
}
V2_HOST_FIELDS = {
    "actor_id",
    "task_id",
    "explicit_invocation",
    "explicit_invocation_sha256",
    "started_at",
    "completed_at",
    "evidence_level",
    "cryptographically_signed",
}
V2_REFERENCE_FIELDS = {"reference_id", "role", "artifact"}
V2_CALL_FIELDS = {
    "generation_id",
    "host_call_id",
    "host_call_id_status",
    "provider_response_id",
    "provider_response_id_status",
    "tool",
    "provider",
    "model",
    "started_at",
    "completed_at",
    "prompt",
    "prompt_sha256",
    "reference_inputs",
    "input_manifest_sha256",
    "output",
}
V2_INPUT_FIELDS = {"source_id", "role", "sha256"}
V2_ATTEMPT_FIELDS = {
    "attempt_id",
    "generation_id",
    "retry_of",
    "corrected_layer",
    "unchanged_lock_sha256",
}
V2_SHOT_FIELDS = {
    "shot_id",
    "generation_id",
    "inherits_from",
    "continuity_lock_sha256",
    "shot_delta",
    "shot_delta_sha256",
}
REVIEW_FIELDS = {
    "schema_version",
    "product",
    "candidate_commit",
    "execution_receipt_sha256",
    "host_trace",
    "reviewer",
    "rubric",
    "rubric_sha256",
    "artifact_reviews",
    "continuity_review",
    "limitations",
}
REVIEW_HOST_TRACE_FIELDS = {
    "thread_id",
    "prefix_bytes",
    "prefix_sha256",
    "review_request_event_id",
    "view_event_ids",
    "review_claim_sha256",
    "evidence_level",
    "cryptographically_signed",
}
REVIEWER_FIELDS = {
    "actor_id",
    "task_id",
    "review_method",
    "input_scope",
    "started_at",
    "completed_at",
}
ARTIFACT_REVIEW_FIELDS = {"subject_id", "artifact_sha256", "decision", "observations"}
CONTINUITY_REVIEW_FIELDS = {
    "shot_ids",
    "decision",
    "continuity_lock_sha256",
    "observations",
}
REQUIRED_CANDIDATE_SKILL_PATHS = frozenset(
    {
        "skills/dircreative/SKILL.md",
        "skills/dircreative/routes/delivery-audit.md",
        "skills/dircreative/references/generation-delivery.md",
    }
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "git command failed")
    return proc.stdout.strip()


def git_bytes(commit: str, relative: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.decode("utf-8", errors="replace").strip())
    return proc.stdout


def current_head() -> str:
    return git("rev-parse", "HEAD")


def commit_time(commit: str) -> str:
    return git("show", "-s", "--format=%cI", commit)


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


IMAGEGEN_TRACE_MARKER = re.compile(
    r"(?m)^// DIRCREATIVE_IMAGEGEN_REQUEST_BASE64:([A-Za-z0-9_-]+={0,2})$"
)
VISUAL_VIEW_TRACE_MARKER = re.compile(
    r"(?m)^// DIRCREATIVE_VISUAL_VIEW_BASE64:([A-Za-z0-9_-]+={0,2})$"
)
EXECUTION_REQUEST_TRACE_MARKER = re.compile(
    r"(?m)^DIRCREATIVE_EXECUTION_REQUEST_BASE64:([A-Za-z0-9_-]+={0,2})$"
)
VISUAL_REVIEW_REQUEST_TRACE_MARKER = re.compile(
    r"(?m)^DIRCREATIVE_VISUAL_REVIEW_REQUEST_BASE64:([A-Za-z0-9_-]+={0,2})$"
)
CANDIDATE_OBSERVATION_MARKER = "DIRCREATIVE_CANDIDATE_OBSERVATION "
VISUAL_REVIEW_CLAIM_MARKER = "DIRCREATIVE_VISUAL_REVIEW_CLAIM "


def trace_marker_base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def imagegen_trace_source(request: dict[str, Any]) -> str:
    request_json = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    marker = trace_marker_base64(request_json.encode("utf-8"))
    return (
        '// @exec: {"yield_time_ms": 120000, "max_output_tokens": 1000}\n'
        f"// DIRCREATIVE_IMAGEGEN_REQUEST_BASE64:{marker}\n"
        f"const request = JSON.parse({json.dumps(request_json)});\n"
        "const result = await tools.image_gen__imagegen(request);\n"
        "generatedImage(result);"
    )


def visual_view_trace_source(path: str) -> str:
    marker = trace_marker_base64(path.encode("utf-8"))
    return (
        f"// DIRCREATIVE_VISUAL_VIEW_BASE64:{marker}\n"
        f"const viewPath = {json.dumps(path)};\n"
        "const view = await tools.view_image({path: viewPath, detail: \"original\"});\n"
        "image(view.image_url, \"original\");"
    )


def execution_request_trace_text(request: dict[str, Any]) -> str:
    invocation = request.get("explicit_invocation") if isinstance(request, dict) else None
    if not isinstance(invocation, str) or not invocation.strip():
        raise ValueError("execution request requires an explicit invocation")
    request_json = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    marker = trace_marker_base64(request_json.encode("utf-8"))
    return (
        f"DIRCREATIVE_EXECUTION_REQUEST_BASE64:{marker}\n"
        f"{invocation}\n\n"
        "This is an isolated DIRcreative candidate execution. Read the exact candidate "
        "paths bound in the request before producing media. Follow the Delivery route: "
        "make one deliberately reviewable first attempt, correct only the named failed "
        "layer in attempt two, then produce three distinct shots from the accepted anchor. "
        "Use the bound references for every generation and do not claim video verification."
    )


def visual_review_request_trace_text(request: dict[str, Any]) -> str:
    if not isinstance(request, dict):
        raise ValueError("visual review request must be an object")
    request_json = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    marker = trace_marker_base64(request_json.encode("utf-8"))
    return (
        f"DIRCREATIVE_VISUAL_REVIEW_REQUEST_BASE64:{marker}\n"
        "Perform an independent visual review using only the raw reference and generated "
        "artifacts plus the rubric encoded in the bound request. Do not read executor QA "
        "conclusions. Open every generated artifact exactly once with the audit module's "
        "visual_view_trace_source(path) template, then return concrete visible observations "
        "for each artifact and the three-shot continuity sequence."
    )


def execution_request_record(payload: dict[str, Any]) -> dict[str, Any]:
    host = payload.get("host_execution")
    if not isinstance(host, dict):
        host = {}
    return {
        "schema_version": "1.0.0",
        "media_type": "image",
        "candidate": payload.get("candidate"),
        "explicit_invocation": host.get("explicit_invocation"),
        "explicit_invocation_sha256": host.get("explicit_invocation_sha256"),
    }


def visual_review_request_record(
    execution_payload: dict[str, Any],
    review_payload: dict[str, Any],
) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    references = execution_payload.get("reference_assets")
    if not isinstance(references, list):
        references = []
    for reference in references:
        if not isinstance(reference, dict) or not isinstance(reference.get("artifact"), dict):
            continue
        artifact = reference["artifact"]
        artifacts.append(
            {
                "kind": "reference",
                "artifact_id": reference.get("reference_id"),
                "path": artifact.get("path"),
                "sha256": artifact.get("sha256"),
            }
        )
    calls = execution_payload.get("generation_calls")
    if not isinstance(calls, list):
        calls = []
    for call in calls:
        if not isinstance(call, dict) or not isinstance(call.get("output"), dict):
            continue
        output = call["output"]
        artifacts.append(
            {
                "kind": "generated_output",
                "artifact_id": call.get("generation_id"),
                "path": output.get("path"),
                "sha256": output.get("sha256"),
            }
        )
    candidate = execution_payload.get("candidate")
    if not isinstance(candidate, dict):
        candidate = {}
    return {
        "schema_version": "1.0.0",
        "candidate_commit": candidate.get("commit"),
        "execution_receipt_sha256": review_payload.get("execution_receipt_sha256"),
        "input_scope": "raw_references_outputs_and_rubric_only",
        "rubric": review_payload.get("rubric"),
        "rubric_sha256": review_payload.get("rubric_sha256"),
        "allowed_artifacts": artifacts,
    }


def decode_trace_marker(value: str, label: str) -> bytes:
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{label} marker is invalid base64") from exc


def trace_text(payload: dict[str, Any]) -> str:
    values: list[str] = []
    for field in ("message", "text"):
        value = payload.get(field)
        if isinstance(value, str):
            values.append(value)
    for field in ("output", "content"):
        value = payload.get(field)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        values.append(text)
    return "\n".join(values)


def parse_candidate_observations(text: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith(CANDIDATE_OBSERVATION_MARKER):
            continue
        try:
            value = json.loads(line[len(CANDIDATE_OBSERVATION_MARKER) :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            observations.append(value)
    return observations


def parse_review_claims(text: str) -> set[str]:
    claims: set[str] = set()
    for line in text.splitlines():
        if line.startswith(VISUAL_REVIEW_CLAIM_MARKER):
            digest = line[len(VISUAL_REVIEW_CLAIM_MARKER) :].strip()
            if SHA256_RE.fullmatch(digest):
                claims.add(digest)
    return claims


def sealed_trace_request(
    text: str,
    *,
    marker: re.Pattern[str],
    renderer: Callable[[dict[str, Any]], str],
    label: str,
) -> dict[str, Any] | None:
    matches = list(marker.finditer(text))
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"{label} contains multiple sealed request markers")
    try:
        request = json.loads(
            decode_trace_marker(matches[0].group(1), label).decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} sealed request is invalid JSON") from exc
    if not isinstance(request, dict):
        raise ValueError(f"{label} sealed request is not an object")
    try:
        rendered = renderer(request)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} sealed request has invalid fields") from exc
    if text.strip() != rendered:
        raise ValueError(f"{label} is not the sealed request template")
    return request


def trace_descriptor_failures(
    descriptor: Any,
    *,
    expected_fields: set[str],
    label: str,
) -> list[str]:
    if not isinstance(descriptor, dict) or set(descriptor) != expected_fields:
        return [f"{label} descriptor has invalid shape"]
    failures: list[str] = []
    thread_id = descriptor.get("thread_id")
    if not isinstance(thread_id, str) or not thread_id.strip() or len(thread_id) > 256:
        failures.append(f"{label}.thread_id must be one bounded identifier")
    prefix_bytes = descriptor.get("prefix_bytes")
    if (
        not isinstance(prefix_bytes, int)
        or isinstance(prefix_bytes, bool)
        or prefix_bytes <= 0
        or prefix_bytes > MAX_HOST_TRACE_PREFIX_BYTES
    ):
        failures.append(f"{label}.prefix_bytes is outside the audit limit")
    digest = descriptor.get("prefix_sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        failures.append(f"{label}.prefix_sha256 is invalid")
    if (
        descriptor.get("evidence_level") != "unsigned_host_trace"
        or descriptor.get("cryptographically_signed") is not False
    ):
        failures.append(f"{label} must be honestly labeled unsigned_host_trace")
    identifier_fields = (
        ("invocation_event_id", "candidate_observation_event_id")
        if expected_fields == V2_HOST_TRACE_FIELDS
        else ("review_request_event_id",)
    )
    for field in identifier_fields:
        value = descriptor.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            failures.append(f"{label}.{field} must be one bounded identifier")
    if expected_fields == REVIEW_HOST_TRACE_FIELDS:
        claim = descriptor.get("review_claim_sha256")
        if not isinstance(claim, str) or not SHA256_RE.fullmatch(claim):
            failures.append(f"{label}.review_claim_sha256 is invalid")
        event_ids = descriptor.get("view_event_ids")
        if (
            not isinstance(event_ids, list)
            or not event_ids
            or not all(
                isinstance(event_id, str) and event_id.strip() and len(event_id) <= 256
                for event_id in event_ids
            )
            or len(event_ids) != len(set(event_ids))
        ):
            failures.append(f"{label}.view_event_ids must be unique bounded identifiers")
    return failures


def parse_host_trace_prefix(
    path: Path,
    descriptor: dict[str, Any],
    *,
    label: str,
) -> tuple[dict[str, Any], list[str]]:
    failures = trace_descriptor_failures(
        descriptor,
        expected_fields=(
            V2_HOST_TRACE_FIELDS if label == "execution host trace" else REVIEW_HOST_TRACE_FIELDS
        ),
        label=label,
    )
    if failures:
        return {}, failures
    expanded = path.expanduser()
    if not expanded.is_absolute():
        return {}, [f"{label} path must be absolute"]
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        return {}, [f"{label} requires O_NOFOLLOW"]
    try:
        descriptor_fd = os.open(expanded, os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        return {}, [f"{label} cannot be opened safely: {exc}"]

    evidence: dict[str, Any] = {
        "thread_id": None,
        "execution_requests": {},
        "review_requests": {},
        "candidate_observations": {},
        "generation_events": {},
        "view_events": {},
        "review_claims": set(),
    }
    pending_generation: dict[str, Any] | None = None
    pending_views: dict[str, dict[str, Any]] = {}
    digest = hashlib.sha256()
    buffered = b""
    line_number = 0

    def consume_line(raw_line: bytes) -> None:
        nonlocal line_number, pending_generation
        line_number += 1
        if len(raw_line) > MAX_HOST_TRACE_LINE_BYTES:
            raise ValueError(f"{label} line {line_number} exceeds the audit limit")
        try:
            record = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} line {line_number} is invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{label} line {line_number} is not an object")
        payload = record.get("payload")
        if not isinstance(payload, dict):
            return
        if record.get("type") == "session_meta":
            session_id = payload.get("id") or payload.get("session_id")
            if isinstance(session_id, str):
                if evidence["thread_id"] not in {None, session_id}:
                    raise ValueError(f"{label} contains multiple session identities")
                evidence["thread_id"] = session_id
            return
        payload_type = payload.get("type")
        if payload_type == "message" and payload.get("role") == "user":
            text = trace_text(payload)
            execution_request = sealed_trace_request(
                text,
                marker=EXECUTION_REQUEST_TRACE_MARKER,
                renderer=execution_request_trace_text,
                label=label,
            )
            review_request = sealed_trace_request(
                text,
                marker=VISUAL_REVIEW_REQUEST_TRACE_MARKER,
                renderer=visual_review_request_trace_text,
                label=label,
            )
            if execution_request is not None and review_request is not None:
                raise ValueError(f"{label} user event mixes execution and review requests")
            event_id = payload.get("id")
            if (execution_request is not None or review_request is not None) and not isinstance(
                event_id, str
            ):
                raise ValueError(f"{label} sealed user request has no host event identity")
            if execution_request is not None:
                evidence["execution_requests"].setdefault(event_id, []).append(
                    execution_request
                )
            if review_request is not None:
                evidence["review_requests"].setdefault(event_id, []).append(review_request)
            return
        if payload_type == "custom_tool_call" and payload.get("name") == "exec":
            source = payload.get("input")
            if not isinstance(source, str):
                return
            generation_match = IMAGEGEN_TRACE_MARKER.search(source)
            if generation_match:
                if pending_generation is not None:
                    raise ValueError(f"{label} overlaps marked image generation requests")
                try:
                    request = json.loads(
                        decode_trace_marker(generation_match.group(1), label).decode("utf-8")
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"{label} marked generation request is invalid JSON") from exc
                if not isinstance(request, dict):
                    raise ValueError(f"{label} marked generation request is not an object")
                if source.strip() != imagegen_trace_source(request):
                    raise ValueError(f"{label} marked generation source is not the sealed template")
                pending_generation = {
                    "request": request,
                    "request_event_id": payload.get("id"),
                    "outer_call_id": payload.get("call_id"),
                    "started_at": record.get("timestamp"),
                }
            view_match = VISUAL_VIEW_TRACE_MARKER.search(source)
            if view_match:
                try:
                    view_path = decode_trace_marker(view_match.group(1), label).decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError(f"{label} marked view path is not UTF-8") from exc
                if source.strip() != visual_view_trace_source(view_path):
                    raise ValueError(f"{label} marked view source is not the sealed template")
                event_id = payload.get("id")
                call_id = payload.get("call_id")
                if not isinstance(event_id, str) or not isinstance(call_id, str):
                    raise ValueError(f"{label} marked view has no host event identity")
                pending_views[call_id] = {"event_id": event_id, "path": view_path}
            return
        if payload_type == "image_generation_end" and pending_generation is not None:
            host_call_id = payload.get("call_id")
            raw_result = payload.get("result")
            if (
                payload.get("status") != "completed"
                or not isinstance(host_call_id, str)
                or not isinstance(raw_result, str)
            ):
                raise ValueError(f"{label} marked image generation did not complete")
            try:
                image_bytes = base64.b64decode(raw_result, validate=True)
            except binascii.Error as exc:
                raise ValueError(f"{label} image result is invalid base64") from exc
            if (
                not image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
                or len(image_bytes) > MAX_PNG_FILE_BYTES
            ):
                raise ValueError(f"{label} image result is not one bounded PNG")
            generation = dict(pending_generation)
            generation.update(
                {
                    "host_call_id": host_call_id,
                    "completed_at": record.get("timestamp"),
                    "output_sha256": sha256_bytes(image_bytes),
                    "saved_path": payload.get("saved_path"),
                }
            )
            if host_call_id in evidence["generation_events"]:
                raise ValueError(f"{label} duplicates image generation event {host_call_id}")
            evidence["generation_events"][host_call_id] = generation
            pending_generation = None
            return
        if payload_type == "custom_tool_call_output":
            event_id = payload.get("id")
            text = trace_text(payload)
            if isinstance(event_id, str):
                for observation in parse_candidate_observations(text):
                    evidence["candidate_observations"].setdefault(event_id, []).append(observation)
            call_id = payload.get("call_id")
            pending_view = pending_views.pop(call_id, None) if isinstance(call_id, str) else None
            if pending_view is not None:
                output = payload.get("output")
                has_image = isinstance(output, list) and any(
                    isinstance(item, dict) and item.get("type") in {"input_image", "image"}
                    for item in output
                )
                if not has_image:
                    raise ValueError(f"{label} marked view returned no image")
                evidence["view_events"][pending_view["event_id"]] = pending_view["path"]
        evidence["review_claims"].update(parse_review_claims(trace_text(payload)))

    try:
        before = os.fstat(descriptor_fd)
        path_before = expanded.lstat()
        prefix_bytes = int(descriptor["prefix_bytes"])
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size < prefix_bytes
            or file_identity(before) != file_identity(path_before)
        ):
            raise ValueError(f"{label} must be one regular single-link file containing the prefix")
        remaining = prefix_bytes
        while remaining:
            chunk = os.read(descriptor_fd, min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError(f"{label} ended before the declared prefix")
            digest.update(chunk)
            remaining -= len(chunk)
            buffered += chunk
            while b"\n" in buffered:
                raw_line, buffered = buffered.split(b"\n", 1)
                if raw_line:
                    consume_line(raw_line)
        after = os.fstat(descriptor_fd)
        path_after = expanded.lstat()
        if buffered:
            raise ValueError(f"{label} prefix must end at a JSONL line boundary")
        if (
            file_identity(before) != file_identity(after)
            or file_identity(before) != file_identity(path_after)
        ):
            raise ValueError(f"{label} path identity changed while reading")
        if digest.hexdigest() != descriptor.get("prefix_sha256"):
            raise ValueError(f"{label} prefix sha256 mismatch")
        if pending_generation is not None:
            raise ValueError(f"{label} ends with an incomplete marked image generation")
        if pending_views:
            raise ValueError(f"{label} ends with incomplete marked visual views")
    except (OSError, ValueError) as exc:
        failures.append(str(exc))
    finally:
        os.close(descriptor_fd)
    return evidence, failures


def review_claim_sha256(payload: dict[str, Any]) -> str:
    claim = copy.deepcopy(payload)
    claim.pop("host_trace", None)
    return canonical_sha256(claim)


def validate_host_trace_bindings(
    payload: dict[str, Any],
    review_payload: Any,
    *,
    host_event_log: Path | None,
    review_host_event_log: Path | None,
) -> list[str]:
    failures: list[str] = []
    host_descriptor = payload.get("host_trace")
    if host_event_log is None:
        failures.append("an execution host event log is required for candidate execution evidence")
        execution_evidence: dict[str, Any] = {}
    elif not isinstance(host_descriptor, dict):
        failures.append("execution host trace descriptor is required")
        execution_evidence = {}
    else:
        execution_evidence, trace_failures = parse_host_trace_prefix(
            host_event_log,
            host_descriptor,
            label="execution host trace",
        )
        failures.extend(trace_failures)

    host_execution = payload.get("host_execution")
    if isinstance(host_descriptor, dict) and isinstance(host_execution, dict):
        if execution_evidence.get("thread_id") != host_descriptor.get("thread_id"):
            failures.append("execution host trace thread_id does not match session_meta")
        if host_execution.get("task_id") != host_descriptor.get("thread_id"):
            failures.append("host_execution.task_id is not bound to the execution trace")
        invocation_event_id = host_descriptor.get("invocation_event_id")
        if not isinstance(invocation_event_id, str):
            invocation_event_id = None
        invocation_requests = execution_evidence.get("execution_requests", {}).get(
            invocation_event_id, []
        )
        if invocation_requests != [execution_request_record(payload)]:
            failures.append(
                "explicit $dircreative invocation request is not present in the bound host trace"
            )
        event_id = host_descriptor.get("candidate_observation_event_id")
        if not isinstance(event_id, str):
            event_id = None
        observations = execution_evidence.get("candidate_observations", {}).get(event_id, [])
        if observations != [payload.get("candidate")]:
            failures.append("candidate Skill observation is not present in the bound host trace")

    source_paths: dict[str, str] = {}
    references = payload.get("reference_assets")
    if isinstance(references, list):
        for reference in references:
            if not isinstance(reference, dict):
                continue
            artifact = reference.get("artifact")
            reference_id = reference.get("reference_id")
            if isinstance(artifact, dict) and isinstance(reference_id, str) and isinstance(
                artifact.get("path"), str
            ):
                source_paths[f"reference:{reference_id}"] = artifact["path"]
    calls = payload.get("generation_calls")
    calls_list = calls if isinstance(calls, list) else []
    if calls_list:
        for index, call in enumerate(calls_list):
            if not isinstance(call, dict):
                continue
            label = f"generation_calls[{index}]"
            host_call_id = call.get("host_call_id")
            if call.get("host_call_id_status") != "available" or not isinstance(host_call_id, str):
                failures.append(f"{label} must expose an available host_call_id")
                continue
            event = execution_evidence.get("generation_events", {}).get(host_call_id)
            if not isinstance(event, dict):
                failures.append(f"{label} is missing from the bound host trace")
                continue
            request = event.get("request")
            inputs = call.get("reference_inputs")
            expected_paths = []
            if isinstance(inputs, list):
                for item in inputs:
                    source_id = item.get("source_id") if isinstance(item, dict) else None
                    expected_paths.append(source_paths.get(str(source_id)))
            if (
                not isinstance(request, dict)
                or set(request) != {"prompt", "referenced_image_paths"}
                or request.get("prompt") != call.get("prompt")
                or request.get("referenced_image_paths") != expected_paths
                or any(path is None for path in expected_paths)
            ):
                failures.append(f"{label} prompt/reference request does not match the host trace")
            output = call.get("output")
            if not isinstance(output, dict) or output.get("sha256") != event.get("output_sha256"):
                failures.append(f"{label} output sha256 does not match the host image bytes")
            if parse_datetime(call.get("started_at")) != parse_datetime(event.get("started_at")):
                failures.append(f"{label} start time does not match the host trace")
            if parse_datetime(call.get("completed_at")) != parse_datetime(event.get("completed_at")):
                failures.append(f"{label} completion time does not match the host trace")
            generation_id = call.get("generation_id")
            if isinstance(generation_id, str) and isinstance(output, dict) and isinstance(
                output.get("path"), str
            ):
                source_paths[f"generation:{generation_id}"] = output["path"]

    if not isinstance(review_payload, dict):
        failures.append("an independent visual review receipt is required")
        return failures
    review_descriptor = review_payload.get("host_trace")
    if review_host_event_log is None:
        failures.append("a separate review host event log is required")
        review_evidence: dict[str, Any] = {}
    elif not isinstance(review_descriptor, dict):
        failures.append("review host trace descriptor is required")
        review_evidence = {}
    else:
        review_evidence, trace_failures = parse_host_trace_prefix(
            review_host_event_log,
            review_descriptor,
            label="review host trace",
        )
        failures.extend(trace_failures)
    reviewer = review_payload.get("reviewer")
    if isinstance(review_descriptor, dict) and isinstance(reviewer, dict):
        if review_evidence.get("thread_id") != review_descriptor.get("thread_id"):
            failures.append("review host trace thread_id does not match session_meta")
        if reviewer.get("task_id") != review_descriptor.get("thread_id"):
            failures.append("reviewer.task_id is not bound to the review trace")
        if isinstance(host_descriptor, dict) and review_descriptor.get("thread_id") == host_descriptor.get(
            "thread_id"
        ):
            failures.append("visual review must use a separate host task")
        expected_claim = review_claim_sha256(review_payload)
        if review_descriptor.get("review_claim_sha256") != expected_claim:
            failures.append("review trace claim digest does not match the review receipt")
        if expected_claim not in review_evidence.get("review_claims", set()):
            failures.append("review judgment claim is not present in the bound review trace")

        review_request_event_id = review_descriptor.get("review_request_event_id")
        if not isinstance(review_request_event_id, str):
            review_request_event_id = None
        review_requests = review_evidence.get("review_requests", {}).get(
            review_request_event_id, []
        )
        if review_requests != [visual_review_request_record(payload, review_payload)]:
            failures.append(
                "independent review input request is not present in the bound review trace"
            )

        event_ids = review_descriptor.get("view_event_ids")
        views = review_evidence.get("view_events", {})
        valid_event_ids = isinstance(event_ids, list) and all(
            isinstance(event_id, str) for event_id in event_ids
        )
        if not valid_event_ids or len(event_ids) != len(set(event_ids)) or set(event_ids) != set(
            views
        ):
            failures.append("review view_event_ids do not exactly match completed visual views")
        expected_output_paths = [
            call.get("output", {}).get("path")
            for call in calls_list
            if isinstance(call, dict) and isinstance(call.get("output"), dict)
        ]
        observed_output_paths = (
            [views[event_id] for event_id in event_ids]
            if valid_event_ids and all(event_id in views for event_id in event_ids)
            else []
        )
        if (
            not all(isinstance(path, str) for path in expected_output_paths)
            or len(observed_output_paths) != len(expected_output_paths)
            or sorted(observed_output_paths)
            != sorted(path for path in expected_output_paths if isinstance(path, str))
        ):
            failures.append("review trace did not visibly open every generated output exactly once")
    return failures


@contextmanager
def sealed_c2patool(path: Path | None):
    if path is None:
        raise ValueError("an exact trusted c2patool binary is required for real tool provenance")
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise ValueError("c2patool must be one absolute executable regular single-link file")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if not nofollow:
        raise ValueError("c2patool snapshot requires O_NOFOLLOW")
    try:
        source_fd = os.open(expanded, os.O_RDONLY | nofollow | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise ValueError(f"c2patool cannot be opened safely: {exc}") from exc
    try:
        source_before = os.fstat(source_fd)
        path_before = expanded.lstat()
        if (
            not stat.S_ISREG(source_before.st_mode)
            or source_before.st_nlink != 1
            or source_before.st_size <= 0
            or source_before.st_size > MAX_C2PATOOL_BYTES
            or not source_before.st_mode & 0o111
            or file_identity(source_before) != file_identity(path_before)
        ):
            raise ValueError("c2patool must be one bounded executable regular single-link file")
        chunks: list[bytes] = []
        remaining = source_before.st_size
        while remaining:
            chunk = os.read(source_fd, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        source_after = os.fstat(source_fd)
        path_after = expanded.lstat()
    finally:
        os.close(source_fd)
    binary = b"".join(chunks)
    if (
        len(binary) != source_before.st_size
        or file_identity(source_before) != file_identity(source_after)
        or file_identity(source_before) != file_identity(path_after)
    ):
        raise ValueError("c2patool changed while being sealed")
    digest = sha256_bytes(binary)
    if digest not in C2PATOOL_ALLOWED_SHA256:
        raise ValueError(f"c2patool binary is not an allowed exact verifier: {digest}")
    with tempfile.TemporaryDirectory(prefix="dircreative-c2patool-snapshot-") as raw:
        snapshot_root = Path(raw)
        snapshot_root.chmod(0o700)
        snapshot = snapshot_root / "c2patool"
        snapshot_fd = os.open(
            snapshot,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | nofollow | getattr(os, "O_CLOEXEC", 0),
            0o700,
        )
        try:
            view = memoryview(binary)
            while view:
                written = os.write(snapshot_fd, view)
                if written <= 0:
                    raise OSError("c2patool snapshot write made no progress")
                view = view[written:]
            os.fchmod(snapshot_fd, 0o700)
            os.fsync(snapshot_fd)
        finally:
            os.close(snapshot_fd)
        proc = subprocess.run(
            [str(snapshot), "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0 or proc.stdout.strip() != "c2patool 0.27.0":
            raise ValueError("c2patool version identity mismatch")
        if sha256(snapshot) != digest:
            raise ValueError("c2patool snapshot changed before use")
        yield snapshot
        snapshot_stat = snapshot.lstat()
        if (
            not stat.S_ISREG(snapshot_stat.st_mode)
            or snapshot_stat.st_nlink != 1
            or stat.S_IMODE(snapshot_stat.st_mode) != 0o700
            or sha256(snapshot) != digest
        ):
            raise ValueError("c2patool snapshot changed during audit")


def validate_c2patool(path: Path | None) -> list[str]:
    try:
        with sealed_c2patool(path):
            pass
    except (OSError, ValueError) as exc:
        return [str(exc)]
    return []


def verify_openai_c2pa(
    artifact: dict[str, Any],
    label: str,
    *,
    c2patool: Path,
    candidate_time: datetime,
) -> list[str]:
    raw_path = artifact.get("path")
    if not isinstance(raw_path, str):
        return [f"{label}: cannot verify C2PA without an artifact path"]
    path = Path(raw_path).expanduser()
    report = subprocess.run(
        [str(c2patool), str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if report.returncode != 0:
        return [f"{label}: c2patool manifest validation failed"]
    try:
        payload = json.loads(report.stdout)
        active = payload["active_manifest"]
        manifest = payload["manifests"][active]
        active_results = payload["validation_results"]["activeManifest"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [f"{label}: c2patool returned an invalid manifest report"]
    failures: list[str] = []
    if payload.get("validation_state") != "Valid":
        failures.append(f"{label}: C2PA validation state is not Valid")
    unexpected_status = {
        item.get("code")
        for item in payload.get("validation_status", [])
        if isinstance(item, dict)
    } - {"signingCredential.untrusted"}
    if unexpected_status:
        failures.append(f"{label}: unexpected C2PA validation status {sorted(unexpected_status)}")
    success_codes = {
        item.get("code")
        for item in active_results.get("success", [])
        if isinstance(item, dict)
    }
    if not REQUIRED_C2PA_SUCCESS_CODES.issubset(success_codes):
        failures.append(f"{label}: C2PA signature or bound data hash was not validated")
    failure_codes = {
        item.get("code")
        for item in active_results.get("failure", [])
        if isinstance(item, dict)
    } - {"signingCredential.untrusted"}
    if failure_codes:
        failures.append(f"{label}: C2PA reported failures {sorted(failure_codes)}")

    signature = manifest.get("signature_info")
    if not isinstance(signature, dict) or (
        signature.get("issuer") != "OpenAI OpCo, LLC"
        or signature.get("common_name") != "OpenAI Media Service"
        or signature.get("alg") not in {"Es256", "Ps256"}
    ):
        failures.append(f"{label}: C2PA signer is not the expected OpenAI Media Service")
        signature = {}
    signature_time = parse_datetime(signature.get("time"))
    now = datetime.now(timezone.utc)
    if signature_time is None or signature_time < candidate_time or signature_time > now:
        failures.append(f"{label}: signed generation time is not candidate-bound")

    generators = manifest.get("claim_generator_info")
    if not isinstance(generators, list) or not any(
        isinstance(item, dict) and item.get("name") == "OpenAI Media Service API"
        for item in generators
    ):
        failures.append(f"{label}: OpenAI claim generator identity is missing")
    actions = [
        action
        for assertion in manifest.get("assertions", [])
        if isinstance(assertion, dict) and assertion.get("label") == "c2pa.actions.v2"
        for action in assertion.get("data", {}).get("actions", [])
        if isinstance(action, dict)
    ]
    if not any(
        action.get("action") == "c2pa.created"
        and action.get("digitalSourceType")
        == "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
        and isinstance(action.get("softwareAgent"), dict)
        and action["softwareAgent"].get("name") == "gpt-image"
        and action["softwareAgent"].get("version") == "2.0"
        for action in actions
    ):
        failures.append(f"{label}: gpt-image 2.0 creation assertion is missing")

    certs = subprocess.run(
        [str(c2patool), str(path), "--certs"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    pem_blocks = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        certs.stdout,
        re.DOTALL,
    )
    try:
        cert_hashes = {
            hashlib.sha256(ssl.PEM_cert_to_DER_cert(block)).hexdigest()
            for block in pem_blocks[1:]
        }
    except ValueError:
        cert_hashes = set()
    if certs.returncode != 0 or not (cert_hashes & OPENAI_SIGNING_CA_SHA256):
        failures.append(f"{label}: OpenAI signing CA is not pinned")
    return failures


def png_scanline_layout(
    width: int,
    height: int,
    bits_per_pixel: int,
    interlace: int,
) -> list[tuple[int, int]]:
    if interlace == 0:
        return [(height, (width * bits_per_pixel + 7) // 8)]
    passes = (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    )
    layout: list[tuple[int, int]] = []
    for x_start, y_start, x_step, y_step in passes:
        pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
        pass_height = 0 if height <= y_start else (height - y_start + y_step - 1) // y_step
        if pass_width and pass_height:
            layout.append((pass_height, (pass_width * bits_per_pixel + 7) // 8))
    return layout


def decode_png_idat(idat_chunks: list[bytes], layout: list[tuple[int, int]]) -> bytes:
    expected_size = sum(rows * (row_bytes + 1) for rows, row_bytes in layout)
    if expected_size <= 0 or expected_size > MAX_DECODED_PNG_BYTES:
        raise ValueError("decoded PNG size is outside the audit limit")
    decoder = zlib.decompressobj()
    decoded = bytearray()
    try:
        for compressed in idat_chunks:
            pending = compressed
            while pending:
                room = expected_size + 1 - len(decoded)
                if room <= 0:
                    raise ValueError("PNG decompression exceeds declared dimensions")
                decoded.extend(decoder.decompress(pending, room))
                pending = decoder.unconsumed_tail
        room = expected_size + 1 - len(decoded)
        if room <= 0:
            raise ValueError("PNG decompression exceeds declared dimensions")
        decoded.extend(decoder.flush(room))
    except zlib.error as exc:
        raise ValueError(f"PNG IDAT cannot be decoded: {exc}") from exc
    if (
        not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
        or len(decoded) != expected_size
    ):
        raise ValueError("PNG IDAT does not decode to the declared image")
    offset = 0
    for rows, row_bytes in layout:
        for _ in range(rows):
            if decoded[offset] > 4:
                raise ValueError("PNG contains an invalid scanline filter")
            offset += row_bytes + 1
    if offset != len(decoded):
        raise ValueError("PNG scanline layout mismatch")
    return bytes(decoded)


def png_dimensions(path: Path) -> tuple[int, int]:
    metadata = path.stat()
    if metadata.st_size <= 0 or metadata.st_size > MAX_PNG_FILE_BYTES:
        raise ValueError(f"PNG size is outside the audit limit: {path}")
    width = height = bit_depth = color_type = interlace = 0
    saw_ihdr = saw_idat = saw_iend = saw_plte = False
    idat_closed = False
    idat_chunks: list[bytes] = []
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"not a PNG: {path}")
        chunk_index = 0
        while not saw_iend:
            header = handle.read(8)
            if len(header) != 8:
                raise ValueError(f"truncated PNG chunk header: {path}")
            length, chunk_type = struct.unpack(">I4s", header)
            if length > MAX_PNG_FILE_BYTES or not all(
                65 <= value <= 90 or 97 <= value <= 122 for value in chunk_type
            ):
                raise ValueError(f"invalid PNG chunk: {path}")
            data = handle.read(length)
            crc_raw = handle.read(4)
            if len(data) != length or len(crc_raw) != 4:
                raise ValueError(f"truncated PNG chunk: {path}")
            expected_crc = struct.unpack(">I", crc_raw)[0]
            actual_crc = zlib.crc32(data, zlib.crc32(chunk_type)) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                raise ValueError(f"PNG CRC mismatch in {chunk_type.decode('ascii')}: {path}")
            if chunk_index == 0 and chunk_type != b"IHDR":
                raise ValueError(f"PNG IHDR must be first: {path}")
            if chunk_type == b"IHDR":
                if saw_ihdr or length != 13:
                    raise ValueError(f"invalid PNG IHDR: {path}")
                width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                    ">IIBBBBB", data
                )
                if (
                    width <= 0
                    or height <= 0
                    or width * height > MAX_PNG_PIXELS
                    or color_type not in PNG_BIT_DEPTHS
                    or bit_depth not in PNG_BIT_DEPTHS[color_type]
                    or compression != 0
                    or filtering != 0
                    or interlace not in {0, 1}
                ):
                    raise ValueError(f"invalid PNG IHDR values: {path}")
                saw_ihdr = True
            elif not saw_ihdr:
                raise ValueError(f"PNG data precedes IHDR: {path}")
            elif chunk_type == b"PLTE":
                if saw_plte or saw_idat or length == 0 or length % 3 or length > 768:
                    raise ValueError(f"invalid PNG palette: {path}")
                if color_type in {0, 4} or (color_type == 3 and length // 3 > 2**bit_depth):
                    raise ValueError(f"PNG palette conflicts with IHDR: {path}")
                saw_plte = True
            elif chunk_type == b"IDAT":
                if idat_closed or (color_type == 3 and not saw_plte):
                    raise ValueError(f"invalid PNG IDAT order: {path}")
                saw_idat = True
                idat_chunks.append(data)
            elif chunk_type == b"IEND":
                if length != 0 or not saw_idat:
                    raise ValueError(f"invalid PNG IEND: {path}")
                saw_iend = True
            else:
                if saw_idat:
                    idat_closed = True
                if chunk_type[0] & 0x20 == 0:
                    raise ValueError(f"unknown critical PNG chunk {chunk_type!r}: {path}")
            chunk_index += 1
        if handle.read(1):
            raise ValueError(f"PNG has trailing data after IEND: {path}")
    if color_type == 3 and not saw_plte:
        raise ValueError(f"indexed PNG has no palette: {path}")
    bits_per_pixel = PNG_CHANNELS[color_type] * bit_depth
    layout = png_scanline_layout(width, height, bits_per_pixel, interlace)
    decode_png_idat(idat_chunks, layout)
    return width, height


def regular_single_link(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1 and not path.is_symlink()


def validate_artifact(
    item: Any,
    label: str,
    *,
    extra_fields: frozenset[str] = frozenset(),
) -> list[str]:
    failures: list[str] = []
    required_fields = {"path", "sha256", "width", "height"} | set(extra_fields)
    if not isinstance(item, dict) or set(item) != required_fields:
        return [f"{label}: artifact must contain path, sha256, width, height"]
    raw_path = item.get("path")
    digest = item.get("sha256")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return [f"{label}: path is required"]
    path = Path(raw_path).expanduser()
    if not path.is_absolute() or not regular_single_link(path):
        return [f"{label}: artifact must be one absolute regular single-link file"]
    if path.stat().st_size <= 0 or path.stat().st_size > MAX_PNG_FILE_BYTES:
        return [f"{label}: artifact size is outside the audit limit"]
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest) or sha256(path) != digest:
        failures.append(f"{label}: sha256 mismatch")
    try:
        width, height = png_dimensions(path)
    except ValueError as exc:
        failures.append(f"{label}: {exc}")
    else:
        if item.get("width") != width or item.get("height") != height:
            failures.append(f"{label}: dimensions mismatch")
    return failures


def validate_distinct_artifact_claims(claims: list[tuple[str, dict[str, Any]]]) -> list[str]:
    failures: list[str] = []
    paths: dict[str, str] = {}
    physical: dict[tuple[int, int], str] = {}
    digests: dict[str, str] = {}
    for label, item in claims:
        raw_path = item.get("path") if isinstance(item, dict) else None
        digest = item.get("sha256") if isinstance(item, dict) else None
        if not isinstance(raw_path, str) or not isinstance(digest, str):
            continue
        path = Path(raw_path).expanduser()
        try:
            metadata = path.stat()
            resolved = str(path.resolve()).casefold()
        except OSError:
            continue
        for identity, seen, kind in (
            (resolved, paths, "path"),
            ((metadata.st_dev, metadata.st_ino), physical, "physical file"),
            (digest, digests, "sha256"),
        ):
            previous = seen.get(identity)
            if previous is not None:
                failures.append(f"{label}: reuses {kind} already claimed by {previous}")
            else:
                seen[identity] = label
    return failures


def file_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_nlink,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def seal_artifact_snapshot(
    item: dict[str, Any],
    label: str,
    destination: Path,
    *,
    after_copy_hook: Callable[[], None] | None = None,
) -> tuple[dict[str, Any] | None, tuple[str, tuple[int, int], str] | None, list[str]]:
    raw_path = item.get("path")
    declared_digest = item.get("sha256")
    if not isinstance(raw_path, str) or not raw_path.strip() or not isinstance(declared_digest, str):
        return None, None, [f"{label}: cannot seal an artifact without path and sha256"]
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        return None, None, [f"{label}: artifact path must be absolute"]
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_fd = os.open(path, flags)
    except OSError as exc:
        return None, None, [f"{label}: cannot open artifact safely: {exc}"]
    destination_fd: int | None = None
    try:
        before = os.fstat(source_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > MAX_PNG_FILE_BYTES
        ):
            return None, None, [f"{label}: source must be one bounded regular single-link file"]
        destination_fd = os.open(
            destination,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        digest = hashlib.sha256()
        with (
            os.fdopen(source_fd, "rb", closefd=True) as source,
            os.fdopen(destination_fd, "wb", closefd=True) as target,
        ):
            source_fd = -1
            destination_fd = None
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
            if after_copy_hook is not None:
                after_copy_hook()
            after = os.fstat(source.fileno())
        try:
            path_after = path.lstat()
        except OSError as exc:
            return None, None, [f"{label}: source path changed while sealing: {exc}"]
        if file_identity(before) != file_identity(after) or file_identity(before) != file_identity(path_after):
            return None, None, [f"{label}: source changed while sealing the evidence snapshot"]
        actual_digest = digest.hexdigest()
        if actual_digest != declared_digest:
            return None, None, [f"{label}: sha256 mismatch while sealing evidence"]
        sealed = copy.deepcopy(item)
        sealed["path"] = str(destination)
        identity = (
            str(path.resolve(strict=False)).casefold(),
            (before.st_dev, before.st_ino),
            actual_digest,
        )
        return sealed, identity, []
    except OSError as exc:
        return None, None, [f"{label}: failed to seal artifact: {exc}"]
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)


def seal_receipt_artifacts(
    payload: dict[str, Any],
    snapshot_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    sealed_payload = copy.deepcopy(payload)
    claims: list[tuple[str, dict[str, Any], Callable[[dict[str, Any]], None]]] = []
    if sealed_payload.get("schema_version") == "2.0.0":
        references = sealed_payload.get("reference_assets")
        if isinstance(references, list):
            for index, item in enumerate(references):
                if isinstance(item, dict) and isinstance(item.get("artifact"), dict):
                    claims.append(
                        (
                            f"reference_assets[{index}].artifact",
                            item["artifact"],
                            lambda value, target=item: target.__setitem__("artifact", value),
                        )
                    )
        calls = sealed_payload.get("generation_calls")
        if isinstance(calls, list):
            for index, item in enumerate(calls):
                if isinstance(item, dict) and isinstance(item.get("output"), dict):
                    claims.append(
                        (
                            f"generation_calls[{index}].output",
                            item["output"],
                            lambda value, target=item: target.__setitem__("output", value),
                        )
                    )
    else:
        references = sealed_payload.get("references")
        if isinstance(references, list):
            for index, item in enumerate(references):
                if isinstance(item, dict):
                    claims.append(
                        (
                            f"references[{index}]",
                            item,
                            lambda value, i=index: references.__setitem__(i, value),
                        )
                    )
        attempts = sealed_payload.get("attempts")
        if isinstance(attempts, list):
            for index, attempt in enumerate(attempts):
                if isinstance(attempt, dict) and isinstance(attempt.get("artifact"), dict):
                    claims.append(
                        (
                            f"attempts[{index}].artifact",
                            attempt["artifact"],
                            lambda value, target=attempt: target.__setitem__("artifact", value),
                        )
                    )
        shots = sealed_payload.get("multi_shot_evidence")
        if isinstance(shots, list):
            for index, shot in enumerate(shots):
                if isinstance(shot, dict) and isinstance(shot.get("artifact"), dict):
                    claims.append(
                        (
                            f"multi_shot_evidence[{index}].artifact",
                            shot["artifact"],
                            lambda value, target=shot: target.__setitem__("artifact", value),
                        )
                    )

    failures: list[str] = []
    paths: dict[str, str] = {}
    physical: dict[tuple[int, int], str] = {}
    digests: dict[str, str] = {}
    for index, (label, item, replace) in enumerate(claims):
        destination = snapshot_root / f"artifact-{index:03d}.png"
        sealed, identity, item_failures = seal_artifact_snapshot(item, label, destination)
        failures.extend(item_failures)
        if sealed is None or identity is None:
            continue
        replace(sealed)
        for value, seen, kind in (
            (identity[0], paths, "path"),
            (identity[1], physical, "physical file"),
            (identity[2], digests, "sha256"),
        ):
            previous = seen.get(value)
            if previous is not None:
                failures.append(f"{label}: reuses {kind} already claimed by {previous}")
            else:
                seen[value] = label
    return sealed_payload, failures


def validate_receipt(
    payload: Any,
    expected_commit: str | None = None,
    *,
    c2patool: Path | None = None,
    review_payload: Any | None = None,
    execution_receipt_sha256: str | None = None,
    require_candidate_skill_execution: bool = False,
    validate_c2pa: bool = True,
    host_event_log: Path | None = None,
    review_host_event_log: Path | None = None,
    head_reader: Callable[[], str] = current_head,
    blob_reader: Callable[[str, str], bytes] = git_bytes,
    commit_time_reader: Callable[[str], str] = commit_time,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["receipt must contain one object"]
    trace_failures = (
        validate_host_trace_bindings(
            payload,
            review_payload,
            host_event_log=host_event_log,
            review_host_event_log=review_host_event_log,
        )
        if payload.get("schema_version") == "2.0.0"
        else []
    )
    with tempfile.TemporaryDirectory(prefix="dircreative-media-evidence-snapshot-") as raw:
        sealed_payload, sealing_failures = seal_receipt_artifacts(payload, Path(raw))
        if sealing_failures:
            return sealing_failures

        def validate_with_tool(trusted_tool: Path | None) -> list[str]:
            if sealed_payload.get("schema_version") == "2.0.0":
                return trace_failures + validate_sealed_v2_receipt(
                    sealed_payload,
                    expected_commit,
                    c2patool=trusted_tool,
                    review_payload=review_payload,
                    execution_receipt_sha256=execution_receipt_sha256,
                    validate_c2pa=validate_c2pa,
                    head_reader=head_reader,
                    blob_reader=blob_reader,
                    commit_time_reader=commit_time_reader,
                )
            failures = validate_sealed_legacy_receipt(
                sealed_payload,
                expected_commit,
                c2patool=trusted_tool,
            )
            if require_candidate_skill_execution:
                failures.append(
                    "legacy media receipt proves provenance only; schema 2.0.0 and an independent review are required"
                )
            return trace_failures + failures

        if not validate_c2pa:
            return validate_with_tool(None)
        try:
            with sealed_c2patool(c2patool) as trusted_tool:
                return validate_with_tool(trusted_tool)
        except (OSError, ValueError) as exc:
            return trace_failures + [f"c2patool sealing failed: {exc}"]


def validate_time_window(
    started_raw: Any,
    completed_raw: Any,
    label: str,
    *,
    earliest: datetime | None = None,
    latest: datetime | None = None,
) -> tuple[datetime | None, datetime | None, list[str]]:
    started = parse_datetime(started_raw)
    completed = parse_datetime(completed_raw)
    failures: list[str] = []
    if started is None or completed is None or started > completed:
        failures.append(f"{label}: invalid UTC start/completion window")
        return started, completed, failures
    if earliest is not None and started < earliest:
        failures.append(f"{label}: starts before the candidate evidence window")
    if latest is not None and completed > latest:
        failures.append(f"{label}: completes after the allowed evidence window")
    return started, completed, failures


def validate_available_identifier(value: Any, status_value: Any, label: str) -> list[str]:
    if status_value not in {"available", "unavailable"}:
        return [f"{label}_status must be available or unavailable"]
    if status_value == "available":
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            return [f"{label} must be a bounded non-empty string when available"]
    elif value is not None:
        return [f"{label} must be null when the host reports it unavailable"]
    return []


def c2pa_signature_time(path: Path, c2patool: Path) -> datetime | None:
    proc = subprocess.run(
        [str(c2patool), str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
        active = payload["active_manifest"]
        return parse_datetime(payload["manifests"][active]["signature_info"]["time"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def validate_independent_review(
    payload: Any,
    *,
    execution_receipt_sha256: str | None,
    candidate_commit: str,
    host_execution: dict[str, Any],
    attempts: list[dict[str, Any]],
    shots: list[dict[str, Any]],
    output_digests: dict[str, str],
    continuity_lock_sha256: str,
    now: datetime,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["an independent visual review receipt is required"]
    failures: list[str] = []
    if set(payload) != REVIEW_FIELDS:
        failures.append("review receipt field set mismatch")
    if payload.get("schema_version") != "1.0.0" or payload.get("product") != "DIRcreative":
        failures.append("review receipt identity mismatch")
    if payload.get("candidate_commit") != candidate_commit:
        failures.append("review receipt candidate_commit mismatch")
    declared_execution_digest = payload.get("execution_receipt_sha256")
    if (
        not isinstance(execution_receipt_sha256, str)
        or not SHA256_RE.fullmatch(execution_receipt_sha256)
        or declared_execution_digest != execution_receipt_sha256
    ):
        failures.append("review receipt is not bound to the exact execution receipt bytes")

    reviewer = payload.get("reviewer")
    review_started: datetime | None = None
    review_completed: datetime | None = None
    if not isinstance(reviewer, dict) or set(reviewer) != REVIEWER_FIELDS:
        failures.append("reviewer record has invalid shape")
    else:
        actor_id = reviewer.get("actor_id")
        task_id = reviewer.get("task_id")
        if not isinstance(actor_id, str) or not actor_id.strip():
            failures.append("reviewer actor_id is required")
        if not isinstance(task_id, str) or not task_id.strip():
            failures.append("reviewer task_id is required")
        if actor_id == host_execution.get("actor_id") or task_id == host_execution.get("task_id"):
            failures.append("visual reviewer must use a different actor_id and task_id from the executor")
        if reviewer.get("review_method") != "independent_visual_review":
            failures.append("review_method must be independent_visual_review")
        if reviewer.get("input_scope") != "raw_references_outputs_and_rubric_only":
            failures.append("review input scope must exclude the executor's QA conclusions")
        host_completed = parse_datetime(host_execution.get("completed_at"))
        review_started, review_completed, time_failures = validate_time_window(
            reviewer.get("started_at"),
            reviewer.get("completed_at"),
            "reviewer",
            earliest=host_completed,
            latest=now,
        )
        failures.extend(time_failures)

    rubric = payload.get("rubric")
    if (
        not isinstance(rubric, str)
        or len(rubric.strip()) < 20
        or payload.get("rubric_sha256") != sha256_bytes(rubric.encode("utf-8"))
    ):
        failures.append("review rubric text and sha256 must be exactly bound")

    expected_decisions: dict[str, str] = {}
    expected_digests: dict[str, str] = {}
    for index, attempt in enumerate(attempts):
        attempt_id = attempt.get("attempt_id")
        generation_id = attempt.get("generation_id")
        if isinstance(attempt_id, str) and isinstance(generation_id, str):
            expected_decisions[attempt_id] = "accept" if index == len(attempts) - 1 else "reject"
            digest = output_digests.get(generation_id)
            if digest:
                expected_digests[attempt_id] = digest
    for shot in shots:
        shot_id = shot.get("shot_id")
        generation_id = shot.get("generation_id")
        if isinstance(shot_id, str) and isinstance(generation_id, str):
            expected_decisions[shot_id] = "pass"
            digest = output_digests.get(generation_id)
            if digest:
                expected_digests[shot_id] = digest

    reviews = payload.get("artifact_reviews")
    seen_subjects: set[str] = set()
    if not isinstance(reviews, list) or len(reviews) != len(expected_decisions):
        failures.append("artifact_reviews must cover every attempt and shot exactly once")
    else:
        for index, item in enumerate(reviews):
            if not isinstance(item, dict) or set(item) != ARTIFACT_REVIEW_FIELDS:
                failures.append(f"artifact_reviews[{index}] has invalid shape")
                continue
            subject_id = item.get("subject_id")
            if not isinstance(subject_id, str) or subject_id not in expected_decisions:
                failures.append(f"artifact_reviews[{index}] has an unknown subject_id")
                continue
            if subject_id in seen_subjects:
                failures.append(f"artifact_reviews[{index}] duplicates {subject_id}")
                continue
            seen_subjects.add(subject_id)
            if item.get("artifact_sha256") != expected_digests.get(subject_id):
                failures.append(f"artifact_reviews[{index}] is not bound to {subject_id}'s output")
            if item.get("decision") != expected_decisions[subject_id]:
                failures.append(f"artifact_reviews[{index}] has the wrong independent disposition")
            observations = item.get("observations")
            if not isinstance(observations, list) or not observations or not all(
                isinstance(value, str) and len(value.strip()) >= 12 for value in observations
            ):
                failures.append(f"artifact_reviews[{index}] requires concrete visible observations")
        if seen_subjects != set(expected_decisions):
            failures.append("artifact_reviews coverage mismatch")

    continuity_review = payload.get("continuity_review")
    expected_shot_ids = [item.get("shot_id") for item in shots]
    if not isinstance(continuity_review, dict) or set(continuity_review) != CONTINUITY_REVIEW_FIELDS:
        failures.append("continuity_review has invalid shape")
    else:
        if continuity_review.get("shot_ids") != expected_shot_ids:
            failures.append("continuity_review must cover the exact shot sequence")
        if continuity_review.get("decision") != "pass":
            failures.append("independent reviewer did not pass multi-shot continuity")
        if continuity_review.get("continuity_lock_sha256") != continuity_lock_sha256:
            failures.append("continuity_review is not bound to the execution continuity lock")
        observations = continuity_review.get("observations")
        if not isinstance(observations, list) or not observations or not all(
            isinstance(value, str) and len(value.strip()) >= 12 for value in observations
        ):
            failures.append("continuity_review requires concrete cross-shot observations")

    limitations = payload.get("limitations")
    limitation_text = (
        " ".join(item for item in limitations if isinstance(item, str)).casefold()
        if isinstance(limitations, list)
        else ""
    )
    if (
        not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(item, str) and item.strip() for item in limitations)
        or "reviewer" not in limitation_text
        or "judgment" not in limitation_text
    ):
        failures.append("review limitations must label continuity quality as reviewer judgment")
    if review_started is None or review_completed is None:
        failures.append("independent review time is unavailable")
    return failures


def validate_sealed_v2_receipt(
    payload: Any,
    expected_commit: str | None = None,
    *,
    c2patool: Path | None = None,
    review_payload: Any | None = None,
    execution_receipt_sha256: str | None = None,
    validate_c2pa: bool = True,
    head_reader: Callable[[], str] = current_head,
    blob_reader: Callable[[str, str], bytes] = git_bytes,
    commit_time_reader: Callable[[str], str] = commit_time,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["receipt must contain one object"]
    failures: list[str] = []
    now = datetime.now(timezone.utc)
    if set(payload) != V2_RECEIPT_FIELDS:
        failures.append("schema 2 execution receipt field set mismatch")
    if (
        payload.get("schema_version") != "2.0.0"
        or payload.get("product") != "DIRcreative"
        or payload.get("media_type") != "image"
    ):
        failures.append("schema 2 execution receipt identity mismatch")
    if payload.get("video_verified") is not False:
        failures.append("image forward evidence must not claim video verification")

    candidate_record = payload.get("candidate")
    candidate_commit = ""
    candidate_time: datetime | None = None
    if not isinstance(candidate_record, dict) or set(candidate_record) != V2_CANDIDATE_FIELDS:
        failures.append("candidate record has invalid shape")
    else:
        commit = candidate_record.get("commit")
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            failures.append("candidate commit must be one full lowercase SHA")
        else:
            candidate_commit = commit
            if expected_commit and commit != expected_commit:
                failures.append("candidate commit does not match --expected-commit")
            try:
                if head_reader() != commit:
                    failures.append("candidate commit does not match current HEAD")
                candidate_time = parse_datetime(commit_time_reader(commit))
            except ValueError as exc:
                failures.append(f"git identity check failed: {exc}")
        observed = candidate_record.get("observed_skill_paths")
        observed_names: set[str] = set()
        if not isinstance(observed, list) or len(observed) != len(REQUIRED_CANDIDATE_SKILL_PATHS):
            failures.append("candidate observed_skill_paths must bind the exact lightweight Delivery surface")
        else:
            for index, item in enumerate(observed):
                if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                    failures.append(f"observed_skill_paths[{index}] has invalid shape")
                    continue
                relative = item.get("path")
                digest = item.get("sha256")
                if (
                    not isinstance(relative, str)
                    or relative not in REQUIRED_CANDIDATE_SKILL_PATHS
                    or relative in observed_names
                ):
                    failures.append(f"observed_skill_paths[{index}] is unknown or duplicated")
                    continue
                observed_names.add(relative)
                if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                    failures.append(f"observed_skill_paths[{index}] has an invalid sha256")
                    continue
                if candidate_commit:
                    try:
                        expected_digest = sha256_bytes(blob_reader(candidate_commit, relative))
                    except ValueError as exc:
                        failures.append(f"observed_skill_paths[{index}] cannot be read: {exc}")
                    else:
                        if digest != expected_digest:
                            failures.append(f"observed_skill_paths[{index}] does not match candidate bytes")
                        current_path = ROOT / relative
                        if validate_c2pa and (
                            not regular_single_link(current_path) or sha256(current_path) != digest
                        ):
                            failures.append(
                                f"observed_skill_paths[{index}] does not match the currently loaded source bytes"
                            )
            if observed_names != REQUIRED_CANDIDATE_SKILL_PATHS:
                failures.append("candidate observed_skill_paths coverage mismatch")
    if candidate_time is None:
        failures.append("candidate commit time is unavailable")

    host = payload.get("host_execution")
    host_started: datetime | None = None
    host_completed: datetime | None = None
    if not isinstance(host, dict) or set(host) != V2_HOST_FIELDS:
        failures.append("host_execution has invalid shape")
        host = {}
    else:
        for field in ("actor_id", "task_id"):
            value = host.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                failures.append(f"host_execution.{field} must be one bounded identifier")
        invocation = host.get("explicit_invocation")
        if (
            not isinstance(invocation, str)
            or "$dircreative" not in invocation
            or host.get("explicit_invocation_sha256") != sha256_bytes(invocation.encode("utf-8"))
        ):
            failures.append("host execution must bind one explicit $dircreative request")
        if (
            host.get("evidence_level") != "unsigned_host_trace"
            or host.get("cryptographically_signed") is not False
        ):
            failures.append("host execution must be honestly labeled unsigned_host_trace")
        host_started, host_completed, time_failures = validate_time_window(
            host.get("started_at"),
            host.get("completed_at"),
            "host_execution",
            earliest=candidate_time,
            latest=now,
        )
        failures.extend(time_failures)

    artifact_claims: list[tuple[str, dict[str, Any]]] = []
    source_digests: dict[str, str] = {}
    reference_ids: set[str] = set()
    reference_roles: set[str] = set()
    references = payload.get("reference_assets")
    if not isinstance(references, list) or len(references) < 2:
        failures.append("reference_assets must contain at least two distinct bound references")
    else:
        for index, item in enumerate(references):
            label = f"reference_assets[{index}]"
            if not isinstance(item, dict) or set(item) != V2_REFERENCE_FIELDS:
                failures.append(f"{label} has invalid shape")
                continue
            reference_id = item.get("reference_id")
            role = item.get("role")
            if (
                not isinstance(reference_id, str)
                or not REFERENCE_ROLE_RE.fullmatch(reference_id)
                or reference_id in reference_ids
            ):
                failures.append(f"{label}.reference_id must be unique snake_case")
            else:
                reference_ids.add(reference_id)
            if not isinstance(role, str) or not REFERENCE_ROLE_RE.fullmatch(role) or role in reference_roles:
                failures.append(f"{label}.role must be unique snake_case")
            else:
                reference_roles.add(role)
            artifact = item.get("artifact")
            failures.extend(validate_artifact(artifact, f"{label}.artifact"))
            if isinstance(artifact, dict):
                artifact_claims.append((f"{label}.artifact", artifact))
                digest = artifact.get("sha256")
                if isinstance(reference_id, str) and isinstance(digest, str):
                    source_digests[f"reference:{reference_id}"] = digest

    continuity_lock = payload.get("continuity_lock")
    continuity_lock_sha256 = canonical_sha256(continuity_lock)
    if not isinstance(continuity_lock, dict) or set(continuity_lock) != {
        "identity_reference_ids",
        "locked_attributes",
    }:
        failures.append("continuity_lock has invalid shape")
    else:
        identity_ids = continuity_lock.get("identity_reference_ids")
        attributes = continuity_lock.get("locked_attributes")
        if (
            not isinstance(identity_ids, list)
            or len(identity_ids) < 2
            or not all(isinstance(value, str) and value in reference_ids for value in identity_ids)
            or len(identity_ids) != len(set(identity_ids))
        ):
            failures.append("continuity_lock must name at least two unique bound references")
        if not isinstance(attributes, list) or not attributes or not all(
            isinstance(value, str) and value.strip() for value in attributes
        ):
            failures.append("continuity_lock must state observable locked attributes")

    calls = payload.get("generation_calls")
    call_by_id: dict[str, dict[str, Any]] = {}
    output_digests: dict[str, str] = {}
    call_windows: dict[str, tuple[datetime | None, datetime | None]] = {}
    available_host_ids: set[str] = set()
    available_provider_ids: set[str] = set()
    generated_claims: list[tuple[str, dict[str, Any], str]] = []
    if not isinstance(calls, list) or len(calls) < 5:
        failures.append("generation_calls must contain at least two attempts and three shots")
        calls = []
    for index, item in enumerate(calls):
        label = f"generation_calls[{index}]"
        if not isinstance(item, dict) or set(item) != V2_CALL_FIELDS:
            failures.append(f"{label} has invalid shape")
            continue
        generation_id = item.get("generation_id")
        if (
            not isinstance(generation_id, str)
            or not REFERENCE_ROLE_RE.fullmatch(generation_id)
            or generation_id in call_by_id
        ):
            failures.append(f"{label}.generation_id must be unique snake_case")
            continue
        call_by_id[generation_id] = item
        failures.extend(
            validate_available_identifier(
                item.get("host_call_id"), item.get("host_call_id_status"), f"{label}.host_call_id"
            )
        )
        failures.extend(
            validate_available_identifier(
                item.get("provider_response_id"),
                item.get("provider_response_id_status"),
                f"{label}.provider_response_id",
            )
        )
        if item.get("host_call_id_status") == "available":
            host_id = str(item.get("host_call_id"))
            if host_id in available_host_ids:
                failures.append(f"{label}.host_call_id is duplicated")
            available_host_ids.add(host_id)
        if item.get("provider_response_id_status") == "available":
            provider_id = str(item.get("provider_response_id"))
            if provider_id in available_provider_ids:
                failures.append(f"{label}.provider_response_id is duplicated")
            available_provider_ids.add(provider_id)
        if (
            item.get("tool") != "image_gen.imagegen"
            or item.get("provider") != "OpenAI Media Service"
            or item.get("model") != "gpt-image 2.0"
        ):
            failures.append(f"{label} has an unsupported observed tool/provider/model identity")
        prompt = item.get("prompt")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt.encode("utf-8")) > 200_000
            or item.get("prompt_sha256") != sha256_bytes(prompt.encode("utf-8"))
        ):
            failures.append(f"{label} prompt text and sha256 must be exactly bound")
        inputs = item.get("reference_inputs")
        if not isinstance(inputs, list) or len(inputs) < 2:
            failures.append(f"{label}.reference_inputs must bind at least two ordered inputs")
        else:
            seen_sources: set[str] = set()
            seen_roles: set[str] = set()
            for input_index, input_item in enumerate(inputs):
                if not isinstance(input_item, dict) or set(input_item) != V2_INPUT_FIELDS:
                    failures.append(f"{label}.reference_inputs[{input_index}] has invalid shape")
                    continue
                source_id = input_item.get("source_id")
                role = input_item.get("role")
                if not isinstance(source_id, str) or source_id in seen_sources:
                    failures.append(f"{label}.reference_inputs[{input_index}] has an invalid source_id")
                    continue
                seen_sources.add(source_id)
                if source_id not in source_digests or input_item.get("sha256") != source_digests.get(source_id):
                    failures.append(f"{label}.reference_inputs[{input_index}] is not bound to a known source")
                if (
                    not isinstance(role, str)
                    or not REFERENCE_ROLE_RE.fullmatch(role)
                    or role in seen_roles
                ):
                    failures.append(
                        f"{label}.reference_inputs[{input_index}] has an invalid or duplicate role"
                    )
                else:
                    seen_roles.add(role)
            if item.get("input_manifest_sha256") != canonical_sha256(inputs):
                failures.append(f"{label}.input_manifest_sha256 mismatch")
        call_started, call_completed, time_failures = validate_time_window(
            item.get("started_at"),
            item.get("completed_at"),
            label,
            earliest=host_started,
            latest=host_completed,
        )
        failures.extend(time_failures)
        call_windows[generation_id] = (call_started, call_completed)
        output = item.get("output")
        failures.extend(validate_artifact(output, f"{label}.output"))
        if isinstance(output, dict):
            artifact_claims.append((f"{label}.output", output))
            digest = output.get("sha256")
            if isinstance(digest, str):
                output_digests[generation_id] = digest
                source_digests[f"generation:{generation_id}"] = digest
            generated_claims.append((f"{label}.output", output, generation_id))

    attempts_raw = payload.get("attempts")
    attempts = attempts_raw if isinstance(attempts_raw, list) else []
    attempt_ids: list[str] = []
    used_generation_ids: set[str] = set()
    first_inputs: Any = None
    if len(attempts) < 2:
        failures.append("attempts must contain an initial generation and at least one retry")
    for index, item in enumerate(attempts):
        label = f"attempts[{index}]"
        if not isinstance(item, dict) or set(item) != V2_ATTEMPT_FIELDS:
            failures.append(f"{label} has invalid shape")
            continue
        attempt_id = item.get("attempt_id")
        generation_id = item.get("generation_id")
        if (
            not isinstance(attempt_id, str)
            or not REFERENCE_ROLE_RE.fullmatch(attempt_id)
            or attempt_id in attempt_ids
        ):
            failures.append(f"{label}.attempt_id must be unique snake_case")
        else:
            attempt_ids.append(attempt_id)
        if (
            not isinstance(generation_id, str)
            or generation_id not in call_by_id
            or generation_id in used_generation_ids
        ):
            failures.append(f"{label}.generation_id must name one unused generation call")
        elif isinstance(generation_id, str):
            used_generation_ids.add(generation_id)
            inputs = call_by_id[generation_id].get("reference_inputs")
            if index == 0:
                first_inputs = inputs
            elif inputs != first_inputs:
                failures.append(f"{label} changed reference inputs instead of one retry layer")
        if item.get("unchanged_lock_sha256") != continuity_lock_sha256:
            failures.append(f"{label} is not bound to the unchanged continuity lock")
        if index == 0:
            if item.get("retry_of") is not None or item.get("corrected_layer") is not None:
                failures.append("the initial attempt cannot claim a retry or corrected layer")
        else:
            expected_parent = attempt_ids[index - 1] if len(attempt_ids) >= index else None
            if item.get("retry_of") != expected_parent:
                failures.append(f"{label}.retry_of must name the immediately preceding attempt")
            corrected_layer = item.get("corrected_layer")
            if not isinstance(corrected_layer, str) or not REFERENCE_ROLE_RE.fullmatch(corrected_layer):
                failures.append(f"{label} must identify exactly one corrected_layer")

    shots_raw = payload.get("shots")
    shots = shots_raw if isinstance(shots_raw, list) else []
    shot_ids: set[str] = set()
    accepted_attempt_id = attempt_ids[-1] if attempt_ids else None
    accepted_generation_id = attempts[-1].get("generation_id") if attempts and isinstance(attempts[-1], dict) else None
    accepted_source_id = f"generation:{accepted_generation_id}" if isinstance(accepted_generation_id, str) else ""
    if len(shots) < 3:
        failures.append("shots must contain at least three continuity-bound generations")
    for index, item in enumerate(shots):
        label = f"shots[{index}]"
        if not isinstance(item, dict) or set(item) != V2_SHOT_FIELDS:
            failures.append(f"{label} has invalid shape")
            continue
        shot_id = item.get("shot_id")
        generation_id = item.get("generation_id")
        if not isinstance(shot_id, str) or not REFERENCE_ROLE_RE.fullmatch(shot_id) or shot_id in shot_ids:
            failures.append(f"{label}.shot_id must be unique snake_case")
        else:
            shot_ids.add(shot_id)
        if (
            not isinstance(generation_id, str)
            or generation_id not in call_by_id
            or generation_id in used_generation_ids
        ):
            failures.append(f"{label}.generation_id must name one unused generation call")
        elif isinstance(generation_id, str):
            used_generation_ids.add(generation_id)
            inputs = call_by_id[generation_id].get("reference_inputs")
            source_ids = (
                {value.get("source_id") for value in inputs if isinstance(value, dict)}
                if isinstance(inputs, list)
                else set()
            )
            if accepted_source_id not in source_ids:
                failures.append(f"{label} does not inherit the accepted attempt output")
        if item.get("inherits_from") != accepted_attempt_id:
            failures.append(f"{label}.inherits_from must name the independently accepted attempt")
        if item.get("continuity_lock_sha256") != continuity_lock_sha256:
            failures.append(f"{label} is not bound to the shared continuity lock")
        delta = item.get("shot_delta")
        if (
            not isinstance(delta, str)
            or not delta.strip()
            or item.get("shot_delta_sha256") != sha256_bytes(delta.encode("utf-8"))
        ):
            failures.append(f"{label} shot_delta text and sha256 must be exactly bound")
    if set(call_by_id) != used_generation_ids:
        failures.append("every generation call must be used by exactly one attempt or shot")

    failures.extend(validate_distinct_artifact_claims(artifact_claims))
    if validate_c2pa:
        verifier_failures = (
            [] if c2patool is not None else ["a sealed c2patool snapshot is required"]
        )
        failures.extend(verifier_failures)
        if not verifier_failures and candidate_time is not None and c2patool is not None:
            trusted_tool = c2patool
            for label, artifact, generation_id in generated_claims:
                failures.extend(
                    verify_openai_c2pa(
                        artifact,
                        label,
                        c2patool=trusted_tool,
                        candidate_time=candidate_time,
                    )
                )
                signature_time = c2pa_signature_time(Path(str(artifact.get("path"))), trusted_tool)
                call_started, call_completed = call_windows.get(generation_id, (None, None))
                if (
                    signature_time is None
                    or call_started is None
                    or call_completed is None
                    or signature_time < call_started
                    or signature_time > call_completed
                ):
                    failures.append(f"{label}: C2PA signing time is outside its host-observed call window")

    limitations = payload.get("limitations")
    limitation_text = (
        " ".join(item for item in limitations if isinstance(item, str)).casefold()
        if isinstance(limitations, list)
        else ""
    )
    if (
        not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(item, str) and item.strip() for item in limitations)
        or "video" not in limitation_text
        or "cryptograph" not in limitation_text
        or "reviewer" not in limitation_text
    ):
        failures.append(
            "limitations must state that video is unverified, host execution is not cryptographic proof, and continuity is reviewer judgment"
        )

    failures.extend(
        validate_independent_review(
            review_payload,
            execution_receipt_sha256=execution_receipt_sha256,
            candidate_commit=candidate_commit,
            host_execution=host,
            attempts=[item for item in attempts if isinstance(item, dict)],
            shots=[item for item in shots if isinstance(item, dict)],
            output_digests=output_digests,
            continuity_lock_sha256=continuity_lock_sha256,
            now=now,
        )
    )
    return failures


def validate_sealed_legacy_receipt(
    payload: Any,
    expected_commit: str | None = None,
    *,
    c2patool: Path | None = None,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["receipt must contain one object"]
    failures: list[str] = []
    if set(payload) != LEGACY_RECEIPT_FIELDS:
        failures.append("receipt field set mismatch")
    if payload.get("schema_version") != "1.0.0" or payload.get("product") != "DIRcreative":
        failures.append("receipt identity mismatch")
    candidate = payload.get("candidate_commit")
    tested = payload.get("tested_commit")
    if not isinstance(candidate, str) or not COMMIT_RE.fullmatch(candidate):
        failures.append("candidate_commit must be one exact commit")
        candidate = ""
    if not isinstance(tested, str) or not COMMIT_RE.fullmatch(tested):
        failures.append("tested_commit must be one exact commit")
        tested = ""
    if expected_commit and candidate != expected_commit:
        failures.append("candidate_commit does not match --expected-commit")
    try:
        if candidate and git("rev-parse", "HEAD") != candidate:
            failures.append("candidate_commit does not match current HEAD")
        if candidate and tested and tested != candidate:
            failures.append("tested_commit must equal candidate_commit for candidate-bound media evidence")
    except ValueError as exc:
        failures.append(f"git identity check failed: {exc}")
    if payload.get("media_type") != "image" or payload.get("tool") != "image_gen.imagegen":
        failures.append("receipt must identify the real image generation tool")
    if payload.get("real_tool_execution") is not True:
        failures.append("real tool execution is not proven")
    if payload.get("video_verified") is not False:
        failures.append("this image-only receipt must not claim video verification")

    verified_paths = payload.get("verified_contract_paths")
    verified_path_names: set[str] = set()
    if not isinstance(verified_paths, list) or not verified_paths:
        failures.append("verified_contract_paths must contain the required media contract allowlist")
    else:
        for index, item in enumerate(verified_paths):
            if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                failures.append(f"verified_contract_paths[{index}] has invalid shape")
                continue
            relative = item.get("path")
            digest = item.get("sha256")
            if (
                not isinstance(relative, str)
                or not relative
                or Path(relative).is_absolute()
                or ".." in Path(relative).parts
                or not isinstance(digest, str)
                or not SHA256_RE.fullmatch(digest)
            ):
                failures.append(f"verified_contract_paths[{index}] is invalid")
                continue
            canonical_relative = Path(relative).as_posix()
            if canonical_relative != relative or relative not in REQUIRED_MEDIA_CONTRACT_PATHS:
                failures.append(f"verified_contract_paths[{index}] is outside the media contract allowlist")
                continue
            if relative in verified_path_names:
                failures.append(f"verified_contract_paths[{index}] duplicates {relative}")
                continue
            verified_path_names.add(relative)
            if not candidate or not tested:
                continue
            try:
                tested_bytes = git_bytes(tested, relative)
                candidate_bytes = git_bytes(candidate, relative)
            except ValueError as exc:
                failures.append(f"verified_contract_paths[{index}] cannot be read: {exc}")
                continue
            if sha256_bytes(tested_bytes) != digest or sha256_bytes(candidate_bytes) != digest:
                failures.append(f"verified_contract_paths[{index}] changed after the real media test")
        if verified_path_names != REQUIRED_MEDIA_CONTRACT_PATHS:
            missing_paths = sorted(REQUIRED_MEDIA_CONTRACT_PATHS - verified_path_names)
            failures.append(f"verified_contract_paths is missing required contracts: {missing_paths}")

    artifact_claims: list[tuple[str, dict[str, Any]]] = []
    generated_claims: list[tuple[str, dict[str, Any]]] = []
    references = payload.get("references")
    if not isinstance(references, list) or len(references) < 2:
        failures.append("at least two bound references are required")
    else:
        roles: set[str] = set()
        for index, item in enumerate(references):
            label = f"references[{index}]"
            failures.extend(validate_artifact(item, label, extra_fields=frozenset({"role"})))
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            if not isinstance(role, str) or not REFERENCE_ROLE_RE.fullmatch(role) or role in roles:
                failures.append(f"{label}: role must be one unique explicit snake_case role")
            else:
                roles.add(role)
            artifact_claims.append((label, item))

    attempts = payload.get("attempts")
    outcomes: list[str] = []
    if not isinstance(attempts, list) or len(attempts) < 2:
        failures.append("attempts must contain a rejected pass and an accepted retry")
    else:
        for index, item in enumerate(attempts):
            label = f"attempts[{index}].artifact"
            if not isinstance(item, dict) or set(item) != {"outcome", "artifact", "qa_findings"}:
                failures.append(f"attempts[{index}] has invalid shape")
                continue
            outcome = item.get("outcome")
            findings = item.get("qa_findings")
            if (
                outcome not in {"rejected", "accepted"}
                or not isinstance(findings, list)
                or not findings
                or not all(isinstance(value, str) and value.strip() for value in findings)
            ):
                failures.append(f"attempts[{index}] lacks a real QA disposition")
            else:
                outcomes.append(str(outcome))
            artifact = item.get("artifact")
            failures.extend(validate_artifact(artifact, label))
            if isinstance(artifact, dict):
                artifact_claims.append((label, artifact))
                generated_claims.append((label, artifact))
        if outcomes != ["rejected", "accepted"]:
            failures.append("attempt order must be rejected then accepted")

    shots = payload.get("multi_shot_evidence")
    if not isinstance(shots, list) or len(shots) < 3:
        failures.append("multi_shot_evidence must contain at least three shots")
    else:
        shot_ids: set[str] = set()
        for index, item in enumerate(shots):
            label = f"multi_shot_evidence[{index}].artifact"
            if not isinstance(item, dict) or set(item) != {"shot_id", "artifact", "continuity_status"}:
                failures.append(f"multi_shot_evidence[{index}] has invalid shape")
                continue
            shot_id = item.get("shot_id")
            if not isinstance(shot_id, str) or not shot_id or shot_id in shot_ids:
                failures.append(f"multi_shot_evidence[{index}] has invalid shot_id")
            else:
                shot_ids.add(shot_id)
            if item.get("continuity_status") != "pass":
                failures.append(f"multi_shot_evidence[{index}] did not pass continuity QA")
            artifact = item.get("artifact")
            failures.extend(validate_artifact(artifact, label))
            if isinstance(artifact, dict):
                artifact_claims.append((label, artifact))
                generated_claims.append((label, artifact))
    failures.extend(validate_distinct_artifact_claims(artifact_claims))
    verifier_failures = [] if c2patool is not None else ["a sealed c2patool snapshot is required"]
    failures.extend(verifier_failures)
    candidate_time: datetime | None = None
    if candidate:
        try:
            candidate_time = parse_datetime(git("show", "-s", "--format=%cI", candidate))
        except ValueError as exc:
            failures.append(f"cannot resolve candidate commit time: {exc}")
    if candidate_time is None:
        failures.append("candidate commit time is unavailable")
    if not verifier_failures and candidate_time is not None and c2patool is not None:
        for label, artifact in generated_claims:
            failures.extend(
                verify_openai_c2pa(
                    artifact,
                    label,
                    c2patool=c2patool,
                    candidate_time=candidate_time,
                )
            )
    limitations = payload.get("limitations")
    if not isinstance(limitations, list) or not limitations or not all(
        isinstance(item, str) and item.strip() for item in limitations
    ):
        failures.append("limitations must state the remaining unverified boundary")
    elif not any("video" in item.casefold() for item in limitations):
        failures.append("limitations must explicitly state that video is unverified")
    return failures


def self_test() -> int:
    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(data, zlib.crc32(chunk_type)) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    def valid_png(width: int, height: int, seed: int = 0) -> bytes:
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        raw = b"".join(
            b"\x00" + bytes([(row + seed) % 256, (20 + seed) % 256, (30 + seed) % 256]) * width
            for row in range(height)
        )
        return (
            b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", ihdr)
            + png_chunk(b"IDAT", zlib.compress(raw))
            + png_chunk(b"IEND", b"")
        )

    with tempfile.TemporaryDirectory(prefix="dircreative-media-forward-") as raw:
        path = Path(raw) / "fixture.png"
        path.write_bytes(valid_png(2, 3))
        if png_dimensions(path) != (2, 3):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        artifact = {"path": str(path), "sha256": sha256(path), "width": 2, "height": 3}
        if validate_artifact(artifact, "fixture"):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        artifact["sha256"] = "0" * 64
        if not validate_artifact(artifact, "fixture"):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        truncated = Path(raw) / "truncated.png"
        truncated.write_bytes(path.read_bytes()[:-12])
        try:
            png_dimensions(truncated)
        except ValueError:
            pass
        else:
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        bad_crc = Path(raw) / "bad-crc.png"
        corrupted = bytearray(path.read_bytes())
        corrupted[29] ^= 0x01
        bad_crc.write_bytes(corrupted)
        try:
            png_dimensions(bad_crc)
        except ValueError:
            pass
        else:
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        duplicate = Path(raw) / "duplicate.png"
        duplicate.write_bytes(path.read_bytes())
        first = {"path": str(path), "sha256": sha256(path), "width": 2, "height": 3}
        second = {"path": str(duplicate), "sha256": sha256(duplicate), "width": 2, "height": 3}
        if not validate_distinct_artifact_claims([("first", first), ("second", second)]):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        sealed, _, seal_failures = seal_artifact_snapshot(
            first,
            "first",
            Path(raw) / "sealed.png",
        )
        if seal_failures or sealed is None or validate_artifact(sealed, "sealed"):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        _, _, mutation_failures = seal_artifact_snapshot(
            first,
            "mutating",
            Path(raw) / "mutating-sealed.png",
            after_copy_hook=lambda: path.write_bytes(valid_png(3, 3)),
        )
        if not any("changed while sealing" in item for item in mutation_failures):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1

        evidence_paths: list[Path] = []
        for index in range(7):
            evidence_path = Path(raw) / f"evidence-{index}.png"
            evidence_path.write_bytes(valid_png(2 + index, 3, index + 1))
            evidence_paths.append(evidence_path)

        def evidence_artifact(index: int) -> dict[str, Any]:
            evidence_path = evidence_paths[index]
            width, height = png_dimensions(evidence_path)
            return {
                "path": str(evidence_path),
                "sha256": sha256(evidence_path),
                "width": width,
                "height": height,
            }

        candidate_commit = "a" * 40
        candidate_blobs = {
            relative: f"self-test fixture for {relative}\n".encode("utf-8")
            for relative in REQUIRED_CANDIDATE_SKILL_PATHS
        }
        invocation = "Use $dircreative from the exact candidate path for an isolated image forward test."
        now = datetime.now(timezone.utc)

        def utc_offset(seconds: int) -> str:
            return (now.replace(microsecond=0) + timedelta(seconds=seconds)).isoformat().replace(
                "+00:00", "Z"
            )

        reference_assets = [
            {
                "reference_id": "character_ref",
                "role": "character_identity",
                "artifact": evidence_artifact(0),
            },
            {
                "reference_id": "product_ref",
                "role": "product_identity",
                "artifact": evidence_artifact(1),
            },
        ]
        continuity_lock = {
            "identity_reference_ids": ["character_ref", "product_ref"],
            "locked_attributes": ["same character face and wardrobe", "same product form and label"],
        }
        lock_digest = canonical_sha256(continuity_lock)
        base_inputs = [
            {
                "source_id": "reference:character_ref",
                "role": "character_identity",
                "sha256": reference_assets[0]["artifact"]["sha256"],
            },
            {
                "source_id": "reference:product_ref",
                "role": "product_identity",
                "sha256": reference_assets[1]["artifact"]["sha256"],
            },
        ]

        def generation_call(
            generation_id: str,
            prompt: str,
            artifact_index: int,
            inputs: list[dict[str, str]],
            event_index: int,
        ) -> dict[str, Any]:
            return {
                "generation_id": generation_id,
                "host_call_id": f"exec-selftest-{event_index}",
                "host_call_id_status": "available",
                "provider_response_id": None,
                "provider_response_id_status": "unavailable",
                "tool": "image_gen.imagegen",
                "provider": "OpenAI Media Service",
                "model": "gpt-image 2.0",
                "started_at": utc_offset(-19 + event_index * 2),
                "completed_at": utc_offset(-18 + event_index * 2),
                "prompt": prompt,
                "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
                "reference_inputs": copy.deepcopy(inputs),
                "input_manifest_sha256": canonical_sha256(inputs),
                "output": evidence_artifact(artifact_index),
            }

        calls = [
            generation_call(
                "gen_attempt_one", "Initial identity-bound commercial frame.", 2, base_inputs, 0
            ),
            generation_call(
                "gen_attempt_two",
                "Correct only character identity; preserve every lock.",
                3,
                base_inputs,
                1,
            ),
        ]
        accepted_input = {
            "source_id": "generation:gen_attempt_two",
            "role": "accepted_identity_anchor",
            "sha256": calls[1]["output"]["sha256"],
        }
        for index in range(3):
            shot_inputs = copy.deepcopy(base_inputs) + [copy.deepcopy(accepted_input)]
            calls.append(
                generation_call(
                    f"gen_shot_{index + 1}",
                    f"Shot {index + 1}; preserve locked identity and change only the described beat.",
                    4 + index,
                    shot_inputs,
                    index + 2,
                )
            )
        attempts = [
            {
                "attempt_id": "attempt_one",
                "generation_id": "gen_attempt_one",
                "retry_of": None,
                "corrected_layer": None,
                "unchanged_lock_sha256": lock_digest,
            },
            {
                "attempt_id": "attempt_two",
                "generation_id": "gen_attempt_two",
                "retry_of": "attempt_one",
                "corrected_layer": "character_identity",
                "unchanged_lock_sha256": lock_digest,
            },
        ]
        shots = []
        for index in range(3):
            delta = f"camera beat {index + 1} with a distinct action while identity remains unchanged"
            shots.append(
                {
                    "shot_id": f"shot_{index + 1}",
                    "generation_id": f"gen_shot_{index + 1}",
                    "inherits_from": "attempt_two",
                    "continuity_lock_sha256": lock_digest,
                    "shot_delta": delta,
                    "shot_delta_sha256": sha256_bytes(delta.encode("utf-8")),
                }
            )
        candidate_record = {
            "commit": candidate_commit,
            "observed_skill_paths": [
                {"path": relative, "sha256": sha256_bytes(candidate_blobs[relative])}
                for relative in sorted(REQUIRED_CANDIDATE_SKILL_PATHS)
            ],
        }
        host_execution_record = {
            "actor_id": "self_test_executor",
            "task_id": "self_test_execution_task",
            "explicit_invocation": invocation,
            "explicit_invocation_sha256": sha256_bytes(invocation.encode("utf-8")),
            "started_at": utc_offset(-20),
            "completed_at": utc_offset(-10),
            "evidence_level": "unsigned_host_trace",
            "cryptographically_signed": False,
        }
        execution_request = execution_request_record(
            {"candidate": candidate_record, "host_execution": host_execution_record}
        )

        source_path_by_id = {
            "reference:character_ref": reference_assets[0]["artifact"]["path"],
            "reference:product_ref": reference_assets[1]["artifact"]["path"],
        }
        execution_trace_records: list[dict[str, Any]] = [
            {
                "timestamp": utc_offset(-31),
                "type": "session_meta",
                "payload": {
                    "id": "self_test_execution_task",
                    "session_id": "self_test_execution_task",
                },
            },
            {
                "timestamp": utc_offset(-30),
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "id": "execution-request-event",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": execution_request_trace_text(execution_request),
                        }
                    ],
                },
            },
            {
                "timestamp": utc_offset(-29),
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "id": "candidate-observation-event",
                    "call_id": "candidate-observation-call",
                    "output": [
                        {
                            "type": "input_text",
                            "text": CANDIDATE_OBSERVATION_MARKER
                            + json.dumps(
                                candidate_record,
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n",
                        }
                    ],
                },
            },
        ]
        for index, call in enumerate(calls):
            referenced_paths = [
                source_path_by_id[item["source_id"]] for item in call["reference_inputs"]
            ]
            request = {
                "prompt": call["prompt"],
                "referenced_image_paths": referenced_paths,
            }
            execution_trace_records.extend(
                [
                    {
                        "timestamp": call["started_at"],
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "id": f"request-event-{index}",
                            "call_id": f"outer-call-{index}",
                            "input": imagegen_trace_source(request),
                        },
                    },
                    {
                        "timestamp": call["completed_at"],
                        "type": "event_msg",
                        "payload": {
                            "type": "image_generation_end",
                            "call_id": call["host_call_id"],
                            "status": "completed",
                            "saved_path": call["output"]["path"],
                            "result": base64.b64encode(
                                Path(call["output"]["path"]).read_bytes()
                            ).decode("ascii"),
                        },
                    },
                ]
            )
            source_path_by_id[f"generation:{call['generation_id']}"] = call["output"]["path"]
        execution_trace_path = Path(raw) / "execution-host-trace.jsonl"
        execution_trace_bytes = b"".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            for record in execution_trace_records
        )
        execution_trace_path.write_bytes(execution_trace_bytes)
        execution_trace_descriptor = {
            "thread_id": "self_test_execution_task",
            "prefix_bytes": len(execution_trace_bytes),
            "prefix_sha256": sha256_bytes(execution_trace_bytes),
            "invocation_event_id": "execution-request-event",
            "candidate_observation_event_id": "candidate-observation-event",
            "evidence_level": "unsigned_host_trace",
            "cryptographically_signed": False,
        }
        execution_payload = {
            "schema_version": "2.0.0",
            "product": "DIRcreative",
            "media_type": "image",
            "candidate": candidate_record,
            "host_trace": execution_trace_descriptor,
            "host_execution": host_execution_record,
            "reference_assets": reference_assets,
            "continuity_lock": continuity_lock,
            "generation_calls": calls,
            "attempts": attempts,
            "shots": shots,
            "video_verified": False,
            "limitations": [
                "Video is unverified.",
                "Host execution is observed but not cryptographically signed.",
                "Continuity quality remains independent reviewer judgment.",
            ],
        }
        execution_bytes = json.dumps(
            execution_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        rubric = "Reject identity drift, accept only the corrected retry, and compare all shots for visible continuity."
        review_payload = {
            "schema_version": "1.0.0",
            "product": "DIRcreative",
            "candidate_commit": candidate_commit,
            "execution_receipt_sha256": sha256_bytes(execution_bytes),
            "reviewer": {
                "actor_id": "self_test_reviewer",
                "task_id": "self_test_review_task",
                "review_method": "independent_visual_review",
                "input_scope": "raw_references_outputs_and_rubric_only",
                "started_at": utc_offset(-9),
                "completed_at": utc_offset(-1),
            },
            "rubric": rubric,
            "rubric_sha256": sha256_bytes(rubric.encode("utf-8")),
            "artifact_reviews": [
                {
                    "subject_id": "attempt_one",
                    "artifact_sha256": calls[0]["output"]["sha256"],
                    "decision": "reject",
                    "observations": ["Character identity visibly departs from the locked reference."],
                },
                {
                    "subject_id": "attempt_two",
                    "artifact_sha256": calls[1]["output"]["sha256"],
                    "decision": "accept",
                    "observations": ["Character and product identity visibly match both locked references."],
                },
                *[
                    {
                        "subject_id": f"shot_{index + 1}",
                        "artifact_sha256": calls[index + 2]["output"]["sha256"],
                        "decision": "pass",
                        "observations": [
                            f"Shot {index + 1} preserves the same face, wardrobe, product form, and label."
                        ],
                    }
                    for index in range(3)
                ],
            ],
            "continuity_review": {
                "shot_ids": ["shot_1", "shot_2", "shot_3"],
                "decision": "pass",
                "continuity_lock_sha256": lock_digest,
                "observations": [
                    "Across all three shots the face, wardrobe, product geometry, and product label remain visibly stable."
                ],
            },
            "limitations": ["Continuity is an independent reviewer judgment, not machine-proven semantics."],
        }
        review_claim = review_claim_sha256(review_payload)
        review_request = visual_review_request_record(execution_payload, review_payload)
        review_trace_records: list[dict[str, Any]] = [
            {
                "timestamp": utc_offset(-9),
                "type": "session_meta",
                "payload": {
                    "id": "self_test_review_task",
                    "session_id": "self_test_review_task",
                },
            },
            {
                "timestamp": utc_offset(-9),
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "id": "review-request-event",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": visual_review_request_trace_text(review_request),
                        }
                    ],
                },
            },
        ]
        review_view_event_ids: list[str] = []
        for index, call in enumerate(calls):
            output_path = call["output"]["path"]
            event_id = f"view-event-{index}"
            outer_call_id = f"view-call-{index}"
            review_view_event_ids.append(event_id)
            review_trace_records.extend(
                [
                    {
                        "timestamp": utc_offset(-8 + index),
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call",
                            "name": "exec",
                            "id": event_id,
                            "call_id": outer_call_id,
                            "input": visual_view_trace_source(output_path),
                        },
                    },
                    {
                        "timestamp": utc_offset(-8 + index),
                        "type": "response_item",
                        "payload": {
                            "type": "custom_tool_call_output",
                            "id": f"view-output-{index}",
                            "call_id": outer_call_id,
                            "output": [{"type": "input_image", "image_url": "fixture"}],
                        },
                    },
                ]
            )
        review_trace_records.append(
            {
                "timestamp": utc_offset(-1),
                "type": "event_msg",
                "payload": {
                    "type": "agent_message",
                    "message": VISUAL_REVIEW_CLAIM_MARKER + review_claim,
                },
            }
        )
        review_trace_path = Path(raw) / "review-host-trace.jsonl"
        review_trace_bytes = b"".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            for record in review_trace_records
        )
        review_trace_path.write_bytes(review_trace_bytes)
        review_payload["host_trace"] = {
            "thread_id": "self_test_review_task",
            "prefix_bytes": len(review_trace_bytes),
            "prefix_sha256": sha256_bytes(review_trace_bytes),
            "review_request_event_id": "review-request-event",
            "view_event_ids": review_view_event_ids,
            "review_claim_sha256": review_claim,
            "evidence_level": "unsigned_host_trace",
            "cryptographically_signed": False,
        }

        def validate_fixture(
            candidate_payload: dict[str, Any],
            candidate_review: dict[str, Any],
            *,
            candidate_execution_trace: Path = execution_trace_path,
            candidate_review_trace: Path = review_trace_path,
        ) -> list[str]:
            raw_bytes = json.dumps(
                candidate_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            bound_review = copy.deepcopy(candidate_review)
            bound_review["execution_receipt_sha256"] = sha256_bytes(raw_bytes)
            return validate_receipt(
                candidate_payload,
                candidate_commit,
                review_payload=bound_review,
                execution_receipt_sha256=sha256_bytes(raw_bytes),
                require_candidate_skill_execution=True,
                validate_c2pa=False,
                host_event_log=candidate_execution_trace,
                review_host_event_log=candidate_review_trace,
                head_reader=lambda: candidate_commit,
                blob_reader=lambda commit, relative: candidate_blobs[relative],
                commit_time_reader=lambda commit: utc_offset(-30),
            )

        if validate_fixture(execution_payload, review_payload):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        negative_mutations: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        bad_skill = copy.deepcopy(execution_payload)
        bad_skill["candidate"]["observed_skill_paths"][0]["sha256"] = "0" * 64
        negative_mutations.append(("candidate bytes", bad_skill, review_payload))
        malformed_candidate = copy.deepcopy(execution_payload)
        malformed_candidate["candidate"] = []
        negative_mutations.append(
            ("candidate record has invalid shape", malformed_candidate, review_payload)
        )
        malformed_calls = copy.deepcopy(execution_payload)
        malformed_calls["generation_calls"] = {}
        negative_mutations.append(
            ("generation_calls must contain", malformed_calls, review_payload)
        )
        bad_prompt = copy.deepcopy(execution_payload)
        bad_prompt["generation_calls"][0]["prompt_sha256"] = "0" * 64
        negative_mutations.append(("prompt", bad_prompt, review_payload))
        untraced_prompt = copy.deepcopy(execution_payload)
        untraced_prompt["generation_calls"][0]["prompt"] += " Untraced mutation."
        untraced_prompt["generation_calls"][0]["prompt_sha256"] = sha256_bytes(
            untraced_prompt["generation_calls"][0]["prompt"].encode("utf-8")
        )
        negative_mutations.append(("does not match the host trace", untraced_prompt, review_payload))
        unavailable_host_id = copy.deepcopy(execution_payload)
        unavailable_host_id["generation_calls"][0]["host_call_id"] = None
        unavailable_host_id["generation_calls"][0]["host_call_id_status"] = "unavailable"
        negative_mutations.append(("available host_call_id", unavailable_host_id, review_payload))
        bad_trace_digest = copy.deepcopy(execution_payload)
        bad_trace_digest["host_trace"]["prefix_sha256"] = "0" * 64
        negative_mutations.append(("prefix sha256 mismatch", bad_trace_digest, review_payload))
        missing_invocation = copy.deepcopy(execution_payload)
        missing_invocation["host_trace"]["invocation_event_id"] = "missing-invocation-event"
        negative_mutations.append(
            ("explicit $dircreative invocation request", missing_invocation, review_payload)
        )
        bad_reference = copy.deepcopy(execution_payload)
        bad_reference["generation_calls"][1]["reference_inputs"][0]["sha256"] = "0" * 64
        bad_reference["generation_calls"][1]["input_manifest_sha256"] = canonical_sha256(
            bad_reference["generation_calls"][1]["reference_inputs"]
        )
        negative_mutations.append(("known source", bad_reference, review_payload))
        bad_retry = copy.deepcopy(execution_payload)
        bad_retry["generation_calls"][1]["reference_inputs"] = bad_retry["generation_calls"][1][
            "reference_inputs"
        ][:-1]
        bad_retry["generation_calls"][1]["input_manifest_sha256"] = canonical_sha256(
            bad_retry["generation_calls"][1]["reference_inputs"]
        )
        negative_mutations.append(("changed reference inputs", bad_retry, review_payload))
        bad_inheritance = copy.deepcopy(execution_payload)
        bad_inheritance["shots"][0]["inherits_from"] = "attempt_one"
        negative_mutations.append(("inherits_from", bad_inheritance, review_payload))
        same_reviewer = copy.deepcopy(review_payload)
        same_reviewer["reviewer"]["actor_id"] = "self_test_executor"
        negative_mutations.append(("different actor_id", execution_payload, same_reviewer))
        unbound_review_task = copy.deepcopy(review_payload)
        unbound_review_task["reviewer"]["task_id"] = "self_test_execution_task"
        negative_mutations.append(("not bound to the review trace", execution_payload, unbound_review_task))
        missing_view = copy.deepcopy(review_payload)
        missing_view["host_trace"]["view_event_ids"] = missing_view["host_trace"][
            "view_event_ids"
        ][:-1]
        negative_mutations.append(("do not exactly match", execution_payload, missing_view))
        missing_review_request = copy.deepcopy(review_payload)
        missing_review_request["host_trace"][
            "review_request_event_id"
        ] = "missing-review-request-event"
        negative_mutations.append(
            ("independent review input request", execution_payload, missing_review_request)
        )
        missing_observation = copy.deepcopy(review_payload)
        missing_observation["artifact_reviews"][0]["observations"] = []
        negative_mutations.append(("visible observations", execution_payload, missing_observation))
        wrong_time = copy.deepcopy(review_payload)
        wrong_time["reviewer"]["started_at"] = utc_offset(-30)
        negative_mutations.append(("candidate evidence window", execution_payload, wrong_time))
        for expected_fragment, candidate_payload, candidate_review in negative_mutations:
            mutation_result = validate_fixture(candidate_payload, candidate_review)
            if not any(expected_fragment in item for item in mutation_result):
                print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
                print(f"missing negative evidence: {expected_fragment}: {mutation_result}")
                return 1

        malformed_marker_records = copy.deepcopy(execution_trace_records)
        for record in malformed_marker_records:
            trace_payload = record.get("payload")
            if isinstance(trace_payload, dict) and trace_payload.get("id") == "execution-request-event":
                trace_payload["content"][0]["text"] = (
                    "DIRCREATIVE_EXECUTION_REQUEST_BASE64:" + trace_marker_base64(b"{}")
                )
                break
        malformed_marker_bytes = b"".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            + b"\n"
            for record in malformed_marker_records
        )
        malformed_marker_path = Path(raw) / "execution-host-trace-malformed-marker.jsonl"
        malformed_marker_path.write_bytes(malformed_marker_bytes)
        malformed_marker_payload = copy.deepcopy(execution_payload)
        malformed_marker_payload["host_trace"]["prefix_bytes"] = len(malformed_marker_bytes)
        malformed_marker_payload["host_trace"]["prefix_sha256"] = sha256_bytes(
            malformed_marker_bytes
        )
        malformed_marker_result = validate_fixture(
            malformed_marker_payload,
            review_payload,
            candidate_execution_trace=malformed_marker_path,
        )
        if not any("sealed request has invalid fields" in item for item in malformed_marker_result):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            print(f"malformed execution marker was not rejected: {malformed_marker_result}")
            return 1

        duplicate_view_records = copy.deepcopy(review_trace_records)
        duplicate_view_records[-1:-1] = [
            {
                "timestamp": utc_offset(-2),
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "id": "duplicate-view-event",
                    "call_id": "duplicate-view-call",
                    "input": visual_view_trace_source(calls[0]["output"]["path"]),
                },
            },
            {
                "timestamp": utc_offset(-2),
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "id": "duplicate-view-output",
                    "call_id": "duplicate-view-call",
                    "output": [{"type": "input_image", "image_url": "fixture"}],
                },
            },
        ]
        duplicate_view_bytes = b"".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            + b"\n"
            for record in duplicate_view_records
        )
        duplicate_view_path = Path(raw) / "review-host-trace-duplicate-view.jsonl"
        duplicate_view_path.write_bytes(duplicate_view_bytes)
        duplicate_view_review = copy.deepcopy(review_payload)
        duplicate_view_review["host_trace"]["prefix_bytes"] = len(duplicate_view_bytes)
        duplicate_view_review["host_trace"]["prefix_sha256"] = sha256_bytes(
            duplicate_view_bytes
        )
        duplicate_view_review["host_trace"]["view_event_ids"].append(
            "duplicate-view-event"
        )
        duplicate_view_result = validate_fixture(
            execution_payload,
            duplicate_view_review,
            candidate_review_trace=duplicate_view_path,
        )
        if not any("exactly once" in item for item in duplicate_view_result):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            print(f"duplicate visual view was not rejected: {duplicate_view_result}")
            return 1

        legacy_payload = {field: None for field in LEGACY_RECEIPT_FIELDS}
        legacy_payload["schema_version"] = "1.0.0"
        if not validate_receipt(
            legacy_payload,
            candidate_commit,
            require_candidate_skill_execution=True,
            validate_c2pa=False,
        ):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
        if not validate_c2patool(None):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
    print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: PASS")
    return 0


def read_bounded_json(path: Path, label: str) -> tuple[Any, bytes]:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise ValueError(f"{label} must be an absolute path")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ValueError(f"{label} cannot be read safely: O_NOFOLLOW is unavailable")
    try:
        descriptor = os.open(expanded, os.O_RDONLY | nofollow)
    except OSError as exc:
        raise ValueError(f"{label} cannot be opened safely: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > MAX_RECEIPT_BYTES
        ):
            raise ValueError(f"{label} must be one bounded regular single-link file")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    try:
        path_after = expanded.lstat()
    except OSError as exc:
        raise ValueError(f"{label} path changed while reading: {exc}") from exc
    if file_identity(before) != file_identity(after) or file_identity(before) != file_identity(path_after):
        raise ValueError(f"{label} changed while reading")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise ValueError(f"{label} was truncated while reading")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is invalid JSON: {exc}") from exc
    return payload, raw


def emit_candidate_observation(expected_commit: str | None) -> int:
    if not isinstance(expected_commit, str) or not COMMIT_RE.fullmatch(expected_commit):
        print("DIRCREATIVE_CANDIDATE_OBSERVATION: FAIL", file=sys.stderr)
        print("- --expected-commit must be one full lowercase commit", file=sys.stderr)
        return 1
    try:
        if current_head() != expected_commit:
            raise ValueError("current HEAD does not match --expected-commit")
        if git("status", "--porcelain"):
            raise ValueError("candidate observation requires a clean worktree")
        candidate = {
            "commit": expected_commit,
            "observed_skill_paths": [
                {"path": relative, "sha256": sha256_bytes(git_bytes(expected_commit, relative))}
                for relative in sorted(REQUIRED_CANDIDATE_SKILL_PATHS)
            ],
        }
    except ValueError as exc:
        print("DIRCREATIVE_CANDIDATE_OBSERVATION: FAIL", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        return 1
    print(
        CANDIDATE_OBSERVATION_MARKER
        + json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a real DIRcreative media forward-test receipt.")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument(
        "--review-receipt",
        type=Path,
        help="Separate independent visual-review receipt required for schema 2 candidate execution evidence.",
    )
    parser.add_argument("--expected-commit")
    parser.add_argument(
        "--host-event-log",
        type=Path,
        help="Absolute Codex JSONL task log whose declared prefix binds candidate execution.",
    )
    parser.add_argument(
        "--review-host-event-log",
        type=Path,
        help="Absolute JSONL log from the separate visual-review task.",
    )
    parser.add_argument(
        "--c2patool",
        type=Path,
        help="Absolute path to the exact pinned c2patool verifier (required with --receipt).",
    )
    parser.add_argument(
        "--require-candidate-skill-execution",
        action="store_true",
        help="Reject legacy provenance-only receipts and require schema 2 host observation plus independent review.",
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--emit-candidate-observation", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.emit_candidate_observation:
        return emit_candidate_observation(args.expected_commit)
    if args.receipt is None:
        parser.error("--receipt is required")
    if args.c2patool is None:
        parser.error("--c2patool is required with --receipt")
    if args.require_candidate_skill_execution and args.review_receipt is None:
        parser.error("--require-candidate-skill-execution requires --review-receipt")
    if args.require_candidate_skill_execution and (
        args.host_event_log is None or args.review_host_event_log is None
    ):
        parser.error(
            "--require-candidate-skill-execution requires --host-event-log and --review-host-event-log"
        )
    try:
        payload, receipt_bytes = read_bounded_json(args.receipt, "execution receipt")
        review_payload = None
        if args.review_receipt is not None:
            review_payload, _ = read_bounded_json(args.review_receipt, "review receipt")
    except ValueError as exc:
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: FAIL", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        return 1
    failures = validate_receipt(
        payload,
        args.expected_commit,
        c2patool=args.c2patool,
        review_payload=review_payload,
        execution_receipt_sha256=sha256_bytes(receipt_bytes),
        require_candidate_skill_execution=args.require_candidate_skill_execution,
        host_event_log=args.host_event_log,
        review_host_event_log=args.review_host_event_log,
    )
    if failures:
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1
    print("media_type: image")
    print("media_provenance: MACHINE_VERIFIED")
    if isinstance(payload, dict) and payload.get("schema_version") == "2.0.0":
        print("candidate_skill_execution: UNSIGNED_HOST_TRACE")
        print("tool_request_binding: UNSIGNED_HOST_TRACE")
        print("host_execution_cryptographically_signed: false")
        print("independent_visual_review: PASS")
        print("accepted_retry: REVIEWER_ASSERTED")
        print("continuity_quality: REVIEWER_ASSERTED")
        print("multi_shot_evidence: HASH_BOUND")
        print("video_verified: false")
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: PASS")
    else:
        print("candidate_skill_execution: NOT_PROVEN")
        print("tool_request_binding: NOT_PROVEN")
        print("independent_visual_review: NOT_PROVEN")
        print("video_verified: false")
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: PROVENANCE_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
