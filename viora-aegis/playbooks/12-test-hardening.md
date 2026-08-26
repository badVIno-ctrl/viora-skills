# Playbook 12 - TESTS (security tests that actually hold)

**Goal:** leave behind tests that fail when the vulnerability comes back. A fix
without a test is a fix with an expiry date.

```bash
python3 scripts/viora.py plan tests
```

---

## The rule

> **A security test must fail on the unfixed code.**

Before you commit a test, verify it: revert the fix (or stash it), run the test,
and confirm it **fails**. A test that passes both before and after asserts
nothing. This one check is the difference between a real regression test and
decoration.

---

## Steps

1. **Identify what the fix actually changed** - the behaviour, not the diff. "An
   unowned object request now returns 403" is testable. "Added a check" is not.

2. **Write the negative test first.** The attack, asserted to fail:

   | Bug class | The test |
   |---|---|
   | SQL injection | Send `'; DROP TABLE users;--` as the parameter. Assert the row is stored/queried **literally** and the table still exists. |
   | Command injection | Send `; id` or `$(id)`. Assert no extra process ran and the value is treated as data. |
   | Path traversal | Request `../../etc/passwd` and its encoded forms. Assert 400/404, not file contents. |
   | Authorisation (IDOR) | As user A, request user B's object. Assert 403 or 404 - **and assert the body contains none of B's data**. |
   | Auth bypass | Call the endpoint with no token, an expired token, a token signed with the wrong key, and `alg: none`. Assert rejection in all four. |
   | XSS | Store `<img src=x onerror=alert(1)>`. Assert the rendered output is escaped. |
   | Fail-open | Force the security dependency to throw or time out. Assert **denial**. |
   | SSRF | Pass `http://169.254.169.254/`, `http://localhost:22`, and a redirect to an internal IP. Assert refusal. |
   | Deserialisation | Feed a crafted payload. Assert a parse error, not object construction. |
   | Rate limit | Exceed the bound. Assert 429 and that the counter is not resettable by the client. |

3. **Then write the positive test** - the legitimate case still works. Without
   it, the next developer "fixes" your test by loosening the check, because they
   cannot tell what the correct behaviour is.

4. **Test the boundary, not just the middle.** For every bound (Law 9): one
   under, exactly at, one over. Off-by-one is where limits fail.

5. **Test every path to the same sink.** If three routes reach one handler, the
   guard must be tested on all three, or the untested one is where it is missing.

6. **Make failure loud and specific.** Assert the status code **and** the
   absence of the sensitive data. A test asserting only `!= 200` passes when the
   server 500s for an unrelated reason, which is a false sense of safety.

7. **Never assert the insecure behaviour.** If an existing test encodes the bug -
   asserting that an unowned object returns 200 - that test **is** the
   vulnerability, written down. Change it deliberately and say so loudly in the
   report.

8. **Add the scanner as a test.** The cheapest permanent regression gate:
   ```bash
   python3 scripts/viora.py scan --fail-on high --quiet
   ```

---

## Test-first rules for the scanner itself

When you add a rule to `rules/*.json`, add both fixtures in the same change. A
rule with no negative fixture becomes a noise generator, a noisy rule gets
disabled, and a disabled rule protects nobody.

```python
# tests/fixtures/inj_042.py

# ruleid: INJ-042        <- must match
cur.execute("SELECT * FROM t WHERE id = " + user_id)

# ok: INJ-042            <- must NOT match
cur.execute("SELECT * FROM t WHERE id = %s", (user_id,))
```

Convention: `# ruleid: <ID>` marks a line that **must** be flagged; `# ok: <ID>`
marks a line that **must not** be. Run the scanner over the fixtures and diff the
result against the annotations. Both directions must hold - a rule that catches
the bug but also catches the correct code is not ready.

The negative fixture is the more valuable of the two. It is what keeps the rule
alive over time.

---

## Hard stops

- Do not weaken, skip, `xfail` or delete a test to make a build green.
- Do not commit a test you have not seen fail on the vulnerable code.
- Do not put a real credential in a test fixture. Law 5 covers test files.
- Do not test against production. Ever.

---

## Output

```
Fix:            <what changed>
Negative test:  <path::name>  - verified failing before the fix
Positive test:  <path::name>  - legitimate use still works
Boundaries:     <under / at / over, if applicable>
Paths covered:  <every route reaching the sink>
Gate added:     <scanner command, if any>
```
