# Mobile

Most of what ships is looked at on a phone held in one hand, often outdoors, often while something
else is happening. Desktop is the calm case. Design the hard case first and the calm one is a
reduction, not a rewrite.

Read this when the brief mentions a phone, an app shell, a form people fill on the move, or when the
mode is APP. In the LITE lane read only the first two sections and the checklist at the end.

## Reach

A thumb on a modern phone comfortably covers the lower two thirds of the screen and the side it is
held on. The top corners are the worst real estate on the device, and the top left is the worst of
the two for a right-handed grip.

- Primary actions go low: a bottom bar, a sticky footer button, or a sheet.
- Destructive actions go where the thumb does not rest by accident. Not next to the primary action.
- Navigation that is used constantly belongs at the bottom. A hamburger in the top corner is fine for
  rarely visited pages and wrong for the three screens people live in.
- Back must exist as a visible control, not only as a system gesture. Gesture-only back fails the
  moment a keyboard is open or the user is wearing gloves.

## Targets and spacing

- 44 by 44 CSS pixels is the floor for anything tappable, 48 is the honest target for a primary
  action. The visual element can be smaller than the hit area, and usually should be.
- Eight pixels of clear space between two adjacent targets. Adjacent targets with no gap produce
  wrong taps, and wrong taps in a destructive row produce support tickets.
- Icon-only controls need an accessible name. On a phone there is no hover to explain them, so if the
  icon is not obvious, it needs a visible label, not a tooltip.
- Row height in a scannable list stays constant. Variable heights make a list impossible to scan with
  a thumb.

## Viewport, safe areas and the keyboard

```css
:root {
	--pad-bottom: max(var(--space-4), env(safe-area-inset-bottom));
}

.app-shell {
	min-height: 100dvh;               /* not 100vh: the toolbar steals it */
	padding-bottom: var(--pad-bottom);
	overscroll-behavior-y: contain;   /* no pull-to-refresh under a sheet */
}

.sticky-cta {
	position: sticky;
	bottom: 0;
	padding-bottom: var(--pad-bottom);
}
```

- `100vh` on a phone is a bug: it is measured against the largest viewport, so a hundred-vh section
  hides its bottom under the browser toolbar. Use `100dvh`, or `min-height` with content flow.
- `env(safe-area-inset-*)` both top and bottom. A notch eats a heading, a home bar eats a button.
- When the keyboard opens, the focused field must stay visible. Test it: focus the last field of a
  long form and check that the submit button is reachable without dismissing the keyboard.
- Never disable zoom. `maximum-scale=1` and `user-scalable=no` are accessibility failures, and they
  are also the reason people cannot read your 14 pixel legal text.
- Font size in a text input stays at 16 pixels or larger, or iOS zooms the page on focus and the
  layout jumps.

## Input types matter more here than anywhere

On a phone the wrong keyboard costs a real fraction of completions.

| Field | What to set |
|---|---|
| Email | `type="email"` with `autocomplete="email"` and `inputmode="email"` |
| Phone | `type="tel"` with `autocomplete="tel"`, no masked format that fights paste |
| One-time code | `autocomplete="one-time-code"`, `inputmode="numeric"` |
| Card number | `autocomplete="cc-number"`, `inputmode="numeric"`, paste allowed |
| Quantity or price | `inputmode="decimal"`, never `type="number"` with spinners in a mobile row |
| Search | `type="search"`, `enterkeyhint="search"` |
| Registration or serial | `inputmode="text"`, `autocapitalize="characters"`, `spellcheck="false"` |

And never block paste. Not on the email, not on the confirmation, not on the card. `wig.mjs` treats
`paste-blocked` as an error for this reason.

## Layout that survives a narrow column

- One column at 390 pixels. Two columns only above roughly 700, and only when both halves are
  independently useful.
- Tables do not shrink. Turn each row into a card, or keep the table and let it scroll horizontally
  inside its own container with a visible edge, never with a hidden overflow hack on the body.
- Long words break the layout. Cyrillic and German compounds are worse than English. Set
  `overflow-wrap: anywhere` on any container that shows user-supplied names.
- Truncation inside a flex row needs `min-width: 0` on the shrinking child, otherwise the ellipsis
  never appears and the row pushes its neighbour off screen.
- Russian copy runs longer than the English original, often by a sixth. Buttons and tabs sized to fit
  English text will wrap in Russian. Check the longest label, not the average one.

## Images and load

- The hero image is the largest paint on a phone. Give it explicit dimensions, `fetchpriority="high"`,
  and no lazy attribute. Everything below the fold is lazy.
- Serve a phone-sized file. A 2400 pixel wide photograph on a 390 pixel screen is the most common
  reason a mobile page feels slow while looking fine on the designer's laptop.
- Reserve space for anything that arrives late: images, embeds, banners, cookie notices. A layout that
  shifts after the tap has already begun is worse than a slow layout.

## Sunlight, gloves and one hand

These are real conditions, not edge cases, and they change the design:

- Outdoors, contrast below the accessible minimum disappears. For field tools push body text past 7:1
  and avoid grey-on-grey secondary text entirely.
- With gloves or wet fingers, precision drops. Bigger targets, more spacing, no drag-only controls.
- One hand means one thumb. Anything that needs two hands, such as a pinch or a two-finger gesture,
  needs a single-finger alternative.
- Every gesture needs a visible equivalent. Swipe to delete is a shortcut, not a feature.

## Motion on a phone

- Shorter than on desktop. 150 to 250 milliseconds for a transition, and the same easing family as
  everywhere else in the project.
- Sheets and drawers move on transform, never on height or top. Anything else drops frames on a
  mid-range Android.
- No scroll-linked animation on a phone unless it is the point of the page. It fights the platform's
  own scroll physics and it drains the battery.
- `prefers-reduced-motion` is respected on mobile too, and it is set more often than people assume.

## What to actually test

Three widths cover most of it: 390 for a common phone, 430 for a large one, 768 for a tablet in
portrait. Then the two conditions nobody tests:

```bash
node scripts/shot.mjs index.html --sizes 390,430,768
node scripts/shot.mjs index.html --sizes 390 --squint
```

- With the keyboard open on the longest form.
- With text scaled up by the reader, at 200 percent.

## Checklist

- [ ] Primary action reachable by a thumb without changing grip
- [ ] Every target at least 44 pixels, with clear space between neighbours
- [ ] `100dvh` instead of `100vh`, safe areas honoured top and bottom
- [ ] Zoom enabled, input font size at 16 pixels or more
- [ ] Correct `type`, `inputmode` and `autocomplete` on every field, paste never blocked
- [ ] Tables reshaped or scrolled inside their own container
- [ ] Hero image sized for a phone, dimensions reserved, nothing shifts on load
- [ ] Gestures have a visible alternative, back is a visible control
- [ ] Motion short, transform-based, reduced-motion respected
- [ ] Checked at 390 pixels with the keyboard open and at 200 percent text size
