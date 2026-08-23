#!/usr/bin/env python3
"""ui_guard.py - static guard against overlapping UI, leaks and layout wars.

This targets the exact failure mode of agent-written frontends: two interfaces
mounted at once, one overlay covering another, z-index escalation, listeners that
are never removed, and styles that silently overwrite each other.

Checks:
  M1  several app mount / render roots (createRoot, ReactDOM.render, createApp, new Vue, mount)
  M2  raw appendChild to document.body without an existing-node guard (duplicate portals)
  M3  duplicate HTML id attributes (broken queries, duplicated surfaces)
  Z1  z-index literals outside a token file; any value >= 1000 (escalation war)
  Z2  !important usage
  Z3  full-viewport overlays (position:fixed + inset/top:0) - count per file
  L1  addEventListener without a matching removeEventListener in the same file
  L2  setInterval without clearInterval
  L3  observers / subscriptions without disconnect / unsubscribe / abort
  C1  the same CSS class defined in 2+ files (collision / silent override)
  C2  global selectors in CSS (bare tag, *, body >) outside reset files

Usage:
    python3 ui_guard.py [ROOT] [--strict] [--json]

Exit code: 0 clean, 1 findings (with --strict any finding fails). Heuristic:
confirm each hit by reading the code. No network. No writes. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", ".next", ".nuxt", "vendor",
    "venv", ".venv", "__pycache__", "coverage", ".turbo", ".cache", ".svelte-kit",
    "target", ".idea", ".vscode", "storybook-static",
}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".html", ".htm"}
CSS_EXT = {".css", ".scss", ".less", ".sass"}
TEST_RE = re.compile(r"(^|[/\\])(tests?|__tests__|spec|e2e|stories)([/\\]|$)|\.(test|spec|stories)\.[a-z]+$", re.I)
TOKEN_FILE_RE = re.compile(r"(token|theme|variable|z-?index|design-system|foundation|reset|normalize)", re.I)

MOUNT_RE = re.compile(r"\b(createRoot\s*\(|ReactDOM\.render\s*\(|hydrateRoot\s*\(|createApp\s*\(|new\s+Vue\s*\(|mount\s*\(\s*(?:document|['\"]#)|\.mount\s*\(\s*['\"#])")
BODY_APPEND_RE = re.compile(r"document\.body\.appendChild\s*\(|document\.body\.append\s*\(")
GUARD_RE = re.compile(r"(querySelector|getElementById|getElementsByClassName|existing|already|if\s*\(!)")
ID_ATTR_RE = re.compile(r"""\bid\s*=\s*["']([A-Za-z][\w:-]*)["']""")
ZINDEX_RE = re.compile(r"z-?index\s*[:=]\s*[\"']?(-?\d{1,6})")
IMPORTANT_RE = re.compile(r"!important")
FIXED_OVERLAY_RE = re.compile(r"position\s*:\s*(fixed|absolute)")
INSET_RE = re.compile(r"(inset\s*:\s*0|top\s*:\s*0[^;]*;\s*left\s*:\s*0)")
ADD_LISTENER_RE = re.compile(r"addEventListener\s*\(")
REMOVE_LISTENER_RE = re.compile(r"removeEventListener\s*\(|AbortController|\{\s*signal\s*\}|signal\s*:")
SET_INTERVAL_RE = re.compile(r"setInterval\s*\(")
CLEAR_INTERVAL_RE = re.compile(r"clearInterval\s*\(")
OBSERVER_RE = re.compile(r"new\s+(ResizeObserver|IntersectionObserver|MutationObserver|PerformanceObserver)\s*\(|\.subscribe\s*\(")
OBSERVER_STOP_RE = re.compile(r"\.disconnect\s*\(|\.unobserve\s*\(|\.unsubscribe\s*\(|\.abort\s*\(")
CSS_CLASS_RE = re.compile(r"^\s*\.([A-Za-z_][\w-]{2,})[\s,{:]", re.M)
GLOBAL_SELECTOR_RE = re.compile(r"^\s*(\*|body\s*>|html\s*>|(?:div|span|p|a|ul|li|button|input|section|h[1-6])\s*(?:\{|,))", re.M)


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in JS_EXT or ext in CSS_EXT:
                yield os.path.relpath(path, root), path, ext


def read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Static guard for overlapping UI and leaks.")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("not a directory: %s" % root, file=sys.stderr)
        return 2

    findings = defaultdict(list)
    mounts, zvalues = [], []
    ids = defaultdict(list)
    css_classes = defaultdict(set)
    scanned = 0

    for rel, path, ext in walk(root):
        if TEST_RE.search(rel):
            continue
        text = read(path)
        if not text:
            continue
        scanned += 1
        is_token_file = bool(TOKEN_FILE_RE.search(rel))

        if ext in JS_EXT:
            for m in MOUNT_RE.finditer(text):
                mounts.append("%s:%d" % (rel, line_of(text, m.start())))
            for m in BODY_APPEND_RE.finditer(text):
                start = max(0, m.start() - 400)
                if not GUARD_RE.search(text[start:m.start()]):
                    findings["M2 unguarded document.body.appendChild (duplicate overlay risk)"].append(
                        "%s:%d" % (rel, line_of(text, m.start())))
            for m in ID_ATTR_RE.finditer(text):
                ids[m.group(1)].append("%s:%d" % (rel, line_of(text, m.start())))
            adds = len(ADD_LISTENER_RE.findall(text))
            if adds and not REMOVE_LISTENER_RE.search(text):
                findings["L1 addEventListener without removal/AbortController"].append(
                    "%s (x%d)" % (rel, adds))
            iv = len(SET_INTERVAL_RE.findall(text))
            if iv and not CLEAR_INTERVAL_RE.search(text):
                findings["L2 setInterval without clearInterval"].append("%s (x%d)" % (rel, iv))
            obs = len(OBSERVER_RE.findall(text))
            if obs and not OBSERVER_STOP_RE.search(text):
                findings["L3 observer/subscription without teardown"].append("%s (x%d)" % (rel, obs))

        for m in ZINDEX_RE.finditer(text):
            value = int(m.group(1))
            place = "%s:%d (z=%d)" % (rel, line_of(text, m.start()), value)
            zvalues.append((value, rel, place, is_token_file))
            if value >= 1000:
                findings["Z1 z-index >= 1000 (escalation war)"].append(place)

        imp = len(IMPORTANT_RE.findall(text))
        if imp:
            findings["Z2 !important (silently overrides another owner)"].append("%s (x%d)" % (rel, imp))

        if FIXED_OVERLAY_RE.search(text) and INSET_RE.search(text):
            findings["Z3 full-viewport overlay (can cover another surface)"].append(rel)

        if ext in CSS_EXT:
            for name in set(CSS_CLASS_RE.findall(text)):
                css_classes[name].add(rel)
            if not is_token_file:
                hits = GLOBAL_SELECTOR_RE.findall(text)
                if len(hits) >= 3:
                    findings["C2 global element selectors outside reset/token file"].append(
                        "%s (x%d)" % (rel, len(hits)))

    if len(mounts) > 1:
        findings["M1 several app mount/render roots (two UIs can run at once)"] = mounts
    for name, places in ids.items():
        if len(places) > 1:
            findings["M3 duplicate DOM id"].append("#%s -> %s" % (name, ", ".join(places[:5])))
    non_token_z = {v for v, rel, place, tok in zvalues if not tok}
    if len(non_token_z) > 3:
        findings["Z1 z-index literals scattered outside a token file"].append(
            "%d distinct values: %s" % (len(non_token_z), sorted(non_token_z)[:12]))
    for name, files in css_classes.items():
        if len(files) >= 2:
            findings["C1 same CSS class defined in several files"].append(
                ".%s -> %s" % (name, ", ".join(sorted(files)[:4])))

    total = sum(len(v) for v in findings.values())
    result = {
        "root": root,
        "files_scanned": scanned,
        "mount_points": mounts,
        "findings": {k: v[:12] for k, v in findings.items()},
        "finding_count": total,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if (args.strict and total) else 0

    out = ["# UI integrity report: %s" % root, "", "files scanned: %d | findings: %d" % (scanned, total), ""]
    if not findings:
        out.append("No structural UI risks found by static scan. Still verify rendered output.")
    for key in sorted(findings):
        out.append("## %s" % key)
        for place in findings[key][:12]:
            out.append("- %s" % place)
        if len(findings[key]) > 12:
            out.append("- ... +%d more" % (len(findings[key]) - 12))
        out.append("")
    out.append("Rules: one mount root, one overlay layer, z-index only from tokens,")
    out.append("every listener/timer/observer has a paired teardown, one owner per class name.")
    print("\n".join(out))
    return 1 if (args.strict and total) else 0


if __name__ == "__main__":
    raise SystemExit(main())
