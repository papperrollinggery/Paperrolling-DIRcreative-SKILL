# DIRcreative Prompt Authoring Standard v1.0

状态：规范草案，供 PRD 实现与后续 skill 编译使用

适用：广告、电影预演、产品片、短剧、社媒视频、参考图组、clean frame、图像 prompt、视频 prompt。

## 1. 总规则

### 1.1 Prompt 不是散文，而是可编译的制作指令

正式 prompt 必须能回答：

1. 这是什么资产，给谁使用？
2. 输入参考图/视频/音频各自承担什么角色？
3. 画面中谁/什么是主体？
4. 主体、道具、环境分别怎么动？
5. 摄影机从哪里开始，沿什么路径，在哪里结束？
6. 何时发生哪个变化？
7. 画面、光线、材质、颜色和比例锁什么？
8. 声音由哪些层组成，何时进入/退出？
9. 前后镜头通过什么视觉/声音桥连接？
10. 构图的视觉重心、层次、负空间和运动空间是什么，为什么这样安排？
11. lighting、optics、atmosphere、grade 哪些被触发，哪些明确不使用？
12. 生成后以什么可观察标准判定通过？

### 1.2 不能依赖的表达

以下词只能作为辅助，不能单独作为完成态：

- cinematic
- premium
- beautiful
- dynamic
- smooth camera
- slow push
- camera follows
- emotional
- high detail
- realistic texture
- advanced VFX

必须把它们翻译成可观察的物理事实、镜头路径、材料行为、时间状态或验收标准。

### 1.3 正式输出的顺序

统一使用以下顺序，再由具体模型 adapter 压缩或改写：

~~~text
A. Contract / asset role
B. Reference map
C. Creative purpose
D. Global locks
E. Composition / visual hierarchy
F. Subject / object / environment
G. Camera / lens / focus
H. Lighting / optics / atmosphere / grade
I. Time / beat / transition
J. Audio
K. Model-facing constraints / targeted avoid
~~~

`QA / retry`、score、failure id、source path/hash、rights receipt 和能力证据属于内部 IR/manifest。它们在 prompt 编译完成后运行，不进入最终粘贴给模型的文本。只有可观察的 preserve、forbidden change 和当前失败风险可以被 adapter 编译成模型约束。

## 2. 共用资产契约

### 2.1 每张图的可复用资产契约

~~~yaml
asset_contract:
  asset_id: ""
  asset_role: identity | scene_fov | storyboard_motion | style_material | clean_start | clean_end | product_detail
  dominant_title: ""
  project_metadata: ""
  role_purity: ""
  source_artifacts: []
  source_kind: user_upload | client_file | conversation_media | generated_candidate | project_file
  source_locator: ""
  source_hash: ""
  source_authorization: user_provided | project_owned | unknown
  inherits_from: []
  preserve: []
  may_change: []
  do_not_copy_or_animate: []
  reuse_action: direct_reference | edit | derive | planning_only | unresolved
  locked: false
  text_policy: no_text | exact_text | planning_labels_allowed
  direct_video_input_policy: planning_only | allowed | conditional
  downstream_use: []
  qa_pass_signal: []
~~~

板式参考图必须把角色标题放在最大层级；项目名只能是较小 metadata。clean frame 则必须无可见标题、标签、箭头、边框和分镜网格。

### 2.2 每个视频引用的外部绑定

Seedance 的最终文本必须使用平台引用角色：

~~~text
@Image 1 = ...
@Image 2 = ...
@Video1 = ...
@Audio1 = ...
~~~

内部 asset_id 只存在于 manifest 和节点图。最终粘贴文本不得要求模型理解本地文件名、工作区路径或项目内部编号。

### 2.3 最小充分参考原则

参考图不是提示词的替代品，也不是每个控制维度都要单独生成一张图。编译器必须先判断当前已有输入是否已经解决身份、场景、构图和材质事实；能由文字和 Prompt IR 稳定表达的内容直接写入 prompt。

只有以下情况才新增视觉参考：身份或几何不稳定；复杂空间需要固定 FOV/轴线；材质或灯光是核心卖点且要跨镜头复用；多人/多道具关系需要客户先看；选定模型需要 clean start/end frame；或生成 QA 已经观察到对应层漂移。

只有人物和场景输入时，最终视频 prompt 仍必须完整写出 composition、subject/object/environment、camera、lighting、optics、atmosphere、grade、audio、transition 和 guardrails。缺少一张材质图不构成提示词不完整。

多人物和多资产使用实体化引用：每个主体有唯一名称、asset role、screen position、保留项和动作所有权；不要用“他/她/它们/另一个”让模型自行消歧。群像构图与个人 identity 是两个不同职责，不能用一张拼贴图替代。

## 3. 图像 Prompt Standard

### 3.1 图像 prompt 目标

图像 prompt 用于生成一个可审计、可复用、可继续被视频模型消费的视觉资产。它不是把所有后续镜头都塞进一张图，也不是一张没有角色边界的 mood collage。

### 3.2 图像 prompt 五层

#### Layer 1：用途与类型

必须声明：

~~~text
Use case: ads-marketing / product-mockup / stylized-concept / ...
Asset type: product identity reference / scene FOV / storyboard / clean frame / ...
Generation intent: lock identity / lock geography / lock material / provide direct I2V frame
~~~

#### Layer 2：版式与空间层次

必须声明：

- 画幅和目标尺寸，前提是来自当前图像能力卡。
- 视觉重心与主体层级。
- foreground / midground / background，以及前景遮挡是否承担揭示作用。
- 负空间、文字安全区和主体运动空间。
- leading lines、视线动线、镜面/玻璃反射和 parallax。
- balance、symmetry/asymmetry、透视深度、地平线/消失点和裁切安全。
- 构图选择服务的叙事目的：hook、reveal、material isolation、power/vulnerability、release 或 final hold。
- 板式是非对称艺术指导、技术图、单帧摄影还是清洁画面。
- 哪些内容是可见画面，哪些内容只是制作标签。

不要把三分法、中心构图或对称构图当成默认答案。构图方法必须能说明它如何改变观众的注意力、空间关系或动作可读性。

#### Layer 3：主体与材质真相

必须写：

- 形状、比例、姿态或 blocking。
- 结构、接缝、连接、边缘、厚度和尺度。
- 材质在光线下如何反射、吸收、折射、起皱、磨损或变形。
- 产品/角色需要跨图保持的锁定项。
- 禁止自动添加的部件和类别漂移。

#### Layer 4：摄影、灯光、光学、空气介质与调色

必须拆成四层写；未触发的层明确写 none by design：

1. lighting：光源位置、方向、大小、硬软、色温关系、阴影边缘和对比度。
2. optics：shot size、angle、lens feel、camera height、perspective、球面或变形宽银幕、扩散、ND、streak、focus falloff、focus breathing、bokeh、flare、veiling glare、halation、畸变和色差。
3. atmosphere：haze、fog、smoke、dust、rain、粒子、丁达尔/体积光、介质密度、尺度、光路可见度和运动。
4. grade：白平衡/中性锚点、gamma/contrast、black level、highlight roll-off、saturation/density、palette anchors、色相分离、grain 和 post halation。

每个启用层都必须写 condition、effect、intensity、preserve、exit/continuity。物理滤镜、镜头行为和后期效果不能统称为滤镜。

例如，只有当画外 practical 的高光以斜角越过镜头前组时，才使用局部 veiling flare；只在高光边缘产生轻微 bloom/halation，保留黑色缎面纹理和主体轮廓。没有方向性光源、介质和可见光路时，不写 generic god rays 或丁达尔光。

如果是 clean frame，说明它只承载一个镜头状态，不承载整张分镜板。

#### Layer 5：限制与 QA

必须分开写：

- exact text / no text。
- no logo / no watermark / no fake UI。
- 角色身份、产品结构、场景空间和材料 continuity locks。
- 目标下游用途。
- 可观察的 pass/fail 条件。
- 只针对当前失败模式的 avoid 列表。

### 3.3 图像 prompt 标准模板

~~~text
Pre-generation contract:
Asset role: <dominant role label>
Project metadata: <small metadata only>
Role purity: <one production job>
Inherited sources: <locked source artifacts>
Direct video input policy: <planning-only / allowed / conditional>
Do not make <project title> the largest title.
Do not show or animate <labels/panels/arrows if planning board>.

Use case: <taxonomy>
Asset type: <asset type>
Primary purpose: <what this image must prove>

Canvas and layout:
- Aspect ratio / target size: <capability-backed>
- Visual center and hierarchy: <what the eye reads first, second, third>
- Composition grammar: <symmetry / asymmetry / centered / rule-of-thirds / occlusion / parallax / other, with reason>
- Foreground / midground / background: <spatial layers>
- Negative space and movement room: <where and why>
- Leading lines / occlusion / reflection: <how attention is guided>
- Perspective depth / screen direction / crop safety: <spatial continuity>
- Main readable zone: <subject / product / safe text area>
- Art direction: <intentional, asymmetrical, non-generic if applicable>
- Panel hierarchy: <if board>

Subject:
- Primary subject: <one hero subject>
- Identity/geometry locks: <exact locks>
- Pose/blocking: <start state and visible state>
- Prop/support relation: <what is hardware and what is set dressing>

Environment:
- Location / backdrop: <concrete facts>
- Spatial anchors: <mirror, floor, wall, practical, horizon>
- Environmental motion implied in still: <only if visually needed>

Camera:
- Shot size / angle / lens feel: <production-specific>
- Focus hierarchy: <what is sharp>
- Camera height / perspective: <specific relation>
- Movement implication: <only if this is a storyboard or motion reference>

Render look:
- Lighting condition / effect / intensity: <or none by design>
- Optical capture condition / lens behavior / filtration: <or none by design>
- Atmosphere condition / medium / density / light path: <or none by design>
- Grade condition / white balance / contrast / black level / highlights / saturation / palette: <or none by design>
- Look preserve / exit / continuity: <what must remain readable>
- Material behavior: <surface truth>

Text policy:
- Exact text: "<verbatim text>" / no visible text
- Typography / placement: <only if exact text is required>

Continuity:
- Preserve: <identity, geometry, color, material, proportion>
- May change: <allowed variables>
- Avoid: <targeted failure modes>

Downstream use:
- <video slot / planning-only / clean first frame>

Falsifiable QA:
- <visible pass conditions>
~~~

### 3.4 图像参考图类型规范

| 类型 | 必须锁定 | 不得承担 |
| --- | --- | --- |
| Product / identity | silhouette、比例、材质、结构、尺度 | 不承担完整广告场景、剧情、分镜文字 |
| Scene + FOV | 空间关系、镜头视场、前中后景、光线方向 | 不承担角色身份或产品细节重设计 |
| Storyboard + motion map | shot cell、时间、景别、运镜、blocking、声音、转场、风险 | 默认不能作为 literal first frame |
| Style / material | palette、light、surface、texture、grade | 不承担动作与故事 |
| Clean first/end frame | 单一时间状态、无字、无板式元素、视频输入安全 | 不承担多个镜头或制作说明 |
| Product detail / macro | 一个具体功能或材质证据 | 不替代 identity board |

### 3.5 图像编辑与重试

编辑必须写不重叠的 preserve / change：

~~~text
Preserve:
- product silhouette
- garment construction
- material and color
- camera framing
- mirror geometry

Change only:
- <one selected variable>

Forbidden change:
- <identity / proportion / text / background / lighting if not selected>
~~~

重试一次只改一个变量：

- identity/product。
- primary pose/action。
- camera/framing。
- light/material/color。
- reference binding。
- output control。

## 4. 视频 Prompt Standard

### 4.1 视频 prompt 的模型适配原则

模型无关层负责意图、时间和制作逻辑；模型 adapter 负责具体语法和能力事实。

Seedance 2.0 的最终文本必须优先采用：

- @Image N：产品、场景、风格、clean frame、分镜指导。
- @VideoN：已授权的视频运动、镜头、动作、效果或节奏参考。
- @AudioN：已授权的音乐、节奏、声音特征或音频参考。
- 文字：描述动作、镜头、时序、连续性、声音和边界。

不要在最终粘贴 prompt 里写：

- R05、image_05、本地路径。
- “请读取我的 manifest”。
- “这是上面那张图”。
- “下面的表格是参考但不要显示”，却没有给出 @ 角色与反误读范围。

### 4.2 视频 prompt 的全局结构

~~~text
REFERENCE MAP
@Image 1 = <role + preserve + direct-use policy>
@Image 2 = <role + preserve + secondary visual target>
@Image 3 = <planning-only role + anti-misread>
@Audio1 = <audio role + rhythm / sound characteristics>

CREATIVE PURPOSE
<one sentence: what the audience should understand or feel>

GLOBAL CONTINUITY LOCKS
<identity / product / wardrobe / location / light / material / axis / audio spine>

SUBJECT / OBJECT / ENVIRONMENT
<three separate action layers>

CINEMATOGRAPHY
<shot language and camera grammar>

TIMELINE
<time-coded beat sheet>

TRANSITIONS AND VFX
<boundary-by-boundary bridges>

AUDIO
<dialogue / VO / ambience / SFX / foley / music / silence / route>

GUARDRAILS
<positive constraints and targeted avoid>

~~~

如果平台不需要章节标题，adapter 可以将这些内容编译为自然段；内部 manifest 仍保留完整字段。

### 4.3 Subject / object / environment 三层

#### 主体层

人物：

- identity、服装、身体起始姿态。
- blocking：起始位置、路径、终点、屏幕方向、轴线。
- 表演：眼神、呼吸、手势、面部微表情、情绪转折、停顿。
- 动作必须写可见行为，不只写“自信”“暧昧”“紧张”。

产品/物体：

- 起始状态、接触面、受力点、运动方向、旋转轴、停止方式。
- 产品结构在运动中不能凭空增减。
- 材质对动作的反应：缎面折叠、金属反光、液体惯性、玻璃折射、布料滞后。

#### 道具层

每个道具必须写：

~~~text
Object: <name>
Initial state: <where / orientation / active state>
Trigger: <what causes movement>
Motion path: <from -> through -> to>
Interaction: <touch / collision / magnet / hinge / gravity>
Physical consequence: <shadow / reflection / debris / light / sound>
End state: <stable final state>
Continuity: <must remain unchanged>
~~~

#### 环境层

环境不是静态背景。要声明：

- 空气、雾、烟、雨、尘、光束、反射、阴影如何动。
- 背景运动和主体运动的速度关系。
- 镜面、玻璃、液体、布料、粒子、火焰、霓虹等如何响应。
- 哪些环境元素是可动的，哪些必须锁定。

### 4.4 摄影机语言规范

每个 shot 只有一个主镜头动作。复合运镜拆成顺序步骤。

| 运镜 | 必须写清 | 典型动机 |
| --- | --- | --- |
| dolly-in / creep-in | 起始距离、终点距离、速度、保持主体尺寸或改变主体尺寸 | 逼近、发现、心理压力 |
| dolly-out | 后退目标、保留主体关系、负空间如何出现 | 释放空间、结尾、揭示环境 |
| truck / lateral track | 横向路径、前景遮挡、主体是否锁定 | 展示材质、制造 parallax |
| arc / orbit | 圆弧角度、旋转中心、主体/镜面关系、是否保持视线 | 产品轮廓、空间揭示 |
| pedestal / crane | 起止高度、俯仰关系、地面/顶部目标 | 权力、空间规模、揭示 |
| rack focus | 焦点 A、焦点 B、发生时间、景深 | 叙事注意力转移 |
| whip pan | 触发动作、方向、运动模糊、接收画面方向 | 快速转场、节奏跳转 |
| dolly zoom | dolly 方向、zoom 方向、主体尺寸锁、背景变化目标 | 眩晕或心理异化；默认禁用 |
| locked-off | 机位固定、主体/环境唯一运动、循环或稳定结尾 | 产品证明、精确变形、文字安全区 |

每个 camera 字段使用：

~~~text
Shot size:
Angle / height / axis:
Lens feel + reason:
Support:
Start target:
Path:
End target:
Speed / easing:
Focus:
Why this movement:
~~~

### 4.4A 构图与动态空间规范

构图不是固定美学模板，而是观众注意力和空间关系的编排。每个 shot 必须从下列字段中选择与当前 beat 相关的内容：

~~~text
Visual center:
Subject hierarchy:
Foreground / midground / background:
Negative space:
Movement room:
Leading lines / occlusion / parallax:
Balance / symmetry / asymmetry:
Perspective depth / horizon / vanishing:
Screen direction / eyeline:
Crop safety:
Composition purpose:
~~~

可用的构图目的包括 hero emphasis、reveal through occlusion、negative-space release、material isolation、power/vulnerability、symmetry/ritual、parallax depth 和 directional movement room。不要为了“专业”强行套用三分法、中心构图或对称构图。

当相机或主体移动时，必须写出构图状态如何变化：例如从前景遮挡到主体揭示、从紧凑裁切到负空间释放、从对称稳定到偏置失衡。每次变化都要绑定时间 beat 和叙事信息。

### 4.4B 四层 Look 与条件式效果规范

视频和图像都使用同一套 look card：

~~~yaml
render_look:
  lighting:
    condition: ""
    effect: ""
    intensity: none | subtle | moderate | strong
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
    intensity: none | subtle | moderate | strong
  grade:
    condition: ""
    white_balance_anchor: ""
    contrast_gamma: ""
    black_level: ""
    highlight_rolloff: ""
    saturation_density: ""
    palette_separation: ""
    grain_halation: ""
    intensity: none | subtle | moderate | strong
  preserve: []
  exit_or_continuity: ""
~~~

写法必须遵循 condition -> effect -> intensity -> preserve -> exit/continuity：

- 变形宽银幕只在横向 flare、椭圆 bokeh、边缘畸变或宽银幕视觉语言对当前故事有帮助时启用；画幅仍按项目要求保持 9:16，并写清垂直裁切和主体安全区。
- diffusion 只描述物理成像的柔化、对比度降低或高光扩散；bloom、halation、grain、density、bleach-bypass 等后期效果单独命名。
- Tyndall/volumetric rays 只有在有方向性光源、空气介质和可见光路时启用，并写密度、光束衰减和运动；没有条件就写 none by design。
- bokeh 必须写焦点目标、背景点光源、形状/尺寸和焦外层次，不写 generic cinematic bokeh。
- flare/refraction 必须写入射光源、镜头角度、streak/ghost/veiling 行为、出现和消退时间，并保留主体可读性。
- 调色先写白平衡锚点，再写 gamma/对比度、黑位、highlights roll-off、饱和度/密度和色相分离；不要无理由使用 teal and orange。
- bleach-bypass、重颗粒、强 halation 或强 bloom 必须写故事条件和材料保护，不能作为全片默认风格。

### 4.5 时间轴规范

#### 10 秒广告

不要只写 0–3 / 3–6 / 6–10 三块空泛概念，而写成以下密度：

~~~text
00.00–00.80  initial state / hook
00.80–01.60  first visible motion
01.60–02.50  reveal or pause
02.50–03.00  transition bridge
03.00–04.00  new shot settles
04.00–05.00  object/material action
05.00–05.50  sound or focus accent
05.50–06.50  payoff setup
06.50–07.50  primary reveal / turn
07.50–08.80  final composition / negative space
08.80–10.00  hold / end-card-safe state
~~~

每一格只写本区间发生的状态增量。主体、表情、道具、环境、摄影机、焦点、Look、声音和连续性中没有变化的字段留在内部 state ledger，不在终端 prompt 逐格重复。每格至少有一个可观察变化和一个明确结束状态。

#### 15 秒广告/短片

15 秒先按叙事功能分为 4–6 个状态变化，再由 exact-card adapter 决定一段生成或逐镜头生成：

~~~text
00.00–02.00  hook / initial relationship
02.00–05.00  setup / ownership / spatial lock
05.00–09.00  primary interaction
09.00–12.00 consequence / reveal
12.00–15.00 payoff / dialogue or final hold
~~~

这不是固定镜头数或模型能力声明。复杂多人动作优先拆镜头；单一连续表演可以合并区间。

#### 30 秒 sequence

30 秒不是把 10 秒 prompt 乘三。先分 sequence function：

~~~text
00–05  hook / world rule
05–11  subject and object setup
11–17  first action / interaction
17–22  escalation / transformation / reveal
22–27  consequence / payoff
27–30  final hold / CTA-safe composition
~~~

然后每个 sequence 再拆 shot。每个边界都要有完全相等的上一段 `outgoing_state` / 下一段 `incoming_state`，以及完全相等的 handoff key；同时记录构图状态、look continuity 和音频 handoff。超过单次生成上限时，最终交付必须逐 unit 编译为本地 0 秒时间轴，禁止把完整 30 秒 assembly plan 当成单次可执行文本。

### 4.6 转场规范

每个转场必须回答“为什么在这里转”和“什么东西把两画面连起来”：

~~~text
Transition:
Visual bridge:
Audio bridge:
Incoming state:
Outgoing state:
Continuity lock:
Model risk:
~~~

可用手法：match cut、shape match、specular match、rack-focus bridge、motivated whip pan、light wipe、parallax reveal、foreground occlusion、sound prelap、sound tail。

不得用“自然转场”“高级转场”“无缝切换”替代具体桥接逻辑。

### 4.7 音频规范

内部 Audio Plan 必须能够表达以下字段：

~~~text
Dialogue: none / speaker / exact line / timing / emotion
Voiceover: none / voice / exact line / timing
Ambience: location bed, distance, perspective
SFX: event-bound effect and cue time
Foley: material / body / prop contact sound
Music: genre / instrumentation / tempo feel / entry / exit
Silence: intentional silent window
Mix perspective: close / distant / off-screen / left-right / center
Generation route: native / audio reference / postproduction / none
~~~

最终模型 prompt 只保留当前 exact-card 路线能够生成且确实需要的可听事件。`postproduction` cue、speaker/rights receipt、未启用的 `none` 字段和后期混音计划留在内部 handoff，不为满足模板而写入模型 prompt。

产品广告示例：

~~~text
00.00–02.50：低音量暗室 room tone，镜面空间的轻微空气噪声。
02.10：缎面擦过展示模特的细软摩擦声，贴近画面但不夸张。
02.50：specular match cut 处加入短促、无旋律的高频亮点。
03.00–05.50：近距离织物纹理声，金属扣件在焦点落下时发出一次细小 tick。
05.50–08.80：转台/结构旋转的低机械声，随角度变化轻微左右移动。
08.80–10.00：声音逐渐留白，保留一秒尾响，片尾文案由后期叠加。
无对白、无旁白、无可识别版权旋律。
~~~

### 4.8 VFX / 物理效果规范

特效必须写“触发—过程—结果”：

~~~text
Effect: <effect name>
Trigger: <what causes it>
Start state: <initial intensity / location>
Process: <order, direction, speed>
Interaction: <light, shadow, reflection, collision, material response>
End state: <stable result>
Audio cue: <sound attached to event>
Forbidden drift: <new objects / uncontrolled color / unrelated effect>
~~~

科幻变形至少写：

1. 原始部件保持。
2. 第一层机械/有机运动。
3. 第二层结构展开/重组。
4. 光效/粒子只围绕真实受力和空间关系出现。
5. 最终形态停稳并可被看清。
6. 相机是否跟随、停留或切换焦点。

## 5. 工作流与确认纪律

### 5.1 收到现成素材先读取

如果用户提供客户文件、故事、分镜、参考图、视频、音频或已经认可的生成物，先执行 intake：

~~~text
识别来源 -> 读取元数据和画面 -> 判断 asset role -> 登记 preserve/change/hash
-> 判断 direct_reference / edit / derive / planning_only
-> 建立下游槽位 -> 再决定是否需要生成
~~~

已解决身份、比例、材质、空间或构图的现成素材优先复用。不能把它重新转译成抽象描述后脱离原图重建；派生图必须写 inherits_from 和 change only。

### 5.2 确认点不是每一步都问

- 生成前只确认会改变产物的事项：目标、模型、画幅、参考角色、生成授权。
- 参考图生成后返回资产、用途、self-QA 和 lock/revise 选择；不自动假设已锁定。
- 视频候选生成后返回候选、问题、当前状态和下一步；不在用户未确认时直接称为 final。
- 用户已明确锁定并继续时，内部登记、评分、manifest、hash 和单变量编译不重复询问。
- 外部上传、付费、发布、提交或覆盖文件必须单独确认。

### 5.3 不允许静默停止

任何生成阶段结束后，交付必须有：

~~~text
artifact
self-QA
status: generated candidate / ready for review / locked / blocked
next action
~~~

用户没有回复时保持 ready for review；用户说继续时沿用当前 source truth；用户发送新素材时先回到 intake 并重建继承关系。

### 5.4 状态与证据

生成、锁定和最终验收是三个不同状态：

~~~yaml
stage_receipt:
  status: draft | ready_for_review | locked | generated | accepted | blocked
  source_truth: []
  produced_artifacts: []
  unresolved_questions: []
  next_action: ""
  evidence: []
~~~

没有真实外部生成 receipt，不声称已经生成；没有用户 lock，不声称 final；没有 live acceptance，不标记整个任务完成。

## 6. Seedance 2.0 适配规则

### 6.1 版本事实

当前项目只把 seedance_2_0_official_launch / 2.0 作为已解析卡。官方资料支持文本、图像、视频、音频混合参考，并展示多镜头音画生成；当前本地卡的执行状态是 documented product / manual export / unverified。

### 6.2 参考图绑定模板

~~~text
@Image 1 = clean first frame; preserve the exact product silhouette, black satin/lace structure, mirror position, and initial three-quarter composition. Use as the direct visual anchor for the opening state.

@Image 2 = clean end-composition target; use only to guide the final angle, mirror relationship, and negative space. Do not paste this image as visible content.

@Image 3 = product identity / material reference; use only for garment construction, satin highlight, lace edge, strap and hardware. Do not show board labels or layout.

@Image 4 = scene geography / FOV reference; use only for mirror, floor, camera axis and spatial depth. Do not animate its labels or panels.

@Image 5 = lighting / material reference; use only for burgundy edge light, black-level control and surface response.

@Image 6 = storyboard / motion map; use only for shot order, timing, camera path and transition logic. Do not recreate its panels, arrows, labels or borders.

No @Video or @Audio reference is attached in this run. Use the written audio plan, then route final sound according to the selected capability card and post-production policy.
~~~

### 6.3 最终粘贴文本

最终文本应从“参考角色”开始，而不是从“Seedance 2.0，生成……”开始。平台已经知道模型；文字只负责创作意图和执行指令。

### 6.4 2.5 / 30 秒兼容

未取得官方 2.5 capability card 前，不得写入 2.5 的硬参数。未来 adapter 只新增：

~~~yaml
capability_card_id: seedance_2_5_<official_surface>
version: "2.5"
max_duration_sec: 30
reference_budget: <officially verified>
native_audio: <officially verified>
longform_mode: <single_sequence | hybrid>
~~~

Prompt IR、时间状态、对象动作、音频 spine 和 transition schema 不变。

## 7. 图像到视频的链路规则

~~~text
图像 identity / scene / style
-> 图像 prompt + manifest
-> 生成候选
-> self-QA
-> user lock
-> clean frame export
-> video reference binding
-> video prompt
-> generation QA
~~~

禁止：

- 用 storyboard board 代替 clean frame。
- 用 style board 作为直接 first frame。
- 用未锁定的 generated candidate 作为视频真相。
- 在聊天中用“图一/图二”但最终 prompt 没有 @ 角色。
- 图像生成后不记录 prompt，导致下一次只能凭记忆重写。

## 8. Prompt 文本风格

### 8.1 写给模型的文本

- 直接、肯定、可观察。
- 先说主体和关键动作，再说摄影机和画面。
- 避免过多元话语：“请理解”“请参考以下规则”“作为专业导演”。
- 负面约束少而精准；正向约束优先。
- 关键连续性可在全局锁和 shot 内重复一次，但不要同义反复十次。

### 8.2 写给用户的文本

- 展示阶段、创作内容、专业判断、一个用户确认点。
- 不把 raw manifest 当成用户界面。
- 用户明确要“可复制 prompt”时才输出完整粘贴块。
- 用户未确认模型时不编译多模型 prompt。
- 生成后先 self-QA，再问用户 lock/revise。

## 9. 规范化验收

### Image prompt 通过条件

- Score ≥90。
- 资产角色、标题层级、继承来源、direct-input policy 齐全。
- visual decomposition 11 项齐全：subject、action/pose、details、environment、lighting、composition、style/camera、color、materials、proportion、intent。
- composition card 明确视觉重心、层次、负空间、运动空间、遮挡/动线和构图目的。
- render look 四层齐全；未使用的 optics、atmosphere 或 grade 写 none by design，启用项有 condition、intensity、preserve、exit/continuity。
- text policy 明确。
- negative 只针对当前失败。
- 下游 video use 明确。

### Video prompt 通过条件

- Score ≥90。
- 每个引用都能解析为 @Image/@Video/@Audio 或明确无引用。
- 每个 shot 有一个主动作和一个主运镜。
- 每个 shot 有构图状态和一个可解释的 composition purpose。
- 每个启用的光学、空气介质和调色效果都有触发条件；不能用 generic filter 或 cinematic look 代替。
- 时间轴没有无解释空档。
- 每个动态实体有起始态、触发、路径、终态和连续性。
- 每个边界有视觉桥、声音桥和风险。
- Audio route 与 capability card 一致。
- QA 标准可由视频回看验证。

### 运行通过条件

- prompt-only 不声称真实生成。
- external generation 未获授权时保持 blocked/instructions_only。
- generation candidate、user_locked、live acceptance 三个状态不混淆。
- retry 记录 failure_id 并只改一个变量。
- 用户提供的现成素材已先读取并完成 role、source、hash、inherits_from 或明确标记 unresolved。
- 生成后有 self-QA、status 和 next action，不静默停止。
