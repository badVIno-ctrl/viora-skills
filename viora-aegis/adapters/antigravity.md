# Antigravity adapter

Antigravity reads the repository `AGENTS.md` and rule files under `.antigravity/rules/`.

## Install

```bash
mkdir -p .viora/skills .antigravity/rules
cp -R viora-aegis .viora/skills/viora-aegis
cp .viora/skills/viora-aegis/adapters/antigravity.md .antigravity/rules/viora-aegis.md
bash .viora/skills/viora-aegis/install.sh --agent antigravity   # also writes the AGENTS.md block
```

---

# Viora Aegis — security rules

Full skill and reference library: `.viora/skills/viora-aegis/SKILL.md`.
Read it before any security review, audit, hardening, triage or agent-security task.

## When this applies

Untrusted input · auth and sessions · authorization and multi-tenancy · payments · file uploads ·
personal data · outbound requests · dependencies · Dockerfiles · CI workflows · infrastructure ·
LLM/agent features (tools, RAG, memory, MCP) · any request to check, audit, harden or secure · any
commit, PR, release or deploy preparation.

## Working agreement

1. Announce the mode: GUARD / REVIEW / AUDIT / HARDEN / FIX / TRIAGE / DESIGN / AGENT-SEC.
2. Measure before you judge — run the CLI, read the auth layer, then report.
3. A pattern match is a lead. Trace input → sink → impact, then give a verdict:
   CONFIRMED / LIKELY / DEFENCE-IN-DEPTH / FALSE POSITIVE / UNDETERMINED.
4. Fix the class, not the line. Use the framework's control, never a hand-rolled filter.
5. Never weaken a control to make something pass. Never disable TLS verification, widen CORS,
   or delete a check to get green.
6. Ask before changing authentication, authorization, CORS, crypto or payment flows.
7. Say what you did **not** check. Absent measurement is never a clean verdict.

## Commands

```bash
python3 .viora/skills/viora-aegis/scripts/viora.py doctor  --path .
python3 .viora/skills/viora-aegis/scripts/viora.py scan    --path . --diff origin/main
python3 .viora/skills/viora-aegis/scripts/viora.py scan    --path . --fail-on high
python3 .viora/skills/viora-aegis/scripts/viora.py deps    --path .
python3 .viora/skills/viora-aegis/scripts/viora.py headers https://your-site
python3 .viora/skills/viora-aegis/scripts/viora.py report  --in .viora --out SECURITY_REPORT.md
```

Exit codes: `0` clean · `1` findings at or above the gate · `2` execution error.
