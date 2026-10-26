"""Adapters `text` and `images`: frames drawn in Python (no browser).

text:   kinetic typography in brand fonts, words appear in sync with the voice; *word* = accent.
        Optional `images` behind the text (user screenshots or project frames), darkened.
images: user screenshots in motion (slow zoom and pan towards `focus`), optional fake cursor clicks
        (`points`: [[x, y, t], ...] in 0..1 image coords and scene seconds).
"""
from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..engine.clips import ClipWriter, cover_resize
from ..plan import resolve_ref
from ..util import ShortsError, ease, hex_to_rgb, snap8
from .site import Capture


def _load(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise ShortsError(f"cannot read image {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def _ken_burns(img: np.ndarray, w: int, h: int, k: float, focus=(0.5, 0.5), zoom=(1.0, 1.12)) -> np.ndarray:
    base = cover_resize(img, int(w * zoom[1]) + 2, int(h * zoom[1]) + 2, focus[0], focus[1])
    z = zoom[0] + (zoom[1] - zoom[0]) * ease(k)
    cw, ch = int(w * zoom[1] / z), int(h * zoom[1] / z)
    bh, bw = base.shape[:2]
    x0 = int((bw - cw) * focus[0])
    y0 = int((bh - ch) * focus[1])
    crop = base[y0:y0 + ch, x0:x0 + cw]
    return cv2.resize(crop, (w, h), interpolation=cv2.INTER_AREA)


def images_capture(scene: dict, w: int, h: int, fps: int, out_len: float, work: Path, plan_dir: Path | None,
                   accent: str) -> Capture:
    src = scene["source"]
    refs = list(src.get("images") or ([src["ref"]] if src.get("ref") else []))
    if not refs:
        raise ShortsError(f"scene {scene['id']}: images adapter needs images or ref")
    paths = []
    for r in refs:
        p = resolve_ref(r, plan_dir)
        if not p:
            raise ShortsError(f"image not found: {r}")
        paths.append(p)
    imgs = [_load(p) for p in paths]
    focus = tuple(src.get("focus", (0.5, 0.4)))
    points = src.get("points") or []
    n = max(1, int(round(out_len * fps)))
    per = n / len(imgs)
    out = work / f"center-{scene['id']}.mp4"
    wr = ClipWriter(out, w, h, fps)
    clicks = []
    acc = hex_to_rgb(accent)
    for k in range(n):
        i = min(len(imgs) - 1, int(k / per))
        local = (k - i * per) / per
        frame = _ken_burns(imgs[i], w, h, local, focus).copy()
        t = k / fps
        for (px, py, pt) in points:
            dt = t - float(pt)
            if 0 <= dt < 0.5:
                r = int(28 + 40 * ease(dt / 0.5))
                a = 1 - dt / 0.5
                over = frame.copy()
                cv2.circle(over, (int(px * w), int(py * h)), r, acc, 4, cv2.LINE_AA)
                frame = cv2.addWeighted(over, a, frame, 1 - a, 0)
        wr.write(frame)
    wr.close()
    clicks = [float(p[2]) for p in points if float(p[2]) < out_len]
    return Capture(out, clicks)


def _tokens(text: str) -> list[tuple[str, bool]]:
    out = []
    for t in text.split():
        acc = t.startswith("*") and t.rstrip(".,!?:;").endswith("*")
        out.append((t.replace("*", ""), acc))
    return out


def split_phrases(text: str) -> list[str]:
    """Phrases for kinetic type: split on '|', newlines, '->' and sentence ends."""
    parts = re.split(r"\s*\|\s*|\n+|\s+(?=->)|(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _layout_phrase(toks, font_path: str, maxw: int, maxh: int, start: int = 240, minimum: int = 72):
    size = start
    while True:
        f = ImageFont.truetype(font_path, size)
        lines, cur = [], []
        for tok in toks:
            trial = " ".join(x for x, _ in cur + [tok])
            if f.getlength(trial) > maxw and cur:
                lines.append(cur)
                cur = [tok]
            else:
                cur.append(tok)
        if cur:
            lines.append(cur)
        asc, desc = f.getmetrics()
        lh = int((asc + desc) * 1.0)
        fits = len(lines) * lh <= maxh and all(f.getlength(" ".join(x for x, _ in ln)) <= maxw for ln in lines)
        if fits or size <= minimum:
            return f, lines, lh, size
        size -= 8


def text_capture(scene: dict, w: int, h: int, fps: int, out_len: float, work: Path, plan_dir: Path | None,
                 brand, words: list[dict], free: tuple[int, int] | None = None) -> Capture:
    """Kinetic type. Each phrase fills the free area; background alternates brand bg / a shade of it per phrase,
    so the centre changes every phrase (no dead air). `free` = (y0, y1) inside the clip kept clear of captions/labels."""
    src = scene["source"]
    text = src.get("ref") or scene.get("on_screen_text") or scene.get("say", "")
    if brand.upper:
        text = text.upper()
    phrases = split_phrases(text)
    if not phrases:
        raise ShortsError(f"scene {scene['id']}: text adapter has no text")
    bg_imgs = [_load(p) for p in (resolve_ref(r, plan_dir) for r in src.get("images") or []) if p]
    y0, y1 = free or (0, h)
    margin = 72
    maxw, maxh = w - 2 * margin, max(160, y1 - y0 - 64)
    bg, fg, ac = hex_to_rgb(brand.bg), hex_to_rgb(brand.fg), hex_to_rgb(brand.accent)
    # second background = a shade of bg towards fg (not a new colour); captions stay readable on both
    surface = tuple(int(bg[c] + (fg[c] - bg[c]) * 0.12) for c in range(3))
    # phrase timing: follow voice words when the counts allow it, else equal slices
    n_ph = len(phrases)
    starts = [i * out_len / n_ph for i in range(n_ph)]
    if words:
        tok_counts = [len(_tokens(p)) for p in phrases]
        total_toks = sum(tok_counts)
        if total_toks:
            acc_t, k = [], 0
            for c in tok_counts:
                idx = min(len(words) - 1, int(k / total_toks * len(words)))
                acc_t.append(words[idx]["s"] if k else 0.0)
                k += c
            starts = acc_t
    layouts = [_layout_phrase(_tokens(p), str(brand.display.path), maxw, maxh) for p in phrases]
    out = work / f"center-{scene['id']}.mp4"
    wr = ClipWriter(out, w, h, fps)
    n = max(1, int(round(out_len * fps)))
    for k in range(n):
        t = k / fps
        pi = max(i for i, s in enumerate(starts) if s <= t + 1e-6)
        base_col = surface if (pi % 2 == 1 and not bg_imgs) else bg
        if bg_imgs:
            im = _ken_burns(bg_imgs[min(len(bg_imgs) - 1, pi % len(bg_imgs))], w, h, t / out_len)
            im = (im.astype(np.float32) * 0.35 + np.array(bg, np.float32) * 0.65).astype(np.uint8)
            img = Image.fromarray(im)
        else:
            img = Image.new("RGB", (w, h), base_col)
        d = ImageDraw.Draw(img)
        f, lines, lh, size = layouts[pi]
        block_h = len(lines) * lh
        top = snap8(y0 + (y1 - y0 - block_h) / 2)
        local = t - starts[pi]
        flat = [tok for ln in lines for tok in ln]
        per = min(0.18, 0.6 / max(1, len(flat)))
        idx = 0
        for li, ln in enumerate(lines):
            line_w = f.getlength(" ".join(x for x, _ in ln))
            x = (w - line_w) / 2
            y = top + li * lh
            for tok, marked in ln:
                p = ease((local - idx * per) / 0.2) if local >= idx * per else 0.0
                idx += 1
                if p > 0:
                    col = ac if marked else fg
                    colp = tuple(int(base_col[c] + (col[c] - base_col[c]) * p) for c in range(3))
                    d.text((x, y + snap8((1 - p) * 24)), tok, font=f, fill=colp)
                x += f.getlength(tok + " ")
        wr.write(np.asarray(img))
    wr.close()
    return Capture(out, notes=[f"kinetic text: {n_ph} phrases"])


def strip_marks(text: str) -> str:
    return re.sub(r"\*", "", text or "")
