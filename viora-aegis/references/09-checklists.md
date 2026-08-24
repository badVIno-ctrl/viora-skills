# Checklists

Gates, not essays. Copy the relevant block into a PR description, a runbook, or a release ticket.

---

## A. Pre-commit (30 seconds)

- [ ] No secret, token, key, `.env` or dump in the diff (`viora scan --diff HEAD --only SECRET`)
- [ ] No `console.log`/`print` of sensitive values, no debug flags left on
- [ ] New user input is validated at the boundary with an allowlist schema
- [ ] New queries are parameterised; no string-built SQL or shell commands
- [ ] New routes have an explicit authorization check, not just authentication
- [ ] No `TODO: security`, commented-out checks, or temporarily widened permissions

---

## B. Pull request review (5 minutes)

- [ ] `viora scan --diff origin/main` is clean, or every finding has a verdict
- [ ] Threat model updated if a trust boundary changed
- [ ] Authorization: does every new endpoint check *ownership*, not just login?
- [ ] Error handling fails **closed**; no `catch { return true }`, no swallowed exceptions
- [ ] New dependencies: justified, popular, maintained, license-clear, no install scripts
- [ ] Tests include at least one abuse case for new security-relevant logic
- [ ] No control was weakened to make a test or build pass
- [ ] Logging added for new auth/authz/admin events; nothing sensitive logged

---

## C. Pre-deploy / release sign-off

**Blockers — do not ship with any of these open:**
- [ ] Zero Critical findings; zero High findings without written, time-boxed acceptance
- [ ] No secrets in the repo or in the image; all secrets injected at runtime
- [ ] TLS enforced end to end; HSTS on; no certificate verification disabled anywhere
- [ ] Authentication and authorization verified on every state-changing endpoint
- [ ] Debug off, stack traces off, source maps not public, admin endpoints not exposed

**Required:**
- [ ] Security headers deployed (`viora headers https://staging.example` clean)
- [ ] Rate limiting on auth, reset, registration, search and expensive endpoints
- [ ] Dependencies scanned; reachable Critical/High CVEs resolved or accepted in writing
- [ ] Backups exist **and a restore has been tested**
- [ ] Logging and alerting live: failed logins, authz denials, 5xx spikes, cost anomalies
- [ ] Rollback plan documented and tested
- [ ] Incident contact and escalation path known by the on-call

---

## D. New project baseline (day one)

- [ ] `.gitignore` covers `.env*`, `*.pem`, `*.key`, dumps, credentials — **before** the first commit
- [ ] Secret scanning in pre-commit and CI (`viora init --hook --ci github`)
- [ ] Dependency lockfile committed; CI installs frozen
- [ ] `permissions: contents: read` in every workflow; actions pinned to SHAs
- [ ] Branch protection: review required, force-push disabled, signed commits if possible
- [ ] Auth built on a proven library or provider, never hand-rolled
- [ ] Input validation library adopted (Zod / Pydantic / Joi / DTO validation) and used at boundaries
- [ ] Security headers middleware installed (`helmet`, `django-csp`, equivalent)
- [ ] Structured logging with a redaction filter
- [ ] `SECURITY.md` with a disclosure contact

---

## E. Authentication & session review

- [ ] Passwords hashed with Argon2id / bcrypt(≥12) / scrypt; never MD5, SHA-1 or unsalted
- [ ] Rate limiting + lockout/backoff on login, reset, registration, MFA and token endpoints
- [ ] Session ID regenerated on login and on privilege change
- [ ] Sessions invalidated on logout, password change and MFA reset — on the server, not just client
- [ ] Cookies: `HttpOnly`, `Secure`, `SameSite=Lax|Strict`, scoped, sane expiry
- [ ] JWT: algorithm pinned, signature verified, `exp`/`iss`/`aud` checked, revocation possible
- [ ] Reset tokens: CSPRNG, hashed at rest, single-use, short TTL, bound to the account
- [ ] Uniform errors and timing — no user enumeration
- [ ] MFA available, and enforced for privileged accounts
- [ ] Constant-time comparison for all secret comparisons

---

## F. API review

- [ ] Every endpoint: authentication **and** object-level authorization
- [ ] Input validated by schema; unknown fields rejected (no mass assignment)
- [ ] Output filtered by an explicit allowlist — no accidental `password_hash`, `internal_notes`
- [ ] Rate limits per user and per IP; global concurrency cap
- [ ] Pagination bounded; no unbounded `limit`
- [ ] Request body size capped at the app **and** the proxy
- [ ] Errors generic to the client, detailed in logs with a correlation ID
- [ ] CORS: exact origin allowlist; wildcard never combined with credentials
- [ ] IDs opaque (UUID/ULID) where enumeration matters
- [ ] Versioning and deprecation path; old versions actually retired

---

## G. Frontend review

- [ ] No `innerHTML`/`dangerouslySetInnerHTML`/`v-html` with dynamic data (or DOMPurify immediately before)
- [ ] CSP without `unsafe-inline`/`unsafe-eval`; nonces or hashes for inline scripts
- [ ] No secrets in client code, bundles, source maps or `NEXT_PUBLIC_*`-style variables
- [ ] Auth tokens in `HttpOnly` cookies rather than `localStorage` where feasible
- [ ] SRI on third-party scripts; third-party scripts minimised and reviewed
- [ ] `target="_blank"` paired with `rel="noopener noreferrer"`
- [ ] `postMessage` handlers validate `event.origin`
- [ ] Client-side validation duplicated server-side — always

---

## H. Incident response (first 60 minutes)

1. **Contain.** Revoke the credential, disable the account, block the IP, take the endpoint offline.
   Containment beats investigation in the first hour.
2. **Preserve.** Snapshot logs, memory and disk *before* remediating. You cannot un-delete evidence.
3. **Assess.** What data, whose data, how much, over what window? Is the access still live?
4. **Eradicate.** Patch the vulnerability, rotate every credential that was reachable, invalidate
   sessions and tokens.
5. **Recover.** Restore from a known-good backup, verify integrity, monitor for re-entry.
6. **Notify.** Legal/regulatory clocks (GDPR: 72 hours) start at *awareness*. Involve legal early.
7. **Learn.** Blameless post-mortem: timeline, root cause, detection gap, prevention, follow-ups with
   owners and dates.

**Secret exposed in git — exact order:**
rotate the credential → verify the old one is dead → check logs for use of the old one → remove from
code → purge history (`git filter-repo` / BFG) → force-push and notify collaborators → add a scan
gate so it cannot recur. **Deleting the line is not remediation** — the value is already harvested.

---

## I. Compliance quick map

| Regime | The parts engineers actually own |
|---|---|
| **GDPR** | Lawful basis, data minimisation, deletion and export on request, 72-hour breach notice, processor agreements, privacy by design |
| **PCI-DSS** | Never store CVV; tokenise PANs; segment the cardholder environment; use a hosted payment field so you stay out of scope |
| **HIPAA** | Encrypt PHI at rest and in transit, audit every access, minimum necessary, BAAs with vendors |
| **SOC 2** | Access reviews, change management, logging and monitoring, vendor management, documented incident response |

If the project touches payments, health data or EU residents, say so in the report — it changes
severity and it changes the deadline.
