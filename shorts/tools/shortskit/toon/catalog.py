"""Names the runtime understands (sets, looks, poses, emotions, items, icons, HUD, schemes, fx, palettes).

manifest.json is dumped from the live JS runtime (`shorts.py toon-catalog --refresh`) so the Python checker never
drifts from the renderer; tests compare it with a fresh dump when Chromium is available."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
CAMERAS = ["drift", "static", "push", "pull", "pan_left", "pan_right", "tilt_up", "tilt_down", "crash"]
TRANSITIONS = ["cut", "fade", "flash", "iris", "slide", "whip", "zoom"]
FACES = ["left", "right", "front", "back"]
NAMES_JS = ("({sets: TOON.SET_NAMES, looks: Object.keys(TOON.LOOKS), poses: TOON.POSE_NAMES, emotions: TOON.EMOTIONS, items: TOON.ITEM_NAMES,"
            " icons: TOON.ICON_NAMES, hud: TOON.HUD_NAMES, schemes: TOON.SCHEME_NAMES, fx: TOON.FX_NAMES, palettes: Object.keys(TOON.PAL),"
            " themes: Object.keys(TOON.SCHEME_THEMES)})")


@lru_cache(maxsize=1)
def load() -> dict:
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    d.update(cameras=CAMERAS, transitions=TRANSITIONS, faces=FACES)
    return d


def refresh(work: Path) -> dict:
    """Dump names from the runtime in Chromium and rewrite manifest.json."""
    from . import render
    names = render.evaluate({"W": 320, "H": 568, "fps": 30, "duration": 1, "style": {}, "cast": {}, "words": [],
                             "scenes": [{"t0": 0, "t1": 1, "set": {"id": "plain"}}]}, NAMES_JS, work)
    names = {k: list(v) for k, v in names.items()}
    MANIFEST.write_text(json.dumps(names, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    load.cache_clear()
    return names


def text() -> str:
    """Compact catalogue for the agent (one line per group)."""
    d = load()
    order = ["sets", "palettes", "looks", "poses", "emotions", "items", "hud", "schemes", "themes", "icons", "fx", "cameras", "transitions", "faces"]
    return "\n".join(f"{k} ({len(d[k])}): " + ", ".join(d[k]) for k in order if k in d)


def examples(name: str | None = None, templates_dir: Path | None = None) -> dict:
    """Real snippets from templates/toon/*.json: how a scheme / hud / fx / set option / actor key / scene key is written.
    `toon-catalog --examples gauge` -> {"scheme:gauge": {"from": "explainer", "json": {...}}}."""
    tdir = templates_dir or HERE.parents[2] / "templates" / "toon"
    found: dict[str, dict] = {}

    def add(key: str, val, src: str) -> None:
        if key not in found:
            found[key] = {"from": src, "json": val}
    for f in sorted(tdir.glob("*.json")):
        ep = json.loads(f.read_text(encoding="utf-8"))
        for k, v in ep.items():
            if k != "scenes":
                add(f"episode:{k}", {k: v}, f.stem)
        for sc in ep.get("scenes") or []:
            for k, v in sc.items():
                add(f"scene:{k}", {k: v}, f.stem)
            if isinstance(sc.get("scheme"), dict):
                add(f"scheme:{sc['scheme'].get('type')}", sc["scheme"], f.stem)
            for h in sc.get("hud") or []:
                add(f"hud:{h.get('type')}", h, f.stem)
            fx = sc.get("fx")
            for x in (fx if isinstance(fx, list) else [fx] if fx else []):
                add(f"fx:{x if isinstance(x, str) else x.get('type')}", x, f.stem)
            if isinstance(sc.get("set"), dict):
                for k in sc["set"]:
                    add(f"set:{k}", sc["set"], f.stem)
            for a in sc.get("actors") or []:
                for k in (a if isinstance(a, dict) else {}):
                    add(f"actor:{k}", a, f.stem)
            for p in sc.get("props") or []:
                for k in (p if isinstance(p, dict) else {}):
                    add(f"prop:{k}", p, f.stem)
    if name:
        n = name.lower()
        return {k: v for k, v in found.items() if k.split(":", 1)[1].lower() == n or k.lower() == n}
    return found
