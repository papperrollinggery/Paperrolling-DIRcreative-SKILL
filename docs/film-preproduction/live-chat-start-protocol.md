# Live Chat Start Protocol

Verified: 2026-07-19

Status: v2 first-response presentation guide. Route selection and stop behavior
are owned by `skills/dircreative/runtime/routing-policy.yaml`; result-first Fast
and Studio execution are owned by their Route Cards.

## Core Rule

The first reply contains useful work. It is not a status-only stage card and it
does not ask the user to confirm facts already supplied.

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

“优化这个镜头” must not restart idea intake. “修改第三句” must not enter a full
story gate. A complete brief must not be restated as a confirmation questionnaire.

## First Reply Shapes

No external gate:

```text
<usable artifact or revision>

关键假设: <only if material>
下一步: <only if it helps; continue without demanding approval>
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

- Continue immediately when no real blocker exists.
- Mark only affected outputs stale after a material upstream change.
- Keep local edits local; do not reopen concept, story, or brief intake.
- Ask about an unknown only when proceeding would be misleading, unsafe, or
  would silently choose between incompatible directions.
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
