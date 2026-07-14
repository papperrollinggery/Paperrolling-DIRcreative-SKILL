# ADCO Native Specialist Exchange

Verified against the active ADCO worktree: 2026-07-10.

## Canonical Transport

DIRcreative integrates through ADCO's neutral transport, not a DIR-owned combined envelope:

```yaml
protocol_id: adco.specialist-exchange
contract_version: "1.0"
profile_id: dircreative.film-preproduction
```

The exchange has four separate JSON messages:

```text
provider descriptor -> ADCO handoff -> DIRcreative receipt -> ADCO adoption
```

DIRcreative publishes:

```text
docs/film-preproduction/schemas/adco-specialist-descriptor.json
```

Validate the portable provider side:

```bash
python3 scripts/dircreative_adco_native_exchange.py --self-test
python3 scripts/dircreative_adco_native_exchange.py validate-handoff \
  --project-root <project_dir> \
  --handoff <handoff.json>
```

Run the real cross-repository roundtrip against an ADCO checkout:

```bash
python3 scripts/dircreative_adco_native_exchange.py \
  --adco-repo <ad-creative-orchestrator-repo>
```

## Ownership

| Surface | ADCO | DIRcreative provider |
|---|---|---|
| Client/business truth | owns and versions | consumes declared source artifacts |
| User/client questions | asks and records | returns structured `open_questions` |
| Film craft | sets bounded objective and requested kinds | story, treatment, script, shots, visual bible, prompt/reference plan, domain QA |
| Execution | selects inline/thread/external mode | stays inside selected mode and exact scope |
| Adoption | owns mapping and decision | recommends only |
| Readiness | owns client, PPT, package, send gates | claims all three readiness flags false |
| Delivery | owns exports, versions, PPT, FinalDelivery | never writes those surfaces |

ADCO remains the only project integration owner. DIRcreative never updates ADCO current truth, artifact index, gate log, versions, PPT exports, FinalDelivery, client status, outer Goal, or worker cleanup.

## Optional Chat Visualization Capability

`dircreative.chat-visualization@1.0` is an optional presentation capability, not a required field in `adco.specialist-exchange@1.0` and not evidence of protocol compatibility by itself.

When a future handoff explicitly negotiates this capability, DIRcreative may return a schema-valid, hash-bound visualization spec as a neutral provider output. The provider-produced spec must use:

- `execution_context: orchestrated_worker`;
- `controller.surface_owner: ad-creative-orchestrator`;
- `controller.user_facing: false`;
- `write_boundary.write_owner: ad-creative-orchestrator`;
- a complete text fallback.

ADCO decides whether to render or convert the view, receives any user response, owns adoption, and writes host current truth. DIRcreative does not call client-facing follow-up actions from worker mode. If the capability is absent or the target surface cannot render it, use the fallback and preserve the existing v1 handoff and receipt behavior.

The current ADCO visual contract is `adco.chat-visualization@1.0` with `execution_context: orchestrated_provider`. DIRcreative does not emit that host contract directly. It returns its provider-hidden `dircreative.chat-visualization@1.0` spec; ADCO validates and projects only the customer-readable fields it chooses to adopt. The projection must keep ADCO as surface and write owner, discard DIR action handling, translate phase and production language for the user, and retain DIR's complete text fallback.

Validate the DIR-side projection logic without an ADCO checkout:

```bash
python3 scripts/dircreative_visualization_adco_audit.py --self-test
```

Validate against the current ADCO checkout and its own full visualization self-test:

```bash
python3 scripts/dircreative_visualization_adco_audit.py --adco-repo <adco-checkout>
```

The bilateral result is `PASS` only when ADCO accepts the projected provider spec and ADCO's own visualization self-test is green. A passing projection with a failing ADCO suite remains incompatible for release claims.

## Provider Descriptor

The descriptor declares:

- provider id and display name;
- `dircreative.film-preproduction` profile;
- supported protocol versions;
- film and workflow capabilities;
- `inline`, `codex_thread`, and `external_handoff` execution modes;
- `isolated_workspace`, `worktree`, and `read_only` workspace modes;
- false authority for client interaction, adoption, client readiness, final export, and nested dispatch.

ADCO calculates compatibility from the descriptor snapshot and requested capabilities. DIRcreative does not self-assert `compatible: true`. ADCO must not hard-code a DIR repository path, package version, `.dircreative/runs`, or internal validator.

## Handoff Acceptance

Enter `orchestrated_worker` only after the native bridge verifies:

- protocol, version, message type, profile, and descriptor hash;
- non-empty bounded objective and supported requested capabilities/output kinds;
- registered project-relative source artifacts whose current hashes match the handoff;
- execution and workspace modes advertised by the descriptor;
- a real handoff thread UUID only when `execution.mode: codex_thread`, bound to the same work/lane run in ADCO's ThreadOps registry and its dispatch receipt;
- `nested_dispatch_allowed: false`;
- project-relative read/write/receipt scopes with no traversal or protected overlap;
- an ADCO host-baseline reference with SHA-256 and manifest SHA-256 for later adoption proof;
- canonical forbidden control-plane, PPT-export, and FinalDelivery prefixes;
- internal-only visibility and provider-recommendation-only authority;
- the required `dircreative.domain-delivery@1.0` receipt extension negotiated from the descriptor;
- `generation_mode: prompt_only`, `authorized: false`, and no authorization reference. This v1 profile rejects every real-media handoff; real media needs a separately negotiated profile with structured authorization binding.

The native default is `inline`. Do not manufacture a Thread receipt for an inline or external handoff. A `read_only` handoff may grant the exact receipt path but no output root; otherwise reject it as `read_only_write_scope`. Its successful return path is a receipt-only `needs_user`/`blocked`/`failed` result followed by ADCO `defer` or `reject`, never a fabricated completed artifact.

## Receipt Contract

The provider receipt binds:

- protocol, contract version, exchange, handoff, work, provider, and profile identity;
- the negotiated descriptor SHA-256 and the exact handoff-file SHA-256;
- `outcome: completed | needs_user | blocked | failed`;
- every consumed input id, version, and SHA-256;
- every output provider id, requested kind, version, project-relative path, SHA-256, visibility, and source input ids;
- domain QA, limitations, structured questions, and specialist recommendation;
- execution mode, optional real thread id, nested-dispatch false, and zero out-of-scope writes;
- `claims.client_ready: false`;
- `claims.ppt_ready: false`;
- `claims.final_delivery_ready: false`;
- `claims.send_ready: false`;
- `claims.project_complete: false`;
- `claims.control_plane_updated: false`;
- the negotiated `dircreative.domain-delivery@1.0` extension whose payload matches the top-level domain detail.

DIRcreative may add `domain_delivery` with its detailed verdict and readiness model. It is a profile extension; the ADCO runtime must not depend on private DIR files or commands.

State mapping is fail-closed:

| DIR state | Native outcome | Provider recommendation | ADCO eligibility |
|---|---|---|---|
| `domain_accepted` | `completed` | adopt for ADCO gate | full adoption may be considered |
| `draft_accepted_with_limitations` | `completed` | partial internal adoption | partial adoption only, limitations retained |
| unresolved client choice | `needs_user` | return to ADCO | no gate advance |
| `needs_revision` | `failed` | reject/defer | not adoptable |
| `blocked` | `blocked` | defer | not adoptable |

An execution receipt must contain non-empty, physically distinct, non-symlinked, hash-matching output files inside exact write scope. Path aliases or one inode reused for multiple output kinds are rejected. A prompt-only or empty receipt cannot claim completed production.

## Adoption And Gate Closure

ADCO writes a separate adoption message. DIRcreative validates that it binds the provider receipt hash, keeps `decision_owner: adco`, maps only known provider outputs, preserves output hashes, does not target control-plane, PPT-export, or FinalDelivery paths, and closes the handoff host baseline with identical observed manifest hash and no changed paths. DIR independently re-reads the baseline and checks the post-adoption project after excluding only declared specialist paths and verified ADCO adoption writes.

The provider recommendation never becomes an adoption automatically:

- only `completed + qa pass` may be fully adopted;
- a limited draft may be partially adopted for internal review;
- `needs_user` cannot advance the gate;
- blocked, failed, simulated, stale-input, out-of-scope, or authority-escalating results must be rejected or deferred;
- an existing target is never overwritten.

After adoption, ADCO must run its current project validator and downstream creative/client/visual/authorization/PPT/package gates. Domain QA PASS is not client, PPT, FinalDelivery, send, or project-completion approval.

## Moving ADCO Boundary

ADCO is actively evolving. Compatibility is pinned to the neutral protocol version and descriptor capabilities, then verified by a cross-repository temp-project roundtrip. A DIR-only fixture is not bilateral evidence. If current ADCO tests, the native roundtrip, or either project validator fails, report compatibility as blocked and keep production on the last verified protocol version.

`scripts/dircreative_release_gate.py` is DIR-only unless called with `--adco-repo <checkout>`. Only the explicit bilateral scope may support a compatibility claim.
