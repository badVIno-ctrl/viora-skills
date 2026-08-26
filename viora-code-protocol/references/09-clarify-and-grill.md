# 09 - Clarify and GRILL: closing the contract before writing code

The most expensive diff is a correct implementation of the wrong requirement. This file
turns step 1 (CONTRACT) from "ask if unclear" into a procedure that terminates.

---

## 1. The CONTRACT is four lines

```
GOAL:      <one sentence: what the user can do afterwards that they cannot do now>
DONE-TEST: <the exact command, request, or click that proves it - not an adjective>
PROTECTED: <behaviour, files, interfaces that must keep working unchanged>
NON-GOALS: <the adjacent things you are deliberately not touching>
```

A DONE-TEST like "the login works properly" is not a done-test. `curl -s localhost:3000/api/login -d '{...}' | jq .token` is. Write the second kind.

Restate the contract in your own words before step 4. A restatement that drifts from the
request is the cheapest bug you will ever catch.

---

## 2. When to GRILL

Grill when the answer to any of these is "I would be guessing":

- What happens in the empty / first-run / zero-items case?
- Who is allowed to do this?
- What should happen when it fails - retry, error, silent default?
- Does existing data need to migrate?
- Is this replacing something, or living beside it?
- Which of two existing patterns in this repo should it follow?

Skip the grill for TRIVIAL mode, and for tasks where the request already contains the
done-test.

---

## 3. The design tree and the frontier

Decisions hang off other decisions. Picture the task as a tree: a choice at the top opens
new choices below it, and closes others entirely.

**The frontier** is every decision whose prerequisites are already settled - the questions
you can ask *now* without guessing at an answer you have not heard yet.

Work in **rounds**:

1. Compute the frontier.
2. Ask the whole frontier in **one** message, numbered, each with your recommended answer.
3. Stop. Wait.
4. The answers settle those branches and push the frontier outward. Recompute. Ask the next round.

A question whose answer depends on another question in this round belongs to the *next*
round. Asking it now forces the user to answer twice.

**Round format:**

```
ROUND 1 - <n> open decisions

Q1 <short title>: <the question, with the concrete options>
-> recommend: <your answer, and the one-line reason>

Q2 <short title>: <the question>
-> recommend: <your answer, and the one-line reason>

If you would rather I just proceed: I will use every recommendation above.
```

Always carry the recommendation. It converts a blocking question into an approval, which
costs the user one word instead of a paragraph.

**Finding facts is your job. Deciding is theirs.** When a frontier question needs a fact
from the repo (which pattern exists, what the schema is, whether a helper is already
there), go read it. Ask only what genuinely requires the user's preference or authority.

The grill ends when the frontier is empty: no branch left silently assumed. Then write the
contract and start step 2.

---

## 4. Tier behaviour

| Tier | Grill shape |
|---|---|
| **T0** | one round, at most 3 questions, each with a recommendation and a stated default. Then proceed on the defaults if the user is absent. |
| **T1** | one or two rounds, up to 5 questions each. |
| **T2** | rounds until the frontier is empty. Dispatch exploration for facts in parallel with asking the rest of the frontier. |

At T0, never let the grill become the task. Three questions, then move.

---

## 5. Assumption surfacing - the non-blocking alternative

When the user is unavailable, or the question is small, do not stall. Write the assumptions
down where they can be corrected, and proceed:

```
ASSUMPTIONS (correct any of these and I will redo that part):
1 <assumption> - because <evidence in the repo>
2 <assumption> - because <evidence in the repo>
```

Every assumption you proceed on appears again in the report under NOT DONE / UNPROVEN.
That is the contract: you may assume, and you may not hide the assumption.

---

## 6. Conflict handling

When two sources in the repo disagree - code vs docs, test vs implementation, two config
files - stop. Do not average them.

```
CONFLICT
A: <source> says <x>   (path:line)
B: <source> says <y>   (path:line)
EFFECT: <what the choice changes>
MY READ: <which one wins, and why - usually: the code that runs, then the test, then the doc>
```

Default precedence when nobody answers: the code that actually runs > the test that guards
it > CI config > documentation > comments. Record the choice in the report.

---

## 7. Anti-patterns

- **Drip questions.** One question, wait, one more, wait. Batch the frontier.
- **Questions without recommendations.** You have read the repo; the user has not.
- **Asking for facts you can read.** "What is your test command?" is answered by `scan_repo.py`.
- **Grilling a trivial task.** A typo fix does not get a design tree.
- **Silent interpretation.** Picking one reading of an ambiguous request and never saying which. This is the failure this whole file exists to prevent.
- **Infinite frontier.** If round 4 is still opening new branches, the task is too big: split it and contract only the first slice.
