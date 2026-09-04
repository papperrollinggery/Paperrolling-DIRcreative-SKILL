#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
OPERATIONS = {"auto", "write", "review", "refactor", "recreate"}
TEXT_KINDS = {"narrative", "professional", "other"}
LANGUAGES = {"zh", "en", "mixed"}
SCOPES = {"line", "passage", "document"}
DEFECT_LEVELS = {"unknown", "none", "local", "systemic"}
SOURCE_MODES = {"new", "existing"}
STATUS_VALUES = {"available", "locked", "missing", "not_applicable"}
MODEL_SOURCES = {"user", "metadata", "system", "unknown"}
BOUNDED_PREFERENCES = {"auto", "contextual", "fidelity"}
PRESERVATION_STATUSES = {"ready", "missing"}
PRESERVATION_COVERAGE = {"covered", "not_present"}
PRESERVATION_KINDS = {
    "fact",
    "claim",
    "intent",
    "quotation",
    "dialogue",
    "protected_span",
}
PRESERVATION_COVERAGE_FIELDS = {
    "facts": "fact",
    "claims": "claim",
    "intent": "intent",
    "quotations": "quotation",
    "dialogue": "dialogue",
    "protected_spans": "protected_span",
}
DIAGNOSIS_LAYERS = {"architecture", "venue", "discourse", "surface"}
DIAGNOSIS_SEVERITIES = {"local", "systemic"}
WHITELIST_VERDICTS = {
    "not_whitelisted",
    "intentional_voice",
    "venue_convention",
    "isolated_hit",
}
CALIBRATION_MODES = {"voice_profile", "venue_corpus", "domain_baseline"}
CALIBRATION_SOURCE_KINDS = {
    "user_approved_source",
    "approved_project_source",
    "verified_venue_corpus",
}
SOURCE_TEXT_BYTES_MAX = 65536
CALIBRATION_SAMPLE_BYTES_MAX = 32768
DIAGNOSIS_FINDINGS_MAX = 64
NARRATIVE_FORBIDDEN_AUTO_MOVES = [
    "direct_reader_address",
    "fourth_wall_break",
    "subplot_insertion",
    "named_reference_injection",
    "nonlinear_time_injection",
    "delayed_revelation_injection",
    "rarity_move_injection",
]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]*$")

NARRATIVE_DOCUMENTS = {
    "screenplay",
    "story",
    "treatment",
    "synopsis",
    "pitch_narrative",
    "narrative_essay",
}
PROFESSIONAL_PROFILES = {
    "release_notes": "release_notes",
    "changelog": "release_notes",
    "announcement": "release_notes",
    "dev_reply": "dev_replies",
    "review_comment": "dev_replies",
    "issue_reply": "dev_replies",
    "postmortem": "postmortem",
    "rca": "postmortem",
    "ticket": "tickets",
    "work_order": "tickets",
    "bug_report": "tickets",
    "technical_article": "technical_article",
    "blog_post": "technical_article",
    "tutorial": "technical_article",
}
REFERENCE_PACKS = {
    "narrative": [
        "references/narrative-pass.md",
        "references/discourse-pass.md",
        "references/style-pass.md",
        "references/rubric.md",
        "references/model-fingerprints.md",
    ],
    "professional": [
        "references/professional-pass.md",
        "references/style-pass.md",
        "references/model-fingerprints.md",
    ],
    "release_notes": [
        "references/professional-pass.md",
        "references/domains/release-notes.md",
        "references/style-pass.md",
        "references/model-fingerprints.md",
    ],
    "dev_replies": [
        "references/professional-pass.md",
        "references/domains/dev-replies.md",
        "references/style-pass.md",
        "references/model-fingerprints.md",
    ],
    "postmortem": [
        "references/professional-pass.md",
        "references/domains/postmortems.md",
        "references/discourse-pass.md",
        "references/style-pass.md",
        "references/model-fingerprints.md",
    ],
    "tickets": [
        "references/professional-pass.md",
        "references/domains/tickets.md",
        "references/style-pass.md",
        "references/model-fingerprints.md",
    ],
    "technical_article": [
        "references/professional-pass.md",
        "references/domains/tech-articles.md",
        "references/discourse-pass.md",
        "references/style-pass.md",
        "references/model-fingerprints.md",
    ],
}


def add_error(errors: list[str], code: str, detail: str) -> None:
    errors.append(f"{code}: {detail}")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def expected_profile_for_document(document_type: str) -> str:
    if document_type in NARRATIVE_DOCUMENTS:
        return "narrative"
    return PROFESSIONAL_PROFILES.get(document_type, "professional")


def validate_diagnosis_set(
    value: Any,
    document_type: str,
    profile: str,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected_fields = {
        "status",
        "source_text",
        "source_text_sha256",
        "document_type",
        "humanization_profile",
        "findings",
        "diagnosis_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        return ["humanization_diagnosis_invalid: exact diagnosis contract required"], {}
    source_text = value.get("source_text")
    if not isinstance(source_text, str) or not source_text.strip():
        add_error(errors, "humanization_diagnosis_source_required", document_type)
        source_text = ""
    elif len(source_text.encode("utf-8")) > SOURCE_TEXT_BYTES_MAX:
        add_error(errors, "humanization_diagnosis_source_too_large", document_type)
    actual_source_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if value.get("source_text_sha256") != actual_source_sha:
        add_error(errors, "humanization_diagnosis_source_hash_mismatch", document_type)
    if value.get("status") != "complete":
        add_error(errors, "humanization_diagnosis_incomplete", str(value.get("status")))
    if value.get("document_type") != document_type:
        add_error(errors, "humanization_diagnosis_document_mismatch", str(value.get("document_type")))
    if value.get("humanization_profile") != profile:
        add_error(errors, "humanization_diagnosis_profile_mismatch", str(value.get("humanization_profile")))
    findings = value.get("findings")
    if not isinstance(findings, list) or not findings:
        add_error(errors, "humanization_findings_required", document_type)
        findings = []
    elif len(findings) > DIAGNOSIS_FINDINGS_MAX:
        add_error(errors, "humanization_findings_too_many", str(len(findings)))
    seen_ids: set[str] = set()
    for index, finding in enumerate(findings):
        label = str(index)
        if not isinstance(finding, dict) or set(finding) != {
            "finding_id",
            "cluster_id",
            "layer",
            "severity",
            "whitelist_verdict",
            "problem",
            "evidence_quote",
            "evidence_start",
            "evidence_end",
            "evidence_spans",
            "recommended_operation",
        }:
            add_error(errors, "humanization_finding_invalid", label)
            continue
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not ID_RE.fullmatch(finding_id) or finding_id in seen_ids:
            add_error(errors, "humanization_finding_id_invalid", str(finding_id))
        else:
            seen_ids.add(finding_id)
        cluster_id = finding.get("cluster_id")
        if not isinstance(cluster_id, str) or not ID_RE.fullmatch(cluster_id):
            add_error(errors, "humanization_finding_cluster_id_invalid", str(finding_id))
        if finding.get("layer") not in DIAGNOSIS_LAYERS:
            add_error(errors, "humanization_finding_layer_invalid", str(finding_id))
        if finding.get("severity") not in DIAGNOSIS_SEVERITIES:
            add_error(errors, "humanization_finding_severity_invalid", str(finding_id))
        if finding.get("recommended_operation") not in {"refactor", "recreate"}:
            add_error(errors, "humanization_finding_operation_invalid", str(finding_id))
        if finding.get("whitelist_verdict") not in WHITELIST_VERDICTS:
            add_error(errors, "humanization_finding_whitelist_invalid", str(finding_id))
        if not isinstance(finding.get("problem"), str) or not finding["problem"].strip():
            add_error(errors, "humanization_finding_problem_invalid", str(finding_id))
        quote = finding.get("evidence_quote")
        start = finding.get("evidence_start")
        end = finding.get("evidence_end")
        if (
            not isinstance(quote, str)
            or not quote
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end <= start
            or end > len(source_text)
            or source_text[start:end] != quote
        ):
            add_error(errors, "humanization_finding_evidence_invalid", str(finding_id))
        evidence_spans = finding.get("evidence_spans")
        seen_spans: set[tuple[int, int, str]] = set()
        if not isinstance(evidence_spans, list) or len(evidence_spans) < 2:
            add_error(errors, "humanization_finding_cluster_evidence_insufficient", str(finding_id))
            evidence_spans = []
        for span_index, span in enumerate(evidence_spans):
            if not isinstance(span, dict) or set(span) != {"quote", "start", "end"}:
                add_error(
                    errors,
                    "humanization_finding_cluster_span_invalid",
                    f"{finding_id}/{span_index}",
                )
                continue
            span_quote = span.get("quote")
            span_start = span.get("start")
            span_end = span.get("end")
            span_key = (
                (span_start, span_end, span_quote)
                if isinstance(span_start, int)
                and not isinstance(span_start, bool)
                and isinstance(span_end, int)
                and not isinstance(span_end, bool)
                and isinstance(span_quote, str)
                else None
            )
            if (
                not isinstance(span_quote, str)
                or not span_quote
                or not isinstance(span_start, int)
                or isinstance(span_start, bool)
                or not isinstance(span_end, int)
                or isinstance(span_end, bool)
                or span_start < 0
                or span_end <= span_start
                or span_end > len(source_text)
                or source_text[span_start:span_end] != span_quote
                or span_key in seen_spans
            ):
                add_error(
                    errors,
                    "humanization_finding_cluster_span_invalid",
                    f"{finding_id}/{span_index}",
                )
            else:
                assert span_key is not None
                seen_spans.add(span_key)
        if (start, end, quote) not in seen_spans:
            add_error(errors, "humanization_finding_primary_evidence_unbound", str(finding_id))
    expected_digest = canonical_sha256(
        {key: value[key] for key in expected_fields if key != "diagnosis_sha256"}
    )
    if value.get("diagnosis_sha256") != expected_digest:
        add_error(errors, "humanization_diagnosis_hash_mismatch", document_type)
    return errors, dict(value)


def validate_calibration_context(
    value: Any,
    profile: str,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected_fields = {"status", "mode", "profile_id", "samples", "context_sha256"}
    if not isinstance(value, dict) or set(value) != expected_fields:
        return ["humanization_calibration_invalid: exact calibration contract required"], {}
    if value.get("status") != "ready":
        add_error(errors, "humanization_calibration_not_ready", str(value.get("status")))
    mode = value.get("mode")
    if mode not in CALIBRATION_MODES:
        add_error(errors, "humanization_calibration_mode_invalid", str(mode))
    profile_id = value.get("profile_id")
    if not isinstance(profile_id, str) or not ID_RE.fullmatch(profile_id):
        add_error(errors, "humanization_calibration_profile_id_invalid", str(profile_id))
    samples = value.get("samples")
    if not isinstance(samples, list):
        add_error(errors, "humanization_calibration_samples_invalid", profile)
        samples = []
    if sum(
        len(str(item.get("text", "")).encode("utf-8"))
        for item in samples
        if isinstance(item, dict)
    ) > CALIBRATION_SAMPLE_BYTES_MAX:
        add_error(errors, "humanization_calibration_samples_too_large", profile)
    seen: set[str] = set()
    seen_source_refs: set[str] = set()
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict) or set(sample) != {
            "sample_id",
            "text",
            "text_sha256",
            "source_kind",
            "source_ref",
        }:
            add_error(errors, "humanization_calibration_sample_invalid", str(index))
            continue
        sample_id = sample.get("sample_id")
        text = sample.get("text")
        if not isinstance(sample_id, str) or not ID_RE.fullmatch(sample_id) or sample_id in seen:
            add_error(errors, "humanization_calibration_sample_id_invalid", str(sample_id))
        else:
            seen.add(sample_id)
        if not isinstance(text, str) or len(text.strip()) < 20:
            add_error(errors, "humanization_calibration_sample_text_invalid", str(sample_id))
        elif sample.get("text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest():
            add_error(errors, "humanization_calibration_sample_hash_mismatch", str(sample_id))
        source_kind = sample.get("source_kind")
        source_ref = sample.get("source_ref")
        if source_kind not in CALIBRATION_SOURCE_KINDS:
            add_error(errors, "humanization_calibration_source_kind_invalid", str(sample_id))
        if not isinstance(source_ref, str) or not ID_RE.fullmatch(source_ref):
            add_error(errors, "humanization_calibration_source_ref_invalid", str(sample_id))
        elif source_ref in seen_source_refs:
            add_error(errors, "humanization_calibration_source_ref_duplicate", source_ref)
        else:
            seen_source_refs.add(source_ref)
        if mode == "voice_profile" and source_kind not in {
            "user_approved_source",
            "approved_project_source",
        }:
            add_error(errors, "humanization_voice_sample_source_invalid", str(sample_id))
        if mode == "venue_corpus" and source_kind != "verified_venue_corpus":
            add_error(errors, "humanization_venue_sample_source_invalid", str(sample_id))
    if profile == "narrative" and (mode != "voice_profile" or len(samples) < 2):
        add_error(errors, "narrative_voice_profile_evidence_required", str(profile_id))
    if profile != "narrative":
        if mode == "venue_corpus" and len(samples) < 2:
            add_error(errors, "venue_corpus_samples_required", str(profile_id))
        if mode == "voice_profile" and len(samples) < 2:
            add_error(errors, "professional_voice_profile_evidence_required", str(profile_id))
        if mode == "domain_baseline" and samples:
            add_error(errors, "domain_baseline_must_not_fake_samples", str(profile_id))
        expected_baseline_id = f"sepia-{profile}-domain-baseline-v0.5.0"
        if mode == "domain_baseline" and profile_id != expected_baseline_id:
            add_error(errors, "domain_baseline_id_invalid", str(profile_id))
    expected_digest = canonical_sha256(
        {key: value[key] for key in expected_fields if key != "context_sha256"}
    )
    if value.get("context_sha256") != expected_digest:
        add_error(errors, "humanization_calibration_hash_mismatch", str(profile_id))
    return errors, dict(value)


def validate_preservation_set(value: Any) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected_fields = {
        "status",
        "set_id",
        "source_text",
        "source_text_sha256",
        "coverage",
        "entries",
        "set_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        return ["preservation_invalid: exact preservation contract required"], {
            "status": "missing",
            "set_id": None,
            "source_text": None,
            "source_text_sha256": None,
            "coverage": {
                field: "not_present" for field in PRESERVATION_COVERAGE_FIELDS
            },
            "entries": [],
            "set_sha256": None,
        }
    status = value.get("status")
    if status not in PRESERVATION_STATUSES:
        add_error(errors, "preservation_status_invalid", str(status))
    if status == "missing":
        if any(
            (
                value.get("set_id") is not None,
                value.get("source_text") is not None,
                value.get("source_text_sha256") is not None,
                value.get("entries") != [],
                value.get("set_sha256") is not None,
            )
        ):
            add_error(errors, "preservation_missing_contract_invalid", "missing set carries content")
        coverage = value.get("coverage")
        if not isinstance(coverage, dict) or set(coverage) != set(PRESERVATION_COVERAGE_FIELDS):
            add_error(errors, "preservation_coverage_invalid", "exact coverage fields required")
        elif any(item != "not_present" for item in coverage.values()):
            add_error(errors, "preservation_missing_coverage_invalid", "missing set cannot claim coverage")
        return errors, dict(value)

    set_id = value.get("set_id")
    if not isinstance(set_id, str) or not ID_RE.fullmatch(set_id):
        add_error(errors, "preservation_set_id_invalid", str(set_id))
    source_text = value.get("source_text")
    if not isinstance(source_text, str) or not source_text.strip():
        add_error(errors, "preservation_source_text_required", str(set_id))
        source_text = ""
    elif len(source_text.encode("utf-8")) > SOURCE_TEXT_BYTES_MAX:
        add_error(errors, "preservation_source_text_too_large", str(set_id))
    actual_source_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if value.get("source_text_sha256") != actual_source_sha:
        add_error(errors, "preservation_source_hash_mismatch", str(set_id))
    coverage = value.get("coverage")
    if not isinstance(coverage, dict) or set(coverage) != set(PRESERVATION_COVERAGE_FIELDS):
        add_error(errors, "preservation_coverage_invalid", "exact coverage fields required")
        coverage = {}
    else:
        for field, coverage_status in coverage.items():
            if coverage_status not in PRESERVATION_COVERAGE:
                add_error(errors, "preservation_coverage_status_invalid", field)
    entries = value.get("entries")
    if not isinstance(entries, list) or not entries:
        add_error(errors, "preservation_entries_required", "ready set needs actual entries")
        entries = []
    seen_ids: set[str] = set()
    kinds_seen: set[str] = set()
    for index, entry in enumerate(entries):
        label = str(index)
        if not isinstance(entry, dict) or set(entry) != {
            "entry_id",
            "kind",
            "text",
            "text_sha256",
            "evidence_quote",
            "evidence_start",
            "evidence_end",
        }:
            add_error(errors, "preservation_entry_invalid", label)
            continue
        entry_id = entry.get("entry_id")
        if not isinstance(entry_id, str) or not ID_RE.fullmatch(entry_id) or entry_id in seen_ids:
            add_error(errors, "preservation_entry_id_invalid", str(entry_id))
        else:
            seen_ids.add(entry_id)
        kind = entry.get("kind")
        if kind not in PRESERVATION_KINDS:
            add_error(errors, "preservation_entry_kind_invalid", str(kind))
        else:
            kinds_seen.add(str(kind))
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            add_error(errors, "preservation_entry_text_invalid", str(entry_id))
        elif entry.get("text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest():
            add_error(errors, "preservation_entry_hash_mismatch", str(entry_id))
        quote = entry.get("evidence_quote")
        start = entry.get("evidence_start")
        end = entry.get("evidence_end")
        if (
            not isinstance(quote, str)
            or not quote
            or not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end <= start
            or end > len(source_text)
            or source_text[start:end] != quote
        ):
            add_error(errors, "preservation_entry_evidence_invalid", str(entry_id))
    for field, kind in PRESERVATION_COVERAGE_FIELDS.items():
        if coverage.get(field) == "covered" and kind not in kinds_seen:
            add_error(errors, "preservation_coverage_unsubstantiated", field)
        if coverage.get(field) == "not_present" and kind in kinds_seen:
            add_error(errors, "preservation_coverage_contradiction", field)
    if coverage.get("intent") != "covered":
        add_error(errors, "preservation_intent_required", "intent must be extracted")
    expected_digest = canonical_sha256(
        {key: value[key] for key in expected_fields if key != "set_sha256"}
    )
    if value.get("set_sha256") != expected_digest:
        add_error(errors, "preservation_set_hash_mismatch", str(value.get("set_id")))
    return errors, dict(value)


def build_humanization_guard(document_type: str) -> dict[str, Any]:
    guard = {
        "guard_version": "1.0",
        "document_type": document_type,
        "corpus_findings_are_advisory": True,
        "forbidden_auto_moves": (
            list(NARRATIVE_FORBIDDEN_AUTO_MOVES)
            if document_type in NARRATIVE_DOCUMENTS
            else []
        ),
        "protected_content_kinds": [
            "facts",
            "claims",
            "intent",
            "quotations",
            "dialogue",
            "approved_names_numbers_timecodes_and_super",
        ],
    }
    return {**guard, "guard_sha256": canonical_sha256(guard)}


def validate_humanization_guard(
    value: Any,
    document_type: str,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected_fields = {
        "guard_version",
        "document_type",
        "corpus_findings_are_advisory",
        "forbidden_auto_moves",
        "protected_content_kinds",
        "guard_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        return ["humanization_guard_invalid: exact guard contract required"], {}
    expected_guard = build_humanization_guard(document_type)
    if value.get("guard_version") != "1.0":
        add_error(errors, "humanization_guard_version_invalid", str(value.get("guard_version")))
    if value.get("document_type") != document_type:
        add_error(errors, "humanization_guard_document_mismatch", str(value.get("document_type")))
    if value.get("corpus_findings_are_advisory") is not True:
        add_error(errors, "humanization_guard_corpus_authority_invalid", document_type)
    forbidden = value.get("forbidden_auto_moves")
    if not isinstance(forbidden, list) or not all(isinstance(item, str) for item in forbidden):
        add_error(errors, "humanization_guard_moves_invalid", document_type)
        forbidden = []
    if document_type in NARRATIVE_DOCUMENTS and not set(
        NARRATIVE_FORBIDDEN_AUTO_MOVES
    ).issubset(forbidden):
        add_error(errors, "narrative_guard_incomplete", document_type)
    if forbidden != expected_guard["forbidden_auto_moves"]:
        add_error(errors, "humanization_guard_moves_not_canonical", document_type)
    protected = value.get("protected_content_kinds")
    required_protected = {
        "facts",
        "claims",
        "intent",
        "quotations",
        "dialogue",
        "approved_names_numbers_timecodes_and_super",
    }
    if not isinstance(protected, list) or not required_protected.issubset(protected):
        add_error(errors, "humanization_guard_protection_incomplete", document_type)
    if protected != expected_guard["protected_content_kinds"]:
        add_error(errors, "humanization_guard_protection_not_canonical", document_type)
    expected_digest = canonical_sha256(
        {key: value[key] for key in expected_fields if key != "guard_sha256"}
    )
    if value.get("guard_sha256") != expected_digest:
        add_error(errors, "humanization_guard_hash_mismatch", document_type)
    return errors, dict(value)


def validate_model(value: Any, role: str, errors: list[str]) -> dict[str, str]:
    if not isinstance(value, dict):
        add_error(errors, "model_identity_invalid", role)
        return {"family": "unknown", "version": "unknown", "source": "unknown"}
    family = str(value.get("family", "unknown")).strip() or "unknown"
    version = str(value.get("version", "unknown")).strip() or "unknown"
    source = value.get("source", "unknown")
    if source not in MODEL_SOURCES or source == "inferred_from_text":
        add_error(errors, "model_identity_source_invalid", role)
        source = "unknown"
    if role == "author" and source == "system":
        add_error(errors, "author_model_source_invalid", role)
    if role == "executor" and source in {"user", "metadata"}:
        add_error(errors, "executor_model_source_invalid", role)
    if source == "unknown":
        family, version = "unknown", "unknown"
    return {"family": family, "version": version, "source": str(source)}


def validate_spec(spec: Any) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["spec_invalid: root must be an object"], {}
    if spec.get("schema_version") != SCHEMA_VERSION:
        add_error(errors, "schema_version_invalid", str(spec.get("schema_version")))
    target_id = spec.get("target_id")
    if not isinstance(target_id, str) or not ID_RE.fullmatch(target_id):
        add_error(errors, "target_id_invalid", str(target_id))
    for field, allowed in (
        ("operation", OPERATIONS),
        ("text_kind", TEXT_KINDS),
        ("language", LANGUAGES),
        ("scope", SCOPES),
        ("structural_defects", DEFECT_LEVELS),
        ("source_mode", SOURCE_MODES),
        ("voice_profile_status", STATUS_VALUES),
        ("venue_corpus_status", STATUS_VALUES),
    ):
        if spec.get(field) not in allowed:
            add_error(errors, f"{field}_invalid", str(spec.get(field)))
    document_type = spec.get("document_type")
    if not isinstance(document_type, str) or not ID_RE.fullmatch(document_type):
        add_error(errors, "document_type_invalid", str(document_type))
    elif (
        spec.get("text_kind") == "narrative"
        and document_type not in NARRATIVE_DOCUMENTS
    ) or (
        spec.get("text_kind") == "professional"
        and document_type in NARRATIVE_DOCUMENTS
    ):
        add_error(errors, "text_kind_document_mismatch", document_type)
    length_chars = spec.get("length_chars")
    if not isinstance(length_chars, int) or isinstance(length_chars, bool) or length_chars < 0:
        add_error(errors, "length_chars_invalid", str(length_chars))
    for field in ("sepia_requested", "validation_required", "voice_skill_explicit"):
        if not isinstance(spec.get(field), bool):
            add_error(errors, f"{field}_invalid", str(spec.get(field)))
    bounded_preference = spec.get("bounded_preference", "auto")
    if bounded_preference not in BOUNDED_PREFERENCES:
        add_error(errors, "bounded_preference_invalid", str(bounded_preference))
    preservation_errors, preservation = validate_preservation_set(spec.get("preservation"))
    errors.extend(preservation_errors)
    author_model = validate_model(spec.get("author_model"), "author", errors)
    executor_model = validate_model(spec.get("executor_model"), "executor", errors)
    normalized = {
        **spec,
        "bounded_preference": bounded_preference,
        "preservation": preservation,
        "author_model": author_model,
        "executor_model": executor_model,
    }
    return errors, normalized


def resolve_operation(spec: dict[str, Any]) -> tuple[str, list[str]]:
    requested = str(spec["operation"])
    if requested != "auto":
        return requested, ["explicit_operation"]
    if spec["source_mode"] == "new":
        return "write", ["new_text_requires_architecture_before_draft"]
    defect_level = spec["structural_defects"]
    if defect_level == "local":
        return "refactor", ["local_defects_preserve_structure"]
    if defect_level == "systemic":
        if spec["preservation"]["status"] == "ready":
            return "recreate", ["systemic_defects_with_preservation_set"]
        return "review", ["systemic_defects_need_preservation_before_recreate"]
    return "review", ["unknown_or_clean_text_diagnose_before_edit"]


def resolve_profile(spec: dict[str, Any]) -> str:
    return expected_profile_for_document(str(spec["document_type"]))


def prose_layer(model: dict[str, str]) -> str:
    family = re.sub(r"[^a-z0-9]+", "", model["family"].casefold())
    version = " ".join(model["version"].casefold().split())
    if family == "unknown":
        return "none"
    if family in {"gpt", "openai", "openaigpt"}:
        return "operative" if version in {"5.6", "gpt-5.6", "gpt 5.6"} else "prior"
    if family in {"claude", "anthropic", "anthropicclaude"}:
        tagged = {"fable 5.1", "mythos 5.1", "fable 5", "mythos 5", "opus 5", "opus 4.8"}
        return "operative" if version in tagged else "prior"
    if family in {"gemini", "google", "googlegemini"}:
        return "operative" if re.fullmatch(r"(?:gemini\s*)?3(?:\.\d+)?(?:\s+flash)?", version) else "prior"
    if family in {"deepseek", "kimi"}:
        return "prior"
    return "none"


def narrative_layer(model: dict[str, str], profile: str) -> str:
    if profile != "narrative" or model["family"] == "unknown":
        return "none"
    family = re.sub(r"[^a-z0-9]+", "", model["family"].casefold())
    if family in {
        "claude",
        "anthropic",
        "anthropicclaude",
        "gpt",
        "openai",
        "openaigpt",
        "gemini",
        "google",
        "googlegemini",
        "deepseek",
        "kimi",
    }:
        return "prior"
    return "none"


def bounded_strategy(spec: dict[str, Any], operation: str) -> bool:
    return (
        not spec["sepia_requested"]
        and spec["scope"] in {"line", "passage"}
        and int(spec["length_chars"]) <= 500
        and spec["structural_defects"] in {"none", "local"}
        and operation in {"review", "refactor"}
    )


def build_plan(spec: dict[str, Any]) -> dict[str, Any]:
    errors, normalized = validate_spec(spec)
    if errors:
        return {"status": "invalid", "errors": errors}
    operation, operation_reasons = resolve_operation(normalized)
    profile = resolve_profile(normalized)
    preservation = normalized["preservation"]
    humanization_guard = build_humanization_guard(normalized["document_type"])
    if operation == "recreate" and preservation["status"] != "ready":
        return {
            "status": "blocked",
            "reason_codes": ["recreate_preservation_set_required"],
            "resolved_operation": operation,
            "humanization_profile": profile,
            "required_preservation_contract": {
                "actual_entries": True,
                "actual_source_text": True,
                "source_text_sha256": True,
                "coverage_for_absent_categories": True,
                "content_and_set_hashes": True,
            },
        }
    if (
        operation in {"refactor", "recreate"}
        and profile == "narrative"
        and normalized["voice_profile_status"] == "missing"
        and not normalized["voice_skill_explicit"]
    ):
        return {
            "status": "blocked",
            "reason_codes": ["narrative_voice_profile_required_before_edit"],
            "resolved_operation": operation,
            "humanization_profile": profile,
            "next_action": "derive a VOICE PROFILE from approved source passages, then rebuild the plan",
        }

    bounded = bounded_strategy(normalized, operation)
    if bounded:
        language = normalized["language"]
        if operation == "review":
            owner = "dircreative"
            scenario_id = (
                "human_language_diagnosis"
                if language in {"zh", "mixed"}
                else "bounded_english_human_language"
            )
            mode = "studio" if language in {"zh", "mixed"} else "fast"
        elif language == "en":
            owner = "dircreative"
            scenario_id = "bounded_english_human_language"
            mode = "fast"
        elif normalized["bounded_preference"] == "fidelity":
            owner = "de-AI-writing"
            scenario_id = "bounded_fidelity_revision"
            mode = "fast"
        else:
            owner = "shuorenhua"
            scenario_id = "human_language_revision"
            mode = "studio"
        provider_steps = [
            {
                "order": 1,
                "scenario_id": scenario_id,
                "provider": owner,
                "mode": mode,
                "route_id": "copy_revision" if mode == "fast" else "film_development",
                "operation": operation,
                "authority": "diagnostic_only" if operation == "review" else "bounded_edit",
                "diagnosis_before_edit": operation == "refactor",
                "accepted_findings_required_for_edit": operation == "refactor",
                **(
                    {"validator": "humanizer-zh"}
                    if operation == "review" and language in {"zh", "mixed"}
                    else {}
                ),
            }
        ]
        if (
            operation == "refactor"
            and normalized["validation_required"]
            and language in {"zh", "mixed"}
        ):
            provider_steps.append(
                {
                    "order": 2,
                    "scenario_id": "human_language_diagnosis",
                    "provider": "dircreative",
                    "validator": "humanizer-zh",
                    "mode": "studio",
                    "route_id": "film_development",
                    "operation": "review",
                    "authority": "diagnostic_only",
                    "condition": "run after the bounded edit; report remaining clusters only",
                }
            )
        pass_order = (
            ["source_lock", "cluster_diagnosis", "stop_without_edit"]
            if operation == "review"
            else [
                "source_lock",
                "cluster_diagnosis",
                "finding_acceptance",
                "bounded_revision",
                "protected_content_diff",
                "overcorrection_check",
            ]
        )
        strategy = "bounded_human_language"
        reference_pack: list[str] = []
    else:
        sepia_common = {
            "scenario_id": "sepia_humanization",
            "provider": "sepia",
            "mode": "studio",
            "route_id": "film_development",
            "humanization_profile": profile,
            "document_type": normalized["document_type"],
            "humanization_guard_sha256": humanization_guard["guard_sha256"],
        }
        if operation in {"refactor", "recreate"}:
            diagnosis_step = {
                **sepia_common,
                "order": 1,
                "operation": "review",
                "target_operation": operation,
                "authority": "diagnostic_only",
                "output_required": "content_addressed_humanization_diagnosis",
            }
            edit_step = {
                **sepia_common,
                "order": 2,
                "operation": operation,
                "authority": "pending_evidence_bound_edit",
                "requires": [
                    "humanization_diagnosis",
                    "accepted_finding_ids",
                    "humanization_calibration",
                    "source_bound_preservation_baseline",
                ],
            }
            if preservation["status"] == "ready":
                edit_step.update(
                    {
                        "preservation_set_sha256": preservation["set_sha256"],
                        "source_text_sha256": preservation["source_text_sha256"],
                    }
                )
            provider_steps = [diagnosis_step, edit_step]
        else:
            provider_steps = [
                {
                    **sepia_common,
                    "order": 1,
                    "operation": operation,
                    "authority": "diagnostic_only" if operation == "review" else "new_draft",
                }
            ]
        if operation != "review" and normalized["language"] in {"zh", "mixed"}:
            provider_steps.append(
                {
                    "order": len(provider_steps) + 1,
                    "scenario_id": "human_language_revision",
                    "provider": "shuorenhua",
                    "mode": "studio",
                    "route_id": "film_development",
                    "operation": "refactor",
                    "authority": "conditional_sentence_layer_only",
                    "condition": (
                        "run only when Sepia quotes a remaining Chinese sentence-layer cluster; "
                        "do not revisit architecture, dialogue, names, or protected spans"
                    ),
                }
            )
        if normalized["validation_required"] and normalized["language"] in {"zh", "mixed"}:
            provider_steps.append(
                {
                    "order": len(provider_steps) + 1,
                    "scenario_id": "human_language_diagnosis",
                    "provider": "dircreative",
                    "validator": "humanizer-zh",
                    "mode": "studio",
                    "route_id": "film_development",
                    "operation": "review",
                    "authority": "diagnostic_only",
                    "condition": "validate the final text without rewriting it",
                }
            )
        pass_order = (
            ["source_and_fact_lock", "domain_and_architecture", "draft", "discourse", "style", "overcorrection_check"]
            if operation == "write"
            else ["source_and_fact_lock", "full_diagnosis", "stop_without_edit"]
            if operation == "review"
            else [
                "source_and_fact_lock",
                "full_diagnosis",
                "architecture_or_domain",
                "discourse",
                "style",
                "overcorrection_check",
            ]
        )
        strategy = "sepia_layered_humanization"
        reference_pack = REFERENCE_PACKS[profile]

    author_model = normalized["author_model"]
    executor_model = normalized["executor_model"]
    return {
        "status": "ready",
        "target_id": normalized["target_id"],
        "strategy": strategy,
        "resolved_operation": operation,
        "operation_reasons": operation_reasons,
        "humanization_profile": profile,
        "provider_steps": provider_steps,
        "reference_pack": reference_pack,
        "pass_order": pass_order,
        "diagnosis_contract": {
            "separate_passes_by_layer": True,
            "short_quote_required_for_each_finding": True,
            "single_hit_is_not_a_cluster": True,
            "authorship_probability_forbidden": True,
            "combined_ai_score_forbidden": True,
            "deepest_confirmed_layer_sets_edit_depth": True,
            "accepted_finding_ids_required_before_edit": operation in {"refactor", "recreate"},
            "unconfirmed_layers_remain_unchanged": True,
            "edit_selector_requires_diagnosis_hash": operation in {"refactor", "recreate"},
        },
        "required_edit_inputs": (
            [
                "content-addressed diagnosis with source-bound quotes",
                "accepted finding IDs",
                "voice/venue/domain calibration evidence",
                "source-bound protected-content baseline",
            ]
            if operation in {"refactor", "recreate"}
            else []
        ),
        "model_identity": {
            "inference_from_prose_forbidden": True,
            "author": {
                **author_model,
                "narrative_layer": narrative_layer(author_model, profile),
                "prose_layer": prose_layer(author_model),
            },
            "executor": {
                **executor_model,
                "narrative_layer": narrative_layer(executor_model, profile),
                "prose_layer": prose_layer(executor_model),
            },
        },
        "calibration": {
            "target": "genre_and_venue_band",
            "single_hit_is_not_failure": True,
            "cluster_before_rewrite": True,
            "select_moves_instead_of_accumulating": True,
            "interventions_derived_from_confirmed_findings": True,
            "corpus_markers_are_not_generation_requirements": True,
            "leave_slack": True,
            "forced_informality_forbidden": True,
            "invented_imperfections_forbidden": True,
            "specificity_requires_source": True,
        },
        "voice_and_venue": {
            "voice_profile_status": normalized["voice_profile_status"],
            "voice_skill_explicit": normalized["voice_skill_explicit"],
            "voice_skill_implicit_injection_forbidden": True,
            "venue_corpus_status": normalized["venue_corpus_status"],
            "sample_recent_human_artifacts": (
                "2-3" if normalized["text_kind"] != "narrative" else "not_required"
            ),
            "screenplay_genre_guard": normalized["document_type"] == "screenplay",
            "narrative_corpus_guard": normalized["document_type"] in NARRATIVE_DOCUMENTS,
        },
        "humanization_guard": humanization_guard,
        "preservation": preservation,
        "user_adjustments": [
            "operation: review / refactor / recreate / write",
            "depth: bounded / layered",
            "target register or venue",
            "VOICE PROFILE and protected spans",
            "which findings to accept",
            "how much structural change is allowed",
        ],
        "evidence_boundary": {
            "manual_plan_is_not_authorship_detector": True,
            "measured_association_is_not_intervention_proof": True,
            "preservation_hash_proves_binding_not_semantic_completeness": True,
            "source_to_preservation_semantic_readback_required": operation == "recreate",
            "quality_requires_readback": True,
        },
    }


def self_test() -> list[str]:
    failures: list[str] = []
    source_text = "版本号为 0.7.1。\n这份说明用于准确说明实际改动。"
    entries = [
        {
            "entry_id": "FACT-001",
            "kind": "fact",
            "text": "版本号为 0.7.1。",
            "text_sha256": hashlib.sha256("版本号为 0.7.1。".encode("utf-8")).hexdigest(),
            "evidence_quote": "版本号为 0.7.1。",
            "evidence_start": source_text.index("版本号为 0.7.1。"),
            "evidence_end": source_text.index("版本号为 0.7.1。")
            + len("版本号为 0.7.1。"),
        },
        {
            "entry_id": "INTENT-001",
            "kind": "intent",
            "text": "准确说明实际改动。",
            "text_sha256": hashlib.sha256("准确说明实际改动。".encode("utf-8")).hexdigest(),
            "evidence_quote": "准确说明实际改动",
            "evidence_start": source_text.index("准确说明实际改动"),
            "evidence_end": source_text.index("准确说明实际改动")
            + len("准确说明实际改动"),
        },
    ]
    preservation_payload = {
        "status": "ready",
        "set_id": "PRESERVE-001",
        "source_text": source_text,
        "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "coverage": {
            "facts": "covered",
            "claims": "not_present",
            "intent": "covered",
            "quotations": "not_present",
            "dialogue": "not_present",
            "protected_spans": "not_present",
        },
        "entries": entries,
    }
    preservation = {
        **preservation_payload,
        "set_sha256": canonical_sha256(preservation_payload),
    }
    base = {
        "schema_version": "1.0",
        "target_id": "TEXT-001",
        "operation": "auto",
        "text_kind": "professional",
        "document_type": "report",
        "language": "zh",
        "scope": "passage",
        "length_chars": 180,
        "structural_defects": "local",
        "source_mode": "existing",
        "voice_profile_status": "locked",
        "venue_corpus_status": "available",
        "sepia_requested": False,
        "validation_required": True,
        "voice_skill_explicit": False,
        "bounded_preference": "auto",
        "preservation": preservation,
        "author_model": {"family": "unknown", "version": "unknown", "source": "unknown"},
        "executor_model": {"family": "OpenAI GPT", "version": "5.6", "source": "system"},
    }
    bounded = build_plan(base)
    if bounded.get("strategy") != "bounded_human_language" or any(
        item.get("provider") == "sepia" for item in bounded.get("provider_steps", [])
    ):
        failures.append("bounded Chinese revision over-routed to Sepia")

    narrative = build_plan(
        {
            **base,
            "target_id": "SCRIPT-001",
            "text_kind": "narrative",
            "document_type": "screenplay",
            "scope": "document",
            "length_chars": 8000,
            "operation": "refactor",
            "structural_defects": "systemic",
            "sepia_requested": True,
        }
    )
    if (
        narrative.get("strategy") != "sepia_layered_humanization"
        or narrative.get("humanization_profile") != "narrative"
        or narrative.get("provider_steps", [{}])[0].get("provider") != "sepia"
        or "direct_reader_address"
        not in narrative.get("humanization_guard", {}).get("forbidden_auto_moves", [])
    ):
        failures.append("narrative Sepia plan lost screenplay calibration")

    release_review = build_plan(
        {
            **base,
            "target_id": "RELEASE-001",
            "document_type": "release_notes",
            "scope": "document",
            "length_chars": 1600,
            "operation": "review",
            "sepia_requested": True,
        }
    )
    if (
        release_review.get("humanization_profile") != "release_notes"
        or "references/domains/release-notes.md" not in release_review.get("reference_pack", [])
        or release_review.get("provider_steps", [{}])[0].get("authority") != "diagnostic_only"
    ):
        failures.append("professional Sepia review lost domain or no-edit boundary")

    blocked = build_plan(
        {
            **base,
            "operation": "recreate",
            "scope": "document",
            "length_chars": 1200,
            "sepia_requested": True,
            "preservation": {
                "status": "missing",
                "set_id": None,
                "source_text": None,
                "source_text_sha256": None,
                "coverage": {
                    field: "not_present" for field in PRESERVATION_COVERAGE_FIELDS
                },
                "entries": [],
                "set_sha256": None,
            },
        }
    )
    if blocked.get("status") != "blocked" or "recreate_preservation_set_required" not in blocked.get(
        "reason_codes", []
    ):
        failures.append("recreate did not require a preservation set")

    unknown = build_plan(base)
    if unknown.get("model_identity", {}).get("author", {}).get("prose_layer") != "none":
        failures.append("unknown author model was inferred from prose")
    if unknown.get("model_identity", {}).get("executor", {}).get("prose_layer") != "operative":
        failures.append("known GPT-5.6 executor layer was not marked operative")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a layered DIRcreative humanization plan.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    if args.command == "self-test":
        failures = self_test()
        print(json.dumps({"status": "pass" if not failures else "fail", "failures": failures}, indent=2))
        return 0 if not failures else 1
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 2
    plan = build_plan(spec)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan.get("status") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
