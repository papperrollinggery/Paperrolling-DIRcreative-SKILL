# Live Chat Acceptance Runbook


## V2 Operator Prompt

Use this prompt for a new acceptance session. The historical checklist below
remains a v1 fixture reader; it does not add approval stages or model limits.
The acceptance pass must happen in chat. Technical success never supplies a
user acceptance statement.

```text
我要做一次 DIRcreative 真实聊天验收。
$dircreative 使用当前核验过的安装，在独立测试目录完成我给出的创作请求。
先返回可用成果，复用完整brief与已有授权；普通故事、剧本、分镜和参考规划不逐项确认。
按请求区分客户故事、技术前期和真实媒体。导演组与创意组的联合/并行请求使用真实可用子代理，不能模拟已派发。
保持用户给出的故事时长、模型、人物、台词与来源；生成单元按所选模型当前能力和表演容量划分，不套固定15秒上限。
仅实际未授权副作用或未解决关键方向需要询问；未授权图片/视频时只交付对应文本或提示词。
没有真实用户明确接受，不写live-user-acceptance.yaml，不宣称用户验收通过。
```

## Historical V1 Acceptance Reference

The following sections describe the retained v1 rehearsal and evidence format.
Their fixed stages, confirmation sequence and council roster are not active
instructions for new v2 sessions.

Verified: 2026-05-17

Purpose: run the final real-user acceptance pass without confusing it with a fixture, terminal demo, goal-mode simulation, or agent-only review.

Goal-mode simulation is covered by `docs/film-preproduction/goal-mode-simulation-protocol.md`. A simulation may auto-select gates with `模拟用户选择`, but it is not an acceptance pass.

## Start Condition

Use this runbook only after:

- `python3 scripts/dircreative_release_gate.py` reports `RELEASE_GATE: PASS`,
- the installed skill at `~/.codex/skills/dircreative` contains `Live Chat Start Contract`,
- the user is present in chat and willing to judge the workflow.
- if Creative Production was used, its receipt records `render_moodboard_board_widget` as a review surface only and writes generated candidates back into DIRcreative artifacts or `.dircreative/runs/`.

## Acceptance Pass Contract

The acceptance pass must happen in chat.

Do not ask the user to inspect raw files as the main experience. Do not create `.dircreative/runs/live-user-acceptance.yaml` until the user explicitly says the workflow is acceptable.

Do not create `.dircreative/runs/live-user-acceptance.yaml` after a goal-mode simulation, even if the simulated result is `PASS`.

Do not create `.dircreative/runs/live-user-acceptance.yaml` from a Creative Production widget, generated candidate, HTML page, local URL, screenshot, or Goal autorun transcript. Those can support chat evidence only after the real user explicitly accepts the workflow.

## Operator Prompt

Use this exact operator prompt when starting the acceptance pass:

```text
我要做一次 DIRcreative 真实聊天验收。

请给我一个一句话想法或完整想法。我会按 installed dircreative skill 跑：
想法读取 -> 导演组 -> 故事/脚本 -> 动态分镜 -> 参考图方案 -> 出图执行建议 -> Seedance/Kling/Runway/Veo 视频生成建议 -> QA/重试规则。

我不会生成真实图片或视频，除非你明确授权。每一步我只问一个确认问题。
如果进入 Creative Production，我只把它作为出图和评审 adapter；`render_moodboard_board_widget` 只是评审面，不是项目真相源。生成候选图必须先自检，再由你明确 lock / reject / retry。
如果你说 15 秒，我会先判断它是故事总时长，还是每组视频生成上限；长故事会先写完整结构，再拆成每组不超过 15 秒。
如果你指出故事、剧本、分镜、参考图、prompt 或 workflow 不专业，我会先开启反驳型议会审核：用户视角、影视专家视角、产品经理视角、Skill 开发者视角、代码研究员视角，然后只做最小必要修正。
如果我使用 Codex worker thread，我会说明它是主控线程、一次性只读 worker、隔离 worktree worker，还是可复用研究 thread；一次性 worker 用完会归档，不能替代项目文件和验收 receipt。
生成前合同、JSON prompt、YAML manifest 只做后台证据，不让你在聊天里审批内部文件。
最后你需要明确说：通过 / 不通过 / 哪些地方还不满意。
```

## Required Chat Stages To Show

For rough ideas:

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

For complete ideas:

1. `阶段: 完整想法读取`
2. `阶段: 导演组会议`
3. `阶段: 故事逻辑确认`
4. `阶段: 专业分镜确认`
5. `阶段: 参考图组方案`
6. `阶段: 出图执行建议`
7. `阶段: 视频生成建议`
9. `阶段: QA 与重试规则`

## User Decision Requirements

Record real user decisions in chat:

- concept/story direction choice,
- script pass or requested changes,
- shot structure pass or requested changes,
- visual/reference strategy pass or requested changes,
- how many images to generate, which image to test first, or whether to stay prompt-only,
- which video model/sequence to test first after usable images exist,
- if Creative Production review was shown, which candidate was locked, rejected, retried, or left pending,
- final acceptance statement,
- any council adversarial review triggered by user dissatisfaction,
- any Codex worker thread used, its class, and whether it was archived or kept reusable.

The final statement must be explicit. Examples:

- "通过，这个 skill 当前流程我认可。"
- "不通过，分镜专业度还不够。"
- "基本通过，但参考图方案还要继续修。"

## Receipt Creation Rule

If the user accepts, copy `docs/film-preproduction/templates/live-user-acceptance.template.yaml` to `.dircreative/runs/live-user-acceptance.yaml` and fill every required field.

Required values:

- `artifact.status: approved`
- `user_acceptance.status: accepted`
- `user_acceptance.accepted_by_user: true`
- `user_acceptance.real_user_co_creation_verified: true`
- `chat_evidence.installed_skill_checked: true`
- `accepted_scope.accepted_items` includes every item from `accepted_scope.checklist`
- `unresolved_blockers.items: []`
- `qa_gate.status: pass`
- if Creative Production evidence was used, `chat_evidence` names the review surface and the DIRcreative receipt that owns generated candidate status.

If the user does not accept, do not create an accepted receipt. Record the blocker in a normal checkpoint or continue fixing the project.

## Final Verification

After an accepted receipt exists, run:

```bash
python3 scripts/dircreative_goal_audit.py --require-installed
python3 scripts/validate_project.py
python3 scripts/dircreative_release_gate.py
```

The goal can be marked complete only when `dircreative_goal_audit.py --require-installed` prints:

```text
TECHNICAL_READINESS: PASS
GOAL_COMPLETE: YES
```

Before real acceptance is recorded, the expected audit state is:

```text
TECHNICAL_READINESS: PASS
GOAL_COMPLETE: NO
```
