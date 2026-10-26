"""Text to speech with word timings, a fallback chain and a cache.

Chain for engine "auto" (2.4): voiceengine (embedded offline VoiceEngine, ru / en, SHORTS_VOICEENGINE=off disables)
-> edge -> elevenlabs (if ELEVENLABS_API_KEY) -> openai (if OPENAI_API_KEY) -> piper (if installed).
VoiceEngine voices are attribute strings ("ж, 90, шёпотом", "дракон", "Кот Борис"); other engines get the
nearest stock voice by gender. Every result is cached by (engine, voice, speed, text); a cache hit needs no
network (tests use this). "silent" makes silence with estimated timings, for dry runs only.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import cache_dir, models_dir
from ..util import ShortsError, log, media_duration, run

SR = 48000

VOICES = {
    "edge": {
        "ru-male-1": "ru-RU-DmitryNeural", "ru-female-1": "ru-RU-SvetlanaNeural",
        "en-male-1": "en-US-AndrewNeural", "en-female-1": "en-US-AvaNeural",
        "en-male-2": "en-US-BrianNeural", "en-female-2": "en-US-EmmaNeural",
        "uk-male-1": "uk-UA-OstapNeural", "de-male-1": "de-DE-ConradNeural", "es-male-1": "es-ES-AlvaroNeural",
    },
    "openai": {"ru-male-1": "onyx", "ru-female-1": "nova", "en-male-1": "onyx", "en-female-1": "nova"},
}
DEFAULT_VOICE = {"ru": "ru-male-1", "en": "en-male-1", "uk": "uk-male-1", "de": "de-male-1", "es": "es-male-1"}
ENGINE_ALIASES = {"ve": "voiceengine", "voice_engine": "voiceengine", "voice-engine": "voiceengine"}
_ELEVEN_ID = re.compile(r"[A-Za-z0-9]{16,}")


def engine_name(engine: str | None) -> str:
    e = (engine or "auto").strip().lower()
    return ENGINE_ALIASES.get(e, e)


def _ve():
    from .. import voice as VE
    return VE


@dataclass
class Speech:
    wav: Path
    duration: float
    words: list[dict]  # {"w", "s", "e"} seconds from start of this clip
    engine: str
    voice: str
    estimated: bool = False


def _key(engine: str, voice: str, speed: float, text: str) -> str:
    return hashlib.sha256(f"{engine}|{voice}|{speed:.3f}|{text}".encode()).hexdigest()[:24]


def _cache_get(key: str) -> Speech | None:
    d = cache_dir("tts")
    w, j = d / f"{key}.wav", d / f"{key}.json"
    if w.exists() and j.exists():
        m = json.loads(j.read_text(encoding="utf-8"))
        return Speech(w, m["duration"], m["words"], m["engine"], m["voice"], m.get("estimated", False))
    return None


def _cache_put(key: str, src_audio: Path, words: list[dict], engine: str, voice: str, estimated: bool) -> Speech:
    d = cache_dir("tts")
    w = d / f"{key}.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src_audio, "-ar", SR, "-ac", 1, "-c:a", "pcm_s16le", w])
    dur = media_duration(w)
    (d / f"{key}.json").write_text(json.dumps({"duration": dur, "words": words, "engine": engine, "voice": voice,
                                               "estimated": estimated}, ensure_ascii=False), encoding="utf-8")
    return Speech(w, dur, words, engine, voice, estimated)


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", text.strip()) if t]


def estimate_words(text: str, duration: float, lead: float = 0.05) -> list[dict]:
    """Spread words over the clip by vowel count (rough syllables). Marked as estimated."""
    toks = tokenize(text)
    weights = [max(1, len(re.findall(r"[aeiouyаеёиоуыэюяіїє]", t.lower()))) + 0.3 for t in toks]
    total = sum(weights) or 1
    span = max(0.1, duration - lead - 0.1)
    t, out = lead, []
    for tok, wt in zip(toks, weights):
        d = span * wt / total
        out.append({"w": tok, "s": round(t, 3), "e": round(t + d * 0.92, 3)})
        t += d
    return out


def _align_words_to_text(text: str, boundaries: list[tuple[str, float, float]]) -> list[dict]:
    """Map engine word boundaries back onto the original tokens (keeps punctuation for chunking)."""
    toks = tokenize(text)
    out, bi = [], 0
    for tok in toks:
        core = re.sub(r"[^\w]", "", tok.lower())
        if not core:  # pure punctuation token: glue to previous word
            if out:
                out[-1]["w"] += " " + tok
            continue
        match = None
        for j in range(bi, min(bi + 4, len(boundaries))):
            if re.sub(r"[^\w]", "", boundaries[j][0].lower()) in (core, core[: len(boundaries[j][0])]):
                match = j
                break
        if match is None and bi < len(boundaries):
            match = bi
        if match is None:
            s = out[-1]["e"] if out else 0.0
            out.append({"w": tok, "s": s, "e": s + 0.2})
            continue
        _, s, e = boundaries[match]
        out.append({"w": tok, "s": round(s, 3), "e": round(e, 3)})
        bi = match + 1
    return out


# ---------------------------------------------------------------- engines

async def _edge(text: str, voice: str, speed: float, out: Path) -> list[tuple[str, float, float]]:
    import edge_tts

    rate = f"{int(round((speed - 1) * 100)):+d}%"
    audio, bounds = bytearray(), []
    async for ch in edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary").stream():
        if ch["type"] == "audio":
            audio += ch["data"]
        elif ch["type"] == "WordBoundary":
            s = ch["offset"] / 1e7
            bounds.append((ch["text"], s, s + ch["duration"] / 1e7))
    if not audio:
        raise ShortsError("edge-tts returned no audio")
    out.write_bytes(bytes(audio))
    return bounds


def _edge_sync(text: str, voice: str, speed: float, out: Path, attempts: int = 9) -> list[tuple[str, float, float]]:
    import time

    delay = 2.0
    for i in range(attempts):
        try:
            return asyncio.run(_edge(text, voice, speed, out))
        except Exception as e:  # service sometimes answers with nothing
            if i == attempts - 1:
                raise ShortsError(f"edge-tts failed {attempts} times: {e}") from e
            log.warning("edge-tts: %s, retry in %.0fs", e, delay)
            time.sleep(delay)
            delay = min(delay * 1.7, 15)
    raise AssertionError


def _http_json(url: str, payload: dict, headers: dict, timeout: float = 90) -> bytes:
    from ..costs import require_paid_approval
    require_paid_approval('tts', len(str(payload.get("text", ""))), url.split("/")[2] if "//" in url else url)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https endpoints)
        return r.read()


def _elevenlabs(text: str, voice: str, speed: float, out: Path) -> list[tuple[str, float, float]]:
    """ElevenLabs 'with-timestamps' gives character alignment, turned into word boundaries. Not verified without a key."""
    key = os.environ["ELEVENLABS_API_KEY"]
    vid = voice if re.fullmatch(r"[A-Za-z0-9]{16,}", voice) else os.environ.get("ELEVENLABS_VOICE_ID", "")
    if not vid:
        raise ShortsError("set ELEVENLABS_VOICE_ID or give a voice id")
    raw = _http_json(f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps",
                     {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"speed": speed}},
                     {"xi-api-key": key})
    data = json.loads(raw)
    out.write_bytes(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or {}
    chars, st, en = al.get("characters", []), al.get("character_start_times_seconds", []), al.get("character_end_times_seconds", [])
    bounds, cur, s0 = [], "", None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                bounds.append((cur, s0, prev_e))
            cur, s0 = "", None
            continue
        if s0 is None:
            s0 = s
        cur += c
        prev_e = e
    if cur:
        bounds.append((cur, s0, prev_e))
    return bounds


def _openai(text: str, voice: str, speed: float, out: Path) -> None:
    raw = _http_json("https://api.openai.com/v1/audio/speech",
                     {"model": os.environ.get("SHORTS_OPENAI_TTS_MODEL", "gpt-4o-mini-tts"), "voice": voice,
                      "input": text, "speed": speed, "response_format": "wav"},
                     {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    out.write_bytes(raw)


PIPER_VOICES = {"ru": "ru_RU-irina-medium", "en": "en_US-lessac-medium", "uk": "uk_UA-ukrainian_tts-medium",
                "de": "de_DE-thorsten-medium", "es": "es_ES-davefx-medium"}


def piper_installed() -> bool:
    import importlib.util

    return importlib.util.find_spec("piper") is not None


def piper_model(lang: str, voice: str | None = None) -> Path:
    """SHORTS_PIPER_MODEL = path to .onnx or a voice name; else the default voice for the language.
    Voices are downloaded once into SHORTS_CACHE/piper (rhasspy/piper-voices on Hugging Face)."""
    want = os.environ.get("SHORTS_PIPER_MODEL") or (voice if voice and "_" in voice else None) or \
        PIPER_VOICES.get(lang[:2], PIPER_VOICES["en"])
    if Path(want).expanduser().exists():
        return Path(want).expanduser()
    d = models_dir("piper")
    onnx = d / f"{want}.onnx"
    if not onnx.exists():
        run([sys.executable, "-m", "piper.download_voices", want, "--download-dir", d], timeout=600)
    if not onnx.exists():
        raise ShortsError(f"piper voice {want} not found and could not be downloaded")
    return onnx


def _piper(text: str, voice: str, speed: float, out: Path, lang: str = "ru") -> None:
    if not piper_installed():
        raise ShortsError("piper is not installed: `python3 -m pip install piper-tts`")
    model = piper_model(lang, voice)
    run([sys.executable, "-m", "piper", "--model", model, "--length-scale", f"{1 / speed:.3f}", "--output-file", out],
        input=text.encode(), timeout=600)


def whisper_boundaries(audio: Path, lang: str) -> list[tuple[str, float, float]] | None:
    """Real word timings for engines without word boundaries (piper, openai): faster-whisper on our own audio.
    None if faster-whisper is not installed."""
    try:
        from ..adapters.film import transcribe
    except ImportError:
        return None
    try:
        words = transcribe(audio, lang=lang[:2], model=os.environ.get("SHORTS_WHISPER_MODEL", "base"), cache=False)
    except ShortsError:
        return None
    return [(w["w"], w["s"], w["e"]) for w in words] or None


def _silent(text: str, out: Path, speed: float) -> None:
    dur = max(0.8, len(tokenize(text)) * 0.36 / speed + 0.2)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.zeros(int(dur * SR), dtype=np.int16).tobytes())


def available_engines() -> list[str]:
    eng = ["voiceengine"] if _ve().available() else []
    eng.append("edge")
    if os.environ.get("ELEVENLABS_API_KEY"):
        eng.append("elevenlabs")
    if os.environ.get("OPENAI_API_KEY"):
        eng.append("openai")
    if piper_installed():
        eng.append("piper")
    return eng


def _native(engine: str, v: str) -> bool:
    """Is `v` a voice id of this engine itself (not a VoiceEngine attribute string)?"""
    VE = _ve()
    if engine == "edge":
        return bool(VE._EDGE_ID.match(v)) or v in VOICES["edge"].values()
    if engine == "openai":
        return v.lower() in VE.OPENAI_VOICES
    if engine == "piper":
        return bool(VE._PIPER_ID.match(v)) or Path(v).suffix == ".onnx"
    if engine == "elevenlabs":
        return bool(_ELEVEN_ID.fullmatch(v))
    return True


def resolve_voice(engine: str, voice: str | None, lang: str) -> str:
    engine = engine_name(engine)
    if engine == "voiceengine":
        return _ve().attrs_for(voice, lang)
    v = voice or DEFAULT_VOICE.get(lang, "en-male-1")
    table = VOICES.get(engine, {})
    if v in table:
        return table[v]
    if voice and engine in ("edge", "openai", "piper", "elevenlabs") and not _native(engine, v):
        # a VoiceEngine voice ("ж, 72, voice=Валя") on a fallback engine: the stock voice of the same gender
        g = _ve().gender_of(v, lang) or "male"
        alias = f"{lang[:2]}-{g}-1"
        if engine in ("piper", "elevenlabs"):
            return ""          # language default (piper) / ELEVENLABS_VOICE_ID
        return table.get(alias) or table.get(DEFAULT_VOICE.get(lang[:2], "en-male-1")) or VOICES["edge"]["en-male-1"]
    return v


def _cache_voice(engine: str, v: str, lang: str) -> str:
    """Voice part of the cache key. VoiceEngine also keys the language (it is forced) and its revision."""
    return f"{v}|{lang[:2]}|{_ve().REV}" if engine == "voiceengine" else v


def _chain(engine: str | None) -> list[str]:
    forced = os.environ.get("SHORTS_TTS")
    if forced:
        return [engine_name(forced)]
    e = engine_name(engine)
    return available_engines() if e in ("auto", "") else [e]


def cached(text: str, *, lang: str, engine: str = "auto", voice: str | None = None, speed: float = 1.0) -> Speech | None:
    """Cache-only lookup (no network, no synthesis): lint / planning use the real timings once a line was voiced."""
    for eng in _chain(engine):
        if eng == "voiceengine" and not _ve().supports(lang, voice):
            continue
        v = resolve_voice(eng, voice, lang)
        hit = _cache_get(_key(eng, _cache_voice(eng, v, lang), speed, text))
        if hit:
            return hit
    return None


def synth(text: str, *, lang: str, engine: str = "auto", voice: str | None = None, speed: float = 1.0) -> Speech:
    chain = _chain(engine)
    errors = []
    for eng in chain:
        if eng == "voiceengine" and not _ve().supports(lang, voice):
            errors.append(f"voiceengine: only ru / en and its own voices (got lang={lang}, voice={voice})")
            continue
        v = resolve_voice(eng, voice, lang)
        key = _key(eng, _cache_voice(eng, v, lang), speed, text)
        hit = _cache_get(key)
        if hit:
            return hit
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "raw.audio"
            try:
                if eng == "voiceengine":
                    r = _ve().speak(text, tmp, voice=voice, lang=lang, speed=speed)
                    words, est = r["words"], r["estimated"]
                elif eng == "edge":
                    words = _align_words_to_text(text, _edge_sync(text, v, speed, tmp))
                    est = False
                elif eng == "elevenlabs":
                    words = _align_words_to_text(text, _elevenlabs(text, v, speed, tmp))
                    est = False
                elif eng in ("openai", "piper", "silent"):
                    {"openai": lambda: _openai(text, v, speed, tmp), "piper": lambda: _piper(text, v, speed, tmp, lang),
                     "silent": lambda: _silent(text, tmp, speed)}[eng]()
                    bounds = whisper_boundaries(tmp, lang) if eng != "silent" else None
                    if bounds:
                        words, est = _align_words_to_text(text, bounds), False
                    else:
                        words, est = estimate_words(text, media_duration(tmp)), True
                else:
                    raise ShortsError(f"unknown TTS engine {eng}")
                return _cache_put(key, tmp, words, eng, v, est)
            except Exception as e:  # try the next engine in the chain
                log.warning("TTS %s failed: %s", eng, e)
                errors.append(f"{eng}: {e}")
    raise ShortsError("all TTS engines failed: " + "; ".join(errors))
