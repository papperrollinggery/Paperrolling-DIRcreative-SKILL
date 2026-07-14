---
name: dircreative-visual-bible
description: Define visual continuity for characters, environments, props, wardrobe, lighting, palette, and texture.
---

# Visual Bible

## Required Knowledge

- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/schemas/visual-bible.yaml`
- `docs/film-preproduction/research/storyboard-reference-analysis.md`
- `docs/film-preproduction/research/image-prompt-style-system.md`

## Inputs

- shot list
- asset requirements
- blocking plan

## Outputs

- visual bible
- continuity locks
- drift risks

## Chat Surface

Show visual style choices before locking the bible:

- `阶段: 视觉风格`
- `智能体创作内容`: 2-3 visual directions, continuity locks, material rules, avoid list.
- `我的建议`: one style direction with production reason.
- `用户确认点`: ask which visual direction should guide reference images.

Do not move to image prompt compilation until the visual direction is confirmed.

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#visual-lock-matrix`. Bind identity, environment, props, wardrobe, light, material, and drift risks to the visual-bible artifact; use fullscreen only when the continuity matrix cannot remain legible inline and preserve the table fallback.

## Rules

- Lock identity, environment, prop states, palette, lighting, and material behavior.
- Break visual direction into concrete fields before prompt work: subject, action/pose or blocking, details/appearance, environment/background, lighting/atmosphere, composition/framing, style/camera, colors/palette, materials/texture, proportion/scale, and generation intent.
- State which facts are locked from story/shot/reference evidence and which are still unresolved. Do not invent unseen brands, exact text, locations, camera bodies, lens models, or hidden objects.
- Define type-specific visual rules when relevant: portrait, product, poster/ad, UI, illustration, 3D, or photography.
- Use style tags only as compact routing labels. The visual bible still needs full visual rules.
- Decide whether the project needs one board or a multi-image reference pack.
- Do not write final image prompts.

## skill_run_receipt

Record visual bible gate status, missing assets, drift risks, and `next_recommended_skill: reference-image-planner`.
