"""Offline lint of a toon episode: names the renderer knows, word anchors, pace and the channel rules
(hook <= 3.5 s, 2.2-3.0 words/s, no static shot > 3.5 s, nothing in the caption zone, <= 2 ribbons, <= 3 lights-out,
no camera / transition twice in a row). Errors block rendering; warnings are style advice."""
from __future__ import annotations

import re

from . import catalog
from .story import build, size_of

ICON_KEYS = ("icon", "center_icon", "route_icon")


def _icons(obj, out: list):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ICON_KEYS and isinstance(v, str):
                out.append(v)
            else:
                _icons(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _icons(v, out)
    return out


def check(ep: dict, story: dict | None = None, report: dict | None = None) -> dict:
    N = catalog.load()
    errors, warns, info = [], [], []
    E = lambda i, m: errors.append({"scene": i, "msg": m})
    Wn = lambda i, m: warns.append({"scene": i, "msg": m})
    if story is None or report is None:
        try:
            from .voice import cached_speaker
            story, report = build(ep, cached_speaker(ep))   # cached real timings where voiced, estimates elsewhere
        except Exception as e:                      # noqa: BLE001 - report as a lint error
            return {"ok": False, "errors": [{"scene": None, "msg": str(e)}], "warnings": [], "info": [], "stats": {}}
    for p in report.get("problems", []):
        (errors if p["level"] == "error" else warns).append({"scene": p["scene"], "msg": p["msg"]})
    W, H = size_of(ep)
    portrait = H >= W
    cast = ep.get("cast") or {}
    for cid, c in cast.items():
        if c.get("look") and c["look"] not in N["looks"]:
            E(None, f"cast {cid}: unknown look {c['look']!r}")
    ribbons = lights_out = 0
    prev_cam = prev_tr = None
    same_run, run_shots = 1, set()
    for i, sc in enumerate(story["scenes"]):
        src = ep["scenes"][i]
        st = sc["set"]
        if st.get("id") not in N["sets"]:
            E(i, f"unknown set {st.get('id')!r}; sets: {', '.join(N['sets'])}")
        if st.get("time") not in N["palettes"]:
            E(i, f"unknown time {st.get('time')!r}; use {', '.join(N['palettes'])}")
        if sc.get("camera") not in N["cameras"]:
            E(i, f"unknown camera {sc.get('camera')!r}")
        shot = sc.get("shot")
        if shot is not None and (shot if isinstance(shot, str) else (shot or {}).get("type", "medium")) not in ("wide", "medium", "close"):
            E(i, f"unknown shot {shot!r}: wide | medium | close | {{\"type\": \"close\", \"on\": actor id}}")
        if sc.get("transition") and sc["transition"] not in N["transitions"]:
            E(i, f"unknown transition {sc['transition']!r}")
        for a in sc.get("actors", []):
            if a.get("look") not in N["looks"]:
                E(i, f"actor {a.get('id')}: unknown look {a.get('look')!r}")
            for p in [a.get("pose")] + [x[1] for x in a.get("acts", [])]:
                if p and p not in N["poses"]:
                    E(i, f"actor {a.get('id')}: unknown pose {p!r}")
            for e in [a.get("emotion")] + [x[1] for x in a.get("feel", [])]:
                if e and e not in N["emotions"]:
                    E(i, f"actor {a.get('id')}: unknown emotion {e!r}")
            for h in (a.get("hold"), a.get("hold2")):
                if h and h not in N["items"]:
                    E(i, f"actor {a.get('id')}: unknown item {h!r}")
            if a.get("face") and a["face"] not in N["faces"]:
                E(i, f"actor {a.get('id')}: face must be one of {', '.join(N['faces'])}")
        for p in sc.get("props", []):
            if p.get("id") != "crowd" and p.get("id") not in N["items"]:
                E(i, f"unknown prop {p.get('id')!r}")
        for el in sc.get("hud", []):
            if el.get("type") not in N["hud"]:
                E(i, f"unknown hud type {el.get('type')!r}; hud: {', '.join(N['hud'])}")
            if el.get("type") == "ribbon":
                ribbons += 1
            at = el.get("at")
            y = at[1] if isinstance(at, list) and len(at) == 2 else (el.get("y") if el.get("type") == "ribbon" else None)
            if portrait and y is not None and 0.55 <= float(y) <= 0.76:
                Wn(i, f"hud {el.get('type')} at y={y} sits in the caption zone (0.55-0.76): move it up")
        sch = sc.get("scheme")
        if sch:
            if sch.get("type") not in N["schemes"]:
                E(i, f"unknown scheme {sch.get('type')!r}; schemes: {', '.join(N['schemes'])}")
            if sch.get("bg") and sch["bg"] not in N["themes"]:
                E(i, f"scheme bg must be one of {', '.join(N['themes'])}")
            if sch.get("item") and sch["item"] not in N["items"]:
                E(i, f"closeup item {sch['item']!r} unknown")
        for ic in _icons([sc.get("hud", []), sch or {}], []):
            if ic not in N["icons"]:
                E(i, f"unknown icon {ic!r}; icons: {', '.join(N['icons'])}")
        for f in sc.get("fx", []):
            name = f if isinstance(f, str) else (f or {}).get("type")
            if name not in N["fx"]:
                E(i, f"unknown fx {name!r}")
            if name == "blackout":
                lights_out += 1
        if st.get("lights_out") is not None or st.get("power_off") is not None:
            lights_out += 1
        # ------------------------------------------------ pace + motion
        dur = sc["t1"] - sc["t0"]
        nw = report["timing"][i]["words"]
        ws = [w for w in story.get("words", []) if w.get("sc") == i]
        talk = (ws[-1]["e"] - ws[0]["s"]) if len(ws) >= 2 else dur        # spoken span: TTS pauses at "." are fine
        if nw >= 4:
            wps = nw / max(0.1, talk)
            if wps > 3.4:
                Wn(i, f"{wps:.1f} words/s: too fast for captions (target 2.4-2.9): split the scene or cut words")
            elif wps < 1.4 and talk > 2.5:
                Wn(i, f"{wps:.1f} words/s: slow scene, cut the pause or add a beat")
        if dur - talk > 2.4 and i < len(story["scenes"]) - 1:
            Wn(i, f"{dur - talk:.1f}s without speech: give it an action beat or shorten \"dur\"")
        moving = (sc.get("camera") != "static" or any(a.get("to") or a.get("path") or a.get("acts") for a in sc.get("actors", []))
                  or len(sc.get("hud", [])) >= 2 or sc.get("scheme") or sc.get("fx"))
        long_fmt = ep.get("format") == "long"
        if src.get("endscreen"):
            if i != len(story["scenes"]) - 1:
                Wn(i, "endscreen must be the last scene")
            if not 5 <= dur <= 20:
                Wn(i, f"endscreen {dur:.1f}s: YouTube end screens need 5-20 s (\"dur\": 12)")
        else:
            if dur > 3.5 and not moving:
                Wn(i, f"static shot {dur:.1f}s: add a camera move, an action (acts/to) or a HUD beat")
            if dur > (12 if long_fmt else 7.5):
                Wn(i, f"scene {dur:.1f}s is long: split it (new angle every {'3-6' if long_fmt else '2-4'} s)")
        if src.get("camera") and src["camera"] == prev_cam and src["camera"] != "static":
            Wn(i, f"camera {src['camera']} twice in a row")
        tr = sc.get("transition")
        if tr and tr != "cut" and tr == prev_tr:
            Wn(i, f"transition {tr} twice in a row")
        prev_cam, prev_tr = sc.get("camera"), (tr if tr and tr != "cut" else prev_tr)
        shot = sc.get("shot") or "wide"
        shot = shot if isinstance(shot, str) else shot.get("type", "medium")
        if i and st.get("id") == story["scenes"][i - 1]["set"].get("id") and not sch:
            same_run += 1
            run_shots.add(shot)
            if same_run == (7 if len(run_shots) >= 3 else 5):     # wide/medium/close variety buys two more scenes
                Wn(i, f"{same_run} scenes in one place: cut to a scheme / close-up / another place")
        else:
            same_run, run_shots = 1, {shot}
    s0 = story["scenes"][0]
    if ep.get("format") == "long":
        beats, last_beat = [], 0.0               # long form: a re-hook (chapter / stamp / question / scheme / ribbon) every <= 45 s
        for src, sc in zip(ep["scenes"], story["scenes"]):
            if src.get("chapter") or src.get("scheme") or any(h.get("type") in ("stamp", "question", "ribbon", "title", "chapter") for h in sc.get("hud", [])):
                if sc["t0"] - last_beat > 45:
                    warns.append({"scene": story["scenes"].index(sc), "msg": f"{sc['t0'] - last_beat:.0f}s without a re-hook: add a question / stamp / scheme / chapter every 30-45 s"})
                last_beat = sc["t0"]
        if story["duration"] - last_beat > 45:
            warns.append({"scene": None, "msg": "no re-hook in the last 45 s"})
        if story["duration"] > 120 and not any(src.get("chapter") for src in ep["scenes"]):
            warns.append({"scene": None, "msg": "long video without chapters: add \"chapter\" every 60-120 s (build/chapters.txt goes to the description)"})
        if s0["t1"] - s0["t0"] > 8:
            warns.append({"scene": 0, "msg": "cold open scene > 8 s: open on the strongest moment"})
    elif s0["t1"] - s0["t0"] > 3.6:
        warns.append({"scene": 0, "msg": "hook scene > 3.5 s: the first frame and first line must hook at once"})
    if ep.get("format") != "long" and not (s0.get("hud") or s0.get("scheme") or s0.get("actors")):
        warns.append({"scene": 0, "msg": "first frame is empty: put the hero, a HUD title or a scheme in scene 1"})
    if ribbons > 2:
        warns.append({"scene": None, "msg": f"{ribbons} ribbons: keep 1-2 per episode"})
    if lights_out > 3:
        warns.append({"scene": None, "msg": f"{lights_out} lights-out moments: keep <= 3"})
    total = story["duration"]
    fmt = ep.get("format", "short")
    if fmt != "long":
        if total > 90:
            warns.append({"scene": None, "msg": f"{total:.0f}s: shorts work best at 45-90 s"})
        elif total < 15:
            warns.append({"scene": None, "msg": f"{total:.0f}s: very short"})
    last = ep["scenes"][-1]
    kids = ep.get("audience") == "kids"
    if kids:
        for i, sc in enumerate(ep["scenes"]):
            if re.search(r"коммент|подпиш|лайк|comment|subscribe|like", sc.get("say") or "", re.I):
                warns.append({"scene": i, "msg": "audience kids: no comment / like / subscribe calls (made-for-kids videos have comments off)"})
        info.append({"scene": None, "msg": "audience kids: tick 'made for kids' on upload (COPPA); no ad card, no product placement, no links"})
    elif not ("?" in (last.get("say") or "") or any(h.get("type") == "question" for h in story["scenes"][-1].get("hud", []))):
        info.append({"scene": len(ep["scenes"]) - 1, "msg": "end on a question (comments) or loop back to the first line"})
    full_sch = sum(s["t1"] - s["t0"] for s in story["scenes"] if s.get("scheme") and s["scheme"].get("full", True) is not False)
    music = ep.get("music")
    if not music or music == "none":
        info.append({"scene": None, "msg": "no music: 2.4 default is \"music\": \"auto\" (a fitting track from YouTube, "
                                           "credited in the description); \"none\" only when the user asked for no music"})
    talkers = {sc.get("speaker") for sc in ep["scenes"] if sc.get("speaker") and sc.get("say") and not sc.get("voice")}
    for cid in sorted(t for t in talkers if t in cast and not (cast[t] or {}).get("voice")):
        info.append({"scene": None, "msg": f"cast {cid} speaks with the narrator voice: give it its own "
                                           f"\"voice\" (VoiceEngine attributes, e.g. \"ж, 8, радостно\"), see reference/voice.md"})
    stats = {"duration": round(total, 2), "scenes": len(story["scenes"]), "words": len(story["words"]),
             "wps": round(len(story["words"]) / max(1, total), 2), "scheme_share": round(full_sch / max(1, total), 2),
             "estimated_timing": any(s.get("estimated") for s in report.get("speech", [])) or not report.get("speech")}
    return {"ok": not errors, "errors": errors, "warnings": warns, "info": info, "stats": stats}
