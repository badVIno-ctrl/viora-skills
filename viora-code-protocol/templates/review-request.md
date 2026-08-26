# REVIEW REQUEST template

What you hand to a reviewer: a sub-agent, another model, or your own eyes in a clean context.

**The reviewer receives ARTIFACT + CONTRACT. It never receives your claim or your reasoning** -
both bias it toward agreement, which defeats the entire point.

---

## The block

```
TASK: Review this diff and report only what would make it FAIL under the contract below.
      Do not comment on style unless it hides a defect. Do not summarise the diff back to me.
      Label each finding Critical / Required / Optional / Nit / FYI, with path:line.

CONTRACT
GOAL:      <...>
DONE-TEST: <...>
PROTECTED: <...>
NON-GOALS: <...>

REPOSITORY FACTS THE REVIEWER NEEDS
- stack / versions: <...>
- the gates this repo defines: <...>
- conventions that matter here: <...>

DIFF
<the output of: git --no-pager diff BASE..HEAD>

CHECK SPECIFICALLY
1 correctness against the contract, including boundaries and error paths
2 anything changed that the contract did not ask for
3 a second owner created for something this repo already has
4 security: input validation, secrets, auth, injection, untrusted data
5 missing tests for the new behaviour
6 callers of every changed signature
```

---

## Getting the range right

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD~1)
git --no-pager diff --stat "$BASE"..HEAD
git --no-pager diff "$BASE"..HEAD > /tmp/viora-review.diff
```

Over ~2000 changed lines: say the review will be partial and name which files you are covering.

---

## Rules

1. **Never include session history.** Craft the context deliberately: a reviewer that saw you
   write the code inherits your blind spots.
2. **Never include the claim.** "I fixed the race condition" turns a review into a confirmation.
3. **Ask what fails, not whether it is good.** "Is this good?" has a comfortable answer and no
   information in it.
4. **Include the versions.** A review against the wrong framework version generates confident
   wrong findings.
5. **One external CLI call needs one explicit yes.** Show the exact command first; every run has
   a different diff and prompt, so every run needs its own permission.

---

## Cross-model second opinion

```bash
command -v codex   || echo "codex not installed"
command -v gemini  || echo "gemini not installed"

# build the prompt file, show it, get a yes, then run the approved command
{ printf 'Review this diff against the contract. List only issues that would make it fail. Label each Critical/Required/Optional/Nit.\n\nCONTRACT:\n%s\n\nDIFF:\n' "$(cat .viora/contract.md)"; cat /tmp/viora-review.diff; } > /tmp/viora-prompt.txt
```

Tool missing or erroring: say so plainly and fall back to the eight-lens cold pass. Never
substitute silently, and never report a review that did not happen.

Two reviewers disagreeing is **more** informative than two agreeing - report the disagreement
rather than averaging it away.

---

## Handling what comes back

Classify every finding, first match wins:

| Class | Meaning | Action |
|---|---|---|
| 1 Contract gap | flagged because the contract was unclear | fix the contract, re-classify |
| 2 Valid + actionable | a real defect | fix it, re-run the gates |
| 3 Valid trade-off | real but costs more to fix than to accept | report it under NOT DONE, with the reason |
| 4 Noise | already correct; reviewer lacked context | note it, move on |

Classify against the **code**, not against your memory of writing it. And write the fix, not the
flattery: no "you're absolutely right", no thanks, no praise.
