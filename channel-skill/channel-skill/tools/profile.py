#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Профиль канала: единственный источник правды о бренде.

Скилл собран так, чтобы его мог взять любой автор. Всё, что относится к
конкретному каналу (имя бренда, автор, ссылки, футер, рубрики, окно
публикации, цифры), живёт в profile/profile.json и больше нигде.
Скрипты и тексты скилла спрашивают значения только через этот модуль.

Запуск:
    python3 tools/profile.py --show      карточка профиля словами
    python3 tools/profile.py --check     проверить профиль, код 1 если сломан
    python3 tools/profile.py --json      профиль машинно
    python3 tools/profile.py --footer    готовая строка футера
    python3 tools/profile.py --selftest  самопроверка модуля

Порядок поиска профиля:
1. CHANNEL_PROFILE, если переменная задана. Тогда только она.
2. profile/profile.json рядом со скиллом. Личный файл, в гит не едет.
3. profile.json в корне рабочей папки.
4. profile/profile.example.json из поставки. Это демо, а не твой канал.

Сторонних библиотек не нужно, только Python 3.
"""

import argparse
import copy
import json
import os
import re
import sys

VERSION = "6.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ROOT = os.path.dirname(SKILL)

PROFILE_DIR = os.path.join(SKILL, "profile")
PERSONAL = os.path.join(PROFILE_DIR, "profile.json")
EXAMPLE = os.path.join(PROFILE_DIR, "profile.example.json")

# Канонная таблица рубрик. Профиль может переписать любую строку и добавить свои.
# Поля: коридор знаков, коридор пунктов, требование пересылки, каркас,
# запасной каркас, один файл на чтение, мягкий первый экран.
RUBRIC_DEFAULTS = {
    "абуз": {"min": 700, "max": 1400, "points": [4, 7], "forward": "required",
             "frame": "SLAY", "frame_alt": "PAS", "file": "reference/formats.md"},
    "сервисы": {"min": 500, "max": 900, "points": [3, 5], "forward": "required",
                "frame": "SLAY", "frame_alt": "BAB", "file": "reference/formats.md"},
    "гайд": {"min": 900, "max": 1800, "points": None, "forward": "wanted",
             "frame": "PAS", "frame_alt": "AIDA", "file": "reference/formats.md"},
    "релиз": {"min": 400, "max": 700, "points": [1, 3], "forward": "none",
              "frame": "BAB", "frame_alt": "STAR", "file": "reference/github.md"},
    "девлог": {"min": 500, "max": 900, "points": [1, 3], "forward": "none",
               "frame": "STAR", "frame_alt": "BAB", "file": "reference/examples.md",
               "soft_first_screen": True},
    "личное": {"min": 400, "max": 900, "points": None, "forward": "none",
               "frame": "STAR", "frame_alt": "PAS", "file": "reference/voice.md",
               "soft_first_screen": True},
    "опрос": {"min": 200, "max": 450, "points": [2, 4], "forward": "wanted",
              "frame": "PAS", "frame_alt": "AIDA", "file": "reference/formats.md"},
    "шортс": {"min": 250, "max": 500, "points": [1, 1], "forward": "wanted",
              "frame": "AIDA", "frame_alt": "BAB", "file": "reference/shorts.md"},
    "лидмагнит": {"min": 400, "max": 700, "points": [1, 1], "forward": "wanted",
                  "frame": "BAB", "frame_alt": "AIDA", "file": "reference/telegraph.md"},
    "второй": {"min": 250, "max": 500, "points": [1, 2], "forward": "wanted",
               "frame": "STAR", "frame_alt": "PAS", "file": "reference/second-brand.md"},
    "мем": {"min": 40, "max": 220, "points": None, "forward": "none"},
    "реклама": {"forward": "none"},
}

RUBRIC_ORDER = [
    "абуз", "сервисы", "гайд", "релиз", "девлог", "личное",
    "опрос", "шортс", "лидмагнит", "второй", "мем", "реклама",
]

DEFAULTS = {
    "schema": 1,
    "brand": {
        "name": "DEMO STUDIO",
        "short": "DEMO",
        "author": "demo_author",
        "language": "ru",
        "tone": "нашёл, проверил, принёс",
        "topics": [],
        "audience": "",
        "taboo": [],
        "about": "",
    },
    "channel": {
        "platform": "telegram",
        "handle": "@demo_channel",
        "url": "",
        "window": "16:30-21:00",
        "tz": "Europe/Moscow",
    },
    "links": [],
    "sources": [],
    "footer": {"enabled": True, "template": "", "legacy_labels": []},
    "article": {"enabled": True, "platform": "telegra.ph", "signature": ""},
    "second_brand": {"enabled": False, "name": "", "tag": "второй",
                     "min": 250, "max": 500, "footer": False},
    "rubrics": {},
    "voice": {"greeting_max_words": 5, "extra_banned": [], "extra_lexicon": []},
    "metrics": {"subscribers": 0, "reach": [0, 0], "reactions": [0, 0]},
    "telegram": {"prefixes": [], "mode": "draft", "inbox": "me"},
}

LABEL_RE = re.compile(r"^[A-ZА-ЯЁ0-9.\- ]{2,12}$")
HANDLE_RE = re.compile(r"^@[A-Za-z0-9_]{4,32}$")


def _read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _merge(base, extra):
    """Глубокое слияние: профиль дописывает поверх значений по умолчанию."""
    out = copy.deepcopy(base)
    for key, value in (extra or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def find_path(root=None):
    """Где лежит профиль. Возвращает путь и словами источник."""
    skill = os.path.abspath(root or SKILL)
    env = os.environ.get("CHANNEL_PROFILE")
    if env:
        return os.path.abspath(env), "CHANNEL_PROFILE"
    personal = os.path.join(skill, "profile", "profile.json")
    if os.path.exists(personal):
        return personal, "profile/profile.json"
    outer = os.path.join(os.path.dirname(skill), "profile.json")
    if os.path.exists(outer):
        return outer, "profile.json в корне"
    return os.path.join(skill, "profile", "profile.example.json"), "демо из поставки"


def load(root=None, path=None):
    """Профиль со значениями по умолчанию. Никогда не падает без файла."""
    if path:
        where, source = os.path.abspath(path), "аргумент"
    else:
        where, source = find_path(root)
    raw, problem = {}, ""
    if os.path.exists(where):
        try:
            raw = _read_json(where)
        except (ValueError, OSError) as err:
            problem = "профиль не читается: %s" % err
            raw = {}
    else:
        problem = "файла профиля нет"
    prof = _merge(DEFAULTS, raw)
    prof["_meta"] = {
        "path": where,
        "source": source,
        "demo": source == "демо из поставки",
        "problem": problem,
        "filled": bool(raw),
    }
    return prof


def is_demo(prof=None):
    prof = prof or load()
    return bool(prof.get("_meta", {}).get("demo"))


# --- бренд и ссылки ---


def brand(prof=None):
    prof = prof or load()
    return (prof["brand"].get("name") or "").strip()


def author(prof=None):
    prof = prof or load()
    return (prof["brand"].get("author") or "").strip()


def language(prof=None):
    prof = prof or load()
    return (prof["brand"].get("language") or "ru").strip()


def channel(prof=None):
    """Куда публикуем: @handle для Телеграма."""
    prof = prof or load()
    return (prof["channel"].get("handle") or "").strip()


def channel_url(prof=None):
    prof = prof or load()
    url = (prof["channel"].get("url") or "").strip()
    if url:
        return url
    handle = channel(prof)
    if handle.startswith("@"):
        return "https://t.me/%s" % handle[1:]
    return ""


def links(prof=None):
    """Ссылки футера в виде списка пар: ярлык и адрес."""
    prof = prof or load()
    out = []
    for item in prof.get("links") or []:
        label = str(item.get("label", "")).strip()
        url = str(item.get("url", "")).strip()
        if label and url:
            out.append((label, url))
    return out


def footer_enabled(prof=None):
    prof = prof or load()
    return bool(prof["footer"].get("enabled", True))


def footer(prof=None):
    """Строка футера знак в знак. Пустая строка значит футера у бренда нет."""
    prof = prof or load()
    if not footer_enabled(prof):
        return ""
    template = (prof["footer"].get("template") or "").strip()
    if template:
        return template
    pairs = links(prof)
    if not pairs:
        return ""
    return " | ".join("[%s](%s)" % (label, url) for label, url in pairs)


def footer_marks(prof=None):
    """Ярлыки, по которым строка узнаётся как футер даже после правок."""
    prof = prof or load()
    text = footer(prof)
    found = re.findall(r"\[([^\]]{1,20})\]\(", text)
    return tuple(found[:4]) if found else tuple()


def footer_labels(prof=None):
    """Ярлыки в форме «[ЧАТ](», как их ищет валидатор."""
    prof = prof or load()
    out = ["[%s](" % mark for mark in footer_marks(prof)]
    out.extend(legacy_labels(prof))
    return tuple(out)


def footer_plain_re(prof=None):
    """Футер без ссылок: два первых ярлыка через палку."""
    prof = prof or load()
    marks = footer_marks(prof)
    if len(marks) < 2:
        return re.compile(r"(?!x)x")
    return re.compile(r"%s\s*\|\s*%s" % (re.escape(marks[0]), re.escape(marks[1])))


def legacy_labels(prof=None):
    """Устаревшие ярлыки футера: были в старых постах, сейчас ошибка."""
    prof = prof or load()
    out = []
    for item in prof["footer"].get("legacy_labels") or []:
        item = str(item).strip()
        if not item:
            continue
        out.append(item if item.endswith("(") else "[%s](" % item.strip("[]("))
    return tuple(out)


def legacy_label_re(prof=None):
    """Регулярка на устаревшие ярлыки или None, если их нет."""
    prof = prof or load()
    marks = [re.escape(item) for item in legacy_labels(prof)]
    if not marks:
        return None
    return re.compile("|".join(marks))


def article_author(prof=None):
    """Подпись в статье. Не задана значит подписываемся брендом."""
    prof = prof or load()
    return (prof["article"].get("signature") or brand(prof)).strip()


def article_enabled(prof=None):
    prof = prof or load()
    return bool(prof["article"].get("enabled", True))


def window(prof=None):
    prof = prof or load()
    return (prof["channel"].get("window") or "").strip()


def timezone(prof=None):
    prof = prof or load()
    return (prof["channel"].get("tz") or "").strip()


# --- рубрики ---


def rubric_table(prof=None):
    """Таблица рубрик: значения по умолчанию плюс правки профиля."""
    prof = prof or load()
    table = {}
    for tag in RUBRIC_ORDER:
        table[tag] = copy.deepcopy(RUBRIC_DEFAULTS[tag])
    for tag, patch in (prof.get("rubrics") or {}).items():
        tag = str(tag).lstrip("#").strip()
        if not tag:
            continue
        if patch in (None, False, "off", "нет"):
            table.pop(tag, None)
            continue
        base = table.get(tag, {})
        table[tag] = _merge(base, patch if isinstance(patch, dict) else {})
    second = prof.get("second_brand") or {}
    if second.get("enabled") and second.get("tag"):
        tag = str(second["tag"]).lstrip("#").strip()
        row = table.get(tag, {})
        row.setdefault("forward", "none")
        if second.get("min"):
            row["min"] = second["min"]
        if second.get("max"):
            row["max"] = second["max"]
        table[tag] = row
    return table


def rubric_names(prof=None):
    return list(rubric_table(prof).keys())


def lengths(prof=None):
    out = {}
    for tag, row in rubric_table(prof).items():
        if row.get("min") and row.get("max"):
            out[tag] = (int(row["min"]), int(row["max"]))
    return out


def points(prof=None):
    out = {}
    for tag, row in rubric_table(prof).items():
        pair = row.get("points")
        if pair:
            out[tag] = (int(pair[0]), int(pair[1]))
    return out


def forward_required(prof=None):
    return set(tag for tag, row in rubric_table(prof).items()
               if row.get("forward") == "required")


def forward_wanted(prof=None):
    return set(tag for tag, row in rubric_table(prof).items()
               if row.get("forward") == "wanted")


def soft_first_screen(prof=None):
    return set(tag for tag, row in rubric_table(prof).items()
               if row.get("soft_first_screen"))


def routes(prof=None):
    """План по рубрике для tools/channel.py route."""
    out = {}
    for tag, row in rubric_table(prof).items():
        if not row.get("frame"):
            continue
        pair = row.get("points")
        out[tag] = (
            row.get("frame"),
            row.get("frame_alt") or row.get("frame"),
            (int(row.get("min", 0)), int(row.get("max", 0))),
            (int(pair[0]), int(pair[1])) if pair else None,
            row.get("file") or "reference/formats.md",
        )
    return out


def metrics(prof=None):
    """Цифры канала для оценки поста. Нули значат «замеров ещё нет»."""
    prof = prof or load()
    box = prof.get("metrics") or {}
    reach = box.get("reach") or [0, 0]
    react = box.get("reactions") or [0, 0]
    return {
        "subscribers": int(box.get("subscribers") or 0),
        "reach": (int(reach[0]), int(reach[1])),
        "reactions": (int(react[0]), int(react[1])),
    }


def extra_banned(prof=None):
    prof = prof or load()
    return [str(item).strip().lower() for item in (prof["voice"].get("extra_banned") or [])
            if str(item).strip()]


def extra_lexicon(prof=None):
    prof = prof or load()
    return [str(item).strip().lower() for item in (prof["voice"].get("extra_lexicon") or [])
            if str(item).strip()]


# --- проверка и вывод ---


def telegram(prof=None):
    """Настройки моста с Телеграмом: префиксы, режим, куда класть черновик."""
    prof = prof or load()
    out = dict(DEFAULTS["telegram"])
    for key, val in (prof.get("telegram") or {}).items():
        if val not in (None, "", []):
            out[key] = val
    out["prefixes"] = [str(item).strip() for item in (out.get("prefixes") or [])
                       if str(item).strip()]
    return out


def second_brand(prof=None):
    """Второй бренд: параллельный проект со своими правилами."""
    prof = prof or load()
    out = dict(DEFAULTS["second_brand"])
    for key, val in (prof.get("second_brand") or {}).items():
        if val is not None and val != "":
            out[key] = val
    return out


def greeting_max_words(prof=None):
    """Потолок слов в приветствии. Ноль значит без приветствия вообще."""
    prof = prof or load()
    try:
        return int(prof["voice"].get("greeting_max_words", 5))
    except (TypeError, ValueError):
        return 5


def validate(prof=None):
    """Список проблем словами. Пустой список значит профиль рабочий."""
    prof = prof or load()
    bad = []
    meta = prof.get("_meta", {})
    if meta.get("problem"):
        bad.append(meta["problem"])
    if not brand(prof):
        bad.append("нет brand.name: имя бренда обязательно")
    if not author(prof):
        bad.append("нет brand.author: кто пишет")
    if not prof["brand"].get("audience"):
        bad.append("нет brand.audience: для кого пишем")
    if not prof["brand"].get("tone"):
        bad.append("нет brand.tone: голос бренда в трёх словах")
    handle = channel(prof)
    if handle and not HANDLE_RE.match(handle):
        bad.append("channel.handle должен быть вида @имя_канала, а не %r" % handle)
    for label, url in links(prof):
        if not LABEL_RE.match(label):
            bad.append("ярлык ссылки %r не годится: капсом, до 12 знаков" % label)
        if not url.startswith(("http://", "https://")):
            bad.append("ссылка %r не начинается с http" % url)
    if footer_enabled(prof) and not footer(prof):
        bad.append("футер включён, но ссылок нет: заполни links или footer.template")
    if footer_enabled(prof) and len(footer(prof)) > 300:
        bad.append("футер длиннее 300 знаков: он съест тело поста")
    for char in "\u2014\u2013\u2015\u2012\u2212":
        if char in json.dumps(prof, ensure_ascii=False):
            bad.append("в профиле длинное тире: правило ноль запрещает его везде")
            break
    table = rubric_table(prof)
    if not table:
        bad.append("не осталось ни одной рубрики")
    for tag, row in table.items():
        lo, hi = row.get("min"), row.get("max")
        if lo and hi and int(lo) >= int(hi):
            bad.append("рубрика %s: коридор знаков задан наоборот" % tag)
    return bad


def source_kind(url):
    """Вид источника по адресу: от него зависит, чем его читать."""
    host = str(url or "").split("//", 1)[-1].split("/", 1)[0].lower()
    if host.endswith("t.me") or host.endswith("telegram.me"):
        return "telegram"
    if "youtube" in host or host.endswith("youtu.be"):
        return "youtube"
    if host.endswith("github.com"):
        return "github"
    if host.endswith("reddit.com"):
        return "reddit"
    if host in ("x.com", "twitter.com") or host.endswith(".x.com"):
        return "x"
    return "web"


def sources(prof=None):
    """Источники тем автора трои́ками имя, адрес, вид."""
    prof = prof or load()
    out = []
    for item in prof.get("sources") or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        name = str(item.get("name", "")).strip() or url
        kind = str(item.get("kind", "")).strip() or source_kind(url)
        role = str(item.get("role", "")).strip()
        if role:
            kind = kind + "/" + role
        out.append((name, url, kind))
    return out


HOW_TO_READ = {
    "telegram": "python3 tools/tg.py read",
    "youtube": "python3 tools/watch.py",
    "github": "python3 tools/research.py --read",
    "reddit": "python3 tools/research.py --read",
    "x": "python3 tools/research.py --read",
    "web": "python3 tools/research.py --read",
}


def sources_table(prof=None):
    """Таблица источников для reference/brand.md."""
    prof = prof or load()
    rows = sources(prof)
    if not rows:
        return ("Источников в профиле нет. Спроси автора, откуда он берёт темы, "
                "и запиши ответ в ключ sources.")
    out = ["| Источник | Адрес | Чем смотрим |", "| --- | --- | --- |"]
    for name, url, kind in rows:
        base = kind.split("/", 1)[0]
        how = HOW_TO_READ.get(base, HOW_TO_READ["web"])
        if "/ориентир" in kind:
            how = how + " (только тон и формат)"
        out.append("| %s | %s | `%s` |" % (name, url, how))
    return "\n".join(out)


def card(prof=None):
    """Карточка профиля словами. Её же показывает агент автору."""
    prof = prof or load()
    meta = prof.get("_meta", {})
    rows = [
        "ПРОФИЛЬ КАНАЛА",
        "источник: %s (%s)" % (meta.get("source", ""), meta.get("path", "")),
        "бренд: %s" % (brand(prof) or "не задан"),
        "автор: %s" % (author(prof) or "не задан"),
        "язык: %s" % language(prof),
        "голос: %s" % (prof["brand"].get("tone") or "не задан"),
        "аудитория: %s" % (prof["brand"].get("audience") or "не задана"),
        "темы: %s" % (", ".join(prof["brand"].get("topics") or []) or "не заданы"),
        "канал: %s" % (channel(prof) or "не задан"),
        "окно публикации: %s %s" % (window(prof) or "любое", timezone(prof)),
        "статья: %s" % (prof["article"].get("platform") if article_enabled(prof) else "выключена"),
        "подпись в статье: %s" % (article_author(prof) or "не задана"),
        "рубрики: %s" % ", ".join("#" + tag for tag in rubric_names(prof)),
        "футер: %s" % (footer(prof) or "нет"),
        "источники тем: %s" % (", ".join(n for n, _u, _k in sources(prof)) or "не заданы"),
    ]
    if is_demo(prof):
        rows.append("")
        rows.append("ЭТО ДЕМО-ПРОФИЛЬ. Пройди интервью: python3 tools/onboard.py")
    problems = validate(prof)
    if problems:
        rows.append("")
        rows.append("ПРОБЛЕМЫ (%d):" % len(problems))
        rows.extend("  - " + item for item in problems)
    return "\n".join(rows)


def who_block(prof=None):
    """Блок «кто пишет» для reference/brand.md и промптов."""
    prof = prof or load()
    pairs = links(prof)
    rows = [
        "КТО ПИШЕТ",
        "Автор: %s. Бренд: %s. Канал: %s." % (author(prof), brand(prof), channel(prof) or "не задан"),
        "Тон: %s." % (prof["brand"].get("tone") or "свой"),
        "Аудитория: %s." % (prof["brand"].get("audience") or "не задана"),
    ]
    topics = prof["brand"].get("topics") or []
    if topics:
        rows.append("Темы: %s." % ", ".join(topics))
    if prof["brand"].get("about"):
        rows.append("О себе: %s" % prof["brand"]["about"])
    if pairs:
        rows.append("Ссылки, которые существуют (другие не выдумывать):")
        rows.append(" | ".join("%s %s" % (label, url) for label, url in pairs))
    if article_enabled(prof):
        rows.append("Подпись в статье всегда %s. Площадка статьи: %s."
                    % (article_author(prof), prof["article"].get("platform")))
    taboo = prof["brand"].get("taboo") or []
    if taboo:
        rows.append("Запрещённые темы и слова: %s." % ", ".join(taboo))
    if window(prof):
        rows.append("Время публикации: %s по %s." % (window(prof), timezone(prof) or "местному"))
    return "\n".join(rows)


def links_table(prof=None):
    """Таблица ссылок в Markdown для reference/brand.md."""
    prof = prof or load()
    rows = ["| Что | Куда |", "|---|---|"]
    if channel_url(prof):
        rows.append("| Канал | %s |" % channel_url(prof))
    for label, url in links(prof):
        rows.append("| %s | %s |" % (label, url))
    if len(rows) == 2:
        rows.append("| ссылок нет | заполни links в профиле |")
    return "\n".join(rows)


def selftest():
    fails = []
    total = [0]

    def check(name, cond):
        total[0] += 1
        print("%s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            fails.append(name)

    demo = load(path=EXAMPLE)
    check("демо-профиль читается", bool(demo["brand"]["name"]))
    check("футер собирается из ссылок", footer(demo).count("](") >= 3)
    check("ярлыки футера найдены", len(footer_marks(demo)) >= 3)
    check("футер без ссылок ловится", bool(footer_plain_re(demo).search(
        "%s | %s" % (footer_marks(demo)[0], footer_marks(demo)[1]))))
    check("демо-профиль проходит проверку", validate(demo) == [])
    check("рубрики на месте", "абуз" in rubric_names(demo))
    check("коридор абуза дефолтный", lengths(demo)["абуз"] == (700, 1400))
    check("пункты абуза дефолтные", points(demo)["абуз"] == (4, 7))
    check("пересылка обязательна в абузе", "абуз" in forward_required(demo))
    check("маршрут абуза даёт SLAY", routes(demo)["абуз"][0] == "SLAY")

    patched = _merge(demo, {
        "rubrics": {"абуз": {"min": 300, "max": 600, "points": [2, 3], "forward": "none"},
                    "шортс": None,
                    "обзор": {"min": 400, "max": 800, "points": [1, 2],
                              "forward": "wanted", "frame": "PAS", "frame_alt": "BAB"}},
    })
    check("профиль переписывает коридор", lengths(patched)["абуз"] == (300, 600))
    check("профиль снимает пересылку", "абуз" not in forward_required(patched))
    check("профиль выключает рубрику", "шортс" not in rubric_names(patched))
    check("профиль добавляет свою рубрику", "обзор" in rubric_names(patched))
    check("своя рубрика попала в маршруты", routes(patched)["обзор"][0] == "PAS")

    template = _merge(demo, {"footer": {"template": "[ТУТ](https://example.com)"}})
    check("шаблон футера сильнее ссылок", footer(template) == "[ТУТ](https://example.com)")
    off = _merge(demo, {"footer": {"enabled": False}})
    check("футер выключается", footer(off) == "")

    broken = _merge(demo, {"brand": {"name": ""}, "channel": {"handle": "channel"}})
    problems = validate(broken)
    check("пустое имя ловится", any("brand.name" in item for item in problems))
    check("кривой хэндл ловится", any("channel.handle" in item for item in problems))

    missing = load(path=os.path.join(SKILL, "profile", "нет-такого.json"))
    check("без файла не падаем", missing["brand"]["name"] == DEFAULTS["brand"]["name"])
    check("без файла есть жалоба", any("нет" in item for item in validate(missing)))

    check("блок кто пишет собирается", "КТО ПИШЕТ" in who_block(demo))
    check("таблица ссылок собирается", links_table(demo).startswith("| Что |"))

    check("настройки телеграма читаются",
          telegram(demo)["mode"] in ("draft", "scheduled", "auto"))
    check("префиксы команд не пустые", bool(telegram(demo)["prefixes"]))
    check("второй бренд имеет тег", bool(second_brand(demo)["tag"]))
    check("приветствие измеряется числом", greeting_max_words(demo) >= 0)

    print()
    if fails:
        print("ПРОВАЛЕНО %d из %d" % (len(fails), total[0]))
        for name in fails:
            print("  - " + name)
        return 1
    print("Профиль: все %d проверок прошли." % total[0])
    return 0


def main():
    parser = argparse.ArgumentParser(description="Профиль канала для скилла")
    parser.add_argument("--show", action="store_true", help="карточка профиля словами")
    parser.add_argument("--json", action="store_true", help="профиль машинно")
    parser.add_argument("--check", action="store_true", help="проверить профиль")
    parser.add_argument("--footer", action="store_true", help="строка футера")
    parser.add_argument("--who", action="store_true", help="блок кто пишет")
    parser.add_argument("--sources", action="store_true", help="источники тем автора")
    parser.add_argument("--path", help="взять конкретный файл профиля")
    parser.add_argument("--selftest", action="store_true", help="самопроверка модуля")
    parser.add_argument("--version", action="store_true", help="версия модуля")
    args = parser.parse_args()

    if args.version:
        print(VERSION)
        return 0
    if args.selftest:
        return selftest()

    prof = load(path=args.path)

    if args.json:
        print(json.dumps(prof, ensure_ascii=False, indent=2))
        return 0
    if args.footer:
        print(footer(prof))
        return 0
    if args.sources:
        rows = sources(prof)
        if not rows:
            print(sources_table(prof))
            return 1
        for name, url, kind in rows:
            print("%-24s %-18s %s" % (name, kind, url))
        return 0
    if args.who:
        print(who_block(prof))
        return 0
    if args.check:
        problems = validate(prof)
        if problems:
            print("ПРОФИЛЬ СЛОМАН (%d):" % len(problems))
            for item in problems:
                print("  - %s" % item)
            print("Починить одной командой: python3 tools/onboard.py")
            return 1
        if is_demo(prof):
            print("Профиль рабочий, но это ДЕМО из поставки.")
            print("Свой профиль: python3 tools/onboard.py")
            return 0
        print("Профиль в порядке: %s" % brand(prof))
        return 0

    print(card(prof))
    return 0


if __name__ == "__main__":
    sys.exit(main())
