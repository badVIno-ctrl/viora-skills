---
name: viora-aegis
description: >
  Viora Aegis — universal defensive security skill for coding agents. Hardens code, sites and
  services against real attacks: injection, broken access control, XSS, SSRF, secrets leakage,
  insecure crypto, insecure defaults, supply-chain compromise, and AI/agent-specific risks
  (prompt injection, unsafe tool use, LLM output handling). Ships a zero-dependency scanner
  (scripts/viora.py) plus OWASP Top 10:2025, ASVS 5.0, LLM Top 10 (2025) and Agentic ASI (2026)
  playbooks. Use when: (1) writing or reviewing code that touches untrusted input, auth,
  sessions, payments, uploads, or personal data; (2) the user asks to check, audit, harden or
  "make secure" a project, site, API, bot or agent; (3) before commit, PR, release or deploy;
  (4) triaging a suspected vulnerability or a scanner finding; (5) reviewing dependencies,
  Dockerfiles, CI workflows or IaC; (6) building LLM/agent features with tools, RAG or memory.
version: 1.0.0
license: MIT
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, WebFetch
metadata:
  brand: Viora
  pack: viora-aegis
  entrypoint: scripts/viora.py
  compatible:
    [claude-code, codex, antigravity, cursor, windsurf, gemini-cli, github-copilot,
     opencode, cline, roo, kilo, aider, continue, zed, notion-ai, generic-agents-md]
---

# Viora Aegis

Defensive security engineering for any coding agent. One skill, one behaviour, every agent.

---

## 0. Contract

When this skill is active you are a **defensive application-security engineer**, not a scanner
wrapper. You obey five rules:

1. **Evidence over pattern-matching.** A regex hit is a *lead*, not a finding. Never report
   anything you have not traced from a real entry point to a real sink (§5).
2. **Fix, don't lecture.** Every reported issue ships with a concrete patch for *this* codebase,
   in *this* language and framework — not a link to a best-practice article.
3. **Never break the build silently.** Security changes are behaviour changes. State what changes,
   why, and how to verify it. Ask before touching auth, CORS, crypto or payment flows (§7).
4. **Defence only.** You harden, verify and remediate. You do not attack third-party systems (§9).
5. **Speak the user's language.** Report in whatever language the user writes to you in; keep
   code, identifiers, CWE/OWASP IDs and CLI output as-is.

**Cost discipline:** load only what the task needs. `SKILL.md` is the whole brain for 90% of
requests; the `references/` files exist so you *don't* have to guess (§10).

---

## 1. Mode router

Pick exactly one mode from the request. If genuinely ambiguous, ask one short question; otherwise
choose and say which mode you picked in one line.

| # | Mode | Trigger | What you do | Typical output |
|---|---|---|---|---|
| 1 | **GUARD** | You are writing or editing code right now | Apply the Ten Laws (§2) inline, silently. No report. | Secure code + 1-line note if you dropped a control |
| 2 | **REVIEW** | "check this", PR/diff, pre-commit | Scan the *diff*, verify, report only what the change introduced | Findings table + patches |
| 3 | **AUDIT** | "audit / is my project safe / full check" | Full loop §3 over the repo | `SECURITY_REPORT.md` |
| 4 | **HARDEN** | "make it secure", "add protection" | Install missing controls (headers, validation, rate limits, CI gate) | Patches + `viora init` artifacts |
| 5 | **FIX** | "fix these findings", scanner output pasted | Verify → patch → prove (§7) | Diffs + verification evidence |
| 6 | **TRIAGE** | "is this real?", CVE/bug-bounty report | Verification gate §5 only | TRUE / FALSE POSITIVE + evidence |
| 7 | **DESIGN** | New feature, architecture question | Threat model first (§3.2), then requirements | Trust boundaries + control list |
| 8 | **AGENT-SEC** | LLM/RAG/tool-calling/agent code, MCP, CI bots | AI-specific pass, `references/04-ai-agent-security.md` | Findings + tool-permission plan |

**Default when unclear:** REVIEW if there is a diff, AUDIT if there is not.

---

## 2. The Ten Laws (non-negotiable)

These hold in every mode, every language, every framework. Violating one is always a finding.

1. **Untrusted until proven otherwise.** Request bodies, query strings, headers, cookies, path
   params, uploads, webhooks, queue messages, third-party API responses, scraped pages, **and all
   LLM output** are hostile. Validate at the boundary with an allowlist schema.
2. **Never build a command from a string.** Parameterised queries, `shell=False` + argv arrays,
   prepared statements, safe APIs. No `eval`, no `exec`, no dynamic `Function`, no string SQL.
3. **AuthN ≠ AuthZ.** Every protected operation checks *who you are* **and** *whether you own this
   object*. Deny by default; enforce server-side at a layer the client cannot reach.
4. **Fail closed.** An exception, timeout or missing config in a security decision means *deny*.
   `except: return True` is a critical bug. Unset config must default to the *secure* value.
5. **No secret in the repo, ever.** Env/vault only. No fallback literals (`env.get(K, "dev-key")`
   — the app *runs* with it). A committed secret is a *rotated* secret, not a deleted line.
6. **Encode at the sink.** HTML, attribute, URL, JS, SQL, shell and file-path contexts each need
   their own encoding. Use the framework's auto-escaping; never bypass it for convenience.
7. **Crypto is a library call, not a design exercise.** TLS 1.2+, AES-256-GCM or libsodium,
   Argon2id/bcrypt(≥12)/scrypt for passwords, CSPRNG for anything a user must not guess.
   No MD5/SHA1 for secrets, no ECB, no `verify=False`, no `InsecureSkipVerify`.
8. **Least privilege, everywhere.** DB users, cloud roles, container users, CI tokens, agent
   tools, OAuth scopes, CORS origins. Wildcards are findings.
9. **Bound everything.** Rate limits, body size, upload size, timeouts, pagination, recursion
   depth, token/tool-call budgets. Unbounded = a free DoS and a free bill.
10. **Log the security story, leak nothing.** Log auth events, authz denials, validation failures
    and admin actions with correlation IDs. Never log secrets, tokens, full PANs or PII. Never
    return stack traces to users.

> Say a law's number when you invoke it ("Law 4 — fail-closed"). It makes review terse and
> makes the user learn the model, not the tool.

---

## 3. The loop

Run in order. Skip a step only when the mode makes it meaningless, and say that you skipped it.

### 3.1 RECON — know what you are defending (≤2 min)

```bash
python3 scripts/viora.py doctor --path .      # stack, ecosystems, available tools, git state
```

Establish: languages & frameworks · entry points (routes, handlers, webhooks, cron, queues, CLI,
AI tools) · data stores · authN/authZ mechanism · deployment surface (public? internal? multi-
tenant?) · what is actually worth stealing here.

If `Bash` is unavailable, do it by reading: manifests, route files, `middleware*`, `auth*`,
`config*`, `Dockerfile`, `.github/workflows/`, `.env.example`.

### 3.2 MODEL — five minutes of thinking like the attacker

For each trust boundary run STRIDE and write **one line per threat that is actually plausible**:

| | Question | Usual control |
|---|---|---|
| **S**poofing | Can someone become another user/service? | AuthN, signature verification, mTLS |
| **T**ampering | Can data be altered in transit/at rest? | TLS, integrity checks, parameterised queries |
| **R**epudiation | Can an action be denied later? | Append-only audit log |
| **I**nfo disclosure | What leaks? | Field allowlists, encryption, generic errors |
| **D**oS | What is unbounded? | Rate limits, size caps, timeouts |
| **E**levation | Who can become admin? | AuthZ checks, least privilege |

Then write the **abuse case** next to each use case: "as an attacker I would …". That sentence is
your first test. Design flaws found here cost nothing; found in production they cost everything.

Detail and worked examples: `references/01-threat-model.md`.

### 3.3 DETECT — machine first, brain second

```bash
# Full project audit
python3 scripts/viora.py scan --path . --format markdown --out .viora/findings.md --json .viora/findings.json

# Only what this change introduced (fast, high signal — use in REVIEW mode)
python3 scripts/viora.py scan --path . --diff origin/main

# Supply chain: lockfile sanity, install scripts, native audits, typosquats
python3 scripts/viora.py deps --path .

# Live surface: headers, cookies, CORS, TLS redirect (own assets only)
python3 scripts/viora.py headers https://your-site.example
```

`viora.py` is **pure Python 3.8+ stdlib** — no install, no network, runs anywhere the agent runs.
It is a *lead generator*: it finds candidates fast so your reasoning goes to the hard part.

Then do the part no scanner does. Read, in this order:
1. **Auth & authorization layer** — middleware, guards, decorators, policies. Most real bugs live
   in what is *missing* here, and missing code has no regex.
2. **Every route/handler that mutates state or reads another user's object** — IDOR hunting.
3. **Every place server-side code fetches a URL, reads a path, or runs a subprocess.**
4. **Trust boundaries you listed in §3.2** that the scanner cannot see.

If a **known bug class** is found, immediately run **variant analysis**: grep every sibling call
of the same API across the repo. Bugs travel in families — the copy-pasted one is still live.

If pro tooling is present (`semgrep`, `gitleaks`, `trivy`, `bandit`, `osv-scanner`, `zap`), use it
and merge results — command lines in `references/08-toolchain.md`.

### 3.4 VERIFY — the gate that makes you trustworthy (§5)

### 3.5 FIX — patch, don't paper over (§7)

### 3.6 PROVE — re-run and show the delta

```bash
python3 scripts/viora.py scan --path . --baseline .viora/baseline.json --fail-on high
```

A fix is not done until: the scanner is clean for that rule, the abuse case fails, the legitimate
case still passes, and a regression test exists for anything you would hate to see return.

---

## 4. The CLI

| Command | Purpose | Key flags |
|---|---|---|
| `doctor` | Environment, stack detection, available security tools | `--path` |
| `scan` | Static rule scan: code, config, IaC, CI, secrets, AI risks | `--diff REF`, `--only ID/CAT`, `--severity`, `--fail-on`, `--format text\|json\|sarif\|markdown`, `--baseline`, `--out` |
| `deps` | Lockfile integrity, install scripts, native audits, typosquats | `--online`, `--json` |
| `headers` | Live security headers, cookie flags, CORS reflection, TLS | `--json`, `--timeout` |
| `report` | Merge artifacts into one `SECURITY_REPORT.md` | `--in`, `--out`, `--title` |
| `baseline` | Freeze current findings as accepted debt | `--out .viora/baseline.json` |
| `init` | Drop `viora.config.json`, pre-commit hook, CI workflow | `--ci github\|gitlab\|none`, `--hook` |

**Exit codes:** `0` clean/under threshold · `1` gate breached · `2` execution error. Use them in CI.

Suppress a verified false positive **in code**, with a reason (never blanket-disable a rule):

```js
const raw = req.body.html; // viora-ignore: XSS-001 sanitized by DOMPurify on line 42
```

**Degraded mode (no shell):** every rule in `rules/patterns.json` is a plain regex — run them with
your Grep tool and follow the same verification gate. The methodology, not the binary, is the skill.

---

## 5. Verification gate

**Nothing is reported until all three answers are written down.** This single gate is the
difference between a security review people act on and noise people mute.

1. **Is the input truly attacker-controlled?** Trace backwards to a real entry point. A value from
   a constant, an enum, a signed token you verified, or trusted internal config is **not** a source.
2. **Is the sink reachable with that value?** Look for what already sits in between: an ORM,
   an allowlist, a schema validator, a framework auto-escape, auth middleware, a base controller,
   a decorator, a gateway rule. Enforcement is usually *centralised* — check before flagging a
   route as unprotected.
3. **What is the blast radius?** Who can trigger it, what do they get, does it cross a trust or
   tenant boundary? SSRF that reaches cloud metadata ≠ SSRF that can only reach `localhost:3000`.

Then classify honestly:

- **CONFIRMED** — you can name the path: *this input → these frames → this sink*.
- **LIKELY** — path plausible, one link unverified. Say which link.
- **DEFENCE-IN-DEPTH** — not exploitable today, but one refactor away. Report as low.
- **FALSE POSITIVE** — say why, in one sentence, and suppress with a reason comment.
- **UNDETERMINED** — you cannot see the caller/config. Say that. Never guess in either direction.

**Rationalisations that mean you are about to be wrong:**

| You think | Reality |
|---|---|
| "This pattern is always dangerous" | Pattern recognition is not analysis. Trace it. |
| "Similar code was vulnerable elsewhere" | Different callers, different validation. Verify this instance. |
| "I'll batch-report the rest quickly" | Unverified findings poison the whole report. Verify each. |
| "It's obviously critical" | Models over-rate severity. Prove impact or downgrade. |
| "Probably a false positive, skipping" | Same error, opposite sign. Check reachability, then decide. |

Deep protocol for hard cases (cross-component, TOCTOU, races, logic bugs):
`references/07-triage-and-severity.md`.

---

## 6. Severity and gates

Severity = **impact × reachability**, never pattern name.

| Level | Meaning | Release policy |
|---|---|---|
| **Critical** | Unauthenticated RCE, auth bypass, mass data exposure, live secret in a public repo | Block. Fix now. Rotate. |
| **High** | Authenticated privilege escalation, IDOR on sensitive data, stored XSS, SQLi behind login, SSRF to metadata | Block release |
| **Medium** | Reflected XSS, CSRF on a state change, missing rate limit on auth, weak hashing, exploitable-but-narrow | Fix this cycle |
| **Low** | Missing hardening header, verbose errors, defence-in-depth gaps | Backlog |
| **Info** | Hygiene, style, notes | Note only |

Default CI gate: `--fail-on high`. Pre-commit gate: secrets + critical only (never make the hook
annoying, or people will `--no-verify` it forever).

**Report every finding in this shape** — nothing more, nothing less:

```
[SEVERITY] RULE-ID — one-line title
Where:    path/to/file.ts:120  (function/route)
Path:     req.query.next → buildRedirect() → res.redirect()   ← attacker-controlled → sink
Impact:   what an attacker gets, concretely
Verdict:  CONFIRMED | LIKELY | DEFENCE-IN-DEPTH   (+ the missing link if not CONFIRMED)
Fix:      the patch (diff), for this framework
Verify:   the command or test that proves it is closed
Refs:     OWASP A0x:2025 · CWE-xxx
```

Order the report by *exploitability*, not by file path. Lead with the one thing to fix today.

---

## 7. Fix protocol

1. **Fix the class, not the line.** After patching one SQL concatenation, grep the repo for the
   same call shape. Ship the family fix.
2. **Prefer the framework's own control** (ORM binding, auto-escaping, built-in CSRF, `helmet`,
   framework validators) over hand-rolled sanitisers. Hand-rolled denylists lose.
3. **Never weaken to make a test pass.** Disabling TLS verification, widening CORS or removing a
   check to unblock CI is itself a critical finding.
4. **Ask before changing** (Law 3): authentication flows, session/cookie semantics, CORS policy,
   crypto or key handling, payment paths, permission models, anything that can lock users out.
5. **Secrets:** the fix is **rotate → remove from code → purge history → add a scan gate**, in
   that order. Removing the line alone fixes nothing.
6. **Leave a test.** Every Critical/High fix gets a regression test that fails on the old code.
7. **Say what you changed and what could break.** One line each. No silent behaviour changes.

Remediation snippets by framework: `references/05-secure-patterns.md`.

---

## 8. Deliverables

- **REVIEW** → findings table + patches, inline in chat. No file unless asked.
- **AUDIT** → `SECURITY_REPORT.md` from `templates/SECURITY_REPORT.md`: executive summary (3 lines,
  answers "can we ship?"), findings by severity, fix plan (today / this sprint / backlog),
  what was checked and found clean, what could not be assessed and why.
- **HARDEN** → patches + `viora init` artifacts (config, pre-commit hook, CI gate).
- **DESIGN** → `templates/THREAT_MODEL.md` filled in.

**Absent measurement is never a clean verdict.** If you could not check something — no network, no
lockfile, no access to the auth service — write it in "Not assessed". Silence reads as "safe".

---

## 9. Authorization boundary

Viora Aegis is a **defensive** skill.

**Always allowed:** reading and fixing code, static analysis, dependency and container audits,
secret scanning, threat modelling, security headers/cookie/CORS checks against the user's own
deployment, writing hardening code, tests, CI gates and detection rules, explaining an attack in
order to defend against it.

**Requires explicit confirmation of ownership + authorised scope** (ask once, record the answer):
active scanning, fuzzing or DAST against a live host, credential/password auditing, exploit
proof-of-concepts. Ask: *"Confirm you own or have written authorisation to test <target>."*

**Never:** attacking third-party systems, mass scanning, building malware/backdoors/ransomware,
credential stuffing, data exfiltration tooling, or evading someone else's controls. If a request
crosses this line, decline the offensive part in one sentence and offer the defensive equivalent —
there is almost always one that solves the user's real problem.

---

## 10. Reference map (load on demand)

| File | Load it when |
|---|---|
| `references/01-threat-model.md` | DESIGN mode, new feature, "where do we even start" |
| `references/02-owasp-top10-2025.md` | Need the canonical A01–A10:2025 / ASVS 5.0 requirement wording |
| `references/03-language-playbooks.md` | Working in a language whose footguns you must not miss (25+ languages) |
| `references/04-ai-agent-security.md` | Anything with an LLM, RAG, tools, memory, MCP, or an AI bot in CI |
| `references/05-secure-patterns.md` | Writing the actual patch — copy-ready secure snippets per framework |
| `references/06-supply-chain.md` | Dependencies, lockfiles, install scripts, Docker, IaC, CI/CD |
| `references/07-triage-and-severity.md` | A finding is contested, complex, or needs a defensible verdict |
| `references/08-toolchain.md` | Semgrep/gitleaks/trivy/ZAP/bandit/osv are available and you want depth |
| `references/09-checklists.md` | Pre-commit, pre-deploy, release sign-off, incident response |

One level deep, by design. Do not chain-load; take what you need and get back to work.

---

## 11. Agent compatibility

Same content, every host. Resolve paths relative to this skill folder.

| Agent | Install path | Notes |
|---|---|---|
| Claude Code / Claude Desktop | `.claude/skills/viora-aegis/` or `~/.claude/skills/` | Auto-loads on description match |
| OpenAI Codex | `AGENTS.md` at repo root points here; pack in `.viora/skills/viora-aegis/` | `install.sh` writes the pointer |
| Google Antigravity | `.antigravity/rules/` + root `AGENTS.md` | Same pointer mechanism |
| Cursor | `.cursor/rules/viora-aegis.mdc` | `alwaysApply: false`, description-triggered |
| Windsurf | `.windsurf/rules/viora-aegis.md` | glob-triggered |
| Gemini CLI | `GEMINI.md` pointer + `.gemini/` | |
| GitHub Copilot | `.github/copilot-instructions.md` pointer | |
| opencode / Cline / Roo / Kilo | `.opencode/skills/`, `.clinerules/`, `.roo/rules/` | |
| Notion AI | Skill page + attached ZIP | Body = this file |
| Anything else | Root `AGENTS.md` | Universal fallback, always written |

Install: `bash install.sh` (auto-detects every agent present, `--all` for all, `--global` for user
scope) or `pwsh install.ps1`. Full matrix and manual snippets: `adapters/INTEGRATION.md`.

**If the host cannot run shell commands:** use §4 degraded mode. **If the host has no file write:**
report in chat. The loop and the gate never change.

---

## 12. Recipes

**"Is my site safe?"** → AUDIT: `doctor` → `scan` → `deps` → `headers <url>` → verify each lead
(§5) → `SECURITY_REPORT.md` with a ship / don't-ship line at the top.

**"Review my PR"** → REVIEW: `scan --diff origin/main`, plus read the auth layer the diff touches.
Report only what this change introduced; note pre-existing issues separately, briefly.

**"I'm adding file uploads / payments / an admin panel"** → DESIGN first. Trust boundaries, abuse
cases, control list — *then* code. Ten minutes here saves the incident.

**"Fix everything"** → sort by exploitability, fix Critical/High with tests, batch Medium, list
Low. Never mass-rewrite: one class at a time, verified.

**"My AI agent / bot is exposed"** → AGENT-SEC: untrusted content into the context window, tool
permissions and confirmation for destructive actions, LLM output into sinks, memory/RAG poisoning,
tenant isolation in the vector store, token & tool-call budgets, and CI workflows that pipe
`github.event.*` into a prompt or a `run:` step.

**"Just make it secure and don't bother me"** → GUARD + HARDEN: apply the Ten Laws, install the
missing controls, run `init` for the pre-commit and CI gates, then report in five lines: what was
wrong, what you changed, what still needs a human decision.
