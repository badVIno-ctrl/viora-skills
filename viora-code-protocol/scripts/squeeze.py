#!/usr/bin/env python3
"""squeeze.py - shrink command output before it enters an agent's context.

Why this exists: an agentic bill is dominated by *reading*, not writing. A test run
that fails once and then prints four hundred vendor stack frames costs the same
context as the whole source file it is complaining about. This filter keeps the
decisive lines and throws away the repetition, deterministically, offline.

What it keeps, in priority order:

  1. every line that names a failure (FAIL, ERROR, assert, Traceback, expected...)
  2. the first --keep lines (the command and its banner)
  3. the last --tail lines (the verdict)

What it collapses:

  - identical consecutive lines -> one line + " xN"
  - runs of vendor stack frames -> "... N frames in node_modules"
  - long JSON arrays and strings -> first 3 items + "...+N", truncated strings

Usage:
    <command> 2>&1 | python3 scripts/squeeze.py
    python3 scripts/squeeze.py build.log --keep 5 --tail 40
    cat payload.json | python3 scripts/squeeze.py --json

Execute it, never read it. Stdlib only, Python 3.8+, no network.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
VENDOR_RE = re.compile(r"node_modules|site-packages|vendor|dist-packages")
IMPORTANT_RE = re.compile(
    r"FAIL|ERROR|Error|assert|Traceback|expected|received|\u2717|\u2718", re.IGNORECASE
)
# A frame line points at code inside a dependency: "at f (node_modules/x.js:1)",
# '  File "/usr/lib/python3/site-packages/y.py", line 9'.
FRAME_RE = re.compile(r"(^\s*at\s)|(^\s*File\s\")|(:\d+)")

MAX_ARRAY = 10
HEAD_ITEMS = 3
MAX_STRING = 200


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def vendor_root(line: str) -> str:
    m = VENDOR_RE.search(line)
    return m.group(0) if m else "vendor"


def is_frame(line: str) -> bool:
    return bool(VENDOR_RE.search(line)) and bool(FRAME_RE.search(line))


def collapse_frames(lines):
    """Runs of two or more vendor frames become one line naming the root."""
    out, i = [], 0
    while i < len(lines):
        if is_frame(lines[i]):
            j = i
            while j < len(lines) and is_frame(lines[j]):
                j += 1
            n = j - i
            if n >= 2:
                out.append("\u2026 %d frames in %s" % (n, vendor_root(lines[i])))
            else:
                out.append(lines[i])
            i = j
            continue
        out.append(lines[i])
        i += 1
    return out


def collapse_repeats(lines):
    out, i = [], 0
    while i < len(lines):
        j = i
        while j + 1 < len(lines) and lines[j + 1] == lines[i]:
            j += 1
        n = j - i + 1
        out.append(lines[i] if n == 1 else "%s \u00d7%d" % (lines[i], n))
        i = j + 1
    return out


def window(lines, keep: int, tail: int):
    """First `keep` + last `tail` + every important line in between."""
    if len(lines) <= keep + tail:
        return list(lines)
    head = lines[:keep]
    foot = lines[len(lines) - tail:] if tail else []
    middle = lines[keep:len(lines) - tail] if tail else lines[keep:]
    out = list(head)
    elided = 0
    for line in middle:
        if IMPORTANT_RE.search(line):
            if elided:
                out.append("\u2026 %d lines elided" % elided)
                elided = 0
            out.append(line)
        else:
            elided += 1
    if elided:
        out.append("\u2026 %d lines elided" % elided)
    return out + foot


def shrink_json(node):
    if isinstance(node, list):
        if len(node) > MAX_ARRAY:
            kept = [shrink_json(x) for x in node[:HEAD_ITEMS]]
            return kept + ["\u2026+%d" % (len(node) - HEAD_ITEMS)]
        return [shrink_json(x) for x in node]
    if isinstance(node, dict):
        return {k: shrink_json(v) for k, v in node.items()}
    if isinstance(node, str) and len(node) > MAX_STRING:
        return node[:MAX_STRING] + "\u2026[%d chars]" % len(node)
    return node


def looks_like_json(text: str) -> bool:
    return text.lstrip()[:1] in ("{", "[")


def squeeze(text: str, keep: int = 15, tail: int = 25, footer: bool = True,
            as_json=None) -> str:
    text = strip_ansi(text)
    raw_lines = text.splitlines()
    in_count = len(raw_lines)

    want_json = looks_like_json(text) if as_json is None else as_json
    if want_json:
        try:
            body = json.dumps(shrink_json(json.loads(text)), indent=2, ensure_ascii=False)
            lines = body.splitlines()
            if footer:
                lines.append("squeezed %d\u2192%d lines" % (in_count, len(lines)))
            return "\n".join(lines)
        except ValueError:
            pass  # not valid JSON after all - fall back to line mode

    lines = [l.rstrip() for l in raw_lines]
    lines = collapse_repeats(collapse_frames(lines))
    lines = window(lines, keep, tail)
    if footer:
        lines.append("squeezed %d\u2192%d lines" % (in_count, len(lines)))
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="squeeze.py",
        description=(
            "Shrink command output before it costs context: identical lines collapse, "
            "vendor stack frames collapse, long JSON arrays and strings truncate. "
            "Lines naming a failure are always kept."
        ),
    )
    p.add_argument("file", nargs="?", help="file to squeeze (default: stdin)")
    p.add_argument("--keep", type=int, default=15, help="leading lines kept verbatim")
    p.add_argument("--tail", type=int, default=25, help="trailing lines kept verbatim")
    p.add_argument("--json", action="store_true", help="treat the input as JSON")
    p.add_argument("--no-footer", action="store_true", help="omit the squeezed n->m line")
    args = p.parse_args(argv)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            sys.stderr.write("squeeze: cannot read %s (%s)\n" % (args.file, exc))
            return 2
    else:
        text = sys.stdin.read()

    out = squeeze(
        text,
        keep=max(0, args.keep),
        tail=max(0, args.tail),
        footer=not args.no_footer,
        as_json=True if args.json else None,
    )
    sys.stdout.write(out if out.endswith("\n") else out + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
