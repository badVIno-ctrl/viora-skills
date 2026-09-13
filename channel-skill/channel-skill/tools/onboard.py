#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Интервью на входе: собирает профиль канала и разливает его по скиллу.

Скилл без профиля работает на демо-бренде. Задача этого файла: задать автору
несколько вопросов, записать ответы в profile/profile.json и пересобрать всё, что из
профиля генерится: карточку бренда, блок «кто пишет», футеры в текстах и промпты.

Три способа пройти интервью:

1. Автор сам, в терминале:
       python3 tools/onboard.py
2. Модель спрашивает в чате и передаёт ответы одним JSON:
       python3 tools/onboard.py --questions
       echo '{...}' | python3 tools/onboard.py --stdin
3. Готовый шаблон из profile/profiles:
       python3 tools/onboard.py --from-json profile/profiles/ru-tech-telegram.json

Служебное:
       python3 tools/onboard.py --check      есть ли свой профиль (код 1 если демо)
       python3 tools/onboard.py --show       карточка текущего профиля
       python3 tools/onboard.py --render     пересобрать тексты по профилю
       python3 tools/onboard.py --selftest   самопроверка

Сторонних библиотек не нужно, только Python 3.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import profile as P  # noqa: E402

VERSION = "6.1.0"
SKILL = os.path.dirname(HERE)
PROFILE_DIR = os.path.join(SKILL, "profile")
TARGET = os.path.join(PROFILE_DIR, "profile.json")
STATE = os.path.join(PROFILE_DIR, ".render.json")

WHO_HEAD = "=== КТО ПИШЕТ ==="
EMDASHES = "\u2014\u2013\u2015\u2012\u2212"
WINDOW_RE = re.compile(r"^\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}$")
SECTION_RE = re.compile(r"^=== ", re.MULTILINE)
FOOTER_LINE_RE = re.compile(
    r"^\s*\[[^\]]{1,20}\]\(https?://[^)]+\)(\s*\|\s*\[[^\]]{1,20}\]\(https?://[^)]+\)){1,5}\s*$")

# Один источник вопросов для терминала и для модели.
# batch это номер порции: вопросы задаются группами, а не по одному.
QUESTIONS = [
    {"id": "brand_name", "batch": 1, "required": True, "kind": "text",
     "ask": "Как называется канал или бренд?",
     "hint": "Одно имя, как на аватарке. Пример: DEMO STUDIO"},
    {"id": "author", "batch": 1, "required": True, "kind": "text",
     "ask": "Как тебя подписывать: ник или имя?",
     "hint": "Так тебя будет называть модель и так ты подписан в постах"},
    {"id": "language", "batch": 1, "required": False, "kind": "text", "default": "ru",
     "ask": "На каком языке пишем посты?",
     "hint": "ru, en, es. По умолчанию ru"},
    {"id": "formats", "batch": 1, "required": False, "kind": "list",
     "ask": "Какой контент ты делаешь?",
     "hint": "Посты, шортсы, видео, стримы, статьи. Можно через запятую"},
    {"id": "topics", "batch": 2, "required": True, "kind": "list",
     "ask": "Про что канал? Три-пять тем через запятую.",
     "hint": "Пример: AI, Web, инди-игры"},
    {"id": "audience", "batch": 2, "required": True, "kind": "text",
     "ask": "Кто тебя читает и что ему нужно?",
     "hint": "Возраст, чем занимаются, за чем пришли, с чего читают"},
    {"id": "tone", "batch": 2, "required": True, "kind": "text",
     "default": "нашёл, проверил, принёс",
     "ask": "Голос канала в трёх словах?",
     "hint": "Пример: нашёл, проверил, принёс"},
    {"id": "about", "batch": 2, "required": False, "kind": "text",
     "ask": "Чем ты занимаешься кроме канала?",
     "hint": "Стек, работа, свои проекты. Нужно для личных деталей в постах"},
    {"id": "taboo", "batch": 2, "required": False, "kind": "list",
     "ask": "О чём не пишем никогда?",
     "hint": "Темы и слова в запрете, через запятую"},
    {"id": "channel_handle", "batch": 3, "required": False, "kind": "text",
     "ask": "Куда публикуем: хэндл канала?",
     "hint": "Вида @demo_channel. Пусто значит пока без автопубликации"},
    {"id": "links", "batch": 3, "required": False, "kind": "links",
     "ask": "Какие ссылки ставим в футер каждого поста?",
     "hint": "Формат ЯРЛЫК=адрес через запятую. Пример: ЧАТ=https://t.me/x, ТГК=https://t.me/y"},
    {"id": "sources", "batch": 3, "required": False, "kind": "sources",
     "ask": "Из каких источников ты берёшь темы? Дай ссылки.",
     "hint": "Свои и чужие ТГ-каналы, сайты, YouTube, GitHub. "
             "Формат ИМЯ=адрес или просто адреса через запятую"},
    {"id": "benchmarks", "batch": 3, "required": False, "kind": "sources",
     "ask": "На какие каналы ты похож или хочешь быть похож?",
     "hint": "Два-три ссылки. Нужны только для тона и формата, текст оттуда не копируется"},
    {"id": "article_platform", "batch": 3, "required": False, "kind": "text",
     "default": "telegra.ph",
     "ask": "Где лежат длинные тексты?",
     "hint": "telegra.ph, Notion, свой сайт. Слово нет значит длинных текстов не будет"},
    {"id": "article_signature", "batch": 3, "required": False, "kind": "text",
     "ask": "Как подписывать статьи?",
     "hint": "Пусто значит именем бренда"},
    {"id": "window", "batch": 4, "required": False, "kind": "text", "default": "16:30-21:00",
     "ask": "В какое время выходят посты?",
     "hint": "Вида 16:30-21:00"},
    {"id": "tz", "batch": 4, "required": False, "kind": "text", "default": "Europe/Moscow",
     "ask": "В каком часовом поясе ты живёшь?",
     "hint": "Вида Europe/Moscow или Asia/Almaty"},
    {"id": "subscribers", "batch": 4, "required": False, "kind": "number",
     "ask": "Сколько сейчас подписчиков?",
     "hint": "Цифра нужна только для оценки охвата. Пусто можно"},
    {"id": "rubrics_mode", "batch": 5, "required": False, "kind": "text", "default": "стандарт",
     "ask": "Рубрики оставить стандартные или задать свои?",
     "hint": "Стандартные: #абуз, #сервисы, #гайд, #релиз, #девлог и дальше. "
             "Свои задаются видом тег=мин-макс, например обзор=400-800"},
    {"id": "second_brand", "batch": 5, "required": False, "kind": "text",
     "ask": "Есть второй формат с другими правилами?",
     "hint": "Например короткие мемы без футера. Имя или слово нет"},
    {"id": "telegram_mode", "batch": 5, "required": False, "kind": "text", "default": "draft",
     "ask": "Как публиковать из Телеграма: draft, scheduled или auto?",
     "hint": "draft показывает черновик, scheduled ставит в отложенные, auto шлёт сразу"},
]

BRAND_TEMPLATE = """# Бренд и автор

Этот файл собирается из профиля. Править руками не надо: поменяй
profile/profile.json и выполни `python3 tools/onboard.py --render`.

## Кто пишет

Автор: **{author}**. Бренд: **{brand}**. Язык постов: {language}.
Тон: {tone}. Не продавец и не пресс-служба.
{about_line}{formats_line}Темы канала: {topics}.

Подпись автора в статье всегда {signature}. Ник автора в статье не стоит.

## Ссылки

{links_table}

{footer_section}

## Источники тем

{sources_block}

Тему ищем сначала здесь, потом в общем поиске. Ссылка в посте ведёт на сам материал,
а не на чужой канал. Цифра без ссылки в пост не едет.

## Аудитория

{audience}

Поэтому работают: цифры, сроки, честное «у меня не завелось с первого раза» и живые
детали. Не работают: маркетинг, офисные слова, длинные вступления.

## Запреты бренда

{taboo_block}

## Ритм канала

- Окно публикации: {window} по {tz}.
- Площадка длинных текстов: {article}.
- Рубрики: {rubrics}.

## Цифры канала

{metrics_block}

Цифры нужны только для понимания масштаба. В пост их не тащим без спроса и
обновляем только со слов автора. Живут они в `memory/metrics.md`.

## Свои посты для перелинковки

Ссылки на свои вышедшие посты живут в `memory/post-log.md`. Если тема пересекается
с уже вышедшим постом, ставим ссылку ярлыком вида `[ПРОШЛЫЙ ПОСТ]`. Это дешёвый
прирост просмотров старых постов.

## Темы, которые уже были

Перед новым постом сверяемся с `memory/post-log.md`, чтобы не предлагать то же самое
второй раз. Если тема уже была, говорим об этом автору и предлагаем углубление
вместо повтора.

## Ядро: кто пишет

Этот блок едет в `PROMPT-CORE.txt` через `tools/build_prompt.py`. Он собирается из профиля.

<!-- CORE:START name="who" -->
{who}
<!-- CORE:END -->
"""


def as_list(value):
    """Строка через запятую или список в чистый список строк."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = [str(x).strip() for x in value]
    else:
        items = [x.strip() for x in re.split(r"[,;\n]", str(value))]
    return [x for x in items if x]


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip() or value.strip().lower() in ("нет", "-", "no", "none", "пропустить", "skip")
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def parse_links(value):
    """Принимает «ЧАТ=url, ТГК=url», список строк или список словарей."""
    if is_empty(value):
        return []
    raw = value if isinstance(value, (list, tuple)) else re.split(r"[,\n;]", str(value))
    out = []
    for item in raw:
        if isinstance(item, dict):
            label = str(item.get("label", "")).strip()
            url = str(item.get("url", "")).strip()
        else:
            text = str(item).strip()
            if not text:
                continue
            if "=" in text:
                label, url = text.split("=", 1)
            elif "|" in text:
                label, url = text.split("|", 1)
            else:
                label, url = "", text
            label = label.strip()
            url = url.strip()
        if not url:
            continue
        if not url.startswith("http"):
            if url.startswith("@"):
                url = "https://t.me/" + url.lstrip("@")
            elif url.startswith("t.me/") or url.startswith("github.com/"):
                url = "https://" + url
            else:
                continue
        if not label:
            host = url.split("//", 1)[-1].split("/", 1)[0].lower()
            guess = {
                "t.me": "ТГК",
                "github.com": "GITHUB",
                "www.youtube.com": "YOUTUBE",
                "youtube.com": "YOUTUBE",
                "youtu.be": "YOUTUBE",
            }
            label = guess.get(host, host.split(".")[0].upper())
        label = re.sub(r"[\[\]()|]", "", label).strip().upper()[:20]
        if label and not any(x["url"] == url for x in out):
            out.append({"label": label, "url": url})
    return out[:6]


def parse_rubrics(value):
    """«обзор=400-800, шортс=нет» в таблицу коридоров."""
    if is_empty(value) or str(value).strip().lower() in ("стандарт", "standard", "default", "как есть"):
        return None
    if isinstance(value, dict):
        return value
    table = {}
    for chunk in re.split(r"[,\n;]", str(value)):
        chunk = chunk.strip().lstrip("#")
        if not chunk:
            continue
        if "=" in chunk:
            name, span = chunk.split("=", 1)
        else:
            name, span = chunk, ""
        name = name.strip().lstrip("#").lower()
        if not name:
            continue
        base = dict(P.RUBRIC_DEFAULTS.get(name, {
            "length": [400, 900],
            "points": [3, 5],
            "forward": "none",
            "frameworks": ["PAS", "BAB"],
            "reference": "",
            "soft": False,
        }))
        pair = re.findall(r"\d+", span or "")
        if len(pair) >= 2:
            low, high = int(pair[0]), int(pair[1])
            if low > high:
                low, high = high, low
            base["length"] = [low, high]
        table[name] = base
    return table or None


def _no_long_dashes(obj):
    """Сносит длинные тире во всех строках структуры: правило бренда."""
    text = json.dumps(obj, ensure_ascii=False)
    for ch in EMDASHES:
        text = text.replace(ch, "-")
    return json.loads(text)


def parse_sources(value, role=""):
    """Принимает «ИМЯ=url, url, @handle» и даёт список источников."""
    if is_empty(value):
        return []
    raw = value if isinstance(value, (list, tuple)) else re.split(r"[,\n;]", str(value))
    out, seen = [], set()
    for item in raw:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
        else:
            text = str(item).strip()
            if not text:
                continue
            if "=" in text:
                name, url = text.split("=", 1)
            else:
                name, url = "", text
            name, url = name.strip(), url.strip()
        if not url:
            continue
        if url.startswith("@"):
            url = "https://t.me/" + url.lstrip("@")
        elif not url.startswith("http"):
            if "." not in url:
                continue
            url = "https://" + url
        if url in seen:
            continue
        seen.add(url)
        kind = P.source_kind(url)
        if not name:
            tail = url.rstrip("/").split("/")[-1]
            name = tail.lstrip("@") or url.split("//", 1)[-1].split("/", 1)[0]
        row = {"name": name[:40], "url": url, "kind": kind}
        if role:
            row["role"] = role
        out.append(row)
        if len(out) >= 12:
            break
    return out


def build_profile(answers, base=None):
    """Ответы интервью в готовый профиль. Готовый профиль тоже принимается."""
    answers = dict(answers or {})
    if "brand" in answers and "brand_name" not in answers:
        # на вход пришёл уже собранный профиль: берём его за основу
        merged = P._merge(P.DEFAULTS, answers)
        merged.pop("_meta", None)
        return _no_long_dashes(merged)

    prof = P._merge(P.DEFAULTS, base or {})
    prof.pop("_meta", None)
    if not base:
        # Демо-значения из поставки не должны протечь в живой профиль.
        prof["brand"]["name"] = ""
        prof["brand"]["short"] = ""
        prof["brand"]["author"] = ""
        prof["channel"]["handle"] = ""
        prof["channel"]["url"] = ""

    brand = str(answers.get("brand_name", "")).strip()
    if brand:
        prof["brand"]["name"] = brand
        short = str(answers.get("brand_short", "")).strip()
        prof["brand"]["short"] = short or (brand.split()[0] if brand.split() else brand)
    author = str(answers.get("author", "")).strip()
    if author:
        prof["brand"]["author"] = author
    language = str(answers.get("language", "")).strip().lower()
    if language:
        prof["brand"]["language"] = language[:5]
    tone = str(answers.get("tone", "")).strip()
    if tone:
        prof["brand"]["tone"] = tone
    about = str(answers.get("about", "")).strip()
    if not is_empty(about):
        prof["brand"]["about"] = about
    formats = as_list(answers.get("formats"))
    if formats:
        prof["brand"]["formats"] = formats
    topics = as_list(answers.get("topics"))
    if topics:
        prof["brand"]["topics"] = topics
    audience = str(answers.get("audience", "")).strip()
    if audience:
        prof["brand"]["audience"] = audience
    if "taboo" in answers:
        prof["brand"]["taboo"] = as_list(answers.get("taboo"))

    if "channel_handle" in answers:
        handle = str(answers.get("channel_handle", "")).strip()
        if is_empty(handle):
            prof["channel"]["handle"] = ""
            prof["channel"]["url"] = ""
        else:
            if handle.startswith("http"):
                name = handle.rstrip("/").split("/")[-1]
            else:
                name = handle.lstrip("@")
            name = re.sub(r"[^A-Za-z0-9_]", "", name)
            prof["channel"]["handle"] = "@" + name if name else ""
            prof["channel"]["url"] = "https://t.me/" + name if name else ""

    window = str(answers.get("window", "")).strip()
    if WINDOW_RE.match(window or ""):
        prof["channel"]["window"] = window
    tz = str(answers.get("tz", "")).strip()
    if tz and "/" in tz:
        prof["channel"]["tz"] = tz

    links = parse_links(answers.get("links"))
    if links:
        prof["links"] = links
        prof["footer"]["enabled"] = True
    elif "links" in answers:
        prof["links"] = []
        prof["footer"]["enabled"] = False

    picked = parse_sources(answers.get("sources"))
    picked += parse_sources(answers.get("benchmarks"), role="ориентир")
    if picked:
        known = set()
        rows = []
        for row in picked:
            if row["url"] in known:
                continue
            known.add(row["url"])
            rows.append(row)
        prof["sources"] = rows
    elif "sources" in answers or "benchmarks" in answers:
        prof["sources"] = []

    if "article_platform" in answers:
        platform = str(answers.get("article_platform", "")).strip()
        if is_empty(platform):
            prof["article"]["enabled"] = False
        else:
            prof["article"]["enabled"] = True
            prof["article"]["platform"] = platform
    signature = str(answers.get("article_signature", "")).strip()
    prof["article"]["signature"] = signature or prof["brand"]["name"].title()

    subs = answers.get("subscribers")
    if not is_empty(subs):
        digits = re.findall(r"\d+", str(subs))
        if digits:
            count = int(digits[0])
            prof["metrics"]["subscribers"] = count
            low = max(1, int(count * 0.35))
            high = max(low + 1, int(count * 1.2))
            prof["metrics"]["reach"] = [low, high]
            prof["metrics"]["reactions"] = [max(1, count // 200), max(2, count // 45)]

    rubrics = parse_rubrics(answers.get("rubrics_mode") or answers.get("rubrics"))
    if rubrics:
        prof["rubrics"] = rubrics

    second = answers.get("second_brand")
    if is_empty(second):
        prof["second_brand"] = {"enabled": False, "name": "", "tag": "мем",
                                "min": 40, "max": 220, "footer": False}
    else:
        prof["second_brand"] = {
            "enabled": True,
            "name": str(second).strip(),
            "tag": "мем",
            "min": 40,
            "max": 220,
            "footer": False,
        }

    mode = str(answers.get("telegram_mode", "")).strip().lower()
    if mode in ("draft", "scheduled", "auto"):
        prof["telegram"]["mode"] = mode

    # Футер без ссылок смысла не имеет: гасим его сами, а не ругаемся на автора.
    has_template = bool((prof["footer"].get("template") or "").strip())
    if prof["footer"].get("enabled") and not prof.get("links") and not has_template:
        prof["footer"]["enabled"] = False

    return _no_long_dashes(prof)


# --- тексты, которые собираются из профиля ---


def brand_md_text(prof):
    """Полный текст reference/brand.md по профилю."""
    box = prof.get("brand", {})
    about = (box.get("about") or "").strip()
    formats = box.get("formats") or []
    taboo = box.get("taboo") or []
    stats = P.metrics(prof)
    foot = P.footer(prof)

    if foot:
        footer_section = (
            "Футер каждого поста, знак в знак:\n\n%s\n\n"
            "Ставится одной строкой в конце. Ни одной ссылки вне этого списка не выдумываем."
        ) % foot
    else:
        footer_section = "Футер у бренда выключен: ссылки в конец поста не ставим."

    if taboo:
        taboo_block = "\n".join("- Не пишем: %s." % item for item in taboo)
    else:
        taboo_block = "- Запретов автор не задавал. Общее правило: никакой незаконности и никаких чужих данных."

    if stats["subscribers"]:
        metrics_block = "- Подписчиков: %d.\n- Обычный охват поста: %d-%d.\n- Реакций на пост: %d-%d." % (
            stats["subscribers"], stats["reach"][0], stats["reach"][1],
            stats["reactions"][0], stats["reactions"][1])
    else:
        metrics_block = "- Замеров пока нет. Оценка поста работает и без них, только грубее."

    who = P.who_block(prof)
    who_body = "\n".join(who.split("\n")[1:]).strip() or who.strip()

    return BRAND_TEMPLATE.format(
        author=P.author(prof) or "не задан",
        brand=P.brand(prof) or "не задан",
        language=P.language(prof),
        tone=box.get("tone") or "свой",
        about_line=("О авторе: %s\n" % about) if about else "",
        formats_line=("Форматы: %s.\n" % ", ".join(formats)) if formats else "",
        topics=", ".join(box.get("topics") or []) or "не заданы",
        signature=P.article_author(prof) or "именем бренда",
        links_table=P.links_table(prof),
        sources_block=P.sources_table(prof),
        footer_section=footer_section,
        audience=box.get("audience") or "Аудитория не задана: спроси автора перед работой.",
        taboo_block=taboo_block,
        window=P.window(prof) or "любое",
        tz=P.timezone(prof) or "местному времени",
        article=(prof["article"].get("platform") if P.article_enabled(prof) else "длинные тексты выключены"),
        rubrics=", ".join("#" + tag for tag in P.rubric_names(prof)),
        metrics_block=metrics_block,
        who=who_body,
    )


def quickcard_who_text(prof):
    """Содержимое секции «КТО ПИШЕТ» в QUICKCARD.txt."""
    who = P.who_block(prof)
    body = "\n".join(who.split("\n")[1:]).strip()
    return "%s\n%s\n" % (WHO_HEAD, body)


def swap_section(text, head, new_block):
    """Заменяет секцию карточки от её заголовка до следующего заголовка."""
    start = text.find(head)
    if start < 0:
        return text, False
    match = SECTION_RE.search(text, start + len(head))
    end = match.start() if match else len(text)
    block = new_block if new_block.endswith("\n") else new_block + "\n"
    return text[:start] + block + "\n" + text[end:], True


def _labels_of(line):
    return tuple(re.findall(r"\[([^\]]{1,20})\]\(", line))


def swap_footer(text, old, new):
    """Меняет старую строку футера на новую. Возвращает текст и число замен."""
    if not old or old == new:
        return text, 0
    hits = 0
    if old in text:
        hits += text.count(old)
        text = text.replace(old, new)
    old_labels = _labels_of(old)
    if not old_labels:
        return text, hits
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if not FOOTER_LINE_RE.match(line):
            continue
        if line.strip() == new.strip():
            continue
        if set(_labels_of(line)) == set(old_labels):
            lines[index] = new
            hits += 1
    return "\n".join(lines), hits


def last_footer():
    """Какой футер сейчас в текстах: из состояния, иначе демо-футер поставки."""
    try:
        with open(STATE, encoding="utf-8") as handle:
            saved = json.load(handle)
        value = (saved.get("footer") or "").strip()
        if value:
            return value
    except (OSError, ValueError):
        pass
    return P.footer(P.load(path=P.EXAMPLE))


# --- разливка профиля по скиллу ---

RENDER_TARGETS = (
    "SKILL.md",
    "QUICKCARD.txt",
    "ROUTER.md",
    "ONBOARDING.md",
    "reference",
    "memory",
    "evals",
    "tools/tests",
    "tools/sample-post.txt",
)
TEXT_EXT = (".md", ".txt", ".json")


def _text_files(root):
    """Все текстовые файлы, в которых может стоять футер."""
    out = []
    for target in RENDER_TARGETS:
        path = os.path.join(root, target)
        if os.path.isfile(path):
            out.append(path)
            continue
        if not os.path.isdir(path):
            continue
        for base, dirs, names in os.walk(path):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
            for name in sorted(names):
                if name.endswith(TEXT_EXT):
                    out.append(os.path.join(base, name))
    return out


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _run(root, script, args=()):
    """Запускает соседний инструмент. Возвращает строку про результат."""
    path = os.path.join(root, "tools", script)
    if not os.path.exists(path):
        return "%s: нет в поставке, пропускаю" % script
    try:
        done = subprocess.run(
            [sys.executable, path] + list(args),
            cwd=root, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as err:
        return "%s: не запустился (%s)" % (script, err)
    if done.returncode == 0:
        return "%s: готово" % script
    tail = (done.stderr or done.stdout or "").strip().split("\n")[-1:]
    return "%s: код %d %s" % (script, done.returncode, tail[0] if tail else "")


def render(root=None, quiet=False, rebuild=True):
    """Пересобирает всё, что зависит от профиля. Возвращает код выхода."""
    root = os.path.abspath(root or SKILL)
    prof = P.load(root)
    problems = P.validate(prof)
    if problems:
        print("Профиль не готов, разливка отменена:")
        for item in problems:
            print("  - " + item)
        return 1

    steps = []

    brand_path = os.path.join(root, "reference", "brand.md")
    if os.path.isdir(os.path.dirname(brand_path)):
        _write(brand_path, brand_md_text(prof))
        steps.append("reference/brand.md: собран из профиля")

    card_path = os.path.join(root, "QUICKCARD.txt")
    if os.path.exists(card_path):
        text, done = swap_section(_read(card_path), WHO_HEAD, quickcard_who_text(prof))
        if done:
            _write(card_path, text)
            steps.append("QUICKCARD.txt: секция КТО ПИШЕТ обновлена")

    old = last_footer()
    new = P.footer(prof)
    changed = 0
    if new and old and old != new:
        for path in _text_files(root):
            before = _read(path)
            after, hits = swap_footer(before, old, new)
            if hits and after != before:
                _write(path, after)
                changed += 1
        steps.append("футер переписан в файлах: %d" % changed)
    elif not new:
        steps.append("футер выключен в профиле: строки не трогал")
    else:
        steps.append("футер уже совпадает с профилем")

    try:
        os.makedirs(PROFILE_DIR, exist_ok=True)
        _write(STATE, json.dumps({
            "footer": new,
            "brand": P.brand(prof),
            "author": P.author(prof),
            "version": VERSION,
        }, ensure_ascii=False, indent=2) + "\n")
    except OSError as err:
        steps.append("состояние не записалось: %s" % err)

    if rebuild:
        steps.append(_run(root, "build_prompt.py"))
        steps.append(_run(root, "sizes.py", ["--write"]))

    if not quiet:
        print("Разливка профиля:")
        for line in steps:
            print("  - " + line)
        print("")
        print(P.card(prof))
    return 0


def save(prof, path=None):
    """Пишет profile/profile.json. Служебные поля не сохраняются."""
    target = os.path.abspath(path or TARGET)
    clean = dict(prof)
    clean.pop("_meta", None)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    _write(target, json.dumps(clean, ensure_ascii=False, indent=2) + "\n")
    return target


# --- интервью в терминале ---

BATCH_TITLES = {
    1: "1 из 5. Кто ты",
    2: "2 из 5. О чём и для кого",
    3: "3 из 5. Ссылки: канал, футер, источники",
    4: "4 из 5. Ритм и масштаб",
    5: "5 из 5. Рубрики и публикация",
}


def questions_json():
    """Вопросы для модели: она задаёт их в чате своими словами."""
    return {
        "version": VERSION,
        "batches": [
            {
                "batch": number,
                "title": BATCH_TITLES[number],
                "questions": [
                    {k: q[k] for k in ("id", "ask", "hint", "kind", "required", "default") if k in q}
                    for q in QUESTIONS if q["batch"] == number
                ],
            }
            for number in sorted(BATCH_TITLES)
        ],
        "then": "echo '{\"brand_name\": ...}' | python3 tools/onboard.py --stdin",
    }


def ask_all(stream=None):
    """Задаёт вопросы в терминале и возвращает ответы."""
    stream = stream or sys.stdin
    answers = {}
    print("Интервью о канале. Девятнадцать вопросов, пять минут.")
    print("Enter без текста берёт значение по умолчанию или пропускает вопрос.")
    current = None
    for question in QUESTIONS:
        if question["batch"] != current:
            current = question["batch"]
            print("")
            print("--- %s ---" % BATCH_TITLES[current])
        while True:
            print("")
            print(question["ask"])
            print("  " + question["hint"])
            default = question.get("default", "")
            prompt = "> " if not default else "[%s] > " % default
            try:
                sys.stdout.write(prompt)
                sys.stdout.flush()
                line = stream.readline()
            except (KeyboardInterrupt, EOFError):
                print("")
                print("Интервью прервано, ничего не сохранёно.")
                raise SystemExit(1)
            if line == "":
                print("")
                print("Ввод закончился раньше вопросов. Ничего не сохранёно.")
                raise SystemExit(1)
            value = line.strip() or default
            if question.get("required") and not str(value).strip():
                print("Этот вопрос без ответа оставить нельзя.")
                continue
            answers[question["id"]] = value
            break
    return answers


def apply_answers(answers, root=None, quiet=False, rebuild=True):
    """Ответы в профиль, проверка, запись и разливка."""
    prof = build_profile(answers)
    problems = P.validate(P._merge(prof, {"_meta": {}}))
    if problems:
        print("Ответы пока не складываются в профиль:")
        for item in problems:
            print("  - " + item)
        print("")
        print("Исправь ответы и повтори. Ничего не записал.")
        return 1
    where = save(prof, os.path.join(os.path.abspath(root or SKILL), "profile", "profile.json"))
    if not quiet:
        print("Профиль записан: %s" % where)
        print("")
    return render(root=root, quiet=quiet, rebuild=rebuild)


# --- самопроверка ---

SAMPLE = {
    "brand_name": "KINO LAB",
    "author": "lena",
    "language": "ru",
    "formats": "посты, шортсы",
    "topics": "кино, монтаж, свет",
    "audience": "начинающие видеографы, смотрят с телефона",
    "tone": "показал, разобрал, отдал",
    "about": "монтирую рекламу и веду курс",
    "taboo": "пиратские сборки, взлом плагинов",
    "channel_handle": "@kino_lab",
    "links": "ЧАТ=https://t.me/kino_lab_chat, YOUTUBE=https://www.youtube.com/@kinolab",
    "article_platform": "telegra.ph",
    "article_signature": "Kino Lab",
    "window": "18:00-22:00",
    "tz": "Europe/Berlin",
    "subscribers": "1200",
    "rubrics_mode": "обзор=400-800, шортс=250-500",
    "second_brand": "нет",
    "telegram_mode": "scheduled",
}


def selftest():
    fails = []
    checks = 0

    def ok(name, condition):
        nonlocal checks
        checks += 1
        if condition:
            print("PASS %s" % name)
        else:
            fails.append(name)
            print("FAIL %s" % name)

    ok("вопросы есть", len(QUESTIONS) >= 15)
    ok("идентификаторы уникальны",
       len({q["id"] for q in QUESTIONS}) == len(QUESTIONS))
    ok("каждый вопрос с подсказкой", all(q.get("hint") for q in QUESTIONS))
    ok("порции от 1 до 5", {q["batch"] for q in QUESTIONS} == {1, 2, 3, 4, 5})
    ok("в вопросах нет длинных тире",
       not any(ch in json.dumps(QUESTIONS, ensure_ascii=False) for ch in EMDASHES))

    ok("список из строки", as_list("a, b , c") == ["a", "b", "c"])
    ok("список из списка", as_list(["a", " b "]) == ["a", "b"])
    ok("пустое слово нет", is_empty("нет") and is_empty("  ") and not is_empty("да"))

    pair = parse_links("ЧАТ=https://t.me/x, GITHUB=https://github.com/y")
    ok("ссылки разобраны", pair == [{"label": "ЧАТ", "url": "https://t.me/x"},
                                   {"label": "GITHUB", "url": "https://github.com/y"}])
    ok("ярлык угадан", parse_links("https://t.me/z") == [{"label": "ТГК",
                                                      "url": "https://t.me/z"}])
    ok("хэндл в ссылке", parse_links("ЧАТ=@my_chat")[0]["url"] == "https://t.me/my_chat")
    ok("мусор отброшен", parse_links("слова без адреса") == [])
    ok("ссылок не больше шести",
       len(parse_links(",".join("L%d=https://t.me/a%d" % (i, i) for i in range(9)))) == 6)

    ok("стандартные рубрики", parse_rubrics("стандарт") is None)
    table = parse_rubrics("обзор=400-800, шортс=500-250")
    ok("свои рубрики", set(table) == {"обзор", "шортс"})
    ok("коридор выровнен", table["шортс"]["length"] == [250, 500])

    prof = build_profile(SAMPLE)
    ok("бренд взят", prof["brand"]["name"] == "KINO LAB")
    ok("короткое имя", prof["brand"]["short"] == "KINO")
    ok("автор взят", prof["brand"]["author"] == "lena")
    ok("темы списком", prof["brand"]["topics"] == ["кино", "монтаж", "свет"])
    ok("запреты списком", len(prof["brand"]["taboo"]) == 2)
    ok("хэндл с собакой", prof["channel"]["handle"] == "@kino_lab")
    ok("адрес канала", prof["channel"]["url"] == "https://t.me/kino_lab")
    ok("окно взято", prof["channel"]["window"] == "18:00-22:00")
    ok("пояс взят", prof["channel"]["tz"] == "Europe/Berlin")
    ok("подпись статьи", prof["article"]["signature"] == "Kino Lab")
    ok("цифры посчитаны", prof["metrics"]["subscribers"] == 1200
       and prof["metrics"]["reach"][1] > prof["metrics"]["reach"][0])
    ok("второго бренда нет", prof["second_brand"]["enabled"] is False)
    ok("режим публикации", prof["telegram"]["mode"] == "scheduled")
    ok("служебных полей нет", "_meta" not in prof)
    ok("профиль без длинных тире",
       not any(ch in json.dumps(prof, ensure_ascii=False) for ch in EMDASHES))
    ok("профиль проходит проверку", P.validate(P._merge(prof, {"_meta": {}})) == [])

    empty = build_profile(dict(SAMPLE, links="", channel_handle="", article_platform="нет"))
    ok("без ссылок футер выключен", empty["footer"]["enabled"] is False)
    ok("без канала хэндл пуст", empty["channel"]["handle"] == "")
    ok("без статей площадка выключена", empty["article"]["enabled"] is False)
    ok("пустой профиль тоже валиден", P.validate(P._merge(empty, {"_meta": {}})) == [])

    minimal = build_profile({"brand_name": "KINO LAB", "author": "lena",
                             "topics": "кино", "audience": "новички",
                             "tone": "показал, разобрал, отдал"})
    ok("минимальные ответы валидны", P.validate(P._merge(minimal, {"_meta": {}})) == [])
    ok("без ссылок футер сам гаснет", minimal["footer"]["enabled"] is False)
    ok("площадка статей осталась по умолчанию", minimal["article"]["enabled"] is True)
    ok("демо-канал не протек", minimal["channel"]["handle"] == ""
       and "demo" not in json.dumps(minimal, ensure_ascii=False))

    ready = build_profile(json.loads(json.dumps(prof)))
    ok("готовый профиль принимается", ready["brand"]["name"] == "KINO LAB")

    full = P._merge(prof, {"_meta": {"path": "", "source": "тест", "demo": False,
                                    "problem": "", "filled": True}})
    text = brand_md_text(full)
    ok("карточка бренда с автором", "lena" in text and "KINO LAB" in text)
    ok("карточка с ядром", "CORE:START" in text and "CORE:END" in text)
    ok("карточка без длинных тире", not any(ch in text for ch in EMDASHES))
    ok("секция кто пишет", quickcard_who_text(full).startswith(WHO_HEAD))

    card = "HEAD\n\n=== КТО ПИШЕТ ===\nстарое\n\n=== ДАЛЬШЕ ===\nтело\n"
    swapped, done = swap_section(card, WHO_HEAD, "=== КТО ПИШЕТ ===\nновое\n")
    ok("секция заменена", done and "новое" in swapped and "старое" not in swapped)
    ok("соседняя секция цела", "=== ДАЛЬШЕ ===\nтело" in swapped)
    ok("чужой заголовок не трогается", swap_section(card, "=== НЕТ ===", "x")[1] is False)

    old = "[ЧАТ](https://t.me/a) | [ТГК](https://t.me/b)"
    new = "[ЧАТ](https://t.me/c) | [ТГК](https://t.me/d)"
    body = "текст\n\n%s\n\nещё текст\n" % old
    out, hits = swap_footer(body, old, new)
    ok("футер заменён", hits == 1 and new in out and old not in out)
    moved = "текст\n\n[ТГК](https://t.me/b) | [ЧАТ](https://t.me/a)\n"
    out2, hits2 = swap_footer(moved, old, new)
    ok("футер с другим порядком тоже", hits2 == 1 and new in out2)
    keep = "читай [ДОКИ](https://example.com/docs) в теле\n"
    ok("строка в тексте не футер", swap_footer(keep, old, new)[1] == 0)
    ok("совпадение не трогается", swap_footer(body, new, new)[1] == 0)

    box = questions_json()
    ok("вопросы для модели собраны", len(box["batches"]) == 5
       and sum(len(b["questions"]) for b in box["batches"]) == len(QUESTIONS))

    print("")
    if fails:
        print("ПРОВАЛЕНО %d из %d" % (len(fails), checks))
        for name in fails:
            print("  - " + name)
        return 1
    print("Интервью: все %d проверок прошли." % checks)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Интервью о канале и сборка профиля скилла")
    parser.add_argument("--questions", action="store_true",
                        help="отдать вопросы в JSON: модель спросит их в чате")
    parser.add_argument("--stdin", action="store_true",
                        help="принять ответы одним JSON со входа")
    parser.add_argument("--from-json", dest="from_json", default="",
                        help="взять готовый профиль или ответы из файла")
    parser.add_argument("--show", action="store_true", help="показать текущий профиль")
    parser.add_argument("--check", action="store_true",
                        help="код 1 если профиля нет или он демовый")
    parser.add_argument("--render", action="store_true",
                        help="пересобрать тексты по текущему профилю")
    parser.add_argument("--no-rebuild", action="store_true",
                        help="не запускать build_prompt.py и sizes.py")
    parser.add_argument("--force", action="store_true",
                        help="перезаписать существующий профиль без вопроса")
    parser.add_argument("--root", default="", help="корень скилла, по умолчанию рядом")
    parser.add_argument("--quiet", action="store_true", help="без лишних строк")
    parser.add_argument("--selftest", action="store_true", help="самопроверка")
    parser.add_argument("--version", action="store_true", help="версия")
    args = parser.parse_args()

    root = os.path.abspath(args.root) if args.root else SKILL
    rebuild = not args.no_rebuild

    if args.version:
        print("onboard.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()
    if args.questions:
        print(json.dumps(questions_json(), ensure_ascii=False, indent=2))
        return 0
    if args.show:
        print(P.card(P.load(root)))
        return 0
    if args.check:
        prof = P.load(root)
        if P.is_demo(prof) or not prof.get("_meta", {}).get("filled"):
            print("Профиля нет: скилл работает на демо-бренде.")
            print("Пройди интервью: python3 tools/onboard.py")
            return 1
        problems = P.validate(prof)
        if problems:
            print("Профиль есть, но с проблемами:")
            for item in problems:
                print("  - " + item)
            return 1
        print("Профиль на месте: %s" % (P.brand(prof)))
        return 0
    if args.render:
        return render(root=root, quiet=args.quiet, rebuild=rebuild)

    if args.from_json:
        try:
            with open(args.from_json, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as err:
            print("Файл не читается: %s" % err)
            return 1
        return apply_answers(data, root=root, quiet=args.quiet, rebuild=rebuild)

    if args.stdin:
        raw = sys.stdin.read().strip()
        if not raw:
            print("На входе пусто. Ожидаю JSON с ответами или готовым профилем.")
            return 1
        try:
            data = json.loads(raw)
        except ValueError as err:
            print("Это не JSON: %s" % err)
            return 1
        return apply_answers(data, root=root, quiet=args.quiet, rebuild=rebuild)

    existing = os.path.join(root, "profile", "profile.json")
    if os.path.exists(existing) and not args.force:
        print("Профиль уже есть: %s" % existing)
        print("Посмотреть: python3 tools/onboard.py --show")
        print("Пересобрать тексты: python3 tools/onboard.py --render")
        print("Пройти интервью заново: python3 tools/onboard.py --force")
        return 0

    answers = ask_all()
    return apply_answers(answers, root=root, quiet=args.quiet, rebuild=rebuild)


if __name__ == "__main__":
    raise SystemExit(main())
