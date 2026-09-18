#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Память скилла: цифры и лог постов. Версия 1.0.

Зачем он нужен. До V5 файлы memory/ надо было обновлять руками, поэтому их не
обновлял никто. Линтер читал used-greetings.md и ругался, а дописать туда строку
было некому. Теперь память пишет скрипт, а модель только вызывает команду.

Команды:
    python3 tools/memory.py show
    python3 tools/memory.py check-greeting "Вечер в хату"
    python3 tools/memory.py add-greeting "Здарова, бандиты"
    python3 tools/memory.py add-post --type абуз --topic "пак абузов" --services "Notion" --url "..."
    python3 tools/memory.py add-metric --url "..." --views 165 --reactions 3 --comments 0
    python3 tools/memory.py --selftest

Флаги:
    --root DIR   работать с другой копией скилла, нужно тестам
    --dry-run    показать строку и ничего не писать
    --json       машинный вывод

Код возврата: 0 порядок, 1 проблема. У check-greeting 1 значит приветствие занято.
Сторонних библиотек не нужно, только Python 3.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

VERSION = "6.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

GREETINGS_SECTION = "## Вышло в канале"
MEMELOG_SECTION = "## Вышло в канале"
POSTLOG_SECTION = "## 2026"
METRICS_SECTION = "## Замеры постов"
METRICS_HEADER = (
    "| Дата | Ссылка | Просмотры | Реакции | Комментарии | Заметка |"
)
METRICS_RULE = "|---|---|---|---|---|---|"

SIMILAR_LIMIT = 0.6


def paths(root):
    memory = os.path.join(root, "memory")
    return {
        "memory": memory,
        "greetings": os.path.join(memory, "used-greetings.md"),
        "memes": os.path.join(memory, "meme-log.md"),
        "postlog": os.path.join(memory, "post-log.md"),
        "metrics": os.path.join(memory, "metrics.md"),
        "decisions": os.path.join(memory, "decisions.md"),
    }


def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def write(path, text):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def today():
    return datetime.date.today().isoformat()


def norm(text):
    """Приветствия сравниваем без регистра, знаков и лишних пробелов."""
    low = text.lower().replace("\u0451", "е")
    low = re.sub(r"[^\w\s]", " ", low, flags=re.UNICODE)
    return " ".join(low.split())


def tokens(text):
    return set(norm(text).split())


def jaccard(left, right):
    first, second = tokens(left), tokens(right)
    if not first or not second:
        return 0.0
    return len(first & second) / float(len(first | second))


def parse_rows(text, section):
    """Строки раздела: от его заголовка до следующего заголовка уровня два."""
    lines = text.split("\n")
    out = []
    inside = False
    for line in lines:
        if line.strip() == section:
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside and line.strip():
            out.append(line.rstrip())
    return out


def insert_into_section(text, section, row, header_rows=None):
    """Дописать строку в конец раздела. Раздел создаётся, если его нет."""
    lines = text.split("\n")
    if section not in [line.strip() for line in lines]:
        tail = ["", section, ""]
        if header_rows:
            tail.extend(header_rows)
        tail.append(row)
        tail.append("")
        body = "\n".join(lines).rstrip("\n")
        return body + "\n" + "\n".join(tail)

    start = next(i for i, line in enumerate(lines) if line.strip() == section)
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break

    last = start
    for index in range(start + 1, end):
        if lines[index].strip():
            last = index
    if last == start and header_rows:
        block = [""] + list(header_rows) + [row]
        lines[start + 1 : start + 1] = block
    else:
        lines.insert(last + 1, row)
    return "\n".join(lines)


def load_greetings(root):
    rows = parse_rows(read(paths(root)["greetings"]), GREETINGS_SECTION)
    out = []
    for row in rows:
        if "|" not in row:
            continue
        date, _, text = row.partition("|")
        text = text.strip()
        if text:
            out.append({"date": date.strip(), "text": text})
    return out


def check_greeting(root, greeting):
    used = load_greetings(root)
    target = norm(greeting)
    for item in used:
        if norm(item["text"]) == target:
            return {
                "status": "used",
                "match": item["text"],
                "date": item["date"],
                "score": 1.0,
            }
    best, score = None, 0.0
    for item in used:
        value = jaccard(greeting, item["text"])
        if value > score:
            best, score = item, value
    if best and score >= SIMILAR_LIMIT:
        return {
            "status": "similar",
            "match": best["text"],
            "date": best["date"],
            "score": round(score, 2),
        }
    return {"status": "free", "match": None, "date": None, "score": round(score, 2)}


def add_greeting(root, greeting, dry_run=False, date=None):
    check = check_greeting(root, greeting)
    if check["status"] == "used":
        return {"written": False, "reason": "уже в списке", "check": check}
    row = "%s | %s" % (date or today(), greeting.strip())
    path = paths(root)["greetings"]
    text = read(path) or "# Использованные приветствия\n\n%s\n" % GREETINGS_SECTION
    updated = insert_into_section(text, GREETINGS_SECTION, row)
    if not dry_run:
        write(path, updated)
    return {"written": not dry_run, "row": row, "check": check}


def load_memes(root):
    """Журнал шуток: та же разметка, что у приветствий, плюс шаблон в середине."""
    rows = parse_rows(read(paths(root)["memes"]), MEMELOG_SECTION)
    out = []
    for row in rows:
        if "|" not in row:
            continue
        parts = [part.strip() for part in row.split("|")]
        if len(parts) < 3:
            parts = [parts[0], "", parts[-1]]
        if parts[2]:
            out.append({"date": parts[0], "template": parts[1], "text": parts[2]})
    return out


def check_meme(root, joke, template=None):
    """Шутка или шаблон уже выходили: проверяем до съёмки, а не после."""
    used = load_memes(root)
    target = norm(joke)
    for item in used:
        if norm(item["text"]) == target:
            return {"status": "used", "match": item["text"],
                    "template": item["template"], "date": item["date"], "score": 1.0}
    if template:
        want = norm(template)
        for item in used:
            if want and norm(item["template"]) == want:
                return {"status": "template", "match": item["text"],
                        "template": item["template"], "date": item["date"], "score": 1.0}
    best, score = None, 0.0
    for item in used:
        value = jaccard(joke, item["text"])
        if value > score:
            best, score = item, value
    if best and score >= SIMILAR_LIMIT:
        return {"status": "similar", "match": best["text"],
                "template": best["template"], "date": best["date"], "score": round(score, 2)}
    return {"status": "free", "match": None, "template": None,
            "date": None, "score": round(score, 2)}


def add_meme(root, joke, template="", dry_run=False, date=None):
    check = check_meme(root, joke, template)
    if check["status"] in ("used", "template"):
        return {"written": False, "reason": "уже в журнале", "check": check}
    row = "%s | %s | %s" % (
        date or today(),
        (template or "без шаблона").strip(),
        joke.strip(),
    )
    path = paths(root)["memes"]
    text = read(path) or "# Использованные шутки и шаблоны\n\n%s\n" % MEMELOG_SECTION
    updated = insert_into_section(text, MEMELOG_SECTION, row)
    if not dry_run:
        write(path, updated)
    return {"written": not dry_run, "row": row, "check": check}


def add_post(root, kind, topic, services="", url="", dry_run=False, date=None):
    row = "%s | %s | %s | %s | %s" % (
        date or today(),
        kind.strip(),
        topic.strip(),
        (services or "-").strip(),
        (url or "-").strip(),
    )
    path = paths(root)["postlog"]
    text = read(path) or "# Журнал постов\n\n%s\n" % POSTLOG_SECTION
    updated = insert_into_section(text, POSTLOG_SECTION, row)
    if not dry_run:
        write(path, updated)
    return {"written": not dry_run, "row": row}


def add_metric(
    root, url="", views=0, reactions=0, comments=0, note="", dry_run=False, date=None
):
    row = "| %s | %s | %d | %d | %d | %s |" % (
        date or today(),
        (url or "-").strip(),
        int(views),
        int(reactions),
        int(comments),
        (note or "-").strip(),
    )
    path = paths(root)["metrics"]
    text = read(path) or "# Метрики канала\n"
    updated = insert_into_section(
        text, METRICS_SECTION, row, header_rows=[METRICS_HEADER, METRICS_RULE]
    )
    if not dry_run:
        write(path, updated)
    return {"written": not dry_run, "row": row}


def load_metrics(root):
    """Базовые цифры и замеры. Нужно score_post.py, чтобы судить на своих числах."""
    text = read(paths(root)["metrics"])
    out = {"subscribers": None, "reach": None, "reactions": None, "samples": []}
    for line in text.split("\n"):
        low = line.lower()
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 2:
            if "подписчик" in low and out["subscribers"] is None:
                digits = re.findall(r"\d+", cells[1])
                if digits:
                    out["subscribers"] = int(digits[0])
            elif "охват" in low and out["reach"] is None and "процен" not in low:
                digits = [int(value) for value in re.findall(r"\d+", cells[1])]
                if len(digits) >= 2:
                    out["reach"] = (digits[0], digits[1])
            elif "реакци" in low and out["reactions"] is None:
                digits = [int(value) for value in re.findall(r"\d+", cells[1])]
                if len(digits) >= 2:
                    out["reactions"] = (digits[0], digits[1])
        if len(cells) == 6 and re.match(r"^\d{4}-\d{2}-\d{2}$", cells[0]):
            try:
                out["samples"].append(
                    {
                        "date": cells[0],
                        "url": cells[1],
                        "views": int(cells[2]),
                        "reactions": int(cells[3]),
                        "comments": int(cells[4]),
                        "note": cells[5],
                    }
                )
            except ValueError:
                continue
    return out


def show(root, limit=5):
    greetings = load_greetings(root)
    posts = [
        row
        for row in parse_rows(read(paths(root)["postlog"]), POSTLOG_SECTION)
        if "|" in row
    ]
    metrics = load_metrics(root)
    memes = load_memes(root)
    return {
        "greetings_total": len(greetings),
        "greetings_last": [item["text"] for item in greetings[-limit:]],
        "memes_total": len(memes),
        "memes_last": ["%s | %s" % (item["template"], item["text"]) for item in memes[-limit:]],
        "posts_total": len(posts),
        "posts_last": posts[-limit:],
        "subscribers": metrics["subscribers"],
        "reach": metrics["reach"],
        "reactions": metrics["reactions"],
        "samples_total": len(metrics["samples"]),
        "samples_last": metrics["samples"][-limit:],
    }


def print_show(data):
    print("Память скилла")
    if data["subscribers"]:
        print("  Подписчиков: %s" % data["subscribers"])
    if data["reach"]:
        print("  Охват хорошего поста: %d-%d" % data["reach"])
    if data["reactions"]:
        print("  Реакций на пост: %d-%d" % data["reactions"])
    print("  Приветствий занято: %d" % data["greetings_total"])
    for item in data["greetings_last"]:
        print("    занято: %s" % item)
    print("  Шуток в журнале мемов: %d" % data.get("memes_total", 0))
    for item in data.get("memes_last", []):
        print("    было: %s" % item)
    print("  Постов в журнале: %d" % data["posts_total"])
    for item in data["posts_last"]:
        print("    %s" % item)
    print("  Замеров постов: %d" % data["samples_total"])
    for item in data["samples_last"]:
        print(
            "    %s просмотров %d, реакций %d: %s"
            % (item["date"], item["views"], item["reactions"], item["note"])
        )


def selftest():
    """Прогнать все команды на временной копии памяти."""
    failed = 0
    checks = []
    root = tempfile.mkdtemp(prefix="channel-memory-")
    try:
        os.makedirs(os.path.join(root, "memory"))
        write(
            paths(root)["greetings"],
            "# Использованные приветствия\n\n"
            + GREETINGS_SECTION
            + "\n\n2026-07-31 | Вечер в хату, товарищи\n",
        )
        write(
            paths(root)["postlog"],
            "# Журнал постов\n\n" + POSTLOG_SECTION + "\n\n2026-08 | абуз | старое | - | -\n",
        )
        write(
            paths(root)["metrics"],
            "# Метрики канала\n\n## База\n\n"
            "| Показатель | Значение |\n|---|---|\n"
            "| Подписчиков | 260 |\n"
            "| Типичный охват хорошего поста | 165-386 |\n"
            "| Реакций на пост | 1-5 |\n",
        )

        got = check_greeting(root, "Вечер в хату, товарищи!")
        checks.append(("точное совпадение ловится", got["status"] == "used"))

        got = check_greeting(root, "Вечер в хату товарищи арестанты")
        checks.append(("похожее ловится", got["status"] == "similar"))

        got = check_greeting(root, "Здарова, бандиты")
        checks.append(("новое свободно", got["status"] == "free"))

        add_greeting(root, "Здарова, бандиты", date="2026-08-21")
        got = check_greeting(root, "Здарова, бандиты")
        checks.append(("после записи стало занято", got["status"] == "used"))

        result = add_greeting(root, "Здарова, бандиты")
        checks.append(("дважды не пишется", result["written"] is False))

        before = len(parse_rows(read(paths(root)["greetings"]), GREETINGS_SECTION))
        add_greeting(root, "Сухарики в доме", dry_run=True)
        after = len(parse_rows(read(paths(root)["greetings"]), GREETINGS_SECTION))
        checks.append(("dry-run не пишет", before == after))

        add_post(root, "гайд", "новый гайд", "Notion", "https://t.me/x/1", date="2026-08-21")
        rows = parse_rows(read(paths(root)["postlog"]), POSTLOG_SECTION)
        checks.append(("пост дописался вниз", rows[-1].startswith("2026-08-21 | гайд")))
        checks.append(("старые строки целы", any("старое" in row for row in rows)))

        add_metric(
            root,
            url="https://t.me/x/1",
            views=165,
            reactions=3,
            comments=0,
            note="польза внутри",
            date="2026-08-21",
        )
        add_metric(
            root,
            url="https://t.me/x/2",
            views=116,
            reactions=1,
            comments=0,
            note="тизер со ссылкой",
            date="2026-08-21",
        )
        metrics = load_metrics(root)
        checks.append(("базовые цифры читаются", metrics["subscribers"] == 260))
        checks.append(("охват читается", metrics["reach"] == (165, 386)))
        checks.append(("два замера на месте", len(metrics["samples"]) == 2))
        checks.append(
            ("замер читается целиком", metrics["samples"][0]["views"] == 165)
        )

        data = show(root)
        checks.append(("show видит всё", data["posts_total"] >= 2 and data["samples_total"] == 2))

        for name, ok in checks:
            if ok:
                print("PASS %s" % name)
            else:
                print("FAIL %s" % name)
                failed += 1
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("Итого: %d проверок, провалилось %d" % (len(checks), failed))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description="Память скилла")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["show", "check-greeting", "add-greeting", "check-meme", "add-meme",
                 "add-post", "add-metric"],
        help="что сделать с памятью",
    )
    parser.add_argument("value", nargs="?", help="текст для команд про приветствие")
    parser.add_argument("--root", default=SKILL, help="корень скилла")
    parser.add_argument("--type", dest="kind", help="рубрика поста")
    parser.add_argument("--topic", help="тема поста")
    parser.add_argument("--template", default="", help="шаблон мема")
    parser.add_argument("--services", default="", help="сервисы через запятую")
    parser.add_argument("--url", default="", help="ссылка на пост")
    parser.add_argument("--views", type=int, default=0, help="просмотры")
    parser.add_argument("--reactions", type=int, default=0, help="реакции")
    parser.add_argument("--comments", type=int, default=0, help="комментарии")
    parser.add_argument("--note", default="", help="заметка к замеру")
    parser.add_argument("--date", help="дата вида 2026-08-21, по умолчанию сегодня")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "show":
        data = show(args.root)
        if args.as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print_show(data)
        return 0

    if args.command == "check-greeting":
        if not args.value:
            print("нужен текст приветствия")
            return 1
        data = check_greeting(args.root, args.value)
        if args.as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif data["status"] == "used":
            print("ЗАНЯТО. Такое уже выходило %s. Придумай другое." % data["date"])
        elif data["status"] == "similar":
            print(
                "ПОХОЖЕ на %s (%s). Смени слова."
                % (data["match"], data["date"])
            )
        else:
            print("СВОБОДНО. После выхода поста запиши через add-greeting.")
        return 1 if data["status"] == "used" else 0

    if args.command == "add-greeting":
        if not args.value:
            print("нужен текст приветствия")
            return 1
        data = add_greeting(args.root, args.value, args.dry_run, args.date)
        if args.as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif data["written"]:
            print("Записал: %s" % data["row"])
        elif args.dry_run:
            print("dry-run, записалось бы: %s" % data["row"])
        else:
            print("Не записал: %s" % data.get("reason", "причина неясна"))
        return 0

    if args.command == "check-meme":
        if not args.value:
            print("нужен текст шутки")
            return 1
        data = check_meme(args.root, args.value, args.template)
        if args.as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif data["status"] == "used":
            print("ЗАНЯТО. Такая шутка уже выходила %s. Придумай другую." % data["date"])
        elif data["status"] == "template":
            print("ШАБЛОН ЗАНЯТ. Он уже был %s: %s" % (data["date"], data["match"]))
        elif data["status"] == "similar":
            print("ПОХОЖЕ на %s (%s). Смени шутку." % (data["match"], data["date"]))
        else:
            print("СВОБОДНО. После выхода ролика запиши через add-meme.")
        return 1 if data["status"] in ("used", "template") else 0

    if args.command == "add-meme":
        if not args.value:
            print("нужен текст шутки")
            return 1
        data = add_meme(args.root, args.value, args.template, args.dry_run, args.date)
        if args.as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif data["written"]:
            print("Записал: %s" % data["row"])
        elif args.dry_run:
            print("dry-run, записалось бы: %s" % data["row"])
        else:
            print("Не записал: %s" % data.get("reason", "причина неясна"))
        return 0

    if args.command == "add-post":
        if not args.kind or not args.topic:
            print("нужны --type и --topic")
            return 1
        data = add_post(
            args.root, args.kind, args.topic, args.services, args.url, args.dry_run, args.date
        )
        if args.as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(("Записал: " if data["written"] else "dry-run: ") + data["row"])
        return 0

    if args.command == "add-metric":
        data = add_metric(
            args.root,
            args.url,
            args.views,
            args.reactions,
            args.comments,
            args.note,
            args.dry_run,
            args.date,
        )
        if args.as_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(("Записал: " if data["written"] else "dry-run: ") + data["row"])
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
