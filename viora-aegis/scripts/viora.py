#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viora Aegis - portable defensive security engine.

Zero dependencies. Python 3.8+. Runs anywhere a coding agent runs.

  viora.py doctor    [--path .]
  viora.py scan      [--path .] [--diff REF] [--only ID|CAT] [--severity low]
                     [--fail-on high] [--format text|json|sarif|markdown]
                     [--staged] [--out FILE] [--json FILE] [--baseline [FILE]] [--quiet]
  viora.py deps      [--path .] [--online] [--json FILE]
  viora.py headers   URL [--json FILE] [--timeout 10]
  viora.py baseline  [--path .] [--out .viora/baseline.json]
  viora.py report    [--in .viora] [--out SECURITY_REPORT.md] [--title "..."]
  viora.py init      [--path .] [--ci github|gitlab|none] [--hook]

Exit codes: 0 = clean / under threshold, 1 = gate breached, 2 = execution error.
"""
from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

__version__ = "1.0.0"
BRAND = "Viora Aegis"

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)

SEVERITIES = ["info", "low", "medium", "high", "critical"]
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", "vendor", "venv",
    ".venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".output", "target",
    "coverage", ".coverage", ".nyc_output", ".gradle", ".idea", ".vscode",
    ".terraform", ".serverless", ".cache", ".parcel-cache", "Pods", "DerivedData",
    ".viora", ".tox", ".eggs", "site-packages", ".turbo", ".yarn",
}
SKIP_FILE_PATTERNS = [
    "*.min.js", "*.min.css", "*.map", "*.lock", "*.snap", "*.svg", "*.ico",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.avif", "*.pdf", "*.zip",
    "*.gz", "*.tar", "*.7z", "*.rar", "*.jar", "*.war", "*.class", "*.pyc",
    "*.so", "*.dll", "*.dylib", "*.exe", "*.bin", "*.wasm", "*.woff", "*.woff2",
    "*.ttf", "*.eot", "*.mp4", "*.mp3", "*.mov", "*.pack", "*.bundle.js",
]
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LINE_LEN = 4000

TEST_HINT = re.compile(
    r"(^|[/\\_.-])(tests?|spec|specs|__tests__|__mocks__|fixtures?|examples?|"
    r"samples?|demo|mocks?|e2e|cypress|playwright|stories)([/\\_.-]|$)", re.I)
DOC_HINT = re.compile(r"\.(md|mdx|rst|txt|adoc)$", re.I)
SUPPRESS = re.compile(r"(viora-ignore|nosec|noqa:\s*S\d|semgrep:\s*ignore|eslint-disable.*security)", re.I)

# --------------------------------------------------------------------------
# tiny console helpers
# --------------------------------------------------------------------------
_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(text, code):
    return "\033[%sm%s\033[0m" % (code, text) if _COLOR else text


SEV_COLOR = {"critical": "1;91", "high": "91", "medium": "93", "low": "96", "info": "90"}


def sev_tag(sev):
    return c(sev.upper().ljust(8), SEV_COLOR.get(sev, "0"))


def eprint(*a):
    print(*a, file=sys.stderr)


# --------------------------------------------------------------------------
# config / rules
# --------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "failOn": "high",
    "minSeverity": "low",
    "exclude": [],
    "disabledRules": [],
    "severityOverrides": {},
    "secretsEntropy": True,
    "downgradeTests": True,
}


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except Exception:
        return default


def load_config(root):
    cfg = dict(DEFAULT_CONFIG)
    for name in ("viora.config.json", ".viora.json", os.path.join(".viora", "config.json")):
        data = load_json(os.path.join(root, name))
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
            break
    return cfg


def load_rules():
    rules, meta = [], {}
    for fname in ("patterns.json", "secrets.json"):
        data = load_json(os.path.join(PACK, "rules", fname))
        if not data:
            continue
        meta.setdefault("categories", {}).update(data.get("categories", {}))
        for r in data.get("rules", []):
            try:
                r["_re"] = re.compile(r["pattern"])
            except re.error as exc:
                eprint("! rule %s has an invalid pattern: %s" % (r.get("id"), exc))
                continue
            if r.get("exclude_line"):
                try:
                    r["_ex"] = re.compile(r["exclude_line"])
                except re.error:
                    r["_ex"] = None
            rules.append(r)
    return rules, meta


# --------------------------------------------------------------------------
# file walking
# --------------------------------------------------------------------------
def should_skip_file(rel, extra_excludes):
    base = os.path.basename(rel)
    for pat in SKIP_FILE_PATTERNS:
        if fnmatch.fnmatch(base, pat):
            return True
    for pat in extra_excludes or []:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def walk_files(root, extra_excludes=None):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".viora")]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if should_skip_file(rel, extra_excludes):
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield rel, full


def read_text(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    return raw.decode("utf-8", errors="replace")


def rule_matches_path(rule, rel):
    inc = rule.get("include")
    if not inc:
        return True
    base = os.path.basename(rel)
    for pat in inc:
        if "/" in pat:
            if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, "*/" + pat):
                return True
        elif fnmatch.fnmatch(base, pat):
            return True
    return False


# --------------------------------------------------------------------------
# secrets: entropy pass
# --------------------------------------------------------------------------
ENTROPY_ASSIGN = re.compile(
    r"(?i)\b([\w.\-]*(secret|token|password|passwd|api[_-]?key|apikey|access[_-]?key"
    r"|private[_-]?key|client[_-]?secret|auth|credential)[\w.\-]*)\s*[:=]\s*"
    r"['\"]([A-Za-z0-9+/=_\-\.]{16,})['\"]")
PLACEHOLDER = re.compile(
    r"(?i)(example|sample|placeholder|dummy|change[_-]?me|your[_-]?|xxx+|\.\.\.|<[^>]+>|"
    r"\{\{|\$\{|test|fake|redact|todo|null|none|undefined|password123|s3cr3t|"
    r"lorem|abcdef123|0{8,}|1234567)")


def shannon(s):
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = float(len(s))
    return -sum((v / n) * math.log(v / n, 2) for v in counts.values())


def entropy_findings(rel, text):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if len(line) > MAX_LINE_LEN or SUPPRESS.search(line):
            continue
        m = ENTROPY_ASSIGN.search(line)
        if not m:
            continue
        name, value = m.group(1), m.group(3)
        if PLACEHOLDER.search(value) or PLACEHOLDER.search(name):
            continue
        ent = shannon(value)
        if ent < 3.6 or len(set(value)) < 8:
            continue
        out.append(dict(
            rule="SECRET-900", title="High-entropy value assigned to a credential-like name",
            category="SECRET", severity="high", confidence="medium",
            owasp="A04:2025 Cryptographic Failures", cwe="CWE-798",
            file=rel, line=i, snippet=redact(line.strip()),
            fix="Move to env/vault, rotate the value, purge it from git history, add a pre-commit secret gate.",
            meta={"entropy": round(ent, 2), "name": name},
        ))
    return out


def redact(line):
    line = line[:220]
    def _r(m):
        v = m.group(3)
        keep = 4 if len(v) > 12 else 0
        return "%s%s'%s%s'" % (m.group(0).split("=")[0].split(":")[0], "=" if "=" in m.group(0) else ":",
                               v[:keep], "*" * 8)
    return ENTROPY_ASSIGN.sub(_r, line)


# --------------------------------------------------------------------------
# git diff support
# --------------------------------------------------------------------------
def git(root, *args):
    try:
        p = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True, timeout=60)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


def changed_lines(root, ref):
    """Return {relpath: set(line numbers added)} for the diff against ref.

    ref == "--staged" diffs the git index (what `git add` has queued).
    """
    if ref == "--staged":
        out = git(root, "diff", "--cached", "--unified=0", "--no-color", "--")
        if not out.strip():
            out = git(root, "diff", "--unified=0", "--no-color", "--")
    else:
        out = git(root, "diff", "--unified=0", "--no-color", ref, "--")
        if not out.strip():
            out = git(root, "diff", "--unified=0", "--no-color", ref + "...HEAD", "--")
    result, cur = {}, None
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:].strip()
            result.setdefault(cur, set())
        elif line.startswith("@@") and cur:
            m = hunk.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2) or 1)
                for n in range(start, start + max(count, 1)):
                    result[cur].add(n)
    return {k: v for k, v in result.items() if v}


# --------------------------------------------------------------------------
# scanning
# --------------------------------------------------------------------------
def fingerprint(f):
    norm = re.sub(r"\s+", " ", f.get("snippet", "")).strip()
    h = hashlib.sha256(("%s|%s|%s" % (f["rule"], f["file"], norm)).encode("utf-8")).hexdigest()
    return h[:16]


def scan_project(root, cfg, only=None, diff_ref=None):
    rules, meta = load_rules()
    if not rules:
        eprint("! no rules loaded - expected %s/rules/patterns.json" % PACK)
    disabled = set(cfg.get("disabledRules") or [])
    only_set = set(x.strip().upper() for x in only.split(",")) if only else None
    limit = changed_lines(root, diff_ref) if diff_ref else None
    if diff_ref and not limit:
        where = "the git index" if diff_ref == "--staged" else diff_ref
        eprint("! no diff against %s (not a git repo, or nothing changed) - scanning everything" % where)
        limit = None

    findings, scanned = [], 0
    for rel, full in walk_files(root, cfg.get("exclude")):
        if limit is not None and rel not in limit:
            continue
        text = read_text(full)
        if text is None:
            continue
        scanned += 1
        lines = text.splitlines()
        is_test = bool(TEST_HINT.search(rel))
        is_doc = bool(DOC_HINT.search(rel))

        for rule in rules:
            rid = rule["id"]
            if rid in disabled:
                continue
            if only_set and rid.upper() not in only_set and rule["category"].upper() not in only_set:
                continue
            if not rule_matches_path(rule, rel):
                continue
            for i, line in enumerate(lines, 1):
                if limit is not None and i not in limit.get(rel, ()):
                    continue
                if len(line) > MAX_LINE_LEN or SUPPRESS.search(line):
                    continue
                if not rule["_re"].search(line):
                    continue
                ex = rule.get("_ex")
                if ex and ex.search(line):
                    continue
                sev = cfg.get("severityOverrides", {}).get(rid, rule["severity"])
                conf = rule.get("confidence", "medium")
                if (is_test or is_doc) and cfg.get("downgradeTests", True):
                    sev = SEVERITIES[max(0, SEV_RANK[sev] - 2)]
                    conf = "low"
                findings.append(dict(
                    rule=rid, title=rule["title"], category=rule["category"],
                    severity=sev, confidence=conf, owasp=rule.get("owasp", ""),
                    cwe=rule.get("cwe", ""), file=rel, line=i,
                    snippet=redact(line.strip()), fix=rule.get("fix", ""),
                    meta={"test_context": is_test or is_doc},
                ))
        if cfg.get("secretsEntropy", True) and not is_doc:
            for f in entropy_findings(rel, text):
                if only_set and "SECRET" not in only_set and f["rule"] not in only_set:
                    continue
                if limit is not None and f["line"] not in limit.get(rel, ()):
                    continue
                if is_test and cfg.get("downgradeTests", True):
                    f["severity"] = "low"
                    f["confidence"] = "low"
                findings.append(f)

    for f in findings:
        f["id"] = fingerprint(f)
    findings.sort(key=lambda f: (-SEV_RANK[f["severity"]], f["file"], f["line"]))
    return findings, scanned, meta


def project_checks(root):
    """Repository-level hygiene that no per-line regex can see."""
    out = []

    def add(rule, title, sev, fix, cwe="", owasp="", path="."):
        out.append(dict(rule=rule, title=title, category="DEFAULT", severity=sev,
                        confidence="high", owasp=owasp, cwe=cwe, file=path, line=0,
                        snippet="(project-level check)", fix=fix, meta={}))

    gi_path = os.path.join(root, ".gitignore")
    gi = read_text(gi_path) or ""
    has_git = os.path.isdir(os.path.join(root, ".git"))
    env_files = [f for f in os.listdir(root) if f.startswith(".env") and not f.endswith((".example", ".sample", ".template"))] \
        if os.path.isdir(root) else []
    if env_files and ".env" not in gi:
        add("PROJ-001", "Environment file present but .env is not git-ignored", "critical",
            "Add .env, .env.local and *.pem/*.key to .gitignore, then rotate anything already committed.",
            "CWE-540", "A02:2025 Security Misconfiguration", ".gitignore")
    if has_git:
        tracked = git(root, "ls-files", "--", ".env", ".env.*", "*.pem", "*.key", "id_rsa", "*.p12", "*.pfx")
        for t in [x for x in tracked.splitlines() if x and not x.endswith((".example", ".sample", ".template"))]:
            add("PROJ-002", "Secret-bearing file is tracked in git: %s" % t, "critical",
                "Rotate the credential first, then git rm --cached and purge history (git filter-repo / BFG).",
                "CWE-540", "A04:2025 Cryptographic Failures", t)

    locks = {
        "npm": "package-lock.json", "yarn": "yarn.lock", "pnpm": "pnpm-lock.yaml",
        "bun": "bun.lockb",
    }
    present = [n for n, f in locks.items() if os.path.exists(os.path.join(root, f))]
    if os.path.exists(os.path.join(root, "package.json")):
        if not present:
            add("PROJ-003", "package.json without a committed lockfile", "medium",
                "Commit a lockfile and use a frozen install in CI (npm ci / pnpm i --frozen-lockfile).",
                "CWE-1357", "A03:2025 Software Supply Chain Failures", "package.json")
        elif len(present) > 1:
            add("PROJ-004", "Competing lockfiles at one installation boundary: %s" % ", ".join(present),
                "medium", "Keep exactly one package manager per installation boundary; delete the others.",
                "CWE-1357", "A03:2025 Software Supply Chain Failures", "package.json")

    wf_dir = os.path.join(root, ".github", "workflows")
    if os.path.isdir(wf_dir):
        any_perms = False
        for fn in os.listdir(wf_dir):
            if fn.endswith((".yml", ".yaml")):
                if "permissions:" in (read_text(os.path.join(wf_dir, fn)) or ""):
                    any_perms = True
        if not any_perms:
            add("PROJ-005", "GitHub workflows do not declare a permissions block", "medium",
                "Add `permissions: { contents: read }` at workflow level and widen per job only where needed.",
                "CWE-732", "A03:2025 Software Supply Chain Failures", ".github/workflows")
    for f in out:
        f["id"] = fingerprint(f)
    return out


# --------------------------------------------------------------------------
# output renderers
# --------------------------------------------------------------------------
def summarize(findings):
    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    return counts


def render_text(findings, scanned, elapsed, root):
    lines = []
    counts = summarize(findings)
    lines.append("")
    lines.append(c("  %s v%s" % (BRAND, __version__), "1;95"))
    lines.append("  %s | %d files | %.2fs" % (os.path.abspath(root), scanned, elapsed))
    lines.append("")
    if not findings:
        lines.append(c("  No findings above threshold. Note what you could NOT assess.", "92"))
        lines.append("")
        return "\n".join(lines)

    by_file = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)
    order = sorted(by_file, key=lambda p: -max(SEV_RANK[x["severity"]] for x in by_file[p]))
    for path in order:
        lines.append(c("  " + path, "1;97"))
        for f in sorted(by_file[path], key=lambda x: (-SEV_RANK[x["severity"]], x["line"])):
            loc = ("%s:%d" % (path, f["line"])) if f["line"] else path
            lines.append("    %s %s  %s" % (sev_tag(f["severity"]), c(f["rule"], "1;94"), f["title"]))
            lines.append("             %s  %s" % (c(loc, "90"),
                                                  c("conf:" + f["confidence"], "90")))
            if f["snippet"] and f["line"]:
                lines.append("             %s" % c(f["snippet"][:150], "90"))
            if f.get("fix"):
                lines.append("             %s %s" % (c("fix:", "92"), f["fix"][:180]))
        lines.append("")
    parts = ["%s %d" % (s, counts[s]) for s in reversed(SEVERITIES) if counts[s]]
    lines.append(c("  " + "  |  ".join(parts), "1"))
    lines.append("")
    lines.append(c("  Next: verify each lead before reporting it (SKILL.md §5).", "90"))
    lines.append(c("  A regex hit is a lead. Trace source -> sink -> impact, then fix the class.", "90"))
    lines.append("")
    return "\n".join(lines)


def render_markdown(findings, scanned, root, title=None):
    counts = summarize(findings)
    md = ["# %s — scan results" % (title or BRAND), ""]
    md.append("- Target: `%s`" % os.path.abspath(root))
    md.append("- Files scanned: %d" % scanned)
    md.append("- Generated: %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    md.append("")
    md.append("| Critical | High | Medium | Low | Info |")
    md.append("|---|---|---|---|---|")
    md.append("| %d | %d | %d | %d | %d |" % (counts["critical"], counts["high"],
                                              counts["medium"], counts["low"], counts["info"]))
    md.append("")
    md.append("> Machine-generated leads. Each item must pass the verification gate "
              "(attacker-controlled input → reachable sink → blast radius) before it is reported as a finding.")
    md.append("")
    for sev in reversed(SEVERITIES):
        group = [f for f in findings if f["severity"] == sev]
        if not group:
            continue
        md.append("## %s (%d)" % (sev.capitalize(), len(group)))
        md.append("")
        for f in group:
            loc = "`%s:%d`" % (f["file"], f["line"]) if f["line"] else "`%s`" % f["file"]
            md.append("### %s — %s" % (f["rule"], f["title"]))
            md.append("")
            md.append("- **Where:** %s" % loc)
            md.append("- **Confidence:** %s | **OWASP:** %s | **CWE:** %s"
                      % (f["confidence"], f.get("owasp") or "n/a", f.get("cwe") or "n/a"))
            if f.get("snippet") and f["line"]:
                md.append("- **Code:**")
                md.append("")
                md.append("  ```")
                md.append("  " + f["snippet"])
                md.append("  ```")
            if f.get("fix"):
                md.append("- **Fix:** %s" % f["fix"])
            md.append("- **Verdict:** _to be completed after verification_")
            md.append("")
    return "\n".join(md)


def render_sarif(findings, root):
    rules, seen = [], set()
    sarif_level = {"critical": "error", "high": "error", "medium": "warning",
                   "low": "note", "info": "note"}
    results = []
    for f in findings:
        if f["rule"] not in seen:
            seen.add(f["rule"])
            rules.append({
                "id": f["rule"],
                "name": f["rule"],
                "shortDescription": {"text": f["title"]},
                "fullDescription": {"text": f.get("fix", f["title"])},
                "defaultConfiguration": {"level": sarif_level.get(f["severity"], "warning")},
                "properties": {"tags": [f["category"], f.get("owasp", ""), f.get("cwe", "")],
                               "security-severity": {"critical": "9.5", "high": "8.0",
                                                     "medium": "5.0", "low": "3.0",
                                                     "info": "1.0"}[f["severity"]]},
            })
        results.append({
            "ruleId": f["rule"],
            "level": sarif_level.get(f["severity"], "warning"),
            "message": {"text": "%s — %s" % (f["title"], f.get("fix", ""))},
            "partialFingerprints": {"vioraFingerprint": f.get("id", "")},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": f["file"]},
                "region": {"startLine": max(1, f["line"])},
            }}],
        })
    return json.dumps({
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": BRAND, "version": __version__,
                                      "informationUri": "https://viora.dev",
                                      "rules": rules}},
                  "results": results}],
    }, indent=2)


def write_out(path, content):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
STACK_MARKERS = [
    ("package.json", "Node / JavaScript"), ("tsconfig.json", "TypeScript"),
    ("requirements.txt", "Python"), ("pyproject.toml", "Python"),
    ("go.mod", "Go"), ("Cargo.toml", "Rust"), ("composer.json", "PHP"),
    ("Gemfile", "Ruby"), ("pom.xml", "Java/Maven"), ("build.gradle", "Java/Gradle"),
    ("build.gradle.kts", "Kotlin/Gradle"), ("Dockerfile", "Docker"),
    ("docker-compose.yml", "Docker Compose"), ("next.config.js", "Next.js"),
    ("nuxt.config.ts", "Nuxt"), ("manage.py", "Django"), ("artisan", "Laravel"),
    ("main.tf", "Terraform"), ("serverless.yml", "Serverless"),
]
OPTIONAL_TOOLS = ["semgrep", "gitleaks", "trivy", "bandit", "osv-scanner", "grype",
                  "syft", "checkov", "hadolint", "govulncheck", "cargo-audit",
                  "npm", "pnpm", "yarn", "pip-audit", "git", "docker"]


def cmd_doctor(args):
    root = os.path.abspath(args.path)
    print("")
    print(c("  %s v%s — environment" % (BRAND, __version__), "1;95"))
    print("  target: %s" % root)
    print("  python: %s" % sys.version.split()[0])
    print("")
    stack = [label for marker, label in STACK_MARKERS if os.path.exists(os.path.join(root, marker))]
    print(c("  Stack detected", "1;97"))
    print("    " + (", ".join(sorted(set(stack))) if stack else "unknown — inspect manually"))
    print("")
    if os.path.isdir(os.path.join(root, ".git")):
        branch = (git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?").strip()
        dirty = bool(git(root, "status", "--porcelain").strip())
        print(c("  Git", "1;97"))
        print("    branch %s | working tree %s" % (branch, "dirty" if dirty else "clean"))
        print("")
    print(c("  Optional security tooling", "1;97"))
    found, missing = [], []
    for t in OPTIONAL_TOOLS:
        (found if shutil.which(t) else missing).append(t)
    print("    available: " + (", ".join(found) if found else "none"))
    print("    missing:   " + (", ".join(missing) if missing else "none"))
    print("")
    entry_hits = []
    for rel, full in walk_files(root):
        b = os.path.basename(rel).lower()
        if any(k in b for k in ("route", "router", "controller", "handler", "middleware",
                                "auth", "session", "permission", "policy", "guard", "webhook")):
            entry_hits.append(rel)
        if len(entry_hits) >= 25:
            break
    print(c("  Likely entry points / security-critical files", "1;97"))
    for p in entry_hits[:20]:
        print("    " + p)
    if not entry_hits:
        print("    none matched by name — map entry points by reading the framework config")
    print("")
    print(c("  Next: viora.py scan --path . --format markdown --out .viora/findings.md", "90"))
    print("")
    return 0


def cmd_scan(args):
    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        eprint("error: not a directory: %s" % root)
        return 2
    cfg = load_config(root)
    if args.fail_on:
        cfg["failOn"] = args.fail_on
    min_sev = args.severity or cfg.get("minSeverity", "low")

    diff_ref = "--staged" if getattr(args, "staged", False) else args.diff

    t0 = time.time()
    findings, scanned, _meta = scan_project(root, cfg, only=args.only, diff_ref=diff_ref)
    if not diff_ref:
        findings.extend(project_checks(root))
    findings = [f for f in findings if SEV_RANK[f["severity"]] >= SEV_RANK[min_sev]]

    if getattr(args, "no_baseline", False):
        base = {}
    else:
        baseline_path = args.baseline or os.path.join(root, ".viora", "baseline.json")
        base = load_json(baseline_path, {}) or {}
    known = set(base.get("fingerprints", []))
    if known:
        before = len(findings)
        findings = [f for f in findings if f["id"] not in known]
        if before != len(findings):
            eprint("  (baseline suppressed %d known findings)" % (before - len(findings)))

    findings.sort(key=lambda f: (-SEV_RANK[f["severity"]], f["file"], f["line"]))
    elapsed = time.time() - t0
    counts = summarize(findings)

    fmt = args.format or "text"
    if fmt == "json":
        body = json.dumps({"tool": BRAND, "version": __version__,
                           "target": root, "filesScanned": scanned,
                           "summary": counts, "findings": findings}, indent=2)
    elif fmt == "sarif":
        body = render_sarif(findings, root)
    elif fmt == "markdown":
        body = render_markdown(findings, scanned, root)
    else:
        body = render_text(findings, scanned, elapsed, root)

    quiet = getattr(args, "quiet", False)
    if args.out:
        write_out(args.out, body)
        if not quiet:
            print("written: %s" % args.out)
    elif not quiet:
        print(body)

    if args.json:
        write_out(args.json, json.dumps({"tool": BRAND, "version": __version__,
                                         "target": root, "filesScanned": scanned,
                                         "summary": counts, "findings": findings}, indent=2))
        if not quiet:
            print("written: %s" % args.json)

    gate = cfg.get("failOn", "high")
    if gate and gate != "none":
        breach = sum(counts[s] for s in SEVERITIES if SEV_RANK[s] >= SEV_RANK[gate])
        if breach:
            if not quiet:
                eprint("gate: %d finding(s) at or above '%s'" % (breach, gate))
            return 1
    return 0


# ---- dependency / supply chain -------------------------------------------
POPULAR = ["react", "lodash", "express", "axios", "moment", "chalk", "commander",
           "request", "debug", "webpack", "typescript", "eslint", "jest", "vue",
           "next", "dotenv", "cross-env", "colors", "underscore", "jquery",
           "requests", "urllib3", "numpy", "pandas", "flask", "django", "pytest",
           "setuptools", "cryptography", "pyyaml", "boto3", "pillow"]


def levenshtein(a, b):
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cmd_deps(args):
    root = os.path.abspath(args.path)
    report = {"tool": BRAND, "target": root, "ecosystems": [], "findings": [], "notAssessed": []}
    out = []

    def add(sev, rule, title, fix, where="."):
        report["findings"].append(dict(rule=rule, title=title, severity=sev, file=where,
                                       line=0, category="SUPPLY", confidence="high",
                                       fix=fix, snippet="(dependency check)",
                                       owasp="A03:2025 Software Supply Chain Failures", cwe="CWE-1357"))

    pkg_path = os.path.join(root, "package.json")
    if os.path.exists(pkg_path):
        report["ecosystems"].append("npm")
        pkg = load_json(pkg_path, {}) or {}
        scripts = pkg.get("scripts", {}) or {}
        for hook in ("preinstall", "install", "postinstall", "prepare"):
            if hook in scripts:
                add("medium", "DEP-001",
                    "package.json defines a lifecycle script '%s': %s" % (hook, str(scripts[hook])[:90]),
                    "Lifecycle scripts execute on every install. Review the source, then install with "
                    "--ignore-scripts and allowlist only what the build genuinely needs.", "package.json")
        deps = {}
        for key in ("dependencies", "devDependencies", "optionalDependencies"):
            deps.update(pkg.get(key, {}) or {})
        for name, spec in deps.items():
            if isinstance(spec, str) and re.match(r"^(https?:|git\+|github:|file:)", spec):
                add("high", "DEP-002", "Dependency '%s' installed from a non-registry source: %s" % (name, spec),
                    "Non-registry sources bypass registry signing and advisories. Vendor it or pin a commit SHA.",
                    "package.json")
            if isinstance(spec, str) and spec.strip() in ("*", "latest", ""):
                add("medium", "DEP-003", "Dependency '%s' has an unpinned range ('%s')" % (name, spec),
                    "Pin to a caret/exact range and rely on the lockfile for reproducibility.", "package.json")
            low = name.lower()
            for pop in POPULAR:
                if low != pop and abs(len(low) - len(pop)) <= 2 and levenshtein(low, pop) == 1:
                    add("high", "DEP-004", "Possible typosquat: '%s' is one character from '%s'" % (name, pop),
                        "Verify the package on the registry (publisher, downloads, repository) before trusting it.",
                        "package.json")
        locks = [f for f in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb")
                 if os.path.exists(os.path.join(root, f))]
        if not locks:
            add("medium", "DEP-005", "No lockfile committed", "Commit a lockfile and use a frozen install in CI.")
        elif len(locks) > 1:
            add("medium", "DEP-006", "Competing lockfiles: %s" % ", ".join(locks),
                "Keep exactly one package manager per installation boundary.")
        out.append("npm: %d direct dependencies, lockfiles: %s" % (len(deps), ", ".join(locks) or "none"))

    for f in ("requirements.txt", "pyproject.toml", "Pipfile"):
        p = os.path.join(root, f)
        if os.path.exists(p):
            report["ecosystems"].append("python")
            txt = read_text(p) or ""
            if f == "requirements.txt":
                unpinned = [ln.strip() for ln in txt.splitlines()
                            if ln.strip() and not ln.strip().startswith("#")
                            and not re.search(r"[=<>~!]=|@", ln)]
                if unpinned:
                    add("medium", "DEP-007",
                        "%d unpinned Python requirement(s): %s" % (len(unpinned), ", ".join(unpinned[:6])),
                        "Pin exact versions and add hashes (pip install --require-hashes) for reproducible installs.",
                        f)
            if "--trusted-host" in txt or "--index-url http://" in txt:
                add("high", "DEP-008", "Insecure package index configuration in %s" % f,
                    "Use HTTPS indexes only; --trusted-host disables TLS verification for the registry.", f)
            out.append("python: %s present" % f)
            break

    for f, eco in (("go.mod", "go"), ("Cargo.toml", "rust"), ("composer.json", "php"), ("Gemfile", "ruby")):
        if os.path.exists(os.path.join(root, f)):
            report["ecosystems"].append(eco)
            out.append("%s: %s present" % (eco, f))

    if not report["ecosystems"]:
        report["notAssessed"].append("No supported manifest found (package.json, requirements.txt, "
                                     "pyproject.toml, go.mod, Cargo.toml, composer.json, Gemfile).")

    if args.online:
        ran = False
        if shutil.which("npm") and os.path.exists(pkg_path):
            ran = True
            try:
                p = subprocess.run(["npm", "audit", "--json"], cwd=root, capture_output=True,
                                   text=True, timeout=300)
                data = json.loads(p.stdout or "{}")
                meta = (data.get("metadata") or {}).get("vulnerabilities", {})
                if meta:
                    out.append("npm audit: " + ", ".join("%s %s" % (k, v) for k, v in meta.items() if v))
                for name, v in (data.get("vulnerabilities") or {}).items():
                    sev = v.get("severity", "medium")
                    sev = {"moderate": "medium"}.get(sev, sev)
                    if sev in SEV_RANK:
                        add(sev, "DEP-100", "Advisory in dependency '%s' (%s)" % (name, sev),
                            "Triage by reachability, then upgrade. Never use forced audit remediation blindly.",
                            "package.json")
            except Exception as exc:
                report["notAssessed"].append("npm audit failed: %s" % exc)
        for tool, cmd in (("pip-audit", ["pip-audit", "-f", "json"]),
                          ("govulncheck", ["govulncheck", "./..."]),
                          ("osv-scanner", ["osv-scanner", "--format", "json", "-r", "."])):
            if shutil.which(tool):
                ran = True
                try:
                    p = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=420)
                    out.append("%s: exit %d (%d bytes of output captured)" % (tool, p.returncode, len(p.stdout)))
                except Exception as exc:
                    report["notAssessed"].append("%s failed: %s" % (tool, exc))
        if not ran:
            report["notAssessed"].append("No advisory scanner available (npm / pip-audit / osv-scanner / govulncheck).")
    else:
        report["notAssessed"].append("Advisory databases not queried (offline mode). Re-run with --online.")

    for f in report["findings"]:
        f["id"] = fingerprint(f)
    report["findings"].sort(key=lambda f: -SEV_RANK[f["severity"]])

    if args.json:
        write_out(args.json, json.dumps(report, indent=2))
        print("written: %s" % args.json)

    print("")
    print(c("  %s — supply chain" % BRAND, "1;95"))
    print("  %s" % root)
    print("")
    for line in out:
        print("    " + line)
    print("")
    if report["findings"]:
        for f in report["findings"]:
            print("    %s %s  %s" % (sev_tag(f["severity"]), c(f["rule"], "1;94"), f["title"]))
            print("             %s %s" % (c("fix:", "92"), f["fix"]))
    else:
        print(c("    No supply-chain findings from the offline checks.", "92"))
    if report["notAssessed"]:
        print("")
        print(c("    Not assessed", "1;93"))
        for n in report["notAssessed"]:
            print("      - " + n)
    print("")
    counts = summarize(report["findings"])
    return 1 if (counts["critical"] or counts["high"]) else 0


# ---- live headers ---------------------------------------------------------
REQUIRED_HEADERS = {
    "strict-transport-security": ("high", "HSTS missing — downgrade and cookie-theft window stays open",
                                  "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload"),
    "content-security-policy": ("high", "CSP missing — no defence-in-depth against XSS/data injection",
                                "Content-Security-Policy: default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"),
    "x-content-type-options": ("medium", "MIME sniffing not disabled", "X-Content-Type-Options: nosniff"),
    "referrer-policy": ("low", "Referrer-Policy missing — URLs leak to third parties",
                        "Referrer-Policy: strict-origin-when-cross-origin"),
    "permissions-policy": ("low", "Permissions-Policy missing — powerful APIs not restricted",
                           "Permissions-Policy: camera=(), microphone=(), geolocation=()"),
}
LEAKY_HEADERS = ["server", "x-powered-by", "x-aspnet-version", "x-generator", "x-drupal-cache"]


def cmd_headers(args):
    import urllib.error
    import urllib.request

    url = args.url
    if not re.match(r"^https?://", url):
        url = "https://" + url
    findings, notes = [], []

    def add(sev, rule, title, fix):
        findings.append(dict(rule=rule, title=title, severity=sev, category="DEFAULT",
                             confidence="high", file=url, line=0, snippet="(live check)",
                             fix=fix, owasp="A02:2025 Security Misconfiguration", cwe="CWE-693"))

    def fetch(target, origin=None, method="GET"):
        req = urllib.request.Request(target, method=method)
        req.add_header("User-Agent", "Viora-Aegis/%s (defensive header check)" % __version__)
        if origin:
            req.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(req, timeout=args.timeout) as resp:
                return resp.status, dict((k.lower(), v) for k, v in resp.getheaders()), resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, dict((k.lower(), v) for k, v in (e.headers.items() if e.headers else [])), target
        except Exception as exc:
            return None, {"__error__": str(exc)}, target

    status, headers, final = fetch(url)
    if status is None:
        eprint("error: could not reach %s (%s)" % (url, headers.get("__error__")))
        return 2

    for h, (sev, title, fix) in REQUIRED_HEADERS.items():
        if h not in headers:
            add(sev, "HDR-" + h[:12].upper().replace("-", ""), title, fix)
    if "content-security-policy" in headers:
        csp = headers["content-security-policy"]
        if "unsafe-inline" in csp or "unsafe-eval" in csp:
            add("medium", "HDR-CSPWEAK", "CSP allows unsafe-inline/unsafe-eval",
                "Remove unsafe-* and adopt nonces or hashes for inline scripts.")
        if "frame-ancestors" not in csp and "x-frame-options" not in headers:
            add("medium", "HDR-CLICKJACK", "No clickjacking protection",
                "Add frame-ancestors 'none' to the CSP (or X-Frame-Options: DENY).")
    elif "x-frame-options" not in headers:
        add("medium", "HDR-CLICKJACK", "No clickjacking protection",
            "Add Content-Security-Policy: frame-ancestors 'none'.")

    for h in LEAKY_HEADERS:
        if h in headers and re.search(r"\d", headers[h]):
            add("low", "HDR-BANNER", "Version disclosure via '%s: %s'" % (h, headers[h]),
                "Strip or genericise the header at the proxy.")

    cookies = headers.get("set-cookie", "")
    if cookies:
        low = cookies.lower()
        if "httponly" not in low:
            add("high", "HDR-COOKIE1", "Set-Cookie without HttpOnly", "Add HttpOnly to session cookies.")
        if "secure" not in low:
            add("high", "HDR-COOKIE2", "Set-Cookie without Secure", "Add Secure; serve cookies over HTTPS only.")
        if "samesite" not in low:
            add("medium", "HDR-COOKIE3", "Set-Cookie without SameSite", "Add SameSite=Lax (or Strict).")

    probe = "https://viora-aegis-probe.invalid"
    _s, cors_headers, _u = fetch(final, origin=probe)
    acao = cors_headers.get("access-control-allow-origin", "")
    acac = cors_headers.get("access-control-allow-credentials", "").lower()
    if acao == "*":
        add("medium", "HDR-CORS1", "CORS allows any origin (*)",
            "Allowlist exact origins; a wildcard exposes any authenticated JSON endpoint to every site.")
    elif acao and probe in acao:
        sev = "critical" if acac == "true" else "high"
        add(sev, "HDR-CORS2", "CORS reflects an arbitrary Origin%s" % (" with credentials" if acac == "true" else ""),
            "Never echo the Origin header. Compare it against a static allowlist before responding.")

    if url.startswith("http://"):
        add("high", "HDR-TLS1", "Plain HTTP endpoint", "Redirect all HTTP to HTTPS and enable HSTS.")

    for f in findings:
        f["id"] = fingerprint(f)
    findings.sort(key=lambda f: -SEV_RANK[f["severity"]])

    if args.json:
        write_out(args.json, json.dumps({"tool": BRAND, "target": final, "status": status,
                                         "headers": headers, "findings": findings}, indent=2))
        print("written: %s" % args.json)

    print("")
    print(c("  %s — live surface" % BRAND, "1;95"))
    print("  %s (HTTP %s)" % (final, status))
    print("")
    present = [h for h in list(REQUIRED_HEADERS) + ["x-frame-options"] if h in headers]
    print(c("    present: ", "92") + (", ".join(present) if present else "none"))
    print("")
    for f in findings:
        print("    %s %s  %s" % (sev_tag(f["severity"]), c(f["rule"], "1;94"), f["title"]))
        print("             %s %s" % (c("fix:", "92"), f["fix"]))
    if not findings:
        print(c("    No header findings. Headers are hardening, not a substitute for server-side controls.", "92"))
    print("")
    print(c("    Not assessed: authentication, authorization, business logic, rate limits.", "90"))
    print("")
    counts = summarize(findings)
    return 1 if (counts["critical"] or counts["high"]) else 0


def cmd_baseline(args):
    root = os.path.abspath(args.path)
    cfg = load_config(root)
    findings, _s, _m = scan_project(root, cfg)
    findings.extend(project_checks(root))
    out = args.out or os.path.join(root, ".viora", "baseline.json")
    write_out(out, json.dumps({
        "tool": BRAND, "version": __version__,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "Accepted findings. Remove an entry to make the gate enforce it again.",
        "fingerprints": sorted(set(f["id"] for f in findings)),
        "items": [{"id": f["id"], "rule": f["rule"], "file": f["file"], "line": f["line"],
                   "severity": f["severity"]} for f in findings],
    }, indent=2))
    print("baseline written: %s (%d findings frozen)" % (out, len(findings)))
    return 0


def cmd_report(args):
    src = os.path.abspath(args.inp)
    files = []
    if os.path.isdir(src):
        files = [os.path.join(src, f) for f in sorted(os.listdir(src)) if f.endswith(".json")]
    elif os.path.isfile(src):
        files = [src]
    merged, sources = [], []
    for f in files:
        data = load_json(f)
        if isinstance(data, dict) and isinstance(data.get("findings"), list):
            merged.extend(data["findings"])
            sources.append(os.path.basename(f))
    seen, uniq = set(), []
    for f in merged:
        key = f.get("id") or fingerprint(f)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    uniq.sort(key=lambda f: (-SEV_RANK.get(f.get("severity", "low"), 1), f.get("file", "")))
    counts = summarize(uniq)

    tpl_path = os.path.join(PACK, "templates", "SECURITY_REPORT.md")
    tpl = read_text(tpl_path)
    body = render_markdown(uniq, 0, ".", title=args.title or "Security assessment")
    if tpl:
        verdict = "BLOCK RELEASE" if (counts["critical"] or counts["high"]) else "SHIP WITH FOLLOW-UPS"
        head = (tpl.replace("{{TITLE}}", args.title or "Security assessment")
                   .replace("{{DATE}}", time.strftime("%Y-%m-%d"))
                   .replace("{{VERDICT}}", verdict)
                   .replace("{{CRITICAL}}", str(counts["critical"]))
                   .replace("{{HIGH}}", str(counts["high"]))
                   .replace("{{MEDIUM}}", str(counts["medium"]))
                   .replace("{{LOW}}", str(counts["low"]))
                   .replace("{{SOURCES}}", ", ".join(sources) or "n/a"))
        body = head + "\n\n---\n\n" + body
    write_out(args.out, body)
    print("report written: %s (%d unique findings from %d artifact(s))" % (args.out, len(uniq), len(files)))
    return 0


PRECOMMIT = """#!/bin/sh
# Viora Aegis pre-commit gate - blocks secrets and critical issues.
# Bypass in a genuine emergency with: git commit --no-verify
ROOT="$(git rev-parse --show-toplevel)"
SKILL_DIR="${{VIORA_SKILL_DIR:-$ROOT/{skilldir}}}"
[ -f "$SKILL_DIR/scripts/viora.py" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0
python3 "$SKILL_DIR/scripts/viora.py" scan --path "$ROOT" --staged --severity high --fail-on critical --no-baseline || {{
  echo ""
  echo "  Viora Aegis blocked this commit. Fix the critical findings above,"
  echo "  or run 'git commit --no-verify' if you are certain they are false positives."
  exit 1
}}
exit 0
"""

GH_WORKFLOW = """name: Viora Aegis

on:
  pull_request:
  push:
    branches: [main, master]

permissions:
  contents: read
  security-events: write

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Viora Aegis scan
        run: |
          python3 {skilldir}/scripts/viora.py scan --path . --format sarif --out viora.sarif
          python3 {skilldir}/scripts/viora.py scan --path . --fail-on high
      - name: Viora Aegis supply chain
        run: python3 {skilldir}/scripts/viora.py deps --path . --online
        continue-on-error: true
      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: viora.sarif
"""

GL_WORKFLOW = """viora-aegis:
  stage: test
  image: python:3.12-slim
  script:
    - python3 {skilldir}/scripts/viora.py scan --path . --format json --out viora.json
    - python3 {skilldir}/scripts/viora.py scan --path . --fail-on high
  artifacts:
    when: always
    paths: [viora.json]
"""


CANONICAL_SKILL_DIR = ".viora/skills/viora-aegis"


def repo_relative_skill_dir(root):
    """Path to the pack that still makes sense from inside the repo.

    If the pack lives outside the project (running the CLI straight from a
    clone), generated files reference the canonical install location instead of
    a fragile ../../.. path.
    """
    try:
        rel = os.path.relpath(PACK, root).replace(os.sep, "/")
    except ValueError:
        return CANONICAL_SKILL_DIR
    if rel.startswith("..") or os.path.isabs(rel):
        return CANONICAL_SKILL_DIR
    return rel


def cmd_init(args):
    root = os.path.abspath(args.path)
    skilldir = repo_relative_skill_dir(root)
    created = []

    cfg_path = os.path.join(root, "viora.config.json")
    if not os.path.exists(cfg_path):
        write_out(cfg_path, json.dumps({
            "$schema": "viora-config/1",
            "failOn": "high",
            "minSeverity": "low",
            "exclude": ["*.generated.*", "docs/**"],
            "disabledRules": [],
            "severityOverrides": {},
            "secretsEntropy": True,
            "downgradeTests": True,
        }, indent=2) + "\n")
        created.append("viora.config.json")

    if args.hook and os.path.isdir(os.path.join(root, ".git")):
        hook = os.path.join(root, ".git", "hooks", "pre-commit")
        write_out(hook, PRECOMMIT.format(skilldir=skilldir))
        try:
            os.chmod(hook, 0o755)
        except OSError:
            pass
        created.append(".git/hooks/pre-commit")

    if args.ci == "github":
        p = os.path.join(root, ".github", "workflows", "viora-aegis.yml")
        write_out(p, GH_WORKFLOW.format(skilldir=skilldir))
        created.append(os.path.relpath(p, root))
    elif args.ci == "gitlab":
        p = os.path.join(root, ".viora", "gitlab-ci-snippet.yml")
        write_out(p, GL_WORKFLOW.format(skilldir=skilldir))
        created.append(os.path.relpath(p, root) + "  (include this in .gitlab-ci.yml)")

    gi = os.path.join(root, ".gitignore")
    existing = read_text(gi) or ""
    if ".viora/" not in existing:
        with open(gi, "a", encoding="utf-8") as fh:
            fh.write("\n# Viora Aegis working files\n.viora/\nviora.sarif\n")
        created.append(".gitignore (+ .viora/)")

    print("")
    print(c("  %s initialised" % BRAND, "1;95"))
    for f in created:
        print("    + " + f)
    if not created:
        print("    nothing to do — already initialised")
    print("")
    if skilldir == CANONICAL_SKILL_DIR and not os.path.isdir(os.path.join(root, skilldir)):
        print("  Note: generated files expect the pack at %s/" % skilldir)
        print("        install it there (install.sh) or set VIORA_SKILL_DIR.")
        print("")
    print("  Next: python3 %s/scripts/viora.py scan --path ." % skilldir)
    print("")
    return 0


# --------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(prog="viora", description="%s v%s — defensive security engine" % (BRAND, __version__))
    p.add_argument("--version", action="version", version="%s %s" % (BRAND, __version__))
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("doctor", help="environment, stack and tooling report")
    d.add_argument("--path", default=".")
    d.set_defaults(func=cmd_doctor)

    s = sub.add_parser("scan", help="static security scan")
    s.add_argument("--path", default=".")
    s.add_argument("--diff", help="only scan lines changed vs this git ref")
    s.add_argument("--staged", action="store_true", help="only scan lines staged in git (pre-commit)")
    s.add_argument("--only", help="comma-separated rule IDs or categories")
    s.add_argument("--severity", choices=SEVERITIES, help="minimum severity to display")
    s.add_argument("--fail-on", choices=SEVERITIES + ["none"], help="exit 1 at or above this severity")
    s.add_argument("--format", choices=["text", "json", "sarif", "markdown"], default="text")
    s.add_argument("--out", help="write the chosen format to this file")
    s.add_argument("--json", help="additionally write raw JSON here")
    s.add_argument("--baseline", nargs="?", const="", default=None,
                   help="suppress findings frozen in a baseline file (default .viora/baseline.json)")
    s.add_argument("--no-baseline", action="store_true", help="ignore any baseline file")
    s.add_argument("--quiet", action="store_true", help="print nothing; communicate through the exit code")
    s.set_defaults(func=cmd_scan)

    dp = sub.add_parser("deps", help="supply-chain and dependency checks")
    dp.add_argument("--path", default=".")
    dp.add_argument("--online", action="store_true", help="run native advisory scanners if installed")
    dp.add_argument("--json", help="write JSON results here")
    dp.set_defaults(func=cmd_deps)

    h = sub.add_parser("headers", help="live security headers / cookies / CORS check")
    h.add_argument("url")
    h.add_argument("--json", help="write JSON results here")
    h.add_argument("--timeout", type=float, default=10.0)
    h.set_defaults(func=cmd_headers)

    b = sub.add_parser("baseline", help="freeze current findings as accepted debt")
    b.add_argument("--path", default=".")
    b.add_argument("--out")
    b.set_defaults(func=cmd_baseline)

    r = sub.add_parser("report", help="merge JSON artifacts into one markdown report")
    r.add_argument("--in", dest="inp", default=".viora")
    r.add_argument("--out", default="SECURITY_REPORT.md")
    r.add_argument("--title")
    r.set_defaults(func=cmd_report)

    i = sub.add_parser("init", help="install config, pre-commit hook and CI gate")
    i.add_argument("--path", default=".")
    i.add_argument("--ci", choices=["github", "gitlab", "none"], default="github")
    i.add_argument("--hook", action="store_true")
    i.set_defaults(func=cmd_init)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        eprint("interrupted")
        return 2
    except Exception as exc:  # never crash the agent's shell
        eprint("error: %s" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
