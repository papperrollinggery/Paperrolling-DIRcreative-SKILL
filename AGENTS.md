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

## Production quality and workflow changes

- Optimize the requested deliverable, not the number of checks or planning
  artifacts. Fix evidenced failures with the smallest coherent change; keep a
  working contrasting scenario. Do not add a router, approval layer, mandatory
  form, provider or universal checklist merely to make the process look complete.
- Preserve the requested scope and quality while optimizing. In particular, a
  requested five-view master stays five-view; do not replace it with one view,
  skip a difficult detail or redefine success to make a test pass.
- Prepare the first generation from the user's visual intent, actual references
  and the current asset's purpose. A simple, fully specified image stays simple.
  Keep craft decisions; exclude management prose and conflicting template defaults
  from model-facing prompts. Create and local edit need different constraints.
- Produce independent content/assets in batches once their shared inputs are
  ready, then review the batch together. Only a defect that affects a real next
  dependency interrupts production. Candidate observations, final acceptance and
  user approval are different; reuse authorization already given by the user.
- A local repair must not silently restage the whole image. Retain the best
  source and inspect both the requested change and non-target deterioration.
  Regressions require a change of method or return to the source, not another
  automatic edit of the latest degraded image. A detector failure is diagnostic
  evidence to investigate, not a reason by itself to redesign accepted content.
- Audit actual stage transitions across story, reference, generation and review.
  Preserve completed work and invalidate only affected consumers. Test batch
  progress, initial output quality and repair fidelity separately; fewer words,
  files or tool calls alone do not establish improvement.
- Use independent review for a release candidate and material unresolved risks,
  not a separate approval ceremony for every routine artifact. Once the agreed
  checks pass, finish the authorized integration, release and installation; do
  not continue optimizing without a new failure or concrete remaining gap.

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `papperrollinggery/Paperrolling-DIRcreative-SKILL`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default Matt Pocock skills triage label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain-doc layout: root `CONTEXT.md` plus root `docs/adr/` when present. See `docs/agents/domain.md`.
