"""2.4 music rule: when the user did not name a track, the agent finds a fitting one on YouTube and uses it.

  "auto"   default for plans, toon episodes, stack specs and edits: search YouTube by mood / genre (from the
           brief or guessed from the topic), rank the results, download only the needed piece through the fetch
           ladder, measure beats, start on a downbeat, credit the track in the description (pack does it).
  "none"   only when the user asked for no music.
  a file or URL: the user's choice, never replaced.

Result per project: music.json (track, start, drop, tempo, credit, alternatives, status). It is reused on the next
render; delete it or run `music-find --force` for another track. If YouTube blocks downloads after the whole
fetch ladder, the video is made without music and music.json carries one ready command for the user's computer.
Rights: free-to-use tracks are preferred and credited; the publisher still checks the licence (pack says it).
SHORTS_MUSIC_AUTO=off turns the search off (tests, offline runs): "auto" then means no music.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from pathlib import Path

from .util import ShortsError, log

AUTO = "auto"
NONE = {"none", "off", "no", "false", "без музыки", "нет", "без"}

# mood -> (words that point to it in a brief / topic, English search phrase)
MOODS: dict[str, tuple[tuple[str, ...], str]] = {
    "tense": (("напряж", "трилл", "саспенс", "выжив", "зомби", "блэкаут", "хоррор", "страш", "ужас", "тревог", "опасн",
               "катастроф", "апокалип", "tense", "thriller", "suspense", "horror", "survival", "zombie", "danger"),
              "dark suspense tension background"),
    "epic": (("эпич", "кино", "трейлер", "героич", "битв", "война", "космос", "epic", "cinematic", "trailer", "battle",
              "space"), "epic cinematic"),
    "energetic": (("энерг", "бодр", "драйв", "спорт", "мотивац", "тренир", "фитнес", "быстр", "hype", "energetic",
                   "upbeat", "sport", "motivation", "workout"), "energetic upbeat"),
    "phonk": (("фонк", "эдит", "дрифт", "сигма", "phonk", "edit", "drift", "sigma"), "phonk"),
    "sad": (("грус", "печал", "драм", "ностальг", "одинок", "трогат", "sad", "drama", "nostalg", "emotional"),
            "sad emotional piano"),
    "calm": (("спокой", "уют", "расслаб", "медитац", "чилл", "лоуфай", "сад", "огород", "дача", "кофе", "calm", "chill",
              "lofi", "relax", "cozy", "garden"), "lofi chill"),
    "happy": (("весел", "смешн", "юмор", "комед", "позитив", "детск", "мульт", "радуг", "happy", "funny", "comedy",
               "kids", "cartoon", "cheerful"), "happy cheerful ukulele"),
    "tech": (("технол", "нейросет", "ии ", "искусствен", "гаджет", "код", "програм", "сайт", "футур", "кибер", "tech",
              "ai ", "gadget", "code", "futur", "cyber", "digital"), "futuristic electronic technology"),
    "luxury": (("бизнес", "деньг", "успех", "богат", "лакшер", "инвест", "крипт", "business", "money", "luxury",
                "success", "invest"), "luxury deep house"),
    "mystery": (("загадк", "тайн", "факт", "интересн", "неизвест", "истори", "mystery", "secret", "facts", "history",
                 "unknown"), "mysterious documentary"),
    "inspiring": (("вдохнов", "обучен", "урок", "объясн", "совет", "лайфхак", "инструкц", "inspir", "tutorial",
                   "explain", "tips", "lifehack", "how to"), "inspiring corporate background"),
    "gaming": (("игр", "геймпл", "майнкрафт", "gaming", "gameplay", "minecraft"), "gaming background"),
    "romantic": (("любов", "романт", "свадьб", "love", "romantic", "wedding"), "romantic soft"),
}
ALIASES = {"напряжённый": "tense", "напряженный": "tense", "тревожный": "tense", "эпичный": "epic", "энергичный": "energetic",
           "бодрый": "energetic", "фонк": "phonk", "грустный": "sad", "спокойный": "calm", "лоуфай": "calm", "весёлый": "happy",
           "веселый": "happy", "детский": "happy", "технологичный": "tech", "лакшери": "luxury", "загадочный": "mystery",
           "вдохновляющий": "inspiring", "игровой": "gaming", "романтичный": "romantic"}
FREE_HINTS = ("no copyright", "copyright free", "royalty free", "free to use", "free music", "audio library", "ncs",
              "nocopyrightsounds", "без авторских", "без ап", "creative commons", "cc-by", "cc by", "free download",
              "vlog no copyright", "background music")
FREE_CHANNELS = ("audio library", "nocopyrightsounds", "ncs", "no copyright music", "vlog no copyright music",
                 "free music", "background music", "royalty free", "bensound", "alex-productions", "mixaund",
                 "tunetank", "infraction", "ikson", "streambeats", "pixabay", "free to use")
BAD = {"1 hour": 6, "hour": 4, "hours": 5, "mix": 2.5, "compilation": 4, "playlist": 4, "live": 2, "slowed": 3,
       "reverb": 2, "sped up": 3, "nightcore": 3, "karaoke": 4, "tutorial": 4, "how to": 4, "reaction": 4,
       "#shorts": 3, "shorts": 1.5, "8d": 2, "bass boosted": 2, "full album": 5, "minecraft": 1, "official video": 3,
       "official music video": 4, "cover": 1.5}
VOCAL = ("lyrics", "lyric", "vocal", "song", "feat", "ft.", "текст песни", "песня", "караоке", "singing", "acapella")


def disabled() -> bool:
    return os.environ.get("SHORTS_MUSIC_AUTO", "").strip().lower() in ("0", "off", "no", "false")


def is_auto(src) -> bool:
    if isinstance(src, dict):
        src = src.get("source", src.get("file"))
    return isinstance(src, str) and src.strip().lower() == AUTO


def is_none(src) -> bool:
    if isinstance(src, dict):
        src = src.get("source", src.get("file"))
    return isinstance(src, str) and src.strip().lower() in NONE


# ---------------------------------------------------------------- mood and queries

def mood_of(text: str, default: str = "inspiring") -> str:
    """Best mood for a brief / topic / script (keyword votes)."""
    t = f" {str(text or '').lower()} "
    t = t.replace("ё", "е")
    if t.strip() in ALIASES:
        return ALIASES[t.strip()]
    if t.strip() in MOODS:
        return t.strip()
    votes = {m: sum(t.count(w.replace("ё", "е")) for w in words) for m, (words, _) in MOODS.items()}
    best = max(votes, key=votes.get)
    return best if votes[best] > 0 else default


def queries(mood: str, genre: str | None = None, voice: bool = True, query: str | None = None) -> list[str]:
    if query:
        return [query] + ([f"{query} no copyright music"] if "copyright" not in query.lower() else [])
    phrase = MOODS.get(mood, MOODS["inspiring"])[1]
    if genre:
        phrase = f"{genre} {phrase}" if genre.lower() not in phrase else phrase
    inst = " instrumental" if voice and mood != "phonk" else ""
    return [f"{phrase}{inst} no copyright music", f"{phrase} royalty free music for videos"]


# ---------------------------------------------------------------- ranking

def history_path() -> Path:
    from .config import memory_dir
    return memory_dir() / "music_history.json"


def used_recently(limit: int = 40) -> set[str]:
    p = history_path()
    try:
        return {h["id"] for h in json.loads(p.read_text(encoding="utf-8"))[-limit:]}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def remember(track: dict) -> None:
    p = history_path()
    try:
        h = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except (OSError, ValueError):
        h = []
    h = [x for x in h if x.get("id") != track.get("id")] + [{"id": track.get("id"), "title": track.get("title"),
                                                           "date": time.strftime("%Y-%m-%d")}]
    p.write_text(json.dumps(h[-200:], ensure_ascii=False, indent=1), encoding="utf-8")


def score(item: dict, *, voice: bool = True, length: float = 30.0, used: set[str] | None = None) -> tuple[float, list[str]]:
    """Higher is better. Reasons are kept for the report (why this track)."""
    title = str(item.get("title") or "").lower()
    chan = str(item.get("channel") or "").lower()
    dur = item.get("duration")
    s, why = 0.0, []
    if dur:
        dur = float(dur)
        if dur < max(20.0, length * 0.6):
            s -= 6; why.append("too short")
        elif dur <= 420:
            s += 2.5
        elif dur <= 900:
            s += 0.5
        else:
            s -= 5; why.append("long mix")
        if dur >= length + 10:
            s += 0.5
    if any(h in title for h in FREE_HINTS):
        s += 3; why.append("free-to-use in title")
    if any(c in chan for c in FREE_CHANNELS):
        s += 2.5; why.append("free music channel")
    if "instrumental" in title or "no vocals" in title or "beat" in title:
        s += 1.0
    for w, pen in BAD.items():
        if re.search(rf"(?<![\w]){re.escape(w)}(?![\w])", title):
            s -= pen; why.append(w)
    if voice and any(w in title for w in VOCAL):
        s -= 4; why.append("vocals under a voice-over")
    if item.get("views"):
        s += min(2.0, math.log10(max(1.0, float(item["views"]))) / 3.5)
    if used and item.get("id") in used:
        s -= 3; why.append("used recently")
    return round(s, 2), why


def search(mood: str, *, genre: str | None = None, voice: bool = True, length: float = 30.0, n: int = 12,
           query: str | None = None) -> list[dict]:
    from .adapters import media
    seen, out = set(), []
    used = used_recently()
    errors = []
    for q in queries(mood, genre, voice, query):
        try:
            res = media.search(q, n)
        except Exception as e:  # noqa: BLE001 - one query failing is not the end
            errors.append(str(e)[:160])
            continue
        for r in res:
            if not r.get("id") or r["id"] in seen:
                continue
            seen.add(r["id"])
            sc, why = score(r, voice=voice, length=length, used=used)
            out.append(dict(r, score=sc, why=why, query=q))
    if not out and errors:
        raise ShortsError("YouTube search failed: " + "; ".join(errors[:2]))
    return sorted(out, key=lambda r: -r["score"])


# ---------------------------------------------------------------- download and analysis

def _section(item: dict, length: float) -> tuple[float, float] | None:
    """Only the piece we need (+ margin). Most replayed part when YouTube gives a heatmap, else past the intro."""
    dur = float(item.get("duration") or 0)
    need = length + 8.0
    if not dur or dur <= need + 4:
        return None
    start = None
    try:
        from .adapters.media import video_meta
        hm = (video_meta(item["url"]) or {}).get("heatmap") or []
        if hm:
            best, best_v = None, -1.0
            for h in hm:
                s0 = float(h.get("start_time", 0))
                v = sum(float(x.get("value", 0)) for x in hm
                        if s0 <= float(x.get("start_time", 0)) < s0 + length)
                if s0 + need <= dur and v > best_v:
                    best, best_v = s0, v
            start = best
    except Exception:  # noqa: BLE001 - metadata is a bonus
        start = None
    if start is None:
        start = min(dur * 0.18, 30.0)
    start = max(0.0, min(start - 2.0, dur - need))
    return round(start, 2), round(min(dur, start + need), 2)


def analyze(path: Path, length: float, voice: bool) -> dict:
    """Start on a downbeat with sound (voice-over) or the strongest window (music-led), drop, tempo."""
    try:
        from .adapters.edit2 import detect_drop
        from .adapters.film import best_music_window
        from .engine import audio as A
        b = A.beats(path)
    except Exception as e:  # noqa: BLE001 - no librosa or an odd file: still usable from 0
        return {"start": 0.0, "drop": None, "tempo": None, "beats": [], "note": f"no beat analysis: {str(e)[:120]}"}
    import numpy as np
    t, r = np.array(b["energy"]["t"], float), np.array(b["energy"]["rms"], float)
    dur = float(b.get("duration") or 0)
    if voice or dur <= length + 1:
        med = float(np.median(r)) if len(r) else 0.0
        loud = [float(x) for x, v in zip(t, r) if v >= 0.5 * med]
        first = loud[0] if loud else 0.0
        downs = [d for d in b.get("downbeats") or [] if d >= first - 0.05 and d <= max(0.0, dur - length)]
        start = downs[0] if downs else first
    else:
        start = best_music_window(b, length)
    start = float(max(0.0, min(start, max(0.0, dur - length))))
    try:
        drop = float(detect_drop(b))
    except Exception:  # noqa: BLE001
        drop = None
    return {"start": round(start, 3), "drop": round(drop, 3) if drop is not None else None, "tempo": b.get("tempo"),
            "beats": [x for x in b.get("beats") or [] if start <= x <= start + length][:256], "duration": dur}


def credit(track: dict, lang: str = "ru") -> str:
    url = track.get("url") or ""
    head = "Музыка" if (lang or "ru")[:2] != "en" else "Music"
    return f"{head}: {track.get('title', '').strip()} - {track.get('channel', '').strip()} ({url})".replace("—", "-").replace("–", "-")


def find(*, length: float = 30.0, voice: bool = True, mood: str | None = None, genre: str | None = None,
         query: str | None = None, context: str = "", out_dir: Path, lang: str = "ru", tries: int = 3,
         dry: bool = False) -> dict:
    """Search, rank, download the best piece that works. Never raises on YouTube blocks: status says what happened."""
    from . import fetch as F
    out_dir = Path(out_dir)
    m = mood or mood_of(f"{genre or ''} {context}")
    rep: dict = {"mood": m, "genre": genre, "query": query, "length": round(float(length), 2), "voice": voice,
                 "searched": time.strftime("%Y-%m-%d %H:%M"), "ok": False}
    try:
        cands = search(m, genre=genre, voice=voice, length=length, query=query)
    except ShortsError as e:
        rep.update(status="not_found", error=str(e)[:300])
        return rep
    rep["queries"] = sorted({c["query"] for c in cands})
    rep["alternatives"] = [{k: c.get(k) for k in ("title", "channel", "url", "duration", "score", "why")} for c in cands[:6]]
    good = [c for c in cands if c["score"] > -2][: max(1, tries)]
    if not good:
        rep.update(status="not_found", error="no fitting track in the search results")
        return rep
    if dry:
        rep.update(status="searched", pick=rep["alternatives"][0])
        return rep
    tries_rep, blocked = [], False
    for k, c in enumerate(good):
        sec = _section(c, length)
        name = f"yt-{c['id']}" + (f"-{int(sec[0])}" if sec else "")
        res = F.fetch(c["url"], out_dir / "music", name, sec, audio=True, allow_update=(k == 0))
        tries_rep.append({"url": c["url"], "ok": res["ok"], "steps": len(res.get("attempts") or []),
                          "kinds": sorted({a.get("kind") for a in res.get("attempts") or [] if a.get("kind")})})
        if res["ok"]:
            path = Path(res["path"])
            an = analyze(path, length, voice)
            track = {k2: c.get(k2) for k2 in ("id", "title", "channel", "url", "duration", "score", "why")}
            rep.update(ok=True, status="ok", file=str(path), section=list(sec) if sec else None, track=track,
                       start=an["start"], drop=an.get("drop"), tempo=an.get("tempo"), beats=an.get("beats"),
                       credit=credit(c, lang), note=an.get("note"), tries=tries_rep)
            remember(c)
            return rep
        kinds = {a.get("kind") for a in res.get("attempts") or []}
        rep.setdefault("local_commands", []).append(res.get("local_command"))
        if "bot_block" in kinds and not any(a.get("ok") for a in res.get("attempts") or []):
            blocked = True
            # every candidate hits the same block from this IP: stop after the first full ladder
            if k == 0 and not any("browser" in a.get("step", "") and a.get("ok") for a in res.get("attempts") or []):
                break
    rep.update(status="blocked" if blocked else "not_downloaded", tries=tries_rep,
               track={k2: good[0].get(k2) for k2 in ("id", "title", "channel", "url", "duration", "score")},
               credit=credit(good[0], lang),
               hint="YouTube did not give the audio from this IP after the whole fetch ladder. Run the command on your "
                    "computer, put the file next to the plan and set audio.music.source to it (or send the file).")
    return rep


# ---------------------------------------------------------------- applying "auto"

def _cache_ok(p: Path, length: float) -> dict | None:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if d.get("ok") and d.get("file") and Path(d["file"]).exists() and float(d.get("length", 0)) + 0.5 >= length * 0.8:
        return d
    return None


def resolve(spec, *, length: float, voice: bool, context: str, base: Path, lang: str = "ru", force: bool = False) -> dict:
    """"auto" (or {"source": "auto", "mood", "genre", "query"}) -> music.json content (also written to base)."""
    spec = spec if isinstance(spec, dict) else {"source": spec}
    base = Path(base)
    mj = base / "music.json"
    if disabled():
        return {"ok": False, "status": "disabled", "note": "SHORTS_MUSIC_AUTO=off"}
    if not force:
        hit = _cache_ok(mj, length)
        if hit:
            return hit
    rep = find(length=length + 2.0, voice=voice, mood=spec.get("mood"), genre=spec.get("genre"), query=spec.get("query"),
               context=context, out_dir=base, lang=lang)
    try:
        base.mkdir(parents=True, exist_ok=True)
        mj.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        rep["json"] = str(mj)
    except OSError:
        pass
    return rep


def plan_context(plan: dict) -> str:
    meta = plan.get("meta") or {}
    md = plan.get("metadata") or {}
    parts = [str(meta.get(k) or "") for k in ("emotion", "genre", "niche", "name", "pacing")]
    parts += [str(md.get("topic") or ""), json.dumps(md.get("niche_context") or {}, ensure_ascii=False)[:400]]
    parts += [str(s.get("say") or "") + " " + str(s.get("on_screen_text") or "") for s in plan.get("scenes") or []]
    return " ".join(parts)


def episode_context(ep: dict) -> str:
    parts = [str(ep.get(k) or "") for k in ("title", "slug", "audience", "mood", "genre")]
    parts += [str(s.get("say") or "") for s in ep.get("scenes") or []]
    return " ".join(parts)


def needs_drop(plan: dict) -> bool:
    """Effects or the title bar keyed to the music drop ("drop" as a time)."""
    def has(v) -> bool:
        if isinstance(v, str):
            return v.strip().lower() == "drop"
        if isinstance(v, dict):
            return any(has(x) for x in v.values())
        if isinstance(v, list):
            return any(has(x) for x in v)
        return False
    return has(plan.get("fx") or {}) or has((plan.get("layout") or {}).get("title_bar") or {})


def apply_to_plan(plan: dict, plan_dir: Path, out: Path, total: float, has_voice: bool, lang: str) -> dict | None:
    """Render hook: replaces audio.music.source "auto" by the found file (start, drop_at) in the resolved plan.
    Returns the music.json content, or None when the plan does not ask for auto music."""
    audio = plan.setdefault("audio", {})
    music = audio.get("music")
    if isinstance(music, str):
        music = {"source": music}
    if not isinstance(music, dict) or not is_auto(music.get("source")):
        return None
    base = plan_dir if os.access(plan_dir, os.W_OK) else out
    rep = resolve(music, length=total, voice=has_voice, context=plan_context(plan), base=base, lang=lang)
    m = {k: v for k, v in music.items() if k not in ("mood", "genre", "query")}
    if rep.get("ok"):
        m["source"] = rep["file"]
        m.setdefault("start", rep.get("start", 0.0))
        drop = rep.get("drop")
        if m.get("drop_at") is None and needs_drop(plan) and drop is not None and float(drop) > float(m["start"]):
            dv = float(drop) - float(m["start"])
            if 0.5 < dv < total - 0.5:
                m["drop_at"] = round(dv, 3)
        if plan.get("metadata") is not None and m.get("beat_sync") and rep.get("beats"):
            plan["metadata"]["music"] = {"start": m["start"], "strong_beats": [round(b - m["start"], 3) for b in rep["beats"]]}
    else:
        m["source"] = "none"
        if m.get("drop_at") is None and needs_drop(plan):
            m["drop_at"] = round(min(total * 0.35, 6.0), 2)
    audio["music"] = m
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / "music.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return rep


def credit_for_video(video: Path) -> str | None:
    """Music credit for pack: <video>.music.json or music.json beside the video (written by render / toon / stack)."""
    video = Path(video)
    for p in (video.with_suffix(".music.json"), video.parent / "music.json"):
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if d.get("ok") and d.get("credit"):
                return str(d["credit"])
    return None


LICENCE_NOTE = ("музыка подобрана автоматически: открой ссылку на трек и проверь условия автора "
                "(бесплатно с указанием автора, без монетизации и т.п.)")


def with_credit(item: dict, video: Path | None) -> dict:
    """pack / deliver: the music credit goes into every description variant (copy-ready) + a licence note."""
    mc = credit_for_video(Path(video)) if video else None
    if not mc:
        return item
    it = dict(item)

    def add(t: str | None) -> str:
        t = (t or "").rstrip()
        return t if mc in t else (t + "\n\n" + mc).strip()
    if it.get("descriptions"):
        it["descriptions"] = [dict(d, text=add(d.get("text"))) for d in it["descriptions"]]
    if (it.get("description") or "").strip():
        it["description"] = add(it["description"])
    notes = list(it.get("notes") or [])
    if LICENCE_NOTE not in notes:
        notes.append(LICENCE_NOTE)
    it["notes"] = notes
    it["music_credit"] = mc
    return it


def summary(rep: dict | None) -> str:
    if not rep:
        return "music: as in the plan"
    if rep.get("ok"):
        return f"music: {rep['track'].get('title')} ({rep['track'].get('channel')}), start {rep.get('start')} s"
    if rep.get("status") == "disabled":
        return "music: auto search off (SHORTS_MUSIC_AUTO=off), no music"
    cmd = (rep.get("local_commands") or [None])[0]
    return f"music: {rep.get('status')}, video made without music" + (f"; on your computer: {cmd}" if cmd else "")
