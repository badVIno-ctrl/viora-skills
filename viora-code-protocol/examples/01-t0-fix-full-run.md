# Example 1 - a complete T0 FIX run, start to report

**Read this if you are a fast or small model.** This is not a description of the protocol.
It is a transcript of one correct run. Copy the shape of it: one step per turn, a header
line on every reply, a command before every claim.

The run below includes one **deliberate mistake** (an edit made after the gates passed) so
you can see how the tooling catches it. That part is not a flaw in the example - it is the
most important thing in it.

**Situation.** Small Express + TypeScript API. The user reports: *"POST /login returns 500
when the request body is empty. It should be a 400."*

---

## Turn 0 - check the ground, pin the tier, open the run

```bash
$ python3 scripts/viora.py doctor
VioraCode doctor - v2.1
root: /work/api

  OK    python 3.11.8
  OK    script present: verify.sh
  OK    script present: scan_repo.py
  OK    script present: find_duplicates.py
  OK    script present: ui_guard.py
  OK    git repository detected - scope, budget and rollback all work
  OK    state directory is writable: .viora
  OK    4 gate(s) detected
  OK    no run in progress
  WARN  no tier pinned; T1 is assumed. If you are a fast/small model, run: tier --set T0

gates this repo declares:
  lint: npm run lint
  types: npx tsc --noEmit
  test: npm test
  build: npm run build

Usable. Read each WARN line - every one of them is a way your report could mislead.

$ python3 scripts/viora.py tier --set T0
tier pinned: T0  (.viora/tier)
budget: <= 80 changed lines, <= 1 file(s), 2 doubt round(s), 2 strike(s)

$ python3 scripts/viora.py start --mode FIX --task "POST /login returns 500 on empty body, should be 400"
VIORA T0 | MODE FIX | STEP 1/10 CONTRACT
task: POST /login returns 500 on empty body, should be 400
steps for FIX: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10
budget: <= 80 changed lines, <= 1 file(s), 2 doubt round(s), 2 strike(s) then BLOCKED
```

**Reply to the user:**

> VIORA T0 | MODE FIX | STEP 1/10 CONTRACT
>
> Tier pinned to T0. Four gates exist in this repo, so this change can be proven.
> Writing the contract next.

---

## Turn 1 - CONTRACT

```bash
$ python3 scripts/viora.py contract \
    --goal "POST /login with an empty or non-object body returns 400 with a JSON error" \
    --done-test "npm test -- login.test.ts" \
    --protected "the existing 200 path for a valid body; the shape of LoginResponse" \
    --non-goals "signup, session expiry, rate limiting, any other endpoint"
GOAL:      POST /login with an empty or non-object body returns 400 with a JSON error
DONE-TEST: npm test -- login.test.ts
PROTECTED: the existing 200 path for a valid body; the shape of LoginResponse
NON-GOALS: signup, session expiry, rate limiting, any other endpoint

written: .viora/contract.md

$ python3 scripts/viora.py done 1 --note "contract written; DONE-TEST=npm test -- login.test.ts"
VIORA T0 | MODE FIX | STEP 2/10 OWNER
step 1 CONTRACT: done
next: step 2 OWNER   (python3 scripts/viora.py next)
```

Note what did **not** happen: no code was read, no fix was proposed. At T0 the contract is
the whole turn.

---

## Turn 2 - OWNER

```bash
$ grep -rn "login" src --include="*.ts" -l
src/routes/login.ts
src/services/auth.ts
src/validation/body.ts

$ grep -n "req.body" src/routes/login.ts
14:  const { email, password } = req.body;

$ sed -n '10,22p' src/routes/login.ts
router.post("/login", async (req, res) => {
  const { email, password } = req.body;
  const user = await auth.authenticate(email, password);
  return res.json({ token: user.token, userId: user.id });
});

$ grep -n "export" src/validation/body.ts
3:export function requireObjectBody(body: unknown): Record<string, unknown> {
```

**Reply to the user:**

> VIORA T0 | MODE FIX | STEP 2/10 OWNER
>
> `Owner: src/routes/login.ts:14` - this is the line that destructures the body and throws.
> There is already a validation helper: `src/validation/body.ts:3 requireObjectBody()`.
> So this is a reuse job, not new code.

```bash
$ python3 scripts/viora.py done 2 --note "Owner: src/routes/login.ts:14; existing helper validation/body.ts:3 requireObjectBody"
VIORA T0 | MODE FIX | STEP 3/10 LADDER
step 2 OWNER: done
```

Finding that helper is the entire value of step 2. A model that skipped it would have
written a second validator, and the repo would now have two.

---

## Turn 3 - LADDER

**Reply to the user:**

> VIORA T0 | MODE FIX | STEP 3/10 LADDER
>
> Rung 2 (reuse local). Rung 1 fails: there is no config flag or existing middleware that
> validates this route's body. Rung 6 (new code) is unnecessary because
> `requireObjectBody()` already exists and already throws a typed error.

```bash
$ python3 scripts/viora.py done 3 --note "rung 2 reuse requireObjectBody; rung 1 fails - no flag or middleware exists"
VIORA T0 | MODE FIX | STEP 4/10 PLAN
step 3 LADDER: done
```

---

## Turn 4 - PLAN (recorded, not described)

```bash
$ python3 scripts/viora.py plan \
    --files src/routes/login.ts,test/login.test.ts \
    --lines 40 \
    --frozen "LoginResponse, the 200 body shape"
viora: 2 files declared, tier T0 allows 1.
  Split the task, or say why this is one atomic change and pass --force.
```

The budget pushed back, and it is right to. A test file plus a source file is the normal
shape of a FIX, so this is the legitimate use of `--force` - and it gets recorded.

```bash
$ python3 scripts/viora.py plan \
    --files src/routes/login.ts,test/login.test.ts \
    --lines 40 \
    --frozen "LoginResponse, the 200 body shape" --force
PLAN recorded
FILES:  src/routes/login.ts, test/login.test.ts
BUDGET: <= 40 changed lines
FROZEN: LoginResponse, the 200 body shape

From now on `scope` fails on any file outside this list. Check it before you claim GREEN.

$ python3 scripts/viora.py done 4 --note "FILE: src/routes/login.ts + test/login.test.ts; <=40 lines; FROZEN LoginResponse"
VIORA T0 | MODE FIX | STEP 5/10 RED
step 4 PLAN: done
```

---

## Turn 5 - RED (watch it fail first)

Added to `test/login.test.ts`:

```ts
it("returns 400 when the body is empty", async () => {
  const res = await request(app).post("/login").send();
  expect(res.status).toBe(400);
});
```

```bash
$ npm test -- login.test.ts
 FAIL  test/login.test.ts
  x returns 400 when the body is empty (18 ms)
    TypeError: Cannot destructure property 'email' of 'req.body' as it is undefined.
      at src/routes/login.ts:14:11

Tests: 1 failed, 4 passed, 5 total

$ python3 scripts/viora.py evidence --gate red --command "npm test -- login.test.ts" --result "FAIL as expected: TypeError at login.ts:14"
evidence recorded: red | npm test -- login.test.ts | FAIL as expected: TypeError at login.ts:14
bound to working tree git:4f1c9ab02e77
rows: 1 total, 1 fresh (.viora/evidence.jsonl)

$ python3 scripts/viora.py done 5 --note "RED: test/login.test.ts new case fails with TypeError at login.ts:14"
VIORA T0 | MODE FIX | STEP 6/10 GREEN
step 5 RED: done
```

It fails **because the behaviour is missing**, at the line step 2 identified. That match
between the failure location and the owner line is what makes RED trustworthy.

---

## Turn 6 - GREEN (checkpoint first)

```bash
$ python3 scripts/viora.py checkpoint --label "before GREEN"
checkpoint 20260826-081455 saved - before GREEN
base commit: a91f0c73de | uncommitted diff: 412 bytes
undo everything since this point: python3 scripts/viora.py rollback --yes
```

The edit, in `src/routes/login.ts`:

```ts
router.post("/login", async (req, res) => {
  let body: Record<string, unknown>;
  try {
    body = requireObjectBody(req.body);
  } catch {
    return res.status(400).json({ error: "A JSON object body is required." });
  }
  const { email, password } = body as { email?: string; password?: string };
  const user = await auth.authenticate(email, password);
  return res.json({ token: user.token, userId: user.id });
});
```

```bash
$ npm test -- login.test.ts
 PASS  test/login.test.ts
  v returns 400 when the body is empty (9 ms)
  v returns 200 for a valid body (12 ms)

Tests: 5 passed, 5 total

$ python3 scripts/viora.py scope
VIORA T0 | MODE FIX | STEP 6/10 GREEN

declared: src/routes/login.ts, test/login.test.ts
touched:  src/routes/login.ts, test/login.test.ts
lines:    23 changed (budget 40) | files: 2 (tier cap 1)

SCOPE OK - every changed file was declared, and the budget holds.

$ python3 scripts/viora.py done 6 --note "GREEN: login.ts:11 reuses requireObjectBody; 5/5 tests pass"
VIORA T0 | MODE FIX | STEP 7/10 CLEAN
step 6 GREEN: done
```

---

## Turn 7 - CLEAN

Checked against the T0 limits: 1 function touched, 14 lines, nesting depth 2, no magic
literals (the message is a string literal used once, which is not a magic value), no debug
output, no commented code, no unused imports.

```bash
$ git --no-pager diff --stat
 src/routes/login.ts   | 9 ++++++--
 test/login.test.ts    | 6 ++++++
 2 files changed, 13 insertions(+), 2 deletions(-)

$ python3 scripts/viora.py done 7 --note "CLEAN: 2 files, 13 insertions, limits pass, no residue"
VIORA T0 | MODE FIX | STEP 8/10 PROVE
step 7 CLEAN: done
```

---

## Turn 8 - PROVE, and the mistake that gets caught

```bash
$ python3 scripts/viora.py gate
==> lint: npm run lint
==> types: npx tsc --noEmit
==> test: npm test
==> build: npm run build

## Evidence table

| Gate | Command | Result |
|---|---|---|
| lint | `npm run lint` | PASS |
| types | `npx tsc --noEmit` | PASS |
| test | `npm test` | PASS |
| build | `npm run build` | PASS |

VERDICT: all executed gates PASS. Gates marked SKIP remain UNPROVEN.

recorded 4 gate row(s); evidence now 5 fresh / 5 total -> .viora/evidence.jsonl
```

Then - and this is the mistake - the error message got reworded, because it read better:

```ts
    return res.status(400).json({ error: "Request body must be a JSON object." });
```

```bash
$ python3 scripts/viora.py check
VIORA T0 | MODE FIX | STEP 8/10 PROVE

NOT READY - 2 problem(s):
  - step 8 PROVE is not done
  - all 5 gate(s) have STALE evidence (format, lint, types, test, build) - the code
    changed after they ran

Fix these before you use the word 'done'. If you cannot, report BLOCKED with this list.
```

A one-word edit invalidated every proof, and the tool said so before the report did. Rerun:

```bash
$ python3 scripts/viora.py gate
...
| test | `npm test` | PASS |
recorded 4 gate row(s); evidence now 4 fresh / 9 total -> .viora/evidence.jsonl

$ python3 scripts/viora.py done 8 --note "gates rerun after the message reword: 4/4 PASS"
VIORA T0 | MODE FIX | STEP 9/10 DOUBT
step 8 PROVE: done
```

**This is the single habit that separates a trustworthy agent from a plausible one:**
after the last edit, the gates run again. Not before. After.

---

## Turn 9 - DOUBT (the five T0 questions, answered honestly)

> 1. **What proves it?** `npm test` 5/5 and `tsc --noEmit` clean, both rerun after the last edit.
> 2. **What did I change that nobody asked for?** Nothing. Two files, both declared.
> 3. **Empty / null / huge / wrong type?** `{}` -> 400. `null` -> 400. A JSON array -> 400,
>    because `requireObjectBody` rejects arrays. A 10 MB body is handled by the body parser
>    limit, which I did not touch and did not test.
> 4. **Second place doing this?** No - I reused the existing helper instead of adding one.
> 5. **What am I calling done that I never ran?** The 400 path was never exercised against a
>    real client, only through supertest. And `/signup` uses the same destructuring pattern
>    at `src/routes/signup.ts:11`, so it very likely has the same bug. Out of contract.

```bash
$ python3 scripts/viora.py ledger add --severity Optional --where src/routes/signup.ts:11 \
    --text "same unguarded destructuring as login had; likely identical 500"
F1 Optional @ src/routes/signup.ts:11: same unguarded destructuring as login had; likely identical 500

$ python3 scripts/viora.py done 9 --note "doubt pass: 1 finding (F1 Optional, out of contract, deferred to follow-ups)"
VIORA T0 | MODE FIX | STEP 10/10 REPORT
step 9 DOUBT: done
```

Question 5 found a real second bug. The correct move was to write it down, **not** to fix
it - fixing it would have broken the contract and the file budget in the same stroke.

---

## Turn 10 - REPORT

```bash
$ python3 scripts/viora.py done 10
$ python3 scripts/viora.py report
VIORA T0 | MODE FIX | STEP 10/10 REPORTED

VERDICT: DELIVERED
MODE: FIX | TIER: T0 | TASK: POST /login returns 500 on empty body, should be 400

CONTRACT
- GOAL: POST /login with an empty or non-object body returns 400 with a JSON error
- DONE-TEST: npm test -- login.test.ts
- PROTECTED: the existing 200 path for a valid body; the shape of LoginResponse

WHAT CHANGED
- 2 file(s), 23 changed line(s): src/routes/login.ts, test/login.test.ts
- 1 CONTRACT: contract written; DONE-TEST=npm test -- login.test.ts
- 2 OWNER: Owner: src/routes/login.ts:14; existing helper validation/body.ts:3
- 3 LADDER: rung 2 reuse requireObjectBody; rung 1 fails - no flag or middleware exists
- 4 PLAN: FILE: src/routes/login.ts + test/login.test.ts; <=40 lines
- 5 RED: test/login.test.ts new case fails with TypeError at login.ts:14
- 6 GREEN: login.ts:11 reuses requireObjectBody; 5/5 tests pass
- 7 CLEAN: 2 files, 13 insertions, limits pass, no residue
- 8 PROVE: gates rerun after the message reword: 4/4 PASS
- 9 DOUBT: doubt pass: 1 finding (F1 Optional, out of contract, deferred)

EVIDENCE
| Gate | Command | Result | Fresh |
|---|---|---|---|
| red | `npm test -- login.test.ts` | FAIL as expected: TypeError at login.ts:14 | pre-fix |
| format | `npm run format:check` | PASS | yes |
| lint | `npm run lint` | PASS | yes |
| types | `npx tsc --noEmit` | PASS | yes |
| test | `npm test` | PASS 5/5 | yes |
| build | `npm run build` | PASS | yes |

One row per gate - the newest one. The earlier `lint` and `test` rows from before the message
reword are still in `evidence.jsonl`, superseded and not counted. The `red` row reads `pre-fix`
on purpose: it describes the tree before the fix, which is exactly why it no longer matches it.

NOT DONE / UNPROVEN
- the 400 response is asserted by status code only; the error body shape is asserted nowhere
- a request with a malformed Content-Type is untested; it may still reach the handler

FOLLOW-UPS
- F1 Optional @ src/routes/signup.ts:11: same unguarded destructuring as login had
```

The STALE rows stay in the report on purpose. They are the audit trail of the reword, and
the four fresh rows underneath them are the actual proof.

---

## What to copy from this

1. **One step per turn, header line every time.** Ten short turns beat one long turn that
   loses the thread halfway through.
2. **Step 2 pays for itself.** Finding `requireObjectBody` turned a 60-line new validator
   into a 9-line reuse.
3. **RED before GREEN, always.** The TypeError at `login.ts:14` confirmed the owner line was
   right *before* any code was written.
4. **Checkpoint costs one second.** It is the difference between one bad edit and five turns
   of digging.
5. **Rerun the gates after the last edit.** A reworded string invalidated four green gates.
   `check` caught it; a confident summary would not have.
6. **Write down the second bug, do not fix it.** F1 went to FOLLOW-UPS. That is discipline,
   not laziness.
7. **`--force` is legitimate when you say why.** Two files for a fix is normal; forcing it
   left a record instead of hiding it.
