"""Three tones for titles, descriptions and covers: loud (pressure on psychology) -> medium -> calm (informative).

Loudness scale used by titles: 1-2 loud, 3 medium, 4-5 calm. Words are accepted too: "loud", "medium", "calm".
"""
from __future__ import annotations

import re

TONES = ("loud", "medium", "calm")
_WORD_LOUDNESS = {"loud": 1, "medium": 3, "calm": 5}
# prefixes for rule-based cover texts: they only restate the topic, nothing is invented
_PREFIX = {
    "ru": {"loud": "СМОТРИ:", "medium": "РАЗБОР:", "calm": "КОРОТКО:"},
    "en": {"loud": "WATCH:", "medium": "BREAKDOWN:", "calm": "QUICK GUIDE:"},
}


def tone_of(loudness: int) -> str:
    return "loud" if loudness <= 2 else ("medium" if loudness == 3 else "calm")


def loudness_of(value, default: int = 3) -> int:
    """Accepts 1-5 or loud/medium/calm; anything else falls back to `default`."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _WORD_LOUDNESS:
            return _WORD_LOUDNESS[v]
        if v.isdigit():
            value = int(v)
    try:
        return min(5, max(1, int(value)))
    except (TypeError, ValueError):
        return default


def tone_name(value) -> str:
    v = str(value or "").strip().lower()
    return v if v in TONES else ""


def _clip(words: list[str], hi: int = 5) -> list[str]:
    return words[:hi]


def derive_cover_texts(hook: str, topic: str, lang: str, upper: bool = True) -> list[dict]:
    """Rule-based 3-5 word cover texts per tone. Loud is always caps; calm follows the brand register."""
    clean = lambda s: re.sub(r"[#\U0001F000-\U0001FAFF\u2600-\u27BF]", "", s or "").split()
    hook_w, topic_w = clean(hook), clean(topic)
    base = hook_w or topic_w or ["VIDEO"]
    loud = _clip(base, 5)
    if len(loud) < 3:
        loud = _clip(loud + [w for w in topic_w if w not in loud], 5)
    pre = _PREFIX.get(lang, _PREFIX["en"])
    if len(loud) < 3:
        loud = _clip([pre["loud"]] + loud, 5)
    core = topic_w or base
    medium = _clip([pre["medium"]] + core[:3], 5)
    calm = _clip(pre["calm"].split() + core[:3], 5)
    out = []
    for tone, ws in (("loud", loud), ("medium", medium), ("calm", calm)):
        text = " ".join(ws)
        if tone == "loud" or upper:
            text = text.upper()
        else:
            text = text[:1].upper() + text[1:].lower() if tone == "calm" else text
        out.append({"tone": tone, "text": text})
    return out


def normalize_cover_texts(raw) -> list[dict]:
    """Draft `cover_texts`: a list of 3 strings (loud -> calm) or of {tone, text}, or {tone: text}. Bad input -> []."""
    items: list[dict] = []
    if isinstance(raw, dict):
        items = [{"tone": k, "text": v} for k, v in raw.items()]
    elif isinstance(raw, list):
        for i, x in enumerate(raw):
            if isinstance(x, str):
                items.append({"tone": TONES[i] if i < 3 else "", "text": x})
            elif isinstance(x, dict):
                items.append({"tone": x.get("tone") or (TONES[i] if i < 3 else ""), "text": x.get("text", "")})
    out = []
    for x in items:
        t = tone_name(x["tone"])
        if t and isinstance(x["text"], str) and x["text"].strip():
            out.append({"tone": t, "text": " ".join(x["text"].split())})
    out.sort(key=lambda x: TONES.index(x["tone"]))
    return out
