# Scoring rubric

Eight axes, five points each, forty possible. Four axes are measured by scripts, four are judged by
looking. Score before fixing anything: a score taken after the fix measures the fix, not the run.

`node scripts/score.mjs <paths>` fills in the measured axes and leaves the judged ones blank.

## The bar

| Total | Verdict |
|---|---|
| 36 to 40 | ships. Better than most human work in this category. |
| 30 to 35 | ships after one pass on the weakest axis. |
| 24 to 29 | recognisably designed, still generic somewhere. Name where. |
| below 24 | template with new colours. Restart from the direction contract. |

Two hard rules on top of the total. Craft floor below 5 fails the run whatever the total says, because
errors are not taste. Any axis at 1 fails the run, because one broken axis is what people notice first.

## Measured axes

### 1. Craft floor

What the linters say. Nothing subjective here.

| Score | State |
|---|---|
| 5 | zero errors, warnings either zero or each suppressed with a written reason |
| 4 | zero errors, up to three warnings left undecided |
| 3 | zero errors, more than three warnings ignored |
| 2 | one error |
| 1 | more than one error, or the linters were never run |

### 2. Colour and contrast

| Score | State |
|---|---|
| 5 | every required pair passes, one accent, hue count at or below three, dark mode from the same tokens |
| 4 | every pair passes, one accent, a fourth hue with a reason |
| 3 | every pair passes, but the accent is doing two jobs |
| 2 | a failing pair, or two accents competing |
| 1 | colours picked outside the token file, contrast never measured |

### 3. Typography

| Score | State |
|---|---|
| 5 | two families at most, a real scale, display tracking set, measure held, script coverage correct |
| 4 | as above with one loose end, such as unset tracking on one display size |
| 3 | scale present but body text is small or the measure runs long |
| 2 | three families, or a display face that does not cover the copy's script |
| 1 | browser defaults with size overrides sprinkled in |

### 4. States and interaction

| Score | State |
|---|---|
| 5 | hover, focus visible, active, disabled, loading, empty, error, all present and all designed |
| 4 | one state missing on a minor control |
| 3 | the happy path is complete, empty and error are afterthoughts |
| 2 | focus removed anywhere, or a control that only works with a mouse |
| 1 | one state per component, the built one |

## Judged axes

### 5. Direction commitment

| Score | State |
|---|---|
| 5 | one world, named, held on every section. A stranger could name the world from a screenshot. |
| 4 | one world held, with one section that drifts |
| 3 | a direction exists but reads as a palette choice rather than a point of view |
| 2 | the default cluster: cream paper, high-contrast serif, terracotta. Or near-black with a neon accent. |
| 1 | no direction. Component defaults in a column. |

### 6. Composition and hierarchy

| Score | State |
|---|---|
| 5 | the silhouette reads at 10 percent zoom, sections differ in shape, one thing is clearly first |
| 4 | strong hierarchy, one section that repeats a shape without reason |
| 3 | readable, but the page is a stack of equal bands |
| 2 | everything centered, every section the same height, cards everywhere |
| 1 | no first thing. The eye starts nowhere. |

### 7. Motion restraint

| Score | State |
|---|---|
| 5 | motion where it explains something, correct easing and duration, reduced-motion in the same commit |
| 4 | one animation that is decorative but harmless |
| 3 | motion is fine but the reduced-motion path was an afterthought |
| 2 | scroll-triggered reveals on every section, or transitions on all properties |
| 1 | animation as the design. Remove it and nothing is left. |

### 8. Copy

| Score | State |
|---|---|
| 5 | specific, in the client's voice, buttons name their action, no filler, no invented numbers |
| 4 | specific with one lazy sentence |
| 3 | correct but generic. Could describe any product in the category. |
| 2 | adjectives instead of facts, or an eyebrow label, or a made-up statistic |
| 1 | placeholder text left in place |

## How to score honestly

- Score the artifact, not the intention. What is on screen is the run.
- One number per axis, no halves. If you cannot choose between two, take the lower one.
- Name the weakest axis in one sentence and say what you would change. That sentence is the value of
  the whole exercise.
- Do not re-score after a fix in the same run. Fix, then run the brief again from the start.
- A score with no failing axis and no note is a score nobody believes.

## Comparing two versions of the skill

Run the same three briefs before and after a change to the skill: brief 10 for anti-slop, brief 9 for
interface rules, brief 4 in the LITE lane. Same model, same lane, same day. Report the two totals and
the axis that moved. A change that moves nothing is documentation, not improvement.
