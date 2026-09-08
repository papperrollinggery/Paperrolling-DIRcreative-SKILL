# Product CG style library / 产品 CG 风格库

Six source-image-free capsules and a product-led directing method are available
inside the existing DIR production-design workflow. They transfer visual rules,
not source packaging, branding, layouts or renderer weights.

六类风格胶囊与产品分析方法已接入既有制作路径。先判断产品要让观众理解或感到什么，
再选择材质行为、镜头和接镜方式；不把某一种美妆配色或爆粉效果设为所有产品的默认。

| Family / 风格 | Main job / 主要表达任务 | Tested targets / 测试目标 |
| --- | --- | --- |
| `pastel-dry-powder-cg` 柔光干粉 | 粉质、细尘密度、短绒接触与软反射 | 粉盒、艺术颜料 |
| `precision-hard-surface-cg` 精密硬表面 | 轮廓、倒角、反射、连接与工艺细节 | 硬盘、精密工具 |
| `elastic-fiber-cg` 弹性与织构 | 织纹方向、局部形变与软硬边界 | 针织鞋、织布音箱 |
| `viscous-sensory-cg` 流变触感 | 黏度、包覆、断裂与固液对比 | 巧克力、陶瓷涂覆 |
| `sculptural-luxury-cg` 雕塑材质 | 工艺材料、负空间与克制超现实关系 | 腕表、钢笔 |
| `graphic-modular-cg` 图形模块 | 简化体块、重复节奏与产品识别 | 耳机、磨豆器 |

[Catalog](../../skills/dircreative/references/product-cg/catalog.json) ·
[Direction method](../../skills/dircreative/references/product-cg-direction.md) ·
[11 official research cases](../../docs/film-preproduction/research/product-cg-expression-2026-09-08.md)

## Call it naturally / 直接调用

```text
$dircreative 用「柔光干粉」为这款产品做 CG 分镜。
保留现有剧本和总时长，先讲清材料如何被看见，再设计动作状态和接镜。
纯画面不加摄影标注，说明放在图下。
```

```text
$dircreative 为这款耳机比较「精密硬表面」与「图形模块」两种 CG 表达。
先说明各自服务哪条产品信息、材质怎么变化、如何回到主产品；暂不生成。
```

```text
$dircreative Develop a product CG sequence using sculptural-luxury-cg.
Keep the supplied geometry, palette and duration. Explain the product role of
one visual metaphor, then show the entry, event and exit of each shot.
```

Select one capsule and copy it into the target project before using the existing
`--style-capsule` preparation/compilation option. Bind its exact relative path and
SHA-256 through the existing handoff. The capsule is not an image attachment.
A conflicting target identity, material, palette or medium takes priority.

选一个包并复制到目标项目，通过既有 `--style-capsule` 入口使用。不要同时加载全部包，
也不要将风格包当作产品身份图片。它不新增生成授权或另一套路由；只改一句提示词时仍只改那一句。

## Product reasoning / 产品分析方法

Use this short chain to expose the decisions that matter:

**产品事实与未知 → 观众应理解/感到什么 → 材料与动作结果 → 镜头信息增量 → 前后接镜 → 停留与验证。**

每个元素都要有来源、运动原因、落点和产品作用。阵列可以组织节奏，微距可以读材料，
接触可以显示触感，反射可以解释曲面；这些作用不能互相替代。新增状态图或备选图不等于
增加镜头和时长。虚构产品允许明确的概念设计，抽象 CG 不等于功效、性能或制造证据。

## Video examples / 视频提示词示例

- [Powder compact PromptIR](prompt-ir.json) → [compiled prompt](video-prompt.txt):
  9 seconds, four shots; hinge opening, short-velvet contact/lift, a declared
  artistic particle excursion and return, then an open-product hold.
- [Precision drive PromptIR](precision-prompt-ir.json) → [compiled prompt](precision-video-prompt.txt):
  9 seconds; silhouette, chamfer/brushing reflections, interface/status-line detail
  and a complete hero. No powder metaphor or invented performance test.

Both use the real PromptIR compiler and the official Seedance 2.5 capability card.
They are text-only concept examples without reference assets or generated video.
Their timings and camera choices are authored designs, not measurements from the
research films. Before production, supply and bind the actual product references
required by the chosen workflow; do not mistake these examples for an accepted film.

两例用不同产品逻辑组织镜头。已验证 schema 与真实编译，没有生成或验收视频。
当前为无参考资产的文字概念示例，不能替代具体项目的产品锁定与实际素材绑定。

## Evidence and limits / 测试证据与边界

[Validation record](../../docs/film-preproduction/research/product-cg-transfer-validation-2026-09-08.json)
binds 12 selected stills across six pairs of distinct scenarios. Two initial
powder failures are retained. Exact native prompts, PNGs and reviews are distributed
separately as `product-cg-style-transfer-evidence-v0.10.0.zip` on the release, keeping
media outside the source package.

独立视觉复核支持六组**静态风格机制迁移**，状态为 `validated`，不是用户 `adopted`。
首轮干粉有粗颗粒/长刷毛问题，细化控制后的两张结果才参与该组结论。
原生 PNG 为 **1672×941**；spec 中 **1920×1080** 是设计意图，原生调用没有尺寸参数，
不能声称精确尺寸合格。粉盒盖仍有裁切，粒径比例/短绒长度未量测；其他细节和构图偏差
逐项保留在记录中。因此这些图是测试样片，不是整图技术交付通过。

Actual DIR preparation was replayed from zero for the precision-drive case using
a hash-bound capsule and the installed provider's sealed five-module runtime.
The resulting native prompt was used for its image. Other cases use the actual
installed Jingzao compiler. No raw client frames, decks, performer footage or
private paths are redistributed, and none of these tests establish temporal
stability, engineering performance or universal first-pass success.
