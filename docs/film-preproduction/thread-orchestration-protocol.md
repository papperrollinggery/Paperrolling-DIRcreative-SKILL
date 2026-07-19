# Thread Orchestration Protocol

Verified: 2026-07-19

Status: legacy v1 evidence reader and explicit Delivery-only reference. This file
does not own active v2 routing. The canonical mode and thread budgets are in
`skills/dircreative/runtime/routing-policy.yaml`.

## Active v2 Boundary

- Fast uses zero Threads and zero Director Room sessions.
- Studio uses one controller and zero Threads by default. Adaptive professional
  perspectives are judgments, not worker seats.
- Delivery may use only the execution mode explicitly permitted by its selected
  route. No current route implicitly creates a Thread.
- Repository source maintenance is outside DIRcreative runtime and never starts
  Threads because creative vocabulary appears in a maintenance request.
- A worker never creates a nested controller or nested dispatch.

Thread state never replaces an artifact, compact state, receipt, authorization,
or user decision. A thread ID alone proves none of those things.

## Specialist Exchange

`adco.specialist-exchange@2.0` is `inline` only and rejects nested dispatch. A v2
handoff or receipt contains no thread field.

Existing v1 handoffs remain readable. A v1 `codex_thread` record is valid only
when its work id, lane id, lane-run id, execution-worker class, isolated
workspace, active ThreadOps registry row, dispatch receipt, and real UUID all
bind the same thread. `inline` and `external_handoff` must not claim one.

In every exchange version, ADCO owns dispatch, adoption, cleanup, Current Truth,
versions, client visibility, readiness, and completion. DIRcreative never starts
a second worker from an assigned provider task.

## Legacy V1 Evidence Shape

The validator may read existing records containing:

- `thread_id`, `source_thread_id`, `lane_id`, and `lane_run_id`;
- thread class and isolated worktree/workspace metadata;
- dispatch, adoption, archive, and cleanup receipts;
- terminal reasons and visibility snapshots;
- first-level worker and bounded second-level subagent evidence.

These fields remain evidence only. They do not authorize a new v2 dispatch and
must not be copied into compact v2 state or Specialist Exchange v2.

The frozen v1 readers use `thread-dispatch-record.yaml` and
`thread-dispatch-record.template.yaml`; both are compatibility schemas, not
active v2 routing instructions.

Historical v1 rule: Second-level subagents are local tools inside a first-level Codex Thread worker.
Their recorded `second_level_subagents` evidence remains
read-only, must resolve `TOOL_BLOCKED` honestly, and can never become durable
truth, authorization, adoption, or completion state.

## Read-Only Integrity Rules

For a legacy record to support a historical claim:

1. all referenced files exist and their hashes match;
2. the thread UUID is syntactically valid and matches the bound dispatch proof;
3. work, lane, workspace, and receipt identities agree;
4. any adoption decision belongs to the outer controller;
5. nested dispatch is false unless the historical contract explicitly recorded
   bounded, read-only subagent assistance;
6. a local snapshot is not treated as trusted live host attestation;
7. missing, stale, or ambiguous evidence fails closed.

Legacy terminal reasons use the frozen vocabulary `completed`, `adopted`,
`rejected`, `failed`, `system_error`, `interrupted`, `duplicate`, `superseded`,
or `abandoned`. New v2 routes do not create these records by default.

## Compatibility Commands

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_thread_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_director_harness_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/dircreative_adco_native_exchange.py --self-test
```

Passing fixtures proves that legacy records remain readable. It is not evidence
that a real Thread ran, remains visible, was archived, or is safe to reuse.
