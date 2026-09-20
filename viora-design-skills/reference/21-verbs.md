# 21 - Verbs

Loaded at G0, and only when the router matched a row. Three verbs, each one a different job
from "build a surface". Each finishes in one pass.

## HARDEN

The surface exists and looks right on the day it was built. HARDEN is the pass that makes it
survive real content and real conditions. Gates: G1, G4, G5, G6. No new direction, no new
palette, no new section.

Walk this list in order, fix what breaks, and report what you found:

| Pressure | What to do | What failure looks like |
|---|---|---|
| Long strings | Paste a 60 character word and a 400 character paragraph into every label, heading and cell | text escapes its box, a flex child refuses to shrink, a card grows taller than its row |
| Empty | Render every list, table and chart with zero rows | a bare "No data", a collapsed layout, a blank panel with no next action |
| Error | Fail every request the screen makes | a spinner that never ends, a toast that replaces the content, a message that names the exception |
| Loading | Slow every request to three seconds | layout that jumps when the answer arrives, a skeleton whose shape does not match the content |
| RTL and i18n | Switch the document to `dir="rtl"`, then to a language that runs 40 % longer | icons pointing the wrong way, hard-coded left padding, truncation in the middle of a word |
| 200 % zoom | Zoom the browser to 200 % at 1280 wide | horizontal scrolling, a sticky header eating the viewport, controls off screen |
| Offline | Kill the network after first paint | an action that silently does nothing, state lost on retry |
| Slow network | Throttle to 3G | fonts flashing, the hero arriving last, layout shift above the fold |

Report at most eight lines: what broke, what changed, what is still exposed and why.

## QUIET and BOLD

One dial, two directions. The request is "calmer" or "louder", and the product truth does not
change. Gates: G1, G3, G4, G6.

**One direction per pass.** Never quiet one half of a surface while making the other half
louder: that is two directions on one page, and it reads as indecision.

| Move | QUIET | BOLD |
|---|---|---|
| Type scale | pull display down one step, raise body line-height | push display up one step, tighten its tracking to the floor |
| Weight | 600 becomes 560, drop one weight from the stack | one weight heavier on the headline only |
| Colour | accent on one element, surfaces move toward the ground | accent field instead of accent text, more ground contrast |
| Space | more space, fewer rules | less space between related things, more between sections |
| Edges | hairlines replace shadows | one ground change replaces many hairlines |
| Motion | shorter durations, fewer moving things | one larger move on the signature moment only |

The dial moves once per pass. If the answer after one pass is "more", run it again and say so.

## CRITIQUE

Audit with no code written. Gates: G1, G6, G7. Output is at most five findings, worst first:

```
<file>:<line> — <the problem, named concretely> — <the one change that fixes it>
```

Rules for this verb:

- Five findings maximum. A list of twenty is a way of saying nothing is important.
- Every finding points at a file and a line, or at a screenshot region, never at "the design".
- Name the defect, not the taste: "three chromatic families outside the semantic colours" is
  a finding, "feels a bit busy" is not.
- Write no patch, no snippet, no refactor. The fix is one sentence.
- Rank by what a visitor loses, not by what is easiest to change.
- If the mechanical linters are clean and nothing survives the five-finding filter, say the
  surface passes and stop. A critique that invents work is worse than no critique.
