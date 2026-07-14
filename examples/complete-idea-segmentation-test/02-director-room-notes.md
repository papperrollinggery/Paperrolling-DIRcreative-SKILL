# Complete Idea Director Room Notes

artifact:
  artifact_id: complete-idea-director-room-v1
  version: 1.0.0
  source_artifact_ids:
    - complete-idea-segmentation-intake-v1
  status: approved
  owner_skill: director-room

## Roles

Live default is real sub-agents. This fixture uses `execution_mode: simulated_role_passes_fallback` only because examples cannot prove live sub-agent execution.

council_protocol: director-room-council-protocol

execution_mode: simulated_role_passes_fallback

subagent_default: true

fallback_reason: "dry-run fixture cannot spawn verifiable live sub-agents"

complete_idea_mode: true

## Role Cards

role_cards:
  producer:
    protected_value: "A 15-second vertical AI short must stay legible and shippable."
    sees_in_idea: "The user already supplied title, plot, tone, duration, channel, and avoid list."
    main_concern: "If the council invents new story directions, it breaks the user's complete idea."
    recommendation: "Keep the supplied story and use the council to validate execution, shot count, and model-safe reference strategy."
  creative_director:
    protected_value: "Humane civic tone instead of generic zombie action."
    sees_in_idea: "The emotional hook is professional care under pressure."
    main_concern: "Horror spectacle would make the cleaner look like an action hero."
    recommendation: "Use grounded blue-gray dawn realism, restrained tension, and quiet proof at the end."
  director:
    protected_value: "Motivated blocking and readable behavior."
    sees_in_idea: "One worker clears one emergency lane so an ambulance can pass."
    main_concern: "A single busy master shot would confuse the route, the cart, and the ambulance."
    recommendation: "Break the 15 seconds into setup, tool activation, push, threat control, release, and proof."
  screenwriter:
    protected_value: "No extra exposition."
    sees_in_idea: "The story can work without dialogue or title-card explanation."
    main_concern: "Voiceover or text would fight the practical realism and create model text errors."
    recommendation: "Use a no-dialogue six-beat script with sound and action carrying the meaning."
  cinematographer:
    protected_value: "Shot grammar, lens logic, and route geography."
    sees_in_idea: "The street axis, emergency lights, fog, and reflective jacket can orient every cut."
    main_concern: "Changing FOV or camera side between shots will break scene continuity."
    recommendation: "Lock a scene geography + camera FOV reference before storyboard and clean frames."
  production_designer:
    protected_value: "Stable wardrobe, cart, street materials, and emergency vehicle design."
    sees_in_idea: "The worker uniform and disinfectant cart are the identity anchors."
    main_concern: "Repeated boards with partial identity information will create competing worker designs."
    recommendation: "Make one character/equipment identity reference the single source of truth."
  editor:
    protected_value: "15-second rhythm with enough dwell for AI generation."
    sees_in_idea: "The idea needs six readable beats, not one continuous model gamble."
    main_concern: "Three shots would overload setup, tool proof, action, threat, and payoff."
    recommendation: "Use six shots now; split later by model if a tool performs better on shorter clips."
  sound_designer:
    protected_value: "Civic realism and material believability."
    sees_in_idea: "Siren, wet street, cart motor, spray, boot water, and distant city bed can tell the story."
    main_concern: "Big music or horror stingers would push the piece into genre parody."
    recommendation: "Use practical sound first, with low restrained music only after the route is cleared."
  model_prompt_engineer:
    protected_value: "Reference inputs must be model-readable."
    sees_in_idea: "The user wants image prompts and video prompts, but boards cannot all be direct video inputs."
    main_concern: "A dense combined board with tiny text, arrows, and multiple duplicate characters will be misread by Kling, Runway, or Veo."
    recommendation: "Use V2 sequential pack: character identity reference, scene geography/camera FOV reference, professional storyboard/motion page, then optional clean first/end frames."
  continuity_qa:
    protected_value: "Character consistency, scene consistency, title hierarchy, and video handoff safety."
    sees_in_idea: "The previous generated image failed because repeated partial references and dominant film title confused the board role."
    main_concern: "More images without strict role labels will increase identity and scene drift."
    recommendation: "Require pre_generation_contract before every assisted image and block video until user locks clean frames."

## Discussion Round 1: Role Brief Read

- producer: This is not an open brainstorm; it is a complete-idea execution pass.
- creative_director: Keep the humane municipal premise and remove gore/action escalation.
- director: Use physical task logic: see blockage, activate tool, clear route, control risk, release ambulance, show proof.
- screenwriter: Keep it no-dialogue because the action is understandable.
- cinematographer: Route axis and camera FOV must be locked before clean frames.
- production_designer: The character/equipment sheet must be a single identity source, not mixed mood references.
- editor: Six shots are justified by beat separation, not by a fixed template.
- sound_designer: Practical sound should be named in shot cards and video prompts.
- model_prompt_engineer: Planning boards must be separated from direct I2V frames.
- continuity_qa: Generated assets must fail if title hierarchy, role label, or inheritance contract is wrong.

## Discussion Round 2: Disagreements

disagreements:
  - topic: "Respect complete idea versus offer new creative directions"
    role_positions:
      - "producer says the user asked for segmentation, so broad concept ideation should be skipped."
      - "creative_director wants enough taste pressure to prevent a generic zombie-service clip."
      - "director needs execution choices for pacing and blocking."
    decision_pressure: "The council must be visible without hijacking a complete user idea."
    resolved_as: "Do not offer new story concepts; offer execution strategies and ask approval on pacing, shot count, reference strategy, and generation mode."
  - topic: "Three shots versus six shots"
    role_positions:
      - "editor says three shots are tempting for model simplicity."
      - "director says three shots overload route, tool proof, action, threat, and payoff."
      - "model_prompt_engineer says overloaded shots are harder for video models than six clean beats."
    decision_pressure: "Shot count should be dynamic and content-driven."
    resolved_as: "Use six shots for the 15-second version, with future model tests allowed to split or merge based on the selected tool."
  - topic: "Dense reference board versus sequential reference locking"
    role_positions:
      - "production_designer needs enough visual information to preserve wardrobe, cart, and street."
      - "continuity_qa warns repeated partial identity panels create drift."
      - "model_prompt_engineer warns text-heavy boards are unsafe as direct video inputs."
    decision_pressure: "The smallest reference pack must maximize information without creating conflicting truth sources."
    resolved_as: "Use V2 sequential pack: one identity board, one scene/FOV board, one professional storyboard/motion board, then optional clean frames."

## Discussion Round 3: Resolution

resolution_notes:
  - production_rule: "Complete-idea mode still runs director-room, but the council validates execution rather than inventing unrelated concepts."
    rationale: "The user can feel the professional review happened while the original story stays intact."
    downstream_owner_skill: chat-facilitator
  - production_rule: "Shot count is dynamic; this 15-second story uses six shots because six narrative functions must stay readable."
    rationale: "This prevents a fixed three-shot template from damaging pacing and model clarity."
    downstream_owner_skill: shot-design
  - production_rule: "Reference generation must follow V2 sequential order: identity, scene/FOV, storyboard/motion, clean frames."
    rationale: "This reduces character drift, scene drift, and direct video model misread."
    downstream_owner_skill: reference-image-planner
  - production_rule: "Every assisted image prompt must contain visible pre_generation_contract instructions and title hierarchy."
    rationale: "The model must know the largest label is the asset role, not the film title."
    downstream_owner_skill: image-prompt-compiler
  - production_rule: "Video prompts must name sound, camera movement, subject blocking, and which references are planning-only."
    rationale: "Seedance/Kling/Runway/Veo need different handoff rules."
    downstream_owner_skill: video-model-adapter

## Discussion Round 4: User-Facing Execution Options

user_facing_options:
  1:
    option_name: "Six-shot civic realism"
    one_line_story: "A calm municipal cleaner clears one emergency lane and lets an ambulance through."
    visual_promise: "Blue-gray dawn fog, wet asphalt, red-blue emergency pulses, restrained professional behavior."
    production_risk: "Requires strict identity and scene locks before clean frames."
    reference_pack_implication: "Use V2 sequential pack plus optional S01/S06 clean frames."
  2:
    option_name: "Four-shot slower realism"
    one_line_story: "A quieter version holds longer on the route and the worker's process."
    visual_promise: "Fewer cuts, more atmosphere, less equipment detail."
    production_risk: "May under-explain the tool activation and controlled threat."
    reference_pack_implication: "Still requires identity and scene/FOV locks; storyboard page can be smaller."
  3:
    option_name: "Eight-shot faster emergency rhythm"
    one_line_story: "A tighter cut emphasizes urgency and process detail."
    visual_promise: "More inserts, faster reaction beats, sharper sound cuts."
    production_risk: "May exceed 15-second readability and require more clean frames."
    reference_pack_implication: "Needs per-shot clean-frame planning if selected."

recommendation:
  option_id: 1
  reason: "Best balance of user story fidelity, professional film grammar, reference consistency, and model feasibility."
  user_confirmation_required: true
  user_question: "用户确认点: 接受六镜头市政现实主义方案，还是改成 4 镜头慢节奏或 8 镜头快剪？"

## Director Room Recommendation

Show this council result in chat before shot-list approval. Make clear that the original story is preserved, broad concept ideation is skipped, and user confirmation moves from story invention to execution choices.

skill_run_receipt:
  run_id: complete-idea-director-room-2026-05-17
  skill_id: director-room
  input_artifacts:
    - examples/complete-idea-segmentation-test/01-complete-idea.md
  output_artifacts:
    - examples/complete-idea-segmentation-test/02-director-room-notes.md
  decisions:
    - "Run director-room in complete-idea validation mode."
    - "Preserve the supplied story and use the council to decide pacing, reference locking, and model handoff."
    - "Recommend six-shot civic realism and V2 sequential reference locking."
  unresolved_questions:
    - "Real user must choose six-shot, four-shot, or eight-shot execution before assisted generation."
  qa_gate:
    status: pass
    reasons:
      - "Director-room council includes all required roles, disagreements, resolution notes, and user-facing execution options."
      - "model_prompt_engineer and continuity_qa explicitly block unsafe reference/image/video handoff."
  next_recommended_skill: chat-facilitator
