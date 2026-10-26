"""Background motion library (research 17 sections 6-7, research 14 bonus 9.3).

Sludge format: "the ears get the meaning, the eyes get the motion". The banner (layout.top.source) or a split
window (layout.split[].b) plays gameplay / satisfying footage without sound while the voice carries the story.
  bg:auto       pick by the topic words (metadata.topic, name, on-screen text) and the mood
  bg:<id>       an item of assets/footage/library.json (gta_ramp, minecraft_parkour, ...)
Files live in SHORTS_CACHE/bg/<id>.mp4 (muted, 30 fps, <= 1080p) with a sidecar <id>.json (credit, motion).
`shorts.py bg fetch <id>` downloads the section once with yt-dlp; when YouTube blocks the server IP ("sign in
to confirm you're not a bot") the same call records the section in the shared browser (adapters/ytbrowser.py,
real time: 75 s of gta_ramp took 222 s). No browser either: get the file another way and register it with
`shorts.py bg add <id> FILE --credit "..."` (also the way to use your own gameplay, the best option of research 17).
Rules kept in code: the piece starts in the middle of the source (no intro, no menus), a piece shorter than
the video is reported (the viewer notices a loop), the credit goes to the manifest and the description.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from .config import cache_dir, skill_root
from .util import ShortsError, log, read_json, run, write_json

LIB_PATH = Path("assets") / "footage" / "library.json"


def library() -> dict:
    return read_json(skill_root() / LIB_PATH)


def items() -> list[dict]:
    return list(library().get("items", []))


def item(key: str) -> dict | None:
    """Library item, or a background added with `bg add` (only in the cache, described by its sidecar)."""
    it = next((it for it in items() if it["id"] == key), None)
    if it is None:
        side = cache_path(key).with_suffix(".json")
        if side.exists():
            meta = read_json(side)
            it = {"id": key, "kind": meta.get("kind", "own"), "credit": meta.get("credit", ""), "url": meta.get("url"),
                  "mood": meta.get("mood") or [], "topics": meta.get("topics") or [], "verified": True, "own": True}
    return it


def cache_path(key: str) -> Path:
    return cache_dir("bg") / f"{key}.mp4"


def choose(topic: str, mood: str | None = None, cached_only: bool = False) -> dict | None:
    """Best item for the topic: topic stems (+2 each), mood (+1), already cached (+1), verified (+1.5)."""
    t = (topic or "").lower()
    best, best_s = None, -1e9
    for i, it in enumerate(items()):
        if cached_only and not cache_path(it["id"]).exists():
            continue
        s = 2.0 * sum(1 for stem in it.get("topics", []) if stem.lower() in t)
        if mood and mood in it.get("mood", []):
            s += 1.0
        if cache_path(it["id"]).exists():
            s += 1.0
        if it.get("verified"):
            s += 1.5
        s -= 0.01 * i
        if s > best_s:
            best, best_s = it, s
    if best is None and not cached_only:
        raise ShortsError("background library is empty: assets/footage/library.json")
    return best


def fetch(key: str, force: bool = False) -> Path:
    it = item(key)
    if it is None:
        raise ShortsError(f"unknown background '{key}': see `shorts.py bg list`")
    out = cache_path(key)
    if out.exists() and not force:
        return out
    from .adapters.media import download_section
    from .engine.clips import video_info

    if not it.get("url"):
        raise ShortsError(f"background '{key}' has no URL: add the file with `shorts.py bg add {key} FILE`")
    s, e = (it.get("section") or [0, 75])[:2]
    raw = download_section(it["url"], float(s), float(e))
    normalize(raw, out)
    write_sidecar(key, out)
    log.info("background %s cached: %s", key, out)
    return out


def normalize(src: Path, out: Path) -> Path:
    """Muted, 30 fps, <= 1080p H.264: what the compositor reads fast and loops without a jump in rate."""
    tmp = out.with_suffix(".tmp.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-an", "-vf", "fps=30,scale=-2:'min(1080,ih)':flags=lanczos",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)],
        timeout=1800)
    tmp.replace(out)
    return out


def add(key: str, src: Path | str, credit: str = "", kind: str = "own", topics: list[str] | None = None,
        mood: list[str] | None = None) -> dict:
    """Register a local file (own gameplay, a piece recorded in a browser) as bg:<key>."""
    src = Path(src)
    if not src.exists():
        raise ShortsError(f"file not found: {src}")
    if not key.replace("_", "").replace("-", "").isalnum():
        raise ShortsError("background id: letters, digits, '_' or '-'")
    out = normalize(src, cache_path(key))
    meta = write_sidecar(key, out)
    meta.update({"credit": credit or meta.get("credit", ""), "kind": (item(key) or {}).get("kind", kind),
                 "topics": topics or [], "mood": mood or [], "source_file": str(src)})
    write_json(out.with_suffix(".json"), meta)
    return meta


def write_sidecar(key: str, path: Path) -> dict:
    from . import panels as PN
    from .engine.clips import video_info

    it = item(key) or {"id": key}
    info = video_info(path)
    meta = {"id": key, "url": it.get("url"), "section": it.get("section"), "credit": it.get("credit", ""),
            "license": it.get("license", ""), "w": info["w"], "h": info["h"], "duration": round(info["duration"], 2),
            "fetched": dt.date.today().isoformat(),
            "motion": PN.measure_file(path, 540, 192, seconds=min(10.0, info["duration"]))}
    write_json(path.with_suffix(".json"), meta)
    return meta


def start_for(dur: float, need: float) -> float:
    """Deterministic start in the middle of the piece: the same plan gives the same video."""
    if dur <= need + 2:
        return 0.0
    return round((dur - need) / 2, 1)


FOCUS_STEPS = (0.0, 0.25, 0.5, 0.75, 1.0)


def frame_window(path: Path | str, need: float, w: int, h: int, dim: float = 0.0, fps: float = 2.0) -> dict:
    """Where to cut the banner from the background piece: start (s) and vertical focus with the most motion
    over the whole video (a frame taller than the source, layout C: horizontal focus `focus_x` instead). Same metrics and scale as QA (270 px wide: share of pixels changing by > 10 luma
    within 1 s, the worst second counts; largest dark flat area), measured on the dimmed picture. Windows
    without a dark hole win, then the liveliest worst second, then the window nearest the middle.
    Cached in the sidecar (one decode per background, size and length)."""
    import cv2
    import numpy as np

    from . import panels as PN
    from .engine.clips import read_frames, video_info

    path = Path(path)
    side = path.with_suffix(".json")
    key = f"{w}x{h}@{round(need)}@{dim:.2f}"
    meta = read_json(side) if side.exists() else {}
    if key in (meta.get("windows") or {}):
        return dict(meta["windows"][key], how="cached")
    info = video_info(path)
    sw = 270
    sh = max(8, int(round(sw * info["h"] / max(1, info["w"]))))
    ph = max(4, int(round(sw * h / max(1, w))))
    grey = [cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32) * (1 - dim)
            for f in read_frames(path, sw, sh, fps=fps)]
    if len(grey) < 3:
        return {"start": 0.0, "focus_y": 0.5, "how": "too short to measure"}
    dur = len(grey) / fps
    lag = int(round(fps))
    n = max(1, int(round(min(need, dur - 1.0) * fps)))
    pw = max(4, int(round(sh * w / max(1, h))))     # crop width when the target is taller than the source (layout C)
    axis = "y" if ph < sh else ("x" if pw < sw else "")
    best = None
    for fy in FOCUS_STEPS if axis else (0.5,):
        if axis == "y":
            y0 = int(round((sh - ph) * fy))
            crops = [g[y0:y0 + ph] for g in grey]
        elif axis == "x":
            x0 = int(round((sw - pw) * fy))
            crops = [g[:, x0:x0 + pw] for g in grey]
        else:
            crops = grey
        share = [float((np.abs(crops[i] - crops[i + lag]) > PN.CHANGE_DELTA).mean()) for i in range(len(crops) - lag)]
        void = [PN.dark_void(c.astype(np.uint8), block=4) for c in crops]
        for k in range(0, max(1, len(share) - n + 1)):
            win = share[k:k + n] or share
            vmax = max(void[k:k + n + lag] or void)
            worst, med = min(win), float(np.median(win))
            mid = abs((k / fps + need / 2) - dur / 2) / max(dur, 1)
            score = (vmax <= PN.MAX_DARK_VOID, round(worst, 2), round(med, 2), -mid) + \
                ((-abs(fy - 0.5),) if axis == "x" else ())
            if best is None or score > best[0]:
                best = (score, k / fps, fy, worst, med, vmax)
    _, start, fy, worst, med, vmax = best
    res = {"start": round(start, 1), "focus_y": fy if axis == "y" else 0.5, "focus_x": fy if axis == "x" else 0.5,
           "change_min": round(worst, 3), "change_median": round(med, 3),
           "dark_void": round(vmax, 3), "ok": bool(worst >= PN.MIN_CHANGE and vmax <= PN.MAX_DARK_VOID)}
    if side.exists():
        meta.setdefault("windows", {})[key] = res
        write_json(side, meta)
    return dict(res, how="measured")


def resolve(src: str, topic: str, need: float, mood: str | None = None) -> tuple[Path | None, dict]:
    """src = bg:auto | bg:<id>. Returns (file or None, info for the manifest). Never raises for a missing file:
    the caller falls back to a procedural loop and reports it."""
    key = src.split(":", 1)[1] if ":" in src else "auto"
    key = key or "auto"
    it = choose(topic, mood) if key == "auto" else item(key)
    if it is None:
        return None, {"error": f"unknown background '{key}' (shorts.py bg list)"}
    p = cache_path(it["id"])
    swap = ""
    if not p.exists():
        try:
            p = fetch(it["id"])
        except Exception as e:  # offline / blocked: report, do not crash the render
            err = (f"background '{it['id']}' is not cached and could not be downloaded ({str(e)[:160]}): "
                   f"run `shorts.py bg fetch {it['id']}`")
            alt = choose(topic, mood, cached_only=True) if key == "auto" else None
            if alt is None:
                return None, {"id": it["id"], "error": err}
            swap, it, p = f"{err}; bg:auto used the cached '{alt['id']}' instead", alt, cache_path(alt["id"])
    from .engine.clips import video_info

    dur = float(video_info(p)["duration"])
    info = {"id": it["id"], "credit": it.get("credit", ""), "url": it.get("url"), "duration": round(dur, 2),
            "start": start_for(dur, need), "focus": it.get("focus", "motion"), "kind": it.get("kind", ""),
            "how": "auto" if key == "auto" else "plan", "notes": [swap] if swap else []}
    if dur < need:
        info["notes"].append(f"background '{it['id']}' is {dur:.0f}s, the video {need:.0f}s: the loop will be visible "
                             f"(longer section in library.json, then `shorts.py bg fetch {it['id']} --force`)")
    return p, info


def describe() -> list[dict]:
    rows = []
    known = {it["id"] for it in items()}
    own = [item(p.stem) for p in sorted(cache_dir("bg").glob("*.json")) if p.stem not in known]
    for it in items() + [x for x in own if x]:
        p = cache_path(it["id"])
        side = p.with_suffix(".json")
        rows.append({"id": it["id"], "kind": it.get("kind"), "mood": it.get("mood"), "audience": it.get("audience"),
                     "url": it.get("url"), "verified": bool(it.get("verified")), "cached": p.exists(),
                     "motion": read_json(side).get("motion") if side.exists() else None})
    return rows
