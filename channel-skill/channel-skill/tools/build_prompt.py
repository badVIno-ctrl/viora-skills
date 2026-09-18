#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка промптов скилла. Версия 3.0.

Источник правды один: файлы скилла. Выходов два:
    PROMPT-CORE.txt - короткое ядро для чата без файловой системы;
    PROMPT-FULL.txt - всё целиком для среды без доступа к папке.

Запуск:
    python3 tools/build_prompt.py            # собрать оба файла
    python3 tools/build_prompt.py --core      # только ядро
    python3 tools/build_prompt.py --full      # только полная версия
    python3 tools/build_prompt.py --check     # проверить, что выходы не разъехались
    python3 tools/build_prompt.py --out /tmp  # сложить результат в другую папку

Вывод детерминированный: никаких дат и времён внутри, иначе --check бесполезен.
Отсутствие CORE-блока это жёсткая ошибка, а не предупреждение.
Сторонних библиотек не нужно, только Python 3.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

START = '<!-- CORE:START name="%s" -->'
END = "<!-- CORE:END -->"

# Порядок важен: сначала кто пишет, потом за что в мусор, потом правила.
CORE_ORDER = [
    ("reference/brand.md", "who"),
    ("SKILL.md", "brand"),
    ("SKILL.md", "trash"),
    ("SKILL.md", "rules"),
    ("reference/hook.md", "hook"),
    ("reference/greetings.md", "greeting"),
    ("reference/voice.md", "lexicon"),
    ("reference/voice.md", "banned"),
    ("reference/words.md", "words"),
    ("reference/layout.md", "layout"),
    ("reference/formats.md", "lengths"),
    ("reference/antislop.md", "antislop"),
    ("reference/slop-patterns.md", "patterns"),
    ("reference/edit-mode.md", "edit"),
    ("reference/split.md", "split"),
    ("SKILL.md", "skeleton"),
    ("SKILL.md", "selfcheck"),
    ("SKILL.md", "output"),
]

FULL_ORDER = [
    "SKILL.md",
    "reference/brand.md",
    "reference/hook.md",
    "reference/voice.md",
    "reference/words.md",
    "reference/layout.md",
    "reference/formats.md",
    "reference/greetings.md",
    "reference/examples.md",
    "reference/publish.md",
    "reference/distribution.md",
    "reference/slop-patterns.md",
    "reference/edit-mode.md",
]

CORE_NAME = "PROMPT-CORE.txt"
FULL_NAME = "PROMPT-FULL.txt"
MAX_CORE_CHARS = 21500


def version():
    path = os.path.join(SKILL, "VERSION")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    return "0.0.0"


def read(rel):
    path = os.path.join(SKILL, rel)
    if not os.path.exists(path):
        raise SystemExit("Нет файла: %s" % rel)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def core_block(rel, name):
    """Вырезать блок между маркерами. Нет блока - останавливаемся."""
    text = read(rel)
    opener = START % name
    if opener not in text:
        raise SystemExit("В %s нет CORE-блока «%s»" % (rel, name))
    tail = text.split(opener, 1)[1]
    if END not in tail:
        raise SystemExit("В %s у блока «%s» нет закрывающего маркера" % (rel, name))
    block = tail.split(END, 1)[0].strip("\n")
    if not block.strip():
        raise SystemExit("Блок «%s» в %s пустой" % (name, rel))
    return block.rstrip()


def brand_name():
    """Имя бренда из профиля автора."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import profile as P
        return P.brand() or "CHANNEL SKILL"
    except Exception:
        return "CHANNEL SKILL"


def build_core():
    head = [
        "%s. Ядро правил для постов в Telegram. Версия %s." % (brand_name(), version()),
        "Собрано автоматически из channel-skill командой tools/build_prompt.py.",
        "Руками не правим: правим источник и собираем заново.",
        "Если есть доступ к файлам, читаем SKILL.md, а не этот файл.",
    ]
    parts = ["\n".join(head)]
    for rel, name in CORE_ORDER:
        parts.append(core_block(rel, name))
    parts.append(
        "\n".join(
            [
                "ЕСЛИ СОМНЕВАЕШЬСЯ",
                "Нет факта в сырье - спрашиваем одной строкой, не выдумываем.",
                "Нет срока у временной акции - пункт не публикуется.",
                "Нет личной детали - спрашиваем одной строкой.",
                "Метрики сильнее правила, кроме запрета на выдуманные факты.",
            ]
        )
    )
    return "\n\n".join(parts).strip() + "\n"


def build_full():
    head = [
        "%s. Полный скилл одним файлом. Версия %s." % (brand_name(), version()),
        "Собрано автоматически из channel-skill командой tools/build_prompt.py.",
        "Файлы идут в том же порядке, в каком их читает скилл.",
    ]
    parts = ["\n".join(head)]
    for rel in FULL_ORDER:
        parts.append(
            "\n".join(
                [
                    "=" * 60,
                    "ФАЙЛ: %s" % rel,
                    "=" * 60,
                    "",
                    read(rel).strip(),
                ]
            )
        )
    return "\n\n".join(parts).strip() + "\n"


def write_out(folder, name, text):
    path = os.path.join(folder, name)
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            old = handle.read()
    if old == text:
        print("без изменений: %s (%d знаков)" % (name, len(text)))
        return
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("собрано: %s (%d знаков)" % (name, len(text)))


def check(max_core_chars):
    """Проверить, что выходы не разъехались с источником."""
    problems = []
    core = build_core()
    full = build_full()

    for name, fresh in ((CORE_NAME, core), (FULL_NAME, full)):
        path = os.path.join(SKILL, name)
        if not os.path.exists(path):
            problems.append("нет файла %s, собери без --check" % name)
            continue
        with open(path, encoding="utf-8") as handle:
            old = handle.read()
        if old != fresh:
            problems.append(
                "%s расходится с источником (было %d знаков, стало бы %d)"
                % (name, len(old), len(fresh))
            )
        else:
            print("совпадает: %s (%d знаков)" % (name, len(old)))

    if len(core) > max_core_chars:
        problems.append(
            "ядро раздулось: %d знаков, потолок %d" % (len(core), max_core_chars)
        )

    if problems:
        print("ПРОБЛЕМЫ (%d):" % len(problems))
        for problem in problems:
            print("  - %s" % problem)
        return 1

    print("Всё собрано из одного источника, расхождений нет.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Сборка промптов скилла")
    parser.add_argument("--core", action="store_true", help="собрать только ядро")
    parser.add_argument("--full", action="store_true", help="собрать только полную версию")
    parser.add_argument("--check", action="store_true", help="проверить совпадение без записи")
    parser.add_argument("--out", default=SKILL, help="куда положить результат")
    parser.add_argument(
        "--max-core-chars",
        type=int,
        default=MAX_CORE_CHARS,
        dest="max_core_chars",
        help="потолок размера ядра в знаках",
    )
    args = parser.parse_args()

    if args.check:
        return check(args.max_core_chars)

    both = not args.core and not args.full
    folder = os.path.abspath(args.out)
    if not os.path.isdir(folder):
        raise SystemExit("Нет папки: %s" % folder)

    if args.core or both:
        core = build_core()
        if len(core) > args.max_core_chars:
            print(
                "ВНИМАНИЕ: ядро %d знаков, потолок %d. Режем блоки."
                % (len(core), args.max_core_chars)
            )
        write_out(folder, CORE_NAME, core)

    if args.full or both:
        write_out(folder, FULL_NAME, build_full())

    return 0


if __name__ == "__main__":
    sys.exit(main())
