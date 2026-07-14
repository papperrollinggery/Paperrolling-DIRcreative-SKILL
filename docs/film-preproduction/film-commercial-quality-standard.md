# Film And Commercial Quality Standard

Verified: 2026-06-15

Purpose: define the minimum standard for DIRcreative to operate as a film-grade and commercial-grade assistant, not only a prompt pack.

## Core Rule

DIRcreative must prove quality through visible creative decisions and executable checks.

The workflow is acceptable only when it can explain:

- why the story creates pressure or desire,
- why the commercial offer is clear,
- why the shot design is shootable,
- why the reference assets preserve identity, product, and scene continuity,
- why image and video prompts are ready for the selected output mode,
- why QA can reject, retry, or lock a generated candidate without asking the user to diagnose it first.

## Film-Grade Dimensions

Every narrative or cinematic brief must satisfy these checks before prompt or media generation:

- `story_conflict`: the protagonist has a visible want, pressure, obstacle, decision, or reveal.
- `emotional_turn`: the ending changes how the viewer reads the beginning.
- `screenable_action`: each beat can be shown through action, blocking, sound, or edit rhythm.
- `shot_density`: each shot has one main story job, one camera job, and enough duration to read.
- `continuity_truth`: identity, wardrobe, prop state, scene geography, and screen direction are locked or explicitly unresolved.
- `audio_intent`: dialogue, voiceover, silence, music, ambience, and post-production audio are separated.
- `model_translation`: model risks are named before export, especially storyboard-board misread and clean-frame requirements.

## Commercial-Grade Dimensions

Every brand, product, service, venue, or offer brief must satisfy these checks before prompt or media generation:

- `business_objective`: the intended result is named, such as demand, proof, launch, conversion, retention, recall, or trust.
- `audience_context`: the target audience, occasion, and channel pressure are explicit.
- `product_proof`: the benefit appears as a visible use, before/after, demonstration, comparison, consequence, or memory frame.
- `brand_assets`: logo, package, mandatory copy, typography, and brand constraints are recorded or marked absent.
- `product_lock`: product silhouette, material, scale, use method, logo/text policy, and forbidden drift are frozen before product identity generation.
- `human_strategy`: face visibility, age range, occupation, city temperament, and performance boundary are confirmed when a person appears.
- `delivery_priority`: the first release format and platform priority are set before reference pack or generated asset work.

## Director-Room Tradeoff Rule

`阶段: 导演组会议` must surface at least one film-vs-commercial tension when the brief has business intent.

Examples:

- story suspense versus product proof clarity,
- cinematic restraint versus first-three-second social hook,
- clean product identity versus lifestyle scene emotion,
- beautiful reference board versus direct video input safety,
- fast generation path versus user-lockable asset truth.

The resolution must name the chosen priority and downstream impact.

## Reference And Generation Quality Gate

Before using Creative Production, ImageGen, an external video tool, or any generated/imported media, DIRcreative must prove:

- story, script, shot, visual bible, and reference pack gates are resolved or intentionally simulated in Goal dry-run,
- `pre_generation_contract.status: pass` exists for the exact asset,
- the asset role is one primary job, not a mixed truth source,
- the output mode is explicit: `prompt_only`, `assisted_generation`, or `external_generation`,
- generated candidates are marked `generated_candidate` until self-QA passes and the user locks them,
- failed candidates remain blocked and route to the smallest corrective artifact.

## Pass Criteria

A run is film/commercial quality ready when:

- all required dimensions above are present in docs, fixtures, or receipts,
- quality failures have retry rules,
- the quality audit reports `QUALITY_AUDIT: PASS`,
- release gate still reports `GOAL_COMPLETE: NO` until real user acceptance exists.

## Failure IDs

Use these failure IDs when a quality gate fails:

- `film_story_conflict_missing`
- `film_emotional_turn_missing`
- `commercial_objective_missing`
- `audience_channel_context_missing`
- `product_proof_not_visible`
- `director_room_tradeoff_missing`
- `product_lock_before_generation_missing`
- `generated_candidate_locked_without_self_qa`
- `creative_production_widget_used_as_truth`
- `goal_autorun_claimed_live_acceptance`
