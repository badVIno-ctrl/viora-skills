"""Small shared helpers: subprocess, ffprobe, retries, colours, text rules, easing."""
from __future__ import annotations

import asyncio
import functools
import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar

log = logging.getLogger("shorts")
T = TypeVar("T")


class ShortsError(RuntimeError):
    """Error with a message that is safe and useful to show to the user."""


# ---------------------------------------------------------------- subprocess

def run(cmd: Iterable[Any], *, quiet: bool = True, input: bytes | None = None, timeout: float | None = None) -> str:
    args = [str(c) for c in cmd]
    log.debug("run: %s", " ".join(args))
    proc = subprocess.run(args, input=input, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        tail = proc.stderr.decode(errors="replace")[-1500:]
        raise ShortsError(f"command failed ({args[0]}): {tail.strip()}")
    return proc.stdout.decode(errors="replace")


def ffprobe(path: Path | str) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    return json.loads(out)


def media_duration(path: Path | str) -> float:
    return float(ffprobe(path)["format"]["duration"])


# ---------------------------------------------------------------- retries

def retry(times: int = 4, delay: float = 1.5, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """Retry a sync or async function with exponential backoff."""

    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrap(*a, **k):
                d = delay
                for i in range(times):
                    try:
                        return await fn(*a, **k)
                    except exceptions as e:  # noqa: PERF203
                        if i == times - 1:
                            raise
                        log.warning("%s failed (%s), retry %d/%d in %.1fs", fn.__name__, e, i + 1, times - 1, d)
                        await asyncio.sleep(d)
                        d *= backoff
            return awrap  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrap(*a, **k):
            d = delay
            for i in range(times):
                try:
                    return fn(*a, **k)
                except exceptions as e:  # noqa: PERF203
                    if i == times - 1:
                        raise
                    log.warning("%s failed (%s), retry %d/%d in %.1fs", fn.__name__, e, i + 1, times - 1, d)
                    time.sleep(d)
                    d *= backoff
        return wrap  # type: ignore[return-value]

    return deco


# ---------------------------------------------------------------- geometry & motion

def snap8(v: float) -> int:
    return int(round(v / 8.0)) * 8


def ease(t: float) -> float:
    """The single easing curve used for every move in a video (ease-out cubic)."""
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


# ---------------------------------------------------------------- colour

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ShortsError(f"bad colour: #{h}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: Iterable[float]) -> str:
    r, g, b = (max(0, min(255, int(round(c)))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def luminance(rgb: tuple[int, int, int]) -> float:
    def ch(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str | tuple, b: str | tuple) -> float:
    ra = hex_to_rgb(a) if isinstance(a, str) else a
    rb = hex_to_rgb(b) if isinstance(b, str) else b
    la, lb = luminance(ra), luminance(rb)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def fit_contrast(color: str, against: str, target: float = 7.0) -> str:
    """Lighten or darken `color` (keeping its hue) until it reaches `target` contrast with `against`."""
    if contrast(color, against) >= target:
        return color.upper()
    base = hex_to_rgb(color)
    toward = (255, 255, 255) if luminance(hex_to_rgb(against)) < 0.18 else (0, 0, 0)
    for i in range(1, 101):
        k = i / 100
        c = rgb_to_hex(base[j] + (toward[j] - base[j]) * k for j in range(3))
        if contrast(c, against) >= target:  # check the rounded hex, not the float colour
            return c
    return rgb_to_hex(toward)


def ass_color(hexcol: str, alpha: int = 0) -> str:
    r, g, b = hex_to_rgb(hexcol)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


# ---------------------------------------------------------------- text rules

DASHES = re.compile("[\u2014\u2013\u2012\u2015]")  # em, en, figure dash, horizontal bar
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U0001F900-\U0001F9FF\u2B50\u2B06\u2194-\u21AA\uFE0F]"
)
URL = re.compile(r"https?://[^\s<>\"')]+|\bt\.me/[\w/]+", re.I)
HASHTAG = re.compile(r"#[\w\u0400-\u04FF]+", re.U)


def has_long_dash(text: str) -> bool:
    return bool(DASHES.search(text or ""))


def fix_dashes(text: str) -> str:
    return DASHES.sub("-", text or "")


def count_emoji(text: str) -> int:
    return len([m for m in EMOJI.findall(text or "") if m != "\uFE0F"])


def script_ratio(text: str) -> dict[str, float]:
    """Share of Cyrillic vs Latin letters (hashtags and links removed)."""
    t = URL.sub(" ", HASHTAG.sub(" ", text or ""))
    cyr = len(re.findall(r"[\u0400-\u04FF]", t))
    lat = len(re.findall(r"[A-Za-z]", t))
    n = max(1, cyr + lat)
    return {"cyrillic": cyr / n, "latin": lat / n, "letters": cyr + lat}


def read_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path | str, data: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
