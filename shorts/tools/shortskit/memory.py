"""User memory: prefs.json (settings + pending reminders), history.json (videos made), experiments and metrics.

All files live in $SHORTS_MEMORY (default <skill>/memory). prefs.json and history.json are git-ignored.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .config import memory_dir
from .util import read_json, write_json

KEYS = ("language", "platforms", "source", "layout", "panels", "links", "qr", "brand", "voice", "music", "title_style")
DEFAULTS: dict[str, Any] = {
    "language": {"chat": "ru", "video": "ru"},
    "platforms": ["youtube_shorts"],
    "layout": "three",
    "brand": {"preset": "mono"},
    "voice": {"engine": "auto", "voice": None, "speed": 1.05},
    "music": {"source": "auto"},   # 2.4: no track named -> a fitting one from YouTube
    "qr": True,
}
REMIND = {
    "ru": {
        "language": "язык роликов", "platforms": "платформы", "source": "откуда сырьё", "layout": "раскладка",
        "panels": "что в верхней и нижней панели", "links": "ссылки и ники для рекламы", "qr": "нужен ли QR",
        "brand.profile": "кто вы и для кого канал", "brand.niche": "тема канала",
        "brand.goal": "цель канала", "brand.telegram": "Telegram-канал или сайт для баннера",
        "brand.offer": "чем занимаетесь и что рекламируем", "brand.style_choice": "предпочтения по стилю",
        "brand": "стиль бренда (пока mono)", "voice": "голос", "music": "музыка", "title_style": "стиль названий",
    },
    "en": {
        "language": "video language", "platforms": "platforms", "source": "raw material", "layout": "layout",
        "panels": "top and bottom panel content", "links": "links and handles", "qr": "QR or not",
        "brand.profile": "who you are and your audience", "brand.niche": "channel topic",
        "brand.goal": "channel goal", "brand.telegram": "Telegram channel or site for the banner",
        "brand.offer": "what you do and what the banner promotes", "brand.style_choice": "style preferences",
        "brand": "brand style (mono for now)", "voice": "voice", "music": "music", "title_style": "title style",
    },
}


def prefs_path() -> Path:
    return memory_dir() / "prefs.json"


def history_path() -> Path:
    return memory_dir() / "history.json"


def empty() -> dict:
    return {"version": 1, "pending": [], "rejected": [], "chosen_titles": [], "updated": None}


def load() -> dict:
    p = prefs_path()
    if not p.exists():
        return empty()
    data = read_json(p)
    base = empty()
    base.update(data)
    return base


def save(prefs: dict) -> dict:
    prefs["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    write_json(prefs_path(), prefs)
    return prefs


def parse_value(v: str) -> Any:
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        if "," in v and not v.startswith("http"):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


def set_value(key: str, value: Any) -> dict:
    p = load()
    cur = p
    parts = key.split(".")
    for k in parts[:-1]:
        if not isinstance(cur.get(k), dict):
            cur[k] = {}
        cur = cur[k]
    cur[parts[-1]] = value
    top = parts[0]
    for pending_key in (key, top):
        if pending_key in p["pending"]:
            p["pending"].remove(pending_key)
    return save(p)


def skip(key: str) -> dict:
    """User skipped a question: use the default now, remind at the end of every video until closed."""
    p = load()
    if key not in p["pending"]:
        p["pending"].append(key)
    if key in DEFAULTS and key not in p:
        p[key] = DEFAULTS[key]
    return save(p)


def close_pending(key: str) -> dict:
    p = load()
    if key in p["pending"]:
        p["pending"].remove(key)
    return save(p)


def reset() -> None:
    for f in (prefs_path(), history_path()):
        f.unlink(missing_ok=True)


def chat_lang(p: dict) -> str:
    lang = p.get("language")
    if isinstance(lang, dict):
        return (lang.get("chat") or "ru")[:2]
    return (lang or "ru")[:2]


def missing(p: dict) -> list[str]:
    return [k for k in KEYS if k not in p and k not in p["pending"] and k != "title_style"]


def reminder_line(p: dict) -> str:
    if not p["pending"]:
        return ""
    lang = chat_lang(p)
    names = [REMIND.get(lang, REMIND["en"]).get(k, k) for k in p["pending"]]
    if lang == "ru":
        return f"Не заполнено: {', '.join(names)}. Дать сейчас?"
    return f"Not set yet: {', '.join(names)}. Give it now?"


def summary_line(p: dict) -> str:
    ru = chat_lang(p) == "ru"
    brand = p.get("brand") if isinstance(p.get("brand"), dict) else {}
    profile = brand.get("profile")
    if isinstance(profile, dict):
        profile = ", ".join(str(profile[k]) for k in ("name", "topic", "audience") if profile.get(k))
    lang = p.get("language") or {}
    video_lang = lang.get("video", "ru") if isinstance(lang, dict) else lang
    langs = {"ru": "русский", "en": "английский"} if ru else {"ru": "Russian", "en": "English"}
    platforms = {"youtube_shorts": "YouTube Shorts", "tiktok": "TikTok", "reels": "Reels", "youtube": "YouTube"}
    parts = [str(profile)] if profile else []
    if brand.get("goal"):
        parts.append(("цель: " if ru else "goal: ") + str(brand["goal"]))
    if p.get("platforms"):
        parts.append(", ".join(platforms.get(k, k) for k in p["platforms"]))
    parts.append(("язык ролика: " if ru else "video language: ") + langs.get(video_lang, video_lang))
    body = "; ".join(parts)
    return (f"Беру настройки как в прошлый раз: {body}. Менять?" if ru
            else f"Using the same settings as last time: {body}. Change anything?")


# Brand intake uses dotted keys so an existing visual preset is not mistaken for a profile.
def _has(p: dict, key: str) -> bool:
    cur = p
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return cur is not None and cur != ""


QUESTIONS = {
    "ru": [
        (("brand.profile",), "Кто вы и что за канал или бренд: как вас зовут, о чём канал и для кого?"),
        (("brand.goal",), "Куда хотите прийти: больше подписчиков, продаж или просмотров?"),
        (("brand.telegram", "brand.offer"), "Для рекламных баннеров: есть ли Telegram-канал или сайт (ссылка или ник), чем занимаетесь и что именно рекламируем?"),
        (("source",), "Что делаем прямо сейчас: есть идея, ссылка, файл, тема или придумать самому?"),
        (("platforms", "language"), "Куда выкладываем и на каком языке делаем ролик? На каком языке вам удобнее общаться?"),
        (("links", "qr"), "Есть ссылки и ники для описания, закрепа и QR? Можно ответить: нет."),
        (("voice", "brand.style_choice"), "Какой голос и стиль вам нравятся? Можно ответить: выбери сам."),
    ],
    "en": [
        (("brand.profile",), "Who are you and what is your channel or brand: your name, topic and audience?"),
        (("brand.goal",), "What is your goal: more subscribers, sales or views?"),
        (("brand.telegram", "brand.offer"), "For ad banners: do you have a Telegram channel or site (link or handle), what do you do and what exactly do we promote?"),
        (("source",), "What are we making now: an idea, link, file, topic, or should a topic be suggested?"),
        (("platforms", "language"), "Where will you post and in what video language? Which language should we use to chat?"),
        (("links", "qr"), "Any links or handles for the description, pinned comment and QR? None is fine."),
        (("voice", "brand.style_choice"), "What voice and style do you like? You can say: you choose."),
    ],
}


def intake_message(p: dict, lang: str | None = None) -> str:
    lang = (lang or chat_lang(p))[:2]
    partial = {
        "ru": {"platforms": "Куда выкладываем?", "language": "На каком языке делаем ролик и общаемся?",
               "links": "Есть ссылки и ники для описания и закрепа? Можно ответить: нет.",
               "qr": "Показывать QR со ссылкой в ролике?", "voice": "Какой голос выбрать? Можно: выбери сам.",
               "brand.style_choice": "Какой стиль нравится? Можно: выбери сам.",
               "brand.telegram": "Есть Telegram-канал или сайт для баннера? Можно: нет.",
               "brand.offer": "Чем занимаетесь и что рекламируем на баннере?"},
        "en": {"platforms": "Where will you post?", "language": "Which video and chat language?",
               "links": "Any links or handles? None is fine.", "qr": "Show a QR link in the video?",
               "voice": "What voice? You can say: you choose.",
               "brand.style_choice": "What style? You can say: you choose.",
               "brand.telegram": "Any Telegram channel or site for the banner? None is fine.",
               "brand.offer": "What do you do and what does the banner promote?"},
    }
    need = []
    for keys, text in QUESTIONS.get(lang, QUESTIONS["en"]):
        absent = [k for k in keys if not _has(p, k) and k not in p.get("pending", [])]
        if absent:
            need.append(text if len(absent) == len(keys) else " ".join(partial.get(lang, partial["en"])[k] for k in absent))
    if not need:
        return summary_line(p) + ("\n" + reminder_line(p) if p["pending"] else "")
    head = ("Бренд. Ответьте одним сообщением, можно коротко или пропустить любой пункт:" if lang == "ru"
            else "Your brand. Reply in one message; brief answers are fine and any question can be skipped:")
    return "\n".join([head] + [f"{i}. {text}" for i, text in enumerate(need, 1)])


# ---------------------------------------------------------------- history and behaviour

def history() -> list[dict]:
    p = history_path()
    return read_json(p) if p.exists() else []


def record_video(name: str, first_hash: str, out_dir: Path) -> None:
    h = [x for x in history() if x.get("name") != name]
    title = ""
    meta = Path(out_dir) / "metadata.json"
    if meta.exists():
        title = read_json(meta).get("recommended_title", "")
    h.append({"name": name, "first_hash": first_hash, "title": title, "dir": str(out_dir),
              "date": dt.date.today().isoformat()})
    write_json(history_path(), h[-200:])


def remember_choice(kind: str, value: Any) -> dict:
    """kind: chosen_title | rejected (anything the user turned down: a style, a title, a voice)."""
    p = load()
    key = "chosen_titles" if kind == "chosen_title" else "rejected"
    p.setdefault(key, []).append({"value": value, "date": dt.date.today().isoformat()})
    p[key] = p[key][-50:]
    return save(p)


def niche_context(p: dict | None = None) -> dict:
    """Snapshot existing brand memory for scenario and packaging; never invent findings."""
    import copy
    p = load() if p is None else p
    b = p.get("brand") if isinstance(p.get("brand"), dict) else {}
    return copy.deepcopy({k: b[k] for k in ("niche", "niche_profile", "goal") if k in b})
