"""2.3 synthetic blogger (AI persona): honest by design.

1. templates pass the check; blank template is refused until filled
2. disclosure is mandatory; the persona never claims to be human
3. ads: RU marking (erid), product claims need sources, no first-hand testimonials (FTC 16 CFR 465.2)
4. no device farms / ADB / anti-detect / fake engagement (FTC 16 CFR 465.8), negations in publishing.never are fine
5. medical promises, kids rules, AI clip length
6. build: toon episode passes toon-check; AI prompt pack keeps the character block; meta.txt carries the disclosure
7. persona-cut: clips + captions + labels through stack"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from shortskit.persona import core as P
from shortskit.util import ShortsError


def make(tmp_path: Path, template: str = "garden") -> Path:
    d = tmp_path / "ch"
    P.new(str(d), template)
    return d


def fill(ed: Path, says: dict | None = None, **over) -> dict:
    pl = json.loads((ed / "plan.json").read_text(encoding="utf-8"))
    for b in pl["beats"]:
        b["say"] = (says or {}).get(b["id"], "Полей рассаду тёплой водой утром.")
        if "action" in b:
            b["action"] = "поливает рассаду из лейки"
    pl["sources"] = ["https://extension.umn.edu/planting-and-growing-guides/starting-seeds-indoors"]
    pl.update(over)
    (ed / "plan.json").write_text(json.dumps(pl, ensure_ascii=False), encoding="utf-8")
    return pl


def errs(rep):
    return [x for x in rep["problems"] if x["level"] == "error"]


def test_templates_pass_and_blank_is_refused(tmp_path):
    assert {"garden", "cartoon3d", "blank"} <= set(P.templates())
    for t in ("garden", "cartoon3d"):
        d = tmp_path / t
        P.new(str(d), t)
        assert P.check(str(d))["ok"], t
    b = tmp_path / "blank"
    P.new(str(b), "blank")
    rep = P.check(str(b))
    assert not rep["ok"] and any(x["where"] == "name" for x in errs(rep))
    with pytest.raises(ShortsError):
        P.new(str(b), "blank")                                   # never overwritten


def test_disclosure_is_mandatory(tmp_path):
    d = make(tmp_path)
    p = json.loads((d / "persona.json").read_text(encoding="utf-8"))
    p["kind"] = "human"
    p["disclosure"] = {"bio": "Бабушка с огородом", "label": "", "description_line": "Подписывайтесь"}
    (d / "persona.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    where = {x["where"] for x in errs(P.check(str(d)))}
    assert {"kind", "disclosure.bio", "disclosure.label", "disclosure.description_line"} <= where


def test_plan_placeholders_block_until_filled(tmp_path):
    d = make(tmp_path)
    r = P.plan(str(d), "Почему рассада вытягивается", "tip")
    ed = Path(r["plan"]).parent
    assert not P.check(str(ed))["ok"]                          # <...> left
    fill(ed)
    rep = P.check(str(ed))
    assert rep["ok"], errs(rep)
    with pytest.raises(ShortsError):
        P.plan(str(d), "x", "nope")


@pytest.mark.parametrize("line", ["Я настоящая бабушка, а не нейросеть!", "Я не ИИ, я живой человек.", "Это не ИИ, всё снято вживую."])
def test_persona_never_claims_to_be_human(tmp_path, line):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "тема", "tip")["plan"]).parent
    fill(ed, {"hook": line})
    assert any("real human" in x["msg"] for x in errs(P.check(str(ed))))


def test_ad_needs_marking_sources_and_no_testimonials(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "Подкормка", "reply", ad=True)["plan"]).parent
    pl = fill(ed, {"answer": "Я сама пользуюсь удобрением «Росток», мне помогло."})
    rep = P.check(str(ed))
    msgs = " | ".join(x["msg"] for x in errs(rep))
    assert "erid" in msgs and "testimonial" in msgs and "source" in msgs
    pl["ad"].update({"advertiser": "ООО «Пример»", "erid": "2Vtzqx1", "product": "удобрение",
                     "claims": [{"claim": "для рассады", "source": "инструкция производителя"}]})
    for b in pl["beats"]:
        if b["id"] == "answer":
            b["say"] = "Производитель пишет: удобрение подходит для рассады овощей."
    (ed / "plan.json").write_text(json.dumps(pl, ensure_ascii=False), encoding="utf-8")
    rep = P.check(str(ed))
    assert rep["ok"], errs(rep)
    info = rep["episodes"][next(iter(rep["episodes"]))]
    assert "erid" in info["ad_marking"] and "реестре" in info["ad_marking"]


def test_testimonial_words_without_ad_are_not_ad_errors(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "тема", "tip")["plan"]).parent
    fill(ed, {"why": "Я пробовала сажать в марте, рано."})
    assert not any("testimonial" in x["msg"] for x in errs(P.check(str(ed))))


def test_no_automation_or_fake_engagement(tmp_path):
    d = make(tmp_path)
    p = json.loads((d / "persona.json").read_text(encoding="utf-8"))
    p["publishing"]["never"] = "никаких накруток и ферм телефонов"          # a negation is fine
    (d / "persona.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    assert P.check(str(d))["ok"]
    p["publishing"]["how"] = "ферма телефонов через ADB + антидетект, прогрев аккаунтов"
    (d / "persona.json").write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
    rep = P.check(str(d))
    assert not rep["ok"] and any("465.8" in x["msg"] for x in errs(rep))
    for bad in ("накрутка просмотров", "мультиаккаунтинг", "обход модерации", "подмена IMEI", "Magisk"):
        assert P.EVASION.search(bad), bad


def test_medical_promise_and_kids_rules(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "тема", "tip")["plan"]).parent
    fill(ed, {"proof": "Этот настой лечит давление."})
    assert any("medical" in x["msg"] for x in errs(P.check(str(ed))))
    ed2 = Path(P.plan(str(d), "детям", "tip", ad=True)["plan"]).parent
    fill(ed2, {"loop": "Подпишись и ставь лайк!"}, audience="kids")
    msgs = " | ".join(x["msg"] for x in errs(P.check(str(ed2))))
    assert "kids: no calls" in msgs and "kids: no advertising" in msgs


def test_ai_engine_limits_speech_per_clip(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "тема", "tip", engine="ai")["plan"]).parent
    long_line = " ".join(["слово"] * 30)                                 # ~12.5 s > 8 s clip
    fill(ed, {"how": long_line})
    assert any("clip limit" in x["msg"] for x in errs(P.check(str(ed))))


def test_build_toon_episode_passes_toon_check(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "Почему рассада вытягивается", "tip")["plan"]).parent
    fill(ed)
    r = P.build(str(ed))
    ep = json.loads((ed / "episode.json").read_text(encoding="utf-8"))
    assert r["toon_check"]["ok"] and ep["cast"]["host"]["look"] == "granny"
    assert "ИИ-персонаж" in ep["brand"] and ep["scenes"][0]["set"]["id"] == "dacha"
    meta = (ed / "meta.txt").read_text(encoding="utf-8")
    assert "созданы с помощью ИИ" in meta and "Использование ИИ" in meta
    assert P.build(str(ed))["toon_check"]["ok"]            # untouched episode.json: rebuild freely (persona or code changed)
    ep["title"] = "правка руками"
    (ed / "episode.json").write_text(json.dumps(ep, ensure_ascii=False), encoding="utf-8")   # hand-edited after the build
    with pytest.raises(ShortsError):
        P.build(str(ed))
    assert P.build(str(ed), force=True)["toon_check"]["ok"]


def test_build_cuts_hook_and_long_beats_by_sentence(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "Почему рассада вытягивается", "tip")["plan"]).parent
    pl = fill(ed, {"hook": "Рассада тянется, как ниточка? Вода тут ни при чём.",
                   "why": "Главная причина тонких длинных стеблей: мало *света*. На подоконнике его не хватает."})
    pl["beats"][0]["title"] = "Вода ни при чём"
    pl["beats"][1]["props"] = [{"id": "lamp", "on": "света"}]          # anchored beat stays whole
    (ed / "plan.json").write_text(json.dumps(pl, ensure_ascii=False), encoding="utf-8")
    ep = P._toon_episode(pl, P.load_persona(d)[0], "x")
    sc = ep["scenes"]
    assert sc[0]["say"] == "Рассада тянется, как ниточка?" and "hud" not in sc[0] and sc[0]["set"]["id"] == "dacha"
    assert sc[1]["say"] == "Вода тут ни при чём." and sc[1]["hud"][0]["text"] == "Вода ни при чём" and sc[1]["shot"] != sc[0]["shot"]
    assert sc[2]["say"].startswith("Главная") and sc[2]["say"].endswith("хватает.") and sc[2]["props"][0]["on"] == "света"
    assert len(sc) == len(pl["beats"]) + 1
    assert all(a.get("shot") != b.get("shot") for a, b in zip(sc, sc[1:]) if "scheme" not in a and "scheme" not in b)
    pl["beats"][2]["title"] = "Тёплая вода"                              # a titled beat cuts to the persona's item card
    sc = P._toon_episode(pl, P.load_persona(d)[0], "x")["scenes"]
    card = [x for x in sc if x.get("scheme", {}).get("type") == "closeup"]
    assert len(card) == 1 and card[0]["scheme"]["item"] == "pot" and card[0]["scheme"]["title"] == "Тёплая вода" and "actors" not in card[0]


def test_build_ai_prompt_pack(tmp_path):
    d = make(tmp_path, "cartoon3d")
    ed = Path(P.plan(str(d), "Как работает холодильник", "tip")["plan"]).parent
    fill(ed, {"hook": "Почему в холодильнике холодно, если внутри нет льда?"})
    r = P.build(str(ed))
    shots = json.loads((ed / "shots.json").read_text(encoding="utf-8"))
    md = (ed / "prompts.md").read_text(encoding="utf-8")
    assert r["engine"] == "ai" and len(shots) == 5 and shots[0]["file"] == "clips/01.mp4"
    assert "Дед Егор" in md and "3D-мультфильм" in md and "«Почему в холодильнике холодно" in md
    assert all(3 <= s["seconds"] <= 8 for s in shots)


def test_build_refuses_with_errors(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "тема", "tip")["plan"]).parent
    with pytest.raises(ShortsError):
        P.build(str(ed))


def test_spread_srt_is_monotonic():
    srt = P.spread_srt(["раз два три четыре пять", "шесть семь"], [3.0, 2.0])
    blocks = [b for b in srt.strip().split("\n\n") if b.strip()]
    assert len(blocks) == 3
    times = [b.splitlines()[1] for b in blocks]
    starts = [t.split(" --> ")[0] for t in times]
    assert starts == sorted(starts) and starts[2] >= "00:00:03,000"


def test_label_layer_size():
    from shortskit import stack
    im = stack._label_layer("ИИ-персонаж")
    assert 200 < im.width < 420 and 40 < im.height < 80 and im.mode == "RGBA"


@pytest.mark.slow
def test_persona_cut_assembles_clips_with_labels(tmp_path):
    d = make(tmp_path)
    ed = Path(P.plan(str(d), "Подкормка", "reply", engine="ai", ad=True)["plan"]).parent
    pl = fill(ed)
    pl["ad"].update({"advertiser": "ООО «Пример»", "erid": "2Vtzqx1", "product": "удобрение",
                     "claims": [{"claim": "для рассады", "source": "инструкция"}]})
    (ed / "plan.json").write_text(json.dumps(pl, ensure_ascii=False), encoding="utf-8")
    P.build(str(ed))
    for i in (1, 2):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=540x960:r=30:d=1.6", "-f", "lavfi",
                        "-i", f"sine=f={300 + 100 * i}:d=1.6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        str(ed / "clips" / f"0{i}.mp4")], check=True)
    r = P.cut(str(ed), check_render=False)
    assert Path(r["out"]).exists() and r["clips"] == 2 and r["notes"]           # 2 clips for 4 beats -> note
    lay = json.loads(Path(r["out"]).with_suffix(".layout.json").read_text(encoding="utf-8"))
    texts = [x["text"] for x in lay["labels"]]
    assert texts[0] == "ИИ-персонаж" and texts[1].startswith("Реклама. ООО «Пример». erid: 2Vtzqx1")
