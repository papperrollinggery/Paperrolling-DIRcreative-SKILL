---
name: dircreative-update
description: Refresh model and prompt-pattern knowledge from official sources, GitHub prompt libraries, and internal QA.
---

# Update

## Required Knowledge

- `docs/film-preproduction/sources/model-sources.yaml`
- `docs/film-preproduction/sources/prompt-sources.yaml`
- `docs/film-preproduction/research/model-adapter-notes.md`
- `docs/film-preproduction/research/image-prompt-style-system.md`
- `docs/film-preproduction/prompt-pattern-registry.json`

## Inputs

- source registry
- prompt registry
- QA observations

## Outputs

- source freshness report
- pattern candidate
- model adapter revision request
- deprecation note

## Rules

- Distinguish official facts from inferred behavior.
- Record source URL and verification date.
- Extract pattern mechanisms, not full copied prompts.
- Promote only after fixture QA improves.

## skill_run_receipt

Record checked sources, stale entries, update decisions, and `next_recommended_skill: checkpoint`.
