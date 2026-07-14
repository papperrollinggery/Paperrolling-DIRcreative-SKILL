# Ad Reference Pack Repair Example

artifact:
  artifact_id: noodle-ad-reference-pack-repair-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-chat-interface-demo-v1
  status: approved
  owner_skill: chat-facilitator

## Purpose

Show the corrected chat behavior after the user asks why a single clean frame was generated instead of a proper ad reference pack.

## Corrected Chat Response

```text
阶段: 参考图生成确认

你说得对。刚才直接生成单张 clean frame 是错误执行。

原因:
- clean frame 只能给可灵 / Runway 做直接 I2V 首帧；
- 它不能代替广告参考图组；
- 它没有产品身份板、风格材质板、故事板运动说明；
- 它也不该承担包装文字和广告识别。

智能体创作内容:
我应该先给你这 4 组图，并说明每张图的用途:

1. 产品身份板
   用途: 锁定包装、品牌名、杯型、封条、汤面、蒸汽、材质。
   文字策略: 允许清晰品牌/产品文字。
   视频模型策略: 不直接作为可灵/Runway 首帧。

2. 黑金灯光/材质板
   用途: 锁定黑桌面、金色切光、冷蓝城市反光、蒸汽真实度。
   文字策略: 少量大字标签可用于人类审查。
   视频模型策略: 风格参考，不直接做 I2V 首帧。

3. 5 镜头故事板
   用途: 展示 S01-S05、时长、景别、镜头运动、主体动作、转场。
   文字策略: 允许大号镜头编号和运动标注。
   视频模型策略: 给人、Seedance、Veo 理解节奏；禁止直接喂给可灵/Runway。

4. Clean Frames 组
   用途: S01 起始帧、S03 蒸汽微距帧、S05 产品英雄帧。
   文字策略: 无文字、无箭头、无分栏、无镜头编号。
   视频模型策略: 可灵/Runway 直接 I2V 输入。

用户确认点:
你要我现在按哪个方案生成？
1. 先生成完整 4 组图；
2. 先生成产品身份板 + clean frames；
3. 只重写 4 组图的 JSON 提示词，不生图。
```

## Acceptance Notes

- The response admits the execution error.
- The response distinguishes ad reference boards from clean frames.
- The response restores a user choice before generation.
- The response includes camera movement and subject movement in the storyboard board requirement.
- The response does not treat one generated image as a complete ad reference pack.

skill_run_receipt:
  run_id: noodle-ad-reference-pack-repair-2026-05-16
  skill_id: chat-facilitator
  input_artifacts:
    - examples/live-user-sim-noodle/16-chat-interface-demo.md
  output_artifacts:
    - examples/live-user-sim-noodle/17-ad-reference-pack-repair.md
  decisions:
    - "Add a repair example for the single-clean-frame failure mode."
  unresolved_questions:
    - "A live run still needs the user to choose which reference pack generation route to take."
  qa_gate:
    status: pass
    reasons:
      - "The corrected response exposes the error, restores the pack gate, and asks one decision question."
  next_recommended_skill: reference-image-planner
