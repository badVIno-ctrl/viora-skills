---
name: viora-code-protocol
description: Viora Code Protocol by Viora Studio - the engineering standard for any coding agent (Codex, Antigravity, Cursor, Claude Code, Copilot and others). Use for every code task - writing a feature, fixing a bug, refactoring, reviewing a diff, building or changing UI, or optimizing performance - in any language or framework. Prevents the typical failures of generated code: duplicated logic and second copies of components that overwrite each other, overlapping interfaces and z-index wars, dead or orphaned code, unbounded files and functions, leaks and heavy render loops, and "done" claims with no proof. Provides task-mode routing, an anti-duplication reuse ladder, hard size limits, UI integrity and performance budgets, evidence-based verification gates, a self-review pass, and a fixed report format, plus read-only scanner scripts (scan_repo, find_duplicates, ui_guard, verify).
---

# Viora Code Protocol

*Viora Studio engineering standard. Companion to Viora Design Skills.*

**The law:** ship the smallest, clearest, single-owner change that is *proven* to work by fresh command output.

This protocol is agent-neutral and language-neutral. It overrides your habits, not the repository's own rules. If a repository instruction file (any `AGENTS.md`, `CONTRIBUTING.md`, `.md` convention doc, lint config) conflicts with this protocol, the repository wins - and you say so in the report.

---

## 0. Pick your lane (10 seconds)

| Situation | Lane |
|---|---|
| Smaller / faster model, tight context, or a simple task | **LITE** - execute the 12-step checklist in section 3 literally, in order. Read reference files only when a step says to. |
| Stronger reasoning model, or risky / multi-file / architectural work | **FULL** - run the phases in section 4 and read the reference file each phase names. |

Both lanes pass **the same gates** (section 6). LITE is a shorter path, never permission to skip proof.

Write the lane and mode in your first message: `Lane: LITE | Mode: FIX`.

---

## 1. The six defects this protocol exists to prevent

| Defect | How it shows up | The rule that stops it |
|---|---|---|
| **Duplication** | A second `Modal`, a second `formatDate`, a second config loader; two files doing one job | Phase 2 Recon: search before you write; one concept = one owner |
| **Overlap / collision** | Two interfaces mounted at once, panels stacking, styles cancelling each other, z-index war | Phase 5 UI integrity: one mount root, one layer manager, replace instead of stack |
| **Orphans & dead code** | New file nobody imports; old code left behind "just in case"; unused flags | Phase 4: every new unit is wired on creation; superseded code is deleted in the same change |
| **Bloat** | 900-line files, 120-line functions, 5 levels of nesting, abstractions with one caller | Section 5 hard limits + "no abstraction before the second consumer" |
| **Heaviness** | Re-render on every keystroke, listeners never removed, N+1 queries, work in loops | Phase 6 budgets + teardown pairs |
| **Fake completion** | "Done, it should work now" with no command output; tests never run | Phase 7 iron law: no claim without fresh evidence |

If your change adds any of these, it is not done - regardless of whether the feature appears to work.

---

## 2. Route the task

Classify in one line, then run only what the mode requires.

| Mode | Trigger | Required phases | Required gates |
|---|---|---|---|
| **TRIVIAL** | typo, string, comment, version bump, single obvious line | 1, 4, 7 | lint + the one relevant check |
| **FIX** | something is broken / wrong behavior | 1, 2, 4, 5*, 7, 8 | reproduce first, then full gates |
| **FEATURE** | new behavior | 1, 2, 3, 4, 5*, 6, 7, 8, 9 | full gates + new test |
| **REFACTOR** | same behavior, better structure | 1, 2, 3, 4, 7, 8, 9 | full gates, **behavior must not change** |
| **UI** | any visible surface, component, layout, style | 1, 2, 3, 4, **5**, 6, 7, 8, 9 | full gates + rendered-state check |
| **PERF** | slow, heavy, laggy, memory | 1, 2, **6**, 4, 7, 8, 9 | measure before + after |
| **REVIEW** | judge someone else's diff | 2, 8, 9 | no gates to run; report findings by severity |

`5*` = only if the change touches UI. When unsure between two modes, pick the stricter one.

---

## 3. LITE: the 12-step checklist

Copy this list into your working notes and tick every box. Never tick a box you did not actually do.

```
[ ]  1. RESTATE: goal in one sentence + acceptance check ("done when X does Y") + what must NOT change.
[ ]  2. UNKNOWNS: if a required fact is missing (target file, API shape, expected behavior), ask ONE
         batched question and stop. Never guess a public interface.
[ ]  3. SEARCH BEFORE WRITING: search the repo for the thing you are about to create -
         3 name variants + 2 behavior keywords. Write down `Owner: path:line` for each concept you touch.
         Command: python3 scripts/find_duplicates.py .   (or: grep -rn "<name>" --include=*.* .)
[ ]  4. LADDER: choose the lowest rung that solves it:
         no change -> delete/config -> reuse local code -> platform/stdlib -> installed dependency
         -> new dependency (needs a reason) -> minimal new code. State the rung.
[ ]  5. PLAN FILES: list every file you will touch and why, in one line each. If a new file is needed,
         say which existing file would otherwise have grown past its limit.
[ ]  6. LIMITS: file <= 400 lines, function <= 50 lines, nesting <= 3, params <= 4, no duplicated block
         > 8 lines, no magic values (name them), no nested ternaries.
[ ]  7. IMPLEMENT ONE OWNER: change the existing owner instead of adding a parallel one.
         Delete the code your change replaces. Wire every new unit immediately (import/route/register).
         No drive-by edits outside the plan.
[ ]  8. UI (skip if no UI): mount once; do not stack a second panel over an existing one - replace or
         reuse it; z-index only from the shared token/scale; no `!important`; every listener, timer,
         subscription and observer gets its paired teardown.
[ ]  9. TEST THE CHANGE: for a bug, first write the check that fails for the reported reason;
         for a feature, cover the main path + one boundary. No tests of the framework itself.
[ ] 10. RUN THE GATES and read the output: format/lint, types, tests, build (whatever the repo defines).
         Command: bash scripts/verify.sh .
[ ] 11. SELF-REVIEW THE DIFF line by line: unused code? leftovers? debug prints? duplicated logic?
         anything outside the plan? Anything you cannot justify - delete it.
[ ] 12. REPORT with the template in section 7. Label anything you did not verify as `UNPROVEN`.
```

Stop conditions inside LITE: two failed fix attempts -> switch to FULL phase 8 debugging. Any gate red -> fix or report `BLOCKED`. Never continue past a red gate.

---

## 4. FULL: the phases

### Phase 1 - Contract
Write 5 lines before touching code: **Outcome** (observable), **Acceptance** (command or interaction that proves it), **Protected behavior** (what must keep working), **Non-goals**, **Assumptions** (mark each as verified or guessed). Guessed assumptions about public interfaces must be resolved by reading code, not by inventing.

### Phase 2 - Recon and anti-duplication
Map the territory before adding to it. Establish, in writing, the current owner of every concept you will touch: `Concept -> path:line`. Then apply the Solution Ladder and justify your rung.
Read: `references/01-recon-and-reuse.md`. Tools: `scripts/scan_repo.py`, `scripts/find_duplicates.py`.
**Hard rule:** two implementations of one behavior is a defect, even if both work.

### Phase 3 - Design and limits
Produce a file plan (path -> single responsibility -> why it exists) and freeze the interfaces first: for each unit, what it **consumes** and what it **produces**. Files that change together live together. No new layer, wrapper, event bus, or abstraction until a second real consumer exists.
Read: `references/02-design-and-limits.md`.

### Phase 4 - Implement surgically
One owner per concept. Smallest diff that fully solves the contract. Delete what you supersede. Wire what you create. Keep names boring and explicit. No commented-out code, no `TODO` without an owner note, no placeholder or fake implementation presented as real. If a needed change falls outside the plan, record it as a follow-up instead of silently doing it.
Read: `references/02-design-and-limits.md` (checklist at the end).

### Phase 5 - UI integrity (any visible surface)
One mount root; one owner per surface; new panels replace or extend existing ones instead of covering them; a single layer/z-index scale; no `!important`; class names namespaced to their component; teardown paired with every setup; verify the *rendered* result, not the source.
Read: `references/03-ui-integrity.md`. Tool: `scripts/ui_guard.py`.

### Phase 6 - Performance and resources
Respect the budgets, prevent the known-heavy patterns (work in render, unthrottled events, N+1, unbounded caches, giant lists without virtualization, layout thrash), and pair every allocation with its release. For PERF mode: measure before, measure after, report both numbers.
Read: `references/04-performance-and-resources.md`.

### Phase 7 - Evidence and verification
**Iron law: no completion claim without fresh command output from the current code.** Identify the gates -> run them -> read the full output -> only then claim. A gate you did not run is `UNPROVEN`, never "probably fine".
Read: `references/05-tests-and-evidence.md`. Tool: `scripts/verify.sh`.

### Phase 8 - Self-review (cold pass)
Re-read the complete diff as if a stranger wrote it. Justify every added line. Hunt: duplication, dead code, orphans, magic values, leaks, silent behavior changes, missing error paths, secrets in code, over-abstraction. Apply the six lenses (correctness, simplicity, integration, resources, failure modes, maintainability). Fix what you find before reporting.
Read: `references/06-review-and-report.md`.

### Phase 9 - Report
Use the fixed contract in section 7. Honest verdict, evidence table, deviations, follow-ups. No praise, no filler, no invented certainty.

---

## 5. Hard limits (numbers, not opinions)

| Limit | Value | On exceeding |
|---|---|---|
| File length | 400 lines | split by responsibility, or state why splitting is worse |
| Function / method | 50 lines | extract a named helper next to it |
| Nesting depth | 3 | early returns, guard clauses |
| Parameters | 4 | pass one options object / struct |
| Duplicated block | 8 lines | consolidate into one owner |
| Public interface change | 0 unrequested | ask first |
| New dependency | needs justification | prefer stdlib / installed / local |
| Magic literals | 0 | one named constant, one owner |
| Nested ternaries / clever one-liners | 0 | clarity beats brevity |
| Files touched beyond the plan | 0 | re-plan or record a follow-up |

Limits are guardrails against sprawl, not license to fragment: never split one coherent function into three files just to satisfy a number, and say so if the tradeoff bites.

---

## 6. Gates

Run the repository's own commands - never invent command names. Discover them via `scripts/scan_repo.py`, the package manifest, `Makefile`, or CI config.

| Gate | Passes when |
|---|---|
| Format / lint | clean on touched files, no new warnings, no suppressions added to hide problems |
| Types | no new type errors (a language with types) |
| Tests | the new check fails before the fix and passes after; the existing suite stays green |
| Build | succeeds |
| Runtime check | the actual behavior was exercised (request, script run, or rendered UI) |
| Scanners | `find_duplicates.py` and (for UI) `ui_guard.py` show no new findings caused by your change |

One command for most of it: `bash scripts/verify.sh .`
If the environment cannot run a gate, say `UNPROVEN: <gate> - <reason>`. Never fabricate output. Never delete or weaken a test to make a gate green.

---

## 7. Report contract

```
VERDICT: DELIVERED | NO_CHANGE | BLOCKED
Mode/Lane: FEATURE / FULL
WHAT CHANGED
- path:line - one line per file, why it changed
HOW IT WAS SOLVED
- ladder rung + the owner you extended (or the reason new code was unavoidable)
EVIDENCE
| Gate | Command | Result |
|---|---|---|
| lint | <cmd> | PASS |
| test | <cmd> | PASS (3 added, 41 total) |
DELETED / REPLACED
- what you removed so nothing duplicates it
NOT DONE / UNPROVEN
- explicit list, no hiding
FOLLOW-UPS
- optional, small, concrete
```

`NO_CHANGE` is a valid, respected outcome when the desired behavior already exists. `BLOCKED` beats a guess.

---

## 8. Stuck rules

| Signal | Action |
|---|---|
| 2 failed fix attempts | stop patching; find the root cause (read the error, trace the data, form one hypothesis, test it) |
| 3 failed fix attempts | the design is suspect; state the architectural doubt and ask before continuing |
| The fix needs a `try/catch` around a mystery | you do not understand the failure yet; keep investigating |
| A test fails and you want to change the test | change it only if the test is provably wrong; otherwise the code is wrong |
| Required information is missing | ask one batched question; do not invent an interface |
| The request itself would create duplication | say so, propose the reuse path, then act |

Read `references/07-model-tiers.md` for the escalation ladder and the smaller-model safety rails.

---

## 9. Banned excuses

| Excuse | Reality |
|---|---|
| "It's cleaner to write a fresh component" | it creates a second owner; extend the existing one |
| "I'll keep the old code just in case" | dead code is a bug with a delay; delete it |
| "The tests probably pass" | run them or write `UNPROVEN` |
| "I'll add the abstraction now, we'll need it later" | second consumer first, abstraction after |
| "Higher z-index fixes it" | you started a war; use the layer scale |
| "Small file, limits don't matter" | limits are cheap now, expensive later |
| "The user only asked for the feature" | they asked for working software |
| "I fixed it" (after editing without running anything) | unverified equals unfinished |

---

## 10. Scripts (read-only, stdlib only, no network)

```bash
python3 scripts/scan_repo.py .            # stack, repo commands, entrypoints, oversized files
python3 scripts/find_duplicates.py .      # clones, duplicate symbols, repeated literals
python3 scripts/ui_guard.py . --strict    # mount roots, overlays, z-index, leaks, CSS collisions
bash    scripts/verify.sh .               # runs the repo's own gates, prints an evidence table
bash    scripts/verify.sh . --only lint,test
```

No Python or shell available? Use the fallbacks: `grep -rn "<name>" .` before creating anything, `grep -rn "z-index\|!important\|addEventListener" src/`, and run the repo's gate commands by hand. The protocol stands without the scripts; the scripts only make it fast.

---

## 11. Reference index (read on demand)

| File | Read it when |
|---|---|
| `references/01-recon-and-reuse.md` | before creating any file, component, helper, constant or dependency |
| `references/02-design-and-limits.md` | planning files/interfaces, or a limit is being exceeded |
| `references/03-ui-integrity.md` | any UI work, overlapping panels, styling conflicts, portals |
| `references/04-performance-and-resources.md` | slowness, heaviness, memory, large lists, animations |
| `references/05-tests-and-evidence.md` | deciding what to test, or proving completion |
| `references/06-review-and-report.md` | self-review, reviewing a diff, writing the final report |
| `references/07-model-tiers.md` | choosing LITE/FULL, escalation, being stuck |
| `references/08-stack-notes.md` | stack-specific traps (web/TS, Python, backend, mobile) |
| `templates/contract.md`, `templates/report.md` | copy-paste working notes and final report |
