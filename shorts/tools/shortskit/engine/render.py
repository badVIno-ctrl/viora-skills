"""plan.json -> finished vertical video + captions + manifest (what was drawn where and when, used by QA)."""
from __future__ import annotations

import asyncio
import bisect
import math
import os
import shutil
import subprocess
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .. import contract as K
from .. import plan as P
from ..config import H, W
from ..util import ShortsError, ease, log, write_json
from . import audio as A
from . import brand as B
from . import captions as C
from . import cards as CD
from . import graphics as G
from . import kinetic as KN
from . import layout as L
from . import tts as T
from . import vfx as VX
from .clips import read_frames, video_info

PAD = 0.35  # silence after each voice line
FLASH_IN, FLASH_OUT = 0.25, 0.18


@dataclass
class SceneT:
    data: dict
    idx: int
    length: float = 0.0
    start: float = 0.0
    speech: T.Speech | None = None
    words: list[dict] = field(default_factory=list)  # relative to scene start
    clip: Path | None = None
    audio: Path | None = None
    clicks: list[float] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: str = ""

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def type(self) -> str:
        return self.data["source"]["type"]


SLIDE_IN, SLIDE_OUT, SLIDE_DY = 0.42, 0.22, 96  # Material motion: enter longer than exit; mobile ~300-500 ms
KIN_IN, KIN_OUT = 0.15, 0.10        # kinetic words: quick pop, the block leaves together
BACK_IN = 0.32                      # pop_back (subscribe card): scale with a small overshoot
LEFT_IN, LEFT_OUT = 0.32, 0.22      # slide_left (fact plates)
DOWN_IN = 0.35                      # slide_down (title bar)
ANIMS = ("pop", "slide", "pop_back", "slide_down", "slide_left", "type", "kin", "bob", "none")


def ease_out_back(t: float, s: float = 1.25) -> float:
    """Overshoot a little and settle: the 'slides out and clicks into place' feel."""
    t = min(1.0, max(0.0, t)) - 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


@dataclass
class Overlay:
    sprite: G.Sprite
    t0: float
    t1: float
    instant_in: bool = False
    arr: np.ndarray | None = None
    anim: str = "pop"  # see ANIMS; pop (scale from the centre) | slide (rises from below into place, exact centre)
    alt: Image.Image | None = None      # second state (subscribe card after the click)
    alt_at: float | None = None
    alt_arr: np.ndarray | None = None
    cursor: dict | None = None          # {"img", "from": (x, y), "to": (x, y), "t_move": s, "t_click": s}
    steps: list | None = None           # [(t, image)]: the picture from each time on (post card writes itself)
    _step: tuple | None = None          # (index, array) of the state on screen: one conversion per state

    def alpha_scale(self, t: float) -> tuple[float, float]:
        a, s, _ = self.motion(t)
        return a, s

    def motion(self, t: float) -> tuple[float, float, float]:
        """(alpha, scale, dy px) at time t."""
        a, s, _, dy, _ = self.full(t)
        return a, s, dy

    def full(self, t: float) -> tuple[float, float, float, float, float]:
        """(alpha, scale, dx px, dy px, reveal 0..1 from the left) at time t."""
        if t < self.t0 or t >= self.t1:
            return 0.0, 1.0, 0.0, 0.0, 1.0
        u_in = 1.0 if self.instant_in else None
        an = self.anim
        if an == "none":
            return 1.0, 1.0, 0.0, 0.0, 1.0
        if an == "slide":
            if not self.instant_in and t < self.t0 + SLIDE_IN:
                u = (t - self.t0) / SLIDE_IN
                return min(1.0, u * 2.5), 1.0, 0.0, SLIDE_DY * (1 - ease_out_back(u)), 1.0
            if t > self.t1 - SLIDE_OUT:
                v = 1 - (self.t1 - t) / SLIDE_OUT
                return max(0.0, 1 - v), 1.0, 0.0, -0.4 * SLIDE_DY * v * v, 1.0
            return 1.0, 1.0, 0.0, 0.0, 1.0
        if an == "kin":
            if u_in is None and t < self.t0 + KIN_IN:
                u = (t - self.t0) / KIN_IN
                return min(1.0, u * 2.0), 0.6 + 0.4 * ease_out_back(u, 1.7), 0.0, 0.0, 1.0
            if t > self.t1 - KIN_OUT:
                return max(0.0, (self.t1 - t) / KIN_OUT), 1.0, 0.0, 0.0, 1.0
            return 1.0, 1.0, 0.0, 0.0, 1.0
        if an == "pop_back":
            if u_in is None and t < self.t0 + BACK_IN:
                u = (t - self.t0) / BACK_IN
                return min(1.0, u * 3.0), 0.5 + 0.5 * ease_out_back(u, 1.4), 0.0, 0.0, 1.0
        elif an == "slide_left":
            off = float(self.sprite.box.x + self.sprite.box.w + 16)
            if u_in is None and t < self.t0 + LEFT_IN:
                u = (t - self.t0) / LEFT_IN
                return 1.0, 1.0, -off * (1 - VX.ease("out_cubic", u)), 0.0, 1.0
            if t > self.t1 - LEFT_OUT:
                v = 1 - (self.t1 - t) / LEFT_OUT
                return 1.0, 1.0, -off * v ** 3, 0.0, 1.0
            return 1.0, 1.0, 0.0, 0.0, 1.0
        elif an == "slide_down":
            if u_in is None and t < self.t0 + DOWN_IN:
                u = (t - self.t0) / DOWN_IN
                return min(1.0, u * 2.5), 1.0, 0.0, -SLIDE_DY * (1 - ease_out_back(u)), 1.0
        elif an == "type":
            n = max(1, len(self.sprite.text))
            dur = min(0.9, max(0.3, 0.035 * n))
            if t > self.t1 - FLASH_OUT:
                return max(0.0, (self.t1 - t) / FLASH_OUT), 1.0, 0.0, 0.0, 1.0
            rev = 1.0 if u_in is not None else min(1.0, (t - self.t0) / dur)
            return 1.0, 1.0, 0.0, 0.0, rev
        elif an == "bob":
            a = 1.0 if u_in is not None else min(1.0, (t - self.t0) / 0.2)
            if t > self.t1 - FLASH_OUT:
                a = min(a, max(0.0, (self.t1 - t) / FLASH_OUT))
            return a, 1.0, 0.0, 12.0 * math.sin(2 * math.pi * 1.5 * (t - self.t0)), 1.0
        else:  # pop
            if not self.instant_in and t < self.t0 + FLASH_IN:
                k = ease((t - self.t0) / FLASH_IN)
                return k, 0.6 + 0.4 * k, 0.0, 0.0, 1.0
        if t > self.t1 - FLASH_OUT:
            k = (self.t1 - t) / FLASH_OUT
            return max(0.0, k), 0.92 + 0.08 * k, 0.0, 0.0, 1.0
        return 1.0, 1.0, 0.0, 0.0, 1.0

    def image_at(self, t: float) -> np.ndarray:
        if self.steps:
            i = max(0, bisect.bisect_right([x[0] for x in self.steps], t + 1e-6) - 1)
            if self._step is None or self._step[0] != i:
                self._step = (i, np.asarray(self.steps[i][1].convert("RGBA")))
            return self._step[1]
        if self.alt_arr is not None and self.alt_at is not None and t >= self.alt_at:
            return self.alt_arr
        return self.arr

    def cursor_at(self, t: float) -> tuple[int, int, float] | None:
        """(x, y, scale) of the cursor tip, None when hidden. Moves in, presses (scale 0.85), stays a moment."""
        c = self.cursor
        if not c or t < c["t_move"] or t >= self.t1 - FLASH_OUT:
            return None
        (x0, y0), (x1, y1) = c["from"], c["to"]
        u = VX.ease("out_cubic", (t - c["t_move"]) / max(0.05, c["t_click"] - c["t_move"]))
        x, y = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        sc = 0.85 if 0 <= t - c["t_click"] < 0.12 else 1.0
        return int(round(x)), int(round(y)), sc


def with_utm(url: str, name: str, platform: str) -> str:
    if not url.startswith(("http://", "https://")) or "t.me/" in url:
        return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(u.query)
    q += [("utm_source", platform), ("utm_medium", "short"), ("utm_campaign", name)]
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), u.fragment))


def short_link(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")


# ---------------------------------------------------------------- stage 1: voice and lengths

def voice_and_lengths(scenes: list[SceneT], plan: dict, lang: str) -> None:
    v = plan["audio"].get("voice", {})
    for s in scenes:
        say = s.data.get("say", "").strip()
        if say:
            s.speech = T.synth(say, lang=lang, engine=v.get("engine", "auto"), voice=v.get("voice"),
                               speed=float(v.get("speed", 1.0)))
            s.words = [dict(w) for w in s.speech.words]
            s.length = max(s.speech.duration + PAD, float(s.data.get("duration", 0)), float(s.data.get("duration_hint", 0)))
            if s.speech.estimated:
                s.notes.append(f"word timings estimated ({s.speech.engine})")
        elif s.data.get("duration"):
            s.length = float(s.data["duration"])
        elif s.data.get("duration_hint"):
            s.length = float(s.data["duration_hint"])
        elif s.type in ("video", "film"):
            src = s.data["source"]
            if src.get("out") is None:
                raise ShortsError(f"scene {s.id}: video/film without say needs duration or source.out")
            from .clips import SpeedMap

            s.length = SpeedMap(s.data.get("speed")).out_at(float(src["out"]) - float(src.get("in", 0)))
        else:
            raise ShortsError(f"scene {s.id}: no say and no duration")
        if s.data.get("transcript") and not say:
            s.words = [{"w": w["w"], "s": float(w["s"]), "e": float(w["e"])} for w in s.data["transcript"]]
        # edit shots on beats are often < 1 s (0.43 s quick cuts): only non-video scenes keep the 1 s floor
        s.length = max(0.2 if s.type in ("film", "video") else 1.0, s.length)


def assign_starts(scenes: list[SceneT], fps: int = 30) -> float:
    """Scene starts on exact frames: lengths are snapped to 1/fps so cuts land where the plan says."""
    t = 0.0
    for s in scenes:
        if s.skipped:
            continue
        s.length = max(1, round(s.length * fps)) / fps
        s.start = t
        t += s.length
    return t


# ---------------------------------------------------------------- stage 2: capture

async def _browser_jobs(jobs, top_job):
    from playwright.async_api import async_playwright

    from ..adapters import html as HT
    from ..adapters import site as SI

    async with async_playwright() as pw:
        browser = await SI.launch(pw)
        try:
            for fn in jobs:
                await fn(browser, SI, HT)
            if top_job:
                await top_job(browser, HT)
        finally:
            await browser.close()


def topic_words(plan: dict) -> str:
    return " ".join([(plan.get("metadata") or {}).get("topic") or "", plan["meta"].get("name", "")] +
                    [sc.get("on_screen_text", "") for sc in plan["scenes"]] + [sc.get("say", "") for sc in plan["scenes"]])


def resolve_bg(src: str, plan: dict, plan_dir: Path, need: float) -> tuple[Path | None, dict]:
    """bg:auto | bg:<id> (library) or a file path; info has credit / start / notes for the manifest."""
    if src.startswith("bg:"):
        from .. import bglib as BG

        mood = ((plan.get("fx") or {}).get("transitions") or {}).get("auto") if isinstance((plan.get("fx") or {}).get("transitions"), dict) else None
        return BG.resolve(src, topic_words(plan), need, mood)
    p = P.resolve_ref(src, plan_dir)
    if not p:
        return None, {"error": f"background video not found: {src}"}
    return p, {"id": Path(src).stem, "credit": "", "start": 0.0, "focus": "center", "how": "file", "notes": []}


def bg_scene(s: SceneT, scenes: list[SceneT], plan: dict, plan_dir: Path, w: int, h: int) -> None:
    """Video scene `ref: "bg:auto" | "bg:<id>"`: background gameplay on the whole frame (research 17, layout C).
    Scenes with the same background continue one window (no jump back to the same jump), the window and the
    horizontal crop are where the motion is (QA metric), the game sound is off, the author goes to the credits."""
    ref = s.data["source"]["ref"]
    same = [x for x in scenes if not x.skipped and x.type == "video"
            and (x.data.get("_bg_ref") or x.data["source"].get("ref")) == ref]   # resolved scenes keep their bg: ref
    need = sum(x.length for x in same)
    path, info = resolve_bg(ref, plan, plan_dir, need + 1.0)
    if path is None:
        raise ShortsError(f"scene {s.id}: {info.get('error', 'background missing')} (or `shorts.py bg add ID FILE`)")
    from .. import bglib as BG

    src0 = s.data["source"]
    win = BG.frame_window(path, need, w, h, 0.0)
    before = sum(x.length for x in same[:same.index(s)]) if s in same else 0.0
    dur = float(info.get("duration") or 0.0)
    start = float(src0.get("in", win["start"] + before))
    if dur and start + s.length > dur:
        start = max(0.0, (start % max(1.0, dur - s.length)))
    src = dict(src0, ref=str(path), keep_audio=False)
    src["in"] = round(start, 3)
    src.pop("out", None)
    src.setdefault("crop_x", float(win.get("focus_x", 0.5)))
    s.data = dict(s.data, source=src, _bg=info, _bg_ref=ref)
    s.notes.append(f"background {info.get('id')}: from {start:.1f}s, crop_x {src['crop_x']}, motion min "
                   f"{win.get('change_min')} (game sound off)")
    s.notes += list(info.get("notes", []))


def _focus(spec, path: Path, w: int, h: int) -> tuple[tuple[float, float], dict]:
    """fit.focus -> (fx, fy): motion (measured), center, number (vertical) or [x, y]."""
    if isinstance(spec, (list, tuple)) and len(spec) == 2:
        return (float(spec[0]), float(spec[1])), {"how": "plan"}
    if isinstance(spec, (int, float)):
        return (0.5, float(spec)), {"how": "plan"}
    if spec == "motion":
        fx, fy, rep = VX.motion_focus(path, w, h)
        return (fx, fy), {"how": "motion", **rep}
    return (0.5, 0.5), {"how": "center"}


_BEATS_CACHE: dict[str, dict] = {}


def music_video_beats(plan: dict, plan_dir: Path) -> dict | None:
    """Beats of the plan music in video time (file time - start + offset). None without a local track."""
    m = plan["audio"].get("music") or {}
    src = m.get("source")
    if not src or str(src).lower() in ("none", "auto") or str(src).startswith(("http://", "https://")):
        return None
    path = P.resolve_ref(src, plan_dir)
    if not path:
        return None
    key = str(path)
    if key not in _BEATS_CACHE:
        try:
            _BEATS_CACHE[key] = A.beats(path)
        except Exception as e:  # noqa: BLE001 - beats are a bonus for html pages
            log.info("no beats for the html page: %s", e)
            _BEATS_CACHE[key] = {}
    b = _BEATS_CACHE[key]
    if not b.get("beats"):
        return None
    shift = float(m.get("offset", 0) or 0) - float(m.get("start", 0) or 0)
    downs = {round(x, 3) for x in b.get("downbeats") or []}
    beats = [round(x + shift, 3) for x in b["beats"] if x + shift >= 0]
    return {"beats": beats, "downbeats": sorted(round(x + shift, 3) for x in downs if x + shift >= 0),
            "tempo": b.get("tempo")}


def html_page_info(s: SceneT, plan: dict, plan_dir: Path, brand: B.Brand, fps: int) -> dict:
    """window.SHORTS for an html scene: everything in page time (seek time = video time - scene start + source.in)."""
    off = float(s.data["source"].get("in", 0) or 0)
    shift = off - s.start
    info: dict = {"scene": s.id, "length": round(s.length, 3), "in": off, "start": round(s.start, 3), "fps": fps,
                  "seed": int(s.data["source"].get("seed", 7) or 7),
                  "words": [{"w": w["w"], "s": round(w["s"] + off, 3), "e": round(w["e"] + off, 3)} for w in s.words],
                  "brand": {"bg": brand.bg, "fg": brand.fg, "accent": brand.accent}}
    mb = music_video_beats(plan, plan_dir)
    if mb:
        lo, hi = s.start - 0.05, s.start + s.length + 0.05
        info["beats"] = [round(b + shift, 3) for b in mb["beats"] if lo <= b <= hi]
        info["strong"] = [round(b + shift, 3) for b in mb["downbeats"] if lo <= b <= hi]
        info["tempo"] = mb["tempo"]
    drop = (plan["audio"].get("music") or {}).get("drop_at")
    if drop is not None:
        info["drop"] = round(float(drop) + shift, 3)
    return info


def capture_all(scenes: list[SceneT], plan: dict, plan_dir: Path, lay: L.Layout, brand: B.Brand, fps: int,
                work: Path, lang: str, total_hint: float, size: tuple[int, int] | None = None) -> dict:
    from ..adapters import media as ME
    from ..adapters import text_images as TI

    cw, ch = size or (lay.center.w, lay.center.h)
    jobs = []
    for s in scenes:
        t = s.type
        if t == "site":
            async def job(browser, SI, HT, s=s):
                cap = await SI.capture(browser, s.data, cw, ch, fps, s.length, work, lang, brand.accent)
                s.clip, s.clicks, s.notes, s.skipped = cap.clip, cap.clicks, s.notes + cap.notes, cap.skipped
            jobs.append(job)
        elif t == "html":
            path = P.resolve_ref(s.data["source"]["ref"], plan_dir)
            if not path:
                raise ShortsError(f"html file not found: {s.data['source']['ref']}")

            page = html_page_info(s, plan, plan_dir, brand, fps)

            async def job(browser, SI, HT, s=s, path=path, page=page):
                cap = await HT.capture(browser, dict(s.data, _page=page), path, cw, ch, fps, s.length, work, lang, brand.accent)
                s.clip, s.clicks, s.notes = cap.clip, cap.clicks, s.notes + cap.notes
            jobs.append(job)
        elif t in ("video", "film"):
            if t == "video" and str(s.data["source"].get("ref", "")).startswith("bg:"):
                bg_scene(s, scenes, plan, plan_dir, cw, ch)
            if plan.get("edit") and t == "film" and s.data.get("edit") is not False:
                s.data["edit"] = {**plan["edit"], **(s.data.get("edit") or {})}
            cap = ME.capture(s.data, cw, ch, fps, s.length, work, plan_dir)
            s.clip, s.audio, s.notes = cap.clip, cap.audio, s.notes + cap.notes
        elif t == "images":
            cap = TI.images_capture(s.data, cw, ch, fps, s.length, work, plan_dir, brand.accent)
            s.clip, s.clicks = cap.clip, cap.clicks
        elif t == "text":
            y0 = 0
            if s.data.get("on_screen_text"):
                y0 = max(0, lay.label_box.y1 - lay.center.y + 16)
            y1 = ch
            if plan["captions"].get("enabled", True) and (s.words or s.data.get("say")):
                y1 = min(ch, lay.caption_band.y - lay.center.y - 16)
            cap = TI.text_capture(s.data, cw, ch, fps, s.length, work, plan_dir, brand, s.words, free=(y0, y1))
            s.data["_text_area"] = [y0, y1]  # kinetic captions keep out of the scene's own words
            s.clip, s.notes = cap.clip, s.notes + cap.notes
    top_info: dict = {"kind": "none"}
    top_job = None
    top = (plan["layout"].get("top") or {}) if lay.top else {}
    if lay.top:
        src = top.get("source", "")
        if src.startswith("html:"):
            path = P.resolve_ref(src[5:], plan_dir)
            if not path:
                raise ShortsError(f"top html not found: {src}")
            top_info = {"kind": "html", "path": str(work / "top.mp4"), "src": src}

            async def top_job(browser, HT, path=path):
                total = sum(s.length for s in scenes if not s.skipped)
                with HT.page_url(path) as url:
                    await HT.render_deterministic(browser, url, lay.top.w, lay.top.h, fps, total + 0.5, work / "top.mp4")
        elif src.startswith("bg:"):
            path, bg = resolve_bg(src, plan, plan_dir, total_hint + 1.0)
            fit = top.get("fit") or {}
            if path is None:
                from .. import panels as PN

                kind = PN.choose_kind(topic_words(plan), [sc["source"]["type"] for sc in plan["scenes"]])
                path = PN.make_loop(kind, lay.top.w, lay.top.h, fps, (brand.bg, brand.fg, brand.accent))
                top_info = {"kind": "video", "path": str(path), "start": 0.0, "loop": kind, "src": src,
                            "bg": bg, "notes": [bg.get("error", "background missing") + f"; used loop:{kind}"]}
            else:
                dim = float(fit.get("dim", 0.12))
                start = float(top.get("start", bg.get("start", 0.0)))
                if "focus" not in fit and "start" not in top:
                    # the window with motion in every second (the banner QA rule), not just the middle
                    from .. import bglib as BG

                    win = BG.frame_window(path, total_hint, lay.top.w, lay.top.h, dim)
                    focus, frep, start = (0.5, win["focus_y"]), dict(win, how="window"), win["start"]
                else:
                    focus, frep = _focus(fit.get("focus", bg.get("focus", "motion")), path, lay.top.w, lay.top.h)
                top_info = {"kind": "video", "path": str(path), "start": start,
                            "src": src, "bg": bg, "focus": list(focus), "focus_report": frep,
                            "dim": dim, "notes": list(bg.get("notes", []))}
        elif src.startswith("loop:"):
            from .. import panels as PN

            kind = src[5:] or "auto"
            if kind == "auto":
                kind = PN.choose_kind(" ".join([(plan.get("metadata") or {}).get("topic") or "", plan["meta"].get("name", "")] +
                                               [sc.get("on_screen_text", "") for sc in plan["scenes"]]),
                                      [sc["source"]["type"] for sc in plan["scenes"]])
            path = PN.make_loop(kind, lay.top.w, lay.top.h, fps, (brand.bg, brand.fg, brand.accent))
            top_info = {"kind": "video", "path": str(path), "start": 0.0, "loop": kind, "src": src}
        elif src.startswith("color:"):
            top_info = {"kind": "color", "color": src[6:]}
        elif src:
            p = P.resolve_ref(src, plan_dir)
            if not p:
                raise ShortsError(f"top video not found: {src}")
            top_info = {"kind": "video", "path": str(p), "start": float(top.get("start", 0))}
            fit = top.get("fit") or {}
            if fit:
                focus, frep = _focus(fit.get("focus", "center"), p, lay.top.w, lay.top.h)
                top_info.update(focus=list(focus), focus_report=frep, dim=float(fit.get("dim", 0.0)))
    if jobs or top_job:
        asyncio.run(_browser_jobs(jobs, top_job))
    return top_info


# ---------------------------------------------------------------- stage 3: compose

def _blend(canvas: np.ndarray, sprite: np.ndarray, x: int, y: int, alpha: float) -> None:
    h, w = sprite.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.shape[1], x + w), min(canvas.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sp = sprite[y0 - y:y1 - y, x0 - x:x1 - x]
    a = sp[..., 3:4].astype(np.float32) / 255.0 * alpha
    region = canvas[y0:y1, x0:x1].astype(np.float32)
    canvas[y0:y1, x0:x1] = (region * (1 - a) + sp[..., :3].astype(np.float32) * a).astype(np.uint8)


def _top_frames(top_info: dict, lay: L.Layout, total: float, fps: int):
    n = int(round(total * fps)) + 2
    if not lay.top:
        return None
    if top_info["kind"] == "color":
        from ..util import hex_to_rgb

        frame = np.zeros((lay.top.h, lay.top.w, 3), np.uint8)
        frame[:] = hex_to_rgb(top_info["color"])
        return (frame for _ in range(n))
    if top_info["kind"] in ("video", "html"):
        fx, fy = top_info.get("focus") or (0.5, 0.5)
        it = read_frames(top_info["path"], lay.top.w, lay.top.h, start=top_info.get("start", 0.0), fps=fps,
                         loop=top_info["kind"] == "video", focus_x=fx, focus_y=fy)
        dim = float(top_info.get("dim") or 0.0)
        if dim > 0.001:
            return (cv2.convertScaleAbs(f, alpha=1.0 - dim, beta=0) for f in it)
        return it
    return None


def _center_frames(scenes: list[SceneT], lay: L.Layout, size: tuple[int, int] | None = None):
    """Frames of all live scenes in order; size = clip size when it is not the centre (full split)."""
    w, h = size or (lay.center.w, lay.center.h)
    for s in scenes:
        if s.skipped:
            continue
        info = video_info(s.clip)
        if (info["w"], info["h"]) != (w, h):
            raise ShortsError(f"clip {s.clip} has wrong size")
        yield from read_frames(s.clip, w, h)


def _indexed_frames(live: list[SceneT], w: int, h: int):
    """(index in live, frame) for every frame of every live scene."""
    for i, s in enumerate(live):
        info = video_info(s.clip)
        if (info["w"], info["h"]) != (w, h):
            raise ShortsError(f"clip {s.clip} has wrong size")
        for fr in read_frames(s.clip, w, h):
            yield i, fr


def _first_frame(s: SceneT, w: int, h: int) -> np.ndarray | None:
    it = read_frames(s.clip, w, h, duration=0.2)
    try:
        return next(it, None)
    finally:
        it.close()


# final encode: "veryfast" at crf 18 is ~3x faster than "medium" and visually the same for shorts
# (docs/perf.md); SHORTS_PRESET overrides (e.g. "medium" for an archive copy)
FINAL_PRESET = os.environ.get("SHORTS_PRESET", "veryfast")


def _draw_overlay(canvas: np.ndarray, o: Overlay, t: float) -> None:
    a, s, dx, dy, rev = o.full(t)
    if a <= 0.01:
        return
    spr = o.image_at(t)
    bx = o.sprite.box
    if rev < 0.999:
        w = max(1, int(round(spr.shape[1] * rev)))
        spr = spr[:, :w]
    if abs(s - 1) > 1e-3:
        nw, nh = max(1, int(spr.shape[1] * s)), max(1, int(spr.shape[0] * s))
        spr = cv2.resize(spr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        x = int(round(bx.x + (bx.w - nw) / 2))
        y = int(round(bx.y + (bx.h - nh) / 2))
    else:
        x, y = bx.x, bx.y
    _blend(canvas, spr, int(round(x + dx)), int(round(y + dy)), a)
    cur = o.cursor_at(t)
    if cur is not None:
        cx, cy, sc = cur
        img = o.cursor["arr"]
        if abs(sc - 1) > 1e-3:
            img = cv2.resize(img, (max(1, int(img.shape[1] * sc)), max(1, int(img.shape[0] * sc))), interpolation=cv2.INTER_AREA)
        _blend(canvas, img, cx, cy, min(1.0, a))


def compose(out_mp4: Path, scenes: list[SceneT], lay: L.Layout, brand: B.Brand, overlays: list[Overlay],
            bottom_img: Image.Image | None, top_info: dict, total: float, fps: int, ass_path: Path | None,
            audio_wav: Path, fx: dict, loop: bool, cand_dir: Path | None = None, vx: VX.State | None = None) -> dict:
    """Frame loop. Centre picture order: punch -> transition -> flicker -> split -> look keys -> letterbox,
    then panels, overlays (text always sharp and still), flash, loop crossfade."""
    from ..util import hex_to_rgb

    vx = vx or VX.State()
    live = [s for s in scenes if not s.skipped]
    n = int(round(total * fps))
    bg = np.array(hex_to_rgb(brand.bg), np.uint8)
    bottom_arr = np.asarray(bottom_img.convert("RGB")) if bottom_img is not None and not callable(bottom_img) else None
    for o in overlays:
        o.arr = np.asarray(o.sprite.img.convert("RGBA"))
        if o.alt is not None:
            o.alt_arr = np.asarray(o.alt.convert("RGBA"))
        if o.cursor is not None and "arr" not in o.cursor:
            o.cursor["arr"] = np.asarray(o.cursor["img"].convert("RGBA"))
    vf = []
    if ass_path:
        fonts_dir = str(brand.display.path.parent).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf.append(f"ass={ass_path.name}:fontsdir='{fonts_dir}'")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-", "-i", str(audio_wav)]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", FINAL_PRESET, "-crf", "18", "-profile:v", "high",
            "-threads", "0",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{n / fps:.3f}",
            "-movflags", "+faststart", out_mp4.name]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=str(out_mp4.parent))
    cw, ch = lay.center.w, lay.center.h
    clip_w, clip_h = vx.clip_size or (cw, ch)
    center_it = _indexed_frames(live, clip_w, clip_h)
    top_it = _top_frames(top_info, lay, total, fps)
    punches = sorted(fx.get("punch") or [])
    flashes = sorted(fx.get("flash") or [])
    first = None
    last_c = None
    cur_i = -1
    prev_last = None          # last frame of the previous scene (held for push / dissolve / flicker after the cut)
    firsts: dict[int, np.ndarray | None] = {}
    starts_k = {int(round(s.start * fps)): i for i, s in enumerate(live)}

    def first_of(i: int) -> np.ndarray | None:
        if i not in firsts and 0 <= i < len(live):
            firsts[i] = _first_frame(live[i], clip_w, clip_h)
        return firsts.get(i)

    last_top = None
    loop_n = int(0.3 * fps) if loop else 0
    t_start = time.time()
    s0 = lay.safe.rect
    safe_off = (max(0, s0.x - lay.center.x), max(0, s0.y - lay.center.y), min(cw, s0.x1 - lay.center.x),
                min(ch, s0.y1 - lay.center.y))
    for sp in vx.splits:
        sp.reader, sp.last_b = None, None
    # clean centre frames (no captions, no overlays) for covers: middle of every scene
    cand = {}
    if cand_dir is not None:
        cand_dir.mkdir(parents=True, exist_ok=True)
        for s in scenes:
            if not s.skipped:
                cand[int((s.start + s.length * 0.55) * fps)] = s.id
    try:
        for k in range(n):
            t = k / fps
            canvas = np.empty((H, W, 3), np.uint8)
            canvas[:] = bg
            if lay.top is not None and top_it is not None:
                fr = next(top_it, None)
                last_top = fr if fr is not None else last_top
                if last_top is not None:
                    canvas[lay.top.y:lay.top.y1, :] = last_top
            got = next(center_it, None)
            if got is not None:
                i, c = got
                if i != cur_i:
                    prev_last = last_c if cur_i >= 0 else None
                    cur_i = i
                last_c = c
            if last_c is not None:
                cf = last_c
                p = [t - x for x in punches if 0 <= t - x < 0.3]
                if p:
                    z = 1 + 0.07 * (1 - ease(p[-1] / 0.3))
                    hh, ww = cf.shape[:2]
                    m = np.float32([[z, 0, -(z - 1) * ww / 2], [0, z, -(z - 1) * hh / 2]])
                    cf = cv2.warpAffine(cf, m, (ww, hh))
                tr = vx.trans_at(t) if vx.trans else None
                if tr is not None:
                    before = t < tr.b
                    cf = VX.apply_transition(tr, t, cf, None if before else prev_last,
                                             first_of(tr.scene) if before else None, k)
                if vx.flicker is not None and vx.flicker.at(k):
                    ev, _ = vx.flicker.at(k)
                    nb = starts_k.get(ev.boundary) if ev.boundary is not None else None
                    cf = vx.flicker.apply(cf, k, prev_last, first_of(nb) if nb is not None else None)
                sp = vx.split_at(t) if vx.splits else None
                for other in vx.splits:
                    if other is not sp and other.reader is not None and t >= other.t1:
                        other.reader.close()
                        other.reader = None
                if sp is not None:
                    if sp.reader is None:
                        bw, bh = sp.b_size(cw, ch)
                        sp.reader = read_frames(sp.path, bw, bh, start=sp.b_start, fps=fps, loop=True,
                                                focus_x=sp.b_focus[0], focus_y=sp.b_focus[1])
                    fb = next(sp.reader, None)
                    if fb is not None:
                        sp.last_b = cv2.convertScaleAbs(fb, alpha=1 - sp.b_dim, beta=0) if sp.b_dim > 0.001 else fb
                    cf = VX.compose_split(sp, cf, t, cw, ch, bg, safe_off, vx.split_border)
                elif cf.shape[:2] != (ch, cw):
                    cf = VX.fit_cover(cf, cw, ch)
                if vx.looks is not None:
                    cf = vx.looks.apply(cf, t)
                if vx.letterbox is not None:
                    cf = vx.letterbox.apply(cf, t)
                canvas[lay.center.y:lay.center.y1, :] = cf
                if k in cand:
                    Image.fromarray(last_c).save(cand_dir / f"{k / fps:06.2f}-{cand[k]}.png", compress_level=1)
            if bottom_img is not None and lay.bottom is not None:
                panel = np.asarray(bottom_img(t).convert("RGB")) if callable(bottom_img) else bottom_arr
                canvas[lay.bottom.y:lay.bottom.y1, :] = panel
                if callable(bottom_img) and lay.bottom.y1 < canvas.shape[0]:
                    # v3.6: the strip reserved for platform UI continues the panel colour, no black void under the ad
                    canvas[lay.bottom.y1:, :] = panel[-1:, :, :]
            cta_on = any(o.sprite.kind.startswith("cta") and o.t0 <= t < o.t1 for o in overlays)
            for o in overlays:
                if o.sprite.kind == "label" and cta_on:
                    continue
                _draw_overlay(canvas, o, t)
            if any(0 <= t - x < 2 / fps for x in flashes):
                canvas = cv2.addWeighted(canvas, 0.6, np.full_like(canvas, 255), 0.4, 0)
            if k == 0:
                first = canvas.copy()
            if loop_n and k >= n - loop_n and first is not None:
                a = ease((k - (n - loop_n)) / loop_n)
                canvas = cv2.addWeighted(canvas, 1 - a, first, a, 0)
            assert proc.stdin
            proc.stdin.write(canvas.tobytes())
    finally:
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait()
        center_it.close()
        for sp in vx.splits:
            if sp.reader is not None:
                sp.reader.close()
                sp.reader = None
    if rc != 0:
        raise ShortsError("final ffmpeg encode failed")
    return {"frames": n, "seconds": round(time.time() - t_start, 1)}


def beat_grid(plan: dict, music_path: Path | None, total: float) -> dict:
    """Strong beats in video time when the plan asks for beat-synced cuts (QA `beat_sync` checks them)."""
    music = plan["audio"].get("music") or {}
    if not music.get("beat_sync") or music_path is None:
        return {"enabled": False}
    known = (plan.get("metadata") or {}).get("music") or {}
    start = float(music.get("start", 0))
    if known.get("strong_beats") and abs(float(known.get("start", start)) - start) < 1e-3:
        strong = [float(x) for x in known["strong_beats"] if x <= total + 0.05]
        how = "plan"
    else:
        from ..adapters.film import strong_beats

        b = A.beats(music_path)
        strong = strong_beats(b, start, total)
        how = "measured"
    return {"enabled": True, "strong_beats": strong, "music_start": start, "from": how}


# ---------------------------------------------------------------- 1.3: effects, plates, kinetic captions

TRANS_SFX = {"whip": "whoosh", "zoom": "whoosh", "spin": "whoosh", "flash_blur": "hit", "glitch": "shutter",
             "flicker": "shutter"}


def _split_spec_win(it: dict, t0: float, t1: float, total: float) -> VX.SplitWin:
    mode = it.get("mode", "v2")
    return VX.SplitWin(t0=t0, t1=t1, mode=mode, ratio=float(it.get("ratio", 0.5 if mode != "pip" else 0.0)),
                       gap=int(it.get("gap", 8)), anim=it.get("anim", "slide"),
                       a_pos=it.get("a_pos", "top" if mode != "h2" else "left"),
                       a_focus=tuple(it.get("a_focus", (0.5, 0.42))), b_focus=(0.5, 0.5),
                       b_dim=float(it.get("b_dim", 0.12 if str(it.get("b", "")).startswith("bg:") else 0.0)),
                       pos=it.get("pos", "bl"), path="", b_start=float(it.get("b_start", 0.0)),
                       full=t0 <= 0.01 and t1 >= total - 0.01)


def split_clip_size(plan: dict, lay: L.Layout, total: float, drop: float | None) -> tuple[int, int] | None:
    """A v2/h2 split over the whole video: scenes are captured right at window A's size (sharper, framed)."""
    for it in plan["layout"].get("split") or []:
        t0 = VX.resolve_t(it.get("from", 0), total, drop, 0.0)
        t1 = VX.resolve_t(it.get("to", "end"), total, drop, total)
        if t0 is None or t1 is None:
            continue
        sp = _split_spec_win(it, t0, t1, total)
        if sp.full and sp.mode in ("v2", "h2"):
            a, _ = sp.geometry(lay.center.w, lay.center.h, 1.0)
            return a[2], a[3]
    return None


def build_vfx(plan: dict, live: list[SceneT], lay: L.Layout, total: float, fps: int, drop: float | None,
              plan_dir: Path, clip_size: tuple[int, int] | None) -> VX.State:
    fx = plan.get("fx") or {}
    st = VX.State(clip_size=clip_size)
    cw, ch = lay.center.w, lay.center.h
    if fx.get("letterbox"):
        st.letterbox = VX.Letterbox(fx["letterbox"], cw, ch, total, drop, fps)
        st.notes += st.letterbox.notes
    if fx.get("flicker"):
        st.flicker = VX.Flicker(fx["flicker"], total, drop, fps, [s.start for s in live[1:]])
        st.notes += st.flicker.notes
    if fx.get("look_keys"):
        st.looks = VX.LookKeys(fx["look_keys"], total, drop)
        st.notes += st.looks.notes
    st.trans, notes = VX.plan_transitions(live, fx, drop)
    for tr in st.trans:
        tr.fps = fps
    st.notes += notes
    for it in plan["layout"].get("split") or []:
        t0 = VX.resolve_t(it.get("from", 0), total, drop, 0.0)
        t1 = VX.resolve_t(it.get("to", "end"), total, drop, total)
        if t0 is None or t1 is None or t1 - t0 < 0.5:
            st.notes.append(f"split {it.get('from')}-{it.get('to')} skipped: shorter than 0.5 s or 'drop' without drop_at")
            continue
        sp = _split_spec_win(it, t0, t1, total)
        path, info = resolve_bg(it["b"], plan, plan_dir, t1 - t0 + 1.0)
        if path is None:
            st.notes.append(f"split at {t0:.1f}s skipped: {info.get('error')}")
            continue
        sp.path = str(path)
        sp.b_start = float(it.get("b_start", info.get("start", 0.0)))
        bw, bh = sp.b_size(cw, ch)
        if "b_focus" not in it and "b_start" not in it:
            from .. import bglib as BG

            win = BG.frame_window(path, t1 - t0, bw, bh, sp.b_dim)
            sp.b_focus, sp.b_start = (float(win.get("focus_x", 0.5)), win["focus_y"]), win["start"]
            sp.notes.append(f"window {win['start']}s, focus {sp.b_focus[0]}/{win['focus_y']}, motion min {win.get('change_min')}")
        else:
            focus, rep = _focus(it.get("b_focus", info.get("focus", "motion")), path, bw, bh)
            sp.b_focus = focus
        sp.notes += list(info.get("notes", []))
        if info.get("credit"):
            sp.notes.append(f"credit: {info['credit']}")
        st.splits.append(sp)
    return st


def fit_band(plan: dict, lay: L.Layout, brand: B.Brand, platforms: list[str]) -> tuple[L.Layout, str | None]:
    """band: the title plate lives in the black field above the picture (from the safe top). A plate with a
    sub line may not fit the default 144 px there; without layout.band_y the band moves down to make room."""
    if lay.mode != "band" or plan["layout"].get("band_y") is not None:
        return lay, None
    tb = plan["layout"].get("title_bar")
    bars = [tb] if isinstance(tb, dict) else (tb or [])
    if not bars:
        return lay, None
    top = lay.safe.rect.y + 8
    room = lay.center.y - 12 - top
    need = max(CD.title_bar(it.get("text", ""), brand, lay, it.get("sub", ""), it.get("style", "plate"), top, room).box.h
               for it in bars)
    if need <= room:
        return lay, None
    y0 = min(-(-(top + need + 12) // 8) * 8, L.H - lay.center.h)
    return L.compute({**plan["layout"], "band_y": y0}, platforms), f"band moved down to y={y0}: the title bar needs {need}px"


def seam_y(st: VX.State, lay: L.Layout) -> int | None:
    """Frame y of the seam of a full v2 split (captions sit on it: the eye passes the middle)."""
    sp = next((s for s in st.splits if s.full and s.mode == "v2"), None)
    if sp is None:
        return None
    a, b = sp.geometry(lay.center.w, lay.center.h, 1.0)
    y = (a[1] + a[3] + sp.gap // 2) if sp.a_pos != "bottom" else (b[1] + b[3] + sp.gap // 2)
    return lay.center.y + y


def lift_chunks(chunks: list[C.Chunk], plates: list[tuple[float, float, L.Rect]], seam: int | None,
                lay: L.Layout) -> list[str]:
    """Move caption chunks: centred on the split seam, then out of fact plates / the arrow / CTA cards
    while they are shown. Candidates are the rows just above and just below every obstacle shown at the
    same time; the nearest one that is free of all of them and inside the safe zone wins (no ping-pong
    between two obstacles). A plate at the bottom pushes the chunk up, a centred CTA card up or down."""
    notes = []
    sz = lay.safe.rect
    for c in chunks:
        if seam is not None:
            dy = int(round((c.box[1] + c.box[3]) / 2 - seam))
            c.box = [c.box[0], c.box[1] - dy, c.box[2], c.box[3] - dy]
        live = [r for a, b, r in plates if c.start < b and c.end > a]
        h = c.box[3] - c.box[1]

        def free(top: int) -> bool:
            box = L.Rect(c.box[0], top, c.box[2] - c.box[0], h)
            return not any(box.intersects(r) for r in live)

        if not live or free(c.box[1]):
            continue
        cands = [r.y - 24 - h for r in live] + [r.y1 + 24 for r in live]
        ok = [y for y in cands if sz.y <= y and y + h <= sz.y1 and free(y)]
        if ok:
            y = min(ok, key=lambda v: abs(v - c.box[1]))
            c.box = [c.box[0], y, c.box[2], y + h]
        else:
            notes.append(f"caption '{c.text}' overlaps a plate/CTA at {c.start:.1f}s: no free row in the safe zone")
    return notes


def post_overlays(plan: dict, lay: L.Layout, brand: B.Brand, live: list[SceneT], words: list[dict], total: float,
                  drop: float | None) -> tuple[list[Overlay], list[tuple[float, float]], list[str], list[dict]]:
    """overlays.post -> card overlays, caption spans to hide (the card already shows those words), notes, reports.
    Default span = the scene `scene` (or the first one); text "voice" = the words of the voice in that span."""
    cfg = (plan.get("overlays") or {}).get("post")
    items = [cfg] if isinstance(cfg, dict) else list(cfg or [])   # {} = one card with the defaults
    ovs: list[Overlay] = []
    hide: list[tuple[float, float]] = []
    notes: list[str] = []
    reps: list[dict] = []
    for it in items:
        sc = next((s for s in live if s.id == it.get("scene")), None) if it.get("scene") else (live[0] if live else None)
        if sc is None:
            notes.append(f"post card: scene '{it.get('scene')}' is not in the video, skipped")
            continue
        t0 = VX.resolve_t(it["from"], total, drop, 0.0) if "from" in it else sc.start
        t1 = VX.resolve_t(it["to"], total, drop, total) if "to" in it else sc.start + sc.length
        if t0 is None or t1 is None or t1 - t0 < 1.0:
            notes.append("post card skipped: shorter than 1 s or 'drop' without drop_at")
            continue
        voice = str(it.get("text", "voice")).strip().lower() in ("voice", "say")
        ws = [w for w in words if t0 - 1e-6 <= w["s"] < t1] if voice else []
        if voice and not ws:
            notes.append(f"post card at {t0:.1f}s: no voice words in {t0:.1f}-{t1:.1f}s, the card shows only the title")
        spr, states, rep = CD.post_card(it, ws, t0, brand, lay)
        if spr.note:
            notes.append(spr.note)
        o = Overlay(spr, t0, t1, instant_in=t0 <= 0.001, anim=it.get("anim", "slide_down"))
        o.steps = states
        ovs.append(o)
        hidden = voice and bool(ws) and not it.get("captions", False)
        if hidden:
            hide.append((t0, t1))
        lead = max([max(0.0, float(w["s"]) - st) for w, (st, _) in zip(ws, states[1:])] or [0.0])
        rep.update(t0=round(t0, 3), t1=round(t1, 3), scene=sc.id, captions_hidden=hidden,
                   first_word_s=round(float(ws[0]["s"]), 3) if ws else None, max_early_s=round(lead, 3))
        reps.append(rep)
    return ovs, hide, notes, reps


def plate_overlays(plan: dict, lay: L.Layout, brand: B.Brand, total: float, drop: float | None, lang: str,
                   sfx_auto: bool) -> tuple[list[Overlay], list[tuple[float, str]], list[str]]:
    """title_bar (layout), facts and arrow (overlays) -> overlays, sfx, notes."""
    ovs: list[Overlay] = []
    sfx: list[tuple[float, str]] = []
    notes: list[str] = []
    tb = plan["layout"].get("title_bar")
    for it in ([tb] if isinstance(tb, dict) else (tb or [])):
        t0 = VX.resolve_t(it.get("from", 0), total, drop, 0.0)
        t1 = VX.resolve_t(it.get("to", "end"), total, drop, total)
        if t0 is None or t1 is None:
            notes.append("title bar at 'drop' skipped: audio.music.drop_at is not set")
            continue
        top = max_h = None
        if lay.mode == "band":
            top = lay.safe.rect.y + 8
            max_h = lay.center.y - 12 - top
        spr = CD.title_bar(it["text"], brand, lay, it.get("sub", ""), it.get("style", "plate"), top, max_h)
        if spr.note:
            notes.append(spr.note)
        anim = it.get("anim") or ("none" if t0 <= 0.001 else "slide_down")
        ovs.append(Overlay(spr, t0, t1, instant_in=t0 <= 0.001, anim=anim))
    ov = plan.get("overlays") or {}
    for f in ov.get("facts") or []:
        t = VX.resolve_t(f.get("t", 0), total, drop, 0.0)
        if t is None:
            notes.append(f"fact '{f.get('text', '')[:20]}' at 'drop' skipped: no drop_at")
            continue
        words = len((f.get("text", "") + " " + f.get("sub", "")).split())
        dur = float(f.get("dur", max(2.0, 1.5 * math.ceil(words / 3))))
        spr = CD.fact(f["text"], brand, lay, f.get("sub", ""))
        ovs.append(Overlay(spr, t, min(total, t + dur), anim="slide_left"))
        if sfx_auto:
            sfx.append((max(0.0, t - 0.05), "whoosh"))
    ar = ov.get("arrow")
    if ar:
        cfg = ar if isinstance(ar, dict) else {}
        dur = float(cfg.get("dur", 2.0))
        t = VX.resolve_t(cfg.get("t", -dur), total, drop, max(0.0, total - dur))
        spr = CD.arrow(brand, lay, cfg.get("text"), lang, cfg.get("side", "left"))
        ovs.append(Overlay(spr, t, min(total, t + dur), anim="bob"))
    return ovs, sfx, notes


def place_labels_under_titles(overlays: list[Overlay]) -> None:
    titles = [o for o in overlays if o.sprite.kind == "title_bar"]
    for o in overlays:
        if o.sprite.kind != "label":
            continue
        for tb in titles:
            if o.t0 < tb.t1 and o.t1 > tb.t0 and o.sprite.box.intersects(tb.sprite.box):
                b = o.sprite.box
                o.sprite.box = L.Rect(b.x, tb.sprite.box.y1 + 16, b.w, b.h)


def author_layer_report(plan: dict, live: list[SceneT], top_info: dict, st: VX.State) -> dict:
    """What is foreign in the video and what the author added (research 15, 22: reused content 2026)."""
    foreign = []
    for s in live:
        if s.type in ("film", "video"):
            foreign.append(f"{s.id}: {s.type}" + (f" {s.data['_bg'].get('id')}" if s.data.get("_bg") else ""))
    if (top_info or {}).get("bg"):
        foreign.append(f"top: {top_info['bg'].get('id')}")
    for sp in st.splits:
        foreign.append(f"split: {Path(sp.path).stem}")
    layers = [x.get("kind") for x in plan.get("author_layer") or []]
    auto = []
    if any(s.data.get("say") for s in live):
        auto.append("voice")
    if any((s.data.get("on_screen_text") or "").strip() for s in live) or plan["layout"].get("title_bar"):
        auto.append("text_point")
    # longest stretch where only foreign material plays without the author's voice or text
    single = 0.0
    run = 0.0
    for s in live:
        if s.type in ("film", "video") and not s.data.get("say") and not s.data.get("on_screen_text"):
            run += s.length
            single = max(single, run)
        else:
            run = 0.0
    credits = []
    if (top_info or {}).get("bg", {}).get("credit"):
        credits.append(top_info["bg"]["credit"])
    for s in live:
        if (s.data.get("_bg") or {}).get("credit"):
            credits.append(s.data["_bg"]["credit"])
    for sp in st.splits:
        credits += [n[len("credit: "):] for n in sp.notes if n.startswith("credit: ")]
    kinds = {k for k in set(layers) | set(auto) if k}
    return {"foreign": foreign, "declared": layers, "detected": auto,
            "count": len(kinds), "core": sorted(kinds & set(K.AUTHOR_CORE)), "longest_foreign_only_s": round(single, 2),
            "credits": list(dict.fromkeys(credits))}


# ---------------------------------------------------------------- main entry

def render(plan_path: Path | str, out_dir: Path | str, force: bool = False, keep_work: bool = False) -> dict:
    raw, plan_dir = P.load(plan_path)
    raw, alias_notes = K.normalize(raw)
    if (raw.get("video") or {}).get("format") == "long":
        from .longform import render_long
        return render_long(raw, plan_dir, Path(out_dir), keep_work=keep_work)
    issues = P.check(raw, plan_dir)
    errs = P.errors(issues)
    if errs and not force:
        raise ShortsError("plan has errors:\n" + "\n".join(str(i) for i in errs))
    plan = P.with_defaults(raw)
    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    (out / "graphics").mkdir(exist_ok=True)
    lang = P.lang2(plan)
    fps = int(plan["meta"].get("fps", 30))
    platforms = plan["meta"]["platforms"]
    lay = L.compute(plan["layout"], platforms)
    brand = B.resolve(plan["brand"], plan_dir, lang)
    lay, band_note = fit_band(plan, lay, brand, platforms)
    scenes = [SceneT(s, i) for i, s in enumerate(plan["scenes"])]
    t0 = time.time()
    voice_and_lengths(scenes, plan, lang)
    total = assign_starts(scenes, fps)
    # 2.4: music "auto" (the default when the user named no track) -> a fitting YouTube track, credited in pack
    from .. import music as MU
    music_auto = MU.apply_to_plan(plan, plan_dir, out, total, any(s.speech for s in scenes), lang)
    if music_auto is not None and not music_auto.get("ok"):
        issues.append(P.Issue("warn", "audio.music", MU.summary(music_auto)))
    drop = (plan["audio"].get("music") or {}).get("drop_at")
    drop = float(drop) if drop is not None else None
    clip_size = split_clip_size(plan, lay, total, drop)
    top_info = capture_all(scenes, plan, plan_dir, lay, brand, fps, work, lang, total, size=clip_size)
    if all(s.skipped for s in scenes):
        raise ShortsError("every scene was skipped: " + "; ".join(s.skipped for s in scenes))
    total = assign_starts(scenes, fps)
    live = [s for s in scenes if not s.skipped]
    vx = build_vfx(plan, live, lay, total, fps, drop, plan_dir, clip_size)
    if band_note:
        vx.notes.append(band_note)

    # captions: words now, chunks after the plates (they move around fact plates, CTA and the split seam)
    words: list[dict] = []
    for s in live:
        for w in s.words:
            words.append({"w": w["w"], "s": round(s.start + w["s"], 3), "e": round(s.start + min(w["e"], s.length), 3),
                          "scene": s.id})
    shown = C.apply_subs(words, plan["captions"].get("subs", {}))
    chunks: list[C.Chunk] = []
    ass_path = None
    if shown:
        (out / "captions.srt").write_text(C.to_srt(shown, duration=total), encoding="utf-8")

    # overlays
    overlays: list[Overlay] = []
    for s in live:
        txt = (s.data.get("on_screen_text") or "").strip()
        if txt:
            spr = G.label(txt, brand, lay)
            if spr.note:
                s.notes.append(spr.note)
            if not lay.safe.allows(spr.box):
                s.notes.append(f"on_screen_text '{txt}' is too wide at {spr.min_font}px: shorten it (QA will fail)")
            overlays.append(Overlay(spr, s.start, s.start + s.length, instant_in=s.start == 0))
    bottom = plan["layout"].get("bottom") or {}
    name = plan["meta"]["name"]
    utm = bool(plan.get("metadata", {}).get("utm"))
    events: list[dict] = []
    extra_sfx: list[tuple[float, str]] = []
    cta_list = plan["layout"].get("cta_in_center", [])
    cta_schedule = K.schedule_ctas(cta_list, [(s.id, s.start, s.length) for s in live], total)
    for c, row in zip(cta_list, cta_schedule):
        if row["dropped"]:
            continue
        dur, t_c = row["duration"], row["t"]
        kind = c["kind"]
        if kind == "link":
            spr = G.cta_link(c.get("text") or short_link(c.get("url", "")), brand, lay, c.get("y", "center"),
                             c.get("icon", "telegram" if "t.me/" in (c.get("url", "") + c.get("text", "")) else ""),
                             c.get("caption", ""))
        elif kind == "qr":
            url = with_utm(c["url"], name, platforms[0]) if utm else c["url"]
            spr = G.cta_qr(url, c.get("text") or short_link(c["url"]), brand, lay, c.get("y"))
        elif kind == "handle":
            link = c.get("url") or (bottom.get("links") or [""])[0]
            spr = G.cta_handle(c.get("text") or bottom.get("handle", ""), short_link(link) if link else "", brand, lay, c.get("y"))
        elif kind == "subscribe":
            who = c.get("text") or bottom.get("handle") or name
            spr, after, btn = CD.subscribe(who, brand, lay, lang, c.get("target", "youtube"), c.get("y", "center"))
            click = t_c + min(1.1, dur * 0.5)
            cursor = {"img": CD.cursor_image(64), "from": (min(W - 80, btn.x1 + 180), min(H - 200, btn.y1 + 260)),
                      "to": (btn.x + int(btn.w * 0.55), btn.y + int(btn.h * 0.6)), "t_move": t_c + 0.3, "t_click": click}
            overlays.append(Overlay(spr, t_c, t_c + dur, anim=c.get("anim", "pop_back"), alt=after, alt_at=click,
                                    cursor=cursor))
            extra_sfx.append((click, "click"))
            events.append({"t": t_c, "kind": "cta_subscribe"})
            events.append({"t": click, "kind": "click"})
            continue
        else:
            spr = G.cta_text(c.get("text", ""), brand, lay, c.get("y"))
        overlays.append(Overlay(spr, t_c, t_c + dur, anim=c.get("anim", "slide" if kind == "link" else "pop")))
        events.append({"t": t_c, "kind": f"cta_{kind}"})
    sfx_auto = bool(plan["audio"].get("sfx_auto", False))  # 2.2: off by default, and only real samples play
    plates, plate_sfx, plate_notes = plate_overlays(plan, lay, brand, total, drop, lang, sfx_auto)
    overlays += plates
    extra_sfx += plate_sfx
    vx.notes += plate_notes
    place_labels_under_titles(overlays)
    for o in plates:
        events.append({"t": o.t0, "kind": o.sprite.kind})
    posts, post_hide, post_notes, post_rep = post_overlays(plan, lay, brand, live, shown, total, drop)
    overlays += posts
    vx.notes += post_notes
    for o in posts:
        events.append({"t": o.t0, "kind": "post"})
        if sfx_auto:
            extra_sfx.append((o.t0, "pop"))
    burn = [w for w in shown if not any(a - 1e-6 <= w["s"] < b for a, b in post_hide)] if post_hide else shown

    cap_cfg = dict(plan["captions"])
    cap_style = cap_cfg.get("style", "karaoke")
    kin_blocks: list[KN.KBlock] = []
    if cap_cfg.get("enabled", True) and burn:
        if cap_style == "kinetic":
            obstacles = [(o.t0, o.t1, o.sprite.box) for o in overlays]
            for s in live:  # a text scene draws big words itself: the kinetic block goes around them
                ta = s.data.get("_text_area")
                if ta and s.type == "text":
                    a_rect = VX.split_capture_rect(vx.splits, lay.center.w, lay.center.h) if clip_size else None
                    oy = lay.center.y + (a_rect[1] if a_rect else 0)
                    obstacles.append((s.start, s.start + s.length, L.Rect(0, oy + int(ta[0]), W, int(ta[1] - ta[0]))))
            kin_blocks = KN.build(burn, brand, lay, cap_cfg, lang, obstacles, total)
            for spr, a, b in KN.overlays(kin_blocks):
                overlays.append(Overlay(spr, a, b, anim="kin"))
        else:
            chunks = C.build(burn, brand, lay, cap_cfg, lang)
            lifts = [(o.t0, o.t1, o.sprite.box) for o in overlays
                     if o.sprite.kind in ("fact", "arrow", "post") or o.sprite.kind.startswith("cta")]
            vx.notes += lift_chunks(chunks, lifts, None if cap_cfg.get("y") is not None else seam_y(vx, lay), lay)
            ass_path = out / "captions.ass"
            ass_path.write_text(C.to_ass(chunks, brand, cap_cfg, total), encoding="utf-8")
    bottom_img = None
    if lay.bottom is not None:
        logo = P.resolve_ref(bottom["logo"], plan_dir) if bottom.get("logo") else None
        animation = bottom.get("animation") or {}
        if animation.get("enabled", False):
            from .banner import AnimatedBanner
            bottom_img = AnimatedBanner(lay.bottom.w, lay.bottom.h, brand, bottom, logo)
            bottom_img(0).save(out / "graphics" / "bottom.png")
            write_json(out / "graphics" / "banner.json", bottom_img.manifest())
        else:
            bottom_img = G.bottom_panel(lay.bottom, brand, bottom.get("handle", ""), bottom.get("links", []),
                                        bottom.get("tagline", ""), logo)
            bottom_img.save(out / "graphics" / "bottom.png")
    gi = 0
    for o in overlays:
        if o.sprite.kind == "kinetic":
            continue  # one picture per block below, not one per word
        o.sprite.img.save(out / "graphics" / f"{gi:02d}-{o.sprite.kind}.png")
        gi += 1
        if o.alt is not None:
            o.alt.save(out / "graphics" / f"{gi:02d}-{o.sprite.kind}-after.png")
            gi += 1
        if o.steps:
            o.steps[-1][1].save(out / "graphics" / f"{gi:02d}-{o.sprite.kind}-final.png")
            gi += 1
    for bi, b in enumerate(kin_blocks):
        x0, y0, x1, y1 = b.box
        sheet = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
        for w in b.words:
            sheet.alpha_composite(w.sprite.img, (w.box.x - x0, w.box.y - y0))
        sheet.save(out / "graphics" / f"kinetic-{bi:02d}.png")

    # audio
    sfx: list[tuple[float, str]] = []
    trans_at = {tr.scene: tr for tr in vx.trans}
    for i, s in enumerate(live):
        for e in s.data.get("sfx", []):
            sfx.append((s.start + float(e["t"]), e["name"]))
        if sfx_auto:
            tr = trans_at.get(i)
            if tr is not None:
                if TRANS_SFX.get(tr.kind):  # the move has its own sound, on its start (whoosh) or on the cut (hit)
                    sfx.append((max(0.0, tr.t0 if TRANS_SFX[tr.kind] == "whoosh" else tr.b), TRANS_SFX[tr.kind]))
            elif s.start > 0:
                sfx.append((max(0.0, s.start - 0.12), "whoosh"))
            sfx += [(s.start + c, "click") for c in s.clicks]
    if sfx_auto:
        sfx += [(o.t0, "pop") for o in overlays if o.sprite.kind.startswith("cta")]
        sfx += extra_sfx
        if vx.flicker is not None:
            sfx += [(e.k0 / fps, "shutter") for e in vx.flicker.events]
    music = plan["audio"].get("music") or {}
    music_path = None
    if music.get("source") and music["source"] != "none":
        msrc = music["source"]
        if msrc.startswith(("http://", "https://")):
            from ..adapters.media import download_section

            music_path = download_section(msrc, audio_only=True)
        else:
            music_path = P.resolve_ref(msrc, plan_dir)
            if not music_path:
                raise ShortsError(f"music not found: {msrc}")
    music_sync = beat_grid(plan, music_path, total)
    # 2.2 sound policy: real recordings only (assets/audio/sfx), no synthesized tones; dropped events are reported
    sfx, sfx_rep = A.sfx_policy(sfx, plan["audio"])
    allow_synth = sfx_rep["mode"] == "synth"
    music_synth = A.music_is_synthetic(music.get("source")) or A.music_is_synthetic(music_path)
    sfx_rep["music_synthetic"] = bool(music_synth)
    if music_synth:
        issues.append(P.Issue("warn", "audio.music", "built-in generated track (bed.mp3/edit.mp3) is a placeholder: "
                              "use a real track (trending sound, licensed music) or audio.export without_music"))
    voice_parts = [(s.start, s.speech.wav) for s in live if s.speech]
    src_parts = [(s.start, s.audio) for s in live if s.audio]
    audio_wav = work / "mix.wav"
    export = plan["audio"].get("export", "with_music")
    lufs = float(plan["audio"].get("target_lufs", -14))
    main_music = music_path if export != "without_music" else None
    audio_rep = A.mix(total, voice_parts, src_parts, words, music, main_music, sfx, audio_wav, lufs, allow_synth=allow_synth)
    audio_out = {"export": export, "files": [f"{name}.mp4"]}

    # compose
    out_mp4 = out / f"{name}.mp4"
    comp = compose(out_mp4, scenes, lay, brand, overlays, bottom_img, top_info, total, fps, ass_path, audio_wav,
                   plan.get("fx", {}), bool(plan["meta"].get("loop", True)), out / "cover" / "candidates", vx=vx)
    if music_path is not None and export in ("both", "without_music"):
        cue = {"music": music.get("source"), "start": float(music.get("start", 0)), "offset": float(music.get("offset", 0) or 0),
               "drop_at": music.get("drop_at"), "beats": (music_sync.get("strong_beats") or [])[:64],
               "note": "add the sound in the app (trending audio); the drop and cuts were planned for this track"}
        write_json(out / "music_cue.json", cue)
        audio_out["files"].append("music_cue.json")
    if music_path is not None and export == "both":
        nm_wav = work / "mix.nomusic.wav"
        audio_out["nomusic"] = A.mix(total, voice_parts, src_parts, words, music, None, sfx, nm_wav, lufs,
                                     allow_synth=allow_synth)
        nm = out / f"{name}.nomusic.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_mp4), "-i", str(nm_wav), "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
                        "-movflags", "+faststart", str(nm)], check=True)
        audio_out["files"].append(nm.name)

    for s in live:
        events.append({"t": s.start, "kind": "scene", "id": s.id})
        events += [{"t": s.start + c, "kind": "click"} for c in s.clicks]
    events += [{"t": c.start, "kind": "caption"} for c in chunks]
    events += [{"t": b.start, "kind": "caption"} for b in kin_blocks]
    events += [{"t": w.t0, "kind": "kinetic_word"} for b in kin_blocks for w in b.words[1:]]
    events += [{"t": round(tr.b, 3), "kind": "transition", "name": tr.kind} for tr in vx.trans]
    if vx.letterbox is not None:
        events += [{"t": round(k.t, 3), "kind": "letterbox"} for k in vx.letterbox.keys if k.t > 0]
    if vx.looks is not None:
        events += [{"t": round(k.t, 3), "kind": "look"} for k in vx.looks.keys]
    if vx.flicker is not None:
        events += [{"t": round(e.k0 / fps, 3), "kind": "flicker"} for e in vx.flicker.events]
    events += [{"t": o.t0, "kind": "label"} for o in overlays if o.sprite.kind == "label"]
    events += [{"t": float(x), "kind": "punch"} for x in plan.get("fx", {}).get("punch", [])]
    events.sort(key=lambda e: e["t"])
    manifest = {
        "engine": "shorts", "version": (Path(__file__).resolve().parents[3] / "VERSION").read_text().strip(),
        "name": name, "video": out_mp4.name, "plan_dir": str(plan_dir), "fps": fps, "duration": round(comp["frames"] / fps, 3),
        "language": lang, "platforms": platforms, "duration_target": plan["meta"].get("duration_target"),
        "loop": bool(plan["meta"].get("loop", True)), "layout": lay.to_dict(), "brand": brand.to_dict(),
        "top": top_info, "bottom": {"handle": bottom.get("handle"), "links": bottom.get("links", [])} if lay.bottom else None,
        "scenes": [{"id": s.id, "type": s.type, "start": round(s.start, 4), "length": round(s.length, 4),
                    "skipped": s.skipped, "notes": s.notes, "say": s.data.get("say", ""),
                    "on_screen_text": s.data.get("on_screen_text", ""), "why": s.data.get("why", ""),
                    "speed": s.data.get("speed") or [],
                    "edit": s.data.get("edit") or None, "edit_report": s.data.get("_edit_report"),
                    "source": {k: s.data["source"].get(k) for k in ("type", "ref", "in", "out") if k in s.data["source"]}}
                   for s in scenes],
        "music_sync": music_sync, "music_auto": music_auto, "cta_schedule": cta_schedule, "alias_notes": alias_notes,
        "schema_version": str(raw.get("schema_version", "1")), "pacing": plan["meta"].get("pacing", "dynamic"), "genre": plan["meta"].get("genre"),
        "overlays": [dict(o.sprite.to_dict(), t0=round(o.t0, 3), t1=round(o.t1, 3)) for o in overlays],
        "post": post_rep,
        "captions": {"enabled": bool(chunks or kin_blocks), "style": "kinetic" if kin_blocks else "karaoke",
                     "chunks": ([b.to_chunk() for b in kin_blocks] if kin_blocks else
                                [{"text": c.text, "start": c.start, "end": c.end, "box": c.box,
                                  "size": c.size, "lines": c.lines, "overflow": c.overflow,
                                  "words": c.words} for c in chunks]),
                     "kinetic": KN.report(kin_blocks) if kin_blocks else None,
                     "words_spoken": words, "fill": brand.caption_fill,
                     "accent": KN.fit_contrast(brand.accent, B.CAPTION_OUTLINE, 7.0) if kin_blocks else brand.caption_accent,
                     "outline": brand.caption_outline, "highlight": plan["captions"].get("highlight", "accent"),
                     "anim": plan["captions"].get("anim", "pop")},
        "events": events, "sfx": [{"t": round(t, 3), "name": n} for t, n in sorted(sfx)], "sfx_policy": sfx_rep,
        "audio": audio_rep,
        "fx": plan.get("fx", {}), "effects": brand.effects, "issues": [str(i) for i in issues],
        "vfx": vx.report(total), "audio_export": audio_out,
        "author_layer": author_layer_report(plan, live, top_info, vx),
        "render_seconds": round(time.time() - t0, 1), "forced": bool(errs and force),
    }
    write_json(out / "manifest.json", manifest)
    write_json(out / "plan.resolved.json", plan)
    if music_auto is not None:     # pack reads the credit from here
        write_json(out_mp4.with_suffix(".music.json"), music_auto)
    elif isinstance(plan["audio"].get("music"), dict) and plan["audio"]["music"].get("credit"):
        write_json(out_mp4.with_suffix(".music.json"), {"ok": True, "status": "given", "credit": plan["audio"]["music"]["credit"],
                                                        "file": str(plan["audio"]["music"].get("source") or "")})
    K.write_render_output(out, manifest, str(raw.get("schema_version", "1")))
    if not keep_work:
        shutil.rmtree(work, ignore_errors=True)
    log.info("rendered %s (%.1fs video) in %.0fs", out_mp4, total, time.time() - t0)
    return manifest
