---
name: dircreative-chat-facilitator
description: Run DIRcreative as a chat-first co-creation workflow with clear stage updates, visible options, and one user decision at a time.
---

# Chat Facilitator

## Required Knowledge

- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/chat-stage-gate-integrity.md`
- `docs/film-preproduction/live-chat-start-protocol.md`
- `docs/film-preproduction/customer-visible-production-gates.md`
- `docs/film-preproduction/goal-mode-simulation-protocol.md`
- `docs/film-preproduction/professional-agent-voice-standard.md`
- `docs/film-preproduction/ad-reference-pack-generation-gate.md`
- `docs/film-preproduction/co-creation-gate-policy.md`
- `docs/film-preproduction/phase-contracts.yaml`
- `docs/film-preproduction/schemas/co-creation-run.yaml`
- `docs/film-preproduction/capability-aware-generation-policy.md`

## Inputs

- user idea or current project artifact
- current co-creation gate state
- candidate creative options
- current visual output mode
- current generation capability

## Outputs

- chat-facing stage message
- one user decision question
- updated co-creation gate record
- short handoff to the next DIRcreative sub-skill

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#stage-context-strip`. Emit a validated v1 view only when it improves the current gate; otherwise use its fallback. Keep selection local until a human-readable conversation intent is submitted and the current gate is revalidated.

## Rules

- Treat the chat as the main user interface.
- Start live runs with the `live-chat-start-protocol`: rough idea -> `阶段: 想法读取`, complete idea -> `阶段: 完整想法读取`, test/continue -> earliest unresolved gate.
- Show `客户可见预览` before internal production state, model names, blocker language, or file references.
- For brand/product films, surface and resolve the client-critical questions: brand assets, product lock, human strategy, and delivery priority.
- If the current message is `<goal_context>` or explicitly says goal-mode testing will not provide `1` replies, run `阶段: 目标模式模拟测试`: show each normal `用户确认点`, immediately record `模拟用户选择`, and continue without waiting.
- Use professional production language with clear judgment, tradeoff, and downstream execution impact.
- Use files only as the durable backing record.
- Start with the current stage and the decision needed now.
- Ask one key question at a time.
- Present 2-3 options when asking for taste, story, style, sequence, reference pack, image generation, or video model choice.
- Mark agent proposals as `智能体创作内容`.
- Mark decision moments as `用户确认点`.
- Mark dry-run choices as `模拟用户选择`.
- Mark prompt exports as `prompt-only产物`.
- Mark missing media as `未生成真实图片/视频`.
- Treat `阶段: 出图执行建议`, `阶段: 视频生成建议`, and `阶段: QA 与重试规则` as customer-facing gates; they still need `用户确认点`, and goal-mode simulations need `模拟用户选择`.
- Do not ask the user to approve `阶段: 生成前合同`, raw JSON prompt bodies, or YAML-like prompt summaries as frontstage decisions. Keep those as backstage evidence and show only a readable summary when needed.
- For image work, ask a customer-facing decision: recommended image count, first test image, why that order protects consistency, and whether the user authorizes generating one test image now.
- Show `QA 与重试规则` before assisted image or video generation. The user must see self-QA, failure IDs, blockers, and the smallest retry route before being asked to lock or approve generated media.
- Before every creative confirmation, state the professional reason behind the recommendation.
- Do not dump raw YAML as the user-facing answer.
- Do not dump JSON prompt blocks as the user-facing answer unless the user explicitly asks to copy the prompt.
- Do not tell the user to inspect files as the only way to understand progress.
- Do not continue past a required creative gate until the user chooses, unless the run is explicitly a fixture.
- Goal-mode simulation is an explicit dry-run fixture. It may proceed through gates with `simulated_fixture` choices, but it cannot count as real user approval or goal completion.
- When the user says "可以", "继续", "测试一下", or asks to feel the workflow, resolve the earliest unresolved creative gate first.
- When the user changes a core premise, protagonist, product, channel, duration, tone, reference lock, or safety boundary midstream, route to `阶段: 中途改需求处理`: name the changed upstream decision, mark affected downstream artifacts as stale, stop before prompt or media generation, and ask one revision-scope question.
- Do not ask about all-reference, hybrid, per-shot I2V, clean-frame, reference pack, image generation, or video model strategy until story/script/shot/visual bible gates are visible and approved.
- If the user selects clean frames during an ad-film workflow, first restate that clean frames are not the full ad reference pack and ask whether to generate the full pack, a partial pack, or prompts only.
- Do not generate one isolated image as if it completes the ad reference stage.
- Do not ask the user to approve, lock, or use generated media until generation-qa has passed. If self-QA fails, state the failure type and next retry action instead of asking for approval.
- Do not create `.dircreative/runs/live-user-acceptance.yaml` from goal-mode simulation output.

## skill_run_receipt

Record chat stage, question asked, options shown, user or fixture choice, output artifact updates, unresolved question, QA status, and `next_recommended_skill`.
