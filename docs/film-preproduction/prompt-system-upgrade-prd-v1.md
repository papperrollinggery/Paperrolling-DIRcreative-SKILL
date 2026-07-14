# DIRcreative Prompt System Upgrade PRD v1.0

状态：P0/P1 可执行基础已落地，真实外部生成、安装与 live acceptance 未验证

范围：图像 prompt、视频 prompt、参考图/clean frame、TabNow/TapNow 节点交付、Seedance 2.0 adapter、未来 30 秒模型兼容、生成 QA 与问题处置。

本文件既定义完整产品路线，也记录已落地的 P0/P1 基础。当前已经具备可执行 Prompt IR JSON Schema、语义校验与终端文本编译器、10/15/30 秒 fixture、多人物/多资产 fixture、模型 adapter 表面测试和 prompt-only QA；不代表 TabNow 节点、Seedance 真实生成、正式安装或用户 live acceptance 已完成。

### 当前落地边界（2026-07-13）

- 已落地：`schemas/prompt-ir.schema.json`、`scripts/dircreative_prompt_compiler.py`、`scripts/dircreative_prompt_fixture_audit.py`、`tests/fixtures/prompt-system/`、Seedance 10 秒镜像案例的确定性编译结果。
- 已验证范围：schema/语义、内部字段清洗、最小“角色图 + 场景图”、多人多资产动作归属、10/15/30 秒分段、Sora/Runway/Kling/Veo 的本地字符串编译 smoke test、能力卡精确解析与负向 fixture。
- adapter 证据边界：本地 smoke test 只证明编译文本形态和能力卡映射没有漂移；各平台真实接收、生成质量和运行时行为仍未验证。
- 未验证范围：任何外部模型的真实生成质量、原生音频表现、平台上传/节点执行、正式安装一致性、用户 live acceptance。
- 禁止推断：fixture 通过不等于模型生成通过；prompt-only 回执不等于生成回执或最终验收。

## 1. 产品定义

### 1.1 产品定位

不是一个“把想法扩写成漂亮 prompt”的工具，而是一条可追溯的生产链：

~~~text
brief / idea
-> story truth
-> shot truth
-> visual and audio bible
-> Prompt IR
-> image/reference prompt
-> clean-frame QA
-> video/audio prompt
-> model adapter
-> TabNow/TapNow graph
-> generation
-> result QA
-> one-variable retry
-> user lock
-> acceptance receipt
~~~

### 1.2 直接解决的问题

1. 现有视频 prompt 过于粗略，缺少每秒节拍、道具动作、环境动作、焦点、转场和声音轨。
2. 现有视频 prompt 使用 R05/R06 这类内部标签，用户直接粘贴到 Seedance 后模型无法可靠理解。
3. 现有提示词把“摄影机高级感”写成抽象词，没有起点、终点、路径、支撑方式、速度与动机。
4. 图像已经生成，但逐图 prompt、角色、继承关系、direct-input policy、QA 证据没有形成 durable truth。
5. 流程曾经跳过用户确认：图像生成后没有及时询问，模型选择前曾经编译多套模型 prompt。
6. 纯文本交付没有映射到 TapNow/TapNow Canvas 的输入节点、参考节点和输出节点。
7. 核心结构与具体模型事实没有分层，未来模型升级会导致全套文档重写。
8. 失败后缺少“只改一层”的故障树，容易整段重写并丢失已经正确的内容。
9. 构图被写成固定套路，缺少视觉重心、负空间、遮挡、层次、动线、运动空间和叙事目的。
10. 灯光、光学成像、空气介质与调色没有拆层，容易把“电影感”误写成无条件滤镜。
11. 用户提供客户文件、现成故事或参考图时，流程没有先读取并建立资产继承关系，容易重新生成出不一致的内容。
12. 图像或候选生成后缺少明确的 self-QA、lock/revise 询问和下一步状态，导致流程停住或把候选误当最终。

## 2. 目标与非目标

### 2.1 产品目标

| 目标 | 可量化目标 |
| --- | --- |
| 图像 prompt 可复用 | 每张正式图都有 asset_id、角色、完整 prompt、核心锁、负面约束、QA、hash 和下游用途；覆盖率 100% |
| 视频 prompt 可执行 | 视频 prompt 评分 ≥90/100；所有最终 Seedance prompt 的引用都编译为 @Image/@Video/@Audio |
| 时间与动作清晰 | 10 秒项目至少 8 个关键时间点；30 秒项目至少 12 个关键时间点；每个动态实体都有起始态与终态 |
| 运镜专业化 | 每个 shot 都有景别、角度、焦段感、支撑、起止目标、路径、速度/缓急、焦点与叙事动机；覆盖率 100% |
| 构图可解释 | 每个 shot 都有视觉重心、前中后景、负空间/运动空间、视线动线、遮挡与构图目的；覆盖率 100% |
| Look 可控而非套滤镜 | 每个 shot 明确 lighting、optics、atmosphere、grade 是否触发；每个已启用效果都有条件、强度、保留项和退出/连续性；覆盖率 100% |
| 声音完整 | 每个 shot 都有 dialogue、VO、ambience、SFX、foley、music/silence 字段和时间 cue；覆盖率 100% |
| 转场明确 | 所有 shot 边界都有 transition type、视觉桥、声音桥和连续性要求；覆盖率 100% |
| TabNow 可交付 | 输出节点图与上传顺序，内部资产 ID 全部能解析到外部引用槽；解析失败时 fail-closed |
| 可重试 | 每次 retry 只修改一个变量，并绑定 failure ID；100% 的 retry 有证据和 upstream owner |
| 版本可扩展 | Seedance 2.0、未来 2.5/30s 或其他模型只替换 adapter/capability card，不修改 Prompt IR |
| 用户体验 | 每个阶段最多一个确认点；不在用户未选择模型前编译多模型；不在生成后跳过用户反馈 |
| 素材复用 | 用户提供的故事、分镜、参考图、音频或客户文件先被读取、登记、继承和复用；可复用输入不被文字重述替代；覆盖率 100% |
| 状态闭环 | 每个生成阶段都有 ready_for_review、locked、generated、accepted 等明确状态和 next_action；不静默停止 |

### 2.2 非目标

- 本阶段不实现真正的 TabNow 登录、上传、付费、生成或发布。
- 本阶段不伪造 Seedance 2.5 的能力、时长、分辨率或输入上限。
- 本阶段不把所有电影术语硬塞进每条 prompt；只有与当前 shot 可观察结果相关的术语才进入最终文本。
- 本阶段不自动绕过图片/视频安全拦截，不为被拦截的人体情趣内衣画面寻找规避写法。
- 本阶段不替换用户已锁定的参考图，不覆盖既有最终文件。

## 3. 用户角色与成功条件

### 3.1 导演/创意用户

用户希望先看到创意、镜头、声音和参考图角色，再决定是否锁定；不希望系统直接编译一堆未选择的模型 prompt。

成功条件：

- 一次只给一个明确选择点。
- 能看到每个镜头的动作、运镜、声音和连续性。
- 能区分 planning board、style board、clean frame 和 direct video input。

### 3.2 Prompt 使用者

用户希望拿到一段可以直接粘贴到 Seedance 的文本，而不是还要自己把内部文件名翻译成 @Image。

成功条件：

- 最终文本不出现 R05、本地路径或内部 manifest 字段。
- 所有上传素材在 prompt 开头有清晰角色映射。
- 语言是直接的视觉指令，不是系统说明或元话语。

### 3.3 TabNow/TapNow 操作者

用户希望把参考图、文本、音频和模型设置按节点连接后再生成，并能知道每条线的用途。

成功条件：

- 有可导入/可手工复现的节点图。
- 每个 input node 有 role、asset hash、direct-input policy。
- 生成节点与 QA、retry、lock 节点可追溯。

### 3.4 QA/制片

用户希望知道问题出在哪一层，以及下一次只修改什么，而不是重新写一整段 prompt。

成功条件：

- 失败能归类到 reference、action、camera、look、audio、transition、output 或 rights。
- 有单变量重试规则。
- 真实生成、用户锁定、最终验收状态分别记录，互不替代。

## 4. 核心架构

### 4.1 分层

~~~text
L0 Source Truth
  story / script / shot list / visual bible / audio plan / reference pack

L0.5 Intake and State
  user/client assets / source precedence / asset manifest / lock state / stage receipt

L1 Prompt IR
  model-neutral structured production intent

L2 Validators
  role / lock order / timeline / camera / audio / transition / rights / QA

L3 Model Adapter
  Seedance 2.0 @-binding, duration, reference modes, audio route
  future Seedance 2.5 adapter, other providers, no alias inheritance

L4 External Handoff
  TabNow/TapNow node graph, upload order, pasteable prompt, settings map

L5 Execution and QA
  generated candidate / external import / failure record / retry / lock
~~~

### 4.2 单一真相原则

| 事实 | Source of truth |
| --- | --- |
| 产品/角色身份 | identity reference / visual bible |
| 场景空间与 FOV | scene geography + camera FOV reference |
| 镜头结构 | shot list / sequence plan |
| 灯光、色彩、材质 | visual bible / style-material reference |
| 声音意图 | audio plan |
| 模型能力 | exact capability card |
| 最终上传槽位 | model adapter + external handoff map |
| 用户或客户提供的现成资产 | original file/attachment + intake manifest |
| 构图重心与空间关系 | shot truth / composition card |
| 光学与调色意图 | visual bible + shot-level render look |
| 生成是否发生 | generation receipt / imported artifact |
| 用户是否锁定 | live user acceptance / lock receipt |

下游 prompt 只能继承，不能重新发明上游事实。

## 5. Prompt IR 最小数据契约

实现时应新增或扩展一个模型无关的 Prompt IR。字段名可调整，但语义不能丢失。

~~~yaml
prompt_ir:
  project_id: ""
  sequence_id: ""
  asset_id: ""
  operation: image_generate | image_edit | video_generate | video_edit | video_extend
  intended_use: advertising | film_previs | social_short | product_demo | reference_pack
  output:
    aspect_ratio: "9:16"
    target_duration_sec: null
    generation_unit_sec: null
    text_policy: no_text | exact_text | post_only
    visual_output_mode: prompt_only | assisted_generation | external_generation
  references:
    - asset_id: ""
      role: identity | scene_fov | style_material | storyboard_motion | clean_start | clean_end | motion | audio
      direct_input_policy: planning_only | allowed | conditional
      preserve: []
      do_not_copy_or_animate: []
      external_slot: ""
  global_locks:
    identity: []
    product_or_prop: []
    wardrobe: []
    scene: []
    palette_lighting: []
    lens_grammar: []
    audio_spine: []
  intake:
    source_precedence: []
    supplied_assets: []
    read_before_regenerate: true
    reuse_or_derive_policy: ""
  composition:
    visual_center: ""
    subject_hierarchy: ""
    foreground_midground_background: ""
    negative_space: ""
    movement_room: ""
    leading_lines_and_occlusion: ""
    balance_and_symmetry: ""
    perspective_depth: ""
    narrative_purpose: ""
  render_look:
    lighting:
      condition: ""
      source_direction_quality: ""
      contrast_and_shadow: ""
    optics:
      condition: ""
      lens_family: spherical | anamorphic | macro | telephoto | unspecified
      filtration: none | diffusion | nd | streak | other
      physical_behavior: ""
      intensity: none | subtle | moderate | strong
    atmosphere:
      condition: ""
      medium: none | haze | fog | smoke | dust | rain | other
      density_scale: ""
      light_path_visibility: ""
      movement: ""
    grade:
      condition: ""
      white_balance_anchor: ""
      contrast_gamma: ""
      black_level: ""
      highlight_rolloff: ""
      saturation_density: ""
      palette_separation: ""
      grain_halation: ""
    preserve: []
    exit_or_continuity: ""
  image_plan:
    asset_role: ""
    visual_decomposition: {}
    layout_spec: {}
    prompt_core: ""
    director_recreation_prompt: ""
    negative_prompt: ""
  video_plan:
    sequence_mode: single_sequence | hybrid | stepwise | batch
    shot_blocks: []
    transition_plan: []
    audio_plan: {}
  capability:
    capability_card_id: ""
    model_key: ""
    version: ""
    provider_surface: ""
    source_evidence: []
    resolution_status: resolved | stale | ambiguous | unsupported
  qa:
    score: null
    pass_threshold: 90
    failure_ids: []
    retry_rules: []
~~~

## 6. 功能需求

### FR-01：意图与材料选择门

在进入图像或视频 prompt 编译前，系统必须确认：

- 项目是广告、电影预演、短剧、社媒还是产品演示。
- 这一步要生成的是 identity board、scene/FOV、storyboard/motion map、style/material、clean frame、image prompt、video prompt 还是 TabNow handoff。
- 目标模型是否已选定。
- 用户是要 prompt-only、外部生成指令还是授权实际生成。

失败条件：用户未选模型时编译多个模型版本；用户未选素材类型时直接出图。

输入分流规则：

- 先识别用户是否已经提供故事、脚本、分镜、参考图、视频、音频或客户最终文件。
- 已提供的内容先读取、视觉检查、登记角色、保留项、hash 和下游用途。
- 如果现成资产已解决身份、比例、材质、空间或构图，就进入 reuse/edit/derive，不重新凭文字生成同一事实。
- 参考图按最小充分原则启用：材质/灯光图、分镜运动图和 clean frame 都是条件式资产，不是所有项目的固定必选项。
- 只有人物和场景输入时，Prompt IR 仍必须独立编译完整的构图、动作、运镜、四层 Look、声音和转场。
- 只有存在会改变结果的歧义才询问；能从文件或上下文读取的内容不重复询问。
- 生成完成后必须返回候选、self-QA、当前状态和 next_action；不允许无提示地停在“生成完了”。

### FR-02A：素材 Intake 与继承图

系统必须支持用户直接提供客户文件、现成故事、分镜、图片、视频、音频或已经认可的生成物。每个输入必须登记：

- source_kind、source_locator、source_hash、source_authorization。
- asset role、preserve、may_change、do_not_copy_or_animate。
- reuse_action：direct_reference、edit、derive、planning_only 或 unresolved。
- locked、qa_status、downstream_slots。

系统必须遵守 source precedence：用户锁定/交付资产高于用户参考资产，高于项目 truth，高于未锁定候选，高于模型想象。未完成 intake 时不得开始大批量重生成。

### FR-02B：构图编译器

每个图像资产和视频 shot 必须从以下字段中选择与当前叙事相关的构图语言：

- visual center、subject hierarchy、foreground/midground/background。
- negative space、movement room、leading lines、occlusion、parallax。
- balance、symmetry/asymmetry、perspective depth、horizon/vanishing。
- crop safety、eyeline/screen direction、narrative purpose。

系统不得把三分法、中心构图或对称构图当成默认答案。构图字段必须能解释它如何帮助 hook、reveal、material isolation、power/vulnerability、release 或 final hold。

### FR-02：图像 Prompt Compiler

每张图必须生成：

1. pre_generation_contract。
2. visual_decomposition。
3. layout_spec。
4. prompt_core，作为跨镜头继承锁。
5. director_recreation_prompt，作为当前图的完整生产 prompt。
6. negative_prompt，只写当前失败风险。
7. asset_output、direct_input_policy、downstream_video_use。
8. self-QA 与用户 lock 状态。

图像 prompt 不写音频生成指令；声音只进入 downstream metadata。
图像 prompt 必须同时登记 composition card 和 render look；如果没有特殊光学或后期效果，明确写 none by design，而不是留空。

### FR-03：视频 Prompt Compiler

每条视频 prompt 必须生成：

- external reference map：把内部 asset ID 翻译为模型可识别的 @Image/@Video/@Audio。
- global continuity locks。
- shot-by-shot timeline。
- 主体动作、道具动作、环境动作三层。
- 摄影机 shot card。
- composition card：视觉重心、层次、负空间、运动空间、遮挡和构图动机。
- render look card：lighting、optics、atmosphere、grade 四层及其触发条件。
- 过渡、VFX、状态变化。
- 声音 cue sheet。
- capability / rights / execution route。
- targeted avoid 与单变量 retry。

### FR-04：时间轴编译器

规则：

- 10 秒：至少 8 个有意义的时间节点，不能只分 3 段后留空。
- 15 秒：至少 10 个关键节点，复杂场面用 1–2 秒区间。
- 30 秒：至少 12 个关键节点，先分 4–6 个 sequence beat，再分 shot beat。
- 每个时间区间必须声明“发生了什么可见变化”。仅写情绪词不算完成。
- 除非明确是 hold，任何连续超过 4 秒没有状态变化的区间都必须触发审查。

### FR-05：专业摄影机语言编译器

每个 shot 至少输出：

~~~text
shot size
camera angle / height / axis
lens feel + lens reason
camera support / rig
start target
movement path
end target
speed / easing / motion texture
focus target / rack focus
movement motivation
~~~

高级运镜只有在叙事或空间关系需要时使用。系统不得为了“高级”自动添加 360° orbit、dolly zoom、crane、whip pan。

### FR-05A：专业构图与动态构图编译器

系统必须将构图写成可观察的空间关系，而不是静态构图标签。每个 shot 至少输出：

~~~text
visual center and hierarchy
foreground / midground / background
negative space and movement room
leading lines / occlusion / parallax
balance / symmetry / asymmetry
perspective depth and screen direction
crop safety
narrative purpose
~~~

当主体或镜头移动时，构图必须声明哪些关系保持不变、哪些关系随路径变化。构图可以从对称转为偏置、从遮挡到揭示、从拥挤到释放，但每次变化都必须绑定 beat。

### FR-05B：四层 Look 编译器

每个 shot 必须把 look 拆成四层，并逐层判断是否触发：

1. lighting：光源位置、方向、大小、硬软、色温、对比度和阴影。
2. optics：镜头家族、球面/变形宽银幕、扩散、ND、streak、焦点衰减、bokeh、flare、veiling glare、halation、呼吸感和畸变。
3. atmosphere：haze、fog、smoke、dust、rain、粒子、丁达尔/体积光、介质密度、光路可见度和运动。
4. grade：白平衡锚点、gamma/对比度、黑位、highlights roll-off、饱和度/密度、色相分离、颗粒和后期 halation。

每个启用层必须写：

~~~text
condition -> effect -> intensity -> preserve -> exit/continuity
~~~

物理滤镜、镜头特性和后期渲染效果必须分开命名。系统不得把“电影感”“拉丝滤镜”“高级光效”当作完成态。anamorphic、bloom、flare、bokeh、Tyndall、haze、bleach-bypass 等只有在画面条件和叙事目的成立时才进入最终 prompt。

### FR-06：主体 / 道具 / 环境动作编译器

每个动态实体必须采用：

~~~text
initial state
trigger
path / blocking
contact or interaction
physical consequence
pause / reaction
final state
continuity lock
~~~

科幻变形、物体拆解、能量效果、液体、烟雾、破碎、重组必须额外声明：

- 变形起点和终点。
- 变形分几步。
- 哪个部件先动、哪个部件后动。
- 质量、惯性、碰撞、光照和声音如何跟随。
- 是否允许模型创造新部件。

### FR-07：声音设计编译器

每个 sequence / shot 必须分开写：

- dialogue。
- voiceover。
- ambience。
- sound effects。
- foley。
- music / rhythm。
- silence。
- cue time。
- sound perspective：近距离、远景、屏外、左右移动或中心定位。
- generation route：native、reference audio、postproduction、none、unresolved。

### FR-08：转场与 VFX 编译器

每个 shot 边界必须声明：

~~~text
transition_in
transition_out
visual bridge
audio bridge / prelap / tail
continuity state
model risk
~~~

转场词必须说明桥接对象，例如：

- specular match cut：用同一条缎面高光从全景切到材质特写。
- rack-focus bridge：焦点从前景扣件拉到镜中主体，完成空间转场。
- motivated whip pan：由主体/镜面反光触发的快速横摇，下一场景以同方向运动接住。
- light wipe：一条受控酒红光带遮过镜头，遮挡时完成场景变化。
- parallax reveal：前景遮挡物移动后露出新空间，但主体身份不变。

### FR-09：Seedance adapter

Seedance adapter 必须独立维护：

- capability_card_id。
- 版本、provider surface、访问方式、执行验证状态。
- @Image/@Video/@Audio 编译规则。
- 引用槽位顺序和角色说明。
- 当前时长和输入上限。
- 原生音频与后期音频 route。
- 2.0 与未来版本的差异。

核心 Prompt IR 不允许出现 Seedance 2.0 特有的硬编码字段。

### FR-10：TabNow/TapNow Handoff

系统输出一份节点图说明：

~~~yaml
nodes:
  - id: brief_01
    type: text
    role: source_truth
  - id: image_01
    type: image
    role: clean_start
    asset_id: ""
    hash: ""
  - id: prompt_video_01
    type: text
    role: seedance_prompt
  - id: audio_01
    type: audio
    role: rhythm_reference
  - id: model_01
    type: model
    capability_card_id: ""
  - id: qa_01
    type: qa
edges:
  - from: brief_01
    to: prompt_video_01
    relation: story_context
  - from: image_01
    to: prompt_video_01
    relation: direct_reference
  - from: audio_01
    to: prompt_video_01
    relation: audio_reference
  - from: prompt_video_01
    to: model_01
    relation: generation_instruction
  - from: model_01
    to: qa_01
    relation: generated_candidate
~~~

节点图必须在执行前通过：资产存在、hash 一致、角色唯一、引用槽位可解析、用户授权明确。

### FR-11：QA 与量化评分

每条 image/video prompt 都必须自动输出分数、缺口、阻断原因和下一步。

分数不是审美真理，而是门禁工具。任何关键字段缺失都可以直接阻断，即使总分高。构图和四层 look 属于必检层；未启用的光学、空气介质或调色效果必须明确标记 none by design。

### FR-12：问题处置与单变量重试

每次失败必须记录：

~~~text
failure_id
observed_output
suspected_layer
preserve_set
one_change
retry_prompt / retry artifact
expected_pass_signal
actual_result
~~~

Look 相关失败至少支持：

- F-LOOK-01：画面平、调色没有叙事作用。
- F-OPT-01：泛化滤镜词，没有可观察光学行为。
- F-OPT-02：flare/bloom 洗白主体或吞掉材质细节。
- F-ATM-01：丁达尔/体积光缺少方向光源、介质和密度条件。
- F-OPT-03：焦点、景深、bokeh 与光源位置不匹配。
- F-GRADE-01：调色破坏镜头连续性、产品材质或可读性。

构图相关失败至少支持：

- F-COMP-01：主体没有视觉重心。
- F-COMP-02：机械套用三分法、中心构图或对称构图。
- F-COMP-03：运动后主体离开安全区或没有 movement room。

### FR-13：未来 30 秒能力兼容

核心系统必须支持：

- story duration 与 generation unit duration 分离。
- 10/15 秒项目和 30 秒项目共用 Prompt IR。
- 30 秒只由 future capability card 授权，不在当前 2.0 card 上冒充。
- sequence boundary 有 picture、motion、audio handoff。
- 长镜头支持 single_sequence，复杂广告默认 hybrid。

## 7. 质量指标与门槛

### 7.1 Video Prompt Score / 100

| 维度 | 权重 | 通过标准 |
| --- | ---: | --- |
| reference binding | 12 | 所有输入都有平台槽位、角色和 anti-misread |
| timeline | 12 | 关键时间点覆盖完整，无未解释状态跳跃 |
| camera/composition | 16 | shot 有起止目标、路径、支撑、焦点、动机和构图关系 |
| subject/object/environment | 13 | 三层动作和连续性可观察 |
| look stack | 12 | lighting、optics、atmosphere、grade 按条件启用，强度和保留项明确 |
| audio | 10 | 7 类声音字段、cue、route 完整 |
| transition/VFX | 8 | 边界有视觉桥和声音桥 |
| continuity/negative | 8 | 关键身份、材料、物理和输出禁区完整 |
| capability/output | 4 | exact card、时长、画幅、引用模式可验证 |
| QA/retry | 5 | 有可判定验收和单变量重试 |
| **合计** | **100** | **≥90 generation-ready；<80 不得外部交付** |

### 7.2 Image Prompt Score / 100

| 维度 | 权重 | 通过标准 |
| --- | ---: | --- |
| pre-generation contract | 13 | 角色、标题层级、继承、direct-input policy 完整 |
| visual decomposition | 17 | 主体、动作/姿态、细节、环境、灯光、构图、材质、用途齐全 |
| layout/composition | 18 | 版式、视觉重心、层次、负空间、运动空间、可读区、下游用途明确 |
| camera/look/material | 17 | 镜头感、四层 look、材质行为和颜色锁具体 |
| reference/consistency | 15 | 每个参考图角色、保留项、不可复制项完整 |
| text policy | 10 | exact text 或 no-text 边界明确 |
| negative/QA | 10 | 失败特定、可观察、可重试 |
| **合计** | **100** | **≥90 prompt-ready；<80 返回图像编译阶段** |

### 7.3 Workflow Score / 100

| 维度 | 权重 |
| --- | ---: |
| source truth / lock order | 12 |
| asset intake / reuse | 13 |
| material/model selection gate | 12 |
| user confirmation discipline | 13 |
| capability / rights / execution truth | 12 |
| artifact / hash / reference traceability | 13 |
| self-QA before user lock | 10 |
| failure / retry evidence | 10 |
| live acceptance / receipt | 5 |

门槛：

- 90–100：进入 generation-ready / review-ready。
- 80–89：内部 draft，不能声称完成。
- 60–79：补齐最小缺失层。
- <60：回到流程或 source truth，不继续堆 prompt。

## 8. 执行路线

### P0：冻结当前真相与基线

产物：

- 当前 6 张参考图资产清单、hash、角色、锁定状态。
- 当前 Seedance prompt v0 归档。
- 当前分镜、脚本、参考图、用户决定和媒体状态索引。
- 用户/客户已提供素材的 intake manifest、来源优先级、hash 和复用/派生关系。
- 研究报告与基线评分。

验收：不覆盖现有文件；所有分数标注为审计分，不冒充生成 benchmark。

### P1：定义 Prompt IR 与评分器

产物：

- Prompt IR schema。
- image/video prompt score rubric。
- reference role enum。
- audio cue schema。
- camera grammar schema。
- composition schema。
- render-look schema：lighting / optics / atmosphere / grade / condition / intensity / preserve / exit。
- transition/VFX schema。

验收：10 秒产品广告和 30 秒长镜头 fixture 都能通过 schema 解析。

### P2：重写图像编译链

顺序：

~~~text
product / identity truth
-> scene/FOV
-> storyboard/motion map
-> style/material
-> clean start/end frame
-> manifest + prompt file + QA
~~~

验收：当前 6 张图各自有可复用 prompt、role、用途、direct-input policy、下游槽位和 QA；图像链能先读取用户/客户现成素材，并在可复用时进入 edit/derive，而不是脱离原图重建。

### P3：重写视频编译链

顺序：

~~~text
locked image assets
-> @ reference map
-> global continuity
-> subject/object/environment action
-> camera shot cards
-> time beat sheet
-> transition/VFX
-> audio cue sheet
-> Seedance prompt
~~~

验收：当前 10 秒广告 prompt 得分 ≥90，且可直接粘贴；内部 ID 不出现在最终文本；每个镜头的构图和四层 look 都有条件式字段，未使用的效果明确为 none by design。

### P4：TabNow/TapNow handoff

产物：节点图、连接关系、上传顺序、执行前检查、输出回收字段。

验收：在没有实际调用外部平台时，也能由另一位操作者按文档复现节点关系；不能声称已执行。

### P5：生成 QA 与故障回归

使用至少 6 类 fixture：

1. 产品广告：静态产品 + 材质特写。
2. 人物情绪：表情和动作递进。
3. 道具交互：物体接触、触发、状态变化。
4. 科幻变形：分步变形、光效、物理后果。
5. 写实环境：雨、雾、镜面、背景运动。
6. 30 秒 sequence：多段场景、连续性和音频 spine。

验收：每个 fixture 都有正向样例、失败样例、诊断层和单变量 retry。

### P6：真实外部生成与用户验收

前置条件：

- exact model surface 已确认。
- 用户明确授权外部生成/上传。
- 参考图 rights 和 lock 通过。
- TabNow 节点图、prompt、audio route、upload map 一致。

生成后：先做系统 self-QA，再把真实候选交给用户确认；明确记录生成了什么、哪一版、哪些问题、用户是否锁定。不能在生成结果出现后静默结束。

### P7：版本升级与 30 秒适配

只有拿到官方或当前执行面证据后，才创建新的 capability card。旧卡不被覆盖，2.5 不能把 2.0 的限制直接改写。

## 9. 交付物清单

本方案对应的实现交付至少包含：

~~~text
docs/film-preproduction/research/prompt-system-research-YYYY-MM-DD.md
docs/film-preproduction/prompt-system-upgrade-prd-v1.md
docs/film-preproduction/prompt-authoring-standard-v1.md
docs/film-preproduction/prompt-qa-and-incident-runbook-v1.md
docs/film-preproduction/asset-intake-and-state-standard-v1.md
schemas/prompt-ir.yaml
schemas/audio-cue.yaml
schemas/camera-move.yaml
schemas/transition-plan.yaml
schemas/tabnow-handoff.yaml
examples/<project>/image-prompt-manifest.yaml
examples/<project>/video-prompt-manifest.yaml
examples/<project>/prompts/image_*.txt
examples/<project>/prompts/video_seedance.txt
examples/<project>/qa/prompt-score.yaml
~~~

## 10. 完成定义

本 PRD 对应的升级不能以“文档写完”作为完成。必须同时满足：

- 规范文档已进入项目 README 的可发现路径。
- schema 可解析，测试 fixture 通过。
- 当前 6 张图被重新登记并保留原始文件，不覆盖用户锁定资产。
- 图像 prompt completeness ≥90。
- 视频 prompt completeness ≥90。
- 构图字段和四层 look 字段覆盖率 100%；每个启用的 optical/atmosphere/grade 效果都有触发条件和退出/连续性。
- Seedance @ 角色映射 100% 可解析。
- 时间轴、摄影机、声音、转场、对象动作 100% 有对应字段。
- TabNow handoff 未授权时保持 instructions_only。
- 实际生成如果发生，必须有 output、hash、QA、用户锁定和 live acceptance 证据。
- 在 live acceptance receipt 生成前，目标不得标记完成。
- 用户提供的现成素材已经完成读取、角色登记、继承或明确标记为不可用；不得用重新想象替代未完成的 intake。
- 每次生成后都有 self-QA、状态和 next_action；没有用户 lock 时不得把候选写成最终。

## 11. 方案结论

后续不是把现有 prompt 继续拉长，而是建立可编译、可评分、可回归的 Prompt Production System：

~~~text
规范化中间层 > 模型专用模板
资产图谱 > 文件名说明
可观察时间状态 > 抽象情绪词
有动机的镜头路径 > 高级运镜词堆叠
分层声音 cue > “有氛围音”
单变量 retry > 全段重写
版本 adapter > 未来模型硬编码
~~~
