# 02 - Tokens

Loaded at G3. Purpose: install one token contract so every later decision is a lookup instead of a guess. Close when the token file exists and the palette and type pair are filled in.

This is the highest-leverage file in the skill. Most "AI-looking" UI is not badly designed, it is **inconsistently** designed: three greys that should be one, four radii, six shadows, durations from 120ms to 900ms with no logic. Tokens remove that class of defect entirely.

## 1. Install

1. Copy `assets/tokens.css` into the project (`styles/tokens.css`, `app/tokens.css`, or next to the global stylesheet).
2. Import it **first**, before any framework or component CSS.
3. Fill in only the marked `EDIT` block: the palette from `05-color.md` and the type pair from `04-typography.md`.
4. Leave everything below the `EDIT` block alone. That part is the craft floor: focus rings, selection, scrollbars, caret, numerals, reduced motion. It is what makes a page feel built rather than assembled.

If the project already has tokens, **extend them**. Read the existing names, adopt them, add only what is missing. A second parallel token system is a defect, not a contribution.

## 2. The naming contract

Names describe **role**, never appearance. `--ink-muted`, not `--gray-500`. Role names survive a theme change; appearance names lie the moment you add dark mode.

### Color roles

| Token | Role | Rule |
|---|---|---|
| `--canvas` | page ground | one per theme |
| `--surface` | raised or inset area | 3-6% lighter or darker than canvas |
| `--surface-2` | second level only if truly needed | never nest a third |
| `--hairline` | 1px separators | must be visible but not read as a line of ink |
| `--hairline-strong` | emphasis borders, inputs | |
| `--ink` | primary text | >= 15:1 on canvas where possible, never `#000` |
| `--ink-muted` | secondary text | >= 4.5:1 on canvas, this is a hard floor |
| `--ink-subtle` | non-text only: icons, decorative labels | >= 3:1 |
| `--accent` | one action colour | see budget below |
| `--accent-hover`, `--accent-ink`, `--accent-soft` | derived | `--accent-ink` must pass 4.5:1 on `--accent` |
| `--focus` | focus ring | must be visible on canvas **and** on accent |
| `--success` `--warning` `--danger` | semantic only | never used decoratively |

**Accent budget.** Pick one strategy and hold it:

- `restrained` - neutrals plus accent on interactive elements only. Default for `APP` and `READ`.
- `committed` - one saturated colour owns 30-60% of the surface as fields, not sprinkles. Strong for `LAND`.
- `duo` - accent plus one supporting hue with defined roles.
- `drenched` - the surface is the colour. `SHOW` and bold `LAND` only.

The common failure is "restrained" applied timidly: a grey page with a single blue button, which reads as unfinished rather than restrained. If you choose restrained, the confidence has to come from type and space instead.

### Scale tokens

| Family | Tokens | Rule |
|---|---|---|
| Space | `--space-1` .. `--space-16` on a 4px base | Only these values. No `13px`, no `gap: 7px`. |
| Radius | `--r-sm` `--r-md` `--r-lg` `--r-xl` `--r-full` | Pick one family in `tokens.css` and never mix families |
| Shadow | `--shadow-1` .. `--shadow-4` | Every shadow has offset **and** blur. A zero-offset coloured halo is decoration, not depth |
| Type | `--text-xs` .. `--text-display-1` | With matched line-height and tracking, see `04-typography.md` |
| Motion | `--dur-*`, `--ease-*` | From `06-motion.md`. Never invent a cubic-bezier |
| Layout | `--measure`, `--gutter`, `--container` | `--measure: 68ch` is the reading floor |

### Radius families

Choose one at G3 and write it into `DESIGN.md`:

| Family | Values | Reads as |
|---|---|---|
| sharp | 0 / 2 / 4 | precise, technical, editorial |
| soft | 6 / 10 / 14 | modern product default |
| round | 12 / 18 / 24 | friendly, consumer, mobile |
| pill | full on interactive, 16 on containers | playful, marketing |

Mixed radii are allowed **only** with a written rule such as "buttons pill, cards 16, inputs 10", applied everywhere. Round buttons in a sharp layout is a visible mistake.

## 3. Component rule

Inside a component: token references only.

```css
/* wrong */
.card { background: #16181b; border: 1px solid #26282d; border-radius: 12px; padding: 18px; }

/* right */
.card {
  background: var(--surface);
  border: 1px solid var(--hairline);
  border-radius: var(--r-md);
  padding: var(--space-5);
}
```

Tailwind projects: map tokens once, then use the mapped names. Do not write `bg-[#16181b]` in markup.

**Tailwind v4** - put this in the same file as the tokens:

```css
@import "tailwindcss";

@theme inline {
  --color-canvas: var(--canvas);
  --color-surface: var(--surface);
  --color-hairline: var(--hairline);
  --color-ink: var(--ink);
  --color-ink-muted: var(--ink-muted);
  --color-accent: var(--accent);
  --color-accent-ink: var(--accent-ink);
  --radius-md: var(--r-md);
  --ease-out: var(--ease-out);
}
```

Then `bg-canvas text-ink border-hairline rounded-md`.

**Tailwind v3** - extend `theme.colors` with the same names in `tailwind.config`, using `var(--canvas)` values so themes still switch at runtime.

**CSS-in-JS / RN / Compose / SwiftUI** - mirror the same names in a single constants module. One source, one vocabulary.

## 4. Theming

`tokens.css` ships light and dark. Rules:

- The whole page is one theme. Sections never invert. A light section in the middle of a dark page reads as a bug, not a device. Exception: one deliberate full-width theme change, used once, with a real transition.
- Set the theme once at the root. Never let a component override it.
- Support both `prefers-color-scheme` and an explicit `[data-theme]` override, and set `color-scheme` so form controls and scrollbars follow.
- In dark mode: raise surfaces with lightness, not with black shadows; desaturate accents slightly; never reuse light-mode shadow alphas, they disappear.
- Test both. Most dark-mode defects are contrast failures on `--ink-muted` and invisible hairlines.

## 5. Deriving a palette when the menu does not fit

Six steps, in order. Work in OKLCH if the tool allows.

1. **Canvas.** Pick lightness first: light `96-99%`, dark `6-11%`. Give it 1-4% chroma so it is not sterile grey.
2. **Surface.** Same hue, lightness offset 3-6%.
3. **Hairline.** Same hue, offset 8-12% from canvas. Check it is visible at 1px on a real screen.
4. **Ink.** Same hue family, chroma slightly higher, lightness such that contrast on canvas is 15:1 or more. Never `#000000` or `#FFFFFF`.
5. **Muted.** Same hue, land it exactly at 4.5-6:1 on canvas. Measure, do not eyeball.
6. **Accent.** One hue, 40-90 degrees away from the neutral hue. Then verify `--accent-ink` on `--accent` passes 4.5:1. If it does not, darken the accent rather than switching the ink to grey.

Saturation ceiling for large fields is roughly 80% of the gamut maximum; above that, text on top gets hard and the page looks synthetic.

## 6. Anti-patterns

| Never | Instead |
|---|---|
| Raw hex in a component | token reference |
| `--gray-500` style names | role names |
| Three greys that differ by 2% | one `--ink-muted` |
| A radius per component | one family |
| `box-shadow: 0 0 24px <accent>` | offset plus blur, tinted from the ink hue |
| Same shadow alphas in dark mode | separate dark values, usually stronger and larger |
| `!important` to win a cascade fight | fix the specificity |
| `z-index: 9999` | a documented 5-step scale, `--z-1` .. `--z-5` |
| A theme toggle that only swaps `background` | full token set per theme |

## Output of this gate

`tokens.css` present, imported first, palette and type filled, radius family chosen and recorded. Then load `03-layout.md` and finish G3.
