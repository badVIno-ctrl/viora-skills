# Changelog

## 4.1.0

The release that makes the skill checkable. Everything added here exists so a claim can be verified
by running something, not by reading a summary.

**Lane routing without self-assessment.** `scripts/lane.mjs` decides FULL or LITE from the model name,
then from name heuristics, then from a three-question probe whose answers live in this folder.
Unresolved resolves to LITE. The old approach asked the model to rate itself, which never worked:
every model says yes. `reference/17-model-tiers.md` was rewritten around the router, with the
downgrade signals and the orchestration split for mixed setups.

**Palette library.** `assets/palettes.css` carries 13 palettes as paste-in blocks, each measured in
both modes. `scripts/palettes.mjs` sweeps the library against the token contract and prints a verdict
per palette. Wired into `verify.mjs` as its own stage, so a palette cannot rot silently.

**Block library.** `assets/blocks/` holds the patterns nobody should retype: shell, marketing and app
blocks in HTML, the same behaviour in React. Tokens only, no raw hex, lint clean with the token file.

**Rules you can interrogate.** `scripts/rules/check-rules.mjs` and `scripts/rules/wig-rules.mjs`
document all 102 rules with a reason, a fix, a before and an after. `scripts/explain.mjs <rule-id>`
prints them, `--coverage` proves every rule has an entry, and both linters accept `--explain <id>`.

**Evals.** `evals/briefs.md` holds twelve briefs with traps and a mechanical floor per brief.
`evals/rubric.md` scores eight axes out of forty. `scripts/score.mjs` computes the four mechanical
axes and leaves the four judged axes blank.

**Russian typography.** `scripts/ru.mjs` checks guillemets, the long dash, non-breaking spaces before
units and currency, mixed alphabets inside one word, shouting caps and Title Case in Russian
headings. `--fix` applies the mechanical half. The long dash is now exempt from the `em-dash` rule on
Cyrillic lines, because there it is grammar rather than a machine tell.

**Installation and continuous integration.** `scripts/install.mjs` writes the skill and a marked
pointer block into five agent formats and is safe to re-run. `.claude-plugin/plugin.json` and
`gemini-extension.json` make it loadable as a plugin or extension.
`.github/workflows/design-gate.yml` runs the same scripts on push, and both linters gained `--github`
for annotations on the diff.

**Self-consistency.** `scripts/docsync.mjs` checks the skill against itself: every path referenced in
the docs exists, the version agrees everywhere, the gates match, all eight LITE recipes measure
clean, every rule has an explanation, every palette passes, blocks use only defined tokens, the
catalog counts are real.

**Also in this release**

- `reference/19-mobile.md`: reach, tap targets, safe areas, mobile keyboards, load, sunlight.
- `pick.mjs --css` prints a fillable token block and warns when the chosen accent is really a surface.
- `LICENSE` added, MIT, with the note that `ATTRIBUTION.md` travels with the folder.
- `SKILL.md` file map, G4 and G6 updated for the new files and stages.

**Fixed**

- `verify.mjs` mistook the palette library for a token contract, then mistook the real contract for a
  library. Detection now keys on the palette marker instead of counting `:root` blocks.
- `palettes.mjs` dropped its first argument when `--only` was absent.
- `docsync.mjs` read the version as missing because the frontmatter has no `v` prefix.
- Icon stroke weight was mixed across the block library, 1.75 in some files and 1.5 in others. One
  weight now, everywhere.
- `ru.mjs` no longer rewrites quotes inside frontmatter, attributes, or lines that are teaching the
  correct form.

## 4.0.0

The release that merged four external skills into one. Design material was taken from an offline
knowledge base of styles, palettes and font pairs, from an art-direction skill, from a set of web
interface guidelines, and from a web quality and Core Web Vitals skill. What came from where is
recorded in `ATTRIBUTION.md`.

- `LITE.md`: the second lane, eight steps, eight recipes with exact hex values.
- `scripts/wig.mjs`: 36 interface rules with file and line output.
- `scripts/pick.mjs`: BM25 search over the offline catalog, with Russian stemming.
- `data/`: 13 tables and 22 stack guides.
- `data/cyrillic-pairs.csv`: 26 Cyrillic type pairs, because Latin-only pairings are the most common
  way a Russian layout dies.
- `reference/13-exemplars.md` through `reference/18-stacks.md`: worked examples, interface rules,
  performance as a design decision, catalog usage, model tiers, stacks.
- `assets/starter.html` rebuilt around the token contract and the craft floor.

## Earlier

Versions before 4.0.0 predate this file. They were a single instruction document without scripts,
which is exactly the thing this release is designed to replace: advice with nothing to verify it.
