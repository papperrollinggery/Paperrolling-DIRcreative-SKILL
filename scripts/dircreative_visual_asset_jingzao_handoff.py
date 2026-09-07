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
from dircreative_visual_asset_plan import validate_plan, build_candidate_repair_source
from dircreative_storyboard_coverage import resolve_planning_image_target, planning_image_spec_errors
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
REPAIR_PRESERVE_REQUIREMENT = "Change only the listed visible defects in the supplied image. Preserve all other established subject identity, shape, proportions, materials, colors, visual medium and unrequested details."
REPAIR_INTENT = "Edit the attached image using the listed corrections; retain its established visual design."
PROVIDER_REVIEW_SCOPES = {
    "length_and_reference_complexity_only",
    "surface_risk_length_and_reference_complexity",
}


def provider_review_approved(review: Any) -> bool:
    """Accept the provider's documented soft-review scopes, never contamination."""
    if not isinstance(review, dict) or not isinstance(review.get("reasons", []), list):
        return False
    return (
        review.get("status") == "approved" and isinstance(review.get("approval_scope"), str)
        and review.get("approval_scope") in PROVIDER_REVIEW_SCOPES
        and not any(str(reason) == "empty_prompt" or str(reason).startswith("context_residue:")
                    for reason in review.get("reasons", []))
    )


def provider_review_ready(review: Any) -> bool:
    return isinstance(review, dict) and (review.get("status") == "ready" or provider_review_approved(review))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


EDIT_SOURCE_REQUIREMENT = (
    "Preserve the source image's existing view order, framing, poses, lighting and visual medium, "
    "except where a listed edit explicitly changes them."
)


def canonical_asset_role_requirements(asset: dict[str, Any], *, operation: str = "create") -> list[str]:
    """Generation constraints, derived from DIR truth before provider compilation.

    These are ordinary supported Jingzao spec values, not compiler metadata or
    an extra post-compile prompt. Narrative/planning contracts keep their own
    existing compiler and are deliberately outside this foundation helper.
    """
    from dircreative_prompt_compiler import ASSET_ROLE_RULES

    role = asset.get("role")
    if operation == "edit":
        requirements = [EDIT_SOURCE_REQUIREMENT, REPAIR_PRESERVE_REQUIREMENT]
        if role == "character_identity_reference" and asset.get("character_mode") == "headless_safe":
            requirements.append("The left portrait is the only readable face. All four bodies are fully headless, preserving natural hands, wrists, cuffs, rear collar and inner back neckline from the approved headed source.")
        return requirements
    if role != "character_identity_reference":
        return [ASSET_ROLE_RULES[role]] if role in ASSET_ROLE_RULES else []
    mode = asset.get("character_mode", "headed_master")
    if mode not in {"headed_master", "headed_state", "headless_safe"}:
        raise ValueError("character_master_mode_invalid")
    if asset.get("identity_kind", "human") == "nonhuman":
        if mode == "headless_safe":
            raise ValueError("nonhuman_character_mode_invalid")
        requirements = [
            "One physical reference sheet for exactly one recurring nonhuman identity and one appearance state; never combine different entities on this sheet.",
            "One dominant close-up of the entity's head, core, or other declared recognition structure at the far left, readable without turning it into a human face.",
            "Four complete reference views in one horizontal row: front, left side, right side, and back. Keep the same scale, recognizable silhouette, anatomy or structure, material behavior, distinctive features, and declared appearance state in every view.",
            "Use a fully opaque neutral background with readable even lighting; no unrelated person, undeclared prop, text, label, border or watermark.",
        ]
        if mode == "headed_state":
            requirements.append("Derive from the attached approved nonhuman master; change only the declared state and preserve identity, structure, materials and recognition features.")
        return requirements
    requirements = [
        "One physical master sheet for exactly one character identity and one appearance state; never combine different characters on this sheet.",
        "One dominant front-facing crown-to-neck face close-up at the far left, level and readable with both eyes visible.",
        "Four full-body views in one horizontal row after the portrait: front, anatomical left profile and anatomical right profile in either order, and back. Front first and back last; both sides are required and are not mirror substitutes.",
        "The portrait and each full-body subject occupy at least 75% of the saved canvas height; equal body scale, shared ground line, complete head-to-toe framing and separated silhouettes.",
        "Preserve this character's identity, body proportions, hair, garment construction and materials, footwear, anatomical left/right detail placement, and the declared pose and appearance state in every view.",
        "Use a fully opaque neutral background with readable even lighting; no extra identity, undeclared prop, costume variant, text, label, border or watermark.",
    ]
    if mode == "headless_safe":
        requirements[2] = "Four full-body views in one horizontal row after the portrait: front, anatomical left profile, anatomical right profile, and back. Front first and back last; both side profiles are required and are not mirror substitutes."
        requirements.append("The left portrait is the only readable face. All four bodies are fully headless, preserving natural hands, wrists, cuffs, rear collar and inner back neckline from the approved headed source.")
    else:
        requirements.append("All four full-body views are headed, including a complete anatomically readable head and back view.")
    if mode != "headed_master":
        requirements.append("Derive from the attached approved headed master; change only the declared state or headless treatment and preserve all other identity and wardrobe details.")
    return requirements


def known_asset_role_requirements() -> set[str]:
    """Only clauses owned by this compiler; custom artistic constraints are untouched."""
    from dircreative_prompt_compiler import ASSET_ROLE_RULES
    clauses = set(ASSET_ROLE_RULES.values())
    clauses.update([EDIT_SOURCE_REQUIREMENT, REPAIR_PRESERVE_REQUIREMENT])
    # Retire the old fixed profile order when reopening an existing spec.
    clauses.add("Four full-body views in one horizontal row after the portrait: front, anatomical left profile with nose pointing frame-left, anatomical right profile with nose pointing frame-right, and back. Front first and back last; both side profiles are required and are not mirror substitutes.")
    for mode in ("headed_master", "headed_state", "headless_safe"):
        clauses.update(canonical_asset_role_requirements({
            "role": "character_identity_reference", "character_mode": mode,
        }))
    for mode in ("headed_master", "headed_state"):
        clauses.update(canonical_asset_role_requirements({"role": "character_identity_reference", "character_mode": mode, "identity_kind": "nonhuman"}))
    return clauses


def prepare_role_spec(spec: dict[str, Any], asset: dict[str, Any]) -> dict[str, Any]:
    """Apply canonical role constraints to an existing spec without changing its mode/ratio."""
    if not isinstance(spec, dict) or spec.get("intent") not in (
        {asset.get("purpose"), REPAIR_INTENT} if spec.get("mode") == "edit" else {asset.get("purpose")}
    ):
        raise ValueError("visual_asset_spec_purpose_mismatch")
    prepared = copy.deepcopy(spec)
    constraints = prepared.setdefault("constraints", {})
    if not isinstance(constraints, dict):
        raise ValueError("visual_asset_spec_constraints_invalid")
    preserved = constraints.setdefault("must_preserve", [])
    if not isinstance(preserved, list) or not all(isinstance(item, str) for item in preserved):
        raise ValueError("visual_asset_spec_preservation_invalid")
    required = canonical_asset_role_requirements(asset, operation=str(spec.get("mode", "create")))
    if not required:
        return prepared
    known = known_asset_role_requirements()
    constraints["must_preserve"] = list(dict.fromkeys([
        *required, *(item for item in preserved if item not in known),
    ]))
    return prepared


def role_spec_errors(spec: Any, asset: dict[str, Any]) -> list[str]:
    required = canonical_asset_role_requirements(asset, operation=str(spec.get("mode", "create")) if isinstance(spec, dict) else "create")
    if not required:
        return []
    constraints = spec.get("constraints") if isinstance(spec, dict) else None
    preserved = constraints.get("must_preserve") if isinstance(constraints, dict) else None
    if not isinstance(preserved, list) or not all(isinstance(item, str) for item in preserved):
        return ["visual_asset_role_requirements_missing"]
    errors = []
    if any(item not in preserved for item in required):
        errors.append("visual_asset_role_requirements_missing")
    if set(preserved).intersection(known_asset_role_requirements()) - set(required):
        errors.append("visual_asset_role_requirements_stale")
    changes = constraints.get("must_change", [])
    if isinstance(changes, list) and any(item in preserved for item in changes if isinstance(item, str)):
        errors.append("visual_asset_change_preserve_conflict")
    return errors


def candidate_repair_reference(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_id": "candidate-repair-base", "asset_id": binding["asset_id"], "role": "base_edit_source",
        "relative_path": binding["source_image"]["relative_path"], "sha256": binding["source_image"]["sha256"],
        "rights_status": "project_owned", "approval_status": "candidate_repair_only",
    }


def prepare_candidate_repair_spec(
    spec: dict[str, Any], binding: dict[str, Any], *, project_root: Path, output_spec: Path,
) -> dict[str, Any]:
    expected = build_candidate_repair_source(project_root=project_root, visual_plan_binding=binding.get("source_plan"), asset_id=binding.get("asset_id"), changes=binding.get("changes"), base_plan_binding=binding.get("base_plan"))
    if binding != expected:
        raise ValueError("candidate_repair_source_binding_mismatch")
    root = project_root.resolve(strict=True)
    target = output_spec if output_spec.is_absolute() else root / output_spec
    target.relative_to(root)
    plan = json.loads(read_relative_regular_file_once(root, binding["source_plan"]["relative_path"], max_bytes=MAX_JSON_BYTES, label="repair plan"))
    asset = next(item for item in plan["assets"] if item["asset_id"] == binding["asset_id"])
    if spec.get("inputs") not in (None, []):
        raise ValueError("candidate_repair_requires_unambiguous_single_base_spec")
    # A repair is a delta against actual pixels, not another costume/lighting
    # design brief. Keep custom preservation facts, but do not replay create
    # scene, subject poses, render directions or aesthetic routing into it.
    prepared = {key: copy.deepcopy(spec[key]) for key in (
        "visual_generation_spec", "intent", "platform", "language", "canvas", "constraints",
    ) if key in spec}
    prepared["mode"] = "edit"
    prepared = prepare_role_spec(prepared, asset)
    # Stable asset purpose remains in the bound request/plan. Repeating that
    # initial design as the edit's Goal can contradict the accepted source.
    prepared["intent"] = REPAIR_INTENT
    prepared["scene"] = {"summary": "Edit the attached source image using only the listed changes."}
    prepared["render"] = {"artifact_budget": "source_matched"}
    prepared["inputs"] = [{
        "id": "candidate-repair-base", "type": "image", "role": "base_edit_source",
        "source_kind": "local_path", "source_ref": os.path.relpath(root / binding["source_image"]["relative_path"], target.parent),
        "must_attach": True, "description": "The current image to edit; preserve unrequested visual features while applying the listed corrections.",
    }]
    prepared["constraints"]["must_change"] = [item["instruction"] for item in binding["changes"]]
    if REPAIR_PRESERVE_REQUIREMENT not in prepared["constraints"]["must_preserve"]:
        prepared["constraints"]["must_preserve"].append(REPAIR_PRESERVE_REQUIREMENT)
    return prepared


def spatial_layout_foundation_source(
    export: dict[str, Any], project_root: Path
) -> dict[str, Any]:
    """Return the foundation-source record for one current spatial export.

    This record is intentionally a reference-only deterministic layout.  It
    cannot become an identity asset or count as a generated visual asset.
    """
    if not isinstance(export, dict):
        raise ValueError("spatial layout export must be an object")
    root = project_root.expanduser().resolve(strict=True)
    source_binding = export if {"relative_path", "sha256"} <= set(export) else export.get("spatial_source")
    if not isinstance(source_binding, dict):
        raise ValueError("spatial layout export requires a bound spatial_source")
    relative_export = source_binding.get("relative_path")
    expected_export_hash = source_binding.get("sha256")
    if not isinstance(relative_export, str) or not isinstance(expected_export_hash, str):
        raise ValueError("spatial export binding is invalid")
    try:
        export_path = (root / relative_export).resolve(strict=True)
        export_path.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise ValueError("spatial export path escapes project root") from exc
    if sha256_bytes(export_path.read_bytes()) != expected_export_hash:
        raise ValueError("spatial export source hash mismatch")
    from dircreative_spatial_scene import read_export, validate_export

    parsed = read_export(export_path, root)
    if errors := validate_export(parsed, root):
        raise ValueError("invalid spatial export: " + "; ".join(errors))
    reference = parsed.get("reference")
    if not isinstance(reference, dict) or (
        not isinstance(reference.get("asset_id"), str)
        or not isinstance(reference.get("relative_path"), str)
        or not isinstance(reference.get("sha256"), str)
        or reference.get("role") != "layout"
        or reference.get("media_class") != "layout_reference"
    ):
        raise ValueError("spatial export layout reference is invalid")
    return {
        "asset_id": reference["asset_id"],
        "source_kind": "deterministic_layout",
        "role": "layout_reference",
        "relative_path": reference["relative_path"],
        "sha256": reference["sha256"],
        "spatial_source": {
            "relative_path": relative_export,
            "sha256": expected_export_hash,
        },
    }


def attach_spatial_layout(
    spec: dict[str, Any],
    export: dict[str, Any],
    project_root: Path,
    spec_path: Path,
) -> dict[str, Any]:
    """Attach one current deterministic layout export to an existing Jingzao spec.

    ``export`` is normally the export artifact binding (``relative_path`` and
    ``sha256``).  A wrapper with that binding in ``spatial_source`` is accepted
    for callers that also carry the parsed export.  The spatial engine remains
    the sole parser and verifier; this helper only turns its approved PNG into
    the final, required Jingzao attachment.
    """
    if not isinstance(spec, dict) or not isinstance(export, dict):
        raise ValueError("spatial layout requires object spec and export")
    try:
        root = project_root.expanduser().resolve(strict=True)
        resolved_spec = spec_path.expanduser().resolve(strict=False)
        resolved_spec.relative_to(root)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise ValueError("spatial layout spec path is outside project root") from exc

    source_binding = export if {"relative_path", "sha256"} <= set(export) else export.get("spatial_source")
    if not isinstance(source_binding, dict):
        raise ValueError("spatial layout export requires a bound spatial_source")
    from dircreative_spatial_scene import read_export, validate_export

    relative_export = source_binding.get("relative_path")
    if not isinstance(relative_export, str):
        raise ValueError("spatial export path is invalid")
    export_path = (root / relative_export).resolve(strict=True)
    try:
        export_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("spatial export path escapes project root") from exc
    expected_export_hash = source_binding.get("sha256")
    if not isinstance(expected_export_hash, str) or sha256_bytes(export_path.read_bytes()) != expected_export_hash:
        raise ValueError("spatial export source hash mismatch")
    parsed = read_export(export_path, root)
    errors = validate_export(parsed, root)
    if errors:
        raise ValueError("invalid spatial export: " + "; ".join(errors))
    reference = parsed.get("reference")
    if not isinstance(reference, dict):
        raise ValueError("spatial export is missing layout reference")
    if (
        reference.get("role") != "layout"
        or reference.get("media_class") != "layout_reference"
        or reference.get("primary_job") != "position_pose_occlusion"
        or reference.get("source_kind") != "deterministic_render"
        or reference.get("must_not_control")
        != ["character_identity", "prop_identity", "material", "texture", "final_art_style"]
    ):
        raise ValueError("spatial export layout role is invalid")
    image_relative = reference.get("relative_path")
    image_hash = reference.get("sha256")
    if not isinstance(image_relative, str) or not isinstance(image_hash, str):
        raise ValueError("spatial export layout image binding is invalid")
    image_path = (root / image_relative).resolve(strict=True)
    try:
        image_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("spatial export layout image escapes project root") from exc
    if sha256_bytes(image_path.read_bytes()) != image_hash:
        raise ValueError("spatial export layout image hash mismatch")
    try:
        source_ref = os.path.relpath(image_path, resolved_spec.parent)
    except ValueError as exc:
        raise ValueError("cannot bind spatial image relative to Jingzao spec") from exc
    updated = copy.deepcopy(spec)
    inputs = updated.setdefault("inputs", [])
    if not isinstance(inputs, list):
        raise ValueError("Jingzao spec inputs must be a list")
    layout_id = f"layout-{parsed.get('shot_id', '')}-{parsed.get('phase', '')}".strip("-")
    if not layout_id or any(not isinstance(item, dict) for item in inputs):
        raise ValueError("spatial export has no usable shot identity")
    if any(item.get("id") == layout_id for item in inputs):
        raise ValueError(f"Jingzao spec already binds spatial layout {layout_id}")
    colors = parsed.get("color_binding")
    color_sentence = parsed.get("prompt_binding")
    if not isinstance(colors, list) or not isinstance(color_sentence, str) or not color_sentence.strip():
        raise ValueError("spatial export color prompt binding is invalid")
    inputs.append(
        {
            "id": layout_id,
            "type": "image",
            "role": "layout",
            "description": (
                "Use only for current position, pose, scale, occlusion and camera-side staging. "
                + color_sentence.strip()
                + " Do not use it for character identity, prop identity, material, texture, or final art style."
            ),
            "source_kind": "local_path",
            "source_ref": source_ref,
            "must_attach": True,
        }
    )
    return updated


def prepare_layout(
    *, project_root: Path, spec_path: Path, export_path: Path, output_spec: Path, output_reference: Path
) -> dict[str, Any]:
    """Create derived Jingzao inputs for one current spatial layout export."""
    root = project_root.expanduser().resolve(strict=True)

    def inside(path: Path, *, exists: bool) -> Path:
        candidate = path.expanduser().resolve(strict=exists)
        candidate.relative_to(root)
        return candidate

    try:
        source_spec = inside(spec_path, exists=True)
        export_file = inside(export_path, exists=True)
        target_spec = inside(output_spec, exists=False)
        target_reference = inside(output_reference, exists=False)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise ValueError("prepare-layout paths must stay inside project_root") from exc
    if target_spec in {source_spec, export_file} or target_reference in {source_spec, export_file, target_spec}:
        raise ValueError("prepare-layout outputs must be new files")
    if target_spec.exists() or target_reference.exists():
        raise ValueError("prepare-layout refuses to overwrite an existing output")
    try:
        spec = json.loads(source_spec.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError("visual spec root is invalid")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("visual spec is unreadable") from exc
    for item in spec.get("inputs", []):
        if not isinstance(item, dict) or item.get("source_kind") != "local_path":
            continue
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, str):
            raise ValueError("visual spec local input is invalid")
        try:
            source_file = (source_spec.parent / source_ref).resolve(strict=True)
            source_file.relative_to(root)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise ValueError("visual spec local input escapes project_root") from exc
        item["source_ref"] = os.path.relpath(source_file, target_spec.parent)
    binding = {
        "relative_path": export_file.relative_to(root).as_posix(),
        "sha256": sha256_bytes(export_file.read_bytes()),
    }
    updated = attach_spatial_layout(spec, binding, root, target_spec)
    input_id = updated["inputs"][-1]["id"]
    source = spatial_layout_foundation_source(binding, root)
    reference = {
        "input_id": input_id,
        "asset_id": source["asset_id"],
        "role": "layout",
        "relative_path": source["relative_path"],
        "sha256": source["sha256"],
        "rights_status": "project_owned",
        "approval_status": "reference_only_approved",
        "spatial_source": source["spatial_source"],
    }
    spec_payload = (json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    reference_payload = (json.dumps(reference, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    def publish_new(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)  # atomic create; never replaces a raced user file
        finally:
            temporary.unlink(missing_ok=True)

    published_spec = False
    try:
        publish_new(target_spec, spec_payload)
        published_spec = True
        publish_new(target_reference, reference_payload)
    except OSError as exc:
        if published_spec:
            target_spec.unlink(missing_ok=True)
        raise ValueError("prepare-layout could not publish both outputs") from exc
    return {"spec": target_spec.relative_to(root).as_posix(), "reference": target_reference.relative_to(root).as_posix(), "input_id": input_id}


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
    if not REQUIRED_REFERENCE_READS.issubset(declared_paths) or len(declared_paths) != len(reference_reads):
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
    plan_asset: dict[str, Any] | None = None
    repair = document.get("candidate_repair")
    verified_repair: dict[str, Any] | None = None
    annotated_storyboard = False
    planning_resolution: dict[str, Any] | None = None
    if isinstance(visual_plan, dict):
        plan_dir = (resolved_project / document["visual_plan"]["relative_path"]).parent
        plan_errors, _ = validate_plan(copy.deepcopy(visual_plan), base_dir=plan_dir)
        if plan_errors:
            errors.append("visual_asset_plan_snapshot_invalid")
        active_matches = [
            item
            for item in visual_plan.get("assets", [])
            if isinstance(item, dict) and item.get("asset_id") == active["asset_id"]
        ]
        if "motion_planning" in document:
            try:
                planning_resolution = resolve_planning_image_target(
                    document["motion_planning"], project_root=resolved_project,
                    visual_plan_binding=document["visual_plan"],
                )
                derived = planning_resolution["asset"]
                if any(active.get(key) != derived[key] for key in (
                    "asset_id", "role", "truth_sha256", "purpose_sha256", "visual_plan_sha256", "operation"
                )):
                    errors.append("visual_asset_planning_target_mismatch")
                active_matches = [derived]
            except (OSError, UnicodeDecodeError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                errors.append(f"visual_asset_planning_target_invalid:{exc}")
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
            coverage = plan_asset.get("coverage") if isinstance(plan_asset, dict) else None
            unit_ids = coverage.get("generation_unit_ids") if isinstance(coverage, dict) else None
            unit = next(
                (
                    item for item in visual_plan.get("generation_units", [])
                    if isinstance(item, dict)
                    and isinstance(unit_ids, list)
                    and len(unit_ids) == 1
                    and item.get("unit_id") == unit_ids[0]
                ),
                None,
            )
            annotated_storyboard = (
                plan_asset.get("role") == "professional_storyboard_motion_map"
                and plan_asset.get("action") == "generate"
                and plan_asset.get("compile_route") == "selected_skill_handoff"
                and isinstance(unit, dict)
                and isinstance(coverage, dict)
                and unit.get("storyboard_strategy") == "annotated_reference"
                and coverage.get("shot_ids") == unit.get("shot_ids")
            )
            if active.get("role") == "professional_storyboard_motion_map" and not annotated_storyboard and planning_resolution is None:
                errors.append("visual_asset_annotated_storyboard_strategy_invalid")
    if repair is not None:
        try:
            expected_repair = build_candidate_repair_source(
                project_root=resolved_project, visual_plan_binding=document["visual_plan"],
                asset_id=active["asset_id"], changes=repair.get("changes") if isinstance(repair, dict) else None,
                base_plan_binding=repair.get("base_plan") if isinstance(repair, dict) else None,
            )
            if repair != expected_repair or active.get("operation") != "edit" or "motion_planning" in document:
                raise ValueError("candidate_repair_source_or_operation_mismatch")
            verified_repair = expected_repair
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append("candidate_repair_invalid:" + str(exc))

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
        if planning_resolution is not None:
            # The bound coverage design is the evidence for this temporary target.
            # It is not a completed foundation pass or a formal asset adoption.
            foundation = None
            if input_spec.get("asset_foundation_pass") is not None:
                errors.append("planning_target_foundation_must_be_null")
        else:
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
            if annotated_storyboard:
                foundation_errors = []
            elif is_design:
                foundation_errors = asset_foundation_pass.validate_design(
                    foundation, artifact_root=resolved_project,
                    asset_id=active["asset_id"], role=active["role"],
                )
                if annotated_storyboard and foundation_errors == ["asset_design_scope_invalid"]:
                    foundation_errors = []
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
            or not set(item).issubset({
                "input_id",
                "asset_id",
                "role",
                "relative_path",
                "sha256",
                "rights_status",
                "approval_status",
                "spatial_source",
            })
            or not {
                "input_id", "asset_id", "role", "relative_path", "sha256", "rights_status", "approval_status"
            }.issubset(item)
            for item in references
        ):
            errors.append("visual_asset_reference_assets_invalid")
        else:
            reference_assets = references
            if verified_repair is not None and references != [candidate_repair_reference(verified_repair)]:
                errors.append("candidate_repair_reference_set_mismatch")
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
                is_layout = item.get("role") == "layout"
                if is_layout and item.get("spatial_source") is not None:
                    try:
                        layout_source = spatial_layout_foundation_source(
                            {"spatial_source": item.get("spatial_source")}, resolved_project
                        )
                        if (
                            layout_source["asset_id"] != item.get("asset_id")
                            or layout_source["relative_path"] != item.get("relative_path")
                            or layout_source["sha256"] != item.get("sha256")
                        ):
                            raise ValueError("layout source mismatch")
                    except (ImportError, OSError, RuntimeError, ValueError):
                        errors.append(f"visual_asset_layout_reference_invalid:{item.get('input_id')}")
                elif verified_repair is None and not annotated_storyboard and planning_resolution is None and (
                    source is None
                    or source.get("relative_path") != item.get("relative_path")
                    or source.get("sha256") != item.get("sha256")
                    or (is_layout and (source.get("source_kind") != "planning_only" or source.get("role") != "planning_only"))
                ):
                    errors.append(f"visual_asset_reference_not_in_foundation:{item.get('input_id')}")
                if item.get("rights_status") not in {
                    "user_provided",
                    "project_owned",
                    "licensed",
                    "public_domain",
                }:
                    errors.append(f"visual_asset_reference_rights_invalid:{item.get('input_id')}")
                expected_approvals = (
                    {"candidate_repair_only"}
                    if verified_repair is not None
                    else
                    {"user_locked", "reused_locked"}
                    if isinstance(source, dict) and source.get("source_kind") == "canonical_asset"
                    else {"reference_only_approved"}
                )
                if item.get("approval_status") not in expected_approvals:
                    errors.append(
                        f"visual_asset_reference_approval_invalid:{item.get('input_id')}"
                    )

    output = document["output_spec"]
    capsule_payload: bytes | None = None
    if output.get("style_capsule") is not None:
        capsule_payload = read_binding(resolved_project, output["style_capsule"], "jingzao_style_capsule", errors)
        load_json_bytes(capsule_payload, "jingzao_style_capsule", errors)
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
        if verified_repair is not None:
            constraints = spec.get("constraints", {})
            if (spec.get("mode") != "edit"
                or not isinstance(constraints, dict)
                or constraints.get("must_change") != [item["instruction"] for item in verified_repair["changes"]]
                or REPAIR_PRESERVE_REQUIREMENT not in constraints.get("must_preserve", [])):
                errors.append("candidate_repair_spec_scope_mismatch")
        if plan_asset is not None:
            errors.extend(role_spec_errors(spec, plan_asset))
        if planning_resolution is not None:
            errors.extend(planning_image_spec_errors(spec, planning_resolution["panels"]))
        if spec.get("intent") != (REPAIR_INTENT if verified_repair is not None else input_spec.get("purpose")):
            errors.append("jingzao_visual_generation_spec_purpose_mismatch")
        allowed_modes = {
            "create": {"create"},
            "styleboard": {"styleboard"},
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
        if planning_resolution is not None and [item.get("id") for item in required_spec_inputs] != [item.get("input_id") for item in reference_assets]:
            errors.append("motion_planning_reference_order_mismatch")
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
            capsule_args: list[str] = []
            if capsule_payload is not None:
                capsule_path = replay_project / output["style_capsule"]["relative_path"]
                capsule_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with capsule_path.open("xb") as handle:
                        handle.write(capsule_payload)
                except FileExistsError:
                    return ["jingzao_style_capsule_replay_path_collision"], None
                capsule_args = ["--style-capsule", str(capsule_path)]
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
            declared_review = compiled.get("prompt_review") if isinstance(compiled, dict) else None
            approve_provider_review = provider_review_approved(declared_review)
            replay_compiled, compile_error = run_json_command(
                isolated_python_command(
                    replay_provider / "scripts/compile_prompt.py",
                    str(replay_spec),
                    "--platform",
                    "openai",
                    "--format",
                    "json",
                    *capsule_args,
                    *(["--approve-review"] if approve_provider_review else []),
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
            if verified_repair is not None and any(
                " ".join(text.split()) not in " ".join(candidate.split())
                for text in [REPAIR_PRESERVE_REQUIREMENT, *[item["instruction"] for item in verified_repair["changes"]]]
            ):
                errors.append("candidate_repair_compiler_dropped_edit_scope")
            # Bind complete canonical spec constraints to the provider's actual
            # output, not arbitrary English marker tokens in a handwritten prompt.
            if plan_asset is not None and any(
                " ".join(requirement.split()) not in " ".join(candidate.split())
                for requirement in canonical_asset_role_requirements(plan_asset, operation=str(active.get("operation", "create")))
            ):
                errors.append("jingzao_compiler_dropped_asset_role_requirements")
        else:
            errors.append("jingzao_compiled_prompt_missing")
        review = compiled.get("prompt_review", {})
        if not provider_review_ready(review):
            errors.append("jingzao_prompt_review_not_ready")
        call_plan = compiled.get("imagegen_call_plan", {})
        if call_plan.get("status") != "ready" or call_plan.get("errors") not in ([], None):
            errors.append("jingzao_imagegen_call_plan_not_ready")
        expected_input_ids = sorted(item["input_id"] for item in reference_assets)
        if planning_resolution is not None and call_plan.get("required_input_ids") != [item["input_id"] for item in reference_assets]:
            errors.append("motion_planning_reference_order_mismatch")
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
    if len(sys.argv) > 1 and sys.argv[1] == "prepare-candidate-repair":
        parser = argparse.ArgumentParser(description="Prepare a same-asset edit from a current reviewed retry candidate.")
        parser.add_argument("prepare-candidate-repair")
        parser.add_argument("--project-root", required=True, type=Path)
        parser.add_argument("--visual-plan", required=True)
        parser.add_argument("--expected-plan-sha256", required=True)
        parser.add_argument("--asset-id", required=True)
        parser.add_argument("--spec", required=True)
        parser.add_argument("--changes", required=True)
        parser.add_argument("--base-plan", help="Reviewed best-quality same-truth plan to use instead of the latest edited image.")
        parser.add_argument("--expected-base-plan-sha256")
        parser.add_argument("--output-spec", required=True)
        parser.add_argument("--output-binding", required=True)
        args = parser.parse_args()
        try:
            root = args.project_root.resolve(strict=True)
            changes = json.loads(read_relative_regular_file_once(root, args.changes, max_bytes=65536, label="repair changes"))
            if bool(args.base_plan) != bool(args.expected_base_plan_sha256):
                raise ValueError("candidate_repair_base_plan_requires_hash")
            binding = build_candidate_repair_source(project_root=root, visual_plan_binding={"relative_path": args.visual_plan, "sha256": args.expected_plan_sha256}, asset_id=args.asset_id, changes=changes,
                base_plan_binding={"relative_path": args.base_plan, "sha256": args.expected_base_plan_sha256} if args.base_plan else None)
            spec = json.loads(read_relative_regular_file_once(root, args.spec, max_bytes=MAX_JSON_BYTES, label="repair source spec"))
            targets = [root / args.output_spec, root / args.output_binding]
            for path in targets:
                path.relative_to(root)
                if path.exists() or path.is_symlink() or path.parent.resolve(strict=True) != path.parent:
                    raise ValueError("candidate_repair_outputs_must_be_new_regular_paths")
            if targets[0] == targets[1]:
                raise ValueError("candidate_repair_outputs_must_be_distinct")
            prepared = prepare_candidate_repair_spec(spec, binding, project_root=root, output_spec=targets[0])
            written = []
            try:
                for path, value in zip(targets, [prepared, binding]):
                    with path.open("xb") as handle:
                        handle.write((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())
                    written.append(path)
            except OSError:
                for path in written:
                    path.unlink()
                raise
            print(json.dumps({"status": "prepared", "candidate_repair": binding, "reference_asset": candidate_repair_reference(binding), "operation": "edit", "spec": {"relative_path": args.output_spec, "sha256": sha256_bytes(targets[0].read_bytes())}, "generated": False, "visual_qa_approved": False}, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(json.dumps({"status": "blocked", "errors": [str(exc)]}, ensure_ascii=False))
            return 1
    if len(sys.argv) > 1 and sys.argv[1] == "prepare-role-spec":
        parser = argparse.ArgumentParser(description="Apply the current asset role before Jingzao compilation.")
        parser.add_argument("prepare-role-spec")
        parser.add_argument("--project-root", required=True, type=Path)
        parser.add_argument("--visual-plan", required=True, type=Path)
        parser.add_argument("--asset-id", required=True)
        parser.add_argument("--spec", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)
        args = parser.parse_args()
        try:
            root = args.project_root.resolve(strict=True)
            plan_path = (root / args.visual_plan).resolve(strict=True)
            spec_path = (root / args.spec).resolve(strict=True)
            output = (root / args.output).resolve(strict=False)
            for path in (plan_path, spec_path, output):
                path.relative_to(root)
            plan_raw = read_relative_regular_file_once(root, plan_path.relative_to(root).as_posix(), max_bytes=MAX_JSON_BYTES, label="visual plan")
            plan = json.loads(plan_raw)
            if validate_plan(plan, base_dir=plan_path.parent)[0]:
                raise ValueError("visual_asset_plan_invalid")
            asset = next((item for item in plan["assets"] if item["asset_id"] == args.asset_id), None)
            if asset is None or asset.get("action") in {"reuse", "assemble"}:
                raise ValueError("active_asset_not_generated")
            if not canonical_asset_role_requirements(asset):
                raise ValueError("role_uses_existing_narrative_or_coverage_handoff")
            spec_raw = read_relative_regular_file_once(root, spec_path.relative_to(root).as_posix(), max_bytes=MAX_JSON_BYTES, label="Jingzao spec")
            prepared = prepare_role_spec(json.loads(spec_raw), asset)
            output.parent.mkdir(parents=True, exist_ok=True)
            raw = (json.dumps(prepared, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
            with output.open("xb") as handle:
                handle.write(raw)
            print(json.dumps({"status": "prepared", "spec": {"relative_path": output.relative_to(root).as_posix(), "sha256": sha256_bytes(raw)}, "asset_id": args.asset_id, "requirements": canonical_asset_role_requirements(asset), "generated": False}, ensure_ascii=False))
            return 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(json.dumps({"status": "blocked", "errors": [str(exc)]}, ensure_ascii=False))
            return 1
    if len(sys.argv) > 1 and sys.argv[1] == "prepare-layout":
        parser = argparse.ArgumentParser(description="Prepare a derived Jingzao spec and formal layout reference.")
        parser.add_argument("prepare-layout")
        parser.add_argument("--project-root", required=True, type=Path)
        parser.add_argument("--spec", required=True, type=Path)
        parser.add_argument("--export", required=True, type=Path)
        parser.add_argument("--output-spec", required=True, type=Path)
        parser.add_argument("--output-reference", required=True, type=Path)
        args = parser.parse_args()
        try:
            result = prepare_layout(
                project_root=args.project_root,
                spec_path=args.spec,
                export_path=args.export,
                output_spec=args.output_spec,
                output_reference=args.output_reference,
            )
        except (OSError, ValueError, ImportError) as exc:
            print(json.dumps({"status": "blocked", "errors": [str(exc)]}, ensure_ascii=False))
            return 1
        print(json.dumps({"status": "prepared", **result}, ensure_ascii=False, indent=2))
        return 0
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
