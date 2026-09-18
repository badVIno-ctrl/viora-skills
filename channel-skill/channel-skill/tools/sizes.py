#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Честные размеры файлов в таблицах документации.

Цифры в таблицах тиров писались руками и врали почти втрое.
Слабая модель по этим цифрам выбирает тир, то есть врущая таблица
сразу ломает бюджет контекста. Теперь их считает скрипт.

    python3 tools/sizes.py            печатает правду
    python3 tools/sizes.py --write    вписывает правду в таблицы
    python3 tools/sizes.py --check    валит сборку, если таблицы разошлись с файлами
"""

import os
import re
import sys

VERSION = "6.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ROOT = os.path.dirname(SKILL)

DOCS = (
    (os.path.join("channel-skill", "ROUTER.md"), SKILL),
    ("AGENTS.md", ROOT),
    (os.path.join("channel-skill", "SKILL.md"), SKILL),
)

SHOW_FILES = (
    "QUICKCARD.txt",
    "SKILL.md",
    "ROUTER.md",
    "PROMPT-CORE.txt",
    "PROMPT-FULL.txt",
)

CELL_KB = re.compile(r"^\d+ КБ$")
CELL_TWO_KB = re.compile(r"^\d+ / \d+ КБ$")
CELL_RANGE_KB = re.compile(r"^плюс \d+-\d+ КБ$")
CELL_CHARS = re.compile(r"^\d+$")
IN_TICKS = re.compile(r"`([^`]+)`")


def size_bytes(path):
    return os.path.getsize(path)


def kb(total):
    return max(1, int(round(total / 1024.0)))


def chars(path):
    with open(path, encoding="utf-8") as handle:
        return len(handle.read())


def round100(value):
    return int(round(value / 100.0)) * 100


def row_paths(row, base):
    found = []
    for item in IN_TICKS.findall(row):
        item = item.strip()
        if not item.endswith((".md", ".txt")):
            continue
        full = os.path.join(base, item)
        if os.path.exists(full) and full not in found:
            found.append(full)
    return found


def reference_range(base):
    folder = os.path.join(base, "reference")
    if not os.path.isdir(folder):
        return None
    sizes = [size_bytes(os.path.join(folder, name))
             for name in sorted(os.listdir(folder)) if name.endswith(".md")]
    if not sizes:
        return None
    return kb(min(sizes)), kb(max(sizes))


def new_cell(cell, paths, base):
    if CELL_RANGE_KB.match(cell):
        pair = reference_range(base)
        if not pair:
            return None
        return "плюс %d-%d КБ" % pair
    if CELL_TWO_KB.match(cell):
        if len(paths) != 2:
            return None
        return "%d / %d КБ" % (kb(size_bytes(paths[0])), kb(size_bytes(paths[1])))
    if CELL_KB.match(cell):
        if not paths:
            return None
        return "%d КБ" % kb(sum(size_bytes(item) for item in paths))
    if CELL_CHARS.match(cell):
        if not paths:
            return None
        return str(round100(sum(chars(item) for item in paths)))
    return None


def is_separator(line):
    return set(line) <= set("|-: ")


def scan(doc, base):
    path = os.path.join(ROOT, doc)
    if not os.path.exists(path):
        return path, [], []
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    changes = []
    for index, line in enumerate(lines):
        if not line.startswith("|") or is_separator(line):
            continue
        cells = line.split("|")
        if len(cells) < 4:
            continue
        tail = cells[-2].strip()
        fresh = new_cell(tail, row_paths(line, base), base)
        if fresh is None or fresh == tail:
            continue
        cells[-2] = " %s " % fresh
        changes.append({
            "line": index + 1,
            "old": tail,
            "new": fresh,
            "row": "|".join(cells),
            "index": index,
        })
    return path, lines, changes


def show():
    print("| Файл | Байт | КБ | Знаков |")
    print("|---|---|---|---|")
    for name in SHOW_FILES:
        path = os.path.join(SKILL, name)
        if not os.path.exists(path):
            continue
        print("| %s | %d | %d | %d |"
              % (name, size_bytes(path), kb(size_bytes(path)), chars(path)))
    pair = reference_range(SKILL)
    if pair:
        print("")
        print("Один файл reference весит от %d до %d КБ." % pair)
    print("Считаем и байты, и знаки: кириллица ест два байта на знак.")
    return 0


def run(write):
    total = 0
    for doc, base in DOCS:
        path, lines, changes = scan(doc, base)
        if not changes:
            continue
        total += len(changes)
        for item in changes:
            print("%s:%d  %s -> %s" % (doc, item["line"], item["old"], item["new"]))
            lines[item["index"]] = item["row"]
        if write:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
    if write:
        print("Поправлено строк: %d" % total)
        return 0
    if total:
        print("Цифры в таблицах разошлись с файлами: %d строк." % total)
        print("Лечится одной командой: python3 tools/sizes.py --write")
        return 1
    print("Цифры в таблицах совпадают с файлами.")
    return 0


def selftest():
    checks = []
    checks.append(("килобайты округляются", kb(9454) == 9 and kb(17492) == 17))
    checks.append(("маленький файл не ноль", kb(10) == 1))
    checks.append(("сотни округляются", round100(6749) == 6700 and round100(6751) == 6800))

    quick = os.path.join(SKILL, "QUICKCARD.txt")
    skill = os.path.join(SKILL, "SKILL.md")
    checks.append(("ячейка в КБ считается",
                   new_cell("3 КБ", [quick], SKILL) == "%d КБ" % kb(size_bytes(quick))))
    checks.append(("две цифры в одной ячейке",
                   new_cell("13 / 90 КБ", [quick, skill], SKILL)
                   == "%d / %d КБ" % (kb(size_bytes(quick)), kb(size_bytes(skill)))))
    checks.append(("коридор reference считается",
                   (new_cell("плюс 3-7 КБ", [], SKILL) or "").startswith("плюс ")))
    checks.append(("знаки считаются",
                   new_cell("0", [quick], SKILL) == str(round100(chars(quick)))))
    checks.append(("текстовая ячейка не трогается",
                   new_cell("по одному файлу", [quick], SKILL) is None))
    checks.append(("цифра без файла не трогается",
                   new_cell("6000", [], SKILL) is None))
    checks.append(("чужие кавычки не путают",
                   row_paths("| бери `--strict` и `SKILL.md` | 1 |", SKILL) == [skill]))
    checks.append(("разделитель таблицы пропускается",
                   is_separator("|---|---|") and not is_separator("| a | 1 |")))
    checks.append(("сумма двух файлов в одной ячейке",
                   new_cell("1 КБ", [quick, skill], SKILL)
                   == "%d КБ" % kb(size_bytes(quick) + size_bytes(skill))))
    _, _, changes = scan(os.path.join("channel-skill", "ROUTER.md"), SKILL)
    checks.append(("роутер читается без ошибок", isinstance(changes, list)))

    failed = 0
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            failed += 1
    print("Итого: %d проверок размеров, провалилось %d" % (len(checks), failed))
    return 1 if failed else 0


def main(argv):
    if not argv or argv[0] in ("--show", "show"):
        return show()
    flag = argv[0]
    if flag == "--write":
        return run(True)
    if flag == "--check":
        return run(False)
    if flag == "--selftest":
        return selftest()
    if flag in ("--version", "version"):
        print("sizes.py %s" % VERSION)
        return 0
    print("Не знаю флаг: %s" % flag)
    print("Есть: --show, --write, --check, --selftest, --version")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
