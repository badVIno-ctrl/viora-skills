---
name: viora-code-protocol
description: Universal engineering protocol for AI coding agents (Codex, Claude Code, Cursor, Windsurf, Antigravity, Gemini CLI, Copilot, Cline). Ship the smallest, clearest, single-owner change that is proven to work by fresh command output. Use for every code task - fix, feature, refactor, UI, performance, debugging, review. Runs on a three-tier ladder (T0 MICRO / T1 LITE / T2 FULL) so a fast cheap model runs the same gates as a frontier model, with more scaffolding and fewer judgment calls.
---

# VioraCode Protocol

**The law.** Ship the smallest, clearest, single-owner change that is *proven* to work by fresh command output.

**Authority order.** 1. Repository rules (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING`, lint/format config, CI). 2. This protocol. 3. Your own habits. When 1 and 2 disagree, 1 wins and you say so in one line.

**Two failures cause every bad diff:** guessing instead of reading, and claiming instead of proving. Every rule below kills one of them.

---

## 0. Set your tier - first action, one line

A tier is *how much scaffolding you need*, not how smart you are. **The gates are identical at every tier.** Only the amount of judgment changes.

| Tier | Fits | How it runs |
|---|---|---|
| **T0 MICRO** | fast/cheap/small models (Gemini Flash class, 8-30B local models), and any model deep into a long session | one action per reply, one file per change, fill-in templates, scripts make the decisions |
| **T1 LITE** | mid-tier models, new but fast models | the 10-step spine, short judgment calls, no sub-agents |
| **T2 FULL** | frontier models with room to think | phases, sub-agent review, cross-model doubt |

**Choose in this order. First match wins.**

1. A `.viora/tier` file exists in the repo → use the word inside it.
2. The user named a tier → use it.
3. Neither → use **T1**.

T1 is the safe default because it is *cheap to be over-scaffolded* and *expensive to be under-scaffolded*.

**Demote one tier the moment any of these is true.** These are observable facts, not self-assessment:

- a gate failed twice in a row on this task
- you touched a file that was not in your PLAN
- you wrote a sentence claiming a result you had not run
- you cannot say which step number you are on
- this is your 15th reply on one task

Demoting is a **win**: T0 finishes tasks, and T2 held badly loses them. Say `DEMOTE -> T0 (reason)` and continue from the current step.

**Every reply opens with this line:**

```
VIORA T1 | MODE FIX | STEP 4/10
```

That single line is the cheapest defence against losing the thread mid-task.

→ Tier rails, the 60-second calibration probe, and the T0 hard stops: `references/07-model-tiers.md`

---

## 1. The spine - ten steps, one owner each

Every task runs these ten steps in order. The tier decides how expensive each one is, never whether it happens.

| # | Step | Output that proves it happened | T0 | T1 | T2 |
|---|---|---|---|---|---|
| 1 | **CONTRACT** | goal, done-test, protected, non-goals | fill template | 5 lines | + GRILL rounds |
| 2 | **OWNER** | `Owner: path:line` for the behaviour, or `Owner: NONE` | run script, paste | script + 3 greps | full ownership map |
| 3 | **LADDER** | the rung you chose and why rung-below fails | pick from list | 1 line | 1 line + rejected rungs |
| 4 | **PLAN** | exact file list, line budget, frozen interfaces | 1 file only | ≤3 files | full plan |
| 5 | **RED** | a check that fails *now* for the right reason | 1 assert | 1-2 tests | seams confirmed first |
| 6 | **GREEN** | smallest edit inside the owner | 1 file, ≤80 lines | ≤3 files | ≤300 lines |
| 7 | **CLEAN** | same behaviour, fewer concepts | run limits check | simplify pass | simplify + dead-code sweep |
| 8 | **PROVE** | fresh gate output, pasted verbatim | `verify.sh` | `verify.sh` | `verify.sh` + runtime check |
| 9 | **DOUBT** | findings from a hostile re-read | 5 fixed questions | 8-lens cold pass | clean-context reviewer / second opinion |
| 10 | **REPORT** | the fixed report contract | template | template | template |

**RED before GREEN.** A change you never watched fail is a change you cannot prove works. If the stack has no test runner, RED is a command whose output changes: a failing `curl`, a script that prints the wrong number, a log line that is missing. → `references/05-tests-and-evidence.md`

**One owner.** Before you create a file, function, component, constant or route, you have already found who owns that behaviour. Two owners of one concept is the most expensive defect an agent produces. → `references/01-recon-and-reuse.md`

---

## 2. Modes - which steps are mandatory

Name the mode in your header line. It sets the floor, and you may always do more.

| Mode | Trigger | Mandatory steps | Extra reference |
|---|---|---|---|
| **TRIVIAL** | typo, string, comment, version bump; ≤5 lines, no logic | 1, 6, 8, 10 | - |
| **FIX** | something behaves wrong | all ten; RED reproduces the bug | `10-debugging.md` |
| **FEATURE** | new behaviour | all ten | `02-design-and-limits.md` |
| **REFACTOR** | same behaviour, better shape | all ten; RED = existing suite green before *and* after | `02`, `12` |
| **UI** | anything a user sees | all ten + UI guard | `03-ui-integrity.md` |
| **PERF** | speed, memory, size | all ten; RED = a measurement, before/after in one table | `04-performance-and-resources.md` |
| **REVIEW** | judge a diff you or another agent wrote | 1, 2, 9, 10 | `13-differential-review.md` |
| **DEBUG** | you are lost, not yet fixing | 1, 2, 5 then re-enter FIX | `10-debugging.md` |

---

## 3. The six defects this protocol prevents

Named so you can point at them in review.

1. **Duplication** - a second implementation of behaviour that already exists.
2. **Collision** - two owners of one concept fighting: styles, routes, state, ids, z-index.
3. **Orphans** - code nothing reaches: dead branches, unused exports, commented blocks, files nobody imports.
4. **Bloat** - 1000 lines where 100 suffice; abstraction that has one caller; a wrapper that only forwards.
5. **Heaviness** - work in the wrong place: N+1 queries, unbounded loops, re-renders, sync work on a hot path.
6. **Fake completion** - "done", "fixed", "should work" with no fresh command output behind it.

---

## 4. Hard limits - checkable, not aesthetic

Break one only by naming it in the report with the reason.

| Limit | Value |
|---|---|
| file length | ≤400 lines (≥1000 is a decomposition task, not a diff) |
| function length | ≤50 lines |
| nesting depth | ≤3 |
| parameters | ≤4 (more → one options object) |
| duplicated block | ≤8 lines before it becomes one owner |
| changed lines per diff | T0 ≤80 · T1 ≤300 · T2 ≤300, then split |
| files beyond PLAN | 0 |
| unrequested public interface changes | 0 |
| magic literals | 0 (name it or make it a constant) |
| nested ternaries | 0 |
| new dependencies | 0 without an explicit ask |

**Change sizing.** ~100 changed lines reviews well. ~300 is acceptable for one logical change. ~1000 means split it: stack it, split by file group, build the shared layer first, or slice it vertically. Refactor and feature in one diff is two diffs. → `references/02-design-and-limits.md`

---

## 5. Gates and the iron law of evidence

```
NO COMPLETION CLAIM WITHOUT FRESH COMMAND OUTPUT IN THIS REPLY.
```

If you did not run it in this reply, you have not proven it. "Should pass", "looks right", "I'm confident" are all the same sentence: unproven.

**The gate function, every time, before any positive statement:**

1. **Name** the command that would prove this claim.
2. **Run** it, whole, fresh.
3. **Read** the exit code and the failure count.
4. **Compare** output to claim.
5. **Then** speak - with the output attached.

One command runs the repo's own gates and prints a pasteable evidence table:

```bash
bash scripts/verify.sh .                       # format, lint, types, test, build
bash scripts/verify.sh . --only lint,test      # narrow while iterating
bash scripts/verify.sh . --list                # show what it would run
```

A gate that did not run is written `SKIP` and appears under **UNPROVEN** in the report. Silence is not a pass.

| Claim | Only this proves it |
|---|---|
| tests pass | test command output, 0 failures, this reply |
| types clean | typechecker exit 0 |
| build works | build command exit 0 (a clean linter proves nothing about compilation) |
| bug fixed | the original failing symptom now passes |
| regression test works | it failed before the fix and passes after |
| refactor safe | the same suite green before and after |
| sub-agent finished | the diff, read by you |

→ `references/05-tests-and-evidence.md`

---

## 6. When you are stuck - count, then change kind

Attempts are counted, and the count changes what you are allowed to do next.

| Attempt | Required move |
|---|---|
| 1st failure | read the whole error, top to bottom. The fix is usually quoted in it. |
| 2nd failure | stop editing. Write the root cause in one sentence: "X happens because Y." Cannot? You are missing information - go read, or ask. |
| 3rd failure | stop. The shape is wrong, not the line. Report `BLOCKED` with: what you tried (3 items), what you learned, the two options you see, and the one question that unblocks you. |

**Never** try fix #4 on the same theory. Three failures that each reveal a new problem elsewhere is an architecture signal - escalate it as one.

**Anti-loop rules.** The same command twice with the same output is a signal, not a retry. A file opened three times means you are searching without a query - go back to step 2. Two identical replies mean you are stalling - report state and ask.

**STOP-AND-ASK is a success, not a failure.** One batched question that saves a wrong 300-line diff is the highest-value thing you can produce. Format:

```
BLOCKED ON: <one sentence>
I can proceed if you answer:
Q1 <question> - my recommendation: <answer>
Q2 <question> - my recommendation: <answer>
Otherwise I will assume Q1=<default>, Q2=<default> and continue.
```

→ `references/09-clarify-and-grill.md`

---

## 7. Banned excuses

When one of these sentences forms in your output, the sentence is the bug.

| You are about to say | What is actually true |
|---|---|
| "I'll add tests later" | later never arrives. RED comes before GREEN or the change is unproven. |
| "Should work now" | run it. Confidence is not evidence. |
| "Tests pass" (not run in this reply) | that is a memory, not a result. |
| "Simpler to write a new one" | cheaper for you to type, more expensive for everyone to own. Find the owner. |
| "I'll clean it up later" | the diff is the only cleanup window that exists. |
| "It's just a small addition to this file" | small diffs still push files past a healthy size and bolt branches onto unrelated flows. |
| "The linter passed" | a linter is not a compiler and not a test. |
| "It works on my machine" | name the machine it must work on and run it there. |
| "This test is flaky, ignore it" | flakiness hides real bugs. Explain the mechanism or fix it. |
| "I know what the bug is" | you are right ~70% of the time; the other 30% costs hours. Reproduce first. |
| "Just this once" | the exception is the failure mode. |
| "AI-generated code is probably fine" | it needs more scrutiny, not less: confident and plausible even when wrong. |

→ Full table with rebuttals for every source skill: `references/14-rationalizations.md`

---

## 8. Report contract - the only accepted ending

```
VERDICT: DELIVERED | NO_CHANGE | BLOCKED
MODE: <mode> | TIER: <T0|T1|T2>

WHAT CHANGED
- path:line - one line, what and why

HOW IT WAS SOLVED
- ladder rung + the owner you extended

EVIDENCE
| Gate | Command | Result |
|---|---|---|
| test | `<cmd>` | PASS 34/34 |

DELETED / REPLACED
- what is gone, and what took over

NOT DONE / UNPROVEN
- every SKIP gate, every assumption, every deferred item

FOLLOW-UPS
- smallest next step, or "none"
```

`NOT DONE / UNPROVEN` is never empty on a real task. An empty one means you did not look. → `references/06-review-and-report.md`

---

## 9. Scripts - deterministic answers instead of guesses

```bash
python3 scripts/viora.py doctor                                     # is this repo usable? what can be proven here?
python3 scripts/viora.py start --mode FIX --tier T1 --task "..."   # open the run
python3 scripts/viora.py next                                      # print the exact next step
python3 scripts/viora.py done 2 --note "Owner: src/auth.ts:140"     # advance with proof
python3 scripts/viora.py plan --files src/a.ts --lines 60           # record the plan the machine holds you to
python3 scripts/viora.py checkpoint --label "before GREEN"          # one-command undo point
python3 scripts/viora.py scope                                      # real diff vs the plan and the budget
python3 scripts/viora.py gate                                      # run gates, record fingerprinted evidence
python3 scripts/viora.py report                                     # emit the report from recorded facts
python3 scripts/viora.py check                                      # audit: what did I skip, what went stale?

python3 scripts/scan_repo.py .              # stack, real commands, rules files, big files
python3 scripts/find_duplicates.py . --top 15   # clones, duplicate symbols, repeated literals
python3 scripts/ui_guard.py . --strict      # mount roots, z-index wars, listener leaks, class collisions
bash    scripts/verify.sh .                 # the repo's own gates + evidence table
```

`viora.py` is the conductor: it holds the step, counts failed attempts, keeps the findings ledger, and refuses to print a PASS that has no recorded command output. **At T0, run it every turn and do exactly what it prints.**

### Three things the machine enforces, so you do not have to remember them

**1. Evidence is bound to the code it proved.** Every gate row is stamped with a fingerprint of the working tree. Edit anything afterwards and that row becomes `STALE`. `check` fails, and `report` prints the row as STALE and counts it into UNPROVEN. So the rule "rerun the gates after your last edit" is no longer a rule you can forget - it is arithmetic. There is exactly one honest response to a stale row: run `gate` again. Two refinements keep this from becoming a nuisance: only the newest row per gate counts (rerunning supersedes, it does not pile up), and rows named `red`, `repro`, `baseline` or `before` are shown as `pre-fix` rather than STALE - they describe the tree *before* the fix, which is the whole point of them. A run holding *only* pre-fix rows is refused outright: a reproduction is not a proof of repair.

**2. Scope is measured from git, not from memory.** `plan` records the files and the line budget; `scope` compares them to the real diff. `done 6` and `done 7` refuse while scope has problems. Widening the plan is allowed and honest - `plan --files <the real list> --force` - and it leaves a record. Silently touching a fourth file does not.

**3. Undo is one command.** `checkpoint` before you edit, `rollback --yes` when a hypothesis dies. This is what makes "stop after two failed attempts" survivable instead of expensive: you hand back a clean tree with two recorded dead ends, not a tree full of half-reverted guesses.

No scripts available? Use the grep fallbacks in `references/01-recon-and-reuse.md`. Reconnaissance is never skipped, only done more slowly.

---

## 10. Reference index - read on demand, not upfront

| Read this | When |
|---|---|
| `07-model-tiers.md` | always, once - tier rails, T0 turn loop, calibration probe |
| `01-recon-and-reuse.md` | step 2-3: finding the owner, the solution ladder, grep fallbacks |
| `02-design-and-limits.md` | step 4, 7: file plans, frozen interfaces, simplification, splitting |
| `03-ui-integrity.md` | any visible change |
| `04-performance-and-resources.md` | PERF mode, or any hot path |
| `05-tests-and-evidence.md` | step 5, 8: seams, RED-GREEN, what to test, evidence rules |
| `06-review-and-report.md` | step 9-10: five-axis review, severity labels, report contract |
| `08-stack-notes.md` | stack-specific traps (TS, React, Python, Go, Rust, SQL) |
| `09-clarify-and-grill.md` | the contract is ambiguous - frontier rounds, batched questions |
| `10-debugging.md` | FIX/DEBUG mode - reproduce, localise, reduce, root cause, guard |
| `11-doubt-and-second-opinion.md` | step 9 - hostile self-review, clean context, cross-model check |
| `12-review-loop-and-ledger.md` | autonomous "review and fix until clean" runs, findings ledger |
| `13-differential-review.md` | REVIEW mode - risk-first diff review, blast radius, git history |
| `14-rationalizations.md` | you are about to explain why a step does not apply |

**Templates:** `templates/contract.md` · `templates/report.md` · `templates/ledger.md` · `templates/review-request.md` · `templates/handoff.md`

### Worked runs - imitate these before you improvise

If you are a fast or small model, **read one of these first**. A transcript of a correct run teaches more than a rule does, because you can copy its shape directly.

| Read this | It shows |
|---|---|
| `examples/01-t0-fix-full-run.md` | a complete T0 FIX, ten turns, including gates going STALE after a one-word edit and being rerun |
| `examples/02-blocked-and-honest.md` | a vague request answered with one batched round of questions, then two dead hypotheses, a rollback, and a BLOCKED report with 0 files changed |
| `examples/03-review-differential.md` | REVIEW mode: `git merge-base`, blast radius, `git log -S` on a suspicious constant, and the finding that lives in a file the diff never touches |
| `examples/04-debug-with-demotion.md` | DEBUG mode: reproducing a flake as a number, a self-demotion T1 -> T0 after scope creep, and probabilistic proof reported as probabilistic |

**Measuring instead of hoping:** `evals/` contains six fixtures, a rubric and a scorer. It answers one question about the model you are running - *does this protocol actually change its behaviour?* - and turns the answer into a number you can use to pick a tier. Start at `evals/README.md`.

**Proving the protocol itself:** `tests/` holds 85 assertions that drive the real conductor, the real hook and the real grader inside throwaway repos - `bash tests/run-all.sh`, no network, no dependencies. Every refusal promised on this page is asserted there. Writing those tests found eight defects before release, all of them the kind that would have made a report mislead; `tests/README.md` lists them.

**Outside the chat:** `hooks/pre-commit` blocks a commit whose run is not ready (unfinished steps, stale evidence, out-of-plan files, open Critical findings), and `ci/viora.yml` enforces gates, change size and report honesty on pull requests. These are the only parts of the protocol that work when the agent forgets it exists. → `INSTALL.md`
