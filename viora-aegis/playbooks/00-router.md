# Playbook 00 - Router

The one decision you make before any security work. Everything else is a
procedure.

```bash
python3 scripts/viora.py plan          # prints this router, machine-readable
python3 scripts/viora.py plan <mode>   # prints the numbered steps for one mode
python3 scripts/viora.py checklist <mode>   # same, as checkboxes
```

---

## How to route

Read the questions in order. **Take the first `yes` and stop.** Do not weigh
them against each other. Do not run two modes at once.

| # | Question | Mode | Playbook |
|---|---|---|---|
| 1 | Is something about to be **installed or trusted** - a skill, plugin, MCP server, rules pack, extension? | SKILL-AUDIT | `05-skill-audit.md` |
| 2 | Is the subject **CI/CD**, GitHub Actions, a pipeline, or an **AI agent running in CI**? | CI-AUDIT | `07-agent-ci-audit.md` |
| 3 | Were you handed an **existing finding**, report, CVE, or asked "is this real / exploitable?" | TRIAGE | `04-triage-verify.md` |
| 4 | Were you asked to **fix or remediate** something already identified? | FIX | `03-fix-findings.md` |
| 5 | Is there an **uncommitted or unmerged change** in scope? | REVIEW | `01-review-diff.md` |
| 6 | Is the subject **dependencies**, packages, lockfiles, licences, a package version? | SUPPLY-CHAIN | `06-supply-chain.md` |
| 7 | Is the subject **configuration, defaults, env vars**, or "is this hardened?" | DEFAULTS | `08-insecure-defaults.md` |
| 8 | Is the request for **gates** - CI, pre-commit, security headers? | HARDEN | `13-harden.md` |
| 9 | Is the subject a **design or feature that does not exist yet**? | DESIGN | `14-design-threat-model.md` |
| 10 | Is the subject **LLM features, prompts, tools or agents inside the user's own product**? | AGENT-SEC | `references/04-ai-agent-security.md` |
| 11 | Did you **just confirm a bug** and want its siblings? | VARIANTS | `09-variant-analysis.md` |
| 12 | Is the codebase **unfamiliar** - you cannot yet say what it does? | CONTEXT | `10-context-building.md` |
| 13 | Anything else. | AUDIT | `02-audit-repo.md` |

**Ambiguous?** REVIEW if a diff exists, otherwise AUDIT. Both are safe defaults:
they are the broadest modes and they will surface whatever the right answer was.

---

## Distinctions people get wrong

**SKILL-AUDIT vs AUDIT.** SKILL-AUDIT is for code you are about to *trust*, and
it is **static only** - you never run the target. AUDIT is for code the user
already owns and runs. If you would be the one installing it: SKILL-AUDIT.

**CI-AUDIT vs AGENT-SEC.** CI-AUDIT is about *your* pipeline being hijacked -
agents in CI, privileged triggers, secrets. AGENT-SEC is about the LLM feature
the user *ships to their customers*.

**TRIAGE vs REVIEW.** TRIAGE starts from a claim someone else made and tries to
refute it. REVIEW starts from a diff and looks for what is new.

**CONTEXT before AUDIT.** If you cannot name the entry points, the auth layer and
the data stores, run CONTEXT first. An audit of a system you do not understand
produces confident nonsense. CONTEXT is cheap; a wrong audit is not.

**VARIANTS is never first.** It requires a confirmed bug as its input.

---

## After the mode is chosen

Every mode obeys the same five obligations:

1. **Recon before judgement** - `viora.py doctor`.
2. **Read every hit you report.** A scanner locates; you judge.
3. **Pass the three-question gate** (`references/07-triage-and-severity.md`).
4. **Use the fixed finding shape** (`SKILL.md` section 6).
5. **End with "Not assessed"** - an absent measurement is never a clean verdict.

---

## If you get stuck

| Symptom | Do this |
|---|---|
| Python missing / script errors | Say you are in degraded mode. Run the regexes in `rules/*.json` with Grep. Continue. |
| Scanner returns 0 findings | That is a result, not a failure. Verify the scan reached the code (`doctor`), then read the auth layer by hand. |
| Hundreds of findings | Filter to `--severity high`. Fix the top class first. Say how many you left untriaged. |
| Cannot tell if it is exploitable | UNDETERMINED, and name the exact fact you would need. Never guess. |
| The target's own rules matched | Rule definitions are not behaviour. `skill-audit` caps these at low automatically. |
| Budget nearly exhausted | Stop, report what you have, and list the rest under "Not assessed". |
