# DIRcreative Prompt QA 与工作流故障处置手册 v1.0

状态：规范草案，供 skill 实现、提示词编译和真实生成验收使用

本手册解决两类问题：

1. 提示词很长，却没有把构图、动作、镜头、光学、调色和声音编译成可执行约束。
2. 工作流在生成、接收用户素材或等待确认时失去状态，导致重复生成、停止不问、跳过锁定或把候选误当最终真相。

本手册只规定可验证的工作方式，不代表已经接入外部平台或完成真实生成。

## 1. 第一性原理

### 1.1 单一真相优先

所有输出先回答“当前最可靠的视觉事实是什么”，再回答“下一步需要生成什么”。

来源优先级：

~~~text
用户明确锁定或交付的最终资产
> 用户提供的参考图、客户文件、现成故事或分镜
> 项目已确认的 visual bible / shot truth
> 本项目已生成但未锁定的候选
> 通用风格知识与模型想象
~~~

下游不得覆盖上游事实。已锁定资产只能被引用、派生或在明确授权下编辑，不能因为重新写 prompt 就重新发明身份、比例、材质或空间。

### 1.2 最小充分行动

每一步只做完成当前阶段所需的最小动作：

- 能读取并复用现有素材，就不重新凭文字生成同一素材。
- 能用一个模型 adapter 解决，就不同时编译多套模型 prompt。
- 能用一个确认点解决，就不把内部字段逐项询问用户。
- 能定位到一层，就不重写整段 prompt。
- 没有真实生成，就不输出“已生成”；没有用户 lock，就不输出“最终”。

### 1.3 提示词必须产生可观察结果

抽象词只能作为意图标签，不能代替执行细节。每个重要判断必须能在图像或视频回看中回答：

- 构图重心在哪里，为什么在那里？
- 主体、道具、环境分别发生了什么？
- 相机从哪里到哪里，如何改变空间关系？
- 光、镜头、空气介质和调色各自做了什么？
- 声音何时进入、退出或改变视角？
- 哪一项如果失败，下一次只改哪一层？

## 2. 状态机与阶段交接

标准状态流：

~~~text
intake
-> source_truth_normalized
-> route_selected
-> asset_reuse_or_generation
-> self_qa
-> user_review
-> user_locked
-> prompt_compiled
-> external_handoff
-> generated_candidate
-> generation_self_qa
-> user_accept_or_revise
-> live_acceptance_receipt
~~~

每个阶段必须输出：

~~~yaml
stage_receipt:
  stage_id: ""
  status: draft | ready_for_review | locked | blocked | generated | accepted
  source_truth: []
  produced_artifacts: []
  unresolved_questions: []
  next_action: ""
  user_confirmation_required: false
  evidence: []
~~~

status 为 generated 不等于 status 为 accepted。status 为 ready_for_review 不等于 status 为 locked。任何阶段都不得静默结束。

### 2.1 阶段门禁

| 门 | 触发时机 | 必须确认 | 不应询问 |
| --- | --- | --- | --- |
| G0 输入分流 | 收到 brief、客户文件或图片 | 只有存在会改变产物的歧义才提问 | 不问已能从素材读取的内容 |
| G1 生成前 | 进入图像或视频生成 | 当前目标、模型、画幅、参考角色、是否授权实际生成 | 不编译用户未选择的多模型版本 |
| G2 参考图完成 | 参考 pack 或 clean frame 完成 | 展示资产、用途、self-QA，请用户 lock/revise | 不在用户未看到产物时默认锁定 |
| G3 候选生成后 | 外部或内置模型返回候选 | 展示候选、问题、保留项，请用户 lock/revise/use as source | 不把候选直接当 final |
| G4 外部交付前 | 需要上传、付款、发布或提交 | 范围、授权、平台、输入槽位和执行状态 | 不把 instructions_only 说成真实执行 |

G0、G1、G2、G3、G4 不是每次都全部询问。若用户已在同一轮明确确认，receipt 记录已确认事项并继续；只有会改变结果的未决项才暂停。

## 3. 收到用户现成素材时的处理

### 3.1 输入类型

收到以下任一内容时，先进入 intake，不直接重写或重新生成：

- 客户已经做好的故事、脚本、分镜或提示词。
- 用户上传的参考图、视频、音频、logo、产品图或 clean frame。
- 对话中已经生成并被用户认可的图。
- 用户说“沿用这个”“以这张为基础”“抓取这张图的内容”。

### 3.2 读取顺序

~~~text
1. 识别文件、附件、对话媒体和来源
2. 读取尺寸、格式、颜色空间、时长、帧率等可得元数据
3. 视觉检查主体、构图、空间、光线、材质和文字
4. 判断角色：identity / scene / style / storyboard / clean frame / motion / audio
5. 记录 preserve、may_change、do_not_copy_or_animate
6. 计算或登记 hash；原始文件只读保留
7. 建立 asset manifest 和下游用途
8. 只有素材不能满足当前阶段时，才提出最小补充问题或派生生成
~~~

不能只依靠文件名或用户一句“这是图一”判断角色。角色必须由可见内容和项目上下文共同确认；不确定时标记 role: ambiguous，不要假装确定。

### 3.3 复用与派生规则

如果已有素材已经包含产品身份、人物身份、场景空间或镜头构图：

- 图像生成应使用该素材作为 reference image 或 edit source。
- 视频 prompt 应把它编译成对应的 @Image/@Video 角色。
- 派生图只改变用户授权的变量。
- 新生成物必须记录 inherits_from 和 change_only。
- 不能把现成素材重新翻译成一段抽象描述后脱离原图生成，这会丢失几何、比例、纹理和空间关系。

使用 ImageGen 编辑本地素材时：

- 先检查目标图片，再将每一张实际要编辑的本地图片作为引用输入。
- 全部目标都有本地路径时使用本地引用；不能用一张描述性 prompt 冒充缺失的参考图。
- 采用 preserve / change / forbidden change 三段式。
- 若用户仅提供对话图片而不是本地路径，保留其作为当前轮输入引用，不凭空声称已写入工作区。
- 安全拦截时报告边界，不能通过换词规避安全规则。

### 3.4 资产 manifest 最小字段

~~~yaml
asset:
  asset_id: ""
  source_kind: user_upload | client_file | conversation_media | generated_candidate | project_file
  source_locator: ""
  source_hash: ""
  role: identity | scene_fov | style_material | storyboard_motion | clean_start | clean_end | motion | audio | ambiguous
  source_authorization: user_provided | project_owned | unknown
  preserve: []
  may_change: []
  do_not_copy_or_animate: []
  reuse_action: direct_reference | edit | derive | planning_only | unresolved
  locked: false
  downstream_slots: []
  qa_status: unreviewed | passed | failed
~~~

source_authorization 为 unknown 或 role 为 ambiguous 时，不能进入不可逆外部交付。

## 4. 提示词编译前的最小输入

### 4.1 图像任务

必须先有：

~~~text
asset role
purpose
source references
composition intent
subject/material truth
lighting and look conditions
text policy
output aspect/size from capability card
preserve/change/forbidden change
pass signal
~~~

### 4.2 视频任务

必须先有：

~~~text
selected model and capability card
reference map
story/shot purpose
global continuity locks
composition and screen direction
subject/object/environment actions
camera start/path/end and reason
time beats
conditional look layers
transition and audio cues
targeted guardrails
generation route
pass signal
~~~

缺少其中一项时，优先回到 source truth 或 intake；不要用更多形容词填空。

## 5. 构图、镜头与 Look 的故障树

### 5.1 构图失败

F-COMP-01：主体没有视觉重心。
表现：主体被背景、文字、反光或边缘裁切抢走。

检查：

- 主体、辅助主体、负空间和视觉路径是否明确。
- 是否存在前景遮挡、镜面反射或线条把视线带离主体。
- 画幅变化后安全区和运动空间是否仍成立。

一次只改 composition layer。保留主体身份、材质、光线和动作。

F-COMP-02：构图机械套用规则。
表现：所有镜头都在三分法、中心构图或对称构图，缺少叙事目的。

修复：为构图选择一个可观察目的：

~~~text
hero emphasis
reveal through occlusion
negative-space release
material isolation
power / vulnerability
symmetry / ritual
parallax depth
directional movement room
~~~

规则不是必须套用的模板；构图选择必须服务当前 beat。

### 5.2 镜头失败

F-CAMERA-01：只有“高级运镜词”，没有路径。
修复：补 start target、path、end target、support、speed/easing、focus、reason。

F-CAMERA-02：一个 shot 同时要求多个主运镜和多个主动作。
修复：保留一个主镜头动作、一个主主体动作；其余变成环境或声音响应，或拆 shot。

F-CAMERA-03：运动与故事不匹配。
修复：删除炫技运动，先写该运动改变的空间关系或心理信息。

### 5.3 光学、空气介质与调色失败

每个 shot 使用四层 look 结构；未触发的层写 none by design，不要默认套用：

~~~yaml
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
~~~

故障编号：

- F-LOOK-01：画面平、调色没有叙事作用。
- F-OPT-01：只写“电影滤镜”，没有光学行为。
- F-OPT-02：flare/bloom 洗白主体或吞掉黑色材质。
- F-ATM-01：没有方向性光源和介质条件，却出现假丁达尔光。
- F-OPT-03：焦点、景深、bokeh 形状与光源位置不匹配。
- F-GRADE-01：调色破坏前后镜头的白平衡、肤色、产品材质或亮度连续性。

修复时必须写触发条件。例如：

~~~text
只有当画外的暖色 practical 以 20–30 度角进入镜头边缘，并且高光越过前组镜片时，才出现很轻的 veiling flare 和局部 halation；高光只停留在画面边缘，不覆盖黑色缎面主体。practical 离开镜头轴线后，flare 在 0.3 秒内消退。
~~~

### 5.4 声音与画面失败

F-AUDIO-01：声音只有“氛围感”。
修复：按 dialogue、VO、ambience、SFX、foley、music、silence 写 cue 和 perspective。

F-AUDIO-02：声音事件没有画面触发。
修复：每个明显声音绑定到接触、移动、焦点落点、转场或环境变化。

### 5.5 参考图失败

F-REF-01：模型复现了 storyboard 的标签、边框或箭头。
修复：将 storyboard 降级为 planning_only，并提供 clean frame 作为 direct visual anchor。

F-REF-02：引用槽位与内部资产不一致。
修复：先重建 manifest 和上传顺序，再编译最终 @ 引用；不能在 prompt 内猜编号。

## 6. 单变量重试协议

每次重试必须先生成 incident record：

~~~yaml
incident:
  failure_id: ""
  observed_output: ""
  suspected_layer: composition | reference | subject | object | environment | camera | lighting | optics | atmosphere | grade | audio | transition | capability | output
  preserve: []
  change_only: ""
  new_constraint: ""
  expected_pass_signal: ""
  upstream_owner: ""
  result: pending | passed | failed
~~~

重试层级顺序：

~~~text
1. reference / source truth
2. composition
3. subject-object-environment action
4. camera / focus
5. lighting
6. optics
7. atmosphere
8. grade
9. audio
10. transition / VFX
11. capability / output
~~~

一次 retry 不得同时改动两个以上层。若问题来自上游参考图，先修参考图，不要在视频 prompt 里堆负面词补救。

### 6.1 收敛预算与升级条件

- 同一个 failure id、同一个 corrected layer 默认最多连续重试 3 次。
- 每次必须保存上一次输出、变更假设和可观察 pass signal；没有对比证据不计为有效重试。
- 连续两次没有朝 pass signal 改善时，停止增加提示词，改为降低动作/人物/运镜复杂度、拆分生成单元、变更 reference route、切换 exact-card adapter 或转后期。
- 第三次仍失败时，状态必须变为 `blocked` 或 `needs_user`，并明确最小升级选择；不得自动开始第四次同层重写。
- source truth、授权、能力卡或用户偏好不明确时立即停止，不消耗重试预算猜测。

一次重试可以包含维持语义一致所必需的最小联动字段，例如更换 reference binding 时同步更新 upload slot；这仍算一个因果假设，不得借机改写故事、镜头、Look 和输出参数。

## 7. 生成后不停止协议

任何图像或视频生成完成后，下一次交付必须包含四项：

1. 生成结果或明确的候选 artifact。
2. 系统 self-QA：通过项、失败项、未验证项。
3. 当前状态：generated candidate / ready for user review / locked / blocked。
4. 一个明确的下一步：lock、revise 哪一层、或进入下一阶段。

如果用户未回复，任务停在 ready_for_user_review，不能把它写成完成；如果用户说“继续”，沿用当前 truth 进入下一步；如果用户上传新素材，先 rebase 到新素材再继续。

只有以下情况可以不再询问：

- 用户本轮已明确“锁定并继续”。
- 用户已明确授权直接生成且当前产物不是用户锁定资产。
- 当前动作只是内部计算、manifest 登记、评分或文件校验，不改变创作结果。

## 8. Receipt 与完成门禁

最小 receipt：

~~~yaml
receipt:
  task_id: ""
  source_truth_ids: []
  selected_model: ""
  generation_route: prompt_only | native | external | postproduction | blocked
  artifact_ids: []
  artifact_hashes: []
  prompt_score: null
  qa_status: passed | failed | unverified
  user_decision: pending | revise | locked | accepted
  live_acceptance: pending | received | not_applicable
  next_action: ""
~~~

完成门禁：

- 仅写 prompt：generation_route 为 prompt_only，不得声称视频已生成。
- 生成了候选：必须有 artifact、QA 和用户审阅状态。
- 用户说锁定：必须记录锁定对象和版本/hash。
- 最终验收：必须有 live acceptance receipt；否则目标保持未完成。

## 9. 最小实现顺序

1. 先实现 asset intake、source precedence、manifest 和状态 receipt。
2. 再实现 image prompt 的 composition 与四层 look。
3. 再实现 video prompt 的时间、镜头、动作、声音、转场和 Seedance @ adapter。
4. 再实现 score、failure IDs、单变量 retry。
5. 最后接真实外部生成和用户 acceptance。

验证原则：每增加一层，都用一个真实小 fixture 回放；不先扩展大量模板、不先编译未来模型、不先批量生成无用途的参考图。
