# Attribution

Viora Design Skills is MIT licensed. It absorbs material from four public skills. This
file records what came from where, under which license, and what was changed. If you fork
this skill, keep this file.

## ui-ux-pro-max-skill

- Source: `github.com/nextlevelbuilder/ui-ux-pro-max-skill`
- License: MIT, Copyright (c) 2024 Next Level Builder
- What was taken: the offline data tables.

| Here | There |
|---|---|
| `data/palettes.csv` | `data/colors.csv`, 192 token sets by product type |
| `data/type-pairs.csv` | `data/typography.csv`, 74 pairings |
| `data/styles.csv` | `data/styles.csv`, 79 named styles |
| `data/products.csv` | `data/products.csv`, 192 product types |
| `data/landing.csv` | `data/landing-patterns.csv`, 34 patterns |
| `data/ux-rules.csv` | `data/ux-rules.csv`, 119 rules |
| `data/app-interface.csv` | `data/app-ux-rules.csv` |
| `data/motion.csv` | `data/gsap.csv` |
| `data/icons.csv` | `data/icons.csv` |
| `data/charts.csv` | `data/charts.csv` |
| `data/react-performance.csv` | `data/react.csv` |
| `data/ui-reasoning.csv` | `data/ui-reasoning.csv` |
| `data/stacks/*.csv` | `data/stacks/*.csv`, 22 stacks |

Changes made:

- Files renamed to match this skill's vocabulary. Contents are unmodified.
- The Python search stack (`core.py`, `search.py`, `design_system.py`, `reasoning_contract.py`)
  was not copied. `scripts/pick.mjs` is an original Node implementation of the same idea:
  BM25 over the same CSVs, zero dependencies, no Python requirement, plus Russian query
  stemming and a `--system` bundle that returns a whole starting kit in one call.
- Oversized tables were excluded on purpose: `google-fonts.csv` (747 KB),
  `google-font-licenses.json` (433 KB), `phosphor-icons-upstream.json` (824 KB),
  `demo.gif` (11 MB). They do not survive a context budget and add nothing that the
  kept tables do not already answer.
- `data/cyrillic-pairs.csv` is original to this skill. The upstream typography table is
  Latin first, which is the single most expensive gap for Russian interface copy.

## web-quality-skills

- Source: `github.com/addyosmani/web-quality-skills`
- License: MIT, Copyright (c) 2026 Addy Osmani
- What was taken: the Core Web Vitals thresholds, the budget table, and the honest
  separation of field data, lab data and static reasoning.
- Where it lives: `reference/15-perf-craft.md`, rewritten around design decisions rather
  than audit tooling. No files were copied verbatim.

## web-interface-guidelines

- Source: `github.com/vercel-labs/web-interface-guidelines` and the `web-design-guidelines`
  skill in `github.com/vercel-labs/agent-skills`
- License: no license file is published at the repository root. Nothing was copied.
- What was taken: the review format (`file:line - problem`, group by file, no preamble) and
  the categories of interface defect worth checking mechanically.
- Where it lives: `reference/14-interface-rules.md` and `scripts/wig.mjs`, both written from
  scratch. Rule ids, messages and implementation are original.
- One deliberate conflict: the upstream guidelines ask for Title Case in headings and
  buttons. This skill enforces sentence case, because Title Case is one of the strongest
  machine tells in Russian and mixed-language interfaces. `check.mjs` keeps flagging it.
  If you want Title Case, suppress `title-case-heading` per file and mean it.

## frontend-design

- Source: the `frontend-design` skill in `github.com/anthropics/claude-code`
- License: see that repository.
- What was taken: three ideas, expressed in this skill's own words. The named slop clusters
  that models fall into when a brief is open. The rule that a token plan is written before
  any component code. The instruction to critique the plan before building from it.
- Where it lives: `reference/01-direction.md`, `reference/09-slop-bans.md`, and the failure
  modes list in `SKILL.md`. No text was copied.

## Everything else

The gate system, the ten laws, the fourteen worlds, the thirteen palettes, `tokens.css`,
`starter.html`, `check.mjs`, `contrast.mjs`, `shot.mjs`, `verify.mjs`, `selftest.mjs`,
`pick.mjs`, `wig.mjs`, `LITE.md`, all `reference/*.md` files and the Cyrillic type pool are
original to Viora Design Skills.
