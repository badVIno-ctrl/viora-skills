#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai.py 1.0.0

Общение с нейронкой без внешнего агента. Только стандартная библиотека.

Зачем: до 5.3.0 скилл умел только готовить задание для чужого агента. Если агента рядом
нет, работа стояла. Теперь скилл сам ходит в модель по ключу автора.

Куда положить ключ (любой из вариантов):
    secrets/ai.env      строка CHANNEL_AI_KEY=sk-...
    переменная среды OPENROUTER_API_KEY или GEMINI_API_KEY и так далее

Команды:
    python3 tools/ai.py ask "текст"          один вопрос, один ответ
    python3 tools/ai.py chat "текст"         разговор с памятью
    python3 tools/ai.py chat --reset            забыть разговор
    python3 tools/ai.py --doctor                что настроено и живо ли
    python3 tools/ai.py --selftest              тесты без сети и без ключа

Коды возврата: 0 ответ есть, 2 ключа нет или модель не ответила.
"""

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "6.1.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import profile as P  # noqa: E402

TIMEOUT = 90
TRIES = 3
MAX_SYSTEM = 14000
DEFAULT_TEMP = 0.6
DEFAULT_TOKENS = 1400

_UNVERIFIED = ssl.create_default_context()
_UNVERIFIED.check_hostname = False
_UNVERIFIED.verify_mode = ssl.CERT_NONE

# Вид API решает, как лепить запрос. Их всего три на всю индустрию.
PROVIDERS = {
    "openrouter": {"kind": "openai", "base": "https://openrouter.ai/api/v1",
                   "env": ("OPENROUTER_API_KEY",),
                   "model": "deepseek/deepseek-chat", "needs_key": True},
    "groq": {"kind": "openai", "base": "https://api.groq.com/openai/v1",
             "env": ("GROQ_API_KEY",),
             "model": "llama-3.3-70b-versatile", "needs_key": True},
    "deepseek": {"kind": "openai", "base": "https://api.deepseek.com/v1",
                 "env": ("DEEPSEEK_API_KEY",),
                 "model": "deepseek-chat", "needs_key": True},
    "together": {"kind": "openai", "base": "https://api.together.xyz/v1",
                 "env": ("TOGETHER_API_KEY",),
                 "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo", "needs_key": True},
    "openai": {"kind": "openai", "base": "https://api.openai.com/v1",
               "env": ("OPENAI_API_KEY",),
               "model": "gpt-4o-mini", "needs_key": True},
    "mistral": {"kind": "openai", "base": "https://api.mistral.ai/v1",
                "env": ("MISTRAL_API_KEY",),
                "model": "mistral-small-latest", "needs_key": True},
    "gemini": {"kind": "gemini", "base": "https://generativelanguage.googleapis.com/v1beta",
               "env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
               "model": "gemini-2.0-flash", "needs_key": True},
    "anthropic": {"kind": "anthropic", "base": "https://api.anthropic.com/v1",
                  "env": ("ANTHROPIC_API_KEY",),
                  "model": "claude-3-5-haiku-20241022", "needs_key": True},
    "ollama": {"kind": "openai", "base": "http://127.0.0.1:11434/v1",
               "env": (), "model": "llama3.1", "needs_key": False},
    "lmstudio": {"kind": "openai", "base": "http://127.0.0.1:1234/v1",
                 "env": (), "model": "local-model", "needs_key": False},
}
# Порядок автовыбора: сначала то, что чаще всего есть у автора бесплатно.
ORDER = ("openrouter", "groq", "gemini", "deepseek", "mistral", "together",
         "openai", "anthropic", "ollama", "lmstudio")
SECRET_FILES = ("ai.env", "watch.env", "telegram.env")
NO_KEY = "\n".join([
    "AI: ключа нет, поэтому сам написать текст не могу.",
    "Что сделать: положи одну строку в secrets/ai.env",
    "    CHANNEL_AI_KEY=сюда_ключ",
    "Ключ берётся на openrouter.ai или console.groq.com, там есть бесплатные модели.",
    "Без ключа всё остальное работает: поиск, бриф, скелет, линтер, телеграм.",
])


# ------------------------------------------------------------------- ключи

def state_home():
    base = os.environ.get("CHANNEL_TG_HOME")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".local", "state", "channel-skill")
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        return ""
    return base


def secret_dirs():
    out = []
    if os.environ.get("CHANNEL_SECRETS"):
        out.append(os.environ["CHANNEL_SECRETS"])
    out.append(os.path.join(os.path.dirname(SKILL), "secrets"))
    out.append(os.path.join(SKILL, "secrets"))
    out.append(os.path.join(os.getcwd(), "secrets"))
    seen, uniq = set(), []
    for path in out:
        real = os.path.abspath(path)
        if real not in seen:
            seen.add(real)
            uniq.append(real)
    return uniq


def read_env_files():
    """Строки вида KEY=VALUE из файлов с ключами. Кавычки и решётки терпим."""
    found = {}
    for folder in secret_dirs():
        for name in SECRET_FILES:
            path = os.path.join(folder, name)
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    body = handle.read()
            except OSError:
                continue
            for line in body.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip().lstrip("\ufeff")
                value = value.strip().strip('"').strip("'")
                if key and value and key not in found:
                    found[key] = value
    return found


def settings(provider="", model="", base=""):
    """Кто отвечает, какой моделью и по какому ключу."""
    box = read_env_files()

    def value(name):
        return os.environ.get(name) or box.get(name) or ""

    provider = (provider or value("CHANNEL_AI_PROVIDER")).strip().lower()
    model = model or value("CHANNEL_AI_MODEL")
    base = base or value("CHANNEL_AI_BASE")
    common = value("CHANNEL_AI_KEY")

    order = [provider] if provider in PROVIDERS else list(ORDER)
    for name in order:
        spec = PROVIDERS[name]
        key = common
        if not key:
            for env_name in spec["env"]:
                key = value(env_name)
                if key:
                    break
        if not key and spec["needs_key"]:
            continue
        return {"provider": name, "kind": spec["kind"], "key": key,
                "model": model or spec["model"], "base": (base or spec["base"]).rstrip("/"),
                "ready": True}
    name = provider if provider in PROVIDERS else "openrouter"
    spec = PROVIDERS[name]
    return {"provider": name, "kind": spec["kind"], "key": "",
            "model": model or spec["model"], "base": (base or spec["base"]).rstrip("/"),
            "ready": False}


# -------------------------------------------------------------------- сеть

def fetch(url, payload, headers, timeout=TIMEOUT):
    """Один заход в модель.

    Повторы живут выше, в call. Так они работают с любым транспортом, а не только
    с этим: раньше повтор был спрятан внутри и при своей заглушке просто исчезал.
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hdr = {"Content-Type": "application/json", "Accept": "application/json"}
    hdr.update(headers or {})
    last = None
    for ctx in (None, _UNVERIFIED):
        req = urllib.request.Request(url, data=body, headers=hdr, method="POST")
        try:
            if ctx is None:
                resp = urllib.request.urlopen(req, timeout=timeout)
            else:
                resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:300]
            except Exception:  # noqa: BLE001
                pass
            raise IOError("HTTP %s %s" % (exc.code, detail))
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise last if last else IOError("модель не ответила")


FETCH = fetch

# Что лечится паузой и повтором, а что повторять бессмысленно.
RETRY_MARKS = ("http 408", "http 409", "http 425", "http 429", "http 500",
               "http 502", "http 503", "http 504", "timed out", "timeout",
               "temporarily", "connection reset", "connection aborted",
               "bad gateway", "overloaded")


def retryable(exc):
    low = str(exc).lower()
    return any(mark in low for mark in RETRY_MARKS)


# ------------------------------------------------------------------- запрос

def build(conf, messages, temperature, max_tokens):
    """Одна форма сообщений превращается в три разных API."""
    kind = conf["kind"]
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    talk = [m for m in messages if m["role"] != "system"]
    if kind == "openai":
        return ("%s/chat/completions" % conf["base"],
                {"Authorization": "Bearer %s" % conf["key"]} if conf["key"] else {},
                {"model": conf["model"], "messages": messages,
                 "temperature": temperature, "max_tokens": max_tokens})
    if kind == "gemini":
        url = "%s/models/%s:generateContent?key=%s" % (
            conf["base"], conf["model"], urllib.parse.quote(conf["key"]))
        payload = {"contents": [{"role": "user" if m["role"] == "user" else "model",
                                 "parts": [{"text": m["content"]}]} for m in talk],
                   "generationConfig": {"temperature": temperature,
                                        "maxOutputTokens": max_tokens}}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return url, {}, payload
    if kind == "anthropic":
        payload = {"model": conf["model"], "max_tokens": max_tokens,
                   "temperature": temperature,
                   "messages": [{"role": m["role"], "content": m["content"]} for m in talk]}
        if system:
            payload["system"] = system
        return ("%s/messages" % conf["base"],
                {"x-api-key": conf["key"], "anthropic-version": "2023-06-01"},
                payload)
    raise ValueError("неизвестный вид API: %s" % kind)


def parse(kind, raw):
    data = json.loads(raw)
    if kind == "openai":
        choices = data.get("choices") or []
        if not choices:
            raise IOError("пустой ответ модели")
        return (choices[0].get("message") or {}).get("content") or ""
    if kind == "gemini":
        cands = data.get("candidates") or []
        if not cands:
            raise IOError("модель отказалась ответить")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(part.get("text") or "" for part in parts)
    if kind == "anthropic":
        blocks = data.get("content") or []
        return "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    raise ValueError(kind)


ARROWS = ("\u2192", "\u2794", "\u27a1", "\u21d2", "->")
DASHES = ("\u2014", "\u2013", "\u2015", "\u2012", "\u2212")


def strip_slop(text):
    """Правило ноль скилла: длинных тире и стрелок в тексте быть не должно.

    Слабые модели сыпят их ведрами, поэтому чистим на выходе, а не ругаемся.
    """
    text = (text or "").replace("\r\n", "\n")
    for dash in DASHES:
        text = text.replace(" %s " % dash, ", ").replace(dash, "-")
    for arrow in ARROWS:
        text = text.replace(" %s " % arrow, ", ").replace(arrow, ",")
    text = re.sub(r"\*\*(ВАЖНО!?)\*\*", r"\1", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def system_prompt(short=True):
    """Свод правил скилла для модели. Слабой модели даём короткий свод."""
    name = "PROMPT-CORE.txt" if short else "PROMPT-FULL.txt"
    path = os.path.join(SKILL, name)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as handle:
                body = handle.read().strip()
            if body:
                return body[:MAX_SYSTEM]
        except OSError:
            pass
    return ("Ты пишешь за автора канала %s от первого лица. "
            "Коротко, сухо, без воды и без канцелярита. Цифры только из источников. "
            "Запрещены длинные тире и стрелки. Эмодзи не больше двух." % P.brand())


def call(messages, provider="", model="", base="", temperature=DEFAULT_TEMP,
         max_tokens=DEFAULT_TOKENS, clean=True):
    """Главная дверь для других скриптов."""
    conf = settings(provider, model, base)
    if not conf["ready"]:
        raise RuntimeError(NO_KEY)
    url, headers, payload = build(conf, messages, temperature, max_tokens)
    last = None
    for attempt in range(TRIES):
        try:
            raw = FETCH(url, payload, headers)
            text = parse(conf["kind"], raw)
            return strip_slop(text) if clean else text
        except ValueError as exc:
            raise IOError("модель ответила не по формату: %s" % str(exc)[:120])
        except Exception as exc:  # noqa: BLE001
            last = exc
            if not retryable(exc) or attempt + 1 >= TRIES:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise last if last else IOError("модель не ответила")


def ask(prompt, system="", **kwargs):
    messages = []
    if system is None:
        pass
    else:
        messages.append({"role": "system", "content": system or system_prompt()})
    messages.append({"role": "user", "content": prompt})
    return call(messages, **kwargs)


# ------------------------------------------------------------------ разговор

def chat_path():
    home = state_home()
    return os.path.join(home, "ai-chat.json") if home else ""


def chat_load(limit=12):
    path = chat_path()
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            rows = json.load(handle)
    except (OSError, ValueError):
        return []
    return [r for r in rows if r.get("role") in ("user", "assistant")][-limit:]


def chat_save(rows, limit=24):
    path = chat_path()
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(rows[-limit:], handle, ensure_ascii=False)
    except OSError:
        pass


def chat(text, **kwargs):
    history = chat_load()
    messages = [{"role": "system", "content": system_prompt()}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})
    answer = call(messages, **kwargs)
    chat_save(history + [{"role": "user", "content": text},
                         {"role": "assistant", "content": answer}])
    return answer


# -------------------------------------------------------------------- доктор

def doctor():
    conf = settings()
    print("ai.py %s, доктор нейронки" % VERSION)
    print("")
    box = read_env_files()
    where = [d for d in secret_dirs() if os.path.isdir(d)]
    print("  папки с ключами: %s" % (", ".join(where) if where else "не найдены"))
    print("  файловых ключей: %d" % len(box))
    print("  провайдер: %s" % conf["provider"])
    print("  модель: %s" % conf["model"])
    print("  адрес: %s" % conf["base"])
    print("  ключ: %s" % ("есть" if conf["key"] else "нет"))
    core = os.path.join(SKILL, "PROMPT-CORE.txt")
    print("  свод правил: %s" % ("есть" if os.path.exists(core) else "нет, возьму короткий"))
    print("")
    if not conf["ready"]:
        print(NO_KEY)
        return 2
    try:
        answer = ask("Ответь одним словом: готов", system="Отвечай одним словом.",
                     max_tokens=20, temperature=0)
    except Exception as exc:  # noqa: BLE001
        print("Модель не ответила: %s" % str(exc)[:200])
        print("Частые причины: неверный ключ, лимит бесплатного тарифа, нет интернета.")
        return 2
    print("Ответ модели: %s" % (answer or "пусто").strip()[:80])
    print("Всё работает. Можно писать посты одной командой.")
    return 0


# -------------------------------------------------------------------- тесты

def selftest():
    global FETCH
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    seen = {}

    def fake(url, payload, headers, timeout=TIMEOUT):
        seen["url"] = url
        seen["payload"] = payload
        seen["headers"] = headers
        if "generativelanguage" in url:
            return json.dumps({"candidates": [{"content": {"parts": [
                {"text": "Ответ гемини"}]}}]})
        if "anthropic" in url:
            return json.dumps({"content": [{"type": "text", "text": "Ответ клода"}]})
        return json.dumps({"choices": [{"message": {"role": "assistant",
                                                    "content": "Ответ модели"}}]})

    keep_env = {}
    for name in ("CHANNEL_AI_PROVIDER", "CHANNEL_AI_KEY", "CHANNEL_AI_MODEL", "CHANNEL_AI_BASE"):
        keep_env[name] = os.environ.get(name)
    old_fetch = FETCH
    try:
        os.environ["CHANNEL_AI_KEY"] = "test-key"
        FETCH = fake

        # Открытые API вида openai
        os.environ["CHANNEL_AI_PROVIDER"] = "openrouter"
        answer = ask("привет")
        ok("ответ openai разобран", answer == "Ответ модели")
        ok("адрес openai верный", seen["url"].endswith("/chat/completions"))
        ok("ключ ушёл в шапку", seen["headers"].get("Authorization") == "Bearer test-key")
        ok("свод правил ушёл в запрос",
           seen["payload"]["messages"][0]["role"] == "system")
        ok("вопрос ушёл в запрос", seen["payload"]["messages"][-1]["content"] == "привет")
        ok("модель по умолчанию есть", bool(seen["payload"]["model"]))

        # Гемини: свод правил идёт отдельным полем, а не в сообщениях
        os.environ["CHANNEL_AI_PROVIDER"] = "gemini"
        answer = ask("привет")
        ok("ответ гемини разобран", answer == "Ответ гемини")
        ok("ключ гемини в адресе", "key=test-key" in seen["url"])
        ok("свод правил у гемини отдельно", "systemInstruction" in seen["payload"])
        ok("роли гемини без system",
           all(c["role"] in ("user", "model") for c in seen["payload"]["contents"]))

        # Антропик: своя шапка и своё поле system
        os.environ["CHANNEL_AI_PROVIDER"] = "anthropic"
        answer = ask("привет")
        ok("ответ клода разобран", answer == "Ответ клода")
        ok("шапка клода верная", seen["headers"].get("x-api-key") == "test-key")
        ok("версия API клода есть", "anthropic-version" in seen["headers"])
        ok("свод правил у клода отдельно", "system" in seen["payload"])

        # Свой адрес и своя модель перебивают настройки по умолчанию
        os.environ["CHANNEL_AI_PROVIDER"] = "ollama"
        ask("привет", model="qwen2.5", base="http://127.0.0.1:9999/v1")
        ok("своя модель взята", seen["payload"]["model"] == "qwen2.5")
        ok("свой адрес взят", seen["url"].startswith("http://127.0.0.1:9999/v1"))

        # Разговор с памятью
        os.environ["CHANNEL_AI_PROVIDER"] = "openrouter"
        path = chat_path()
        if path and os.path.exists(path):
            os.remove(path)
        chat("первый вопрос")
        chat("второй вопрос")
        roles = [m["role"] for m in seen["payload"]["messages"]]
        ok("история подхватилась", roles.count("assistant") >= 1)
        ok("история легла на диск", len(chat_load()) >= 2)
        if path and os.path.exists(path):
            os.remove(path)

        # Чистка слопа
        dirty = "Шаг один \u2014 делаем так \u2192 потом так.\n\n\nИтог \u2013 готово.  "
        clean_text = strip_slop(dirty)
        ok("длинные тире вычищены", not any(d in clean_text for d in DASHES))
        ok("стрелки вычищены", not any(a in clean_text for a in ARROWS))
        ok("пустые строки сжаты", "\n\n\n" not in clean_text)
        ok("хвостовые пробелы сняты", clean_text == clean_text.strip())

        # Повторы и ошибки
        calls = {"n": 0}

        def flaky(url, payload, headers, timeout=TIMEOUT):
            calls["n"] += 1
            if calls["n"] < 2:
                raise IOError("HTTP 429 слишком часто")
            return json.dumps({"choices": [{"message": {"content": "Со второго раза"}}]})

        FETCH = flaky
        ok("ответ после повтора пришёл", ask("текст") == "Со второго раза")

        def broken(url, payload, headers, timeout=TIMEOUT):
            return json.dumps({"choices": []})

        FETCH = broken
        try:
            ask("текст")
            ok("пустой ответ замечен", False)
        except IOError:
            ok("пустой ответ замечен", True)

        # Без ключа говорим честно и с инструкцией
        FETCH = fake
        for name in list(os.environ):
            if name.endswith("_API_KEY"):
                keep_env.setdefault(name, os.environ[name])
                del os.environ[name]
        del os.environ["CHANNEL_AI_KEY"]
        os.environ["CHANNEL_AI_PROVIDER"] = "openrouter"
        os.environ["CHANNEL_SECRETS"] = os.path.join(SKILL, "tools", "tests", "nope")
        conf = settings()
        ok("без ключа не готовы", not conf["ready"])
        try:
            ask("текст")
            ok("без ключа честная ошибка", False)
        except RuntimeError as exc:
            ok("без ключа честная ошибка", "secrets/ai.env" in str(exc))

        # Локальные модели ключа не требуют
        os.environ["CHANNEL_AI_PROVIDER"] = "ollama"
        ok("локальная модель без ключа готова", settings()["ready"])
        ok("локальный адрес на месте", "127.0.0.1" in settings()["base"])

        # Свод правил и его размер
        prompt = system_prompt()
        ok("свод правил не пуст", len(prompt) > 200)
        ok("свод правил в лимите", len(prompt) <= MAX_SYSTEM)
        ok("в своде нет длинных тире", not any(d in prompt for d in DASHES[:4]))

        # Разбор чужих ошибок
        ok("неизвестный вид API падает явно", _raises(ValueError, parse, "чушь", "{}"))
        ok("кривой json падает явно", _raises(ValueError, parse, "openai", "не json"))
    finally:
        FETCH = old_fetch
        for name, value in keep_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        os.environ.pop("CHANNEL_SECRETS", None)

    bad = 0
    for name, good in checks:
        print("  %s  %s" % ("ок " if good else "НЕТ", name))
        bad += 0 if good else 1
    print("")
    print("ai.py: проверок %d, провалов %d" % (len(checks), bad))
    return 1 if bad else 0


def _raises(kind, func, *args):
    try:
        func(*args)
    except kind:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


# --------------------------------------------------------------------- вход

def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True, description="Общение с нейронкой")
    parser.add_argument("command", nargs="?", default="", help="ask или chat")
    parser.add_argument("text", nargs="*", help="текст вопроса")
    parser.add_argument("--provider", default="", help="имя провайдера")
    parser.add_argument("--model", default="", help="имя модели")
    parser.add_argument("--base", default="", help="свой адрес API")
    parser.add_argument("--temp", type=float, default=DEFAULT_TEMP)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_TOKENS)
    parser.add_argument("--system", default="", help="свой свод правил")
    parser.add_argument("--raw", action="store_true", help="без свода правил скилла")
    parser.add_argument("--file", default="", help="взять вопрос из файла")
    parser.add_argument("--out", default="", help="куда положить ответ")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--reset", action="store_true", help="забыть разговор")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print("ai.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()
    if args.doctor:
        return doctor()
    if args.reset:
        path = chat_path()
        if path and os.path.exists(path):
            os.remove(path)
        print("Разговор забыт.")
        return 0

    command = (args.command or "ask").lower()
    text = " ".join(args.text).strip()
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as handle:
                text = (text + "\n\n" + handle.read()).strip()
        except OSError as exc:
            print("Файл не читается: %s" % exc)
            return 2
    if command not in ("ask", "chat"):
        text = ("%s %s" % (args.command, text)).strip()
        command = "ask"
    if not text:
        print(__doc__.strip())
        return 2

    extra = {"provider": args.provider, "model": args.model, "base": args.base,
             "temperature": args.temp, "max_tokens": args.max_tokens}
    try:
        if command == "chat":
            answer = chat(text, **extra)
        else:
            system = None if args.raw else (args.system or system_prompt())
            answer = ask(text, system=system, **extra)
    except RuntimeError as exc:
        print(str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001
        print("Модель не ответила: %s" % str(exc)[:300])
        return 2

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(answer + "\n")
        except OSError as exc:
            print("Не смог записать: %s" % exc)
            return 2
    if args.json:
        conf = settings(args.provider, args.model, args.base)
        print(json.dumps({"provider": conf["provider"], "model": conf["model"],
                          "answer": answer}, ensure_ascii=False, indent=2))
    else:
        print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
