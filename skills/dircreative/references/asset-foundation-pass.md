# Staged Asset Foundation Pass

Read this reference only for the `asset_foundation` scenario or when validating
the asset gate before `script_to_seedance`.

Persist the pass with
`docs/film-preproduction/schemas/asset-foundation-pass.schema.json` and validate
it using `python3 scripts/dircreative_asset_foundation_pass.py validate <pass> --artifact-root <root>`.

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
