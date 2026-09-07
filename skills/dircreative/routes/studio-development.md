# Studio Development Route Card

Use for connected film work. Reuse the brief and artifacts; start at the needed stage.

## Budget

- One controller; zero Threads by default.
- One task reference, at most three useful perspectives and one critical pass.
- Zero routing/audit calls before an obvious first artifact; no full-project
  validation. At least 70% of the answer is usable film content or craft judgment.
- Creative perspectives cover audience, concept and brand role; director
  perspectives cover performance, camera and sound. Actual joint/parallel
  dispatch follows `docs/film-preproduction/director-room-routing.md`.

## Execution

1. Produce a recommended direction and usable first-round artifact. Do not re-confirm
   a complete brief. Separate facts from assumptions; missing product evidence
   blocks its claim, not story work.
2. Select the requested layer: `client_story`, `narrative_storyboard`,
   `frame_content_spec`, `technical_production` or `full_preproduction`.
   Client stories, nine-grid narratives and frame specs stop at their layer;
   they do not automatically acquire shot rows or a production worksheet.
   Preserve actual SUPER, UI/data, proposal brand lines and ADCO/client claims.
3. Maintain one creative spine: audience tension, applicable brand role, core action,
   start-action-end, physical/media rules, visual motif, continuity and sound/edit
   logic. Challenge substitutable ideas and unsupported claims with concrete
   alternatives; repair the result in the same turn.
4. For whole-film technical scope, derive assets from recurring identities,
   products/critical props, distinct scenes, shots and generation units. Include
   every scene image, complete director storyboard coverage and required clean
   model-input frames. Use shot frames with an overview, or reviewed model-generated
   boards for `annotated_reference` units. Cover every shot and required phase;
   reuse supplied assets.
   A formal shot row carries its canonical ID and continuous start-end timecode.
5. Continue through every authorized deliverable in dependency order. Use
   `concept_lock` only for a remaining material conflict the user must decide.
   Do not re-approve existing choices or permission.
   In real production scope, check execution/review capability before a large
   asset build, then use the Delivery card for the active media call.
6. Verify the current output and affected dependencies. Mark a representative
   sample as incomplete for whole-film coverage. `pre_video_assets` requires
   `dircreative_pre_video_assets_gate.py` with the bound storyboard-coverage
   sidecar for whole-film/sequence scope before any completion claim; missing
   media/review/readback remains an explicit blocker with usable work preserved.
7. Persist compact state only for pause/resume or multi-file output. Delegation
   uses the consistency-only `dircreative_request_scope_contract.py`; it cannot
   grant authorization. Keep one authoritative source and derive linked views.
8. Inspect project material in place. Follow `references/project-hygiene.md` for
   file work. Keep regenerable QA in replace-current cache; do not duplicate
   source files merely to register them.

For `spatial_discussion`, use its task reference and current host display
contract. Keep viewing presentation-only and finish the requested scope.

Return the actual requested content and necessary limitations. Do not expose
route labels, hashes, role meetings or validation machinery unless asked.
