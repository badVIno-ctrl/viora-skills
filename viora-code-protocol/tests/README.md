# tests/ - the protocol tests itself

These suites exist for one reason: a protocol about not trusting unproven claims cannot ship
unproven claims about itself. Every refusal promised in `SKILL.md` is asserted here against the
real scripts.

```bash
bash tests/run-all.sh          # all three suites, one summary line
bash tests/01-conductor.sh     # one suite, full output
```

Requirements: `bash`, `git`, `python3`. No network, no dependencies, no config. Each suite builds
a throwaway git repo under `/tmp` and never touches your project.

## What each suite covers

| Suite | Assertions | What it proves |
|---|---|---|
| `01-conductor.sh` | 53 | Every `viora.py` subcommand, the step machine, tier budgets, scope from git, checkpoint/rollback, strikes, demotion, and every exit code the docs promise |
| `02-hooks-and-evals.sh` | 6 | `hooks/install-hooks.sh` (install, `--check`, backup, restore), the pre-commit hook (blocks an unready run, blocks conflict markers and focused tests, warns on debug residue, honours `VIORA_SKIP=1`), and the whole `evals/` harness end to end |
| `03-prefix-evidence.sh` | 26 | Evidence staleness arithmetic: one row per gate, `pre-fix` rows exempt, a reproduction alone refused, a rerun clearing staleness, gate names matched case-insensitively |

85 assertions total. All green as shipped.

## Why these particular tests exist

They were not written to decorate the package. Writing them found **eight** defects that reading
the code had not, and every one would have made the protocol produce a misleading report:

1. `scope` counted build junk (`__pycache__/*.pyc`) as undeclared files - a clean run reported
   900 changed lines and refused to close.
2. A deliberately widened plan deadlocked: the file cap was re-checked against the plan instead
   of the tier, so `plan --force` could not rescue the run.
3. Running the gates invalidated its own evidence - `gate` wrote `.pyc` files, which moved the
   fingerprint, which marked the rows it had just written STALE.
4. `strike` past the cap and `demote` at T0 printed the correct refusal but exited `0`, so a hook
   or CI job would have read both as success.
5. The pre-commit hook printed `integer expression expected` on every commit: `grep -c` exits 1
   on zero matches, so the counter received `"0\n0"`.
6. `score.py --fixture f01` accepted only a path relative to the current directory - and the
   "a bad transcript must FAIL" assertion had been passing for the wrong reason: an argument
   error, not a verdict.
7. The grader failed a genuinely correct transcript because it demanded the literal words
   `reproduc` or `FAIL as expected`. A false negative in the measuring instrument punishes weak
   models for doing the right thing - the worst possible bug in an eval harness.
8. Staleness deadlocked RED-before-GREEN: a `red` row is stale by design the moment the bug is
   fixed, so it blocked `check` forever. That is where the `pre-fix` rule came from.

## If a suite goes red

The assertion text names the promise that broke. Fix the code, or fix the document that promised
it. Do not relax the assertion to get a green number - that is the exact behaviour this protocol
exists to prevent.

When you extend the protocol, add the assertion first. A refusal that is not tested is a refusal
that quietly stops working.
