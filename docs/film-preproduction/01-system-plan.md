# Film Preproduction Agent System Plan

## 核心定位

目标不是做一个生图 prompt 工具，而是做一个从一句想法进入影视前期制作流程的 agent 系统。

主链路：

```text
一句想法
-> 灵感读取
-> 导演组讨论
-> 渠道/片型判断
-> 初步创意
-> 故事大纲
-> Treatment
-> 脚本
-> 脚本拆解
-> 镜头设计
-> 视觉圣经
-> 分镜/参考图组 Prompt Compiler
-> 视频模型 Prompt Adapter
-> 生成结果 QA
-> 迭代修正
```

`Storyboard Prompt Compiler` 只是后段模块。它的输入必须来自前面的故事、脚本、镜头、资产、声音和模型约束，不能直接从一句想法跳到最终生图提示词。

## 成功标准

系统必须做到：

- 用户只给一句模糊想法，也能被引导到专业前期产物。
- 不同渠道给出不同建议，不把电影、广告、短剧、短视频、MV 用同一套结构处理。
- 每一步都有结构化产物，后一步只消费前一步确认过的内容。
- 生成图片组前，已经明确人物、场景、道具、镜头、声音、时长、模型目标。
- 视频 prompt 明确解释每张参考图的用途，防止模型把分镜板、表格、文字标签当成要动画化的画面内容。
- 每次生成都记录 prompt、参考图、模型、参数、失败原因和修正策略。

## 非目标

- 不先做全自动一键成片。
- 不先做通用 AI 视频平台。
- 不先做复杂前端编辑器。
- 不把所有专业知识硬编码进一个超长 prompt。
- 不把 `Prompt Compiler Skill` 当成完整产品。

## 专业知识底座

### Film Production Ontology

必须先沉淀影视制作对象和关系。

核心对象：

- idea：原始想法、灵感碎片、参考链接、参考图片
- concept：一句话创意、主题、情绪、类型、受众
- outline：故事大纲、段落、起承转合、关键场面
- treatment：以散文方式描述完整视听体验
- script：场景、动作、对白、旁白
- script_breakdown：人物、场景、道具、服装、妆发、特效、声音、特殊设备
- shot_list：镜头编号、时长、景别、角度、焦段、机位、运镜、动作、声音、备注
- storyboard：画面构图、blocking、镜头运动箭头、时间、对白/声音备注
- visual_bible：人物、场景、道具、灯光、色彩、材质、风格一致性
- video_prompt：面向具体视频模型的执行 prompt
- generation_run：模型、参数、输入、输出、失败原因、修正记录

### 影视术语范围

第一版知识库至少覆盖：

- 景别：ECU、CU、MCU、MS、MLS、FS、WS、EWS、establishing shot
- 角度：eye-level、low angle、high angle、top-down、POV、OTS、Dutch angle
- 运镜：static、pan、tilt、dolly、truck、pedestal、tracking、crane、drone、handheld、whip pan、arc、dolly zoom、rack focus
- 镜头属性：lens、focal length、depth of field、anamorphic、macro、frame rate、slow motion
- 场面调度：blocking、eyeline、screen direction、axis/180-degree rule、foreground/midground/background
- 剪辑：cut、match cut、jump cut、cross cut、montage、prelap、transition、rhythm
- 美术：production design、set dressing、props、wardrobe、texture、material、palette、practical light
- 声音：dialogue、voiceover、SFX、foley、ambience、score、music cue、diegetic、non-diegetic、silence

## 渠道策略库

### 电影 / 短片

重点：

- 主题、人物弧光、情绪递进
- 场面调度和镜头语言
- 画面构图、光线、声音、节奏统一
- 镜头不是只服务信息，还服务心理和主题

输出偏好：

- logline
- treatment
- scene outline
- shot list
- visual bible
- sound mood board

### 广告 / 产品片

重点：

- 产品利益点
- 品牌记忆点
- 使用场景
- 前 3-6 秒 hook
- packshot / product hero / CTA
- 15s、30s、60s 结构差异

输出偏好：

- creative brief
- audience + insight
- hook/body/close
- product demonstration beats
- product asset board
- CTA variants
- channel cutdowns

### 短剧 / 竖屏剧

重点：

- 竖屏 9:16
- 近景和脸部情绪
- 每集开头 hook
- 单集冲突升级
- 结尾 cliffhanger
- 少场景、小演员、快节奏

输出偏好：

- episode beat sheet
- hook/escalation/cliffhanger
- vertical blocking
- close-up based shot list
- recurring character bible

### 短视频 / 社媒内容

重点：

- 前 1-3 秒明确内容价值
- 信息密度
- 字幕/贴纸/平台原生感
- 声音和节奏
- 可复看点
- 强 CTA 或互动点

输出偏好：

- hook variants
- beat-by-beat script
- caption/text overlay plan
- sound-first plan
- platform aspect ratio plan

### MV / 概念片

重点：

- 音乐结构
- 情绪曲线
- 视觉母题
- 色彩和符号系统
- 镜头节奏跟随音乐段落

输出偏好：

- music map
- visual motif list
- beat-synced storyboard
- mood board
- lighting/color progression

## 多智能体导演组

### Producer / 制片策划

职责：

- 明确目标、渠道、受众、时长、预算感、交付形式。
- 判断当前想法是否适合电影、广告、短剧、短视频或 MV。
- 控制范围，避免创意变成不可执行项目。

输出：

- project_brief
- constraints
- channel_recommendation
- deliverable_plan

### Creative Director / 创意总监

职责：

- 提炼核心概念、情绪、卖点、视觉符号。
- 生成 2-3 个创意方向并解释取舍。
- 保持创意统一，不让后续步骤散掉。

输出：

- concept_options
- selected_concept
- tone_statement
- visual_hook

### Director / 导演

职责：

- 决定叙事方式、表演、场面调度、镜头策略。
- 把文学描述转成视听表达。
- 指定每场戏的导演意图。

输出：

- director_statement
- scene_intent
- performance_notes
- blocking_notes

### Screenwriter / 编剧

职责：

- 建立故事结构、人物关系、冲突和对白/旁白。
- 根据渠道控制节奏和信息释放。

输出：

- outline
- treatment
- script
- dialogue_or_vo

### Cinematographer / 摄影指导

职责：

- 设计景别、焦段、机位、运镜、光线、画面结构。
- 确保镜头是可执行的，不是抽象形容词堆叠。

输出：

- shot_language
- camera_plan
- lighting_plan
- lens_plan

### Production Designer / 美术指导

职责：

- 设计场景、道具、服装、材质、色彩。
- 建立视觉连续性。

输出：

- environment_board_plan
- prop_board_plan
- wardrobe_material_notes
- palette

### Editor / 剪辑指导

职责：

- 设计节奏、转场、信息释放、镜头长度。
- 检查镜头能否剪成完整段落。

输出：

- pacing_plan
- transition_notes
- shot_duration_review

### Sound Designer / 音频指导

职责：

- 判断是否需要对白、旁白、环境声、音效、音乐或静音。
- 区分 diegetic / non-diegetic。
- 根据模型能力决定声音是否写入视频 prompt。

输出：

- audio_plan
- dialogue_plan
- sfx_plan
- music_cue_plan
- silent_mode_decision

### Model Prompt Engineer / 模型适配工程师

职责：

- 把镜头和资产翻译成模型能理解的 prompt。
- 为 Seedance、Kling、Runway、Veo 输出不同版本。
- 防止模型误读参考图。

输出：

- image_prompt_manifest
- video_prompt_manifest
- model_specific_prompts
- prompt_risk_notes

### Continuity QA / 场记与质检

职责：

- 检查人物、服装、道具、场景、镜头方向、声音连续性。
- 检查是否缺少必要资产。
- 检查 prompt 是否过载、矛盾、不可执行。

输出：

- continuity_report
- missing_assets
- contradiction_report
- retry_plan

## 视频模型适配层

### Seedance Adapter

已知倾向：

- 适合多参考图、多模态、多镜头短片。
- 官方论文描述支持 4-15 秒生成；开放平台参考输入可到 9 张图、3 段视频、3 段音频。
- 适合用参考图绑定角色、场景、道具，再用 shot flow 控制镜头。

Prompt 策略：

- 明确 `Reference Map`：哪张图是角色，哪张是场景，哪张是道具，哪张是分镜。
- 明确 `Do not animate the storyboard sheet itself`。
- 使用 chronological shot flow。
- 强化 continuity：same face、same costume、same location logic、same prop state。
- 音频如果使用，单独写 audio section，不混进视觉句子。

### Kling / 可灵 Adapter

已知倾向：

- 图生视频重点是动作控制。
- 官方 Image-to-Video 指南给出的核心是 `Subject + Movement, Background + Movement`。
- 动作不能明显偏离图片，否则容易切镜或乱解释。
- Kling 3.0 多镜头能力适合指定每镜头内容、时长、视角、运镜。

Prompt 策略：

- 图生视频时少重复图片已有视觉细节。
- 优先写主体动作、背景动作、相机动作。
- 多主体要用位置语言：left subject、right subject、background vehicle。
- 多镜头模式写 shot-by-shot，不让模型自动乱剪。

### Runway Adapter

已知倾向：

- Gen-4 / Gen-4.5 图生视频更适合 5-10 秒单场景。
- 官方建议 prompt 聚焦 motion，不要重复描述输入图。
- 负面表达不稳定，应使用正向描述。

Prompt 策略：

- 输入图负责视觉，prompt 负责动作。
- 每次只控制一个主要运动目标。
- 使用简单直接语言。
- 需要静止镜头时写 `locked-off camera remains still`，不用 `no movement`。
- 复杂多镜头应拆成多个 run。

### Veo Adapter

已知倾向：

- 官方 prompt guide 强调 subject、context、action、style、camera angles、camera movements、lighting、mood、temporal elements。
- Veo 3 系列常见优势是原生音频；音频必须明确提示。

Prompt 策略：

- 使用完整但不矛盾的结构：subject + action + setting + camera + lighting + style + audio。
- 音频单独写：dialogue、ambient sound、SFX、music、silence。
- 如果需要人声，写清楚说话者、语气、语言、台词。
- 如果不要声音，写 `silent video, no dialogue, no music, no sound effects`。

## 图片提示词与声音策略

图片 prompt 原则：

- 图片不生成声音。
- 纯视觉图不写音乐和音效。
- 分镜导演板可以写 `Audio Plan` 标签，但只是给人和后续 video adapter 读取。
- 不指望视频模型从图片中文字准确推断声音。

声音决策问题必须在视频生成前问清或自动推断：

- 是否需要人声？
- 人声是 dialogue 还是 voiceover？
- 是否需要背景音乐？
- 是否需要环境声？
- 是否需要音效或 Foley？
- 是否需要静音版，后期单独配音配乐？
- 目标模型是否支持稳定音频？
- 目标渠道是 sound-on 还是 sound-off 优先？

默认策略：

- 电影/短片：输出声音设计计划，但视频模型是否生成声音按目标模型决定。
- 广告：必须明确 VO、BGM、SFX、CTA 是否进入视频 prompt。
- 短剧：对白/情绪声优先，音乐谨慎。
- 短视频：字幕和声音 hook 同时设计。
- MV：音乐先行，镜头跟音乐结构。

## WYSIWYG 前端产物结构

前端不应是一个 prompt 输入框。

核心视图：

- Idea Board：灵感、参考、关键词、用户偏好
- Director Room：不同角色意见、冲突点、推荐决策
- Story View：logline、大纲、treatment、脚本
- Shot Table：每个镜头的所有字段
- Visual Bible：人物、场景、道具、色彩、灯光
- Storyboard Board：分镜图、镜头表、时间轴
- Prompt Manifest：图片 prompt、视频 prompt、模型适配版本
- Generation Runs：每次生成的输入、输出、评分、失败原因

每个镜头最小字段：

```yaml
shot_id:
duration:
channel:
aspect_ratio:
story_beat:
shot_size:
camera_angle:
lens:
camera_motion:
subject_action:
blocking:
scene_reference:
character_reference:
prop_reference:
dialogue:
voiceover:
sfx:
music:
silence:
target_model:
image_prompt:
video_prompt:
negative_or_avoid_notes:
generated_output:
failure_notes:
retry_instruction:
```

## QA Gates

### Story Gate

- 是否有明确主题或传播目标。
- 是否有清晰人物/产品/信息主体。
- 是否适配目标渠道。
- 是否有可执行时长。

### Script Gate

- 是否有完整段落。
- 是否有冲突、变化或信息推进。
- 是否有对白/旁白/静音决策。
- 是否没有过多抽象形容。

### Shot Gate

- 每个镜头是否有景别、角度、动作、运镜、时长。
- 镜头之间是否可剪辑。
- 是否存在轴线、方向、空间关系错误。
- 是否有镜头过载。

### Visual Bible Gate

- 人物是否一致。
- 场景空间是否清晰。
- 道具状态是否明确。
- 色彩、材质、灯光是否统一。

### Image Prompt Gate

- 参考图组是否分工明确。
- 单张图是否过密或过小。
- 文字是否可读。
- 是否避免无用装饰和空白。
- 是否标明图像角色：character / environment / prop / storyboard / style。

### Video Prompt Gate

- 是否映射参考图。
- 是否说明不要动画化分镜板/表格。
- 是否按目标模型重写。
- 是否有音频策略。
- 是否没有互相冲突的动作和运镜。

### Generation QA Gate

- 角色一致性。
- 场景一致性。
- 道具状态。
- 动作执行。
- 镜头运动。
- 声音执行。
- 渠道适配。
- 是否需要重试、拆镜头或换模型。

## 第一版系统边界

MVP 只做本地文本与 Markdown 产物，不做完整前端。

MVP 输入：

```text
一句想法 + 可选渠道 + 可选时长 + 可选参考图/链接说明
```

MVP 输出：

```text
project_brief
director_room_notes
concept_options
selected_concept
outline
treatment
script
script_breakdown
shot_list
visual_bible_plan
image_prompt_manifest
video_prompt_manifest
qa_report
```

MVP 不负责直接调用图像或视频模型。

## 参考资料

- StudioBinder Shot List Guide: https://www.studiobinder.com/blog/shot-list-template-free-download/
- StudioBinder Storyboard Camera Movement: https://www.studiobinder.com/blog/storyboard-camera-movement/
- Tools for Film Storyboard Glossary: https://www.toolsforfilm.com/glossary/storyboard
- Script Breakdown: https://en.wikipedia.org/wiki/Script_breakdown
- CineVision Previsualization Paper: https://arxiv.org/abs/2507.20355
- Screenplayology Sound and Silence: https://www.screenplayology.com/content-sections/screenplay-form-content/3-7/
- Seedance 2.0 Paper: https://arxiv.org/abs/2604.14148
- Kling Image-to-Video Guide: https://kling.ai/quickstart/image-to-video-guide
- Runway Gen-4 Prompt Guide: https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide
- Runway Image-to-Video Prompting Guide: https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide
- Veo Prompt Guide: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide
- TikTok Creative Best Practices: https://ads.us.tiktok.com/help/article/creative-best-practices
