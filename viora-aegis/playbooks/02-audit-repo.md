# Playbook 02 - AUDIT a repository

**Goal:** find the real security problems in a codebase you have full access to.
This is the default mode when nothing more specific fits.

```bash
python3 scripts/viora.py plan audit
```

---

## Steps

1. **Recon.**
   ```bash
   python3 scripts/viora.py doctor
   ```
   Note the languages, frameworks, package managers and whether it is a git repo.

2. **Understand before hunting.** Write down these four, in one line each. If you
   cannot fill all four, run `10-context-building.md` first.
   - **Entry points** - every way untrusted data gets in: HTTP routes, CLI args,
     queue consumers, webhooks, file uploads, env, cron, LLM output.
   - **Auth layer** - where identity is established, and where authorisation is
     enforced. Name the files.
   - **Data stores** - databases, caches, buckets, secret stores.
   - **Trust boundaries** - the lines where data changes owner: internet to app,
     app to database, app to third party, tenant to tenant, user to admin.

3. **Run the detectors.** All four, in this order:
   ```bash
   python3 scripts/viora.py scan --format json --out .viora/scan.json
   python3 scripts/viora.py deps --json .viora/deps.json
   python3 scripts/viora.py defaults --format json --out .viora/defaults.json
   python3 scripts/viora.py ci-audit --format json --out .viora/ci.json
   ```
   ELSE if any fails: record which one, continue with the rest, and list the gap
   under "Not assessed".

4. **Read code in this priority order.** This ordering is the whole trick - it
   puts the highest-impact code first, so a small budget still finds real bugs:
   1. The authorisation layer. Not authentication - **authorisation**. Law 3.
   2. Every mutating route or handler: does each one check the object's owner?
   3. The sinks the scan flagged: SQL, shell, path, deserialise, template, HTTP.
   4. Secret handling and config defaults. Law 5, Law 4.
   5. Crypto usage. Law 7.
   6. Multi-tenant queries: is the tenant filter present on **every** one?

5. **Hunt what regexes cannot see.** These are absences, so no pattern finds
   them. Check each explicitly and record the answer:
   - A route with no authorisation check at all.
   - An `if` on a permission whose `else` continues rather than denies.
   - A query missing its `WHERE tenant_id = ?`.
   - An object fetched by an ID taken straight from the request (IDOR).
   - A `catch` that swallows a security error.
   - An unbounded loop, upload, page size or retry. Law 9.

6. **Verify everything** through the three-question gate
   (`04-triage-verify.md`). Batch it: restate all claims first, then verify each
   independently, then look for chains between confirmed findings.

7. **Chain the confirmed findings.** Two mediums that compose into an account
   takeover are a critical. Report chains before individual findings.

8. **Write the report** using `templates/SECURITY_REPORT.md`.
   ```bash
   python3 scripts/viora.py report --out SECURITY_REPORT.md
   ```

9. **Close with "Not assessed"** - every file, area and check you skipped, and
   why.

---

## Budget discipline

If the repository is larger than you can read:

- Audit by **trust boundary**, not by directory. Pick the internet-facing
  boundary first.
- Say explicitly which boundaries you covered and which you did not.
- Prefer depth on the auth layer over breadth across the whole tree. One
  confirmed authorisation bug is worth more than forty unread regex hits.

---

## Hard stops

- Do not report a scanner hit you did not read.
- Do not produce a "clean" verdict for an area you did not measure.
- Do not run live tests against a deployed host without explicit authorisation.
- Do not fix anything in this mode. Findings first; FIX is a separate mode with
  its own confirmation.

---

## Output

Findings ordered by exploitability, each in the fixed shape. Then:

```
Coverage
  Assessed:      <areas, boundaries, file counts>
  Not assessed:  <what and why>
Summary
  critical=N high=N medium=N low=N   confirmed=N undetermined=N false-positive=N
```
