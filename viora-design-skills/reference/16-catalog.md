# 16 - The catalog

Loaded at G2 and G3, when direction needs raw material instead of taste. `01-direction.md`
decides *which world*. This file supplies the concrete rows inside that world: a palette
built for the product type, a type pair that ships the right script, a landing pattern, the
motion tier, and the list of things that are specifically wrong for this industry.

Origin: `data/` is a curated copy of the offline design corpus from
`github.com/nextlevelbuilder/ui-ux-pro-max-skill` (MIT), with the oversized font and icon
dumps removed, plus `cyrillic-pairs.csv` written for this skill. Search runs locally with
`node`, no network, no Python, no install.

**The catalog is raw material, not a decision.** It removes guessing about hex values and
font pairings. It cannot tell you what the surface is about. Direction still comes first,
always. A palette pulled without a thesis produces a competent page nobody remembers.

## 1. What is in `data/`

| File | Rows | What you get |
|---|---|---|
| `palettes.csv` | 192 | a full token set per product type: primary, on-primary, secondary, accent, background, foreground, card, muted, border, destructive, ring, plus notes |
| `type-pairs.csv` | 74 | display plus body pairings with mood keywords, what they suit, the Google Fonts URL and the CSS import |
| `cyrillic-pairs.csv` | 26 | the same, restricted to faces that actually ship Cyrillic |
| `styles.csv` | 88 | 79 named visual styles: keywords, colours, effects, what they are for, **what they must not be used for**, light and dark support, performance, complexity, era, implementation checklist |
| `products.csv` | 192 | product type to recommended style, landing pattern, dashboard style, palette focus, key considerations |
| `landing.csv` | 34 | landing page patterns: section order, CTA placement, colour strategy, conversion notes |
| `ux-rules.csv` | 119 | UX rules with severity, do, don't, and a good and bad code example each |
| `app-interface.csv` | 32 | the same, for in-product screens |
| `motion.csv` | 17 | motion by intensity tier: trigger, duration, easing, snippet, performance notes |
| `icons.csv` | 105 | icon names by semantic role, library, import code, allowed contexts |
| `charts.csv` | - | chart type selection and data-ink guidance |
| `ui-reasoning.csv` | 192 | per UI category: recommended pattern, decision rules as JSON, anti-patterns, confidence |
| `react-performance.csv` | - | React-specific performance rules |
| `stacks/*.csv` | 22 stacks | per-stack implementation notes: where tokens live, what the idiomatic component looks like |

## 2. How to query it

```bash
node scripts/pick.mjs "fintech dashboard trust" --domain palette
node scripts/pick.mjs "editorial long read" --domain type
node scripts/pick.mjs "russian saas landing" --domain type --cyrillic
node scripts/pick.mjs "brutalist" --domain style
node scripts/pick.mjs "medical booking" --domain product
node scripts/pick.mjs "pricing objection" --domain landing
node scripts/pick.mjs "modal focus trap" --domain ux
node scripts/pick.mjs "page transition" --domain motion --tier subtle
node scripts/pick.mjs "nextjs" --domain stack
node scripts/pick.mjs "b2b analytics for ops teams" --system
```

- `--system` runs the whole set at once and prints one bundle: palette, type pair, style,
  landing pattern, motion tier, and the anti-patterns for that product type. Use it once, at
  G2, then stop searching.
- `-n 3` changes the result count, `--json` gives machine output, `--list-domains` lists what
  is queryable, `--cyrillic` restricts type results to faces that ship Cyrillic.
- Queries work in Russian and English. `банковский дашборд` finds rows tagged `banking`,
  `finance`, `dashboard`.

If `node` cannot run, do not stop and do not guess: use the digest in section 4 below. It is
small on purpose so it works in a single-file context.

## 3. How to use a result without going generic

1. **Direction first.** Write the thesis and pick the world from `01-direction.md`.
2. **Then pull.** One `--system` call. Read the rows once.
3. **Take what is raw material, not the whole row.** Take the hex values, the font pair, the
   `Do Not Use For` column and the anti-patterns. Ignore any row's suggestion to add
   "glassmorphism with animated gradient blobs" and similar era decoration: the ten laws in
   `SKILL.md` and the bans in `09-slop-bans.md` outrank every catalog row.
4. **Adapt, do not paste.** A catalog palette gives you a starting hue relationship. Run it
   through `02-tokens.md` and then through `node scripts/contrast.mjs`. Numbers decide, not
   the CSV.
5. **Rotate.** If the catalog's top row for this product type is the same one you used last
   time, take the second or third row. Repetition across projects is how a house style turns
   into a template.
6. **Cyrillic.** If the copy has Cyrillic, use `cyrillic-pairs.csv` or `--cyrillic`. Most of
   the fashionable Latin faces in `type-pairs.csv` have no Cyrillic and will fall back to a
   system font. `check.mjs` catches this, but catching it at G3 is cheaper.

Conflict rule, in order: the ten laws, then this skill's reference files, then the catalog.
The catalog is inventory. The laws are the standard.

## 4. Offline digest, when scripts cannot run

Eight complete packages. Each one is a full direction: ground, ink, one accent, a type pair
that ships Cyrillic, a radius family, and the move that carries the page.

| # | World | Ground / ink / accent | Type pair | Radius | Best for | Wrong for |
|---|---|---|---|---|---|---|
| 1 | Swiss Utility | `#ffffff` / `#16171a` / `#1d4ed8` | Manrope + Inter | 4px | B2B tools, admin, docs | anything that must feel warm |
| 2 | Software Craft | `#0b0c0e` / `#f2f3f5` / `#5b7cfa` | Manrope + Inter + JetBrains Mono | 8px | devtools, infra, analytics | consumer retail |
| 3 | Editorial Broadsheet | `#faf7f2` / `#1c1a17` / `#8a3324` | Playfair Display + PT Serif | 0px | long reads, manifestos | dense dashboards |
| 4 | Nordic Clinical | `#f8fafa` / `#12201f` / `#0f766e` | Onest + Inter | 10px | health, fintech, forms | nightlife, gaming |
| 5 | Industrial Signal | `#111111` / `#f5f5f4` / `#ea580c` | Oswald + Inter | 2px | hardware, logistics, sport | wellness, luxury |
| 6 | Solar Optimist | `#fffaf3` / `#231a12` / `#c2410c` | Unbounded + Nunito Sans | 16px | consumer, education | enterprise security |
| 7 | Botanical Calm | `#f7f8f4` / `#161d17` / `#2f6b4f` | Lora + Golos Text | 14px | food, wellness, retreats | high-frequency tools |
| 8 | Gallery White | `#ffffff` / `#111111` / `#111111` | Tenor Sans + Inter | 0px | portfolio, photography | data-heavy products |

Product type to world, when the brief gives no other signal:

| Product type | Start with | Never start with |
|---|---|---|
| Developer tool, API, CLI, infra | 2, 1 | 6, 7 |
| B2B SaaS, admin, internal tool | 1, 2 | 6, 8 |
| Fintech, banking, insurance | 4, 1 | 6, and no AI gradient anywhere |
| Health, clinic, medtech | 4, 7 | 5, 3 |
| Government, education, civic | 1, 4 | 6, 8 |
| Marketplace, retail, D2C | 6, 5 | 3 |
| Media, blog, newsletter, docs | 3, 1 | 5 |
| Agency, studio, portfolio | 8, 3 | 4 |
| Food, hospitality, travel | 7, 6 | 2 |
| Sport, automotive, construction | 5, 2 | 7 |
| Luxury, jewellery, real estate | 8, 3 | 6 |
| Crypto, web3 | 2, 5 | the purple to blue gradient, always |

Cyrillic-safe pairings, short list: Manrope + Inter, Onest + Inter, Golos Text + Inter,
Unbounded + Nunito Sans, Playfair Display + PT Serif, Lora + Golos Text, Cormorant Garamond
+ Golos Text, Oswald + Inter, PT Serif + PT Sans, IBM Plex Serif + IBM Plex Sans, Prata +
Inter, Tenor Sans + Inter. Mono: JetBrains Mono, IBM Plex Mono, Fira Code, Source Code Pro.
Full list with URLs in `data/cyrillic-pairs.csv`.

Industry anti-patterns worth memorising:

- **Fintech and banking:** no AI gradients, no neon on dark, no playful rounded display face.
  Trust reads as precision, tabular numerals and generous whitespace.
- **Health:** no black grounds, no aggressive reds outside real errors, no thin grey text.
- **Developer tools:** no stock photography of people, no hand-drawn illustration, no
  marketing gradient. Show the product, show real output.
- **Luxury:** no drop shadows on everything, no busy gradients, no more than one accent.
  Space is the material.
- **Government and civic:** no trend styling at all. Legibility, contrast, plain language.
- **Children and education:** high contrast, large targets, no thin weights.
- **Enterprise security:** no dark neon hacker theme. It reads as a toy.

## 5. Persisting a decision

When a project will be extended later, write the chosen rows into `DESIGN.md`
(see `12-design-md.md`) under the token contract. Any future run, at any model tier, reads
that file and matches instead of re-deciding. A palette that changes between two sessions is
the most visible failure this skill can have.

## 6. Output of this gate

One line in the G2 marker naming what you took: `catalog: palette 47 fintech-trust,
type 12 Manrope/Inter, landing pattern 6, motion tier subtle`. Then close the catalog and
build. Do not keep searching while you design.

## 7. From a catalog row to a token block

`--css` turns the palette row you picked into the block that goes into `assets/tokens.css`:

```bash
node scripts/pick.mjs "logistics operations dashboard" --domain palette --css
```

It prints an `EDIT 1` block with light and dark values for every token the contract needs, plus a
comment naming the row it came from, so in six months the file still says where the colour was
decided. It also checks that the accent is an accent: when the row's primary is a near-neutral
surface colour, it says so instead of letting a grey accent through as an action colour.

Then measure, because a catalog row is a starting point and not a guarantee:

```bash
node scripts/contrast.mjs assets/tokens.css
```

If a pair fails, change the token, never the requirement. `assets/palettes.css` holds 13 palettes
that already pass all 30 pairs in both modes, and any of them can be pasted in whole.
