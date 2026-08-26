# HANDOFF template

Use this when the context is nearly full, the session is ending, or the work is passing to
another agent or another tier. Generate it with:

```bash
python3 scripts/viora.py handoff
```

A weak model loses the thread long before it loses the tokens. This block is what makes the next
context resume instead of restart - and restarting is where duplicate implementations come from.

---

## The block

```
HANDOFF
TIER / MODE: <T0|T1|T2> / <mode>       STEP: <n> of <total>
TASK: <one sentence>

CONTRACT
GOAL:      <...>
DONE-TEST: <...>
PROTECTED: <...>
NON-GOALS: <...>

OWNER: <path:line>            (from step 2 - do not search again)
LADDER: rung <n> because <...>
PLAN:  <files, budget, frozen interfaces>
RED:   <the failing check and its current output>

DONE SO FAR
  step 1 CONTRACT - <proof>
  step 2 OWNER    - <proof>
  ...

GATES LAST RUN
  <gate>: <result> (<command>)

FILES TOUCHED
  <path> - <what changed>

OPEN FINDINGS
  <id> <severity> <text>

DECISIONS ALREADY MADE (do not revisit)
  - <decision> - <who decided and why>

ATTEMPTS ON THE CURRENT PROBLEM: <n> failed
  1 <what was tried> -> <what it ruled out>
  2 <what was tried> -> <what it ruled out>

NEXT ACTION: <the single next thing, in one imperative sentence>
DO NOT: <the traps already discovered in this session>
```

---

## Rules

1. **State, not narrative.** The next context needs facts and the next action, not the story of
   how you got here.
2. **Carry the decisions.** An unrecorded decision gets re-made differently, and now the repo has
   two answers to one question.
3. **Carry the attempts.** Without them the next context repeats a failed fix and burns the
   attempt budget again.
4. **Carry the owner line.** Re-searching wastes context; worse, a failed re-search produces a
   second implementation.
5. **One next action.** A list of five things invites the next context to batch them, which is
   exactly the failure mode T0 exists to prevent.
6. **Never hand off a claim you did not prove.** Write `UNPROVEN` and let the next context prove
   it, rather than passing on a belief as a fact.

---

## Receiving a handoff

```
1 read the CONTRACT first, and treat it as fixed unless the user changes it
2 run  python3 scripts/viora.py status   - the state on disk is authoritative
3 re-run the gates once before adding anything: the tree may not be where the note claims
4 do the NEXT ACTION only - do not re-plan, do not re-search what OWNER already answers
5 respect DECISIONS ALREADY MADE and DO NOT
```

Disagreeing with a decision in the handoff? Say so as a question, with your reasoning. Do not
silently reverse it - a reversed decision mid-task produces a change that half-follows two
designs.
