# Skill audit - {{SKILL_NAME}}

**Verdict:** {{VERDICT}}
<!-- EXACTLY ONE of: safe | safe-with-caveats | needs-caution | do-not-install -->

**Date:** {{DATE}}
**Target:** <!-- repo URL or local path, plus the commit SHA if you cloned it -->
**Declared version / licence:** <!-- from the frontmatter, not from the README -->
**Method:** Static review only. **Nothing in the target was executed.**

---

## Verdict in one paragraph

<!-- Two or three sentences a non-engineer can act on: install it, install it with
     these limits, or do not install it - and the single reason why. -->

---

## What this skill claims to do

<!-- One paragraph, from SKILL.md. Then, separately, what the CODE actually does.
     The gap between the two is the most valuable paragraph in this report. -->

**Claimed:**

**Observed in code:**

**Gap:** <!-- none, or describe it -->

---

## Execution surface

| Tier | File | Trigger | Read in full? |
|---|---|---|---|
| auto-run | | | yes / no |
| on-invocation | | | yes / no |
| on-demand | | | |
| static-text | | | |

**Rule:** every `auto-run` and `on-invocation` file must be 100% read. If any row
says *no*, the verdict cannot be `safe`.

---

## The seven behaviours

For each: quote evidence at `file:line`, or write **none found**. "None found"
means you looked and did not find it - not that you skipped it.

| # | Behaviour | Found? | Evidence (`file:line`) | Judgement |
|---|---|---|---|---|
| 1 | Network egress | | | |
| 2 | Process execution | | | |
| 3 | Credential access (`~/.ssh`, cloud creds, keychain, `.env`, env enumeration) | | | |
| 4 | Dynamic execution (`eval`, `pickle`, decode-then-run) | | | |
| 5 | Filesystem reach and persistence | | | |
| 6 | Obfuscation (base64/hex blobs, hidden Unicode, minified payloads) | | | |
| 7 | Prompt injection in the instruction text | | | |

---

## Network destinations

| Host | Reached from | Declared by the skill? | What is sent |
|---|---|---|---|
| | | yes / **no** | |

**Any host the skill does not document is a question that must be answered before
installing.**

---

## The exfiltration question

> **Does any local data end up in an outbound request?**

This is the single most important question in a skill audit. Answer it
concretely, or say that no outbound call exists at all.

- **Data read:** <!-- variable, and the file:line where it is populated -->
- **Data sent:** <!-- the call, and the file:line -->
- **Path:** <!-- read -> assignment -> ... -> send -->
- **Conclusion:** <!-- no path exists | path exists and is documented (telemetry, opt-in) | PATH EXISTS AND IS UNDECLARED -> critical, do-not-install -->

---

## Permissions vs purpose

| Requested | Needed for the stated purpose? | Verdict |
|---|---|---|
| <!-- e.g. Bash --> | | proportionate / **over-privileged** |
| <!-- e.g. WebFetch --> | | |

A wildcard grant is a finding on its own (Law 8). A formatter that asks for
`Bash` and `WebFetch` is over-privileged regardless of intent.

---

## The skill's own supply chain

- [ ] Dependencies pinned
- [ ] No install / postinstall script, or its contents were read
- [ ] GitHub Actions pinned to a commit SHA
- [ ] No remote script fetched at runtime
- [ ] No submodule
- [ ] Upstream is maintained (last commit, open issues, single maintainer?)

---

## Findings

<!-- Order by exploitability, never by file path. Drop this section entirely if
     there are none - do not pad it. -->

### {{N}}. [{{SEVERITY}}] {{RULE-ID}} - {{title}}

- **Where:** `path/file.ext:line`
- **Tier:** <!-- auto-run / on-invocation / on-demand / static-text -->
- **Evidence:**
  ```
  <the exact line>
  ```
- **Impact:** <!-- what the author of this skill gets, concretely -->
- **Verdict:** <!-- CONFIRMED | LIKELY | DEFENCE-IN-DEPTH | FALSE POSITIVE | UNDETERMINED -->
- **If you install anyway:** <!-- the specific mitigation, or "no mitigation available" -->

---

## Rejected leads

List what the scanner flagged and you dismissed, **with the reason**. This is not
optional: it is what makes the report auditable, and it stops the next reviewer
repeating your work.

| Rule | Where | Why it is not a finding |
|---|---|---|
| | | |

### If the target is itself a security scanner

A scanner, linter or rules pack necessarily *contains* every dangerous string it
hunts for. Those are **detector definitions, not behaviour**, and the engine caps
them at `low` with a note rather than hiding them.

The distinguishing question: **is the dangerous string an argument to a MATCHER,
or to an ACTION?**

- `re: /\.ssh\b|id_rsa/` in a rules table -> a definition. Not a finding.
- `fs.readFileSync('~/.ssh/id_rsa')` -> an action. Critical.

State here how many capped hits you confirmed as definitions.

---

## Not reviewed

<!-- Every file, directory or path you did not read, and why. A binary you could
     not inspect belongs here AND in findings. An absent measurement is never a
     clean verdict. -->

---

## Conditions of installation

<!-- Only if the verdict is safe-with-caveats or needs-caution. Be specific and
     enforceable: which tools to deny, which network to block, which config to
     set, what to re-check on the next version bump. -->

1.
2.

---

*Static audit produced with Viora Aegis (`skill-audit`). The engine locates; the
reviewer judges. Every finding above was read at its reported line.*
