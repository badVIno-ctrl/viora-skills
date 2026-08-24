# Codex adapter

Codex reads `AGENTS.md` from the repository root (and `~/.codex/AGENTS.md` for all projects).
It does not auto-discover skill folders, so the pack lives in `.viora/skills/viora-aegis/` and
`AGENTS.md` points at it.

## Install

```bash
mkdir -p .viora/skills
cp -R viora-aegis .viora/skills/viora-aegis
bash .viora/skills/viora-aegis/install.sh --agent codex
```

Or paste the block below into `AGENTS.md` yourself.

## Block for AGENTS.md

```markdown
<!-- VIORA-AEGIS:START -->
## Security — Viora Aegis

Read `.viora/skills/viora-aegis/SKILL.md` and follow it whenever the task involves untrusted input,
authentication, authorization, sessions, payments, uploads, personal data, external requests,
dependencies, Dockerfiles, CI workflows, infrastructure, or LLM/agent features — and whenever asked
to check, audit, harden, or secure anything, or to prepare a commit, PR, release or deploy.

Start by stating the mode you picked (GUARD / REVIEW / AUDIT / HARDEN / FIX / TRIAGE / DESIGN / AGENT-SEC).

Run before you report:
    python3 .viora/skills/viora-aegis/scripts/viora.py doctor --path .
    python3 .viora/skills/viora-aegis/scripts/viora.py scan   --path . --diff origin/main
    python3 .viora/skills/viora-aegis/scripts/viora.py deps   --path .

A scanner hit is a lead, not a finding: trace attacker-controlled input to a reachable sink before
reporting it, and give each item a verdict (CONFIRMED / LIKELY / DEFENCE-IN-DEPTH / FALSE POSITIVE /
UNDETERMINED). Never weaken a security control to make a build or test pass. Ask before changing
auth, CORS, crypto or payment behaviour.
<!-- VIORA-AEGIS:END -->
```

## Notes for Codex specifically

- Codex runs in a sandbox that may be offline. `viora.py` is stdlib-only and needs no network;
  `deps --online` is the only command that would, and it degrades gracefully without it.
- When the sandbox forbids `Bash`, the skill still works: `rules/patterns.json` and
  `rules/secrets.json` are plain regexes usable with the built-in file search, and the methodology in
  `SKILL.md` §§3–7 does not depend on the CLI. Say which mode you are in.
- Codex often works on a branch. Prefer `scan --diff` for review-sized context, and keep the full
  `AUDIT` for an explicit request.
- Long transcripts: re-read `SKILL.md` §5 (verification gate) before writing the report, so the
  discipline does not drift.
