---
name: dircreative-script-breakdown
description: Extract production assets, props, wardrobe, sound, VFX, and special requirements from script.
---

# Script Breakdown

## Required Knowledge

- `docs/film-preproduction/research/film-production-glossary.md`
- `docs/film-preproduction/research/audio-design-notes.md`
- `docs/film-preproduction/schemas/story-package.yaml`

## Inputs

- approved script

## Outputs

- script breakdown YAML
- asset requirements
- audio policy

## Rules

- Separate image prompt labels, video prompt audio, and post-production audio.
- List every story-critical character, location, prop, wardrobe item, VFX, SFX, and special requirement.
- Do not write shot list or prompt files.

## skill_run_receipt

Record extracted assets, missing decisions, QA status, and `next_recommended_skill: shot-design`.
