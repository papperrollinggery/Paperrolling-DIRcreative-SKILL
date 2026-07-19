# DIRcreative Durable State Audit Guide

Status: supporting guide for resume, handoff, Delivery, and completion audits.
It is not a Fast or ordinary Studio startup contract. The active v2 working-state owner is
`skills/dircreative/runtime/state-snapshot.schema.json`. It contains only project,
route, locked facts, assumptions, active/stale outputs, open questions, and the two
external authorization booleans.

## V2 Persistence Policy

- Fast keeps the compact snapshot in memory and does not write state by default.
- Studio persists it only for a pause, cross-session resume, or multi-file output.
- Delivery always persists it before authorization or client-visible handoff.
- Standalone execution does not read ADCO documents.
- Only a validated ADCO handoff may load the ADCO integration contract; ADCO then
  owns Current Truth and DIR returns only domain output plus domain QA.
- Do not run the full state audit before every response. Run it only for resume,
  handoff, Delivery, or a completion claim.

The remainder of this document defines the full durable audit surface used at
those four boundaries and the read-only v1 migration contract. It is not a Fast
or ordinary Studio startup dependency.

This contract governs standalone DIRcreative durable project state. It does not
replace ADCO current truth. Under `orchestrated_worker`, DIR returns only its
scoped provider artifacts and receipt; ADCO owns the host projection and
adoption.

## Full Durable State Location

Store the current standalone state at:

```text
.dircreative/state/current.json
```

The file must conform to `docs/film-preproduction/schemas/runtime-state.schema.json` and declare `schema_version: 1.0.0`.

`current.state_kind` distinguishes a versioned `repository_baseline` from a `live_session`. A repository baseline must remain empty of live records, acceptance, authorizations, and thread claims; only live sessions require a reconciliation timestamp no older than 24 hours.

The audit validates the complete Draft 2020-12 schema before semantic checks. It uses `jsonschema` when available and a packaged fail-closed validator for the schema features used here otherwise. Malformed arrays, missing required fields, extra fields, bad timestamps, or wrong nested types are structured P0 findings; they must never crash the audit or fall through to `PASS`.

The chat surface remains primary. At every resume or handoff, render a current-first summary from this file:

1. current stage and blocker,
2. current artifact links,
3. current manifest and generation-authorization state,
4. live-acceptance state,
5. thread reconciliation state,
6. legacy-debt count, shown separately from current failures.

Do not ask the user to browse `.dircreative/runs/` to discover what is current.

## Current projection

`current_projection` is the only list allowed to drive the current chat view. Every referenced record must:

- exist in `records`,
- have `lifecycle: active`,
- use a unique `logical_id`,
- use a unique canonical path when a path is present,
- resolve to an existing regular file when `durable: true`,
- match its SHA-256 when a hash is recorded.

Every durable record requires a SHA-256. Durable current files must be regular, non-symlink, single-link files read through one no-follow file descriptor; an external or internal hardlink is a P0 integrity failure.

Records with `superseded`, `withdrawn`, `archived`, or `removed` lifecycle never appear in `current_projection`. Their original path is retained as evidence; it is never rewritten to a summary or replacement path.

The user-facing current artifact list uses `canonical_path`, verifies existence first, and emits a clickable absolute file link in hosts that support it. Missing durable current files are P0 current-integrity failures, not warnings.

`current.completion_requirements` declares required record kinds, logical IDs, manifest presence, and whether live acceptance is required. A current stage may use `status: complete` only when those requirements and a durable typed completion receipt pass. An empty projection or an empty self-declared completion contract cannot prove completion.

## Supersession and tombstones

Use immutable record IDs and explicit lifecycle transitions:

```text
active -> superseded | withdrawn | archived | removed
```

- A replacement record points to the previous record with `supersedes_record_id`.
- The previous record points forward with `superseded_by_record_id`.
- Every non-active record carries a tombstone reason and timestamp.
- A removed record retains `original_path`; its path field is not repurposed to point at a surviving summary.
- Free-text status may appear in notes, but it cannot control lifecycle or current visibility.
- Supersession is an acyclic chain for one `logical_id`: revision increases strictly, the predecessor is `superseded`, links are reciprocal, and the active head has no successor.

## Semantic migration

Never make an old record appear current by filling missing fields with defaults.

For each legacy source, choose exactly one migration mode:

- `transformed`: the source was interpreted and converted into typed records with explicit current/non-current meaning;
- `quarantined`: the source is preserved as evidence but excluded from current projection because its meaning is ambiguous, stale, or incomplete;
- `already_current`: the source already satisfied the current schema without inferred semantics.

Every migration records its source, source SHA-256, from/to versions, affected record IDs, transformation receipt where applicable, mode, and timestamp. Ordinary audits and migration writes both require exact discovered/mapped coverage: a mapping cannot point at a missing source, and `from_schema_version` must equal the fully parsed source version (or `null` when parsing cannot establish one). Discovery scans nested runs and checkpoints without following symlinks, including the discovery roots themselves, but excludes durable v1 control envelopes already hash-bound by the current state. `already_current` requires a full UTF-8 JSON/YAML parse, validation against the complete current runtime schema, exact equality between mapped IDs and the source current projection, and matching canonical record content; a `schema_version` string found in a prefix is never proof. `transformed` requires a durable validation/completed receipt bound to the migration ID and exactly the converted record IDs; transformed records remain non-active and outside `current_projection` until a separate live adoption. A source with no valid `schema_version` uses `from_schema_version: null`; it can be quarantined but cannot be declared `already_current`.

Use the runtime tool in two steps:

```bash
python3 scripts/dircreative_state_audit.py migration-plan --project-root <project>
python3 scripts/dircreative_state_audit.py migrate --project-root <project> --mapping <reviewed-v1-state.json>
```

The second command is a dry run unless `--write` is explicit. A write is allowed only when every discovered legacy source has an explicit hash-bound migration entry and current integrity passes. It creates only the canonical state path. Publication uses an atomic no-clobber link, fsyncs the parent directory, and refuses concurrent or existing destinations; future version upgrades require a new reviewed migration contract.

When repository-owned legacy samples are relocated out of live runtime, `fixture_migration` binds a no-authority migration manifest. The manifest records every original path/hash and destination path/hash and declares `fixture_authority: none`, `live_state_authority: false`, `live_acceptance_authority: false`, and `host_attestation_authority: false`. The audit rejects a missing or changed destination and rejects any migrated source that reappears under `.dircreative/`.

## Current integrity and legacy debt

Audits produce two independent lanes:

```text
CURRENT_INTEGRITY: PASS | FAIL
LEGACY_DEBT: NONE | PRESENT
```

Current failures are fail-closed. Examples:

- missing current artifact or manifest,
- duplicate current logical identity or canonical path,
- current hash mismatch,
- accepted live state without a current acceptance receipt,
- generated media without a current authorization record,
- active thread record without verified task visibility,
- current projection containing a tombstoned record.

Legacy debt is reported by P1/P2 and cannot drown the current P0 result. A legacy debt item must be isolated from the current projection. If it affects current projection, it is a current-integrity failure instead.

Isolation is calculated from the debt source path and `record_ids`; `isolated: true` is only an assertion. A source matching a current path, an active/current related record, or a missing referenced record upgrades the item to current P0.

## Reconciliation

Run reconciliation before resume, delivery, archive, or completion claims.

### Disk

- Check every durable current path and hash.
- List untracked project files inside declared artifact roots.
- Treat manually added files as unclassified until the user/controller chooses adopt, archive, cache, or delete-candidate.
- Do not silently adopt a file because its name resembles an artifact.

### Acceptance and manifests

- `accepted` requires an active acceptance receipt record in the current projection.
- That receipt is a durable, hash-bound JSON envelope whose parsed payload exactly matches the state record. A `live_acceptance` receipt binds one or more durable current output records—not a thread, receipt, cache, or authorization—to a real user/client confirmation ID and actor in a fresh host snapshot. It must cover every output named by the current completion requirements. Another receipt type or a self-written `user_confirmation:` string cannot satisfy acceptance.
- Current manifest IDs must point to active, durable manifest JSON envelopes. Each typed manifest lists one or more current output record IDs; those IDs must exist, be durable, active, and non-control records. When completion requires a manifest, its bound outputs and the completion receipt must cover the required output records.
- Generated-media records require an active generation-authorization JSON envelope bound to the exact project/work, asset ID, output kind, model ID, recomputed canonical scope hash, host-confirmed human/controller actor, authorization time, and optional expiry.
- Reference media and generated media are distinct kinds even if their bytes match.

### Threads

- Persist thread ID, class, host ID, output status, terminal reason, adoption target, archive state, and last visibility check in a typed, file-bound thread payload.
- Terminal reasons use the closed vocabulary `completed`, `adopted`, `rejected`, `failed`, `system_error`, `interrupted`, `duplicate`, `superseded`, or `abandoned`; active threads use `null`.
- Verify real Codex task visibility with the host thread tool before completion. Export the fresh `codex_app.list_threads` result plus relevant confirmation message IDs into the `--thread-snapshot` input; a state file cannot verify its own thread claim.
- The payload and evidence timestamps must match and be no older than 24 hours. A stale receipt cannot prove that the task is still active, archived, or cleaned up.
- `--thread-snapshot` is diagnostic input, not a signed host attestation. A JSON file can validate shape and cross-references but can never by itself grant live acceptance, generation authorization, task visibility, or completion. The controller must perform a live `codex_app.list_threads`/thread readback in the active Codex task; until that trusted tool check exists, the local audit returns `live_host_attestation_required` and fails closed.

## Storage lifecycle

Every record has one storage class:

| Class | Meaning | Default action |
| --- | --- | --- |
| `final` | User-approved final deliverable | Preserve; never delete without explicit confirmation |
| `necessary_archive` | Required provenance, prior approved version, receipt, or non-reproducible source | Preserve or review with the user/controller |
| `regenerable_cache` | Preview, render, extract, or cache reproducible from durable sources | Regenerate before removal when still needed |
| `delete_candidate` | Rejected duplicate, stale preview, abandoned generated candidate, or orphaned cache | Propose removal; never delete silently |

The project declares bounded, non-overlapping `artifact_roots` and `control_roots`, a byte budget, and a warning ratio. The v1 class policy is fixed: final=`preserve`+confirmation, necessary_archive=`review`+confirmation, regenerable_cache=`regenerate_then_remove`, and delete_candidate=`remove_after_confirmation`+confirmation. Final and necessary archives are non-regenerable; regenerable caches must be reproducible. Every durable record must be inside the appropriate declared root. Receipts, manifests, authorizations, thread proofs, runs, and checkpoints use control roots and cannot be cache/delete candidates. `.git`, `.dircreative/state`, root policy files, and paths outside the declared roots cannot be registered as managed artifacts. A self-written tombstone cannot authorize physical deletion: `removed` remains fail-closed until a trusted live host/controller attestation mechanism is available, and `original_path` is still retained. Storage reporting scans both root classes without following links, requires every file to be classified, counts all managed durable records plus untracked root bytes, identifies duplicate physical/content storage and directory-plus-ZIP parallel storage, and reports ZIP packages separately from references, generated media, previews, and caches. Equal hashes are evidence for review, not automatic deletion.

## Standalone completion boundary

A standalone DIR run is not complete merely because repository fixtures pass. Completion requires:

- current integrity passes,
- required current artifacts exist and are user-readable,
- live acceptance is present when the goal requires it,
- thread and disk reconciliation are current,
- final and necessary-archive records are classified,
- cache and delete candidates are reported without destructive action,
- legacy debt is disclosed separately.

Synthetic fixtures prove contracts only. They do not prove creative quality, user acceptance, or the existence of a real current project.

Release and install packages retain only `.dircreative/checkpoints/.keep` and `.dircreative/runs/.keep`. They do not publish `current.json`, historical receipts, timeline, learnings, or migration fixtures as consumer runtime truth.
