"""One clean folder for a person: videos with human names + one text file with titles and descriptions.

`python tools/shorts.py deliver deliver.json --out ГОТОВО [--zip] [--with-service]`

deliver.json (written by the agent, UTF-8):
{
  "set_title": "4 шортса с рекламой",
  "items": [
    {"video": "out/s1/final.mp4",            # required
     "title": "Название ролика",             # required (or "from": "out/s1" to take the recommended meta)
     "description": "Текст для описания",     # required, copy-paste ready
     "pinned_comment": "...", "hashtags": ["#a", "#b"],
     "cover": "out/s1/cover/cover-A.png",     # optional
     "titles": [{"t": "ЗАГОЛОВОК 😱 #shorts", "tone": "loud"}, ...],   # optional: 5-7 variants, loud -> calm
     "recommended": 2, "tiktok_caption": "...",                     # optional (caption is derived when missing)
     "descriptions": [{"tone": "loud", "psychology": "FOMO", "text": "..."}, {"tone": "medium", ...}, {"tone": "calm", ...}],
                                              # optional, exactly 3 non-empty; then `description` is the recommended one
     "recommended_description": "loud|medium|calm",
     "covers": [{"path": "out/s1/cover/cover-B-hero-9x16.jpg", "tone": "loud"}, ... 3],   # optional, one per tone
     "ad": {"name": "Quattro VPN", "url": "https://..."},   # optional: paid/partner promo inside the video
     "sources": ["https://..."],              # optional: where the material comes from
     "to_check": ["Прослушать речь на стыках"],  # optional: honest unchecked items, plain words
     "service": ["out/s1/captions.srt", "out/s1/timeline.json"]}   # optional: go to _служебное, never to the top level
  ]
}
Rules: the top level of the result holds only NN-<title>.mp4, NN-<title>-обложка[-тон].<ext> and ОПИСАНИЯ.txt.
Subtitles, timelines, JSON reports and logs go to `_служебное/` which is NOT put in the zip unless --with-service.
Exit 1 with a list when a video has no title/description, is not 9:16 1080x1920, has no audio, or an ad item lacks
the disclosure word and the exact link in its description.
2.2: also when the render next to the video (manifest.json) used the generated placeholder music (bed.mp3 / edit.mp3)
or synthesized sound effects from a pre-2.2 render ("placeholder_audio_ok": true in the item = a conscious draft).
"""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

from . import variants as V
from .meta.tones import TONES, tone_name
from .util import ShortsError, ffprobe, read_json

SERVICE = "_служебное"
BAD = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def slug(title: str, n: int = 60) -> str:
    s = BAD.sub(" ", re.sub(r"#\S+", "", title)).strip(" .")
    s = re.sub(r"\s+", " ", s)[:n].strip(" .")
    return s or "ролик"


def _probe(path: Path) -> dict:
    info = ffprobe(path)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float((info.get("format") or {}).get("duration") or 0)
    return {"w": int(v["width"]) if v else 0, "h": int(v["height"]) if v else 0, "audio": a is not None, "dur": dur}


def _from_meta(d: Path) -> dict:
    meta = read_json(d / "metadata.json")
    desc = meta.get("description", "")
    pinned = meta.get("pinned_comment") or ""
    if isinstance(pinned, list):
        pinned = "\n".join(pinned)
    t = meta.get("recommended_title") or (meta.get("titles") or [{}])[0].get("title", "")
    out = {"title": t, "description": desc, "pinned_comment": pinned}
    if meta.get("descriptions"):
        out["descriptions"] = [{"tone": x["tone"], "psychology": x.get("psychology", ""), "text": x["text"]} for x in meta["descriptions"]]
        out["recommended_description"] = meta.get("recommended_description", "")
    if meta.get("titles"):
        out["titles"] = [{"t": x["title"], "tone": x.get("tone", ""), "why": x.get("why", "")} for x in meta["titles"]]
        out["recommended"] = int(meta.get("recommended") or 1)
    if meta.get("tiktok_caption"):
        out["tiktok_caption"] = meta["tiktok_caption"]
    tone_covers = []
    for letter, tone in (("B", "loud"), ("C", "medium"), ("A", "calm")):
        jpg = sorted((d / "cover").glob(f"cover-{letter}-*-16x9.jpg"))
        if jpg:
            tone_covers.append({"path": str(jpg[0]), "tone": tone})
    if len(tone_covers) == 3:
        out["covers"] = tone_covers
    vids = sorted(d.glob("*.mp4"))
    if vids:
        out["video"] = str(vids[0])
    covers = sorted((d / "cover").glob("cover-A*16x9.png")) + sorted((d / "cover").glob("cover-A*9x16*")) + sorted((d / "cover").glob("cover-A*"))
    if covers:
        out["cover"] = str(covers[0])
    srt = sorted(d.glob("*.srt"))
    out["service"] = [str(p) for p in srt + [d / "qa.md", d / "manifest.json"] if p.exists()]
    return out


def validate(item: dict, i: int, p: dict | None) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    tag = f"ролик {i}"
    if not (item.get("title") or "").strip():
        errs.append(f"{tag}: нет названия")
    elif len(item["title"]) > 100:
        errs.append(f"{tag}: название длиннее 100 знаков ({len(item['title'])})")
    variants, e, w = V.check_descriptions(item, tag)
    errs += e
    warns += w
    if not (item.get("description") or "").strip() and variants is None:
        errs.append(f"{tag}: нет описания (человек не должен писать его сам)")
    titles = item.get("titles") or []
    if titles and not 5 <= len(titles) <= 7:
        warns.append(f"{tag}: вариантов названия {len(titles)}, лучше 5-7")
    if p is None:
        errs.append(f"{tag}: видеофайл не найден")
        return errs, warns
    if (p["w"], p["h"]) != (1080, 1920):
        errs.append(f"{tag}: размер {p['w']}x{p['h']}, нужен 1080x1920")
    if not p["audio"]:
        errs.append(f"{tag}: нет звуковой дорожки")
    if p["dur"] > 180:
        errs.append(f"{tag}: длительность {p['dur']:.0f} с, для Shorts максимум 180 с")
    elif p["dur"] > 59:
        warns.append(f"{tag}: {p['dur']:.0f} с - дольше минуты, проверь правила площадки")
    ad = item.get("ad")
    if ad and (item.get("description") or "").strip():
        text = (item.get("description") or "") + "\n" + (item.get("pinned_comment") or "")
        if not re.search(r"реклам", text, re.I):
            errs.append(f"{tag}: в ролике реклама, а в описании нет пометки «Реклама»")
        if ad.get("url") and ad["url"] not in text:
            errs.append(f"{tag}: в описании нет точной рекламной ссылки")
    man = item.get("_manifest")
    if man is not None and not item.get("placeholder_audio_ok"):
        from .qa.gate import audio_flags

        f = audio_flags(man[0], man[1])
        if f["synth_sfx"] and f["mode"] == "legacy":
            errs.append(f"{tag}: в звуке синтезированные эффекты ({', '.join(f['synth_sfx'])}) - "
                        f"перерендерить в 2.2 (только реальные записи)")
        if f["music_synthetic"]:
            errs.append(f"{tag}: музыка - встроенная сгенерированная заглушка (bed.mp3 / edit.mp3); "
                        f"нужен реальный трек или выгрузка без музыки")
    tags = item.get("hashtags") or []
    if len(tags) > 15:
        warns.append(f"{tag}: хэштегов больше 15 - YouTube игнорирует все хэштеги")
    return errs, warns


def _text(set_title: str, rows: list[dict]) -> str:
    L = [f"{set_title}", "=" * len(set_title), ""]
    L.append("Что в папке: готовые MP4 (по порядку номеров) и этот файл. Всё служебное убрано.")
    L.append("Для каждого ролика ниже: название, описание, закреплённый комментарий - копируй как есть.")
    L.append("")
    for r in rows:
        it = r["item"]
        L += ["-" * 60, f"{r['n']:02d}. {it['title']}", f"Файл: {r['video']}  ({r['p']['dur']:.0f} с, {r['p']['w']}x{r['p']['h']})"]
        if r.get("cover"):
            L.append(f"Обложка: {r['cover']}")
        L += ["", "НАЗВАНИЕ:", it["title"], ""]
        if it.get("titles"):
            rec = int(it.get("recommended") or 1)
            L += [f"ВСЕ НАЗВАНИЯ ({len(it['titles'])}): от громкого к спокойному"]
            for i, t in enumerate(it["titles"], 1):
                t = t if isinstance(t, dict) else {"t": str(t)}
                tn = tone_name(t.get("tone"))
                L.append(f"{i}. {'[' + V.LABEL_RU[tn].lower() + '] ' if tn else ''}{t.get('t', '')}{'  ★ рекомендую' if i == rec else ''}")
            L.append("")
        if r.get("variants"):
            L += [f"ОПИСАНИЯ: три варианта, от громкого к спокойному (рекомендую: {V.LABEL_RU[r['rec_tone']].lower()}). Копируй один целиком", ""]
            L += V.variant_lines(r["variants"], r["rec_tone"])
        else:
            L += ["ОПИСАНИЕ:", it["description"].strip(), ""]
        if it.get("tiktok_caption") or r.get("variants"):
            L += ["TIKTOK (подпись):", V.tiktok_caption(it, it["title"], V.recommended_text(it, r.get("variants"))), ""]
        if r.get("covers"):
            L += ["ОБЛОЖКИ: " + ", ".join(f"{n} ({V.LABEL_RU[t].lower()})" for n, t in r["covers"]), ""]
        if it.get("pinned_comment"):
            L += ["ЗАКРЕПЛЁННЫЙ КОММЕНТАРИЙ:", it["pinned_comment"].strip(), ""]
        if it.get("hashtags"):
            L += ["ХЭШТЕГИ:", " ".join(it["hashtags"]), ""]
        if it.get("ad"):
            L += [f"РЕКЛАМА В РОЛИКЕ: {it['ad'].get('name', '')} {it['ad'].get('url', '')}".strip(),
                  "Ссылка в самом MP4 (QR/плашка) не кликабельна: поставь её в описание/комментарий.", ""]
        if it.get("sources"):
            L += ["ИСТОЧНИКИ МАТЕРИАЛА:"] + [f"- {s}" for s in it["sources"]] + [""]
        if it.get("to_check"):
            L += ["ПЕРЕД ПУБЛИКАЦИЕЙ ПРОВЕРЬ:"] + [f"- {s}" for s in it["to_check"]] + [""]
    L += ["-" * 60, "Права на чужие видео, музыку и логотипы, правила площадки и рекламная маркировка - на стороне публикующего.",
          "Ничего не опубликовано."]
    return "\n".join(L) + "\n"


def deliver(spec_path: str, out: str = "ГОТОВО", zip_it: bool = False, with_service: bool = False) -> dict:
    sp = Path(spec_path)
    spec = read_json(sp)
    base = sp.parent
    items = spec.get("items") or []
    if not items:
        raise ShortsError("deliver.json: no items")

    def res(p):
        q = Path(p)
        return q if q.is_absolute() else (base / q if (base / q).exists() else Path.cwd() / q)

    errs, warns, rows = [], [], []
    for i, it in enumerate(items, 1):
        it = dict(it)
        if it.get("from"):
            auto = _from_meta(res(it["from"]))
            for k, v in auto.items():
                if not it.get(k):
                    it[k] = v
            it["service"] = list(dict.fromkeys((it.get("service") or []) + auto.get("service", [])))
        vp = res(it["video"]) if it.get("video") else None
        pr = _probe(vp) if vp and vp.exists() else None
        if vp is not None and (vp.parent / "manifest.json").exists():
            try:
                it["_manifest"] = (read_json(vp.parent / "manifest.json"), vp.parent)
            except Exception:
                it.pop("_manifest", None)
        e, w = validate(it, i, pr)
        errs += e
        warns += w
        if vp is not None:   # 2.4: auto-found music -> credit line in the description(s)
            from . import music as MU
            it = MU.with_credit(it, vp)
            if it.get("music_credit"):
                warns.append(f"{i:02d}: {MU.LICENCE_NOTE}: {it['music_credit']}")
        variants, _, _ = V.check_descriptions(it, "")
        if variants and not (it.get("description") or "").strip():
            it["description"] = V.recommended_text(it, variants)
        rows.append({"n": i, "item": it, "vp": vp, "p": pr, "variants": variants,
                     "rec_tone": V.recommended_tone(it, variants) if variants else ""})
    if errs:
        return {"ok": False, "errors": errs, "warnings": warns}

    outd = Path(out)
    if outd.exists():
        shutil.rmtree(outd)
    (outd / SERVICE).mkdir(parents=True)
    for r in rows:
        it = r["item"]
        name = f"{r['n']:02d}-{slug(it['title'])}"
        r["video"] = name + ".mp4"
        shutil.copy2(r["vp"], outd / r["video"])
        if it.get("cover") and res(it["cover"]).exists():
            c = res(it["cover"])
            r["cover"] = f"{name}-обложка{c.suffix.lower()}"
            shutil.copy2(c, outd / r["cover"])
        r["covers"] = []
        for c in it.get("covers") or []:
            cp = res(c["path"] if isinstance(c, dict) else c)
            tn = tone_name(c.get("tone")) if isinstance(c, dict) else ""
            if cp.exists():
                label = f"-{V.LABEL_RU[tn].lower()}" if tn else f"-{len(r['covers']) + 1}"
                cn = f"{name}-обложка{label}{cp.suffix.lower()}"
                shutil.copy2(cp, outd / cn)
                r["covers"].append((cn, tn or "medium"))
        for s in it.get("service") or []:
            sp2 = res(s)
            if sp2.exists():
                shutil.copy2(sp2, outd / SERVICE / f"{r['n']:02d}-{sp2.name}")
    (outd / "ОПИСАНИЯ.txt").write_text(_text(spec.get("set_title") or "Готовые ролики", rows), encoding="utf-8")
    top = sorted(p.name for p in outd.iterdir() if p.is_file())
    res_obj = {"ok": True, "folder": str(outd), "files": top, "service_files": sorted(p.name for p in (outd / SERVICE).iterdir()),
               "warnings": warns}
    if zip_it:
        zp = outd.with_suffix(".zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
            for p in sorted(outd.rglob("*")):
                if p.is_file() and (with_service or SERVICE not in p.relative_to(outd).parts):
                    z.write(p, Path(outd.name) / p.relative_to(outd))
        res_obj["zip"] = str(zp)
    if not any((outd / SERVICE).iterdir()):
        (outd / SERVICE).rmdir()
    return res_obj
