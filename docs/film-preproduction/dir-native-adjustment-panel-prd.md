# DIRcreative 原生调节面板 PRD

Status: post-v0.7.1 product specification; not implemented

Date: 2026-09-04

## 1. 产品结论

DIRcreative 不需要再造一个 localhost 网页或把完整工作台塞进对话内卡片。推荐产品形态是：

```text
Codex 原生 Visual Workspace 全屏画布
    + DIRcreative 项目文件只读适配层
    + 对话中的自然语言控制器
    + 经过现有 gate 校验的写回/生成动作
```

面板负责看、比较、定位和表达修改意图；DIRcreative 负责重新读取当前真相、判断影响、执行最小修改并验证；项目文件继续是权威状态。画布点击不能直接把候选标成已采用、已批准、已生成或已发布。

该方案利用已验证的 Visual Workspace 宿主能力：原生全屏无限画布、只读扫描项目图片、画布状态保存在应用支持目录、不启动本地服务器，以及通过“带回对话”返回结构化选择。若宿主没有这项能力，回退到当前 Markdown、Mermaid、表格和对话内可视化，不弹出自建浏览器窗口。

## 2. 要解决的问题

当前 DIRcreative 已能生成和验证故事、镜头、动作面板、视觉资产、声音、模型单元与提示词，但用户调整仍分散在聊天和文件中：

- 想改一个动作面板时，需要重新描述镜头、状态、保留项和上游资产；
- 一张图的角色、场景、道具、材质和模型用途分布在不同台账；
- 18 个技术镜头与 30 个动作面板难以同时浏览；
- `needs_revision`、本地候选、平台绑定、真实生成和人类批准容易被混称；
- 细节审阅需要缩放、A/B、叠加、区域批注，内联卡片容纳不了；
- “更电影、更高级”这类宽泛指令无法直接转换成最小、可验证的修改合同；
- 文本去 AI、镜头、视觉、声音和 Seedance 编译分别有控制，但用户看不到它们如何相互影响。

## 3. 目标与非目标

### 3.1 目标

1. 用户在一个原生全屏工作区看到故事、镜头、面板、资产、声音和模型单元的同一份当前状态。
2. 用户能用“锁、改、比较、回退、验收”五种直观动作表达意图，不重述整个项目。
3. 每次修改自动显示影响范围、保留项、失效项、执行 owner、验证方式和回退点。
4. 支持高密度逐镜与动作阶段审阅，而不是一场一张粗关键帧。
5. 支持文本的两阶段审阅：先看 source-bound findings，再选择接受哪些修改。
6. 最大化 Seedance 2.5/2.0 的能力，同时保持权威剧本、资产主权和模型表面分离。
7. UI 中的状态与文件、工具回执一致；没有证据就显示未验证。
8. 保留现有 DIRcreative、ADCO、Jingzao、production ledger 和 Visual Workspace 的所有权边界，不增加第二控制器或第二账本。

### 3.2 非目标

- 面板不直接调用付费模型、上传平台、发布或发送内容。
- P0/P1 不提供多人客户门户、权限系统或长期评论服务。
- 不在面板内部实现完整 NLE、调色、混音或节点式生成器。
- 不把所有项目强制成固定镜头数、30 面板、同一画幅、同一风格或同一 provider。
- 不把 Visual Workspace 的画布状态当作项目真相源。
- 不因为用户拖动一个滑杆就立即改写全部下游文件。

## 4. 核心用户与任务

| 用户 | 主要任务 | 最需要看见的东西 |
| --- | --- | --- |
| 导演/创意负责人 | 调整故事、表演、镜头与整体风格 | 戏剧功能、信息推进、镜头关系、版本差异 |
| AI 视频制片 | 管理资产、模型单元、时长与返工 | 依赖、状态、成本影响、可重试单元 |
| 分镜/视觉开发 | 逐镜与动作阶段生产、检查连续性 | 同机位面板、轴线、视线、道具状态、主权参考 |
| 声音/表演负责人 | 调整对白力度、声线、停顿和 cue | 台词窗、角色意图、接收反应、声画因果 |
| 用户/客户 | 选方向、指出问题、确认可见结果 | 简洁预览、专业判断、后续影响、清楚的状态边界 |

## 5. 产品结构

### 5.1 左侧：项目导航与状态

固定层级：

```text
项目
├─ 参考片与方法
├─ 故事 / 剧本 / 对白
├─ 角色 / 场景 / 道具 / 材质
├─ 镜头
│  └─ 动作面板
├─ 声音
├─ Seedance 2.5 / 2.0 单元
├─ 生成候选与 QA
└─ 版本 / 拒绝 / 回退
```

每项显示一个便于扫描的主状态，同时保留 provenance、gate、QA、adoption、platform binding 和 publication 的关键 badges；主状态只是这些事实的摘要，不能覆盖它们。用户可筛选：

- 需要决定；
- 需要修改；
- 已有本地候选；
- 等待宿主/平台；
- 已生成待审；
- 已由人确认。

状态必须来自适配器读到的项目事实，不由 UI 自行推断。

### 5.2 中间：原生无限画布

画布根据任务切换视图，不做固定 dashboard：

| 视图 | 用途 | 默认内容 |
| --- | --- | --- |
| `project_overview` | 看项目整体 | 故事、资产、镜头、声音、模型单元依赖图 |
| `story_flow` | 看故事是否成立 | beat、场次、转折、不可逆选择、结尾回响 |
| `script_review` | 看对白与文本 | 原文、findings、VOICE PROFILE、改前/改后 |
| `shot_timeline` | 看镜头节奏 | timecode、景别、机位、动作、声音、风险 |
| `action_panels` | 看逐镜颗粒 | prepare/contact/change/consequence 状态与正反打 |
| `asset_graph` | 看资产主权 | identity、scene、prop、geometry、finish、clean input |
| `version_compare` | 看 A/B 差异 | 联动缩放、叠加、区域批注、版本来源 |
| `model_units` | 看生成计划 | SD2.5/2.0 单元、时长、槽位、首帧、音频、阻塞 |
| `generation_qa` | 看真实输出 | motion、身份、接触、材质、口型、声画、最小重试 |

用户可以自由摆放图片和分组，但这些布局只属于个人画布状态。项目文件中的镜头顺序、资产关系和版本状态不能被画布位置改写。

### 5.3 右侧：上下文检查器

选中任一故事节点、镜头、面板、资产或模型单元后显示：

- 当前版本和真实状态；
- 它在故事中的作用；
- 来源与主权：控制什么、不能控制什么；
- 必须保留；
- 允许改变；
- 当前阻塞与拒绝原因；
- 受影响的下游项目；
- 推荐的最小修改；
- 修改后要运行的检查；
- 上一个可回退版本。

普通界面隐藏 raw hash、receipt 和内部 schema；“查看技术证据”展开后才显示。

### 5.4 底部：对话与命令带

画布不替代聊天。底部保持当前 Codex 对话输入，并提供五个语义动作：

| 动作 | 用户看到的含义 | 输出 |
| --- | --- | --- |
| 锁 | 这部分继续沿用 | 一条 `preserve` 意图，控制器复核后才写当前状态 |
| 改 | 只改一个明确问题 | one-variable change request |
| 比较 | 并排看两个版本/方向 | comparison request，不改变项目 |
| 回退 | 返回已验证版本 | rollback proposal，控制器展示影响后执行 |
| 验收 | 按选定标准检查 | review request；不自动等于人类批准 |

“带回对话”返回结构化选择：对象 ID、版本、用户动作、选中批注和可见上下文。DIRcreative 收到后重新读取当前文件，拒绝 stale 版本，再输出自然语言确认和下一步。

## 6. 最重要的工作流

### 6.1 从参考片到原创项目前期

```text
参考片证据与时间码
-> 可迁移机制 / 禁止复制项
-> 原创创意核心
-> 权威剧本
-> 资产与动作台账
-> 逐镜/动作面板
-> Seedance 单元与提示词
-> 生成前准入
```

画布允许把参考片证据与原创资产并排查看，但不得用源片人物、画面或台词直接作为生成输入。每个迁移机制都要说明“源片为什么有效、原创项目如何用另一种内容实现”。

### 6.2 文本与对白调节

文档级文本遵循 v0.7.1 的两阶段 humanization：

1. 显示 architecture/venue、discourse、surface 三层 findings；每条绑定原文跨度、cluster 和 whitelist verdict。
2. 用户选择接受/拒绝 finding，选择 minimal refactor 或 recreate。
3. recreate 前显示 facts、claims、intent、dialogue 与 protected spans 基线。
4. VOICE PROFILE 或 venue samples 必须完成宿主读回；否则显示“等待来源确认”。
5. 修改后显示 protected-content diff、朗读检查和残余 cluster，不让 validator 再改一次稿。

文本面板不提供“去 AI 程度 100%”滑杆，也不提供 AI 作者概率。用户调的是：修改深度、目标场域、声音样本、接受哪些问题、最大结构变化。

### 6.3 逐镜与动作面板

每个技术镜头是一组，不是一张图。组内按实际动作显示：

- 人物走近 / 到位；
- 准备 / 接触 / 变化 / 结果；
- 说话者 / 听者反应；
- 视线对象变化；
- 道具状态转移；
- 机械对准 / 插入 / 松手 / 驱动；
- 因果终态。

同机位面板共享 camera setup、axis 和 lens；修改后一张默认只开放动作或状态变量。改变机位必须显式解除 camera lock，并显示哪些 continuity 检查会重新运行。

### 6.4 S07 场景/支撑真值排错

S07 是 P0 验收用例：动作可读、图片存在、哈希唯一，但悬挂铜钟被错误放在桌面上。面板必须同时显示：

- 预期场景：炉坊；
- 预期支撑：悬挂；
- 实际错误：生成水平支撑面；
- 参考主权：道具图只管钟，不得控制背景/地面；
- 当前状态：`needs_revision`、禁止模型上传；
- 影响：只阻塞两张面板与两个 Seedance 单元；
- 下一步：待用户授权后重生成，再做独立像素复核。

面板不得因为“手指接触阶段正确”把这两张图判为通过，也不得因此重置其余 28 张候选。

### 6.5 资产主权与白模/约束输入

资产节点显示两列：`可继承` 与 `禁止继承`。

| 资产 | 可继承 | 禁止继承 |
| --- | --- | --- |
| 角色母板 | 身份、年龄、体型、发型、服装结构 | 场景、动作、机位 |
| 场景母板 | 地理、固定物、通道、机位区 | 角色/道具身份、首帧动作 |
| 道具母板 | 形状、比例、关键结构、状态 | 背景、桌面、地面、光色 finish |
| 几何导板/白模 | geometry、scale、occlusion、support | 身份、材质、纹理、最终风格 |
| 状态图 | 某一动作阶段 | 全局 finish、其他阶段 |
| clean input | 当前模型单元的第一/末状态 | 联系表、标签、箭头、网格 |

UI 只有在空间、遮挡、比例或支撑风险高时才建议白模、深度、遮罩或局部约束；默认选最低充分控制，不强制 3D。

### 6.6 Seedance 2.5 / 2.0 模型单元

同一权威剧本在画布中显示两条模型路线：

- Seedance 2.5：允许较长连续单元和原生多镜关系；显示视觉基线、完整 asset/audio binding、对白容量和跨镜状态。
- Seedance 2.0：拆成更短单元控制漂移；优先保留接触、不可逆变化和终态。

用户可调：单元边界、包含镜头、请求时长上限、首帧/末帧、参考槽位、对白窗、动作与镜头复杂度。修改任一项后，面板必须显示哪些提示词和绑定会失效。

现成 Prompt 的局部修改保持 Fast；从剧本正式编译 Seedance 2.5 必须进入 Studio 并读完整方法包。面板不得把“可发现 mr-li provider”显示成“已实际使用”，直到 host 读取并采用其正文与 references。

### 6.7 声音与表演

声音视图与镜头共用同一时间轴：

- 精确台词与说话者；
- 入点、出点、停顿和重音；
- 听者反应；
- 环境、动作、设计音和音乐 stems；
- 唯一性规则，例如一次钟击；
- 临时 TTS / 正式声线 / 已审听的真实状态。

没有正式音频时显示“时序样本”，不能显示“声线已完成”。

## 7. 用户可调参数

控件必须绑定可见效果和下游影响，不提供空泛风格按钮。

| 类别 | 可调参数 | 不允许的简化 |
| --- | --- | --- |
| 故事 | 信息顺序、转折时点、不可逆选择、结尾回响 | “更高级” |
| 文本 | operation、finding selection、场域、VOICE PROFILE、结构改动上限 | “去 AI 100%” |
| 表演 | 目的、阻力、动作、停顿、眼神、声线 | 情绪形容词堆叠 |
| 镜头 | 景别、焦段、机位、轴线、运动、时长 | 只选“电影感” |
| 动作 | 阶段数量、接触点、状态变化、终态 | 每场固定一张/三张 |
| 视觉 | palette、contrast、softness、grain、material、optics | 固定 LUT/滤镜套用全片 |
| 资产 | 主权、reference role、inherits/forbidden、状态 | scene board 自动当首帧 |
| 声音 | dialogue window、cue、stem、进入/退出、响度目标 | 音乐铺满全片 |
| 模型 | target model、unit boundary、duration、slots、clean input | 一份通用 prompt 喂所有模型 |

所有滑杆默认只更新预览与修改草稿。提交时必须生成可读句子，例如：

> 只把 S09-P02 的视线向左下调整，保留人物身份、机位、钟的位置、服装和炉坊光色；改后只复核视线与 S09→S10 连续性。

## 8. 状态与所有权

### 8.1 正交状态向量

`workspace_snapshot` 不把所有事实塞进一个枚举。每个对象至少保留：

| 维度 | 示例值 | 负责回答 |
| --- | --- | --- |
| `artifact.lifecycle` | `planned / prompt_ready / generated_candidate / reused_candidate / missing / rejected` | 有没有实际对象，它处于什么资产阶段 |
| `provenance.status` | `unknown / local_hash_verified / tool_receipt_verified` | 来源和文件证据是否成立 |
| `gate.status` | `open / waiting / blocked / passed` | 当前动作能不能继续，为什么 |
| `qa.status` | `unreviewed / needs_revision / conditional / passed` | 指定范围的技术/视觉审查结论 |
| `adoption.status` | `unselected / agent_selected / user_locked / human_approved / rejected` | 谁选择或批准了它 |
| `platform_binding.status` | `unbound / bound` | 是否有真实平台 reference |
| `publication.status` | `unpublished / published` | 是否有外部发布回执 |

这些维度可以并存。例如一张真实生成图可以同时是：

```text
artifact.lifecycle = generated_candidate
provenance.status = tool_receipt_verified
gate.status = blocked
qa.status = needs_revision
adoption.status = rejected
platform_binding.status = unbound
publication.status = unpublished
```

左侧项目树可按优先级突出一个主状态：`blocked` > `needs_revision` > `waiting` > `generated pending review` > `adopted` > `planned`。检查器必须同时显示其它 badges 和证据，不能把摘要写回源文件。

### 8.2 现有 visual asset 状态 crosswalk

| 现有 `visual-asset-plan` 值 | 投影规则 | 不能自动推出 |
| --- | --- | --- |
| `planned` | lifecycle=`planned` | source valid、prompt ready |
| `prompt_ready` | lifecycle=`prompt_ready` | 已生成 |
| `generated_candidate` | lifecycle=`generated_candidate`; adoption=`unselected` | QA 通过、人类采用 |
| `user_locked` | adoption=`user_locked`; lifecycle/provenance 另从文件与 receipt 读取 | 客户批准、发布 |
| `reused_locked` | lifecycle=`reused_candidate`; adoption=`user_locked` | 当前文件仍有效，必须重新核 hash |
| `rejected` | lifecycle=`rejected`; qa=`needs_revision`; gate=`blocked` | 其它资产也应回退 |

`generated_file`、technical receipt 和文件 hash 决定 provenance；visual QA receipt 决定 QA；真实平台 ref 决定 platform binding；用户/客户确认与发布回执分别决定 human approval 和 publication。缺少对应证据时保留 `unknown/unbound/unpublished`。

UI 不允许一个维度自动升级另一个维度，也不把旧 schema 的 `user_locked` 扩张成通用 `human_approved`。

### 8.3 权威来源

| 数据 | Owner |
| --- | --- |
| 故事、镜头、资产、提示词与项目 QA | DIRcreative 项目文件 |
| 客户当前真相与采用 | ADCO（若存在） |
| Visual Workspace 节点位置、缩放、个人分组 | 宿主应用支持目录 |
| 外部 Skill 方法 | 当前实际读取的 host-installed provider |
| 真实媒体生成 | 具体工具回执与输出文件 |
| 人类批准 | 用户/客户明确确认 |

## 9. 数据适配与技术架构

### 9.1 不新增第二数据库

P0/P1 从现有项目合同读取：

- `creative-source` / 权威剧本；
- `shot-cards` / shot plan；
- `storyboard-coverage`；
- asset manifest / visual asset plan；
- selected panel index；
- production ledger；
- Seedance unit/bindings；
- dialogue timing / sound cues；
- QA、rejection、writeback receipts。

适配器将它们投影成统一只读 `workspace_snapshot`，不回写源文件。

### 9.2 建议的新合同

`dircreative.workspace-change-request@1.0`：

```yaml
request_id: change-001
snapshot_sha256: <current snapshot>
target:
  kind: panel
  id: S09-P02
  version_sha256: <selected version>
action: modify
must_preserve:
  - camera_setup
  - character_identity
  - scene_identity
may_change:
  - gaze_direction
requested_change: 视线向左下调整
expected_effect: 让接收反应更明确
affected_downstream:
  - S09 continuity
  - Seedance unit G25_02
validation:
  - source hash freshness
  - gaze target
  - S09 to S10 continuity
authority:
  component_write: false
  controller_revalidation_required: true
```

组件只产生这份意图。控制器验证 snapshot 与 target version 仍 current，随后才修改项目并返回 writeback。

### 9.3 复用现有可视化合同

- 对话内摘要继续使用 `dircreative.chat-visualization@1.0`；
- 高分辨率全屏审阅复用 image review 规划中的 hash-bound annotation；
- 画布与聊天之间传递对象 ID、版本和 action，不传私有临时 URL；
- 真实图片只读加载，缩略图与原图分离；
- 不把离线 HTML renderer 当作原生 Visual Workspace。

## 10. MVP 范围

### P0.1：snapshot 与状态 crosswalk

- 为现有 creative source、shot、coverage、asset、ledger、sound 和 model-unit 合同实现只读 adapters；
- 生成正交 `workspace_snapshot`；
- 验证 visual asset legacy crosswalk、S07 blocked 状态、stale 和缺证据回退；
- 不渲染 UI，不写项目。

### P0.2：全屏浏览与 selection roundtrip

- 从项目根读取现有合同与图片；
- 全屏显示项目树、18 镜/多动作面板时间线、资产关系与模型单元；
- 单图缩放、A/B 并排、状态/阻塞筛选；
- “带回对话”返回选中对象；
- Markdown fallback；
- 不写项目，不生成媒体。

验收用例：加载 60 秒回归项目，必须显示 28/30 可采用、S07 两帧 `needs_revision`、两个下游单元 blocked、`whole_film_visual_assets_complete=false`；检查器同时显示 S07 的 lifecycle、provenance、gate、QA、adoption、binding 与 publication，不允许主状态隐藏其它维度。

### P1：调节意图与可验证写回

- `锁/改/比较/回退/验收`；
- must-preserve/may-change 编辑器；
- stale snapshot 检测；
- 影响图和 one-variable request；
- 控制器执行后的 diff、validation 和确认回声。

### P2：专业图片与分镜审阅

- 联动/独立缩放；
- 叠加滑杆；
- 点、矩形、多边形批注；
- annotation 绑定 asset/version hash；
- 故事板网格、轴线/视线、连续性热图；
- 版本改变后旧批注自动 stale。

### P3：文本、Seedance 与声音

- humanization findings/acceptance/VOICE readback；
- Seedance 2.5/2.0 单元比较与 prompt diff；
- dialogue/sound 多轨时间线；
- 生成前容量与阻塞检查。

### P4：真实生成后回路

- 真实输出浏览；
- 运动/身份/接触/材质/口型/声音 QA；
- 最小重试；
- NLE/发布仍为外部系统。

## 11. 可用性与可访问性

- 默认请求 fullscreen；只有用户明确需要简版时使用 inline。
- 320 CSS px 回退视图不出现双向滚动；全屏画布保留缩放而非压缩文字。
- 键盘可完成选择、切换版本、打开检查器、带回对话和提交意图。
- 状态不用颜色单独表达；同时显示图标、文字和原因。
- 所有图像有可读 alt text；批注可从列表定位到区域。
- 动画尊重 reduced motion；时间轴移动不造成焦点丢失。
- 普通用户界面最小正文字号 14px；技术证据可折叠。
- 空状态说明缺少什么、为什么影响下一步、用户能做什么。

## 12. 性能与上下文

- 首屏只读项目索引与缩略图，不加载全部原图和 raw prompts。
- 联系表虚拟化；默认最多预取当前镜头前后各一组。
- 原图按需加载并缓存；画布状态不写入项目仓库。
- 适配器按内容哈希增量更新 snapshot。
- “带回对话”只发送选中对象、版本、批注摘要和必要依赖，不发送整个画布。
- 大项目按 scene/sequence 分区，但保留全局故事、角色和资产主权索引。

## 13. 安全与失败模式

| 失败 | 行为 |
| --- | --- |
| Visual Workspace 不可用 | 回退 Markdown/Mermaid/表格，不开 localhost |
| 项目路径未授权 | 使用宿主路径授权，不猜路径 |
| asset hash 改变 | 标记 stale，禁止提交旧选择 |
| 图片缺失/损坏 | 显示 missing，不用 placeholder 冒充 |
| component 试图写真相 | 拒绝，转为 conversation intent |
| 用户选择需要生成 | 返回对话，执行现有 generation authorization |
| provider 可发现但未读 | 显示“可用”，不显示“已采用” |
| sampled calibration 未完成宿主读回 | 显示 `waiting_for_host_readback`，不授予文本改写权 |
| 平台 ref 缺失 | 显示未绑定 |
| QA 与人类意见冲突 | 同时显示；人类决定不改写技术事实 |
| 上游版本变化 | 列出 stale downstream，等待重新编译 |

## 14. 成功指标

### 体验

- 用户从打开项目到定位目标镜头不超过 30 秒；
- 80% 的局部修改可用五种短动作完成，无需重述项目；
- 一次操作最多需要一个实质性确认问题；
- 用户能正确区分本地候选、已生成和已批准。

### 质量

- S07 桌面污染在 P0 中 100% 可见且保持 blocked；
- 任一 panel 的场景、支撑、身份、状态与下游单元可在三次点击内追溯；
- 修改后 stale 依赖漏报率为 0；
- 任何 UI 选择都不能绕过 generation、acceptance 或 publication gate。

### 工程

- 不启动 localhost server；
- 不新增项目内第二数据库；
- P0 打开 30 面板项目首个可交互画面小于 2 秒（本地 SSD 基准）；
- 1,000 面板项目仍能虚拟化浏览；
- schema、fallback、键盘、reflow、stale、路径与 hash 负向测试进入 CI。

## 15. 发布门与验收矩阵

| Gate | 必须证明 | 不能证明 |
| --- | --- | --- |
| schema | snapshot/change request 结构有效 | 用户看得懂 |
| renderer | 数据能显示、交互 payload 正确 | 项目已写回 |
| host display receipt | fullscreen 实际挂载 | 内容质量通过 |
| controller writeback | 当前版本经过验证并写入 | 人类批准 |
| visual QA | 指定图像范围通过 | 成片通过 |
| live user test | 用户能找到、比较、调整、回退 | 外部发布 |

P0 完成条件不是“页面能打开”，而是用户能在真实 60 秒项目上完成：找到 S07、理解为什么失败、比较两个版本、带回一个最小修正意图，并确认其他 28 张图不会被回退。

## 16. 开发前仍需确认的研究问题

1. `open_visual_workspace` 的可调用工具是否会在 DIRcreative 运行环境稳定暴露；若没有，P0 只能保持 PRD/数据适配层。
2. “带回对话”的 structured context 字段和大小上限，需要用真实宿主回执固定。
3. 原图授权、缩略图缓存和 project/worktree 同源复用边界，需要宿主实现说明。
4. Visual Workspace 是否支持版本联动缩放、overlay 和区域批注；缺失部分应由同一原生组件扩展，还是交给独立 fullscreen review app。
5. ADCO worker 模式下，谁负责把 DIR 的中立 snapshot 挂载到客户窗口，仍需双边 UI capability negotiation。

## 17. 推荐实施顺序

1. 先做只读 adapter + S07 truth fixture + fullscreen project tree。
2. 再做 selection roundtrip 和 stale 检测。
3. 再做 change request，不直接写项目。
4. 写回闭环稳定后才做 A/B/annotation。
5. 最后加入 humanization、Seedance 和生成后 QA。

每阶段都先在 60 秒真实项目与一个完全不同的广告 fixture 上测试，避免面板过拟合《最后一炉》或叙事短片。

## 18. 参考与复用

- [`chat-inline-visualization-interface.md`](chat-inline-visualization-interface.md)
- [`chat-inline-visualization-v2-ux-plan.md`](chat-inline-visualization-v2-ux-plan.md)
- [`image-review-visualization-integration-plan.md`](image-review-visualization-integration-plan.md)
- [`workbench-product-spec.md`](workbench-product-spec.md)
- [`runtime-state-governance.md`](runtime-state-governance.md)
- [`humanization-workflow.md`](../../skills/dircreative/references/humanization-workflow.md)
- [`storyboard-coverage.md`](../../skills/dircreative/references/storyboard-coverage.md)
- [`storyboard-frame-to-jingzao.md`](../../skills/dircreative/references/storyboard-frame-to-jingzao.md)
- [`script-to-seedance.md`](../../skills/dircreative/references/script-to-seedance.md)
- Visual Workspace host capability contract, verified 2026-09-04

这些资料继续各自负责现有合同。本 PRD 只定义产品组合与后续开发顺序，不复制 renderer、schema、ledger 或 gate。
