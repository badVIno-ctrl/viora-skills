#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Viora Aegis PreToolUse guard: refuse a write that carries a secret.

Claude Code sends a PreToolUse event as JSON on stdin. This reads it, runs
every regex in rules/secrets.json over the content the agent is about to
write, and exits 2 when one matches - which is how a PreToolUse hook blocks
the call.

The one line it prints names the rule, the title and the destination file. It
never prints the matched value: a hook that echoes the secret into the
transcript has moved the leak, not stopped it.

Zero dependencies. Python 3.8+. Exit 0 = allow, exit 2 = block.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(os.path.dirname(HERE))
RULES = os.path.join(PACK, "rules", "secrets.json")
WRITE_TOOLS = {"write", "edit", "multiedit", "notebookedit"}
CONTENT_KEYS = ("content", "new_string", "new_str", "text", "replacement")


def load_rules():
    try:
        with open(RULES, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except Exception:
        # A missing rule pack must not block every write in the session.
        return []
    out = []
    for r in data.get("rules", []):
        try:
            out.append((r.get("id", "SECRET-???"), r.get("title", "secret"),
                        re.compile(r["pattern"])))
        except (KeyError, re.error):
            continue
    return out


def candidate_text(tool_input):
    parts = []
    for key in CONTENT_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str):
            parts.append(val)
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict):
            for key in CONTENT_KEYS:
                if isinstance(edit.get(key), str):
                    parts.append(edit[key])
    return "\n".join(parts)


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(event, dict):
        return 0
    if (event.get("tool_name") or "").strip().lower() not in WRITE_TOOLS:
        return 0

    tool_input = event.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    target = tool_input.get("file_path") or tool_input.get("path") or "(unnamed file)"
    text = candidate_text(tool_input)
    if not text:
        return 0

    for rid, title, rx in load_rules():
        if rx.search(text):
            sys.stderr.write("%s %s in %s\n" % (rid, title, target))
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
