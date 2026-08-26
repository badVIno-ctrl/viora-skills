# Example 3 - REVIEW mode: a differential review that finds what the diff hides

**Situation.** The user says: *"review this PR before I merge it"*. The branch adds a
"remember me" option to login. 4 files, +180 / -22.

REVIEW mode runs only steps **1 -> 2 -> 9 -> 10**. There is no GREEN, because a review that
edits the code is not a review. The whole weight of the mode sits on step 9 DOUBT.

This run is at **T2** (a strong model). The T0 version of the same review is at the bottom -
shorter, narrower, and still useful.

---

## Turn 0 - open the run, establish the range

```bash
$ python3 scripts/viora.py start --mode REVIEW --tier T2 --task "review PR: remember-me option on login"
VIORA T2 | MODE REVIEW | STEP 1/10 CONTRACT
steps for REVIEW: 1 -> 2 -> 9 -> 10
budget: <= 300 changed lines, <= 8 file(s), 5 doubt round(s), 3 strike(s) then BLOCKED

$ BASE=$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD~1)
$ echo $BASE
7c22ab9e4d1188aa3f0b

$ git --no-pager diff --stat $BASE...HEAD
 src/routes/login.ts          |  38 ++++++++++--
 src/services/session.ts      |  84 +++++++++++++++++++++--
 src/types/session.d.ts       |   9 ++-
 test/login.test.ts           |  71 ++++++++++++++++
 4 files changed, 180 insertions(+), 22 deletions(-)
```

180 changed lines - inside the 300 target, so this is reviewable in one pass at
**standard depth** (20-200 lines). Above 200 it would have to be split.

```bash
$ python3 scripts/viora.py contract \
    --goal "decide whether this PR is safe to merge, with a severity-labelled finding list" \
    --done-test "every file in the diff read line by line; every finding has file:line and a severity" \
    --protected "the branch itself - I do not edit it" \
    --non-goals "rewriting the feature, style opinions, unrelated files"
written: .viora/contract.md

$ python3 scripts/viora.py done 1 --note "review contract: findings with file:line + severity, no edits"
VIORA T2 | MODE REVIEW | STEP 2/10 OWNER
```

---

## Turn 1 - OWNER, but for a review this means blast radius

```bash
$ git --no-pager diff $BASE...HEAD --name-only | while read f; do echo "--- $f"; grep -rn "$(basename ${f%.*})" src --include="*.ts" -l | head -5; done
--- src/services/session.ts
src/routes/login.ts
src/routes/logout.ts
src/middleware/requireAuth.ts
src/routes/profile.ts
src/jobs/sessionCleanup.ts

$ grep -rn "createSession\|SESSION_TTL" src --include="*.ts"
src/services/session.ts:22:const SESSION_TTL = 60 * 60 * 24 * 30;
src/services/session.ts:31:export function createSession(userId: string, remember: boolean) {
src/routes/login.ts:29:  const session = createSession(user.id, remember);
src/middleware/requireAuth.ts:14:  const session = await loadSession(req.cookies.sid);
src/jobs/sessionCleanup.ts:9:  // deletes sessions older than SESSION_TTL
```

**Blast radius: 6-50 callers.** `session.ts` is touched by auth middleware, logout, profile
and a cleanup job. None of those four files are in the diff, and that is the single most
important fact about this PR.

Then the history, because a diff alone cannot tell you *why* a line exists:

```bash
$ git log -S'SESSION_TTL' --oneline -- src/services/session.ts
9f31c02 harden session expiry after incident #412 (4 months ago)
2ab77e1 initial session service (14 months ago)

$ git show 9f31c02 --stat
 harden session expiry after incident #412
 src/services/session.ts | 12 ++++++---
 docs/incidents/412.md   | 30 ++++++++++++++++

$ git blame -L 20,24 src/services/session.ts
9f31c02 (Dana 4 months ago 22) const SESSION_TTL = 60 * 60 * 24 * 30;
9f31c02 (Dana 4 months ago 23) // capped deliberately: incident #412, do not raise without security review
```

That comment is on line 23 of the base. The PR changes line 22. **The diff shows the change
but not the reason the old value was chosen** - only `git log -S` surfaced it.

```bash
$ python3 scripts/viora.py done 2 --note "blast radius 6-50: requireAuth, logout, profile, sessionCleanup all consume session.ts and are NOT in the diff; SESSION_TTL was capped by incident #412"
VIORA T2 | MODE REVIEW | STEP 9/10 DOUBT
```

---

## Turn 2 - DOUBT round 1: read every changed line

```bash
$ git --no-pager diff $BASE...HEAD -- src/services/session.ts
@@ -20,8 +20,10 @@
-const SESSION_TTL = 60 * 60 * 24 * 30;
-// capped deliberately: incident #412, do not raise without security review
+const SESSION_TTL = 60 * 60 * 24 * 30;
+const REMEMBER_TTL = 60 * 60 * 24 * 365;
@@ -31,7 +33,14 @@
-export function createSession(userId: string) {
+export function createSession(userId: string, remember: boolean) {
+  const ttl = remember ? REMEMBER_TTL : SESSION_TTL;
   ...
@@ -58,6 +67,9 @@
+export async function loadSession(sid: string) {
+  const row = await db.sessions.findOne({ sid });
+  if (!row) return null;
+  return row;
 }
```

Findings, each with a file:line and a severity:

```bash
$ python3 scripts/viora.py ledger add --severity Critical --where src/services/session.ts:23 \
    --text "the incident #412 warning comment was deleted, and REMEMBER_TTL (365d) is 12x the value that incident capped; no security review referenced in the PR"
F1 Critical @ src/services/session.ts:23

$ python3 scripts/viora.py ledger add --severity Critical --where src/services/session.ts:33 \
    --text "createSession() gained a required second parameter; 3 callers outside the diff (logout.ts, profile.ts, sessionCleanup.ts) are not updated - if TS did not catch it, one of them passes undefined and silently gets the short TTL"
F2 Critical @ src/services/session.ts:33

$ python3 scripts/viora.py ledger add --severity Required --where src/services/session.ts:70 \
    --text "loadSession() returns the raw db row including passwordHash and internalNotes; requireAuth.ts:14 puts this on req.session, so those fields are now reachable anywhere downstream"
F3 Required @ src/services/session.ts:70

$ python3 scripts/viora.py ledger add --severity Required --where src/jobs/sessionCleanup.ts:9 \
    --text "the cleanup job deletes anything older than SESSION_TTL, so it will delete remember-me sessions after 30 days - the feature silently does not work after a month"
F4 Required @ src/jobs/sessionCleanup.ts:9

$ python3 scripts/viora.py ledger add --severity Optional --where src/routes/login.ts:24 \
    --text "remember is read as req.body.remember with no validation; the string 'false' is truthy and grants a 365-day session"
F5 Optional @ src/routes/login.ts:24

$ python3 scripts/viora.py ledger add --severity Nit --where src/types/session.d.ts:11 \
    --text "remember?: boolean is optional in the type but required in the function signature"
F6 Nit @ src/types/session.d.ts:11
```

**F4 is the finding that justifies the whole method.** It is not in the diff at all. It
lives in a file nobody touched, and it makes the feature quietly stop working after 30
days. Only the blast-radius pass in step 2 could have found it.

---

## Turn 3 - DOUBT round 2: the adversarial pass

Round 1 asks "is this code correct?". Round 2 asks "how do I break it?".

> - **Can I get a 365-day session without ticking the box?** Yes - F5. `remember: "no"` is a
>   non-empty string, so it is truthy.
> - **What happens on logout?** `logout.ts` deletes by `sid`. Fine.
> - **What happens to an existing session created before this PR?** `remember` is absent, so
>   `ttl` falls back to `SESSION_TTL`. Fine.
> - **What does the new test actually assert?**

```bash
$ grep -n "expect" test/login.test.ts | tail -6
61:    expect(res.status).toBe(200);
64:    expect(res.headers["set-cookie"]).toBeDefined();
70:    expect(session).toBeTruthy();
```

> The three new tests assert that a cookie **exists**. Not one of them asserts the TTL, which
> is the entire feature. This is a green test suite that proves nothing about the change.

```bash
$ python3 scripts/viora.py ledger add --severity Required --where test/login.test.ts:61 \
    --text "the 3 new tests assert only that a cookie exists; none asserts the 365-day TTL, so the feature is untested despite the suite being green"
F7 Required @ test/login.test.ts:61
```

Then the gates, because a review that trusts the CI badge is not a review:

```bash
$ python3 scripts/viora.py gate
==> lint: npm run lint
==> types: npx tsc --noEmit
==> test: npm test

## Evidence table

| Gate | Command | Result |
|---|---|---|
| lint | `npm run lint` | PASS |
| types | `npx tsc --noEmit` | FAIL |
| test | `npm test` | PASS |

VERDICT: FAIL - fix the failing gate before claiming completion.
recorded 3 gate row(s); evidence now 3 fresh / 3 total

$ npx tsc --noEmit 2>&1 | head -3
src/routes/logout.ts:18:31 - error TS2554: Expected 2 arguments, but got 1.
```

F2 confirmed by the compiler, not by argument. The PR does not build.

```bash
$ python3 scripts/viora.py done 9 --note "2 doubt rounds + adversarial pass; 7 findings (2 Critical, 4 Required, 1 Nit); tsc FAILS on logout.ts:18"
VIORA T2 | MODE REVIEW | STEP 10/10 REPORT
```

---

## Turn 4 - REPORT

```bash
$ python3 scripts/viora.py ledger list
| ID | Severity | Where | Verdict | Text |
|---|---|---|---|---|
| F1 | Critical | src/services/session.ts:23 | OPEN | incident #412 warning deleted... |
| F2 | Critical | src/services/session.ts:33 | OPEN | createSession() signature... |
| F3 | Required | src/services/session.ts:70 | OPEN | loadSession leaks passwordHash |
| F4 | Required | src/jobs/sessionCleanup.ts:9 | OPEN | cleanup deletes remember sessions |
| F5 | Optional | src/routes/login.ts:24 | OPEN | remember not validated |
| F6 | Nit | src/types/session.d.ts:11 | OPEN | optional vs required mismatch |
| F7 | Required | test/login.test.ts:61 | OPEN | tests assert cookie, not TTL |

$ python3 scripts/viora.py report
VERDICT: BLOCKED
MODE: REVIEW | TIER: T2 | TASK: review PR: remember-me option on login

NOT DONE / UNPROVEN
- gate 'types' FAILED: FAIL
- F1 Critical @ src/services/session.ts:23 is still OPEN: incident #412 warning deleted...
- F2 Critical @ src/services/session.ts:33 is still OPEN: createSession() signature...
```

**Reply to the user:**

> VIORA T2 | MODE REVIEW | REPORT
>
> **Do not merge.** `npx tsc --noEmit` fails on `src/routes/logout.ts:18`, so this branch
> does not compile. That alone is decisive; the rest matters for the next revision.
>
> **Must fix (2)**
> - **F1 `session.ts:23`** - the PR deletes the comment
>   *"capped deliberately: incident #412, do not raise without security review"* and
>   introduces a 365-day TTL, 12x the capped value. `git log -S'SESSION_TTL'` points at
>   commit `9f31c02` and `docs/incidents/412.md`. This needs the security review that comment
>   asks for, not a code fix.
> - **F2 `session.ts:33`** - `createSession()` gained a required parameter and three callers
>   outside the diff were not updated. `tsc` proves it.
>
> **Should fix (3)**
> - **F4 `sessionCleanup.ts:9`** - not in this diff, and the most interesting finding: the
>   cleanup job deletes sessions older than `SESSION_TTL`, so every remember-me session dies
>   at day 30. The feature would appear to work in QA and fail a month after launch.
> - **F3 `session.ts:70`** - `loadSession()` returns the raw row, so `passwordHash` reaches
>   `req.session`. Select explicit fields.
> - **F7 `test/login.test.ts:61`** - all three new tests assert a cookie exists; none asserts
>   the TTL. The suite is green and the feature is untested.
>
> **Optional (1)** F5 `login.ts:24` - `remember` unvalidated; `"false"` is truthy.
> **Nit (1)** F6 `session.d.ts:11` - optional in the type, required in the signature.
>
> I changed nothing. Findings ordered by severity, each with file:line.

---

## The same review at T0

A small model should not attempt the history forensics or the adversarial round. It should
do this instead, and it will still catch F2 and F7:

```bash
$ python3 scripts/viora.py start --mode REVIEW --tier T0 --task "review PR: remember-me"
$ git --no-pager diff --stat $BASE...HEAD          # 1. how big is it
$ npx tsc --noEmit                                  # 2. does it compile - ALWAYS
$ npm test                                          # 3. do tests pass
$ git --no-pager diff $BASE...HEAD | head -200      # 4. read the diff, one file at a time
$ grep -rn "createSession" src --include="*.ts"     # 5. for each changed export: who calls it
$ grep -n "expect" test/login.test.ts               # 6. what do the new tests assert
```

Six commands, in that order, every time. Then: one finding per line, each with `file:line`
and a severity, and the honest closing sentence -
**"I reviewed the diff and the direct callers of the changed exports. I did not review the
rest of the repository, and I did not run the app."**

---

## What to copy from this

1. **Establish the range with `git merge-base` first.** Reviewing the wrong range is the
   most common way to review nothing.
2. **The diff is not the change.** F4, the finding that actually kills the feature, is in a
   file the PR never touches.
3. **`git log -S` and `git blame` before judging a constant.** A number with a history is
   not an arbitrary number.
4. **Run the gates yourself.** `tsc` settled F2 in one second, with no argument.
5. **Read what the tests assert, not that they pass.** Green suites hide untested features.
6. **Every finding gets file:line + severity.** "This feels risky" is not a finding.
7. **Never edit in REVIEW mode.** The output is a decision and a list, not a diff.
