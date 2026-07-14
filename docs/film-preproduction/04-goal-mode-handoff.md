# Goal Mode Handoff

Status: active handoff

Current phase: none, all planned phases complete

Repository: `Paperrolling-DIRcreative-SKILL`

## Objective

Make the repo safe for Goal-mode and gstack-driven continuation.

The planned execution goal is complete through WYSIWYG workbench planning, the Phase J model-safe reference pack policy, and the Phase K longform/capability-aware workflow. Future workers should run validation, inspect the completion audit evidence, and only start new work after a new phase or user decision is added.

## Read First

Read these files in order:

1. `README.md`
2. `docs/film-preproduction/01-system-plan.md`
3. `docs/film-preproduction/02-execution-roadmap.md`
4. `docs/film-preproduction/03-office-hours-optimization-plan.md`
5. `docs/film-preproduction/05-skill-integration-architecture.md`
6. `docs/film-preproduction/06-gstack-execution-goal.md`
7. `docs/film-preproduction/goal-mode-simulation-protocol.md`
8. `docs/film-preproduction/phase-contracts.yaml`

## Goal Mode Simulation Rule

If the user asks to test normal operation in Goal mode and says they will not keep sending `1` or manual choices, do not wait at every creative gate. Run `阶段: 目标模式模拟测试`, show the normal `用户确认点`, record `模拟用户选择`, continue through the prompt-only workflow, and end with `阶段: 模拟测试结论`.

This is dry-run evidence only. It cannot create `.dircreative/runs/live-user-acceptance.yaml`, cannot set `real_user_co_creation_verified: true`, and cannot close the active goal.

## Completed Reusable Inserts

These planning inserts are complete and should be treated as reusable context:

```text
docs/film-preproduction/research/image-prompt-style-system.md
docs/film-preproduction/schemas/image-prompt-style-config.schema.json
docs/film-preproduction/templates/image-prompt-style-config.template.json
docs/film-preproduction/prompt-pattern-registry.json
docs/film-preproduction/05-skill-integration-architecture.md
docs/film-preproduction/06-gstack-execution-goal.md
docs/film-preproduction/schemas/skill-orchestration.yaml
docs/film-preproduction/longform-decomposition-policy.md
docs/film-preproduction/capability-aware-generation-policy.md
docs/film-preproduction/schemas/sequence-plan.yaml
docs/film-preproduction/schemas/longform-reference-pack.yaml
```

They are reusable context for image prompt compiler, video model adapter, skill packaging, self-update, director-room orchestration, longform planning, and capability-aware generation.

## Active Phase

```yaml
phase_id: phase_b_story_fixture_completion
name: Story fixture completion
status: completed
```

```yaml
phase_id: phase_c_script_and_breakdown_fixture
name: Script and breakdown fixture
status: completed
```

```yaml
phase_id: phase_d_shot_design_fixture
name: Shot design fixture
status: completed
```

```yaml
phase_id: phase_e_visual_bible_reference_pack
name: Visual bible and reference pack
status: completed
```

```yaml
phase_id: phase_f_image_prompt_compiler_design
name: Image prompt compiler design
status: completed
```

```yaml
phase_id: phase_g_video_model_adapters
name: Video model adapters
status: completed
```

```yaml
phase_id: phase_h_skill_packaging
name: Skill packaging
status: completed
```

```yaml
phase_id: phase_i_wysiwyg_workbench_plan
name: WYSIWYG workbench plan
status: completed
```

```yaml
phase_id: phase_j_model_safe_reference_pack_policy
name: Model-safe reference pack policy
status: completed
```

```yaml
phase_id: phase_k_longform_capability_aware_reference_workflow
name: Longform and capability-aware reference workflow
status: completed
```

## Allowed Edits

No active phase is open. Future edits require a new phase contract or explicit user scope.

Last phase files:

```text
docs/film-preproduction/longform-decomposition-policy.md
docs/film-preproduction/capability-aware-generation-policy.md
docs/film-preproduction/schemas/sequence-plan.yaml
docs/film-preproduction/schemas/longform-reference-pack.yaml
docs/film-preproduction/reference-locking-policy.md
docs/film-preproduction/schemas/reference-pack-manifest.yaml
docs/film-preproduction/schemas/image-prompt-manifest.yaml
docs/film-preproduction/schemas/video-prompt-manifest.yaml
skills/dircreative/reference-image-planner/SKILL.md
skills/dircreative/image-prompt-compiler/SKILL.md
skills/dircreative/video-model-adapter/SKILL.md
skills/dircreative/sequence-planner/SKILL.md
skills/dircreative/longform-reference-planner/SKILL.md
skills/dircreative/edit-assembly-planner/SKILL.md
examples/product-ad-raincoat/10-sequence-plan.yaml
examples/product-ad-raincoat/11-longform-reference-pack.yaml
scripts/validate_project.py
docs/film-preproduction/phase-contracts.yaml
```

Optional if needed:

```text
README.md
```

## Standing Boundaries

Do not:

- implement frontend,
- add dependencies,
- generate production images or videos,
- publish plugin.

The current repo remains a local skill workflow and planning package until the user authorizes implementation or media generation.

## Done When

Phase K is complete because:

- longform policy defines 15s, 60s, 90s, and 180s sequence workflows,
- capability policy defines prompt_only, assisted_generation, and external_generation,
- reference/image/video manifests now carry visual output mode, execution capability, and asset output status,
- sequence-plan and longform-reference-pack schemas exist,
- RainLock has a 180s hybrid prompt-only fixture,
- Zombie Cleaner has a public-reference-inspired 180s prompt-only E2E genre-short fixture,
- QA and retry rules cover longform and capability failures,
- verification commands pass.

## Verification Commands

Run:

```bash
ruby -e 'require "yaml"; Dir["docs/film-preproduction/**/*.yaml"].each { |f| YAML.load_file(f); puts "ok #{f}" }'
python3 scripts/validate_project.py
rg -n 'TB[D]|TO[D]O|待[定]|占[位]|x[x]x|FIX[ME]' .
git diff --check
git status --short
```

Expected:

- YAML command exits `0`.
- `rg` exits `1`, meaning no placeholder markers match.
- `git status --short` shows only intended changes before commit and clean after commit.

## Completion Report Format

Use this format:

```text
STATUS: DONE | DONE_WITH_CONCERNS | BLOCKED
PHASE: phase_k_longform_capability_aware_reference_workflow
CHANGED:
- file path
VERIFIED:
- command and result
NEXT:
- exact next phase and files
```

For current state use:

```text
PHASE: phase_k_longform_capability_aware_reference_workflow
```

## Final Phase

After Phase K:

```yaml
phase_id: none
name: Completion audit
target: Validate that the local skill workflow can move from one rough idea to professional preproduction artifacts.
```

Completion audit must inspect real files and command output before marking the goal done.

## Recommended Prompt For Next Goal Run

```text
Use native Goal mode in `<repo-root>`.

Read:
- README.md
- docs/film-preproduction/04-goal-mode-handoff.md
- docs/film-preproduction/05-skill-integration-architecture.md
- docs/film-preproduction/06-gstack-execution-goal.md
- docs/film-preproduction/phase-contracts.yaml

Execute only the active phase.

Respect allowed edits and non-goals.
Run verification commands.
Commit the scoped result if verification passes.
Report STATUS, PHASE, CHANGED, VERIFIED, NEXT.
```
