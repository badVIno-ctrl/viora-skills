"""Edits and cut-downs: find the best moments, cut on the beat, build plans.

Signals for a moment (EDITS.md):
  heatmap   YouTube "most replayed" (yt-dlp), the main signal: real viewer behaviour
  loudness  momentary loudness peaks (ffmpeg ebur128)
  cuts      scene-change density (ffmpeg scene score): action is cut faster
  speech    transcript density / sentence ends (faster-whisper if installed, or a given transcript)
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from ..config import cache_dir, models_dir
from ..engine.audio import beats as audio_beats
from ..util import ShortsError, log, write_json
from .media import download_section, is_url, search, video_meta


# ---------------------------------------------------------------- signals

def loudness_curve(path: Path, step: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=metadata=0",
                        "-f", "null", "-"], capture_output=True)
    ts, ms = [], []
    for m in re.finditer(r"t:\s*([\d.]+)\s+TARGET:.*?M:\s*(-?[\d.]+|-inf)", p.stderr.decode(errors="replace")):
        ts.append(float(m.group(1)))
        ms.append(-70.0 if m.group(2) == "-inf" else float(m.group(2)))
    if not ts:
        return np.array([0.0]), np.array([-70.0])
    t, v = np.array(ts), np.array(ms)
    grid = np.arange(0, t[-1], step)
    return grid, np.interp(grid, t, v)


def scene_cuts(path: Path, thr: float = 0.3) -> list[float]:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
                        f"scale=160:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"], capture_output=True)
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", p.stderr.decode(errors="replace"))]


def transcribe(path: Path, lang: str | None = None, model: str = "base", cache: bool = True) -> list[dict]:
    """Word timings with faster-whisper (optional dependency). Result cached in SHORTS_CACHE/transcripts,
    the model itself in SHORTS_CACHE/whisper (downloaded once)."""
    key = cache_dir("transcripts") / f"{path.stem}-{model}-{lang or 'auto'}.json"
    if cache and key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise ShortsError("faster-whisper is not installed: `uv pip install faster-whisper`, or pass --transcript") from e
    # decode with ffmpeg ourselves: avoids PyAV version issues inside faster-whisper
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, np.float32)
    wm = _whisper_model(model)
    segs, _ = wm.transcribe(audio, language=lang, word_timestamps=True, vad_filter=True)
    words = [{"w": w.word.strip(), "s": round(float(w.start), 3), "e": round(float(w.end), 3)} for s in segs for w in (s.words or [])
             if w.word.strip()]
    if cache:
        key.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


_WM: dict = {}


def _whisper_model(model: str):
    from faster_whisper import WhisperModel

    if model not in _WM:
        _WM[model] = WhisperModel(model, device="cpu", compute_type="int8", download_root=str(models_dir("whisper")))
    return _WM[model]


def _norm(x: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(x, 5), np.percentile(x, 98)
    return np.clip((x - lo) / max(1e-6, hi - lo), 0, 1)


def score_timeline(duration: float, heatmap: list[dict] | None, loud: tuple[np.ndarray, np.ndarray] | None,
                   cuts: list[float] | None, words: list[dict] | None, step: float = 0.5) -> tuple[np.ndarray, np.ndarray, dict]:
    grid = np.arange(0, max(step, duration), step)
    parts: dict[str, np.ndarray] = {}
    weights = {"heatmap": 0.5, "loudness": 0.2, "cuts": 0.2, "speech": 0.1}
    if heatmap:
        hv = np.zeros_like(grid)
        for h in heatmap:
            hv[(grid >= h["start_time"]) & (grid < h["end_time"])] = h["value"]
        parts["heatmap"] = hv
    if loud is not None and len(loud[0]) > 2:
        parts["loudness"] = _norm(np.interp(grid, loud[0], loud[1]))
    if cuts:
        dens = np.zeros_like(grid)
        for c in cuts:
            dens += np.exp(-((grid - c) ** 2) / (2 * 1.5 ** 2))
        parts["cuts"] = _norm(dens)
    if words:
        sp = np.zeros_like(grid)
        for w in words:
            sp[int(w["s"] / step):int(w["e"] / step) + 1] += 1
        parts["speech"] = _norm(sp)
    if not parts:
        raise ShortsError("no signals for moments (no heatmap and no media to analyse)")
    tot_w = sum(weights[k] for k in parts)
    score = sum(parts[k] * weights[k] for k in parts) / tot_w
    k = int(2 / step)
    smooth = np.convolve(score, np.ones(k) / k, mode="same")
    return grid, smooth, parts


HEAD_SKIP = 0.02  # first 2% of a film: logos, titles
TAIL_SKIP = 0.08  # last 8%: credits (a text detector covers longer credits)
SECTIONS = 8  # "places" of a film for diversity: no more than MAX_PER_SECTION moments from one place
MAX_PER_SECTION = 2


def content_penalty(grid: np.ndarray, screens: dict | None) -> tuple[np.ndarray, np.ndarray]:
    """Per grid step: soft multiplier (text and black lower the score) and a hard mask (never pick).

    Hard: text screens that last >= 2 s (credits, title cards) and black runs, both widened by 1 s.
    Soft: a single text-like sample (a sign in the picture) lowers the score but does not forbid it."""
    mult = np.ones_like(grid, dtype=np.float64)
    hard = np.zeros_like(grid, dtype=bool)
    if not screens or not screens.get("t"):
        return mult, hard
    from ..analysis.screens import text_runs

    t = np.array(screens["t"], np.float64)
    tx = np.interp(grid, t, np.array(screens["text"], np.float64), left=0, right=0)
    mult *= 1 - 0.7 * np.clip(tx, 0, 1)
    for a, b in text_runs(screens["t"], screens["text"]):
        if b - a >= 2.0 - 1e-6:
            hard |= (grid >= a - 1.0) & (grid < b + 1.0)
    blk = np.array(screens.get("black") or [False] * len(t), bool)
    step = t[1] - t[0] if len(t) > 1 else 1.0
    for tb in t[blk]:
        hard |= (grid >= tb - 1.0) & (grid < tb + step + 1.0)
    return mult, hard


def pick_windows(grid: np.ndarray, score: np.ndarray, n: int, length: float, gap: float, skip_head: float = 0.0,
                 skip_tail: float = 0.0, hard: np.ndarray | None = None, sections: int = 1,
                 max_per_section: int | None = None) -> list[tuple[float, float, float]]:
    """Best non-overlapping windows. `hard` marks forbidden steps (text screens, black).

    Diversity: the usable part of the film is split into `sections` places; one place gives at most
    `max_per_section` windows while other places still have candidates."""
    step = grid[1] - grid[0] if len(grid) > 1 else 0.5
    win = max(1, int(round(length / step)))
    if len(score) < win:
        return []
    csum = np.concatenate([[0], np.cumsum(score)])
    means = (csum[win:] - csum[:-win]) / win
    bad = np.zeros(len(means), bool)
    if hard is not None and hard.any():
        hs = np.concatenate([[0], np.cumsum(hard.astype(np.int32))])
        bad = (hs[win:] - hs[:-win]) > 0
    starts = grid[: len(means)]
    end_limit = grid[-1] + step - skip_tail
    lo, hi = skip_head, max(skip_head + length, end_limit)
    sec_len = max(length, (hi - lo) / max(1, sections))
    order = np.argsort(-means, kind="stable")
    chosen: list[tuple[float, float, float]] = []
    per: dict[int, int] = {}
    deferred: list[tuple[float, float, float]] = []
    for i in order:
        s = float(starts[i])
        if bad[i] or s < skip_head or s + length > end_limit:
            continue
        if not all(abs(s - c[0]) >= length + gap for c in chosen):
            continue
        sec = int((s - lo) // sec_len)
        if max_per_section and per.get(sec, 0) >= max_per_section:
            deferred.append((s, s + length, float(means[i])))
            continue
        per[sec] = per.get(sec, 0) + 1
        chosen.append((s, s + length, float(means[i])))
        if len(chosen) >= n:
            break
    for d in deferred:  # only when the film has too few places
        if len(chosen) >= n:
            break
        if all(abs(d[0] - c[0]) >= length + gap for c in chosen):
            chosen.append(d)
    return chosen


def section_of(t: float, duration: float, sections: int = SECTIONS) -> int:
    lo, hi = duration * HEAD_SKIP, duration * (1 - TAIL_SKIP)
    return int(min(sections - 1, max(0, (t - lo) // max(1e-6, (hi - lo) / sections))))


def analysis_copy(url: str) -> Path:
    """Low-res copy for loudness, cuts and screens (a URL is downloaded once at 240p, cached)."""
    return download_section(url, max_height=240) if is_url(url) else Path(url)


def find_moments(url: str, n: int = 10, min_len: float = 2.5, max_len: float = 6.0, deep: bool = False,
                 plan_dir: Path | None = None, heatmap: list[dict] | None = None,
                 screens: bool = True) -> list[dict]:
    """Best moments of a film. Heatmap is the main signal; text screens, black frames, the first 2% and the
    last 8% are excluded; moments come from different places of the film."""
    meta = video_meta(url) if is_url(url) else {"duration": None, "heatmap": None, "title": Path(url).name}
    heat = heatmap or meta.get("heatmap")
    loud = cuts = None
    path: Path | None = None
    if deep or not heat or screens:
        path = analysis_copy(url)
    if path is not None and (deep or not heat):
        loud = loudness_curve(path)
        cuts = scene_cuts(path)
    scr = None
    if path is not None and screens:
        from ..analysis.screens import film_screens

        scr = film_screens(path)
    duration = meta.get("duration") or (scr["t"][-1] + 1 if scr else None) or float(loud[0][-1] if loud else 0)
    if not duration and path is not None:
        from ..engine.clips import video_info

        duration = video_info(path)["duration"]
    grid, score, parts = score_timeline(duration, heat, loud, cuts, None)
    mult, hard = content_penalty(grid, scr)
    score = score * mult
    length = (min_len + max_len) / 2
    wins = pick_windows(grid, score, n, length, gap=1.0, skip_head=duration * HEAD_SKIP,
                        skip_tail=duration * TAIL_SKIP, hard=hard, sections=SECTIONS,
                        max_per_section=MAX_PER_SECTION)
    out = []
    step = grid[1] - grid[0]
    for s, e, sc in wins:
        i0, i1 = int(round(s / step)), int(round(e / step))
        sig = {k: round(float(v[i0:i1].mean()), 3) for k, v in parts.items()}
        if scr:
            sig["text"] = round(float(1 - mult[i0:i1].min()), 3)
        peak = s + float(np.argmax(score[i0:i1])) * step if i1 > i0 else s
        out.append({"start": round(s, 2), "end": round(e, 2), "peak": round(peak, 2), "score": round(sc, 3),
                    "section": section_of(s, duration), "signals": sig})
    log.info("moments for %s: %d (signals: %s%s)", meta.get("title"), len(out), ", ".join(parts),
             ", screens" if scr else "")
    return out


# ---------------------------------------------------------------- music

def music_file(src: str, plan_dir: Path | None = None) -> Path:
    if is_url(src):
        return download_section(src, audio_only=True)
    from ..plan import resolve_ref

    p = resolve_ref(src, plan_dir)
    if not p:
        raise ShortsError(f"music not found: {src}")
    return p


def music_beats(src: str) -> dict:
    p = music_file(src)
    key = cache_dir("beats") / f"{p.stem}.json"
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    b = audio_beats(p)
    key.write_text(json.dumps(b), encoding="utf-8")
    return b


def best_music_window(b: dict, length: float) -> float:
    t, r = np.array(b["energy"]["t"]), np.array(b["energy"]["rms"])
    if len(t) < 3 or t[-1] <= length:
        return 0.0
    step = t[1] - t[0]
    win = max(1, int(length / step))
    cs = np.concatenate([[0], np.cumsum(r)])
    means = (cs[win:] - cs[:-win]) / win
    i = int(np.argmax(means[: max(1, len(means))]))
    start = float(t[i])
    downs = [d for d in b["downbeats"] if d <= start + 1e-6]
    return downs[-1] if downs else start  # start on a downbeat


def beat_cuts(b: dict, start: float, length: float, target_shot: float = 1.6, fps: int = 30) -> list[float]:
    """Cut points (relative to `start`) on STRONG beats: bar beats 1 and 3 (stride 2) or downbeats only
    (stride 4), whichever gives shots closer to `target_shot`. Every cut is snapped to a frame (1/fps)."""
    beat = 60.0 / max(40.0, float(b["tempo"]))
    stride = min((2, 4), key=lambda s: abs(s * beat - target_shot))
    bt = [x - start for x in b["beats"] if start - 1e-6 <= x <= start + length + 1e-6]
    q = lambda x: round(round(x * fps) / fps, 4)  # noqa: E731
    end = q(length)
    if len(bt) < 2:
        n = max(1, int(length / target_shot))
        return sorted({q(i * length / n) for i in range(n)} | {end})
    downs = {round(d - start, 3) for d in b["downbeats"]}
    first = next((i for i, x in enumerate(bt) if round(x, 3) in downs), 0)
    cuts = [0.0] + [q(x) for x in bt[first::stride] if 0.3 < x < length - 0.3] + [end]
    return sorted(set(cuts))


def strong_beats(b: dict, start: float, length: float) -> list[float]:
    """Strong beats inside the music window, relative to `start`: downbeats and bar beat 3 (4/4)."""
    bt = list(b.get("beats") or [])
    downs = set(round(d, 3) for d in b.get("downbeats") or [])
    phase = next((i for i, x in enumerate(bt) if round(x, 3) in downs), 0)
    strong = {round(x, 3) for i, x in enumerate(bt) if (i - phase) % 2 == 0} | downs
    return sorted(round(x - start, 3) for x in strong if start - 1e-6 <= x <= start + length + 1e-6)


def music_energy_at(b: dict, t_abs: list[float]) -> list[float]:
    t, r = np.array(b["energy"]["t"], float), np.array(b["energy"]["rms"], float)
    if len(t) < 2:
        return [0.0] * len(t_abs)
    return [float(np.interp(x, t, r)) for x in t_abs]


def assemble_shots(moments: list[dict], shots: list[tuple[float, float]], energy: list[float] | None = None,
                   slow_rate: float = 0.5) -> list[dict]:
    """Which moment fills which beat slot.

    - shot 1 starts ON the peak of the best moment (the first frame is the best frame);
    - the hero shot (loudest music in the middle) shows the second best moment slowed down around its peak;
    - the last shot ends exactly where the first one starts (same moment), so the video loops seamlessly;
    - the other shots walk through the remaining moments in film order, one piece each, so neighbouring
      shots come from different places (never more than 2 in a row from one place)."""
    if not moments:
        raise ShortsError("no moments")
    n = len(shots)
    best = max(moments, key=lambda m: m["score"])
    rest = sorted((m for m in moments if m is not best), key=lambda m: m["start"])
    hero_m = max(rest, key=lambda m: m["score"]) if rest else best
    hero = None
    if n >= 4:
        mid = range(1, n - 1)
        if energy and len(energy) == n:
            hero = max(mid, key=lambda i: (energy[i], -abs(i - 0.6 * n)))
        else:
            hero = min(mid, key=lambda i: abs(i - 0.6 * n))
    walk = [m for m in rest if m is not hero_m] or rest or [best]
    d_last = shots[-1][1] - shots[-1][0] if n >= 3 else 0.0
    # first frame on the peak, but late enough that the loop piece before it stays inside the moment window
    first_in = min(max(float(best["peak"]), float(best["start"]) + d_last), float(best["end"]))
    cursor = {id(m): float(m["start"]) for m in walk}
    out: list[dict] = []
    k = 0
    for i, (a, z) in enumerate(shots):
        d = z - a
        if i == 0:
            src_in, m, rate, role = first_in, best, 1.0, "best"
        elif i == n - 1 and n >= 3 and first_in - d >= 0:
            src_in, m, rate, role = first_in - d, best, 1.0, "loop"
        elif i == hero:
            span = d * slow_rate
            src_in, m, rate, role = max(0.0, float(hero_m["peak"]) - span / 2), hero_m, slow_rate, "hero"
        else:
            for _ in range(len(walk) * 2 + 1):
                m = walk[k % len(walk)]
                k += 1
                c = cursor[id(m)]
                if c + d <= m["end"] + 0.8:
                    break
                cursor[id(m)] = float(m["start"]) + 0.4  # this moment is used up: start again with an offset
            src_in, rate, role = cursor[id(m)], 1.0, "walk"
            cursor[id(m)] = src_in + d + 0.25
        out.append({"slot": i, "in": round(src_in, 3), "out": round(src_in + d * rate, 3), "duration": round(d, 4),
                    "rate": rate, "role": role, "moment": m["start"], "section": m.get("section", 0),
                    "score": m["score"]})
    _limit_runs(out)
    return out


def max_run_same_section(shots: list[dict]) -> int:
    best = run = 0
    prev = None
    for s in shots:
        run = run + 1 if s["section"] == prev else 1
        prev = s["section"]
        best = max(best, run)
    return best


def _limit_runs(shots: list[dict], limit: int = 2) -> None:
    """Swap walk shots so that no more than `limit` shots in a row come from one place."""
    for _ in range(len(shots)):
        bad = None
        run, prev = 0, None
        for i, s in enumerate(shots):
            run = run + 1 if s["section"] == prev else 1
            prev = s["section"]
            if run > limit and s["role"] == "walk":
                bad = i
                break
        if bad is None:
            return
        for j in range(len(shots)):
            o = shots[j]
            if o["role"] == "walk" and o["section"] != shots[bad]["section"] and abs(j - bad) > 1 and \
                    abs(o["duration"] - shots[bad]["duration"]) < 1e-3:
                keep = ("slot", "duration")
                a = {k: v for k, v in shots[bad].items() if k not in keep}
                shots[bad].update({k: v for k, v in o.items() if k not in keep})
                o.update(a)
                break
        else:
            return


# ---------------------------------------------------------------- plans

DEFAULT_MUSIC = "assets/audio/bed.mp3"  # generated placeholder (make_assets.py): only with --music builtin


def edit_plan(video: str | None, music: str | None = None, length: float = 24.0, name: str = "film-edit",
              title: str = "", lang: str = "ru", n: int = 10, query: str | None = None, links: list[str] | None = None,
              handle: str = "", platforms: list[str] | None = None, brand: str = "mono",
              heatmap: list[dict] | None = None, fps: int = 30) -> dict:
    """Film edit cut on strong beats (see `assemble_shots` for what goes where). 2.2: the track is required."""
    from .edit2 import need_music

    music, synthetic_music = need_music(music, "classic edit")
    if synthetic_music:
        music = DEFAULT_MUSIC
    if not video:
        if not query:
            raise ShortsError("give --video URL or --query")
        res = [r for r in search(query, 10) if r.get("duration")]
        if not res:
            raise ShortsError(f"nothing found for '{query}'")
        video = max(res, key=lambda r: r["duration"])["url"]
    moments = find_moments(video, n=n, min_len=2.0, max_len=5.0, heatmap=heatmap)
    if not moments:
        raise ShortsError("no moments found (the whole film looks like text screens or black frames?)")
    b = music_beats(music)
    m_start = best_music_window(b, length)
    cuts = beat_cuts(b, m_start, length, fps=fps)
    shots = list(zip(cuts, cuts[1:]))
    energy = music_energy_at(b, [m_start + a for a, _ in shots])
    plan_shots = assemble_shots(moments, shots, energy)
    scenes = []
    hero_t = None
    for sh in plan_shots:
        i = sh["slot"]
        sc = {"id": f"shot-{i + 1:02d}", "why": f"{sh['role']}: moment {sh['moment']}s (score {sh['score']})",
              "duration": sh["duration"],
              "source": {"type": "film", "ref": video, "in": sh["in"], "out": sh["out"]}}
        if sh["rate"] != 1.0:
            sc["speed"] = [{"t": 0, "rate": sh["rate"]}]
            sc["why"] += "; slow-mo on the peak"
            hero_t = shots[i][0]
        if i == 0 and title:
            sc["on_screen_text"] = title
        scenes.append(sc)
    downs = [round(d - m_start, 3) for d in b["downbeats"] if m_start <= d <= m_start + length]
    ctas = []
    total = cuts[-1]
    if handle:
        ctas.append({"t": round(total * 0.5, 2), "duration": 2.0, "kind": "handle", "text": handle})
    if links:
        ctas.append({"t": round(max(0.0, total - 3.2), 2), "duration": 3.0, "kind": "qr", "url": links[0]})
    plan = {
        "schema_version": "1.1",
        "meta": {"name": name, "language": lang, "platforms": platforms or ["youtube_shorts"],
                 "duration_target": [max(10, length - 6), length + 6], "emotion": "energy", "audience": "film fans",
                 "loop": True, "fps": fps},
        "layout": {"mode": "center_only", "cta_in_center": ctas},
        "brand": {"preset": brand},
        "captions": {"enabled": True, "max_words": 3, "highlight": "accent"},
        "audio": {"voice": {"engine": "auto"}, "music": {"source": music, "start": round(m_start, 3), "beat_sync": True},
                  "target_lufs": -14, "sfx_auto": False, "sfx": "off"},
        "fx": {"punch": [c for c in cuts[1:-1] if any(abs(c - d) < 0.06 for d in downs)],
               "flash": [hero_t] if hero_t is not None else downs[len(downs) // 2: len(downs) // 2 + 1]},
        "scenes": scenes,
        "metadata": {"topic": title, "source_video": video, "moments": moments[:n],
                     "hashtags": ["shorts", "edit", "movie", "film"] + ([re.sub(r"\W", "", title.lower())] if title else []),
                     "music": {"tempo": b["tempo"], "start": m_start, "cuts": cuts,
                               "strong_beats": strong_beats(b, m_start, length)}},
    }
    return plan


def clips_plans(video: str, out_dir: Path, n: int = 3, length: float = 30.0, lang: str = "ru",
                transcript: str | None = None, layout: str = "center_only", brand: str = "mono",
                platforms: list[str] | None = None) -> list[Path]:
    """Long video -> n plans of `length` s. Windows by loudness + cuts + speech, snapped to sentence starts."""
    path = download_section(video, max_height=1080) if is_url(video) else Path(video).resolve()
    if not path.exists():
        raise ShortsError(f"video not found: {video}")
    from ..engine.clips import video_info

    info = video_info(path)
    words: list[dict] = []
    if transcript:
        words = json.loads(Path(transcript).read_text(encoding="utf-8"))
    else:
        try:
            words = transcribe(path, lang if lang != "auto" else None)
        except ShortsError as e:
            log.warning("%s; cutting without captions", e)
    heat = video_meta(video).get("heatmap") if is_url(video) else None
    loud = loudness_curve(path)
    cuts = scene_cuts(path)
    grid, score, parts = score_timeline(info["duration"], heat, loud, cuts, words)
    wins = pick_windows(grid, score, n, length, gap=2.0)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    sent_starts = [w["s"] for i, w in enumerate(words) if i == 0 or re.search(r"[.!?]$", words[i - 1]["w"])]
    for k, (s, e, sc) in enumerate(sorted(wins), 1):
        if sent_starts:
            s = min(sent_starts, key=lambda x: abs(x - s) if x <= s + 2 else 1e9)
            e = s + length
            # end on a sentence end if the clip keeps >= 60% of the target, else after the last whole word
            ends = [w["e"] for w in words if s + 0.6 * length <= w["e"] <= e + 1.5 and re.search(r"[.!?]$", w["w"])]
            if ends:
                e = max(ends)
            else:
                last = [w["e"] for w in words if s < w["e"] <= e + 0.2]
                inside = [w for w in words if w["s"] < e < w["e"]]
                if inside:
                    e = inside[0]["e"] + 0.05
                elif last and e - max(last) < 1.0:
                    e = max(last) + 0.05
        # split into 3 scenes so the plan has structure (and punch-in at each cut)
        nsc = 3
        bounds = [s + (e - s) * i / nsc for i in range(nsc + 1)]
        if words:  # never cut inside a word
            for i in range(1, nsc):
                inside = [w for w in words if w["s"] < bounds[i] < w["e"]]
                if inside:
                    bounds[i] = inside[0]["e"] + 0.01
        scenes = []
        for i in range(nsc):
            a, z = bounds[i], bounds[i + 1]
            tw = [{"w": w["w"], "s": round(w["s"] - a, 3), "e": round(min(w["e"], z) - a, 3)} for w in words if a <= w["s"] < z]
            scenes.append({"id": f"part-{i + 1}", "why": f"window score {sc:.2f}", "duration": round(z - a, 3),
                           "source": {"type": "video", "ref": str(path), "in": round(a, 3), "out": round(z, 3),
                                      "keep_audio": True},
                           **({"transcript": tw} if tw else {})})
        plan = {
            "schema_version": "1",
            "meta": {"name": f"clip-{k}", "language": lang, "platforms": platforms or ["youtube_shorts"],
                     "duration_target": [max(10, length - 10), length + 15], "loop": False},
            "layout": {"mode": layout, "cta_in_center": []},
            "brand": {"preset": brand},
            "captions": {"enabled": True, "max_words": 3, "highlight": "accent"},
            "audio": {"voice": {"engine": "auto"}, "target_lufs": -14, "sfx_auto": False},
            "fx": {"punch": [round(b - s, 3) for b in bounds[1:-1]]},
            "scenes": scenes,
            "metadata": {"source_video": str(path), "window": [round(s, 2), round(e, 2)],
                         "signals": {kk: round(float(v[int(s / 0.5):int(e / 0.5)].mean()), 3) for kk, v in parts.items()},
                         "transcript_words": len(words)},
        }
        f = out_dir / f"clip-{k}.plan.json"
        write_json(f, plan)
        files.append(f)
    return files
