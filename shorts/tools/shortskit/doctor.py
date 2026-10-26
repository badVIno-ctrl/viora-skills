"""Environment check: tools, browser, TTS, image generator (env var names only, never values)."""
from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import subprocess

from .config import chrome_executable
from .engine.tts import available_engines


def _ver(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.splitlines()[0][:80]
    except Exception:
        return None


# What was really run in the 1.1.0 sandbox (tests/e2e/test_local_models.py). Everything else: "не проверено".
VERIFIED = {
    "voiceengine": "проверено локально (2.4): VoiceEngine (Silero v5 RU + Kokoro EN на onnxruntime, 12 голосов), модели из assets/voice, "
                   "точные тайминги слов для RU, оценка для EN",
    "edge_tts": "проверено (сеть, tests/e2e/test_network.py)",
    "piper": "проверено локально: ru_RU-irina-medium, en_US-lessac-medium, модели в SHORTS_MODELS/piper (или кэш)",
    "faster_whisper": "проверено локально: модель base в SHORTS_MODELS/whisper (или кэш), слова для piper и нарезок",
}
NOT_VERIFIED = {
    "elevenlabs": "не проверено (нет ключа ELEVENLABS_API_KEY в песочнице)",
    "openai_tts": "не проверено (нет ключа OPENAI_API_KEY)",
    "openai_image": "не проверено (нет ключа OPENAI_API_KEY; тест подменяет вызов)",
    "gemini_image": "не проверено (нет ключа GEMINI_API_KEY; тест подменяет вызов)",
}


def smoke_local() -> dict:
    """--deep: VoiceEngine self-test (ru + en), then one phrase with piper read back with faster-whisper."""
    import tempfile
    from pathlib import Path

    from . import voice as VE
    from .engine import tts

    out: dict = {}
    try:
        st = VE.status()
        if st["deps_missing"]:
            out["voiceengine"] = "нет зависимостей: python3 -m pip install " + " ".join(st["deps_missing"])
        elif not st["enabled"]:
            out["voiceengine"] = "выключен (SHORTS_VOICEENGINE=off)"
        else:
            r = VE.selftest(Path(tempfile.mkdtemp(prefix="shorts-ve-")))
            out["voiceengine"] = ("ok сейчас: " if r["ok"] else "ошибка: ") + "; ".join(
                f"{c['lang']} {c.get('sec', '?')} s, слов {c.get('words', 0)}" if c.get("ok") else f"{c['lang']} {c.get('error', 'плохой звук')}"
                for c in r["checks"])
    except Exception as e:  # report, do not crash doctor
        out["voiceengine"] = f"ошибка: {str(e)[:160]}"
    try:
        os.environ.setdefault("SHORTS_TTS", "piper")
        sp = tts.synth("Проверка локального голоса.", lang="ru", engine="piper")
        out["piper"] = f"ok сейчас ({sp.duration:.1f} s)"
        out["faster_whisper"] = "ok сейчас (слова из whisper)" if not sp.estimated else "нет: слова оценены"
    except Exception as e:  # report, do not crash doctor
        out["piper"] = f"ошибка: {str(e)[:160]}"
    return out


def doctor(deep: bool = False) -> dict:
    rep: dict = {"tools": {}, "python": {}, "env": {}, "notes": []}
    rep["tools"]["ffmpeg"] = _ver(["ffmpeg", "-version"])
    rep["tools"]["ffprobe"] = _ver(["ffprobe", "-version"])
    if rep["tools"]["ffmpeg"]:
        filt = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        rep["tools"]["libass"] = " ass " in filt
        rep["tools"]["ebur128"] = "ebur128" in filt
    rep["tools"]["yt-dlp"] = _ver(["yt-dlp", "--version"]) or ("python module" if importlib.util.find_spec("yt_dlp") else None)
    rep["tools"]["js_runtime_for_youtube"] = shutil.which("deno") or shutil.which("node")
    for mod in ("playwright", "edge_tts", "segno", "cv2", "numpy", "PIL", "jsonschema", "librosa", "pyloudnorm",
                "fontTools", "faster_whisper"):
        rep["python"][mod] = importlib.util.find_spec(mod) is not None
    rep["tools"]["browser"] = chrome_executable() or "playwright chromium (if installed)"
    rep["tts_engines"] = available_engines()
    try:
        from . import voice as VE

        rep["voiceengine"] = VE.status()
        if rep["voiceengine"]["deps_missing"]:
            rep["notes"].append("VoiceEngine (встроенный офлайн-голос) ждёт: python3 -m pip install "
                                + " ".join(rep["voiceengine"]["deps_missing"]))
        elif not rep["voiceengine"]["models"] and rep["voiceengine"]["pack"]:
            rep["notes"].append("VoiceEngine: модели ещё в архиве, распакуются при первой озвучке "
                                "(или сразу: python3 tools/shorts.py voice-setup)")
    except Exception as e:  # noqa: BLE001 - doctor never crashes
        rep["voiceengine"] = {"error": str(e)[:160]}
    try:
        from . import music as MU

        rep["music_auto"] = {"enabled": not MU.disabled(), "yt_dlp": bool(rep["tools"]["yt-dlp"]),
                             "how": "music not given -> YouTube search by mood, best free track, section under the voice "
                                    "(tools/shortskit/music.py); offline or blocked -> video without music + local command"}
    except Exception as e:  # noqa: BLE001
        rep["music_auto"] = {"error": str(e)[:160]}
    for name in ("ELEVENLABS_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "SHORTS_PIPER_MODEL",
                 "SHORTS_CHROME", "SHORTS_HOME", "SHORTS_MEMORY", "SHORTS_CACHE", "SHORTS_VOICEENGINE",
                 "SHORTS_VOICE_MODELS", "SHORTS_MUSIC_AUTO"):
        rep["env"][name] = bool(os.environ.get(name))
    from .meta.cover import generator

    rep["image_generator"] = generator()
    if not rep["image_generator"]:
        rep["notes"].append("no image generator: covers are made from video frames + a prompt for the user")
    must = [rep["tools"]["ffmpeg"], rep["tools"].get("libass"), rep["python"]["playwright"], rep["python"]["segno"],
            rep["python"]["cv2"], rep["python"]["jsonschema"]]
    rep["ok"] = all(must)
    rep["python"]["piper"] = importlib.util.find_spec("piper") is not None
    if not rep["python"]["faster_whisper"]:
        rep["notes"].append("faster-whisper missing: long videos are cut without captions unless a transcript is given "
                            "(bash tools/install.sh --local)")
    rep["python"]["onnxruntime"] = importlib.util.find_spec("onnxruntime") is not None
    ver = {}
    for k, v in VERIFIED.items():
        installed = rep["python"].get("onnxruntime" if k == "voiceengine" else k, True)
        ver[k] = v if installed else "не установлено (bash tools/install.sh --local)"
    ver.update(NOT_VERIFIED)
    rep["verification"] = ver
    if deep:
        rep["verification_now"] = smoke_local()
    return rep
