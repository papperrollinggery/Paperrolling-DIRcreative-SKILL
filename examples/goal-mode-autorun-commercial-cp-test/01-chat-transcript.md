# Goal Autorun Commercial Creative Production Test

artifact:
  artifact_id: goal-autorun-commercial-cp-chat-v1
  version: 1
  status: reviewed
  owner_skill: chat-facilitator
  created_at: "2026-06-15"
  source_artifact_ids:
    - docs/film-preproduction/goal-autorun-completion-protocol.md
    - docs/film-preproduction/creative-production-integration.md

Purpose: prove Goal mode can run rough idea, complete idea, commercial product ad, Creative Production preflight, and QA without waiting for manual `1/2/3` choices.

This is a dry-run transcript. It is not real user acceptance.

## Transcript

阶段: 目标模式模拟测试
智能体创作内容:
- 当前是 Goal autorun dry-run，不等用户发 1。
- 我会展示每个用户确认点，并记录模拟用户选择。
- Creative Production 只做生成和评审 adapter，不会成为 DIRcreative 真相源。

用户确认点:
这里原本会问是否进入自动 dry-run。

模拟用户选择:
进入 dry-run，因为这能验证完整流程不会卡在手动选择上。

阶段: 想法读取
客户可见预览:
- 一句话方向: 夜班便利店里，一杯自热面把加班者从疲惫拉回清醒。
- 情绪弧线: 冷、饿、赶时间 -> 热气、安静、重新开工。
- 3 个关键画面: 冷蓝办公灯、杯面蒸汽、手机消息变成已完成。

用户确认点:
这个 rough idea 是否正确？

模拟用户选择:
通过，因为商业目标、使用场景和情绪转折都清楚。

阶段: 导演组会议
客户可见预览:
- producer: 9:16 social-first，15 秒，必须前三秒读懂产品用途。
- creative_director: 用克制夜班质感，不做吵闹零食广告。
- director: 人物表演要轻，不靠夸张反应。
- cinematographer: 冷办公室与暖蒸汽形成颜色转折。
- production_designer: 产品形状、杯盖、蒸汽路径先锁定。
- editor: 五镜头比三镜头更稳，能保留使用过程。
- sound_designer: 环境噪声到安静吸气声，后期音频优先。
- model_prompt_engineer: 先做产品身份，再做场景/FOV，再做 storyboard motion。
- continuity_qa: 产品、桌面、人物手部和蒸汽方向不能漂移。

专业判断:
分歧是电影质感想慢，商业广告需要前三秒证明产品。解决方案是第一镜头直接把疲惫场景和产品放在同一画面。

用户确认点:
选电影克制方向、强促销方向，还是折中执行？

模拟用户选择:
选折中执行，因为它兼顾商业证明和影视质感。

阶段: 完整想法读取
智能体创作内容:
- 当前完整想法已包含人物、产品、场景、时长和渠道。
- broad brainstorming 跳过，但故事逻辑、镜头和参考图仍要验证。

用户确认点:
是否按完整想法进入专业分解，而不是重新脑暴？

模拟用户选择:
按完整想法进入专业分解，因为用户目标是执行质量，不是换创意。

阶段: 故事逻辑确认
智能体创作内容:
- business_objective: 证明自热面适合夜班即时恢复。
- audience_context: 夜间办公、便利店、独居或加班人群。
- product_proof: 开盖、蒸汽、可食用热度、继续工作的行为结果。
- brand_assets: dry-run 不强制 logo 素材，但保留杯身标识策略和画面留白。
- product_lock: 产品轮廓、杯盖、杯身材质、蒸汽方向先锁定。
- human_strategy: 人物是夜班工作者，不做夸张吃播表演。
- delivery_priority: 9:16 social-first，前三秒读懂使用场景和产品作用。
- emotional_turn: 疲惫的人重新获得一点秩序。

用户确认点:
这个故事逻辑是否通过？

模拟用户选择:
通过，因为产品利益通过动作和结果可见。

阶段: 专业分镜确认
智能体创作内容:
- SH01 00:00-00:03: 冷办公室与产品同框，建立问题和解决物。
- SH02 00:03-00:06: 手部打开杯盖，蒸汽出现。
- SH03 00:06-00:09: 面体和热气特写，证明产品状态。
- SH04 00:09-00:12: 人物表情恢复，但表演克制。
- SH05 00:12-00:15: 手机消息与产品记忆帧，形成结尾。

用户确认点:
这个五镜头结构是否通过？

模拟用户选择:
通过，因为每个镜头只有一个商业和叙事任务。

阶段: 参考图组方案
智能体创作内容:
- PRODUCT IDENTITY REFERENCE: 锁产品轮廓、杯盖、材质和标识策略。
- SCENE GEOGRAPHY + CAMERA FOV REFERENCE: 锁办公桌、屏幕光、手部路线。
- PROFESSIONAL STORYBOARD + MOTION MAP: 锁五镜头节奏、运动和声音提示。
- CLEAN FIRST/KEY/END FRAMES: 仅用于直接 I2V 测试。

用户确认点:
先生成哪类材料，还是保持 prompt-only？

模拟用户选择:
先做 PRODUCT IDENTITY REFERENCE，因为产品身份不稳会污染后续所有参考图和视频。

阶段: 出图执行建议
客户可见预览:
- 将通过 Creative Production 的 Ads path 生成首张产品身份候选图。
- `render_moodboard_board_widget` 只作为评审 surface。
- 生成候选图会保持 `generated_candidate`，不会自动变成 `user_locked`。

生产状态:
- visual_output_mode: assisted_generation dry-run
- pre_generation_contract.status: pass
- real media generation: false
- live acceptance receipt: false

用户确认点:
是否授权生成已过合同的首张产品身份候选图？

模拟用户选择:
授权 dry-run 记录，不调用真实生成，因为 Goal autorun 不能创建真实媒体。

阶段: 视频生成建议
智能体创作内容:
- Seedance: 可用参考图组和时间顺序提示，但要防止显示 board。
- Kling: 只有 clean first/key/end frame 可作为主输入。
- Runway: 用已锁 clean frame 加短运动提示。
- Veo: 用结构化 subject/action/scene/camera/light/audio 提示。

用户确认点:
首个视频模型测试选哪个？

模拟用户选择:
选 Kling 的 clean first frame 路径作为未来真实测试，因为它最能暴露直接 I2V 兼容性。

阶段: QA 与重试规则
智能体创作内容:
- 若产品像音箱、香薰、空气净化器或香水瓶，回到产品身份参考。
- 若办公室地理漂移，回到 scene geography/FOV。
- 若 storyboard 被视频模型当成画面，改用 clean frame。
- 若 CP candidate 未过 self-QA，不允许用户锁定。

用户确认点:
若首张候选图失败，是 retry 产品身份，还是停止在 prompt-only？

模拟用户选择:
retry 产品身份，因为这是最小纠正层。

阶段: 模拟测试结论
结果: PASS
覆盖: rough idea / complete idea / commercial product ad / Creative Production preflight / QA
未生成真实图片/视频: true
不计入真实验收: true
下一步真实用户确认点: 真实用户是否接受这个 chat-first workflow，并是否授权首张产品身份图生成。

skill_run_receipt:
  run_id: goal-autorun-commercial-cp-2026-06-15
  skill_id: chat-facilitator
  input_artifacts:
    - docs/film-preproduction/goal-autorun-completion-protocol.md
    - docs/film-preproduction/creative-production-integration.md
  output_artifacts:
    - examples/goal-mode-autorun-commercial-cp-test/01-chat-transcript.md
  decisions:
    - "Goal autorun covers Creative Production preflight without real generation."
    - "Every visible user confirmation point records a simulated choice."
    - "Live acceptance remains a separate user decision."
  unresolved_questions:
    - "Real user has not accepted this workflow."
  qa_gate:
    status: pass
    reasons:
      - "Dry-run reaches final conclusion and keeps media/acceptance boundaries."
  next_recommended_skill: co-creation-gate-runtime
