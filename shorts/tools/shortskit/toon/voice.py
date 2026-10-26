"""Voice for toon episodes: TTS per scene (cached, parallel), then voice + music ("auto" = found on YouTube, 2.4) + real SFX files -> -14 LUFS."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..util import ShortsError, run
from .story import parse_say


def make_speaker(ep: dict, engine: str | None = None) -> callable:
    """All lines voiced up front (cached). 2.4: every character can have its own voice (cast.<id>.voice,
    scene voice / tone, see story.scene_voice); the narrator is ep["voice"]."""
    from ..engine import tts
    from .story import scene_voice
    lang = ep.get("lang", "ru")
    eng = engine or ep.get("engine", "auto")
    voice = ep.get("voice")
    speed = float(ep.get("speed", 1.0))
    lines = [(parse_say(s.get("say") or "")[0], scene_voice(ep, s) or voice) for s in ep.get("scenes", [])]
    cache: dict[tuple[str, str | None], dict] = {}

    def one(line: tuple[str, str | None]) -> dict:
        sp = tts.synth(line[0], lang=lang, engine=eng, voice=line[1], speed=speed)
        return {"wav": sp.wav, "duration": sp.duration, "words": sp.words, "estimated": sp.estimated, "engine": sp.engine, "voice": sp.voice}
    todo = [ln for ln in dict.fromkeys(lines) if ln[0]]
    # edge-tts often answers "No audio was received" (worse in parallel): one line at a time + retries; cached afterwards
    workers = max(1, min(4, int(os.environ.get("SHORTS_TTS_WORKERS", "1"))))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for ln, r in zip(todo, ex.map(one, todo)):
            cache[ln] = r
    engines = {r["engine"] for r in cache.values()}
    if len(engines) > 1:   # a scene fell back to another engine -> different voice inside one episode
        raise ShortsError(f"TTS engines mixed inside one episode {sorted(engines)}: rerun (cache keeps the good lines) "
                          "or force one with --engine / SHORTS_TTS")

    def speak(text: str, voice: str | None = None) -> dict:
        ln = (text, voice or ep.get("voice"))
        return cache.get(ln) or one(ln)
    return speak


def cached_speaker(ep: dict) -> callable:
    """Real timings for lines already in the TTS cache, estimates for the rest (no network)."""
    from ..engine import tts
    from .story import estimate
    lang, eng, voice, speed = ep.get("lang", "ru"), ep.get("engine", "auto"), ep.get("voice"), float(ep.get("speed", 1.0))

    def speak(text: str, voice_override: str | None = None, **kw) -> dict:
        vo = kw.get("voice") or voice_override or voice
        try:
            hit = tts.cached(text, lang=lang, engine=eng, voice=vo, speed=speed)
        except Exception:  # noqa: BLE001 - lint must never fail on the cache
            hit = None
        if hit:
            return {"wav": hit.wav, "duration": hit.duration, "words": hit.words, "estimated": hit.estimated, "engine": hit.engine, "voice": hit.voice}
        return estimate(text)
    return speak


def sfx_events(story: dict) -> list[tuple[float, str]]:
    """scene "sfx": ["door"] / [{"name": "door", "t": 1.2}] (t resolved from "on") -> absolute (t, name)."""
    ev = []
    for sc in story["scenes"]:
        for e in sc.get("sfx") or []:
            if isinstance(e, str):
                ev.append((sc["t0"] + 0.05, e))
            elif isinstance(e, dict) and e.get("name"):
                ev.append((sc["t0"] + float(e.get("t", 0.05)), e["name"]))
            elif isinstance(e, (list, tuple)) and len(e) == 2:
                ev.append((sc["t0"] + float(e[1]), str(e[0])))
    return ev


def mix_audio(story: dict, report: dict, ep: dict, base: Path, out_wav: Path) -> dict:
    from ..engine import audio
    parts = [(s["t"], Path(s["wav"])) for s in report.get("speech", []) if s.get("wav")]
    from .. import music as MU
    raw = ep.get("music", "auto")
    music = dict(raw) if isinstance(raw, dict) else ({"file": raw} if raw else {})
    if "source" in music and "file" not in music:
        music["file"] = music.pop("source")
    auto_rep = None
    if MU.is_none(music) or not music.get("file"):
        music = {}
    elif MU.is_auto(music):
        # 2.4: no track named by the user -> a fitting one from YouTube (music.json next to the episode)
        auto_rep = MU.resolve(music, length=float(story["duration"]), voice=True, context=MU.episode_context(ep),
                              base=base, lang=ep.get("lang", "ru"))
        music = {k: v for k, v in music.items() if k not in ("file", "mood", "genre", "query")}
        if auto_rep.get("ok"):
            music["file"] = auto_rep["file"]
            music.setdefault("start", auto_rep.get("start", 0.0))
        else:
            music = {}
    mpath = None
    if music.get("file"):
        mp = Path(music["file"])
        mpath = mp if mp.is_absolute() else (base / mp)
        if not mpath.exists():
            raise ShortsError(f"music file not found: {mpath}")
    events, pol = audio.sfx_policy(sfx_events(story), ep.get("audio") or {})
    rep = audio.mix(story["duration"], parts, [], story["words"], music, mpath, events, out_wav)
    rep.update(sfx=pol, music=str(mpath) if mpath else None, music_placeholder=audio.music_is_synthetic(mpath))
    if auto_rep is not None:
        rep["music_auto"] = {k: auto_rep.get(k) for k in ("status", "track", "start", "credit", "local_commands", "hint", "json")
                             if auto_rep.get(k) is not None}
        rep["music_note"] = MU.summary(auto_rep)
    return rep


def mux(video: Path, wav: Path | None, out: Path) -> Path:
    if wav and wav.exists():
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out])
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-c", "copy", "-movflags", "+faststart", out])
    return out
