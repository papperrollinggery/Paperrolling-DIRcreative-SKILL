# Film Preproduction Docs

This directory stores the system design, execution roadmap, research base, schemas, examples, and QA rules for the film preproduction agent workflow.

## Structure

```text
01-system-plan.md
02-execution-roadmap.md
03-office-hours-optimization-plan.md
04-goal-mode-handoff.md
05-skill-integration-architecture.md
06-gstack-execution-goal.md
phase-contracts.yaml
prompt-pattern-registry.json
research/
schemas/
templates/
qa/
```

## Document Order

For active runtime behavior, read only the selected path:

1. `runtime-contracts.md` — canonical owner index and compatibility matrix.
2. `skills/dircreative/runtime/routing-policy.yaml` — selected mode and files.
3. Exactly one Fast, Studio, or Delivery Route Card.
4. Only the task files returned by the router.

`01-system-plan.md`, roadmaps, Goal/gstack plans, and
`05-skill-integration-architecture.md` preserve architecture history and fixture
planning. They are not startup reads and do not override the active owner index.
`phase-contracts.yaml` owns repository fixture planning, not chat runtime.

Presentation guides such as `chat-co-creation-interface.md` and
`live-chat-start-protocol.md` explain how to show the result; machine-readable
routing, gates, persistence, and schemas remain authoritative.

## Prompt System Upgrade Bundle

研究、规范和实现前置文档：

1. research/prompt-system-research-2026-07-12.md：官方、专业资料、GitHub 结构与现状基线。
2. prompt-system-upgrade-prd-v1.md：产品需求、Prompt IR、评分、执行路线和完成门禁。
3. prompt-authoring-standard-v1.md：图像/视频 prompt 的构图、动作、运镜、四层 look、声音、转场和模型适配写法。
4. asset-intake-and-state-standard-v1.md：用户/客户现成素材的读取、复用、继承、锁定和状态规则。
5. prompt-qa-and-incident-runbook-v1.md：生成后确认、故障分类、单变量重试和 receipt。
6. schemas/prompt-ir.schema.json：可执行的 Draft 2020-12 Prompt IR v1.1 schema；schemas/prompt-ir.yaml 只作为作者模板。
7. scripts/dircreative_prompt_compiler.py：Prompt IR 语义校验、模型表面编译、内部字段清洗与 prompt-only handoff。
8. tests/fixtures/prompt-system：角色+场景最小输入、多人多资产 15 秒、30 秒分段、模型 adapter 和负向污染 fixtures。
9. examples/seedance-mirror-turn-10s：10 秒 9:16 主 fixture；最终 Seedance 文本必须由 compiler 确定性生成。

当前 Prompt IR、compiler 和 fixtures 可在本地执行结构验证；它们不代表 TabNow/TapNow、Seedance 或其他外部生成表面已经真实执行。

~~~text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_prompt_compiler.py validate <prompt-ir.json>
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_prompt_compiler.py compile <prompt-ir.json>
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_prompt_fixture_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_headless_acceptance_audit.py
~~~

目标超过一个生成单元时，编译器 fail-closed；必须用 `--unit-index 1`、`--unit-index 2` 逐段导出。每段 prompt 重置为本地 0 秒时间轴并携带入段/出段状态；不支持原生音频时，声音 handoff 只出现在 `inspect` 结果中。

无头验收在隔离 subprocess 中真实写出 Fast 文案修订和 Studio 完整广告片
脚本/分镜答案，再逐字对比 reviewed snapshots。它不调用已安装 Skill、不创建
真实项目，也不代表外部模型生成或真人创意验收。
