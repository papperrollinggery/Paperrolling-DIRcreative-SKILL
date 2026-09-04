#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL_ROOT = ROOT / "skills/dircreative"
SKILL_ROOT = SOURCE_SKILL_ROOT if (SOURCE_SKILL_ROOT / "SKILL.md").is_file() else ROOT
REGISTRY_PATH = SKILL_ROOT / "runtime/visual-skill-policy.json"
ROUTING_PATH = SKILL_ROOT / "runtime/routing-policy.yaml"
CASES_PATH = ROOT / "tests/fixtures/skill-stack/cases.json"
HOST_CATALOG_PATH = ROOT / "tests/fixtures/skill-stack/host-catalog.json"
MAIN_SKILL = SKILL_ROOT / "SKILL.md"

ID_RE = re.compile(r"^[a-z0-9][a-z0-9:._-]{0,127}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_ROLES = {
    "craft_owner",
    "collaborator",
    "validator",
    "execution_adapter",
    "explicit_overlay",
    "reference_only",
}
ALLOWED_PERSPECTIVES = {
    "narrative_strategy",
    "visual_production",
    "model_continuity",
    "validation_only",
}
ISOLATED_CONTEXT_SCOPES = {
    "isolated_craft_contract",
    "isolated_validator_contract",
    "isolated_handoff_contract",
}
REQUIRED_PROVIDER_FIELDS = {
    "skill_id",
    "source_type",
    "availability",
    "capabilities",
    "media_gate",
    "deliverable_layers",
    "provider_roles",
    "trigger_stages",
    "explicit_only",
    "mode_allowlist",
    "tool_dependencies",
    "required_gate",
    "external_write",
    "may_cost_money",
    "priority",
    "mutually_exclusive",
    "fallback",
    "context_cost",
    "perspective",
}
PRIVATE_PATH_MARKERS = ("/Users/", "/home/", "\\Users\\")
BodyLoader = Callable[[str, "CatalogEntry"], "CatalogEntry | None"]
_ROUTE_CONTEXT_SEAL = object()
REALISTIC_SMOKE_EXPECTED = {
    "p01_fast_single_concept": ("dircreative", 0, "ready", None),
    "p06_key_visual": ("dircreative", 0, "ready", None),
    "p17_seedance_direct": ("mr-li-seedance-25", 1, "ready", None),
    "p39_seedance_performance_handoff": ("mr-li-seedance-25", 2, "ready", None),
    "p23_mechanical_still": ("mechanical-transformation-design", 1, "ready", None),
    "p24_mechanical_temporal": ("mechanical-transformation-design", 1, "ready", None),
    "p38_full_project_stack": ("creative-anchor-director", 1, "ready", None),
    "p41_generation_gate": ("dircreative", 0, "waiting_for_gate", "generation_authorization"),
    "p10_technical_storyboard": ("professional-storyboard-director", 1, "ready", None),
    "p20_action_choreography": ("action-choreography-reference", 1, "ready", None),
    "p21_action_showcase": ("action-showcase-direction", 1, "ready", None),
    "p22_seedance_fight": ("seedance-fight-director", 1, "ready", None),
    "p26_sound_design": ("cinematic-music-sound-design", 1, "ready", None),
    "p42_authorized_generation_adapter": ("dircreative", 1, "ready", None),
    "p44_score_mix_reuses_loaded_body": ("score-and-mix-picture", 1, "ready", None),
    "p45_asset_foundation": ("minimum-visual-bible", 2, "needs_followup", None),
    "p46_script_to_seedance": ("convert-script-to-seedance", 2, "ready", None),
    "p52_script_to_seedance25": ("convert-script-to-seedance", 3, "ready", None),
    "p53_seedance25_emotion_specialist": ("seedance-25-emotion-prompt", 2, "ready", None),
    "p54_seedance25_fast_priority": ("mr-li-seedance-25", 1, "ready", None),
    "p55_script_target_seedance25_from_20_source": ("convert-script-to-seedance", 3, "ready", None),
    "p56_contextual_human_language": ("shuorenhua", 2, "ready", None),
    "p47_cinematic_storyboard_frames": ("jingzao-image-forge", 1, "ready", None),
    "p48_asset_foundation_production_design_pass": ("production-design-worldbuilding", 1, "needs_followup", None),
    "p49_asset_stress_validation": ("dircreative", 1, "ready", None),
    "p50_production_ledger": ("dircreative", 1, "ready", None),
    "n12_candidate_pool_capped": ("creative-anchor-director", 1, "ready", None),
}
REALISTIC_BODY_PAD = {
    "creative-anchor-director": 5800,
    "visual-style-aesthetic-direction": 11800,
    "seedance-25-emotion-prompt": 13300,
    "mechanical-transformation-design": 6350,
    "professional-storyboard-director": 4150,
    "action-choreography-reference": 5750,
    "action-showcase-direction": 4070,
    "seedance-fight-director": 5160,
    "cinematic-music-sound-design": 4000,
    "imagegen": 19000,
    "score-and-mix-picture": 9950,
    "convert-script-to-seedance": 7680,
    "mr-li-seedance-25": 5355,
    "production-design-worldbuilding": 4430,
    "minimum-visual-bible": 5000,
    "character-continuity-bible": 5000,
    "ai-film-asset-stress-test": 7000,
    "ai-film-production-ledger": 4000,
    "jingzao-image-forge": 28240,
    "ai-video-prompt-preflight": 23600,
    "shuorenhua": 20670,
    "humanizer-zh": 18898,
}
JINGZAO_REFERENCE_PAD = {
    "references/visual-spec.md": 29007,
    "references/prompt-compiler.md": 16154,
    "references/reference-delivery.md": 6718,
    "references/styleboard-mode.md": 6429,
    "references/shot-tension-design.md": 5096,
    "references/cinematic-shot-design.md": 7767,
}
MR_LI_REFERENCE_PAD = {
    "references/prompt-writing.md": 2863,
    "references/continuity-and-duration.md": 1917,
}
SHUORENHUA_REFERENCE_PAD = {
    "references/protected-spans.md": 4399,
    "references/positive-style.md": 6881,
    "references/operation-manual.md": 15687,
    "references/structures.md": 7418,
}
HANDOFF_REQUIRED_CHAINS = {
    "script_to_seedance_v1": [
        "authoritative_script",
        "shots",
        "generation_units",
        "bindings",
        "prompt_units",
    ],
    "storyboard_frame_to_jingzao_v1": [
        "input_spec",
        "reference_reads",
        "output_spec",
        "delivery_consumption",
    ],
}
ASSET_FOUNDATION_STAGE_IDS = [
    "identity_state",
    "production_design",
    "camera_geography",
    "material_response",
    "constraint_assignment",
    "stress_certification",
]


class SkillStackError(ValueError):
    pass


def resolve_runtime_path(
    relative: str,
    *,
    root: Path = ROOT,
    skill_root: Path = SKILL_ROOT,
) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise SkillStackError("runtime path must be a POSIX relative path")
    parsed = PurePosixPath(relative)
    raw_parts = relative.split("/")
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        raise SkillStackError("runtime path escapes the allowed root")
    prefix = "skills/dircreative/"
    candidates: list[tuple[Path, Path]] = [(root / Path(*parsed.parts), root)]
    if relative.startswith(prefix):
        mapped = PurePosixPath(relative.removeprefix(prefix))
        candidates.append((skill_root / Path(*mapped.parts), skill_root))

    for candidate, allowed_root in candidates:
        if allowed_root.is_symlink():
            raise SkillStackError("runtime root must not be a symlink")
        try:
            allowed_resolved = allowed_root.resolve(strict=True)
            lexical_relative = candidate.relative_to(allowed_root)
        except (OSError, ValueError) as exc:
            raise SkillStackError("runtime path escapes the allowed root") from exc
        cursor = allowed_root
        missing = False
        for part in lexical_relative.parts:
            cursor = cursor / part
            try:
                metadata = cursor.lstat()
            except FileNotFoundError:
                missing = True
                break
            except OSError as exc:
                raise SkillStackError("runtime context file is unavailable") from exc
            if stat.S_ISLNK(metadata.st_mode):
                raise SkillStackError("runtime path must not traverse a symlink")
        if missing:
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise SkillStackError("runtime context file is unavailable") from exc
        if not resolved.is_relative_to(allowed_resolved):
            raise SkillStackError("runtime path escapes the allowed root")
        metadata = resolved.stat()
        if not stat.S_ISREG(metadata.st_mode):
            raise SkillStackError("runtime context must be a regular file")
        return resolved
    raise SkillStackError("runtime context file is unavailable")


@dataclass(frozen=True)
class CatalogEntry:
    skill_id: str
    source_type: str
    skill_file: Path | None
    body_bytes: int
    body_sha256: str | None
    frontmatter_bytes: int
    openai_metadata: dict[str, str]
    body_loaded: bool
    capability_policy: dict[str, Any] | None = None

    def public(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "source_type": self.source_type,
            "available": True,
            "body_bytes": self.body_bytes,
            "body_sha256": self.body_sha256,
            "frontmatter_bytes": self.frontmatter_bytes,
            "openai_metadata_present": bool(self.openai_metadata),
            "body_loaded": self.body_loaded,
            "capability_policy_validated": self.capability_policy is not None,
        }


@dataclass(frozen=True)
class ValidatedRouteContext:
    route_id: str
    mode: str
    execution_context: str
    final_owner: str
    granted_gates: frozenset[str]
    deliverable_layer: str
    _seal: object

    def __post_init__(self) -> None:
        if self._seal is not _ROUTE_CONTEXT_SEAL:
            raise SkillStackError("route context must be created by primary-route validation")


def validate_primary_route_context(
    intent: dict[str, Any],
    *,
    request_text: str,
    handoff_path: Path | None = None,
    project_root: Path | None = None,
    descriptor_path: Path | None = None,
) -> ValidatedRouteContext:
    from dircreative_route import route_request

    handoff: dict[str, Any] | None = None
    descriptor: dict[str, Any] | None = None
    resolved_handoff: Path | None = None
    resolved_project: Path | None = None
    if handoff_path is not None or project_root is not None:
        if handoff_path is None or project_root is None or descriptor_path is None:
            raise SkillStackError("ADCO primary route requires handoff, project root, and descriptor")
        try:
            resolved_handoff = handoff_path.resolve(strict=True)
            resolved_project = project_root.resolve(strict=True)
            handoff = load_json(resolved_handoff)
            descriptor = load_json(descriptor_path.resolve(strict=True))
        except (OSError, SkillStackError) as exc:
            raise SkillStackError("ADCO primary route evidence is unavailable") from exc
    primary = route_request(
        request_text,
        handoff,
        project_root=resolved_project,
        descriptor=descriptor,
        handoff_path=resolved_handoff,
    )
    if primary.get("route") != intent.get("route_id") or primary.get("mode") != intent.get("mode"):
        raise SkillStackError("intent does not match the validated primary route")
    execution_context = str(primary.get("execution_context") or "")
    expected_context = str(intent.get("execution_context") or "standalone_chat")
    if execution_context != expected_context:
        raise SkillStackError("intent execution context does not match the validated primary route")
    if primary.get("action") == "stop_skill_runtime":
        raise SkillStackError("validated primary route stopped Skill runtime")
    granted: set[str] = set()
    if primary.get("action") == "continue" and primary.get("external_user_gate") is None:
        if primary.get("route") == "generation_authorization":
            granted.add("generation_authorization")
        if primary.get("route") == "client_delivery":
            granted.add("client_delivery_approval")
    return ValidatedRouteContext(
        route_id=str(primary["route"]),
        mode=str(primary["mode"]),
        execution_context=execution_context,
        final_owner="adco" if execution_context == "orchestrated_worker" else "dircreative",
        granted_gates=frozenset(granted),
        deliverable_layer=str(primary.get("deliverable_layer") or "bounded_output"),
        _seal=_ROUTE_CONTEXT_SEAL,
    )


def _fixture_route_context(case: dict[str, Any]) -> ValidatedRouteContext:
    intent = case["intent"]
    return ValidatedRouteContext(
        route_id=str(intent["route_id"]),
        mode=str(intent["mode"]),
        execution_context=str(intent.get("execution_context") or "standalone_chat"),
        final_owner=str(case.get("trusted_controller_owner") or "dircreative"),
        granted_gates=frozenset(case.get("trusted_granted_gates", [])),
        deliverable_layer=str(intent.get("deliverable_layer") or "fixture_layer"),
        _seal=_ROUTE_CONTEXT_SEAL,
    )


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_reference_pack(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == len(set(value))
        and all(
            isinstance(item, str)
            and item.startswith("references/")
            and "\\" not in item
            and ".." not in PurePosixPath(item).parts
            for item in value
        )
    )


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SkillStackError(f"invalid JSON: {path.name}: {exc}") from exc


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SkillStackError("visual Skill policy must be an object")
    return payload


def load_routing(path: Path = ROUTING_PATH) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SkillStackError("routing policy must be JSON-compatible YAML")
    return payload


def normalize_providers(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    defaults = registry.get("provider_defaults")
    providers = registry.get("providers")
    if not isinstance(defaults, dict) or not isinstance(providers, list):
        raise SkillStackError("provider defaults/providers are malformed")
    normalized: dict[str, dict[str, Any]] = {}
    for raw in providers:
        if not isinstance(raw, dict):
            raise SkillStackError("provider entry must be an object")
        item = {**defaults, **raw}
        missing = REQUIRED_PROVIDER_FIELDS - set(item)
        if missing:
            raise SkillStackError(f"provider metadata missing fields: {sorted(missing)}")
        skill_id = item.get("skill_id")
        if not isinstance(skill_id, str) or not ID_RE.fullmatch(skill_id):
            raise SkillStackError(f"invalid provider id: {skill_id!r}")
        if skill_id in normalized:
            raise SkillStackError(f"duplicate provider id: {skill_id}")
        roles = item.get("provider_roles")
        if not isinstance(roles, list) or not roles or not set(roles) <= ALLOWED_ROLES:
            raise SkillStackError(f"invalid provider roles: {skill_id}")
        if item.get("perspective") not in ALLOWED_PERSPECTIVES:
            raise SkillStackError(f"invalid provider perspective: {skill_id}")
        if item.get("explicit_only") is not True and item.get("explicit_only") is not False:
            raise SkillStackError(f"invalid explicit_only flag: {skill_id}")
        normalized[skill_id] = item
    return normalized


def normalize_dynamic_provider(
    skill_id: str,
    raw: Any,
    registry: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    allowed_capabilities = {
        capability
        for provider in normalize_providers(registry).values()
        for capability in provider.get("capabilities", [])
    }
    required = {
        "capabilities",
        "media_gate",
        "deliverable_layers",
        "provider_roles",
        "trigger_stages",
        "mode_allowlist",
        "priority",
        "perspective",
    }
    if set(raw) != required:
        return None
    capabilities = raw.get("capabilities")
    roles = raw.get("provider_roles")
    media_gate = raw.get("media_gate")
    layers = raw.get("deliverable_layers")
    stages = raw.get("trigger_stages")
    modes = raw.get("mode_allowlist")
    priority = raw.get("priority")
    perspective = raw.get("perspective")
    allowed_media = {"any", "still", "image_series", "storyboard", "video", "audio", "document"}
    allowed_stages = {"any"} | {
        str(scenario.get("stage"))
        for scenario in registry.get("scenarios", [])
        if isinstance(scenario, dict)
    }
    allowed_layers = {
        "any",
        "bounded_output",
        "bounded_specialist_output",
        "client_story",
        "narrative_storyboard",
        "frame_content_spec",
        "technical_production",
        "full_preproduction",
        "generation_execution",
        "client_delivery",
        "fixture_layer",
    }
    if (
        not isinstance(capabilities, list)
        or not capabilities
        or not all(isinstance(item, str) and item in allowed_capabilities for item in capabilities)
        or not isinstance(roles, list)
        or not roles
        or not set(roles) <= {"craft_owner", "collaborator", "validator"}
        or not isinstance(media_gate, list)
        or not media_gate
        or not all(isinstance(item, str) and item in allowed_media for item in media_gate)
        or not isinstance(layers, list)
        or not layers
        or not all(isinstance(item, str) and item in allowed_layers for item in layers)
        or not isinstance(stages, list)
        or not stages
        or not all(isinstance(item, str) and item in allowed_stages for item in stages)
        or not isinstance(modes, list)
        or not modes
        or not set(modes) <= {"fast", "studio", "delivery"}
        or not isinstance(priority, int)
        or not 1 <= priority <= 79
        or perspective not in ALLOWED_PERSPECTIVES
    ):
        return None
    return {
        **registry["provider_defaults"],
        "skill_id": skill_id,
        "source_type": "host_capability_catalog",
        "availability": "host_validated",
        "capabilities": capabilities,
        "media_gate": media_gate,
        "deliverable_layers": layers,
        "provider_roles": roles,
        "trigger_stages": stages,
        "explicit_only": False,
        "mode_allowlist": modes,
        "tool_dependencies": [],
        "required_gate": None,
        "external_write": False,
        "may_cost_money": False,
        "priority": priority,
        "mutually_exclusive": ["nested_controller", "external_write"],
        "fallback": "dircreative",
        "context_cost": "measure_actual_body_bytes",
        "perspective": perspective,
    }


def validate_registry(registry: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    serialized = json.dumps(registry, ensure_ascii=False, sort_keys=True)
    if any(marker in serialized for marker in PRIVATE_PATH_MARKERS):
        failures.append("registry persists a private absolute path")
    try:
        providers = normalize_providers(registry)
    except SkillStackError as exc:
        return [str(exc)]
    discovery = registry.get("discovery_contract", {})
    if discovery.get("candidate_limit") != 12:
        failures.append("candidate metadata limit must remain 12")
    if discovery.get("host_catalog_bytes_max") != 2097152:
        failures.append("host catalog byte limit must remain 2 MiB")
    if discovery.get("execute_discovered_code") is not False:
        failures.append("discovery must never execute third-party code")
    if discovery.get("persist_private_paths") is not False:
        failures.append("discovery must not persist private paths")
    controller = registry.get("controller_contract", {})
    expected_controller = {
        "standalone_final_owner": "dircreative",
        "orchestrated_final_owner": "adco",
        "providers_are_advisory": True,
        "nested_dispatch_allowed": False,
        "ai_visual_production_director_in_dir": "reference_only",
        "artifact_before_skill_card": True,
    }
    if controller != expected_controller:
        failures.append("controller contract drifted")
    modes = registry.get("mode_contracts", {})
    expected_caps = {
        "fast": (1, 0, 1),
        "studio": (3, 2, 1),
        "delivery": (1, 0, 1),
    }
    for mode, (body_max, collaborators_max, validators_max) in expected_caps.items():
        item = modes.get(mode, {})
        if (
            item.get("provider_bodies_max"),
            item.get("collaborators_max"),
            item.get("validators_max"),
        ) != (body_max, collaborators_max, validators_max):
            failures.append(f"{mode} Skill Stack cap drifted")
    if modes.get("studio", {}).get("isolated_craft_context_bytes_max") != 131072:
        failures.append("Studio isolated craft context must remain 128 KiB")
    if modes.get("fast", {}).get("isolated_craft_context_bytes_max") != 16384:
        failures.append("Fast isolated craft context must remain 16 KiB")
    if modes.get("studio", {}).get("isolated_validator_context_bytes_max") != 65536:
        failures.append("Studio isolated validator context must remain 64 KiB")
    if modes.get("studio", {}).get("isolated_handoff_context_bytes_max") != 86016:
        failures.append("Studio isolated handoff context must remain 84 KiB")
    if modes.get("delivery", {}).get("execution_adapter_context_bytes_max") != 24576:
        failures.append("Delivery isolated execution-adapter budget must remain 24 KiB")
    for skill_id, provider in providers.items():
        if not valid_reference_pack(provider.get("reference_pack", [])):
            failures.append(f"{skill_id}: invalid provider reference pack")
        application_contract = provider.get("application_contract")
        if application_contract is not None and (
            not isinstance(application_contract, dict)
            or application_contract.get("authority") != "diagnostic_only"
            or application_contract.get("output_mode") != "findings_only"
            or application_contract.get("may_rewrite") is not False
            or provider.get("provider_roles") != ["validator"]
        ):
            failures.append(f"{skill_id}: invalid diagnostic-only application contract")
    for overlay in ("liu-creative-workflow", "sophia-research-mode"):
        item = providers.get(overlay, {})
        if item.get("explicit_only") is not True or item.get("provider_roles") != ["explicit_overlay"]:
            failures.append(f"{overlay} must remain an explicit-only overlay")
    ai_director = providers.get("ai-visual-production-director", {})
    if ai_director.get("provider_roles") != ["reference_only"] or ai_director.get("explicit_only") is not True:
        failures.append("ai-visual-production-director must remain reference-only inside DIR")
    imagegen = providers.get("imagegen", {})
    if (
        imagegen.get("context_cost") != "isolated_host_tool_contract"
        or imagegen.get("may_cost_money") is not True
        or imagegen.get("cost_status") != "host_managed_unknown"
        or imagegen.get("separate_payment_action") is not False
        or imagegen.get("api_key_required") is not False
        or imagegen.get("tool_dependencies") != ["image_gen.imagegen"]
    ):
        failures.append("imagegen host-managed isolated adapter contract drifted")
    fal_media = providers.get("fal-ai-media", {})
    if fal_media.get("may_cost_money") is not True:
        failures.append("external fal adapter lost its possible-cost boundary")
    jingzao = providers.get("jingzao-image-forge", {})
    if (
        jingzao.get("context_cost") != "isolated_craft_contract"
        or jingzao.get("provider_roles") != ["craft_owner"]
        or jingzao.get("external_write") is not False
        or jingzao.get("may_cost_money") is not False
    ):
        failures.append("Jingzao must remain a non-executing isolated craft owner")
    prompt_preflight = providers.get("ai-video-prompt-preflight", {})
    if prompt_preflight.get("validator_context_cost") != "isolated_validator_contract":
        failures.append("video prompt preflight must retain isolated validator context")
    asset_stress = providers.get("ai-film-asset-stress-test", {})
    if (
        asset_stress.get("provider_roles") != ["validator"]
        or asset_stress.get("validator_context_cost") != "isolated_validator_contract"
        or asset_stress.get("external_write") is not False
    ):
        failures.append("asset stress test must remain a non-executing isolated validator")
    production_ledger = providers.get("ai-film-production-ledger", {})
    if (
        production_ledger.get("provider_roles") != ["collaborator"]
        or production_ledger.get("external_write") is not False
        or production_ledger.get("may_cost_money") is not False
    ):
        failures.append("production ledger must remain a record-only collaborator")
    handoff_contracts = registry.get("handoff_contracts")
    if not isinstance(handoff_contracts, dict):
        failures.append("handoff_contracts must be an object")
        handoff_contracts = {}
    for contract_id, contract in handoff_contracts.items():
        if not isinstance(contract_id, str) or not ID_RE.fullmatch(contract_id):
            failures.append(f"invalid handoff contract id: {contract_id!r}")
            continue
        if not isinstance(contract, dict):
            failures.append(f"{contract_id}: handoff contract must be an object")
            continue
        if contract.get("source_owner") not in providers or contract.get("target_owner") not in providers:
            failures.append(f"{contract_id}: handoff contract owner is not a registered provider")
        if contract.get("authority") != "compile_only":
            failures.append(f"{contract_id}: handoff contract must remain compile-only")
        if contract.get("output_owner") != contract.get("source_owner"):
            failures.append(f"{contract_id}: handoff output ownership must return to source owner")
        if not isinstance(contract.get("required_inputs"), str) or not contract.get("required_inputs"):
            failures.append(f"{contract_id}: handoff required inputs are missing")
        if not isinstance(contract.get("slot_crosswalk"), str) or not contract.get("slot_crosswalk"):
            failures.append(f"{contract_id}: handoff contract slot crosswalk is missing")
        reference_pack = contract.get("reference_pack", [])
        if not valid_reference_pack(reference_pack):
            failures.append(f"{contract_id}: invalid provider reference pack")
        output_binding = contract.get("output_binding")
        if not isinstance(output_binding, dict) or set(output_binding) != {
            "schema",
            "validator",
            "required_chain",
        }:
            failures.append(f"{contract_id}: provider handoff output binding is malformed")
        else:
            if output_binding.get("required_chain") != HANDOFF_REQUIRED_CHAINS.get(contract_id):
                failures.append(f"{contract_id}: provider handoff provenance chain drifted")
            for key in ("schema", "validator"):
                try:
                    resolve_runtime_path(output_binding.get(key, ""))
                except SkillStackError as exc:
                    failures.append(f"{contract_id}: invalid output binding {key}: {exc}")
        reference = contract.get("reference")
        if not isinstance(reference, str):
            failures.append(f"{contract_id}: handoff contract reference is missing")
            continue
        try:
            contract_path = resolve_runtime_path(reference)
        except SkillStackError as exc:
            failures.append(f"{contract_id}: invalid handoff contract reference: {exc}")
        else:
            if not contract_path.is_file():
                failures.append(f"{contract_id}: handoff contract reference is not a file")
    scenarios = registry.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 30:
        failures.append("visual Skill policy must cover at least 30 high-frequency scenarios")
        scenarios = []
    seen: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            failures.append("scenario entry must be an object")
            continue
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or not ID_RE.fullmatch(scenario_id) or scenario_id in seen:
            failures.append(f"invalid or duplicate scenario id: {scenario_id!r}")
            continue
        seen.add(scenario_id)
        referenced: list[str] = []
        referenced.extend(scenario.get("owner_candidates", []))
        referenced.extend(scenario.get("validator_candidates", []))
        referenced.extend(scenario.get("execution_adapters", []))
        gaps = scenario.get("collaborator_gaps", {})
        if isinstance(gaps, dict):
            for candidates in gaps.values():
                if isinstance(candidates, list):
                    referenced.extend(candidates)
        unknown = sorted(set(referenced) - set(providers))
        if unknown:
            failures.append(f"{scenario_id}: unknown providers {unknown}")
        contract_id = scenario.get("handoff_contract_id")
        if contract_id is not None and contract_id not in handoff_contracts:
            failures.append(f"{scenario_id}: unknown handoff contract {contract_id!r}")
        elif contract_id is not None:
            target_owner = handoff_contracts[contract_id].get("target_owner")
            owner_candidates = scenario.get("owner_candidates", [])
            if not owner_candidates or owner_candidates[0] != target_owner:
                failures.append(f"{scenario_id}: handoff target is not the first owner candidate")
        if scenario.get("validator_required") is True and not scenario.get("validator_candidates"):
            failures.append(f"{scenario_id}: required validator has no candidates")
        staged_passes = scenario.get("staged_passes")
        if staged_passes is not None:
            if scenario_id != "asset_foundation" or not isinstance(staged_passes, list):
                failures.append(f"{scenario_id}: staged passes are only valid for asset foundation")
                continue
            pass_ids = [item.get("pass_id") for item in staged_passes if isinstance(item, dict)]
            if pass_ids != ASSET_FOUNDATION_STAGE_IDS:
                failures.append("asset foundation staged pass IDs drifted")
            for item in staged_passes:
                if not isinstance(item, dict):
                    failures.append("asset foundation pass entry must be an object")
                    continue
                pass_references = [
                    *item.get("owner_candidates", []),
                    *item.get("validator_candidates", []),
                ]
                for candidates in item.get("collaborator_gaps", {}).values():
                    pass_references.extend(candidates)
                unknown_pass = sorted(set(pass_references) - set(providers))
                if unknown_pass:
                    failures.append(f"asset foundation {item.get('pass_id')}: unknown providers {unknown_pass}")
                if len(item.get("validator_candidates", [])) > 1:
                    failures.append(f"asset foundation {item.get('pass_id')}: more than one validator")
    script_scenario = next(
        (item for item in scenarios if isinstance(item, dict) and item.get("scenario_id") == "script_to_seedance"),
        {},
    )
    if script_scenario.get("requires_asset_foundation_gate") is not True:
        failures.append("script_to_seedance must require the asset foundation gate")
    missing = registry.get("missing_legacy_handoffs")
    if missing != [
        "ai-video-prompt-director",
        "creative-casebook",
        "capsule-engine",
        "watch",
    ]:
        failures.append("known missing legacy handoffs drifted")
    return failures


def _bounded_utf8(path: Path, limit: int, label: str) -> tuple[str, bytes]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SkillStackError(f"{label}_unavailable") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise SkillStackError(f"{label}_not_regular")
    if metadata.st_size > limit:
        raise SkillStackError(f"{label}_too_large")
    data = path.read_bytes()
    if len(data) != metadata.st_size:
        raise SkillStackError(f"{label}_changed_while_reading")
    if b"\x00" in data:
        raise SkillStackError(f"{label}_binary")
    try:
        return data.decode("utf-8"), data
    except UnicodeDecodeError as exc:
        raise SkillStackError(f"{label}_not_utf8") from exc


def _parse_frontmatter(text: str, max_bytes: int) -> tuple[dict[str, str], int]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        raise SkillStackError("frontmatter_missing")
    encoded = normalized.encode("utf-8")
    boundary = encoded.find(b"\n---\n", 4, min(len(encoded), max_bytes + 6))
    if boundary < 0:
        raise SkillStackError("frontmatter_unbounded_or_too_large")
    front_bytes = encoded[4:boundary]
    if len(front_bytes) > max_bytes:
        raise SkillStackError("frontmatter_too_large")
    lines = front_bytes.decode("utf-8").splitlines()
    result: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line[:1].isspace() or ":" not in line:
            raise SkillStackError("frontmatter_not_flat")
        key, raw = line.split(":", 1)
        key = key.strip()
        value = raw.strip()
        if key not in {"name", "description"}:
            index += 1
            if not value:
                while index < len(lines) and (
                    not lines[index].strip() or lines[index][:1].isspace()
                ):
                    index += 1
            continue
        if value in {">", "|", ">-", "|-"}:
            chunks: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                chunks.append(lines[index].strip())
                index += 1
            result[key] = " ".join(chunk for chunk in chunks if chunk)
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
        index += 1
    if not ID_RE.fullmatch(result.get("name", "")) or not result.get("description", "").strip():
        raise SkillStackError("frontmatter_required_fields_invalid")
    return result, boundary + 5


def _frontmatter_probe(
    path: Path,
    *,
    frontmatter_limit: int,
    body_limit: int,
) -> tuple[dict[str, str], int, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SkillStackError("skill_body_unavailable") from exc
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise SkillStackError("skill_body_not_regular")
    if metadata.st_size > body_limit:
        raise SkillStackError("skill_body_too_large")
    with path.open("rb") as handle:
        probe = handle.read(frontmatter_limit + 16)
    if b"\x00" in probe:
        raise SkillStackError("skill_body_binary")
    normalized_probe = probe.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not normalized_probe.startswith(b"---\n"):
        raise SkillStackError("frontmatter_missing")
    boundary = normalized_probe.find(
        b"\n---\n",
        4,
        min(len(normalized_probe), frontmatter_limit + 6),
    )
    if boundary < 0:
        raise SkillStackError("frontmatter_unbounded_or_too_large")
    frontmatter_probe = normalized_probe[: boundary + 5]
    try:
        text = frontmatter_probe.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SkillStackError("skill_body_not_utf8") from exc
    frontmatter, front_bytes = _parse_frontmatter(text, frontmatter_limit)
    return frontmatter, front_bytes, metadata.st_size


def hydrate_entry(entry: CatalogEntry, registry: dict[str, Any]) -> CatalogEntry | None:
    if entry.body_loaded:
        return entry
    if entry.skill_file is None:
        return None
    text, data = _bounded_utf8(
        entry.skill_file,
        int(registry["discovery_contract"]["skill_body_bytes_max"]),
        "skill_body",
    )
    frontmatter, front_bytes = _parse_frontmatter(
        text,
        int(registry["discovery_contract"]["frontmatter_bytes_max"]),
    )
    if frontmatter["name"] != entry.skill_id:
        raise SkillStackError("selected_skill_identity_changed")
    return replace(
        entry,
        body_bytes=len(data),
        body_sha256=digest_bytes(data),
        frontmatter_bytes=front_bytes,
        body_loaded=True,
    )


def body_loader_for_roots(
    roots: Iterable[tuple[str, Path]],
    registry: dict[str, Any],
) -> BodyLoader:
    safe_roots: list[tuple[str, Path]] = []
    for source_type, raw_root in roots:
        try:
            if raw_root.is_symlink():
                continue
            resolved = raw_root.resolve(strict=True)
            if resolved.is_dir():
                safe_roots.append((source_type, resolved))
        except OSError:
            continue

    def load(skill_id: str, entry: CatalogEntry) -> CatalogEntry | None:
        if entry.skill_file is not None:
            try:
                parent = entry.skill_file.parent
                if parent.is_symlink() or entry.skill_file.is_symlink():
                    return None
                resolved_parent = parent.resolve(strict=True)
                if not any(resolved_parent.is_relative_to(root) for _source, root in safe_roots):
                    return None
            except OSError:
                return None
            return hydrate_entry(entry, registry)
        for source_type, root in safe_roots:
            candidate = root / skill_id / "SKILL.md"
            try:
                parent = candidate.parent
                if parent.is_symlink() or candidate.is_symlink():
                    continue
                resolved_parent = parent.resolve(strict=True)
                if not resolved_parent.is_relative_to(root):
                    continue
                frontmatter, front_bytes, body_bytes = _frontmatter_probe(
                    candidate,
                    frontmatter_limit=int(registry["discovery_contract"]["frontmatter_bytes_max"]),
                    body_limit=int(registry["discovery_contract"]["skill_body_bytes_max"]),
                )
                if frontmatter["name"] != skill_id:
                    continue
                bound = replace(
                    entry,
                    source_type=source_type,
                    skill_file=candidate,
                    body_bytes=body_bytes,
                    frontmatter_bytes=front_bytes,
                )
                return hydrate_entry(bound, registry)
            except (OSError, SkillStackError):
                continue
        return None

    return load


def _parse_openai_yaml(path: Path, max_bytes: int) -> dict[str, str]:
    text, _ = _bounded_utf8(path, max_bytes, "openai_yaml")
    if any(token in text for token in ("!!", "!include", "&anchor", "*anchor")):
        raise SkillStackError("openai_yaml_unsafe_yaml_feature")
    result: dict[str, str] = {}
    in_interface = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_interface = stripped == "interface:"
            continue
        if in_interface and indent >= 2 and ":" in stripped:
            key, raw = stripped.split(":", 1)
            if key in {"display_name", "short_description", "default_prompt"}:
                value = raw.strip().strip("'\"")
                if value:
                    result[key] = value
    return result


def discover_roots(
    roots: Iterable[tuple[str, Path]],
    registry: dict[str, Any],
) -> tuple[dict[str, CatalogEntry], list[dict[str, str]]]:
    contract = registry["discovery_contract"]
    body_max = int(contract["skill_body_bytes_max"])
    front_max = int(contract["frontmatter_bytes_max"])
    openai_max = int(contract["openai_yaml_bytes_max"])
    catalog: dict[str, CatalogEntry] = {}
    collided_ids: set[str] = set()
    rejected: list[dict[str, str]] = []
    for source_type, raw_root in roots:
        try:
            if raw_root.is_symlink():
                raise SkillStackError("root_symlink")
            root = raw_root.resolve(strict=True)
            if not root.is_dir():
                raise SkillStackError("root_not_directory")
        except SkillStackError as exc:
            rejected.append({"source_type": source_type, "reason": str(exc)})
            continue
        except OSError:
            rejected.append({"source_type": source_type, "reason": "root_unavailable"})
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name.casefold()):
            if child.name.startswith("."):
                continue
            try:
                if child.is_symlink() or not child.is_dir():
                    raise SkillStackError("skill_directory_not_regular")
                resolved = child.resolve(strict=True)
                if not resolved.is_relative_to(root):
                    raise SkillStackError("skill_path_escape")
                skill_file = child / "SKILL.md"
                frontmatter, front_bytes, body_bytes = _frontmatter_probe(
                    skill_file,
                    frontmatter_limit=front_max,
                    body_limit=body_max,
                )
                openai_metadata: dict[str, str] = {}
                openai_path = child / "agents/openai.yaml"
                if openai_path.exists() or openai_path.is_symlink():
                    if (child / "agents").is_symlink():
                        raise SkillStackError("agents_directory_symlink")
                    openai_metadata = _parse_openai_yaml(openai_path, openai_max)
                skill_id = frontmatter["name"]
                if skill_id in collided_ids:
                    raise SkillStackError("duplicate_skill_id")
                if skill_id in catalog:
                    catalog.pop(skill_id, None)
                    collided_ids.add(skill_id)
                    raise SkillStackError("duplicate_skill_id")
                catalog[skill_id] = CatalogEntry(
                    skill_id=skill_id,
                    source_type=source_type,
                    skill_file=skill_file,
                    body_bytes=body_bytes,
                    body_sha256=None,
                    frontmatter_bytes=front_bytes,
                    openai_metadata=openai_metadata,
                    body_loaded=False,
                )
            except SkillStackError as exc:
                rejected.append({"skill_id": child.name if ID_RE.fullmatch(child.name) else "invalid", "source_type": source_type, "reason": str(exc)})
            except OSError:
                rejected.append({"skill_id": child.name if ID_RE.fullmatch(child.name) else "invalid", "source_type": source_type, "reason": "skill_unavailable"})
    return catalog, rejected


def load_host_catalog(path: Path, registry: dict[str, Any]) -> tuple[dict[str, CatalogEntry], list[dict[str, str]]]:
    text, _ = _bounded_utf8(
        path,
        int(registry["discovery_contract"]["host_catalog_bytes_max"]),
        "host_catalog",
    )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SkillStackError("invalid host catalog JSON") from exc
    raw_entries = payload.get("skills") if isinstance(payload, dict) else None
    if not isinstance(raw_entries, list):
        raise SkillStackError("host catalog must contain a skills array")
    if len(raw_entries) > 4096:
        raise SkillStackError("host catalog entry limit exceeded")
    known = set(normalize_providers(registry))
    catalog: dict[str, CatalogEntry] = {}
    collided_ids: set[str] = set()
    rejected: list[dict[str, str]] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            rejected.append({"source_type": "host_catalog", "reason": "catalog_entry_not_object"})
            continue
        raw_skill_id = raw.get("skill_id") or raw.get("name")
        safe_skill_id = raw_skill_id if isinstance(raw_skill_id, str) and ID_RE.fullmatch(raw_skill_id) else "invalid"
        serialized = json.dumps(raw, ensure_ascii=False)
        if any(marker in serialized for marker in PRIVATE_PATH_MARKERS) or any(
            key in raw for key in ("path", "skill_path", "root", "cwd")
        ):
            rejected.append({"skill_id": safe_skill_id, "source_type": "host_catalog", "reason": "catalog_private_path_forbidden"})
            continue
        skill_id = raw.get("skill_id") or raw.get("name")
        description = raw.get("description")
        available = raw.get("available", True)
        source_type = raw.get("source_type", "host_catalog")
        capability_policy = None
        if isinstance(skill_id, str) and skill_id not in known:
            capability_policy = normalize_dynamic_provider(
                skill_id,
                raw.get("capability_policy"),
                registry,
            )
        if (
            not isinstance(skill_id, str)
            or not ID_RE.fullmatch(skill_id)
            or not isinstance(description, str)
            or not description.strip()
            or not isinstance(source_type, str)
            or not ID_RE.fullmatch(source_type)
            or available is not True
            or (skill_id not in known and capability_policy is None)
            or (skill_id in known and raw.get("capability_policy") is not None)
        ):
            rejected.append({"skill_id": safe_skill_id, "source_type": "host_catalog", "reason": "catalog_entry_invalid_or_unavailable"})
            continue
        if skill_id in collided_ids:
            rejected.append({"skill_id": skill_id, "source_type": "host_catalog", "reason": "duplicate_skill_id"})
            continue
        if skill_id in catalog:
            catalog.pop(skill_id, None)
            collided_ids.add(skill_id)
            rejected.append({"skill_id": skill_id, "source_type": "host_catalog", "reason": "duplicate_skill_id"})
            continue
        metadata_bytes = len(
            json.dumps(
                {
                    "skill_id": skill_id,
                    "description": description,
                    "capability_policy": raw.get("capability_policy"),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if metadata_bytes > int(registry["discovery_contract"]["frontmatter_bytes_max"]):
            rejected.append({"skill_id": skill_id, "source_type": "host_catalog", "reason": "catalog_frontmatter_too_large"})
            continue
        catalog[skill_id] = CatalogEntry(
            skill_id=skill_id,
            source_type=str(source_type),
            skill_file=None,
            body_bytes=0,
            body_sha256=None,
            frontmatter_bytes=metadata_bytes,
            openai_metadata={},
            body_loaded=False,
            capability_policy=capability_policy,
        )
    return catalog, rejected


def _scenario_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["scenario_id"]: item for item in registry["scenarios"]}


def _normalized_model_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def _targets_seedance25(intent: dict[str, Any]) -> bool:
    capability_card_id = str(intent.get("capability_card_id", "")).strip()
    if capability_card_id:
        return capability_card_id == "seedance_2_5_official_launch"
    return _normalized_model_token(intent.get("target_model")) == "seedance25"


def _eligible(
    skill_id: str,
    role: str,
    mode: str,
    media: str,
    stage: str,
    deliverable_layer: str,
    explicit: set[str],
    providers: dict[str, dict[str, Any]],
    catalog: dict[str, CatalogEntry],
    available_tools: set[str],
) -> bool:
    provider = providers.get(skill_id)
    if not provider or role not in provider["provider_roles"]:
        return False
    if skill_id != "dircreative" and skill_id not in catalog:
        return False
    if provider["explicit_only"] and skill_id not in explicit:
        return False
    if mode not in provider["mode_allowlist"]:
        return False
    if not set(provider.get("tool_dependencies", [])) <= available_tools:
        return False
    if (
        role == "execution_adapter"
        and provider.get("may_cost_money") is True
        and provider.get("separate_payment_action") is not False
    ):
        return False
    media_gate = set(provider["media_gate"])
    if "any" not in media_gate and media not in media_gate:
        return False
    trigger_stages = set(provider.get("trigger_stages", []))
    if "any" not in trigger_stages and stage not in trigger_stages:
        return False
    deliverable_layers = set(provider.get("deliverable_layers", []))
    if "any" not in deliverable_layers and deliverable_layer not in deliverable_layers:
        return False
    return True


def _base_context_bytes(
    route_id: str,
    routing: dict[str, Any],
    *,
    include_required: bool = True,
) -> tuple[int, int]:
    routes = routing.get("routes", {})
    route = routes.get(route_id)
    if not isinstance(route, dict):
        raise SkillStackError(f"unknown route_id: {route_id}")
    paths = [MAIN_SKILL, resolve_runtime_path(route["route_card"])]
    if include_required:
        paths.extend(resolve_runtime_path(relative) for relative in route.get("required_files", []))
    for path in paths:
        if not path.is_file():
            raise SkillStackError(f"missing context file: {path.name}")
    return sum(len(path.read_bytes()) for path in paths), len(paths)


def _slot(skill_id: str, role: str, provider: dict[str, Any], entry: CatalogEntry | None) -> dict[str, Any]:
    if skill_id == "dircreative":
        return {
            "skill_id": skill_id,
            "role": role,
            "perspective": provider["perspective"],
            "status": "built_in",
            "body_bytes": 0,
            "body_sha256": None,
        }
    assert entry is not None
    if not entry.body_loaded or entry.body_sha256 is None:
        raise SkillStackError(f"provider body was not read: {skill_id}")
    slot = {
        "skill_id": skill_id,
        "role": role,
        "perspective": provider["perspective"],
        "status": "materialized",
        "body_bytes": entry.body_bytes,
        "body_sha256": entry.body_sha256,
    }
    application_contract = provider.get("application_contract")
    if isinstance(application_contract, dict):
        slot["application_contract"] = dict(application_contract)
    return slot


def _metadata_bytes(slots: Iterable[dict[str, Any]]) -> int:
    compact = [
        {
            "skill_id": item["skill_id"],
            "role": item["role"],
            "perspective": item["perspective"],
            "status": item["status"],
            "body_bytes": item["body_bytes"],
            "body_sha256": item["body_sha256"],
            **(
                {"application_contract": item["application_contract"]}
                if isinstance(item.get("application_contract"), dict)
                else {}
            ),
        }
        for item in slots
    ]
    return len(json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _candidate_metadata_bytes(
    candidate_ids: Iterable[str],
    catalog: dict[str, CatalogEntry],
    providers: dict[str, dict[str, Any]],
) -> int:
    compact: list[dict[str, Any]] = []
    for skill_id in candidate_ids:
        provider = providers.get(skill_id)
        entry = catalog.get(skill_id)
        compact.append(
            {
                "skill_id": skill_id,
                "available": skill_id == "dircreative" or entry is not None,
                "frontmatter_bytes": entry.frontmatter_bytes if entry else 0,
                "roles": provider.get("provider_roles", []) if provider else [],
                "priority": provider.get("priority", 0) if provider else 0,
            }
        )
    return len(json.dumps(compact, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _render_skill_card(mode: str, slots: list[dict[str, Any]], suggested: list[str]) -> list[str]:
    used = [item for item in slots if item["status"] == "used" and item["role"] != "execution_adapter"]
    if not used and not suggested:
        return ["本次无需额外 Skill，DIRcreative 足够。"]
    if mode == "fast":
        if used:
            line = f"本次 Skill 配置：已用 `${used[0]['skill_id']}`"
        else:
            line = "本次 Skill 配置：DIRcreative 已完成"
        if suggested:
            line += f"；下一步建议 `${suggested[0]}`。"
        else:
            line += "。"
        return [line]
    lines = ["本次 Skill 配置"]
    role_labels = {
        "craft_owner": "主 Skill",
        "collaborator": "协作 Skill",
        "validator": "校验 Skill",
        "explicit_overlay": "显式 Overlay",
        "execution_adapter": "执行适配器",
    }
    for item in used:
        lines.append(f"- {role_labels[item['role']]}：`${item['skill_id']}` — 已实际读取并采用")
    if suggested and len(lines) < 5:
        lines.append("- 建议：" + "、".join(f"`${item}`" for item in suggested[:3]) + " — 未读取正文")
    return lines[:5]


def select_stack(
    intent: dict[str, Any],
    registry: dict[str, Any],
    routing: dict[str, Any],
    catalog: dict[str, CatalogEntry],
    *,
    route_context: ValidatedRouteContext,
    body_loader: BodyLoader | None = None,
) -> dict[str, Any]:
    providers = normalize_providers(registry)
    for entry in catalog.values():
        if entry.capability_policy is not None:
            providers[entry.skill_id] = entry.capability_policy
    scenarios = _scenario_map(registry)
    scenario_id = intent.get("scenario_id")
    if scenario_id not in scenarios:
        raise SkillStackError(f"unknown scenario_id: {scenario_id}")
    scenario = scenarios[scenario_id]
    intent = dict(intent)
    if scenario_id == "cinematic_storyboard_frames":
        downstream_use = intent.get("downstream_use")
        if (
            not isinstance(downstream_use, str)
            or downstream_use
            not in {"rough_planning", "clean_model_input", "full_preproduction"}
        ):
            raise SkillStackError("invalid cinematic_storyboard_frames downstream_use")
        if downstream_use in {"clean_model_input", "full_preproduction"}:
            scenario = {**scenario, "requires_asset_foundation_gate": True}
    capability_card_id = str(intent.get("capability_card_id", "")).strip()
    target_model = str(intent.get("target_model", "")).strip()
    if (
        scenario_id == "seedance25_prompt"
        and capability_card_id
        and capability_card_id != "seedance_2_5_official_launch"
    ):
        raise SkillStackError("seedance25_prompt_conflicts_with_exact_capability_card")
    if (
        scenario_id == "seedance25_prompt"
        and not capability_card_id
        and target_model
        and _normalized_model_token(target_model) != "seedance25"
    ):
        raise SkillStackError("seedance25_prompt_conflicts_with_target_model")
    seedance25_gap = "seedance25_authoring_method"
    requested_gaps = [gap for gap in intent.get("gaps", []) if gap != seedance25_gap]
    seedance25_target = scenario_id == "seedance25_prompt" or _targets_seedance25(intent)
    if (
        scenario_id == "script_to_seedance"
        and seedance25_target
    ):
        scenario = {
            **scenario,
            "collaborator_gaps": {
                **scenario.get("collaborator_gaps", {}),
                seedance25_gap: ["mr-li-seedance-25"],
            },
        }
        requested_gaps.append(seedance25_gap)
    elif scenario_id == "seedance25_prompt" and intent.get("emotion_priority") is True:
        scenario = {
            **scenario,
            "owner_candidates": ["seedance-25-emotion-prompt", "mr-li-seedance-25"],
            "collaborator_gaps": {
                **scenario.get("collaborator_gaps", {}),
                seedance25_gap: ["mr-li-seedance-25"],
            },
        }
        requested_gaps.append(seedance25_gap)
    if intent.get("performance_contract_locked") and scenario_id == "seedance25_prompt":
        requested_gaps = [gap for gap in requested_gaps if gap != "performance"]
    if scenario_id == "seedance25_prompt" and intent.get("needs_validation") is True:
        scenario = {**scenario, "validator_required": True}
    intent["gaps"] = list(dict.fromkeys(requested_gaps))
    staged_passes = scenario.get("staged_passes", [])
    active_asset_pass: dict[str, Any] | None = None
    active_asset_pass_id: str | None = None
    next_asset_pass_id: str | None = None
    staged_pass_count = len(staged_passes) if isinstance(staged_passes, list) else 0
    asset_pass_status = str(intent.get("asset_pass_status", "in_progress"))
    previous_asset_pass_verified = True
    staged_pass_blocked = False
    staged_pass_needs_followup = False
    if staged_pass_count:
        active_asset_pass_id = str(intent.get("asset_pass_id") or staged_passes[0].get("pass_id"))
        pass_index = next(
            (
                index
                for index, item in enumerate(staged_passes)
                if isinstance(item, dict) and item.get("pass_id") == active_asset_pass_id
            ),
            None,
        )
        if pass_index is None:
            raise SkillStackError(f"unknown asset pass id: {active_asset_pass_id}")
        active_asset_pass = staged_passes[pass_index]
        if pass_index + 1 < staged_pass_count:
            next_asset_pass_id = str(staged_passes[pass_index + 1].get("pass_id"))
        if pass_index > 0:
            previous_asset_pass_verified = (
                intent.get("previous_asset_pass_status") == "passed"
                and isinstance(intent.get("previous_stage_output_sha256"), str)
                and SHA_RE.fullmatch(intent["previous_stage_output_sha256"]) is not None
            )
        staged_pass_blocked = asset_pass_status == "failed" or not previous_asset_pass_verified
        staged_pass_needs_followup = not staged_pass_blocked and (
            asset_pass_status != "passed" or pass_index < staged_pass_count - 1
        )
        scenario = {
            **scenario,
            "stage": active_asset_pass.get("stage", scenario["stage"]),
            "owner_candidates": list(active_asset_pass.get("owner_candidates", [])),
            "collaborator_gaps": dict(active_asset_pass.get("collaborator_gaps", {})),
            "validator_candidates": list(active_asset_pass.get("validator_candidates", [])),
            "validator_required": active_asset_pass.get("validator_required", False),
        }
        if not intent.get("gaps"):
            intent["gaps"] = list(active_asset_pass.get("required_gaps", []))

    asset_foundation_gate_status = "not_required"
    asset_foundation_gate_blocked = False
    asset_foundation_gate_reason: str | None = None
    if scenario.get("requires_asset_foundation_gate") is True:
        requested_scope = set(intent.get("requested_shot_scope", []))
        allowed_scope = set(intent.get("asset_allowed_shot_scope", []))
        blocked_scope = set(intent.get("asset_blocked_shot_scope", []))
        stress_verdict = intent.get("asset_stress_verdict")
        if intent.get("asset_foundation_status") != "complete":
            asset_foundation_gate_reason = "asset_foundation_gate_required"
        elif stress_verdict not in {"certified", "conditional"}:
            asset_foundation_gate_reason = "asset_stress_verdict_not_compilable"
        elif (
            not requested_scope
            or not requested_scope.issubset(allowed_scope)
            or bool(requested_scope & blocked_scope)
        ):
            asset_foundation_gate_reason = "asset_scope_not_allowed"
        asset_foundation_gate_blocked = asset_foundation_gate_reason is not None
        asset_foundation_gate_status = "blocked" if asset_foundation_gate_blocked else "allowed"

    ledger_candidate_blocked = (
        scenario_id == "production_ledger"
        and intent.get("candidate_status") != "final_generation_candidate"
    )
    mode = intent.get("mode")
    if mode not in {"fast", "studio", "delivery"}:
        raise SkillStackError(f"invalid mode: {mode}")
    media = intent.get("media")
    allowed_media = set(scenario["media"])
    if not isinstance(media, str) or ("any" not in allowed_media and media not in allowed_media):
        raise SkillStackError(f"media does not match scenario: {media}")
    route_id = intent.get("route_id")
    route_config = routing.get("routes", {}).get(route_id, {})
    if route_config.get("mode") != mode:
        raise SkillStackError(f"route/mode mismatch: {route_id}/{mode}")
    if route_context.route_id != route_id or route_context.mode != mode:
        raise SkillStackError("Skill Stack route does not match validated primary route")
    internal_base_bytes, internal_base_files = _base_context_bytes(route_id, routing)
    external_base_bytes, external_base_files = _base_context_bytes(
        route_id,
        routing,
        include_required=mode == "delivery",
    )
    handoff_contract_id = scenario.get("handoff_contract_id")
    handoff_contract: dict[str, Any] | None = None
    if handoff_contract_id is not None:
        contract = registry.get("handoff_contracts", {}).get(handoff_contract_id)
        if not isinstance(contract, dict):
            raise SkillStackError(f"unknown handoff contract: {handoff_contract_id}")
        handoff_contract = {
            "contract_id": handoff_contract_id,
            "contract_reference": contract["reference"],
            "source_owner": contract["source_owner"],
            "target_owner": contract["target_owner"],
            "authority": contract["authority"],
            "required_inputs": contract["required_inputs"],
            "output_owner": contract["output_owner"],
            "slot_crosswalk": contract["slot_crosswalk"],
        }
        if contract.get("reference_pack"):
            handoff_contract["reference_pack"] = list(contract["reference_pack"])
        if contract.get("output_binding"):
            handoff_contract["output_binding"] = contract["output_binding"]
        external_base_bytes += len(
            json.dumps(handoff_contract, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
    handoff_read_requests: list[dict[str, Any]] = []
    if handoff_contract is not None:
        output_binding = handoff_contract.get("output_binding", {})
        requested_paths = [
            ("contract_reference", handoff_contract.get("contract_reference")),
            ("output_schema", output_binding.get("schema")),
            ("output_validator", output_binding.get("validator")),
        ]
        for role, relative_path in requested_paths:
            path = resolve_runtime_path(str(relative_path))
            payload = path.read_bytes()
            handoff_read_requests.append(
                {
                    "role": role,
                    "relative_path": str(relative_path),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                    "context_scope": "isolated_handoff_contract",
                    "host_action": "independent_full_read_hash_verify_and_apply_before_handoff",
                }
            )
    base_bytes, base_files = external_base_bytes, external_base_files
    budget = int(routing["performance_budgets"][mode]["loaded_context_bytes_max"])
    file_budget = int(routing["performance_budgets"][mode]["loaded_context_files_max"])
    mode_contract = registry["mode_contracts"][mode]
    body_cap = int(mode_contract["provider_bodies_max"])
    collaborators_cap = int(mode_contract["collaborators_max"])
    raw_explicit = intent.get("explicit_overlays", [])
    raw_tools = intent.get("available_tools", [])
    if not isinstance(raw_explicit, list) or not all(isinstance(item, str) for item in raw_explicit):
        raise SkillStackError("explicit_overlays must be a string array")
    if not isinstance(raw_tools, list) or not all(isinstance(item, str) for item in raw_tools):
        raise SkillStackError("available_tools must be a string array")
    explicit_ordered = list(dict.fromkeys(raw_explicit))
    explicit = set(explicit_ordered)
    available_tools = set(raw_tools)
    final_owner = route_context.final_owner
    if intent.get("execution_context") == "orchestrated_worker" and final_owner != "adco":
        raise SkillStackError("orchestrated_worker requires a validated ADCO primary route")
    if final_owner == "adco" and intent.get("real_side_effect"):
        raise SkillStackError("ADCO worker cannot execute packaging, generation, or external-write adapters")

    default_owner_candidates = list(scenario.get("owner_candidates", []))
    owner_capabilities = {
        capability
        for skill_id in default_owner_candidates
        for capability in providers[skill_id].get("capabilities", [])
    }
    dynamic_owner_candidates = sorted(
        (
            skill_id
            for skill_id, provider in providers.items()
            if skill_id not in default_owner_candidates
            and skill_id in catalog
            and catalog[skill_id].capability_policy is not None
            and "craft_owner" in provider.get("provider_roles", [])
            and owner_capabilities & set(provider.get("capabilities", []))
        ),
        key=lambda skill_id: (-int(providers[skill_id]["priority"]), skill_id),
    )
    owner_candidates = [*default_owner_candidates, *dynamic_owner_candidates]

    def gap_candidates(gap: str) -> list[str]:
        defaults = list(scenario.get("collaborator_gaps", {}).get(gap, []))
        capabilities = {
            capability
            for skill_id in defaults
            for capability in providers[skill_id].get("capabilities", [])
        }
        dynamic = sorted(
            (
                skill_id
                for skill_id, provider in providers.items()
                if skill_id not in defaults
                and skill_id in catalog
                and catalog[skill_id].capability_policy is not None
                and "collaborator" in provider.get("provider_roles", [])
                and capabilities & set(provider.get("capabilities", []))
            ),
            key=lambda skill_id: (-int(providers[skill_id]["priority"]), skill_id),
        )
        return [*defaults, *dynamic]

    default_validator_candidates = list(scenario.get("validator_candidates", []))
    validator_capabilities = {
        capability
        for skill_id in default_validator_candidates
        for capability in providers[skill_id].get("capabilities", [])
    }
    dynamic_validator_candidates = sorted(
        (
            skill_id
            for skill_id, provider in providers.items()
            if skill_id not in default_validator_candidates
            and skill_id in catalog
            and catalog[skill_id].capability_policy is not None
            and "validator" in provider.get("provider_roles", [])
            and validator_capabilities & set(provider.get("capabilities", []))
        ),
        key=lambda skill_id: (-int(providers[skill_id]["priority"]), skill_id),
    )
    validator_candidates = [*default_validator_candidates, *dynamic_validator_candidates]

    requested_ids: list[str] = []
    requested_ids.extend(owner_candidates)
    for gap in intent.get("gaps", []):
        requested_ids.extend(gap_candidates(gap))
    if intent.get("needs_validation"):
        requested_ids.extend(validator_candidates)
    requested_ids.extend(explicit_ordered)
    if intent.get("real_side_effect"):
        requested_ids.extend(scenario.get("execution_adapters", []))
    candidate_limit = int(registry["discovery_contract"]["candidate_limit"])
    candidate_pool = list(dict.fromkeys(requested_ids))[:candidate_limit]
    candidate_set = set(candidate_pool)
    candidate_metadata_bytes = _candidate_metadata_bytes(candidate_pool, catalog, providers)

    slots: list[dict[str, Any]] = []
    suggestions: list[str] = []
    reason_codes: list[str] = []
    if staged_pass_blocked:
        reason_codes.append(
            "asset_pass_failed" if asset_pass_status == "failed" else "previous_asset_pass_unverified"
        )
    if asset_foundation_gate_reason is not None:
        reason_codes.append(asset_foundation_gate_reason)
    if ledger_candidate_blocked:
        reason_codes.append("ledger_candidate_not_final")
    materialization_failures: dict[str, str] = {}
    reference_request_cache: dict[str, list[dict[str, Any]]] = {}

    def materialize(skill_id: str) -> bool:
        if skill_id == "dircreative":
            return True
        entry = catalog.get(skill_id)
        if entry is None:
            return False
        if entry.body_loaded:
            return True
        if body_loader is None:
            materialization_failures[skill_id] = "provider_body_not_bound"
            return False
        try:
            loaded = body_loader(skill_id, entry)
        except SkillStackError as exc:
            materialization_failures[skill_id] = str(exc)
            return False
        if loaded is None or not loaded.body_loaded:
            materialization_failures[skill_id] = "provider_body_unavailable"
            return False
        catalog[skill_id] = loaded
        return True

    def provider_reference_requests(skill_id: str) -> list[dict[str, Any]]:
        if skill_id in reference_request_cache:
            return reference_request_cache[skill_id]
        reference_pack = list(providers.get(skill_id, {}).get("reference_pack", []))
        if handoff_contract and handoff_contract.get("target_owner") == skill_id:
            reference_pack.extend(handoff_contract.get("reference_pack", []))
        reference_pack = list(dict.fromkeys(reference_pack))
        if not reference_pack:
            reference_request_cache[skill_id] = []
            return []
        entry = catalog.get(skill_id)
        if entry is None or entry.skill_file is None:
            raise SkillStackError("isolated provider reference root is unavailable")
        skill_root = entry.skill_file.parent
        if skill_root.is_symlink():
            raise SkillStackError("isolated provider reference root must not be a symlink")
        resolved_root = skill_root.resolve(strict=True)
        requests: list[dict[str, Any]] = []
        for relative in reference_pack:
            parsed = PurePosixPath(relative)
            if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
                raise SkillStackError("isolated provider reference path is invalid")
            candidate = skill_root.joinpath(*parsed.parts)
            cursor = skill_root
            for part in parsed.parts:
                cursor = cursor / part
                metadata = cursor.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    raise SkillStackError("isolated provider reference path traverses a symlink")
            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(resolved_root):
                raise SkillStackError("isolated provider reference path escapes provider root")
            _text, data = _bounded_utf8(
                resolved,
                int(registry["discovery_contract"]["skill_body_bytes_max"]),
                "isolated_provider_reference",
            )
            requests.append(
                {
                    "skill_id": skill_id,
                    "relative_path": relative,
                    "bytes": len(data),
                    "sha256": digest_bytes(data),
                    "context_scope": "isolated_craft_contract",
                    "host_action": "primary_host_read_hash_verify_and_apply_when_provider_routes_here",
                }
            )
        reference_request_cache[skill_id] = requests
        return requests

    def eligible(skill_id: str, role: str) -> bool:
        if skill_id not in candidate_set and skill_id != "dircreative":
            return False
        provider = providers.get(skill_id)
        if provider is None:
            return False
        if not _eligible(
            skill_id,
            role,
            mode,
            media,
            str(scenario["stage"]),
            route_context.deliverable_layer,
            explicit,
            providers,
            catalog,
            available_tools,
        ):
            return False
        return materialize(skill_id)

    def can_add(skill_id: str, role: str) -> bool:
        provider = providers[skill_id]
        entry = catalog.get(skill_id)
        slot = _slot(skill_id, role, provider, entry)
        if role == "craft_owner" and provider.get("context_cost") == "isolated_craft_contract":
            slot["context_scope"] = "isolated_craft_contract"
        if role == "collaborator" and provider.get("context_cost") == "isolated_handoff_contract":
            slot["context_scope"] = "isolated_handoff_contract"
        if (
            role == "validator"
            and provider.get("validator_context_cost") == "isolated_validator_contract"
            and (
                scenario.get("validator_required") is True
                or provider.get("application_contract", {}).get("authority")
                == "diagnostic_only"
            )
        ):
            slot["context_scope"] = "isolated_validator_contract"
        future = [*slots, slot]
        bodies = sum(1 for item in future if item["status"] in {"materialized", "eligible_after_gate"})
        isolated_craft = [
            item for item in future if item.get("context_scope") == "isolated_craft_contract"
        ]
        isolated_craft_bytes = sum(
            int(item["body_bytes"]) + _metadata_bytes([item]) for item in isolated_craft
        )
        for item in isolated_craft:
            try:
                requests = provider_reference_requests(item["skill_id"])
            except (OSError, SkillStackError) as exc:
                materialization_failures[item["skill_id"]] = str(exc)
                return False
            isolated_craft_bytes += sum(int(request["bytes"]) for request in requests)
            isolated_craft_bytes += len(
                json.dumps(requests, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
        isolated_craft_budget = int(mode_contract.get("isolated_craft_context_bytes_max", 0))
        isolated_validators = [
            item for item in future if item.get("context_scope") == "isolated_validator_contract"
        ]
        isolated_validator_bytes = sum(
            int(item["body_bytes"]) + _metadata_bytes([item]) for item in isolated_validators
        )
        isolated_validator_budget = int(
            mode_contract.get("isolated_validator_context_bytes_max", 0)
        )
        isolated_handoffs = [
            item for item in future if item.get("context_scope") == "isolated_handoff_contract"
        ]
        isolated_handoff_bytes = sum(
            int(item["body_bytes"]) + _metadata_bytes([item]) for item in isolated_handoffs
        )
        isolated_handoff_budget = int(mode_contract.get("isolated_handoff_context_bytes_max", 0))
        total_bytes = (
            base_bytes
            + candidate_metadata_bytes
            + sum(
                int(item["body_bytes"])
                for item in future
                if item.get("context_scope") not in ISOLATED_CONTEXT_SCOPES
            )
            + _metadata_bytes(
                [
                    item
                    for item in future
                    if item.get("context_scope") not in ISOLATED_CONTEXT_SCOPES
                ]
            )
        )
        main_bodies = bodies - len(isolated_craft) - len(isolated_validators) - len(isolated_handoffs)
        total_files = base_files + main_bodies
        return (
            bodies <= body_cap
            and total_bytes <= budget
            and total_files <= file_budget
            and len(isolated_craft) <= 1
            and len(isolated_validators) <= 1
            and len(isolated_handoffs) <= 1
            and (
                not isolated_craft
                or (bool(isolated_craft_budget) and isolated_craft_bytes <= isolated_craft_budget)
            )
            and (
                not isolated_validators
                or (
                    bool(isolated_validator_budget)
                    and isolated_validator_bytes <= isolated_validator_budget
                )
            )
            and (
                not isolated_handoffs
                or (bool(isolated_handoff_budget) and isolated_handoff_bytes <= isolated_handoff_budget)
            )
        )

    reserve_for_isolated_adapter = mode == "delivery" and bool(intent.get("real_side_effect")) and any(
        skill_id in candidate_set
        and providers.get(skill_id, {}).get("context_cost") == "isolated_host_tool_contract"
        and _eligible(
            skill_id,
            "execution_adapter",
            mode,
            media,
            str(scenario["stage"]),
            route_context.deliverable_layer,
            explicit,
            providers,
            catalog,
            available_tools,
        )
        for skill_id in scenario.get("execution_adapters", [])
    )
    owner_id: str | None = None
    if reserve_for_isolated_adapter:
        reason_codes.append("delivery_body_reserved_for_execution_adapter")
        suggestions.extend(skill_id for skill_id in owner_candidates if skill_id in catalog)
        if not intent.get("disable_dir_fallback"):
            owner_id = "dircreative"
    else:
        for skill_id in owner_candidates:
            if eligible(skill_id, "craft_owner") and can_add(skill_id, "craft_owner"):
                owner_id = skill_id
                break
            if skill_id in catalog:
                suggestions.append(skill_id)

    if owner_id is None:
        if intent.get("disable_dir_fallback"):
            reason_codes.append("no_eligible_craft_owner")
            return {
                "status": "blocked",
                "reason_codes": reason_codes,
                "candidate_count": len(candidate_pool),
                "artifact_before_skill_card": True,
                "final_artifact_owner": final_owner,
                "final_state_owner": final_owner,
                "execution_performed": False,
                "generated": False,
            }
        owner_id = "dircreative"
        reason_codes.append("dircreative_fallback")
        base_bytes, base_files = internal_base_bytes, internal_base_files
    elif owner_id == "dircreative":
        base_bytes, base_files = internal_base_bytes, internal_base_files
    owner_slot = _slot(owner_id, "craft_owner", providers[owner_id], catalog.get(owner_id))
    if providers[owner_id].get("context_cost") == "isolated_craft_contract":
        owner_slot["context_scope"] = "isolated_craft_contract"
    if owner_id == "dircreative":
        trimmed = False
        while candidate_pool and (
            base_bytes + candidate_metadata_bytes + _metadata_bytes([owner_slot]) > budget
        ):
            dropped = candidate_pool.pop()
            candidate_set.discard(dropped)
            candidate_metadata_bytes = _candidate_metadata_bytes(candidate_pool, catalog, providers)
            if dropped != "dircreative":
                suggestions.append(dropped)
            trimmed = True
        if base_bytes + candidate_metadata_bytes + _metadata_bytes([owner_slot]) > budget:
            raise SkillStackError("dircreative fallback cannot fit the mode context budget")
        if trimmed:
            reason_codes.append("candidate_pool_trimmed_for_fallback_budget")
    slots.append(owner_slot)

    for overlay_id in explicit_ordered:
        if overlay_id not in {"liu-creative-workflow", "sophia-research-mode"}:
            continue
        if eligible(overlay_id, "explicit_overlay") and can_add(overlay_id, "explicit_overlay"):
            slots.append(_slot(overlay_id, "explicit_overlay", providers[overlay_id], catalog[overlay_id]))
        else:
            suggestions.append(overlay_id)
            reason_codes.append(f"{overlay_id}_not_loaded")
    if "ai-visual-production-director" in explicit:
        reason_codes.append("nested_controller_downgraded_to_reference_only")

    collaborator_count = 0
    selected_ids = {item["skill_id"] for item in slots}
    occupied_capabilities = set(providers[owner_id].get("capabilities", []))
    for gap in intent.get("gaps", []):
        if mode == "fast" or collaborator_count >= collaborators_cap:
            for skill_id in gap_candidates(gap):
                if skill_id not in selected_ids:
                    suggestions.append(skill_id)
            continue
        for skill_id in gap_candidates(gap):
            if skill_id in selected_ids:
                continue
            overlaps = occupied_capabilities & set(providers[skill_id].get("capabilities", []))
            if overlaps:
                suggestions.append(skill_id)
                reason_codes.append(f"overlapping_capability_skipped:{skill_id}")
                continue
            if eligible(skill_id, "collaborator") and can_add(skill_id, "collaborator"):
                collaborator_slot = _slot(
                    skill_id,
                    "collaborator",
                    providers[skill_id],
                    catalog[skill_id],
                )
                if providers[skill_id].get("context_cost") == "isolated_handoff_contract":
                    collaborator_slot["context_scope"] = "isolated_handoff_contract"
                slots.append(collaborator_slot)
                selected_ids.add(skill_id)
                occupied_capabilities.update(providers[skill_id].get("capabilities", []))
                collaborator_count += 1
                break
            if skill_id in catalog:
                suggestions.append(skill_id)

    validator: dict[str, Any] | None = None
    if intent.get("needs_validation"):
        for skill_id in validator_candidates:
            if skill_id in selected_ids:
                continue
            if eligible(skill_id, "validator") and can_add(skill_id, "validator"):
                validator = _slot(skill_id, "validator", providers[skill_id], catalog[skill_id])
                if (
                    providers[skill_id].get("validator_context_cost")
                    == "isolated_validator_contract"
                    and (
                        scenario.get("validator_required") is True
                        or providers[skill_id]
                        .get("application_contract", {})
                        .get("authority")
                        == "diagnostic_only"
                    )
                ):
                    validator["context_scope"] = "isolated_validator_contract"
                slots.append(validator)
                selected_ids.add(skill_id)
                break
            if skill_id in catalog:
                suggestions.append(skill_id)

    requested_gaps = [item for item in intent.get("gaps", []) if isinstance(item, str)]
    selected_capabilities = {
        capability
        for item in slots
        for capability in providers[item["skill_id"]].get("capabilities", [])
    }
    covered_gaps = [gap for gap in requested_gaps if gap in selected_capabilities]
    missing_gaps = [gap for gap in requested_gaps if gap not in selected_capabilities]
    validation_required_missing = (
        scenario.get("validator_required") is True and validator is None
    )
    if validation_required_missing:
        reason_codes.append("required_validator_unavailable")
    if scenario.get("requires_complete_gaps_before_downstream") is True and missing_gaps:
        reason_codes.append("required_asset_foundation_gaps_missing")

    gate: str | None = None
    adapter: dict[str, Any] | None = None
    if intent.get("real_side_effect"):
        side_effect_kind = intent.get("side_effect_kind", "generation")
        for skill_id in scenario.get("execution_adapters", []):
            if skill_id not in candidate_set:
                continue
            if not _eligible(
                skill_id,
                "execution_adapter",
                mode,
                media,
                str(scenario["stage"]),
                route_context.deliverable_layer,
                explicit,
                providers,
                catalog,
                available_tools,
            ):
                continue
            required_gate = (
                "client_delivery_approval"
                if side_effect_kind in {"client_delivery", "publish", "external_send"}
                else providers[skill_id].get("required_gate") or "generation_authorization"
            )
            if required_gate not in route_context.granted_gates:
                gate = required_gate
                suggestions.append(skill_id)
                reason_codes.append("execution_adapter_waits_for_authorization")
                break
            if not materialize(skill_id):
                suggestions.append(skill_id)
                reason_codes.append("execution_adapter_body_unavailable")
                continue
            existing = next((item for item in slots if item["skill_id"] == skill_id), None)
            if existing is not None:
                adapter = {
                    **existing,
                    "role": "execution_adapter",
                    "status": "eligible_after_gate",
                    "body_bytes": 0,
                    "reuses_loaded_body": True,
                }
                break
            if providers[skill_id].get("context_cost") == "isolated_host_tool_contract":
                isolated = _slot(
                    skill_id,
                    "execution_adapter",
                    providers[skill_id],
                    catalog[skill_id],
                )
                isolated["status"] = "eligible_after_gate"
                isolated["context_scope"] = "isolated_host_tool_contract"
                isolated_bytes = int(isolated["body_bytes"]) + _metadata_bytes([isolated])
                isolated_budget = int(mode_contract.get("execution_adapter_context_bytes_max", 0))
                if isolated_budget and isolated_bytes <= isolated_budget:
                    adapter = isolated
                    break
                suggestions.append(skill_id)
                reason_codes.append("execution_adapter_isolated_context_unavailable")
                continue
            if can_add(skill_id, "execution_adapter"):
                adapter = _slot(skill_id, "execution_adapter", providers[skill_id], catalog[skill_id])
                adapter["status"] = "eligible_after_gate"
                slots.append(adapter)
                break
            suggestions.append(skill_id)
            reason_codes.append("execution_adapter_context_unavailable")

        if gate is None and adapter is None:
            reason_codes.append("execution_adapter_unavailable")

    loaded_body_ids = list(
        dict.fromkeys(
            [item["skill_id"] for item in slots if item["status"] in {"materialized", "eligible_after_gate"}]
            + (
                [adapter["skill_id"]]
                if adapter is not None
                and adapter.get("context_scope") == "isolated_host_tool_contract"
                else []
            )
        )
    )
    reference_read_requests = [
        request
        for item in slots
        if item.get("context_scope") == "isolated_craft_contract"
        for request in provider_reference_requests(str(item["skill_id"]))
    ]
    isolated_craft_reference_bytes = sum(
        int(request["bytes"]) for request in reference_read_requests
    ) + (
        len(
            json.dumps(
                reference_read_requests,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if reference_read_requests
        else 0
    )
    provider_body_bytes = sum(
        int(item["body_bytes"])
        for item in slots
        if item.get("context_scope") not in ISOLATED_CONTEXT_SCOPES
    )
    selected_metadata_bytes = _metadata_bytes(
        [
            item
            for item in slots
            if item.get("context_scope") not in ISOLATED_CONTEXT_SCOPES
        ]
    )
    isolated_craft_context_bytes = sum(
        int(item["body_bytes"]) + _metadata_bytes([item])
        for item in slots
        if item.get("context_scope") == "isolated_craft_contract"
    ) + isolated_craft_reference_bytes
    isolated_validator_context_bytes = sum(
        int(item["body_bytes"]) + _metadata_bytes([item])
        for item in slots
        if item.get("context_scope") == "isolated_validator_contract"
    )
    isolated_handoff_context_bytes = sum(
        int(item["body_bytes"]) + _metadata_bytes([item])
        for item in slots
        if item.get("context_scope") == "isolated_handoff_contract"
    ) + sum(int(item["bytes"]) for item in handoff_read_requests) + (
        len(
            json.dumps(
                handoff_read_requests,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if handoff_read_requests
        else 0
    )
    execution_adapter_context_bytes = (
        int(adapter["body_bytes"]) + _metadata_bytes([adapter])
        if adapter is not None and adapter.get("context_scope") == "isolated_host_tool_contract"
        else 0
    )
    total_context_bytes = base_bytes + candidate_metadata_bytes + provider_body_bytes + selected_metadata_bytes
    if total_context_bytes > budget:
        raise SkillStackError("selected stack exceeds total context budget")
    if isolated_craft_context_bytes > int(mode_contract.get("isolated_craft_context_bytes_max", 0)):
        raise SkillStackError("selected isolated craft context exceeds its budget")
    if isolated_validator_context_bytes > int(
        mode_contract.get("isolated_validator_context_bytes_max", 0)
    ):
        raise SkillStackError("selected isolated validator context exceeds its budget")
    if isolated_handoff_context_bytes > int(
        mode_contract.get("isolated_handoff_context_bytes_max", 0)
    ):
        raise SkillStackError("selected isolated handoff context exceeds its budget")
    if len(loaded_body_ids) > body_cap:
        raise SkillStackError("selected stack exceeds provider body budget")
    if len([item for item in slots if item["role"] == "validator"]) > 1:
        raise SkillStackError("selected stack has more than one validator")
    if slots[0]["role"] != "craft_owner" or len([item for item in slots if item["role"] == "craft_owner"]) != 1:
        raise SkillStackError("selected stack must have exactly one craft owner")

    if intent.get("performance_contract_locked") and scenario_id == "seedance25_prompt":
        slots = [item for item in slots if item["skill_id"] != "performance-scene-director"]
        loaded_body_ids = list(
            dict.fromkeys(
                [item["skill_id"] for item in slots if item["status"] in {"materialized", "eligible_after_gate"}]
                + (
                    [adapter["skill_id"]]
                    if adapter is not None
                    and adapter.get("context_scope") == "isolated_host_tool_contract"
                    else []
                )
            )
        )
        reason_codes.append("performance_handoff_locked_no_second_creative_pass")
        provider_body_bytes = sum(
            int(item["body_bytes"])
            for item in slots
            if item.get("context_scope") not in ISOLATED_CONTEXT_SCOPES
        )
        selected_metadata_bytes = _metadata_bytes(
            [
                item
                for item in slots
                if item.get("context_scope") not in ISOLATED_CONTEXT_SCOPES
            ]
        )
        isolated_craft_context_bytes = sum(
            int(item["body_bytes"]) + _metadata_bytes([item])
            for item in slots
            if item.get("context_scope") == "isolated_craft_contract"
        ) + isolated_craft_reference_bytes
        isolated_validator_context_bytes = sum(
            int(item["body_bytes"]) + _metadata_bytes([item])
            for item in slots
            if item.get("context_scope") == "isolated_validator_contract"
        )
        total_context_bytes = base_bytes + candidate_metadata_bytes + provider_body_bytes + selected_metadata_bytes

    suggestions = [item for item in dict.fromkeys(suggestions) if item not in loaded_body_ids and item != "dircreative"]
    status = (
        "waiting_for_gate"
        if gate is not None
        else "blocked"
        if validation_required_missing
        or staged_pass_blocked
        or asset_foundation_gate_blocked
        or ledger_candidate_blocked
        or (intent.get("real_side_effect") and adapter is None)
        else "needs_followup"
        if staged_pass_needs_followup
        or (scenario.get("requires_complete_gaps_before_downstream") is True and missing_gaps)
        else "ready"
    )
    media_controls: list[str] = []
    if media == "still":
        media_controls = ["no_timeline", "no_camera_travel", "no_editing", "no_sound"]
    applied_handoff_contract = (
        handoff_contract
        if handoff_contract is not None
        and owner_id == handoff_contract.get("target_owner")
        else None
    )
    priority_method_provider = (
        "mr-li-seedance-25"
        if seedance25_target
        and any(item.get("skill_id") == "mr-li-seedance-25" for item in slots)
        else None
    )
    if priority_method_provider and scenario_id == "script_to_seedance":
        reason_codes.append("seedance25_method_precedes_compile")
    elif priority_method_provider and intent.get("emotion_priority") is True:
        reason_codes.append("seedance25_method_precedes_emotion_compile")
    return {
        "status": status,
        "scenario_id": scenario_id,
        "active_asset_pass_id": active_asset_pass_id,
        "next_asset_pass_id": next_asset_pass_id,
        "staged_pass_count": staged_pass_count,
        "asset_pass_status": asset_pass_status if staged_pass_count else None,
        "asset_foundation_gate_status": asset_foundation_gate_status,
        "handoff_contract_id": (
            applied_handoff_contract.get("contract_id") if applied_handoff_contract else None
        ),
        "handoff_contract": applied_handoff_contract,
        "priority_method_provider": priority_method_provider,
        "mode": mode,
        "route_id": route_id,
        "media": media,
        "candidate_count": len(candidate_pool),
        "covered_gaps": covered_gaps,
        "missing_gaps": missing_gaps,
        "fallback_used": owner_id == "dircreative" and "dircreative" not in owner_candidates,
        "craft_owner": slots[0],
        "collaborators": [item for item in slots if item["role"] == "collaborator"],
        "validator": next((item for item in slots if item["role"] == "validator"), None),
        "execution_adapter": adapter,
        "explicit_overlays": [item for item in slots if item["role"] == "explicit_overlay"],
        "loaded_body_ids": loaded_body_ids,
        "loaded_body_count": len(loaded_body_ids),
        "body_read_requests": [
            {
                "skill_id": item["skill_id"],
                "body_sha256": item["body_sha256"],
                "body_bytes": item["body_bytes"],
                "context_scope": item.get("context_scope", "main_skill_stack"),
                "host_action": (
                    "primary_host_diagnose_only_no_rewrite_hash_verify_before_card"
                    if item.get("application_contract", {}).get("authority")
                    == "diagnostic_only"
                    else "primary_host_independent_full_read_hash_verify_and_apply_before_card"
                ),
                **(
                    {"application_contract": item["application_contract"]}
                    if isinstance(item.get("application_contract"), dict)
                    else {}
                ),
            }
            for item in [
                *slots,
                *(
                    [adapter]
                    if adapter is not None
                    and adapter.get("skill_id") not in {slot["skill_id"] for slot in slots}
                    else []
                ),
            ]
            if item.get("body_sha256")
        ],
        "reference_read_requests": reference_read_requests,
        "handoff_read_requests": handoff_read_requests,
        "host_adoption_status": "unverified" if loaded_body_ids else "not_required",
        "host_card_contract": {
            "selector_may_claim_used": False,
            "independent_full_body_read_required": True,
            "body_hash_verification_required": True,
            "receipt_hash_echo_sufficient": False,
        },
        "slots": slots,
        "suggested_skill_ids": suggestions,
        "final_artifact_owner": final_owner,
        "final_state_owner": final_owner,
        "gate": gate,
        "execution_performed": False,
        "generated": False,
        "artifact_before_skill_card": True,
        "skill_card": [],
        "media_controls": media_controls,
        "reason_codes": reason_codes,
        "context": {
            "base_bytes": base_bytes,
            "candidate_metadata_bytes": candidate_metadata_bytes,
            "selected_metadata_bytes": selected_metadata_bytes,
            "provider_body_bytes": provider_body_bytes,
            "execution_adapter_context_bytes": execution_adapter_context_bytes,
            "execution_adapter_context_budget_bytes": int(
                mode_contract.get("execution_adapter_context_bytes_max", 0)
            ),
            "isolated_craft_context_bytes": isolated_craft_context_bytes,
            "isolated_craft_reference_bytes": isolated_craft_reference_bytes,
            "isolated_craft_reference_count": len(reference_read_requests),
            "isolated_craft_context_budget_bytes": int(
                mode_contract.get("isolated_craft_context_bytes_max", 0)
            ),
            "isolated_validator_context_bytes": isolated_validator_context_bytes,
            "isolated_validator_context_budget_bytes": int(
                mode_contract.get("isolated_validator_context_bytes_max", 0)
            ),
            "isolated_handoff_context_bytes": isolated_handoff_context_bytes,
            "isolated_handoff_reference_count": len(handoff_read_requests),
            "isolated_handoff_context_budget_bytes": int(
                mode_contract.get("isolated_handoff_context_bytes_max", 0)
            ),
            "aggregate_accounted_bytes": (
                total_context_bytes
                + isolated_craft_context_bytes
                + isolated_validator_context_bytes
                + isolated_handoff_context_bytes
                + execution_adapter_context_bytes
            ),
            "total_bytes": total_context_bytes,
            "budget_bytes": budget,
            "total_files": base_files + len(
                [
                    item
                    for item in slots
                    if item["status"] in {"materialized", "eligible_after_gate"}
                    and item.get("context_scope") not in ISOLATED_CONTEXT_SCOPES
                ]
            ),
            "budget_files": file_budget,
            "task_reference_source": (
                "internal_reference"
                if owner_id == "dircreative"
                else "isolated_external_provider_body"
                if owner_slot.get("context_scope") == "isolated_craft_contract"
                else "external_provider_body"
            ),
        },
    }


STATIC_FORBIDDEN_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:s|sec|secs|second|seconds)\b|"
    r"[一二两三四五六七八九十\d]+(?:\.\d+)?\s*(?:秒|分钟)(?:后|内)?|"
    r"(?:片刻|顷刻|随后|之后|然后|接着|继而)(?:之后|以后|之内)?|"
    r"\b(?:camera|lens)\s+(?:moves?|travels?|orbits?|pushes?|pulls?|pans?|tilts?|dives?|tracks?)\b|"
    r"(?:镜头|摄影机|摄像机|相机).{0,20}(?:推进|拉远|环绕|移动|摇|移|俯冲|跟拍|升降|旋转|推拉|运动|滑行|跟随|追随|扫过|掠过|俯仰)|"
    r"运镜|剪辑|转场|音效|环境声|声音|声响|爆破声|响起|对白|旁白|配乐|"
    r"\b(?:cut|cuts|editing|transition|sound|music|voiceover)\b)",
    re.IGNORECASE,
)
UNEXECUTED_CLAIM_RE = re.compile(
    r"(?:已(?:经)?(?:生成|渲染|导出|写入|上传|发布|外发)|"
    r"(?:生成|渲染|导出|写入|上传|发布|外发)(?:已)?完成|"
    r"(?:成片|文件|结果).{0,12}(?:保存|写入|导出)(?:为|至|到)?|"
    r"(?:成片|输出|文件|结果|视频).{0,18}(?:现?已?就绪|完成|保存|下载|链接)|"
    r"(?:现?已?就绪|完成|保存|下载|链接).{0,18}(?:成片|输出|文件|结果|视频|[\w.-]+\.(?:mp4|mov|webm|png|jpe?g))|"
    r"(?:generated|rendered|exported|written|uploaded|published|sent)\s+(?:to|at)|"
    r"(?:/tmp/|/var/tmp/|[A-Za-z]:\\))",
    re.IGNORECASE,
)


def render_artifact_then_card(
    artifact: str,
    receipt: dict[str, Any],
) -> str:
    artifact = artifact.strip()
    if not artifact:
        raise SkillStackError("artifact must be non-empty")
    if receipt.get("media") == "still" and STATIC_FORBIDDEN_RE.search(artifact):
        raise SkillStackError("still artifact contains temporal, camera, edit, or sound instructions")
    if receipt.get("execution_performed") is not True and UNEXECUTED_CLAIM_RE.search(artifact):
        raise SkillStackError("artifact claims an execution that the selector did not perform")
    # Materialization proves bytes were read by this selector, not that the
    # primary host applied the Skill. Never accept a caller-echoed receipt hash
    # as adoption. The host may append its own card only after an independent
    # full-body read, hash verification, and actual use on the artifact.
    if receipt.get("body_read_requests"):
        selected = [
            item.get("skill_id")
            for item in receipt.get("body_read_requests", [])
            if item.get("skill_id")
        ]
        if receipt.get("mode") == "fast":
            card = "本次 Skill 配置：已选 " + "、".join(f"`${item}`" for item in selected)
            card += "；采用状态 `HOST_ADOPTION=UNVERIFIED`。"
        else:
            card = "本次 Skill 配置\n- 已选：" + "、".join(f"`${item}`" for item in selected)
            card += " — `HOST_ADOPTION=UNVERIFIED`"
        return artifact + "\n\n" + card
    card = "\n".join(
        _render_skill_card(
            str(receipt.get("mode")),
            [dict(item) for item in receipt.get("slots", [])],
            list(receipt.get("suggested_skill_ids", [])),
        )
    )
    return artifact + ("\n\n" + card if card else "")


def _write_mock_skill(root: Path, skill_id: str, body_pad: int = 0) -> None:
    skill_dir = root / skill_id.replace(":", "__")
    skill_dir.mkdir(parents=True)
    nested_metadata = (
        '\nmetadata:\n  version: "1.5.0"\n  display-version-name: "Seedance 2.5 method"'
        if skill_id == "mr-li-seedance-25"
        else ""
    )
    body = (
        f"---\nname: {skill_id}\ndescription: Deterministic test provider.{nested_metadata}\n---\n\n# Test\n"
    ) + ("x" * body_pad)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    agents = skill_dir / "agents"
    agents.mkdir()
    (agents / "openai.yaml").write_text(
        f"interface:\n  display_name: {skill_id}\n  short_description: test provider\n",
        encoding="utf-8",
    )
    if skill_id == "jingzao-image-forge":
        for relative, realistic_bytes in JINGZAO_REFERENCE_PAD.items():
            reference = skill_dir / relative
            reference.parent.mkdir(parents=True, exist_ok=True)
            target_bytes = realistic_bytes if body_pad else 64
            prefix = "# Deterministic reference fixture\n"
            padding = max(0, target_bytes - len(prefix.encode("utf-8")))
            reference.write_text(prefix + ("x" * padding), encoding="utf-8")
    if skill_id == "mr-li-seedance-25":
        for relative, realistic_bytes in MR_LI_REFERENCE_PAD.items():
            reference = skill_dir / relative
            reference.parent.mkdir(parents=True, exist_ok=True)
            target_bytes = realistic_bytes if body_pad else 64
            prefix = "# Deterministic reference fixture\n"
            padding = max(0, target_bytes - len(prefix.encode("utf-8")))
            reference.write_text(prefix + ("x" * padding), encoding="utf-8")
    if skill_id == "shuorenhua":
        for relative, realistic_bytes in SHUORENHUA_REFERENCE_PAD.items():
            reference = skill_dir / relative
            reference.parent.mkdir(parents=True, exist_ok=True)
            target_bytes = realistic_bytes if body_pad else 64
            prefix = "# Deterministic human-language reference fixture\n"
            padding = max(0, target_bytes - len(prefix.encode("utf-8")))
            reference.write_text(prefix + ("x" * padding), encoding="utf-8")


def _case_assertions(case: dict[str, Any], receipt: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    expected = case.get("expected", {})
    case_id = case.get("id", "unknown")
    for key, value in expected.items():
        if key == "craft_owner":
            actual = receipt.get("craft_owner", {}).get("skill_id")
        elif key == "validator":
            actual = (receipt.get("validator") or {}).get("skill_id") or None
        elif key == "collaborators":
            actual = [item["skill_id"] for item in receipt.get("collaborators", [])]
        elif key == "explicit_overlays":
            actual = [item["skill_id"] for item in receipt.get("explicit_overlays", [])]
        elif key == "execution_adapter":
            actual = (receipt.get("execution_adapter") or {}).get("skill_id") or None
        elif key == "reason_code":
            actual = value if value in receipt.get("reason_codes", []) else None
        else:
            actual = receipt.get(key)
        if actual != value:
            failures.append(f"{case_id}: expected {key}={value!r}, got {actual!r}")
    if receipt.get("candidate_count", 0) > 12:
        failures.append(f"{case_id}: candidate limit exceeded")
    if receipt.get("artifact_before_skill_card") is not True:
        failures.append(f"{case_id}: artifact-before-card contract lost")
    if receipt.get("execution_performed") is not False:
        failures.append(f"{case_id}: selector executed a side effect")
    if receipt.get("generated") is not False:
        failures.append(f"{case_id}: prompt-only selector claimed generation")
    if receipt.get("final_artifact_owner") != receipt.get("final_state_owner"):
        failures.append(f"{case_id}: artifact/state owner split")
    return failures


def self_test() -> tuple[list[str], dict[str, Any]]:
    failures = validate_registry(load_registry())
    registry = load_registry()
    misrouted_registry = json.loads(json.dumps(registry))
    for scenario in misrouted_registry.get("scenarios", []):
        if scenario.get("scenario_id") == "script_to_seedance":
            scenario["owner_candidates"] = ["mr-li-seedance-25", "convert-script-to-seedance"]
            break
    if not any(
        "handoff target is not the first owner candidate" in failure
        for failure in validate_registry(misrouted_registry)
    ):
        failures.append("handoff contract target did not remain the first owner candidate")
    routing = load_routing()
    cases_payload = load_json(CASES_PATH)
    cases = cases_payload.get("cases", []) if isinstance(cases_payload, dict) else []
    expected_defaults = cases_payload.get("expected_defaults", {}) if isinstance(cases_payload, dict) else {}
    positives = [case for case in cases if case.get("kind") == "positive"]
    negatives = [case for case in cases if case.get("kind") == "negative"]
    if len(positives) < 24:
        failures.append("Skill Stack fixtures need at least 24 positive cases")
    if len(negatives) < 12:
        failures.append("Skill Stack fixtures need at least 12 negative cases")
    host_catalog, host_rejected = load_host_catalog(HOST_CATALOG_PATH, registry)
    if set(host_catalog) != {"creative-anchor-director", "mechanical-transformation-design", "imagegen"}:
        failures.append("host catalog normalization did not preserve the verified policy candidates")
    if not host_rejected or host_rejected[0].get("reason") != "catalog_entry_invalid_or_unavailable":
        failures.append("host catalog did not reject an unavailable entry")
    if any(entry.body_loaded for entry in host_catalog.values()):
        failures.append("frontmatter-only host catalog falsely claimed provider bodies were loaded")
    with tempfile.TemporaryDirectory(prefix="dircreative-skill-stack-") as temp:
        temp_root = Path(temp)
        nested_frontmatter_skill = temp_root / "nested-frontmatter-skill.md"
        nested_frontmatter_skill.write_text(
            "---\n"
            "name: nested-frontmatter-skill\n"
            "description: |\n"
            "  合法中文多行说明，用于验证 UTF-8 边界。\n"
            "allowed-tools:\n"
            "  - Read\n"
            "  - Edit\n"
            "metadata:\n"
            "  trigger: 自然语言审阅\n"
            "---\n\n"
            + ("中文正文" * 2000),
            encoding="utf-8",
        )
        try:
            nested_frontmatter, _front_bytes, _body_bytes = _frontmatter_probe(
                nested_frontmatter_skill,
                frontmatter_limit=int(
                    registry["discovery_contract"]["frontmatter_bytes_max"]
                ),
                body_limit=int(registry["discovery_contract"]["skill_body_bytes_max"]),
            )
        except SkillStackError as exc:
            failures.append(f"nested UTF-8 frontmatter rejected: {exc}")
        else:
            if nested_frontmatter.get("name") != "nested-frontmatter-skill":
                failures.append("nested UTF-8 frontmatter changed Skill identity")
            if "UTF-8" not in nested_frontmatter.get("description", ""):
                failures.append("nested UTF-8 frontmatter lost multiline description")
        installed_layout = temp_root / "installed-layout"
        installed_route = installed_layout / "routes/fast-task.md"
        installed_route.parent.mkdir(parents=True)
        (installed_layout / "SKILL.md").write_text("# installed fixture\n", encoding="utf-8")
        installed_route.write_text("# route\n", encoding="utf-8")
        if resolve_runtime_path(
            "skills/dircreative/routes/fast-task.md",
            root=installed_layout,
            skill_root=installed_layout,
        ) != installed_route.resolve(strict=True):
            failures.append("installed layout did not resolve a source-relative runtime path")
        outside_runtime = temp_root / "outside-runtime.md"
        outside_runtime.write_text("outside\n", encoding="utf-8")
        escape_link = installed_layout / "routes/escape.md"
        os.symlink(outside_runtime, escape_link)
        for invalid_runtime_path in (
            "../outside-runtime.md",
            str(outside_runtime),
            "skills/dircreative/../outside-runtime.md",
            "skills/dircreative/routes/escape.md",
            "skills/dircreative/routes/missing.md",
        ):
            try:
                resolve_runtime_path(
                    invalid_runtime_path,
                    root=installed_layout,
                    skill_root=installed_layout,
                )
            except SkillStackError:
                pass
            else:
                failures.append(f"runtime path containment accepted: {invalid_runtime_path}")
        skills_root = temp_root / "skills"
        skills_root.mkdir()
        providers = normalize_providers(registry)
        for skill_id in providers:
            if skill_id != "dircreative":
                _write_mock_skill(skills_root, skill_id)
        catalog, rejected = discover_roots([("fixture", skills_root)], registry)
        if rejected:
            failures.append(f"valid discovery rejected fixtures: {rejected[:2]}")
        fixture_loader = body_loader_for_roots([("fixture", skills_root)], registry)
        for case in cases:
            effective_case = dict(case)
            if case.get("kind") == "positive":
                effective_case["expected"] = {**expected_defaults, **case.get("expected", {})}
            case_catalog = dict(catalog)
            for missing in case.get("remove_skills", []):
                case_catalog.pop(missing, None)
            try:
                receipt = select_stack(
                    case["intent"],
                    registry,
                    routing,
                    case_catalog,
                    route_context=_fixture_route_context(case),
                    body_loader=fixture_loader,
                )
            except SkillStackError as exc:
                receipt = {
                    "status": "blocked",
                    "reason_codes": [str(exc)],
                    "candidate_count": 0,
                    "artifact_before_skill_card": True,
                    "final_artifact_owner": "dircreative",
                    "final_state_owner": "dircreative",
                    "execution_performed": False,
                    "generated": False,
                }
            failures.extend(_case_assertions(effective_case, receipt))
            if receipt.get("status") != "blocked":
                rendered = render_artifact_then_card("可用成品", receipt)
                if not rendered.startswith("可用成品") or rendered.find("可用成品") > rendered.find("本次 Skill") >= 0:
                    failures.append(f"{case['id']}: skill card appeared before artifact")
                if receipt.get("body_read_requests") and "已用" in rendered:
                    failures.append(f"{case['id']}: selector receipt self-certified host adoption")
                used_ids = set(receipt.get("loaded_body_ids", []))
                for suggested in receipt.get("suggested_skill_ids", []):
                    if suggested not in used_ids and f"已用 `${suggested}`" in rendered:
                        failures.append(f"{case['id']}: suggested provider mislabeled as used")

        overlay_case = next(item for item in cases if item["id"] == "p40_explicit_overlays")
        reverse_overlay_intent = dict(
            overlay_case["intent"],
            explicit_overlays=["sophia-research-mode", "liu-creative-workflow"],
        )
        reverse_overlay_receipt = select_stack(
            reverse_overlay_intent,
            registry,
            routing,
            dict(catalog),
            route_context=_fixture_route_context(overlay_case),
            body_loader=fixture_loader,
        )
        if [
            item["skill_id"] for item in reverse_overlay_receipt.get("explicit_overlays", [])
        ] != ["sophia-research-mode", "liu-creative-workflow"]:
            failures.append("explicit overlay order did not preserve the user input")

        host_bound_catalog = dict(host_catalog)
        host_case = next(item for item in cases if item["id"] == "p01_fast_single_concept")
        host_receipt = select_stack(
            host_case["intent"],
            registry,
            routing,
            host_bound_catalog,
            route_context=_fixture_route_context(host_case),
            body_loader=fixture_loader,
        )
        if host_receipt.get("craft_owner", {}).get("skill_id") != "creative-anchor-director":
            failures.append("host catalog did not bind only the selected provider body")
        _write_mock_skill(skills_root, "next-concept-provider")
        dynamic_catalog_path = temp_root / "dynamic-catalog.json"
        dynamic_catalog_path.write_text(
            json.dumps(
                {
                    "skills": [
                        {
                            "skill_id": "next-concept-provider",
                            "description": "Host-validated future concept provider.",
                            "capability_policy": {
                                "capabilities": ["concept_direction"],
                                "media_gate": ["any"],
                                "deliverable_layers": ["any"],
                                "provider_roles": ["craft_owner"],
                                "trigger_stages": ["concept"],
                                "mode_allowlist": ["fast", "studio"],
                                "priority": 70,
                                "perspective": "narrative_strategy",
                            },
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        dynamic_catalog, dynamic_rejected = load_host_catalog(dynamic_catalog_path, registry)
        dynamic_receipt = select_stack(
            host_case["intent"],
            registry,
            routing,
            dynamic_catalog,
            route_context=_fixture_route_context(host_case),
            body_loader=fixture_loader,
        )
        if dynamic_rejected or dynamic_receipt.get("craft_owner", {}).get("skill_id") != "next-concept-provider":
            failures.append("validated future provider did not become a bounded capability candidate")
        realistic_root = temp_root / "realistic-root"
        realistic_root.mkdir()
        for skill_id, body_pad in REALISTIC_BODY_PAD.items():
            _write_mock_skill(realistic_root, skill_id, body_pad=body_pad)
            skill_path = realistic_root / skill_id / "SKILL.md"
            skill_path.write_bytes(skill_path.read_bytes().replace(b"\n", b"\r\n"))
        realistic_catalog, realistic_rejected = discover_roots(
            [("realistic_fixture", realistic_root)],
            registry,
        )
        if realistic_rejected:
            failures.append(f"realistic CRLF discovery rejected providers: {realistic_rejected[:2]}")
        realistic_loader = body_loader_for_roots(
            [("realistic_fixture", realistic_root)],
            registry,
        )
        case_map = {item["id"]: item for item in cases}
        for case_id, expected in REALISTIC_SMOKE_EXPECTED.items():
            case = case_map[case_id]
            try:
                receipt = select_stack(
                    case["intent"],
                    registry,
                    routing,
                    dict(realistic_catalog),
                    route_context=_fixture_route_context(case),
                    body_loader=realistic_loader,
                )
            except SkillStackError as exc:
                failures.append(f"{case_id}: realistic selection failed: {exc}")
                continue
            actual = (
                receipt["craft_owner"]["skill_id"],
                receipt["loaded_body_count"],
                receipt["status"],
                receipt["gate"],
            )
            if actual != expected:
                failures.append(f"{case_id}: realistic expected {expected!r}, got {actual!r}")
            if case_id == "p56_contextual_human_language":
                owner = receipt.get("craft_owner") or {}
                validator = receipt.get("validator") or {}
                context = receipt.get("context") or {}
                reference_requests = receipt.get("reference_read_requests") or []
                validator_request = next(
                    (
                        item
                        for item in receipt.get("body_read_requests", [])
                        if item.get("skill_id") == "humanizer-zh"
                    ),
                    {},
                )
                if (
                    owner.get("context_scope") != "isolated_craft_contract"
                    or validator.get("context_scope")
                    != "isolated_validator_contract"
                    or validator.get("application_contract")
                    != {
                        "authority": "diagnostic_only",
                        "output_mode": "findings_only",
                        "may_rewrite": False,
                    }
                    or int(context.get("isolated_craft_context_bytes", 0)) < 54000
                    or int(context.get("isolated_validator_context_bytes", 0)) < 18000
                    or int(context.get("isolated_craft_reference_count", 0)) != 4
                    or int(context.get("isolated_craft_reference_bytes", 0)) < 34000
                    or len(reference_requests) != 4
                    or validator_request.get("application_contract")
                    != validator.get("application_contract")
                    or "diagnose_only_no_rewrite"
                    not in str(validator_request.get("host_action", ""))
                    or int(context.get("total_bytes", 0)) > 20000
                ):
                    failures.append(
                        "realistic human-language owner/diagnostic contexts were not isolated"
                    )
            if case_id == "p42_authorized_generation_adapter":
                adapter = receipt.get("execution_adapter") or {}
                context = receipt.get("context") or {}
                if (
                    adapter.get("context_scope") != "isolated_host_tool_contract"
                    or int(context.get("execution_adapter_context_bytes", 0)) < 19000
                    or int(context.get("execution_adapter_context_bytes", 0)) > 24576
                    or int(context.get("total_bytes", 0)) > 30000
                    or int(context.get("aggregate_accounted_bytes", 0))
                    != int(context.get("total_bytes", 0))
                    + int(context.get("execution_adapter_context_bytes", 0))
                ):
                    failures.append("realistic imagegen adapter was not fully and separately budgeted")
            if case_id == "p47_cinematic_storyboard_frames":
                owner = receipt.get("craft_owner") or {}
                context = receipt.get("context") or {}
                requests = receipt.get("body_read_requests") or []
                reference_requests = receipt.get("reference_read_requests") or []
                handoff_requests = receipt.get("handoff_read_requests") or []
                output_binding = (receipt.get("handoff_contract") or {}).get("output_binding") or {}
                if (
                    owner.get("context_scope") != "isolated_craft_contract"
                    or int(context.get("isolated_craft_context_bytes", 0)) < 99000
                    or int(context.get("isolated_craft_context_bytes", 0)) > 131072
                    or int(context.get("isolated_craft_reference_count", 0)) != 6
                    or int(context.get("isolated_craft_reference_bytes", 0)) < 71000
                    or int(context.get("total_bytes", 0)) > 20000
                    or int(context.get("isolated_handoff_context_bytes", 0)) < 30000
                    or int(context.get("isolated_handoff_context_bytes", 0)) > 86016
                    or int(context.get("aggregate_accounted_bytes", 0))
                    != int(context.get("total_bytes", 0))
                    + int(context.get("isolated_craft_context_bytes", 0))
                    + int(context.get("isolated_handoff_context_bytes", 0))
                    or not requests
                    or requests[0].get("context_scope") != "isolated_craft_contract"
                    or len(reference_requests) != 6
                    or len(handoff_requests) != 3
                    or {item.get("role") for item in handoff_requests}
                    != {"contract_reference", "output_schema", "output_validator"}
                    or output_binding.get("validator")
                    != "scripts/dircreative_storyboard_frame_handoff.py"
                    or any(
                        item.get("context_scope") != "isolated_craft_contract"
                        or not item.get("sha256")
                        or not item.get("relative_path", "").startswith("references/")
                        for item in reference_requests
                    )
                ):
                    failures.append("realistic Jingzao owner was not fully isolated and budgeted")
            if case_id == "p46_script_to_seedance":
                owner = receipt.get("craft_owner") or {}
                validator = receipt.get("validator") or {}
                context = receipt.get("context") or {}
                handoff_requests = receipt.get("handoff_read_requests") or []
                output_binding = (receipt.get("handoff_contract") or {}).get("output_binding") or {}
                if (
                    owner.get("context_scope") != "isolated_craft_contract"
                    or validator.get("context_scope") != "isolated_validator_contract"
                    or int(context.get("isolated_validator_context_bytes", 0)) < 23000
                    or int(context.get("isolated_validator_context_bytes", 0)) > 65536
                    or int(context.get("total_bytes", 0)) > 20000
                    or int(context.get("isolated_handoff_context_bytes", 0)) < 40000
                    or int(context.get("isolated_handoff_context_bytes", 0)) > 86016
                    or int(context.get("aggregate_accounted_bytes", 0))
                    != int(context.get("total_bytes", 0))
                    + int(context.get("isolated_craft_context_bytes", 0))
                    + int(context.get("isolated_validator_context_bytes", 0))
                    + int(context.get("isolated_handoff_context_bytes", 0))
                    or len(handoff_requests) != 3
                    or {item.get("role") for item in handoff_requests}
                    != {"contract_reference", "output_schema", "output_validator"}
                    or output_binding.get("validator")
                    != "scripts/dircreative_script_to_seedance_handoff.py"
                ):
                    failures.append("realistic Seedance validator was not isolated and budgeted")
            if case_id == "p54_seedance25_fast_priority":
                context = receipt.get("context") or {}
                reference_requests = receipt.get("reference_read_requests") or []
                if (
                    int(context.get("isolated_craft_context_bytes", 0)) < 10000
                    or int(context.get("isolated_craft_context_bytes", 0)) > 16384
                    or int(context.get("isolated_craft_reference_count", 0)) != 2
                    or int(context.get("isolated_craft_reference_bytes", 0)) < 5000
                    or int(context.get("aggregate_accounted_bytes", 0))
                    != int(context.get("total_bytes", 0))
                    + int(context.get("isolated_craft_context_bytes", 0))
                    or {item.get("relative_path") for item in reference_requests}
                    != set(MR_LI_REFERENCE_PAD)
                    or any(not item.get("sha256") for item in reference_requests)
                ):
                    failures.append("realistic Fast Seedance method references were not isolated and budgeted")
        still_case = next(item for item in cases if item["id"] == "p06_key_visual")
        still_receipt = select_stack(
            still_case["intent"],
            registry,
            routing,
            dict(catalog),
            route_context=_fixture_route_context(still_case),
            body_loader=fixture_loader,
        )
        try:
            render_artifact_then_card(
                "静帧成品：镜头在5秒内环绕并剪切，响起爆炸声",
                still_receipt,
            )
        except SkillStackError:
            pass
        else:
            failures.append("still artifact accepted temporal/edit/sound instructions")
        try:
            render_artifact_then_card(
                "静帧成品：三秒后，摄像机俯冲跟拍，加入环境声。",
                still_receipt,
            )
        except SkillStackError:
            pass
        else:
            failures.append("still artifact accepted Chinese temporal/camera/sound synonyms")
        try:
            render_artifact_then_card(
                "静帧成品：片刻之后，摄像机向前滑行，响起爆破声。",
                still_receipt,
            )
        except SkillStackError:
            pass
        else:
            failures.append("still artifact accepted alternate temporal/camera/sound synonyms")
        prompt_case = next(item for item in cases if item["id"] == "p17_seedance_direct")
        prompt_receipt = select_stack(
            prompt_case["intent"],
            registry,
            routing,
            dict(catalog),
            route_context=_fixture_route_context(prompt_case),
            body_loader=fixture_loader,
        )
        prompt_hashes = [item["body_sha256"] for item in prompt_receipt["body_read_requests"]]
        try:
            render_artifact_then_card(
                "已生成真实视频 /tmp/final.mp4",
                prompt_receipt,
            )
        except SkillStackError:
            pass
        else:
            failures.append("prompt-only artifact claimed generation")
        try:
            render_artifact_then_card(
                "视频生成完成，成片保存为 final.mp4",
                prompt_receipt,
            )
        except SkillStackError:
            pass
        else:
            failures.append("prompt-only artifact accepted a completed-output synonym")
        try:
            render_artifact_then_card(
                "成片现已就绪，下载链接见 final.mp4",
                prompt_receipt,
            )
        except SkillStackError:
            pass
        else:
            failures.append("prompt-only artifact accepted a ready/download synonym")
        if prompt_hashes:
            rendered = render_artifact_then_card("可用成品", prompt_receipt)
            if "已用" in rendered:
                failures.append("Skill card accepted materialized body without host adoption")
            if "HOST_ADOPTION=UNVERIFIED" not in rendered:
                failures.append("unverified host adoption was not exposed after the artifact")
            try:
                render_artifact_then_card(
                    "可用成品",
                    prompt_receipt,
                    adopted_body_sha256s=prompt_hashes,  # type: ignore[call-arg]
                )
            except TypeError:
                pass
            else:
                failures.append("renderer accepted caller-supplied adoption hashes")
        authorized_case = next(item for item in cases if item["id"] == "p42_authorized_generation_adapter")
        authorized_context = validate_primary_route_context(
            authorized_case["intent"],
            request_text="$dircreative 现在立即生成这个画面，我确认生成",
        )
        authorized_receipt = select_stack(
            authorized_case["intent"],
            registry,
            routing,
            dict(catalog),
            route_context=authorized_context,
            body_loader=fixture_loader,
        )
        if authorized_receipt.get("execution_adapter", {}).get("skill_id") != "imagegen":
            failures.append("validated generation route did not grant the selected adapter")
        fal_intent = dict(authorized_case["intent"], available_tools=["fal_media"])
        fal_catalog = dict(catalog)
        fal_catalog.pop("imagegen", None)
        fal_receipt = select_stack(
            fal_intent,
            registry,
            routing,
            fal_catalog,
            route_context=authorized_context,
            body_loader=fixture_loader,
        )
        if fal_receipt.get("status") != "blocked" or fal_receipt.get("execution_adapter") is not None:
            failures.append("possible-cost external adapter bypassed its unverified cost boundary")
        key_visual_intent = {
            "scenario_id": "key_visual",
            "mode": "delivery",
            "route_id": "generation_authorization",
            "media": "still",
            "gaps": [],
            "needs_validation": False,
            "real_side_effect": True,
            "side_effect_kind": "generation",
            "available_tools": ["image_gen.imagegen"],
        }
        key_visual_context = validate_primary_route_context(
            key_visual_intent,
            request_text="$dircreative 现在立即生成这个画面，我确认生成",
        )
        key_visual_receipt = select_stack(
            key_visual_intent,
            registry,
            routing,
            dict(catalog),
            route_context=key_visual_context,
            body_loader=fixture_loader,
        )
        if (
            key_visual_receipt.get("status") != "ready"
            or key_visual_receipt.get("craft_owner", {}).get("skill_id") != "dircreative"
            or key_visual_receipt.get("execution_adapter", {}).get("skill_id") != "imagegen"
            or key_visual_receipt.get("loaded_body_count") != 1
        ):
            failures.append("Delivery did not reserve its single provider body for the execution adapter")
        unconfirmed_context = validate_primary_route_context(
            authorized_case["intent"],
            request_text="$dircreative 申请真实生成",
        )
        forged_intent = dict(
            authorized_case["intent"],
            authorizations={"generation_authorization": "caller-forged"},
        )
        forged_receipt = select_stack(
            forged_intent,
            registry,
            routing,
            dict(catalog),
            route_context=unconfirmed_context,
            body_loader=fixture_loader,
        )
        if forged_receipt.get("status") != "waiting_for_gate" or forged_receipt.get("execution_adapter") is not None:
            failures.append("caller-controlled authorization bypassed the validated primary route")
        adco_case = next(item for item in cases if item["id"] == "p43_adco_unique_owner")
        try:
            validate_primary_route_context(adco_case["intent"], request_text="")
        except SkillStackError:
            pass
        else:
            failures.append("ADCO owner was accepted without native handoff evidence")

        bad_root = temp_root / "bad"
        bad_root.mkdir()
        _write_mock_skill(bad_root, "valid-test-skill")
        binary_dir = bad_root / "binary-skill"
        binary_dir.mkdir()
        (binary_dir / "SKILL.md").write_bytes(b"---\nname: binary-skill\ndescription: x\n---\n\x00")
        huge_dir = bad_root / "huge-skill"
        huge_dir.mkdir()
        (huge_dir / "SKILL.md").write_text(
            "---\nname: huge-skill\ndescription: " + ("x" * 17000) + "\n---\n",
            encoding="utf-8",
        )
        link_dir = bad_root / "link-skill"
        os.symlink(bad_root / "valid-test-skill", link_dir)
        for directory_name in ("duplicate-a", "duplicate-b", "duplicate-c"):
            duplicate_dir = bad_root / directory_name
            duplicate_dir.mkdir()
            (duplicate_dir / "SKILL.md").write_text(
                "---\nname: creative-anchor-director\ndescription: duplicate\n---\n",
                encoding="utf-8",
            )
        bad_catalog, bad_rejected = discover_roots([("fixture", bad_root)], registry)
        rejected_reasons = {item["reason"] for item in bad_rejected}
        for expected_reason in {
            "skill_body_binary",
            "frontmatter_unbounded_or_too_large",
            "skill_directory_not_regular",
        }:
            if expected_reason not in rejected_reasons:
                failures.append(f"discovery did not reject {expected_reason}")
        if "creative-anchor-director" in bad_catalog:
            failures.append("three-way duplicate discovery restored a collided provider")
        public_dump = json.dumps(
            {
                "catalog": [entry.public() for entry in catalog.values()],
                "rejected": rejected,
            },
            ensure_ascii=False,
        )
        if str(temp_root) in public_dump:
            failures.append("discovery output leaked a private absolute path")
        private_catalog = temp_root / "private-catalog.json"
        private_catalog.write_text(
            json.dumps(
                {
                    "skills": [
                        {
                            "skill_id": "creative-anchor-director",
                            "description": "bad path",
                            "path": "/Users/example/private/SKILL.md",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        private_loaded, private_rejected = load_host_catalog(private_catalog, registry)
        if private_loaded or not private_rejected or private_rejected[0].get("reason") != "catalog_private_path_forbidden":
            failures.append("host catalog accepted or echoed a private absolute path")
        duplicate_catalog = temp_root / "duplicate-catalog.json"
        duplicate_catalog.write_text(
            json.dumps(
                {
                    "skills": [
                        {
                            "skill_id": "creative-anchor-director",
                            "description": f"duplicate {index}",
                        }
                        for index in range(3)
                    ]
                }
            ),
            encoding="utf-8",
        )
        duplicate_loaded, duplicate_rejected = load_host_catalog(duplicate_catalog, registry)
        if "creative-anchor-director" in duplicate_loaded or len(duplicate_rejected) != 2:
            failures.append("three-way host catalog duplicate restored a collided provider")
        malformed_intent = dict(cases[0]["intent"])
        malformed_intent["available_tools"] = {"image_gen.imagegen": True}
        try:
            select_stack(
                malformed_intent,
                registry,
                routing,
                catalog,
                route_context=_fixture_route_context(cases[0]),
                body_loader=fixture_loader,
            )
        except SkillStackError as exc:
            if str(exc) != "available_tools must be a string array":
                failures.append("malformed tool list failed with the wrong reason")
        else:
            failures.append("selector accepted a non-array available_tools value")

    summary = {
        "positive_cases": len(positives),
        "negative_cases": len(negatives),
        "scenario_count": len(registry.get("scenarios", [])),
        "provider_policy_count": len(registry.get("providers", [])),
        "realistic_smoke_cases": len(REALISTIC_SMOKE_EXPECTED),
        "two_phase_host_binding": True,
        "trusted_primary_route_controls": True,
        "artifact_output_guard_controls": True,
        "future_capability_provider_control": True,
        "deterministic_candidate_pool": True,
        "explicit_overlay_order_preserved": True,
        "installed_layout_resolution": True,
        "runtime_path_containment_controls": True,
        "unverified_cost_adapter_blocked": True,
        "delivery_single_body_reservation": True,
        "isolated_execution_adapter_budget_bytes": 24576,
        "isolated_craft_context_budget_bytes": 131072,
        "isolated_validator_context_budget_bytes": 65536,
        "host_managed_imagegen_path": True,
        "failures": failures,
    }
    return failures, summary


def _parse_roots(values: list[str]) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    for value in values:
        if "=" in value:
            source_type, raw_path = value.split("=", 1)
        else:
            source_type, raw_path = "user_skill", value
        if not ID_RE.fullmatch(source_type):
            raise SkillStackError("invalid source type")
        roots.append((source_type, Path(raw_path)))
    return roots


def _catalog_from_args(
    args: argparse.Namespace,
    registry: dict[str, Any],
) -> tuple[dict[str, CatalogEntry], list[dict[str, str]], BodyLoader | None]:
    catalog_path = getattr(args, "catalog", None)
    root_values = getattr(args, "root", None) or []
    roots = _parse_roots(root_values)
    if catalog_path:
        catalog, rejected = load_host_catalog(catalog_path, registry)
        return catalog, rejected, body_loader_for_roots(roots, registry) if roots else None
    if not root_values:
        raise SkillStackError("a host catalog or authorized Skill root is required")
    catalog, rejected = discover_roots(roots, registry)
    return catalog, rejected, body_loader_for_roots(roots, registry)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover and select a bounded DIRcreative visual Skill Stack.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("self-test")
    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("--root", action="append", help="[source_type=]/authorized/skill/root")
    discover_parser.add_argument("--catalog", type=Path, help="host-injected metadata catalog JSON")
    select_parser = subparsers.add_parser("select")
    select_parser.add_argument("--intent", type=Path, required=True)
    select_parser.add_argument("--root", action="append", help="[source_type=]/authorized/skill/root")
    select_parser.add_argument("--catalog", type=Path, help="host-injected metadata catalog JSON")
    select_parser.add_argument("--request", default="", help="original request for primary-route validation")
    select_parser.add_argument("--handoff", type=Path, help="real ADCO Specialist Exchange handoff")
    select_parser.add_argument("--project-root", type=Path, help="ADCO project root")
    select_parser.add_argument("--descriptor", type=Path, help="DIR specialist descriptor")
    case_parser = subparsers.add_parser("case")
    case_parser.add_argument("case_id")
    case_parser.add_argument("--root", action="append", help="[source_type=]/authorized/skill/root")
    case_parser.add_argument("--catalog", type=Path, help="host-injected metadata catalog JSON")
    smoke_parser = subparsers.add_parser("smoke")
    smoke_parser.add_argument("--root", action="append", help="[source_type=]/authorized/skill/root")
    smoke_parser.add_argument("--catalog", type=Path, help="host-injected metadata catalog JSON")
    smoke_parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args()
    command = args.command or "self-test"
    if command == "self-test":
        failures, summary = self_test()
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        print("DIRCREATIVE_SKILL_STACK_AUDIT:", "PASS" if not failures else "FAIL")
        return 0 if not failures else 1
    registry = load_registry()
    failures = validate_registry(registry)
    if failures:
        raise SkillStackError("; ".join(failures))
    catalog, rejected, body_loader = _catalog_from_args(args, registry)
    if command == "discover":
        print(
            json.dumps(
                {
                    "available": [catalog[key].public() for key in sorted(catalog)],
                    "rejected": rejected,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if command == "select":
        intent = load_json(args.intent)
        route_context = validate_primary_route_context(
            intent,
            request_text=args.request,
            handoff_path=args.handoff,
            project_root=args.project_root,
            descriptor_path=args.descriptor,
        )
        receipt = select_stack(
            intent,
            registry,
            load_routing(),
            catalog,
            route_context=route_context,
            body_loader=body_loader,
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if receipt["status"] != "blocked" else 1
    cases = load_json(CASES_PATH)["cases"]
    if command == "smoke":
        default_ids = [
            "p01_fast_single_concept",
            "p06_key_visual",
            "p17_seedance_direct",
            "p39_seedance_performance_handoff",
            "p23_mechanical_still",
            "p24_mechanical_temporal",
            "p38_full_project_stack",
            "p41_generation_gate",
            "p10_technical_storyboard",
            "p20_action_choreography",
            "p21_action_showcase",
            "p22_seedance_fight",
            "p26_sound_design",
            "p42_authorized_generation_adapter",
            "p44_score_mix_reuses_loaded_body",
            "p45_asset_foundation",
            "p46_script_to_seedance",
            "p47_cinematic_storyboard_frames",
            "n18_asset_foundation_does_not_generate",
            "n20_jingzao_craft_does_not_bypass_generation_gate",
            "n21_required_seedance_validator_missing",
            "n12_candidate_pool_capped",
        ]
        selected_ids = args.case_ids or default_ids
        case_map = {item["id"]: item for item in cases}
        unknown = sorted(set(selected_ids) - set(case_map))
        if unknown:
            raise SkillStackError(f"unknown smoke case ids: {unknown}")
        receipts = [
            select_stack(
                case_map[case_id]["intent"],
                registry,
                load_routing(),
                dict(catalog),
                route_context=_fixture_route_context(case_map[case_id]),
                body_loader=body_loader,
            )
            for case_id in selected_ids
        ]
        smoke_failures: list[str] = []
        for case_id, receipt in zip(selected_ids, receipts):
            expected = REALISTIC_SMOKE_EXPECTED.get(case_id)
            if expected is not None:
                actual = (
                    receipt["craft_owner"]["skill_id"],
                    receipt["loaded_body_count"],
                    receipt["status"],
                    receipt["gate"],
                )
                if actual != expected:
                    smoke_failures.append(f"{case_id}: expected {expected!r}, got {actual!r}")
            if receipt.get("artifact_before_skill_card") is not True:
                smoke_failures.append(f"{case_id}: artifact-first contract lost")
        print(
            json.dumps(
                {
                    "catalog_available": len(catalog),
                    "catalog_rejected": len(rejected),
                    "failures": smoke_failures,
                    "cases": [
                        {
                            "case_id": case_id,
                            "status": receipt["status"],
                            "craft_owner": receipt["craft_owner"]["skill_id"],
                            "loaded_body_count": receipt["loaded_body_count"],
                            "validator": (receipt["validator"] or {}).get("skill_id"),
                            "gate": receipt["gate"],
                            "fallback_used": receipt["fallback_used"],
                            "artifact_before_skill_card": receipt["artifact_before_skill_card"],
                            "media_controls": receipt["media_controls"],
                        }
                        for case_id, receipt in zip(selected_ids, receipts)
                    ],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if not smoke_failures else 1
    case = next((item for item in cases if item["id"] == args.case_id), None)
    if case is None:
        raise SkillStackError(f"unknown case id: {args.case_id}")
    receipt = select_stack(
        case["intent"],
        registry,
        load_routing(),
        catalog,
        route_context=_fixture_route_context(case),
        body_loader=body_loader,
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if receipt["status"] != "blocked" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SkillStackError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
