#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""viora_ciaudit - audit CI/CD pipelines, focused on AI agents in CI.

The question: can an outsider make your pipeline run their code, or make your
agent act on their instructions, in a job that holds credentials?

No single fact is the vulnerability. The COMBINATION is. So this engine
extracts nine facts per workflow, then assembles named chains from them.
A chain is a finding; a fact alone is only a lead.

Zero dependencies. Python 3.8+.
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)

SEVERITIES = ["info", "low", "medium", "high", "critical"]
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", "vendor", "target", ".next", ".mypy_cache"}
MAX_FILE_BYTES = 1024 * 1024

WORKFLOW_DIRS = (".github/workflows", ".gitea/workflows", ".forgejo/workflows")

CI_FILENAMES = re.compile(
    r"(?:^|/)(?:\.gitlab-ci\.ya?ml|\.travis\.ya?ml"
    r"|azure-pipelines(?:\.[\w.-]+)?\.ya?ml|Jenkinsfile[\w.-]*"
    r"|bitbucket-pipelines\.ya?ml|\.circleci/config\.ya?ml|cloudbuild\.ya?ml"
    r"|buildspec(?:\.[\w.-]+)?\.ya?ml|\.drone\.ya?ml|action\.ya?ml"
    r"|dagger\.ya?ml|\.woodpecker\.ya?ml|appveyor\.ya?ml)$", re.I)

# ---- the nine fact detectors ---------------------------------------------

PRIVILEGED_TRIGGER = re.compile(
    r"^\s*(?:-\s*)?(pull_request_target|issue_comment|issues|workflow_run"
    r"|discussion_comment|pull_request_review_comment|pull_request_review)"
    r"\s*:?\s*$", re.M)

UNTRUSTED_EXPR = re.compile(
    r"\$\{\{\s*(?:github\.event\.(?:issue|comment|pull_request|discussion"
    r"|review|head_commit|commits|inputs)[\w.\[\]'\"]*"
    r"|github\.head_ref|github\.ref_name|github\.actor|github\.triggering_actor"
    r"|inputs\.[\w.]+)\s*\}\}")

AGENT_MARKERS = re.compile(
    r"(?i)(?:anthropics/claude-code-action|claude-code|openai/codex"
    r"|codex\s+exec|github/copilot|copilot-agent|gemini-cli|aider"
    r"|cursor-agent|opencode|goose\s+run|sweep-ai|devin"
    r"|ANTHROPIC_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|GOOGLE_API_KEY"
    r"|llm\s+-m\b|ollama\s+run)")

SECRET_REF = re.compile(r"\$\{\{\s*secrets\.[\w.]+\s*\}\}|\bsecrets\.[A-Z_]{3,}")

OIDC_REF = re.compile(r"(?i)id-token\s*:\s*write|configure-aws-credentials"
                      r"|azure/login|google-github-actions/auth")

WRITE_PERMS = re.compile(
    r"(?i)(?:contents|pull-requests|issues|packages|id-token|deployments"
    r"|actions|checks|statuses)\s*:\s*write|permissions\s*:\s*write-all")

PR_HEAD_CHECKOUT = re.compile(
    r"(?i)ref\s*:\s*\$\{\{\s*github\.event\.pull_request\.head\.(?:sha|ref)"
    r"|ref\s*:\s*\$\{\{\s*github\.head_ref"
    r"|ref\s*:\s*refs/pull/.*?/(?:head|merge)"
    r"|gh\s+pr\s+checkout")

AUTHOR_GUARD = re.compile(
    r"(?i)(?:author_association|github\.event\.comment\.user\.login"
    r"|github\.actor\s*==|user\.login\s*==|author_association|OWNER|COLLABORATOR|MEMBER"
    r"|environment\s*:|permission-check|check-permissions"
    r"|contains\s*\(\s*fromJSON)")

SELF_HOSTED = re.compile(r"(?i)runs-on\s*:.*self-hosted|labels\s*:.*self-hosted")

WILDCARD_TOOLS = re.compile(
    r"(?i)(?:allowed[_-]?tools\s*:.*\*|Bash\s*\(\s*\*\s*\)"
    r"|(?:--)?dangerously[_-]?skip[_-]?permissions|--yolo|danger-full-access"
    r"|--allow-all|--full-auto|approval[_-]?mode\s*:\s*never"
    r"|permission[_-]?mode\s*:\s*(?:accept|bypass))")

UNPINNED_ACTION = re.compile(r"uses\s*:\s*([\w.-]+/[\w.\-/]+)@([\w.\-/]+)")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
FIRST_PARTY = re.compile(r"^(?:actions|github|docker|advanced-security)/")

SECRET_LEAK = re.compile(
    r"(?i)(?:echo|printf|print|cat|curl[^\n]*-d)\s[^\n]*\$\{\{\s*secrets\."
    r"|\becho\s+\$\(\s*env\s*\)|\benv\s*\|\s*(?:sort|base64|curl)"
    r"|printenv[^\n]*\|")


def _find_ci_files(root):
    out = []
    for wd in WORKFLOW_DIRS:
        d = os.path.join(root, wd)
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if name.lower().endswith((".yml", ".yaml")):
                    out.append((os.path.join(d, name), wd + "/" + name))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(x for x in dirnames if x not in SKIP_DIRS)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if any(rel.startswith(w + "/") for w in WORKFLOW_DIRS):
                continue
            if CI_FILENAMES.search("/" + rel):
                out.append((full, rel))
    seen, uniq = set(), []
    for full, rel in out:
        if rel not in seen:
            seen.add(rel)
            uniq.append((full, rel))
    return uniq


def _read(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _lines_matching(rx, text, limit=6):
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if rx.search(line):
            ev = line.strip()
            hits.append({"line": i, "evidence": ev[:180]})
            if len(hits) >= limit:
                break
    return hits


def _context(text, rel):
    """Extract the nine facts. Facts, not verdicts."""
    trig = [m.group(1) for m in PRIVILEGED_TRIGGER.finditer(text)]
    unpinned = []
    for m in UNPINNED_ACTION.finditer(text):
        repo, ref = m.group(1), m.group(2)
        if FIRST_PARTY.match(repo):
            continue
        if not SHA40.match(ref):
            unpinned.append("%s@%s" % (repo, ref))
    return {
        "file": rel,
        "privileged_trigger": sorted(set(trig)),
        "untrusted_expr": _lines_matching(UNTRUSTED_EXPR, text),
        "agent": _lines_matching(AGENT_MARKERS, text, limit=4),
        "secrets": _lines_matching(SECRET_REF, text, limit=4),
        "oidc": bool(OIDC_REF.search(text)),
        "write_perms": _lines_matching(WRITE_PERMS, text, limit=4),
        "pr_head_checkout": _lines_matching(PR_HEAD_CHECKOUT, text, limit=3),
        "author_guard": bool(AUTHOR_GUARD.search(text)),
        "self_hosted": bool(SELF_HOSTED.search(text)),
        "wildcard_tools": _lines_matching(WILDCARD_TOOLS, text, limit=3),
        "secret_leak": _lines_matching(SECRET_LEAK, text, limit=3),
        "unpinned": sorted(set(unpinned))[:12],
    }


def _chains(ctx):
    """Assemble the named chains. This is where the findings actually are."""
    out = []
    f = ctx["file"]
    priv = bool(ctx["privileged_trigger"])
    creds = bool(ctx["secrets"]) or ctx["oidc"]
    agent = bool(ctx["agent"])
    untrusted = bool(ctx["untrusted_expr"])
    guard = ctx["author_guard"]

    def add(sev, name, why, fix):
        out.append({"severity": sev, "chain": name, "file": f,
                    "why": why, "fix": fix})

    # 1. untrusted code executed in a credentialed job
    if ctx["pr_head_checkout"] and creds and priv:
        add("critical", "Untrusted code runs with base-repo credentials",
            "A privileged trigger (%s) checks out pull-request head code AND the "
            "job can reach secrets. Anyone who opens a PR can run code with your "
            "credentials." % ", ".join(ctx["privileged_trigger"]),
            "Split into two jobs: an unprivileged `pull_request` job with NO "
            "secrets that builds and uploads an artifact, and a `workflow_run` "
            "job that holds the secrets and never checks out the head.")

    # 2. prompt injection into a credentialed agent
    if agent and untrusted and creds:
        add("critical", "Untrusted text reaches a credentialed agent",
            "Attacker-controlled fields (issue/comment/PR text or branch names) "
            "are interpolated in the same workflow as an AI agent that has "
            "credentials. Assume the injection succeeds and count what the agent "
            "can then do.",
            "Never interpolate event text into a prompt or a run block. Pass it "
            "via env and read it as DATA, keep the agent's tool grant on an "
            "allowlist, and remove credentials from the agent job.")

    # 3. agent reachable by any outsider, holding credentials
    if agent and priv and not guard and creds:
        add("high", "Agent is reachable by any outside actor",
            "A privileged trigger can start an agent job that holds credentials, "
            "and no author or environment guard was found. Anyone who can file an "
            "issue or comment can start it.",
            "Gate on author_association / an allowlist / a protected "
            "`environment:` requiring approval, before the agent step runs.")

    # 4. unrestricted agent tools
    if agent and ctx["wildcard_tools"]:
        add("high", "Agent runs with unrestricted tools",
            "The agent is granted wildcard tools or has its permission prompts "
            "disabled. Any successful injection inherits the full grant "
            "(Law 8).",
            "Replace the wildcard with an explicit allowlist of the specific "
            "commands the job actually needs.")

    # 5. privileged trigger with no actor guard
    if priv and not guard and not agent:
        add("medium", "Privileged trigger with no actor guard",
            "Trigger(s) %s run with base-repo context, and no author or "
            "environment check was found." % ", ".join(ctx["privileged_trigger"]),
            "Add an author_association or allowlist condition, or move the "
            "privileged work behind `workflow_run`.")

    # 6. fork-reachable self-hosted runner
    if ctx["self_hosted"] and (priv or ctx["pr_head_checkout"]):
        add("high", "Fork-reachable self-hosted runner",
            "A self-hosted runner is reachable by outside code. Self-hosted "
            "runners are not ephemeral by default: the attacker gets persistence "
            "on your machine and whatever that machine can reach.",
            "Use ephemeral runners for anything fork-reachable, or restrict this "
            "workflow to trusted branches only.")

    # 7. informational: an agent job with no visible credentials
    if agent and not creds:
        add("info", "Agent job appears uncredentialed",
            "An agent runs here but no secret reference or OIDC grant was found. "
            "That is the safer shape - confirm the token really is scoped "
            "read-only, including the default GITHUB_TOKEN.",
            "Keep it that way: `permissions: contents: read` at the top level.")

    # secret hygiene is per-file, not a chain, but belongs in the same report
    if ctx["secret_leak"]:
        add("high", "Secret may be printed or exported",
            "A secret or the whole environment appears in an echo, print, cat or "
            "outbound request. Log output is retained and often world-readable.",
            "Never echo a secret. Pass it through env to the process that needs "
            "it and never through a shell argument or a log line.")

    return out


def audit(root="."):
    files = _find_ci_files(root)
    contexts, chains, unread = [], [], []
    for full, rel in files:
        text = _read(full)
        if text is None:
            unread.append(rel)
            continue
        ctx = _context(text, rel)
        contexts.append(ctx)
        chains.extend(_chains(ctx))

    findings = []
    for ctx in contexts:
        for u in ctx["unpinned"]:
            findings.append({
                "id": "CI-PIN-001", "severity": "medium",
                "title": "Third-party action is not pinned to a commit SHA",
                "file": ctx["file"], "evidence": u,
                "fp": "A tag you control in your own org is lower risk - say so.",
                "fix": "Pin to a full 40-character commit SHA and record the "
                       "version in a comment."})
        for h in ctx["untrusted_expr"]:
            findings.append({
                "id": "CI-EXPR-001", "severity": "high",
                "title": "Attacker-controlled expression interpolated into the workflow",
                "file": ctx["file"], "line": h["line"], "evidence": h["evidence"],
                "fp": "If it is only used as a step name or label, impact is low.",
                "fix": "Assign it to an env var and reference \"$VAR\" quoted, so "
                       "the value is never expanded into the script text."})
        if not ctx["author_guard"] and ctx["privileged_trigger"]:
            findings.append({
                "id": "CI-CHK-002", "severity": "medium",
                "title": "No actor or environment guard on a privileged trigger",
                "file": ctx["file"], "evidence": ", ".join(ctx["privileged_trigger"]),
                "fp": "A guard implemented in a called reusable workflow will not "
                      "be visible here - follow the call before reporting.",
                "fix": "Require OWNER/MEMBER/COLLABORATOR, an allowlist, or a "
                       "protected environment with required reviewers."})

    chains.sort(key=lambda c: -SEV_RANK[c["severity"]])
    findings.sort(key=lambda f: (-SEV_RANK[f["severity"]], f["file"]))
    counts = {s: 0 for s in SEVERITIES}
    for x in chains + findings:
        counts[x["severity"]] += 1

    return {
        "root": os.path.abspath(root),
        "workflows": len(contexts),
        "unread": unread,
        "agentic": sum(1 for c in contexts if c["agent"]),
        "contexts": contexts,
        "chains": chains,
        "findings": findings,
        "counts": counts,
    }


def render_text(r):
    L = []
    L.append("VIORA AEGIS - CI-AUDIT (static; no workflow was executed)")
    L.append("=" * 76)
    L.append("root:      %s" % r["root"])
    L.append("workflows: %d   agentic: %d   findings: %d   chains: %d"
             % (r["workflows"], r["agentic"], len(r["findings"]), len(r["chains"])))
    c = r["counts"]
    L.append("severity:  critical=%d high=%d medium=%d low=%d info=%d"
             % (c["critical"], c["high"], c["medium"], c["low"], c["info"]))
    if r["unread"]:
        L.append("unread:    %s" % ", ".join(r["unread"]))
    L.append("")

    if not r["contexts"]:
        L.append("No pipeline definition found. That is a fact, not a clean")
        L.append("verdict - say 'no CI found' rather than 'CI is secure'.")
        return "\n".join(L)

    L.append("-- THE NINE FACTS PER WORKFLOW " + "-" * 45)
    for ctx in r["contexts"]:
        L.append("")
        L.append("  %s" % ctx["file"])
        L.append("    1 privileged trigger : %s"
                 % (", ".join(ctx["privileged_trigger"]) or "no"))
        L.append("    2 untrusted exprs    : %d" % len(ctx["untrusted_expr"]))
        L.append("    3 agent present      : %s"
                 % ("yes" if ctx["agent"] else "no"))
        L.append("    4 credentials        : %s"
                 % ("yes" if (ctx["secrets"] or ctx["oidc"]) else "none found"))
        L.append("    5 write permissions  : %s"
                 % ("yes" if ctx["write_perms"] else "none found"))
        L.append("    6 PR head checkout   : %s"
                 % ("yes" if ctx["pr_head_checkout"] else "no"))
        L.append("    7 actor guard        : %s"
                 % ("yes" if ctx["author_guard"] else "NOT FOUND"))
        L.append("    8 self-hosted runner : %s"
                 % ("yes" if ctx["self_hosted"] else "no"))
        L.append("    9 tool grant         : %s"
                 % ("WILDCARD" if ctx["wildcard_tools"] else "none found"))
    L.append("")

    L.append("-- CHAINS (report these FIRST - the chain is the finding) " + "-" * 19)
    if not r["chains"]:
        L.append("  none assembled")
    for ch in r["chains"]:
        L.append("")
        L.append("  [%-8s] %s" % (ch["severity"].upper(), ch["chain"]))
        L.append("    file: %s" % ch["file"])
        L.append("    why:  %s" % ch["why"])
        L.append("    fix:  %s" % ch["fix"])
    L.append("")

    L.append("-- LEADS (verify each before reporting) " + "-" * 36)
    if not r["findings"]:
        L.append("  none")
    for f in r["findings"][:120]:
        L.append("")
        L.append("  [%-8s] %-12s %s" % (f["severity"].upper(), f["id"], f["title"]))
        loc = "%s:%s" % (f["file"], f.get("line", "?"))
        L.append("    %s" % loc)
        L.append("    | %s" % f["evidence"])
        L.append("    fp:  %s" % f["fp"])
        L.append("    fix: %s" % f["fix"])
    L.append("")
    L.append("Now follow: python3 scripts/viora.py plan ci-audit")
    L.append("List any reusable workflow or called action you did not follow.")
    return "\n".join(L)


def render_markdown(r):
    c = r["counts"]
    L = ["# CI/CD audit", "", "**No workflow was executed.**", ""]
    L.append("| | |")
    L.append("|---|---|")
    L.append("| Root | `%s` |" % r["root"])
    L.append("| Workflows | %d |" % r["workflows"])
    L.append("| With an AI agent | %d |" % r["agentic"])
    L.append("| Chains | %d |" % len(r["chains"]))
    L.append("| Critical / High / Medium | %d / %d / %d |"
             % (c["critical"], c["high"], c["medium"]))
    L.append("")
    L.append("## Facts per workflow")
    L.append("")
    L.append("| Workflow | Priv. trigger | Untrusted | Agent | Creds | Write | "
             "PR head | Guard | Self-hosted | Tools |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for x in r["contexts"]:
        L.append("| `%s` | %s | %d | %s | %s | %s | %s | %s | %s | %s |" % (
            x["file"], ", ".join(x["privileged_trigger"]) or "-",
            len(x["untrusted_expr"]), "yes" if x["agent"] else "-",
            "yes" if (x["secrets"] or x["oidc"]) else "-",
            "yes" if x["write_perms"] else "-",
            "yes" if x["pr_head_checkout"] else "-",
            "yes" if x["author_guard"] else "**NOT FOUND**",
            "yes" if x["self_hosted"] else "-",
            "**WILDCARD**" if x["wildcard_tools"] else "-"))
    L.append("")
    L.append("## Chains - report these first")
    L.append("")
    if not r["chains"]:
        L.append("None assembled.")
    for ch in r["chains"]:
        L.append("### %s - %s" % (ch["severity"].upper(), ch["chain"]))
        L.append("")
        L.append("- **Where:** `%s`" % ch["file"])
        L.append("- **Why:** %s" % ch["why"])
        L.append("- **Fix:** %s" % ch["fix"])
        L.append("")
    L.append("## Leads")
    L.append("")
    L.append("| Sev | Rule | Where | Evidence |")
    L.append("|---|---|---|---|")
    for f in r["findings"][:120]:
        ev = f["evidence"].replace("|", "\\|")[:100]
        L.append("| %s | %s | `%s:%s` | `%s` |"
                 % (f["severity"], f["id"], f["file"], f.get("line", "?"), ev))
    return "\n".join(L)


def run(args=None, **kw):
    """Accept an argparse.Namespace from viora.py, or plain keyword args.

    viora.py dispatches every subcommand as eng.run(args), so the namespace form
    is the primary one. The keyword form keeps the module usable standalone.
    """
    def g(name, default=None):
        if args is not None and not isinstance(args, str) and hasattr(args, name):
            v = getattr(args, name)
            if v is not None:
                return v
        return kw.get(name, default)

    root = g("path", kw.get("root", "."))
    if isinstance(args, str):
        root = args
    fmt = g("format", kw.get("fmt", "text"))
    out = g("out")
    fail_on = g("fail_on", "none") or "none"

    if not os.path.isdir(root):
        sys.stderr.write("! not a directory: %s\n" % root)
        return 2
    r = audit(root)
    if fmt == "json":
        text = json.dumps(r, indent=2, ensure_ascii=False)
    elif fmt == "markdown":
        text = render_markdown(r)
    else:
        text = render_text(r)

    if out:
        d = os.path.dirname(os.path.abspath(out))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("wrote %s" % out)
    else:
        print(text)

    if fail_on and fail_on != "none":
        gate = SEV_RANK.get(fail_on, 3)
        if any(SEV_RANK[x["severity"]] >= gate
               for x in r["chains"] + r["findings"]):
            return 1
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(run(root=(a[0] if a and not a[0].startswith("-") else "."),
                 fmt=("json" if "--json" in a else "text")))
