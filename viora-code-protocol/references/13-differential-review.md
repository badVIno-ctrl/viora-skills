# 13 - Differential review: judging a diff

REVIEW mode. The subject is a **change**, not a codebase. What matters is what the change
breaks, exposes, or silently removes - and the history behind the lines it deletes.

---

## 1. Principles

1. **Risk first, not size.** A two-line diff removing a bounds check outranks a 400-line rename. Heartbleed was two lines.
2. **Evidence per finding.** `path:line`, a command, or a commit. "This feels fragile" is not a finding.
3. **Depth scaled to the codebase.** Small → read everything. Large → critical paths only, and say so.
4. **Honest coverage.** State what you did *not* look at. A review implying full coverage it did not have is worse than a narrow review.
5. **Written output.** Findings live in a report with severities, not in a paragraph of prose.

---

## 2. Get the range right first

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD~1)
git --no-pager diff --stat "$BASE"..HEAD
git --no-pager diff --name-only "$BASE"..HEAD
git status --porcelain          # uncommitted work counts as part of the change
```

Empty diff → say so and stop. Over ~2000 changed lines → say the review will be partial,
and name the parts you are covering.

---

## 3. Phase 0 - triage every changed file

| Risk | Triggers |
|---|---|
| **HIGH** | auth, permissions, crypto, tokens, secrets, money, external calls, input validation, deletion of user data, migrations, removed checks |
| **MEDIUM** | business logic, state transitions, new public API, caching, concurrency |
| **LOW** | comments, tests, docs, formatting, pure UI copy |

Depth by codebase size:

| Size | Approach |
|---|---|
| < 20 files | read dependencies too, full `git blame` on removed lines |
| 20-200 | one hop of callers, priority on HIGH files |
| 200+ | HIGH files and their direct callers only - and state that limit in the report |

"Just a refactor" is HIGH until proven otherwise: refactors break invariants that nothing
names.

---

## 4. Phase 1 - interrogate the deletions

Removed lines are where reviews earn their keep. Additions announce themselves; deletions
are silent.

```bash
git --no-pager log -S'<removed symbol>' --oneline -- <path>   # when did it arrive, and why
git --no-pager blame -L <start>,<end> <path>                   # what commit owned that line
```

Escalate immediately when a deletion touches a line introduced by a commit whose message
mentions `fix`, `security`, `CVE`, `guard`, `validate`, `overflow`, or a ticket id. **A
removed guard is a re-introduced bug until the author explains why it is unnecessary now.**

Also flag: an access modifier widened (`internal` → `public`, `private` → exported), a
check replaced by a default, a `try` that now swallows, a timeout removed, a validation
moved later than the use.

---

## 5. Phase 2 - the five axes

Every changed file, in this order.

| Axis | Look for |
|---|---|
| **1 Correctness** | matches the contract; empty/null/boundary/huge inputs; error paths, not just the happy path; ordering and concurrency; off-by-one |
| **2 Readability** | names that say what they hold; flow you can follow once; no nested ternaries; would fewer lines do; does each abstraction have ≥2 real callers |
| **3 Architecture** | follows the existing pattern or justifies a new one; module boundaries intact; dependency direction; **does this reduce concepts or just relocate them**; feature logic staying out of shared modules |
| **4 Security** | input validated at the boundary; secrets out of code, logs and history; auth checked where it matters; parameterised queries; output encoded; external data treated as untrusted |
| **5 Performance** | N+1; unbounded loops or fetches; sync work on a hot path; missing pagination; avoidable re-renders; large allocations in loops |

**Test coverage is part of the review, not a separate task.** New behaviour with no test is
a finding, and it *raises* the severity of everything else in that file: nothing is holding
it in place.

---

## 6. Phase 3 - blast radius

Count, do not estimate.

```bash
grep -rn "<changed symbol>" --include='*.*' . | grep -v node_modules | wc -l
grep -rln "<changed symbol>" --include='*.*' . | grep -v node_modules | head -30
```

| Callers | Meaning |
|---|---|
| 0 | is this reachable at all? possibly dead code |
| 1-5 | check each one |
| 6-50 | check the HIGH-risk ones, name the rest |
| 50+ | any behaviour change here is a HIGH finding by itself |

A changed signature, changed default, changed return shape, changed error type, or changed
nullability propagates to every caller. Those callers are part of the diff whether they
appear in it or not.

---

## 7. Phase 4 - adversarial pass (HIGH risk only)

```
ATTACKER:  who can reach this code, with what access?
INPUT:     what is the worst thing they can send?
PATH:      the concrete sequence of calls to abuse it
EFFECT:    what they get - data, money, escalation, denial
BLOCKER:   what stops it today, and is that thing inside this diff?
```

A generic "could be vulnerable to injection" is not a finding. A concrete path is.

---

## 8. Output format

```
REVIEW: <range>  ·  <n> files, +<a> -<b>
COVERAGE: <what was reviewed deeply, what was skimmed, what was skipped>

VERDICT: APPROVE | APPROVE WITH REQUIRED FIXES | REQUEST CHANGES

FINDINGS
Critical  <path:line> <what breaks, and the concrete path to it> -> <the named remedy>
Required  <path:line> <what is wrong> -> <the named remedy>
Optional  <path:line> <suggestion>
Nit       <path:line> <style>
FYI       <path:line> <context>

MISSING TESTS
- <behaviour with no check behind it>

BLAST RADIUS
- <symbol>: <n> callers, <which were checked>

NOT REVIEWED
- <files, paths, or aspects deliberately out of coverage>
```

**Lead with what matters.** One structural problem plus ten nits is a review of one
structural problem. Ordering findings by leverage is part of the job; burying a real defect
under cosmetics is a review failure.

**Propose the move, not just the problem.** "This is complex" leaves the author guessing.
Name the restructuring: replace the conditional chain with a typed dispatch; collapse the
duplicate branches; separate orchestration from logic; move the feature logic out of the
shared module; reuse the canonical helper; make the type boundary explicit; delete the
pass-through wrapper; split the file.

---

## 9. The approval standard

Approve when the change **definitely improves overall code health**, even if it is not how
you would have written it. Perfect does not exist; "not my style" is not a finding. Block
only on Critical and Required.

And do not rubber-stamp: `LGTM` with no evidence of reading helps nobody, and softening a
real defect into "might be a minor concern" is a dishonest review. Quantify where you can -
"this adds ~50ms per row in a list that renders 200" beats "might be slow".

---

## 10. Tier behaviour

| Tier | Review shape |
|---|---|
| **T0** | `--stat` + triage, then the five axes on HIGH files only, one file per turn. Coverage stated plainly. |
| **T1** | full triage, five axes on HIGH and MEDIUM, blast radius counted for changed signatures, deletions blamed. |
| **T2** | all phases including adversarial, plus a second reviewer in clean context (`11-doubt-and-second-opinion.md`). |

---

## 11. Rationalisations

| "..." | Reality |
|---|---|
| "small PR, quick look" | classify by risk, never by size |
| "I know this codebase" | familiarity is what produces blind spots; build the baseline anyway |
| "git history takes too long" | history is where removed guards confess themselves |
| "blast radius is obvious" | transitive callers are never obvious; count them |
| "no tests, not my problem" | missing tests raise the severity of everything else here |
| "just a refactor" | refactors break unnamed invariants; HIGH until proven LOW |
| "I'll explain it in chat" | no written findings means the findings are lost |
