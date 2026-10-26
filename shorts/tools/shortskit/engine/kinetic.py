"""Kinetic typography over the picture: captions.style = "kinetic" (schema 1.3; research 14 section 5, 16).

Instead of 2-3 word karaoke at the bottom, the phrase is built on screen word by word as it is spoken
(the "typographic stack" of monologue / philosophy shorts):
  * a block = one phrase: ends on a sentence end, a pause >= 0.35 s, a scene cut or max_words (8, hard 12);
  * 1-4 words per line, every line stretched to the same strip width (stacked type), so short lines get
    big letters and long ones small; a stop word never ends a line;
  * weights: stop words 0.6 (body font, smaller), normal 1.0, accent 1.8; the accent word (number,
    the longest content word, or a word from captions.kinetic.accent) stands on its own line in the
    accent colour;
  * every word is its own overlay: it pops in on its spoken start, the whole block leaves together.
Limits kept in code (QA checks them again): <= 4 lines, <= 12 words, >= 56 px, block <= 45% of the frame
height, every word on screen >= 0.3 s, 6 px black outline (reads on any picture: no plate, no glow).
The block never covers a CTA, title bar, fact plate or label that is on screen at the same time:
it moves into the largest free part of the safe zone and shrinks if it has to.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from ..util import fit_contrast, fix_dashes, hex_to_rgb
from .brand import CAPTION_OUTLINE, Brand
from .captions import FUNCTION_WORDS, MEDIUM, NUM_WORDS, STRONG, core
from .graphics import Sprite
from .layout import H, Layout, Rect

MIN_PX = 56
MAX_LINES = 4
MAX_WORDS_HARD = 12
DEFAULT_WORDS = 8
MAX_H_SHARE = 0.45
MIN_WORD_S = 0.3
PAUSE_S = 0.35
TAIL_S = 0.45      # block stays after its last word
STROKE = 6
WEIGHTS = {"stop": 0.6, "normal": 1.0, "accent": 1.8}
MAX_PX = {"stop": 104, "normal": 176, "accent": 264}
LINE_GAP = 0.20    # gap between lines, share of the bigger cap height
POP_IN, FADE_OUT = 0.15, 0.10
EARLY_MAX = 0.12   # s a word may appear before it is spoken (to get its 0.3 s); QA sync tolerance is 0.15 s

STOP_EXTRA = {
    "ru": set("я ты он она оно мы вы они мне тебе ему ей нам вам им меня тебя нас вас это так там тут уже ещё "
              "еще вот лишь только даже когда если чем то есть был была было были будет".split()),
    "en": set("i you he she it we they me him us them is are was were be been am do does did have has had "
              "will would can could just very".split()),
}
# a negation flips the meaning: it is never drawn small ("НЕ делай так" must read as НЕ)
NEGATIONS = {"ru": {"не", "ни", "нет", "нельзя", "никогда", "без"},
             "en": {"not", "no", "never", "don't", "dont", "can't", "cant", "won't", "without"}}


def stop_words(lang: str) -> set[str]:
    l2 = (lang or "ru")[:2]
    return (FUNCTION_WORDS.get(l2, set()) | STOP_EXTRA.get(l2, set())) - NEGATIONS.get(l2, set())


@lru_cache(maxsize=256)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


@dataclass
class KWord:
    w: str
    s: float
    e: float
    kind: str = "normal"        # stop | normal | accent
    size: int = 0
    line: int = 0
    box: Rect | None = None
    t0: float = 0.0             # on screen from
    sprite: Sprite | None = None


@dataclass
class KBlock:
    words: list[KWord]
    lines: list[list[int]] = field(default_factory=list)
    start: float = 0.0
    end: float = 0.0
    box: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.w for w in self.words)

    @property
    def min_size(self) -> int:
        return min((w.size for w in self.words), default=0)

    def to_chunk(self) -> dict:
        return {"text": self.text, "start": round(self.start, 3), "end": round(self.end, 3), "box": self.box,
                "size": self.min_size, "lines": len(self.lines), "overflow": False, "style": "kinetic",
                "words": [{"w": w.w, "s": w.s, "e": w.e, "t0": round(w.t0, 3), "kind": w.kind, "size": w.size,
                           "box": w.box.as_list() if w.box else None} for w in self.words]}


# ------------------------------------------------------------------ 1. phrases

def split_blocks(words: list[dict], max_words: int = DEFAULT_WORDS, pause: float = PAUSE_S) -> list[list[dict]]:
    max_words = max(2, min(MAX_WORDS_HARD, int(max_words)))
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end = nxt is None
        if not end:
            gap = nxt["s"] - w["e"]
            if STRONG.search(w["w"]) or gap >= pause or len(cur) >= max_words:
                end = True
            elif w.get("scene") is not None and nxt.get("scene") != w.get("scene"):
                end = True
            elif MEDIUM.search(w["w"]) and len(cur) >= max(4, max_words - 3):
                end = True
        if end:
            out.append(cur)
            cur = []
    return out


def pick_accents(block: list[dict], lang: str, explicit: list[str], auto: bool) -> set[int]:
    stops = stop_words(lang)
    want = {core(x) for x in explicit or [] if core(x)}
    acc = {i for i, w in enumerate(block) if core(w["w"]) in want}
    if acc or not auto or len(block) < 3:
        return acc
    nums = [i for i, w in enumerate(block) if NUM_WORDS.match(core(w["w"])) or re.search(r"\d", w["w"])]
    if nums:
        return {nums[0]}
    content = [i for i, w in enumerate(block) if core(w["w"]) not in stops and len(core(w["w"])) >= 5]
    if not content:
        return set()
    return {max(content, key=lambda i: (len(core(block[i]["w"])), -i))}


# ------------------------------------------------------------------ 2. lines and sizes

class _Measure:
    def __init__(self, brand: Brand, upper: bool):
        self.display = str(brand.display.path)
        self.body = str(brand.body.path)
        self.upper = upper

    def text(self, w: KWord) -> str:
        t = fix_dashes(w.w)
        return t.upper() if self.upper else t

    def font(self, w: KWord, size: int) -> ImageFont.FreeTypeFont:
        return _font(self.body if w.kind == "stop" else self.display, max(8, int(size)))

    def width(self, w: KWord, size: int) -> float:
        return self.font(w, size).getlength(self.text(w))

    def space(self, size: int) -> float:
        return _font(self.display, max(8, int(size))).getlength(" ")

    def cap(self, w: KWord, size: int) -> int:
        bb = self.font(w, size).getbbox("H", anchor="ls")
        return -bb[1]


def _gap(m: "_Measure", a: int, b: int) -> float:
    """Space between two words: from the smaller one, so 'ЗА 3' does not get a 262 px hole."""
    return m.space(min(a, b)) * 0.9


def _line_width(ws: list[KWord], sizes: list[int], m: "_Measure") -> float:
    return sum(m.width(w, s) for w, s in zip(ws, sizes)) + sum(_gap(m, a, b) for a, b in zip(sizes, sizes[1:]))


def _line_sizes(ws: list[KWord], m: _Measure, strip_w: float) -> tuple[list[int], float]:
    """Sizes for one line stretched to strip_w (capped per weight, >= MIN_PX). Returns (sizes, width).
    Words pinned at MIN_PX make the line wider than planned: the others shrink until it fits again."""
    unit = 100
    base = [unit * WEIGHTS[w.kind] for w in ws]
    scale = strip_w / max(1.0, _line_width(ws, [int(b) for b in base], m))
    scale = min(scale, min(MAX_PX[w.kind] / b for w, b in zip(ws, base)))
    sizes = [max(MIN_PX, int(b * scale)) for b in base]
    width = _line_width(ws, sizes, m)
    for _ in range(40):
        if width <= strip_w + 0.5 or all(s <= MIN_PX for s in sizes):
            break
        scale *= 0.97
        sizes = [max(MIN_PX, int(b * scale)) for b in base]
        width = _line_width(ws, sizes, m)
    return sizes, width


def plan_lines(ws: list[KWord], m: _Measure, strip_w: float, lang: str, max_lines: int = MAX_LINES) -> list[list[int]] | None:
    """DP over line breaks: balanced 1-3 word lines, accent alone, no stop word at a line end."""
    n = len(ws)
    INF = float("inf")
    best = [[INF] * (max_lines + 1) for _ in range(n + 1)]
    prev = [[-1] * (max_lines + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(n):
        for L in range(max_lines):
            if best[i][L] == INF:
                continue
            for j in range(i + 1, min(n, i + 4) + 1):
                line = ws[i:j]
                sizes, width = _line_sizes(line, m, strip_w)
                if width > strip_w + 1 and len(line) > 1:
                    break
                c = {1: 0.8, 2: 0.0, 3: 0.35, 4: 1.2}[len(line)]
                kinds = [w.kind for w in line]
                # stacked type is about big letters: small content words and a small accent cost extra
                content = [sz for w, sz in zip(line, sizes) if w.kind != "stop"]
                if content:
                    c += 2.0 * max(0.0, (96 - min(content)) / 40)
                for w, sz in zip(line, sizes):
                    if w.kind == "accent":
                        c += 2.0 * max(0.0, (128 - sz) / 40)
                if len(line) == 1 and kinds[0] == "accent":
                    c -= 0.8
                if "accent" in kinds and sum(1 for k in kinds if k != "stop") > 1:
                    c += 3.0
                if j < n and line[-1].kind == "stop" and not (MEDIUM.search(line[-1].w) or STRONG.search(line[-1].w)):
                    c += 20.0
                if all(k == "stop" for k in kinds):
                    c += 4.0
                for w in line[:-1]:
                    if STRONG.search(w.w):
                        c += 6.0
                    elif MEDIUM.search(w.w):
                        c += 2.0
                if MEDIUM.search(line[-1].w) or STRONG.search(line[-1].w):
                    c -= 0.8
                if best[i][L] + c < best[j][L + 1]:
                    best[j][L + 1] = best[i][L] + c
                    prev[j][L + 1] = i
    Ls = [L for L in range(1, max_lines + 1) if best[n][L] < INF]
    if not Ls:
        return None
    L = min(Ls, key=lambda x: best[n][x] + 0.15 * x)
    out, j = [], n
    while L > 0:
        i = prev[j][L]
        out.append(list(range(i, j)))
        j, L = i, L - 1
    return out[::-1]


# ------------------------------------------------------------------ 3. where on screen

def free_band(lay: Layout, obstacles: list[tuple[float, float, Rect]], t0: float, t1: float,
              prefer: str) -> tuple[int, int]:
    """Largest vertical band of the safe zone free from obstacles visible during [t0, t1)."""
    s = lay.safe.rect
    top, bot = s.y + 16, s.y1 - 16
    busy = sorted((max(top, r.y - 24), min(bot, r.y1 + 24)) for a, b, r in obstacles if a < t1 and b > t0)
    free, y = [], top
    for a, b in busy:
        if a > y:
            free.append((y, a))
        y = max(y, b)
    if y < bot:
        free.append((y, bot))
    if not free:
        return top, bot
    if prefer == "upper":
        big = [f for f in free if f[1] - f[0] >= 0.6 * max(g[1] - g[0] for g in free)]
        return big[0]
    return max(free, key=lambda f: (f[1] - f[0], -abs((f[0] + f[1]) / 2 - H / 2)))


# ------------------------------------------------------------------ 4. drawing

def _word_sprite(w: KWord, m: _Measure, fill: str, accent: str, x: float, baseline: float) -> Sprite:
    f = m.font(w, w.size)
    t = m.text(w)
    bb = f.getbbox(t, anchor="ls", stroke_width=STROKE)
    img = Image.new("RGBA", (max(1, bb[2] - bb[0]), max(1, bb[3] - bb[1])), (0, 0, 0, 0))
    col = accent if w.kind == "accent" else fill
    ImageDraw.Draw(img).text((-bb[0], -bb[1]), t, font=f, fill=hex_to_rgb(col) + (255,), anchor="ls",
                             stroke_width=STROKE, stroke_fill=hex_to_rgb(CAPTION_OUTLINE) + (255,))
    box = Rect(int(round(x + bb[0])), int(round(baseline + bb[1])), img.width, img.height)
    pairs = [(col, CAPTION_OUTLINE, 7.0)]
    return Sprite("kinetic", img, box, t, w.size, pairs)


def build(words: list[dict], brand: Brand, lay: Layout, cfg: dict, lang: str,
          obstacles: list[tuple[float, float, Rect]] | None = None, total: float | None = None) -> list[KBlock]:
    kc = dict(cfg.get("kinetic") or {})
    upper = cfg.get("upper", brand.upper)
    m = _Measure(brand, upper)
    stops = stop_words(lang)
    strip = lay.label_box  # widest strip symmetric around x = 540 inside the safe zone
    strip_w = strip.w - 2 * STROKE - 8
    cx = strip.x + strip.w / 2
    max_lines = max(1, min(MAX_LINES, int(kc.get("max_lines", MAX_LINES))))
    prefer = kc.get("box", "center")
    fill = brand.caption_fill
    accent = fit_contrast(brand.accent, CAPTION_OUTLINE, 7.0)
    obstacles = obstacles or []
    words = [w for w in words if w["w"].strip()]
    groups = split_blocks(words, int(kc.get("max_words", DEFAULT_WORDS)), float(kc.get("pause", PAUSE_S)))
    out: list[KBlock] = []

    def make(group: list[dict]) -> list[KBlock]:
        acc = pick_accents(group, lang, kc.get("accent") or [], bool(kc.get("auto_accent", True)))
        ws = []
        for i, w in enumerate(group):
            kind = "accent" if i in acc else ("stop" if core(w["w"]) in stops else "normal")
            ws.append(KWord(w["w"], float(w["s"]), float(w["e"]), kind))
        lines = plan_lines(ws, m, strip_w, lang, max_lines)
        if lines is None:
            if len(group) == 1:
                lines = [[0]]
            else:
                h = len(group) // 2
                return make(group[:h]) + make(group[h:])
        b = KBlock(ws, lines)
        for li, idx in enumerate(lines):
            sizes, _ = _line_sizes([ws[i] for i in idx], m, strip_w)
            for i, s in zip(idx, sizes):
                ws[i].size, ws[i].line = s, li
        return [b]

    for g in groups:
        out += make(g)

    # timing: block from its first word to the last word + tail (not into the next block); every word >= 0.3 s
    end_all = total if total is not None else (words[-1]["e"] + 1.0 if words else 0.0)
    for bi, b in enumerate(out):
        nxt = out[bi + 1].words[0].s if bi + 1 < len(out) else end_all
        b.start = b.words[0].s
        b.end = min(nxt - 0.02, b.words[-1].e + TAIL_S) if bi + 1 < len(out) else min(end_all, b.words[-1].e + TAIL_S)
        b.end = max(b.end, min(nxt - 0.02, b.words[-1].s + MIN_WORD_S))
        prev_t = b.start
        for w in b.words:
            # a word may come a little early to stay readable, never more than EARLY_MAX (sync tolerance 150 ms)
            w.t0 = max(prev_t, min(w.s, max(b.end - MIN_WORD_S, w.s - EARLY_MAX)))
            prev_t = w.t0
        if b.end - b.words[-1].t0 < MIN_WORD_S - 1e-3:
            b.notes.append(f"'{b.words[-1].w}' is on screen {b.end - b.words[-1].t0:.2f}s (< {MIN_WORD_S}s): speech too fast")

    # geometry: lines stacked, centred on x = 540, block inside the largest free band
    for b in out:
        y_top, y_bot = free_band(lay, obstacles, b.start, b.end, prefer)
        avail = min(y_bot - y_top, int(H * MAX_H_SHARE))
        for _ in range(12):
            caps = [max(m.cap(b.words[i], b.words[i].size) for i in idx) for idx in b.lines]
            gaps = [int(LINE_GAP * max(a, c)) + STROKE * 2 for a, c in zip(caps, caps[1:])]
            height = sum(caps) + sum(gaps) + 2 * STROKE
            if height <= avail:
                break
            k = avail / height
            if all(w.size <= MIN_PX for w in b.words):
                b.notes.append(f"block '{b.text[:30]}' needs {height}px, only {avail}px free")
                break
            for w in b.words:
                w.size = max(MIN_PX, int(w.size * k))
        if prefer == "upper":
            y0 = y_top
        elif prefer == "lower":
            y0 = y_bot - height
        else:
            y0 = min(max(H / 2 - height / 2, y_top), y_bot - height)
        y = y0 + STROKE
        x0s, y0s, x1s, y1s = [], [], [], []
        for li, idx in enumerate(b.lines):
            ws = [b.words[i] for i in idx]
            cap = caps[li]
            baseline = y + cap
            width = _line_width(ws, [w.size for w in ws], m)
            x = cx - width / 2
            for wi, w in enumerate(ws):
                w.sprite = _word_sprite(w, m, fill, accent, x, baseline)
                w.box = w.sprite.box
                x0s.append(w.box.x), y0s.append(w.box.y), x1s.append(w.box.x1), y1s.append(w.box.y1)
                x += m.width(w, w.size) + (_gap(m, w.size, ws[wi + 1].size) if wi + 1 < len(ws) else 0)
            y = baseline + (gaps[li] if li < len(gaps) else 0)
        b.box = [min(x0s), min(y0s), max(x1s), max(y1s)]
    return out


def overlays(blocks: list[KBlock]) -> list[tuple[Sprite, float, float]]:
    return [(w.sprite, w.t0, b.end) for b in blocks for w in b.words if w.sprite is not None]


def report(blocks: list[KBlock]) -> dict:
    return {"blocks": len(blocks), "max_lines": max((len(b.lines) for b in blocks), default=0),
            "max_words": max((len(b.words) for b in blocks), default=0),
            "min_px": min((b.min_size for b in blocks), default=0),
            "max_height_share": round(max(((b.box[3] - b.box[1]) / H for b in blocks if b.box), default=0), 3),
            "min_word_s": round(min((b.end - w.t0 for b in blocks for w in b.words), default=0), 3),
            "accents": [w.w for b in blocks for w in b.words if w.kind == "accent"],
            "notes": [n for b in blocks for n in b.notes]}
