# Viora design evals

Twelve briefs. They exist because "the design got better" is not a claim anyone can check. Each brief
names a job, a mode, a stack and a lane, then states what a good answer has to hold and how a weak
answer usually fails. Run them when the skill changes, not when a project changes.

## How to run one

1. `node scripts/lane.mjs --probe` and take the lane it gives you. Do not pick the lane by feel.
2. Read the brief only. Stop before `Must hold`, that part is the answer key.
3. Build the thing, all seven gates in the FULL lane, the eight steps in LITE.
4. `node scripts/verify.mjs <paths>` until it prints one clean verdict.
5. `node scripts/score.mjs <paths>` for the four mechanical axes, then score the other four by eye
   with `evals/rubric.md` open.
6. Write the total, the weakest axis and one sentence on what you would change next. Nothing else.

One run of one brief is enough to catch a regression. Running all twelve is for a release.

## How to read a brief

`Job` is one of NEW, CHANGE, REDESIGN, REVIEW, FIX. `Mode` is LAND, APP, READ or SHOW. `Stack` is
FILE for a single artifact, PARTS for components in an existing codebase, APP for a running project.
`Lane` says which lane the brief is written for: some are deliberately given to LITE, because a weak
model has to survive them too.

---

## Brief 1. Logistics analytics, landing page

**Job** NEW | **Mode** LAND | **Stack** FILE | **Lane** FULL

The client sells route planning to mid-size delivery fleets. Buyers are operations managers who look
at spreadsheets all day and distrust anything that looks like a startup pitch. They asked for one
page that explains the product, shows the interface, and gets a demo booked. They have real product
screenshots and real customer names. No budget for photography.

**Must hold**
- A direction that is not the default cream and terracotta editorial look, and not near-black with a
  neon accent. Operations software has its own worlds: Swiss Utility, Technical Blueprint, Software Craft.
- The first viewport says what the product does for whom, in the client's words, not in adjectives.
- The interface screenshot is treated as the hero asset, framed and cropped deliberately, with space
  reserved so nothing jumps when it loads.
- Section rhythm varies. If every section is a centered heading over three cards, the page failed.

**Traps** A hero with a gradient mesh behind it. An eyebrow label above the h1. Invented numbers in a
stats band. Six identical feature cards. A scroll cue arrow.

**Mechanical floor** Zero errors from `check.mjs` and `wig.mjs`. `hue-count` and `card-monotony` are
the two warnings most likely to fire here, and both are usually real.

---

## Brief 2. Crypto treasury dashboard

**Job** NEW | **Mode** APP | **Stack** APP | **Lane** FULL

A finance team holds assets across several exchanges and wants one screen: total value, allocation,
recent transfers, and a way to move funds. Numbers change every few seconds. The people using it are
looking for one thing at a time, usually under pressure, and one of the actions is irreversible.

**Must hold**
- Density that suits a working screen, not a marketing page. Expression dial low, density dial high.
- Numbers in a tabular face, aligned on the decimal, never re-flowing as they tick.
- The irreversible action names what it does and what it affects, and is not the same button style as
  a safe action.
- Loading, empty, error and stale states all exist. A dashboard with only a happy path is a mockup.

**Traps** Glass panels stacked on a gradient. Green and red as the only signal for gain and loss.
A sparkline with no axis and no last value. Numbers formatted by hand.

**Mechanical floor** `wig.mjs` errors must be zero, especially `destructive-bare`, `hand-number` and
`tabular-nums-missing`.

---

## Brief 3. Private dental clinic, Russian copy

**Job** NEW | **Mode** LAND | **Stack** FILE | **Lane** FULL

Частная стоматология в спальном районе. Нужна страница: услуги, цены, врачи, запись. Аудитория
взрослая, платит из своего кармана и боится стоматологов. Тексты на русском, есть фотографии врачей
и кабинетов, снятые на телефон. Латиницы на странице нет вообще.

**Must hold**
- A type pair that actually covers Cyrillic. Check with `node scripts/pick.mjs "clinic" --cyrillic`.
  A Latin-only display face over Russian copy is an automatic fail, whatever it looks like in Latin.
- Calm clinical direction. Trust here comes from restraint, legible prices and real faces.
- Prices in a readable table with non-breaking spaces before the currency, not in cards.
- Photographs handled honestly: cropped, sized, given a consistent treatment. No stock replacements.

**Traps** Latin headings over Russian body text. Title Case in Russian headings. Teeth-white gradients.
A booking form with placeholders instead of labels.

**Mechanical floor** `cyrillic-latin-face` and `lang-copy-mismatch` must not fire. Run `node
scripts/ru.mjs <paths>` as well: Russian copy has its own typography rules.

---

## Brief 4. Longform article page

**Job** NEW | **Mode** READ | **Stack** FILE | **Lane** LITE

An investigative piece, about four thousand words, with pull quotes, two charts, one photograph and a
footnote section. It will be read on phones more than on desktops. The publication has no design
system yet, so whatever ships here becomes one.

**Must hold**
- One measure, held. Body text between sixty and seventy-five characters per line.
- A type scale with real steps, and a body size no smaller than 17 pixels on mobile.
- Quotes, charts and images interrupt the column deliberately, at a rhythm a reader can predict.
- Almost no motion. A reading surface that animates is a reading surface nobody finishes.

**Traps** Body text at 14 pixels. Justified text. Grey-on-grey body copy. A sticky bar covering four
lines of the article on mobile.

**Mechanical floor** `tiny-text`, `off-rhythm-space` and the contrast pairs. In the LITE lane this is
recipe R3 or R8 with the measure taken seriously.

---

## Brief 5. Product page for a small shop

**Job** NEW | **Mode** LAND | **Stack** PARTS | **Lane** FULL

A workshop sells one line of leather bags directly. Six colours, three sizes, real photography, a
waiting list for the sold-out variants. The codebase already exists in React with a token file the
previous developer left behind. The page must fit that token file, not replace it.

**Must hold**
- The variant picker shows availability before the click, not after. Sold out is a state, not an alert.
- Photography leads and the layout serves it. Type stays quiet.
- Add to cart gives feedback in place. No full-page reload, no toast that vanishes before it is read.
- The existing tokens are extended, not overwritten. New values are named the same way as the old ones.

**Traps** A carousel as the only way to see the photographs. Price without currency. A quantity input
that is a controlled field with no handler. Hover-only colour swatches.

**Mechanical floor** `wig.mjs` on the touched components: `value-no-onchange`, `hover-ungated`,
`image-hover`, `flex-truncate-minw`.

---

## Brief 6. Portfolio for an architecture studio

**Job** NEW | **Mode** SHOW | **Stack** FILE | **Lane** FULL

Six built projects, professional photography, a short studio statement, contacts. The partners are
precise people who dislike anything decorative. They want the work to be the only thing anyone
notices, and they want the site to feel like their buildings: quiet, exact, expensive.

**Must hold**
- Expression high, ornament low. The signature moment comes from scale, cropping or a single held
  gesture, not from effects.
- One clear silhouette. Squint at it: the layout should still read as a portfolio at 10 percent.
- Image loading planned. On this page a jumping layout reads as amateur work immediately.
- Project pages that use one grid, not six inventive ones.

**Traps** Gallery White done as a Bootstrap grid of equal thumbnails. A cursor follower. Parallax on
every image. A studio statement set in 40 pixel light grey.

**Mechanical floor** `img-no-dimensions`, `framework-default-shadow`, `center-everything`.

---

## Brief 7. Developer documentation

**Job** NEW | **Mode** READ | **Stack** PARTS | **Lane** LITE

An API reference plus guides for a small open source library. Readers arrive from search, land deep,
and need to copy code without reading the page. Dark mode is expected. There is no designer and
nobody will maintain anything clever.

**Must hold**
- Code blocks that are copyable, monospaced, with the language stated and no horizontal surprise.
- Navigation that shows where you are, at both levels, without a mystery hamburger on desktop.
- Dark mode from the same token file as light, both measured, not two hand-tuned palettes.
- One accent, used for links and the current item, and nowhere else.

**Traps** Two accents. Code blocks with a different font per language. A sidebar that scrolls the page
instead of itself. Search that is decorative.

**Mechanical floor** contrast in both modes, `color-scheme-missing`, `focus-ring-missing`.

---

## Brief 8. Courier app shell

**Job** NEW | **Mode** APP | **Stack** APP | **Lane** FULL

A delivery courier uses this on a phone, one hand, outdoors, in bright sun and in rain, sometimes
with gloves. Screens: today's route, one delivery, proof of delivery, problem report. Battery and
signal are both unreliable.

**Must hold**
- Targets sized for a thumb, at the bottom of the screen, never in the top corners.
- Contrast high enough for sunlight. This is the one brief where the accessible minimum is not enough.
- Safe areas respected, both notch and home bar. Overscroll contained.
- Every screen works offline or says clearly that it cannot.

**Traps** A desktop layout squeezed into 390 pixels. Icon-only buttons with no label. A confirmation
dialog for the action performed forty times a day. Swipe as the only way to do anything.

**Mechanical floor** `safe-area-missing`, `touch-action-missing`, `icon-button-unnamed`,
`overscroll-missing`.

---

## Brief 9. Admin console with bulk actions

**Job** CHANGE | **Mode** APP | **Stack** APP | **Lane** FULL

An internal tool where support staff manage accounts. The table exists and works. What is missing is
selection, bulk actions, filters that survive a page reload, and a delete flow that stops being
terrifying. Twelve thousand rows. Staff live in this screen for eight hours.

**Must hold**
- Filters and selection in the URL. A support agent has to be able to paste a link to a colleague.
- Keyboard everything: move, select, act, escape. Mouse-only is a defect in an eight-hour tool.
- Bulk delete states the count and the scope, and offers an undo window rather than a scarier dialog.
- Row density and column alignment fixed for scanning, not for looking modern.

**Traps** A checkbox column that is a div with an onClick. Selection lost on sort. A destructive button
with no name. Filter state only in React state.

**Mechanical floor** `url-state`, `div-click-target`, `destructive-bare`, `escape-close-missing`.

---

## Brief 10. Landing page for an AI product

**Job** NEW | **Mode** LAND | **Stack** FILE | **Lane** FULL

The hardest brief in the set, because the category has a house style and the house style is slop. A
team ships an agent that reads support tickets and drafts replies. They want the page to feel like
engineering, not like a pitch deck. They have a real demo video and two real customers.

**Must hold**
- Not one gradient orb, not one glowing border, not one purple to blue wash. If the page could belong
  to any other AI company, it failed.
- The demo is the hero. Everything else supports it.
- Claims are specific and attributable. "Drafts a reply in the client's tone" beats any adjective.
- One decision that no template would make, and a stated reason for it.

**Traps** The entire slop cluster: mesh gradient, eyebrow label, three-column feature cards with thin
icons, a stats band of invented numbers, dark mode with one neon accent, sparkle emoji as an icon.

**Mechanical floor** `ai-gradient`, `hero-mesh-blob`, `neon-glow`, `fake-stat`, `emoji-icon`. This is
the brief where the linter earns its keep.

---

## Brief 11. Insurance quote form

**Job** NEW | **Mode** APP | **Stack** PARTS | **Lane** LITE

Five steps, about twenty fields, including a date of birth, an address, a car registration and a
payment step. People abandon this form constantly. The client cannot change the questions, only how
they are asked.

**Must hold**
- One question group per step, with visible progress and a real back button.
- Labels above fields, always. Errors next to the field, after the field is left, in words.
- Correct autocomplete and input modes, so a phone keyboard shows digits for a registration number.
- Nothing blocks paste. Not on the email, not on the card, not anywhere.

**Traps** Placeholder as label. Validation on every keystroke. A date built from three selects. Paste
blocked on the confirmation field. Progress shown as a percentage that lies.

**Mechanical floor** `paste-blocked`, `placeholder-as-label`, `autocomplete-missing`, `submit-gated`,
`hand-date`.

---

## Brief 12. Redesign of a page that already exists

**Job** REDESIGN | **Mode** LAND | **Stack** FILE | **Lane** FULL

Take any page the model itself produced in an earlier run, or any real page with these symptoms: one
hero with a gradient, four equal cards, an eyebrow label, a stats band, two accents, body copy in
light grey, and a footer with nine columns. The brief is one sentence: make it look like a real
product made by people who care.

**Must hold**
- A named diagnosis before any new pixel. Which defects, in which order of harm.
- A different world, chosen deliberately, not the same page with new colours.
- Deletions counted and reported. A redesign that adds elements is not a redesign.
- The same content, rewritten only where the copy was the actual problem.

**Traps** Restyling the cards instead of questioning them. Keeping the eyebrow because it "balances"
the heading. Swapping the gradient for a different gradient. Adding motion to hide a weak layout.

**Mechanical floor** The before-page fails many rules by construction. The after-page must be clean,
and the report must state what was removed, not only what was added.

---

## What a run looks like when it is honest

```
brief 10, lane FULL, stack FILE
verify: check 0 errors 2 warnings, wig 0, contrast 0 failures in 30 pairs
score: direction 4, composition 4, type 5, colour 4, states 3, motion 5, copy 3, floor 5 = 33/40
weakest: states. The empty state of the ticket list is a sentence, not a designed surface.
next: give the empty state the same care as the hero, then re-score only that axis.
```

No other prose. The score is the report.
