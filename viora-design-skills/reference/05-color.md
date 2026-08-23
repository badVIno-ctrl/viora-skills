# 05 - Color

Loaded at G4 when colour is being decided. Purpose: install a palette that is already balanced and already accessible, instead of guessing hex values. Close when the palette is in `tokens.css`.

Every palette below is ready to paste. Take one whole palette. Do not mix rows from two palettes: the neutrals are hue-matched to their accent, and swapping breaks that.

## How to use

1. Find the palette id from your world in `01-direction.md`.
2. Paste the values into the `EDIT` block of `tokens.css`.
3. Measure, never eyeball: `node scripts/contrast.mjs <your token file>`. It resolves `var()`, `color-mix()`, `oklch()`, and `hsl()` in both themes and prints every pair in the contract. Zero failures is the passing condition at G6, and "it looks fine" is not a measurement.
4. If a pair fails, darken or lighten the **accent**. Never solve a contrast failure by greying out the text.

---

## graphite - neutral, precise, universally safe

Worlds: Swiss Utility, Cinematic Product (dark). Modes: any. Strategy: restrained.

| Token | Light | Dark |
|---|---|---|
| `--canvas` | `#FFFFFF` | `#0B0B0D` |
| `--surface` | `#F6F6F7` | `#16171A` |
| `--surface-2` | `#EDEDF0` | `#1D1E22` |
| `--hairline` | `#E4E4E7` | `#26272B` |
| `--hairline-strong` | `#D2D2D7` | `#33343A` |
| `--ink` | `#16171A` | `#F4F4F5` |
| `--ink-muted` | `#5B5E66` | `#9C9FA6` |
| `--ink-subtle` | `#83868F` | `#71747B` |
| `--accent` | `#1D4ED8` | `#5B7CFA` |
| `--accent-ink` | `#FFFFFF` | `#0B0B0D` |

Body 6.4:1, accent text 6.6:1 light. In dark, `#5B7CFA` takes dark ink on fills.

## nightshift - near-black product surface, software craft

Worlds: Software Craft, Terminal-adjacent app UI. Dark only. Strategy: restrained.

| Token | Value |
|---|---|
| `--canvas` | `#08090A` |
| `--surface` | `#101113` |
| `--surface-2` | `#16181B` |
| `--hairline` | `#22252A` |
| `--hairline-strong` | `#2E3238` |
| `--ink` | `#F7F8F8` |
| `--ink-muted` | `#8A8F98` |
| `--ink-subtle` | `#6B7079` |
| `--accent` | `#6E7BF2` (text and icons, 5.4:1 on canvas) |
| `--accent-fill` | `#4F5BD5` (button backgrounds, takes `#FFFFFF` at 5.5:1) |
| `--accent-ink` | `#FFFFFF` on `--accent-fill` |

Raise surfaces with lightness, never with black shadows. Panels get a `inset 0 1px 0 rgba(255,255,255,0.04)` top light instead of a border on the top edge.

## forest - grown, calm, premium without beige

Worlds: Botanical Calm. Strategy: committed or restrained.

| Token | Light | Dark |
|---|---|---|
| `--canvas` | `#FBFBF9` | `#0C1310` |
| `--surface` | `#F2F3EF` | `#14201A` |
| `--surface-2` | `#E9EBE4` | `#1B2A22` |
| `--hairline` | `#DDE0D8` | `#24312A` |
| `--hairline-strong` | `#C7CBBF` | `#314137` |
| `--ink` | `#14201A` | `#EDF2ED` |
| `--ink-muted` | `#55635A` | `#96A69B` |
| `--ink-subtle` | `#7C8A81` | `#6E7D74` |
| `--accent` | `#1F6F4A` | `#4FBF87` |
| `--accent-ink` | `#FFFFFF` | `#0C1310` |

## clinic - trustworthy, careful, clean

Worlds: Nordic Clinical. Health, fintech, government, `APP`. Strategy: restrained.

| Token | Light | Dark |
|---|---|---|
| `--canvas` | `#FCFDFD` | `#0A1416` |
| `--surface` | `#F1F5F6` | `#122023` |
| `--surface-2` | `#E7EDEF` | `#18292D` |
| `--hairline` | `#DCE5E5` | `#223438` |
| `--hairline-strong` | `#C3D1D2` | `#2E4348` |
| `--ink` | `#10201F` | `#EAF2F2` |
| `--ink-muted` | `#4F6360` | `#93A6A7` |
| `--ink-subtle` | `#7A8D8B` | `#6C7F80` |
| `--accent` | `#0E7C86` | `#3FC0C9` |
| `--accent-ink` | `#FFFFFF` | `#0A1416` |

## oxide - industrial, dark, signal orange

Worlds: Industrial Signal, Cinematic Product. Dark only. Strategy: committed.

| Token | Value |
|---|---|
| `--canvas` | `#0D0D0E` |
| `--surface` | `#17181A` |
| `--surface-2` | `#1F2023` |
| `--hairline` | `#262729` |
| `--hairline-strong` | `#35363A` |
| `--ink` | `#F2F2F0` |
| `--ink-muted` | `#9A9A98` |
| `--ink-subtle` | `#75757A` |
| `--accent` | `#FF5A1F` |
| `--accent-ink` | `#14100E` (dark ink on orange, 6.1:1 - white fails here) |

Orange is a signal, not a background for text. Use it on fills, rules, and small marks, and keep the field under 15% of the page.

## blueprint - engineered, measured, technical

Worlds: Technical Blueprint. Strategy: duo (cool ground plus one warm signal).

| Token | Light | Dark |
|---|---|---|
| `--canvas` | `#F7F9FB` | `#0A0F14` |
| `--surface` | `#EDF1F6` | `#111820` |
| `--surface-2` | `#E2E8F0` | `#17202A` |
| `--hairline` | `#D5DDE7` | `#212C38` |
| `--hairline-strong` | `#B9C6D4` | `#2D3A48` |
| `--ink` | `#0E1620` | `#E9EFF5` |
| `--ink-muted` | `#4C5A6B` | `#93A2B2` |
| `--ink-subtle` | `#75838F` | `#6B7A8A` |
| `--accent` | `#1668B8` | `#4BA3E8` |
| `--accent-2` | `#C2410C` | `#F97316` (signal only, never decorative) |
| `--accent-ink` | `#FFFFFF` | `#0A0F14` |

## terminal - insider, exact, keyboard-first

Worlds: Terminal Modern. Dark only.

| Token | Value |
|---|---|
| `--canvas` | `#0A0B0A` |
| `--surface` | `#121412` |
| `--surface-2` | `#181B18` |
| `--hairline` | `#232823` |
| `--hairline-strong` | `#31382F` |
| `--ink` | `#E8EDE6` |
| `--ink-muted` | `#8B958A` |
| `--ink-subtle` | `#6B746A` |
| `--accent` | `#7DDA6A` |
| `--accent-ink` | `#0A0B0A` |
| `--warning` | `#E3B341` |

One accent used only for state and prompt marks. Green everywhere becomes a costume.

## editorial - authored, literate, printed

Worlds: Editorial Broadsheet, long-form `READ`. Light only. **Gated**: use only when the content is genuinely long-form text, never as a shortcut to "premium".

| Token | Value |
|---|---|
| `--canvas` | `#F4F2ED` |
| `--surface` | `#EAE7E0` |
| `--surface-2` | `#E0DCD3` |
| `--hairline` | `#DAD6CE` |
| `--hairline-strong` | `#BEB8AC` |
| `--ink` | `#141412` |
| `--ink-muted` | `#5A574F` |
| `--ink-subtle` | `#837F74` |
| `--accent` | `#8C2318` |
| `--accent-ink` | `#F4F2ED` |

## bauhaus - primary, structural, loud

Worlds: Bauhaus Poster. Light ground with colour fields. Strategy: drenched.

| Token | Value |
|---|---|
| `--canvas` | `#F5F3EE` |
| `--surface` | `#FFFFFF` |
| `--hairline` | `#1A1A18` (rules are ink here, not grey) |
| `--ink` | `#111110` |
| `--ink-muted` | `#4A4A46` |
| `--accent` | `#D42A20` |
| `--accent-2` | `#1B4FD8` |
| `--accent-3` | `#F2B713` |
| `--accent-ink` | `#F5F3EE` on red and blue, `#111110` on yellow |

Three colours, each owning whole fields. Never all three in one component.

## mono-pop - monochrome plus one bright

Worlds: Kinetic Type, Gallery-adjacent. Strategy: restrained with one loud note.

| Token | Light | Dark |
|---|---|---|
| `--canvas` | `#FFFFFF` | `#0A0A0A` |
| `--surface` | `#F5F5F5` | `#141414` |
| `--surface-2` | `#EBEBEB` | `#1C1C1C` |
| `--hairline` | `#E5E5E5` | `#262626` |
| `--hairline-strong` | `#CFCFCF` | `#363636` |
| `--ink` | `#0A0A0A` | `#F5F5F5` |
| `--ink-muted` | `#575757` | `#A1A1A1` |
| `--ink-subtle` | `#7A7A7A` | `#787878` |
| `--accent` | `#0F9D58` or `#E0245E` | `#3DDC84` or `#FF4D79` |
| `--accent-ink` | `#FFFFFF` on both light options | `#0A0A0A` |

## solar - warm, energetic, friendly

Worlds: Solar Optimist. Consumer, education. Strategy: committed.

| Token | Light | Dark |
|---|---|---|
| `--canvas` | `#FFFDF8` | `#14110B` |
| `--surface` | `#FFF6E6` | `#1E1911` |
| `--surface-2` | `#FBEBD2` | `#282118` |
| `--hairline` | `#F0E3CC` | `#332B20` |
| `--hairline-strong` | `#DCC9A9` | `#453B2C` |
| `--ink` | `#1E1A12` | `#F7F2E8` |
| `--ink-muted` | `#5E5341` | `#A79B87` |
| `--ink-subtle` | `#877A64` | `#7E7461` |
| `--accent` | `#B45309` | `#FFB63D` |
| `--accent-ink` | `#FFFDF8` | `#14110B` |

Amber cannot carry small text on light grounds. `#B45309` is the text-safe version; `#FFB63D` is a fill.

## slate-glass - layered translucency

Worlds: Glass Depth. **Gated**: needs a real background layer to refract, plus fallbacks.

| Token | Value |
|---|---|
| `--canvas` | `#0E1116` |
| `--surface` | `rgba(255,255,255,0.06)` over canvas |
| `--surface-2` | `rgba(255,255,255,0.10)` |
| `--hairline` | `rgba(255,255,255,0.12)` |
| `--glass-border` | `inset 0 1px 0 rgba(255,255,255,0.14)` |
| `--ink` | `#F2F5F9` |
| `--ink-muted` | `#9AA5B4` |
| `--accent` | `#5B9DF9` |
| `--accent-ink` | `#08111C` |

Rules: `backdrop-filter: blur(20px) saturate(140%)`, always with a `@supports not (backdrop-filter: blur(1px))` solid fallback, and a solid fallback under `prefers-reduced-transparency`. Glass over a flat colour is pointless; there must be content or an image behind it.

## gallery - the work leads

Worlds: Gallery White, portfolio `SHOW`. Light only.

| Token | Value |
|---|---|
| `--canvas` | `#FDFDFC` |
| `--surface` | `#F7F7F6` |
| `--hairline` | `#E8E8E6` |
| `--hairline-strong` | `#CFCFCC` |
| `--ink` | `#141414` |
| `--ink-muted` | `#606060` |
| `--ink-subtle` | `#8A8A88` |
| `--accent` | `#141414` (the images are the colour) |
| `--accent-ink` | `#FDFDFC` |

---

## Control borders are not hairlines

Every palette above lists `--hairline` and `--hairline-strong`. Both are structural: they separate regions, and at 1.5:1 that is exactly right. Neither may be the only affordance of an interactive control, because nobody can see it. Inputs, checkboxes, radios, quiet buttons, and segmented controls use `--control-border`, which must clear 3:1 against **both** `--canvas` and `--surface`. Most generated forms fail this and it is invisible until measured.

| Theme | Derivation | Verified example (graphite) |
|---|---|---|
| Light | ink mixed to roughly 45% over canvas | `#8A8C95`, 3.35:1 on canvas, 3.10:1 on surface |
| Dark | ink mixed to roughly 40% over canvas | `#66686F`, 3.54:1 on canvas, 3.23:1 on surface |

`color-mix(in oklab, var(--ink) 45%, var(--canvas))` is the honest way to write it. Then run `contrast.mjs`, because a mix that looks right on canvas routinely fails on the slightly darker surface, which is where fields usually sit.

## Semantic colours

Use across all palettes unless the palette overrides them. Never use these for decoration.

| Role | Light | Dark |
|---|---|---|
| `--success` | `#1A7F4B` | `#4ADE80` |
| `--warning` | `#9A6206` | `#FBBF24` |
| `--danger` | `#C0261F` | `#FF6B6B` |

Status is never colour alone: pair it with an icon, a label, or a shape. Colour-blind users and grayscale printouts both need the second channel.

## Rules that apply to every palette

1. **Never `#000000` text, never a `#000000` surface, and never `#FFFFFF` on saturated colour without measuring it.** Pure black on white vibrates; near-black reads as intentional. The checker reports `pure-black-text` and `pure-black-surface`, and shadows tinted from pure black are the same defect wearing a different hat.
2. **One accent, three chromatic hue families maximum in the whole interface.** A second colour needs a written role (`--accent-2` for signal or data only). `scripts/check.mjs` counts hue families and raises `hue-count` above three; semantic colours are excluded from the count because they are not decoration.
3. **Accent budget.** Restrained: accent under 5% of pixels. Committed: 30-60% as fields. Never 10 accent-coloured sprinkles across a grey page.
4. **Shadows are tinted from the ink hue**, never pure black, never coloured like the accent. A coloured glow with zero offset is decoration; `tokens.css` has the correct four-step scale.
5. **Gradients**: at most one per page, between two adjacent hues, and it must sit on a surface, not on text. `background-clip: text` gradients are banned. Radial mesh blobs behind heroes are banned.
6. **Dark mode is not inverted light mode.** Recheck every contrast pair; hairlines and muted text are where it breaks.
7. **Data visualisation** needs its own ordered scale, distinguishable in grayscale, with a documented order. Do not pick chart colours ad hoc per chart.
8. Test the page in grayscale once: `node scripts/shot.mjs <url> --squint` produces exactly that view, blurred. If the hierarchy survives, colour is doing the right job. If everything flattens, the hierarchy was resting on hue, which is the most common reason a page looks busy and reads as flat.

## Hexes that are already spent

These exact values are what generated "premium" and "artisan" surfaces ship. They are not illegal, they are disqualified as defaults: if the brief did not pin them, they announce a skipped decision.

| Role | Spent values |
|---|---|
| Cream and bone grounds | `#F5F1EA` `#F7F5F1` `#FBF8F1` `#EFEAE0` `#ECE6DB` `#FAF7F1` `#E8DFCB` |
| Terracotta, brass, oxblood accents | `#B08947` `#B6553A` `#9A2436` `#9C6E2A` `#BC7C3A` `#7D5621` |
| Warm near-black text | `#1A1714` `#1A1814` `#1B1814` |

The `editorial` and `solar` palettes above are the sanctioned way to be warm: they were built as complete systems and their pairs are measured. A hand-mixed cream with a terracotta accent is the same idea with none of the work done.

## Output of this gate

One complete palette in `tokens.css`, both themes if the project has both, contrast pairs verified. Continue G4.
