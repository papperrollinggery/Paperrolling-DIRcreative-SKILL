# Ad Reference Pack Generation Gate

Verified: 2026-05-16

Purpose: prevent DIRcreative from jumping from a user choice directly into one isolated image generation when the deliverable is an ad film.

## Core Rule

For an advertising film, image generation must start from an approved reference pack, not from a single isolated clean frame.

Clean frames are only one part of the pack. They are useful for direct image-to-video models, but they do not replace product identity, ad art direction, or storyboard/motion planning.

## Required Pack For Ad Films

Default pack:

1. `product_identity_board`
   - Locks product shape, packaging, brand/product text, logo placement, hero angle, material, food or product truth.
   - May contain clear readable text.
   - Not a direct Kling/Runway first frame when it has labels, callouts, or multiple panels.

2. `lighting_material_style_board`
   - Locks lighting grammar, palette, surface behavior, atmosphere, texture and artifact guards.
   - Includes anti-fish-scale, anti-over-sharpening, anti-noise, anti-plastic rules.
   - Used for human approval and style consistency.

3. `storyboard_motion_board`
   - Shows shot order, duration, framing, camera movement, subject movement, and transition logic.
   - Must include shot movement descriptions when the user is planning video.
   - Must not be used as a direct first frame for Kling/Runway.

4. `clean_frames`
   - Text-free, label-free, panel-free still frames for direct I2V.
   - Usually includes start frame, key motion frame, and end/hero frame.
   - Must be derived from approved product identity and style decisions.

## Chat Gate Before Any Image Generation

Before calling an image generation tool, DIRcreative must show this in chat:

```text
阶段: 参考图生成确认
智能体创作内容:
- 本次要生成的参考图组: <board list>
- 每张图的用途: <role>
- 哪些图可以直接喂给视频模型: <direct I2V inputs>
- 哪些图只能做人类/Seedance/Veo 参考: <dense boards>
- 文字策略: <which images may include text, which must be no-text>
- 镜头运动策略: <which board records camera/subject movement>

用户确认点:
确认生成整组，还是只生成其中几张？
```

If the user asks for clean frames before the pack is approved, ask a correction question:

```text
你现在选的是 clean frames，但广告片还缺产品身份板/风格材质板/故事板。
建议先生成完整参考图组，或者至少生成产品身份板 + clean frames。
你选哪种？
```

## Prompt Writing Requirements

Use JSON-first prompts.

Every generated image prompt must specify:

- image role,
- primary job,
- aspect ratio,
- whether text is allowed,
- exact visible text if text is allowed,
- layout policy,
- art-directed asymmetry rule,
- material truth,
- camera/framing notes,
- motion notes if it is a storyboard/motion board,
- direct video input policy,
- must-not-animate list,
- artifact guard.

## Layout Rules

Reuse the user-specified art direction pattern:

- do not use a generic layout,
- do not use an evenly distributed grid unless the image is explicitly a technical sheet,
- do not create symmetry for its own sake,
- composition must feel art-directed, intentional, and slightly asymmetric,
- every panel must have a production purpose,
- text must be large enough to read if present,
- boards with text, arrows, panel borders, or timing notes are planning references, not direct I2V frames.

## Failure Conditions

The workflow is wrong if:

- it generates one clean frame before showing the full ad reference pack plan,
- it uses `no readable text` for a product identity board that must establish packaging,
- it omits shot movement/camera movement from the storyboard board,
- it treats a storyboard board as a direct Kling/Runway first frame,
- it says the ad reference step is done when only one cup image exists,
- it hides the image generation plan inside YAML instead of showing it in chat.
