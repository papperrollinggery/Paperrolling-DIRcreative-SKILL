#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import tempfile
import copy
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]

from dircreative_state_audit import _builtin_schema_errors
from dircreative_verify_release import read_relative_regular_file_once
from dircreative_visual_asset_plan import validate_plan
import dircreative_asset_foundation_pass as asset_foundation_pass


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/film-preproduction/schemas/visual-asset-to-jingzao.schema.json"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_PROVIDER_FILE_BYTES = 1024 * 1024
REQUIRED_REFERENCE_READS = {
    "references/visual-spec.md",
    "references/prompt-compiler.md",
    "references/reference-delivery.md",
    "references/quality-controls.md",
}
REQUIRED_PROVIDER_RUNTIME_FILES = {
    "scripts/validate_spec.py",
    "scripts/compile_prompt.py",
    "scripts/reference_delivery.py",
    "scripts/validate_style_capsule.py",
}
INPUT_SPEC_FIELDS = {
    "contract_id",
    "asset_id",
    "role",
    "truth_sha256",
    "purpose",
    "visual_plan_sha256",
    "operation",
    "asset_foundation_pass",
    "reference_assets",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def default_provider_roots() -> tuple[Path, ...]:
    return (
        Path.home() / ".codex/skills/jingzao-image-forge",
        Path.home() / ".agents/skills/jingzao-image-forge",
        Path.home() / ".skillshub/jingzao-image-forge",
    )


def schema_errors(document: Any) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if Draft202012Validator is None or os.environ.get("DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"):
        return [
            f"schema_error:{error}"
            for error in _builtin_schema_errors(document, schema, schema, "$")
        ]
    validator = Draft202012Validator(schema)
    return [
        "schema_error:"
        + "/".join(str(item) for item in error.absolute_path)
        + f":{error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.absolute_path))
    ]


def read_binding(root: Path, binding: Any, label: str, errors: list[str]) -> bytes | None:
    if not isinstance(binding, dict):
        errors.append(f"{label}_binding_invalid")
        return None
    relative = binding.get("relative_path")
    if not isinstance(relative, str):
        errors.append(f"{label}_path_invalid")
        return None
    try:
        payload = read_relative_regular_file_once(
            root,
            relative,
            max_bytes=MAX_JSON_BYTES,
            label=label,
        )
    except (OSError, ValueError):
        errors.append(f"{label}_file_invalid")
        return None
    if sha256_bytes(payload) != binding.get("sha256"):
        errors.append(f"{label}_hash_mismatch")
    return payload


def load_json_bytes(payload: bytes | None, label: str, errors: list[str]) -> dict[str, Any] | None:
    if payload is None:
        return None
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"{label}_json_invalid")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}_root_invalid")
        return None
    return value


def provider_errors(
    document: dict[str, Any],
    provider_root: Path,
    trusted_provider_roots: tuple[Path, ...] | None,
) -> tuple[list[str], dict[str, bytes]]:
    errors: list[str] = []
    runtime_files: dict[str, bytes] = {}
    try:
        resolved = provider_root.expanduser().resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        return ["jingzao_provider_root_invalid"], runtime_files
    trusted: set[Path] = set()
    for item in trusted_provider_roots or default_provider_roots():
        try:
            candidate = item.expanduser().resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            continue
        if candidate.is_dir():
            trusted.add(candidate)
    if resolved not in trusted:
        return ["jingzao_provider_root_not_trusted"], runtime_files
    try:
        skill_bytes = read_relative_regular_file_once(
            resolved,
            "SKILL.md",
            max_bytes=MAX_PROVIDER_FILE_BYTES,
            label="Jingzao Skill",
        )
    except (OSError, ValueError):
        return ["jingzao_provider_skill_invalid"], runtime_files
    provider = document.get("provider_skill", {})
    if provider.get("skill_id") != "jingzao-image-forge" or provider.get(
        "sha256"
    ) != sha256_bytes(skill_bytes):
        errors.append("jingzao_provider_skill_hash_mismatch")
    reference_reads = document.get("reference_reads", [])
    declared_paths = {
        item.get("relative_path")
        for item in reference_reads
        if isinstance(item, dict)
    }
    if declared_paths != REQUIRED_REFERENCE_READS:
        errors.append("jingzao_reference_read_set_mismatch")
    for item in reference_reads:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            continue
        relative = item["relative_path"]
        try:
            payload = read_relative_regular_file_once(
                resolved,
                relative,
                max_bytes=MAX_PROVIDER_FILE_BYTES,
                label=f"Jingzao reference {relative}",
            )
        except (OSError, ValueError):
            errors.append(f"jingzao_reference_read_invalid:{relative}")
            continue
        if item.get("sha256") != sha256_bytes(payload) or item.get("bytes") != len(payload):
            errors.append(f"jingzao_reference_read_binding_mismatch:{relative}")
    runtime_entries = document.get("provider_runtime_files", [])
    runtime_paths = {
        item.get("relative_path")
        for item in runtime_entries
        if isinstance(item, dict)
    }
    if runtime_paths != REQUIRED_PROVIDER_RUNTIME_FILES:
        errors.append("jingzao_provider_runtime_file_set_mismatch")
    for item in runtime_entries:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            continue
        relative = item["relative_path"]
        try:
            payload = read_relative_regular_file_once(
                resolved,
                relative,
                max_bytes=MAX_PROVIDER_FILE_BYTES,
                label=f"Jingzao runtime {relative}",
            )
        except (OSError, ValueError):
            errors.append(f"jingzao_provider_runtime_file_invalid:{relative}")
            continue
        runtime_files[relative] = payload
        if item.get("sha256") != sha256_bytes(payload) or item.get("bytes") != len(payload):
            errors.append(f"jingzao_provider_runtime_binding_mismatch:{relative}")
    return errors, runtime_files


def run_json_command(
    command: list[str],
    *,
    cwd: Path,
    label: str,
    sandbox_root: Path | None = None,
    allow_unsandboxed_test_replay: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    if sandbox_root is not None:
        sandbox_exec = Path("/usr/bin/sandbox-exec")
        if sys.platform == "darwin" and sandbox_exec.is_file():
            escaped_root = str(sandbox_root.resolve(strict=True)).replace("\\", "\\\\").replace('"', '\\"')
            escaped_home = str(Path.home().resolve()).replace("\\", "\\\\").replace('"', '\\"')
            profile = (
                "(version 1) (allow default) (deny network*) (deny file-write*) "
                f'(allow file-write* (subpath "{escaped_root}")) '
                f'(deny file-read* (subpath "{escaped_home}")) '
                f'(allow file-read* (subpath "{escaped_root}"))'
            )
            command = [str(sandbox_exec), "-p", profile, *command]
        elif not allow_unsandboxed_test_replay:
            return None, f"{label}_sandbox_unavailable"

    def limit_child() -> None:
        for limit, value in (
            (resource.RLIMIT_CPU, 15),
            (resource.RLIMIT_FSIZE, MAX_JSON_BYTES),
            (resource.RLIMIT_AS, 512 * 1024 * 1024),
        ):
            try:
                resource.setrlimit(limit, (value, value))
            except (OSError, ValueError):
                pass

    try:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            proc = subprocess.run(
                command,
                cwd=cwd,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=30,
                check=False,
                env={
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                },
                preexec_fn=limit_child,
            )
            stdout_file.seek(0, os.SEEK_END)
            stdout_size = stdout_file.tell()
            stderr_file.seek(0, os.SEEK_END)
            stderr_size = stderr_file.tell()
            if stdout_size > MAX_JSON_BYTES or stderr_size > MAX_JSON_BYTES:
                return None, f"{label}_output_too_large"
            stdout_file.seek(0)
            stdout_text = stdout_file.read().decode("utf-8", errors="strict")
    except (OSError, subprocess.TimeoutExpired):
        return None, f"{label}_execution_failed"
    except (UnicodeDecodeError, ValueError):
        return None, f"{label}_output_invalid"
    if proc.returncode != 0:
        return None, f"{label}_execution_failed"
    try:
        value = json.loads(stdout_text)
    except json.JSONDecodeError:
        return None, f"{label}_output_invalid"
    if not isinstance(value, dict):
        return None, f"{label}_output_invalid"
    return value, None


def isolated_python_command(script: Path, *args: str) -> list[str]:
    launcher = (
        "import os,runpy,sys;"
        "p=sys.argv[1];"
        "sys.path.insert(0,os.path.dirname(p));"
        "sys.argv=[p,*sys.argv[2:]];"
        "runpy.run_path(p,run_name='__main__')"
    )
    return [sys.executable, "-I", "-c", launcher, str(script), *args]


def validate(
    document: Any,
    *,
    project_root: Path,
    provider_root: Path,
    trusted_provider_roots: tuple[Path, ...] | None = None,
    allow_fixture: bool = False,
    allow_unsandboxed_test_replay: bool = False,
) -> tuple[list[str], str | None]:
    errors = schema_errors(document)
    if errors or not isinstance(document, dict):
        return errors, None
    if document.get("fixture_only") is True and not allow_fixture:
        return ["visual_asset_jingzao_fixture_not_production"], None
    try:
        resolved_project = project_root.expanduser().resolve(strict=True)
        resolved_provider = provider_root.expanduser().resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        return ["visual_asset_project_root_invalid"], None
    if resolved_provider.is_relative_to(resolved_project) or resolved_project.is_relative_to(resolved_provider):
        return ["jingzao_provider_artifact_root_overlap"], None
    provider_validation_errors, runtime_files = provider_errors(
        document, provider_root, trusted_provider_roots
    )
    errors.extend(provider_validation_errors)
    if provider_validation_errors:
        return list(dict.fromkeys(errors)), None

    visual_plan = load_json_bytes(
        read_binding(resolved_project, document["visual_plan"], "visual_plan", errors),
        "visual_plan",
        errors,
    )
    active = document["active_asset"]
    if isinstance(visual_plan, dict):
        plan_errors, _ = validate_plan(copy.deepcopy(visual_plan), base_dir=resolved_project)
        if plan_errors:
            errors.append("visual_asset_plan_snapshot_invalid")
        active_matches = [
            item
            for item in visual_plan.get("assets", [])
            if isinstance(item, dict) and item.get("asset_id") == active["asset_id"]
        ]
        if len(active_matches) != 1:
            errors.append("visual_asset_plan_active_asset_missing_or_ambiguous")
        else:
            plan_asset = active_matches[0]
            if (
                plan_asset.get("role") != active["role"]
                or plan_asset.get("truth_sha256") != active["truth_sha256"]
                or sha256_bytes(str(plan_asset.get("purpose", "")).encode("utf-8"))
                != active["purpose_sha256"]
                or document["visual_plan"]["sha256"] != active["visual_plan_sha256"]
            ):
                errors.append("visual_asset_plan_active_asset_mismatch")

    stack_request_bytes = read_binding(
        resolved_project,
        document["skill_stack_request"],
        "skill_stack_request",
        errors,
    )
    stack_request = load_json_bytes(stack_request_bytes, "skill_stack_request", errors)
    stack = load_json_bytes(
        read_binding(resolved_project, document["skill_stack_receipt"], "skill_stack_receipt", errors),
        "skill_stack_receipt",
        errors,
    )
    stack_intent = stack_request.get("intent") if isinstance(stack_request, dict) else None
    stack_request_text = (
        stack_request.get("request_text") if isinstance(stack_request, dict) else None
    )
    if isinstance(stack_request, dict):
        if (
            set(stack_request) != {"contract_id", "request_text", "intent"}
            or stack_request.get("contract_id") != "visual_asset_skill_stack_request_v1"
            or not isinstance(stack_request_text, str)
            or not isinstance(stack_intent, dict)
            or stack_intent.get("scenario_id") != "visual_asset_compile"
            or stack_intent.get("mode") != "studio"
            or stack_intent.get("route_id") != "film_development"
            or stack_intent.get("media") not in {"still", "image_series", "storyboard"}
        ):
            errors.append("visual_asset_skill_stack_request_invalid")
    if isinstance(stack, dict):
        owner = stack.get("craft_owner", {})
        if (
            stack.get("status") != "ready"
            or stack.get("scenario_id") != "visual_asset_compile"
            or not isinstance(owner, dict)
            or owner.get("skill_id") != "jingzao-image-forge"
            or stack.get("handoff_contract_id") != "visual_asset_to_jingzao_v1"
        ):
            errors.append("visual_asset_skill_stack_receipt_invalid")
        if owner.get("body_sha256") != document["provider_skill"]["sha256"]:
            errors.append("visual_asset_skill_stack_provider_hash_mismatch")

    if isinstance(stack_intent, dict) and isinstance(stack_request_text, str) and isinstance(stack, dict):
        with tempfile.TemporaryDirectory() as raw:
            request_path = Path(raw) / "intent.json"
            request_path.write_text(
                json.dumps(stack_intent, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            replay, replay_error = run_json_command(
                isolated_python_command(
                    ROOT / "scripts/dircreative_skill_stack.py",
                    "select",
                    "--intent",
                    str(request_path),
                    "--request",
                    stack_request_text,
                    "--root",
                    str(provider_root.resolve(strict=True).parent),
                ),
                cwd=ROOT,
                label="visual_asset_skill_stack_replay",
            )
        if replay_error is not None:
            errors.append(replay_error)
        elif replay != stack:
            errors.append("visual_asset_skill_stack_replay_mismatch")

    reference_assets: list[dict[str, Any]] = []
    reference_payloads: dict[str, bytes] = {}
    foundation_source_by_id: dict[str, dict[str, Any]] = {}
    input_spec = load_json_bytes(
        read_binding(resolved_project, document["input_spec"], "input_spec", errors),
        "input_spec",
        errors,
    )
    if isinstance(input_spec, dict):
        if set(input_spec) != INPUT_SPEC_FIELDS or input_spec.get("contract_id") != "dircreative_visual_asset_request_v1":
            errors.append("visual_asset_input_spec_shape_invalid")
        expected = {
            "asset_id": active["asset_id"],
            "role": active["role"],
            "truth_sha256": active["truth_sha256"],
            "visual_plan_sha256": active["visual_plan_sha256"],
            "operation": active["operation"],
        }
        if any(input_spec.get(key) != value for key, value in expected.items()):
            errors.append("visual_asset_input_spec_active_asset_mismatch")
        purpose = input_spec.get("purpose")
        if not isinstance(purpose, str) or sha256_bytes(purpose.encode("utf-8")) != active[
            "purpose_sha256"
        ]:
            errors.append("visual_asset_input_spec_purpose_mismatch")
        foundation = load_json_bytes(
            read_binding(
                resolved_project,
                input_spec.get("asset_foundation_pass"),
                "asset_foundation_pass",
                errors,
            ),
            "asset_foundation_pass",
            errors,
        )
        if isinstance(foundation, dict):
            foundation_source_by_id = {
                str(item.get("asset_id")): item
                for item in foundation.get("source_assets", [])
                if isinstance(item, dict) and isinstance(item.get("asset_id"), str)
            }
            is_design = foundation.get("status") == "in_progress" and bool(foundation.get("planned_asset_ids"))
            if is_design:
                foundation_errors = asset_foundation_pass.validate_design(
                    foundation, artifact_root=resolved_project,
                    asset_id=active["asset_id"], role=active["role"],
                )
            else:
                foundation_errors = asset_foundation_pass.validate(foundation, artifact_root=resolved_project)
            if foundation_errors:
                errors.append("visual_asset_foundation_pass_invalid")
            if (
                (not is_design and (
                    foundation.get("status") != "complete"
                    or foundation.get("compile_gate", {}).get("status") != "allowed"
                    or active["asset_id"] not in foundation.get("canonical_asset_ids", [])
                ))
                or (
                    isinstance(visual_plan, dict)
                    and foundation.get("project_id") != visual_plan.get("project_id")
                )
            ):
                errors.append("visual_asset_foundation_pass_scope_mismatch")
        references = input_spec.get("reference_assets")
        if not isinstance(references, list) or any(
            not isinstance(item, dict)
            or set(item)
            != {
                "input_id",
                "asset_id",
                "role",
                "relative_path",
                "sha256",
                "rights_status",
                "approval_status",
            }
            for item in references
        ):
            errors.append("visual_asset_reference_assets_invalid")
        else:
            reference_assets = references
            input_ids = [item.get("input_id") for item in references]
            source_asset_ids = [item.get("asset_id") for item in references]
            reference_paths = [item.get("relative_path") for item in references]
            if (
                len(input_ids) != len(set(input_ids))
                or len(source_asset_ids) != len(set(source_asset_ids))
                or len(reference_paths) != len(set(reference_paths))
            ):
                errors.append("visual_asset_reference_assets_duplicate")
            for item in references:
                payload = read_binding(
                    resolved_project,
                    item,
                    f"reference_asset:{item.get('input_id')}",
                    errors,
                )
                if payload is not None:
                    reference_payloads[str(item.get("input_id"))] = payload
                source = foundation_source_by_id.get(str(item.get("asset_id")))
                if (
                    source is None
                    or source.get("relative_path") != item.get("relative_path")
                    or source.get("sha256") != item.get("sha256")
                ):
                    errors.append(
                        f"visual_asset_reference_not_in_foundation:{item.get('input_id')}"
                    )
                if item.get("rights_status") not in {
                    "user_provided",
                    "project_owned",
                    "licensed",
                    "public_domain",
                }:
                    errors.append(f"visual_asset_reference_rights_invalid:{item.get('input_id')}")
                expected_approvals = (
                    {"user_locked", "reused_locked"}
                    if isinstance(source, dict) and source.get("source_kind") == "canonical_asset"
                    else {"reference_only_approved"}
                )
                if item.get("approval_status") not in expected_approvals:
                    errors.append(
                        f"visual_asset_reference_approval_invalid:{item.get('input_id')}"
                    )

    output = document["output_spec"]
    spec = load_json_bytes(
        read_binding(resolved_project, output["visual_generation_spec"], "visual_generation_spec", errors),
        "visual_generation_spec",
        errors,
    )
    validation_receipt = load_json_bytes(
        read_binding(resolved_project, output["validation_receipt"], "validation_receipt", errors),
        "validation_receipt",
        errors,
    )
    compiled = load_json_bytes(
        read_binding(
            resolved_project,
            output["compiled_prompt_manifest"],
            "compiled_prompt_manifest",
            errors,
        ),
        "compiled_prompt_manifest",
        errors,
    )
    spec_inputs_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(spec, dict) and isinstance(input_spec, dict):
        if spec.get("intent") != input_spec.get("purpose"):
            errors.append("jingzao_visual_generation_spec_purpose_mismatch")
        allowed_modes = {
            "create": {"create"},
            "reconstruct": {"reconstruct"},
            "edit": {"edit"},
            "restyle": {"restyle"},
            "expand": {"expand"},
            "clean_reset": {"create", "reconstruct"},
        }
        if spec.get("mode") not in allowed_modes.get(active["operation"], set()):
            errors.append("jingzao_visual_generation_spec_operation_mismatch")
        raw_spec_inputs = spec.get("inputs", [])
        if not isinstance(raw_spec_inputs, list) or any(
            not isinstance(item, dict) or item.get("must_attach") is not True
            for item in raw_spec_inputs
        ):
            errors.append("jingzao_visual_generation_spec_unbound_input")
            raw_spec_inputs = []
        required_spec_inputs = raw_spec_inputs
        spec_inputs_by_id = {
            str(item.get("id")): item
            for item in required_spec_inputs
            if isinstance(item.get("id"), str)
        }
        reference_by_id = {
            str(item.get("input_id")): item
            for item in reference_assets
            if isinstance(item.get("input_id"), str)
        }
        if set(spec_inputs_by_id) != set(reference_by_id):
            errors.append("jingzao_visual_generation_spec_reference_set_mismatch")
        else:
            spec_path = resolved_project / output["visual_generation_spec"]["relative_path"]
            for input_id, spec_input in spec_inputs_by_id.items():
                binding = reference_by_id[input_id]
                source_ref = spec_input.get("source_ref")
                try:
                    spec_source = (spec_path.parent / str(source_ref)).resolve(strict=True)
                    expected_source = (
                        resolved_project / str(binding.get("relative_path"))
                    ).resolve(strict=True)
                except (FileNotFoundError, RuntimeError):
                    errors.append(f"jingzao_visual_generation_spec_reference_path_invalid:{input_id}")
                    continue
                if (
                    spec_input.get("type") != "image"
                    or spec_input.get("source_kind") != "local_path"
                    or spec_input.get("role") != binding.get("role")
                    or spec_source != expected_source
                ):
                    errors.append(f"jingzao_visual_generation_spec_reference_binding_mismatch:{input_id}")

    if errors:
        return list(dict.fromkeys(errors)), None

    replay_validation: dict[str, Any] | None = None
    replay_compiled: dict[str, Any] | None = None
    if isinstance(spec, dict) and set(runtime_files) == REQUIRED_PROVIDER_RUNTIME_FILES:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            replay_provider = root / "provider"
            replay_project = root / "project"
            for relative, payload in runtime_files.items():
                target = replay_provider / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            spec_relative = output["visual_generation_spec"]["relative_path"]
            replay_spec = replay_project / spec_relative
            replay_spec.parent.mkdir(parents=True, exist_ok=True)
            replay_spec.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            reference_by_id = {
                str(item.get("input_id")): item
                for item in reference_assets
                if isinstance(item.get("input_id"), str)
            }
            for input_id, item in spec_inputs_by_id.items():
                source_ref = item.get("source_ref")
                source_payload = reference_payloads.get(input_id)
                if source_payload is None:
                    errors.append(f"jingzao_spec_local_input_invalid:{input_id}")
                    continue
                try:
                    replay_input = (replay_spec.parent / str(source_ref)).resolve(strict=False)
                    replay_input.relative_to(replay_project.resolve(strict=True))
                except (RuntimeError, ValueError):
                    errors.append(f"jingzao_spec_replay_input_escape:{input_id}")
                    continue
                replay_input.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with replay_input.open("xb") as handle:
                        handle.write(source_payload)
                except FileExistsError:
                    errors.append(f"jingzao_spec_replay_input_exists:{input_id}")
            if errors:
                return list(dict.fromkeys(errors)), None
            replay_validation, validation_error = run_json_command(
                isolated_python_command(
                    replay_provider / "scripts/validate_spec.py",
                    "--json",
                    str(replay_spec),
                ),
                cwd=replay_provider,
                label="jingzao_validate_spec_replay",
                sandbox_root=root,
                allow_unsandboxed_test_replay=allow_unsandboxed_test_replay,
            )
            if validation_error is not None:
                return [validation_error], None
            if replay_validation != validation_receipt or replay_validation != {"valid": True, "errors": []}:
                return ["jingzao_validation_replay_mismatch"], None
            replay_compiled, compile_error = run_json_command(
                isolated_python_command(
                    replay_provider / "scripts/compile_prompt.py",
                    str(replay_spec),
                    "--platform",
                    "openai",
                    "--format",
                    "json",
                ),
                cwd=replay_provider,
                label="jingzao_compile_prompt_replay",
                sandbox_root=root,
                allow_unsandboxed_test_replay=allow_unsandboxed_test_replay,
            )
        if validation_error is not None:
            errors.append(validation_error)
        if compile_error is not None:
            errors.append(compile_error)
    if replay_validation != validation_receipt or validation_receipt != {"valid": True, "errors": []}:
        errors.append("jingzao_validation_replay_mismatch")
    if replay_compiled != compiled:
        errors.append("jingzao_compilation_replay_mismatch")

    prompt: str | None = None
    if isinstance(replay_compiled, dict):
        compiled = replay_compiled
        candidate = compiled.get("prompt")
        if isinstance(candidate, str) and candidate.strip():
            prompt = candidate
        else:
            errors.append("jingzao_compiled_prompt_missing")
        if compiled.get("prompt_review", {}).get("status") != "ready":
            errors.append("jingzao_prompt_review_not_ready")
        call_plan = compiled.get("imagegen_call_plan", {})
        if call_plan.get("status") != "ready" or call_plan.get("errors") not in ([], None):
            errors.append("jingzao_imagegen_call_plan_not_ready")
        expected_input_ids = sorted(item["input_id"] for item in reference_assets)
        if (
            sorted(call_plan.get("required_input_ids", [])) != expected_input_ids
            or call_plan.get("expected_attachment_count") != len(expected_input_ids)
        ):
            errors.append("jingzao_imagegen_call_plan_reference_mismatch")
    if prompt is None or sha256_bytes(prompt.encode("utf-8")) != output["prompt_sha256"]:
        errors.append("jingzao_compiled_prompt_hash_mismatch")
    delivery = document["delivery_consumption"]
    if delivery.get("consumed_prompt_sha256") != output["prompt_sha256"]:
        errors.append("jingzao_delivery_prompt_hash_mismatch")
    return list(dict.fromkeys(errors)), prompt


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a formal DIR-to-Jingzao visual asset compile handoff.")
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--provider-root", type=Path, default=Path.home() / ".codex/skills/jingzao-image-forge")
    args = parser.parse_args()
    try:
        raw = read_relative_regular_file_once(
            args.handoff.parent.resolve(strict=True),
            args.handoff.name,
            max_bytes=MAX_JSON_BYTES,
            label="visual asset Jingzao handoff",
        )
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        print(json.dumps({"status": "blocked", "errors": ["visual_asset_jingzao_handoff_unreadable"]}))
        return 1
    errors, prompt = validate(
        document,
        project_root=args.project_root,
        provider_root=args.provider_root,
    )
    print(
        json.dumps(
            {
                "status": "ready" if not errors else "blocked",
                "errors": errors,
                "prompt_sha256": sha256_bytes(prompt.encode("utf-8")) if prompt else None,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
