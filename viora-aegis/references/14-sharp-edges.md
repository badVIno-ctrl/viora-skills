# Sharp edges — APIs that make the wrong call look right

A vulnerability is usually not a mistake in reasoning. It is an API where the
dangerous call and the safe call look the same in review. Six classes, each with
the rule that hunts it and the design change that removes it.

Rules live in `rules/defaults.json` as `DEFAULT-001` … `DEFAULT-006`. Run them
with `viora.py defaults`.

---

## 1. The bool that hides a decision — `DEFAULT-001`

`verify=False`, `secure=false`, `strict=0`. At the call site a security switch
reads exactly like a retry setting. Nothing in the line says what is being given
up, so review slides over it and grep finds it only if you already know the
keyword.

**Fix:** take an enum or a policy object. `TlsPolicy.SKIP_VERIFICATION` cannot be
skimmed past; `verify=False` can.

## 2. Verification off by keyword argument — `DEFAULT-002`

`rejectUnauthorized: false`, `InsecureSkipVerify: true`, `CERT_NONE`, `curl -k`.
Usually added once to get past a self-signed certificate in development, then it
ships. The connection is still encrypted, which is why nothing breaks and nobody
notices: it is encrypted to whoever answered.

**Fix:** keep verification on and pin the internal CA. If a test genuinely needs
it, scope it to that test's client, never a shared session or a global default.

## 3. The sentinel that inverts the meaning — `DEFAULT-003`

`ttl=0`, `max_age=-1`, `expires_in: 0`. Read naively, zero means "immediately".
In most APIs it means "never". A token nobody tracks is issued with no expiry and
outlives the employee it was issued to.

**Fix:** require an explicit bounded duration, and reject 0 at config load with
an error that names the field. Never let a sentinel carry the most dangerous
meaning.

## 4. Stringly-typed security state — `DEFAULT-004`

`if user.role == "admin"`. The typo `"Admin"` compiles, passes tests that use
the same typo, and fails open or closed depending on which side of the branch it
lands. Nothing enumerates the valid roles, so no reviewer can tell whether the
set is complete.

**Fix:** an enum, and a total authorisation function — an unknown role must
deny, loudly, rather than falling through.

## 5. A security answer that is easy to drop — `DEFAULT-005`

`check_permission(user, doc)` on its own line. The function ran, the answer went
nowhere, execution continued. It looks like a gate in a diff and behaves like a
comment. The same shape covers an ignored `verify_signature` return value.

**Fix:** raise on denial, or return a value the caller is forced to consume. If
the API cannot make the result unignorable, the API is the finding.

## 6. Dangerous combinations accepted in silence — `DEFAULT-006`

`Access-Control-Allow-Origin: *` with `credentials: true`. `SameSite=None`
without `Secure`. `alg: none` with verification disabled. Each option is legal
alone; the library validates each one alone, and the pair is the vulnerability.

**Fix:** validate the *combination* at startup and refuse to boot. A config
error at deploy time costs minutes. The same combination discovered later costs
an incident.

---

## Reviewing your own API

Three questions, from the caller's side:

1. **Can the dangerous call be shorter than the safe one?** If disabling a
   control is one keyword and enabling it is three lines, the default has
   already been chosen for you.
2. **Does the call site name the risk?** A reviewer with no context should be
   able to see what is given up without opening your documentation.
3. **Can the result be ignored?** If the caller can drop the security answer on
   the floor without a warning, some caller eventually will.

If a call site fails all three, no amount of documentation fixes it. Change the
signature.
