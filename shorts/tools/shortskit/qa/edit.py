"""QA for edits (film / video scenes): what the cuts show and where they fall.

edit_content: shots differ, no text screens (credits, title cards), no black frames longer than 0.5 s.
beat_sync:    every planned cut is a visible change ON a strong beat (tolerance 50 ms); slow-mo present.
Everything is measured on the finished video, overlays and captions are masked out.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..analysis.screens import BLACK_MEAN, BLACK_STD, TEXT_LINES_HARD, text_lines
from . import frames as F

BEAT_TOL = 0.05
BEAT_MIN_HITS = 0.8
BLACK_MAX = 0.5
SAME_SHOT_BITS = 12  # dhash (256 bits) closer than this = the same picture


def is_edit(m: dict) -> bool:
    if m.get("schema_version") == "1.4" and m.get("genre") in ("tutorial", "interview", "story", "observation", "other"):
        return False
    live = [s for s in m["scenes"] if not s["skipped"]]
    return bool(live) and sum(1 for s in live if s["type"] in ("film", "video")) / len(live) >= 0.5


def _center(img: np.ndarray, lay: dict, scale: float = 1.0) -> tuple[np.ndarray, int]:
    y0 = int(lay["center"]["y"] * scale)
    y1 = int((lay["center"]["y"] + lay["center"]["h"]) * scale)
    return img[y0:y1], y0


def _masked_gray(img: np.ndarray, m: dict, t: float) -> np.ndarray:
    """Centre panel in grey with our own text (labels, CTA, captions) painted over with the frame mean."""
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    fill = int(np.median(g))
    for o in m["overlays"]:
        if o["t0"] <= t < o["t1"]:
            x0, y0, x1, y1 = o["box"]
            g[max(0, y0 - 8):y1 + 8, max(0, x0 - 8):x1 + 8] = fill
    for c in m["captions"]["chunks"]:
        if c["start"] - 0.1 <= t < c["end"] + 0.5:
            x0, y0, x1, y1 = c["box"]
            g[max(0, y0 - 8):y1 + 8, max(0, x0 - 8):x1 + 8] = fill
    cg, _ = _center(g, m["layout"])
    return cg


def edit_content(m: dict, full: np.ndarray, ft: list[float], small: np.ndarray, st: list[float]) -> dict:
    """Return {'ok': bool, 'problems': [...], ...measurements}."""
    lay = m["layout"]
    live = [s for s in m["scenes"] if not s["skipped"]]
    problems: list[str] = []
    # 1 shots are different pictures
    hashes = []
    for s in live:
        t = s["start"] + s["length"] / 2
        i = int(np.argmin([abs(x - t) for x in ft]))
        hashes.append(F.dhash(_center(full[i], lay)[0]))
    same_pairs = [(live[i - 1]["id"], live[i]["id"]) for i in range(1, len(hashes))
                  if F.hamming(hashes[i - 1], hashes[i]) < SAME_SHOT_BITS]
    distinct = sum(1 for i, h in enumerate(hashes) if all(F.hamming(h, p) >= SAME_SHOT_BITS for p in hashes[:i]))
    distinct_share = distinct / max(1, len(hashes))
    if same_pairs:
        problems.append(f"same picture twice in a row: {same_pairs[:3]}")
    if len(hashes) >= 4 and distinct_share < 0.6:
        problems.append(f"only {distinct}/{len(hashes)} shots are different pictures")
    # 2 text screens (credits, title cards) in the picture itself
    text_frames = []
    for img, t in zip(full, ft):
        n, _, _ = text_lines(_masked_gray(img, m, t))
        if n >= TEXT_LINES_HARD:
            text_frames.append(round(t, 2))
    step = ft[1] - ft[0] if len(ft) > 1 else 0.5
    runs, cur = [], []
    for t in text_frames:
        if cur and t - cur[-1] <= step + 1e-6:
            cur.append(t)
        else:
            if cur:
                runs.append(cur)
            cur = [t]
    if cur:
        runs.append(cur)
    longest_text = max((len(r) * step for r in runs), default=0.0)
    if longest_text >= 0.5 - 1e-6 and any(len(r) >= 2 for r in runs) or len(text_frames) > max(2, 0.1 * len(ft)):
        problems.append(f"text screen in the picture (credits/titles) at {text_frames[:6]}s")
    # 3 black frames
    sc = small.shape[2] / 1080
    blk = []
    for img in small:
        c, _ = _center(img, lay, sc)
        g = F.luma(c)
        blk.append(bool(g.mean() < BLACK_MEAN and g.std() < BLACK_STD))
    sstep = st[1] - st[0] if len(st) > 1 else 0.1
    longest_black, run, at = 0.0, 0.0, None
    for t, b in zip(st, blk):
        run = run + sstep if b else 0.0
        if run > longest_black:
            longest_black, at = run, round(t - run + sstep, 2)
    if longest_black > BLACK_MAX + 1e-6:
        problems.append(f"black frames for {longest_black:.1f}s at {at}s")
    return {"ok": not problems, "problems": problems, "shots": len(hashes), "distinct_shots": distinct,
            "same_in_a_row": same_pairs, "text_frames": text_frames, "longest_text_s": round(longest_text, 2),
            "longest_black_s": round(longest_black, 2)}


def measured_cuts(video: Path, m: dict, fps: float) -> tuple[list[float], np.ndarray]:
    """Visible hard changes in the centre panel, frame accurate."""
    lay = m["layout"]
    w, h = 90, 160
    frames, times = F.sample(video, fps, w, h)
    y0 = int(lay["center"]["y"] * h / 1920)
    y1 = max(y0 + 2, int((lay["center"]["y"] + lay["center"]["h"]) * h / 1920))
    g = [F.luma(f[y0:y1]) for f in frames]
    d = np.array([0.0] + [float(np.mean(np.abs(g[i] - g[i - 1]))) for i in range(1, len(g))])
    cuts: list[float] = []
    for k in range(1, len(d)):
        win = np.concatenate([d[max(1, k - 4):k], d[k + 1:k + 5]])
        base = float(np.median(win)) if len(win) else 0.0
        if d[k] > 10 and d[k] > 2.5 * base + 2:
            t = times[k]
            if not cuts or t - cuts[-1] > 0.15:
                cuts.append(round(t, 4))
    return cuts, d


def beat_sync(video: Path, m: dict, fps: float, duration: float) -> dict:
    sync = m.get("music_sync") or {}
    beats = sync.get("strong_beats") or []
    planned = [s["start"] for s in m["scenes"] if not s["skipped"] and s["start"] > 0.3]
    planned = [t for t in planned if t < duration - 0.4]
    cuts, _ = measured_cuts(video, m, fps)
    rows, hits, visible = [], 0, 0
    for p in planned:
        near = [c for c in cuts if abs(c - p) <= 0.1]
        seen = min(near, key=lambda c: abs(c - p)) if near else None
        beat = min(beats, key=lambda b: abs(b - (seen if seen is not None else p))) if beats else None
        err = abs(seen - beat) if seen is not None and beat is not None else None
        ok = err is not None and err <= BEAT_TOL + 1e-6
        visible += seen is not None
        hits += ok
        rows.append({"planned": round(p, 3), "seen": seen, "beat": beat, "err_ms": None if err is None else round(err * 1000)})
    share = hits / max(1, len(planned))
    slow = [s["id"] for s in m["scenes"] if any(float(x.get("rate", 1)) < 1 for x in s.get("speed") or [])
            or ((s.get("edit_report") or {}).get("rate_min", 1) < 0.95)]  # velocity curves hang in slow motion
    first = m["scenes"][0] if m["scenes"] else {}
    return {"ok": bool(beats) and share >= BEAT_MIN_HITS, "hit_share": round(share, 3), "hits": hits,
            "planned_cuts": len(planned), "visible_cuts": visible, "measured_cuts": len(cuts),
            "tolerance_ms": int(BEAT_TOL * 1000), "slowmo_scenes": slow, "first_role": first.get("why", ""),
            "rows": rows[:40], "beats_known": bool(beats)}


def edit_style(m: dict, fps: float) -> dict:
    """Edit craft (tutorial + research sec. 20): no panels, the link/handle in the exact centre, speed curves,
    faces centred, the line ends exactly on the drop, a face on frame 0, 7-20 s."""
    live = [s for s in m["scenes"] if not s["skipped"]]
    eds = [s for s in live if s.get("edit")]
    if not eds:
        return {"applicable": False, "problems": [], "warnings": []}
    problems: list[str] = []
    warnings: list[str] = []
    lay = m["layout"]
    if lay.get("mode") != "center_only" or lay.get("top") or lay.get("bottom"):
        problems.append(f"edit with panels (layout {lay.get('mode')}): edits are full screen, layout center_only")
    # CTA / link plates: optical centre of the screen
    off = []
    for o in m["overlays"]:
        if o["kind"].startswith("cta") and o.get("box"):
            cx = (o["box"][0] + o["box"][2]) / 2
            if abs(cx - 540) > 4:
                off.append(f"{o['kind']} at {o['t0']:.1f}s is {cx - 540:+.0f}px off centre")
    problems += off
    # speed curves
    moving = [s for s in eds if (s["edit"].get("velocity") or "flat") != "flat"]
    flat_ok = [s for s in eds if (s["edit"].get("velocity") or "flat") == "flat"]
    share = len(moving) / max(1, len(eds))
    if len(eds) >= 4 and share < 0.6:
        warnings.append(f"only {len(moving)}/{len(eds)} shots have a speed curve (velocity): the edit looks flat")
    # faces centred where there is a face
    face_shots = [s for s in eds if (s.get("edit_report") or {}).get("face_frames", 0) >= 0.5]
    centred = [s for s in face_shots if (s["edit_report"].get("face_center") or [0.5])[0] and
               abs(s["edit_report"]["face_center"][0] - 0.5) <= 0.12]
    if face_shots and len(centred) / len(face_shots) < 0.7:
        problems.append(f"faces centred only in {len(centred)}/{len(face_shots)} face shots")
    no_face = [s["id"] for s in eds if (s.get("edit_report") or {}).get("face_frames", 1) < 0.2]
    if len(no_face) > len(eds) / 2:
        warnings.append(f"{len(no_face)}/{len(eds)} shots without a face: hero edits live on faces")
    # the line and the drop
    drop = (m.get("audio") or {}).get("drop_at")
    first = live[0]
    end1 = first["start"] + first["length"]
    words = (m.get("captions") or {}).get("words_spoken") or []
    line = {"drop_at": drop, "first_scene_end": round(end1, 3), "words_before_drop": 0}
    if drop is not None:
        line["words_before_drop"] = sum(1 for w in words if w["s"] < drop)
        if first.get("edit") and (first["edit"].get("velocity") or "flat") == "flat" and abs(drop - end1) > 1.5 / fps:
            problems.append(f"the drop ({drop:.2f}s) is not at the end of the line ({end1:.2f}s)")
        if not line["words_before_drop"]:
            warnings.append("no dialogue before the drop (tutorial: a short line from the film, then the drop)")
    rep0 = first.get("edit_report") or {}
    if rep0 and rep0.get("face_frames", 0) < 0.3:
        warnings.append("no face on the first shot: frame 0 should be the strongest (a face, big)")
    total = first["start"] + sum(s["length"] for s in live)
    if not 7 <= total <= 20.5:
        warnings.append(f"edit is {total:.1f}s: 7-20 s loops best (research 20)")
    return {"applicable": True, "problems": problems, "warnings": warnings, "velocity_share": round(share, 2),
            "face_shots": len(face_shots), "faces_centred": len(centred), "flat_shots": len(flat_ok),
            "line": line, "duration": round(total, 2)}
