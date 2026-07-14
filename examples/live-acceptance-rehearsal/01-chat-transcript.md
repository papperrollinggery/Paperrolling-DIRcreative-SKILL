# Live Acceptance Rehearsal Chat Transcript

artifact:
  artifact_id: live-acceptance-rehearsal-chat-transcript-v1
  version: 1.0.0
  source_artifact_ids:
    - live-chat-acceptance-runbook
    - goal-mode-simulation-chat-transcript-v1
    - goal-mode-rough-idea-simulation-chat-transcript-v1
  status: approved
  owner_skill: chat-facilitator

## Purpose

Show the final real-user acceptance surface before a real user is present. This is a rehearsal only.

It must not create `.dircreative/runs/live-user-acceptance.yaml`, must not set `real_user_co_creation_verified: true`, and must not mark the goal complete.

## Rehearsal Transcript

DIRcreative:

```text
阶段: 真实聊天验收预演
智能体创作内容:
- 这是验收预演，不是真实用户验收。
- 我会展示真实验收时用户会看到的聊天表面。
- 当前使用模拟用户选择继续，不等用户发 1。
- 不生成真实图片或视频。
- 不写 live-user-acceptance.yaml。

专业判断:
真实验收必须让用户在聊天界面判断，而不是让用户去读 examples、YAML 或终端输出。
```

DIRcreative:

```text
阶段: 验收入口
智能体创作内容:
请给我一个一句话想法或完整想法。我会按 installed dircreative skill 跑:
想法读取 -> 导演组 -> 故事/脚本 -> 动态分镜 -> 参考图方案 -> 出图执行建议 -> Seedance/Kling/Runway/Veo 视频生成建议 -> QA/重试规则。

我不会生成真实图片或视频，除非你明确授权。每一步我只问一个确认问题。
如果你指出故事、剧本、分镜、参考图、prompt 或 workflow 不专业，我会先开启反驳型议会审核：用户视角、影视专家视角、产品经理视角、Skill 开发者视角、代码研究员视角，然后只做最小必要修正。
如果我使用 Codex worker thread，我会说明它是主控线程、一次性只读 worker、隔离 worktree worker，还是可复用研究 thread；一次性 worker 用完会归档，不能替代项目文件和验收 receipt。
出图合同、JSON prompt、YAML manifest 只做后台证据，不在聊天里让你审批内部文件。
最后你需要明确说: 通过 / 不通过 / 哪些地方还不满意。

用户确认点:
给一句话想法，还是给完整想法？

模拟用户选择:
先测试一句话想法。理由: 一句话流程最能暴露共创、导演组、脚本、分镜、参考图和提示词是否连贯。
```

DIRcreative:

```text
阶段: 想法读取
智能体创作内容:
- 原始想法: 做一条 15 秒竖屏自热面杯广告，温暖、电影感、适合深夜工作者，不要吵闹零食广告感。
- 渠道/时长: 竖屏短视频广告 / 15 秒。
- 初始风险: 产品可能被氛围盖住；蒸汽可能被模型夸张；包装小字不能承担识别。

用户确认点:
这个 brief 是否正确？

模拟用户选择:
正确。理由: 产品、情绪、渠道和禁止项足够进入导演组。
```

DIRcreative:

```text
阶段: 导演组会议
智能体创作内容:
- producer: 15 秒广告先保证产品可读，不能只做氛围。
- creative_director: 核心是冷屏幕被热汤蒸汽变暖。
- director: 表演克制，拍真实工作者从疲惫到稳定。
- screenwriter: 无对白，用动作和声音讲清产品启动、热气、第一口。
- cinematographer: 必须有 macro proof 证明封条、蒸汽和汤面。
- production_designer: 杯型、封条、杯盖、桌面道具从产品板统一继承。
- editor: 5 镜头比 3 镜头更稳，能保住产品动作和情绪转折。
- sound_designer: 办公室 hum、雨声、封条声、热汤声、停顿要进入分镜。
- model_prompt_engineer: storyboard board 只做规划；Kling/Runway 只吃无字 clean frames。
- continuity_qa: 产品、办公室、灯光、蒸汽密度、手和杯的位置必须锁定。

给出的 3 个方向:
1. Last Light At The Desk: 深夜办公室，蒸汽把屏幕冷光变暖，产品最清楚。
2. Platform Warmth: 雨夜站台，用杯子暖手，氛围更孤独。
3. Night Driver Pause: 司机短暂停车加热，动作更强但产品更难拍清。

用户确认点:
选 1/2/3，或者说怎么混合。

模拟用户选择:
选 1。理由: 15 秒内最容易讲清产品、人物情绪和参考图结构。
```

DIRcreative:

```text
阶段: 故事确认
智能体创作内容:
- Logline: 深夜办公室里，一杯自热面把冷屏幕疲惫变成一个温暖暂停。
- 节拍: 冷光疲惫 / 拉开封条 / 蒸汽穿过蓝光 / 第一口放松 / 产品英雄帧。
- 渠道判断: 3 秒内建立需求，6 秒内完成产品动作，12 秒前给情绪转折。

用户确认点:
这个故事方向是否通过？

模拟用户选择:
通过。理由: 需求、动作、情绪和产品记忆帧都可视化。
```

DIRcreative:

```text
阶段: 脚本确认
智能体创作内容:
00:00-00:03 冷屏幕光，深夜工位，面杯还没打开。
00:03-00:06 手拉红色封条，热量指示变暖。
00:06-00:09 蒸汽升起，穿过屏幕蓝光。
00:09-00:12 工作者喝第一口，肩膀放松。
00:12-00:15 产品英雄帧，窗外雨夜，文案只放最终 packshot。

声音策略:
无对白。办公室 hum、雨声、封条声、杯盖摩擦、热汤细声、短暂停顿。

用户确认点:
脚本是否通过？

模拟用户选择:
通过。理由: 15 秒信息密度合适，产品动作和情绪都没有被省掉。
```

DIRcreative:

```text
阶段: 分镜头确认
智能体创作内容:
N01 00:00-00:03 | Need-state hook | MS / 28mm / slider push
- 叙事任务: 建立深夜疲惫和未打开产品。
- 主体调度: 人物右手停在鼠标旁，杯子在前景左三分线。
- 声音剪辑: 低办公室 hum、雨声、键盘停顿。
- 模型风险: 宽镜头产品可能不清，后续必须有 macro proof。

N02 00:03-00:06 | Product activation proof | ECU / 85mm macro / locked-off
- 叙事任务: 清楚看到红色封条被拉开。
- 主体调度: 手从右入画拉封条，动作只做一次。
- 声音剪辑: 封条轻响、杯盖摩擦声。
- 模型风险: 包装文字不要在这一镜承担品牌识别。

N03 00:06-00:09 | Heat reveal | CU / 50mm / motivated tilt-up
- 叙事任务: 蒸汽把冷蓝屏幕光转成温暖感。
- 主体调度: 人物不夸张，只让呼吸和肩膀微松。
- 声音剪辑: 热汤细声和呼吸进入。
- 模型风险: 蒸汽不能爆炸式扩散，需要 clean frame 控制密度。

N04 00:09-00:12 | Human reset | MCU / 50mm / small dolly-in
- 叙事任务: 第一口后从疲惫变稳定。
- 主体调度: 杯子从胸前到嘴边，眼神从屏幕移到杯身。
- 声音剪辑: 轻吸一口，短暂停顿。
- 模型风险: 手和杯口接触易漂移，Kling/Runway 应用 clean first frame。

N05 00:12-00:15 | Product memory frame | Packshot / 70mm / locked-off
- 叙事任务: 留下产品、热汤和深夜场景记忆。
- 主体调度: 人物手离开杯身，只保留桌面静物。
- 声音剪辑: 雨声回到背景，音乐低量收尾。
- 模型风险: 文案和包装文字必须来自产品板或单独 packshot，不塞进分镜板小字。

用户确认点:
这个 5 镜头分镜是否通过？

模拟用户选择:
通过。理由: 镜头数由广告节奏决定，5 镜头保护产品动作、情绪转折和模型可读性。
```

DIRcreative:

```text
阶段: 参考图方案
智能体创作内容:
- product identity board: 锁杯型、红封条、汤面、蒸汽。不是直接视频首帧。
- office environment/FOV board: 锁办公室、桌面轴线、屏幕、窗、灯光方向。planning only。
- lighting/material/style board: 锁蓝/琥珀灯光、纸杯、汤面、蒸汽、抗鱼鳞材质。planning only。
- storyboard/motion board: 给人和 Seedance/Veo 看镜头顺序和运动。不能直接喂 Kling/Runway。
- clean N01/N05 frames: 无文字、无分栏、无箭头，锁定后才可做直接 I2V。

用户确认点:
采用 5 组图方案，还是压缩成更少的图？

模拟用户选择:
采用 5 组图方案。理由: 用最少资产覆盖产品身份、场景、风格、运动和直接 I2V 输入。
```

DIRcreative:

```text
阶段: 出图执行建议
客户可见预览:
- 第一张只测产品身份，不混入办公室、人物手势或分镜。
- 产品通过后再做 office/FOV、lighting/material/style、storyboard/motion board 和 clean N01/N05 frames。

智能体创作内容:
- 建议先出 1 张 `PRODUCT IDENTITY REFERENCE`，只锁产品，不混入办公室、人物手势或分镜。
- 通过 self-QA 后再出 office/FOV、lighting/material/style、professional storyboard/motion board、clean N01/N05 frames。
- storyboard/motion board、style board、带文字说明的规划板不能直接喂 Kling/Runway 做首尾帧；只有无字 clean frame 可作为直接 I2V 输入。
- 后台证据已准备: pre_generation_contract.status: pass、JSON-first image prompts、direct video input policy；不让用户审批 raw JSON/YAML。
- 固定材质防伪影后缀默认关闭；只在记录到具体材质/几何失败 ID 的单次重试或内部 A/B 中启用。

当前没有生成真实图片或视频。

用户确认点:
先试 1 张产品身份参考图，还是保持 prompt-only 看视频生成建议？

模拟用户选择:
保持 prompt-only。理由: 当前验收预演只验证聊天表面；真实执行时先测产品身份图最稳。
```

DIRcreative:

```text
阶段: 视频生成建议
客户可见预览:
- 第一轮建议等产品身份图和 clean frame 通过 QA 后，再测 Runway 单镜头 N03 蒸汽；Seedance 可作为完整 15 秒顺序测试。
- Kling 只用 clean N01/N05 first/end frame，不上传 storyboard board 或 style board 做首帧。
- Veo 用 subject/action/scene/camera/audio/restrictions 结构化提示词。

prompt-only产物:
- Seedance / Kling / Runway / Veo prompt bodies 后台可导出，需要复制时再展开。

用户确认点:
继续 prompt-only，还是授权 assisted_generation？

模拟用户选择:
继续 prompt-only。理由: 当前验收预演只验证聊天表面和工作流判断。
```

DIRcreative:

```text
阶段: QA 与重试规则
智能体创作内容:
- 生成前 QA: pre_generation_contract、资产角色、标题层级、职责纯度、继承关系、direct input policy。
- 生成后 self-QA: 产品漂移、办公室漂移、文字不可读、鱼鳞材质、规划板误当首帧、视频模型提示词混写。
- 失败类型: character_identity_reference_drift、scene_geography_reference_drift、reference_role_label_hierarchy_wrong、storyboard_information_density_too_low、storyboard_board_misread_by_video_model。
- 最小重试路由: 产品板失败只重试产品板；场景/FOV 失败只重试场景板；分镜信息不足回 shot-design；clean frame 不匹配只重试该帧；某模型失败只重试该模型 prompt。
- 用户不是第一道质检；失败图不允许请求用户锁定。

用户确认点:
真实验收时，请用户明确说: 通过 / 不通过 / 哪些地方还不满意。

模拟用户选择:
本预演不写真实验收。理由: 没有真实用户明确接受，不能生成 live-user-acceptance.yaml。
```

DIRcreative:

```text
阶段: 预演结论
结果: PASS_FOR_REHEARSAL
未生成真实图片/视频: true
未写 live-user-acceptance.yaml: true
不计入真实验收: true
下一步真实用户确认点: 用户在聊天里看完整流程后，明确说“通过”或指出不满意项。
```

skill_run_receipt:
  run_id: live-acceptance-rehearsal-chat-transcript-2026-05-17
  skill_id: chat-facilitator
  input_artifacts:
    - docs/film-preproduction/live-chat-acceptance-runbook.md
    - docs/film-preproduction/goal-mode-simulation-protocol.md
  output_artifacts:
    - examples/live-acceptance-rehearsal/01-chat-transcript.md
  decisions:
    - "Add a visible acceptance rehearsal that demonstrates the final user-facing chat surface without claiming real acceptance."
  unresolved_questions:
    - "Real user must still explicitly accept or reject the live chat workflow."
  qa_gate:
    status: pass
    reasons:
      - "Rehearsal shows required chat stages, simulated choices, prompt-only boundary, QA/retry, and live acceptance blocker."
  next_recommended_skill: checkpoint
