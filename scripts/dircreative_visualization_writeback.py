#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from dircreative_state_audit import canonical_authorization_scope, load_state as load_runtime_state, validate_state
from dircreative_visualization_spec import load_document, validate_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs/film-preproduction/schemas/chat-visualization-writeback.schema.json"
FIXTURE_ROOT = ROOT / "tests/fixtures/chat-visualization"
CSS_PATH = ROOT / "skills/dircreative/assets/visualizations/decision-surface.css"
STATUS_LABELS = {
    "approved": "已记录",
    "needs_revision": "待修改",
    "pending": "待处理",
    "skipped_with_risk": "带风险跳过",
    "ready": "可进入",
    "blocked": "仍阻塞",
    "stay": "停留当前阶段",
}
CHANGE_LABELS = {"created": "新建", "updated": "更新", "preserved": "保留"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_relative(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"path must stay relative to project root: {value}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {value}") from exc
    return candidate


def validate_inherited_generation_authorization(
    receipt: dict[str, Any],
    project_root: Path,
    spec: dict[str, Any] | None,
) -> list[str]:
    """Bind an adopt-and-generate receipt to the current state authority.

    The state audit remains the owner of confirmation and revocation semantics;
    this adapter only proves that the requested spatial export is inside that
    already-current authority. It cannot independently identify the user.
    """
    failures: list[str] = []
    authorization = receipt.get("generation_authorization")
    request = receipt.get("generation_request")
    if not isinstance(authorization, dict) or not isinstance(request, dict):
        return ["adopt_and_generate requires a state-bound authorization and generation request"]
    try:
        state_path = resolve_relative(project_root, str(authorization.get("state_path", "")))
        snapshot_path = resolve_relative(project_root, str(authorization.get("thread_snapshot_path", "")))
    except ValueError as exc:
        return [str(exc)]
    if not state_path.is_file() or sha256(state_path) != authorization.get("state_sha256"):
        failures.append("generation authorization state hash mismatch")
        return failures
    if not snapshot_path.is_file() or sha256(snapshot_path) != authorization.get("thread_snapshot_sha256"):
        failures.append("generation authorization thread snapshot hash mismatch")
        return failures
    try:
        state = load_runtime_state(state_path)
        thread_snapshot = load_runtime_state(snapshot_path)
    except ValueError as exc:
        return [f"generation authorization evidence is unreadable: {exc}"]
    state_findings, _ = validate_state(project_root, state, thread_snapshot=thread_snapshot)
    blocking_findings = [
        finding
        for finding in state_findings
        if finding.lane == "current" and finding.severity == "P0" and finding.code != "live_host_attestation_required"
    ]
    if blocking_findings:
        failures.append("generation authorization state integrity failed")
        return failures
    record_id = authorization.get("authorization_id")
    records = {
        record.get("record_id"): record
        for record in state.get("records", [])
        if isinstance(record, dict) and isinstance(record.get("record_id"), str)
    }
    record = records.get(record_id)
    payload = record.get("generation_authorization") if isinstance(record, dict) else None
    current_ids = state.get("current", {}).get("generation_authorization_ids", [])
    if (
        not isinstance(record, dict)
        or record_id not in current_ids
        or record.get("kind") != "generation_authorization"
        or record.get("lifecycle") != "active"
        or record.get("revision") != authorization.get("record_revision")
        or not isinstance(payload, dict)
    ):
        failures.append("generation authorization record is not current")
        return failures
    canonical_scope = canonical_authorization_scope(payload)
    if payload.get("scope_hash") != canonical_scope or authorization.get("scope_hash") != canonical_scope:
        failures.append("generation authorization scope hash mismatch")
    if payload.get("status") != "active":
        failures.append("generation authorization is not active")
    controller_check = authorization.get("controller_check")
    if not isinstance(controller_check, dict) or any(
        controller_check.get(key) != payload.get(key)
        for key in ("thread_id", "confirmation_id", "authorized_by", "authorized_by_type")
    ):
        failures.append("generation authorization controller check is not bound to the authority record")
    spatial = spec.get("presentation", {}).get("spatial_scene", {}) if isinstance(spec, dict) else {}
    if not isinstance(spatial, dict) or request.get("scene_id") != spatial.get("scene_id"):
        failures.append("generation request scene does not match adopted spatial scene")
    cameras = spatial.get("cameras") if isinstance(spatial, dict) else None
    camera_shots = {camera.get("shot_id") for camera in cameras if isinstance(camera, dict)} if isinstance(cameras, list) else set()
    request_shots = request.get("shot_ids") if isinstance(request.get("shot_ids"), list) else []
    if not camera_shots or not request_shots or not set(request_shots).issubset(camera_shots):
        failures.append("generation request shots are not current adopted spatial shots")
    request_assets = request.get("asset_ids") if isinstance(request.get("asset_ids"), list) else []
    if not request_assets or request.get("scene_id") not in request_assets:
        failures.append("generation request must bind the adopted scene as an authorized asset")
    if not set(request_assets).issubset(set(payload.get("asset_ids", []))):
        failures.append("generation request assets exceed authorization scope")
    if request.get("expected_output_kind") not in set(payload.get("expected_output_kinds", [])):
        failures.append("generation request output kind exceeds authorization scope")
    if request.get("model_id") not in set(payload.get("model_ids", [])):
        failures.append("generation request model exceeds authorization scope")
    return failures


def schema_errors(receipt: Any) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if os.environ.get("DIRCREATIVE_FORCE_BUILTIN_SCHEMA_VALIDATOR"):
        from dircreative_state_audit import _builtin_schema_errors

        return [f"schema:{failure}" for failure in _builtin_schema_errors(receipt, schema, schema, "$")]
    try:
        import jsonschema
    except ImportError:
        from dircreative_state_audit import _builtin_schema_errors

        return [f"schema:{failure}" for failure in _builtin_schema_errors(receipt, schema, schema, "$")]
    validator = jsonschema.Draft202012Validator(schema)
    failures = []
    for error in sorted(validator.iter_errors(receipt), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        failures.append(f"schema:{location}: {error.message}")
    return failures


def semantic_errors(receipt: Any, project_root: Path) -> list[str]:
    if not isinstance(receipt, dict):
        return ["receipt must be an object"]
    failures: list[str] = []
    context = receipt.get("execution_context")
    receipt_version = receipt.get("receipt_version")
    interaction_mode = receipt.get("interaction_mode") if isinstance(receipt_version, str) and receipt_version.endswith("@1.1") else "decision"
    controller = receipt.get("controller", {})
    expected_owner = "dircreative" if context == "standalone_chat" else "ad-creative-orchestrator"
    expected_facing = context == "standalone_chat"
    if controller.get("write_owner") != expected_owner or controller.get("recorded_by") != expected_owner:
        failures.append(f"{context} writeback must be owned and recorded by {expected_owner}")
    if controller.get("user_facing") is not expected_facing:
        failures.append(f"{context} user_facing must be {str(expected_facing).lower()}")

    source = receipt.get("source_view", {})
    try:
        spec_path = resolve_relative(project_root, str(source.get("spec_path", "")))
    except ValueError as exc:
        failures.append(str(exc))
        spec_path = None
    spec: dict[str, Any] | None = None
    if spec_path is not None:
        if not spec_path.is_file():
            failures.append(f"source visualization spec is missing: {source.get('spec_path')}")
        elif sha256(spec_path) != source.get("spec_sha256"):
            failures.append("source visualization spec hash mismatch")
        else:
            loaded = load_document(spec_path)
            if isinstance(loaded, dict):
                spec = loaded
                spec_failures = validate_document(spec, project_root=project_root)
                if spec_failures:
                    failures.append("source visualization spec is invalid: " + "; ".join(spec_failures))
            else:
                failures.append("source visualization spec must be an object")

    intent = receipt.get("conversation_intent", {})
    gate_result = receipt.get("gate_result", {})
    if spec is not None:
        if source.get("view_id") != spec.get("view_id"):
            failures.append("source view_id does not match visualization spec")
        gate = spec.get("stage_gate", {})
        if interaction_mode == "decision":
            if source.get("gate_id") != gate.get("id"):
                failures.append("source gate_id does not match visualization spec")
        elif source.get("gate_id") is not None:
            failures.append("gate-less adoption receipt must not bind a stage_gate")
        if spec.get("execution_context") != context:
            failures.append("writeback execution_context does not match visualization spec")
        if spec.get("write_boundary", {}).get("write_owner") != expected_owner:
            failures.append("visualization write owner does not match writeback controller")
        if interaction_mode != "decision" and spec.get("interaction_mode") != interaction_mode:
            failures.append("writeback interaction_mode does not match visualization spec")
        actions = {
            item.get("id"): item
            for item in spec.get("interactions", {}).get("actions", [])
            if isinstance(item, dict)
        }
        action = actions.get(intent.get("action_id"))
        if action is None:
            failures.append("conversation intent action_id is absent from source visualization")
        else:
            if intent.get("action_kind") != action.get("kind"):
                failures.append("conversation intent action_kind does not match source action")
            if interaction_mode == "decision" and action.get("target_gate_id") != source.get("gate_id"):
                failures.append("source action does not target the receipt gate")
        option_ids = {
            item.get("id")
            for item in spec.get("presentation", {}).get("options", [])
            if isinstance(item, dict)
        }
        selected = intent.get("selected_option_id")
        if selected is not None and selected not in option_ids:
            failures.append("selected option is absent from source visualization")

    action_kind = intent.get("action_kind")
    selected = intent.get("selected_option_id")
    result_selected = gate_result.get("selected_option_id")
    if interaction_mode == "decision" and action_kind == "submit_selection":
        if not selected or selected != result_selected or gate_result.get("status") != "approved":
            failures.append("submit_selection requires the same selected option and an approved gate result")
    elif interaction_mode == "decision" and action_kind in {"request_revision", "request_mix"}:
        if gate_result.get("status") != "needs_revision":
            failures.append(f"{action_kind} requires needs_revision gate result")
    if interaction_mode == "decision" and gate_result.get("status") == "approved" and gate_result.get("conflict") is not None:
        failures.append("approved gate result cannot carry a conflict")
    if interaction_mode == "decision" and gate_result.get("status") != "approved" and receipt.get("next_stage", {}).get("status") == "ready":
        failures.append("next stage cannot be ready while the current gate is unresolved")

    if interaction_mode in {"adopt", "adopt_and_generate"}:
        if intent.get("decision_source") != "real_user" or not str(intent.get("submitted_text", "")).strip() or not intent.get("user_confirmation_id"):
            failures.append("adoption requires explicit real-user conversation intent")
        adoption = receipt.get("adoption_evidence", {})
        source_refs = adoption.get("source_refs") if isinstance(adoption, dict) else None
        if not isinstance(source_refs, list) or not source_refs:
            failures.append("adoption requires source binding evidence")
        elif spec is not None:
            spatial = spec.get("presentation", {}).get("spatial_scene", {})
            expected_refs = set(spatial.get("source_refs", [])) if isinstance(spatial, dict) else set()
            if expected_refs and not set(source_refs).issubset(expected_refs):
                failures.append("adoption source_refs are not bound to the current spatial scene")
            for source_ref in source_refs:
                if not isinstance(source_ref, str) or "#/" not in source_ref:
                    failures.append("adoption source_refs must be JSON-pointer bindings")
        if not isinstance(adoption, dict) or not str(adoption.get("source_revision", "")).strip():
            failures.append("adoption requires source revision evidence")
        elif spec is not None:
            spatial = spec.get("presentation", {}).get("spatial_scene", {})
            if isinstance(spatial, dict) and spatial.get("revision") is not None and adoption.get("source_revision") != spatial.get("revision"):
                failures.append("adoption source_revision does not match the current spatial scene")
        if interaction_mode == "adopt_and_generate":
            authorization = receipt.get("generation_authorization", {})
            if not isinstance(authorization, dict) or authorization.get("status") != "inherited":
                failures.append("adopt_and_generate must inherit an existing generation authorization")
            failures.extend(validate_inherited_generation_authorization(receipt, project_root, spec))
        elif receipt.get("generation_authorization") is not None:
            failures.append("adopt must not create or attach generation authorization")

    seen_artifacts: set[str] = set()
    write_records: dict[str, dict[str, Any]] = {}
    for index, artifact in enumerate(receipt.get("artifact_writes", [])):
        if not isinstance(artifact, dict):
            continue
        artifact_id = artifact.get("artifact_id")
        if artifact_id in seen_artifacts:
            failures.append(f"duplicate artifact write: {artifact_id}")
        seen_artifacts.add(str(artifact_id))
        write_records[str(artifact_id)] = artifact
        try:
            artifact_path = resolve_relative(project_root, str(artifact.get("path", "")))
        except ValueError as exc:
            failures.append(str(exc))
            continue
        if not artifact_path.is_file():
            failures.append(f"written artifact is missing: {artifact.get('path')}")
            continue
        if artifact_path.is_symlink():
            failures.append(f"written artifact must not be a symlink: {artifact.get('path')}")
            continue
        if sha256(artifact_path) != artifact.get("after_sha256"):
            failures.append(f"written artifact hash mismatch: {artifact.get('path')}")
        change_kind = artifact.get("change_kind")
        before = artifact.get("before_sha256")
        after = artifact.get("after_sha256")
        if change_kind == "created" and before is not None:
            failures.append(f"created artifact must use null before_sha256: {artifact_id}")
        if change_kind == "updated" and (before is None or before == after):
            failures.append(f"updated artifact requires distinct before/after hashes: {artifact_id}")
        if change_kind == "preserved" and before != after:
            failures.append(f"preserved artifact requires equal before/after hashes: {artifact_id}")

    if interaction_mode in {"adopt", "adopt_and_generate"}:
        adoption = receipt.get("adoption_evidence", {})
        evidence_refs = adoption.get("write_evidence_refs", []) if isinstance(adoption, dict) else []
        if not evidence_refs or not set(evidence_refs).issubset(seen_artifacts):
            failures.append("adoption requires write evidence that names written artifacts")
        spatial = spec.get("presentation", {}).get("spatial_scene", {}) if isinstance(spec, dict) else {}
        for artifact_id in evidence_refs:
            artifact = write_records.get(str(artifact_id), {})
            linkage = artifact.get("source_scene") if isinstance(artifact, dict) else None
            if not isinstance(linkage, dict) or not isinstance(spatial, dict) or any(
                linkage.get(key) != spatial.get(key)
                for key in ("scene_id", "scene_state_sha256")
            ) or linkage.get("revision") != adoption.get("source_revision") or set(linkage.get("source_refs", [])) != set(adoption.get("source_refs", [])):
                failures.append("adoption write evidence is not linked to the adopted scene revision")
                continue
            try:
                written = resolve_relative(project_root, str(artifact.get("path", "")))
                written_payload = load_runtime_state(written)
            except ValueError:
                failures.append("adoption write evidence is not readable JSON")
                continue
            if written_payload.get("source_scene") != linkage:
                failures.append("adoption write content is not linked to the adopted scene revision")

    lock_effects = receipt.get("lock_effects", {})
    if interaction_mode == "decision" and set(lock_effects.get("created", [])) & set(lock_effects.get("preserved", [])):
        failures.append("a lock cannot be both created and preserved")
    downstream = receipt.get("downstream_effects", {})
    categories = [set(downstream.get(name, [])) for name in ("stale", "preserved", "blocked")]
    if any(categories[i] & categories[j] for i in range(3) for j in range(i + 1, 3)):
        failures.append("a downstream artifact cannot be stale, preserved, and/or blocked at the same time")
    authority = receipt.get("authority", {})
    if interaction_mode == "decision" and authority.get("generation_authorized") is not False:
        failures.append("legacy visualization writeback cannot authorize generation")
    if interaction_mode == "adopt" and authority.get("generation_authorized") is not False:
        failures.append("adoption without generation must not authorize generation")
    if interaction_mode == "adopt_and_generate" and authority.get("generation_authorized") is not True:
        failures.append("adopt_and_generate must prove inherited generation authorization")
    return failures


def validate_receipt(receipt: Any, project_root: Path) -> list[str]:
    return schema_errors(receipt) + semantic_errors(receipt, project_root)


def seal_receipt(receipt: dict[str, Any], project_root: Path, output_value: str) -> Path:
    failures = validate_receipt(receipt, project_root)
    if failures:
        raise ValueError("invalid writeback receipt: " + "; ".join(failures))
    output = resolve_relative(project_root, output_value)
    relative = output.relative_to(project_root.resolve())
    if len(relative.parts) < 3 or relative.parts[:2] != (".dircreative", "runs"):
        raise ValueError("writeback receipt output must stay under .dircreative/runs/")
    if output.exists():
        raise ValueError(f"refusing to overwrite writeback receipt: {output_value}")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = output.parent / f".{output.name}.{os.getpid()}.tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, output)
        directory_fd = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def list_text(values: list[str], empty: str) -> str:
    return "、".join(values) if values else empty


def render_confirmation_fragment(receipt: dict[str, Any], project_root: Path) -> str:
    failures = validate_receipt(receipt, project_root)
    if failures:
        raise ValueError("invalid writeback receipt: " + "; ".join(failures))
    result = receipt.get("gate_result", {"status": "approved", "rationale": "已按你的明确意图写入当前修订。", "conflict": None})
    intent = receipt["conversation_intent"]
    downstream = receipt["downstream_effects"]
    next_stage = receipt["next_stage"]
    selected = intent.get("submitted_text")
    rows = [
        ("你的选择", selected),
        ("当前结果", STATUS_LABELS.get(result["status"], result["status"])),
        ("专业判断", result["rationale"]),
        ("接下来", f"进入{next_stage['label']}，状态：{STATUS_LABELS.get(next_stage['status'], next_stage['status'])}"),
    ]
    if downstream["preserved"]:
        rows.append(("会继续沿用", list_text(downstream["preserved"], "")))
    if downstream["stale"]:
        rows.append(("需要重新确认", list_text(downstream["stale"], "")))
    if downstream["blocked"]:
        rows.append(("暂时不能做", list_text(downstream["blocked"], "")))
    row_html = "".join(
        '<div class="dc-echo-row" role="row">'
        f'<span class="text-small" role="rowheader">{esc(label)}</span>'
        f'<span role="cell">{esc(value)}</span></div>'
        for label, value in rows
    )
    css = CSS_PATH.read_text(encoding="utf-8").strip()
    conflict = result.get("conflict")
    if receipt.get("interaction_mode") == "adopt_and_generate":
        status = f"你的选择已经确认。控制器会在既有授权范围内继续{next_stage['label']}。"
    else:
        status = f"你的选择已经确认。下一步先展示{next_stage['label']}内容，不会自动开始生成。"
    if conflict:
        status = f"当前未写入新的批准结果：{conflict}"
    spec_path = resolve_relative(project_root, receipt["source_view"]["spec_path"])
    source_spec = load_document(spec_path)
    stage_label = source_spec["view"]["customer_stage_label"]
    return (
        '<div data-dircreative-visual="confirmation-echo">\n'
        f'<style>\n{css}\n</style>\n'
        '<div class="dc-header"><div><span class="viz-badge">已确认你的选择</span> '
        f'<strong>{esc(stage_label)}</strong></div>'
        '<span class="text-small text-muted">可以继续</span></div>\n'
        f'<div class="card dc-confirmation-echo" role="table" aria-label="你的选择与下一步">{row_html}</div>\n'
        f'<div class="dc-status text-small" role="status">{esc(status)}</div>\n'
        '</div>\n'
    )


def self_test() -> list[str]:
    failures: list[str] = []
    valid_path = FIXTURE_ROOT / "valid-writeback-receipt.json"
    invalid_path = FIXTURE_ROOT / "invalid-writeback-stale-source.json"
    valid = load_document(valid_path)
    valid_failures = validate_receipt(valid, ROOT)
    if valid_failures:
        failures.append(f"valid receipt rejected: {valid_failures}")
    else:
        fragment = render_confirmation_fragment(valid, ROOT)
        for required in ("已确认你的选择", "你的选择", "专业判断", "接下来", "不会自动开始生成"):
            if required not in fragment:
                failures.append(f"confirmation echo missing: {required}")
        if "data-dc-action" in fragment or "sendFollowUpMessage" in fragment:
            failures.append("confirmation echo must not contain a new decision action")
    invalid = load_document(invalid_path)
    invalid_failures = validate_receipt(invalid, ROOT)
    if not any("source visualization spec hash mismatch" in item for item in invalid_failures):
        failures.append(f"stale source receipt was not rejected: {invalid_failures}")
    invalid_any_of = json.loads(json.dumps(valid))
    invalid_any_of["artifact_writes"][0]["before_sha256"] = True
    if not any("anyOf failed" in item or "is not valid under any" in item for item in schema_errors(invalid_any_of)):
        failures.append("invalid before_sha256 type bypassed schema anyOf validation")
    invalid_max_length = json.loads(json.dumps(valid))
    invalid_max_length["receipt_id"] = "x" * 161
    if not any("longer than 160" in item or "is too long" in item for item in schema_errors(invalid_max_length)):
        failures.append("oversized receipt_id bypassed schema maxLength validation")
    with tempfile.TemporaryDirectory(prefix="dircreative-writeback-") as tmp_value:
        tmp = Path(tmp_value)
        (tmp / "artifacts").mkdir()
        shutil.copy2(FIXTURE_ROOT / "valid-director-compare-inline.json", tmp / "source-spec.json")
        shutil.copy2(
            FIXTURE_ROOT / "writeback-project/artifacts/selected-concept.json",
            tmp / "artifacts/selected-concept.json",
        )
        portable = json.loads(json.dumps(valid))
        portable["source_view"]["spec_path"] = "source-spec.json"
        portable["source_view"]["spec_sha256"] = sha256(tmp / "source-spec.json")
        portable["artifact_writes"][0]["path"] = "artifacts/selected-concept.json"
        portable["artifact_writes"][0]["after_sha256"] = sha256(tmp / "artifacts/selected-concept.json")
        try:
            sealed = seal_receipt(portable, tmp, ".dircreative/runs/writeback-receipt.json")
            if not sealed.is_file() or load_document(sealed) != portable:
                failures.append("sealed receipt did not persist exact validated content")
            try:
                seal_receipt(portable, tmp, ".dircreative/runs/writeback-receipt.json")
                failures.append("seal receipt overwrote an existing receipt")
            except ValueError as exc:
                if "refusing to overwrite" not in str(exc):
                    failures.append(f"seal no-clobber failed for wrong reason: {exc}")
        except ValueError as exc:
            failures.append(f"valid receipt could not be sealed: {exc}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and render DIRcreative visualization writeback receipts.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("receipt")
    validate.add_argument("--project-root", default=str(ROOT))
    render = sub.add_parser("render-confirmation")
    render.add_argument("receipt")
    render.add_argument("--project-root", default=str(ROOT))
    render.add_argument("--output", required=True)
    seal = sub.add_parser("seal")
    seal.add_argument("receipt")
    seal.add_argument("--project-root", default=str(ROOT))
    seal.add_argument("--output", required=True, help="Relative path under .dircreative/runs/")
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "self-test":
        failures = self_test()
        print(f"CHAT_VISUALIZATION_WRITEBACK: {'PASS' if not failures else 'FAIL'}")
        for failure in failures:
            print(f"- {failure}")
        return 0 if not failures else 1
    root = Path(args.project_root).expanduser().resolve()
    receipt_path = Path(args.receipt)
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    receipt = load_document(receipt_path)
    failures = validate_receipt(receipt, root)
    if failures:
        print("CHAT_VISUALIZATION_WRITEBACK: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    if args.command == "seal":
        try:
            output = seal_receipt(receipt, root, args.output)
        except ValueError as exc:
            print("CHAT_VISUALIZATION_WRITEBACK: FAIL")
            print(f"- {exc}")
            return 1
        print(f"receipt: {output}")
    if args.command == "render-confirmation":
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_confirmation_fragment(receipt, root), encoding="utf-8")
        print(f"output: {output}")
    print("CHAT_VISUALIZATION_WRITEBACK: PASS")
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
