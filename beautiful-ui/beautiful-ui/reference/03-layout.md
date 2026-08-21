# 03 - Layout

Loaded at G3 after tokens. Purpose: plan the page as an argument, not as a stack of boxes. Close when the section plan is written.

The single most recognisable AI layout is: centered hero, three equal cards, three more equal cards, a logo strip, a final centered call to action. Every section has the same shape, the same width, the same rhythm. Fixing that is worth more than any colour decision.

Three of the ten laws are won or lost in this file. **Silhouette**: at icon size the page must still have a recognisable shape, and only distinct section families produce one. **Hierarchy**: the eye must be able to rank the elements before reading a word. **Subtraction**: if a section can go, it goes. `node scripts/shot.mjs <url> --squint` and `--icon` are how you check all three without lying to yourself.

## 1. Section families

Build the page from **distinct families**. Use each family at most once per page.

| # | Family | Shape | Carries |
|---|---|---|---|
| 1 | Statement | few words at display scale, huge air, one action | positioning |
| 2 | Split | text one side, artefact the other, unequal ratio (55/45, 62/38) | mechanism, product truth |
| 3 | Bleed | full-width image or panel, type overlaid | atmosphere, scale |
| 4 | Ledger | rows separated by hairlines, no boxes | features, specs, changelog, pricing rows |
| 5 | Stack | numbered or sequential steps down the page, each step wider or narrower | process, onboarding |
| 6 | Mosaic | deliberately unequal grid, one large plus several small | gallery, use cases, integrations |
| 7 | Detail | one small thing, enormously enlarged, with a caption | craft, a single killer feature |
| 8 | Quote | one voice at reading scale with attribution, real name and role | proof |
| 9 | Table | real comparison or data with aligned numerals | pricing tiers, specs |
| 10 | Marquee | one horizontal motion band, used **once** | logos, breadth |
| 11 | Terminal | code, log, or config as content, monospaced, real | technical credibility |
| 12 | Close | the last decision, minimal, one action, no new information | conversion |

Rules:

- **Maximum two card-based sections per page**, and never two in a row. Cards are a container of last resort, not a layout.
- No two adjacent sections may share the same content width. Alternate contained, wide, and full-bleed.
- Section count: `LAND` 5-8, `SHOW` 4-6, `READ` follows the document, `APP` has no sections, it has regions.
- If two sections carry the same kind of content, merge them or cut one.
- **Family coverage**: at least 4 distinct families on any page of 6 or more sections. Three families stretched across eight sections is exactly the template look.
- **Zigzag ceiling**: at most 2 alternating left-right splits in a row. The third alternation stops being rhythm and becomes a pattern the reader can predict and skip.
- **Eyebrow ceiling**: eyebrow or kicker labels on no more than `ceil(sections / 3)` sections, and never in the first viewport. The checker counts them and raises `eyebrow`.
- Section headline: 8 words maximum. If it needs more, it is a paragraph and belongs in the body.

## 2. First viewport

The first screen decides everything. Requirements:

1. It says what the thing **is** in seven words or fewer, in the product's own vocabulary. Not "Transform your workflow". What it is.
2. Exactly one primary action, visually unambiguous. A secondary action is allowed at lower weight; a third is a failure to decide.
3. Something real is visible: the actual product, an actual artefact, an actual photograph. Not an abstract gradient blob, not a floating glass card with three fake rows.
4. It is composed, not centered by default. Off-center, asymmetric, or grid-anchored beats centered unless the world is Gallery White or Statement-led.
5. It ends deliberately. Either the next section is clearly cut off at a meaningful place, or the fold is respected. Never let a section end 40px below the fold by accident.

Counted limits for the first viewport, because "restraint" is not a number:

- At most **4** elements above the fold: headline, one supporting line, one action group, one real artefact. A badge, a stat row, a logo strip, and a scroll cue are four separate ways to break this.
- Headline: **2 lines maximum** at the intended desktop width, 7 words or fewer.
- Supporting line: **20 words maximum**, one sentence, and it must carry a fact the headline does not.
- Nav height 56-72px, never above 80px, and it is not one of the four elements.

Banned in the first viewport: kicker above the headline, a scroll cue, a rotating word in the headline, a stat row of round invented numbers, a floating browser chrome mockup containing grey placeholder bars.

## 3. Navigation

- Under 5 primary destinations: inline links. 5 or more: group them.
- Logo left, primary action right, links between. Deviate only for a real reason.
- Sticky nav must change on scroll: gain a hairline or a background, lose height. A nav that floats unchanged over content looks unfinished.
- Height 56-72px desktop, 52-60px mobile. Never taller than 80px.
- Mobile: a real menu with a focus trap, `Escape` to close, body scroll locked, and a working close affordance. Never a menu that pushes content down and breaks the layout.
- Active state must be visible without hovering.
- The current page's nav item is not a link to itself.

## 4. Rhythm

Spacing is where craft is felt without being noticed.

| Relationship | Rule |
|---|---|
| Section vertical padding | `--space-14` to `--space-16` desktop, roughly 60% of that on mobile |
| Heading to its body | `--space-3` |
| Body to next heading | `--space-8` or more. **Space above a heading is always larger than space below it.** |
| Inside a card | one padding value on all sides, `--space-5` or `--space-6` |
| Between siblings in a group | `--space-4` |
| Between groups | `--space-8` or more |
| Label to its field | `--space-2` |
| Field to next field | `--space-5` |
| Icon to its text | `--space-2`, and optically aligned, not box-aligned |

Proximity encodes grouping. If related items are the same distance apart as unrelated items, the layout carries no information. When something reads as "almost right", the cause is nearly always a spacing relationship, not a colour.

## 5. Grid, measure, alignment

- 12 columns desktop, 6 tablet, 4 mobile. Content spans meaningful column counts, not arbitrary percentages.
- Body text measure: 60-75 characters. Use `--measure` (`68ch`). A paragraph running 120 characters wide is unreadable no matter how good the type is.
- Establish one left alignment edge and hold it down the page. Optical alignment beats box alignment: a quote mark, a bullet, or an italic overhang should hang outside the edge so the text edge stays straight.
- Centered text: only for a Statement or a Close family, and never for more than three lines.
- Numbers in columns: right-aligned with tabular figures, always. See `.tnum` in `tokens.css`.

## 6. Responsive

Design the mobile layout, do not shrink the desktop one.

| Breakpoint | Width | Behaviour |
|---|---|---|
| base | 0-639 | single column, full-bleed media, stacked nav, 16-20px gutters |
| sm | 640 | two-up where it helps, larger gutters |
| md | 768 | tablet, sidebars may appear |
| lg | 1024 | intended desktop composition |
| xl | 1280 | max content width engages, extra space becomes margin |
| 2xl | 1536 | never let line length grow, cap the container |

Per-section collapse must be decided, not inherited:

- Split sections stack with the **artefact first** if the artefact is the argument, text first if the text is.
- Mosaic collapses to one column with the large item first, not to a uniform grid.
- Tables become stacked labelled rows on mobile, never a horizontal scroll of 8 columns without a sticky first column.
- Multi-column marketing type collapses to one column at md, not sm.

Hard requirements:

- `min-height: 100dvh`, never `100vh`. `100vh` is broken on mobile browsers.
- Nothing scrolls horizontally at 320px wide. Check it.
- Touch targets >= 44x44px with >= 8px between them.
- Respect safe areas: `padding-bottom: max(var(--space-4), env(safe-area-inset-bottom))` on fixed bottom bars.
- Fluid type via `clamp()` between the base and xl breakpoints, so there is no snap.

## 7. Density by mode

- `APP` at `DENSITY 4-5`: 32-40px row height, 12-14px labels, hairline separation, no card wrapper per row, sticky headers, action columns right-aligned.
- `LAND` at `DENSITY 2`: fewer elements, bigger type, more air, one idea per section.
- `READ`: one column, 68ch, generous leading (1.6-1.75), clear heading hierarchy, no sidebars competing with the text.
- Empty space is a material. If a page has no area with nothing in it, it will read as cramped regardless of spacing values.

## 8. Anti-patterns

| Never | Instead |
|---|---|
| Three equal cards, three more equal cards | Ledger, then Split, then Mosaic |
| Every section the same width | alternate contained / wide / bleed |
| Icon plus heading plus two lines, six times | one Detail section that earns its space |
| Centered everything | one alignment edge, held |
| A card wrapping every list item | hairlines between rows |
| Nested cards | one surface level, hairlines inside |
| Equal space above and below headings | more above than below |
| `100vh` hero | `100dvh` or content-driven height |
| Section numbers or eyebrow labels to create structure | let type scale and space carry hierarchy |
| A middle-dot meta strip: `Fast · Secure · Simple` | one line of real copy, or a Ledger row per claim |
| A decorative language strip or a `v2.0` badge in the footer | a switcher that works, or nothing |
| Identical section padding from top to bottom | padding varies with the weight of the section |
| A section that exists because the page felt short | cut it. A shorter page that argues beats a longer one that pads |

## Output of this gate

A short section plan, one line per section: name, family, content. Then print the marker and start G4.

```
G3 frame: tokens installed, 6 sections / 6 families
1 Statement  - what it replaces, one action
2 Split 62/38 - live product panel, mechanism in 3 lines
3 Ledger     - 5 capabilities as hairline rows with real values
4 Terminal   - actual config, 12 lines, copyable
5 Quote      - one named customer, real role
6 Close      - single action, no new claims
```
