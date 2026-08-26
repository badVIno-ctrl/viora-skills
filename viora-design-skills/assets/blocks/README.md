# Blocks

Finished pieces you can paste. Every block passes `check.mjs` and `wig.mjs`,
uses only tokens from `../tokens.css`, and contains no colour of its own. Change
the palette in `EDIT 1` and every block follows.

This folder exists because the two worst failure modes are the same failure:
invention. A weak model invents a colour, a strong model invents a pattern that
already has a correct form. Start from the block, then push the direction.

## What is here

| File | Contains |
| --- | --- |
| `html/shell.html` | Skip link, sticky header, primary nav, mobile drawer with Escape and focus return, four-column footer |
| `html/marketing.html` | Hero with a real image slot, trust row, feature grid with one lead card, attributed numbers, three-tier pricing, FAQ, quote, closing band |
| `html/app.html` | Sidebar shell, breadcrumb top bar, tabs and filter chips, sortable data table with tabular numbers, empty state, settings form with inline validation, destructive confirm dialog, toast region, keyboard hints |
| `react/patterns.tsx` | `useUrlState`, `Tabs`, `NotesTable`, `EmptyState`, `TokenForm`, `ConfirmDialog`, `useToasts`, `ToastRegion`, and a screen that wires them together |

The React file carries no styling. It reuses the class names from
`html/app.html`, so behaviour and appearance stay in one place each.

## How to use them

1. Link or paste `../tokens.css` once per project. Nothing here works without it.
2. Copy the section you need, including its `<style>` block. Each file uses its
   own class prefix, `v-`, `m-` or `a-`, so two blocks never collide.
3. Replace the copy. The words in these blocks are deliberately specific about a
   fake product called Halyard. Specific copy is easier to replace than
   placeholder copy, and it stops the placeholder from shipping.
4. Delete what you do not need. A block is a floor, not a requirement.
5. Then push it: one signature move per screen, from `reference/01-direction.md`.

## The rules these blocks already follow

These are the same rules the linters check, shown in working form:

- Hover is inside `@media (hover: hover)`, so a tap on a phone never sticks.
- Every interactive element has `:focus-visible` with the `--focus` token.
- Transitions name their properties. `transition: all` is never used.
- Motion is disabled under `prefers-reduced-motion: reduce`.
- Numbers in tables and prices use `font-variant-numeric: tabular-nums`.
- Truncation always pairs `text-overflow` with `min-width: 0`.
- Scroll containers set `overscroll-behavior`, fixed bottom bars add
  `env(safe-area-inset-bottom)`.
- Icon buttons carry `aria-label`, decorative icons carry `aria-hidden`.
- Dates render inside `<time datetime>`, numbers through `Intl.NumberFormat`.
- The dialog is a native `<dialog>` with `showModal`, so Escape, the backdrop
  and the focus trap are the platform's job.
- Destructive actions ask for a typed confirmation, never a bare button.
- Submit buttons stay pressable so the form can explain what is wrong.
- Tab sets have one tab stop and move with arrow keys.
- Shareable state, tab, sort, filter and query, lives in the URL.

## Verifying a block after you edit it

```bash
# from the skill root
node scripts/check.mjs assets/blocks/html/app.html assets/tokens.css
node scripts/wig.mjs   assets/blocks/html/app.html
```

Pass `tokens.css` alongside the block. On its own a fragment defines no custom
properties, and `check.mjs` correctly reports `tokens-missing`.

## For the LITE lane

If you are running `LITE.md`, blocks are the one part of the full skill you
should open. Copy a block, swap the recipe colours, replace the copy, run
`check.mjs`. Do not read `SKILL.md` or `reference/` in that lane.
