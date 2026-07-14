# Goal Mode Rough Idea Simulation Chat Transcript

artifact:
  artifact_id: goal-mode-rough-idea-simulation-chat-transcript-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-chat-interface-demo-v1
    - noodle-co-creation-run-v1
    - noodle-qa-retry-plan-v1
  status: approved
  owner_skill: chat-facilitator

## Purpose

Show goal-mode dogfood for a one-sentence rough idea. The user does not keep sending `1`, so every gate records `模拟用户选择` and continues.

This is a dry-run transcript. It is not real user acceptance.

## Transcript

DIRcreative:

```text
阶段: 目标模式模拟测试
智能体创作内容:
- 当前是 goal_context 自动测试，不等用户发 1。
- 测试路径是“一句话想法 -> 共创确认 -> 导演组 -> 脚本 -> 动态分镜 -> 参考图 -> 合同 -> prompt -> QA”。
- 所有自动选择都标记为 `模拟用户选择`。
- 不生成真实图片或视频。
- 不写 live-user-acceptance.yaml。

专业判断:
这条路径检查用户最初要求的“一句话就能进入专业视频前期流程”，但不替代真实验收。
```

DIRcreative:

```text
阶段: 想法读取
智能体创作内容:
- 原始想法: 做一条 15 秒竖屏自热面杯广告，温暖、电影感、适合深夜工作者，不要吵闹零食广告感。
- 目标渠道/时长: 竖屏短视频广告 / 15 秒。
- 初始风险: 产品可能被氛围灯光藏掉；蒸汽可能被模型生成成爆炸；包装小字不能承担识别。
- 当前边界: prompt-only，不生成真实图片或视频。

用户确认点:
这个 brief 是否正确？

模拟用户选择:
正确。理由: 产品、场景、情绪、渠道和禁止项都足够进入导演组。
```

DIRcreative:

```text
阶段: 导演组会议
智能体创作内容:
- producer: 15 秒广告先保证产品可读，不能只做气氛片。
- creative_director: 核心不是普通食物特写，而是冷屏幕被热汤蒸汽变暖。
- director: 表演要克制，拍真实工作者从疲惫到稳定。
- screenwriter: 不用对白；动作和声音讲清楚产品启动、热气和第一口。
- cinematographer: 产品、封条、蒸汽和汤面必须有 macro proof。
- production_designer: 杯型、红封条、铜色杯盖、桌面道具要从产品板统一继承。
- editor: 5 镜头更稳；3 镜头会压掉产品动作或情绪转折。
- sound_designer: 办公室 hum、雨声、封条声、热汤声、第一口停顿要写进分镜。
- model_prompt_engineer: storyboard board 只做规划；Kling/Runway 需要无文字 clean frames。
- continuity_qa: 产品一致性、办公室灯光、蒸汽密度、手和杯的位置必须锁定。

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
- 5 个节拍: 冷光疲惫 / 拉开封条 / 蒸汽穿过蓝光 / 第一口放松 / 产品英雄帧。
- 情绪转折: 不是兴奋，是重新稳定下来。
- 渠道判断: 15 秒竖屏广告需要 3 秒内建立需求，6 秒内完成产品动作，12 秒前给情绪转折。

用户确认点:
这个故事方向是否通过？

模拟用户选择:
通过。理由: 需求、产品动作、情绪变化和产品记忆帧都可视化。
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
通过。理由: 15 秒广告信息密度合适，产品动作和情绪都没有被省掉。
```

DIRcreative:

```text
阶段: 分镜头确认
智能体创作内容:
N01 00:00-00:03 | Need-state hook | MS / 28mm / slider push
- 叙事任务: 建立深夜疲惫和未打开产品。
- 机位/镜头: 桌面 30 度低机位，28mm 保留办公室空间，slider 从键盘推到面杯。
- 主体调度: 人物右手停在鼠标旁，杯子在前景左三分线。
- 构图层次: 前景键盘和杯盖，中景手臂，背景冷蓝屏幕与窗外雨点。
- 声音剪辑: 低办公室 hum、雨声、键盘停顿。
- 模型风险: 宽镜头产品可能不清，后续必须有 macro proof。

N02 00:03-00:06 | Product activation proof | ECU / 85mm macro / locked-off
- 叙事任务: 清楚看到红色封条被拉开。
- 机位/镜头: 85mm macro 固定，浅景深锁定封条和杯盖边缘。
- 主体调度: 手从右入画拉封条，动作只做一次。
- 构图层次: 前景指尖，中景红封条和杯身标识，背景桌灯琥珀光。
- 声音剪辑: 封条轻响、杯盖摩擦声。
- 模型风险: 包装文字不要在这一镜承担品牌识别。

N03 00:06-00:09 | Heat reveal | CU / 50mm / motivated tilt-up
- 叙事任务: 蒸汽把冷蓝屏幕光转成温暖感。
- 机位/镜头: 50mm 从杯口轻微 tilt-up 到人物下半张脸。
- 主体调度: 人物不夸张，只让呼吸和肩膀微松。
- 构图层次: 前景蒸汽，中景杯口和汤面，背景蓝屏被琥珀灯压暖。
- 声音剪辑: 热汤细声和呼吸进入。
- 模型风险: 蒸汽不能爆炸式扩散，需要 clean frame 控制密度。

N04 00:09-00:12 | Human reset | MCU / 50mm / small dolly-in
- 叙事任务: 第一口后从疲惫变稳定。
- 机位/镜头: 50mm MCU，小 dolly-in 到眼神和肩膀。
- 主体调度: 杯子从胸前到嘴边，眼神从屏幕移到杯身。
- 构图层次: 前景杯身，人物脸在中景，背景屏幕蓝光降饱和。
- 声音剪辑: 轻吸一口，短暂停顿。
- 模型风险: 手和杯口接触易漂移，Kling/Runway 应用 clean first frame。

N05 00:12-00:15 | Product memory frame | Packshot / 70mm / locked-off
- 叙事任务: 留下产品、热汤和深夜场景记忆。
- 机位/镜头: 70mm 锁定，杯身正面偏 10 度，汤面和蒸汽可见。
- 主体调度: 人物手离开杯身，只保留桌面静物。
- 构图层次: 前景杯身和勺，中景桌灯暖光，背景窗外雨点和屏幕冷光。
- 声音剪辑: 雨声回到背景，音乐低量收尾。
- 模型风险: 文案和包装文字必须来自产品板或单独 packshot，不塞进分镜板小字。

用户确认点:
这个 5 镜头分镜是否通过？

模拟用户选择:
通过。理由: 镜头数由广告节奏决定，5 镜头比 3 镜头更能保护产品动作、情绪转折和模型可读性。
```

DIRcreative:

```text
阶段: 视觉方向 / 视觉 bible
智能体创作内容:
- 视觉方向: warm practical food realism + slight neo-noir office contrast。
- 产品锁: 象牙纸杯、红色封条、铜色杯盖边、黑色竖排 MIDNIGHT BROTH。
- 灯光锁: 蓝色显示器冷光 + 琥珀桌灯 + 柔和蒸汽。
- 材质锁: 哑光纸杯、清澈热汤、自然面体、无鱼鳞感纹理。
- 避免: 噪点、过锐化、爆炸蒸汽、假小字、塑料感。

用户确认点:
这些视觉锁是否通过？

模拟用户选择:
通过。理由: 视觉锁同时服务产品广告和模型一致性。
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
采用 5 组图方案。理由: 用最少资产覆盖产品身份、场景、风格、运动和直接 I2V 输入，不让职责互相污染。
```

DIRcreative:

```text
阶段: 出图执行建议
客户可见预览:
- 第一张只测产品身份，先把产品从办公室、人物手势和分镜规划里拆出来。
- 产品稳定后再补 office/FOV、lighting/material/style、storyboard/motion board 和 clean frames。

智能体创作内容:
- 建议先出 1 张 `PRODUCT IDENTITY REFERENCE`，只锁产品，不混入办公室、人物手势或分镜。
- 通过 self-QA 后再出 office/FOV、lighting/material/style、professional storyboard/motion board、clean N01/N05 frames。
- storyboard/motion board、style board、带文字说明的规划板不能直接喂 Kling/Runway 做首尾帧；只有无字 clean frame 可作为直接 I2V 输入。
- 后台证据已准备: pre_generation_contract.status: pass、JSON image prompts、direct video input policy。用户不审批 raw JSON/YAML。

用户确认点:
先试 1 张产品身份参考图，还是保持 prompt-only？

模拟用户选择:
保持 prompt-only。理由: 当前测试验证流程，不生成真实媒体；真实执行时先测产品身份图最稳。
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
继续 prompt-only。理由: 当前测试目标是验证流程，不生成真实媒体。
```

DIRcreative:

```text
阶段: QA 与重试规则
智能体创作内容:
- 生成前 QA: pre_generation_contract、资产角色、标题层级、职责纯度、继承关系、direct input policy。
- 生成后 self-QA: 产品漂移、办公室漂移、文字不可读、鱼鳞材质、规划板误当首帧、视频模型提示词混写。
- 最小重试路由: 产品板失败只重试产品板；场景/FOV 失败只重试场景板；分镜信息不足回 shot-design；clean frame 不匹配只重试该帧；某模型失败只重试该模型 prompt。
- 用户不是第一道质检；失败图不允许请求用户锁定。

用户确认点:
是否认可这个 goal-mode 粗想法模拟覆盖完整流程？

模拟用户选择:
模拟通过。理由: 从一句想法开始，已覆盖共创、导演组、脚本、分镜、参考图、出图建议、视频建议、QA。
```

DIRcreative:

```text
阶段: 模拟测试结论
结果: PASS
覆盖: 一句话想法读取 / 共创确认 / 导演组会议 / 故事确认 / 脚本确认 / 5 镜头动态分镜 / 视觉 bible / 参考图方案 / 出图执行建议 / Seedance-Kling-Runway-Veo 视频生成建议 / QA 与重试规则
未生成真实图片/视频: true
不计入真实验收: true
下一步真实用户确认点: 是否授权先生成 product identity board，或继续 prompt-only 导出。
```

## Acceptance Notes

- This transcript proves goal-mode simulation covers the rough-idea path, not only complete-idea segmentation.
- Every automatic decision is labeled `模拟用户选择`.
- It does not generate media.
- It does not write a live user acceptance receipt.

skill_run_receipt:
  run_id: goal-mode-rough-idea-simulation-chat-transcript-2026-05-17
  skill_id: chat-facilitator
  input_artifacts:
    - docs/film-preproduction/goal-mode-simulation-protocol.md
    - examples/live-user-sim-noodle/16-chat-interface-demo.md
  output_artifacts:
    - examples/goal-mode-rough-idea-simulation-test/01-chat-transcript.md
  decisions:
    - "Goal mode rough-idea simulation proceeds through every gate without waiting for numeric user replies."
    - "All automatic choices are marked simulated_fixture and cannot become real user acceptance."
  unresolved_questions:
    - "A real user must still accept the live chat workflow before goal completion."
  qa_gate:
    status: pass
    reasons:
      - "Transcript shows full rough-idea chat-visible workflow and separates simulation from live acceptance."
  next_recommended_skill: checkpoint
