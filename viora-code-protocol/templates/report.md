# REPORT template

The last thing you emit. Nothing else - no praise, no restating the request, no summary of your
own effort. Generate the skeleton with `python3 scripts/viora.py report`, then fill in the prose
lines.

```
VERDICT: DELIVERED | NO_CHANGE | BLOCKED
MODE: <TRIVIAL|FIX|FEATURE|REFACTOR|UI|PERF|REVIEW|DEBUG> | TIER: <T0|T1|T2>

WHAT CHANGED
- <path:line> - <what and why, one line>
- <path:line> - <what and why, one line>

HOW IT WAS SOLVED
- Owner: <path:line>. Ladder rung <n> (<name>); rung <n-1> fails: <reason>.

EVIDENCE
| Gate  | Command | Result |
|-------|---------|--------|
| <gate> | `<exact command>` | PASS / FAIL / SKIP-UNPROVEN |

DELETED / REPLACED
- <what is gone, and what took over>

NOT DONE / UNPROVEN
- <every assumption you proceeded on>
- <every path you did not exercise>
- <every gate that was skipped or unavailable>

FOLLOW-UPS
- <exact path> - <the smallest next step>
```

---

## Rules

1. **Every EVIDENCE row is a command you actually ran in this session.** No memory, no
   reconstruction, no paraphrase. `viora.py report` prints only what is in `.viora/evidence.jsonl`.
2. **NOT DONE / UNPROVEN is never empty on a real task.** An empty section means you did not
   look. Environment limits, untested paths and assumptions all belong here.
3. `SKIP` is not `PASS`. A gate that did not run proves nothing.
4. **NO_CHANGE is a valid delivery.** "It already works, here is the proof" is a complete answer.
5. **BLOCKED early beats wrong late.** Use the block below.
6. No adjectives about your own work. "Robust", "clean", "production-ready" are claims with no
   evidence behind them.

---

## BLOCKED variant

```
VERDICT: BLOCKED
MODE: <mode> | TIER: <tier>

BLOCKED ON: <the one decision or piece of information you need>

Q1 <question> - my recommendation: <answer + reasoning>
Q2 <question> - my recommendation: <answer + reasoning>

WHAT I DID ANYWAY
- <recon, reproduction, findings - work that survives either answer>

ATTEMPTS
1 <what I tried> -> <what it ruled out>
2 <what I tried> -> <what it ruled out>
3 <what I tried> -> <what it ruled out>

DEFAULT IF YOU DO NOT REPLY: <what I will assume>
```

---

## NO_CHANGE variant

```
VERDICT: NO_CHANGE
MODE: <mode> | TIER: <tier>

WHY NO CHANGE WAS NEEDED
- <the behaviour already exists at path:line>  OR  <the premise does not hold, because ...>

EVIDENCE
| Gate | Command | Result |
|------|---------|--------|
| repro | `<the command the user described>` | behaves correctly already |

WHAT I CHECKED
- <searches run, files read, commands executed>

IF YOU MEANT SOMETHING ELSE
- <the most likely alternative reading of the request, as a question>
```
