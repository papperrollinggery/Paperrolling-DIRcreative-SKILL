# AI Video Prompt Community Lessons

Verified: 2026-06-06

Purpose: capture public prompt-construction lessons from Higgsfield-style skills, official model guidance, Reddit/X community practice, and professional storyboard templates. This file is evidence input for DIRcreative. It is not a dependency on Higgsfield, any MCP server, X, Reddit, or any external generation account.

## Sources Checked

- Higgsfield community prompt skill: https://github.com/OSideMedia/higgsfield-ai-prompt-skill
- Higgsfield official agent skills: https://github.com/higgsfield-ai/skills
- User-supplied X reference: https://x.com/D_studioproject/status/2062078290249253134
- OpenAI Sora 2 Prompting Guide: https://cookbook.openai.com/examples/sora/sora2_prompting_guide
- Boords storyboard template guide: https://boords.com/storyboard-template
- Reddit PromptEngineering search surface: https://www.reddit.com/r/PromptEngineering/

Access notes:

- X and Reddit are unstable sources for programmatic retrieval and may block direct fetches. Treat them as weak community signals.
- Higgsfield community and official repositories are stronger evidence for structure, layer separation, and preflight discipline, but DIRcreative must not copy platform-specific pricing, model menus, account flows, or private prompts.
- Official model guidance is stronger evidence for generic video prompt anatomy, but model limits still require current local policy, source registry, or tool schema evidence before being written as facts.

## Adopted Lessons

### Prompt Construction Is A Separate Layer

Higgsfield-style prompt skills separate prompt construction from execution. The community prompt skill routes a user request into a production prompt using MCSLA: Model, Camera, Subject, Look, Action. The official Higgsfield skills then execute through their own CLI-backed skill surface.

DIRcreative adoption:

- Keep DIRcreative as prompt-only or assisted-generation depending on current capability and user authorization.
- Do not add a Higgsfield MCP, CLI, account, pricing, or generation dependency.
- Preserve the layer split: source truth -> prompt construction layer -> pre-delivery harness -> execution mode -> QA/retry.
- Use MCSLA as a compact mental check, then expand into DIRcreative's six-slot scene check: camera, subject, action, setting, style, lighting.

### Shot Prompts Need Time-Bound Micro-Scenes

The Sora guide frames video prompting as storyboard-like shot direction: clear framing, action in beats, lighting/palette, recognizable subject anchors, and iteration through small changes. Community AI-video prompting discussions on Reddit and X show the same practical pattern: the useful prompt is a micro-scene, not a pile of adjectives.

DIRcreative adoption:

- Every video prompt should describe one visible change over time.
- Use this micro-scene beat sheet before final prompt text:
  - initial visible state,
  - trigger or pressure,
  - subject action path,
  - camera start target,
  - camera end target,
  - timing beat or pause,
  - final visible state,
  - sound or silence policy when relevant.
- Do not combine several unrelated actions, multiple camera moves, and a tonal slogan in one shot prompt.
- When a prompt fails, change one variable: action, blocking, camera, light/style, reference binding, or output control.

### Professional Storyboard Images Are Production Documents

Boords' storyboard template guidance emphasizes shot-level annotations, camera movement, transitions, and visual intent. Community AI-video prompt examples also tend to improve when a storyboard cell contains enough production information to translate into camera and motion language.

DIRcreative adoption:

- A director storyboard image is not a mood collage, poster, or generic 3x3 panel.
- Each professional storyboard cell must include:
  - shot id and timecode,
  - narrative purpose,
  - shot size and frame description,
  - lens/support/movement,
  - camera position and camera path,
  - subject blocking and movement path,
  - continuity lock,
  - sound/edit cue,
  - transition logic,
  - model risk.
- Visible cell text may be compact, but it must be shot-card language. Thin labels such as `wide`, `close-up`, `slow push`, or `emotional ending` are not enough.

### Asset Roles Must Stay Separated

Higgsfield-style skills and broader AI-video practice both benefit from named reference roles: identity, scene, motion/storyboard, style/material, clean start/end frame, and final video prompt. Overloaded boards make video models misread planning documents as literal frames.

DIRcreative adoption:

- Ask for or simulate material selection before prompt compilation.
- Separate character identity reference, scene geography/FOV reference, professional storyboard + motion map, style/material board, and clean direct I2V frames.
- Mark storyboard and dense boards as planning-only unless a model-specific adapter has verified they are allowed direct inputs.
- Keep clean frame prompts no-text, no-label, no-arrow, and no-panel.

### Community Recipes Are Patterns, Not Truth

Reddit and X prompt recipes can reveal useful structures, such as micro-scene beat sheets, negative constraints, and camera/action separation. They cannot prove current model behavior, duration limits, supported reference slots, pricing, account state, or availability.

DIRcreative adoption:

- Use community recipes only as reusable structure.
- Verify model facts through local policy, source registries, official docs, or current tool schemas.
- Do not copy a public prompt wholesale into DIRcreative docs or prompt manifests.
- Record source strength in research notes and keep uncertain claims out of locked prompts.

## DIRcreative Pre-Delivery Addendum

Before exporting a prompt learned from external/community practice, check:

1. Source strength: official/source repo/community weak signal.
2. Transfer boundary: what is structure, and what is model/platform fact.
3. Material role: identity, scene/FOV, storyboard/motion, style/material, clean frame, or video prompt.
4. Micro-scene completeness: initial state, trigger, action path, camera start/end, timing, final state.
5. Storyboard cell completeness: professional shot-card text, not thin labels.
6. Negative constraints: targeted to the smallest likely failure.
7. Falsifiable pass/fail rubric: visible criteria before generation/import.

If a community recipe bypasses any of these checks, mark `community_recipe_overfit` or `plausibility_over_verification` and route to the smallest corrective artifact.
