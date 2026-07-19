#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_VIEWPOINTS = {
    "user",
    "professional_film_expert",
    "product_manager",
    "skill_developer",
    "code_researcher",
}
REQUIRED_FAILURE_IDS = {
    "story_development_skipped",
    "script_depth_insufficient",
    "storyboard_information_density_too_low",
    "material_selection_missing",
    "community_recipe_overfit",
    "thread_control_incomplete",
    "plausibility_over_verification",
}


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists() and path.startswith("skills/") and path.endswith("/SKILL.md"):
        target = target.with_name("INTERNAL_SKILL.md")
    return target.read_text(encoding="utf-8")


def load_yaml(path: str) -> Any:
    proc = run(
        [
            "ruby",
            "-e",
            "require 'yaml'; require 'json'; data = YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], aliases: true); puts JSON.generate(data)",
            str(ROOT / path),
        ]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"failed to parse {path}: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def has_all(text: str, terms: list[str]) -> tuple[bool, list[str]]:
    missing = [term for term in terms if term not in text]
    return not missing, missing


def main() -> int:
    failures: list[str] = []
    review = read("docs/film-preproduction/council-adversarial-review.md")
    studio_route = read("skills/dircreative/routes/studio-development.md")
    routing_policy = read("skills/dircreative/runtime/routing-policy.yaml")
    runbook = read("docs/film-preproduction/live-chat-acceptance-runbook.md")
    rehearsal = read("examples/live-acceptance-rehearsal/01-chat-transcript.md")
    taxonomy_text = read("docs/film-preproduction/qa/failure-taxonomy.yaml")
    retry = read("docs/film-preproduction/qa/retry-rules.md")
    community = read("docs/film-preproduction/research/ai-video-prompt-community-lessons.md")
    prompt_discipline = read("docs/film-preproduction/production-prompt-discipline.md")
    objective = load_yaml("tests/fixtures/runtime/runs/objective-requirement-audit-2026-06-06.yaml")
    template = load_yaml("docs/film-preproduction/templates/live-user-acceptance.template.yaml")

    review_ok, missing_review = has_all(
        review,
        [
            "Use council review when the workflow could plausibly pass validation while still failing the user.",
            "User Viewpoint",
            "Professional Film Expert Viewpoint",
            "Product Manager Viewpoint",
            "Skill Developer Viewpoint",
            "Code Researcher Viewpoint",
            "Position:",
            "Blocking risk:",
            "Smallest correction:",
            "Adopt/reject:",
            "strongest dissent",
            "smallest repo change",
            "OBJECTIVE_COMPLETE",
            "External community and platform research is allowed only as input to this council",
        ],
    )
    if not review_ok:
        failures.append("council review doc missing terms: " + ", ".join(missing_review))

    route_ok, missing_route = has_all(
        studio_route + "\n" + routing_policy,
        [
            "council-adversarial-review.md",
            "at most one independent critical pass",
            "external_gates_only_for_material_decisions: true",
        ],
    )
    if not route_ok:
        failures.append("Studio route missing bounded critical-review contract: " + ", ".join(missing_route))

    subskill_failures = []
    for path in [
        "skills/dircreative/story-development/SKILL.md",
        "skills/dircreative/script-treatment/SKILL.md",
        "skills/dircreative/shot-design/SKILL.md",
        "skills/dircreative/image-prompt-compiler/SKILL.md",
    ]:
        if "council-adversarial-review.md" not in read(path):
            subskill_failures.append(path)
    if subskill_failures:
        failures.append("sub-skills missing council knowledge: " + ", ".join(subskill_failures))

    for term in ["反驳型议会审核", "用户视角", "影视专家视角", "产品经理视角", "Skill 开发者视角", "代码研究员视角"]:
        if term not in runbook or term not in rehearsal:
            failures.append(f"live acceptance chat surface missing council term: {term}")

    chat_evidence = template.get("chat_evidence", {})
    council = chat_evidence.get("council_adversarial_review", {})
    accepted_scope = template.get("accepted_scope", {})
    if set(council.get("viewpoints", [])) != REQUIRED_VIEWPOINTS:
        failures.append("live acceptance template council viewpoints mismatch")
    if council.get("triggered") is not False:
        failures.append("live acceptance template must start with council.triggered false")
    if "council_adversarial_review_boundary" not in accepted_scope.get("checklist", []):
        failures.append("live acceptance template missing council accepted scope item")
    if template.get("qa_gate", {}).get("status") != "needs_user":
        failures.append("live acceptance template must keep qa_gate needs_user")

    taxonomy_ids = {line.strip().removeprefix("- id: ").strip() for line in taxonomy_text.splitlines() if line.strip().startswith("- id: ")}
    missing_failure_ids = sorted(REQUIRED_FAILURE_IDS - taxonomy_ids)
    if missing_failure_ids:
        failures.append("failure taxonomy missing council-related IDs: " + ", ".join(missing_failure_ids))
    missing_retry_ids = sorted(failure_id for failure_id in REQUIRED_FAILURE_IDS if failure_id not in retry)
    if missing_retry_ids:
        failures.append("retry rules missing council-related IDs: " + ", ".join(missing_retry_ids))

    research_ok, missing_research = has_all(
        community + "\n" + prompt_discipline,
        [
            "weak community signals",
            "Do not add a Higgsfield MCP",
            "Use community recipes only as reusable structure",
            "community_recipe_overfit",
            "falsifiable QA criteria",
        ],
    )
    if not research_ok:
        failures.append("external research boundary missing terms: " + ", ".join(missing_research))

    requirement_rows = objective.get("run", {}).get("requirement_matrix", [])
    council_rows = [row for row in requirement_rows if "council adversarial review" in row.get("requirement", "")]
    if not council_rows:
        failures.append("objective receipt missing council adversarial requirement")
    elif council_rows[0].get("status") != "satisfied_for_technical_readiness":
        failures.append("objective receipt council requirement status is not satisfied_for_technical_readiness")
    standard = objective.get("run", {}).get("authoritative_completion_standard", {})
    if standard.get("current_result") != "OBJECTIVE_COMPLETE: NO":
        failures.append("objective receipt must preserve OBJECTIVE_COMPLETE: NO")

    print("DIRcreative Council Audit")
    print("=" * 72)
    print(f"viewpoint_count: {len(council.get('viewpoints', []))}")
    print(f"required_viewpoints_present: {str(set(council.get('viewpoints', [])) == REQUIRED_VIEWPOINTS).lower()}")
    print(f"council_trigger_surface_present: {str('反驳型议会审核' in runbook and '反驳型议会审核' in rehearsal).lower()}")
    print(f"smallest_change_rule_present: {str('smallest repo change' in review).lower()}")
    print(f"external_research_boundary_present: {str('weak community signals' in community and 'Do not add a Higgsfield MCP' in community).lower()}")
    print(f"failure_ids_present: {str(not missing_failure_ids and not missing_retry_ids).lower()}")
    print(f"objective_complete: {standard.get('current_result', '')}")
    if failures:
        print("COUNCIL_AUDIT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("COUNCIL_AUDIT: PASS")
    print("NOTE: Council audit proves technical readiness only; live user acceptance is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
