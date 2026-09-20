#!/usr/bin/env python3
"""less.py - rank what this repository could delete, not what it should add.

Why this exists: an agent's default instinct is to write. Every line it writes is
a line somebody owns forever. This script answers one question with grep-level
determinism - what here is already carried by the platform, by the standard
library, or by nobody at all?

Out of scope, on purpose: correctness, security and performance. A finding here
means "this costs more than it earns", never "this is broken". Deleting something
this script names still needs the ten steps and a green gate.

Findings are tagged:

    delete:   nothing reads it
    stdlib:   the standard library already does this
    native:   the platform/runtime already does this
    yagni:    one caller, one implementation - the abstraction has not earned its name
    shrink:   config or wrapper that only forwards

Usage:
    python3 scripts/less.py .
    python3 scripts/less.py . --top 10

Execute it, never read it. Stdlib only, Python 3.8+, offline.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Dependencies the platform replaced. Each pair is (package, replacement, lines saved).
# The number is the rough cost of keeping it: install, lockfile churn, audit noise.
JS_REPLACEMENTS = [
    ("lodash", "native: destructuring, Array.prototype, structuredClone", 40),
    ("lodash.get", "native: optional chaining a?.b?.c", 20),
    ("underscore", "native: Array/Object methods", 30),
    ("moment", "native: Intl.DateTimeFormat / Temporal", 50),
    ("dayjs", "native: Intl.DateTimeFormat for formatting", 30),
    ("date-fns", "native: Intl for format, Date arithmetic for the rest", 25),
    ("axios", "native: fetch()", 35),
    ("request", "native: fetch()", 40),
    ("node-fetch", "native: global fetch (Node 18+)", 15),
    ("isomorphic-fetch", "native: global fetch (Node 18+)", 15),
    ("uuid", "native: crypto.randomUUID()", 15),
    ("nanoid", "native: crypto.randomUUID() when the length is not the point", 12),
    ("classnames", "native: template literal or array.filter(Boolean).join(' ')", 10),
    ("clsx", "native: template literal", 10),
    ("bluebird", "native: Promise", 30),
    ("q", "native: Promise", 30),
    ("left-pad", "native: String.prototype.padStart", 5),
    ("is-odd", "native: n % 2 !== 0", 3),
    ("is-number", "native: typeof n === 'number'", 3),
    ("object-assign", "native: Object.assign / spread", 5),
    ("querystring", "native: URLSearchParams", 12),
    ("qs", "native: URLSearchParams", 18),
    ("rimraf", "native: fs.rm(path, {recursive: true})", 8),
    ("mkdirp", "native: fs.mkdir(path, {recursive: true})", 8),
    ("dotenv", "native: node --env-file=.env (Node 20+)", 10),
    ("chalk", "native: ANSI escapes, or util.styleText (Node 20+)", 10),
    ("glob", "native: fs.glob (Node 22+) for simple patterns", 12),
    ("deep-equal", "native: node:assert deepStrictEqual, or structuredClone + JSON", 15),
]

PY_REPLACEMENTS = [
    ("pytz", "stdlib: zoneinfo (3.9+)", 20),
    ("mock", "stdlib: unittest.mock", 10),
    ("six", "stdlib: drop it, Python 2 is gone", 25),
    ("simplejson", "stdlib: json", 10),
    ("attrs", "stdlib: dataclasses", 20),
    ("enum34", "stdlib: enum", 8),
    ("pathlib2", "stdlib: pathlib", 8),
    ("typing-extensions", "stdlib: typing, if you are on a recent Python", 6),
    ("requests", "stdlib: urllib.request for a single call", 25),
    ("python-dateutil", "stdlib: datetime.fromisoformat for ISO input", 18),
    ("ujson", "stdlib: json", 8),
    ("toml", "stdlib: tomllib (3.11+)", 10),
    ("dataclasses", "stdlib: built in since 3.7", 5),
    ("futures", "stdlib: concurrent.futures", 8),
    ("funcsigs", "stdlib: inspect.signature", 6),
    ("contextlib2", "stdlib: contextlib", 6),
    ("backports.zoneinfo", "stdlib: zoneinfo (3.9+)", 8),
    ("nose", "stdlib: unittest, or pytest if it is already there", 20),
]

# Tool config files that cost a file and a review each, with nothing behind them.
TOOL_CONFIGS = {
    ".eslintrc": "eslint", ".eslintrc.js": "eslint", ".eslintrc.json": "eslint",
    ".prettierrc": "prettier", ".prettierrc.json": "prettier",
    "jest.config.js": "jest", "vitest.config.ts": "vitest",
    "babel.config.js": "@babel/core", ".babelrc": "@babel/core",
    "webpack.config.js": "webpack", "rollup.config.js": "rollup",
    ".flake8": "flake8", "mypy.ini": "mypy", ".isort.cfg": "isort",
    "tox.ini": "tox",
}

SKIP_DIRS = {
    ".git", ".viora", "node_modules", "__pycache__", ".venv", "venv", "dist",
    "build", ".next", ".nuxt", "target", "coverage", "vendor", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".turbo",
}

PY_WRAPPER_RE = re.compile(
    r"^(\s*)def\s+(\w+)\s*\(([^)]*)\)[^:]*:\s*\n\s+return\s+(\w+)\s*\(", re.MULTILINE
)
JS_WRAPPER_RE = re.compile(
    r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:\([^)]*\)|\w+)\s*=>)\s*\{?\s*"
    r"return\s+(\w+)\s*\(", re.MULTILINE
)
PY_DEF_RE = re.compile(r"^\s*(?:class|def)\s+(\w+)", re.MULTILINE)
JS_EXPORT_RE = re.compile(r"export\s+(?:default\s+)?(?:const|function|class)\s+(\w+)")


def walk(root: Path, exts):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix in exts:
                yield p


def read(p: Path) -> str:
    try:
        if p.stat().st_size > 400_000:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def declared_deps(root: Path):
    """Package name -> True, across package.json and the usual Python manifests."""
    deps = {}
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(read(pkg) or "{}")
            for key in ("dependencies", "devDependencies"):
                for name in (data.get(key) or {}):
                    deps[name] = "js"
        except ValueError:
            pass
    req = root / "requirements.txt"
    if req.exists():
        for line in read(req).splitlines():
            name = re.split(r"[=<>!\[; ]", line.strip(), maxsplit=1)[0]
            if name and not name.startswith("#"):
                deps[name.lower()] = "py"
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        for m in re.finditer(r'"([A-Za-z0-9_.\-]+)\s*[=<>~!]*[^"]*"', read(pyproject)):
            deps[m.group(1).lower()] = "py"
    return deps


def find_replaceable(root: Path, deps):
    out = []
    for name, replacement, saved in JS_REPLACEMENTS:
        if name in deps:
            tag = replacement.split(":", 1)[0]
            out.append((saved, tag, "package.json", "%s -> %s" % (name, replacement.split(": ", 1)[1]), 1))
    for name, replacement, saved in PY_REPLACEMENTS:
        key = name.lower()
        if key in deps or any(key == d for d in deps):
            tag = replacement.split(":", 1)[0]
            out.append((saved, tag, "requirements", "%s -> %s" % (name, replacement.split(": ", 1)[1]), 1))
    # Imported but never declared is still a dependency the reader must own.
    for p in walk(root, {".py"}):
        text = read(p)
        for name, replacement, saved in PY_REPLACEMENTS:
            mod = name.replace("-", "_").split(".")[0]
            if re.search(r"^\s*(?:import|from)\s+%s\b" % re.escape(mod), text, re.MULTILINE):
                tag = replacement.split(":", 1)[0]
                out.append((saved, tag, str(p.relative_to(root)),
                            "%s -> %s" % (name, replacement.split(": ", 1)[1]), 1))
    return out


def find_wrappers(root: Path):
    out = []
    for p in walk(root, {".py"}):
        text = read(p)
        for m in PY_WRAPPER_RE.finditer(text):
            name, inner = m.group(2), m.group(4)
            if name != inner and not name.startswith("_"):
                line = text[:m.start()].count("\n") + 1
                out.append((4, "shrink", "%s:%d" % (p.relative_to(root), line),
                            "%s() only forwards to %s() - call %s directly"
                            % (name, inner, inner), 0))
    for p in walk(root, {".js", ".ts", ".jsx", ".tsx"}):
        text = read(p)
        for m in JS_WRAPPER_RE.finditer(text):
            name = m.group(1) or m.group(2)
            inner = m.group(3)
            if name and name != inner:
                line = text[:m.start()].count("\n") + 1
                out.append((4, "shrink", "%s:%d" % (p.relative_to(root), line),
                            "%s() only forwards to %s() - call %s directly"
                            % (name, inner, inner), 0))
    return out


def find_single_caller(root: Path):
    """Names defined once and referenced once: an abstraction with one caller."""
    defs = {}
    texts = {}
    for p in walk(root, {".py", ".js", ".ts", ".jsx", ".tsx"}):
        text = read(p)
        texts[p] = text
        rx = PY_DEF_RE if p.suffix == ".py" else JS_EXPORT_RE
        for m in rx.finditer(text):
            name = m.group(1)
            if len(name) < 4 or name.startswith("_") or name.startswith("test"):
                continue
            defs.setdefault(name, []).append((p, text[:m.start()].count("\n") + 1))
    out = []
    for name, places in defs.items():
        if len(places) != 1:
            continue
        uses = sum(len(re.findall(r"\b%s\b" % re.escape(name), t)) for t in texts.values())
        if uses <= 2:  # the definition plus at most one caller
            p, line = places[0]
            out.append((6, "yagni", "%s:%d" % (p.relative_to(root), line),
                        "%s has %d reference(s) - inline it or delete it"
                        % (name, max(0, uses - 1)), 0))
    return out


def find_orphan_configs(root: Path, deps):
    out = []
    for fname, tool in TOOL_CONFIGS.items():
        p = root / fname
        if p.exists() and tool not in deps and tool.lower() not in deps:
            out.append((8, "delete", fname,
                        "config for %s, which is not in the dependencies - delete it or install the tool"
                        % tool, 0))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="less.py",
        description=(
            "Rank what can be deleted, simplified or replaced by the platform. "
            "Correctness, security and performance are out of scope: a finding means "
            "'this costs more than it earns', never 'this is broken'."
        ),
    )
    ap.add_argument("root", nargs="?", default=".", help="repository root")
    ap.add_argument("--top", type=int, default=25, help="how many findings to print")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write("less: %s is not a directory\n" % root)
        return 2

    deps = declared_deps(root)
    findings = []
    findings += find_replaceable(root, deps)
    findings += find_wrappers(root)
    findings += find_single_caller(root)
    findings += find_orphan_configs(root, deps)

    if not findings:
        print("Lean already. Nothing here is carried by the platform or unreferenced.")
        return 0

    findings.sort(key=lambda f: -f[0])
    seen = set()
    shown, lines_saved, deps_saved = 0, 0, 0
    for saved, tag, where, text, is_dep in findings:
        key = (tag, where, text)
        if key in seen:
            continue
        seen.add(key)
        if shown >= args.top:
            continue
        print("%-8s %s - %s" % (tag + ":", where, text))
        shown += 1
        lines_saved += saved
        deps_saved += is_dep
    print("")
    print("net: -%d lines, -%d deps possible" % (lines_saved, deps_saved))
    print("Every cut still runs the ten steps. A deletion with no green gate is a new bug.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
