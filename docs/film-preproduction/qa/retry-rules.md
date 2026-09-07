# Retry Rules

Retry only the smallest artifact that can remove the failure. Do not rewrite the full workflow when a local fix is enough.

## Story And Script

`weak_story_idea`: return to director-room. Add a concrete decision, conflict pressure, visible reversal, and channel-specific hook. Keep the selected channel constraints. For narrative shorts, require external pressure, hidden relationship engine, irreversible choice/reveal, escalation, consequence, and a visible ending action.

`story_development_skipped`: return to story-development. Stop visual generation, storyboard, prompt, and reference planning. Build the missing story engine: protagonist want, obstacle, stakes, external pressure, hidden relationship engine, reversal, consequence, and setting-as-plot-device. Ask the user to approve the story direction before writing script or visual assets.

`generic_script`: return to script-treatment. Replace abstract copy with action, product proof, character choice, or voiceover that changes how the viewer reads the image.

`script_depth_insufficient`: return to script-treatment, or story-development if the story engine is weak. Rewrite scenes around character objective, conflict pressure, action beats, turn/reveal, consequence, and visible ending action. Dialogue must create pressure, misdirection, refusal, concession, reveal, or choice.

`visual_generation_before_story_lock`: stop media work and mark generated assets as not locked. Record the feedback in `.dircreative/runs/`, then return to story-development or script-treatment until the user approves story/script quality.

`material_selection_missing`: return to the frontstage material choice. Ask which material to make next: character identity reference, scene geography/FOV reference, professional storyboard + motion map, selected clean frame, style/material board, first test image, full recommended pack, prompt-only export, or stop. Do not infer the asset type from a vague image request.

`thread_control_incomplete`: return to the main-controller thread. Define worker role, write scope, expected output, cleanup rule, and acceptance standard before dispatch. Check `git worktree list --porcelain`, archive or clear failed worktree initialization entries when visible, and reconcile useful findings into repository files, `.dircreative/runs/`, `skill_run_receipt`, or validation scripts before using them.

`community_recipe_overfit`: return to update or the prompt-owning skill. Keep the external/community recipe only as structure, then rewrite it against DIRcreative source truth, material role, prompt contract, reference bindings, targeted negative constraints, and falsifiable success criteria. Verify model facts through official docs, source repositories, local policy, or current tool schemas. Do not copy Reddit, X, or Higgsfield-style wording wholesale.

`product_benefit_not_visible`: return to director-room or shot-design. Make the benefit visible through before/after, stress test, tactile use, comparison, or consequence.

`film_story_conflict_missing`: return to story-development. Add one visible want, one pressure source, one obstacle, one decision or reveal, and one consequence. Do not advance to script or visual material until the conflict can be shown as action.

`film_emotional_turn_missing`: return to script-treatment. Make the final beat reinterpret the first beat through a visible change in behavior, object state, environment, sound, or edit rhythm.

`commercial_objective_missing`: return to idea-intake or director-room. State the business objective before choosing creative tone, reference style, or media generation path.

`audience_channel_context_missing`: return to idea-intake. Confirm target audience, usage occasion, market or cultural context, platform, aspect ratio, and first release priority before shot or reference work.

`product_proof_not_visible`: return to shot-design. Add a visible proof shot, transformation, comparison, use behavior, or final memory frame before any product ad image generation.

`director_room_tradeoff_missing`: return to director-room. Add at least one film-versus-commercial disagreement, then write the resolution and downstream impact before the user decision gate.

`product_lock_before_generation_missing`: return to image-prompt-compiler. Freeze product silhouette, material, scale, use method, logo/text policy, and forbidden drift before Creative Production or image generation.

`generated_candidate_locked_without_self_qa`: return to generation-qa. Move the asset back to `generated_candidate`, run self-QA, record failure IDs or pass criteria, and ask for lock only after QA passes.

`creative_production_widget_used_as_truth`: return to the Creative Production adapter receipt. Mark widget and local preview surfaces as review surfaces only, write candidate status back to `.dircreative/runs/` and manifests, then rerun the adapter audit.

`goal_autorun_claimed_live_acceptance`: remove the live acceptance claim. Keep the run as `dry_run_fixture`, set `real_user_co_creation_verified: false`, do not write `live-user-acceptance.yaml`, and run the live chat acceptance pass separately.

## Shot And Blocking

`overloaded_shot`: split the shot. Keep one dominant action, one camera move, one purpose, and one audio intent per shot.

`continuity_drift`: identify the source artifact that introduced the contradiction. Write a revision request instead of silently changing locked upstream artifacts.

`storyboard_information_density_too_low`: return to shot-design. Build a dedicated professional storyboard/motion page with one cell per shot, including timecode, duration, shot image region, detailed frame description, shot size, focal length, camera position, camera movement, subject blocking, sound, transition, and model risk. Rewrite visible cell text as compact professional shot-card language: narrative purpose, lens/support/movement, blocking path, continuity lock, sound/edit cue, and model risk. Do not accept thin labels such as wide, close-up, slow push, conversation, or emotional ending by themselves.

## Visual Bible And Reference Planning

`vague_visual_direction`: return to visual-bible. Replace broad adjectives with palette, light source, material behavior, texture, wardrobe/product geometry, and lens/capture rules.

`unusable_reference_image_plan`: split reference roles. Use separate boards or clean stills for identity, environment, product/prop, style, storyboard, and first-frame tasks.

`reference_board_too_dense_for_model`: keep the dense board as a human or Seedance/Veo planning asset, then create clean first-frame or element references for Kling/Runway.

`clean_first_frame_missing`: generate or select a clean frame with no text, arrows, borders, floor plan marks, or labels. It must match the intended shot start.

`reference_role_conflict`: assign one primary job to each asset. Move secondary needs into `supports`, or split the asset.

`character_identity_reference_drift`: return to reference-image-planner. Lock one character identity reference first, then regenerate downstream scene boards and clean frames with explicit inheritance from that asset. Do not use the drifting candidates for video.

`scene_geography_reference_drift`: return to reference-image-planner. Lock one scene geography plus camera FOV atlas, then regenerate storyboards and clean frames against that route, axis, vehicle position, and lighting direction.

`reference_asset_duplicate_conflict`: reduce the pack. Keep only the asset that owns the visual truth, and rewrite repeated assets as crops, insets, or planning annotations that inherit from the locked source instead of redesigning it.

`reference_asset_role_label_missing`: revise the prompt or manifest. Add large role labels or manifest role labels such as character reference, scene + camera movement reference, professional storyboard + motion map, lighting/material reference, or clean first/end frame.

`reference_role_label_hierarchy_wrong`: revise the prompt. Make the asset role the dominant page title and move the film/project title to smaller metadata. Do not accept poster-like hierarchy for production reference assets.

`image_generation_called_without_pre_generation_contract`: return to image-prompt-compiler. Write a machine-readable `pre_generation_contract` that passes asset role, dominant title, title hierarchy, role purity, inheritance, and direct-input policy before calling any image generation tool.

`unreadable_reference_text`: enlarge labels, reduce copy, replace prose with short tags, or move notes into the artifact manifest instead of the image.

`element_reference_missing`: create a main reference plus up to three supplementary views for the character, product, prop, costume, or scene element.

`first_frame_does_not_match_shot`: revise the first frame or the shot plan. Do not use prompt text to force motion that contradicts the frame.

`model_pack_budget_exceeded`: reduce competing references. Keep identity first, then motion/camera, then style/audio only when needed.

`visual_output_mode_missing`: set `visual_output_mode` to `prompt_only`, `assisted_generation`, or `external_generation`. Default to `prompt_only` when capability or authorization is absent.

`missing_asset_output_status`: add `asset_output.status` for every image/reference asset. Block video export if required files are missing and no external instructions exist.

`unauthorized_assisted_generation`: switch to `prompt_only`, or ask for explicit authorization before using image/video generation tools. Record the authorization in execution capabilities.

`external_generation_instructions_missing`: add target tool, prompt file, upload role, expected reference slot, clean start/end frame requirement, and import checklist.

`plausibility_over_verification`: return to the source registry, local policy, official docs, or current tool schema. Remove unverified model facts, pricing, account state, aspect ratio, duration, audio support, and availability claims. If the fact cannot be verified, downgrade the run to `prompt_only` or `external_generation` with an explicit risk note.

`prompt_contract_incomplete`: return to the prompt-owning skill. Run the production prompt discipline pre-delivery harness and fill routing, required knowledge, lock order, user gate state, visual output mode, execution capability, prompt contract, reference bindings, model constraints, targeted avoid constraints, prompt-window hygiene, and falsifiable success criteria before delivery.

`multi_variable_retry`: stop the broad retry. Pick one corrected layer only: subject/product identity, scene/reference binding, action/blocking, camera/duration, look/material/light, or output control. Record the unchanged locks, one variable changed, expected visible improvement, and next QA check.

`stale_reference_context`: return to checkpoint or the prompt-owning skill. Remove stale choices, old references, unavailable generated files, and conflicting prompt fragments. Convert any useful thread or chat context into an artifact field or receipt before using it as production truth.

`missing_falsifiable_success_criteria`: add a visible pass/fail rubric before generation or external handoff. Criteria must name identity match, scene/FOV match, shot action fit, camera start/end targets, role label/title hierarchy when required, direct I2V input policy, and audio policy where relevant.

`longform_sequence_plan_missing`: return to sequence-planner. Split the target duration into 5-15s generation units and add sequence/user gates before image prompts.

`sequence_pack_overloaded`: split the sequence pack or reduce it to one dramatic function, one dominant action, one camera grammar, and one clean frame requirement.

`batch_mode_risk_unaccepted`: either switch to hybrid mode or record accepted risks for continuity drift, rework cost, and reduced user control.

F-COMP-01, F-COMP-02, F-COMP-03: change only the composition card. Preserve identity, material, lighting, and action; correct visual center, hierarchy, negative space, movement room, or crop safety. Do not add a random camera move to hide a composition failure.

F-LOOK-01: change only the grade layer. Keep the lighting, optics, atmosphere, composition, and material locks; add a neutral anchor, contrast/gamma, black level, highlight roll-off, saturation/density, and narrative reason.

F-OPT-01, F-OPT-02, F-OPT-03: change only the optics layer. State the physical lens/filter condition and observable behavior; limit flare/bloom to the triggering light source; correct focus, falloff, bokeh, and crop readability.

F-ATM-01: change only the atmosphere layer. Add the directional source, medium, density, light-path visibility, and falloff required for the beam; otherwise set the effect to none by design.

F-GRADE-01: change only grade continuity. Restore the white-balance anchor, product material readability, highlight roll-off, and palette relationship before changing any prompt action or camera field.

## Image Prompting

`generic_grid_board_layout`: revise the JSON style config. Add hierarchy, placement logic, hero region, supporting regions, exact labels, and art-directed asymmetric policy.

`fish_scale_material_artifact`: add or strengthen `surface_integrity_guard`. Reduce excessive sharpening language. Specify natural material continuity, smooth coherent texture, and complete geometry.

`image_prompt_missing_json_style_config`: rebuild the prompt from `docs/film-preproduction/templates/image-prompt-style-config.template.json`. Use active pattern IDs from the registry.

`image_prompt_missing_visual_decomposition`: return to image-prompt-compiler. Fill subject, action/pose or blocking, details/appearance, environment/background, lighting/atmosphere, composition/framing, style/camera, colors/palette, materials/texture, proportion/scale, and generation intent before compiling final prose.

`image_prompt_missing_prompt_layers`: return to image-prompt-compiler. Add a complete director prompt, a reusable prompt core, and a targeted negative prompt. Keep the full prompt for the exact asset and the core prompt for reusable locks only.

`invented_visual_fact`: return to the smallest source artifact that owns the fact. Remove invented logos, exact text, locations, camera bodies, lens models, hidden objects, product features, wardrobe details, or scene props unless they are visible or locked upstream.

`empty_quality_wording`: revise the prompt text. Replace standalone praise words with concrete edge behavior, material response, lens/focus relationship, lighting direction, readable text rules, composition hierarchy, or continuity constraints.

## Video Prompting

`storyboard_board_misread_by_video_model`: add the anti-misread clause. Prefer clean first-frame images for Kling and Runway. For Seedance or Veo, map storyboard as shot-order reference only.

`board_used_as_direct_i2v_input_when_forbidden`: replace the direct image input with a clean first frame. Keep the board only as production guidance in the prompt or reference map.

`copied_video_prompt_across_models`: regenerate each adapter from model behavior:

- Seedance: reference map, chronological shot flow, continuity locks, audio section.
- Kling: subject movement, background movement, camera movement, compatible with the input image.
- Runway: simple positive motion prompt from a strong input image.
- Veo: structured subject, action, scene, camera, lighting, style, and audio.

`missing_audio_policy`: add a separate audio section. State visual-only silence, post-production audio, generated ambience, dialogue, voiceover, music, and effects boundaries.

`model_specific_motion_failure`: retry the failing model only. Simplify movement, reduce shot count, remove conflicting camera instructions, and keep the input image physically compatible.

## Learning And Registry Updates

For image assets, review the independent batch before choosing retries. A local
failure blocks only its consuming use; it does not stop unrelated production or
restart the story/reference stages. First repair the cause in the input/prompt,
not just the latest visible symptom. If a repair damages a previously correct
region or materially degrades texture, stop recursive edits of that result.
Return to the best same-truth base, use supported regional editing, or generate
a fresh candidate. Keep both failures and successful originals. More retries,
longer negative prompts and more reviewers are not evidence of improvement.

Promote a new prompt pattern only when a fixture retry improves at least one QA gate without regressing another. Record the source, mechanism, fixture evidence, failure risk, and deprecation rule.

## Prompt IR, Compiler, Convergence, And Cleanup

`prompt_ir_schema_invalid`: validate against `docs/film-preproduction/schemas/prompt-ir.schema.json`; fix the smallest invalid field and rerun semantic validation. Do not add keyword checks as a substitute for schema validation.

`terminal_prompt_internal_leak`: return to `scripts/dircreative_prompt_compiler.py`. Remove the internal field from the compiled surface, keep it in Prompt IR/manifest, regenerate the prompt deterministically, and rerun terminal-surface negative fixtures.

`terminal_prompt_phantom_reference`: compile only `attached_to_run: true` references accepted by the exact adapter. Keep planning-only assets in the manifest. Rebuild the upload map before changing creative text.

`entity_action_owner_unresolved`: assign one stable external name, action owner, target, prop owner, speaker, and final state. Do not solve ambiguity with pronouns or a larger negative prompt.

`generation_unit_plan_invalid`: make shots and units contiguous from zero to target duration, keep each unit within `generation_unit_sec`, and carry incoming/outgoing visual and audio state across every boundary.

`retry_not_converging`: stop the same-layer retry after the third failed attempt. Present the smallest escalation: simplify action/subjects/camera, split the unit, change reference route or exact-card adapter, move the element to post-production, or stop for user input.

`historical_context_pollution`: classify each candidate through current-state references and storage class. Delete only unreferenced regenerable cache or an explicitly authorized delete candidate. Preserve user-owned sources, locked/final artifacts, receipts, provenance, and ambiguous files; remove stale search/index references before deleting bytes.
