# 14 - Interface rules

Loaded at G5 for building and at G6 for review. This is the code-level contract: the rules a
reviewer can point at with a file and a line number. `01` to `08` decide what the surface
should be. This file decides whether the implementation is actually correct.

Origin: the rule set is the Vercel Web Interface Guidelines
(`github.com/vercel-labs/web-interface-guidelines`), reorganised, extended with the WCAG 2.2
additions and the app-side rules this skill needs, and reconciled with the ten laws in
`SKILL.md`. `scripts/wig.mjs` enforces the mechanical part of it.

## How to use

- **Building:** read the areas the work touches. A form screen needs Forms, Focus and
  Accessibility. A table needs Content handling and Performance.
- **Reviewing:** run `node scripts/wig.mjs <paths>`, then read the areas the script cannot
  see (copy, state, navigation) with your own eyes.
- **Reporting:** one finding per line, `file:line - problem`. No paragraphs, no praise.

Severity has two levels only. `error` is a defect: it breaks a user, a keyboard, a screen
reader, or the layout. `warn` is a craft miss: fix it or justify it in one clause.

## A. Accessibility

- Icon-only buttons need an accessible name: `aria-label`, or visually hidden text. `error`
- Every form control needs a real `<label>` (`htmlFor`) or `aria-label`. A placeholder is
  not a label. `error`
- Use `<button>` for actions and `<a href>` for navigation. A `div` with a click handler is
  unreachable by keyboard. `error`
- Images need `alt`, or `alt=""` when genuinely decorative. `error`
- Decorative icons need `aria-hidden="true"`. Meaningful icons need a text alternative.
  Icon controls need a name and, when stateful, `aria-pressed` or `aria-expanded`. `warn`
- Async updates (toasts, inline validation, live counts) need `aria-live="polite"` or a
  `role="status"` region that already exists in the DOM. `error`
- Semantic HTML before ARIA: `main`, `nav`, `header`, `footer`, `section`, `dialog`. `warn`
- Headings are hierarchical `h1` to `h6`, one `h1` per document, no level skipped. `warn`
- Provide a skip link to main content. `warn`
- `scroll-margin-top` on anchor targets so a sticky header does not cover them. `warn`
- Keyboard reachability is not optional: every action reachable, tab order matching visual
  order, `Escape` closing every overlay, focus returned to the trigger on close. `error`
- WCAG 2.2, the four that generated code misses most:
  - focus is never obscured by sticky headers, footers, banners or toasts, `error`
  - every drag action has a single-pointer and keyboard alternative, `error`
  - pointer targets are at least 24x24 CSS px on the web, 44x44 for anything primary, `warn`
  - information already entered in a flow is not asked for twice. `warn`
- Authentication allows paste and password managers. Blocking paste is a defect. `error`

## B. Focus states

- Visible focus on every interactive element. `error`
- Never `outline: none` or `outline-none` without a `:focus-visible` replacement in the same
  file. `error`
- Prefer `:focus-visible` over `:focus` so a mouse click does not leave a ring. `warn`
- Compound controls take group focus with `:focus-within`. `warn`
- The focus ring needs its own contrast: at least 3:1 against both the control and the
  ground behind it. Measure it, do not eyeball it. `warn`

## C. Forms

- Inputs carry a meaningful `name` and the right `autocomplete`. `warn`
- Correct `type` and `inputmode`: `email`, `tel`, `url`, `numeric`, `decimal`. `warn`
- Never block paste. `error`
- Labels are clickable, and a checkbox or radio shares one hit target with its label:
  no dead zone between the box and the text. `warn`
- `spellcheck="false"` on emails, codes, usernames, tokens. `warn`
- The submit button stays enabled until the request starts, then shows a spinner and keeps
  its width. A disabled button that never explains itself is a dead end. `warn`
- Errors appear inline next to the field, in the interface voice, naming the recovery.
  On submit, focus moves to the first error. `error`
- Validate on blur or on submit, never on the first keystroke of an empty field. `warn`
- Warn before navigation with unsaved changes. `warn`
- A placeholder shows an example pattern and ends with an ellipsis character. It never
  replaces the label. `warn`

## D. Animation

- `prefers-reduced-motion` ships in the same commit as the animation. `error`
- Animate `transform` and `opacity` only. `error`
- Never `transition: all`. Name each property. `error`
- Set `transform-origin` deliberately. For SVG use `transform-box: fill-box`. `warn`
- Animations are interruptible: a second user input takes over mid-flight, from the current
  position, not from the start. `warn`
- Autoplaying motion longer than five seconds needs pause, stop or hide. `error`
- Decorative loops stop under reduced motion. `warn`
- Entrances use `ease-out`, exits use `ease-in`, and exits are faster than entrances. `warn`

## E. Typography and copy

- Use the ellipsis character, not three periods. Use curly quotes, and the correct quotes
  for the copy's language: `"..."` in English, `«...»` in Russian. `warn`
- Non-breaking space inside units and shortcuts: `10 MB`, `Cmd K`, brand names. `warn`
- Loading and progress labels end with an ellipsis: `Saving...` becomes `Saving` plus the
  ellipsis character. `warn`
- `font-variant-numeric: tabular-nums` on any column or comparison of numbers. `warn`
- `text-wrap: balance` on headings, `text-wrap: pretty` on paragraphs. `warn`
- Sentence case for headings and buttons. This overrides the Title Case convention in the
  upstream Vercel rules: Title Case reads as a marketing deck, and the linter flags it.
  Keep Title Case only when the user pinned a brand voice that requires it. `warn`
- Active voice, second person, specific labels. `Save API key`, not `Continue`. An action
  keeps its name through the whole flow: `Publish` produces `Published`. `warn`
- Numerals for counts: `8 deployments`, not `eight deployments`. `warn`
- Error messages carry the fix, not just the problem. Errors do not apologise. `warn`

## F. Content handling

- Text containers survive long content: `truncate`, `line-clamp`, or `break-words`. `warn`
- A flex child that must truncate needs `min-w-0`. Without it the layout blows out. `warn`
- Empty strings and empty arrays render an empty state, never broken UI. `error`
- User-generated content is tested at three lengths: one word, average, and absurdly long.
  Names, prices and counts all get their turn. `warn`

## G. Images and media

- Explicit `width` and `height`, or `aspect-ratio`. This is the cheapest CLS fix. `error`
- Below the fold: `loading="lazy"`. Above the fold: `fetchpriority="high"` or the
  framework's `priority`, and never `lazy`. `warn`
- Modern formats with a fallback, `srcset` and `sizes` for anything full width. `warn`
- Prefer a compressed video over an animated GIF, muted, `playsinline`, with a still
  fallback and a reduced-motion condition. `warn`
- Meaningful media needs captions or a transcript. Media controls are keyboard operable. `warn`

## H. Performance in code

The budget and the measurement workflow live in `15-perf-craft.md`. The code-level rules:

- Lists over roughly 50 rows are virtualised, or use `content-visibility: auto`. `warn`
- No layout reads in render: `getBoundingClientRect`, `offsetHeight`, `scrollTop` belong in
  an effect or a handler, batched, never interleaved with writes. `warn`
- Prefer uncontrolled inputs. A controlled input must be cheap per keystroke. `warn`
- `preconnect` for font and asset origins. Critical fonts get `preload` plus
  `font-display: swap`, and only the weights actually used above the fold. `warn`
- Layout comes from flex and grid, not from JavaScript measurement. `warn`

## I. Navigation and state

- The URL reflects state: filters, tabs, pagination, expanded panels, dialogs worth
  linking to. If it lives in `useState` and a user might share it, it belongs in the URL. `warn`
- Links are real links so Cmd-click and middle-click work. `error`
- Back does what the user expects, including after a modal. `warn`
- Destructive actions need a confirmation or an undo window. Never immediate, never silent. `error`
- Preserve scroll position on back. Restore focus where the user left it. `warn`

## J. Touch and pointer

- `touch-action: manipulation` on interactive elements to kill the double-tap delay. `warn`
- `-webkit-tap-highlight-color` set on purpose, not left to the browser. `warn`
- `overscroll-behavior: contain` in modals, drawers and sheets. `warn`
- During a drag: disable text selection, mark the dragged element `inert`. `warn`
- Every gesture has a tap and keyboard alternative. `error`
- `autoFocus` only on desktop, only for a single primary input, never on mobile. `warn`
- Hover effects are gated behind `@media (hover: hover)` so they do not stick on touch. `warn`

## K. Layout, safe areas, dark mode

- Full-bleed layouts respect `env(safe-area-inset-*)`. Fixed bars, sheets and CTA bars
  clear the notch and the home indicator. `warn`
- No unwanted scrollbars. Find the element that overflows at 320px and fix it, do not hide
  the overflow. `error`
- `color-scheme` declared for dark themes so scrollbars, form controls and the caret follow. `warn`
- `theme-color` matches the page ground. `warn`
- Native `select`, `option` and date inputs get explicit `background-color` and `color`, or
  they turn unreadable on Windows dark mode. `warn`
- Interaction states increase contrast: hover, active and focus are more prominent than
  rest, in both themes. `warn`
- Borders, dividers and disabled states are visible in both themes, not just light. `warn`

## L. Locale and i18n

- Dates, times and numbers go through `Intl.DateTimeFormat` and `Intl.NumberFormat`. Never
  hand-formatted, never a hardcoded `MM/DD/YYYY`. `error`
- Language comes from `Accept-Language` or `navigator.languages`, never from IP. `warn`
- Brand names, code tokens and identifiers carry `translate="no"`. `warn`
- The document `lang` matches the copy. Cyrillic copy in a document claiming English is a
  defect, and the type stack must ship the script the copy is written in. `error`
- Layout survives a 30% longer string. German, Russian and Finnish all pay that tax. `warn`

## M. Hydration and framework safety

- An input with `value` needs `onChange`, or use `defaultValue`. `error`
- Anything time-dependent is guarded against a server and client mismatch. `warn`
- `suppressHydrationWarning` only where the mismatch is genuinely expected. `warn`
- CSS selector specificity is planned: a type selector like `.section` and an element
  selector like `.cta` that fight over padding produce the invisible bug that eats an hour. `warn`

## N. Anti-patterns, flag on sight

`user-scalable=no` or `maximum-scale=1`. `onPaste` with `preventDefault`. `transition: all`.
`outline: none` with no replacement. `div` or `span` with a click handler. An `<a>` with an
`onClick` and no `href`. Images without dimensions. A 500-row `.map()` with no virtualisation.
Inputs without labels. Icon buttons without names. Hand-rolled date and number formatting.
`autoFocus` on mobile. An animated GIF where a video belongs. A gesture with no keyboard
path. Positive `tabindex`. `100vh` on a mobile layout. Two competing scroll containers.

## Output format for a review

Group by file. One finding per line. `file:line`, then the problem in a few words. Clickable
in every editor. No preamble, no summary paragraph, no restating the rule.

```text
## src/components/Button.tsx

src/components/Button.tsx:42 - icon button missing aria-label
src/components/Button.tsx:55 - animation has no prefers-reduced-motion path
src/components/Button.tsx:67 - transition: all, name the properties

## src/components/Modal.tsx

src/components/Modal.tsx:12 - missing overscroll-behavior: contain
src/components/Modal.tsx:31 - focus not returned to trigger on close
src/components/Modal.tsx:44 - three periods, use the ellipsis character

## src/components/Card.tsx

pass
```

End a review with two lines: the count by severity, and the single most expensive fix.
Nothing else.

## What the script sees and what it does not

`node scripts/wig.mjs <paths>` covers the mechanical half: blocked paste, missing
`autocomplete`, missing labels, `value` without `onChange`, three periods, straight quotes
in copy, missing `min-w-0`, missing `overscroll-behavior`, missing `color-scheme`,
hand-formatted dates and numbers, layout reads in render, animated GIFs, `autoFocus`,
missing `preconnect`, `@font-face` without `font-display`, missing safe-area handling,
missing tabular numerals in tables.

It cannot see: whether the copy is honest, whether the state belongs in the URL, whether
back works, whether the empty state is useful, whether the focus order matches the visual
order, whether the confirmation is worth the friction. Those need the walkthroughs in
`10-review.md`.

Run both linters. `check.mjs` grades the design, `wig.mjs` grades the implementation.

## Output of this gate

Zero `error` findings, every `warn` either fixed or justified in one clause, and the review
printed in `file:line` form. Then close this file.
