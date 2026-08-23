# 03 - UI integrity: no overlapping, no stacking, no style wars

Read for any work on a visible surface: screens, components, layouts, modals, panels, toasts, styles.

**Core rules**
1. The app mounts **once**.
2. Every surface has **one owner**. A new panel **replaces or extends** the existing one - it never covers it.
3. Layering comes from **one shared scale**, never from a local number.
4. Every setup has a **paired teardown**.
5. You verify the **rendered result**, not the source you just wrote.

---

## 1. Mount once

Symptoms of a double mount: the interface appears twice, an old screen shows through a new one, clicks hit an invisible copy, state resets randomly, CPU stays busy on an idle page.

- Exactly **one** root render call in the whole app (`createRoot`/`render`/`createApp`/`mount`/`new App`). Check: `python3 scripts/ui_guard.py .` reports every mount point it finds.
- Initialization must be idempotent: calling it twice does nothing the second time.

```js
// one root, guarded
let root
export function mountApp(el) {
  if (root) return root          // second call is a no-op
  root = createRoot(el)
  root.render(<App />)
  return root
}
```

- Never create a container element unconditionally. Look for the existing node first:

```js
function getOverlayHost() {
  return document.getElementById('overlay-host')
    ?? Object.assign(document.createElement('div'), { id: 'overlay-host' })
}
```

- Server-rendered or hot-reloaded environments: guard module-level side effects so a re-import does not attach a second instance.

## 2. One owner per surface (replace, do not stack)

Before adding any visible container, answer these three questions in writing:

| Question | If yes |
|---|---|
| Does a component for this surface already exist? | extend it with a prop/variant; do not create a sibling |
| Is this a modal / drawer / toast / tooltip? | route it through the **single host** for that family, with one active item at a time |
| Does the new surface appear while another one is open? | decide explicitly: replace, nest inside, or refuse to open. Never "both on screen by accident" |

Patterns that keep this true:
- **One host per family**: one modal host, one toast container, one tooltip layer - each rendered once, near the app root.
- **One state owner**: the open/closed state of a surface lives in exactly one place. Two components must never both be able to open the same surface independently.
- Opening a second modal closes or stacks it **through the host's rules**, not by rendering another fixed-position div.
- Same rule for layout regions: one header, one sidebar, one content region, each rendered by one owner. A screen does not render its own copy of a shell element.

## 3. Layering: one scale, no escalation

z-index wars (`999`, `1000`, `99999`) are the visible sign of two owners fighting. Fix the ownership, not the number.

```css
/* tokens.css - the ONLY place layer values are defined */
:root {
  --layer-base: 0;
  --layer-sticky: 100;
  --layer-dropdown: 200;
  --layer-modal: 300;
  --layer-toast: 400;
  --layer-tooltip: 500;
}
```

- Components use `z-index: var(--layer-modal)`; never a literal.
- More than a few distinct literal values in the codebase means the scale is not being used - consolidate.
- Stacking context traps: `transform`, `filter`, `will-change`, `opacity < 1`, `contain` create a new context, so a child's high z-index cannot escape its parent. Move the surface into the shared host instead of raising numbers.
- `position: fixed; inset: 0` is a full-screen blocker. Count them: more than one active at a time is a bug.

## 4. Styles that do not fight

- Scope styles to their component: CSS modules, scoped blocks, or a component prefix (`.card__title`). Two files must never define the same class name.
- No bare element selectors (`div`, `p`, `section`, `button`) outside a single reset/base file - they silently overwrite component padding and margins. A generic `.section { padding: 24px }` plus a later `section { padding: 0 }` is how spacing mysteriously disappears.
- **No `!important`.** It means another owner already sets the property; find that owner.
- Keep specificity flat and equal across components. Escalating selectors (`.a .b .c .d`) is escalation by another name.
- Design tokens (spacing, color, radius, font, layer) have one owner. Components never hardcode a hex value or a pixel scale.
- Responsive and theme states are part of "done": check narrow width and the alternate theme before claiming completion.

## 5. Teardown pairs (leaks and ghost handlers)

Every acquisition needs its release, in the same unit that acquired it.

| Setup | Teardown |
|---|---|
| `addEventListener` | `removeEventListener` (or one `AbortController` + `signal`) |
| `setInterval` / `setTimeout` | `clearInterval` / `clearTimeout` |
| `requestAnimationFrame` loop | `cancelAnimationFrame` |
| Resize/Intersection/Mutation observer | `disconnect()` |
| store / socket / event-bus subscription | `unsubscribe()` / `close()` |
| in-flight request tied to a view | `abort()` on unmount |
| body scroll lock, focus trap, global class | restore the previous value on close |
| DOM node appended to `body` | remove it on unmount |

Ghost handlers cause "the old interface is still reacting" bugs: two listeners, two responses, one of them from a screen the user already left.

Leak check: open and close the surface 10 times, then confirm listener count and memory return to the starting level.

## 6. Interaction correctness minimums

- Focus: a modal traps focus and returns it to the trigger on close. Only one element owns focus.
- Keyboard: `Escape` closes the topmost surface only. Enter/space work on interactive elements.
- Scroll lock is owned by the host, released exactly once.
- Loading, empty, error and long-content states exist for every new surface - not just the happy path.
- Test hooks: give interactive elements stable, repository-owned identifiers (`data-testid` or the repo's convention). Never target elements by visible text, CSS position or class in tests.

## 7. Verification for UI work (never skip)

```bash
python3 scripts/ui_guard.py . --strict
```

Then prove the rendered state, by whatever the repo supports: component test asserting a **single** instance of the surface, DOM assertion after open/close cycles, snapshot of the mounted tree, or a browser check. Minimum evidence for a UI change:

```
[ ] the surface appears exactly once (asserted, not assumed)
[ ] the previous surface is gone, not hidden behind it
[ ] open -> close -> open leaves no residue (listeners, nodes, scroll lock)
[ ] narrow viewport and alternate theme look intact
[ ] no new ui_guard findings
```

If you cannot render it in this environment, say `UNPROVEN: rendered state not verified - no browser available` and list exactly what a human should click.
