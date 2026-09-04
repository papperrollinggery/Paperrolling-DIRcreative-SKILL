# Studio Development Route Card

Use for a complete concept, story plus script, script plus storyboard, or another
connected preproduction output set.

## Budget

- One controller; zero Threads by default.
- One task reference, at most three useful perspectives, at most one critical
  pass, and zero full-project validation.
- Zero routing or audit tool calls before an obvious standalone first artifact.
- At least 70% of the answer should be film content or decision-useful craft.

## Execution

1. Reuse supplied brief facts without asking for them again.
2. Deliver a recommended concept and a usable first-round artifact before any
   process explanation.
3. Apply only the perspectives that can materially improve the result; integrate
   their judgment instead of showing role cards or meeting minutes.
   Keep one creative spine from audience tension through brand role, causal
   story, visual motif, proof, and ending. Reject generic mood words, parallel
   ideas that do not change the strategy, and unsupported UI/data/brand claims.
4. Select the requested deliverable layer before expanding the work:
   `client_story`, `narrative_storyboard`, `frame_content_spec`,
   `technical_production`, or `full_preproduction`. A one-to-two-page client
   story, nine-grid narrative, or frame-content specification stops at its own
   layer. It must not acquire shot rows, asset slots, TN/CG ids, or a production
   worksheet by default. Keep actual SUPER, UI/data, and proposal brand lines
   separate; keep L1/L2/L3 and pending claims with ADCO/client evidence.
5. Before any technical matrix, lock audience state change, one core action,
   brand causal role, start-action-end, media/physical rules, continuity, and
   sound/edit logic. For an explicitly requested whole film or complete
   technical multi-output scope, derive and show the
   visual asset matrix from the actual characters, products/critical props,
   distinct scenes, approved shots, and generation units. It must include every
   scene image, one individual storyboard frame per shot, complete director
   storyboard coverage, and the clean model-input frames the selected strategy
   needs. Reuse a locked supplied asset instead of regenerating it.
   In a formal shot table, give every row its canonical `S01`-style ID and an
   explicit continuous start-end timecode; do not hide the timeline in prose.
6. Use `concept_lock` only when incompatible directions would create materially
   different films. Do not manufacture alternatives or conflict.
7. Validate current outputs and dependencies. Label a representative sample as
   incomplete for whole-film coverage; `pre_video_assets` requires
   `dircreative_pre_video_assets_gate.py` before return.
8. Persist compact state only for a pause, cross-session resume, or multi-file
   output that genuinely needs it. Delegation must pass the consistency-only
   `dircreative_request_scope_contract.py`; it grants no authorization.
9. For existing projects, inspect supplied materials in place. Do not copy a
   source, reference, preview, or old immutable delivery merely to register it.
   Put regenerable QA in a replace-current cache and make one organization offer
   after the creative artifact when the read-only scan finds material disorder.

Do not narrate routes, paths, Git, receipts, hashes, gates, validation commands,
or internal roles unless the user asks. `no_material_conflict` is an internal
condition, not user-facing ceremony.
