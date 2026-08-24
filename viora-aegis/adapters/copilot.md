# GitHub Copilot adapter

Copilot reads `.github/copilot-instructions.md` (repository-wide) and `.github/instructions/*.instructions.md`
(path-scoped).

## Install

```bash
mkdir -p .viora/skills .github
cp -R viora-aegis .viora/skills/viora-aegis
bash .viora/skills/viora-aegis/install.sh --agent copilot
```

## Block for .github/copilot-instructions.md

```markdown
<!-- VIORA-AEGIS:START -->
## Security — Viora Aegis

Full skill: `.viora/skills/viora-aegis/SKILL.md`. Read it for any security review, audit, hardening,
triage, dependency/CI review, or LLM/agent security task.

When generating or reviewing code, enforce:
- Validate all external input at the boundary with an allowlist schema; reject unknown fields.
- Parameterised queries and argv arrays only — never string-built SQL, shell commands or `eval`.
- Every endpoint checks object ownership, not just login; return 404 for cross-tenant access.
- Fail closed: an exception or missing config in a security decision means deny.
- No secrets in code, and no fallback default that lets the app boot without one.
- Argon2id / bcrypt(≥12) for passwords; CSPRNG for tokens; constant-time comparison for secrets.
- Set rate limits, body-size caps, timeouts and pagination bounds on every new endpoint.
- Never disable TLS verification, widen CORS, or remove a check to make a build or test pass.

In review comments, cite the rule and give the fix as a diff plus a verification step.
A pattern match is a lead, not a finding — trace input to a reachable sink first.
<!-- VIORA-AEGIS:END -->
```

## Path-scoped variant

`.github/instructions/security.instructions.md`:

```markdown
---
applyTo: "**/{auth,session,payment,upload,api}/**"
---
Follow `.viora/skills/viora-aegis/SKILL.md`. These paths are security-critical: object-level
authorization, fail-closed error handling, no secrets, bound inputs, audit logging.
```

## CI gate

```bash
python3 .viora/skills/viora-aegis/scripts/viora.py init --ci github
```

Writes `.github/workflows/viora-security.yml`, which fails the build on High and Critical findings
and uploads SARIF to the Security tab.
