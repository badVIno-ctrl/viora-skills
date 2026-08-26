# 06 - Self-review, code review and the report

Read before reporting, and whenever the task is to review a change.

**Core rule: review the diff as if a stranger wrote it and you have to maintain it for a year.**

For reviewing someone else's diff in depth, use `13-differential-review.md`. For attacking your
own work, `11-doubt-and-second-opinion.md`. This file owns the self-review sweep and the report.

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
[ ] scope creep      - lines unrelated to the contract; reformatted untouched code
[ ] magic values     - literals that should be named constants with one owner
[ ] silent changes   - behaviour I altered that nobody asked for (defaults, ordering, error text)
[ ] error paths      - what happens on empty, null, huge, slow, offline, unauthorized?
[ ] resources        - every listener/timer/observer/connection has its teardown
[ ] secrets          - keys, tokens, internal URLs, personal data in code or logs
[ ] over-abstraction - layers, options, hooks with a single consumer
[ ] stale docs       - comments, READMEs or types my change just made false
```

At **T0** this collapses to the five DOUBT questions in `11-doubt-and-second-opinion.md`. Five
answered honestly beats twelve skimmed.

## 2. The five axes

Every changed file, in this order. The order matters: a correctness defect outranks every style
remark, and finding it after twenty nits wastes both passes.

| Axis | Ask |
|---|---|
| **1 Correctness** | does it do exactly what the contract says, including boundaries? what input breaks it? error paths, ordering, concurrent access, off-by-one? |
| **2 Readability** | can it be followed in one read? do names say what they hold? nested ternaries, dead branches, clever one-liners? would fewer concepts do? |
| **3 Architecture** | one owner per concept? does it follow the existing pattern or justify a new one? are module boundaries and dependency direction intact? is feature logic staying out of shared modules? |
| **4 Security** | input validated at the boundary? secrets out of code, logs and history? auth checked where it matters? parameterised queries, encoded output, external data treated as untrusted? |
| **5 Performance** | N+1? unbounded loops or fetches? sync work on a hot path? missing pagination? avoidable re-renders? allocations in loops? |

Plus two that apply to the change as a whole: **is anything missing** (test, teardown, error
path, migration, doc) and **is anything unproven**.

## 3. Severity - one vocabulary everywhere

| Label | Meaning | Action |
|---|---|---|
| **Critical** | security, data loss, broken behaviour | must fix now; blocks the report |
| **Required** | a real defect under the contract | must fix before claiming done |
| **Optional** | worth considering; author decides | note it, decide, say what you decided |
| **Nit** | style or taste, safely ignorable | mark it as such, do not expand the diff for it |
| **FYI** | context for later | follow-ups |

Fix every Critical and Required before reporting. Everything else goes to FOLLOW-UPS rather than
into a growing diff. **Label nits as nits** - an unlabelled nit reads as a demand and buries the
finding that mattered.

## 4. Reviewing someone else's change

- Read the contract first: what was it supposed to do? Judge against that, not against your preferences.
- Cite `path:line` for every finding, state the concrete consequence, and propose the minimal fix - the named restructuring, not "this is complex".
- Verify claims by reading the code, not by pattern-matching a name.
- Quantify where you can: "adds ~50ms per row on a 200-row list" beats "might be slow".
- Do not bikeshed formatting a formatter owns. Do not demand abstractions with one consumer.
- Check what is **missing**: tests, teardown, error path, deleted-but-not-deleted old code, docs the repo keeps.
- **Approve when the change definitely improves code health**, even if it is not how you would have written it. Perfect does not exist; "not my style" is not a finding.
- Output: severity-grouped findings, a coverage statement, then a verdict - `APPROVE`, `APPROVE WITH REQUIRED FIXES`, or `REQUEST CHANGES` with the blocking reason.

## 5. Receiving a review

- **No performative agreement.** Not "you're absolutely right", not "great catch", not gratitude. Write the finding and the fix: `Fixed - the join produced duplicate rows; single query now, repo.ts:88`.
- Read everything before reacting. Verify each point against this codebase before changing anything.
- **Clarify every ambiguous item before implementing any of them** - items are usually related, and partial understanding produces a partly-wrong change.
- Push back when the suggestion breaks existing behaviour, adds an unused feature, is wrong for this stack or version, or contradicts a decision the user already made. Push back with output or a `path:line`, then accept the user's call.
- Fix the cause, not the symptom, one item at a time, re-running the gates. A review round is not done until the gates are green again.

## 6. Report contract

Write this and nothing more. No praise, no filler, no restating the request.

```
VERDICT: DELIVERED | NO_CHANGE | BLOCKED
MODE: FIX | TIER: T1

WHAT CHANGED
- src/lib/format.ts:14 - extended the existing formatter with the compact variant
- src/ui/Report.tsx:88 - uses the formatter instead of its own inline copy

HOW IT WAS SOLVED
- Owner: src/lib/format.ts:14. Ladder rung 2 (reuse local); rung 1 fails - no flag exists.

EVIDENCE
| Gate  | Command           | Result                   |
|-------|-------------------|--------------------------|
| lint  | npm run lint      | PASS                     |
| test  | npm test          | PASS (1 added, 44 total) |
| build | npm run build     | PASS                     |

DELETED / REPLACED
- removed the duplicate inline date formatting in src/ui/Report.tsx (12 lines)

NOT DONE / UNPROVEN
- visual check in a real browser: UNPROVEN (no browser in this environment)
- assumed dates are always UTC; if not, format.ts:22 needs a timezone argument

FOLLOW-UPS
- src/legacy/date.js still has a third copy; consolidating it needs its own change
```

Generate it from what was recorded, not from memory:

```bash
python3 scripts/viora.py report      # builds the skeleton from .viora/state.json + evidence.jsonl
```

**NOT DONE / UNPROVEN is never empty on a real task.** Every task has an assumption, an
environment limit, or an untested path. An empty section means you did not look, and it is the
single most reliable sign of fake completion.

Honesty rules: report the deviation you made, the thing you could not verify, and the thing you
broke. A short honest report is worth more than a confident wrong one. `NO_CHANGE` and `BLOCKED`
are respected outcomes, and `BLOCKED` delivered early is cheaper than a wrong change delivered
confidently.

## 7. When you are blocked

```
BLOCKED ON: <the one decision you cannot make yourself>

Q1 <question> - my recommendation: <answer + one line of reasoning>
Q2 <question> - my recommendation: <answer + one line of reasoning>

WHAT I DID ANYWAY: <recon, reproduction, findings - the work that survives either answer>
DEFAULT IF YOU DO NOT REPLY: <what you will assume, so silence is still progress>
```

A question with a recommendation costs the user five seconds. A wrong 300-line diff costs an
hour of review and a rollback.

## 8. Final self-check (five questions)

```
1 Does anything in this repo now do the same job twice because of me?
2 Is every line I added justified by the contract?
3 Did I delete what my change replaced?
4 Did I run the gates and read the output?
5 Is every unverified claim labelled UNPROVEN?
```

If any answer is uncomfortable, fix it before you speak.
