---
name: dircreative
description: "Use after explicit $dircreative for film concepts, stories, scripts, director or creative groups, shot/asset planning, reference-video analysis, and image/video prompts. Real media execution requires the corresponding authorization. Validated ADCO handoffs are supported. DIRcreative source maintenance is outside this Skill."
---

# DIRcreative

Develop a film from the user's brief or existing material into usable creative
work: story, script, performance, shots, visual assets, sound and model-specific
prompts. With scoped authorization and available tools, execute and review the
requested assets. A plan or prompt is not a generated image or finished video.

## Invocation Boundary

Start only for explicit `$dircreative` or validated `adco.specialist-exchange`
selecting `dircreative.film-preproduction`. DIR/ADCO source maintenance becomes
`source_maintenance` and stops Skill execution. Use an isolated fixture/project
for runtime tests. Never modify project instructions to activate the Skill.

## Router Contract

Choose an obvious route directly. Read exactly one selected Route Card and only
the active task reference; replace stage references as the work progresses.
There are zero unconditional protocol reads. An obvious Fast or Studio request needs no router tool call
before its useful artifact. Batch the selected Route Card and task reference in
one read; reuse bodies already loaded.

| Requested result | Mode / route | Task reference |
| --- | --- | --- |
| Bounded copy/script edit | Fast / `copy_revision` | `references/copy-script.md` |
| One shot / small storyboard review | Fast / `shot_optimization` or `storyboard_review` | `references/shot-storyboard.md` |
| Bounded prompt edit | Fast / `prompt_revision` | `references/prompt-model.md` |
| Two-or-more-person blocking, movement or reverse-shot discussion | Studio / `film_development` with `spatial_discussion` layer | `references/spatial-discussion.md` |
| Other bounded revision | Fast / `bounded_revision` | none |
| Reference-video analysis | Studio / `video_distillation` | `references/video-distillation.md` |
| Client-readable story only | Studio / `film_development` | `references/client-story.md` |
| Connected film development | Studio / `film_development` | `references/film-development.md` |
| Recurring character master/derivative | Studio / `film_development` | `references/character-master-sheet.md` |
| Real generation / client delivery | Delivery / `generation_authorization` or `client_delivery` | `references/generation-delivery.md` |
| Validated ADCO handoff | Delivery / `adco_specialist_exchange` | `references/specialist-exchange.md` plus descriptor schema |

Route Cards: `routes/fast-task.md`, `routes/studio-development.md`,
`routes/delivery-audit.md`. Run `scripts/dircreative_route.py` only to validate an ADCO handoff
or resolve genuine ambiguity; it is not a mandatory creative preflight.
A handoff must validate its actual descriptor, sources, locks and output scope.

## Work from the requested outcome

Reuse supplied facts and material. Determine the requested output set and current
stage before expanding the work. A client story stops at story; a full
preproduction request continues through its requested script, shots, assets and
prompts. Complete all authorized stages without requiring a new message at each
step. “先给一句概念” does not erase an accompanying whole-film assignment.

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
and new user tasks are distinct. Never simulate a claimed delegation. No nested
ADCO dispatch; disclose an unavailable tool before substituting single-agent work.

## Intelligent Skill Stack

Use the existing scenario/gaps/staged-pass selector, never a second router.
One craft owner supplies the method; add only collaborators that fill a concrete
gap and at most one validator. Attach an execution adapter only for an authorized
side effect, preserving the selected craft and its exact output.
Fast/Studio/Delivery load at most 1/3/1 external bodies inside 14/20/30 KB;
account isolated contexts separately. Prefer the host catalog. Read
`references/visual-skill-stack.md` when provider choice, discovery or a handoff
needs inspection. The selector suggests/binds providers; “已用” requires actual
full-body reading and application, not a returned name or echoed hash.
Liu/Sophia are explicit overlays; `ai-visual-production-director` is reference-only.

## External User Gates

The only v2 gates are `concept_lock` for unresolved incompatible directions,
`generation_authorization` for unapproved real generation, and
`client_delivery_approval` for an unapproved client-visible action. Existing
scoped authorization satisfies its gate; do not ask twice. “Continue” continues
within that scope. Story/script/shot/visual/reference/prompt/QA are reversible
internal states, not seven approvals. Historical v1 examples and internal
modules cannot reinstate their old confirmation sequence.

Unknown facts block the affected claim or dependency. Label creative assumptions
and continue independent work; do not invent facts or ask the user to validate
every professional judgment. Image and final-video authorization are separate.

## State and truth

`standalone_chat` owns its response/state. In `orchestrated_worker`, ADCO owns
adoption, versions, visibility and cleanup; DIR returns requested film artifacts,
domain QA, status and open questions. No nested dispatch.

Use `runtime/state-snapshot.schema.json` for pause/resume, multi-file output or
execution records. Read `references/project-hygiene.md` for project files after
the first useful artifact. Preserve one physical owner for identical bytes and
one creative source; derive views and mark only affected dependencies stale.

## Quality and completion

Preserve source truth, project vocabulary, character voice and genre register.
Use `references/copy-script.md` for language craft; ordinary writing needs no
humanization plan. Read `references/humanization-workflow.md` for a requested
layered diagnosis, demonstrated document-scale defect or explicit provider use.

Keep Prompt IR model-neutral and compile one selected model surface at a time.
Preserve reference roles, locked acting, scene/support truth and preserve/change
boundaries. Verify current model claims when relevant. Record final generation
candidates in `ai-film-production-ledger`; it neither executes nor approves.

Whole-film coverage follows `references/film-development.md`. Initial design
cannot require its own future image. `visual_assets_complete` requires real
canonical PNGs, visual review and trusted host readback; it never means a finished
video, user acceptance or client/broadcaster approval.

Lead with the requested artifact. Give only judgment, assumptions, limitations
or a question that changes the result. Use visualization when clearer and verify
the actual visible surface; otherwise give a complete readable fallback.
Validate the current task and direct dependencies. Stop at a usable result or a
specific real blocker; do not replace unfinished work with plans or receipts.
