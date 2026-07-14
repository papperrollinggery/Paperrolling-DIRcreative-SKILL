# DIRcreative 图片审阅与可视化集成规划

Status: research-backed implementation plan

Date: 2026-07-14

## 结论

DIRcreative 可以把真实图片放进对话中的交互界面进行审阅，但不应把所有审阅能力都塞进一张内联卡片。推荐采用三层体验：

1. **对话内快速审阅**：2–4 个候选缩略图、当前专业判断、关键差异、一个用户决定。
2. **全屏精细审阅**：高分辨率缩放和平移、并排/叠加/滑杆对比、区域批注、版本差异。
3. **持久化审阅应用**：多人评论、权限、版本历史、活动记录、长期保存和分享。

模型负责理解图片和形成结构化判断；可视化负责让用户看懂、比较和表达决定；DIRcreative 控制器负责校验当前版本并写入权威 QA、修订或确认记录。三者不能互相替代。

## 官方能力与边界

### ChatGPT Visualizations

官方将 Visualizations 定义为对话内的图表、地图、关系图、计算器、模拟器和交互式解释器。它适合可调输入、时间变化、空间关系和比较；默认应选择足够解决问题的最小界面。可视化通常是创建时信息的快照，不是持续同步的项目仪表盘。需要可重访、可分享、权限或持久数据时，应使用 Site。

Source: https://learn.chatgpt.com/docs/visualizations

### 图片理解

视觉模型可以分析图片中的对象、形状、颜色、纹理和文字。API 可通过 URL、Base64 data URL 或 Files API file ID 输入一张或多张图片。多图审阅因此可以先形成结构化 QA，再渲染对比界面；图片越多、细节越高，token 和处理成本越高。

Source: https://developers.openai.com/api/docs/guides/images-vision

### 对话组件与全屏组件

官方 Apps SDK 指南把内联卡片限定为单一动作或决定、少量结构化数据和简单直接编辑；建议最多两个主要动作，不做深层导航、多个视图或嵌套滚动。富媒体、复杂图、编辑画布和多步探索应进入全屏，并继续保留对话输入。

Sources:

- https://developers.openai.com/apps-sdk/concepts/ui-guidelines#inline-card
- https://developers.openai.com/apps-sdk/concepts/ui-guidelines#fullscreen

### 图片文件与组件状态

Apps SDK 组件可以上传文件、从可用的 ChatGPT 文件库选择文件、取得临时下载 URL，并协商 inline、PiP 或 fullscreen 模式。组件状态、服务端权威状态和对话消息必须分开：选中项、缩放位置和草拟批注可留在组件；QA 结论、版本、确认和修订记录必须由控制器写入权威数据。

Sources:

- https://developers.openai.com/apps-sdk/build/chatgpt-ui#upload-files-from-the-widget-chatgpt-extension
- https://developers.openai.com/apps-sdk/build/chatgpt-ui#request-alternate-layouts-chatgpt-extension
- https://developers.openai.com/apps-sdk/plan/components#define-the-state-contract

## 外部成熟模式

### Frame.io：精确版本比较

Frame.io 的静态素材对比包含并排查看、联动/独立缩放和平移、叠加滑杆、像素差异和明确绑定到左/右资产的评论。对 DIRcreative 最有价值的原则是：

- 两个版本必须明确标识，评论不能失去归属；
- 同尺寸图片才允许像素级叠加；
- 缩放既要支持联动，也要允许解除联动；
- 差异图是证据层，不能替代语义和创意判断。

Source: https://help.frame.io/en/articles/9952618-comparison-viewer

### Boords：故事板、单帧和时序审阅分层

Boords 将审阅拆成全局/网格视图、单帧编辑器、Animatic 时间线和客户分享视图。全局视图用于扫描镜头顺序；单帧视图用于绘制、形状、文字、运动方向和评论；Animatic 用帧时长、音频波形和字幕检查节奏；分享视图提供版本、状态、评论、权限和签核记录。

Sources:

- https://boords.com/docs/storyboard-views
- https://boords.com/docs/animatics
- https://boords.com/docs/sharing-links

### OpenAI 示例与社区经验

官方 Apps SDK 示例已经覆盖列表、轮播、地图、相册、视频、全屏和 host state 同步，可作为图库、镜头浏览和全屏审阅的实现参考。社区对新可视化的共同反馈是：真正有价值的不是“生成一张图”，而是继续追问、调整过滤或比较，并且不要盲信第一版可视化。这些社区反馈只作为使用线索，不作为能力边界依据。

Sources:

- https://github.com/openai/openai-apps-sdk-examples
- https://www.reddit.com/r/promptingmagic/comments/1u4txyw/chatgpt_interactive_charts_and_dashboards_have/

## 可视化能力目录

| 能力 | DIRcreative 用途 | 推荐界面 |
| --- | --- | --- |
| 多序列曲线 | 情绪、钩子、品牌存在、认知负荷、声音能量 | 内联 |
| 时间带/节奏轨道 | 剧本时长、镜头节奏、动作、摄影机、声音、风险 | 内联或全屏 |
| 对比矩阵 | 概念、视觉方向、模型路线、候选图 QA | 内联 |
| 素材关系图 | 身份、场景、道具、镜头和模型输入依赖 | 内联或全屏 |
| 连续性热图 | 角色、服装、场景、光线、道具跨镜头漂移 | 全屏 |
| 图片联系表 | 扫描候选、故事板帧、参考素材包 | 内联摘要或全屏 |
| A/B 并排 | 两个候选或两个版本的构图和语义比较 | 内联或全屏 |
| 叠加滑杆 | 相同尺寸版本的构图、位置和修改差异 | 全屏 |
| 像素差异 | 技术变化证据，不承担创意结论 | 全屏 |
| 区域批注 | 指向具体人物、产品、背景、光区或文字问题 | 全屏 |
| 缩放和平移 | 检查脸、手、产品结构、品牌文字和细节瑕疵 | 全屏 |
| 故事板网格 | 镜头顺序、覆盖率、重复、跳轴和节奏概览 | 全屏 |
| Animatic | 帧时长、节奏、音乐/音效节点和转场 | 全屏或持久应用 |
| 变化影响图 | 上游修改会让哪些脚本、镜头、参考和 prompt 失效 | 内联或全屏 |
| 可调模拟 | 时长、镜头数量、节奏密度、品牌露出变化的影响 | 内联 |
| 客户审阅记录 | 版本、评论、状态、签核人和时间戳 | 持久应用 |

## 推荐的图片审阅体验

### 1. 对话内快速审阅

适用于：用户刚上传或生成 1–3 张候选图，需要决定继续、精审或重试；4 张及以上进入全屏联系表。

必须显示：

- 当前审阅对象和版本；
- 有真实媒体时使用真实缩略图，不用模拟素材替代；
- 一句专业判断；
- 3–5 个最关键维度，例如叙事功能、主体一致性、构图、光线、产品准确性和模型瑕疵；
- 当前查看项与初始推荐分开；
- 一个主要动作和最多一个次要动作。

允许本地操作：切换候选、放大预览、显示/隐藏维度、查看问题列表。

允许提交的对话意图：`沿用这个候选继续`、`打开精细审阅`、`只重试这个问题`、`停止`。

不允许：在组件内直接写“已锁定”“已通过最终验收”“已允许生成下一批”。

### 2. 全屏精细审阅

适用于：高分辨率图片、两个版本对比、具体区域修改、故事板或四张及以上候选。

优先实现：

1. 单图 Fit/100%/放大/平移；
2. A/B 并排和联动缩放；
3. 相同尺寸时的叠加滑杆；
4. 点、矩形和自由区域批注；
5. 问题筛选：身份、场景、产品、构图、光线、文字、瑕疵、连续性；
6. 每条批注明确绑定 asset id、版本 hash 和归一化坐标；
7. 选择“接受当前版本”或“按选中问题重试”时返回对话，由控制器复核。

像素差异放在二级工具中。创意修改、不同裁切或不同尺寸不能用像素差异直接判定优劣。

### 3. 持久化客户审阅

仅在需要多人或长期协作时开发：

- 版本栈和最新版本提醒；
- 帧/区域/时间码评论；
- 待审、需修改、已确认等状态；
- 评论解决状态；
- 审阅人、时间戳、活动记录；
- 访问范围和分享权限；
- 服务端保存图片、缩略图和批注。

这应作为 Apps SDK 应用或 Site，而不是继续扩大 DIRcreative 的内联 fragment。

## DIRcreative 阶段映射

| 阶段 | 默认可视化 | 图片审阅增强 |
| --- | --- | --- |
| 导演组概念 | 三方向对比 | 可附每个方向 1 张真实参考缩略图 |
| 故事发展 | 情绪/钩子/品牌曲线 | 关键节点帧只用于解释，不提前冒充故事板 |
| 剧本 | 时间带和声音预算 | 无需图片，除非已有明确画面证据 |
| 镜头设计 | 多轨镜头节奏 | 全屏故事板网格和运动方向 |
| 视觉圣经 | 风格矩阵和连续性图 | 身份/场景/产品母版精审 |
| 参考图规划 | 素材关系图 | 联系表、角色标签、用途与镜头绑定 |
| 图片 prompt | 继承关系摘要 | 展示引用图和目标，不展示 raw prompt 为主要界面 |
| 生成 QA | 候选差异和最小重试 | A/B、叠加、区域批注、连续性热图 |
| 视频路线 | 模型能力对比 | 首尾帧和引用角色检查 |
| 检查点 | 当前状态和影响范围 | 显示哪些图仍有效、哪些因上游修改已过期 |

## 数据契约

新增 `image_review` 结构，不把图片路径直接塞进通用展示字段：

```yaml
image_review:
  review_id: review-001
  mode: candidate_set | version_compare | storyboard | continuity
  assets:
    - asset_id: candidate-a
      version: v3
      sha256: <64 hex>
      mime_type: image/png
      width: 2048
      height: 1152
      thumbnail_ref: <safe thumbnail reference>
      full_image_ref: <authorized file reference>
      role: product_identity_candidate
  dimensions:
    - id: product_identity
      label: 产品是否准确
      status: pass | fail | pending
      evidence: <plain-language observation>
  annotations:
    - annotation_id: ann-01
      asset_id: candidate-a
      asset_sha256: <64 hex>
      geometry:
        type: point | rect | polygon
        coordinates: [0.0, 0.0, 1.0, 1.0]
      category: identity | scene | product | composition | light | text | artifact | continuity
      observation: <what is visible>
      requested_change: <one bounded correction>
  comparison:
    left_asset_id: candidate-a
    right_asset_id: candidate-b
    allow_linked_zoom: true
    allow_overlay: false
    allow_pixel_diff: false
  recommendation:
    asset_id: candidate-a
    reason: <source-bound reason>
  action_boundary:
    preview_only: true
    controller_revalidation_required: true
```

关键约束：

- 坐标使用 0–1 归一化值，避免显示尺寸变化导致批注漂移；
- 每条批注绑定具体 asset hash，版本变化后默认标记为 stale；
- 原图与缩略图分开，内联只加载足够审阅的缩略图；
- 临时下载 URL 不写入长期 artifact；
- 图片来源、权限和人物/品牌使用边界保持在权威资产记录中；
- 用户选择不是 QA 结论，控制器必须读取当前 hash 后再写回。

## 当前实现状态与剩余缺口

现有实现已经覆盖：

- 概念动态对比；
- 情绪、钩子和品牌存在曲线；
- 镜头节奏轨道；
- 素材依赖图；
- QA 文本差异；
- 视觉方向板；
- 真实 PNG 候选预览与候选/QA/动作同步；
- 来源、授权、渠道适配证据引用与 current 生命周期；
- 安全项目根、hash、图片格式、字节、像素和 SVG 主动内容门禁；
- 无媒体回退与演示参考图限制；
- 320/736 宽度、明暗主题、文本间距和大字验证。

P1 及以后尚未覆盖：

1. 没有缩放、平移、A/B 联动、叠加滑杆和像素差异；
2. 没有 hash-bound 区域批注；
3. 没有 version compare、storyboard、continuity review 模式；
4. 没有全屏状态协商和内联到全屏的状态迁移；
5. 没有多人持久化审阅、权限和活动记录。

## 对 Skill 的修改方式

保持根 `SKILL.md` 精简，只新增图片审阅触发和路由，不把 UI 实现细节写进主提示：

1. 根 `SKILL.md`
   - 当用户要求看图、比较候选、圈出问题、比较版本或审故事板时，读取图片审阅规范；
   - 先确认真实图片和当前版本，禁止用假图代替；
   - 根据数量和任务选择内联、全屏或持久应用。
2. `generation-qa/SKILL.md`
   - 加入单图、多候选、版本对比和连续性审阅路由；
   - 规定先自 QA，再让用户做创意决定；
   - 区域批注必须形成 one-variable retry。
3. `reference-image-planner/SKILL.md`
   - 生成可审阅联系表数据和素材角色标签；
   - 区分母版、规划用图、直接模型输入和已过期版本。
4. `shot-design/SKILL.md`
   - 提供故事板网格和 Animatic 数据；
   - 把镜头、动作、摄影机和声音与帧绑定。
5. 可复用资源
   - 新建独立 image-review schema；
   - 新建 image reviewer renderer/controller，而不是继续膨胀 decision-surface；
   - 内联 viewer 与 fullscreen inspector 共用同一结构化数据；
   - 保留 Markdown/表格 fallback。

## 执行顺序与完成标准

### P0：真实图片快速审阅

实现：

- typed image review schema；
- 1–3 张真实候选的联系表/单图查看；
- 动态专业判断和维度状态；
- 当前查看、初始推荐、用户选择三者分离；
- 提交对话意图和 hash 复核；
- 320/736、明暗、大字、文本间距、键盘和无图片 fallback。

完成标准：使用真实本地 PNG 图片夹具完成候选切换、文字更新、错误 hash、错绑证据、过期生命周期、超限图片拒绝和动作 payload 验证；同时覆盖无媒体和演示参考图路径。

### P1：全屏精细审阅

实现：

- 单图缩放/平移；
- 并排和联动缩放；
- 同尺寸叠加滑杆；
- 点/矩形批注；
- 从内联带当前资产和选择进入全屏；
- 批注生成最小重试意图。

完成标准：批注在不同显示尺寸下位置稳定；版本改变时旧批注 fail closed；所有核心功能只用键盘也能完成。

### P2：故事板与连续性

实现：

- 故事板网格和单帧精审；
- 30+ 镜头虚拟化/分页；
- Animatic 时间线、帧时长、音频/字幕节点；
- 角色、场景、服装、道具和光线连续性热图。

完成标准：长故事板无内部横向滚动和文字遮挡；帧、时间码、评论和镜头数据一致。

### P3：持久化协作

仅在确认有多人审阅需求后启动 Apps SDK 应用或 Site：版本栈、评论、状态、权限、活动记录和存储。

完成标准：刷新和重开后仍能恢复权威状态；审阅人、版本、时间和决定可追溯；分享范围经过明确配置和验证。

## 验收门禁

不得仅凭 schema 校验或页面能打开就声称完成。每个阶段至少验证：

- 真实图片而非模拟审阅素材；
- 图片、版本和 hash 绑定；
- 所有选择都会更新对应说明与建议；
- 320/736 宽度无重叠、裁切和内部横向滚动；
- 浅色、深色、强制文本间距、大字模式；
- 键盘、焦点、非颜色唯一编码和文本替代；
- 无效引用、过期版本、不同尺寸叠加和缺图均 fail closed；
- 组件不能直接写锁定、验收、完成或生成授权；
- 控制器写回后才显示确认回声；
- 使用一组未参与开发的真实图片做最终冷审阅。
