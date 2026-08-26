#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viora Aegis - SKILL-AUDIT engine.

Static safety audit of an Agent Skill, plugin, MCP server or agent-rules pack
BEFORE it is installed or trusted.

HARD RULE: this module NEVER executes the target. It only reads files.
No install, no build, no postinstall, no npx, no hooks enabled, no server started.

Why this exists: a skill is code that runs with the full permissions of the agent,
and its SKILL.md text is injected straight into the agent's context. So a hostile
skill has two attack channels at once - it can run code, and it can try to
reprogram the agent reading it. This engine locates both, and tiers every finding
by HOW the code reaches execution:

    auto-run       - fires by itself once installed (hooks, install scripts)
    on-invocation  - runs whenever the skill is used (scripts named in SKILL.md)
    on-demand       - runs only if a specific feature is explicitly invoked
    static-text    - text injected into the agent context (prompt-injection surface)

The scanner locates. The agent judges. Counts are never a verdict.

Zero dependencies. Python 3.8+.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)

SEVERITIES = ["info", "low", "medium", "high", "critical"]
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
TIERS = ["auto-run", "on-invocation", "on-demand", "static-text"]
TIER_WEIGHT = {"auto-run": 3, "on-invocation": 2, "on-demand": 1, "static-text": 2}

CODE_EXTS = {
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".sh", ".bash", ".zsh",
    ".fish", ".rb", ".pl", ".php", ".ps1", ".psm1", ".go", ".rs", ".java", ".kt",
    ".lua", ".r", ".jl",
}
MD_EXTS = {".md", ".markdown", ".mdx", ".mdc", ".txt", ".rst"}
CONFIG_EXTS = {".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".xml"}
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".next",
    "coverage", ".turbo", ".yarn", "site-packages",
}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_LINE_LEN = 4000
VENDOR_LINE_LEN = 2000

LOCALHOST = re.compile(r"\b(localhost|127\.0\.0\.1|0\.0\.0\.0|::1|\[::1\])\b")
URL_HOST = re.compile(r"https?://([A-Za-z0-9._\-]+)")
FENCE = re.compile(r"^\s*(```|~~~)")

# A security tool's own rule table necessarily contains every string it hunts
# for. Those lines describe detection, not behaviour, so they must not be
# reported as if the skill performed the action. They are still shown - capped at
# low - because "suppressed silently" is how real findings get lost.
DETECTOR_LINE = re.compile(
    r"""(?x)
      \bre\s*:\s*/                      # { re: /.../ }  JS rule object
    | \bpattern\b["']?\s*[:=]           # pattern: / "pattern":
    | re\.compile\s*\(                   # Python compiled rule
    | new\s+RegExp\s*\(
    | \bid\s*:\s*["'][A-Za-z0-9_.\-]+["']\s*,   # { id: 'net-fetch', ... }
    | \bseverity\s*:\s*["'](?:info|low|medium|high|critical)["']
    | \bcategory\s*:\s*["']
    | ^\s*["']?(?:exclude_line|fp|note|ask|fix|title)["']?\s*:
    | \bgrep\s+-[a-zA-Z]*E\b            # documented grep recipe
    | ^\s*[|+-]?\s*\\b\(               # a bare alternation fragment
    """)
# Whole files that exist only to declare patterns.
DETECTOR_FILE = re.compile(
    r"(^|/)(rules?|patterns?|signatures?|corpus|seeds)[\w.\-]*\.(json|ya?ml|toml)$"
    r"|(^|/)(patterns|rules|signatures)\.mdx?$", re.I)

# A path string is not an access. "~/.ssh" inside a rule table, an allowlist or
# a sentence is a mention; open("~/.ssh/id_rsa") is behaviour. The question that
# separates them: is the dangerous string an argument to a MATCHER, or to an
# ACTION? These are the verbs that make it an action.
IO_VERB = re.compile(
    r"\b(?:open|read|write|append|load|save|copy|move|remove|unlink|delete|dump)\w*\s*\("
    r"|\bfs\s*\.|\bshutil\.|\bglob\.|\bpathlib\b|\bPath\s*\("
    r"|\bos\.(?:path|remove|rename|listdir|scandir|walk|stat)\b"
    r"|\b(?:cat|less|head|tail|cp|mv|rm|scp|rsync|tar|zip|gzip|base64|find)\b"
    r"|\bfetch\s*\(|\baxios|\brequests?\.|\burlopen|\bcurl\b|\bwget\b|\bupload\b"
    r"|\b(?:send|post|put)\b|\bexec\w*\s*\(|\bspawn\w*\s*\(|\bsubprocess\."
    r"|\bsystem\s*\(|>>?\s*[\w./~$]", re.I)

# Config filenames that can wire code to run on their own.
AUTORUN_MANIFESTS = re.compile(
    r"(^|/)(hooks?\.json|settings(\.local)?\.json|\.mcp\.json|mcp\.json|"
    r"package\.json|plugin\.json|marketplace\.json|manifest\.json|"
    r"\.claude-plugin/|\.cursor/|\.vscode/)", re.I)
AUTORUN_FILENAME = re.compile(
    r"(^|/)(hook[\w.\-]*|(pre|post)[-_]?tool[-_]?use[\w.\-]*|(pre|post)install|"
    r"session[-_]?start|on[-_]?activate|activate|bootstrap|setup)"
    r"\.(mjs|cjs|js|ts|py|sh|bash|ps1)$", re.I)
SCRIPT_REF = re.compile(
    r"(?:node|python3?|bash|sh|zsh|pwsh|powershell|uv run|deno run|bun|\./)\s+"
    r"([\w./\-]+\.(?:mjs|cjs|js|ts|py|sh|bash|ps1))")
HOOK_CMD_REF = re.compile(r"[\"']([^\"'\n]*\.(?:mjs|cjs|js|ts|py|sh|bash|ps1))[\"']")


def _load_rules():
    path = os.path.join(PACK, "rules", "skill-audit.json")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except Exception as exc:  # pragma: no cover
        sys.stderr.write("! cannot load rules/skill-audit.json: %s\n" % exc)
        return [], {}
    rules = []
    for r in data.get("rules", []):
        try:
            r["_re"] = re.compile(r["pattern"])
        except re.error as exc:
            sys.stderr.write("! rule %s invalid pattern: %s\n" % (r.get("id"), exc))
            continue
        r["_ex"] = None
        if r.get("exclude_line"):
            try:
                r["_ex"] = re.compile(r["exclude_line"])
            except re.error:
                pass
        # require_line: a second condition that must ALSO match the same line.
        # Composition rules ("local data placed in an outbound request body")
        # are only meaningful when both halves are present. Without this they
        # fire on any assignment whose name happens to contain "data".
        r["_req"] = None
        if r.get("require_line"):
            try:
                r["_req"] = re.compile(r["require_line"])
            except re.error:
                pass
        rules.append(r)
    return rules, data.get("categories", {})


def _walk(target):
    if os.path.isfile(target):
        root = os.path.dirname(os.path.abspath(target)) or "."
        return root, [os.path.abspath(target)]
    root = os.path.abspath(target)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            out.append(os.path.join(dirpath, fn))
    return root, sorted(out)


def _read(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None, "too-large"
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return None, "unreadable (%s)" % exc.__class__.__name__
    if b"\x00" in raw[:4096]:
        return None, "binary"
    return raw.decode("utf-8", errors="replace"), None


def _classify(rel, text):
    ext = os.path.splitext(rel)[1].lower()
    base = os.path.basename(rel).lower()
    if ext in MD_EXTS:
        return "markdown"
    if ext in CONFIG_EXTS or base in ("dockerfile", "makefile", ".npmrc", ".gitmodules"):
        return "config"
    if ext in CODE_EXTS:
        if re.search(r"\.(min|umd|bundle|vendor)\.(js|css)$", base):
            return "vendored"
        if text and max((len(l) for l in text.splitlines()), default=0) > VENDOR_LINE_LEN:
            return "vendored"
        return "code"
    return "asset"


def _frontmatter(text):
    """Parse the leading YAML frontmatter of a SKILL.md, flatly and forgivingly."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out, key = {}, None
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1).strip()
            out[key] = m.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            out[key] = (out.get(key, "") + " " + line.strip()).strip()
    return out


def _detect_tiers(root, files, texts, kinds):
    """Return {abs_path: tier}. Anything reachable without the user asking is auto-run."""
    autorun, oninv = set(), set()
    by_base = {}
    for f in files:
        by_base.setdefault(os.path.basename(f).lower(), []).append(f)

    def resolve(ref):
        ref = ref.strip().lstrip("./")
        if not ref:
            return None
        for f in files:
            rel = os.path.relpath(f, root).replace(os.sep, "/")
            if rel == ref or rel.endswith("/" + ref):
                return f
        cands = by_base.get(os.path.basename(ref).lower())
        return cands[0] if cands and len(cands) == 1 else None

    for f in files:
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        if AUTORUN_FILENAME.search(rel):
            autorun.add(f)
        if kinds.get(f) != "config" or not AUTORUN_MANIFESTS.search(rel):
            continue
        text = texts.get(f) or ""
        base = os.path.basename(rel).lower()
        wired = False
        if base == "package.json":
            try:
                pkg = json.loads(text)
                for name, cmd in (pkg.get("scripts") or {}).items():
                    if name in ("preinstall", "install", "postinstall", "prepare",
                                "prepublish", "prepublishOnly", "postprepare"):
                        wired = True
                        for ref in SCRIPT_REF.findall(str(cmd)):
                            t = resolve(ref)
                            if t:
                                autorun.add(t)
            except Exception:
                if re.search(r"\"(pre|post)?install\"\s*:|\"prepare\"\s*:", text):
                    wired = True
        elif re.search(r"PostToolUse|PreToolUse|SessionStart|UserPromptSubmit|"
                       r"\"hooks\"\s*:|activationEvents|onActivate|\"mcpServers\"", text):
            wired = True
            for ref in HOOK_CMD_REF.findall(text):
                t = resolve(ref)
                if t:
                    autorun.add(t)
        if wired:
            autorun.add(f)

    # Scripts the skill text tells the agent to run = on-invocation.
    for f in files:
        if os.path.basename(f).lower() not in ("skill.md", "agents.md", "claude.md", "readme.md"):
            continue
        for ref in SCRIPT_REF.findall(texts.get(f) or ""):
            t = resolve(ref)
            if t and t not in autorun:
                oninv.add(t)

    tiers = {}
    for f in files:
        if f in autorun:
            tiers[f] = "auto-run"
        elif f in oninv:
            tiers[f] = "on-invocation"
        elif kinds.get(f) == "markdown":
            tiers[f] = "static-text"
        else:
            tiers[f] = "on-demand"
    return tiers


def _fenced_lines(text):
    """Line numbers (1-based) inside fenced code blocks - used to soften markdown rules."""
    inside, out = False, set()
    for i, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            inside = not inside
            out.add(i)
            continue
        if inside:
            out.add(i)
    return out


def _scan_file(rel, text, kind, rules, vendor_domains):
    findings = []
    lines = text.splitlines()
    fenced = _fenced_lines(text) if kind == "markdown" else set()
    detector_file = bool(DETECTOR_FILE.search("/" + rel))
    for rule in rules:
        targets = rule.get("targets") or ["any"]
        if "any" not in targets and kind not in targets:
            continue
        rx, ex = rule["_re"], rule.get("_ex")
        req = rule.get("_req")
        for i, line in enumerate(lines, 1):
            if len(line) > MAX_LINE_LEN and rule["category"] != "OBF":
                continue
            if not rx.search(line):
                continue
            if ex and ex.search(line):
                continue
            if req and not req.search(line):
                continue
            sev = rule["severity"]
            notes = []
            # Detector definitions describe a pattern; they do not do the thing.
            if rule["category"] != "OBF" or "OBF-003" not in rule["id"]:
                is_detector = detector_file or bool(DETECTOR_LINE.search(line))
            else:
                is_detector = detector_file or bool(DETECTOR_LINE.search(line))
            if is_detector and SEV_RANK[sev] > 1:
                sev = "low"
                notes.append("looks like a detector/rule definition, not behaviour "
                             "- capped at low; confirm by reading the file")
            # A credential path or filename with no read, write or send on the
            # line is a mention, not an access. Cap it - never hide it, because
            # silent suppression is how real findings get lost (Law 1 applies to
            # our own output too).
            elif (rule["category"] in ("CRED", "FS") and SEV_RANK[sev] > 1
                    and not IO_VERB.search(line)):
                sev = "low"
                notes.append("path or name is mentioned, but nothing on this line "
                             "reads, writes or sends it - capped at low; read the "
                             "surrounding code before reporting")
            # A localhost destination is a much smaller blast radius.
            if rule["category"] == "NET" and LOCALHOST.search(line):
                sev = SEVERITIES[max(0, SEV_RANK[sev] - 2)]
                notes.append("localhost destination - downgraded")
            # Egress to a domain the user declared as the vendor's own.
            if rule["category"] == "NET" and vendor_domains:
                for host in URL_HOST.findall(line):
                    if any(host == d or host.endswith("." + d) for d in vendor_domains):
                        sev = SEVERITIES[max(0, SEV_RANK[sev] - 1)]
                        notes.append("declared vendor domain %s" % host)
                        break
            # Prose inside a fenced example block is usually a quoted example.
            if kind == "markdown" and i in fenced and rule["category"] == "PI":
                sev = SEVERITIES[max(0, SEV_RANK[sev] - 1)]
                notes.append("inside a fenced block - may be a quoted example")
            findings.append(dict(
                rule=rule["id"], title=rule["title"], category=rule["category"],
                severity=sev, declared_severity=rule["severity"], file=rel, line=i,
                snippet=line.strip()[:220], note=rule.get("note", ""),
                fp=rule.get("fp", ""), ask=rule.get("ask", ""),
                adjustments=notes,
            ))
    return findings


def audit(target, vendor_domains=None):
    rules, categories = _load_rules()
    vendor_domains = [d.lower().lstrip(".") for d in (vendor_domains or [])]
    root, files = _walk(target)

    texts, kinds, inventory, skipped = {}, {}, [], []
    for f in files:
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        text, why = _read(f)
        texts[f] = text or ""
        kind = _classify(rel, text)
        if why:
            kind = "asset" if why == "binary" else kind
            skipped.append({"file": rel, "reason": why})
        kinds[f] = kind
        inventory.append({"file": rel, "kind": kind,
                          "bytes": os.path.getsize(f) if os.path.exists(f) else 0})

    tiers = _detect_tiers(root, files, texts, kinds)

    skills, findings, egress = [], [], {}
    for f in files:
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        kind, text = kinds[f], texts[f]
        if os.path.basename(rel).lower() == "skill.md":
            fm = _frontmatter(text)
            skills.append({
                "file": rel,
                "name": fm.get("name", "(no name)"),
                "license": fm.get("license", "(unstated)"),
                "allowed_tools": fm.get("allowed-tools") or fm.get("allowed_tools") or "(unstated)",
                "description": (fm.get("description", "")[:400] or "(none)"),
            })
        if kind == "vendored":
            skipped.append({"file": rel, "reason": "vendored/minified - not line-scanned"})
            continue
        if kind == "asset" or not text:
            continue
        for host in URL_HOST.findall(text):
            if not LOCALHOST.search(host):
                egress[host] = egress.get(host, 0) + 1
        for fnd in _scan_file(rel, text, kind, rules, vendor_domains):
            fnd["tier"] = tiers.get(f, "on-demand")
            findings.append(fnd)

    findings.sort(key=lambda x: (-SEV_RANK[x["severity"]],
                                 -TIER_WEIGHT.get(x["tier"], 0), x["file"], x["line"]))
    detector_capped = sum(
        1 for f in findings
        if any("detector/rule definition" in a for a in f["adjustments"]))

    entrypoints = sorted(
        os.path.relpath(f, root).replace(os.sep, "/")
        for f, t in tiers.items() if t in ("auto-run", "on-invocation")
    )
    verdict, reasons = _pre_verdict(findings)
    return {
        "target": os.path.abspath(target),
        "skills": skills,
        "inventory": inventory,
        "file_count": len(files),
        "entrypoints": entrypoints,
        "tiers": {os.path.relpath(f, root).replace(os.sep, "/"): t for f, t in tiers.items()},
        "egress_hosts": sorted(egress),
        "findings": findings,
        "not_reviewed": skipped,
        "pre_verdict": verdict,
        "pre_verdict_reasons": reasons,
        "categories": categories,
        "counts": _counts(findings),
        "detector_capped": detector_capped,
    }


def _counts(findings):
    out = {"by_severity": {s: 0 for s in SEVERITIES},
           "by_tier": {t: 0 for t in TIERS}, "total": len(findings)}
    for f in findings:
        out["by_severity"][f["severity"]] = out["by_severity"].get(f["severity"], 0) + 1
        out["by_tier"][f["tier"]] = out["by_tier"].get(f["tier"], 0) + 1
    return out


STOP_RULES = {"SA-DYN-003", "SA-EXEC-005", "SA-OBF-003", "SA-CRED-001",
              "SA-CRED-002", "SA-CRED-003", "SA-NET-006",
              "SA-PI-001", "SA-PI-002", "SA-PI-003", "SA-PI-004", "SA-PI-006"}


def _pre_verdict(findings):
    """A machine pre-verdict. It is a starting point for the agent, never the answer."""
    reasons = []
    stop = [f for f in findings if f["rule"] in STOP_RULES]
    live_crit = [f for f in findings
                 if f["severity"] == "critical" and f["tier"] in ("auto-run", "on-invocation")]
    live_high = [f for f in findings
                 if f["severity"] == "high" and f["tier"] in ("auto-run", "on-invocation")]
    any_crit = [f for f in findings if f["severity"] == "critical"]
    any_high = [f for f in findings if f["severity"] == "high"]

    if stop:
        for f in stop[:6]:
            reasons.append("stop-and-warn rule %s at %s:%d" % (f["rule"], f["file"], f["line"]))
        return "DO-NOT-INSTALL (pending human confirmation)", reasons
    if live_crit:
        for f in live_crit[:6]:
            reasons.append("critical in the %s tier: %s at %s:%d"
                           % (f["tier"], f["rule"], f["file"], f["line"]))
        return "DO-NOT-INSTALL (pending human confirmation)", reasons
    if any_crit or live_high:
        for f in (any_crit + live_high)[:6]:
            reasons.append("%s %s in the %s tier at %s:%d"
                           % (f["severity"], f["rule"], f["tier"], f["file"], f["line"]))
        return "NEEDS-CAUTION", reasons
    if any_high:
        for f in any_high[:6]:
            reasons.append("high %s (on-demand only) at %s:%d" % (f["rule"], f["file"], f["line"]))
        return "NEEDS-CAUTION", reasons
    if findings:
        reasons.append("%d finding(s), none high or critical" % len(findings))
        return "SAFE-WITH-CAVEATS", reasons
    reasons.append("no pattern matched; this is not proof of safety - read the entrypoints")
    return "NO-PATTERNS-MATCHED", reasons


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def render_text(res, color=True):
    def c(t, code):
        return "\033[%sm%s\033[0m" % (code, t) if color else t
    sev_color = {"critical": "1;91", "high": "91", "medium": "93", "low": "96", "info": "90"}
    L = []
    L.append(c("Viora Aegis - SKILL-AUDIT (static only, target never executed)", "1;95"))
    L.append("target: %s" % res["target"])
    L.append("files: %d   findings: %d" % (res["file_count"], res["counts"]["total"]))
    L.append("")
    for s in res["skills"]:
        L.append(c("skill: ", "1") + "%s   (%s)" % (s["name"], s["file"]))
        L.append("  license:       %s" % s["license"])
        L.append("  allowed-tools: %s" % s["allowed_tools"])
    if res["skills"]:
        L.append("")
    L.append(c("ENTRYPOINTS TO READ BY HAND (mandatory):", "1;93"))
    if res["entrypoints"]:
        for e in res["entrypoints"]:
            L.append("  [%s] %s" % (res["tiers"].get(e, "?"), e))
    else:
        L.append("  (none detected - markdown-only skill, or the wiring is unusual: verify by hand)")
    L.append("")
    if res["egress_hosts"]:
        L.append(c("EGRESS HOSTS SEEN IN TEXT:", "1;93"))
        for h in res["egress_hosts"]:
            L.append("  %s" % h)
        L.append("")
    cs = res["counts"]
    L.append("severity: " + "  ".join(
        "%s=%d" % (s, cs["by_severity"][s]) for s in reversed(SEVERITIES)))
    L.append("tier:     " + "  ".join("%s=%d" % (t, cs["by_tier"][t]) for t in TIERS))
    if res.get("detector_capped"):
        L.append("note:     %d hit(s) look like rule/pattern definitions and were "
                 "capped at low." % res["detector_capped"])
        L.append("          That is normal when the target is itself a security scanner.")
    L.append("")
    for tier in TIERS:
        group = [f for f in res["findings"] if f["tier"] == tier]
        if not group:
            continue
        L.append(c("== tier: %s (%d) ==" % (tier, len(group)), "1;96"))
        for f in group:
            L.append("%s %s  %s:%d" % (c(f["severity"].upper().ljust(8),
                                         sev_color.get(f["severity"], "0")),
                                       f["rule"], f["file"], f["line"]))
            L.append("         %s" % f["title"])
            L.append("         | %s" % f["snippet"])
            if f["note"]:
                L.append("         judge: %s" % f["note"])
            if f["fp"]:
                L.append("         common FP: %s" % f["fp"])
            if f["adjustments"]:
                L.append("         adjusted: %s" % "; ".join(f["adjustments"]))
            L.append("")
    if res["not_reviewed"]:
        L.append(c("NOT REVIEWED (declare this in your verdict):", "1;93"))
        for s in res["not_reviewed"]:
            L.append("  %s - %s" % (s["file"], s["reason"]))
        L.append("")
    L.append(c("MACHINE PRE-VERDICT: %s" % res["pre_verdict"], "1;95"))
    for r in res["pre_verdict_reasons"]:
        L.append("  - %s" % r)
    L.append("")
    L.append("This is a pre-verdict, not the verdict. Before you answer the user you MUST:")
    L.append("  1. read every auto-run and on-invocation file listed above, in full;")
    L.append("  2. confirm or reject each finding at its file:line;")
    L.append("  3. state what you could not review;")
    L.append("  4. write the verdict using templates/SKILL_AUDIT_REPORT.md.")
    return "\n".join(L)


def render_markdown(res):
    L = ["# Skill audit - %s" % os.path.basename(res["target"].rstrip("/")), ""]
    L.append("Static analysis only. The target was **never executed**.")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append("| Target | `%s` |" % res["target"])
    L.append("| Files | %d |" % res["file_count"])
    L.append("| Findings | %d |" % res["counts"]["total"])
    L.append("| Machine pre-verdict | **%s** |" % res["pre_verdict"])
    if res.get("detector_capped"):
        L.append("| Detector definitions capped at low | %d |" % res["detector_capped"])
    L.append("")
    for s in res["skills"]:
        L.append("## Declared: `%s`" % s["name"])
        L.append("")
        L.append("- Manifest: `%s`" % s["file"])
        L.append("- License: %s" % s["license"])
        L.append("- Declared tools: `%s`" % s["allowed_tools"])
        L.append("- Purpose: %s" % s["description"])
        L.append("")
    L.append("## Entrypoints that must be read by hand")
    L.append("")
    if res["entrypoints"]:
        for e in res["entrypoints"]:
            L.append("- `%s` - tier **%s**" % (e, res["tiers"].get(e, "?")))
    else:
        L.append("- None detected. Either the skill is markdown-only or the wiring is unusual.")
    L.append("")
    if res["egress_hosts"]:
        L.append("## Network destinations found in text")
        L.append("")
        for h in res["egress_hosts"]:
            L.append("- `%s`" % h)
        L.append("")
    for tier in TIERS:
        group = [f for f in res["findings"] if f["tier"] == tier]
        if not group:
            continue
        L.append("## Tier: %s (%d)" % (tier, len(group)))
        L.append("")
        L.append("| Sev | Rule | Location | Title | Judge this |")
        L.append("|---|---|---|---|---|")
        for f in group:
            L.append("| %s | `%s` | `%s:%d` | %s | %s |" % (
                f["severity"].upper(), f["rule"], f["file"], f["line"],
                f["title"], (f["note"] or "").replace("|", "/")))
        L.append("")
    if res["not_reviewed"]:
        L.append("## Not reviewed")
        L.append("")
        for s in res["not_reviewed"]:
            L.append("- `%s` - %s" % (s["file"], s["reason"]))
        L.append("")
    L.append("## Machine pre-verdict")
    L.append("")
    L.append("**%s**" % res["pre_verdict"])
    L.append("")
    for r in res["pre_verdict_reasons"]:
        L.append("- %s" % r)
    L.append("")
    L.append("> A pre-verdict is a lead, not a conclusion. Confirm every finding at its")
    L.append("> `file:line`, read the auto-run and on-invocation tiers in full, and state")
    L.append("> what was not reviewed before giving the user an answer.")
    return "\n".join(L)


def run(args):
    res = audit(args.target, vendor_domains=(args.vendor_domain or []))
    if args.format == "json":
        out = json.dumps(res, indent=2, ensure_ascii=False)
    elif args.format == "markdown":
        out = render_markdown(res)
    else:
        out = render_text(res, color=sys.stdout.isatty() and not os.environ.get("NO_COLOR"))
    if args.out:
        d = os.path.dirname(os.path.abspath(args.out))
        if d:
            os.makedirs(d, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
        if args.format != "json":
            print(out)
        print("\n-> written to %s" % args.out)
    else:
        print(out)

    gate = (args.fail_on or "none").lower()
    if gate != "none":
        threshold = SEV_RANK.get(gate, 3)
        if any(SEV_RANK[f["severity"]] >= threshold for f in res["findings"]):
            return 1
    return 0
