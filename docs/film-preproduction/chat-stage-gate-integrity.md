# Chat Stage Gate Integrity

Verified: 2026-05-17

Purpose: prevent a DIRcreative chat run from looking complete while silently skipping user co-creation gates.

## Core Rule

Every visible creative stage must carry a decision surface.

A stage is not valid unless the user can see:

1. `阶段: <stage name>`
2. `智能体创作内容`
3. professional judgment or downstream impact
4. `用户确认点`
5. the next stage or action unlocked by the answer

Goal-mode simulation has the same gates, but it immediately records:

```text
模拟用户选择:
<recommended choice and one production reason>
```

## Live Run Contract

For a live user run:

- show one current stage only,
- ask one decision question,
- wait for the user answer,
- record the answer before continuing,
- never mark a choice as confirmed from a fixture.

Do not advance from story to script, script to shots, shots to references, references to prompts, or prompts to generation without a visible `用户确认点`.

If a visual decision view is used, it must validate against `chat-visualization-spec.schema.json`. A local selection does not resolve the gate. Only the controller may convert a submitted conversation intent into an artifact-backed gate decision, and it must show the confirmation echo before advancing.

If the user changes a core premise, protagonist, product, channel, duration, tone, reference lock, or safety boundary after downstream planning has started, the next visible stage must be `阶段: 中途改需求处理`. It must name the changed upstream decision, mark affected downstream artifacts as stale, stop before prompt or media generation, and ask one revision-scope question.

## Goal-Mode Simulation Contract

For a declared goal-mode simulation:

- keep the same stage sequence as a live run,
- show each normal `用户确认点`,
- immediately add `模拟用户选择`,
- state why the simulated choice is conservative,
- continue until `阶段: 模拟测试结论`,
- keep `real_user_co_creation_verified: false`.

The first wrapper stage, such as `阶段: 目标模式模拟测试`, may describe the run without a full decision gate. Terminal report stages may omit `模拟用户选择` only when no downstream creative choice remains.

## Prompt And Media Boundary

`阶段: 出图执行建议`, `阶段: 视频生成建议`, and `阶段: QA 与重试规则` are customer-facing gates.

`阶段: 生成前合同`, `阶段: 图片提示词摘要`, and raw JSON/YAML prompt bodies are backstage evidence. They may be summarized for traceability, but the user should not be asked to approve internal contracts or code-like prompt dumps as the main decision.

They must say whether the current output is:

- `prompt-only产物`,
- generated candidate,
- imported external asset,
- blocked assisted generation,
- or approved live media.

They must also say plainly when `当前没有生成真实图片或视频`.

The visible image-generation decision must answer:

- how many images are recommended,
- which one to generate first,
- why this order protects consistency,
- which images are planning-only versus direct video inputs,
- whether the user authorizes generating one test image now.

## Failure Cases

Fail the chat surface if:

- a creative stage has no `用户确认点`,
- a simulated stage has `用户确认点` but no `模拟用户选择`,
- the user is asked to approve raw JSON, YAML, or a pre-generation contract instead of a customer-facing image execution choice,
- prompt summaries appear before the customer-facing reference/image execution plan,
- old prompts or media generation continue after a core midstream change,
- the user is asked to approve generated media before self-QA,
- a file path or terminal report becomes the main user interface,
- the transcript implies real user approval from a simulated fixture.
- a visual click directly claims lock, readiness, acceptance, completion, or generation authorization,
- a visual view has no complete text fallback,
- an `orchestrated_worker` view makes DIRcreative user-facing or assigns host writes to DIRcreative.

## Validation

`scripts/dircreative_chat_surface_audit.py` is the executable check for this contract.

`scripts/dircreative_visualization_audit.py` is the executable check for visual state, source binding, action limits, fallback, and ADCO ownership.

Every transcript used as a product fixture must pass:

- `stage_order: ok`
- `contract_before_prompts: ok`
- `content_terms: ok`
- `decision_counts: ok`
- `stage_gate_integrity: ok`
