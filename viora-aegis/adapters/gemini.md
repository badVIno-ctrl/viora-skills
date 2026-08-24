# Gemini CLI adapter

Gemini CLI reads `GEMINI.md` from the project root (and `~/.gemini/GEMINI.md` globally).

## Install

```bash
mkdir -p .viora/skills
cp -R viora-aegis .viora/skills/viora-aegis
bash .viora/skills/viora-aegis/install.sh --agent gemini
```

## Block for GEMINI.md

```markdown
<!-- VIORA-AEGIS:START -->
## Security — Viora Aegis

Read `.viora/skills/viora-aegis/SKILL.md` and follow it for any task touching untrusted input,
authentication, authorization, sessions, payments, uploads, personal data, outbound requests,
dependencies, containers, CI/CD, infrastructure or LLM/agent features — and for every request to
check, audit, harden or secure something, or to prepare a commit, PR, release or deploy.

Announce the mode you picked, measure before judging, and trace attacker-controlled input to a
reachable sink before reporting anything. Give each finding a verdict and a fix with a verification
step. Never weaken a control to make a build pass. Ask before changing auth, CORS, crypto or payments.

    python3 .viora/skills/viora-aegis/scripts/viora.py doctor --path .
    python3 .viora/skills/viora-aegis/scripts/viora.py scan   --path . --diff origin/main
    python3 .viora/skills/viora-aegis/scripts/viora.py deps   --path .
<!-- VIORA-AEGIS:END -->
```

## Note

Gemini CLI's sandbox may restrict shell execution. If the CLI cannot run, use grep-only mode: the
regexes in `rules/patterns.json` and `rules/secrets.json` are directly usable with the built-in
search tool, and the review methodology in `SKILL.md` is unchanged. State that measurement was
limited in the report.
