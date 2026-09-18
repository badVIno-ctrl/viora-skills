#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
search.py 1.0.0

Глубокий поиск фактов для постов автора и для кодинга.
Только стандартная библиотека Python 3.8+. Ключей нет, установки нет.

Зачем этот файл, если есть research.py. research.py умел три движка и один
запрос. Если DuckDuckGo молчал, поиск молчал весь. Ещё он ничего не знал про
кодинг: на вопрос про ошибку в библиотеке он приносил новости. Здесь другое:
восемь источников и пять веб-движков, план запросов из одной темы, ранжирование,
кэш и бриф, по которому пост пишет даже слабая модель.

Быстрый вход:
    python3 tools/search.py "Cursor free tier limits 2026"
    python3 tools/search.py "тема" --brief          факт-пак под пост
    python3 tools/search.py "ошибка telethon flood wait" --profile code
    python3 tools/search.py --read "https://..."
    python3 tools/search.py "тема" --plan            только план запросов
    python3 tools/search.py --doctor
    python3 tools/search.py --selftest               тесты без сети

Коды возврата: 0 нашлось, 2 не нашлось или сети нет.
"""

import argparse
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

VERSION = "6.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.1.0.0 Safari/537.36")
TIMEOUT = 12
READ_TIMEOUT = 20
TRIES = 2
DEFAULT_BUDGET = 1800
BRIEF_BUDGET = 2600
DEFAULT_LIMIT = 8
CACHE_TTL = 6 * 3600
WORKERS = 6

NO_NET = ("SEARCH: сети нет или все движки молчат. "
          "Пиши по сырью автора, цифры не выдумывай.")

# Профиль решает, куда идти. Автор говорит тему, профиль выбирает источники сам.
PROFILES = {
    "post": ("web", "wiki", "github", "hn"),
    "code": ("web", "stack", "github", "issues", "pkg", "hn"),
    "news": ("web", "hn", "reddit"),
    "deep": ("web", "wiki", "github", "issues", "stack", "hn", "reddit", "pkg"),
}
ALL_SOURCES = ("web", "wiki", "github", "issues", "stack", "hn", "reddit", "pkg")

# Доверие к домену. Первоисточник и документация выше блогов и агрегаторов.
TRUST = {
    "github.com": 9, "docs.python.org": 9, "developer.mozilla.org": 9,
    "stackoverflow.com": 8, "pypi.org": 8, "npmjs.com": 8, "wikipedia.org": 7,
    "news.ycombinator.com": 6, "habr.com": 6, "openai.com": 8, "anthropic.com": 8,
    "google.dev": 8, "ai.google.dev": 8, "telegram.org": 9, "core.telegram.org": 9,
    "notion.so": 8, "notion.com": 8, "cursor.com": 8, "cursor.sh": 8,
    "openrouter.ai": 8, "huggingface.co": 8, "reddit.com": 5, "medium.com": 3,
    "dev.to": 4, "vc.ru": 4, "dzen.ru": 2, "pikabu.ru": 1,
}
# Мусор: копипаст-сайты и агрегаторы, из них факт брать нельзя.
JUNK = ("pinterest.", "quora.com", "answers.", "coupons", "promokod", "kupon",
        "tracker", "utm_", "aliexpress", "amazon.", "ebay.")
SEARCH_HOSTS = ("duckduckgo.com", "mojeek.com", "google.", "bing.com", "yandex.",
                "searx", "startpage.com", "ecosia.org", "brave.com", "marginalia")

# Слова, по которым видно, что вопрос про код, а не про сервис для канала.
CODE_WORDS = (
    "ошибка", "error", "traceback", "exception", "баг", "bug", "падает", "crash",
    "api", "sdk", "библиотек", "library", "пакет", "package", "версия", "version",
    "install", "установ", "import", "компил", "build", "deploy", "docker",
    "python", "node", "npm", "pip", "typescript", "javascript", "react", "rust",
    "sql", "regex", "async", "поток", "thread", "timeout", "flood",
    "telethon", "webhook", "токен", "token", "аутентифик", "auth", "cors",
    "как исправить", "how to fix", "не работает код", "почему падает",
)
# Слова про деньги и лимиты: они тянут за собой страницу тарифов.
PRICE_WORDS = ("бесплатн", "халяв", "триал", "trial", "free", "лимит", "limit",
               "цена", "price", "pricing", "тариф", "кредит", "credit", "подписк")

_UNVERIFIED = ssl.create_default_context()
_UNVERIFIED.check_hostname = False
_UNVERIFIED.verify_mode = ssl.CERT_NONE


# ------------------------------------------------------------------------ сеть

def fetch(url, data=None, headers=None, timeout=TIMEOUT):
    """Одна дорога в интернет. Два подхода, потом честный отказ."""
    hdr = {"User-Agent": UA, "Accept-Language": "ru,en;q=0.9",
           "Accept": "text/html,application/json,*/*",
           "Accept-Encoding": "identity"}
    if headers:
        hdr.update(headers)
    body = urllib.parse.urlencode(data).encode("utf-8") if data else None
    last = None
    for attempt in range(TRIES):
        for ctx in (None, _UNVERIFIED):
            req = urllib.request.Request(url, data=body, headers=hdr)
            try:
                if ctx is None:
                    resp = urllib.request.urlopen(req, timeout=timeout)
                else:
                    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
                raw = resp.read()
                enc = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(enc, "replace")
            except Exception as exc:  # noqa: BLE001
                last = exc
        if attempt + 1 < TRIES:
            time.sleep(0.4 * (attempt + 1))
    raise last if last else IOError("нет ответа")


# Точка подмены для тестов: селфтест гоняет весь конвейер без сети.
FETCH = fetch


def get(url, data=None, headers=None, timeout=TIMEOUT):
    return FETCH(url, data=data, headers=headers, timeout=timeout)


def get_json(url, headers=None, timeout=TIMEOUT):
    return json.loads(get(url, headers=headers, timeout=timeout))


# ----------------------------------------------------------------------- текст

class _Strip(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer", "form"}
    BREAK = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"}

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.buf = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BREAK:
            self.buf.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag in self.BREAK:
            self.buf.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)

    def result(self):
        text = "".join(self.buf).replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]*", "\n", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def strip_tags(raw):
    parser = _Strip()
    try:
        parser.feed(raw)
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", raw)
    return parser.result()


def clean(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    for bad, good in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"),
                      ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " "),
                      ("&#x27;", "'"), ("&hellip;", "...")):
        text = text.replace(bad, good)
    # Длинные тире в скилле вне закона: вычищаем на входе, а не в посте.
    for dash in ("\u2014", "\u2013", "\u2015", "\u2012"):
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip()


def trim(text, size):
    text = clean(text)
    if size <= 0 or len(text) <= size:
        return text
    cut = text[:size]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if stop < size * 0.5:
        stop = cut.rfind(" ")
    if stop <= 0:
        stop = size
    return cut[:stop].rstrip(" ,.;:") + "..."


def host_of(url):
    try:
        return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")
    except ValueError:
        return ""


def words_of(text):
    return [w for w in re.split(r"[^\w+.#-]+", (text or "").lower()) if len(w) > 2]


# ------------------------------------------------------------------ план запросов

def looks_like_code(topic):
    low = " " + (topic or "").lower() + " "
    return any(word in low for word in CODE_WORDS)


def looks_like_price(topic):
    low = (topic or "").lower()
    return any(word in low for word in PRICE_WORDS)


def latin_core(topic):
    """Латиница и цифры из темы: имена сервисов ищутся только так."""
    keep = re.findall(r"[A-Za-z][A-Za-z0-9.+_-]{1,}|\d+(?:\.\d+)?", topic or "")
    out, seen = [], set()
    for item in keep:
        low = item.lower()
        if low in seen or low in ("http", "https", "www", "com"):
            continue
        seen.add(low)
        out.append(item)
    return " ".join(out).strip()


def year_now():
    return datetime.now().year


def plan_queries(topic, profile="post", limit=5):
    """Из одной темы автора сделать несколько запросов под разные факты.

    Это главное место, которое снимает работу со слабой модели: ей не надо
    придумывать формулировки, за неё думает план. Правило простое: имя
    латиницей плюс то, что нужно знать, плюс год.
    """
    topic = " ".join((topic or "").split())
    if not topic:
        return []
    year = str(year_now())
    core = latin_core(topic) or topic
    out = [topic]
    if profile == "code":
        out.append("%s fix solution" % core)
        out.append("%s stackoverflow" % core)
        out.append("%s github issue" % core)
        out.append("%s docs %s" % (core, year))
    elif profile == "news":
        out.append("%s %s" % (core, year))
        out.append("%s release announcement" % core)
        out.append("%s news" % core)
    else:
        if core.lower() != topic.lower():
            out.append("%s %s" % (core, year))
        out.append("%s pricing free tier limits %s" % (core, year))
        out.append("%s free plan limit requests" % core)
        if looks_like_price(topic):
            out.append("%s trial without card" % core)
        else:
            out.append("%s review problems" % core)
    seen, uniq = set(), []
    for item in out:
        key = " ".join(item.lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        uniq.append(" ".join(item.split()))
    return uniq[:max(1, limit)]


def pick_profile(topic, given=""):
    if given:
        return given if given in PROFILES else "post"
    return "code" if looks_like_code(topic) else "post"


# --------------------------------------------------------------------- движки

def _unwrap(href):
    if href.startswith("//"):
        href = "https:" + href
    hit = re.search(r"[?&]uddg=([^&]+)", href)
    if hit:
        href = urllib.parse.unquote(hit.group(1))
    hit = re.search(r"[?&]url=(https?%3A[^&]+)", href)
    if hit:
        href = urllib.parse.unquote(hit.group(1))
    return href


def _anchors(raw):
    """Ссылки с текстом из выдачи любого движка."""
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                                 raw, re.IGNORECASE | re.DOTALL):
        url = _unwrap(href)
        if not url.startswith("http"):
            continue
        host = host_of(url)
        if not host or any(bad in host for bad in SEARCH_HOSTS):
            continue
        if any(bad in url.lower() for bad in JUNK):
            continue
        title = clean(label)
        if len(title) < 8 or len(url) > 300:
            continue
        out.append((url, title))
    return out


def _snippets(raw):
    got = re.findall(r'class="[^"]*(?:result-snippet|result__snippet|snippet|s)[^"]*"[^>]*>(.*?)</',
                     raw, re.IGNORECASE | re.DOTALL)
    return [clean(s) for s in got if len(clean(s)) > 20]


def _days_code(days):
    if not days:
        return ""
    if days <= 1:
        return "d"
    if days <= 7:
        return "w"
    if days <= 31:
        return "m"
    return "y"


WEB_ENGINES = ("ddg-lite", "ddg-html", "mojeek", "searx", "marginalia")


def _web_engine(name, query, days):
    if name == "ddg-lite":
        return get("https://lite.duckduckgo.com/lite/", data={"q": query})
    if name == "ddg-html":
        return get("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
            {"q": query, "df": _days_code(days)}))
    if name == "mojeek":
        return get("https://www.mojeek.com/search?" + urllib.parse.urlencode(
            {"q": query, "t": "20"}))
    if name == "searx":
        return get("https://searx.be/search?" + urllib.parse.urlencode(
            {"q": query, "language": "ru"}))
    if name == "marginalia":
        return get("https://search.marginalia.nu/search?" + urllib.parse.urlencode(
            {"query": query}))
    raise ValueError(name)


def search_web(query, limit, days=0):
    """Веб-поиск через пять движков по очереди. Один упал, работает следующий.

    Если молчат все, мы говорим об этом вслух. Молчаливый пустой список хуже
    ошибки: автор решит, что фактов нет, а на самом деле упала сеть.
    """
    errors = []
    for name in WEB_ENGINES:
        try:
            raw = _web_engine(name, query, days)
        except Exception as exc:  # noqa: BLE001
            errors.append("%s: %s" % (name, str(exc)[:40]))
            continue
        low = raw.lower()
        if ("captcha" in low or "unusual traffic" in low) and len(raw) < 6000:
            continue
        pairs = _anchors(raw)
        if not pairs:
            continue
        snips = _snippets(raw)
        out = []
        for idx, (url, title) in enumerate(pairs[:limit * 2]):
            out.append({"src": "web", "engine": name, "title": title, "url": url,
                        "text": snips[idx] if idx < len(snips) else "", "date": ""})
        if out:
            return out[:limit]
    if len(errors) == len(WEB_ENGINES):
        raise IOError("все веб-движки молчат: " + "; ".join(errors[:2]))
    return []


def search_wiki(query, limit, days=0):
    """Википедия: короткое определение, чтобы не путать сервис с тёзкой."""
    out, errors = [], []
    for lang in ("ru", "en"):
        url = "https://%s.wikipedia.org/w/api.php?" % lang + urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": max(1, min(limit, 3)), "format": "json", "utf8": 1})
        try:
            data = get_json(url)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc)[:40])
            continue
        for row in (data.get("query", {}).get("search") or [])[:limit]:
            title = clean(row.get("title") or "")
            out.append({"src": "wiki", "engine": lang, "title": title,
                        "url": "https://%s.wikipedia.org/wiki/%s"
                               % (lang, urllib.parse.quote(title.replace(" ", "_"))),
                        "text": clean(row.get("snippet") or ""),
                        "date": (row.get("timestamp") or "")[:10]})
        if out:
            break
    if not out and len(errors) == 2:
        raise IOError("википедия не ответила: " + errors[0])
    return out[:limit]


def search_github(query, limit, days=0):
    """Репозитории: звёзды, язык, лицензия и дата последнего коммита."""
    q = query
    if days:
        since = (datetime.now(timezone.utc) - timedelta(days=max(days, 30))).strftime("%Y-%m-%d")
        q = "%s pushed:>=%s" % (query, since)
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({
        "q": q, "sort": "stars", "order": "desc", "per_page": max(limit, 3)})
    data = get_json(url, headers={"Accept": "application/vnd.github+json"})
    out = []
    for item in (data.get("items") or [])[:limit]:
        lic = (item.get("license") or {}).get("spdx_id") or "лицензии нет"
        pushed = (item.get("pushed_at") or "")[:10]
        out.append({"src": "github", "engine": "api",
                    "title": item.get("full_name") or "",
                    "url": item.get("html_url") or "",
                    "text": "%s. звёзд %s, язык %s, лицензия %s, последний коммит %s" % (
                        clean(item.get("description") or "описания нет"),
                        item.get("stargazers_count"), item.get("language") or "?",
                        lic, pushed or "?"),
                    "date": pushed})
    return out


def search_issues(query, limit, days=0):
    """Задачи и обсуждения на GitHub: тут живут реальные грабли и обходы."""
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({
        "q": "%s in:title" % query, "sort": "updated", "order": "desc",
        "per_page": max(limit, 3)})
    data = get_json(url, headers={"Accept": "application/vnd.github+json"})
    out = []
    for item in (data.get("items") or [])[:limit]:
        state = item.get("state") or "?"
        body = clean(item.get("body") or "")[:400]
        out.append({"src": "issues", "engine": "github",
                    "title": clean(item.get("title") or ""),
                    "url": item.get("html_url") or "",
                    "text": "%s, комментариев %s. %s" % (
                        "открыта" if state == "open" else "закрыта",
                        item.get("comments"), body),
                    "date": (item.get("updated_at") or "")[:10]})
    return out


def search_stack(query, limit, days=0):
    """Stack Overflow через открытое API: принятый ответ важнее блогов."""
    params = {"order": "desc", "sort": "relevance", "q": query, "site": "stackoverflow",
              "pagesize": max(limit, 3), "filter": "default"}
    if days:
        params["fromdate"] = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    data = get_json("https://api.stackexchange.com/2.3/search/advanced?"
                    + urllib.parse.urlencode(params))
    out = []
    for item in (data.get("items") or [])[:limit]:
        when = ""
        if item.get("last_activity_date"):
            when = datetime.fromtimestamp(int(item["last_activity_date"]),
                                          timezone.utc).strftime("%Y-%m-%d")
        out.append({"src": "stack", "engine": "api",
                    "title": clean(item.get("title") or ""),
                    "url": item.get("link") or "",
                    "text": "%s, голосов %s, ответов %s%s" % (
                        "ответ принят" if item.get("is_answered") else "ответ не принят",
                        item.get("score"), item.get("answer_count"),
                        ", теги " + ", ".join(item.get("tags") or [])[:80]),
                    "date": when})
    return out


def search_hn(query, limit, days=0):
    params = {"query": query, "tags": "story", "hitsPerPage": max(limit, 3)}
    if days:
        edge = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        params["numericFilters"] = "created_at_i>%d" % edge
    data = get_json("https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(params))
    out = []
    for hit in (data.get("hits") or [])[:limit]:
        story = "https://news.ycombinator.com/item?id=%s" % hit.get("objectID")
        out.append({"src": "hn", "engine": "algolia",
                    "title": clean(hit.get("title") or ""),
                    "url": hit.get("url") or story,
                    "text": "обсуждение: %s очков, %s комментариев. %s" % (
                        hit.get("points"), hit.get("num_comments"),
                        clean(hit.get("story_text") or "")),
                    "date": (hit.get("created_at") or "")[:10]})
    return out


def search_reddit(query, limit, days=0):
    window = "year"
    if days and days <= 1:
        window = "day"
    elif days and days <= 7:
        window = "week"
    elif days and days <= 31:
        window = "month"
    url = "https://www.reddit.com/search.json?" + urllib.parse.urlencode({
        "q": query, "limit": max(limit, 3), "sort": "relevance", "t": window, "raw_json": 1})
    data = get_json(url)
    out = []
    for child in (data.get("data", {}).get("children") or [])[:limit]:
        post = child.get("data", {})
        when = ""
        if post.get("created_utc"):
            when = datetime.fromtimestamp(int(post["created_utc"]),
                                          timezone.utc).strftime("%Y-%m-%d")
        out.append({"src": "reddit", "engine": "json",
                    "title": clean(post.get("title") or ""),
                    "url": "https://www.reddit.com" + (post.get("permalink") or ""),
                    "text": "r/%s, %s очков, %s комментариев. %s" % (
                        post.get("subreddit"), post.get("score"),
                        post.get("num_comments"), clean(post.get("selftext") or "")),
                    "date": when})
    return out


PKG_RE = re.compile(r"\b(?:pip install|npm i|npm install|yarn add|package|пакет)\s+([A-Za-z][\w.-]{1,40})")


def pkg_names(query):
    """Имена пакетов из запроса. Без них в pypi и npm идти незачем."""
    found = PKG_RE.findall(query or "")
    if found:
        return found[:2]
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9._-]{2,}", query or "")
             if w.lower() not in ("error", "python", "node", "install", "github",
                                  "issue", "docs", "fix", "solution", "how", "the",
                                  "free", "tier", "limits", "pricing", "stackoverflow")]
    return words[:2]


def search_pkg(query, limit, days=0):
    """PyPI и npm: версия, дата выпуска и лицензия из первоисточника."""
    out, errors = [], []
    for name in pkg_names(query):
        try:
            data = get_json("https://pypi.org/pypi/%s/json" % urllib.parse.quote(name))
            info = data.get("info") or {}
            ver = info.get("version") or "?"
            when = ""
            for row in (data.get("releases", {}).get(ver) or []):
                when = (row.get("upload_time") or "")[:10]
                break
            out.append({"src": "pkg", "engine": "pypi", "title": "pypi %s %s" % (name, ver),
                        "url": "https://pypi.org/project/%s/" % name,
                        "text": "%s. лицензия %s, требует python %s" % (
                            clean(info.get("summary") or "описания нет"),
                            info.get("license") or "не указана",
                            info.get("requires_python") or "любой"),
                        "date": when})
        except Exception as exc:  # noqa: BLE001
            errors.append("pypi %s: %s" % (name, str(exc)[:30]))
        try:
            data = get_json("https://registry.npmjs.org/%s" % urllib.parse.quote(name, safe="@/"))
            tags = data.get("dist-tags") or {}
            ver = tags.get("latest") or "?"
            when = (data.get("time", {}) or {}).get(ver, "")[:10]
            out.append({"src": "pkg", "engine": "npm", "title": "npm %s %s" % (name, ver),
                        "url": "https://www.npmjs.com/package/%s" % name,
                        "text": "%s. лицензия %s" % (
                            clean(data.get("description") or "описания нет"),
                            data.get("license") or "не указана"),
                        "date": when})
        except Exception as exc:  # noqa: BLE001
            errors.append("npm %s: %s" % (name, str(exc)[:30]))
        if len(out) >= limit:
            break
    if not out and errors:
        raise IOError("реестры пакетов не ответили: " + "; ".join(errors[:2]))
    return out[:limit]


ENGINE_MAP = {
    "web": search_web, "wiki": search_wiki, "github": search_github,
    "issues": search_issues, "stack": search_stack, "hn": search_hn,
    "reddit": search_reddit, "pkg": search_pkg,
}


# ------------------------------------------------------------------ ранжирование

def trust_of(url):
    host = host_of(url)
    if not host:
        return 0
    for domain, weight in TRUST.items():
        if host == domain or host.endswith("." + domain):
            return weight
    if host.endswith(".gov") or host.endswith(".edu"):
        return 7
    if "docs." in host or host.startswith("developer.") or "/docs" in url:
        return 6
    if any(bad in host for bad in JUNK):
        return 0
    return 4


def fresh_of(date_text):
    """Свежесть в баллах. Цена и лимит годовой давности врут каналу."""
    if not date_text:
        return 0
    try:
        when = datetime.strptime(date_text[:10], "%Y-%m-%d")
    except ValueError:
        return 0
    days = (datetime.now() - when).days
    if days < 0:
        return 0
    if days <= 30:
        return 6
    if days <= 120:
        return 4
    if days <= 365:
        return 2
    if days <= 900:
        return 1
    return -2


SRC_WEIGHT = {"web": 2, "wiki": 2, "github": 3, "issues": 3, "stack": 3,
              "hn": 1, "reddit": 0, "pkg": 4}


def score_row(row, topic):
    """Одна цифра на строку: доверие плюс совпадение слов плюс свежесть."""
    terms = set(words_of(topic))
    haystack = set(words_of(row.get("title", "") + " " + row.get("text", "")))
    hit = len(terms & haystack)
    cover = (hit / float(len(terms))) if terms else 0
    score = trust_of(row.get("url", "")) + SRC_WEIGHT.get(row.get("src"), 1)
    score += 6 * cover
    score += fresh_of(row.get("date", ""))
    body = (row.get("title", "") + " " + row.get("text", "")).lower()
    if any(word in body for word in ("цен", "price", "лимит", "limit", "free", "бесплатн")):
        score += 1
    if re.search(r"\d", body):
        score += 1
    if len(row.get("text", "")) < 30:
        score -= 2
    return round(score, 3)


def dedup(rows):
    """Один URL один раз, один домен не больше двух раз: иначе выдача из одного блога."""
    seen, per_host, out = set(), {}, []
    for row in rows:
        url = (row.get("url") or "").split("#")[0].rstrip("/")
        if not url:
            continue
        key = re.sub(r"[?&](utm_[^&]+|ref|fbclid)=[^&]*", "", url)
        if key in seen:
            continue
        host = host_of(url)
        if per_host.get(host, 0) >= 2 and row.get("src") == "web":
            continue
        seen.add(key)
        per_host[host] = per_host.get(host, 0) + 1
        row["url"] = url
        out.append(row)
    return out


# ---------------------------------------------------------------------- кэш

def cache_dir():
    base = os.environ.get("CHANNEL_CACHE")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".cache", "channel-skill")
    path = os.path.join(base, "search")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return ""
    return path


def cache_key(topic, profile, sources, days, limit):
    raw = "|".join([topic or "", profile, ",".join(sources), str(days), str(limit), VERSION])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def cache_load(key, ttl=CACHE_TTL):
    folder = cache_dir()
    if not folder:
        return None
    path = os.path.join(folder, key + ".json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > ttl:
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def cache_save(key, payload):
    folder = cache_dir()
    if not folder:
        return
    try:
        with open(os.path.join(folder, key + ".json"), "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
    except OSError:
        pass


# --------------------------------------------------------------------- факты

NUM = re.compile(r"\d")
FACT_KILL = ("cookie", "куки", "подпишись", "все права", "all rights", "©",
              "реклам", "политика конфиден", "privacy policy", "terms of service",
              "sign in", "log in", "войти", "регистрация на сайте", "javascript")
UNITS = ("$", "€", "₽", "руб", "долл", "%", "гб", "мб", "gb", "mb", "tb", "кб",
         "токен", "token", "запрос", "request", "кредит", "credit", "минут",
         "час", "день", "дней", "месяц", "day", "month", "раз в", "per ", "/мес",
         "версия", "version", "v1", "v2", "звёзд", "star", "голосов", "коммент")
DEADLINE = ("до ", "дедлайн", "законч", "истек", "until", "deadline", "expires",
            "ends ", "акция до", "по графику")


def fact_kind(text):
    low = text.lower()
    if any(word in low for word in DEADLINE):
        return "срок"
    if any(word in low for word in ("$", "₽", "руб", "price", "цен", "тариф", "платн")):
        return "цена"
    if any(word in low for word in ("лимит", "limit", "запрос", "request", "квот", "quota", "кредит")):
        return "лимит"
    if re.search(r"\bv?\d+\.\d+", low) or "верси" in low or "version" in low:
        return "версия"
    return "цифра"


def facts_from(rows, cap=10):
    """Цифры и сроки с привязкой к источнику.

    Главное отличие от старого research.py: факт всегда знает свой номер
    источника. Без этого модель ставит цифру в пост без ссылки, а потом
    автор не может проверить, откуда она взялась.
    """
    out, seen = [], set()
    for idx, row in enumerate(rows, 1):
        blob = (row.get("text") or "") + " " + (row.get("title") or "")
        for piece in re.split(r"(?<=[.!?;])\s+|\n+|\s\|\s", blob):
            piece = clean(piece)
            if not (25 <= len(piece) <= 220) or not NUM.search(piece):
                continue
            low = piece.lower()
            if any(bad in low for bad in FACT_KILL):
                continue
            if not any(unit in low for unit in UNITS) and not any(w in low for w in DEADLINE):
                continue
            if re.fullmatch(r"[\d\s.,:/-]+", piece):
                continue
            key = re.sub(r"\W+", "", low)[:60]
            if key in seen:
                continue
            seen.add(key)
            out.append({"kind": fact_kind(piece), "text": piece, "src": idx,
                        "url": row.get("url", ""), "date": row.get("date", "")})
            if len(out) >= cap:
                return out
    return out


def gaps_of(facts, topic, profile):
    """Чего не хватает для поста. Лучше одна строка вопроса, чем выдуманная цифра."""
    kinds = set(f["kind"] for f in facts)
    need = []
    if profile == "code":
        if "версия" not in kinds:
            need.append("версия библиотеки или рунтайма")
        if not any(row for row in facts if "шаг" in row["text"].lower()):
            need.append("рабочий обход шагами")
    else:
        if "цена" not in kinds:
            need.append("цена или что именно бесплатно")
        if "лимит" not in kinds:
            need.append("лимиты бесплатного тарифа")
        if "срок" not in kinds and looks_like_price(topic):
            need.append("срок акции, без срока пункт не публикуем")
    need.append("личная деталь автора: с какого раза завелось")
    return need


# --------------------------------------------------------------------- поиск

def run_search(topic, profile="", sources=(), days=0, limit=DEFAULT_LIMIT,
               queries=None, use_cache=True, workers=WORKERS):
    """Главная дверь. Возвращает готовую картинку, а не сырую выдачу."""
    profile = pick_profile(topic, profile)
    picked = tuple(sources) if sources else PROFILES[profile]
    picked = tuple(s for s in picked if s in ENGINE_MAP) or ("web",)
    plan = list(queries) if queries else plan_queries(topic, profile)
    key = cache_key(topic, profile, picked, days, limit)
    if use_cache:
        hit = cache_load(key)
        if hit:
            hit["cached"] = True
            return hit

    jobs = []
    for source in picked:
        # Веб гоняем по всем запросам плана, узкие API только по главным двум.
        take = plan if source == "web" else plan[:2]
        for query in take:
            jobs.append((source, query))

    rows, dead = [], []

    def work(job):
        source, query = job
        try:
            return source, query, ENGINE_MAP[source](query, limit, days), ""
        except Exception as exc:  # noqa: BLE001
            return source, query, [], str(exc)[:120]

    if workers > 1 and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
            done = list(pool.map(work, jobs))
    else:
        done = [work(job) for job in jobs]

    for source, query, got, err in done:
        if err:
            dead.append({"source": source, "query": query, "error": err})
        for row in got:
            row["query"] = query
            rows.append(row)

    rows = dedup(rows)
    for row in rows:
        row["score"] = score_row(row, topic)
    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:limit]
    payload = {"topic": topic, "profile": profile, "sources": list(picked),
               "queries": plan, "results": rows, "facts": facts_from(rows),
               "failed": dead, "cached": False, "version": VERSION,
               "asked": datetime.now().strftime("%Y-%m-%d %H:%M")}
    if use_cache and rows:
        cache_save(key, payload)
    return payload


def read_page(url, budget=4000):
    """Страница текстом. Сначала напрямую, в запасе читалка и архив."""
    ways = (url,
            "https://r.jina.ai/" + url,
            "http://archive.org/wayback/available?url=" + urllib.parse.quote(url))
    for step, way in enumerate(ways):
        try:
            raw = get(way, timeout=READ_TIMEOUT)
        except Exception:  # noqa: BLE001
            continue
        if step == 2:
            try:
                snap = json.loads(raw).get("archived_snapshots", {}).get("closest", {})
            except ValueError:
                continue
            if not snap.get("url"):
                continue
            try:
                raw = get(snap["url"], timeout=READ_TIMEOUT)
            except Exception:  # noqa: BLE001
                continue
        text = strip_tags(raw) if "<" in raw[:400] else raw
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) > 200:
            return {"url": url, "chars": len(text), "text": text[:budget],
                    "cut": len(text) > budget}
    return {"url": url, "chars": 0, "text": "", "cut": False}


# --------------------------------------------------------------------- вывод

def render(payload, budget=DEFAULT_BUDGET):
    rows = payload.get("results") or []
    if not rows:
        return NO_NET
    out = ["ПОИСК: %s" % payload.get("topic", ""),
           "Профиль %s, источники: %s" % (payload.get("profile"),
                                              ", ".join(payload.get("sources") or [])),
           ""]
    per = max(160, int(budget / max(len(rows), 1)))
    for idx, row in enumerate(rows, 1):
        head = "[%d] %s" % (idx, row.get("title") or row.get("url"))
        if row.get("date"):
            head += " (%s)" % row["date"]
        out.append(head)
        out.append("    %s" % row.get("url"))
        if row.get("text"):
            out.append("    %s" % trim(row["text"], per))
    facts = payload.get("facts") or []
    if facts:
        out.append("")
        out.append("ЦИФРЫ И СРОКИ (в квадратных скобках номер источника):")
        for fact in facts:
            out.append("  %s: %s [%d]" % (fact["kind"], trim(fact["text"], 180), fact["src"]))
    if payload.get("failed"):
        out.append("")
        out.append("Не ответили: %s" % ", ".join(
            sorted(set(row["source"] for row in payload["failed"]))))
    return "\n".join(out)


def render_brief(payload):
    """Факт-пак для поста. Форма жёсткая, чтобы слабая модель не думала."""
    rows = payload.get("results") or []
    topic = payload.get("topic", "")
    profile = payload.get("profile", "post")
    if not rows:
        return "\n".join(["БРИФ: %s" % topic, NO_NET,
                          "Спроси у автора сырьё одной строкой и пиши по нему."])
    facts = payload.get("facts") or []
    out = ["БРИФ: %s" % topic,
           "Собрано %s, профиль %s, источников %d"
           % (payload.get("asked", ""), profile, len(rows)), ""]
    out.append("ФАКТЫ (берём только отсюда, цифра в скобках это источник):")
    if facts:
        for num, fact in enumerate(facts, 1):
            out.append("%d. %s [%d]" % (num, trim(fact["text"], 170), fact["src"]))
    else:
        out.append("Цифр не нашлось. Пишем без цифр или спрашиваем автора.")
    out.append("")
    out.append("ИСТОЧНИКИ (ссылки только отсюда, свои не выдумываем):")
    for idx, row in enumerate(rows, 1):
        out.append("[%d] %s%s" % (idx, trim(row.get("title") or row.get("url"), 90),
                                  " (%s)" % row["date"] if row.get("date") else ""))
        out.append("    %s" % row.get("url"))
    out.append("")
    out.append("ЧЕГО НЕ ХВАТАЕТ (спроси одной строкой, не выдумывай):")
    for gap in gaps_of(facts, topic, profile):
        out.append("  нет: %s" % gap)
    out.append("")
    if profile == "code":
        out.append("ДАЛЬШЕ: чини код по источникам выше. Сначала дока и issue, потом блоги.")
        out.append("Глубже в страницу: python3 tools/search.py --read ссылка")
    else:
        out.append("ДАЛЬШЕ: пиши пост по этому брифу.")
        out.append('Одной командой: python3 tools/channel.py post "%s"' % topic)
    return "\n".join(out)


# --------------------------------------------------------------------- доктор

def doctor():
    print("search.py %s, доктор поиска" % VERSION)
    print("")
    rows = []
    for name in WEB_ENGINES:
        try:
            raw = _web_engine(name, "telegram bot api", 0)
            rows.append((name, bool(_anchors(raw)), "%d байт" % len(raw)))
        except Exception as exc:  # noqa: BLE001
            rows.append((name, False, str(exc)[:60]))
    for source in ("wiki", "github", "issues", "stack", "hn", "reddit"):
        try:
            got = ENGINE_MAP[source]("telegram", 2, 0)
            rows.append((source, bool(got), "%d строк" % len(got)))
        except Exception as exc:  # noqa: BLE001
            rows.append((source, False, str(exc)[:60]))
    width = max(len(name) for name, _, _ in rows)
    alive = 0
    for name, ok, detail in rows:
        alive += 1 if ok else 0
        print("  %-*s  %s  %s" % (width, name, "ок " if ok else "нет", detail))
    print("")
    folder = cache_dir()
    print("Кэш: %s" % (folder or "нет доступа к папке, работаем без кэша"))
    if not alive:
        print("Сети нет совсем. Посты пишем по сырью автора, цифры не выдумываем.")
        return 2
    print("Живых источников: %d из %d. Для работы достаточно одного." % (alive, len(rows)))
    return 0


# -------------------------------------------------------------------- тесты

FAKE_DDG = """<html><body>
<a class="result-link" href="https://example.com/pricing">Cursor pricing and free tier</a>
<td class="result-snippet">Free plan gives 200 requests per month, Pro costs $20 per month until 31.12.2026.</td>
<a class="result-link" href="https://example.com/pricing?utm_source=x">Cursor pricing and free tier copy</a>
<td class="result-snippet">Duplicate of the same page with tracking tail.</td>
<a class="result-link" href="https://blog.example.org/review">Cursor review after three months</a>
<td class="result-snippet">I burned 40 hours, agent mode ate 500 credits in one day.</td>
<a class="result-link" href="https://docs.example.net/limits">Rate limits reference page</a>
<td class="result-snippet">Hard cap is 50 requests per minute on the free plan.</td>
<a class="result-link" href="https://duckduckgo.com/?q=skip">this engine link must be skipped</a>
<a class="result-link" href="https://pinterest.com/junk-page">junk aggregator page here</a>
</body></html>"""

FAKE_GH = json.dumps({"items": [
    {"full_name": "acme/tool", "html_url": "https://github.com/acme/tool",
     "description": "Toolkit for tests", "stargazers_count": 1200, "language": "Python",
     "license": {"spdx_id": "MIT"}, "pushed_at": "2026-08-01T10:00:00Z"}]})
FAKE_ISSUES = json.dumps({"items": [
    {"title": "FloodWaitError on login", "html_url": "https://github.com/acme/tool/issues/7",
     "state": "open", "comments": 5, "body": "Workaround: wait 30 seconds and retry once.",
     "updated_at": "2026-08-20T10:00:00Z"}]})
FAKE_STACK = json.dumps({"items": [
    {"title": "How to fix FloodWaitError", "link": "https://stackoverflow.com/q/1",
     "is_answered": True, "score": 42, "answer_count": 3, "tags": ["python", "telethon"],
     "last_activity_date": 1780000000}]})
FAKE_HN = json.dumps({"hits": [
    {"objectID": "1", "title": "Show HN: tool", "url": "https://news.ycombinator.com/item?id=1",
     "points": 100, "num_comments": 20, "story_text": "", "created_at": "2026-08-10T00:00:00Z"}]})
FAKE_WIKI = json.dumps({"query": {"search": [
    {"title": "Telegram", "snippet": "messenger with 900 million users",
     "timestamp": "2026-07-01T00:00:00Z"}]}})
FAKE_PYPI = json.dumps({"info": {"version": "1.36.0", "summary": "Telegram client",
                                 "license": "MIT", "requires_python": ">=3.7"},
                        "releases": {"1.36.0": [{"upload_time": "2026-05-05T00:00:00"}]}})


def fake_fetch(url, data=None, headers=None, timeout=TIMEOUT):
    """Сеть из коробки: тесты не имеют права зависеть от интернета."""
    low = url.lower()
    if "duckduckgo" in low or "mojeek" in low or "searx" in low or "marginalia" in low:
        return FAKE_DDG
    if "api.github.com/search/repositories" in low:
        return FAKE_GH
    if "api.github.com/search/issues" in low:
        return FAKE_ISSUES
    if "stackexchange" in low:
        return FAKE_STACK
    if "algolia" in low:
        return FAKE_HN
    if "wikipedia.org/w/api.php" in low:
        return FAKE_WIKI
    if "pypi.org" in low:
        return FAKE_PYPI
    if "registry.npmjs" in low:
        raise IOError("404")
    if "reddit.com" in low:
        raise IOError("429 too many requests")
    if low.startswith("https://example.com/page"):
        return "<html><body><p>" + ("тело страницы " * 40) + "</p></body></html>"
    raise IOError("нет такого адреса в тесте: %s" % url)


def selftest():
    global FETCH
    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))

    # План запросов
    plan = plan_queries("Cursor бесплатный тариф", "post")
    ok("план из нескольких запросов", len(plan) >= 3)
    ok("первым идёт запрос автора", plan[0] == "Cursor бесплатный тариф")
    ok("в плане есть лимиты", any("limit" in q for q in plan))
    ok("в плане есть год", any(str(year_now()) in q for q in plan))
    ok("латинское имя вытащилось", latin_core("абуз Cursor 2.0 как забрать") == "Cursor 2.0")
    ok("без темы план пуст", plan_queries("", "post") == [])
    ok("дублей в плане нет", len(set(q.lower() for q in plan)) == len(plan))
    code_plan = plan_queries("telethon FloodWaitError ошибка", "code")
    ok("кодовый план идёт в issue", any("issue" in q for q in code_plan))
    ok("кодовый план идёт в стек", any("stackoverflow" in q for q in code_plan))

    # Автовыбор профиля
    ok("ошибка это код", pick_profile("почему падает ошибка в telethon") == "code")
    ok("халява это пост", pick_profile("бесплатные кредиты в новом сервисе") == "post")
    ok("ручной профиль сильнее", pick_profile("ошибка", "news") == "news")
    ok("кривой профиль падает в post", pick_profile("тема", "чушь") == "post")

    # Разбор выдачи
    pairs = _anchors(FAKE_DDG)
    urls = [u for u, _ in pairs]
    ok("ссылки разобрались", len(pairs) >= 3)
    ok("сам движок выкинут", not any("duckduckgo" in u for u in urls))
    ok("мусорный домен выкинут", not any("pinterest" in u for u in urls))
    ok("сниппеты разобрались", len(_snippets(FAKE_DDG)) >= 2)
    ok("uddg раскрывается",
       _unwrap("/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=1") == "https://example.com/a")

    # Дедуп и ранжирование
    same = dedup([{"url": "https://a.com/x", "src": "web"},
                  {"url": "https://a.com/x/", "src": "web"},
                  {"url": "https://a.com/x#frag", "src": "web"}])
    ok("один адрес одна строка", len(same) == 1)
    many = dedup([{"url": "https://b.com/%d" % i, "src": "web"} for i in range(5)])
    ok("домен не больше двух раз", len(many) == 2)
    ok("дока выше блога",
       trust_of("https://docs.python.org/3/library/re.html") > trust_of("https://medium.com/p/1"))
    ok("мусорный домен без доверия", trust_of("https://pinterest.com/x") == 0)
    ok("свежее выше старого",
       fresh_of(datetime.now().strftime("%Y-%m-%d")) > fresh_of("2019-01-01"))
    ok("кривая дата не ломает", fresh_of("не дата") == 0)
    high = score_row({"src": "github", "url": "https://github.com/a/b",
                      "title": "cursor limits", "text": "free plan 200 requests per month",
                      "date": datetime.now().strftime("%Y-%m-%d")}, "cursor limits")
    low = score_row({"src": "reddit", "url": "https://medium.com/p/1",
                     "title": "nothing", "text": "", "date": "2018-01-01"}, "cursor limits")
    ok("ранжирование ставит дело выше шума", high > low)

    # Факты
    facts = facts_from([{"title": "Pricing", "url": "https://example.com/pricing",
                        "text": "Free plan gives 200 requests per month. "
                                "Pro costs $20 per month until 31.12.2026. "
                                "Мы используем cookie и 2026 года все права защищены.",
                        "date": "2026-08-01"}])
    texts = " ".join(f["text"] for f in facts)
    ok("цифра поймалась", "200 requests" in texts)
    ok("факт знает источник", all(f["src"] == 1 and f["url"] for f in facts))
    ok("cookie в факты не полезла", "cookie" not in texts.lower())
    ok("виды фактов размечены", set(f["kind"] for f in facts) & {"цена", "лимит", "срок"})
    ok("пустота не ломает факты", facts_from([]) == [])
    gaps = gaps_of([], "бесплатные кредиты", "post")
    ok("без цифр просит цену и срок", len(gaps) >= 3)
    ok("в дырах есть личная деталь", any("личная" in g for g in gaps))

    # Чистка текста
    ok("длинное тире вырезано", "\u2014" not in clean("а \u2014 б"))
    ok("теги вырезаны", clean("<b>жир</b>") == "жир")
    ok("обрезка не рвёт слово", len(trim("а" * 100 + " ббб", 50)) <= 54)
    ok("хост без www", host_of("https://www.example.com/a") == "example.com")

    # Конвейер целиком без сети
    saved = FETCH
    FETCH = fake_fetch
    try:
        payload = run_search("Cursor free tier limits", profile="post",
                             limit=6, use_cache=False, workers=1)
        rows = payload["results"]
        ok("конвейер вернул строки", len(rows) >= 3)
        ok("все строки с адресом", all(r.get("url", "").startswith("http") for r in rows))
        ok("оценка у каждой строки", all("score" in r for r in rows))
        ok("порядок по оценке",
           all(rows[i]["score"] >= rows[i + 1]["score"] for i in range(len(rows) - 1)))
        ok("дубль с utm выкинут", len(set(r["url"] for r in rows)) == len(rows))
        ok("факты собрались", len(payload["facts"]) >= 1)
        ok("падение источника не роняет всё", isinstance(payload["failed"], list))
        brief = render_brief(payload)
        ok("в брифе есть факты", "ФАКТЫ" in brief)
        ok("в брифе есть источники", "ИСТОЧНИКИ" in brief)
        ok("в брифе есть дыры", "ЧЕГО НЕ ХВАТАЕТ" in brief)
        ok("в брифе нет длинных тире", not any(d in brief for d in ("\u2014", "\u2013")))
        ok("бриф короткий", len(brief) <= BRIEF_BUDGET + 1200)
        plain = render(payload, budget=900)
        ok("обычный вывод с номерами", "[1]" in plain)

        code = run_search("telethon FloodWaitError ошибка", profile="code",
                          limit=8, use_cache=False, workers=1)
        got = set(r["src"] for r in code["results"])
        ok("кодовый профиль идёт в стек", "stack" in got)
        ok("кодовый профиль идёт в issue", "issues" in got)
        ok("кодовый профиль видит пакеты", "pkg" in got)
        ok("мёртвый npm ушёл в список падений или пропущен",
           all(r["engine"] != "npm" for r in code["results"] if r["src"] == "pkg"))
        ok("ответ стека виден как принятый",
           any("принят" in r["text"] for r in code["results"] if r["src"] == "stack"))

        page = read_page("https://example.com/page", budget=200)
        ok("страница читается", page["chars"] > 200 and page["cut"])
        ok("битый адрес не падает", read_page("https://nope.invalid/x")["chars"] == 0)

        empty = run_search("тема которой нет", profile="post", sources=("reddit",),
                           limit=3, use_cache=False, workers=1)
        ok("пустая выдача говорит честно", render(empty) == NO_NET)
        ok("пустой бриф тоже честный", NO_NET in render_brief(empty))

        # Кэш: второй забег не должен лезть в сеть
        import tempfile
        box = tempfile.mkdtemp(prefix="channel-search-")
        old_cache = os.environ.get("CHANNEL_CACHE")
        os.environ["CHANNEL_CACHE"] = box
        try:
            first = run_search("cache probe limits", profile="post", sources=("web",),
                               limit=3, use_cache=True, workers=1)
            FETCH = lambda *a, **k: (_ for _ in ()).throw(IOError("сети нет"))  # noqa: E731
            second = run_search("cache probe limits", profile="post", sources=("web",),
                                limit=3, use_cache=True, workers=1)
            ok("кэш спасает без сети",
               second.get("cached") and len(second["results"]) == len(first["results"]))
        finally:
            FETCH = fake_fetch
            if old_cache is None:
                os.environ.pop("CHANNEL_CACHE", None)
            else:
                os.environ["CHANNEL_CACHE"] = old_cache
            import shutil
            shutil.rmtree(box, ignore_errors=True)

        FETCH = lambda *a, **k: (_ for _ in ()).throw(IOError("сети нет"))  # noqa: E731
        dark = run_search("сети нет совсем", profile="post", limit=3,
                          use_cache=False, workers=1)
        ok("без сети не падаем", dark["results"] == [] and dark["failed"])
    finally:
        FETCH = saved

    bad = [name for name, good in checks if not good]
    for name, good in checks:
        print("  %s %s" % ("ок " if good else "НЕТ", name))
    print("")
    print("search.py: проверок %d, провалов %d" % (len(checks), len(bad)))
    return 1 if bad else 0


# ----------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True,
                                 description="Глубокий поиск для постов и для кода")
    ap.add_argument("query", nargs="*", help="тема словами автора")
    ap.add_argument("--profile", default="", choices=[""] + sorted(PROFILES),
                    help="post, code, news, deep. По умолчанию выбирается сам")
    ap.add_argument("--source", default="", help="свой список: " + ",".join(ALL_SOURCES))
    ap.add_argument("--days", type=int, default=0, help="только свежее за N дней")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="сколько строк оставить")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="бюджет знаков вывода")
    ap.add_argument("--brief", action="store_true", help="факт-пак под пост")
    ap.add_argument("--json", action="store_true", help="сырой json для скриптов")
    ap.add_argument("--plan", action="store_true", help="только показать план запросов")
    ap.add_argument("--read", default="", help="прочитать страницу текстом")
    ap.add_argument("--no-cache", action="store_true", help="не брать и не писать кэш")
    ap.add_argument("--doctor", action="store_true", help="какие источники живы")
    ap.add_argument("--selftest", action="store_true", help="тесты без сети")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args(argv)

    if args.version:
        print("search.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()
    if args.doctor:
        return doctor()
    if args.read:
        page = read_page(args.read, budget=max(args.budget, 1200))
        if args.json:
            print(json.dumps(page, ensure_ascii=False, indent=2))
            return 0 if page["chars"] else 2
        if not page["chars"]:
            print("Страница не отдалась: %s" % args.read)
            return 2
        print("СТРАНИЦА: %s" % page["url"])
        print("Знаков всего %d%s" % (page["chars"], ", показано начало" if page["cut"] else ""))
        print("")
        print(page["text"])
        return 0

    topic = " ".join(args.query).strip()
    if not topic:
        ap.print_help()
        return 2

    if args.plan:
        profile = pick_profile(topic, args.profile)
        print("Профиль: %s" % profile)
        print("Источники: %s" % ", ".join(PROFILES[profile]))
        print("Запросы:")
        for num, query in enumerate(plan_queries(topic, profile), 1):
            print("  %d. %s" % (num, query))
        return 0

    sources = tuple(s.strip() for s in args.source.split(",") if s.strip())
    payload = run_search(topic, profile=args.profile, sources=sources, days=args.days,
                         limit=max(1, args.limit), use_cache=not args.no_cache)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["results"] else 2
    print(render_brief(payload) if args.brief else render(payload, budget=args.budget))
    return 0 if payload["results"] else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
