# Playbook 03 - FIX findings

**Goal:** remediate confirmed findings without breaking the product and without
faking green.

```bash
python3 scripts/viora.py plan fix
```

---

## Steps

1. **Refuse to fix what is not verified.** For each item, confirm a verdict of
   CONFIRMED or LIKELY exists. If not, run `04-triage-verify.md` first.
   ELSE if it is UNDETERMINED: say what fact is missing. Do not "fix" it
   speculatively - a speculative fix hides the question forever.

2. **Order the work by exploitability**, not by how easy the fix is:
   critical -> high -> the class fix that closes several mediums at once.

3. **Check the blast radius before editing.** Stop and ask the user first if the
   fix touches:
   - authentication, session, or token issuance
   - authorisation, roles, ownership or tenancy
   - CORS, CSP or cookie flags
   - crypto, key handling or password hashing
   - payment, billing or quota logic
   - anything that can lock users out or let users in

   Ask like this: *"This fix changes `<file>`, which controls `<behaviour>`. It
   may affect `<who>`. Confirm before I proceed."*

4. **Fix the class, not the line.** One unparameterised query means the module
   builds SQL by concatenation. Fix the module or introduce the safe helper.
   Then grep for siblings before you call it done:
   ```bash
   python3 scripts/viora.py plan variants
   ```

5. **Prefer the platform's control**, in this order:
   1. The framework's built-in (parameterised API, auto-escaping, authz
      decorator, signed cookies).
   2. A vetted library.
   3. Hand-written validation - last resort, and it must be an allowlist.

6. **Apply the change.** Minimal, readable, in the codebase's existing style. No
   drive-by refactors mixed into a security fix - it makes the fix unreviewable.

7. **Leave a test that fails without the fix.** This is not optional. A fix with
   no test comes back.
   - Injection -> a test asserting the payload is stored or rejected literally,
     not executed.
   - Authorisation -> a test where user A requests user B's object and gets 403/404.
   - Fail-open -> a test that forces the check to throw and asserts denial.

8. **Secrets follow a fixed order.** Do not reorder it:
   1. **Rotate** the credential. It was public the moment it was pushed.
   2. Remove it from the code, replace with env or a secret manager.
   3. Purge it from git history - **ask first**, this rewrites history.
   4. Add a gate so it cannot happen again (`13-harden.md`).

9. **Prove it.** Re-run the exact detector that found it:
   ```bash
   python3 scripts/viora.py scan --diff HEAD --fail-on high
   ```
   Then run the project's own test suite. Report both results honestly.

10. **Report what could break.** For every fix: the behaviour change, who could
    be affected, and any migration or config step required.

---

## Hard stops - these are how security fixes go wrong

- **Never weaken a check to get green.** If a test asserted the insecure
  behaviour, that test encoded the bug. Change it deliberately, and say so
  loudly in the report.
- **Never delete or skip a failing test** to close a finding.
- **Never widen a suppression** to silence a scanner. If you suppress, it is one
  line, with a rule ID and a reason:
  ```js
  // viora-ignore: XSS-001 value is a fixed enum set in config, not user input
  ```
- **Never mix an unrelated refactor** into a security fix.
- **Never claim a fix works without re-running the detector.**

---

## Output

For each finding:

```
RULE-ID - title
Fixed in:   path/file.ext:line
Change:     what you did, one sentence
Why safe:   which law or control now holds (e.g. "Law 2 - argv array, no shell")
Test:       path/to/test  (fails without the fix)
Verified:   command run + result
Breaks:     what callers must know, or "nothing"
```

Then a summary: fixed N, deferred N (with reasons), still open N.
