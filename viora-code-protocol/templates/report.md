# Final report template (the only format you deliver in)

```
VERDICT: DELIVERED | NO_CHANGE | BLOCKED
Mode/Lane:

WHAT CHANGED
- path:line - why it changed (one line per file; no file without a reason)

HOW IT WAS SOLVED
- ladder rung + the owner that was extended, or why new code was unavoidable
- searches that proved nothing existed yet (for new code)

EVIDENCE
| Gate  | Command | Result |
|-------|---------|--------|
| lint  |         |        |
| types |         |        |
| test  |         |        |
| build |         |        |
| ui    |         |        |
| perf  |         | before -> after, same command |

DELETED / REPLACED
- what was removed so nothing exists twice

NOT DONE / UNPROVEN
- gate or behavior + the exact reason it could not be verified here
- what a human should click or run to confirm

RISKS
- what could break, and where to look first if it does

FOLLOW-UPS
- concrete, small, with paths (duplicates found but out of scope, missing tests, etc.)
```

Rules: no praise, no filler, no restating the request, no invented numbers. If you did not run it, it is `UNPROVEN`. `NO_CHANGE` (the behavior already existed) and `BLOCKED` (a decision is needed) are valid, respected outcomes - a guess is not.
