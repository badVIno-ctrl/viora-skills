#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tg_watch.py 1.0.0

Сторож Избранного. Слушает только чат с самим собой и кладёт в ящик моста
только то, что автор отправил агенту: сообщения с префиксом и ответы реплаем на
сообщения агента. Всё остальное личное и никуда не уходит.

Проверку связи, помощь и статус сторож отвечает сам, тем же подключением и
сразу. Агента будим только там, где нужен пост: на вопрос "как дела" ждать нечего.

Два режима. Без ключа сторож работает на агента в редакторе: заявку кладёт в
ящик и возвращает каркас поста с фактами и требованиями линтера. Ключ нужен
только для автономной работы, когда агента рядом нет.

Мозг. Если в secrets/ai.env лежит ключ любой модели, сторож сам отвечает на
свободный текст и сам гонит цепочку поста: поиск фактов, текст, автоправка,
оценка. Внешний агент для этого больше не нужен, но заявка всё равно ложится в
ящик: захочешь довести руками или агентом, всё на месте. Выключается ключом
brain=off в конфиге или переменной CHANNEL_BRAIN=off.

Почему сторож, а не MCP: MCP видит входящие сообщения от других людей, а свои
же исходящие в Избранном отбрасывает. Заявки автора берём сами: Telethon,
фильтр outgoing, только свой чат.

Запуск:
    python3 tools/tg_watch.py                 держать смену
    python3 tools/tg_watch.py --once --timeout 600
    python3 tools/tg_watch.py --doctor
    python3 tools/tg_watch.py --selftest

Ключи и строка сессии лежат в secrets/watch.env, читает их сам мост.
Сессия одна на всё: мост и сторож работают по очереди, а не одновременно.
Вход одной командой: python3 tools/tg.py login

Коды возврата: 0 порядок, 1 проблема.
"""

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile

VERSION = "6.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import tg as TG  # noqa: E402


def creds():
    """Доступы берём у моста: он читает и окружение, и secrets/watch.env.

    Раньше сторож смотрел только на переменные окружения, и запуск из обычной
    консоли заканчивался словами о нехватке доступов, хотя ключи лежали рядом.
    """
    info = TG.creds()
    return {"api_id": info["api_id"], "api_hash": info["api_hash"],
            "session": info["session"], "session_env": info["source"],
            "problems": list(info["problems"]), "warn": ""}


def quick_answer(text, cfg, verdict):
    """Что сторож отвечает сам: связь, помощь, статус. Остальное ждёт агента."""
    if verdict != "cmd":
        return ""
    cmd = TG.classify(text, cfg, verdict)
    kind = cmd.get("kind")
    if kind == "ping":
        return TG.ping_text(cfg)
    if kind == "help":
        return TG.card_text(cfg)
    if kind == "status":
        return TG.status_text(cfg)
    return ""


# ----------------------------------------------------------------------- мозг

# По этим словам видно, что человеку нужен текст в канал, а не разговор.
POST_WORDS = ("пост", "напиши", "разбор", "гайд", "абуз", "подборк", "сервис",
              "шортс", "девлог", "релиз", "опрос", "лидмагнит", "второй",
              "черновик", "текст в канал", "халяв", "бесплатн")
# А по этим видно разговор. Разговор сильнее: лучше ответить словами,
# чем выдать пост там, где его не просили.
TALK_WORDS = ("как дела", "что думаешь", "объясни", "почему", "зачем",
              "как лучше", "посоветуй", "что скажешь", "идеи", "придумай тем",
              "стоит ли", "что такое", "в чем разница", "в чём разница")

TOOL_TIMEOUT = 300


def brain_on(cfg):
    """Мозг работает, пока его явно не выключили."""
    value = cfg.get("brain")
    if value is None:
        value = os.environ.get("CHANNEL_BRAIN", "on")
    return str(value).strip().lower() not in ("off", "0", "no", "нет", "выкл")


def wants_post(text):
    """Заявка на пост или обычный вопрос."""
    low = " ".join((text or "").lower().split())
    if not low:
        return False
    if any(word in low for word in TALK_WORDS):
        return False
    if low.startswith("http") or " http" in low:
        return True
    return any(word in low for word in POST_WORDS)


def run_tool(script, args, timeout=TOOL_TIMEOUT):
    """Запустить скрипт скилла и вернуть код и вывод. Наружу не падаем."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        done = subprocess.run(
            [sys.executable, os.path.join(HERE, script)] + [str(a) for a in args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, "не успел за %d секунд, скажи короче или повтори" % timeout
    except OSError as err:
        return 1, "не запустился: %s" % err
    out = (done.stdout or b"").decode("utf-8", "replace").strip()
    err = (done.stderr or b"").decode("utf-8", "replace").strip()
    return done.returncode, out or err


# Тесты подменяют эту точку, а не сам subprocess: так видно, кого звали.
RUNNER = run_tool


def fit(text, limit=None):
    """В Телеграме есть потолок сообщения, и ломаться о него глупо."""
    limit = int(limit or TG.TG_LIMIT)
    body = text or ""
    if len(body) <= limit:
        return body
    return body[:limit - 60].rstrip() + "\n\nдальше обрезал, чтобы влезло в сообщение"


HANDOFF = "\n".join([
    "Текст добери агентом в редакторе: правила он читает сам из SKILL.md.",
    "Заявка уже в ящике: python3 tools/tg.py next --json",
])

NO_BRAIN = "\n".join([
    "Ключа модели нет, и это нормально: скилл рассчитан на агента в редакторе.",
    "Заявку записал, забери её командой: python3 tools/tg.py next --json",
    "Хочешь ответы прямо в телеге, положи один ключ в secrets/ai.env",
])


def ai_ready():
    """Есть ли чем писать самому. Без ключа работаем на агента, а не падаем."""
    try:
        import ai as AI
        return bool(AI.settings().get("ready"))
    except Exception:
        return False


# Тесты подменяют эту точку: так проверяются оба режима, с ключом и без.
READY = ai_ready


def brain_reply(text, cfg):
    """Ответ на свободный текст: цепочка поста, разговор или каркас агенту.

    Ответ всегда начинается с маркера: свои же сообщения сторож в ящик не
    кладёт, иначе он услышит сам себя и уйдёт в круг.
    """
    body = (text or "").strip()
    if not body:
        return ""
    marker = str(cfg.get("marker") or "CHANNEL")
    smart = READY()
    if wants_post(body):
        code, out = RUNNER("post.py", [body] if smart else [body, "--no-ai"])
        if not out:
            return ""
        if not smart:
            return "%s КАРКАС, модели нет\n%s\n\n%s" % (marker, out, HANDOFF)
        head = "%s ЧЕРНОВИК" % marker if not code else "%s ЧЕРНОВИК, есть замечания" % marker
        return "%s\n%s" % (head, out)
    if not smart:
        return "%s БЕЗ МОДЕЛИ\n%s" % (marker, NO_BRAIN)
    code, out = RUNNER("ai.py", ["ask", body])
    if not out:
        return ""
    if code:
        # Сырую ругань транспорта в телегу не тащим: толку ноль, шума много.
        return "%s НЕ ВЫШЛО\nМодель не ответила. Проверка: python3 tools/ai.py --doctor\n%s" % (
            marker, HANDOFF)
    return "%s ОТВЕТ\n%s" % (marker, out)


def telethon_parts():
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    return TelegramClient, events, StringSession


def doctor():
    info = creds()
    print("Сторож Избранного, tg_watch.py %s" % VERSION)
    print("")
    have_telethon = TG.telethon_ready()
    print("  telethon         %s"
          % ("ок" if have_telethon else "нет, встанет сам: python3 tools/tg.py setup"))
    print("  ключи api        %s"
          % ("ок" if info["api_id"] and info["api_hash"] else "нет в secrets/watch.env"))
    print("  строка сессии   %s"
          % (info["session_env"] or "нет, вход: python3 tools/tg.py login"))
    print("  ящик моста      %s" % TG.paths()["home"])
    cfg = TG.load_config()
    print("  префикс          %s" % ", ".join(cfg["prefixes"]))
    print("  ответ реплаем   %s" % ("ловлю" if cfg.get("reply_capture") else "не ловлю"))
    if info["warn"]:
        print("")
        print("  внимание: %s" % info["warn"])
    if info["problems"] or not have_telethon:
        print("")
        for item in info["problems"]:
            print("  не хватает: %s" % item)
        print("  одной командой: python3 tools/tg.py setup")
        return 1
    print("")
    print("Готов держать смену.")
    return 0


async def serve(args):
    info = creds()
    if info["problems"]:
        for item in info["problems"]:
            print("не хватает: %s" % item)
        print("одной командой: python3 tools/tg.py setup")
        return 1
    if info["warn"]:
        print("внимание: %s" % info["warn"])
    try:
        TelegramClient, events, StringSession = telethon_parts()
    except Exception:
        print("нет telethon: pip install telethon")
        return 1

    cfg = TG.load_config()
    TG.ensure_home()
    client = TelegramClient(
        StringSession(info["session"]), int(info["api_id"]), info["api_hash"],
        device_model=os.environ.get("TELEGRAM_DEVICE_MODEL", "CHANNEL watch"),
        system_version=os.environ.get("TELEGRAM_SYSTEM_VERSION", "1.0"),
        app_version=os.environ.get("TELEGRAM_APP_VERSION", VERSION),
    )
    caught = asyncio.Event()

    await client.connect()
    if not await client.is_user_authorized():
        print("строка сессии не подошла: python3 tools/tg.py login --force")
        await client.disconnect()
        return 1
    me = await client.get_me()
    mine = int(getattr(me, "id", 0))

    @client.on(events.NewMessage(outgoing=True))
    async def on_out(event):
        try:
            if int(getattr(event, "chat_id", 0) or 0) != mine or not event.is_private:
                return
            text = event.raw_text or ""
            parent_text = ""
            reply_to = int(getattr(event, "reply_to_msg_id", 0) or 0)
            if reply_to and cfg.get("reply_capture"):
                try:
                    parent = await event.get_reply_message()
                    parent_text = getattr(parent, "raw_text", "") or ""
                except Exception:
                    parent_text = ""
            verdict = TG.decide_capture(text, parent_text, cfg)
            if not verdict:
                return
            quick = quick_answer(text, cfg, verdict)
            if quick:
                await event.reply(quick, parse_mode=None, link_preview=False)
                print("ответил сам: %s" % TG.brief_of(quick))
                return
            row = {"msg_id": int(event.id), "text": text, "kind": verdict, "src": "watch",
                   "date": str(getattr(event.message, "date", "")), "reply_to": reply_to}
            if TG.append_inbox([row]):
                print("взял %s id %d: %s" % (verdict, row["msg_id"], TG.brief_of(text)))
                caught.set()

            # Мозг отвечает сам, но заявка уже в ящике: если ответ не зайдёт,
            # есть чем довести руками или внешним агентом.
            if verdict != "cmd" or not brain_on(cfg):
                return
            cmd = TG.classify(text, cfg, verdict)
            if cmd.get("kind") != "request" or not cmd.get("arg"):
                return
            loop = asyncio.get_event_loop()
            answer = await loop.run_in_executor(None, brain_reply, cmd["arg"], cfg)
            if answer:
                await event.reply(fit(answer), parse_mode=None, link_preview=False)
                print("ответил сам: %s" % TG.brief_of(answer))
        except Exception as err:  # сторож не падает из-за одного сообщения
            print("ошибка на сообщении: %s" % err)

    print("Смена началась. Слушаю Избранное, префикс %s" % ", ".join(cfg["prefixes"]))
    print("Ящик: %s" % TG.paths()["home"])
    if args.once:
        try:
            await asyncio.wait_for(caught.wait(), timeout=max(5, int(args.timeout)))
        except asyncio.TimeoutError:
            print("за %d с ничего не пришло" % int(args.timeout))
        await client.disconnect()
        return 0
    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()
    return 0


def selftest():
    global RUNNER, READY
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    cfg = dict(TG.DEFAULT_CONFIG)
    ok("ядро моста подгружается", hasattr(TG, "append_inbox") and hasattr(TG, "decide_capture"))
    ok("версии совпадают", TG.VERSION == VERSION)
    ok("личное не берём", TG.decide_capture("напомнить про зал", "", cfg) is None)
    ok("заявку берём", TG.decide_capture("/post пост про Notion", "", cfg) == "cmd")
    ok("ответ реплаем берём", TG.decide_capture("да, так и было", "CHANNEL ВОПРОС r3", cfg) == "answer")

    old = {}
    for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "CHANNEL_SECRETS",
                "CHANNEL_TG_HOME") + TG.SESSION_ENVS:
        old[key] = os.environ.pop(key, None)
    tmp = tempfile.mkdtemp(prefix="channel-watch-")
    try:
        os.environ["CHANNEL_SECRETS"] = os.path.join(tmp, "secrets")
        os.environ["CHANNEL_TG_HOME"] = os.path.join(tmp, "state")
        empty = creds()
        ok("без доступов говорим три вещи", len(empty["problems"]) == 3)
        ok("вторая сессия больше не нужна",
           all("WATCH" not in row for row in empty["problems"]))
        TG.write_atomic(
            os.path.join(tmp, "secrets", "watch.env"),
            "TELEGRAM_API_ID=123456\nTELEGRAM_API_HASH=hash\n"
            "TELEGRAM_SESSION_STRING_WATCH=own\n")
        full = creds()
        ok("ключи и сессия берутся из файла",
           not full["problems"] and full["session"] == "own")
        ok("видно, что сессия из secrets", "secrets" in full["session_env"])
        ok("на проверку связи отвечаем сразу",
           quick_answer("/post как дела", cfg, "cmd").startswith(cfg["marker"]))
        ok("помощь отдаём сразу", "ПОМОЩЬ" in quick_answer("/post", cfg, "cmd"))
        ok("заявку быстрым ответом не гасим",
           quick_answer("/post пост про Notion", cfg, "cmd") == "")
        ok("ответ реплаем отдаём агенту",
           quick_answer("да, так и было", cfg, "answer") == "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # Мозг: куда уходит свободный текст и что возвращается в телегу
    ok("заявку на пост узнаём", wants_post("пост про халявный доступ к моделям"))
    ok("ссылка тоже заявка", wants_post("https://example.com глянь и сделай"))
    ok("разговор постом не считаем", not wants_post("объясни, почему так вышло"))
    ok("пустота не заявка", not wants_post("   "))
    ok("мозг включён по умолчанию", brain_on(cfg))
    ok("мозг выключается конфигом", not brain_on(dict(cfg, brain="off")))

    calls = []

    def fake_runner(script, args, timeout=0):
        calls.append((script, [str(a) for a in args]))
        return 0, "готовый текст"

    keep = RUNNER
    RUNNER = fake_runner
    try:
        answer = brain_reply("пост про халяву в кодинге", cfg)
        ok("заявка идёт в цепочку поста", calls and calls[0][0] == "post.py")
        ok("тема дошла до цепочки", calls and "халяву" in calls[0][1][0])
        ok("ответ начинается с маркера", answer.startswith(cfg["marker"]))
        ok("свой ответ в ящик не вернётся",
           TG.decide_capture(answer, "", cfg) is None)
        ok("тело поста на месте", "готовый текст" in answer)
        del calls[:]
        answer = brain_reply("объясни, почему так вышло", cfg)
        ok("вопрос идёт в нейронку", calls and calls[0][0] == "ai.py")
        ok("вопрос ушёл командой ask", calls and calls[0][1][:1] == ["ask"])
        ok("на вопрос отвечаем словами", "ОТВЕТ" in answer)
        del calls[:]
        ok("пустой текст никого не будит", brain_reply("  ", cfg) == "" and not calls)

        # Режим без ключа: работаем на агента в редакторе, а не сыплем ошибками
        keep_ready = READY
        READY = lambda: False
        try:
            del calls[:]
            answer = brain_reply("пост про халяву в кодинге", cfg)
            ok("без ключа цепочку зовём без модели",
               calls and calls[0][1][-1] == "--no-ai")
            ok("без ключа отдаём каркас",
               "КАРКАС" in answer and "готовый текст" in answer)
            ok("каркас начинается с маркера", answer.startswith(cfg["marker"]))
            ok("каркас в ящик не вернётся", TG.decide_capture(answer, "", cfg) is None)
            ok("каркас передаёт работу агенту", "tg.py next" in answer)
            del calls[:]
            answer = brain_reply("объясни, почему так вышло", cfg)
            ok("без ключа модель не зовём", not calls)
            ok("без ключа говорим, что делать", "secrets/ai.env" in answer)
            ok("подсказка начинается с маркера", answer.startswith(cfg["marker"]))
        finally:
            READY = keep_ready

        # Модель есть, но не ответила: в телегу идёт проверка, а не ругань сети
        def broken_runner(script, args, timeout=0):
            calls.append((script, [str(a) for a in args]))
            return 2, "Модель не ответила: <urlopen error [Errno 111] Connection refused>"

        RUNNER = broken_runner
        del calls[:]
        answer = brain_reply("объясни, почему так вышло", cfg)
        ok("ругань сети не пересылаем", "urlopen" not in answer)
        ok("вместо ругани даём проверку", "--doctor" in answer)
        ok("провал начинается с маркера", answer.startswith(cfg["marker"]))
    finally:
        RUNNER = keep

    ok("длинный ответ влезает в сообщение",
       len(fit("я" * (TG.TG_LIMIT + 500))) <= TG.TG_LIMIT)
    ok("короткий ответ не трогаем", fit("коротко") == "коротко")

    bad = [name for name, good in checks if not good]
    for name, good in checks:
        print("%s %s" % ("PASS" if good else "FAIL", name))
    print("Итого: %d проверок сторожа, провалилось %d" % (len(checks), len(bad)))
    return 1 if bad else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="Сторож Избранного в Телеграме")
    ap.add_argument("--once", action="store_true", help="выйти после первой заявки")
    ap.add_argument("--timeout", type=int, default=600, help="сколько ждать в режиме --once")
    ap.add_argument("--doctor", action="store_true", help="проверить доступы")
    ap.add_argument("--selftest", action="store_true", help="свои тесты")
    ap.add_argument("--version", action="version", version="tg_watch.py %s" % VERSION)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.doctor:
        return doctor()
    try:
        return asyncio.run(serve(args))
    except KeyboardInterrupt:
        print("смена закончена")
        return 0


if __name__ == "__main__":
    sys.exit(main())
