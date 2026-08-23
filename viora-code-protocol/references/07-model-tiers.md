# 07 - Lanes, escalation and getting unstuck

Read when choosing LITE vs FULL, when the task grows, or when you are stuck.

**Goal: the same output quality from a small fast model and from a large reasoning model.** The lanes differ in how much they reason, never in the gates they must pass.

---

## 1. LITE lane (smaller/faster models, simple tasks, tight context)

Rules that replace judgment with procedure:

1. Execute the 12-step checklist in `SKILL.md` **in order**. Announce each step in one short line (`3. searched: no existing csv builder -> new file justified`).
2. **One step at a time.** Never edit several files "in one go" from memory; finish and verify a step, then start the next.
3. Keep the diff small: aim for under ~150 changed lines and under ~5 files. If the task needs more, split it and deliver in parts.
4. Use the scripts instead of guessing: `scan_repo.py` for the map, `find_duplicates.py` before creating anything, `ui_guard.py` for UI, `verify.sh` for proof.
5. Prefer the lowest ladder rung. Reusing an existing function is always safer than writing a new one.
6. Never invent an API, path, flag, column or option name. Read it in the code, or ask.
7. Copy the exact command output into the report. Do not summarize what you did not read.
8. When something surprises you, stop and report instead of improvising.

LITE forbids: multi-file redesigns, new dependencies, schema/migration changes, concurrency work, security-sensitive changes, deleting tests, and "while I was in there" edits. Any of those requires FULL or a human decision.

## 2. FULL lane (stronger models, risky or wide work)

Adds, on top of everything in LITE: written contract, ownership map, file plan with frozen interfaces, deliberate tradeoff notes, the six-lens self-review, and reading the reference files relevant to the phase. Same gates, same report, higher scrutiny.

## 3. Escalate the lane when any of these is true

```
[ ] more than ~5 files or ~300 lines will change
[ ] the change crosses module/service boundaries or touches a shared interface
[ ] data model, migration, or persisted format is involved
[ ] auth, permissions, payments, personal data, or anything destructive
[ ] concurrency, caching, or performance-critical paths
[ ] the requirements are ambiguous, or two readings of the request differ in outcome
[ ] the repo area has no tests and the behavior is hard to verify
[ ] duplicates must be consolidated across many callers
```

Escalation means: switch to FULL, or split the task into reviewable parts, or ask for a decision. It never means "push on and hope".

## 4. The stuck ladder (hard stops, no infinite loops)

| Attempt | Required action |
|---|---|
| 1st failure | read the **actual** error text and the failing line; do not change anything yet |
| 2nd failure | stop patching. Form one written hypothesis about the cause, find the evidence for it, then fix the cause |
| 3rd failure | stop. The design or your model of the system is wrong. Report `BLOCKED` with: what you tried, what the errors said, your best hypothesis, and the decision you need |

Hard anti-loop rules:
- Same error twice means change the **approach**, not the syntax.
- Never rewrite a whole file from scratch to escape a bug you have not understood.
- Never wrap a mystery in `try/catch`, `except: pass`, `|| true`, `--force`, `--no-verify` or a retry to make it quiet.
- Never disable a check, test or type to move forward.
- Never keep two candidate implementations "until one works" - that is how duplicates are born.

## 5. Context economy (why weak models degrade, and how not to)

- Read what the ownership map points at, not the whole repository.
- Do not re-read a file you already read in this task; keep the facts in your notes.
- Keep one visible working-notes block: contract, ownership map, file plan, checklist state, evidence collected. It is your memory.
- Long output beats no output: state findings as you go so a restart can resume.

## 6. Handoff format (session ends, or work passes on)

```
CONTRACT: <goal + acceptance>
DONE: <steps completed, with file:line and evidence>
NEXT: <the exact next step>
OPEN QUESTIONS: <decisions needed>
RISKS: <what could be broken, what is UNPROVEN>
```

A handoff without the evidence table is not a handoff.

## 7. Before you say "done", answer these

```
1. Which rung of the ladder did I use, and why not a lower one?
2. What did I delete?
3. Which command proves it works, and what did it print?
4. What did I not verify?
5. If a teammate opened this diff, what would they ask me first? Answer that in the report.
```
