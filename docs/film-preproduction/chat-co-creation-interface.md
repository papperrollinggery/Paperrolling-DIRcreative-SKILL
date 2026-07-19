# Chat Co-Creation Interface

Verified: 2026-07-19

Status: v2 presentation guide. Gate names, routing, and persistence are owned by
`skills/dircreative/runtime/routing-policy.yaml`; this guide does not redefine
them. The v1 eleven-gate workflow is read-only fixture vocabulary.

## Active Contract

DIRcreative is chat-first and artifact-backed. The useful result leads; process
notes, state, and receipts follow only when they help the user judge or continue
the work.

A new run may stop for exactly three external user gates:

1. `concept_lock` when incompatible creative directions would materially change
   the result;
2. `generation_authorization` immediately before real image or video generation;
3. `client_delivery_approval` immediately before a client-visible handoff.

Story, script, shot, visual, reference, prompt, and QA progress are reversible
internal state. They are not default user approval gates.

## Live Operating Loop

1. Route the request to Fast, Studio, or Delivery.
2. Reuse supplied facts and current artifacts. Do not repeat a known brief.
3. Produce the smallest useful artifact or revision.
4. Continue through internal states while no real blocker exists.
5. Ask one question only when one of the three external gates is actually due or
   an unknown fact makes useful work impossible.
6. Record only the decisions and outputs needed for the selected route.

“继续” and “可以” mean continue when there is no real blocker. “优化这个镜头”
stays on that shot. “修改第三句” stays on that line. Neither request returns to
idea intake or opens a full story approval sequence.

## Result-First First Reply

When the user asks for a direct artifact, the first response must contain a
usable artifact: revised copy, a shot proposal, a storyboard finding, a concept
recommendation, or the requested prompt. A stage label alone is not a result.

For a complete brief, lock the supplied facts internally and begin the requested
work. Do not ask the user to reconfirm facts already present. For an incomplete
brief, state bounded working assumptions and still produce a provisional result
unless an unresolved fact would make that result misleading or unsafe.

## External Gate Shape

Only an actual external gate uses a blocking question:

```text
结果预览: <the work the user can judge>
专业判断: <why this decision changes the result>
用户确认点: <concept_lock | generation_authorization | client_delivery_approval>
你现在只需要决定: <one concrete decision>
```

If no external gate is due, omit `用户确认点` and return the artifact plus any
important assumptions or next action. Do not manufacture 2-3 options, a conflict,
or a neat decision ceremony.

## Reversible Internal State

The active internal fields are:

```text
story_state
script_state
shot_state
visual_state
reference_state
prompt_state
qa_state
```

An internal state can be revised, marked stale, or regenerated without asking
for user approval at every transition. A core premise change marks only affected
downstream outputs stale; a bounded change does not invalidate the whole project.

## Frontstage And Backstage

Frontstage is the user-readable artifact, recommendation, material tradeoff, and
the one real decision if needed. Backstage is compact state, hashes, manifests,
authorization evidence, QA details, and legacy fixture interpretation.

Do not dump raw YAML or JSON as the main answer. Do not expose thread IDs,
dispatch records, worker cleanup, or control-plane mechanics. Fast uses no Codex
Threads; Studio defaults to one controller and zero Threads.

## Frontstage Copy Hygiene

Every visible gate must follow `docs/film-preproduction/professional-agent-voice-standard.md` and run a humanizer pass. The point is not to sound friendlier; it is to keep concrete production judgment while removing formulaic model language. Apply the same humanizer check to result-first responses that have no gate.

Prompt-only handoffs need an extra boundary: state what the prompt inherits, what
was not generated, and what later QA must verify. Do not frame a prompt-only handoff as a finished creative win.

## Prompt And Media Boundary

Prompt-only output must say that no real image or video was generated. A real
generation request stops at `generation_authorization` after internal preflight
and QA readiness pass. Generated candidates remain internal QA state until they
pass self-QA; a client-visible handoff then requires `client_delivery_approval`.

Customer-facing labels such as `阶段: 出图执行建议`, `阶段: 视频生成建议`, and
`阶段: QA 与重试规则` may organize a complex Delivery response, but they do not
create extra external gates.

## Visual Decision Enhancement

When a visualization materially improves a real decision, follow
`chat-inline-visualization-interface.md`. A local visual selection is
presentation-only until the controlling chat converts it into a human-readable
decision. The fallback must preserve the artifact and question without forcing
the user into another client.

## Goal Mode Simulation

A declared goal-mode simulation may demonstrate the v2 flow and label a
`模拟用户选择`, but it cannot create real authorization, live acceptance, or
client delivery approval. Do not wait for `1` during a declared simulation.

## Legacy V1 Fixture Compatibility

`docs/film-preproduction/schemas/co-creation-run.yaml` and existing example runs
remain readable as `contract_version: 1.0.0`. Their old live operating loop,
production-room gate, one question / one user decision sequence, and “earliest
unresolved creative gate” language exist only to interpret fixtures.

The legacy eleven types are `concept_options_gate`, `story_approval_gate`,
`script_approval_gate`, `shot_list_approval_gate`, `visual_direction_gate`,
`visual_bible_approval_gate`, `sequence_plan_gate`,
`global_reference_pack_gate`, `sequence_reference_pack_gate`,
`clean_frame_gate`, and `video_prompt_gate`. New v2 runs must not create or
require them. Legacy reference strategy must wait rules, ad reference pack terms
(product identity board, lighting/material/style board, storyboard/motion board,
clean frames, single clean frame), multi-review / 多专家评审 / compound
professional mode labels, `阶段: 想法读取`, and `阶段: 完整想法读取` are read-only
compatibility vocabulary, not active stage gates.
