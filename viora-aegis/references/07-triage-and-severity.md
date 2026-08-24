# Triage, evidence and severity

This file exists to stop the two failure modes that destroy trust in a security review:
**crying wolf** (reporting unverified pattern matches) and **missing the real one** (dismissing a
finding because it looked like noise). Both come from the same root cause: deciding before tracing.

---

## 1. The verification protocol

For every candidate finding, write these three answers **before** deciding anything. If you cannot
answer one, that is your verdict: UNDETERMINED, with the missing piece named.

### Q1. Is the input attacker-controlled?

Trace **backwards** from the sink to an entry point. Real sources:

- HTTP request: body, query, path params, headers, cookies, method, content-type, filename
- Webhooks and callbacks (until the signature is verified — verify *then* trust)
- Uploaded file names, contents and metadata (EXIF, ZIP entry paths)
- Message queues, cron payloads, imported CSV/JSON, scraped pages
- Third-party API responses (a compromised or malicious partner)
- Database values that were originally user input (**stored/second-order injection**)
- LLM output, RAG documents, tool results, agent memory
- Environment in a shared-tenant runtime; CLI args in a privileged context

**Not** sources: constants, enum members, values already validated against an allowlist, verified
signed tokens, config you control, internal IDs the user cannot influence.

> A stored value is *still* attacker-controlled. "It comes from the database" is not a defence.

### Q2. Is the sink actually reachable with that value?

Look for what sits in between before you flag anything:

| Mitigation to check for | Where it hides |
|---|---|
| ORM parameter binding | The "raw" call may still be bound — read the API |
| Schema validation | Zod/Pydantic/Joi/DTO at the boundary, decorator, or gateway |
| Allowlist / enum cast | Often a few frames up, in a mapper or service layer |
| Framework auto-escaping | Templating engines escape by default — the bug is only the bypass |
| Auth middleware | Route-level, router-level, base controller, or gateway rule |
| Type coercion | An `int(...)` or `:id(\\d+)` route constraint kills many traversal/SQLi claims |
| WAF / proxy rule | Real, but never count it as *the* control — note it as defence in depth |

**Enforcement is usually centralised.** Before declaring a route unauthenticated, find the app's
actual enforcement point and check whether it covers this route. Reviewers who skip this produce
reports that get ignored.

Also check the negative case: is the "protection" real? A denylist of `../` fails against `..%2f`,
double encoding, and `....//`. A `startsWith(allowedHost)` check fails against
`allowedhost.attacker.com`. Regex anchoring matters.

### Q3. What is the blast radius?

- Who can trigger it: anonymous / any user / same tenant / admin only?
- What do they get: read one record, read all records, write, execute code, move money?
- Does it cross a **trust boundary** (tenant → tenant, user → admin, app → infrastructure)?
- Is it a stepping stone (SSRF → cloud metadata → credentials → everything)?
- How hard is it: single request, or a race window measured in microseconds?

---

## 2. Verdicts

Use exactly these words — they set expectations correctly.

| Verdict | Requirement | How to write it |
|---|---|---|
| **CONFIRMED** | You can name every frame from source to sink | "`req.params.id` → `getOrder()` → `db.raw()` at `orders.js:88`, no ownership check" |
| **LIKELY** | Path plausible, one link unverified | "… assuming `parseFilter()` does not sanitise — I could not read that module" |
| **DEFENCE-IN-DEPTH** | Not exploitable today, fragile tomorrow | "Currently only called with a constant; make it safe so a future caller cannot break it" |
| **FALSE POSITIVE** | You found the mitigation | "Bound parameter, not concatenation — `?` placeholders on line 42" |
| **UNDETERMINED** | Cannot resolve a critical link | "Reachability depends on the gateway config, which is not in this repo" |

Never report a bare regex match. Never silently drop a lead — an unverified lead that you dismissed
without checking reachability is the same error as reporting it, with the opposite sign.

---

## 3. Rationalisations to catch in yourself

| Thought | Why it is wrong | Do instead |
|---|---|---|
| "This pattern is always dangerous" | Context decides, not the token | Trace source → sink |
| "Similar code was vulnerable in another repo" | Different callers and validation | Verify this instance |
| "There are 30 hits, I'll batch them" | Unverified findings poison the whole report | Verify each; group only after |
| "Obviously critical" | Impact inflation is the #1 credibility killer | Prove impact or downgrade |
| "Probably a false positive" | Same laziness, opposite direction | Check for the mitigation, then decide |
| "The WAF handles it" | WAFs are bypassed daily | Fix the code; count the WAF as layer two |
| "Internal only" | Assumes the perimeter holds and insiders are benign | Model the post-compromise case |
| "Users would never do that" | Attackers are not users | Write the abuse case |
| "It's been like this for years" | Age is not evidence of safety | Age means longer exposure |
| "Tests pass" | Tests encode expected behaviour, not abuse | Add the abuse-case test |

---

## 4. Severity calculus

**Severity = impact × reachability.** Compute, don't feel.

| Reachability | Impact: code exec / full data | Impact: privilege escalation | Impact: limited data | Impact: none directly |
|---|---|---|---|---|
| Unauthenticated, remote | **Critical** | **Critical** | High | Low |
| Any authenticated user | **Critical** | **High** | Medium | Low |
| Same-tenant / specific role | High | Medium | Medium | Low |
| Admin-only or local | Medium | Low | Low | Info |
| Requires unusual preconditions | Downgrade one level and say why | | | |

**Escalate one level** when: the data is regulated (payment, health, government ID), the finding is
already public, exploitation leaves no trace, or the fix cannot be deployed quickly.

**Downgrade one level** when: exploitation needs a race window under a millisecond, needs a
privilege the attacker would not have, or the impact is bounded to the attacker's own data.

**Never** downgrade because the fix is hard, because the code is old, or because the team disagrees.
Severity describes the world, not the roadmap.

### Special cases

- **Secret in a public repo:** Critical, always. Assume it was harvested within minutes of the push.
  The clock starts at commit time, not discovery time.
- **Dependency CVE:** severity is *yours*, not the advisory's. Unreachable vulnerable code path →
  Low/Info with an upgrade ticket. Reachable from an entry point → inherit and adjust.
- **Missing hardening (headers, SRI):** Low on its own; Medium when it is the only thing standing
  between a known XSS and full account takeover.
- **Fail-open logic:** rate at the impact of the *bypass*, not the probability of the exception.
  Attackers cause the exception on purpose.

---

## 5. Variant analysis — always do this

A confirmed bug is a **template**, not an incident. Bugs travel in families: the same developer,
the same copy-paste, the same misunderstood API.

1. Extract the shape: which API, which misuse, which missing check.
2. Grep every call of that API across the repo (and sibling repos/services).
3. For each hit run Q1–Q3. Most will be safe; the one that is not is why you did this.
4. Check history: `git log -S "<api>"` shows where the pattern was introduced and copied.
5. Fix the family in one change, then add a lint/Semgrep/`viora` rule so it cannot return.

Report variants together: *"SQL injection in 3 of 11 `db.raw()` call sites; the other 8 are bound."*
That sentence is worth more than eleven separate tickets.

---

## 6. Hard cases

**Race conditions / TOCTOU.** Name the two operations, the shared state and the window. Ask: what
happens if the same request arrives twice in parallel? Common in balance checks, coupon redemption,
quota enforcement, file upload-then-validate, and SSRF host validation (resolve → pin the IP →
connect, never resolve → connect).

**Second-order / stored injection.** The source and the sink are in different requests, often
different files, sometimes different services. Follow the *data*, not the control flow.

**Logic bugs.** No pattern exists. Read the state machine and ask which transitions are reachable
out of order. Payment before authorization, refund after refund, reset token reuse.

**Cross-component flows.** Frontend validates, backend trusts. Service A sanitises for HTML,
service B renders into SQL. Encoding applied twice, or once in the wrong context. Note explicitly
which component owns each control.

**Deleted or moved code.** If a control disappeared in a refactor, `git log -p` on the file finds
it. "It used to check ownership" is a strong finding.

---

## 7. Writing the finding

```
[HIGH] AUTH-IDOR — Any authenticated user can read any invoice
Where:    src/api/invoices.ts:64  GET /api/invoices/:id
Path:     req.params.id → invoiceRepo.findById(id) → res.json(invoice)
          No tenant or ownership predicate anywhere in the chain.
Evidence: requireAuth middleware runs (router.ts:12) but only asserts a valid session;
          findById issues `SELECT * FROM invoices WHERE id = $1` with no user scoping.
Impact:   Sequential integer IDs → full customer invoice enumeration across all tenants,
          including names, addresses and amounts. Regulated data.
Verdict:  CONFIRMED
Fix:      Scope the query to the session tenant and 404 (not 403) on mismatch:
            const invoice = await invoiceRepo.findOne({ id, tenantId: session.tenantId });
            if (!invoice) return res.status(404).end();
          Apply the same predicate to the 4 sibling handlers in this file (variant analysis).
Verify:   Log in as tenant A, request an ID owned by tenant B → expect 404.
          Regression test added in invoices.authz.test.ts.
Refs:     OWASP A01:2025 · CWE-639 · ASVS 5.0 §8.2.1
```

**Rules for the write-up:**
- One finding per issue; group variants under one finding with a list of locations.
- Lead with impact in plain language — the reader may not be an engineer.
- The fix must be code for *this* codebase, not a principle.
- Every claim must be traceable to a file and line you actually read.
- Order the report by exploitability. The first item should be the one to fix today.
- Include a **"Not assessed"** section. Silence about what you could not check reads as "safe",
  and that is how audits become dangerous.
