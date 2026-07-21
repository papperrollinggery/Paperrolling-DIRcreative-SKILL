#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
from datetime import datetime, timezone
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
RECEIPT_FIELDS = {
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def validate_c2patool(path: Path | None) -> list[str]:
    if path is None:
        return ["an exact trusted c2patool binary is required for real tool provenance"]
    expanded = path.expanduser()
    if (
        not expanded.is_absolute()
        or not regular_single_link(expanded)
        or not os.access(expanded, os.X_OK)
    ):
        return ["c2patool must be one absolute executable regular single-link file"]
    digest = sha256(expanded)
    if digest not in C2PATOOL_ALLOWED_SHA256:
        return [f"c2patool binary is not an allowed exact verifier: {digest}"]
    proc = subprocess.run(
        [str(expanded), "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0 or proc.stdout.strip() != "c2patool 0.27.0":
        return ["c2patool version identity mismatch"]
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
        for action in actions
    ):
        failures.append(f"{label}: gpt-image creation assertion is missing")

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
    references = sealed_payload.get("references")
    if isinstance(references, list):
        for index, item in enumerate(references):
            if isinstance(item, dict):
                claims.append((f"references[{index}]", item, lambda value, i=index: references.__setitem__(i, value)))
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
) -> list[str]:
    if not isinstance(payload, dict):
        return ["receipt must contain one object"]
    with tempfile.TemporaryDirectory(prefix="dircreative-media-evidence-snapshot-") as raw:
        sealed_payload, sealing_failures = seal_receipt_artifacts(payload, Path(raw))
        if sealing_failures:
            return sealing_failures
        return validate_sealed_receipt(
            sealed_payload,
            expected_commit,
            c2patool=c2patool,
        )


def validate_sealed_receipt(
    payload: Any,
    expected_commit: str | None = None,
    *,
    c2patool: Path | None = None,
) -> list[str]:
    if not isinstance(payload, dict):
        return ["receipt must contain one object"]
    failures: list[str] = []
    if set(payload) != RECEIPT_FIELDS:
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
    verifier_failures = validate_c2patool(c2patool)
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
                    c2patool=c2patool.expanduser(),
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

    def valid_png(width: int, height: int) -> bytes:
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        raw = b"".join(b"\x00" + bytes([row, 20, 30]) * width for row in range(height))
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
        if not validate_c2patool(None):
            print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: FAIL")
            return 1
    print("DIRCREATIVE_MEDIA_FORWARD_SELF_TEST: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a real DIRcreative media forward-test receipt.")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--expected-commit")
    parser.add_argument(
        "--c2patool",
        type=Path,
        help="Absolute path to the exact pinned c2patool verifier (required with --receipt).",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.receipt is None:
        parser.error("--receipt is required")
    if args.c2patool is None:
        parser.error("--c2patool is required with --receipt")
    receipt_path = args.receipt.expanduser()
    if not receipt_path.is_absolute() or not regular_single_link(receipt_path):
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: FAIL", file=sys.stderr)
        print("- receipt must be one absolute regular single-link file", file=sys.stderr)
        return 1
    if receipt_path.stat().st_size <= 0 or receipt_path.stat().st_size > MAX_RECEIPT_BYTES:
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: FAIL", file=sys.stderr)
        print("- receipt size is outside the audit limit", file=sys.stderr)
        return 1
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: FAIL", file=sys.stderr)
        print(f"- invalid receipt JSON: {exc}", file=sys.stderr)
        return 1
    failures = validate_receipt(payload, args.expected_commit, c2patool=args.c2patool)
    if failures:
        print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1
    print("media_type: image")
    print("real_tool_execution: true")
    print("c2pa_openai_provenance: true")
    print("accepted_retry: true")
    print("multi_shot_evidence: true")
    print("video_verified: false")
    print("DIRCREATIVE_MEDIA_FORWARD_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
