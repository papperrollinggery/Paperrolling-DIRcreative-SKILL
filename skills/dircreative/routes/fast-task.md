# Fast Task Route Card

Contract owner: this file owns Fast execution behavior.

Use for a bounded copy, shot, storyboard, prompt, or existing-artifact revision.

## Budget

- One controlling agent.
- Zero Threads and zero Director Room sessions.
- Read the user's input plus no more than three files returned by the router.
- Do not load ADCO, Thread, Goal, Delivery, or full-project validation contracts.
- At most one external user gate, and only for a real blocker.
- Do not run full-project validation or write a full receipt.
- Read exactly this one Route Card.

## Execution

1. Preserve facts and decisions outside the requested edit scope.
2. Load only `required_files` returned by the router; load an `optional_file` only
   when its need is visible in the input.
3. Apply the smallest useful professional change.
4. Return the revised result first, followed by assumptions or one blocking
   question only when necessary.

Before user-visible creative output, follow the routed
`docs/film-preproduction/professional-agent-voice-standard.md` humanizer check.

Fast never backtracks a local edit to idea intake. It does not demand staged
confirmation and does not persist state unless the user explicitly asks for a
file update.

## Fast Receipt

When a file write needs a receipt, use only:

```yaml
status:
route:
input_refs:
output_refs:
assumptions:
open_questions:
```

No file write means no receipt is required.
