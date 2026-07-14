# Live User Acceptance Gate

Verified: 2026-05-17

Purpose: define the only receipt that can close the active DIRcreative goal.

## Core Rule

Technical gates can prove readiness. They cannot prove user satisfaction.

The active goal can be marked complete only after a real user acceptance pass is recorded at `.dircreative/runs/live-user-acceptance.yaml` and `scripts/dircreative_goal_audit.py --require-installed` reports `GOAL_COMPLETE: YES`. Without that receipt, even a complete Goal autorun dry-run must remain `GOAL_COMPLETE: NO`.

## Required Acceptance Evidence

The receipt must prove that the user saw the actual chat-facing workflow, not only terminal output or hidden files.

Required evidence:

- the real user prompt used for the acceptance pass,
- observed chat stages,
- user decisions made in chat,
- council adversarial review evidence when the user raised story, script, storyboard, prompt, workflow, or generation-quality concerns,
- Codex thread orchestration evidence when any worker thread was used,
- Creative Production review evidence when it was used, including the review surface and DIRcreative receipt that owns generated candidate status,
- a short transcript summary,
- direct user feedback or acceptance statement,
- accepted scope checklist,
- unresolved blocker list,
- QA gate result.

## Required Accepted Scope

The accepted scope checklist must include every item below:

- `chat_first_flow`
- `director_room_collaboration`
- `professional_script`
- `dynamic_shot_design`
- `reference_pack_roles`
- `pre_generation_contracts`
- `image_prompt_summaries`
- `model_specific_video_prompts`
- `qa_retry_rules`
- `prompt_only_boundary`
- `assisted_generation_preflight`
- `installed_skill_behavior`
- `gstack_visual_dogfood`
- `council_adversarial_review_boundary`
- `thread_orchestration_cleanup`

## Not Enough To Close

These are not enough:

- `RELEASE_GATE: PASS` alone,
- generated visual dogfood pages alone,
- Creative Production widgets, generated candidates, review pages, local URLs, screenshots, or run directories alone,
- Goal autorun dry-runs, even when the result is `PASS`,
- a fixture with `simulated_fixture` choices,
- a terminal demo,
- a receipt with no real user decision,
- a receipt with unresolved blockers.

## Receipt Template

Use `docs/film-preproduction/templates/live-user-acceptance.template.yaml` as the starting point.

Copy it to `.dircreative/runs/live-user-acceptance.yaml` only after the user explicitly accepts the chat experience. Do not create an accepted receipt from a dry run, a simulated fixture, or an agent-only review.

## Runbook

Use `docs/film-preproduction/live-chat-acceptance-runbook.md` to run the acceptance pass. That runbook defines the operator prompt, required chat stages, required user decisions, receipt creation rule, and final verification commands.
