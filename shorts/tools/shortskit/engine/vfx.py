"""Compose-level video effects (schema 1.3). Everything works on the centre picture BEFORE text is drawn,
so captions, plates and CTA stay sharp and still (research 03, error 6: "text must not shake with the cut").

  Letterbox    cinema bars that open on the drop / close at the end / kick on beats (research 14.4)
  Flicker      a short series of frames (A/B shots, exposure, black) with a photosensitivity limiter (14.5)
  LookKeys     colour switch inside the video: bw -> colour on the drop, cut / fade / wipe / radial (14.6)
  Transitions  scene-to-scene moves: whip, zoom, flash_blur, glitch, dip, spin, dissolve, flicker (03, 16)
  Split        second picture inside the video: v2 (top/bottom), h2 (left/right), pip (14.7, 17)

How the transitions are built (what editors do in CapCut/AE with keyframes on both clips): the OUT half
animates the end of clip A, the IN half animates the start of clip B, the cut stays exactly on the beat.
Push-type moves (whip) also need the other clip: the first frame of B (before the cut) and the last frame
of A (after the cut) are held, which is invisible under the motion blur.
Rules from the research kept in code: 70-90% of joins are plain cuts (auto mode), heavy moves never on two
joins in a row, transitions 0.1-0.4 s (never the 0.5-1 s "presentation slide"), <= 3 flashes in any second.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from .. import contract as K
from . import look as LK

# ------------------------------------------------------------------ time and easing

EASE = {
    "linear": lambda u: u,
    "out_cubic": lambda u: 1 - (1 - u) ** 3,
    "in_cubic": lambda u: u ** 3,
    "in_out": lambda u: 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2,
}


def ease(name: str, u: float) -> float:
    u = min(1.0, max(0.0, u))
    return EASE.get(name or "out_cubic", EASE["out_cubic"])(u)


def resolve_t(v, total: float, drop: float | None, default: float = 0.0) -> float | None:
    """Plan time -> video seconds. number >= 0 as is, negative = from the end, "drop" = audio.music.drop_at,
    "end" = video end, "NN%" = share of the length. None if "drop" is asked and there is no drop."""
    if v is None:
        return default
    if isinstance(v, str):
        s = v.strip().lower()
        if s == "drop":
            return None if drop is None else float(drop)
        if s == "end":
            return total
        if s == "start":
            return 0.0
        if s.endswith("%"):
            return total * float(s[:-1]) / 100
        v = float(s)
    v = float(v)
    return max(0.0, total + v) if v < 0 else min(total, v)


# ------------------------------------------------------------------ small image helpers

def dir_blur(img: np.ndarray, length: float, horizontal: bool = True) -> np.ndarray:
    k = int(length) | 1
    if k < 3:
        return img
    return cv2.blur(img, (k, 1) if horizontal else (1, k))


def zoom_at(img: np.ndarray, s: float, cx: float = 0.5, cy: float = 0.5, angle: float = 0.0) -> np.ndarray:
    h, w = img.shape[:2]
    if abs(s - 1) < 1e-3 and abs(angle) < 1e-3:
        return img
    m = cv2.getRotationMatrix2D((w * cx, h * cy), angle, s)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def zoom_blur(img: np.ndarray, s: float, strength: float, n: int = 6) -> np.ndarray:
    """Radial (zoom) blur: average of n copies scaled from s to s*(1+strength) around the centre.
    Done at half size when the blur is strong (it hides the resolution anyway)."""
    if strength < 0.01:
        return zoom_at(img, s)
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    acc = np.zeros(small.shape, np.float32)
    for i in range(n):
        acc += zoom_at(small, s * (1 + strength * i / (n - 1)))
    return cv2.resize((acc / n).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)


def soft_blur(img: np.ndarray, sigma: float) -> np.ndarray:
    if sigma < 0.6:
        return img
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), sigma / 2)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)


def mix(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    if k <= 0:
        return a
    if k >= 1:
        return b
    return cv2.addWeighted(a, 1 - k, b, k, 0)


def to_white(img: np.ndarray, k: float) -> np.ndarray:
    return mix(img, np.full_like(img, 255), k) if k > 0.005 else img


def fit_cover(img: np.ndarray, w: int, h: int, fx: float = 0.5, fy: float = 0.5) -> np.ndarray:
    """Crop to the w:h aspect around (fx, fy), then resize: what 'fill' does in every editor."""
    ih, iw = img.shape[:2]
    if (iw, ih) == (w, h):
        return img
    ar = w / h
    if iw / ih > ar:
        cw, ch = int(round(ih * ar)), ih
    else:
        cw, ch = iw, int(round(iw / ar))
    x0 = int(round((iw - cw) * min(1, max(0, fx))))
    y0 = int(round((ih - ch) * min(1, max(0, fy))))
    crop = img[y0:y0 + ch, x0:x0 + cw]
    inter = cv2.INTER_AREA if cw > w else cv2.INTER_LINEAR
    return cv2.resize(crop, (w, h), interpolation=inter)


def rel_luminance(rgb: np.ndarray) -> np.ndarray:
    """WCAG relative luminance of sRGB pixels (0..1)."""
    c = rgb.astype(np.float32) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


# ------------------------------------------------------------------ letterbox (14.4)

@dataclass
class _Key:
    t: float
    target: float  # bar height, px
    dur: float
    ease: str


class Letterbox:
    """Two black bars over the centre picture. Keys: {t, ratio, dur, ease}; ratio = aspect (w/h) of the visible
    picture (2.39 = cinema slit, 1.0 = square window, "full" = no bars) or {"bars_pct": 12}. Kicks: {t, pulse: px}
    push the bars in by px and back in 0.15 s (beat accents). t: seconds, "drop", negative = from the end."""

    KICK = 0.15

    def __init__(self, spec, cw: int, ch: int, total: float, drop: float | None, fps: int):
        self.cw, self.ch, self.fps = cw, ch, fps
        self.keys: list[_Key] = []
        self.kicks: list[tuple[float, float]] = []
        self.notes: list[str] = []
        if isinstance(spec, dict):
            items = list(spec.get("keys", []))
            for x in spec.get("hits", []):
                items.append({"pulse": spec.get("pulse", 48), **x} if isinstance(x, dict) else {"t": x, "pulse": spec.get("pulse", 48)})
        else:
            items = list(spec or [])
        for it in items:
            t = resolve_t(it.get("t", 0), total, drop)
            if t is None:
                self.notes.append(f"letterbox key at 'drop' skipped: audio.music.drop_at is not set")
                continue
            if "pulse" in it and "ratio" not in it and "bars_pct" not in it:
                self.kicks.append((t, float(it["pulse"])))
                continue
            self.keys.append(_Key(t, self._bars(it), float(it.get("dur", 0.5 if self.keys else 0.0)),
                                  it.get("ease", "out_cubic")))
        self.keys.sort(key=lambda k: k.t)
        if self.keys and self.keys[0].t > 0:
            self.keys.insert(0, _Key(0.0, 0.0, 0.0, "linear"))

    def _bars(self, it: dict) -> float:
        if "bars_pct" in it:
            return self.ch * float(it["bars_pct"]) / 100
        r = it.get("ratio", "full")
        if r in ("full", None, 0):
            return 0.0
        if isinstance(r, str) and ":" in r:
            a, b = r.split(":")
            r = float(a) / float(b)
        vis = self.cw / float(r)
        return max(0.0, (self.ch - vis) / 2)

    def at(self, t: float) -> int:
        if not self.keys and not self.kicks:
            return 0
        v = self.keys[0].target if self.keys else 0.0
        for k in self.keys[1:]:
            if t < k.t:
                break
            u = 1.0 if k.dur <= 0 else (t - k.t) / k.dur
            v = v + (k.target - v) * ease(k.ease, u)
        for tk, px in self.kicks:
            d = t - tk
            if 0 <= d < self.KICK:
                v += px * (1 - d / self.KICK) ** 2
        return int(round(min(v, self.ch / 2 - 8)))

    def apply(self, img: np.ndarray, t: float) -> np.ndarray:
        h = self.at(t)
        if h > 0:
            img = img.copy()  # never paint over a held frame (it is shown again by transitions)
            img[:h] = 0
            img[img.shape[0] - h:] = 0
        return img

    def report(self, total: float) -> dict:
        step = 1 / self.fps
        closed, cur = [], None
        n = int(total * self.fps)
        for i in range(n + 1):
            t = i * step
            c = self.at(t) > max(8, 0.04 * self.ch)
            if c and cur is None:
                cur = t
            if not c and cur is not None:
                closed.append([round(cur, 2), round(t, 2)])
                cur = None
        if cur is not None:
            closed.append([round(cur, 2), round(total, 2)])
        start_closed = closed[0][1] if closed and closed[0][0] == 0 else 0.0
        return {"keys": [{"t": round(k.t, 3), "bars_px": int(k.target), "dur": k.dur} for k in self.keys],
                "kicks": [round(t, 3) for t, _ in self.kicks], "closed": closed,
                "closed_at_start_s": round(start_closed, 2), "max_bar_px": max((int(k.target) for k in self.keys), default=0),
                "notes": self.notes}


# ------------------------------------------------------------------ flicker (14.5)

FLICKER_MAX_S = 0.25     # one series
FLICKER_GAP_S = 1.0      # between series
FLICKER_MAX_SERIES = 4
FLASH_LIMIT = 3          # WCAG 2.3.1: no more than 3 flashes in any 1 s
LEVEL = {"exposure": {"1": 1.6, "0": 0.4}, "black": {"1": 1.0, "0": 0.0}}
PATTERN = {"cut": "AABABB", "exposure": "101101", "black": "101101"}


def pattern_flashes(kind: str, pattern: str) -> int:
    """Flashes (pairs of opposing luminance changes) a pattern makes, normal frames on both sides.
    For 'cut' A/B frames of different shots are counted as potential changes (worst case)."""
    if kind == "cut":
        lv = [1.0] + [1.0 if c == "A" else 0.4 for c in pattern] + [0.4 if pattern and pattern[-1] == "B" else 1.0]
    else:
        lv = [1.0] + [LEVEL[kind].get(c, 1.0) for c in pattern] + [1.0]
    trans, prev_dir = 0, 0
    for a, b in zip(lv, lv[1:]):
        if abs(b - a) < 0.1:
            continue
        d = 1 if b > a else -1
        if d != prev_dir:
            trans += 1
            prev_dir = d
    return trans // 2


@dataclass
class FlickerEvent:
    k0: int           # first frame
    kind: str
    pattern: str
    boundary: int | None = None  # frame index of the scene cut for kind 'cut'


class Flicker:
    def __init__(self, spec: list, total: float, drop: float | None, fps: int, cuts: list[float]):
        self.fps = fps
        self.events: list[FlickerEvent] = []
        self.notes: list[str] = []
        max_len = int(FLICKER_MAX_S * fps + 1e-6)
        last_end = -1e9
        for it in sorted(spec or [], key=lambda x: resolve_t(x.get("t", 0), total, drop) or 0):
            t = resolve_t(it.get("t", 0), total, drop)
            if t is None:
                self.notes.append("flicker at 'drop' skipped: audio.music.drop_at is not set")
                continue
            kind = it.get("kind", "exposure")
            pat = str(it.get("pattern") or PATTERN.get(kind, "101101"))
            boundary = None
            if kind == "cut":
                near = min(cuts, key=lambda c: abs(c - t)) if cuts else None
                if near is None or abs(near - t) > 0.6:
                    self.notes.append(f"flicker cut at {t:.2f}s: no scene cut within 0.6 s, made it 'exposure'")
                    kind, pat = "exposure", PATTERN["exposure"]
                else:
                    t, boundary = near, int(round(near * fps))
            if len(pat) > max_len:
                self.notes.append(f"flicker at {t:.2f}s: pattern {pat} longer than {FLICKER_MAX_S}s, cut to {pat[:max_len]}")
                pat = pat[:max_len]
            while pat and pattern_flashes(kind, pat) > FLASH_LIMIT:
                pat = pat[:-1]
            start = t - len(pat) / fps / 2 if boundary is not None else t
            if start < last_end + FLICKER_GAP_S:
                self.notes.append(f"flicker at {t:.2f}s dropped: less than {FLICKER_GAP_S}s after the previous series")
                continue
            if len(self.events) >= FLICKER_MAX_SERIES:
                self.notes.append(f"flicker at {t:.2f}s dropped: more than {FLICKER_MAX_SERIES} series per video")
                continue
            k0 = max(0, int(round(start * fps)))
            self.events.append(FlickerEvent(k0, kind, pat, boundary))
            last_end = start + len(pat) / fps

    def at(self, k: int) -> tuple[FlickerEvent, str] | None:
        for e in self.events:
            if e.k0 <= k < e.k0 + len(e.pattern):
                return e, e.pattern[k - e.k0]
        return None

    def apply(self, img: np.ndarray, k: int, a_frame: np.ndarray | None, b_frame: np.ndarray | None) -> np.ndarray:
        hit = self.at(k)
        if not hit:
            return img
        e, c = hit
        if e.kind == "cut":
            # before the cut the picture is A (b_frame = first frame of B); after it B (a_frame = held last A)
            before = e.boundary is not None and k < e.boundary
            if c == "A":
                return img if before else (a_frame if a_frame is not None else img)
            return b_frame if before and b_frame is not None else img
        if e.kind == "black":
            return img if c == "1" else np.zeros_like(img)
        g = LEVEL["exposure"].get(c, 1.0)
        return cv2.convertScaleAbs(img, alpha=g, beta=0)

    def report(self) -> dict:
        return {"series": [{"t": round(e.k0 / self.fps, 3), "kind": e.kind, "pattern": e.pattern,
                            "flashes": pattern_flashes(e.kind, e.pattern)} for e in self.events], "notes": self.notes}


# ------------------------------------------------------------------ colour switch (14.6)

def grade(img: np.ndarray, name: str) -> np.ndarray:
    if name in (None, "base", "none", ""):
        return img
    lut, sat = LK._luts(name)
    out = cv2.LUT(img, lut)
    if abs(sat - 1) > 1e-3:
        grey = cv2.cvtColor(cv2.cvtColor(out, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
        out = cv2.addWeighted(out, sat, grey, 1 - sat, 0)
    return out


@dataclass
class LookKey:
    t: float
    look: str
    trans: str = "cut"
    dur: float = 0.0
    dir: str = "lr"
    cx: float = 0.5
    cy: float = 0.42


class LookKeys:
    """Keys [{t, look, trans, dur, dir}]. look = film|cold|punchy|bw|base ('base' = the shot as it is: shots of an
    edit already carry their look, so bw -> base is the classic "colour comes back on the drop")."""

    LINE = 6  # px, white wipe line, no glow

    def __init__(self, spec: list, total: float, drop: float | None, face: tuple[float, float] | None = None):
        self.keys: list[LookKey] = []
        self.notes: list[str] = []
        for it in spec or []:
            t = resolve_t(it.get("t", 0), total, drop)
            if t is None:
                self.notes.append("look key at 'drop' skipped: audio.music.drop_at is not set")
                continue
            look = it.get("look", "base")
            if look not in LK.GRADES and look != "base":
                self.notes.append(f"unknown look '{look}', used 'base'")
                look = "base"
            trans = it.get("trans", "cut")
            dur = float(it.get("dur", 0 if trans == "cut" else (0.3 if trans == "fade" else 0.6)))
            cx, cy = face or (0.5, 0.42)
            self.keys.append(LookKey(t, look, trans, dur, it.get("dir", "lr"), float(it.get("cx", cx)), float(it.get("cy", cy))))
        self.keys.sort(key=lambda k: k.t)

    def changes(self) -> int:
        return sum(1 for a, b in zip(self.keys, self.keys[1:]) if a.look != b.look)

    def apply(self, img: np.ndarray, t: float) -> np.ndarray:
        if not self.keys:
            return img
        prev, cur = "base", None
        for k in self.keys:
            if k.t <= t:
                prev, cur = (cur.look if cur else "base"), k
        if cur is None:
            return img
        u = 1.0 if cur.dur <= 0 or cur.trans == "cut" else (t - cur.t) / cur.dur
        if u >= 1.0 or prev == cur.look:
            return grade(img, cur.look)
        old, new = grade(img, prev), grade(img, cur.look)
        e = ease("out_cubic", u)
        h, w = img.shape[:2]
        if cur.trans == "fade":
            return mix(old, new, e)
        if cur.trans == "wipe":
            out = old.copy()
            if cur.dir in ("lr", "rl"):
                x0 = int(round(w * e))
                if cur.dir == "lr":
                    out[:, :x0] = new[:, :x0]
                    xl = x0
                else:
                    out[:, w - x0:] = new[:, w - x0:]
                    xl = w - x0
                if 0 < xl < w:
                    out[:, max(0, xl - self.LINE // 2):xl + self.LINE // 2] = 255
            else:
                y0 = int(round(h * e))
                if cur.dir == "tb":
                    out[:y0] = new[:y0]
                    yl = y0
                else:
                    out[h - y0:] = new[h - y0:]
                    yl = h - y0
                if 0 < yl < h:
                    out[max(0, yl - self.LINE // 2):yl + self.LINE // 2] = 255
            return out
        if cur.trans == "radial":
            yy, xx = np.ogrid[0:h, 0:w]
            r = e * math.hypot(max(cur.cx, 1 - cur.cx) * w, max(cur.cy, 1 - cur.cy) * h) * 1.02
            m = ((xx - cur.cx * w) ** 2 + (yy - cur.cy * h) ** 2) <= r * r
            out = old.copy()
            out[m] = new[m]
            return out
        return new

    def report(self) -> dict:
        return {"keys": [{"t": round(k.t, 3), "look": k.look, "trans": k.trans, "dur": k.dur} for k in self.keys],
                "changes": self.changes(), "notes": self.notes}


# ------------------------------------------------------------------ transitions between scenes (03, 16)

TRANS_DUR = {"whip": 0.27, "zoom": 0.33, "flash_blur": 0.27, "glitch": 0.2, "dip": 0.27, "spin": 0.33,
             "dissolve": 0.4, "flicker": 0.2, "cut": 0.0}
HEAVY = {"zoom", "flash_blur", "glitch", "spin", "flicker"}
KINDS = tuple(TRANS_DUR)
AUTO_MOODS = {
    # research 03 section 4: transitions by format / emotion
    "energy": ["zoom", "whip", "glitch", "zoom", "flicker", "spin"],
    "phonk": ["zoom", "glitch", "spin", "flicker"],
    "facts": ["whip", "zoom", "whip"],
    "sad": ["dissolve", "dip"],
    "calm": ["dip", "dissolve"],
    "monologue": ["dip"],
}


@dataclass
class Trans:
    b: float          # cut time (scene start), s
    kind: str
    dur: float
    dir: str
    scene: int        # index of the incoming scene in `live`
    how: str = "plan"
    fps: int = 30

    @property
    def t0(self) -> float:
        return self.b - self.dur / 2

    @property
    def t1(self) -> float:
        return self.b + self.dur / 2


def plan_transitions(live: list, fx: dict, drop: float | None) -> tuple[list[Trans], list[str]]:
    """Transitions from scenes[].trans (explicit) and fx.transitions.auto (research rules)."""
    notes: list[str] = []
    out: dict[int, Trans] = {}
    for i, s in enumerate(live):
        if i == 0:
            continue
        tr = s.data.get("trans")
        if not tr:
            continue
        if isinstance(tr, str):
            tr = {"kind": tr}
        kind = tr.get("kind", "cut")
        if kind == "cut":
            out[i] = Trans(s.start, "cut", 0.0, "left", i)
            continue
        out[i] = Trans(s.start, kind, float(tr.get("dur", TRANS_DUR.get(kind, 0.27))), tr.get("dir", "left"), i)
    auto = (fx.get("transitions") or {}).get("auto") if isinstance(fx.get("transitions"), dict) else None
    if auto:
        kinds = AUTO_MOODS.get(auto, AUTO_MOODS["energy"])
        free = [i for i in range(1, len(live)) if i not in out]
        share = float((fx.get("transitions") or {}).get("share", 0.2))  # 10-30% of joins, research 03.1
        n = max(1, int(round(share * (len(live) - 1)))) if free else 0
        picked: list[int] = []
        if drop is not None:
            at_drop = min(free, key=lambda i: abs(live[i].start - drop), default=None)
            if at_drop is not None and abs(live[at_drop].start - drop) < 0.2:
                picked.append(at_drop)  # the drop already gets a flash; a move here doubles the hit
        step = max(3, int(round((len(live) - 1) / max(1, n))))  # heavy moves: no more than 1 per 3-4 cuts
        for i in free[step // 2::step]:
            if len([p for p in picked]) >= n:
                break
            if all(abs(i - p) >= 3 for p in picked):
                picked.append(i)
        picked = sorted(set(picked))[:n]
        for j, i in enumerate(picked):
            kind = kinds[j % len(kinds)]
            out[i] = Trans(live[i].start, kind, TRANS_DUR[kind], "left" if j % 2 == 0 else "right", i, how="auto")
    res = []
    for i in sorted(out):
        tr = out[i]
        if tr.kind == "cut":
            continue
        if tr.kind not in TRANS_DUR:
            notes.append(f"scene {live[i].id}: unknown transition '{tr.kind}', plain cut")
            continue
        room = min(live[i - 1].length, live[i].length)
        if tr.dur / 2 > room * 0.45:
            new = round(max(2 / 30, room * 0.9), 3)
            notes.append(f"scene {live[i].id}: {tr.kind} {tr.dur:.2f}s is too long for {room:.2f}s shots, {new:.2f}s")
            tr.dur = new
        if tr.dur > 0.5:
            notes.append(f"scene {live[i].id}: {tr.kind} lasts {tr.dur:.2f}s (> 0.5 s looks like a slide show)")
        res.append(tr)
    heavy = [t for t in res if t.kind in HEAVY]
    for a, b in zip(heavy, heavy[1:]):
        if b.scene - a.scene == 1:
            notes.append(f"heavy transitions on two joins in a row ({a.kind} at {a.b:.2f}s, {b.kind} at {b.b:.2f}s)")
    return res, notes


def _glitch(img: np.ndarray, env: float, seed: int) -> np.ndarray:
    if env < 0.02:
        return img
    rng = np.random.default_rng(seed)
    h, w = img.shape[:2]
    out = img.copy()
    s = max(1, int(round(4 + 8 * env)))
    out[:, s:, 0] = img[:, :-s, 0]
    out[:, :-s, 2] = img[:, s:, 2]
    for _ in range(int(4 + 8 * env)):
        y0 = int(rng.integers(0, h - 8))
        bh = int(rng.integers(8, max(9, int(h * 0.08))))
        dx = int(rng.integers(-1, 2) * rng.integers(10, 10 + int(60 * env)))
        out[y0:y0 + bh] = np.roll(out[y0:y0 + bh], dx, axis=1)
    return out


def _push(a: np.ndarray, b: np.ndarray, off: float, direction: str) -> np.ndarray:
    """A pushed out by B. off 0..1. direction = where the content goes (left: B comes from the right)."""
    h, w = a.shape[:2]
    if direction in ("left", "right"):
        o = int(round(off * w))
        if direction == "left":
            return np.concatenate([a[:, o:], b[:, :o]], axis=1) if 0 < o < w else (a if o <= 0 else b)
        return np.concatenate([b[:, w - o:], a[:, :w - o]], axis=1) if 0 < o < w else (a if o <= 0 else b)
    o = int(round(off * h))
    if direction == "up":
        return np.concatenate([a[o:], b[:o]], axis=0) if 0 < o < h else (a if o <= 0 else b)
    return np.concatenate([b[h - o:], a[:h - o]], axis=0) if 0 < o < h else (a if o <= 0 else b)


def apply_transition(tr: Trans, t: float, img: np.ndarray, a_last: np.ndarray | None, b_first: np.ndarray | None,
                     k: int) -> np.ndarray:
    """img is the frame the timeline shows at t (A before the cut, B after)."""
    before = t < tr.b
    half = tr.dur / 2
    u = (t - tr.t0) / half if before else (t - tr.b) / half   # 0..1 inside its half
    u = min(1.0, max(0.0, u))
    w_total = (t - tr.t0) / tr.dur                               # 0..1 over the whole move
    h, w = img.shape[:2]
    kind = tr.kind
    if kind == "whip":
        a = img if before else (a_last if a_last is not None else img)
        b = (b_first if b_first is not None else img) if before else img
        off = ease("in_out", w_total)
        out = _push(a, b, off, tr.dir)
        speed = math.sin(math.pi * min(1, max(0, w_total)))
        horiz = tr.dir in ("left", "right")
        return dir_blur(out, speed * (0.16 * (w if horiz else h)), horiz)
    if kind == "zoom":
        if before:
            e = ease("in_cubic", u)
            return zoom_blur(img, 1 + 0.9 * e, 0.22 * e)
        e = 1 - ease("out_cubic", u)
        return zoom_blur(img, 1 + 0.9 * e, 0.22 * e)
    if kind == "flash_blur":
        e = ease("in_cubic", u) if before else 1 - ease("out_cubic", u)
        return to_white(soft_blur(img, 22 * e), 0.75 * e)
    if kind == "glitch":
        e = math.sin(math.pi * min(1, max(0, w_total)))
        return _glitch(img, e, seed=k)
    if kind == "dip":
        e = ease("in_cubic", u) if before else 1 - ease("out_cubic", u)
        return cv2.convertScaleAbs(img, alpha=1 - e, beta=0)
    if kind == "spin":
        sign = 1 if tr.dir in ("left", "up") else -1
        if before:
            e = ease("in_cubic", u)
            ang = sign * 90 * e
        else:
            e = 1 - ease("out_cubic", u)
            ang = -sign * 90 * e
        sc = 1 + 0.35 * e
        out = zoom_at(img, sc, angle=ang)
        if e > 0.05:
            out = mix(out, zoom_at(img, sc, angle=ang - sign * 8 * e), 0.5)
            out = soft_blur(out, 6 * e)
        return out
    if kind == "dissolve":
        if before:
            return mix(img, b_first, 0.5 * ease("linear", u)) if b_first is not None else img
        return mix(a_last, img, 0.5 + 0.5 * ease("linear", u)) if a_last is not None else img
    if kind == "flicker":
        # A B A B around the cut, one frame each, then B (<= 2 flashes)
        n = int(round((t - tr.t0) * tr.fps))
        show_b = n % 2 == 1
        if before:
            return b_first if show_b and b_first is not None else img
        return img if show_b or a_last is None else a_last
    return img


# ------------------------------------------------------------------ split screen (14.7, 17)

@dataclass
class SplitWin:
    t0: float
    t1: float
    mode: str
    ratio: float
    gap: int
    anim: str
    a_pos: str
    a_focus: tuple[float, float]
    b_focus: tuple[float, float]
    b_dim: float
    pos: str
    path: str
    b_start: float
    full: bool = False   # covers the whole video: scenes are captured at the window size
    reader: object = None
    last_b: np.ndarray | None = None
    notes: list[str] = field(default_factory=list)

    ANIM = 0.3

    def geometry(self, cw: int, ch: int, u: float = 1.0) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int] | None]:
        """(a_rect, b_rect) inside the centre as (x, y, w, h); u = 0..1 of the slide-in."""
        e = ease("out_cubic", u)
        if self.mode == "v2":
            a_h = int(round(ch * self.ratio / 8)) * 8
            b_h = ch - a_h - self.gap
            cur_a = int(round(ch + (a_h - ch) * e))
            if self.a_pos == "bottom":
                a = (0, ch - cur_a, cw, cur_a)
                b = (0, ch - cur_a - self.gap - b_h, cw, b_h)
            else:
                a = (0, 0, cw, cur_a)
                b = (0, cur_a + self.gap, cw, b_h)
            return a, b
        if self.mode == "h2":
            a_w = int(round(cw * self.ratio / 8)) * 8
            b_w = cw - a_w - self.gap
            cur_a = int(round(cw + (a_w - cw) * e))
            if self.a_pos == "right":
                return (cw - cur_a, 0, cur_a, ch), (cw - cur_a - self.gap - b_w, 0, b_w, ch)
            return (0, 0, cur_a, ch), (cur_a + self.gap, 0, b_w, ch)
        # pip: a stays full, b is a small window (36% width), slides in from its side
        bw = int(round(cw * 0.36 / 8)) * 8
        bh = int(round(bw * 16 / 9 / 8)) * 8 if self.ratio <= 0 else int(round(bw / max(0.3, self.ratio) / 8)) * 8
        return (0, 0, cw, ch), (0, 0, bw, bh)

    def b_size(self, cw: int, ch: int) -> tuple[int, int]:
        _, b = self.geometry(cw, ch, 1.0)
        return b[2], b[3]


def split_capture_rect(splits: list[SplitWin], cw: int, ch: int) -> tuple[int, int, int, int] | None:
    """When one split covers the whole video, scenes are rendered right at window A's size (sharper)."""
    full = [s for s in splits if s.full]
    if not full:
        return None
    a, _ = full[0].geometry(cw, ch, 1.0)
    return a


def compose_split(sp: SplitWin, a_img: np.ndarray, t: float, cw: int, ch: int, bg: np.ndarray,
                  safe_offset: tuple[int, int, int, int], border: tuple[int, int, int]) -> np.ndarray:
    """a_img: centre frame (cw x ch) or, for a full split, a frame already at window A's size."""
    u = 1.0 if sp.anim == "none" or sp.full else min(1.0, (t - sp.t0) / sp.ANIM)
    v = 1.0 if sp.anim == "none" or sp.full else min(1.0, (sp.t1 - t) / (sp.ANIM * 0.7))
    u = min(u, v)
    out = np.empty((ch, cw, 3), np.uint8)
    out[:] = bg
    a, b = sp.geometry(cw, ch, u)
    if sp.mode == "pip":
        out[:] = a_img if a_img.shape[:2] == (ch, cw) else fit_cover(a_img, cw, ch, *sp.a_focus)
    else:
        ax, ay, aw, ah = a
        if aw > 0 and ah > 0:
            out[ay:ay + ah, ax:ax + aw] = a_img if a_img.shape[:2] == (ah, aw) else fit_cover(a_img, aw, ah, *sp.a_focus)
    fr = sp.last_b
    if fr is None:
        return out
    if sp.mode == "pip":
        bw, bh = b[2], b[3]
        sx, sy, sx1, sy1 = safe_offset
        x = sx + 24 if sp.pos in ("tl", "bl") else sx1 - 24 - bw
        y = sy + 24 if sp.pos in ("tl", "tr") else sy1 - 24 - bh
        x_from = -bw - 8 if sp.pos in ("tl", "bl") else cw + 8
        x = int(round(x_from + (x - x_from) * ease("out_cubic", u)))
        b4 = 4
        y0, y1, x0, x1 = max(0, y - b4), min(ch, y + bh + b4), max(0, x - b4), min(cw, x + bw + b4)
        out[y0:y1, x0:x1] = border
        _paste(out, fr, x, y)
        return out
    bx, by, bw, bh = b
    _paste(out, fr, bx, by)
    return out


def _paste(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(dst.shape[1], x + w), min(dst.shape[0], y + h)
    if x1 > x0 and y1 > y0:
        dst[y0:y1, x0:x1] = src[y0 - y:y1 - y, x0 - x:x1 - x]


def motion_focus(path, w: int, h: int, samples: int = 24) -> tuple[float, float, dict]:
    """Where the action is: the w:h window (of a cover crop) with the most frame-to-frame change.
    Gameplay strips (car on a ramp, runner) sit off-centre; a centre crop often shows sky or HUD."""
    from .clips import video_info

    info = video_info(path)
    iw, ih = info["w"], info["h"]
    dur = max(0.5, info["duration"])
    ar = w / h
    if iw / ih > ar:
        cw, chh, axis = int(round(ih * ar)), ih, "x"
    else:
        cw, chh, axis = iw, int(round(iw / ar)), "y"
    if (axis == "x" and cw >= iw - 2) or (axis == "y" and chh >= ih - 2):
        return 0.5, 0.5, {"axis": "none"}
    sw = 160
    sh = max(2, int(round(ih * sw / iw / 2)) * 2)
    import subprocess

    step = dur / (samples + 1)
    energy = np.zeros(sh if axis == "y" else sw, np.float64)
    prev = None
    for i in range(samples):
        ts = step * (i + 1)
        for dt in (0.0, 0.1):
            cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{ts + dt:.2f}", "-i", str(path), "-frames:v", "1",
                   "-vf", f"scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
            buf = subprocess.run(cmd, capture_output=True).stdout
            if len(buf) < sw * sh:
                continue
            g = np.frombuffer(buf[:sw * sh], np.uint8).reshape(sh, sw).astype(np.float32)
            if dt and prev is not None:
                d = np.abs(g - prev)
                energy += d.sum(axis=1 if axis == "y" else 0)
            prev = g
    if energy.sum() <= 0:
        return 0.5, 0.5, {"axis": axis, "energy": 0}
    win = int(round((chh / ih if axis == "y" else cw / iw) * len(energy)))
    cs = np.concatenate([[0], np.cumsum(energy)])
    sums = cs[win:] - cs[:-win] if win < len(energy) else np.array([cs[-1]])
    best = int(np.argmax(sums))
    span = len(energy) - win
    f = best / span if span > 0 else 0.5
    centre_share = float(sums[span // 2] / max(1e-9, sums.max())) if span > 0 else 1.0
    if centre_share > 0.9:
        f = 0.5  # centre is as good: keep it (stable, expected framing)
    return (f, 0.5, {"axis": axis, "focus": round(f, 3), "centre_share": round(centre_share, 3)}) if axis == "x" else \
        (0.5, f, {"axis": axis, "focus": round(f, 3), "centre_share": round(centre_share, 3)})


# ------------------------------------------------------------------ everything compose needs

@dataclass
class State:
    letterbox: Letterbox | None = None
    flicker: Flicker | None = None
    looks: LookKeys | None = None
    trans: list[Trans] = field(default_factory=list)
    splits: list[SplitWin] = field(default_factory=list)
    clip_size: tuple[int, int] | None = None     # scene clips are this size (full split), else the centre
    split_border: tuple[int, int, int] = (0, 0, 0)
    notes: list[str] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return bool(self.letterbox or self.flicker or self.looks or self.trans or self.splits)

    def trans_at(self, t: float) -> Trans | None:
        for tr in self.trans:
            if tr.t0 <= t < tr.t1:
                return tr
        return None

    def split_at(self, t: float) -> SplitWin | None:
        for sp in self.splits:
            if sp.t0 <= t < sp.t1:
                return sp
        return None

    def notable(self) -> list[str]:
        """Effects a viewer notices as 'a move' (research 14: <= 2 per video besides cuts)."""
        out = []
        if self.letterbox and self.letterbox.keys:
            out.append("letterbox")
        if self.flicker and self.flicker.events:
            out.append("flicker")
        if self.looks and self.looks.changes():
            out.append("look_keys")
        if any(t.kind in HEAVY for t in self.trans):
            out.append("heavy transitions")
        if self.splits:
            out.append("split")
        return out

    def report(self, total: float) -> dict:
        return {"letterbox": self.letterbox.report(total) if self.letterbox else None,
                "flicker": self.flicker.report() if self.flicker else None,
                "look_keys": self.looks.report() if self.looks else None,
                "transitions": [{"t": round(t.b, 3), "kind": t.kind, "dur": round(t.dur, 3), "dir": t.dir,
                                 "scene": t.scene, "how": t.how} for t in self.trans],
                "splits": [{"t0": round(s.t0, 3), "t1": round(s.t1, 3), "mode": s.mode, "ratio": s.ratio, "full": s.full,
                            "b": s.path, "b_start": s.b_start, "b_focus": list(s.b_focus), "b_dim": s.b_dim,
                            "notes": s.notes} for s in self.splits],
                "clip_size": list(self.clip_size) if self.clip_size else None,
                "notable": self.notable(), "notes": self.notes}


# ------------------------------------------------------------------ edit preset (research 14.4 A+B, 14.6 A/C)

AUTHOR_KINDS = K.AUTHOR_KINDS   # shared with validate and QA (contract)


def parse_layers(items: list[str] | None) -> list[dict]:
    """CLI `--layer kind:note` -> author_layer items (unknown kinds are an error, the note is free text)."""
    out = []
    for raw in items or []:
        kind, _, note = str(raw).partition(":")
        kind = kind.strip()
        if kind not in AUTHOR_KINDS:
            raise ValueError(f"author layer '{kind}': one of {', '.join(AUTHOR_KINDS)}")
        out.append({"kind": kind, "note": note.strip()})
    return out


def edit_cinema(plan: dict, bars: bool = False, bw: bool = False, layers: list[dict] | None = None,
                face: tuple[float, float] | None = None) -> list[str]:
    """`edit --bars / --bw-drop` on an edit v2 plan (changes it in place, returns notes for the user).

    bars: the line plays in 2.39 cinema bars, the drop opens them in 0.45 s (ease-out), they close again on the
          last 1.2 s, so the loop meets the first frame (research 14.4 A + B).
    bw:   the line is black and white, the colour comes back on the drop: a circle grows from the hero's face
          (radial, 0.5 s; reframe "face" keeps it at (0.5, 0.42)) or a wipe when it is unknown (research 14.6 C / A).
    Both are keyed to "drop" (edit v2 puts audio.music.drop_at on the end of the line). These are 2 noticeable
    moves: nothing else noticeable should be added (research 14: <= 2). Foreign film = author layers needed."""
    notes: list[str] = []
    drop = ((plan.get("audio") or {}).get("music") or {}).get("drop_at")
    if (bars or bw) and drop is None:
        raise ValueError("--bars / --bw-drop need audio.music.drop_at (edit with --line or --line-at)")
    fx = plan.setdefault("fx", {})
    if bars:
        fx["letterbox"] = [{"t": 0, "ratio": 2.39}, {"t": "drop", "ratio": "full", "dur": 0.45, "ease": "out_cubic"},
                           {"t": -1.2, "ratio": 2.39, "dur": 0.6, "ease": "in_out"}]
        if float(drop) > 3.0:
            notes.append(f"the line is {float(drop):.1f}s: the bars hide the hook > 3 s (QA warns); a shorter line reads better")
    if bw:
        key = {"t": "drop", "look": "base", "dur": 0.5}
        if face is None and (plan.get("edit") or {}).get("reframe") == "face":
            face = (0.5, 0.42)  # reframe "face" keeps the hero's face here (QA edit_style: faces centred)
        if face is not None:
            key.update(trans="radial", cx=round(float(face[0]), 3), cy=round(float(face[1]), 3))
        else:
            key.update(trans="wipe", dir="lr")
        fx["look_keys"] = [{"t": 0, "look": "bw"}, key]
    if layers:
        plan["author_layer"] = list(plan.get("author_layer") or []) + list(layers)
    if bars or bw or layers:
        plan["schema_version"] = "1.3"
        kinds = {x.get("kind") for x in plan.get("author_layer") or []}
        if not K.author_layers_ok(kinds):
            notes.append("film footage needs >= 2 author layers, one of them voice / thesis / own_footage / compare, "
                         "with schema 1.3 (validate fails without them): "
                         "--layer thesis:'the idea of the cut' --layer sound_design:'drop on the line end' "
                         "(velocity, look and plates are template changes, not a layer: research 15)")
    return notes
