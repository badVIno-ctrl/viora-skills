#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Доктор слопа: называет приёмы машины в тексте и даёт готовую правку.

Линтер поста ловит слова и вёрстку. Этот скрипт ловит приёмы: конструкции,
которые выглядят как мысль, но мысли не несут.

Запуск:
    python3 tools/slop_doctor.py draft.txt
    python3 tools/slop_doctor.py draft.txt --json
    python3 tools/slop_doctor.py --text "строка из твоего ответа автору"
    python3 tools/slop_doctor.py --selftest

Код выхода 0 значит находок уровня ERROR нет. С --strict считаются и WARN.
"""

import argparse
import json
import re
import sys

VERSION = "6.2.1"

DASHES = "".join(chr(code) for code in (0x2014, 0x2013, 0x2015, 0x2012, 0x2212))


def rx(*parts):
    return [re.compile(part, re.IGNORECASE) for part in parts]


PATTERNS = [
    {
        "code": "P-FAUX-INSIGHT",
        "level": "error",
        "name": "поза тайного знания",
        "fix": "убрать зачин, оставить факт с цифрой",
        "rules": rx(
            r"вот что (все|большинство|никто)",
            r"никто (не говорит|не пишет|об этом не)",
            r"(все|большинство) (упускают|не замечают|забывают об)",
            r"мало кто (знает|понимает|видит)",
            r"на самом деле (всё|все) (иначе|не так)",
        ),
    },
    {
        "code": "P-WEASEL",
        "level": "error",
        "name": "безымянные эксперты",
        "fix": "назвать источник ссылкой или снять утверждение",
        "rules": rx(
            r"исследовани\w* показывают",
            r"эксперты (считают|говорят|уверены|сходятся)",
            r"многие (считают|уверены|говорят|жалуются)",
            r"принято считать",
            r"по мнению (специалистов|экспертов|аналитиков)",
        ),
    },
    {
        "code": "P-PUFFERY",
        "level": "error",
        "name": "надувание важности",
        "fix": "поставить факт, важность читатель решит сам",
        "rules": rx(
            r"знаков\w* событие",
            r"настоящий прорыв",
            r"меняет правила игры",
            r"не имеет аналогов",
            r"революци\w* (в|для)",
            r"по-настоящему важн",
        ),
    },
    {
        "code": "P-META",
        "level": "error",
        "name": "указание, как читать",
        "fix": "удалить строку, факт говорит сам",
        "rules": rx(
            r"как вы (понимаете|уже поняли|видите)",
            r"(иными|другими) словами",
            r"стоит отметить",
            r"важно понимать",
            r"обратите внимание",
        ),
    },
    {
        "code": "P-RHETORIC-SETUP",
        "level": "error",
        "name": "риторическая подводка",
        "fix": "сказать главное первой строкой",
        "rules": rx(
            r"^а что если",
            r"спойлер:",
            r"представьте[,:]",
            r"угадайте, (что|сколько)",
            r"звучит (странно|дико|скучно)[,.]",
        ),
    },
    {
        "code": "P-RECAP",
        "level": "error",
        "name": "пересказ в конце",
        "fix": "снести: конец поста это адресная просьба переслать",
        "rules": rx(
            r"в сухом остатке",
            r"подводя итог",
            r"резюмиру\w+",
            r"^итого:",
            r"если коротко, то",
        ),
    },
    {
        "code": "P-KICKER",
        "level": "error",
        "name": "красивая пустая концовка",
        "fix": "удалить строку целиком, а не переписывать метафору",
        "rules": rx(
            r"вот и вся (история|магия|правда)",
            r"время покажет",
            r"выбор за (тобой|вами)",
            r"решать (тебе|вам)",
            r"остальное детали",
            r"дальше дело за",
        ),
    },
    {
        "code": "P-COLON-REVEAL",
        "level": "warn",
        "name": "двоеточие-раскрытие",
        "fix": "обычное предложение: кто, что делает, сколько",
        "rules": rx(
            r"(главн\w+|секрет|фишка|причина|деталь|проблема|нюанс|соль)[^:\n]{0,24}:\s*\S",
        ),
    },
    {
        "code": "P-BINARY",
        "level": "error",
        "name": "контрастная формула",
        "fix": "оставить только вторую половину",
        "rules": rx(
            r"это не (про )?\w+, а (про )?\w+",
            r"не просто \w+, а",
            r"дело не в \w+, а в",
            r"вопрос не в \w+, а в",
        ),
    },
    {
        "code": "P-SUPERFICIAL",
        "level": "warn",
        "name": "деепричастный вывод",
        "fix": "два предложения, второе про последствие для читателя",
        "rules": rx(
            r",\s*(подчёркивая|подчеркивая|показывая|демонстрируя|открывая|позволяя|создавая|обеспечивая|напоминая|подтверждая|отражая|укрепляя)\b",
        ),
    },
    {
        "code": "P-FAKE-VERB",
        "level": "error",
        "name": "канцелярский глагол",
        "fix": "писать действие: режет, считает, отдаёт, собирает",
        "rules": rx(
            r"представля\w+ собой",
            r"явля\w+ (собой|мощным|удобным|отличным|хорошим)",
            r"осуществля\w+",
            r"имеет возможность",
            r"обладает возможност\w+",
            r"выступает в качестве",
        ),
    },
    {
        "code": "P-PORTABLE",
        "level": "error",
        "name": "переносимое предложение",
        "fix": "вставить цифру, имя или свой случай, иначе вычеркнуть",
        "rules": rx(
            r"улучшает качество",
            r"открывает новые возможности",
            r"экономит (ваше |твоё |твое )?время",
            r"повышает эффективность",
            r"выводит на новый уровень",
            r"упрощает процесс",
            r"незаменим\w* (инструмент|помощник)",
        ),
    },
    {
        "code": "P-HEDGE",
        "level": "error",
        "name": "обтекание",
        "fix": "своя оценка прямо: что зашло, что бесит",
        "rules": rx(
            r"имеет как плюсы, так и минусы",
            r"есть и плюсы, и минусы",
            r"у каждого свой опыт",
            r"(всё|все) зависит от (задач|вас|тебя)",
            r"кому-то (зайдёт|зайдет), кому-то нет",
        ),
    },
]

SYNONYMS = ("инструмент", "сервис", "решение", "платформа", "продукт", "тулза")

NEG_START = re.compile(r"^(не|никакой|никаких|ни)\b", re.IGNORECASE)


def finding(code, level, name, fix, line_no, line):
    return {
        "code": code,
        "level": level,
        "name": name,
        "fix": fix,
        "line": line_no,
        "quote": line.strip()[:160],
    }


def scan_lines(text):
    out = []
    for number, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        for pattern in PATTERNS:
            for rule in pattern["rules"]:
                if rule.search(line):
                    out.append(
                        finding(
                            pattern["code"],
                            pattern["level"],
                            pattern["name"],
                            pattern["fix"],
                            number,
                            line,
                        )
                    )
                    break
        if any(char in line for char in DASHES):
            out.append(
                finding(
                    "P-DASH-CRUTCH",
                    "error",
                    "длинное тире как костыль",
                    "точка, двоеточие, запятые или короткий дефис",
                    number,
                    line,
                )
            )
    return out


def scan_neg_list(text):
    """Две и больше подряд фразы, начинающиеся с отрицания."""
    out = []
    for number, line in enumerate(text.split("\n"), 1):
        chunks = [part.strip() for part in re.split(r"[.!?]+", line) if part.strip()]
        streak = 0
        for chunk in chunks:
            if NEG_START.match(chunk):
                streak += 1
            else:
                streak = 0
            if streak >= 2:
                out.append(
                    finding(
                        "P-NEG-LIST",
                        "error",
                        "перечисление отрицаний",
                        "сказать один раз, чем вещь является",
                        number,
                        line,
                    )
                )
                break
    return out


def scan_synonym_cycle(text):
    """Три и больше синонима на одну и ту же вещь в одном тексте."""
    used = []
    for word in SYNONYMS:
        if re.search(word, text, re.IGNORECASE):
            used.append(word)
    if len(used) < 3:
        return []
    lines = text.split("\n")
    for number, line in enumerate(lines, 1):
        if any(re.search(word, line, re.IGNORECASE) for word in used):
            return [
                finding(
                    "P-SYNONYM-CYCLE",
                    "warn",
                    "карусель синонимов: " + ", ".join(used),
                    "одно слово на всю вещь, лучше её имя",
                    number,
                    line,
                )
            ]
    return []


def doctor(text):
    found = scan_lines(text) + scan_neg_list(text) + scan_synonym_cycle(text)
    found.sort(key=lambda item: (item["line"], item["code"]))
    return found


def report(found, strict=False):
    if not found:
        print("Чисто. Приёмов машины не видно.")
        return 0
    errors = [item for item in found if item["level"] == "error"]
    warns = [item for item in found if item["level"] != "error"]
    for item in found:
        mark = "ERROR" if item["level"] == "error" else "WARN "
        print("%s %-17s строка %d" % (mark, item["code"], item["line"]))
        print("      приём:  %s" % item["name"])
        print("      строка: %s" % item["quote"])
        print("      правка: %s" % item["fix"])
        print("")
    print("Находок: %d, из них ERROR %d, WARN %d" % (len(found), len(errors), len(warns)))
    print("Разбор приёмов: reference/slop-patterns.md")
    if errors:
        return 1
    return 1 if (strict and warns) else 0


CASES = [
    ("P-FAUX-INSIGHT", "Вот что все упускают в этом релизе."),
    ("P-WEASEL", "Исследования показывают, что лимиты урежут."),
    ("P-PUFFERY", "Это настоящий прорыв для тех, кто жмёт сканы."),
    ("P-META", "Иными словами, он считает страницы сам."),
    ("P-RHETORIC-SETUP", "Спойлер: он не справился с кириллицей."),
    ("P-RECAP", "В сухом остатке жать сканы стало быстрее."),
    ("P-KICKER", "Вот и вся история."),
    ("P-COLON-REVEAL", "Главная деталь: он считает страницы сам."),
    ("P-BINARY", "Это не про скорость, а про контроль."),
    ("P-SUPERFICIAL", "Вышел релиз, подчёркивая курс команды."),
    ("P-FAKE-VERB", "Сервис представляет собой удобную штуку."),
    ("P-PORTABLE", "Он заметно улучшает качество работы."),
    ("P-HEDGE", "Штука имеет как плюсы, так и минусы."),
    ("P-NEG-LIST", "Не реклама. Не обзор. Просто факты."),
    ("P-SYNONYM-CYCLE", "Сервис бесплатный. Инструмент жмёт сканы. Решение закрывает задачу."),
    ("P-DASH-CRUTCH", "Он жмёт сканы " + chr(0x2014) + " быстро."),
]

CLEAN = "\n".join(
    [
        "Сжал PDF на 300 страниц за 12 секунд.",
        "",
        "Завелось не сразу. Первый запуск упал на кириллице в именах файлов.",
        "",
        "Как забрать: три аккаунта на один ящик, лимит 50 МБ на файл.",
        "Из минусов: в час пик очередь до пяти минут.",
        "",
        "Кидай знакомому, который каждый месяц жмёт сканы вручную.",
    ]
)


def selftest():
    fails = 0
    for code, text in CASES:
        codes = [item["code"] for item in doctor(text)]
        if code in codes:
            print("ok   %s" % code)
        else:
            fails += 1
            print("FAIL %s не найден в: %s" % (code, text))
    clean = doctor(CLEAN)
    if clean:
        fails += 1
        print("FAIL чистый пост дал находки: %s" % ", ".join(item["code"] for item in clean))
    else:
        print("ok   чистый пост без находок")
    print("")
    print("Провалов: %d из %d" % (fails, len(CASES) + 1))
    return 1 if fails else 0


def main():
    parser = argparse.ArgumentParser(description="Приёмы машины в тексте: код, строка, правка")
    parser.add_argument("path", nargs="?", help="файл с черновиком")
    parser.add_argument("--text", help="проверить строку прямо из командной строки")
    parser.add_argument("--json", action="store_true", help="машинный вывод")
    parser.add_argument("--strict", action="store_true", help="считать WARN за ошибку")
    parser.add_argument("--selftest", action="store_true", help="прогон на встроенных фикстурах")
    parser.add_argument("--version", action="store_true", help="версия скрипта")
    args = parser.parse_args()

    if args.version:
        print("slop_doctor.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()

    if args.text:
        text = args.text
    elif args.path:
        try:
            with open(args.path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            print("Не читается файл: %s" % error)
            return 2
    else:
        text = sys.stdin.read()

    found = doctor(text)
    if args.json:
        print(json.dumps({"version": VERSION, "findings": found}, ensure_ascii=False, indent=2))
        return 1 if any(item["level"] == "error" for item in found) else 0
    return report(found, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
