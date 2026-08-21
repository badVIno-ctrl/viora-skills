# 07 - Components

Loaded at G4 or G5. Purpose: the craft floor for the parts every interface is made of. Close when the components are built.

Rule zero: **do not build primitives from scratch.** A hand-rolled dropdown, modal, or combobox will be worse than a library one in keyboard handling, focus trapping, portalling, and screen-reader semantics, every time. Build the surface, borrow the behaviour.

## 0. Library routing

| Need | Use |
|---|---|
| Unstyled accessible primitives (React) | Base UI, Radix UI, or React Aria |
| Styled starting point you will own and edit | shadcn/ui (Radix underneath, code in your repo) |
| Toasts | Sonner |
| Drawers and bottom sheets | Vaul |
| Command palette | cmdk |
| Animation and gestures | Motion |
| Charts | Recharts for standard, visx or D3 when the chart is the product |
| Tables with sorting, grouping, virtualisation | TanStack Table |
| Forms and validation | React Hook Form plus Zod |
| Icons | Phosphor, Radix Icons, Tabler, or Hugeicons. One set, one weight, one size |
| Number that changes | NumberFlow, so digits roll instead of snapping |
| Lists over 200 rows | TanStack Virtual or react-virtuoso |
| Drag and drop | dnd-kit |
| One-time-code input | input-otp |
| Syntax highlighting | Shiki |
| Theme switching in Next.js | next-themes, and set `color-scheme` too |
| Class composition | clsx with tailwind-merge, or cva for variants |
| Client state that is not server state | zustand. Do not reach for Redux by reflex |
| Open Graph images | Satori |
| A globe or 3D flourish | Cobe, once per product, and only if it earns its bytes |
| Brand logos | `https://cdn.simpleicons.org/<slug>/<hex>`, for example `.../stripe/635bff` |
| Placeholder photography | `https://picsum.photos/seed/<seed>/<w>/<h>`, and say in the report that it is a placeholder |

Icon rules: never mix sets, never mix weights, never resize below 16px, never use emoji as an icon, always give an icon-only button an accessible name. Icons align optically with text, which usually means the icon box is 1px higher than the text box.

---

## 1. Button

Anatomy: label, optional leading icon, optional trailing affordance. Never a bare icon without a name.

| Property | Value |
|---|---|
| Heights | `sm` 32px, `md` 40px, `lg` 48px. Touch contexts: 44px minimum |
| Padding | horizontal 1.5x-2x the vertical, so it never looks square |
| Label | sentence case, names the action (`Create project`), 1-3 words |
| Radius | from the chosen family, identical across all buttons |
| Font | 500 or 600 weight, `--text-sm` or `--text-base`, never below 14px |
| Icon gap | `--space-2`, icon optically centered |

Hierarchy: exactly one primary per view or per card. Secondary is a hairline or tinted surface. Tertiary is text-only. If two buttons look equally important, the design failed to decide.

States, all required:

```css
.btn { transition: background-color var(--dur-instant) var(--ease-out), transform var(--dur-instant) var(--ease-out), box-shadow var(--dur-instant) var(--ease-out); }
@media (hover: hover) and (pointer: fine) { .btn:hover { background: var(--accent-hover); } }
.btn:active { transform: scale(0.98); }
.btn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn[data-loading="true"] { pointer-events: none; }
```

Loading: keep the button's width fixed so the layout does not jump; swap the label for a spinner or show the spinner and dim the label. Disable while in flight so double submits are impossible.

Common defects: `cursor: pointer` on a `<div>` instead of a real `<button>`; a destructive action with the same weight as the safe one; two primary buttons side by side; a hover state that only changes the cursor.

## 2. Input and form field

| Property | Value |
|---|---|
| Height | 40px default, 44px on touch |
| Label | **always visible**, above the field. Placeholders are not labels |
| Placeholder | an example of the format, or nothing |
| Border | `--control-border`, 1px. On a field this line is the only affordance, so it must clear 3:1. `--hairline` is for structure, not for controls |
| Focus | 2px `--focus` ring at `outline-offset: 2px`, or an inset ring. Never `outline: none` alone |
| Help text | below the field, `--text-sm`, `--ink-muted`, present before the user errs |
| Error | below the field, `--danger`, with an icon, tied by `aria-describedby`, and `aria-invalid` on the input |
| Required | mark the required ones, or mark the optional ones. Do not mark both |

Rules:

- 16px minimum font size on mobile inputs, otherwise iOS zooms the page on focus.
- Correct `type`, `inputmode`, `autocomplete`, and `enterkeyhint` on every field. `autocomplete="one-time-code"` for OTP, `inputmode="decimal"` for amounts. This is felt immediately on a phone.
- Validate on blur, not on every keystroke. Clear the error the moment the user starts fixing it.
- Never disable paste. Never block a password manager.
- `field-sizing: content` on textareas that should grow with typing.
- One column of fields. Side-by-side fields only for genuinely paired data (city and postcode, expiry and CVC).
- Errors summarised at the top for long forms, each item linking to its field, focus moved to the first error on submit.

## 3. Card

A card is a container of last resort. Before using one, ask whether a hairline row or plain spacing would do the job better. Usually it would.

If you use cards: one padding value on all sides, one surface level, hairline border **or** a shadow but not both stacked into mush, and the same internal grid in every card in the group. Never nest a card inside a card. Never wrap every item in a list in its own card.

Interactive cards: the whole card is one link or button, the hover state is a subtle surface or hairline change plus at most a 2px lift, and there is exactly one focusable element so keyboard users do not tab through five stops per card.

## 4. Navigation

Covered structurally in `03-layout.md`. Component floor:

- Real `<a>` for navigation and real `<button>` for actions.
- `aria-current="page"` on the active item, plus a visible mark that is not colour alone.
- Sticky nav: `backdrop-filter` plus a translucent background, and it must gain a hairline once scrolled.
- Mobile menu: focus trap, `Escape` closes, focus returns to the trigger, body scroll locked, `aria-expanded` on the trigger.
- Skip link as the first focusable element on the page.

## 5. Modal and dialog

Use the native `<dialog>` element or a library primitive.

- Focus moves into the dialog on open, is trapped while open, and returns to the trigger on close.
- `Escape` closes. Backdrop click closes, unless there is unsaved data, in which case confirm.
- Backdrop: `var(--scrim)` from `tokens.css`, never a raw `rgb(0 0 0 / 0.4)`. Add 2px to 4px of blur only if the direction uses depth.
- Width: 400-560px for confirmations, up to 720px for forms. Never full-width on desktop, always near-full on mobile.
- Body scroll locked, and the lock must not shift the layout when the scrollbar disappears (`scrollbar-gutter: stable`).
- Actions bottom right on desktop, primary last in reading order; stacked full-width on mobile with primary on top.
- Never nest modals. If a modal needs a modal, the flow is wrong.
- Destructive confirmations name the object: `Delete 3 invoices?` and label the button `Delete invoices`, not `Yes` / `OK`.

## 6. Dropdown, select, menu

- Library primitive, always. Keyboard support required: arrows, `Home`, `End`, type-ahead, `Escape`, `Enter`.
- `transform-origin` set from the trigger position so it grows out of what opened it.
- Max height with internal scroll, and a visible top or bottom fade when there is more content.
- Checkmark for the selected item, not colour alone.
- Over 10 options: add a filter input. Over 25: use a combobox.
- Never a custom select that loses native mobile behaviour without replacing it properly.

## 7. Table and data grid

- Header row sticky, `--surface`, `--text-xs` or `--text-sm`, weight 500-600, `--ink-muted`.
- Rows separated by `--hairline` only. No per-row card, no zebra striping unless the table is genuinely wide.
- Row height 40-48px comfortable, 32-36px compact. Give the user the choice on dense tools.
- Numbers right-aligned with `tabular-nums`. Text left. Dates in one format, never mixed.
- Sortable headers show current direction and are keyboard operable.
- Actions in a right-aligned column, revealed on row hover **and** always visible on touch.
- Truncate with a real ellipsis and a tooltip or expansion; never let text overflow silently.
- Selection: checkbox column, a persistent bar showing `n selected` with the bulk actions.
- Empty, loading, error, and filtered-to-nothing are four different states with four different messages.
- Mobile: labelled stacked rows, or a horizontal scroll with a sticky first column. Never an unusable 8-column squeeze.

## 8. Toast and notification

- Bottom right on desktop, top on mobile away from the notch.
- Maximum 3 stacked, older ones collapse.
- 4-6 seconds for information, persistent for errors and anything with an action.
- Slide in 200ms `--ease-out`, out 150ms, along one axis.
- Includes an undo when the action is reversible. Undo is worth more than a confirmation dialog.
- Never for validation errors: those belong next to the field.

## 9. Tooltip

- 125-200ms delay in, near-instant out, so a moving cursor does not trail popups.
- Explains, never contains essential information or actions.
- Never on touch as the only affordance.
- Icon-only buttons need a real accessible name in addition to the tooltip.

## 10. Tabs, accordion, disclosure

- Tabs: roving tabindex, arrow keys move, active tab marked by more than colour, panel associated by `aria-controls`. Never more than 6 top-level tabs.
- Accordion: real `<details>`/`<summary>` when possible. Chevron rotates 180deg in 200ms. Height animated per the recipe in `06-motion.md`.
- Never hide critical information behind a disclosure the user has no reason to open.

## 11. Avatar, badge, chip

- Avatar: initials fallback with a deterministic colour from the name hash, never a broken image icon. `border-radius: 50%` and `object-fit: cover`.
- Badge: `--text-xs`, tight padding, semantic colour with a label, never colour alone. Status dots need a text label next to them.
- Chip and filter pill: removable ones show the affordance permanently on touch, and the remove target is at least 24px.

## 12. Skeleton, spinner, progress

- Skeleton geometry must match the real content exactly, so nothing jumps on load.
- Spinner only for 300ms-2s waits and only when nothing more specific is available.
- Over 2 seconds: show real progress or a step description (`Processing 3 of 12`).
- Progress bars: never a filled-but-static track, never a track that resets backwards.

## 13. Search, filter, pagination

- Search: debounce 200-300ms, show what is being searched, allow clearing in one click, keep the query in the URL.
- Filters: show the active ones as removable chips with a `Clear all`, keep them in the URL, show the result count.
- Pagination: current page, total, and a jump. Or infinite scroll with a real end state and a working back button. Not both.

## 14. Empty state

The most-skipped and highest-value screen in any product.

Required: a short line saying what lives here, one line on why it matters or how it works, and the primary action that fills it. Optional: a small illustration or a sample row. Never a shrug emoji, never `No data`, never a giant grey box with a magnifying glass.

Four distinct empties, four distinct messages: first run, user cleared everything, search found nothing, and an error occurred.

## 15. Command palette

Worth building for any tool a person uses daily. `cmd/ctrl + K`, fuzzy search over navigation and actions, recent items first, keyboard hints displayed, `Escape` closes, and every action reachable another way too.

---

## Per-component defect sweep

Run this over what you built:

1. Every interactive element: hover, focus-visible, active, disabled present.
2. Every async surface: loading, empty, error present.
3. Nothing uses `div` where `button` or `a` belongs.
4. No focus outline removed without a visible replacement.
5. One icon set, one weight, one size scale.
6. No nested cards, no card-per-list-item.
7. Every icon-only control has an accessible name.
8. Every image has meaningful `alt`, or `alt=""` if genuinely decorative.
9. All text at least 14px, body at least 16px.
10. Every hover effect gated by `@media (hover: hover)`.
11. Contrast measured with `scripts/contrast.mjs`, not judged by eye.
12. One radius family, one shadow scale, no raw hex, no magic px.
13. Every string in the interface is in the product language, including errors and empty states.

## Output of this gate

Components built on real primitives, states complete, no defect from the sweep remaining. Continue to `08-states-a11y.md`.
