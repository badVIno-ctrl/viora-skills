#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
post.py 1.0.0

Одна команда от темы до готового поста.

    python3 tools/post.py "бесплатные кредиты в Cursor" --rubric абуз

Цепочка жёсткая и одна на всех:
    1. search.py собирает факты и даёт бриф с номерами источников
    2. скелет рубрики задаёт форму и коридор длины
    3. ai.py пишет черновик строго по брифу и скелету
    4. lint_post.py --fix чинит механику, ставит хэштег и футер
    5. если линтер всё ещё ругается, модель получает список ошибок и переписывает
    6. score_post.py ставит оценку и говорит, публиковать или переписать

Слабая модель тоже справляется: думать ей не надо, все решения уже в брифе
и скелете, а механику за неё дочищает линтер. Без ключа отдаёт бриф и скелет,
чтобы дописать руками или чужим агентом.

Коды возврата: 0 пост готов, 1 пост не прошёл порог, 2 работать нечем.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

VERSION = "6.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ai  # noqa: E402
import search  # noqa: E402

MIN_SCORE = 70
AI_TRIES = 2

# Формы постов. Коридоры сухие нарочно: автор просил коротко, без воды.
SHAPES = {
    "абуз": {"low": 200, "high": 900, "points": (3, 6), "file": "reference/formats.md",
             "lead": "что дают и кому", "tail": "Как забрать:"},
    "сервисы": {"low": 200, "high": 700, "points": (3, 5), "file": "reference/formats.md",
                "lead": "что за сервис и зачем", "tail": "По факту:"},
    "гайд": {"low": 400, "high": 1200, "points": (4, 6), "file": "reference/matrix.md",
             "lead": "какая боль решается", "tail": "Итог:"},
    "релиз": {"low": 200, "high": 600, "points": (1, 3), "file": "reference/publish.md",
              "lead": "что выложил и зачем", "tail": "Где взять:"},
    "девлог": {"low": 250, "high": 700, "points": (1, 3), "file": "reference/examples.md",
               "lead": "что делал и что сломалось", "tail": "Дальше:"},
    "личное": {"low": 250, "high": 700, "points": (0, 3), "file": "reference/voice.md",
               "lead": "что случилось", "tail": "Вывод:"},
    "опрос": {"low": 150, "high": 400, "points": (2, 4), "file": "reference/formats.md",
              "lead": "что спрашиваю", "tail": "Варианты:"},
    "шортс": {"low": 200, "high": 450, "points": (1, 1), "file": "reference/publish.md",
              "lead": "про что ролик", "tail": "Смотреть:"},
    "лидмагнит": {"low": 250, "high": 600, "points": (1, 3), "file": "reference/publish.md",
                  "lead": "что внутри и зачем", "tail": "Забрать:"},
    "второй": {"low": 200, "high": 450, "points": (1, 2), "file": "reference/voice.md",
                "lead": "что сломалось", "tail": "Статус:"},
}
DEFAULT_RUBRIC = "абуз"
# По чему угадываем рубрику, если автор не сказал её вслух.
HINTS = (
    ("абуз", ("бесплатн", "халяв", "абуз", "промо", "триал", "trial", "кредит",
              "free", "скидк", "даром")),
    ("релиз", ("релиз", "выложил", "версия", "release", "обнова", "выкатил")),
    ("гайд", ("как ", "гаид", "гайд", "инструкц", "настройк", "пошагов")),
    ("девлог", ("девлог", "пилю", "делаю скилл", "работаю над")),
    ("шортс", ("шортс", "ролик", "shorts", "видео")),
    ("опрос", ("опрос", "голосован", "что выберете")),
    ("лидмагнит", ("подборк", "список сервис", "телеграф", "лидмагнит")),
    ("сервисы", ("сервис", "инструмент", "нейронк", "модель", "бот")),
)


def pick_rubric(topic, given=""):
    if given:
        return given if given in SHAPES else DEFAULT_RUBRIC
    low = (topic or "").lower()
    for name, words in HINTS:
        if any(word in low for word in words):
            return name
    return "сервисы"


# ------------------------------------------------------------------- скелет

def skeleton(topic, rubric, facts):
    """Скелет без воды: строка крючка, строка сути, пункты, закрывающая строка.

    Футер и хэштег не трогаем: их ставит lint_post.py --fix, чтобы истина
    жила в одном месте.
    """
    shape = SHAPES[rubric]
    low, high = shape["points"]
    count = min(max(len(facts), low), high) or low or 1
    rows = ["[Крючок одной строкой, без вводных слов]",
            "[%s, одна строка]" % shape["lead"], ""]
    for num in range(1, count + 1):
        if num <= len(facts):
            fact = facts[num - 1]
            rows.append("%d. [пункт одной строкой по факту %d: %s]"
                        % (num, num, search.trim(fact["text"], 90)))
        else:
            rows.append("%d. [пункт одной строкой]" % num)
    rows.append("")
    rows.append("%s [одна строка действия]" % shape["tail"])
    return "\n".join(rows)


RULES = [
    "Пиши от первого лица за автора канала, без слова ассистент и без редакции.",
    "Каждый пункт в одну строку. Никаких абзацев под пунктами.",
    "Цифры только из блока ФАКТЫ. Своих цифр не выдумывай ни одной.",
    "Если цифры под пункт нет, пиши пункт без цифры.",
    "Запрещены длинные тире и стрелки любого вида.",
    "Эмодзи ноль или одно на всё сообщение. Вместо смайла можно две скобки.",
    "Голых адресов не ставь. Ссылка только ярлыком вида ТЫК в квадратных скобках.",
    "Запрещены штампы: в современном мире, давайте разберёмся, в этой статье мы,",
    "    стоит отметить, важно понимать, погрузимся, революция, геймченджер.",
    "Не пиши вводный абзац про то, что сейчас будет текст. Сразу дело.",
    "Не ставь хэштеги и не ставь футер со ссылками: их добавит линтер сам.",
    "Ответ это только текст поста. Без пояснений, без заголовка Пост, без кавычек.",
]


# Требования линтера на языке модели. Дешевле выполнить сразу, чем ловить КОД
# ошибки на втором заходе: слабой модели второй заход часто не помогает.
# Списки совпадают с FORWARD_REQUIRED, FORWARD_WANTED и SOFT_FIRST_SCREEN в lint_post.py.
FORWARD_RUBRICS = {"абуз", "сервисы", "гайд", "лидмагнит", "второй", "шортс", "опрос"}
SOFT_SCREEN = {"личное", "девлог"}


def demands(rubric):
    rows = []
    if rubric in SOFT_SCREEN:
        rows.append("В первых двух строках лучше дать конкретный факт или срок.")
    else:
        rows.append("В первых 120 знаках обязательна цифра или срок: это превью и пуш.")
    rows.append("Нужна одна личная деталь: что сам делал, сколько времени ушло, "
                "с какого раза завелось.")
    if rubric in FORWARD_RUBRICS:
        rows.append("Нужна просьба переслать пост конкретному человеку, одной строкой.")
    if rubric == "абуз":
        rows.append("Если есть риск или срок жизни схемы, скажи об этом прямо и без пафоса.")
    return rows


def build_prompt(topic, rubric, brief, frame, extra=""):
    shape = SHAPES[rubric]
    rows = ["Задача: написать пост для телеграм-канала про: %s" % topic,
            "Рубрика: %s. Длина строго от %d до %d знаков."
            % (rubric, shape["low"], shape["high"]),
            "Пунктов от %d до %d." % shape["points"], "",
            "Правила, нарушать нельзя:"]
    rows.extend("  %s" % rule for rule in RULES)
    rows.extend(["", "Обязательно, иначе линтер завернёт пост:"])
    rows.extend("  %s" % row for row in demands(rubric))
    rows.extend(["", brief, "", "Скелет, держи его форму и замени квадратные скобки текстом:",
                 frame])
    if extra:
        rows.extend(["", extra])
    rows.extend(["", "Верни только готовый текст поста."])
    return "\n".join(rows)


# ----------------------------------------------------------------- инструменты

def run_tool(name, args, text=""):
    """Запуск соседнего скрипта скилла. Свою версию логики не плодим."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, os.path.join(HERE, name)] + list(args),
                          input=text, capture_output=True, text=True, env=env,
                          cwd=SKILL, timeout=180)
    return proc.returncode, proc.stdout, proc.stderr


def lint_fix(text, rubric, media=False):
    """Механика на откуп: тире, стрелки, хэштег и футер."""
    handle, path = tempfile.mkstemp(prefix="channel-post-", suffix=".txt")
    os.close(handle)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        args = [path, "--fix", "--rubric", rubric]
        if media:
            args.append("--media")
        run_tool("lint_post.py", args)
        with open(path, encoding="utf-8") as fh:
            fixed = fh.read()
        args = [path, "--json", "--rubric", rubric]
        if media:
            args.append("--media")
        code, out, _ = run_tool("lint_post.py", args)
        try:
            report = json.loads(out)
        except ValueError:
            report = {"issues": [], "raw": out}
        return fixed.strip(), code, report
    finally:
        if os.path.exists(path):
            os.remove(path)


def score(text, rubric, media=False, minimum=MIN_SCORE):
    # Имени файла тут быть не должно: оценщик читает stdin, а дефис считает файлом.
    args = ["--json", "--rubric", rubric, "--min", str(minimum), "--root", SKILL]
    if media:
        args.append("--media")
    code, out, _ = run_tool("score_post.py", args, text=text)
    try:
        return code, json.loads(out)
    except ValueError:
        return code, {"raw": out}


def errors_of(report):
    """Ошибки линтера в виде, который модель поймёт со второго захода."""
    rows = []
    for item in (report.get("errors") or report.get("issues") or []):
        if isinstance(item, str):
            rows.append(item)
            continue
        if not isinstance(item, dict):
            continue
        code = item.get("code") or ""
        body = (item.get("hint") or item.get("message") or item.get("text")
                or item.get("why") or item.get("what") or "")
        head = ("%s %s" % (code, body)).strip() if code else str(body).strip()
        line = item.get("line")
        rows.append("%s (строка %s)" % (head, line) if line else head)
    return [row for row in (r.strip() for r in rows) if row]


# --------------------------------------------------------------------- цепочка

def make(topic, rubric="", days=0, limit=8, media=False, use_ai=True,
         use_cache=True, minimum=MIN_SCORE, sources=()):
    rubric = pick_rubric(topic, rubric)
    payload = search.run_search(topic, profile="post", sources=sources, days=days,
                               limit=limit, use_cache=use_cache)
    brief = search.render_brief(payload)
    facts = payload.get("facts") or []
    frame = skeleton(topic, rubric, facts)
    out = {"topic": topic, "rubric": rubric, "brief": brief, "skeleton": frame,
           "facts": facts, "sources": payload.get("results") or [],
           "post": "", "score": None, "issues": [], "ai": False,
           "note": "", "min": minimum, "version": VERSION}

    conf = ai.settings()
    if not use_ai or not conf["ready"]:
        out["note"] = ("Ключа нет, поэтому отдаю бриф и скелет. Допиши руками или "
                       "положи ключ в secrets/ai.env, тогда пост соберётся сам.")
        if not use_ai:
            out["note"] = "Режим без модели: отдаю бриф и скелет."
        return out

    extra = ""
    draft = ""
    for attempt in range(AI_TRIES):
        prompt = build_prompt(topic, rubric, brief, frame, extra)
        try:
            draft = ai.ask(prompt, temperature=0.5 if attempt == 0 else 0.2,
                           max_tokens=1600)
        except Exception as exc:  # noqa: BLE001
            out["note"] = "Модель не ответила: %s" % str(exc)[:200]
            return out
        draft = strip_wrapper(draft)
        fixed, code, report = lint_fix(draft, rubric, media)
        bad = errors_of(report)
        out["ai"] = True
        out["post"] = fixed
        out["issues"] = bad
        if not bad:
            break
        extra = "\n".join(["Прошлый вариант линтер забраковал. Исправь именно это:"]
                          + ["  %s" % row for row in bad[:8]])

    if out["post"]:
        code, report = score(out["post"], rubric, media, minimum)
        out["score"] = report
        out["passed"] = code == 0
    return out


WRAPPERS = re.compile(r"^\s*```[a-zA-Z]*\s*|\s*```\s*$")
# Строка-подводка целиком, а не начало настоящей строки поста.
# Проверка по началу строки съедала первую строку самого поста.
META = re.compile(
    r"^\**\s*(?:конечно[,!]?\s*)?(?:вот|итак[,]?)?\s*"
    r"(?:твой\s+|ваш\s+)?(?:готовый\s+|финальный\s+|итоговый\s+)?"
    r"(?:пост|текст\s+поста|черновик|вариант)"
    r"(?:\s+для\s+[\w\-]+)?\s*[:.!]?\s*\**$", re.IGNORECASE)
META_EN = re.compile(r"^\**\s*(?:here\s+is|here's|sure[,!]?\s*here)\b[^\n]*$",
                     re.IGNORECASE)


def strip_wrapper(text):
    """Слабые модели любят обернуть пост в три кавычки или подписать себя."""
    text = (text or "").strip()
    text = WRAPPERS.sub("", text).strip()
    lines = text.split("\n")
    while lines:
        head = lines[0].strip()
        if not head or META.match(head) or META_EN.match(head):
            lines.pop(0)
            continue
        break
    return "\n".join(lines).strip()


def render(out):
    rows = []
    if out.get("post"):
        rows.append(out["post"])
        rows.append("")
        report = out.get("score") or {}
        total = report.get("total", report.get("score"))
        if total is not None:
            rows.append("Оценка: %s из 100, порог %s, длина %d знаков"
                        % (total, out.get("min", MIN_SCORE), len(out["post"])))
            if report.get("verdict"):
                rows.append("Вердикт: %s" % report["verdict"])
            for part, notes in (report.get("notes") or {}).items():
                for note in notes or []:
                    rows.append("  %s: %s" % (part, note))
        if out.get("issues"):
            rows.append("Остались замечания линтера:")
            rows.extend("  %s" % row for row in out["issues"])
        if out.get("passed") is False:
            rows.append("Порог не взят. Смотри замечания выше и перепиши слабые пункты.")
        return "\n".join(rows)
    rows.append(out.get("brief", ""))
    rows.append("")
    rows.append("СКЕЛЕТ под рубрику %s (замени скобки текстом):" % out.get("rubric"))
    rows.append(out.get("skeleton", ""))
    if out.get("note"):
        rows.append("")
        rows.append(out["note"])
    return "\n".join(rows)


# ---------------------------------------------------------------------- тесты

GOOD_POST = "\n".join([
    "Забрал двести запросов бесплатно, делюсь схемой",
    "Сервис даёт лимит на месяц без карты, проверил сам, ушло десять минут.",
    "",
    "1. На бесплатном тарифе дают 200 запросов в месяц.",
    "2. Платный стоит 20 долларов в месяц, без скидок.",
    "3. Лимит жёсткий: 50 запросов в минуту и всё.",
    "",
    "Как забрать: регаем аккаунт, берём лимит, чекаем расход раз в неделю.",
    "Перешли другу, который платит за такое же из своего кармана.",
])


def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # Рубрика и форма
    ok("халява это абуз", pick_rubric("бесплатные кредиты в Cursor") == "абуз")
    ok("релиз угадан", pick_rubric("выложил релиз скилла") == "релиз")
    ok("ручная рубрика сильнее", pick_rubric("бесплатно", "гайд") == "гайд")
    ok("кривая рубрика падает в абуз", pick_rubric("тема", "чушь") == "абуз")
    ok("все рубрики с коридором",
       all(s["low"] < s["high"] for s in SHAPES.values()))
    ok("коридоры сухие", max(s["high"] for s in SHAPES.values()) <= 1200)

    frame = skeleton("тема", "абуз", [{"text": "дают 200 запросов в месяц", "src": 1}])
    ok("в скелете есть крючок", "Крючок" in frame)
    ok("в скелете есть нумерация", "\n1. " in frame)
    ok("в скелете есть закрытие", "Как забрать:" in frame)
    ok("факт попал в скелет", "200 запросов" in frame)
    ok("скелет без футера", "GITHUB" not in frame)
    ok("скелет без хэштега", "#" not in frame)

    prompt = build_prompt("тема", "абуз", "БРИФ: тема", frame)
    ok("в задании есть коридор", "200 до 900" in prompt)
    ok("в задании есть запрет цифр", "выдумывай" in prompt)
    ok("в задании есть запрет футера", "линтер сам" in prompt)
    ok("в задании нет длинных тире", not any(d in prompt for d in ai.DASHES[:4]))
    ok("в задании требуют пересылку", "переслать" in prompt)
    ok("в задании требуют личную деталь", "личная деталь" in prompt)
    ok("в задании требуют цифру на первом экране", "120 знаках" in prompt)
    ok("у личного первый экран мягче",
       "120 знаках" not in build_prompt("тема", "личное", "БРИФ", frame))
    ok("у личного пересылку не требуют",
       "переслать" not in build_prompt("тема", "личное", "БРИФ", frame))

    # Снятие обёрток модели
    ok("три кавычки снялись", strip_wrapper("```\nтекст\n```") == "текст")
    ok("предисловие снялось",
       strip_wrapper("Вот готовый пост:\nТекст поста тут").startswith("Текст"))

    # Полная цепочка без сети и без ключа
    old_search, old_ai = search.FETCH, ai.FETCH
    keep = {}
    for name in ("CHANNEL_AI_PROVIDER", "CHANNEL_AI_KEY", "CHANNEL_CACHE", "CHANNEL_SECRETS"):
        keep[name] = os.environ.get(name)
    try:
        cache = tempfile.mkdtemp(prefix="channel-cache-")
        os.environ["CHANNEL_CACHE"] = cache
        os.environ["CHANNEL_SECRETS"] = os.path.join(cache, "nope")
        os.environ.pop("CHANNEL_AI_KEY", None)
        search.FETCH = search.fake_fetch

        out = make("Cursor бесплатный тариф", use_ai=False, use_cache=False)
        ok("без модели есть бриф", "ФАКТЫ" in out["brief"])
        ok("без модели есть скелет", bool(out["skeleton"]))
        ok("без модели честная пометка", "бриф" in out["note"])
        ok("без модели поста нет", not out["post"])
        ok("факты собрались", len(out["facts"]) >= 1)
        ok("вывод без модели читаем", "СКЕЛЕТ" in render(out))

        # С моделью: подставляем готовый пост и гоняем всю цепочку
        os.environ["CHANNEL_AI_KEY"] = "test-key"
        os.environ["CHANNEL_AI_PROVIDER"] = "openrouter"
        asked = {}

        def fake_ai(url, payload, headers, timeout=90):
            asked["payload"] = payload
            return json.dumps({"choices": [{"message": {"content": GOOD_POST}}]})

        ai.FETCH = fake_ai
        out = make("Cursor бесплатный тариф", rubric="абуз", use_cache=False)
        post = out["post"]
        ok("пост собрался", bool(post))
        ok("модель получила бриф",
           "ИСТОЧНИКИ" in asked["payload"]["messages"][-1]["content"])
        ok("модель получила свод правил",
           asked["payload"]["messages"][0]["role"] == "system")
        ok("линтер добавил футер", "GITHUB" in post)
        ok("линтер добавил хэштег", "#" in post)
        ok("в посте нет длинных тире", not any(d in post for d in ai.DASHES[:4]))
        ok("в посте нет стрелок", not any(a in post for a in ai.ARROWS[:4]))
        ok("ошибок линтера нет", not out["issues"])
        ok("оценка посчитана", isinstance(out["score"], dict) and bool(out["score"]))
        ok("длина в коридоре", 150 <= len(post) <= 1400)
        ok("вывод с оценкой", "Оценка" in render(out))

        # Модель упала: цепочка не падает, а говорит правду
        def dead_ai(url, payload, headers, timeout=90):
            raise IOError("HTTP 401 ключ не подходит")

        ai.FETCH = dead_ai
        out = make("Cursor бесплатный тариф", use_cache=False)
        ok("падение модели не роняет цепочку", out["post"] == "")
        ok("падение объяснено", "401" in out["note"])
        ok("бриф всё равно отдали", "ФАКТЫ" in out["brief"])

        # Модель прислала грязь: линтер обязан вычистить механику
        dirty = GOOD_POST.replace("делюсь схемой", "делюсь \u2014 схемой \u2192 тут")

        def dirty_ai(url, payload, headers, timeout=90):
            return json.dumps({"choices": [{"message": {"content": dirty}}]})

        ai.FETCH = dirty_ai
        out = make("Cursor бесплатный тариф", rubric="абуз", use_cache=False)
        ok("грязный черновик вычищен",
           out["post"] and not any(d in out["post"] for d in ai.DASHES[:4]))
        ok("стрелка вычищена", "\u2192" not in out["post"])
    finally:
        search.FETCH, ai.FETCH = old_search, old_ai
        for name, value in keep.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    bad = 0
    for name, good in checks:
        print("  %s  %s" % ("ок " if good else "НЕТ", name))
        bad += 0 if good else 1
    print("")
    print("post.py: проверок %d, провалов %d" % (len(checks), bad))
    return 1 if bad else 0


# ----------------------------------------------------------------------- вход

def main(argv=None):
    parser = argparse.ArgumentParser(description="Пост одной командой")
    parser.add_argument("topic", nargs="*", help="тема поста")
    parser.add_argument("--rubric", default="", help="абуз, сервисы, гайд и так далее")
    parser.add_argument("--days", type=int, default=0, help="только свежее за N дней")
    parser.add_argument("--limit", type=int, default=8, help="сколько источников брать")
    parser.add_argument("--source", default="", help="свой список источников через запятую")
    parser.add_argument("--media", action="store_true", help="пост идёт с фото")
    parser.add_argument("--no-ai", action="store_true", help="только бриф и скелет")
    parser.add_argument("--no-cache", action="store_true", help="не брать из кэша")
    parser.add_argument("--min", type=int, default=MIN_SCORE, dest="minimum")
    parser.add_argument("--out", default="", help="куда записать пост")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print("post.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()

    topic = " ".join(args.topic).strip()
    if not topic:
        print(__doc__.strip())
        return 2

    sources = tuple(s.strip() for s in args.source.split(",") if s.strip())
    out = make(topic, rubric=args.rubric, days=args.days, limit=args.limit,
               media=args.media, use_ai=not args.no_ai,
               use_cache=not args.no_cache, minimum=args.minimum, sources=sources)
    body = out["post"] or render(out)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(body.rstrip() + "\n")
        except OSError as exc:
            print("Не смог записать: %s" % exc)
            return 2
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render(out))
    if not out["post"]:
        return 2 if not out.get("brief") else 0
    return 0 if out.get("passed", True) else 1


if __name__ == "__main__":
    sys.exit(main())
