---
name: dircreative-co-creation-gate-runtime
description: Track user creative approvals, fixture simulations, and pending media blockers before downstream artifacts are locked.
---

# Co-Creation Gate Runtime

## Required Knowledge

- `docs/film-preproduction/co-creation-gate-policy.md`
- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/schemas/co-creation-run.yaml`
- `docs/film-preproduction/phase-contracts.yaml`
- `docs/film-preproduction/capability-aware-generation-policy.md`

## Inputs

- current project artifacts
- proposed creative options
- current visual output mode
- current longform generation mode
- user decision or fixture decision source

## Outputs

- co-creation run manifest
- gate status report
- next user decision prompt
- media blocker list

## Visual Decision Contract

Use `skills/dircreative/assets/visualizations/stage-surface-registry.json#confirmation-echo`. After the controller writes the result and affected project records, create a `dircreative.chat-visualization-writeback@1.0` receipt and validate it with `scripts/dircreative_visualization_writeback.py`. Keep ids, hashes, write targets, lock records, stale markers, and protocol status in that backstage receipt. The visible confirmation says only what the user chose, whether it is confirmed, one production judgment, what continues unchanged, what needs another look, and what comes next. Render it read-only: no action button, no `sendFollowUpMessage`, and no generation or acceptance authority.

## Rules

- Record every creative approval as `real_user`, `simulated_fixture`, or `pending`.
- Use `simulated_fixture` only for examples and dry-run tests.
- Do not mark taste, story, visual style, reference, clean-frame, or video-prompt choices as `system_default`.
- In live runs, do not approve a gate unless the user chose or confirmed the option.
- Present options before locking concept, story, script, shot list, visual direction, visual bible, sequence plan, global reference pack, sequence reference pack, clean frames, or model video prompts.
- Present those options in chat and ask one user decision at a time.
- Resolve the earliest unresolved creative gate first; "可以", "继续", or "测试一下" is not approval to skip story, script, shot list, or visual bible gates.
- When a user changes a core premise, protagonist, product, channel, duration, tone, reference lock, or safety boundary, mark affected downstream gates and artifacts as stale, block prompt/media generation, and ask one revision-scope question before new downstream locks are written.
- Keep reference pack, clean-frame, image generation, and video prompt choices blocked until story/script/shot/visual bible gates are visible and approved.
- Keep `clean_frame_gate` and `video_prompt_gate` blocking `media_generation` while pending.
- When checking whether a workflow works, run `python3 scripts/dircreative_run.py status --example <example>` and `python3 scripts/validate_project.py`.

## skill_run_receipt

Record run type, decision sources, pending gates, media blockers, user-visible next decision, QA status, and `next_recommended_skill`.
