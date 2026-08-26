# Playbook 06 - SUPPLY-CHAIN

**Goal:** decide whether the dependencies of this project are safe to ship, and
whether the install itself is safe to run.

```bash
python3 scripts/viora.py plan supply-chain
python3 scripts/viora.py deps
```

---

## The one rule that governs this mode

> **Unavailable data is never evidence of risk, and an absent measurement is
> never a clean verdict.**

Every package ends up in exactly one of three buckets. There is no fourth.

| Bucket | Meaning |
|---|---|
| `assessed-clean` | You checked it against a real source and found nothing. |
| `assessed-flagged` | You checked it and found something. |
| `unassessable` | You could not check it - **and you must say why**. |

Never let `unassessable` silently become `clean`. Never let it become `risky`
either - a package is not dangerous because you had no network.

---

## Steps

1. **Inventory.**
   ```bash
   python3 scripts/viora.py deps --json .viora/deps.json
   ```

2. **Know which lockfiles are authoritative.** A resolved lockfile gives exact
   versions; a manifest gives ranges, and a range cannot be checked against an
   advisory.

   | Read as exact versions | Manifest only - ranges, not exact |
   |---|---|
   | `package-lock.json`, `npm-shrinkwrap.json` | `package.json` |
   | `uv.lock`, `poetry.lock`, `Pipfile.lock` | `requirements.txt` with `>=` or no pin |
   | `go.mod` (Go 1.17+), `go.sum` | - |
   | `Cargo.lock`, `composer.lock`, `Gemfile.lock` | `Cargo.toml`, `composer.json` |
   | `yarn.lock`, `pnpm-lock.yaml` | - |

   ELSE if there is no lockfile: that is itself a finding (`SUPPLY-*`). Builds
   are not reproducible and an advisory check cannot be exact. Say so.

3. **Check advisories for the exact installed version.** Not the latest version,
   not the range - the version that is actually installed.
   ```bash
   npm audit --json          # or: pnpm audit --json / yarn npm audit
   pip-audit -f json         # or: uv pip list --format json + osv
   govulncheck ./...
   cargo audit --json
   ```
   ELSE if no tooling or no network: mark every package `unassessable - no
   advisory source available`, and continue with the checks below that need
   neither.

4. **Audit install-time execution.** This runs on a developer machine and in CI,
   often with credentials present:
   - `postinstall`, `preinstall`, `install` scripts in `package.json` and in
     **transitive** dependencies.
   - `setup.py` with executable code at import time.
   - Any build script fetching from the network at install time.

   Then check whether the project could avoid them entirely:
   ```bash
   npm ci --ignore-scripts --dry-run
   ```
   If it succeeds, `--ignore-scripts` is viable in CI and should be recommended.

5. **Look for the human signals** - these matter more than a CVE count, because
   they predict the *next* compromise:
   - **Abandoned upstream**: last release age, open critical issues, archived repo.
   - **Single maintainer** on a package with deep reach.
   - **Recent ownership transfer** or a sudden maintainer change.
   - **Typosquat shape**: a name one edit away from a popular package. Check
     `reqeusts` vs `requests`, `lodahs` vs `lodash`.
   - **Suspiciously new version** of an old, stable package.
   - **Install-time-only package** with network access.
   - **A dependency that does not appear anywhere in the source.** Unused but
     installed still executes at install time.

6. **Check pinning and integrity.**
   - Lockfile committed?
   - Integrity hashes present (`integrity`, `--require-hashes`, `go.sum`)?
   - GitHub Actions pinned to a **commit SHA**, not a moving tag? A tag is
     mutable, so `@v4` is an unpinned dependency with write access to your CI.
   - Private registry configured with a `.npmrc` scope, so a public package
     cannot shadow an internal name (dependency confusion)?

7. **Check licences** if the user cares about distribution. Copyleft in a
   proprietary product is a legal finding, not a security one - report it
   separately and do not inflate its severity.

8. **Report.** Group by bucket, then by severity. For each flagged package:

   ```
   [SEVERITY] SUPPLY-xxx - package@version
   Where:   path/to/lockfile
   Path:    direct | transitive via <parent>
   Impact:  what the advisory or signal actually allows
   Verdict: CONFIRMED | UNDETERMINED
   Fix:     upgrade to <version>, or remove, or pin + --ignore-scripts
   Verify:  re-run the audit command
   Refs:    advisory ID
   ```

---

## Reachability matters

A critical CVE in a dev-only dependency that never ships is not a critical for
the product. State the distinction:

- **Runtime dependency, reachable code path** -> full severity.
- **Runtime dependency, feature not used** -> downgrade, say why.
- **Dev/test only** -> downgrade, but note it still runs on developer machines
  and in CI, which hold credentials.

This is Law 1 again: the advisory is a lead. Whether *this* project is exposed is
the finding.

---

## Hard stops

- Do not run `npm install`, `pip install` or any resolver **just to inventory**.
  Read the lockfile. Installing executes third-party code.
- Do not upgrade a major version as a "fix" without saying it is breaking.
- Do not report the sum of `npm audit` as the project's risk. Most of it is
  unreachable, and reporting it as-is destroys your credibility on the findings
  that matter.
