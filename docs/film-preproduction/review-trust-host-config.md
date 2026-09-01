# Review Trust Host Configuration

Reviewer trust is host state, not installed Skill state. The packaged
`skills/dircreative/runtime/review-trust-registry.json` is an empty template and
is never the default mutable registry.

Resolution order:

1. `--review-trust-registry /absolute/path/review-trust-registry.json`;
2. `DIRCREATIVE_REVIEW_TRUST_REGISTRY`;
3. `~/.codex/dircreative/review-trust-registry.json`.

Read-only status:

```bash
python3 scripts/dircreative_review_trust.py status
```

A missing or invalid registry returns `TOOL_BLOCKED` and prints the exact path.
Handoff and ledger validation accept the same explicit flag.

Provision only an existing public key. Dry-run is the default:

```bash
python3 scripts/dircreative_review_trust.py provision-public-key \
  --authority-id PROMPT-REVIEW-001 \
  --actor-id prompt-reviewer \
  --public-key /detached/reviewer-public.pem \
  --allowed-purpose prompt_authority_review \
  --allowed-source independent_review
```

Add `--apply` only after inspecting the emitted entry and destinations. Apply
copies the public key and atomically replaces the host registry; it never
generates a reviewer private key. OpenSSL first inspects the supplied file using
public-key-only parsing, canonical public output, and an external byte comparison;
Python reads bytes only after those checks succeed. OpenSSL necessarily opens the
candidate file to perform that validation. A private-key input is rejected and is
never imported, copied, or saved by DIRcreative. Existing authority IDs and key destinations are
not overwritten. Because host state lives outside the installed package, atomic
Skill installation cannot replace it.
