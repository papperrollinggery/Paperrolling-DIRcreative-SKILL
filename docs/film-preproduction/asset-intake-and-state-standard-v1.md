# DIRcreative Asset Intake 与 State Standard v1.0

状态：规范草案，供 skill 主流程和图像/视频编译器共享

## 1. 目的

本标准解决一个根本问题：用户已经提供了故事、客户文件、参考图、视频、音频或已做好的部分时，系统必须先读取并建立继承关系，而不是把现成事实重新翻译成文字后重新想象。

本标准只处理输入、复用、状态和确认。创意细节见 Prompt Authoring Standard，故障处置见 Prompt QA 与工作流故障处置手册。

## 2. 输入分流

每次收到新输入，先归类为一种或多种：

| 输入 | 默认处理 |
| --- | --- |
| 新 brief / idea | 建立 source truth，进入需求归一化 |
| 客户故事、脚本、分镜 | 读取、提取 shot truth，不重写成另一套故事 |
| 参考图、产品图、人物图 | 读取并登记 visual role，必要时作为 ImageGen edit/reference |
| 已生成但未锁定图 | 作为 candidate，可诊断或派生，不作为最终真相 |
| 用户明确认可或锁定图 | 作为高优先级 source truth，保持 hash 和几何身份 |
| 视频/动图 | 读取镜头、动作、节奏和可复用运动角色 |
| 音频 | 读取时长、节奏、音色和用途，登记 audio role |
| 客户最终文件 | 只读登记；除非明确授权，不覆盖、不移动、不改写 |

## 3. 来源优先级

~~~text
locked user/client final
> user/client reference
> confirmed project truth
> unlocked generated candidate
> generic model knowledge
~~~

发生冲突时：

1. 报告冲突对象。
2. 保留原始输入和 hash。
3. 询问一个能解决冲突的最小问题，或沿用用户最新明确决定。
4. 不把冲突静默合并成“看起来合理”的新版本。

## 4. Intake 记录

每个资产都必须登记：

~~~yaml
asset_id: ""
source_kind: user_upload | client_file | conversation_media | generated_candidate | project_file
source_locator: ""
source_hash: ""
media_metadata:
  width: null
  height: null
  duration_sec: null
  fps: null
  color_space: ""
role: identity | scene_fov | style_material | storyboard_motion | clean_start | clean_end | motion | audio | ambiguous
authorization: user_provided | project_owned | unknown
inherits_from: []
preserve: []
may_change: []
do_not_copy_or_animate: []
reuse_action: direct_reference | edit | derive | planning_only | unresolved
locked: false
qa_status: unreviewed | passed | failed
downstream_slots: []
~~~

hash 是追溯字段，不是审美评价。对话中出现但没有本地落盘路径的媒体可以登记为 conversation_media，但不得声称已写入工作区。

### 4.1 最小充分参考策略

参考图角色是可用的视觉控制输入，不是固定生成清单。提示词必须能够在只有人物、场景或产品现成素材的情况下独立完成专业编译。

| 参考角色 | 只有在这些条件成立时才生成 | 如果事实已经明确 |
| --- | --- | --- |
| identity / product / character | 身份、比例、结构、人物外观或产品几何未锁定，或存在多个相似主体 | 直接复用用户/客户/已锁定资产 |
| scene / FOV | 空间轴线、镜面/玻璃关系、复杂机位或场景连续性未锁定 | 用现有场景图、shot card 和文字继承 |
| style / material / lighting | 材质或灯光是故事核心、需要跨镜头重复，或模型已有明显漂移风险 | 直接写入提示词的 render look，不额外出图 |
| storyboard / motion | 需要客户看分镜、多人/多道具节拍复杂，或 shot card 难以表达 | 由 shot list、Prompt IR 和时间轴承担 |
| clean start / end frame | 选定的模型路线需要 start/end 或直接 image-to-video 锚点 | 不需要 frame-controlled 输入时不生成 |
| product detail / macro | 功能、结构或材质证据在 identity 图中不可读 | 不为装饰性细节单独生成 |

多人物：每个主要人物使用独立 identity asset；群像或交互另建 scene/blocking 参考，不用一张拼贴图同时承担多个人物身份。多资产：每个产品、道具、载体和环境硬件拥有唯一 asset_id、角色、preserve 和下游槽位；相似资产必须补充颜色、形状、位置或功能差异，不能用“它们”“另一个”代替实体名。

最终模型 prompt 只编译当前运行实际挂载的槽位。planning-only 资产可以留在 manifest 或作为模型允许的指导引用，但不能被误当作 direct first frame；未挂载的资产不进入最终 @Image/@Video/@Audio 文本。

## 5. 读取与视觉检查

### 5.1 图像

至少检查：

- 画幅、尺寸、格式、色彩信息。
- 主体轮廓、比例、结构、材质和颜色。
- foreground / midground / background。
- 视觉重心、负空间、运动空间、遮挡、镜面或玻璃关系。
- 光源方向、阴影、反射、高光、雾或空气介质。
- 可见文字、logo、标签、箭头、边框和分镜元素。
- 是否适合作为 identity、planning board 或 direct video input。

### 5.2 视频

至少检查：

- 起始帧、结束帧、镜头切换和主要动作。
- 相机路径、焦点变化、景别和屏幕方向。
- 主体、道具、环境的运动关系。
- 音画同步、转场、速度变化和可复用 motion role。
- 是否拥有使用授权，是否只能作为 planning reference。

### 5.3 音频

至少登记：

- 时长、节拍、音色、响度和主要事件。
- music、ambience、foley、SFX 或 voice 的角色。
- 可以作为模型输入、只能作为创作参考，还是必须后期制作。
- 画面中的 cue time 和 sound perspective。

## 6. 复用策略

### direct_reference

素材已经满足当前目标。只建立外部引用槽位和 preserve 约束，不再生成同类替代物。

### edit

素材身份正确，只修改用户指定变量。必须明确：

~~~text
Preserve:
Change only:
Forbidden change:
Expected pass signal:
~~~

### derive

素材作为上游真相，生成新的用途版本，例如从 style board 派生 clean frame，从 scene/FOV 派生不同景别。必须记录 inherits_from 和新用途。

### planning_only

素材只提供构图、运动、节奏或色彩方向。最终视频输入必须另有 clean frame；模型不得复制板式标签、箭头、边框或标题。

### unresolved

角色、授权、用途或冲突未解决。阻断外部交付，不凭猜测继续。

## 7. 用户确认纪律

### 必须确认

- 多个素材角色冲突且会改变生成结果。
- 用户提供的文件是否允许作为直接生成输入。
- 模型、画幅、时长或生成路线尚未确定。
- 要不要锁定参考图或候选。
- 需要外部上传、付费、发布、提交或覆盖文件。

### 不必重复确认

- 已确认过的模型和画幅。
- 纯内部 manifest、hash、评分和格式校验。
- 已明确授权的单变量派生。
- 用户已经说“锁定并继续”的同一产物。

### 生成后固定回执

每次生成后必须返回：

~~~text
artifact
self-QA
current status
one next action
~~~

如果用户没有回答，状态停在 ready_for_review；不能当作用户已经接受。

## 8. 与 ImageGen / Video Prompt 的交接

图像链：

~~~text
intake
-> role and lock
-> visual inspection
-> preserve/change contract
-> ImageGen reference or edit
-> self-QA
-> user lock
-> clean frame or reference slot
~~~

视频链：

~~~text
intake
-> reference map
-> composition and continuity locks
-> subject/object/environment actions
-> camera and look cards
-> timeline/audio/transition
-> model adapter
-> external handoff
~~~

ImageGen 编辑规则：

- 本地目标先查看，再把所有目标作为实际引用输入。
- 对话图片没有本地路径时，使用当前轮可用的图片引用机制，不伪造路径。
- 不能用文字重建代替已有图片。
- 不能通过修改描述来规避安全拦截。

Video adapter 规则：

- 内部 asset_id 只在 manifest 中存在。
- 最终 Seedance 文本使用平台可识别的 @Image、@Video、@Audio 角色。
- planning_only 资产不得被编译为 direct visual anchor。
- 未经 capability card 证实的时长、分辨率、引用数量和音频能力不得写入最终提示词。

## 9. 验收

Intake 通过条件：

- 每个输入都有来源、角色、授权状态和用途。
- 用户或客户提供的现成素材已经先被读取。
- 锁定资产没有被覆盖或替换。
- 所有派生资产都有 inherits_from。
- direct video input、planning_only 和 clean frame 没有混淆。
- unresolved 资产不会进入外部交付。
- 生成后有 self-QA、状态和 next_action。

最小验证 fixture：

1. 用户提供一张客户产品图：应进入 identity/direct_reference。
2. 用户提供一张带箭头分镜板：应进入 storyboard/planning_only。
3. 用户提供一张 clean frame 并要求延展：应保留 geometry 并进入 clean_start。
4. 用户提供一段参考视频：应登记 motion，不自动复制人物身份。
5. 用户生成候选后说“锁定”：应记录 locked、hash 和 receipt。
