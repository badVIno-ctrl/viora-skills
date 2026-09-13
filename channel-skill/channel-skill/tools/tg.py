#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tg.py 1.0.0

Мост между Избранным в Телеграме и каналом автора.

Зачем он нужен. Автор пишет заявку в Избранное одной строкой, агент должен
понять её так же, как понял бы в прошлый раз, ничего не потерять при перезапуске
и не публиковать лишнего. Держать это в голове модели нельзя, поэтому состояние,
разбор команд и все тексты для автора живут здесь, в коде.

В Телеграм скрипт ходит сам, через telethon. Сервер MCP больше не нужен:
он был лишним звеном, и любая его ошибка выглядела как тишина в Избранном.
Ключи и строка сессии берутся из secrets/, поэтому команды работают из любой
оболочки, без экспорта переменных. Входящие заявки приносит сторож
tools/tg_watch.py или команда poll.

Команды:
    python3 tools/tg.py setup
    python3 tools/tg.py login --force
    python3 tools/tg.py doctor
    python3 tools/tg.py card
    python3 tools/tg.py poll --limit 30
    python3 tools/tg.py send --text "CHANNEL на смене" --to me
    python3 tools/tg.py ping
    python3 tools/tg.py publish r1 --at 20:30
    python3 tools/tg.py next --wait 600 --json
    python3 tools/tg.py feed --stdin
    python3 tools/tg.py stage r1 --file out/r1.txt --rubric абуз
    python3 tools/tg.py sent r1 --msg-id 4821
    python3 tools/tg.py payload r1
    python3 tools/tg.py published r1 --msg-id 612 --link https://t.me/demo_channel/612
    python3 tools/tg.py ask r1 --text "какой личный факт добавить"
    python3 tools/tg.py cancel r1
    python3 tools/tg.py status
    python3 tools/tg.py when --at 20:30
    python3 tools/tg.py config --set channel=@demo_channel
    python3 tools/tg.py selftest

Рабочая папка моста: ~/.local/state/channel-skill, меняется через CHANNEL_TG_HOME.
Одна папка на все копии скилла: сторож и агент видят один и тот же ящик.

Коды возврата: 0 порядок, 1 проблема, 2 ошибка вызова.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time

VERSION = "6.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

STATE_VERSION = 1
INBOX_KEEP = 400
INBOX_MAX = 800
MAX_WAIT = 900
MAX_TRIES = 3
BRIEF = 70
TG_LIMIT = 4096
DEVICE = "CHANNEL"

# Где искать строку сессии. Первое имя главное, остальные для старых файлов:
# раньше сессий было две, теперь хватает одной.
SESSION_ENVS = ("TELEGRAM_SESSION_STRING_WATCH", "TELEGRAM_WATCH_SESSION_STRING",
                "TELEGRAM_SESSION_STRING")
SESSION_KEY = "TELEGRAM_SESSION_STRING_WATCH"
SECRET_FILES = ("watch.env", "telegram.env")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import profile as P  # noqa: E402

# Канал, окно выхода и префиксы команд задаёт профиль автора.
PROFILE = P.load()
TG = P.telegram(PROFILE)

DEFAULT_CONFIG = {
    "prefixes": TG.get("prefixes") or ["/post", "/vs"],
    "marker": "CHANNEL",
    "inbox": TG.get("inbox") or "me",
    "channel": P.channel(PROFILE),
    "mode": TG.get("mode") or "draft",
    "window": P.window(PROFILE) or "16:30-21:00",
    "tz": P.timezone(PROFILE) or "Europe/Moscow",
    "reply_capture": True,
    "rubric_default": "",
    "preview": False,
}

MODES = ("draft", "scheduled", "auto")

# Слова, которые работают только без хвоста. "/post что там по Notion" это
# заявка на пост, а не запрос статуса, иначе автор будет ловить сюрпризы.
SOLO = {
    "publish": ("пуб", "публикуй", "опубликуй", "публикую", "го", "ок", "окей", "go", "ship"),
    "cancel": ("стоп", "отмена", "отмени", "забудь", "хватит"),
    "status": ("что", "статус", "дела", "где"),
    "help": ("помощь", "help", "справка", "команды", "?"),
    "log": ("лог", "история"),
}

# Проверка связи. Автор пишет "/post как дела" и ждёт ответ сразу, а не
# пост про то, как дела. Отвечает сам сторож, агента не будим.
PING = (
    "как дела", "как ты", "ты тут", "ты здесь", "жив", "живой", "тест",
    "проверка", "пинг", "ping", "test", "алло", "ау", "привет", "здарова",
    "ку", "на месте", "работаешь", "слышишь", "канал", "channel",
)

# Слова с хвостом: хвост это и есть смысл команды.
WITH_TAIL = {
    "edit": ("правь", "править", "правка", "переделай", "перепиши", "фикс"),
    "schedule": ("отложи", "отложить", "вечером"),
}

HINTS = {
    "request": "Новая заявка. Разбери сырьё, недостающее спроси ОДНОЙ строкой через ask, "
               "собери пост, прогони ship, отдай через stage.",
    "edit": "Автор просит правку черновика. Правь только то, что просят, снова ship, снова stage.",
    "publish": "Автор дал добро. Возьми текст через payload и отправь в канал, потом published.",
    "schedule": "Автор просит отложенную публикацию. Время возьми через when, потом published.",
    "cancel": "Автор отменил заявку. Отметь cancel и ответь одной строкой.",
    "status": "Автор спросил статус. Отправь в Избранное вывод команды status.",
    "help": "Автор просит карточку команд. Отправь в Избранное вывод команды card.",
    "log": "Автор просит последние заявки. Отправь в Избранное вывод команды status.",
    "answer": "Это ответ на твой вопрос. Допиши пост с новым фактом и снова stage.",
    "resume": "Незакрытая заявка с прошлого запуска. Доведи её до конца или отмени.",
    "empty": "Ящик пуст. Ничего не делаем и не пишем автору.",
    "unknown": "Команда не разобрана. Ответь автору карточкой card.",
    "ping": "Проверка связи. Одна строка через tg.py ping, пост писать не надо.",
}


# ---------------------------------------------------------------- пути и файлы

def home():
    """Рабочая папка моста. Одна на машину, а не на копию скилла."""
    env = os.environ.get("CHANNEL_TG_HOME")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "channel-skill")


def paths():
    root = home()
    return {
        "home": root,
        "config": os.path.join(root, "tg-config.json"),
        "state": os.path.join(root, "tg-state.json"),
        "inbox": os.path.join(root, "tg-inbox.jsonl"),
        "drafts": os.path.join(root, "drafts"),
    }


def ensure_home():
    p = paths()
    os.makedirs(p["drafts"], exist_ok=True)
    try:
        os.chmod(p["home"], 0o700)
    except OSError:
        pass
    return p


def write_atomic(path, text, mode=0o600):
    """Запись без полуфабрикатов: сторож и агент читают файл в любой момент."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".tg-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path, fallback):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return fallback


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    got = read_json(paths()["config"], {})
    if isinstance(got, dict):
        for key, value in got.items():
            if key in cfg:
                cfg[key] = value
    if isinstance(cfg["prefixes"], str):
        cfg["prefixes"] = [cfg["prefixes"]]
    cfg["prefixes"] = [str(x).strip().lower() for x in cfg["prefixes"] if str(x).strip()]
    if not cfg["prefixes"]:
        cfg["prefixes"] = list(DEFAULT_CONFIG["prefixes"])
    if cfg["mode"] not in MODES:
        cfg["mode"] = "draft"
    return cfg


def save_config(cfg):
    ensure_home()
    write_atomic(paths()["config"], json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


def blank_state():
    return {"version": STATE_VERSION, "cursor": 0, "seq": 0, "items": []}


def load_state():
    st = read_json(paths()["state"], None)
    if not isinstance(st, dict) or "items" not in st:
        return blank_state()
    st.setdefault("version", STATE_VERSION)
    st.setdefault("cursor", 0)
    st.setdefault("seq", 0)
    if not isinstance(st["items"], list):
        st["items"] = []
    return st


def save_state(st):
    ensure_home()
    st["items"] = st["items"][-200:]
    write_atomic(paths()["state"], json.dumps(st, ensure_ascii=False, indent=2) + "\n")


def now_iso():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


# --------------------------------------------------------------- разбор команд

def strip_prefix(text, cfg):
    """Отрезать префикс. Вернуть хвост или None, если это не команда моста."""
    body = (text or "").strip()
    if not body:
        return None
    low = body.lower()
    for prefix in cfg["prefixes"]:
        if low == prefix:
            return ""
        if low.startswith(prefix):
            nxt = body[len(prefix):]
            if nxt[:1] in (" ", "\n", "\t", ":", ",", ".", "!", "-"):
                return nxt.lstrip(" \n\t:,.!-")
    return None


def starts_with_marker(text, cfg):
    """Своё сообщение агента. Такое в ящик не кладём никогда."""
    body = (text or "").lstrip()
    marker = str(cfg.get("marker") or "CHANNEL")
    return body[:len(marker)].upper() == marker.upper()


def decide_capture(text, parent_text, cfg):
    """Что делать сторожу с исходящим сообщением: cmd, answer или ничего.

    Одна точка правды для сторожа и для тестов. Правило простое: своё не берём,
    команду с префиксом берём всегда, ответ реплаем на своё сообщение берём,
    если это разрешено настройкой.
    """
    if starts_with_marker(text, cfg):
        return None
    if strip_prefix(text, cfg) is not None:
        return "cmd"
    if cfg.get("reply_capture") and parent_text and starts_with_marker(parent_text, cfg):
        if (text or "").strip():
            return "answer"
    return None


def classify(text, cfg, kind_hint="cmd"):
    """Из текста автора сделать команду моста."""
    if kind_hint == "answer":
        return {"kind": "answer", "arg": (text or "").strip()}
    tail = strip_prefix(text, cfg)
    if tail is None:
        return {"kind": "skip", "arg": ""}
    if not tail:
        return {"kind": "help", "arg": ""}
    parts = tail.split(None, 1)
    head = parts[0].strip().strip("/!.,:;").lower()
    rest = parts[1].strip() if len(parts) > 1 else ""
    short = " ".join(tail.split()).strip("!?.,;:() ").lower()
    if short in PING:
        return {"kind": "ping", "arg": short}
    for kind, words in WITH_TAIL.items():
        if head in words:
            return {"kind": kind, "arg": rest}
    for kind, words in SOLO.items():
        if head in words and not rest:
            return {"kind": kind, "arg": ""}
    return {"kind": "request", "arg": tail}


# ------------------------------------------------------------------------ ящик

def read_inbox():
    path = paths()["inbox"]
    out = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and isinstance(row.get("msg_id"), int):
                    out.append(row)
    except OSError:
        return []
    out.sort(key=lambda r: r["msg_id"])
    return out


def append_inbox(rows):
    """Дописать заявки в ящик, без повторов по msg_id."""
    if not rows:
        return 0
    ensure_home()
    path = paths()["inbox"]
    known = set(r["msg_id"] for r in read_inbox())
    fresh = []
    for row in rows:
        mid = row.get("msg_id")
        if not isinstance(mid, int) or mid in known:
            continue
        known.add(mid)
        row.setdefault("ts", round(time.time(), 2))
        row.setdefault("kind", "cmd")
        fresh.append(row)
    if not fresh:
        return 0
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        for row in fresh:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    trim_inbox()
    return len(fresh)


def trim_inbox():
    rows = read_inbox()
    if len(rows) <= INBOX_MAX:
        return
    keep = rows[-INBOX_KEEP:]
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep)
    write_atomic(paths()["inbox"], body)


MCP_ID = re.compile(r"^ID:\s*(\d+)\b")
MCP_DATE = re.compile(r"\|\s*Date:\s*([^|]+)")
MCP_SPLIT = " | Message: "


def parse_mcp(text):
    """Разобрать вывод list_messages из MCP в строки ящика.

    Формат строки MCP: ID: 12 | ... | Date: ... | Message: текст, переносы
    внутри текста экранированы в \\n.
    """
    out = []
    for raw in (text or "").split("\n"):
        raw = raw.strip()
        m = MCP_ID.match(raw)
        if not m:
            continue
        cut = raw.find(MCP_SPLIT)
        if cut == -1:
            continue
        body = raw[cut + len(MCP_SPLIT):]
        body = body.replace("\\n", "\n")
        if body.strip() == "[empty]":
            body = ""
        date = ""
        dm = MCP_DATE.search(raw[:cut])
        if dm:
            date = dm.group(1).strip()
        out.append({"msg_id": int(m.group(1)), "date": date, "text": body,
                    "src": "poll", "kind": "cmd"})
    return out


def feed_rows(text, cfg=None):
    """Строки из вывода MCP, которые реально стоит положить в ящик."""
    cfg = cfg or load_config()
    return [r for r in parse_mcp(text) if decide_capture(r["text"], "", cfg) == "cmd"]


# --------------------------------------------------------------------- заявки

def find(st, item_id):
    for item in st["items"]:
        if item["id"] == item_id:
            return item
    return None


def active(st):
    """Живые заявки: те, что ещё не закрыты."""
    return [i for i in st["items"] if i["status"] in ("work", "asked", "staged", "await")]


def awaiting(st):
    for item in reversed(st["items"]):
        if item["status"] in ("await", "staged"):
            return item
    return None


def new_item(st, row, raw):
    st["seq"] = int(st.get("seq", 0)) + 1
    item = {
        "id": "r%d" % st["seq"],
        "msg_id": row.get("msg_id"),
        "date": row.get("date", ""),
        "created": now_iso(),
        "updated": now_iso(),
        "status": "work",
        "raw": raw,
        "brief": brief_of(raw),
        "rubric": "",
        "draft": "",
        "draft_msg_id": 0,
        "ask_msg_id": 0,
        "published_msg_id": 0,
        "link": "",
        "note": "",
        "tries": 0,
    }
    st["items"].append(item)
    return item


def brief_of(text):
    one = " ".join((text or "").split())
    return one[:BRIEF]


def touch(item, **fields):
    item.update(fields)
    item["updated"] = now_iso()


def target_for(st, row, cmd):
    """К какой заявке относится короткая команда автора."""
    parent = row.get("reply_to")
    if parent:
        for item in reversed(st["items"]):
            if parent in (item.get("draft_msg_id"), item.get("ask_msg_id")):
                return item
    if cmd["kind"] in ("publish", "schedule"):
        return awaiting(st)
    live = active(st)
    return live[-1] if live else None


# ----------------------------------------------------------------- next и feed

def take_next(st, cfg):
    """Первая необработанная строка ящика. Курсор двигаем сразу."""
    for row in read_inbox():
        if int(row.get("msg_id", 0)) <= int(st.get("cursor", 0)):
            continue
        st["cursor"] = int(row["msg_id"])
        cmd = classify(row.get("text", ""), cfg, row.get("kind", "cmd"))
        if cmd["kind"] == "skip":
            save_state(st)
            continue
        if cmd["kind"] == "request":
            item = new_item(st, row, cmd["arg"])
            save_state(st)
            return {"kind": "request", "id": item["id"], "msg_id": row.get("msg_id"),
                    "text": cmd["arg"], "rubric": cfg.get("rubric_default", ""),
                    "mode": cfg["mode"], "source": row.get("src", "watch")}
        item = target_for(st, row, cmd)
        if cmd["kind"] in ("edit", "answer") and item is not None:
            touch(item, status="work", note=cmd["arg"][:200])
        if cmd["kind"] == "cancel" and item is not None:
            touch(item, status="cancelled")
        save_state(st)
        return {"kind": cmd["kind"], "id": item["id"] if item else "",
                "msg_id": row.get("msg_id"), "text": cmd["arg"],
                "mode": cfg["mode"], "source": row.get("src", "watch")}
    return None


def resume_candidate(st):
    for item in active(st):
        if int(item.get("tries", 0)) >= MAX_TRIES:
            continue
        if item["status"] in ("work", "staged"):
            touch(item, tries=int(item.get("tries", 0)) + 1)
            save_state(st)
            return {"kind": "resume", "id": item["id"], "msg_id": item.get("msg_id"),
                    "text": item.get("raw", ""), "status": item["status"],
                    "note": item.get("note", "")}
    return None


def emit(result, as_json):
    result.setdefault("hint", HINTS.get(result.get("kind", ""), ""))
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print("команда: %s" % result.get("kind"))
    if result.get("id"):
        print("заявка: %s" % result["id"])
    if result.get("text"):
        print("текст: %s" % result["text"])
    if result.get("hint"):
        print("что делать: %s" % result["hint"])
    return 0


def cmd_next(args):
    cfg = load_config()
    wait = max(0, min(int(args.wait or 0), MAX_WAIT))
    deadline = time.time() + wait
    checked_resume = False
    while True:
        st = load_state()
        got = take_next(st, cfg)
        if got:
            return emit(got, args.as_json)
        if not checked_resume:
            checked_resume = True
            got = resume_candidate(load_state())
            if got:
                return emit(got, args.as_json)
        if time.time() >= deadline:
            return emit({"kind": "empty"}, args.as_json)
        time.sleep(1.0)


def cmd_feed(args):
    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            raw = handle.read()
    else:
        raw = sys.stdin.read()
    cfg = load_config()
    rows = feed_rows(raw, cfg)
    added = append_inbox(rows)
    if args.as_json:
        print(json.dumps({"parsed": len(rows), "added": added}, ensure_ascii=False))
    else:
        print("строк с командой: %d, новых в ящике: %d" % (len(rows), added))
    return 0


# -------------------------------------------------------- черновик и публикация

def lint(path, rubric, media):
    argv = [sys.executable, os.path.join(HERE, "lint_post.py"), path, "--strict"]
    if rubric:
        argv += ["--rubric", rubric]
    if media:
        argv.append("--media")
    done = subprocess.run(argv, capture_output=True, text=True)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def draft_message(item, cfg, text):
    head = "%s ЧЕРНОВИК %s" % (cfg["marker"], item["id"])
    facts = "рубрика %s, знаков %d" % (item.get("rubric") or "не задана", len(text))
    if cfg["mode"] == "auto":
        ask = "режим автопубликации: уходит в канал без подтверждения"
    elif cfg["mode"] == "scheduled":
        ask = "%s пуб поставлю в отложенные, %s правь скажи что не так" % (cfg["prefixes"][0], cfg["prefixes"][0])
    else:
        ask = "%s пуб публикую, %s правь скажи что не так" % (cfg["prefixes"][0], cfg["prefixes"][0])
    return "\n".join([head, facts, ask, "", text])


def cmd_stage(args):
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    if not os.path.exists(args.file):
        print("нет файла черновика: %s" % args.file)
        return 2
    with open(args.file, encoding="utf-8") as handle:
        text = handle.read().strip("\n")
    if not text.strip():
        print("черновик пустой")
        return 2
    rubric = args.rubric or item.get("rubric") or load_config().get("rubric_default", "")
    code, output = lint(args.file, rubric, args.media)
    if code != 0:
        print("линтер не пустил черновик, правь по подсказкам и запускай stage снова")
        print(output.strip())
        return 1
    ensure_home()
    dest = os.path.join(paths()["drafts"], "%s.txt" % item["id"])
    write_atomic(dest, text + "\n")
    touch(item, status="staged", draft=dest, rubric=rubric)
    save_state(st)
    cfg = load_config()
    card = draft_message(item, cfg, text)
    if not getattr(args, "send", False):
        print(card)
        return 0
    try:
        out = send_text(card, "me", int(item.get("msg_id") or 0), None, cfg)
    except NetProblem as err:
        print(card)
        print("")
        print("в Телеграм не ушло: %s" % err)
        return 1
    touch(item, status="await", draft_msg_id=out["msg_id"], tries=0)
    save_state(st)
    print(card)
    print("")
    print("черновик ушёл автору: id %d" % out["msg_id"])
    return 0


def cmd_sent(args):
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    touch(item, status="await", draft_msg_id=int(args.msg_id), tries=0)
    save_state(st)
    print("заявка %s ждёт добро автора" % item["id"])
    return 0


def cmd_payload(args):
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    path = item.get("draft")
    if not path or not os.path.exists(path):
        print("черновик не сохранён, сначала stage")
        return 1
    with open(path, encoding="utf-8") as handle:
        text = handle.read().strip("\n")
    if args.out:
        write_atomic(args.out, text + "\n", 0o644)
        print(args.out)
        return 0
    sys.stdout.write(text + "\n")
    return 0


def cmd_ask(args):
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    cfg = load_config()
    question = " ".join((args.text or "").split())
    if not question:
        print("дай текст вопроса")
        return 2
    touch(item, status="asked", note=question[:200])
    save_state(st)
    card = "%s ВОПРОС %s\n%s" % (cfg["marker"], item["id"], question)
    if not getattr(args, "send", False):
        print(card)
        return 0
    try:
        out = send_text(card, "me", int(item.get("msg_id") or 0), None, cfg)
    except NetProblem as err:
        print(card)
        print("")
        print("в Телеграм не ушло: %s" % err)
        return 1
    touch(item, ask_msg_id=out["msg_id"])
    save_state(st)
    print(card)
    print("")
    print("вопрос ушёл автору: id %d" % out["msg_id"])
    return 0


def cmd_asked(args):
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    touch(item, ask_msg_id=int(args.msg_id))
    save_state(st)
    print("вопрос по %s отмечен" % item["id"])
    return 0


def cmd_published(args):
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    cfg = load_config()
    link = args.link or ""
    status = "scheduled" if args.scheduled else "published"
    touch(item, status=status, published_msg_id=int(args.msg_id or 0), link=link)
    save_state(st)
    if args.topic:
        log_post(item, args.topic, args.services, link)
    word = "ОТЛОЖЕН" if args.scheduled else "ГОТОВО"
    tail = link if link else "ссылки нет, канал приватный"
    print("%s %s %s\n%s" % (cfg["marker"], word, item["id"], tail))
    return 0


def log_post(item, topic, services, link):
    argv = [sys.executable, os.path.join(HERE, "memory.py"), "add-post",
            "--type", item.get("rubric") or "абуз", "--topic", topic]
    if services:
        argv += ["--services", services]
    if link:
        argv += ["--url", link]
    try:
        subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def cmd_cancel(args):
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    touch(item, status="cancelled", note=(args.why or "")[:200])
    save_state(st)
    cfg = load_config()
    print("%s ОТМЕНА %s" % (cfg["marker"], item["id"]))
    return 0


# ------------------------------------------------------------- тексты для автора

def card_text(cfg=None):
    cfg = cfg or load_config()
    p = cfg["prefixes"][0]
    lines = [
        "%s ПОМОЩЬ" % cfg["marker"],
        "Пишу посты по заявкам из этого чата. Всё, что без %s, я не читаю." % p,
        "",
        "%s текст или ссылка   новая заявка на пост" % p,
        "%s правь что не так   переделать черновик" % p,
        "%s пуб                опубликовать в канал" % p,
        "%s отложи 20:30       поставить в отложенные" % p,
        "%s стоп               отменить заявку" % p,
        "%s что                что сейчас в работе" % p,
        "%s помощь             эта карточка" % p,
        "",
        "Можно кинуть альбом скринов и написать заявку в подписи.",
        "На мой вопрос отвечай реплаем, префикс не нужен.",
    ]
    return "\n".join(lines)


def status_text(cfg=None):
    cfg = cfg or load_config()
    st = load_state()
    lines = ["%s СТАТУС" % cfg["marker"]]
    live = active(st)
    if live:
        for item in live[-3:]:
            lines.append("%s %s: %s" % (item["id"], human_status(item["status"]), item["brief"] or "без темы"))
    else:
        lines.append("в работе ничего, ящик чист")
    done = [i for i in st["items"] if i["status"] in ("published", "scheduled")]
    if done:
        last = done[-1]
        lines.append("последний: %s %s %s" % (last["id"], human_status(last["status"]),
                                              last.get("link") or ""))
    fresh = [r for r in read_inbox() if int(r.get("msg_id", 0)) > int(st.get("cursor", 0))]
    lines.append("новых заявок в ящике: %d" % len(fresh))
    return "\n".join(x.rstrip() for x in lines)


def human_status(code):
    return {
        "work": "пишу",
        "asked": "жду ответ",
        "staged": "черновик готов",
        "await": "жду добро",
        "published": "опубликован",
        "scheduled": "в отложенных",
        "cancelled": "отменён",
    }.get(code, code)


def cmd_card(args):
    print(card_text())
    return 0


def cmd_status(args):
    if args.as_json:
        st = load_state()
        print(json.dumps({"cursor": st["cursor"], "items": st["items"][-10:]},
                         ensure_ascii=False, indent=2))
        return 0
    print(status_text())
    return 0


# ------------------------------------------------------------------- время окна

def window_bounds(cfg):
    raw = str(cfg.get("window") or "16:30-21:00")
    try:
        a, b = raw.split("-", 1)
        ah, am = [int(x) for x in a.strip().split(":")]
        bh, bm = [int(x) for x in b.strip().split(":")]
        return (ah, am), (bh, bm)
    except (ValueError, TypeError):
        return (16, 30), (21, 0)


def tzinfo_of(cfg):
    name = str(cfg.get("tz") or "Europe/Moscow")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return datetime.timezone(datetime.timedelta(hours=4))


def next_slot(cfg, at=None, now=None):
    """Когда публиковать: своё окно канала, а не случайный час ночи."""
    tz = tzinfo_of(cfg)
    now = now or datetime.datetime.now(tz)
    start, end = window_bounds(cfg)
    if at:
        hh, mm = [int(x) for x in at.split(":")]
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return target
    begin = now.replace(hour=start[0], minute=start[1], second=0, microsecond=0)
    finish = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
    if now < begin:
        return begin
    if now <= finish - datetime.timedelta(minutes=5):
        return now + datetime.timedelta(minutes=10)
    return begin + datetime.timedelta(days=1)


def cmd_when(args):
    cfg = load_config()
    try:
        when = next_slot(cfg, args.at)
    except (ValueError, TypeError):
        print("время не разобрал, пиши так: --at 20:30")
        return 2
    if args.as_json:
        print(json.dumps({"iso": when.isoformat(), "tz": cfg.get("tz"),
                          "window": cfg.get("window")}, ensure_ascii=False))
    else:
        print(when.isoformat())
    return 0


# ---------------------------------------------------------------- доктор и конфиг

def cmd_config(args):
    cfg = load_config()
    changed = []
    for pair in args.set or []:
        if "=" not in pair:
            print("настройка задаётся так: --set channel=@demo_channel")
            return 2
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in DEFAULT_CONFIG:
            print("нет такой настройки: %s" % key)
            return 2
        if key == "prefixes":
            cfg[key] = [x.strip().lower() for x in value.split(",") if x.strip()]
        elif key == "reply_capture":
            cfg[key] = value.lower() in ("1", "да", "true", "yes", "on")
        elif key == "mode":
            if value not in MODES:
                print("режим бывает только draft, scheduled или auto")
                return 2
            cfg[key] = value
        else:
            cfg[key] = value
        changed.append(key)
    if changed:
        save_config(cfg)
    if args.as_json:
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0
    print("рабочая папка: %s" % paths()["home"])
    for key in sorted(cfg):
        print("  %-14s %s" % (key, cfg[key]))
    if changed:
        print("обновлено: %s" % ", ".join(changed))
    return 0


def telethon_ready():
    try:
        import telethon  # noqa: F401
        return True
    except Exception:
        return False


def watch_session():
    for name in ("TELEGRAM_SESSION_STRING_WATCH", "TELEGRAM_WATCH_SESSION_STRING"):
        value = os.environ.get(name)
        if value:
            return name, value
    value = os.environ.get("TELEGRAM_SESSION_STRING")
    if value:
        return "TELEGRAM_SESSION_STRING", value
    return "", ""


# --------------------------------------------------------------- сеть: телетон
# Почему сеть живёт здесь, а не в стороннем сервере. Сервер MCP был лишним
# звеном: если он не поднялся или агент не позвал инструмент, автор видел
# тишину в Избранном и никто не мог сказать, на каком шаге всё встало. Теперь
# отправляет тот же скрипт, который ведёт состояние. Одна команда, один ответ,
# одна понятная ошибка.

class NetProblem(Exception):
    """Причина отказа человеческими словами."""


def secrets_dirs():
    """Где искать ключи: переменная, корень поставки, сам скилл, текущая папка."""
    out = []
    env = os.environ.get("CHANNEL_SECRETS")
    if env:
        # Явно указанная папка главнее всего: иначе тест или вторая установка
        # незаметно зацепит чужие ключи.
        return [os.path.abspath(os.path.expanduser(env))]
    out.append(os.path.join(os.path.dirname(SKILL), "secrets"))
    out.append(os.path.join(SKILL, "secrets"))
    out.append(os.path.join(os.getcwd(), "secrets"))
    uniq = []
    for path in out:
        if path not in uniq:
            uniq.append(path)
    return uniq


def read_env_file(path):
    """Строки вида КЛЮЧ=ЗНАЧЕНИЕ. Решётка это заметка, а не ключ."""
    rows = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.lstrip("\ufeff").strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                rows[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return rows


def secrets_env():
    """Ключи из secrets/*.env. Переменные окружения важнее файла."""
    merged = {}
    for folder in secrets_dirs():
        for name in SECRET_FILES:
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            for key, value in read_env_file(path).items():
                if value and key not in merged:
                    merged[key] = value
    return merged


def secrets_file():
    """Куда писать строку сессии: в тот watch.env, который уже лежит на диске."""
    folders = secrets_dirs()
    for folder in folders:
        path = os.path.join(folder, "watch.env")
        if os.path.isfile(path):
            return path
    folder = folders[0] if folders else os.getcwd()
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        folder = os.getcwd()
    return os.path.join(folder, "watch.env")


def creds():
    """Ключи и строка сессии плюс словами, чего не хватает."""
    disk = secrets_env()
    api_id = (os.environ.get("TELEGRAM_API_ID") or disk.get("TELEGRAM_API_ID") or "").strip()
    api_hash = (os.environ.get("TELEGRAM_API_HASH") or disk.get("TELEGRAM_API_HASH") or "").strip()
    session, source = "", ""
    for name in SESSION_ENVS:
        value = (os.environ.get(name) or "").strip()
        if value:
            session, source = value, name
            break
    if not session:
        for name in SESSION_ENVS:
            value = (disk.get(name) or "").strip()
            if value:
                session, source = value, "secrets: %s" % name
                break
    problems = []
    if not api_id.isdigit():
        problems.append("нет ключа TELEGRAM_API_ID")
    if not api_hash:
        problems.append("нет ключа TELEGRAM_API_HASH")
    if not session:
        problems.append("нет строки сессии: запусти python3 tools/tg.py login")
    return {"api_id": api_id, "api_hash": api_hash, "session": session,
            "source": source, "problems": problems}


def save_session(value):
    """Строка сессии ложится в secrets/watch.env сама, копировать нечего."""
    path = secrets_file()
    info = creds()
    rows = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as handle:
            rows = handle.read().splitlines()
    pairs = []
    if info["api_id"]:
        pairs.append(("TELEGRAM_API_ID", info["api_id"]))
    if info["api_hash"]:
        pairs.append(("TELEGRAM_API_HASH", info["api_hash"]))
    pairs.append((SESSION_KEY, value))
    for key, val in pairs:
        line = "%s=%s" % (key, val)
        placed = False
        for index, row in enumerate(rows):
            clean = row.lstrip("\ufeff").strip()
            if clean.startswith(key + "=") or clean.startswith(key + " ="):
                rows[index] = line
                placed = True
                break
        if not placed:
            rows.append(line)
    body = "\n".join(row.lstrip("\ufeff") for row in rows).strip() + "\n"
    write_atomic(path, body)
    return path


def telethon_bits():
    try:
        from telethon.sessions import StringSession
        from telethon.sync import TelegramClient
    except ImportError:
        raise NetProblem("нет telethon: поставь его командой pip install telethon")
    return TelegramClient, StringSession


def connect():
    """Подключённый клиент. Любой отказ объясняем одной строкой."""
    info = creds()
    if info["problems"]:
        raise NetProblem("; ".join(info["problems"]))
    TelegramClient, StringSession = telethon_bits()
    client = TelegramClient(
        StringSession(info["session"]), int(info["api_id"]), info["api_hash"],
        device_model=os.environ.get("TELEGRAM_DEVICE_MODEL", DEVICE),
        system_version=os.environ.get("TELEGRAM_SYSTEM_VERSION", "1.0"),
        app_version=os.environ.get("TELEGRAM_APP_VERSION", VERSION),
    )
    try:
        client.connect()
    except Exception as err:
        raise NetProblem("нет связи с Телеграмом: %s" % err)
    if not client.is_user_authorized():
        try:
            client.disconnect()
        except Exception:
            pass
        raise NetProblem("строка сессии не подошла: python3 tools/tg.py login --force")
    return client


def target_of(where, cfg):
    """Куда отправлять: me это Избранное, channel это канал из настроек."""
    name = (where or "me").strip()
    if name.lower() in ("me", "self", "saved", "избранное", "себе"):
        return "me"
    if name.lower() in ("channel", "канал"):
        name = str(cfg.get("channel") or "").strip()
    if not name:
        raise NetProblem("не задан канал: python3 tools/tg.py config --set channel=@demo_channel")
    return name


def link_for(where, msg_id):
    """Ссылка на сообщение, если канал публичный."""
    name = str(where or "").strip()
    if not name.startswith("@") or not msg_id:
        return ""
    return "https://t.me/%s/%d" % (name.lstrip("@"), int(msg_id))


def send_text(text, where="me", reply_to=0, at=None, cfg=None):
    """Отправить сообщение. Одна дорога для всех команд моста."""
    cfg = cfg or load_config()
    body = (text or "").rstrip("\n")
    if not body.strip():
        raise NetProblem("пустой текст, отправлять нечего")
    if len(body) > TG_LIMIT:
        raise NetProblem("текст %d знаков, предел Телеграма %d: режь через split_post.py"
                         % (len(body), TG_LIMIT))
    entity = target_of(where, cfg)
    client = connect()
    try:
        kwargs = {"parse_mode": "md", "link_preview": bool(cfg.get("preview"))}
        if reply_to:
            kwargs["reply_to"] = int(reply_to)
        if at is not None:
            kwargs["schedule"] = at
        try:
            msg = client.send_message(entity, body, **kwargs)
        except Exception as err:
            # Старое сообщение могло уйти в трубу. Текст важнее ответа на реплай.
            if "reply_to" in kwargs and "reply" in str(err).lower():
                kwargs.pop("reply_to")
                msg = client.send_message(entity, body, **kwargs)
            else:
                raise NetProblem("Телеграм отказал: %s" % err)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
    msg_id = int(getattr(msg, "id", 0) or 0)
    return {"msg_id": msg_id, "to": entity, "link": link_for(entity, msg_id),
            "scheduled": at is not None, "chars": len(body)}


def ping_text(cfg=None):
    """Ответ на проверку связи: одна строка и никакой воды."""
    cfg = cfg or load_config()
    live = active(load_state())
    return "%s на смене. В работе %d, режим %s, канал %s." % (
        cfg["marker"], len(live), cfg["mode"], cfg["channel"])


def cmd_login(args):
    """Вход в аккаунт: номер, код, готово. Строка сессии пишется сама."""
    info = creds()
    if not info["api_id"].isdigit() or not info["api_hash"]:
        print("нет ключей api. Впиши TELEGRAM_API_ID и TELEGRAM_API_HASH в secrets/watch.env")
        return 1
    if info["session"] and not getattr(args, "force", False):
        print("строка сессии уже есть (%s)" % (info["source"] or "secrets"))
        print("нужен новый вход: python3 tools/tg.py login --force")
        return 0
    try:
        TelegramClient, StringSession = telethon_bits()
    except NetProblem as err:
        print(str(err))
        return 1
    print("Сейчас Телеграм спросит номер и код.")
    print("Номер с плюсом и кодом страны, например +79991234567.")
    print("Код придёт в сам Телеграм, в чат Telegram.")
    print("")
    client = TelegramClient(
        StringSession(), int(info["api_id"]), info["api_hash"],
        device_model=os.environ.get("TELEGRAM_DEVICE_MODEL", DEVICE),
    )
    try:
        client.start()
        me = client.get_me()
        session = client.session.save()
    except Exception as err:
        print("войти не получилось: %s" % err)
        return 1
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
    path = save_session(session)
    name = (getattr(me, "first_name", "") or "").strip()
    tag = getattr(me, "username", None)
    print("")
    print("вошёл как %s%s" % (name, " (@%s)" % tag if tag else ""))
    print("строка сессии записана: %s" % path)
    print("это полный вход в аккаунт, никому её не показывай")
    return 0


def cmd_setup(args):
    """Одна команда на всю настройку: доставить, войти, показать итог."""
    print("%s, настройка моста с Телеграмом" % P.brand(PROFILE))
    print("")
    if not telethon_ready():
        print("ставлю telethon...")
        code = subprocess.call([sys.executable, "-m", "pip", "install", "--quiet",
                               "--disable-pip-version-check", "telethon"])
        if code != 0 or not telethon_ready():
            print("telethon не встал. Поставь руками: pip install telethon")
            return 1
        print("telethon на месте")
    info = creds()
    if not info["api_id"].isdigit() or not info["api_hash"]:
        print("нет ключей api. Они лежат в secrets/watch.env, впиши их туда")
        return 1
    if not info["session"]:
        code = cmd_login(argparse.Namespace(force=False))
        if code != 0:
            return code
    cfg = load_config()
    print("")
    print("канал %s, режим %s, окно %s" % (cfg["channel"], cfg["mode"], cfg["window"]))
    print("всё на месте. Смена: python3 tools/tg_watch.py")
    return 0


def cmd_send(args):
    """Отправить текст себе в Избранное или в канал."""
    cfg = load_config()
    text = getattr(args, "text", "") or ""
    if getattr(args, "file", None):
        try:
            with open(args.file, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as err:
            print("не читается файл: %s" % err)
            return 2
    if not text.strip():
        print("дай текст: --text или --file")
        return 2
    at = None
    if getattr(args, "at", None):
        try:
            at = next_slot(cfg, args.at)
        except (ValueError, TypeError):
            print("время не разобрал, пиши так: --at 20:30")
            return 2
    if getattr(args, "dry_run", False):
        try:
            where = target_of(args.to, cfg)
        except NetProblem as err:
            print(str(err))
            return 1
        print(json.dumps({"dry": True, "to": where, "chars": len(text.strip()),
                          "at": at.isoformat() if at else ""}, ensure_ascii=False))
        return 0
    try:
        out = send_text(text, args.to, getattr(args, "reply_to", 0), at, cfg)
    except NetProblem as err:
        print(str(err))
        return 1
    if getattr(args, "as_json", False):
        print(json.dumps(out, ensure_ascii=False))
    else:
        tail = ", %s" % out["link"] if out["link"] else ""
        print("ушло в %s: id %d%s" % (out["to"], out["msg_id"], tail))
    return 0


def cmd_ping(args):
    """Ответить автору, что смена идёт."""
    cfg = load_config()
    text = ping_text(cfg)
    if getattr(args, "local", False):
        print(text)
        return 0
    try:
        send_text(text, "me", int(getattr(args, "reply_to", 0) or 0), None, cfg)
    except NetProblem as err:
        print(text)
        print("в Телеграм не ушло: %s" % err)
        return 1
    print(text)
    return 0


def cmd_poll(args):
    """Забрать заявки из Избранного своими руками, без сторожа."""
    cfg = load_config()
    try:
        client = connect()
    except NetProblem as err:
        print(str(err))
        return 1
    rows = []
    try:
        limit = max(1, min(int(getattr(args, "limit", 30) or 30), 200))
        for msg in client.iter_messages("me", limit=limit):
            text = getattr(msg, "message", "") or ""
            if not text.strip():
                continue
            parent_text = ""
            parent_id = int(getattr(msg, "reply_to_msg_id", 0) or 0)
            if parent_id and cfg.get("reply_capture"):
                try:
                    parent = client.get_messages("me", ids=parent_id)
                    parent_text = getattr(parent, "message", "") or ""
                except Exception:
                    parent_text = ""
            verdict = decide_capture(text, parent_text, cfg)
            if not verdict:
                continue
            rows.append({"msg_id": int(msg.id), "text": text, "kind": verdict,
                         "src": "poll", "date": str(getattr(msg, "date", "")),
                         "reply_to": parent_id})
    except Exception as err:
        print("чтение Избранного не удалось: %s" % err)
        return 1
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
    rows.sort(key=lambda row: row["msg_id"])
    added = append_inbox(rows)
    if getattr(args, "as_json", False):
        print(json.dumps({"seen": len(rows), "added": added}, ensure_ascii=False))
    else:
        print("с командой нашлось %d, новых в ящике %d" % (len(rows), added))
    return 0


def cmd_publish(args):
    """Отправить готовый черновик в канал и закрыть заявку."""
    st = load_state()
    item = find(st, args.req)
    if item is None:
        print("нет такой заявки: %s" % args.req)
        return 2
    path = item.get("draft")
    if not path or not os.path.exists(path):
        print("черновик не сохранён, сначала stage")
        return 1
    with open(path, encoding="utf-8") as handle:
        text = handle.read().strip("\n")
    cfg = load_config()
    at = None
    if getattr(args, "at", None) or cfg["mode"] == "scheduled":
        try:
            at = next_slot(cfg, getattr(args, "at", None))
        except (ValueError, TypeError):
            print("время не разобрал, пиши так: --at 20:30")
            return 2
    try:
        out = send_text(text, getattr(args, "to", "channel") or "channel", 0, at, cfg)
    except NetProblem as err:
        print("в канал не ушло: %s" % err)
        return 1
    touch(item, status="scheduled" if at else "published",
          published_msg_id=out["msg_id"], link=out["link"])
    save_state(st)
    if getattr(args, "topic", ""):
        log_post(item, args.topic, getattr(args, "services", ""), out["link"])
    word = "ОТЛОЖЕН" if at else "ГОТОВО"
    tail = out["link"] or "ссылки нет, канал приватный"
    print("%s %s %s" % (cfg["marker"], word, item["id"]))
    print(tail)
    return 0


def cmd_doctor(args):
    cfg = load_config()
    p = ensure_home()
    rows = []
    rows.append(("питон", "ок", "%d.%d.%d" % sys.version_info[:3]))
    writable = os.access(p["home"], os.W_OK)
    rows.append(("рабочая папка", "ок" if writable else "нет", p["home"]))
    rows.append(("настройки", "ок" if os.path.exists(p["config"]) else "по умолчанию",
                 "режим %s, канал %s" % (cfg["mode"], cfg["channel"])))
    rows.append(("префикс", "ок", ", ".join(cfg["prefixes"])))
    inbox = read_inbox()
    st = load_state()
    fresh = [r for r in inbox if int(r.get("msg_id", 0)) > int(st.get("cursor", 0))]
    rows.append(("ящик", "ок", "строк %d, новых %d" % (len(inbox), len(fresh))))
    rows.append(("заявки", "ок", "всего %d, живых %d" % (len(st["items"]), len(active(st)))))
    rows.append(("линтер поста", "ок" if os.path.exists(os.path.join(HERE, "lint_post.py")) else "нет",
                 os.path.join("tools", "lint_post.py")))
    tele = telethon_ready()
    rows.append(("telethon", "ок" if tele else "нет",
                 "есть" if tele else "встанет сам: python3 tools/tg.py setup"))
    info = creds()
    api = bool(info["api_id"]) and bool(info["api_hash"])
    rows.append(("ключи api", "ок" if api else "нет",
                 "api_id %s" % info["api_id"] if api else "нет в secrets/watch.env"))
    rows.append(("строка сессии", "ок" if info["session"] else "нет",
                 info["source"] or "вход одной командой: python3 tools/tg.py login"))
    rows.append(("канал", "ок" if cfg.get("channel") else "нет", str(cfg.get("channel") or "")))

    if args.as_json:
        print(json.dumps([{"что": a, "как": b, "детали": c} for a, b, c in rows],
                         ensure_ascii=False, indent=2))
    else:
        print("Мост в Телеграм, tg.py %s" % VERSION)
        print("")
        for a, b, c in rows:
            print("  %-16s %-4s %s" % (a, b, c))
        print("")
        if not tele or info["problems"]:
            print("Чего не хватает:")
            if not tele:
                print("  telethon: pip install telethon")
            for problem in info["problems"]:
                print("  %s" % problem)
            print("")
            print("Одной командой: python3 tools/tg.py setup")
        else:
            print("Всё на месте. Смена: python3 tools/tg_watch.py")
            print("Без сторожа тоже работает: python3 tools/tg.py poll")
    bad = [r for r in rows if r[1] == "нет" and r[0] in ("рабочая папка", "линтер поста")]
    return 1 if bad else 0


# ------------------------------------------------------------------- селфтест

def selftest():
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    cfg = dict(DEFAULT_CONFIG)

    ok("текст без префикса не берём", decide_capture("купить хлеб", "", cfg) is None)
    ok("своё сообщение не берём", decide_capture("CHANNEL ЧЕРНОВИК r1", "", cfg) is None)
    ok("команда с префиксом берётся", decide_capture("/post пуб", "", cfg) == "cmd")
    ok("русский префикс берётся", decide_capture("/канал сделай пост", "", cfg) == "cmd")
    ok("реплай на своё берётся", decide_capture("со второго раза", "CHANNEL ВОПРОС r1", cfg) == "answer")
    ok("реплай на чужое не берётся", decide_capture("ага", "привет", cfg) is None)
    ok("префикс без пробела не команда", decide_capture("/postпуб", "", cfg) is None)

    ok("пустая команда это помощь", classify("/post", cfg)["kind"] == "help")
    ok("пуб это публикация", classify("/post пуб", cfg)["kind"] == "publish")
    ok("публикуй с точкой это публикация", classify("/post публикуй!", cfg)["kind"] == "publish")
    ok("что это статус", classify("/post что", cfg)["kind"] == "status")
    ok("что с хвостом это заявка", classify("/post что там по Notion", cfg)["kind"] == "request")
    ok("правь несёт хвост", classify("/post правь первую строку", cfg)["arg"] == "первую строку")
    ok("отложи несёт время", classify("/post отложи 20:30", cfg)["arg"] == "20:30")
    ok("стоп это отмена", classify("/post стоп", cfg)["kind"] == "cancel")
    ok("сырьё это заявка", classify("/post Notion даёт Business бесплатно", cfg)["kind"] == "request")
    ok("двоеточие после префикса", classify("/post: сделай пост", cfg)["kind"] == "request")
    ok("перенос строки в заявке", "\n" in classify("/post тема\nвторая строка", cfg)["arg"])

    rows = parse_mcp("ID: 11 | Me | Date: 2026-08-25 18:00:00+00:00 | Message: /post пуб\n"
                     "ID: 12 | Me | Date: 2026-08-25 18:01:00+00:00 | Message: /post тема\\nвторая строка\n"
                     "мусорная строка\n")
    ok("разбор вывода MCP: две строки", len(rows) == 2)
    ok("разбор вывода MCP: перенос", rows[1]["text"].endswith("вторая строка"))
    ok("разбор вывода MCP: id", rows[0]["msg_id"] == 11)

    ok("окно публикации по умолчанию", window_bounds(cfg) == ((16, 30), (21, 0)))
    tz = tzinfo_of(cfg)
    early = datetime.datetime(2026, 8, 25, 9, 0, tzinfo=tz)
    late = datetime.datetime(2026, 8, 25, 23, 0, tzinfo=tz)
    inside = datetime.datetime(2026, 8, 25, 18, 0, tzinfo=tz)
    ok("утром ждём окно", next_slot(cfg, None, early).hour == 16)
    ok("ночью уходим на завтра", next_slot(cfg, None, late).day == 26)
    ok("внутри окна публикуем скоро", next_slot(cfg, None, inside).hour == 18)
    ok("точное время в будущем", next_slot(cfg, "20:30", inside).hour == 20)

    # Полный проход по сценарию в отдельной папке, чтобы не тронуть настоящую.
    tmp = tempfile.mkdtemp(prefix="channel-tg-")
    old = os.environ.get("CHANNEL_TG_HOME")
    os.environ["CHANNEL_TG_HOME"] = tmp
    try:
        save_config(dict(DEFAULT_CONFIG))
        added = append_inbox(feed_rows(
            "ID: 20 | Me | Date: d | Message: /post пост про пак абузов\n"
            "ID: 21 | Me | Date: d | Message: CHANNEL ЧЕРНОВИК r1 эхо своего же сообщения\n"))
        ok("в ящик легла только заявка", added == 1)
        ok("повтор не дублируется", append_inbox(feed_rows("ID: 20 | Me | Date: d | Message: /post пост\n")) == 0)

        st = load_state()
        got = take_next(st, load_config())
        ok("next отдал заявку", got and got["kind"] == "request" and got["id"] == "r1")
        ok("курсор сдвинулся", load_state()["cursor"] == 20)
        ok("второй раз заявку не отдаёт", take_next(load_state(), load_config()) is None)

        sample = os.path.join(HERE, "sample-post.txt")
        args = argparse.Namespace(req="r1", file=sample, rubric="", media=False)
        code = cmd_stage(args)
        ok("stage пропустил чистый пост", code == 0)
        ok("черновик сохранён", os.path.exists(os.path.join(tmp, "drafts", "r1.txt")))

        cmd_sent(argparse.Namespace(req="r1", msg_id=99))
        ok("статус ждёт добро", find(load_state(), "r1")["status"] == "await")

        append_inbox([{"msg_id": 30, "text": "/post пуб", "src": "watch", "kind": "cmd"}])
        got = take_next(load_state(), load_config())
        ok("пуб нашёл свою заявку", got and got["kind"] == "publish" and got["id"] == "r1")

        with open(sample, encoding="utf-8") as handle:
            want = handle.read().strip("\n")
        out = os.path.join(tmp, "payload.txt")
        cmd_payload(argparse.Namespace(req="r1", out=out))
        with open(out, encoding="utf-8") as handle:
            got_text = handle.read().strip("\n")
        ok("payload отдаёт пост знак в знак", got_text == want)
        ok("в payload нет служебной шапки", not got_text.startswith("CHANNEL"))

        cmd_published(argparse.Namespace(req="r1", msg_id=612, link="https://t.me/demo_channel/612",
                                        scheduled=False, topic="", services=""))
        ok("заявка закрыта", find(load_state(), "r1")["status"] == "published")
        ok("живых заявок нет", not active(load_state()))
        ok("статус упоминает ссылку", "612" in status_text())

        append_inbox([{"msg_id": 40, "text": "/post пуб", "src": "watch", "kind": "cmd"}])
        got = take_next(load_state(), load_config())
        ok("пуб без черновика не находит цель", got and got["kind"] == "publish" and not got["id"])

        ok("карточка помощи начинается с метки", card_text().startswith("CHANNEL ПОМОЩЬ"))
        ok("карточка не уйдёт в ящик", decide_capture(card_text(), "", load_config()) is None)

        # проверка связи: короткое слово это ответ сторожа, а не заявка на пост
        ok("как дела это проверка связи",
           classify("/post как дела?", load_config())["kind"] == "ping")
        ok("привет это проверка связи",
           classify("/канал привет", load_config())["kind"] == "ping")
        ok("длинная строка остаётся заявкой",
           classify("/post как дела с абузами на курсор", load_config())["kind"] == "request")
        ok("ответ на связь в одну строку", "\n" not in ping_text())

        # ключи и строка сессии берутся из файла, а не только из окружения
        keep = {}
        for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "CHANNEL_SECRETS") + SESSION_ENVS:
            keep[key] = os.environ.pop(key, None)
        secret_dir = os.path.join(tmp, "secrets")
        os.environ["CHANNEL_SECRETS"] = secret_dir
        write_atomic(os.path.join(secret_dir, "watch.env"),
                     "# заметка\nTELEGRAM_API_ID=123456\nTELEGRAM_API_HASH=hash\n")
        info = creds()
        ok("ключи читаются из secrets",
           info["api_id"] == "123456" and info["api_hash"] == "hash")
        ok("без сессии просят login", any("login" in row for row in info["problems"]))
        path = save_session("STRING-FOR-TEST")
        ok("сессия легла в тот же файл", os.path.dirname(path) == secret_dir)
        again = creds()
        ok("сессия читается обратно", again["session"] == "STRING-FOR-TEST")
        ok("ключи не потерялись", again["api_id"] == "123456")
        ok("заметка не стала ключом", "# заметка" not in read_env_file(path))
        ok("ссылка на пост канала",
           link_for("@demo_channel", 612) == "https://t.me/demo_channel/612")
        ok("для Избранного ссылки нет", link_for("me", 5) == "")
        ok("канал берётся из настроек",
           target_of("channel", load_config()) == "@demo_channel")
        ok("Избранное остаётся me", target_of("Избранное", load_config()) == "me")
        for key, value in keep.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    finally:
        if old is None:
            os.environ.pop("CHANNEL_TG_HOME", None)
        else:
            os.environ["CHANNEL_TG_HOME"] = old
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    bad = [name for name, good in checks if not good]
    for name, good in checks:
        print("%s %s" % ("PASS" if good else "FAIL", name))
    print("Итого: %d проверок моста, провалилось %d" % (len(checks), len(bad)))
    return 1 if bad else 0


# ----------------------------------------------------------------------- разбор

def build_parser():
    ap = argparse.ArgumentParser(description="Мост между Избранным и каналом автора")
    ap.add_argument("--version", action="version", version="tg.py %s" % VERSION)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("doctor", help="проверить окружение моста")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("card", help="карточка команд для автора")
    p.set_defaults(func=cmd_card)

    p = sub.add_parser("next", help="следующая команда автора")
    p.add_argument("--wait", type=int, default=0, help="сколько секунд ждать, потолок %d" % MAX_WAIT)
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("feed", help="положить вывод list_messages в ящик")
    p.add_argument("--file", help="файл с выводом, по умолчанию stdin")
    p.add_argument("--stdin", action="store_true", help="читать stdin")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_feed)

    p = sub.add_parser("stage", help="проверить черновик и получить текст для Избранного")
    p.add_argument("req")
    p.add_argument("--file", required=True)
    p.add_argument("--rubric", default="")
    p.add_argument("--media", action="store_true")
    p.add_argument("--send", action="store_true", help="сразу отправить автору в Избранное")
    p.set_defaults(func=cmd_stage)

    p = sub.add_parser("sent", help="отметить, что черновик ушёл автору")
    p.add_argument("req")
    p.add_argument("--msg-id", dest="msg_id", required=True)
    p.set_defaults(func=cmd_sent)

    p = sub.add_parser("payload", help="текст поста для канала, знак в знак")
    p.add_argument("req")
    p.add_argument("--out")
    p.set_defaults(func=cmd_payload)

    p = sub.add_parser("ask", help="текст вопроса автору")
    p.add_argument("req")
    p.add_argument("--text", required=True)
    p.add_argument("--send", action="store_true", help="сразу отправить вопрос автору")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("asked", help="отметить id отправленного вопроса")
    p.add_argument("req")
    p.add_argument("--msg-id", dest="msg_id", required=True)
    p.set_defaults(func=cmd_asked)

    p = sub.add_parser("published", help="отметить публикацию")
    p.add_argument("req")
    p.add_argument("--msg-id", dest="msg_id", default="0")
    p.add_argument("--link", default="")
    p.add_argument("--scheduled", action="store_true")
    p.add_argument("--topic", default="", help="тема для лога постов")
    p.add_argument("--services", default="")
    p.set_defaults(func=cmd_published)

    p = sub.add_parser("cancel", help="отменить заявку")
    p.add_argument("req")
    p.add_argument("--why", default="")
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("status", help="что в работе")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("when", help="время следующей публикации в окне канала")
    p.add_argument("--at", help="точное время вида 20:30")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_when)

    p = sub.add_parser("config", help="посмотреть и поменять настройки")
    p.add_argument("--set", action="append", help="ключ=значение")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("setup", help="первый запуск: поставить telethon и войти")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("login", help="вход в Телеграм: номер и код")
    p.add_argument("--force", action="store_true", help="перелогин, даже если сессия есть")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("send", help="отправить текст себе или в канал")
    p.add_argument("--text", default="")
    p.add_argument("--file")
    p.add_argument("--to", default="me", help="me, channel или @имя")
    p.add_argument("--reply-to", dest="reply_to", type=int, default=0)
    p.add_argument("--at", help="отложить на время вида 20:30")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_send)

    p = sub.add_parser("ping", help="ответить автору, что смена идёт")
    p.add_argument("--reply-to", dest="reply_to", type=int, default=0)
    p.add_argument("--local", action="store_true", help="только напечатать")
    p.set_defaults(func=cmd_ping)

    p = sub.add_parser("poll", help="забрать заявки из Избранного без сторожа")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--json", action="store_true", dest="as_json")
    p.set_defaults(func=cmd_poll)

    p = sub.add_parser("publish", help="отправить черновик в канал")
    p.add_argument("req")
    p.add_argument("--to", default="channel")
    p.add_argument("--at", help="время вида 20:30, иначе сразу")
    p.add_argument("--topic", default="")
    p.add_argument("--services", default="")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("selftest", help="свои тесты")
    p.set_defaults(func=lambda a: selftest())
    return ap


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--selftest":
        return selftest()
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
