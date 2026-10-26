"""Clip helpers: speed maps, camera zoom on clicks, writing exact-size CFR clips, reading frames."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import cv2
import numpy as np

from ..util import ShortsError, ease, ffprobe, log

ZOOM = 1.28


class SpeedMap:
    """Piecewise constant playback rate. `t` in plan entries is source time (s from scene start)."""

    def __init__(self, entries: list[dict] | None):
        pts = sorted(((float(e["t"]), float(e["rate"])) for e in entries or []), key=lambda x: x[0])
        self.src = [0.0]
        self.rate = [1.0]
        for t, r in pts:
            if t <= 0:
                self.rate[0] = r
            else:
                self.src.append(t)
                self.rate.append(r)
        self.out = [0.0]
        for i in range(1, len(self.src)):
            self.out.append(self.out[-1] + (self.src[i] - self.src[i - 1]) / self.rate[i - 1])

    def src_at(self, t_out: float) -> float:
        k = max(i for i, o in enumerate(self.out) if o <= t_out + 1e-9)
        return self.src[k] + (t_out - self.out[k]) * self.rate[k]

    def out_at(self, t_src: float) -> float:
        k = max(i for i, s in enumerate(self.src) if s <= t_src + 1e-9)
        return self.out[k] + (t_src - self.src[k]) / self.rate[k]

    def rate_at(self, t_out: float) -> float:
        k = max(i for i, o in enumerate(self.out) if o <= t_out + 1e-9)
        return self.rate[k]


@dataclass
class Camera:
    """Zoom-on-click keyframes (time in source seconds, zoom, centre x/y in clip px)."""
    w: int
    h: int
    keys: list[tuple[float, float, float, float]] = field(default_factory=list)

    @classmethod
    def from_clicks(cls, w: int, h: int, clicks: list[tuple[float, float, float]], zoom: float = ZOOM) -> "Camera":
        cx, cy = w / 2, h / 2
        keys = [(0.0, 1.0, cx, cy)]
        for i, (tc, x, y) in enumerate(sorted(clicks)):
            last_t, last_z, lx, ly = keys[-1]
            t_in = max(tc - 0.3, last_t + 0.01)
            t_full = max(tc + 0.1, t_in + 0.2)
            keys.append((t_in, last_z, lx, ly))
            keys.append((t_full, zoom, x, y))
            nxt = clicks[i + 1][0] if i + 1 < len(clicks) else None
            hold_end = tc + 1.4
            if nxt is None or nxt - 0.3 > hold_end + 0.45:
                keys.append((hold_end, zoom, x, y))
                keys.append((hold_end + 0.45, 1.0, cx, cy))
        return cls(w, h, keys)

    def at(self, t: float) -> tuple[float, float, float]:
        ks = self.keys
        if not ks or len(ks) == 1:
            return 1.0, self.w / 2, self.h / 2
        if t <= ks[0][0]:
            return ks[0][1:]
        for a, b in zip(ks, ks[1:]):
            if a[0] <= t <= b[0]:
                k = ease((t - a[0]) / max(1e-6, b[0] - a[0]))
                return tuple(a[i] + (b[i] - a[i]) * k for i in (1, 2, 3))  # type: ignore[return-value]
        return ks[-1][1:]

    def apply(self, frame: np.ndarray, t: float) -> np.ndarray:
        z, cx, cy = self.at(t)
        if z <= 1.001:
            return frame
        h, w = frame.shape[:2]
        cw, ch = w / z, h / z
        x0 = min(max(0.0, cx - cw / 2), w - cw)
        y0 = min(max(0.0, cy - ch / 2), h - ch)
        m = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
        return cv2.warpAffine(frame, m, (w, h), flags=cv2.INTER_LINEAR)


def cover_resize(img: np.ndarray, w: int, h: int, focus_x: float = 0.5, focus_y: float = 0.5) -> np.ndarray:
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    nw, nh = max(w, int(round(iw * s))), max(h, int(round(ih * s)))
    r = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    x0 = int(round((nw - w) * focus_x))
    y0 = int(round((nh - h) * focus_y))
    return r[y0:y0 + h, x0:x0 + w]


class ClipWriter:
    """Pipe RGB frames into an intermediate H.264 file of exact size and fps."""

    def __init__(self, path: Path, w: int, h: int, fps: int, crf: int = 14):
        self.path, self.w, self.h = path, w, h
        self.n = 0
        self.p = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
             "-i", "-", "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(crf), "-pix_fmt", "yuv420p", str(path)],
            stdin=subprocess.PIPE)

    def write(self, frame: np.ndarray) -> None:
        if frame.shape[0] != self.h or frame.shape[1] != self.w:
            frame = cover_resize(frame, self.w, self.h)
        assert self.p.stdin
        self.p.stdin.write(np.ascontiguousarray(frame[..., :3], dtype=np.uint8).tobytes())
        self.n += 1

    def close(self) -> Path:
        assert self.p.stdin
        self.p.stdin.close()
        if self.p.wait() != 0:
            raise ShortsError(f"ffmpeg failed writing {self.path}")
        return self.path


def video_info(path: Path | str) -> dict:
    info = ffprobe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    if not v:
        raise ShortsError(f"no video stream in {path}")
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    return {"w": int(v["width"]), "h": int(v["height"]), "fps": fps or 30.0,
            "duration": float(info["format"].get("duration", 0) or 0),
            "has_audio": any(s["codec_type"] == "audio" for s in info["streams"])}


def read_frames(path: Path | str, w: int, h: int, start: float = 0.0, duration: float | None = None,
                fps: float | None = None, focus_x: float = 0.5, loop: bool = False,
                focus_y: float = 0.5) -> Iterator[np.ndarray]:
    """Decode frames already scaled/cropped (cover) to w x h. focus_x / focus_y (0..1) move the crop window
    (a wide gameplay strip in a 1080x384 banner: focus_y picks the band with the action)."""
    # crop to the target aspect FIRST, then scale: same picture as scale-to-cover + crop, far fewer pixels
    # (a 640x360 film into 1080x1920 used to be scaled to 3413x1920 and then cropped)
    ar = f"{w}/{h}"
    vf = (f"crop='min(iw,ih*{ar})':'min(ih,iw/({ar}))':'(iw-min(iw,ih*{ar}))*{focus_x:.3f}':"
          f"'(ih-min(ih,iw/({ar})))*{focus_y:.3f}',"
          f"scale={w}:{h}:flags=bicubic,setsar=1")
    if fps:
        vf = f"fps={fps}," + vf
    cmd = ["ffmpeg", "-loglevel", "error"]
    if loop:
        cmd += ["-stream_loop", "-1"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = w * h * 3
    try:
        assert p.stdout
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        p.kill()
        p.wait()


def retime_stream(frames: Iterator[np.ndarray], src_fps: float, n_out: int, fps: int, speed: SpeedMap,
                  camera: Camera | None = None, on_hold: Callable[[], None] | None = None) -> Iterator[np.ndarray]:
    """Turn a forward-only source stream into n_out output frames following the speed map."""
    idx, cur = -1, None
    held = False
    for k in range(n_out):
        t_src = speed.src_at(k / fps)
        want = int(t_src * src_fps + 1e-6)
        while idx < want:
            nxt = next(frames, None)
            if nxt is None:
                if not held and on_hold:
                    on_hold()
                held = True
                break
            cur, idx = nxt, idx + 1
        if cur is None:
            raise ShortsError("source produced no frames")
        yield camera.apply(cur, t_src) if camera else cur


def write_frames_clip(out: Path, w: int, h: int, fps: int, frames: Iterator[np.ndarray]) -> int:
    wr = ClipWriter(out, w, h, fps)
    for f in frames:
        wr.write(f)
    wr.close()
    if wr.n == 0:
        raise ShortsError(f"empty clip {out}")
    log.debug("clip %s: %d frames", out.name, wr.n)
    return wr.n
