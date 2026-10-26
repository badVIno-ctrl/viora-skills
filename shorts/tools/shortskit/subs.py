"""YouTube subtitles -> word-timed SRT for a section (v2.1). No speech model needed.

`python tools/shorts.py srt URL --start 8064 --end 8110 --out 01.srt [--lang ru]`
The SRT is shifted so 0 = `--start`: use the same start as the `fetch --section` of the main video.
YouTube auto-captions carry per-word timestamps (<00:00:01.200><c> word</c>): cues are rebuilt from them, not from the
rolling two-line text (which repeats every phrase). Cues break on pauses > 1 s, sentence ends or after 6 words.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

from .util import ShortsError, log

_TS = r"(\d\d):(\d\d):(\d\d)\.(\d+)"


def _sec(h, m, s, ms) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def _keep_word(w: str) -> bool:
    """Drop speaker marks, bleep markers ("[ __ ]") and sound tags ("[Музыка]") that auto-captions put between words."""
    w = html.unescape(w).strip()
    return not (w in (">>", ">") or re.fullmatch(r"[\[\]()_\s*♪-]+", w) or re.fullmatch(r"\[[^\]]*\]", w))


def vtt_words(text: str) -> list[tuple[float, str]]:
    """[(start, word)] from a YouTube auto-caption VTT (word tags). Falls back to whole cues for manual subtitles."""
    words: dict[int, tuple[float, str]] = {}
    plain = []
    cue_t = 0.0
    for line in text.splitlines():
        m = re.match(_TS + r" --> ", line)
        if m:
            cue_t = _sec(*m.groups())
            continue
        if "<c>" in line or re.search(r"<\d\d:\d\d:\d\d\.\d+>", line):
            first = re.match(r"([^<]+)<", line)
            if first and first.group(1).strip():
                for w in first.group(1).split():
                    words.setdefault(int(cue_t * 100), (cue_t, w))
            for tm in re.finditer(r"<" + _TS + r"><c>([^<]*)</c>", line):
                t = _sec(*tm.groups()[:4])
                for w in html.unescape(tm.group(5)).split():
                    words.setdefault(int(t * 100), (t, w))
        elif line.strip() and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            plain.append((cue_t, line.strip()))
    if words:
        return [(t, html.unescape(w)) for t, w in sorted(words.values()) if _keep_word(w)]
    out, seen = [], set()
    for t, l in plain:
        if l not in seen:
            seen.add(l)
            out += [(t + i * 0.01, w) for i, w in enumerate(html.unescape(l).split())]
    return out


def words_to_srt(words: list[tuple[float, str]], start: float, end: float, pause: float = 1.0, max_words: int = 6) -> str:
    sel = [(t, w) for t, w in words if start - 0.2 <= t <= end]
    cues, cur = [], []
    for i, (t, w) in enumerate(sel):
        if cur and (t - cur[-1][0] > pause or len(cur) >= max_words or cur[-1][1].endswith((".", "?", "!"))):
            cues.append(cur)
            cur = []
        cur.append((t, w))
    if cur:
        cues.append(cur)

    def ts(x: float) -> str:
        x = max(x, 0.0)
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round(x * 1000)) % 1000:03d}"
    out = []
    for n, c in enumerate(cues, 1):
        a = c[0][0] - start
        nxt = (cues[n][0][0] - start) if n < len(cues) else a + 99
        b = min(c[-1][0] - start + 0.45, nxt - 0.02, end - start)
        out.append(f"{n}\n{ts(a)} --> {ts(max(b, a + 0.3))}\n{' '.join(w for _, w in c)}\n")
    return "\n".join(out)


def youtube_srt(url: str, start: float, end: float, out: Path, lang: str = "ru") -> dict:
    exe = shutil.which("yt-dlp")
    base = [exe] if exe else [sys.executable, "-m", "yt_dlp"]
    if shutil.which("deno") is None and shutil.which("node"):
        base += ["--js-runtimes", "node"]
    with tempfile.TemporaryDirectory() as td:
        cmd = base + ["--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", f"{lang},{lang}-orig", "--sub-format", "vtt",
                      "--no-warnings", "-o", f"{td}/s", url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        files = sorted(Path(td).glob("s*.vtt"))
        if not files:
            raise ShortsError(f"no {lang} subtitles for {url}: {r.stderr.strip()[-200:]}. Use a speech model (faster-whisper) on the downloaded piece.")
        words = vtt_words(files[0].read_text(encoding="utf-8"))
    srt = words_to_srt(words, start, end)
    if not srt.strip():
        raise ShortsError("subtitles exist but nothing falls inside the section")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(srt, encoding="utf-8")
    side = write_words_sidecar(words, start, end, out)
    log.info("srt: %d cues -> %s (+ word starts %s)", srt.count("-->"), out, side.name)
    return {"srt": str(out), "cues": srt.count("-->"), "words": sum(1 for t, _ in words if start <= t <= end),
            "words_json": str(side)}


def write_words_sidecar(words: list[tuple[float, str]], start: float, end: float, srt_out: Path) -> Path:
    """v2.2: `<name>.words.json` next to the SRT: [{"w", "s", "e"}] in the same timebase (0 = --start).
    YouTube gives the START of every word; the end is the next word's start (pause > 0.6 s: start + length estimate).
    `stack` uses it for word-by-word captions and to keep cuts out of words."""
    import json

    sel = [(t, w) for t, w in words if start - 0.2 <= t <= end + 3.0 and _keep_word(w)]
    rows = []
    for i, (t, w) in enumerate(sel):
        est = t + min(0.75, 0.12 + 0.065 * len(w))
        nxt = sel[i + 1][0] if i + 1 < len(sel) else None
        e = min(est, nxt - 0.02) if nxt is not None and nxt - t < 0.6 else est
        rows.append({"w": html.unescape(w), "s": round(t - start, 3), "e": round(max(e, t + 0.08) - start, 3), "approx_end": True})
    side = Path(srt_out).with_suffix(".words.json")
    side.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return side


_MAT = re.compile(
    r"(?<![а-яёa-z])(?:"
    r"[а-яё]*(?:пизд|залуп|долбо[её]б|мудак|мудил|пидор|пидар|[её]бл[аоуы]н|[её]бан|хуев|хуёв)[а-яё]*"
    r"|(?:на|по|до|при|за|от|вы|ни|о|с)?х[уy][йеёяию][а-яё]*"
    r"|бля(?:[дт]ь|[дт]ск[а-яё]*)?"
    r"|(?:за|по|у|вы|от|на|при|съ|об|раз|до|с)?[её]б(?:а[нтл]|ну|ыр|ло|ёт|ет|ут|ли|ыв)[а-яё]*"
    r")(?![а-яё])", re.I)


def mask_profanity(text: str) -> str:
    """Profanity -> first letter + asterisks (ads and monetization: never show it as is)."""
    return _MAT.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), text)
