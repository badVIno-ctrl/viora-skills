"""Speech boundaries (v2.2): a cut never lands inside a word, a join prefers the end of a sentence, the video ends
after the last word with a real tail of silence.

Why: in 2.1 `stack` joined the pieces exactly at the given seconds. A 77 s interview short ended 0.07 s after
"...тогда в личке" (the speaker went on) and had a join "...и я там | Он сказал" in the middle of a sentence.

Word timings, best first (all in SOURCE seconds):
  1. faster-whisper on the used ranges only (if installed; cached in SHORTS_CACHE/words): start and end of every word
  2. `<srt>.words.json`, written by `shorts.py srt` (YouTube auto-caption word starts; ends estimated)
  3. SRT cues (cue start/end, words spread by length): weakest, the energy envelope does the rest
The voice-band energy envelope then refines every boundary: a cut goes into the quiet gap after a word.

snap_pieces(pieces, words_of, env_of)  -> new pieces + report (what moved and why)
check_pieces(pieces, words_of)         -> problems that remain (cut inside a word, open end, short tail)
audio_qa(wav, joins, duration)         -> measured on the rendered sound: voice at a join / in the last 120 ms
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

from .config import cache_dir
from .util import log

PRE_ROLL = 0.10       # before the first word of a piece
TAIL_JOIN = 0.22      # after the last word at an internal join (never into the next word)
TAIL_END = 0.70       # after the last word of the whole video (shorter if the next word starts sooner)
MIN_TAIL_END = 0.35   # QA: shorter = "the video was cut on the word"
SENT_PAUSE = 0.55     # a pause this long ends a sentence when the text has no punctuation (YouTube auto-captions)
PHRASE_PAUSE = 0.25   # a pause this long is a safe place for a cut
MAX_EXTEND = 4.0      # the end may move this far forward to finish the sentence
MAX_BACK = 3.0        # ... or this far back to the previous sentence end
MAX_START_BACK = 2.5  # the start may move this far back to the start of the sentence
STRONG = re.compile(r"[.!?\u2026]+[\"')»]*$")
MEDIUM = re.compile(r"[,;:\-]+[\"')»]*$")
CONT = re.compile(r"^(и|а|но|что|чтобы|потому|который|которая|которые|где|когда|если|как|то|ну|вот|or|and|but|that|which|because)$", re.I)


# ------------------------------------------------------------------ energy

class Envelope:
    """Voice-band (120-3800 Hz) RMS in dB, 10 ms hop, for one source range."""

    def __init__(self, t: np.ndarray, db: np.ndarray):
        self.t, self.db = t, db
        if len(db):
            lo, hi = float(np.percentile(db, 12)), float(np.percentile(db, 92))
            self.thr = max(lo + 7.0, hi - 24.0)
        else:
            self.thr = -40.0

    def voiced(self, t: float) -> bool:
        if not len(self.t):
            return False
        i = int(np.clip(np.searchsorted(self.t, t), 0, len(self.t) - 1))
        return bool(self.db[i] > self.thr)

    def quiet_after(self, t: float, limit: float, min_len: float = 0.06) -> float | None:
        """First moment >= t where the voice is below the threshold for min_len seconds (None within limit)."""
        if not len(self.t):
            return None
        i0 = int(np.searchsorted(self.t, t))
        need = max(1, int(round(min_len / 0.01)))
        run = 0
        for i in range(i0, len(self.t)):
            if self.t[i] > t + limit:
                break
            run = run + 1 if self.db[i] <= self.thr else 0
            if run >= need:
                return float(self.t[i - need + 1])
        return None

    def quiet_before(self, t: float, limit: float, min_len: float = 0.06) -> float | None:
        """Last quiet run that ends <= t (returns its END, the place to start a piece)."""
        if not len(self.t):
            return None
        i0 = int(np.clip(np.searchsorted(self.t, t), 0, len(self.t) - 1))
        need = max(1, int(round(min_len / 0.01)))
        run = 0
        for i in range(i0, -1, -1):
            if self.t[i] < t - limit:
                break
            run = run + 1 if self.db[i] <= self.thr else 0
            if run >= need:
                return float(self.t[i + need - 1])
        return None


def envelope(src: Path | str, a: float, b: float, hop: float = 0.01, win: float = 0.03) -> Envelope:
    a = max(0.0, float(a))
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{max(0.05, b - a):.3f}", "-i", str(src), "-vn",
           "-ac", "1", "-ar", "16000", "-af", "highpass=f=120,lowpass=f=3800", "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    x = np.frombuffer(r.stdout, np.float32) if r.returncode == 0 else np.zeros(0, np.float32)
    return envelope_of(x, 16000, a, hop, win)


def envelope_of(x: np.ndarray, sr: int, t0: float = 0.0, hop: float = 0.01, win: float = 0.03) -> Envelope:
    nh, nw = max(1, int(sr * hop)), max(1, int(sr * win))
    if len(x) < nw:
        return Envelope(np.zeros(0), np.zeros(0))
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    starts = np.arange(0, len(x) - nw + 1, nh)
    rms = np.sqrt((c[starts + nw] - c[starts]) / nw)
    return Envelope(t0 + (starts + nw / 2) / sr, 20 * np.log10(rms + 1e-7))


# ------------------------------------------------------------------ words

def _clean(words: list[dict]) -> list[dict]:
    out = []
    for w in words:
        t = str(w.get("w", "")).strip()
        if not re.search(r"\w", t):
            continue
        s = float(w["s"])
        e = float(w.get("e", s + 0.3))
        out.append({"w": t, "s": s, "e": max(e, s + 0.04), **({"approx": True} if w.get("approx") or w.get("approx_end") else {})})
    out.sort(key=lambda w: w["s"])
    return out


def words_from_srt(cues: list[tuple[float, float, str]]) -> list[dict]:
    """Cue -> words spread by length (approximate; flagged)."""
    out = []
    for a, b, text in cues:
        ws = text.split()
        if not ws:
            continue
        lens = np.array([len(w) + 1 for w in ws], float)
        edges = a + (b - a) * np.concatenate([[0], np.cumsum(lens) / lens.sum()])
        out += [{"w": w, "s": float(edges[i]), "e": float(edges[i + 1]) - 0.02, "approx": True} for i, w in enumerate(ws)]
    return out


def whisper_words(src: Path | str, a: float, b: float, lang: str = "ru", model: str | None = None) -> list[dict] | None:
    """faster-whisper word timings for [a, b] of src (source seconds), punctuation kept. None if not installed."""
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return None
    import os

    model = model or os.environ.get("SHORTS_WHISPER", "small")
    if model.lower() in ("off", "none", "0", "no"):
        return None
    p = Path(src)
    st = p.stat()
    key = hashlib.sha1(f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}|{a:.2f}|{b:.2f}|{model}|{lang}|v1".encode()).hexdigest()[:16]
    f = cache_dir("words") / f"{p.stem[:40]}-{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    a = max(0.0, a)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(p), "-vn",
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    audio = np.frombuffer(raw, np.float32)
    if len(audio) < 1600:
        return []
    from .adapters.film import _whisper_model

    try:
        segs, _ = _whisper_model(model).transcribe(audio, language=lang, word_timestamps=True, vad_filter=False,
                                                   condition_on_previous_text=False, beam_size=3)
        words = [{"w": w.word.strip(), "s": round(a + float(w.start), 3), "e": round(a + float(w.end), 3),
                  "p": round(float(w.probability), 2)} for s in segs for w in (s.words or []) if w.word.strip()]
    except Exception as e:  # model download blocked, broken install: boundaries fall back to energy
        log.warning("whisper failed (%s): speech boundaries use the energy envelope only", e)
        return None
    f.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


def sidecar_words(srt: Path | None) -> list[dict] | None:
    if not srt:
        return None
    p = Path(srt)
    for cand in (p.with_suffix(".words.json"), Path(str(p) + ".words.json")):
        if cand.exists():
            return json.loads(cand.read_text(encoding="utf-8"))
    return None


def _tok(w: str) -> str:
    return re.sub(r"[^\w]+", "", str(w).lower().replace("ё", "е"))


def align_text(text_words: list[dict], timed: list[dict] | None) -> list[dict]:
    """Keep the TEXT of text_words (an edited SRT), take the TIMES of timed (whisper / YouTube word starts).
    Matched words get the timed word's start/end; a replaced run of the same length maps 1:1 ("100" vs "сто");
    the rest is spread over the time between its matched neighbours. Precision flag follows the timed words."""
    import difflib

    out = [dict(w) for w in text_words]
    if not timed or not out:
        return out
    timed = sorted(timed, key=lambda w: float(w["s"]))
    a = [_tok(w["w"]) for w in out]
    b = [_tok(w["w"]) for w in timed]
    done = [False] * len(out)

    def take(i, j):
        out[i]["s"], out[i]["e"] = float(timed[j]["s"]), float(timed[j].get("e", float(timed[j]["s"]) + 0.3))
        if timed[j].get("approx") or timed[j].get("approx_end"):
            out[i]["approx"] = True
        else:
            out[i].pop("approx", None)
        done[i] = True

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                take(i1 + k, j1 + k)
        elif tag == "replace":                       # different lengths: spread the text over the timed span
            s0, e0 = float(timed[j1]["s"]), float(timed[j2 - 1].get("e", timed[j2 - 1]["s"]))
            lens = np.array([len(out[i]["w"]) + 1 for i in range(i1, i2)], float)
            edges = s0 + (e0 - s0) * np.concatenate([[0], np.cumsum(lens) / lens.sum()])
            for k, i in enumerate(range(i1, i2)):
                out[i]["s"], out[i]["e"], out[i]["approx"] = float(edges[k]), float(edges[k + 1]) - 0.02, True
                done[i] = True
    i = 0
    while i < len(out):                              # inserted words (only in the text): between the neighbours
        if done[i]:
            i += 1
            continue
        j = i
        while j < len(out) and not done[j]:
            j += 1
        lo = out[i - 1]["e"] if i > 0 else out[i]["s"]
        hi = out[j]["s"] if j < len(out) else max(lo + 0.3 * (j - i), out[j - 1]["e"])
        hi = max(hi, lo + 0.08 * (j - i))
        step = (hi - lo) / (j - i)
        for k in range(i, j):
            out[k]["s"], out[k]["e"], out[k]["approx"] = lo + step * (k - i), lo + step * (k - i + 1) - 0.01, True
        i = j
    return out


# ------------------------------------------------------------------ boundaries

CUT_OFF = re.compile(r"(\.\.\.|\u2026)[\"')»]*$")
_FW = set("в во на с со к ко по о об у из за от до для при про без над под через и а но или да что чтобы как "
          "a an the to of in on at by for with from into and or but if as than that".split())


def cut_off(word: str) -> bool:
    """'в...' / 'and…': the ASR heard the speech break off on a function word - never a place to end."""
    return bool(CUT_OFF.search(word)) and re.sub(r"[^\w\-]", "", word.lower()) in _FW


def sentence_end(words: list[dict], i: int) -> bool:
    w = words[i]
    if cut_off(w["w"]):
        return False
    if i >= len(words) - 1:          # the last known word: trust a full stop; with no punctuation at all, a guess
        return bool(STRONG.search(w["w"])) or not any(STRONG.search(x["w"]) or MEDIUM.search(x["w"]) for x in words)
    nxt = words[i + 1]
    gap = nxt["s"] - w["e"]
    if STRONG.search(w["w"]):            # ASR full stop: trust it unless the next word runs straight on in lowercase
        return gap >= 0.03 or nxt["w"][:1].isupper()
    has_punct = any(STRONG.search(x["w"]) or MEDIUM.search(x["w"]) for x in words)
    if CONT.match(re.sub(r"\W", "", nxt["w"])) and gap < 0.9:
        return False
    return gap >= (SENT_PAUSE if not has_punct else 0.9)


def phrase_end(words: list[dict], i: int) -> bool:
    if cut_off(words[i]["w"]):
        return False
    if i >= len(words) - 1:
        return True
    return sentence_end(words, i) or bool(MEDIUM.search(words[i]["w"])) or words[i + 1]["s"] - words[i]["e"] >= PHRASE_PAUSE


def _inside(words: list[dict], t: float, pad: float = 0.02):
    for i, w in enumerate(words):
        if w["s"] + pad < t < w["e"] - pad:
            return i
    return None


def _touching(words: list[dict], t: float):
    """The word a START at t would hit: t inside it, or the word began up to 30 ms before t."""
    for i, w in enumerate(words):
        if w["s"] - 0.03 <= t < w["e"] - 0.02:
            return i
    return None


def _last_before(words, t):
    """Last word that really started before an END at t (a word starting in the last 50 ms is not 'said')."""
    j = None
    for i, w in enumerate(words):
        if w["s"] < t - 0.05:
            j = i
    return j


def _first_after(words, t):
    for i, w in enumerate(words):
        if w["s"] >= t:
            return i
    return None


def snap_start(s: float, words: list[dict], env: Envelope | None, mode: str = "sentence") -> tuple[float, str]:
    if words:
        k = _touching(words, s)
        first = _first_after(words, s) if k is None else k
        if first is None:
            return s, "no speech after the start"
        prev = first - 1
        starts_sentence = prev < 0 or sentence_end(words, prev) or (words[first]["s"] - words[prev]["e"]) > 1.2
        why = ""
        if mode == "sentence" and not starts_sentence:
            cand = [i for i in range(len(words)) if (i == 0 or sentence_end(words, i - 1))
                    and s - MAX_START_BACK <= words[i]["s"] <= s + 1.0]
            if cand:
                first = min(cand, key=lambda i: (abs(words[i]["s"] - s) + (0.0 if words[i]["s"] <= s else 0.4)))
                why = f"start moved to the sentence start '{words[first]['w']}'"
        if not why and k is not None and s > words[k]["s"] + 0.005:
            why = f"start was inside '{words[k]['w']}'"
        lo = (words[first - 1]["e"] + min(0.03, max(0.0, words[first]["s"] - words[first - 1]["e"]) / 2)) if first > 0 else 0.0
        ns = max(lo, words[first]["s"] - PRE_ROLL)
        if env is not None and env.voiced(ns):
            q = env.quiet_before(words[first]["s"], 0.25, 0.03)
            if q is not None and q >= lo:
                ns = min(ns, q)
        return round(ns, 3), why
    if env is not None and env.voiced(s):
        q = env.quiet_before(s, 1.2, 0.12)
        if q is not None:
            return round(max(0.0, q - 0.04), 3), "start moved into the pause before the voice"
    return s, ""


def snap_end(e: float, words: list[dict], env: Envelope | None, last: bool, mode: str = "sentence",
             min_end: float = 0.0) -> tuple[float, str, float | None]:
    """-> (new end, why, mute_from). mute_from: the sound fades out there (the next word would start inside the tail);
    the picture runs on to the new end."""
    tail = TAIL_END if last else TAIL_JOIN
    if words:
        k = _inside(words, e)
        j = k if k is not None else _last_before(words, e)
        if j is None:
            return e, "", None
        why = f"end was inside '{words[k]['w']}'" if k is not None else ""
        if mode == "sentence" and not sentence_end(words, j):
            fwd = [i for i in range(j, len(words)) if sentence_end(words, i) and words[i]["e"] <= e + MAX_EXTEND]
            back = [i for i in range(0, j) if sentence_end(words, i) and words[i]["e"] >= e - MAX_BACK and words[i]["e"] > min_end + 0.5]
            c_f = (words[fwd[0]]["e"] - e) if fwd else 1e9            # finishing the thought is slightly preferred
            c_b = (e - words[back[-1]]["e"]) * 1.3 if back else 1e9
            if fwd and c_f <= c_b:
                j = fwd[0]
                why = f"end moved forward to finish the sentence ('{words[j]['w']}')"
            elif back:
                j = back[-1]
                why = f"end moved back to the previous sentence end ('{words[j]['w']}')"
            else:                     # no sentence end in reach (edited speech without pauses): the nearest phrase end
                ph = [i for i in range(len(words) - 1) if phrase_end(words, i) and e - 1.5 <= words[i]["e"] <= e + 1.5
                      and words[i]["e"] > min_end + 0.5]
                if ph:
                    j = min(ph, key=lambda i: abs(words[i]["e"] - e) * (1.0 if words[i]["e"] >= e else 1.3))
                    why = (why + "; " if why else "") + f"no sentence end near, cut at the pause after '{words[j]['w']}'"
        we = words[j]["e"]
        if env is not None:
            q = env.quiet_after(we - 0.05, 0.35, 0.05)
            if q is not None:
                we = max(we, q)
        nxt = words[j + 1]["s"] if j + 1 < len(words) else None
        mute = None
        if nxt is None:
            ne = we + tail
        elif last:
            ne = we + tail
            if nxt < ne:      # the next word starts inside the tail: stop the picture before it (no silent talking)
                if nxt - 0.04 - we >= MIN_TAIL_END + 0.05:
                    ne = nxt - 0.04
                else:         # it starts too soon: a short tail, the sound fades before the next word
                    ne = we + MIN_TAIL_END + 0.05
                    mute = round(max(we + 0.04, (we + nxt) / 2 if nxt - we < 0.3 else nxt - 0.08), 3)
        else:
            ne = min(we + tail, max(we + 0.04, nxt - 0.05))
        return round(ne, 3), why, mute
    if env is not None:
        if env.voiced(e):
            q = env.quiet_after(e, 1.5, 0.12)
            if q is not None:
                return round(q + (tail if last else 0.08), 3), "end moved into the pause after the voice", None
        elif last:
            return round(e + 0.25, 3), "tail added", None
    return e, "", None


def snap_pieces(pieces: list[dict], words_of, env_of, mode: str = "sentence", durations: dict | None = None
                ) -> tuple[list[dict], list[dict]]:
    """words_of(src, a, b) -> words in source seconds or None; env_of(src, a, b) -> Envelope or None;
    durations: {src: seconds} - an end past the source end becomes `hold` (last frame held, silence).
    Two pieces that continue each other in the same file (gap < 50 ms) are one take: that seam is not moved."""
    out, rep = [], []
    n = len(pieces)
    for i, p in enumerate(pieces):
        q = dict(p)
        if q.get("snap", True) is False or mode == "off":
            out.append(q)
            continue
        a, b = float(p["start"]), float(p["end"])
        glued_prev = i > 0 and str(pieces[i - 1]["src"]) == str(p["src"]) and abs(float(pieces[i - 1]["end"]) - a) < 0.05
        glued_next = i + 1 < n and str(pieces[i + 1]["src"]) == str(p["src"]) and abs(float(pieces[i + 1]["start"]) - b) < 0.05
        ws = _clean(words_of(p["src"], a - MAX_START_BACK - 1, b + MAX_EXTEND + 1) or [])
        env = env_of(p["src"], max(0.0, a - MAX_START_BACK - 1), b + MAX_EXTEND + 1.5)
        na, why_a = (a, "") if glued_prev else snap_start(a, ws, env, mode)
        if glued_next:
            nb, why_b, mute = b, "", None
        else:
            nb, why_b, mute = snap_end(b, ws, env, last=(i == n - 1), mode=mode, min_end=na)
        if nb - na < 0.6:                                     # snapping must never eat the piece
            na, nb, why_a, why_b, mute = a, max(b, a + 0.6), "", "kept: snapping left < 0.6 s", None
        dur = (durations or {}).get(str(p["src"]))
        if dur and nb > dur - 0.02:
            hold = round(nb - (dur - 0.02), 3)
            nb = round(dur - 0.02, 3)
            if i == n - 1 and hold > 0.04:
                q["hold"] = hold
                why_b = (why_b + "; " if why_b else "") + f"source ends: last frame held {hold:.2f} s"
        q["start"], q["end"] = na, nb
        if mute is not None and mute < nb:
            q["mute_from"] = mute
        q["_ctx"] = ws
        q["_words"] = [w for w in ws if w["s"] >= na - 0.01 and w["e"] <= (q.get("mute_from") or nb) + 0.02]
        rep.append({"piece": i, "from": [a, b], "to": [na, nb], "start": why_a, "end": why_b,
                    **({"mute_from": q["mute_from"]} if "mute_from" in q else {}), **({"hold": q["hold"]} if "hold" in q else {}),
                    "words": "precise" if ws and not any(w.get("approx") for w in ws) else ("approx" if ws else "none")})
        out.append(q)
    return out, rep


def check_pieces(pieces: list[dict], mode: str = "sentence", allow_open_end: bool = False) -> list[dict]:
    """Problems after snapping (uses p['_ctx'] from snap_pieces). level "error" blocks the render.
    Approximate words (spread over an SRT cue) only give warnings: their boundaries are guesses."""
    probs = []
    n = len(pieces)
    for i, p in enumerate(pieces):
        ctx = p.get("_ctx") or []
        if not ctx:
            continue
        approx = any(w.get("approx") for w in ctx)
        hard = "warn" if approx else "error"
        a, b = float(p["start"]), float(p["end"])
        endt = min(b, float(p["mute_from"])) if p.get("mute_from") else b
        k = _inside(ctx, a, 0.05)
        if k is not None:
            probs.append({"level": hard, "piece": i, "what": f"starts inside the word '{ctx[k]['w']}'"})
        k = _inside(ctx, endt, 0.05)
        if k is not None:
            probs.append({"level": hard, "piece": i, "what": f"ends inside the word '{ctx[k]['w']}'"})
        inside = [j for j, w in enumerate(ctx) if w["s"] >= a - 0.01 and w["e"] <= endt + 0.02]
        if not inside:
            continue
        j = inside[-1]
        if i == n - 1:
            tail = b + float(p.get("hold") or 0) - ctx[j]["e"]
            if tail < MIN_TAIL_END:
                probs.append({"level": hard, "piece": i, "what": f"the video ends {tail:.2f} s after the last word '{ctx[j]['w']}' (need >= {MIN_TAIL_END})"})
            if mode == "sentence" and not allow_open_end and not sentence_end(ctx, j):
                reach = [q for q in range(len(ctx) - 1) if sentence_end(ctx, q)
                         and endt - MAX_BACK <= ctx[q]["e"] <= endt + MAX_EXTEND]
                if not reach and phrase_end(ctx, j):     # speech without full stops / pauses: a phrase end is the best cut
                    probs.append({"level": "warn", "piece": i, "what": f"no sentence end within reach: the video ends at the "
                                  f"phrase pause after '{ctx[j]['w']}' (listen to the last seconds)"})
                else:
                    probs.append({"level": hard, "piece": i, "what": f"the video ends mid-sentence after '{ctx[j]['w']}'"
                                  f" (possible ends: {end_hints(ctx, endt)})"})
        elif mode == "sentence" and not sentence_end(ctx, j):
            probs.append({"level": "warn", "piece": i, "what": f"join after '{ctx[j]['w']}' is mid-sentence"})
    return probs


def end_hints(words: list[dict], t: float, span: float = 4.0, k: int = 3) -> str:
    """The k word ends near t with the longest pause after them: where a person would end the piece."""
    cand = []
    for q, w in enumerate(words):
        if abs(w["e"] - t) > span:
            continue
        if q == len(words) - 1:           # the end of the context window is not a real boundary
            continue
        gap = words[q + 1]["s"] - w["e"]
        cand.append((sentence_end(words, q), phrase_end(words, q), gap, q))
    best = sorted(cand, key=lambda c: (not c[0], not c[1], -c[2]))[:k]
    return ", ".join(f"{words[q]['e']:.2f} after '{words[q]['w']}'" + (" (sentence end)" if se else f" (pause {g:.2f} s)")
                     for se, _, g, q in sorted(best, key=lambda c: c[3])) or "none"


def join_texts(pieces: list[dict]) -> list[dict]:
    """The words around every join (final seconds), for the agent to read the seams."""
    out, off = [], 0.0
    for i, p in enumerate(pieces[:-1]):
        off += float(p["end"]) - float(p["start"])
        a = [w["w"] for w in (p.get("_words") or [])][-4:]
        b = [w["w"] for w in (pieces[i + 1].get("_words") or [])][:4]
        out.append({"at": round(off, 3), "before": " ".join(a), "after": " ".join(b)})
    return out


# ------------------------------------------------------------------ QA on the rendered sound

def join_is_clean(p: dict, q: dict) -> bool | None:
    """Precise word timings say the join p|q cuts no word (p ends after its last word, q starts before its first).
    None when the timings are approximate or missing (then only the sound level can tell)."""
    a_ctx, b_ctx = p.get("_ctx") or [], q.get("_ctx") or []
    if not a_ctx or not b_ctx or any(w.get("approx") for w in a_ctx + b_ctx):
        return None
    pe, qs = float(p.get("mute_from") or p["end"]), float(q["start"])
    last = [w for w in a_ctx if w["s"] < pe - 0.05]
    first = [w for w in b_ctx if w["e"] > qs + 0.05]
    return (not last or last[-1]["e"] <= pe - 0.02) and (not first or first[0]["s"] >= qs + 0.03)


def audio_qa(wav: Path | str, joins: list[float], duration: float, clean: list | None = None) -> dict:
    """Voice right at a join (both sides loud: a word was cut) or in the last 120 ms (the video stops on a word).
    clean[k] = join_is_clean(...) for joins[k]: when precise word timings say no word is cut but the level stays high,
    it is music / noise under the voice - a note to listen to, not a problem."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(wav), "-vn", "-ac", "1", "-ar", "16000",
                        "-af", "highpass=f=120,lowpass=f=3800", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32)
    env = envelope_of(x, 16000)
    probs, notes = [], []
    if not len(env.t):
        return {"ok": True, "problems": [], "skipped": "no audio"}
    for k, t in enumerate(joins):
        if env.voiced(t - 0.03) and env.voiced(t + 0.03) and env.voiced(t):
            if clean and k < len(clean) and clean[k]:
                notes.append(f"the level stays high at the join at {t:.2f}s, but the word timings show no cut word "
                             f"(music or noise under the voice?) - listen to this join")
            else:
                probs.append(f"voice runs through the join at {t:.2f}s (a word is probably cut)")
    tail = env.db[env.t >= duration - 0.12]
    if len(tail) and float(np.max(tail)) > env.thr:
        probs.append("voice in the last 120 ms: the video stops on a word")
    last_voice = env.t[env.db > env.thr]
    silent_tail = round(duration - float(last_voice[-1]), 2) if len(last_voice) else None
    return {"ok": not probs, "problems": probs, **({"notes": notes} if notes else {}),
            "silent_tail_s": silent_tail, "threshold_db": round(env.thr, 1)}
