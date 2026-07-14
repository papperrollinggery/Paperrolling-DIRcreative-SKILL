# DIRcreative 图像 / 视频提示词系统研究与现状审计

状态：研究基线 / 不代表运行时已升级

日期：2026-07-12

研究范围：当前 DIRcreative 对话与产物、仓库内图像/视频 prompt 规范、Seedance 2.0 官方资料、TapNow 节点工作流、GitHub 公开 skill 与 prompt library、专业电影摄影与声音资料、官方图像/视频 prompt 指南，以及未来 30 秒模型的兼容性设计。

## 1. 研究边界

“全网”无法被严格证明为穷尽式搜索。本轮采用多源、分层、可复核的公开资料研究：

| 来源层 | 研究对象 | 可借用内容 | 不可直接借用 |
| --- | --- | --- | --- |
| S1 官方模型/平台 | ByteDance Seedance、TapNow、OpenAI、Runway | 当前能力、输入角色、节点关系、官方提示词原则 | 社区推测、第三方平台参数 |
| S2 原始论文 | Seedance 2.0 论文 | 版本范围、生成单元与多模态研究事实 | UI 或第三方产品行为 |
| S3 专业创作资料 | American Cinematographer、Dolby、FilmSkills | 摄影机运动的动机、镜头/声音关系、制作语言 | 把电影术语当成模型已支持的参数 |
| S4 GitHub skill / prompt library | Seedance skill、GPT Image skill、Higgsfield skill、prompt gallery | 结构、模板、问题分类、经验性表达 | 版本限制、价格、成功率、平台可用性 |
| S5 用户观察 | 本次对话、用户提供的 TabNow 工作流经验 | 实际体验、产品需求、质量目标 | 未经生成验证的模型能力结论 |

## 2. 官方与专业资料结论

### 2.1 Seedance 2.0：必须使用平台引用角色，而不是内部文件名

ByteDance 官方 Seedance 2.0 发布页明确展示了文本、图片、视频、音频混合引用，并用 `@Image 1` 这类角色绑定方式表达“脚本/分镜来自哪张图、人物来自哪张图、场景来自哪张图”。官方示例同时把景别、运镜、画面、文案与声音放进同一条拍摄指令中。

因此，当前 prompt 中的 `R05`、`R06` 是内部项目标识，不能原样作为最终粘贴文本。正确链路应是：

```text
内部资产 ID -> TabNow / Seedance 上传顺序 -> @Image 1 / @Image 2 -> 角色说明 -> 反误读约束
```

当前能力卡仍以 `seedance_2_0_official_launch` / `2.0` 为准；平台执行状态仍是 `manual_export`、`execution_verification_status: unverified`，所以本项目只能声称“生成提示词已准备”，不能声称已在 TabNow 真实生成。

来源：

- [Seedance 2.0 Official Launch](https://seed.bytedance.com/en/blog/seedance-2-0-official-launch)
- [Seedance 2.0 官方论文](https://arxiv.org/abs/2604.14148)
- [DIRcreative model-sources.yaml](../sources/model-sources.yaml)

### 2.2 声音不是装饰词，而是独立的时间轨

官方 Seedance 2.0 材料强调音画联合生成、背景音乐、环境音效与角色声音的同步。专业声音资料把声音拆成 dialogue、voiceover、ambience、SFX、foley、music、silence，而不是一句“有氛围音”。American Cinematographer 对《寂静之地》的案例也说明，近距离画面、物体细节和声音设计必须互相支持：镜头越接近可听见的物体，细微声音越有可信度。

本系统必须同时记录：

```text
desired_audio     = 创作上想听到什么
generation_route  = 当前模型是否允许原生生成
cue_timeline      = 哪个声音在何时进入、退出、变化
post_mix_handoff  = 原生声音不可靠时交给后期怎么做
```

来源：

- [Seedance 2.0 Official Launch](https://seed.bytedance.com/en/blog/seedance-2-0-official-launch)
- [American Cinematographer: Don’t Speak — A Quiet Place](https://theasc.com/articles/dont-speak-a-quiet-place)
- [Dolby Atmos for sound creators](https://professional.dolby.com/cinema/dolby-atmos/)
- [DIRcreative Audio Design Notes](../research/audio-design-notes.md)

### 2.3 高级运镜必须有叙事动机、实体起止目标和可执行路径

American Cinematographer 的镜头运动资料强调：运动应该由剧本、导演意图和画面设计驱动；慢速 creep-in 可以表达逼近、危机或认知变化；dolly、slider、gimbal、Steadicam、crane 各自提供不同的空间关系和运动质感。复杂运动不是越多越好，随机添加 360°、dolly zoom、whip pan 反而会削弱可控性。

因此 `slow push`、`cinematic orbit`、`camera follows` 只能作为简写，不能作为完成态。完成态至少要给出：

```text
shot_size + angle + lens_feel + camera_support
start_target -> movement_path -> end_target
speed / easing + focus behavior + movement motivation
```

来源：

- [American Cinematographer: Shot Craft — Tools for Camera Movement](https://theasc.com/articles/shot-craft-camera-movement)
- [American Cinematographer: Putting the Move in Movie](https://theasc.com/magazine/oct03/sub/)
- [DIRcreative Shot Language Standard](../shot-language-standard.md)

### 2.4 时间轴要写“可观察变化”，不是只写三段概念

OpenAI 的 Sora 官方提示词指南把复杂镜头写成 storyboard 单元：镜头构图、景深、动作节拍、灯光、调色、声音和镜头理由都可以进入提示词；每个 shot 只保留一个主要镜头动作和一个主要主体动作。Runway 的官方 image-to-video 指南也把输入图视为构图/主体/光线/风格锚点，把文字 prompt 重点放在主体运动、环境运动、镜头运动、时序和速度上，并推荐用有时间标记的 sequential prompting。

这支持本项目的“时间编排层”，但不意味着 Seedance 必须照搬其他平台格式。规范应在模型无关层先建立时间状态，再由 Seedance adapter 编译成自然语言。

来源：

- [OpenAI Sora 2 Prompting Guide](https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide)
- [Runway Image to Video Prompting Guide](https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide)
- [DIRcreative Longform Decomposition Policy](../longform-decomposition-policy.md)

### 2.5 TapNow 的关键不是“自动润色”，而是可连线的制作图

TapNow 官方文档显示，其 Canvas 以节点承载文本、图片和本地上传素材，并允许把文本节点与图片节点连接为视频生成参考；图片节点还有 prompt optimizer。这个结构解释了用户观察到的“别人把参考图和 prompt 放进 Tab/TapNow 后效果更好”：模型不是只看到一段孤立文字，而是看到有来源关系的输入图谱。

本项目的交付不能只给一段 markdown。必须同时导出：

```text
brief/story node
visual-bible node
image-prompt node
reference-image nodes
clean-frame nodes
video-prompt node
audio-plan node
model-config node
generation node
QA / retry / lock nodes
```

来源：

- [TapNow 官方节点文档](https://docs.tapnow.ai/en/docs/my-canvas/unlock-the-power-of-nodes)
- [ComfyUI Seedance 2.0 workflow documentation](https://docs.comfy.org/tutorials/partner-nodes/bytedance/seedance-2-0)

### 2.6 构图、镜头、光学与调色必须按条件编译

本轮新增的要求不是“给所有镜头加更多电影术语”，而是建立可触发的 look stack：

~~~text
lighting
-> optical capture
-> atmosphere / medium
-> color grade / post
~~~

构图也不能停在三分法、中心构图或“高级构图”。shot 必须回答视觉重心、主体层级、前中后景、负空间、运动空间、遮挡/动线、透视深度和叙事目的；主体或相机移动时，还要说明这些关系如何变化。

专业资料支持以下边界：

- American Cinematographer 强调镜头运动应服从剧本、导演意图和整体视觉设计；复杂运动不是质量本身。
- ASC 的镜头测试资料把 bokeh、falloff、veiling glare、chromatic/spherical aberration、astigmatism 和 flare 作为需要测试和控制的不同光学行为。
- Panavision 将 anamorphic flare、bokeh、magnification/perspective、focus roll-off 等作为不同的镜头特性，不应统称为一个“滤镜”。
- Kodak 对 gamma、density、neutrality、saturation、ND 和 halation 的定义说明了曝光控制、光学滤镜和后期/成像效果之间的区别；bleach-bypass 等处理也会同时改变对比度、阴影、高光、饱和度和颗粒。
- ASC 的案例显示，特定滤镜或 flare 可以作为情绪、转场或心理状态 cue，但不是每个镜头的默认装饰。

因此，最终 prompt 采用每镜头四层 look card：

~~~yaml
render_look:
  lighting: condition / source / quality / contrast
  optics: condition / lens / filtration / physical behavior / intensity
  atmosphere: condition / medium / density / light path / movement
  grade: condition / white balance / gamma / black level / highlights / saturation / palette / grain
  preserve: subject and material readability
  exit_or_continuity: when the effect ends or carries forward
~~~

示例约束：

- anamorphic 只有在横向 flare、椭圆 bokeh、边缘畸变或宽银幕语言服务故事时启用；竖屏项目仍需写清 9:16 构图和裁切安全。
- 丁达尔/体积光只有在方向性光源、悬浮介质和可见光路同时成立时启用；必须写密度和衰减，不能写 generic god rays。
- bokeh 必须绑定焦点目标、背景点光源、形状/尺度和景深层次。
- flare/refraction 必须写入射光源、进入镜头的角度、streak/ghost/veiling 行为、出现/消退时间，并保护主体可读性。
- 调色先建立白平衡和中性锚点，再写对比度、黑位、highlight roll-off、饱和度/密度和色相分离；强 bleach-bypass、grain 或 bloom 必须有故事条件。

来源：

- [American Cinematographer: Shot Craft — Tools for Camera Movement](https://theasc.com/articles/shot-craft-camera-movement)
- [American Cinematographer: ShareGrid Anamorphic Lens Test Library](https://theasc.com/articles/sharegrid-offers-online-anamorphic-lens-test-library)
- [American Cinematographer: Anamorphic Lens Characteristics](https://theasc.com/articles/shadows-from-the-past-them)
- [Panavision: The Five Pillars of Anamorphic Flare](https://www.panavision.com/highlights/highlights-detail/the-five-pillars-of-anamorphic-flare)
- [Kodak Motion Picture Glossary](https://www.kodak.com/en/motion/page/glossary-of-motion-picture-terms/)
- [Kodak Processing Techniques](https://www.kodak.com/en/motion/page/processing-techniques/)
- [American Cinematographer: Instinct — Enlightening Illumination](https://theasc.com/articles/instinct-enlightening-illumination)

### 2.7 从第一性原理重做工作流，而不是增加确认仪式

用户反馈暴露出的流程缺口不是“确认按钮不够多”，而是状态和来源没有被正确管理。优化后的最小流程是：

~~~text
读取用户/客户现成输入
-> 建立 source truth 与资产角色
-> 判断复用、编辑、派生或 planning-only
-> 只确认会改变结果的歧义
-> 生成一项必要资产
-> self-QA + 返回候选状态
-> 用户 lock/revise
-> 编译单一已选模型的 prompt
-> external handoff / generation
-> self-QA + 用户 acceptance
~~~

以下动作不得再发生：

- 已有参考图能解决身份和空间时，重新凭文字想象同一对象。
- 用户未选模型时同时编译多套模型 prompt。
- 生成图后没有返回 self-QA、状态和下一步。
- 把 planning storyboard 误当 direct video input。
- 用一串滤镜词、运镜词或“电影感”形容词掩盖没有构图、路径、触发条件和验收标准。

## 3. GitHub skill / prompt library 研究结论

### 3.1 `dexhunter/seedance2-skill`

有用结构：

- 明确列出 `@Image`、`@Video`、`@Audio` 的角色绑定。
- 把 prompt 拆为 subject、scene、action、camera、timing、transition/effects、audio、style。
- 对产品展示、科学可视化、一次性长镜头、视频延展分别提供模板。
- 用“先做什么、再做什么、最后停在哪里”的时间段描述动作。

不采纳的内容：

- 与 ByteDance 官方或本地能力卡冲突的上传总数、分辨率、平台限制和成功率。
- 把社区术语表当成 Seedance 官方参数。

来源：[dexhunter/seedance2-skill](https://github.com/dexhunter/seedance2-skill/blob/main/SKILL.md)

### 3.2 `makesupday/Awesome-Seedance-2.0-Prompt-and-Examples`

有用结构：

- 把 image-to-video 的文字部分集中写运动，而不是重复描述输入图中已经存在的物体。
- 把产品、场景、相机、风格、声音、VFX、时间轴分开。
- 记录产品形体、文字、logo、镜头和动作的常见失败。

不采纳的内容：

- README 中未经官方证据支持的分辨率、引用数量、成功率和“30–100 words 最佳”等硬规则。
- 把一个 30 秒产品故事模板当成所有模型都能一次生成的事实。

来源：[makesupday/Awesome-Seedance-2.0-Prompt-and-Examples](https://github.com/makesupday/Awesome-Seedance-2.0-Prompt-and-Examples)

### 3.3 `wuyoscar/gpt_image_2_skill` 与图像提示词模式

有用结构：

- gallery-first：先选择参考模式，再写 prompt。
- 复杂图片使用 JSON/config 记录角色、构图、参考图、材质和约束。
- 编辑任务明确 preserve / change，且两者不能重叠。
- 先声明画幅和用途，再写场景、主体、细节、限制。

不采纳的内容：

- 第三方 CLI、价格、模型参数或当前可用性，除非由当前项目能力卡重新验证。

来源：[wuyoscar/gpt_image_2_skill](https://github.com/wuyoscar/gpt_image_2_skill)

### 3.4 `OSideMedia/higgsfield-ai-prompt-skill`

有用结构：

- MCSLA：Model、Camera、Subject、Look、Action。
- 通过技能路由把不同模型、摄影机、动作、声音和参考资料分开。
- 把提示词写作与执行面分层。

本项目升级：

```text
MCSLA 作为快速完整性检查
DIRcreative Prompt IR 作为正式生产结构
Seedance adapter 负责 @ 引用、平台格式与版本限制
```

来源：[OSideMedia/higgsfield-ai-prompt-skill](https://github.com/OSideMedia/higgsfield-ai-prompt-skill)

## 4. 当前项目的量化基线

以下评分是“提示词与控制链完整度审计”，不是实际视频画质 benchmark。因为当前运行状态是 `prompt_only`，尚未有 Seedance 真实生成样本，所以不能把这些分数写成模型质量结论。

### 4.1 当前 Seedance 视频 prompt：40 / 100

| 维度 | 权重 | 当前得分 | 证据 / 缺口 |
| --- | ---: | ---: | --- |
| 参考图绑定 | 15 | 3 | 使用 `R05/R06` 内部标签，没有编译为 `@Image` 角色图谱 |
| 时间轴与微节拍 | 15 | 5 | 只有 3 个大段，缺少每秒可观察的动作、停顿、声音和状态 |
| 摄影机语言 | 15 | 4 | 有 push/glide/pull，但缺少起止目标、rig、焦段理由、焦点和速度曲线 |
| 主体/道具/环境动作 | 15 | 8 | 产品主体有动作，缺少独立的道具状态、环境反应与物理后果层 |
| 声音设计 | 10 | 3 | 有声音类别，没有 cue 时间、音画关系、层级和后期交接 |
| 转场与 VFX | 10 | 2 | 主要是“切入/回到”，没有 match cut、光效桥、镜面/焦点转场策略 |
| 连续性与负面约束 | 10 | 8 | 产品、颜色、无真人和文字禁区写得相对完整 |
| 能力卡与输出控制 | 5 | 3 | 时长/画幅写出，但没有把平台引用槽和执行面分开 |
| QA 与单变量重试 | 5 | 4 | 有初检和重试，但还没有与具体失败 ID/证据绑定 |
| **合计** | **100** | **40** | **需要重写，不应直接作为最终生产 prompt** |

### 4.2 当前图像 prompt 链：36 / 100（可复用性与可审计度）

这不是对 6 张已生成图的视觉质量打分。现有图片已经做过人工视觉检查并被用户锁定；36 分反映的是“生成它们的 prompt、manifest、角色与 QA 证据没有完整沉淀”。

| 维度 | 权重 | 当前得分 | 主要问题 |
| --- | ---: | ---: | --- |
| 预生成契约与资产角色 | 15 | 4 | 当前 pack 没有逐图可复用 prompt 文件与正式 manifest |
| visual decomposition | 20 | 5 | 产物可见，但主体/构图/层次/材质/用途没有逐图结构化存档 |
| 构图与版式控制 | 15 | 6 | 生成结果有板式意图，但 prompt 依据不完整 |
| 灯光、镜头、材质 | 15 | 7 | 结果中有黑缎、镜面、酒红光，缺少可重复的生产语言 |
| 参考图与连续性 | 15 | 5 | 没有图像到视频槽位的完整可追溯映射 |
| 文本 / no-text / direct-input policy | 10 | 4 | 部分图是 planning-only，部分是 clean frame，但边界依赖聊天历史 |
| QA、重试与版本 | 10 | 5 | 做了视觉复核，但没有逐图失败码和单变量重试记录 |
| **合计** | **100** | **36** | **需要补齐图像 prompt manifest 与资产谱系** |

### 4.3 当前流程：59 / 100

主要扣分不是技术能力，而是控制面：生成后没有及时询问用户、模型选择前先编译了多套、最终 prompt 没有从内部资产 ID 编译到平台角色、图像产物没有反向沉淀为可复用 prompt truth。

新增审计发现：

- 旧视频 prompt 没有独立的 composition card，无法验证视觉重心、负空间、运动空间和构图变化。
- 旧 look 描述没有区分 lighting、optics、atmosphere、grade，缺少 flare、bokeh、haze、Tyndall 和调色的触发条件。
- 旧流程没有把“用户/客户现成素材先读取并复用”作为硬门；因此存在不一致重生成风险。
- 旧流程没有把“生成后 self-QA + 当前状态 + next action”作为固定回执；因此存在生成后静默停止风险。

## 5. 研究后确定的核心原则

1. **先建立 Prompt IR，再由模型 adapter 编译。** 不把某一个平台的写法直接当作系统规范。
2. **每张图与每条视频都有一个生产角色。** Identity、scene/FOV、style/material、storyboard、clean frame、motion、audio 不能混成“参考图”。
3. **最终粘贴文本只出现平台能识别的引用。** Seedance 使用 `@Image` / `@Video` / `@Audio`；内部 `asset_id` 只留在 manifest 和 TabNow 节点。
4. **每个动态实体都有状态机。** `initial -> trigger -> path -> interaction -> consequence -> final`。
5. **每个镜头只有一个主运镜和一个主动作。** 复合运动必须分解成顺序步骤，不用“高级感”代替路径。
6. **声音有独立时间轴。** 图片 prompt 只记录下游声音意图；视频 prompt 才写可执行声音；原生音频与后期 route 分离。
7. **细节越多，不等于越好。** 细节必须有角色、时间、物理对象和验收标准；否则会造成 prompt overload。
8. **长时长不是把 10 秒 prompt 拉长。** 30 秒需要 sequence / state / transition / audio spine / continuity handoff。
9. **社区 prompt 只能贡献结构。** 所有模型能力、时长、引用数量、版权和执行状态必须回到官方或本地能力卡。
10. **每次失败只改一层。** 先确认是参考绑定、动作、摄影机、材质灯光、声音、转场还是输出控制，不整段重写。
11. **构图是叙事控制量，不是固定构图口诀。** 每个镜头选择视觉重心、层次、负空间、遮挡、动线和透视关系，并说明目的。
12. **Look 采用条件式四层。** lighting、optics、atmosphere、grade 可以为空，但不能含糊；启用效果必须写触发、强度、保留和退出连续性。
13. **先 intake 再生成，先 self-QA 再询问 lock。** 用户已有素材优先成为 source truth，候选、锁定和验收分别记录。

## 6. 研究结论

当前主要缺口不是“再加更多形容词”，而是缺少一个把导演意图转成可执行控制量的中间层。后续优化应优先建设：

```text
Prompt IR
-> image prompt compiler
-> reference / clean-frame compiler
-> video shot + audio compiler
-> Seedance @-role adapter
-> TapNow node graph export
-> generation QA / one-variable retry
-> user lock / acceptance receipt
```

完整需求、执行阶段、量化指标、问题处置和文档升级规范见：

- [Prompt System Upgrade PRD](../prompt-system-upgrade-prd-v1.md)
- [Prompt Authoring Standard](../prompt-authoring-standard-v1.md)
- [Prompt QA and Incident Runbook](../prompt-qa-and-incident-runbook-v1.md)
- [Asset Intake and State Standard](../asset-intake-and-state-standard-v1.md)
