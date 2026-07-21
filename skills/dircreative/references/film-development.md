# Film Development Craft

Use this card for a complete concept or connected story, script, shot, visual,
sound, and prompt plan. The first answer must contain a recommended creative
direction and the usable artifacts the user requested.

## Build the film, not a meeting

Silently lock the supplied audience, objective, proposition, duration, format,
mandatory moments, claims, product/character facts, source assets, and exclusions.
Do not ask for them again.

Develop one strong direction by default:

1. **Dramatic engine** — audience tension, character or viewer desire, opposing
   pressure, the product/brand's causal role, the turn, consequence, and visible
   ending action.
2. **Time design** — hook, escalation, turn, proof, and resolution fit the actual
   duration. Treat model generation-unit limits as production constraints, not as
   the film's story duration.
3. **Image and performance** — each beat has an observable action, readable
   spatial relation, motivated camera choice, and performance intention.
4. **Sound** — use ambience, foley, dialogue/VO, music, and silence to carry
   structure rather than merely decorate it.
5. **Continuity** — lock identity, wardrobe, prop ownership, handedness, product
   orientation, screen direction, geography, light, and changing object states.
6. **Production/model reality** — separate live-action truth, planning boards,
   clean direct-input frames, model-safe units, and postproduction work.

## Whole-film visual asset coverage

For a complete film, derive the image set from the film instead of naming a
generic moodboard pack. Inventory recurring characters, hero products,
state-changing props, distinct scene/geography states, every approved shot, and
the planned video-generation units. Lock the delivery profile first: medium,
duration, aspect ratio, raster, frame rate, action/title safe zones, brand
end-frame duration, audio master requirements, and the target broadcaster or
platform specification. Do not treat a social vertical format as TVC evidence.
Then show a human-readable asset matrix.

The minimum whole-film coverage is:

- one `character_identity_reference` per recurring character and wardrobe-state
  family, unless a supplied locked image already fulfills it;
- one `product_identity_board` per hero product, plus a
  `prop_continuity_board` only for important state-changing props not already
  covered by the product or character lock;
- one `scene_geography_camera_fov_reference` per distinct location/geography
  state, covering all shots that use that scene;
- one individual `storyboard_frame` for every approved shot;
- one or more `professional_storyboard_motion_map` pages whose cells cover every
  approved shot exactly once. Each cell carries narrative purpose, timecode,
  lens/support/movement, blocking/path, continuity, sound/edit, and model risk;
- the `clean_first_frame`, `clean_key_frame`, or `clean_end_frame` assets required
  by every planned generation unit and the selected model strategy;
- a `lighting_material_style_board` only when look/material truth is not already
  locked by supplied references or scene anchors. Do not add a redundant board.

Scene references, individual shot images, and director storyboard pages are
different deliverables. A director storyboard assembles the approved shot
frames and production instructions; it does not replace scene truth or clean
video inputs. Reuse, derive, generate, and assemble are explicit actions.

Use `runtime/visual-asset-plan.schema.json` when this matrix is persisted. Studio
may claim `plan_complete` after inventory-bound coverage is valid, but not image
generation. Persist exact per-shot truth and exact storyboard/direct-input
dependencies; bind the approved shot-card file and preserve each shot's
timecode, duration, narrative purpose, shot design, action, sound/edit, and
continuity/model notes alongside its scene and entity coverage. Each storyboard,
director page, and clean input inherits a hash of the relevant truth. Do not
replace these records with global entity lists. A representative
sample may claim only `sample_plan_complete`. `representative_sample` always
remains incomplete for whole-film coverage.

## Dynamic perspectives

Apply only perspectives that can change the answer:

- `narrative_strategy`: causality, tension, audience meaning, copy, and ending.
- `visual_production`: performance, blocking, camera, art, edit, and sound.
- `model_continuity`: references, identity/prop locks, generation-unit design, and
  likely model failure.

Integrate their judgment into the film. Do not print role cards, vote counts,
minutes, or artificial disagreements. Add one critical pass only when it exposes
a material weakness.

## Output shape

Adapt to the request, usually in this order:

1. recommended concept in one precise paragraph;
2. story or treatment with a clear turn and ending action;
3. timed script/shot plan with image, performance, camera, and sound;
4. whole-film visual asset matrix with counts, coverage, reuse/generate action,
   and dependency order;
5. visual/continuity locks and model-production notes;
6. concise domain QA and genuine unknowns.

Offer alternatives only when they solve materially different strategic choices.
Use `concept_lock` only when those choices are incompatible and guessing would
change the film. Otherwise deliver a best judgment and label assumptions.

Quality is not a gate count. A usable Studio answer makes the narrative causal,
the camera motivated, the sound structural, the production instructions
specific, and the unknowns honest without burying the creative work.
