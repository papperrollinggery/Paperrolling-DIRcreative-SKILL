# Product CG direction

Use this bounded craft reference inside existing film development or the
`production_design` foundation pass when product CG, material macro or a related
style pack is requested. Inherit [asset foundation](asset-foundation-pass.md),
current product truth, scope and generation authorization. This is not a new
route, approval stage or compulsory questionnaire. A prompt-only edit stays an
edit; analysis alone does not create assets or call a model.

## Work from the product

Start with the supplied product, existing storyboard and requested viewer effect.
Identify what is known about geometry, finish, components, material state and
function. Inspect actual references when supplied. Keep observed features,
author-provided facts, design interpretations and unknowns distinct. Do not
infer ingredients, micron sizes, waterproofing, mechanical internals or efficacy
from attractive images. A fictional product may use explicitly authored design
facts without pretending they are engineering evidence.

For each important choice, give the user a concise, reviewable rationale:
`product fact → viewer understanding/feeling → visible event → shot control → check`.
This is a decision summary and research method, not a request for private internal
reasoning. Use the supplied facts first; ask only for missing facts that change
the deliverable. When facts are unavailable, select an honest expressive metaphor
or state the assumption rather than inventing a product claim.

## Choose the visual system

Read the small [catalog](product-cg/catalog.json), then only the selected capsule.
Choose by the material behavior and communication job, not merely by industry.
The same device can use precise hard surfaces, a sculptural treatment or graphic
modules for different briefs. Six initial families are available:

- **柔光干粉 / pastel-dry-powder-cg**: dry grains, selective macro detail, soft
  packaging reflections and contact/lift contrast.
- **精密硬表面 / precision-hard-surface-cg**: continuous reflection bands,
  meaningful edges, readable assembly or operation supported by product facts.
- **弹性与织构 / elastic-fiber-cg**: strain, release and fiber direction; separate
  expressive secondary material from the allowed deformation of the product.
- **流变触感 / viscous-sensory-cg**: coating, stretching, fracture and flow;
  distinguish each target's viscosity, wetness and solid/liquid boundaries.
- **雕塑材质 / sculptural-luxury-cg**: true material cues with one deliberate
  surreal spatial relation, precise silhouette and controlled negative space.
- **图形模块 / graphic-modular-cg**: reduced surface frequency, bold volume and
  modular rhythm; preserve deliberate stylization rather than forcing live action.

Use one primary family. A secondary influence must own a different named layer.
Target product identity, palette, layout, text, physical properties and requested
rendering method override the capsule. Pastel powder is one named option, not the
default for every product. Source packaging, brand copy and exact layouts are not
style. Capsule validation describes tested transfers; it does not certify every
product or a generated moving film.

## Turn material into a sequence

Keep **render treatment**, **material behavior** and **shot progression** separate.
A chrome-like appearance does not authorize liquid metal transformation. A
photorealistic render can depict an explicit metaphor; mark the metaphor instead
of presenting it as a real product process.

Every active element needs a visible origin, a reason to move, a destination and
a purpose in the product story. Choose only the mechanisms that help:

- **Array to hero**: repetition establishes scale and rhythm, then attention moves
  to one subject. Preserve SKU, size, geometry and a readable hero; perspective
  changes projected size, not the physical dimensions of identical products.
- **Macro to material**: enter an existing surface or boundary to reveal a new
  property. Specify viewing distance, focal intent, angle, focus plane and detail
  hierarchy. A focal number alone cannot define perspective or material scale.
- **Contact to release**: show the correct tool/material approaching, contacting,
  deforming or adhering, then separating. Brush fibers, velvet, rubber and hard
  probes have different contact behavior; do not substitute one for another.
- **Element excursion and return**: an outward particle burst and inward return
  require different start/end states, flow direction and contact endpoints. A
  still cannot prove temporal direction. Keep the product intact unless a breakup
  is explicitly intended; name the visual metaphor when material leaves/reforms.
- **Material as landscape**: enlarge an existing material feature, then preserve
  a shape, texture or light anchor that returns to the product. Avoid unrelated
  spectacle. Do not infer manufacturing facts from the metaphor.
- **Precision process**: use verified alignment, assembly, load or mechanism facts.
  Reveal the consequence of the action, rather than merely orbiting a machine.
- **Graphic or sculptural reveal**: rhythm, silhouette and controlled obscuration
  organize recognition. A brand's typography or iconic geometry is not a generic
  reusable motif; use target-approved content only.

A useful progression often establishes the object, reveals a material or
functional difference, provides contact/action evidence and returns to product
recognition. It is not a mandatory order. Preserve a supplied film's shot slots,
performer scenes and timing; improve the work inside those constraints.

## Design the joins and timing

Each shot must add information or intentionally sustain a moment. Describe its
entry anchor, main change and exit anchor using the existing shot cards/PromptIR.
Possible joins include shared silhouette, screen direction, contact state,
reflection sweep, material boundary, depth/focus, occlusion or an authored sound
cue. Name the actual relation; “seamless transition” alone is insufficient.

Describe approach → event → settle/recognition, selecting only necessary phases.
Keep the total duration and generation-unit budget from the brief. Additional
state frames and alternatives are not automatically extra shots or extra seconds.
Mark alternatives as mutually exclusive. If a join is unclear, use a short textual
bridge or a transition frame; do not restage the entire film. Lens and speed values
are authored design intent unless the source actually establishes them.

For clean CG story frames, keep camera notes, arrows and shot numbers in the
caption/shot list. An explicitly requested technical or annotated board retains
its annotations; this reference does not disable that deliverable.

## Use the existing production handoffs

For new assets, write design evidence before generation using the current
foundation pass. A finished output cannot be its own design prerequisite. Copy
only the chosen source-image-free capsule into the target project. Bind its exact
bytes through `output_spec.style_capsule = {relative_path, sha256}` and the existing
[visual asset handoff](visual-asset-to-jingzao.md). The preparation command already
accepts `--style-capsule`; Jingzao compilation uses the same flag. A capsule is
text/style input, never a product-identity image or an extra model attachment.
Keep provider prompt review and actual call-plan/reference requirements.
A reference profile and a style capsule are mutually exclusive compiler options.
Preserve an existing profile; transfer compatible material rules into the authored
target spec or keep that profile flow rather than silently discarding its facts.

For video, preserve the existing PromptIR/compiler path. Put material/palette
facts in `global_locks.palette_material`, global look in supported `render_look`
fields, local changes in `shot.look_delta`, and actions/joins in their existing
shot fields. State the chosen CG treatment in `project.intended_use` or optional
`video_quality.style`; use other optional quality overrides when an authored
lighting, optics, cadence or material law needs exact wording. Do not add an
unsupported `render_look.medium` field or an independent CG prefix. Source-derived quality direction, model-specific bindings and the
sound-generation boundary remain; irrelevant quality categories stay omitted.

A concrete example and the evidence scope are in the
[product CG examples](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/blob/main/examples/product-cg-style-library/README.md).

## Review the actual result

Review the batch after independent images are produced; stop early only for a
real dependency failure. Check product recognition and authorized geometry,
material-specific response, selective detail, contact/attachment, scale, focus,
reflection ownership and clean output requirements. For sequences also check
state progression, source/destination, cut anchors and the declared duration.
Inward/outward flow or elastic recovery needs moving evidence before claiming
video success. Still-image tests do not establish temporal coherence.

Repair only the observed defect from the best source. Retain contrast and motion
intent when reducing overly coarse powder; retain destination/contact when fixing
ambiguous return flow. Do not impose source colors, source tools or automatic
microtexture on an unrelated target. A passing file/schema check is not visual
approval. Source research and boundaries are documented in
[the research note](https://github.com/papperrollinggery/Paperrolling-DIRcreative-SKILL/blob/main/docs/film-preproduction/research/product-cg-expression-2026-09-08.md).

For local reading in either source or installed layouts, resolve the example and
research paths from the Skill root: `examples/product-cg-style-library/README.md`
and `docs/film-preproduction/research/product-cg-expression-2026-09-08.md`.
