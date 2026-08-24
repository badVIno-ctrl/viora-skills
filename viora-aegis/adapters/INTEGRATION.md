# Installing Viora Aegis in any agent

One pack, every agent. The skill body (`SKILL.md`) never changes — adapters only tell each host
*where to find it*.

## Automatic (recommended)

```bash
# macOS / Linux / WSL / Git Bash
bash install.sh                 # detects the agents present in this project
bash install.sh --all           # write adapters for every supported agent
bash install.sh --global        # install to the user-level directories too
bash install.sh --dry-run       # show what would change
```

```powershell
# Windows PowerShell
pwsh ./install.ps1              # same flags: -All, -Global, -DryRun
```

The installer copies the pack to `.viora/skills/viora-aegis/` in your project (or
`~/.viora/skills/viora-aegis/` with `--global`), then writes a small pointer for each detected agent.
It never overwrites your existing instructions — it appends a clearly delimited block between
`<!-- VIORA-AEGIS:START -->` and `<!-- VIORA-AEGIS:END -->`, and replaces only that block on re-run.

## Manual matrix

| Agent | Where it looks | What to do |
|---|---|---|
| **Claude Code** | `.claude/skills/<name>/SKILL.md`, `~/.claude/skills/` | Copy the whole `viora-aegis/` folder there. Auto-loads by description match. |
| **Claude Desktop / claude.ai** | Skill upload | Upload `viora-aegis.zip` in Settings → Capabilities → Skills. |
| **OpenAI Codex** | `AGENTS.md` (repo root), `~/.codex/AGENTS.md` | Copy the pack to `.viora/skills/viora-aegis/` and add the pointer block below to `AGENTS.md`. |
| **Google Antigravity** | `AGENTS.md`, `.antigravity/rules/` | Same pointer block; optionally copy `adapters/antigravity.md` to `.antigravity/rules/viora-aegis.md`. |
| **Cursor** | `.cursor/rules/*.mdc` | Copy `adapters/cursor.mdc` to `.cursor/rules/viora-aegis.mdc`. |
| **Windsurf** | `.windsurf/rules/*.md` | Copy `adapters/windsurf.md` to `.windsurf/rules/viora-aegis.md`. |
| **Gemini CLI** | `GEMINI.md`, `.gemini/` | Add the pointer block to `GEMINI.md`. |
| **GitHub Copilot** | `.github/copilot-instructions.md` | Add the pointer block. |
| **opencode** | `.opencode/skills/<name>/SKILL.md` | Copy the folder there. |
| **Cline / Roo / Kilo** | `.clinerules/`, `.roo/rules/`, `.kilocode/rules/` | Copy `SKILL.md` in as a rule file. |
| **Aider / Continue / Zed** | `CONVENTIONS.md`, `.continue/rules/`, `.rules` | Add the pointer block. |
| **Notion AI** | Skill page | Create a page, paste `SKILL.md`, mark it as a skill, attach the ZIP. |
| **Anything else** | Root `AGENTS.md` | The universal fallback. Always written by the installer. |

## The pointer block

For any agent that reads a single instructions file, this is all that is needed:

```markdown
<!-- VIORA-AEGIS:START -->
## Security — Viora Aegis

This project uses the **Viora Aegis** security skill.

**Read `.viora/skills/viora-aegis/SKILL.md` and follow it whenever you:**
- write or modify code that touches untrusted input, authentication, authorization, sessions,
  payments, uploads, personal data, or external requests;
- are asked to check, audit, harden or "make secure" anything;
- prepare a commit, pull request, release or deploy;
- triage a vulnerability report or scanner finding;
- review dependencies, Dockerfiles, CI workflows or infrastructure;
- build LLM/agent features with tools, RAG or memory.

Quick commands:
- `python3 .viora/skills/viora-aegis/scripts/viora.py scan --path . --diff origin/main` — review a change
- `python3 .viora/skills/viora-aegis/scripts/viora.py scan --path .` — full audit
- `python3 .viora/skills/viora-aegis/scripts/viora.py deps --path .` — supply chain
- `python3 .viora/skills/viora-aegis/scripts/viora.py doctor --path .` — environment

Never report a scanner hit as a finding without tracing attacker-controlled input to a reachable
sink (`SKILL.md` §5). Never weaken a security control to make a build or test pass.
<!-- VIORA-AEGIS:END -->
```

## Verifying the install

```bash
python3 .viora/skills/viora-aegis/scripts/viora.py doctor --path .
```

Then ask your agent: **"Run a Viora Aegis review of this project."** A correctly installed pack makes
the agent state the mode it picked (GUARD / REVIEW / AUDIT / …) before it starts.

## Notes

- **Python 3.8+** is the only requirement, and only for the CLI. Without it the skill still works in
  degraded mode: the rules in `rules/*.json` are plain regexes an agent can run with its own Grep
  tool, and the methodology is unchanged.
- **Team install:** commit `.viora/skills/viora-aegis/` and the pointer blocks so every teammate and
  every agent gets the same behaviour. Add `.viora/` working files (`findings.json`, `baseline.json`)
  to `.gitignore` — `viora init` does this for you.
- **Updating:** replace the folder and re-run the installer. Pointer blocks are regenerated in place.
- **Uninstall:** `bash install.sh --uninstall` removes the pointer blocks and the copied pack.
