# Playbook 01 - REVIEW a diff

**Goal:** decide whether this change is safe to merge. Scope is the diff, plus
whatever the diff reaches.

```bash
python3 scripts/viora.py plan review
```

---

## Steps

1. **Recon.**
   ```bash
   python3 scripts/viora.py doctor
   ```
   ELSE if it fails: note degraded mode and continue.

2. **Get the diff.** Try in this order and use the first that produces output:
   ```bash
   git diff --stat HEAD
   git diff --stat origin/main...HEAD
   git diff --stat --staged
   ```
   ELSE if there is no diff: this is not REVIEW. Switch to AUDIT
   (`02-audit-repo.md`).

3. **Scan only what changed.**
   ```bash
   python3 scripts/viora.py scan --diff HEAD --format json --out .viora/review.json
   ```
   Use `--diff origin/main` for a PR.

4. **Classify the change before reading hits.** Write one line for each that
   applies - this decides how hard you look:
   - touches authentication, session or token handling
   - touches authorisation, roles, ownership or tenancy checks
   - adds or changes an input boundary (route, handler, form, webhook, queue)
   - adds or changes a dangerous sink (SQL, shell, filesystem, HTTP, deserialise, template)
   - adds or changes a dependency
   - touches crypto, secrets or config defaults
   - touches CI, workflows or build scripts
   - touches an LLM prompt, tool definition or agent loop

   ELSE if none apply: say so, do a light pass, and stop early. Not every diff
   is a security event.

5. **Read every hit at its `file:line`.** No exceptions. A hit you did not read
   cannot be reported.

6. **Look for what the scanner cannot see.** Regexes do not find missing things.
   For each item you ticked in step 4, ask the matching question:
   - New route: is there an authz check, and does it check the *object's owner* -
     not just that the caller is logged in? (Law 3)
   - New parameter: is it bounded - length, count, depth, rate? (Law 9)
   - Error path added: does it deny on failure, or continue? (Law 4)
   - Removed code: did the diff delete a check? Read the `-` lines specifically.
   - New dependency: run `03` of `06-supply-chain.md`.

7. **Verify each candidate** through the three-question gate
   (`04-triage-verify.md`). Discard false positives explicitly - naming what you
   rejected is part of the deliverable.

8. **Report** in the fixed finding shape, ordered by exploitability.

9. **Verdict.** Exactly one of:
   - `APPROVE` - no confirmed findings at or above high.
   - `APPROVE WITH COMMENTS` - only medium/low, or defence-in-depth.
   - `REQUEST CHANGES` - one or more confirmed high/critical.
   Then list what you did not assess.

---

## Hard stops

- Do not approve a diff you could not read in full. Say which files you skipped.
- Do not report a finding that exists in code the diff did not touch **as if the
  diff introduced it**. Mark it `pre-existing`.
- Do not weaken or delete a test to make the change pass.

---

## The `-` lines matter most

The highest-value line in any security review is a deleted check. Scanners only
see what is there now. Read the removals deliberately:

```bash
git diff HEAD | grep -E '^-' | grep -Ei 'auth|permission|role|owner|verify|validate|check|csrf|escape|sanitiz|encrypt|assert|require'
```

A removed guard with no replacement is a finding at the severity of whatever it
was guarding.
