#!/usr/bin/env python3
"""find_duplicates.py - find code that already exists before you write it again.

This is the anti-slop scanner. It reports three kinds of duplication that make
agent-written code collapse under its own weight:

  1. CLONES     - near-identical blocks of logic in 2+ places (normalized match)
  2. SYMBOLS    - the same function / class / component name declared in 2+ files
  3. LITERALS   - the same magic string repeated 3+ times (route keys, ids, labels)

Usage:
    python3 find_duplicates.py [ROOT] [--min-lines 8] [--top 15] [--include-tests] [--json]

Read the report BEFORE creating a new file, component, helper or constant:
  * a hit in SYMBOLS means you are about to create a second owner of one concept
  * a hit in CLONES means the behavior exists; extend the existing owner instead
  * a hit in LITERALS means the value needs one exported constant, not copies

No network. No writes. Stdlib only. Heuristic by design: every hit is a lead to
confirm by reading the code, not an automatic defect.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "dist", "build", "out", ".next", ".nuxt",
    "vendor", "venv", ".venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "target", "obj", ".gradle", ".idea", ".vscode", "coverage",
    ".turbo", ".cache", "Pods", "site-packages", ".terraform", ".svelte-kit",
    "migrations", "__snapshots__",
}
CODE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go",
    ".rs", ".java", ".kt", ".swift", ".rb", ".php", ".cs", ".c", ".h", ".cc", ".cpp",
    ".hpp", ".dart", ".scala", ".sh", ".css", ".scss",
}
TEST_RE = re.compile(r"(^|[/\\])(tests?|__tests__|spec|e2e|fixtures?)([/\\]|$)|\.(test|spec)\.[a-z]+$", re.I)
GENERATED_RE = re.compile(r"(\.min\.|\.d\.ts$|generated|\.pb\.|_pb2|lock)", re.I)

SYMBOL_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"),
    re.compile(r"^\s*def\s+([A-Za-z_][\w]*)\s*\("),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)\s*\("),
    re.compile(r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:fun|fn)\s+([A-Za-z_][\w]*)"),
    re.compile(r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*="),
]
COMMON_SYMBOLS = {
    "main", "init", "__init__", "setup", "teardown", "run", "handler", "handle",
    "index", "default", "config", "props", "state", "toString", "render", "new",
    "get", "set", "post", "put", "delete", "test", "describe", "it", "expect",
    "String", "Error", "Options", "Props", "Result", "Module", "Config",
}
STRING_RE = re.compile(r"""["']([^"'\n]{6,80})["']""")
WORD_RE = re.compile(r"^[\w./:@ -]+$")
NOISE_LITERALS = re.compile(r"^(utf-?8|https?://(localhost|example)|[\d.\s]+|[a-z]{1,3})$", re.I)
STOPWORD_LITERALS = {
    "__main__", "__init__", "default", "result", "results", "passed", "failed",
    "error", "errors", "warning", "warnings", "true", "false", "none", "null",
    "content", "string", "number", "object", "status", "message", "data", "name",
    "value", "type", "types", "unknown", "success", "output", "input", "options",
}
INTERESTING_LITERAL = re.compile(r"[./:_-]")


def walk(root, include_tests):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.splitext(name)[1].lower() not in CODE_EXT:
                continue
            rel = os.path.relpath(path, root)
            if GENERATED_RE.search(rel):
                continue
            if not include_tests and TEST_RE.search(rel):
                continue
            yield rel, path


def normalize(line):
    """Collapse a code line to its shape so cosmetic edits still match."""
    s = line.strip()
    if not s or s.startswith(("//", "#", "*", "/*", "--", "<!--")):
        return ""
    if re.match(r"^(import|from|use|using|require|package|include|@)\b", s):
        return ""
    s = re.sub(r"""["'][^"']*["']""", '"S"', s)
    s = re.sub(r"\b\d+(\.\d+)?\b", "N", s)
    s = re.sub(r"\s+", "", s)
    return s if len(s) >= 12 else ""


def scan_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find duplicated logic, symbols and literals.")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--min-lines", type=int, default=8, help="clone window size in significant lines")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--include-tests", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("not a directory: %s" % root, file=sys.stderr)
        return 2

    windows = defaultdict(list)          # hash -> [(rel, start_line, end_line)]
    symbols = defaultdict(list)          # name -> [(rel, line)]
    literals = Counter()
    literal_places = defaultdict(set)
    files = 0

    for rel, path in walk(root, args.include_tests):
        files += 1
        lines = scan_file(path)
        significant = []
        for idx, raw in enumerate(lines, start=1):
            norm = normalize(raw)
            if norm:
                significant.append((idx, norm))
            for pattern in SYMBOL_PATTERNS:
                m = pattern.match(raw)
                if m:
                    name = m.group(1)
                    if name not in COMMON_SYMBOLS and len(name) > 2:
                        symbols[name].append((rel, idx))
                    break
            for lit in STRING_RE.findall(raw):
                clean = lit.strip()
                if not clean or not WORD_RE.match(clean) or NOISE_LITERALS.match(clean):
                    continue
                if clean.lower() in STOPWORD_LITERALS:
                    continue
                literals[clean] += 1
                literal_places[clean].add(rel)

        k = args.min_lines
        for i in range(0, max(0, len(significant) - k + 1)):
            chunk = significant[i:i + k]
            digest = hashlib.sha1("\n".join(c[1] for c in chunk).encode()).hexdigest()
            windows[digest].append((rel, chunk[0][0], chunk[-1][0]))

    def merge_windows(places):
        """Collapse sliding windows that describe one and the same block."""
        merged = []
        for rel, start, end in sorted(places):
            if merged and merged[-1][0] == rel and start <= merged[-1][2]:
                merged[-1] = (rel, merged[-1][1], max(end, merged[-1][2]))
            else:
                merged.append((rel, start, end))
        return merged

    clusters = []
    for digest, places in windows.items():
        merged = merge_windows(places)
        if len(merged) >= 2:
            clusters.append(merged)
    clusters.sort(key=lambda m: (-len(m), -sum(e - s for _, s, e in m)))

    claimed = defaultdict(list)

    def is_claimed(rel, start, end):
        return any(not (end < cs or start > ce) for cs, ce in claimed[rel])

    clones = []
    for merged in clusters:
        fresh = [p for p in merged if not is_claimed(*p)]
        distinct_files = {p[0] for p in fresh}
        if len(fresh) < 2 or (len(distinct_files) == 1 and len(fresh) < 3):
            continue
        for rel, start, end in fresh:
            claimed[rel].append((start, end))
        clones.append({
            "copies": len(fresh),
            "files": len(distinct_files),
            "lines": max(e - s + 1 for _, s, e in fresh),
            "places": ["%s:%d-%d" % p for p in fresh[:6]],
        })
    clones.sort(key=lambda c: (-c["copies"], -c["lines"]))

    dup_symbols = []
    for name, places in symbols.items():
        distinct = sorted({p[0] for p in places})
        if len(distinct) >= 2:
            dup_symbols.append({
                "name": name,
                "files": len(distinct),
                "places": ["%s:%d" % p for p in sorted(places)[:6]],
            })
    dup_symbols.sort(key=lambda s: (-s["files"], s["name"]))

    dup_literals = [
        {"value": lit, "count": n, "files": sorted(literal_places[lit])[:5]}
        for lit, n in literals.most_common(300)
        if n >= 3 and len(literal_places[lit]) >= 2
        and (INTERESTING_LITERAL.search(lit) or n >= 6)
    ][:args.top]

    result = {
        "root": root, "files_scanned": files,
        "clones": clones[:args.top],
        "duplicate_symbols": dup_symbols[:args.top],
        "repeated_literals": dup_literals,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if (clones or dup_symbols) else 0

    out = ["# Duplication report: %s" % root, "", "files scanned: %d" % files, ""]
    out.append("## 1. Clones (same logic, %d+ significant lines)" % args.min_lines)
    if not result["clones"]:
        out.append("- none found")
    for c in result["clones"]:
        out.append("- x%d copies (~%d lines each) in %d files: %s"
                   % (c["copies"], c["lines"], c["files"], "  |  ".join(c["places"])))
    out.append("")
    out.append("## 2. Same name declared in several files (two owners of one concept)")
    if not result["duplicate_symbols"]:
        out.append("- none found")
    for s in result["duplicate_symbols"]:
        out.append("- %-28s %d files: %s" % (s["name"], s["files"], "  |  ".join(s["places"])))
    out.append("")
    out.append("## 3. Repeated literals (need one exported constant)")
    if not result["repeated_literals"]:
        out.append("- none found")
    for l in result["repeated_literals"]:
        out.append("- x%-3d %-40s %s" % (l["count"], l["value"][:40], ", ".join(l["files"])))
    out.append("")
    out.append("Every hit is a lead: open the files, confirm, then reuse or consolidate.")
    print("\n".join(out))
    return 1 if (result["clones"] or result["duplicate_symbols"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
