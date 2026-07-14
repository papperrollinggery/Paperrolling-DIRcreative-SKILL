# Director Room Council Protocol

The director room is a structured council stage. It must not collapse into one generic creative summary.

## Purpose

Turn a rough idea into 2-3 professional directions through visible role collaboration. The output is a user-facing choice gate, not a locked final concept.

## Automatic Entry Routing

Read `docs/film-preproduction/director-room-routing.md`, `docs/film-preproduction/schemas/director-role-harness.yaml`, and the canonical typed council result in `docs/film-preproduction/schemas/director-room.yaml` before deciding whether to open or validate this stage.

When a user asks for a non-trivial advertising film, promotional film, brand video, short-form video, film, shoot, shot plan, storyboard, script, or visual-creativity artifact, enter `阶段: 导演组会议` automatically after any unresolved idea-intake gate. The user does not need to name Producer, Director, or any other role. Judge the whole request before generic `title` or `one-line` words: an incidental title/copy deliverable never downgrades an advertising-film + script + storyboard job. Route a genuinely simple rewrite, translation, proofreading task, title-only request, one-line copy request, film review/course/distribution/explanation request, explicit non-creation request, or single factual question to the lightweight path instead.

Automatic entry is a stage-gate decision, not permission to lock a concept. It creates a director-room `needs_user` gate and must return a visible council result before the single user decision question.

## Required Role Seats

Each director room run must include these seats:

- `producer`: channel fit, time budget, deliverable scope, production risk.
- `creative_director`: concept territory, emotional hook, brand or genre taste.
- `director`: scene intent, performance, blocking, camera motivation.
- `screenwriter`: conflict, beat logic, copy, dialogue or no-dialogue policy.
- `cinematographer`: lens, lighting, camera movement, shot grammar.
- `production_designer`: environment, prop, wardrobe, material, palette.
- `editor`: pacing, shot count, transition logic, cut rhythm.
- `sound_designer`: voice, music, ambience, sound effects, silence.
- `model_prompt_engineer`: reference pack impact, image/video model risks, prompt structure.
- `continuity_qa`: contradictions, identity locks, product locks, downstream QA gates.

## Role Harness

Each required seat uses its role contract in `docs/film-preproduction/schemas/director-role-harness.yaml` and emits the canonical role-card shape in `docs/film-preproduction/schemas/director-room.yaml`. Every result card must contain:

- bounded `inputs` and sourced `evidence`;
- a professional `judgment` and typed `quality` result;
- a downstream `handoff` payload;
- the smallest `retry` and retry stop condition;
- lane/mode `execution` provenance.

Seats can be grouped into professional lanes for execution efficiency, but a lane may not reduce a seat to a name in a list. If one role cannot produce its bounded judgment, the controller retries only that seat or stops at the missing user/source decision; it does not silently fill the gap with a generic synthesis.

## Execution Modes

Default live mode is Codex Thread-backed role passes through worker execution when the host exposes Codex Threads and the council work is non-trivial. The legacy `subagent_default` field remains for old artifact compatibility, but the active execution meaning is `codex_thread_default: true`.

Use `docs/film-preproduction/thread-orchestration-protocol.md` before dispatch. Do not create one thread per seat by default. The main-controller should group seats into bounded professional lanes:

1. `creative_story_lane`: creative director, director, screenwriter.
2. `production_image_lane`: producer, cinematographer, production designer, editor, sound designer.
3. `model_continuity_lane`: model prompt engineer, continuity QA.

For each lane, dispatch one Codex Thread with a professional identity, source list, stop condition, expected output, and cleanup rule. If the lane will write or update the director-room artifact, use an isolated worktree worker. Use same-directory read-only workers only for research, review, or cold-review notes. A true-Thread result is incomplete until every default lane records its `lane_id`, real thread id/class, `thread_dispatch_record`, worker receipt, adoption decision, and cleanup status, and each role card links back to that lane thread. Treat these as `real_subagents` only when they are real Codex task threads with recorded dispatch, receipt, adoption, and cleanup evidence; simulated role text is never enough. The main-controller preserves disagreements, arbitrates conflicts, adopts or rejects worker diffs, runs final validation, reports to the user, and archives workers after findings are consumed.

Use simulated role passes only for a non-explicit `standalone_chat` small gate with no durable artifact work and a recorded fallback reason. If the user explicitly requires true Codex Threads, a real worker receipt, or Thread-backed execution and the tool is unavailable, stop with `TOOL_BLOCKED`; do not fall back to simulated role passes. In `orchestrated_worker`, nested dispatch is forbidden: run only the handoff-selected sub-skill, return `open_questions`, and leave dispatch, adoption, and cleanup to ADCO.

For a permitted standalone simulated pass:

1. Write one labeled pass per seat.
2. Keep voice, responsibility, and decision criteria separate.
3. Add a conflict round where seats challenge each other.
4. Add a synthesis round that turns the conflict into user-facing options.
5. Record why Codex Thread-backed role passes were unnecessary for that small standalone gate.

Both modes must produce the same artifact fields.

## Required Rounds

### Round 1: Role Brief Read

Each seat states:

- what it sees in the idea,
- what it protects,
- what it worries about,
- one concrete recommendation.

### Round 2: Disagreement And Pressure Test

Record at least two real tradeoffs. Examples:

- product clarity versus mood,
- commercial objective versus film-grade atmosphere; 商业目标和影视质感冲突时必须写明取舍,
- story ambition versus 15-second legibility,
- dense reference board versus video-model misread risk,
- music energy versus dialogue clarity,
- visual style versus brand or channel fit.

### Round 3: Resolution

The council resolves each major conflict into a production rule. The resolution must be useful for the next skill.

The controller must make an explicit arbitration/ruling when positions conflict. A resolution note records the production rule; the ruling records why that rule won and which downstream owner receives it. Agreement without a real discussion, disagreement, and ruling is not a council result.

### Round 4: User-Facing Options

Create 2-3 options for the user. Each option must include:

- concept name,
- one-line story,
- visual promise,
- production risk,
- downstream reference implication.

The council may recommend one option, but it cannot lock the final direction unless the run is marked `simulated_fixture` or the user chooses in chat.

## Artifact Requirements

Every director-room artifact must conform to the canonical typed council result in `director-room.yaml` and include:

- `schema_version: "2.0.0"` and `artifact_type: canonical_typed_council_result`
- `automatic_routing_decision`
- typed `stage_gate`
- typed `execution.context` and `execution.mode`
- real-Thread `lane_id`, `thread_id`, `thread_class`, `dispatch_record`, `worker_receipt`, `adoption_decision`, and `cleanup_status` when applicable
- `fallback_reason` inside a permitted simulated execution
- `open_questions`
- `role_cards`
- `discussion_rounds`
- `disagreements`
- `arbitration`
- `resolution_notes`
- `user_facing_options`
- `recommendation`
- typed `user_confirmation`
- `final_direction_locked: false` before user choice

## Chat Surface

The chat surface must show enough council work for the user to feel the director room happened:

```text
阶段: 导演组会议
智能体创作内容:
- producer: ...
- creative_director: ...
- director: ...
- screenwriter: ...
- model_prompt_engineer: ...
- continuity_qa: ...

导演组分歧:
- ...
- ...

给你的 3 个方向:
1. ...
2. ...
3. ...

我的建议: ...
用户确认点: 选 1/2/3，或说怎么混合。
```

## Validation Rules

A director-room run fails if:

- a non-trivial advertising film, film, storyboard, script, or visual-creativity task required the director room but was left on the lightweight path,
- a simple rewrite or single factual question was escalated only because it contains a film term,
- role names are present but no role cards exist,
- a required role card is empty or lacks `inputs`, `evidence`, `judgment`, `quality`, `handoff`, `retry`, or `execution`,
- a role card lacks its harness-defined judgment, evidence boundary, quality gate, handoff, or retry path,
- there is no disagreement round,
- there is no resolution round,
- there is no explicit arbitration/ruling before the recommendation,
- a disagreement repeats the same role/position, a resolution does not reference a valid disagreement and ruling, or a recommendation points to an absent option/resolution,
- an explicit true-Thread result lacks thread/dispatch/receipt/adoption/cleanup evidence or uses a simulated fallback,
- `orchestrated_worker` performs nested dispatch, executes a sub-skill outside the handoff, or omits `open_questions`,
- `execution_mode` hides whether Codex Threads, grouped professional lanes, or simulated role passes were used,
- `model_prompt_engineer` does not address reference pack and video-model risk,
- `continuity_qa` does not address identity, product, or story locks,
- the artifact locks the final direction before user choice,
- the chat surface skips the user-facing options gate.
