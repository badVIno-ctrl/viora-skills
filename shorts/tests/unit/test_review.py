"""`shorts.py review`: the agent must describe the frames; empty or file-name-only notes are refused."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shortskit.qa.review import record_review
from shortskit.util import ShortsError


def _qa(d: Path) -> Path:
    p = d / "qa.json"
    p.write_text(json.dumps({"passed": True, "checks": [
        {"id": "eyes", "status": "manual", "ok": True, "detail": "", "data": {"contact_sheets": ["contact-dense.png"]}},
        {"id": "silent", "status": "manual", "ok": True, "detail": ""}]}), encoding="utf-8")
    return p


def test_review_refuses_file_names_only(tmp_path):
    _qa(tmp_path)
    with pytest.raises(ShortsError):
        record_review(tmp_path, "contact-dense.png contact first last frames qa 1 2 3")


def test_review_refuses_without_qa(tmp_path):
    with pytest.raises(ShortsError):
        record_review(tmp_path, "a rabbit walks in the forest and a butterfly lands on his nose")


def test_review_records_note(tmp_path):
    p = _qa(tmp_path)
    record_review(tmp_path, "first frame: the rabbit close up, then butterflies, no titles, no black frames",
                  silent="a big rabbit gets angry at three rodents")
    rep = json.loads(p.read_text())
    eyes = next(c for c in rep["checks"] if c["id"] == "eyes")
    assert eyes["status"] == "pass" and "rabbit" in eyes["detail"]
    assert rep["review"]["silent"]
    assert (tmp_path / "review.md").exists()
