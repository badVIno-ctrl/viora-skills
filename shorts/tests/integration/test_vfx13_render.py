"""1.3 on offline fixtures: effects, plates, subscribe card, kinetic captions, band, background banner.
Each plan renders a short video and must pass the QA gate (no fail)."""
from __future__ import annotations

import subprocess

import pytest

from shortskit import bglib as BG
from shortskit.engine import layout as L
from shortskit.engine.render import render
from shortskit.meta.packaging import package_dir
from shortskit.qa.gate import run_gate

from conftest import write_plan

WORDS = [("Два", 0.2, 0.5), ("бесплатных", 0.55, 1.1), ("сайта,", 1.15, 1.6), ("и", 1.9, 2.0), ("оба", 2.05, 2.4),
         ("пригодятся.", 2.45, 3.2), ("Смотри", 3.6, 4.0), ("до", 4.05, 4.2), ("конца.", 4.25, 4.8)]
WORDS_B = [("Сделай", 0.2, 0.6), ("это", 0.65, 0.9), ("за", 0.95, 1.1), ("10", 1.15, 1.5), ("минут.", 1.55, 2.2),
           ("Без", 2.6, 2.9), ("монтажа", 2.95, 3.5), ("руками.", 3.55, 4.2)]


def _tr(words, shift=0.0):
    return [{"w": w, "s": round(s - shift, 3), "e": round(e - shift, 3)} for w, s, e in words]


def _plan(name, scenes, **over):
    p = {"schema_version": "1.3",
         "meta": {"name": name, "language": "ru", "platforms": ["youtube_shorts"], "duration_target": [4, 20], "loop": True},
         "layout": {"mode": "center_only", "cta_in_center": []}, "brand": {"preset": "viora"},
         "captions": {"enabled": True, "max_words": 3},
         "audio": {"music": {"source": "assets/audio/bed.mp3"}, "sfx_auto": True},
         "author_layer": [{"kind": "voice", "note": "own voice"}, {"kind": "text_point", "note": "theses"}],
         "scenes": scenes}
    for k, v in over.items():
        p[k] = v
    return p


def _two_scenes(trans="whip"):
    return [{"id": "a", "why": "hook", "duration": 3.4, "on_screen_text": "ТЕСТ КАДРА",
             "source": {"type": "html", "ref": "orbit.html"}, "transcript": _tr(WORDS[:6])},
            {"id": "b", "why": "proof", "duration": 3.0, "trans": trans,
             "source": {"type": "images", "images": ["app-screen.png"], "focus": [0.5, 0.2]},
             "transcript": _tr(WORDS[6:], 3.4)}]


def _fails(rep):
    return [(c["id"], c["detail"]) for c in rep["checks"] if c["status"] == "fail"]


def _row(rep, cid):
    return next(c for c in rep["checks"] if c["id"] == cid)


@pytest.mark.slow
def test_effects_plates_subscribe_and_export_pass_qa(tmp_path):
    plan = _plan("fx13", _two_scenes("whip"),
                 layout={"mode": "center_only",
                         "cta_in_center": [{"t": 4.0, "duration": 2.0, "kind": "subscribe", "text": "@viora"}]},
                 audio={"music": {"source": "assets/audio/bed.mp3", "drop_at": 1.5}, "sfx_auto": True, "export": "both"},
                 fx={"letterbox": [{"t": 0, "ratio": 2.39}, {"t": "drop", "ratio": "full", "dur": 0.4}],
                     "look_keys": [{"t": 0, "look": "bw"}, {"t": "drop", "look": "base", "trans": "wipe", "dur": 0.5}]},
                 overlays={"facts": [{"t": 2.0, "text": "Факт: 2 сайта", "sub": "бесплатно"}]})
    out = tmp_path / "out"
    m = render(write_plan(tmp_path, plan), out)
    assert (out / "fx13.nomusic.mp4").exists() and (out / "music_cue.json").exists()
    assert [t["kind"] for t in m["vfx"]["transitions"]] == ["whip"]
    assert m["vfx"]["letterbox"]["closed_at_start_s"] < 2.0 and m["vfx"]["look_keys"]["changes"] == 1
    kinds = {o["kind"] for o in m["overlays"]}
    assert {"fact", "cta_subscribe"} <= kinds
    assert list((out / "graphics").glob("*cta_subscribe-after.png"))
    cta = next(o for o in m["overlays"] if o["kind"] == "cta_subscribe")
    for ch in m["captions"]["chunks"]:   # captions moved off the card while it is shown
        if ch["start"] < cta["t1"] and ch["end"] > cta["t0"]:
            assert not L.Rect.from_xyxy(*ch["box"]).intersects(L.Rect.from_xyxy(*cta["box"]))
    rep = run_gate(out)
    assert rep["passed"], _fails(rep)
    vfx = _row(rep, "vfx")
    assert vfx["data"]["flashes"]["max_flashes"] <= 3
    assert {"click", "transition", "look", "letterbox", "fact"} <= {e["kind"] for e in m["events"]}


@pytest.mark.slow
def test_band_title_bar_kinetic_captions_pass_qa(tmp_path):
    scenes = [{"id": "a", "why": "hook", "duration": 2.4, "source": {"type": "html", "ref": "orbit.html"},
               "transcript": _tr(WORDS_B[:5])},
              {"id": "b", "why": "proof", "duration": 2.4, "source": {"type": "images", "images": ["app-screen.png"]},
               "transcript": _tr(WORDS_B[5:], 2.4)}]
    plan = _plan("band13", scenes,
                 layout={"mode": "band", "cta_in_center": [],
                         "title_bar": {"text": "ЦЕНА ПРИЗНАНИЯ", "sub": "Джокер (2019)"}},
                 captions={"enabled": True, "style": "kinetic"},
                 fx={"transitions": {"auto": "facts"}})
    out = tmp_path / "out"
    m = render(write_plan(tmp_path, plan), out)
    tb = next(o for o in m["overlays"] if o["kind"] == "title_bar")
    assert tb["box"][3] <= m["layout"]["center"]["y"] and any("band moved" in n for n in m["vfx"]["notes"])
    cap = m["captions"]
    assert cap["style"] == "kinetic" and cap["kinetic"]["min_px"] >= 56 and cap["kinetic"]["max_lines"] <= 4
    assert "10" in [w.strip(".,") for w in cap["kinetic"]["accents"]]
    assert list((out / "graphics").glob("kinetic-*.png"))
    rep = run_gate(out)
    assert rep["passed"], _fails(rep)
    assert _row(rep, "captions")["data"]["kinetic"]["max_words"] <= 12


@pytest.mark.slow
def test_background_banner_from_own_file_passes_qa_and_credits(tmp_path):
    src = tmp_path / "run.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=12",
                    "-vf", "scroll=horizontal=0.004:vertical=0.002", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
                   check=True)
    BG.add("test_run", src, credit="Gameplay: test author")
    plan = _plan("banner13", _two_scenes("cut"),
                 layout={"mode": "three", "top": {"height_pct": 20, "source": "bg:test_run"},
                         "bottom": {"height_pct": 16, "handle": "VioraStudio", "links": ["https://t.me/VioraStudio"]},
                         "cta_in_center": [{"t": 4.0, "duration": 2.0, "kind": "handle", "text": "VioraStudio"}]})
    out = tmp_path / "out"
    m = render(write_plan(tmp_path, plan), out)
    assert m["top"]["bg"]["id"] == "test_run" and m["top"]["focus_report"]["how"] == "window"
    assert m["author_layer"]["credits"] == ["Gameplay: test author"]
    assert m["author_layer"]["core"] == ["voice"] and m["author_layer"]["count"] >= 2
    meta = package_dir(out)
    assert "Gameplay: test author" in meta["description"]
    rep = run_gate(out)
    assert rep["passed"], _fails(rep)
    lay = _row(rep, "layout")["data"]["top"]
    assert lay["change_per_second_min"] >= 0.3
    assert _row(rep, "author_layer")["status"] == "pass"


@pytest.mark.slow
def test_edit_bars_and_bw_open_on_the_drop(tmp_path, synthetic_film, monkeypatch):
    """`edit --bars --bw-drop` (research 14.4 + 14.6) on the edit v2 flow: the line plays in cinema bars and in
    black and white, the drop opens the bars and brings the colour back; the edit checks still pass."""
    import json

    import numpy as np

    from shortskit import plan as P
    from shortskit.adapters import edit2 as E2
    from shortskit.engine import vfx as VX
    from shortskit.util import ShortsError

    def no_whisper(*a, **k):
        raise ShortsError("no whisper in tests")

    monkeypatch.setattr(E2, "hear", no_whisper)
    monkeypatch.setattr(E2, "_sface", lambda: None)
    plan = E2.edit_plan(str(synthetic_film), tmp_path, music="builtin", line_at=(8.0, 10.0), line_text="Город злая сила",
                        link="t.me/TESTNAME", length=12.0, brand="mono", spares=2)
    notes = VX.edit_cinema(plan, bars=True, bw=True,
                           layers=VX.parse_layers(["thesis:the idea of the cut", "sound_design:drop on the line end"]))
    assert notes == [] and plan["schema_version"] == "1.3"
    assert plan["fx"]["look_keys"][1]["trans"] == "radial"  # reframe "face": colour grows from the face
    assert not P.errors(P.check(plan, tmp_path))
    drop = float(plan["audio"]["music"]["drop_at"])
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    render(p, tmp_path / "out")
    rep = run_gate(tmp_path / "out")
    by = {c["id"]: c for c in rep["checks"]}
    for cid in ("edit_content", "edit_style", "beat_sync", "vfx", "author_layer", "captions", "layout"):
        assert by[cid]["status"] != "fail", by[cid]
    m = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
    lb = m["vfx"]["letterbox"]
    assert lb["closed_at_start_s"] == pytest.approx(drop, abs=0.3) and lb["max_bar_px"] > 600
    assert m["vfx"]["notable"] == ["letterbox", "look_keys"]

    def frame(t):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(tmp_path / "out" / f"{m['name']}.mp4"),
                              "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(np.int16)

    def sat(a):
        return float((a.max(axis=2) - a.min(axis=2)).mean())

    before, after = frame(max(0.3, drop - 0.6)), frame(drop + 1.0)
    bar = lb["max_bar_px"]
    assert before[40:bar - 40, 60:1020].mean() < 6           # the top bar is pure black on the line
    assert sat(before[bar + 40:960, 60:1020]) < 4             # the line is black and white
    assert after[300:600, 60:1020].std() > 12                 # the bars are open: picture where the bar was
    assert sat(after[bar + 40:960, 60:1020]) > 15             # the colour is back


def _frame(video, t):
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(np.int16)


@pytest.mark.slow
def test_post_card_over_full_background_passes_qa(tmp_path):
    """Layout C (research 17, @amazinglul 4.9M): gameplay on the whole frame, a Reddit card that writes itself
    with the voice, captions only after the card, the background author in the description."""
    src = tmp_path / "run.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=14",
                    "-vf", "scroll=horizontal=0.004:vertical=0.002", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)],
                   check=True)
    BG.add("test_full", src, credit="Gameplay: test author")
    scenes = [{"id": "story", "why": "hook", "duration": 4.8, "source": {"type": "video", "ref": "bg:test_full"},
               "transcript": _tr(WORDS)},
              {"id": "end", "why": "payoff", "duration": 4.2, "source": {"type": "video", "ref": "bg:test_full"},
               "transcript": _tr(WORDS_B)}]
    plan = _plan("post13", scenes, overlays={"post": {"scene": "story", "kind": "reddit", "name": "u/test_user",
                                                      "where": "r/AskReddit", "title": "Два сайта", "stats": "12,4k 873"}},
                 metadata={"topic": "два бесплатных сайта"})   # no say here (transcripts): the description needs a topic
    out = tmp_path / "out"
    m = render(write_plan(tmp_path, plan), out)
    post = m["post"][0]
    assert post["captions_hidden"] and post["max_early_s"] == 0.0 and post["states"] == len(WORDS) + 1
    chunks = m["captions"]["chunks"]
    assert chunks and all(ch["start"] >= post["t1"] - 1e-3 for ch in chunks)   # the card already shows those words
    assert m["author_layer"]["credits"] == ["Gameplay: test author"]
    assert any("background test_full" in n for s in m["scenes"] for n in s.get("notes", []))
    sc = {s["id"]: s for s in m["scenes"]}   # the second scene goes on where the first one stopped (no repeat)
    assert abs(sc["end"]["source"]["in"] - (sc["story"]["source"]["in"] + sc["story"]["length"])) < 0.05
    meta = package_dir(out)
    assert "Gameplay: test author" in meta["description"]
    rep = run_gate(out)
    assert rep["passed"], _fails(rep)
    first = next(c for c in rep["checks"] if c["id"] == "first_frame")
    assert "no on-screen text" not in (first.get("detail") or "")   # the card is the on-screen text of scene 1
    x0, y0, x1, y1 = post["box"]
    video = out / m["video"]
    a, b = _frame(video, 2.0), _frame(video, 3.0)
    card = a[y0 + 44:y0 + 100, x1 - 140:x1 - 50]   # the header row right of the name: white plate
    assert card.mean() > 200
    below = slice(y1 + 40, 1900)
    assert abs(a[below] - b[below]).mean() > 4       # the background moves under the card
