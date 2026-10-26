"""What is on screen in a source film: text screens (titles, credits), black frames, line positions.

Used twice:
  - when picking moments for an edit (a text screen or a black frame lowers the moment score),
  - in QA (`edit_content`): the finished edit must not show credits or long black frames.

Text detector (no models, OpenCV only), tuned on Big Buck Bunny (CC-BY, credits 490-580 s) at 640 px width:
  1. horizontal Sobel edges stronger than EDGE_THR (letters are many sharp vertical strokes);
  2. a horizontal closing merges letters of one line into one blob;
  3. a blob is a text line if it is thin (4..6% of height), wide (>= 4x its height), dense with strokes
     and has calm rows right above and below it (grass and fur have strokes everywhere, text has line gaps).
  Film frames: at most 4 such lines (99th percentile 3). Credit frames: median 15.
Static rows (a title card or a credit block that holds still) raise the score: the same line rows in the
next sample mean "printed text", not texture.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from ..config import cache_dir
from ..util import ShortsError

ANALYSIS_W = 640
EDGE_THR = 120
TEXT_LINES_HARD = 5  # this many text lines on a frame = a text screen
BLACK_MEAN = 18.0
BLACK_STD = 10.0


@dataclass
class ScreenInfo:
    lines: int
    area: float
    rows: list[int]
    mean: float
    std: float

    @property
    def black(self) -> bool:
        return self.mean < BLACK_MEAN and self.std < BLACK_STD


def text_lines(gray: np.ndarray) -> tuple[int, float, list[int]]:
    """Number of text lines, their area share and their row positions (in a 640-wide frame)."""
    h, w = gray.shape[:2]
    if w != ANALYSIS_W:
        s = ANALYSIS_W / w
        gray = cv2.resize(gray, (ANALYSIS_W, max(8, int(h * s))), interpolation=cv2.INTER_AREA)
        h, w = gray.shape[:2]
    gx = np.abs(cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3))
    e = (gx > EDGE_THR).astype(np.uint8)
    blob = cv2.morphologyEx(e, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1)))
    blob = cv2.morphologyEx(blob, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 2)))
    n, _, st, _ = cv2.connectedComponentsWithStats(blob, connectivity=8)
    lines, area, rows = 0, 0, []
    for i in range(1, n):
        x, y, ww, hh, _a = (int(v) for v in st[i])
        if not (4 <= hh <= 0.06 * h + 4 and ww >= max(30, 4 * hh)):
            continue
        dens = float(e[y:y + hh, x:x + ww].mean())
        if dens < 0.18:
            continue
        above = float(e[max(0, y - hh):y, x:x + ww].mean()) if y > 0 else 0.0
        below = float(e[y + hh:min(h, y + 2 * hh), x:x + ww].mean()) if y + hh < h else 0.0
        if max(above, below) > 0.35 * dens:
            continue
        lines += 1
        area += ww * hh
        rows.append(y + hh // 2)
    return lines, area / float(w * h), sorted(rows)


def screen_info(gray: np.ndarray) -> ScreenInfo:
    n, a, rows = text_lines(gray)
    return ScreenInfo(n, round(a, 4), rows, float(gray.mean()), float(gray.std()))


def textness(infos: list[ScreenInfo]) -> np.ndarray:
    """0..1 per sample: 0 = picture, 1 = text screen. Lines that stay on the same rows add confidence."""
    out = np.zeros(len(infos), np.float32)
    for i, s in enumerate(infos):
        base = np.clip((s.lines - 2) / (TEXT_LINES_HARD + 1 - 2), 0.0, 1.0)
        if i > 0 and s.rows and infos[i - 1].rows:
            prev = np.array(infos[i - 1].rows)
            same = sum(1 for r in s.rows if np.min(np.abs(prev - r)) <= 2)
            if same >= 2:
                base = min(1.0, base + 0.15 * same / max(1, len(s.rows)) + 0.1)
        out[i] = base if s.lines >= 2 else 0.0
    return out


def decode_gray(path: Path | str, fps: float, width: int = ANALYSIS_W, start: float = 0.0,
                duration: float | None = None, crop: tuple[int, int, int, int] | None = None) -> tuple[np.ndarray, list[float]]:
    """Grey frames at `fps`, scaled to `width` (aspect kept). `crop` = x, y, w, h in source pixels."""
    vf = []
    if crop:
        x, y, cw, ch = crop
        vf.append(f"crop={cw}:{ch}:{x}:{y}")
    cmd = ["ffmpeg", "-loglevel", "error", "-threads", "0"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "json", str(path)], capture_output=True, text=True)
    try:
        st = json.loads(probe.stdout)["streams"][0]
        sw, sh = (crop[2], crop[3]) if crop else (int(st["width"]), int(st["height"]))
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise ShortsError(f"cannot read video size of {path}") from e
    h = max(2, int(round(sh * width / sw / 2)) * 2)
    vf += [f"fps={fps}", f"scale={width}:{h}:flags=area"]
    cmd += ["-an", "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise ShortsError(f"ffmpeg could not decode {path}: {p.stderr.decode(errors='replace')[-200:]}")
    n = len(p.stdout) // (width * h)
    arr = np.frombuffer(p.stdout[: n * width * h], np.uint8).reshape(n, h, width)
    return arr, [start + i / fps for i in range(n)]


def _key(path: Path, fps: float) -> str:
    st = path.stat()
    return hashlib.sha1(f"{path.resolve()}|{st.st_size}|{int(st.st_mtime)}|{fps}|v1".encode()).hexdigest()[:16]


def film_screens(path: Path | str, fps: float = 1.0) -> dict:
    """Per-second screen analysis of a whole film (cached): times, textness, black, lines."""
    path = Path(path)
    cache = cache_dir("screens") / f"{_key(path, fps)}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    frames, times = decode_gray(path, fps)
    infos = [screen_info(g) for g in frames]
    tx = textness(infos)
    res = {"fps": fps, "t": [round(t, 3) for t in times], "text": [round(float(v), 3) for v in tx],
           "black": [bool(s.black) for s in infos], "lines": [s.lines for s in infos]}
    cache.write_text(json.dumps(res), encoding="utf-8")
    return res


def text_runs(times: list[float], text: list[float], thr: float = 0.5) -> list[tuple[float, float]]:
    """Merged [start, end) intervals where the text score is at least thr."""
    out: list[list[float]] = []
    step = times[1] - times[0] if len(times) > 1 else 1.0
    for t, v in zip(times, text):
        if v >= thr:
            if out and t - out[-1][1] <= step + 1e-6:
                out[-1][1] = t + step
            else:
                out.append([t, t + step])
    return [(a, b) for a, b in out]
