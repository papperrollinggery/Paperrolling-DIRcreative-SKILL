---
name: dircreative-checkpoint
description: Save and resume workflow state across phases, artifacts, and skill runs.
---

# Checkpoint

## Required Knowledge

- `docs/film-preproduction/phase-contracts.yaml`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/schemas/skill-orchestration.yaml`
- `.dircreative/checkpoints/`
- `.dircreative/timeline.jsonl`

## Inputs

- current phase
- git status
- recent skill_run_receipt
- unresolved questions

## Outputs

- checkpoint markdown
- timeline entry
- next exact action

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#checkpoint-current-state`. Show current stage, locks, stale artifacts, unresolved decision, and next action from the audited current-state projection; resume intent must re-enter the active gate and preserve the Markdown fallback.

## Rules

- Save current active phase, completed artifacts, verification status, blockers, and next command.
- Do not delete old checkpoints automatically.
- Keep checkpoint text actionable for another worker.

## skill_run_receipt

Record checkpoint file path, active phase, unresolved questions, and `next_recommended_skill`.
