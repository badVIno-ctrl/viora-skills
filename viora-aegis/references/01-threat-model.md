# Threat modelling in fifteen minutes

A threat model is not a document. It is four answers and a list. Do it before the code, or before
the audit — never after the incident.

---

## 1. The four questions

1. **What are we building?** One diagram or one paragraph. Components, data stores, external parties.
2. **What can go wrong?** STRIDE across each trust boundary.
3. **What are we going to do about it?** One control per plausible threat.
4. **Did we do a good job?** A test or a check for each control.

---

## 2. Draw the trust boundaries

A trust boundary is any line where data or control passes from something you trust less to something
you trust more. **Every security control lives on a boundary.** If a control is not on one, it is
decoration.

Typical boundaries:

| Boundary | What crosses it | Control that belongs there |
|---|---|---|
| Internet → web/API | Requests, uploads, webhooks | AuthN, schema validation, rate limits, size caps |
| Client → server | Anything the browser sends back | Server-authoritative state; never trust returned prices/roles |
| Service → service | Internal RPC | mTLS or signed tokens, per-service authz, timeouts |
| App → database | Queries | Parameter binding, least-privilege DB user, row-level security |
| App → third party | Outbound calls | Allowlist, SSRF guard, timeouts, response validation |
| Third party → app | Webhooks, OAuth callbacks | Signature verification, replay window, idempotency |
| Tenant → tenant | Shared storage/queues/cache | Tenant predicate on every query, key namespacing |
| Human → privileged action | Admin console, deploys | MFA, approval, audit log |
| LLM → application | Model output, tool calls | Treat as untrusted input; schema + allowlist + confirmation |
| Untrusted content → LLM | RAG docs, web pages, emails, PR bodies | Delimiting, provenance tags, no instruction authority |

**Rule:** enumerate boundaries first, then walk each one. Bugs cluster where a boundary was not
recognised as one — especially "internal" services and LLM output.

---

## 3. STRIDE worksheet

For each boundary, write one line per threat that is *actually plausible here*. Skip the rest — a
model that lists everything gets read by nobody.

| Threat | Question | Typical control |
|---|---|---|
| **S**poofing | Can someone claim to be another user, service or origin? | AuthN, mTLS, signature verification, SPF/DKIM |
| **T**ampering | Can data be modified in transit, at rest, or in the client? | TLS, integrity checks, parameterised queries, signed state |
| **R**epudiation | Can someone deny an action? Could we reconstruct it? | Append-only audit log with actor + correlation ID |
| **I**nformation disclosure | What leaks — in responses, errors, logs, timing, or metadata? | Field allowlists, generic errors, encryption, redaction |
| **D**enial of service | What is unbounded — requests, payload, recursion, cost? | Rate limits, size caps, timeouts, budgets, queue limits |
| **E**levation of privilege | How does a user become an admin, or a tenant reach another tenant? | AuthZ on every operation, least privilege, no mass assignment |

---

## 4. Abuse cases

For every user story, write the attacker's version. This is the highest-value five minutes in the
whole process, and it produces your test cases for free.

| User story | Abuse case | Test |
|---|---|---|
| "A user can download their invoice" | "I change the ID and download someone else's" | Cross-tenant ID → expect 404 |
| "A user can upload an avatar" | "I upload a 2 GB polyglot SVG with a script and a `../../` name" | Size, MIME-by-magic-bytes, path, and render-context tests |
| "A user can reset their password" | "I reuse the token, or request 10 000 resets for someone else" | Single-use token, rate limit per account |
| "A user can invite a teammate" | "I invite myself to another org, or set role=owner in the payload" | Field allowlist, org-scoped authz |
| "A user can pay" | "I replay the callback, or change the amount client-side" | Signature + idempotency + server-side price |
| "The agent can read our docs" | "I plant instructions in a doc so the agent exfiltrates data" | Untrusted-content isolation, egress allowlist |

---

## 5. Classify the data

Controls follow the data, not the code.

| Class | Examples | Minimum controls |
|---|---|---|
| **Critical** | Passwords, keys, tokens, payment data, health, government ID | Encrypt at rest + in transit, strict access control, audit every access, never log, defined retention |
| **Sensitive** | Names, emails, addresses, phone, IP, behavioural data | Access control, encrypt in transit, minimise, redact in logs, honour deletion |
| **Internal** | Business config, non-public metrics | AuthN required, no public caching |
| **Public** | Marketing content | Integrity only |

Ask, every time: **do we even need to store this?** The cheapest control is not collecting the data.

---

## 6. Multi-tenant checklist

If the product has more than one customer, tenancy is the number-one risk. Check all of it:

- [ ] Every query carries a tenant predicate, enforced centrally (repository/ORM scope, RLS) — not
      per-handler and not by convention.
- [ ] Cache keys, queue names, blob paths, search indices and vector namespaces include the tenant.
- [ ] Background jobs carry tenant context; a retried job cannot run in the wrong tenant.
- [ ] Cross-tenant admin/support access is explicit, logged, time-boxed, and visible to the customer.
- [ ] IDs are opaque; leaking a UUID does not leak a tenant boundary.
- [ ] Exports, webhooks and AI/RAG retrieval are tenant-filtered at the source, not in the UI.
- [ ] Rate limits and quotas are per-tenant — one customer cannot starve the others.
- [ ] There is a test that logs in as tenant A and asserts 404 for tenant B's resources.

---

## 7. Output

Fill `templates/THREAT_MODEL.md`. Keep it under two pages:

1. **Scope** — what is in, what is explicitly out.
2. **Diagram / component list** with trust boundaries marked.
3. **Threat table** — boundary, STRIDE letter, threat, control, owner, status.
4. **Abuse cases** — the ones that became tests.
5. **Accepted risks** — what you consciously chose not to fix, why, and who signed off.
6. **Assumptions** — the things that, if false, invalidate the model ("the gateway strips
   `X-Forwarded-For`", "internal network is not attacker-reachable").

That last section matters most. Most breaches are an assumption that quietly stopped being true.
