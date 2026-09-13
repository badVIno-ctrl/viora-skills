#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_chat.py 1.0.0
Линтер обычной речи агента, а не поста. Нужен, чтобы в ответах в чате
не было длинных тире и нейронных связок.

Запуск:
    python3 tools/lint_chat.py --text "мой ответ"
    python3 tools/lint_chat.py черновик.txt --json
    echo "текст" | python3 tools/lint_chat.py
    python3 tools/lint_chat.py --text "10 \u2014 20" --fix

Код возврата: 0 если ошибок нет, 1 если есть ERROR.
Сторонних библиотек не нужно.
"""

import argparse
import importlib.util
import json
import os
import re
import sys

VERSION = "6.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))

EMDASHES = "\u2014\u2013\u2015\u2012\u2212"
ARROWS = "\u2192\u2190\u21d2\u2022\u203a\u203b"
DEMO_MARK = "dash-demo"

# Запасные списки на случай, если lint_post.py рядом не нашлся.
FALLBACK_BANNED = [
    "революционн", "геймченджер", "мастхвот", "уникальная возможность",
    "в современном мире", "в эпоху цифровизации", "погрузитесь в мир",
    "откройте для себя", "не упустите шанс", "поднимите на новый уровень",
    "бесценный опыт", "впечатляющие результаты", "стоит отметить",
    "важно понимать, что", "давайте разберёмся", "итак, друзья",
]
FALLBACK_SLOP = [
    r"не просто [\w\s]{2,25}, а ",
    r"это не [\w\s]{2,25}, это ",
    r"в мире [\w]{3,20} важно",
    r"открывает новые горизонты",
    r"ключ к успеху",
    r"в заключение стоит",
    r"погружаемся глубже",
]
FALLBACK_HINTS = {
    "E-EMDASH": "Замени длинное тире на точку, запятую или дефис.",
    "E-ARROW": "Убери стрелки и точки-кружки, пиши словами.",
    "E-BANNED-WORD": "Слово из стоп-листа, скажи проще.",
    "E-SLOP-CONSTRUCT": "Разбей на два коротких предложения.",
    "W-SENT-LONG": "Разбей длинное предложение.",
    "W-TRIPLE-LIST": "Сломай тройку с нарастанием.",
    "W-RHETORIC-END": "Убери вопрос в конце, скажи утверждением.",
    "W-HEDGE": "Убери слова-подушки: «возможно», «в целом», «как упоминалось».",
    "W-EMOJI": "В чате смайлы не нужны.",
}

HEDGES = [
    "возможно, стоит", "в целом можно сказать", "как упоминалось выше",
    "стоит отметить", "надеюсь, это поможет", "если у вас есть ещё вопросы",
    "давайте разберёмся",
]
EMOJI = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf\u2b00-\u2bff]")


def load_post_linter():
    """Тянем словари из lint_post.py, чтобы не держать два разных стоп-листа."""
    path = os.path.join(HERE, "lint_post.py")
    if not os.path.exists(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("channel_lint_post", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def normalize_slop(raw):
    """В lint_post.py слоп лежит парами (регулярка, текст). Запасной список простые строки."""
    out = []
    for item in raw or []:
        if isinstance(item, (tuple, list)) and item:
            pattern = item[0]
            note = item[1] if len(item) > 1 else ""
        else:
            pattern, note = item, ""
        if not isinstance(pattern, str):
            pattern = getattr(pattern, "pattern", None)
        if isinstance(pattern, str):
            out.append((pattern, note))
    return out


POST = load_post_linter()
BANNED = [word for word in (getattr(POST, "BANNED", None) or FALLBACK_BANNED)
          if isinstance(word, str)]
SLOP = normalize_slop(getattr(POST, "SLOP", None)) or normalize_slop(FALLBACK_SLOP)


def hint_for(code):
    if POST is not None and hasattr(POST, "HINTS") and code in POST.HINTS:
        return POST.HINTS[code]
    return FALLBACK_HINTS.get(code, "Скажи проще и конкретнее.")


def strip_code(text):
    """Код и пути не трогаем: там символы часть синтаксиса."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part for part in parts if part.strip()]


def add(issues, level, code, message):
    issues.append({"level": level, "code": code, "message": message})


def lint(text):
    issues = []
    if not text.strip():
        add(issues, "ERROR", "E-EMPTY", "пустой текст")
        return issues

    prose = strip_code(text)
    low = prose.lower()

    bad_lines = []
    for number, line in enumerate(prose.split("\n"), 1):
        if DEMO_MARK in line:
            continue
        if any(char in line for char in EMDASHES):
            bad_lines.append(number)
    if bad_lines:
        add(issues, "ERROR", "E-EMDASH",
            "длинное тире в строках %s" % ", ".join(str(n) for n in bad_lines[:8]))

    if any(char in prose for char in ARROWS):
        add(issues, "ERROR", "E-ARROW", "стрелки или точки-кружки в тексте")

    for word in BANNED:
        if word.lower() in low:
            add(issues, "ERROR", "E-BANNED-WORD", "слово из стоп-листа: %s" % word)

    for pattern, note in SLOP:
        try:
            found = re.search(pattern, low, re.M)
        except re.error:
            continue
        if found:
            add(issues, "ERROR", "E-SLOP-CONSTRUCT",
                note or ("нейронная связка: %s" % found.group(0).strip()[:50]))

    for hedge in HEDGES:
        if hedge in low:
            add(issues, "WARN", "W-HEDGE", "слово-подушка: %s" % hedge)

    for row in sentences(prose):
        if len(row.split()) > 28:
            add(issues, "WARN", "W-SENT-LONG",
                "предложение из %d слов: %s..." % (len(row.split()), row.strip()[:40]))
            break

    for triple in re.findall(
        r"([\w][\w\s-]{2,40}), ([\w][\w\s-]{2,40}) и ([\w][\w\s-]{2,40})", prose
    ):
        sizes = [len(part.strip()) for part in triple]
        if sizes[0] < sizes[1] < sizes[2]:
            add(issues, "WARN", "W-TRIPLE-LIST",
                "тройное перечисление с нарастанием")
            break

    tail = [row for row in prose.strip().split("\n") if row.strip()]
    if tail and tail[-1].strip().endswith("?") and len(tail[-1].split()) > 3:
        add(issues, "WARN", "W-RHETORIC-END", "ответ заканчивается вопросом")

    smiles = len(EMOJI.findall(prose))
    if smiles > 2:
        add(issues, "WARN", "W-EMOJI", "смайлов %d: в чате они не нужны" % smiles)

    return issues


def fix(text):
    """Автозамена тире. Между цифрами дефис, между словами дефис с пробелами."""
    out = []
    for index, char in enumerate(text):
        if char not in EMDASHES:
            out.append(char)
            continue
        before = text[index - 1] if index else ""
        after = text[index + 1] if index + 1 < len(text) else ""
        if before.isdigit() and after.isdigit():
            out.append("-")
        elif before == " " and after == " ":
            out.append("-")
        else:
            out.append("-")
    result = "".join(out)
    result = re.sub(r"\s+-\s+", " - ", result)
    return result


def report(issues, strict, as_json):
    errors = [item for item in issues if item["level"] == "ERROR"]
    warns = [item for item in issues if item["level"] == "WARN"]
    if strict:
        errors, warns = errors + warns, []

    if as_json:
        print(json.dumps({
            "version": VERSION,
            "clean": not errors and not warns,
            "errorCount": len(errors),
            "warnCount": len(warns),
            "errors": [{"code": i["code"], "message": i["message"],
                        "hint": hint_for(i["code"])} for i in errors],
            "warns": [{"code": i["code"], "message": i["message"],
                       "hint": hint_for(i["code"])} for i in warns],
        }, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    if errors:
        print("ERROR (%d) - так отвечать нельзя:" % len(errors))
        for item in errors:
            print("  - [%s] %s" % (item["code"], item["message"]))
            print("      как исправить: %s" % hint_for(item["code"]))
    if warns:
        print("WARN (%d) - посмотреть глазами:" % len(warns))
        for item in warns:
            print("  - [%s] %s" % (item["code"], item["message"]))
    if not errors and not warns:
        print("Чисто. Так можно отвечать.")
    elif not errors:
        print("ERROR нет.")
    return 1 if errors else 0


def selftest():
    fails = []
    dash = "Наш скилл \u2014 это инструмент."
    codes = [item["code"] for item in lint(dash)]
    if "E-EMDASH" not in codes:
        fails.append("длинное тире не поймано")
    if "E-EMDASH" in [i["code"] for i in lint("Строка с \u2014 и меткой dash-demo")]:
        fails.append("строка с меткой dash-demo не должна ругаться")
    if "E-EMDASH" in [i["code"] for i in lint("Вот код: `a \u2014 b`")]:
        fails.append("внутри кода тире не считаем")
    clean = lint("Сделал два файла. Гоню тесты, потом отдам зип.")
    if clean:
        fails.append("чистый ответ оказался грязным: %s" % clean)
    fixed = fix("От 10\u201320 минут \u2014 и готово.")
    if any(char in fixed for char in EMDASHES):
        fails.append("автозамена оставила тире")
    if "10-20" not in fixed:
        fails.append("диапазон цифр должен стать 10-20, а вышло: %s" % fixed)
    for line in fails:
        print("SELFTEST ПРОВАЛ: %s" % line)
    if not fails:
        print("SELFTEST: линтер речи в порядке")
    return 1 if fails else 0


def main():
    parser = argparse.ArgumentParser(description="линтер ответов агента в чате")
    parser.add_argument("file", nargs="?", help="файл с текстом, без аргумента читает stdin")
    parser.add_argument("--text", help="текст строкой")
    parser.add_argument("--fix", action="store_true", help="напечатать текст без тире")
    parser.add_argument("--strict", action="store_true", help="предупреждения становятся ошибками")
    parser.add_argument("--json", action="store_true", dest="as_json", help="машинный вывод")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if args.text is not None:
        text = args.text
    elif args.file:
        with open(args.file, encoding="utf-8") as handle:
            text = handle.read()
    else:
        text = sys.stdin.read()

    if args.fix:
        print(fix(text))
        return 0

    return report(lint(text), args.strict, args.as_json)


if __name__ == "__main__":
    sys.exit(main())
