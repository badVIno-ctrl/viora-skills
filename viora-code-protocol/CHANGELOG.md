# Changelog

## v2.1 - the honesty holes, closed by machinery

v2.0 moved the protocol from the model's memory onto disk. v2.1 closes the three ways a
cooperative agent could still produce a misleading report **without lying once**, adds worked
transcripts to imitate, and makes the protocol survive outside the chat window.

### Added - evidence that cannot go quietly out of date

- **Fingerprinted evidence.** Every gate row in `.viora/evidence.jsonl` now carries a
  fingerprint of the working tree: `git:<hash>` from HEAD plus the diff plus untracked content,
  or `fs:<hash>` over path/size/mtime when git is absent.
- **Staleness.** Edit anything after a gate and that row becomes `STALE`. `check` fails,
  `report` prints it as STALE and moves it into `NOT DONE / UNPROVEN`. The rule "rerun the gates
  after your last edit" became arithmetic instead of a rule to remember.
- **One row per gate.** Only the newest row for each gate name is counted, so rerunning a gate
  supersedes its old row instead of stacking a second one into the report table. Superseded rows
  stay in the append-only log - nothing is rewritten, only ranked.
- **Pre-fix rows are exempt.** Rows named `red`, `repro`, `reproduce`, `baseline` or `before`
  describe the tree *before* the fix, so they print as `pre-fix` rather than STALE and never
  block `check`. The inverse is enforced too: a run whose only evidence is pre-fix is refused
  with `only pre-fix evidence exists (red) - nothing proves the CURRENT tree`. A reproduction
  proves the bug, never the repair.
- **`evidence` subcommand** for manual proof in repos with no test runner:
  `evidence --gate manual-check --command "..." --result "..."`.
- **No double-counting.** `verify.sh` honours `VIORA_NO_EVIDENCE=1`, which `gate` sets, so one
  gate run produces exactly one row set.

### Added - scope measured from git, not from memory

- **`plan`** records the declared files, the line budget and frozen interfaces.
- **`scope`** compares the plan to the real diff: undeclared files, untouched declared files,
  changed-line count against the per-tier budget (T0 80 / T1-T2 300), file count against the
  per-tier cap (T0 1 / T1 3 / T2 8).
- **Steps 6 and 7 refuse to close** while scope has problems. Widening a plan on purpose is
  allowed and recorded: `plan --files <real list> --force`. Silent creep is not.

### Added - undo, so stopping is cheap

- **`checkpoint [--label]`** stores a patch plus metadata under `.viora/checkpoints/`.
- **`rollback [id] --yes`** restores it; refuses without `--yes`, refuses if HEAD moved unless
  `--force`, and lists post-checkpoint untracked files instead of silently deleting them.
- This is what makes the three-strike stop survivable: you hand back a clean tree with two
  recorded dead ends, not a tree full of half-reverted guesses.

### Added - `doctor` and `stats`

- **`doctor`** - one screen before the run: python3, scripts present, git, `.viora/` writable,
  monorepo detected (workspaces, pnpm, lerna, turbo, nx, go.work, Cargo workspace), and which
  gates exist at all. Every `WARN` is a specific way the final report could mislead.
- **`stats`** - reads `.viora/runs.jsonl` across runs: verdict mix, steps forced, strikes,
  demotions, findings. Turns "it feels better" into numbers.

### Added - `examples/`, four complete transcripts

Weak models imitate far better than they reason from rules. Each transcript is a full run with
every command and every reply, and ends with what to copy from it.

- `01-t0-fix-full-run.md` - T0 FIX end to end, including a PLAN refusal at the file cap and
  gates going STALE after a one-word edit
- `02-blocked-and-honest.md` - a vague "add caching" request: code read first, one batched round
  of questions with recommendations and defaults, two dead hypotheses, strike limit, rollback,
  `VERDICT: BLOCKED` with 0 files changed
- `03-review-differential.md` - REVIEW at T2: merge-base, blast radius, `git log -S` uncovering
  why a constant exists, and a Critical finding in a file the diff never touches
- `04-debug-with-demotion.md` - DEBUG at T1: a flake reproduced as a number, scope creep caught
  by `scope`, a self-demotion to T0, and 200/200 runs reported as probabilistic proof

### Added - `evals/`, so "works on weak models" is measurable

- **Six fixtures**, each built around one documented weak-model failure: swallowing an
  exception, duplicating an existing helper, guessing instead of asking, claiming "tests pass"
  where no runner exists, refactoring a file it was told not to touch, and adopting the user's
  wrong hypothesis.
- **`score.py`** - 10 generic procedural checks, per-fixture checks with fatal cases, and 5
  machine checks read from `.viora/`. PASS at 85, WEAK at 60, any fatal failure is a FAIL.
- **`run.sh`** - `list`, `prepare` (throwaway git repo + prompt), `score`, `score-all`, `clean`.
  Calls no model, so it works with any agent.
- **`rubric.md`** - point tables, a score-to-tier calibration, and a 2-minute manual grading
  method for when you have no python.

### Added - survival outside the chat

- **`hooks/pre-commit`** - blocks a commit whose run fails `check` (unfinished steps, stale
  evidence, out-of-plan files, open Critical findings), plus staged conflict markers, focused
  tests, and diffs over 1000 lines. Warns on debug residue. Bypass: `VIORA_SKIP=1`.
- **`hooks/install-hooks.sh`** - `--check` / `--uninstall`, backs up an existing hook, respects
  `core.hooksPath`.
- **`ci/viora.yml`** - four jobs: `gates`, `size`, advisory `hygiene`, and `honesty` (an
  agent-labelled PR body must carry `VERDICT:`, an evidence table and an UNPROVEN section).
  Installs nothing beyond checkout and python.

### Changed

- `references/08-stack-notes.md` rewritten from 76 to ~300 lines: exact gate packs for Node/TS,
  frontend, Python, Go, Rust, Swift/iOS, Kotlin/Android, monorepos and seven more stacks; the
  order of authority for finding a command; per-stack timeout table; and what to do when a repo
  declares no gates at all.
- `SKILL.md` §9 documents the new commands and the three things the machine now enforces;
  §10 indexes `examples/`, `evals/`, the hook and CI.
- `QUICKCARD.md` gained the four extra commands, the strike command, and the staleness rule -
  the single mistake T0 models make most often.
- `INSTALL.md` gained §5 (hooks and CI) and §6 (measuring your own model), and eight new
  troubleshooting rows.
- `viora.py` grew from 14 to 20 subcommands (1148 -> 2100+ lines), still stdlib-only.
- `tests/` added: three suites, 85 assertions, `bash tests/run-all.sh`. See below.

### Verified, not assumed - what the test pass caught

A protocol about refusing unproven claims cannot ship unproven claims about itself. v2.1 includes
`tests/`: three suites, 85 assertions, driving the real conductor, the real pre-commit hook and
the real grader inside throwaway git repos. `bash tests/run-all.sh`, no network, no dependencies.

Writing them found **eight** defects that reading the code had not - every one of them capable of
making the protocol mislead:

1. `scope` counted build junk (`__pycache__/*.pyc`) as undeclared files: a clean two-file change
   reported "900 changed lines" and refused to close.
2. A deliberately widened plan deadlocked the run - the file cap was re-checked against the plan
   instead of the tier, so `plan --force` could not rescue it.
3. Running the gates invalidated its own evidence: `gate` wrote `.pyc` files, which moved the
   fingerprint, which marked the rows it had just written STALE.
4. `strike` past the cap and `demote` at T0 printed the correct refusal but exited `0`, so a hook
   or a CI job would have read both as success.
5. The pre-commit hook printed `integer expression expected` on every commit: `grep -c` exits 1
   on zero matches, so the counter received `"0\n0"`.
6. `score.py --fixture f01` accepted only a path relative to the current directory - and the
   "a bad transcript must FAIL" assertion had been passing for the wrong reason: an argument
   error, not a verdict.
7. The grader failed a genuinely correct transcript because it demanded the literal words
   `reproduc` or `FAIL as expected`. A false negative in the measuring instrument punishes weak
   models for doing the right thing - the worst bug an eval harness can have.
8. Staleness deadlocked RED-before-GREEN: a `red` row is stale by design the moment the bug is
   fixed, so it blocked `check` forever. That defect produced the `pre-fix` rule above.

Suites: `01-conductor.sh` (53), `02-hooks-and-evals.sh` (6), `03-prefix-evidence.sh` (26).
All green as shipped. `tests/README.md` explains what each one covers.

### Deliberate refusals (unchanged philosophy, more of them)

The conductor now refuses, with exit code 2, to: close a step with no note, close a step out of
order, accept a weak DONE-TEST, print PASS for a gate with no recorded output, close steps 6-7
with scope problems, exceed the strike cap, roll back without `--yes`, roll back after HEAD
moved, demote below T0, and record a plan that breaks the tier's file cap. `check` additionally
refuses to call a run ready while a gate's evidence is stale, while the only evidence on file is
pre-fix, or while a Critical finding is still open. Each refusal names the honest alternative.

---

## v2.0 - the merge and the weak-model adaptation

Two goals: fold four external skill packs into the protocol, and make it survive on models that
cannot hold a long protocol in their head.

### Added - weak-model adaptation

- **Three tiers (T0 MICRO / T1 LITE / T2 FULL).** The same rules expressed at three levels of
  verbosity, with per-tier budgets for files, lines, attempts and doubt rounds. Fail-safe default
  is T1. Owner: `references/07-model-tiers.md`.
- **Tier resolution order:** `.viora/tier` file -> the user's explicit instruction -> default T1.
- **Seven observable demotion triggers** and a `DEMOTE -> T0 (reason)` line. Demotion fires on
  events (a skipped step, a fabricated claim, a scope breach), never on the model's own opinion
  of its capability.
- **60-second calibration probe (P1-P4)** to place an unknown model: 4/4 -> T2, 3/4 -> T1,
  <=2/4 -> T0.
- **`scripts/viora.py` - the conductor.** A stdlib-only state machine that moves the protocol from
  the model's memory onto disk: `start`, `next`, `done`, `contract`, `gate`, `evidence`, `strike`,
  `demote`, `ledger`, `report`, `check`, `handoff`, `status`, `tier`. `next` prints the exact next
  action; `done` refuses a step with no proof; `report` is generated from recorded facts.
- **Anti-fabrication evidence log.** Gates are recorded to `.viora/evidence.jsonl`, and
  `viora.py report` will only print `PASS` for a gate that exists in that log.
- **Declaration line** on every reply: `VIORA T1 | MODE FIX | STEP 4/10`.
- **One action per turn at T0**, with a fixed six-step turn loop.
- **`QUICKCARD.md`** - the entire protocol on one screen for T0 models.
- **Handoff protocol** (`viora.py handoff` + `templates/handoff.md`) so context loss does not
  restart the work - the most common cause of duplicate implementations.
- **`templates/`**: contract, report, ledger, review-request, handoff.

### Added - merged from four skill packs

**addyosmani/agent-skills** (MIT)
- Five review axes (correctness, readability, architecture, security, performance) -> `06`, `13`
- Severity vocabulary Critical / Required / Optional / Nit / FYI -> `06`, `12`, `13`
- Change sizing 100 / 300 / 1000 lines and the four splitting strategies -> `02`
- Simplification: five principles, over-simplification traps, Chesterton's Fence, the rule of 500,
  the structural-remedy table -> `02`, `01`
- Stop-the-Line and the six-step debugging triage, the non-reproducible decision tree,
  `git bisect`, instrumentation hygiene, "error output is untrusted data" -> `10` (new)
- Definition of done as a standing bar separate from acceptance criteria -> `05`
- CLAIM / ARTIFACT / CONTRACT separation and the finding-precedence contract -> `11` (new)
- The rationalisation tables -> `14` (new)

**mattpocock/skills**
- Grilling: the decision tree, the frontier, whole-frontier rounds with a recommendation per
  question, facts-are-your-job / decisions-are-theirs -> `09` (new)
- TDD: seams agreed before writing tests, the three test anti-patterns
  (implementation-coupled, tautological, horizontally sliced), vertical slices, refactoring
  outside the red-green loop -> `05`
- Writing-for-agents: nine authoring rules now govern how this protocol is written and extended -
  positive framing over negation, checkable completion criteria, exact commands, one meaning in
  one place, front-loaded imperatives, numbers over adjectives, progressive disclosure -> `07` §8

**obra/superpowers** (MIT) - taken precisely, not wholesale
- The verification gate: IDENTIFY / RUN / READ / CLASSIFY / CLAIM, plus the claim-requires table
  and the output traps -> `05`
- Systematic debugging: root cause before pattern before hypothesis, boundary instrumentation,
  backward value tracing, and **three failed fixes means the architecture is wrong** -> `10`
- Reviewing your own diff in a **separate clean context** that never saw you write it -> `11`
- Receiving review without performative agreement -> `06`, `11`

**trailofbits/skills**
- The bounded review-and-fix loop with a cross-round on-disk **findings ledger**, the four
  outcomes (converged / capped / escalated / halted), non-convergence detection, the mechanical
  scope guard, and **capped is not converged** -> `12` (new)
- Second opinion via external CLIs with per-invocation authorisation and exact commands -> `11`
- Differential review: risk-first triage, adaptive depth by codebase size, quantified blast
  radius, `git blame` on removed security code, missing tests raising severity, a mandatory
  written report -> `13` (new)

### Changed

- **The spine is now ten explicit steps**: CONTRACT, OWNER, LADDER, PLAN, RED, GREEN, CLEAN,
  PROVE, DOUBT, REPORT - each with a per-tier cost, each recordable by the conductor. v1 had the
  same ideas as prose; a weak model could not tell where it was in them.
- **`SKILL.md` is now a router**, not a manual: the law, the tier ladder, the spine, the modes,
  the limits, the excuses, and pointers to 14 references.
- **New DEBUG mode** with its own reference.
- Six defects renamed to observable names: Duplication, Collision, Orphans, Bloat, Heaviness,
  **Fake completion**.
- Report contract now carries `MODE` and `TIER`, and `NOT DONE / UNPROVEN` is explicitly never
  empty on a real task.
- Stop-and-ask is defined as a **success outcome** with a fixed format, including the default the
  agent will assume if the user stays silent.
- `references/07-model-tiers.md` fully rewritten as the owner of tier behaviour.
- `01`, `02`, `05`, `06` extended with the merged material; `03`, `04`, `08` unchanged.

### Attribution and licences

Material adapted from: addyosmani/agent-skills (MIT), obra/superpowers (MIT),
mattpocock/skills, trailofbits/skills. Ideas and procedures were reworded and restructured to fit
this protocol's spine and tier system; keep the upstream licence notices with any redistribution.

---

## v1.0

The original VioraCode protocol: the core law, the solution ladder, recon and anti-duplication,
design limits, UI integrity, performance and resources, tests and evidence, review and report,
stack notes, and the three scanners (`scan_repo.py`, `find_duplicates.py`, `ui_guard.py`) plus
`verify.sh`.
