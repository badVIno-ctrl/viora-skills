# Виора Design Skills

**v4.1.0** A design skill for coding agents. It makes the agent produce interfaces that look designed
rather than generated: a committed visual direction, a measured palette, real states, and a
mechanical floor that is checked by scripts instead of claimed in a summary.

Works with Claude Code, Codex, Cursor, Gemini CLI, Copilot, Windsurf, Cline and anything else that
reads a Markdown instruction file. No dependencies, no network, no API keys. Node 18 or newer for the
scripts, and the skill still works without a terminal.

## What it changes

An agent left alone produces the same page every time: a gradient hero, an eyebrow label above the
heading, three feature cards with thin icons, a band of invented statistics, grey body text, a footer
with nine columns. It looks like software and it looks like nothing.

This skill replaces that default with a process. Route the job, read only what the job needs, commit
to a direction, build on a token contract, then verify with scripts that print file and line numbers.
The verification is the part that matters: a rule the agent can measure is a rule the agent cannot
talk its way around.

## Install

```bash
# 1. into a project, for every agent format at once
node /path/to/viora-design-skills/scripts/install.mjs --into /path/to/project

# see what it would touch first
node /path/to/viora-design-skills/scripts/install.mjs --into /path/to/project --dry-run
```

That copies the skill to `.claude/skills/viora-design-skills` and writes a short pointer block into
`AGENTS.md`, `GEMINI.md`, `.cursor/rules/viora-design.mdc` and `.github/copilot-instructions.md`. The
pointer is wrapped in markers, so running it again replaces the block and leaves your own text alone.

Other ways in:

- **Claude Code plugin.** The folder ships `.claude-plugin/plugin.json`, so it can be added as a
  plugin directly.
- **Gemini CLI extension.** `gemini-extension.json` points at `LITE.md`, which is the lane a Flash
  model should be on anyway.
- **By hand.** Put the folder anywhere and add one line to your agent instructions: read
  `viora-design-skills/SKILL.md` before any design work.

## The two lanes

Strong models get the full process. Light models get a shorter one with fixed values. The lane is
decided by a script, never by asking the model how capable it feels.

```bash
node scripts/lane.mjs --model claude-sonnet-4.5    # FULL
node scripts/lane.mjs --model gemini-2.5-flash     # LITE
node scripts/lane.mjs --probe                      # unknown model: three questions with real answers
node scripts/lane.mjs --list-models                # the table it actually uses
```

FULL is `SKILL.md`: seven gates, fourteen visual worlds, the catalog, the subtraction pass. LITE is
`LITE.md`: eight steps, eight numbered recipes with exact hex values, one motion pattern. LITE removes
decisions, not standards. The token contract, the contrast requirement, visible focus and real copy
are identical on both lanes.

Why a script decides: self-assessment is the first ability to fail. Every model answers yes when asked
if it can hold eight constraints at once. The router uses the model name, then name heuristics, then a
three-question probe whose answers live in these files. Unresolved means LITE, because a strong model
on the short lane still ships good work, while a weak model on the long lane ships three skipped
gates and a confident summary. Details in `reference/17-model-tiers.md`.

## The gates

| Gate | What happens | Marker |
|---|---|---|
| G0 | route the job: new, change, redesign, review or fix, and the mode | `G0 route:` |
| G1 | read only the files this job needs | `G1 read:` |
| G2 | commit to a direction, name the world, fill the contract | `G2 direction:` |
| G3 | tokens and the section plan, no component code yet | `G3 frame:` |
| G4 | build, paste blocks where the pattern is standard | `G4 build:` |
| G5 | one signature detail that no template would produce | `G5 detail:` |
| G6 | verify with the scripts, fix, then delete something | `G6 verify:` |
| G7 | report what was built and what was cut | `G7 done` |

## Scripts

Everything here is plain Node with no dependencies. All of it runs offline.

| Command | What it does |
|---|---|
| `node scripts/verify.mjs <paths>` | the whole pipeline, one verdict |
| `node scripts/check.mjs <paths>` | 66 rules: slop copy, banned patterns, motion, colour, craft |
| `node scripts/wig.mjs <paths>` | 36 interface rules with file and line output |
| `node scripts/contrast.mjs <token file>` | measures 30 required pairs, light and dark |
| `node scripts/palettes.mjs` | measures all 13 palettes in the library |
| `node scripts/shot.mjs <url>` | screenshots at several widths, squint and scale tests |
| `node scripts/pick.mjs "<query>" --system` | offline catalog: palette, type, style, pattern, motion |
| `node scripts/explain.mjs <rule-id>` | why a rule exists, with a before and an after |
| `node scripts/lane.mjs --probe` | decides FULL or LITE |
| `node scripts/ru.mjs <paths>` | Russian typography, with `--fix` for the mechanical half |
| `node scripts/score.mjs <paths>` | scores the four measurable axes of the rubric |
| `node scripts/docsync.mjs` | checks the skill against itself before shipping it |
| `node scripts/install.mjs --into <dir>` | installs into a project |
| `node scripts/selftest.mjs` | proves the scripts still work |

Both linters take `--summary`, `--json`, `--strict`, `--ignore-rule a,b`, `--list-rules`,
`--explain <id>` and `--github` for GitHub Actions annotations.

## The offline catalog

`data/` holds 13 tables and 22 stack guides, roughly 190 palettes, 74 Latin type pairs, 26 Cyrillic
type pairs, 79 styles, 34 landing patterns, 119 interface rules, 105 icon entries and 192 product
routings. `scripts/pick.mjs` searches them with BM25 in about 20 milliseconds, with Russian stemming,
so the agent picks from measured rows instead of choosing colours by mood.

```bash
node scripts/pick.mjs "logistics dashboard for operations managers" --system
node scripts/pick.mjs "клиника" --cyrillic         # only Cyrillic-safe font pairs
node scripts/pick.mjs "fintech" --domain palette --css   # ready token block
```

`--css` prints a fillable `EDIT 1` block for `assets/tokens.css`, checks that the accent is actually
an accent rather than a surface colour, and tells you which command measures the result.

## Palettes and blocks

- `assets/tokens.css` is the token contract. Two edits are allowed: palette and type. The craft floor
  is not editable.
- `assets/palettes.css` holds 13 palettes as paste-in blocks. Every one passes all 30 contrast pairs
  in both modes, and `scripts/palettes.mjs` proves it on demand.
- `assets/blocks/` holds the patterns nobody should retype: header, mobile drawer, footer, hero,
  feature grid, pricing, FAQ, quote, sidebar, toolbar, data table, settings form, destructive dialog,
  toast. Plus the same behaviour in React. Tokens only, no raw hex, and they lint clean.

A pasted block is a floor, not a design. The direction still has to show up in it.

## Evals

`evals/briefs.md` holds twelve briefs that test the skill itself, from a logistics landing page to a
Russian dental clinic to an admin table with bulk actions. `evals/rubric.md` scores eight axes out of
forty, four of them mechanical.

```bash
node scripts/score.mjs .        # the four measurable axes
```

The pass bar: 30 or more out of 40, no axis below 3, and the craft floor at 5. Errors are not taste.

## Continuous integration

`.github/workflows/design-gate.yml` runs the same scripts on every push and turns findings into
annotations on the diff. Linters block, palette and typography warnings do not, because a warning is
a decision and a decision needs a person.

## Russian and other scripts

Cyrillic is treated as a first-class case, not an afterthought. There are 26 measured Cyrillic type
pairs, a rule that fails a Latin-only display face over Russian copy, and `scripts/ru.mjs` for the
rest: guillemets, the long dash, non-breaking spaces before units and currency, mixed alphabets
inside one word, Title Case in Russian headings.

One deliberate conflict: `check.mjs` treats the long dash as the loudest machine tell in English copy
and bans it. In Russian the same character is grammar, so Cyrillic lines are exempt and `ru.mjs`
requires it. Both rules say so in their own messages.

## What it refuses to do

- No gradient meshes, glowing borders or purple-to-blue washes.
- No invented statistics, no placeholder names, no adjectives standing in for facts.
- No removed focus rings, no blocked paste, no icon-only buttons without names.
- No em dash in English copy.
- No claim that a check passed when no script was run.

## Layout of the folder

```
SKILL.md              the FULL lane: gates, worlds, routing, file map
LITE.md               the LITE lane: eight steps, eight recipes with exact values
reference/            19 files, opened one at a time, never all at once
assets/               token contract, starter file, palettes, paste-in blocks, snippets
data/                 13 catalog tables plus 22 stack guides
scripts/              linters, measurements, router, catalog search, installer
evals/                twelve briefs and the scoring rubric
```

## Attribution and license

MIT, see `LICENSE`. The catalog data and several ideas come from other open projects, and
`ATTRIBUTION.md` records exactly what came from where, including which parts are not MIT and must not
be presented as such. If you redistribute this folder, keep that file with it.

What is original here: the gate process, the direction contract, the token contract, the lane router,
both linters and their rule catalogues, the palette library and its measurement pass, the block
library, the Cyrillic pairs, the Russian typography linter, the eval suite and the scoring rubric.
