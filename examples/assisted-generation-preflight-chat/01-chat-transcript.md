# Assisted Generation Preflight Chat Transcript

artifact:
  artifact_id: assisted-generation-preflight-chat-transcript-v1
  version: 1.0.0
  source_artifact_ids:
    - live-chat-start-protocol
    - complete-idea-chat-transcript-v1
    - fog-route-cleaner-assisted-generation-v1
  status: approved
  owner_skill: chat-facilitator

## Purpose

Show how DIRcreative should behave in chat when the user says "看看图" or asks to generate images before the workflow is ready.

This is a dry-run transcript. It does not call image generation and does not create real media.

## Transcript

User:

```text
看看图
```

DIRcreative:

```text
阶段: 出图请求前置拦截
智能体创作内容:
- 当前不能直接出图。
- 原因 1: 还没有看到本轮故事、脚本、分镜、参考图方案和生成前合同是否被确认。
- 原因 2: 如果现在直接生成，很容易复发人物漂移、场景漂移、标题层级错误、分镜板被视频模型误读。
- 原因 3: 用户还没有明确授权 assisted_generation；默认仍是 prompt_only。

专业判断:
“看看图”不是跳过前期流程的许可。正确路径是先把最小参考图组和 direct video input policy 锁清楚，再决定是否生成第一张图。

用户确认点:
先回到最早未确认的创意 gate，还是只导出 prompt-only 参考图提示词？

模拟用户选择:
回到最早未确认的创意 gate。理由: 先补齐故事/分镜/参考图职责，才能避免生成出错误资产。
```

DIRcreative:

```text
阶段: 最早未确认 gate
智能体创作内容:
- 需要先确认: 分镜头确认 -> 参考图方案 -> 生成前合同。
- 不会生成单张“好看的概念图”来替代专业分镜。
- 不会把片名做成最大标题。
- 不会把 storyboard/motion board 当 Kling 或 Runway 的首帧。

用户确认点:
是否先看分镜头和参考图方案？

模拟用户选择:
先看。理由: 用户需要直观看到图要解决什么问题，而不是只看到随机漂亮图。
```

DIRcreative:

```text
阶段: 分镜头确认
智能体创作内容:
S01 00:00-00:02 | Route blocked | WS / 24mm / locked-off
- 叙事任务: 一眼看懂救护车被堵和清道夫入场。
- 机位/镜头: 竖屏街口低机位，24mm 保留湿路、雾、救护车灯和人物入口。
- 主体调度: 清道夫从前景左侧入画，救护车在背景右侧，轴线沿街道向前。
- 声音剪辑: 远警笛、低频清晨风、轮胎水声。
- 模型风险: 远处人影只做剪影，不要血腥近景。

S02 00:02-00:04 | Tool activation | ECU / 85mm macro / locked
- 叙事任务: 证明这是专业清道设备，不是战斗。
- 机位/镜头: 85mm macro 锁定手套、开关、压力表。
- 主体调度: 手套从下方入画，只按一次开关。
- 声音剪辑: 开关咔哒、电机低鸣。
- 模型风险: 表盘文字不做关键信息。

S03 00:04-00:07 | Lane clearing push | MS / 35mm / stabilized follow
- 叙事任务: 显示通道开始出现。
- 机位/镜头: 35mm 侧后方低速跟拍，焦点锁清道车前缘。
- 主体调度: 清道夫推车从左前向右后，喷雾只覆盖地面和低处障碍。
- 声音剪辑: 电机、喷雾、靴子踩水。
- 模型风险: 喷雾不能变成爆炸或魔法光效。

用户确认点:
这个分镜信息密度是否足够进入参考图方案？

模拟用户选择:
足够。理由: 每个镜头已有时间、景别、焦段、移动、调度、声音和模型风险。
```

DIRcreative:

```text
阶段: 参考图方案
智能体创作内容:
- 图 1 / CHARACTER IDENTITY REFERENCE: 锁同一个清道夫、制服、面罩、手套、清道车。不是直接视频首帧。
- 图 2 / SCENE GEOGRAPHY + CAMERA FOV REFERENCE: 锁街道轴线、救护车位置、FOV 扇形、人物和车辆路径。planning only。
- 图 3 / PROFESSIONAL STORYBOARD + MOTION MAP: 每个镜头包含 timecode、景别、焦段、运动起止、调度、画面层次、声音、模型风险。planning only。
- 图 4 / CLEAN FIRST FRAME S03: 无文字、无分栏、无箭头，只在角色和场景锁定后生成。
- 图 5 / CLEAN END FRAME S06: 无文字、无分栏、无箭头，只在 clean first frame 通过 self-QA 后生成。

专业判断:
这不是“一张图塞满所有信息”，而是最少图组承担最多职责。重复内容必须继承锁定来源，不能重复设计。

用户确认点:
是否采用这个顺序，而不是一次性批量出所有图？

模拟用户选择:
采用顺序生成。理由: 一次性批量出图会放大人物和场景漂移，顺序锁定更适合后续视频模型。
```

DIRcreative:

```text
阶段: 出图执行建议
客户可见预览:
- 只允许先测 1 张人物身份参考图。
- 这张图用于锁人物、制服、面罩、手套和清道车，不作为视频首帧。

智能体创作内容:
- 建议只先生成 1 张 `CHARACTER IDENTITY REFERENCE`。
- 这张图只锁人物、制服、面罩、手套、清道车，不画完整场景分镜。
- 它不是 Kling/Runway 首帧，只能做人和设备身份参考。
- 后续场景图、storyboard/motion page、clean frames 必须继承这一张人物身份锁。
- 后台证据已准备: pre_generation_contract.status: pass、dominant_title、secondary_project_metadata、direct video input policy；不让用户审批 raw JSON/YAML。

用户确认点:
是否允许先生成第一张人物身份参考图？

模拟用户选择:
不生成真实图片，只记录 preflight。理由: 目标模式测试不能替代真实授权；但真实执行时第一步只能生成这一张人物身份图。
```

DIRcreative:

```text
阶段: assisted_generation 前置结果
智能体创作内容:
- 真实工具调用: false
- 当前视觉输出模式: prompt_only
- assisted_generation_status: blocked_for_real_authorization
- blocked_media: image_generation, video_generation
- 下一步真实用户动作: 明确授权“生成第一张人物身份参考图”，或继续 prompt-only 导出。

如果用户真实授权:
1. 只生成 CHARACTER IDENTITY REFERENCE。
2. 立即运行 post-generation self-QA。
3. 如果出现 character_identity_reference_drift、reference_role_label_hierarchy_wrong、fish_scale_material_artifact，直接失败并重试最小资产。
4. self-QA 通过后才请用户锁定。
5. 用户锁定人物后，才进入 SCENE GEOGRAPHY + CAMERA FOV REFERENCE。

用户确认点:
真实执行时，是否授权从人物身份参考图开始？

模拟用户选择:
继续 prompt-only。理由: 本测试只验证前置拦截和顺序生成策略，不生成真实媒体。
```

DIRcreative:

```text
阶段: QA 与重试规则
智能体创作内容:
- 用户不是第一道质检。
- 失败图不能进入用户锁定。
- 失败只重试最小环节: 人物图、场景/FOV 图、storyboard/motion page、clean frame、或某个视频模型 prompt。
- storyboard/motion page 不能作为 Kling/Runway direct I2V input。
- clean frame 必须无文字、无分栏、无箭头，并继承已锁人物和场景。

用户确认点:
是否认可这个“看看图”前置拦截流程继续保持 prompt-only？

模拟用户选择:
认可。理由: 当前测试只验证前置拦截，不调用真实 image generation。

预演结论:
PASS。这个流程能拦住“看看图”导致的过早出图，并把 assisted_generation 收束到可控顺序。
```

skill_run_receipt:
  run_id: assisted-generation-preflight-chat-transcript-2026-05-17
  skill_id: chat-facilitator
  input_artifacts:
    - docs/film-preproduction/live-chat-start-protocol.md
    - .dircreative/runs/fog-route-cleaner-assisted-generation.yaml
  output_artifacts:
    - examples/assisted-generation-preflight-chat/01-chat-transcript.md
  decisions:
    - "Treat image requests as chat-visible preflight gates, not as permission to bypass story, shot, reference, and contract locks."
    - "Keep the dry run prompt-only while showing the exact first assisted-generation step."
  unresolved_questions:
    - "Real user must explicitly authorize any actual image generation."
  qa_gate:
    status: pass
    reasons:
      - "Transcript blocks premature image generation, shows the earliest unresolved gate, and records sequential assisted-generation rules."
  next_recommended_skill: checkpoint
