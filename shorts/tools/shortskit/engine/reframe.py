"""16:9 -> 9:16 reframing that keeps the subject in frame (the "face in the middle" step of every edit tutorial).

Same idea as Google AutoFlip (research.google, 2020): detect the subject on every few frames, then choose
a camera strategy per shot: STATIONARY (subject stays put: one crop for the whole shot, no wobble) or
TRACKING (a smooth low-degree polynomial path through the subject positions, never frame-by-frame jitter).
Subject = faces (YuNet, assets/models). No faces: where the motion is. Nothing at all: the centre.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from ..config import skill_root

YUNET = "assets/models/face_detection_yunet_2023mar.onnx"


@lru_cache(maxsize=4)
def _detector(w: int, h: int):
    p = skill_root() / YUNET
    if not p.exists() or not hasattr(cv2, "FaceDetectorYN"):
        return None
    return cv2.FaceDetectorYN.create(str(p), "", (w, h), 0.72, 0.3, 50)


def faces(img_bgr: np.ndarray, min_rel: float = 0.04) -> list[dict]:
    """Faces as dicts in RELATIVE coords (0..1): x, y (centre), w, h, score. Small frames are upscaled."""
    h, w = img_bgr.shape[:2]
    scale = 1.0
    if w < 640:
        scale = 640 / w
        img_bgr = cv2.resize(img_bgr, (640, int(round(h * scale))), interpolation=cv2.INTER_CUBIC)
    hh, ww = img_bgr.shape[:2]
    det = _detector(ww, hh)
    if det is None:
        return []
    det.setInputSize((ww, hh))
    _, res = det.detect(img_bgr)
    out = []
    if res is None:
        return out
    for r in res:
        x, y, fw, fh, score = float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[14])
        if fh / hh < min_rel:
            continue
        out.append({"x": (x + fw / 2) / ww, "y": (y + fh / 2) / hh, "w": fw / ww, "h": fh / hh, "score": score,
                    "row": (r / scale).tolist() if scale != 1 else r.tolist()})
    out.sort(key=lambda f: -f["w"] * f["h"] * f["score"])
    return out


@dataclass
class CropPath:
    """Crop centre x (relative 0..1 of the source width) for every analysed time + the strategy used."""
    t: np.ndarray
    cx: np.ndarray
    strategy: str
    subject: str            # "face" | "motion" | "center"
    face_boxes: list        # per analysed time: main face (relative) or None
    crop_w: float           # relative width of the crop window in the source

    def at(self, t: float) -> float:
        if len(self.t) == 1:
            return float(self.cx[0])
        return float(np.interp(t, self.t, self.cx))

    def face_at(self, t: float):
        if not self.face_boxes:
            return None
        i = int(np.argmin(np.abs(self.t - t)))
        return self.face_boxes[i]


def _pick_main(fs: list[dict], prev: dict | None) -> dict | None:
    if not fs:
        return None
    if prev is None:
        return fs[0]
    # continuity: a big face close to the previous one wins over a slightly bigger face elsewhere
    return max(fs, key=lambda f: f["w"] * f["h"] * f["score"] - 0.5 * abs(f["x"] - prev["x"]) * f["h"])


def motion_x(frames: list[np.ndarray]) -> list[float | None]:
    out: list[float | None] = [None]
    for a, b in zip(frames, frames[1:]):
        ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
        d = cv2.absdiff(ga, gb).astype(np.float32)
        d[d < 18] = 0
        col = d.sum(axis=0)
        s = col.sum()
        out.append(float((col * np.arange(len(col))).sum() / s / len(col)) if s > d.shape[0] * 4 else None)
    return out


def plan_path(times: list[float], frames_bgr: list[np.ndarray], src_aspect: float, out_aspect: float = 9 / 16,
              zoom: float = 1.0) -> CropPath:
    """frames_bgr: small analysis frames of ONE camera shot. src_aspect = w/h of the source."""
    crop_w = min(1.0, out_aspect / src_aspect / max(zoom, 1.0))
    half = crop_w / 2
    t = np.array(times, float)
    main, prev = [], None
    for fr in frames_bgr:
        m = _pick_main(faces(fr), prev)
        main.append(m)
        prev = m or prev
    xs = np.array([m["x"] if m else np.nan for m in main], float)
    subject = "face"
    coverage = float((~np.isnan(xs)).mean()) if len(xs) else 0.0
    if coverage < 0.4:
        # faces seen rarely (profile, silhouette, back): follow the motion, keep the face positions we have
        mx = np.array([v if v is not None else np.nan for v in motion_x(frames_bgr)], float)
        if (~np.isnan(mx)).sum() >= max(2, (~np.isnan(xs)).sum()):
            xs = np.where(np.isnan(xs), mx, xs)
            subject = "motion" if coverage == 0 else "face+motion"
    if np.isnan(xs).all():
        return CropPath(t, np.full(len(t), 0.5), "stationary", "center", main, crop_w)
    good = ~np.isnan(xs)
    xs = np.interp(t, t[good], xs[good]) if good.sum() > 1 else np.full(len(t), xs[good][0])
    lo, hi = half, 1 - half
    if hi <= lo:
        return CropPath(t, np.full(len(t), 0.5), "stationary", subject, main, crop_w)
    spread = float(np.percentile(xs, 90) - np.percentile(xs, 10))
    if spread < crop_w * 0.25 or len(t) < 4:
        c = float(np.clip(np.median(xs), lo, hi))
        cx = np.full(len(t), c)
        strategy = "stationary"
    else:
        deg = 2 if len(t) >= 6 else 1
        coef = np.polyfit(t - t[0], xs, deg)
        cx = np.clip(np.polyval(coef, t - t[0]), lo, hi)
        strategy = "tracking"
    # never cut a face: if the main face would leave the window, shift the window
    for i, m in enumerate(main):
        if m:
            fx0, fx1 = m["x"] - m["w"] * 0.6, m["x"] + m["w"] * 0.6
            if fx0 < cx[i] - half:
                cx[i] = max(lo, fx0 + half)
            elif fx1 > cx[i] + half:
                cx[i] = min(hi, fx1 - half)
    if strategy == "tracking":  # light smoothing after the corrections
        k = np.ones(5) / 5
        cx = np.convolve(np.pad(cx, 2, mode="edge"), k, mode="valid")
    return CropPath(t, cx, strategy, subject, main, crop_w)


def crop_box(src_w: int, src_h: int, cx_rel: float, crop_w_rel: float, cy_rel: float = 0.5) -> tuple[int, int, int, int]:
    """Pixel crop (x0, y0, w, h) of the source for a 9:16 window centred at (cx_rel, cy_rel).
    cy only matters when the window is shorter than the source (zoomed in)."""
    cw = int(round(src_w * crop_w_rel))
    ch = int(round(min(src_h, cw * 16 / 9)))
    cw = int(round(ch * 9 / 16))
    x0 = int(round(cx_rel * src_w - cw / 2))
    x0 = max(0, min(src_w - cw, x0))
    y0 = int(round(cy_rel * src_h - ch / 2))
    y0 = max(0, min(src_h - ch, y0))
    return x0, y0, cw, ch
