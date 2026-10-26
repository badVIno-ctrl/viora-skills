from shortskit.engine import brand as B
from shortskit.engine import captions as C
from shortskit.engine import layout as L


def words(text: str, step: float = 0.3, pause_after: dict | None = None):
    out, t = [], 0.1
    for i, w in enumerate(text.split()):
        out.append({"w": w, "s": round(t, 3), "e": round(t + step * 0.85, 3)})
        t += step + (pause_after or {}).get(i, 0)
    return out


def build(text, lang="ru", platforms=("youtube_shorts",), **kw):
    br = B.resolve({"preset": "viora"}, None, lang)
    lay = L.compute({"mode": "three"}, list(platforms))
    return C.build(words(text, **kw), br, lay, {"max_words": 3}, lang), br, lay


def test_chunks_are_2_to_3_words_and_not_cut_after_preposition():
    chunks, _, _ = build("Описываешь деталь обычными словами, например шестерёнка с двенадцатью зубьями, и получаешь сорок моделей.")
    texts = [c.text for c in chunks]
    assert all(1 <= len(c.words) <= 3 for c in chunks)
    assert not any(t.split()[-1].lower() in ("с", "и", "в", "на") for t in texts[:-1]), texts
    assert "например шестерёнка с" not in [t.lower() for t in texts]
    assert sum(len(c.words) for c in chunks) / len(chunks) >= 2


def test_punctuation_ends_a_chunk():
    chunks, _, _ = build("Первый сайт. Второй сайт тоже бесплатный.")
    assert chunks[0].text.endswith(".")


def test_no_overflow_with_tiktok_column():
    chunks, _, lay = build("Невероятно длинноесловодлясубтитров и ещё немного текста здесь", platforms=("youtube_shorts", "tiktok"))
    for c in chunks:
        assert c.box[0] >= lay.safe.rect.x - 8 and c.box[2] <= lay.caption_band.x1 + 8 or c.overflow


def test_subs_replace_spoken_with_written():
    w = words("Первый лёрн энисинг и кэд лукап")
    out = C.apply_subs(w, {"лёрн энисинг": "learn-anything", "кэд лукап": "CAD Lookup"})
    assert [x["w"] for x in out] == ["Первый", "learn-anything", "и", "CAD Lookup"]
    assert out[1]["s"] == w[1]["s"] and out[1]["e"] == w[2]["e"]
    dropped = C.apply_subs(words("лёрн энисинг тут"), {"лёрн": "learn-anything", "энисинг": ""})
    assert [x["w"] for x in dropped] == ["learn-anything", "тут"]


def test_ass_highlights_current_word_flat_no_blur():
    chunks, br, _ = build("Два бесплатных сайта")
    ass = C.to_ass(chunks, br, {"highlight": "accent"}, 3.0)
    assert "\\1c" in ass
    assert "\\blur" not in ass and "\\be" not in ass
    style = [ln for ln in ass.splitlines() if ln.startswith("Style:")][0].split(",")
    assert style[17].strip() == "0"  # shadow 0, outline instead
    assert int(style[16]) >= 4
    n_words = sum(len(c.words) for c in chunks)
    assert ass.count("Dialogue:") == n_words


def test_caption_size_and_contrast():
    chunks, br, _ = build("Тест размера")
    assert all(c.size >= 64 for c in chunks)
    from shortskit.util import contrast

    assert contrast(br.caption_accent, br.caption_outline) >= 7
    assert contrast(br.caption_fill, br.caption_outline) >= 7


def test_srt():
    srt = C.to_srt(words("Раз два три. Четыре пять."))
    assert srt.startswith("1\n00:00:00,100 --> ")
    assert "\n\n2\n" in srt


def test_english_chunks():
    chunks, _, _ = build("Two free sites and you will use both of them today.", lang="en")
    assert not any(c.text.split()[-1].lower() in ("and", "of", "the") for c in chunks[:-1])


# ---------------------------------------------------------------- 1.1.0 item 6: fewer one-word chunks, safe breaks

def _w(text: str, step: float = 0.3, pauses: dict | None = None) -> list[dict]:
    out, t = [], 0.0
    for i, w in enumerate(text.split()):
        t += (pauses or {}).get(i, 0.0)
        out.append({"w": w, "s": round(t, 3), "e": round(t + step - 0.04, 3)})
        t += step
    return out


def _chunks(text, lang="ru", **kw):
    from shortskit.engine import captions as CP

    words = _w(text, **kw)
    return CP.chunk_words(words, lang, 3, lambda ch: 1 if len(" ".join(w["w"] for w in ch)) <= 24 else (2 if len(ch) > 1 else 0))


def _texts(chs):
    return [" ".join(w["w"] for w in c) for c in chs]


def test_comma_list_is_not_one_word_each():
    # BAD case from 1.0.0: "книги, | курсы, | ссылки." and "сайта, | и оба" gave 36% one-word chunks
    t = _texts(_chunks("Два бесплатных сайта, и оба пригодятся. Книги, курсы, ссылки и видео."))
    ones = [x for x in t if len(x.split()) == 1]
    assert len(ones) / len(t) <= 0.2, t


def test_preposition_and_conjunction_stay_with_next_word():
    for text in ("Ссылка на остальные находки в закрепе и в канале", "Open the file in the editor and save it"):
        t = _texts(_chunks(text, lang="ru" if text[0] == "С" else "en"))
        fw = {"на", "в", "и", "the", "in", "and"}
        assert not any(x.split()[-1].lower() in fw for x in t[:-1]), t


def test_name_and_surname_not_split():
    t = _texts(_chunks("Сегодня смотрим, как Илон Маск запускает ракету"))
    assert any("Илон Маск" in x for x in t), t


def test_number_stays_with_its_noun():
    t = _texts(_chunks("За один вечер я собрал 5 сайтов и 3 игры"))
    assert any("5 сайтов" in x for x in t) and any("3 игры" in x for x in t), t


def test_chunk_report_flags_bad_breaks():
    from shortskit.engine import captions as CP

    bad = [CP.Chunk(_w("Ссылка на")), CP.Chunk(_w("закрепе")), CP.Chunk(_w("Илон")), CP.Chunk(_w("Маск 5")),
           CP.Chunk(_w("сайтов"))]
    rep = CP.chunk_report(bad, "ru")
    assert rep["one_word"] == 3 and len(rep["issues"]) == 3, rep


def test_demo_words_one_word_share_under_20pct():
    """Re-chunk the words of the committed demos with the current rules (tools/caption_stats.py)."""
    import glob
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "tools"))
    import caption_stats as CS

    tot = one = 0
    for p in glob.glob(str(root / "demos" / "*" / "manifest.json")):
        chunks, lang = CS.rechunk(Path(p))
        if chunks:
            from shortskit.engine import captions as CP

            r = CP.chunk_report(chunks, lang)
            tot, one = tot + r["chunks"], one + r["one_word"]
            assert not r["issues"], (p, r["issues"])
    assert tot >= 30 and one / tot <= 0.20, (one, tot)
