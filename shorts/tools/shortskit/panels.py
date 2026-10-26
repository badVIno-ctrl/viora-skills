"""Own procedural loops for the top panel (CC0, drawn by code, no stock footage).

Four kinds, each a seamless 10 s loop in brand colours:
  race   - procedural race: three lanes, racers overtake, road and stands scroll
  spin   - a row of flat-shaded 3D objects (cubes / octahedra) spinning over a moving stripe floor
  code   - code rain: every cell of a monospace grid filled, columns fall at different speeds
  runner - side view, BIG hero (70% of the panel) runs and jumps over crates, parallax city
Rules (QA checks the same on the final video): >= 30% of panel pixels change every second,
no big dark empty area. `make_loop` caches the mp4 in SHORTS_CACHE/panels.
`choose_kind(topic, source_types)` picks the loop for the topic; `layout.top.source: "loop:auto"` or "loop:<kind>"."""
from __future__ import annotations

import hashlib
import math
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import asset, cache_dir
from .util import ShortsError, hex_to_rgb

KINDS = ("race", "spin", "code", "runner")
LOOP = 10.0
VERSION = "1"
MIN_CHANGE = 0.30   # share of panel pixels that must change between t and t+1 s
MAX_DARK_VOID = 0.25  # largest connected dark flat area, share of the panel
CHANGE_DELTA = 10   # luma difference that counts as "changed"

TOPIC = [
    ("code", ("код", "html", "программ", "скрипт", "нейросет", "ии", "ai", "gpt", "api", "сайт", "веб", "code",
              "script", "dev", "site", "web", "python", "js", "terminal", "терминал")),
    ("spin", ("3d", "cad", "модел", "дизайн", "товар", "продукт", "деталь", "three", "render", "рендер", "design",
              "product", "object", "объект")),
    ("race", ("гонк", "скорост", "быстр", "турнир", "битв", "сравн", "против", "рейтинг", "race", "speed", "fast",
              "battle", "versus", "vs", "compare", "top")),
    ("runner", ("игр", "game", "раннер", "runner", "фильм", "кино", "эдит", "film", "movie", "edit", "весел", "fun")),
]
BY_SOURCE = {"html": "spin", "site": "code", "film": "runner", "video": "race", "text": "code", "images": "spin"}


def choose_kind(topic: str, source_types: list[str] | None = None) -> str:
    words = re.findall(r"\w+", (topic or "").lower())
    for kind, stems in TOPIC:
        for w in words:
            if any(w.startswith(s) if len(s) > 2 else w == s for s in stems):
                return kind
    for t in source_types or []:
        if t in BY_SOURCE:
            return BY_SOURCE[t]
    return "runner"


def _mix(a, b, k: float) -> tuple[int, int, int]:
    return tuple(int(round(x * (1 - k) + y * k)) for x, y in zip(a, b))


class Pal:
    def __init__(self, bg: str, fg: str, accent: str):
        self.bg, self.fg, self.ac = hex_to_rgb(bg), hex_to_rgb(fg), hex_to_rgb(accent)
        # panels never sit on pure black: the base is lifted towards fg so there is no dark void
        self.base = _mix(self.bg, self.fg, 0.16)
        self.t1 = _mix(self.bg, self.fg, 0.28)
        self.t2 = _mix(self.bg, self.fg, 0.45)
        self.t3 = _mix(self.bg, self.fg, 0.65)

    def bgr(self, c):
        return (int(c[2]), int(c[1]), int(c[0]))


def _rnd(i: float) -> float:
    x = math.sin(i * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


# ---------------------------------------------------------------- the four loops (t in [0, LOOP))

def _race(t: float, w: int, h: int, p: Pal) -> np.ndarray:
    im = np.empty((h, w, 3), np.uint8)
    im[:] = p.bgr(p.base)
    u = h / 384
    stand_h = int(h * 0.30)
    # stands: checker of spectators, scroll 2 tiles per loop-second multiple -> seamless
    tile = max(8, int(24 * u))
    off = int((t / LOOP) * tile * 45) % (6 * tile)  # 4.5 tiles/s: never the same picture 1 s later
    for y in range(0, stand_h, tile):
        for x in range(-2 * tile, w + 2 * tile, tile):
            k = ((x + off) // tile + y // tile + (y // tile) % 2) % 3
            col = (p.t1, p.t2, p.t3)[k]
            cv2.rectangle(im, (x - off % tile, y), (x - off % tile + tile - 3, y + tile - 3), p.bgr(col), -1)
    road_y = stand_h
    lanes = 3
    lane_h = (h - road_y) // lanes
    dash = int(90 * u)
    period = dash * 2
    shift = int((t / LOOP) * period * 35) % period  # 3.5 periods/s: half a period off after 1 s
    # asphalt: diagonal bands, 2.5 periods per second
    per = int(120 * u)
    aoff = int((t / LOOP) * per * 25) % per
    for x in range(-h - per, w + per, per):
        pts = np.array([[x + aoff, h], [x + aoff + per // 2, h], [x + aoff + per // 2 + (h - road_y), road_y],
                        [x + aoff + (h - road_y), road_y]], np.int32)
        cv2.fillPoly(im, [pts], p.bgr(p.t1))
    for i in range(lanes + 1):
        y = road_y + i * lane_h
        cv2.line(im, (0, y), (w, y), p.bgr(p.t3), max(2, int(4 * u)))
        if 0 < i < lanes:
            for x in range(-period, w + period, period):
                cv2.rectangle(im, (x - shift, y - int(3 * u)), (x - shift + dash, y + int(3 * u)), p.bgr(p.fg), -1)
    for i in range(lanes):
        # each racer moves on its own sine so they overtake; period divides LOOP
        x = int(w * (0.45 + 0.28 * math.sin(2 * math.pi * (t / LOOP * (i + 1)) + i * 2.1)))
        y = road_y + i * lane_h + lane_h // 2
        rw, rh = int(150 * u), int(lane_h * 0.62)
        col = p.ac if i == 1 else p.fg
        cv2.rectangle(im, (x - rw // 2, y - rh // 2), (x + rw // 2, y + rh // 2), p.bgr(col), -1)
        cv2.rectangle(im, (x - rw // 6, y - rh // 2 + int(6 * u)), (x + rw // 4, y + rh // 2 - int(6 * u)), p.bgr(p.bg), -1)
        for k in range(4):  # speed lines behind
            ly = y - rh // 2 + int((k + 0.5) * rh / 4)
            ln = int((60 + 50 * _rnd(i * 10 + k + math.floor(t * 8))) * u)
            cv2.line(im, (x - rw // 2 - int(12 * u) - ln, ly), (x - rw // 2 - int(12 * u), ly), p.bgr(p.t3), max(2, int(5 * u)))
    return im


def _proj(v: np.ndarray, ax: float, ay: float) -> np.ndarray:
    ca, sa, cb, sb = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])
    ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]])
    return v @ (ry @ rx).T


CUBE_V = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
CUBE_F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
OCT_V = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float) * 1.5
OCT_F = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]


def _spin(t: float, w: int, h: int, p: Pal) -> np.ndarray:
    im = np.empty((h, w, 3), np.uint8)
    im[:] = p.bgr(p.t1)
    u = h / 384
    # moving diagonal stripes: 20 periods per loop
    per = int(80 * u)
    off = int((t / LOOP) * per * 25) % per  # 2.5 periods/s
    for x in range(-h - per, w + per, per):
        pts = np.array([[x + off, h], [x + off + per // 2, h], [x + off + per // 2 + h, 0], [x + off + h, 0]], np.int32)
        cv2.fillPoly(im, [pts], p.bgr(p.t2))
    light = np.array([0.4, -0.6, -0.7])
    light /= np.linalg.norm(light)
    n = 5
    size = h * 0.40
    for k in range(n):
        cx = w * (k + 0.5) / n
        cy = h * 0.5 + h * 0.08 * math.sin(2 * math.pi * (t / LOOP * 2) + k)
        ang = 2 * math.pi * (t / LOOP) * (2 + (k % 2)) + k
        verts, faces = (CUBE_V, CUBE_F) if k % 2 == 0 else (OCT_V, OCT_F)
        v = _proj(verts * size / 1.6, 2 * math.pi * (t / LOOP) + k, ang)  # whole laps: seamless
        drawn = []
        for f in faces:
            a, b, c = v[f[0]], v[f[1]], v[f[2]]
            nrm = np.cross(b - a, c - a)
            if nrm[2] >= 0:
                continue
            nrm = nrm / (np.linalg.norm(nrm) + 1e-9)
            shade = 0.35 + 0.65 * max(0.0, float(-nrm @ light))
            depth = float(np.mean(v[list(f), 2]))
            drawn.append((depth, f, shade))
        base = p.ac if k == n // 2 else p.fg
        for _, f, shade in sorted(drawn, key=lambda x: -x[0]):
            pts = np.array([[cx + v[i, 0], cy + v[i, 1]] for i in f], np.int32)
            col = _mix(p.bg, base, 0.25 + 0.75 * shade)
            cv2.fillPoly(im, [pts], p.bgr(col), lineType=cv2.LINE_AA)
            cv2.polylines(im, [pts], True, p.bgr(p.bg), max(2, int(3 * u)), lineType=cv2.LINE_AA)
    return im


_GLYPHS: dict = {}


def _glyph_atlas(cell_w: int, cell_h: int) -> tuple[np.ndarray, int]:
    key = (cell_w, cell_h)
    if key not in _GLYPHS:
        chars = "0123456789abcdef{}()<>=+-*/;:.#$&|[]ABCDEFxyz"
        font = ImageFont.truetype(str(asset("fonts/JetBrainsMono-Bold.ttf")), int(cell_h * 0.95))
        atlas = np.zeros((len(chars), cell_h, cell_w), np.float32)
        for i, ch in enumerate(chars):
            g = Image.new("L", (cell_w, cell_h), 0)
            ImageDraw.Draw(g).text((cell_w // 2, cell_h // 2), ch, font=font, fill=255, anchor="mm")
            atlas[i] = np.asarray(g, np.float32) / 255.0
        _GLYPHS[key] = (atlas, len(chars))
    return _GLYPHS[key]


def _code(t: float, w: int, h: int, p: Pal) -> np.ndarray:
    u = h / 384
    cw, ch = max(8, int(22 * u)), max(12, int(30 * u))
    cols, rows = w // cw + 1, h // ch + 2
    atlas, nch = _glyph_atlas(cw, ch)
    im = np.empty((rows * ch, cols * cw, 3), np.float32)
    im[:] = np.array(p.base, np.float32)
    drift = t * 1.5  # the whole sheet slides down 1.5 cells/s (15 per loop: seamless, never the same 1 s later)
    shift_rows, frac = int(math.floor(drift)), drift - math.floor(drift)
    for c in range(cols):
        laps = 2 + int(_rnd(c) * 4)  # whole passes per loop -> seamless
        trail = 6 + int(_rnd(c + 99) * 8)
        head = ((t / LOOP) * laps + _rnd(c + 7)) % 1.0 * (rows + trail)
        for r in range(rows):
            d = head - r
            if 0 <= d < trail:
                k = 1.0 - d / trail
                col = np.array(p.ac if d < 1 else _mix(p.t2, p.fg, k), np.float32)
            else:
                k = 0.0
                col = np.array(p.t2, np.float32)
            rg = (r - shift_rows) % 15  # glyph identity travels with the sheet (15 rows per loop)
            gi = int(_rnd(c * 31 + rg * 7 + (math.floor(t * 4) % 40 if k > 0 else 0)) * nch)
            a = atlas[gi][..., None]
            cell = im[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
            cell[:] = cell * (1 - a) + col * a
    y0 = ch - int(frac * ch)
    return np.ascontiguousarray(im[y0:y0 + h, :w, ::-1]).astype(np.uint8)


def _runner(t: float, w: int, h: int, p: Pal) -> np.ndarray:
    im = np.empty((h, w, 3), np.uint8)
    im[:] = p.bgr(p.t1)
    u = h / 384
    # sky bands moving (clouds as flat bars)
    for k in range(6):
        y = int(h * (0.06 + 0.07 * k))
        bw = int((220 + 180 * _rnd(k)) * u)
        per = w + bw
        x = int(w - ((t / LOOP) * per * (1 + k % 2) + _rnd(k + 3) * per) % per)
        cv2.rectangle(im, (x, y), (x + bw, y + int(14 * u)), p.bgr(p.t2), -1)
    # far and near buildings: a strip exactly w wide (widths normalised), drawn twice, integer laps per loop
    for layer, (lap, col, hmin, hmax, bw0) in enumerate(((3, p.t2, 0.25, 0.55, 110), (8, p.t3, 0.15, 0.40, 160))):
        raw = [(bw0 + 60 * _rnd(i + layer * 50)) * u for i in range(64)]
        n = max(1, int(w / (sum(raw) / len(raw))))
        widths = [r * w / sum(raw[:n]) for r in raw[:n]]
        off = ((t / LOOP) * lap % 1.0) * w
        for rep in (0, w):
            x = rep - off
            for i, bwf in enumerate(widths):
                bw = int(bwf)
                bh = int(h * (hmin + (hmax - hmin) * _rnd(i * 3 + layer)))
                xx = int(x)
                if xx < w and xx + bw > 0:
                    cv2.rectangle(im, (xx, int(h * 0.82) - bh), (xx + bw - int(6 * u), int(h * 0.82)), p.bgr(col), -1)
                    for wy in range(int(h * 0.82) - bh + int(14 * u), int(h * 0.82) - int(10 * u), int(26 * u)):
                        cv2.rectangle(im, (xx + int(10 * u), wy), (xx + bw - int(18 * u), wy + int(8 * u)), p.bgr(p.t1), -1)
                x += bwf
    ground = int(h * 0.82)
    cv2.rectangle(im, (0, ground), (w, h), p.bgr(p.t2), -1)
    tile = int(60 * u)
    off = int((t / LOOP) * tile * 125) % tile  # 12.5 tiles/s
    for x in range(-tile, w + tile, tile):
        cv2.rectangle(im, (x - off, ground + int(10 * u)), (x - off + tile // 2, h), p.bgr(p.t3), -1)
    # crates every 2.5 s, the hero jumps over them
    speed = w / 2.5
    for j in range(4):
        cx = int(w * 0.75 - ((t - j * 2.5) % LOOP) * speed) + int(w * 0.55)
        if -200 < cx < w + 200:
            s = int(70 * u)
            cv2.rectangle(im, (cx - s // 2, ground - s), (cx + s // 2, ground), p.bgr(p.ac), -1)
            cv2.line(im, (cx - s // 2, ground - s), (cx + s // 2, ground), p.bgr(p.bg), max(2, int(4 * u)))
    hx = int(w * 0.28)
    phase = (t % 2.5) / 2.5
    dj = min(phase, 1 - phase)  # a crate reaches the hero at phase 0: the jump is centred there
    jump = math.cos(dj / 0.16 * math.pi / 2) if dj < 0.16 else 0.0
    H = int(h * 0.70)  # BIG hero
    feet = ground - int(jump * h * 0.25)
    step = math.sin(t * 2 * math.pi * 3)
    body = (hx - H // 7, feet - int(H * 0.72), hx + H // 7, feet - int(H * 0.30))
    cv2.rectangle(im, body[:2], body[2:], p.bgr(p.fg), -1)
    cv2.circle(im, (hx, feet - int(H * 0.84)), int(H * 0.13), p.bgr(p.fg), -1)
    cv2.rectangle(im, (hx - H // 7, feet - int(H * 0.62)), (hx + H // 7, feet - int(H * 0.55)), p.bgr(p.ac), -1)
    lw = max(6, int(H * 0.09))
    for sgn in (1, -1):
        kx = hx + int(sgn * step * H * 0.18)
        cv2.line(im, (hx, feet - int(H * 0.32)), (kx, feet), p.bgr(p.fg), lw)
        ax = hx - int(sgn * step * H * 0.2)
        cv2.line(im, (hx, feet - int(H * 0.66)), (ax, feet - int(H * 0.42)), p.bgr(p.fg), lw)
    return im


DRAW = {"race": _race, "spin": _spin, "code": _code, "runner": _runner}


def frames(kind: str, w: int, h: int, fps: int, palette: tuple[str, str, str], seconds: float = LOOP):
    if kind not in DRAW:
        raise ShortsError(f"unknown loop '{kind}', use one of {', '.join(KINDS)}")
    p = Pal(*palette)
    n = int(round(seconds * fps))
    for i in range(n):
        yield DRAW[kind]((i / fps) % LOOP, w, h, p)


def make_loop(kind: str, w: int, h: int, fps: int, palette: tuple[str, str, str]) -> Path:
    """Encode one 10 s loop (BGR frames) to mp4, cached by kind/size/fps/palette/version."""
    key = hashlib.sha1(f"{VERSION}|{kind}|{w}x{h}|{fps}|{'|'.join(palette)}".encode()).hexdigest()[:16]
    out = cache_dir("panels") / f"{kind}-{w}x{h}-{fps}-{key}.mp4"
    if out.exists() and out.stat().st_size > 1000:
        return out
    tmp = out.with_suffix(".tmp.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(tmp)]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert pr.stdin
    for f in frames(kind, w, h, fps, palette):
        pr.stdin.write(f.tobytes())
    pr.stdin.close()
    if pr.wait():
        raise ShortsError(f"ffmpeg failed for loop {kind}")
    tmp.replace(out)
    return out


# ---------------------------------------------------------------- measurement (used by tests and QA)

def change_per_second(gray: list[np.ndarray], times: list[float], delta: int = CHANGE_DELTA) -> dict:
    """For every sample t, share of pixels whose luma differs by > delta from the sample at t + 1 s."""
    shares = []
    j = 0
    for i, t in enumerate(times):
        while j < len(times) and times[j] < t + 1.0 - 1e-6:
            j += 1
        if j >= len(times):
            break
        d = np.abs(gray[i].astype(np.int16) - gray[j].astype(np.int16)) > delta
        shares.append(float(d.mean()))
    if not shares:
        return {"min": 0.0, "median": 0.0, "n": 0}
    return {"min": round(min(shares), 3), "median": round(float(np.median(shares)), 3), "n": len(shares)}


def dark_void(gray: np.ndarray, block: int = 8, dark: float = 32.0, flat: float = 6.0) -> float:
    """Largest connected area of dark flat blocks, as a share of the panel."""
    h, w = gray.shape
    hb, wb = h // block, w // block
    if hb == 0 or wb == 0:
        return 0.0
    g = gray[:hb * block, :wb * block].astype(np.float32).reshape(hb, block, wb, block)
    m = (g.mean(axis=(1, 3)) < dark) & (g.std(axis=(1, 3)) < flat)
    n, _, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 4)
    return float(st[1:, cv2.CC_STAT_AREA].max() / m.size) if n > 1 else 0.0


def measure_frames(rgb_frames: list[np.ndarray], times: list[float]) -> dict:
    gray = [cv2.cvtColor(f, cv2.COLOR_RGB2GRAY) for f in rgb_frames]
    ch = change_per_second(gray, times)
    void = max((dark_void(g) for g in gray[:: max(1, len(gray) // 10)]), default=0.0)
    return {"change_min": ch["min"], "change_median": ch["median"], "dark_void": round(void, 3),
            "ok": ch["min"] >= MIN_CHANGE and void <= MAX_DARK_VOID}


def measure_file(path: Path | str, w: int, h: int, fps: float = 5.0, seconds: float = LOOP) -> dict:
    from .engine.clips import read_frames

    fr, ts = [], []
    for i, f in enumerate(read_frames(path, w, h, fps=fps, duration=seconds)):
        fr.append(f)
        ts.append(i / fps)
    return measure_frames(fr, ts)
