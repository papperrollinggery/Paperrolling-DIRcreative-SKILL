# Delivery Audit Route Card

Contract owner: this file owns Delivery execution behavior.

Use only for generation authorization, formal assets and versions, client-visible
delivery, final prompt or asset handoff, or a validated Specialist Exchange
handoff.

## Budget

- Read exactly this one Route Card and the router's route-specific files.
- Full receipts, hashes, authorization, and strict audit are allowed here only.
- Persist the compact state snapshot.
- Keep one state owner. DIR owns standalone delivery state; ADCO owns host state
  during an orchestrated handoff.

## Execution

1. Re-read bound inputs and current versions before any completion claim.
2. Require internal `pre_generation_contract.status: pass` before media execution;
   this is validation evidence, not an extra external user gate.
3. Stop at `generation_authorization` before real generation and at
   `client_delivery_approval` before a client-visible handoff.
4. Run full domain QA and bind only real inputs and outputs in hashes.
5. For `adco_specialist_exchange`, load only the router-returned integration
   files, execute inline, forbid nested dispatch, and return domain outputs plus
   domain QA. Do not copy host Current Truth, Goal, versions, user confirmations,
   client readiness, or cleanup state.
6. Never claim client, send, project, or control-plane readiness for ADCO.

For standalone user-visible delivery, follow the routed
`docs/film-preproduction/professional-agent-voice-standard.md` humanizer check.

Legacy v1 records remain read-only inputs. New runtime state and exchange output
use their current v2 contracts.
