# opencode / Cline / Roo / Kilo / Continue / Aider / Zed adapter

These hosts either read a skills folder or a single rules file. Pick your row.

| Host | Path | Method |
|---|---|---|
| opencode | `.opencode/skills/viora-aegis/SKILL.md` | copy the whole folder |
| Cline | `.clinerules/viora-aegis.md` | copy `SKILL.md` |
| Roo Code | `.roo/rules/viora-aegis.md` | copy `SKILL.md` |
| Kilo Code | `.kilocode/rules/viora-aegis.md` | copy `SKILL.md` |
| Continue | `.continue/rules/viora-aegis.md` | copy `SKILL.md` |
| Aider | `CONVENTIONS.md` | append the pointer block |
| Zed | `.rules` | append the pointer block |
| Anything else | `AGENTS.md` | append the pointer block |

```bash
bash install.sh --all        # writes every one of the above that applies
bash install.sh --agent opencode
```

## Pointer block

```markdown
<!-- VIORA-AEGIS:START -->
## Security — Viora Aegis

Read `.viora/skills/viora-aegis/SKILL.md` and follow it for anything touching untrusted input, auth,
authorization, sessions, payments, uploads, personal data, outbound requests, dependencies,
containers, CI/CD, infrastructure or LLM/agent features — and for every "check / audit / harden /
make it secure" request and every commit, PR, release or deploy.

Trace attacker-controlled input to a reachable sink before reporting anything. Give a verdict and a
fix with a verification step. Never weaken a control to make a build pass.

    python3 .viora/skills/viora-aegis/scripts/viora.py scan --path . --diff origin/main
    python3 .viora/skills/viora-aegis/scripts/viora.py deps --path .
<!-- VIORA-AEGIS:END -->
```

## Copying the whole folder vs. the pointer

Copy the **folder** when the host supports progressive disclosure (skills). The agent then loads
`SKILL.md` first and pulls in `references/*` only when needed — cheaper context, better answers.

Use the **pointer block** when the host only supports one instructions file. Keep the pack at
`.viora/skills/viora-aegis/` so the reference paths in the block resolve.
