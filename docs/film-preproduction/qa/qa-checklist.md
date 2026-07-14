# DIRcreative QA Checklist

Use this checklist before handing any artifact to the next skill. A pass means the artifact is usable for downstream production, not merely complete.

## Story Gate

- The idea has a clear channel, audience, duration, and deliverable target.
- Director-room notes include producer, creative director, director, writer, cinematographer, production designer, editor, sound designer, model prompt engineer, and continuity QA tradeoffs.
- The selected concept has conflict, emotional turn, visual hook, channel fit, and production constraint.
- Logline and beat sheet avoid generic mood-only phrasing.
- Treatment describes visible actions, not abstract themes alone.

## Script Gate

- Script separates action, dialogue, voiceover, silence, and sound.
- Every scene has a screenable beat and a clear reason to exist.
- Advertising scripts include product role, benefit proof, offer or memory hook, and brand-safe tone.
- Short-form scripts define the first-frame hook and the final retention beat.
- No line depends on invisible exposition unless voiceover is explicitly intended.

## Shot Gate

- Every shot has duration, purpose, shot size, angle, lens, camera motion, subject action, blocking, and audio fields.
- No shot carries multiple incompatible actions.
- Shot count fits the target duration and channel.
- Camera moves support story, product proof, or emotional transition.
- Blocking preserves continuity of subject, prop, geography, and screen direction.

## Visual Bible Gate

- Identity, environment, product/prop, wardrobe, material, lighting, color, and texture rules are explicit.
- Visual decomposition covers subject, action/pose or blocking, details/appearance, environment/background, lighting/atmosphere, composition/framing, style/camera, colors/palette, materials/texture, proportion/scale, and generation intent.
- Evidence boundaries are explicit: locked facts are separated from unresolved or uncertain details.
- Material truth includes wear, surface behavior, lighting interaction, and artifact risks.
- Visual direction is usable by image prompt compiler without hidden conversation context.
- Reference pack roles are separated: identity, environment, prop/product, storyboard, style, and first-frame roles do not collapse into one overloaded board.

## Reference Pack Gate

- User decision gate is resolved before locked references are used downstream.
- Every reference asset has exactly one primary role and optional supporting roles.
- `visual_output_mode` is explicit: `prompt_only`, `assisted_generation`, or `external_generation`.
- Execution capability receipt records whether image/video generation exists and whether the user authorized it.
- Every reference asset has an `asset_output.status`.
- Master boards, identity/product boards, environment/camera boards, storyboard motion boards, style/material boards, clean first frames, and clean end frames are separated when model safety requires it.
- Dense boards have large readable panels and simple labels.
- Any board with labels, arrows, floor plans, panel borders, shot numbers, or timing notes has a `must_not_animate` warning.
- Direct input policy is explicit for Seedance, Kling, Runway, and Veo.
- Kling and Runway have clean first-frame inputs when enabled.
- Seedance references have explicit role binding expectations.
- Model reference budget is not exceeded.

## Longform Sequence Gate

- 60s, 90s, and 180s projects have a `sequence_plan` before per-sequence prompt work.
- 180s projects default to `hybrid`: full plan first, global visual lock second, one sequence pack at a time after that.
- Every generation unit is 5-15s unless a model-specific policy says otherwise.
- Sequence functions are distinct and sum to the target duration.
- Global continuity anchors are reused across sequence packs.
- Batch mode records accepted risk when per-sequence gates are skipped.
- Edit handoff records incoming transition, outgoing transition, audio handoff, and retry priority per sequence.

## Image Prompt Gate

- Prompt source is JSON-first.
- Prompt manifest records `visual_output_mode`, execution capabilities, and `asset_output` for each image.
- `prompt_only` mode includes enough external generation instructions to be useful without generated files.
- Selected prompt pattern IDs exist in `docs/film-preproduction/prompt-pattern-registry.json`.
- Art-directed layout policy is present.
- Board sections have role, hierarchy, placement logic, and readable exact labels.
- Material truth and surface integrity guard are present when subject surfaces matter.
- Evidence policy is present for complex image assets and blocks invented logos, exact text, locations, camera bodies, lens models, hidden objects, or offscreen props.
- Prompt layers are present for complex image assets: full director prompt, reusable core prompt, and targeted negative prompt.
- Type treatment is selected when the asset is a portrait, product, poster/ad, UI, illustration, 3D render, or photographic clean frame.
- Consistency locks protect identity, product geometry, wardrobe, prop state, and panel-to-panel continuity.
- Avoid list is targeted, short, and relevant to the artifact.
- Prompt does not ask for fake microtext or evenly distributed generic grids unless a technical subsection requires it.
- Prompt does not rely on standalone filler quality words such as `high detail`, `masterpiece`, `best quality`, `cinematic`, `beautiful`, or `premium`.

## Video Prompt Gate

- Prompt manifest includes reference map, model prompt entries, audio policy, risk notes, and retry rules.
- Video prompt manifest records whether referenced assets are prompt-ready, generated candidates, user locked, external pending, or external imported.
- Missing generated assets are blocked or exported as external-generation instructions; prompts do not pretend missing files exist.
- Longform video prompts preserve sequence IDs for edit assembly.
- Seedance, Kling, Runway, and Veo prompts differ materially.
- Storyboard/reference boards are marked as production guidance only.
- Audio is separated from visual motion.
- Model-specific rules are followed: Seedance uses reference map and shot flow, Kling focuses subject/background movement, Runway stays motion-first and positive, Veo uses structured components.
- Dense boards are not treated as first-frame inputs for models that need clean image-to-video frames.
- Video adapter respects reference pack direct input policy and blocks unsafe direct use.

## Prompt-System Closure Gate

- Supplied user/client/project assets were read before regeneration and have source, hash, role, inheritance, reuse action, and lock status.
- Prompt IR validates against the executable v1.1 JSON Schema; the YAML file is used only as an authoring template.
- Every person, product, and prop has a stable entity, external name, action ownership, starting position, and final state.
- Dialogue and event sounds bind to a valid speaker or source entity.
- Shot and generation-unit timelines are contiguous and exactly cover target duration.
- Targets longer than one generation unit carry explicit incoming/outgoing state across units.
- Image prompts include composition and four-layer Look cards; unused layers are explicit none by design.
- Video prompts include subject, object, environment, camera start/path/end, time beats, audio, transitions, and conditional Look triggers.
- The final selected-model prompt is compiler-derived and contains no internal shot/asset labels, paths, hashes, manifest fields, failure IDs, or retry instructions.
- The terminal prompt names only references actually attached to the selected adapter run; planning-only assets remain internal.
- QA/retry, capability evidence, rights evidence, and post-production-only audio remain in internal receipts or handoffs.
- The minimal character + scene fixture passes without storyboard, material/light board, or clean-frame requirements.
- The multi-character fixture preserves identity, action, speaker, screen position, and prop ownership.
- Structural scores are computed by the validator/compiler and match the recorded fixture score.
- Same-layer retry count remains inside the convergence budget; repeated non-improvement escalates or stops.
- Historical cleanup candidates are proven unreferenced and regenerable or explicitly authorized before deletion.
- Receipt states prompt_only or instructions_only until external generation evidence exists; after generation it must return self-QA, status, next_action, and user lock/revise state.

## Generation QA Gate

- Review checks character/product drift, location confusion, prop state, camera motion, unwanted labels, surface artifacts, and audio mismatch.
- Review checks invented visual facts against locked evidence and visible output.
- Review checks that negative prompts address the smallest observed failure instead of using a generic artifact dump.
- In longform mode, review localizes failures to global pack, sequence pack, clean frame, model prompt, or edit assembly.
- In prompt-only mode, review checks prompt completeness and external instructions instead of image/video pixels.
- Failures map to `docs/film-preproduction/qa/failure-taxonomy.yaml`.
- Retry instruction names the artifact to revise and the smallest useful change.
- Reusable findings are written to versioned research docs or the prompt registry and referenced from `.dircreative/state/current.json`; runtime fixtures remain read-only.
- Registry candidates are proposed only when fixture QA improves.
