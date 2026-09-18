#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
split_post.py 1.0.0
Решает, нужно ли резать пост на два уровня (Telegram плюс статья на telegra.ph),
и если нужно, сам готовит обе части.
Только стандартная библиотека. Пороги взяты из reference/split.md.
"""

import argparse
import json
import os
import re
import sys

VERSION = "6.2.1"

TG_HARD_LIMIT = 4096          # технический предел сообщения
TG_CAPTION_LIMIT = 1024       # предел подписи к медиа
FOOTER_RESERVE = 130          # сколько съедает футер
SOFT_ONE_POST = 1400          # ниже этого резать нечего
SOFT_CORRIDOR = 2200          # выше этого статья обязательна
ITEMS_CORRIDOR = 7            # больше этого в коридоре 1400-2200 значит статья
ITEMS_HARD = 8                # больше этого статья при любой длине
MEDIA_BODY_LIMIT = 900        # фото плюс тело больше этого значит статья
KEEP_ITEMS = 3                # сколько пунктов остаётся в посте

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import profile as P  # noqa: E402

# Футер и подпись статьи берём из профиля, а не из чужого бренда.
PROFILE = P.load()
FOOTER = P.footer(PROFILE) if P.footer_enabled(PROFILE) else ""
AUTHOR = P.article_author(PROFILE)
LINKS = P.links(PROFILE)
FOOTER_MARK = (re.sub("^https?://(www[.])?", "", LINKS[0][1])
               if LINKS else "футера-в-профиле-нет")
PLACEHOLDER = "PASTE_TELEGRAPH_URL"
ARTICLE_HEAD = "=== СТАТЬЯ НА TELEGRA.PH ==="
POST_HEAD = "=== ПОСТ В TELEGRAM ==="

ITEM_RE = re.compile(r"^\s*(?:\*\*)?(\d{1,2})[.)]\s", re.MULTILINE)
HASHTAG_LINE_RE = re.compile(r"^\s*#[^\s#]+\s*$")
# Точка предложения часто прячется под жирным: «честные.**» это тоже конец.
SENT_SPLIT = re.compile(r"(?<=[.!?])(?:\*\*|__|[*_`])*\s+")
TITLE_MIN, TITLE_MAX = 40, 70   # коридор заголовка статьи: reference/publish.md
HASHTAG_RE = re.compile(r"#([а-яёa-z]+)", re.IGNORECASE)
MONEY_RE = re.compile(r"\d[\d\s.,]*\s?(?:\$|₽|руб|USD|EUR|%)|\$\s?\d", re.IGNORECASE)
NUM_RE = re.compile(r"\d")
FREE_RE = re.compile(r"без карт|без vpn|без регистрации|бесплатн|бесплатно|даром",
                     re.IGNORECASE)
TIME_RE = re.compile(r"минут|часа|часов|дней|секунд", re.IGNORECASE)


def read_source(path):
    if not path or path == "-":
        return sys.stdin.read()
    return P.read_post(path)


def strip_footer(text):
    lines = text.rstrip().split("\n")
    footer = ""
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and FOOTER_MARK in lines[-1]:
        footer = lines.pop().strip()
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines), footer


def find_items(body):
    """Режет тело на голову, нумерованные пункты и хвост."""
    starts = [m.start() for m in ITEM_RE.finditer(body)]
    if not starts:
        return body.strip(), [], ""
    head = body[:starts[0]].strip()
    items = []
    for index, begin in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(body)
        items.append(body[begin:end].strip())
    tail = ""
    if items:
        last = items[-1]
        parts = last.split("\n\n")
        if len(parts) > 1:
            items[-1] = parts[0].strip()
            tail = "\n\n".join(parts[1:]).strip()
    return head, items, tail


def score_item(text):
    """Скоринг из reference/split.md: что оставляем в посте."""
    score = 0
    if MONEY_RE.search(text):
        score += 2
    elif NUM_RE.search(text) and TIME_RE.search(text):
        score += 2
    if FREE_RE.search(text):
        score += 2
    body = re.sub(r"\s+", " ", text)
    if len(body) <= 160:
        score += 1
    if "](" in text:
        score += 1
    return score


def rubric_of(text):
    tags = HASHTAG_RE.findall(text)
    return tags[0].lower() if tags else ""


def verdict(text, media=False):
    body, footer = strip_footer(text)
    head, items, tail = find_items(body)
    body_len = len(body)
    total_len = len(text)
    reasons = []
    need = False

    if media and body_len > MEDIA_BODY_LIMIT:
        need = True
        reasons.append("есть медиа, тело %d больше %d, подпись обрежется на %d"
                       % (body_len, MEDIA_BODY_LIMIT, TG_CAPTION_LIMIT))
    if len(items) > ITEMS_HARD:
        need = True
        reasons.append("пунктов %d, больше %d" % (len(items), ITEMS_HARD))
    if body_len > SOFT_CORRIDOR:
        need = True
        reasons.append("тело %d больше %d" % (body_len, SOFT_CORRIDOR))
    elif body_len > SOFT_ONE_POST and len(items) > ITEMS_CORRIDOR:
        need = True
        reasons.append("тело %d в коридоре и пунктов %d больше %d"
                       % (body_len, len(items), ITEMS_CORRIDOR))
    if total_len > TG_HARD_LIMIT:
        need = True
        reasons.append("всё сообщение %d, технический предел %d" % (total_len, TG_HARD_LIMIT))
    if not need and body_len > SOFT_ONE_POST:
        reasons.append("тело %d в коридоре %d-%d, режь слабые пункты внутри поста"
                       % (body_len, SOFT_ONE_POST, SOFT_CORRIDOR))
    if not reasons:
        reasons.append("тело %d ниже %d, статья не нужна" % (body_len, SOFT_ONE_POST))

    return {
        "need_article": need,
        "body_chars": body_len,
        "total_chars": total_len,
        "items": len(items),
        "rubric": rubric_of(text),
        "media": bool(media),
        "has_footer": bool(footer),
        "reasons": reasons,
        "_parts": {"head": head, "items": items, "tail": tail, "footer": footer},
    }


def flat(text):
    """Текст без разметки и лишних пробелов: им сравниваем и считаем длину."""
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", text or "")).strip()


def drop_hashtags(text):
    """Хэштег рубрики живёт только в посте.

    В статье строка с решёткой читается как заголовок первого уровня,
    а телеграф ждёт ### и ####: lint_article ловит это как E-A-HEADING.
    """
    rows = [row for row in (text or "").split("\n")
            if not HASHTAG_LINE_RE.match(row)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(rows)).strip()


def title_of(lead, items, rubric):
    """Заголовок статьи это имя материала, а не приветствие.

    Приветствие уезжает в анонс, поэтому сюда приходит вторая строка
    первого экрана. Если имя короче коридора, добираем вторым
    предложением, пока влезает: коридор 40-70 из reference/publish.md.
    """
    source = re.sub(r"^#+\s*", "", flat(lead))
    if not source and items:
        source = flat(items[0])
    parts = [part.strip() for part in SENT_SPLIT.split(source) if part.strip()]
    title = parts[0] if parts else source
    index = 1
    while len(title) < TITLE_MIN and index < len(parts):
        longer = title.rstrip(" .!?:") + ". " + parts[index]
        if len(longer) > TITLE_MAX:
            break
        title = longer
        index += 1
    title = title.rstrip(" .!?:")
    if len(title) > TITLE_MAX:
        title = title[:TITLE_MAX].rsplit(" ", 1)[0].rstrip(" ,.:;-")
    if not title:
        title = "Подборка %s" % (rubric or "материалов")
    return title


def renumber(items):
    out = []
    for index, item in enumerate(items, 1):
        out.append(ITEM_RE.sub(lambda m, n=index: m.group(0).replace(m.group(1), str(n), 1),
                               item, count=1))
    return out


def build(text, media=False):
    data = verdict(text, media)
    parts = data.pop("_parts")
    head, items, tail, footer = parts["head"], parts["items"], parts["tail"], parts["footer"]
    footer = footer or FOOTER
    rubric = data["rubric"]

    if not data["need_article"]:
        return data, None, text.rstrip()

    if not items:
        chunks = [c.strip() for c in head.split("\n\n") if c.strip()]
        keep_head = "\n\n".join(chunks[:2])
        rest = "\n\n".join(chunks[2:])
        items, head = [], keep_head
        stay, moved = [], [rest] if rest else []
    else:
        ranked = sorted(range(len(items)), key=lambda i: (-score_item(items[i]), i))
        keep_index = sorted(ranked[:KEEP_ITEMS])
        stay = [items[i] for i in keep_index]
        moved = [items[i] for i in range(len(items)) if i not in keep_index]

    # Первый экран черновика: сначала приветствие, потом имя материала.
    # Приветствие уезжает в анонс, имя становится заголовком статьи.
    rows = [row.strip() for row in head.split("\n") if row.strip()] if head else []
    greeting = rows[0] if len(rows) > 1 else ""
    lead = " ".join(rows[1:]) if len(rows) > 1 else (rows[0] if rows else "")
    title = title_of(lead, items, rubric)

    # Вступление статьи это тот же первый экран без приветствия и без
    # первого предложения, которое уже ушло в заголовок.
    intro = "\n".join(rows[1:] if greeting else rows).strip()
    halves = SENT_SPLIT.split(intro, maxsplit=1)
    if halves and flat(halves[0]).rstrip(" .!?:").startswith(title[:20]):
        intro = halves[1].strip() if len(halves) > 1 else ""
    intro = drop_hashtags(intro)

    article = ["Заголовок: %s" % title, "", "Автор: %s" % AUTHOR, ""]
    if intro:
        article.append(intro)
        article.append("")
    article.append("### Список" if items else "### Подробно")
    article.append("")
    for item in renumber(items if items else moved):
        article.append(drop_hashtags(item))
        article.append("")
    if tail:
        article.append(drop_hashtags(tail))
        article.append("")

    # Есть статья значит пост это анонс: приветствие, название ссылкой,
    # хэштег и футер. Пункты в анонс не переносим: reference/split.md.
    name = re.sub(r"\s+", " ", re.sub(r"^#+\s*", "", lead or title)).strip()
    name = re.split(r"(?<=[.!?])\s", name)[0].strip()
    if not name:
        name = "Собрал подборку целиком"
    if name[-1] not in ".!?":
        name += "."

    post = []
    if greeting:
        post.append(greeting)
        post.append("")
    post.append("[%s](%s)" % (name, PLACEHOLDER))
    post.append("")
    if rubric:
        post.append("#" + rubric)
        post.append("")
    post.append(footer)

    article_text = re.sub(r"\n{3,}", "\n\n", "\n".join(article)).strip()
    post_text = re.sub(r"\n{3,}", "\n\n", "\n".join(post)).strip()
    data["post_chars_after"] = len(post_text)
    data["article_chars"] = len(article_text)
    data["title"] = title
    data["title_ok"] = TITLE_MIN <= len(title) <= TITLE_MAX
    # В анонсе пунктов нет: всё содержание уезжает в статью.
    data["items_kept"] = 0
    data["items_moved"] = len(items) if items else len(moved)
    return data, article_text, post_text


def report(data):
    lines = ["SPLIT: %s" % ("нужна статья на telegra.ph" if data["need_article"]
                          else "один пост, статья не нужна")]
    lines.append("тело: %d знаков | всё сообщение: %d | пунктов: %d | рубрика: %s"
                 % (data["body_chars"], data["total_chars"], data["items"],
                    data["rubric"] or "нет"))
    for reason in data["reasons"]:
        lines.append("  причина: %s" % reason)
    if data.get("post_chars_after"):
        lines.append("после разреза: пост %d знаков, статья %d знаков, осталось пунктов %d, уехало %d"
                     % (data["post_chars_after"], data["article_chars"],
                        data["items_kept"], data["items_moved"]))
    if data.get("title"):
        lines.append("заголовок статьи: %s (%d знаков%s)"
                     % (data["title"], len(data["title"]),
                        "" if data.get("title_ok")
                        else ", коридор %d-%d пробит, допиши руками"
                        % (TITLE_MIN, TITLE_MAX)))
    if data["need_article"]:
        lines.append("порядок: публикуешь статью, подставляешь адрес вместо %s, потом пост"
                     % PLACEHOLDER)
    return "\n".join(lines)


def use_demo_profile():
    """Резку проверяем на демо-профиле, чтобы чужой бренд не ломал тесты."""
    demo = P.load(path=P.EXAMPLE)
    box = globals()
    box["PROFILE"] = demo
    box["FOOTER"] = P.footer(demo)
    box["AUTHOR"] = P.article_author(demo)
    links = P.links(demo)
    box["FOOTER_MARK"] = (re.sub("^https?://(www[.])?", "", links[0][1])
                          if links else "футера-в-профиле-нет")
    return demo


def selftest():
    use_demo_profile()
    short = "Привет.\n\n**1. Сервис.** Польза за 0 рублей. [ТЫК](https://a.b)\n\n#сервисы\n\n" + FOOTER
    long_items = ["**%d. Сервис №%d.** Даёт %d запросов бесплатно и работает без карты. "
                  "[ТЫК](https://example.com/%d)" % (i, i, i * 100, i)
                  for i in range(1, 16)]
    long_post = "Привет.\n\nСобрал 15 сервисов.\n\n" + "\n\n".join(long_items) + \
        "\n\nПерешли другу.\n\n#сервисы\n\n" + FOOTER
    fails = []
    data, article, post = build(short)
    if data["need_article"]:
        fails.append("короткий пост не должен требовать статью")
    if article is not None:
        fails.append("короткий пост не должен рожать статью")
    data, article, post = build(long_post)
    if not data["need_article"]:
        fails.append("15 пунктов обязаны уехать в статью")
    if PLACEHOLDER not in post:
        fails.append("в посте нет метки адреса статьи")
    if re.search(r"(?m)^\s*\*\*\d+\.", post):
        fails.append("анонс не должен пересказывать пункты статьи")
    if not re.search(r"\[[^\]]+\]\(" + re.escape(PLACEHOLDER) + r"\)", post):
        fails.append("в анонсе название обязано быть ссылкой")
    if data["items_kept"] != 0:
        fails.append("в анонсе пункты не остаются")
    if data["items_moved"] != 15:
        fails.append("все 15 пунктов обязаны уехать в статью")
    if FOOTER_MARK not in post.split("\n")[-1]:
        fails.append("футер обязан быть последней строкой")
    if len(post) > TG_HARD_LIMIT:
        fails.append("пост после разреза всё равно больше предела")
    if "15" not in article:
        fails.append("в статье обязаны быть все пункты")
    head_line = article.split("\n")[0]
    if not head_line.startswith("Заголовок: "):
        fails.append("первая строка статьи это Заголовок: имя материала")
    bare_title = head_line.split(":", 1)[-1].strip()
    if bare_title.startswith("Привет"):
        fails.append("заголовок статьи не должен быть приветствием")
    if "Собрал 15 сервисов" not in bare_title:
        fails.append("заголовок статьи берётся из имени материала")
    if re.search(r"(?m)^\s*#[^\s#]+\s*$", article):
        fails.append("хэштег рубрики остался в статье")
    if ("Автор: %s" % AUTHOR) not in article:
        fails.append("в шапке статьи нет подписи автора из профиля")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import lint_article
    except ImportError:
        fails.append("рядом нет lint_article.py")
    else:
        dirty = sorted(set(item["code"] for item in lint_article.lint(article)
                           if item["level"] == "ERROR"))
        if dirty:
            fails.append("статья из разреза не проходит свой линтер: %s"
                         % ", ".join(dirty))
    data, article, post = build("Фото плюс тело. " * 60 + "\n\n#сервисы\n\n" + FOOTER, media=True)
    if not data["need_article"]:
        fails.append("медиа плюс длинное тело обязаны требовать статью")
    for line in fails:
        print("SELFTEST ПРОВАЛ: %s" % line)
    if not fails:
        print("SELFTEST: все проверки разреза прошли")
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description="разрез длинного поста на пост плюс статью")
    ap.add_argument("file", nargs="?", default="-", help="черновик поста, или минус для stdin")
    ap.add_argument("--check", action="store_true", help="только вердикт, без текстов")
    ap.add_argument("--media", action="store_true", help="пост с фото или альбомом")
    ap.add_argument("--brand", default="vs", choices=["vs", "second-brand"],
                    help="бренд текста, по умолчанию vs")
    ap.add_argument("--out", metavar="DIR", help="куда положить article.md и post.md")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args()

    if args.version:
        print("split_post.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()

    if args.brand == "second-brand":
        print("Бренд ВТОРОЙ БРЕНД: мем не режем, у него одна шутка и подпись 40-220 знаков.")
        print("Правила мема: reference/distribution.md")
        return 0

    text = read_source(args.file)
    if not text.strip():
        print("SPLIT: пустой ввод")
        return 1

    if args.check:
        data = verdict(text, args.media)
        data.pop("_parts", None)
        if args.json:
            print(json.dumps(data, ensure_ascii=False))
        else:
            print(report(data))
        return 0

    data, article, post = build(text, args.media)
    if args.json:
        print(json.dumps({"verdict": data, "article": article, "post": post},
                         ensure_ascii=False))
        return 0

    print(report(data))
    print("")
    if article:
        print(ARTICLE_HEAD)
        print("")
        print(article)
        print("")
    print(POST_HEAD)
    print("")
    print(post)

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        if article:
            with open(os.path.join(args.out, "article.md"), "w", encoding="utf-8") as handle:
                handle.write(article + "\n")
        with open(os.path.join(args.out, "post.md"), "w", encoding="utf-8") as handle:
            handle.write(post + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
