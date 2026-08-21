# 11 - App patterns

Loaded at G4 for `APP` mode work: dashboards, tools, settings, onboarding, mobile shells. Purpose: patterns that are already solved, so you do not reinvent them badly. Close when the screen is built.

`APP` mode inverts the `LAND` priorities. Here familiarity beats novelty, scanability beats expression, and consistency beats variety. Beautiful product UI is not decorated product UI: it is precise, dense, fast, and quiet. The wow comes from how it feels to use, not from what it looks like in a screenshot.

## 1. App shell

```
+---------------------------------------------------------------+
| top bar: workspace switcher | search | notifications | avatar |
+----------+----------------------------------------------------+
| sidebar  | page header: title, breadcrumb, primary action      |
| nav      +----------------------------------------------------+
| groups   | content region                                     |
|          |                                                    |
+----------+----------------------------------------------------+
```

- Sidebar 240-280px, collapsible to 56-64px icon rail, state persisted.
- Nav grouped with small `--ink-muted` group labels. Active item marked by a background plus a left bar or a weight change, never colour alone.
- Top bar 52-60px. Global search reachable at `cmd/ctrl + K`.
- Page header holds the title, the breadcrumb if nesting is real, and exactly one primary action, right-aligned.
- Content region has its own scroll. The sidebar and top bar do not scroll away.
- Mobile: sidebar becomes a drawer, top bar keeps search and avatar, primary action becomes a bottom-right floating action or moves into the header.
- Never two competing navigation systems on one screen.

## 2. Dashboard

The most-abused screen in software. A grid of twelve identical metric cards is not a dashboard, it is a wall.

Rules:

1. **One question per dashboard.** What does the person open this to find out? Answer that above the fold.
2. The most important number is visibly the largest thing on the screen. Not one of six equal tiles.
3. Every metric carries a comparison: versus previous period, versus target, or a trend line. A number with no baseline is not information.
4. Maximum 4-6 primary metrics. More belongs on a second screen or behind a tab.
5. Charts: axes labelled, units stated, the time range visible and changeable, no 3D, no pie chart with more than 3 slices, no dual y-axes.
6. Tinted deltas: green up, red down, plus an arrow glyph, plus the actual percentage. Never colour alone.
7. Loading: skeletons matching the exact card geometry. Never let cards pop in at different times and shift the layout.
8. Empty: a real first-run state explaining what will appear here once there is data.
9. Timestamp the data. `Updated 2 minutes ago` builds more trust than any visual polish.
10. Everything on the dashboard is a link to the detail. A metric you cannot drill into is a decoration.

Hierarchy pattern that works: one hero metric with a chart, a row of 3-4 supporting metrics as hairline-separated blocks (not cards), then one table of recent activity. Three levels, decreasing weight.

## 3. Data table

See `07-components.md` for the component floor. Screen-level rules:

- Filters above the table, active filters as removable chips, result count always visible.
- Column choice is deliberate: 5-7 columns is readable, 12 is a spreadsheet. Offer column visibility settings for the rest.
- Density toggle for tools people live in.
- Sticky header, and sticky first column on horizontal scroll.
- Bulk selection with a persistent action bar showing `n selected`.
- Row click opens the detail; the action column does not trigger the row click.
- Pagination or virtualisation past 100 rows. Never render 5000 DOM rows.
- Server-side sort and filter for anything real, with the state in the URL so it can be shared.
- Distinct states for: loading, empty (no records ever), filtered-empty (no matches), error, and partially loaded.

## 4. Settings

- Group into sections with headings. Never one flat list of 30 switches.
- Each row: label, one-line description, control right-aligned. Consistent row height.
- Autosave with a quiet inline confirmation, or an explicit save bar that appears only when something changed. Pick one and never mix them.
- Destructive actions in their own zone at the bottom, visually separated, with typed confirmation for anything irreversible.
- Show current values, not just controls. A field showing what the value is beats a field waiting to be filled.
- Explain consequences next to the switch, not in a tooltip.

## 5. Onboarding and first run

- Fastest path to the first real outcome. Every step that is not required for that is cut.
- Show progress: `Step 2 of 3`, and let people go back.
- Never a tour of the UI before the user has any data in it. Contextual hints at the moment of need beat a five-slide carousel.
- Prefill everything you can infer. Ask for nothing you can derive.
- Provide sample data or a template so the first screen is never empty.
- Skippable, resumable, and the state persists if they close the tab.
- The first-run screen is a designed screen with real copy, not an empty template.

## 6. Auth

- Single column, centered, 360-420px wide, generous padding.
- Social or SSO options above the divider, email below, in the order people actually use.
- `autocomplete="email"`, `autocomplete="current-password"` / `"new-password"`, and a show/hide password toggle.
- Password requirements shown before typing, validated live, phrased positively.
- Errors are specific but never leak whether an account exists.
- After login, land on something useful, not a blank dashboard.

## 7. Search and command

- `cmd/ctrl + K` opens a palette over the current context.
- Results grouped by type with the group label visible, recents first when the query is empty.
- Keyboard hints displayed inline (`Enter` to open, `cmd + Enter` for new tab).
- Highlight the matched substring in results.
- Empty query state shows recents and suggested actions, not a blank box.
- No results state offers the closest alternatives and a way to create the thing being searched for.

## 8. Mobile and native

- Bottom navigation for 3-5 primary destinations, with labels. Icon-only bottom nav is a guessing game.
- Primary actions in the bottom third of the screen: that is where thumbs are.
- Safe areas: `env(safe-area-inset-bottom)` on fixed bars, `env(safe-area-inset-top)` on headers.
- Sheets over modals. Grabber handle, drag to dismiss, `--ease-drawer`, snap points.
- Swipe actions are additive: every swipe action must also exist as a visible control.
- Pull to refresh where a list is time-sensitive.
- Never a hover-only affordance. Never a 32px tap target.
- Keyboard avoidance: the focused field stays visible when the keyboard opens.
- Loading and offline states are more visible on mobile, not less. Assume flaky networks.

### Native platforms

If the target is genuinely native, defer to the platform:

- **iOS**: system typography and Dynamic Type, standard navigation and tab bars, native sheets, San Francisco unless the brand overrides it, respect Reduce Motion and Increase Contrast, use SF Symbols for system-adjacent icons.
- **Android**: Material 3 components and elevation, dynamic colour where appropriate, edge-to-edge with proper insets, predictive back.
- Do not port a web layout into a native shell and call it native. The details that make native feel native are the platform's own controls.

## 9. Feedback and system status

- Any action over 300ms shows progress at the point of interaction, not globally.
- Optimistic updates with visible rollback on failure.
- Undo for anything destructive and reversible. Undo beats a confirmation dialog.
- Save state always legible: `Saved`, `Saving...`, `Unsaved changes`.
- Offline: state it plainly, queue what can be queued, block what cannot with an explanation.
- Never a silent failure. Never a spinner with no timeout.

## 10. Density and craft in dense UI

What makes a dense tool feel expensive:

- Consistent 4px rhythm at small scale. At 32px row heights, a 2px inconsistency is visible.
- Hairlines, not borders, and always the same hairline.
- Tabular numerals everywhere numbers stack.
- Keyboard shortcuts for the top 5 actions, discoverable in a `?` overlay.
- Instant feedback: no animation on high-frequency interactions.
- Truncation that is always recoverable.
- Every list has a sort, every table has a filter, every long page has an anchor nav.
- No decoration inside working surfaces. No gradients on a data table. No card wrapper on a log row.

## Output of this gate

The screen is built on the correct pattern, states are complete, keyboard works, the layout does not shift on load. Continue to G5.
