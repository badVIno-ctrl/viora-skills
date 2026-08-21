---
# Machine-readable contract. Keep valid YAML. Keep key names stable.
world: Software Craft
mode: LAND
dials: { expression: 4, density: 4, motion: 2, ornament: 2 }

colors:
  canvas: "#08090a"
  surface: "#101113"
  surface_2: "#16181b"
  hairline: "#22252a"
  hairline_strong: "#2e3238"
  ink: "#f7f8f8"
  ink_muted: "#8a8f98"
  ink_subtle: "#6b7079"
  accent: "#6e7bf2"
  accent_fill: "#4f5bd5"
  accent_ink: "#ffffff"
  success: "#4ade80"
  warning: "#fbbf24"
  danger: "#ff6b6b"

typography:
  display: { family: "Schibsted Grotesk", weight: 700, source: "Google Fonts" }
  text: { family: "Schibsted Grotesk", weight: 400, source: "Google Fonts" }
  mono: { family: "Geist Mono", weight: 400, source: "Google Fonts" }
  display_tracking: "-0.03em"
  body_size: "16px"
  measure: "68ch"

shape:
  radius_family: soft
  radius: { sm: "6px", md: "10px", lg: "14px", xl: "18px" }
  space_base: "4px"

motion:
  ease_out: "cubic-bezier(0.23, 1, 0.32, 1)"
  ease_drawer: "cubic-bezier(0.32, 0.72, 0, 1)"
  durations: { instant: "100ms", fast: "150ms", base: "200ms", slow: "300ms" }
  reduced_motion: true

icons: { set: "Phosphor", weight: "regular", size: "20px" }
theme: dark-only
---

# DESIGN.md

This file is the design contract for this project. It overrides any default in
any skill or tool. Read it before changing visual code. Update it in the same
commit as any decision that changes a value here.

## Direction

**World:** Software Craft.

**Refuses:** the centered hero plus three feature cards plus logo strip that
this category ships. Also refuses the near-black-plus-neon-glow cluster.

**One paragraph, nouns only:** Near-black ground with hairline panels. The
first viewport is a two-column split: the mechanism stated in seven words on
the left, a live product panel bleeding off the right edge. Data is monospaced
because the values are real. One indigo accent, used only on actions and on
the active state. Panels are raised with lightness and a 1px top highlight,
never with a black shadow.

## Palette

See the frontmatter for values. Rules specific to this project:

- Accent appears on interactive elements only. Under 5% of pixels.
- `accent` is for text and icons. `accent_fill` is for button backgrounds, so
  white ink stays above 4.5:1.
- Panels raise with `surface` and `--shadow-inset-top`, never with a shadow.
- Semantic colours never appear decoratively.

## Type

- Two weights only: 400 body, 700 display. No 500, no 600.
- Display tracking `-0.03em` above 2rem. Never zero.
- Mono only for real values: IDs, timestamps, durations, config.
- Body 16px floor, 68ch measure, nothing below 12px anywhere.

## Space and shape

- 4px rhythm. Only the token values.
- Space above a heading always exceeds space below it.
- One radius family: soft. Buttons, inputs, cards and panels all use it.
- Four shadow levels, each with offset and blur. No zero-offset halos.

## Motion

- Two authored moments: the first-viewport entrance and the panel state change.
- Everything else is state feedback at 100-150ms.
- `transform` and `opacity` only. Nothing above 300ms.
- `prefers-reduced-motion` handled globally in `tokens.css`.

## Components

- Button heights 32 / 40 / 48. One primary per view.
- Cards are a last resort. Lists use hairline rows.
- Icon set: Phosphor regular, 20px, never mixed with another set.
- Tables: sticky header, hairline rows, tabular numerals, right-aligned numbers.
- Every async surface has loading, empty, and error states.

## Voice

Direct, specific, technical. Sentence case. No filler adjectives.

- Good: `Deploy in 40 seconds. No config.`
- Bad: `Seamlessly transform your deployment workflow.`
- Button: `Create project`, not `Get started`.
- Error: `Could not reach the build server. Retry` with a working retry.

## Do not

Project-specific bans on top of the standard set:

- No gradient anywhere, including buttons and text.
- No glass or blur surfaces.
- No illustration. Product screenshots or nothing.
- No em-dashes in any copy.
- No stat row of round numbers under the headline.

## Changelog

- `2026-01-01` Created. World: Software Craft, palette nightshift, type Schibsted Grotesk.
