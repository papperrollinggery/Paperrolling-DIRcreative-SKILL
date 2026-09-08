# Model Prompt Craft

Use for bounded image/video prompts and revisions. Return the copyable prompt,
then essential bindings. Do not imply generation or media exists.

## Content and structure

Video starts with Style, Cinematography, Lighting, Color, Camera, Skin, Acting,
Physics, Composition, Continuity, Technical and Audio, then concrete shots.
Use declared scene facts; `video-quality-prefix.md` is optional detail. One block
per submission, not per shot. Image work keeps still-image rules. The user's
structure overrides a collaborator's default heading-free prose.

Keep a complete tested prompt as the authored baseline. Change only requested
or demonstrably conflicting content; do not automatically translate, expand or
add a style capsule. Formal bindings, when needed, are mechanical metadata.

Resolve the relevant visible facts before surface adaptation:

- identity, dominant action, environment, spatial relations and object states;
- shot size, angle, lens, support, movement endpoints, focus and temporal beats;
- motivated light, material, atmosphere, palette and grade;
- each input's role: identity, environment, composition, literal frame, style,
  motion or planning-only;
- preserve/change boundaries, allowed incidental changes and targeted avoids;
- desired sound versus its actual generation or finishing route.

Templates supply structure. Compare people, props, setting, camera, actions and
sound with current facts. Remove old content instead of turning it into negative
lists. If residue remains, use `prompt-contamination-guard`. Keep internal IDs,
QA/account notes and local paths outside copyable text; aliases bind real inputs.

## Adaptation boundaries

1. Keep the supplied model/version/surface. Verify relevant capabilities officially;
   do not guess reference limits, duration, audio, editing or extension support.
2. Prioritize identity, action, camera and chronology. To fit a prompt budget,
   remove repeated adjectives/negatives, secondary atmosphere and optional metadata;
   retain unique design constraints. Split overloaded action chains rather than
   hiding missing capacity in prose.
3. Storyboards remain planning truth, not substitutes for clean first/end frames.
   Hand-drawn shot-order/action/camera references require the exact card's
   `storyboard_reference: conditional_with_explicit_role_binding`.
   `conditional_inferred_from_omni_reference` permits a labeled, unverified trial
   from documented image input. Prevent copied panel borders, shot labels, arrows
   and production marks; retain intentional in-world text/SUPER. UI screenshots
   and management tables stay planning-only.
4. Never preserve and change the same property in one edit. Rights audits,
   capability receipts, hashes and generation authorization belong to execution
   or formal handoff, not ordinary prompt revision.
5. Seedance 2.5 formal work uses Studio and the current `mr-li-seedance-25` method.
   Add `seedance-25-emotion-prompt` only for emotion/micro-performance-led work.
   Small revisions stay Fast without claiming the full method; cards own surface
   capabilities.
6. Bind one unified recurring-character master per unit: headed by default, or
   a user-requested/evidence-triggered headless-safe derivative, never both.
   Add detail sheets only for visible shot needs. `character-master-sheet.md`
   owns layout, provenance and review; this layer binds the selected asset.

State a specific missing capability/reference only when it changes usability.
