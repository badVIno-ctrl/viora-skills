# Виора Design Lite

One file. Self-contained. Nothing else has to be read.

This is the LITE lane of `viora-design-skills`. It exists because the FULL lane asks a model
to route across thirteen reference files, hold a direction contract in its head and run three
scripts. A strong model does that well. A fast or small model drops the plan halfway and
ships a generic page. LITE removes every choice a weak model gets wrong and keeps every
choice that makes a page look designed.

**Run LITE when any of these is true:**

- you are a fast, small, cheap or distilled model, or you are unsure how strong you are,
- you cannot reliably read more files later in this task,
- you cannot run shell commands,
- the whole job is one screen or one component and speed matters,
- the user asked for the lite lane.

**Run the FULL lane (`SKILL.md`) instead when** you can hold a plan across many steps,
read files on demand and run `node`. FULL produces better work. LITE produces good work
every time.

Rule for this lane: **select, never invent.** Every table below is a menu. Pick a row,
follow it literally, do not average two rows together, do not improve it by feel.

---

## Step 1. Write four lines, then stop planning

Copy this block into your answer or as a comment at the top of the file, filled in:

```
SURFACE: <what this is> for <who, concretely: "dispatcher at 6am, one hand, cold yard">
JOB:     <the one thing the visitor must do or understand>
RECIPE:  <R1..R8 from Step 2>
SIGNATURE: <the one moment a visitor would describe to someone else>
```

Rules for this block:

- The audience is a real scene, never "users".
- One job per surface. If you list two, the design will show two and land neither.
- The signature is one thing: one oversized number, one hairline ledger, one photograph
  bleeding off the edge, one animated draw of a rule on load. Not five effects.
- **The interface speaks the language of the request.** A Russian request gets Russian copy,
  Russian quotes, and a font that ships Cyrillic. Set `lang` on `<html>` to match.

If something material is missing, ask at most three questions in one round, then continue.
Never ask which colour the user prefers. Deciding is your job.

---

## Step 2. Pick one recipe

Eight complete worlds. Each row is a full package: palette, type, shape, one signature move.
Pick by the audience and job you just wrote, not by the industry cliché.

| # | Recipe | Use for | Accent | Type pair (both ship Cyrillic) | Radius | Signature move |
|---|---|---|---|---|---|---|
| R1 | **Precise Graphite** light, neutral, adult | B2B tools, admin, settings, docs of a product | `#1d4ed8` | Manrope 600 display / Inter 400 text | 4px | one hairline table doing real work, no cards |
| R2 | **Night Console** near-black, technical | devtools, infra, analytics, anything with logs | `#5b7cfa` | Manrope 600 / Inter 400, JetBrains Mono for values | 8px | real product panel in the first viewport, mono numbers |
| R3 | **Paper Editorial** authored, literate | long reads, guides, changelogs, manifestos | `#8a3324` | Playfair Display 600 / PT Serif 400 | 0px | one asymmetric column with a real measure of 66 characters |
| R4 | **Clinic Trust** calm, careful | health, fintech, government, forms | `#0f766e` | Onest 600 / Inter 400 | 10px | a form that is obviously easy: one column, big labels, no card |
| R5 | **Signal Industry** rugged, loud | hardware, logistics, sport, construction | `#ea580c` | Oswald 600 / Inter 400 | 2px | edge-to-edge band of one signal colour carrying the claim |
| R6 | **Warm Solar** friendly, energetic | consumer apps, education, community | `#c2410c` | Unbounded 600 / Nunito Sans 400 | 16px | one large warm colour field behind the primary action |
| R7 | **Deep Forest** grown, unhurried | wellness, food, sustainability, retreats | `#2f6b4f` | Lora 600 / Golos Text 400 | 14px | wide margins and one photograph at full bleed |
| R8 | **Gallery Quiet** the work leads | portfolio, photography, showcase | `#111111` | Tenor Sans 400 / Inter 400 | 0px | an image grid with real air and hairline captions |

Palette values for each recipe are in Step 3. Do not mix a recipe's accent into another
recipe's ground.

**Anti-default check, ten seconds.** If your first instinct was cream paper plus a
high-contrast serif plus a terracotta accent, or near-black plus one neon accent plus a
glowing mesh gradient, or a purple-to-blue gradient button for anything AI: that is the
default, not a decision. Those clusters appear in every generated page. Pick a different
recipe unless the user pinned that look.

**Font safety.** All faces named above ship Cyrillic. If you swap in your own, and the copy
contains Cyrillic, never use Geist, Schibsted Grotesk, Instrument Sans, Satoshi, General Sans,
Cabinet Grotesk, Clash Display, Outfit, Space Grotesk or Bebas Neue. They silently fall back
to a system font and the design is gone.

---

## Step 3. Paste the token block, then edit only the first six lines

One block. Light and dark. Put it at the top of your CSS or in a `<style>` in the head.
Everything under `CRAFT FLOOR` is what makes a page feel built. Do not delete it.

```css
:root {
  /* EDIT: paste one recipe row from the table below */
  --canvas:#ffffff; --surface:#f6f6f7; --hairline:#e4e4e7;
  --ink:#16171a; --ink-muted:#5b5e66; --accent:#1d4ed8; --accent-ink:#ffffff;

  /* control boundary: on an input this line IS the affordance, keep it dark enough */
  --control-border:#8a8c95;
  --danger:#c0261f; --success:#1a7f4b; --warning:#9a6206;

  --font-display:"Manrope",system-ui,sans-serif;
  --font-text:"Inter",system-ui,sans-serif;
  --font-mono:"JetBrains Mono",ui-monospace,monospace;

  --r:4px;                       /* one radius family, everywhere */
  --s1:4px;  --s2:8px;  --s3:12px; --s4:16px; --s5:24px;
  --s6:32px; --s7:48px; --s8:64px; --s9:96px;
  --measure:66ch;                /* reading width for body copy */
  --shadow-1:0 1px 2px hsl(232 12% 10% / .06);
  --shadow-2:0 6px 16px -4px hsl(232 12% 10% / .10);
  --dur:180ms; --dur-slow:320ms; --ease:cubic-bezier(.2,.6,.2,1);
}

@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --canvas:#0b0b0d; --surface:#16171a; --hairline:#26272b;
    --ink:#f4f4f5; --ink-muted:#9c9fa6; --accent:#5b7cfa; --accent-ink:#0b0b0d;
    --control-border:#66686f;
    --shadow-1:0 1px 2px hsl(232 30% 2% / .5);
    --shadow-2:0 8px 24px -6px hsl(232 30% 2% / .6);
  }
}

/* ---------------- CRAFT FLOOR: do not edit, do not delete ---------------- */
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--canvas);color:var(--ink);
  font:400 16px/1.55 var(--font-text);
  font-synthesis-weight:none;text-rendering:optimizeLegibility;
  -webkit-font-smoothing:antialiased}
h1,h2,h3{font-family:var(--font-display);line-height:1.08;
  letter-spacing:-.02em;text-wrap:balance;margin:0}
p{text-wrap:pretty;max-width:var(--measure)}
a{color:inherit;text-underline-offset:.18em}
:where(a,button,input,select,textarea,summary,[tabindex]):focus-visible{
  outline:2px solid var(--accent);outline-offset:2px;border-radius:calc(var(--r) - 1px)}
::selection{background:color-mix(in oklab,var(--accent) 22%,transparent);color:var(--ink)}
input,textarea,select,button{font:inherit;color:inherit}
input,textarea,select{background:var(--canvas);border:1px solid var(--control-border);
  border-radius:var(--r);padding:10px 12px}
button{cursor:pointer;touch-action:manipulation}
table{border-collapse:collapse;width:100%}
td,th{text-align:left;padding:10px 12px;border-bottom:1px solid var(--hairline)}
[data-num],td:has(+td),.num{font-variant-numeric:tabular-nums}
img,svg,video{display:block;max-width:100%;height:auto}
:target{scroll-margin-top:5rem}
@media (prefers-reduced-motion: reduce){
  *,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;
    transition-duration:.01ms!important;scroll-behavior:auto!important}
}
```

### Recipe palettes: copy one row into the six EDIT values

| # | canvas | surface | hairline | ink | ink-muted | accent | accent-ink |
|---|---|---|---|---|---|---|---|
| R1 | `#ffffff` | `#f6f6f7` | `#e4e4e7` | `#16171a` | `#5b5e66` | `#1d4ed8` | `#ffffff` |
| R2 | `#0b0c0e` | `#14161a` | `#24262c` | `#f2f3f5` | `#9ba1ab` | `#5b7cfa` | `#0b0c0e` |
| R3 | `#faf7f2` | `#f2ede4` | `#ded5c6` | `#1c1a17` | `#5d564c` | `#8a3324` | `#faf7f2` |
| R4 | `#f8fafa` | `#eef3f3` | `#d8e2e2` | `#12201f` | `#4e6260` | `#0f766e` | `#ffffff` |
| R5 | `#111111` | `#1b1b1b` | `#2e2e2e` | `#f5f5f4` | `#a3a3a0` | `#ea580c` | `#111111` |
| R6 | `#fffaf3` | `#fff1df` | `#f2ddc4` | `#231a12` | `#6b5744` | `#c2410c` | `#ffffff` |
| R7 | `#f7f8f4` | `#eaeee6` | `#d3dbcd` | `#161d17` | `#4f5b4f` | `#2f6b4f` | `#ffffff` |
| R8 | `#ffffff` | `#f4f4f4` | `#e6e6e6` | `#111111` | `#6b6b6b` | `#111111` | `#ffffff` |

For R2 and R5 the values above are already the dark ground: delete the
`prefers-color-scheme` block or invert it deliberately, do not ship both.

### Load the fonts (one line in the head, before your CSS)

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600&family=Inter:wght@400;500&display=swap">
```

Two families maximum, plus one mono only when real values are shown. Four weights maximum
in the whole project. Swap the family names for your recipe's pair.

---

## Step 4. Lay out the page

Pick the surface type, then follow the order literally. Every section below carries content,
not decoration. If a section has nothing real to say, delete it.

**Landing or marketing page**

1. Header: wordmark left, at most four links, one primary action right. Height 64px.
2. First viewport: the claim in at most nine words, one sentence of proof, one primary
   action, and one real artefact (screenshot, photograph, live demo, big number).
   Nothing below the fold pretends to be above it.
3. Proof: three to six real facts. Hairline rows or a plain grid, not three equal cards.
4. Mechanism: how it works, in two or three steps with real labels.
5. Objection: the one thing a sceptic asks, answered plainly. Pricing or limits belong here.
6. Close: repeat the primary action once, with one line of context.
7. Footer: real links, no fake social row.

**Product screen, dashboard or app**

1. Shell: sidebar or top nav, current location always visible, one primary action.
2. Content: the data first. Tables with hairlines and tabular numerals beat cards.
3. One primary action per view, in the same place on every view.
4. Every state that can happen: loading, empty, error, and the first-run screen.
5. Density is a feature: 8px rhythm, 36 to 40px row height, no decorative padding.

**Article, doc or guide**

1. Title, one line of context, then the text. No hero image unless it carries information.
2. Measure of 60 to 75 characters, 17 to 19px body, line height 1.6.
3. Headings from one level only where structure actually changes.
4. Code, tables and captions styled once, consistently.

**Portfolio or showcase**

1. The work in the first viewport, at the largest size the layout allows.
2. Captions as hairline metadata, never as marketing copy.
3. One navigation affordance, no scroll cue, no autoplay carousel.

Spacing rhythm for all of them: section padding `var(--s9)` desktop, `var(--s6)` mobile.
Space inside a group is always smaller than space between groups. More space above a heading
than below it. Breakpoints: one at 768px, one at 1024px. Test at 390px wide.

---

## Step 5. The twelve rules you may not break

1. One accent, one radius family, one type pair, one shadow scale, one icon set at one
   stroke weight. Per project, not per section.
2. No raw hex inside a component. Colour lives in the token block only.
3. No em dash and no en dash as punctuation. Use a comma, a colon or a period.
4. No kicker above a heading, no `01 /` section numbers, no scroll cue, no `Lorem ipsum`,
   no `Acme`, no `John Doe`, no emoji as icons, no gradient text.
5. Sentence case in headings and buttons. A button names its action: `Save changes`, not
   `Submit`. The toast after it says `Saved`.
6. Real copy, real numbers, real names, in the language of the request. Thin content is the
   loudest machine tell there is.
7. Every interactive element ships hover, `focus-visible`, active and disabled.
   Anything that fetches ships loading, empty and error.
8. Body text contrast at least 4.5:1. Control borders and large text at least 3:1.
   Hit targets at least 44px. Never remove the focus ring.
9. Animate `transform` and `opacity` only. Never `transition: all`. Under 300ms for UI.
   `ease-out` for entrances. `prefers-reduced-motion` ships in the same edit.
10. Images carry `width` and `height` or `aspect-ratio`, and `alt`. Below the fold they are
    `loading="lazy"`. The hero image is not lazy.
11. No `100vh` (use `100dvh`), no `overflow-x: hidden` to hide a layout bug, no positive
    `tabindex`, no `user-scalable=no`.
12. Delete one element before you finish. If nothing can go, you did not look.

---

## Step 6. Finish

**If you can run commands** (from the skill folder, pointed at the project):

```bash
node scripts/check.mjs .            # slop and craft linter, fix every ERROR
node scripts/wig.mjs .              # interface rules, file:line output
node scripts/contrast.mjs <tokens>  # WCAG measurement, never argue with the number
```

Fix everything in one batch. Run once more. Stop. Do not open a third round.

**If you cannot run commands**, read your own output once against this list and fix what fails:

- [ ] `lang` on `<html>` matches the language of the copy.
- [ ] Search the file for `—`, `–`, `...`, `Lorem`, `Acme`, `transition: all`, `100vh`,
      `outline: none`, `user-scalable`. Every hit is a fix.
- [ ] Every `img` has `alt` and dimensions. Every icon-only button has a name.
- [ ] One `h1`. No heading level skipped.
- [ ] Focus ring visible on every interactive element. Tab through the page in your head.
- [ ] Muted text is not lighter than `--ink-muted`. Nothing important is grey on grey.
- [ ] The 390px layout has no horizontal scroll and no text under 12px.
- [ ] Every value repeated three times is a token.
- [ ] The signature you named in Step 1 is actually visible in the result.
- [ ] One element deleted.

---

## Step 7. Report, at most five lines

```
Built:     <what, in one line>
Recipe:    <R#> because <one clause about the audience>
Signature: <the one moment>
Deleted:   <what you removed in the subtraction pass>
You supply: <real images, real copy, real data, keys>
```

No checklists in the answer. No self-congratulation. No list of the rules you followed.

---

## When LITE is not enough

Escalate to the FULL lane (`SKILL.md`) when the job is a whole product surface, a design
system, a redesign with a brand to respect, or an audit of someone else's code. LITE is a
floor high enough to ship. FULL is where a page becomes memorable.
