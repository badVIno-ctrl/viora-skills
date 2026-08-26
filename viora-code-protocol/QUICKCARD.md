# VioraCode QUICKCARD - one screen, T0 MICRO

Use this card when you are a fast/cheap/small model, or when the session is long and you
are losing the thread. Everything you need is on this page. Reading other files is optional.

**Rule of this card: one action per reply. Then stop and look at the output.**

---

## Open every reply with this line

```
VIORA T0 | MODE <FIX|FEATURE|REFACTOR|UI|PERF|TRIVIAL> | STEP n/10
```

## Run this every turn and obey it

```bash
python3 scripts/viora.py next
```

It prints the step, the exact commands, and what counts as finished. When you finish a step:

```bash
python3 scripts/viora.py done <n> --note "<the proof, one line>"
```

**Four more commands. Type them without thinking about it - they do the remembering for you.**

```bash
python3 scripts/viora.py doctor                  # once, before you start: what can be proven here?
python3 scripts/viora.py plan --files <f> --lines 60   # step 4: before the first edit
python3 scripts/viora.py checkpoint              # step 6: before the first edit. Undo is then one command
python3 scripts/viora.py scope                   # after editing: did I touch anything I did not declare?
```

If a hypothesis dies: `python3 scripts/viora.py rollback --yes` puts the tree back. Use it.
A clean tree with two recorded dead ends is a better handover than a tree full of guesses.

---

## The ten steps, with the exact thing to type

**1. CONTRACT** - fill these four lines, change nothing else:

```
GOAL: <one sentence, what the user gets>
DONE-TEST: <the one command or click that proves it>
PROTECTED: <what must keep working>
NON-GOALS: <what I am not touching>
```

**2. OWNER** - find who already does this:

```bash
python3 scripts/find_duplicates.py . --top 15
grep -rn "<main-word>" --include=* -l . | head -20
```

Write one line: `Owner: path/file.ext:123` or `Owner: NONE`.
When an owner exists, you extend it. You do not write a second one.

**3. LADDER** - pick the highest line that solves it, and say why:

```
0 NO CHANGE - it already works / it was not asked for
1 DELETE or CONFIGURE - a flag, a constant, removing code
2 REUSE what this repo already has
3 USE the language / platform / stdlib
4 USE a dependency already installed
5 ADD a dependency (needs the user's yes)
6 WRITE new code - last resort, smallest version
```

**4. PLAN** - at T0 the plan is exactly one file:

```
FILE: path/file.ext
BUDGET: <= 80 changed lines
FROZEN: <public names I will not rename>
```

Need a second file? Say so and ask before opening it.

**5. RED** - make a check that fails *now*:

```bash
<repo test command> <path-to-your-new-test>
```

You must see it FAIL, and the failure must be about the missing behaviour.
No test runner in this repo? Then RED is any command whose output is wrong today.
Paste that wrong output. That is your RED.

**6. GREEN** - smallest edit in that one file, then run the same command until it passes.
Add nothing you were not asked for. No options, no flags, no "while I'm here".

**7. CLEAN** - check yourself against these numbers:

```
file <= 400 lines · function <= 50 · nesting <= 3 · params <= 4
0 magic numbers/strings · 0 nested ternaries · 0 leftover debug prints
0 commented-out code · 0 files outside the PLAN
```

**8. PROVE** - run the gates and paste the table:

```bash
bash scripts/verify.sh .
```

Anything that says SKIP is unproven. Write it down as unproven.

**9. DOUBT** - answer all five out loud, in one short line each:

```
1 Which command output proves this works? (quote it)
2 What did I change that nobody asked for?
3 What breaks if the input is empty, null, huge, or wrong-typed?
4 Is there now a second place that does this same thing?
5 What am I calling done that I never ran?
```

Any answer that worries you sends you back to the step it belongs to.

**10. REPORT** - copy this shape and fill it:

```
VERDICT: DELIVERED | NO_CHANGE | BLOCKED
MODE: <mode> | TIER: T0

WHAT CHANGED
- path:line - <what and why>

HOW IT WAS SOLVED
- ladder rung <n>, extended <owner>

EVIDENCE
| Gate | Command | Result |
|---|---|---|
| test | `<cmd>` | PASS 12/12 |

NOT DONE / UNPROVEN
- <every SKIP, every assumption>

FOLLOW-UPS
- <smallest next step, or none>
```

---

## Three sentences you are not allowed to write

1. "Should work" → run it, paste the output.
2. "Tests pass" without output in *this* reply → that is a memory, not a result.
3. "I'll add the test later" → the test comes first, at step 5.

## Stop and ask when any of these is true

- the file you need is over 400 lines and you would make it longer
- you need a second file, a new dependency, or a schema/API change
- two things in the repo disagree and you cannot tell which one wins
- the same fix failed twice

Ask like this, then wait:

```
BLOCKED ON: <one sentence>
Q1 <question> - my recommendation: <answer>
Q2 <question> - my recommendation: <answer>
```

## Failed twice? Change what you are doing, not the line

```
1st fail - read the whole error message, all of it
2nd fail - stop typing. Write "X happens because Y". Cannot? Go read the code.
3rd fail - stop. Report BLOCKED with what you tried, what you learned, and one question.
```

Record each one so the count is real, not a feeling:

```bash
python3 scripts/viora.py strike --reason "<hypothesis that died, and how it died>"
```

---

## The one thing that catches you out most often

**Every gate result is stamped to the exact code it tested.** Run the gates, then edit one
more line - even a comment, even a string - and that PASS turns `STALE`. It no longer proves
anything, and `check` will say so.

```bash
python3 scripts/viora.py check      # says STALE? then:
python3 scripts/viora.py gate       # rerun. This is the whole fix.
```

So the order is always: **last edit, then gates, then report.** Never the other way round.

Two things that are *not* mistakes. Rerunning a gate replaces its old row - only the newest row
per gate is counted, so the table never fills with duplicates. And your RED row, recorded as
`red`, `repro`, `baseline` or `before`, shows as `pre-fix` rather than STALE: describing the
broken tree is its entire job. What *is* refused is a run where `red` is the only evidence -
a reproduction proves the bug, never the repair.

---

## Before you improvise, copy a real run

`examples/01-t0-fix-full-run.md` is a complete T0 FIX - ten turns, every command, every reply,
including the moment the gates go stale after a one-word edit and get rerun.

Imitating that transcript is easier than reasoning from rules, and it produces a better
result. That is not a criticism of you; it is how this card is designed to be used.
