# Viora Aegis — reference index

Load **one** file, do the work, come back. Do not chain-load: the skill body (`SKILL.md`) already
contains the method; these files exist so you never have to guess a detail.

| File | Contents | Load when |
|---|---|---|
| `01-threat-model.md` | STRIDE worksheet, trust boundaries, abuse cases, data classification | DESIGN mode, new feature, greenfield project |
| `02-owasp-top10-2025.md` | A01–A10:2025 with detection questions and required controls, ASVS 5.0 anchors | You need canonical wording, IDs, or a systematic sweep |
| `03-language-playbooks.md` | Per-language footguns and safe APIs: JS/TS, Python, PHP, Java, C#, Go, Ruby, Rust, C/C++, Kotlin, Swift, SQL, shell, IaC | Working in a language whose traps you must not miss |
| `04-ai-agent-security.md` | LLM01–LLM10 (2025), agentic ASI risks, MCP, RAG, memory, tool permissions, CI bots | Any LLM, agent, RAG, MCP or AI-in-CI code |
| `05-secure-patterns.md` | Copy-ready secure implementations per framework: authn, authz, sessions, uploads, SSRF guard, headers, rate limits, crypto | You are writing the actual patch |
| `06-supply-chain.md` | Dependencies, lockfiles, install scripts, CI/CD, Docker, IaC, artifact integrity | Reviewing deps, pipelines, containers, infra |
| `07-triage-and-severity.md` | Verification protocol, evidence standards, severity calculus, variant analysis, writing the verdict | A finding is contested, complex, or needs to be defensible |
| `08-toolchain.md` | Semgrep, gitleaks, trivy, bandit, osv-scanner, ZAP, CodeQL — exact commands and how to read output | Pro tooling is installed and you want depth |
| `09-checklists.md` | Pre-commit, pre-deploy, release sign-off, incident response, new-project baseline | You need a gate, not an essay |

## Rule IDs

Every scanner rule maps to this taxonomy. Use the ID in reports so findings are greppable.

| Prefix | Domain |
|---|---|
| `INJ-` | Injection: SQL, NoSQL, command, code, template, LDAP, XXE |
| `XSS-` | Cross-site scripting, unsafe rendering, open redirect |
| `AUTH-` | Authentication, session, access control, JWT |
| `CRYPTO-` | Hashing, ciphers, TLS, randomness, key material |
| `SECRET-` | Hardcoded credentials, tokens, keys, entropy hits |
| `DEFAULT-` | Insecure defaults, fail-open, debug, CORS, wildcards |
| `SSRF-` | Server-side request forgery |
| `PATH-` | Traversal, uploads, archive extraction |
| `DESER-` | Unsafe deserialization |
| `AI-` | LLM and agent-specific risks |
| `SUPPLY-` | CI/CD, actions, remote scripts, artifact integrity |
| `CONTAINER-` | Docker, Kubernetes, cloud misconfiguration |
| `DOS-` | Rate limits, ReDoS, unbounded resources |
| `LOG-` | Logging, error handling, information exposure |
| `DEP-` | Dependency and lockfile findings (`viora deps`) |
| `HDR-` | Live header, cookie, CORS findings (`viora headers`) |
| `PROJ-` | Repository-level hygiene |
