# Film Development Craft

Use this card for a complete concept or connected story, script, shot, visual,
sound, and prompt plan. The first answer must contain a recommended creative
direction and the usable artifacts the user requested.

## Build the film, not a meeting

Lock supplied audience, objective, proposition, duration, format, mandatory
moments, claims, identities, assets, and exclusions; do not re-ask. Build one
strong direction around audience tension, opposing pressure, brand causal role,
turn, consequence, and a visible ending. Fit hook-escalation-turn-proof-resolution
to real duration; generation-unit limits are production constraints.

Every beat needs an observable start, one decisive action, and a changed end
that motivates the next. Use spatially readable performance, motivated camera,
structural sound, continuity locks, and a clear split between live action,
boards, clean model inputs, model-safe units, and post. A bridge requires causal
or matched action, object, sound, gaze, or geometry. Keep the protagonist.

Before any production matrix, give the client one precise idea, brand role,
beginning-turn-proof-ending story, visual/sound system, and credible route. An
internal transcript, generic shot list, or asset ledger is not the creative idea.

## Keep deliverable layers separate

- A one-to-two-page dual-direction client request returns two complete,
  client-readable stories. Stop before shot rows, asset slots, TN/CG ids, or a
  production worksheet unless the user separately asks for technical production.
- A nine-grid storyboard is nine narrative beats by default. It does not become
  a technical shot list merely because each beat has an image.
- When those frames were generated before identity, production-design, scene-
  geography, or clean-frame assets were locked, classify them as planning-only
  narrative evidence. Recover their useful visible facts, but derive the asset
  foundation before treating any repeated face, costume, vehicle, prop, or
  location as source truth.
- A frame-content request separates `View`, `Storyline`, actual `SUPER`,
  `UI/data`, and proposal-only brand line. `Storyline` states what the frame
  proves and how it hands meaning to the next frame; camera movement belongs in
  `View` or later technical production.
- L1/L2/L3 and `claims_pending_confirmation` remain ADCO/client fact controls.
  Repeat only evidence-bound locked facts. Do not infer algorithms, parameters,
  timing, capabilities, or product ownership from a creative idea.

Do not enter a shot or asset matrix until audience state change, one core action,
brand causal role, start-action-end, media/physical rules, continuity logic, and
sound/edit logic are explicit. Structural coverage proves production planning,
not creative quality, client readability, asset authorization, or approval.

## Whole-film visual asset coverage

Derive assets from the film: recurring identities/states, products/critical
props, scene geography, approved shots, and generation units. First lock medium,
duration, aspect, raster, fps, safe zones, end-frame duration, audio, and target
platform. A social vertical format is not TVC evidence.

The minimum whole-film coverage is:

- one `character_identity_reference` per recurring identity/state family;
- one `product_identity_board` per hero product and only necessary
  `prop_continuity_board` records;
- one `scene_geography_camera_fov_reference` per distinct location/state;
- one individual `storyboard_frame` for every approved shot;
- `professional_storyboard_motion_map` cells covering every shot exactly once,
  with purpose, time, camera, blocking, continuity, sound/edit, and model risk;
- each unit's required clean first/key/end frame;
- a style board only when existing locks do not establish look/material truth.

Scene references, individual shot images, and director storyboard pages are
different deliverables; boards replace neither scene truth nor clean inputs.
Mark reuse, derive, generate, and assemble explicitly.

Canonical asset truth and director-frame quality are independent gates. Asset
identity, topology, geography, and state must survive the shot, but they do not
choose a centered or neutral composition. When polished storyboard or clean
narrative frames are requested and `jingzao-image-forge` is available, route
frame direction and prompt/spec compilation through
`cinematic_storyboard_frames`; image generation remains a later authorized
Delivery action.

Persist with `runtime/visual-asset-plan.schema.json`, bound inventory and shot
cards, exact per-shot time/action/sound/continuity/entity truth, dependencies,
and inherited hashes. Valid coverage allows `plan_complete`, not generation.
A sample allows only `sample_plan_complete`; `representative_sample` always
remains incomplete for whole-film coverage.

## Dynamic perspectives

Use only answer-changing `narrative_strategy`, `visual_production`, and
`model_continuity` judgments. Integrate them silently; no role cards, votes, or
invented disagreement. One critical pass is enough.

## Output shape

Adapt to the request, usually in this order:

1. recommended concept in one precise paragraph;
2. story or treatment with a clear turn and ending action;
3. timed script/shot plan with image, performance, camera, and sound, only when
   the requested layer is technical production or full preproduction;
4. whole-film visual asset matrix with counts, coverage, reuse/generate action,
   and dependency order;
5. visual/continuity locks and model-production notes;
6. concise domain QA and genuine unknowns.

For a whole-film shot table, keep one visible row per formal shot. Start each
row with its canonical `S01`-style ID and include a continuous start-end
timecode so the full duration can be checked without interpreting prose. Each
row must make the start state, single action, end state, causal/match bridge,
media method, and continuity or ambiguity control recoverable from the row.

Offer alternatives only for materially incompatible strategy; only then use
`concept_lock`. Before return, remove stale assumptions and duplication, replace
generic language with observable choices, verify supplied/post-produced facts,
and make the ending resolve the opening. Technical completeness cannot rescue a
weak or misleading direction.
