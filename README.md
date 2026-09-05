<div align="center">

# DIRcreative

**A chat-first film preproduction skill for Codex.**

把一句创意发展成可讨论、可选择、可验证的导演方案、故事、脚本、镜头、参考图计划与模型专用提示词。

[![Release](https://img.shields.io/github/v/release/papperrollinggery/Paperrolling-DIRcreative-SKILL?display_name=tag)](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/releases/latest)
[![CI](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/actions/workflows/ci.yml/badge.svg)](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Codex Skill](https://img.shields.io/badge/Codex-Skill-111827)
![License](https://img.shields.io/badge/license-not%20yet%20granted-lightgrey)

[快速开始](#quick-start) · [能力](#what-it-does) · [交互体验](#visual-conversational-workflow) · [示例](#examples) · [文档](#documentation) · [正式安装](#verified-release-install)

</div>

![DIRcreative interactive decision surface](docs/assets/dircreative-chat-visualization.png)

DIRcreative 不是“输入一句话、吐出一堆提示词”的黑盒。它先判断任务是局部修改、完整开发还是交付审计，再只加载对应合同。局部任务直接交付修改结果；只有真实方向冲突、生成授权或客户交付才停下来询问。

当前源码版本为 `v0.8.1`；已发布版本与下载以 [GitHub Releases](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/releases) 为准。本版修复全片前期从文字规划切换到真实图片资产时的执行断层：分离图片/视频授权，绑定跨任务用户范围、资产角色、权威真值、人物母版、依赖 DAG、媒体调用前置检查和真实生成证据；同时把去 AI 化规划与实际改写、Seedance 能力卡与权威剧本源、结构验证与视觉采用继续保持为不同状态。

源码仓库包含 DIRcreative 根 Skill、19 个 `skills/dircreative/*` 内部子 Skill，以及 `ai-film-asset-stress-test`、`ai-film-production-ledger` 两个 P0 能力入口。正式 DIRcreative 安装包按安全设计只暴露根 `$dircreative`，其余入口会内部化后由 selector 路由；Skill Stack 还会发现宿主中已安装的外部专业 provider。这些依赖不会被复制进本仓库，也不能把“宿主可调用”表述成“GitHub 已内置”。ADCO 始终是独立外部编排方。

## What is DIRcreative?

DIRcreative is an AI film preproduction and AI video workflow Skill for Codex.
It turns a brief, screenplay, local video, or public reference-video link into
the production decisions and artifacts needed before image or video generation.
It is designed for narrative shorts, commercials, brand films, and model-aware
workflows using Seedance 2.5/2.0 and other video models.

Typical outputs include:

- reference-film evidence, timecoded craft analysis, and transferable methods;
- concept direction, treatment, screenplay, dialogue, and source-derived voice;
- shot list, camera/blocking plan, reverse shots, eyelines, and action-phase panels;
- character, location, prop, material, continuity, and clean-input asset plans;
- image prompts plus Seedance-specific video prompts and asset/audio bindings;
- sound cues, production ledger, validation report, rejection reasons, and retry plan.

DIRcreative does not claim that a prompt is a generated video, that a local
candidate is approved, or that a structural PASS proves visual quality.

## Why DIRcreative

- **先创作，后生成**：先解决受众、叙事、产品证明和镜头逻辑，再进入图片或视频生成。
- **把专业判断放在结果后面**：Fast 直接修改；Studio 最多选择三个真正影响结果的专业视角，不展示固定角色会议。
- **让复杂方案看得懂**：方向比较、节奏曲线、镜头时间线、参考图依赖和 QA 结果都可以可视化。
- **不锁定单一模型**：把同一镜头意图适配到 Seedance、Kling、Runway、Veo 等不同生成模型。
- **证据与风险成比例**：Fast / Studio 默认不写路径、Git、receipt 或全项目记录；只有真实生成、交付和跨系统 handoff 才保留必要证据。

## What it does

| 模式 | 适用任务 | 默认预算与产出 |
| --- | --- | --- |
| Fast | 一句/一段文案、单镜头、少量分镜、Prompt 或既有产物局部修改 | <= 14 KB 上下文、0 Threads、0 Director Room；>= 75% 有用内容 |
| Studio | 完整概念、故事+脚本、脚本+分镜、多产物影视前期 | <= 20 KB 上下文、最多 3 个动态专业视角、最多 1 个 critic；>= 70% 有用内容 |
| Delivery | 真实生成授权、正式版本/资产、客户可见交付、有效 ADCO handoff | <= 30 KB 上下文；只为当前真实动作运行审计与 receipt |

```text
explicit $dircreative → direct judgment → Fast | Studio | Delivery
                     → one Route Card + at most one craft card
                     → useful artifact first
                     → router only for ambiguity or validated handoff
```

## Visual, conversational workflow

可视化不是装饰，而是每个用户决策的操作界面：

- **方案比较卡**：选中项、推荐理由和下游影响同步变化，避免“选择变了、建议没变”。
- **曲线与时间线**：展示情绪、信息密度、钩子、产品曝光和镜头节奏。
- **关系图**：说明角色、场景、产品、参考图和最终镜头之间的继承关系。
- **图片审阅**：在对话中查看候选图、放大关键区域、标记问题，并决定采用、重试或改方向。
- **明确空状态**：没有媒体时显示生成前置条件与下一步，不使用假图冒充结果。
- **响应式布局**：桌面端并排比较，窄屏自动改为可读的纵向流程。

2026-07-14 对 `v0.4.0` 交互面的本地浏览器验收覆盖 **14 个页面、84 个响应式场景、0 个失败**；复现命令见 [Development and validation](#development-and-validation)。技术门禁证明界面和工作流按约定运行，但不会替代具体客户项目的真人创意验收。

本轮工作流优化已修复显式组协作、否定请求、单页故事范围和系统/包内 Skill 发现链，并清理旧逐阶段确认。详见 [优化记录与验证边界](docs/film-preproduction/research/workflow-optimization-2026-09-05.md)。正式发布与安装以对应 Release 和实际验证结果为准；源码测试不代表媒体效果验收。

## Quick start

### Prerequisites

- 支持 Skills 的 Codex 环境
- Python 3.10+
- Ruby（项目总验证中的 YAML 兼容检查需要）
- 可选：Node.js 20+ 与 Playwright，仅用于 84 场景浏览器审计
- 可选：GitHub CLI `gh`，仅用于下载正式 Release

### 1. Clone and install a development copy

```bash
git clone https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL.git
cd Paperrolling-DIRcreative-SKILL
python3 scripts/install_local_skill.py
```

开发副本安装到 `~/.codex/dev-skills/dircreative`，不会覆盖正式 SkillHub 安装。

### 2. Run the demo and validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_headless_acceptance_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_project.py
```

安装后请打开一个新的 Codex 任务，并显式写 `$dircreative`。隐式调用已关闭；普通广告问题或仓库维护不会启动本 Skill。

### 3. Start in Codex

可以直接用自然语言开始：

```text
$dircreative 把“多年未见的朋友，因为一件旧物重新联系”
发展成一支 30 秒品牌短片。先给我推荐方向和首轮故事，不生成图片或视频。
```

DIRcreative 会选择 Fast、Studio 或 Delivery。Fast 不进入 Director Room；Studio 只选择能改变结果的 `narrative_strategy`、`visual_production`、`model_continuity` 视角，最多三个。用户不需要点名固定角色。

## Safety model

- 图片生成与最终视频生成分别授权；“完成视频生成前全部流程”在明确包含图片资产时会生成真实图片，但不会生成最终视频。
- 每次图片调用都要绑定当前视觉计划、active asset、role-specific contract、prompt、父资产审查状态和 host 选择的项目根；错误人物母版不能解锁后续分镜或 clean input。
- 完整成片先展示动态视觉资产矩阵：角色/产品/关键道具、每个场景、每个镜头的独立分镜图、覆盖全部镜头的导演故事板，以及模型实际需要的 clean frames。
- TVC 验收使用 16:9 广播主档案，不以 9:16 社媒变体代替；具体帧率、声音、字幕/法务安全区与母版参数以目标客户或播出方规格为准。
- 再展示生成合同：每张图的用途、继承来源、标题层级和是否会成为视频输入；代表性样片不得冒充全片完成。
- 视觉资产计划 v2.3 绑定源清单、批准 shot cards、连续且逐帧对齐的 timecode、完整逐镜创意真相和精确继承关系；完成证据统一为依赖无关的规范 PNG，场景、逐镜、风格与视频输入帧必须匹配目标画幅，文件完整解码后再绑定规范化像素身份、技术收据和包内独立视觉复核清单。`user_locked` 只是工作流状态，不能绕过复核；技术盖章不能自动通过视觉判断，独立资产也不得靠 metadata 改写把同一画面冒充多张图。
- `visual_assets_complete` 只表示场景图、逐镜分镜、导演故事板和视频输入帧完成，不表示 TVC 成片、客户批准或电视台验收。
- fixture、终端演示、HTML 页面和自动化测试不能冒充真人验收。
- 生成候选、临时截图和 review widget 不能自动成为项目 source of truth。
- 高风险场景/支撑关系在交给镜造或图像工具前必须写入 `truth_contract`：场景附件、道具附件、参考图不可控制的背景/地面字段、可见支撑关系、父帧状态和最低充分约束输入均须显式绑定。实际执行的 prompt 与附件路径还必须和 hash-bound manifest 及 host trace 一致；结构 PASS 不代表像素里真的看见了悬挂关系。
- 不在未授权情况下修改目标项目的 `AGENTS.md`。

## ADCO Integration

DIRcreative 既可以独立在聊天中运行，也可以作为 ADCO 的影视前期专业 worker：

```yaml
protocol_id: adco.specialist-exchange
contract_version: "2.0"
execution_mode: inline
```

ADCO 负责客户交互、Current Truth、采用决策、版本、可见性、PPT、FinalDelivery、完成状态和 cleanup；DIRcreative v2 只返回领域产物、领域 QA、状态和开放问题，不复制这些控制平面字段。v1 handoff/receipt/adoption 仍可读取。

```bash
python3 scripts/dircreative_adco_native_exchange.py --self-test
python3 scripts/dircreative_adco_native_exchange.py \
  --adco-repo /path/to/ad-creative-orchestrator
```

未提供 `--adco-repo` 时，发布门只报告 `RELEASE_GATE_SCOPE: DIR_ONLY`，不能作为双边兼容证据。完整协议见 [`adco-integration-contract.md`](docs/film-preproduction/adco-integration-contract.md)。

## Examples

| 示例 | 适合查看 |
| --- | --- |
| [`live-user-sim-noodle`](examples/live-user-sim-noodle/) | 从一句产品创意到方向、脚本、镜头、参考图与模型提示词的完整对话 |
| [`cyber-courier`](examples/cyber-courier/) | Director Room 如何形成并选择概念方向 |
| [`goal-mode-simulation-test`](examples/goal-mode-simulation-test/) | 用户不逐项回复时，如何标注模拟选择并安全继续 |
| [`assisted-generation-preflight-chat`](examples/assisted-generation-preflight-chat/) | 用户说“看看图”时，如何先完成生成前置门 |
| [`zombie-cleaner-test`](examples/zombie-cleaner-test/) | 180 秒长叙事的拆解、参考计划与 prompt-only 测试 |
| [`v0.7.1 60s preproduction regression`](docs/film-preproduction/research/v071-60s-preproduction-regression.md) | 真实 60 秒项目如何保留 18 镜/30 面板设计，同时阻止受场景/支撑污染的 S07 进入 Seedance |

## Frequently asked questions

### Is DIRcreative an AI video generator?

It prepares and validates the creative, visual, sound, asset, and model-specific
inputs. Real image/video generation is a separately authorized Delivery action,
and every generated output still needs visual and production review.

### Can it analyze a reference video without copying it?

Yes. The `video_distillation` route separates timecoded observations,
inferences, unknowns, and transferable mechanisms. A new project inherits the
method and quality bar, not the source film's characters, world, dialogue, or
protected expression.

### How detailed are its storyboards?

Coverage follows actions and information changes rather than a fixed image
count. A shot can contain prepare/contact/consequence panels, reverse shots,
eyelines, prop-state transitions, and clean model inputs when those distinctions
change generation or QA.

### How does it use Seedance 2.5 and 2.0?

The authoritative script and asset ledger are model-neutral. DIRcreative then
builds different generation units, duration plans, visual baselines, reference
roles, performance instructions, and prompt surfaces for each target model.

## Documentation

### Layered humanization

Clear, bounded dialogue and prose edits can be written directly while preserving
facts and voice. They do not require a full humanization plan or Sepia call.
Document-scale rewrites and demonstrated structural or discourse problems use
the layered path: distinguish `write`, `review`, `refactor`, and `recreate`;
inspect architecture or venue, discourse and surface separately; and select the
repair depth from confirmed defects. Layered findings need a source-bound quote,
cluster and whitelist verdict. When Sepia refactor/recreate is selected, diagnosis
runs first; only a second call carrying the
diagnosis hash, accepted findings and host-read voice/venue evidence may edit.
Inline sources have a 64 KiB limit and the full evidence packet has a separately
reported 128 KiB Studio budget:

```bash
python3 scripts/dircreative_humanization_plan.py plan \
  docs/film-preproduction/templates/humanization-plan.template.json
python3 -m unittest discover -s tests -p test_humanization_plan.py -v
```

The plan treats model fingerprints as version-scoped inspection guidance, never
infers an author model from prose, and requires the actual source text, exact
entry spans and content/set hashes before a full rewrite. A document guard
travels into provider selection, blocking screenplay-inappropriate inventions such as added
subplots, nonlinear time or fourth-wall gestures merely to imitate a corpus
statistic. Short Chinese edits choose a contextual or explicit fidelity route;
short English edits remain bounded; layered operations use the installed
[Sepia](https://github.com/Nanako0129/sepia) provider when selected.
Sepia and `mr-li-seedance-25` remain external Skills and are not copied into this
repository. See [the workflow contract](skills/dircreative/references/humanization-workflow.md).

### Reference-video distillation

`$dircreative 拆解这个视频链接，给我 AI 制作方法报告` selects the Studio
`video_distillation` route. Reuse the installed public-video downloader and
Video Evidence Workbench when available. The local bridge prepares hash-bound
evidence and an unknown analysis draft; it does not perform vision inference:

```bash
python3 scripts/dircreative_video_distill.py prepare \
  --video /path/to/source.mp4 --output-dir /path/to/new-study \
  --workbench-project /path/to/workbench-project
python3 scripts/dircreative_video_distill.py validate /path/to/new-study
python3 scripts/dircreative_video_distill.py render /path/to/new-study
python3 -m unittest discover -s tests -p test_video_distill.py -v
```

The report separates observations, inferred methods and unknowns across twelve
craft axes. Its creative review asks why the reference works, why that effect
matters to the original, where the actual artifact falls short, what changes,
and what reinspection shows. Structural validity cannot certify creative quality.
Analysis produces candidates; source iteration, image/video generation, global
installation and publishing retain separate scoped authorization. Complete the
reference study and upgrade review before an explicitly requested original-film
trial. See [the mode contract](skills/dircreative/references/video-distillation.md).

Explicit detailed/full preproduction also uses an action-panel coverage sidecar.
It preserves one representative frame per shot while allowing ordered panels
inside that shot and optional reverse/eyeline pairs. Design and actual PNG
coverage are separate checks, with no fixed per-minute shot quota:

```bash
python3 scripts/dircreative_storyboard_coverage.py validate /path/coverage.json \
  --project-root /path/project --phase design
python3 scripts/dircreative_storyboard_coverage.py validate /path/coverage.json \
  --project-root /path/project --phase assets --legacy-plan /path/project/visual-plan.json
```

See [detailed storyboard coverage](skills/dircreative/references/storyboard-coverage.md).
Legacy visual-asset completeness does not alone certify all requested action
panels. The new checker validates declared coverage, never artistic quality.

Coverage-declared high-risk scene/support frames must use the existing Jingzao
handoff truth gate. `truth_contract` keeps the scene asset authoritative,
prevents prop or identity references from donating their background or ground,
requires every declared attachment to exist and match its SHA-256, invalidates
children of failed parent frames, and compares the compiled prompt/reference
manifest with the sealed host request. Low-risk and rough-planning frames keep
the legacy path; a spatial mockup or scene reference is selected only when risk
requires it. See [the Jingzao handoff contract](skills/dircreative/references/storyboard-frame-to-jingzao.md).
Reviewer public keys live in persistent host configuration, not the installed
Skill; see [review trust host configuration](docs/film-preproduction/review-trust-host-config.md).

白模、深度图或空间 layout 不是默认资产。只有镜头存在高风险空间、遮挡、比例或支撑关系时才选择最低充分约束；它们只控制 geometry、composition、occlusion、scale 与 support，不得控制人物/道具身份、材质、纹理或最终美术。最终生图是否调用镜造仍由任务和已安装 provider 能力决定，不做全局强制。

- [`System plan`](docs/film-preproduction/01-system-plan.md) — 系统架构、角色、适配器和 QA 门
- [`Runtime contracts`](docs/film-preproduction/runtime-contracts.md) — v2 单一合同所有者、上下文边界和兼容矩阵
- [`Chat co-creation interface`](docs/film-preproduction/chat-co-creation-interface.md) — 结果优先的聊天呈现指南
- [`Native adjustment panel PRD`](docs/film-preproduction/dir-native-adjustment-panel-prd.md) — 发布后的 Visual Workspace 全屏工作台产品规格，不是已实现功能
- [`Director Room perspectives`](docs/film-preproduction/director-room-council-protocol.md) — 动态专业视角、真实分歧与 v1 只读边界
- [`Live chat start protocol`](docs/film-preproduction/live-chat-start-protocol.md) — 粗想法、完整想法、测试和图片请求的入口
- [`Film commercial quality standard`](docs/film-preproduction/film-commercial-quality-standard.md) — 影视与商业质量门
- [`Model sources`](docs/film-preproduction/sources/model-sources.yaml) — 有日期和证据等级的模型能力卡
- [`Release and integration architecture`](docs/film-preproduction/05-skill-integration-architecture.md) — Skill、运行时和发布结构

完整规范、schemas、研究与运行手册位于 [`docs/film-preproduction`](docs/film-preproduction/)。

## Verified release install

正式安装源是同一 GitHub Release 中的归档和 `SHA256SUMS`，再由该 tag 的精确、
干净源码执行同进程验证与安装；不能运行归档内的 installer，也不能用 metadata
自证。下面的信任链从 `v0.5.0` 起适用；更早版本不满足这条正式安装门。
以下命令在 `v0.8.1` tag 与 Release 实际发布后生效。

```bash
gh release download v0.8.1 \
  --repo papperrollinggery/Paperrolling-DIRcreative-SKILL \
  --pattern 'dircreative-0.8.1.tar.gz' \
  --pattern 'SHA256SUMS'
```

<details>
<summary><strong>从精确 tag 一次完成验证、可复现重建、安装和回读</strong></summary>

```bash
set -euo pipefail
REPO_URL="https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL.git"
TAG="v0.8.1"
EXPECTED_COMMIT="$(
  git ls-remote --exit-code --tags "$REPO_URL" \
    "refs/tags/$TAG" "refs/tags/$TAG^{}" |
  awk -v ref="refs/tags/$TAG^{}" '
    $2 == ref { count += 1; sha = $1 }
    END {
      if (count != 1 || length(sha) != 40 || sha !~ /^[0-9a-f]+$/) exit 1
      print sha
    }
  '
)"
ARTIFACT="$(pwd)/dircreative-0.8.1.tar.gz"
CHECKSUMS="$(pwd)/SHA256SUMS"
VERIFY_ROOT="$(mktemp -d)"
trap 'rm -rf "$VERIFY_ROOT"' EXIT
git clone --filter=blob:none --no-checkout "$REPO_URL" "$VERIFY_ROOT/source"
git -C "$VERIFY_ROOT/source" fetch --depth 1 origin \
  "refs/tags/$TAG:refs/tags/$TAG"
git -C "$VERIFY_ROOT/source" checkout --detach "$EXPECTED_COMMIT"
python3 "$VERIFY_ROOT/source/scripts/install_local_skill.py" \
  --target ~/.skillshub/dircreative \
  --formal-install \
  --artifact "$ARTIFACT" \
  --checksums "$CHECKSUMS" \
  --expected-commit "$EXPECTED_COMMIT" \
  --expected-tag "$TAG" \
  --reproducible-source "$VERIFY_ROOT/source"
```

</details>

维护者安装未发布的精确候选时仍需完整 artifact/checksum/source 绑定，并额外显式
加入 `--allow-unpublished`。它只放宽 canonical remote tag 条件；exact commit、干净
canonical source、逐字节可复现、完整 manifest、staging 与 target 回读都不会放宽。

安装后验证实际目标：

```bash
cd ~/.skillshub/dircreative
python3 scripts/validate_project.py
python3 scripts/dircreative_adco_native_exchange.py --self-test
```

## Development and validation

最常用的本地门禁：

```bash
python3 scripts/validate_project.py
python3 scripts/dircreative_activation_policy_audit.py
python3 scripts/dircreative_context_budget_audit.py
python3 scripts/dircreative_director_harness_audit.py
python3 scripts/dircreative_prompt_fixture_audit.py
python3 scripts/dircreative_headless_acceptance_audit.py
python3 scripts/dircreative_content_first_audit.py
python3 scripts/dircreative_live_model_eval.py --self-test
python3 scripts/dircreative_visual_asset_plan.py --self-test
python3 scripts/dircreative_readiness_audit.py
python3 scripts/dircreative_quality_audit.py
python3 scripts/dircreative_chat_surface_audit.py
python3 scripts/dircreative_visualization_dogfood.py
python3 scripts/dircreative_adco_native_exchange.py --self-test
```

`dircreative_live_model_eval.py` 只验证真实模型的文字响应行为，不证明图片或
视频已经生成。当正式安装验收包含真实媒体能力时，需针对仓库内候选执行一次
隔离的交互式媒体前向测试，检查实际落盘文件；测试媒体保留在仓库包之外。
媒体收据不能只自报 `real_tool_execution=true`。v2 前向测试用两份相互绑定的
收据：执行收据必须绑定 Codex 原始 JSONL 日志的不可变前缀（字节数与 SHA-256），
从真实日志反推出独立任务中的密封 `$dircreative` 用户调用、候选 Skill 观察、
imagegen 事件 ID、提示词、按序参考图、输出字节与时间；另一独立任务的日志必须绑定
只含原始参考图、输出和 rubric 的密封审查请求，证明每个输出恰好打开一次，并绑定其
审查结论。门禁会
把固定哈希的 `c2patool` 复制到私有快照后，再校验 OpenAI
Media Service 的 C2PA 签名、签发 CA、`gpt-image 2.0` 创建声明、签名时间和输出
数据哈希。C2PA 不绑定提示词或输入参考；本机日志仍是 unsigned host trace，
视觉结论仅是 reviewer judgment，图片通过也不代表视频已经验证。

完整发布门：

```bash
python3 scripts/dircreative_release_gate.py \
  --require-tag \
  --adco-repo /path/to/ad-creative-orchestrator \
  --media-forward-receipt /absolute/path/to/media-forward-execution-v2.json \
  --media-review-receipt /absolute/path/to/media-visual-review-v1.json \
  --media-host-event-log /absolute/path/to/execution-rollout.jsonl \
  --media-review-host-event-log /absolute/path/to/review-rollout.jsonl \
  --media-c2patool /absolute/path/to/pinned/c2patool \
  --require-media-forward
```

`--allow-unpublished` 仅用于开发或 CI 预发布检查，不是正式 release 证据。发布门在开始时封存一个精确 commit，把同一 SHA 传给媒体、preflight、build 与 archive verifier，并在结束时再次读取 HEAD；任何中途切换都会失败。它还验证源码、行为、临时安装、独立校验归档和可选的 ADCO 双边兼容。

复现完整浏览器响应式审计：

```bash
npm ci
npx playwright install chromium
python3 scripts/dircreative_visualization_dogfood.py
npm run audit:visual-browser
```

审计覆盖 736px / 320px、明暗主题、文字间距和大字号模式，并检查横向溢出、文字重叠、裁切、触控目标、图片状态、选择后的推荐同步和可执行动作。

## Contributing

欢迎通过 [Issues](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/issues) 报告问题或提出改进。提交前请：

1. 保持修改范围集中，不把 fixture 结果写成真人验收。
2. 为 bug 补最小复现或回归测试。
3. 运行 `python3 scripts/validate_project.py` 和与改动相关的审计脚本。
4. 不提交客户素材、密钥、真实运行历史或个人绝对路径。

Issue 与 PRD 约定见 [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md)。

### Fixture media notice

`outputs/reference-pack/` 中的图片是用于测试参考图绑定与审阅流程的 AI-generated fixtures。仓库公开或标记为 `project_owned` 仅描述 fixture 在测试中的归属关系，不授予素材商用权，也不替代对具体模型条款、品牌权利和投放地区的独立审核。

## License

This repository is publicly readable, but no open-source license has been granted yet. Until a license is added, default copyright restrictions apply.

本仓库目前可公开阅读，但尚未授予开源许可证。在正式添加许可证之前，默认著作权限制仍然适用。
