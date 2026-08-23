# 06 - Self-review, code review and the report

Read before reporting, and whenever the task is to review a change.

**Core rule: review the diff as if a stranger wrote it and you have to maintain it for a year.**

---

## 1. The cold pass (mandatory before any completion claim)

1. Print the full diff of your change and read every line. Not the summary - the lines.
2. For each file, state in one sentence why it changed. A file you cannot justify gets reverted.
3. Run the scanners over the touched area: `python3 scripts/find_duplicates.py .` and, for UI, `python3 scripts/ui_guard.py . --strict`.
4. Hunt these specifically:

```
[ ] duplication      - does this logic now exist twice? did I create a second owner?
[ ] leftovers        - debug prints, commented code, unused imports/vars/params, dead branches
[ ] orphans          - anything created but never imported, registered, routed or reachable
[ ] scope creep       - lines unrelated to the contract; reformatted untouched code
[ ] magic values     - literals that should be named constants with one owner
[ ] silent changes   - behavior I altered that nobody asked for (defaults, ordering, error text)
[ ] error paths      - what happens on empty, null, huge, slow, offline, unauthorized?
[ ] resources        - every listener/timer/observer/connection has its teardown
[ ] secrets          - keys, tokens, internal URLs, personal data in code or logs
[ ] over-abstraction - layers, options, hooks with a single consumer
```

## 2. The six lenses

| Lens | Ask |
|---|---|
| **Correctness** | does it do exactly what the contract says, including boundaries? what input breaks it? |
| **Simplicity** | what can be deleted without losing behavior? is there a shorter path through the existing code? |
| **Integration** | is it wired in? does it match the repo's patterns, naming, folder layout? does it break a caller? |
| **Resources** | new work in hot paths? unbounded growth? extra requests or queries? teardown paired? |
| **Failure modes** | what happens when the network, disk, permission or input fails? is the error visible and actionable? |
| **Maintainability** | can a newcomer change this in six months without archaeology? is the intent obvious from names? |

Rate each finding: **BLOCKER** (broken, unsafe, data loss, duplicate owner), **MAJOR** (will cause bugs or confusion soon), **MINOR** (small clarity/perf issue), **NIT** (taste). Fix every BLOCKER and MAJOR before reporting. List MINOR/NIT as follow-ups instead of silently expanding the diff.

## 3. Reviewing someone else's change

- Read the contract first: what was it supposed to do? Judge against that, not against your preferences.
- Cite `path:line` for every finding, state the concrete consequence, and propose the minimal fix.
- Verify claims by reading the code, not by pattern-matching a name.
- Do not bikeshed formatting a formatter owns. Do not demand abstractions with one consumer.
- Check what is **missing**: tests, teardown, error path, deleted-but-not-deleted old code, docs the repo actually keeps.
- Output: severity-grouped findings, then a verdict - `APPROVE`, `APPROVE WITH FIXES`, or `REJECT` with the blocking reason.

## 4. Receiving a review

- No performative agreement. Skip "you're absolutely right" and evaluate the claim.
- Verify each point against the code before changing anything. If the reviewer is wrong, say so with evidence.
- Ask for clarification on everything ambiguous **before** editing, in one batch.
- Fix the cause, not the symptom, and re-run the gates. A review round is not done until the gates are green again.

## 5. Report contract

Write this and nothing more. No praise, no filler, no restating the request.

```
VERDICT: DELIVERED | NO_CHANGE | BLOCKED
Mode/Lane: FIX / LITE

WHAT CHANGED
- src/lib/format.ts:14 - extended the existing formatter with the compact variant
- src/ui/Report.tsx:88 - uses the formatter instead of its own inline copy

HOW IT WAS SOLVED
- Ladder rung 2 (reuse local). No new file: the owner already existed at src/lib/format.ts.

EVIDENCE
| Gate  | Command           | Result                   |
|-------|-------------------|--------------------------|
| lint  | npm run lint      | PASS                     |
| test  | npm test          | PASS (1 added, 44 total)  |
| build | npm run build     | PASS                     |

DELETED / REPLACED
- removed the duplicate inline date formatting in src/ui/Report.tsx (12 lines)

NOT DONE / UNPROVEN
- visual check in a real browser: UNPROVEN (no browser in this environment)

FOLLOW-UPS
- src/legacy/date.js still has a third copy; consolidating it needs its own change
```

Honesty rules: report the deviation you made, the thing you could not verify, and the thing you broke. A short honest report is worth more than a confident wrong one. `NO_CHANGE` and `BLOCKED` are respected outcomes.

## 6. Final self-check (five questions)

```
1. Does anything in this repo now do the same job twice because of me?
2. Is every line I added justified by the contract?
3. Did I delete what my change replaced?
4. Did I run the gates and read the output?
5. Is every unverified claim labelled UNPROVEN?
```

If any answer is uncomfortable, fix it before you speak.
