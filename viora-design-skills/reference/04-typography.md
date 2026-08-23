# 04 - Typography

Loaded at G4 when type is being decided. Purpose: choose a voice and a scale that carry the direction. Close when the pair is loaded and the scale is in `tokens.css`.

Type does more for perceived quality than any other single decision. A page with excellent type and no colour looks designed. A page with a beautiful palette and default type looks generated.

## 1. The scale

`assets/tokens.css` is the single source of truth. This table mirrors it, and if the two ever disagree the file wins. Every step has a matched line-height and tracking, and those pairings are the whole point.

| Token | Size | Line-height | Tracking | Use |
|---|---|---|---|---|
| `--text-display-1` | `clamp(2.5rem, 1.55rem + 3.8vw, 5rem)` | 0.98 | -0.035em | one per page, the statement |
| `--text-display-2` | `clamp(2rem, 1.45rem + 2.2vw, 3.5rem)` | 1.02 | -0.03em | section openers |
| `--text-h1` | `clamp(1.75rem, 1.4rem + 1.2vw, 2.25rem)` | 1.1 | -0.022em | page title in an app or article |
| `--text-h2` | `clamp(1.375rem, 1.25rem + 0.6vw, 1.625rem)` | 1.2 | -0.016em | section heading |
| `--text-h3` | `1.25rem` | 1.3 | -0.01em | subsection, card title |
| `--text-h4` | `1.0625rem` | 1.35 | -0.005em | row title, dense list heading |
| `--text-lg` | `1.125rem` | 1.6 | -0.005em | lead paragraph |
| `--text-base` | `1rem` | 1.55 | 0 | body. Never below 16px for body on the web |
| `--text-sm` | `0.875rem` | 1.5 | 0 | secondary, table cells, captions |
| `--text-xs` | `0.75rem` | 1.4 | 0.008em | meta, badges. Absolute floor |

Hard rules:

- **Tracking is a function of size.** Large text needs negative tracking; small text needs zero or slightly positive. Display type at default tracking is the most common amateur tell. Floor is `-0.04em`; below that, letters collide.
- Line-height is inverse to size: display 0.95-1.05, headings 1.1-1.3, body 1.5-1.65, small print 1.4-1.5.
- Maximum four sizes on one screen. More than that and the hierarchy stops meaning anything.
- Use weight and colour for hierarchy before reaching for another size.
- Never use `text-transform: uppercase` with default tracking. Uppercase requires `0.06em`-`0.1em`. And per the bans, uppercase micro-labels above headings are out entirely.

## 2. Pairing

One display face plus one text face. Or one excellent variable family used across the range with real weight contrast. Two faces maximum, plus a mono **only if real code or real values appear**.

Ten pairings that work. Choose by world, not by taste.

| # | Display | Text | Mono | Source | Reads as | Cyrillic |
|---|---|---|---|---|---|---|
| 1 | Geologica 600 | Inter 400 | JetBrains Mono | Google | precise, technical, current | yes |
| 2 | Unbounded 700 | Onest 400 | - | Google | expressive, contemporary | yes |
| 3 | Manrope 700 | Manrope 400 | IBM Plex Mono | Google | geometric, friendly, calm | yes |
| 4 | Golos Text 600 | Golos Text 400 | - | Google | institutional, plain-spoken | yes |
| 5 | Source Serif 4 600 | Commissioner 400 | - | Google | authored, trustworthy | yes |
| 6 | Literata 600 | IBM Plex Sans 400 | - | Google | editorial, readable | yes |
| 7 | Schibsted Grotesk 600 | Schibsted Grotesk 400 | Geist Mono | Google | precise, modern, neutral | no |
| 8 | Instrument Sans 600 | Instrument Sans 400 | JetBrains Mono | Google | clean, slightly warm | no |
| 9 | Bricolage Grotesque 700 | Inter 400 | - | Google | characterful, editorial-modern | no |
| 10 | Satoshi 700 | Switzer 400 | - | Fontshare | contemporary product | no |

Both sources are free for commercial use: Google Fonts (`fonts.google.com`) and Fontshare (`fontshare.com`). **Verify the family actually loads** before building on it: request it once, and if the request fails, fall back to the nearest family in the table and note the substitution. Do not ship a stylesheet referencing a family that 404s.

### Alphabet coverage is a build failure, not a nicety

If the copy contains Cyrillic and the display face has no Cyrillic subset, the browser silently substitutes a system font, and the design you chose does not exist for that reader. `scripts/check.mjs` reports this as the error `cyrillic-latin-face`, so it cannot pass unnoticed.

- Cyrillic copy: choose from rows 1 to 6, or verify another family subset list yourself.
- Latin-only copy: any row is available.
- Mixed copy: one family covers both alphabets, or the two faces are metrically close enough that the switch is invisible. Two visibly different faces for two alphabets in one paragraph is worse than a system font.
- Mono with Cyrillic: JetBrains Mono, IBM Plex Mono, Fira Code. Geist Mono has none.
- Wider Cyrillic pool: Inter, Manrope, Onest, Golos Text, Geologica, Commissioner, IBM Plex Sans, Fira Sans, Rubik, PT Sans, PT Serif, Bitter, Literata, Source Serif 4.

### Banned as defaults

These are not bad faces. They are the faces a model reaches for when it is not choosing, so they now signal "not chosen":

Playfair Display, Fraunces, Instrument Serif, Cormorant, DM Serif, Lora, Newsreader, Space Grotesk, Outfit, Plus Jakarta Sans, Poppins, Montserrat, Raleway, Bebas Neue.

Allowed when the user pins them, or when the direction genuinely requires that exact face and you say why in one line.

### Also banned

- The system font stack as the display voice when `EXPRESSION >= 4`. Inter, Helvetica, SF, Segoe, Roboto are correct for body and for `APP` chrome, and Inter is the token default for exactly that reason. None of them is a decision at high expression.
- Monospace as costume: mono on headings, buttons, or marketing prose. Mono is for code, IDs, keyboard keys, timestamps, and numeric values that must align.
- Three or more families.
- A second face that is nearly the same as the first. Contrast or nothing.

## 3. Loading

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geologica:wght@400;600&family=Inter:wght@400;500;600&display=swap">
```

- Always `display=swap`.
- Load only the weights you use. Four weights maximum. Every extra weight is bytes and none of them are seen.
- Prefer variable fonts when available: one file, any weight.
- Next.js: `next/font/google` with `display: 'swap'`, exposed as a CSS variable and wired into `--font-display` / `--font-text` in `tokens.css`.
- Self-hosted: `woff2` only, `font-display: swap`, subset to the character sets actually used. Include Cyrillic when the content is Russian - a Latin-only subset silently falls back and the page looks broken.
- Set fallbacks in the same metric class to reduce layout shift: `font-family: var(--font-text), ui-sans-serif, system-ui, sans-serif`.

## 4. Details that separate good from beautiful

| Detail | Rule |
|---|---|
| Headline wrapping | `text-wrap: balance` on headings. Prevents a single orphan word |
| Paragraph wrapping | `text-wrap: pretty` on body |
| Numerals in tables | `font-variant-numeric: tabular-nums` so columns do not jitter |
| Numerals in prose | proportional is correct here, do not force tabular everywhere |
| Links in prose | `text-underline-offset: 0.15em; text-decoration-thickness: 1px`. Never remove the underline in body copy |
| Quotes | typographic `“ ”` for English, `« »` for Russian. A straight `"` is a tell |
| Apostrophe | `’`, never `'` |
| Ellipsis | one character `…`, never three dots `...` |
| Ranges | en dash `–` between numbers, as in `10–20`. The em dash `—` is banned everywhere, in every language |
| Non-breaking space | between a number and its unit, and before a lone final word in a heading |
| Widows | no single word alone on the last line of a heading or a short paragraph |
| Optical alignment | quote marks, bullets, and italic overhangs hang outside the text edge |
| All-caps | only for 1-2 word labels, with `0.08em` tracking |
| Italic | for emphasis and titles, never for whole paragraphs |
| Language | set `lang` on `<html>` so hyphenation and quotes are correct |
| Cyrillic | confirm the face has the subset before using it for Russian copy. Many display faces do not. See section 2 |

## 5. Hierarchy without size

When a screen needs more levels than four sizes allow:

1. Weight: 400 body, 500 emphasis, 600-700 headings. A jump of 200 or more is legible; 100 is invisible.
2. Colour: `--ink` for primary, `--ink-muted` for secondary. This is the cheapest and most effective level.
3. Space: separation encodes grouping more strongly than size does.
4. Case and tracking: only within the rules above.
5. Position: an indented or offset block reads as subordinate without any style change.

## 6. Copy quality

Type only looks good if the words are worth reading.

- Sentence case for headings and buttons. Title Case is a tell; ALL CAPS in a heading is worse.
- Buttons name their action: `Create project`, not `Submit`, not `Get started` on a form.
- Headings say something specific and falsifiable. `Deploy in 40 seconds` beats `Ship faster than ever`.
- No filler adjectives: `seamless`, `robust`, `powerful`, `cutting-edge`, `revolutionary`, `elevate`, `unlock`, `transform`, `game-changing`, `delve`, `leverage`. The checker flags each of these by name.
- Errors say what happened and what to do next. Empty states say what goes here and offer the action that fills it.
- Numbers must be plausible and specific. `99.99% uptime`, `10,000+ users`, `$1,234,567` are invented-looking. Use real figures or none.
- Match the product's language. If the content is Russian, everything is Russian, including button labels and empty states. Do not mix languages in one interface.

## Output of this gate

Type pair loaded and wired into `--font-display` / `--font-text`, scale in place, tracking applied at display sizes. Continue G4.

## Script and language

The copy language is the language of the request, and it decides three things before any font is chosen.

**The pool.** A Cyrillic interface can only use faces that ship Cyrillic. Golos Text, Inter, Manrope, IBM Plex Sans, Onest, Geologica, Roboto Flex, Noto Sans, JetBrains Mono and Fira Code do. Most display darlings do not, and the page silently falls back to a system font, which is the most common way a Russian layout dies. The default stack in `assets/tokens.css` already lists a Cyrillic-safe fallback before the generic one.

**The marks.** Russian uses guillemets for quotes and a hyphen or spaced dash for parentheticals: «Севзапфрахт», not "Севзапфрахт". English uses curly double quotes. German uses low-high. Getting this wrong reads as a machine translation of a template, which is exactly the impression the whole skill exists to avoid.

**The numbers.** Russian groups thousands with a thin space and puts the currency after the amount: 184 200 ₽. English groups with a comma and puts the symbol first: $184,200. Both need `font-variant-numeric: tabular-nums` in any column that is read vertically.

Declare the language on the document. `check.mjs` fails a missing `lang` and fails a document that declares English while the copy is Cyrillic.
