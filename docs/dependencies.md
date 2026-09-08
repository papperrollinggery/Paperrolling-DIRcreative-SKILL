# Install and update dependencies / 安装与更新联动 Skill

[English overview](../README.md) · [中文介绍](../README.zh-CN.md)

DIRcreative's internal modules ship with DIRcreative. External specialist Skills are separate installations. The combined installer below is opt-in, installs only the licensed local bundle, and checks Jingzao's official latest stable GitHub Release. It does not contact the network during normal film or image requests.

DIRcreative 内部模块随主包提供。外部专业 Skill 单独安装；以下联合安装入口需要显式启用，只安装许可明确的本地依赖包，并检查镜造官方最新稳定 Release。普通影视／图片请求不会因此每次联网更新。

## Combined installation / 一起安装

From this source checkout, install a development copy and its dependencies into the same development Skills root:

从本源码目录执行，将开发副本和依赖安装到同一个开发 Skills 目录：

```bash
python3 scripts/install_local_skill.py \
  --skills-root "$HOME/.codex/dev-skills" \
  --with-dependencies
```

This writes `dircreative`, `humanizer-zh` and, when available and safe to install, `jingzao-image-forge` beneath the supplied root. Configure your host to discover that development root. Passing `--target` together with `--skills-root` is rejected to prevent an ambiguous destination.

上述目录下会得到 `dircreative`、`humanizer-zh`，以及在来源可用且可以安全安装时的 `jingzao-image-forge`。请让宿主发现该开发目录。`--target` 与 `--skills-root` 不能同时使用，以免目标含糊。

For a canonical installation in `$HOME/.codex/skills`, keep the full [verified-release installation](../README.technical.md#verified-release-install) procedure. Replace its `--target` argument with `--skills-root "$HOME/.codex/skills"` and add `--with-dependencies`. Preserve all artifact, checksum, expected commit, expected tag and reproducible-source arguments. The dependency switches belong to this updated source; older published releases may not contain them.

正式安装到 `$HOME/.codex/skills` 时，保留[正式 Release 验证安装](../README.technical.md#verified-release-install)的完整步骤，把其中 `--target` 换成 `--skills-root "$HOME/.codex/skills"`，并加上 `--with-dependencies`。归档、校验文件、精确 commit、tag 与可复现源码参数都必须保留。依赖参数属于本轮更新源码；旧 Release 可能尚未包含。

## Jingzao only / 单独更新镜造

Inspect the official release and the local installation without writing to the Skills directory:

只检查官方发布和本地状态，不写入 Skills 目录：

```bash
python3 scripts/dircreative_jingzao_updater.py check \
  --skills-root "$HOME/.codex/skills"
```

Install a missing copy or update a clean copy managed by this updater:

安装缺失副本，或更新由本入口管理且未被修改的副本：

```bash
python3 scripts/dircreative_jingzao_updater.py sync \
  --skills-root "$HOME/.codex/skills"
```

The updater resolves the official `papperrollinggery/jingzao-image-forge` latest stable Release to an exact tag commit, stages that commit's archive, and installs regular files without running upstream scripts. It retains a file-hash receipt outside the Skill directory.

更新器将官方 `papperrollinggery/jingzao-image-forge` 的最新稳定 Release 解析为精确 tag commit，暂存该 commit 的归档，只安装普通文件，不执行上游脚本。文件哈希回执保存在 Skill 目录之外。

Unmanaged installations, edited files, unexpected files and newer or unorderable versions are preserved. A conflict requires inspection; this tool never uses a force-overwrite option. Successful installation establishes file provenance and integrity, not compatibility with every future model or successful image generation. If an existing local copy is preserved, it has not been synchronized to the public release.

未托管安装、本地修改、意外文件、较新版本及无法排序的版本会被保留。冲突需要查看原因，本工具不提供强制覆盖选项。安装成功证明文件来源和完整性，不代表适配所有未来模型或真实出图成功。本地副本若被保留，就没有同步成公开版本。

## Offline bundle / 离线依赖包

| Skill | Contents / 内容 | License / 许可 | Version source / 版本依据 |
| --- | --- | --- | --- |
| `humanizer-zh` | `SKILL.md`, `README.md`, `LICENSE` | MIT, original notice retained / 保留原声明 | Exact snapshot and SHA-256 per file / 快照与逐文件哈希 |

The lock is [humanizer-zh/manifest.json](../dependency-bundles/humanizer-zh/manifest.json). No unrelated images, caches, credentials or machine-specific origin files are included.

锁定清单见 [humanizer-zh/manifest.json](../dependency-bundles/humanizer-zh/manifest.json)。不包含无关图片、缓存、凭据或本机来源记录。

To install only this bundle, without network access:

仅安装此依赖包，无需联网：

```bash
python3 scripts/dircreative_dependency_bundle.py install \
  dependency-bundles/humanizer-zh/manifest.json \
  --skills-root "$HOME/.codex/skills"
```

## Other providers / 其他联动能力

The [provider catalog](dependency-catalog.md) lists the Skill IDs in the existing selector. Most are not redistributable from the material currently available in this repository, so they are not copied into the public package. Obtain those Skills from their authors or your authorized collection, retain their original IDs, install through your host's supported mechanism, and open a new task so discovery can refresh. Where a verified public source is unavailable, this guide does not invent a download link.

[Provider 清单](dependency-catalog.md)列出既有 selector 中的 Skill ID。多数条目目前缺少可据以公开再分发的材料，因此不复制进公开包。请从作者或你有权使用的合集取得，保留原 Skill ID，通过宿主支持的方式安装，再打开新任务刷新发现。尚未核实公开来源的条目不提供猜测的下载链接。

Image-generation tools, fal.ai access, transcription services, ffmpeg and video download utilities are services or executables, not capabilities granted by copying a Skill directory. Follow their own setup requirements. The dependency bundle is not a complete clone of the maintainer's local environment.

图像生成工具、fal.ai 使用权限、转录服务、ffmpeg 和视频下载工具属于服务或可执行程序，复制 Skill 目录不会同时获得这些能力，仍需按各自说明配置。依赖包不等于维护者本地环境的完整克隆。

## Return values / 返回状态

Commands emit JSON. `ok` means the requested installation/check completed; individual entries distinguish `installed` (new or updated) and `up_to_date`. `preserved` or `conflict` explains why a local copy was left untouched. Exit code `2` signals attention is required; `1` signals a blocking error. Read every dependency result: DIRcreative may already be installed when a network dependency fails.

命令输出 JSON。`ok` 表示所请求的安装／检查完成；各条目区分 `installed`（新装或更新）与 `up_to_date`。`preserved` 或 `conflict` 说明本地副本为何未改动。退出码 `2` 表示需要处理，`1` 表示阻塞错误。请逐项查看依赖结果：联网依赖失败时，DIRcreative 本体可能已安装。
