# Live Chat Start Protocol

Verified: 2026-05-17

Purpose: make the installed `dircreative` skill feel usable inside chat from the first reply, without asking the user to inspect files or terminal output.

## Core Rule

The first reply is a production-room gate, not a status report.

The agent must show the current stage, a useful preview, and one decision question. Files are created or updated only after the visible gate is resolved.

## Trigger Mapping

| User input | First visible stage | Do next |
| --- | --- | --- |
| rough idea | `阶段: 想法读取` | restate brief, infer channel/duration risk, ask if brief is right |
| complete story idea | `阶段: 完整想法读取` | mark locked facts, state skipped brainstorming gates, ask story-logic confirmation |
| "测试一下" or "让我感受一下" | earliest unresolved creative gate | show 2-3 options and one question |
| "导演组", "council", "multi-review", "多专家评审", or "compound professional mode" | `阶段: 导演组会议` or `阶段: 想法读取` if the brief is not locked | use Thread-backed council mode when useful; show role judgments, disagreements, options, and one decision question |
| `<goal_context>` or explicit goal-mode simulation | `阶段: 目标模式模拟测试` | show the normal gate, record `模拟用户选择`, and continue without waiting for `1` |
| "继续" or "可以" | earliest unresolved creative gate | resolve the next gate, not image generation |
| user asks for images | current story/script/shot/reference gate | block image generation until reference pack and pre-generation contract pass |
| user changes core premise midstream | `阶段: 中途改需求处理` | name changed upstream decision, mark affected downstream artifacts stale, ask one revision-scope question |

## Mandatory First Reply Shape

For a rough idea:

```text
阶段: 想法读取
智能体创作内容:
- 我理解你的项目是: <one sentence>
- 目标渠道/时长: <inferred or unknown>
- 当前边界: <prompt-only / assisted_generation only if authorized>
- 下一步会进入导演组，给 3 个方向，不会直接生图。

专业判断:
<one sentence about why this gate matters>

用户确认点:
这个 brief 是否正确？正确的话我下一步给你 3 个创意方向。
```

For a complete idea:

```text
阶段: 完整想法读取
智能体创作内容:
- 已锁定: <story/channel/duration/character/product/scene facts>
- 需要验证: <story logic / timing / shot rhythm / model risk>
- 可跳过: 广泛创意发散，因为用户已经给出完整故事方向。

专业判断:
我会先检查故事逻辑和节奏，再拆分镜；不会跳到参考图或生图。

用户确认点:
这些已锁定信息是否正确？正确后我给你专业分镜方案。
```

For a test run:

```text
阶段: <earliest unresolved gate>
智能体创作内容:
1. <recommended option> - <why>
2. <alternative> - <tradeoff>
3. <alternative> - <tradeoff>

我的建议: <one recommendation>

用户确认点:
选 1/2/3，或者说怎么混合。
```

For a council, multi-review, or compound professional mode request:

```text
阶段: 导演组会议
智能体创作内容:
- 我会用导演组模式做多角色评审: 故事/导演、制片/影像、模型风险/连续性 QA 分开压测，再合并成一个选择门。
- 你在当前对话里只会看到角色判断、主要分歧、2-3 个方向和我的建议。
- 后台运行记录和文件只做内部证据；你不需要管理这些过程。

专业判断:
这一步先解决方向、取舍和下游风险，不跳到参考图、提示词或生成。

用户确认点:
如果 brief 已正确，我直接给你 2-3 个方向；如果不正确，请只改 brief。
```

For a midstream change:

```text
阶段: 中途改需求处理
智能体创作内容:
- 变更点: <changed upstream decision>
- 受影响下游: <story/script/shot/reference/prompt/media artifacts now stale>
- 当前边界: 先不继续提示词或媒体生成。

专业判断:
<one sentence about continuity, credibility, or model-risk impact>

用户确认点:
这次修改是只局部替换，还是重写故事目标？
```

For goal-mode simulation:

```text
阶段: 目标模式模拟测试
智能体创作内容:
- 当前是 workflow dogfood，不等用户发 1。
- 我会展示每个用户确认点，并用 `模拟用户选择` 继续。
- 本次不生成真实图片或视频，不写 live-user-acceptance.yaml。

专业判断:
模拟测试可以证明流程是否顺，但不能替代真实用户验收。

用户确认点:
这里原本会要求用户选择。

模拟用户选择:
选 <recommended option>，理由是 <story/channel/shot/reference/model risk reason>。
```

## Prohibited First Replies

- "我已经生成了文件，你去看 examples。"
- "要不要直接出图？"
- "我先生成一张参考图。"
- raw YAML or JSON as the main answer.
- thread IDs, dispatch records, worker cleanup details, or other backend mechanics as the main answer.
- five creative questions in one message.
- claiming a simulated fixture choice is real user approval.
- waiting for `1` after a goal-mode simulation trigger.
- continuing old prompts or media generation after a core midstream change.

## Installed Skill Requirement

The installed skill at `~/.codex/skills/dircreative` must preserve this protocol. Validation should fail if the root skill, chat facilitator, or chat interface docs stop requiring the earliest unresolved gate, one user decision, prompt-only boundary, and QA/retry visibility.

Visual availability does not change the first-reply gate. When supported, the first reply may add the smallest validated visual view after the readable stage content; when unsupported, render the declared fallback without changing the decision sequence or asking the user to switch clients.
