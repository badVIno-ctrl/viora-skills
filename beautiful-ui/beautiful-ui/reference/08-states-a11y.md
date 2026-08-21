# 08 - States and accessibility

Loaded at G5. Purpose: make the interface complete, not just pretty in its happy path. Close when the sweep is clean.

An interface is judged on its worst state, not its best one. The screenshot-perfect empty dashboard with a broken error message is a bad interface.

## 1. The state matrix

For every component you shipped, confirm each applicable row exists. This is a mechanical pass, not a judgement call.

| State | Applies to | Requirement |
|---|---|---|
| Default | everything | the resting look |
| Hover | pointer-capable devices | visible change, gated by `@media (hover: hover) and (pointer: fine)`, 100-150ms |
| Focus-visible | everything focusable | 2px ring, `--focus`, `outline-offset: 2px`, visible on every background it can sit on |
| Active / pressed | buttons, links, rows | immediate feedback, usually `scale(0.98)` or a surface shift |
| Selected | list items, tabs, options, rows | not colour alone: add a check, a bar, a weight change |
| Disabled | controls | `opacity: 0.5`, `cursor: not-allowed`, and a reason available. Never disable without explanation |
| Loading | anything async | inline, scoped to the thing loading, layout reserved |
| Empty | any collection | what goes here, why, and the action that fills it |
| Error | anything that can fail | what happened, what to do, and a retry |
| Success | anything that completes | confirmation plus what changed, and undo where reversible |
| Partial | lists, uploads, syncs | show what succeeded and what did not, separately |
| Offline | anything network-bound | state it, queue or block clearly, do not fail silently |
| Read-only | permission-gated views | visually distinct from disabled, and explained |
| Overflow | any text container | truncation with a way to see the whole value |
| Zero-to-one | new accounts | the first-run experience is a designed screen, not an empty template |

## 2. Loading, empty, error copy

| Do not write | Write |
|---|---|
| `Loading...` | `Loading invoices` or nothing plus a skeleton |
| `No data` | `No invoices yet. Create your first one to start tracking payments.` |
| `Error` / `Something went wrong` | `Could not load invoices. Check your connection and try again.` plus a `Retry` button |
| `Success!` | `Invoice sent to acme-billing@example.com` |
| `Are you sure?` | `Delete 3 invoices? This cannot be undone.` |
| `Submit` | `Send invoice` |

Every error names the object, the cause if known, and the next action. Every error that could be retried has a retry control. Never blame the user, never show a stack trace, never show a raw error code without a human sentence next to it.

## 3. Accessibility floor

Not optional, and not a separate pass at the end. Mechanical checks first:

### Contrast

| Content | Minimum |
|---|---|
| Body text, placeholders, labels | 4.5:1 |
| Text 18.66px bold or 24px regular and above | 3:1 |
| Icons and UI boundaries that convey meaning | 3:1 |
| Focus indicator against its background | 3:1 |
| Disabled text | exempt, but keep it legible enough to read |

Placeholder text is real text. `--ink-subtle` is for non-text only. Text over an image needs a scrim, not hope.

### Keyboard

- Everything operable by mouse is operable by keyboard.
- Tab order follows visual order. No positive `tabindex`.
- Focus is always visible, never removed. `outline: none` is only acceptable when a visible replacement exists in the same rule set.
- `Escape` closes any overlay. `Enter` and `Space` activate buttons. Arrows navigate within composite widgets.
- Focus is trapped inside modals and returned to the trigger on close.
- A skip-to-content link is the first focusable element.
- Nothing traps focus permanently.

### Semantics

- One `<h1>` per page, headings in order, no level skipped, never chosen for size.
- Landmarks: `header`, `nav`, `main`, `footer`, `aside`. One `main`.
- Lists are `<ul>` / `<ol>`. Tables are `<table>` with `<th scope>`. Buttons are `<button>`. Links are `<a href>`.
- Every form control has a programmatically associated `<label>`.
- Icon-only controls have `aria-label`. Decorative icons have `aria-hidden="true"`.
- Live regions for async updates: `aria-live="polite"` for status, `role="alert"` for errors.
- `aria-expanded`, `aria-controls`, `aria-current`, `aria-invalid`, `aria-describedby` where they apply.
- No ARIA is better than wrong ARIA. Prefer native elements.

### Motion and sensory

- `prefers-reduced-motion` honoured everywhere.
- No autoplay with sound. No content flashing more than 3 times per second.
- Never colour alone to convey status, validity, or selection.
- Anything conveyed by hover is also available on focus and on touch.

### Touch and mobile

- Hit targets >= 44x44px, spacing >= 8px between adjacent targets.
- `user-scalable=no` and `maximum-scale=1` are banned. Users must be able to zoom.
- Text scales when the OS font size increases; nothing clips at 200% zoom.
- Safe area insets respected on fixed elements.
- No hover-only affordance on touch.

### Zoom and reflow

At 200% zoom and at 320px wide: no horizontal scrolling, no clipped content, no overlapping text. This single test finds more real defects than any audit tool.

## 4. Forms, in depth

1. Labels above fields, always visible.
2. One column. Group related fields with a heading and space, not with boxes.
3. Required vs optional marked one way, consistently.
4. Correct `type`, `inputmode`, `autocomplete`, `enterkeyhint`.
5. Format hints before the error, not after: `MM / YY`, `+7 900 000 00 00`.
6. Inline validation on blur. Clear the error on input.
7. Submit disabled only while in flight, never as a substitute for validation messages.
8. Errors: summary at the top for long forms, focus to the first invalid field, each error next to its field.
9. Success is unmistakable and says what happened next.
10. Never lose typed data on error. Never clear a form because one field failed.
11. Multi-step: show progress, allow going back, preserve entered values.
12. Destructive confirmations require the object name, not just `Yes`.

## 5. Content and internationalisation

- Set `lang` correctly. It drives hyphenation, quote marks, and screen-reader pronunciation.
- Design for text 30-40% longer than English. German, Russian, and Finnish will break tight buttons and nav items.
- Never build a layout that depends on a label being short.
- Numbers, dates, and currency formatted for the locale. Use `Intl`, never string concatenation.
- If content is Russian, the whole interface is Russian: labels, empty states, errors, button text. Mixed-language UI reads as unfinished.
- Check the chosen typeface actually contains the required script before shipping.

## 6. The browser surfaces nobody draws

These are already handled in `assets/tokens.css`. Confirm they survived:

| Surface | Why it matters |
|---|---|
| `::selection` | default blue selection breaks any palette instantly |
| `caret-color` | a blue caret in a warm dark theme is jarring |
| Scrollbar | a default light scrollbar on a dark page is the loudest tell there is |
| `:focus-visible` ring | the difference between accessible and merely compliant |
| Link underline offset and thickness | default underlines cut descenders |
| `text-wrap: balance` / `pretty` | removes orphans and ragged edges for free |
| `tabular-nums` on numeric columns | stops numbers dancing on update |
| `color-scheme` | makes native controls, scrollbars, and autofill match the theme |
| Autofill background | Chrome paints yellow unless overridden |
| `scrollbar-gutter: stable` | prevents layout shift when a scrollbar appears |
| Print styles | one `@media print` rule is often all it takes to stop a page printing as a black rectangle |

## Output of this gate

The state matrix has no missing row, the accessibility checks pass, the browser surfaces are themed. Print `G5 detail: done` and move to G6.
