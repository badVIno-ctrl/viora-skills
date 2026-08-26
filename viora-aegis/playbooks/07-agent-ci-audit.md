# Playbook 07 - CI-AUDIT (pipelines and agentic CI)

**Goal:** find the paths by which an outsider can make your CI run their code, or
make an AI agent in your CI act on their instructions - with your credentials.

```bash
python3 scripts/viora.py plan ci-audit
python3 scripts/viora.py ci-audit
```

---

## The threat in one sentence

CI has credentials and write access. If untrusted input can influence what CI
executes - or what an agent in CI decides to do - the attacker inherits those
credentials without ever touching your infrastructure.

When an LLM agent runs in CI, **the agent is a sink** (Law 1: every token an LLM
reads is untrusted input, and every token it emits is untrusted output). A PR
title is attacker-controlled text. If it reaches the agent's prompt and the agent
can run tools, you have injection into a credentialed shell.

---

## Steps

1. **Enumerate the pipelines.**
   ```bash
   python3 scripts/viora.py ci-audit --format markdown --out ci-audit.md
   ```
   Covers `.github/workflows`, `action.yml`, Gitea/Forgejo, GitLab CI, Travis,
   Azure Pipelines, Jenkinsfile, Bitbucket, CircleCI, Cloud Build, Drone.

2. **For each workflow, record these nine facts.** The scanner prints them; your
   job is to confirm and interpret. The combination is the vulnerability - no
   single fact is:

   1. **Trigger** - and whether it is privileged. `pull_request_target`,
      `issue_comment`, `workflow_run`, `issues` all run with **write** access and
      secrets, on content from a fork.
   2. **Untrusted expressions** - any `${{ github.event.* }}` carrying attacker
      text: PR title, body, branch name, comment body, author name.
   3. **Agent present** - an LLM action, CLI or SDK invoked in a step.
   4. **Secrets referenced** - `secrets.*`, cloud OIDC, registry tokens.
   5. **Write permissions** - `permissions:` at workflow or job level.
   6. **PR-head checkout** - `ref: ${{ github.event.pull_request.head.sha }}`
      inside a privileged trigger. This is checking out the attacker's code.
   7. **Actor guard** - a condition restricting who can trigger it
      (`author_association`, an allowlist, `github.actor`).
   8. **Self-hosted runner** - `runs-on: self-hosted`, reachable from a fork.
   9. **Tool grants** - what the agent is allowed to do. `Bash(*)`,
      `--dangerously-skip-permissions`, `--yolo`, `danger-full-access`.

3. **Assemble the chains. Report chains before individual findings** - a chain is
   the actual vulnerability, and it is what makes the severity real:

   | Chain | Composition | Severity |
   |---|---|---|
   | **Untrusted code + credentials** | privileged trigger + PR-head checkout + secrets or write perms | critical |
   | **Injection into a credentialed agent** | untrusted expression -> agent prompt + agent has tools + secrets | critical |
   | **Agent reachable by anyone** | privileged trigger + no actor guard + agent + write perms | critical |
   | **Unrestricted agent tools** | agent + wildcard tool grant or permission-skip flag | high |
   | **Privileged trigger, no guard** | privileged trigger + no actor guard | high |
   | **Fork-reachable self-hosted runner** | fork trigger + self-hosted | high |
   | **Uncredentialed agent** | agent, no secrets, no write perms | info - confirm the token is read-only |

4. **Check the safe-pattern boundary.** The correct structure for handling fork
   contributions is two jobs:
   - Job A: `pull_request` trigger, no secrets, `permissions: contents: read`.
     Builds and tests the untrusted code. Uploads an artifact.
   - Job B: `workflow_run`, has secrets, **never checks out the PR head**. Only
     consumes the artifact, and treats its contents as untrusted data.

   If a single job both checks out fork code and holds secrets, that is the
   finding regardless of anything else.

5. **Check the agent's blast radius**, if one is present:
   - Which tools can it call? Is the grant an allowlist or a wildcard?
   - Can it write to the repo, push, comment, or approve?
   - Can it reach the network, and can it be steered by untrusted text?
   - Is its output used in a later step **without validation**? Law 1: agent
     output is untrusted input to the next step.
   - Is there a spend or step bound? Law 9.

6. **Check pinning.** Third-party actions pinned to a mutable tag (`@v4`) are
   unpinned dependencies with write access to your pipeline. Require a commit
   SHA. `@main` is the worst case.

7. **Check the secret hygiene.** Secrets echoed, printed, written to a file,
   passed as a CLI argument (visible in `ps`), or dumped via `env`. `echo
   $(env)` in a credentialed job is exfiltration.

---

## Rationalisations to reject

| Excuse | Why it fails |
|---|---|
| "Only maintainers can trigger it." | Show the guard. `pull_request_target` fires for **any** fork PR by default. |
| "The agent only reads." | Read + network = exfiltration. And check what its output feeds. |
| "The token is scoped." | Name the scopes. `GITHUB_TOKEN` with `contents: write` can push. |
| "It's just a linter." | It runs code from the PR. That is arbitrary execution. |
| "The prompt tells it not to." | A prompt is not a permission boundary. |
| "It needs a fork PR to exploit." | Anyone can open a fork PR. That is the feature. |

---

## Hard stops

- Do not run a workflow to test it. Read it.
- Do not add or widen `permissions:` as a fix without saying what it grants.
- Do not report `pull_request` (unprivileged) as if it were
  `pull_request_target`. The difference is the entire finding.

---

## Output

Chains first, then individual leads, each in the fixed finding shape. Then:

```
Workflows assessed: N   agentic: N
Not assessed:       <reusable workflows, called actions, container images>
```

Reusable workflows (`uses: ./.github/workflows/x.yml`) and composite actions
contain steps you have not read. Either follow them or list them as not assessed.
