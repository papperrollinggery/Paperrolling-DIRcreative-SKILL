#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from dircreative_content_first_audit import audit_answer, case_map, load_payload


ROOT = Path(__file__).resolve().parents[1]


def parse_events(raw: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    events: list[dict[str, Any]] = []
    tool_items_by_id: dict[str, dict[str, Any]] = {}
    usage: dict[str, Any] = {}
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") not in {"reasoning", "agent_message", "error"}:
            item_id = str(item.get("id") or event.get("id") or len(tool_items_by_id))
            existing = tool_items_by_id.get(item_id)
            if existing is None or item.get("status") == "completed" or item.get("exit_code") is not None:
                tool_items_by_id[item_id] = item
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return events, list(tool_items_by_id.values()), usage


def event_error_messages(events: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    for event in events:
        candidates: list[object] = []
        if event.get("type") == "error":
            candidates.append(event.get("message"))
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "error":
            candidates.append(item.get("message"))
        error = event.get("error")
        if isinstance(error, dict):
            candidates.append(error.get("message"))
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip() and candidate not in messages:
                messages.append(candidate.strip())
    return messages


def command_text(item: dict[str, Any]) -> str:
    for key in ("command", "cmd", "input"):
        value = item.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return " ".join(str(part) for part in value)
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def build_command(
    codex_bin: str,
    workspace: Path,
    model: str,
    answer_path: Path,
    prompt: str,
) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--disable",
        "plugins",
        "--disable",
        "apps",
        "--disable",
        "multi_agent",
        "--sandbox",
        "read-only",
        "--cd",
        str(workspace),
        "--model",
        model,
        "--json",
        "--output-last-message",
        str(answer_path),
        prompt,
    ]


def self_test() -> int:
    sample = "\n".join(
        [
            json.dumps({"type": "item.completed", "item": {"type": "reasoning", "text": "x"}}),
            json.dumps({"type": "item.completed", "item": {"type": "command_execution", "command": "sed -n 1,40p ref.md"}}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "answer"}}),
            json.dumps({"type": "error", "message": "usage limit"}),
            json.dumps({"type": "turn.failed", "error": {"message": "usage limit"}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 20}}),
        ]
    )
    events, tools, usage = parse_events(sample)
    if len(events) != 6 or len(tools) != 1 or usage.get("output_tokens") != 20:
        raise AssertionError("live model event parser self-test failed")
    if event_error_messages(events) != ["usage limit"]:
        raise AssertionError("live model error diagnostics self-test failed")
    command = build_command("codex", Path("/tmp/work"), "gpt-5.6-sol", Path("/tmp/answer"), "$dircreative test")
    if "--ignore-user-config" not in command or "--sandbox" not in command or "read-only" not in command:
        raise AssertionError("live model command lost isolation controls")
    print("DIRCREATIVE_LIVE_MODEL_EVAL_SELF_TEST: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real isolated Codex forward evals against source DIRcreative.")
    parser.add_argument("--case", action="append", default=[], help="Case id; repeat or omit for all cases.")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--codex-bin", default=shutil.which("codex") or "codex")
    parser.add_argument("--codex-home", type=Path, help="Optional isolated CODEX_HOME containing valid auth.")
    parser.add_argument("--output-dir", type=Path, help="Directory for answers, JSONL events, and report.")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    payload = load_payload()
    cases = case_map()
    selected_ids = args.case or list(cases)
    unknown = [case_id for case_id in selected_ids if case_id not in cases]
    if unknown:
        print(f"unknown content-first cases: {', '.join(unknown)}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.resolve() if args.output_dir else Path(tempfile.mkdtemp(prefix="dircreative-live-eval-output-"))
    output_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if args.codex_home:
        env["CODEX_HOME"] = str(args.codex_home.resolve())

    failures: list[str] = []
    reports: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dircreative-live-eval-workspace-") as raw_workspace:
        workspace = Path(raw_workspace)
        skill_target = workspace / ".agents/skills/dircreative-candidate"
        install = subprocess.run(
            [sys.executable, str(ROOT / "scripts/install_local_skill.py"), "--target", str(skill_target)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
        if install.returncode != 0:
            print(install.stderr or install.stdout, file=sys.stderr)
            return 1
        candidate_skill = skill_target / "SKILL.md"
        candidate_text = candidate_skill.read_text(encoding="utf-8")
        candidate_text = candidate_text.replace("name: dircreative\n", "name: dircreative-candidate\n", 1)
        candidate_text = candidate_text.replace("$dircreative", "$dircreative-candidate")
        candidate_skill.write_text(candidate_text, encoding="utf-8")
        (workspace / "AGENTS.md").write_text(
            "# Isolated candidate evaluation\n\n"
            "When a request invokes `$dircreative-candidate`, read and follow "
            "`.agents/skills/dircreative-candidate/SKILL.md`. Resolve its relative paths inside that "
            "candidate directory. Never read or invoke any global `dircreative` installation under "
            "`.skillshub`, `.codex/skills`, or `.codex/dev-skills`. Return the requested creative answer; "
            "do not discuss this evaluation harness.\n",
            encoding="utf-8",
        )

        for case_id in selected_ids:
            case = cases[case_id]
            answer_path = output_dir / f"{case_id}.answer.md"
            events_path = output_dir / f"{case_id}.events.jsonl"
            request = case["request"].replace("$dircreative", "$dircreative-candidate", 1)
            command = build_command(args.codex_bin, workspace, args.model, answer_path, request)
            started = time.perf_counter()
            try:
                proc = subprocess.run(
                    command,
                    cwd=workspace,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=args.timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                failures.append(f"{case_id}: live model timeout")
                continue
            elapsed_seconds = round(time.perf_counter() - started, 3)
            events_path.write_text(proc.stdout, encoding="utf-8")
            events, tool_items, usage = parse_events(proc.stdout)
            if proc.returncode != 0 or not answer_path.is_file():
                event_diagnostics = " | ".join(event_error_messages(events))
                diagnostic = event_diagnostics or proc.stderr.strip()[-1600:] or "no diagnostic output"
                failures.append(f"{case_id}: codex exec failed with exit {proc.returncode}: {diagnostic}")
                continue
            answer = answer_path.read_text(encoding="utf-8")
            metrics, answer_errors = audit_answer(answer, case, payload["process_terms"])
            failures.extend(f"{case_id}: {error}" for error in answer_errors)

            if len(tool_items) > int(case["maximum_tool_calls"]):
                failures.append(f"{case_id}: tool calls {len(tool_items)} exceed {case['maximum_tool_calls']}")
            command_texts = [command_text(item) for item in tool_items]
            forbidden_commands = [
                blocked
                for blocked in payload["forbidden_pre_artifact_commands"]
                if any(blocked.casefold() in value.casefold() for value in command_texts)
            ]
            if forbidden_commands:
                failures.append(f"{case_id}: forbidden pre-artifact commands: {forbidden_commands}")
            global_skill_paths = [
                blocked
                for blocked in payload["forbidden_global_skill_paths"]
                if any(blocked.casefold() in value.casefold() for value in command_texts)
            ]
            candidate_used = any(
                ".agents/skills/dircreative-candidate/" in value
                for value in command_texts
            )
            if global_skill_paths:
                failures.append(f"{case_id}: global Skill path used: {global_skill_paths}")
            if not candidate_used:
                failures.append(f"{case_id}: repo-local candidate Skill was not read")
            reports.append(
                {
                    "case_id": case_id,
                    "model": args.model,
                    "elapsed_seconds": elapsed_seconds,
                    "answer_path": str(answer_path),
                    "events_path": str(events_path),
                    "event_count": len(events),
                    "tool_calls": len(tool_items),
                    "tool_types": [item.get("type") for item in tool_items],
                    "forbidden_commands": forbidden_commands,
                    "global_skill_paths": global_skill_paths,
                    "repo_local_candidate_used": candidate_used,
                    "usage": usage,
                    **metrics,
                }
            )

    report = {
        "status": "PASS" if not failures else "FAIL",
        "model": args.model,
        "runtime_boundary": "isolated repo-local source package; read-only ephemeral Codex exec; no global Skill update",
        "output_dir": str(output_dir),
        "cases": reports,
        "failures": failures,
    }
    (output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("DIRCREATIVE_LIVE_MODEL_EVAL: " + ("PASS" if not failures else "FAIL"))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
