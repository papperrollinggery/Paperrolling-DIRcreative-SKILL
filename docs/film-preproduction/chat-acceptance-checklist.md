# Chat Acceptance Checklist

Verified: 2026-05-16

Purpose: prevent DIRcreative from passing file validation while still feeling bad in chat.

## Core Acceptance Rule

The user must be able to understand the workflow from the chat alone.

Files are receipts. Chat is the product surface.

## Required Checks

- The agent starts from the earliest unresolved gate.
- The installed root skill follows `docs/film-preproduction/live-chat-start-protocol.md` for the first reply.
- The agent does not jump to image generation or reference strategy before story, script, shot, and visual bible gates.
- The agent asks one user decision at a time.
- The agent labels `智能体创作内容`, `用户确认点`, `模拟用户选择`, `prompt-only产物`, and `当前没有生成真实图片或视频` when relevant.
- The agent uses professional film language: `专业判断`, `取舍`, `执行影响`, `叙事任务`, `机位/镜头`, `主体调度`, `构图层次`, `声音剪辑`, and `模型风险`.
- The agent explains channel, duration, story, shot, reference, and model tradeoffs before asking for approval.
- The agent distinguishes a complete user idea from an early brainstorm.
- If the user already has a complete idea, the agent may skip broad concept generation with a visible reason, then move to story validation, script timing, and shot segmentation.
- Shot count is dynamic. The agent may choose 3, 5, 6, or more shots when rhythm and clarity require it.
- The agent distinguishes story duration from video model generation-unit limit. `15s` can mean the whole story is 15 seconds, or it can mean each generation group is capped at 15 seconds.
- If duration is ambiguous, the agent asks one clarification question before scripting; in goal-mode simulation it records a visible assumption and simulated choice.
- For 30s, 60s, 90s, or 180s stories, the agent writes the whole story arc first, then splits it into 5-15s sequence units. It must not compress the entire story into one 15s script just because a video model has a 15s limit.
- If the user changes a core premise midstream, the agent enters `阶段: 中途改需求处理`, marks affected downstream artifacts stale, blocks prompt/media generation, and asks one revision-scope question.
- Reference image count is dynamic. The agent plans the fewest model-safe assets that still preserve identity, scene, motion, and clean direct I2V inputs.
- Dense storyboard boards are planning-only unless a model policy explicitly allows them.
- Clean frames must be text-free, panel-free, label-free, and separately approved or generated.
- `阶段: 出图执行建议` is the customer-facing gate before image work. It says how many images, what each image does, which one to test first, what cannot be fed directly to video models, and whether the user wants one test image, the full pack, or prompt-only output.
- `pre_generation_contract` is backstage evidence. It must exist and pass before assisted generation, but the user is not asked to approve raw JSON, YAML, or contract text in chat.
- `阶段: 视频生成建议` is the customer-facing gate before video work. It says which model/sequence to test first, which reference assets bind to which slots, and what is blocked until clean frames are generated or imported.
- Prompt-only mode is explicit; the agent never pretends media exists.
- Simulated fixture decisions are labeled and never converted into real user approval.
- Goal mode simulation does not wait for the user to send `1`; it shows the gate, records `模拟用户选择`, continues to `阶段: 模拟测试结论`, and remains separate from live acceptance.
- QA and retry rules are visible before assisted image or video generation. The chat names self-QA, failure IDs, blockers, and the smallest-artifact retry route.

## Failure Cases

Fail the chat surface if:

- the first response asks for image generation before story/script/shot review,
- the shot list is only a list of vague camera moves,
- a longform story is collapsed into one 15s script because the model generation cap was mistaken for story duration,
- a midstream core change continues into old prompts or generation without stale-artifact handling,
- the answer says "cinematic" without production reasoning,
- the reference plan is one overloaded board with no direct-input policy,
- the pre-generation contract is missing or merged into a vague prompt summary,
- the user is asked to approve raw JSON, YAML, prompt bodies, or `pre_generation_contract` instead of choosing an image/video execution action,
- video prompt summaries are shown as internal model text before a customer-facing `阶段: 视频生成建议`,
- the user is asked five creative questions at once,
- a dry-run fixture claims real user confirmation,
- a declared goal-mode simulation stops at every confirmation and waits for manual numeric choices,
- a dense storyboard board is treated as a Kling or Runway first frame.

## Complete-Idea Scenario Requirement

When the user gives a complete idea and says they only need professional segmentation:

1. Restate the complete idea and identify what is already locked.
2. Explain which brainstorming gates can be skipped and why.
3. Validate the story logic before writing shots.
4. Choose shot count from rhythm, readability, and model generation constraints.
5. Show professional shot cards in chat.
6. Plan reference boards and clean frames after shot approval.
7. Show `阶段: 出图执行建议`: recommended image count, first test image, direct-video-safe assets, planning-only assets, and prompt-only vs assisted generation choice.
8. Show `阶段: 视频生成建议`: model/sequence test order, reference bindings, blocked inputs, and whether the user wants to test one model first.
9. Show QA/retry rules before any assisted generation or user lock request.

This scenario is covered by `examples/complete-idea-segmentation-test`.
