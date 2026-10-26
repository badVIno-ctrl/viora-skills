"""Embedded VoiceEngine: offline Russian + English voices of any gender, age (2-105) and character.

The agent uses it through ONE entry: `python tools/shorts.py voice ...` (CLI) or the TTS engine "voiceengine"
(first in the "auto" chain for ru / en, so every plan, toon episode, stack and persona gets it by itself).

Weight: all models (171 MB unpacked) live in ONE sealed pack `assets/voice/voiceengine-models.tar.xz`.
Never open, list or read it: `voice-setup` (or the first voice call) unpacks it once, checks the sha256 and
reuses the folder afterwards. Where it goes (first that works): SHORTS_VOICE_MODELS, SHORTS_MODELS/voiceengine,
<skill>/.cache/models/voiceengine, ~/.cache/shorts/voiceengine, <tmp>/shorts-voiceengine.

Voice = one attribute string (same as VoiceEngine `--attrs`): "ж, 90, шёпотом, voice=Нюра, speed=0.9",
"м, 7, радостно", "дракон", "ведущая", "m2", or a bare name ("Кот Борис" = its own stable timbre).
Aliases ru-male-1 / ru-female-1 / en-male-1 ... keep old plans working. SHORTS_VOICEENGINE=off disables it.

Word timings: Russian words come from the model's own symbol durations (exact); English sentences are exact,
words inside a sentence are spread by length and real pauses (estimated, or faster-whisper when installed).
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np

from .config import asset, memory_dir, skill_root
from .util import ShortsError, log

SR = 48000
PACK_NAME = "voiceengine-models.tar.xz"
REV = "ve2"                     # bump when synthesis changes: part of the TTS cache key
REQUIRED = ("ru/speaker_f0.json", "ru/ru_voc.onnx", "ru/ru_speakers.npz", "ru_stress/homo_bert.npz",
            "en/voice_f0.json", "en/kokoro-v1.0.int8.f0.onnx", "en/kokoro_voices_en.npz")
PKG = Path(__file__).resolve().parent / "voiceengine"

# old voice names -> VoiceEngine attributes (presets "диктор" / "ведущая" are made for narration)
ALIASES = {
    "ru-male-1": "диктор", "ru-female-1": "ведущая", "ru-male-2": "м, 26, m4", "ru-female-2": "ж, 25, f5",
    "en-male-1": "диктор", "en-female-1": "ведущая", "en-male-2": "m, 26, m4", "en-female-2": "f, 25, f5",
}
DEFAULT = {"ru": "ru-male-1", "en": "en-male-1"}
_EDGE_ID = re.compile(r"^[a-z]{2,3}-[A-Z]{2}-\w+Neural$")
_PIPER_ID = re.compile(r"^[a-z]{2}_[A-Z]{2}-[\w-]+$")
OPENAI_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer", "verse"}

_ENGINE = None
_ELOCK = threading.Lock()
_SLOCK = threading.Lock()


# ---------------------------------------------------------------- availability and the models pack

def disabled() -> bool:
    return os.environ.get("SHORTS_VOICEENGINE", "").strip().lower() in ("0", "off", "no", "false", "disable", "disabled")


def deps_missing() -> list[str]:
    import importlib.util
    return [m for m in ("numpy", "onnxruntime") if importlib.util.find_spec(m) is None]


def pack_path() -> Path:
    return asset(f"voice/{PACK_NAME}")


def pack_info() -> dict:
    p = asset("voice/pack.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _complete(d: Path) -> bool:
    return all((d / r).is_file() for r in REQUIRED)


def _managed_ok(d: Path) -> bool:
    """A folder we unpacked ourselves: complete and made from this very pack."""
    m = d / ".pack.json"
    if not (_complete(d) and m.exists()):
        return False
    try:
        return json.loads(m.read_text(encoding="utf-8")).get("sha256") == pack_info().get("sha256")
    except (OSError, ValueError):
        return False


def candidate_dirs() -> list[Path]:
    out = []
    if os.environ.get("SHORTS_MODELS"):
        out.append(Path(os.environ["SHORTS_MODELS"]).expanduser() / "voiceengine")
    out += [skill_root() / ".cache" / "models" / "voiceengine", Path.home() / ".cache" / "shorts" / "voiceengine",
            Path(tempfile.gettempdir()) / "shorts-voiceengine"]
    return out


def models_dir() -> Path | None:
    """Ready models folder or None (nothing unpacked yet)."""
    own = os.environ.get("SHORTS_VOICE_MODELS")
    if own:   # a folder the user points to (for example an unpacked VoiceEngine/models): used as is
        d = Path(own).expanduser()
        return d if _complete(d) else None
    for d in candidate_dirs():
        if _managed_ok(d):
            return d
    return None


def _writable(d: Path) -> bool:
    try:
        d.parent.mkdir(parents=True, exist_ok=True)
        probe = d.parent / f".probe-{os.getpid()}"
        probe.write_text("x")
        probe.unlink()
        return True
    except OSError:
        return False


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ensure_models(verify: bool = True) -> Path:
    """Unpack the sealed pack once (about 10-20 s), then reuse it. Safe for parallel calls (file lock)."""
    d = models_dir()
    if d:
        return d
    if os.environ.get("SHORTS_VOICE_MODELS"):
        raise ShortsError(f"SHORTS_VOICE_MODELS={os.environ['SHORTS_VOICE_MODELS']} has no complete models "
                          f"(needs {', '.join(REQUIRED[:2])} ...)")
    pack, info = pack_path(), pack_info()
    if not pack.exists():
        raise ShortsError(f"voice models pack is missing: {pack} (the skill zip was unpacked without assets/voice)")
    target = next((c for c in candidate_dirs() if _writable(c)), None)
    if target is None:
        raise ShortsError("no writable folder for voice models: set SHORTS_VOICE_MODELS or SHORTS_MODELS")
    lock = target.parent / (target.name + ".lock")
    with open(lock, "a+") as lf:
        try:
            import fcntl
            fcntl.flock(lf, fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        if _managed_ok(target):
            return target
        t0 = time.time()
        if verify and info.get("sha256") and _sha256(pack) != info["sha256"]:
            raise ShortsError(f"voice models pack is damaged (sha256 differs from assets/voice/pack.json): {pack}")
        tmp = Path(tempfile.mkdtemp(prefix=".unpack-", dir=target.parent))
        try:
            with tarfile.open(pack, "r:xz") as tf:
                try:
                    tf.extractall(tmp, filter="data")
                except TypeError:       # Python < 3.11.4 has no filter argument
                    tf.extractall(tmp)  # noqa: S202 - our own sealed pack, sha256 checked above
            src = tmp / "models"
            if not _complete(src):
                raise ShortsError("voice models pack is incomplete")
            if target.exists():
                shutil.rmtree(target)
            src.rename(target)
            (target / ".pack.json").write_text(json.dumps({"sha256": info.get("sha256"), "pack": PACK_NAME,
                                                           "unpacked_s": round(time.time() - t0, 1)}), encoding="utf-8")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        log.info("voice models unpacked to %s in %.1f s", target, time.time() - t0)
        return target


def available() -> bool:
    """Cheap check for the TTS chain: not disabled, deps importable, models unpacked or the pack present."""
    if disabled() or deps_missing():
        return False
    return bool(models_dir() or (pack_path().exists() and not os.environ.get("SHORTS_VOICE_MODELS")))


def status() -> dict:
    d = models_dir()
    return {"enabled": not disabled(), "deps_missing": deps_missing(), "pack": pack_path().exists(),
            "pack_mb": round(pack_path().stat().st_size / 1e6, 1) if pack_path().exists() else None,
            "models": str(d) if d else None, "available": available(),
            "next": None if d else "python tools/shorts.py voice-setup   # unpack once, then self-test"}


def engine():
    global _ENGINE
    with _ELOCK:
        if _ENGINE is None:
            miss = deps_missing()
            if miss:
                raise ShortsError(f"VoiceEngine needs {' and '.join(miss)}: python3 -m pip install {' '.join(miss)}")
            from .voiceengine.engine.core import Engine
            dicts = [str(PKG / "user_stress.txt"), str(memory_dir() / "stress.txt")]
            th = int(os.environ.get("SHORTS_VOICE_THREADS") or 0) or None
            _ENGINE = Engine(models_dir=str(ensure_models()), threads=th, user_dicts=dicts)
        return _ENGINE


# ---------------------------------------------------------------- voices

def is_foreign_voice(voice: str | None) -> bool:
    """Voice ids of other engines (edge, piper, openai): VoiceEngine must not guess them."""
    v = (voice or "").strip()
    return bool(_EDGE_ID.match(v) or _PIPER_ID.match(v) or v.lower() in OPENAI_VOICES)


def supports(lang: str, voice: str | None) -> bool:
    return (lang or "ru")[:2] in ("ru", "en") and not is_foreign_voice(voice)


def attrs_for(voice: str | None, lang: str) -> str:
    """Voice field -> VoiceEngine attributes. Old names work alone and inside a list ("ru-female-1, шёпотом")."""
    v = (voice or "").strip() or DEFAULT.get((lang or "ru")[:2], "ru-male-1")
    if v in ALIASES:
        return ALIASES[v]
    if "," in v:
        parts = [x.strip() for x in v.split(",")]
        if any(x in ALIASES for x in parts):
            return ", ".join(ALIASES.get(x, x) for x in parts if x)
    return v


def parse(attrs: str) -> tuple[dict, str | None]:
    """Attribute string -> (spec, name). Words the parser does not know become the name: own stable timbre,
    gender guessed from it ("Валя" -> female)."""
    from .voiceengine.engine.script import parse_attrs
    spec = parse_attrs(attrs or "", {})
    unknown = [str(u).strip() for u in spec.pop("_unknown", []) if str(u).strip() and "=" not in str(u)]
    name = " ".join(unknown) or None
    if name and not spec.get("voice"):
        spec["voice"] = name
    return spec, name


def gender_of(voice: str | None, lang: str = "ru") -> str | None:
    """'ж, 72, voice=Валя' -> 'female' (for the edge / openai fallback). None when nothing says it."""
    if not voice or is_foreign_voice(voice):
        return None
    try:
        from .voiceengine.engine.characters import PRESETS
        from .voiceengine.engine.script import guess_from_name
        from .voiceengine.engine.voices import BANK
        spec, name = parse(attrs_for(voice, lang))
        if spec.get("gender"):
            return spec["gender"]
        if spec.get("preset") and PRESETS.get(spec["preset"], {}).get("gender"):
            return PRESETS[spec["preset"]]["gender"]
        if str(spec.get("voice", "")).lower() in BANK:
            return BANK[str(spec["voice"]).lower()]["gender"]
        if name:
            return guess_from_name(name)[0]
    except Exception:  # noqa: BLE001 - only a hint for another engine
        return None
    return None


def spec_for(attrs: str, lang: str, speed: float = 1.0) -> tuple[dict, str | None]:
    spec, name = parse(attrs)
    if "lang" not in spec and (lang or "")[:2] in ("ru", "en"):
        spec["lang"] = lang[:2]           # keep one voice in a video: English words in Russian are read in Russian
    if spec.get("lang") == "auto":
        spec.pop("lang")
    if speed and abs(float(speed) - 1.0) > 1e-6:
        spec["speed"] = float(spec.get("speed") or 1.0) * float(speed)
    return spec, name


def describe(voice: str | None, lang: str = "ru") -> str:
    eng = engine()
    spec, name = spec_for(attrs_for(voice, lang), lang)
    return eng.describe(eng.resolve(spec, name), lang[:2] if lang[:2] in ("ru", "en") else None)


# ---------------------------------------------------------------- word timings

def _key(w: str) -> str:
    return re.sub(r"[^\w]", "", str(w).lower().replace("ё", "е").replace("+", ""))


def _weights(toks: list[str]) -> list[float]:
    out = []
    for t in toks:
        k = _key(t)
        digits = len(re.findall(r"\d", k))
        syl = len(re.findall(r"[aeiouyаеёиоуыэюяіїє]+", k)) + int(round(1.6 * digits)) or 1
        out.append(0.35 + 0.55 * syl + 0.04 * len(k))
    return out


def _gaps(seg: np.ndarray, sr: int, min_len: float = 0.04) -> list[tuple[float, float]]:
    """Silent runs inside a sentence (seconds from its start), edges excluded."""
    hop = int(0.01 * sr)
    n = len(seg) // hop
    if n < 10:
        return []
    e = np.sqrt((seg[: n * hop].astype(np.float64).reshape(n, hop) ** 2).mean(1) + 1e-12)
    quiet = 20 * np.log10(e / (e.max() + 1e-12) + 1e-12) < -38
    out, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if i > 2 and j < n - 2 and (j - i) * 0.01 >= min_len:
                out.append((i * 0.01, j * 0.01))
            i = j
        else:
            i += 1
    return out


def _pick_gaps(want: list[float], gaps: list[tuple[float, float]], tol: float) -> list[tuple[float, float] | None]:
    """Monotonic best match of expected phrase ends to real pauses (dynamic programming)."""
    m, n = len(want), len(gaps)
    score = [[0.0] * (n + 1) for _ in range(m + 1)]
    take = [[0] * (n + 1) for _ in range(m + 1)]      # 0 skip cut, 1 skip gap, 2 match
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            g = gaps[j - 1]
            fit = 1.0 - abs((g[0] + g[1]) / 2 - want[i - 1]) / tol
            best, how = score[i - 1][j], 0
            if score[i][j - 1] > best:
                best, how = score[i][j - 1], 1
            if fit > 0 and score[i - 1][j - 1] + fit * (1.0 + min(g[1] - g[0], 0.3)) > best:
                best, how = score[i - 1][j - 1] + fit * (1.0 + min(g[1] - g[0], 0.3)), 2
            score[i][j], take[i][j] = best, how
    res: list[tuple[float, float] | None] = [None] * m
    i, j = m, n
    while i > 0 and j > 0:
        if take[i][j] == 2:
            res[i - 1] = gaps[j - 1]
            i, j = i - 1, j - 1
        elif take[i][j] == 1:
            j -= 1
        else:
            i -= 1
    return res


def _spread(toks: list[str], s: float, e: float, seg: np.ndarray | None, sr: int) -> list[tuple[str, float, float]]:
    """English (no durations): phrases snap to real pauses at , ; : and the words inside follow their length."""
    if not toks:
        return []
    wts = _weights(toks)
    cuts = [i + 1 for i, t in enumerate(toks[:-1]) if re.search(r"[,;:)\]]$|[\u2014\u2013-]$", t)]
    gaps = _gaps(seg, sr) if seg is not None and len(seg) else []
    total = sum(wts)
    spans = [(0, len(toks), s, e)]
    if cuts and gaps:
        speech = (e - s) - sum(g[1] - g[0] for g in gaps)
        want, acc = [], 0.0
        for c in cuts:
            frac = sum(wts[:c]) / total
            # expected end of the phrase + the pauses that come before it
            t = frac * speech
            t += sum(g[1] - g[0] for g in gaps if (g[0] + g[1]) / 2 < t + acc)
            want.append(t)
        picked = _pick_gaps(want, gaps, 0.22 * (e - s) + 0.25)
        spans, a, t0 = [], 0, s
        for c, g in zip(cuts, picked):
            if g is None:
                continue
            spans.append((a, c, t0, s + g[0]))
            a, t0 = c, s + g[1]
        spans.append((a, len(toks), t0, e))
    out = []
    for a, b, t0, t1 in spans:
        w = wts[a:b]
        tot = sum(w) or 1.0
        t = t0
        for tok, wt in zip(toks[a:b], w):
            d = (t1 - t0) * wt / tot
            out.append((tok, round(t, 3), round(t + d * 0.94, 3)))
            t += d
    return out


def _owners(toks: list[str], tk: list[str], wk: list[str], norm) -> list[int | None]:
    """Which written token each spoken word belongs to: characters of the tokens spelled out one by one
    ("25-м" -> "двадцать пятом", "iPhone" -> "айфоун") matched against the model words."""
    exp = []
    for t, k in zip(toks, tk):
        try:
            e = _key(norm(t)) if norm else k
        except Exception:  # noqa: BLE001 - normalizer hiccup on one token: use the token itself
            e = k
        exp.append(e or k)
    a_own = [i for i, e in enumerate(exp) for _ in e]
    b_own = [j for j, w in enumerate(wk) for _ in w]
    votes: list[dict[int, int]] = [dict() for _ in wk]
    sm = difflib.SequenceMatcher(None, "".join(exp), "".join(wk), autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            j, i = b_own[b + k], a_own[a + k]
            votes[j][i] = votes[j].get(i, 0) + 1
    own: list[int | None] = [max(v, key=v.get) if v else None for v in votes]
    lo = 0
    for j, o in enumerate(own):          # keep the order: never go back to an earlier token
        if o is not None:
            own[j] = lo = max(lo, o)
    return own


def _match(toks: list[str], words: list[tuple[str, float, float]], norm=None) -> list[tuple[str, float, float]]:
    """Sentence tokens (as written) <- model words (normalized: numbers spelled, Latin transliterated)."""
    tk, wk = [_key(t) for t in toks], [_key(w[0]) for w in words]
    out: list[tuple[str, float, float] | None] = [None] * len(toks)
    sm = difflib.SequenceMatcher(None, tk, wk, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                out[i1 + k] = (toks[i1 + k], words[j1 + k][1], words[j1 + k][2])
        elif op == "replace":
            own = _owners(toks[i1:i2], tk[i1:i2], wk[j1:j2], norm)
            span: dict[int, list[float]] = {}
            for j, o in enumerate(own):
                if o is None:
                    o = next((x for x in own[j:] if x is not None), i2 - i1 - 1)
                w = words[j1 + j]
                cur = span.setdefault(o, [w[1], w[2]])
                cur[0], cur[1] = min(cur[0], w[1]), max(cur[1], w[2])
            for o, (a, b) in span.items():
                out[i1 + o] = (toks[i1 + o], a, b)
        elif op == "insert" and i1 > 0 and out[i1 - 1]:      # extra spoken words: the previous token owns them
            prev = out[i1 - 1]
            out[i1 - 1] = (prev[0], prev[1], words[j2 - 1][2])
    last = words[0][1] if words else 0.0
    res = []
    for i, o in enumerate(out):
        if o is None:     # written but not spoken (symbols): zero length at the current time
            o = (toks[i], last, last)
        last = o[2]
        res.append((o[0], round(float(o[1]), 3), round(float(o[2]), 3)))
    return res


def sentence_words(mark: dict, y: np.ndarray | None, sr: int = SR, norm=None) -> tuple[list[tuple[str, float, float]], bool]:
    toks = [t for t in str(mark["text"]).split() if _key(t)]
    if mark.get("words"):
        return _match(toks, mark["words"], norm), False
    seg = None if y is None else y[int(mark["s"] * sr): int(mark["e"] * sr)]
    return _spread(toks, mark["s"], mark["e"], seg, sr), True


def marks_to_words(text: str, marks: list[dict], y: np.ndarray | None, sr: int = SR, norm=None) -> tuple[list[dict], bool]:
    """Engine sentence marks -> [{"w","s","e"}] over the ORIGINAL tokens of `text` (punctuation kept, pause
    markers dropped), plus `estimated` (True when any sentence had no model durations)."""
    from .voiceengine.engine.script import PAUSE_RE
    spoken, est = [], False
    for m in marks:
        ws, e = sentence_words(m, y, sr, norm)
        spoken += ws
        est |= e
    pauses = [(m.start(), m.end()) for m in PAUSE_RE.finditer(text)]
    toks = []
    for m in re.finditer(r"\S+", text):
        if any(a < m.end() and m.start() < b for a, b in pauses):
            continue
        toks.append(m.group(0))
    real = [t for t in toks if _key(t)]
    sk = [_key(w[0]) for w in spoken]
    times: dict[int, tuple[float, float]] = {}
    sm = difflib.SequenceMatcher(None, [_key(t) for t in real], sk, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("equal", "replace") and j2 > j1:
            for k in range(i1, i2):
                j = j1 + min(k - i1, j2 - j1 - 1) if op == "equal" else None
                if j is not None:
                    times[k] = (spoken[j][1], spoken[j][2])
                else:
                    a, b = spoken[j1][1], spoken[j2 - 1][2]
                    n = i2 - i1
                    times[k] = (a + (b - a) * (k - i1) / n, a + (b - a) * (k - i1 + 1) / n)
    out, ri, last = [], 0, 0.0
    for t in toks:
        if not _key(t):
            if out:
                out[-1]["w"] += " " + t
            continue
        s, e = times.get(ri, (last, last))
        out.append({"w": t, "s": round(float(s), 3), "e": round(float(max(e, s)), 3)})
        last = e
        ri += 1
    return out, est


# ---------------------------------------------------------------- synthesis

def write_wav(path: Path, y: np.ndarray, sr: int = SR) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(np.asarray(y, np.float32), -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def _whisper_words(wav: Path, text: str, lang: str) -> list[dict] | None:
    if os.environ.get("SHORTS_WHISPER", "").lower() == "off":
        return None
    from .engine import tts
    bounds = tts.whisper_boundaries(wav, lang)
    return tts._align_words_to_text(text, bounds) if bounds else None


def speak(text: str, out_wav: Path, *, voice: str | None = None, lang: str = "ru", speed: float = 1.0) -> dict:
    """Text -> 48 kHz mono wav + word timings. voice: attribute string or alias (see module doc)."""
    text = str(text or "").strip()
    if not text:
        raise ShortsError("nothing to voice: empty text")
    attrs = attrs_for(voice, lang)
    eng = engine()
    spec, name = spec_for(attrs, lang, speed)
    v = eng.resolve(spec, name)
    marks: list[dict] = []
    with _SLOCK:
        y = eng.render(text, v, marks=marks)
    if not len(y):
        raise ShortsError("VoiceEngine produced no audio (no letters to read?)")
    write_wav(out_wav, y)
    words, est = marks_to_words(text, marks, y, norm=eng.norm)
    if est:
        ww = _whisper_words(Path(out_wav), text, lang)
        if ww:
            words, est = ww, False
    if v["warnings"]:
        log.warning("voice %r: not recognized: %s", attrs, "; ".join(v["warnings"]))
    return {"wav": Path(out_wav), "duration": len(y) / SR, "words": words, "estimated": est, "voice": attrs,
            "warnings": v["warnings"], "sentences": len(marks)}


def speak_script(script: str, out_wav: Path, *, defaults: str | None = None, lang: str | None = None,
                 save_lines: str | None = None) -> dict:
    """Dialogue script ("@Бабушка = ж, 90", "Бабушка: реплика", "[пауза 1]") -> one wav + words + line list."""
    eng = engine()
    spec, _ = spec_for(defaults or "", lang or "auto")
    marks: list[dict] = []
    with _SLOCK:
        y, info = eng.script(script, spec, save_lines=save_lines, marks=marks)
    if not len(y):
        raise ShortsError("script has no spoken lines")
    write_wav(out_wav, y)
    words, est = [], False
    for m in marks:
        ws, e = sentence_words(m, y, norm=eng.norm)
        est |= e
        words += [{"w": w, "s": s, "e": e2, "speaker": m.get("speaker", "")} for w, s, e2 in ws]
    return {"wav": Path(out_wav), "duration": len(y) / SR, "words": words, "estimated": est, "lines": info}


def srt(words: list[dict], max_chars: int = 42, max_sec: float = 3.2) -> str:
    """Words -> SRT cues (break on sentence ends, long cues and speaker changes)."""
    def ts(t: float) -> str:
        ms = int(round(max(0.0, t) * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    cues, cur = [], []
    for w in words:
        if cur and (len(" ".join(x["w"] for x in cur + [w])) > max_chars or w["e"] - cur[0]["s"] > max_sec
                    or w.get("speaker") != cur[-1].get("speaker")):
            cues.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?\u2026]['\"\u00bb)]*$", w["w"]):
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)
    return "\n".join(f"{i}\n{ts(c[0]['s'])} --> {ts(max(c[-1]['e'], c[0]['s'] + 0.3))}\n{' '.join(x['w'] for x in c)}\n"
                     for i, c in enumerate(cues, 1))


def to_file(wav: Path, out: Path) -> Path:
    """wav -> .wav / .mp3 / .ogg / .m4a / .flac by extension (ffmpeg)."""
    out = Path(out)
    if out.suffix.lower() in ("", ".wav"):
        if Path(wav).resolve() != out.resolve():
            shutil.copyfile(wav, out)
        return out
    from .util import run
    codec = {".mp3": ["-c:a", "libmp3lame", "-q:a", "2"], ".m4a": ["-c:a", "aac", "-b:a", "192k"],
             ".ogg": ["-c:a", "libvorbis", "-q:a", "6"], ".flac": []}.get(out.suffix.lower(), [])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, *codec, out])
    return out


def list_all() -> str:
    from .voiceengine.engine.characters import (EFFECT_ALIASES, EFFECTS, EMOTION_ALIASES, EMOTIONS, PRESET_ALIASES,
                                                PRESETS)
    from .voiceengine.engine.script import ROLES
    from .voiceengine.engine.voices import BANK
    L = ["Голоса (voice=..., или просто m1..f6):"]
    L += [f"  {k:<3} {'муж.' if b['gender'] == 'male' else 'жен.'}  {b['desc']}" for k, b in BANK.items()]
    L.append("  любое имя = свой стабильный тембр: \"Кот Борис\", \"voice=Нюра\"")
    L.append("Персонажи (preset):")
    L += [f"  {k:<14} {p['desc']}" + (f"  [{', '.join(a for a, t in PRESET_ALIASES.items() if t == k)}]"
                                      if any(t == k for t in PRESET_ALIASES.values()) else "") for k, p in PRESETS.items()]
    L.append("Эмоции:")
    L += [f"  {k:<13} {p['desc']}" + (f"  [{', '.join(a for a, t in EMOTION_ALIASES.items() if t == k)}]"
                                     if any(t == k for t in EMOTION_ALIASES.values()) else "") for k, p in EMOTIONS.items()]
    L.append("Эффекты (effect=a+b):")
    L += [f"  {k:<12} {d}" + (f"  [{', '.join(a for a, t in EFFECT_ALIASES.items() if t == k)}]"
                              if any(t == k for t in EFFECT_ALIASES.values()) else "") for k, d in EFFECTS.items()]
    L.append("Роли (слово задаёт пол и возраст): " + ", ".join(f"{r}={'м' if g == 'male' else 'ж'}{a}"
                                                             for r, (g, a) in ROLES.items()))
    L.append("Псевдонимы для старых планов: " + ", ".join(f"{k} = \"{v}\"" for k, v in ALIASES.items()))
    return "\n".join(L)


def selftest(out_dir: Path) -> dict:
    """Two phrases (ru + en): duration, level and word timings. Used by voice-setup and doctor --deep."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, ok = [], True
    for name, text, voice, lang in (("ru", "Проверка голоса: двадцать пять слов в минуту, без интернета.", "ведущая", "ru"),
                                    ("en", "Voice check, offline and fast.", "m, 30, m3", "en")):
        t = time.time()
        try:
            r = speak(text, out_dir / f"selftest_{name}.wav", voice=voice, lang=lang)
            good = r["duration"] > 0.8 and len(r["words"]) >= 4
            rows.append({"lang": name, "ok": good, "sec": round(r["duration"], 2), "work_s": round(time.time() - t, 1),
                         "words": len(r["words"]), "estimated": r["estimated"], "file": str(r["wav"])})
        except Exception as e:  # noqa: BLE001 - report, never crash setup
            good = False
            rows.append({"lang": name, "ok": False, "error": str(e)[:200]})
        ok &= good
    return {"ok": ok, "checks": rows}
