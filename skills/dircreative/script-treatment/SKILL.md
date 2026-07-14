---
name: dircreative-script-treatment
description: Turn approved treatment into script-ready scenes, action, dialogue, voiceover, and no-dialogue decisions.
---

# Script Treatment

## Required Knowledge

- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/creative-copy-deck-capability.md`
- `docs/film-preproduction/professional-agent-voice-standard.md`
- `docs/film-preproduction/production-demo-retrospective.md`
- `docs/film-preproduction/council-adversarial-review.md`
- `docs/film-preproduction/client-film-hard-gates.md`
- `docs/film-preproduction/schemas/story-package.yaml`
- `docs/film-preproduction/research/audio-design-notes.md`
- `docs/film-preproduction/research/film-production-glossary.md`

## Inputs

- approved treatment
- story review
- audio intent
- approved claim register
- real copy samples and `VOICE PROFILE` when a client or brand voice is requested

## Outputs

- script
- dialogue or no-dialogue policy
- voiceover or no-voiceover policy
- copy-development receipt
- `deck_narrative_spec` when a deck handoff is requested; no PPT output

## Chat Surface

Show the script in a readable preview:

- `阶段: 脚本预览`
- `智能体创作内容`: timed script, scene objective, conflict pressure, action beats, turn/reveal, dialogue/no-dialogue policy, VO budget when used, audio intent.
- `用户确认点`: ask whether the script direction passes before shot design.

Keep the question about script approval only.

## Copy Development Gate

Run audience-facing copy in this order:

1. Collect 5 to 20 representative real samples when available; require `sample_id`, `source_ref`, `excerpt`, `why_representative`, and `recency`, and record any shortfall.
2. Build exactly one source-derived `VOICE PROFILE` with the fields defined in `project.yaml`; cover all unique sample IDs or record `coverage_shortfall_reason`.
3. Add DIR professional judgment: audience effect, channel fit, factual boundaries, tradeoff, and approved claim IDs.
4. Run `de-AI-writing` as a fidelity-preserving refinement. Protect meaning, evidence, and claim boundaries; add no unsupported fact or conclusion.
5. Run `humanizer` or `humanizer-zh` as a diagnostic only.
6. Record manual craft review of rhythm, abstraction, and evidence alignment, then reconcile its status and trace clusters with `copy_execution`.

An AI-trace cluster triggers manual review. A word-list or phrase hit cannot fail copy by itself and cannot prove authorship. Preserve intentional voice, quotations, technical terms, and approved claims.

The detected cluster set, diagnostic cluster set, manual-craft reviewed cluster set, and `copy_execution.ai_trace_clusters` must match. A cluster remains review-only, and the diagnostic may not add hidden blocking or authorship authority. Copy with no phrase hit can still require revision when manual craft review records repetitive rhythm, abstraction, or evidence detachment.

Every `claim_id` used by audience-facing dialogue, voiceover, supers, captions, CTA, or deck copy must have `approval_status: approved` and verified evidence. `copy_execution.evidence_ids_used` must cover used-claim evidence through the story source bindings. Pending, rejected, unreviewed, missing, or dangling claims block the relevant line. Audience-facing text must be non-empty, and copy statuses must match the validated pipeline.

## Deck Narrative Handoff

When the user requests a deck, create `deck_narrative_spec` only after the script direction is approved. The spec must define the communication job, opening tension, cumulative story beats, closing resolution, one narrative job and authoritative `primary_claim_id` per slide, claim/evidence bindings, layout family, composition, primary visual role, text-density budget, and recomputed QA statuses.

Routing rules:

- Editable PowerPoint defaults to `Presentations` with element-level editability.
- `codex-ppt` is allowed only after the user explicitly accepts full-slide images whose contents are not separately editable.
- `high-end-visual-design` may inform aesthetic references, but it is not a PPT construction, editability, or QA authority.
- Stop at the spec. Do not generate slides, slide images, or a `.pptx` in this skill.

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#script-timing-bands`. Bind time bands, dialogue, voiceover, audio, duration budget, and overrun to the current script artifact; approval and revision remain conversation intents with a table fallback.

## Rules

- Separate action, dialogue, voiceover, and sound notes.
- Preserve the approved facts, inferences, audience tension, business objective, proposition, avoid-cliches, concept dependencies, and claim boundaries.
- Write to the approved story duration, not automatically to 15s. If 15s is only the model generation-unit cap, write the full script/treatment first and hand longform splitting to sequence-planner.
- For 60-second client films, create a time budget and VO budget before shot design. Each VO line must include readable VO text, start/end seconds, covered shot IDs, and covered seconds. A VO line may cover multiple shots, but the mapping must be copyable and unambiguous.
- Do not write placeholders such as `VO marks this shot segment`, `VO标注本镜头句段`, or internal production instructions inside VO text.
- Each scene must identify what the character wants, what blocks it, what changes by the end of the scene, and which visible action proves that change.
- Each scene must fill a scene beat card: scene objective, opposing force, tactic change, subtext under dialogue, visible action beat, turn/reveal, and end-state change.
- Dialogue must create pressure, misdirection, reveal, refusal, concession, or choice. Do not use dialogue only to state the theme or decorate the mood.
- The script must preserve the approved story engine: external pressure, hidden relationship engine, irreversible choice/reveal, escalation, consequence, and visible ending action.
- If the script reads as atmosphere without causality, return to story-development instead of continuing to shot design.
- If there is no dialogue, state that explicitly.
- Do not hide an unapproved claim inside dialogue, voiceover, a slogan, a supers line, or a slide title.
- Do not write shot list or prompt files.

## skill_run_receipt

Record script scope, dialogue policy, copy source set and shortfalls, VOICE PROFILE coverage status, DIR judgment status, de-AI fidelity status, manual-craft status, humanizer review-only status, reconciled trace clusters, approved claim and evidence IDs used, deck claim/evidence/QA handoff status, and `next_recommended_skill: script-breakdown`.
