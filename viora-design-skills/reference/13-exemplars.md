# 13 - Exemplars

<!-- viora-allow-file: the rejected column is deliberately wrong, that is the whole point of this file -->

Contrastive pairs. Left is what a model writes by default. Right is what ships.
Read this when the output is technically correct and still looks generated, or when
the checker is clean but the page has no character.

Every pair is the same content, same effort, different decision. Copy the shape of
the right column, never the left.

1. Hero
2. Feature section
3. Card grid to ledger
4. Button
5. Form field
6. Table
7. Empty state
8. Motion
9. Copy
10. The diff test

---

## 1. Hero

**Default, rejected.** Centered stack, kicker, gradient headline, two buttons of equal weight, three round metrics.

```html
<section class="text-center py-24">
  <p class="uppercase tracking-widest text-sm">Analytics platform</p>
  <h1 class="text-5xl bg-gradient-to-r from-violet-500 to-blue-500 bg-clip-text">
    Unlock Powerful Insights Seamlessly
  </h1>
  <p>The all-in-one solution for modern teams.</p>
  <button>Get started</button> <button>Learn more</button>
</section>
```

**Decided, ships.** One alignment edge, one claim with a number in it, one primary action, one supporting line that names the mechanism.

```html
<section class="hero">
  <h1>Queries over 40 billion events, answered in under a second.</h1>
  <p>Point it at your warehouse. No pipeline, no pre-aggregation, no cube to rebuild.</p>
  <div class="hero-actions">
    <a class="btn btn-primary" href="/signup">Connect a warehouse</a>
    <a class="btn-quiet" href="/docs/latency">How the latency is measured</a>
  </div>
</section>
```

Why: the claim is falsifiable, the second action is a link and not a twin button, and the hierarchy survives grayscale.

---

## 2. Feature section

**Default, rejected.** Six identical tiles, icon plus heading plus two lines, nothing said.

```html
<div class="grid grid-cols-3 gap-6">
  <div class="rounded-xl border p-6 shadow">
    <Icon /><h3>Fast</h3><p>Blazing fast performance for your team.</p>
  </div>
  <!-- x5 more, same shape -->
</div>
```

**Decided, ships.** One claim gets the room, and the rest become a scannable ledger.

```html
<section class="split">
  <div>
    <h2>Cold queries stay under a second</h2>
    <p>Every column is stored sorted, so a filter is a range scan and not a table scan.
      The first query of the morning is as fast as the hundredth.</p>
  </div>
  <figure><img src="/img/query-plan.png" width="720" height="480"
    alt="Query plan showing a 0.6s range scan across 40 billion rows"></figure>
</section>

<dl class="ledger">
  <div><dt>Storage</dt><dd>Sorted columnar, 11x compression on event data</dd></div>
  <div><dt>Freshness</dt><dd>Streaming ingest, visible in queries within 4 seconds</dd></div>
  <div><dt>Access</dt><dd>SQL, Postgres wire protocol, existing BI tools connect unchanged</dd></div>
</dl>
```

Why: hairline rows carry more information per pixel than cards, and one large statement beats six small ones.

---

## 3. Card grid to ledger

The single highest-value substitution in this skill. When you have a list of short
facts, do not wrap each one in a bordered, rounded, shadowed box.

```css
/* rejected: a card per list item */
.card { border: 1px solid var(--hairline); border-radius: var(--r-lg);
        box-shadow: 0 4px 6px rgba(0,0,0,.1); padding: var(--space-6) }

/* ships: hairline rows, one surface level */
.ledger > div { display: grid; grid-template-columns: 12rem 1fr;
  gap: var(--space-6); padding: var(--space-4) 0;
  border-block-end: 1px solid var(--hairline) }
.ledger dt { color: var(--ink-muted) }
.ledger dd { margin: 0 }
```

---

## 4. Button

```html
<!-- rejected: gradient, glow, no states, vague label -->
<button class="bg-gradient-to-r from-purple-600 to-blue-500 shadow-lg rounded-full">
  Learn More
</button>
```

```css
/* ships: one accent, named action, every state, real focus ring */
.btn-primary {
  block-size: 2.5rem; padding-inline: var(--space-5);
  background: var(--accent); color: var(--accent-ink);
  border-radius: var(--r-md); font-weight: 560;
  transition: background var(--dur-fast) var(--ease-out),
              transform var(--dur-fast) var(--ease-out);
}
@media (hover: hover) and (pointer: fine) {
  .btn-primary:hover { background: var(--accent-hover) }
}
.btn-primary:active { transform: translateY(1px) }
.btn-primary:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px }
.btn-primary[disabled] { opacity: .5; cursor: not-allowed }
```

Label it `Connect a warehouse`, never `Learn more`, `Get Started` or `Click here`.

---

## 5. Form field

```html
<!-- rejected: placeholder as label, no error path, invisible border -->
<input placeholder="Email" class="border-gray-200 rounded p-2">
```

```html
<!-- ships: visible label, format hint, error that names the recovery -->
<div class="field">
  <label for="email">Work email</label>
  <input id="email" type="email" name="email" autocomplete="email"
    aria-describedby="email-hint email-err" aria-invalid="true">
  <p id="email-hint" class="hint">We send the invoice here. Use a domain you control.</p>
  <p id="email-err" class="error">This domain has no MX record. Check the spelling, or use a personal address.</p>
</div>
```

The field border uses `--control-border`, not `--hairline`: it is the only affordance, so it must clear 3:1.

---

## 6. Table

```css
/* rejected: zebra stripes, centered numbers, borders on every cell */
td { text-align: center; border: 1px solid #eee }
tr:nth-child(even) { background: #fafafa }
```

```css
/* ships: numbers right-aligned and tabular, one hairline per row, sticky head */
.tbl { inline-size: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums }
.tbl th { position: sticky; inset-block-start: 0; background: var(--surface);
  text-align: start; font-weight: 560; color: var(--ink-muted) }
.tbl td, .tbl th { padding: var(--space-3) var(--space-4);
  border-block-end: 1px solid var(--hairline) }
.tbl td.num { text-align: end }
```

Why: a column of numbers that jitters is the fastest way to look unfinished.

---

## 7. Empty state

```html
<!-- rejected -->
<div class="text-center py-20"><p>No data available</p></div>
```

```html
<!-- ships: what goes here, why it is empty, the action that fills it -->
<div class="empty">
  <h3>No queries yet</h3>
  <p>Saved queries appear here so the team can rerun them without rewriting SQL.</p>
  <a class="btn btn-primary" href="/query/new">Write the first query</a>
  <a class="btn-quiet" href="/docs/import">Or import from dbt</a>
</div>
```

---

## 8. Motion

```css
/* rejected: everything animates, on entrance, slowly, on every property */
* { transition: all .5s ease-in-out }
.card { animation: fadeInUp 1s ease-in both }
```

```css
/* ships: one authored moment, transform and opacity, exit shorter than entry */
@media (prefers-reduced-motion: no-preference) {
  .row { transition: background var(--dur-fast) var(--ease-out) }
  .sheet { transition: translate var(--dur-base) var(--ease-out),
                       opacity var(--dur-fast) var(--ease-out) }
  .sheet[hidden] { translate: 0 8px; opacity: 0 }
}
```

---

## 9. Copy

| Rejected | Ships |
|---|---|
| Seamlessly integrate with your existing workflow | Reads your dbt manifest, so models keep their names |
| Trusted by thousands of teams worldwide | 40 engineering teams, including two of the four largest exchanges in the region |
| Blazing fast performance | p95 of 780ms across 40 billion rows |
| Ready to get started? | Connect a warehouse |
| Something went wrong | Upload failed at 40MB. The limit is 25MB per file. Split it, or use the CLI. |

Russian copy follows Russian habits: `«кавычки»`, non-breaking space before units, no Title Case, no borrowed marketing English.

---

## 10. The diff test

Before reporting at G7, put the built page next to a generic template of the same
category and answer three questions in one line each:

1. What would have to change for this to become that template? If the answer is
   "the palette", the direction never got built, only painted.
2. Which single element would a visitor describe to a colleague? If none, the
   signature moment was skipped.
3. What did you delete? If nothing, the subtraction pass did not happen.
