<!-- VIORA-AEGIS:START -->
# Security — Viora Aegis

This project carries the **Viora Aegis** security skill.

**Read `SKILL.md` in this folder (or `.viora/skills/viora-aegis/SKILL.md` once installed) and follow
it whenever you:**

- write or modify code touching untrusted input, authentication, authorization, sessions, payments,
  file uploads, personal data, or outbound requests;
- are asked to check, audit, harden, or "make secure" anything;
- prepare a commit, pull request, release, or deploy;
- triage a vulnerability report or a scanner finding;
- review dependencies, Dockerfiles, CI workflows, or infrastructure;
- build LLM or agent features with tools, RAG, memory, or MCP.

## Non-negotiables

1. Announce the mode you picked: GUARD / REVIEW / AUDIT / HARDEN / FIX / TRIAGE / DESIGN / AGENT-SEC.
2. Measure before judging — run the CLI and read the auth layer before you report.
3. A pattern match is a lead, not a finding. Trace attacker-controlled input to a reachable sink,
   then give a verdict: CONFIRMED / LIKELY / DEFENCE-IN-DEPTH / FALSE POSITIVE / UNDETERMINED.
4. Severity = impact × reachability. Never the pattern name.
5. Fix the class, not the line, using the framework's own control.
6. Never weaken a control to make a build or test pass — no disabled TLS verification, no widened
   CORS, no deleted check.
7. Ask before changing authentication, authorization, CORS, crypto, or payment behaviour.
8. Say what you did **not** check. Absent measurement is never a clean verdict.
9. Defensive work only, on systems the user owns.
10. Answer in the user's language.

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
No Python or no shell? Use grep-only mode: the regexes in `rules/patterns.json` and
`rules/secrets.json` work with any file-search tool, and the methodology is unchanged.
<!-- VIORA-AEGIS:END -->
