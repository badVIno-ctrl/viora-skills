"""2.0: three variants (loud -> calm) of titles, descriptions and covers, and the hand-off that carries them."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest import mini_plan
from shortskit import memory as M
from shortskit import pack as P
from shortskit.deliver import deliver
from shortskit.meta import cover as C
from shortskit.meta import packaging as PK
from shortskit.meta.tones import derive_cover_texts, loudness_of, normalize_cover_texts
from shortskit.util import ShortsError, count_emoji, has_long_dash

TONES = ["loud", "medium", "calm"]


def manifest(lang="ru"):
    return {"name": "mini", "language": lang, "platforms": ["youtube_shorts", "tiktok"]}


def made(lang="ru", plan=None):
    plan = plan or mini_plan()
    plan["scenes"][0]["say"] = "Два бесплатных сайта и оба пригодятся." if lang == "ru" else "Two free sites you will use."
    d = PK.auto_draft(plan, manifest(lang), lang)
    return plan, d, PK.build(plan, manifest(lang), d, M.load())


def desc(tone, text=None, **kw):
    return {"tone": tone, "psychology": "trigger", "text": text or f"Строка один {tone}.\nСтрока два.", **kw}


def draft_with(plan, **over):
    d = PK.auto_draft(plan, manifest(), "ru")
    d.update(over)
    return d


# ---------------------------------------------------------------- metadata generation

@pytest.mark.parametrize("lang", ["ru", "en"])
def test_fallback_makes_three_descriptions_loud_to_calm(lang):
    _, _, m = made(lang)
    assert not m["errors"], m["errors"]
    ds = m["descriptions"]
    assert [x["tone"] for x in ds] == TONES
    assert all(x["text"].strip() and x["psychology"] for x in ds)
    assert len({x["text"] for x in ds}) == 3
    for x in ds:
        lines = x["text"].strip().splitlines()
        assert 3 <= lines[-1].count("#") <= 5 and lines[-1].startswith("#")
        first = " ".join(lines[:2])
        assert "#" not in first and "http" not in first
        assert not has_long_dash(x["text"])
    assert m["description"] == next(x["text"] for x in ds if x["tone"] == m["recommended_description"])
    assert m["recommended_description"] == m["titles"][m["recommended"] - 1]["tone"]


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_titles_five_to_seven_and_all_tiers_present(lang):
    _, _, m = made(lang)
    ts = m["titles"]
    assert 5 <= len(ts) <= 7
    assert [t["loudness"] for t in ts] == sorted(t["loudness"] for t in ts)
    assert {t["tone"] for t in ts} == set(TONES)
    assert count_emoji(ts[0]["title"]) == 1 and ts[0]["text"].split()[0].isupper()
    calm = [t for t in ts if t["tone"] == "calm"]
    assert all(len(t["hashtags"]) <= 3 for t in calm) and all(not count_emoji(t["title"]) for t in calm)


def test_missing_tier_is_an_error():
    plan = mini_plan()
    titles = [{"text": f"ГРОМКО {i} \U0001F631", "loudness": 1 + i % 2} for i in range(5)]
    m = PK.build(plan, manifest(), draft_with(plan, titles=titles), M.load())
    assert any("medium" in e and "calm" in e and "tiers" in e for e in m["errors"]), m["errors"]


def test_loudness_words_are_accepted():
    assert [loudness_of(x) for x in ("loud", "medium", "calm", 2, "4", None)] == [1, 3, 5, 2, 4, 3]
    plan = mini_plan()
    base = PK.auto_draft(plan, manifest(), "ru")["titles"]
    for t, w in zip(base, ["loud", "loud", "medium", "medium", "calm", "calm"]):
        t["loudness"] = w
    m = PK.build(plan, manifest(), draft_with(plan, titles=base), M.load())
    assert not m["errors"], m["errors"]
    assert [t["tone"] for t in m["titles"]][:2] == ["loud", "loud"]


def test_reference_title_pattern_passes_validation():
    plan = mini_plan()
    titles = [
        {"text": "2 АККАУНТА - 1 ОТКАЗ \U0001F480 ПОИСК РАБОТЫ В 2026 #shorts #нейросетьзахватитмир", "loudness": "loud"},
        {"text": "ИИ СДЕЛАЛ 8 ПУШЕК БЕЗ 3D-ШНИКА \U0001F631 #shorts #нейросети #opus55 #gamedev #ии #игры", "loudness": "loud"},
        {"text": "Как нейросеть сделала 8 пушек для игры", "loudness": "medium"},
        {"text": "Нейросеть сделала оружие для игры", "loudness": "medium"},
        {"text": "Оружие для игры из нейросети", "loudness": "calm"},
        {"text": "Нейросеть и gamedev: коротко о главном", "loudness": "calm"},
    ]
    m = PK.build(plan, manifest(), draft_with(plan, titles=titles), M.load())
    assert not m["errors"], m["errors"]
    t0, t1 = m["titles"][0], m["titles"][1]
    assert t0["title"].endswith("#shorts #нейросетьзахватитмир") and t0["chars"] <= 100
    assert t1["hashtags"][:2] == ["#shorts", "#нейросети"] and len(t1["hashtags"]) == 6 and t1["chars"] <= 100
    assert not any("hook ends" in w or "without emoji" in w for w in m["warnings"]), m["warnings"]


def test_loud_hook_after_40_chars_warns():
    plan = mini_plan()
    base = PK.auto_draft(plan, manifest(), "ru")["titles"]
    base[0]["text"] = "ОЧЕНЬ ДЛИННЫЙ ГРОМКИЙ ЗАГОЛОВОК БЕЗ ЕДИНОГО СМЫСЛА \U0001F631"
    m = PK.build(plan, manifest(), draft_with(plan, titles=base), M.load())
    assert any("hook ends" in w for w in m["warnings"])


def test_cover_texts_three_distinct_short():
    _, _, m = made()
    ct = m["cover_texts"]
    assert [x["tone"] for x in ct] == TONES
    assert len({x["text"] for x in ct}) == 3
    assert all(3 <= len(x["text"].split()) <= 5 for x in ct)
    assert ct[0]["text"] == ct[0]["text"].upper()


def test_derive_and_normalize_cover_texts():
    ru = derive_cover_texts("ПАРОЛЬ", "защита паролей", "ru", upper=False)
    assert all(3 <= len(x["text"].split()) <= 5 for x in ru)
    assert normalize_cover_texts(["А Б В", "Г Д Е", "Ж З И"])[2] == {"tone": "calm", "text": "Ж З И"}
    assert normalize_cover_texts({"calm": "x y z", "loud": "a b c"})[0]["tone"] == "loud"
    assert normalize_cover_texts("junk") == []


def test_legacy_draft_without_descriptions_still_builds():
    plan = mini_plan()
    legacy = {k: v for k, v in PK.auto_draft(plan, manifest(), "ru").items() if k not in ("descriptions", "cover_texts")}
    legacy["cover_text"] = "ОДИН ДВА ТРИ"
    m = PK.build(plan, manifest(), legacy, M.load())
    assert not m["errors"], m["errors"]
    assert len(m["descriptions"]) == 3 and any("no descriptions" in w for w in m["warnings"])
    assert m["cover_texts"][0]["text"] == "ОДИН ДВА ТРИ" and m["cover_text"] == "ОДИН ДВА ТРИ"


def test_agent_descriptions_get_links_and_tags_appended():
    plan = mini_plan()
    plan["layout"]["bottom"] = {"links": ["https://t.me/VioraStudio"]}
    ds = [desc("calm"), desc("loud", hashtags=["#shorts", "#ии", "#ai", "#тест"]), desc("medium", "Тело.\n#один #два #три")]
    m = PK.build(plan, manifest(), draft_with(plan, descriptions=ds), M.load())
    assert not m["errors"], m["errors"]
    assert [x["tone"] for x in m["descriptions"]] == TONES
    loud, med = m["descriptions"][0], m["descriptions"][1]
    assert "Telegram: https://t.me/VioraStudio" in loud["text"] and loud["text"].strip().splitlines()[-1] == "#shorts #ии #ai #тест"
    assert med["hashtags"] == ["#один", "#два", "#три"] and med["text"].count("Тело.") == 1


# ---------------------------------------------------------------- validation failures

@pytest.mark.parametrize("ds,needle", [
    ([desc("loud"), desc("calm")], "exactly 3 descriptions"),
    ([desc("loud"), desc("medium"), desc("calm"), desc("calm")], "exactly 3 descriptions"),
    ([desc("loud"), desc("medium"), desc("calm", "   ")], "calm: text is empty"),
    ([desc("loud"), desc("loud"), desc("calm")], "used twice"),
    ([desc("loud"), desc("medium"), desc("fierce")], "tone must be"),
    ([desc("loud"), desc("medium"), desc("calm", hashtags=["#a", "#b", "#c", "#d", "#e", "#f"])], "need 3-5"),
])
def test_description_validation_failures(ds, needle):
    plan = mini_plan()
    m = PK.build(plan, manifest(), draft_with(plan, descriptions=ds), M.load())
    assert any(needle in e for e in m["errors"]), (needle, m["errors"])


def test_long_dash_in_a_description_is_fixed_not_kept():
    plan = mini_plan()
    ds = [desc("loud"), desc("medium"), desc("calm", "Текст \u2014 с тире")]
    m = PK.build(plan, manifest(), draft_with(plan, descriptions=ds), M.load())
    assert not m["errors"] and not has_long_dash(m["descriptions"][2]["text"])


def test_few_hashtags_are_padded_with_warning():
    plan = mini_plan()
    ds = [desc("loud"), desc("medium"), desc("calm", hashtags=["#один"])]
    m = PK.build(plan, manifest(), draft_with(plan, descriptions=ds), M.load())
    assert not m["errors"], m["errors"]
    assert len(m["descriptions"][2]["hashtags"]) == 3 and any("padded" in w for w in m["warnings"])


def test_bad_cover_texts_are_errors():
    plan = mini_plan()
    m = PK.build(plan, manifest(), draft_with(plan, cover_texts=["один два три четыре пять шесть", "а б в", "г д е"]), M.load())
    assert any("6 words" in e for e in m["errors"])
    m = PK.build(plan, manifest(), draft_with(plan, cover_texts=["а б в"]), M.load())
    assert any("exactly 3" in e for e in m["errors"])


def ad_plan(**md):
    plan = mini_plan()
    plan["metadata"] = {"ad": {"name": "Quattro", "url": "https://t.me/q_bot?start=r_1"}, **md}
    return plan


def test_ad_plan_requires_disclosure_in_every_variant():
    plan = ad_plan()
    ds = [desc("loud", "Реклама. https://t.me/q_bot?start=r_1"), desc("medium"), desc("calm", "Реклама.")]
    m = PK.build(plan, manifest(), draft_with(plan, descriptions=ds), M.load())
    errs = " ".join(m["errors"])
    assert "description medium: ad plan needs an ad disclosure" in errs
    assert "description calm: ad plan needs the exact ad link" in errs
    assert "description loud" not in errs


def test_ad_plan_fallback_is_valid_and_carries_the_ad_in_each_variant():
    for lang in ("ru", "en"):
        plan, _, m = made(lang, ad_plan())
        assert not m["errors"], m["errors"]
        assert all("https://t.me/q_bot?start=r_1" in x["text"] for x in m["descriptions"])


def test_not_an_ad_needs_no_disclosure():
    _, _, m = made()
    assert not any("ad plan" in e for e in m["errors"])


# ---------------------------------------------------------------- metadata.md and package_dir

def test_metadata_md_lists_all_variants():
    plan, _, m = made("ru")
    md = PK.to_md(m, "ru", manifest())
    assert "громкое" in md and "среднее" in md and "спокойное" in md and "рекомендую" in md
    assert md.count("Приём:") == 3 and "Тексты на обложках" in md
    for x in m["descriptions"]:
        assert x["text"].splitlines()[0] in md
    md_en = PK.to_md(made("en")[2], "en", manifest("en"))
    assert "Descriptions (loud to calm)" in md_en and md_en.count("Trigger:") == 3


def test_package_dir_writes_variants(tmp_path):
    plan = mini_plan()
    plan["scenes"][0]["say"] = "Два бесплатных сайта."
    (tmp_path / "manifest.json").write_text(json.dumps(manifest()), encoding="utf-8")
    (tmp_path / "plan.resolved.json").write_text(json.dumps(plan), encoding="utf-8")
    res = PK.package_dir(tmp_path)
    assert res["ok"], res["errors"]
    saved = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert [x["tone"] for x in saved["descriptions"]] == TONES and saved["description"]
    assert [x["tone"] for x in json.loads((tmp_path / "metadata.draft.json").read_text(encoding="utf-8"))["descriptions"]] == TONES
    assert "Описания" in (tmp_path / "metadata.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- covers

def test_covers_follow_the_tones_and_write_a_prompt_per_variant(tmp_path, monkeypatch):
    from test_cover import _fake_out
    monkeypatch.delenv("SHORTS_IMAGE_PROVIDER", raising=False)
    d = _fake_out(tmp_path)
    (d / "metadata.json").write_text(json.dumps({"cover_texts": [
        {"tone": "loud", "text": "ПАРОЛЬ ЗА МИНУТУ"}, {"tone": "medium", "text": "КАК ЗАЩИТИТЬ ПАРОЛЬ"},
        {"tone": "calm", "text": "Защита паролей: коротко"}]}), encoding="utf-8")
    res = C.cover_dir(d)
    assert res["tones"] == {"A": "calm", "B": "loud", "C": "medium"}
    assert res["texts"]["B"] == "ПАРОЛЬ ЗА МИНУТУ" and res["texts"]["C"] == "КАК ЗАЩИТИТЬ ПАРОЛЬ"
    assert len({v["text"] for v in res["variants"]}) == 3
    assert {(v["variant"], v["tone"]) for v in res["variants"]} >= {("minimal", "calm"), ("hero", "loud")}
    assert not res["errors"], res["errors"]
    pr = (d / "cover" / "prompt.md").read_text(encoding="utf-8")
    for head in ("## A minimal (calm)", "## B hero (loud)", "## C split (medium)"):
        assert head in pr
    assert pr.count("```") == 6 and "КАК ЗАЩИТИТЬ ПАРОЛЬ" in pr and "Dramatic" in pr


def test_covers_without_metadata_derive_three_different_texts(tmp_path, monkeypatch):
    from test_cover import _fake_out
    monkeypatch.delenv("SHORTS_IMAGE_PROVIDER", raising=False)
    res = C.cover_dir(_fake_out(tmp_path))
    texts = res["texts"]
    assert texts["B"] == "ПАРОЛЬ ЗА МИНУТУ" and len(set(texts.values())) == 3
    assert all(3 <= len(t.split()) <= 5 for t in texts.values())
    assert not res["errors"], res["errors"]


def test_explicit_text_is_used_for_all_tones(tmp_path, monkeypatch):
    from test_cover import _fake_out
    monkeypatch.delenv("SHORTS_IMAGE_PROVIDER", raising=False)
    res = C.cover_dir(_fake_out(tmp_path), text="ТРИ СЛОВА ТУТ")
    assert set(res["texts"].values()) == {"ТРИ СЛОВА ТУТ"}


# ---------------------------------------------------------------- pack and deliver

def mk_video(p: Path, w=1080, h=1920, dur=2):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=25:duration={dur}",
                    "-f", "lavfi", "-i", f"sine=d={dur}", "-shortest", "-pix_fmt", "yuv420p", str(p)], check=True)


@pytest.fixture(scope="module")
def video(tmp_path_factory):
    p = tmp_path_factory.mktemp("v20") / "clip.mp4"
    mk_video(p)
    return p


def pack_item(video: Path, **over) -> dict:
    tones = ["loud", "loud", "medium", "medium", "calm"]
    it = {"slug": "clip", "name": "Тест", "video": str(video), "recommended": 2,
          "titles": [{"t": f"Название {i}", "why": "тест", "tone": tn} for i, tn in enumerate(tones, 1)],
          "descriptions": [desc("loud", "ГРОМКО про тест.\nВторая строка.\n\n#shorts #тест #ии"),
                           desc("medium", "Средне про тест.\nВторая строка.\n\n#shorts #тест #ии #ai"),
                           desc("calm", "Спокойно про тест.\nВторая строка.\n\n#shorts #тест #ии")],
          "pinned_comment": "Пин: что показать дальше?",
          "covers": [{"t0": 0.2, "t1": 1.8, "text": f"ТЕКСТ {n} ТУТ", "tone": tn} for n, tn in enumerate(TONES, 1)]}
    it.update(over)
    return it


def run_pack(tmp_path, video, **over):
    sp = tmp_path / "pack.json"
    sp.write_text(json.dumps({"items": [pack_item(video, **over)]}, ensure_ascii=False), encoding="utf-8")
    return P.pack(sp, tmp_path / "out"), tmp_path / "out" / "01-clip" / "НАЗВАНИЕ-И-ОПИСАНИЕ.txt"


def test_pack_with_three_descriptions_writes_labelled_variants(video, tmp_path):
    res, card = run_pack(tmp_path, video, tiktok_caption="Тест в ТикТок #тест #ии")
    txt = card.read_text(encoding="utf-8")
    assert "НАЗВАНИЯ (5)" in txt and "[громкое] Название 1" in txt and "[спокойное] Название 5" in txt
    assert txt.index("ОПИСАНИЕ 1: ГРОМКОЕ") < txt.index("ОПИСАНИЕ 2: СРЕДНЕЕ") < txt.index("ОПИСАНИЕ 3: СПОКОЙНОЕ")
    assert "Приём: trigger" in txt and "ГРОМКО про тест." in txt and "Спокойно про тест." in txt
    assert "рекомендую: громкое" in txt and "★ рекомендую" in txt   # title 2 is loud -> loud description
    assert "ЗАКРЕПЛЁННЫЙ КОММЕНТАРИЙ" in txt and "Пин: что показать дальше?" in txt
    assert "TIKTOK (подпись)" in txt and "Тест в ТикТок #тест #ии" in txt
    assert "(громкое)" in txt and "(спокойное)" in txt
    assert not res["warnings"], res["warnings"]
    assert (tmp_path / "out" / "01-clip" / "cover-3.png").exists()


def test_pack_recommended_description_and_derived_tiktok(video, tmp_path):
    _, card = run_pack(tmp_path, video, recommended_description="calm", recommended=3)
    txt = card.read_text(encoding="utf-8")
    assert "рекомендую: спокойное" in txt
    tk = txt.split("TIKTOK (подпись)\n")[1].splitlines()[0]
    assert tk.startswith("Название 3") and "#тест" in tk and "#shorts" not in tk


@pytest.mark.parametrize("ds,needle", [
    ([desc("loud"), desc("calm")], "exactly 3 descriptions"),
    ([desc("loud"), desc("medium"), desc("calm", "  ")], "calm description is empty"),
    ([desc("loud"), desc("loud"), desc("calm")], "one description per tone"),
    ([desc("loud"), desc("medium"), desc("calm", "x" * 4901)], "over 4900"),
])
def test_pack_blocks_bad_description_sets(video, tmp_path, ds, needle):
    with pytest.raises(ShortsError) as e:
        run_pack(tmp_path, video, descriptions=ds)
    assert needle in str(e.value)


def test_pack_ad_item_checks_every_variant(video, tmp_path):
    ad = {"name": "Q", "url": "https://t.me/q_bot?start=r_1"}
    ds = [desc("loud", "Реклама. https://t.me/q_bot?start=r_1"), desc("medium", "Без пометки https://t.me/q_bot?start=r_1"),
          desc("calm", "Реклама. но без ссылки")]
    with pytest.raises(ShortsError) as e:
        run_pack(tmp_path, video, ad=ad, descriptions=ds)
    msg = str(e.value)
    assert "medium description must contain the word" in msg and "calm description must contain the exact link" in msg
    assert "loud description" not in msg
    ok = [desc(t, "Реклама. https://t.me/q_bot?start=r_1") for t in TONES]
    run_pack(tmp_path, video, ad=ad, descriptions=ok)


def test_pack_old_format_with_single_description_still_works(video, tmp_path):
    res, card = run_pack(tmp_path, video, descriptions=None, description="Одно описание.\n\n#тест", covers=[{"t0": 0.2, "t1": 1.8, "text": "ТРИ СЛОВА ТУТ"}])
    txt = card.read_text(encoding="utf-8")
    assert "ОПИСАНИЕ - копируй целиком" in txt and "Одно описание." in txt and "ОПИСАНИЕ 1:" not in txt
    assert any("только одно" in w or "only one" in w for w in res["warnings"])


def test_pack_without_any_description_is_blocked(video, tmp_path):
    with pytest.raises(ShortsError) as e:
        run_pack(tmp_path, video, descriptions=None)
    assert "description is empty" in str(e.value)


def test_deliver_with_three_descriptions_and_covers(video, tmp_path):
    covers = []
    for tn in TONES:
        f = tmp_path / f"c-{tn}.jpg"
        f.write_bytes(b"\xff\xd8\xff\xd9")
        covers.append({"path": str(f), "tone": tn})
    item = {"video": str(video), "title": "Название 2", "pinned_comment": "Пин", "recommended": 2, "covers": covers,
            "titles": [{"t": f"Название {i}", "tone": tn} for i, tn in enumerate(["loud", "loud", "medium", "calm", "calm"], 1)],
            "descriptions": [desc(t, f"Текст {t}.\n\n#a #b #c") for t in TONES], "recommended_description": "medium"}
    sp = tmp_path / "d.json"
    sp.write_text(json.dumps({"items": [item]}, ensure_ascii=False), encoding="utf-8")
    rep = deliver(str(sp), str(tmp_path / "ГОТОВО"))
    assert rep["ok"], rep
    assert sorted(rep["files"]) == sorted(["01-Название 2.mp4", "01-Название 2-обложка-громкое.jpg",
                                           "01-Название 2-обложка-среднее.jpg", "01-Название 2-обложка-спокойное.jpg", "ОПИСАНИЯ.txt"])
    txt = (tmp_path / "ГОТОВО" / "ОПИСАНИЯ.txt").read_text(encoding="utf-8")
    assert "ВСЕ НАЗВАНИЯ (5)" in txt and "ОПИСАНИЕ 2: СРЕДНЕЕ  ★ рекомендую" in txt and "TIKTOK (подпись)" in txt
    assert "Текст loud." in txt and "Текст calm." in txt and "ЗАКРЕПЛЁННЫЙ КОММЕНТАРИЙ" in txt


def test_deliver_blocks_two_descriptions_and_undisclosed_ad_variant(video, tmp_path):
    base = {"video": str(video), "title": "Т", "ad": {"url": "https://e.invalid/a"}}
    sp = tmp_path / "d.json"
    sp.write_text(json.dumps({"items": [dict(base, descriptions=[desc("loud"), desc("calm")])]}, ensure_ascii=False), encoding="utf-8")
    assert "ровно 3 описания" in " ".join(deliver(str(sp), str(tmp_path / "o"))["errors"])
    ds = [desc("loud", "Реклама https://e.invalid/a"), desc("medium", "Реклама https://e.invalid/a"), desc("calm", "Просто текст")]
    sp.write_text(json.dumps({"items": [dict(base, descriptions=ds)]}, ensure_ascii=False), encoding="utf-8")
    errs = " ".join(deliver(str(sp), str(tmp_path / "o"))["errors"])
    assert "«calm»" in errs and "«loud»" not in errs


def test_deliver_old_item_with_one_description_warns_only(video, tmp_path):
    item = {"video": str(video), "title": "Т", "description": "Текст"}
    sp = tmp_path / "d.json"
    sp.write_text(json.dumps({"items": [item]}, ensure_ascii=False), encoding="utf-8")
    rep = deliver(str(sp), str(tmp_path / "o"))
    assert rep["ok"] and any("только одно" in w for w in rep["warnings"])
    assert "ОПИСАНИЕ:" in (tmp_path / "o" / "ОПИСАНИЯ.txt").read_text(encoding="utf-8")
