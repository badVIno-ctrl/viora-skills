# Install VioraCode v2.0

One folder, five files at the root plus `references/`, `templates/`, `scripts/`. No build step,
no dependencies beyond Python 3.8+ and bash for the gate runner.

```
viora-code-protocol/
  SKILL.md        the protocol - the only file that must always be loaded
  QUICKCARD.md    one screen for T0 / weak models
  references/     01-14, loaded on demand
  templates/      contract, report, ledger, review-request, handoff
  scripts/        viora.py, verify.sh, scan_repo.py, find_duplicates.py, ui_guard.py
```

---

## 1. Pick the tier first

This is the setting that makes the protocol work on a weak model. Run it once per repository:

```bash
mkdir -p .viora
python3 scripts/viora.py tier --set T1     # T0 weak model | T1 default | T2 strong model
```

| Model class | Tier |
|---|---|
| Opus-class, GPT-5-class, Sonnet-class thinking | **T2** |
| Mid-tier chat models, Sonnet non-thinking, GPT-4.1-class | **T1** |
| Flash / mini / Lite / Haiku-class, anything you have seen skip steps | **T0** |

Unsure? Leave it at T1 and let the demotion triggers in `references/07-model-tiers.md` drop it
automatically, or run the 60-second calibration probe in the same file.

---

## 2. Per-agent installation

### Claude Code

```bash
mkdir -p .claude/skills
cp -r viora-code-protocol .claude/skills/
```

It is discovered by the front matter in `SKILL.md`. To force it on for every coding task, add to
`CLAUDE.md`:

```md
For any code change, follow .claude/skills/viora-code-protocol/SKILL.md.
Start every reply with the declaration line: VIORA <tier> | MODE <mode> | STEP <n>/<total>.
```

### Codex / Codex CLI

Codex reads `AGENTS.md` from the repository root. Put the protocol in the repo and point at it:

```bash
cp -r viora-code-protocol .agent/
```

```md
<!-- AGENTS.md -->
# Code changes

Follow `.agent/viora-code-protocol/SKILL.md` for every code change in this repository.
Weak/fast models: read `.agent/viora-code-protocol/QUICKCARD.md` instead and set tier T0.

Before editing: python3 .agent/viora-code-protocol/scripts/viora.py start --mode <MODE> --task "<task>"
Every turn:     python3 .agent/viora-code-protocol/scripts/viora.py next
Before claiming done: python3 .agent/viora-code-protocol/scripts/viora.py gate && python3 .agent/viora-code-protocol/scripts/viora.py check
```

### Antigravity

Add the protocol to the repo and reference it from the agent's rules/system field:

```md
Follow viora-code-protocol/SKILL.md. Print the declaration line on every reply.
Run `python3 viora-code-protocol/scripts/viora.py next` before each action and
`... viora.py check` before reporting completion.
```

Antigravity's browser/verification tooling maps directly onto step 8 PROVE - use it as the runtime
check, and still paste the output.

### Windsurf

```bash
cp -r viora-code-protocol .windsurf/
```

```md
<!-- .windsurfrules -->
For every code change follow .windsurf/viora-code-protocol/SKILL.md.
Never claim completion without fresh command output.
Run .windsurf/viora-code-protocol/scripts/verify.sh before saying a task is done.
```

Windsurf's rules file has a character budget. If it is tight, paste the ten-step table from
`SKILL.md` §1 and the three forbidden sentences from `QUICKCARD.md`, and let the agent read the
rest from disk.

### Cursor

```bash
mkdir -p .cursor/rules
cp -r viora-code-protocol .cursor/
```

```md
<!-- .cursor/rules/viora.mdc -->
---
description: VioraCode protocol - required for all code changes
alwaysApply: true
---

Follow .cursor/viora-code-protocol/SKILL.md.
Set the tier in .viora/tier. Weak models: T0 + QUICKCARD.md.
```

### Gemini CLI

Gemini CLI reads `GEMINI.md`. Flash-class models should be pinned to **T0**:

```bash
python3 viora-code-protocol/scripts/viora.py tier --set T0
```

```md
<!-- GEMINI.md -->
Follow viora-code-protocol/QUICKCARD.md for every code change. Tier T0.
One action per turn. Run `python3 viora-code-protocol/scripts/viora.py next` and do exactly what it prints.
Never say "should work", "probably", or "I'm confident".
```

### GitHub Copilot / Cline / Continue / Roo

Use the repository instruction file each one reads
(`.github/copilot-instructions.md`, `.clinerules`, `.continuerules`) with the same three lines:
point at `SKILL.md`, require the declaration line, require `verify.sh` output before any
completion claim.

### Any agent, minimum viable install

If the tool has no rules file, paste this into the system prompt or the first message:

```
Follow this protocol for the whole session:
1 Write a 4-line contract: GOAL / DONE-TEST / PROTECTED / NON-GOALS.
2 Find the existing owner of the behaviour with grep and paste the output. Extend it; do not write a second one.
3 Plan: one file, <= 80 changed lines.
4 Write a check, run it, watch it FAIL, then fix it, then watch it PASS. Paste both.
5 Run the repo's lint/typecheck/test/build and paste the output.
6 Answer: what did I change that nobody asked for? what did I never run?
7 Report: WHAT CHANGED / EVIDENCE table / NOT DONE-UNPROVEN.
Never say "should work", "probably fine", or "I'm confident". One action per turn.
```

---

## 3. Verify the install

```bash
cd <your repo>
python3 viora-code-protocol/scripts/viora.py doctor
python3 viora-code-protocol/scripts/viora.py start --mode FIX --tier T0 --task "install smoke test"
python3 viora-code-protocol/scripts/viora.py next
python3 viora-code-protocol/scripts/scan_repo.py .
bash    viora-code-protocol/scripts/verify.sh . --list
```

**Start with `doctor`.** It answers, in one screen, the only questions that matter before a run:
is python3 usable, are the scripts present, is this a git repository (scope, checkpoint and
rollback all need it), is `.viora/` writable, and **which gates exist here at all**. Every `WARN`
line it prints is a specific way your final report could mislead someone.

Expected from the rest: the conductor prints step 1 CONTRACT with the exact template; `scan_repo`
prints your stack and the commands your repo defines; `verify.sh --list` prints the gates it
detected. If `verify.sh` finds no gates, that is information, not an error: the repo has no
automated proof, so every claim must come from a command you run by hand and paste.

Clean up the smoke test with `rm -rf .viora`.

---

### The package can test itself

```bash
bash viora-code-protocol/tests/run-all.sh
```

85 assertions across three suites, no network and nothing to install beyond `bash`, `git` and
`python3`. Each suite builds a throwaway repo under `/tmp`, drives the real `viora.py`, the real
pre-commit hook and the real grader, and never touches your project.

If that run is green, every refusal described in `SKILL.md` is a refusal the code actually
performs. `tests/README.md` lists what each suite covers - and the eight defects these tests
found before release.

---

## 4. What to add to `.gitignore`

```gitignore
.viora/
```

Except `.viora/tier`, if you want the tier committed for the whole team:

```gitignore
.viora/*
!.viora/tier
```

---

## 5. Make it survive outside the chat

Everything above depends on the agent choosing to cooperate. These two pieces do not, which
makes them the highest-leverage 5 minutes in this install.

### The pre-commit hook

```bash
bash viora-code-protocol/hooks/install-hooks.sh
bash viora-code-protocol/hooks/install-hooks.sh --check      # confirm
bash viora-code-protocol/hooks/install-hooks.sh --uninstall  # remove, restores any backup
```

It backs up an existing hook rather than overwriting it, and respects `core.hooksPath`.

On every commit it **blocks**:

- an open run that fails `viora.py check` - unfinished steps, **stale evidence**, files outside
  the recorded plan, open Critical findings
- staged merge-conflict markers
- focused tests (`.only`, `fdescribe`, `fit`) that would silently skip the rest of the suite
- more than 1000 changed lines (over 300 it warns instead)

and **warns** on debug residue (`print`, `console.log`, `breakpoint()`, `dd()`).

Bypass once, loudly enough to appear in your shell history:

```bash
VIORA_SKIP=1 git commit -m "..."
```

The hook is not smarter than you. It is only more consistent - and unlike the agent, it cannot
forget.

### The CI workflow

```bash
mkdir -p .github/workflows
cp viora-code-protocol/ci/viora.yml .github/workflows/viora.yml
```

Four jobs, installing nothing beyond checkout and python:

| Job | Fails the PR when |
|---|---|
| `gates` | one of the repo's own gates fails. Uploads `evidence.jsonl` as an artifact |
| `size` | over 1000 hand-written changed lines (lockfiles and snapshots excluded), conflict markers, or a focused test |
| `hygiene` | never - advisory only. Posts hotspots, duplicate blocks and UI findings to the run summary |
| `honesty` | an agent-authored PR body has no `VERDICT:`, no `UNPROVEN` section, or no evidence table |

The `honesty` job only applies to PRs labelled `agent`, `ai` or `viora`. Humans are not asked to
paste a machine report; agents are, because their claims are the thing that needs checking.

---

## 6. Measure it on your model

Do not take "works on weak models" on trust - including from this package. Run the harness.

```bash
bash viora-code-protocol/evals/run.sh list
bash viora-code-protocol/evals/run.sh prepare f02    # builds a throwaway git repo + prints the prompt
# ... point the agent under test at that directory, paste the prompt, save what it printed ...
bash viora-code-protocol/evals/run.sh score f02 ~/runs/flash-f02.txt
bash viora-code-protocol/evals/run.sh score-all
```

Six fixtures, each built around one specific way weak models fail: duplicating a helper that
already exists, guessing instead of asking, claiming "tests pass" in a repo with no tests,
refactoring a file it was told not to touch, and adopting the user's wrong diagnosis.

Use the result to **pick the tier instead of guessing it**: 6 PASS means T2 is safe, 4-5 means
T1, 2-3 means pin it to T0. A fatal failure on `f04-no-test-runner` means that model will claim
results it never got - use it with the pre-commit hook, not on its word.

Details, honest limits and how to add your own fixture: `evals/README.md` and `evals/rubric.md`.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| the agent ignores the protocol | it was never loaded | put the pointer in the rules file the tool actually reads, and require the declaration line |
| the agent narrates steps without doing them | too much protocol for the model | drop to T0, use `QUICKCARD.md`, one action per turn |
| "tests pass" with no output | no mechanical gate | require `viora.py gate`; `viora.py report` cannot print PASS without the evidence log |
| steps get skipped mid-task | context loss | run `viora.py next` every turn; hand off with `viora.py handoff` |
| the diff keeps growing | no PLAN, or no scope guard | `viora.py plan --files ... --lines ...`, then `viora.py scope` every round - it reads the real diff from git |
| the agent loops on one bug | no attempt budget | `viora.py strike` on each failure; it forces a stop and a question |
| `verify.sh` exits 2 | bad usage | `bash scripts/verify.sh . --list` to see the detected gates |
| the report claims a PASS that no longer holds | gates ran, then the code changed | that row is now `STALE`; `viora.py check` fails and `report` moves it into UNPROVEN. Rerun `viora.py gate` |
| `scope` says "no PLAN recorded" | step 4 was skipped | `viora.py plan --files a,b --lines 60`. To widen a plan on purpose, rerun it with `--force` |
| `rollback` refuses | HEAD moved since the checkpoint, or there is no checkpoint | `viora.py rollback --list`; if HEAD moved, resolve by hand - the tool will not rewrite commits |
| checkpoints do nothing useful | not a git repository | `viora.py doctor` will say so. Untracked files are never covered by a checkpoint |
| you cannot tell whether the protocol is helping | no measurement | run `evals/run.sh` against your model and compare the score to the rubric bands |
