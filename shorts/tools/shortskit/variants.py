"""Three description variants (loud, medium, calm) for the hand-off: validation and text blocks, shared by pack and deliver.

Item fields: `descriptions` = [{"tone": "loud|medium|calm", "text": "...", "psychology": "optional note"}] x 3,
`recommended_description` = tone or 1..3 (default: the tone of the recommended title, else medium),
`tiktok_caption` (optional; derived from the recommended title and its hashtags when missing).
A pack/deliver item with only `description` still works: the variants are then optional and only a warning is given.
"""
from __future__ import annotations

import re

from .meta.tones import TONES, loudness_of, tone_name, tone_of

LABEL_RU = {"loud": "ГРОМКОЕ", "medium": "СРЕДНЕЕ", "calm": "СПОКОЙНОЕ"}
HASHTAG = re.compile(r"#[\w\u0400-\u04FF]+", re.U)
AD_WORD = re.compile(r"реклам|\bad\b|#ad\b|advertis|sponsor|спонсор|paid partnership", re.I)
MAX_DESC = 4900


def check_descriptions(it: dict, tag: str, ru: bool = True) -> tuple[list[dict] | None, list[str], list[str]]:
    """-> (normalized variants loud->calm or None when absent, errors, warnings)."""
    errs: list[str] = []
    warns: list[str] = []
    raw = it.get("descriptions")
    if raw is None:
        if (it.get("description") or "").strip():
            warns.append(f"{tag}: нет трёх вариантов описания (descriptions: громкое, среднее, спокойное), только одно" if ru
                         else f"{tag}: no 3 description variants (descriptions: loud, medium, calm), only one")
        return None, errs, warns
    if not isinstance(raw, list) or len(raw) != 3:
        n = len(raw) if isinstance(raw, list) else 0
        errs.append(f"{tag}: нужно ровно 3 описания (громкое, среднее, спокойное), сейчас {n}" if ru
                    else f"{tag}: need exactly 3 descriptions (loud, medium, calm), got {n}")
        return None, errs, warns
    out: list[dict] = []
    ad = it.get("ad")
    for i, d in enumerate(raw):
        d = d if isinstance(d, dict) else {"text": str(d)}
        tone = tone_name(d.get("tone")) or (TONES[i] if not d.get("tone") else "")
        text = (d.get("text") or "").strip()
        if not tone:
            errs.append(f"{tag}: описание {i + 1}: tone должен быть loud, medium или calm" if ru
                        else f"{tag}: description {i + 1}: tone must be loud, medium or calm")
            continue
        if not text:
            errs.append(f"{tag}: описание «{LABEL_RU[tone].lower()}» пустое" if ru else f"{tag}: {tone} description is empty")
            continue
        if len(text) > MAX_DESC:
            errs.append(f"{tag}: описание «{tone}» длиннее {MAX_DESC} знаков" if ru else f"{tag}: {tone} description over {MAX_DESC} chars")
        if ad:
            if not AD_WORD.search(text):
                errs.append(f"{tag}: описание «{tone}»: в ролике реклама, нужна пометка «Реклама»" if ru
                            else f"{tag}: ad item: {tone} description must contain the word «Реклама»")
            if ad.get("url") and ad["url"] not in text:
                errs.append(f"{tag}: описание «{tone}»: нет точной рекламной ссылки {ad['url']}" if ru
                            else f"{tag}: ad item: {tone} description must contain the exact link {ad['url']}")
        if not (d.get("psychology") or "").strip():
            warns.append(f"{tag}: у описания «{tone}» нет заметки о приёме (psychology)" if ru
                         else f"{tag}: {tone} description has no psychology note")
        out.append({"tone": tone, "text": text, "psychology": (d.get("psychology") or "").strip()})
    tones = [x["tone"] for x in out]
    if len(set(tones)) != len(tones) or (not errs and set(tones) != set(TONES)):
        errs.append(f"{tag}: нужны по одному описанию каждого тона: loud, medium, calm" if ru
                    else f"{tag}: need one description per tone: loud, medium, calm")
    out.sort(key=lambda x: TONES.index(x["tone"]))
    return (out if not errs else None), errs, warns


def recommended_tone(it: dict, variants: list[dict]) -> str:
    v = it.get("recommended_description")
    if isinstance(v, int) and 1 <= v <= 3:
        return TONES[v - 1]
    if tone_name(v) in {x["tone"] for x in variants}:
        return tone_name(v)
    titles = it.get("titles") or []
    rec = int(it.get("recommended", 1))
    if 1 <= rec <= len(titles):
        t = titles[rec - 1]
        tone = tone_name(t.get("tone")) or (tone_of(loudness_of(t["loudness"])) if t.get("loudness") else "")
        if tone in {x["tone"] for x in variants}:
            return tone
    return "medium"


def recommended_text(it: dict, variants: list[dict] | None) -> str:
    if variants:
        tone = recommended_tone(it, variants)
        return next(x["text"] for x in variants if x["tone"] == tone)
    return (it.get("description") or "").strip()


def tiktok_caption(it: dict, title: str, description: str) -> str:
    """Explicit `tiktok_caption`, else the title without hashtags + up to 5 hashtags (from the title, then the description)."""
    if (it.get("tiktok_caption") or "").strip():
        return it["tiktok_caption"].strip()
    text = HASHTAG.sub("", title).strip()
    tags: list[str] = []
    for t in HASHTAG.findall(title) + HASHTAG.findall(description):
        t = t.lower()
        if t != "#shorts" and t not in tags:
            tags.append(t)
    return f"{text} {' '.join(tags[:5])}".strip()


def variant_lines(variants: list[dict], rec: str) -> list[str]:
    """Text blocks, loud -> calm, the recommended one marked."""
    out: list[str] = []
    for n, x in enumerate(variants, 1):
        star = "  ★ рекомендую" if x["tone"] == rec else ""
        out += [f"ОПИСАНИЕ {n}: {LABEL_RU[x['tone']]}{star}"]
        if x.get("psychology"):
            out.append(f"Приём: {x['psychology']}")
        out += ["-" * 40, x["text"], "-" * 40, ""]
    return out
