---
name: dircreative-idea-intake
description: Parse a rough idea into project brief, inferred channel, constraints, and missing decisions.
---

# Idea Intake

## Required Knowledge

- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/creative-copy-deck-capability.md`
- `docs/film-preproduction/schemas/project.yaml`
- `docs/film-preproduction/research/channel-playbooks.md`

## Inputs

- raw user idea
- optional channel, duration, aspect ratio, references, constraints

## Outputs

- project brief
- parsed intent
- channel inference
- facts, source evidence, and labeled inferences
- audience tension, business objective, single-minded proposition, and avoid-cliches
- missing decisions
- recommended next skill: `director-room`

## Chat Surface

Show a brief in chat before writing downstream artifacts:

- `阶段: 想法读取`
- `智能体创作内容`: restated idea, inferred channel, likely story duration, generation-unit cap, aspect, constraints, known facts and evidence, explicit inferences, audience tension, business objective, single-minded proposition, and avoid-cliches.
- `用户确认点`: ask whether the brief is right before moving into director-room options.

Ask one question only: "这个 brief 是否正确？"

## Creative Foundation Gate

Before recommending a concept:

- Record each factual input under `creative_foundation.facts` and bind it to one or more `source_evidence_ids`.
- Record source type, locator, summary, and verification status under `creative_foundation.source_evidence`.
- Keep DIRcreative interpretations under `creative_foundation.inferences`; name the supporting fact IDs and confidence.
- Treat evidence, facts, and inference IDs as fail-closed: arrays only, mapping items only, unique non-empty IDs, and resolving references.
- For commercial work, fill `commercial_strategy.audience_tension`, `business_objective`, `single_minded_proposition`, and `avoid_cliches`.
- Resolve audience-tension evidence IDs and proposition support-fact IDs before the brief can pass.
- Treat generic goals such as "build awareness" or "make it cinematic" as unresolved until the audience pressure and intended change are concrete.
- Do not convert an unverified input or an inference into an audience-facing factual claim.

If source evidence or audience tension is missing, keep the brief at `needs_user` and name only the smallest missing decision. Do not compensate with invented research or polished copy.

## Rules

- Infer a channel only when evidence is strong.
- Keep uncertainty explicit.
- Distinguish `story_duration` from `generation_unit_limit`. A 15s video model cap means each generated group is at most 15s, not necessarily that the story is 15s.
- If the duration meaning is ambiguous, ask one clarification question before scripting.
- Separate facts from inferences in both the artifact and the chat preview.
- Do not write a single-minded proposition that has no supporting fact IDs.
- Record category cliches and familiar visual shortcuts the downstream concept should avoid.
- Do not write story, script, shot list, image prompts, or video prompts.

## skill_run_receipt

Include `skill_run_receipt` with input artifacts, output artifacts, fail-closed ID status, source-evidence and inference binding status, tension/SMP source status, commercial-strategy status, decisions, unresolved questions, QA status, and `next_recommended_skill: director-room`.
