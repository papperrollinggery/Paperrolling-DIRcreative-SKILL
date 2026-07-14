# TapNow Agentic Canvas Lessons

Verified: 2026-05-16

Purpose: capture TapNow-style agentic canvas ideas that are useful for DIRcreative without making TapNow a required runtime.

## Publicly Observed TapNow Patterns

TapNow presents itself as an agentic creative canvas that unifies text, image, audio, and video models in one workspace. Its docs describe a flexible canvas for scriptwriting, storyboarding, and finished visual content.

Relevant public behaviors:

- Infinite canvas is the visible workspace for a production workflow.
- TapTV shared canvases let users inspect, reuse, and build on a visible creative process.
- Nodes can generate text, generate images, upload local images, and connect text/image nodes as video references.
- Prompt Optimizer expands a simple image prompt into a more professional instruction.
- Multi-image generation accepts references such as style and scene.
- Start/end frame video generation connects two image nodes to a video node.
- TapNow docs emphasize that better starting frames improve video quality.
- Advanced image fusion uses cutout, size, angle, and position adjustments before AI generation, improving consistency and detail control.

## Useful Lessons For DIRcreative

### 1. Treat The Workflow As A Graph

DIRcreative should expose a logical graph, not only a folder of files:

```text
idea node
-> director room node
-> story node
-> script node
-> shot list node
-> visual bible node
-> reference asset nodes
-> image prompt nodes
-> model video prompt nodes
-> QA node
```

Each node needs:

- role,
- source artifacts,
- user gate status,
- output status,
- downstream model safety.

### 2. Separate Human Boards From Direct Model Inputs

TapNow-style canvas flow makes it tempting to connect every image to every video node. DIRcreative should be stricter:

- dense storyboard boards are for human review and shot-order planning,
- product/person boards are for identity locking,
- scene/style boards are for reference context,
- clean start/end frames are direct I2V inputs,
- direct video nodes should receive only model-safe assets.

### 3. Add A Canvas Graph Receipt

Future DIRcreative workbench exports should include a simple graph receipt:

```yaml
canvas_graph_receipt:
  nodes:
    - node_id:
      node_type: idea | script | shot_list | reference_board | clean_frame | image_prompt | video_prompt | qa
      role:
      source_artifacts: []
      asset_output_status:
      user_gate:
  edges:
    - from:
      to:
      relationship: derives_from | references | direct_video_input | qa_checks
      allowed_for_video_input: true | false
      risk_note:
```

This keeps the process inspectable in chat, terminal, and future UI.

### 4. Preserve Prompt Optimizer Provenance

If DIRcreative adds a prompt optimizer step, it must keep both:

- original JSON-first intent,
- optimized natural-language prompt.

The optimized prompt cannot replace the structured source, because downstream QA needs the original locks, references, and forbidden elements.

### 5. Use Fusion Logic For Consistency

For product, character, wardrobe, and set continuity, DIRcreative should model reference generation as layer-aware planning:

- base scene,
- product/person cutout,
- wardrobe/prop layer,
- lighting/material direction,
- clean frame export.

This matches the practical lesson from advanced image fusion: consistency improves when components are positioned and controlled before generation.

### 6. Start/End Frames Are A Strategy, Not A Default

For every shot or 15-second sequence, DIRcreative should choose:

- single clean first frame,
- clean start/end frames,
- all-reference sequence,
- hybrid reference pack,
- prompt-only export.

The choice depends on action complexity, continuity risk, model behavior, and user review cost.

### 7. Make Process Visible

TapTV's shared-canvas idea reinforces the main DIRcreative UI rule: the user should see the process, not be told that files exist.

DIRcreative chat output should show:

- current node,
- upstream locked decisions,
- next user gate,
- what will be generated or exported,
- what is blocked.

## What DIRcreative Should Not Copy Blindly

Do not copy blindly:

- Do not rely on TapNow-specific UI or private app behavior.
- Do not assume "agentic canvas" means a portable agent protocol.
- Do not allow arbitrary graph edges that bypass story, script, shot list, or visual bible gates.
- Do not treat a dense canvas board as a safe direct video input.

## Immediate Implementation Impact

- Reference-image planning should keep asset-node roles and direct-input policy.
- Video-model adapter should export a model input graph: prompt node plus allowed image nodes.
- Chat facilitator should explain the current graph step when the user asks "现在到哪了".
- Future workbench can render the same graph without changing the core skill.
