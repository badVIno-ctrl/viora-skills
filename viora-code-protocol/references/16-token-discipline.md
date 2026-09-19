# 16 - Token discipline

Where an agentic bill actually goes: **reading > writing > talking.** A 40-line patch
costs a few hundred output tokens. The test log, the file dumps and the repeated tool
results that produced it cost tens of thousands of input tokens, every turn, because the
whole transcript is resent. Optimise reading first; speaking last.

## The four levers, with the published figures

| Lever | Effect | Default |
|---|---|---|
| Squeeze tool output before it enters context (proxy-style filtering) | -27...-55 % input tokens | **on** |
| Lazy code: ship the smallest version, question the rest | ~-20 % cost per task | on |
| Terse register in replies | -8.5 % output, but **+7 % in some agentic runs** (more turns) | **opt-in** |
| Cache-friendly ordering: stable prefix, changing content last | varies by provider | on |

Terse is opt-in precisely because it can cost more: a reply too short to carry the next
step buys another turn, and a turn costs more than the sentence saved.

## Squeezing is the default

```bash
<any noisy command> 2>&1 | python3 scripts/squeeze.py
python3 scripts/viora.py gate            # squeezes for you, full log on disk
python3 scripts/viora.py evidence --full # the raw log when you actually need it
```

`squeeze.py` collapses identical lines to one + `×N`, folds vendor stack frames to
`… N frames in node_modules`, keeps the first 15 and last 25 lines plus every line
matching FAIL/ERROR/assert/Traceback/expected/received, and truncates long JSON arrays
and strings. The full text is never destroyed - it is written to `.viora/logs/<ts>-<gate>.log`
and linked from the report. Squeezed for thinking, full for auditing.

## Terse register - rules, when it is on

- No narration of tool calls. Run the thing; report the result.
- One decisive line of an error, not the log. The line that names the failure.
- One status line per finished item: `B13 done — scripts/squeeze.py, viora.py gate`.
- No invented abbreviations. The tokenizer saves nothing on `cfg`, `impl`, `req`, and the
  reader loses the word. Write config, implementation, request.
- Keep `not`, `never`, `only` exact. Negation is the cheapest word and the most expensive
  one to get wrong.
- No pleasantries, no restating the task, no plans in prose.

## Auto-Clarity - where terse is forbidden

Terse mode switches itself off for these. Use plain, full sentences:

- security warnings and anything that widens a trust boundary
- irreversible actions: deletion, migration, force-push, data transformation
- multi-step order the user must follow in sequence
- anything the user will read months later: code comments, commit messages, docs, reports

A terse security warning is a security warning nobody reads.

## Context is a budget too

`python3 scripts/viora.py doctor --context` estimates the always-on bill from
`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/**` and installed skills. Above ~25k tokens,
trim it or demote a tier: a full window fails the same way a weak model does - drift,
then confident nonsense. Context past ~60 % of the window is itself a demotion trigger
(`references/07-model-tiers.md`).
