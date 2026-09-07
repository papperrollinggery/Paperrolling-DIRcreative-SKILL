# Staged Asset Foundation Pass

Read this reference only for the `asset_foundation` scenario or when validating
the asset gate before `script_to_seedance`.

Persist the pass with
`docs/film-preproduction/schemas/asset-foundation-pass.schema.json` and validate
it using `python3 scripts/dircreative_asset_foundation_pass.py validate <pass> --artifact-root <root>`.

## Initial design and source scope

Independent asset requests use `scope: asset_only` and the existing
`asset_pass_scope: initial_design` stage selection. This only prepares the relevant
design pass (`in_progress`, no side effect); it cannot certify the pass, skip
stress/review, or authorize media. Do not require screenplay/timed-shot artifacts
for a standalone character or scene. In mixed storyboard-and-asset work, enumerate
every recurring identity and critical scene/prop from the authorized story before
the first generation. A supplied portrait is an identity input unless direct reuse
was selected; it is not evidence that the remaining characters or views exist.

Compare the current source, scene heading and adjacent state before making a
state-dependent asset or prompt. Resolve meaningful contradictions from actual
source/user evidence; leave an unresolved conflict attached to its affected work
and continue independent work. Ordinary unspecified craft details remain design
judgments. Do not silently turn a review suggestion into the production source.
Offscreen, cropped and occluded characters retain their established presence and
state until the source establishes an exit or change.


## Before the first image

An asset being created cannot supply its own completed image or stress report.
For image compilation, the same pass may remain `in_progress` with explicit
`planned_asset_ids`, only the selected design stages, and
`stress_test_binding: null`. Keep `compile_gate.status: blocked`: this is the
video-compilation gate, not image authorization. `source_assets` contains only
actual supplied or previously generated inputs and may be empty. Planned IDs
must not be presented as `canonical_asset_ids`.

The image handoff uses `validate_design` to check the selected stage owners,
required craft, structured output, source files and hash chain. A character
needs identity/wardrobe/state design; a scene needs camera/geography design.
Load other stages only when needed. This design check does not certify images;
the complete pass and stress gate below remain required before Seedance.

## Stable passes

Run one bounded pass at a time. Each pass consumes the exact hash of the prior
output and returns ownership to DIRcreative.

| Pass ID | Owner | Optional collaborator / validator | Output purpose |
| --- | --- | --- | --- |
| `identity_state` | `minimum-visual-bible` | `character-continuity-bible` | descriptor, identity, wardrobe/prop and state-family truth |
| `production_design` | `production-design-worldbuilding` | none by default | world, location, vehicle and prop language |
| `camera_geography` | `master-shot-camera-planning` | none by default | GEO, landmarks, axis, camera zones and FOV |
| `material_response` | `ai-material-realism` | none by default | target material/light response |
| `constraint_assignment` | `constraint-input-router` | none by default | one primary role and must-not-control scope per reference |
| `stress_certification` | DIRcreative | validator: `ai-film-asset-stress-test` | certified or conditional shot scope |

Do not load all owners into one Studio context. A failed, missing, or incomplete
pass keeps later work blocked. Planning boards remain planning-only and never
become identity, topology, geography, or clean-frame truth.

For a recurring clothed human, use the canonical v3 rules in
`character-master-sheet.md`. This pass only owns stage order: bind generation
input provenance, produce one headed master, derive optional headless/detail
surfaces from it, then pass exact hashes into stress certification. State
variants remain versioned local derivatives. Legacy v1/v2 reports stay readable
but do not gain v3 guarantees.

## Seedance gate

Seedance compilation requires the complete pass file plus the bound stress-test
report, actual file hashes, complete stage coverage, and a compile scope allowed
by a `certified` or `conditional` verdict. The handoff validator re-runs both
validators; summary labels alone are insufficient.

Every stage input/output carries a project-relative path and SHA-256 over the
actual bytes. A passed output is structured JSON bound to project, pass, stage,
input hash, gap accounting, payload hash, and stage-specific minimum content;
arbitrary or hollow bytes cannot satisfy the pass. The stress report must cover the exact canonical asset set; a
single-asset report cannot certify an unrelated character, location, prop, or
vehicle in the same pass.

The intake also carries canonical/planning source records with relative paths
and actual byte hashes. One source path or content hash has one role; renaming a
planning board cannot promote the same bytes into a canonical identity,
topology, geography, or clean-frame asset.

Completion means only that the scoped asset foundation is ready for prompt
compilation. It does not mean generated media, `visual_assets_complete`, user or
client approval, host adoption, installation, or delivery.
