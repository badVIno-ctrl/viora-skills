#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Линтер постов. Все правила бренда берутся из профиля.

Запуск:
    python3 tools/lint_post.py draft.txt
    python3 tools/lint_post.py draft.txt --strict
    python3 tools/lint_post.py draft.txt --json
    python3 tools/lint_post.py draft.txt --rubric абуз
    python3 tools/lint_post.py draft.txt --media
    python3 tools/lint_post.py --selftest
    cat draft.txt | python3 tools/lint_post.py

Код возврата: 0 - ошибок нет, 1 - есть ERROR.
ERROR - публиковать нельзя. WARN - пересмотреть глазами.
--strict делает все предупреждения ошибками.
--json отдаёт результат машинно, чтобы агент правил себя в цикле.
Сторонних библиотек не нужно, только Python 3.
"""

import argparse
import json
import os
import re
import sys

VERSION = "6.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import profile as P  # noqa: E402

# Бренд, футер, рубрики и коридоры приезжают из profile/profile.json.
# Зашитого автора здесь нет: пройди интервью, и правила подстроятся.
PROFILE = P.load()
NEVER_RE = re.compile("(?!x)x")

FOOTER = P.footer(PROFILE)
FOOTER_ON = P.footer_enabled(PROFILE) and bool(FOOTER)
FOOTER_PLAIN_RE = P.footer_plain_re(PROFILE) or NEVER_RE
FOOTER_MARKS = P.footer_marks(PROFILE)
OLD_LABEL_RE = P.legacy_label_re(PROFILE) or NEVER_RE


def footer_row(line):
    """Строка ведёт себя как футер, даже если ярлык в ней старый.

    Без этого сбитый футер читался как пропажа футера: линтер звал
    E-FOOTER-MISSING, а автоправка дописывала второй футер под первым.
    Разбор правила: reference/publish.md.
    """
    bare = line.strip()
    if not bare or not FOOTER_ON:
        return False
    if bare == FOOTER:
        return True
    if FOOTER_PLAIN_RE.search(bare):
        return True
    if "|" not in bare:
        return False
    return sum(1 for mark in FOOTER_MARKS if mark in bare) >= 2

BAD_CHARS = {
    "\u2192": "стрелка, главный признак ИИ-слопа. В цепочке шагов пишем ->",
    "\u2190": "стрелка",
    "\u21d2": "стрелка",
    "\u2022": "буллет, в Telegram ставим дефис",
    "\u203a": "шеврон",
    "\u203b": "декоративный символ",
}

BAN_EMOJI = [
    "\U0001f680", "\U0001f525", "\U0001f4a1", "\u2705", "\u2728",
    "\U0001f3af", "\U0001f4aa", "\U0001f64c", "\U0001f64f", "\u2b50",
]

BANNED = [
    "тимлид", "синерг", "экосистем", "воркфлоу", "продуктивност",
    "оптимизаци", "юзкейс", "мощный инструмент", "мощнейший",
    "открывает новые возможности", "надеюсь, было полезно",
    "надеюсь было полезно", "а вы уже пробовали", "что это для нас значит",
    "комментарий от проверщика", "получай доступ", "получи доступ",
    "разработчики заявляют", "позволяет сэкономить время",
    "идеально подходит", "погружаемся", "приятного использования",
    "целевая аудитория", "решение для бизнеса", "must have", "маст-хэв",
    "вкатываемся",
    "революцион", "инновацион", "прорывн", "не имеет аналогов",
    "лайфхак", "качественный контент", "цифровая трансформаци",
    "бесценный опыт", "в два клика", "буквально за минуту",
]

# Слоп живёт в оборотах, а не в словаре. Каждый пункт ловится регуляркой.
SLOP = [
    ("в мире, где", "«В мире, где»: зачин из школьного сочинения"),
    ("^\\s*итак\\b", "«Итак»: начинаем с дела, а не со связки"),
    ("давайте разбер", "«Давайте разберёмся»: разбираем, а не объявляем разбор"),
    ("не просто [^,.!?\\n]{1,40}, а ", "«не просто X, а Y»: главный оборот слопа"),
    ("стоит отметить", "«Стоит отметить»: если важно, просто говорим это"),
    ("важно понимать", "«Важно понимать»: убираем связку, оставляем факт"),
    ("\\bпредставьте\\b", "«Представьте»: не приглашаем воображать, показываем"),
    ("\\bпредставь\\b", "«Представь»: не приглашаем воображать, показываем"),
    ("в современном мире", "«В современном мире»: мёртвая связка"),
    ("как известно", "«Как известно»: кому известно и откуда"),
    ("ни для кого не секрет", "«Ни для кого не секрет»: сразу к факту"),
    ("в этой статье мы", "«В этой статье мы»: объявление плана вместо текста"),
    ("не только [^,.!?\n]{1,40}, но и ", "«не только X, но и Y»: второй по частоте оборот слопа"),
    ("\\bтаким образом\\b", "«Таким образом»: канцелярит, в канале так не говорят"),
    ("\\bподводя ито", "«Подводя итог»: школьное сочинение, отрежь и поставь просьбу переслать"),
    ("\\bв заключени", "«В заключение»: пост не реферат"),
    ("\\bболее того\\b", "«Более того»: пустая связка"),
    ("\\bтем не менее\\b", "«Тем не менее»: пустая связка, живое «но» короче"),
    ("\\bв конечном ито", "«В конечном итоге»: связка из переводного текста"),
    ("\\bсвоего рода\\b", "«Своего рода»: вата, назови вещь своим именем"),
    ("\\bиграет (?:важную|ключевую) роль", "«Играет важную роль»: отчёт, а не пост"),
    ("\\bключевым моментом\\b", "«Ключевым моментом»: канцелярит"),
    ("\\bстоит подчеркнуть\\b", "«Стоит подчеркнуть»: если важно, просто скажи"),
    ("\\bпозволяет (?:вам|тебе)\\b", "«Позволяет тебе»: сайт-описание, а не живой текст"),
    ("\\bи это только начало\\b", "«И это только начало»: пустое обещание"),
    ("\\bменяет правила игры\\b", "«Меняет правила игры»: перевод game changer"),
    ("\\bвыводит на новый уровень", "«Выводит на новый уровень»: рекламный штамп"),
    ("^\\s*что ж[,.!]", "«Что ж»: зачин нейронки"),
    ("\\bбез лишних слов\\b", "«Без лишних слов»: сама фраза и есть лишнее слово"),
    ("\\bразбираемся вместе\\b", "«Разбираемся вместе»: блогерский штамп"),
    ("\\bкоротко о главном\\b", "«Коротко о главном»: шапка новостного агрегатора"),
]

TY_FORMS = [
    "перейди", "перейдите", "зарегистрируйся", "зарегистрируйтесь",
    "скачай", "скачайте", "вставь", "вставьте", "проверь", "проверьте",
    "создай", "создайте", "войди", "войдите", "нажми", "нажмите",
    "открой", "откройте", "используй", "используйте", "попробуй",
    "попробуйте", "убедись", "убедитесь", "протестируй", "тестируй",
    "копируй", "скопируй", "жми", "заходи", "получай", "активируй",
    "введи", "введите", "выбери", "выберите",
]

CAPS_OK = {
    "GITHUB", "YOUTUBE", "ЧАТ", "VS", "HF", "API", "IP", "GPT", "GLM",
    "IDE", "TG", "HTML", "AI", "VPN", "ТЫК", "ТУТ", "РЕПА", "КОД",
    "ДЕМО", "СТАТЬЯ", "ИГРА", "ГАЙД", "ЗДЕСЬ", "ВАЖНО", "ЖИРНОЕ",
    "САМОЕ", "SOL", "URL", "OK", "UI", "UX", "TS", "PDF", "CSS",
    "HTTP", "HTTPS", "PS", "БЕСПЛАТНО", "БЕЗ", "КАРТЫ", "НОВОЕ",
    "УЖЕ", "НЕ", "РОБИТ", "ВИДЕО", "СТАРЫЙ", "ПОСТ", "КАНАЛ",
    "ТГК",
}

LABELS_OK = {
    "ТЫК", "ТУТ", "ЗДЕСЬ", "РЕПА", "КОД", "ДЕМО", "HF", "СТАТЬЯ",
    "ИГРА", "ГАЙД", "ЧАТ", "GITHUB", "YOUTUBE", "ТГК", "ВИДЕО",
    "СТАРЫЙ ПОСТ", "КАНАЛ",
}

LABELS_BAD = {"по ссылке", "здесь", "тут", "ссылка", "link", "клик", "жми"}

# Два бренда. По умолчанию vs, то есть старое поведение линтера не меняется.
# Разбор второго бренда: reference/distribution.md.
BRANDS = ("vs", "second-brand")

# Оффер в мем-тексте это ошибка: мем ничего не продаёт.
OFFER_WORDS = [
    "как забрать", "забирай", "подпишись", "подписывайся",
    "переходи", "ссылка в описании", "ссылка в закрепе",
    "промокод", "регистрируйся", "успей забрать", "жми на ссылку",
]

# Признаки рекламного поста: по ним включается проверка маркировки.
# Требования целиком: reference/distribution.md.
AD_SIGNS = ["#реклама", "erid", "рекламодател", "на правах рекламы"]

# План распространения в конце черновика. Проверка только по флагу --growth,
# иначе старые тесты получили бы новое предупреждение на ровном месте.
GROWTH_MARK = "^\\s*Приток:"

# Правила DEMO, которые к мему не применяются: у него другой голос, другая
# длина, нет футера, нет оффера и нет просьбы переслать. Символы, стоп-слова,
# слоп и тире проверяются у обоих брендов одинаково.
NEROBIT_SKIP = {
    "E-FOOTER-MISSING", "E-FOOTER-NOT-LAST", "E-FOOTER-PLAIN", "W-FOOTER-NO-BLANK",
    "E-HASHTAG-MISSING", "W-HASHTAG-UNKNOWN", "W-HASHTAG-PLACE", "W-HASHTAG-MANY",
    "E-FIRST-SCREEN", "E-FORWARD-CTA", "W-FORWARD-CTA", "W-REACTION-END",
    "E-PERSONAL", "E-DEADLINE-MISSING", "E-DEADLINE-NOT-IN-HEAD",
    "E-RHETORIC-END", "W-TRIPLE-LIST", "E-GREETING-LONG", "W-GREETING-SIX",
    "E-GREETING-USED", "W-GREETING-SIMILAR", "E-GREETING-BLACKLIST",
    "W-LEN-SHORT", "W-LEN-LONG", "W-ITEMS-MANY", "E-SPLIT-NEEDED", "W-SPLIT-SOON",
    "E-POST-RETELL", "E-ANONS-LABEL", "W-ANONS-LONG", "W-ARTICLE-PLACEHOLDER", "E-CAPTION-LIMIT", "W-CAPS-MANY",
    "W-HUMANITY-LOW", "W-NO-LEXICON", "W-RISK-NO-IMPORTANT", "W-INSTRUCTION-WORD",
    "E-TY-FORM", "W-TY-ADDRESS", "W-SYMMETRY", "W-PARA-RHYTHM", "W-POS-STREAK",
    "W-OPENERS", "W-SENT-LONG", "W-PARASITE",
    "W-SENT-RUN", "W-NOMINAL-SUBJ", "W-PARTICIPLE-TAIL",
}

# Есть статья значит пост это анонс: пунктов в нём нет, разбор в
# reference/split.md. Тело анонса короткое, поэтому правила про длину рубрики,
# личную деталь и просьбу переслать к нему не применяются.
ANNOUNCE_MAX = 400
ANNOUNCE_SKIP = {
    "E-PERSONAL", "E-DEADLINE-MISSING", "E-DEADLINE-NOT-IN-HEAD",
    "E-FIRST-SCREEN", "E-FORWARD-CTA", "E-RHETORIC-END",
    "E-SPLIT-NEEDED", "W-SPLIT-SOON", "W-ITEMS-MANY",
    "W-LEN-SHORT", "W-LEN-LONG", "W-HUMANITY-LOW", "W-RISK-NO-IMPORTANT",
    "W-NO-LEXICON", "W-LABEL-NONSTD", "W-SYMMETRY", "W-PARA-RHYTHM",
    "W-POS-STREAK", "W-TRIPLE-LIST", "W-SENT-RUN", "W-OPENERS",
    "W-REACTION-END", "W-FORWARD-CTA",
}

# Блоки, которые модель пришивает сама. Разбор в reference/antislop.md.
OBVIOUS_BLOCKS = [
    "где можно обжечься", "где можно погореть", "важно помнить",
    "стоит помнить", "будьте осторожны", "будь осторожен",
    "никогда не давайте", "никогда не давай", "меры предосторожности",
    "техника безопасности",
]

SUBSCRIBE_CTA = [
    "подписывайтесь на канал", "подпишитесь на канал", "подписывайся на канал",
    "заходите в наш чат", "заходи в наш чат", "вступайте в чат",
    "остальное выкладываю в канале", "старый пост с полезными сервисами",
]

# Структурные следы машины, которых не видно по словарю: reference/beauty.md.
PARTICIPLE_TAIL = re.compile(
    r",\s*(позволяя|обеспечивая|делая|давая|создавая|открывая|превращая"
    r"|сохраняя|экономя|упрощая|ускоряя)\b"
)
NOMINAL_SUBJ = re.compile(
    r"(?:ация|ение|ание|овка|изация)\b[^.!?]{0,40}\b"
    r"(позволяет|даёт|дает|обеспечивает|помогает|улучшает|повышает)\b"
)


LEXICON = [
    "жир", "годнота", "халяв", "абуз", "лутать", "забираем", "чекаем",
    "регаем", "акк", "рега", "рефка", "лимит", "робит", "крч",
    "подъехало", "потыкать", "налетайте", "дырка", "буржу", "сабы",
    "тащит", "вывозит", "сам сижу", "я проверял", "у меня", "сам забрал",
]

RISK = [
    ("\\bкарт(?:а|у|ы|ой|е)\\b", "привязка карты"),
    ("\\bIP\\b", "смена IP"),
    ("\\bбан\\w*", "риск бана"),
    ("запись экрана", "запись экрана"),
    ("номер телефона", "номер телефона"),
    ("инкогнито", "режим инкогнито"),
    ("\\bVPN\\b", "VPN"),
]

# Призыв к пересылке и просьба о реакциях.
FORWARD = [
    "перешли", "перешлите", "переслать", "перекинь", "кинь тому",
    "кинь друг", "скинь тому", "скинь друг", "отправь тому",
    "покажи тому", "покажи друг",
]

REACTION = ["реакци", "добьем", "добьём", "поставь плюс", "лайк"]

# Личная деталь: железное правило 19.
PERSONAL = [
    "сам ", "сам,", "сами ", "я провер", "мы провер", "у меня", "мне ",
    "завелось", "завелся", "не завел", "отвали", "убил", "ушло ",
    "гонял", "потратил", "тестил", "сижу", "с первого раза",
    "со второго раза", "с третьего раза", "по моему опыту",
    "вчера ", "ночью ", "проверял", "сломалось у", "попытк",
]

RUBRICS = P.rubric_names(PROFILE)

LENGTHS = P.lengths(PROFILE)

# Запрещённые тире и минусы. В постах их не бывает ни одного.
EMDASHES = "\u2014\u2013\u2015\u2012\u2212"

# Пороги разреза на пост плюс статью. Источник: reference/split.md.
TG_LIMIT = 4096
CAPTION_LIMIT = 1024
SPLIT_SOFT = 1400
SPLIT_HARD = 2200
SPLIT_ITEMS_SOFT = 7
SPLIT_ITEMS_HARD = 8
MEDIA_BODY = 900
ARTICLE_LABEL = "[СТАТЬЯ]("
ARTICLE_PLACEHOLDER = "PASTE_TELEGRAPH_URL"

# Призыв к пересылке: где ошибка, где предупреждение, где не нужен.
FORWARD_REQUIRED = P.forward_required(PROFILE)
FORWARD_WANTED = P.forward_wanted(PROFILE)
SOFT_FIRST_SCREEN = P.soft_first_screen(PROFILE)

OPENERS = [
    "вечер", "шалом", "хай", "привет", "приветствую", "здравствуй",
    "здарова", "здорова", "салют", "доброе", "добрый", "всем",
    "йо", "ку", "утро", "ночь", "доброго", "дорогие", "товарищи",
]

DEADLINE = [
    "\\bдо \\d{1,2}", "\\d{1,2}\\.\\d{2}", "\\d{1,2} (?:янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)",
    "до конца", "\\bсегодня\\b", "\\bзавтра\\b", "\\bna \\d+\\b",
    "\\d+ (?:дней|дня|день|недел|месяц)", "пока не закрыли",
]

TEMPORAL = ["акци", "триал", "trial", "промокод", "раздают", "раздаю", "скидк"]

PARASITE = ["просто", "очень", "буквально", "довольно", "вообще"]

PREPS = {
    "в", "на", "с", "по", "для", "из", "у", "о", "к", "за", "при", "без",
    "под", "над", "от", "до", "про", "между",
}

EMOJI = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf\u2b00-\u2bff]")
LINK = "\\[([^\\]]*)\\]\\([^)]*\\)"


def norm(text):
    """Нижний регистр, без знаков и лишних пробелов: для сравнения приветствий."""
    low = text.lower().replace("\u0451", "\u0435")
    low = re.sub("[^0-9a-z\u0430-\u044f ]+", " ", low)
    return re.sub("\\s+", " ", low).strip()


def unlink(text):
    """[ЯРЛЫК](url) превращаем в ЯРЛЫК: считаем то, что видит читатель."""
    return re.sub(LINK, "\\1", text)


def nolinks(text):
    """Убрать ссылки целиком: так видно, что голый URL остался в тексте."""
    return re.sub(LINK, " ", text)


def markup_off(line):
    """Снять разметку и маркеры списка, оставить слова."""
    clean = line.replace("**", "").replace("__", "").replace("`", "")
    clean = re.sub("^\\s*>\\s*", "", clean)
    clean = re.sub("^\\s*[-*]\\s+", "", clean)
    clean = re.sub("^\\s*\\d+[.)]\\s*", "", clean)
    return unlink(clean).strip()


def words(text):
    return re.findall("[0-9A-Za-z\u0410-\u042f\u0401\u0430-\u044f\u0451-]+", text)


def sentences(row):
    parts = re.split("(?<=[.!?])\\s+", row.strip())
    return [part for part in parts if part.strip()]


def read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return handle.read().split("\n")


def bank_section(name):
    """Пункты списка из раздела ## <name> в reference/greetings.md."""
    rows = read_lines(os.path.join(SKILL, "reference", "greetings.md"))
    out = []
    inside = False
    for row in rows:
        if row.startswith("## "):
            inside = name.lower() in row.lower()
            continue
        if not inside:
            continue
        item = re.match("^\\s*(?:[-*]|\\d+[.)])\\s+(.+)$", row)
        if item:
            out.append(item.group(1).strip().strip("*_`"))
    return out


def load_used_greetings():
    """Приветствия, которые уже выходили: memory/used-greetings.md."""
    rows = read_lines(os.path.join(SKILL, "memory", "used-greetings.md"))
    out = []
    for row in rows:
        hit = re.match("^\\d{4}-\\d{2}[^|]*\\|\\s*(.+)$", row.strip())
        if hit:
            out.append(hit.group(1).strip().strip("*_`"))
    return out


def load_blacklist_greetings():
    """Занятые и забракованные автором приветствия."""
    return bank_section("Занято") + bank_section("Забраковано")


def load_meme_log():
    """Шаблоны и шутки, которые уже выходили: memory/meme-log.md."""
    rows = read_lines(os.path.join(SKILL, "memory", "meme-log.md"))
    out = []
    for row in rows:
        hit = re.match("^(\\d{4}-\\d{2}[^|]*)\\|([^|]*)\\|\\s*(.+)$", row.strip())
        if not hit:
            continue
        out.append({
            "date": hit.group(1).strip(),
            "template": hit.group(2).strip().strip("*_`").lower(),
            "text": hit.group(3).strip().strip("*_`"),
        })
    return out


GREETING_BASE = {
    "вечер", "здарова", "здорова", "хай", "шалом", "привет",
    "приветствую", "салют", "доброго", "добрый", "доброе",
    "йо", "ку", "в", "хату", "всем", "салам", "мир",
}


def greeting_tail(line):
    """Хвост приветствия без базы: база повторяется, хвост нет."""
    parts = [
        word
        for word in norm(markup_off(line)).split(" ")
        if word and word not in GREETING_BASE
    ]
    return " ".join(parts).strip()


def starts_with_opener(line):
    first = words(norm(line))
    return bool(first) and first[0] in OPENERS


def jaccard(left, right):
    """Похожесть двух хвостов по общим словам."""
    left_set = set(left.split())
    right_set = set(right.split())
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / float(len(left_set | right_set))


def find_hashtags(text):
    """Хэштеги-рубрики: только те, что стоят отдельной строкой."""
    out = []
    for index, row in enumerate(text.split("\n")):
        hit = re.match("^#([^\\s#]+)$", row.strip())
        if hit:
            out.append((index, hit.group(1).lower()))
    return out


def detect_rubric(text, rubric=None):
    """Рубрика берётся из флага --rubric или из хэштега в тексте."""
    if rubric:
        return rubric.strip().lstrip("#").lower()
    for _, tag in find_hashtags(text):
        if tag in RUBRICS:
            return tag
    return None


def detect_brand(text, brand=None):
    """Бренд берётся из флага --brand или из хэштега #мем в тексте."""
    if brand:
        value = brand.strip().lstrip("#").lower()
        return value if value in BRANDS else "vs"
    for _, tag in find_hashtags(text):
        if tag == "мем":
            return "second-brand"
    return "vs"


def has_any(low, items):
    return any(item in low for item in items)


def has_deadline(text):
    low = text.lower()
    return any(re.search(pattern, low) for pattern in DEADLINE)


def word_class(word):
    """Грубая часть речи: хватает, чтобы поймать три однотипные строки подряд."""
    low = norm(word)
    if not low:
        return "прочее"
    if re.match("^\\d+$", low):
        return "числительное"
    if low in PREPS:
        return "предлог"
    if re.search("(аем|яем|им|ем|ешь|ишь|ать|ить|еть|ыть|ал|ил|ыл|ла|ли)$", low):
        return "глагол"
    if re.search("(ый|ий|ой|ая|яя|ое|ее|ые|ие)$", low):
        return "прилагательное"
    return "существительное"


def numbered_items(body):
    """Разбить текст на пункты списка. Каждый пункт это список строк."""
    blocks = []
    current = None
    for row in body.split("\n"):
        if re.match("^\\s*(?:\\*\\*)?\\d+[.)]", row):
            if current:
                blocks.append(current)
            current = [row]
            continue
        if current is not None:
            if not row.strip():
                blocks.append(current)
                current = None
            else:
                current.append(row)
    if current:
        blocks.append(current)
    return blocks


HUMANITY_MIN = 3

# Разговорные частицы и улыбки: то, чего нейронка почти никогда не ставит сама.
CHATTY = [
    "крч", "короче", "кароч", "типа", "вроде", "мол", "щас",
    "по факту", "как-то", "ага", "жиза", "))", "ну и ", "да и ",
]

# Знаки честного минуса: живой автор говорит, где не работает.
HONEST = [
    "второй бренд", "не завел", "минус", "может забан", "риск",
    "дырк", "костыл", "сыро", "лагает", "отвалил", "убил",
    "с третьего раза", "не всем ", "не всегда",
]


def humanity(text):
    """Счёт живых признаков: сколько человеческого осталось в тексте.

    Семь признаков, по одному баллу. Ни один не обязателен по отдельности,
    но если живых меньше трёх, текст читается как сгенерированный, даже когда
    в нём нет ни одного запрещённого слова. Это вторая половина антислопа:
    стоп-лист убирает машинное, а счёт требует добавить человеческое.

    Возвращает (счёт, максимум, чего не хватает словами).
    """
    body = nolinks(text)
    low = body.lower()
    short = False
    for row in body.split("\n"):
        for part in sentences(row):
            count = len(words(part))
            if 0 < count <= 4:
                short = True
                break
        if short:
            break
    marks = [
        ("своя деталь или проверка на себе", has_any(low, PERSONAL)),
        ("конкретная цифра", bool(re.search("\\d", body))),
        ("слово из словаря канала", has_any(low, LEXICON)),
        ("короткая фраза до четырёх слов", short),
        ("разговорная частица или улыбка", has_any(low, CHATTY)),
        ("обращение к читателю на ты",
         bool(re.search("\\bт(?:ы|ебе|ебя|вой|воя|вои|воё)\\b", low))),
        ("честный минус или риск", has_any(low, HONEST)),
    ]
    live = sum(1 for _, ok in marks if ok)
    missing = [name for name, ok in marks if not ok]
    return live, len(marks), missing


HINTS = {
    "E-EMPTY": "Напиши пост по скелету из SKILL.md.",
    "E-ARROW": "Убери стрелки. Пиши словами: сначала одно, потом другое.",
    "E-BULLET": "Убери точки и кружки. Нумеруй пункты цифрой с точкой.",
    "E-CIRCLED": "Замени кружки-цифры на обычные цифры.",
    "E-BOLD-UNICODE": "Убери unicode-жирные буквы. Жирный только через двойные звёздочки.",
    "E-EMOJI-BAN": "Этот смайл из бана. Возьми спокойный смайл или обойдись без него.",
    "E-BARE-URL": "Оберни адрес в ярлык: [ТЫК](https://...).",
    "E-LABEL-SLOP": "Ярлык «здесь» или «по ссылке» замени на ТЫК, РЕПА, ДЕМО, СТАТЬЯ.",
    "W-LABEL-NONSTD": "Этого ярлыка нет в списке бренда. Сверься с reference/layout.md.",
    "E-FOOTER-PLAIN": "Футер ставь ссылками в квадратных скобках, а не текстом.",
    "E-FOOTER-MISSING": "Добавь футер бренда последней строкой без изменений.",
    "E-FOOTER-NOT-LAST": "Перенеси футер в самый конец поста.",
    "W-FOOTER-NO-BLANK": "Отдели футер пустой строкой.",
    "E-BANNED-WORD": "Слово из стоп-листа. Открой reference/antislop.md и возьми живую замену.",
    "E-SLOP-CONSTRUCT": "Это нейронная связка. Разбей на два простых предложения.",
    "W-HUMANITY-LOW": "Мало живых признаков. Добавь свою деталь, цифру и короткую фразу.",
    "E-TY-FORM": "Перепиши шаг в мы-форме: не «скачай», а «скачиваем».",
    "E-MD-HEADING": "Убери решётки заголовков, Telegram их не рендерит. Заголовок делай жирным.",
    "E-EMDASH": "Замени каждое длинное тире на точку, запятую или дефис. Диапазон пиши словом «от и до».",
    "E-RHETORIC-END": "Убери вопрос в конце. Последняя строка это просьба переслать.",
    "W-TRIPLE-LIST": "Разбей тройку с нарастанием: оставь два пункта или сломай ритм.",
    "E-GREETING-LONG": "Сократи приветствие до пяти слов.",
    "W-GREETING-SIX": "Приветствие на грани длины, лучше короче.",
    "E-GREETING-BLACKLIST": "Это приветствие запрещено. Возьми новое из reference/greetings.md.",
    "E-GREETING-USED": "Такое приветствие уже было. Придумай другое и запиши в memory/used-greetings.md.",
    "W-GREETING-SIMILAR": "Приветствие похоже на прошлое, смени слова.",
    "E-FIRST-SCREEN": "В первые две строки поставь цифру выгоды или конкретный факт.",
    "E-HASHTAG-MISSING": "Добавь один хэштег рубрики перед футером.",
    "W-HASHTAG-MANY": "Оставь один хэштег, остальные убери.",
    "W-HASHTAG-UNKNOWN": "Такой рубрики нет. Список в SKILL.md.",
    "W-HASHTAG-PLACE": "Хэштег ставим перед футером, а не в середине.",
    "E-FORWARD-CTA": "Для этой рубрики обязательна просьба переслать конкретному человеку.",
    "W-FORWARD-CTA": "Добавь адресную просьбу переслать, она даёт охват.",
    "W-REACTION-END": "Просьба про реакции слабее просьбы переслать. Замени.",
    "E-PERSONAL": "Добавь одну личную деталь: что сам делал, сколько времени ушло.",
    "E-DEADLINE-NOT-IN-HEAD": "Срок акции перенеси в первую строку пункта.",
    "E-DEADLINE-MISSING": "Укажи срок акции цифрой или датой.",
    "W-LEN-SHORT": "Добавь один пункт или личную деталь.",
    "W-LEN-LONG": "Режь слабые пункты или гони python3 tools/split_post.py draft.txt --check.",
    "W-ITEMS-MANY": "Оставь в посте три пункта, остальное в статью на telegra.ph.",
    "E-SPLIT-NEEDED": "Гони python3 tools/split_post.py draft.txt и отдай две части: статью и пост.",
    "W-SPLIT-SOON": "Пост на грани. Либо режь пункты, либо делай статью.",
    "E-POST-RETELL": "Есть статья значит пост это анонс: приветствие, название ссылкой, хэштег, футер.",
    "E-ANONS-LABEL": "Ссылкой в анонсе идёт само название материала, а не ярлык ТЫК или СТАТЬЯ.",
    "W-ANONS-LONG": "Анонс раздулся до пересказа. Тело до 400 знаков, остальное живёт в статье.",
    "E-OBVIOUS-BLOCK": "Убери общий ликбез про риски. Оставляем конкретный лимит или цифру.",
    "E-SUBSCRIBE-CTA": "Приглашение в канал и чат живёт в футере и закрепе, а не внутри текста.",
    "E-FOOTER-OLD-LABEL": "В футере остался устаревший ярлык из профиля: поставь актуальный.",
    "W-PARTICIPLE-TAIL": "Деепричастный хвост «, позволяя ...» это машина. Режь на два предложения.",
    "W-NOMINAL-SUBJ": "«Интеграция позволяет» это машина. Пиши, кто и что делает: «сервис собирает».",
    "W-SENT-RUN": "Три предложения подряд одной длины. Вставь короткое на три слова.",
    "W-ARTICLE-PLACEHOLDER": "Адрес статьи ещё не вставлен. Автор публикует статью и меняет метку.",
    "E-TG-LIMIT": "Сообщение больше предела Telegram. Режь через split_post.py.",
    "E-CAPTION-LIMIT": "С фото влезает только короткая подпись. Уноси тело в статью.",
    "W-CAPS-MANY": "Оставь до трёх слов капсом.",
    "W-BANGS": "Убери лишние восклицания.",
    "W-EMOJI-MANY": "Оставь смайлы только где они несут смысл.",
    "W-DOUBLE-BLANK": "Между блоками только одна пустая строка.",
    "W-SENT-LONG": "Разбей длинное предложение на два.",
    "W-PARA-RHYTHM": "Сделай абзацы разной высоты: две строки, одна, три.",
    "W-SYMMETRY": "Сломай симметрию пунктов: один пункт сделай короче или длиннее.",
    "W-POS-STREAK": "Добавь одну строку недовольства, иначе читается как реклама.",
    "W-OPENERS": "Не начинай подряд с одного слова.",
    "W-NO-LEXICON": "Добавь одно слово из словаря бренда из reference/voice.md.",
    "W-RISK-NO-IMPORTANT": "Есть риск, а блока ВАЖНО! нет. Добавь одну строку про риск.",
    "W-INSTRUCTION-WORD": "Замени «Инструкция:» на «Как забрать:».",
    "W-TY-ADDRESS": "Замени «ты» на «вы» или перепиши без обращения.",
    "W-PARASITE": "Убери слово-паразит, смысл не пострадает.",
    "E-BRAND-FOOTER": "Убери футер основного бренда: у второго бренда его нет. Ссылка живёт в закрепе.",
    "E-BRAND-OFFER": "Убери оффер: мем ничего не продаёт. Голос в reference/distribution.md.",
    "E-MEME-LINK": "Убери ссылку из мема. Её место в закреплённом комментарии.",
    "E-AD-NO-MARK": "Поставь «Реклама» первой строкой, назови рекламодателя и добавь erid от ОРД.",
    "W-MEME-REPEAT": "Шаблон или шутка уже выходили. Возьми другой шаблон из reference/distribution.md.",
    "W-GROWTH-NO-PLAN": "Допиши три строки: Приток, Действие, Замер. Каналы в reference/distribution.md.",
}


def hint_for(code):
    return HINTS.get(code, "Смотри SKILL.md и reference/ по этому пункту.")


def add(issues, level, code, message):
    issues.append({"level": level, "code": code, "message": message})


ARTICLE_URL_MARK = "PASTE_TELEGRAPH_URL"
OLD_POST_LINK = re.compile("\\[СТАРЫЙ ПОСТ\\]\\([^()\\s]*\\)")
LINK_PAIR = re.compile("\\[([^\\[\\]]*)\\]\\(([^()\\s]*)\\)")


def article_link(text):
    """Есть ли в тексте ссылка на свою статью. Старый пост не считается."""
    clean = OLD_POST_LINK.sub("", text)
    return (
        ARTICLE_LABEL in clean
        or ARTICLE_URL_MARK in clean
        or "telegra.ph" in clean.lower()
    )


def is_article_target(target):
    return "telegra.ph" in target.lower() or ARTICLE_URL_MARK in target


def check_announce(issues, text, size):
    """Правила анонса: ссылкой идёт название материала, тело короткое."""
    for label, target in LINK_PAIR.findall(text):
        if not is_article_target(target):
            continue
        clean = label.strip()
        if clean in LABELS_OK or clean == clean.upper() or len(clean) < 15:
            add(issues, "ERROR", "E-ANONS-LABEL",
                "ссылка на статью спрятана за ярлык [%s]: ставим название материала"
                % clean)
    if size > ANNOUNCE_MAX:
        add(issues, "WARN", "W-ANONS-LONG",
            "анонс %d знаков, верх %d: это уже пересказ статьи"
            % (size, ANNOUNCE_MAX))


def sentence_run(body):
    """Самая долгая серия соседних предложений почти одной длины."""
    plain = unlink(body).replace("**", "")
    parts = [p.strip() for p in re.split("(?<=[.!?])\\s+", plain)]
    sizes = [len(p) for p in parts if len(p) >= 40]
    best = run = 1
    for first, second in zip(sizes, sizes[1:]):
        if abs(first - second) <= 6:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return best


def lint(text, rubric=None, media=False, brand=None, growth=False,
         kind="авто"):
    """Проверить пост. Возвращает список найденного и распознанную рубрику."""
    issues = []
    lines = text.split("\n")
    filled = [line for line in lines if line.strip()]
    if not filled:
        add(issues, "ERROR", "E-EMPTY", "пустой пост")
        return issues, None

    rubric = detect_rubric(text, rubric)
    brand = detect_brand(text, brand)
    low = text.lower()
    shown = unlink(text)
    stripped = nolinks(text)

    tags = find_hashtags(text)
    tag_rows = set(index for index, _ in tags)
    footer_rows = set(
        index for index, line in enumerate(lines) if line.strip() == FOOTER
    )
    # Похожий на футер ряд тоже футер: тело поста его не включает.
    footish_rows = set(
        index for index, line in enumerate(lines) if footer_row(line)
    )
    body_lines = [
        line
        for index, line in enumerate(lines)
        if index not in tag_rows and index not in footish_rows
    ]
    body = "\n".join(body_lines)
    body_filled = [line for line in body_lines if line.strip()]

    # --- символы ---
    for char, why in BAD_CHARS.items():
        if char in text:
            code = "E-ARROW" if char in "\u2192\u2190\u21d2" else "E-BULLET"
            add(issues, "ERROR", code, "символ %s: %s" % (char, why))
    if re.search("[\u2460-\u2473]", text):
        add(issues, "ERROR", "E-CIRCLED", "кружки-цифры: пишем обычные 1. 2. 3.")
    if re.search("[\U0001d400-\U0001d7ff]", text):
        add(issues, "ERROR", "E-BOLD-UNICODE", "жирные юникод-буквы: пишем обычным текстом")
    for emo in BAN_EMOJI:
        if emo in text:
            add(issues, "ERROR", "E-EMOJI-BAN", "эмодзи %s: не наш стиль" % emo)

    # --- ссылки и ярлыки ---
    if re.search("https?://", stripped):
        add(issues, "ERROR", "E-BARE-URL", "голый URL: ссылки прячем в текст, [ЯРЛЫК](url)")

    # Ярлык внутри футера судит отдельное правило E-FOOTER-OLD-LABEL,
    # иначе один старый [DEMO] давал сразу два сообщения.
    label_hay = "\n".join(
        line for index, line in enumerate(lines) if index not in footish_rows
    )
    for label in re.findall("\\[([^\\[\\]]*)\\]\\(", label_hay):
        clean = label.strip()
        if clean.lower() in LABELS_BAD and clean != clean.upper():
            add(issues, "ERROR", "E-LABEL-SLOP",
                "ярлык-слоп [%s]: ставим [ТЫК], [ТУТ], [РЕПА]" % clean)
        elif clean not in LABELS_OK and not clean.startswith("Абуз"):
            add(issues, "WARN", "W-LABEL-NONSTD",
                "нестандартный ярлык [%s]: ок, если это имя сервиса" % clean)

    # --- футер ---
    # Один сбитый футер обязан давать одно сообщение. Старый ярлык это
    # не пропажа футера, так что здесь молчим и отдаём его E-FOOTER-OLD-LABEL.
    spot = sorted(footish_rows)
    exact = FOOTER in text
    stale = bool(OLD_LABEL_RE.search(text))
    if FOOTER_ON and not spot:
        add(issues, "ERROR", "E-FOOTER-MISSING",
            "нет футера: ставим строку со ссылками в самом низу")
    elif not exact and FOOTER_PLAIN_RE.search(text):
        add(issues, "ERROR", "E-FOOTER-PLAIN",
            "футер без ссылок: он существует только ради охвата")
    elif not exact and not stale:
        add(issues, "ERROR", "E-FOOTER-MISSING",
            "футер собран не по образцу: сверь строку со ссылками со стандартом")
    if FOOTER_ON and spot:
        if filled and not footer_row(filled[-1]):
            add(issues, "ERROR", "E-FOOTER-NOT-LAST", "футер не последней строкой")
        if spot[0] > 0 and lines[spot[0] - 1].strip():
            add(issues, "WARN", "W-FOOTER-NO-BLANK", "перед футером нет пустой строки")

    # --- слова и конструкции ---
    for phrase in BANNED:
        if phrase in low:
            add(issues, "ERROR", "E-BANNED-WORD", "запрещённая фраза: %s" % phrase)
    for pattern, why in SLOP:
        if re.search(pattern, low, re.M):
            add(issues, "ERROR", "E-SLOP-CONSTRUCT", "слоп-конструкция: %s" % why)

    live, total, missing = humanity(text)
    if live < HUMANITY_MIN:
        add(issues, "WARN", "W-HUMANITY-LOW",
            "живых признаков %d из %d, нет: %s" % (live, total, ", ".join(missing[:3])))
    for verb in TY_FORMS:
        if re.search("\\b%s\\b" % verb, low):
            add(issues, "ERROR", "E-TY-FORM",
                "ты-форма «%s»: шаги пишем в мы-форме" % verb)

    if re.search("^#{1,6}\\s", text, re.M):
        add(issues, "ERROR", "E-MD-HEADING",
            "markdown-заголовок: в Telegram решётки не рендерятся")

    dashes = [char for char in text if char in EMDASHES]
    if dashes:
        add(issues, "ERROR", "E-EMDASH",
            "длинных тире и минусов %d: в постах их не бывает ни одного" % len(dashes))

    # риторический вопрос в конце: разрешён только в опросе
    if body_filled and rubric != "опрос":
        if body_filled[-1].strip().endswith("?"):
            add(issues, "ERROR", "E-RHETORIC-END",
                "риторический вопрос в конце: вместо него просим пересылку")

    # тройное перечисление с нарастанием
    for triple in re.findall(
        "([\\w][\\w\\s-]{2,40}), ([\\w][\\w\\s-]{2,40}) и ([\\w][\\w\\s-]{2,40})", shown
    ):
        sizes = [len(part.strip()) for part in triple]
        if sizes[0] < sizes[1] < sizes[2]:
            add(issues, "WARN", "W-TRIPLE-LIST",
                "тройное перечисление с нарастанием: %s..." % triple[0].strip()[:30])
            break

    # --- приветствие ---
    head_line = markup_off(filled[0])
    if starts_with_opener(head_line):
        count = len(words(head_line))
        if count > 6:
            add(issues, "ERROR", "E-GREETING-LONG",
                "приветствие в %d слов: до пяти, оно съедает превью" % count)
        elif count == 6:
            add(issues, "WARN", "W-GREETING-SIX",
                "приветствие в шесть слов: держим пять")

        current = norm(head_line)
        tail = greeting_tail(head_line)
        for bad in load_blacklist_greetings():
            if bad and (bad == current or bad in current):
                add(issues, "ERROR", "E-GREETING-BLACKLIST",
                    "приветствие забраковано автором: %s" % bad)
                break

        for used in load_used_greetings():
            used_tail = greeting_tail(used)
            if not used_tail or not tail:
                if used == current:
                    add(issues, "ERROR", "E-GREETING-USED",
                        "приветствие уже занято: %s" % used)
                    break
                continue
            if tail == used_tail:
                add(issues, "ERROR", "E-GREETING-USED",
                    "приветствие уже занято: %s" % used)
                break
            shorter = min(len(tail), len(used_tail))
            same = tail[:shorter] == used_tail[:shorter]
            if same and shorter >= 2:
                add(issues, "ERROR", "E-GREETING-USED",
                    "приветствие повторяет занятое: %s" % used)
                break
            if same and shorter == 1:
                add(issues, "WARN", "W-GREETING-SIMILAR",
                    "приветствие близко к занятому: %s" % used)
                break
            if jaccard(tail, used_tail) >= 0.6:
                add(issues, "WARN", "W-GREETING-SIMILAR",
                    "приветствие почти совпадает с занятым: %s" % used)
                break

    # --- первый экран ---
    head = unlink("\n".join(body_filled))[:120]
    if not re.search("\\d", head) and not has_deadline(head):
        level = "WARN" if rubric in SOFT_FIRST_SCREEN else "ERROR"
        add(issues, level, "E-FIRST-SCREEN",
            "в первых 120 знаках нет ни цифры, ни срока: это превью и пуш")

    # --- хэштег-рубрика ---
    if not tags:
        add(issues, "ERROR", "E-HASHTAG-MISSING",
            "нет хэштега-рубрики: ставим один отдельной строкой перед футером")
    else:
        if len(tags) > 1:
            add(issues, "WARN", "W-HASHTAG-MANY",
                "хэштегов %d: ровно один, иначе надо было писать два поста" % len(tags))
        for index, tag in tags:
            if tag not in RUBRICS:
                add(issues, "WARN", "W-HASHTAG-UNKNOWN",
                    "хэштег #%s не из списка рубрик" % tag)
        last_tag = tags[-1][0]
        after = [
            line.strip()
            for line in lines[last_tag + 1:]
            if line.strip()
        ]
        # Сбитый футер уже назван своим кодом. Если после хэштега идёт
        # только строка футера, пусть даже с чужим ярлыком, место верное.
        if after and not (len(after) == 1 and footer_row(after[0])):
            add(issues, "WARN", "W-HASHTAG-PLACE",
                "хэштег не на своём месте: он идёт последней строкой перед футером")

    # --- концовка: пересылка важнее реакций ---
    forward = has_any(low, FORWARD)
    reaction = has_any(low, REACTION)
    if not forward:
        if rubric in FORWARD_REQUIRED:
            add(issues, "ERROR", "E-FORWARD-CTA",
                "нет призыва к пересылке: для #%s он обязателен" % rubric)
        elif rubric in FORWARD_WANTED:
            add(issues, "WARN", "W-FORWARD-CTA",
                "нет призыва к пересылке: для #%s он обычно уместен" % rubric)
    if reaction and not forward:
        add(issues, "WARN", "W-REACTION-END",
            "концовка просит реакции: реакции греют самолюбие, пересылки приводят людей")

    # --- личная деталь ---
    if not has_any(low, PERSONAL):
        add(issues, "ERROR", "E-PERSONAL",
            "нет личной детали: с какого раза завелось, что отвалилось, сколько времени убил")

    # --- срок в первой строке пункта ---
    blocks = numbered_items(body)
    deadline_reported = False
    for block in blocks:
        chunk = "\n".join(block)
        chunk_low = chunk.lower()
        if not has_any(chunk_low, TEMPORAL):
            continue
        first_row = markup_off(block[0])
        if has_deadline(chunk):
            if not has_deadline(first_row):
                add(issues, "ERROR", "E-DEADLINE-NOT-IN-HEAD",
                    "срок спрятан в теле пункта: %s..." % first_row[:40])
        else:
            deadline_reported = True
            add(issues, "ERROR", "E-DEADLINE-MISSING",
                "временная акция без срока: %s..." % first_row[:40])

    # Акция бывает и вне списка. Тогда срок обязан быть хотя бы где-то в тексте.
    if not deadline_reported and has_any(low, TEMPORAL) and not has_deadline(body):
        add(issues, "ERROR", "E-DEADLINE-MISSING",
            "временная акция без срока: срок идёт в первую строку пункта")

    # --- объём ---
    size = len(unlink(body).strip())
    low_limit, high_limit = LENGTHS.get(rubric, (400, 1600))
    if size < low_limit:
        add(issues, "WARN", "W-LEN-SHORT",
            "коротко: %d знаков, нижняя граница %d" % (size, low_limit))
    elif size > high_limit:
        add(issues, "WARN", "W-LEN-LONG",
            "длинно: %d знаков, верхняя граница %d" % (size, high_limit))

    if len(blocks) > SPLIT_ITEMS_SOFT:
        add(issues, "WARN", "W-ITEMS-MANY",
            "пунктов %d: больше семи значит остальное идёт в статью" % len(blocks))

    # --- разрез на пост плюс статью, пороги из reference/split.md ---
    full_size = len(unlink(text).strip())
    has_article = article_link(text)
    need_article = (
        size > SPLIT_HARD
        or len(blocks) > SPLIT_ITEMS_HARD
        or (media and size > MEDIA_BODY)
    )
    if media and full_size > CAPTION_LIMIT:
        add(issues, "ERROR", "E-CAPTION-LIMIT",
            "подпись к медиа %d знаков, предел %d" % (full_size, CAPTION_LIMIT))
    if full_size > TG_LIMIT:
        add(issues, "ERROR", "E-TG-LIMIT",
            "сообщение %d знаков, предел Telegram %d" % (full_size, TG_LIMIT))
    if need_article and not has_article:
        add(issues, "ERROR", "E-SPLIT-NEEDED",
            "тело %d знаков и пунктов %d: нужна статья на telegra.ph"
            % (size, len(blocks)))
    elif not need_article and size > SPLIT_SOFT and len(blocks) > SPLIT_ITEMS_SOFT \
            and not has_article:
        add(issues, "WARN", "W-SPLIT-SOON",
            "тело %d и пунктов %d: на грани разреза" % (size, len(blocks)))
    ann_size = len(unlink(body).strip())
    announce = kind == "анонс" or (
        kind == "авто" and has_article and not blocks and ann_size <= ANNOUNCE_MAX
    )
    if has_article and blocks:
        add(issues, "ERROR", "E-POST-RETELL",
            "при статье пост это анонс, а тут пунктов %d: пересказ убивает переход"
            % len(blocks))
    if announce:
        check_announce(issues, text, ann_size)
    if ARTICLE_PLACEHOLDER in text:
        add(issues, "WARN", "W-ARTICLE-PLACEHOLDER",
            "адрес статьи ещё не вставлен")

    # --- три блока, которые модель пришивает сама: reference/antislop.md ---
    hay = text.lower()
    for phrase in OBVIOUS_BLOCKS:
        if phrase in hay:
            add(issues, "ERROR", "E-OBVIOUS-BLOCK",
                "общий ликбез «%s»: подписчик это знает, оставь конкретный лимит"
                % phrase)
            break
    for phrase in SUBSCRIBE_CTA:
        if phrase in hay:
            add(issues, "ERROR", "E-SUBSCRIBE-CTA",
                "приглашение внутри текста «%s»: его место в футере и закрепе"
                % phrase)
            break
    if OLD_LABEL_RE.search(text):
        add(issues, "ERROR", "E-FOOTER-OLD-LABEL",
            "старый ярлык [DEMO]: канал в футере подписываем [ТГК]")

    # --- структурные следы машины: reference/beauty.md ---
    if PARTICIPLE_TAIL.search(body):
        add(issues, "WARN", "W-PARTICIPLE-TAIL",
            "деепричастный хвост после запятой: два коротких предложения живее")
    if NOMINAL_SUBJ.search(body):
        add(issues, "WARN", "W-NOMINAL-SUBJ",
            "отглагольное подлежащее вида «интеграция позволяет»: скажи, кто что делает")
    same_run = sentence_run(body)
    if same_run >= 3:
        add(issues, "WARN", "W-SENT-RUN",
            "%d предложения подряд одной длины: вставь короткое, ритм оживёт" % same_run)

    caps = [
        word
        for word in re.findall("[А-ЯЁ]{2,}|[A-Z]{2,}", unlink(body))
        if word not in CAPS_OK
    ]
    if len(caps) > 3:
        add(issues, "WARN", "W-CAPS-MANY", "капса много: %s" % ", ".join(caps[:6]))

    bangs = text.count("!") - len(re.findall("ВАЖНО!", text))
    if bangs > 1:
        add(issues, "WARN", "W-BANGS", "восклицательных знаков %d: хватает одного" % bangs)

    if len(EMOJI.findall(text)) > 2:
        add(issues, "WARN", "W-EMOJI-MANY", "эмодзи больше двух")

    if re.search("\\n\\s*\\n\\s*\\n", text):
        add(issues, "WARN", "W-DOUBLE-BLANK",
            "две пустые строки подряд: между блоками ровно одна")

    # --- ритм: цифры вместо пожеланий ---
    # Правило «до 12 слов» держит проверка абзаца ниже: одно длинное на абзац
    # разрешено. Здесь ловим только монстров, которые не читаются с телефона.
    for row in unlink(body).split("\n"):
        for sentence in sentences(row):
            if len(words(sentence)) > 20:
                add(issues, "WARN", "W-SENT-LONG",
                    "предложение на %d слов: %s..."
                    % (len(words(sentence)), sentence.strip()[:60]))

    for para in re.split("\\n\\s*\\n", unlink(body)):
        long_ones = [
            sentence
            for row in para.split("\n")
            for sentence in sentences(row)
            if len(words(sentence)) > 12
        ]
        if len(long_ones) > 1:
            add(issues, "WARN", "W-PARA-RHYTHM",
                "в абзаце %d длинных предложений: разрешено одно" % len(long_ones))

    sizes = [len(unlink("\n".join(block)).strip()) for block in blocks]
    for order in range(len(sizes) - 1):
        first, second = sizes[order], sizes[order + 1]
        if not first or not second:
            continue
        diff = abs(first - second) / float(max(first, second))
        if diff < 0.15:
            add(issues, "WARN", "W-SYMMETRY",
                "пункты %d и %d почти одинаковой длины (%d и %d знаков): разница нужна от 15 процентов"
                % (order + 1, order + 2, first, second))

    opens = []
    for line in body_filled:
        clean = markup_off(line)
        if not clean or clean == FOOTER:
            continue
        first_word = words(clean)
        if not first_word:
            continue
        opens.append((norm(first_word[0]), word_class(first_word[0])))

    # Строки, начатые с существительного или с названия сервиса, это норма для русского.
    # Машину выдают одинаковые глаголы, прилагательные, числа и предлоги три раза подряд.
    SYMMETRY_CLASSES = ("глагол", "прилагательное", "числительное", "предлог")
    streak = 1
    for order in range(1, len(opens)):
        if (
            opens[order][1] == opens[order - 1][1]
            and opens[order][1] in SYMMETRY_CLASSES
        ):
            streak += 1
        else:
            streak = 1
        if streak >= 3:
            add(issues, "WARN", "W-POS-STREAK",
                "три строки подряд начинаются с одной части речи (%s)" % opens[order][1])
            break

    streak = 1
    for order in range(1, len(opens)):
        if opens[order][0] == opens[order - 1][0]:
            streak += 1
        else:
            streak = 1
        if streak >= 3:
            add(issues, "WARN", "W-OPENERS",
                "три строки подряд начинаются с одного слова «%s»" % opens[order][0])
            break

    # --- живое и риски ---
    if "))" not in text and not has_any(low, LEXICON):
        add(issues, "WARN", "W-NO-LEXICON", "нет живой детали: своя оценка, своё слово или ))")

    if "ВАЖНО!" not in text:
        for pattern, why in RISK:
            if re.search(pattern, text, re.I):
                add(issues, "WARN", "W-RISK-NO-IMPORTANT", "риск «%s» без блока ВАЖНО!" % why)
                break

    if re.search("^\\s*Инструкция:", text, re.M | re.I):
        add(issues, "WARN", "W-INSTRUCTION-WORD",
            "«Инструкция:» - у автора это «Как забрать:» или «Что нужно делать:»")

    if re.search("\\bты\\b", low):
        add(issues, "WARN", "W-TY-ADDRESS", "обращение «ты»: канал говорит «мы» и «вы»")

    for parasite in PARASITE:
        hits = len(re.findall("\\b%s\\b" % parasite, low))
        if hits >= 3:
            add(issues, "WARN", "W-PARASITE",
                "слово-паразит «%s» %d раза" % (parasite, hits))

    # --- бренд: DEMO против ВТОРОЙ БРЕНД ---
    if brand == "second-brand":
        if (FOOTER_ON and FOOTER in text) or FOOTER_PLAIN_RE.search(text):
            add(issues, "ERROR", "E-BRAND-FOOTER",
                "футер DEMO в мем-тексте: у ВТОРОЙ БРЕНД футера не бывает")
        for word in OFFER_WORDS:
            if word in low:
                add(issues, "ERROR", "E-BRAND-OFFER",
                    "оффер «%s» в мем-тексте: мем ничего не продаёт" % word)
                break
        clean = "\n".join(line for line in lines if line.strip() != FOOTER)
        if re.search("https?://", clean) or re.search(LINK, clean):
            add(issues, "ERROR", "E-MEME-LINK",
                "ссылка в меме: она живёт только в закрепе и в описании канала")
        joke = norm(nolinks(text))
        for item in load_meme_log():
            if item["template"] and item["template"] in low:
                add(issues, "WARN", "W-MEME-REPEAT",
                    "шаблон «%s» уже выходил %s" % (item["template"], item["date"]))
                break
            if item["text"] and jaccard(joke, norm(item["text"])) >= 0.6:
                add(issues, "WARN", "W-MEME-REPEAT",
                    "шутка близка к вышедшей: %s" % item["text"])
                break

    # --- реклама: без маркировки пост не выходит ---
    if rubric == "реклама" or has_any(low, AD_SIGNS):
        missing = []
        if not re.match("^\\s*реклама\\b", markup_off(filled[0]), re.I):
            missing.append("пометки «Реклама» в первой строке")
        if "erid" not in low:
            missing.append("токена erid от ОРД")
        if missing:
            add(issues, "ERROR", "E-AD-NO-MARK",
                "рекламный пост без %s" % " и без ".join(missing))

    # --- план распространения, только по флагу --growth ---
    if growth and not re.search(GROWTH_MARK, text, re.M):
        add(issues, "WARN", "W-GROWTH-NO-PLAN",
            "нет плана распространения: три строки Приток, Действие, Замер")

    if announce:
        issues = [item for item in issues if item["code"] not in ANNOUNCE_SKIP]

    if brand == "second-brand":
        issues = [item for item in issues if item["code"] not in NEROBIT_SKIP]

    return issues, rubric


def split_levels(issues, strict=False):
    errors = [item for item in issues if item["level"] == "ERROR"]
    warns = [item for item in issues if item["level"] == "WARN"]
    if strict:
        return errors + warns, []
    return errors, warns


# ---------------------------------------------------------------------------
# Автоправка. Всю механику чинит скрипт, модель занимается только смыслом.
# Слабая модель плохо чинит текст по описанию ошибки, зато умеет запустить команду.
# ---------------------------------------------------------------------------

ARROWS = "\u2192\u2190\u21d2\u21d0\u27a1\u2794\u21aa\u21b3"
BULLET_CHARS = "\u2022\u25cf\u25aa\u25e6\u2023\u00b7\u27a4\u25b6\u2713\u2714\u2705\u2726"
NBSPS = "\u00a0\u202f\u2007\u2009\u200a\u2060\ufeff\u200b"


def _plain_char(char):
    """Юникод-украшение в обычную букву или цифру. Кириллица не страдает."""
    import unicodedata

    if ord(char) < 128:
        return char
    if unicodedata.category(char) not in ("Lu", "Ll", "Nd", "No"):
        return char
    flat = unicodedata.normalize("NFKC", char)
    if flat != char and 0 < len(flat) <= 2 and all(ord(item) < 128 for item in flat):
        return flat
    return char


def _has_circled(text):
    return any(0x2460 <= ord(char) <= 0x24FF for char in text)


def _flatten(text):
    return "".join(_plain_char(char) for char in text)


def _dashes(text):
    """Правило ноль автора: длинных тире не бывает нигде."""
    out = []
    for line in text.split("\n"):
        if "dash-demo" in line:
            out.append(line)
            continue
        for char in EMDASHES:
            line = line.replace(char, "-")
        out.append(line)
    return "\n".join(out)


def _arrows(text):
    for char in ARROWS:
        text = text.replace(char, "-")
    return text


def _bullets(text):
    """Кружки и галочки в начале строки становятся нумерацией."""
    out = []
    counter = 0
    for line in text.split("\n"):
        stripped = line.strip()
        hit = re.match(r"^(\d+)[.)]\s", stripped)
        if hit:
            counter = int(hit.group(1))
            out.append(line)
            continue
        if stripped and stripped[0] in BULLET_CHARS and len(stripped) > 1:
            rest = stripped[1:].strip()
            # За буллетом часто идёт второй маркер: кружок-цифра или цифра с точкой.
            # Его сносим, иначе нумерация двоится вида «1. 1 Название».
            rest = re.sub(r"^[\u2460-\u24ff]\s*", "", rest)
            rest = re.sub(r"^\d+[.)]\s+", "", rest)
            counter += 1
            out.append("%d. %s" % (counter, rest))
            continue
        if stripped and 0x2460 <= ord(stripped[0]) <= 0x24FF and len(stripped) > 1:
            flat = _flatten(stripped[0]).strip()
            counter = int(flat) if flat.isdigit() else counter + 1
            out.append("%d. %s" % (counter, stripped[1:].strip()))
            continue
        if stripped:
            counter = 0
        out.append(line)
    body = "\n".join(out)
    for char in BULLET_CHARS:
        body = body.replace(char, "-")
    return body


def _headings(text):
    """Telegram не рендерит решётки, заголовок там только жирный."""
    return re.sub(
        r"(?m)^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t]*$",
        lambda hit: "**%s**" % hit.group(1).strip("*# "),
        text,
    )


def _spaces(text):
    for char in NBSPS:
        text = text.replace(char, " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"(\S)[ \t]{2,}(\S)", r"\1 \2", text)
    return text


def _blanks(text):
    return re.sub(r"\n{3,}", "\n\n", text)


def _bangs(text):
    return re.sub(r"!{2,}", "!", text)


def _typo(text):
    text = text.replace("\u2026", "...")
    text = text.replace("\u201c", "\u00ab").replace("\u201d", "\u00bb")
    text = text.replace("\u201e", "\u00ab").replace("\u201f", "\u00ab")
    return text


def _tail(text, rubric):
    """Хвост поста собирается заново: концовка, хэштег, пустая строка, футер."""
    keep = []
    for line in text.split("\n"):
        # Любой футерный ряд сносим целиком, включая старый ярлык [DEMO]:
        # иначе правка дописывала второй футер вместо замены ярлыка.
        if footer_row(line):
            continue
        keep.append(line.rstrip())
    tags = [line.strip() for line in keep if re.match(r"^#[^\s#]+$", line.strip())]
    keep = [line for line in keep if not re.match(r"^#[^\s#]+$", line.strip())]
    while keep and not keep[-1].strip():
        keep.pop()
    if not tags and rubric:
        tags = ["#" + rubric]
    body = "\n".join(keep)
    if tags:
        body += "\n\n" + "\n".join(tags)
    if not FOOTER_ON:
        return body + "\n"
    return body + "\n\n" + FOOTER + "\n"


def autofix(text, rubric=None, media=False, brand=None):
    """Починить всё, что чинится без участия смысла.

    Возвращает новый текст и список того, что было сделано.
    Смысловые ошибки вида тизера или голого крючка не трогает совсем.
    """
    applied = []

    def mark(code, what):
        applied.append({"code": code, "what": what})

    def step(code, what, func):
        nonlocal text
        new = func(text)
        if new != text:
            text = new
            mark(code, what)

    step("E-EMDASH", "длинные тире стали дефисами", _dashes)
    step("E-ARROW", "стрелки убраны", _arrows)
    step("E-BULLET", "кружки списка стали цифрами", _bullets)
    if _has_circled(text):
        step("E-CIRCLED", "кружки-цифры стали обычными цифрами", _flatten)
    step("E-BOLD-UNICODE", "юникод-жир стал обычными буквами", _flatten)
    step("E-MD-HEADING", "заголовки с решётками стали жирными", _headings)
    step("W-BANGS", "серии восклицательных знаков сжаты", _bangs)
    step("W-DOUBLE-BLANK", "двойные пустые строки убраны", _blanks)
    step("FIX-SPACES", "невидимые пробелы и двойные отступы убраны", _spaces)
    step("FIX-TYPO", "троеточие и кавычки приведены к обычным", _typo)

    # У мема нет ни футера, ни хвоста поста: достраивать его нечем.
    if detect_brand(text, brand) == "second-brand":
        return text, applied

    known = rubric or detect_rubric(text)
    rows = text.split("\n")
    filled = [line for line in rows if line.strip()]
    had_footer = FOOTER in text
    footish = any(footer_row(line) for line in rows)
    stale = footish and bool(OLD_LABEL_RE.search(text))
    was_last = bool(filled) and footer_row(filled[-1])
    had_tag = bool(find_hashtags(text))
    if stale:
        code, what = "E-FOOTER-OLD-LABEL", "устаревший ярлык в футере заменён на актуальный"
    elif FOOTER_ON and not footish:
        code, what = "E-FOOTER-MISSING", "футер бренда встал последней строкой"
    elif FOOTER_ON and not had_footer:
        code, what = "E-FOOTER-PLAIN", "футер пересобран по образцу со ссылками"
    elif not was_last:
        code, what = "E-FOOTER-NOT-LAST", "футер перенесён в самый низ"
    elif not had_tag and known:
        code, what = "E-HASHTAG-MISSING", "хэштег рубрики встал перед футером"
    else:
        code, what = "W-HASHTAG-PLACE", "хвост поста выровнен: хэштег, пустая строка, футер"
    step(code, what, lambda body: _tail(body, known))

    return text, applied


def use_demo_profile():
    """Тесты гоняем на демо-профиле: чужой бренд не должен их ронять."""
    demo = P.load(path=P.EXAMPLE)
    box = globals()
    box["PROFILE"] = demo
    box["FOOTER"] = P.footer(demo)
    box["FOOTER_ON"] = True
    box["FOOTER_PLAIN_RE"] = P.footer_plain_re(demo) or NEVER_RE
    box["FOOTER_MARKS"] = P.footer_marks(demo)
    box["OLD_LABEL_RE"] = P.legacy_label_re(demo) or NEVER_RE
    box["RUBRICS"] = P.rubric_names(demo)
    box["LENGTHS"] = P.lengths(demo)
    box["FORWARD_REQUIRED"] = P.forward_required(demo)
    box["FORWARD_WANTED"] = P.forward_wanted(demo)
    box["SOFT_FIRST_SCREEN"] = P.soft_first_screen(demo)
    return demo


def fix_selftest():
    """Автоправка меняет чужой текст, значит её страхуем тестами."""
    use_demo_profile()
    checks = []

    # Старый ярлык в футере: правка меняет ярлык, а не дописывает второй футер.
    stale = ("Здарова.\n\nСобрал подборку сервисов.\n\n#сервисы\n\n"
             "[ЧАТ](https://t.me/demo_chat) | "
             "[GITHUB](https://github.com/demo) | "
             "[YOUTUBE](https://www.youtube.com/@demo) | "
             "[DEMO](https://t.me/demo_channel)")
    fixed, applied = autofix(stale, rubric="сервисы")
    rows = [row for row in fixed.split("\n") if row.strip()]
    checks.append(("старый ярлык ушёл", "[DEMO]" not in fixed))
    checks.append(("футер один, а не два",
                   sum(1 for row in rows if footer_row(row)) == 1))
    checks.append(("футер эталонный и последний", rows[-1] == FOOTER))
    checks.append(("правка названа своим кодом",
                   any(item["code"] == "E-FOOTER-OLD-LABEL" for item in applied)))
    checks.append(("хэштег рубрики на месте", "#сервисы" in fixed))
    left = [item["code"] for item in lint(fixed, "сервисы")[0]]
    checks.append(("после правки претензий к футеру нет",
                   not [code for code in left if code.startswith("E-FOOTER")]))
    checks.append(("старый ярлык не плодит лишних претензий",
                   "W-LABEL-NONSTD" not in
                   [item["code"] for item in lint(stale, "сервисы")[0]]))

    fixed, applied = autofix("Здарова. Дали 5 запросов \u2014 забирай", rubric="абуз")
    checks.append(("тире ушло", not any(char in fixed for char in EMDASHES)))
    checks.append(("правка отмечена", any(item["code"] == "E-EMDASH" for item in applied)))

    fixed, _ = autofix("Регаешься \u2192 получаешь доступ", rubric="абуз")
    checks.append(("стрелка ушла", "\u2192" not in fixed))

    fixed, _ = autofix(
        "Список:\n\u2022 первый\n\u2022 второй\n\u2022 третий", rubric="сервисы"
    )
    checks.append(
        ("кружки стали цифрами", "1. первый" in fixed and "3. третий" in fixed)
    )

    fixed, _ = autofix("\u2022 \u2460 Diagram\n\u2022 \u2461 Flux", rubric="сервисы")
    checks.append(
        ("нумерация не двоится", "1. Diagram" in fixed and "2. Flux" in fixed)
    )

    fixed, _ = autofix("\u2460 Первый\n\u2461 Второй", rubric="сервисы")
    checks.append(
        (
            "кружок без буллета стал пунктом",
            "1. Первый" in fixed and "2. Второй" in fixed,
        )
    )

    fixed, _ = autofix("План на 5 шагов\n\u2022 5 минут на регу", rubric="гайд")
    checks.append(
        ("цифра внутри пункта цела", "1. 5 минут на регу" in fixed)
    )

    fixed, _ = autofix("Пункт \u2460 и пункт \u2461", rubric="абуз")
    checks.append(("кружки-цифры стали цифрами", "\u2460" not in fixed and "1" in fixed))

    fixed, _ = autofix("\U0001d413\U0001d428\U0001d429 модели", rubric="сервисы")
    checks.append(("юникод-жир стал обычным", "Top" in fixed))

    fixed, _ = autofix("## Заголовок\nтекст", rubric="гайд")
    checks.append(
        ("заголовок стал жирным", "**Заголовок**" in fixed and "## " not in fixed)
    )

    fixed, _ = autofix("Текст без хвоста", rubric="абуз")
    rows = [line for line in fixed.split("\n") if line.strip()]
    checks.append(("футер встал последним", rows[-1] == FOOTER))
    checks.append(("хэштег встал перед футером", rows[-2] == "#абуз"))

    moved = "Текст\n" + FOOTER + "\nещё строка\n\n#абуз"
    fixed, _ = autofix(moved, rubric="абуз")
    rows = [line for line in fixed.split("\n") if line.strip()]
    checks.append(
        ("футер перенесён вниз", rows[-1] == FOOTER and rows[-2] == "#абуз")
    )

    fixed, _ = autofix("Раз\n\n\n\nДва", rubric="абуз")
    checks.append(("тройные пустые строки убраны", "\n\n\n" not in fixed))

    twice, again = autofix(fixed, rubric="абуз")
    checks.append(("правка идемпотентна", twice == fixed and not again))

    dirty = "## План!!!\n\u2022 раз \u2014 два\n\u2022 три \u2192 четыре"
    cleaned, _ = autofix(dirty, rubric="гайд")
    before = len([item for item in lint(dirty, "гайд")[0] if item["level"] == "ERROR"])
    after = len([item for item in lint(cleaned, "гайд")[0] if item["level"] == "ERROR"])
    checks.append(("ошибок стало меньше", after < before))

    failed = 0
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            failed += 1
    print("Итого: %d проверок автоправки, провалилось %d" % (len(checks), failed))
    return 1 if failed else 0


def report(name, issues, rubric, strict, as_json, brand="vs"):
    errors, warns = split_levels(issues, strict)

    if as_json:
        payload = {
            "version": VERSION,
            "brand": brand,
            "file": name,
            "rubric": rubric,
            "strict": bool(strict),
            "clean": not errors and not warns,
            "errorCount": len(errors),
            "warnCount": len(warns),
            "errors": [
                {"code": item["code"], "message": item["message"],
                 "hint": hint_for(item["code"])} for item in errors
            ],
            "warns": [
                {"code": item["code"], "message": item["message"],
                 "hint": hint_for(item["code"])} for item in warns
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    if rubric:
        print("Рубрика: #%s%s" % (rubric, " (--strict)" if strict else ""))
    elif strict:
        print("Рубрика не распознана (--strict)")
    if brand == "second-brand":
        print("Бренд: ВТОРОЙ БРЕНД. Правила DEMO про футер, оффер и длину сняты")

    if errors:
        print("ERROR (%d) - публиковать нельзя:" % len(errors))
        for item in errors:
            print("  - [%s] %s" % (item["code"], item["message"]))
            print("      как исправить: %s" % hint_for(item["code"]))
    if warns:
        print("WARN (%d) - посмотреть глазами:" % len(warns))
        for item in warns:
            print("  - [%s] %s" % (item["code"], item["message"]))
    if not errors and not warns:
        print("Чисто. Пост можно отдавать автору.")
    elif not errors:
        print("ERROR нет. Предупреждения выше - на твоё решение.")

    return 1 if errors else 0


def read_fixtures(tests):
    """Фикстуры лежат одним файлом tests/fixtures.md, чтобы не плодить мелочь.

    Формат простой: между <!-- FIXTURE: имя --> и <!-- /FIXTURE --> лежит тело.
    Отдельные файлы тоже работают: их читаем напрямую.
    """
    path = os.path.join(tests, "fixtures.md")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    out = {}
    for chunk in text.split("<!-- FIXTURE: ")[1:]:
        head, _, rest = chunk.partition(" -->\n")
        body, _, _ = rest.partition("<!-- /FIXTURE -->")
        out[head.strip()] = body.rstrip("\n") + "\n"
    return out


def selftest():
    """Прогнать tools/tests/ и проверить сам линтер.

    Линтер уже ловил ложные ошибки в своих же регулярках, тесты страхуют от повтора.
    """
    use_demo_profile()
    tests = os.path.join(HERE, "tests")
    manifest_path = os.path.join(tests, "manifest.json")
    if not os.path.exists(manifest_path):
        print("нет tools/tests/manifest.json")
        return 1

    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    failed = 0
    bundle = read_fixtures(tests)
    cases = manifest.get("cases", [])
    for case in cases:
        path = os.path.join(tests, case["file"])
        if case["file"] in bundle:
            text = bundle[case["file"]]
        elif os.path.exists(path):
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        else:
            print("FAIL %s: файла нет ни в папке, ни в fixtures.md" % case["file"])
            failed += 1
            continue

        strict = bool(case.get("strict"))
        issues, _ = lint(text, case.get("rubric"), brand=case.get("brand"))
        errors, warns = split_levels(issues, strict)
        codes = set(item["code"] for item in issues)
        problems = []

        if case.get("expect") == "clean":
            if errors:
                problems.append(
                    "ожидали чисто, получили: "
                    + ", ".join(
                        "%s (%s)" % (item["code"], item["message"]) for item in errors
                    )
                )
            if warns:
                problems.append(
                    "лишние предупреждения: "
                    + ", ".join(item["code"] for item in warns)
                )
        else:
            if not errors:
                problems.append("ожидали ERROR, линтер промолчал")
            missing = [code for code in case.get("codes", []) if code not in codes]
            if missing:
                problems.append("не поймано: " + ", ".join(missing))

        extra = [code for code in case.get("forbidden", []) if code in codes]
        if extra:
            problems.append("ложная ошибка: " + ", ".join(extra))

        if problems:
            failed += 1
            print("FAIL %s" % case["file"])
            for problem in problems:
                print("    %s" % problem)
        else:
            print("PASS %s" % case["file"])

    print("Итого: %d тестов, провалилось %d" % (len(cases), failed))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(
        description="Линтер постов по профилю бренда"
    )
    parser.add_argument("file", nargs="?", help="файл с черновиком, без аргумента читает stdin")
    parser.add_argument("--strict", action="store_true", help="все предупреждения становятся ошибками")
    parser.add_argument("--json", action="store_true", dest="as_json", help="машинный вывод для агента")
    parser.add_argument("--rubric", help="рубрика без решётки, если хэштега в тексте ещё нет")
    parser.add_argument("--brand", default="vs", choices=list(BRANDS),
                        help="бренд текста, по умолчанию vs")
    parser.add_argument("--growth", action="store_true",
                        help="требовать план распространения в конце черновика")
    parser.add_argument("--kind", default="авто",
                        choices=["авто", "пост", "анонс"],
                        help="форма текста: анонс это пост при статье, без пунктов")
    parser.add_argument("--media", action="store_true", help="пост идёт с фото или альбомом: лимит подписи")
    parser.add_argument("--fix", action="store_true",
                        help="починить механику: тире, стрелки, кружки, заголовки, хэштег, футер")
    parser.add_argument("--out", help="куда записать исправленный текст, по умолчанию тот же файл")
    parser.add_argument("--selftest", action="store_true", help="прогнать tools/tests/")
    parser.add_argument("--selftest-fix", action="store_true", dest="selftest_fix",
                        help="прогнать проверки автоправки")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if args.selftest_fix:
        return fix_selftest()

    if args.file:
        text = P.read_post(args.file)
        name = args.file
    else:
        text = sys.stdin.read()
        name = "stdin"

    if args.fix:
        text, applied = autofix(text, args.rubric, args.media, args.brand)
        target = args.out or args.file
        lines = []
        if applied:
            lines.append("Автоправка: %d штук" % len(applied))
            for item in applied:
                lines.append("  - [%s] %s" % (item["code"], item["what"]))
        else:
            lines.append("Автоправка: чинить было нечего")
        if not target:
            sys.stdout.write(text)
            sys.stderr.write("\n".join(lines) + "\n")
            return 0
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        lines.append("Записано: %s" % target)
        if args.as_json:
            sys.stderr.write("\n".join(lines) + "\n")
        else:
            print("\n".join(lines))
            print("")
        name = target

    issues, rubric = lint(text, args.rubric, args.media, args.brand, args.growth,
                          args.kind)
    return report(name, issues, rubric, args.strict, args.as_json,
                  detect_brand(text, args.brand))


if __name__ == "__main__":
    sys.exit(main())
