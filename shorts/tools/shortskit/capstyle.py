"""Caption styles for `stack` (v2.2). Learned from two reference shorts the user sent:

  E0BvqC3MY1E (Рилсодел, "стильные субтитры в CapCut"): heavy geometric font, lowercase, the "scary" outline removed,
      soft black shadow (opacity ~25-50 %, blur ~10), words APPEAR one by one as they are spoken, bigger, raised
      above the bottom (about 60 % of the height).
  VOuZxWAeXgs (@ivl_smm, "трендовые субтитры", top-3): (1) a big heavy wide font for headings + one handwritten
      accent word; (2) accent words on a small label, calm animation (no bouncing); (3) small thin lowercase subtitles
      in the FREE space around the face (beside the head, above it), never over the face.

Styles (`captions.style`):
  clean      default. Montserrat ExtraBold ~100 px, lowercase, white, no outline, two soft shadows, 1-3 words by
             meaning (engine.captions.chunk_words), every word appears on its own start (alpha + 8 % scale, 0.1 s),
             one accent word at most per ~2.5 s in the accent colour (numbers, money, names, *marked* words).
             Placed in the main picture: ~62 % of the height on a full-screen picture, lower part of a smaller panel;
             moved off faces, the ad card and the hook.
  aesthetic  Jost Medium ~46 px, lowercase, white + soft shadow, 2-5 words, placed beside / above the head (the side
             changes per sentence), accent words on a small pale-yellow label with dark text. Calm fade + 10 px rise.
  karaoke    the 2.1 look (caps, black outline, active word yellow), now with real word times.
Hook (`hook.style`): headline (default) = Unbounded Black caps, soft shadow, an optional `*word*` in Great Vibes
script; classic = the 2.1 Montserrat with outline.

Word times (final timeline) come from stack: whisper / `<srt>.words.json` / SRT cues, in that order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import asset

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 288, 1920 - 672
TEXT_TOP = 170          # text may go a bit higher than the card rule when the face is high (still below the icons)

STYLES = {
    "clean": {"font": "Montserrat-ExtraBold.ttf", "size": 100, "min_size": 70, "case": "lower", "max_words": 3,
              "max_w": 920, "lines": 2, "fill": "#FFFFFF", "accent": "#FFD84D", "stroke": 0,
              "shadow": [(12, 0.42, 6), (2.5, 0.38, 2)], "reveal": "word", "pop": 0.08, "placement": "center",
              "line_h": 1.08},
    "aesthetic": {"font": "Jost-Medium.ttf", "size": 46, "min_size": 38, "case": "lower", "max_words": 5,
                  "max_w": 560, "lines": 3, "fill": "#FFFFFF", "accent": None, "label": {"bg": "#F3D77B", "fg": "#141414"},
                  "stroke": 0, "shadow": [(6, 0.55, 2), (1.5, 0.35, 1)], "reveal": "phrase", "pop": 0.0,
                  "placement": "face", "line_h": 1.22},
    "karaoke": {"font": "Montserrat-ExtraBold.ttf", "size": 72, "min_size": 56, "case": "upper", "max_words": 3,
                "max_w": 960, "lines": 1, "fill": "#FFFFFF", "accent": "#FFD84D", "stroke": 7, "shadow": [],
                "reveal": "karaoke", "pop": 0.0, "placement": "center", "line_h": 1.1},
}
ACCENT_RE = re.compile(r"(\d|%|\$|₽|€|тысяч|миллион|миллиард|млн|млрд|рубл|доллар)", re.I)
TRAIL = re.compile(r"[,.;:\u2026\"'»«()\[\]]+$")
LEAD = re.compile(r"^[\"'«(\[]+")
FADE_OUT = 0.08
SMALL_ZONE = 700        # a caption zone lower than this (split-screen panel) gets the compact one-line look
COMPACT = {"size": 86, "min_size": 62}


@lru_cache(maxsize=64)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(asset("fonts") / name), int(size))


def _rgb(h):
    if isinstance(h, (tuple, list)):
        return tuple(int(v) for v in h[:3])
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ words

def display_text(w: str, case: str) -> str:
    t = LEAD.sub("", TRAIL.sub("", w.strip()))
    t = t.replace("*", "")
    if case == "lower":
        t = t.lower()
    elif case == "upper":
        t = t.upper()
    return t


def mark_accents(words: list[dict], explicit: list[str] | None = None, every: float = 2.5) -> None:
    """Sets w['acc'] on at most one word per `every` seconds: *marked*, explicit list, numbers/money, then names."""
    stems = [e.lower().strip("*") for e in (explicit or []) if e.strip()]
    last = -99.0
    for i, w in enumerate(words):
        raw = w["w"]
        core = re.sub(r"\W", "", raw.lower())
        prio = 0
        if "*" in raw:
            prio = 3
        elif stems and any(core.startswith(s[: max(4, len(s) - 2)]) for s in stems):
            prio = 3
        elif ACCENT_RE.search(raw):
            prio = 2
        elif raw[:1].isupper() and i > 0 and not re.search(r"[.!?\u2026]$", words[i - 1]["w"]) and len(core) > 3:
            prio = 1
        w["acc"] = False
        if prio >= 2 or (prio == 1 and w["s"] - last >= every * 1.6):
            if w["s"] - last >= every or prio == 3:
                w["acc"] = True
                last = w["s"]


# ------------------------------------------------------------------ sprites

def text_sprite(text: str, fnt: ImageFont.FreeTypeFont, fill, shadows, stroke: int = 0, label: dict | None = None):
    """RGBA sprite of one word with soft shadows (blur, alpha, dy). Returns (image, ox, oy): the word's own top-left
    inside the sprite, so sprites line up on the text baseline grid."""
    pad = 28 if shadows else 12
    asc, desc = fnt.getmetrics()
    tw = int(np.ceil(fnt.getlength(text))) + stroke * 2
    th = asc + desc + stroke * 2
    lw, lh = tw + pad * 2, th + pad * 2
    ox, oy = pad, pad
    img = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    if label:
        px, py_ = max(8, fnt.size // 4), max(4, fnt.size // 9)
        box = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((ox - px, oy + int(asc * 0.12) - py_, ox + tw + px, oy + asc + desc - int(desc * 0.35) + py_),
                                              radius=max(4, fnt.size // 7), fill=_rgb(label["bg"]) + (255,))
        img.alpha_composite(box)
        ImageDraw.Draw(img).text((ox + stroke, oy + stroke), text, font=fnt, fill=_rgb(label["fg"]) + (255,))
        return img, ox, oy
    for blur, alpha, dy in shadows:
        sh = Image.new("L", (lw, lh), 0)
        ImageDraw.Draw(sh).text((ox + stroke, oy + stroke + dy), text, font=fnt, fill=255, stroke_width=stroke)
        sh = sh.filter(ImageFilter.GaussianBlur(blur))
        layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        layer.putalpha(sh.point(lambda v, a=alpha: int(v * a)))
        img.alpha_composite(layer)
    ImageDraw.Draw(img).text((ox + stroke, oy + stroke), text, font=fnt, fill=_rgb(fill) + (255,),
                             stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    return img, ox, oy


@dataclass
class Placed:
    text: str
    s: float
    e: float
    acc: bool
    x: float = 0.0          # word top-left relative to the block
    y: float = 0.0
    w: float = 0.0


@dataclass
class Chunk:
    words: list[Placed]
    t0: float
    t1: float
    size: int
    bw: int
    bh: int
    align: str = "center"
    x: int = 0               # block top-left on the canvas
    y: int = 0
    pos: str = ""
    sentence: int = 0
    sprites: dict = field(default_factory=dict)


def _layout_lines(words: list[Placed], fnt, max_w: int, max_lines: int, line_h: float, align: str):
    sp = fnt.getlength(" ")
    lines, cur, cur_w = [], [], 0.0
    for w in words:
        ww = fnt.getlength(w.text)
        if cur and cur_w + sp + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append(w)
        w.w = ww
        cur_w = cur_w + (sp if len(cur) > 1 else 0) + ww
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        return None
    widths = [sum(w.w for w in l) + sp * (len(l) - 1) for l in lines]
    bw = int(max(widths)) if widths else 0
    lh = int(fnt.size * line_h)
    for li, (l, lw_) in enumerate(zip(lines, widths)):
        x = 0.0 if align == "left" else (bw - lw_) if align == "right" else (bw - lw_) / 2
        for w in l:
            w.x, w.y = x, li * lh
            x += w.w + sp
    return bw, lh * len(lines)


def layout_chunk(words: list[Placed], st: dict, max_w: int | None = None, align: str = "center"):
    """Biggest size (st.size .. st.min_size) at which the words fit max_w in st.lines lines."""
    max_w = int(max_w or st["max_w"])
    size = int(st["size"])
    while size >= int(st["min_size"]):
        f = font(st["font"], size)
        r = _layout_lines(words, f, max_w, int(st["lines"]), float(st["line_h"]), align)
        if r:
            return size, r[0], r[1]
        size -= 4
    f = font(st["font"], int(st["min_size"]))
    r = _layout_lines(words, f, 10 ** 6, 1, float(st["line_h"]), align)
    return int(st["min_size"]), r[0], r[1]


# ------------------------------------------------------------------ chunks

def build_chunks(words: list[dict], style: str = "clean", cfg: dict | None = None, lang: str = "ru") -> list[Chunk]:
    from .engine.captions import chunk_words
    from .subs import mask_profanity

    cfg = cfg or {}
    st = dict(STYLES[style])
    st.update({k: cfg[k] for k in ("size", "min_size", "font", "max_words", "fill", "accent", "lines", "max_w")
               if cfg.get(k) is not None})
    st["min_size"] = min(int(st["min_size"]), int(st["size"]))
    if cfg.get("words"):
        st["max_words"] = int(cfg["words"])
    ws = []
    for w in words:
        t = w["w"]
        if cfg.get("mask", True):
            t = mask_profanity(t)
        if not display_text(t, "none"):
            continue
        ws.append({"w": t, "s": float(w["s"]), "e": float(w["e"])})
    if not ws:
        return []
    mark_accents(ws, cfg.get("accent_words"))
    fnt = font(st["font"], int(st["size"]))
    sp = fnt.getlength(" ")

    def fits(ch):
        tw = sum(fnt.getlength(display_text(x["w"], st["case"])) for x in ch) + sp * (len(ch) - 1)
        if tw <= st["max_w"]:
            return 1
        return 2 if st["lines"] >= 2 and tw <= st["max_w"] * 1.85 else 0

    groups = chunk_words(ws, lang, int(st["max_words"]), fits)
    out: list[Chunk] = []
    sent = 0
    for gi, g in enumerate(groups):
        placed = [Placed(display_text(x["w"], st["case"]), x["s"], x["e"], bool(x.get("acc"))) for x in g]
        if style != "karaoke":     # one accent per chunk, the strongest (first marked) wins
            seen = False
            for p in placed:
                if p.acc and seen:
                    p.acc = False
                seen |= p.acc
        size, bw, bh = layout_chunk(placed, st)
        nxt = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else None
        t0 = max(0.0, g[0]["s"] - 0.04)
        t1 = g[-1]["e"] + 0.45
        if nxt is not None:
            t1 = min(t1, nxt - 0.06)
        t1 = max(t1, g[-1]["e"] + 0.12, t0 + 0.45)
        if nxt is not None:
            t1 = min(t1, max(0.0, nxt - 0.04))      # never overlaps the next chunk (it shows 40 ms before its word)
        out.append(Chunk(placed, t0, t1, size, bw, bh, sentence=sent))
        if re.search(r"[.!?\u2026]$", g[-1]["w"]) or (nxt is not None and nxt - g[-1]["e"] > 0.7):
            sent += 1
    return out


# ------------------------------------------------------------------ placement

def _ov(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def _core(r):
    """The part of a face box text must never touch: brows, eyes, nose, mouth (YuNet box: brow line .. chin).
    The chin edge and the hair may carry text on a close-up (that is where editors put it)."""
    w, h = r[2] - r[0], r[3] - r[1]
    return (r[0] + 0.06 * w, r[1] - 0.04 * h, r[2] - 0.06 * w, r[1] + 0.90 * h)


class Placer:
    """Finds a block position per chunk. zone = (x0, y0, x1, y1) where text may go (main picture inside the safe zone);
    faces(t0, t1) -> face rects (canvas px, x0 y0 x1 y1); obstacles = [(rect, t0, t1)] (ad card, hook);
    extra = fallback zones (the seam over the bottom of the top panel) used only when the main zone has no free place.
    A block never leaves its zone if any free place exists; when a block cannot get a free place at its size it is
    re-laid out smaller in one line (st given) before anything is allowed to touch a face or the card."""

    def __init__(self, zone, faces, obstacles, pref_cy: float | None = None, extra=None):
        self.zone, self.faces, self.obstacles = zone, faces, obstacles
        self.extra = [tuple(z) for z in (extra or []) if z[3] - z[1] >= 60 and z[2] - z[0] >= 300]
        z0, z1 = zone[1], zone[3]
        big = (z1 - z0) > 900
        self.pref_cy = pref_cy if pref_cy is not None else (0.62 * H if big else z0 + (z1 - z0) * 0.80)

    @staticmethod
    def _out(r, z) -> float:
        return max(0, z[0] - r[0]) + max(0, r[2] - z[2]) + max(0, z[1] - r[1]) + max(0, r[3] - z[3])

    def _blocked(self, r, t0, t1, fs) -> float:
        bad = sum(_ov(r, _core(f)) for f in fs)
        bad += sum(_ov(r, o) * 3 for o, a, b in self.obstacles if a < t1 and b > t0)
        out = min(self._out(r, z) for z in [self.zone] + self.extra)
        return bad + out * 2000

    def _cands(self, bh: float, prev: Chunk | None, fs, z) -> list[float]:
        def clamp(cy):
            lo, hi = z[1] + 6 + bh / 2, z[3] - 6 - bh / 2
            return min(max(cy, lo), hi) if lo <= hi else (z[1] + z[3]) / 2
        raw = []
        if prev is not None and prev.pos == "center":
            raw.append(prev.y + prev.bh / 2)                 # same place as the previous chunk: no jumping
        raw.append(self.pref_cy if z == self.zone else (z[1] + z[3]) / 2)
        if fs:
            cores = [_core(f) for f in fs]
            raw += [max(c[3] for c in cores) + 22 + bh / 2, min(c[1] for c in cores) - 22 - bh / 2]
        raw += [z[3] - 10 - bh / 2, z[1] + 10 + bh / 2]
        out = []
        for c in raw:
            for v in (c, clamp(c)):
                if all(abs(v - o) > 2 for o in out):
                    out.append(v)
        return out

    def _best(self, bw, bh, t0, t1, prev, fs, z):
        x = (W - bw) / 2
        best, best_bad = None, None
        for cy in self._cands(bh, prev, fs, z):
            bad = self._blocked((x, cy - bh / 2, x + bw, cy + bh / 2), t0, t1, fs)
            if bad == 0:
                return cy, 0.0
            if best_bad is None or bad < best_bad:
                best, best_bad = cy, bad
        return best, best_bad

    def _variants(self, ch: Chunk, st: dict | None):
        yield ch.words, ch.size, ch.bw, ch.bh
        if not st:
            return
        width = self.zone[2] - self.zone[0] - 8
        tried = {(ch.size, ch.bh)}
        for size, lines in ((int(ch.size * 0.86), 1), (int(st["min_size"]), 1), (int(st["min_size"]), 2)):
            if size > ch.size:
                continue
            words = [Placed(w.text, w.s, w.e, w.acc) for w in ch.words]
            sz, bw, bh = layout_chunk(words, dict(st, size=size, lines=lines, min_size=min(size, int(st["min_size"]))),
                                      max_w=min(int(st["max_w"]), width))
            if bw > width or (sz, bh) in tried:
                continue
            tried.add((sz, bh))
            yield words, sz, bw, bh

    def center(self, ch: Chunk, prev: Chunk | None, st: dict | None = None):
        fs = self.faces(ch.t0, ch.t1)
        variants = list(self._variants(ch, st))
        best = None                          # (bad, cy, variant)
        for z in [self.zone] + self.extra:
            for v in variants:
                cy, bad = self._best(v[2], v[3], ch.t0, ch.t1, prev, fs, z)
                if best is None or bad < best[0]:
                    best = (bad, cy, v)
                if bad == 0:
                    break
            if best[0] == 0:
                break
        bad, cy, (words, size, bw, bh) = best
        ch.words, ch.size, ch.bw, ch.bh = words, size, bw, bh
        ch.x, ch.y, ch.pos = int(round((W - bw) / 2)), int(round(cy - bh / 2)), "center"

    def face(self, ch: Chunk, prev: Chunk | None, st: dict, k: int):
        fs = self.faces(ch.t0, ch.t1)
        if not fs:
            return self.center(ch, prev, st)
        f = max(fs, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        fx0, fy0, fx1, fy1 = f
        fw, fh = fx1 - fx0, fy1 - fy0
        order = ["left", "above", "right"]
        if prev is not None and prev.sentence == ch.sentence and prev.pos in order:
            order.remove(prev.pos)
            order.insert(0, prev.pos)
        else:
            r = k % 3
            order = order[r:] + order[:r]
        for pos in order + ["below"]:
            if pos == "left":
                avail = fx0 - 0.35 * fw - 48
                align = "right"
            elif pos == "right":
                avail = (W - 48) - (fx1 + 0.35 * fw)
                align = "left"
            else:
                avail = min(st["max_w"] + 260, W - 120)
                align = "center"
            if avail < 220:
                continue
            words = [Placed(w.text, w.s, w.e, w.acc) for w in ch.words]
            size, bw, bh = layout_chunk(words, dict(st, max_w=int(avail)), align=align)
            if bw > avail + 2:
                continue
            if pos == "left":
                x, y = fx0 - 0.35 * fw - bw, fy0 + 0.30 * fh - bh / 2
            elif pos == "right":
                x, y = fx1 + 0.35 * fw, fy0 + 0.30 * fh - bh / 2
            elif pos == "above":
                x, y = min(max(48, (fx0 + fx1) / 2 - bw / 2), W - 48 - bw), fy0 - 0.30 * fh - bh
            else:
                x, y = min(max(48, (fx0 + fx1) / 2 - bw / 2), W - 48 - bw), fy1 + 0.55 * fh
            r = (x, y, x + bw, y + bh)
            if self._blocked(r, ch.t0, ch.t1, fs) == 0:
                ch.words, ch.size, ch.bw, ch.bh, ch.align = words, size, bw, bh, align
                ch.x, ch.y, ch.pos = int(round(x)), int(round(y)), pos
                return
        self.center(ch, prev, st)


# ------------------------------------------------------------------ track

def _ease_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


class CaptionTrack:
    def __init__(self, words: list[dict], cfg: dict, zone, faces, obstacles, lang: str = "ru", extra=None):
        self.style = cfg.get("style", "clean")
        if self.style not in STYLES:
            raise ValueError(f"captions.style '{self.style}': use one of {', '.join(STYLES)}")
        base = STYLES[self.style]
        cfg = dict(cfg)
        self.compact = False
        if (base["placement"] == "center" and zone[3] - zone[1] < SMALL_ZONE and cfg.get("size") is None
                and cfg.get("lines") is None):
            # a small panel (split screen): one line, a bit smaller, so a chunk never covers half of the face
            cfg.update(size=min(int(base["size"]), COMPACT["size"]), lines=1, min_size=COMPACT["min_size"])
            self.compact = True
        self.st = dict(base)
        self.st.update({k: cfg[k] for k in ("size", "min_size", "font", "fill", "accent", "lines", "max_w")
                        if cfg.get(k) is not None})
        self.st["min_size"] = min(int(self.st["min_size"]), int(self.st["size"]))
        if self.style == "karaoke" and cfg.get("accent"):
            self.st["accent"] = cfg["accent"]
        self.chunks = build_chunks(words, self.style, cfg, lang)
        pref = None
        if cfg.get("y") is not None:
            pref = float(cfg["y"]) + self.st["size"] * 0.75
        self.placer = Placer(zone, faces, obstacles, pref, extra)
        prev = None
        for k, ch in enumerate(self.chunks):
            if self.st["placement"] == "face" and cfg.get("placement", "auto") != "center":
                self.placer.face(ch, prev, self.st, ch.sentence)
            else:
                self.placer.center(ch, prev, self.st)
            prev = ch
        self._i = 0

    def rects(self) -> list[tuple[float, float, list[int]]]:
        return [(c.t0, c.t1, [c.x, c.y, c.bw, c.bh]) for c in self.chunks]

    def _sprite(self, ch: Chunk, i: int, active: bool = False):
        key = (i, active)
        if key not in ch.sprites:
            w = ch.words[i]
            fnt = font(self.st["font"], ch.size)
            if w.acc and self.st.get("label"):
                ch.sprites[key] = text_sprite(w.text, fnt, self.st["fill"], [], 0, self.st["label"])
            else:
                col = self.st["fill"]
                if self.style == "karaoke":
                    col = self.st["accent"] if active else self.st["fill"]
                elif w.acc and self.st.get("accent"):
                    col = self.st["accent"]
                ch.sprites[key] = text_sprite(w.text, fnt, col, self.st["shadow"], int(self.st["stroke"]))
        return ch.sprites[key]

    def _recentre(self, ch: Chunk, t: float) -> float:
        """Words appear one by one: the visible first line stays centred and slides smoothly (0.1 s) as it grows,
        instead of a lone first word stuck at the left edge of the future line."""
        first = [w for w in ch.words if w.y == ch.words[0].y]
        full = first[-1].x + first[-1].w - first[0].x

        def vis_w(tt):
            seen = [w for w in first if tt >= w.s - 0.03]
            return (seen[-1].x + seen[-1].w - first[0].x) if seen else first[0].w

        starts = [w.s - 0.03 for w in first if w.s - 0.03 <= t]
        if not starts:
            return (full - first[0].w) / 2
        t_new = starts[-1]
        now = vis_w(t)
        before = vis_w(t_new - 1e-3) if len(starts) > 1 else now
        k = _ease_out((t - t_new) / 0.10)
        return (full - (before + (now - before) * k)) / 2

    def active(self, t: float) -> Chunk | None:
        """The latest chunk that has started (a new chunk replaces the fading one at once: no late first word)."""
        cur = None
        for ch in self.chunks:
            if ch.t0 > t:
                break
            cur = ch
        return cur if cur is not None and t < cur.t1 + FADE_OUT else None

    def draw(self, canvas: np.ndarray, t: float, blend) -> None:
        ch = self.active(t)
        if ch is None:
            return
        out_k = 1.0 if t < ch.t1 else max(0.0, 1 - (t - ch.t1) / FADE_OUT)
        rise = 0.0
        if self.st["reveal"] == "phrase":
            k = _ease_out((t - ch.t0) / 0.22)
            rise = (1 - k) * 10
            out_k *= k
        act = 0
        for i, w in enumerate(ch.words):
            if t >= w.s - 0.03:
                act = i
        shift = 0.0
        if self.st["reveal"] == "word" and ch.align == "center":
            shift = self._recentre(ch, t)
        for i, w in enumerate(ch.words):
            if self.st["reveal"] == "word" and t < w.s - 0.03:
                continue
            spr, ox, oy = self._sprite(ch, i, active=(i == act))
            a = out_k
            sc = 1.0
            if self.st["reveal"] == "word":
                age = t - (w.s - 0.03)
                a *= min(1.0, age / 0.06) if age >= 0 else 0.0
                sc = 1.0 - self.st["pop"] * (1 - _ease_out(age / 0.10))
            elif w.acc and self.st.get("label"):
                age = t - (w.s - 0.03)            # the label is there with the phrase, a small pop when it is said
                sc = 1.0 + 0.07 * np.sin(np.pi * min(1.0, age / 0.16)) if 0 <= age <= 0.16 else 1.0
            if a <= 0.01:
                continue
            x = ch.x + w.x - ox + (shift if w.y == ch.words[0].y else 0.0)
            y = ch.y + w.y - oy + rise
            img = spr
            if sc < 0.999:
                nw, nh = max(1, int(spr.width * sc)), max(1, int(spr.height * sc))
                img = spr.resize((nw, nh), Image.BILINEAR)
                x += (spr.width - nw) / 2
                y += (spr.height - nh) / 2
            blend(canvas, img, int(round(x)), int(round(y)), a)


# ------------------------------------------------------------------ headline (hook)

def headline_layer(text: str, size: int = 96, accent=None, max_w: int = 940, style: str = "headline") -> Image.Image:
    """Hook text. headline: Unbounded Black caps + optional *script* word (Great Vibes) under the last line, soft shadow.
    classic: the 2.1 Montserrat with a black outline."""
    if style == "classic":
        return _classic_hook(text, size)
    script = re.findall(r"\*([^*]+)\*", text)
    plain = re.sub(r"(\d)\s+(?=\d{3}\b)", "\\1\u00a0", re.sub(r"\*[^*]+\*", " ", text))   # "100 000" never splits
    main = plain.split(" ")
    main = [m for m in main if m.strip()]
    size = int(size)
    while size > 54:
        f = font("Unbounded-Black.ttf", size)
        lines, cur = [], ""
        for w in [x.upper() for x in main]:
            t = (cur + " " + w).strip()
            if f.getlength(t) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        if len(lines) <= 3 and all(f.getlength(l) <= max_w for l in lines):
            break
        size -= 6
    f = font("Unbounded-Black.ttf", size)
    lh = int(size * 1.08)
    sf = font("GreatVibes-Regular.ttf", int(size * 1.15)) if script else None
    s_h = int(size * 1.05) if script else 0
    lay = Image.new("RGBA", (W, lh * max(1, len(lines)) + s_h + 70), (0, 0, 0, 0))
    txt = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    y = 20
    for l in lines:
        d.text((W / 2, y), l, font=f, fill=(255, 255, 255, 255), anchor="mt")
        y += lh
    if script:
        col = _rgb(accent) if accent else (255, 255, 255)
        last_w = f.getlength(lines[-1]) if lines else 0
        d.text((W / 2 + last_w * 0.18, y - int(size * 0.32)), " ".join(script), font=sf, fill=col + (255,), anchor="mt")
    a = txt.split()[3]
    for blur, alpha, dy in ((14, 0.45, 6), (3, 0.35, 2)):
        sh = Image.new("RGBA", lay.size, (0, 0, 0, 0))
        m = Image.new("L", lay.size, 0)
        m.paste(a.filter(ImageFilter.GaussianBlur(blur)).point(lambda v, k=alpha: int(v * k)), (0, dy))
        sh.putalpha(m)
        lay.alpha_composite(sh)
    lay.alpha_composite(txt)
    return lay


def _classic_hook(text: str, size: int) -> Image.Image:
    f = font("Montserrat-ExtraBold.ttf", size)
    words, lines, cur = text.replace("*", "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= W - 160 or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    lay = Image.new("RGBA", (W, int(size * 1.25 * len(lines)) + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = 6
    for l in lines:
        d.text((W / 2, y), l, font=f, fill=(255, 255, 255, 255), anchor="mt", stroke_width=9, stroke_fill=(0, 0, 0, 255))
        y += int(size * 1.25)
    return lay
