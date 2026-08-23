# Snippets

Open this file at G4 or G5, copy **only** the component you need, then close it.
Every snippet assumes `tokens.css` is loaded. Every snippet already carries its
states. Never ship a copy with a state removed.

These are plain HTML and CSS on purpose. Port them to your framework, keep the
token references, the `44px` floor, the gated hover and the `focus-visible` ring.

## Button

```html
<button class="btn btn-primary" type="button">Publish</button>
<button class="btn btn-quiet" type="button">Preview</button>
<button class="btn btn-primary" type="button" disabled>Publishing</button>
<button class="btn btn-icon" type="button" aria-label="Copy link">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
    <path d="M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1" />
    <path d="M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1" />
  </svg>
</button>
```

```css
.btn {
  display: inline-flex; align-items: center; justify-content: center;
  gap: var(--space-2);
  min-height: 44px; padding: 0 var(--space-4);
  border: 1px solid transparent; border-radius: var(--r-md);
  font: inherit; font-size: var(--text-sm); font-weight: var(--weight-medium);
  cursor: pointer;
  transition:
    background-color var(--dur-instant) var(--ease-out),
    border-color var(--dur-instant) var(--ease-out),
    transform var(--dur-instant) var(--ease-out);
}
.btn-primary { background: var(--accent); color: var(--accent-ink); box-shadow: var(--shadow-1); }
.btn-quiet   { background: transparent; color: var(--ink); border-color: var(--control-border); }
.btn-icon    { width: 44px; padding: 0; background: transparent; color: var(--ink-muted); }
@media (hover: hover) {
  .btn-primary:hover { background: var(--accent-hover); }
  .btn-quiet:hover   { background: var(--surface); }
  .btn-icon:hover    { color: var(--ink); background: var(--surface); }
}
.btn:active   { transform: scale(0.985); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
```

Rules: label names the action, never "Submit". Icon-only buttons always carry
`aria-label`. One primary action per view. A loading button keeps its width.

## Input and field

```html
<div class="field">
  <label for="repo">Repository</label>
  <input id="repo" name="repo" type="text" autocomplete="off"
         placeholder="owner/name" aria-describedby="repo-hint" />
  <p class="field-hint" id="repo-hint">Read access is enough.</p>
</div>

<div class="field" data-invalid="true">
  <label for="email">Work email</label>
  <input id="email" name="email" type="email" aria-invalid="true" aria-describedby="email-error" />
  <p class="field-error" id="email-error">Add the domain, for example you@company.com</p>
</div>
```

```css
.field { display: flex; flex-direction: column; gap: var(--space-2); }
.field label { font-size: var(--text-sm); color: var(--ink-muted); }
.field input {
  min-height: 44px; padding: 0 var(--space-3);
  background: var(--canvas); color: var(--ink);
  border: 1px solid var(--control-border); border-radius: var(--r-md);
  font: inherit; font-size: var(--text-sm);
  transition: border-color var(--dur-instant) var(--ease-out);
}
.field input:focus-visible { border-color: var(--accent); outline: 2px solid var(--focus); outline-offset: 1px; }
.field input:disabled { background: var(--surface); color: var(--ink-subtle); }
.field-hint  { font-size: var(--text-xs); color: var(--ink-subtle); }
.field-error { font-size: var(--text-xs); color: var(--danger); }
.field[data-invalid="true"] input { border-color: var(--danger); }
```

Rules: a placeholder is not a label. The error names the fix, not the failure.
Errors appear on blur or submit, never mid-typing.

## Card

```html
<article class="card">
  <h3>Weekly digest</h3>
  <p>One message on Friday with everything that shipped.</p>
  <a class="card-action" href="/digest">Set it up</a>
</article>
```

```css
.card {
  padding: var(--space-6);
  background: var(--surface);
  border: 1px solid var(--hairline);   /* elevation declared ONCE: border or shadow */
  border-radius: var(--r-lg);
  transition: border-color var(--dur-base) var(--ease-out);
}
@media (hover: hover) { .card:hover { border-color: var(--control-border); } }
.card h3 { font-size: var(--text-h3); margin-bottom: var(--space-2); }
.card p  { color: var(--ink-muted); font-size: var(--text-sm); }
```

Rules: pick border **or** shadow, not both. A whole card is clickable only if
the entire surface is one link. Three identical cards in a row is a layout stub,
not a composition.

## Table

```html
<table class="table">
  <caption class="sr-only">Published notes</caption>
  <thead>
    <tr><th scope="col">Note</th><th scope="col">Repo</th><th scope="col" class="num">Reads</th></tr>
  </thead>
  <tbody>
    <tr><td>Faster diff parsing</td><td>halyard/core</td><td class="num">1,284</td></tr>
    <tr><td>Slack approvals</td><td>halyard/bots</td><td class="num">932</td></tr>
  </tbody>
</table>
```

```css
.table { width: 100%; border-collapse: collapse; font-size: var(--text-sm); }
.table th, .table td { padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--hairline); }
.table th { text-align: left; font-weight: var(--weight-medium); color: var(--ink-muted); }
.table .num { text-align: right; font-variant-numeric: tabular-nums; }
.table tbody tr:last-child td { border-bottom: 0; }
@media (hover: hover) { .table tbody tr:hover { background: var(--surface); } }
```

Rules: numbers right-aligned and tabular, always. Header row is a label row, not
a banner. No zebra striping when a hairline already separates rows.

## Dialog

```html
<dialog class="dialog" id="confirm">
  <h2>Publish to 4,200 subscribers</h2>
  <p>The note goes out immediately. You can edit it afterwards, they keep the first version.</p>
  <div class="dialog-actions">
    <button class="btn btn-quiet" type="button" data-close>Keep editing</button>
    <button class="btn btn-primary" type="button">Publish now</button>
  </div>
</dialog>
```

```css
.dialog {
  max-width: 32rem; padding: var(--space-7);
  background: var(--canvas); color: var(--ink);
  border: 1px solid var(--hairline); border-radius: var(--r-lg);
  box-shadow: var(--shadow-4);
}
.dialog::backdrop { background: var(--scrim); backdrop-filter: blur(2px); }
.dialog[open] { animation: dialog-in var(--dur-base) var(--ease-out); }
.dialog-actions { display: flex; justify-content: flex-end; gap: var(--space-3); margin-top: var(--space-7); }
@keyframes dialog-in {
  from { opacity: 0; transform: translateY(6px) scale(0.98); }
  to   { opacity: 1; transform: none; }
}
@media (prefers-reduced-motion: reduce) { .dialog[open] { animation: none; } }
```

Rules: use the native `dialog` element for focus trapping and Escape. Enter from
`0.98`, never from `0`. The destructive action names what it destroys.

## Empty state

```html
<div class="empty">
  <h3>No notes yet</h3>
  <p>Connect a repository and the first draft appears after the next merge.</p>
  <button class="btn btn-primary" type="button">Connect a repository</button>
</div>
```

```css
.empty {
  display: grid; justify-items: start; gap: var(--space-3);
  padding: var(--space-9);
  border: 1px dashed var(--hairline); border-radius: var(--r-lg);
}
.empty p { color: var(--ink-muted); font-size: var(--text-sm); }
```

Rules: an empty state has one job, to start the first action. No illustration
unless the product already has an illustration language.

## Skeleton

```css
.skeleton {
  background: linear-gradient(90deg, var(--surface) 25%, var(--surface-2) 37%, var(--surface) 63%);
  background-size: 400% 100%;
  border-radius: var(--r-sm);
  animation: shimmer 1.4s var(--ease-linear) infinite;
}
.skeleton-line { height: 0.75rem; }
@keyframes shimmer { from { background-position: 100% 0; } to { background-position: 0 0; } }
@media (prefers-reduced-motion: reduce) { .skeleton { animation: none; } }
```

Rules: the skeleton has the shape of the content that replaces it, otherwise the
layout jumps. Under 300ms of wait, show nothing at all.

## Toast

```css
.toast {
  position: fixed; inset-block-end: var(--space-4); inset-inline-start: 50%;
  translate: -50% 0; z-index: var(--z-5);
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--ink); color: var(--canvas);
  border-radius: var(--r-md); box-shadow: var(--shadow-3);
  animation: toast-in var(--dur-base) var(--ease-out);
}
@keyframes toast-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .toast { animation: none; } }
```

Rules: a toast confirms, it never asks. Anything that needs a decision is a
dialog. Errors that block work belong next to the thing that failed.

## Icons

One set, one stroke weight, one size scale. `stroke-width: 1.5` at 16px and 20px,
`currentColor` for the stroke, `aria-hidden="true"` when a text label is present,
`aria-label` on the button when it is not. Never mix two icon libraries, and never
use an emoji as an icon.

```html
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
     stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M20 6 9 17l-5-5" />
</svg>
```

## Utilities worth having

```css
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0;
}
.tnum { font-variant-numeric: tabular-nums; }
.stack > * + * { margin-top: var(--space-4); }
.safe-bottom { padding-bottom: max(var(--space-4), env(safe-area-inset-bottom)); }
```
