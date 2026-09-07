#!/usr/bin/env python3
"""Fail closed before compiling a DIR narrative film-frame specification.

This is deliberately a thin boundary around the installed Jingzao validator and
compiler.  It does not produce a second prompt format or alter a specification.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from dircreative_verify_release import read_relative_regular_file_once
from dircreative_visual_asset_jingzao_handoff import isolated_python_command, run_json_command
from dircreative_visual_asset_jingzao_handoff import provider_review_approved, provider_review_ready


MAX_SPEC_BYTES = 4 * 1024 * 1024


def trusted_provider_roots() -> tuple[Path, ...]:
    return (
        Path.home() / ".codex/skills/jingzao-image-forge",
        Path.home() / ".agents/skills/jingzao-image-forge",
        Path.home() / ".skillshub/jingzao-image-forge",
    )


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@contextlib.contextmanager
def spec_snapshot(source_path: Path, payload: bytes):
    """Place immutable bytes beside the source so relative attachment refs keep meaning."""
    descriptor, raw_name = tempfile.mkstemp(
        prefix=f".{source_path.stem}.narrative-", suffix=source_path.suffix, dir=source_path.parent
    )
    snapshot = Path(raw_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        yield snapshot
    finally:
        snapshot.unlink(missing_ok=True)


def read_project_spec(project_root: Path, relative: str) -> tuple[dict[str, Any] | None, bytes | None, str | None]:
    try:
        payload = read_relative_regular_file_once(
            project_root, relative, max_bytes=MAX_SPEC_BYTES, label="narrative spec"
        )
        value = json.loads(payload.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None, "spec_file_invalid"
    if not isinstance(value, dict):
        return None, None, "spec_json_object_required"
    return value, payload, None


def narrative_errors(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    direction = spec.get("direction")
    cinematic = spec.get("cinematic")
    if not isinstance(direction, dict) or direction.get("deliverable") != "narrative_film_frame":
        errors.append("narrative_deliverable_required")
    if not isinstance(cinematic, dict) or cinematic.get("profile") != "narrative_film_frame":
        errors.append("cinematic_profile_required")
    return errors


def output_spec_errors(value: Any, frames: list[dict[str, Any]]) -> list[str]:
    """Check the two Jingzao output envelopes without creating a DIR envelope."""
    expected = {(item.get("id"), item.get("shot_id")) for item in frames if isinstance(item, dict)}
    if len(expected) != len(frames) or any(not nonempty(frame_id) or not nonempty(shot_id) for frame_id, shot_id in expected):
        return ["expected_frame_coverage_invalid"]
    if isinstance(value, dict) and value.get("visual_generation_spec") == "1.0":
        if len(frames) != 1:
            return ["output_spec_frame_coverage_mismatch"]
        entries = [{"id": frames[0]["id"], "shot_id": frames[0]["shot_id"], "spec": value}]
    elif isinstance(value, dict) and value.get("production_manifest") == "1.0" and isinstance(value.get("frames"), list):
        entries = value["frames"]
    else:
        return ["output_spec_envelope_invalid"]
    actual: set[tuple[Any, Any]] = set()
    errors: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not nonempty(entry.get("id")) or not nonempty(entry.get("shot_id")) or not isinstance(entry.get("spec"), dict):
            errors.append("output_spec_frame_invalid")
            continue
        pair = (entry["id"], entry["shot_id"])
        if pair in actual:
            errors.append("output_spec_frame_duplicate")
            continue
        actual.add(pair)
        errors.extend(f"output_spec_{entry['id']}_{error}" for error in narrative_errors(entry["spec"]))
    if actual != expected:
        errors.append("output_spec_frame_coverage_mismatch")
    return errors


def bound_output_spec_errors(
    root: Path,
    binding: dict[str, Any],
    frames: list[dict[str, Any]],
    *,
    provider_root: Path | None = None,
) -> list[str]:
    value, payload, error = read_project_spec(root, binding.get("relative_path", ""))
    if error or payload is None or sha256(payload) != binding.get("sha256"):
        return ["narrative_output_spec_invalid_or_changed"]
    expected = [{"id": frame.get("frame_id"), "shot_id": frame.get("shot_id")} for frame in frames]
    errors = output_spec_errors(value, expected)
    if errors:
        return errors
    provider, provider_error = resolve_provider(provider_root, root, trusted_roots=(provider_root,) if provider_root else None)
    if provider_error or provider is None:
        return [provider_error or "provider_root_untrusted_or_overlaps_artifact_root"]
    manifest_relative = binding.get("prompt_manifest_relative_path")
    manifest_sha = binding.get("prompt_manifest_sha256")
    manifest, manifest_bytes, manifest_error = read_project_spec(root, manifest_relative)
    if manifest_error or manifest_bytes is None or sha256(manifest_bytes) != manifest_sha:
        return ["narrative_prompt_manifest_invalid_or_changed"]
    prompts = manifest.get("frame_prompts") if isinstance(manifest, dict) else None
    if not isinstance(prompts, list):
        return ["narrative_prompt_manifest_invalid_or_changed"]
    prompt_by_id = {item.get("frame_id"): item for item in prompts if isinstance(item, dict)}
    if set(prompt_by_id) != {item["id"] for item in expected} or len(prompt_by_id) != len(prompts):
        return ["narrative_prompt_manifest_coverage_mismatch"]
    if isinstance(value, dict) and value.get("visual_generation_spec") == "1.0":
        entries = [{"id": expected[0]["id"], "spec": value}]
    else:
        entries = value["frames"]
    capsule = binding.get("style_capsule")
    capsule_bytes = None
    if capsule is not None:
        if not isinstance(capsule, dict) or set(capsule) != {"relative_path", "sha256"}:
            return ["narrative_style_capsule_binding_invalid"]
        try:
            capsule_bytes = read_relative_regular_file_once(root, capsule["relative_path"], max_bytes=MAX_SPEC_BYTES, label="narrative style capsule")
        except (OSError, ValueError):
            return ["narrative_style_capsule_invalid_or_changed"]
        if sha256(capsule_bytes) != capsule["sha256"]:
            return ["narrative_style_capsule_invalid_or_changed"]
    output_path = root / binding["relative_path"]
    for entry in entries:
        frame_id, spec = entry["id"], entry["spec"]
        prompt_entry = prompt_by_id.get(frame_id, {})
        declared_review = prompt_entry.get("prompt_review") if isinstance(prompt_entry, dict) else None
        approve_review = provider_review_approved(declared_review)
        compiled, _, compile_error = compile_snapshot(
            provider,
            output_path,
            json.dumps(spec, ensure_ascii=False, separators=(",", ":")).encode(),
            approve_review=approve_review,
            style_capsule=capsule_bytes,
        )
        if compile_error or not isinstance(compiled, dict) or not nonempty(compiled.get("prompt")):
            errors.append(f"narrative_provider_compile_failed:{frame_id}")
            continue
        review = compiled.get("prompt_review")
        review_status = review.get("status") if isinstance(review, dict) else None
        approved_scope = review.get("approval_scope") if isinstance(review, dict) else None
        if not provider_review_ready(review):
            errors.append(f"narrative_provider_prompt_review_not_ready:{frame_id}")
            continue
        prompt = prompt_entry.get("prompt") if isinstance(prompt_entry, dict) else None
        if review_status == "approved" and review != declared_review:
            errors.append(f"narrative_prompt_review_replay_mismatch:{frame_id}")
            continue
        if compiled.get("prompt") != prompt or sha256(str(prompt).encode()) != prompt_entry.get("prompt_sha256"):
            errors.append(f"narrative_prompt_manifest_replay_mismatch:{frame_id}")
    return errors


def resolve_provider(raw: Path | None, artifact_root: Path, *, trusted_roots: tuple[Path, ...] | None = None) -> tuple[Path | None, str | None]:
    configured_roots = trusted_provider_roots() if trusted_roots is None else trusted_roots
    candidate = raw or configured_roots[0]
    try:
        provider = candidate.resolve(strict=True)
        artifact = artifact_root.resolve(strict=True)
        allowed = {item.resolve(strict=True) for item in configured_roots if item.exists()}
        if provider not in allowed or provider == artifact or artifact in provider.parents or provider in artifact.parents:
            return None, "provider_root_untrusted_or_overlaps_artifact_root"
        for relative in ("SKILL.md", "scripts/validate_spec.py", "scripts/compile_prompt.py", "scripts/reference_delivery.py"):
            target = provider / relative
            if target.is_symlink() or not target.is_file():
                return None, "provider_files_invalid"
            read_relative_regular_file_once(provider, relative, max_bytes=MAX_SPEC_BYTES, label="provider runtime")
    except (OSError, ValueError):
        return None, "provider_root_untrusted_or_overlaps_artifact_root"
    return provider, None


def compile_snapshot(provider: Path, source_path: Path, payload: bytes, *, approve_review: bool = False, style_capsule: bytes | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    with spec_snapshot(source_path, payload) as snapshot:
        validation, error = run_json_command(
            isolated_python_command(provider / "scripts/validate_spec.py", "--json", str(snapshot)),
            cwd=provider, label="jingzao_validate_spec",
        )
        if error or validation != {"valid": True, "errors": []}:
            return None, validation, error or "jingzao_validation_failed"
        args = ["--platform", "openai", "--format", "json"]
        capsule = None
        if style_capsule is not None:
            capsule = snapshot.with_suffix(".style-capsule.json")
            capsule.write_bytes(style_capsule)
            args.extend(["--style-capsule", str(capsule)])
        if approve_review:
            args.append("--approve-review")
        compiled, error = run_json_command(
            isolated_python_command(provider / "scripts/compile_prompt.py", *args, str(snapshot)),
            cwd=provider, label="jingzao_compile_prompt",
        )
        if capsule is not None: capsule.unlink(missing_ok=True)
        return compiled, validation, error


def preflight(project_root: Path, spec_relative: str, provider_root: Path | None = None, *, approve_review: bool = False, style_capsule: str | None = None) -> tuple[int, dict[str, Any]]:
    try:
        root = project_root.resolve(strict=True)
    except OSError:
        return 1, {"status": "blocked", "errors": ["project_root_invalid"]}
    spec, raw_spec, error = read_project_spec(root, spec_relative)
    if error:
        return 1, {"status": "blocked", "errors": [error]}
    assert spec is not None and raw_spec is not None
    errors = narrative_errors(spec)
    if errors:
        return 1, {"status": "blocked", "errors": errors, "input_spec_sha256": sha256(raw_spec)}
    provider, error = resolve_provider(provider_root, root)
    if error:
        return 1, {"status": "blocked", "errors": [error], "input_spec_sha256": sha256(raw_spec)}
    assert provider is not None
    spec_path = root / spec_relative
    capsule_bytes = None
    if style_capsule:
        try: capsule_bytes = read_relative_regular_file_once(root, style_capsule, max_bytes=MAX_SPEC_BYTES, label="narrative style capsule")
        except (OSError, ValueError): return 1, {"status":"blocked","errors":["style_capsule_invalid"]}
    compiled, validation, error = compile_snapshot(provider, spec_path, raw_spec, approve_review=approve_review, style_capsule=capsule_bytes)
    review = compiled.get("prompt_review", {}).get("status") if isinstance(compiled, dict) else None
    if error or not isinstance(compiled, dict) or not nonempty(compiled.get("prompt")) or review not in {"ready", "approved"}:
        return 1, {"status": "blocked", "errors": [error or "jingzao_compilation_not_ready"], "input_spec_sha256": sha256(raw_spec), "compiled": compiled}
    if style_capsule and capsule_bytes is not None:
        try:
            reread_capsule = read_relative_regular_file_once(root, style_capsule, max_bytes=MAX_SPEC_BYTES, label="narrative style capsule")
        except (OSError, ValueError):
            reread_capsule = None
        if reread_capsule != capsule_bytes:
            return 1, {"status": "blocked", "errors": ["style_capsule_changed_during_provider_replay"]}
    with spec_snapshot(spec_path, raw_spec) as snapshot:
        reference_delivery, error = run_json_command(
            isolated_python_command(provider / "scripts/reference_delivery.py", str(snapshot), "--target", "codex_imagegen"),
            cwd=provider, label="jingzao_reference_delivery",
        )
    call_plan = reference_delivery.get("imagegen_call_plan") if isinstance(reference_delivery, dict) else None
    if error or not isinstance(reference_delivery, dict) or reference_delivery.get("valid") is not True or not isinstance(call_plan, dict) or call_plan.get("status") != "ready":
        return 1, {"status": "blocked", "errors": [error or "jingzao_references_not_ready"], "input_spec_sha256": sha256(raw_spec), "compiled": compiled, "reference_delivery": reference_delivery}
    try:
        _, reread, reread_error = read_project_spec(root, spec_relative)
    except OSError:
        reread, reread_error = None, "spec_file_invalid"
    if reread_error or reread != raw_spec:
        return 1, {"status": "blocked", "errors": ["input_spec_changed_during_provider_replay"], "input_spec_sha256": sha256(raw_spec)}
    compiled_bytes = json.dumps(compiled, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return 0, {"status": "compile_only", "verification": "unverified", "generated": False, "approval_scope": compiled.get("prompt_review", {}).get("approval_scope"), "input_spec_sha256": sha256(raw_spec), "prompt_sha256": sha256(compiled["prompt"].encode()), "compiled_sha256": sha256(compiled_bytes), "provider_root": str(provider), "validation": validation, "compiled": compiled, "reference_delivery": reference_delivery, "call_plan": call_plan, "prompt_review_status": review}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run installed Jingzao validation and compilation for a narrative film-frame spec.")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("spec", help="safe project-relative specification path")
    parser.add_argument("--provider-root", type=Path)
    parser.add_argument("--approve-review", action="store_true")
    parser.add_argument("--style-capsule")
    args = parser.parse_args()
    code, result = preflight(args.project_root, args.spec, args.provider_root, approve_review=args.approve_review, style_capsule=args.style_capsule)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
