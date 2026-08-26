# 11 - DOUBT: attacking your own work before someone else does

Step 9 exists because the author of a change is the worst reviewer of it. You know what you
*meant*, so you read your intent instead of your code. This file is the owner of that step.

The move is always the same: **separate the claim from the artifact, then attack the
artifact.**

---

## 1. The three inputs

| Name | What it is |
|---|---|
| **CLAIM** | what you believe you achieved ("this fixes the race") |
| **ARTIFACT** | the diff, the file, the plan - the thing that either works or does not |
| **CONTRACT** | the four lines from step 1: goal, done-test, protected, non-goals |

A review receives **ARTIFACT + CONTRACT**. It never receives the CLAIM or your reasoning -
both bias a reviewer toward agreement, which is exactly the thing you are trying to defeat.

Ask for **"find what breaks this under the contract"**, never "is this good?". The second
question has a comfortable answer and no information in it.

---

## 2. T0 - the five questions

Answer all five in one short line each, out loud, before the report:

```
1 Which command output proves this works? (quote it - not from memory)
2 What did I change that nobody asked for?
3 What happens on empty / null / huge / wrong-typed input?
4 Is there now a second place in this repo that does this same thing?
5 What am I about to call done that I never ran?
```

Any uncomfortable answer sends you back to the step that owns it. That is the whole
mechanism: cheap, fixed, unskippable.

---

## 3. T1 - the eight-lens cold pass

Re-read the diff as if a stranger wrote it and you have to sign off. One lens at a time.

| Lens | The question that finds real defects |
|---|---|
| **Correctness** | does it match the contract? edge cases, error paths, off-by-one, ordering, concurrent access |
| **Evidence** | is every claim in my report backed by output in this session? |
| **Ownership** | did I create a second owner of anything - helper, constant, style, route, state? |
| **Scope** | is every changed line traceable to the contract? |
| **Simplicity** | fewer lines possible? does each abstraction have ≥2 real callers? |
| **Structure** | did I bolt a new conditional onto an unrelated flow instead of giving it its own home? |
| **Blast radius** | who else calls what I changed? did I check them? |
| **Residue** | debug prints, dead branches, unused imports, commented code, stale docs |

Write findings down before fixing them. Fixing while reading means you stop reading.

---

## 4. T2 - fresh context and cross-model

### 4.1 Clean-context review

The strongest cheap review: read the diff in a context that never saw you write it.

- Sub-agent available → dispatch one with `templates/review-request.md` filled in. It receives the diff and the contract; you receive only findings. Your own context stays free for the work.
- No sub-agent → do it by hand: `git diff <base>..HEAD > /tmp/review.diff`, then read that file top to bottom as a document, with the contract beside it. Reading the diff is not the same as remembering the edits.

Get the range right first:

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD~1)
git --no-pager diff --stat "$BASE"..HEAD
git --no-pager diff "$BASE"..HEAD > /tmp/viora-review.diff
```

### 4.2 Cross-model second opinion

A different model has different blind spots. Offer it; let the user decide.

**Authorisation rules - each run is its own permission:**

1. Confirm the tool exists (`command -v codex`, `command -v gemini`).
2. Show the exact command you intend to run.
3. Wait for a yes. Every time - the diff, prompt and flags change between runs.
4. Tool missing or erroring → say so plainly and continue with §3/§4.1. Never silently substitute.

```bash
# example shape - confirm before running
git --no-pager diff "$BASE"..HEAD > /tmp/viora-review.diff
{ printf 'Review this diff against the contract below. List only issues that would make it fail. Label each Critical/Required/Optional/Nit.\n\nCONTRACT:\n%s\n\nDIFF:\n' "$(cat .viora/contract.md)"; cat /tmp/viora-review.diff; } > /tmp/viora-prompt.txt
```

Then the CLI the user approved, reading `/tmp/viora-prompt.txt`. When two reviews disagree,
report the disagreement - agreement between models is weak evidence, disagreement is a
pointer to the actual risk.

Skipping cross-model is fine. Skipping it *silently* is not: say `cross-model: skipped (no CLI available)`.

---

## 5. Classifying findings - precedence order, first match wins

A reviewer with less context can be wrong. Deferring to it automatically is the same failure
as ignoring it.

| Class | Meaning | Action |
|---|---|---|
| **1 Contract gap** | flagged because the contract was unclear or incomplete | fix the contract first, then re-classify |
| **2 Valid + actionable** | a real defect under the contract | change the artifact, re-run the gates |
| **3 Valid trade-off** | real, but costs more to fix than to accept | write it in the report under NOT DONE, with the reason |
| **4 Noise** | correct already; the reviewer lacked context | note it, move on - and ask whether the contract should have said it |

Always classify against the **artifact text**, never against your memory of writing it.

---

## 6. Stop conditions - bounded, not recursive

Stop the doubt loop when any is true:

- the next pass returns only nits or already-classified findings
- **3 cycles** are done - escalate rather than grind a fourth
- the user says ship it

Three cycles still surfacing real defects is **information about the change**, not a reason
to keep looping: the change is probably too large. Go back to step 4 and split it. Raising
the cycle cap is not an option.

---

## 7. Receiving review - technical, not social

Feedback arrives from a human, a sub-agent, another model, or CI. Same procedure:

```
1 READ everything before reacting
2 RESTATE the requirement in your own words - or ask
3 VERIFY against this codebase (grep it, run it)
4 EVALUATE: correct for THIS repo, this version, these constraints?
5 RESPOND: technical acknowledgement, or reasoned pushback
6 IMPLEMENT one item at a time, testing each
```

**Any item unclear → clarify before implementing anything.** Items are usually related;
partial understanding produces a partly-wrong change.

**Write the fix, not the flattery.** `Fixed - the join was producing duplicate rows; changed
to a single query in repo.ts:88` carries information. "You're absolutely right!" carries
none, and it costs credibility you need for the next disagreement.

**Push back when** the suggestion breaks existing behaviour, the reviewer lacks context,
it adds an unused feature, it is wrong for this stack or version, or it contradicts a
decision the user already made. Push back with a command output or a `path:line`, not with
tone. Then accept the user's call.

**Wrong about your pushback?** `Checked - you were right, <what I found>. Fixing.` One line,
no ceremony.

---

## 8. Red flags

- a doubt pass that produced zero actionable findings across two cycles where real issues existed - that is validation theatre, not doubt
- passing your reasoning or your claim to the reviewer
- "is this good?" as the review prompt
- treating reviewer output as a verdict without re-reading the code
- looping past 3 cycles without escalating
- re-reviewing an unchanged artifact and expecting new findings
- doubting only after the commit - that is a post-mortem, not a gate
- running an external CLI without checking it exists and getting a yes
