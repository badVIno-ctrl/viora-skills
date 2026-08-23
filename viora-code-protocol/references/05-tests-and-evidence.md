# 05 - Tests, verification and evidence

Read when deciding what to test and before claiming anything is done.

**Iron law: no completion claim without fresh command output from the current code.** "Should work", "looks right", "I fixed it" are not results.

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

If the repository has no test infrastructure, do not build one uninvited: exercise the code directly (script, request, CLI run) and paste that output as evidence. Say `UNPROVEN` for what you could not exercise.

## 2. Red before green (for bugs and new behavior)

1. Write the smallest check that reproduces the problem.
2. **Run it and read the failure.** It must fail for the reported reason, not because of a typo, missing import, or wrong path. A test that fails for the wrong reason proves nothing.
3. Implement the fix.
4. Run again: it passes, and the rest of the suite is still green.
5. Report both runs.

Writing the test after the fix and assuming it would have failed is exactly how silent regressions ship.

## 3. Test quality rules

- One behavior per test. The name states the behavior: `returns empty csv for empty input`, not `test1`.
- Arrange - act - assert. No branching, loops or clever helpers inside tests; a test must be obviously correct.
- Assert on **observable behavior** (return value, rendered output, stored row, emitted event), not on internals or call counts of your own functions.
- Deterministic: no `sleep`, no wall-clock dependence, no random data without a fixed seed, no reliance on test order. Wait for a **condition**, never for a duration.
- Independent: each test sets up and tears down its own state. Shared mutable fixtures cause phantom failures.
- Mock only true external boundaries (network, clock, filesystem, third-party service). Mocking the thing under test produces a test of your mock.
- Stable selectors for UI: repository-owned test ids. Never visible text, CSS classes or DOM position.

**Do not write**: tests of framework behavior, getter/setter tests, snapshot dumps nobody reads, tests asserting a constant equals itself, or tests added only to raise a coverage number. Deleting a worthless test is an improvement; deleting an inconvenient one is misconduct.

## 4. The verification gate (run before every completion claim)

```
1. IDENTIFY  - which commands does this repo define? (scan_repo.py, manifest, Makefile, CI config)
2. RUN       - run them on the current code, unfiltered
3. READ      - read the whole output, not just the exit status
4. CLASSIFY  - PASS / FAIL / SKIP-UNPROVEN for each
5. CLAIM     - only what the output supports
```

One command for most repositories:

```bash
bash scripts/verify.sh .              # detects and runs format/lint/types/test/build
bash scripts/verify.sh . --only test  # narrow it
```

When reading output, look for the traps: `0 tests ran`, `skipped: 12`, a passing exit code with warnings, a build that succeeded from cache, a watcher that never exited, a test file that was silently filtered out.

## 5. Never do this

- Never fabricate, paraphrase or "reconstruct" command output.
- Never delete, skip, `xfail`, comment out or loosen an assertion to get green.
- Never add a lint suppression to hide a real finding (a justified suppression is documented in the report).
- Never claim a percentage or timing you did not measure.
- Never re-run a flaky test until it passes: diagnose it, or report it as flaky with the exact name.
- Never say "all tests pass" when you ran one file. Say what you ran.

## 6. Evidence table (goes into the report)

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

## 7. Verification exit checklist

```
[ ] the bug has a check that failed before the fix (FIX mode)
[ ] gates identified from the repo, not invented
[ ] every gate run on the current code, output read in full
[ ] no test weakened, skipped or deleted to pass
[ ] evidence table filled with real commands and real results
[ ] everything unverified explicitly labelled UNPROVEN
```
