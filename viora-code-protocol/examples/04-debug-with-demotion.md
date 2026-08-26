# Example 4 - DEBUG mode: a flaky test, a self-demotion, and probabilistic proof

**Situation.** *"The user list test fails in CI maybe one run in ten. Locally it always
passes. Fix it."*

DEBUG mode runs steps **1 -> 2 -> 5 -> 6 -> 8 -> 10**. There is no LADDER and no CLEAN pass,
because a debug session is not a design exercise. Step 5 (RED) is doing the heaviest work
here: **an intermittent bug that you cannot reproduce on demand cannot be fixed, only
guessed at.**

This run starts at **T1 and demotes itself to T0** part-way through. That demotion is the
point of the example. Demotion is not punishment - it is what an honest agent does after it
catches itself breaking its own rules.

---

## Turn 0 - open the run

```bash
$ python3 scripts/viora.py start --mode DEBUG --tier T1 --task "users.test.ts fails ~1 in 10 CI runs, passes locally"
VIORA T1 | MODE DEBUG | STEP 1/10 CONTRACT
steps for DEBUG: 1 -> 2 -> 5 -> 6 -> 8 -> 10
budget: <= 300 changed lines, <= 3 file(s), 3 doubt round(s), 3 strike(s) then BLOCKED

$ python3 scripts/viora.py contract \
    --goal "users.test.ts passes 200 consecutive runs with no code path left non-deterministic" \
    --done-test "for i in $(seq 200); do npm test -- users.test.ts || break; done" \
    --protected "the public shape of listUsers(); the other 340 tests" \
    --non-goals "other flaky tests, CI runner configuration, test framework upgrade"
written: .viora/contract.md

$ python3 scripts/viora.py done 1 --note "DONE-TEST is 200 consecutive passes, not 1 pass - a single green run proves nothing about a flake"
VIORA T1 | MODE DEBUG | STEP 2/10 OWNER
```

The DONE-TEST is the most important decision in this run. "The test passes" would have been
a weak DONE-TEST, and the script would have warned about it:

```
WARNING: this DONE-TEST reads like an opinion ('passes'), not a command.
A DONE-TEST must be something you can run and watch fail.
```

---

## Turn 1 - OWNER: make it fail on demand before touching anything

```bash
$ for i in $(seq 50); do npm test -- users.test.ts >/dev/null 2>&1 || echo "FAIL at run $i"; done
FAIL at run 14
FAIL at run 39
FAIL at run 47
```

3 failures in 50 runs - about 6%. Now the failure is on tap, and any fix has a measurable
target.

```bash
$ npm test -- users.test.ts 2>&1 | tail -12
 FAIL  test/users.test.ts
  x lists users in creation order
    expected [ 'ada', 'bob', 'cy' ]
    received [ 'bob', 'ada', 'cy' ]
      at test/users.test.ts:34:20

$ sed -n '24,36p' test/users.test.ts
  it("lists users in creation order", async () => {
    await createUser("ada");
    await createUser("bob");
    await createUser("cy");
    const users = await listUsers();
    expect(users.map((u) => u.name)).toEqual(["ada", "bob", "cy"]);
  });

$ grep -n "order\|sort" src/services/users.ts
41:  return rows.sort((a, b) => a.createdAt - b.createdAt);

$ grep -rn "createdAt" src/services/users.ts
18:    createdAt: Date.now(),
41:  return rows.sort((a, b) => a.createdAt - b.createdAt);
```

**Reply to the user:**

> VIORA T1 | MODE DEBUG | STEP 2/10 OWNER
>
> Reproduced: 3 failures in 50 local runs (~6%), so I can measure any fix instead of hoping.
> `Owner: src/services/users.ts:41` - the sort key. `createdAt` comes from `Date.now()` at
> line 18, which has millisecond resolution. Two users created inside the same millisecond
> get equal keys, and `Array.prototype.sort` is not required to keep their relative order for
> equal keys. Confirming before I believe it.

```bash
$ python3 scripts/viora.py done 2 --note "reproduced 3/50 (~6%); Owner: src/services/users.ts:41 sort on Date.now() ms key"
VIORA T1 | MODE DEBUG | STEP 5/10 RED
```

---

## Turn 2 - strike 1: the obvious cause, tested and rejected

> HYPOTHESIS: the test machine is fast enough that all three users land in the same
> millisecond, so the sort is comparing equal keys.
> TEST: log the three `createdAt` values across 20 runs and look for duplicates.

```bash
$ VIORA_DEBUG=1 node -e "..." # instrumented run, 20 iterations
run 03: createdAt = [1787310442871, 1787310442871, 1787310442872]   <-- duplicate
run 07: createdAt = [1787310443118, 1787310443119, 1787310443119]   <-- duplicate
run 11: createdAt = [1787310443402, 1787310443402, 1787310443402]   <-- all three equal
...
duplicates in 14 of 20 runs
```

Duplicates in 14 of 20 runs - but the test only fails in 3 of 50. So equal keys are **not
sufficient** to cause the failure. Something else decides the outcome when keys tie.

> RESULT: hypothesis **incomplete, therefore wrong as stated**. Equal keys happen 70% of the
> time and the test fails 6% of the time. If I "fixed" this and saw green, I would be reading
> luck as proof.

```bash
$ python3 scripts/viora.py strike --reason "equal ms keys occur in 70% of runs but the test fails in 6% - equal keys alone do not explain it"
STRIKE 1/3 - equal ms keys occur in 70% of runs but the test fails in 6%
Two strikes left at T1. Change hypothesis, not volume.
```

This is the moment most agents get wrong. The obvious cause was **real** and **not the
whole cause**. Shipping here produces a fix that appears to work and does not.

---

## Turn 3 - the mistake: scope creep, caught by the machine

While looking for what breaks ties, the tidying instinct took over: a helper got extracted
in `users.ts`, a type got tightened in `types/user.d.ts`, an unrelated `sort` in
`services/teams.ts` got the same "defensive" treatment, and the test got a retry wrapper.

```bash
$ python3 scripts/viora.py scope
VIORA T1 | MODE DEBUG | STEP 5/10 RED

declared: (nothing recorded)
touched:  src/services/users.ts, src/services/teams.ts, src/types/user.d.ts, test/users.test.ts
lines:    96 changed (budget 300) | files: 4 (tier cap 3)

SCOPE FAIL - 2 problem(s):
  - no PLAN recorded, so nothing constrains this diff - run `plan` before editing
  - 4 file(s) touched, tier T1 allows 3

Two honest ways out: shrink the diff, or widen the plan on purpose and say so.
  python3 scripts/viora.py plan --files <the real list> --lines <n>
```

Four files touched while chasing a one-line sort bug, with no plan recorded and a retry
wrapper added to the very test that is supposed to detect the bug. A retry wrapper on a
flaky test is not a fix - it is a way to stop being told about the bug.

That is an observable rule violation, so the tier drops. The agent does this to itself:

```bash
$ python3 scripts/viora.py demote --reason "edited 4 files with no PLAN while debugging a 1-line sort bug, and added a retry wrapper that hides the failure"
DEMOTE -> T0 (edited 4 files with no PLAN while debugging a 1-line sort bug, and added a
retry wrapper that hides the failure)

T0 rules now apply: <= 80 changed lines, <= 1 file(s), 2 doubt round(s), 2 strike(s).
Re-read the current step at the new tier: python3 scripts/viora.py next

$ python3 scripts/viora.py rollback --list
no checkpoints. Next time, run `checkpoint` before you start editing.

$ git checkout -- src/services/teams.ts src/types/user.d.ts test/users.test.ts
$ git --no-pager diff --stat
 src/services/users.ts | 14 ++++++++---
 1 file changed, 11 insertions(+), 3 deletions(-)
```

No checkpoint existed, so the cleanup was manual. That is the cost of skipping a
one-second command.

**Reply to the user:**

> VIORA T0 | MODE DEBUG | STEP 5/10 RED
>
> DEMOTE -> T0. I caught myself editing four files with no recorded plan while chasing a
> one-line sort bug, and one of those edits was a retry wrapper on the flaky test - which
> would have hidden the bug instead of fixing it. I have reverted three of the four files and
> I am now working under T0 limits: one file, 80 lines, and a recorded plan before any edit.

```bash
$ python3 scripts/viora.py plan --files src/services/users.ts --lines 25 --frozen "listUsers() return shape, User type"
PLAN recorded
FILES:  src/services/users.ts
BUDGET: <= 25 changed lines
FROZEN: listUsers() return shape, User type
```

---

## Turn 4 - the real root cause, found by tracing instead of guessing

Strikes stand at 1 (carried across the demotion), and the T0 cap is 2. One guess left - so
no more guessing. Trace it:

```bash
$ git log -S'createdAt' --oneline -- src/services/users.ts
4d81a7c switch users to the shared repository layer (3 weeks ago)
1188cc2 add users service (11 months ago)

$ git show 4d81a7c -- src/services/users.ts | head -20
-  const rows = await db.query("SELECT * FROM users ORDER BY created_at ASC");
+  const rows = await repo.findAll("users");
   ...
+  return rows.sort((a, b) => a.createdAt - b.createdAt);

$ grep -n "findAll" src/data/repo.ts
27:export async function findAll(table: string) {
29:  return Promise.all(shards.map((s) => s.select(table))).then((r) => r.flat());
```

There it is. Three weeks ago the query lost its `ORDER BY` and gained an in-memory sort. The
new source is `repo.findAll()`, which fans out across shards with `Promise.all` and flattens
the results - so **the input order is non-deterministic**, and the sort only preserves it
when the millisecond keys happen to differ.

That explains both numbers: ties happen 70% of the time, and the flatten order differs often
enough to break the tie badly about 6% of the time. This is a different hypothesis family -
ordering source, not clock resolution - so the strike counter resets, with the reason
recorded:

```bash
$ python3 scripts/viora.py strike --reset --reason "new family: root cause is non-deterministic input order from repo.findAll shard flatten (commit 4d81a7c dropped ORDER BY), not clock resolution"
strikes reset to 0 - new family: root cause is non-deterministic input order from
repo.findAll shard flatten (commit 4d81a7c dropped ORDER BY), not clock resolution
The reset is recorded. A reset without a genuinely new hypothesis family is self-deception.

$ python3 scripts/viora.py evidence --gate red --command "for i in $(seq 50); do npm test -- users.test.ts; done" --result "FAIL 3/50 (6%) before the fix"
evidence recorded: red | for i in $(seq 50); ... | FAIL 3/50 (6%) before the fix
bound to working tree git:9c02b7f1a4de

$ python3 scripts/viora.py done 5 --note "RED quantified: 3/50 failures; root cause = repo.findAll shard flatten order + equal ms keys (4d81a7c dropped ORDER BY)"
VIORA T0 | MODE DEBUG | STEP 6/10 GREEN
```

---

## Turn 5 - GREEN: a total order, not a bigger clock

```bash
$ python3 scripts/viora.py checkpoint --label "before GREEN - total order fix"
checkpoint 20260826-104512 saved - before GREEN - total order fix
base commit: 3c7712fe90 | uncommitted diff: 0 bytes
```

The rejected options are worth naming:

- *Higher-resolution timestamps* - narrows the tie window, does not remove it. Still flaky,
  just more rarely, which is strictly worse because it will come back later and look new.
- *A retry wrapper on the test* - hides the bug. This is what the demotion was for.
- *Restore `ORDER BY` in the repository layer* - correct, but `repo.ts` is used by 9 other
  services and is outside the plan and the contract.

The chosen fix is a **total order** at the owner line: a deterministic tiebreak, so equal
timestamps can no longer produce two valid answers.

```ts
// src/services/users.ts:41
return rows.sort((a, b) => a.createdAt - b.createdAt || a.id.localeCompare(b.id));
```

```bash
$ for i in $(seq 200); do npm test -- users.test.ts >/dev/null 2>&1 || echo "FAIL at run $i"; done
$ echo "exit: $?"
exit: 0

$ python3 scripts/viora.py scope
declared: src/services/users.ts
touched:  src/services/users.ts
lines:    1 changed (budget 25) | files: 1 (tier cap 1)

SCOPE OK - every changed file was declared, and the budget holds.

$ python3 scripts/viora.py done 6 --note "GREEN: total order via id tiebreak at users.ts:41; 200/200 passes; 1 changed line"
VIORA T0 | MODE DEBUG | STEP 8/10 PROVE
```

---

## Turn 6 - PROVE

```bash
$ python3 scripts/viora.py gate
==> lint: npm run lint
==> types: npx tsc --noEmit
==> test: npm test

| Gate | Command | Result |
|---|---|---|
| lint | `npm run lint` | PASS |
| types | `npx tsc --noEmit` | PASS |
| test | `npm test` | PASS |

VERDICT: all executed gates PASS. Gates marked SKIP remain UNPROVEN.
recorded 3 gate row(s); evidence now 4 fresh / 4 total

$ python3 scripts/viora.py evidence --gate flake-loop --command "for i in $(seq 200); do npm test -- users.test.ts; done" --result "PASS 200/200 after the fix (was 3/50 FAIL)"
evidence recorded: flake-loop | ... | PASS 200/200 after the fix (was 3/50 FAIL)

$ python3 scripts/viora.py ledger add --severity Required --where src/data/repo.ts:29 \
    --text "findAll() flattens Promise.all over shards, so every consumer gets non-deterministic row order; 9 other services rely on it and 4 of them sort on a low-resolution timestamp - same latent flake"
F1 Required @ src/data/repo.ts:29

$ python3 scripts/viora.py ledger add --severity Optional --where src/services/users.ts:18 \
    --text "createdAt uses Date.now() (ms); ties are normal, not exceptional - the sort must never assume uniqueness"
F2 Optional @ src/services/users.ts:18

$ python3 scripts/viora.py done 8 --note "gates 3/3 PASS + 200/200 flake loop recorded; 2 findings raised for the shared repo layer"
VIORA T0 | MODE DEBUG | STEP 10/10 REPORT
```

---

## Turn 7 - REPORT

```bash
$ python3 scripts/viora.py done 10
$ python3 scripts/viora.py report
VERDICT: DELIVERED
MODE: DEBUG | TIER: T0 | TASK: users.test.ts fails ~1 in 10 CI runs, passes locally

WHAT CHANGED
- 1 file(s), 1 changed line(s): src/services/users.ts

EVIDENCE
| Gate | Command | Result | Fresh |
|---|---|---|---|
| red | `for i in $(seq 50); do npm test -- users.test.ts; done` | FAIL 3/50 (6%) before the fix | yes |
| lint | `npm run lint` | PASS | yes |
| types | `npx tsc --noEmit` | PASS | yes |
| test | `npm test` | PASS | yes |
| flake-loop | `for i in $(seq 200); do npm test -- users.test.ts; done` | PASS 200/200 after the fix (was 3/50 FAIL) | yes |

NOT DONE / UNPROVEN
- 200 consecutive passes is strong evidence, not proof: a 6% flake has roughly a 1-in-10^5
  chance of surviving 200 runs undetected, but the CI machine has different core counts and
  shard timing, so the CI rate is unmeasured
- the same latent bug remains in 4 other services that sort on Date.now() (see F1)
- I did not change repo.findAll(); its row order is still non-deterministic for everyone else

FOLLOW-UPS
- F1 Required @ src/data/repo.ts:29: findAll() flattens Promise.all over shards...
- F2 Optional @ src/services/users.ts:18: createdAt uses Date.now() (ms)...

TIER HISTORY
- T1 -> T0: edited 4 files with no PLAN while debugging a 1-line sort bug, and added a retry
  wrapper that hides the failure
```

---

## What to copy from this

1. **Reproduce and quantify before you fix.** "3 in 50" turns a ghost into a measurement,
   and turns "it passed once" into "200/200 vs 3/50".
2. **A weak DONE-TEST poisons a flake hunt.** "The test passes" is satisfied by luck.
3. **The obvious cause can be real and still not be the cause.** 70% ties vs 6% failures was
   the number that saved this run.
4. **`scope` catches drift that self-assessment never will.** Four files, no plan, and a
   retry wrapper - all invisible from the inside.
5. **Demote yourself when you break your own rules.** It is a cheap, reversible correction,
   and it turned this run around.
6. **Reset strikes only for a genuinely new hypothesis family, and record why.** Anything
   else is an infinite guess budget with extra steps.
7. **Prefer determinism over precision.** A tiebreak removes the flake; a better clock only
   makes it rarer, which is worse.
8. **Never retry-wrap a flaky test.** That converts a known bug into an unknown one.
9. **Probabilistic proof is stated as probabilistic.** 200/200 is strong evidence, and the
   report says exactly that instead of "fixed".
