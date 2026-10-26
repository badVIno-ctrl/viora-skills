"""Shared fixtures. Every test runs with its own memory and cache folders (no network unless marked)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
FIX = ROOT / "tests" / "fixtures"


def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs internet (sites, YouTube, TTS service); skipped unless SHORTS_NETWORK=1")
    config.addinivalue_line("markers", "slow: renders a full video")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("SHORTS_NETWORK") == "1":
        return
    skip = pytest.mark.skip(reason="network test (set SHORTS_NETWORK=1)")
    for it in items:
        if "network" in it.keywords:
            it.add_marker(skip)


@pytest.fixture(scope="session")
def session_dirs(tmp_path_factory):
    base = tmp_path_factory.mktemp("shorts")
    cache = base / "cache"
    tts = cache / "tts"
    tts.mkdir(parents=True)
    # ready-made voice for the offline plan ("готовая озвучка"): ogg in git -> wav in the cache
    for ogg in (FIX / "tts").glob("*.ogg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ogg), "-ar", "48000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(tts / (ogg.stem + ".wav"))], check=True)
        shutil.copy(ogg.with_suffix(".json"), tts / (ogg.stem + ".json"))
    return base


@pytest.fixture(autouse=True)
def isolated_env(session_dirs, tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_CACHE", str(session_dirs / "cache"))
    monkeypatch.setenv("SHORTS_MEMORY", str(tmp_path / "memory"))
    if os.environ.get("SHORTS_NETWORK") != "1":
        monkeypatch.setenv("SHORTS_IMAGE_PROVIDER", "none")
    if os.environ.get("SHORTS_TEST_WHISPER") != "1":      # word timings in tests come from SRT / synthetic words
        monkeypatch.setenv("SHORTS_WHISPER", "off")
    # 2.4: the cached fixture voice is an edge-tts take; VoiceEngine (first in "auto") and the YouTube music search
    # stay off unless a test turns them on (tests/unit/test_v24_voice_music.py does, for the real engine)
    if os.environ.get("SHORTS_TEST_VOICEENGINE") != "1":
        monkeypatch.setenv("SHORTS_VOICEENGINE", "off")
    if os.environ.get("SHORTS_NETWORK") != "1":
        monkeypatch.setenv("SHORTS_MUSIC_AUTO", "off")
    yield


def write_plan(tmp: Path, plan: dict, name: str = "plan.json") -> Path:
    for f in ("orbit.html", "app-screen.png"):
        if not (tmp / f).exists():
            shutil.copy(FIX / f, tmp / f)
    p = tmp / name
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def mini_plan(**over) -> dict:
    """6-second plan without TTS (fast). Captions come from a given transcript."""
    plan = {
        "schema_version": "1",
        "meta": {"name": "mini", "language": "ru", "platforms": ["youtube_shorts"], "duration_target": [4, 12], "loop": True},
        "layout": {"mode": "center_only", "cta_in_center": []},
        "brand": {"preset": "viora"},
        "captions": {"enabled": True, "max_words": 3},
        "audio": {"music": {"source": "assets/audio/bed.mp3"}, "sfx_auto": False},
        "scenes": [{
            "id": "a", "why": "test", "duration": 6.0, "on_screen_text": "ТЕСТ КАДРА",
            "source": {"type": "html", "ref": "orbit.html"},
            "transcript": [{"w": "Два", "s": 0.2, "e": 0.5}, {"w": "бесплатных", "s": 0.55, "e": 1.1},
                           {"w": "сайта,", "s": 1.15, "e": 1.6}, {"w": "и", "s": 1.9, "e": 2.0},
                           {"w": "оба", "s": 2.05, "e": 2.4}, {"w": "пригодятся.", "s": 2.45, "e": 3.2},
                           {"w": "Смотри", "s": 3.6, "e": 4.0}, {"w": "до", "s": 4.05, "e": 4.2},
                           {"w": "конца.", "s": 4.25, "e": 4.8}]}],
    }
    for k, v in over.items():
        plan[k] = v
    return plan


# ---------------------------------------------------------------- synthetic film (own code, no licence questions)

SYN_TITLE = (20.0, 23.0)  # static title card
SYN_BLACK = (33.0, 34.5)  # black frames
SYN_CREDITS = (46.0, 60.0)  # rolling credits to the end


def make_synthetic_film(path: Path, seconds: float = 60.0, fps: int = 10, w: int = 640, h: int = 360) -> Path:
    """Moving colour shapes (the 'film'), a title card, a black gap and rolling credits at the end."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Manrope-SemiBold.ttf"), 15)
    big = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Manrope-Bold.ttf"), 22)
    names = ["Director", "Art Director", "Lead Animator", "Sound Design", "Music", "Producer", "Editor",
             "Camera", "Lighting", "Rendering", "Software", "Special Thanks"]
    credits_lines = [f"{names[i % len(names)]}    Person Number {i:02d}" for i in range(60)]
    rng = np.random.default_rng(7)
    blobs = [(rng.uniform(0, w), rng.uniform(0, h), rng.uniform(-60, 60), rng.uniform(-40, 40), rng.uniform(25, 70),
              tuple(int(v) for v in rng.integers(40, 255, 3))) for _ in range(9)]
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                          "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    for k in range(int(seconds * fps)):
        t = k / fps
        if SYN_TITLE[0] <= t < SYN_TITLE[1]:
            img = Image.new("RGB", (w, h), (12, 12, 16))
            d = ImageDraw.Draw(img)
            for i, ln in enumerate(["A FILM BY NOBODY", "PRODUCED WITH CODE", "MUSIC BY A SINE WAVE",
                                    "WRITTEN BY A RANDOM SEED", "IN COLOUR"]):
                d.text((90, 70 + i * 44), ln, font=big, fill=(235, 235, 235))
        elif SYN_BLACK[0] <= t < SYN_BLACK[1]:
            img = Image.new("RGB", (w, h), (2, 2, 2))
        elif t >= SYN_CREDITS[0]:
            img = Image.new("RGB", (w, h), (8, 10, 12))
            d = ImageDraw.Draw(img)
            off = (t - SYN_CREDITS[0]) * 40
            for i, ln in enumerate(credits_lines):
                y = h - 120 + i * 26 - off
                if -20 < y < h:
                    d.text((150, y), ln, font=font, fill=(230, 230, 230))
        else:
            img = Image.new("RGB", (w, h), (int(70 + 60 * np.sin(t / 3)), 110, 150))
            d = ImageDraw.Draw(img)
            for x, y, vx, vy, r, col in blobs:
                cx, cy = (x + vx * t) % w, (y + vy * t) % h
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        assert p.stdin
        p.stdin.write(np.asarray(img, np.uint8).tobytes())
    assert p.stdin
    p.stdin.close()
    assert p.wait() == 0
    return path


@pytest.fixture(scope="session")
def synthetic_film(tmp_path_factory) -> Path:
    return make_synthetic_film(tmp_path_factory.mktemp("film") / "synthetic-film.mp4")


def heatmap_on_text(seconds: float = 60.0) -> list[dict]:
    """YouTube-like heatmap whose peaks sit on the title card and on the credits (the reported bug)."""
    seg = seconds / 100
    out = []
    for i in range(100):
        t = i * seg
        v = 0.3 + 0.1 * ((i * 37) % 10) / 10
        if SYN_TITLE[0] <= t < SYN_TITLE[1] or t >= SYN_CREDITS[0] + 1:
            v = 1.0
        out.append({"start_time": round(t, 3), "end_time": round(t + seg, 3), "value": round(v, 3)})
    return out
