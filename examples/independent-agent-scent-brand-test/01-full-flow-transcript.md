---
artifact_id: independent-agent-scent-brand-full-flow-v1
run_id: independent-agent-scent-brand-2026-05-18
run_type: isolated_independent_agent_simulation
real_user_co_creation_verified: false
live_user_acceptance_receipt_written: false
real_media_generated: false
simulated_user_source: independent_subagent
---

# Independent Agent Full Flow Transcript

This is an isolated simulation. The simulated user did not see DIRcreative internals, scoring rules, or a standard answer. It is not real user acceptance.

## Simulated User Initial Demand

我想做一个 60-90 秒的 AI 视频，给一个新中式香氛品牌做发布短片。

品牌感觉不要太仙、太古风，也不要像普通香水广告。核心想表达“回到自己的节奏”，有一点东方气质，但画面要现代、克制、高级。产品是一个小型车载/桌面两用香氛器，外形像一块黑色鹅卵石，表面有细微金属光泽。

受众主要是 25-35 岁城市女性，平时压力比较大，通勤、加班、独处这些场景都可以出现。希望视频不是硬卖产品，而是像一个短片，有情绪变化，有一个人从外界噪音里慢慢安静下来的过程。

预算很低，只能用 AI 生成画面和后期剪辑，不能实拍。成片要适合小红书、抖音、官网首屏都能剪版本。先做一个主版本，后面可能拆 15 秒和 30 秒。

我现在只有产品概念、品牌关键词和几个参考方向，没有完整脚本。希望你帮我把方向、故事、分镜、画面参考和视频生成提示词都整理出来。不要太玄，也不要太像奢侈品广告。

## Stage 1: Idea Intake

阶段: 想法读取

客户可见预览:

- 一句话方向: 一个现代城市女性从外界噪音里慢慢找回自己的节奏。
- 情绪弧线: 被推着走 -> 找到安静锚点 -> 主动放慢。
- 3 个关键画面: 地铁玻璃上的通知反光；黑色鹅卵石香氛器落在车内/桌面；夜晚房间里屏幕熄灭，产品留在安静光里。
- 产品出现方式: 不是硬广开箱，而是节奏转换的物理锚点。
- 结尾记忆点: `回到自己的节奏`。

智能体创作内容:

- 项目: 新中式香氛器发布短片。
- 产品: 黑色鹅卵石形车载/桌面两用香氛器，细微金属光泽。
- 用户给出的时长: 60-90 秒主版本，后续 15 秒和 30 秒拆条。
- 生成单元: 视频模型每组按 5-15 秒拆，不把主片压成 15 秒。
- 渠道: 小红书/抖音需要 9:16 与前 2 秒钩子；官网首屏更适合 16:9 或 21:9 的无声循环片段。
- 当前模式: prompt-only；不生成真实图片或视频。

专业判断:

这个需求的核心难点不是“东方风格”，而是避免三种俗套：仙气古风、奢侈品香水套路、AI 空镜堆叠。主版本应先确定一个可剪成短条的情绪线，而不是直接写散装画面。

用户确认点:

我先按以下假设推进是否正确：75 秒主版本、9:16 社交优先、官网后续横版适配、产品外观可微调但必须保持黑色鹅卵石？如果不对，请先改这四项。

模拟用户选择:

确认 75 秒主版本和社交优先。产品外观可以微调，但必须像黑色鹅卵石，不能变成香水瓶。

## Stage 2: Director Room

阶段: 导演组会议

客户可见预览:

- 片名方向: `一块黑石的呼吸`
- 情绪弧线: 城市噪音压近，黑石让空间变慢，人重新掌握节奏。
- 3 个关键画面: 电梯/地铁玻璃反光压迫；产品在车内/桌面成为黑色锚点；夜晚桌面安静收束。
- 产品/人物出现方式: 产品先于品牌语出现，人物是普通城市白领，不是香水广告模特。
- 结尾记忆点: 关掉屏幕后，产品还在安静地“留住节奏”。

智能体创作内容:

导演组角色卡:

- producer: 先做 75 秒 9:16 主版，所有镜头要能抽出 15 秒和 30 秒拆条；低预算 AI 制作不允许过多角色和场景。
- creative_director: 核心不是东方符号，而是现代留白；必须禁止水墨、仙雾、古风摆件、香水大片凝视。
- director: 女主表演要小，肩颈、眼神、关通知这些微动作比大情绪更可信。
- cinematographer: 低饱和城市夜光、玻璃反射、50/85mm 肖像和 100mm 产品 macro；少用大幅度运动。
- production_designer: 产品必须先锁形状和材质，车内/桌面两用要靠尺度和摆放方式读出来。
- editor: 前 2 秒要有噪音钩子；75 秒主片分 6 个 sequence，15 秒拆条只保留最短因果。
- sound_designer: 不建议一开始用音乐铺满，先用城市噪音，产品入场后让高频退场。
- model_prompt_engineer: 第一张不能生 hero frame，应先出 PRODUCT IDENTITY REFERENCE，否则后面产品漂移。
- continuity_qa: 品牌名、Logo、出香口、产品尺寸还未明确，生成前必须冻结产品不可变字段。

导演组分歧:

- creative_director 想更抽象，producer 反对：社交平台会读不懂产品。
- cinematographer 想用雾感表现香气，production_designer 反对：用户明确不要廉价香薰感。

解决:

- 用“空气轻微折射/光线变柔”替代明显烟雾。
- 用真实通勤、桌面、车内锚定现代东方克制。

1. 方向 A: `静音按钮`
   - 叙事: 女主从地铁噪音、工位消息、深夜车流里逐步按下自己的静音按钮。
   - 优点: 适合社交平台，第一秒可用强噪音视觉开场。
   - 风险: 如果处理过猛，会像助眠 App 广告。

2. 方向 B: `一块黑石的呼吸`
   - 叙事: 产品像一块沉默的黑色鹅卵石，陪女主从通勤到独处，让空间节奏变慢。
   - 优点: 产品身份强，东方气质现代化，不玄。
   - 风险: 镜头必须有明确事件，否则会变成漂亮空镜。

3. 方向 C: `城市留白`
   - 叙事: 女主在城市缝隙里找到几段留白，香氛器成为她切换节奏的锚点。
   - 优点: 高级、克制、适合官网。
   - 风险: 抖音/小红书前 2 秒钩子偏弱。

专业判断:

推荐方向 B，并混入 A 的开场噪音压力。它最能保护产品记忆点：黑色鹅卵石不是装饰，而是节奏转换的触发器。

用户确认点:

选 A/B/C，或说明怎么混合。

模拟用户选择:

选 B，开头加一点 A 的都市噪音压力。

## Stage 3: Story Direction

阶段: 故事方向确认

智能体创作内容:

Logline:

一个被城市节奏推着走的年轻女性，在通勤、加班和独处之间，借一枚黑色鹅卵石般的香氛器，把外界噪音慢慢降下来，找回自己的呼吸速度。

7 个故事 beat:

1. 00:00-00:08 地铁门、手机震动、楼宇电梯声压上来。
2. 00:08-00:17 女主回到车内/办公桌边，拿出黑色鹅卵石香氛器。
3. 00:17-00:28 产品被放下，微光和细雾不是仙气，而是空间里的轻微呼吸。
4. 00:28-00:40 城市噪音被视觉化为玻璃反射和消息浮层，逐渐后退。
5. 00:40-00:55 女主在办公室、车内、家中三个场景里切换，动作变慢。
6. 00:55-01:08 近景回到产品材质：黑石、金属微光、气息扩散。
7. 01:08-01:15 女主关掉屏幕，空间安静下来。品牌语: 回到自己的节奏。

专业判断:

故事可以拍成 75 秒，因为它有三段空间转换；15 秒短条应只保留“噪音 -> 黑石 -> 安静”的最短逻辑，30 秒保留通勤和独处两段。

用户确认点:

是否确认这个故事线？确认后我写 75 秒脚本和 sequence plan。

模拟用户选择:

确认，但不要出现太明显的烟雾，避免像廉价香薰。

## Stage 4: 75s Script + Sequence Plan

阶段: 脚本与长片拆分

智能体创作内容:

主版本: 75 秒，拆为 6 个视频生成 sequence，每组 9-14 秒。

| Seq | Time | Function | Visual Action | Audio |
| --- | --- | --- | --- | --- |
| S01 | 00:00-00:10 | 压力钩子 | 地铁门、人群脚步、手机通知反光压到女主脸上 | 高频城市噪音，无旁白 |
| S02 | 00:10-00:22 | 产品入场 | 女主坐进车内或办公室角落，掌心放下黑石香氛器 | 噪音开始变钝 |
| S03 | 00:22-00:34 | 空间变慢 | 桌面反光、车窗雨痕、产品边缘微光；气息只做轻微空气折射 | 低频呼吸感 |
| S04 | 00:34-00:48 | 三场景转换 | 通勤车内、加班桌面、夜晚房间以相同产品位置连接 | 节奏放慢 |
| S05 | 00:48-01:03 | 情绪转折 | 女主摘下耳机/关掉消息，眼神从紧绷到松开 | 留白，少量环境声 |
| S06 | 01:03-01:15 | 品牌收束 | 产品黑石质感特写，女主手离开屏幕，空间稳定 | 品牌音 + 一句字幕 |

15 秒拆条:

- 00:00-00:03 城市噪音压迫。
- 00:03-00:07 黑石香氛器落桌/落车内。
- 00:07-00:12 空气变慢，女主表情松开。
- 00:12-00:15 产品特写 + 品牌语。

30 秒拆条:

- 保留 S01、S02、S03、S06；删除三场景展开。

专业判断:

这里必须先做 deliverable version map。否则后面生成参考图时会只服务 75 秒主片，无法可靠剪小红书、抖音和官网首屏。

用户确认点:

确认按 75s 主片 + 30s 拆条 + 15s 拆条的 deliverable map 继续吗？

模拟用户选择:

确认。优先保证竖屏平台，官网可以后面适配。

## Stage 5: Professional Shot Plan

阶段: 专业分镜确认

智能体创作内容:

| Shot | Time | Seq | 景别/焦段 | 画面内容 | 运动 | 声音 | 模型风险 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SH01 | 00:00-00:05 | S01 | 35mm 中近景 | 女主站在地铁门边，手机通知反射在玻璃和脸侧 | 轻微手持推近 | 通知声、轨道声叠加 | 不能做成惊悚片 |
| SH02 | 00:05-00:10 | S01 | 50mm 特写 | 她握紧包带，灯箱和人群形成压迫线 | 慢速横移 | 高频声变密 | 避免夸张焦虑表演 |
| SH03 | 00:10-00:16 | S02 | 50mm 手部近景 | 黑色鹅卵石香氛器被放到车内/桌面 | 静态微推 | 噪音变钝 | 产品形状必须一致 |
| SH04 | 00:16-00:22 | S02 | 85mm 产品特写 | 黑石表面有细微金属光泽，无明显喷雾 | 微距拉焦 | 低频开始出现 | 避免廉价烟雾 |
| SH05 | 00:22-00:34 | S03 | 40mm 室内中景 | 女主坐下，肩颈放松，空间反光变柔 | 缓慢 dolly-in | 呼吸声/室内底噪 | 不要瑜伽广告感 |
| SH06 | 00:34-00:42 | S04 | 35mm 车内广角 | 产品在中控台，车窗城市光点后退 | 稳定车内侧移 | 雨声/路噪 | 车载位置要可信 |
| SH07 | 00:42-00:48 | S04 | 50mm 桌面中景 | 办公桌灯下，产品与笔记本形成黑色锚点 | 顶部轻俯拍 | 键盘声减少 | 别像电商详情页 |
| SH08 | 00:48-00:58 | S05 | 85mm 肖像 | 女主眼神从紧到松，关掉通知 | 极慢推近 | 声音留白 | 微表情要真实 |
| SH09 | 00:58-01:08 | S05/S06 | 100mm macro | 产品边缘金属微光、黑石材质、空气轻微折射 | 微距滑动 | 品牌音前奏 | 不可有鱼鳞/噪点 |
| SH10 | 01:08-01:15 | S06 | 50mm 静物 + 手部 | 手离开屏幕，黑石留在安静桌面 | 静态定格 | 品牌音 + 字幕 | 字幕另做后期，不进画面参考 |

专业判断:

10 个镜头比 5 个镜头更合适。75 秒品牌短片需要节奏层次，但每组视频生成仍保持 5-15 秒，降低模型漂移。

用户确认点:

是否确认这个 10 镜头方案？确认后进入视觉风格和参考图计划。

模拟用户选择:

确认，女主不要太网红，要像真实城市白领。

## Stage 6: Visual Direction

阶段: 视觉风格选择

智能体创作内容:

1. `Urban Quiet Luxury`
   - 现代城市夜色、玻璃、黑石、低饱和金属光。
   - 风险: 可能太像奢侈品广告。

2. `Modern Eastern Restraint`
   - 东方气质来自留白、材质、节奏，不用古建筑/水墨/仙雾。
   - 风险: 需要严格控制画面不要太空。

3. `Warm Workday Reset`
   - 更生活化，办公室/车内/房间都可信。
   - 风险: 高级感下降。

专业判断:

推荐 2，并混入 3 的生活可信度。这样能避开“太仙”和“太奢侈品”，也适合 AI 生成时保持统一材质。

用户确认点:

选 1/2/3，或说明怎么混合。

模拟用户选择:

选 2，加入一点 3 的真实生活感。

## Stage 7: Reference Image Plan

阶段: 参考图方案

客户可见预览:

- 第一张图应该看到什么: 只有产品，一枚黑色鹅卵石状香氛器，能读出桌面/车载两用，材质克制高级。
- 暂时不应该看到什么: 女主、完整广告场景、大片式香水姿态、古风元素、标题大字。
- 后续三张关键图: 真实白领人物身份、车内/办公桌/房间空间 FOV、10 镜头故事板运动图。
- 可直接喂视频模型的图: 只有后续无字 clean frames；带标注的身份板/故事板不能直接当首帧。

智能体创作内容:

最少参考图组:

1. `PRODUCT IDENTITY REFERENCE`
   - 用途: 锁定黑色鹅卵石香氛器外形、比例、材质、微金属光泽。
   - 不能直接喂视频模型: 如果是多视图板，只给人和后续提示词用；clean product frame 才可作为直接参考。

2. `CHARACTER IDENTITY REFERENCE`
   - 用途: 锁定 25-35 岁城市女性，真实白领气质，非网红、非香水大片模特。
   - 不能直接喂视频模型: 多角度人物板是身份参考，不是镜头画面。

3. `ENVIRONMENT + CAMERA FOV REFERENCE`
   - 用途: 车内/办公桌/夜晚房间的空间关系、镜头视场、产品摆放点。
   - 不能直接喂视频模型: 带标注/FOV 的规划板只用于人类和 prompt 编译。

4. `PROFESSIONAL STORYBOARD + MOTION MAP`
   - 用途: 10 个镜头的景别、焦段、运动、声音、模型风险。
   - 不能直接喂视频模型: 故事板是 planning-only，不能当 first frame。

5. `CLEAN FRAMES`
   - 用途: 为 Kling/Runway 首帧或尾帧准备：SH03 产品落桌、SH05 女主放松、SH09 产品 macro、SH10 品牌收束。
   - 可直接喂视频模型: 只有通过 QA 且无文字/无分栏/无标注的 clean frame。

专业判断:

这个项目不能把人物、产品、场景、分镜都塞进一张大图。产品一致性和人物一致性是成败点，所以产品身份和人物身份必须独立。

用户确认点:

确认先按这 5 组参考图做 prompt-only 方案，不生成真实图片？

模拟用户选择:

确认，不生成真实图片。

## Stage 8: Image Execution Recommendation

阶段: 出图执行建议

客户可见预览:

- 这次如果出图，只出 `PRODUCT IDENTITY REFERENCE`。
- 目标: 锁定黑色鹅卵石香氛器，不拍广告画面。
- 画面: 中性现代桌面/车内暗示，3/4 角度，柔和侧光，细微金属光泽。
- 禁区: 古风、水墨、仙雾、奢侈品香水瓶、女主入镜、大标题广告语。

智能体创作内容:

- 建议先生成 1 张 `PRODUCT IDENTITY REFERENCE`，只锁黑色鹅卵石香氛器。
- 通过 self-QA 后再补 `FUNCTION DETAIL REFERENCE` 和 `USAGE POSITION REFERENCE`。
- product/character/environment/storyboard boards 都是 planning_only；clean frames 只有生成或导入并 QA pass 后才是 direct_input_candidate。
- 后台证据已准备: image_generation_allowed for `PRODUCT IDENTITY REFERENCE` only、pre_generation_contract.status: pass、direct_video_input_policy、artifact suffix；不让用户审批 raw JSON/YAML。

专业判断:

不按这个出图顺序执行，会直接复发产品身份漂移、标题层级错、规划板被视频模型误读的问题。

用户确认点:

是否确认只生成这一张 `PRODUCT IDENTITY REFERENCE`，不生成女主、场景、故事板或视频？

模拟用户选择:

确认，先看产品身份参考图。

## Stage 9: Image Execution Detail

阶段: 出图执行建议

客户可见预览:

1. 先导出或生成 `PRODUCT IDENTITY REFERENCE`。
2. 通过 self-QA 后再补 `CHARACTER IDENTITY REFERENCE`、`ENVIRONMENT + CAMERA FOV REFERENCE`、`PROFESSIONAL STORYBOARD + MOTION MAP` 和 clean frames。
3. JSON prompt bodies 保留在后台，需要复制时再展开。

未生成真实图片/视频:

此处进入 assisted_generation，准备生成一张产品身份参考图；视频仍未生成。

用户确认点:

先导出或生成哪一组？推荐先处理 PRODUCT IDENTITY REFERENCE。

模拟用户选择:

先导出 PRODUCT IDENTITY REFERENCE。

## Stage 9B: Assisted Image Generation Result

阶段: 出图结果自检

生成资产:

- image_id: scent-product-identity-reference-01
- role: PRODUCT IDENTITY REFERENCE
- media_status: generated_candidate
- direct_video_input_policy: rejected_for_direct_video_input
- file: /Users/example-user/.codex/generated_images/00000000-0000-7000-8000-000000000001/ig_08fed30c2ff4f193016a0a061e9e0c8199be7c8fcdfe21796b.png

自检标准:

- 是否像黑色鹅卵石香氛器。
- 是否能读出桌面/车载两用。
- 是否有细微金属光泽。
- 是否避免古风/仙雾/香水瓶/奢侈品广告模板。
- 是否没有女主、故事板、大标题或广告语。

用户确认点:

这张图只能作为早期产品造型候选，不能锁定，不能直接喂视频。独立评审建议重出一张 clean single-product version：无文字、无拼贴、无车控旋钮、香氛属性更明确。

## Stage 9C: Assisted Image Generation Retry

阶段: 出图重试结果自检

生成资产:

- image_id: scent-product-identity-reference-02
- role: PRODUCT IDENTITY REFERENCE CANDIDATE
- media_status: generated_candidate
- direct_video_input_policy: product identity candidate only, not a final clean frame
- file: /Users/example-user/.codex/generated_images/00000000-0000-7000-8000-000000000001/ig_08fed30c2ff4f193016a0a0726b9ac8199b199b3b7cb26b067.png

自检结果:

- 通过: 无文字、无拼贴、无车控旋钮、单一产品视角、黑色鹅卵石和微金属颗粒稳定。
- 风险: 白色圆盘底座可能被误读成产品组成；出香口仍偏抽象，可能被看成鼠标、音箱、香皂盒、充电盒或石头摆件；车载/桌面两用只体现了桌面。

用户确认点:

这张图可作为 `PRODUCT IDENTITY REFERENCE CANDIDATE`，但不能最终锁定。下一步必须补 `FUNCTION DETAIL REFERENCE` 和 `USAGE POSITION REFERENCE`，再让真实用户决定是否锁定产品身份。

## Stage 10: Video Generation Recommendation

阶段: 视频生成建议

客户可见预览:

- Seedance 按 S01-S06 sequence pack 输出，可绑定 product identity / character identity / environment references。
- Kling 需要 clean first/end frames 才能进入强一致性 I2V；当前保持 blocked。
- Runway 使用 clean frame + text motion；storyboard board 只转译为 movement prompt，不上传为 first frame。
- Veo 使用 subject/action/scene/camera/lighting/style/audio 分段结构；保留 reference map 和 anti-misread clause。
- model prompt bodies 保留后台，需要复制时再展开。

15s/30s cutdown prompt policy:

- 15s: 只使用 S01/S02/S05/S06 的浓缩结构。
- 30s: 使用 S01/S02/S03/S06。
- 不能从 75s prompt 随机剪，需要独立 cutdown prompt，避免前后因果断裂。

未生成真实图片/视频:

当前没有生成真实图片或视频。

用户确认点:

下一步是导出 PRODUCT IDENTITY REFERENCE 的完整 JSON prompt，还是先细化 15s/30s cutdown？

模拟用户选择:

先导出产品参考图 prompt，再细化 cutdown。

## Simulation Notes

- The run completed the visible path from demand to concept, story, sequence, shot plan, visual direction, reference strategy, pre-generation contract, image prompts, and video prompts.
- No real media was generated.
- No live acceptance receipt was written.
- This transcript is ready for independent review.

skill_run_receipt:
  run_id: independent-agent-scent-brand-2026-05-18
  skill_id: dircreative
  input_artifacts: []
  output_artifacts:
    - examples/independent-agent-scent-brand-test/01-full-flow-transcript.md
  decisions:
    - "simulated_fixture chose 75s main version"
    - "simulated_fixture chose direction B with A-style pressure hook"
    - "simulated_fixture chose Modern Eastern Restraint with lived-in realism"
    - "simulated_fixture kept visual_output_mode prompt_only"
  unresolved_questions:
    - "Real user still needs to approve the workflow."
  qa_gate:
    status: needs_user
    reasons:
      - "Independent simulation is not real acceptance."
  next_recommended_skill: generation-qa
