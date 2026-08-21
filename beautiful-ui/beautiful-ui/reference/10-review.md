# 10 - Review

Loaded at G6. Purpose: verify mechanically, fix in one batch, then stop. Close when the checker is clean and one screenshot round is resolved.

Self-review by reading your own code does not work. You will approve your own defects. Verification has to be mechanical (a script) or visual (a screenshot). Both are cheap.

## 1. Run the checker

From the project root:

```bash
node <skill-path>/scripts/check.mjs .
node <skill-path>/scripts/contrast.mjs <your token file>
```

Useful flags:

```bash
node check.mjs src app            # limit to paths
node check.mjs . --summary        # counts only
node check.mjs . --json           # machine-readable
node check.mjs . --ignore-rule banned-font,raw-hex
```

How to respond:

- **Every ERROR gets fixed.** No exceptions, no explaining why it is fine.
- **Every WARN gets a decision.** Either fix it, or add `/* bui-allow: rule-id reason */` on the line above so the choice is recorded. Silently ignoring warnings is how quality drifts.
- Exit code 1 means errors remain. Do not report success while the exit code is 1.

The checker catches the mechanical subset. `contrast.mjs` catches what a text search cannot: it resolves `var()`, `color-mix()`, and `oklch()` in both themes and measures the real ratios. Neither can see that your hero is boring. That is what the screenshot round is for.

## 2. Screenshot round

One round. Desktop and mobile in the same round, not two rounds.

```bash
node <skill-path>/scripts/shot.mjs http://localhost:3000 --out .bui-shots
node <skill-path>/scripts/shot.mjs http://localhost:3000 --squint   # grayscale blur, silhouette test
node <skill-path>/scripts/shot.mjs http://localhost:3000 --icon     # 0.2x, is it still recognisable
```

That writes `desktop-1440x900.png` and `mobile-390x844.png`, plus `-squint` and `-icon` variants when those flags are used, and full-page versions with `--full`. If the helper cannot run here, use whatever screenshot tool exists at 1440x900 and 390x844, or ask the user for two screenshots. Do not skip the visual check because the tooling was awkward.

Look at the images and answer these twelve questions honestly:

1. Does the first screen say what this is, in the first two seconds?
2. Is there a single obvious next action?
3. Does any section look like a placeholder? (Repeated cards, empty boxes, grey bars.)
4. Is the alignment edge held, or does the left margin wander?
5. Is spacing above headings clearly larger than below?
6. Do any two adjacent sections have the same shape and width?
7. On mobile: does anything overflow, clip, or squeeze? Is the nav usable? Are targets big enough?
8. Is the type hierarchy readable in one glance, from a squint?
9. Does anything look accidental: a stray gap, a misaligned icon, an orphan word, a hairline that changes weight?
10. Would a designer look at this and say it was decided, or generated?
11. Squint at the grayscale blur: is the silhouette still readable, and does the eye land where you intended?
12. At icon scale, does it still read as this product, or as any template?

Fix everything you found **in one batch**. Then take one confirming screenshot. Then stop. A third round buys nothing and risks breaking what worked.

## 3. Heuristic pass, severity, personas

Three passes that catch what a checker and a screenshot both miss. One sitting, in this order, and the result goes into the report.

### The ten heuristics, scored

Score each one 0, 1, or 2. Anything at 0 is a named defect, not a feeling.

| # | Heuristic | What to look for |
|---|---|---|
| 1 | Visibility of status | every action produces visible feedback inside 100ms |
| 2 | Match to the real world | labels use the user words, not the schema names |
| 3 | Control and freedom | undo, cancel, escape, and back all work |
| 4 | Consistency | one word per concept, one pattern per job |
| 5 | Error prevention | constraints and good defaults instead of error messages |
| 6 | Recognition over recall | the next step is visible, not remembered |
| 7 | Efficiency | a shortcut for the hundredth visit, not just the first |
| 8 | Minimalism | nothing on screen that does not earn its place |
| 9 | Error recovery | the error names the fix, in plain language |
| 10 | Help | the hard part has an inline explanation |

Under 15 out of 20 means the problem is structural, not stylistic. Do not fix it with colour.

### Severity, so the fix order is not a matter of taste

- **P0**: blocks the task, loses data, or fails accessibility outright. Fix now.
- **P1**: the task is possible but the user has to work around something. Fix in this batch.
- **P2**: friction or inconsistency. Fix if the batch has room.
- **P3**: taste disagreement. Record it, move on, do not argue.

### Five walkthroughs

Walk the primary flow as five people. Two lines each, naming what breaks:

1. First-time visitor, thirty seconds, no context, on a phone.
2. Returning power user, keyboard only, doing this for the hundredth time.
3. One hand, bright sunlight, moving, poor connection.
4. Screen reader user, tab and arrow keys only.
5. The sceptic who has seen ten of these this week and is looking for a reason to leave.

### Subtraction pass

Delete one thing: a section, a card, a label, a shadow, a colour, a word in the headline. If the page got worse, put it back. A review that removes nothing did not happen.

## 4. Pre-flight checklist

Run once at the end. Anything that fails goes into the same fix batch.

### Direction
- [ ] The world is named in `DESIGN.md` and the build matches it.
- [ ] The output is not in one of the banned default clusters.
- [ ] The dials are respected: motion level matches actual motion, density matches actual density.

### Tokens
- [ ] One token file, imported first.
- [ ] No raw hex, no magic px inside components.
- [ ] One radius family. One shadow scale. One accent.
- [ ] Both themes complete if the project has both.

### Type
- [ ] Two families maximum, plus mono only if real code or values exist.
- [ ] Display sizes carry negative tracking.
- [ ] Body 16px or larger, nothing below 12px.
- [ ] Reading measure at or under 75 characters.
- [ ] `text-wrap: balance` on headings, no orphan words in headings.
- [ ] The font actually loads, including the script the content needs.

### Layout
- [ ] At least four distinct section families, no family used twice.
- [ ] No more than two card-based sections, never adjacent.
- [ ] Space above headings exceeds space below.
- [ ] Nothing scrolls horizontally at 320px.
- [ ] `100dvh`, never `100vh`.
- [ ] Safe areas respected on fixed elements.

### Components and states
- [ ] Hover, focus-visible, active, disabled on every interactive element.
- [ ] Loading, empty, error on every async surface.
- [ ] Real `<button>` and `<a>`, never a clickable `div`.
- [ ] One icon set, one weight.
- [ ] Every icon-only control has an accessible name.
- [ ] Every image has `alt`.

### Motion
- [ ] One or two authored moments, not motion everywhere.
- [ ] Only `transform` and `opacity` on hot paths.
- [ ] Tokenised easings and durations, nothing invented.
- [ ] Nothing above 300ms in-app.
- [ ] `prefers-reduced-motion` present and correct.
- [ ] Hover effects gated for touch.

### Accessibility
- [ ] Body contrast >= 4.5:1, UI and control borders >= 3:1, measured with `scripts/contrast.mjs`, not guessed.
- [ ] Full keyboard pass: tab through the whole page, everything reachable, focus always visible, order matches visual order.
- [ ] `Escape` closes overlays, focus returns to the trigger.
- [ ] One `<h1>`, headings in order.
- [ ] Labels on all form controls.
- [ ] Works at 200% zoom.
- [ ] Status never conveyed by colour alone.

### Content
- [ ] Zero em-dashes.
- [ ] No `Lorem`, `Acme`, `John Doe`, invented-perfect statistics.
- [ ] Every button names its action.
- [ ] Every error says what to do next.
- [ ] Every empty state offers the action that fills it.
- [ ] One language throughout.

### Browser surfaces
- [ ] `::selection` themed.
- [ ] `caret-color` themed.
- [ ] Scrollbar themed, `color-scheme` set.
- [ ] Focus ring visible on every background it can appear on.
- [ ] Link underline offset set.
- [ ] Tabular numerals on numeric columns.
- [ ] Autofill styling overridden.

### Performance
- [ ] Images sized, `loading="lazy"` below the fold, `width` and `height` set so nothing shifts.
- [ ] No layout shift on load.
- [ ] Fonts limited to the weights used, `display=swap`.
- [ ] No animation library pulled in for a fade.

## 5. REVIEW mode

When the job is `REVIEW`, write no product code. Deliver:

1. A verdict in one line: what this interface is trying to be, and whether it is that.
2. The three highest-leverage fixes, each with the concrete change (before and after values, not adjectives).
3. Everything else grouped by severity, referencing file and line where possible.
4. What is already good, in two lines, so the next editor does not destroy it.

Use a before/after table for anything visual. It is the only review format that survives being handed to another model:

| Element | Now | Change to | Why |
|---|---|---|---|
| Hero heading | 48px, tracking 0 | 64px, `-0.03em` | display type at default tracking reads as unset |
| Card grid | 3 equal cards | ledger rows with hairlines | equal cards read as a template |

## 6. Optional extra pass

Only if this environment actually has network access, and only for a web project with context budget left after G6, the Vercel web interface guidelines are a useful independent second opinion:

`https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`

If the fetch fails, say so in one line and move on. Never block G6 on a network call, and never claim you consulted a document you could not load.

## 7. Stop rule

Stop when: the checker exits 0, the pre-flight has no unresolved item, and one confirming screenshot looks right.

Do not:
- start a third screenshot round,
- refactor working code for elegance,
- add a feature nobody asked for,
- keep polishing to appear thorough.

Print `G6 verify: 0 errors, N warnings (all decided), contrast 0 failures` and go to G7.
