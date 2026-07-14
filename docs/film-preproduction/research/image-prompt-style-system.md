# Image Prompt Style System

Verified: 2026-07-10

Purpose: normalize image prompt writing for reference boards, clean frames, generation, and edits using JSON-first prompt configs, exact capability-card resolution, art-directed layout, rights, preserve/change contracts, failure-specific artifact guards, and a self-updating prompt-pattern registry.

## Core Finding

The useful part of the provided character-sheet prompt is not that it has many character fields.

The useful part is this control layer:

```text
Do not use a generic layout.
Do not use evenly distributed grids.
Do not make the design symmetrical only for symmetry.
The composition must feel art-directed, intentional, and slightly asymmetric.
Every section must feel carefully placed, not automatically generated.
```

That language should become a reusable `art_direction_policy` for every production image:

- character boards,
- environment boards,
- prop/product boards,
- storyboard boards,
- lighting/style boards,
- complete production boards.

## Why The Provided Prompt Works

### It defines the production audience

It says the image is for:

- director,
- casting,
- costume department,
- film development,
- merchandising,
- pitch presentation.

This is stronger than asking for a "character sheet" because it tells the image model what quality bar and artifact type to imitate.

Reusable rule:

```json
"production_audience": ["director", "cinematographer", "production designer", "video generation adapter"]
```

### It forbids default layout behavior

The best phrase is the anti-generic layout clause. It blocks the model's common default:

- centered symmetry,
- evenly sized boxes,
- generic grid,
- empty margins,
- automatic template look.

Reusable rule:

```json
"layout_policy": {
  "must_feel": ["art-directed", "intentional", "slightly asymmetric", "production-designed"],
  "forbidden": ["generic layout", "evenly distributed grid", "symmetry for symmetry", "auto-generated template feel"],
  "placement_rule": "each section must have a visible reason for its size, position, and hierarchy"
}
```

### It separates visible systems

The prompt separates:

- identity,
- face,
- psychology,
- performance,
- costume,
- material,
- turnaround,
- head studies,
- cinematic portrait,
- layout,
- style,
- consistency.

That is the right pattern for all image prompts. Do not write one long prose paragraph. Split the image into visual systems.

### It gives acting direction, not pose direction

The phrase "captured like a real actor in a key moment, not posing" is important.

Reusable for any board with humans:

```json
"performance_direction": {
  "acting_quality": "captured during a real narrative moment, not posed",
  "emotion": "transitional emotion with micro-expression",
  "avoid": ["stiff pose", "symmetrical posing", "blank model-sheet expression"]
}
```

### It demands material behavior

The prompt asks for fabric stretch, stitching, folds, wear, dirt, stains, aging, soft skin-light interaction.

That should become a general `material_truth` block.

Reusable rule:

```json
"material_truth": {
  "principle": "materials must behave like real surfaces, not plastic placeholders",
  "include": ["wear", "creases", "stitching", "surface texture", "use marks"],
  "avoid": ["plastic CGI", "over-smooth skin", "fake high-frequency texture", "scale-like artifacts"]
}
```

### It locks consistency across panels

The strict turnaround rules solve a core problem for video generation: identity drift.

Reusable rule:

```json
"consistency_locks": {
  "identity": "same face and proportions across all views",
  "costume": "same garment structure, seams, materials, and wear marks",
  "geometry": "same silhouette and spatial relation across panels",
  "forbidden": ["reinterpretation between views", "angle-to-angle costume drift"]
}
```

## GitHub And Public Prompt-Pattern Findings

### wuyoscar/gpt_image_2_skill

Useful patterns:

- Use a reference gallery before writing from scratch.
- Put canvas, aspect ratio, and layout before subject.
- JSON/config-style prompts are treated as a core pattern for complex images.
- Multi-panel boards need consistency constraints.
- Camera and capture context improve realism.
- Scene density beats adjectives.
- Material, lighting, and palette should be separate controls.
- Avoid-lines should be short and targeted.

How to reuse:

Our prompt compiler should not write from a blank page. It should first choose a pattern class, then fill a JSON schema.

### YouMind-OpenLab/gpt-image-2-prompts-search

Useful patterns:

- Curated prompt library organized by use case.
- Search by user intent, return top matches, then remix.
- Prompt data lives as category JSON files.
- The library refreshes on a schedule.
- The skill uses grep-style selective loading instead of loading the full prompt library.

How to reuse:

This project should maintain its own prompt-pattern registry:

```text
pattern registry -> select 3 nearby patterns -> remix into project JSON -> compile final prompt
```

The registry should be small, curated, and versioned. It should not become a random dump of viral prompts.

### OpenAI GPT Image 2 API Guidance

Useful patterns:

- Resolve `gpt_image_2_openai_api` before naming model behavior or output controls.
- The official guide supports generation, editing, masked editing, one or more image references, and Responses API multi-turn editing.
- For multi-image inputs, reference each image by index and role.
- Iterate with small changes instead of overloading one prompt.
- Editing prompts must declare non-overlapping `preserve` and `change` sets.
- The exact card records that transparent backgrounds are unsupported for `gpt-image-2`; prompt wording cannot override that control.

How to reuse:

Every prompt config needs:

- `capability_resolution`,
- `rights_gate`,
- `operation`,
- `transformation_contract`,
- `exact_text`,
- `reference_map`,
- `iteration_policy`,
- `quality_profile`,
- `invariants`.

## Universal JSON Prompt Architecture

Every image prompt should be authored as valid JSON first.

The JSON object is the source of truth. It can be sent directly as a prompt block, or compiled into natural language later.

Recommended top-level structure:

```json
{
  "meta": {},
  "capability_resolution": {},
  "rights_gate": {},
  "operation": "generate | edit | retry",
  "transformation_contract": {
    "preserve": [],
    "change": [],
    "forbidden_change": [],
    "overlap_check": "pass | fail"
  },
  "artifact": {},
  "production_context": {},
  "art_direction_policy": {},
  "layout_system": {},
  "visual_systems": {},
  "cinematic_capture": {},
  "text_annotation_system": {},
  "material_truth": {},
  "consistency_locks": {},
  "quality_and_artifact_control": {},
  "avoid": [],
  "self_update": {}
}
```

Capability resolution must include an exact `capability_card_id`, version, status, provider surface, verified/accessed dates, and evidence URLs. A model-family alias or `latest` is invalid. The rights gate must pass before assisted generation or external upload.

## Zhijuan Prompt Card Pattern Review

Keep these design patterns:

- fixed structured output for complex visual reasoning,
- evidence-first visual decomposition,
- separate complete prompt, reusable core prompt, and negative prompt,
- compact style tags for routing and QA,
- targeted ban on filler quality language,
- type-specific treatment for portrait, product, poster/ad, UI, illustration, 3D, and photography.

Do not import these parts as defaults:

- full `zh/en/ja` multilingual buckets for every DIRcreative handoff,
- reverse-prompt fidelity as the primary objective,
- mandatory race or ethnicity inference,
- generic quality modifiers as standalone fields.

DIRcreative is director-led. The prompt compiler should not merely reconstruct an image. It should preserve the locked story, shot, visual bible, asset role, and downstream model use.

Reusable structure:

```json
{
  "evidence_policy": {
    "source_of_truth": "locked upstream artifacts and visible generated/imported evidence",
    "uncertainty_rule": "write broader production-safe wording when a detail is uncertain",
    "forbidden": ["invented logos", "invented unreadable text", "invented locations", "hidden objects"]
  },
  "visual_decomposition": {
    "subject": {},
    "action_pose_or_blocking": {},
    "details_appearance": {},
    "environment_background": {},
    "lighting_atmosphere": {},
    "composition_framing": {},
    "style_camera": {},
    "colors_palette": {},
    "materials_texture": {},
    "proportion_scale": {},
    "generation_intent": {}
  },
  "prompt_layers": {
    "director_recreation_prompt": "complete prompt for this exact asset",
    "prompt_core": "short reusable lock for identity, composition, light, style, palette, and material",
    "negative_prompt": "targeted avoid-list for artifact risks and continuity drift"
  },
  "style_tags": ["3 to 5 short routing tags"]
}
```

Field mapping into DIRcreative:

| Zhijuan-style field | DIRcreative mapping |
| --- | --- |
| subject | character/product/prop identity lock |
| action or pose | blocking, performance direction, subject action |
| environment | scene geography and camera FOV reference |
| light | visual bible lighting rules and shot lighting state |
| composition | shot card foreground/midground/background/readable zone |
| style/camera | shot size, angle, lens feel, support, movement, focus |
| colors/materials | palette, wardrobe/product material locks, texture QA |
| aspect/proportion | canvas, scale, product silhouette, frame role |
| generation intent | asset role, direct video input policy, retry target |

Language policy:

- Default to the project working language and exact displayed labels only.
- Add multilingual fields only when the client deliverable, UI, or external generation tool needs them.
- Style tags stay short and concrete; they help selection and QA, not image quality by themselves.

## Art-Directed Layout Policy

Use this policy across all image types:

```json
{
  "layout_policy": {
    "non_negotiables": [
      "do not use a generic layout",
      "do not use evenly distributed grids unless the artifact specifically requires a technical grid",
      "do not make the layout symmetrical only for symmetry",
      "composition must feel art-directed, intentional, and slightly asymmetric",
      "every section must feel carefully placed, not automatically generated"
    ],
    "hierarchy": {
      "hero_region": "largest and most important visual information",
      "secondary_regions": "supporting views, details, breakdowns",
      "annotation_regions": "short readable production labels",
      "negative_space": "breathing room only, never filler"
    },
    "placement_logic": [
      "section size follows production importance",
      "camera/shot information stays near the related frame",
      "material notes stay near the visible material",
      "reference panels are large enough for downstream video models"
    ]
  }
}
```

Grid exception:

Use strict grids only for technical reasons:

- turnaround views,
- expression matrices,
- data small multiples,
- shot strips,
- thumbnail contact sheets.

Even then, the whole page can still be art-directed with asymmetry around the grid.

## Production Image Types

### Character Design Board

Must include:

- identity,
- face structure,
- psychology,
- performance,
- costume,
- materials,
- turnaround,
- head studies,
- cinematic portrait,
- consistency locks.

Use the user's provided prompt as the base pattern, but convert it into JSON fields.

### Environment Blocking Board

Must include:

- hero environment,
- support angles,
- top-down floor plan,
- camera positions,
- subject path,
- prop/location anchors,
- lighting sources,
- scale references.

Art direction policy:

The board should feel like a production designer and cinematographer planned it together, not like a real estate layout.

### Prop/Product Board

Must include:

- hero view,
- front/side/back or key angles,
- macro material details,
- interaction view,
- state changes,
- scale reference,
- story function.

Art direction policy:

The object must feel usable in production, with material truth and handling logic.

### Director Storyboard Board

Must include:

- shot strip,
- timecode,
- shot size,
- lens,
- camera motion,
- action,
- narrative purpose,
- sound cue labels if needed.

Art direction policy:

The storyboard area may use shot panels, but the full board should not become a generic equal-grid contact sheet unless the shot logic requires it.

### Lighting Style Board

Must include:

- palette,
- light sources,
- contrast rule,
- lens texture,
- weather/atmosphere,
- post look,
- still references or generated style frames.

Art direction policy:

It should feel like a cinematography look bible, not a mood-board collage.

## Fish-Scale / Texture Artifact Guard

The second user-provided prompt points to a common image-model failure: high-frequency, scale-like, noisy, cracked, or over-sharpened texture.

Normalize it as `surface_integrity_guard`, but keep the fixed wording as an optional internal QA macro rather than a model rule.

Legacy internal QA macro text:

```text
The image is clean and transparent, with complete and natural materials, smooth and uniform texture, and the main subject Be clear, with distinct background layers, and avoid excessive sharpening, color spots, and noise Cracks, collapse, and distortion
```

Activation rules:

- `default_application: false`.
- Use only when an observed output shows a matching material/geometry failure or an explicit internal A/B eval needs it.
- Record the failure ID, the prompt without the macro, and the changed result.
- Prefer a concise failure-specific avoid list when it is enough.
- Never use the word `transparent` in this macro as evidence that the selected model supports alpha/transparent background output.
- Never append the macro to every GPT Image, Image2, or provider-family prompt.

Possible triggers:

- fish-scale surface,
- color speckles,
- noisy microtexture,
- broken material continuity,
- over-sharpened edges,
- cracked/collapsed geometry,
- distorted subject silhouette.

Reusable block:

```json
{
  "surface_integrity_guard": {
    "required": [
      "clean natural materials",
      "smooth and coherent surface texture",
      "main subject remains clear",
      "background depth layers remain distinct",
      "complete object geometry"
    ],
    "avoid": [
      "fish-scale texture",
      "excessive sharpening",
      "color speckles",
      "random noise",
      "cracks",
      "collapsed surfaces",
      "distorted geometry",
      "broken material continuity"
    ]
  }
}
```

The macro preserves the user-provided wording for internal comparison only. `transparent_background` remains a separate capability-card output control when alpha/cutout output is actually required.

## Generate vs Edit Prompt Contract

Before prompt compilation, select one operation:

```json
{
  "operation": "generate | edit | retry",
  "input_images": [
    {"ref_id": "", "role": "", "rights_status": "verified"}
  ],
  "transformation_contract": {
    "preserve": [],
    "change": [],
    "allow_incidental_change": [],
    "forbidden_change": [],
    "overlap_check": "pass"
  }
}
```

- `generate` describes a new visible state and must not pretend an edit source exists.
- `edit` requires at least one real input image and explicit preserve/change sets.
- `retry` changes one production variable and names the observed failure.
- `preserve` and `change` may not overlap; split a partly changed field into invariant and mutable subfields.
- Every input image must pass the rights gate before execution.

## Storyboard / Clean Frame Prompt Separation

Professional storyboard/motion prompts carry role title, shot image, timecode, duration, lens, camera movement, blocking, sound, transition, and model risk. Their direct input policy defaults to `planning_only`.

Clean-frame prompts carry `Clean frame contract:`, `no visible title`, one shot state, and a direct input policy bound to an exact capability-card reference mode. Never hide a clean-frame request inside a board prompt or imply that a board crop exists.

## Prompt Registry For Self-Update

The prompt system should become self-updating through a registry, not by rewriting core docs every time.

Each pattern entry should contain:

```json
{
  "pattern_id": "character_board_art_directed_v1",
  "category": "character_design_board",
  "source": {
    "type": "user_pattern | github | internal_eval | output_retry",
    "url": "",
    "observed_date": "2026-05-14"
  },
  "trigger_keywords": [],
  "strengths": [],
  "failure_modes": [],
  "json_delta": {},
  "quality_gate": [],
  "status": "active"
}
```

Update loop:

```text
new prompt example found
-> classify category
-> extract reusable pattern, not full prompt
-> add source and observed date
-> test against one fixture
-> promote to active only if it improves output or clarity
-> deprecate if repeated QA failures appear
```

## Compiler Rule

The final compiler should not concatenate every field blindly.

It should:

1. Select image type.
2. Load 2-3 relevant patterns from registry.
3. Merge selected pattern deltas into the JSON config.
4. Validate required fields.
5. Produce one compact JSON prompt.
6. Add a short natural-language preface only when useful.
7. Keep exact labels quoted.
8. Preserve avoid-lines as targeted guardrails.

## Sources — Accessed 2026-07-10

- wuyoscar/gpt_image_2_skill: https://github.com/wuyoscar/gpt_image_2_skill
- wuyoscar craft guide: https://github.com/wuyoscar/gpt_image_2_skill/blob/main/skills/gpt-image/references/craft.md
- YouMind prompt search skill: https://github.com/YouMind-OpenLab/gpt-image-2-prompts-search
- OpenAI image generation and editing guide: https://developers.openai.com/api/docs/guides/image-generation
- OpenAI GPT Image prompting guide: https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide
