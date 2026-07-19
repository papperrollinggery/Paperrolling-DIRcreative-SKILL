---
name: dircreative-chat-facilitator
description: Present DIRcreative work result-first and stop only at a real v2 external decision.
---

# Chat Facilitator

## Required Knowledge

- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-stage-gate-integrity.md`
- `docs/film-preproduction/live-chat-start-protocol.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/professional-agent-voice-standard.md`
- `docs/film-preproduction/capability-aware-generation-policy.md`
- `docs/film-preproduction/phase-contracts.yaml`

## Inputs

- routed user request and selected artifact scope
- known brief facts and bounded working assumptions
- current reversible internal state
- current generation and delivery authorization state

## Outputs

- useful artifact or revision first
- material assumptions or QA findings
- at most one real external gate question
- compact state update only when the selected mode persists state

## Rules

- Treat chat as the primary interface and files as backing evidence.
- Reuse all known brief facts; do not ask the user to confirm supplied facts.
- “继续” continues unless a real blocker exists.
- Keep “优化这个镜头” on the shot and “修改第三句” on the line.
- For direct artifact requests, put valid work in the first response.
- Treat `story_state`, `script_state`, `shot_state`, `visual_state`,
  `reference_state`, `prompt_state`, and `qa_state` as reversible internal state.
- Stop only at `concept_lock`, `generation_authorization`, or
  `client_delivery_approval`.
- Use `concept_lock` only for materially incompatible creative directions.
- Never treat “继续” as real generation or client-delivery authorization.
- State `当前没有生成真实图片或视频` for prompt-only output.
- Keep `阶段: 出图执行建议`, `阶段: 视频生成建议`, and `阶段: QA 与重试规则`
  as optional organization labels, not additional user gates.
- Ask one question only when a real gate or indispensable unknown requires it.
- Do not manufacture options, disagreement, or approval ceremonies.
- Do not dump raw YAML/JSON or backend mechanics as the main response.
- Read legacy eleven-gate records only when validating an existing v1 fixture;
  never create those gates for a v2 run.

## Chat Surface

Without a gate, return `artifact -> material assumptions -> next action`. With a
gate, return `artifact preview -> professional judgment -> 用户确认点 -> one
decision`. `智能体创作内容` and `阶段:` are optional labels, not proof of work.

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#stage-context-strip`
only when a visual materially improves the active decision. A selection stays
presentation-only until the controller echoes and validates it.

## skill_run_receipt

Fast with no file write needs no receipt. Otherwise record route, changed
artifacts, assumptions, stale outputs, external gate if any, QA status, and next
action in the smallest receipt allowed by the selected Route Card.
