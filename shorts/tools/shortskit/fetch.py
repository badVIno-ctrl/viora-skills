"""Source acquisition ladder (`shorts.py fetch`) and brand logos from public Telegram pages.

Why a ladder: one failed yt-dlp call is not "YouTube is blocked". Real fixes, in order of cost:
  1. current yt-dlp + a JS runtime (node/deno): without it YouTube formats are missing (yt-dlp wiki "EJS");
  2. other player clients (web_safari, mweb, tv, android_vr, ios);
  3. the USER's own cookies (SHORTS_YTDLP_COOKIES file or SHORTS_YTDLP_BROWSER=chrome|firefox);
  4. the USER's own proxy (SHORTS_YTDLP_PROXY);
  5. self-update of yt-dlp, then the same again;
  6. recording in the shared browser (adapters/ytbrowser.py) for short sections.
Every attempt is written to <out>/fetch-status.json. Only after the whole ladder failed does the tool print
ONE ready command for the user's own computer (residential IP) and the run continues with other sources.
No free-proxy lists, no account farms, no DRM or paywall bypass.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .config import cache_dir
from .util import ShortsError, log

FORMAT = "bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}]"   # H.264 first: OpenCV cannot read AV1/VP9
CLIENTS = [None, "web_safari", "mweb", "tv", "android_vr", "ios"]
MEDIA_EXT = (".mp4", ".m4a", ".webm", ".mkv", ".wav", ".opus", ".mp3")


# ------------------------------------------------------------------ brand logos

def brand_logo(handle: str) -> Path | None:
    """Official avatar of a public Telegram bot/channel (t.me/<handle> og:image). None if unavailable."""
    handle = handle.strip().lstrip("@").split("?")[0].rstrip("/").split("/")[-1]
    dest = cache_dir("brands") / f"{re.sub(r'[^A-Za-z0-9_]', '_', handle)}.jpg"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    try:
        req = urllib.request.Request(f"https://t.me/{handle}", headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if not m:
            return None
        img = urllib.request.Request(m.group(1).replace("&amp;", "&"), headers={"User-Agent": "Mozilla/5.0"})
        dest.write_bytes(urllib.request.urlopen(img, timeout=30).read())
        return dest if dest.stat().st_size > 1000 else None
    except Exception as e:  # network is best-effort; the caller falls back to an honest monogram
        log.warning("brand logo for %s not fetched: %s", handle, e)
        return None


def _ensure_h264(p: Path) -> str:
    """Every tool in the skill reads frames through OpenCV: AV1/VP9/webm must become H.264 mp4 right after download."""
    codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True).stdout.strip()
    if codec == "h264" and p.suffix == ".mp4":
        return str(p)
    dst = p.with_suffix(".mp4") if p.suffix != ".mp4" else p.with_name(p.stem + "-h264.mp4")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)], capture_output=True, text=True)
    if r.returncode == 0 and dst.exists():
        if dst != p:
            p.unlink(missing_ok=True)
        return str(dst)
    log.warning("H.264 transcode failed for %s: %s", p, r.stderr[-200:])
    return str(p)


# ------------------------------------------------------------------ yt-dlp helpers

def _ytdlp() -> list[str]:
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def _base() -> list[str]:
    cmd = _ytdlp() + ["--no-playlist", "--no-warnings", "--quiet", "--no-progress"]
    if shutil.which("deno") is None and shutil.which("node"):
        cmd += ["--js-runtimes", "node"]
    return cmd


def classify(err: str) -> str:
    e = err.lower()
    if "confirm you" in e and "bot" in e or "sign in to confirm" in e:
        return "bot_block"
    if "private video" in e or "video unavailable" in e or "has been removed" in e or "terminated" in e:
        return "unavailable"
    if "not available in your country" in e or "geo" in e and "restrict" in e:
        return "geo"
    if "age" in e and ("confirm your age" in e or "age-restricted" in e):
        return "age"
    if "http error 403" in e or "nsig" in e or "unable to extract" in e or "requested format is not available" in e:
        return "outdated_or_formats"
    if "http error 429" in e or "too many requests" in e:
        return "rate_limit"
    return "other"


def parse_time(x: str) -> float:
    x = x.strip()
    if ":" in x:
        sec = 0.0
        for p in x.split(":"):
            sec = sec * 60 + float(p)
        return sec
    return float(x)


def parse_section(s: str | None) -> tuple[float, float] | None:
    if not s:
        return None
    a, b = re.split(r"\s*[-–]\s*", s.strip().lstrip("*"), maxsplit=1)
    start, end = parse_time(a), parse_time(b)
    if end <= start:
        raise ShortsError(f"bad section {s!r}: end must be after start")
    return start, end


def probe(url: str) -> dict:
    """Title, channel, duration - cheap check that a URL is the video the user means."""
    cmd = _base() + ["--skip-download", "--print", "%(id)s\t%(title)s\t%(channel)s\t%(duration)s", url]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if out.returncode != 0:
        # oEmbed still names public videos when yt-dlp is blocked
        try:
            ep = "https://www.youtube.com/oembed?format=json&url=" + urllib.request.quote(url, safe="")
            j = json.load(urllib.request.urlopen(ep, timeout=15))
            return {"id": url, "title": j.get("title", ""), "channel": j.get("author_name", ""), "duration": None, "via": "oembed"}
        except Exception:
            raise ShortsError(f"cannot read {url}: {out.stderr.strip()[-300:]}")
    i, t, c, d = (out.stdout.strip().split("\t") + ["", "", "", ""])[:4]
    return {"id": i, "title": t, "channel": c, "duration": float(d) if d not in ("", "NA", "None") else None, "via": "yt-dlp"}


def local_command(url: str, section: tuple[float, float] | None, audio: bool, name: str, max_height: int) -> str:
    """One command for the user's own computer, only used after every automatic rung failed."""
    parts = ["yt-dlp", "--no-playlist"]
    if section:
        parts += ["--download-sections", f'"*{section[0]:.2f}-{section[1]:.2f}"', "--force-keyframes-at-cuts"]
    if audio:
        parts += ["-x", "--audio-format", "wav"]
    else:
        parts += ["-f", f'"{FORMAT.format(h=max_height)}"', "--merge-output-format", "mp4"]
    parts += ["-o", f'"{name}.%(ext)s"', f'"{url}"']
    return " ".join(parts)


def _attempts(max_height: int, audio: bool):
    cookies = os.environ.get("SHORTS_YTDLP_COOKIES")
    browser = os.environ.get("SHORTS_YTDLP_BROWSER")
    proxy = os.environ.get("SHORTS_YTDLP_PROXY")
    fmt = ["-f", "ba/b", "-x", "--audio-format", "wav"] if audio else ["-f", FORMAT.format(h=max_height), "--merge-output-format", "mp4"]
    for cl in CLIENTS:
        extra = list(fmt)
        if cl:
            extra += ["--extractor-args", f"youtube:player_client={cl}"]
        yield (f"client={cl or 'default'}", extra)
    if cookies and Path(cookies).exists():
        for cl in (None, "web_safari", "mweb"):
            extra = fmt + ["--cookies", cookies] + (["--extractor-args", f"youtube:player_client={cl}"] if cl else [])
            yield (f"user-cookies+client={cl or 'default'}", extra)
    if browser:
        yield (f"user-browser-cookies={browser}", fmt + ["--cookies-from-browser", browser])
    if proxy:
        yield ("user-proxy", fmt + ["--proxy", proxy])


def _update_ytdlp() -> bool:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "--break-system-packages", "yt-dlp[default]"],
                           capture_output=True, text=True, timeout=240)
        if r.returncode != 0:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp[default]"], capture_output=True, text=True, timeout=240)
        return r.returncode == 0
    except Exception:
        return False


def fetch(url: str, out_dir: Path, name: str, section: tuple[float, float] | None = None, audio: bool = False,
          max_height: int = 1080, allow_update: bool = True) -> dict:
    """Run the ladder for one source. Returns {"ok", "path", "attempts", "local_command"}; never raises on blocks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = [p for p in out_dir.glob(f"{name}.*") if p.suffix in MEDIA_EXT]
    if existing:
        return {"ok": True, "path": str(existing[0]), "attempts": [{"step": "cache", "ok": True}], "url": url}
    attempts: list[dict] = []
    updated = False
    tmpl = str(out_dir / f"{name}.%(ext)s")

    def run_ladder() -> str | None:
        for label, extra in _attempts(max_height, audio):
            cmd = _base() + extra + ["-o", tmpl]
            if section:
                cmd += ["--download-sections", f"*{section[0]:.2f}-{section[1]:.2f}", "--force-keyframes-at-cuts"]
            r = subprocess.run(cmd + [url], capture_output=True, text=True, timeout=1500)
            got = [p for p in out_dir.glob(f"{name}.*") if p.suffix in MEDIA_EXT]
            if r.returncode == 0 and got:
                attempts.append({"step": label, "ok": True})
                return str(got[0])
            kind = classify(r.stderr)
            attempts.append({"step": label, "ok": False, "kind": kind, "error": r.stderr.strip()[-240:]})
            log.info("fetch %s: %s failed (%s)", name, label, kind)
            if kind in ("unavailable", "geo", "age") and not (os.environ.get("SHORTS_YTDLP_COOKIES") or os.environ.get("SHORTS_YTDLP_BROWSER")):
                return None
        return None

    path = run_ladder()
    if path and not audio:
        path = _ensure_h264(Path(path))
    if not path and allow_update and any(a.get("kind") in ("outdated_or_formats", "bot_block", "other") for a in attempts):
        updated = _update_ytdlp()
        attempts.append({"step": "update yt-dlp", "ok": updated})
        if updated:
            path = run_ladder()
    if not path and section:
        try:
            from .adapters import ytbrowser as YB
            if YB.is_youtube(url) and YB.available():
                p = YB.record_section(url, section[0], section[1], audio_only=audio, max_height=max_height)
                attempts.append({"step": "shared-browser recording", "ok": True})
                path = str(p)
            else:
                attempts.append({"step": "shared-browser recording", "ok": False, "error": "no shared browser (SHORTS_BROWSER_CDP) in this environment"})
        except Exception as e:
            attempts.append({"step": "shared-browser recording", "ok": False, "error": str(e)[-200:]})
    res = {"ok": bool(path), "path": path, "url": url, "name": name, "attempts": attempts}
    if not path:
        res["local_command"] = local_command(url, section, audio, name, max_height)
    return res


def fetch_many(items: list[dict], out_dir: Path) -> dict:
    """items: [{"url", "name", "section": "7-16", "audio": false}] -> status dict, also saved as fetch-status.json."""
    results = []
    for it in items:
        sec = parse_section(it.get("section"))
        name = it.get("name") or hashlib.sha1(it["url"].encode()).hexdigest()[:10]
        results.append(fetch(it["url"], out_dir, name, sec, bool(it.get("audio")), int(it.get("max_height", 1080))))
    status = {"ok": all(r["ok"] for r in results), "results": results}
    (out_dir / "fetch-status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status
