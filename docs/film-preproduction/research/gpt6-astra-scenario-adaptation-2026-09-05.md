# DIRcreative scenario and GPT-6 Astra adaptation

Date: 2026-09-05. Scope: the v0.8.0 source candidate and instruction behavior.
This report does not certify a release, generated film or user approval.

## Official basis

OpenAI identifies instruction sensitivity, clarification, delegation and excessive
testing as specific Astra migration considerations. Its guidance supports clear
authorized outcomes, explicit Skill conflicts and tests proportional to the
change. These are behavioral adjustments; changing the model name alone does
not validate a workflow. [Official model guidance](https://developers.openai.com/api/docs/guides/latest-model#gpt-6-astra-behavior).

Codex loads global and project instructions in a defined chain at run start.
Instruction edits therefore require a fresh load check, not a claim that an
existing task automatically adopted them. [Official AGENTS.md guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Intended scenarios

| User task | Smallest useful result | Workflow and completion evidence |
| --- | --- | --- |
| A bounded dialogue, text or prompt edit | Revised requested passage | Fast; protect voice and facts; no full film intake or media gate |
| Analyze a reference video | Timecoded observations, uncertainty and filmmaking lessons | Studio distillation; read actual media; separate observation from inferred production method |
| Develop a complete short film | Story, authoritative script, shots, sound, model units and asset plan | Studio; derive work from information/action changes; images required only when the requested scope includes them |
| A simple low-risk image | The requested image or prompt | Concise direct route remains available; authorization and exact active-asset packet apply to real generation |
| A recurring character, complex scene or prop | Asset-specific design, compiled spec and image | Existing Skill Stack chooses needed craft; selected design precedes creation; review follows actual image evidence |
| Edit or repair a referenced image | Minimal requested change with preserve rules | Choose reference/edit/constraint methods for the observed need; retain exact reference bytes and roles |
| Shot boards and clean video frames | Required per-shot/action coverage | Bind scene, support, character and prop truth; assemble overview pages deterministically from reviewed images |
| Seedance 2.5 or 2.0 preparation | Model-scoped generation units and prompts | Actual source dialogue and capability-card limits; require the completed asset/stress pass at this stage |
| Output review and retry | Specific visible findings and one bounded correction | Review saved pixels; distinguish detected structure, semantic judgment, host adoption and user approval |

The scenario/gaps/staged-pass selector remains the sole selection mechanism.
There is no new model-specific router and no requirement to use every provider.
Planning, prompt compilation, generated candidates, QA, adoption, platform
binding and publication remain separate states.

## Demonstrated problems and corrections

1. Authorized `clean_image` and `key_visual` execution was forced into
   `real_execution`, discarding the specialist. Execution now attaches the
   adapter to the selected craft and applies the same packet/scope checks.
2. The first character image required a completed foundation pass containing
   that image. Legacy tests hid the cycle by manufacturing source PNG bytes.
   An in-progress design pass can now bind planned IDs and selected design
   artifacts without a generated image or stress report. It cannot pass the
   final video-compilation validator.
3. Provider and artifact roots could overlap; reference files were read again
   after their hash check; a rejected spec still reached compilation. Roots
   are now disjoint, replay consumes sealed bytes, and validation failure stops
   compilation.
4. Selected provider metadata was counted again as candidate metadata. Near the
   existing context limit this removed required validators and collaborators.
   Selection and final accounting now count each record once; budgets are unchanged.
5. An independent raw-request test found that standalone product and character
   images required a fictitious film timeline. `asset_only` now represents this
   scope in the existing inventory/plan validator, with no timed shots, audio or
   video units. Its completion claim is limited to the asset plan. Direct still
   prompts also omit unsolicited project titles, IDs and hashes that conflicted
   with the user's no-text request.
6. Actual character outputs contained unintended nonopaque alpha, while the
   primary-portrait template inherited a three-quarter view. Neutral-background
   masters now require measured full opacity bound to the review receipt, and
   their default primary portrait is frontal. Generic RGBA assets remain valid;
   the workflow does not flatten or cut out failed source images.

## Instruction scope

Global guidance should retain language, authorization continuity, proportional
testing and bounded delegation. It should not pin the primary controller to an
older model or contain DIR asset rules. The repository AGENTS.md owns source
maintenance, scenario regression and release validation. Installed Skill files
own filmmaking behavior and remain explicit-invocation-only.

The source-maintenance rule now applies regardless of checkout folder name.
The original rule depended on a repository name while the local checkout was
named `DIR SKILL`. No source-maintenance instructions are installed into the
runtime Skill, and no model or reasoning configuration is changed by this work.

## Verification and limits

Regression cases cover specialist retention, missing authorization/packets,
zero-image creation, incorrect design ownership, provider-root overlap,
reference mutation and rejected-spec short-circuiting. The full source validator
and installed-provider replay complement these cases. Their run receipts belong
to the exact candidate used; fixtures do not establish semantic image quality.

Real forward acceptance must independently read the installed candidate and
required provider bodies, produce the requested files, inspect actual images,
and preserve any remaining failures. Neither a ready selector nor a newer model
is evidence that a film has achieved the reference's quality.

### Observed forward-test boundary

The isolated native test made five image calls: one standalone cup and four
character candidates. The cup passed an independent visual check. The first two
character tool outputs had unintended alpha and were rejected without editing.
The next two were fully opaque with frontal primary faces. The last call used an
actually attached 2D composition guide, after the real reference-bearing provider
compile, sealed replay and execution-packet checks passed. It also passed the
Apple Vision four-body structural check and independent view-order inspection.

The final character candidate still failed the requested 3:1 canvas: it was
1717 by 916 pixels, and its portrait included excess shoulder/chest area. The
five-call test stopped with those failures recorded. It did not certify a final
character master, authorize downstream headless derivatives, or validate video.
This is a runtime workflow and failure-handling check, not a sealed exact-release
media certificate or a guarantee that an image provider will obey every prompt.
