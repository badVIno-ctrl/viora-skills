# {{TITLE}}

**Date:** {{DATE}}
**Scope:** <!-- repository / branch / commit range / live URL. State what was OUT of scope too. -->
**Method:** <!-- Viora Aegis scan + manual review of <areas>. Name the tools that ran. -->
**Verdict:** {{VERDICT}}

---

## Summary

| Severity | Count |
|---|---|
| Critical | {{CRITICAL}} |
| High | {{HIGH}} |
| Medium | {{MEDIUM}} |
| Low | {{LOW}} |

<!-- Two or three sentences a non-engineer can act on: what is the real risk right now, what is the
     single most important thing to do today, and can this ship? -->

**Release recommendation:** <!-- BLOCK / SHIP WITH FIXES / SHIP -->

---

## What was checked

- [ ] Injection sinks (SQL, command, template, deserialization)
- [ ] Authentication and session management
- [ ] Authorization / object ownership / multi-tenancy
- [ ] Secrets in code and git history
- [ ] Cryptography and transport
- [ ] Input validation and output encoding
- [ ] File uploads and path handling
- [ ] Outbound requests (SSRF)
- [ ] Dependencies and supply chain
- [ ] Containers, CI/CD, infrastructure
- [ ] Security headers and configuration
- [ ] Logging, monitoring, error handling
- [ ] LLM / agent surfaces (tools, RAG, memory)

## What was NOT checked

<!-- Be explicit. Runtime behaviour, third-party services, business logic in <area>, the mobile
     client, anything requiring credentials you did not have. An unchecked area is not a clean area. -->

---

## Findings

{{FINDINGS}}

<!-- Format for each, highest severity first:

### [CRITICAL] RULE-ID — Short title

**Where:** `path/to/file.ts:142` (`functionName`)
**Path:** attacker-controlled input → transformation → sink
**Impact:** what an attacker gets, concretely
**Verdict:** CONFIRMED / LIKELY / DEFENCE-IN-DEPTH / FALSE POSITIVE / UNDETERMINED
**Refs:** OWASP A0X:2025 · CWE-XXX

**Fix**
```diff
- vulnerable line
+ fixed line
```

**Verify:** the exact command or request that proves the fix works
**Risk of the fix:** what could break, and what to regression-test
-->

---

## Accepted risks

| Finding | Why accepted | Owner | Review by |
|---|---|---|---|
| | | | |

---

## Remediation plan

| # | Action | Severity | Owner | Due |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |

**Today:** <!-- Critical items. Rotate exposed credentials FIRST — rotation before code changes. -->
**This week:** <!-- High items. -->
**This quarter:** <!-- Medium items and structural work: central authz, validation layer, CI gates. -->

---

## Systemic recommendations

<!-- The patterns behind the findings. "Authorization is implemented per-handler" is worth more than
     twelve individual IDOR tickets. Propose the control that makes the class impossible. -->

---

<sub>Sources: {{SOURCES}} · Generated with Viora Aegis · Findings are leads until verified in context.</sub>
