---
name: dircreative-learn
description: Record reusable project learnings, prompt fixes, channel rules, and model behavior.
---

# Learn

## Required Knowledge

- `docs/film-preproduction/prompt-pattern-registry.json`
- `.dircreative/learnings.jsonl`
- `.dircreative/timeline.jsonl`

## Inputs

- QA report
- retry plan
- user feedback
- observed output behavior

## Outputs

- learning entry
- registry update request
- deprecation request when a pattern fails repeatedly

## Rules

- Write append-only JSONL.
- Mark source as `user-stated`, `observed`, `inferred`, `official`, or `internal_eval`.
- Do not promote a pattern without fixture QA improvement.

## skill_run_receipt

Record new learning keys, confidence, source, and `next_recommended_skill: checkpoint`.
