"""QA item 13/14 done by the agent: it opens the contact sheet and writes what it saw.

`shorts.py review DIR --saw "..."` stores the note in DIR/review.md and in qa.json (check `eyes`).
A note that is empty or only repeats file names is refused: the point is to look at the frames."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from ..util import ShortsError, read_json, write_json

MIN_WORDS = 8


def record_review(d: Path, saw: str, silent: str = "") -> dict:
    qa = d / "qa.json"
    if not qa.exists():
        raise ShortsError(f"run `shorts.py qa {d}` first: {qa} is missing")
    text = " ".join((saw or "").split())
    words = [w for w in re.findall(r"\w+", text) if not re.fullmatch(r"(contact|png|jpg|qa|frames?|dense|first|last|\d+)", w, re.I)]
    if len(words) < MIN_WORDS:
        raise ShortsError(f"describe what is on the frames (at least {MIN_WORDS} words): what is in the first frame, "
                          "what changes, anything wrong (titles, black, cut-off text)")
    rep = read_json(qa)
    sheets = []
    for c in rep["checks"]:
        if c["id"] == "eyes":
            sheets = c.get("data", {}).get("contact_sheets", [])
            c["status"], c["ok"] = "pass", True
            c["detail"] = f"agent looked at {', '.join(sheets) or 'the frames'}: {text[:400]}"
            c.setdefault("data", {})["agent_note"] = text
        if c["id"] == "silent" and silent.strip():
            c["status"], c["ok"] = "pass", True
            c["detail"] = f"retold without sound: {' '.join(silent.split())[:400]}"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rep["review"] = {"at": stamp, "saw": text, "silent": " ".join(silent.split())}
    rep["not_checked"] = [c["id"] for c in rep["checks"] if c["status"] == "manual"]
    write_json(qa, rep)
    out = d / "review.md"
    out.write_text(f"# Review {stamp}\n\nLooked at: {', '.join(sheets)}\n\n## What I saw\n\n{text}\n"
                   + (f"\n## Without sound\n\n{' '.join(silent.split())}\n" if silent.strip() else ""), encoding="utf-8")
    return {"file": str(out), "qa": str(qa)}
