"""Item 1 (d) and item 7 of 1.1.0: the QA gate measures what an edit shows and where its cuts fall.

Bad cases (each passed QA in 1.0.0): credits, black frames, the same picture twice, cuts off the beat."""
from __future__ import annotations

import pytest

from shortskit.adapters import film as FL
from shortskit.engine.render import render
from shortskit.qa.gate import run_gate

from conftest import SYN_BLACK, SYN_CREDITS, heatmap_on_text, write_plan


def _check(rep: dict, cid: str) -> dict:
    return next(c for c in rep["checks"] if c["id"] == cid)


@pytest.mark.slow
def test_good_edit_passes_content_and_beat_checks(tmp_path, synthetic_film):
    plan = FL.edit_plan(str(synthetic_film), music="builtin", length=10.0, heatmap=heatmap_on_text(), n=8, brand="viora")
    p = write_plan(tmp_path, plan)
    render(p, tmp_path / "out")
    rep = run_gate(tmp_path / "out")
    ec, bs = _check(rep, "edit_content"), _check(rep, "beat_sync")
    assert ec["status"] == "pass" and ec["ok"], ec
    assert bs["status"] in ("pass", "warn") and bs["ok"], bs
    assert bs["data"]["hit_share"] >= 0.8 and bs["data"]["slowmo_scenes"]
    assert all(r["err_ms"] is not None and r["err_ms"] <= 50 for r in bs["data"]["rows"] if r["seen"] is not None)


@pytest.mark.slow
def test_bad_edit_with_credits_black_repeats_and_off_beat_cuts_fails(tmp_path, synthetic_film):
    ref = str(synthetic_film)

    def shot(i: int, a: float, d: float = 1.0) -> dict:
        return {"id": f"s{i}", "why": "bad case", "duration": d, "source": {"type": "film", "ref": ref, "in": a, "out": a + d}}

    scenes = [shot(0, 5.0), shot(1, 8.0), shot(2, 8.0),  # same picture twice in a row
              shot(3, SYN_BLACK[0], 1.2),  # black
              shot(4, SYN_CREDITS[0] + 2), shot(5, SYN_CREDITS[0] + 4), shot(6, 12.0), shot(7, 15.0)]
    plan = {"schema_version": "1.1",
            "meta": {"name": "bad-edit", "language": "en", "platforms": ["youtube_shorts"], "duration_target": [6, 14]},
            "layout": {"mode": "center_only", "cta_in_center": []}, "brand": {"preset": "mono"},
            "captions": {"enabled": False},
            "audio": {"music": {"source": "assets/audio/bed.mp3", "start": 0, "beat_sync": True}, "sfx_auto": False},
            "scenes": scenes}
    p = write_plan(tmp_path, plan)
    render(p, tmp_path / "out")
    rep = run_gate(tmp_path / "out")
    assert not rep["passed"]
    ec, bs = _check(rep, "edit_content"), _check(rep, "beat_sync")
    assert ec["status"] == "fail" and ec["ok"] is False
    text = " ".join(ec["data"]["problems"])
    assert "text screen" in text and "black frames" in text and "same picture" in text, text
    assert bs["status"] == "fail" and bs["data"]["hit_share"] < 0.8, bs["data"]
