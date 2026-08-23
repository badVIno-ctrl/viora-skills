# Working notes (copy this into your scratchpad at the start of every task)

```
LANE: LITE | FULL          MODE: TRIVIAL | FIX | FEATURE | REFACTOR | UI | PERF | REVIEW

--- CONTRACT ---
Outcome (observable):
Acceptance (the command or interaction that proves it):
Protected behavior (must keep working):
Non-goals:
Assumptions (mark VERIFIED or GUESSED - never implement on a guessed interface):

--- OWNERSHIP MAP (fill from recon; one line per concept) ---
concept                -> path:line                 note
...                    -> ...                        canonical / duplicate / missing

--- SEARCHES RUN (proof that nothing was duplicated) ---
grep/scanner command                                  -> result
python3 scripts/find_duplicates.py .                  -> ...

--- LADDER ---
Chosen rung: 0 no change | 1 delete/config | 2 reuse local | 3 platform/stdlib |
             4 installed dep | 5 new dep | 6 minimal custom
Why not a lower rung:

--- FILE PLAN ---
path                          NEW/EDIT   single responsibility                 est. lines

--- INTERFACES (frozen before coding) ---
unit(signature) -> returns
  consumes:
  produces:
  edge cases:

--- CHECKLIST (tick only what you actually did) ---
[ ]  1 restate goal + acceptance + protected behavior
[ ]  2 unknowns asked in one batch (or none)
[ ]  3 searched before writing; ownership map filled
[ ]  4 ladder rung chosen
[ ]  5 file plan written
[ ]  6 limits respected (400 file / 50 func / 3 nesting / 4 params / 8-line dup / 0 magic)
[ ]  7 implemented on the existing owner; superseded code deleted; everything wired
[ ]  8 UI: mounted once, replaced not stacked, layer tokens, teardown pairs
[ ]  9 checks written (failing-first for bugs)
[ ] 10 gates run and output read
[ ] 11 diff self-reviewed line by line
[ ] 12 report written with evidence

--- EVIDENCE COLLECTED ---
| gate | command | result |

--- DEVIATIONS / FOLLOW-UPS / UNPROVEN ---
```
