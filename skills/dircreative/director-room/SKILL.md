---
name: dircreative-director-room
description: Run role-based creative discussion and select a professional direction.
---

# Director Room

## Required Knowledge

- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/professional-agent-voice-standard.md`
- `docs/film-preproduction/director-room-council-protocol.md`
- `docs/film-preproduction/director-room-routing.md`
- `docs/film-preproduction/schemas/director-role-harness.yaml`
- `docs/film-preproduction/customer-visible-production-gates.md`
- `docs/film-preproduction/schemas/director-room.yaml`
- `docs/film-preproduction/research/channel-playbooks.md`
- `docs/film-preproduction/research/film-production-glossary.md`

## Automatic Entry And Role Harness

Read `director-room-routing.md` before deciding whether this stage is needed. When a user asks for a non-trivial advertising film, promotional film, brand video, short-form video, shoot, shot plan, film, storyboard, script, or visual-creativity artifact, enter `阶段: 导演组会议` automatically after any unresolved idea-intake gate. The user does not need to name Producer, Director, or any other seat.

Judge overall intent before generic lightweight words. A request for an ad film plus script and storyboard remains director-room work when it incidentally asks for a title or one line. Keep genuinely bounded rewrites, translations, proofreading, title-only/one-line copy work, film reviews, courses, distribution questions, explanation-only requests, explicit non-creation requests, and single factual questions on the lightweight path.

For an activated room, load every required role contract in `schemas/director-role-harness.yaml` and emit the canonical typed council result in `schemas/director-room.yaml`. A role card is valid only when it contains non-empty `inputs`, sourced `evidence`, craft `judgment`, typed `quality`, downstream `handoff`, smallest `retry`, and lane/mode `execution`. The lane map is an execution compression mechanism; it never removes an individual seat's judgment or quality boundary.

The room must return discussion, at least two useful disagreements, an explicit arbitration/ruling, resolution notes, and user-visible options. Role names alone, unanimous summaries, or a recommendation without a user choice gate are invalid.

## Inputs

- project brief
- raw idea
- channel assumption

## Outputs

- director-room notes
- concept options
- selected concept
- unresolved questions

## Roles

Producer, Creative Director, Director, Screenwriter, Cinematographer, Production Designer, Editor, Sound Designer, Model Prompt Engineer, Continuity QA.

## Council Protocol

The director room is a customer-visible council stage, not a role-name checklist.

Default to Codex Thread-backed worker execution for substantive `standalone_chat` work. Read `docs/film-preproduction/thread-orchestration-protocol.md` before dispatching, adopting, archiving, or judging any worker thread. If the user explicitly requires true Codex Threads, every default lane must record its `lane_id`, real thread id/class, dispatch record, worker receipt, adoption decision, and cleanup status, and each role card must link to the lane thread; if the tool is unavailable, stop with `TOOL_BLOCKED`. Simulated role passes are allowed only when true Threads were not explicitly requested and the work is a small standalone chat-only gate with no durable artifact work; record the fallback reason.

In `orchestrated_worker`, do not open role lanes or perform any nested dispatch. Execute only the sub-skill selected by the validated handoff, return `open_questions` (an empty list is valid), and leave worker adoption and cleanup to ADCO.

Do not create one thread per role by default. Group the seats into bounded professional lanes:

- `creative_story_lane`: creative director, director, screenwriter.
- `production_image_lane`: producer, cinematographer, production designer, editor, sound_designer.
- `model_continuity_lane`: model_prompt_engineer, continuity_qa.

Lane workers do the professional-role work. If a lane writes or updates artifacts, dispatch it as an isolated worktree worker. Same-directory workers are read-only and only for research, review, or cold review. The main-controller owns dispatch, synthesis, conflict arbitration, worker diff adoption or rejection, validation, cleanup, and user reporting; it may write receipts, adoption records, and merge or rollback actions, but it must not default to doing the role work itself.

In chat, show role cards for producer, creative_director, director, screenwriter, cinematographer, production_designer, editor, sound_designer, model_prompt_engineer, and continuity_qa before the recommendation.

Required rounds:

1. `Role Brief Read`: every seat gives its own recommendation, concern, and protected value.
2. `Disagreement And Pressure Test`: record at least two tradeoffs that affect story, channel fit, reference planning, model behavior, or production clarity.
3. `Resolution`: turn each useful conflict into an executable production rule for the next skill.
4. `User-Facing Options`: present 2-3 directions and ask the user to choose or mix.

For every disagreement, record the two positions, the arbitration/ruling, and the resulting downstream production rule. If a required role misses its quality gate, retry that seat only with the same accepted locks; stop and ask one bounded question when its missing input belongs to the user.

`model_prompt_engineer` must comment before direction lock on reference-pack structure, image prompt risk, and Seedance/Kling/Runway/Veo interpretation risk.

`continuity_qa` must comment before direction lock on identity locks, product locks, story contradictions, and downstream QA gates.

## Chat Surface

Show the director room result as a visible council meeting plus 2-3 selectable concepts:

- `阶段: 导演组会议`
- `智能体创作内容`: labeled role cards for the required seats.
- `导演组分歧`: at least two useful conflicts and what they change.
- `给你的方向`: 2-3 concepts, each with why it works, tradeoff, and reference-pack implication.
- `我的建议`: one recommendation with a production reason.
- `用户确认点`: ask the user to choose 1/2/3 or mix.

Do not lock a selected concept until the user chooses in chat, except in a fixture marked `simulated_fixture`.

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#director-concept-comparison`. Bind every option to the current director-room artifact, keep two or three directions visible together, and map adopt/mix/revise actions to the current concept gate plus a complete table fallback.

## Rules

- Do not output a single generic summary.
- Do not treat the role list itself as collaboration.
- Each role card must speak from craft expertise and carry its canonical inputs/evidence/judgment/quality/handoff/retry/execution fields; an empty mapping is invalid.
- Preserve useful disagreements and their resolution; reject duplicate/empty positions, unbound resolutions, and recommendations that reference absent options or resolutions.
- Include at least one customer-visible disagreement and one resolution note before asking the user to choose.
- Make channel tradeoffs explicit.
- Select one direction only when it is executable.
- Do not write final script, shot list, image prompts, or video prompts.

## skill_run_receipt

Record execution mode; real thread/dispatch/receipt/adoption/cleanup evidence when applicable; fallback reason for a permitted small standalone simulated gate; role decisions; disagreements; resolution notes; rejected options; selected concept state; `open_questions`; QA gate; and `next_recommended_skill: story-development`.
