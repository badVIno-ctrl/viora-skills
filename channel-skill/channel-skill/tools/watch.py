#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watch.py 1.0.0
Просмотр видео с YouTube для постов автора.
По умолчанию берёт только субтитры: кадр стоит тысячи токенов, строка текста единицы.
Только стандартная библиотека Python 3.8+. Ключи не нужны.
"""

import argparse
import glob
import html as htmlmod
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

VERSION = "6.2.1"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 15
DEFAULT_BUDGET = 1500
HEAD_CHARS = 400
TAIL_CHARS = 200
MAX_FRAMES = 8
SUB_LANGS = "ru,ru-orig,ru-RU,en,en-orig,en-US"

NO_SUBS = ("WATCH: субтитров нет и достать их нечем. Скажи автору одной строкой и "
           "пиши пост без опоры на содержание видео.")

_UNVERIFIED = ssl.create_default_context()
_UNVERIFIED.check_hostname = False
_UNVERIFIED.verify_mode = ssl.CERT_NONE


# ---------------------------------------------------------------- сеть

def fetch(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "ru,en;q=0.9"})
    last = None
    for ctx in (None, _UNVERIFIED):
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


# ---------------------------------------------------------------- адреса

def video_id(url):
    url = url.strip()
    for pattern in (r"youtu\.be/([A-Za-z0-9_-]{6,})",
                    r"[?&]v=([A-Za-z0-9_-]{6,})",
                    r"/shorts/([A-Za-z0-9_-]{6,})",
                    r"/embed/([A-Za-z0-9_-]{6,})",
                    r"/live/([A-Za-z0-9_-]{6,})"):
        hit = re.search(pattern, url)
        if hit:
            return hit.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    return None


def watch_url(vid):
    return "https://www.youtube.com/watch?v=%s" % vid


def to_seconds(stamp):
    if stamp is None:
        return None
    stamp = str(stamp).strip().replace(",", ".")
    if not stamp:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", stamp):
        return float(stamp)
    parts = stamp.split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return None
    total = 0.0
    for piece in parts:
        total = total * 60 + piece
    return total


def stamp(seconds):
    seconds = int(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return "%d:%02d:%02d" % (hours, minutes, secs)
    return "%d:%02d" % (minutes, secs)


# ---------------------------------------------------------------- парсеры субтитров

def clean_line(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = htmlmod.unescape(text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def push(segments, start, text):
    text = clean_line(text)
    if not text:
        return
    if segments:
        prev = segments[-1][1]
        if text == prev:
            return
        if text.startswith(prev) and len(text) > len(prev):
            segments[-1] = (segments[-1][0], text)
            return
        if prev.endswith(text):
            return
    segments.append((start, text))


def parse_vtt(raw):
    segments = []
    block_time = None
    buf = []
    for line in raw.splitlines():
        line = line.rstrip()
        hit = re.match(r"^((?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3})\s+-->\s+", line)
        if hit:
            if block_time is not None and buf:
                push(segments, block_time, " ".join(buf))
            block_time = to_seconds(hit.group(1))
            buf = []
            continue
        if not line:
            if block_time is not None and buf:
                push(segments, block_time, " ".join(buf))
                buf = []
            continue
        if line.upper().startswith(("WEBVTT", "KIND:", "LANGUAGE:", "NOTE", "STYLE")):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        buf.append(line)
    if block_time is not None and buf:
        push(segments, block_time, " ".join(buf))
    return segments


def parse_json3(raw):
    segments = []
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return segments
    for event in data.get("events") or []:
        pieces = event.get("segs") or []
        text = "".join(p.get("utf8", "") for p in pieces)
        push(segments, (event.get("tStartMs") or 0) / 1000.0, text)
    return segments


def parse_timedtext_xml(raw):
    segments = []
    for start, body in re.findall(r'<text[^>]*start="([\d.]+)"[^>]*>(.*?)</text>',
                                 raw, re.DOTALL):
        push(segments, float(start), body)
    return segments


def parse_any(raw):
    head = raw.lstrip()[:80].lower()
    if head.startswith("webvtt") or "-->" in raw[:2000]:
        return parse_vtt(raw)
    if head.startswith("{"):
        return parse_json3(raw)
    if "<text" in raw[:2000]:
        return parse_timedtext_xml(raw)
    return parse_vtt(raw)


# ---------------------------------------------------------------- источники субтитров

def subs_via_page(vid):
    """Страница видео: в ней лежит список дорожек субтитров. Без yt-dlp."""
    meta = {"title": None, "author": None, "duration": None}
    try:
        page = fetch(watch_url(vid))
    except Exception:  # noqa: BLE001
        return [], meta
    title = re.search(r'"title":\s*"([^"]{2,200})"', page)
    author = re.search(r'"author":\s*"([^"]{1,120})"', page)
    seconds = re.search(r'"lengthSeconds":\s*"(\d+)"', page)
    if title:
        meta["title"] = clean_line(title.group(1).encode("utf-8").decode("unicode_escape", "ignore")
                                   if "\\u" in title.group(1) else title.group(1))
    if author:
        meta["author"] = clean_line(author.group(1))
    if seconds:
        meta["duration"] = int(seconds.group(1))
    block = re.search(r'"captionTracks":(\[.*?\])', page, re.DOTALL)
    if not block:
        return [], meta
    payload = block.group(1).replace("\\u0026", "&").replace("\\/", "/")
    try:
        tracks = json.loads(payload)
    except Exception:  # noqa: BLE001
        tracks = []
        for base in re.findall(r'"baseUrl":"([^"]+)"', payload):
            tracks.append({"baseUrl": base, "languageCode": ""})
    ordered = sorted(tracks, key=lambda t: (
        0 if str(t.get("languageCode", "")).startswith("ru") else
        1 if str(t.get("languageCode", "")).startswith("en") else 2))
    for track in ordered:
        base = (track.get("baseUrl") or "").replace("\\u0026", "&")
        if not base:
            continue
        for suffix in ("&fmt=json3", "&fmt=vtt", ""):
            try:
                raw = fetch(base + suffix)
            except Exception:  # noqa: BLE001
                continue
            segments = parse_any(raw)
            if segments:
                return segments, meta
    return [], meta


def subs_via_ytdlp(vid):
    if not shutil.which("yt-dlp"):
        return [], {}
    tmp = tempfile.mkdtemp(prefix="vsub_")
    out = os.path.join(tmp, "s")
    meta = {}
    cmd = ["yt-dlp", "--skip-download", "--no-warnings", "--write-sub",
           "--write-auto-sub", "--sub-langs", SUB_LANGS, "--sub-format",
           "vtt/srv3/best", "--print-json", "-o", out, watch_url(vid)]
    try:
        done = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=120)
        head = (done.stdout or b"").decode("utf-8", "replace").strip().split("\n")[0]
        if head.startswith("{"):
            info = json.loads(head)
            meta = {"title": info.get("title"), "author": info.get("uploader"),
                    "duration": info.get("duration")}
    except Exception:  # noqa: BLE001
        return [], meta
    files = sorted(glob.glob(out + "*"))
    ranked = sorted(files, key=lambda p: (0 if ".ru" in p else 1 if ".en" in p else 2))
    for path in ranked:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                segments = parse_any(handle.read())
        except Exception:  # noqa: BLE001
            continue
        if segments:
            shutil.rmtree(tmp, ignore_errors=True)
            return segments, meta
    shutil.rmtree(tmp, ignore_errors=True)
    return [], meta


def get_transcript(vid):
    segments, meta = subs_via_page(vid)
    if segments:
        return segments, meta, "page"
    segments, meta2 = subs_via_ytdlp(vid)
    if segments:
        merged = meta2 or meta
        return segments, merged, "yt-dlp"
    return [], meta, "none"


# ---------------------------------------------------------------- сжатие

NUM_RE = re.compile(r"\d")
MONEY_RE = re.compile(r"[$€₽%]|доллар|руб|бесплат|цена|price|free|limit|лимит",
                     re.IGNORECASE)


def window(segments, start, end):
    left = to_seconds(start)
    right = to_seconds(end)
    if left is None and right is None:
        return segments
    out = []
    for moment, text in segments:
        if left is not None and moment < left:
            continue
        if right is not None and moment > right:
            continue
        out.append((moment, text))
    return out or segments


def full_text(segments):
    return " ".join(text for _, text in segments)


def build_map(segments, budget, keywords):
    """Детерминированная карта видео: начало, выдержки, цифры, конец."""
    if not segments:
        return []
    words = [w.strip().lower() for w in (keywords or []) if w.strip()]
    text = full_text(segments)
    lines = []

    head = text[:HEAD_CHARS]
    lines.append(("НАЧАЛО %s" % stamp(segments[0][0]), head))

    picked = []
    for moment, line in segments:
        score = 0
        low = line.lower()
        if words and any(word in low for word in words):
            score += 3
        if MONEY_RE.search(line):
            score += 2
        if NUM_RE.search(line):
            score += 1
        if score:
            picked.append((score, moment, line))
    picked.sort(key=lambda item: (-item[0], item[1]))
    keep = sorted(picked[:12], key=lambda item: item[1])
    for _, moment, line in keep:
        lines.append(("ЦИФРЫ %s" % stamp(moment), line))

    step = max(1, len(segments) // 6)
    for index in range(0, len(segments), step):
        moment, line = segments[index]
        if len(line) < 25:
            continue
        lines.append(("%s" % stamp(moment), line))

    lines.append(("КОНЕЦ %s" % stamp(segments[-1][0]), text[-TAIL_CHARS:]))

    out, used, seen = [], 0, set()
    for label, body in lines:
        body = re.sub(r"\s+", " ", body).strip()
        key = body[:60]
        if key in seen:
            continue
        seen.add(key)
        piece = "[%s] %s" % (label, body)
        if budget > 0 and used + len(piece) > budget:
            room = budget - used
            if room > 80:
                out.append(piece[:room].rsplit(" ", 1)[0] + "...")
            break
        out.append(piece)
        used += len(piece)
    return out


# ---------------------------------------------------------------- кадры

def grab_frames(vid, count, duration):
    count = max(1, min(int(count), MAX_FRAMES))
    if not shutil.which("yt-dlp"):
        return None, "WATCH: кадры требуют yt-dlp, его нет. Работай по тексту субтитров."
    if not shutil.which("ffmpeg"):
        return None, "WATCH: кадры требуют ffmpeg, его нет. Работай по тексту субтитров."
    folder = os.path.join(tempfile.gettempdir(), "vframes_%s" % vid)
    os.makedirs(folder, exist_ok=True)
    media = os.path.join(folder, "v.mp4")
    if not os.path.exists(media):
        cmd = ["yt-dlp", "--no-warnings", "-f",
               "worst[ext=mp4][height<=480]/worst[height<=480]/worst",
               "-o", media, watch_url(vid)]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=600)
        except Exception:  # noqa: BLE001
            return None, "WATCH: видео не скачалось. Работай по тексту субтитров."
    if not os.path.exists(media):
        return None, "WATCH: видео не скачалось. Работай по тексту субтитров."
    span = duration or 0
    shots = []
    for index in range(count):
        moment = int(span * (index + 0.5) / count) if span else index * 30
        path = os.path.join(folder, "f%02d.jpg" % index)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(moment), "-i", media,
               "-frames:v", "1", "-vf", "scale=640:-2", path]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=120)
        except Exception:  # noqa: BLE001
            continue
        if os.path.exists(path):
            shots.append((stamp(moment), path))
    if not shots:
        return None, "WATCH: кадры не вышли. Работай по тексту субтитров."
    return shots, None


# ---------------------------------------------------------------- доктор

def doctor():
    net = "нет"
    try:
        fetch("https://www.youtube.com/robots.txt", timeout=8)
        net = "есть"
    except Exception:  # noqa: BLE001
        pass
    print("сеть до youtube: %s" % net)
    print("yt-dlp: %s" % ("есть" if shutil.which("yt-dlp") else "нет, остаётся способ через страницу"))
    print("ffmpeg: %s" % ("есть" if shutil.which("ffmpeg") else "нет, флаг --frames недоступен"))
    print("режим по умолчанию: субтитры без кадров, бюджет %d знаков" % DEFAULT_BUDGET)
    return 0 if net == "есть" else 2


# ---------------------------------------------------------------- главное

def main():
    ap = argparse.ArgumentParser(description="просмотр видео для постов автора")
    ap.add_argument("url", nargs="?", default="", help="ссылка на видео или его id")
    ap.add_argument("--find", "--keywords", dest="find", default="",
                    help="слова через запятую, вокруг них берётся текст")
    ap.add_argument("--full", action="store_true", help="весь текст с таймкодами")
    ap.add_argument("--start", default=None, help="откуда, вида 04:10")
    ap.add_argument("--end", default=None, help="докуда, вида 07:30")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help="потолок вывода в знаках, 0 без ограничения")
    ap.add_argument("--frames", type=int, default=0,
                    help="сколько кадров вытащить, потолок %d" % MAX_FRAMES)
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument("--doctor", action="store_true", help="проверить окружение")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args()

    if args.version:
        print("watch.py %s" % VERSION)
        return 0
    if args.doctor:
        return doctor()
    if not args.url.strip():
        ap.print_help()
        return 1

    vid = video_id(args.url)
    if not vid:
        print("WATCH: это не похоже на ссылку YouTube. Проверь адрес у автора.")
        return 1

    segments, meta, how = get_transcript(vid)
    if not segments:
        print(NO_SUBS)
        return 2
    segments = window(segments, args.start, args.end)
    keywords = [w for w in args.find.split(",") if w.strip()]
    duration = meta.get("duration") or int(segments[-1][0]) + 5

    if args.find and not args.full:
        rows = []
        low = [w.strip().lower() for w in keywords]
        for moment, line in segments:
            if any(word in line.lower() for word in low):
                rows.append("[%s] %s" % (stamp(moment), line))
        body = rows or ["слова не нашлись, ниже карта видео"] + build_map(
            segments, args.budget, keywords)
    elif args.full:
        body = ["[%s] %s" % (stamp(moment), line) for moment, line in segments]
    else:
        body = build_map(segments, args.budget, keywords)

    text = "\n".join(body)
    if args.budget > 0 and len(text) > args.budget:
        text = text[:args.budget].rsplit("\n", 1)[0] + "\n[обрезано по бюджету %d]" % args.budget

    shots, shot_error = ([], None)
    if args.frames:
        shots, shot_error = grab_frames(vid, args.frames, duration)
        shots = shots or []

    if args.json:
        print(json.dumps({
            "id": vid, "title": meta.get("title"), "author": meta.get("author"),
            "duration": duration, "source": how, "segments": len(segments),
            "text": text, "frames": [{"time": t, "path": p} for t, p in shots],
            "frames_error": shot_error}, ensure_ascii=False))
        return 0

    print("WATCH: %s" % (meta.get("title") or vid))
    print("автор: %s | длина: %s | субтитры: %s | строк: %d" % (
        meta.get("author") or "?", stamp(duration), how, len(segments)))
    print("url: %s" % watch_url(vid))
    print(text)
    if shot_error:
        print(shot_error)
    for moment, path in shots:
        print("кадр %s: %s" % (moment, path))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
