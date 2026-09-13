#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Линтер статьи на telegra.ph. Подпись и бренд берутся из профиля.

Ловит то, что ломает статью: чужая подпись автора, слитые в один абзац
метки пункта, общий ликбез про риски, приглашение в канал внутри
текста, длинное тире и заголовки не того уровня.

Запуск:
    python3 tools/lint_article.py article.txt --strict
    python3 tools/lint_article.py --selftest
"""

import argparse
import json
import os
import re
import sys

VERSION = "6.1.0"

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import profile as P  # noqa: E402

# Подпись в статье задаёт профиль: article.signature или имя бренда.
PROFILE = P.load()
AUTHOR_OK = P.article_author(PROFILE)
EMDASHES = "\u2014\u2013\u2015\u2012\u2212"
LABELS = ("Что даёт", "Что дает", "Что внутри", "Как запустить",
          "Как завести", "Лимиты", "Подводные камни", "Ссылка",
          "Кому надо", "Итог")
OBVIOUS = ("где можно обжечься", "где можно погореть", "важно помнить",
           "стоит помнить", "будьте осторожны", "будь осторожен",
           "никогда не давайте", "никогда не давай",
           "меры предосторожности", "техника безопасности")
SUBSCRIBE = ("подписывайтесь на канал", "подпишитесь на канал",
             "подписывайся на канал", "заходите в наш чат",
             "заходи в наш чат", "вступайте в чат",
             "остальное выкладываю в канале",
             "старый пост с полезными сервисами")
TITLE_MIN, TITLE_MAX = 40, 70
LEN_MIN, LEN_MAX = 3000, 6000
PARA_CHARS, PARA_SENT = 350, 3

HINTS = {
    "E-A-AUTHOR": "Подпись автора в статье задана в профиле: article.signature. Ник автора живёт в другом месте.",
    "E-A-OBVIOUS": "Общий ликбез про риски убираем. Оставляем конкретный лимит, цену, запрет.",
    "E-A-SUBSCRIBE": "Приглашение в канал и чат в статье не пишем: для этого есть футер поста.",
    "E-A-MERGED-LABELS": "Метки пункта идут каждая со своей строки, иначе абзац читается как стена.",
    "E-A-DENSE": "Абзац раздулся. Предел 350 знаков и три предложения, дальше рвём на строки.",
    "E-A-HEADING": "Заголовки в статье только ### и ####, telegra.ph остальное не тянет.",
    "E-A-EMDASH": "Длинное тире меняем на дефис.",
    "W-A-TITLE": "Заголовок в коридоре 40-70 знаков: цифра, суть, выгода, год.",
    "W-A-LEN": "Объём статьи 3000-6000 знаков. Больше 8000 значит нужны две статьи.",
    "W-A-SYMMETRY": "Названия пунктов одной длины выдают машину. Дай разброс.",
    "E-A-EMPTY": "Пустой файл.",
}


def add(issues, level, code, message):
    issues.append({"level": level, "code": code, "message": message})


def lint(text):
    issues = []
    lines = text.split("\n")
    filled = [row.strip() for row in lines if row.strip()]
    if not filled:
        add(issues, "ERROR", "E-A-EMPTY", "пустая статья")
        return issues

    head = "\n".join(lines[:8])
    author = re.search(r"(?im)^\s*Автор:\s*(.+)$", head)
    if not author:
        add(issues, "ERROR", "E-A-AUTHOR", "в шапке нет строки «Автор: %s»" % AUTHOR_OK)
    else:
        name = author.group(1).strip().rstrip(".").strip()
        if name != AUTHOR_OK:
            add(issues, "ERROR", "E-A-AUTHOR",
                "подпись автора «%s», а профиль просит «%s»" % (name, AUTHOR_OK))

    title = re.sub(r"^\s*(Заголовок|Title):\s*", "", filled[0]).strip()
    title = re.sub(r"^#+\s*", "", title)
    if not TITLE_MIN <= len(title) <= TITLE_MAX:
        add(issues, "WARN", "W-A-TITLE",
            "заголовок %d знаков, коридор %d-%d"
            % (len(title), TITLE_MIN, TITLE_MAX))

    low = text.lower()
    for phrase in OBVIOUS:
        if phrase in low:
            add(issues, "ERROR", "E-A-OBVIOUS",
                "общий ликбез «%s»: такого блока в статье не бывает" % phrase)
            break
    for phrase in SUBSCRIBE:
        if phrase in low:
            add(issues, "ERROR", "E-A-SUBSCRIBE",
                "приглашение в канал «%s»: в статье этого не пишем" % phrase)
            break
    if any(ch in text for ch in EMDASHES):
        add(issues, "ERROR", "E-A-EMDASH", "длинное тире: у нас только дефис")

    for number, row in enumerate(lines, 1):
        clean = row.strip()
        if clean.startswith("#") and not clean.startswith("###"):
            add(issues, "ERROR", "E-A-HEADING",
                "строка %d: заголовок уровня %s, а нужен ### или ####"
                % (number, clean.split(" ")[0]))
        hits = [label for label in LABELS if (label + ":") in clean]
        if len(hits) > 1:
            add(issues, "ERROR", "E-A-MERGED-LABELS",
                "строка %d: метки %s слиты в один абзац, каждая идёт со своей строки"
                % (number, ", ".join(hits)))

    for chunk in re.split(r"\n\s*\n", text):
        flat = " ".join(chunk.split())
        if not flat or flat.startswith("#"):
            continue
        sentences = [part for part in re.split(r"(?<=[.!?])\s+", flat) if part]
        if len(flat) > PARA_CHARS or len(sentences) > PARA_SENT:
            add(issues, "ERROR", "E-A-DENSE",
                "абзац %d знаков и %d предложений, предел %d и %d: «%s...»"
                % (len(flat), len(sentences), PARA_CHARS, PARA_SENT, flat[:40]))

    size = len(" ".join(text.split()))
    if not LEN_MIN <= size <= LEN_MAX:
        add(issues, "WARN", "W-A-LEN",
            "статья %d знаков, коридор %d-%d" % (size, LEN_MIN, LEN_MAX))

    items = [row.strip() for row in lines if re.match(r"^###\s*\d+\.", row.strip())]
    if len(items) >= 3:
        sizes = [len(item) for item in items]
        if max(sizes) - min(sizes) <= 4:
            add(issues, "WARN", "W-A-SYMMETRY",
                "названия пунктов одной длины (%d знаков): дай разброс" % sizes[0])
    return issues


def report(issues, strict=False, as_json=False):
    errors = [item for item in issues if item["level"] == "ERROR"]
    warns = [item for item in issues if item["level"] == "WARN"]
    if as_json:
        print(json.dumps({"version": VERSION, "issues": issues,
                          "clean": not issues,
                          "errorCount": len(errors), "warnCount": len(warns),
                          "errors": errors, "warns": warns},
                         ensure_ascii=False, indent=2))
    else:
        for item in issues:
            mark = "ОШИБКА" if item["level"] == "ERROR" else "предупреждение"
            print("[%s] %s: %s" % (mark, item["code"], item["message"]))
            hint = HINTS.get(item["code"])
            if hint:
                print("        %s" % hint)
        if not issues:
            print("Статья чистая.")
        else:
            print("\nИтог: ошибок %d, предупреждений %d" % (len(errors), len(warns)))
    if errors or (warns and strict):
        return 1
    return 0


GOOD = """30 бесплатных сервисов для учебы, курсовых и дипломов 2026

Автор: Demo Studio

### 1. NotebookLM

Что даёт: выжимку и тесты по загруженному учебнику.

Лимиты: 50 источников в одном блокноте.

Ссылка: https://notebooklm.google.com/
"""

BAD = """Сервисы для учебы

Автор: demo_author

## 1. NotebookLM

Что даёт: выжимку по учебнику. Как запустить: грузим файл. Подводные камни: путает даты и придумывает авторов, поэтому каждую сноску проверяем руками, иначе научрук найдёт выдуманный источник и вернёт работу. Ссылка: репозиторий с примерами и настройками лежит на гитхабе, там же список ограничений сервиса и план развития на осень.

### Где можно обжечься

Никогда не давайте агенту доступ к платежным данным.

Подписывайтесь на канал DEMO STUDIO: https://t.me/demo_channel
"""


def use_demo_profile():
    """Тесты статьи гоняем на демо-подписи."""
    demo = P.load(path=P.EXAMPLE)
    globals()["PROFILE"] = demo
    globals()["AUTHOR_OK"] = P.article_author(demo)
    return demo


def selftest():
    use_demo_profile()
    fails = []
    dirty = [item["code"] for item in lint(GOOD) if item["level"] == "ERROR"]
    if dirty:
        fails.append("чистая статья дала ошибки: %s" % ", ".join(dirty))
    codes = [item["code"] for item in lint(BAD)]
    for code in ("E-A-AUTHOR", "E-A-OBVIOUS", "E-A-SUBSCRIBE",
                 "E-A-MERGED-LABELS", "E-A-DENSE", "E-A-HEADING"):
        if code not in codes:
            fails.append("не поймал %s" % code)
    for line in fails:
        print("!! %s" % line)
    if fails:
        return 1
    print("lint_article %s: тесты прошли" % VERSION)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="линтер статьи на telegra.ph, версия %s" % VERSION)
    parser.add_argument("path", nargs="?", help="файл со статьёй")
    parser.add_argument("--strict", action="store_true",
                        help="предупреждения тоже считать провалом")
    parser.add_argument("--json", action="store_true", help="машинный вывод")
    parser.add_argument("--selftest", action="store_true", help="тесты линтера")
    parser.add_argument("--version", action="store_true", help="версия")
    args = parser.parse_args()
    if args.version:
        print(VERSION)
        return 0
    if args.selftest:
        return selftest()
    if not args.path:
        parser.print_help()
        return 2
    with open(args.path, encoding="utf-8") as fh:
        text = fh.read()
    return report(lint(text), args.strict, args.json)


if __name__ == "__main__":
    sys.exit(main())
