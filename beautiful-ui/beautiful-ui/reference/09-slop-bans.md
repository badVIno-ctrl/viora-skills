# 09 - Slop bans

Load this when the output feels generic, when the user says "it looks AI-made", or when `scripts/check.mjs` reports something you do not understand. It is also the source list the checker implements.

These are not style preferences. They are the specific patterns that make a viewer think "a machine made this", which destroys the wow reaction no matter how good the rest is.

The examples below are literal characters. Copy the character, not the description.

## A. Text tells

| Banned | Why | Instead |
|---|---|---|
| The em dash `—` used as punctuation, and the en dash `–` outside number ranges | the single most recognisable machine tell in 2025 | comma, colon, full stop, or parentheses. En dash only between numbers: `10–20` |
| "It's not just X, it's Y" | template sentence | say the one true thing |
| `seamless`, `robust`, `powerful`, `cutting-edge`, `revolutionary`, `elevate`, `unlock`, `transform`, `game-changing`, `delve`, `leverage` | filler adjectives that carry no information | a concrete claim with a number or a mechanism |
| Title Case Headings Like This | marketing-deck voice | sentence case |
| Emoji as bullet points or icons | reads as a chat message, not a product | a real icon set, or nothing |
| Rhetorical question headings ("Ready to get started?") | filler | the actual proposition |
| `Lorem ipsum` | unfinished | real copy, in the product's language |
| `Acme`, `Acme Inc`, `Company Name`, `Your Brand` | placeholder | the real name, or a plausible invented one with a real-sounding domain |
| `John Doe`, `Jane Doe`, `John Smith`, `Jane Smith` | placeholder | plausible names matched to the region of the audience |
| `Nexus`, `NexusFlow`, `SmartFlow`, `TaskFlow`, `CloudSync`, `Cloudly`, `InnovateHub`, `TechFlow`, `DataFlow` | generated brand names | something with a reason behind it |
| `99.9%`, `99.99%`, `10,000+`, `$1,234,567`, `24/7` | invented-perfect statistics | real figures, or omit the stat entirely |
| Straight quotes `"` and `'` in prose | typographic laziness | `“ ”` and `’`, or `« »` for Russian |
| Three dots `...` | it is not an ellipsis and it breaks kerning | one character `…` |
| Poetic section labels: `The art of shipping`, `Where design meets engineering`, `Crafted with intention` | brochure voice with no claim in it | name what the section does |
| A language strip used as decoration: `EN / RU / DE` in the footer of a single-language page | signals a template, not a product | one language, or a switcher that works |
| Decorative version stamps: `v2.0`, a `Beta` badge on a product with no versioning | borrowed credibility | nothing, or a real changelog link |

## B. Layout tells

| Banned | Instead |
|---|---|
| Kicker / eyebrow: a small uppercase tracked label above a heading | let the heading be the heading. If context is needed, put it in the heading |
| Section numbers as decoration: `01 /`, `001 ~`, `Step 1`, `Phase 0`, `Stage Two` | real hierarchy through type and space |
| Scroll cues: `Scroll to explore`, a bouncing chevron, `↓` | if the page reads as scrollable, it is |
| Three equal cards, then three more equal cards | mix section families from `03-layout.md` |
| Icon + heading + two lines of text, repeated six times | one section that says something substantial |
| Hero metric row: three round numbers under the headline | one real number in context, or none |
| Centered everything | one alignment edge held down the page |
| A card wrapper around every list item | hairline rows |
| Nested cards | one surface level |
| Every section the same width | alternate contained, wide, bleed |
| Fake browser chrome built out of grey `div` bars | a real screenshot, a real component, or an honest illustration |
| A logo strip of invented company logos | real customers, or cut the section |
| Timeline with alternating left-right dots for two events | a simple list |
| A pricing table with a "Most popular" ribbon on the middle tier by reflex | mark it only if it is true |
| A middle-dot meta strip: three or more `·` separators on one line | two items, or a real layout |
| More than one `h1`, or a skipped heading level (`h2` then `h4`) | one `h1`, no gaps. Screen readers navigate by this |

## C. Colour and material tells

| Banned | Instead |
|---|---|
| Gradient text (`background-clip: text`) | solid ink. If emphasis is needed, use weight or size |
| Purple-to-blue gradient buttons with an outer glow | one solid accent |
| Radial mesh gradient blobs behind the hero | a real image, a flat field, or nothing |
| Glow as depth: `box-shadow: 0 0 40px <accent>` | offset plus blur, tinted from the ink hue |
| Hard offset shadows with no blur (`4px 4px 0`) | only in an explicitly neo-brutalist direction, never as a default |
| Glass on a flat colour | glass needs content behind it, or use a solid surface |
| Pure `#000` text, `#000` surfaces, or `#000` shadows | near-black ink on a near-black ground, shadows tinted from the ink hue |
| More than three chromatic hues in one interface | one accent plus semantics. The checker counts hue families |
| Two radius families in one interface, `4px` cards beside `16px` buttons | one family from `tokens.css`, top to bottom |
| Rainbow status colours used decoratively | semantic colours only for semantics |
| Dark mode by category habit (dev tool must be dark, wellness must be light) | decide from the user's actual scene |
| Ten accent sprinkles on a grey page | commit: either restrained-and-confident, or committed-as-fields |
| Neon on near-black as the default "modern" look | pick a world deliberately |

## D. Typography tells

| Banned | Instead |
|---|---|
| Display type at default tracking | `-0.02em` to `-0.04em` above 2rem |
| Uppercase without added tracking | `0.06em`-`0.1em`, and only for 1-2 word labels |
| A Latin-only face over Cyrillic copy | a family with the subset, from `04-typography.md` section 2 |
| Monospace on headings, buttons, or marketing prose | mono for code, IDs, keys, timestamps, aligned values |
| The default font stack as the display voice at `EXPRESSION >= 4` | a sourced face |
| Playfair Display, Fraunces, Instrument Serif, Space Grotesk, Outfit, Plus Jakarta, Poppins, Montserrat as a free choice | choose from `04-typography.md`, or justify in one line |
| Three or more families | two, plus mono if real code exists |
| Two icon sets, or two stroke weights inside one set | one set, one weight, one size scale |
| Body text below 16px | 16px floor on the web |
| Any text below 12px | 12px absolute floor |
| Text over an image with no scrim | a gradient scrim or a solid panel |
| Line length above 80 characters | `--measure: 68ch` |

## E. Motion tells

| Banned | Instead |
|---|---|
| `transition: all` | name the properties |
| `scale(0)` entrances | `scale(0.96)` |
| `ease-in` on an entrance | `--ease-out` |
| Fade-in-on-scroll for every section | show the content; animate one moment |
| Parallax on decorative elements | nothing, or a single restrained instance |
| Hover effects not gated by `@media (hover: hover)` | gate them |
| More than one marquee on a page | one, or zero |
| Animation driven by a scroll event listener | `animation-timeline: view()` or IntersectionObserver |
| Auto-rotating carousels | a grid, or manual control with visible affordances |
| A word that cycles inside the headline | one clear headline |
| Typewriter effect on the hero heading | let the words be readable at t=0 |
| Confetti on anything routine | reserve delight for genuinely rare moments |
| Spring bounce on modals and drawers | `--ease-out`, no bounce |
| An image that scales on hover for no reason | move the card, change the border, or nothing |
| Animating `width`, `height`, `top`, `left`, or `margin` | `transform` and `opacity`, or `interpolate-size` for height |
| Missing `prefers-reduced-motion` | ship it in the same commit |

## F. Code and production tells

| Banned | Why |
|---|---|
| `100vh` for full-height sections | broken on mobile browsers; use `100dvh` |
| `outline: none` without a visible replacement | removes keyboard accessibility |
| `!important` to win a cascade fight | the specificity is wrong |
| `z-index: 9999` | use a 5-step documented scale |
| Raw hex or magic px inside components | tokens exist for this |
| `<div onClick>` where a `<button>` belongs | breaks keyboard and screen readers |
| `<img>` without `alt` | fails the basic floor |
| An input with a placeholder and no label | the label vanishes the moment typing starts |
| An icon-only button with no accessible name | unusable by voice control and screen reader |
| `user-scalable=no`, `maximum-scale=1` | blocks zoom |
| Positive `tabindex` | destroys tab order |
| Hotlinked `images.unsplash.com` URLs | they rot; use a documented placeholder service and say so |
| Placeholder text left in production copy | unfinished |
| Console logs left in shipped UI code | unfinished |

## G. Structural tells

- **Thin content.** Four features described in five words each. Real products have specific, unequal, detailed things to say. Thin content is the loudest tell of all and no amount of styling hides it.
- **Symmetry everywhere.** Real compositions have deliberate imbalance. Perfect symmetry in every section reads as a template.
- **Uniform density.** A page where every section has the same amount of content and the same visual weight has no rhythm and no emphasis.
- **No opinion.** Nothing on the page could be argued with. Design carries a point of view; a page that offends nobody impresses nobody.
- **Aesthetic cluster reflex.** Cream plus serif plus terracotta, or near-black plus neon. See `01-direction.md` section 3.

## H. What is mechanically enforced

`scripts/check.mjs` implements 49 rules across `.css`, `.scss`, `.html`, `.vue`, `.svelte`, `.astro`, `.js`, `.jsx`, `.ts`, `.tsx`, `.md`, and `.mdx`. Run `node scripts/check.mjs --list-rules` for the current list. The mapping from this document:

| Section | Rule ids |
|---|---|
| A | `em-dash`, `filler-words`, `lorem`, `slop-names`, `fake-stat`, `poetic-label`, `locale-strip`, `version-stamp` |
| B | `eyebrow`, `section-number`, `scroll-cue`, `middle-dot-strip`, `h1-multiple`, `heading-skip` |
| C | `gradient-text`, `neon-glow`, `pure-black-text`, `pure-black-surface`, `raw-hex`, `hue-count`, `radius-family` |
| D | `banned-font`, `font-count`, `cyrillic-latin-face`, `tiny-text`, `icon-stroke-mixed` |
| E | `transition-all`, `scale-zero`, `ease-in-enter`, `transition-layout`, `slow-motion`, `scroll-listener`, `motion-axis-keys`, `hover-ungated`, `marquee-multi`, `image-hover`, `reduced-motion-missing` |
| F | `vh-height`, `focus-none`, `focus-ring-missing`, `important`, `zindex-high`, `img-no-alt`, `viewport-no-zoom`, `tabindex-positive`, `icon-button-unnamed`, `emoji-icon`, `placeholder-as-label` |

`scripts/contrast.mjs` covers what a text search cannot: it resolves `var()`, `color-mix()`, `oklch()`, and `hsl()` in both themes and measures every pair in the contract. The contrast claims in section C are checked there, not here.

Section G and the composition judgements in section B are not machine-checkable. That is what the squint test at G6 and the review pass in `10-review.md` are for.

## How to use this list

Do not read it start to finish before building; that wastes context. Use it three ways:

1. Run `node scripts/check.mjs .` and `node scripts/contrast.mjs <token file>` at G6. Fix every error, decide every warning.
2. When the user says the output looks generic, read sections A, B, and G and rework the composition, not the colours.
3. When you are about to reach for a pattern you have used before, check whether it appears here.

Suppression: if a ban genuinely does not apply (a neo-brutalist direction that wants hard shadows, an editorial piece that wants section numbers), add `/* bui-allow: RULE-ID reason */` next to the code so the decision is visible and the checker stays quiet.
