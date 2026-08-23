#!/usr/bin/env python3
"""scan_repo.py - fast, read-only reconnaissance of an unfamiliar repository.

Run this BEFORE writing code. It answers, cheaply and deterministically:
  * which stack / package managers / frameworks are in play
  * which commands the repo itself defines (lint, test, build, typecheck)
  * which instruction files the agent must obey (AGENTS.md, CLAUDE.md, .cursorrules, ...)
  * where the entrypoints are, and which files are dangerously large

Usage:
    python3 scan_repo.py [ROOT] [--top N] [--json]

No network. No writes. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "dist", "build", "out", ".next", ".nuxt",
    "vendor", "venv", ".venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "target", "obj", ".gradle", ".idea", ".vscode", "coverage",
    ".turbo", ".cache", "Pods", "site-packages", ".terraform", ".svelte-kit",
}
CODE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go",
    ".rs", ".java", ".kt", ".kts", ".swift", ".rb", ".php", ".cs", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".m", ".mm", ".dart", ".scala", ".sh", ".bash", ".sql",
    ".css", ".scss", ".less", ".html", ".htm",
}
STACK_MARKERS = [
    ("package.json", "node"), ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
    ("package-lock.json", "npm"), ("bun.lockb", "bun"), ("deno.json", "deno"),
    ("pyproject.toml", "python"), ("requirements.txt", "python"), ("setup.py", "python"),
    ("Pipfile", "python"), ("go.mod", "go"), ("Cargo.toml", "rust"),
    ("pom.xml", "java-maven"), ("build.gradle", "java-gradle"), ("build.gradle.kts", "java-gradle"),
    ("Gemfile", "ruby"), ("composer.json", "php"), ("Makefile", "make"),
    ("Dockerfile", "docker"), ("docker-compose.yml", "docker"), ("compose.yaml", "docker"),
    ("tsconfig.json", "typescript"), ("next.config.js", "nextjs"), ("next.config.ts", "nextjs"),
    ("vite.config.ts", "vite"), ("vite.config.js", "vite"), ("webpack.config.js", "webpack"),
    ("tailwind.config.js", "tailwind"), ("tailwind.config.ts", "tailwind"),
    ("eslint.config.js", "eslint"), (".eslintrc", "eslint"), (".eslintrc.json", "eslint"),
    (".prettierrc", "prettier"), ("biome.json", "biome"), ("ruff.toml", "ruff"),
    ("pytest.ini", "pytest"), ("tox.ini", "tox"), ("jest.config.js", "jest"),
    ("vitest.config.ts", "vitest"), ("playwright.config.ts", "playwright"),
    ("cypress.config.ts", "cypress"), ("pubspec.yaml", "flutter"),
]
INSTRUCTION_FILES = [
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "CONVENTIONS.md", "CONTRIBUTING.md",
    ".cursorrules", ".windsurfrules", ".github/copilot-instructions.md",
    "docs/architecture.md", "ARCHITECTURE.md", "STYLEGUIDE.md", "CODEOWNERS",
]
ENTRY_RE = re.compile(r"(^|[/\\])(main|index|app|server|cli|__main__|entry|bootstrap|routes?)\.[a-z]+$", re.I)
TEST_RE = re.compile(r"(^|[/\\])(tests?|__tests__|spec|e2e)([/\\]|$)|\.(test|spec)\.[a-z]+$", re.I)


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".egg")]
        for name in filenames:
            yield os.path.join(dirpath, name)


def count_lines(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().count(b"\n") + 1
    except OSError:
        return 0


def read_text(path, limit=200_000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(limit)
    except OSError:
        return ""


def npm_scripts(root):
    path = os.path.join(root, "package.json")
    if not os.path.exists(path):
        return {}
    try:
        data = json.loads(read_text(path))
    except ValueError:
        return {}
    scripts = data.get("scripts") or {}
    return {k: v for k, v in scripts.items() if isinstance(v, str)}


def make_targets(root):
    path = os.path.join(root, "Makefile")
    if not os.path.exists(path):
        return []
    found = []
    for line in read_text(path).splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+):(?!=)", line)
        if m and m.group(1) not in found:
            found.append(m.group(1))
    return found[:30]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only repository reconnaissance.")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--top", type=int, default=12, help="how many largest files to list")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("not a directory: %s" % root, file=sys.stderr)
        return 2

    ext_counter, ext_lines = Counter(), Counter()
    sizes, entries, test_files, total_files = [], [], 0, 0
    for path in walk(root):
        total_files += 1
        rel = os.path.relpath(path, root)
        ext = os.path.splitext(path)[1].lower()
        if ext not in CODE_EXT:
            continue
        lines = count_lines(path)
        ext_counter[ext] += 1
        ext_lines[ext] += lines
        sizes.append((lines, rel))
        if TEST_RE.search(rel):
            test_files += 1
        elif ENTRY_RE.search(rel):
            entries.append(rel)

    stack = sorted({label for marker, label in STACK_MARKERS
                    if os.path.exists(os.path.join(root, marker))})
    instructions = [f for f in INSTRUCTION_FILES if os.path.exists(os.path.join(root, f))]
    sizes.sort(reverse=True)
    scripts = npm_scripts(root)
    targets = make_targets(root)

    result = {
        "root": root,
        "files_scanned": total_files,
        "code_files": sum(ext_counter.values()),
        "code_lines": sum(ext_lines.values()),
        "test_files": test_files,
        "stack": stack,
        "instruction_files": instructions,
        "languages": [{"ext": e, "files": c, "lines": ext_lines[e]}
                      for e, c in ext_counter.most_common(10)],
        "entrypoints": sorted(entries)[:15],
        "largest_files": [{"lines": n, "path": p} for n, p in sizes[:args.top]],
        "npm_scripts": scripts,
        "make_targets": targets,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    out = ["# Repo recon: %s" % root, ""]
    out.append("- code files: %d | code lines: %d | test files: %d"
               % (result["code_files"], result["code_lines"], test_files))
    out.append("- stack: %s" % (", ".join(stack) or "unknown"))
    out.append("- instruction files to obey: %s" % (", ".join(instructions) or "none found"))
    out.append("")
    out.append("## Languages")
    for item in result["languages"]:
        out.append("- %-7s %4d files  %7d lines" % (item["ext"], item["files"], item["lines"]))
    out.append("")
    out.append("## Repo-defined commands (use these, do not invent your own)")
    if scripts:
        for key in sorted(scripts):
            out.append("- npm run %-16s -> %s" % (key, scripts[key][:110]))
    if targets:
        out.append("- make targets: %s" % ", ".join(targets))
    if not scripts and not targets:
        out.append("- none declared; look for CI config before inventing commands")
    out.append("")
    out.append("## Entrypoints")
    for e in result["entrypoints"] or ["(none matched)"]:
        out.append("- %s" % e)
    out.append("")
    out.append("## Largest files (split candidates / hard to reason about)")
    for item in result["largest_files"]:
        flag = "  <-- over 400 lines" if item["lines"] > 400 else ""
        out.append("- %6d  %s%s" % (item["lines"], item["path"], flag))
    if test_files == 0:
        out.append("")
        out.append("WARNING: no test files found. Expect no safety net; add the one test that proves your change.")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
