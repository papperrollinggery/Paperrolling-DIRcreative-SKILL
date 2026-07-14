# Chat Interface Demo

artifact:
  artifact_id: noodle-chat-interface-demo-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-co-creation-run-v1
    - noodle-qa-retry-plan-v1
  status: approved
  owner_skill: chat-facilitator

## Purpose

Show how DIRcreative should feel in chat.

This is not a terminal report and not a raw YAML dump. It is the user-visible conversation style that should happen before and between artifact writes.

## Chat Transcript Shape

### 1. Idea Intake

DIRcreative:

```text
阶段: 想法读取
我理解你的想法是: 做一条 15 秒竖屏自热面杯广告，气质要温暖、电影感、适合深夜工作者，不要吵闹零食广告感。

智能体创作内容:
- 产品: 自热面杯
- 场景: 深夜办公室
- 情绪: 疲惫到被热汤拉回状态
- 交付: 15 秒竖屏广告

用户确认点:
这个 brief 对吗？如果对，我下一步给你 3 个创意方向。
```

User:

```text
用导演组，多专家评审一下。
```

DIRcreative:

```text
阶段: 导演组会议
智能体创作内容:
- 我会用导演组模式做 multi-review: 故事/导演、制片/影像、模型风险/连续性 QA 分开压测，再合并成一个选择门。
- 你只会看到角色判断、主要分歧、3 个方向和我的建议。
- 后台运行记录只做内部证据；不展示内部运行细节。

专业判断:
这一步先决定广告方向和生产取舍，不跳到参考图、提示词或生成。

用户确认点:
如果这个 brief 已正确，我直接给你 3 个方向；如果不正确，请只改 brief。
```

### 2. Director Room Council

DIRcreative:

```text
阶段: 导演组会议
智能体创作内容:
- producer: 15 秒竖屏广告必须先保证产品看得清，场景要可拍、可生成、可测试。
- creative_director: 不做普通食物特写，核心是深夜冷光被热汤蒸汽变暖。
- director: 表演不要夸张，拍一个真实工作者从疲惫到松一口气。
- cinematographer: 可以电影感，但杯身、封条、蒸汽和面体不能被低调灯光藏掉。
- model_prompt_engineer: 需要产品板、办公室板、故事板运动板、干净首帧；文字重的板不能直接喂给可灵/Runway。
- continuity_qa: 锁住杯型、红封条、手的位置、蒸汽密度和面体质感。

导演组分歧:
- 氛围感 vs 产品清晰度: 保留电影灯光，但所有产品镜头必须清楚显示杯身和热汤。
- 一张大参考板 vs 视频模型误判: 大板只做规划，直接图生视频用无分栏、无箭头、无小字的 clean frame。
- 音乐情绪 vs 真实材质: 先用办公室 hum、封条、倒汤、第一口，音乐只能低量辅助。

给你的 3 个方向:
1. Last Light At The Desk - 深夜办公室，蒸汽把屏幕冷光变暖，产品最清楚。
2. Platform Warmth - 雨夜站台，用杯子暖手，氛围更孤独。
3. Night Driver Pause - 司机短暂停车加热，动作更强但产品更难拍清。

我的建议: 选 1，因为 15 秒内最容易讲清产品、人物情绪和参考图结构。

用户确认点:
选 1/2/3，或者说你想怎么混合。
```

User:

```text
选 1
```

DIRcreative:

```text
已记录: Last Light At The Desk
模拟用户选择: 这个 fixture 里用 simulated_fixture 标记，不等于真实用户确认。
我会继续到故事确认，不进入参考图或出图策略。
```

### 3. Story, Script, And Shot Preview

DIRcreative:

```text
阶段: 故事确认
智能体创作内容:
- Logline: 深夜办公室里，一杯自热面把冷屏幕疲惫变成一个温暖暂停。
- 5 个节拍: 冷光疲惫 / 拉开封条 / 蒸汽穿过蓝光 / 第一口放松 / 产品英雄帧。
- 情绪转折: 不是兴奋，是重新稳定下来。

用户确认点:
这个故事方向是否通过？通过后我写 15 秒脚本。
```

User:

```text
通过
```

DIRcreative:

```text
阶段: 15秒脚本
智能体创作内容:
00:00-00:03 冷屏幕光，深夜工位，面杯还没打开。
00:03-00:06 手拉红色封条，热量指示变暖。
00:06-00:09 蒸汽升起，穿过屏幕蓝光。
00:09-00:12 工作者喝第一口，肩膀放松。
00:12-00:15 产品英雄帧，窗外雨夜，文案: Warmth, ready at midnight.

用户确认点:
脚本方向是否通过？通过后我给你 5 镜头分镜。
```

User:

```text
通过
```

DIRcreative:

```text
阶段: 5镜头分镜
智能体创作内容:
专业判断:
- 15 秒广告不适合 3 个慢镜头；需要 5 个 3 秒镜头，保证 3 秒内建立需求，6 秒内完成产品动作，12 秒前给情绪转折，最后留产品记忆帧。

N01 00:00-00:03 | Need-state hook | MS / 28mm / slider push
- 叙事任务: 建立深夜疲惫和未打开的产品，观众先看懂需求。
- 机位/镜头: 桌面 30 度低机位，28mm 保留办公室空间，slider 从键盘推到面杯。
- 主体调度: 人物右手停在鼠标旁，目线落在屏幕，杯子在前景左三分线，轴线不变。
- 构图层次: 前景键盘和杯盖，中景人物手臂，背景冷蓝屏幕与窗外雨点。
- 声音剪辑: 低办公室 hum、雨声、键盘停顿，切点落在手伸向封条。
- 模型风险: 宽镜头产品可能不清，后续必须有 macro proof。

N02 00:03-00:06 | Product activation proof | ECU insert / 85mm macro / locked-off
- 叙事任务: 让观众清楚看到红色封条被拉开，产品动作成立。
- 机位/镜头: 85mm macro 固定，浅景深锁定封条和杯盖边缘。
- 主体调度: 手从右入画拉封条，动作只做一次，不增加多余手势。
- 构图层次: 前景指尖，中景红封条和杯身标识，背景虚化桌灯琥珀光。
- 声音剪辑: 封条轻响、杯盖摩擦声，不加夸张音效。
- 模型风险: 文字不要在这一镜头里承担品牌识别，产品板另行锁定。

N03 00:06-00:09 | Heat reveal | CU / 50mm / motivated tilt-up
- 叙事任务: 蒸汽把冷蓝屏幕光转成温暖感，完成视觉转折。
- 机位/镜头: 50mm 从杯口轻微 tilt-up 到人物下半张脸，焦点从汤面拉到蒸汽边缘。
- 主体调度: 人物身体不动，只让呼吸和肩膀微松。
- 构图层次: 前景蒸汽，中景杯口和汤面，背景蓝屏被琥珀桌灯压暖。
- 声音剪辑: 热汤细微声和呼吸声进入，音乐只做低频铺底。
- 模型风险: 蒸汽不能爆炸式扩散；需要 clean frame 控制密度。

N04 00:09-00:12 | Human reset | MCU / 50mm / small dolly-in
- 叙事任务: 第一口后人物从疲惫变成稳定，不做夸张表演。
- 机位/镜头: 50mm MCU，小 dolly-in 到眼神和肩膀，浅景深保留杯口热气。
- 主体调度: 杯子从胸前到嘴边，眼神从屏幕移到杯身，肩膀下降。
- 构图层次: 前景杯身，人物脸在中景，背景屏幕蓝光降饱和。
- 声音剪辑: 轻吸一口、短暂停顿，剪辑点落在肩膀放松。
- 模型风险: 手和杯口接触容易漂移，建议可灵/Runway 用 clean first frame。

N05 00:12-00:15 | Product memory frame | Packshot / 70mm / locked-off
- 叙事任务: 留下产品、热汤和深夜场景的记忆，不再讲新信息。
- 机位/镜头: 70mm 锁定，杯身正面偏 10 度，汤面和蒸汽可见。
- 主体调度: 人物手离开杯身，只保留桌面静物和窗外雨夜。
- 构图层次: 前景杯身和勺，中景桌灯暖光，背景窗外雨点和屏幕冷光。
- 声音剪辑: 雨声回到背景，音乐留一个低量温暖尾音。
- 模型风险: 文案和包装文字必须来自产品板或单独 packshot，不塞进分镜板小字。

用户确认点:
这个分镜结构是否通过？通过后我锁视觉 bible。
```

User:

```text
通过
```

DIRcreative:

```text
阶段: 视觉风格
智能体创作内容:
1. Warm practical food realism + slight neo-noir office contrast - 温暖、真实、适合产品广告。
2. Graphic high-energy snack commercial - 节奏快，但会偏吵。
3. Minimal Japanese product tabletop film - 很干净，但人的故事弱。

我的建议: 选 1。

用户确认点:
你要哪一种视觉方向？确认后我再锁视觉 bible。
```

User:

```text
选 1
```

DIRcreative:

```text
阶段: 视觉 bible 确认
智能体创作内容:
- 产品锁定: 象牙纸杯、红色封条、铜色杯盖边、黑色竖排 MIDNIGHT BROTH。
- 灯光锁定: 蓝色显示器冷光 + 琥珀桌灯 + 柔和蒸汽。
- 材质锁定: 哑光纸杯、清澈热汤、自然面体、无鱼鳞感纹理。
- 避免: 噪点、过锐化、爆炸蒸汽、假小字、塑料感。

用户确认点:
这些视觉锁是否通过？通过后我给参考图组方案。
```

User:

```text
通过
```

### 5. Reference Pack Gate

DIRcreative:

```text
阶段: 参考图方案
智能体创作内容:
我建议最少 5 组图:
1. product board - 锁定杯型、红封条、汤面、蒸汽。
2. office board - 锁定办公室、灯光、人物位置。
3. lighting/material/style board - 锁定蓝/琥珀灯光、纸杯、汤面、蒸汽、抗鱼鳞纹理。
4. storyboard board - 只给人和 Seedance/Veo 看镜头顺序。
5. clean frames - 给可灵/Runway 做直接 I2V。

重要限制:
- storyboard board 不能直接喂给可灵或 Runway。
- office board 和 style board 也不能作为直接首帧。
- clean frames 要无文字、无分栏、无箭头。

用户确认点:
选这个 5 组图方案，还是要压缩成更少的图？
```

### 6. Image Execution Recommendation

DIRcreative:

```text
阶段: 出图执行建议
客户可见预览:
- 第一张只测杯面产品身份，先把杯型、红封条、汤面、蒸汽和材质锁稳。
- 通过后再扩展办公室、灯光材质、分镜规划和 clean frames，避免一次性把产品与场景混在一起。

智能体创作内容:
- 建议先出 1 张测试图: `PRODUCT IDENTITY REFERENCE`。先锁杯型、红封条、汤面、蒸汽和材质，避免后面每张图都重新发明产品。
- 测试图通过 self-QA 后，再出 4 类补充图: office/FOV、lighting/material/style、professional storyboard/motion board、clean N01/N05 frames。
- storyboard/motion board、style board、带文字说明的规划板不能直接喂 Kling/Runway 做首帧。
- clean frames 必须无文字、无分栏、无箭头，才可作为直接 I2V 输入。

prompt-only产物:
- 后台已准备 pre_generation_contract.status: pass、JSON prompts、direct video input policy。它们只作为后台证据，不让用户审批 raw JSON 或 YAML。

未生成真实图片/视频:
当前没有生成真实图片或视频。

用户确认点:
先试 1 张 `PRODUCT IDENTITY REFERENCE`，还是保持 prompt-only 不出图？
```

User:

```text
保持 prompt-only，先看视频生成建议。
```

### 7. Video Generation Recommendation

DIRcreative:

```text
阶段: 视频生成建议
客户可见预览:
- 第一轮不建议直接做全片视频。建议先测 N03 蒸汽揭示或 N05 packshot，因为最容易暴露产品漂移、蒸汽过度和文字假象。
- Seedance: 适合用多参考图讲完整 15 秒顺序，但必须声明 storyboard board 只做 planning，不显示板面、箭头、小字。
- Kling: 只在 clean N01/N05 生成并通过 QA 后再用 first/end frame。
- Runway: 先测单镜头 I2V，避免一次性塞完整故事。
- Veo: 用 subject/action/scene/camera/audio/restrictions 结构化提示词。

prompt-only产物:
- Seedance / Kling / Runway / Veo prompt bodies 已在后台准备；需要复制时再展开 raw prompt。

用户确认点:
后续如果授权视频，先测 Seedance 15 秒完整顺序，还是先测 Runway 单镜头 N03？
```

User:

```text
继续 prompt-only。
```

### 8. QA And Retry Gate

DIRcreative:

```text
阶段: QA 与重试规则
智能体创作内容:
- 如果你授权 assisted_generation，我会先按上面的 pre_generation_contract 检查，再调用生图。
- 每张图生成后先过 self-QA，不把失败图直接交给你锁定。
- 失败只重试最小环节: 产品板、办公室板、灯光材质板、分镜板、clean frame、或某个视频模型提示词。

prompt-only产物:
- Post-Generation Self-QA: 产品漂移、办公室漂移、文字不可读、鱼鳞材质、规划板误当首帧、视频模型提示词混写。
- Retry Routing: product identity -> office clean-frame source -> lighting/material/style -> storyboard/motion -> clean N01/N05 -> model-specific retry。
- 后台证据: pre_generation_contract、JSON image prompts、model-specific video prompts 均保留，但不作为客户前台审批项。

用户确认点:
如果之后授权真实生成，是否先从 1 张产品身份测试图开始？
```

User:

```text
同意顺序，但这个 demo 继续保持 prompt-only。
```

DIRcreative:

```text
阶段: 下一步选择
智能体创作内容:
- 当前没有生成真实图片或视频。
- 如果真实执行，第一步只生成 product identity board，self-QA 通过后才让用户确认是否锁定。

用户确认点:
下一步你要:
1. 继续 prompt-only，只拿提示词；
2. 先生成 clean frames；
3. 先用 Seedance 测 15 秒；
4. 先用可灵/Runway 测单镜头。
```

## Acceptance Notes

- The user can understand the workflow without opening files.
- Every creative lock is visible in chat.
- Every major output has a short preview before the next gate.
- The workflow asks one decision at a time.
- Fixture decisions are labeled as simulation.

skill_run_receipt:
  run_id: noodle-chat-interface-demo-2026-05-16
  skill_id: chat-facilitator
  input_artifacts:
    - examples/live-user-sim-noodle/15-co-creation-run.yaml
    - examples/live-user-sim-noodle/12-qa-retry-plan.md
  output_artifacts:
    - examples/live-user-sim-noodle/16-chat-interface-demo.md
  decisions:
    - "Define the user-facing chat style separately from terminal and file validation."
    - "Expose pre-generation contract and QA/retry rules before assisted generation."
  unresolved_questions:
    - "A live session still needs actual user choices."
  qa_gate:
    status: pass
    reasons:
      - "Demo shows stage labels, options, simulated choice labels, prompt-only boundary, and one-question gates."
  next_recommended_skill: chat-facilitator
