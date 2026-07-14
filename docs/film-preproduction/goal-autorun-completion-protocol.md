# Goal Autorun Completion Protocol

Verified: 2026-06-15

Purpose: make native Goal mode run DIRcreative end to end without waiting for repeated manual `1/2/3` replies, while preserving the real user acceptance boundary.

## Trigger

Use this protocol when:

- the current message contains `<goal_context>`,
- the user says Goal mode should run without manual choices,
- the user asks for an automated full dry-run,
- an audit needs to prove that rough idea, complete idea, product ad, and Creative Production preflight can proceed without blocking on every gate.

## Autorun Rule

Goal autorun is a dry-run fixture unless the user is actively present and explicitly accepting the live workflow.

For every visible `用户确认点`, the agent must immediately record:

```text
模拟用户选择:
<recommended conservative option>, because <one production reason>.
```

The reason must name at least one of:

- story clarity,
- commercial proof,
- channel fit,
- shot rhythm,
- reference consistency,
- direct video input safety,
- prompt-only boundary,
- Creative Production generation readiness.

## Required Coverage

The autorun fixture must cover:

- rough idea path,
- complete idea segmentation path,
- commercial/product-ad path,
- Creative Production generation preflight path,
- QA and retry path,
- final dry-run conclusion.

## Generation Boundary

In autorun, generation stages may simulate authorization checks and receipt shape only.

They must not:

- generate real images or videos,
- call Creative Production generation workers,
- write `live-user-acceptance.yaml`,
- set `real_user_co_creation_verified: true`,
- call `update_goal`,
- treat `render_moodboard_board_widget` or a generated candidate as truth.

## Completion Output

Every autorun transcript must end with:

```text
阶段: 模拟测试结论
结果: PASS | NEEDS_FIX
覆盖: rough idea / complete idea / commercial product ad / Creative Production preflight / QA
未生成真实图片/视频: true
不计入真实验收: true
下一步真实用户确认点: <one concrete live decision>
```

## Machine Checks

`scripts/dircreative_goal_autorun_audit.py` is the owner for autorun completion evidence.

It must prove:

- every `用户确认点` has a nearby `模拟用户选择`,
- Creative Production preflight is included but not executed,
- real media generation is false,
- live acceptance receipt is not written,
- the final result is `PASS`,
- the next live user decision is explicit.
