---
name: dircreative-shot-design
description: Convert script and breakdown into professional shot list, camera plan, blocking plan, and shot QA.
---

# Shot Design

## Required Knowledge

- `docs/film-preproduction/schemas/prompt-ir.schema.json`
- `docs/film-preproduction/prompt-authoring-standard-v1.md`
- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/professional-agent-voice-standard.md`
- `docs/film-preproduction/production-demo-retrospective.md`
- `docs/film-preproduction/council-adversarial-review.md`
- `docs/film-preproduction/client-film-hard-gates.md`
- `docs/film-preproduction/schemas/shot-list.yaml`
- `docs/film-preproduction/shot-language-standard.md`
- `docs/film-preproduction/research/film-production-glossary.md`
- `docs/film-preproduction/research/audio-design-notes.md`

## Inputs

- script
- script breakdown
- audio policy

## Outputs

- shot list
- camera plan
- blocking plan
- shot QA

## Chat Surface

Show the shot plan as a compact table:

- `阶段: 分镜头`
- `智能体创作内容`: story section count versus shot/rhythm count, timecode, story beat, narrative purpose, shot type, lens, camera support, camera motion, focus, blocking, scene layers, continuity locks, audio, asset source, vertical framing, and model notes.
- `用户确认点`: ask whether the shot structure passes before visual bible/reference planning.

If there are multiple duration strategies, show 2-3 choices and ask one selection question.

Use this chat preview shape, not a vague one-line storyboard:

```text
S01 00:00-00:03 | Hook / MS -> CU insert | 35mm then 85mm macro
- 叙事任务: <story_beat + narrative_purpose>
- 机位/镜头: <camera_angle + lens + camera_support + camera_motion + focus>
- 主体调度: <start/end/path/eyeline/screen_direction/axis>
- 构图层次: <foreground/midground/background/lighting/readable zone>
- 声音剪辑: <ambience/SFX/music/silence/cut point>
- 模型风险: <Seedance/Kling/Runway/Veo risk or split rule>
```

Use this visible storyboard shot-card text template for professional storyboard/motion pages:

```text
S03 00:18-00:24 | Narrative purpose: <why the shot exists>
Lens/support/movement: <lens + rig + start/end camera target>
Blocking/path: <subject start -> path -> end, eyeline, axis>
Continuity: <prop/wardrobe/light lock>
Sound/edit: <dialogue/ambience/SFX/music/cut point>
Model risk: <likely misread + avoid clause>
```

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#shot-density-timeline`. Keep the inline timeline compact; request fullscreen for 30 or more shots or dense inspection. Bind every displayed shot to the current shot-list artifact and preserve a table fallback.

## Rules

- One main action per shot.
- Explain shot count and rhythm with professional reasoning before asking for approval.
- For one-minute client films, distinguish `12 customer story sections` from the real shot/rhythm plan. Do not approve 12 shots as a complete 60-second shot list unless the user explicitly accepts a slower format; default to roughly 30+ shots or rhythm points.
- Every shot needs timecode, duration, story beat, narrative purpose, shot type, shot size, angle, lens, lens reason, camera support, camera motion, focus, composition, subject action, structured blocking, scene layers, continuity locks, audio fields, transitions, and model notes.
- For client-facing storyboard/PPT work, every shot also needs seconds, camera position, emotional function, props/characters, asset source, vertical composition consideration, and reference motion or reference video for hero/expression-critical moments.
- The downstream professional storyboard/motion page must have one cell per approved shot and include shot image region, detailed frame description, shot size, focal length, camera position, camera movement, subject blocking, sound, transition, and model risk.
- Storyboard page writing must read like a director explaining the film: story purpose first, camera language second, material/source or confirmation point last. Do not make the page feel like a production table.
- PPT storyboard pages may show 3-6 images per page, but the image regions must stay large, non-distorted, crop-safe, and readable. Captions belong under images and must carry story, camera, and source meaning.
- The downstream professional storyboard/motion page must use the visible shot-card template. Do not approve thin cell text that lacks narrative purpose, lens/support/movement, blocking/path, continuity, sound/edit, and model risk.
- Do not let a storyboard page replace the shot list. The page visualizes the approved shot cards; it must not invent new character identity or scene geography.
- Blocking must be structured as start position, end position, path, eyeline, screen direction, and axis note.
- Audio must be structured as dialogue, voiceover, ambience, SFX, foley, music, and silence policy.
- Camera motion must name a physical start target and end target. Do not write only `slow push`, `camera follows`, or `cinematic movement`.
- Composition must name foreground, midground, background, and the product/face/readable-text zone.
- Composition must also name the visual center, subject hierarchy, negative space, movement room, leading lines or occlusion, perspective depth, screen direction, and the narrative purpose of the chosen grammar. Do not mechanically apply rule of thirds, center framing, or symmetry.
- For every frame intended for storyboard generation, also lock viewer task and
  viewer position, dominant/secondary read, frozen action phase, action vector
  and counterforce, foreground/midground/background jobs, crop pressure,
  parallax/occlusion, exaggeration budget with one protected anchor, and one
  quiet region. These fields form the `storyboard_frame_to_jingzao_v1` handoff;
  canonical assets constrain truth but do not flatten camera direction.
- Apply those fields by `shot_class` and function. Static product, identity,
  interview, dialogue, observation, or deliberately calm frames may set action
  vector/counterforce, crop pressure, parallax, or exaggeration to
  `not_applicable` with a concrete reason. Viewer task/position, dominant read,
  depth organization, and camera motivation still remain explicit. Never invent
  motion or resistance merely to fill the contract.
- When a subject or camera moves, state which composition relationships stay locked and which change at the beat.
- Shot cards must include conditional render-look cues for lighting, optics, atmosphere, and grade. Each enabled cue needs condition, effect, intensity, preserve, and exit/continuity; unused layers must be marked none by design.
- Shot cards must give the image-prompt compiler concrete visual evidence for subject, blocking, environment, light, composition, camera, color/material, proportion, and generation intent.
- Do not invent visual facts that belong in the visual bible or reference pack. Mark unresolved wardrobe, product, text, location, or material decisions as blockers for the next stage.
- Lens choices must have a production reason, not just a focal length.
- Model notes must say whether the shot is safe as a single video generation or should be split/converted into clean frames.
- Do not approve generic phrases such as `cinematic close-up`, `warm lighting`, `hero shot`, or `worker drinks` unless the full shot card makes them production-specific.
- Across a generated storyboard sequence, reject unmotivated repetition of
  viewer position, subject/frame ratio, camera height, visual center, horizon,
  attention path, and depth pattern. Do not impose a fixed wide/medium/close
  quota; repeated grammar is valid only when motivated.
- Do not write image or video prompts.

## skill_run_receipt

Record shot gate status, overloaded shots, continuity risks, and `next_recommended_skill: visual-bible`.
