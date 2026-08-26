# 11 - Static analysis: dataflow engines, and writing rules that survive

`viora.py scan` is a **line-oriented** detector. It is fast, dependency-free and
runs anywhere, and that design has a hard ceiling: it sees one line at a time, so
it cannot tell you whether attacker-controlled data actually *reaches* a
dangerous sink.

That is what a dataflow engine does. This reference explains when to reach for
one, how to read its output honestly, and how to write rules that do not get
disabled six weeks later.

---

## 1. What each tool class can and cannot do

| Class | Sees | Cannot see |
|---|---|---|
| Regex / line scanner (`viora.py scan`) | Dangerous shapes, secrets, bad defaults | Whether data flows there; anything spanning lines |
| Taint-mode SAST (Semgrep, CodeQL) | source to sink paths within a language, often across functions and files | Runtime configuration, reflection, dynamic dispatch, anything crossing a process boundary |
| Type systems and linters | Structural misuse | Intent |
| Manual review | Absences, logic, authorisation, chains | Everything at scale |

**None of them find a missing check.** No engine reports "this route has no
authorisation", because there is nothing there to match. Absences are found by
reading, which is why `plan audit` has a dedicated absence-hunting step.

---

## 2. Escalate to a dataflow engine when

- You have a candidate injection and cannot manually prove the path from the
  entry point to the sink, so the honest verdict would otherwise be
  `UNDETERMINED`.
- The codebase is large enough that variant analysis by grep produces mostly
  noise.
- You need to demonstrate reachability to someone who will otherwise dismiss the
  finding.
- You are hardening CI and want a gate stronger than pattern matching.

Useful commands, if the tool is installed:

```bash
# Semgrep - registry rules, then your own
semgrep --config=p/security-audit --sarif --output=semgrep.sarif
semgrep --config=./semgrep-rules/ --error

# Semgrep - only what this PR changed (the CI-friendly form)
semgrep ci --baseline-commit "$(git merge-base origin/main HEAD)"

# CodeQL - build a database, then query it
codeql database create db --language=javascript
codeql database analyze db --format=sarif-latest --output=codeql.sarif
```

**ELSE, if none of them are installed:** say so. Work with `viora.py scan` plus
manual tracing, and record "no dataflow analysis was available" under *Not
assessed*. An absent measurement is never a clean verdict.

---

## 3. Reading SARIF without deceiving yourself

SARIF is the common output format, so one reader handles every tool. `viora.py
scan --format sarif` emits the same shape, which means a single CI step can
upload results from every engine you run.

```bash
python3 -c 'import json,sys; d=json.load(open(sys.argv[1]));
[print(r.get("level","?"),
       r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
       r["locations"][0]["physicalLocation"].get("region",{}).get("startLine","?"),
       r["message"]["text"][:90])
 for run in d.get("runs",[]) for r in run.get("results",[])]' semgrep.sarif
```

Three rules for reading it:

1. **A SARIF result is still a lead.** Tool confidence is not your verdict. Run
   the three-question gate (`plan triage`) on every one you intend to report.
2. **Read the trace, not the headline.** A taint path is a claim with steps, and
   the step where a sanitiser was ignored is where most false positives live.
3. **Never paste the tool's total as the project's risk.** Group by root cause
   first. Twenty hits from one unsafe helper is *one* finding with twenty call
   sites; reporting it as twenty destroys your credibility on the one that
   matters.

---

## 4. Writing your own rule - test first

A rule with no negative test becomes a noise generator; a noisy rule gets
disabled; a disabled rule protects nothing. So the fixtures come **first**, and
the pattern is written until both pass.

The convention is a comment marker on the line above:

```python
# ruleid: py-subprocess-shell-true
subprocess.run(f"ls {user_input}", shell=True)

# ok: py-subprocess-shell-true
subprocess.run(["ls", user_input])
```

`ruleid:` **must** match. `ok:` **must not**. The negative fixture is the more
valuable of the two: it encodes the safe pattern, so the rule tells the next
developer what to do instead of only what not to do.

### Prefer taint mode over pattern matching

A pattern that flags every `subprocess.run(..., shell=True)` flags the safe
constant-string case too. A taint rule flags it only when a source reaches it:

```yaml
rules:
  - id: py-shell-injection-from-request
    mode: taint
    pattern-sources:
      - pattern: flask.request.$ANY
      - pattern: os.environ[...]
    pattern-sanitizers:
      - pattern: shlex.quote(...)
      - pattern: int(...)
    pattern-sinks:
      - pattern: subprocess.$F(..., shell=True, ...)
      - pattern: os.system(...)
    message: Request data reaches a shell. Pass an argument list instead.
    severity: ERROR
    languages: [python]
```

Declaring the **sanitiser** is what makes the rule survive. Without it, every
correctly-escaped call is a false positive, and someone will delete the rule.

### Adding a rule to this pack

`rules/patterns.json` uses one Python regex per rule, with these fields: `id`,
`title`, `category`, `severity`, `confidence`, `cwe`, optional `owasp`,
`pattern`, optional `exclude_line`, optional `include` globs, `note`, `fix`.
Copy the nearest existing rule in the same category and edit it - that guarantees
the field names and the escaping style are right.

Checklist before you commit it:

- [ ] Positive fixture matches
- [ ] Negative fixture does not match
- [ ] Run it against the whole repo: how many new hits, and are they real?
- [ ] `confidence` is honest. A low-confidence rule must carry a `note` telling
      the reader what to check by hand
- [ ] `exclude_line` covers the common safe form
- [ ] The `fix` names the safe construct, not just "sanitise input"
- [ ] `python3 -m json.tool rules/patterns.json` still passes

---

## 5. Diff-aware scanning

On any repository with history, scan the **diff**, not the tree. A gate that
fails on pre-existing debt gets `continue-on-error` added to it within a week,
and then it is decoration that still costs CI minutes.

```bash
python3 scripts/viora.py scan --diff origin/main --fail-on high
semgrep ci --baseline-commit "$(git merge-base origin/main HEAD)"
```

Full-tree scans still have a place: run one deliberately, freeze the result with
`viora.py baseline`, and burn it down on a schedule. See
`playbooks/13-harden.md`.

---

## 6. Honest reporting of coverage

State which engines ran, on what, and what they cannot see:

```
Analysis performed
  viora.py scan (line patterns)      - whole tree, patterns + secrets + defaults
  semgrep p/security-audit (taint)   - src/ only, 3 findings
  codeql                             - NOT RUN (not installed)

What none of these can find
  - missing authorisation checks (an absence has no signature)
  - business logic and IDOR
  - fail-open error paths
  - anything crossing a process or service boundary
```

That block is the difference between a report a reader can rely on and one that
quietly implies more than it checked.

---

## Attribution

The test-first rule-authoring discipline in section 4 - fixtures before pattern,
`ruleid:` and `ok:` markers, taint mode with declared sanitisers, and diff-aware
scanning in CI - follows the practice published by
[Semgrep](https://github.com/semgrep/skills) and their open rule registry.

The escalation criteria and the SARIF-reading discipline draw on the
static-analysis and variant-analysis methodology published by
[Trail of Bits](https://github.com/trailofbits/skills), which is licensed
CC-BY-SA-4.0. **Their text is not reproduced here**: the methodology has been
restated in our own words so that this pack can remain MIT-licensed. Read the
originals - they are excellent.
