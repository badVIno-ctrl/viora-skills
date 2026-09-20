# Changelog

All notable changes to Viora Aegis. Item ids refer to the upgrade plan.

## 2.1.0

Tests first, then three new answers: what a hostile skill looks like beyond
prompt injection, what is already installed on this machine, and whether a fix
actually fixes anything.

### Added

- **A1** `tests/run-all.sh` — 86 assertions, bash + `python3`, offline — and six
  fixtures under `evals/fixtures/`, each with its own negative half:
  `f01-sqli-true`, `f02-sqli-param`, `f03-secret-in-test`, `f04-ci-prt`,
  `f05-malicious-skill`, `f06-fail-open`. `tests/README.md`.
- **A2** Twelve skill-audit rules in seven new categories: `SA-TRIG-001/002`
  (trigger hijacking), `SA-REF-001` (anti-refusal), `SA-MEM-001/002` (writes to
  host memory and instruction files), `SA-MCP-001/002/003` (tool poisoning,
  built-in name shadowing, wildcard roots), `SA-SNOOP-001` (other agents'
  configs and credential stores), `SA-LEAK-001` (prompt extraction),
  `SA-OBF-004` (mixed-script identifiers, NFKC-compared), `SA-FLOW-001` (toxic
  flow, computed across files, one HIGH with three anchors). The auto-run tier
  now covers `.claude/settings.json` hooks, `.cursor/mcp.json`,
  `.codex/config.toml`, `.gemini/settings.json`, `.mcp.json`, `hooks/**` and
  npm `postinstall`/`preinstall`/`prepare`.
- **A3** `risk_score` (0–100) beside `MACHINE PRE-VERDICT` in text, markdown and
  JSON. Severity weights × tier multiplier, floor of 70 on any
  `SA-PI`/`SA-FLOW`/`SA-MEM` hit. Printed with: *Score is a lead; the tier table
  is the verdict.*
- **A4** `skill-audit --installed` (skills and MCP configs for Claude Code,
  Codex, Cursor, Windsurf, Gemini CLI, Copilot, OpenCode and Antigravity, both
  scopes), `--lock` (`.viora/skills.lock.json`) and `--verify`, which reports
  drift as HIGH `SA-SUP-006 post-install drift`.
- **A5** `rules/finding.schema.json`, validated with the standard library.
  `report` exits 2 on the first violation and renders prose only from validated
  JSON. UNDETERMINED carries no severity.
- **A6** Ten secret rules: Azure client secret and storage connection string,
  GCP service-account JSON, Vercel, Supabase `service_role`, Cloudflare,
  Discord, HuggingFace, Docker Hub PAT, `AGE-SECRET-KEY-1`, Firebase server key.
  Each with a matching and a non-matching sample in `f03`.
- **A7** `ATTRIBUTION.md`, `evals/triggers.json` (20 queries, 10 near-misses,
  including Russian), SKILL.md version, CLI list and reference map.
- **A8** Coverage ledger: `coverage init|mark|status`. `report` builds "Not
  assessed" from it; `check --mode audit` exits 1 while units are `planned`.
- **A9** `fixcheck --base <ref> --cmd <argv...>`: runs in a temporary worktree at
  base and in the working tree, requires a `VIORA_REACHED` marker in both, and
  logs to `.viora/fixes.jsonl`. `report` lists FIX items without a green row
  under UNPROVEN.
- **A10** `references/14-sharp-edges.md` and six `DEFAULT-001`…`DEFAULT-006`
  rules for the six footgun classes. Playbook 08 gains an "your own API" pass.
- **A11** SPEC-CHECK: `templates/THREAT_MODEL.md` §5b "Controls vs code"
  (holds / contradicted / absent / undocumented) and a second pass in
  playbook 14.
- **A14** Agent hook `hooks/agent/pre-write-secrets.py` plus
  `hooks/agent/claude-code.json`; `init --agent-hooks` merges it into
  `.claude/settings.json` without touching other hooks. An "Agent hooks" section
  in `adapters/INTEGRATION.md`.

### Changed

- Rules may declare `"multiline": true` to match a two-line shape; `DEFAULT-105`
  (fail-open auth) uses it and now fires on the `try/except` form it always
  described.
- The pack ships its own `.viora/baseline.json`: its rule corpora necessarily
  contain every string it hunts for, and that is accepted debt, recorded rather
  than hidden.

### Not included

- **A12**, **A13** — deferred; no behaviour depends on them.

## 2.0.0

Ten modes, the tier model for SKILL-AUDIT, CI-AUDIT and DEFAULTS engines,
`plan`/`checklist` as the small-model safety net.
