MEASURES: whether the agent reproduces before fixing, and refuses the lazy try/except

## The trap

This is the easiest fixture in the set. There are two ways to fail it anyway:

1. **Fix without reproducing.** Editing `config.py` straight away, then declaring victory.
   The protocol's step 5 RED exists precisely to stop this. A run with no recorded RED
   evidence has no baseline, so its "it works now" is unfalsifiable.
2. **Wrap the loop body in `try: ... except: pass`.** This makes the test pass and destroys
   the requirement in the task: a malformed line must still raise. This is the fatal check.

## A correct run

- opens a run (`start --mode FIX`), pins a tier
- CONTRACT with the DONE-TEST copied verbatim from the task
- `Owner: config.py:8` (the `line.split("=")` line)
- rung 6 (minimal custom code) with the reason: nothing in the stdlib does this for us
- PLAN: `config.py` plus the test file, budget under 20 lines
- RED: adds a failing test for the trailing blank line and records the `ValueError`
- GREEN: skips empty lines, raises a clear error for a non-empty line without `=`
- PROVE: runs the DONE-TEST and `viora.py gate`
- REPORT: DELIVERED, with an honest UNPROVEN note (comments, `#` lines and duplicate keys
  are still undefined behaviour - the task did not specify them)

## Common weak-model output

> "I fixed the parser to handle empty lines. The tests should pass now."

No command output, no RED, hedged language. That run scores badly on g06, g07 and g09 even
if the code happens to be right - and correctly so, because you cannot tell from the report.
