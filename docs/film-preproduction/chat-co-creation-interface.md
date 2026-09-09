# Chat Co-Creation Interface

Verified: 2026-07-19

Status: v2 presentation guide. Gate names, routing, persistence, and interaction
state are owned by
`skills/dircreative/runtime/routing-policy.yaml`; this guide does not redefine
them. The v1 eleven-gate workflow is read-only fixture vocabulary.

## Active Contract

DIRcreative is chat-first and artifact-backed. The useful result leads; process
notes, state, and receipts follow only when they help the user judge or continue
the work.

A new run may stop for exactly three external authorization gates:

1. `concept_lock` when incompatible creative directions would materially change
   the result;
2. `generation_authorization` immediately before real image or video generation;
3. `client_delivery_approval` immediately before a client-visible handoff.

Story, script, shot, visual, reference, prompt, and QA progress are reversible
internal state. They are not default user approval gates.

## First Project Interaction Choice

For a new story or film-preproduction project whose user has not stated a
preference, make this short setup before creative production and wait:

```text
这次你想怎样推进？
1. 讨论共创：我围绕当前问题给出判断和可用建议，等你自然反馈。
2. 直接执行：我按已授权范围持续完成前期工作。
3. 关键节点讨论：前期只在约定的创意节点一起决定，开始制作后连续执行。

专业视角可选：创意组（剧情、人物动机、写作）、导演组（表演、镜头、空间、声音），或两组。
组名代表专业分工，不代表会启用子代理。
```

The confirmed choice applies only to the current project scope. Do not repeat it
for a same-scope continuation; allow the user to switch mode or groups at any
time. Do not show this setup for bounded local edits, analysis, execution of an
already-designed asset, source maintenance, or ADCO workers. It is an
interaction wait, not an external authorization gate: media authorization stays
independent.

The router records this independently from external authorization:

```text
interaction:
  status: pending | confirmed | not_required
  mode: discuss | direct | checkpoints | null
  professional_groups: list[creative | director]
  discussion_stage: <current issue or null>
  checkpoint_stages: <agreed stages or null>
  awaiting_checkpoint: <checkpoint or null>
  production_scope: list[str] = []
  scope_id: <current project scope>
```

## Live Operating Loop

1. Route the request to Fast, Studio, or Delivery.
2. If the interaction choice is required and pending, present it and wait.
3. Reuse supplied facts and current artifacts. Do not repeat a known brief.
4. In `discuss`, handle ordinary responses, explanations, and additions directly
   with substantive judgment and usable recommendations, then wait for natural
   feedback. Do not force a question or control after every reply. “继续” remains
   in the current discussion stage; it does not advance to script, storyboard,
   or generation automatically.
5. In `direct`, continue through internal states while the authorized scope has
   work remaining. In `checkpoints`, wait only at the agreed checkpoint stages.
6. Ask an external authorization question only when one of the three gates is due.
7. Record only the decisions and outputs needed for the selected route.

During authorized execution, “继续” and “可以” mean continue. A pending mode,
direction or production-start decision still requires its actual answer.
In `discuss`, “继续” means the next discussion turn. “优化这个镜头” stays on that
shot. “修改第三句” stays on that line. Neither request returns to idea intake or
opens a full story approval sequence.

## Native Choice Surface

Use a native host choice control only for initial interaction setup, a real
direction choice, agreed-stage wrap-up, or production start. Inspect the current
host: the default is `request_user_input_async` when available;
`request_user_input` is allowed only when the current host mode permits it;
otherwise use another callable host equivalent.

| Situation | Title | Choices |
| --- | --- | --- |
| initial setup | `DIRcreative · 协作方式` | `讨论共创（推荐）` / `直接执行` / `关键节点讨论` |
| direction choice or wrap-up | `DIRcreative · 方向确认` | decision-specific choices |
| ready production scope | `DIRcreative · 开始制作` | `按此开始制作` / `继续调整` |

Wait for the real tool-delivered user response. A preselection, timeout, or
successful call is not confirmation. If no control is callable, state
`TOOL_BLOCKED` for button display and give the matching text fallback without
claiming buttons were shown. Do not create a separate UI site.

## Discussion Progress And Production Start

Discussion turns solve the current creative question. They do not run an endless
“continue” loop or force story, script, and storyboard approvals. When the
information is sufficient, proactively summarize the direction, style, and
concrete production scope, then offer a short choice such as: `按这个方向开始做，还是
继续调整？` Clear natural-language equivalents are valid: `确认故事，进入剧本` sets
`discussion_stage: script`, and `确认剧本，进入分镜` sets
`discussion_stage: shots`. A bare “继续” or “可以” never performs either move.

The equivalent of `讨论完成，准备生产` sets
`discussion_stage: production_ready` and
`awaiting_checkpoint: production_start`. Before asking whether to start, present
the nonempty `production_scope`, its concrete deliverables, and every image or
video it would generate. Only a later explicit equivalent of `确认开始生产`, while
that checkpoint is still awaiting and the scope remains nonempty, enters
`mode: direct` at stage `production` and executes only the already-authorized
listed work. This production confirmation does not authorize unlisted media,
all media generation, or client-visible delivery.

## Result-First First Reply

When the user asks for a direct artifact, the first response must contain a
usable artifact: revised copy, a shot proposal, a storyboard finding, a concept
recommendation, or the requested prompt. A stage label alone is not a result.

For a complete brief, lock the supplied facts internally and begin the requested
work after any required interaction choice. Do not ask the user to reconfirm
facts already present. For an incomplete
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

If no external gate is due, omit `用户确认点`. In discussion mode, return a material
judgment and usable recommendation, then wait for natural feedback; use a choice
control only when a real decision is due. Do not manufacture 2-3 options, a
conflict, or a neat decision ceremony. In direct mode, return the artifact plus
any important assumptions or next action.

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

## Native question lifecycle and execution handoff

Use the existing router's `interaction` object in memory; persist it with the
compact snapshot for actual multi-file production or resume. The router is a
helper, not a mandatory call on each chat message. `interaction_question` is only
a proposed native question, never proof it was displayed. After the actual host
question tool returns, record its available acknowledgement with `question_id`
via `--question-receipt`. Only a submitted reply to that presented question may use
`--question-answer`; both accept small JSON files. A question receipt has `question_id` and an actual exposed `host_call_id`,
or the tool's `accepted: true` result plus `tool_name` when no call id is exposed.
Do not inspect logs merely to obtain an opaque UI handle. Text fallback instead
records `surface: text_fallback`, `shown: true`, and the concrete
`unavailable_reason` after presenting the scope in chat. An answer has
`question_id` and the offered `choice`. Preselection/cancel/timeout is not an answer.

Keep an unanswered question active while answering an ordinary follow-up. Do not
call the tool again for the same question. The helper returns no new
`interaction_question` after presentation. Changing production items advances
`production_revision` and replaces the question id; an old response cannot
approve the new scope. If no deliverables are listed, draft them before offering
a start button. Natural, unambiguous equivalents of a selection are valid;
historical, quoted, conditional or negated statements do not select a mode.

Once the current project plan exists, bind its `project_id` as the interaction
`scope_id`, carrying only this project's already confirmed choice. A production
consumer rejects an interaction state belonging to another plan project.
Pass the same confirmed state to `dircreative_skill_stack.py select` using
`--interaction-state` and `--interaction-scope-id`. Asset preparation also accepts
`--interaction-state`; it binds the state without rewriting the original media
request. A source file, returned template or imagined user reply cannot create
confirmation. A separate project's state never supplies this project's choice.

Questions about mode, style and start belong before production. Once the user
chooses the presented production scope, use direct execution for its remaining
work, reviews and repairs. Report finished content with a file link or saved
image preview, not a stage-by-stage protocol report. Keep requested deliverables
visible; do not create an approval stop merely to show them. Explicit initial
self-direction such as “自行编排” or “直接执行” already selects execution.

During execution, lead with completed content and its openable artifact.
Lead with the requested artifact; show neither every internal stage nor an
acceptance question for routine checks and repairs.
