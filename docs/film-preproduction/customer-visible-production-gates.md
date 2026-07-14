# Customer Visible Production Gates

Verified: 2026-05-18

Purpose: keep DIRcreative's professional workflow visible to the client, not hidden in files or internal summaries.

## Core Rule

Every major stage must first show a customer-readable creative preview, then the production system state.

The user should be able to judge:

- what the film will feel like,
- what the first 3 key images are,
- what the emotional arc is,
- how the product or protagonist appears,
- what decision is needed now.

Do not lead with model jargon, gate names, or blocker language when the user has not yet seen the creative proposal.

## Mandatory Client Questions

Before story, script, reference images, or generation for a brand/product film, ask or infer and confirm:

1. `brand_assets`: brand name, logo, package, typography, and mandatory copy status.
2. `product_lock`: whether product shape/material/scale/use method are fixed or may be designed.
3. `human_strategy`: whether the protagonist is shown, face visibility, age, occupation, city temperament, and performance boundaries.
4. `delivery_priority`: first release aspect and platform priority, such as 9:16 social-first, 16:9 web-first, or multi-version.

If any item is unknown, show the best assumption and ask one grouped decision question before image generation.

## Director Room Visibility

`阶段: 导演组会议` must show distinct seat cards, not only a final recommendation.

Minimum visible seats:

- `producer`: scope, platform, budget, deliverables.
- `creative_director`: concept, brand taste, forbidden cliches.
- `director`: performance, blocking, emotional arc.
- `cinematographer`: lens, light, camera movement, visual continuity.
- `production_designer`: product, set, material, color, props.
- `editor`: hook, rhythm, cutdown logic.
- `sound_designer`: noise, music, silence, voice policy.
- `model_prompt_engineer`: model risk, reference strategy, direct input policy.
- `continuity_qa`: identity/product/scene locks and downstream stale risks.

The stage must include at least one disagreement and resolution note before asking the user to choose a direction.

## Customer Preview Before Internal System State

Use this order:

```text
阶段: <stage>

客户可见预览:
- 一句话片名/方向:
- 情绪弧线:
- 3 个关键画面:
- 产品/人物出现方式:
- 结尾记忆点:

导演组/专业判断:
<role cards or production rationale>

生产状态:
<prompt-only / assisted_generation / blocked items / no real media generated>

用户确认点:
<one decision question>
```

## First Image Generation For Product Films

When image generation is allowed but product identity is not locked, the first generated asset should normally be `PRODUCT IDENTITY REFERENCE`.

Before generating it, freeze:

- product silhouette,
- size and scale cues,
- material and surface behavior,
- outlet/opening/diffusion method,
- logo/text policy,
- desk/car use readability,
- forbidden style drift.

The first product identity image must not include:

- protagonist,
- full ad scene,
- storyboard panels,
- labels, captions, large or small page text,
- detail insets or product-sheet collage panels,
- large slogan text,
- strong background props that can rewrite the product category,
- ancient/immortal/fantasy symbols unless explicitly requested,
- luxury perfume ad cliches when the user rejects them.

The first generated product identity candidate should be a clean single-product view. If material macro, vent detail, packaging, or usage-context details are needed, split them into separate assets after the primary silhouette is accepted.

After generation, run a video-model misread check before asking the user to lock the asset:

- Could it be mistaken for a speaker, power bank, air purifier, car control knob, perfume bottle, incense burner, or ancient ornament?
- For abstract pebble, pod, stone, or capsule products, could it be mistaken for a mouse, soap, jewelry box, stone decor, charging case, or generic electronic accessory?
- Does any text, label, inset, panel, or background prop risk being copied into video?
- Does it clearly read as the intended product category without relying on written labels?
- Does it preserve the requested cultural/taste direction without drifting into rejected cliches?

Abstract product identity cannot be locked from a beauty shot alone. Before user lock, require:

- `PRODUCT IDENTITY REFERENCE CANDIDATE`: clean single-product silhouette and material candidate.
- `FUNCTION DETAIL REFERENCE`: same product identity, showing diffusion/opening/use mechanism without turning into a technical collage.
- `USAGE POSITION REFERENCE` when the product claims multiple modes, such as desk plus car placement.

If the asset includes a coaster, base, tray, dock, magnet, stand, or holder, label it in the artifact contract as environment/support hardware so the model does not merge it into the product body.

## New Chinese / Eastern Style Risk Gate

For modern Chinese or Eastern mood requests, DIRcreative must explicitly reject unwanted cliches when the brief asks for restraint:

- excessive ancient costume or palace cues,
- ink-wash default styling,
- immortal/fantasy mist,
- generic Zen props,
- luxury perfume visual template,
- abstract "oriental" symbols without daily-life grounding.

Replace them with concrete modern anchors: commute, desk, car interior, apartment, elevator, parking garage, glass, ceramic, metal, fabric, screen light, rain, city noise, silence.

## Failure Cases

Fail the chat UX if:

- the director room is summarized as one monologue,
- the user does not see role cards or disagreement,
- the user is not asked client-critical questions before generation,
- the first generated product image happens before product invariants are frozen,
- the reply exposes only internal terms such as `blocked`, `contract`, or model names before showing the creative preview.
