# Lanes and model tiers

This skill runs on two lanes. FULL is the seven-gate process in `SKILL.md`. LITE is the eight-step
recipe in `LITE.md`. The difference is not quality of output, it is how much simultaneous reasoning
the process asks for. A model that cannot hold eight constraints at once produces better work from a
shorter list of five, and produces worse work when it silently drops three of the eight.

Read this file only when the lane is genuinely unclear. Deciding a lane is one command.

## The lane is decided by a script, not by a feeling

```bash
node scripts/lane.mjs --model claude-sonnet-4.5    # FULL
node scripts/lane.mjs --model gemini-2.5-flash     # LITE
node scripts/lane.mjs --probe                      # when the name is unknown
```

Asking a model to rate its own ability does not work. Every model says it can hold the full process,
because saying so is the agreeable answer, and self-assessment is exactly the capability that fails
first. So the router never asks. It uses three inputs, in this order.

1. **The model name.** `lane.mjs` carries a table of known families. Exact and prefix matches win.
2. **Name heuristics.** If the family is unknown, the words in the name still carry information:
   flash, haiku, nano, lite, tiny, distill, instant, mini, small, turbo all mean a smaller sibling.
3. **The probe.** If the name says nothing, the model answers three questions that have exactly one
   correct answer each, all three obtainable from files in this folder.

If none of the three resolve, the answer is LITE. A strong model on the LITE lane still ships a good
page. A weak model on the FULL lane ships a page with three gates skipped and a confident summary
saying otherwise. The asymmetry decides the default.

## What the probe asks and why those questions

```bash
node scripts/lane.mjs --probe
# then answer, in one command:
node scripts/lane.mjs --a1 <word> --a2 <number> --a3 <number>
```

| Question | What it actually tests |
|---|---|
| The third word of the first long line in `reference/09-slop-bans.md` | can it read a file and count precisely |
| The number of lines in `data/palettes.csv` | can it run a command and report the real number |
| The number of `.md` files in `reference/` | can it list a directory without inventing entries |

None of these test intelligence. They test whether the model has working tools and reports what the
tools returned instead of what sounds right. Three correct answers means the FULL lane is safe.
One or two means LITE. The third question also has a machine-readable form, so an orchestrator can
check the answer without a human reading it.

A model that invents a plausible number here will invent a plausible contrast ratio later. That is
the whole point of the probe.

## The tiers

| Tier | Examples | Holds | Breaks on |
|---|---|---|---|
| Strong | Claude Opus and Sonnet, GPT-5, o-series, Gemini Pro, Grok 4, DeepSeek R1 and V3, Qwen3 Coder, Kimi K2, GLM 4.6, MiniMax M2, Mistral Large | all seven gates, the direction contract, the subtraction pass, a long file without losing the token contract | rarely. When it does, it is ambition: too many ideas in one page |
| Narrow | GPT-4o, GPT-5 mini, o4 mini, Claude 3.5 Haiku, Llama 4 Maverick, Llama 3.3 70B, Qwen3 32B, Mistral Medium, Devstral, Codestral | the seven gates on one page or a few components, with the reference files opened one at a time | long multi-file work, holding a design system in mind across ten files |
| Light | any Flash, Claude 3 Haiku, GPT-4o mini, Gemma, Phi, Mistral Small, Ministral, small distills | the eight LITE steps, one recipe, one accent, one motion pattern | free choice. Given options it averages them, and the average is a template |

The FULL lane serves the first two tiers. LITE serves the third. `lane.mjs --list-models` prints the
table it actually uses, which is the version that matters.

## What LITE removes and what it never removes

LITE removes decisions, not standards.

**Removed:** the fourteen worlds become eight numbered recipes with fixed hex values. The direction
contract becomes three lines. The catalog search becomes a lookup table. The subtraction pass becomes
one question. Motion becomes one pattern with one duration.

**Never removed:** the token contract, the contrast requirement, focus visibility, real copy instead
of placeholder text, the linters. A weak model is not allowed to ship a page with removed focus rings
because it is weak. The floor is the floor.

This is why the LITE recipes carry their hex values in the file. A light model asked to pick a palette
from a range of choices produces mud. The same model given seven exact values produces a page that
measures clean.

## Do not mix lanes

One lane per run, recorded on the `G0` line. Mixing produces the two worst outcomes in this skill:

- LITE recipe with FULL ambition: a fixed palette carrying a direction it was never measured for.
- FULL gates with LITE attention: gates announced, not performed. The summary says
  `G6 verify: 0 errors` and no script was ever run.

If you find yourself opening `reference/01-direction.md` while working from a LITE recipe, stop. Pick
the lane again with the script, then start the gate you are on from the beginning.

## Downgrade mid-run

Some runs start FULL and should not stay FULL. These are the signals, and any two of them are enough:

- a path that does not exist was quoted as if it had been read
- a gate marker was printed with no work under it
- the direction contract has fields filled with the word for the field, such as `WORLD: a world`
- a number was reported that no script produced, especially a contrast ratio
- the same three sections keep coming back regardless of the brief
- the token file was edited outside `EDIT 1` and `EDIT 2`

```bash
node scripts/lane.mjs --downgrade "quoted a contrast ratio that no script printed"
```

The command prints the LITE entry point and the reason, so the switch is on the record. Then restart
from the LITE step that matches where you were. Do not carry FULL artifacts across: a half-built
direction contract is worse than a recipe number.

Downgrading is not a failure. Finishing a mediocre page while claiming otherwise is.

## For orchestrators running more than one model

The split that works: a strong model writes the plan, a light model executes it.

- Strong model: run G1 to G3, write `DESIGN.md` with the direction contract and the filled token file.
- Light model: build sections against that file, one section per turn, `check.mjs` after each.
- Strong model: the G6 verify pass and the subtraction pass.

With `DESIGN.md` in place the light model is no longer choosing anything, which is the tier's actual
weakness. `assets/DESIGN.template.md` is the handoff format. `reference/12-design-md.md` explains how
to keep it honest across sessions.

## When there is no terminal

No tools is not a reason to change lanes. It changes what the lane runs:

- the linters become the manual checklist in `reference/10-review.md`
- the catalog becomes the offline digest in `reference/16-catalog.md`
- the contrast requirement becomes the measured pairs already listed in `reference/05-color.md`

Say which substitution you used. A checklist walked by hand is a real check. A checklist skipped and
reported as passed is the failure this whole file exists to prevent.
