# Claude Code adapter

Claude Code discovers skills automatically from `SKILL.md` frontmatter — no pointer file needed.

## Install

```bash
# project-scoped (recommended: commit it, the whole team gets it)
mkdir -p .claude/skills
cp -R viora-aegis .claude/skills/viora-aegis

# or user-scoped, for every project on this machine
mkdir -p ~/.claude/skills
cp -R viora-aegis ~/.claude/skills/viora-aegis
```

Restart the session and check with `/skills`. Then: *"Run a Viora Aegis review of this change."*

## How it activates

The `description` in the frontmatter is what Claude matches against. It fires on security review,
auditing, hardening, secret handling, dependency and CI review, pre-commit and pre-deploy checks,
vulnerability triage, and LLM/agent security work — plus any explicit "viora" mention.

## Allowed tools

`Read, Grep, Glob, Bash, Edit, Write, WebFetch` — declared in the frontmatter.
If your policy blocks `Bash`, the skill degrades to grep-only mode and says so; findings quality
drops but the methodology is unchanged.

## Recommended companions

```bash
# a pre-commit gate so nothing leaks between reviews
python3 .claude/skills/viora-aegis/scripts/viora.py init --hook --ci github
```

## Plugin / marketplace layout

To ship it inside a plugin, place the folder at `<plugin>/skills/viora-aegis/` and reference the
plugin in `.claude-plugin/marketplace.json`. Nothing inside the pack needs to change.
