# Viora Aegis - one page

For small and fast models: **this page plus one command is enough.** You do not
need to read `SKILL.md`.

---

## Step 1 - get your procedure

```bash
python3 scripts/viora.py plan
```

That prints a numbered router. Take the **first** line that matches your
situation, then run the plan it names:

```bash
python3 scripts/viora.py plan <mode>
```

Every step it prints is a command to run, a file to read, or a sentence to write.
**Follow them in order. Do not skip. Do not reorder.**

---

## Step 2 - pick the mode (short version)

| Situation | Command |
|---|---|
| About to install a skill / plugin / MCP server | `plan skill-audit` |
| GitHub Actions, CI, an AI agent in CI | `plan ci-audit` |
| Someone handed you a finding: "is this real?" | `plan triage` |
| Asked to fix something already found | `plan fix` |
| There is an uncommitted change | `plan review` |
| Dependencies, packages, CVEs | `plan supply-chain` |
| Config, defaults, env vars | `plan defaults` |
| Add CI gates / pre-commit | `plan harden` |
| A design that does not exist yet | `plan design` |
| LLM features in the user's own product | `plan agent-sec` |
| You confirmed a bug, want its siblings | `plan variants` |
| You do not understand the codebase yet | `plan context` |
| Anything else | `plan audit` |

---

## Step 3 - the four rules you must never break

1. **A scanner hit is a lead, not a finding.** Open the file at the reported
   line and read it. If you did not read it, you may not report it.
2. **Never report "clean" for something you did not measure.** Write "not
   assessed" and say why.
3. **Never weaken a security check, or a test, to make something pass.**
4. **Ask before editing** auth, session, CORS, crypto, payment or permission
   logic.

---

## Step 4 - the gate every finding must pass

Write these three answers down, literally, for every finding:

```
Q1 Can an attacker control the input?   -> yes / no / unknown  (+ where it enters)
Q2 Does it reach the dangerous sink?    -> yes / no / unknown  (+ the call path)
Q3 What happens if it does?             -> one sentence of concrete impact
```

- Three `yes` -> **CONFIRMED**
- Any `no` -> **FALSE POSITIVE** (name the question that failed)
- Unresolvable `unknown` -> **UNDETERMINED** (name the fact you needed)

Never write "probably fine".

---

## Step 5 - the output shape

Every finding, exactly this, in this order:

```
[SEVERITY] RULE-ID - short title
Where:   path/file.ext:line  (function or route)
Path:    source -> ... -> sink
Impact:  what an attacker gets, concretely
Verdict: CONFIRMED | LIKELY | DEFENCE-IN-DEPTH | FALSE POSITIVE | UNDETERMINED
Fix:     the change, concretely
Verify:  how to prove it is fixed
```

Order by exploitability, never by file path. End every report with a **"Not
assessed"** section.

---

## The commands

```bash
python3 scripts/viora.py plan            # the procedure (start here)
python3 scripts/viora.py doctor          # what stack am I in
python3 scripts/viora.py scan            # static scan
python3 scripts/viora.py scan --diff HEAD
python3 scripts/viora.py skill-audit DIR # vet a skill before installing it
python3 scripts/viora.py ci-audit        # workflows + agentic CI
python3 scripts/viora.py defaults        # insecure defaults / fail-open
python3 scripts/viora.py deps            # dependencies
python3 scripts/viora.py report          # merge artifacts into markdown
```

**If a command fails:** say so, then continue in degraded mode. Every rule in
`rules/*.json` is a plain regex you can run with Grep. A degraded audit that
says it is degraded is useful. A silent gap is not.

---

## The Ten Laws (compressed)

1. Everything untrusted until proven - including LLM output.
2. Never build a command, query or path from a string.
3. Authentication is not authorisation. Check the owner.
4. Fail closed.
5. No secret in the repo, ever.
6. Encode at the sink.
7. Crypto is a library call.
8. Least privilege.
9. Bound everything.
10. Log the security story, leak nothing.

Say a law's number when you use it.
