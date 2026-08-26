# 05 - Tests, verification and evidence

Read when deciding what to test and before claiming anything is done.

```
NO COMPLETION CLAIM WITHOUT FRESH COMMAND OUTPUT FROM THE CURRENT CODE.
```

"Should work", "looks right", "I fixed it" are not results. This is the law the whole protocol
protects, because it is the one an agent breaks most naturally: predicting output is exactly
what a language model does well, and exactly what must never substitute for running the command.

---

## 1. Proportionate testing (what to write, by mode)

| Mode | Required checks |
|---|---|
| TRIVIAL | run the existing gates; no new test |
| **FIX** | **first** write the check that fails **because of the reported bug**, watch it fail, then fix, then watch it pass |
| FEATURE | main path + one boundary/edge + one failure path if failure is user-visible |
| REFACTOR | no new tests; the existing suite must pass **unchanged**. If you must edit a test, the change is not a refactor |
| UI | the surface renders exactly once; open/close leaves no residue; the interaction works |
| PERF | measurement before and after, plus a test locking in correctness |
| REVIEW | nothing to run; report findings |
| DEBUG | the reproduction command, then the regression test that guards it |

If the repository has no test infrastructure, do not build one uninvited: exercise the code directly (script, request, CLI run) and paste that output as evidence. Say `UNPROVEN` for what you could not exercise.

## 2. Red before green

```
1 write the smallest check for the behaviour
2 RUN IT and read the failure
3 confirm it fails for the RIGHT reason
4 implement the minimum that passes
5 RUN IT again - green, and the rest of the suite still green
6 report both runs
```

Step 3 is the one that gets skipped and the one that carries the value. A test that fails
because of a typo, a missing import or a wrong path proves nothing about your code. A test
you never watched fail is not known to test anything at all.

Writing the test after the fix and assuming it would have failed is exactly how silent
regressions ship. **Wrote the code first?** The honest recovery is: delete it, write the test,
watch it fail, write it again. It takes minutes, and it is the only way you find out the test
actually detects the problem. Keeping the code "as a reference" means you will adapt it, which
is testing after with extra steps.

## 3. Seams: where to attach the test

A seam is the boundary you test through. Choose it **before** writing the test, and at T2 state
it out loud so the user can correct you - a badly chosen seam produces tests that break on every
refactor and prove nothing about behaviour.

| Good seams | Bad seams |
|---|---|
| exported function or class | private method reached through a back door |
| HTTP route / handler | internal helper three layers down |
| CLI invocation | a mock you wrote yourself |
| rendered component + user event | component internal state |
| queue message in -> effect out | the ORM call inside a service |

Rule of thumb: **test what the caller can observe.** If a pure refactor breaks the test, the
test was attached to the implementation, not the behaviour.

## 4. Test quality rules

- One behaviour per test. The name states the behaviour: `returns empty csv for empty input`, not `test1`.
- Arrange - act - assert. No branching, loops or clever helpers inside tests; a test must be obviously correct.
- Assert on **observable behaviour** (return value, rendered output, stored row, emitted event), not on internals or call counts of your own functions.
- Deterministic: no `sleep`, no wall-clock dependence, no random data without a fixed seed, no reliance on test order. Wait for a **condition**, never for a duration.
- Independent: each test sets up and tears down its own state. Shared mutable fixtures cause phantom failures.
- Mock only true external boundaries (network, clock, filesystem, third-party service). Mocking the thing under test produces a test of your mock.
- Stable selectors for UI: repository-owned test ids. Never visible text, CSS classes or DOM position.

### The three anti-patterns

| Anti-pattern | What it looks like | Why it is worthless |
|---|---|---|
| **Implementation-coupled** | asserts internal calls, private fields, call counts | breaks on every refactor, catches no bug |
| **Tautological** | re-implements the logic in the test, or asserts a constant equals itself | passes by construction |
| **Horizontally sliced** | "all the validators", "all the getters" in one sweep | no single behaviour is actually pinned; failures are unreadable |

Prefer **vertical slices**: one behaviour end to end, through every layer it touches. One thin
slice working beats five layers half-built - it proves the wiring, which is where generated
code fails most.

**Do not write**: tests of framework behaviour, getter/setter tests, snapshot dumps nobody
reads, or tests added only to raise a coverage number. Deleting a worthless test is an
improvement; deleting an inconvenient one is misconduct.

## 5. Refactoring is not part of the red-green loop

Red, green, and *stop*. Cleaning up is step 7 CLEAN, with the tests already green and
unmodified. Mixing "make it pass" with "make it nice" is how a passing test turns red again
with nobody able to say which edit did it.

## 6. The verification gate (run before every completion claim)

```
1 IDENTIFY  - which commands does this repo define? (scan_repo.py, manifest, Makefile, CI config)
2 RUN       - run them on the current code, unfiltered
3 READ      - read the whole output, not just the exit status
4 CLASSIFY  - PASS / FAIL / SKIP-UNPROVEN for each
5 CLAIM     - only what the output supports
```

One command for most repositories:

```bash
python3 scripts/viora.py gate           # runs the gates AND records the evidence
bash scripts/verify.sh .                # the gates alone
bash scripts/verify.sh . --only test    # narrow it
```

Prefer `viora.py gate`: it appends every gate row to `.viora/evidence.jsonl`, and `viora.py report`
will only print `PASS` for a gate that exists in that log. That is the mechanical answer to
remembered - or invented - test results.

### What each claim actually requires

| Claim | Requires | Not sufficient |
|---|---|---|
| "it compiles" | build/typecheck output, exit 0 | it looks syntactically fine |
| "tests pass" | test output with counts, from this code | tests passed before the last edit |
| "the bug is fixed" | the reproduction now behaves correctly | the code looks right now |
| "nothing else broke" | the full suite green | the touched file's tests green |
| "it is faster" | a before number and an after number | it should be faster in theory |
| "it works end to end" | the real path exercised, output pasted | the unit tests pass |

### Output traps to look for

`0 tests ran` · `skipped: 12` · exit 0 with warnings · a build served from cache · a watcher
that never exited · a test file silently filtered out · a suite that passed because the whole
file failed to import.

## 7. Never do this

- Never fabricate, paraphrase or "reconstruct" command output.
- Never delete, skip, `xfail`, comment out or loosen an assertion to get green.
- Never add a lint suppression to hide a real finding (a justified suppression is documented in the report).
- Never claim a percentage or timing you did not measure.
- Never re-run a flaky test until it passes: diagnose it, or report it as flaky with the exact name.
- Never say "all tests pass" when you ran one file. Say what you ran.

## 8. Evidence table (goes into the report)

```
| Gate  | Command                | Result                        |
|-------|------------------------|-------------------------------|
| lint  | npm run lint           | PASS (0 warnings)             |
| types | npm run typecheck      | PASS                          |
| test  | npm test -- export     | PASS (2 added, 44 total)      |
| build | npm run build          | PASS (4.1s)                   |
| ui    | ui_guard.py --strict   | PASS (0 findings)             |
| e2e   | -                      | UNPROVEN (no browser here)    |
```

## 9. Definition of done

Acceptance criteria are per-task and come from the contract. This is the standing bar that
applies to **every** change regardless of the task.

```
CORRECTNESS
[ ] does what the contract says, including the boundary the contract implies
[ ] error paths handled, not just the happy path
[ ] no behaviour changed that nobody asked for (defaults, ordering, error text, formats)

QUALITY
[ ] hard limits respected or the exception stated
[ ] no duplicated owner created
[ ] no debug output, dead code, commented-out code or unused imports
[ ] names and structure match this repository

INTEGRATION
[ ] wired in and reachable by a real caller or user action
[ ] callers of anything you changed were checked
[ ] nothing left half-applied

EVIDENCE
[ ] every gate the repo defines was run on this code, output read in full
[ ] the contract's DONE-TEST was executed
[ ] behavioural fixes have a regression check that was seen to fail without the fix

HONESTY
[ ] everything unverified is labelled UNPROVEN
[ ] deviations from the plan are reported
[ ] follow-ups named with exact paths
```

Every unchecked box is either work remaining or a line in NOT DONE / UNPROVEN. There is no
third option.

---

## 10. Evidence expires - staleness is now arithmetic

The most common way an honest agent produces a dishonest report: it runs the gates, they pass, and
then it makes "one last small edit" - a renamed variable, a reworded error string, a comment. The
evidence table in the report is now describing code that no longer exists.

Nobody lied. The report is still wrong.

### How the conductor closes this

Every row written to `.viora/evidence.jsonl` carries a **fingerprint of the working tree** at the
moment the command ran:

- with git: a hash of `HEAD` + `git diff HEAD` + the content of untracked files
- without git: a hash of path, size and mtime across the tree (up to 4000 files)

When the current fingerprint differs from the one stored on a row, that row is `STALE`:

```bash
$ python3 scripts/viora.py check
NOT READY - 1 problem(s):
  - all 5 gate(s) have STALE evidence (format, lint, types, test, build) - the code
    changed after they ran
```

`report` prints the row with `Fresh: STALE` and counts it into `NOT DONE / UNPROVEN`. The
pre-commit hook refuses the commit. There is exactly one honest response:

```bash
python3 scripts/viora.py gate      # rerun. That is the whole fix.
```

### One row per gate, and the one row that is supposed to rot

The log is append-only, so rerunning `test` never erases the old `test` row - that is what
makes it auditable. So `check`, `report` and `doctor` judge only the **newest row per gate
name**. A superseded row is history, not debt: if it counted, no amount of rerunning could
ever clear it, and the tool would be permanently, uselessly angry.

One family of rows is *expected* to go stale: `red`, `repro`, `reproduce`, `baseline`,
`before`. Their job is to describe the tree **before** the fix. The moment the fix lands they
stop matching the tree - and that mismatch is itself evidence the fix changed something.
Those rows print as `pre-fix` instead of `STALE`, and they never block `check`.

What *does* block `check`: having **only** pre-fix rows.

```text
only pre-fix evidence exists (red) - nothing proves the CURRENT tree. Run: viora.py gate
```

A reproduction is not a proof of repair. Recording the failure and then claiming the fix is
the oldest trick in the book, and it is now a named refusal rather than a matter of taste.

### The rule this replaces

Old rule, easy to forget: *"rerun the gates after your last edit."*

New rule, impossible to forget: **the order is always last edit -> gates -> report.** Reversing
those two produces a stale row, and the machine says so before anyone else has to.

### What staleness is not

- **Not a failure.** A stale row means unknown, not broken. Report it as UNPROVEN, never as FAIL -
  a false FAIL sends a colleague hunting for a bug that may not exist.
- **Not a reason to skip the gate.** "It passed a minute ago and I only changed a comment" is a
  prediction about a compiler, not an observation of one. Comments have broken builds before -
  in doctests, in annotations, in generated code, in linters configured with `--max-warnings 0`.
- **Not defeated by `--force`.** There is no flag to mark a stale row fresh. Rerun it or declare
  it unproven; the third option does not exist by design.

### Manual evidence for repos with no runner

When there is nothing to run, record the command you did run - with both values:

```bash
python3 scripts/viora.py evidence \
  --gate manual-check \
  --command "python3 -c 'from cart import checkout; print(checkout([{\"unit_cents\":1000,\"qty\":1}], True))'" \
  --result "9.00 after the fix (was 8.10 before)"
```

This row is fingerprinted like any other, so it goes stale like any other. A before-value and an
after-value is proof of a change. An after-value alone is proof that the code runs.
