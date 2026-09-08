# Film Development Craft

Use for connected story, script, shot, visual, sound and prompt work. Deliver
the requested creative result first.

## Build the film, not a meeting

Lock supplied constraints without reasking. Build one direction around audience
tension, opposing pressure, turn, consequence and visible
ending. Fit the real duration; generation-unit limits are production constraints.
For branded work, give the brand a causal role.

Co-design story, acting, space and photography before locking shots: wide
geography, medium interaction and close detail each reveal useful information,
without quotas. Let setting enable action, concealment or revelation. Separate
facts from tentative cameras; apply Director Room photography. Preserve causal
cuts, the protagonist and media boundaries.

Before production matrices, give the client a clear idea, causal story,
visual/sound system and feasible route. A transcript or ledger is not the idea.

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
brand role when applicable, start-action-end, media/physical rules, continuity logic, and
sound/edit logic are explicit. Structural coverage proves production planning,
not creative quality, client readability, asset authorization, or approval.

At technical-shot development, follow the active craft handoffs in
`shot-development.md`; replace this general reference at that stage. Infer
full preparation from the requested deliverables, including real images before
user-run video generation. Read/apply the relevant shot, action and camera
method before frame compilation; a planned provider name is not use.

## Whole-film visual asset coverage

Derive assets from the film: recurring identities/states, products/critical
props, scene geography, approved shots, and generation units. First lock medium,
duration, aspect, raster, fps, safe zones, end-frame duration, audio, and target
platform. A social vertical format is not TVC evidence.

The minimum whole-film coverage is:

- one `character_identity_reference` per recurring identity/state family; new
  clothed-human work follows `character-master-sheet.md`, while this film layer
  records only the active version/hash and shot/state dependencies;
- one `product_identity_board` per hero product and only necessary
  `prop_continuity_board` records;
- one `scene_geography_camera_fov_reference` per distinct location/state;
- readable coverage of every approved shot and required phase, using individual
  `storyboard_frame` images plus an assembled overview, or a unit's explicitly
  selected `annotated_reference` model-generated board with current review and
  supported Prompt IR attachment;
- only the clean inputs required by the selected model/unit strategy; no
  per-shot first/key/end quota;
- a style board only when existing locks do not establish look/material truth.

Apply `storyboard-motion-planning.md` for early action drawings and model-drawn
annotations. A final frame overview follows the individual-frame strategy.
Deliver image files, copyable text and a short index by default. Reuse ledger
data; do not add a website/workbench or local server for routine browsing.
Keep necessary spatial/camera interaction in its focused viewer.

Scene references, individual shot images, and director storyboard pages are
different deliverables; boards replace neither scene truth nor clean inputs.
Mark reuse, derive, generate, and assemble explicitly.

For requested detailed/full preproduction, a per-shot frame is only a
representative. At the coverage stage use `storyboard-coverage.md`: derive the
plan ledger, action panels and necessary reverse/reaction coverage before
production. Require its design/assets checks in addition to legacy coverage;
`visual_assets_complete` alone does not certify action-panel completeness.

Reselect craft per stage. `pre_video_assets` makes required images but defers
video; planned rows stay incomplete. Use the character contract for recurring
identities. Cinematic storyboard and clean narrative frames use the existing
Jingzao handoff; complex spec/reference/edit assets use `visual_asset_compile`.
Simple standalone images stay direct. `rough_planning` stays ungated; clean/full
preproduction needs the asset gate and scoped Delivery authorization.
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
row must make the start state, connected main event, end state, causal/match bridge,
media method, and continuity or ambiguity control recoverable from the row.

Offer alternatives only for materially incompatible strategy; only then use
`concept_lock`. Before return, remove stale assumptions and duplication, replace
generic language with observable choices, verify supplied/post-produced facts,
and make the ending resolve the opening. Technical completeness cannot rescue a
weak or misleading direction.

Before delivery, check speakability, dramatic purpose, source fidelity and project
voice using `copy-script.md`. Existing prose can establish a VOICE PROFILE; a
register choice suffices for new writing. Use `humanization-workflow.md` and its
helper only for requested layered work, a demonstrated document-scale defect or
an explicitly selected provider. Follow that reference's evidence/preservation
contract; protect IDs, timecodes, SUPER, claims and paste-ready model syntax.

For explicit groups/parallel work follow `docs/film-preproduction/director-room-routing.md`.

For video prose use `prompt-structure.md`: source facts, evolving events and their camera/sound.
