# Supply chain, CI/CD and infrastructure

A05 was the classic risk. **A03:2025 — Supply Chain Failures — is the growing one.** The attacker
does not breach your code; they breach something your code installs, or the pipeline that ships it.

---

## 1. Dependencies

### Before adding one

- Is it maintained? Last release, open issues, single-maintainer risk.
- How many transitive dependencies does it drag in? A 3-line utility with 40 deps is a liability.
- Does it need install-time scripts, native builds or network access at install?
- License compatible?
- Does the name match what you meant? **Typosquats** (`lodahs`, `reqeusts`, `python-dateutil` vs
  `dateutil`) and **slopsquats** (names an AI invented, then registered by an attacker) are the two
  live threats. Verify the package on the registry before installing anything an assistant suggested.

### Ongoing

- Commit lockfiles. Install frozen in CI: `npm ci`, `pnpm i --frozen-lockfile`,
  `pip install --require-hashes -r requirements.txt`, `cargo build --locked`.
- One package manager per installation boundary. Competing lockfiles mean somebody is installing
  something nobody reviewed.
- Disable lifecycle scripts by default (`npm ci --ignore-scripts`) and allowlist the few that need them.
- Scan continuously: `viora deps --online`, `npm audit`, `pip-audit`, `osv-scanner`, `govulncheck`,
  `cargo audit`, `trivy fs .`.
- Generate an SBOM (`syft`, `cyclonedx`) so "are we affected by CVE-X?" takes minutes, not days.

### Triaging a dependency CVE

1. **Is the vulnerable code path reachable from our entry points?** Unreachable → Low/Info + an
   upgrade ticket. Reachable → inherit the advisory severity and adjust for our exposure.
2. Is there a patched version? Upgrade, run tests, done.
3. No patch? Options: pin and mitigate at the call site, vendor a fix, replace the dependency, or
   accept the risk in writing with an owner and a review date.
4. Never apply a forced/automatic remediation blindly — it silently changes major versions.

### Signals of a compromised package

Obfuscated or minified code in a source package · network calls at install time · reading `~/.ssh`,
`~/.aws`, `.env`, browser profiles or keychains · base64 blobs decoded and executed · a maintainer
change followed immediately by a release · a version bump with no corresponding repository commit ·
postinstall that downloads a second-stage payload.

If you suspect compromise: freeze installs, pin the last known-good version, rotate every credential
that was present on machines that installed it (developer laptops and CI runners), and check egress
logs for the install window.

---

## 2. CI/CD — the highest-privilege code you run

Your pipeline holds deploy keys, registry tokens and cloud credentials, and it executes code from
anyone who can open a pull request.

### GitHub Actions rules

```yaml
permissions:
  contents: read          # workflow-level default; widen per job only where needed
```

- **Never** interpolate `${{ github.event.* }}` into a `run:` step. That is shell injection with a
  repository token attached:

  ```yaml
  # WRONG
  - run: echo "${{ github.event.issue.title }}"
  # RIGHT
  - run: echo "$TITLE"
    env:
      TITLE: ${{ github.event.issue.title }}
  ```

- `pull_request_target` runs **with repository secrets and write scope**. Never check out or execute
  PR head code inside it. Split: an unprivileged `pull_request` job builds; a privileged job
  consumes the artifact.
- Pin third-party actions to a full commit SHA, not a tag. Tags are mutable.
- Never `echo` a secret, and never pass one as a command-line argument (it lands in process lists
  and logs). Use `env:` and mask.
- Require approval for workflow runs from first-time contributors.
- Separate build and publish. Publishing credentials live only in the publish job, on protected
  branches or tags.
- Restrict runner egress where you can; a compromised step exfiltrates in one request.
- Self-hosted runners must be ephemeral — a persistent runner is a persistent foothold.

### Branch and release protection

Required review · no force-push to protected branches · required status checks including the security
gate · signed commits or tags where practical · artifact provenance/attestation · two-person rule for
production deploys.

---

## 3. Containers

```dockerfile
# Multi-stage: build tools never reach the runtime image
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM node:22-alpine
RUN addgroup -S app && adduser -S app -G app
WORKDIR /app
COPY --from=build --chown=app:app /app/dist ./dist
COPY --from=build --chown=app:app /app/node_modules ./node_modules
USER app                                  # never root
EXPOSE 3000
HEALTHCHECK CMD wget -qO- http://localhost:3000/health || exit 1
CMD ["node", "dist/server.js"]
```

**Checklist:** pin the base image by digest · minimal base (alpine/distroless/slim) · non-root user ·
no secrets in `ENV`/`ARG` (layers are readable — use BuildKit `--mount=type=secret`) · `.dockerignore`
covering `.env`, `.git`, `node_modules` · read-only root filesystem at runtime · drop all capabilities ·
resource limits · scan the image (`trivy image`) and rebuild regularly for base-image patches.

**Never:** `privileged: true` · mounting `/var/run/docker.sock` · `hostNetwork`/`hostPID` ·
`:latest` in production.

---

## 4. Kubernetes

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities: { drop: ["ALL"] }
resources:
  limits:   { cpu: "500m", memory: "512Mi" }
  requests: { cpu: "100m", memory: "128Mi" }
```

Plus: default-deny `NetworkPolicy` · secrets from a real secret manager (base64 in a Secret object is
not encryption) · RBAC scoped per service account, never `cluster-admin` · no default service-account
token automount · admission policy (Kyverno/OPA) to enforce all of the above.

---

## 5. Cloud and IaC

- No `0.0.0.0/0` except 80/443 on a load balancer. Never on SSH, RDP or database ports.
- Storage: block public access at the account level, enforce encryption, enable versioning and
  access logging.
- IAM: no wildcards in `Action` or `Resource`; separate roles per service; short-lived credentials
  via OIDC federation instead of long-lived keys in CI.
- Terraform state is a secret store — encrypt it, lock it, restrict access.
- Enable the cloud provider's own detection (GuardDuty / Defender / SCC) and route findings somewhere
  a human reads.
- Scan IaC in CI: `checkov`, `tfsec`, `trivy config`.

---

## 6. Artifact and release integrity

- Reproducible builds where feasible; record the build inputs.
- Sign artifacts (cosign/sigstore) and verify signatures at deploy time.
- Generate and publish an SBOM per release.
- Immutable tags in the registry; no overwriting a released version.
- Verify checksums for every downloaded binary or installer — `curl | bash` has no integrity check
  at all.

---

## 7. Fast audit

```bash
python3 scripts/viora.py deps --path . --online --json .viora/deps.json

trivy fs --scanners vuln,secret,misconfig .
trivy image --severity HIGH,CRITICAL myapp:1.2.3
checkov -d infra/
hadolint Dockerfile
osv-scanner -r .
syft . -o cyclonedx-json > sbom.json
```

Merge everything into one report:

```bash
python3 scripts/viora.py report --in .viora --out SECURITY_REPORT.md
```
