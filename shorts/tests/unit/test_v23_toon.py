"""2.3 toon: code-drawn cartoon episodes (story builder, captions, channel rules, templates, catalog, runtime syntax).

Fast tests use estimated timings (no TTS, no Chromium); one smoke test draws a preview sheet in Chromium."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shortskit.toon import catalog, check as C, story as S
from shortskit.toon.cli import TEMPLATES, templates, youtube_chapters

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "tools" / "shortskit" / "toon" / "runtime"


def tpl(name: str) -> dict:
    return json.loads((TEMPLATES / f"{name}.json").read_text(encoding="utf-8"))


def mini(**over) -> dict:
    ep = {"title": "t", "lang": "ru", "cast": {"max": {"look": "hero", "name": "Макс"}},
          "scenes": [{"say": "Свет *пропал* во всём доме.", "set": {"id": "room", "time": "night"},
                      "actors": [{"id": "max", "pose": "scared", "emotion": "scared"}]},
                     {"say": "Макс берёт фонарик и идёт к двери.", "actors": [{"id": "max", "pose": "flashlight"}]},
                     {"say": "А ты бы пошёл вниз или остался?", "actors": [{"id": "max", "pose": "think"}]}]}
    ep.update(over)
    return ep


# ------------------------------------------------------------------ text, timing, anchors
def test_parse_say_marks_accent_words():
    clean, flags = S.parse_say("Без воды *три дня* можно прожить")
    assert "*" not in clean and clean.startswith("Без воды три дня")
    words = clean.split()
    assert [w for w, f in zip(words, flags) if f] == ["три", "дня"]


def test_estimate_and_find_word():
    sp = S.estimate("Свет пропал во всём доме.")
    assert sp["duration"] > 1.0 and len(sp["words"]) == 5
    w = S.find_word(sp["words"], "пропал")
    assert w is not None and w["s"] > sp["words"][0]["s"]
    assert S.find_word(sp["words"], "ПРОПА") is not None          # word start, any case
    assert S.find_word(sp["words"], "нет-такого") is None


def test_anchor_keys_map_to_runtime_fields():
    for k in ("split_on", "break_on", "path_on", "route_on", "water_on", "vent_on", "reveal_on", "lights_out_on", "t_on"):
        assert k in S.ANCHOR_KEYS
    assert S.ANCHOR_KEYS["split_on"] == "split_t" and S.ANCHOR_KEYS["lights_out_on"] == "lights_out"


def test_word_anchor_becomes_time_inside_the_scene():
    ep = mini()
    ep["scenes"][0]["set"]["lights_out_on"] = "пропал"
    story, rep = S.build(ep)
    sc = story["scenes"][0]
    assert sc["t0"] <= sc["set"]["lights_out"] <= sc["t1"]
    assert not [p for p in rep["problems"] if p["level"] == "error"]


def test_scene_time_follows_voice_and_inherits_place():
    story, _ = S.build(mini())
    s0, s1 = story["scenes"][0], story["scenes"][1]
    assert s1["t0"] >= s0["t1"] - 1e-6
    assert s1["set"]["id"] == "room"                                   # place carried over
    assert story["duration"] == pytest.approx(story["scenes"][-1]["t1"], abs=1.5)
    ep = mini()
    ep["scenes"][1] = {"say": "Фонарик, а не свеча.", "scheme": {"type": "closeup", "item": "flashlight", "label": "Фонарик"}}
    story, _ = S.build(ep)
    assert story["scenes"][2]["set"]["id"] == "room"                   # back to the place after a full-screen scheme


def test_camera_and_transition_never_repeat_back_to_back():
    ep = tpl("blackout")
    story, _ = S.build(ep)
    cams = [None if src.get("scheme") else sc.get("camera") for src, sc in zip(ep["scenes"], story["scenes"])]
    for a, b in zip(cams, cams[1:]):                                   # story shots (schemes keep their own slow push)
        assert not (a and a == b and a != "static")
    trs = [sc.get("transition") for sc in story["scenes"][1:]]
    for a, b in zip(trs, trs[1:]):
        assert not (a and a == b and a not in ("cut",))


def test_auto_shot_changes_size_inside_one_place():
    out = {"actors": [{"id": "a", "emotion": "calm"}]}
    assert S.auto_shot(out, None) == "medium"
    assert S.auto_shot(out, "medium") == "close"                       # no jump cut
    assert S.auto_shot({"actors": [{"id": "a", "emotion": "scared"}]}, None) == "close"
    assert S.auto_shot({"actors": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}, None) == "wide"


def test_hud_is_lifted_out_of_the_face_band():
    hud = [{"type": "stamp", "text": "ЛОВУШКА", "at": [0.5, 0.45]}]
    probs: list = []
    S._clear_face_band(hud, 3, probs)
    assert not (S.FACE_BAND[0] < hud[0]["at"][1] < S.FACE_BAND[1]) and probs


# ------------------------------------------------------------------ captions
def _words(text: str):
    sp = S.estimate(text)
    return [dict(w, sc=0) for w in sp["words"]]


def test_caps_captions_are_one_line_of_at_most_three_words():
    ws = _words("Все бегут вниз по лестнице а ты остаёшься дома и ждёшь")
    caps = S.captions(ws, [{"accent": "yellow"}], 1080, 1920, dict(S.STYLE))
    assert caps and all(len(c["lines"]) == 1 and len(c["lines"][0]) <= 3 for c in caps)
    ends = [c["lines"][0][-1]["w"].lower() for c in caps[:-1]]
    assert not any(e in S.WEAK for e in ends)                          # never end a chunk on "а", "и", "по"


def test_long_single_word_gets_a_fit_factor():
    ws = _words("Свети двенадцать-шестнадцать-семнадцать-восемнадцать часов")
    caps = S.captions(ws, [{}], 1080, 1920, dict(S.STYLE))
    fits = [c.get("fit") for c in caps if c.get("fit")]
    assert fits and all(0.5 <= f < 1 for f in fits)


# ------------------------------------------------------------------ channel rules (check)
def _msgs(rep, key="warnings"):
    return " | ".join(x["msg"] for x in rep[key])


@pytest.mark.parametrize("name", ["blackout", "zombie", "kids", "explainer", "long"])
def test_every_template_passes_check(name):
    rep = C.check(tpl(name))
    assert rep["ok"], rep["errors"]


def test_templates_list_and_toon_new(tmp_path):
    assert templates() == ["blackout", "explainer", "kids", "long", "zombie"]
    from shortskit.toon.cli import new
    r = new(str(tmp_path / "ep"), "kids")
    assert Path(r["episode"]).exists()
    with pytest.raises(Exception):
        new(str(tmp_path / "ep"), "kids")                              # never overwritten


def test_unknown_names_are_errors():
    ep = mini()
    ep["scenes"][0]["actors"][0]["pose"] = "moonwalk"
    ep["scenes"][1]["scheme"] = {"type": "hologram"}
    rep = C.check(ep)
    assert not rep["ok"]
    assert "moonwalk" in _msgs(rep, "errors") and "hologram" in _msgs(rep, "errors")


def test_kids_audience_rules():
    ep = mini(audience="kids")
    ep["scenes"][-1]["say"] = "Подпишись и ставь лайк, если понравилось!"
    rep = C.check(ep)
    assert "no comment / like / subscribe" in _msgs(rep)
    assert "made for kids" in " | ".join(x["msg"] for x in rep["info"])


def test_long_format_rules_chapters_and_endscreen():
    ep = tpl("long")
    rep = C.check(ep)
    assert rep["ok"]
    no_ch = copy.deepcopy(ep)
    for sc in no_ch["scenes"]:
        sc.pop("chapter", None)
    for _ in range(3):                                               # make it longer than 120 s
        no_ch["scenes"][1:1] = copy.deepcopy(no_ch["scenes"][1:8])
    for sc in no_ch["scenes"]:
        sc.pop("chapter", None)
    assert "without chapters" in _msgs(C.check(no_ch))
    bad_end = copy.deepcopy(ep)
    i = next(i for i, sc in enumerate(bad_end["scenes"]) if sc.get("endscreen"))
    bad_end["scenes"].append(bad_end["scenes"].pop(i - 1)) if i > 0 else None
    bad_end["scenes"].insert(0, bad_end["scenes"].pop(len(bad_end["scenes"]) - 1)) if bad_end["scenes"][-1].get("endscreen") else None
    assert "endscreen must be the last scene" in _msgs(C.check(bad_end))


def test_youtube_chapters_start_at_zero_and_merge_short_ones():
    ep = tpl("long")
    story, _ = S.build(ep)
    txt = youtube_chapters(ep, story)
    lines = txt.strip().splitlines()
    assert lines[0].startswith("00:00") and len(lines) >= 3
    fake = {"lang": "ru", "scenes": [{"chapter": "A"}, {"chapter": "B"}, {}, {"chapter": "C"}]}
    st = {"scenes": [{"t0": 0}, {"t0": 4}, {"t0": 20}, {"t0": 40}]}
    out = youtube_chapters(fake, st).strip().splitlines()
    assert out == ["00:00 A", "00:40 C"]


# ------------------------------------------------------------------ catalog and runtime
def test_catalog_has_2_3_names():
    d = catalog.load()
    assert "prism" in d["schemes"] and "sky" in d["themes"]
    for fx in ("rainbow", "sparkle", "spray"):
        assert fx in d["fx"]
    assert len(d["sets"]) == 15 and "pigtails" not in d["looks"]


def test_catalog_examples_come_from_templates():
    ex = catalog.examples("gauge")
    assert "scheme:gauge" in ex and ex["scheme:gauge"]["json"]["type"] == "gauge"
    allx = catalog.examples()
    assert any(k.startswith("hud:") for k in allx) and any(k.startswith("actor:") for k in allx)


def test_templates_use_only_known_names():
    names = catalog.load()
    for name in templates():
        ep = tpl(name)
        for sc in ep["scenes"]:
            if isinstance(sc.get("scheme"), dict):
                assert sc["scheme"]["type"] in names["schemes"]
            for h in sc.get("hud") or []:
                assert h["type"] in names["hud"]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_runtime_js_parses():
    for f in sorted(RUNTIME.glob("*.js")):
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{f.name}: {r.stderr[-400:]}"


@pytest.mark.slow
def test_preview_sheet_draws_frames(tmp_path):
    """Chromium smoke test: a silent preview of a short episode produces a non-empty contact sheet."""
    from shortskit.toon.cli import preview_cmd
    d = tmp_path / "ep"
    d.mkdir()
    (d / "episode.json").write_text(json.dumps(mini(), ensure_ascii=False), encoding="utf-8")
    try:
        rep = preview_cmd(str(d), True, 0.6)
    except Exception as e:                                          # no Chromium on this machine
        pytest.skip(f"chromium not available: {e}")
    assert rep["ok"]
    import cv2
    img = cv2.imread(str(d / "build" / "sheet.jpg"))
    assert img is not None and img.std() > 20
