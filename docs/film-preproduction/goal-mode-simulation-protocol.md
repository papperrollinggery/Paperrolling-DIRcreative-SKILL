# Goal Mode Simulation Protocol

Verified: 2026-05-17

Purpose: make DIRcreative dogfood usable in native Goal mode, where the user may not answer every creative gate with `1`, `通过`, or another manual choice.

## Trigger

Use this protocol when the current message or objective clearly asks for an automated test of the chat workflow, including:

- the incoming message is a `<goal_context>` continuation,
- the objective says `simulate user normal operation`,
- the user says `目标模式状态下我不会给你发1 或者做选择,这是测试`,
- the operator is checking whether the installed skill can run the full chat experience without waiting for a human at each gate.

Do not use this protocol for final live acceptance.

## Frontstage Rule

Goal mode simulation is still chat-first.

The agent must show the same user-visible stages as a live run, but it does not stop after each `用户确认点`. Instead, it immediately records:

```text
模拟用户选择:
<the conservative recommended option and why>
```

Then it continues to the next visible stage.

The user should be able to read the conversation and feel the workflow:

```text
阶段: 目标模式模拟测试
智能体创作内容:
- 当前是自动 dogfood，不等用户发 1。
- 我会展示每个确认点，并用模拟用户选择继续。
- 所有模拟选择都不算真实用户验收。

用户确认点:
这里原本会问用户选 1/2/3。

模拟用户选择:
选择 1，因为它最稳、最符合 brief，并且后续参考图/视频模型风险最低。
```

## Required Stages

Dogfood fixtures must cover both a rough-idea simulation and a complete-idea simulation. The two paths test different failure modes: rough ideas test intake, brainstorming, and taste gates; complete ideas test whether the workflow skips broad ideation without skipping professional segmentation.

For a rough idea simulation:

1. `阶段: 想法读取`
2. `阶段: 导演组会议`
3. `阶段: 故事确认`
4. `阶段: 脚本确认`
5. `阶段: 分镜头确认`
6. `阶段: 视觉方向 / 视觉 bible`
7. `阶段: 参考图方案`
8. `阶段: 出图执行建议`
9. `阶段: 视频生成建议`
11. `阶段: QA 与重试规则`
12. `阶段: 模拟测试结论`

For a complete idea simulation:

1. `阶段: 完整想法读取`
2. `阶段: 导演组会议`
3. `阶段: 故事逻辑确认`
4. `阶段: 脚本确认`
5. `阶段: 专业分镜确认`
6. `阶段: 参考图组方案`
7. `阶段: 出图执行建议`
8. `阶段: 视频生成建议`
10. `阶段: QA 与重试规则`
11. `阶段: 模拟测试结论`

## Choice Policy

The simulated user must choose the option recommended by the director-room council unless the option violates a hard guardrail.

Every simulated choice must include the practical reason:

- story clarity,
- channel fit,
- shot rhythm,
- reference consistency,
- direct video input safety,
- prompt-only boundary,
- assisted-generation readiness.

For generation stages, the simulated choice must select a customer-facing action: first test image, full recommended image pack, prompt-only export, first video model test, or no generation. It must not approve `pre_generation_contract`, raw JSON, YAML, or prompt bodies as the visible user decision.

Do not use `system_default` for creative choices. The decision source is `simulated_fixture`.

## Boundaries

Goal mode simulation may:

- proceed past creative gates without waiting for the user,
- show the full chat transcript in one response or a small number of responses,
- use existing fixtures as test briefs,
- write dry-run artifacts or receipts marked `simulated_fixture`.

Goal mode simulation must not:

- write `.dircreative/runs/live-user-acceptance.yaml`,
- mark `real_user_co_creation_verified: true`,
- call `update_goal`,
- generate real images or videos without explicit user authorization,
- treat a simulated choice as `real_user`,
- hide the workflow in files or terminal output.

## Completion Signal

At the end of a goal-mode simulation, report:

```text
阶段: 模拟测试结论
结果: PASS | NEEDS_FIX
覆盖: <stages covered>
未生成真实图片/视频: true
不计入真实验收: true
下一步真实用户确认点: <one concrete decision>
```

If the simulation exposes a weak stage, fix the project instead of asking the user to choose.

## Receipt Rule

Use a normal dry-run receipt or fixture if a file record is needed. The receipt must state:

```yaml
run_type: dry_run_fixture
decision_source: simulated_fixture
real_user_co_creation_verified: false
live_user_acceptance_receipt_written: false
```

The final live user acceptance receipt remains governed by `docs/film-preproduction/live-user-acceptance-gate.md`.
