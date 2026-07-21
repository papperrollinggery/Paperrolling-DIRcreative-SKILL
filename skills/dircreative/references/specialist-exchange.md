# Specialist Exchange Runtime

Use only after the native validator confirms the versioned descriptor, exact
registered handoff file and hash, unique ADCO exchange-index row, descriptor
snapshot, locked input files and hashes, brief binding, requested capabilities,
and isolated output/receipt scopes for an `adco.specialist-exchange` message
selecting `dircreative.film-preproduction`. Schema validity alone does not
activate this runtime.

## Ownership

- ADCO owns Current Truth, Goal, versions, user confirmations, adoption, client
  visibility/readiness, completion, and cleanup.
- DIR owns only the requested film-preproduction output and its domain QA.
- Execute v2 inline. Reject nested dispatch and do not create another worker,
  Thread, council, project, or control plane.

## Work

1. Treat `brief_snapshot`, `locked_decisions`, `requested_outputs`, and
   `quality_targets` as the complete host context unless one missing creative fact
   makes the output impossible.
2. Produce the requested artifact using the relevant DIR craft guidance without
   copying host state into a parallel structure.
3. Validate only the output and its direct dependencies.
4. Never write into a locked-input directory. Write the receipt only to ADCO's
   registered path as a new file; never overwrite an existing path.
5. Return status, output references with real hashes when files exist, domain QA,
   limitations, and open questions. Do not return client/send/project/control-
   plane readiness claims.

v1 messages remain readable under their v1 validator. Never rewrite a v1 record
in place or use its larger receipt as the v2 output template.
