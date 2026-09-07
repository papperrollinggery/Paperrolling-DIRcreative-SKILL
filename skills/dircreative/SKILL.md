---
name: dircreative
description: "Use after explicit $dircreative for film concepts, stories, scripts, director or creative groups, shot/asset planning, reference-video analysis, and image/video prompts. Real media execution requires the corresponding authorization. Validated ADCO handoffs are supported. DIRcreative source maintenance is outside this Skill."
---

# DIRcreative

Develop film work and execute authorized assets.
Plans and prompts are not media.

## Invocation Boundary

Start only on explicit DIRcreative invocation (for example, `$dircreative`) or validated `adco.specialist-exchange`
selecting `dircreative.film-preproduction`. DIR/ADCO source maintenance stops
runtime execution (`source_maintenance`); runtime tests use isolated fixtures.
Never modify project instructions to activate this Skill.

## Router Contract

Choose the route by unfinished work. Read exactly one selected Route Card and its active
reference together; replace references by stage and reuse loaded bodies.
There are zero unconditional protocol reads. An obvious Fast or Studio request needs no router tool call.
Canonical asset work still uses the stage selector before its first image.

**Full film preparation starts in Studio even when images are authorized.**
Delivery executes already-designed assets after the required film craft.

| Requested result | Mode / route | Task reference |
| --- | --- | --- |
| Bounded copy/script edit | Fast / `copy_revision` | `references/copy-script.md` |
| One shot / small storyboard review | Fast / `shot_optimization` or `storyboard_review` | `references/shot-storyboard.md` |
| Bounded prompt edit | Fast / `prompt_revision` | `references/prompt-model.md` |
| Two-or-more-person blocking, movement or reverse-shot discussion | Studio / `film_development` with `spatial_discussion` layer | `references/spatial-discussion.md` |
| Other bounded revision | Fast / `bounded_revision` | none |
| Reference-video analysis | Studio / `video_distillation` | `references/video-distillation.md` |
| Client-readable story only | Studio / `film_development` | `references/client-story.md` |
| Full film/scene preparation, including real images | Studio / `film_development` | `references/film-development.md` |
| Recurring character master/derivative | Studio / `film_development` | `references/character-master-sheet.md` |
| Execute an already-designed asset / client delivery | Delivery / `generation_authorization` or `client_delivery` | `references/generation-delivery.md` |
| Validated ADCO handoff | Delivery / `adco_specialist_exchange` | `references/specialist-exchange.md` plus descriptor schema |

Route Cards: `routes/fast-task.md`, `routes/studio-development.md`,
`routes/delivery-audit.md`. Run `scripts/dircreative_route.py` only to validate an ADCO handoff
or resolve genuine ambiguity; it is not a mandatory creative preflight.
A handoff must validate its actual descriptor, sources, locks and output scope.

## Work from the requested outcome

Preserve supplied material and the whole requested output set. Story-only stops
at story; full preparation continues through script, shots, assets and prompts.
A first concept does not cancel the remaining film work.

- **Fast:** one bounded change, zero Threads or Director Room. Return the edit.
- **Studio:** one controller, at most three dynamic professional perspectives
  and one critical pass. Establish dramatic cause, action, visual/sound choices
  and continuity before matrices.
- **Delivery:** check tool/reviewer/readback availability early; validate the
  asset and dependencies, execute authorized work, inspect, then continue.

For `spatial_discussion`, read the current host Visualize contract and use its
response surface or complete fallback. Camera switching is presentation-only;
scene/shot facts remain authoritative. A concise prompt edit remains Fast.

Named 导演组/创意组 use the active craft card. For real/ambiguous collaboration read
`docs/film-preproduction/director-room-routing.md`. Distinguish perspectives,
subagents and user tasks. Never simulate delegation. No nested dispatch
through ADCO; disclose unavailable tools before substituting single-agent work.

## Intelligent Skill Stack

Infer required assets from the requested deliverables and current story, including
“九宫格分镜和相关资产”. Apply `references/shot-development.md` through
`select --stage <stage> --format task`. Recurring human assets default to one
identity per master: frontal portrait plus front, left, right and back full bodies;
read `references/character-master-sheet.md` before designing them. A standalone
portrait or text-only board stays bounded. Initial assets need design, not their
own future images.

For canonical asset generation, use `references/image-execution.md`: prepare the
role-bound Jingzao spec, validate the current packet, submit its returned arguments,
record the real PNG and inspect its role-specific checks before the next image.
Repair failed candidates within scope. A generic compiled prompt, later plan,
or unchecked generation cannot replace this sequence. Contact/action rehearsals
and narrative frames retain their selected craft and coverage requirements.

Reuse the scenario/gaps/staged-pass selector: one craft owner, needed collaborators,
at most one validator. The authorized adapter executes the owner's exact output.
Fast/Studio/Delivery allow 1/3/1 external bodies within 14/20/30 KB; count isolated
contexts separately. Prefer the host catalog; inspect discovery/handoffs with
`references/visual-skill-stack.md`. “已用” requires full-body reading and application.
Liu/Sophia are explicit overlays; `ai-visual-production-director` is reference-only.

## External User Gates

Only unresolved incompatible directions (`concept_lock`), unapproved generation
(`generation_authorization`) and unapproved client-visible actions
(`client_delivery_approval`) need user gates. Existing scoped authorization
satisfies them; “continue” preserves that scope. Reversible craft stages and old
modules cannot impose seven approvals. Keep image/video authorization separate.
Unknown facts block affected claims; state assumptions and continue independent work.

## State and truth

`standalone_chat` owns response/state. In `orchestrated_worker`, ADCO owns
adoption, versions, visibility and cleanup; DIR returns artifacts, domain QA, status and open questions.

Use `runtime/state-snapshot.schema.json` for resume, multi-file output or execution.
For project files read `references/project-hygiene.md` after the first useful
artifact. Keep one physical owner for identical bytes and one creative source;
mark only affected descendants stale.

## Quality and completion

Preserve source truth, project vocabulary, voice and genre. Before affected assets
or prompts, reconcile the current source and adjacent continuity; proposed revisions
do not become source facts. Keep offscreen presence distinct from an actual exit.
Use `references/copy-script.md` for language craft; load
`references/humanization-workflow.md` only for requested layered diagnosis,
demonstrated document-scale defects or explicit providers.

Keep Prompt IR model-neutral; compile one verified model surface at a time.
Preserve reference roles, acting, scene/support truth and preserve/change limits.
Record final candidates in `ai-film-production-ledger`; it neither executes nor approves.

Whole-film coverage follows `references/film-development.md`. Compare the original
requested roles/units with the current plan and inspected outputs before delivery.
`visual_assets_complete` requires real
canonical PNGs, visual review and trusted host readback; it never means a finished
video, user acceptance or client/broadcaster approval.

For required real images, run the pre-video gate and complete its executable
missing work. `partial` is a continuation state, not a finished preproduction pack.

Lead with the requested artifact and relevant limits. Visualize useful decisions;
otherwise provide native files and readable text. Finish required work or report
the specific blocker; plans and receipts do not complete it.
