"""Animation ("survival") episodes: skeleton, scenario picker, offline episode check.

Offline and deterministic. Nothing here renders, downloads or installs anything.
Format of shotlist.md / brief.json / words.json: reference/animation.md.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from .config import skill_root
from .util import ShortsError

TEMPLATES = ("brief.json", "script.md", "shotlist.md", "notes.md")
WPS_IDEAL = (2.4, 2.7)
WPS_HARD = (2.3, 2.8)
DURATION_RANGE = (65.0, 90.0)
MAX_SCENE_S = 3.0
MIN_SCENE_S = 1.0
MIN_SCHEMES = 3
MAX_3D_SHARE = 0.25
MIN_TEXT_PX = 34
MAX_SFX = 4
MAX_LIGHTS_OUT = 3
HOOK_MAX_WORDS = 12
EPS = 0.06
CLICHES = ("давайте разберёмся", "давайте разберемся", "представьте себе", "и вот тут начинается самое интересное")
VOICES = ("record", "edge", "piper", "elevenlabs", "A", "B", "C")

COLUMNS = {
    "time": ("время", "time", "t", "тайм", "тайминг"),
    "words": ("слова", "words", "фраза"),
    "frame": ("кадр", "frame", "в кадре", "что в кадре"),
    "type": ("тип", "type"),
    "layers": ("слои", "layers"),
    "motion": ("движение", "motion", "камера"),
    "transition": ("переход", "transition"),
    "hud": ("hud", "плашка", "hud-плашка"),
    "sound": ("звук", "sound", "sfx"),
}
REQUIRED_COLUMNS = ("time", "frame", "layers", "motion", "sound")
PARTS = (
    ("крючок", ("крючок",)),
    ("ошибка", ("ошибк",)),
    ("что на самом деле", ("на самом деле", "что происходит")),
    ("что делать", ("что делать", "шаги")),
    ("поворот", ("поворот", "вопрос", "финал")),
)
_WORD = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+(?:[-'’][0-9A-Za-zА-Яа-яЁё]+)*")


# ------------------------------------------------------------------ helpers

def _scenarios() -> dict:
    p = skill_root() / "templates" / "animation" / "scenarios.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ShortsError(f"scenarios.json is missing or invalid: {p}: {e}") from e


def spoken_words(text: str) -> list[str]:
    """Words of the voice text: no headings, quotes (>), table rows (|), [directions] or <!-- comments -->."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] in "#>|" or s.startswith("---"):
            continue
        out += _WORD.findall(re.sub(r"\[[^\]]*\]", " ", s))
    return out


def parse_time(s: str) -> float:
    """'12', '12.5', '12,5', '1:05.5', '00:01:05' (an optional trailing 'с') -> seconds."""
    s = s.strip().lower().rstrip("с").strip().replace(",", ".")
    parts = s.split(":")
    if not 1 <= len(parts) <= 3 or not all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        raise ValueError(f"bad time {s!r}")
    v = 0.0
    for p in parts:
        v = v * 60 + float(p)
    return v


def parse_range(cell: str) -> tuple[float, float]:
    bits = re.split(r"\s*(?:->|→|–|—|-|\.\.)\s*", cell.strip(), maxsplit=1)
    if len(bits) != 2:
        raise ValueError(f"time must look like 0.0-2.4, got {cell!r}")
    a, b = parse_time(bits[0]), parse_time(bits[1])
    if b <= a:
        raise ValueError(f"end is not after start in {cell!r}")
    return a, b


def parse_table(text: str) -> tuple[dict[str, int], list[list[str]], list[str]]:
    """First markdown table in text -> (column index by role, rows of cells, unknown headers)."""
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in text.splitlines() if ln.strip().startswith("|")]
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    if not rows:
        return {}, [], []
    cols: dict[str, int] = {}
    unknown: list[str] = []
    for i, h in enumerate(rows[0]):
        role = next((k for k, names in COLUMNS.items() if h.strip().lower() in names), None)
        if role and role not in cols:
            cols[role] = i
        elif not role:
            unknown.append(h)
    return cols, rows[1:], unknown


def classify_type(cell: str) -> tuple[str, str]:
    """Type cell -> (kind, scheme name). Kinds: 2d, scheme, closeup, 3d, unknown."""
    c = cell.strip().lower()
    name = c.split(":", 1)[1].strip() if ":" in c else ""
    if c.startswith(("3d", "3д")):
        return "3d", ""
    if c.startswith(("схем", "scheme", "diagram")):
        return "scheme", name
    if c.startswith(("2d", "2д")):
        return "2d", ""
    if c.startswith(("предмет", "крупн", "closeup", "close-up")):
        return "closeup", ""
    return "unknown", ""


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ------------------------------------------------------------------ init / pick

def init_episode(name: str, root: str | Path = ".") -> dict:
    if not re.fullmatch(r"[\w.-]+", name or "") or name in (".", ".."):
        raise ShortsError("anim-init: NAME is a short folder name (letters, digits, - _ .), got " + repr(name))
    ep = Path(root) / "episodes" / name
    ep.mkdir(parents=True, exist_ok=True)
    (ep / "voice").mkdir(exist_ok=True)
    (ep / "assets").mkdir(exist_ok=True)
    tdir = skill_root() / "templates" / "animation"
    created, skipped = [], []
    for fn in TEMPLATES:
        dst = ep / fn
        if dst.exists():
            skipped.append(str(dst))
            continue
        src = tdir / ("episode-" + fn)
        if not src.exists():
            raise ShortsError(f"template is missing: {src}")
        text = src.read_text(encoding="utf-8")
        if fn == "brief.json":
            b = json.loads(text)
            b["episode"] = name
            text = json.dumps(b, ensure_ascii=False, indent=2) + "\n"
        dst.write_text(text, encoding="utf-8")
        created.append(str(dst))
    dst = ep / "words.json"
    if dst.exists():
        skipped.append(str(dst))
    else:
        dst.write_text("[]\n", encoding="utf-8")
        created.append(str(dst))
    return {"episode": str(ep), "created": created, "skipped_existing": skipped,
            "next": "fill brief.json, then script.md (stage 2); python3 tools/shorts.py anim-check " + str(ep) + " --stage script"}


def compatible(sc: dict, disaster: dict, place: dict) -> bool:
    for r in sc.get("incompatible", []):
        if set(place["tags"]) & set(r["place_tags"]) and set(disaster["tags"]) & set(r["disaster_tags"]):
            return False
    return True


def pick(n: int = 3, seed: int | None = None) -> dict:
    sc = _scenarios()
    if not 1 <= n <= 10:
        raise ShortsError("anim-pick: --n is 1..10")
    rng = random.Random(seed)
    ds, ps = list(sc["disasters"]), list(sc["places"])
    rng.shuffle(ds)
    rng.shuffle(ps)
    pairs, used_d, used_p = [], set(), set()
    for d in ds:
        if len(pairs) >= n:
            break
        for p in ps:
            if p["id"] in used_p or not compatible(sc, d, p):
                continue
            pairs.append({"disaster": d["name"], "disaster_id": d["id"], "place": p["name"], "place_id": p["id"]})
            used_d.add(d["id"])
            used_p.add(p["id"])
            break
    return {"seed": seed, "pairs": pairs,
            "judge_each_by": ["понятна ли за 1 секунду", "есть ли неочевидный поворот", "можно ли показать простыми схемами"],
            "hook_formulas": sc.get("hook_formulas", [])}


# ------------------------------------------------------------------ check

class _R:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.stats: dict = {}

    def err(self, m):
        self.errors.append(m)

    def warn(self, m):
        self.warnings.append(m)


def _load_json(path: Path, r: _R, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        r.err(f"{label}: file is missing")
    except ValueError as e:
        r.err(f"{label}: invalid JSON ({e})")
    return None


def _check_brief(d: Path, r: _R) -> float | None:
    b = _load_json(d / "brief.json", r, "brief.json")
    if not isinstance(b, dict):
        if b is not None:
            r.err("brief.json: must be an object")
        return None
    for k in ("disaster", "place", "hero_name"):
        if not str(b.get(k) or "").strip():
            r.warn(f"brief.json: '{k}' is empty")
    if b.get("voice") not in VOICES:
        r.warn(f"brief.json: voice should be one of {', '.join(VOICES)}")
    if b.get("fps") not in (None, 30):
        r.warn("brief.json: fps is 30 in the format (reference/animation.md)")
    if b.get("size") not in (None, [1080, 1920]):
        r.warn("brief.json: size is [1080, 1920] in the format")
    mp = b.get("text_min_px")
    if mp is not None and (not _num(mp) or mp < MIN_TEXT_PX):
        r.err(f"brief.json: text_min_px {mp} is below {MIN_TEXT_PX}")
    dur = b.get("duration_s")
    if not _num(dur) or dur <= 0:
        r.err("brief.json: duration_s must be a number (65..90)")
        return None
    return float(dur)


def _check_script(d: Path, dur: float | None, r: _R) -> int:
    p = d / "script.md"
    if not p.exists():
        r.err("script.md: file is missing")
        return 0
    text = p.read_text(encoding="utf-8")
    n = len(spoken_words(text))
    r.stats["script_words"] = n
    if dur:
        wps = n / dur
        r.stats["words_per_s"] = round(wps, 2)
        r.stats["words_expected"] = [round(dur * WPS_IDEAL[0]), round(dur * WPS_IDEAL[1])]
        if wps < WPS_HARD[0] or wps > WPS_HARD[1]:
            r.err(f"script.md: {n} words for {dur:g} s is {wps:.2f} words/s; need {WPS_IDEAL[0]}-{WPS_IDEAL[1]} "
                  f"(about {r.stats['words_expected'][0]}-{r.stats['words_expected'][1]} words)")
        elif wps < WPS_IDEAL[0] or wps > WPS_IDEAL[1]:
            r.warn(f"script.md: {wps:.2f} words/s is outside {WPS_IDEAL[0]}-{WPS_IDEAL[1]}")
    heads = " ".join(ln.lower() for ln in text.splitlines() if ln.lstrip().startswith("#"))
    for label, keys in PARTS:
        if not any(k in heads for k in keys):
            r.warn(f"script.md: no heading for part '{label}' (5 parts, reference/animation.md)")
    low = text.lower()
    for c in CLICHES:
        if c in low:
            r.warn(f"script.md: cliche '{c}'")
    hook = _hook_words(text)
    if hook and len(hook) > HOOK_MAX_WORDS:
        r.warn(f"script.md: the first sentence has {len(hook)} words; the hook is up to {HOOK_MAX_WORDS}")
    return n


def _hook_words(text: str) -> list[str]:
    body = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    lines = [ln.strip() for ln in body.splitlines()]
    flow = " ".join(ln for ln in lines if ln and ln[0] not in "#>|" and not ln.startswith("---"))
    flow = re.sub(r"\[[^\]]*\]", " ", flow).strip()
    first = re.split(r"(?<=[.!?…])\s", flow, maxsplit=1)[0] if flow else ""
    return _WORD.findall(first)


def _check_shotlist(d: Path, dur: float | None, r: _R) -> float | None:
    p = d / "shotlist.md"
    if not p.exists():
        r.err("shotlist.md: file is missing")
        return None
    cols, rows, _ = parse_table(p.read_text(encoding="utf-8"))
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        r.err("shotlist.md: no column(s) " + ", ".join(missing) + " (header: Время | Слова | Кадр | Тип | Слои | Движение | Переход | HUD | Звук)")
        return None
    if not rows:
        r.err("shotlist.md: the table has no rows")
        return None

    def cell(row, role):
        i = cols.get(role)
        return row[i].strip() if i is not None and i < len(row) else ""

    scenes, schemes, lights, sfx, prev_tr = [], set(), 0, 0, ""
    dur3d = total = 0.0
    for n, row in enumerate(rows, 1):
        tag = f"shotlist.md row {n}"
        try:
            a, b = parse_range(cell(row, "time"))
        except ValueError as e:
            r.err(f"{tag}: {e}")
            continue
        scenes.append((n, a, b))
        for role in ("frame", "layers", "motion", "sound"):
            if cell(row, role).strip(" -") == "":
                r.err(f"{tag}: '{role}' is empty (write 'нет' / 'тишина' if there is nothing)")
        kind, name = classify_type(cell(row, "type")) if "type" in cols else ("unknown", "")
        if "type" in cols and kind == "unknown":
            r.warn(f"{tag}: type '{cell(row, 'type')}' is not 2D / схема / предмет / 3D")
        if "type" not in cols:
            kind = "2d"
        if kind == "scheme":
            schemes.add(name or "схема")
            if not name:
                r.warn(f"{tag}: name the scheme ('схема: разрез') so different schemes can be counted")
        if kind == "3d":
            dur3d += b - a
        total += b - a
        if b - a > MAX_SCENE_S + EPS:
            r.err(f"{tag}: the picture holds {b - a:.1f} s; change it at least every {MAX_SCENE_S:g} s")
        elif b - a < MIN_SCENE_S - EPS:
            r.warn(f"{tag}: only {b - a:.1f} s (target 1.5-3 s)")
        if kind == "2d" and len([x for x in re.split(r"[+,;/]", cell(row, "layers")) if x.strip()]) < 2:
            r.warn(f"{tag}: a 2D scene wants 2-3 parallax layers")
        for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*px", " ".join(row), flags=re.I):
            if float(m.group(1).replace(",", ".")) < MIN_TEXT_PX:
                r.err(f"{tag}: text {m.group(0)} is below {MIN_TEXT_PX} px")
        s = cell(row, "sound").lower()
        if "sfx" in s or "эффект" in s:
            sfx += 1
        t = cell(row, "transition").lower().strip(" -")
        if t:
            if t == prev_tr:
                r.warn(f"{tag}: the same transition '{t}' twice in a row")
            if "свет гаснет" in t:
                lights += 1
            prev_tr = t
    scenes.sort(key=lambda x: x[1])
    for (n1, a1, b1), (n2, a2, b2) in zip(scenes, scenes[1:]):
        if a2 - b1 > EPS:
            r.err(f"shotlist.md: gap {a2 - b1:.1f} s between row {n1} and row {n2} (no scene change for {a2 - a1:.1f} s)")
        elif b1 - a2 > EPS:
            r.err(f"shotlist.md: rows {n1} and {n2} overlap by {b1 - a2:.1f} s")
    end = scenes[-1][2] if scenes else None
    if scenes and scenes[0][1] > EPS:
        r.err(f"shotlist.md: the first row starts at {scenes[0][1]:.1f} s; frame 0 needs a picture")
    if len(schemes) < MIN_SCHEMES:
        r.err(f"shotlist.md: {len(schemes)} different scheme(s) ({', '.join(sorted(schemes)) or 'none'}); need at least {MIN_SCHEMES}")
    share = dur3d / total if total else 0.0
    if share > MAX_3D_SHARE + 0.005:
        r.err(f"shotlist.md: 3D takes {share:.0%} of the runtime; at most {MAX_3D_SHARE:.0%}")
    if sfx > MAX_SFX:
        r.warn(f"shotlist.md: {sfx} sound-effect rows; at most {MAX_SFX} per video")
    if lights > MAX_LIGHTS_OUT:
        r.warn(f"shotlist.md: 'свет гаснет' {lights} times; at most {MAX_LIGHTS_OUT}")
    if end and dur:
        if abs(end - dur) > 5:
            r.err(f"shotlist.md: ends at {end:.1f} s, brief says {dur:g} s")
        elif abs(end - dur) > 2:
            r.warn(f"shotlist.md: ends at {end:.1f} s, brief says {dur:g} s")
    r.stats.update({"rows": len(scenes), "schemes": sorted(schemes), "share_3d": round(share, 3),
                    "longest_scene_s": round(max((b - a for _, a, b in scenes), default=0), 2)})
    return end


def _check_words(d: Path, nscript: int, dur: float | None, r: _R) -> None:
    p = d / "words.json"
    if not p.exists():
        r.err("words.json: file is missing (stage 3: faster-whisper on the clean voice)")
        return
    data = _load_json(p, r, "words.json")
    if isinstance(data, dict):
        data = data.get("words")
    if data is None:
        return
    if not isinstance(data, list) or not data:
        r.err("words.json: empty (stage 3 is not done: [{\"w\": \"слово\", \"s\": 0.0, \"e\": 0.3}, ...])")
        return
    last_s, last_e, bad = -1.0, 0.0, 0
    for i, it in enumerate(data, 1):
        if not isinstance(it, dict):
            r.err(f"words.json item {i}: must be an object")
            return
        s = it.get("s", it.get("start"))
        e = it.get("e", it.get("end"))
        if not _num(s) or not _num(e):
            r.err(f"words.json item {i}: 's' and 'e' must be numbers")
            return
        if e < s:
            r.err(f"words.json item {i}: end {e} is before start {s}")
            bad += 1
        elif s < last_s:
            r.err(f"words.json item {i}: start {s} goes back (previous start {last_s}); times must grow")
            bad += 1
        elif s < last_e - EPS:
            r.warn(f"words.json item {i}: overlaps the previous word by {last_e - s:.2f} s")
        last_s, last_e = max(last_s, s), max(last_e, e)
        if bad >= 5:
            r.err("words.json: too many order errors, stopped")
            break
    r.stats.update({"words_json_count": len(data), "voice_end_s": round(last_e, 2)})
    if nscript and abs(len(data) - nscript) > 0.15 * nscript:
        r.warn(f"words.json has {len(data)} words, script.md has {nscript}; re-run recognition or fix the script")
    if dur and last_e > dur + 2:
        r.warn(f"words.json ends at {last_e:.1f} s, brief says {dur:g} s")


def check_episode(directory: str | Path, stage: str = "full") -> dict:
    d = Path(directory)
    if not d.is_dir():
        raise ShortsError(f"anim-check: not a folder: {d}")
    if stage not in ("script", "full"):
        raise ShortsError("anim-check: --stage is script or full")
    r = _R()
    dur = _check_brief(d, r)
    if dur is not None:
        r.stats["duration_s"] = dur
        if not DURATION_RANGE[0] <= dur <= DURATION_RANGE[1]:
            r.err(f"brief.json: duration_s {dur:g} is outside {DURATION_RANGE[0]:g}-{DURATION_RANGE[1]:g}")
    n = _check_script(d, dur, r)
    if stage == "full":
        _check_shotlist(d, dur, r)
        _check_words(d, n, dur, r)
    return {"ok": not r.errors, "dir": str(d), "stage": stage, "errors": r.errors, "warnings": r.warnings, "stats": r.stats}
