# Optional pro tooling

`viora.py` needs nothing installed and works everywhere. When heavier tools *are* available, use
them for depth — then merge everything into one report. Check availability first:

```bash
python3 scripts/viora.py doctor --path .
```

---

## Semgrep — semantic static analysis

```bash
semgrep --config=p/security-audit --config=p/secrets --config=p/owasp-top-ten \
        --severity=ERROR --json -o .viora/semgrep.json .
semgrep --config=p/ci --baseline-commit origin/main .        # diff-only, fast
```

Understands data flow, so far fewer false positives than regex. Write a custom rule whenever you fix
a bug class so the family cannot come back:

```yaml
rules:
  - id: viora-raw-sql-concat
    languages: [python]
    severity: ERROR
    message: SQL built by interpolation. Use bound parameters.
    patterns:
      - pattern: $CUR.execute(f"...")
      - pattern-not: $CUR.execute($SQL, $PARAMS)
```

## gitleaks — secrets, including git history

```bash
gitleaks detect --source . --redact --report-path .viora/gitleaks.json
gitleaks protect --staged --redact          # pre-commit
```

History matters: a secret deleted in the latest commit is still live in the repository.

## Trivy — dependencies, images, IaC, secrets

```bash
trivy fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL .
trivy image --severity HIGH,CRITICAL myapp:1.2.3
trivy config infra/
```

## Language-specific

```bash
bandit -r . -f json -o .viora/bandit.json      # Python
npm audit --omit=dev --json                    # Node
pip-audit -f json                              # Python deps
govulncheck ./...                              # Go, reachability-aware
cargo audit                                    # Rust
brakeman -A                                    # Rails
osv-scanner -r .                               # everything, OSV database
```

`govulncheck` is the gold standard for triage: it reports only vulnerabilities whose code is actually
reachable. Apply the same *reachability-first* logic manually for other ecosystems.

## CodeQL — deep dataflow, when you need proof

```bash
codeql database create db --language=javascript --source-root=.
codeql database analyze db codeql/javascript-queries:codeql-suites/javascript-security-extended.qls \
       --format=sarif-latest --output=.viora/codeql.sarif
```

Slow, precise, and the right tool when you must *prove* a source reaches a sink across many files.

## Containers and IaC

```bash
hadolint Dockerfile
checkov -d infra/ --compact
tfsec infra/
kube-score score k8s/*.yaml
```

## DAST — only against systems you own

```bash
docker run --rm -v "$PWD:/zap/wrk" -t ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t https://staging.example.com -r zap-report.html
nuclei -u https://staging.example.com -severity critical,high
```

Confirm ownership or written authorisation first (`SKILL.md` §9). Run against staging, never
production, and never against a third party.

---

## Merging results

```bash
python3 scripts/viora.py scan  --path . --format json --out .viora/viora.json
python3 scripts/viora.py deps  --path . --online     --json .viora/deps.json
python3 scripts/viora.py headers https://staging.example --json .viora/headers.json
python3 scripts/viora.py report --in .viora --out SECURITY_REPORT.md --title "Q3 audit"
```

`report` deduplicates by fingerprint and orders by severity. Any JSON file with a `findings` array
in the same shape is merged, so you can normalise Semgrep/Trivy output into `.viora/` and include it.

---

## Reading tool output well

1. **Tools produce leads, not findings.** Everything still passes the verification gate (`SKILL.md` §5).
2. **Deduplicate across tools** — four scanners reporting one line is one finding.
3. **Downgrade test and fixture paths** by default; upgrade them only if test credentials are real.
4. **A clean scan proves nothing about access control or business logic.** Those need reading. Say so
   in the report rather than implying coverage you do not have.
5. **Tune once, benefit forever.** When you confirm a false positive, add a targeted suppression with
   a reason (`// viora-ignore: RULE-ID why`), not a global rule disable.
