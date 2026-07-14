---
name: dircreative-sequence-planner
description: Split 60s, 90s, and 180s projects into model-safe sequence plans and user review gates.
---

# Sequence Planner

## Required Knowledge

- `docs/film-preproduction/longform-decomposition-policy.md`
- `docs/film-preproduction/capability-aware-generation-policy.md`
- `docs/film-preproduction/schemas/sequence-plan.yaml`
- `docs/film-preproduction/schemas/shot-list.yaml`
- `docs/film-preproduction/research/channel-playbooks.md`

## Inputs

- selected concept
- treatment or script
- shot list
- target duration
- channel and model targets

## Outputs

- sequence plan
- generation unit policy
- user gate map
- edit handoff skeleton

## Rules

- Default 180s work to `longform_generation_mode: hybrid`.
- Default `visual_output_mode` to `prompt_only` unless the user authorizes generation.
- Plan the whole film before any per-sequence reference prompts.
- Treat 15s as the default generation-unit ceiling, not the story duration.
- If the user only names a model limit, infer `generation_unit_limit: 15s` and keep the story duration separate.
- Use 5-15s generation units.
- Keep each sequence's dramatic function distinct.
- Do not create images or videos.
- Mark batch mode with accepted continuity and rework risks.
- Preserve global continuity anchors for identity, product, wardrobe, location, lens, light, and audio.

## skill_run_receipt

Record duration split, mode choice, user gates, unresolved continuity questions, QA status, and `next_recommended_skill: longform-reference-planner`.
