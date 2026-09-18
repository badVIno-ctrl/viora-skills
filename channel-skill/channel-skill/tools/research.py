#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
research.py 1.0.0
Поиск фактов в интернете для постов автора.
Только стандартная библиотека Python 3.8+. Ключи не нужны, установка не нужна.
Вывод сжат до бюджета знаков, чтобы не забивать контекст слабой модели.
"""

import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser

VERSION = "6.2.1"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 12
DEFAULT_BUDGET = 1800
DEFAULT_LIMIT = 6
DEEP_LIMIT = 10
DEFAULT_SOURCES = ["web", "github", "hn"]
DEEP_SOURCES = ["web", "github", "hn", "reddit"]
ALL_SOURCES = ["web", "github", "hn", "reddit"]

NO_NET = ("RESEARCH: сети нет или поиск недоступен. "
          "Пиши пост по сырью автора, цифры не выдумывай.")

_UNVERIFIED = ssl.create_default_context()
_UNVERIFIED.check_hostname = False
_UNVERIFIED.verify_mode = ssl.CERT_NONE


# ---------------------------------------------------------------- сеть

def fetch(url, data=None, headers=None, timeout=TIMEOUT):
    hdr = {"User-Agent": UA, "Accept-Language": "ru,en;q=0.9",
           "Accept": "text/html,application/json,*/*"}
    if headers:
        hdr.update(headers)
    body = urllib.parse.urlencode(data).encode("utf-8") if data else None
    last = None
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
    raise last


def fetch_json(url, headers=None):
    return json.loads(fetch(url, headers=headers))


# ---------------------------------------------------------------- текст

class _Strip(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer"}
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
        text = "".join(self.buf)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def strip_tags(raw):
    parser = _Strip()
    try:
        parser.feed(raw)
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", raw)
    return parser.result()


def clean(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
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


# ---------------------------------------------------------------- факты

FACT_PATTERNS = [
    r"\$\s?\d[\d\s.,]*",
    r"\d[\d\s.,]*\s?(?:USD|EUR|GBP|руб|₽|€)",
    r"\d+(?:[.,]\d+)?\s?(?:%|процент\w*)",
    r"\d+(?:[.,]\d+)?\s?(?:GB|TB|MB|ГБ|МБ|ТБ|Гб|Мб)",
    r"\d[\d\s,]*\s?(?:requests?|запрос\w*|credits?|кредит\w*|tokens?|токен\w*|"
    r"messages?|сообщен\w*|minutes?|минут\w*|hours?|час\w*|days?|дней|дня|"
    r"months?|месяц\w*|seats?|users?|пользовател\w*)",
    r"(?:free tier|free plan|бесплатн\w+)[^.\n]{0,70}",
    r"\b20\d\d-(?:0\d|1[0-2])-(?:[0-2]\d|3[01])\b",
    r"\b(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|"
    r"ноябр|декабр)\w*\s+20\d\d\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{0,2},?\s?20\d\d\b",
]


def facts_from(text, limit=12):
    found, seen = [], set()
    for pattern in FACT_PATTERNS:
        for hit in re.findall(pattern, text or "", re.IGNORECASE):
            item = clean(hit)
            key = item.lower()
            if len(item) < 2 or key in seen:
                continue
            seen.add(key)
            found.append(item)
            if len(found) >= limit:
                return found
    return found


# ---------------------------------------------------------------- веб-поиск

def _unwrap(href):
    if href.startswith("//"):
        href = "https:" + href
    hit = re.search(r"[?&]uddg=([^&]+)", href)
    if hit:
        href = urllib.parse.unquote(hit.group(1))
    return href


def _anchors(raw, block_hosts):
    out = []
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                                 raw, re.IGNORECASE | re.DOTALL):
        url = _unwrap(href)
        if not url.startswith("http"):
            continue
        host = urllib.parse.urlparse(url).netloc.lower()
        if any(bad in host for bad in block_hosts):
            continue
        title = clean(label)
        if len(title) < 8 or len(url) > 300:
            continue
        out.append((url, title))
    return out


def _dedup(pairs, limit):
    out, seen = [], set()
    for url, title in pairs:
        key = urllib.parse.urlparse(url).netloc.lower() + urllib.parse.urlparse(url).path
        if key in seen:
            continue
        seen.add(key)
        out.append((url, title))
        if len(out) >= limit:
            break
    return out


def _days_param(days):
    if not days:
        return ""
    if days <= 1:
        return "d"
    if days <= 7:
        return "w"
    if days <= 31:
        return "m"
    return "y"


def search_web(query, limit, days=0):
    block = ["duckduckgo.com", "mojeek.com", "google.", "bing.com", "yandex."]
    attempts = [
        ("https://lite.duckduckgo.com/lite/", {"q": query}),
        ("https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
            {"q": query, "df": _days_param(days)}), None),
        ("https://www.mojeek.com/search?" + urllib.parse.urlencode({"q": query}), None),
    ]
    for url, post in attempts:
        try:
            raw = fetch(url, data=post)
        except Exception:  # noqa: BLE001
            continue
        if "captcha" in raw.lower() and len(raw) < 4000:
            continue
        pairs = _dedup(_anchors(raw, block), limit)
        if not pairs:
            continue
        snippets = [clean(s) for s in re.findall(
            r'class="(?:result-snippet|result__snippet|s)"[^>]*>(.*?)</',
            raw, re.IGNORECASE | re.DOTALL)]
        results = []
        for idx, (link, title) in enumerate(pairs):
            body = snippets[idx] if idx < len(snippets) else ""
            results.append({"src": "web", "title": title, "url": link, "text": body})
        return results
    return []


# ---------------------------------------------------------------- github

def search_github(query, limit, days=0):
    q = query
    if days:
        since = (datetime.utcnow() - timedelta(days=max(days, 30))).strftime("%Y-%m-%d")
        q = "%s pushed:>=%s" % (query, since)
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({
        "q": q, "sort": "stars", "order": "desc", "per_page": max(limit, 3)})
    try:
        data = fetch_json(url, headers={"Accept": "application/vnd.github+json"})
    except Exception:  # noqa: BLE001
        return []
    out = []
    for item in (data.get("items") or [])[:limit]:
        lic = (item.get("license") or {}).get("spdx_id") or "лицензии нет"
        pushed = (item.get("pushed_at") or "")[:10]
        text = "%s. звёзд %s, последний коммит %s, %s, язык %s" % (
            clean(item.get("description") or "описания нет"),
            item.get("stargazers_count"), pushed, lic, item.get("language") or "?")
        out.append({"src": "github", "title": item.get("full_name"),
                    "url": item.get("html_url"), "text": text})
    return out


# ---------------------------------------------------------------- hacker news

def search_hn(query, limit, days=0, deep=False):
    params = {"query": query, "tags": "story", "hitsPerPage": max(limit, 3)}
    if days:
        edge = int((datetime.utcnow() - timedelta(days=days)).timestamp())
        params["numericFilters"] = "created_at_i>%d" % edge
    try:
        data = fetch_json("https://hn.algolia.com/api/v1/search?" +
                          urllib.parse.urlencode(params))
    except Exception:  # noqa: BLE001
        return []
    out = []
    for hit in (data.get("hits") or [])[:limit]:
        story = "https://news.ycombinator.com/item?id=%s" % hit.get("objectID")
        text = "обсуждение: %s очков, %s комментариев, %s. %s" % (
            hit.get("points"), hit.get("num_comments"),
            (hit.get("created_at") or "")[:10], clean(hit.get("story_text") or ""))
        out.append({"src": "hn", "title": clean(hit.get("title") or ""),
                    "url": hit.get("url") or story, "text": text})
    if deep and out:
        try:
            data = fetch_json("https://hn.algolia.com/api/v1/search?" +
                              urllib.parse.urlencode({"query": query, "tags": "comment",
                                                      "hitsPerPage": 3}))
            for hit in (data.get("hits") or [])[:3]:
                body = clean(hit.get("comment_text") or "")
                if len(body) < 60:
                    continue
                out.append({"src": "hn-mnenie", "title": "мнение в обсуждении",
                            "url": "https://news.ycombinator.com/item?id=%s" % hit.get("objectID"),
                            "text": body})
        except Exception:  # noqa: BLE001
            pass
    return out


# ---------------------------------------------------------------- reddit

def search_reddit(query, limit, days=0):
    window = "year"
    if days and days <= 1:
        window = "day"
    elif days and days <= 7:
        window = "week"
    elif days and days <= 31:
        window = "month"
    url = "https://www.reddit.com/search.json?" + urllib.parse.urlencode({
        "q": query, "limit": max(limit, 3), "sort": "relevance", "t": window,
        "raw_json": 1})
    try:
        data = fetch_json(url)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for child in (data.get("data", {}).get("children") or [])[:limit]:
        post = child.get("data", {})
        text = "r/%s, %s очков, %s комментариев. %s" % (
            post.get("subreddit"), post.get("score"), post.get("num_comments"),
            clean(post.get("selftext") or ""))
        out.append({"src": "reddit", "title": clean(post.get("title") or ""),
                    "url": "https://www.reddit.com" + (post.get("permalink") or ""),
                    "text": text})
    return out


# ---------------------------------------------------------------- чтение страницы

def read_feed(raw):
    items = re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", raw, re.DOTALL | re.IGNORECASE)
    out = []
    for chunk in items[:10]:
        title = re.search(r"<title[^>]*>(.*?)</title>", chunk, re.DOTALL | re.IGNORECASE)
        link = re.search(r"<link[^>]*href=\"([^\"]+)\"", chunk, re.IGNORECASE) or \
            re.search(r"<link[^>]*>(.*?)</link>", chunk, re.DOTALL | re.IGNORECASE)
        date = re.search(r"<(?:updated|published|pubDate)[^>]*>(.*?)</", chunk,
                         re.DOTALL | re.IGNORECASE)
        out.append("%s | %s | %s" % (
            clean(title.group(1)) if title else "?",
            clean(date.group(1))[:16] if date else "?",
            clean(link.group(1)) if link else "?"))
    return "\n".join(out)


def read_page(url, budget):
    text = ""
    try:
        text = fetch("https://r.jina.ai/" + url, timeout=20)
        if text.strip().startswith("<"):
            text = strip_tags(text)
    except Exception:  # noqa: BLE001
        text = ""
    if len(text) < 200:
        try:
            raw = fetch(url, timeout=20)
        except Exception:  # noqa: BLE001
            return None
        low = raw.lstrip()[:200].lower()
        if "<rss" in low or "<feed" in low or url.rstrip("/").endswith((".xml", ".atom", ".rss")):
            text = read_feed(raw)
        else:
            text = strip_tags(raw)
    return text


# ---------------------------------------------------------------- сборка ответа

def has_cyrillic(text):
    return bool(re.search(r"[а-яё]", text, re.IGNORECASE))


def latin_only(text):
    keep = re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,}|\d+", text)
    return " ".join(keep).strip()


def collect(query, sources, limit, days, deep):
    per = max(2, limit // max(1, len(sources)))
    results = []
    for name in sources:
        if name == "web":
            results += search_web(query, per + 1, days)
        elif name == "github":
            results += search_github(query, per, days)
        elif name == "hn":
            results += search_hn(query, per, days, deep)
        elif name == "reddit":
            results += search_reddit(query, per, days)
    return results[:limit]


def render(query, results, budget, used_query=None):
    lines = []
    head = 'RESEARCH по запросу: "%s"' % (used_query or query)
    lines.append(head)
    if not results:
        return head + "\n" + NO_NET
    share = 240 if budget <= 0 else max(90, (budget - 120) // len(results) - 70)
    pool = []
    for num, item in enumerate(results, 1):
        pool.append("[%d] %s\n    src: %s | url: %s\n    %s" % (
            num, trim(item["title"], 110), item["src"], item["url"],
            trim(item["text"], share) or "описания нет"))
    lines += pool
    facts = facts_from(" ".join("%s %s" % (r["title"], r["text"]) for r in results))
    lines.append("FACTS: " + (" | ".join(facts) if facts else
                              "цифр нет, в пост цифры не тяни"))
    text = "\n".join(lines)
    if budget > 0 and len(text) > budget:
        text = text[:budget].rsplit("\n", 1)[0] + "\n[обрезано по бюджету %d]" % budget
    return text


def doctor():
    net = "нет"
    try:
        fetch("https://example.com", timeout=8)
        net = "есть"
    except Exception:  # noqa: BLE001
        pass
    web = "работает" if search_web("telegram bot api limits", 2) else "не работает"
    print("сеть: %s" % net)
    print("веб-поиск: %s" % web)
    print("yt-dlp: %s" % ("есть" if shutil.which("yt-dlp") else "нет, видео только через страницу"))
    print("ffmpeg: %s" % ("есть" if shutil.which("ffmpeg") else "нет, кадры недоступны"))
    return 0 if net == "есть" else 2


def run_video(url, budget, as_json):
    here = os.path.dirname(os.path.abspath(__file__))
    watch = os.path.join(here, "watch.py")
    if not os.path.exists(watch):
        print("RESEARCH: нет tools/watch.py, видео посмотреть нечем.")
        return 2
    cmd = [sys.executable, watch, url, "--budget", str(budget)]
    if as_json:
        cmd.append("--json")
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser(add_help=True, description="ресерч для постов автора")
    ap.add_argument("query", nargs="?", default="", help="что искать")
    ap.add_argument("--read", metavar="URL", help="прочитать конкретную страницу")
    ap.add_argument("--yt", metavar="URL", help="передать видео в tools/watch.py")
    ap.add_argument("--source", default="", help="web,github,hn,reddit через запятую")
    ap.add_argument("--days", type=int, default=0, help="только свежее за N дней")
    ap.add_argument("--limit", type=int, default=0, help="сколько источников показать")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="потолок вывода в знаках, 0 без ограничения")
    ap.add_argument("--deep", action="store_true", help="больше источников и мнений")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument("--doctor", action="store_true", help="проверить окружение")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args()

    if args.version:
        print("research.py %s" % VERSION)
        return 0
    if args.doctor:
        return doctor()
    if args.yt:
        return run_video(args.yt, args.budget, args.json)

    if args.read:
        text = read_page(args.read, args.budget)
        if not text:
            print(NO_NET)
            return 2
        body = trim(" ".join(text.split("\n")), args.budget) if args.budget > 0 else text
        if args.json:
            print(json.dumps({"url": args.read, "text": body,
                              "facts": facts_from(text)}, ensure_ascii=False))
        else:
            print("READ: %s" % args.read)
            print(body)
            got = facts_from(text)
            print("FACTS: " + (" | ".join(got) if got else "цифр нет"))
        return 0

    if not args.query.strip():
        ap.print_help()
        return 1

    sources = [s.strip() for s in args.source.split(",") if s.strip()] or \
        (DEEP_SOURCES if args.deep else DEFAULT_SOURCES)
    sources = [s for s in sources if s in ALL_SOURCES] or DEFAULT_SOURCES
    limit = args.limit or (DEEP_LIMIT if args.deep else DEFAULT_LIMIT)

    used = args.query
    results = collect(args.query, sources, limit, args.days, args.deep)
    if len(results) < 3 and has_cyrillic(args.query):
        latin = latin_only(args.query)
        if len(latin) >= 4:
            extra = collect(latin, sources, limit, args.days, args.deep)
            if len(extra) > len(results):
                results, used = extra, latin
    if args.json:
        print(json.dumps({"query": used, "sources": sources, "results": results,
                          "facts": facts_from(" ".join(
                              "%s %s" % (r["title"], r["text"]) for r in results))},
                         ensure_ascii=False))
        return 0 if results else 2
    print(render(args.query, results, args.budget, used))
    return 0 if results else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
