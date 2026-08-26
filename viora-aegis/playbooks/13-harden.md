# Playbook 13 - HARDEN (gates that stay green)

**Goal:** install controls that stop the *next* vulnerability from being
committed. A gate people disable is worse than no gate, because it teaches the
team that security tooling is noise.

```bash
python3 scripts/viora.py plan harden
```

---

## The rule

> **Install in order. Each step reduces the noise for the next one.**

The order below is not a preference. A CI gate installed before a baseline fails
on day one against pre-existing debt, someone adds `continue-on-error`, and the
gate is now decoration that still costs CI minutes.

---

## Steps

1. **Recon what already exists.** Do not add a second linter next to a working
   one - you will double the noise and halve the trust.

   ```bash
   python3 scripts/viora.py doctor
   ```

   *ELSE if `doctor` fails:* look for `.pre-commit-config.yaml`,
   `.github/workflows/`, `.gitlab-ci.yml`, `.semgrep.yml`, `.gitleaks.toml` by
   hand before adding anything.

2. **Scaffold the baseline config, then read what it wrote** before committing.

   ```bash
   python3 scripts/viora.py init
   ```

   *ELSE:* copy `templates/pre-commit` and `templates/ci-github-actions.yml`
   manually and edit the paths.

3. **Set the pre-commit gate NARROW - secrets and criticals only.**

   ```bash
   python3 scripts/viora.py scan --staged --severity critical --fail-on critical --quiet
   ```

   A secret must never reach the remote, because once it is pushed, rotation is
   the only remedy - deleting the commit does not help. Everything else waits for
   CI. A pre-commit hook that takes 30 seconds or fires on style will be
   bypassed with `--no-verify` within a week, and then it catches nothing at all.

4. **Set the CI gate at `high`, scanning the DIFF.**

   ```bash
   python3 scripts/viora.py scan --diff origin/main --fail-on high \
       --format sarif --out viora.sarif
   ```

   Scanning the diff means a legacy repository does not fail on day one, and
   only **new** problems block a merge. This is the single most important choice
   in this playbook: a gate that blames you for someone else's 2019 code gets
   switched off.

5. **For a legacy repo, freeze today's findings as known debt.**

   ```bash
   python3 scripts/viora.py baseline
   ```

   Then agree a burn-down: how many, by when, who owns it. A baseline that is
   never reduced is a permanent exemption with a friendlier name.

6. **Harden the pipeline itself.** CI is a production system that holds
   credentials, and it is usually the least reviewed code in the repository.

   | Control | Why |
   |---|---|
   | Pin third-party actions to a 40-char commit SHA | A mutable tag is remote code with write access to your pipeline |
   | Default `permissions: contents: read` at the top level | Least privilege (Law 8); grant more per job, never globally |
   | Never combine a fork-triggered checkout with secrets | This is the single most exploited CI shape - see playbook 07 |
   | `npm ci --ignore-scripts` in credentialed jobs | Install scripts are arbitrary code from every transitive dependency |
   | Restrict who can trigger privileged workflows | `pull_request_target` and `issue_comment` are reachable by strangers |
   | Set a job timeout | An unbounded job is a cost and a stuck-runner problem (Law 9) |

   *ELSE if you do not own the CI config:* report these as findings instead of
   changing them, and say who does own it.

7. **Add dependency automation** (Dependabot or Renovate) with security updates
   on a fast track. Say out loud that review is still required - automated PRs
   are a delivery mechanism, not a decision.

8. **If it serves HTTP, add security headers.**

   ```bash
   python3 scripts/viora.py headers https://staging.example.com
   ```

   Stage CSP with `Content-Security-Policy-Report-Only` first, collect reports,
   then enforce. A CSP that breaks the product gets removed entirely.

   *ELSE:* skip if there is no environment you are authorised to test. Do not
   point this at production without permission.

9. **Enable the platform's secret push protection** as a backstop. The hook can
   be bypassed with `--no-verify`; server-side push protection cannot.

10. **Write down what each gate does *not* catch.** A gate the team believes is
    comprehensive is more dangerous than no gate, because it stops them looking.
    Regex scanners do not find missing authorisation checks, logic flaws, IDOR,
    or a fail-open `catch`. Say so explicitly.

---

## Hard stops

- **Never enable a gate you have not run locally first.** You are about to block
  every engineer in the repository.
- **Never add a gate that fails on pre-existing findings without a baseline.**
- **Never set `--fail-on low`.** It will be disabled, and it trains people to
  ignore the tool.
- **Never commit a suppression to make a new gate pass.** Fix it or baseline it -
  both are visible and countable. A suppression scattered in the code is neither.

---

## The trade-off, stated honestly

| Gate | Catches | Misses | Cost if too strict |
|---|---|---|---|
| Pre-commit, criticals + secrets | Secrets before they leave the machine | Everything subtle | Bypassed with `--no-verify` |
| CI on diff, `--fail-on high` | New high-severity code | Pre-existing debt, logic flaws | Merges blocked on false positives; `continue-on-error` appears |
| CI on full tree | Total debt picture | Nothing new, just louder | Permanent red build, total loss of signal |
| Dependency automation | Known CVEs in deps | Unreachable vs reachable | PR fatigue, blind merging |

Pick the narrow gate. A narrow gate that survives contact with a deadline is
worth more than a comprehensive one that gets deleted.

---

## Output

```
Gates added
  <name> | <command> | <where it runs> | <what it blocks>

Baseline
  <N> findings frozen as accepted debt
  Burn-down: <how many, by when, owner>

Not covered by these gates
  - missing authorisation checks (no scanner finds an absence)
  - business logic and IDOR
  - fail-open error paths
  - <anything else specific to this repo>

Verified locally
  <command> -> <exit code>
```

---

**Related:** `references/08-toolchain.md`, `templates/pre-commit`,
`templates/ci-github-actions.yml`, `templates/ci-gitlab-ci.yml`,
`playbooks/07-agent-ci-audit.md`.
