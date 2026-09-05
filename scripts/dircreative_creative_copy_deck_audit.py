#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dircreative_validation_harness import ROOT, Check, add_check, read, require_terms


SCHEMA_PATHS = [
    "docs/film-preproduction/schemas/project.yaml",
    "docs/film-preproduction/schemas/story-package.yaml",
    "docs/film-preproduction/schemas/deck-narrative-spec.yaml",
]

FIXTURE_PATHS = [
    "tests/fixtures/invalid-creative-copy-deck-missing-source-tension.yaml",
    "tests/fixtures/invalid-creative-copy-deck-foundation-cross-bindings.yaml",
    "tests/fixtures/invalid-creative-copy-deck-story-deck-cross-bindings.yaml",
    "tests/fixtures/invalid-creative-copy-deck-source-sample-provenance.yaml",
    "tests/fixtures/invalid-creative-copy-deck-voice-profile-coverage.yaml",
    "tests/fixtures/invalid-creative-copy-deck-substitutable-concept.yaml",
    "tests/fixtures/invalid-creative-copy-deck-self-reviewed-concept.yaml",
    "tests/fixtures/invalid-creative-copy-deck-missing-voice-profile.yaml",
    "tests/fixtures/invalid-creative-copy-deck-unapproved-claim.yaml",
    "tests/fixtures/invalid-creative-copy-deck-copy-status.yaml",
    "tests/fixtures/invalid-creative-copy-deck-ai-trace-cluster-review-only.yaml",
    "tests/fixtures/invalid-creative-copy-deck-ai-trace-metadata.yaml",
    "tests/fixtures/invalid-creative-copy-deck-ai-trace-authority.yaml",
    "tests/fixtures/invalid-creative-copy-deck-manual-craft-evidence-gap.yaml",
    "tests/fixtures/invalid-creative-copy-deck-story-arc.yaml",
    "tests/fixtures/invalid-creative-copy-deck-claim-evidence-qa.yaml",
    "tests/fixtures/invalid-creative-copy-deck-audience-copy-boundary.yaml",
    "tests/fixtures/invalid-creative-copy-deck-layout.yaml",
    "tests/fixtures/invalid-creative-copy-deck-presentations-not-editable.yaml",
    "tests/fixtures/invalid-creative-copy-deck-editability.yaml",
    "tests/fixtures/invalid-creative-copy-deck-high-end-authority.yaml",
]

VOICE_PROFILE_FIELDS = [
    "author",
    "goal",
    "confidence",
    "source_sample_ids",
    "rhythm",
    "compression",
    "capitalization",
    "parentheticals",
    "question_use",
    "claim_style",
    "preferred_moves",
    "banned_moves",
    "cta_rules",
    "channel_notes",
]

SOURCE_SAMPLE_FIELDS = [
    "sample_id",
    "source_ref",
    "excerpt",
    "why_representative",
    "recency",
]

COPY_STATUS_FIELDS = [
    "voice_profile_status",
    "dir_professional_judgment_status",
    "de_ai_fidelity_status",
    "manual_craft_status",
    "humanizer_review_status",
]

AI_TRACE_PATTERNS = {
    "road_sign_cluster": [
        r"此外",
        r"值得注意(?:的是)?",
        r"总之",
        r"换句话说",
        r"与此同时",
    ],
    "binary_contrast_cluster": [
        r"不是.{1,40}而是",
        r"不仅.{1,40}(?:而且|更是|还)",
        r"不在于.{1,40}而在于",
    ],
    "analysis_posture_cluster": [
        r"拆一拆",
        r"盘一盘",
        r"捋一捋",
        r"简单来说",
        r"本质上",
    ],
    "inflated_significance_cluster": [
        r"标志着",
        r"彰显",
        r"至关重要",
        r"深刻",
        r"充满活力",
    ],
}


@dataclass(frozen=True)
class Finding:
    finding_id: str
    severity: str
    detail: str


def load_yaml(path: str) -> dict[str, Any]:
    target = ROOT / path
    ruby = (
        "require 'yaml'; require 'json'; "
        "data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: false); "
        "puts JSON.generate(data)"
    )
    proc = subprocess.run(
        ["ruby", "-e", ruby, str(target)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"YAML parse failed for {path}: {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    if not isinstance(data, dict):
        raise AssertionError(f"{path} must contain a YAML mapping")
    return data


def present(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return value is not None


def add_finding(findings: list[Finding], finding_id: str, severity: str, detail: str) -> None:
    if any(item.finding_id == finding_id for item in findings):
        return
    findings.append(Finding(finding_id, severity, detail))


def detect_ai_trace_clusters(text: str) -> list[str]:
    matched_categories: list[str] = []
    total_hits = 0
    for category, patterns in AI_TRACE_PATTERNS.items():
        hits = sum(1 for pattern in patterns if re.search(pattern, text))
        if hits:
            matched_categories.append(category)
            total_hits += hits
    if total_hits < 2:
        return []
    return matched_categories


def mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def valid_string_list(value: Any, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, list) or (not allow_empty and not value):
        return False
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return False
        normalized.append(item.strip())
    return len(normalized) == len(set(normalized))


def record_index(
    value: Any,
    id_field: str,
    required_fields: list[str],
    *,
    minimum: int = 1,
) -> dict[str, dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) < minimum:
        return None
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            return None
        identifier = item.get(id_field)
        if (
            not isinstance(identifier, str)
            or not identifier.strip()
            or identifier != identifier.strip()
            or identifier in result
        ):
            return None
        if any(field not in item or not present(item.get(field)) for field in required_fields):
            return None
        result[identifier] = item
    return result


def references_resolve(value: Any, allowed_ids: set[str], *, allow_empty: bool = False) -> bool:
    return valid_string_list(value, allow_empty=allow_empty) and set(value).issubset(allowed_ids)


def validate_creative_and_copy(bundle: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    project = mapping(bundle.get("project"))
    story = mapping(bundle.get("story_package"))

    foundation = mapping(project.get("creative_foundation"))
    evidence = foundation.get("source_evidence")
    evidence_index = record_index(
        evidence,
        "evidence_id",
        ["evidence_id", "source_type", "locator", "summary", "verification_status"],
    )
    evidence_ok = evidence_index is not None and all(
        item.get("verification_status") in {"verified", "unverified"}
        for item in evidence_index.values()
    )
    evidence_ids = set(evidence_index or {})
    verified_evidence_ids = {
        evidence_id
        for evidence_id, item in (evidence_index or {}).items()
        if item.get("verification_status") == "verified"
    }
    if not evidence_ok:
        add_finding(
            findings,
            "creative_source_evidence_missing",
            "blocker",
            "source_evidence must be a non-empty mapping array with unique IDs and complete provenance",
        )

    facts = foundation.get("facts")
    fact_index = record_index(facts, "fact_id", ["fact_id", "statement", "source_evidence_ids"])
    facts_ok = fact_index is not None and evidence_ok and all(
        references_resolve(item.get("source_evidence_ids"), evidence_ids)
        for item in fact_index.values()
    )
    fact_ids = set(fact_index or {})
    if not facts_ok:
        add_finding(
            findings,
            "creative_fact_source_binding_missing",
            "blocker",
            "facts must be unique-ID records whose source_evidence_ids resolve",
        )

    inferences = foundation.get("inferences")
    inference_index = record_index(
        inferences,
        "inference_id",
        ["inference_id", "statement", "based_on_fact_ids", "confidence", "audience_facing_policy"],
    )
    inferences_ok = inference_index is not None and facts_ok and all(
        references_resolve(item.get("based_on_fact_ids"), fact_ids)
        and item.get("confidence") in {"low", "medium", "high"}
        and item.get("audience_facing_policy") in {"label_as_inference", "internal_only"}
        for item in inference_index.values()
    )
    inference_ids = set(inference_index or {})
    if not inferences_ok:
        add_finding(
            findings,
            "creative_inference_binding_missing",
            "blocker",
            "inferences must have unique IDs, resolving fact IDs, confidence, and a disclosure policy",
        )

    strategy = mapping(project.get("commercial_strategy"))
    tension = mapping(strategy.get("audience_tension"))
    tension_present = all(
        present(tension.get(field))
        for field in ["audience_state", "felt_pressure", "desired_change", "evidence_ids"]
    )
    tension_binding_ok = tension_present and evidence_ok and references_resolve(
        tension.get("evidence_ids"), evidence_ids
    )
    if not tension_present:
        add_finding(
            findings,
            "creative_audience_tension_missing",
            "blocker",
            "audience state, felt pressure, desired change, and evidence are required",
        )
    elif not tension_binding_ok:
        add_finding(
            findings,
            "creative_audience_tension_source_binding_invalid",
            "blocker",
            "audience tension evidence IDs must resolve to project source evidence",
        )

    objective = mapping(strategy.get("business_objective"))
    if not all(
        present(objective.get(field))
        for field in ["objective_type", "intended_result", "measurement_signal"]
    ):
        add_finding(
            findings,
            "creative_business_objective_missing",
            "blocker",
            "business objective and measurement signal are required",
        )

    proposition = mapping(strategy.get("single_minded_proposition"))
    proposition_present = all(
        present(proposition.get(field))
        for field in ["statement", "support_fact_ids", "audience_relevance"]
    )
    proposition_binding_ok = proposition_present and facts_ok and references_resolve(
        proposition.get("support_fact_ids"), fact_ids
    )
    if not proposition_present:
        add_finding(
            findings,
            "creative_single_minded_proposition_missing",
            "blocker",
            "single-minded proposition must be audience-relevant and fact-supported",
        )
    elif not proposition_binding_ok:
        add_finding(
            findings,
            "creative_single_minded_proposition_binding_invalid",
            "blocker",
            "single-minded proposition support_fact_ids must resolve",
        )
    if not valid_string_list(strategy.get("avoid_cliches")):
        add_finding(
            findings,
            "creative_avoid_cliches_missing",
            "blocker",
            "category and story cliches must be named before concept approval",
        )

    source_bindings = mapping(story.get("source_bindings"))
    story_fact_ids = source_bindings.get("fact_ids")
    story_evidence_ids = source_bindings.get("source_evidence_ids")
    story_inference_ids = source_bindings.get("inference_ids")
    story_bindings_ok = (
        facts_ok
        and evidence_ok
        and inferences_ok
        and references_resolve(story_fact_ids, fact_ids)
        and references_resolve(story_evidence_ids, evidence_ids)
        and references_resolve(story_inference_ids, inference_ids)
        and (not tension_binding_ok or set(tension.get("evidence_ids", [])).issubset(set(story_evidence_ids)))
        and (
            not proposition_binding_ok
            or set(proposition.get("support_fact_ids", [])).issubset(set(story_fact_ids))
        )
    )
    if not story_bindings_ok:
        add_finding(
            findings,
            "creative_story_source_binding_invalid",
            "blocker",
            "story source bindings must resolve and preserve tension, proposition, and inference sources",
        )

    story_outline = mapping(story.get("outline"))
    story_beat_index = record_index(
        story_outline.get("beats"),
        "beat_id",
        [
            "beat_id",
            "title",
            "story_function",
            "visible_action",
            "emotional_shift",
            "duration_estimate",
            "source_fact_ids",
            "source_inference_ids",
        ],
    )
    story_beats_ok = story_beat_index is not None and story_bindings_ok and all(
        references_resolve(beat.get("source_fact_ids"), set(story_fact_ids))
        and references_resolve(beat.get("source_inference_ids"), set(story_inference_ids))
        for beat in story_beat_index.values()
    )
    if not story_beats_ok:
        add_finding(
            findings,
            "creative_story_beat_source_binding_invalid",
            "blocker",
            "story beats must have unique IDs and resolve fact/inference sources through story bindings",
        )

    concept = mapping(story.get("concept"))
    concept_author_id = concept.get("concept_author_id")
    dependency_index = record_index(
        concept.get("specific_dependencies"),
        "dependency_id",
        ["dependency_id", "description"],
        minimum=2,
    )
    dependency_ids = set(dependency_index or {})
    swap = mapping(concept.get("substitutability_check"))
    alternative_index = record_index(
        swap.get("alternatives"),
        "alternative_id",
        ["alternative_id", "subject", "proximity_reason"],
        minimum=2,
    )
    selected_alternative_id = swap.get("selected_alternative_id")
    selected_alternative = (alternative_index or {}).get(selected_alternative_id, {})
    reviewer = mapping(swap.get("independent_reviewer"))
    broken_dependency_ids = swap.get("broken_dependency_ids")
    substitutability_ok = (
        dependency_index is not None
        and alternative_index is not None
        and present(selected_alternative_id)
        and selected_alternative.get("subject") == swap.get("swap_subject")
        and present(swap.get("before_swap"))
        and present(swap.get("after_swap"))
        and swap.get("before_swap") != swap.get("after_swap")
        and swap.get("still_works_without_rewrite") is False
        and references_resolve(broken_dependency_ids, dependency_ids)
        and len(broken_dependency_ids) >= 2
        and swap.get("verdict") == "distinctive"
        and isinstance(concept_author_id, str)
        and bool(concept_author_id.strip())
        and all(present(reviewer.get(field)) for field in ["reviewer_id", "reviewer_role", "review_status"])
        and reviewer.get("reviewer_id") != concept_author_id
        and reviewer.get("independent_from_concept_author") is True
        and reviewer.get("review_status") == "pass"
    )
    if not substitutability_ok:
        add_finding(
            findings,
            "creative_concept_substitutable",
            "blocker",
            "alternatives, before/after swap, broken dependency IDs, and an independent reviewer are required",
        )

    copy_development = mapping(project.get("copy_development"))
    samples = copy_development.get("source_samples")
    sample_index = record_index(samples, "sample_id", SOURCE_SAMPLE_FIELDS)
    sample_ids = set(sample_index or {})
    samples_ok = (
        sample_index is not None
        and len(sample_index) <= 20
        and (len(sample_index) >= 5 or present(copy_development.get("sample_shortfall_reason")))
    )
    if not samples_ok:
        add_finding(
            findings,
            "copy_source_samples_missing",
            "blocker",
            "source samples require unique IDs, complete provenance fields, and a shortfall reason below five",
        )

    profile = mapping(copy_development.get("voice_profile"))
    profile_complete = all(present(profile.get(field)) for field in VOICE_PROFILE_FIELDS)
    profile_source_sample_ids = profile.get("source_sample_ids")
    profile_sample_ids = set(profile_source_sample_ids) if valid_string_list(profile_source_sample_ids) else set()
    profile_binding_ok = (
        profile_complete
        and valid_string_list(profile.get("preferred_moves"))
        and valid_string_list(profile.get("banned_moves"))
        and isinstance(profile.get("channel_notes"), dict)
        and bool(profile.get("channel_notes"))
        and profile.get("confidence") in {"low", "medium", "high"}
        and samples_ok
        and profile_sample_ids.issubset(sample_ids)
        and (
            profile_sample_ids == sample_ids
            or present(profile.get("coverage_shortfall_reason"))
        )
        and not (
            len(sample_ids) < 5
            and profile.get("confidence") == "high"
        )
    )
    if not profile_binding_ok:
        add_finding(
            findings,
            "copy_voice_profile_missing",
            "blocker",
            "one VOICE PROFILE mapping must cover unique source samples or record a coverage shortfall",
        )

    claims = copy_development.get("claims")
    claim_index = record_index(claims, "claim_id", ["claim_id", "text", "approval_status", "evidence_ids"])
    claims_ok = claim_index is not None and evidence_ok and all(
        item.get("approval_status") in {"approved", "pending", "rejected", "unreviewed"}
        and references_resolve(item.get("evidence_ids"), evidence_ids)
        and (
            item.get("approval_status") != "approved"
            or set(item.get("evidence_ids", [])).issubset(verified_evidence_ids)
        )
        for item in claim_index.values()
    )
    approved_claim_ids = {
        claim_id
        for claim_id, item in (claim_index or {}).items()
        if item.get("approval_status") == "approved"
    }
    if not claims_ok:
        add_finding(
            findings,
            "copy_claim_register_invalid",
            "blocker",
            "claims must have unique IDs, valid statuses, and resolving verified evidence",
        )

    judgment = mapping(copy_development.get("dir_professional_judgment"))
    judgment_present = all(
        present(judgment.get(field))
        for field in ["audience_effect", "channel_fit", "factual_boundaries", "tradeoff", "approved_claim_ids"]
    )
    judgment_ok = (
        claims_ok
        and judgment_present
        and valid_string_list(judgment.get("factual_boundaries"))
        and references_resolve(judgment.get("approved_claim_ids"), approved_claim_ids)
    )
    if not judgment_ok:
        add_finding(
            findings,
            "copy_dir_professional_judgment_missing",
            "blocker",
            "voice matching cannot replace DIR audience and production judgment",
        )

    de_ai = mapping(copy_development.get("de_ai_refinement"))
    de_ai_ok = (
        de_ai.get("fidelity_status") == "pass"
        and valid_string_list(de_ai.get("protected_meaning_points"))
        and de_ai.get("factual_additions") == []
        and de_ai.get("new_claims_added") is False
    )
    if not de_ai_ok:
        add_finding(
            findings,
            "copy_de_ai_fidelity_missing",
            "blocker",
            "de-AI refinement must preserve meaning and add no facts or claims",
        )

    copy_execution = mapping(story.get("copy_execution"))
    audience_text = copy_execution.get("audience_facing_text")
    if not present(audience_text):
        add_finding(
            findings,
            "copy_audience_text_missing",
            "blocker",
            "audience-facing copy must be non-empty",
        )

    used_claim_ids = copy_execution.get("claim_ids_used")
    used_claims_ok = (
        claims_ok
        and references_resolve(used_claim_ids, approved_claim_ids)
        and set(used_claim_ids).issubset(set(judgment.get("approved_claim_ids", [])))
    )
    if not used_claims_ok:
        add_finding(
            findings,
            "copy_unapproved_claim",
            "blocker",
            "audience-facing copy may use only evidence-bound approved claims",
        )

    used_evidence_ids = copy_execution.get("evidence_ids_used")
    claim_evidence_ids = {
        evidence_id
        for claim_id in (used_claim_ids if isinstance(used_claim_ids, list) else [])
        for evidence_id in mapping((claim_index or {}).get(claim_id)).get("evidence_ids", [])
    }
    execution_source_binding_ok = (
        story_bindings_ok
        and references_resolve(used_evidence_ids, evidence_ids)
        and claim_evidence_ids.issubset(set(used_evidence_ids))
        and set(used_evidence_ids).issubset(set(story_evidence_ids))
    )
    if not execution_source_binding_ok:
        add_finding(
            findings,
            "copy_execution_source_binding_invalid",
            "blocker",
            "copy evidence must cover used claims and resolve through story source bindings",
        )

    manual_craft = mapping(copy_development.get("manual_craft_review"))
    manual_craft_present = all(
        present(manual_craft.get(field))
        for field in ["reviewer_role", "status", "rhythm_assessment", "abstraction_assessment", "evidence_alignment"]
    ) and valid_string_list(manual_craft.get("reviewed_ai_trace_clusters"), allow_empty=True)
    if not manual_craft_present or manual_craft.get("status") not in {
        "pass",
        "review_required",
        "needs_revision",
    }:
        add_finding(
            findings,
            "copy_manual_craft_review_incomplete",
            "blocker",
            "manual craft review must record rhythm, abstraction, evidence alignment, and reviewer role",
        )
    elif manual_craft.get("status") == "needs_revision" or manual_craft.get("evidence_alignment") != "pass":
        add_finding(
            findings,
            "copy_manual_craft_review_failed",
            "blocker",
            "manual craft review found rhythm, abstraction, or evidence-alignment defects",
        )

    diagnostic = mapping(copy_development.get("humanizer_diagnostic"))
    diagnostic_authority_ok = (
        set(diagnostic)
        == {"authority", "trace_clusters", "manual_review_required", "may_fail_copy_by_itself"}
        and diagnostic.get("authority") == "diagnostic_only"
        and diagnostic.get("may_fail_copy_by_itself") is False
    )
    if not diagnostic_authority_ok:
        add_finding(
            findings,
            "copy_humanizer_authority_invalid",
            "blocker",
            "humanizer must remain diagnostic-only and cannot fail copy by itself",
        )

    trace_clusters = detect_ai_trace_clusters(audience_text if isinstance(audience_text, str) else "")
    expected_trace_status = "review_required" if trace_clusters else "pass"
    trace_metadata_ok = (
        diagnostic_authority_ok
        and valid_string_list(diagnostic.get("trace_clusters"), allow_empty=True)
        and set(diagnostic.get("trace_clusters", [])) == set(trace_clusters)
        and diagnostic.get("manual_review_required") is bool(trace_clusters)
        and manual_craft_present
        and set(manual_craft.get("reviewed_ai_trace_clusters", [])) == set(trace_clusters)
        and valid_string_list(copy_execution.get("ai_trace_clusters"), allow_empty=True)
        and set(copy_execution.get("ai_trace_clusters", [])) == set(trace_clusters)
        and copy_execution.get("humanizer_review_status") == expected_trace_status
        and (
            (trace_clusters and manual_craft.get("status") == "review_required")
            or (not trace_clusters and manual_craft.get("status") in {"pass", "needs_revision"})
        )
    )
    if not trace_metadata_ok:
        add_finding(
            findings,
            "copy_ai_trace_metadata_inconsistent",
            "blocker",
            "detected clusters, diagnostic state, manual craft review, and copy_execution must agree",
        )
    if trace_clusters:
        add_finding(
            findings,
            "copy_ai_trace_cluster_review",
            "review",
            "contextual review required for: " + ", ".join(trace_clusters),
        )

    status_values_present = all(field in copy_execution for field in COPY_STATUS_FIELDS)
    status_consistent = (
        status_values_present
        and copy_execution.get("voice_profile_status") in {"pending", "blocked", "pass"}
        and copy_execution.get("dir_professional_judgment_status") in {"pending", "blocked", "pass"}
        and copy_execution.get("de_ai_fidelity_status") in {"pending", "blocked", "pass"}
        and copy_execution.get("manual_craft_status") in {"pending", "pass", "review_required", "needs_revision"}
        and copy_execution.get("humanizer_review_status") in {"not_run", "pass", "review_required"}
        and (
            (profile_binding_ok and copy_execution.get("voice_profile_status") == "pass")
            or (not profile_binding_ok and copy_execution.get("voice_profile_status") != "pass")
        )
        and (
            (judgment_ok and copy_execution.get("dir_professional_judgment_status") == "pass")
            or (not judgment_ok and copy_execution.get("dir_professional_judgment_status") != "pass")
        )
        and (
            (de_ai_ok and copy_execution.get("de_ai_fidelity_status") == "pass")
            or (not de_ai_ok and copy_execution.get("de_ai_fidelity_status") != "pass")
        )
        and (
            (not manual_craft_present and copy_execution.get("manual_craft_status") != "pass")
            or (
                manual_craft_present
                and copy_execution.get("manual_craft_status") == manual_craft.get("status")
            )
        )
        and copy_execution.get("humanizer_review_status") == expected_trace_status
    )
    if not status_consistent:
        add_finding(
            findings,
            "copy_execution_status_inconsistent",
            "blocker",
            "copy execution statuses must match the validated copy pipeline state",
        )

    return findings


def validate_deck(bundle: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    project = mapping(bundle.get("project"))
    story = mapping(bundle.get("story_package"))
    foundation = mapping(project.get("creative_foundation"))
    copy_development = mapping(project.get("copy_development"))
    deck = mapping(bundle.get("deck_narrative_spec"))

    evidence_index = record_index(
        foundation.get("source_evidence"),
        "evidence_id",
        ["evidence_id", "source_type", "locator", "summary", "verification_status"],
    )
    fact_index = record_index(
        foundation.get("facts"),
        "fact_id",
        ["fact_id", "statement", "source_evidence_ids"],
    )
    inference_index = record_index(
        foundation.get("inferences"),
        "inference_id",
        ["inference_id", "statement", "based_on_fact_ids", "confidence", "audience_facing_policy"],
    )
    claim_index = record_index(
        copy_development.get("claims"),
        "claim_id",
        ["claim_id", "text", "approval_status", "evidence_ids"],
    )
    evidence_ids = set(evidence_index or {})
    fact_ids = set(fact_index or {})
    inference_ids = set(inference_index or {})
    approved_claim_ids = {
        claim_id
        for claim_id, item in (claim_index or {}).items()
        if item.get("approval_status") == "approved"
    }

    communication_job = mapping(deck.get("communication_job"))
    communication_ok = all(
        present(communication_job.get(field))
        for field in ["audience", "deck_job", "audience_outcome", "central_takeaway"]
    )
    if not communication_ok:
        add_finding(
            findings,
            "deck_communication_job_missing",
            "blocker",
            "deck audience, job, outcome, and central takeaway are required",
        )

    source_constraints = mapping(deck.get("source_constraints"))
    story_bindings = mapping(story.get("source_bindings"))
    story_fact_ids = story_bindings.get("fact_ids")
    story_evidence_ids = story_bindings.get("source_evidence_ids")
    story_inference_ids = story_bindings.get("inference_ids")
    source_constraints_ok = (
        evidence_index is not None
        and fact_index is not None
        and inference_index is not None
        and claim_index is not None
        and references_resolve(source_constraints.get("fact_ids"), fact_ids)
        and references_resolve(source_constraints.get("source_evidence_ids"), evidence_ids)
        and references_resolve(source_constraints.get("inference_ids"), inference_ids)
        and references_resolve(source_constraints.get("approved_claim_ids"), approved_claim_ids)
        and source_constraints.get("inference_disclosure_policy") in {"label_as_inference", "internal_only"}
        and valid_string_list(story_fact_ids)
        and valid_string_list(story_evidence_ids)
        and valid_string_list(story_inference_ids)
        and set(source_constraints.get("fact_ids", [])).issubset(set(story_fact_ids))
        and set(source_constraints.get("source_evidence_ids", [])).issubset(
            set(story_evidence_ids)
        )
        and set(source_constraints.get("inference_ids", [])).issubset(set(story_inference_ids))
    )
    if not source_constraints_ok:
        add_finding(
            findings,
            "deck_source_constraints_invalid",
            "blocker",
            "deck source constraints must resolve through project and story source bindings",
        )

    arc = mapping(deck.get("story_arc"))
    beats = arc.get("beats")
    required_beat_fields = [
        "beat_id",
        "audience_question",
        "narrative_job",
        "primary_claim_id",
        "primary_claim",
        "evidence_ids",
        "audience_shift",
        "transition_to_next",
    ]
    beat_index = record_index(beats, "beat_id", required_beat_fields, minimum=3)
    arc_ok = (
        beat_index is not None
        and present(arc.get("arc_type"))
        and present(arc.get("opening_tension"))
        and present(arc.get("closing_resolution"))
    )
    if not arc_ok:
        add_finding(
            findings,
            "deck_story_arc_incomplete",
            "blocker",
            "opening tension, three cumulative beats, and closing resolution are required",
        )

    deck_claim_ids = set(source_constraints.get("approved_claim_ids", [])) if source_constraints_ok else set()
    deck_evidence_ids = set(source_constraints.get("source_evidence_ids", [])) if source_constraints_ok else set()
    beat_claim_binding_ok = beat_index is not None and all(
        beat.get("primary_claim_id") in deck_claim_ids
        and mapping((claim_index or {}).get(beat.get("primary_claim_id"))).get("text") == beat.get("primary_claim")
        and references_resolve(beat.get("evidence_ids"), deck_evidence_ids)
        and set(mapping((claim_index or {}).get(beat.get("primary_claim_id"))).get("evidence_ids", [])).issubset(
            set(beat.get("evidence_ids", []))
        )
        for beat in beat_index.values()
    )
    if not beat_claim_binding_ok:
        add_finding(
            findings,
            "deck_beat_claim_evidence_binding_invalid",
            "blocker",
            "each beat claim ID and evidence must resolve through approved deck sources",
        )

    slides = deck.get("slides")
    required_slide_fields = [
        "slide_id",
        "beat_id",
        "narrative_job",
        "takeaway_title",
        "primary_claim_id",
        "primary_claim",
        "evidence_ids",
        "layout",
    ]
    slide_index = record_index(slides, "slide_id", required_slide_fields)
    if slide_index is None:
        add_finding(
            findings,
            "deck_slide_collection_invalid",
            "blocker",
            "slides must be a non-empty mapping array with unique IDs and complete required fields",
        )
    slide_arc_binding_ok = (
        slide_index is not None
        and beat_index is not None
        and set(beat_index) == {slide.get("beat_id") for slide in slide_index.values()}
        and all(
            slide.get("beat_id") in beat_index
            and slide.get("narrative_job") == beat_index[slide.get("beat_id")].get("narrative_job")
            for slide in slide_index.values()
        )
    )
    if not slide_arc_binding_ok:
        add_finding(
            findings,
            "deck_story_arc_incomplete",
            "blocker",
            "every story beat must map to at least one slide and no slide may float outside the arc",
        )

    layout_fields = ["layout_family", "composition", "primary_visual_role", "text_density"]
    layout_ok = slide_index is not None and all(
        all(present(mapping(slide.get("layout")).get(field)) for field in layout_fields)
        and mapping(slide.get("layout")).get("text_density") in {"low", "medium"}
        and mapping(slide.get("layout")).get("title_max_lines") in {1, 2}
        and mapping(slide.get("layout")).get("avoid_ui_panels") is True
        for slide in slide_index.values()
    )
    if not layout_ok:
        add_finding(
            findings,
            "deck_layout_spec_incomplete",
            "blocker",
            "each slide requires a readable composition, visual role, density budget, and non-dashboard default",
        )

    slide_claim_binding_ok = slide_index is not None and beat_index is not None and all(
        slide.get("primary_claim_id") in deck_claim_ids
        and slide.get("beat_id") in beat_index
        and slide.get("primary_claim_id") == beat_index[slide.get("beat_id")].get("primary_claim_id")
        and mapping((claim_index or {}).get(slide.get("primary_claim_id"))).get("text") == slide.get("primary_claim")
        and references_resolve(slide.get("evidence_ids"), deck_evidence_ids)
        and set(mapping((claim_index or {}).get(slide.get("primary_claim_id"))).get("evidence_ids", [])).issubset(
            set(slide.get("evidence_ids", []))
        )
        for slide in slide_index.values()
    )
    if not slide_claim_binding_ok:
        add_finding(
            findings,
            "deck_slide_claim_evidence_binding_invalid",
            "blocker",
            "slide claim IDs, beat IDs, claim text, and evidence must resolve without text fallback",
        )

    route = mapping(deck.get("delivery_route"))
    codex_ppt = mapping(route.get("codex_ppt"))
    presentations_route_ok = (
        route.get("default_route") == "Presentations"
        and route.get("selected_route") in {"Presentations", "codex-ppt"}
        and codex_ppt.get("allowed_only_with_non_editable_acceptance") is True
        and codex_ppt.get("output_editability") == "full_slide_image_only"
        and (
            route.get("selected_route") != "Presentations"
            or (
                route.get("editable_ppt_required") is True
                and route.get("element_level_editability") == "required"
            )
        )
    )
    if not presentations_route_ok:
        add_finding(
            findings,
            "deck_editability_route_invalid",
            "blocker",
            "editable decks default to Presentations with element-level editability",
        )

    codex_ppt_route_ok = route.get("selected_route") != "codex-ppt" or (
        codex_ppt.get("user_accepted_full_slide_images") is True
        and route.get("editable_ppt_required") is False
        and route.get("element_level_editability") == "not_available"
    )
    if not codex_ppt_route_ok:
        add_finding(
            findings,
            "deck_noneditable_route_without_consent",
            "blocker",
            "codex-ppt requires explicit acceptance of full-slide image editability limits",
        )

    high_end = mapping(route.get("high_end_visual_design"))
    high_end_ok = (
        set(high_end) == {"allowed_role", "presentation_rule_authority"}
        and high_end.get("allowed_role") == "aesthetic_reference_only"
        and high_end.get("presentation_rule_authority") is False
    )
    if not high_end_ok:
        add_finding(
            findings,
            "deck_presentation_authority_invalid",
            "blocker",
            "high-end-visual-design cannot define PPT construction or QA rules",
        )

    qa = mapping(deck.get("qa"))
    allowed_slide_fields = {
        "slide_id",
        "beat_id",
        "narrative_job",
        "takeaway_title",
        "primary_claim_id",
        "primary_claim",
        "evidence_ids",
        "layout",
    }
    audience_copy_only = slide_index is not None and all(
        set(slide).issubset(allowed_slide_fields) for slide in slide_index.values()
    )
    if not audience_copy_only:
        add_finding(
            findings,
            "deck_audience_copy_boundary_invalid",
            "blocker",
            "slides may contain only audience-facing narrative fields and layout metadata",
        )
    claim_traceable = beat_claim_binding_ok and slide_claim_binding_ok
    evidence_traceable = source_constraints_ok and claim_traceable
    route_ok = presentations_route_ok and codex_ppt_route_ok and high_end_ok
    qa_expected = {
        "story_arc_complete": arc_ok and slide_arc_binding_ok,
        "one_narrative_job_per_slide": slide_arc_binding_ok,
        "claims_traceable": claim_traceable,
        "evidence_traceable": evidence_traceable,
        "layout_readable": layout_ok,
        "audience_facing_copy_only": audience_copy_only,
        "editability_route_valid": route_ok,
    }
    if any(qa.get(field) is not expected for field, expected in qa_expected.items()):
        add_finding(
            findings,
            "deck_qa_status_invalid",
            "blocker",
            "deck QA booleans must be complete and match computed arc, claim, evidence, layout, and route results",
        )

    return findings


def validate_bundle(bundle: dict[str, Any]) -> list[Finding]:
    return validate_creative_and_copy(bundle) + validate_deck(bundle)


def valid_reference_bundle() -> dict[str, Any]:
    samples = [
        {
            "sample_id": f"sample-{index}",
            "source_ref": f"approved-copy-{index}",
            "excerpt": f"Approved source excerpt {index}.",
            "why_representative": "Shows the approved direct, evidence-led voice.",
            "recency": "recent",
        }
        for index in range(1, 6)
    ]
    return {
        "project": {
            "creative_foundation": {
                "facts": [
                    {
                        "fact_id": "fact-01",
                        "statement": "The product proof is visible during normal use.",
                        "source_evidence_ids": ["evidence-01"],
                    }
                ],
                "source_evidence": [
                    {
                        "evidence_id": "evidence-01",
                        "source_type": "approved_client_brief",
                        "locator": "brief.pdf#page=4",
                        "summary": "Approved functional proof and audience occasion.",
                        "verification_status": "verified",
                    }
                ],
                "inferences": [
                    {
                        "inference_id": "inference-01",
                        "statement": "The proof should resolve hesitation before the packshot.",
                        "based_on_fact_ids": ["fact-01"],
                        "confidence": "medium",
                        "audience_facing_policy": "label_as_inference",
                    }
                ],
            },
            "commercial_strategy": {
                "audience_tension": {
                    "audience_state": "Interested but skeptical category buyer.",
                    "felt_pressure": "The promise sounds interchangeable with competitors.",
                    "desired_change": "Trust the visible proof enough to consider purchase.",
                    "evidence_ids": ["evidence-01"],
                },
                "business_objective": {
                    "objective_type": "consideration",
                    "intended_result": "Increase qualified product consideration.",
                    "measurement_signal": "Proof-beat recall in concept testing.",
                },
                "single_minded_proposition": {
                    "statement": "The benefit proves itself in the audience's real occasion.",
                    "support_fact_ids": ["fact-01"],
                    "audience_relevance": "It replaces a generic promise with visible evidence.",
                },
                "avoid_cliches": [
                    "generic lifestyle montage",
                    "unsupported premium claim",
                ],
            },
            "copy_development": {
                "source_samples": samples,
                "sample_shortfall_reason": "",
                "voice_profile": {
                    "author": "Approved brand voice",
                    "goal": "Make the proof clear without inflated claims.",
                    "confidence": "high",
                    "source_sample_ids": [item["sample_id"] for item in samples],
                    "rhythm": "Short claim followed by one concrete reason.",
                    "compression": "Compressed but not cryptic.",
                    "capitalization": "Conventional.",
                    "parentheticals": "Rare and only for factual qualification.",
                    "question_use": "Rare; no bait questions.",
                    "claim_style": "Evidence precedes conclusion.",
                    "preferred_moves": ["specific proof", "plain consequence"],
                    "banned_moves": ["inflated significance", "generic uplift"],
                    "cta_rules": "One direct action after proof.",
                    "channel_notes": {"deck": "Takeaway titles; low-density body copy."},
                    "coverage_shortfall_reason": "",
                },
                "claims": [
                    {
                        "claim_id": "claim-01",
                        "text": "The current category promise is easy to substitute.",
                        "approval_status": "approved",
                        "evidence_ids": ["evidence-01"],
                    },
                    {
                        "claim_id": "claim-02",
                        "text": "The approved benefit is visible during normal use.",
                        "approval_status": "approved",
                        "evidence_ids": ["evidence-01"],
                    },
                    {
                        "claim_id": "claim-03",
                        "text": "The evidence-led concept direction should be approved.",
                        "approval_status": "approved",
                        "evidence_ids": ["evidence-01"],
                    },
                ],
                "dir_professional_judgment": {
                    "audience_effect": "Move skepticism to consideration through visible proof.",
                    "channel_fit": "The deck gives proof before the recommendation.",
                    "factual_boundaries": ["Do not extend the claim beyond normal use."],
                    "tradeoff": "Clarity takes priority over suspense at the proof beat.",
                    "approved_claim_ids": ["claim-01", "claim-02", "claim-03"],
                },
                "de_ai_refinement": {
                    "fidelity_status": "pass",
                    "protected_meaning_points": ["visible proof", "normal use"],
                    "factual_additions": [],
                    "new_claims_added": False,
                },
                "manual_craft_review": {
                    "reviewer_role": "copy_editor",
                    "status": "pass",
                    "rhythm_assessment": "Sentence lengths vary and each line advances the decision.",
                    "abstraction_assessment": "Every conclusion names the visible proof it depends on.",
                    "evidence_alignment": "pass",
                    "reviewed_ai_trace_clusters": [],
                },
                "humanizer_diagnostic": {
                    "authority": "diagnostic_only",
                    "trace_clusters": [],
                    "manual_review_required": False,
                    "may_fail_copy_by_itself": False,
                },
            },
        },
        "story_package": {
            "source_bindings": {
                "fact_ids": ["fact-01"],
                "source_evidence_ids": ["evidence-01"],
                "inference_ids": ["inference-01"],
            },
            "outline": {
                "beats": [
                    {
                        "beat_id": "story-beat-01",
                        "title": "Name the credibility gap",
                        "story_function": "Turn category skepticism into visible pressure.",
                        "visible_action": "The audience compares an unsupported promise with the approved use proof.",
                        "emotional_shift": "General doubt becomes a concrete question.",
                        "duration_estimate": "opening",
                        "source_fact_ids": ["fact-01"],
                        "source_inference_ids": ["inference-01"],
                    },
                    {
                        "beat_id": "story-beat-02",
                        "title": "Reveal the proof",
                        "story_function": "Make the source-backed mechanism visible.",
                        "visible_action": "Normal use demonstrates the approved benefit.",
                        "emotional_shift": "Skepticism becomes informed consideration.",
                        "duration_estimate": "middle",
                        "source_fact_ids": ["fact-01"],
                        "source_inference_ids": ["inference-01"],
                    },
                    {
                        "beat_id": "story-beat-03",
                        "title": "Resolve on the decision",
                        "story_function": "Translate proof into the requested approval.",
                        "visible_action": "The recommendation points back to the visible proof.",
                        "emotional_shift": "Consideration becomes a clear decision.",
                        "duration_estimate": "closing",
                        "source_fact_ids": ["fact-01"],
                        "source_inference_ids": ["inference-01"],
                    },
                ]
            },
            "concept": {
                "concept_author_id": "concept-author-01",
                "specific_dependencies": [
                    {
                        "dependency_id": "dependency-01",
                        "description": "The proof depends on the approved use method.",
                    },
                    {
                        "dependency_id": "dependency-02",
                        "description": "The payoff depends on the audience's documented occasion.",
                    },
                ],
                "substitutability_check": {
                    "alternatives": [
                        {
                            "alternative_id": "alternative-01",
                            "subject": "nearest generic competitor",
                            "proximity_reason": "It makes the same category-level promise.",
                        },
                        {
                            "alternative_id": "alternative-02",
                            "subject": "generic lifestyle substitute",
                            "proximity_reason": "It could inherit the mood without inheriting the proof.",
                        },
                    ],
                    "selected_alternative_id": "alternative-01",
                    "swap_subject": "nearest generic competitor",
                    "before_swap": "Approved use visibly proves the benefit in the documented occasion.",
                    "after_swap": "A generic competitor repeats the promise without the approved use proof.",
                    "still_works_without_rewrite": False,
                    "broken_dependency_ids": ["dependency-01", "dependency-02"],
                    "verdict": "distinctive",
                    "independent_reviewer": {
                        "reviewer_id": "reviewer-01",
                        "reviewer_role": "independent_creative_reviewer",
                        "independent_from_concept_author": True,
                        "review_status": "pass",
                    },
                },
            },
            "copy_execution": {
                "audience_facing_text": "The proof appears in normal use. The recommendation follows that evidence.",
                "claim_ids_used": ["claim-02"],
                "evidence_ids_used": ["evidence-01"],
                "voice_profile_status": "pass",
                "dir_professional_judgment_status": "pass",
                "de_ai_fidelity_status": "pass",
                "manual_craft_status": "pass",
                "humanizer_review_status": "pass",
                "ai_trace_clusters": [],
            },
        },
        "deck_narrative_spec": {
            "project_title": "Reference Creative Copy Deck",
            "version": "1.0.0",
            "communication_job": {
                "audience": "Client decision makers",
                "deck_job": "recommend",
                "audience_outcome": "Approve the evidence-led concept direction.",
                "central_takeaway": "Visible use proof makes the proposition credible.",
            },
            "source_constraints": {
                "fact_ids": ["fact-01"],
                "source_evidence_ids": ["evidence-01"],
                "inference_ids": ["inference-01"],
                "approved_claim_ids": ["claim-01", "claim-02", "claim-03"],
                "inference_disclosure_policy": "label_as_inference",
            },
            "story_arc": {
                "arc_type": "tension -> proof -> decision",
                "opening_tension": "The category promise feels interchangeable.",
                "beats": [
                    {
                        "beat_id": "beat-01",
                        "audience_question": "Why will the audience hesitate?",
                        "narrative_job": "Make the skepticism concrete.",
                        "primary_claim_id": "claim-01",
                        "primary_claim": "The current category promise is easy to substitute.",
                        "evidence_ids": ["evidence-01"],
                        "audience_shift": "Recognize the credibility gap.",
                        "transition_to_next": "The next beat needs visible proof.",
                    },
                    {
                        "beat_id": "beat-02",
                        "audience_question": "What makes this direction credible?",
                        "narrative_job": "Show the approved proof mechanism.",
                        "primary_claim_id": "claim-02",
                        "primary_claim": "The approved benefit is visible during normal use.",
                        "evidence_ids": ["evidence-01"],
                        "audience_shift": "See why the subject is necessary.",
                        "transition_to_next": "The proof now supports a decision.",
                    },
                    {
                        "beat_id": "beat-03",
                        "audience_question": "What should be approved?",
                        "narrative_job": "Resolve the tension with a recommendation.",
                        "primary_claim_id": "claim-03",
                        "primary_claim": "The evidence-led concept direction should be approved.",
                        "evidence_ids": ["evidence-01"],
                        "audience_shift": "Move from evaluation to approval.",
                        "transition_to_next": "End on the explicit decision.",
                    },
                ],
                "closing_resolution": "Approve the concept because its proof cannot be swapped out.",
            },
            "slides": [
                {
                    "slide_id": f"slide-{index:02d}",
                    "beat_id": f"beat-{index:02d}",
                    "narrative_job": job,
                    "takeaway_title": title,
                    "primary_claim_id": claim_id,
                    "primary_claim": claim,
                    "evidence_ids": ["evidence-01"],
                    "layout": {
                        "layout_family": "image_led" if index == 2 else "claim_and_evidence",
                        "composition": "One dominant visual zone with a clear text hierarchy.",
                        "primary_visual_role": "proof" if index == 2 else "context",
                        "text_density": "low",
                        "title_max_lines": 1,
                        "avoid_ui_panels": True,
                    },
                }
                for index, (job, title, claim_id, claim) in enumerate(
                    [
                        (
                            "Make the skepticism concrete.",
                            "The category promise is easy to swap",
                            "claim-01",
                            "The current category promise is easy to substitute.",
                        ),
                        (
                            "Show the approved proof mechanism.",
                            "Normal use makes the benefit legible",
                            "claim-02",
                            "The approved benefit is visible during normal use.",
                        ),
                        (
                            "Resolve the tension with a recommendation.",
                            "Approve the direction that owns its proof",
                            "claim-03",
                            "The evidence-led concept direction should be approved.",
                        ),
                    ],
                    start=1,
                )
            ],
            "delivery_route": {
                "default_route": "Presentations",
                "selected_route": "Presentations",
                "editable_ppt_required": True,
                "element_level_editability": "required",
                "codex_ppt": {
                    "allowed_only_with_non_editable_acceptance": True,
                    "user_accepted_full_slide_images": False,
                    "output_editability": "full_slide_image_only",
                },
                "high_end_visual_design": {
                    "allowed_role": "aesthetic_reference_only",
                    "presentation_rule_authority": False,
                },
            },
            "qa": {
                "story_arc_complete": True,
                "one_narrative_job_per_slide": True,
                "claims_traceable": True,
                "evidence_traceable": True,
                "layout_readable": True,
                "audience_facing_copy_only": True,
                "editability_route_valid": True,
            },
        },
    }


def mutate(bundle: dict[str, Any], mutations: list[dict[str, Any]]) -> None:
    for mutation in mutations:
        operation = mutation.get("operation")
        path = mutation.get("path", "")
        if operation not in {"replace", "remove"} or not present(path):
            raise AssertionError(f"invalid fixture mutation: {mutation}")
        parts = path.split(".")
        cursor: Any = bundle
        for part in parts[:-1]:
            if isinstance(cursor, dict):
                child = cursor.get(part)
            elif isinstance(cursor, list) and part.isdigit() and int(part) < len(cursor):
                child = cursor[int(part)]
            else:
                raise AssertionError(f"mutation path does not resolve: {path}")
            cursor = child
        final = parts[-1]
        if operation == "replace":
            if isinstance(cursor, dict):
                cursor[final] = copy.deepcopy(mutation.get("value"))
            elif isinstance(cursor, list) and final.isdigit() and int(final) < len(cursor):
                cursor[int(final)] = copy.deepcopy(mutation.get("value"))
            else:
                raise AssertionError(f"mutation path does not resolve: {path}")
        else:
            if isinstance(cursor, dict) and final in cursor:
                del cursor[final]
            elif isinstance(cursor, list) and final.isdigit() and int(final) < len(cursor):
                del cursor[int(final)]
            else:
                raise AssertionError(f"mutation path does not resolve: {path}")


def resolve_path(bundle: dict[str, Any], path: str) -> Any:
    cursor: Any = bundle
    for part in path.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        elif isinstance(cursor, list) and part.isdigit() and int(part) < len(cursor):
            cursor = cursor[int(part)]
        else:
            raise AssertionError(f"path does not resolve: {path}")
    return cursor


def assert_fail_closed_collections() -> int:
    collection_specs = [
        (
            "project.creative_foundation.source_evidence",
            "evidence_id",
            "creative_source_evidence_missing",
        ),
        (
            "project.creative_foundation.facts",
            "fact_id",
            "creative_fact_source_binding_missing",
        ),
        (
            "project.copy_development.source_samples",
            "sample_id",
            "copy_source_samples_missing",
        ),
        (
            "project.copy_development.claims",
            "claim_id",
            "copy_claim_register_invalid",
        ),
        (
            "story_package.outline.beats",
            "beat_id",
            "creative_story_beat_source_binding_invalid",
        ),
        (
            "deck_narrative_spec.story_arc.beats",
            "beat_id",
            "deck_story_arc_incomplete",
        ),
        (
            "deck_narrative_spec.slides",
            "slide_id",
            "deck_slide_collection_invalid",
        ),
    ]
    cases_run = 0
    for path, id_field, expected_finding_id in collection_specs:
        reference = valid_reference_bundle()
        records = copy.deepcopy(resolve_path(reference, path))
        variants = {
            "not_array": {},
            "non_mapping_item": records + ["invalid-record"],
            "duplicate_id": records + [copy.deepcopy(records[0])],
            "blank_id": copy.deepcopy(records),
        }
        variants["blank_id"][0][id_field] = ""
        for variant_name, replacement in variants.items():
            bundle = valid_reference_bundle()
            mutate(bundle, [{"operation": "replace", "path": path, "value": replacement}])
            blocker_ids = {
                item.finding_id
                for item in validate_bundle(bundle)
                if item.severity == "blocker"
            }
            if expected_finding_id not in blocker_ids:
                raise AssertionError(
                    f"{path} {variant_name} failed open; expected {expected_finding_id}, got {sorted(blocker_ids)}"
                )
            cases_run += 1
    if cases_run != 28:
        raise AssertionError(f"fail-closed collection matrix ran {cases_run} cases, expected 28")
    return cases_run


def assert_fixture(path: str) -> dict[str, Any]:
    data = load_yaml(path)
    fixture = data.get("fixture", {})
    bundle = valid_reference_bundle()
    mutate(bundle, fixture.get("mutations", []))
    findings = validate_bundle(bundle)
    blockers = {item.finding_id for item in findings if item.severity == "blocker"}
    reviews = {item.finding_id for item in findings if item.severity == "review"}
    expected_blockers = set(fixture.get("expected_failure_ids", []))
    expected_reviews = set(fixture.get("expected_review_ids", []))
    expectation = fixture.get("expectation")

    if expectation == "reject":
        if blockers != expected_blockers:
            raise AssertionError(
                f"{path} blockers mismatch: expected {sorted(expected_blockers)}, got {sorted(blockers)}"
            )
    elif expectation == "review_only":
        if blockers:
            raise AssertionError(f"{path} review-only fixture produced blockers: {sorted(blockers)}")
    else:
        raise AssertionError(f"{path} has invalid expectation: {expectation}")

    if reviews != expected_reviews:
        raise AssertionError(
            f"{path} reviews mismatch: expected {sorted(expected_reviews)}, got {sorted(reviews)}"
        )
    return {
        "expectation": expectation,
        "blockers": blockers,
        "reviews": reviews,
    }


def assert_schema_contracts() -> None:
    project = load_yaml(SCHEMA_PATHS[0])
    story = load_yaml(SCHEMA_PATHS[1])
    deck = load_yaml(SCHEMA_PATHS[2])
    for key in ["creative_foundation", "commercial_strategy", "copy_development"]:
        if key not in project:
            raise AssertionError(f"project schema missing {key}")
    copy_schema = mapping(project.get("copy_development"))
    sample_schema = copy_schema.get("source_samples")
    if not isinstance(sample_schema, list) or not sample_schema or not isinstance(sample_schema[0], dict):
        raise AssertionError("project schema source_samples must expose a mapping-array contract")
    if any(field not in sample_schema[0] for field in SOURCE_SAMPLE_FIELDS):
        raise AssertionError("project schema source sample provenance contract is incomplete")
    profile_schema = mapping(copy_schema.get("voice_profile"))
    if "coverage_shortfall_reason" not in profile_schema:
        raise AssertionError("project schema VOICE PROFILE missing coverage_shortfall_reason")
    if "manual_craft_review" not in copy_schema:
        raise AssertionError("project schema missing manual_craft_review")
    for key in ["source_bindings", "concept", "copy_execution"]:
        if key not in story:
            raise AssertionError(f"story-package schema missing {key}")
    story_beats_schema = mapping(story.get("outline")).get("beats")
    if not isinstance(story_beats_schema, list) or not story_beats_schema:
        raise AssertionError("story-package schema missing beats mapping array")
    story_beat_schema = mapping(story_beats_schema[0])
    for key in ["beat_id", "source_fact_ids", "source_inference_ids"]:
        if key not in story_beat_schema:
            raise AssertionError(f"story-package beat schema missing {key}")
    concept_schema = mapping(story.get("concept"))
    if "concept_author_id" not in concept_schema:
        raise AssertionError("story-package concept schema missing concept_author_id")
    swap_schema = mapping(concept_schema.get("substitutability_check"))
    for key in [
        "alternatives",
        "selected_alternative_id",
        "before_swap",
        "after_swap",
        "broken_dependency_ids",
        "independent_reviewer",
    ]:
        if key not in swap_schema:
            raise AssertionError(f"story-package substitutability schema missing {key}")
    copy_execution_schema = mapping(story.get("copy_execution"))
    for key in ["evidence_ids_used", "manual_craft_status", "ai_trace_clusters"]:
        if key not in copy_execution_schema:
            raise AssertionError(f"story-package copy_execution schema missing {key}")
    deck_spec = deck.get("deck_narrative_spec", {})
    for key in ["communication_job", "source_constraints", "story_arc", "slides", "delivery_route", "qa"]:
        if key not in deck_spec:
            raise AssertionError(f"deck narrative schema missing {key}")
    if "inference_ids" not in mapping(deck_spec.get("source_constraints")):
        raise AssertionError("deck source constraints missing inference_ids")
    deck_beats_schema = mapping(deck_spec.get("story_arc")).get("beats")
    slides_schema = deck_spec.get("slides")
    if not isinstance(deck_beats_schema, list) or not deck_beats_schema:
        raise AssertionError("deck schema missing beats mapping array")
    if not isinstance(slides_schema, list) or not slides_schema:
        raise AssertionError("deck schema missing slides mapping array")
    beat_schema = mapping(deck_beats_schema[0])
    slide_schema = mapping(slides_schema[0])
    if "primary_claim_id" not in beat_schema or "primary_claim_id" not in slide_schema:
        raise AssertionError("deck beat/slide schema missing primary_claim_id")
    if "claims_traceable" not in mapping(deck_spec.get("qa")):
        raise AssertionError("deck QA schema missing claims_traceable")


def assert_docs_and_skills() -> None:
    capability = read("docs/film-preproduction/creative-copy-deck-capability.md")
    voice = read("docs/film-preproduction/professional-agent-voice-standard.md")
    idea = read("skills/dircreative/idea-intake/SKILL.md")
    story = read("skills/dircreative/story-development/SKILL.md")
    script = read("skills/dircreative/script-treatment/SKILL.md")
    require_terms(
        capability,
        [
            "facts",
            "source_evidence",
            "inferences",
            "audience_tension",
            "business_objective",
            "single_minded_proposition",
            "avoid_cliches",
            "Concept Substitutability Gate",
            "real source samples",
            "VOICE PROFILE",
            "DIR professional judgment",
            "de-AI fidelity refinement",
            "word-list hit is not proof of AI authorship",
            "collections fail closed",
            "broken_dependency_ids",
            "concept_author_id",
            "coverage_shortfall_reason",
            "manual craft review",
            "primary_claim_id",
            "Deck QA records are recomputed",
            "audience-facing narrative fields",
            "not hard-coded declarations",
            "deck_narrative_spec",
            "Presentations",
            "codex-ppt",
            "high-end-visual-design",
            "does not create a PPT",
            "does not modify `skills/dircreative/SKILL.md`",
        ],
        "creative copy deck capability",
    )
    require_terms(
        voice,
        [
            "real source samples",
            "VOICE PROFILE",
            "DIR professional judgment",
            "de-AI fidelity refinement",
            "diagnostic gate",
            "cannot fail copy by itself",
            "approved claim IDs",
            "manual review of rhythm, abstraction, and evidence alignment",
            "word-list-clean copy",
        ],
        "professional voice standard",
    )
    require_terms(
        idea + "\n" + story + "\n" + script,
        [
            "creative-copy-deck-capability.md",
            "source_evidence_ids",
            "source_fact_ids",
            "source_inference_ids",
            "single-minded proposition",
            "still_works_without_rewrite",
            "broken_dependency_ids",
            "independent_reviewer",
            "concept_author_id",
            "VOICE PROFILE",
            "deck_narrative_spec",
            "primary_claim_id",
            "Editable PowerPoint defaults to `Presentations`",
            "`codex-ppt` is allowed only after the user explicitly accepts full-slide images",
            "`high-end-visual-design` may inform aesthetic references",
            "Do not generate slides, slide images, or a `.pptx`",
        ],
        "DIRcreative sub-skill wiring",
    )


def assert_positive_reference() -> None:
    findings = validate_bundle(valid_reference_bundle())
    if findings:
        rendered = [f"{item.severity}:{item.finding_id}" for item in findings]
        raise AssertionError(f"valid reference bundle produced findings: {rendered}")


def assert_voice_profile_shortfall_paths() -> None:
    coverage_shortfall = valid_reference_bundle()
    profile = coverage_shortfall["project"]["copy_development"]["voice_profile"]
    profile["source_sample_ids"] = profile["source_sample_ids"][:-1]
    profile["coverage_shortfall_reason"] = "The excluded sample is a legal footer, not authored brand copy."
    findings = validate_bundle(coverage_shortfall)
    if findings:
        raise AssertionError(
            "documented VOICE PROFILE coverage shortfall failed: "
            + ", ".join(item.finding_id for item in findings)
        )

    source_shortfall = valid_reference_bundle()
    copy_development = source_shortfall["project"]["copy_development"]
    copy_development["source_samples"] = copy_development["source_samples"][:4]
    copy_development["sample_shortfall_reason"] = "Only four approved original samples exist."
    short_profile = copy_development["voice_profile"]
    short_profile["source_sample_ids"] = short_profile["source_sample_ids"][:4]
    short_profile["confidence"] = "medium"
    findings = validate_bundle(source_shortfall)
    if findings:
        raise AssertionError(
            "documented source-sample shortfall failed: "
            + ", ".join(item.finding_id for item in findings)
        )


def assert_codex_ppt_consent_route() -> None:
    bundle = valid_reference_bundle()
    route = bundle["deck_narrative_spec"]["delivery_route"]
    route["selected_route"] = "codex-ppt"
    route["editable_ppt_required"] = False
    route["element_level_editability"] = "not_available"
    route["codex_ppt"]["user_accepted_full_slide_images"] = True
    findings = validate_bundle(bundle)
    if findings:
        raise AssertionError(
            "explicitly consented codex-ppt route failed: "
            + ", ".join(item.finding_id for item in findings)
        )


def main() -> int:
    checks: list[Check] = []
    fixture_results: dict[str, dict[str, Any]] = {}
    measured: dict[str, int] = {}

    def run_fail_closed_matrix() -> None:
        measured["fail_closed_cases"] = assert_fail_closed_collections()

    def run_fixture(path: str) -> None:
        fixture_results[path] = assert_fixture(path)

    add_check(checks, "schemas parse and expose durable contracts", ", ".join(SCHEMA_PATHS), assert_schema_contracts)
    add_check(
        checks,
        "capability and sub-skills preserve routing boundaries",
        "creative-copy-deck capability + professional voice + three sub-skills",
        assert_docs_and_skills,
    )
    add_check(
        checks,
        "complete creative/copy/deck reference passes",
        "embedded behavior-level positive reference",
        assert_positive_reference,
    )
    add_check(
        checks,
        "VOICE PROFILE coverage and source shortfalls are explicit",
        "two behavior-level positive shortfall cases",
        assert_voice_profile_shortfall_paths,
    )
    add_check(
        checks,
        "codex-ppt requires and accepts explicit non-editable consent",
        "behavior-level consented route case; no PPT generation",
        assert_codex_ppt_consent_route,
    )
    add_check(
        checks,
        "evidence/facts/samples/claims/beats/slides fail closed",
        "28 malformed-array, non-mapping-item, duplicate-ID, and blank-ID adversarial cases",
        run_fail_closed_matrix,
    )
    for path in FIXTURE_PATHS:
        add_check(
            checks,
            f"fixture behavior: {Path(path).name}",
            path,
            lambda fixture_path=path: run_fixture(fixture_path),
        )

    print("DIRcreative Creative Copy Deck Audit")
    print("=" * 72)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.label}")
        print(f"       evidence: {check.evidence}")
    failures = [check for check in checks if not check.ok]
    if failures:
        print("CREATIVE_COPY_DECK_AUDIT: FAIL")
        return 1

    reference = valid_reference_bundle()
    reference_findings = validate_bundle(reference)
    reference_blocker_ids = {
        item.finding_id for item in reference_findings if item.severity == "blocker"
    }
    foundation_finding_ids = {
        "creative_source_evidence_missing",
        "creative_fact_source_binding_missing",
        "creative_inference_binding_missing",
        "creative_audience_tension_missing",
        "creative_audience_tension_source_binding_invalid",
        "creative_business_objective_missing",
        "creative_single_minded_proposition_missing",
        "creative_single_minded_proposition_binding_invalid",
        "creative_avoid_cliches_missing",
        "creative_story_source_binding_invalid",
    }
    creative_foundation_ready = not bool(reference_blocker_ids & foundation_finding_ids)
    concept_ready = "creative_concept_substitutable" not in reference_blocker_ids
    copy_pipeline_ready = not any(item.startswith("copy_") for item in reference_blocker_ids)
    blocking_fixtures_rejected = sum(
        1
        for result in fixture_results.values()
        if result["expectation"] == "reject" and bool(result["blockers"])
    )
    review_only_fixtures_accepted = sum(
        1
        for result in fixture_results.values()
        if result["expectation"] == "review_only"
        and not result["blockers"]
        and bool(result["reviews"])
    )
    ai_trace_scan_failure_authority = any(
        "copy_ai_trace_cluster_review" in result["blockers"]
        for result in fixture_results.values()
    )
    record_paths = [
        "project.creative_foundation.source_evidence",
        "project.creative_foundation.facts",
        "project.copy_development.source_samples",
        "project.copy_development.claims",
        "story_package.outline.beats",
        "deck_narrative_spec.story_arc.beats",
        "deck_narrative_spec.slides",
    ]
    validated_reference_records = sum(len(resolve_path(reference, path)) for path in record_paths)
    deck_default_route = resolve_path(reference, "deck_narrative_spec.delivery_route.default_route")
    ppt_outputs = [
        path
        for suffix in ("*.ppt", "*.pptx")
        for path in ROOT.rglob(suffix)
        if ".git" not in path.parts
    ]

    print(f"creative_foundation_ready: {str(creative_foundation_ready).lower()}")
    print(f"concept_substitutability_gate_ready: {str(concept_ready).lower()}")
    print(f"copy_pipeline_ready: {str(copy_pipeline_ready).lower()}")
    print(f"fail_closed_cases_run: {measured['fail_closed_cases']}")
    print(f"validated_reference_records: {validated_reference_records}")
    print(f"blocking_fixtures_rejected: {blocking_fixtures_rejected}")
    print(f"review_only_fixtures_accepted: {review_only_fixtures_accepted}")
    print(f"ai_trace_scan_failure_authority: {str(ai_trace_scan_failure_authority).lower()}")
    print(f"deck_default_route: {deck_default_route}")
    print(f"ppt_generated: {str(bool(ppt_outputs)).lower()}")
    print("CREATIVE_COPY_DECK_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
