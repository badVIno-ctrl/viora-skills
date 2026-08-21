# viora-skills
<h1 align="center">Viora Skills</h1>

<p align="center">
Three opinionated agent skills — <b>design</b>, <b>code</b>, <b>security</b> —
plus one router that tells your agent which one to use.
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#the-router">Router</a> ·
  <a href="#the-skills">Skills</a> ·
  <a href="#compatibility">Compatibility</a> ·
  <a href="#use-alongside">Use alongside</a>
</p>

---

## Why this exists

Coding agents are not short on intelligence. They are short on standards.
Left alone they produce the same three outcomes: a purple-gradient UI nobody
asked for, code that passes because the test was written to pass, and a
"ready to deploy" claim with no one having looked at auth.

Viora Skills encodes the standards instead of the intelligence. Three narrow
skills, one router, no magic.

**Design principle:** one skill per kind of work. A single mega-skill that
covers design, code and security has to describe itself vaguely, so the agent
picks it at the wrong moment and then loads all of it at once. Narrow
descriptions trigger accurately; thin skill bodies keep the context free for
the actual task.

## The skills

| Skill | Use it when | Ships with |
|---|---|---|
| **`viora-design`** | any UI is created, restyled or reviewed | direction worksheet, UI checklist, visual QA loop |
| **`viora-code`** | code is written, refactored, debugged or reviewed | plan template, TDD flow, adversarial review checklist |
| **`viora-security`** | auth, input, uploads, payments, secrets, deps, or shipping | diff threat pass, pre-launch hardening checklist |

Each skill is a thin `SKILL.md` (the workflow) plus `references/` (the details,
read only when a phase asks for them).

## Install

### Option 1 — skills CLI (recommended)

```sh
npx skills add viora/viora-skills                        # all three
npx skills add viora/viora-skills --skill viora-design   # just one
```

### Option 2 — manual

```sh
git clone https://github.com/viora/viora-skills
cp -r viora-skills/skills/* ~/.claude/skills/    # Claude Code
cp -r viora-skills/skills/* ~/.agents/skills/    # Codex, Copilot CLI, others
```

Project-scoped instead of global? Use `.claude/skills/` and `.agents/skills/`
inside the repo, and commit them so your whole team gets the same standards.

### Option 3 — the router (do this too)

Copy `AGENTS.md` to the root of your project and fill in the stack and
commands. Without it the skills still work, but you have to ask for them by
name. With it the agent picks the right one on its own.

## The router

`AGENTS.md` is read on every session, so it stays deliberately short: hard
rules plus a dispatch table.

```md
## Skill router — pick by what you are doing right now
| If the current work is... | Load skill |
|---|---|
| any UI: page, screen, component, dashboard, landing, email, slides | viora-design |
| writing, refactoring, debugging code; reviewing a diff; preparing a PR | viora-code |
| auth, input, uploads, payments, secrets, deps, or shipping to prod | viora-security |
| a full feature end to end | in order: design -> code -> security |

- Load one skill at a time and say which one you loaded.
- Switching work type means switching skill, explicitly.
- Finishing a feature always ends with viora-security.
```

## How each skill runs

**`viora-design`** — direction before markup. Reference, personality, type
scale, color, density get written to `DESIGN.md` once and reused everywhere.
Then build with existing tokens and full interaction states. Then the part
agents skip: render it, screenshot 375 / 768 / 1440 in light and dark, compare
against the stated direction, fix the gaps. No screenshot, no "done".

**`viora-code`** — plan, failing test, minimal implementation, root-cause
debugging, then a deliberately hostile self-review (silent catches, weak types,
untested edges, tests asserting implementation), then simplification, then a
report with real command output.

**`viora-security`** — scope the risky surfaces first, so the pass stays
targeted instead of theatrical. Walk the diff against the checklist: server-side
authorization and object ownership, schema validation, parameterized queries,
output escaping, secrets in env only, rate limits, upload allowlists, safe error
output. Then the pre-launch list: HTTPS, security headers and CSP, cookie flags,
dependency audit, staging de-indexed, backups, key rotation. Verdict is a table
with severity, and "not checked" is a valid honest value.

## Compatibility

| Agent | Path | Notes |
|---|---|---|
| Claude Code | `~/.claude/skills/` or `.claude/skills/` | native |
| Codex | `~/.agents/skills/` or `.agents/skills/` | native, plus reads `AGENTS.md` |
| GitHub Copilot | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | open Agent Skills spec |
| Cursor / Cline / Windsurf / Zed | `.claude/skills/` | via skills CLI |

## Repo structure

```
viora-skills/
├── AGENTS.md                  # the router — copy this to your project root
├── DESIGN.template.md         # per-project design direction
├── skills/
│   ├── viora-design/
│   │   ├── SKILL.md
│   │   └── references/  aesthetic.md  ui-checklist.md  visual-qa.md
│   ├── viora-code/
│   │   ├── SKILL.md
│   │   └── references/  tdd.md  debugging.md  review.md
│   └── viora-security/
│       ├── SKILL.md
│       └── references/  diff-checklist.md  prelaunch.md
├── scripts/install.sh
└── LICENSE
```

## Use alongside

Viora Skills is judgement and process. It deliberately does not reimplement
tools. Pair it with the real thing:

- [`anthropics/claude-code` → security-guidance](https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance) — hook that flags unsafe patterns as code is written
- [`semgrep/skills`](https://github.com/semgrep/skills) — SAST scanning on every edit
- [`trailofbits/skills`](https://github.com/trailofbits/skills) — deep audit workflows
- [`vercel-labs/agent-skills`](https://github.com/vercel-labs/agent-skills) — web interface guidelines, React rules
- [`obra/superpowers`](https://github.com/obra/superpowers) — broader engineering workflow library

## Credits

Shaped by ideas from Anthropic's official skills, `obra/superpowers`,
Vercel's web interface guidelines, and the OWASP Top 10 / ASVS. All text here
is original; nothing is copied from those projects.

## Security note

Skills are executable instructions. Read every `SKILL.md` before you install
it — from this repo or any other. Viora Skills bundles no network calls and
no post-install hooks; `scripts/install.sh` only copies files.

## Roadmap

- [ ] `viora-content` — writing and microcopy
- [ ] optional hooks: block a commit when the security pass never ran
- [ ] plugin marketplace manifest for one-command install

## License

MIT © Viora
