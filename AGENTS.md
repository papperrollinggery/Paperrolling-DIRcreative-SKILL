# Agent Instructions

## Repository Self-Maintenance Mode

Treat work in this source repository as Skill maintenance by default, regardless
of its checkout directory name (including `DIR SKILL`).

- Do not invoke an installed `dircreative` Skill while changing or reviewing this
  repository's code, documentation, schemas, tests, installer, or package layout.
- Mentions of advertising films, scripts, storyboards, video prompts, or
  DIRcreative inside a maintenance request do not start Director Room or any
  DIRcreative runtime workflow.
- Run DIRcreative runtime code only when a test command explicitly selects an
  isolated fixture or temporary project.
- Use the ordinary Git and Python repository workflow for source maintenance.
- This section governs only the source repository. It must not be copied into the
  installed DIRcreative Skill or alter normal explicitly invoked Skill behavior.

## Scenario and model adaptation

- Start from the requested result and current stage: bounded text/prompt edits,
  reference-video distillation, full preproduction, initial asset creation,
  reference-based edits, shot/clean-frame generation, or output review. Keep
  planning, compilation, generation and acceptance separate.
- Reuse the existing scenario/gaps/staged-pass selector. Preserve selected craft
  and its artifacts when attaching an execution adapter; do not introduce a
  second router or force every image through one provider.
- A new asset needs design evidence before generation. Its own finished image
  and post-generation stress report cannot be prerequisites for creating it.
- Model upgrades require a focused audit of relevant Skills and instructions
  against current official model guidance. Preserve user facts and domain
  contracts; remove demonstrated contradictions and accidental restrictions.
  Do not change model configuration or weaken evidence because a model is newer.
- Test the changed scenario and a contrasting unaffected scenario. For execution
  changes, include a from-zero fixture and actual installed-provider replay;
  mock-generated images or receipts do not prove forward production succeeds.
- Run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/validate_project.py` on the frozen
  release candidate. Keep generated media and host-specific evidence outside the
  source tree; use the existing release/install gates for publication.

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `papperrollinggery/Paperrolling-DIRcreative-SKILL`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default Matt Pocock skills triage label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain-doc layout: root `CONTEXT.md` plus root `docs/adr/` when present. See `docs/agents/domain.md`.
