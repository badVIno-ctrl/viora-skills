# 12 - The review-and-fix loop and the findings ledger

For autonomous runs: "improve this until review passes", "fix everything the reviewer
finds", "clean up this module". Without structure, that request produces one of three
failures: an infinite loop, silent scope explosion, or a confident "all clean" that is
simply the loop giving up.

This file is the owner of bounded iteration.

---

## 1. The three inputs - never guessed

Collect all three before the first round. Missing one is a question, not an assumption.

| Input | Rule |
|---|---|
| **TARGET** | the exact path under improvement. Verify it exists. |
| **REVIEWER** | who judges: the DOUBT lenses, a sub-agent, an external CLI, or the repo's own gates. There is no default - if the user did not name one, ask, or state which you are using. |
| **SCOPE** | the glob list the loop may touch, e.g. `src/auth/**`. Not given → propose `<target>/**` and confirm. |

---

## 2. The loop

```
ROUND n:
  1 REVIEW  - reviewer reads the artifact + contract, emits findings
  2 LEDGER  - record every finding with an id, severity, and verdict
  3 FIX     - address blocking findings only (Critical, Required)
  4 GATES   - bash scripts/verify.sh .   (a fix that breaks a gate is not a fix)
  5 SCOPE   - git status: any file outside SCOPE -> HALT
  6 JUDGE   - clean review? converged. Budget spent? capped. Not converging? escalate.
```

**The loop may only end on a fresh review that found zero blocking issues.** Ending on "I
fixed the last batch" is ending on an unverified claim.

**Round budget:** T0 = 2 · T1 = 3 · T2 = 5. The budget is a real cap, not a target.

---

## 3. The four outcomes - report them honestly

| Outcome | Condition | What you must say |
|---|---|---|
| **CONVERGED** | last action was a review with 0 blocking findings | rounds used, remaining minor findings, evidence table |
| **CAPPED** | budget spent, final review still has blocking findings | "**CAPPED, NOT CONVERGED**" plus the open blocking list. Never dress this as success. |
| **ESCALATED** | the loop is not converging (see §4) | the pattern observed, the finding ids, and the design question that needs an answer |
| **HALTED** | a guard fired: scope violation, untracked new files, reviewer unavailable, gate broken by a fix | what fired, which paths, what you did not do |

A capped run reported as a success is the worst output this protocol can produce: it teaches
the user to trust a signal that is not there.

---

## 4. Non-convergence - detect it, do not out-grind it

Escalate immediately on any of these patterns:

- the **same finding id** returns after being marked fixed
- the blocking count is **not decreasing** across two rounds
- a fix **relocates** a problem: closed here, appeared there, same concept
- fixes are getting **larger** each round
- the same file is rewritten in three consecutive rounds

These mean the shape is wrong. More rounds cost tokens and produce churn. Escalate:

```
ESCALATION after round <n>
PATTERN: <which of the above>
FINDINGS: <ids>
ROOT QUESTION: <the one design decision that would end this>
OPTIONS: A <...>  B <...>
COST OF EACH: <one line each>
```

When the user rules, restart with the ruling recorded verbatim in the ledger. The ledger
carries over, so nothing is re-derived; only the round counter resets.

---

## 5. The scope guard - mechanical, every round

```bash
git status --porcelain           # every touched path
git status --porcelain | grep '^??'   # new untracked files
```

Every path must match SCOPE, and every new file must be intentional and named in the
ledger. One unexplained file → HALT and report it. This is the guard that keeps "improve
this module" from quietly becoming "rewrite this project".

**Also guard against improvement drift:** a finding that is not a defect under the contract
is out of scope even when the change would be nice. Record it as a follow-up.

---

## 6. The findings ledger

One file, `.viora/ledger.md`, that survives context resets and prevents re-litigating
settled questions.

```
| id | round | severity | where | finding | verdict | evidence |
|----|-------|----------|-------|---------|---------|----------|
| F1 | 1 | Critical | src/auth.ts:88 | token compared with == | FIXED | test/auth.test.ts:41 red->green |
| F2 | 1 | Nit | src/auth.ts:12 | name `d` | OPEN | - |
| F3 | 2 | Required | src/db.ts:210 | N+1 in list endpoint | REJECTED: intentional, see ADR-4 | benchmark 12ms |
```

**Severity** uses one vocabulary everywhere in this protocol:

| Label | Meaning |
|---|---|
| **Critical** | blocks: security, data loss, broken behaviour |
| **Required** | must fix before done |
| **Optional** | worth considering, author decides |
| **Nit** | style or taste, ignorable |
| **FYI** | context for later, no action |

**Verdicts:** `OPEN` · `FIXED` (+ the evidence that proves it) · `REJECTED` (+ the reason) ·
`DEFERRED` (+ where it was written down).

**A verdict is final.** A finding rejected with a reason does not come back in round 3 in
new words. That rule is what makes the loop terminate.

Deterministic helpers:

```bash
python3 scripts/viora.py ledger add --severity Critical --where src/auth.ts:88 --text "token compared with =="
python3 scripts/viora.py ledger resolve F1 --verdict FIXED --evidence "test/auth.test.ts:41 red->green"
python3 scripts/viora.py ledger list --open
```

---

## 7. Pin every behavioural fix

Every fix that changes behaviour gets a **pin**: a check that fails without the fix.

```
1 write the check
2 revert the fix  -> the check MUST fail
3 restore the fix -> the check MUST pass
4 record both results in the ledger evidence column
```

No pin, no `FIXED` verdict. This is what stops a loop from "fixing" the same defect three
times across three rounds.

---

## 8. Finishing a loop

Before the report:

- [ ] the last action was a **review**, not a fix
- [ ] every ledger row has a verdict
- [ ] every `FIXED` row names its pin
- [ ] gates are green on the final state, output pasted
- [ ] `git status` is inside SCOPE
- [ ] no narration residue in the code: no "improved", "refactored", "was:" comments, no leftover TODOs from the loop itself
- [ ] docs and comments that the change made false are updated

Then report with the ledger attached, and the outcome word from §3 stated first.

---

## 9. When not to loop

- **one-shot review requested** → do one DOUBT pass and report; the loop's value is iteration
- **a single known fix** → just make it under the normal ten steps
- **the target is undefined** → get a contract first; a loop over an unclear goal maximises churn
- **T0 with no reviewer available** → run the five DOUBT questions once, report, and hand off

---

## 10. The scope guard is now a command, not a habit

§5 describes checking scope mechanically every round. In v2.1 that check is a subcommand, so it
costs one line instead of discipline:

```bash
python3 scripts/viora.py plan --files src/a.ts,src/b.ts --lines 120 --frozen "public API of a.ts"
# ... one round of fixes ...
python3 scripts/viora.py scope
```

```
SCOPE FAIL - 2 problem(s):
  - 1 file(s) changed but not declared in the PLAN: src/utils/retry.ts
  - 214 changed line(s) over the T1 budget of 300  <- fine
```

Steps 6 and 7 refuse to close while scope has problems, which is precisely the moment a
review-and-fix loop starts drifting: round three finds something adjacent, fixes it "while I am in
here", and by round five the diff is unreviewable.

### How this changes the loop

| Round event | Old behaviour | Now |
|---|---|---|
| a fix touches a new file | noticed if the agent remembered to run `git status` | `scope` fails; step will not close |
| the diff crosses the tier budget | judged by feel | counted from `git diff --numstat` |
| a finding is out of scope | "I will just do it" | record it in the ledger as `DEFERRED`, or widen the plan on purpose with `--force` |
| a hypothesis fails | revert by hand, imperfectly | `checkpoint` before the round, `rollback --yes` after |

### Widening is a decision, and decisions are recorded

Sometimes the loop genuinely needs a fourth file - a shared constant, a type, a barrel export.
That is allowed:

```bash
python3 scripts/viora.py plan --files src/a.ts,src/b.ts,src/types.ts --lines 120 --force
python3 scripts/viora.py ledger add --severity Optional --where src/types.ts:1 \
  --text "plan widened to include src/types.ts: the fix for F3 needs the shared type"
```

Two lines, and the diff stays explicable to whoever reads it next week. Compare that with the
alternative - a silent fourth file - which is indistinguishable from scope creep because it *is*
scope creep.

### Checkpoints per round

For loops of three or more rounds, checkpoint at the start of each round:

```bash
python3 scripts/viora.py checkpoint --label "round 3 start"
python3 scripts/viora.py checkpoint --list      # via rollback --list
```

The payoff comes at the non-convergence check in §4. Detecting non-convergence is only useful if
you can *return* to the last good state; otherwise "stop" means "hand over a half-built round".
With checkpoints, `HALTED` becomes a clean state rather than a mess with a label.

### The loop's exit condition, restated mechanically

A loop may report `CONVERGED` only when all of the following are true:

```bash
python3 scripts/viora.py scope     # SCOPE OK
python3 scripts/viora.py gate      # every gate PASS, recorded
python3 scripts/viora.py check     # READY: no missing steps, no STALE rows, no open Critical
```

All three, in that order, in the same turn as the report. Any one of them failing means the honest
outcome is `CAPPED, NOT CONVERGED` - which is a normal result, not a defeat.
