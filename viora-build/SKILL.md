---
name: viora-build
description: >
  Viora Build by Viora Studio - pipeline orchestrator that takes a whole product from brief to
  release by running the other Viora skills in order: direction and design tokens
  (viora-design-skills), engineering with hard limits and evidence gates (viora-code-protocol),
  and defensive security (viora-aegis), then one combined verification gate. Use when the request
  covers a whole project: "build me a landing page / site / dashboard / app from scratch",
  "redesign this product end to end", "take this project to release", "собери сайт под ключ".
  Do NOT use for a single feature, a single bug fix, one visual tweak or a standalone audit -
  those go directly to viora-code-protocol, viora-design-skills or viora-aegis.
version: 1.0.0
license: MIT
metadata:
  brand: Viora
  pack: viora-build
  role: orchestrator
  owns-rules: false
  delegates-to: [viora-design-skills, viora-code-protocol, viora-aegis]
  entrypoint: scripts/pipeline_check.sh
---

# Viora Build

*Viora Studio pipeline orchestrator. Runs Viora Design Skills, Viora Code Protocol and Viora Aegis
as one build.*

**The law:** one phase at a time, one artifact per phase, no phase closes without its exit evidence.

This skill holds **no design, engineering or security rules of its own**. It decides *which* skill
runs *when*, what each phase hands to the next, and what proof closes a phase. Every real rule stays
in the child pack that owns it.

---

## 0. Contract

1. **Own nothing.** Never restate, summarise or "improve" a rule from a child skill. A rule that
   needs changing is changed in the child pack, not here.
2. **Delegate literally.** At a phase that names a skill, open that skill's `SKILL.md` and follow it
   as written - its own routers, gates, markers and report format included.
3. **State lives in files.** `.viora/BUILD.md` holds the plan and the phase log; `DESIGN.md`,
   `SECURITY_REPORT.md` and gate output hold the results. A new session resumes from the files,
   never from memory. This is what makes long builds survive a context reset.
4. **No phase skipping.** Exit criteria are artifacts and fresh command output. "Looks done" is not
   an exit criterion.
5. **Degrade loudly.** If a pack is missing, name it, apply the fallback in section 8, and record
   the gap in the final report.

Announce each phase on one line, nothing else: `P3 build: 2/6 - pricing`.

---

## 1. Scope router (10 seconds)

| Situation | Use |
|---|---|
| New site, app or product from scratch | this skill, `P0` to `P7` |
| Existing project: full redesign, or "take it to release" | this skill, start at `P1` (at `P2` if `DESIGN.md` is current) |
| One feature, one bug, one refactor | `viora-code-protocol` directly - no pipeline |
| One visual tweak, one component | `viora-design-skills` directly |
| Audit, triage or hardening only | `viora-aegis` directly |

When torn between this skill and a child skill, pick the child. A pipeline on a small task is waste.

---

## 2. Phase map

| Phase | Goal | Delegate to | Exit evidence | Marker |
|---|---|---|---|---|
| `P0` | Frame the job | - | `.viora/BUILD.md` with brief, surfaces, stack, acceptance | `P0 frame: <n> surfaces, <stack>` |
| `P1` | Direction and tokens | design `G0`-`G3` | `DESIGN.md` + token file, `contrast.mjs` clean | `P1 direction: <world>` |
| `P2` | Skeleton | protocol `FEATURE`/`FULL` | build passes, one mount root, file plan recorded | `P2 skeleton: <n> files` |
| `P3` | Surfaces, one at a time | protocol per surface + design `G4` | repo gates green each iteration, no new duplicates | `P3 build: <k>/<n> <name>` |
| `P4` | Detail and craft | design `G5`-`G6` | `check.mjs` 0 errors, screenshot round done, deletions named | `P4 detail: <e> errors, <d> deletions` |
| `P5` | Security | aegis `DESIGN` → `AUDIT` → `HARDEN` → `FIX` | `SECURITY_REPORT.md`, no open critical/high | `P5 security: <c> critical, <h> high` |
| `P6` | Combined gate | all three toolchains | one evidence table, every row `PASS` or `UNPROVEN: reason` | `P6 gate: <pass>/<total>` |
| `P7` | Handover | - | final report + user to-dos | `P7 done` |

---

## 3. Phases in detail

### P0 Frame

Write `.viora/BUILD.md` from `templates/BUILD.template.md`. It must answer: what is being built, for
whom, the **list of surfaces** (pages, screens, flows), the stack, the constraints that must not
change, and one acceptance line per surface ("done when X does Y").

If a required fact is missing (audience, stack, real content, brand pins), ask **one batched
question** and stop. Guessing the brief is the most expensive mistake in the pipeline.

**Exit:** the file exists and every surface has an acceptance line.

### P1 Direction

Run `viora-design-skills` gates `G0` to `G3`. The pipeline needs its two outputs: the direction
contract and the token file. Nothing visual is built before both exist.

**Exit:** `DESIGN.md` and the token file are in the repo, `contrast.mjs` passes.

### P2 Skeleton

Run `viora-code-protocol` (`Mode: FEATURE`, lane by model tier) for the shell only: routing, layout
shell, one mount root, shared providers, the token file wired in. No product content yet.

**Exit:** the project builds, `ui_guard.py` shows one mount root, the file plan with owners is in
`.viora/BUILD.md`.

### P3 Surfaces

Loop over the surface list from `P0`. **One surface per iteration**, each a full protocol pass
(`Mode: UI` for visible work) plus design `G4` for the section being built. Close each iteration
with the repo's own gates before starting the next; never batch six surfaces and verify once.

**Exit per iteration:** gates green, `find_duplicates.py` shows no new findings, the surface row in
`.viora/BUILD.md` moves to `built`.

### P4 Detail

Run design `G5` and `G6` across everything built: states, focus rings, empty and error states,
optical alignment, the signature moment, then the mechanical checks and one screenshot round.
Subtraction happens here - deletions are named, not implied.

**Exit:** `check.mjs` 0 errors, contrast clean, screenshot fixes applied in one batch.

### P5 Security

Hand `viora-aegis` the real attack surface produced by `P3`: entry points, forms, uploads, auth,
payments, third-party calls, any LLM or agent feature. Run `DESIGN` first only if `P3` introduced
new trust boundaries, then `AUDIT`, then `HARDEN`, then `FIX` for what the audit found.

**Exit:** `SECURITY_REPORT.md` exists, no open critical or high, findings either fixed or explicitly
accepted with a reason.

### P6 Combined gate

One run of all three toolchains over the whole project, one table (section 7). This is the only
place where a claim of completeness is allowed.

**Exit:** every row is `PASS`, or `UNPROVEN: <gate> - <reason>` with the reason visible in the
report.

### P7 Handover

Final report (section 9) plus the short list of things only the user can do: domains, keys, real
content, hosting, analytics, legal pages.

---

## 4. Always on (not phases)

- **Aegis `GUARD` runs from `P2` onward**, inline and silent. Security is not a step at the end;
  `P5` is the audit, not the first time anyone thinks about it.
- **Protocol limits and the evidence law apply to every line written in any phase**, including token
  files in `P1` and detail edits in `P4`.
- **`DESIGN.md` beats taste; user pins beat `DESIGN.md`; the repository's own rules beat all three
  packs.** Say so in the report when a repository rule overrides a pack.
- **Never run two child skills at once on the same file.** One owner at a time, always.

---

## 5. Handoff contract

A phase is not closed until the next phase's inputs exist by name.

| From → To | What must be handed over |
|---|---|
| `P0` → `P1` | audience, surface list, constraints, pinned brand/font/palette |
| `P1` → `P2` | direction line, token file path, section plan |
| `P2` → `P3` | file plan with one owner per concept, mount root path, routing map |
| `P3` → `P4` | list of surfaces built, known gaps, components that still lack states |
| `P3` → `P5` | entry points, forms, uploads, auth surfaces, external calls, LLM/tool usage |
| `P4` → `P6` | checker output, screenshot round result, named deletions |
| `P5` → `P6` | patch list, remaining accepted findings with reasons |
| `P6` → `P7` | the evidence table |

---

## 6. State file

`.viora/BUILD.md` - copy `templates/BUILD.template.md` at `P0` and keep it current. It carries the
brief, the surface table with per-surface status, the decisions (direction, ladder rungs,
deviations), the phase log with marker lines, and the open list (blocked, unproven, follow-ups).

It does **not** carry rules copied from child packs, design tokens, or code. Those live in their own
files.

---

## 7. Combined gate

```bash
bash scripts/pipeline_check.sh .                      # design + code + security, one table
bash scripts/pipeline_check.sh . --only design,code   # subset
VIORA_SKILLS_DIR=~/.claude/skills bash scripts/pipeline_check.sh .
```

The script only calls the child packs' own scripts and prints their verdicts; it holds no rules and
changes no source. Logs go to `.viora/build/`.

No script? Run the children directly and build the table by hand:

```bash
node   viora-design-skills/scripts/check.mjs .
node   viora-design-skills/scripts/contrast.mjs tokens.css
python3 viora-code-protocol/scripts/find_duplicates.py .
python3 viora-code-protocol/scripts/ui_guard.py . --strict
bash   viora-code-protocol/scripts/verify.sh .
python3 viora-aegis/scripts/viora.py scan --path . --format text
```

---

## 8. Missing packs

| Missing | Effect | Fallback |
|---|---|---|
| `viora-design-skills` | `P1` and `P4` have no owner | ask the user for direction, palette and type pair; keep a token file by hand; mark design checks `UNPROVEN` |
| `viora-code-protocol` | no limits, no gates, no evidence law | run the repository's own lint, types, tests and build; keep the evidence table manually |
| `viora-aegis` | no security pass | run `P5` as a manual sweep over untrusted input, authZ, secrets, encoding, crypto and limits; mark `UNPROVEN` |
| all three | nothing left to orchestrate | say so and work normally |

Never silently substitute your own version of a missing pack's rules.

---

## 9. Final report

```
VERDICT: SHIPPED | PARTIAL | BLOCKED
PHASES        - P0..P7, one marker line each
BUILT         - surface -> files
DESIGN        - direction, token file, signature moment
EVIDENCE      - | gate | command | result |
SECURITY      - fixed / open findings, pointer to SECURITY_REPORT.md
NOT DONE / UNPROVEN - explicit list, no hiding
USER TO-DOS   - domains, keys, real content, hosting, legal
FOLLOW-UPS    - small and concrete
```

`PARTIAL` with an honest list beats `SHIPPED` with a hidden gap.

---

## 10. Banned

- Merging phases "to save time" without recording the merge and its reason.
- Copying child-pack rules into `.viora/BUILD.md` or into your own words.
- Closing a phase without its artifact, or claiming a gate you did not run.
- Treating `P5` as a cosmetic final step - `GUARD` is on from `P2`.
- Starting `P3` without a file plan, or building two surfaces in one iteration.
- Inventing gate command names instead of discovering the repository's own.
