# 18. Stacks

Load this when the code has to live inside a real project and you need to know what changes
and what does not. Everything in the other reference files still applies. This file only
translates it into the stack in front of you.

## First, find out where you are

Run this before you write a line. Guessing the stack is how a parallel design system gets
born.

```
ls package.json tailwind.config.* postcss.config.* components.json 2>/dev/null
cat package.json 2>/dev/null | head -40
ls app src pages components 2>/dev/null
```

What the answers mean:

| Evidence | Stack | First move |
|---|---|---|
| no `package.json` | `FILE` | copy `assets/starter.html`, tokens inline |
| `tailwindcss` in deps | Tailwind | tokens as CSS variables, then map them in config |
| `components.json` | shadcn/ui | edit the theme layer, never the primitives |
| `next` in deps | Next.js | `app/globals.css` holds the token layer |
| `vite` + `react` | React SPA | `src/styles/tokens.css`, imported once in the entry |
| `nuxt` / `svelte` / `astro` | see below | same token file, framework-specific entry |
| `react-native` / `expo` | React Native | tokens become a TS object, no CSS |
| `*.xcodeproj`, `build.gradle`, `pubspec.yaml` | native | tokens become platform constants |

If a project already has a token layer, extend it. Read its names, keep its names. A second
system beside the first one is a defect, not a contribution.

## FILE, one self-contained page

The default when nothing points elsewhere.

- Copy `assets/starter.html`. Do not rebuild the shell by hand.
- Tokens live in the `<style>` block at the top. Both themes ship.
- Fonts: `preconnect` to `fonts.gstatic.com`, one `link` with the two families you chose,
  `display=swap`. Two families maximum, four weights maximum.
- No build step, no bundler, no framework CDN. If it needs a script tag for a library,
  ask whether the design needs the library at all.
- Verify with `node scripts/verify.mjs page.html`.

## Tailwind

Tailwind is a delivery mechanism for your tokens, not a design system. The token file stays
the source of truth.

```css
/* tokens.css, imported before Tailwind's utilities */
:root { --accent: #1d4ed8; --canvas: #ffffff; --ink: #16171a; }
```

```js
// tailwind.config.js
theme: { extend: {
  colors: { accent: "var(--accent)", canvas: "var(--canvas)", ink: "var(--ink)" },
  borderRadius: { md: "var(--radius-md)", lg: "var(--radius-lg)" },
  transitionDuration: { base: "var(--dur-base)" },
} }
```

Rules that keep a Tailwind project from turning into slop:

- No arbitrary values for anything the tokens already answer. `p-[13px]` is a defect;
  `p-3` is a decision. `check.mjs` flags `arbitrary-px-class`.
- Dark mode through the `dark:` variant only if the tokens already have dark twins.
  Never hand-pick dark colors per component.
- Long class strings are fine. Ten variants of the same button are not: one component,
  one variant prop.
- `min-w-0` on any flex child that truncates. `wig.mjs` flags it because it is the single
  most common Tailwind layout bug.
- Tailwind v4 puts the theme in CSS with `@theme`. Same rule: variables first, theme second.

## React, Vite, plain SPA

- `src/styles/tokens.css`, imported once in `main.tsx`. Never per component.
- One `Button`, one `Input`, one `Card`, one `Dialog`. If two components need the same
  padding, they share a token, not a copy.
- CSS Modules or one stylesheet per component, both fine. Styled-components adds runtime
  cost for nothing here; do not introduce it to a project that lacks it.
- Interactive state lives in CSS (`:hover`, `:focus-visible`, `[data-state]`), not in
  JavaScript state. A `useState` for hover is a defect.
- Shareable state (tab, filter, page, sort, query) goes in the URL. `wig.mjs` flags it.

## Next.js

- Token layer in `app/globals.css`, imported in the root layout, once.
- Fonts through `next/font`. It self-hosts, adds `display: swap` and kills the layout shift
  that a remote font link causes. Two families maximum.
- Server components by default. `"use client"` only where an interaction actually lives.
  A page that is one big client component throws away the framework.
- Never render `Math.random()` or `new Date()` directly in markup: hydration mismatch, and
  the fix is always to compute it in an effect or on the server. `wig.mjs` flags both.
- Images through `next/image` with explicit `width` and `height`. The hero gets `priority`.
  Nothing gets both `priority` and `loading="lazy"`.
- `metadata` export carries `themeColor`. Browser chrome that fights the page is a visible
  design defect on mobile.

## Vue, Nuxt, Svelte, Astro

Same token file, different entry point.

| Stack | Where the token file is imported | Scoped styles |
|---|---|---|
| Vue 3 | `main.ts` | `<style scoped>`, tokens still global |
| Nuxt | `nuxt.config.ts` `css: []` | same |
| Svelte / SvelteKit | `src/routes/+layout.svelte` | `<style>` is scoped by default |
| Astro | one import in the base layout | `<style>` scoped, `is:global` for tokens |

- Astro: ship zero JavaScript unless an island earns it. This is the best stack in the list
  for a content surface that must feel instant.
- Svelte transitions are cheap and easy to overuse. The motion gate still holds: one or two
  authored moments per surface, `prefers-reduced-motion` in the same commit.

## shadcn/ui

The most common way to get a generic result while feeling productive. The default theme is
recognizable at a glance, and every second AI-built product ships it untouched.

- Change the theme layer: `--background`, `--foreground`, `--primary`, `--radius`, and the
  font stack. Map them to your tokens, do not keep the generated defaults.
- The default `--radius: 0.5rem` and the default border color are the tell. Pick a radius
  family from the direction contract and set it once.
- Do not edit the primitives in `components/ui/*` for visual reasons. Wrap them.
- Delete the components you did not use. An unused `carousel.tsx` is dead weight that also
  invites someone to use it.
- Icons: one library, one stroke weight. Lucide by default, and `check.mjs` flags mixed
  stroke widths.

## React Native and Expo

No CSS, so the token contract becomes a typed object.

```ts
export const t = {
  canvas: "#ffffff", surface: "#f6f6f7", ink: "#16171a", accent: "#1d4ed8",
  radius: { md: 10, lg: 14 }, space: (n: number) => n * 4,
} as const
```

- `Pressable` with an explicit pressed style, never `TouchableOpacity` fading to 0.2.
- Hit targets 44pt minimum. Padding, not margin, does the work.
- Safe areas: `useSafeAreaInsets`, applied to every fixed bar. This is the mobile equivalent
  of the `safe-area-missing` rule.
- One font family loaded through `expo-font`, checked for Cyrillic if the copy is Russian.
- Motion through `react-native-reanimated` on the UI thread. Under 300ms. Respect
  `AccessibilityInfo.isReduceMotionEnabled()`.
- Lists: `FlashList` or `FlatList` with `keyExtractor`. Mapping 500 rows into a `ScrollView`
  is the standard performance failure.

## SwiftUI, Compose, Flutter

- Tokens become a constants file: colors, radii, spacing, durations. Same rule, same names.
- Follow the platform's own affordances. An iOS app that looks like a web page reads as
  cheap. Sheets, navigation bars and system controls are part of the design.
- Dynamic type and dark mode are not optional on either platform.
- Motion uses the platform spring, not a hand-tuned cubic bezier.

## Server-rendered templates

Django, Rails, Laravel, PHP, Go templates.

- Token file in the static folder, one `link` in the base layout.
- Partials are your components. One partial per repeated element, and no copy-pasted markup
  with a changed class name.
- Progressive enhancement: the form must work without JavaScript, then get better with it.
- Server-rendered pages are usually fast until someone adds three analytics scripts.
  `reference/15-perf-craft.md` has the third-party budget.

## Desktop and internal tools

Electron, Tauri, WPF, JavaFX, Avalonia.

- Density goes up, decoration goes down. `APP` mode dials: expression 2, density 4.
- Keyboard first. Every action reachable, shortcuts shown next to their labels.
- Native window chrome unless you have a real reason to redraw it. Custom title bars break
  window management and are noticed immediately.
- Tables carry the product. Tabular numerals, right-aligned numbers, sticky header, one
  hairline weight.

## What never changes

Whatever the stack:

1. One token layer, one accent, one radius family, one type pair, one icon set.
2. Real copy in the language of the request, and a type pair that ships that script.
3. Every interactive element has hover, `focus-visible`, active and disabled.
4. Contrast is measured, not estimated.
5. `prefers-reduced-motion` ships with the motion, not after it.
6. The verification pass runs the scripts and fixes what they find, in one batch.

If the stack makes one of these six hard, the stack is wrong for the surface, or the six are
being negotiated for the wrong reason. They are not negotiable.
