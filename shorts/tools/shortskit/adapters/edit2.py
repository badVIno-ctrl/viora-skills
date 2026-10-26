"""Film edit v2: the structure of real edits (CapCut tutorials, research sec. 20).

  0 .. D   a short dialogue line from the film: original sound, subtitles grow in, music quiet under it
  D        the DROP of the track exactly at the end of the line: a flash on it. 2.2: no synthesized riser / hit /
           whoosh (they sounded like "AI bells"): the real track carries the drop. The track is required
           (--music FILE|URL); the generated assets/audio/edit.mp3 is a placeholder, only with --music builtin
  D .. L   hero shots on strong beats (~0.85-1.2 s each) with the velocity curve (fast - hang - fast),
           reframed so the face is in the centre; two longer hero shots (deep hang) on the loud bars;
           the link slides in to the centre twice (about the middle and the last ~2.5 s); the end loops.

Shots: candidates come from YouTube storyboard thumbnails (the whole film, nothing is downloaded), scored by
faces (YuNet), sharpness, contrast, no text screens or black; diverse in time and in look (no "market scene
five times"). Then every candidate is recorded (yt-dlp, or the shared browser when YouTube blocks the
render IP) and refined at full size: one camera shot only, the slow "hang" on the biggest face.
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
from pathlib import Path

import numpy as np

from ..config import asset, cache_dir, models_dir
from ..util import ShortsError, log
from . import ytbrowser as YB
from .media import BotBlock, _BLOCKED, download_section, is_url, video_meta

HEAD_SKIP, TAIL_SKIP = 0.02, 0.08  # opening titles / end credits
DEFAULT_MUSIC = "assets/audio/edit.mp3"  # generated placeholder (make_assets.py, 808 + cowbell): never a default
BUILTIN = ("builtin", "built-in", DEFAULT_MUSIC)


def need_music(music: str | None, kind: str = "edit") -> tuple[str, bool]:
    """(source, synthetic). 2.2: an edit needs a real track; the generated one only when asked for by name."""
    if not music:
        raise ShortsError(f"{kind}: give the track: --music FILE|URL (the trending sound or licensed music; the drop "
                          f"and the cuts are planned on it). The built-in generated track is a placeholder for drafts "
                          f"only: --music builtin")
    if str(music).lower() in BUILTIN:
        log.warning("%s: built-in generated music (placeholder, sounds synthetic): replace it before delivery", kind)
        return DEFAULT_MUSIC, True
    return music, False


# ---------------------------------------------------------------- transcript lines

def _norm_words(t: str) -> list[str]:
    return [w for w in re.sub(r"[^\w\s-]", " ", t.lower().replace("ё", "е")).split() if w]


def film_lines(video: str, lang: str = "ru") -> list[dict]:
    """Transcript lines [{start, end, text}] of the film: YouTube transcript (through the shared browser),
    or faster-whisper for a local file."""
    if is_url(video) and YB.is_youtube(video):
        if not YB.available() and not YB._meta_path(video).exists():
            raise ShortsError("no transcript: the shared browser is not available (give --line-at A-B)")
        info = YB.probe(video, with_transcript=True)
        lines = info.get("transcript") or []
        if not lines:
            raise ShortsError("this video has no transcript (give --line-at A-B)")
        return [x for x in lines if not re.fullmatch(r"\[[^\]]*\]", x["text"].strip())]
    from .film import transcribe

    words = transcribe(Path(video), lang)
    out, cur = [], []
    for w in words:
        if cur and (w["s"] - cur[-1]["e"] > 0.7 or len(cur) >= 12):
            out.append({"start": cur[0]["s"], "end": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
            cur = []
        cur.append(w)
    if cur:
        out.append({"start": cur[0]["s"], "end": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
    return out


def find_line(lines: list[dict], query: str) -> tuple[float, float, str]:
    """Where a phrase is said: best window of 1-3 consecutive transcript lines (ASR text is noisy)."""
    q = _norm_words(query)
    if not q:
        raise ShortsError("empty --line")
    qs = " ".join(q)
    best = (0.0, 0, 0)
    for i in range(len(lines)):
        for j in range(i, min(len(lines), i + 3)):
            words = _norm_words(" ".join(x["text"] for x in lines[i:j + 1]))
            text = " ".join(words)
            hit = sum(1 for w in q if any(difflib.SequenceMatcher(None, w, x).ratio() > 0.8 for x in words)) / len(q)
            m = difflib.SequenceMatcher(None, qs, text).find_longest_match(0, len(qs), 0, len(text))
            sc = hit + 0.5 * m.size / len(qs) - 0.05 * (j - i)
            if sc > best[0]:
                best = (sc, i, j)
    sc, i, j = best
    if sc < 0.6:
        raise ShortsError(f"line not found in the transcript: '{query}' (see `film-lines URL --grep WORD`)")
    return float(lines[i]["start"]), float(lines[j]["end"]), " ".join(x["text"] for x in lines[i:j + 1])


# ---------------------------------------------------------------- media

def fetch(video: str, windows: list[tuple[float, float]], dst_dir: Path, prefix: str) -> list[Path]:
    """Record/download [start, end] pieces into the plan folder (the plan stays self-contained)."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    if not is_url(video):  # local film: cut the pieces (same layout as recorded ones: file time 0 = window start)
        from ..util import run

        out = []
        for k, (a, b) in enumerate(windows):
            d = dst_dir / f"{prefix}-{k + 1:02d}.mp4"
            run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.3f}", "-i", str(video), "-t", f"{b - a:.3f}",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", d])
            out.append(d)
        return out
    paths: list[Path | None] = [None] * len(windows)
    if not (YB.is_youtube(video) and _BLOCKED["yt"]):
        try:
            paths[0] = download_section(video, *windows[0])
        except BotBlock:
            _BLOCKED["yt"] = True
        except ShortsError:
            if not YB.is_youtube(video):
                raise
    rest = [i for i, p in enumerate(paths) if p is None]
    if rest and YB.is_youtube(video) and (_BLOCKED["yt"] or not paths[0]):
        if not YB.available():
            raise ShortsError("YouTube blocks this machine and the shared browser is not available")
        got = YB.record_sections(video, [windows[i] for i in rest])  # one browser session for all pieces
        for i, p in zip(rest, got):
            paths[i] = p
    else:
        for i in rest:
            paths[i] = download_section(video, *windows[i])
    out = []
    for k, p in enumerate(paths):
        d = dst_dir / f"{prefix}-{k + 1:02d}{Path(p).suffix}"
        if not d.exists() or d.stat().st_size != Path(p).stat().st_size:
            shutil.copyfile(p, d)
        out.append(d)
    return out


# ---------------------------------------------------------------- candidates (thumbnails)

def thumbnails(video: str, every: float = 5.0) -> tuple[list[tuple[float, np.ndarray]], float]:
    """(time, BGR image) samples of the whole film + duration. YouTube: storyboard (no download);
    local file: one frame every `every` seconds."""
    import cv2

    if is_url(video) and YB.is_youtube(video) and (YB.available() or YB._meta_path(video).exists()):
        info = YB.probe(video, with_transcript=False)
        sb = YB.storyboard_frames(video, info)
        d = Path(sb["dir"])
        return [(float(t), cv2.imread(str(d / f))) for t, f in zip(sb["t"], sb["files"])], float(info["duration"])
    if is_url(video):
        path = download_section(video, max_height=240)
    else:
        path = Path(video)
    from ..engine.clips import video_info

    dur = video_info(path)["duration"]
    out = []
    import subprocess

    w, h = 320, 180
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf",
                          f"fps=1/{every},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:-1:-1",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
    for k in range(len(raw) // (w * h * 3)):
        out.append((k * every, np.frombuffer(raw[k * w * h * 3:(k + 1) * w * h * 3], np.uint8).reshape(h, w, 3)))
    return out, dur


def score_thumb(img: np.ndarray) -> dict | None:
    """How good a frame is for a hero edit. None = unusable (black, text screen)."""
    import cv2

    from ..analysis.screens import TEXT_LINES_HARD, text_lines
    from ..engine import reframe as RF

    if img is None:
        return None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean, std = float(g.mean()), float(g.std())
    if mean < 22 or std < 12:
        return None
    big = cv2.resize(g, (640, int(round(640 * g.shape[0] / g.shape[1]))), interpolation=cv2.INTER_CUBIC)
    n_lines, _, _ = text_lines(big)
    if n_lines >= TEXT_LINES_HARD:
        return None
    fs = RF.faces(img)
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
    sat = float(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1].mean())
    face = max(fs, key=lambda f: f["h"]) if fs else None
    f = 0.0
    if face:
        f = min(1.0, face["h"] / 0.32) * (1.0 if len(fs) == 1 else 0.85 if len(fs) == 2 else 0.65)
        if face["x"] < 0.1 or face["x"] > 0.9:
            f *= 0.8
    sharp_n = min(1.0, np.log1p(sharp) / np.log1p(1500))
    score = 0.62 * f + 0.18 * sharp_n + 0.10 * min(1.0, std / 70) + 0.10 * min(1.0, sat / 120)
    hist = cv2.calcHist([cv2.cvtColor(img, cv2.COLOR_BGR2HSV)], [0, 1, 2], None, [8, 6, 4], [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    return {"score": round(float(score), 4), "faces": len(fs), "face": face, "sharp": round(sharp, 1),
            "mean": round(mean, 1), "text_lines": n_lines, "hist": hist}


def pick_candidates(scored: list[dict], n: int, duration: float, avoid: list[tuple[float, float]] = (),
                    gap: float = 30.0, same_look: float = 0.30, look_window: float = 240.0,
                    sections: int = 8) -> list[dict]:
    """Best frames, spread over the film: >= `gap` s apart, no two shots of the same look within
    `look_window` s (same scene from another angle), at most ceil(n/sections)+1 per part of the film."""
    import cv2

    lo, hi = duration * HEAD_SKIP, duration * (1 - TAIL_SKIP)
    gap = min(gap, max(4.0, (hi - lo) / (n * 1.3)))  # short videos: the gap shrinks with the length
    look_window = min(look_window, max(20.0, (hi - lo) / 4))
    cap = int(np.ceil(n / sections)) + 1
    per = [0] * sections
    out: list[dict] = []
    for c in sorted(scored, key=lambda c: -c["score"]):
        t = c["t"]
        if not (lo <= t <= hi) or any(a - 8 <= t <= b + 8 for a, b in avoid):
            continue
        sec = int(min(sections - 1, (t - lo) / max(1e-6, (hi - lo) / sections)))
        if per[sec] >= cap:
            continue
        bad = False
        for o in out:
            if abs(o["t"] - t) < gap:
                bad = True
                break
            if abs(o["t"] - t) < look_window and cv2.compareHist(o["hist"], c["hist"], cv2.HISTCMP_BHATTACHARYYA) < same_look:
                bad = True
                break
        if bad:
            continue
        out.append(c)
        per[sec] += 1
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- refine a recorded candidate

_SF: dict = {}
SFACE_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/"
             "face_recognition_sface_2021dec.onnx")


def _sface():
    """SFace recogniser (optional, downloaded once into SHORTS_MODELS/faces, 37 MB). None if unavailable."""
    if "m" in _SF:
        return _SF["m"]
    import cv2

    p = models_dir("faces") / "face_recognition_sface_2021dec.onnx"
    if not p.exists():
        try:
            import urllib.request

            log.info("downloading SFace (37 MB, once) to find the main character")
            tmp = p.with_suffix(".part")
            urllib.request.urlretrieve(SFACE_URL, tmp)
            tmp.rename(p)
        except Exception as e:  # noqa: BLE001
            log.info("no SFace (%s): hero shots by face size only", e)
            _SF["m"] = None
            return None
    try:
        _SF["m"] = cv2.FaceRecognizerSF.create(str(p), "")
    except Exception as e:  # noqa: BLE001
        log.info("SFace failed to load (%s)", e)
        _SF["m"] = None
    return _SF["m"]


def _embed(img_bgr: np.ndarray, face: dict) -> np.ndarray | None:
    import cv2

    rec = _sface()
    if rec is None or not face or face.get("row") is None:
        return None
    try:
        al = rec.alignCrop(img_bgr, np.array(face["row"], np.float32)[None])
        return rec.feature(al).flatten().astype(np.float32)
    except cv2.error:
        return None


def analyse_clip(path: Path) -> dict:
    """Camera shots + faces of a recorded candidate (8 fps, 480 px)."""
    import cv2

    from ..engine import editfx as EF
    from ..engine import reframe as RF
    from ..engine.clips import video_info

    info = video_info(path)
    frames, fps = EF._decode(path, 0.0, info["duration"], 480)
    if not frames:
        raise ShortsError(f"no frames in {path}")
    cuts = EF.hard_cuts(frames)
    bounds = [0] + list(cuts) + [len(frames)]
    segs = [(bounds[i] / fps, bounds[i + 1] / fps) for i in range(len(bounds) - 1)]
    step = max(1, int(round(fps / 8)))
    ts, fh, fx, fn, raws = [], [], [], [], []
    for i in range(0, len(frames), step):
        fs = RF.faces(frames[i])
        f = max(fs, key=lambda x: x["h"]) if fs else None
        ts.append(i / fps)
        fh.append(f["h"] if f else 0.0)
        fx.append(f["x"] if f else 0.5)
        fn.append(len(fs))
        raws.append(f)
    g = [cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY).astype(np.float32) for i in range(0, len(frames), step)]
    motion = [0.0] + [float(np.abs(a - b).mean()) for a, b in zip(g[1:], g[:-1])]
    from ..analysis.screens import BLACK_MEAN, BLACK_STD

    # black / flat frames (fade to black, a gap between scenes): never a shot (QA edit_content: black > 0.5 s fails)
    dark = [bool(x.mean() < BLACK_MEAN and x.std() < BLACK_STD) for x in g]
    return {"path": str(path), "duration": info["duration"], "fps": fps, "segments": segs, "t": ts, "face_h": fh,
            "face_x": fx, "faces": fn, "motion": motion, "dark": dark, "w": info["w"], "h": info["h"], "_faces": raws}


def best_offset(an: dict, span: float, tau: float, prefer: float | None = None,
                avoid: list | None = None) -> tuple[float, float]:
    """Start offset in the clip for a shot that needs `span` source seconds with its hang at `tau`:
    inside one camera shot, the hang on the biggest face. Returns (offset, quality 0..1).
    `avoid` = [(offset, span)] windows of this clip already used: a repeated shot must come from a different window
    (no free window: returns (None, -1.0))."""
    t = np.array(an["t"])
    fh = np.array(an["face_h"])
    mo = np.array(an["motion"])
    dk = np.array(an.get("dark") or [False] * len(t), bool)
    best = (None, -1.0)
    for a, b in an["segments"]:
        if b - a < span + 0.08:
            continue
        for o in np.arange(a + 0.04, b - span - 0.04 + 1e-6, 0.1):
            if avoid and any(o < uo + us + 0.15 and uo < o + span + 0.15 for uo, us in avoid):
                continue
            hang = o + tau * span
            inside = (t >= o) & (t <= o + span)
            if not inside.any():
                continue
            if dk[inside].mean() > 0.15:  # mostly black: a fade or a gap, not a shot
                continue
            f_hang = float(np.interp(hang, t, fh))
            cover = float((fh[inside] > 0.05).mean())
            m = float(np.clip(mo[inside].mean() / 12.0, 0, 1))
            q = 0.6 * min(1.0, f_hang / 0.3) + 0.25 * cover + 0.15 * m + 0.05 * min(f_hang, 0.5)
            if prefer is not None:
                q -= 0.02 * abs(hang - prefer)
            if q > best[1]:
                best = (float(o), q)
    if best[0] is None and avoid:
        return None, -1.0
    if best[0] is None:  # no camera shot long enough: the longest one, the curve gets slower (fit in render)

        def lit(seg):  # share of non-black samples in a camera shot
            m = (t >= seg[0]) & (t <= seg[1])
            return 1.0 - float(dk[m].mean()) if m.any() else 1.0

        a, b = max(an["segments"], key=lambda s: (lit(s) > 0.85, s[1] - s[0]))
        return a + 0.02, 0.2 * (b - a) / max(span, 1e-3) * (1.0 if lit((a, b)) > 0.85 else 0.1)
    return round(best[0], 3), round(best[1], 4)


# ---------------------------------------------------------------- dialogue

def _vad(path: Path, start: float = 0.0, dur: float | None = None) -> list[tuple[float, float]]:
    """Speech-ish regions by voice-band energy (fallback when faster-whisper is missing)."""
    import subprocess

    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(path)]
    if dur:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", "-af", "highpass=f=250,lowpass=f=3500", "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:  # no audio track
        return []
    x = np.frombuffer(r.stdout, np.float32)
    hop = 320
    if len(x) < hop * 4:
        return []
    e = np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop])
    e_db = 20 * np.log10(e + 1e-6)
    thr = np.median(e_db) + 0.45 * (np.percentile(e_db, 95) - np.median(e_db))
    on = e_db > thr
    regs, s = [], None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        if not v and s is not None:
            regs.append([s * 0.02, i * 0.02])
            s = None
    if s is not None:
        regs.append([s * 0.02, len(on) * 0.02])
    merged: list[list[float]] = []
    for a, b in regs:
        if merged and a - merged[-1][1] < 0.25:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a + start, b + start) for a, b in merged if b - a > 0.12]


def _split_text(text: str, a: float, b: float) -> list[dict]:
    ws = text.split()
    if not ws:
        return []
    lens = np.array([len(w) + 1 for w in ws], float)
    edges = a + (b - a) * np.concatenate([[0], np.cumsum(lens) / lens.sum()])
    return [{"w": w, "s": round(float(edges[i]), 3), "e": round(float(edges[i + 1]) - 0.02, 3)} for i, w in enumerate(ws)]


def hear(path: Path, lang: str, model: str, prompt: str = "") -> list[dict]:
    """Word timings of a short piece (faster-whisper): language forced, the transcript line as a prompt,
    no VAD, no prompt (a prompt with the noisy YouTube line made whisper hallucinate subtitle credits),
    no carry-over between segments. Cached by file content."""
    import hashlib
    import subprocess

    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except ImportError as e:
        raise ShortsError("faster-whisper is not installed") from e
    from .film import _whisper_model

    h = hashlib.sha1(Path(path).read_bytes()[:4_000_000] + f"novad3|{model}|{lang}".encode()).hexdigest()[:16]
    key = cache_dir("transcripts") / f"line-{h}.json"
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, np.float32)
    segs, _ = _whisper_model(model).transcribe(audio, language=lang, task="transcribe", word_timestamps=True,
                                               vad_filter=False, condition_on_previous_text=False,
                                               beam_size=5)
    # no VAD: Silero cuts quiet film dialogue under music (tested on a film line: with VAD only the
    # louder second speaker was heard). Punctuation-only tokens (dashes) are dropped, trailing , . ; : too.
    words = []
    for sg in segs:
        for w in sg.words or []:
            t = re.sub(r"[,.;:\u2026]+$", "", w.word.strip())
            if re.search(r"\w", t):
                words.append({"w": t, "s": round(float(w.start), 3), "e": round(float(w.end), 3)})
    key.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


def dialogue(video: str, media: Path, line: str | None = None, line_at: tuple[float, float] | None = None,
             text: str | None = None, lang: str = "ru", whisper: str = "small", max_len: float = 6.0) -> dict:
    """The opening line: file + in/out (film time = in the file) + words (relative to `in`)."""
    if line_at:
        a, b = line_at
        win = (max(0.0, a - 1.0), b + 1.0)
        ref_text = text
    elif line:
        a, b, ref_text = find_line(film_lines(video, lang), line)
        win = (max(0.0, a - 1.5), min(b + 1.5, a + 22.0))
    else:
        raise ShortsError("give --line TEXT or --line-at A-B for the opening dialogue")
    path = fetch(video, [win], media, "dialogue")[0]
    base = win[0]  # file time 0 = film time `base`
    words: list[dict] = []
    engine = "whisper"
    try:
        words = [{"w": w["w"], "s": w["s"] + base, "e": w["e"] + base}
                 for w in hear(path, lang, whisper, prompt=ref_text or line or "")]
    except ShortsError as e:
        log.info("%s: word timings from voice energy", e)
        engine = "energy"
    score = 0.0
    if words:
        lo_t, hi_t = (line_at if line_at else (win[0], win[1]))
        if line:
            q = _norm_words(line)
            norm = [(_norm_words(w["w"]) or [""])[0] for w in words]
            best = (0.0, 0, 0)
            for i in range(len(words)):
                for j in range(i, min(len(words), i + len(q) + 6)):
                    cand = " ".join(norm[i:j + 1])
                    sc = difflib.SequenceMatcher(None, " ".join(q), cand).ratio()
                    if sc > best[0] + 1e-9:
                        best = (sc, i, j)
            score, i, j = best
            if score >= 0.6:
                words = words[i:j + 1]
            else:  # whisper misheard (noisy film sound): the speech region around the transcript line
                log.info("whisper heard %r (match %.2f): the speech region is used",
                         " ".join(w["w"] for w in words), score)
                engine = "energy"
                words = []
        else:
            words = [w for w in words if w["e"] > lo_t - 0.1 and w["s"] < hi_t + 0.1] or words
    if words:
        s, e = words[0]["s"], words[-1]["e"]
    else:
        regs = [(x + base, y + base) for x, y in _vad(path)]
        lo, hi = (line_at if line_at else (win[0] + 1.0, win[1] - 1.0))
        regs = [r for r in regs if r[1] > lo and r[0] < hi] or [(lo, hi)]
        s, e = regs[0][0], regs[-1][1]
        if not line_at and e - s > max_len:  # several phrases: the first sentence-sized piece
            e = s + max_len
        words = _split_text(text or line or ref_text or "", s, e)
        engine = "energy"
    if text:
        words = _split_text(text, s, e) if engine == "energy" or len(text.split()) != len(words) else \
            [{**w, "w": t} for w, t in zip(words, text.split())]
    if e - s > max_len:
        log.warning("the line is %.1fs long (> %.1fs): a short line works better", e - s, max_len)
    clip_in, clip_out = max(base, s - 0.2), e + 0.3
    rel = [{"w": w["w"], "s": round(w["s"] - clip_in, 3), "e": round(w["e"] - clip_in, 3)} for w in words]
    return {"file": path, "film_in": round(clip_in, 3), "film_out": round(clip_out, 3), "in": round(clip_in - base, 3),
            "out": round(clip_out - base, 3), "words": rel, "text": " ".join(w["w"] for w in words), "timing": engine}


# ---------------------------------------------------------------- music

def detect_drop(b: dict, earliest: float = 2.0) -> float:
    """Biggest energy jump on a downbeat (2 s after vs 2 s before); the loudest window if no clear jump."""
    t, r = np.array(b["energy"]["t"], float), np.array(b["energy"]["rms"], float)
    best, best_d = 1.0, None
    for d in b.get("downbeats") or []:
        if d < earliest or d > t[-1] - 6:
            continue
        after = r[(t >= d) & (t < d + 2)].mean() if ((t >= d) & (t < d + 2)).any() else 0
        before = r[(t >= d - 2) & (t < d)].mean() if ((t >= d - 2) & (t < d)).any() else 1e9
        ratio = after / max(1e-6, before)
        if ratio > best:
            best, best_d = ratio, d
    if best_d is not None and best > 1.3:
        return float(best_d)
    from .film import best_music_window

    return best_music_window(b, 12.0)


def music_info(src: str) -> dict:
    """{path, bpm, beat, beats, downbeats, drop, duration}. Own tracks have a sidecar JSON (exact grid)."""
    from .film import music_beats, music_file

    p = music_file(src) if src != DEFAULT_MUSIC else asset("audio/edit.mp3")
    side = p.with_suffix(".json")
    if side.exists():
        d = json.loads(side.read_text(encoding="utf-8"))
        return {**d, "path": str(p), "source": "sidecar"}
    b = music_beats(str(p))
    beat = 60.0 / max(40.0, float(b["tempo"]))
    return {"path": str(p), "bpm": b["tempo"], "beat": beat, "beats": b["beats"], "downbeats": b["downbeats"],
            "drop": detect_drop(b), "duration": b["duration"], "source": "librosa"}


def slot_pattern(n_beats: int, beat: float) -> list[tuple[int, str]]:
    """Shot lengths in beats after the drop. Regular shots ~0.7-1.4 s on strong beats, two hero shots
    (double length) at ~25% and ~62%, a quick double cut before the second hero (rhythm change)."""
    u = 2
    for cand in (1, 2, 4, 8):
        if 0.7 <= cand * beat <= 1.4:
            u = cand
            break
    out: list[tuple[int, str]] = []
    pos = 0
    hero_at = [round(n_beats * 0.25 / u) * u, round(n_beats * 0.62 / u) * u]
    while pos < n_beats:
        left = n_beats - pos
        if hero_at and pos >= hero_at[0] and left >= 2 * u + u:
            out.append((2 * u, "hero"))
            pos += 2 * u
            hero_at.pop(0)
            continue
        if len(hero_at) == 1 and hero_at[0] - pos == u and u >= 2 and left > 2 * u:
            out += [(u // 2, "quick"), (u // 2, "quick")]
            pos += u
            continue
        step = min(u, left)
        out.append((step, "shot"))
        pos += step
    return out


# ---------------------------------------------------------------- the plan

def edit_plan(video: str, out_dir: Path, line: str | None = None, line_at: tuple[float, float] | None = None,
              line_text: str | None = None, music: str | None = None, length: float = 18.0,
              link: str | None = None, handle: str | None = None, name: str = "film-edit", lang: str = "ru",
              platforms: list[str] | None = None, brand: str = "mono", look: str = "film", fps: int = 30,
              title: str = "", spares: int = 4, whisper: str = "small") -> dict:
    """Build an edit plan (dialogue -> drop -> hero shots) and record the media into out_dir/media."""
    from ..engine import velocity as V

    out_dir.mkdir(parents=True, exist_ok=True)
    media = out_dir / "media"
    meta = video_meta(video) if is_url(video) else {"title": Path(video).stem}
    title = title or meta.get("title") or ""
    # 1) the line
    dlg = dialogue(video, media, line, line_at, line_text, lang, whisper)
    D = dlg["out"] - dlg["in"]
    log.info("line %.2f-%.2fs (%.2fs): %s [%s]", dlg["film_in"], dlg["film_out"], D, dlg["text"], dlg["timing"])
    # 2) music: drop exactly at the end of the line (2.2: a real track is required, see need_music)
    music, synthetic_music = need_music(music, "edit")
    mu = music_info(music)
    beat = float(mu["beat"])
    drop_tl = round(round(D * fps) / fps, 4)  # drop on the timeline = first frame after the line
    m_start = float(mu["drop"]) - drop_tl
    m_offset = 0.0
    if m_start < 0:
        m_offset, m_start = -m_start, 0.0
    bar = 4 * beat
    post_bars = max(4, int(round((length - drop_tl) / bar)))
    if mu.get("duration"):
        post_bars = min(post_bars, int((float(mu["duration"]) - float(mu["drop"]) - 0.5) / bar))
    pattern = slot_pattern(post_bars * 4, beat)
    # 3) candidates: thumbnails of the whole film
    thumbs, duration = thumbnails(video)
    scored = []
    for t, img in thumbs:
        s = score_thumb(img)
        if s:
            scored.append({"t": t, **s})
    n_need = len(pattern)
    hero_thumbs(thumbs, scored)
    cands = pick_candidates(scored, n_need + spares, duration, avoid=[(dlg["film_in"], dlg["film_out"])])
    if len(cands) < n_need:
        log.warning("only %d good frames for %d shots: some shots repeat", len(cands), n_need)
    if not cands:
        raise ShortsError("no usable frames (all black or text?)")
    log.info("candidates: %s", ", ".join(f"{c['t']:.0f}s({c['score']:.2f})" for c in cands))
    # 4) record the candidates and refine them at full size
    pre, post = 2.2, 2.8
    wins = [(max(0.0, c["t"] - pre), c["t"] + post) for c in cands]
    files = fetch(video, wins, media, "shot")
    an = []
    for c, w, f in zip(cands, wins, files):
        a = analyse_clip(f)
        a["film_t0"] = w[0]
        a["thumb"] = c
        an.append(a)
    # main character: the face seen most often (SFace), optional
    _hero_ids(an)
    # 5) assign shots to slots
    spans = {}
    for k, (nb, role) in enumerate(pattern):
        dur = nb * beat
        preset = "hero" if role == "hero" else "velocity"
        spans[k] = (dur, preset, V.source_span(preset, dur), V.hang_tau(preset))
    pool = list(range(len(an)))

    def quality(i, k):
        dur, preset, span, tau = spans[k]
        o, q = best_offset(an[i], span, tau, prefer=an[i]["thumb"]["t"] - an[i]["film_t0"])
        return o, q * (1.25 if an[i].get("hero") else 1.0)

    order = [0] + [k for k, (nb, r) in enumerate(pattern) if r == "hero"]
    order += [k for k in range(len(pattern)) if k not in order]
    chosen: dict[int, tuple[int, float, float]] = {}
    for k in order[: 1 + sum(1 for _, r in pattern if r == "hero")]:  # first + heroes: the best ones
        if not pool:
            break
        i, (o, q) = max(((i, quality(i, k)) for i in pool), key=lambda x: x[1][1])
        chosen[k] = (i, o, q)
        pool.remove(i)
    rest_slots = [k for k in range(len(pattern)) if k not in chosen]
    ranked = sorted(pool, key=lambda i: -quality(i, rest_slots[0] if rest_slots else 0)[1])[: len(rest_slots)]
    ranked.sort(key=lambda i: an[i]["film_t0"])  # the rest in film order (a story, not a shuffle)
    for k, i in zip(rest_slots, ranked):
        o, q = quality(i, k)
        chosen[k] = (i, o, q)
    used: dict[int, list] = {}
    for k, (i, o, _q) in chosen.items():
        used.setdefault(i, []).append((o, spans[k][2]))
    for k in rest_slots:  # not enough candidates: reuse clips, but never the same moment twice
        if k in chosen:
            continue
        best = None
        for i in range(len(an)):
            o, q = best_offset(an[i], spans[k][2], spans[k][3], prefer=an[i]["thumb"]["t"] - an[i]["film_t0"], avoid=used.get(i))
            if o is not None and (best is None or q > best[2]):
                best = (i, o, q)
        if best is None:
            log.warning("slot %d: no unused moment left, a shot repeats", k)
            i = max(range(len(an)), key=lambda i: quality(i, k)[1])
            o, q = quality(i, k)
            best = (i, max(0.0, o - 0.6), q)
        chosen[k] = best
        used.setdefault(best[0], []).append((best[1], spans[k][2]))
    # 6) scenes
    look_d = {"grade": look}
    scenes = [{
        "id": "line", "type": "film", "duration": round(D, 4),
        "why": f"opening line from the film ({dlg['film_in']:.1f}s): the hook, original sound",
        "source": {"type": "film", "ref": _ref(dlg["file"], out_dir), "in": dlg["in"],
                   "out": dlg["out"], "keep_audio": True, "film_time": dlg["film_in"]},
        "transcript": dlg["words"],
        "edit": {"velocity": "flat", "hits": [], "look": look_d},
    }]
    t = drop_tl
    shot_starts = []
    cum = 0
    fr = lambda x: round(round(x * fps) / fps, 4)  # noqa: E731  cut on the frame nearest to the beat
    for k, (nb, role) in enumerate(pattern):
        _, preset, span, tau = spans[k]
        dur = round(fr(drop_tl + (cum + nb) * beat) - fr(drop_tl + cum * beat), 4)  # no drift over many shots
        cum += nb
        i, o, q = chosen[k]
        a = an[i]
        sc = {"id": f"shot-{k + 1:02d}", "type": "film", "duration": round(dur, 4),
              "why": f"{role}{' (main character)' if a.get('hero') else ''}: film {a['film_t0'] + o:.1f}s, q {q:.2f}",
              "source": {"type": "film", "ref": _ref(a["path"], out_dir), "in": round(o, 3),
                         "out": round(o + span, 3), "film_time": round(a["film_t0"] + o, 2)},
              "edit": {"velocity": preset, "look": look_d, "hits": [0.0]}}
        if k == 0:
            sc["why"] += " - on the drop"
        scenes.append(sc)
        shot_starts.append(t)
        t += dur
    total = t
    # 7) link / handle: centre, slides in; twice (research 5.2: nick on screen twice)
    ctas = []
    txt = link or handle
    if txt:
        mid = min((s for s in shot_starts if s >= drop_tl + (total - drop_tl) * 0.42), default=drop_tl + 2)
        for tt, dd in ((mid, 2.4), (max(mid + 3.0, total - 2.6), 2.6)):
            if tt + 0.5 < total:
                c = {"t": round(tt, 3), "duration": round(min(dd, total - tt), 3), "kind": "link", "text": txt,
                     "y": "center", "anim": "slide"}
                if link:
                    c["url"] = link if re.match(r"https?://", link) else "https://" + link  # description, pinned
                    if "t.me" in link:
                        c["icon"] = "telegram"
                ctas.append(c)
    # strong beats in video time (QA beat_sync): own track = every beat after the drop has a kick or a clap;
    # other tracks: downbeats and beat 3 (film.strong_beats)
    if mu.get("source") == "sidecar":
        strong = [round(b - m_start + m_offset, 3) for b in mu["beats"] if b >= float(mu["drop"]) - 1e-6
                  and b - m_start + m_offset <= total + 0.05]
    else:
        from .film import strong_beats as _sb

        strong = [round(x + m_offset, 3) for x in _sb({"beats": mu["beats"], "downbeats": mu["downbeats"]}, m_start, total)]
    downs = [round(drop_tl + j * bar, 3) for j in range(post_bars) if drop_tl + j * bar < total - 0.2]
    tag = re.sub(r"\W", "", (title.split("(")[0] if title else "").lower())
    plan = {
        "schema_version": "1.2",
        "meta": {"name": name, "language": lang, "platforms": platforms or ["youtube_shorts"],
                 "duration_target": [7, 20], "emotion": "energy", "audience": "film fans", "loop": True, "fps": fps},
        "layout": {"mode": "center_only", "cta_in_center": ctas},
        "brand": {"preset": brand},
        "captions": {"enabled": True, "max_words": 3, "highlight": "none", "anim": "grow"},
        "audio": {"voice": {"engine": "none"},
                  "music": {"source": str(Path(mu["path"])), "start": round(m_start, 3), "offset": round(m_offset, 3),
                            "drop_at": drop_tl, "pre_drop_db": -16, "beat_sync": True},
                  "target_lufs": -14, "sfx_auto": False, "sfx": "off"},
        "edit": {"reframe": "face", "look": look_d},
        "fx": {"flash": [drop_tl], "punch": downs[1:]},
        "scenes": scenes,
        "metadata": {"topic": title, "source_video": video, "structure": "line -> drop -> hero shots",
                     "line": {"text": dlg["text"], "film_in": dlg["film_in"], "film_out": dlg["film_out"],
                              "timing": dlg["timing"]},
                     "music": {"bpm": mu["bpm"], "drop": mu["drop"], "start": round(m_start, 3), "source": mu["source"],
                               "strong_beats": strong, "synthetic": synthetic_music},
                     "candidates": [{"t": c["t"], "score": c["score"], "faces": c["faces"]} for c in cands],
                     "hashtags": ["edit", "shorts"] + ([tag] if tag else []) + ["movie"]},
    }
    return plan


def _cluster(embs: list[np.ndarray], thr: float = 0.363) -> tuple[np.ndarray, int] | None:
    """Biggest identity: (cosine similarity of every embedding to the cluster centre, votes)."""
    if len(embs) < 3:
        return None
    E = np.stack(embs)
    E = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
    sim = E @ E.T
    votes = (sim > thr).sum(1)
    c = int(np.argmax(votes))
    return sim[c], int(votes[c])


def hero_thumbs(thumbs: list[tuple[float, np.ndarray]], scored: list[dict], boost: float = 1.3) -> None:
    """Main character on the thumbnails (most frequent face, SFace on 2x upscaled storyboard frames):
    his frames get `boost` - an edit is about the hero (tutorial: hero shots)."""
    import cv2

    from ..engine import reframe as RF

    if _sface() is None:
        return
    by_t = {t: img for t, img in thumbs}
    idx, embs = [], []
    for k, c in enumerate(scored):
        f = c.get("face")
        if not f or f["h"] < 0.14:
            continue
        img = by_t.get(c["t"])
        big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        fs = RF.faces(big)
        if not fs:
            continue
        e = _embed(big, max(fs, key=lambda x: x["h"]))
        if e is not None:
            idx.append(k)
            embs.append(e)
    res = _cluster(embs)
    if not res:
        return
    sim, votes = res
    if votes < max(3, len(embs) // 12):
        return
    n = 0
    for k, sv in zip(idx, sim):
        if sv > 0.363:
            scored[k]["hero"] = True
            scored[k]["score"] = round(scored[k]["score"] * boost, 4)
            n += 1
    log.info("main character on %d of %d face thumbnails", n, len(embs))


def _ref(path, out_dir: Path) -> str:
    """Plan refs are relative to the plan folder when possible (the plan folder can be moved)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(Path(out_dir).resolve()))
    except ValueError:
        return str(p)


def _hero_ids(an: list[dict]) -> None:
    """Mark candidates whose biggest face is the most frequent identity (SFace cosine > 0.363)."""
    import cv2

    from ..engine import editfx as EF

    if _sface() is None:
        return
    embs = []
    for a in an:
        fh = np.array(a["face_h"])
        if not len(fh) or fh.max() < 0.08:
            embs.append(None)
            continue
        j = int(np.argmax(fh))
        fr, _ = EF._decode(Path(a["path"]), a["t"][j], 0.05)
        f = a["_faces"][j]
        if not fr or not f:
            embs.append(None)
            continue
        from ..engine import reframe as RF

        fs = RF.faces(fr[0])
        big = max(fs, key=lambda x: x["h"]) if fs else None
        embs.append(_embed(fr[0], big) if big else None)
    idx = [i for i, e in enumerate(embs) if e is not None]
    if len(idx) < 3:
        return
    rec = _sface()
    sim = np.zeros((len(idx), len(idx)))
    for x, i in enumerate(idx):
        for y, j in enumerate(idx):
            sim[x, y] = rec.match(embs[i][None], embs[j][None], cv2.FaceRecognizerSF_FR_COSINE)
    votes = (sim > 0.363).sum(1)
    c = int(np.argmax(votes))
    if votes[c] < 3:
        return
    for x, i in enumerate(idx):
        if sim[c, x] > 0.363:
            an[i]["hero"] = True
    log.info("main character in %d of %d candidates", int(votes[c]), len(an))
