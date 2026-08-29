#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs/film-preproduction/sources/model-sources.yaml"
PROMPT_SOURCES_PATH = ROOT / "docs/film-preproduction/sources/prompt-sources.yaml"
FIXTURE_GLOB = "invalid-model-capability-e[0-6].yaml"
CONTRACT_FIXTURE_GLOB = "invalid-model-manifest-*.yaml"
REQUIRED_CONTRACT_FIXTURE_IDS = {
    "per-model-audio-card-conflict",
    "image-edit-missing-source",
    "image-external-upload-unverified-rights",
    "image-item-qa-and-overlap-truth",
    "image-item-rights-required",
    "longform-family-alias",
    "longform-exact-card-asset-role",
    "stale-card",
    "video-external-upload-blocked-rights",
    "video-qa-must-match-computed-facts",
}
IMAGE_MANIFEST_GLOB = "*image-prompt-manifest.yaml"
VIDEO_MANIFEST_GLOB = "*video-prompt-manifest.yaml"
LONGFORM_MANIFEST_GLOB = "*longform-reference-pack.yaml"
OPTIONAL_SURFACE_GUARD_MACRO_TEXT = (
    "The image is clean and transparent, with complete and natural materials, smooth and uniform texture, "
    "and the main subject Be clear, with distinct background layers, and avoid excessive sharpening, color "
    "spots, and noise Cracks, collapse, and distortion"
)
UNVERSIONED_ALIASES = {"", "latest", "current", "default", "auto"}
EXECUTABLE_STATUSES = {"current"}
RISK_STATUSES = {"preview", "legacy"}
AUTHORIZATION_FIELDS = {
    "likeness_authorization",
    "voice_authorization",
    "brand_or_character_authorization",
    "music_or_audio_rights",
}
QUALIFIED_SOURCE_ASSET_RIGHTS = {
    "client_owned",
    "user_owned",
    "user_licensed",
    "licensed",
    "public_domain",
    "original_work",
    "provider_generated",
    "rights_cleared",
}
DURABLE_RIGHTS_EVIDENCE_TOKENS = {
    "authorization",
    "consent",
    "contract",
    "license",
    "ownership",
    "release",
    "rights",
}
ASSET_ROLE_REFERENCE_MODES = {
    "scene_plate": ("image_reference", "image_to_video", "asset_reference_images"),
    "clean_first_frame": ("first_frame_image", "image_reference", "image_to_video", "first_last_frame", "start_end_frame", "keyframe_images"),
    "clean_end_frame": ("image_reference", "first_last_frame", "start_end_frame", "keyframe_images", "image_to_video"),
    "motion_reference_video": ("video_reference",),
    "audio_reference": ("audio_reference",),
    "storyboard_motion_board": ("storyboard_reference",),
    "element_reference": ("element_reference", "asset_reference_images", "image_reference"),
}

REQUIRED_CARD_FIELDS = {
    "capability_card_id",
    "version",
    "status",
    "verified_on",
    "accessed_on",
    "source",
    "evidence_level",
    "reference_modes",
    "audio_route",
    "duration",
    "edit",
    "extension",
    "rights",
    "failure_modes",
}
VALID_STATUSES = {"current", "preview", "legacy", "deprecated", "workflow_only"}
VALID_EVIDENCE_LEVELS = {"S1", "S2", "S3", "S4"}
AUTHORITATIVE_SOURCE_ALLOWLISTS = {
    "S1": {
        "allowed_source_types": {
            "official_api_changelog",
            "official_api_documentation",
            "official_api_guide",
            "official_api_input_manual",
            "official_api_model_catalog",
            "official_endpoint_manual",
            "official_model_page",
            "official_release_notes",
            "official_stable_model_page",
            "official_vertex_api_reference",
        },
        "allowed_domains": {"developers.openai.com", "docs.dev.runwayml.com", "docs.cloud.google.com", "cloud.google.com"},
    },
    "S2": {
        "allowed_source_types": {"original_research_paper"},
        "allowed_domains": {"arxiv.org"},
    },
    "S3": {
        "allowed_source_types": {
            "legacy_version_scoped_official_guide",
            "official_product_announcement",
            "official_workflow_guide",
            "version_scoped_official_guide",
            "version_scoped_official_launch_guide",
            "version_scoped_official_prompt_guide",
        },
        "allowed_domains": {
            "app.klingai.com",
            "cloud.google.com",
            "developers.openai.com",
            "docs.tapnow.ai",
            "help.runwayml.com",
            "kling.ai",
            "seed.bytedance.com",
        },
    },
}


class AuditError(Exception):
    pass


class EvalFailure(Exception):
    def __init__(self, error_id: str, detail: str) -> None:
        super().__init__(detail)
        self.error_id = error_id


@dataclass
class Check:
    label: str
    ok: bool
    detail: str


@dataclass
class FixtureMetrics:
    detail: str
    negatives_rejected: int
    positive_controls_passed: int


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def load_yaml(path: Path) -> Any:
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AuditError(f"YAML parse failed for {path.relative_to(ROOT)}: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AuditError(f"YAML-to-JSON conversion failed for {path.relative_to(ROOT)}: {exc}") from exc


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists() and path.endswith("/SKILL.md"):
        internal = target.with_name("INTERNAL_SKILL.md")
        if internal.exists():
            target = internal
    if not target.exists() and path == "skills/dircreative/SKILL.md" and (ROOT / "SKILL.md").exists():
        target = ROOT / "SKILL.md"
    return target.read_text(encoding="utf-8")


def add_check(checks: list[Check], label: str, fn: Callable[[], str]) -> None:
    try:
        detail = fn()
    except Exception as exc:  # noqa: BLE001 - audit aggregates independent failures.
        checks.append(Check(label, False, str(exc)))
    else:
        checks.append(Check(label, True, detail))


def parse_iso_date(label: str, value: Any) -> date:
    require(isinstance(value, str) and value, f"{label} missing ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AuditError(f"{label} invalid ISO date: {value}") from exc


def require_fresh(label: str, value: Any, stale_after_days: int, *, today: date | None = None) -> None:
    runtime_day = today or date.today()
    observed = parse_iso_date(label, value)
    age_days = (runtime_day - observed).days
    require(age_days >= 0, f"{label} is future-dated by {-age_days} days")
    require(age_days <= stale_after_days, f"{label} is stale by {age_days - stale_after_days} days")


def validate_source_entry(
    card_id: str,
    entry: dict[str, Any],
    source_tiers: dict[str, dict[str, Any]],
    stale_after_days: int,
) -> None:
    require(entry.get("tier") in VALID_EVIDENCE_LEVELS, f"{card_id} source has invalid tier")
    require(entry.get("type"), f"{card_id} source missing type")
    source_url = str(entry.get("url", ""))
    require(source_url.startswith("https://"), f"{card_id} source missing HTTPS URL")
    require_fresh(f"{card_id} source accessed_on", entry.get("accessed_on"), stale_after_days)
    require(entry.get("claim_scope"), f"{card_id} source missing claim_scope")
    if entry["tier"] in {"S1", "S2", "S3"}:
        contract = source_tiers.get(entry["tier"], {})
        allowed_types = set(contract.get("allowed_source_types", []))
        allowed_domains = set(contract.get("allowed_domains", []))
        hostname = (urlparse(source_url).hostname or "").lower()
        require(entry["type"] in allowed_types, f"{card_id} forged {entry['tier']} source type: {entry['type']}")
        require(hostname in allowed_domains, f"{card_id} forged {entry['tier']} source domain: {hostname}")


def validate_registry() -> tuple[dict[str, dict[str, Any]], dict[str, Any], str]:
    data = load_yaml(REGISTRY_PATH)
    registry = data.get("source_registry", {})
    require(registry.get("version") == "2.0.0", "source registry must be version 2.0.0")
    refresh_policy = registry.get("refresh_policy", {})
    stale_after_days = refresh_policy.get("stale_after_days")
    require(isinstance(stale_after_days, int) and stale_after_days > 0, "registry stale_after_days must be a positive integer")
    require(refresh_policy.get("fail_closed_when_stale_or_ambiguous") is True, "registry freshness must fail closed")
    require_fresh("registry verified_date", registry.get("verified_date"), stale_after_days)
    require_fresh("registry accessed_on", registry.get("accessed_on"), stale_after_days)
    require(list(registry.get("source_tier_precedence", [])) == ["S1", "S2", "S3", "S4"], "source tier precedence drifted")
    require(set(data.get("source_tiers", {})) == VALID_EVIDENCE_LEVELS, "registry must define S1-S4")
    source_tiers = data["source_tiers"]
    for authoritative_tier, expected_contract in AUTHORITATIVE_SOURCE_ALLOWLISTS.items():
        for field, expected_values in expected_contract.items():
            actual_values = set(source_tiers.get(authoritative_tier, {}).get(field, []))
            require(actual_values == expected_values, f"{authoritative_tier} {field} allowlist drifted: {sorted(actual_values ^ expected_values)}")

    contract = data.get("capability_card_contract", {})
    require(set(contract.get("required_fields", [])) == REQUIRED_CARD_FIELDS, "capability-card required fields drifted")

    cards: dict[str, dict[str, Any]] = {}
    for card in data.get("models", []):
        card_id = card.get("capability_card_id", "")
        require(card_id, "card missing capability_card_id")
        require(card_id not in cards, f"duplicate capability card: {card_id}")
        missing = sorted(REQUIRED_CARD_FIELDS - set(card))
        require(not missing, f"{card_id} missing fields: {missing}")
        require(card.get("status") in VALID_STATUSES, f"{card_id} invalid status")
        require(card.get("evidence_level") in VALID_EVIDENCE_LEVELS, f"{card_id} invalid evidence_level")
        require_fresh(f"{card_id} verified_on", card.get("verified_on"), stale_after_days)
        require_fresh(f"{card_id} accessed_on", card.get("accessed_on"), stale_after_days)
        version = str(card.get("version", "")).strip().lower()
        require(version not in UNVERSIONED_ALIASES, f"{card_id} uses an unversioned alias")
        require(card.get("provider_surface"), f"{card_id} missing provider_surface")
        require(card.get("failure_modes"), f"{card_id} missing failure_modes")
        require(card.get("rights", {}).get("gate") == "required", f"{card_id} rights gate must be required")
        require(card.get("rights", {}).get("generation_allowed_when_unverified") is False, f"{card_id} must fail closed on rights")

        source = card.get("source", {})
        validate_source_entry(card_id, source.get("primary", {}), source_tiers, stale_after_days)
        for supporting in source.get("supporting", []):
            validate_source_entry(card_id, supporting, source_tiers, stale_after_days)
        all_tiers = {source["primary"]["tier"], *(entry["tier"] for entry in source.get("supporting", []))}
        require(card["evidence_level"] in all_tiers, f"{card_id} evidence_level has no matching source")
        if card.get("status") == "current":
            require(card.get("evidence_level") != "S4", f"{card_id} cannot be current from S4-only evidence")
            require("preview" not in version, f"{card_id} current card cannot use a preview alias")
        cards[card_id] = card

    required_cards = {
        "gpt_image_2_openai_api",
        "sora_2_openai_videos_api",
        "sora_2_pro_openai_videos_api",
        "seedance_2_0_official_launch",
        "seedance_2_5_official_launch",
        "kling_video_3_0_official_guide",
        "kling_legacy_i2v_5_10_official_guide",
        "runway_gen_4_5_web",
        "runway_aleph_2_0_web",
        "runway_aleph_2_0_api",
        "runway_gen_4_aleph_api_deprecated",
        "veo_3_1_generate_001_vertex_api",
        "veo_3_1_fast_generate_001_vertex_api",
        "veo_3_1_lite_generate_001_vertex_api",
        "tapnow_canvas_workflow_2026_07_10",
    }
    require(required_cards.issubset(cards), f"missing cards: {sorted(required_cards - set(cards))}")
    return cards, registry, f"{len(cards)} versioned cards validated at runtime date {date.today().isoformat()}"


def validate_known_capabilities(cards: dict[str, dict[str, Any]]) -> str:
    gpt = cards["gpt_image_2_openai_api"]
    for mode in ["text_to_image", "image_edit", "mask_edit", "multi_image_reference", "multi_turn_edit"]:
        require(gpt["reference_modes"].get(mode) == "supported", f"GPT Image 2 missing {mode}")
    require(gpt["audio_route"].get("native_audio_supported") is False, "GPT Image 2 must not claim audio")

    for card_id in ["sora_2_openai_videos_api", "sora_2_pro_openai_videos_api"]:
        card = cards[card_id]
        require(card["reference_modes"].get("first_frame_image") == "supported", f"{card_id} missing first-frame mode")
        require(card["reference_modes"].get("human_likeness_character") == "blocked_by_default", f"{card_id} human likeness boundary missing")
        require(card["audio_route"].get("native_audio_supported") is True, f"{card_id} native audio missing")
        require(card["edit"].get("supported") is True, f"{card_id} edit missing")
        require(card["extension"].get("supported") is True, f"{card_id} extension missing")

    seedance = cards["seedance_2_0_official_launch"]
    require(seedance["reference_modes"].get("maximum_image_references") == 9, "Seedance 2.0 image cap drifted")
    require(seedance["reference_modes"].get("maximum_video_references") == 3, "Seedance 2.0 video cap drifted")
    require(seedance["reference_modes"].get("maximum_audio_references") == 3, "Seedance 2.0 audio cap drifted")
    require("2.0" in seedance["reference_modes"].get("limit_scope", ""), "Seedance reference limits must be 2.0-scoped")
    require(
        (seedance.get("access_mode"), seedance.get("execution_mode"), seedance.get("execution_verification_status"))
        == ("documented_product", "manual_export", "unverified"),
        "Seedance launch card must stay documented-product/manual-export and execution-unverified",
    )

    seedance25 = cards["seedance_2_5_official_launch"]
    require(seedance25["reference_modes"].get("maximum_image_references") == 30, "Seedance 2.5 image cap drifted")
    require(seedance25["reference_modes"].get("maximum_video_references") == 10, "Seedance 2.5 video cap drifted")
    require(seedance25["reference_modes"].get("maximum_audio_references") == 10, "Seedance 2.5 audio cap drifted")
    require(seedance25["duration"].get("maximum_sec") == 30, "Seedance 2.5 duration cap drifted")
    require(seedance25["duration"].get("kind") == "upper_bound", "Seedance 2.5 duration evidence must remain upper-bound only")
    require(seedance25["extension"].get("maximum_extensions") == 2, "Seedance 2.5 extension cap drifted")
    require(
        (seedance25.get("access_mode"), seedance25.get("execution_mode"), seedance25.get("execution_verification_status"))
        == ("documented_product", "manual_export", "unverified"),
        "Seedance 2.5 launch card must remain documented-product/manual-export and execution-unverified",
    )

    kling = cards["kling_video_3_0_official_guide"]
    require(kling["duration"].get("minimum_sec") == 3 and kling["duration"].get("maximum_sec") == 15, "Kling VIDEO 3 duration drifted")
    require(kling["reference_modes"].get("multi_shot") == "supported", "Kling VIDEO 3 multi-shot missing")
    require(
        (kling.get("access_mode"), kling.get("execution_mode"), kling.get("execution_verification_status"))
        == ("documented_product", "manual_export", "unverified"),
        "Kling guide card must stay documented-product/manual-export and execution-unverified",
    )
    legacy_kling = cards["kling_legacy_i2v_5_10_official_guide"]
    require(legacy_kling["status"] == "legacy", "Kling 5/10 card must remain legacy")
    require(legacy_kling["duration"].get("supported_values_sec") == [5, 10], "Kling legacy durations drifted")

    runway = cards["runway_gen_4_5_web"]
    require(runway["duration"].get("minimum_sec") == 2 and runway["duration"].get("maximum_sec") == 10, "Runway Gen-4.5 duration drifted")
    require(runway["edit"].get("supported") is False, "Runway Gen-4.5 must not own edit")
    require(runway["edit"].get("route") == "runway_aleph_2_0_web", "Runway edit route must point to Aleph 2.0")
    aleph = cards["runway_aleph_2_0_web"]
    require(aleph["status"] == "current" and aleph["edit"].get("supported") is True, "Aleph 2.0 current edit card invalid")
    require(aleph["duration"].get("surface") == "runway_edit_studio", "Aleph web duration surface drifted")
    require(aleph["duration"].get("verification_status") == "unverified", "Aleph web numeric duration must remain unverified")
    require(aleph["duration"].get("minimum_input_sec") is None and aleph["duration"].get("maximum_input_sec") is None, "Aleph API duration leaked into web card")
    aleph_api = cards["runway_aleph_2_0_api"]
    require(aleph_api["provider_surface"] == "Runway API video_to_video endpoint" and aleph_api["version"] == "aleph2", "Aleph API identity drifted")
    require(aleph_api["duration"].get("surface") == "runway_api_video_to_video", "Aleph API duration surface drifted")
    require(aleph_api["duration"].get("minimum_input_sec") == 2 and aleph_api["duration"].get("maximum_input_sec") == 30, "Aleph API input duration drifted")
    deprecated_aleph = cards["runway_gen_4_aleph_api_deprecated"]
    require(deprecated_aleph["status"] == "deprecated", "Gen-4 Aleph must be deprecated")
    require(deprecated_aleph.get("deprecation", {}).get("replacement_capability_card_id") == "runway_aleph_2_0_api", "Gen-4 Aleph API replacement missing")

    for card_id in ["veo_3_1_generate_001_vertex_api", "veo_3_1_fast_generate_001_vertex_api"]:
        card = cards[card_id]
        require(card["status"] == "current" and card["version"].endswith("-001"), f"{card_id} must use stable 001")
        require(card["audio_route"].get("request_parameter") == "unverified", f"{card_id} must not infer generateAudio from a generic API page")
        require(card["audio_route"].get("parameter_required_for_veo_3") == "unverified", f"{card_id} generateAudio requirement must remain unverified")
        require(card["audio_route"].get("native_audio_supported") == "unverified", f"{card_id} native audio must fail closed")
        require(card["audio_route"].get("generation_audio_route") == "postproduction_required", f"{card_id} must default to postproduction audio")
        require(card["audio_route"].get("verification_status") == "ambiguous_official_surface_conflict", f"{card_id} must preserve official audio ambiguity")
        source_urls = [card["source"]["primary"]["url"], *(entry["url"] for entry in card["source"].get("supporting", []))]
        require(any("release-notes" in url for url in source_urls), f"{card_id} missing preview migration evidence")
        require(any("veo-video-generation" in url for url in source_urls), f"{card_id} missing API reference evidence")
    lite = cards["veo_3_1_lite_generate_001_vertex_api"]
    require(lite["status"] == "preview", "Veo Lite status must remain preview")
    require(lite["audio_route"].get("native_audio_supported") is True, "Veo Lite exact endpoint sound support missing")
    require(lite["audio_route"].get("endpoint_specific") is True, "Veo Lite audio must remain endpoint-specific")
    require(lite["audio_route"].get("generation_audio_route") == "native", "Veo Lite exact sound route drifted")
    require(lite["audio_route"].get("request_parameter") == "unverified", "Veo Lite must not infer an undocumented generateAudio field")

    tapnow = cards["tapnow_canvas_workflow_2026_07_10"]
    require(tapnow["status"] == "workflow_only", "TapNow canvas must remain workflow-only")
    require(tapnow["reference_modes"].get("underlying_model_capability") == "must_resolve_separately", "TapNow must delegate model capability")
    return "provider-specific invariants validated"


def validate_prompt_sources() -> str:
    data = load_yaml(PROMPT_SOURCES_PATH)
    registry = data.get("source_registry", {})
    require(registry.get("version") == "2.0.0", "prompt source registry must be 2.0.0")
    refresh_policy = registry.get("refresh_policy", {})
    stale_after_days = refresh_policy.get("stale_after_days")
    require(isinstance(stale_after_days, int) and stale_after_days > 0, "prompt sources stale_after_days missing")
    require(refresh_policy.get("fail_closed_when_stale_or_ambiguous") is True, "prompt source freshness must fail closed")
    require_fresh("prompt sources verified_date", registry.get("verified_date"), stale_after_days)
    require_fresh("prompt sources accessed_on", registry.get("accessed_on"), stale_after_days)
    sources = {item.get("source_key"): item for item in data.get("sources", [])}
    for source_key, source in sources.items():
        require_fresh(f"prompt source {source_key} accessed_on", source.get("accessed_on"), stale_after_days)
    macro = sources.get("user_surface_integrity_guard", {})
    require(macro.get("status") == "optional_internal_qa_macro", "surface macro must be optional internal QA")
    require(macro.get("activation_policy", {}).get("default_application") is False, "surface macro must default off")
    require("appended_to_every_image_prompt" in macro.get("activation_policy", {}).get("forbidden_when", []), "surface macro universal append guard missing")
    for key in ["wuyoscar_gpt_image_2_skill", "youmind_gpt_image_2_prompts_search"]:
        require(sources[key].get("evidence_level") == "S4" and sources[key].get("status") == "clue_only", f"{key} must remain S4 clue-only")
    require(sources["openai_gpt_image_2_generation_and_editing"].get("evidence_level") == "S1", "OpenAI prompt source must be S1")
    require(sources["veo_3_1_vertex_prompting"].get("status") == "current_endpoint_scoped", "Veo prompt source must be endpoint-scoped")
    return f"{len(sources)} prompt sources validated"


def validate_contract_surfaces() -> str:
    required_terms = {
        "docs/film-preproduction/capability-aware-generation-policy.md": [
            "Source-Tier Contract",
            "Desired Audio vs Generation Audio Route",
            "Preserve / Change Contract",
            "Rights Gate",
            "E0-E6 Behavioral Eval Contract",
            "external_upload_authorized",
            "instructions_only",
        ],
        "docs/film-preproduction/reference-locking-policy.md": [
            "Storyboard / Clean-Frame Separation",
            "capability_card_id",
            "rights",
            "preserve",
            "change",
        ],
        "docs/film-preproduction/clean-frame-export-policy.md": [
            "Capability-Resolved Strategy",
            "planning_only",
            "Clean frame contract:",
        ],
        "docs/film-preproduction/longform-decomposition-policy.md": [
            "capability_card_id",
            "generation_audio_route",
            "transformation_contract",
        ],
        "docs/film-preproduction/schemas/reference-pack-manifest.yaml": [
            "capability_resolution:",
            "rights_gate:",
            "planning_boards_separated_from_clean_frames",
        ],
        "docs/film-preproduction/schemas/image-prompt-manifest.yaml": [
            "transformation_contract:",
            "optional_internal_qa_macro",
            "prohibited_in_image_prompt",
            "external_upload_authorized:",
            "rights_evidence_refs:",
            "allow_incidental_change:",
            "forbidden_change:",
            "capability_card_resolved:",
            "optional_qa_macro_not_forced:",
        ],
        "docs/film-preproduction/schemas/video-prompt-manifest.yaml": [
            "desired_audio:",
            "generation_audio_route:",
            "deprecated_card_ids_rejected",
            "external_upload_authorized:",
            "exact_capability_cards_resolved:",
            "official_source_conflicts_preserved:",
        ],
        "docs/film-preproduction/schemas/longform-reference-pack.yaml": [
            "capability_resolution:",
            "capability_targets:",
            "capability_card_id:",
            "family_aliases_absent:",
        ],
        "docs/film-preproduction/research/model-adapter-notes.md": [
            "runway_aleph_2_0_web",
            "runway_aleph_2_0_api",
            "documented_product",
            "manual_export",
            "execution verification: `unverified`",
        ],
        "skills/dircreative/reference-image-planner/SKILL.md": [
            "capability_card_id + version + provider_surface",
            "Run the rights gate",
        ],
        "skills/dircreative/image-prompt-compiler/SKILL.md": [
            "optional internal QA macro",
            "preserve",
            "change",
        ],
        "skills/dircreative/video-model-adapter/SKILL.md": [
            "generateAudio",
            "runway_aleph_2_0_api",
            "runway_gen_4_aleph_api_deprecated",
            "desired_audio",
        ],
        "skills/dircreative/generation-qa/SKILL.md": [
            "E0 rejects",
            "E6 rejects",
            "dircreative_model_capability_audit.py",
        ],
    }
    for path, terms in required_terms.items():
        text = read(path)
        missing = [term for term in terms if term not in text]
        require(not missing, f"{path} missing terms: {missing}")

    image_skill = read("skills/dircreative/image-prompt-compiler/SKILL.md")
    require("append this exact suffix" not in image_skill, "image compiler still forces the legacy suffix")

    reference_schema = read("docs/film-preproduction/schemas/reference-pack-manifest.yaml")
    leaked_schema_facts = [
        term
        for term in [
            "max_image_refs_policy",
            "max_video_refs_policy",
            "max_audio_refs_policy",
            "mixed_file_cap_policy",
            "max_images_per_element",
        ]
        if term in reference_schema
    ]
    require(not leaked_schema_facts, f"static provider limits leaked into reference schema: {leaked_schema_facts}")

    longform_schema = read("docs/film-preproduction/schemas/longform-reference-pack.yaml")
    forbidden_longform_family_fields = [
        term
        for term in ["model_targets:", "seedance:", "kling:", "runway:", "veo:", "max_image_refs", "max_video_refs", "max_audio_refs"]
        if term in longform_schema
    ]
    require(not forbidden_longform_family_fields, f"model-family facts leaked into longform schema: {forbidden_longform_family_fields}")

    core = "\n".join(
        read(path)
        for path in [
            "docs/film-preproduction/capability-aware-generation-policy.md",
            "docs/film-preproduction/reference-locking-policy.md",
            "docs/film-preproduction/clean-frame-export-policy.md",
            "docs/film-preproduction/longform-decomposition-policy.md",
        ]
    ).lower()
    forbidden_static_facts = [
        "up to 9 images",
        "5-second or 10-second video outputs",
        "3 to 15 seconds",
        "2 - 10 seconds",
        "reference images per element: 4",
    ]
    leaked = [term for term in forbidden_static_facts if term in core]
    require(not leaked, f"platform facts leaked into core policy: {leaked}")
    return f"{len(required_terms)} contract surfaces validated"


def card_source_urls(card: dict[str, Any]) -> list[str]:
    source = card.get("source", {})
    entries = [source.get("primary", {}), *source.get("supporting", [])]
    return [entry.get("url", "") for entry in entries if entry.get("url")]


def card_has_source_conflict(card: dict[str, Any]) -> bool:
    verification_status = str(card.get("audio_route", {}).get("verification_status", ""))
    return "conflict" in verification_status


def resolve_exact_card(
    selection: dict[str, Any],
    cards: dict[str, dict[str, Any]],
    context: str,
    *,
    strict_receipt: bool,
) -> dict[str, Any]:
    card_id = selection.get("capability_card_id", "")
    version = str(selection.get("version", "")).strip()
    require(card_id in cards and version.lower() not in UNVERSIONED_ALIASES, f"{context} exact capability card and version required")
    card = cards[card_id]
    require(version == card["version"], f"{context} card/version mismatch")
    require(selection.get("status") == card["status"], f"{context} card/status mismatch")
    require(selection.get("provider_surface") == card["provider_surface"], f"{context} card/provider surface mismatch")
    status_allowed = card["status"] in EXECUTABLE_STATUSES or (
        card["status"] in RISK_STATUSES and selection.get("accepted_status_risk") is True
    )
    require(status_allowed, f"{context} card status is not executable")
    if strict_receipt:
        require(selection.get("resolution_status") == "resolved", f"{context} capability resolution must be resolved")
        require(selection.get("verified_on") == card["verified_on"], f"{context} verified_on mismatch")
        require(selection.get("accessed_on") == card["accessed_on"], f"{context} accessed_on mismatch")
        require(selection.get("evidence_level") == card["evidence_level"], f"{context} evidence-level mismatch")
        urls = set(selection.get("source_urls", []))
        require(set(card_source_urls(card)).issubset(urls), f"{context} source receipt does not cover exact card")
        if card_has_source_conflict(card):
            require(selection.get("source_conflicts"), f"{context} official source conflict was hidden")
        for field in ["access_mode", "execution_mode", "execution_verification_status"]:
            if field in card:
                require(selection.get(field) == card[field], f"{context} {field} mismatch")
    return card


def rights_gate_passed(gate: dict[str, Any]) -> bool:
    return gate.get("status") in {"verified", "conditional"} and gate.get("generation_allowed") is True


def validate_rights_gate(gate: dict[str, Any], context: str, *, execution_kind: str = "none") -> None:
    require(execution_kind in {"none", "local", "external"}, f"{context} invalid execution kind")
    require(gate.get("status") in {"verified", "conditional", "unverified", "blocked"}, f"{context} rights status missing")
    require(isinstance(gate.get("provider_restrictions_checked"), bool), f"{context} provider restriction receipt missing")
    require(isinstance(gate.get("generation_allowed"), bool), f"{context} generation_allowed missing")
    require(isinstance(gate.get("evidence_refs"), list), f"{context} evidence_refs must be a list")
    evidence_refs = gate.get("evidence_refs", [])
    require(
        all(isinstance(ref, str) and ref.strip() for ref in evidence_refs),
        f"{context} evidence_refs must contain durable reference identifiers",
    )
    conditions = gate.get("conditions", [])
    require(isinstance(conditions, list), f"{context} conditions receipt must be a list")
    authorization_values = {field: gate.get(field, "not_applicable") for field in AUTHORIZATION_FIELDS}
    invalid_authorizations = {
        field: value
        for field, value in authorization_values.items()
        if value not in {"not_applicable", "verified", "unverified", "blocked"}
    }
    require(not invalid_authorizations, f"{context} invalid authorization values: {invalid_authorizations}")
    blocked_or_unverified = {
        field: value for field, value in authorization_values.items() if value in {"blocked", "unverified"}
    }
    if gate.get("status") in {"verified", "conditional"}:
        require(gate.get("provider_restrictions_checked") is True, f"{context} qualified rights conflict with unchecked provider restrictions")
        require(not blocked_or_unverified, f"{context} qualified rights conflict with authorization: {blocked_or_unverified}")
        require(gate.get("source_asset_rights"), f"{context} qualified rights missing source-asset basis")
        require(gate.get("evidence_refs"), f"{context} qualified rights missing evidence")
    if gate.get("status") == "conditional":
        require(conditions, f"{context} conditional rights missing conditions")
    else:
        require(not conditions, f"{context} conditions require conditional rights status")
    if gate.get("status") in {"unverified", "blocked"}:
        require(gate.get("generation_allowed") is False, f"{context} unqualified rights cannot allow generation")
    if gate.get("generation_allowed") is True:
        require(gate.get("status") in {"verified", "conditional"}, f"{context} generation permission requires qualified rights")
        require(
            gate.get("source_asset_rights") in QUALIFIED_SOURCE_ASSET_RIGHTS,
            f"{context} generation permission requires typed source-asset rights",
        )
        durable_evidence = [
            ref
            for ref in evidence_refs
            if not ref.lower().startswith(("self-asserted", "note", "memo"))
            and any(token in ref.lower() for token in DURABLE_RIGHTS_EVIDENCE_TOKENS)
        ]
        require(durable_evidence, f"{context} generation permission requires durable authorization or license evidence")
    if execution_kind != "none":
        allowed_statuses = {"verified", "conditional"} if execution_kind == "external" else {"verified"}
        require(gate.get("status") in allowed_statuses, f"{context} {execution_kind} execution requires qualified rights")
        require(gate.get("generation_allowed") is True, f"{context} execution requires generation_allowed")
        require(gate.get("provider_restrictions_checked") is True, f"{context} execution requires provider restriction review")
        require(not blocked_or_unverified, f"{context} execution conflicts with authorization: {blocked_or_unverified}")


def validate_asset_input_policy(
    asset_role: Any,
    input_mode: Any,
    card: dict[str, Any],
    context: str,
) -> None:
    valid_modes = {"allowed", "conditional", "forbidden", "planning_only", "element_only", "reference_only"}
    require(input_mode in valid_modes, f"{context} invalid direct-input mode")
    require(asset_role in ASSET_ROLE_REFERENCE_MODES, f"{context} unknown asset role: {asset_role}")
    if input_mode in {"forbidden", "planning_only"}:
        return

    reference_modes = card.get("reference_modes", {})
    candidates = ASSET_ROLE_REFERENCE_MODES[asset_role]
    observed = {mode: reference_modes.get(mode, "not_supported") for mode in candidates}
    supported = any(value == "supported" for value in observed.values())
    conditional = any(isinstance(value, str) and value.startswith("conditional") for value in observed.values())
    if input_mode in {"allowed", "element_only"}:
        require(supported, f"{context} {asset_role} unsupported by exact card reference_modes: {observed}")
    else:
        require(supported or conditional, f"{context} {asset_role} unsupported by exact card reference_modes: {observed}")
    if input_mode == "element_only":
        require(asset_role == "element_reference", f"{context} element_only requires element_reference asset role")


def validate_execution_capability(
    visual_output_mode: Any,
    execution: dict[str, Any],
    rights_gate: dict[str, Any],
    context: str,
    *,
    external_instructions: Any,
) -> str:
    require(visual_output_mode in {"prompt_only", "assisted_generation", "external_generation"}, f"{context} visual output mode missing")
    require(isinstance(execution.get("available"), bool), f"{context} runtime availability missing")
    require(isinstance(execution.get("allowed_by_user"), bool), f"{context} user authorization missing")
    require(isinstance(execution.get("external_upload_authorized"), bool), f"{context} external upload authorization missing")
    state = execution.get("external_execution_state")
    require(state in {"instructions_only", "external_upload_ready", "externally_executed"}, f"{context} external execution state missing")
    evidence = execution.get("external_execution_evidence")
    require(isinstance(evidence, list), f"{context} external execution evidence must be a list")
    local_requested = execution.get("available") is True and execution.get("allowed_by_user") is True
    external_authorized = execution.get("external_upload_authorized") is True
    if execution.get("allowed_by_user") is True:
        require(execution.get("available") is True, f"{context} user-authorized local execution has no available runtime")

    if visual_output_mode == "assisted_generation":
        require(local_requested, f"{context} assisted generation requires an available user-authorized runtime")
    else:
        require(not local_requested, f"{context} local execution conflicts with {visual_output_mode}")

    if visual_output_mode == "external_generation":
        require(external_instructions, f"{context} external generation instructions missing")
        if external_authorized:
            require(state in {"external_upload_ready", "externally_executed"}, f"{context} authorized external upload cannot remain instructions-only")
            require(execution.get("provider") not in {None, "", "none", "unknown"}, f"{context} external provider unresolved")
            if state == "externally_executed":
                require(evidence, f"{context} externally executed claim lacks evidence")
            validate_rights_gate(rights_gate, f"{context} rights gate", execution_kind="external")
            return "external"
        require(state == "instructions_only", f"{context} unauthorized external upload must remain instructions-only")
        require(not evidence, f"{context} instructions-only handoff cannot claim external execution evidence")
    else:
        require(not external_authorized, f"{context} external upload authorization conflicts with {visual_output_mode}")
        require(state == "instructions_only", f"{context} non-external mode cannot claim external execution")
        require(not evidence, f"{context} non-external mode cannot claim external execution evidence")

    execution_kind = "local" if local_requested else "none"
    validate_rights_gate(rights_gate, f"{context} rights gate", execution_kind=execution_kind)
    return execution_kind


def desired_audio_requested(desired_audio: Any) -> bool:
    if desired_audio is None or (isinstance(desired_audio, str) and desired_audio in {"", "none", "silence"}):
        return False
    if isinstance(desired_audio, dict):
        if desired_audio.get("silence") is True:
            return False
        return any(value is not None and value is not False and value != "" and value != [] and value != "none" for value in desired_audio.values())
    return True


def validate_audio_route(
    card: dict[str, Any],
    route: Any,
    desired_audio: Any,
    handoff: Any,
    context: str,
) -> None:
    require(route in {"native", "native_configurable", "reference_audio", "preserve_source", "postproduction", "none"}, f"{context} unresolved or invalid audio route")
    card_audio = card.get("audio_route", {})
    if route in {"native", "native_configurable", "reference_audio"}:
        require(card_audio.get("native_audio_supported") is True, f"{context} native/reference audio unsupported by exact card")
        require(card.get("execution_verification_status") != "unverified", f"{context} native audio cannot execute on an unverified manual surface")
    if route == "native_configurable":
        require(card_audio.get("generation_audio_route") == "native_configurable", f"{context} card does not expose configurable native audio")
    if route == "reference_audio":
        require(card_audio.get("audio_reference_supported") is True, f"{context} card does not support audio reference input")
    if route == "preserve_source":
        require("preserve_source" in str(card_audio.get("generation_audio_route", "")), f"{context} source-audio preservation unsupported")
    if route == "postproduction" and desired_audio_requested(desired_audio):
        require(isinstance(handoff, str) and handoff.strip(), f"{context} post-production audio handoff missing")
    if route == "none":
        require(not desired_audio_requested(desired_audio), f"{context} desired audio conflicts with route none")


def validate_transformation_contract(
    operation: Any,
    contract: dict[str, Any],
    context: str,
    *,
    source_references: list[Any] | None = None,
    require_extended_fields: bool = False,
) -> None:
    require(operation in {"generate", "edit", "extend", "retry"}, f"{context} invalid operation")
    preserve = contract.get("preserve") if require_extended_fields else contract.get("preserve", [])
    change = contract.get("change") if require_extended_fields else contract.get("change", [])
    require(isinstance(preserve, list) and isinstance(change, list), f"{context} preserve/change must be lists")
    forbidden = contract.get("forbidden_change", [])
    incidental = contract.get("allow_incidental_change", [])
    require(isinstance(forbidden, list), f"{context} forbidden_change must be a list")
    require(isinstance(incidental, list), f"{context} allow_incidental_change must be a list")
    if require_extended_fields:
        for field in ["allow_incidental_change", "forbidden_change", "overlap_check"]:
            require(field in contract, f"{context} transformation field missing: {field}")
    conflicts = {
        "preserve/change": set(preserve) & set(change),
        "preserve/incidental": set(preserve) & set(incidental),
        "change/forbidden": set(change) & set(forbidden),
        "incidental/forbidden": set(incidental) & set(forbidden),
    }
    conflicts = {label: sorted(values) for label, values in conflicts.items() if values}
    require(not conflicts, f"{context} transformation overlap: {conflicts}")
    if "overlap_check" in contract or require_extended_fields:
        require(contract.get("overlap_check") == "pass", f"{context} overlap_check must truthfully be pass")
    if operation == "edit":
        require(preserve and change, f"{context} edit requires non-empty preserve and change sets")
        require(source_references, f"{context} image edit requires a source/reference")


def validate_declared_boolean_qa(qa: Any, expected: dict[str, bool], context: str) -> None:
    require(isinstance(qa, dict), f"{context} QA receipt missing")
    for field, computed in expected.items():
        require(isinstance(qa.get(field), bool), f"{context} QA field missing or non-boolean: {field}")
        require(qa[field] is computed, f"{context} lying QA field {field}: declared {qa[field]}, computed {computed}")


def validate_optional_surface_guard(prompt: str, macro: dict[str, Any], context: str) -> None:
    suffix_present = OPTIONAL_SURFACE_GUARD_MACRO_TEXT in prompt
    enabled = macro.get("optional_internal_qa_macro") is True
    if suffix_present:
        require(enabled, f"{context} fixed E6 suffix present without optional macro activation")
        require(macro.get("activation") in {"observed_failure", "internal_ab_eval"}, f"{context} fixed E6 suffix has invalid activation")
        require(macro.get("failure_id"), f"{context} fixed E6 suffix lacks observed failure ID")
    if enabled:
        require(suffix_present, f"{context} optional E6 macro enabled but suffix absent")


def evaluate_e0(case: dict[str, Any], cards: dict[str, dict[str, Any]]) -> None:
    selection = case.get("selection", {})
    try:
        resolve_exact_card(selection, cards, "E0 selection", strict_receipt=False)
    except AuditError as exc:
        raise EvalFailure("E0_EXACT_CARD_REQUIRED", "exact card, version, and provider surface are required")


def evaluate_e1(case: dict[str, Any], cards: dict[str, dict[str, Any]]) -> None:
    claim = case.get("claim", {})
    if claim.get("authoritative") is not True:
        return
    registered_authoritative = {
        (
            entry.get("tier"),
            entry.get("type"),
            entry.get("url"),
            entry.get("claim_scope"),
            card.get("version"),
            card.get("provider_surface"),
        )
        for card in cards.values()
        for entry in [card.get("source", {}).get("primary", {}), *card.get("source", {}).get("supporting", [])]
        if entry.get("tier") in {"S1", "S2", "S3"}
    }
    binding = (
        claim.get("evidence_level"),
        claim.get("source_type"),
        claim.get("source_url"),
        claim.get("claim_scope"),
        claim.get("version_scope"),
        claim.get("provider_surface"),
    )
    authoritative_level = claim.get("evidence_level") in {"S1", "S2", "S3"}
    forged_or_unbound = authoritative_level and binding not in registered_authoritative
    if not authoritative_level or forged_or_unbound or not claim.get("version_scope") or not claim.get("provider_surface"):
        raise EvalFailure("E1_AUTHORITATIVE_SOURCE_REQUIRED", "forged, S4, or unscoped evidence cannot authorize capability")


def evaluate_e2(case: dict[str, Any], cards: dict[str, dict[str, Any]]) -> None:
    plan = case.get("audio_plan", {})
    card = cards.get(plan.get("capability_card_id"))
    if card is None:
        raise EvalFailure("E2_AUDIO_ROUTE_MISMATCH", "audio plan card is unresolved")
    try:
        validate_audio_route(
            card,
            plan.get("generation_audio_route"),
            plan.get("desired_audio"),
            plan.get("postproduction_handoff"),
            "E2 audio plan",
        )
    except AuditError as exc:
        raise EvalFailure("E2_AUDIO_ROUTE_MISMATCH", "post-production audio needs a handoff")


def evaluate_e3(case: dict[str, Any], _cards: dict[str, dict[str, Any]]) -> None:
    try:
        validate_transformation_contract(
            case.get("operation"),
            case.get("transformation_contract", {}),
            "E3 edit",
            source_references=case.get("source_references"),
        )
    except AuditError as exc:
        raise EvalFailure("E3_PRESERVE_CHANGE_INVALID", str(exc)) from exc


def evaluate_e4(case: dict[str, Any], _cards: dict[str, dict[str, Any]]) -> None:
    try:
        execution_state = case.get("execution_state")
        execution_kind = "external" if execution_state == "external_upload_ready" else "local" if execution_state == "generation_ready" else "none"
        validate_rights_gate(
            case.get("rights_gate", {}),
            "E4 rights gate",
            execution_kind=execution_kind,
        )
    except AuditError as exc:
        raise EvalFailure("E4_RIGHTS_GATE_BLOCKED", str(exc)) from exc


def evaluate_e5(case: dict[str, Any], _cards: dict[str, dict[str, Any]]) -> None:
    bindings = case.get("bindings", [])
    has_direct_clean_frame = False
    for binding in bindings:
        role = binding.get("asset_role", "")
        mode = binding.get("reference_mode", "")
        direct = binding.get("direct_input_allowed") is True
        if "storyboard" in role and direct and mode in {"first_frame", "last_frame", "clean_key_frame"}:
            raise EvalFailure("E5_BOARD_BOUND_AS_CLEAN_FRAME", "storyboard cannot be a literal clean frame")
        if role in {"clean_first_frame", "clean_key_frame", "clean_end_frame"} and direct:
            has_direct_clean_frame = True
    if case.get("requires_direct_frame") is True and not has_direct_clean_frame:
        raise EvalFailure("E5_BOARD_BOUND_AS_CLEAN_FRAME", "required direct clean frame is missing")


def evaluate_e6(case: dict[str, Any], _cards: dict[str, dict[str, Any]]) -> None:
    macro = case.get("qa_macro", {})
    normalized = {
        "optional_internal_qa_macro": macro.get("enabled") is True,
        "activation": macro.get("activation", "off"),
        "failure_id": macro.get("failure_id", ""),
    }
    prompt = OPTIONAL_SURFACE_GUARD_MACRO_TEXT if case.get("prompt_contains_fixed_suffix") is True else "targeted prompt without fixed suffix"
    try:
        if macro.get("application") == "required_for_all_prompts":
            raise AuditError("optional QA macro was forced universally")
        validate_optional_surface_guard(prompt, normalized, "E6 prompt")
    except AuditError as exc:
        raise EvalFailure("E6_OPTIONAL_QA_MACRO_FORCED", str(exc)) from exc


EVALUATORS: dict[str, Callable[[dict[str, Any], dict[str, dict[str, Any]]], None]] = {
    "E0": evaluate_e0,
    "E1": evaluate_e1,
    "E2": evaluate_e2,
    "E3": evaluate_e3,
    "E4": evaluate_e4,
    "E5": evaluate_e5,
    "E6": evaluate_e6,
}


def validate_fixtures(cards: dict[str, dict[str, Any]]) -> FixtureMetrics:
    fixture_paths = sorted((ROOT / "tests/fixtures").glob(FIXTURE_GLOB))
    require(len(fixture_paths) == 7, f"expected 7 E0-E6 fixtures, found {len(fixture_paths)}")
    seen: set[str] = set()
    negative_count = 0
    positive_count = 0
    for path in fixture_paths:
        fixture = load_yaml(path).get("eval_fixture", {})
        eval_id = fixture.get("id")
        require(eval_id in EVALUATORS, f"{path.name} invalid eval id")
        require(eval_id not in seen, f"duplicate fixture for {eval_id}")
        seen.add(eval_id)
        evaluator = EVALUATORS[eval_id]
        negatives = fixture.get("negative_cases")
        if negatives is None:
            negatives = [{"case": fixture.get("negative", {}), "expected_error_id": fixture.get("expected_error_id")}]
        positives = fixture.get("positive_controls")
        if positives is None:
            positives = [fixture.get("positive_control", {})]
        require(isinstance(negatives, list) and negatives, f"{path.name} negative cases missing")
        require(isinstance(positives, list) and positives, f"{path.name} positive controls missing")
        for index, negative in enumerate(negatives, start=1):
            case = negative.get("case", negative)
            expected_error = negative.get("expected_error_id", fixture.get("expected_error_id"))
            try:
                evaluator(case, cards)
            except EvalFailure as exc:
                require(exc.error_id == expected_error, f"{path.name} negative {index} rejected with {exc.error_id}, expected {expected_error}")
                negative_count += 1
            else:
                raise AuditError(f"{path.name} negative {index} was not rejected")
        for index, positive in enumerate(positives, start=1):
            try:
                evaluator(positive, cards)
            except EvalFailure as exc:
                raise AuditError(f"{path.name} positive control {index} failed with {exc.error_id}: {exc}") from exc
            positive_count += 1
    require(seen == set(EVALUATORS), f"fixture coverage mismatch: {sorted(set(EVALUATORS) - seen)}")
    return FixtureMetrics(
        detail=f"{negative_count} negative fixtures rejected; {positive_count} positive controls passed",
        negatives_rejected=negative_count,
        positive_controls_passed=positive_count,
    )


def resolve_prompt_text(manifest_path: Path, image: dict[str, Any]) -> str:
    inline_prompt = image.get("prompt")
    if isinstance(inline_prompt, str) and inline_prompt.strip():
        return inline_prompt
    prompt_ref = image.get("prompt_file") or image.get("asset_output", {}).get("prompt_file")
    require(isinstance(prompt_ref, str) and prompt_ref, f"{manifest_path.name} image {image.get('image_id')} missing prompt")
    path_ref, _, fragment = prompt_ref.partition("#")
    target = ROOT / path_ref
    if target.resolve() == manifest_path.resolve() and fragment == image.get("image_id"):
        raise AuditError(f"{manifest_path.name} image {image.get('image_id')} self-reference has no inline prompt")
    require(target.is_file(), f"{manifest_path.name} prompt file missing: {path_ref}")
    return target.read_text(encoding="utf-8")


def validate_image_item(
    image: dict[str, Any],
    manifest_rights: dict[str, Any],
    card: dict[str, Any],
    context: str,
    *,
    prompt: str,
) -> None:
    capability_resolved = image.get("capability_card_id") == card["capability_card_id"]
    require(capability_resolved, f"{context} card conflicts with manifest capability")
    operation = image.get("operation")
    source_references = image.get("source_references")
    require(isinstance(source_references, list), f"{context} source_references must be a list")
    validate_transformation_contract(
        operation,
        image.get("transformation_contract", {}),
        context,
        source_references=source_references,
        require_extended_fields=True,
    )

    item_rights = image.get("rights")
    require(isinstance(item_rights, dict), f"{context} per-image rights missing")
    require(item_rights.get("status") == manifest_rights.get("status"), f"{context} rights status conflicts with manifest gate")
    require(isinstance(item_rights.get("evidence_refs"), list), f"{context} per-image rights evidence must be a list")
    require(item_rights.get("evidence_refs") == manifest_rights.get("evidence_refs"), f"{context} rights evidence conflicts with manifest gate")

    edit_sources_valid = operation != "edit"
    if operation == "edit":
        require(card.get("edit", {}).get("supported") is True, f"{context} edit unsupported by exact card")
        edit_sources_valid = bool(source_references)
        evidence_refs = set(item_rights["evidence_refs"])
        for reference in source_references:
            require(reference.get("ref_id") and reference.get("file_or_generation_id"), f"{context} source/reference receipt incomplete")
            bound_rights = reference.get("rights_evidence_refs")
            require(isinstance(bound_rights, list) and bound_rights, f"{context} edit source/reference rights evidence missing")
            require(set(bound_rights).issubset(evidence_refs), f"{context} edit source/reference rights evidence is unbound")

    surface_guard = image.get("style_config", {}).get("quality_and_artifact_control", {}).get("surface_integrity_guard", {})
    validate_optional_surface_guard(prompt, surface_guard, context)
    expected_qa = {
        "capability_card_resolved": capability_resolved,
        "rights_gate_passed": rights_gate_passed(manifest_rights),
        "preserve_change_disjoint": True,
        "source_reference_present_for_edit": edit_sources_valid,
        "optional_qa_macro_not_forced": True,
    }
    validate_declared_boolean_qa(image.get("qa"), expected_qa, context)


def validate_real_image_manifest(path: Path, cards: dict[str, dict[str, Any]], registry: dict[str, Any]) -> int:
    data = load_yaml(path)
    manifest = data.get("image_prompt_manifest", {})
    context = str(path.relative_to(ROOT))
    visual_output_mode = manifest.get("visual_output_mode")
    require(visual_output_mode in {"prompt_only", "assisted_generation", "external_generation"}, f"{context} visual output mode missing")
    capability = data.get("capability_resolution", {})
    require(capability.get("registry_path") == str(REGISTRY_PATH.relative_to(ROOT)), f"{context} registry path mismatch")
    require(capability.get("registry_version") == registry.get("version"), f"{context} registry version mismatch")
    card = resolve_exact_card(capability, cards, f"{context} capability", strict_receipt=True)
    execution = data.get("execution_capabilities", {}).get("image_generation", {})
    rights_gate = data.get("rights_gate", {})
    validate_execution_capability(
        visual_output_mode,
        execution,
        rights_gate,
        f"{context} image generation",
        external_instructions=data.get("handoff_notes", {}).get("external_generation_instructions"),
    )
    audio_intent = data.get("audio_intent", {})
    require(audio_intent.get("generation_audio_route") == "not_applicable", f"{context} image manifest cannot claim an audio route")
    require(audio_intent.get("prohibited_in_image_prompt") is True, f"{context} image audio must remain metadata-only")
    images = data.get("images", [])
    require(images, f"{context} has no images")
    for image in images:
        image_id = image.get("image_id", "unknown")
        item_context = f"{context} image {image_id}"
        if visual_output_mode == "external_generation" and execution.get("external_upload_authorized") is False:
            require(
                image.get("asset_output", {}).get("status") in {"prompt_ready", "external_pending", "rejected"},
                f"{item_context} unauthorized external handoff can only remain instructions-only",
            )
        validate_image_item(image, rights_gate, card, item_context, prompt=resolve_prompt_text(path, image))
    return len(images)


def selected_video_card_id(model_key: str, prompt: dict[str, Any]) -> str:
    if model_key == "runway":
        operation = prompt.get("operation")
        return prompt.get("edit_capability_card_id") if operation == "edit" else prompt.get("generation_capability_card_id")
    return prompt.get("capability_card_id")


def validate_real_video_manifest(path: Path, cards: dict[str, dict[str, Any]], registry: dict[str, Any]) -> int:
    data = load_yaml(path)
    manifest = data.get("video_prompt_manifest", {})
    context = str(path.relative_to(ROOT))
    visual_output_mode = manifest.get("visual_output_mode")
    require(visual_output_mode in {"prompt_only", "assisted_generation", "external_generation"}, f"{context} visual output mode missing")
    resolution = data.get("capability_resolution", {})
    require(resolution.get("registry_path") == str(REGISTRY_PATH.relative_to(ROOT)), f"{context} registry path mismatch")
    require(resolution.get("registry_version") == registry.get("version"), f"{context} registry version mismatch")
    selected_cards: dict[str, dict[str, Any]] = {}
    for selection in resolution.get("selected_cards", []):
        card = resolve_exact_card(selection, cards, f"{context} selected card", strict_receipt=True)
        model_key = selection.get("model_key")
        require(model_key == card.get("model_key"), f"{context} model key/card conflict")
        require(model_key not in selected_cards, f"{context} duplicate model key: {model_key}")
        selected_cards[model_key] = card
    require(selected_cards, f"{context} has no selected cards")

    execution = data.get("execution_capabilities", {}).get("video_generation", {})
    rights_gate = data.get("rights_gate", {})
    external_instructions = [
        item.get("external_generation_instructions")
        for item in data.get("reference_map", [])
        if item.get("external_generation_instructions")
    ]
    validate_execution_capability(
        visual_output_mode,
        execution,
        rights_gate,
        f"{context} video generation",
        external_instructions=external_instructions,
    )

    audio_plan = data.get("audio_plan", {})
    shared_desired_audio = audio_plan.get("desired_audio")
    routes: dict[str, dict[str, Any]] = {}
    for route in audio_plan.get("per_model_routes", []):
        model_key = route.get("model_key")
        require(model_key in selected_cards and model_key not in routes, f"{context} audio route model/card conflict")
        card = selected_cards[model_key]
        require(route.get("capability_card_id") == card["capability_card_id"], f"{context} {model_key} audio card mismatch")
        validate_audio_route(
            card,
            route.get("generation_audio_route"),
            shared_desired_audio,
            route.get("postproduction_handoff"),
            f"{context} {model_key} audio plan",
        )
        routes[model_key] = route

    enabled_prompts: dict[str, str] = {}
    for model_key, prompt in data.get("model_prompts", {}).items():
        if prompt.get("enabled") is not True:
            continue
        prompt_card_id = selected_video_card_id(model_key, prompt)
        require(model_key in selected_cards, f"{context} enabled {model_key} has no selected exact card")
        require(prompt_card_id == selected_cards[model_key]["capability_card_id"], f"{context} {model_key} prompt/card conflict")
        prompt_selection = {
            "capability_card_id": prompt_card_id,
            "version": prompt.get("version"),
            "status": prompt.get("status"),
            "provider_surface": prompt.get("provider_surface"),
        }
        card = resolve_exact_card(prompt_selection, cards, f"{context} {model_key} prompt", strict_receipt=False)
        operation = prompt.get("operation")
        validate_transformation_contract(operation, prompt.get("transformation_contract", {}), f"{context} {model_key} prompt")
        if operation == "edit":
            require(card.get("edit", {}).get("supported") is True, f"{context} {model_key} edit unsupported")
        if operation == "extend":
            require(card.get("extension", {}).get("supported") is True, f"{context} {model_key} extension unsupported")
        require(model_key in routes, f"{context} {model_key} per-model audio route missing")
        route = routes[model_key]
        require(prompt.get("generation_audio_route") == route.get("generation_audio_route"), f"{context} {model_key} prompt/audio-plan conflict")
        generate_audio_parameter = route.get("generate_audio_parameter")
        if card.get("audio_route", {}).get("request_parameter") == "generateAudio":
            require(isinstance(generate_audio_parameter, bool), f"{context} {model_key} generateAudio must be explicit")
            require(prompt.get("generate_audio_parameter") is generate_audio_parameter, f"{context} {model_key} generateAudio prompt/plan conflict")
        else:
            require(generate_audio_parameter == "not_applicable", f"{context} {model_key} unsupported generateAudio parameter")
        require(prompt.get("rights_gate_status") == rights_gate.get("status"), f"{context} {model_key} prompt/rights conflict")
        if card.get("execution_verification_status") == "unverified":
            for field in ["access_mode", "execution_mode", "execution_verification_status"]:
                require(prompt.get(field) == card.get(field), f"{context} {model_key} {field} conflict")
        if card_has_source_conflict(card):
            require(prompt.get("source_conflicts"), f"{context} {model_key} official audio conflict was hidden")
        enabled_prompts[model_key] = prompt_card_id

    require(set(enabled_prompts) == set(selected_cards), f"{context} selected/enabled model set mismatch")
    require(set(routes) == set(selected_cards), f"{context} selected/audio-route model set mismatch")
    reference_items = data.get("reference_map", [])
    require(isinstance(reference_items, list) and reference_items, f"{context} reference map missing or malformed")
    reference_map = {item.get("ref_id"): item for item in reference_items}
    require(None not in reference_map and len(reference_map) == len(reference_items), f"{context} reference map has missing or duplicate ref_id")
    if visual_output_mode == "external_generation" and execution.get("external_upload_authorized") is False:
        for ref_id, item in reference_map.items():
            require(
                item.get("asset_output_status") in {"prompt_ready", "external_pending", "rejected"},
                f"{context} reference {ref_id} unauthorized external handoff can only remain instructions-only",
            )
    storyboard_clean_frame_valid = True
    for binding in data.get("reference_bindings", []):
        model_key = binding.get("model")
        require(model_key in enabled_prompts, f"{context} binding uses unresolved model family")
        ref_id = binding.get("ref_id")
        require(ref_id in reference_map, f"{context} binding references missing asset: {ref_id}")
        reference_role = str(reference_map[ref_id].get("role", ""))
        binding_role = binding.get("role")
        if any(token in reference_role for token in ["storyboard", "order_reference_only"]):
            require(binding_role == "planning_only" and binding.get("required_for_generation") is False, f"{context} storyboard/reference board must remain planning-only")
        if binding_role == "planning_only":
            require(binding.get("required_for_generation") is False, f"{context} planning-only binding cannot be required for generation")
        if binding_role == "primary_direct_input":
            require(reference_role in {"clean_first_frame", "clean_key_frame", "clean_end_frame"}, f"{context} primary direct input is not a clean frame")
        binding_selection = {
            "capability_card_id": binding.get("capability_card_id"),
            "version": binding.get("version"),
            "status": binding.get("status"),
            "provider_surface": binding.get("provider_surface"),
        }
        binding_card = resolve_exact_card(binding_selection, cards, f"{context} {model_key} binding", strict_receipt=False)
        require(binding_card["capability_card_id"] == enabled_prompts[model_key], f"{context} {model_key} binding/card conflict")

    official_conflicts_preserved = all(
        not card_has_source_conflict(card)
        or (
            next(selection for selection in resolution["selected_cards"] if selection.get("model_key") == model_key).get("source_conflicts")
            and data.get("model_prompts", {}).get(model_key, {}).get("source_conflicts")
        )
        for model_key, card in selected_cards.items()
    )
    expected_qa = {
        "exact_capability_cards_resolved": set(enabled_prompts) == set(selected_cards) == set(routes),
        "deprecated_or_preview_aliases_rejected": all(card.get("status") == "current" for card in selected_cards.values()),
        "rights_gate_passed": rights_gate_passed(rights_gate),
        "desired_audio_route_compatible": True,
        "preserve_change_disjoint": True,
        "storyboard_clean_frame_separation_valid": storyboard_clean_frame_valid,
        "official_source_conflicts_preserved": bool(official_conflicts_preserved),
    }
    validate_declared_boolean_qa(data.get("qa"), expected_qa, context)
    return len(enabled_prompts)


def validate_real_longform_manifest(path: Path, cards: dict[str, dict[str, Any]], registry: dict[str, Any]) -> int:
    data = load_yaml(path)
    pack = data.get("longform_reference_pack", {})
    context = str(path.relative_to(ROOT))
    require(pack.get("visual_output_mode") in {"prompt_only", "assisted_generation", "external_generation"}, f"{context} visual output mode missing")
    resolution = data.get("capability_resolution", {})
    require(resolution.get("registry_path") == str(REGISTRY_PATH.relative_to(ROOT)), f"{context} registry path mismatch")
    require(resolution.get("registry_version") == registry.get("version"), f"{context} registry version mismatch")
    selected: dict[str, dict[str, Any]] = {}
    for selection in resolution.get("selected_cards", []):
        card = resolve_exact_card(selection, cards, f"{context} selected card", strict_receipt=True)
        selected[card["capability_card_id"]] = card
    require(selected, f"{context} selected exact cards missing")
    validate_rights_gate(data.get("rights_gate", {}), f"{context} rights gate")
    serialized = json.dumps(data, ensure_ascii=False)
    forbidden = [term for term in ["model_targets", "max_image_refs", "max_video_refs", "max_audio_refs"] if term in serialized]
    require(not forbidden, f"{context} hard-coded model-family capability fields remain: {forbidden}")
    target_count = 0
    for sequence_pack in data.get("sequence_packs", []):
        sequence_id = sequence_pack.get("sequence_id", "unknown")
        targets = sequence_pack.get("capability_targets", [])
        require(targets, f"{context} {sequence_id} exact capability targets missing")
        target_ids: set[str] = set()
        for target in targets:
            require("model_family" not in target and "model_key" not in target, f"{context} {sequence_id} family alias target rejected")
            card_id = target.get("capability_card_id")
            require(card_id in selected and card_id not in target_ids, f"{context} {sequence_id} target card unresolved or duplicated")
            validate_transformation_contract(target.get("operation"), target.get("transformation_contract", {}), f"{context} {sequence_id} {card_id}")
            target_ids.add(card_id)
            target_count += 1
        for asset in sequence_pack.get("assets", []):
            policies = asset.get("direct_input_policy", [])
            require(isinstance(policies, list) and policies, f"{context} {sequence_id} asset direct-input policy must be exact-card list")
            policy_ids: set[str] = set()
            for policy in policies:
                card_id = policy.get("capability_card_id")
                require(card_id in target_ids and card_id not in policy_ids, f"{context} {sequence_id} asset policy card unresolved or duplicated")
                validate_asset_input_policy(
                    asset.get("role"),
                    policy.get("input_mode"),
                    selected[card_id],
                    f"{context} {sequence_id} {card_id}",
                )
                policy_ids.add(card_id)
            require(policy_ids == target_ids, f"{context} {sequence_id} asset policy does not cover exact targets")
    return target_count


def validate_real_manifests(cards: dict[str, dict[str, Any]], registry: dict[str, Any]) -> str:
    examples_root = ROOT / "examples"
    image_paths = sorted(examples_root.rglob(IMAGE_MANIFEST_GLOB))
    video_paths = sorted(examples_root.rglob(VIDEO_MANIFEST_GLOB))
    longform_paths = sorted(examples_root.rglob(LONGFORM_MANIFEST_GLOB))
    require(image_paths and video_paths and longform_paths, "real manifest discovery returned an empty class")
    image_items = sum(validate_real_image_manifest(path, cards, registry) for path in image_paths)
    video_targets = sum(validate_real_video_manifest(path, cards, registry) for path in video_paths)
    longform_targets = sum(validate_real_longform_manifest(path, cards, registry) for path in longform_paths)
    return (
        f"{len(image_paths)} image manifests/{image_items} images, "
        f"{len(video_paths)} video manifests/{video_targets} targets, "
        f"{len(longform_paths)} longform manifests/{longform_targets} targets validated"
    )


def validate_contract_fixture_case(case: dict[str, Any], cards: dict[str, dict[str, Any]]) -> None:
    validator = case.get("validator")
    payload = case.get("payload", {})
    if validator == "image_edit":
        card = cards.get(payload.get("capability_card_id"))
        require(card is not None and card.get("edit", {}).get("supported") is True, "fixture edit card unsupported")
        source_references = payload.get("source_references")
        validate_transformation_contract(
            "edit",
            payload.get("transformation_contract", {}),
            "fixture image edit",
            source_references=source_references,
        )
        evidence_refs = set(payload.get("rights", {}).get("evidence_refs", []))
        for reference in source_references:
            bound_rights = reference.get("rights_evidence_refs")
            require(isinstance(bound_rights, list) and bound_rights, "fixture edit source/reference rights evidence missing")
            require(set(bound_rights).issubset(evidence_refs), "fixture edit source/reference rights evidence is unbound")
        return
    if validator == "audio_route":
        selected_card_id = payload.get("selected_capability_card_id", payload.get("capability_card_id"))
        require(payload.get("capability_card_id") == selected_card_id, "fixture per-model audio card does not match selected model card")
        card = cards.get(payload.get("capability_card_id"))
        require(card is not None, "fixture audio card unresolved")
        validate_audio_route(card, payload.get("generation_audio_route"), payload.get("desired_audio"), payload.get("postproduction_handoff"), "fixture audio route")
        return
    if validator == "longform_target":
        require("model_family" not in payload and "model_key" not in payload, "fixture family alias rejected")
        require(payload.get("capability_card_id") in cards, "fixture exact capability card required")
        return
    if validator == "longform_asset_policy":
        card = cards.get(payload.get("capability_card_id"))
        require(card is not None, "fixture exact capability card required")
        validate_asset_input_policy(
            payload.get("asset_role"),
            payload.get("input_mode"),
            card,
            "fixture longform asset policy",
        )
        return
    if validator == "freshness":
        age_days = payload.get("age_days")
        stale_after_days = payload.get("stale_after_days")
        require(isinstance(age_days, int) and isinstance(stale_after_days, int), "fixture freshness inputs missing")
        observed = (date.today() - timedelta(days=age_days)).isoformat()
        require_fresh("fixture verified_on", observed, stale_after_days)
        return
    if validator in {"image_external_execution", "video_external_execution"}:
        validate_execution_capability(
            payload.get("visual_output_mode"),
            payload.get("execution", {}),
            payload.get("rights_gate", {}),
            f"fixture {validator}",
            external_instructions=payload.get("external_instructions"),
        )
        return
    if validator == "image_item":
        card = cards.get(payload.get("capability_card_id"))
        require(card is not None, "fixture image item card unresolved")
        validate_image_item(
            payload.get("image", {}),
            payload.get("manifest_rights", {}),
            card,
            "fixture image item",
            prompt=payload.get("prompt", "targeted prompt without fixed suffix"),
        )
        return
    if validator == "video_qa":
        expected = payload.get("computed")
        require(isinstance(expected, dict) and expected, "fixture video computed QA facts missing")
        require(all(isinstance(value, bool) for value in expected.values()), "fixture video computed QA facts must be booleans")
        validate_declared_boolean_qa(payload.get("qa"), expected, "fixture video QA")
        return
    raise AuditError(f"unknown contract fixture validator: {validator}")


def validate_contract_negative_fixtures(cards: dict[str, dict[str, Any]]) -> FixtureMetrics:
    paths = sorted((ROOT / "tests/fixtures").glob(CONTRACT_FIXTURE_GLOB))
    require(paths, "manifest contract negative fixtures missing")
    negative_count = 0
    positive_count = 0
    seen_ids: set[str] = set()
    for path in paths:
        fixture = load_yaml(path).get("contract_fixture", {})
        fixture_id = fixture.get("id")
        require(fixture_id and fixture_id not in seen_ids, f"{path.name} missing or duplicate contract fixture id")
        seen_ids.add(fixture_id)
        negatives = fixture.get("negative_cases")
        if negatives is None:
            negatives = [{"case": fixture.get("negative", {}), "expected_error_contains": fixture.get("expected_error_contains", "")}]
        positives = fixture.get("positive_controls")
        if positives is None:
            positives = [fixture.get("positive_control", {})]
        require(isinstance(negatives, list) and negatives, f"{path.name} contract negatives missing")
        require(isinstance(positives, list) and positives, f"{path.name} contract positive controls missing")
        for index, negative in enumerate(negatives, start=1):
            payload = negative.get("case", negative)
            expected = negative.get("expected_error_contains", fixture.get("expected_error_contains", ""))
            try:
                validate_contract_fixture_case({"validator": fixture.get("validator"), "payload": payload}, cards)
            except AuditError as exc:
                require(expected in str(exc), f"{path.name} negative {index} wrong rejection: {exc}")
                negative_count += 1
            else:
                raise AuditError(f"{path.name} negative {index} was not rejected")
        for index, positive in enumerate(positives, start=1):
            validate_contract_fixture_case({"validator": fixture.get("validator"), "payload": positive}, cards)
            positive_count += 1
    require(REQUIRED_CONTRACT_FIXTURE_IDS.issubset(seen_ids), f"required contract fixture coverage missing: {sorted(REQUIRED_CONTRACT_FIXTURE_IDS - seen_ids)}")
    return FixtureMetrics(
        detail=f"{negative_count} manifest contract negatives rejected; {positive_count} positive controls passed",
        negatives_rejected=negative_count,
        positive_controls_passed=positive_count,
    )


def main() -> int:
    checks: list[Check] = []
    cards_holder: dict[str, dict[str, Any]] = {}
    registry_holder: dict[str, Any] = {}
    fixture_metrics: list[FixtureMetrics] = []

    def registry_check() -> str:
        cards, registry, detail = validate_registry()
        cards_holder.update(cards)
        registry_holder.update(registry)
        return detail

    add_check(checks, "versioned capability registry", registry_check)
    if cards_holder:
        add_check(checks, "known provider invariants", lambda: validate_known_capabilities(cards_holder))
    else:
        checks.append(Check("known provider invariants", False, "registry unavailable"))
    add_check(checks, "prompt source tiers and optional QA macro", validate_prompt_sources)
    add_check(checks, "policy, schema, and subskill contracts", validate_contract_surfaces)
    if cards_holder:
        def fixture_check() -> str:
            metrics = validate_fixtures(cards_holder)
            fixture_metrics.append(metrics)
            return metrics.detail

        def contract_fixture_check() -> str:
            metrics = validate_contract_negative_fixtures(cards_holder)
            fixture_metrics.append(metrics)
            return metrics.detail

        add_check(checks, "E0-E6 positive and negative fixtures", fixture_check)
        add_check(checks, "manifest contract negative fixtures", contract_fixture_check)
        add_check(checks, "real image/video/longform manifests", lambda: validate_real_manifests(cards_holder, registry_holder))
    else:
        checks.append(Check("E0-E6 positive and negative fixtures", False, "registry unavailable"))
        checks.append(Check("manifest contract negative fixtures", False, "registry unavailable"))
        checks.append(Check("real image/video/longform manifests", False, "registry unavailable"))

    print("DIRcreative Model Capability Audit")
    print("=" * 72)
    for check in checks:
        marker = "PASS" if check.ok else "FAIL"
        print(f"[{marker}] {check.label}: {check.detail}")

    failed = [check for check in checks if not check.ok]
    if failed:
        print("MODEL_CAPABILITY_AUDIT: FAIL")
        return 1
    rejected = sum(metrics.negatives_rejected for metrics in fixture_metrics)
    positives = sum(metrics.positive_controls_passed for metrics in fixture_metrics)
    print(f"negative_fixtures_rejected: {rejected}/{rejected}")
    print(f"positive_controls_passed: {positives}/{positives}")
    print("MODEL_CAPABILITY_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
