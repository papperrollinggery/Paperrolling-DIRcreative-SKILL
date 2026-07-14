# Director Room Notes

artifact:
  artifact_id: noodle-director-room-v1
  version: 1.0.0
  source_artifact_ids:
    - noodle-idea-intake-v1
  status: approved
  owner_skill: director-room

## Roles

Live default is real sub-agents. This fixture uses `execution_mode: simulated_role_passes_fallback` only because examples cannot spawn live worker agents.

council_protocol: director-room-council-protocol

execution_mode: simulated_role_passes_fallback

subagent_default: true

fallback_reason: "dry-run fixture cannot prove live sub-agent execution"

## Role Cards

role_cards:
  producer:
    protected_value: "15-second vertical ad must stay clear, shippable, and testable."
    sees_in_idea: "A late-night office worker needs a quick warm meal."
    main_concern: "Too much mood can hide the product benefit."
    recommendation: "Use one office table, one cup, one actor, and one visible heat transformation."
  creative_director:
    protected_value: "Premium emotional taste."
    sees_in_idea: "A quiet pause from cold screen fatigue into warm relief."
    main_concern: "Generic noodle beauty shots will feel like stock food advertising."
    recommendation: "Make the emotional hook the blue-to-warm light shift caused by steam."
  director:
    protected_value: "Readable behavior and motivated camera."
    sees_in_idea: "The actor is not performing hunger; they are returning to themselves."
    main_concern: "A rushed performance makes the spot feel like a cheap snack ad."
    recommendation: "Block the scene as hand, timer, steam, breath, product hero."
  screenwriter:
    protected_value: "No wasted words."
    sees_in_idea: "The story can work without spoken dialogue."
    main_concern: "Adding voiceover too early will explain what the image can show."
    recommendation: "Use one final title line only after product proof lands."
  cinematographer:
    protected_value: "Product clarity inside cinematic light."
    sees_in_idea: "Cold monitor light and warm broth steam can carry the transition."
    main_concern: "Low-key noir lighting may hide cup text, steam, and noodles."
    recommendation: "Use 28mm office context, 50mm action, 85mm steam and product insert."
  production_designer:
    protected_value: "Recognizable product identity."
    sees_in_idea: "Ivory paper cup, red seal band, copper foil lid edge, clean black typography."
    main_concern: "Tiny text on a dense reference board can be misread downstream."
    recommendation: "Lock large label geometry and avoid small readable copy inside video references."
  editor:
    protected_value: "15-second legibility."
    sees_in_idea: "Five shots are enough: office, seal, steam, sip, hero."
    main_concern: "More shots would reduce product dwell time."
    recommendation: "Hold the steam and first-sip beats longer than the setup."
  sound_designer:
    protected_value: "Tactile product proof."
    sees_in_idea: "Office hum, kettle click, peel tab, broth pour, first sip."
    main_concern: "Music can make the ad feel generic and reduce material realism."
    recommendation: "Keep music optional and very low; lead with practical sound."
  model_prompt_engineer:
    protected_value: "Reference inputs must be clear for image and video models."
    sees_in_idea: "The workflow needs product board, environment board, storyboard motion board, and clean first frame."
    main_concern: "Text-heavy boards and arrows can be misread as scene content by Kling or Runway."
    recommendation: "Use dense boards for planning and clean frames for direct image-to-video."
  continuity_qa:
    protected_value: "Stable product, actor, hand position, steam, and label."
    sees_in_idea: "A simple product ad can still drift across generated shots."
    main_concern: "Cup label, red band, noodle texture, and steam density may change between frames."
    recommendation: "Lock cup design, steam behavior, actor hand, table props, and no-scales noodle texture guard."

## Discussion Round 1: Role Brief Read

- producer: The spot should prove the workflow with one executable 15-second ad, not a larger campaign.
- creative_director: The strongest concept is not food appetite; it is late-night emotional recovery.
- director: The actor should feel caught in a real pause, not posed for a product demo.
- screenwriter: The scene should use almost no words.
- cinematographer: The lighting transition can explain the product benefit.
- production_designer: Product identity needs a large, simple label system.
- editor: Five shots are enough for one 15-second unit.
- sound_designer: Practical sound should carry the heat and material detail.
- model_prompt_engineer: Reference images must be split by role before prompt compilation.
- continuity_qa: Product and hand continuity must be treated as locks, not suggestions.

## Discussion Round 2: Disagreements

disagreements:
  - topic: "Mood versus product clarity"
    role_positions:
      - "creative_director wants quiet premium warmth."
      - "cinematographer warns dark office contrast may hide the cup and noodles."
      - "producer requires product benefit to read in the first 6 seconds."
    decision_pressure: "The ad fails if it looks beautiful but the product is unclear."
    resolved_as: "Use cinematic lighting, but keep cup face, red seal band, steam, and noodles readable in every product beat."
  - topic: "Dense reference board versus direct video input"
    role_positions:
      - "model_prompt_engineer wants compact boards for maximum planning density."
      - "continuity_qa warns that arrows, tiny labels, and panel borders can be treated as visual content by video models."
      - "production_designer needs enough product detail to preserve identity."
    decision_pressure: "The same image cannot safely act as both production board and clean first frame."
    resolved_as: "Create dense boards for planning and separate clean frames for direct Kling/Runway/Veo image-to-video input."
  - topic: "Music versus real material sound"
    role_positions:
      - "sound_designer wants office hum, kettle click, seal peel, broth pour, and sip to lead."
      - "creative_director allows low music only if it does not flatten realism."
      - "editor wants silence around the first steam reveal."
    decision_pressure: "Audio must support product proof instead of generic comfort advertising."
    resolved_as: "Use practical sound as primary audio; music stays optional and low."

## Discussion Round 3: Resolution

resolution_notes:
  - production_rule: "Concept must show a visible cold-to-warm transformation before the final hero frame."
    rationale: "This turns mood into product proof."
    downstream_owner_skill: script-treatment
  - production_rule: "Reference pack must include separate product identity board, environment camera board, storyboard motion board, and clean first frame."
    rationale: "Dense planning boards are useful, but direct video inputs need clean scene frames."
    downstream_owner_skill: reference-image-planner
  - production_rule: "Video prompts must avoid asking the model to read small board text or arrows."
    rationale: "Seedance can use explicit role binding, while Kling, Runway, and Veo need cleaner first-frame logic."
    downstream_owner_skill: video-model-adapter
  - production_rule: "Audio plan should name practical sounds and mark music as optional."
    rationale: "This prevents a generic ad mood from replacing product tactility."
    downstream_owner_skill: script-treatment

## Discussion Round 4: User-Facing Concept Options

user_facing_options:
  1:
    concept_name: "Last Light At The Desk"
    one_line_story: "A tired office worker opens the noodle cup, and steam slowly turns the cold desk into a warm pause."
    visual_promise: "Blue monitor light shifts into amber broth steam."
    production_risk: "If the setup is too dark, product detail is lost."
    reference_pack_implication: "Needs product identity board, office camera board, storyboard motion board, and clean first frame."
  2:
    concept_name: "Platform Warmth"
    one_line_story: "A commuter waits on a rainy platform and uses the hot cup as a small private shelter."
    visual_promise: "Rain reflections, platform lights, hands around cup."
    production_risk: "Outdoor weather and crowd detail can distract from the cup."
    reference_pack_implication: "Needs stronger environment board and clean first frame separation."
  3:
    concept_name: "Night Driver Pause"
    one_line_story: "A delivery driver stops for one heated meal before the next route."
    visual_promise: "Dashboard light, window rain, steam in a parked car."
    production_risk: "Car interior may compress blocking and product visibility."
    reference_pack_implication: "Needs vehicle interior board plus product identity board."

recommendation:
  option_id: 1
  reason: "Best balance of product clarity, emotional hook, controllable set, and 15-second readability."
  user_confirmation_required: true
  user_question: "用户确认点: 选 1/2/3，或说你想混合哪两个方向。"

## Director Room Recommendation

Offer the user these three creative directions in chat. Recommend option 1, but do not lock the concept unless the user chooses or the fixture records `decision_source: simulated_fixture`.

skill_run_receipt:
  run_id: noodle-director-room-2026-05-16
  skill_id: director-room
  input_artifacts:
    - examples/live-user-sim-noodle/01-idea-intake.md
  output_artifacts:
    - examples/live-user-sim-noodle/02-director-room-notes.md
  decisions:
    - "Run director-room as simulated role passes with visible council discussion."
    - "Prioritize warmth, restraint, product clarity, and reference-pack safety."
  unresolved_questions:
    - "User should choose the creative direction."
  qa_gate:
    status: pass
    reasons:
      - "Director-room council includes role cards, discussion rounds, disagreements, resolution notes, and user-facing options."
      - "model_prompt_engineer and continuity_qa pressure-tested downstream reference and video-model risks."
  next_recommended_skill: co-creation-gate-runtime
