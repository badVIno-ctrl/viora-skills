"""One film shot of an edit: 9:16 reframe on the subject + velocity (speed curve with optical-flow
in-betweens, motion blur on the fast parts) + the edit look. Called by the film/video capture when a
scene has `edit` settings. Output: centre clip w x h at the video fps (+ the source audio if asked).

Why each step (tutorials and how CapCut/AE do it):
  reframe      "move the clip so the face is in the centre" (Tifofey CapCut tutorial), AutoFlip camera logic
  velocity     speed curve ~10x -> 0.5x -> fast: the hero "appears, hangs, disappears", cuts become invisible
  optical flow CapCut "smooth slow-mo: optical flow" = new in-between frames, no stutter at 0.3-0.5x
  motion blur  fast parts blend the frames they skip (what a real shutter would record)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

from ..util import ShortsError, log
from . import look as LK
from . import reframe as RF
from . import velocity as V
from .clips import ClipWriter, video_info

ANALYSIS_W = 480


def _decode(path: Path, start: float, dur: float, w: int | None = None) -> tuple[list[np.ndarray], float]:
    info = video_info(path)
    sw, sh = info["w"], info["h"]
    if w:
        h = int(round(sh * w / sw / 2) * 2)
        vf = [f"scale={w}:{h}:flags=area"]
    else:
        w, h = sw, sh
        vf = []
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{max(0.0, start):.3f}", "-i", str(path), "-t", f"{dur:.3f}"]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out = []
    size = w * h * 3
    assert p.stdout
    while True:
        b = p.stdout.read(size)
        if len(b) < size:
            break
        out.append(np.frombuffer(b, np.uint8).reshape(h, w, 3))
    p.wait()
    return out, info["fps"]


def hard_cuts(frames: list[np.ndarray], thr: float = 0.45) -> list[int]:
    """Indices i where frame i starts a new camera shot (HSV histogram distance)."""
    cuts, prev = [], None
    for i, f in enumerate(frames):
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        if prev is not None and cv2.compareHist(prev, hist, cv2.HISTCMP_BHATTACHARYYA) > thr:
            cuts.append(i)
        prev = hist
    return cuts


class Interp:
    """Optical-flow in-betweens (OpenCV DIS, computed at half size). Cached per frame pair."""

    def __init__(self, frames: list[np.ndarray]):
        self.f = frames
        self.dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
        self.cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        h, w = frames[0].shape[:2]
        self.small = (max(16, w // 2), max(16, h // 2))
        gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        self.gx, self.gy = gx, gy

    def _flows(self, i: int):
        if i not in self.cache:
            a = cv2.cvtColor(cv2.resize(self.f[i], self.small, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
            b = cv2.cvtColor(cv2.resize(self.f[i + 1], self.small, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
            h, w = self.f[i].shape[:2]
            sx = w / self.small[0]
            fab = cv2.resize(self.dis.calc(a, b, None), (w, h)) * sx
            fba = cv2.resize(self.dis.calc(b, a, None), (w, h)) * sx
            self.cache = {i: (fab, fba)}  # keep only the current pair (memory)
        return self.cache[i]

    def at(self, f: float) -> np.ndarray:
        n = len(self.f)
        if f <= 0:
            return self.f[0]
        if f >= n - 1:
            return self.f[-1]
        i = int(f)
        a = f - i
        if a < 0.06:
            return self.f[i]
        if a > 0.94:
            return self.f[i + 1]
        fab, fba = self._flows(i)
        wa = cv2.remap(self.f[i], self.gx - a * fab[..., 0], self.gy - a * fab[..., 1], cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_REPLICATE)
        wb = cv2.remap(self.f[i + 1], self.gx - (1 - a) * fba[..., 0], self.gy - (1 - a) * fba[..., 1],
                       cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return cv2.addWeighted(wa, 1 - a, wb, a, 0)

    def blur(self, f0: float, f1: float) -> np.ndarray:
        """Average of the source frames between f0 and f1 (motion blur of a fast part), at most 6."""
        i0, i1 = max(0, int(round(f0))), min(len(self.f) - 1, int(round(f1)))
        if i1 <= i0:
            return self.at(f1)
        idx = np.linspace(i0, i1, min(6, i1 - i0 + 1)).round().astype(int)
        acc = np.zeros_like(self.f[0], dtype=np.float32)
        for j in idx:
            acc += self.f[j]
        return (acc / len(idx)).astype(np.uint8)


def render_shot(path: Path, offset: float, out_len: float, out: Path, w: int, h: int, fps: int,
                edit: dict, span: float | None = None) -> dict:
    """offset: source time (s) in `path` where the shot starts. span: source seconds to use (None = from curve)."""
    spec = edit.get("velocity", "flat")
    need = V.source_span(spec, out_len)
    scale = 1.0
    if span is not None and span > 0:
        scale = max(0.2, float(span) / need)
    remap = V.Remap(spec, out_len, scale)
    src_len = remap.span
    info = video_info(path)
    notes: list[str] = []
    avail = info["duration"] - offset
    if src_len > avail + 0.05:
        notes.append(f"source has {avail:.2f}s, the curve needs {src_len:.2f}s: rates slowed to fit")
        remap = V.Remap(spec, out_len, scale * max(0.2, avail / src_len))
        src_len = remap.span
    zoom = float(edit.get("zoom", 1.0))
    # 1) analysis pass: subject path
    small, sfps = _decode(path, offset, src_len + 0.1, ANALYSIS_W)
    if not small:
        raise ShortsError(f"no frames at {offset:.2f}s in {path.name}")
    cuts = hard_cuts(small)
    if cuts:
        notes.append(f"camera cut inside the shot at +{cuts[0] / sfps:.2f}s source (pick another 'in')")
    step = max(1, int(round(sfps / 8)))
    a_idx = list(range(0, len(small), step))
    a_t = [i / sfps for i in a_idx]
    mode = edit.get("reframe", "face")
    aspect = info["w"] / info["h"]
    if isinstance(mode, (int, float)) and not isinstance(mode, bool):
        path_ = RF.CropPath(np.array([0.0]), np.array([float(mode)]), "fixed", "manual", [], min(1.0, (w / h) / aspect / zoom))
    elif mode == "center":
        path_ = RF.CropPath(np.array([0.0]), np.array([0.5]), "fixed", "center", [], min(1.0, (w / h) / aspect / zoom))
    else:
        path_ = RF.plan_path(a_t, [small[i] for i in a_idx], aspect, w / h, zoom)
    # 2) full-res pass, cropped right away (memory: only the 9:16 window is kept)
    full, ffps = _decode(path, offset, src_len + 0.15)
    if not full:
        raise ShortsError(f"no frames at {offset:.2f}s in {path.name}")
    crops, face_out = [], []
    sw, sh = full[0].shape[1], full[0].shape[0]
    for i, fr in enumerate(full):
        t = i / ffps
        fb = path_.face_at(t)
        cy = 0.5 if zoom <= 1.0 or not fb else fb["y"]
        x0, y0, cw, ch = RF.crop_box(sw, sh, path_.at(t), path_.crop_w, cy)
        crops.append(np.ascontiguousarray(fr[y0:y0 + ch, x0:x0 + cw]))
        if fb:
            face_out.append({"x": (fb["x"] * sw - x0) / cw, "y": (fb["y"] * sh - y0) / ch,
                             "w": fb["w"] * sw / cw, "h": fb["h"] * sh / ch})
        else:
            face_out.append(None)
    full.clear()
    ip = Interp(crops)
    lk = LK.Look.from_dict(edit.get("look"))
    lk.hits = [float(x) for x in edit.get("hits", [0.0])]
    n_out = max(1, int(round(out_len * fps)))
    wr = ClipWriter(out, w, h, fps)
    rates = []
    prev_f = 0.0
    for k in range(n_out):
        t = k / fps
        f = remap.src(t) * ffps
        r = remap.rate(t)
        rates.append(r)
        fr = ip.blur(prev_f, f) if (r > 1.6 and k > 0) else ip.at(f)
        prev_f = f
        img = cv2.resize(fr, (w, h), interpolation=cv2.INTER_CUBIC)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        face = face_out[min(len(face_out) - 1, int(f))] if face_out else None
        img = LK.apply(img, t, lk, k, face)
        wr.write(img)
    wr.close()
    faces_seen = sum(1 for x in face_out if x)
    rep = {"strategy": path_.strategy, "subject": path_.subject, "crop_x": round(float(np.mean(path_.cx)), 3),
           "src_len": round(src_len, 3), "rate_min": round(min(rates), 2), "rate_max": round(max(rates), 2),
           "face_frames": round(faces_seen / max(1, len(face_out)), 2), "src_fps": round(ffps, 3), "notes": notes,
           "face_center": [round(float(np.mean([f["x"] for f in face_out if f])), 3)] if faces_seen else []}
    log.debug("edit shot %s: %s", out.name, rep)
    return rep
