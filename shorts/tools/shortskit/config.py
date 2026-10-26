"""Paths and settings. Nothing is hard-coded: every location can be overridden by env vars.

SHORTS_HOME     skill root (default: two levels above this package)
SHORTS_MEMORY   folder with prefs.json, history.json, metrics (default: $SHORTS_HOME/memory)
SHORTS_CACHE    cache for TTS, downloads, analysis (default: $SHORTS_HOME/.cache)
SHORTS_CHROME   browser executable (default: Playwright's Chromium, then chrome/chromium in PATH)
SHORTS_NETWORK  "1" enables network tests
SHORTS_TTS      force a TTS engine (voiceengine, edge, elevenlabs, openai, piper, silent)
SHORTS_VOICEENGINE  "off" removes the embedded VoiceEngine from the auto chain
SHORTS_VOICE_MODELS folder with unpacked VoiceEngine models (default: unpacked from assets/voice on first use)
SHORTS_MUSIC_AUTO   "off" disables the automatic music search (music "auto" then means no music)
"""
from __future__ import annotations

import os
import shutil
from functools import lru_cache
from pathlib import Path

W, H = 1080, 1920
DEFAULT_FPS = 30


def skill_root() -> Path:
    env = os.environ.get("SHORTS_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def memory_dir() -> Path:
    p = Path(os.environ.get("SHORTS_MEMORY") or skill_root() / "memory").expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir(sub: str = "") -> Path:
    p = Path(os.environ.get("SHORTS_CACHE") or skill_root() / ".cache").expanduser()
    if sub:
        p = p / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def models_dir(sub: str) -> Path:
    """Downloaded models (piper voices, whisper). SHORTS_MODELS, else the cache. Big and reusable: keep them
    out of per-run caches."""
    base = os.environ.get("SHORTS_MODELS")
    p = Path(base).expanduser() / sub if base else cache_dir(sub)
    p.mkdir(parents=True, exist_ok=True)
    return p


def schema_path(name: str) -> Path:
    return skill_root() / "schema" / name


def asset(rel: str) -> Path:
    return skill_root() / "assets" / rel


@lru_cache(maxsize=1)
def chrome_executable() -> str | None:
    """None means "let Playwright use its own Chromium"."""
    env = os.environ.get("SHORTS_CHROME")
    if env:
        return env
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        from playwright._impl._driver import compute_driver_executable  # noqa: F401

        pw_dir = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", Path.home() / ".cache/ms-playwright"))
        if any(pw_dir.glob("chromium-*")) or any(pw_dir.glob("chromium_headless_shell-*")):
            return None
    except Exception:
        pass
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def browser_args() -> list[str]:
    args = ["--hide-scrollbars", "--mute-audio", "--ignore-gpu-blocklist", "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader", "--disable-dev-shm-usage"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        args.append("--no-sandbox")
    return args


def network_enabled() -> bool:
    return os.environ.get("SHORTS_NETWORK") == "1"
