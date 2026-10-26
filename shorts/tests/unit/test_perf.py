"""Speed changes must not change the picture: crop-then-scale == old scale-to-cover-then-crop."""
from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from shortskit.engine import clips


def _src(tmp: Path, w: int, h: int) -> Path:
    p = tmp / f"src{w}x{h}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=10",
                    "-t", "0.5", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "10", str(p)], check=True)
    return p


def _old_way(path: Path, w: int, h: int, focus_x: float) -> np.ndarray:
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=bicubic,crop={w}:{h}:(iw-{w})*{focus_x:.3f}:(ih-{h})/2"
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-frames:v", "1", "-vf", vf,
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw[: w * h * 3], np.uint8).reshape(h, w, 3)


@pytest.mark.parametrize("src,dst,fx", [((640, 360), (270, 480), 0.5),    # wide film into vertical
                                         ((640, 360), (270, 480), 0.2),    # off-centre focus
                                         ((360, 640), (320, 180), 0.5)])   # tall source into wide
def test_crop_then_scale_same_picture(tmp_path, src, dst, fx):
    p = _src(tmp_path, *src)
    new = next(iter(clips.read_frames(p, dst[0], dst[1], focus_x=fx)))
    old = _old_way(p, dst[0], dst[1], fx)
    assert new.shape == old.shape == (dst[1], dst[0], 3)
    diff = np.abs(new.astype(int) - old.astype(int)).mean()
    assert diff < 6, f"picture moved: mean diff {diff:.1f}"


def test_bad_case_wrong_focus_is_detected(tmp_path):
    # the comparison is not blind: a different crop position gives a clearly different frame
    p = _src(tmp_path, 640, 360)
    new = next(iter(clips.read_frames(p, 270, 480, focus_x=0.0)))
    old = _old_way(p, 270, 480, 1.0)
    assert np.abs(new.astype(int) - old.astype(int)).mean() > 15


def test_final_preset_default_and_env(monkeypatch):
    from shortskit.engine import render
    monkeypatch.delenv("SHORTS_PRESET", raising=False)
    assert importlib.reload(render).FINAL_PRESET == "veryfast"
    monkeypatch.setenv("SHORTS_PRESET", "medium")
    assert importlib.reload(render).FINAL_PRESET == "medium"
    monkeypatch.delenv("SHORTS_PRESET")
    importlib.reload(render)
