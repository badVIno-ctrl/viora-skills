# Attribution

Ideas that shaped this pack, expressed in our own words. **No text was copied from any
source below.** Where a source is licensed share-alike, only the idea travelled; the
wording, structure, code and examples here are original.

| Source | Licence | Idea taken | Where it lives | Text copied |
|---|---|---|---|---|
| Trail of Bits - agent testing and mutation notes | CC BY-SA 4.0 | flip one operator, rerun the test: a suite that still passes is weak | `references/05-tests-and-evidence.md`, `viora.py mutate` (planned) | no text copied |
| NVIDIA - agent engineering guidance | Apache-2.0 | token budget as an engineering constraint; context past ~60 % of the window degrades the model | `references/16-token-discipline.md`, `references/07-model-tiers.md`, `doctor --context` | no text copied |
| snyk - AI code review practice | Apache-2.0 | AI-written code needs more scrutiny, not less; review lenses per defect class | `references/06-review-and-report.md`, `references/14-rationalizations.md` | no text copied |
| impeccable - engineering rules for agents | Apache-2.0 | greppable rule ids; refusals encoded as checks rather than advice | `SKILL.md` §4, §7, `scripts/viora.py` gates | no text copied |
| rohitg00 - agent workflow tooling | Apache-2.0 | proxy-style squeezing of tool output before it reaches the model | `scripts/squeeze.py`, `viora.py gate` | no text copied |
| caveman - terse-register skill | MIT (skill); engine BSL | terse speech as an opt-in register with Auto-Clarity exceptions; no invented abbreviations | `references/16-token-discipline.md`, `viora.py --terse` | no text copied; BSL engine never read or reproduced |
| Anthropic - Claude Code documentation | Anthropic docs terms | Stop and PreCompact hook contract: exit 2 blocks and feeds stderr back | `hooks/agent/claude-code.json`, `viora.py check --hook`, `INSTALL.md` | no text copied |
| Martin Fowler - refactoring catalogue | book, referenced by name | twelve smells used as labelled heuristics ("possible Feature Envy"), never as verdicts | `references/06-review-and-report.md` | no text copied |

If you believe something here reproduces your text rather than your idea, open an issue
and it will be rewritten or removed.
