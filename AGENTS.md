# Agent Instructions

## Repository Self-Maintenance Mode

When the current Git root is `Paperrolling-DIRcreative-SKILL`, treat work on this
repository as Skill source maintenance by default.

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

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `papperrollinggery/Paperrolling-DIRcreative-SKILL`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default Matt Pocock skills triage label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain-doc layout: root `CONTEXT.md` plus root `docs/adr/` when present. See `docs/agents/domain.md`.
