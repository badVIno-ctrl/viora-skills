"""1.2.0: edit v2 (line -> drop -> hero shots), browser access helpers, link CTA in the exact centre."""
from __future__ import annotations

import json

import numpy as np
import pytest

from shortskit.adapters import edit2 as E2
from shortskit.adapters import ytbrowser as YB
from shortskit.config import asset
from shortskit.engine import velocity as V


# ---------------------------------------------------------------- velocity
def test_velocity_curve_hangs_slow_in_the_middle_and_is_monotonic():
    r = V.Remap("velocity", 1.0)
    ts = np.linspace(0, 1, 61)
    src = [r.src(t) for t in ts]
    assert all(b >= a for a, b in zip(src, src[1:]))
    assert r.rate(0.0) > 4 and r.rate(1.0) > 3.5 and 0.45 <= r.rate(0.45) <= 0.6
    assert V.source_span("velocity", 1.2) == pytest.approx(r.span * 1.2, rel=0.02)
    assert V.source_span("flat", 2.0) == pytest.approx(2.0, abs=1e-3)
    assert 0.3 < V.hang_tau("velocity") < 0.6


def test_slot_pattern_fills_the_bars_with_two_heroes_and_a_quick_double():
    beat = 60 / 140
    p = E2.slot_pattern(32, beat)
    assert sum(n for n, _ in p) == 32
    roles = [r for _, r in p]
    assert roles.count("hero") == 2 and roles.count("quick") == 2
    assert all(0.7 <= n * beat <= 1.4 for n, r in p if r == "shot")
    for bpm in (90, 120, 170):
        b = 60 / bpm
        q = E2.slot_pattern(16, b)
        assert sum(n for n, _ in q) == 16


# ---------------------------------------------------------------- the line
LINES = [{"start": 5276.0, "end": 5283.0, "text": "ну пойдём"},
         {"start": 5283.0, "end": 5290.0, "text": "Вот ты говорил город сила А здесь слабые"},
         {"start": 5290.0, "end": 5297.0, "text": "все город - это злая сила сильный приезжает становится"}]


def test_find_line_spans_two_noisy_transcript_lines():
    a, b, text = E2.find_line(LINES, "Вот ты говорил: город - сила, а здесь слабые все")
    assert a == 5283.0 and b == 5297.0 and "слабые" in text
    with pytest.raises(Exception):
        E2.find_line(LINES, "совсем другая фраза про кошек")


def test_split_text_is_proportional_and_ordered():
    w = E2._split_text("Город злая сила", 1.0, 3.0)
    assert [x["w"] for x in w] == ["Город", "злая", "сила"]
    assert w[0]["s"] == pytest.approx(1.0) and w[-1]["e"] <= 3.0
    assert all(x["s"] < x["e"] for x in w)


# ---------------------------------------------------------------- music
def test_own_edit_track_has_a_sidecar_with_the_drop():
    info = E2.music_info(E2.DEFAULT_MUSIC)
    assert info["source"] == "sidecar" and info["bpm"] == 140
    assert info["drop"] == pytest.approx(4 * 4 * 60 / 140, abs=1e-3)
    assert asset("audio/edit.mp3").exists()


def test_detect_drop_finds_the_energy_jump_on_a_downbeat():
    t = np.arange(0, 30, 0.25)
    rms = np.where(t < 8.0, 0.05, 0.4)
    b = {"energy": {"t": t.tolist(), "rms": rms.tolist()}, "downbeats": [0, 2, 4, 6, 8, 10, 12, 14],
         "beats": list(np.arange(0, 30, 0.5)), "tempo": 120}
    assert E2.detect_drop(b) == 8


def test_audio_mix_keeps_music_quiet_until_the_drop(tmp_path):
    from shortskit.engine import audio as A

    sr = A.SR
    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(6 * sr) / sr)).astype(np.float32)
    mus = tmp_path / "m.wav"
    A._write_wav(mus, np.stack([tone, tone], 1))
    voice = (0.2 * np.random.default_rng(1).standard_normal(2 * sr)).astype(np.float32)
    v = tmp_path / "v.wav"
    A._write_wav(v, np.stack([voice, voice], 1))
    out = tmp_path / "mix.wav"
    rep = A.mix(5.0, [], [(0.0, v)], [{"w": "a", "s": 0.1, "e": 1.9}], {"drop_at": 2.0}, mus, [], out)
    assert rep["drop_at"] == 2.0 and rep["pre_drop_db"] == -16
    x = A.load_audio(out, mono=True)
    music_before = x[int(2.3 * sr) - int(0.6 * sr):int(1.9 * sr)]  # (voice is there too: just check after > before)
    after = x[int(2.5 * sr):int(4.0 * sr)]
    assert np.sqrt((after ** 2).mean()) > 0.5 * np.sqrt((music_before ** 2).mean())


# ---------------------------------------------------------------- candidates
def test_pick_candidates_spreads_over_the_film_and_skips_the_same_look():
    import cv2

    def h(seed):
        img = np.full((90, 160, 3), seed * 20 % 255, np.uint8)
        img[:, : seed * 7 % 160] = 200
        hh = cv2.calcHist([cv2.cvtColor(img, cv2.COLOR_BGR2HSV)], [0, 1, 2], None, [8, 6, 4], [0, 180, 0, 256, 0, 256])
        cv2.normalize(hh, hh)
        return hh

    same = h(3)
    scored = [{"t": 100.0, "score": 0.9, "hist": same}, {"t": 110.0, "score": 0.89, "hist": h(5)},  # too close
              {"t": 160.0, "score": 0.88, "hist": same},  # same look within 4 min
              {"t": 600.0, "score": 0.5, "hist": h(9)}, {"t": 5.0, "score": 1.0, "hist": h(11)},  # head of film
              {"t": 990.0, "score": 1.0, "hist": h(12)}]  # credits
    got = E2.pick_candidates(scored, 5, 1000.0)
    ts = [c["t"] for c in got]
    assert 100.0 in ts and 600.0 in ts
    assert 110.0 not in ts and 160.0 not in ts and 5.0 not in ts and 990.0 not in ts


def test_best_offset_stays_inside_one_camera_shot_and_hangs_on_the_face():
    an = {"segments": [(0.0, 1.0), (1.0, 5.0)], "t": list(np.arange(0, 5, 0.125)),
          "face_h": [0.0] * 8 + [0.1] * 16 + [0.35] * 8 + [0.1] * 8, "motion": [3.0] * 40}
    o, q = E2.best_offset(an, 1.2, 0.45)
    assert 1.0 <= o and o + 1.2 <= 5.0
    assert 2.95 <= o + 0.45 * 1.2 <= 4.0  # hang where the face is biggest
    assert q > 0.5


# ---------------------------------------------------------------- browser helpers
def test_bot_block_and_ids():
    assert YB.is_bot_block("ERROR: [youtube] x: Sign in to confirm you're not a bot. Use --cookies")
    assert not YB.is_bot_block("HTTP Error 404")
    assert YB.video_id("https://www.youtube.com/watch?v=aDaaCGZz-Ok&t=5") == "aDaaCGZz-Ok"
    assert YB.video_id("https://youtu.be/aDaaCGZz-Ok") == "aDaaCGZz-Ok"


def test_parse_transcript_and_storyboard():
    lines = YB.parse_transcript(["0:01 [музыка]", "1:28:03 1 hour, 28 minutes, 3 seconds Вот ты говорил",
                                 "1:28:10 город сила"])
    assert lines[1]["start"] == 5283.0 and lines[1]["end"] == 5290.0 and lines[1]["text"] == "Вот ты говорил"
    spec = ("https://i.ytimg.com/sb/ID/storyboard3_L$L/$N.jpg?sqp=x|48#27#100#10#10#0#default#rs$A|"
            "80#45#574#10#10#10000#M$M#rs$B|160#90#574#5#5#10000#M$M#rs$C|320#180#574#3#3#10000#M$M#rs$D")
    lv = YB.parse_storyboard(spec, 5723.0)
    big = max(lv, key=lambda x: x["w"])
    assert (big["w"], big["h"], big["cols"], big["rows"], big["count"]) == (320, 180, 3, 3, 574)
    assert big["interval"] == pytest.approx(10.0, abs=0.01)
    assert big["url"].endswith("sigh=rs$D") and "storyboard3_L3/M$M.jpg" in big["url"]


# ---------------------------------------------------------------- link CTA and captions
def test_link_cta_is_in_the_exact_centre_and_slides_in():
    from shortskit.engine import brand as B
    from shortskit.engine import graphics as G
    from shortskit.engine import layout as L
    from shortskit.engine.render import SLIDE_DY, SLIDE_IN, Overlay

    lay = L.compute({"mode": "center_only"}, ["youtube_shorts"])
    br = B.resolve({"preset": "mono"})
    spr = G.cta_link("t.me/MIGHTINVEST1", br, lay, y="center")
    x0, y0, x1, y1 = spr.box.as_list()
    assert abs((x0 + x1) / 2 - 540) <= 1
    assert abs((y0 + y1) / 2 - 960) <= 40
    o = Overlay(spr, 1.0, 3.4, anim="slide")
    a0, _, dy0 = o.motion(1.0)
    a1, _, dy1 = o.motion(1.0 + SLIDE_IN + 0.01)
    assert a0 == 0.0 and dy0 == pytest.approx(SLIDE_DY) and a1 == 1.0 and dy1 == 0.0
    assert o.motion(3.39)[0] < 0.2 and o.motion(3.5)[0] == 0.0


def test_grow_captions_blur_in_and_out():
    from shortskit.engine import brand as B
    from shortskit.engine import captions as C
    from shortskit.engine import layout as L

    lay = L.compute({"mode": "center_only"}, ["youtube_shorts"])
    br = B.resolve({"preset": "mono"})
    words = [{"w": "Город", "s": 0.2, "e": 0.6}, {"w": "злая", "s": 0.65, "e": 0.9}, {"w": "сила", "s": 0.95, "e": 1.4}]
    cfg = {"enabled": True, "max_words": 3, "highlight": "none", "anim": "grow"}
    ch = C.build(words, br, lay, cfg, "ru")
    C.place(ch, br, lay, cfg)
    ass = C.to_ass(ch, br, cfg, 3.0)
    assert "\\blur8" in ass and "\\blur10" in ass
    cx = [(c.box[0] + c.box[2]) / 2 for c in ch]
    assert all(abs(x - 540) <= 2 for x in cx)


# ---------------------------------------------------------------- QA edit_style
def _manifest(cx=540, drop=3.0, end1=3.0, velocity="velocity", mode="center_only", face_x=0.5):
    sc = [{"id": "line", "type": "film", "start": 0.0, "length": end1, "skipped": False,
           "edit": {"velocity": "flat"}, "edit_report": {"face_frames": 0.9, "face_center": [0.5]}}]
    t = end1
    for i in range(6):
        sc.append({"id": f"s{i}", "type": "film", "start": t, "length": 0.857, "skipped": False,
                   "edit": {"velocity": velocity}, "edit_report": {"face_frames": 0.8, "face_center": [face_x]}})
        t += 0.857
    return {"scenes": sc, "layout": {"mode": mode, "top": None, "bottom": None},
            "overlays": [{"kind": "cta_link", "box": [cx - 200, 900, cx + 200, 1020], "t0": 4.0, "t1": 6.0}],
            "audio": {"drop_at": drop}, "captions": {"words_spoken": [{"w": "a", "s": 0.3, "e": 0.8}]}}


def test_edit_style_passes_a_good_edit_and_catches_each_problem():
    from shortskit.qa.edit import edit_style

    good = edit_style(_manifest(), 30)
    assert good["applicable"] and not good["problems"], good
    assert any("off centre" in p for p in edit_style(_manifest(cx=470), 30)["problems"])
    assert any("drop" in p for p in edit_style(_manifest(drop=3.4), 30)["problems"])
    assert any("panels" in p for p in edit_style(_manifest(mode="three"), 30)["problems"])
    assert any("faces centred" in p for p in edit_style(_manifest(face_x=0.8), 30)["problems"])
    assert any("speed curve" in w for w in edit_style(_manifest(velocity="flat"), 30)["warnings"])


def test_schema_accepts_edit_v2_fields():
    from shortskit.config import skill_root

    sch = json.loads((skill_root() / "schema" / "plan.schema.json").read_text(encoding="utf-8"))
    props = sch["properties"]
    assert "1.2" in json.dumps(props["schema_version"])
    assert "anim" in props["captions"]["properties"]
    assert "drop_at" in json.dumps(props["audio"])
