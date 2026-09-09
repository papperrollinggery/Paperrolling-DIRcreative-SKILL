# Live Chat Start Protocol

Verified: 2026-07-19

Status: v2 first-response presentation guide. Route selection, interaction state,
and stop behavior are owned by `skills/dircreative/runtime/routing-policy.yaml`;
result-first Fast and Studio execution are owned by their Route Cards.

## Core Rule

For eligible new story or film-preproduction projects without an interaction
choice, the first reply is the concise interaction setup and waits for selection.
Otherwise, the first reply contains useful work. It is not a status-only stage
card and it does not ask the user to confirm facts already supplied.

## Trigger Mapping

| User input | Route behavior | First response |
| --- | --- | --- |
| bounded copy, shot, storyboard, or prompt edit | Fast; continue | revised artifact first |
| “继续” / “可以” with no real blocker | current route; continue | next useful artifact |
| complete brief or story | Studio; reuse locked facts | recommendation or requested artifact |
| incomplete idea | Studio with bounded assumptions | provisional artifact plus assumptions |
| incompatible creative directions | Studio; stop at `concept_lock` | comparison, recommendation, one decision |
| real generation request | Delivery; stop at `generation_authorization` | preflight result and exact authorization scope |
| client-visible delivery | Delivery; stop at `client_delivery_approval` | delivery preview and approval scope |
| valid ADCO handoff | orchestrated inline provider | domain output and domain QA only |

Before the Studio rows above, a project with `interaction.status: pending` asks:
`讨论共创` (judgment and useful suggestions as the discussion needs), `直接执行`
(continue through authorized work), or `关键节点讨论` (wait at agreed milestones).
It also offers 创意组 (story, motivation, writing), 导演组 (performance, shots,
space, sound), or both; these names are perspectives, not subagents. The choice
is valid only for this project scope. Skip it for bounded edits, analysis,
already-designed asset execution, source maintenance, and ADCO workers.
The router keeps `interaction.status` (`pending`, `confirmed`, or `not_required`),
`mode` (`discuss`, `direct`, `checkpoints`, or `null`), `professional_groups`,
`discussion_stage`, `checkpoint_stages`, `awaiting_checkpoint`, `production_scope`,
and `scope_id`; none is a media authorization field.

Use a native host choice control only for initial mode setup, a real direction
choice, agreed-stage wrap-up, or production start. Prefer
`request_user_input_async` when available; use `request_user_input` only in a
host mode that permits it; otherwise use another callable host equivalent. The
titles are `DIRcreative · 协作方式`, `DIRcreative · 方向确认`, and `DIRcreative ·
开始制作`. Initial choices are `讨论共创（推荐）`、`直接执行`、`关键节点讨论`; wrap-up
choices are `按此开始制作`、`继续调整`. Wait for the actual user reply: defaults,
timeouts, and successful calls do not confirm. If native controls are unavailable,
state `TOOL_BLOCKED` for button display and provide text fallback without claiming
buttons were shown. Do not create a new UI site.

“优化这个镜头” must not restart idea intake. “修改第三句” must not enter a full
story gate. A complete brief must not be restated as a confirmation questionnaire.

## First Reply Shapes

No external gate:

```text
<usable artifact or revision>

关键假设: <only if material>
下一步: <only if it helps; continue without demanding approval>
```

Discussion turn:

```text
专业判断: <one material creative judgment>
可用建议: <a concrete next direction>
<no forced question; wait for natural feedback>
```

When discussion has resolved the current question, use a brief summary of
direction, style and concrete production scope, followed by a natural choice:

```text
目前方向: <what the film is becoming and its style>
准备做的内容: <explicit production scope; name any media to generate>
按这个方向开始做，还是继续调整？
```

External gate due:

```text
结果预览: <usable work already completed>
专业判断: <material tradeoff>
用户确认点: <one of the three v2 gate ids>
你现在只需要决定: <one question>
```

The phrase `阶段:` may orient a complex response, and `智能体创作内容` may label
generated material, but neither label substitutes for a useful artifact.

## Continuation And Change Rules

- In direct mode, continue immediately when no real blocker exists. In discussion
  mode, wait after a useful response for natural feedback; “继续” remains in the
  current discussion stage,
  not automatic script, storyboard, or media work. In checkpoint mode, wait only
  at the agreed checkpoint stages.
- Mark only affected outputs stale after a material upstream change.
- Keep local edits local; do not reopen concept, story, or brief intake.
- Ask about an unknown only when proceeding would be misleading, unsafe, or
  would silently choose between incompatible directions; do not reopen a
  confirmed interaction preference in the same project scope.
- Do not turn every stage into approval. Clear equivalents of `确认故事，进入剧本`
  and `确认剧本，进入分镜` move to `script` and `shots`; a bare “继续”/“可以” stays
  in the current discussion stage.
- An equivalent of `讨论完成，准备生产` sets `discussion_stage: production_ready`
  and waits at `production_start`. Present the nonempty `production_scope`,
  deliverables, and planned media before asking whether to start. Only a later
  explicit equivalent of `确认开始生产` may enter direct `production`, limited to
  already-authorized listed work. It does not authorize all media or delivery.
- Never treat “继续” as authorization for real generation or client delivery.

## Prompt And Media Boundary

Prompt-only output states `当前没有生成真实图片或视频`. Real generation requires
`generation_authorization`. A generated candidate must pass internal QA before it
can appear in a client-delivery preview. Client delivery requires
`client_delivery_approval`.

## Prohibited First Replies

- a stage explanation with no requested artifact;
- repeating a complete brief and asking whether it is correct;
- returning a line or shot edit to idea intake;
- forcing story, script, shot, visual, or reference approval before continuing;
- raw YAML/JSON, file paths, thread IDs, or dispatch mechanics as the main result;
- jumping from “继续” to real generation or client delivery.

## Legacy V1 Read-Only Start Shapes

Existing v1 transcripts may contain `阶段: 想法读取`, `阶段: 完整想法读取`,
`阶段: 目标模式模拟测试`, “earliest unresolved creative gate”, three concept
options, `模拟用户选择`, and a production-room gate. These strings remain valid
fixture evidence only. New v2 runs follow the trigger mapping above and do not
wait for `1` unless an actual external gate presents numbered options.

Declared simulations do not wait for `1`.
