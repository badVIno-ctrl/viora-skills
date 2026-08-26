# LEDGER template

The findings ledger for review-and-fix loops. Lives at `.viora/ledger.md` and survives context
resets, so a settled question is never re-litigated in round 3.

```
| id | round | severity | where | finding | verdict | evidence |
|----|-------|----------|-------|---------|---------|----------|
| F1 | 1 | Critical | src/auth.ts:88 | token compared with == | FIXED | test/auth.test.ts:41 red->green |
| F2 | 1 | Nit | src/auth.ts:12 | variable named `d` | OPEN | - |
| F3 | 2 | Required | src/db.ts:210 | N+1 on the list endpoint | REJECTED: intentional, ADR-4 | benchmark 12ms |
| F4 | 2 | Optional | src/ui/List.tsx:60 | could memoise the row | DEFERRED: follow-ups | - |
```

Maintain it with the conductor rather than by hand:

```bash
python3 scripts/viora.py ledger add --severity Critical --where src/auth.ts:88 --text "token compared with =="
python3 scripts/viora.py ledger resolve F1 --verdict FIXED --evidence "test/auth.test.ts:41 red->green"
python3 scripts/viora.py ledger list --open
```

---

## Severity

| Label | Meaning |
|---|---|
| **Critical** | security, data loss, broken behaviour - blocks everything |
| **Required** | a real defect under the contract - must fix before done |
| **Optional** | worth considering; author decides and says what they decided |
| **Nit** | style or taste; safely ignorable |
| **FYI** | context for later; no action |

## Verdicts

| Verdict | Requires |
|---|---|
| `OPEN` | nothing - it is waiting |
| `FIXED` | the pin: a check that fails without the fix, named in the evidence column |
| `REJECTED` | a reason, in the verdict cell |
| `DEFERRED` | where it was written down (report follow-ups, issue tracker) |

**A verdict is final.** A finding rejected with a reason does not return in a later round wearing
new words. That rule is what makes the loop terminate.

**No pin, no FIXED.** A behavioural fix without a check that fails when reverted is an unproven
claim, and the loop will "fix" it again next round.

---

## Loop closing block

```
LOOP OUTCOME: CONVERGED | CAPPED | ESCALATED | HALTED
ROUNDS USED: <n> of <budget>
LAST ACTION: review (never a fix)
BLOCKING OPEN: <none | list of ids>
SCOPE: <globs>, git status clean inside scope: yes/no
```

`CAPPED` is written as **"CAPPED, NOT CONVERGED"** with the open blocking list. A capped run
reported as a success is the worst output this protocol can produce.

## Escalation block

```
ESCALATION after round <n>
PATTERN:  <same finding returned | count not decreasing | problem relocated | fixes growing>
FINDINGS: <ids>
ROOT QUESTION: <the one design decision that ends this>
OPTIONS:  A <...>   B <...>
COST:     A <one line>   B <one line>
```
