<div align="center">

# DIRcreative

**在 Codex 里，完成影视前期。**

[English](README.md) · [简体中文](README.zh-CN.md)

[![Release](https://img.shields.io/github/v/release/papperrollinggery/Paperrolling-DIRcreative-SKILL?display_name=tag)](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/releases/latest)
[![CI](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/actions/workflows/ci.yml/badge.svg)](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/actions/workflows/ci.yml)

[介绍页](https://papperrollinggery.github.io/Paperrolling-DIRcreative-SKILL/zh/) · [开始使用](#开始使用) · [可以做什么](#可以做什么) · [联动-skill](#联动-skill) · [文档](#文档)

</div>

![DIRcreative：故事与对白、摄影与连续性、资产与提示词](docs/assets/marketing-20260908/intro-zh-CN.png)

*AI 生成的创作示意图，不是应用截图或已经验收的生产结果。*

DIRcreative 是面向 **AI 影视前期制作的 Codex Skill**。从一句创意、一份剧本或一段参考影片出发，完成故事、分镜、视觉资产和图像／视频模型专用提示词。适用于叙事短片、广告、品牌片，也可以只处理一个镜头或一段对白。

按你需要的结果开始。局部修改保持局部；完整前期则衔接故事、摄影、人物连续性、资产与声音。实际生成使用当前 Codex 环境中已经安装、可调用的能力。

## 可以做什么

| 你提供 | 可以得到 |
| --- | --- |
| 创意或项目简报 | 创作方向、故事大纲、剧本与对白 |
| 剧本或场次 | 镜头表、机位、调度、视线与动作覆盖 |
| 人物、场景或产品 | 视觉设计、连续性约束与图像制作输入 |
| 本地视频或支持的公开视频链接 | 带时间码的参考拆解与可复用制作方法 |
| 已确定的场次和参考资产 | 模型专用视频提示词，含 Seedance 2.5/2.0 素材绑定 |
| 既有提示词或生成资产 | 局部修改、实际缺陷判断与下一轮修复方案 |

产出取决于请求范围和可用工具。提示词提交前需要核对实际参考资产与模型要求；图片生成、视频生成和最终采纳分别处理。

## 按场景组织视频提示词

先明确参考职责与稳定设计，再写逐拍变化，让动作、表演、环境、摄影与声音互相衔接。
保留具体创作要求，取消自动附加的电影质感前缀与固定节奏模板。
可查看[六类对照提示词](examples/prompt-structure-quality/README.md)和
[研究依据与验证边界](docs/film-preproduction/research/prompt-structure-20260909.md)。

## 产品 CG 风格与分析

可按需调用柔光干粉、精密硬表面、弹性与织构、流变触感、雕塑材质、图形模块六类风格。
先从产品事实出发，再设计材料行为、镜头信息、前后衔接与节奏；不会把爆粉或美妆配色套给所有产品。
包含跨场景静态测试、两份不同产品逻辑的视频提示词示例，以及 11 个官方案例的研究。
详见[风格库与测试边界](examples/product-cg-style-library/README.md)。

## 开始使用

需要支持 Skills 的 Codex 环境与 Python 3.10 及以上。图像、视频、转录和媒体下载服务各有自己的运行要求。

**正式版本安装**：从 [GitHub Releases](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/releases/latest) 下载归档与校验文件，按[精确 tag 安装说明](README.technical.md#verified-release-install)完成验证。当前源码版本为 **v0.11.1**；已发布版本以 Release 中的实际资产为准。

安装开发副本：

```bash
git clone https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL.git
cd Paperrolling-DIRcreative-SKILL
python3 scripts/install_local_skill.py
```

默认安装到 `~/.codex/dev-skills/dircreative`。在宿主中启用该开发 Skill 后，打开新的 Codex 任务，显式写 `$dircreative`：

```text
$dircreative 把“两位多年未见的朋友，因为一把遗失的钥匙再次相遇”
发展成一支 30 秒短片。先完成故事和分镜方案。
```

也可以只做局部工作：

```text
$dircreative 修改这场戏的对白，保留人物口吻和已有事件。
只交付修改后的场次。
```

## 联动 Skill

DIRcreative 已包含内部影视前期模块，按任务选择相关专业 Skill。一起安装依赖，不代表每次请求都会加载全部 Skill。

- **镜造 Jingzao Image Forge** 通过自己的[官方仓库与 Release](https://github.com/papperrollinggery/jingzao-image-forge/releases)分发。依赖更新入口检查稳定发布，并保护未托管、有本地修改或版本更高的安装。
- **许可已确认的依赖**采用版本与文件哈希锁定的打包方式，保留原许可说明。
- **其他专业 Skill** 单独安装。未确认再分发许可的文件、第三方服务及模型使用权限不随包提供。

一起安装、更新命令、已包含内容和剩余配置见[依赖安装指南](docs/dependencies.md)。该安装包不等于维护者电脑上全部能力的完整复制。

## 常见问题

**会自动生成完整成片吗？**
DIRcreative 负责前期工作，并可在请求范围内衔接可用生成工具。图片资产、视频渲染和审阅后的成片是不同交付物。

**所有图片都必须经过镜造吗？**
不需要。继续按实际任务和可用 provider 选择；镜造是图像制作联动能力。

**支持中文和英文吗？**
支持。提示中说明简报与产出的语言即可。项目介绍文档和介绍图均提供中英文版本。

**检查通过就代表画面质量合格吗？**
不代表。自动检查覆盖合同、文件与流程行为；实际视觉质量需要查看生成结果。

## 文档

- [技术指南与正式安装](README.technical.md)
- [依赖安装与更新](docs/dependencies.md)
- [影视开发流程](skills/dircreative/references/film-development.md)
- [分镜覆盖](skills/dircreative/references/storyboard-coverage.md)
- [参考视频拆解](skills/dircreative/references/video-distillation.md)
- [Seedance 转换](skills/dircreative/references/script-to-seedance.md)
- [示例](examples/) · [更新记录](CHANGELOG.md) · [机器可读项目索引](llms.txt)
- 落地页源码：[English](site/index.html) · [简体中文](site/zh/index.html)

源码验证命令为 `PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_project.py`。额外开发依赖与历史审计覆盖范围见技术指南。

## 许可

DIRcreative 尚未授予通用使用／再分发许可，公开可见不自动代表获得再分发授权。包内第三方内容保留各自明确声明的许可；这些许可不适用于整个 DIRcreative 项目。
