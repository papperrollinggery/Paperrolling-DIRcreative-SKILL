# Council Adversarial Review

Verified: 2026-06-06

Purpose: require a compact rebuttal review before DIRcreative locks story/script/shot/prompt/generation work, especially after a demo exposes quality or orchestration failures.

This is a decision harness, not a new production phase and not an external dependency. It must improve judgment without adding unnecessary features, hidden state, or process weight.

## Core Rule

Use council review when the workflow could plausibly pass validation while still failing the user.

The review must challenge:

- whether the user need was understood,
- whether story and script quality are real or only atmospheric,
- whether shot/storyboard detail is production-grade,
- whether product flow fits the user's stage and patience,
- whether skill/code validation covers the actual failure.

The main-controller thread owns user-facing synthesis, conflict arbitration, adoption or rejection, validation, and status reporting. Worker threads may provide read-only dissent, but their findings are advisory until reconciled into repository docs, `.dircreative/runs/`, `skill_run_receipt`, taxonomy, retry rules, or validation scripts.

Required viewpoints are review lenses, not required worker threads. The main-controller may synthesize all five viewpoints directly when the change is small. For non-trivial deliverables, spawn at most one independent read-only validation reviewer by default; use more Codex Threads only when the controller records a lane budget reason in the dispatch record or the user explicitly authorizes a broader review.

## Required Viewpoints

### User Viewpoint

Ask:

- Did the assistant ask what material the user wanted before producing prompts or images?
- Did the output answer the user's actual objection, or continue the previous direction?
- Can the user judge the creative work from chat without opening raw files?
- Are generated assets clearly marked draft, locked, rejected, or needs revision?

Stop if the workflow guesses the next material, treats "可以/通过" as broad approval, or hides the next decision in backend artifacts.

### Professional Film Expert Viewpoint

Ask:

- Is there a story engine: want, obstacle, external pressure, hidden relationship engine, stakes, escalation, turn/reveal, irreversible choice, consequence, and visible ending action?
- Does the script translate that engine into scene objectives, conflict pressure, action beats, reveal/refusal/concession, and end-state change?
- Does every shot have narrative purpose, shot size, lens, camera support, camera position, camera movement, subject movement path, blocking/path, continuity, sound/edit cue, transition, and model risk?
- Does the storyboard/motion page use professional shot-card text instead of thin labels?

Stop if visual style is being used to hide weak drama.

### Product Manager Viewpoint

Ask:

- Which user stage is this: rough idea, complete idea, test/demo, assisted generation, retry, or live acceptance?
- Which intent is active: visual exploration, story rebuild, formal lockable material, retry, thread/workflow audit, or live acceptance?
- Is the workflow asking one useful decision at a time?
- Is the process too heavy for a quick test, or too loose for a lockable production run?
- Are prompt-only, assisted-generation, external-generation, simulation, and live acceptance kept distinct?

Stop if the workflow adds gates without a decision purpose, or skips gates because the user is testing.

### Skill Developer Viewpoint

Ask:

- Can the root skill route the situation to the correct sub-skill without hidden memory?
- Are failure IDs present in taxonomy and retry rules?
- Are rules written as executable checks, not generic values?
- Do sub-skills know when to stop downstream visual work and return upstream?

Stop if a rule lives only in prose and cannot be routed, validated, or recorded.

### Code Researcher Viewpoint

Ask:

- Does `scripts/validate_project.py` check the new durable contract without pretending keyword checks prove quality?
- Does validation cover the files where operators actually work, including root skill, sub-skills, taxonomy, retry rules, and receipts?
- Does objective audit remain the source for completion instead of release gates, generated images, worker reviews, or simulations?
- Is thread use inspected through visible thread IDs, `git worktree list --porcelain`, and reconciled file diffs?
- Are completed disposable workers archived, and is only the active main-controller thread pinned unless a reusable research thread is intentionally active?

Stop if validation can pass while `OBJECTIVE_COMPLETE: NO` is ignored.

## External Research Intake

External community and platform research is allowed only as input to this council, not as production truth.

Use public research to look for patterns such as:

- separating character identity reference, scene/FOV reference, storyboard/motion map, and clean frame,
- using storyboarding and previsualization as planning assets before generation,
- keeping character consistency through dedicated reference assets,
- writing camera/lens/blocking/movement details in prompt bodies,
- using agent guardrails, handoffs, tools, tracing, and validation as a harness rather than relying on hidden chat memory.

Do not copy platform-specific menus, price claims, account behavior, private prompts, or unverified community recipes into core rules.

## Review Output

For each viewpoint, produce:

```text
Position:
Blocking risk:
Smallest correction:
Adopt/reject:
```

The synthesis must include:

- consensus,
- strongest dissent,
- smallest repo change,
- validation that proves the change is wired,
- whether `OBJECTIVE_COMPLETE` remains `NO`.

## Current Demo Lessons

The "back door light" demo must be treated as a negative training case:

- story and script dissatisfaction means visual assets are not locked,
- a director storyboard image with thin text fails professional usefulness,
- material choice must be asked before prompt writing or generation,
- worker thread failures must be cleaned or recorded as infrastructure failures,
- generated images cannot substitute for live user acceptance.
