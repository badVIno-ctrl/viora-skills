# 06 - Motion

Loaded at G4 or G5 whenever anything moves. Purpose: a small number of correct, deliberate movements. Close when the motion is built.

Motion is the fastest way to make an interface feel expensive and the fastest way to make it feel cheap. The difference is not quantity, it is whether each movement was authored.

## 1. The gate: should this animate at all

Answer before writing a single transition.

| How often will a user see it? | Treatment |
|---|---|
| 100+ times a day (list rows, table sorts, tab switches) | Do not animate. Instant. |
| Tens of times a day (dropdowns, tooltips, toggles) | Near-imperceptible: 100-150ms, opacity and 2-4px of movement at most. |
| A few times a session (modals, drawers, page transitions) | Standard: 200-300ms with a real easing curve. |
| Once, or rarely (onboarding, success, first run, empty state) | Delight budget: this is where a spring, a stagger, or a small surprise is earned. |

Second question: **what does this movement tell the user?** Valid answers: where the thing came from, that the system heard them, what changed, what is loading, what is now in focus. "It looks nice" is not an answer; that is decoration and it costs attention every single time.

Third question: **has this product already spent its delight budget?** One authored moment per product, two at most. The second signature move devalues the first, and a page where everything is special has nothing special on it. Write down which moment is the one, then keep everything else at state feedback.

Hard consequence of `MOTION` dial from `01-direction.md`:
- `MOTION 1-2`: state feedback only. No scroll reveals, no entrance animation.
- `MOTION 3`: entrances on the first viewport plus state feedback. One scroll-triggered moment maximum.
- `MOTION 4-5`: motion carries the narrative. Still one system, still under the duration caps.

## 2. Tool ladder - always take the lowest rung that works

1. **CSS `transition`** - hover, focus, active, open and closed states driven by a class or attribute. Covers 80% of real needs.
2. **`@starting-style` plus `transition-behavior: allow-discrete`** - animating an element in as it enters the DOM, including `display: none` to `block` and popover or dialog. No JS.
3. **CSS `@keyframes`** - looping or multi-step sequences (spinners, shimmer, marquee).
4. **Web Animations API** - when you need to interrupt, reverse, or read progress in JS.
5. **A motion library** (Motion / Framer Motion) - only for layout animation, shared-element transitions, drag, gesture, or orchestration that the above cannot express.
6. **View Transitions API** - cross-document or same-document route transitions.

Do not install a 40KB animation library to fade in a card.

## 3. Easing

Already in `tokens.css`. Never invent a curve.

| Token | Curve | Use |
|---|---|---|
| `--ease-out` | `cubic-bezier(0.23, 1, 0.32, 1)` | **Default for everything the user triggers.** Fast start, gentle settle |
| `--ease-in-out` | `cubic-bezier(0.77, 0, 0.175, 1)` | Movement that starts and ends on screen |
| `--ease-drawer` | `cubic-bezier(0.32, 0.72, 0, 1)` | Sheets, drawers, panels sliding from an edge |
| `--ease-linear` | `linear` | Only continuous motion: spinners, marquees, progress |

Rules:

- **Never `ease-in` on an entrance.** It starts slow, which reads as lag. `ease-in` is for exits only, and only when the element leaves the screen.
- **Never bare `ease`, `ease-in-out` shorthand, or the browser default** on anything the user notices. The default curve is why generated UI feels floaty.
- Springs: use for drag, gesture, and playful one-off moments. `{ type: "spring", duration: 0.5, bounce: 0.2 }`. Bounce above 0.3 is a toy. Bounce on a modal is a bug.
- One curve family per project. Mixed easings read as inconsistent even when nobody can name why.

## 4. Duration

| Interaction | Duration |
|---|---|
| Colour and opacity on hover | 100-150ms |
| Button press feedback | 100-160ms |
| Tooltip, small popover | 125-200ms |
| Dropdown, select, menu | 150-250ms |
| Modal, dialog | 200-300ms |
| Drawer, sheet, side panel | 250-400ms (travel distance justifies it) |
| Page or route transition | 300-500ms |
| Exit animations | 70-80% of the entrance duration |
| Stagger between siblings | 30-80ms, cap the total at 400ms |

**Cap for anything in-app: 300ms.** Above that the interface feels slow no matter how pretty the curve is. Longer distances get longer durations; a 4px shift and a 400px drawer should not share a duration.

## 5. What can move

Only `transform` and `opacity` for anything that runs at 60fps. Also cheap: `filter` in moderation, `clip-path` on small areas.

Never animate `width`, `height`, `top`, `left`, `margin`, or `box-shadow` on a hot path. For size changes use `transform: scale()`, a grid-template trick, or `interpolate-size: allow-keywords` with `height: auto` where supported.

| Never ship | Why | Instead |
|---|---|---|
| `transition: all` | animates properties you never intended, including layout | name each property |
| `scale(0)` to `scale(1)` | material appearing from nothing looks fake | `scale(0.96)` to `scale(1)` |
| `opacity: 0` with no movement on an entrance | reads as a rendering glitch | pair with 4-12px of translate |
| Fade-in of an entire page section on scroll | delays content the user asked for | show it, or animate one element |
| Hover animation without `@media (hover: hover)` | fires on tap and sticks on touch devices | gate it |
| A spinner for something under 300ms | flashes and looks broken | show nothing, or an optimistic result |
| A loop with no end condition | eats battery and attention | one-shot, or pause offscreen |
| Animation on a scroll event listener | jank, main-thread bound | CSS `animation-timeline: view()` or IntersectionObserver |
| Bounce on modals, drawers, tooltips | undermines authority | plain `--ease-out` |
| Blur transitions on text | unreadable mid-flight and expensive | opacity only |

## 6. Recipes

### Button press

```css
.button {
  transition: background-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out);
}
@media (hover: hover) and (pointer: fine) {
  .button:hover { background: var(--accent-hover); }
}
.button:active { transform: scale(0.98); }
```

### Entrance with `@starting-style`, no JS

```css
.panel {
  opacity: 1;
  translate: 0 0;
  transition: opacity var(--dur-base) var(--ease-out), translate var(--dur-base) var(--ease-out);
}
@starting-style {
  .panel { opacity: 0; translate: 0 8px; }
}
```

### Dialog with a discrete property

```css
dialog {
  opacity: 0;
  transform: scale(0.97) translateY(8px);
  transition: opacity var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out), overlay var(--dur-base) allow-discrete, display var(--dur-base) allow-discrete;
}
dialog[open] { opacity: 1; transform: none; }
@starting-style { dialog[open] { opacity: 0; transform: scale(0.97) translateY(8px); } }
dialog::backdrop { background: transparent; transition: background var(--dur-base) var(--ease-out), overlay var(--dur-base) allow-discrete, display var(--dur-base) allow-discrete; }
dialog[open]::backdrop { background: var(--scrim); }
```

### Menu or popover that grows from its trigger

Set the origin so it appears to come from the thing that opened it. This one detail separates a real menu from a floating box.

```css
.menu { transform-origin: var(--transform-origin, top center); }
```

Radix, Base UI, and similar libraries expose `--radix-popover-content-transform-origin` or an equivalent. Use it. Exception: modals and dialogs are centered by design and use `top center`.

### Accordion / disclosure height

```css
.details-content { height: 0; overflow: hidden; transition: height var(--dur-slow) var(--ease-out); }
.details[open] .details-content { height: auto; }
@supports (interpolate-size: allow-keywords) { :root { interpolate-size: allow-keywords; } }
```

Fallback without `interpolate-size`: animate a CSS grid row from `0fr` to `1fr`.

### Scroll reveal, no JS, no jank

```css
@media (prefers-reduced-motion: no-preference) {
  @supports (animation-timeline: view()) {
    .reveal {
      animation: reveal linear both;
      animation-timeline: view();
      animation-range: entry 10% cover 30%;
    }
    @keyframes reveal { from { opacity: 0; translate: 0 16px; } to { opacity: 1; translate: 0 0; } }
  }
}
```

One group of elements per page, not every section. Content above the fold never waits for a reveal.

### Stagger

```css
.item { animation: rise var(--dur-slow) var(--ease-out) both; animation-delay: calc(var(--i) * var(--stagger)); }
@keyframes rise { from { opacity: 0; translate: 0 10px; } to { opacity: 1; translate: 0 0; } }
```

Maximum 8 items. Past that the last item arrives after the user has moved on.

### Number transition

Count up only on first view, `linear` easing, `tabular-nums` so the layout does not jitter, 400-600ms, and never on a value the user is actively editing.

### Skeleton shimmer

One shimmer definition, matching the real content's exact geometry, and only for loads expected to exceed 400ms. A skeleton whose shape differs from the loaded content causes a visible jump, which is worse than a spinner.

### Motion library, correct form

```jsx
<motion.div
  initial={{ opacity: 0, transform: "translateY(8px) scale(0.98)" }}
  animate={{ opacity: 1, transform: "translateY(0px) scale(1)" }}
  exit={{ opacity: 0, transform: "translateY(4px) scale(0.99)" }}
  transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
/>
```

Write the full `transform` string rather than separate `x` / `y` / `scale` keys when several transform parts animate together: independent transform properties can interpolate out of sync and produce a wobble.

### Route transition, no library

```css
@view-transition { navigation: auto; }
::view-transition-old(root),
::view-transition-new(root) { animation-duration: var(--dur-slow); }
```

Give `view-transition-name` only to elements that genuinely persist across the navigation, and never to more than two. Everything else cross-fades, which is correct. Check it with the back button: a transition that only works forwards is half-built.

## 7. Interruption and symmetry

- Every animation must survive being interrupted. Opening and closing a menu quickly three times must not leave it half-open or double-mounted.
- Exits mirror entrances, at 70-80% of the duration, along the same axis. An element that slides up from the bottom must leave downward.
- No animation may block input. The user can click the button again while it animates.
- Never animate something the user is dragging or typing into.
- Interruptible means implemented, not hoped for. With CSS, transitions on a class or attribute toggle handle it for free. With JS, hold the animation and reverse it (`el.getAnimations()`, `animation.reverse()`, `animation.currentTime`) instead of starting a second animation on top of the first.
- Drag dismiss uses velocity, not distance alone: a flick faster than roughly `0.11` px/ms in the dismiss direction completes the gesture even if the travel was short. Distance-only thresholds feel sticky and cheap.
- On fast travel, up to 2px of blur along the axis of motion sells the speed. Above 2px it is a smear, and never on text.
- Every duration and every curve comes from a token. A raw `340ms` in a component is how a system becomes eleven slightly different speeds.

## 8. Reduced motion - ships in the same commit

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

This global damp is already in `tokens.css`. Beyond it: replace essential motion with an instant state change, never remove the feedback entirely. Keep opacity fades under 200ms if a transition genuinely carries meaning; what must go is movement, parallax, and auto-playing loops.

Also honour `prefers-reduced-transparency` if the direction uses glass, and never autoplay video with sound.

## 9. Perceived performance

Often worth more than any animation.

- Respond to input within 100ms, even if the response is only a pressed state.
- Optimistic UI: show the result immediately, reconcile with the server after. Roll back visibly if it fails.
- Preload on `pointerenter` or on `pointerdown`, so the navigation feels instant.
- Skeletons only above 400ms; below that, nothing.
- Reserve space for anything async so nothing shifts when it lands. Cumulative layout shift is felt as cheapness.
- Targets: LCP under 2.5s, INP under 200ms, CLS under 0.1.

## Output of this gate

One or two authored moments, tokens used for every curve and duration, reduced motion in place, no banned pattern present. Continue.
