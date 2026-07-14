# DIRcreative 对话内可视化 V2：体验审计与执行计划

Status: P0 implemented and regression-gated; P1 fullscreen inspection remains planned; final user acceptance pending

Date: 2026-07-14

Related implementation track: `image-review-visualization-integration-plan.md` covers real-image intake, candidate review, fullscreen inspection, annotations, storyboard/animatic review, and persistent collaboration boundaries.

## 结论

早期 V1 不能以“浏览器审计通过”判定完成。当前 P0 已把选择同步、图形语义、真实 PNG 候选、无媒体回退、演示素材边界、320 px 中文排版和大字号检查加入自动门禁；P1 的全屏缩放、叠加和区域批注仍是后续范围。

V2 不应继续增加一张固定的大面板。正确方向是建立一套由当前创作问题驱动的“可视化语法”：先判断用户现在需要理解的是选择、节奏、关系、连续性、素材还是差异，再只调用最小但足够丰富的视图。每个视图都必须进入同一条对话状态链：

```text
一个关键问题
-> 对应的可视化证据
-> 本地探索选择
-> 选择对应的动态专业判断与影响
-> 明确提交
-> 聊天中的确认回声
-> 下一个创作视图
```

V2 的首批重点不是把 12 个旧页面全部装饰得更复杂，而是优先完成五种代表性能力：动态方案比较、多曲线故事引擎、多轨镜头节奏、真实关系图、A/B 差异检查。它们通过后，再迁移其余阶段。

## 当前实现状态（2026-07-14）

- 已实现动态方案比较，并分离“当前查看”和“初始推荐”；
- 已实现情绪、钩子/注意力、品牌存在感多曲线故事视图；
- 已实现镜头、景别、运动、动作、声音、风险多轨时间线；
- 已实现参考素材与镜头的真实节点关系图；
- 已实现无真实媒体时的结构化 A/B QA 差异视图；
- 已实现真实 PNG 候选预览、证据绑定、项目根路径约束、演示素材 fail-closed 路由和图片体积/像素上限；
- 已实现色板、光线、材质、镜头语言、允许项与避开项视觉方向板；
- 浏览器审计扩展到每页 6 个场景：736/320 light、736/320 dark、320 强制文本间距、736 大字号；
- 当前共 14 页、84 个场景纳入自动检查，并对代表性最坏场景进行截图人工复核；
- 仍未满足最终完成条件：需要用户在当前会话实际操作并确认验收。

## 本轮证据与失败复盘

### 已确认的问题

1. 第一版方向选择把标题、解释、优缺点同时塞进三个按钮，中文文本在窄屏内堆叠，选择器承担了过多阅读任务。
2. 用户从“情感回响”切换到“视觉冲击”后，下方仍显示“优先选择情感回响”。选择状态和专业判断使用了两套不同的数据源。
3. 当前通用 renderer 仍可能重现相同问题：选项详情会更新，但全局 `recommendation.reason` 是静态输出。
4. 当前 browser audit 只点击第二个选项并检查少量字段，没有遍历全部选择，也没有检查专业判断、下游影响、按钮文案和提交 payload 是否同步。
5. 现有 12 个 dogfood 页面通过了 36 项自动检查，但截图人工复核显示：
   - “故事节拍带”没有情绪曲线或钩子曲线；
   - “镜头密度时间线”只是通用时间块；
   - “参考素材关系图”实际是表格；
   - “QA 差异比较”只有文本行，没有并排、叠加或差异标记；
   - “视觉方向板”只有文字，没有色彩、光线、材质、镜头语言或真实媒体预览。

因此，V1 的绿色结果只能表述为“基础 DOM 与尺寸检查通过”，不能表述为“UI/UX 已完成”。

### 已经有价值的基础

- 12 个创作阶段已有入口映射；
- spec、renderer、positive/negative fixtures、browser audit 和 writeback 已形成基本链路；
- 已区分组件本地选择、聊天提交与项目权威写入；
- 已规定客户界面不得暴露 hash、receipt、gate、项目写回等后台术语；
- 当前比较视图使用“短选项 + 单一动态详情区”的结构，适合作为 V2 基线。

## 研究转化为设计约束

### Codex / ChatGPT Visualizations

[OpenAI Visualizations](https://learn.chatgpt.com/docs/visualizations) 将可视化覆盖到图表、地图、图解、计算器、模拟器和交互式解释器，并建议选择能够解决当前问题的最小格式。它还明确强调轴、单位、数据摘要、键盘操作、可见焦点、非颜色编码和减少动态效果。

对 DIRcreative 的直接含义：

- 曲线不是装饰，必须回答一个明确问题，例如“前三秒是否形成注意力峰值”；
- 图形必须提供文字摘要和来源绑定；
- 对话内可视化是当前创作状态的快照，不伪装成持续同步的项目 dashboard；
- 用户可以在同一对话继续要求修改曲线、标签、对比项和注释。

### 创作产品模式

- [Boords Storyboard Views](https://boords.com/docs/storyboard-views) 和 [Boords Animatics](https://boords.com/docs/animatics) 把全局浏览、镜头列表、单帧编辑、时间与音频检查拆为不同视图。DIRcreative 也应让“看故事”“看节奏”“看镜头”使用不同语法。
- [Frame.io Comparison Viewer](https://help.frame.io/en/articles/9952618-comparison-viewer) 的并排、联动缩放、叠加滑杆和像素差异说明：有真实媒体时，QA 不应退化为文本表格。
- [Runway Workflows](https://help.runwayml.com/hc/en-us/articles/45763528999699-Introduction-to-Workflows) 展示节点、连接、输入输出和执行历史；发布为 App 时又隐藏内部设置。DIRcreative 应保留关系和影响，但把内部协议从客户视图隐藏。
- [Figma Interactive Components](https://help.figma.com/hc/en-us/articles/39747190144023-Components-collection-Interactive-components-fundamentals) 与 [Variables in prototypes](https://help.figma.com/hc/en-us/articles/14506587589399-Use-variables-in-prototypes) 说明一个选择状态应驱动所有绑定内容更新。DIRcreative 不能再让“当前选择”和“导演建议”各自维护状态。

### 可访问与响应式约束

- [WCAG 2.2 Reflow](https://www.w3.org/TR/WCAG22/#reflow) 要求 320 CSS px 宽度下不丢失信息或功能、不产生双向滚动。
- [WAI-ARIA Radio Group](https://www.w3.org/WAI/ARIA/apg/patterns/radio/) 要求选择组拥有明确标签、可用方向键切换，并同步选中状态。
- [MDN aria-live](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live) 说明动态详情与判断更新需要以适当方式通知辅助技术。
- [WCAG Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum) 的 AA 最小目标是 24 × 24 CSS px；本项目面向对话选择，内部设计目标采用不小于 44 px 的主操作高度。

## 能力缺口矩阵

| 用户问题 | V1 名称/承诺 | 当前实现 | V2 要达到的状态 | 优先级 |
| --- | --- | --- | --- | --- |
| 哪个创意方向更适合？ | 方案比较 | 动态详情 + 静态全局建议 | 所有判断、风险、影响、CTA、payload 由同一 selected state 派生 | P0 |
| 故事什么时候抓住人、何时回落？ | 节拍带或情绪曲线 | 四段节拍 ribbon | 情绪、钩子/注意力、张力、品牌露出等多序列曲线，带时间轴和节拍注释 | P0 |
| 镜头是否太碎、太慢或难拍？ | 镜头密度时间线 | 通用时间块 | 时长、景别、运动、动作、声音、风险的同步多轨时间线 | P0 |
| 素材如何影响镜头和后续生成？ | 参考素材关系图 | 表格 | 可读的节点/边/角色图，支持高亮一个资产的影响范围 | P0 |
| 两版生成结果究竟差在哪里？ | QA 差异比较 | 文本 pass/fail 行 | 有媒体时并排/叠加/差异检查；无媒体时用维度化 delta，不伪造图像 | P0 |
| 视觉方向长什么样？ | 视觉方向板 | 文字详情 | 色板、光线、材质、镜头语言、禁用项；有来源时显示真实参考缩略图 | P1 |
| 哪些连续性要锁住？ | 视觉锁定矩阵 | 文本表格 | 角色/环境/道具/服装/光线/材质矩阵 + 漂移风险与依赖 | P1 |
| 脚本时间如何分配？ | 时间带 | 粗粒度 timing bars | VO/对白/静默/产品/声音时间预算、重叠与超时警告 | P1 |
| 修改这一项会影响什么？ | 下游影响文字 | 单行描述 | 变更影响图：保留、需复核、失效，面向创作语言 | P1 |
| 当前知道和不知道什么？ | Brief map | 事实列表 | 已知/推断/待确认三类信息地图，禁止把未知值画成曲线 | P1 |
| 不支持图形时怎么办？ | Markdown fallback | 已有通用 fallback | 与图形包含相同事实、结论和一个问题；曲线附数据表/摘要 | P0 |

## 可视化选择路由

renderer 不再只按 stage gate 硬编码图形。先使用以下输入选择视图：

```text
当前阶段 + 用户此刻的问题 + 可用数据形态 + 信息规模 + 是否有真实媒体
-> visual_question
-> visualization_kind
-> inline / fullscreen / fallback
```

| visual_question | 数据形态 | 首选视图 | 降级 |
| --- | --- | --- | --- |
| 选哪个 | 2–3 个离散方案 | comparison | 短表格 + 当前判断 |
| 什么时候升降 | 时间序列 | curve / bands | 数据表 + 峰谷摘要 |
| 哪些元素相关 | 节点与边 | graph | 邻接清单 / Mermaid |
| 哪些维度一致 | 二维分类 | matrix | 分组表格 |
| 两个结果差多少 | 两个媒体或维度向量 | compare / delta | 维度化 delta 表 |
| 改动影响哪里 | 有向依赖 | impact map | 保留/复核/失效清单 |
| 目前缺什么 | 已知、推断、未知 | alignment map | 三段摘要 |

路由必须 fail closed：缺少时间值时不能生成伪精确曲线；缺少媒体时不能画假的 A/B 图；数据不足时明确显示“待确认”。

## V2 组件目录

### 1. 动态方案比较器 `decision_comparison`

- 输入：2–3 个方案；每个方案独立拥有摘要、优势、风险、适用条件、专业判断、下游影响、主操作文案。
- 交互：短标签 radio/tabs；键盘切换；一个详情区更新；提交前可反复预览。
- 规则：`selected_option_id` 是唯一选择源，所有可变文本从该 id 派生；“系统推荐”是独立徽标，不能覆盖“当前正在查看”。
- 典型视图：导演概念、视觉方向、模型路线。
- 完成条件：遍历每个选项时，标题、摘要、风险、判断、影响、CTA、follow-up payload 全部匹配且无上一个选项残留。

### 2. 多曲线故事引擎 `story_curve`

- 可用序列：
  - 情绪强度；
  - 钩子/注意力；
  - 张力与释放；
  - 品牌/产品存在感；
  - 信息密度。
- 默认最多同时显示 2–3 条与当前问题有关的曲线，避免“五彩心电图”。用户可切换其他序列。
- X 轴：秒数或故事百分比；Y 轴：明确标注为相对强度或来源数据单位。
- 注释：开场钩子、转折、证据、品牌出现、高潮、结尾记忆点。
- 图下必须有一句直接判断，例如“注意力在 3–6 秒回落，而产品直到 11 秒才出现”。
- 数据边界：数值必须来自已确认节拍、脚本时码或明确标为“创作推演”；不得将模型猜测包装成观众测试结果。

### 3. 多轨镜头节奏 `shot_rhythm_timeline`

- 共享时间轴：每条镜头的起止、时长和切点。
- 轨道：景别、机位/运动、主体动作、VO/对白/音乐/音效、制作风险。
- 可视提示：过密切换、长时间无变化、声音冲突、关键产品镜头不足。
- 移动端：按镜头纵向堆叠，每个镜头仍保持相同字段顺序；不横向压缩到不可读。
- 大于 30 镜头：inline 只显示总体节奏摘要和问题区间，详细时间线请求 fullscreen。

### 4. 视觉方向板 `visual_direction_board`

- 结构：色板、光比/光向、材质、镜头焦段/景深/运动语言、允许项、禁用项。
- 有真实来源图时：显示有来源标识的缩略图和角色；无图时只显示色块、图例与文字，不生成假 moodboard。
- 交互：选择方向后，板内全部属性和专业判断同步；可请求混合两个方向。

### 5. 连续性矩阵 `continuity_matrix`

- 行：角色、环境、道具、服装、光线、材质、品牌元素。
- 列：镜头/场景/生成批次。
- 单元格：确认、待确认、冲突、允许变化；不能只靠颜色表达。
- 选中冲突后显示“为什么冲突、影响哪些镜头、最小修复是什么”。

### 6. 参考资产关系图 `asset_dependency_graph`

- 节点：参考图、角色、场景、镜头、prompt/生成任务。
- 边：仅策划参考、直接输入、继承、禁止继承。
- 交互：选择节点后高亮一跳影响范围，并显示客户语言摘要。
- 规模控制：inline 只显示与当前决定相关的子图；完整图使用 fullscreen；纯层级关系优先 Mermaid。

### 7. A/B 与差异检查 `qa_comparison`

- 有真实媒体：并排、联动查看；条件允许时提供叠加滑杆或差异视图。
- 无媒体：按构图、身份、环境、材质、动作、光线、品牌、技术瑕疵显示明确 delta，不渲染空假框。
- 每一维给出：A、B、锁定要求、结论、最小重试动作。
- 默认只突出阻塞项，其余维度可展开。

### 8. 变更影响图 `change_impact_map`

- 用户修改故事、脚本、镜头、视觉或参考资产时显示。
- 三种结果：继续沿用、需要复核、必须重做。
- 用户界面只用创作对象名称，不显示 stale marker、artifact id 或锁记录。

### 9. 对齐地图与确认回声

- 对齐地图：已知、合理推断、待确认；一次只问一个真正阻塞的问题。
- 确认回声：复述用户选择、真实记录状态、专业判断、保留项、下一步；不含按钮，不伪造完成。

## 对话与状态模型

### 状态机

| 状态 | 用户看到什么 | 可做什么 | 禁止 |
| --- | --- | --- | --- |
| `asking` | 一个关键问题和必要上下文 | 回答 | 同时抛出多项审批 |
| `exploring` | 可视化与短选择器 | 本地切换、展开、比较 | 选择即写入项目 |
| `staged` | 当前选择对应的判断与影响 | 提交、修改、取消 | 保留旧选项判断 |
| `submitting` | 明确的处理状态 | 等待或取消（如支持） | 重复提交 |
| `confirmed` | 聊天确认回声与下一步 | 进入下一轮 | 把组件状态当权威完成 |
| `blocked` | 一个客户可理解的冲突 | 修正该冲突 | 展示协议/路径/堆栈 |

### 单一状态派生规则

所有动态字段由一个 state selector 产生：

```text
selected_option_id
-> selected option record
-> title + summary + strengths + risks + judgment
   + downstream impact + CTA + follow-up payload
```

推荐项只作为 option record 的元数据：

```text
recommended_option_id != selected_option_id
```

此时应同时显示：

- “当前查看：视觉冲击”；
- “专业建议：情感回响（原因……）”；
- “如果采用视觉冲击：代价与补救……”。

不能把推荐项的说明冒充当前项的说明，也不能因为用户预览了其他方案就悄悄改掉系统推荐。

### 动态通知

- 当前详情区域使用 `aria-live="polite"` 或 `role="status"`，只播报有意义的选择结果；
- 不在每次 hover 时播报整张卡片；
- 提交、错误和完成状态拥有独立的可访问文本；
- loading 不覆盖当前选择，也不导致布局跳动。

## UI/UX 规则

### 信息层级

1. 现在要决定什么。
2. 判断所需的视觉证据。
3. 当前选择对应的专业判断和取舍。
4. 这个选择会改变什么。
5. 一个主操作，最多一个次操作。

### 中文排版与密度

- 选择器只放 2–8 个汉字的短标签；完整解释只出现在一个动态详情区。
- 正文行高不低于 1.45；小字只用于非关键补充，关键风险和判断不可使用弱对比灰字。
- 不用强制单行或固定卡片高度承载可变中文文本。
- 320 px 时优先单列；不把三列卡片硬压成窄栏。
- 736 px 可使用并列布局，但每个选择仍应可独立点击且文字不拥挤。
- 图表直接标注关键线/点；图例不要求用户在颜色间来回匹配。

### 交互

- 选方案使用原生 radio 或符合 APG 的 radio/tab 模式；方向键可切换，焦点清晰。
- 所有主操作目标高度不小于 44 px；相邻点击目标保持清楚间距。
- 不使用 hover 才能获得的关键信息。
- 不使用组件内嵌套滚动；超出 inline 能力时切换 fullscreen 或摘要。
- 动画只帮助理解状态变化，并尊重 `prefers-reduced-motion`。

### 视觉表达

- 信息丰富来自曲线、关系、时间、差异和真实媒体，不来自永久增加更多面板。
- 一个图只回答一个主要问题；同图最多 2–3 条默认曲线。
- 颜色必须同时配合文字、线型、形状或图案。
- 图中必须注明轴、单位、数据性质和缺失值。
- 若数据是“创作推演”，明确标注；若来自脚本/shot list，绑定具体来源；若未知，显示待确认。

## Spec 与 renderer 改造

### Schema V2

将 `view.intent` 扩展为明确的数据语义，而不是仅靠 gate 猜测：

```yaml
view:
  question: choose | change_over_time | relationship | consistency | delta | impact | missing
  visualization_kind: comparison | curve | bands | timeline | graph | matrix | media_compare | alignment

data:
  axes: []
  series: []
  nodes: []
  edges: []
  matrix: null
  media: []
  annotations: []

state:
  selected_option_id: null
  recommended_option_id: null
  dynamic_bindings: []

accessibility:
  summary: ""
  data_table: []
  reduced_motion: true
```

约束：

- series 必须声明 label、unit、source_kind 和 source_ref；
- source_kind 仅允许 `artifact | confirmed_user_input | creative_projection`；
- `creative_projection` 必须在界面显式标注；
- graph 的所有边必须引用存在的节点；
- media_compare 必须引用真实可用媒体，否则使用 delta；
- 每个动态字段必须声明依赖的 state key；
- fallback 必须包含与主视图相同的关键事实和结论。

### Renderer 架构

```text
validated spec
-> question router
-> view model builder
-> visualization renderer
-> shared interaction state
-> accessibility summary/table
-> follow-up intent builder
```

共享层负责：主题、排版、选择状态、focus、aria-live、按钮、错误、发送和 fallback。每种图形 renderer 只负责其数据语法，不能各自维护一份 recommendation 逻辑。

### 渐进式发布

V1 schema 暂时只读兼容；V2 renderer 通过 `spec_version` 分流。V2 未覆盖的旧阶段继续使用安全的 V1 文本/表格 fallback，不能一次性大爆炸替换。

## 验证与回归门禁

### 1. 契约层

- schema 正/反例；
- 缺轴、缺单位、悬空节点、伪媒体、未绑定动态字段必须失败；
- 未知数据被填为精确数值必须失败或显式标为 creative projection。

### 2. 动态语义层（P0）

对每个选择逐一遍历并建立快照：

- selected name；
- summary；
- strength；
- risk/tradeoff；
- professional judgment；
- downstream impact；
- CTA；
- follow-up payload。

每个值必须与该 option fixture 对应；切换后 DOM 中不得残留上一选项的唯一文本。系统推荐与当前选择分别断言。

### 3. 可视化正确性层

- 曲线的点数、顺序、范围、轴、单位、标签、注释与输入一致；
- timeline 的镜头起止、总时长与轨道位置一致；
- graph 节点边数量、引用和高亮邻域一致；
- matrix 行列和状态完整；
- QA 媒体存在性和 delta 结论一致；
- 所有图都有可访问摘要或数据表。

### 4. 布局与可读性层

测试矩阵：

| 宽度 | 主题 | 文本条件 | 必测 |
| --- | --- | --- | --- |
| 320 | light/dark | 默认、最长中文 | overflow、重叠、裁切、按钮换行 |
| 736 | light/dark | 默认、最长中文 | 信息层级、并列布局、详情更新 |
| 320/736 | light/dark | 200% zoom / 增大文本间距 | reflow、焦点可见、功能不丢失 |

加入几何检查：相交 bounding boxes、文本超出容器、固定高度裁切、内部滚动、点击目标尺寸。关键 fixture 保留截图用于人工复核。

### 5. 键盘与状态层

- Tab 进入选择组；方向键切换；Space/Enter 激活；
- focus 不丢失、不被遮挡；
- `aria-checked`/`aria-selected` 与视觉状态一致；
- 动态区域产生正确 live-region 更新；
- loading、disabled、send failure、retry、double-submit 均有状态测试。

### 6. 内容与对话层

- 一张 inline surface 只要求一个主要决定；
- 不出现 code、hash、artifact、gate、receipt、项目写回、新建锁等后台词；
- 当前选择、专业建议、选择代价三者语义不混淆；
- 提交 payload 使用人类可读句子，并准确包含当前选择与动作；
- 确认回声来自验证后的 writeback，而不是点击后的乐观假完成。

### 7. 真实会话验收

自动测试通过后，在当前 Codex 会话依次打开五个代表性 surface：

1. 三方案动态比较；
2. 情绪 + 钩子 + 品牌出现的故事曲线；
3. 多轨镜头节奏；
4. 参考资产关系图；
5. A/B 或无媒体 delta QA。

用户逐项验证：看得懂、字不挤、选择后所有判断同步、图形确实帮助决定、提交后聊天能收到正确意图。没有这一步，不标记“已完成”。

## 分阶段执行计划

### Phase 0：冻结 V1 完成声明与建立失败样本

- 将本次拥挤截图和静态建议问题固化为回归 fixture；
- 给现有 audit 增加“全部选项 + recommendation/current selection 分离”断言；
- 文档与测试输出明确区分 `DOM_PASS`、`SEMANTIC_PASS`、`UX_REVIEW_PASS`。

Done：旧 bug 在修改前能够稳定复现并使新测试失败。

### Phase 1：统一动态状态与比较器

- 删除 renderer 中独立的静态 recommendation 输出路径；
- 建立 shared view model 和唯一 selected state；
- 完成 radio keyboard、aria-live、错误与 payload 测试；
- 修复 320/736 中文排版。

Done：三方案全部动态字段一致；旧 bug fixture 通过；当前会话人工验收通过。

### Phase 2：故事曲线与脚本时间

- 扩展 series/axes/annotations schema；
- 实现 SVG 多曲线、直接标签、文字摘要、数据表 fallback；
- 加入情绪、钩子/注意力、张力、品牌出现、信息密度；
- 实现脚本 timing bands。

Done：同一故事可在当前会话切换 2–3 条曲线，所有数据有来源/性质说明，移动端可读。

### Phase 3：镜头时间线、关系图与矩阵

- 实现 shot multi-track timeline；
- 实现 asset dependency graph；
- 实现 continuity matrix 和 impact map；
- 明确 inline/fullscreen 阈值。

Done：图名与实际表达一致；复杂数据可安全降级；30+ 镜头不被硬塞入 inline。

### Phase 4：视觉板与 QA 媒体比较

- 实现色板、光线、材质和镜头语言；
- 有媒体时提供并排与可选叠加；无媒体时提供 delta；
- 加入资源缺失、坏链接和大图性能降级。

Done：不伪造媒体；A/B 的结论可追溯到可见证据；阻塞差异能触发最小重试意图。

### Phase 5：迁移 12 个阶段与 cold review

- 使用 router 重新映射全部阶段；
- 为每类视图补正/反例、布局、键盘、语义和截图门禁；
- 运行独立 cold review；
- 在当前对话完成代表性用户验收。

Done：测试、截图人工复核、cold review 和用户实际验收全部有证据；之后才能把目标标为完成。

## 完成定义

只有同时满足以下条件，才能说“这套可视化优化完成”：

1. 本次两个已知回归（中文拥挤、静态建议）有失败样本和自动测试；
2. 五种 P0 代表性视图实现，不再用表格冒充曲线、图或 QA 比较；
3. 所有动态内容共享一个选择状态并遍历验证；
4. 320/736、light/dark、长中文、放大文本、键盘和 reduced motion 通过；
5. 曲线/图/矩阵/QA 的数据和视觉正确性通过；
6. 真实当前会话中能打开并操作代表性视图；
7. 用户实际确认可读、同步且有助于做决定；
8. 未经用户验收，状态只能是“实现待验收”，不能是“完成”。

## 范围边界

- V2 不把 inline surface 做成永久项目管理器或剪辑软件。
- V2 不允许组件直接写项目真相、锁定资产或授权生成。
- V2 不为“看起来丰富”而伪造曲线、评分、媒体或观众研究。
- V2 不在第一阶段引入新的前端框架或第三方运行时；优先扩展现有无依赖 renderer。
- 本计划不授权 commit、push、发布、安装或外部写入。
