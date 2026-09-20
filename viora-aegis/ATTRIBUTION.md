# Attribution

Viora Aegis is MIT-licensed and contains no third-party text. Every idea below
was re-expressed in our own words, as our own rules, prose and code. **No text
copied** from any source listed here.

| Source | Licence | Idea taken | Where it lives in this pack |
|---|---|---|---|
| Trail of Bits — engineering writing on API misuse and "sharp edges" | CC BY-SA 4.0 | Vulnerabilities come from APIs where the dangerous call looks like the safe one; review the signature, not the caller | `references/14-sharp-edges.md`, `DEFAULT-001`…`DEFAULT-006` in `rules/defaults.json` |
| NVIDIA AI Red Team — agent and toxic-flow analysis | Apache-2.0 | Exfiltration is a *composition*: untrusted content in, private data read, outbound send. No single step is a finding | `SA-FLOW-001`, computed in `scripts/viora_skillaudit.py:_scan_toxic_flow` |
| Snyk — secret-detection rule sets | Apache-2.0 | Per-provider credential shapes deserve individual rules with a matching and a non-matching sample each | `SECRET-016`…`SECRET-026`, fixtures in `evals/fixtures/f03-secret-in-test/` |
| impeccable — agent-hook patterns | Apache-2.0 | A PreToolUse hook that blocks a write before it happens beats a scan that finds the secret afterwards | `hooks/agent/pre-write-secrets.py`, `hooks/agent/claude-code.json`, `viora.py init --agent-hooks` |
| rohitg00 — MCP and agent configuration inventory | Apache-2.0 | Enumerate every agent's install and MCP config path, per project and per user scope | `skill-audit --installed`, `INSTALL_PATHS` in `scripts/viora_skillaudit.py` |
| caveman — skill layer (skill MIT; engine BSL, not consulted) | MIT | A coverage ledger makes "not assessed" a first-class state instead of an omission | `viora.py coverage`, the "Not assessed" section of `report` |
| Anthropic — Agent Skills and Claude Code hook documentation | Anthropic docs | The PreToolUse event shape (stdin JSON, exit 2 blocks) and the `.claude/settings.json` hook structure | `hooks/agent/*`, `install_agent_hooks` in `scripts/viora.py` |
| dkleptsov/skill-security-review | Apache-2.0 | A dedicated static pre-install audit for skills, and the behaviour categories it covers | `rules/skill-audit.json`, `references/10-skill-audit.md` |

The BSL-licensed caveman engine was **not** read and no part of it is
reproduced. Only the publicly described idea of a coverage ledger informed our
own implementation.

Everything else — the tier model, the risk score, the verification gate, the
refutation gates, the rule text, the plans and the playbooks — is Viora's own
work under MIT.
