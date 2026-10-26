"""The "edit look": what the tutorials stack on top of the cut (sharpen, grade, grain off the faces,
vignette, chromatic aberration and shake on the hits, slight sway). One preset, applied the same way to
every shot, so the edit looks like one piece. Everything is numpy/OpenCV on 1080x1920 frames.
Not used here on purpose (anti-slop rule): glow, gradient plates, heavy blur.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

GRADES = {
    # name: (lift, gamma, gain per channel R,G,B, contrast, saturation)
    "film": ((0.035, 0.03, 0.04), (1.0, 1.0, 1.04), (1.04, 1.0, 0.92), 1.14, 0.88),   # warm, soft blacks
    "cold": ((0.03, 0.035, 0.05), (1.02, 1.0, 0.98), (0.94, 1.0, 1.06), 1.12, 0.85),
    "punchy": ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1.02, 1.0, 0.98), 1.22, 1.08),
    "bw": ((0.02, 0.02, 0.02), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0), 1.25, 0.0),
    "none": ((0, 0, 0), (1, 1, 1), (1, 1, 1), 1.0, 1.0),
}


@dataclass
class Look:
    grade: str = "film"
    sharpen: float = 0.55      # unsharp amount (upscaled 607 px -> 1080 px needs it)
    grain: float = 6.0         # noise sigma, 0 = off; faces are masked out (tutorial: circular mask)
    vignette: float = 0.18     # darkening at the corners, 0..1
    chroma: float = 1.5        # base RGB split, px (0 = off); +chroma_hit on hits
    chroma_hit: float = 9.0
    shake_hit: float = 16.0    # px on hits, decays in 0.28 s
    sway: float = 3.0          # slow continuous sway ("покачивание"), px
    hits: list = field(default_factory=list)  # seconds (scene time) of hits: cut, drop, strong beats

    @classmethod
    def from_dict(cls, d: dict | str | None) -> "Look":
        if d is None or d is True:
            return cls()
        if d is False or d == "none":
            return cls(grade="none", sharpen=0, grain=0, vignette=0, chroma=0, chroma_hit=0, shake_hit=0, sway=0)
        if isinstance(d, str):
            return cls(grade=d)
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in d.items() if k in keys})


@lru_cache(maxsize=8)
def _luts(grade: str) -> tuple[np.ndarray, float]:
    lift, gamma, gain, con, sat = GRADES.get(grade, GRADES["film"])
    x = np.linspace(0, 1, 256)
    luts = []
    for c in range(3):
        y = x * gain[c]
        y = lift[c] + (1 - lift[c]) * y
        y = np.clip(y, 0, 1) ** (1 / gamma[c])
        # S-curve contrast around mid grey
        y = 0.5 + (y - 0.5) * con
        y = np.clip(y, 0, 1)
        luts.append((y * 255).astype(np.uint8))
    return np.stack(luts, axis=1).reshape(256, 1, 3), sat


@lru_cache(maxsize=4)
def _vignette(w: int, h: int, amount: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    v = 1 - amount * np.clip((r - 0.35) / 0.65, 0, 1) ** 1.6
    return cv2.merge([(v * 255).astype(np.uint8)] * 3)


@lru_cache(maxsize=2)
def _grain_bank(w: int, h: int, sigma: float, n: int = 6) -> list[tuple[np.ndarray, np.ndarray]]:
    """(positive, negative) uint8 noise maps, 3 channels, grain a bit bigger than a pixel."""
    rng = np.random.default_rng(7)
    bank = []
    for _ in range(n):
        g = rng.normal(0, sigma, (h // 2, w // 2)).astype(np.float32)
        g = cv2.resize(g, (w, h), interpolation=cv2.INTER_LINEAR)
        pos = np.clip(g, 0, 255).astype(np.uint8)
        neg = np.clip(-g, 0, 255).astype(np.uint8)
        bank.append((cv2.merge([pos] * 3), cv2.merge([neg] * 3)))
    return bank


def _face_mask(w: int, h: int, face: dict) -> np.ndarray:
    """uint8 3-channel mask: ~40 on the face (15%), 255 outside, soft edge. Built at 1/8 size."""
    sw, sh = max(8, w // 8), max(8, h // 8)
    yy, xx = np.ogrid[0:sh, 0:sw]
    fx, fy = face["x"] * sw, face["y"] * sh
    rx, ry = max(face["w"] * sw, 8) * 1.1, max(face["h"] * sh, 8) * 1.25
    d = ((xx - fx) / rx) ** 2 + ((yy - fy) / ry) ** 2
    m = 0.15 + 0.85 * np.clip(d - 0.6, 0, 1)
    m = cv2.resize((m * 255).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.merge([m] * 3)


def _hit_env(t: float, hits: list[float], decay: float) -> float:
    e = 0.0
    for h in hits:
        d = t - h
        if 0 <= d < decay:
            e = max(e, (1 - d / decay) ** 2)
    return e


def apply(frame_rgb: np.ndarray, t: float, look: Look, k: int, face: dict | None = None) -> np.ndarray:
    """frame_rgb: final-size frame (uint8). t: scene time. face: main face box in OUTPUT relative coords."""
    h, w = frame_rgb.shape[:2]
    img = frame_rgb
    if look.sharpen > 0:
        blur = cv2.GaussianBlur(img, (0, 0), 1.4)
        img = cv2.addWeighted(img, 1 + look.sharpen, blur, -look.sharpen, 0)
    if look.grade != "none":
        lut, sat = _luts(look.grade)
        img = cv2.LUT(img, lut)
        if abs(sat - 1) > 1e-3:
            grey = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
            img = cv2.addWeighted(img, sat, grey, 1 - sat, 0)
    # shake (hits) + sway (always): one affine warp, slightly zoomed so the edges never show
    e = _hit_env(t, look.hits, 0.28)
    dx = look.sway * np.sin(t * 1.7) + look.shake_hit * e * np.sin(t * 73.0)
    dy = look.sway * 0.6 * np.sin(t * 1.3 + 1.0) + look.shake_hit * e * np.cos(t * 59.0)
    ang = 0.35 * e * np.sin(t * 41.0)
    if abs(dx) + abs(dy) + abs(ang) > 0.05:
        pad = (max(abs(dx), abs(dy)) * 2 + 4) / min(w, h)
        m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1 + pad)
        m[0, 2] += dx
        m[1, 2] += dy
        img = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    ch = look.chroma + look.chroma_hit * _hit_env(t, look.hits, 0.18)
    if ch >= 0.75:
        s = int(round(ch))
        out = img.copy()
        out[:, s:, 0] = img[:, :-s, 0]      # red to the right
        out[:, :-s, 2] = img[:, s:, 2]      # blue to the left
        img = out
    if look.grain > 0:
        pos, neg = _grain_bank(w, h, float(look.grain))[k % 6]
        if face:
            m = _face_mask(w, h, face)
            pos, neg = cv2.multiply(pos, m, scale=1 / 255), cv2.multiply(neg, m, scale=1 / 255)
        img = cv2.subtract(cv2.add(img, pos), neg)
    if look.vignette > 0:
        img = cv2.multiply(img, _vignette(w, h, float(look.vignette)), scale=1 / 255)
    return img
