# Chat Co-Creation Interface

Verified: 2026-05-16

Purpose: make DIRcreative usable in a chat interface, not only through files or terminal reports.

Companion contract: `docs/film-preproduction/chat-stage-gate-integrity.md`.

## Core Rule

DIRcreative is chat-first and artifact-backed.

The user should see a clear conversation:

1. what stage we are in,
2. what the agent produced,
3. what the user must decide,
4. which options are available,
5. what happens after the choice.

Files remain the durable record. They must not be the primary user experience.

## Live Operating Loop

For a live user run, every stage follows this loop:

1. Show the current stage in chat.
2. Show a short preview of the agent-created work.
3. Ask one decision question.
4. Wait for the user answer.
5. Record the decision in the artifact.
6. Show what was recorded and what the next visible output will be.
7. Continue to the next stage.

Do not perform steps 5-7 if the user has not answered the gate.

## Goal Mode Simulation Loop

When the current input is a `<goal_context>` continuation or explicitly says the user will not keep choosing `1` during a test, use `docs/film-preproduction/goal-mode-simulation-protocol.md`.

Goal mode simulation uses the same frontstage messages as a live run, but it does not wait at each gate. It must:

1. Show the current `用户确认点`.
2. Immediately show `模拟用户选择`.
3. Explain the choice in one production reason.
4. Continue to the next stage.
5. End with `阶段: 模拟测试结论`.

It must not create `.dircreative/runs/live-user-acceptance.yaml`, mark `real_user_co_creation_verified: true`, or treat the simulated pass as goal completion.

## Live Run Start Rule

When a user says "可以", "继续", "测试一下", or asks to see the workflow, do not jump to image/reference strategy.

When a user or goal objective asks to simulate normal operation in Goal mode and says no manual choices will be provided, do not wait for `1`. Enter `阶段: 目标模式模拟测试`, show the same gates, mark `模拟用户选择`, and continue.

Start from the earliest unresolved creative gate:

1. If the brief is not locked, show idea intake.
2. If the concept is not locked, run the director room and show 3 story directions.
3. If the story is not locked, show logline, beats, and emotional turn.
4. If the script is not locked, show the timed script and audio/dialogue policy.
5. If the shot list is not locked, show professional shot cards.
6. If visual direction or visual bible is not locked, show style options and visual locks.
7. Only after story/script/shot/visual bible gates are resolved may DIRcreative ask about reference pack, clean frames, image generation, or model video prompts.

Reference strategy must wait until story/script/shot/visual bible gates are visible and approved.

The installed root skill must also follow `docs/film-preproduction/live-chat-start-protocol.md`. That file defines the exact first-message shape for rough ideas, complete ideas, test runs, and image requests.

## Frontstage And Backstage

Frontstage is the chat message. It must be readable without opening a file.

Backstage is the artifact. It records source ids, receipts, YAML contracts, manifests, and QA evidence.

The frontstage must never say "go read the file" as the main explanation. The file is a receipt, not the interface.

Codex Threads are backstage execution resources. When the user asks for council, multi-review, or compound professional mode, the chat should say that the director-room will separate professional viewpoints and return a merged recommendation. Do not expose thread IDs, dispatch YAML, worker cleanup details, or raw worker notes as the main answer. The main-controller thread owns the user-facing synthesis; worker findings become usable only after they are reconciled into artifacts, receipts, docs, manifests, or validation output.

## Frontstage Copy Hygiene

Every visible gate must follow `docs/film-preproduction/professional-agent-voice-standard.md` and run a humanizer pass before it is sent. This applies to creative directions, production plans, script notes, shot explanations, prompt-only exports, generation recommendations, QA/retry notes, and summaries.

The point is not to sound friendlier. The point is to remove machine-written habits while keeping DIRcreative's production judgment.

Rules:

- Lead with the current decision and the production reason.
- Say what changed downstream: story lock, script lock, shot count, reference role, prompt-only export, generation block, QA retry variable, or next gate.
- Use concrete nouns and numbers when available. `5 镜头版本，12 秒前完成情绪转折` is useful; `更完整、更有电影感` is not.
- Keep one decision question. Do not pad it with `你也可以告诉我更多想法` unless that is the actual gate.
- In Chinese, avoid AI-style filler such as `此外`, `值得注意的是`, `整体来看`, `这不仅是`, `充分体现`, `赋能`, and `沉浸式体验`.
- In English, avoid `Certainly`, `Here is`, `Let's dive in`, `showcase`, `seamless`, `elevate`, `vibrant`, and generic upbeat closers.
- Do not use a neat three-part slogan when two specific options or four concrete constraints would be more honest.
- Do not end a gate with a generic offer. End with the one decision the user must make.

Prompt-only handoffs need an extra boundary:

- The paste-ready prompt may be structured and explicit.
- The surrounding DIRcreative explanation must stay short, plain, and specific.
- State whether no image/video was generated, which artifact the prompt inherits from, and what QA would check after external generation.
- Do not frame a prompt-only handoff as a finished creative win. It is a handoff, not proof that media exists.

## Chat Shape

Every creative gate should use this shape:

```text
阶段: <current stage>
我先给你 3 个方向:
1. <recommended option> - <why>
2. <alternative option> - <tradeoff>
3. <alternative option> - <tradeoff>

我的建议: <one short recommendation>
你现在只需要决定: 选 1/2/3，或者说怎么混合。
```

After the user answers:

```text
已记录: <user choice>
我会基于这个继续到 <next stage>。
下一步我会给你看 <next visible output>。
```

## One Question Rule

Ask one key question at a time.

Do not ask concept, style, duration, reference pack, image generation, and video model choice in one message.

## Required Visible Gates

| Stage | Chat Output | User Question |
| --- | --- | --- |
| idea intake | restated brief and constraints | Is this brief right? |
| director room | 3 concept directions | Which direction, or how to mix? |
| story approval | logline, beats, emotional turn | Should this story become the script? |
| script approval | timed script and audio/dialogue policy | Does this script pass? |
| shot list approval | shot count, timing, lens, motion, action | Does this shot structure pass? |
| visual direction | 3 style directions | Which look should guide the film? |
| visual bible approval | identity, palette, material, avoid locks | Should these visual locks drive references? |
| sequence plan | duration and shot count options | One-pass, stepwise, or batch? |
| reference pack | reference image plan | Which pack strategy should lock? |
| image prompt export | image prompt summary | Prompt-only or generate images? |
| video prompt export | model-specific prompt summary | Which model should be tested first? |

## Ad Reference Pack Gate

For ad films, do not jump from a user's "generate clean frames" answer directly into one image.

First show the ad reference pack generation plan:

- product identity board,
- lighting/material/style board,
- storyboard/motion board,
- clean frames.

Then ask whether to generate the full pack, a partial pack, or prompts only.

Clean frames can be generated only after the chat makes clear what they do and what they do not do. They are direct I2V inputs, not product identity boards and not storyboard boards.

## Stage Message Templates

### Idea Intake

```text
阶段: 想法读取
智能体创作内容:
- 我理解你的项目是: <one sentence>
- 目标渠道: <channel>
- 时长/画幅: <duration/aspect>
- 当前边界: <prompt-only / image generation / video generation>

用户确认点:
这个 brief 是否正确？如果正确，我下一步给你 3 个创意方向。
```

### Director Room

```text
阶段: 导演组创意方向
智能体创作内容:
1. <direction A> - <why it works>
2. <direction B> - <tradeoff>
3. <direction C> - <tradeoff>

我的建议: <recommended direction and why>

用户确认点:
选 1/2/3，或者说你想怎么混合。
```

### Goal Mode Simulation

```text
阶段: 目标模式模拟测试
智能体创作内容:
- 当前是自动 dogfood，不等用户发 1。
- 我会展示每个确认点，并用模拟用户选择继续。
- 所有模拟选择都不算真实用户验收。

专业判断:
这能检查真实聊天体验是否连贯，但不能关闭 goal。

用户确认点:
这里原本会问用户选 1/2/3。

模拟用户选择:
选 <recommended option>，因为 <professional reason>。
```

### Script And Shot Preview

```text
阶段: 脚本预览
智能体创作内容:
- <short script or beat preview>
- <dialogue/no-dialogue policy>
- <audio intent>

用户确认点:
这个脚本是否通过？通过后我再给你分镜头表。
```

```text
阶段: 分镜头确认
智能体创作内容:
- <shot count and timing>
- <professional shot cards with timecode, story beat, shot type, lens, camera support, camera motion, focus, blocking, scene layers, continuity, audio, and model notes>

用户确认点:
这个分镜结构是否通过？通过后我继续做视觉风格和视觉 bible。
```

Shot preview must follow `docs/film-preproduction/shot-language-standard.md`; do not reduce shots to only `camera movement / action / sound`.

### Reference And Prompt Export

```text
阶段: 参考图和提示词导出
智能体创作内容:
- 参考图组: <product identity board / lighting material board / storyboard motion board / clean frames>
- 不能直接喂给视频模型: <risks>
- 镜头运动策略: <camera movement and subject movement map>
- 已准备的 prompt-only 产物: <image/video prompt summaries>

未生成真实图片/视频:
<state plainly>

用户确认点:
下一步你要继续 prompt-only，还是授权生成参考图/首帧/视频？
```

## Message Boundaries

- Show enough output for the user to judge.
- Do not dump raw YAML.
- Do not hide creative choices inside files.
- Do not claim user approval until the user chose in chat.
- Do not wait for the user to send `1` during a declared goal-mode simulation.
- Do not generate media unless the user explicitly authorizes it.
- Do not generate a single clean frame before showing the ad reference pack plan for an ad-film workflow.
- Do not treat "可以", "继续", or "测试一下" as approval to skip story, script, shot list, or visual bible gates.
- Do not ask all-reference, hybrid, per-shot I2V, clean-frame, or image generation choices before the earliest unresolved creative gate is handled.
- If using `simulated_fixture`, say it is simulated.
- Treat image prompt summary, video prompt summary, and QA/retry as decision gates, not afterthought summaries.

## Visual Decision Enhancement

When the active surface supports chat visualization, follow `chat-inline-visualization-interface.md` and build a validated `dircreative.chat-visualization@1.0` view from current hash-bound artifacts.

- Keep the same `阶段 -> 客户可见预览 -> 专业判断 -> 用户确认点` sequence.
- Show one current decision, one primary action, and at most one secondary action.
- Treat option selection, comparison, and expansion as presentation-only until a human-readable conversation intent is submitted.
- Revalidate the current gate before writing any decision, lock, stale marker, authorization, QA verdict, or receipt.
- Use the declared Markdown/table/Mermaid fallback when visualization is unavailable or fails.

The visual view may improve scannability, but it cannot replace the visible question or become the source of approval.

## Good Chat Behavior

- Lead with the current decision.
- Keep options short and visually scannable.
- Label `智能体创作内容`, `用户确认点`, `模拟用户选择`, `prompt-only产物`, and `未生成真实图片/视频` when relevant.
- Explain the practical impact of a choice in one sentence.
- Continue only after the gate is resolved.

## Bad Chat Behavior

- "I finished the files; go inspect examples."
- A raw YAML or JSON dump as the main output.
- A terminal command as the primary demo.
- Asking five creative questions at once.
- Auto-selecting a style because it seems likely.
- Saying a live user confirmed something when only a fixture selected it.
