# Playbook 09 - VARIANTS (find the sibling bugs)

**Goal:** you confirmed one bug. Find every other instance of the same mistake.
The first bug is rarely the only one, because it was written by a habit, and
habits repeat.

```bash
python3 scripts/viora.py plan variants
```

**Precondition:** a CONFIRMED finding. This mode is never first. Without a
confirmed root cause you are pattern-hunting, not variant-hunting.

---

## Steps

1. **State the root cause, not the symptom.** One sentence, and it must describe
   the *mistake*, not the location.

   | Weak - a symptom | Strong - a root cause |
   |---|---|
   | "SQL injection in `getUser`" | "Query strings are built by f-string concatenation in the `db/` layer, because there is no parameterised helper." |
   | "Missing authz on `/orders/:id`" | "Handlers fetch by ID from the request without an owner check; authorisation is assumed to be done by middleware that only checks authentication." |
   | "XSS in the profile page" | "Template values are marked safe by default in this renderer, and the codebase calls `\|safe` habitually." |

   The root cause tells you what to search for. The symptom does not.

2. **Search for the exact known instance first.** Take the literal shape of the
   confirmed bug and find identical copies. High precision, zero imagination.
   ```bash
   grep -rn 'f"SELECT .* WHERE .*{' --include=*.py .
   ```
   Verify each hit. These are your true positives and they calibrate everything
   that follows.

3. **Generalise one element at a time.** This is the discipline of the mode.
   Change exactly one dimension per pass, and check the noise level after each:

   - Pass 1: the same function, other call sites.
   - Pass 2: the same sink, other query verbs (`INSERT`, `UPDATE`, `DELETE`).
   - Pass 3: the same pattern, other string-building forms (`%`, `+`, `.format`,
     template literals).
   - Pass 4: the same mistake, other sinks (shell, path, template, header).
   - Pass 5: the same mistake, other languages in the repo.

   **Stop the moment more than half the hits are noise.** That is the signal that
   you generalised past the actual habit and are now matching the language
   instead of the bug. Record where you stopped and why - the boundary is useful
   information for the next audit.

4. **Check the inverse.** Where the codebase does it *correctly*, is that pattern
   available everywhere? If a safe helper exists but only three of twenty call
   sites use it, the finding is that the helper is optional. Make the safe path
   the only path.

5. **Verify every variant independently.** A hit that matches the pattern is not
   automatically a bug - the input may be a constant here, or validated there.
   Run each through the three-question gate (`04-triage-verify.md`). Do not let
   the confirmed original make you generous.

6. **Group the results.** One root cause, N confirmed sites. Report it as a
   single finding with a site list, not as N findings - N findings implies N
   independent fixes, when one class fix closes all of them.

7. **Write down the patterns that found nothing.** This is as valuable as the
   hits: it tells the next reviewer which shapes are already clean, so the work
   is not repeated.

8. **Leave a rule behind.** Convert the confirmed pattern into a permanent check
   so it cannot come back. Add it to `rules/patterns.json`:

   ```json
   {
     "id": "INJ-0xx",
     "title": "SQL built by f-string concatenation",
     "category": "INJ",
     "severity": "high",
     "targets": ["*.py"],
     "pattern": "f\"[^\"]*(SELECT|INSERT|UPDATE|DELETE)[^\"]*\\{",
     "note": "Use a parameterised query. Law 2.",
     "fp": "A constant query with an interpolated table name from an internal enum."
   }
   ```

   **Write the tests with the rule** - one case that must match, one that must
   not. A rule with no negative test becomes a noise generator, and a noisy rule
   gets disabled, which protects nobody:

   ```python
   # ruleid: INJ-0xx
   cur.execute(f"SELECT * FROM users WHERE id = {user_id}")
   # ok: INJ-0xx
   cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
   ```

---

## Hard stops

- Do not report unverified variants. "Matches the pattern" is a lead, not a
  finding (Law 1).
- Do not keep generalising after the noise threshold. A pattern matching 400
  lines has told you nothing.
- Do not fix variants silently while auditing. Findings first, then FIX mode.

---

## Output

Use `templates/VARIANT_REPORT.md`.

```
Root cause:      <one sentence, the mistake>
Original:        <file:line of the confirmed bug>
Variants found:  N confirmed / M candidates checked
Sites:           file:line  (verdict)  x N
Patterns clean:  <shapes searched that found nothing>
Stopped at:      <the generalisation that went too noisy>
Rule added:      <rule ID + test case names>
Class fix:       <the one change that closes all of them>
```
