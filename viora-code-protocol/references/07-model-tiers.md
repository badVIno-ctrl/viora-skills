# 07 - Model tiers: making one protocol run on any model

The protocol has one spine and three amounts of scaffolding. **The gates never change.**
What changes is how much judgment the model is asked to supply, and how much is supplied
by a template, a script, or a hard number.

This file is the single owner of tier behaviour. Other references describe *what* a step
is; this one describes *how much of it you do*.

---

## 1. Why tiers exist

A strong model reads "find the owner of this behaviour" and runs four searches, reads three
files, and writes one accurate line. A fast model reads the same sentence and writes a
plausible line without searching, because the instruction asked for a *judgment* and gave
no *procedure*.

So the same rule is expressed three ways:

| Rule | T2 FULL | T1 LITE | T0 MICRO |
|---|---|---|---|
| Find the owner | "map ownership before writing" | "3 name variants + 2 behaviour keywords, write `Owner: path:line`" | "run `find_duplicates.py`, paste output, copy one `Owner:` line from it" |

Same gate. Three costs. **Under-scaffolding a weak model produces confident fiction;
over-scaffolding a strong model costs a few tokens.** That asymmetry is why the default is T1.

---

## 2. Choosing the tier

First match wins:

1. **`.viora/tier` file** in the repo root contains `T0`, `T1` or `T2` → use it. Deterministic, survives context loss, works for a whole team.
2. **The user named a tier** → use it.
3. **Neither** → **T1**.

Create the file once per repo:

```bash
mkdir -p .viora && echo T0 > .viora/tier
```

### Suggested mapping (guidance, never a hard identity check)

| Class of model | Start at |
|---|---|
| Frontier reasoning models with a long budget | T2 |
| Mid-tier and "fast" frontier variants | T1 |
| Flash/mini/turbo class, 8-30B local models, heavily quantised models | T0 |
| Any model past ~15 replies in one task | drop one tier |
| Any model in an unfamiliar repo on its first task | drop one tier |

A model does not need to know its own name to run this protocol. The demotion triggers
below are all observable events, which is what makes the system work without introspection.

---

## 3. Demotion and promotion

**Demote one tier immediately when any of these happens:**

| Trigger | Why it means "less judgment, more scaffolding" |
|---|---|
| a gate failed twice in a row on this task | the current approach is not converging |
| you edited a file outside the PLAN | scope control is already lost |
| you wrote a claim you had not run | the evidence discipline slipped |
| you cannot state your current step number | state is lost; the checklist has to hold it |
| 15th reply on one task | context is crowded; shrink the unit of work |
| you re-opened the same file a third time | searching without a query |
| you produced two near-identical replies | stalling |

Announce it and keep going: `DEMOTE -> T0 (gate failed twice)`. Restart the *current* step
under the new tier; keep everything already proven.

**Promote only on evidence, and only one tier:** the task is finished, gates passed first
try, and you never lost the step. Promotion is optional. Staying at T0 forever and shipping
is better than reaching T2 and thrashing.

---

## 4. The 60-second calibration probe (optional, honest)

Run once in a new repo when you want the tier decided by behaviour instead of by guess.
Do all four, in order, in one reply.

```
P1  Run:  python3 scripts/scan_repo.py .
    Then answer from the output only: what is the repo's real test command?
    Pass = you quote it exactly. Fail = you invent "npm test" without seeing it.

P2  Name the file in this repo that owns <the concept in the task>, as path:line.
    Pass = the path exists and the line contains the concept.

P3  Say what you have NOT verified about this repo yet, in three bullets.
    Pass = three specific unknowns. Fail = "nothing" or vague hedging.

P4  Write the four-line CONTRACT for this task.
    Pass = DONE-TEST is a command or a click, not an adjective.
```

| Result | Tier |
|---|---|
| 4/4 clean | T2 |
| 3/4 | T1 |
| ≤2/4, or any invented fact | T0 |

Write the result into `.viora/tier` so it survives the next context reset.

---

## 5. T0 MICRO - the rails

T0 is not a weaker protocol. It is the same protocol with the judgment removed.

### 5.1 The turn loop

```
1  Print the header line:  VIORA T0 | MODE <mode> | STEP n/10
2  Run:  python3 scripts/viora.py next
3  Do exactly the ONE action it prints. Nothing else.
4  Paste the real output.
5  Run:  python3 scripts/viora.py done <n> --note "<proof>"
6  Stop. Wait for the next turn.
```

One action per turn is the single highest-value T0 rule. Most weak-model failures are not
wrong answers; they are five actions taken at once with no output read in between.

### 5.2 Hard stops - ask, then wait

At T0 these are not judgment calls. Hitting one ends the turn with a question:

- a second file is needed
- a new dependency is needed
- a public interface, schema, migration, or config default would change
- the target file is already over 400 lines
- more than 80 lines would change
- two sources in the repo disagree (code vs docs vs test)
- the same fix has failed twice
- anything involving auth, payments, secrets, permissions, or deletion of user data

### 5.3 T0 forbids (and what to do instead)

| Instead of | Do this |
|---|---|
| parallel edits across files | one file, one turn |
| "I'll refactor while I'm here" | write it in FOLLOW-UPS |
| inventing a command | copy the command from `scan_repo.py` output |
| summarising output | paste output verbatim |
| a plan longer than 5 lines | the four-line PLAN template |
| sub-agents, worktrees, cross-model reviews | the five DOUBT questions |
| reading three reference files | read `QUICKCARD.md` only |

### 5.4 Context economy at T0

Context is the scarce resource. Spend it on code, not on the protocol.

- Load `QUICKCARD.md`. Load one reference file only if the step names it.
- Re-read your own CONTRACT before steps 6, 8 and 10. It is four lines; it is cheap.
- After each step, keep the *result* and drop the exploration. `viora.py` stores results on disk so you can forget them safely.
- When you notice you are summarising your own earlier replies, hand off (§7) instead of continuing.

---

## 6. T1 LITE and T2 FULL - what is added

### T1 LITE adds to T0

- up to 3 files per PLAN, up to 300 changed lines
- real judgment on the ladder instead of picking from a list
- OWNER search by hand: 3 name variants + 2 behaviour keywords
- the 8-lens cold pass at DOUBT instead of the 5 questions
- one reference file per step, when the step names it

### T2 FULL adds to T1

- GRILL rounds when the contract is ambiguous (`09-clarify-and-grill.md`)
- seam confirmation before writing tests (`05-tests-and-evidence.md`)
- clean-context or cross-model review at DOUBT (`11-doubt-and-second-opinion.md`)
- the bounded review-and-fix loop with a ledger (`12-review-loop-and-ledger.md`)
- risk-first differential review with blast radius (`13-differential-review.md`)
- sub-agents, worktrees, parallel exploration - each one still reporting into the same report contract

---

## 7. Handoff - surviving a context reset

When context runs short, or you demote mid-task, write this and stop. Any tier can pick it up.

```
HANDOFF
TIER / MODE: T1 / FIX          STEP: 6 of 10
CONTRACT:  <the four lines, verbatim>
OWNER:     <path:line>
PLAN:      <files + budget>
DONE:      <what is finished, with the command that proved it>
RED:       <the failing check and its exact command>
NEXT:      <the single next action>
OPEN:      <questions blocking progress>
RISKS:     <what might break>
ATTEMPTS:  <failed attempts on the current problem: n>
```

`python3 scripts/viora.py handoff` prints this from recorded state, already filled in.

---

## 8. Writing rules for anyone extending this protocol

These are the rules that make instructions survive a weak model. Apply them to every file here.

1. **State the target behaviour, not the ban.** "Paste the command output" beats "don't claim without evidence": a prohibition drags the forbidden action into context and makes it more available. Keep a ban only as a hard guardrail, and pair it with the positive form.
2. **Every step ends on a checkable condition.** "Understand the code" is unfinishable. "Write `Owner: path:line`" is done or not done.
3. **Give the exact command.** A weak model that must invent a command will invent a plausible wrong one.
4. **One meaning, one place.** Duplicated rules drift apart and then contradict each other. Point at the owner file instead of restating it.
5. **Short imperative sentences, front-loaded verb.** The first three words decide whether the instruction fires.
6. **Numbers over adjectives.** "≤80 changed lines" survives; "keep it small" does not.
7. **Repeat a *word*, never a *rule*.** OWNER, LADDER, RED, PROVE, DOUBT are load-bearing labels; reusing them anchors behaviour at zero token cost. Restating a whole rule twice creates two owners of it.
8. **Cut anything the model already does by default.** A line that changes no behaviour costs attention for nothing.
9. **Push detail behind a pointer.** The top level holds the steps; depth lives in a reference file that is read only when its step fires.

---

## 9. What the machine enforces, so the tier does not depend on memory

Tiers describe how much protocol a model can hold. The three mechanisms below do not depend on
holding anything: they are files on disk and exit codes. **They matter most at T0**, because a T0
model is exactly the model that will forget an instruction between two turns.

### 9.1 Evidence staleness

Every gate result is fingerprinted against the working tree. Edit anything afterwards and that
result is `STALE`: `check` fails, `report` moves it into UNPROVEN, the pre-commit hook blocks the
commit.

```bash
python3 scripts/viora.py check     # STALE?
python3 scripts/viora.py gate      # rerun. That is the whole fix.
```

The rule "gates last, after the final edit" is no longer something a weak model has to remember.
It is arithmetic. → `references/05-tests-and-evidence.md` §10

### 9.2 Scope, measured from git

```bash
python3 scripts/viora.py plan --files src/routes/login.ts --lines 60
# ... edit ...
python3 scripts/viora.py scope
```

`scope` compares the recorded plan to the real diff and reports undeclared files, declared files
you never touched, changed lines against the tier budget (T0 80 / T1-T2 300) and file count
against the tier cap (T0 1 / T1 3 / T2 8). **Steps 6 and 7 will not close while scope has
problems.**

This converts the per-tier budgets in this file from advice into a gate. At T0 the file cap of 1
is the single most valuable constraint in the protocol, and it is now checked rather than trusted.

Widening a plan deliberately is allowed and leaves a record:

```bash
python3 scripts/viora.py plan --files src/routes/login.ts,src/validation/body.ts --lines 60 --force
```

Silently touching the second file is not. That is the whole difference between a decision and
scope creep.

### 9.3 Checkpoints, so stopping is cheap

```bash
python3 scripts/viora.py checkpoint --label "before GREEN"
# ... hypothesis dies ...
python3 scripts/viora.py rollback --yes
```

The hardest instruction to obey at T0 is *stop after two failed attempts*. It is hard because
stopping feels like abandoning a mess. With a checkpoint, stopping returns a **clean tree plus two
recorded dead ends** - which is a genuinely useful handover, and often more useful than a fix.

`rollback` refuses without `--yes`, refuses when HEAD has moved (unless `--force`), and lists
untracked files created after the checkpoint instead of deleting them silently.

### 9.4 The T0 turn loop, updated

The loop in §5.1 becomes, in full:

```bash
python3 scripts/viora.py next        # what am I doing?
#   ... do exactly that, one action ...
python3 scripts/viora.py scope       # did I stay inside the plan?   (steps 6-7)
python3 scripts/viora.py done <n> --note "<proof>"
```

Four commands, no judgement calls. A model that can run four commands per turn can follow this
protocol - which is the entire claim T0 makes.

### 9.5 Demotion is now partly automatic

Two of the seven demotion triggers in §3 are detected by the machine rather than self-reported:

| Trigger | How it surfaces |
|---|---|
| a fabricated claim | `report` cannot print PASS without a recorded row; a changed tree marks it STALE |
| a scope breach | `scope` fails and steps 6-7 refuse to close |

When either fires, demote and say so in one line - `DEMOTE -> T0 (scope breach: 4 files against a
cap of 3)` - then continue at the lower tier. The demotion is a fact about this run, not a verdict
on the model.

### 9.6 Do not guess the tier - measure it

`evals/` contains six fixtures and a scorer built around documented weak-model failures. Run them
against the model you actually have:

```bash
bash evals/run.sh prepare f02
bash evals/run.sh score f02 ~/runs/model-f02.txt
```

6 PASS means T2 is safe. 4-5 means T1. 2-3 means pin T0 and leave it pinned. A fatal failure on
`f04-no-test-runner` means that model claims results it never obtained: use it with the pre-commit
hook installed, and do not accept its reports on their own word. → `evals/rubric.md`
