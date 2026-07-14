---
name: dircreative-story-development
description: Convert selected concept into logline, beat sheet, treatment, and story review.
---

# Story Development

## Required Knowledge

- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/creative-copy-deck-capability.md`
- `docs/film-preproduction/professional-agent-voice-standard.md`
- `docs/film-preproduction/production-demo-retrospective.md`
- `docs/film-preproduction/council-adversarial-review.md`
- `docs/film-preproduction/client-film-hard-gates.md`
- `docs/film-preproduction/schemas/story-package.yaml`
- `docs/film-preproduction/research/channel-playbooks.md`

## Inputs

- selected concept
- director-room notes
- channel and duration

## Outputs

- logline
- beat sheet
- treatment
- source bindings and concept substitutability check
- story review

## Chat Surface

Show the story as a short preview before moving to script:

- `阶段: 故事创意`
- `智能体创作内容`: logline, story engine, 5-8 beats, external pressure, irreversible choice, emotional turn, channel fit.
- `客户可见故事预览`: for client-facing films, write 2 or more readable story paragraphs that can be read to the client. Do not output only route labels, page titles, or short beat names.
- `用户确认点`: ask whether this story direction should become a script.

Do not ask about visual style in the same message.

## Quality Gate

Pass only if the story has protagonist, goal, obstacle, stakes, emotional turn, channel fit, and visualizable beats.

The approved concept must also pass the substitutability check:

- Record at least two alternatives with unique IDs and proximity reasons, then select the nearest one by ID into `swap_subject`.
- Record `before_swap` and `after_swap` while holding concept wording and beat order constant.
- Set `still_works_without_rewrite: false` only when the replacement breaks the mechanism, proof, relationship, setting, or payoff.
- Record at least two concrete `broken_dependency_ids` that resolve to `specific_dependencies`.
- Record `concept_author_id`; require an `independent_reviewer` whose reviewer ID differs from it, with `independent_from_concept_author: true` and a passing review status.
- Set `verdict: distinctive` only after those checks pass.
- Reject a concept that survives with noun replacement, even when its title, mood, or imagery sounds original.

Bind the story package to the approved fact, source-evidence, and inference IDs. The source arrays and IDs fail closed; preserve the audience-tension evidence and proposition facts used by the story. Every outline beat needs a unique ID plus `source_fact_ids` and `source_inference_ids` that resolve through the story binding. Keep inference-based creative moves labeled as professional judgment. Do not introduce an audience-facing commercial claim that is absent from the project's approved claim register.

For narrative shorts, also require a professional story engine:

- external pressure that forces action now, not only atmosphere,
- a hidden relationship engine, secret, misunderstanding, exchange, debt, or promise that changes the two-person dynamic,
- an irreversible choice or reveal before the ending,
- escalation from setup to pressure to reversal to consequence,
- a visible ending action that changes how the viewer reads the relationship,
- a reason the setting is a plot device, not just a mood background.

Reject story proposals that are only vibe, poster mood, soft dialogue, slice-of-life texture, or a gentle ending without conflict pressure and consequence.

Fill the dramatic pressure card before approval:

```text
Want:
Obstacle:
Tactic:
Subtext:
Turn/reveal:
Irreversible consequence:
Visible ending action:
Setting as plot device:
```

Reject if the card contains abstractions instead of specific screenable facts.

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#story-beat-ribbon`. Bind the beginning, turn, proof, ending, tension, and downstream effect to the story package; submit approval or revision intent to the current story gate and preserve the Mermaid fallback.

## Rules

- Keep the story executable for the target duration.
- Make the audience tension, business objective, single-minded proposition, and avoid-cliches visible in the concept decision when the project has commercial intent.
- Reject category cliches that reproduce an item in `avoid_cliches` without a project-specific reversal or consequence.
- For client-facing relationship, anniversary, brand-story, storyboard, or PPT proposal work, pass the Story Gate in `client-film-hard-gates.md` before script work. Customer-readable story paragraphs are required; short labels are not enough.
- Preserve every source-brief requirement not explicitly removed by the user. If an old route, alternate direction, customer prop, story bone, character count, or client-provided object is not used, record it as `omitted_requirements_without_user_removal` and block downstream work.
- If a prop list uses an ellipsis, treat it as examples. Expand the prop logic into each relevant character's role identity, prop, action, and shot function before approval.
- Explain why the story direction fits the channel, duration, first-hook timing, emotional turn, and reference-pack needs.
- If the user asks for visual exploration, story rebuild, formal lockable material, retry, thread/workflow audit, or live acceptance, name that intent before continuing.
- Do not move to script, shot design, reference planning, or image generation until the story review passes story tension, causal escalation, and professional story engine checks.
- Do not write a script until the story review passes.
- Do not write shot lists or prompts.

## skill_run_receipt

Record source-binding status, alternatives considered, selected swap and before/after result, broken dependency IDs, independent reviewer receipt, concept substitutability verdict, story gate status, claim-boundary status, and `next_recommended_skill: script-treatment`.
