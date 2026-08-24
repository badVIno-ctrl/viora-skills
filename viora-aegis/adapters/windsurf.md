---
trigger: model_decision
description: Viora Aegis — defensive security skill. Use for security review, audits, hardening, secret handling, dependency and CI review, vulnerability triage, and LLM/agent security.
---

# Viora Aegis — security rules

Full skill: `.viora/skills/viora-aegis/SKILL.md`. Read it before any security work.

## The Ten Laws

1. Untrusted until proven — all external input, including LLM output. Allowlist schema at the boundary.
2. Never build a command from a string — bound parameters, argv arrays, no `eval`.
3. Authentication is not authorization — check object ownership server-side, every request.
4. Fail closed — exception or missing config in a security decision means deny.
5. No secret in the repo, and no default that lets the app boot without one.
6. Encode at the sink, in the sink's context.
7. Crypto is a library call — TLS 1.2+, AES-GCM, Argon2id/bcrypt(≥12), CSPRNG.
8. Least privilege — DB users, cloud roles, CI tokens, CORS origins, agent tools.
9. Bound everything — rate limits, body size, timeouts, pagination, token and tool budgets.
10. Log the security story — auth events with correlation IDs, no secrets, no stack traces to users.

## Discipline

- Announce the mode: GUARD / REVIEW / AUDIT / HARDEN / FIX / TRIAGE / DESIGN / AGENT-SEC.
- A pattern match is a lead. Trace input → sink → impact before reporting; give a verdict
  (CONFIRMED / LIKELY / DEFENCE-IN-DEPTH / FALSE POSITIVE / UNDETERMINED).
- Severity = impact × reachability. Never the pattern name.
- Fix the class, not the line. Never weaken a control to make a build pass.
- Ask before touching auth, CORS, crypto or payments. Say what you did not check.

## Commands

```bash
python3 .viora/skills/viora-aegis/scripts/viora.py scan --path . --diff origin/main
python3 .viora/skills/viora-aegis/scripts/viora.py scan --path . --fail-on high
python3 .viora/skills/viora-aegis/scripts/viora.py deps --path .
```
