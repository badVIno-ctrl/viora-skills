"""2.4: built-in VoiceEngine, music "auto" from YouTube, code videos (html seek + window.SHORTS), brand.md, fx-get."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import pytest

from shortskit import brandmd as BM
from shortskit import fxlib as FX
from shortskit import music as MU
from shortskit import voice as VE
from shortskit.config import skill_root

ROOT = skill_root()


# ---------------------------------------------------------------- voice: aliases, attributes, gender

def test_aliases_keep_old_plans_working():
    assert VE.attrs_for("ru-male-1", "ru") == "диктор"
    assert VE.attrs_for("ru-female-1", "ru") == "ведущая"
    assert VE.attrs_for(None, "ru") == "диктор"            # default voice for the language
    assert VE.attrs_for("", "en") == "диктор"
    assert VE.attrs_for("ж, 90, шёпотом", "ru") == "ж, 90, шёпотом"


def test_alias_inside_an_attribute_list_is_expanded():
    # toon "tone" on top of an old episode voice: "ru-female-1, шёпотом"
    assert VE.attrs_for("ru-female-1, шёпотом", "ru") == "ведущая, шёпотом"
    assert VE.attrs_for("ru-male-2, сердито", "ru") == "м, 26, m4, сердито"


def test_foreign_voice_ids_are_left_to_their_engines():
    assert VE.is_foreign_voice("ru-RU-DmitryNeural")
    assert VE.is_foreign_voice("ru_RU-irina-medium")
    assert VE.is_foreign_voice("nova")
    assert not VE.is_foreign_voice("ж, 30")
    assert not VE.supports("de", "м, 30")                  # other languages go to edge-tts
    assert VE.supports("ru", "дракон") and VE.supports("en", "f2")


@pytest.mark.parametrize("voice,gender", [("ж, 72, voice=Валя", "female"), ("м, 7", "male"), ("ведущая", "female"),
                                          ("m2", "male"), ("f3", "female"), ("ru-RU-DmitryNeural", None)])
def test_gender_of_for_fallback_engines(voice, gender):
    assert VE.gender_of(voice, "ru") == gender


def test_parse_keeps_unknown_words_as_a_stable_name():
    spec, name = VE.parse("мультяшка, м, Пушок")
    assert name == "Пушок" and spec.get("voice") == "Пушок"


def test_marks_to_words_keeps_original_tokens_and_drops_pauses():
    text = "Привет, мир! [пауза 1] Как дела?"
    marks = [{"text": "Привет, мир!", "s": 0.0, "e": 1.0, "words": [("привет", 0.05, 0.45), ("мир", 0.5, 0.9)]},
             {"text": "Как дела?", "s": 2.0, "e": 2.8, "words": [("как", 2.0, 2.3), ("дела", 2.35, 2.8)]}]
    words, est = VE.marks_to_words(text, marks, None)
    assert [w["w"] for w in words] == ["Привет,", "мир!", "Как", "дела?"]
    assert words[0]["s"] == 0.05 and words[3]["e"] == 2.8 and est is False


def test_models_pack_is_described_and_sealed():
    info = VE.pack_info()
    assert info["file"] == VE.PACK_NAME and len(info["sha256"]) == 64
    assert VE.pack_path().exists(), "assets/voice/voiceengine-models.tar.xz must ship with the skill"
    assert abs(VE.pack_path().stat().st_size - info["bytes"]) == 0


def test_voiceengine_off_in_tests_and_status_shape():
    assert VE.disabled()                                   # conftest: SHORTS_VOICEENGINE=off
    st = VE.status()
    assert st["enabled"] is False and st["pack"] is True and "deps_missing" in st


def test_tts_chain_puts_voiceengine_first_when_available(monkeypatch):
    from shortskit.engine import tts
    monkeypatch.setattr(VE, "available", lambda: True)
    assert tts.available_engines()[0] == "voiceengine"
    monkeypatch.setattr(VE, "available", lambda: False)
    assert "voiceengine" not in tts.available_engines()


@pytest.mark.skipif(os.environ.get("SHORTS_TEST_VOICEENGINE") != "1" and not VE.models_dir(),
                    reason="VoiceEngine models not unpacked here (python3 tools/shorts.py voice-setup)")
def test_real_voiceengine_speaks_russian_with_exact_word_timings(tmp_path, monkeypatch):
    monkeypatch.delenv("SHORTS_VOICEENGINE", raising=False)
    if VE.deps_missing():
        pytest.skip("onnxruntime missing")
    r = VE.speak("Проверка голоса без интернета.", tmp_path / "v.wav", voice="ж, 30, f5", lang="ru")
    assert r["duration"] > 1.0 and not r["estimated"]
    assert [w["w"] for w in r["words"]] == ["Проверка", "голоса", "без", "интернета."]
    assert all(b["s"] >= a["e"] - 1e-3 for a, b in zip(r["words"], r["words"][1:]))


# ---------------------------------------------------------------- toon: voices of the cast

def test_scene_voice_cast_and_tone():
    from shortskit.toon.story import scene_voice
    ep = {"lang": "ru", "voice": "ru-female-1", "cast": {"masha": {"voice": "ж, 7, voice=Маша"}, "pushok": {}}}
    assert scene_voice(ep, {"say": "x"}) is None                                   # narrator
    assert scene_voice(ep, {"speaker": "masha"}) == "ж, 7, voice=Маша"
    assert scene_voice(ep, {"speaker": "masha", "tone": "восторженно"}) == "ж, 7, voice=Маша, восторженно"
    assert scene_voice(ep, {"speaker": "pushok", "tone": "шёпотом"}) == "ведущая, шёпотом"   # no own voice: narrator + tone
    assert scene_voice(ep, {"speaker": "masha", "voice": "дракон"}) == "дракон"


def test_kids_template_gives_each_hero_a_voice():
    ep = json.loads((ROOT / "templates/toon/kids.json").read_text(encoding="utf-8"))
    assert all(c.get("voice") for c in ep["cast"].values())
    assert ep.get("music") == "auto"


# ---------------------------------------------------------------- music auto

def test_music_defaults_are_auto():
    from shortskit import memory as M
    from shortskit.planner import _music_pref
    assert M.DEFAULTS["music"]["source"] == "auto"
    assert _music_pref({}) == {"source": "auto"}
    assert _music_pref({"music": {"source": "assets/audio/bed.mp3"}}) == {"source": "auto"}   # old placeholder default
    assert _music_pref({"music": {"source": "my.mp3"}}) == {"source": "my.mp3"}
    assert _music_pref({"music": {"source": "auto", "mood": "tense"}}) == {"source": "auto", "mood": "tense"}


def test_is_auto_and_none():
    assert MU.is_auto("auto") and MU.is_auto({"source": "auto"}) and not MU.is_auto("track.mp3")
    assert MU.is_none("none") and MU.is_none("без музыки") and MU.is_none({"source": "off"}) and not MU.is_none("auto")


@pytest.mark.parametrize("text,mood", [("Как выжить при зомби-апокалипсисе", "tense"), ("детский мультик про радугу", "happy"),
                                       ("нейросеть пишет код", "tech"), ("эпичный трейлер", "epic"), ("напряжённый", "tense"),
                                       ("бабушка на огороде", "calm"), ("", "inspiring")])
def test_mood_of(text, mood):
    assert MU.mood_of(text) == mood


def test_queries_ask_for_free_instrumental_under_a_voice():
    q = MU.queries("tense", voice=True)
    assert q and all("no copyright" in x or "royalty free" in x or "free" in x for x in q)
    assert MU.queries("tense", query="my own query")[0] == "my own query"


def test_score_prefers_free_instrumental_and_punishes_vocals_and_mixes():
    good = {"id": "a", "title": "Dark suspense background music (no copyright)", "channel": "Audio Library", "duration": 150}
    vocal = {"id": "b", "title": "Dark song lyrics", "channel": "Some Singer", "duration": 200}
    mix = {"id": "c", "title": "Dark music 1 hour mix", "channel": "x", "duration": 3600}
    sg, _ = MU.score(good, voice=True, length=30)
    sv, why = MU.score(vocal, voice=True, length=30)
    sm, _ = MU.score(mix, voice=True, length=30)
    assert sg > sv and sg > sm and "vocals under a voice-over" in why
    su, why = MU.score(good, voice=True, length=30, used={"a"})
    assert su < sg and "used recently" in why


def test_disabled_search_means_no_music(tmp_path):
    assert MU.disabled()                                    # conftest: SHORTS_MUSIC_AUTO=off
    rep = MU.resolve("auto", length=20, voice=True, context="x", base=tmp_path)
    assert rep["ok"] is False and rep["status"] == "disabled"


def _fake_rep(tmp_path: Path) -> dict:
    f = tmp_path / "found.wav"
    f.write_bytes(b"RIFF")
    return {"ok": True, "file": str(f), "start": 12.5, "drop": 20.0, "beats": [12.5, 13.0, 13.5], "length": 40,
            "track": {"id": "x1", "title": "Tense Bed", "channel": "Free Music", "url": "https://www.youtube.com/watch?v=x1"},
            "credit": "Музыка: Tense Bed - Free Music (https://www.youtube.com/watch?v=x1)"}


def test_apply_to_plan_replaces_auto_by_the_found_track(tmp_path, monkeypatch):
    seen = {}

    def fake_resolve(spec, **kw):
        seen.update(spec=spec, **kw)
        return _fake_rep(tmp_path)
    monkeypatch.setattr(MU, "resolve", fake_resolve)
    plan = {"meta": {"emotion": "tense"}, "audio": {"music": {"source": "auto", "mood": "tense", "duck_db": -10}},
            "scenes": [{"say": "Зомби уже в подъезде"}], "metadata": {"topic": "выживание"}}
    rep = MU.apply_to_plan(plan, tmp_path, tmp_path / "out", total=25.0, has_voice=True, lang="ru")
    m = plan["audio"]["music"]
    assert rep["ok"] and m["source"].endswith("found.wav") and m["start"] == 12.5 and m["duck_db"] == -10
    assert "mood" not in m and seen["spec"]["mood"] == "tense" and seen["voice"] is True
    assert (tmp_path / "out" / "music.json").exists()


def test_apply_to_plan_blocked_goes_on_without_music(tmp_path, monkeypatch):
    monkeypatch.setattr(MU, "resolve", lambda spec, **kw: {"ok": False, "status": "blocked",
                                                           "local_commands": ["yt-dlp ..."]})
    plan = {"audio": {"music": "auto"}, "scenes": [{"say": "x"}]}
    rep = MU.apply_to_plan(plan, tmp_path, tmp_path / "out", total=10.0, has_voice=True, lang="ru")
    assert rep["status"] == "blocked" and plan["audio"]["music"]["source"] == "none"
    assert "on your computer" in MU.summary(rep)


def test_apply_to_plan_leaves_user_track_alone(tmp_path):
    plan = {"audio": {"music": {"source": "mine.mp3"}}}
    assert MU.apply_to_plan(plan, tmp_path, tmp_path, total=10, has_voice=True, lang="ru") is None
    assert plan["audio"]["music"]["source"] == "mine.mp3"


def test_credit_goes_into_every_description(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"")
    rep = _fake_rep(tmp_path)
    (tmp_path / "v.music.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    assert MU.credit_for_video(video) == rep["credit"]
    item = {"descriptions": [{"tone": "loud", "text": "Громко"}, {"tone": "calm", "text": "Спокойно"}], "description": "Одно"}
    out = MU.with_credit(item, video)
    assert all(rep["credit"] in d["text"] for d in out["descriptions"]) and rep["credit"] in out["description"]
    assert MU.LICENCE_NOTE in out["notes"] and out["music_credit"] == rep["credit"]
    assert MU.with_credit(out, video)["descriptions"][0]["text"].count(rep["credit"]) == 1      # no double credit
    assert "\u2014" not in MU.credit({"title": "A \u2014 B", "channel": "C", "url": "u"})       # no long dashes in copy


def test_edit_without_music_but_none_is_explained(tmp_path):
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "tools/shorts.py"), "edit", "--music", "none", "--video", "x.mp4",
                        "-o", str(tmp_path / "p.json")], capture_output=True, text=True)
    assert r.returncode != 0 and "without_music" in (r.stdout + r.stderr)


# ---------------------------------------------------------------- brand.md

def test_brand_md_parse_and_import(tmp_path):
    b = BM.parse(BM.TEMPLATE)
    assert b["palette"] == {"bg": "#0B0B0B", "fg": "#F2F2F2", "accent": "#FF5A1F"}
    assert b["fonts"]["display"].startswith("Montserrat") and b["voice"] == "м, 32, m4"
    assert any("easing" in m for m in b["motion"])
    src = tmp_path / "brand.md"
    src.write_text(BM.TEMPLATE, encoding="utf-8")
    rep = BM.import_md(src, tmp_path / "out")
    bj = json.loads(Path(rep["brand_json"]).read_text(encoding="utf-8"))
    css = Path(rep["brand_css"]).read_text(encoding="utf-8")
    assert bj["palette"]["accent"] == "#FF5A1F" and "--accent" in css and "@font-face" in css


def test_brand_md_english_keys():
    b = BM.parse("# Brand\n## Colors\n- background: #101010\n- text: #FAFAFA\n- accent: #00C2FF\n")
    assert b["palette"] == {"bg": "#101010", "fg": "#FAFAFA", "accent": "#00C2FF"}


# ---------------------------------------------------------------- fx-get and code videos

def test_bundled_effects_copy_with_licence(tmp_path):
    names = {x["name"] for x in FX.list_bundled()}
    assert {"p5.brush", "thinking-orbs"} <= names
    for spec in ("p5.brush", "orbs"):
        rep = FX.get(spec, tmp_path)
        d = Path(rep["dir"])
        assert rep["license_ok"] and rep["license"] == "MIT"
        assert any(p.name.upper().startswith("LICENSE") for p in d.iterdir())
        note = (d / "SOURCE.md").read_text(encoding="utf-8")
        assert "licence: MIT" in note and "taken:" in note
    assert (tmp_path / "vendor/p5.brush/brush.js").stat().st_size > 50_000
    assert "window.ThinkingOrbs" in (tmp_path / "vendor/thinking-orbs/orbs.js").read_text(encoding="utf-8")


def test_licence_detection():
    assert FX.license_of("MIT License\n\nPermission is hereby granted, free of charge") == "MIT"
    assert FX.license_of("GNU GENERAL PUBLIC LICENSE Version 3") == "GPL"
    assert FX.license_of("all rights reserved") == "unknown"


def test_beats_js_main_beat(tmp_path):
    from shortskit.cli24 import beats_js
    track = ROOT / "assets/audio/bed.mp3"
    out = tmp_path / "beats.js"
    r = beats_js(str(track), str(out), start=0.0, length=12.0, main="5")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("// shorts.py beats") and "window.BEATS = " in text
    data = json.loads(text.split("window.BEATS = ", 1)[1].rstrip().rstrip(";"))
    assert r["beats"] >= 5 and data["main"] == data["beats"][4]
    r2 = beats_js(str(track), str(out), main="7.25s")
    assert r2["main"] == 7.25


def test_html_module_pages_are_served(tmp_path):
    from shortskit.adapters import html as HT
    classic = tmp_path / "a.html"
    classic.write_text("<script src='x.js'></script>", encoding="utf-8")
    module = tmp_path / "b.html"
    module.write_text("<script type=\"module\">import * as T from './vendor/three.module.js'</script><p>ok</p>",
                      encoding="utf-8")
    assert not HT.needs_http(classic) and HT.needs_http(module)
    with HT.page_url(classic) as u:
        assert u.startswith("file://")
    with HT.page_url(module) as u:
        assert u.startswith("http://127.0.0.1:")
        assert b"ok" in urllib.request.urlopen(u, timeout=5).read()


def test_code_video_template_contract():
    tpl = ROOT / "templates/code-video"
    html = (tpl / "scene.html").read_text(encoding="utf-8")
    plan = json.loads((tpl / "plan.json").read_text(encoding="utf-8"))
    assert "window.seek" in html and "window.SHORTS" in html and "Math.random()" not in html
    draw, _, preview = html.partition("if (!window.__shortsVT)")       # real time only in the browser preview loop
    assert preview and "Date.now(" not in draw and "performance.now(" not in draw
    assert plan["scenes"][0]["source"]["type"] == "html" and plan["audio"]["music"]["source"] == "auto"
    assert VE.attrs_for(plan["audio"]["voice"]["voice"], "ru")


def test_code_new_makes_a_project(tmp_path, monkeypatch):
    import argparse
    from shortskit.cli24 import cmd_code_new
    d = tmp_path / "code1"
    assert cmd_code_new(argparse.Namespace(dir=str(d), fx="p5.brush,thinking-orbs", brand=None, force=False)) == 0
    for f in ("scene.html", "plan.json", "README.md", "fonts/Montserrat-ExtraBold.ttf", "vendor/p5.brush/brush.js",
              "vendor/thinking-orbs/orbs.js"):
        assert (d / f).exists(), f
    from shortskit import plan as P
    plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
    errs = [i for i in P.check(plan, d) if i.level == "error"]
    assert not errs, errs


def test_docs_name_the_24_commands():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    router = (ROOT / "ROUTER.md").read_text(encoding="utf-8")
    for word in ("reference/voice.md", "reference/code-video.md", "music: auto", "brand-md import", "voiceengine-models.tar.xz"):
        assert word in skill, word
    for cmd in ("`voice`", "`code-new`", "`music-find`", "`fx-get`", "`brand-md import`"):
        assert cmd in router, cmd
    assert (ROOT / "VERSION").read_text().strip() == "2.4.0"
