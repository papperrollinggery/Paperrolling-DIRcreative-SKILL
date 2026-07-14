# Film Preproduction Agent Execution Roadmap

## 执行原则

先做知识和流程，再做 skill。

顺序：

```text
Goal-ready contract layer
-> gstack-grade skill integration architecture
-> 研究资料
-> 建知识库
-> 定产物 schema
-> 做单链路文本 MVP
-> 做导演组 agent 编排
-> 做图片 prompt compiler
-> 做视频模型 adapter
-> 做 QA 和重试机制
-> 再考虑前端 WYSIWYG
```

原始内容层顺序：

```text
研究资料
-> 建知识库
-> 定产物 schema
-> 做单链路文本 MVP
-> 做导演组 agent 编排
-> 做图片 prompt compiler
-> 做视频模型 adapter
-> 做 QA 和重试机制
-> 再考虑前端 WYSIWYG
```

每阶段都必须有可检查产物。没有产物就不算完成。

## Phase A：Goal-ready contract layer

目标：让后续 Goal 模式或 gstack skill 能读一个入口文件就知道当前阶段、允许编辑范围、产物、验收和下一步。

产物：

```text
docs/film-preproduction/03-office-hours-optimization-plan.md
docs/film-preproduction/04-goal-mode-handoff.md
docs/film-preproduction/phase-contracts.yaml
```

验收：

- 每个阶段都有 inputs、outputs、allowed_edits、non_goals、done_when、next_phase。
- README 有 Goal Mode Entry。
- 后续 worker 不需要重新推断执行边界。
- YAML 可解析。
- 无 placeholder markers。

## Phase 0：资料研究与知识采集

目标：建立专业影视和模型适配的事实底座，避免后面靠空泛 prompt 硬编。

工作项：

- 收集影视前期制作资料：script breakdown、shot list、storyboard、previs、sound design。
- 收集渠道资料：电影、广告、短剧、短视频、MV。
- 收集模型资料：Seedance、Kling/可灵、Runway、Veo。
- 建立术语表：中英术语、定义、适用场景、prompt 写法。
- 建立案例库：成功分镜板、失败分镜板、视频 prompt 案例。

产物：

```text
docs/film-preproduction/research/film-production-glossary.md
docs/film-preproduction/research/channel-playbooks.md
docs/film-preproduction/research/model-adapter-notes.md
docs/film-preproduction/research/audio-design-notes.md
docs/film-preproduction/research/storyboard-reference-analysis.md
```

验收：

- 每个术语都有定义、用途、示例。
- 每个渠道都有结构模板和禁忌。
- 每个模型都有 prompt 策略和不适合做的事。
- 声音策略明确区分图片 prompt、视频 prompt、后期音频。

## Phase 1：统一数据结构

目标：让所有 agent 和 skill 读写同一套结构，不靠自然语言来回传。

工作项：

- 定义 project schema。
- 定义 idea intake schema。
- 定义 director room schema。
- 定义 story / script / shot / asset schema。
- 定义 image prompt manifest。
- 定义 video prompt manifest。
- 定义 QA report schema。

建议文件：

```text
docs/film-preproduction/schemas/project.yaml
docs/film-preproduction/schemas/director-room.yaml
docs/film-preproduction/schemas/story-package.yaml
docs/film-preproduction/schemas/shot-list.yaml
docs/film-preproduction/schemas/visual-bible.yaml
docs/film-preproduction/schemas/image-prompt-manifest.yaml
docs/film-preproduction/schemas/video-prompt-manifest.yaml
docs/film-preproduction/schemas/qa-report.yaml
```

最小 project schema：

```yaml
project:
  title:
  raw_idea:
  channel:
  target_duration:
  aspect_ratio:
  audience:
  tone:
  references:
  constraints:
  status:

creative:
  logline:
  theme:
  concept:
  visual_hook:
  story_promise:

production:
  characters:
  locations:
  props:
  wardrobe:
  sound_policy:
  target_models:

deliverables:
  outline:
  treatment:
  script:
  shot_list:
  visual_bible:
  image_prompt_manifest:
  video_prompt_manifest:
  qa_report:
```

验收：

- 后续每个模块都能明确读什么、写什么。
- 每个字段都有 owner。
- 不存在只有人类能理解、agent 无法消费的产物。

## Phase 2：一句想法到初步创意

目标：先打通最前段，避免系统一开始就掉进分镜 prompt。

输入：

```text
雨夜，一个赛博快递员必须把机密包裹送到一条没人敢进去的巷子。
```

工作项：

- Idea Intake 读取原始想法。
- Producer 判断渠道和交付形式。
- Creative Director 提 2-3 个创意方向。
- Director 给出视听方向。
- Screenwriter 给出 logline 和故事钩子。
- Channel Strategist 给出渠道改写建议。
- QA 检查范围是否过大、是否需要追问。

产物：

```text
examples/cyber-courier/01-idea-intake.md
examples/cyber-courier/02-director-room-notes.md
examples/cyber-courier/03-concept-options.md
examples/cyber-courier/04-selected-concept.md
```

验收：

- 不直接生成镜头。
- 有明确渠道建议。
- 有 2-3 个创意方向和推荐理由。
- 有必须追问的问题清单。

## Phase 3：创意到故事大纲和 Treatment

目标：把选定创意变成可拍的故事结构。

工作项：

- 生成 logline。
- 生成 beat sheet。
- 生成 treatment。
- 根据渠道压缩或扩展。
- 让导演、编剧、剪辑分别 review。

产物：

```text
examples/cyber-courier/05-logline.md
examples/cyber-courier/06-beat-sheet.md
examples/cyber-courier/07-treatment.md
examples/cyber-courier/08-story-review.md
```

验收：

- 故事有开始、发展、转折、结束。
- 每个段落有明确情绪和信息推进。
- 广告/短视频必须有 hook 和 CTA 逻辑。
- 短剧必须有冲突升级和 cliffhanger。
- 电影/短片必须有主题和人物变化。

## Phase 4：Treatment 到脚本和脚本拆解

目标：把故事转成可拆解、可分镜的文本。

工作项：

- 输出脚本。
- 标注对白/旁白/动作。
- 做 script breakdown。
- 提取人物、场景、道具、服装、声音、特殊镜头需求。
- 判断是否需要补资产设定。

产物：

```text
examples/cyber-courier/09-script.md
examples/cyber-courier/10-script-breakdown.yaml
examples/cyber-courier/11-asset-requirements.md
examples/cyber-courier/12-audio-policy.md
```

验收：

- 每个场景可拆。
- 每个重要道具和人物状态有记录。
- 声音策略明确：静音、人声、旁白、音乐、音效。
- 不存在脚本里出现但资产表缺失的核心元素。

## Phase 5：脚本到镜头设计

目标：把脚本变成专业 shot list。

工作项：

- Director 定每个镜头的意图。
- Cinematographer 定景别、焦段、角度、机位、运镜。
- Editor 定镜头长度、节奏、转场。
- Sound Designer 定每镜头声音。
- QA 检查镜头是否可剪、是否空间关系清晰。

产物：

```text
examples/cyber-courier/13-shot-list.yaml
examples/cyber-courier/14-camera-plan.md
examples/cyber-courier/15-blocking-plan.md
examples/cyber-courier/16-shot-qa.md
```

shot list 最小字段：

```yaml
shots:
  - shot_id:
    duration:
    story_beat:
    shot_size:
    camera_angle:
    lens:
    camera_motion:
    subject_action:
    blocking:
    location:
    characters:
    props:
    dialogue:
    voiceover:
    sfx:
    music:
    transition:
    narrative_purpose:
```

验收：

- 每个镜头都能直接交给 storyboard prompt compiler。
- 每个镜头只有一个主动作。
- 运镜和主体动作不冲突。
- 镜头时长符合目标模型能力。

## Phase 6：视觉圣经和参考图组规划

目标：先决定要生成哪些参考图，而不是直接写生图 prompt。

工作项：

- 人物设定板规划。
- 场景设定板规划。
- 道具/产品板规划。
- 灯光/色彩/风格板规划。
- 分镜导演板规划。
- 判断单页还是多图组。

产物：

```text
examples/cyber-courier/17-visual-bible.md
examples/cyber-courier/18-reference-pack-plan.yaml
examples/cyber-courier/19-image-layout-spec.md
```

参考图组默认结构：

```yaml
reference_pack:
  - id: image_01
    type: character_design_board
    purpose: lock character identity, costume, expressions, action poses
  - id: image_02
    type: environment_blocking_board
    purpose: lock location, spatial relation, camera paths
  - id: image_03
    type: prop_product_board
    purpose: lock key props, material, interaction details
  - id: image_04
    type: director_storyboard_board
    purpose: lock shot sequence and camera plan
  - id: image_05
    type: lighting_style_board
    purpose: lock mood, palette, lens texture
```

验收：

- 每张图有明确用途。
- 不把所有内容硬塞进一张图。
- 图内信息尺寸足够大，视频模型可读。
- 分镜板中的文字是辅助，不是让视频模型自行解析的唯一依据。

## Phase 7：图片 Prompt Compiler

目标：把视觉圣经和参考图规划编译成 Image2 / GPT Image 可用 prompt。

工作项：

- 使用 JSON-first prompt config，而不是直接拼长段落。
- 从 prompt pattern registry 选择 2-3 个相关 pattern。
- 合并 art-directed layout policy、material truth、consistency locks、surface integrity guard。
- 校验 style config schema。
- 为每张参考图生成 prompt。
- 明确布局、模块、文字、大小、密度。
- 指定可读文字。
- 指定禁止项：伪文字、无用装饰、过小面板、纯氛围图。
- 输出 prompt manifest。

编译器基础文件：

```text
docs/film-preproduction/research/image-prompt-style-system.md
docs/film-preproduction/schemas/image-prompt-style-config.schema.json
docs/film-preproduction/templates/image-prompt-style-config.template.json
docs/film-preproduction/prompt-pattern-registry.json
```

产物：

```text
examples/cyber-courier/20-image-prompt-manifest.yaml
examples/cyber-courier/prompts/image_01_character_board.txt
examples/cyber-courier/prompts/image_02_environment_board.txt
examples/cyber-courier/prompts/image_03_prop_board.txt
examples/cyber-courier/prompts/image_04_storyboard_board.txt
examples/cyber-courier/prompts/image_05_style_board.txt
```

验收：

- prompt 能独立复制使用。
- 每张图 role 清晰。
- 布局明确。
- 标签可读。
- 不出现“高级感”“电影感”这类无约束词单独承担核心指令。
- 每张图有 JSON style config、selected pattern ids、art_direction_policy、surface_integrity_guard。
- prompt registry 记录来源、适用场景、失败模式、promote/deprecate 规则。

## Phase 8：视频模型 Prompt Adapter

目标：把同一套镜头和参考图，适配成不同视频模型能执行的 prompt。

工作项：

- Seedance adapter。
- Kling adapter。
- Runway adapter。
- Veo adapter。
- 每个 adapter 输出 model-specific prompt。
- 每个 adapter 输出风险提示和推荐参数。

产物：

```text
examples/cyber-courier/21-video-prompt-manifest.yaml
examples/cyber-courier/prompts/video_seedance.txt
examples/cyber-courier/prompts/video_kling.txt
examples/cyber-courier/prompts/video_runway.txt
examples/cyber-courier/prompts/video_veo.txt
examples/cyber-courier/22-model-adapter-risk-notes.md
```

不同模型默认策略：

```yaml
seedance:
  best_for: multi-reference, 4-15s, short multi-shot continuity
  prompt_style: reference map + chronological shot flow + continuity locks
  avoid: letting the model animate the storyboard sheet itself

kling:
  best_for: image-to-video motion control, custom multi-shot
  prompt_style: subject movement + background movement + shot duration
  avoid: actions that contradict the source image

runway:
  best_for: 5-10s single-scene motion from strong image
  prompt_style: simple positive motion description
  avoid: long multi-scene prompt, negative phrasing

veo:
  best_for: structured cinematic prompt with possible native audio
  prompt_style: subject + action + setting + camera + style + audio
  avoid: vague or conflicting audio/visual instructions
```

验收：

- 每个模型 prompt 不是同一文本换标题。
- 每个 prompt 都解释参考图用途。
- 每个 prompt 都包含声音策略。
- 每个 prompt 都有失败时的重试建议。

## Phase 9：QA 与重试机制

目标：让系统能识别“不专业”和“模型误读”，而不是只产出一次。

工作项：

- 建立 QA checklist。
- 建立生成结果评分维度。
- 建立失败类型分类。
- 建立 retry instruction 生成规则。

失败类型：

```yaml
failure_types:
  - character_drift
  - costume_drift
  - prop_missing
  - location_confusion
  - storyboard_sheet_animated
  - wrong_camera_motion
  - too_many_actions
  - bad_audio
  - no_audio_when_required
  - unwanted_text_or_labels
  - layout_unreadable
  - generic_grid_layout
  - fish_scale_texture
  - material_surface_artifact
  - model_refusal_or_filter
```

产物：

```text
docs/film-preproduction/qa/qa-checklist.md
docs/film-preproduction/qa/failure-taxonomy.yaml
docs/film-preproduction/qa/retry-rules.md
examples/cyber-courier/23-generation-qa-report.md
```

验收：

- 每种失败都有判断标准。
- 每种失败都有修正动作。
- 能决定是改 prompt、改参考图、拆镜头、换模型还是后期处理。

## Phase 10：Skill 化

目标：把稳定流程封装成可复用 skill 包。

建议包名：

```text
dircreative
```

skill 架构依据：

```text
docs/film-preproduction/05-skill-integration-architecture.md
docs/film-preproduction/schemas/skill-orchestration.yaml
```

内部 skill：

```text
idea-intake
director-room
channel-strategy
story-development
script-treatment
script-breakdown
shot-design
visual-bible
reference-image-planner
image-prompt-compiler
video-model-adapter
generation-qa
learn
update
checkpoint
```

第一版只实现文本产物生成，不调用外部图像/视频 API。

gstack-grade 要求：

- root skill 有 preamble、update check、routing、phase contract check。
- sub-skill 只能读写自己的 artifact contract。
- skill 之间通过 artifact、receipt、revision_request、qa_report 协同。
- 模型和 prompt pattern 通过 registry 更新，不靠手动改根提示词。
- `SKILL.md` 后续用模板生成，防止文档和实际 schema 漂移。
- 当前会话和采用状态只写入 `.dircreative/state/current.json`；可复用学习进入受版本控制的研究文档或 prompt registry。`tests/fixtures/runtime/history/` 仅供回归测试，不得作为 live state。

验收：

- 每个 skill 有清晰输入输出。
- 每个 skill 能独立测试。
- 每个 skill 不重复上游工作。
- 下游只读结构化产物，不猜上下文。
- 每个 skill 产出 `skill_run_receipt`。
- 每个 source/pattern/model adapter 有来源和验证日期。

## Phase 11：WYSIWYG 前端

目标：让用户看到的是影视前期工作台，不是 prompt 文件夹。

第一版前端模块：

- Project Navigator
- Idea Board
- Director Room Notes
- Story/Script Editor
- Shot Table
- Visual Bible Board
- Prompt Manifest Viewer
- Generation Run Log

关键交互：

- 用户能锁定某个创意版本。
- 用户能锁定某个镜头。
- 用户能查看每张参考图服务哪个镜头。
- 用户能比较 Seedance / Kling / Runway / Veo prompt 差异。
- 用户能记录某次生成失败原因。

验收：

- 用户能从一句想法走到 shot list。
- 用户能看到每一步为何产生。
- 用户能改某个字段并重新生成下游产物。
- 系统不会把修改后的内容和旧版本混用。

## 推荐第一轮实际任务

先做这 5 个文件：

```text
docs/film-preproduction/research/film-production-glossary.md
docs/film-preproduction/research/channel-playbooks.md
docs/film-preproduction/research/model-adapter-notes.md
docs/film-preproduction/schemas/project.yaml
examples/cyber-courier/01-idea-intake.md
```

原因：

- 这 5 个文件能建立专业底座。
- 能马上验证一句想法能不能被结构化。
- 还不会过早进入 UI 或生图。
- 后续所有 skill 都会依赖这些文件。

## 总体验收路线

### Milestone A：研究底座完成

通过条件：

- 有术语表。
- 有渠道策略。
- 有模型适配说明。
- 有声音策略。
- 有参考图组规范。

### Milestone B：单案例文本链路跑通

通过条件：

- 同一个案例从 idea 到 shot list 全部落地。
- 每一步有文件。
- 每一步都能解释为什么这样设计。

### Milestone C：Prompt Compiler 跑通

通过条件：

- 能输出完整参考图组 prompt。
- 能区分单页 production board 和多图 reference pack。
- 能检查图像 prompt 是否过密、过小、不可读。

### Milestone D：Video Adapter 跑通

通过条件：

- 同一套镜头能生成 Seedance / Kling / Runway / Veo 四套 prompt。
- 每套 prompt 都有参考图映射和声音策略。
- 每套 prompt 都有模型风险提示。

### Milestone E：Skill 包成型

通过条件：

- skill 拆分清晰。
- 每个 skill 有输入输出合同。
- 有示例。
- 有 QA gate。
- 有失败重试规则。

## 当前状态

已完成：

- 系统方向确认。
- 浏览器原会话阅读。
- 用户参考图分析。
- Seedance / Kling / Runway / Veo 第一批资料核对。
- 系统规划第一版。
- 执行路线第一版。
- Office Hours 设计审查。
- Goal-ready contract layer 第一版。
- Phase 0 研究库第一版：术语、渠道、模型、声音、分镜参考图规范。
- Phase 1 schema 第一版：project、director-room、story-package、shot-list、visual-bible、image/video prompt manifest、QA report。
- Phase 2 cyber-courier 示例起步：idea intake、director room、concept options、selected concept。
- Phase B cyber-courier story package：logline、beat sheet、treatment、story review。
- Phase C cyber-courier script package：script、breakdown、asset requirements、audio policy。
- Phase D cyber-courier shot design：shot list、camera plan、blocking plan、shot QA。
- Phase E cyber-courier visual bible：visual bible、reference pack plan、image layout spec。
- Phase F cyber-courier image prompt compiler：JSON-first image manifest and five prompt files。
- Phase G cyber-courier video adapters：Seedance、Kling、Runway、Veo prompt manifests and risk notes。
- Phase H skill packaging：root skill, sub-skills, QA docs, source registries, validation script, generation QA template, RainLock product ad fixture。
- Phase I WYSIWYG workbench plan：product spec、data flow、interface plan。
- Phase J model-safe reference pack policy：Seedance/Kling/Runway/Veo/TapNow 参考图逻辑、reference locking、reference-pack-manifest schema、fixture reference pack 升级。
- Phase K longform + capability-aware workflow：15s/60s/90s/180s 拆分策略、prompt_only/assisted_generation/external_generation、sequence-plan schema、longform-reference-pack schema、RainLock 180s fixture。
- Zombie Cleaner E2E test fixture：参考公开《丧尸清道夫》类型基准但不复刻，完成原创 180s prompt-only genre short 从 idea 到视频 prompt manifest 的链路。

未完成：

- 后续真实前端实现。
- 后续真实图片/视频生成验证。

下一步：

```text
执行最终 audit：
1. 运行 scripts/validate_project.py
2. 运行 YAML/JSON/placeholder/git diff 验证
3. 核对目标要求到具体文件证据，尤其是 longform sequence plan、reference pack manifest、asset_output status、模型 direct input policy
4. 如无缺口，保持 git clean
```
