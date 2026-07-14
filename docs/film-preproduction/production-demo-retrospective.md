# Production Demo Retrospective

Purpose: capture the failures exposed by the "back door light" test run and turn them into durable DIRcreative execution rules. This file is not live acceptance, not a user approval record, and not evidence that the project is complete.

## Status

- Demo status: needs revision.
- Acceptance status: not live acceptance.
- Completion status: `OBJECTIVE_COMPLETE: NO`.
- Required completion evidence remains a real `live-user-acceptance.yaml` created only after explicit real-user acceptance.
- Generated images, storyboard boards, prompt bundles, worker reviews, release gates, and goal-mode simulation are not enough to close the Goal.

## Failures Observed

`story_development_skipped`

The workflow moved into visual production before a professional story engine was locked. A poster mood, reference look, or attractive scene premise did not prove protagonist want, obstacle, stakes, escalation, turn/reveal, irreversible choice, consequence, or visible ending action.

`script_depth_insufficient`

The script material lacked dramatic pressure. Dialogue and scene beats did not carry enough conflict, misdirection, refusal, reveal, concession, or irreversible choice. A quiet slice-of-life tone is allowed only when the relationship engine and external pressure are still active.

`visual_generation_before_story_lock`

Visual assets were generated before story and script lock. This makes downstream images useful as exploration only; they cannot be treated as locked character, scene, shot, or acceptance artifacts.

`storyboard_information_density_too_low`

The storyboard/motion page used thin visible labels. A professional storyboard/motion map must include professional shot-card text for each cell: narrative purpose, timecode, duration, shot size, focal length, lens/support/movement, camera position, camera movement, subject movement path, blocking/path, continuity lock, sound or edit cue, transition logic, emotional beat, and model risk.

`prompt_contract_incomplete`

The visual prompt contract did not carry enough frontstage production detail. A prompt for storyboard or director board output must include character design locks, scene layout locks, prop continuity, camera path, subject path, shot-card text, negative constraints, and falsifiable success criteria inside the prompt body, not only in hidden notes.

`material_selection_missing`

The workflow guessed the requested asset type. Before prompt writing or media generation, show a material selection gate and ask what the user wants next: character identity reference, scene geography/FOV reference, professional storyboard + motion map, selected clean frame, style/material board, first test image, full recommended pack, prompt-only export, or stop.

`thread_control_incomplete`

The main-controller thread did not make worker setup and cleanup visible early enough. failed worktree initialization entries must be inspected, reconciled, and archived when exposed by the thread tools. Worker outputs must be read-only findings unless the main-controller intentionally adopts an isolated worktree change.

## Corrected Execution Order

1. Intent routing gate: identify whether the user is asking for visual exploration, story rebuild, formal lockable material, retry, thread/workflow audit, or live acceptance.
2. Story engine gate: lock protagonist want, obstacle, external pressure, hidden relationship engine, stakes, reversal, irreversible choice, consequence, and setting-as-plot-device.
3. Script tension gate: each scene must have a want, obstacle, tactic change, subtext, visible action, and end-state change; dialogue must create pressure or reveal, not just atmosphere.
4. Shot logic gate: each shot must have narrative purpose, blocking, continuity dependency, and transition logic.
5. Material selection gate: ask which material to produce before prompt writing or generation.
6. Prompt discipline gate: run `production-prompt-discipline.md` and require prompt-window hygiene, reference binding, model constraints, negative constraints, single-variable retry logic, and falsifiable success criteria.
7. Thread orchestration gate: when Codex threads are used, follow `thread-orchestration-protocol.md`; substantive output belongs in worker scope by default, while the main-controller handles adoption or rejection, merge or rollback, cleanup, validation, receipts, status, and Goal completion decisions.
8. Generation QA gate: generated images are draft evidence until QA passes and the user explicitly locks them.
9. Acceptance gate: do not create `live-user-acceptance.yaml` and do not report completion until the real user explicitly accepts in a live chat acceptance pass.

## Professional Story Minimum

Before any visual pack, the story package must answer:

- Who wants what right now?
- What visible force prevents it?
- Why does the scene have to happen tonight, here, in this setting?
- What hidden relationship pressure is active under the dialogue?
- What changes by the end that cannot be undone?
- What final action proves the change on screen?

If these are missing, route back to story-development and mark downstream visual assets as not locked.

Required dramatic pressure card:

```text
Want:
Obstacle:
Tactic:
Subtext:
Turn/reveal:
Irreversible consequence:
Visible ending action:
Setting as plot device:
```

Reject story work that cannot fill this card with specific screenable facts.

## Professional Scene Beat Minimum

Before shot design, each scene must include:

```text
Scene objective:
Opposing force:
Tactic change:
Subtext under dialogue:
Visible action beat:
Turn/reveal:
End-state change:
```

Reject script work that only says what characters feel or discuss.

## Professional Storyboard/Motion Minimum

A director storyboard image is not a mood collage. It must be a production document with cells that can guide staging and model prompting.

Each cell must carry:

- shot id and timecode,
- narrative purpose,
- frame description,
- shot size and focal length,
- camera position and height,
- camera movement,
- subject movement path,
- blocking/path,
- prop continuity,
- light and weather continuity,
- sound or edit cue,
- transition logic,
- model risk and avoid constraint.

Reject any board where visible text only says broad labels such as wide, close-up, slow push, conversation, emotional ending, or final look.

Visible shot-card template:

```text
S03 00:18-00:24 | Narrative purpose: <why the shot exists>
Lens/support/movement: <lens + rig + start/end camera target>
Blocking/path: <subject start -> path -> end, eyeline, axis>
Continuity: <prop/wardrobe/light lock>
Sound/edit: <dialogue/ambience/SFX/music/cut point>
Model risk: <likely misread + avoid clause>
```

## Next-Run Checklist

- Did the user approve or revise the story direction before script work?
- Did the user approve or revise the script tension before shot work?
- Did the user choose the material type before prompt writing or generation?
- Did the storyboard prompt require professional shot-card text and motion-path detail?
- Did the receipt state that generated assets are draft, locked, or rejected?
- Did the main-controller thread reconcile worker findings into repository files, `.dircreative/runs/`, or `skill_run_receipt`?
- Did validation pass without claiming live acceptance?
- Does the objective audit still show `OBJECTIVE_COMPLETE: NO` until real acceptance exists?
