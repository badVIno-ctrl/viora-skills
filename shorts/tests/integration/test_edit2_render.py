"""1.2.0: edit v2 end to end on a local film (no network): plan -> render -> QA edit checks."""
from __future__ import annotations

import json

import pytest

from shortskit.adapters import edit2 as E2
from shortskit.engine.render import render
from shortskit.qa.gate import run_gate
from shortskit.util import ShortsError


def _check(rep: dict, cid: str) -> dict:
    return next(c for c in rep["checks"] if c["id"] == cid)


@pytest.mark.slow
def test_edit_v2_local_film_line_drop_shots_link(tmp_path, synthetic_film, monkeypatch):
    def no_whisper(*a, **k):
        raise ShortsError("no whisper in tests")

    monkeypatch.setattr(E2, "hear", no_whisper)  # energy timing path (the film has no sound)
    monkeypatch.setattr(E2, "_sface", lambda: None)
    plan = E2.edit_plan(str(synthetic_film), tmp_path, music="builtin", line_at=(8.0, 10.0), line_text="Город злая сила",
                        link="t.me/TESTNAME", length=12.0, brand="mono", spares=2)
    # structure: the line, then shots on the beat; drop at the end of the line; link twice in the centre
    sc = plan["scenes"]
    assert sc[0]["id"] == "line" and sc[0]["edit"]["velocity"] == "flat" and sc[0]["source"]["keep_audio"]
    assert [w["w"] for w in sc[0]["transcript"]] == ["Город", "злая", "сила"]
    assert plan["audio"]["music"]["drop_at"] == pytest.approx(sc[0]["duration"], abs=1 / 30 + 1e-6)
    assert all(s["edit"]["velocity"] in ("velocity", "hero") for s in sc[1:])
    ctas = plan["layout"]["cta_in_center"]
    assert len(ctas) == 2 and all(c["kind"] == "link" and c["y"] == "center" for c in ctas)
    assert plan["layout"]["mode"] == "center_only" and not any(s.get("on_screen_text") for s in sc)
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    render(p, tmp_path / "out")
    rep = run_gate(tmp_path / "out")
    es, bs = _check(rep, "edit_style"), _check(rep, "beat_sync")
    assert es["status"] != "fail", es
    assert es["data"]["velocity_share"] >= 0.9
    assert bs["data"]["hit_share"] >= 0.8 and bs["data"]["slowmo_scenes"], bs
    m = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    links = [o for o in m["overlays"] if o["kind"] == "cta_link"]
    assert len(links) == 2 and all(abs((o["box"][0] + o["box"][2]) / 2 - 540) <= 4 for o in links)
    assert m["captions"]["chunks"] and m["captions"]["chunks"][0]["start"] < 1.5
    assert _check(rep, "qr")["status"] == "pass"
