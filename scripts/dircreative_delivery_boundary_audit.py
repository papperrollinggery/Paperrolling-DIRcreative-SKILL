#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path, PurePosixPath
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
MATCH_FIELDS = (
    "geometry",
    "subject_position",
    "subject_size",
    "direction",
    "speed",
    "visual_anchor",
)
FRAME_CONTENT_FIELDS = (
    "view",
    "storyline",
    "actual_super",
    "ui_data",
    "proposal_brand_line",
)
FOUNDATION_FIELDS = (
    "audience_state_change",
    "single_core_action",
    "brand_causal_role",
    "start_action_end",
    "world_rules",
    "continuity_logic",
    "sound_edit_logic",
)
SENSITIVE_CLAIM_TYPES = {
    "algorithm",
    "parameter",
    "timing",
    "capability",
    "product_ownership",
}
MAX_MATCH_FRAME_BYTES = 64 * 1024 * 1024
TRUSTED_MATCH_CUT_READBACK_REQUIRED = "trusted_match_cut_visual_readback_required"
TRUSTED_CLAIM_ADOPTION_REQUIRED = "sensitive_claim_value_requires_adco_host_adoption"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_dimensions(source: Path | bytes) -> tuple[int, int] | None:
    """Recognize canonical PNG frame evidence; every other byte stream fails closed."""
    data = source if isinstance(source, bytes) else source.read_bytes()
    if len(data) >= 33 and data[:8] == b"\x89PNG\r\n\x1a\n":
        offset = 8
        dimensions: tuple[int, int] | None = None
        scanline_bytes: int | None = None
        compressed = bytearray()
        saw_iend = False
        phase = "ihdr"
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            kind = data[offset + 4 : offset + 8]
            chunk_end = offset + 12 + length
            if chunk_end > len(data):
                return None
            payload = data[offset + 8 : offset + 8 + length]
            recorded_crc = int.from_bytes(data[offset + 8 + length : chunk_end], "big")
            if zlib.crc32(kind + payload) & 0xFFFFFFFF != recorded_crc:
                return None
            if phase == "ihdr" and (kind != b"IHDR" or length != 13):
                return None
            if kind == b"IHDR":
                if phase != "ihdr":
                    return None
                width, height = struct.unpack(">II", payload[:8])
                if width <= 0 or height <= 0:
                    return None
                bit_depth, color_type, compression, filter_method, interlace = payload[8:13]
                # Match Cut uses a deliberately narrow canonical evidence
                # profile: 8-bit RGB/RGBA, non-interlaced, no ancillary chunks.
                channels = {2: 3, 6: 4}.get(color_type)
                if (
                    channels is None
                    or bit_depth != 8
                    or compression != 0
                    or filter_method != 0
                    or interlace != 0
                ):
                    return None
                row_payload = (width * channels * bit_depth + 7) // 8
                scanline_bytes = 1 + row_payload
                if scanline_bytes * height > 256 * 1024 * 1024:
                    return None
                dimensions = (width, height)
                phase = "idat"
            elif kind == b"IDAT":
                if phase not in {"idat", "idat_continuation"}:
                    return None
                compressed.extend(payload)
                phase = "idat_continuation"
            elif kind == b"IEND":
                if phase != "idat_continuation" or length != 0:
                    return None
                saw_iend = True
                offset = chunk_end
                break
            else:
                return None
            offset = chunk_end
        if (
            not saw_iend
            or offset != len(data)
            or dimensions is None
            or scanline_bytes is None
            or not compressed
        ):
            return None
        try:
            expected = scanline_bytes * dimensions[1]
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(bytes(compressed), expected + 1)
            if decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
                return None
            decoded += decoder.flush()
        except zlib.error:
            return None
        if len(decoded) != expected:
            return None
        if any(decoded[offset] > 4 for offset in range(0, expected, scanline_bytes)):
            return None
        return dimensions
    # JPEG/WebP evidence must first be transcoded to a verified PNG by the
    # existing asset-intake path; this boundary intentionally has no permissive
    # header-only fallback.
    return None


def stable_file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
    )


def read_contained_frame(
    base_dir: Path,
    value: str,
    *,
    _after_directories_hook: Callable[[], None] | None = None,
) -> tuple[bytes, tuple[int, int]] | None:
    if value != value.strip() or "\\" in value:
        return None
    raw_parts = value.split("/")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not raw_parts
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        return None
    try:
        base_before = os.stat(base_dir, follow_symlinks=False)
    except OSError:
        return None
    if not stat.S_ISDIR(base_before.st_mode) or stat.S_ISLNK(base_before.st_mode):
        return None
    flags_directory = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    flags_file = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        root_fd = os.open(base_dir, flags_directory)
    except OSError:
        return None
    directory_fds = [root_fd]
    directory_bindings: list[tuple[int, str, int, tuple[int, int]]] = []
    try:
        root_opened = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(root_opened.st_mode)
            or (root_opened.st_dev, root_opened.st_ino)
            != (base_before.st_dev, base_before.st_ino)
        ):
            return None
        current_fd = root_fd
        for part in raw_parts[:-1]:
            try:
                before = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            except OSError:
                return None
            if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode):
                return None
            try:
                child_fd = os.open(part, flags_directory, dir_fd=current_fd)
            except OSError:
                return None
            directory_fds.append(child_fd)
            opened = os.fstat(child_fd)
            linked = os.stat(part, dir_fd=current_fd, follow_symlinks=False)
            if (
                (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
                or (linked.st_dev, linked.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                return None
            directory_bindings.append(
                (
                    current_fd,
                    part,
                    child_fd,
                    (opened.st_dev, opened.st_ino),
                )
            )
            current_fd = child_fd
        if _after_directories_hook is not None:
            _after_directories_hook()
        name = raw_parts[-1]
        try:
            before = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
        except OSError:
            return None
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > MAX_MATCH_FRAME_BYTES
        ):
            return None
        try:
            file_fd = os.open(name, flags_file, dir_fd=current_fd)
        except OSError:
            return None
        try:
            opened = os.fstat(file_fd)
            if stable_file_identity(before) != stable_file_identity(opened):
                return None
            with os.fdopen(file_fd, "rb", closefd=False) as handle:
                data = handle.read(MAX_MATCH_FRAME_BYTES + 1)
            after = os.fstat(file_fd)
            linked = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
            try:
                base_linked = os.stat(base_dir, follow_symlinks=False)
            except OSError:
                return None
            directory_chain_matches = True
            for parent_fd, part, child_fd, identity in reversed(
                directory_bindings
            ):
                try:
                    child_opened = os.fstat(child_fd)
                    child_linked = os.stat(
                        part, dir_fd=parent_fd, follow_symlinks=False
                    )
                except OSError:
                    directory_chain_matches = False
                    break
                if (
                    not stat.S_ISDIR(child_opened.st_mode)
                    or not stat.S_ISDIR(child_linked.st_mode)
                    or (child_opened.st_dev, child_opened.st_ino) != identity
                    or (child_linked.st_dev, child_linked.st_ino) != identity
                ):
                    directory_chain_matches = False
                    break
            if (
                len(data) != before.st_size
                or len(data) > MAX_MATCH_FRAME_BYTES
                or stable_file_identity(opened) != stable_file_identity(after)
                or stable_file_identity(after) != stable_file_identity(linked)
                or (base_linked.st_dev, base_linked.st_ino)
                != (root_opened.st_dev, root_opened.st_ino)
                or not directory_chain_matches
            ):
                return None
            return data, (opened.st_dev, opened.st_ino)
        finally:
            os.close(file_fd)
    finally:
        for descriptor in reversed(directory_fds):
            os.close(descriptor)


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number == number and abs(number) != float("inf") else None


def point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, dict):
        return None
    x, y = finite_number(value.get("x")), finite_number(value.get("y"))
    if x is None or y is None or not (0 <= x <= 1 and 0 <= y <= 1):
        return None
    return x, y


def computed_match(field: str, departure: Any, arrival: Any) -> bool:
    if field == "geometry":
        if not isinstance(departure, dict) or not isinstance(arrival, dict):
            return False
        d_ratio = finite_number(departure.get("aspect_ratio"))
        a_ratio = finite_number(arrival.get("aspect_ratio"))
        d_rotation = finite_number(departure.get("rotation_deg"))
        a_rotation = finite_number(arrival.get("rotation_deg"))
        return (
            None not in {d_ratio, a_ratio, d_rotation, a_rotation}
            and abs(d_ratio - a_ratio) <= 0.05
            and abs(d_rotation - a_rotation) <= 5.0
        )
    if field in {"subject_position", "visual_anchor"}:
        left, right = point(departure), point(arrival)
        return left is not None and right is not None and max(
            abs(left[0] - right[0]), abs(left[1] - right[1])
        ) <= 0.05
    if field == "direction":
        return (
            isinstance(departure, str)
            and isinstance(arrival, str)
            and departure.strip().casefold() in {"left", "right", "up", "down", "in", "out"}
            and departure.strip().casefold() == arrival.strip().casefold()
        )
    if field in {"subject_size", "speed"}:
        left, right = finite_number(departure), finite_number(arrival)
        if left is None or right is None or left < 0 or right < 0:
            return False
        tolerance = 0.1 if field == "subject_size" else 0.2 * max(left, right, 1e-9)
        return abs(left - right) <= tolerance
    return False


def validate_match_cut(record: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    failures: list[str] = []
    evidence_hashes: dict[str, str] = {}
    identities: set[tuple[int, int]] = set()
    frames = record.get("frames")
    if not isinstance(frames, dict):
        frames = {}
    for frame_id in ("departure", "arrival"):
        value = frames.get(frame_id)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"frame_evidence_missing:{frame_id}")
            continue
        evidence = read_contained_frame(base_dir, value)
        if evidence is None:
            failures.append(f"frame_evidence_invalid:{frame_id}")
            continue
        data, identity = evidence
        if image_dimensions(data) is None:
            failures.append(f"frame_evidence_not_recognized_image:{frame_id}")
            continue
        if identity in identities:
            failures.append("frame_evidence_not_independent")
        identities.add(identity)
        evidence_hashes[frame_id] = hashlib.sha256(data).hexdigest()

    comparisons = record.get("comparisons")
    if not isinstance(comparisons, dict):
        comparisons = {}
    for field in MATCH_FIELDS:
        comparison = comparisons.get(field)
        if not isinstance(comparison, dict):
            failures.append(f"comparison_missing:{field}")
            continue
        for endpoint in ("departure", "arrival"):
            value = comparison.get(endpoint)
            if value is None or value == "" or value == [] or value == {}:
                failures.append(f"comparison_value_missing:{field}:{endpoint}")
        if not computed_match(field, comparison.get("departure"), comparison.get("arrival")):
            failures.append(f"comparison_not_comparable:{field}")

    requested = record.get("status")
    if requested == "verified":
        failures.append(TRUSTED_MATCH_CUT_READBACK_REQUIRED)
    status = "unverified"
    return {"status": status, "failures": failures, "evidence_hashes": evidence_hashes}


def validate_pending_claims(
    claims: list[dict[str, Any]], evidence_root: Path | None = None
) -> list[str]:
    failures: list[str] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            failures.append(f"invalid_claim:{index}")
            continue
        claim_type = claim.get("claim_type")
        if claim_type not in SENSITIVE_CLAIM_TYPES:
            failures.append(f"unknown_claim_type:{index}")
        supplied = claim.get("value") not in (None, "", [], {})
        if supplied:
            # A local file plus caller-authored owner/ref strings cannot grant DIR
            # authority over client facts. The primary ADCO/host must adopt a
            # hash-bound claim record outside this payload before a value is used.
            failures.append(f"{TRUSTED_CLAIM_ADOPTION_REQUIRED}:{index}:{claim_type}")
        if claim.get("tier") not in {"L1", "L2", "L3"}:
            failures.append(f"invalid_claim_tier:{index}")
    return failures


def validate_frame_content(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(f"invalid_frame_row:{index}")
            continue
        missing = [field for field in FRAME_CONTENT_FIELDS if field not in row]
        if missing:
            failures.append(f"frame_fields_missing:{index}:{','.join(missing)}")
            continue
        storyline = row["storyline"]
        if not isinstance(storyline, dict) or not all(
            isinstance(storyline.get(field), str) and storyline[field].strip()
            for field in ("proof", "bridge_to_next")
        ):
            failures.append(f"storyline_is_not_proof_and_bridge:{index}")
        if not isinstance(row["view"], str) or not row["view"].strip():
            failures.append(f"view_missing:{index}")
    return failures


def validate_studio_foundation(foundation: dict[str, Any]) -> list[str]:
    return [
        f"studio_foundation_missing:{field}"
        for field in FOUNDATION_FIELDS
        if foundation.get(field) in (None, "", [], {})
    ]


def runtime_agents_nonwrite_test() -> list[str]:
    failures: list[str] = []
    fixture = ROOT / "tests/fixtures/prompt-system/valid/minimal-character-scene-10s.json"
    scenarios = {
        "director_room": [sys.executable, str(ROOT / "scripts/dircreative_director_harness_audit.py"), "--route", "$dircreative 开发完整品牌片"],
        "storyboard": [sys.executable, str(ROOT / "scripts/dircreative_route.py"), "$dircreative 为品牌片写九宫格故事板"],
        "prompt": [sys.executable, str(ROOT / "scripts/dircreative_prompt_compiler.py"), "validate", str(fixture), "--skip-project-file-check"],
        "goal": [sys.executable, str(ROOT / "scripts/dircreative_goal_autorun_audit.py")],
        "worker_dispatch": [sys.executable, str(ROOT / "scripts/dircreative_second_level_dispatch_audit.py")],
        "live_acceptance": [sys.executable, str(ROOT / "scripts/dircreative_acceptance_preflight.py")],
    }
    with tempfile.TemporaryDirectory(prefix="dircreative-agents-nonwrite-") as raw:
        project = Path(raw)
        root_agents = project / "AGENTS.md"
        child_agents = project / "AD-creative" / "AGENTS.md"
        child_agents.parent.mkdir()
        root_agents.write_text("# Root policy\n\nkeep root\n", encoding="utf-8")
        child_agents.write_text("# ADCO policy\n\nkeep child\n", encoding="utf-8")
        before = {path: digest(path) for path in (root_agents, child_agents)}
        old_cwd = Path.cwd()
        try:
            os.chdir(project)
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            for scenario, command in scenarios.items():
                result = subprocess.run(
                    command,
                    cwd=project,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=45,
                    check=False,
                )
                if result.returncode != 0:
                    failures.append(f"runtime_scenario_failed:{scenario}:exit={result.returncode}")
                if any(digest(path) != before[path] for path in before):
                    failures.append(f"runtime_wrote_agents:{scenario}")
        finally:
            os.chdir(old_cwd)
        if list(project.glob("AGENTS.dircreative.proposed.md")):
            failures.append("runtime_created_agents_proposal")

    allowed_fixture_or_writer = {
        "dircreative_project_agents.py",
        "dircreative_live_model_eval.py",
        "dircreative_workspace.py",
        "validate_project.py",
        Path(__file__).name,
    }
    write_tokens = ("write_text(", "write_bytes(", "atomic_write_text(", "open(")
    for path in sorted((ROOT / "scripts").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "AGENTS.md" not in text or path.name in allowed_fixture_or_writer:
            continue
        if any(token in text for token in write_tokens):
            failures.append(f"unapproved_agents_write_surface:{path.name}")
    return failures


def self_test() -> tuple[bool, dict[str, Any]]:
    failures: list[str] = []
    controls: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="dircreative-match-cut-") as raw:
        base = Path(raw)
        def png_container(width: int, height: int, raw_scanlines: bytes) -> bytes:
            signature = b"\x89PNG\r\n\x1a\n"
            def chunk(kind: bytes, payload: bytes) -> bytes:
                return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
            return signature + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw_scanlines)) + chunk(b"IEND", b"")
        def png(pixel: bytes) -> bytes:
            return png_container(1, 1, b"\x00" + pixel)
        (base / "departure.png").write_bytes(png(b"\x00\x00\x00"))
        (base / "arrival.png").write_bytes(png(b"\xff\xff\xff"))
        comparisons = {
            "geometry": {"departure": {"aspect_ratio": 1.78, "rotation_deg": 0}, "arrival": {"aspect_ratio": 1.77, "rotation_deg": 2}},
            "subject_position": {"departure": {"x": 0.5, "y": 0.5}, "arrival": {"x": 0.52, "y": 0.49}},
            "subject_size": {"departure": 0.45, "arrival": 0.5},
            "direction": {"departure": "right", "arrival": "right"},
            "speed": {"departure": 1.0, "arrival": 1.1},
            "visual_anchor": {"departure": {"x": 0.25, "y": 0.3}, "arrival": {"x": 0.27, "y": 0.32}},
        }
        valid = validate_match_cut(
            {
                "status": "verified",
                "frames": {"departure": "departure.png", "arrival": "arrival.png"},
                "comparisons": comparisons,
            },
            base,
        )
        controls["match_cut_requires_trusted_visual_readback"] = (
            valid["status"] == "unverified"
            and TRUSTED_MATCH_CUT_READBACK_REQUIRED in valid["failures"]
        )
        missing_first = validate_match_cut(
            {
                "status": "verified",
                "frames": {"arrival": "arrival.png"},
                "comparisons": comparisons,
            },
            base,
        )
        controls["match_cut_missing_first_frame_unverified"] = (
            missing_first["status"] == "unverified"
            and "frame_evidence_missing:departure" in missing_first["failures"]
        )
        (base / "fake.png").write_bytes(b"not-an-image")
        fake = validate_match_cut(
            {
                "status": "verified",
                "frames": {"departure": "fake.png", "arrival": "arrival.png"},
                "comparisons": {field: {**value, "comparable": True} for field, value in comparisons.items()},
            },
            base,
        )
        controls["match_cut_rejects_fake_image_and_self_attestation"] = (
            fake["status"] == "unverified"
            and "frame_evidence_not_recognized_image:departure" in fake["failures"]
        )
        (base / "truncated.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1, 1)
        )
        truncated = validate_match_cut(
            {
                "status": "verified",
                "frames": {"departure": "truncated.png", "arrival": "arrival.png"},
                "comparisons": comparisons,
            },
            base,
        )
        controls["match_cut_rejects_truncated_png"] = (
            truncated["status"] == "unverified"
            and "frame_evidence_not_recognized_image:departure" in truncated["failures"]
        )
        (base / "fake-decodable-header.png").write_bytes(
            png_container(1920, 1080, b"x")
        )
        wrong_scanlines = validate_match_cut(
            {
                "status": "verified",
                "frames": {"departure": "fake-decodable-header.png", "arrival": "arrival.png"},
                "comparisons": comparisons,
            },
            base,
        )
        controls["match_cut_rejects_wrong_png_scanlines"] = (
            wrong_scanlines["status"] == "unverified"
            and "frame_evidence_not_recognized_image:departure" in wrong_scanlines["failures"]
        )
        def raw_png(ihdr: bytes, raw_scanlines: bytes) -> bytes:
            signature = b"\x89PNG\r\n\x1a\n"
            def chunk(kind: bytes, payload: bytes) -> bytes:
                return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
            return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw_scanlines)) + chunk(b"IEND", b"")
        (base / "indexed-without-palette.png").write_bytes(
            raw_png(struct.pack(">IIBBBBB", 1, 1, 8, 3, 0, 0, 0), b"\x00\x00")
        )
        indexed = validate_match_cut(
            {
                "status": "verified",
                "frames": {"departure": "indexed-without-palette.png", "arrival": "arrival.png"},
                "comparisons": comparisons,
            },
            base,
        )
        controls["match_cut_rejects_noncanonical_indexed_png"] = (
            indexed["status"] == "unverified"
            and "frame_evidence_not_recognized_image:departure" in indexed["failures"]
        )
        mismatched = {field: dict(value) for field, value in comparisons.items()}
        mismatched["direction"] = {"departure": "left", "arrival": "right", "comparable": True}
        mismatch = validate_match_cut(
            {"status": "verified", "frames": {"departure": "departure.png", "arrival": "arrival.png"}, "comparisons": mismatched},
            base,
        )
        controls["match_cut_computes_endpoint_comparability"] = (
            mismatch["status"] == "unverified"
            and "comparison_not_comparable:direction" in mismatch["failures"]
        )

        containment_root = base / "containment-root"
        containment_root.mkdir()
        (containment_root / "arrival.png").write_bytes(png(b"\xff\xff\xff"))
        (base / "outside.png").write_bytes(png(b"\x11\x22\x33"))
        escaped = validate_match_cut(
            {
                "status": "verified",
                "frames": {"departure": "../outside.png", "arrival": "arrival.png"},
                "comparisons": comparisons,
            },
            containment_root,
        )
        controls["match_cut_rejects_dotdot_evidence_escape"] = (
            escaped["status"] == "unverified"
            and "frame_evidence_invalid:departure" in escaped["failures"]
        )
        symlink_escape = containment_root / "escape"
        symlink_escape.symlink_to(base, target_is_directory=True)
        linked = validate_match_cut(
            {
                "status": "verified",
                "frames": {"departure": "escape/outside.png", "arrival": "arrival.png"},
                "comparisons": comparisons,
            },
            containment_root,
        )
        controls["match_cut_rejects_intermediate_symlink_escape"] = (
            linked["status"] == "unverified"
            and "frame_evidence_invalid:departure" in linked["failures"]
        )
        race_root = base / "directory-race-root"
        inside = race_root / "inside"
        inside.mkdir(parents=True)
        original_bytes = png(b"\x44\x55\x66")
        replacement_bytes = png(b"\x77\x88\x99")
        (inside / "frame.png").write_bytes(original_bytes)
        moved_out = base / "moved-out-inside"

        def move_intermediate_directory() -> None:
            inside.rename(moved_out)
            inside.mkdir()
            (inside / "frame.png").write_bytes(replacement_bytes)

        raced = read_contained_frame(
            race_root,
            "inside/frame.png",
            _after_directories_hook=move_intermediate_directory,
        )
        controls["match_cut_rejects_moved_intermediate_directory"] = raced is None

    inferred_claims = [
        {"tier": "L2", "claim_type": claim_type, "value": "creative guess"}
        for claim_type in sorted(SENSITIVE_CLAIM_TYPES)
    ]
    claim_failures = validate_pending_claims(inferred_claims)
    controls["all_sensitive_creative_claims_rejected"] = len(claim_failures) == len(SENSITIVE_CLAIM_TYPES)
    controls["pending_claims_without_values_allowed"] = not validate_pending_claims(
        [
            {"tier": "L1", "claim_type": claim_type, "value": None}
            for claim_type in sorted(SENSITIVE_CLAIM_TYPES)
        ]
    )
    controls["claim_evidence_ref_must_resolve"] = bool(
        validate_pending_claims(
            [
                {
                    "tier": "L1",
                    "claim_type": "timing",
                    "value": "one day",
                    "evidence_owner": "client",
                    "evidence_ref": "missing-evidence.json",
                }
            ]
        )
    )
    with tempfile.TemporaryDirectory(prefix="dircreative-claim-boundary-") as claim_raw:
        claim_root = Path(claim_raw)
        (claim_root / "unrelated.txt").write_text("hello world\n", encoding="utf-8")
        unrelated_failures = validate_pending_claims(
            [
                {
                    "tier": "L1",
                    "claim_type": "timing",
                    "value": "same-day delivery",
                    "evidence_owner": "client",
                    "evidence_ref": "unrelated.txt",
                }
            ],
            evidence_root=claim_root,
        )
    controls["local_evidence_cannot_authorize_sensitive_claim"] = any(
        failure.startswith(TRUSTED_CLAIM_ADOPTION_REQUIRED)
        for failure in unrelated_failures
    )
    controls["frame_content_columns_separated"] = not validate_frame_content(
        [
            {
                "view": "卖家合上杂乱页面",
                "storyline": {"proof": "人物作出单一选择", "bridge_to_next": "进入品牌承接"},
                "actual_super": None,
                "ui_data": None,
                "proposal_brand_line": "从第一步开始",
            }
        ]
    )
    controls["camera_action_cannot_replace_storyline"] = bool(
        validate_frame_content(
            [
                {
                    "view": "推近产品",
                    "storyline": "镜头向前推进",
                    "actual_super": None,
                    "ui_data": None,
                    "proposal_brand_line": None,
                }
            ]
        )
    )
    complete_foundation = {field: f"locked-{field}" for field in FOUNDATION_FIELDS}
    controls["studio_foundation_complete"] = not validate_studio_foundation(complete_foundation)
    incomplete_foundation = dict(complete_foundation)
    incomplete_foundation.pop("brand_causal_role")
    controls["studio_foundation_blocks_matrix_when_incomplete"] = bool(
        validate_studio_foundation(incomplete_foundation)
    )
    agents_failures = runtime_agents_nonwrite_test()
    controls["runtime_agents_nonwrite"] = not agents_failures
    failures.extend(agents_failures)
    failures.extend(key for key, passed in controls.items() if not passed)
    return not failures, {"status": "PASS" if not failures else "FAIL", "controls": controls, "failures": failures}


def main() -> int:
    ok, report = self_test()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"DIRCREATIVE_DELIVERY_BOUNDARY_AUDIT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
