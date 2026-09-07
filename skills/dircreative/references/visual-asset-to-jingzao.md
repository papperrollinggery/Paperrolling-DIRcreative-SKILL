# Visual asset to Jingzao

Use this handoff only after DIR has decided that a formal image asset needs a
maintainable visual spec, reference-aware compilation, an edit/preserve plan, or
complex continuity/layout control. It is not the default for every image.

Typical triggers include a multi-view character master, multiple required
references, exact scene geography, a high-risk prop state, a mask/region edit,
or a previously observed material/artifact failure. A simple single-subject
image with no continuity, attachment, edit, or precision-layout requirement may
keep the concise direct ImageGen path.

Standalone asset requests use the existing visual plan with `scope: asset_only`
and `medium: still`; leave time-based fields null and timeline arrays empty.
The same active-asset and handoff checks apply without a fictitious film brief.

DIR owns the asset ID, role, purpose, truth hash, dependency order, approved
upstream artifacts, and downstream state. `jingzao-image-forge` owns the
`visual_generation_spec`, prompt compilation, prompt review, reference handoff,
and image-call plan. The host image tool remains the execution adapter. Neither
prompt compilation nor a successful tool call grants visual approval.

The handoff must bind:

- the active visual-plan snapshot and asset truth;
- the Skill Stack receipt that selected `jingzao-image-forge` for
  `visual_asset_compile`;
- the installed Jingzao Skill body and exact reference files read;
- the selected asset-foundation design stages and any required image-reference hashes;
- the input request, validated visual spec, validation receipt, compiled prompt
  manifest, prompt hash, and ImageGen call-plan status;
- the delivery route without claiming that an image was generated.

The inventory-derived visual plan stores `compile_route` as `direct_concise`,
`selected_skill_handoff`, or `deterministic_assembly`; execution cannot infer a
direct route merely because the handoff is absent. Before an asset exists, use
the `in_progress` design pass described in `asset-foundation-pass.md`; do not
require the image being created or a post-generation stress report. Its selected
stages bind owners, collaborators and exact structured artifact hashes; arbitrary
nonempty Markdown cannot replace them. A complete certified pass remains valid
for existing assets. The Jingzao spec must match the active
operation and purpose. Every image reference must already appear in the
foundation source set with an allowed rights/approval state, then appear exactly
once as a local `must_attach` input and in the compiled call plan.

An authored 2D layout/sketch can be a `planning_only` foundation source and a
`layout` input with exact path/hash and `reference_only_approved` scope. It controls
only its declared arrangement, never identity or material. A layout declaring
`spatial_source` still requires the verified spatial export; an ordinary panel
guide does not need to impersonate a measured 3D scene.

Validation replays the current DIR selector and the hash-bound Jingzao validator
and compiler from sealed copies. On macOS provider replay runs with isolated
Python, a minimal environment, no network, no home-directory reads, and no file
writes outside the replay directory. Provider identity failure stops before any
script execution. Replay uses the exact reference bytes that were hash-checked,
and compilation starts only after spec validation succeeds. Provider and project
roots must not contain each other. For edits, add Lira or constraint input only
when needed.

The execution packet must consume the exact compiled prompt hash from this
handoff. Missing provider files, changed upstream truth, `prompt_review` other
than `ready`, unresolved required references, or a non-ready ImageGen call plan
blocks the formal asset. A direct DIR prompt may still be used for rough or
low-risk work, but it cannot impersonate this handoff.
