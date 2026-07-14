# Complete Idea Chat Transcript

artifact:
  artifact_id: complete-idea-chat-transcript-v1
  version: 1.0.0
  source_artifact_ids:
    - complete-idea-segmentation-intake-v1
    - complete-idea-director-room-v1
    - complete-idea-qa-retry-plan-v1
  status: approved
  owner_skill: chat-facilitator

## Purpose

Show the real-use chat behavior when the user already has a complete idea and only needs professional segmentation, shot design, reference planning, and prompt export.

## Transcript

DIRcreative:

```text
阶段: 完整想法读取
智能体创作内容:
- 专业判断: 你已经给了完整故事、时长、气质和禁止项，所以这里不进入创意发散，也不直接出图。
- 已锁定: Fog Route Cleaner / 15 秒 / 9:16 / 市政清道夫 / 丧尸污染街道 / 救护车通道 / 无血腥无喜剧。
- 取舍: 我会跳过 3 个大创意方向，但保留故事验证、脚本节奏、分镜、视觉 Bible、参考图组和模型提示词 gate。
- 执行影响: 这会更快，但仍然不会绕过分镜和参考图确认。

用户确认点:
是否按“完整想法切分模式”继续？继续后我先给故事逻辑和 15 秒节奏。
```

模拟用户选择:

```text
继续，按完整想法切分。
```

DIRcreative:

```text
阶段: 导演组会议
智能体创作内容:
- producer: 这是完整想法执行，不是开放头脑风暴。保留用户的片名、时长、故事目标和禁止项，把确认点放在节奏、分镜、参考图和生成模式。
- creative_director: 核心气质是人性克制的市政现实主义，不是丧尸动作片。画面要让观众相信“专业的人让生命通道恢复”。
- director: 镜头必须跟随任务逻辑: 看到堵塞、启动工具、推进清道、控制风险、救护车通过、安静收尾。
- screenwriter: 不加对白和解释性字幕。15 秒靠动作、声音和剪辑讲清楚。
- cinematographer: 街道轴线、救护车位置、雾中光源和镜头视场要先锁定，否则后续 clean frame 会漂移。
- production_designer: 人物/设备参考必须是一张单一身份来源，避免多个清道夫设计互相竞争。
- editor: 三镜头会把信息压爆，六镜头更适合这个 15 秒故事；镜头数应由内容节奏决定，不是固定模板。
- sound_designer: 声音要写进分镜: 远警笛、湿路、推车电机、喷雾、靴子踩水、救护车远去。
- model_prompt_engineer: 参考图不能混用。V2 sequential 顺序应是人物身份参考 -> 场景空间+镜头视场 -> 专业故事版+镜头运动 -> 可选 clean frames。
- continuity_qa: 视频前必须锁人物一致性、场景一致性、标题层级和参考图职责；分镜页、人物板、场景板不能直接当 Kling/Runway 首帧。

导演组分歧:
- 完整想法是否还要给 3 个新创意方向: 不给新故事方向，只给执行方案，因为用户已经给了完整设定。
- 3 镜头还是 6 镜头: 6 镜头通过，因为该故事有建立、设备证明、推进、风险、放行、证明六个必要任务。
- 一张密集总图还是顺序锁定: 采用 V2 sequential，先锁单一人物身份和单一场景/FOV，再做专业分镜运动页。

给你的 3 个执行方案:
1. 六镜头市政现实主义: 最稳，信息密度和模型可读性平衡最好。
2. 四镜头慢节奏: 更有氛围，但会弱化工具启动和风险控制。
3. 八镜头快剪: 更急迫，但对 15 秒和 clean frames 要求更高。

我的建议:
选 1。它最符合用户原始想法，也最适合后续人物/场景一致性锁定。

用户确认点:
接受六镜头市政现实主义方案，还是改成 4 镜头慢节奏或 8 镜头快剪？
```

模拟用户选择:

```text
接受六镜头市政现实主义方案。
```

DIRcreative:

```text
阶段: 故事逻辑确认
智能体创作内容:
- 专业判断: 这个想法的核心不是打丧尸，而是“专业的人完成一件小但重要的公共服务”。这适合 15 秒，因为目标清楚，动作单一，结尾有可见结果。
- 15 秒节奏: 2 秒建立街道和救护车阻塞，2 秒启动设备，3 秒推进清道，2 秒处理风险，3 秒让救护车通过，3 秒留人物和清理后的路。
- 取舍: 6 镜头比 3 镜头更合适。3 镜头会把设备、动作、障碍、救护车通过压在一起，模型容易混乱。
- 执行影响: 后续参考图需要角色/设备板、街道场景板、分镜运动板、2 张 clean frames。

用户确认点:
这个 6 镜头节奏通过吗？不通过我可以改成 4 镜头慢节奏或 8 镜头快剪。
```

模拟用户选择:

```text
通过 6 镜头。
```

DIRcreative:

```text
阶段: 专业分镜确认
智能体创作内容:
S01 00:00-00:02 | Route blocked | WS / 24mm / locked-off
- 叙事任务: 用一个可读画面说明街道被堵，救护车需要通道。
- 机位/镜头: 竖屏街口低机位，24mm 保留路面、雾、救护车灯和清道夫入口。
- 主体调度: 救护车停在背景右侧，清道夫从前景左侧进入，轴线沿街道向前。
- 构图层次: 前景湿路面和警戒线，中景清道夫，背景救护车蓝红灯与慢移丧尸剪影。
- 声音剪辑: 远处警笛、低频清晨风、轮胎水声。
- 模型风险: 丧尸只做远景剪影，不要血腥近景。

S02 00:02-00:04 | Tool activation | ECU / 85mm macro / locked
- 叙事任务: 让设备可信，证明他是专业清道，不是战斗。
- 机位/镜头: 85mm macro 锁定手套、开关、喷雾压力表。
- 主体调度: 手套从画面下方进入，按下一次开关，压力表抬升。
- 构图层次: 前景手套，中景开关和表盘，背景雾中车灯虚化。
- 声音剪辑: 开关咔哒、电机低鸣、压力表轻震。
- 模型风险: 表盘文字不要作为关键可读信息。

S03 00:04-00:07 | Lane clearing push | MS tracking / 35mm / stabilized follow
- 叙事任务: 展示清道夫推进，狭窄通道开始出现。
- 机位/镜头: 35mm 侧后方跟拍，稳定器低速推进，焦点锁清道车前缘。
- 主体调度: 清道夫从左前向右后推车，喷雾只覆盖地面和低处障碍。
- 构图层次: 前景喷雾和湿路面，中景设备与清道夫，背景救护车灯被雾切开。
- 声音剪辑: 电机嗡鸣、喷雾、靴子踩水。
- 模型风险: 喷雾不能变成爆炸或魔法光效。

S04 00:07-00:09 | Controlled threat | MCU / 50mm / small pan
- 叙事任务: 给紧张感，但保持专业克制。
- 机位/镜头: 50mm 轻 pan 从清道夫肩章到远处丧尸剪影。
- 主体调度: 清道夫不冲刺，只停半步调整喷头方向，保持路线。
- 构图层次: 前景肩章和反光条，中景喷头，背景模糊丧尸剪影。
- 声音剪辑: 警笛压低，呼吸声短促一次，喷头角度变化。
- 模型风险: 不要让丧尸扑到镜头前，不要肢体攻击。

S05 00:09-00:12 | Ambulance release | WS to MS / 32mm / dolly back
- 叙事任务: 显示通道完成，救护车能通过。
- 机位/镜头: 32mm 从清道车前缘后撤，露出一条干净窄道。
- 主体调度: 清道夫退到左侧，救护车缓慢向前，双方不抢主角。
- 构图层次: 前景清道车边缘，中景空出的车道，背景救护车灯穿雾。
- 声音剪辑: 救护车低速发动、喷雾声退后、音乐第一次进入。
- 模型风险: 车速必须慢，避免动作混乱。

S06 00:12-00:15 | Quiet proof | CU / 70mm / locked-off
- 叙事任务: 结尾不是英雄姿势，而是职业完成后的安静证明。
- 机位/镜头: 70mm 锁定清道夫手套放回喷头，背景救护车离开。
- 主体调度: 清道夫低头检查路面，不看镜头，不摆姿势。
- 构图层次: 前景喷头滴水，中景手套和反光袖口，背景救护车尾灯远去。
- 声音剪辑: 电机降速、远去警笛、雾中城市底噪。
- 模型风险: 不能生成胜利 pose 或血腥街道。

用户确认点:
这个 6 镜头分镜通过吗？通过后我再给视觉 Bible 和参考图组方案。
```

模拟用户选择:

```text
分镜通过，继续参考图方案。
```

DIRcreative:

```text
阶段: 参考图组方案
智能体创作内容:
- 专业判断: 这个片子不适合一张大图解决。角色、设备、街道、镜头运动和 clean frames 要分开，否则视频模型会把分镜板、小字和箭头当成画面内容。
- 参考图组: 角色/设备板、街道场景板、灯光材质风格板、分镜运动板、S01 clean start frame、S06 clean end frame。

prompt-only产物:
- reference plan: character-equipment board / street-environment board / lighting-material-style board / storyboard-motion board / S01 clean frame / S06 clean frame。

当前没有生成真实图片或视频:
- clean_frame_gate 仍然 pending。
- media_generation 被阻止，直到用户授权生成或导入 clean frames。

用户确认点:
是否采用这套参考图组拆分？
```

模拟用户选择:

```text
采用。先看出图执行建议，再决定是否进入 assisted_generation。
```

DIRcreative:

```text
阶段: 出图执行建议
客户可见预览:
- 第一张只测清道夫人物身份，锁年龄、制服、面罩、手套、体态和职业气质。
- 人物通过后再补场景视场、分镜运动页和 clean frames，降低角色漂移。

智能体创作内容:
- 建议先出 1 张 `CHARACTER IDENTITY REFERENCE`，只锁清道夫年龄、制服、面罩、手套、体态和职业气质。
- 通过 self-QA 后再出 `SCENE GEOGRAPHY + CAMERA FOV REFERENCE`，再出 `PROFESSIONAL STORYBOARD + MOTION MAP`，最后出 clean start/end frames。
- storyboard/motion map、带文字规划板、场景/FOV 图不能直接当 Kling/Runway 首帧。
- Image2/Image Gen 提示词后台会统一加材质防伪影后缀。

prompt-only产物:
- 后台已准备 pre_generation_contract.status: pass、JSON-first image prompts、direct video input policy；不在聊天里让用户审批 raw JSON/YAML。

用户确认点:
先试 1 张人物身份参考图，还是继续 prompt-only 看视频生成建议？
```

模拟用户选择:

```text
采用先试 1 张人物身份参考图；本轮仍保持 prompt-only，不出真实图片。
```

DIRcreative:

```text
阶段: 视频生成建议
客户可见预览:
- 第一轮建议测试 Seedance 的 15 秒完整段落，因为它更适合多参考绑定；同时明确 storyboard/motion map 只做规划，不显示板面。
- Kling/Runway 只在 clean start/end frames 生成并通过 QA 后测试。
- Veo 采用 subject/action/scene/camera/audio/restrictions 结构化提示词。

prompt-only产物:
- Seedance、Kling、Runway、Veo prompt bodies 已后台准备；需要复制时再展开。

用户确认点:
如果之后授权视频，先测 Seedance 15 秒完整段，还是先等 clean frames 后测 Runway 单镜头？
```

模拟用户选择:

```text
先不测视频，继续看 QA 与重试规则。
```

DIRcreative:

```text
阶段: QA 与重试规则
智能体创作内容:
- 我不会把生成图直接交给你判断。每张图先过 self-QA。
- 生成前先检查 pre_generation_contract: 资产角色、最大标题、项目名小字、职责纯度、继承关系、direct video input policy。
- 旧问题会被直接拦截: 人物漂移、场景漂移、标题层级错误、参考图职责混乱、分镜信息密度不足、鱼鳞材质、把规划板当视频首帧、不同视频模型提示词混写。
- 失败只重试最小环节: 人物图失败只重试人物图；场景/FOV 失败只重试场景图；分镜信息不足只回到 shot-design；某个视频模型运动失败只重试该模型。
- 人物没锁就不生成场景；场景没锁就不生成分镜页；分镜页不合格就不生成 clean frames；clean frames 没锁就不进视频。

prompt-only产物:
- QA checklist: pre-generation contract / post-generation self-QA / model handoff blocker。
- Retry routing: character identity -> scene/FOV -> storyboard/motion -> clean frames -> video model adapter。

用户确认点:
如果开始 assisted_generation，是否同意按顺序生成并逐步 QA: 1 人物身份参考图 -> 2 场景/FOV 图 -> 3 专业分镜运动页 -> 4 clean start/end frames -> 5 单模型视频测试？
```

模拟用户选择:

```text
同意顺序生成，但本 demo 仍保持 prompt-only，不生成真实图片或视频。
```

DIRcreative:

```text
阶段: 下一步选择
智能体创作内容:
- 当前仍是 prompt-only。没有生成真实图片或视频。
- 下一步如果真实执行，我会先生成 `frc_v2_01_character_identity_reference`，通过 self-QA 后才让用户确认是否锁定。
- 如果 self-QA 失败，我会给出失败类型和最小重试动作，不会要求用户锁定失败图。

用户确认点:
下一步选一个：1 继续 prompt-only；2 先生成参考图组；3 只生成 S01/S06 clean frames；4 先用 Runway 测 S03 单镜头。
```

## Acceptance Notes

- This fixture skips broad brainstorming only because the user supplied a complete idea.
- It still requires story, shot, visual, reference, clean-frame, and video-prompt gates.
- It uses 6 shots because the rhythm demands more than 3 and different from the existing 5-shot ad test.
- It does not generate real media.

skill_run_receipt:
  run_id: complete-idea-chat-transcript-2026-05-16
  skill_id: chat-facilitator
  input_artifacts:
    - examples/complete-idea-segmentation-test/01-complete-idea.md
    - examples/complete-idea-segmentation-test/02-director-room-notes.md
    - examples/complete-idea-segmentation-test/05-qa-retry-plan.md
  output_artifacts:
    - examples/complete-idea-segmentation-test/02-chat-transcript.md
  decisions:
    - "Skip broad concept ideation because the user supplied a complete idea."
    - "Show director-room in complete-idea validation mode before story and shot approval."
    - "Use six shots because the 15-second rhythm needs setup, activation, progress, threat, release, and proof."
    - "Expose QA and retry rules before any assisted generation."
  unresolved_questions:
    - "A live user must still choose prompt-only, reference generation, clean-frame generation, or a video model test."
  qa_gate:
    status: pass
    reasons:
      - "Transcript exposes professional judgment, user gates, shot cards, reference strategy, and media blockers."
  next_recommended_skill: reference-image-planner
