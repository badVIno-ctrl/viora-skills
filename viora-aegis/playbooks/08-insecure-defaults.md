# Playbook 08 - DEFAULTS (insecure defaults and fail-open paths)

**Goal:** find the places where the system is insecure **when nobody configures
it** - and the places where a failing security check lets the request through.

```bash
python3 scripts/viora.py plan defaults
python3 scripts/viora.py defaults
```

---

## The reading rule

> **Read the default value, not the flag name.**

`verify_ssl`, `strict_mode`, `secure`, `enforce_auth` - the name tells you the
author's intention. The default tells you the behaviour. `verify_ssl=False` is
not a strict mode, whatever it is called. Every judgement in this mode comes from
the value on the right of the `=`.

Corollary: a security control that is **off by default** protects nobody, because
the deployment that forgets to turn it on is the deployment that gets breached.

---

## Steps

1. **Run the corpus scan.**
   ```bash
   python3 scripts/viora.py defaults --format json --out .viora/defaults.json
   ```
   ELSE degraded: grep the patterns in `rules/defaults.json` directly.

2. **Work the six corpora.** Treat each as a separate pass - they fail
   differently and a single sweep misses them:

   | Corpus | What you are looking for |
   |---|---|
   | **Fallback secrets** | `os.getenv("KEY", "dev-secret")`, `process.env.X \|\| "changeme"`. The fallback ships and becomes the production key. |
   | **Default credentials** | `admin/admin`, a seeded user, a hardcoded token in config or a test fixture that the app also reads. |
   | **Fail-open security** | A `try/except` around an authz or signature check that continues. A `catch` returning `true`. A timeout treated as success. |
   | **Weak crypto defaults** | MD5/SHA1 for passwords, ECB, a static IV or salt, `random` instead of `secrets`, a short key, a disabled cert check. |
   | **Permissive access** | `CORS: *` with credentials, `0.0.0.0` bind, `chmod 777`, a public bucket, `AllowAny` permission class, wildcard IAM. |
   | **Debug features** | `DEBUG=True`, a stack trace to the client, an introspection endpoint, a profiler, a test backdoor guarded only by an env var. |

3. **For each candidate, verify by refutation.** Answer all three, in writing.
   This is what separates a finding from a config file quotation:

   ```
   V1 Is this value actually the default in a real deployment,
      or is it always overridden in every shipped config?
      -> Show the override, or it is the default.

   V2 Is the insecure path reachable in production,
      or is it dev-only and excluded from the build?
      -> Show the exclusion, or it is reachable.

   V3 What does an attacker get if it stays at this value?
      -> One concrete sentence, or it is not a finding.
   ```

   If a shipped config, Helm chart, Dockerfile or CI env sets a safe value on
   every path, the finding is DEFENCE-IN-DEPTH at most, and you must name where
   the override lives.

4. **Check the fail-open shape specifically.** This is the highest-value pattern
   in the mode and no regex finds it reliably. For every security decision - auth
   check, signature verify, permission lookup, token validation, rate limit -
   ask:
   - What happens if it **throws**?
   - What happens if the dependency it calls is **down or times out**?
   - What happens if it returns **null or undefined**?

   If any of those results in the request proceeding, that is Law 4 broken, and
   the severity is whatever the check was protecting.

5. **Assign a status to every corpus.** Never leave one blank:

   | Status | Meaning |
   |---|---|
   | `findings` | Confirmed insecure defaults, listed. |
   | `no-findings-confirmed` | You looked and the defaults are safe. |
   | `no-candidates` | Nothing of this shape exists here. **Not proof of absence** - say what you searched. |
   | `not-assessed` | You could not check. Say why. |

6. **Report** in the fixed finding shape. For each, the fix is the safe default
   plus a startup assertion:

   ```python
   SECRET = os.environ["APP_SECRET"]        # KeyError at boot, not a weak default
   ```

   Fail at startup, loudly, rather than running insecurely and quietly. A missing
   config should stop the process, not downgrade the security.

---

## Common false positives - check before reporting

- A default in a **test fixture or example file** that production never loads.
  Confirm the app does not read that path.
- A **development compose file** or `.env.example` clearly marked as such.
- A permissive default in a **library** where the caller is required to configure
  it - though "insecure unless configured" is still worth a low.
- A flag that looks dangerous but the framework overrides at runtime. Name the
  version and mechanism (gate G5).
- A weak hash used for a **non-security purpose** - a cache key, an ETag, a
  checksum. MD5 for deduplication is not a crypto finding. Read what the digest
  is used for before judging it.

---

## Hard stops

- Do not report the existence of a config option as a finding. Report its value.
- Do not change a default without saying what deployments it breaks - flipping a
  default is a breaking change for everyone relying on the old one.
- Do not report `DEBUG=True` in a file named `settings_dev.py` at high severity
  without showing that production loads it.
