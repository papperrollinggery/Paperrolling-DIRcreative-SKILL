# Model Prompt Craft

Use this card for a bounded image/video prompt or model-specific prompt revision.
Return the copyable prompt first, followed by only the bindings or risks the user
needs to run it correctly.

## Prompt content

Build a model-neutral intent before adapting the surface:

- subject identity and the one dominant action;
- environment, spatial relation, and relevant object states;
- camera size, angle, lens intent, support, movement start/end, and focus;
- temporal beats in observable order;
- lighting, material, atmosphere, color, and grade that affect the shot;
- reference role for each input: identity, environment, composition, first frame,
  end frame, style, motion, or planning-only;
- preserve, change, allowed incidental change, and forbidden change;
- desired audio versus where audio will actually be generated or finished;
- targeted avoid constraints for likely failures, not a generic negative dump.

## Adaptation rules

1. Use exactly one named model/version/provider surface when supplied. If current
   capability facts affect the answer, verify them from official evidence; do not
   guess reference counts, duration, audio, edit, or extension support.
2. Keep identity, action, camera, and temporal order ahead of decorative style.
   When over budget, remove redundant adjectives, secondary atmosphere, repeated
   negatives, and optional metadata in that order.
3. One generation unit should have one dominant action and a coherent spatial
   problem. Split overloaded transformations, crowds, handoffs, or long causal
   chains rather than hiding them in prose.
4. A storyboard is planning truth unless the exact model surface supports its
   direct role. Do not silently treat a dense board as a clean first frame.
5. For edits, state the invariant and mutable subfield separately. Never ask one
   pass to both preserve and change the same property.
6. Prompt revision alone does not require a rights audit, capability receipt,
   file hash, or generation authorization. Those belong only to a real execution
   or formal handoff.

Never imply that a prompt was run or media exists. State one exact unknown when a
volatile capability or missing reference materially changes usability.
