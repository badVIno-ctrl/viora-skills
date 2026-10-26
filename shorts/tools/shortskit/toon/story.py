"""Toon episode (what the agent writes) -> story (what the renderer draws).

Scene time comes from the voice: scene = lead + speech + pad. `*word*` in `say` marks the caption accent word.
Anything ending in `_on` ("lights_out_on": "пропал", hud "on": "ловушка") becomes the time of that word in the scene.
Missing camera / transition / clock / actor positions are filled with the channel rules (reference/animation.md):
the camera never repeats twice in a row, transitions vary, the clock carries over and flips when it changes."""
from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Callable

from ..util import ShortsError
from . import catalog

SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
SCENE_KEYS = {"say", "dur", "pad", "set", "time", "camera", "cam_amount", "cam0", "actors", "props", "hud", "clock", "scheme", "fx",
              "transition", "tr_dur", "accent", "speaker", "shake", "focus_xy", "dark", "id", "note", "sfx", "chapter", "beat",
              "shot", "endscreen", "voice", "tone"}
SHOTS = ("wide", "medium", "close")
ANCHOR_KEYS = {"split_on": "split_t", "break_on": "break_t", "path_on": "path_t", "route_on": "route_t", "water_on": "water_t", "vent_on": "vent_t",
               "t_on": "t", "reveal_on": "reveal", "lights_out_on": "lights_out"}
STRONG = {"scared", "sad", "surprised", "shout", "angry", "zombie", "tired"}
CAM_CYCLE = ["push", "drift", "pan_right", "push", "pull", "pan_left", "drift", "tilt_up"]
TR_CYCLE = ["whip", "slide", "zoom", "iris"]          # "flash" only on purpose (shock beats)
EXIT_CYCLE = ["slide", "cut", "whip", "cut"]          # back from a scheme to the story
STYLE = {"grain": 0.04, "vignette": 0.32, "outline": "thin", "captions": "caps"}
LEAD, LEAD0, PAD, PAD_JOIN, PAD_LAST, MIN_SCENE, SILENT_SCENE = 0.15, 0.06, 0.26, 0.1, 0.9, 1.2, 2.2
CHAPTER_LEAD = 1.3
END_PUNCT = tuple(".!?…»\"")


def spoken(sp: dict) -> float:
    """Seconds until the last word ends. TTS files carry ~0.8 s of trailing silence: never pace scenes by it."""
    ws = sp.get("words") or []
    if ws and not sp.get("estimated"):
        return min(float(sp["duration"]), float(ws[-1]["e"]) + 0.08)
    return float(sp["duration"])
WPS_SILENT = 2.5          # estimate for previews without a voice
SpeakFn = Callable[..., dict]   # (text, voice=None) -> {"wav": Path|None, "duration": float, "words": [{"w","s","e"}]}


def scene_voice(ep: dict, sc: dict) -> str | None:
    """2.4: the line's own voice when it is not the narrator: scene "voice", else cast[speaker]["voice"];
    scene "tone" adds VoiceEngine attributes for this line only ("шёпотом", "сердито", "эхо").
    None = the episode voice (old speak functions with one argument keep working)."""
    v = sc.get("voice")
    if not v and sc.get("speaker"):
        v = ((ep.get("cast") or {}).get(sc["speaker"]) or {}).get("voice")
    tone = str(sc.get("tone") or "").strip()
    if tone:
        from ..voice import attrs_for
        base = attrs_for(v or ep.get("voice"), ep.get("lang", "ru"))
        v = f"{base}, {tone}" if base else tone
    return str(v) if v else None


def size_of(ep: dict) -> tuple[int, int]:
    if ep.get("W") and ep.get("H"):
        return int(ep["W"]), int(ep["H"])
    asp = str(ep.get("aspect") or ("16:9" if ep.get("format") == "long" else "9:16"))
    if asp not in SIZES:
        raise ShortsError(f"aspect {asp!r}: use one of {', '.join(SIZES)}")
    return SIZES[asp]


def norm(w: str) -> str:
    return re.sub(r"[^\w]", "", str(w).lower().replace("ё", "е"))


def parse_say(text: str) -> tuple[str, list[bool]]:
    """'Ты на *двадцатом* этаже' -> ('Ты на двадцатом этаже', [False, False, True, False]) (one flag per spoken token)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    clean, acc, inside = [], [], False
    for ch in text:
        if ch == "*":
            inside = not inside
            continue
        clean.append(ch); acc.append(inside)
    s = "".join(clean)
    flags = []
    for m in re.finditer(r"\S+", s):
        if norm(m.group(0)):
            flags.append(any(acc[m.start():m.end()]))
    return s, flags


def estimate(text: str, wps: float = WPS_SILENT) -> dict:
    from ..engine.tts import estimate_words
    n = max(1, len([t for t in text.split() if norm(t)]))
    d = n / wps + 0.25
    return {"wav": None, "duration": d, "words": estimate_words(text, d), "estimated": True}


def find_word(words: list[dict], query: str, after: float = -1.0) -> dict | None:
    """First word (or start of a phrase) matching query by prefix; words are scene-relative."""
    q = [norm(x) for x in str(query).split() if norm(x)]
    if not q:
        return None
    ws = [norm(w["w"]) for w in words]
    for i in range(len(ws)):
        if words[i]["s"] < after:
            continue
        if all(i + j < len(ws) and ws[i + j].startswith(q[j][:max(3, len(q[j]) - 2)]) for j in range(len(q))):
            return words[i]
    return None


class Resolver:
    """Turns *_on word anchors of one scene into scene-relative seconds."""
    def __init__(self, words: list[dict], lead: float, idx: int, problems: list):
        self.words, self.lead, self.idx, self.problems = words, lead, idx, problems

    def t(self, query) -> float | None:
        if isinstance(query, (int, float)):
            return float(query)
        w = find_word(self.words, query)
        if not w:
            self.problems.append({"level": "error", "scene": self.idx, "msg": f"word {query!r} is not in this scene's say"})
            return None
        return round(self.lead + w["s"], 3)

    def walk(self, obj):
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                v = obj[k]
                if k == "on" and isinstance(v, (str, int, float)) and not isinstance(v, bool):   # closeup "on": true is a flag
                    t = self.t(v); obj.pop(k)
                    if t is not None:
                        obj["t"] = t
                elif k.endswith("_on") and isinstance(v, (str, int, float)) and not isinstance(v, bool):
                    t = self.t(v); obj.pop(k)
                    if t is not None:
                        key = ANCHOR_KEYS.get(k, k[:-3])
                        if isinstance(obj.get(key), (list, dict)):       # "path_on" must not overwrite the path itself
                            key = k[:-3] + "_t"
                        obj[key] = t
                else:
                    self.walk(v)
        elif isinstance(obj, list):
            for v in obj:
                self.walk(v)
        return obj


def _shorthand_actor(s: str, names: dict) -> dict:
    parts = [p for p in re.split(r"[:\s]+", s.strip()) if p]
    a = {"id": parts[0]}
    for p in parts[1:]:
        if p in names["poses"]:
            a["pose"] = p
        elif p in names["emotions"]:
            a["emotion"] = p
        elif p in names["items"]:
            a["hold"] = p
        elif p in catalog.FACES:
            a["face"] = p
    return a


def _timeline(entries, key: str, res: Resolver) -> list:
    """acts / feel: [[t, name]] or [{"on": word | "t": s, "pose": name}] -> [[t, name]] sorted."""
    out = []
    for e in entries or []:
        if isinstance(e, (list, tuple)) and len(e) >= 2:
            t = res.t(e[0])
            if t is not None:
                out.append([t, e[1]])
        elif isinstance(e, dict):
            name = e.get(key) or e.get("pose") or e.get("emotion")
            t = res.t(e["on"]) if "on" in e else (float(e.get("t", 0)) if e.get("t") is not None else None)
            if t is not None and name:
                out.append([t, name])
    return sorted(out, key=lambda x: x[0])


def _actors(sc: dict, cast: dict, names: dict, res: Resolver, portrait: bool) -> list[dict]:
    raw = sc.get("actors") or []
    acts = [_shorthand_actor(a, names) if isinstance(a, str) else copy.deepcopy(a) for a in raw]
    slots = {1: [0.5], 2: [0.34, 0.66] if portrait else [0.38, 0.62], 3: [0.22, 0.5, 0.78] if portrait else [0.3, 0.5, 0.7]}
    free = [a for a in acts if not a.get("at")]
    xs = slots.get(len(acts)) or [0.12 + 0.76 * i / max(1, len(acts) - 1) for i in range(len(acts))]
    for i, a in enumerate(acts):
        if isinstance(a.get("at"), (int, float)):
            a["at"] = [float(a["at"]), None]
        if not a.get("at"):
            a["at"] = [xs[i] if i < len(xs) else 0.5, None]
        c = cast.get(a.get("id"), {})
        if "look" not in a:
            a["look"] = c.get("look") or (a.get("id") if a.get("id") in names["looks"] else "hero")
        if "acts" in a:
            a["acts"] = _timeline(a["acts"], "pose", res)
        if "feel" in a:
            a["feel"] = _timeline(a["feel"], "emotion", res)
    if len(acts) == 2 and not any("face" in a for a in acts) and len(free) == 2:
        acts[0]["face"], acts[1]["face"] = "right", "left"
    return acts


def _props(sc: dict, portrait: bool) -> list[dict]:
    out = []
    raw = sc.get("props") or []
    for i, p in enumerate(raw):
        p = {"id": p} if isinstance(p, str) else copy.deepcopy(p)
        if isinstance(p.get("at"), (int, float)):
            p["at"] = [float(p["at"]), None]
        if not p.get("at"):
            p["at"] = [[0.78, 0.22, 0.88, 0.12][i % 4], None]
        out.append(p)
    return out


def _is_full_scheme(sc: dict) -> bool:
    s = sc.get("scheme")
    return bool(s) and s.get("full", True) is not False


def _day(clock) -> str | None:
    txt = clock if isinstance(clock, str) else (clock or {}).get("text", "") if isinstance(clock, dict) else ""
    m = re.search(r"(ДЕНЬ|DAY|НЕДЕЛЯ|WEEK|МЕСЯЦ|MONTH)\s*(\d+)", str(txt).upper())
    return m.group(0) if m else None


FACE_BAND = (0.24, 0.52)
BAND_SAFE_Y = 0.2


def _clear_face_band(hud: list, i: int, problems: list) -> None:
    """Medium / close shots put faces at 0.33-0.55 H: lift stamps, plates, ribbons, questions out of that band."""
    for el in hud:
        typ = el.get("type")
        if typ in ("ribbon",) and FACE_BAND[0] < float(el.get("y", BAND_SAFE_Y)) < FACE_BAND[1]:
            el["y"] = BAND_SAFE_Y
            problems.append({"level": "info", "scene": i, "msg": f"hud {typ} moved to y {BAND_SAFE_Y} (face band of the shot)"})
        elif typ in ("stamp", "plate", "question", "title", "tape", "label", "timer", "counter") and isinstance(el.get("at"), list) \
                and len(el["at"]) == 2 and FACE_BAND[0] < float(el["at"][1]) < FACE_BAND[1] \
                and not (typ == "timer" and float(el["at"][1]) <= BAND_SAFE_Y + 0.11):     # a timer just under the plate row is fine
            el["at"] = [el["at"][0], BAND_SAFE_Y if typ != "timer" else BAND_SAFE_Y + 0.11]
            problems.append({"level": "info", "scene": i, "msg": f"hud {typ} moved to y {el['at'][1]} (face band of the shot)"})


def auto_shot(out: dict, prev: str | None) -> str | None:
    """Pick wide / medium / close like an editor: crowds and movement wide, two people medium, one person medium,
    strong emotion close; inside one place the shot size always changes on a cut (no jump cuts)."""
    acts = out.get("actors") or []
    crowd = next((p for p in out.get("props") or [] if p.get("id") == "crowd" and p.get("area")), None)
    if not acts and crowd:          # frame the crowd above the caption band instead of a tiny wide shot
        a = crowd["area"]
        return {"type": "medium", "at": [round((a[0] + a[2]) / 2, 3), round(a[1] - 0.08, 3)], "z": 1.4}
    if not acts:
        things = [p for p in out.get("props") or [] if p.get("id") != "crowd" and p.get("at") is not None]
        if len(things) == 1:        # one object in an empty room: go to it
            at = things[0]["at"]
            x = at[0] if isinstance(at, (list, tuple)) else at
            y = at[1] if isinstance(at, (list, tuple)) and len(at) > 1 else None
            return {"type": "medium", "at": [x, y], "z": 1.6}
        return None
    if (len(acts) >= 3 or any(a.get("path") or a.get("to") for a in acts)
            or any(p.get("id") == "crowd" for p in out.get("props") or [])):
        want = "wide"
    elif len(acts) == 2:
        want = "medium"
    else:
        a = acts[0]
        strong = (a.get("emotion") in STRONG or out.get("accent") == "red" or out.get("camera") == "crash"
                  or any((f[1] if isinstance(f, (list, tuple)) else f.get("emotion")) in STRONG for f in a.get("feel") or []))
        want = "close" if strong else "medium"
    if prev and want == prev:
        want = {"medium": "close" if len(acts) == 1 else "wide", "close": "medium", "wide": "medium"}[want]
    return want


def build(ep: dict, speak: SpeakFn | None = None, measure: Callable[[str, int], float] | None = None) -> tuple[dict, dict]:
    """Episode -> (story, report). speak=None -> estimated timings (silent preview)."""
    names = catalog.load()
    if not isinstance(ep.get("scenes"), list) or not ep["scenes"]:
        raise ShortsError("episode has no scenes")
    W, H = size_of(ep)
    portrait = H >= W
    fps = int(ep.get("fps", 30))
    style = dict(STYLE); style.update(ep.get("style") or {})
    cast = copy.deepcopy(ep.get("cast") or {})
    problems: list[dict] = []
    t = 0.0
    scenes, words_all = [], []
    prev_set, prev_cam, last_tr, last_clock, prev_shot, exit_i = None, None, None, None, "wide", 0
    cam_i = 0
    n = len(ep["scenes"])
    speech_report = []
    for i, src in enumerate(ep["scenes"]):
        sc = copy.deepcopy(src)
        unknown = [k for k in sc if k not in SCENE_KEYS]
        for k in unknown:
            problems.append({"level": "warn", "scene": i, "msg": f"unknown scene key {k!r} (set options go inside \"set\")"})
        # ------------------------------------------------ set (inherits the previous place when omitted)
        st = sc.get("set")
        if st is None and prev_set is not None and not _is_full_scheme(sc):
            st = copy.deepcopy(prev_set)
            for k in ("lights_out", "lights_out_on", "power_off", "wave"):      # one-shot events do not repeat
                st.pop(k, None)
        st = {"id": st} if isinstance(st, str) else copy.deepcopy(st or {"id": "plain"})
        if sc.get("time"):
            st["time"] = sc["time"]
        if "time" not in st:
            st["time"] = (prev_set or {}).get("time") if prev_set and prev_set.get("id") == st.get("id") else ep.get("time", "day")
        # ------------------------------------------------ voice + duration
        say = sc.get("say") or ""
        clean, flags = parse_say(say)
        sp = None
        if clean:
            vo = scene_voice(ep, sc)
            sp = (speak(clean, voice=vo) if vo else speak(clean)) if speak else estimate(clean)
        lead = LEAD0 if i == 0 else LEAD
        card = bool(sc.get("chapter")) and ep.get("chapter_card", "full") == "full"
        if card:
            lead += CHAPTER_LEAD                                   # full-frame chapter card first, then the line
        # a line that ends mid-sentence ("Толпа бежит вниз,") flows into the next scene with a short gap
        pad = float(sc.get("pad", PAD_LAST if i == n - 1 else (PAD if clean.rstrip().endswith(END_PUNCT) or not clean else PAD_JOIN)))
        if sp:
            talk = spoken(sp)
            need = lead + talk + pad
            dur = max(float(sc["dur"]), lead + talk + 0.05) if sc.get("dur") else need
            if sc.get("dur") and float(sc["dur"]) < lead + talk:
                problems.append({"level": "warn", "scene": i, "msg": f"dur {sc['dur']} < speech {talk:.2f}s: extended"})
        else:
            dur = float(sc.get("dur", SILENT_SCENE))
        dur = round(max(MIN_SCENE, dur), 3)
        words = []
        if sp:
            ws = sp["words"]
            for j, w in enumerate(ws):
                words.append({"w": w["w"], "s": float(w["s"]), "e": float(w["e"]), "a": bool(flags[j]) if j < len(flags) else False})
            if len(flags) != len(ws) and any(flags):           # fall back to text matching for accents
                acc = {norm(m) for m in re.findall(r"\*([^*]+)\*", say) for m in m.split()}
                for w in words:
                    w["a"] = norm(w["w"]) in acc
        res = Resolver(words, lead, i, problems)
        # ------------------------------------------------ scene body
        out = {"id": sc.get("id") or f"s{i + 1}", "t0": round(t, 3), "t1": round(t + dur, 3), "set": res.walk(st)}
        if sc.get("scheme"):
            out["scheme"] = res.walk(copy.deepcopy(sc["scheme"]))
        out["actors"] = _actors(sc, cast, names, res, portrait)
        out["props"] = res.walk(_props(sc, portrait))
        hud = res.walk(copy.deepcopy(sc.get("hud") or []))
        if sc.get("chapter"):
            ch = sc["chapter"] if isinstance(sc["chapter"], dict) else {"text": str(sc["chapter"])}
            base = {"type": "chapter", "t": 0.05, "out": lead - 0.2, "full": True} if card else {"type": "chapter", "t": 0.1, "out": min(dur - 0.3, 2.4)}
            hud.insert(0, dict(base, **ch))
        out["hud"] = hud
        out["fx"] = res.walk(copy.deepcopy(sc.get("fx") or []))
        for k in ("cam_amount", "cam0", "shake", "focus_xy", "dark", "speaker", "tr_dur", "note", "beat"):
            if k in sc:
                out[k] = copy.deepcopy(sc[k])
        if sc.get("sfx"):
            out["sfx"] = res.walk(copy.deepcopy(sc["sfx"]))
        # ------------------------------------------------ clock carry-over + flip
        ck = sc.get("clock", "__carry__")
        if sc.get("endscreen") and ck == "__carry__":
            ck = "__none__"
        if ck is False or ck == "" or ck is None:
            last_clock = None
        elif ck == "__none__":
            pass
        elif ck == "__carry__":                 # full-frame schemes have their own title row: no clock unless asked
            if last_clock is not None and ep.get("clock_carry", True) and not (_is_full_scheme(sc) and not ep.get("clock_on_schemes")):
                out["clock"] = copy.deepcopy(last_clock)
        else:
            text = ck if isinstance(ck, str) else ck.get("text", "")
            prev_text = (last_clock if isinstance(last_clock, str) else (last_clock or {}).get("text")) if last_clock else None
            out["clock"] = copy.deepcopy(ck)
            if prev_text and prev_text != text:
                out["clock_prev"], out["clock_new"] = prev_text, True
            elif not prev_text:
                out["clock_new"] = True
            last_clock = copy.deepcopy(ck)
        # ------------------------------------------------ camera (never the same twice in a row)
        cam = sc.get("camera")
        if not cam:
            if _is_full_scheme(sc):
                cam = "push"; out.setdefault("cam_amount", 0.5)
            else:
                nxt = (ep["scenes"][i + 1].get("camera") if i + 1 < n else None)
                for _ in range(len(CAM_CYCLE)):
                    cam = CAM_CYCLE[cam_i % len(CAM_CYCLE)]; cam_i += 1
                    if cam != prev_cam and cam != nxt:
                        break
        out["camera"] = cam
        # ------------------------------------------------ shot size: never cut between two equal shots of one place
        same_place = bool(scenes) and not _is_full_scheme(sc) and "scheme" not in scenes[-1] and scenes[-1]["set"].get("id") == st.get("id")
        shot = sc.get("shot")
        if shot is None and not _is_full_scheme(sc):
            shot = auto_shot(out, prev_shot if same_place else None)
        if shot and shot != "wide":
            out["shot"] = shot
            if portrait:
                _clear_face_band(out["hud"], i, problems)
        elif shot == "wide" and out.get("actors") and portrait:
            out["shot"] = "wide"            # runtime lifts the ground line to 0.74 H: faces stay above the captions
        prev_shot = (shot if isinstance(shot, str) else (shot or {}).get("type", "medium")) if shot else "wide"
        # ------------------------------------------------ transition (varied, cut inside one place)
        tr = sc.get("transition")
        if i == 0:
            tr = None
        elif not tr:
            ps = scenes[-1]
            same_place = (not _is_full_scheme(sc) and "scheme" not in ps and ps["set"].get("id") == st.get("id"))
            if _day(ps.get("clock")) and _day(out.get("clock")) and _day(ps.get("clock")) != _day(out.get("clock")):
                tr = "fade" if last_tr != "fade" else "iris"   # time passes: fade even inside one place
            elif same_place:
                tr = "cut"
            elif _is_full_scheme(sc) and not _is_full_scheme(ps):
                tr = "zoom" if last_tr != "zoom" else "iris"
            elif _is_full_scheme(ps) and not _is_full_scheme(sc):
                tr = EXIT_CYCLE[exit_i % len(EXIT_CYCLE)]; exit_i += 1
                if tr == last_tr:
                    tr = "cut"
            elif _is_full_scheme(ps) and _is_full_scheme(sc):
                tr = "slide" if last_tr != "slide" else "cut"
            else:
                cands = [x for x in TR_CYCLE if x != last_tr]
                tr = cands[i % len(cands)]
        if tr:
            out["transition"] = tr
            if tr != "cut":
                last_tr = tr
        # ------------------------------------------------ captions accent colour + words on the global timeline
        out["accent"] = sc.get("accent", "yellow")
        for w in words:
            words_all.append({"w": w["w"], "s": round(t + lead + w["s"], 3), "e": round(t + lead + w["e"], 3), "a": w["a"], "sc": i})
        if sp:
            speech_report.append({"scene": i, "t": round(t + lead, 3), "wav": str(sp["wav"]) if sp.get("wav") else None,
                                  "duration": round(sp["duration"], 3), "estimated": bool(sp.get("estimated"))})
        scenes.append(out)
        if not _is_full_scheme(sc) or sc.get("set") is not None:   # after a full-screen scheme the story returns to the last place
            prev_set = st
        prev_cam = cam
        t += dur
    total = round(t, 3)
    story = {"W": W, "H": H, "fps": fps, "duration": total, "title": ep.get("title", ""), "style": style, "cast": cast,
             "words": words_all, "scenes": scenes}
    if ep.get("brand") or style.get("brand"):
        story["brand"] = ep.get("brand") or style.get("brand")
    story["captions"] = captions(words_all, scenes, W, H, style, measure) if style.get("captions") != "off" else []
    report = {"duration": total, "scenes": len(scenes), "speech": speech_report, "problems": problems,
              "timing": [{"scene": i, "t0": s["t0"], "t1": s["t1"], "dur": round(s["t1"] - s["t0"], 2),
                          "words": sum(1 for w in words_all if w["sc"] == i), "set": s["set"].get("id"),
                          "scheme": (s.get("scheme") or {}).get("type"), "camera": s["camera"], "transition": s.get("transition")}
                         for i, s in enumerate(scenes)]}
    return story, report


# ---------------------------------------------------------------- captions: 2 lines x 2-4 words, measured with the real font
def _font_measure(W: int, H: int, style: dict) -> Callable[[str, int], float]:
    from PIL import ImageFont
    from .render import fonts_dir
    s = min(W, H) / 1080
    size = int(round((style.get("caption_size") or (84 if H >= W else 72)) * s))
    try:
        font = ImageFont.truetype(str(fonts_dir() / "Montserrat-ExtraBold.ttf"), size)
    except OSError:
        font = None

    def m(text: str, _=0) -> float:
        if font is None:
            return len(text) * size * 0.62
        return float(font.getlength(text))
    return m


def _disp(w: str, caps: bool) -> str:
    w = w.strip().strip("«»\"“”„'").rstrip(",;:—-")
    if w.endswith(".") and not w.endswith("..."):
        w = w[:-1]
    return w.upper() if caps else w


WEAK = {"в", "во", "на", "с", "со", "и", "а", "но", "за", "по", "к", "ко", "у", "о", "об", "от", "до", "из", "без", "для", "что", "как",
        "не", "ни", "же", "ли", "под", "над", "при", "про", "the", "a", "an", "to", "of", "in", "on", "and", "or", "for", "at", "by"}


def _weak(word: str) -> bool:
    return norm(word) in WEAK and not re.search(r"[.!?,:;…]$", word.strip("»\"”"))


def captions(words: list[dict], scenes: list[dict], W: int, H: int, style: dict,
             measure: Callable[[str, int], float] | None = None) -> list[dict]:
    caps = style.get("captions", "caps") != "sentence"
    m = measure or _font_measure(W, H, style)
    portrait = H >= W
    max_w = W * (0.78 if portrait else 0.66)          # right rail of Shorts/TikTok icons starts at ~0.87 W
    # caps = punchy 1-line chunks of <= 3 words (the survival-channel look); sentence = calmer 2 lines (kids, explainers)
    max_words = int(style.get("caption_words") or ((3 if caps else 4) if portrait else (5 if caps else 7)))
    max_lines = int(style.get("caption_lines") or (1 if caps else 2))
    chunks: list[list[list[dict]]] = []
    cur: list[list[dict]] = [[]]

    def flush():
        nonlocal cur
        if cur and cur[0]:
            chunks.append([ln for ln in cur if ln])
        cur = [[]]
    for i, w in enumerate(words):
        prev = words[i - 1] if i else None
        if prev and (prev["sc"] != w["sc"] or w["s"] - prev["e"] > 0.45):
            flush()
        line = cur[-1]
        cand = " ".join(_disp(x["w"], caps) for x in line + [w])
        if line and (len(line) >= max_words or m(cand, 0) > max_w):
            carry = []
            while len(line) >= 2 and _weak(line[-1]["w"]):      # never end a chunk on "на", "и", "а не"
                carry.insert(0, line.pop())
            if len(cur) >= max_lines:
                flush()
            else:
                cur.append([])
            cur[-1].extend(carry)
        cur[-1].append(w)
        n_in = sum(len(ln) for ln in cur)
        end_sent = bool(re.search(r"[.!?…]$", w["w"].strip("»\"”")))
        comma = w["w"].rstrip("»\"”").endswith((",", ":", "—", ";"))
        if end_sent or (comma and n_in >= (2 if max_lines == 1 else 3)):
            flush()
    flush()
    out = []
    for ci, ch in enumerate(chunks):
        first, last = ch[0][0], ch[-1][-1]
        t0 = first["s"] - 0.08
        if out:
            t0 = max(t0, out[-1]["t1"])
        nxt = chunks[ci + 1][0][0]["s"] - 0.08 if ci + 1 < len(chunks) else None
        t1 = last["e"] + 0.6
        if nxt is not None:
            t1 = min(t1, nxt)
        sc = scenes[first["sc"]]
        t1 = max(t1, last["e"] + 0.05)
        widest = max(m(" ".join(_disp(x["w"], caps) for x in ln), 0) for ln in ch)
        fit = round(max(0.55, max_w / widest), 3) if widest > max_w else None      # one long word ("двенадцать-шестнадцать")
        out.append({"t0": round(t0, 3), "t1": round(t1, 3), "color": sc.get("accent", "yellow"), **({"fit": fit} if fit else {}),
                    "lines": [[{"w": _disp(x["w"], False), "s": x["s"], "e": x["e"], **({"a": 1} if x.get("a") else {})} for x in ln] for ln in ch]})
    return out
