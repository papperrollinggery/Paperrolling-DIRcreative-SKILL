---
name: dircreative
description: "Use after explicit $dircreative for film concepts, stories, scripts, director or creative groups, shot/asset planning, reference-video analysis, and image/video prompts. Real media execution requires the corresponding authorization. Validated ADCO handoffs are supported. DIRcreative source maintenance is outside this Skill."
---

# DIRcreative

Develop film work and execute authorized assets.
Plans and prompts are not media.

## Invocation Boundary

Start only for explicit `$dircreative` or validated `adco.specialist-exchange`
selecting `dircreative.film-preproduction`. DIR/ADCO source maintenance becomes
`source_maintenance` and stops Skill execution. Use an isolated fixture/project
for runtime tests. Never modify project instructions to activate the Skill.

## Router Contract

Choose the route by unfinished work. Read exactly one selected Route Card and its active
reference together; replace references by stage and reuse loaded bodies.
There are zero unconditional protocol reads. An obvious Fast or Studio request needs no router tool call
before its useful artifact.

**Full film preparation starts in Studio even when images are authorized.**
“做一段短片，视频前的资料和图片都做好” needs story/shot development first.
Delivery executes an already-designed asset; it does not replace the film's craft.

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

Reuse supplied material and preserve the full requested output set. A client
story stops at story; full preproduction continues through script, shots, assets
and prompts without a new message per stage. “先给一句概念” does not cancel the film.

- **Fast:** one bounded change, zero Threads or Director Room. Return the edit.
- **Studio:** one controller, at most three dynamic professional perspectives
  and one critical pass. Establish audience change, core action, dramatic cause,
  visual/sound choices and continuity before technical matrices. Select only
  the perspectives that change this result.
- **Delivery:** validate the active asset/action and its dependencies; execute
  authorized work, inspect the real result, then continue the dependency chain.
  Check tool/reviewer/readback availability early in a real production request.

For `spatial_discussion`, read the current host Visualize contract and use its
response surface or complete fallback. Camera switching is presentation-only;
scene/shot facts remain authoritative. A concise prompt edit remains Fast.

Named 导演组/创意组 use the active craft card's professional judgments. For real
joint/parallel work or ambiguous collaboration read
`docs/film-preproduction/director-room-routing.md`. Perspectives, real subagents
and new user tasks are distinct. Never simulate a claimed delegation. No nested dispatch
through ADCO; disclose an unavailable tool before substituting single-agent work.

## Intelligent Skill Stack

Before a film's first image call, apply `references/shot-development.md`.
Use `select --stage <stage> --format task`: produce the current artifact before selecting
the next stage. Contact/action first draws its
rehearsal, then reviews it. Narrative frames and annotated boards use the
selected Jingzao spec/validator/compiler; the image tool executes that output.
A handwritten image prompt or post-call plan cannot replace this sequence.

Use the existing scenario/gaps/staged-pass selector. One craft owner supplies
the method; add gap-filling collaborators and at most one validator. Attach the
authorized execution adapter without replacing craft or its exact output.
Fast/Studio/Delivery load at most 1/3/1 external bodies inside 14/20/30 KB;
account isolated contexts separately. Prefer the host catalog. Read
`references/visual-skill-stack.md` when provider choice, discovery or a handoff
needs inspection. “已用” requires full-body reading and application, not a name or hash.
Liu/Sophia are explicit overlays; `ai-visual-production-director` is reference-only.

## External User Gates

The only v2 gates are `concept_lock` for unresolved incompatible directions,
`generation_authorization` for unapproved real generation, and
`client_delivery_approval` for an unapproved client-visible action. Existing
scoped authorization satisfies its gate; do not ask twice. “Continue” continues
within that scope. Story/script/shot/visual/reference/prompt/QA are reversible
internal states, not seven approvals. Historical v1 examples and internal
modules cannot reinstate their old confirmation sequence.

Unknown facts block affected claims. State assumptions and continue independent
work; make routine craft judgments. Image/video authorization stays separate.

## State and truth

`standalone_chat` owns response/state. In `orchestrated_worker`, ADCO owns
adoption, versions, visibility and cleanup; DIR returns artifacts, domain QA, status and open questions.

Use `runtime/state-snapshot.schema.json` for pause/resume, multi-file output or
execution records. Read `references/project-hygiene.md` for project files after
the first useful artifact. Preserve one physical owner for identical bytes and
one creative source; derive views and mark only affected dependencies stale.

## Quality and completion

Preserve source truth, project vocabulary, voice and genre.
Use `references/copy-script.md` for language craft; load
`references/humanization-workflow.md` only for requested layered diagnosis,
demonstrated document-scale defects or explicit providers.

Keep Prompt IR model-neutral and compile one selected model surface at a time.
Preserve reference roles, locked acting, scene/support truth and preserve/change
boundaries. Verify current model claims when relevant. Record final generation
candidates in `ai-film-production-ledger`; it neither executes nor approves.

Whole-film coverage follows `references/film-development.md`. Initial design
cannot require its own future image. `visual_assets_complete` requires real
canonical PNGs, visual review and trusted host readback; it never means a finished
video, user acceptance or client/broadcaster approval.

For required real images, run the pre-video gate and complete its executable
missing work. `partial` is a continuation state, not a finished preproduction pack.

Lead with the requested artifact and relevant judgments/limits. Use focused visualization
when it aids a decision, otherwise complete native files and readable text.
Validate the task and dependencies. Stop at a usable result or specific blocker;
plans or receipts do not complete unfinished work.
