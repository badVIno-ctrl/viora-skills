# Threat model — <system name>

**Owner:** · **Last updated:** · **Reviewers:**

## 1. Scope

**In scope:**
**Out of scope:** <!-- name it explicitly, so nobody assumes coverage -->

## 2. System

<!-- A diagram, or a component list. Mark every trust boundary with a line. -->

| Component | Trusts | Handles data class | Exposed to |
|---|---|---|---|
| | | Critical / Sensitive / Internal / Public | Internet / internal / operators |

## 3. Actors

| Actor | Legitimate capability | If compromised, they get |
|---|---|---|
| Anonymous visitor | | |
| Authenticated user | | |
| Admin / operator | | |
| Service account / CI | | |
| Third-party integration | | |
| Agent / LLM | | |

## 4. Trust boundaries

| # | Boundary | What crosses | Control on the boundary | Verified by |
|---|---|---|---|---|
| B1 | Internet → API | requests, uploads | authN, schema validation, rate limit, size cap | |
| B2 | App → database | queries | bound params, least-privilege user, RLS | |
| B3 | App → third party | outbound calls | allowlist, SSRF guard, timeout | |
| B4 | Tenant → tenant | shared storage/cache | tenant predicate everywhere | |
| B5 | Untrusted content → LLM | RAG docs, web, email | delimiting, provenance, no instruction authority | |

## 5. Threats (STRIDE)

| # | Boundary | STRIDE | Threat | Likelihood | Impact | Control | Status |
|---|---|---|---|---|---|---|---|
| T1 | B1 | S | | | | | open / mitigated / accepted |
| T2 | B2 | T | | | | | |
| T3 | B1 | I | | | | | |
| T4 | B1 | D | | | | | |
| T5 | B4 | E | | | | | |

## 6. Abuse cases → tests

| User story | Abuse case | Test that proves the control |
|---|---|---|
| | | |

## 7. Data

| Data | Class | Stored where | Encrypted? | Retention | Deletion path |
|---|---|---|---|---|---|
| | | | | | |

**Do we need to store it at all?** <!-- The cheapest control is not collecting the data. -->

## 8. Accepted risks

| Risk | Why | Compensating control | Owner | Review by |
|---|---|---|---|---|
| | | | | |

## 9. Assumptions

<!-- The things that, if they stop being true, invalidate this model. Most breaches live here.
     e.g. "the gateway strips X-Forwarded-For", "the internal network is not attacker-reachable",
     "the payment provider validates the amount". Add a check for each where possible. -->

1.
2.
3.

## 10. Follow-ups

| Action | Owner | Due |
|---|---|---|
| | | |
