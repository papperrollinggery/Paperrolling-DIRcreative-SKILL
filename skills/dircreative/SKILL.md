---
name: dircreative
description: Use only after the user explicitly invokes $dircreative for film preproduction: story, script, storyboard, shot planning, visual systems, reference-image planning, and model-specific video prompts. ADCO mode accepts only a validated Specialist Exchange handoff. Do not use for maintaining, debugging, refactoring, testing, or evaluating the DIRcreative source repository; maintaining ADCO; ordinary code work; factual questions; or generic advertising requests without an explicit $dircreative invocation.
---

# DIRcreative

Run this as a chat-first, artifact-backed workflow.

The user-facing experience should be clear in the conversation. Files are the durable record, not the primary interface.

## Preflight

1. Read `docs/film-preproduction/phase-contracts.yaml`.
2. Read `docs/film-preproduction/chat-co-creation-interface.md`.
3. Read `docs/film-preproduction/professional-agent-voice-standard.md` before any user-visible creative direction, option, script explanation, prompt-only handoff, retry note, or summary.
4. Read `docs/film-preproduction/05-skill-integration-architecture.md` before changing harness, receipts, sub-skill routing, session persistence, or retry loops.
5. Read `docs/film-preproduction/adco-integration-contract.md` before accepting an ADCO handoff, returning a domain deliverable receipt, or changing external-orchestrator behavior.
6. Read `docs/film-preproduction/chat-stage-gate-integrity.md`.
7. Read `docs/film-preproduction/live-chat-start-protocol.md`.
8. Read `docs/film-preproduction/customer-visible-production-gates.md`.
9. Read `docs/film-preproduction/client-film-hard-gates.md` before client-facing relationship, anniversary, brand-story, one-minute, storyboard, PPT, asset-reference, or prompt handoff work.
10. Read `docs/film-preproduction/goal-mode-simulation-protocol.md` if the current message is `goal_context` or asks to simulate normal user operation.
11. Read `docs/film-preproduction/goal-autorun-completion-protocol.md` before Goal autorun, dry-run evidence, completion audit, or simulated acceptance work.
12. Read `docs/film-preproduction/production-demo-retrospective.md` before story, script, storyboard, prompt, assisted generation, external generation, retry, or Goal completion work.
13. Read `docs/film-preproduction/council-adversarial-review.md` before ambiguous go/no-go decisions, user rejection recovery, assisted generation demos, cold review, or Goal completion judgment.
14. Read `docs/film-preproduction/production-prompt-discipline.md` before image prompt, video prompt, assisted generation, external generation, or retry work.
15. Read `docs/film-preproduction/research/ai-video-prompt-community-lessons.md` before changing prompt structure from Higgsfield-style, Reddit, X, or other external/community examples.
16. Read `docs/film-preproduction/thread-orchestration-protocol.md` before creating, forking, dispatching, adopting, archiving, or judging Codex worker threads.
17. Read `docs/film-preproduction/workspace-cleanliness-protocol.md` before thread-backed work, validation, release gates, or cleanup.
18. Read `docs/film-preproduction/project-agents-protocol.md` before proposing, auditing, creating, appending to, editing, or deleting a target project `AGENTS.md`.
19. Read `docs/film-preproduction/06-gstack-execution-goal.md`.
20. Before automatic director-room routing or judging a director-room result, read `docs/film-preproduction/director-room-routing.md` and `docs/film-preproduction/schemas/director-role-harness.yaml`.
21. In `standalone_chat`, before resume, a current-first summary, handoff reconciliation, or a completion claim, read `docs/film-preproduction/runtime-state-governance.md`; run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_state_audit.py audit --project-root <standalone_project_root>` and then `PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_state_audit.py current-index --project-root <standalone_project_root>`. A failed state audit or blocked current index stops the current/complete claim. Under `orchestrated_worker`, do not create a DIR current projection; ADCO owns host current truth.
22. Confirm `execution_context`, the active phase, typed stage gate, allowed edits, stop condition, and acceptance boundary.
23. Load only the knowledge packs required by the selected sub-skill.
24. When the active chat surface supports visualizations or the user requests a visual decision view, read `docs/film-preproduction/chat-inline-visualization-interface.md` and validate the view spec before rendering it.
25. In `standalone_chat`, show the user the current stage, customer-visible creative preview, production judgment, and one decision question. In `orchestrated_worker`, return the preview and decision request to ADCO instead.
26. Write outputs as files with artifact metadata only after the relevant gate is resolved and the active write scope allows them.
27. Write a `skill_run_receipt` in standalone work. Under ADCO, return the neutral `adco.specialist-exchange` provider receipt at the handoff's exact `scope.receipt_path`.
28. Run `python3 scripts/validate_project.py` before reporting completion.

## Live Chat Start Contract

In `standalone_chat`, the first reply must be a visible production-room gate.

- Rough idea: start at `阶段: 想法读取`, restate the brief, infer channel/duration risks, and ask if the brief is right.
- Complete idea: start at `阶段: 完整想法读取`, list what is already locked, state which brainstorming gates are skipped and why, then ask for story-logic confirmation.
- "测试一下", "继续", or "可以": start from the earliest unresolved creative gate. Do not treat those words as permission to jump to image generation.
- Goal mode simulation: when the current message is `<goal_context>` or the user says the test should simulate normal operation without manual `1` replies, enter `阶段: 目标模式模拟测试`, show each normal `用户确认点`, immediately record `模拟用户选择`, and continue through the full prompt-only flow. Do not wait for `1` during this simulation.
- Image request: show the current story/script/shot/reference strategy and block generation until the required assets for the selected route plus `pre_generation_contract.status: pass` are visible. Do not require optional style boards, storyboard boards, or clean frames when the prompt and selected model route do not need them.
- Every first response must include `智能体创作内容`, `专业判断`, and `用户确认点`.
- User-visible wording must pass the professional voice and humanizer check in `professional-agent-voice-standard.md`: concrete judgment, specific tradeoffs, varied rhythm, no chatbot politeness wrapper, no promotional filler, no generic uplift ending.
- Never make files, terminal output, raw YAML, or a single generated image the first user-facing experience.
- Generation decisions must be customer-facing: use `阶段: 出图执行建议`, `阶段: 视频生成建议`, and `阶段: QA 与重试规则`. Keep `阶段: 生成前合同`, raw JSON prompt bodies, YAML manifests, and model prompt text as backstage evidence unless the user explicitly asks to copy them.

## Visual Decision Surface

Treat chat visualization as progressive enhancement to the existing stage gate.

- Choose the smallest view that materially improves the current decision. Use Mermaid for a static labeled relationship, one inline view for one compact decision, and fullscreen only for dense timelines, continuity matrices, reference graphs, or linked QA inspection.
- Keep one current stage, one decision question, one primary action, and at most one secondary action. Do not embed a tabbed Workbench or multi-stage editor in an inline reply.
- Build a `dircreative.chat-visualization@1.0` spec from hash-bound current artifacts and validate it with `scripts/dircreative_visualization_spec.py` before rendering.
- When real generated or imported images exist, show the image itself in the review surface with its bound version/hash, source status, authorization status, channel-fit status, alt text, and concise annotations. Never replace an available image with a text-only QA table.
- A simulated or illustrative image must be visibly labeled `演示参考图`, may not be presented as a real candidate, and may not expose a confirm/use action. Reject missing files, hash mismatches, unsupported image types, and active or externally linked SVG.
- Render supported standalone-chat views with `scripts/dircreative_visualization_render.py render-html --project-root <active-project-root>`; resolve image paths only inside that verified project root, and write a new lowercase hyphenated fragment only inside the current thread's `.codex/visualizations` directory. Never render an `orchestrated_worker` provider spec directly.
- Keep local selection and expansion presentation-only. A visual action sends human-readable conversation intent; it cannot lock, approve, authorize generation, claim readiness, record acceptance, or claim completion.
- Re-read current state and validate the typed gate before any artifact, lock, stale marker, authorization, QA verdict, or receipt write. Then show a confirmation echo and the next visible stage.
- Always include the schema-declared Markdown/table/Mermaid fallback. The workflow must remain complete in Codex CLI, IDE, unsupported accounts, or a failed render.
- In `orchestrated_worker`, return the neutral visualization spec or fallback to ADCO with `controller.user_facing: false`; do not render to the client or handle its action directly.

## Execution Context

Resolve the outer execution context before applying chat or thread rules.

- `standalone_chat`: default when no valid orchestrator contract exists. DIRcreative owns its visible user gate, session loop, worker dispatch, adoption, validation, and cleanup.
- `orchestrated_worker`: use only for a valid `adco.specialist-exchange` v1 handoff whose profile is `dircreative.film-preproduction` and whose descriptor, capabilities, source hashes, execution mode, and exact scopes pass `scripts/dircreative_adco_native_exchange.py validate-handoff`.
- Fail closed on an unsupported protocol/version, unverified descriptor, missing capability, stale source hash, missing work/handoff identity, invalid worker identity, unsafe scope, authority escalation, or incomplete receipt evidence. Return stable failure IDs; do not fall back to standalone behavior inside an ADCO exchange.
- In `orchestrated_worker`, ADCO is the user-facing controller and integration owner. Do not ask the client directly, update the active Goal, decide adoption, archive ADCO workers, or claim client/final readiness.
- Return `open_questions` in every provider receipt; use an empty list when nothing is unresolved. ADCO decides how to surface populated questions.
- ADCO's native default is `execution.mode: inline`. Use `codex_thread` only when the handoff contains a verified real worker UUID; `external_handoff` carries no thread claim. In `orchestrated_worker`, nested dispatch is forbidden: execute only the handoff-selected sub-skill and do not enter adjacent DIRcreative stages or director-room lanes.
- Accept `worktree`, `isolated_workspace`, or `read_only` only from the validated handoff. A `read_only` handoff may grant only its receipt path, never an output root. Write only the requested output kinds and receipt inside `scope.write`; never write a path in `scope.forbidden`, ADCO's control plane, PPT exports, or FinalDelivery.
- Consume exactly the hash-bound `source_truth.artifacts`. Return project-relative, non-empty, SHA-256-bound `output_artifacts`; do not force a private DIR file layout onto ADCO.
- Return the neutral provider receipt with matching exchange/handoff/work/profile, descriptor SHA-256, and handoff SHA-256; consumed inputs; output artifacts; QA; structured questions; execution evidence; recommendation; the negotiated `dircreative.domain-delivery` extension; and `claims.client_ready/ppt_ready/final_delivery_ready/send_ready/project_complete/control_plane_updated: false`.
- DIRcreative owns domain craft and domain QA. ADCO owns current truth, versions, artifact adoption, client gates, exports, and final delivery.
- Map `domain_accepted` to a recommendation for full adoption, `draft_accepted_with_limitations` to internal partial adoption, unresolved client choice to `outcome: needs_user`, and revision/blocked/failed states to reject or defer. Only ADCO writes the separate adoption decision.
- The `dircreative.film-preproduction` v1 exchange is prompt-only: keep `generation_ready: false` and reject every non-`prompt_only` handoff. Real media requires a separately negotiated profile with work/asset/hash-bound authorization and passing pre-generation contracts.

## Routing

### Automatic Director-Room Routing

Do not require the user to name individual roles. Use `docs/film-preproduction/director-room-routing.md` as the routing contract and `docs/film-preproduction/schemas/director-role-harness.yaml` as the role harness.

- A non-trivial advertising-film, promotional-film, brand-video, short-form-video, shoot, shot-plan, film, storyboard, script, or visual-creativity request automatically enters `阶段: 导演组会议` after any unresolved idea-intake gate, with all required professional seats activated through bounded lanes.
- Evaluate overall multi-artifact intent before generic `title`/`one-line` signals. An incidental title or sentence cannot downgrade an advertising-film + script + storyboard request. A genuinely bounded rewrite, title-only task, film review/course/distribution/explanation request, explicit non-creation request, or single factual question remains lightweight.
- Director-room output must show role judgments, discussion, useful disagreements, an arbitration/ruling, resolution notes, and user-visible options before its one decision question. A role-name list is not a council.
- The director room recommends but does not lock final direction until the user chooses, except in a clearly marked `simulated_fixture`.

```text
raw idea -> idea-intake
non-trivial advertising-film / film / storyboard / script / visual-creativity request -> idea-intake if unresolved -> automatic director-room -> user choice gate
simple rewrite / translation / proofreading / one-line copy / single factual question -> lightweight chat response
ADCO native handoff -> descriptor/capability/scope validation -> selected domain sub-skill -> neutral provider receipt -> ADCO adoption
chat interaction -> chat-facilitator
project brief -> director-room
creative approval or pending user choice -> co-creation-gate-runtime
selected concept -> story-development
treatment -> script-treatment
script -> script-breakdown
script breakdown -> shot-design
shot list -> visual-bible
visual bible -> reference-image-planner
longform target -> sequence-planner
sequence plan -> longform-reference-planner
reference pack plan -> image-prompt-compiler
image prompt manifest -> video-model-adapter
generated clips or external clip list -> edit-assembly-planner
generated output or failure -> generation-qa
reusable finding -> learn
source/model/pattern refresh -> update
pause/resume -> checkpoint
```

## Required Knowledge

- `docs/film-preproduction/05-skill-integration-architecture.md`
- `docs/film-preproduction/adco-integration-contract.md`
- `docs/film-preproduction/schemas/adco-specialist-descriptor.json`
- `docs/film-preproduction/chat-co-creation-interface.md`
- `docs/film-preproduction/chat-inline-visualization-interface.md`
- `docs/film-preproduction/chat-stage-gate-integrity.md`
- `docs/film-preproduction/live-chat-start-protocol.md`
- `docs/film-preproduction/client-film-hard-gates.md`
- `docs/film-preproduction/goal-mode-simulation-protocol.md`
- `docs/film-preproduction/live-user-acceptance-gate.md`
- `docs/film-preproduction/live-chat-acceptance-runbook.md`
- `docs/film-preproduction/professional-agent-voice-standard.md`
- `docs/film-preproduction/ad-reference-pack-generation-gate.md`
- `docs/film-preproduction/schemas/skill-orchestration.yaml`
- `docs/film-preproduction/phase-contracts.yaml`
- `docs/film-preproduction/co-creation-gate-policy.md`
- `docs/film-preproduction/production-demo-retrospective.md`
- `docs/film-preproduction/council-adversarial-review.md`
- `docs/film-preproduction/production-prompt-discipline.md`
- `docs/film-preproduction/research/ai-video-prompt-community-lessons.md`
- `docs/film-preproduction/thread-orchestration-protocol.md`
- `docs/film-preproduction/workspace-cleanliness-protocol.md`
- `docs/film-preproduction/project-agents-protocol.md`
- `docs/film-preproduction/research/thread-orchestration-community-lessons.md`
- `docs/film-preproduction/schemas/thread-dispatch-record.yaml`
- `docs/film-preproduction/schemas/thread-dispatch-record.template.yaml`
- `docs/film-preproduction/film-commercial-quality-standard.md`
- `docs/film-preproduction/creative-production-integration.md`
- `docs/film-preproduction/goal-autorun-completion-protocol.md`
- `docs/film-preproduction/director-room-routing.md`
- `docs/film-preproduction/schemas/director-role-harness.yaml`
- `docs/film-preproduction/longform-decomposition-policy.md`
- `docs/film-preproduction/capability-aware-generation-policy.md`
- `docs/film-preproduction/reference-consistency-gate.md`
- `docs/film-preproduction/shot-language-standard.md`
- `docs/film-preproduction/schemas/client-film-gate-contract.yaml`
- `docs/film-preproduction/schemas/chat-visualization-spec.schema.json`
- `docs/film-preproduction/research/`
- `docs/film-preproduction/schemas/`
- `docs/film-preproduction/prompt-pattern-registry.json`

## skill_run_receipt

Every sub-skill output must include:

```yaml
skill_run_receipt:
  receipt_version: "1.0"
  run_id:
  skill_id:
  execution_context:
    mode: standalone_chat | orchestrated_worker
    controller_skill: dircreative | ad-creative-orchestrator
  orchestrator_context:
    contract_name:
    contract_version:
    caller_skill:
    caller_run_id:
    handoff_id:
    goal_id:
    work_id:
    lane_id:
    lane_run_id:
    target_gate_id:
    absolute_deadline_at:
    adoption_owner:
    skill_sha256:
  worker_identity:
    thread_id:
    source_thread_id:
    assigned_worker_thread_id:
    reporting_thread_id:
  stage_gate:
    id:
    type: idea | story | script | shot | visual | reference | image_prompt | video_prompt | generation_qa | retry | acceptance | checkpoint
    status: pass | fail | needs_user | blocked | simulated
    decision_owner: user | simulated_fixture | controller | worker
  input_artifacts: []
  output_artifacts: []
  decisions: []
  unresolved_questions: []
  retry_loop:
    failure_id:
    corrected_layer:
    unchanged_locks: []
    next_smallest_artifact:
  qa_gate:
    status: pass | fail | needs_user
    reasons: []
  session_state:
    checkpoint_path:
    source_truth_refs: []
    stale_artifacts: []
  domain_delivery:
    domain_verdict: domain_accepted | draft_accepted_with_limitations | needs_user | needs_revision | blocked
    discussion_ready: false
    specialist_handoff_ready: false
    generation_ready: false
    client_ready: false
    final_export_allowed: false
    hard_blockers: []
    evidence_refs: []
    dirty_state_impact:
    worker_recommendation:
    loop_state:
    qa_gate_status:
    manifest_index_updates_needed: []
    recurrence_guard:
    cleanup_actions: []
    adoption_recommendation: adopt_as_internal_draft | adopt_for_next_gate | reject | defer
  next_recommended_skill:
```

## Prompt Production Closure

对于 image prompt、video prompt、参考图复用或生成后 QA，先读取并遵循：

- docs/film-preproduction/schemas/prompt-ir.schema.json
- docs/film-preproduction/schemas/prompt-ir.yaml（仅作者模板）
- docs/film-preproduction/prompt-authoring-standard-v1.md
- docs/film-preproduction/asset-intake-and-state-standard-v1.md
- docs/film-preproduction/prompt-qa-and-incident-runbook-v1.md
- scripts/dircreative_prompt_compiler.py

执行顺序固定为：

~~~text
读取用户/客户/项目现成素材
-> 登记 source、hash、role、preserve、change、inherits_from、lock
-> 判断 direct_reference / edit / derive / planning_only
-> 建立模型无关 Prompt IR
-> 编译单一已选模型
-> self-QA
-> 返回 artifact、status、next_action
-> 等待或记录 user lock/revise
~~~

Prompt IR 必须通过可执行 v1.1 JSON Schema 和语义校验。提示词同时处理 composition、逐实体 action ownership、camera start/path/end、audio、transition，以及按条件启用的 lighting、optics、atmosphere、grade 四层 Look。未启用层保留在内部 IR，不为满足模板写进终端模型文本；不能用 cinematic、premium、高级滤镜或高级运镜代替具体结果。

用户已提供的故事、分镜、参考图、视频或音频优先作为 source truth。能够复用或编辑时，不得脱离原素材凭文字重新想象。最终模型 prompt 只出现当前 exact adapter 真正挂载的引用角色和可观察指令；不得出现内部 shot/entity/asset id、本地路径、hash、manifest/QA/retry 字段、planning-only 资产、post-production-only 音频或未挂载槽位。

参考图遵循最小充分原则：人物/产品身份和场景是常见基础输入；材质灯光、分镜运动图、产品细节图和 clean frame 只有在对应事实未锁定、跨镜头漂移风险高、需要客户视觉确认或选定模型明确要求时才新增。只有人物和场景输入时，提示词仍必须独立完成全部摄影、动作、Look、声音和转场描述。

生成后不得静默停止：没有真实生成时状态必须是 prompt_only 或 instructions_only；有候选时必须记录 self-QA、status、next_action；没有用户 lock 或 live acceptance 时不得称为 final 或 complete。

主 fixture 的结构性回归命令：

~~~text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_prompt_fixture_audit.py
~~~

## Harness And Loop Contract

DIRcreative is a product-grade skill harness, not a prompt bundle. Every material stage must run as a typed stage gate with a customer-readable preview, durable artifacts, a receipt, QA status, retry routing, and an explicit stop condition. The preview is shown directly in `standalone_chat` and returned to ADCO in `orchestrated_worker`.

The required loop is:

```text
read source truth
-> select typed stage gate
-> show customer-visible preview and one decision question
-> write or update artifact only after the gate is resolved
-> write skill_run_receipt
-> run QA or council/cold-review when the decision could pass validation while still failing the user
-> if failed, retry the smallest artifact and change one variable
-> persist checkpoint/session state
-> stop at needs_user, blocked, dry-run boundary, or live acceptance boundary
```

Typed stage gates must declare `stage_gate.type`, `stage_gate.status`, `decision_owner`, source-truth locks, output artifacts, and next retry owner before downstream work starts. Hidden chat memory is not a valid stage gate.

In `orchestrated_worker`, ADCO owns the outer loop, user gate, assigned worker, adoption, and cleanup. DIRcreative owns only the bounded inner domain loop granted by the handoff. A DIRcreative domain PASS is not an ADCO client, generation, export, or FinalDelivery PASS.

Receipts must preserve session persistence: run id, input artifacts, output artifacts, decisions, unresolved questions, QA result, retry loop fields, checkpoint path, stale artifacts, and next recommended skill. If a thread worker contributed, the receipt or adoption record must include the worker thread id, thread class, read/write scope, adoption decision, validation command, and cleanup state.

Retry loop discipline is mandatory. Use the failure taxonomy, change one corrected layer only, keep unchanged locks visible, name the next smallest artifact, and stop if the next correction needs a real user decision, external account/API access, real image/video authorization, unsafe repo state, or live acceptance.

Goal autorun is a dry-run boundary. It may simulate user choices and receipt shape, but it must not call `update_goal`, write `live-user-acceptance.yaml`, set `real_user_co_creation_verified: true`, or claim `OBJECTIVE_COMPLETE`.

Live acceptance is a separate boundary. Only an explicit live user acceptance pass may write `.dircreative/runs/live-user-acceptance.yaml`; worker approval, council approval, validation PASS, generated media, prompt-only export, or Goal autorun cannot substitute for it.

## Guardrails

- Resolve `standalone_chat` versus `orchestrated_worker` before the first visible response or file write.
- In `standalone_chat`, use `runtime-state-governance.md` plus the state audit/current-index commands before resume, current-first, reconciliation, or completion reporting. Do not substitute DIR runtime state for ADCO current truth in `orchestrated_worker`.
- For ADCO work, validate the native descriptor/handoff before production, validate the neutral receipt before return, and return `invalid_worker_thread_id` when Codex Thread evidence does not match the handoff.
- Do not generate real images or videos unless explicitly authorized.
- Before calling any image generation tool, require a `pre_generation_contract.status: pass` for the exact asset being generated.
- Before delivering an image prompt, video prompt, generation recommendation, or retry instruction, run the production prompt discipline pre-delivery harness: routing, required knowledge, lock order, user gate state, visual output mode, execution capability, prompt contract, reference bindings, model constraints, targeted avoid constraints, prompt-window hygiene, and falsifiable success criteria.
- Before delivering any user-visible creative direction, option set, script note, prompt-only handoff, generation recommendation, QA/retry note, or final summary, run a short humanizer pass. Chinese output follows `humanizer-zh`; English output follows `humanizer`. Rewrite signs of AI writing into plain production language without losing professional judgment.
- The contract must be present in the prompt text, not only in hidden notes: the prompt must include the exact dominant title, smaller project metadata, and the explicit instruction forbidding the film/project title as largest text.
- Prompt-only and external-generation handoffs must carry the same visible contract inside the prompt text, because the user may paste that prompt into another image tool.
- If the pre-generation contract is missing or fails, stop before generation and fix the prompt/spec first.
- Do not make terminal output or raw files the primary user experience.
- In chat, show the current stage, 2-3 options, your recommendation, and exactly one user decision question.
- Do not ask the user to approve `pre_generation_contract`, raw JSON, YAML, or prompt bodies as a frontstage choice. Ask what to execute: first test image, full recommended pack, prompt-only export, first video model test, retry one failed asset, or stop.
- Before compiling or generating any visual material, show a user-facing material choice instead of guessing the asset type: character identity reference, scene geography/FOV reference, professional storyboard + motion map, selected clean frame, style/material board, first test image, full recommended pack, prompt-only export, or stop.
- Every creative stage must include `用户确认点`; every goal-mode simulated stage with a confirmation point must also include `模拟用户选择`, except terminal report stages.
- Every major stage must show `客户可见预览` before internal production state, model jargon, or blocker language.
- Brand/product films must ask or confirm brand assets, product lock, human strategy, and delivery priority before story lock, reference prompts, or image generation.
- `阶段: 导演组会议` must show distinct role cards, at least one disagreement, and a resolution note before the recommendation.
- Do not require a user to name individual director-room roles for a non-trivial advertising-film, film, storyboard, script, or visual-creativity task. Route it automatically through the director-role harness; preserve the lightweight path for simple rewrites and single factual questions.
- A director-room result must contain discussion, useful disagreements, an explicit arbitration/ruling, downstream resolution notes, and user-visible options. Never present a role-name list as if it were a council.
- Chat output must sound like a professional production team: include judgment, tradeoff, and downstream execution impact.
- When the user gives a rough idea, first respond with a chat brief and the next confirmation question; do not silently create a full hidden package.
- Treat 15 seconds as a possible model generation-unit limit, not automatically as the story duration. If unclear, ask whether 15s means the whole film or each generated group; in goal-mode simulation, state the assumption as `模拟用户选择`.
- For longform work, plan the whole story arc before splitting into 5-15s generation units. Do not compress a longer story into one 15s script because a video model has a 15s cap.
- When a stage completes, show the user the useful preview before mentioning files.
- For ad films, do not generate a single clean frame before showing and confirming the ad reference pack plan.
- Do not offer reference strategy, clean frames, image generation, or video model choices before story/script/shot/visual bible gates are visible and approved.
- Do not use visual polish, poster quality, storyboard boards, or generated images to compensate for weak story/script work. If the user says the story lacks tension or the script is not professional, mark downstream visual assets as not locked and return to story-development or script-treatment.
- Apply `docs/film-preproduction/production-demo-retrospective.md` after any assisted generation demo or user rejection. Treat `story_development_skipped`, `script_depth_insufficient`, `visual_generation_before_story_lock`, and `storyboard_information_density_too_low` as stop-work signals for downstream visual locking.
- Apply `docs/film-preproduction/council-adversarial-review.md` when a decision could pass validation while still failing the user. The required viewpoints are user, professional film expert, product manager, skill developer, and code researcher; synthesize dissent into the smallest repo change and keep `OBJECTIVE_COMPLETE: NO` unless live acceptance proves otherwise.
- Use council/cold-review as part of the harness loop for non-trivial locks, assisted-generation demos, retry-policy changes, thread/worktree changes, and completion claims. Review output is advisory until reconciled into docs, artifacts, receipts, taxonomy, retry rules, or validation output.
- If the user asks to test or continue, route to the earliest unresolved creative gate instead of jumping to image/reference generation.
- If the user changes a core premise, protagonist, product, channel, duration, tone, reference lock, or safety boundary midstream, enter `阶段: 中途改需求处理`, name the changed upstream decision, mark affected downstream artifacts as stale, stop before prompt or media generation, and ask one revision-scope question.
- Default to `prompt_only` when image generation capability is absent or not authorized.
- Before locking concept, story, script, shot list, visual style, visual bible, sequence plan, reference pack, clean frame, or video prompt choices, update the co-creation gate state.
- Do not convert `simulated_fixture` choices into `real_user` approval.
- In goal-mode simulation, do not stop at every gate waiting for `1`; label the recommended choice as `模拟用户选择` and keep going until `阶段: 模拟测试结论`.
- Goal-mode simulation must never create `.dircreative/runs/live-user-acceptance.yaml`, set `real_user_co_creation_verified: true`, or close the active goal.
- For 60s, 90s, and 180s projects, plan sequence packs before final image/video prompts.
- Do not skip story, script, shot, and reference planning before prompts.
- For client-facing relationship, anniversary, brand-story, one-minute, storyboard, or PPT proposal work, follow `client-film-hard-gates.md`: customer-readable story preview -> timed script/VO budget -> 30+ shot/rhythm points for 60s -> per-shot asset/reference contract -> locked-shot prompt plan -> client-language review. Any missing upstream gate blocks prompt writing, image generation, video generation, and PPT handoff.
- Do not treat 12 customer story sections as a complete one-minute shot list. A 60-second film needs roughly 30+ shot or rhythm points unless the user explicitly accepts a slower format.
- If the source brief uses an ellipsis in a prop list, expand it as examples across the relevant characters, roles, props, actions, and shot functions. Do not treat the first visible props as exhaustive.
- If the user says existing browser, Grok, ChatGPT, ImageGen, downloaded, or local images already exist, complete browser/local intake or record `TOOL_BLOCKED` before declaring images missing or regenerating them.
- Customer-visible copy must not expose prompt, thread, worker, gate, AI, internal workflow, asset-permission, authorization, or confirmation labels. Translate risks into client-readable production boundaries and keep internal terms in receipts or checklists.
- Character consistency and scene consistency are mandatory; reject generated assets that drift from the locked identity or scene source.
- Assisted image generation must follow lock order: character identity, scene geography/camera FOV, professional storyboard/motion page, then selected clean frames.
- For brand/product films where product identity is not locked, assisted image generation must start with a clean single-product `PRODUCT IDENTITY REFERENCE`, after freezing product silhouette, scale, material, diffusion/opening method, logo/text policy, desk/car use readability, and forbidden style drift.
- The first generated product identity candidate must not contain labels, captions, detail insets, collage panels, strong category-rewriting background props, protagonist, full ad scene, storyboard panels, or large slogan text. Split detail/macro/context images into separate later assets.
- Product identity QA must check whether the image could be misread as a speaker, power bank, air purifier, car control knob, perfume bottle, incense burner, or ancient ornament before asking the user to lock it.
- Abstract pebble, pod, stone, or capsule products cannot be locked from a beauty shot alone; require a clean product identity candidate, a function detail reference, and a usage position reference when the product claims multiple modes such as desk plus car use.
- If a base, coaster, tray, dock, magnet, stand, or holder appears, label it as support/environment hardware in the artifact contract so it is not merged into the product body.
- For modern Chinese, new Chinese, or Eastern restraint briefs, explicitly reject unwanted ancient, immortal, ink-wash, generic Zen, and luxury perfume cliches when the user asks for modern restraint.
- A professional storyboard/motion page is required before reference images can be treated as useful shot guidance.
- A professional storyboard/motion page must carry character design, scene layout, prop continuity, shot size, camera position, camera movement, subject movement path, blocking, emotional beat, transition logic, and model risk. Do not replace it with a generic 3x3 mood storyboard.
- Before assisted image or video generation, show the user `QA 与重试规则`: pre-generation contract checks, post-generation self-QA, failure IDs, blockers, and smallest-artifact retry routing.
- Never ask the user to lock a generated asset before self-QA passes. Failed candidates must stay blocked and route to the smallest corrective retry.
- After any image generation or external import, run generation QA before asking the user to approve, lock, or proceed with that asset.
- Do not ask the user to be the first QA pass. Failed generated candidates must be labeled as failed, recorded in `.dircreative/runs/`, and regenerated or replanned before any user lock request.
- Creative Production is allowed as a deep generation and review adapter only after DIRcreative story, script, shot, visual bible, reference pack, and `pre_generation_contract.status: pass` gates are satisfied or explicitly simulated in Goal autorun.
- When using Creative Production, `render_moodboard_board_widget` is the review surface and is not the source of truth. DIRcreative artifacts, manifests, and `.dircreative/runs/` remain the source of truth.
- Creative Production paths map as follows: visual direction to Mood boards or Scenes, brand/product proof to Offers or Ads, approved shot variants to Shots, and locked final assets to Generative Polish.
- Every Creative Production candidate must be recorded as `generated_candidate` until self-QA passes and the user locks it. A widget, local URL, HTML page, or temporary screenshot cannot become a locked artifact or live acceptance evidence by itself.
- Do not use one universal video prompt for every model.
- Do not write plausible model facts as verified facts. Aspect ratios, durations, reference media roles, audio support, clean-frame requirements, and tool availability must come from local policy, source docs, or tool schema evidence.
- For generation retries, change one variable at a time and record the failure ID, corrected layer, and next smallest artifact to update.
- Persist session state before handoff, retry, pause, worker adoption, or stop: checkpoint path, source-truth refs, current typed stage gate, unresolved user decision, stale artifacts, and next recommended skill.
- Do not copy prompt libraries wholesale; extract sourced reusable patterns.
- When learning from Higgsfield-style skills, Reddit, X, or prompt libraries, extract only structure: prompt-construction layer, MCSLA/five-layer camera discipline, material role separation, micro-scene beat sheet, negative constraints, and single-variable iteration. Do not import unverified model facts or platform dependencies.
- Treat `community_recipe_overfit` as a stop-work signal when a public prompt recipe bypasses DIRcreative source truth, material selection, prompt contract, or falsifiable QA.
- Do not let hidden conversation state be the only handoff.
- In `standalone_chat`, follow `thread-orchestration-protocol.md`: the DIRcreative main-controller owns dispatch, active Goal and acceptance standard, worker scope, worktree selection, conflict arbitration, worker diff adoption or rejection, final validation, cleanup, user reporting, and Goal completion decisions.
- In `orchestrated_worker`, ADCO retains those controller duties. DIRcreative stays inside the assigned worker, executes only the handoff-selected sub-skill, and returns scoped artifacts, validation evidence, blockers, `open_questions`, and an adoption recommendation.
- Standalone substantive production work, implementation, document changes, and professional role execution default to worker Threads. Under ADCO, use the already assigned worker; nested dispatch is forbidden.
- Temporary stateless subagents are second-level local tools inside an explicitly authorized Codex worker, not a substitute for Codex Threads. Use them only for bounded read-only decomposition, reference checks, risk lists, source triage, or candidate ranking; record subagent id or `TOOL_BLOCKED`, input, output summary, close status, adoption decision, and adopted artifact inside the first-level worker receipt.
- Second-level subagents must not write files, write live acceptance, change `write_scope`, verify cleanup, make user-facing final acceptance decisions, mark a Goal/objective complete, or become durable truth without first-level worker reconciliation.
- When the user asks for council mode, multi-review, compound professional roles, or Thread-backed execution, keep thread mechanics backstage. Internally assign the lane map, worker budget, professional identities, stop conditions, dispatch record path, and cleanup rule; the user-facing answer should show role judgments, disagreements, options, recommendation, and one decision question. Compress many seats into the default professional lanes before creating extra threads.
- If the user explicitly requires true Codex Threads, a real worker receipt, or Thread-backed execution and the required tool is unavailable, return `TOOL_BLOCKED`; do not silently use simulated role passes as a substitute.
- Same-directory Codex worker threads are read-only and only for research, review, or cold review. Standalone writable workers use an isolated worktree. An ADCO `orchestrated_worker` may instead use a caller-verified `isolated_workspace` for non-git material projects, with exact write scope and ADCO adoption.
- A disposable Codex Thread result is not durable truth until it is reconciled into repository docs, `.dircreative/runs/`, manifests, receipts, or validation output; archive it after the result is consumed or rejected.
- Before and after standalone thread-backed work or validation, follow `workspace-cleanliness-protocol.md`: inspect `git status --short` and `git worktree list --porcelain`, classify user-owned versus task-owned dirty files, remove only task-owned generated caches, and report every intentional remaining dirty path. Under ADCO, return workspace evidence and leave adoption/cleanup to ADCO.
- Target project `AGENTS.md` is stable project policy, not a normal DIRcreative artifact. DIRcreative may read, follow, audit, and propose candidate rules by default, but must not create, append to, overwrite, delete, or move target project `AGENTS.md` instructions without explicit user authorization naming the target project and operation. `AGENTS.md` proposal or audit output is technical readiness only, not live user acceptance.
- Do not mark a standalone active goal complete from release-gate output alone; completion requires `.dircreative/runs/live-user-acceptance.yaml` to pass `scripts/dircreative_goal_audit.py --require-installed`. In `orchestrated_worker`, never update or complete the outer Goal.
- Goal autorun must cover rough idea, complete idea, commercial product ad, Creative Production preflight, QA, and final dry-run conclusion without real media generation, without `update_goal`, and without `live-user-acceptance.yaml`.
- For a standalone final acceptance pass, follow `docs/film-preproduction/live-chat-acceptance-runbook.md` and wait for an explicit user acceptance statement before writing `.dircreative/runs/live-user-acceptance.yaml`. An ADCO worker returns to ADCO and never writes live acceptance on ADCO's behalf.
- Structural validation, including `scripts/validate_project.py` and `client_film_gate_contract` checks, only proves contract coverage. It does not prove client-send readiness, copy quality, visual quality, asset authorization, music/video licensing, or live user acceptance.
