"""Covers (COMMON.md 8, research 2.1/2.2/7, design-rules, viora-v8/refs/ref-4).

TEXT IS ALWAYS DRAWN BY CODE with the brand font. Three variants with DIFFERENT ideas, each 1280x720 and 1080x1920:
  A "minimal": black, one line-art symbol for the topic (lock, key, browser, chess, gear, play, code, chart, chip),
               big white caps, lots of air, the only accent is a small part of the symbol
  B "hero":    one hero object large (model image without text if OPENAI/GEMINI key, else the best frame,
               cropped on its mass) + ONE accent: the plate under the text
  C "split":   two moments side by side (before / after), one accent divider, text on a flat black band;
               with one frame only: "outline" (darkened frame, big outlined text)
Checks per cover: 3-5 words, readable at 320 px, contrast >= 4.5:1 around the real glyphs, squint test
(grey + blur at 320 px: subject and text still separate shapes), no gradient, no glow, not in the time-stamp
corner (16:9) / inside the safe zone (9:16), and the three variants must differ (dhash).
Tones (2.0): B hero = loud (shock, big caps hook), C split = medium (before/after contrast), A minimal = calm
(informative, soft). Each tone has its own 3-5 word text (metadata.json cover_texts, else derived from the hook/topic).
If no generator: DIR/cover/prompt.md has one ready prompt per variant (and the covers are still made).
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ..engine import brand as B
from ..engine.graphics import plate_colors
from ..engine.layout import safe_zone
from ..util import contrast, fit_contrast, hex_to_rgb, log, read_json, rgb_to_hex, write_json
from ..qa import frames as F
from .symbols import draw_symbol, symbol_for
from .tones import TONES, derive_cover_texts, normalize_cover_texts

SIZES = {"16x9": (1280, 720), "9x16": (1080, 1920)}
TONE_OF_LETTER = {"A": "calm", "B": "loud", "C": "medium"}
TONE_MOOD = {
    "loud": "Dramatic and tense: the main object exaggerated in scale, strongest contrast, one shocking but honest detail.",
    "medium": "Curious and clear: a visible before/after difference, bold but not aggressive.",
    "calm": "Quiet and informative: soft, plenty of air, one simple idea, nothing shouting.",
}


# ---------------------------------------------------------------- generator detection (names only, never values)

def generator() -> str | None:
    forced = os.environ.get("SHORTS_IMAGE_PROVIDER")
    if forced in ("none", "off"):
        return None
    if forced:
        return forced
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return None


def _post(url: str, payload: dict, headers: dict) -> dict:
    from ..costs import require_paid_approval
    require_paid_approval('image', 1, url.split("/")[2] if "//" in url else url)
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
        return json.loads(r.read())


def generate_image(prompt: str, out: Path, provider: str, landscape: bool = True) -> Path:
    """Not verified in CI (needs a key). Image only, no text in the prompt result."""
    if provider == "openai":
        data = _post("https://api.openai.com/v1/images/generations",
                     {"model": os.environ.get("SHORTS_OPENAI_IMAGE_MODEL", "gpt-image-1"), "prompt": prompt,
                      "size": "1536x1024" if landscape else "1024x1536", "n": 1},
                     {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
        out.write_bytes(base64.b64decode(data["data"][0]["b64_json"]))
    elif provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
        model = os.environ.get("SHORTS_GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
        data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                     {"contents": [{"parts": [{"text": prompt}]}]}, {"x-goog-api-key": key})
        parts = data["candidates"][0]["content"]["parts"]
        img = next(p for p in parts if "inlineData" in p or "inline_data" in p)
        blob = img.get("inlineData") or img.get("inline_data")
        out.write_bytes(base64.b64decode(blob["data"]))
    else:
        raise ValueError(f"unknown image provider {provider}")
    return out


def prompt_text(manifest: dict, plan: dict, words: str, lang: str, symbol: str = "gear",
                texts: dict[str, str] | None = None) -> str:
    br = manifest["brand"]
    pal = br["palette"]
    topic = (plan.get("metadata") or {}).get("topic") or words
    emotion = plan["meta"].get("emotion") or br.get("emotion_default", "trust")
    ru = lang == "ru"
    ban = ("Do NOT draw: any text or letters, logos, neon glow, light leaks, purple-blue gradients, bokeh orbs, "
           "lens flares, cinematic teal-orange grading, sparkles, emoji, faces of real people, busy collage.")
    texts = texts or {}

    def head(letter: str, name: str) -> list[str]:
        tone = TONE_OF_LETTER[letter]
        t = texts.get(letter)
        note = (f"Тон: {tone}. Текст на обложке (рисует код): {t}" if ru else f"Tone: {tone}. Cover text (drawn by code): {t}") if t \
            else (f"Тон: {tone}." if ru else f"Tone: {tone}.")
        return [f"## {letter} {name} ({tone})", note, "```"]

    lines = [
        ("# Промпты для обложек" if ru else "# Cover prompts"), "",
        ("Картинки БЕЗ ТЕКСТА: текст наложит код. Вариант A (минимал) код рисует сам, промпт на случай своей картинки."
         if ru else "Images WITH NO TEXT: code adds the text. Variant A is drawn by code; the prompt is for your own image."), "",
        *head("A", "minimal"),
        f"A single {symbol} drawn as thin white line art, centred, on a pure black background. One small detail in {pal['accent']}.",
        "Huge negative space, nothing else in the frame. Flat, no shading. " + TONE_MOOD["calm"] + " " + ban, "```", "",
        *head("B", "hero"),
        hero_prompt(topic, pal, emotion, "loud"), "```", "",
        *head("C", "split"),
        f"Two halves of one scene about \"{topic}\": left = before (plain, grey), right = after (the result, vivid).",
        f"Hard vertical cut in the middle, flat colours, background {pal['bg']}, one accent {pal['accent']}. " + TONE_MOOD["medium"] + " " + ban, "```", "",
        "Formats: 1280x720 (16:9) and 1080x1920 (9:16) with the subject above the middle.", "",
        ("Готовую картинку дай мне файлом, я запущу: `python3 tools/shorts.py cover DIR --image файл.png`"
         if ru else "Send the image back and run: `python3 tools/shorts.py cover DIR --image file.png`"),
    ]
    return "\n".join(lines) + "\n"


def hero_prompt(topic: str, pal: dict, emotion: str, tone: str = "") -> str:
    return (TONE_MOOD.get(tone, "") + (" " if tone in TONE_MOOD else "") +f"One hero object that stands for \"{topic}\", large, clear silhouette, honest to the video content. "
            "Hero on the right third, the left third calm and dark for a headline, lots of negative space. "
            f"Background {pal['bg']}, main {pal['fg']}, ONE accent {pal['accent']}. Flat colour, high contrast, "
            f"at most 3 colours. Mood: {emotion}. Minimal editorial product photo or clean 3D render. "
            "Do NOT draw any text or letters, logos, glow, gradients, lens flares, sparkles, emoji, real faces.")


# ---------------------------------------------------------------- composition helpers

def _cover_fit(img: np.ndarray, w: int, h: int, fx: float = 0.5, fy: float = 0.5) -> np.ndarray:
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    r = cv2.resize(img, (max(w, int(iw * s + 0.5)), max(h, int(ih * s + 0.5))), interpolation=cv2.INTER_AREA)
    x0 = int((r.shape[1] - w) * fx)
    y0 = int((r.shape[0] - h) * fy)
    return r[y0:y0 + h, x0:x0 + w]


def saliency_x(img: np.ndarray) -> float:
    """Horizontal centre of visual mass (edges), 0..1."""
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    e = cv2.Canny(g, 80, 160).astype(np.float32)
    col = e.sum(axis=0)
    if col.sum() < 1:
        return 0.5
    return float((col * np.arange(len(col))).sum() / col.sum() / len(col))


def pick_frames(cand_dir: Path, k: int = 3, skip_ids: set[str] | None = None, ranked: bool = False) -> list[Path]:
    """Sharp, contrasty, not blank. One per scene, best first. Text-card scenes are skipped (text over text)."""
    scored = []
    for p in sorted(cand_dir.glob("*.png")):
        if skip_ids and p.stem.split("-", 1)[-1] in skip_ids:
            continue
        img = np.asarray(Image.open(p).convert("RGB"))
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        sharp = cv2.Laplacian(g, cv2.CV_64F).var()
        sil = float(cv2.GaussianBlur(g, (0, 0), 8).std())  # figure/ground survives blur = good cover
        scored.append((sil >= 25, sil * 2 + float(g.std()) + min(sharp, 2000) / 40, p))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if ranked:  # every candidate once, best first (spares for a cover that failed the squint test)
        return [p for _, _, p in scored]
    good = [p for ok, _, p in scored if ok] or [p for _, _, p in scored]
    return [good[i % len(good)] for i in range(k)] if good else []


def _font(path, size):
    return ImageFont.truetype(str(path), size)


def _wrap(words: list[str], font, maxw: int) -> list[list[str]]:
    lines, cur = [], []
    for w in words:
        if cur and font.getlength(" ".join(cur + [w])) > maxw:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines


# Floors target at least 7 px cap height at 150 px; semantic readability still needs agent review.
FLOOR_9x16 = 72


def _fit(words: list[str], font_path, maxw: int, maxh: int, start: int, minimum: int, floor: int | None = None):
    size = start
    while size > minimum:
        f = _font(font_path, size)
        lines = _wrap(words, f, maxw)
        lh = int(size * 1.08)
        if len(lines) <= 3 and len(lines) * lh <= maxh and all(f.getlength(" ".join(ln)) <= maxw for ln in lines):
            return f, lines, size, lh
        size -= 6
    # a long word (БЕСПЛАТНО) may not fit at the preferred minimum: go smaller rather than spill out of the
    # safe zone; check_cover still fails it if it gets unreadable at 320 px
    for size in range(minimum, (floor or minimum) - 1, -4):
        f = _font(font_path, size)
        lines = _wrap(words, f, maxw)
        if len(lines) <= 3 and all(f.getlength(" ".join(ln)) <= maxw for ln in lines):
            return f, lines, size, int(size * 1.08)
    f = _font(font_path, minimum)
    return f, _wrap(words, f, maxw), minimum, int(minimum * 1.08)


def _draw_text(img: Image.Image, lines, font, lh: int, x: int, y: int, fg, accent_word: int, accent, stroke=0,
               stroke_col=None) -> list[int]:
    d = ImageDraw.Draw(img)
    k = 0
    x1 = x
    for li, ln in enumerate(lines):
        cx = x
        for w in ln:
            col = accent if k == accent_word else fg
            d.text((cx, y + li * lh), w, font=font, fill=col, stroke_width=stroke, stroke_fill=stroke_col)
            cx += font.getlength(w + " ")
            k += 1
        x1 = max(x1, int(cx - font.getlength(" ")))
    return [x, y, x1, y + len(lines) * lh]


BLACK = (10, 10, 10)
WHITE = (255, 255, 255)


def _text_mask(size: tuple[int, int], lines, font, lh: int, x: int, y: int, stroke: int = 0) -> np.ndarray:
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for li, ln in enumerate(lines):
        d.text((x, y + li * lh), " ".join(ln), font=font, fill=255, stroke_width=stroke, stroke_fill=255)
    return np.asarray(m) > 127


def _clear_of_exclusions(area: tuple[int, int, int, int], platforms: list[str]) -> tuple[int, int, int, int]:
    """Shrink a text area (x0, y0, x1, y1) so it does not touch platform UI columns (TikTok action buttons)."""
    x0, y0, x1, y1 = area
    for ex in safe_zone(platforms).exclusions:
        if ex.y < y1 and ex.y1 > y0 and ex.x < x1 and ex.x1 > x0:
            if ex.x > x0 + (x1 - x0) // 2:      # column on the right: stop before it
                x1 = min(x1, ex.x - 8)
            elif ex.x1 < x1:                     # on the left: start after it
                x0 = max(x0, ex.x1 + 8)
            else:                                # spans the area: keep the text above it
                y1 = min(y1, ex.y - 8)
    return x0, y0, x1, y1


def _accent_index(words: list[str]) -> int:
    return max(range(len(words)), key=lambda i: len(words[i])) if words else 0


def _readable_on(bg: tuple[int, int, int], brand: B.Brand) -> tuple[int, int, int]:
    hexbg = rgb_to_hex(bg)
    return WHITE if contrast("#FFFFFF", hexbg) >= contrast("#0A0A0A", hexbg) else BLACK


def _minimal(words, brand: B.Brand, fmt: str, platforms: list[str], symbol: str):
    W, H = SIZES[fmt]
    canvas = Image.new("RGB", (W, H), BLACK)
    ac = hex_to_rgb(brand.accent)
    if contrast(brand.accent, rgb_to_hex(BLACK)) < 3.0:  # accent must read on black
        ac = hex_to_rgb(fit_contrast(brand.accent, rgb_to_hex(BLACK), 3.0))
    if fmt == "16x9":
        side = int(H * 0.62)
        sym_xy = (int(W * 0.60), int(H * 0.10))
        area = (80, int(H * 0.52), int(W * 0.62), H - 70)
        start, minimum = 150, 86
    else:
        sz = safe_zone(platforms).rect
        side = int(min(sz.w * 0.8, sz.h * 0.5))
        sym_xy = (sz.x + (sz.w - side) // 2, sz.y + int(sz.h * 0.06))
        area = _clear_of_exclusions((sz.x + 24, sz.y + int(sz.h * 0.56), sz.x1 - 24, sz.y1 - 16), platforms)
        start, minimum = 170, 96
    stroke = max(10, side // 30)
    sym = draw_symbol(symbol, side, stroke, WHITE, ac)
    canvas.paste(sym, sym_xy, sym)
    maxw, maxh = area[2] - area[0], area[3] - area[1]
    f, lines, size, lh = _fit(words, brand.display.path, maxw, maxh, start, minimum, FLOOR_9x16 if fmt == "9x16" else None)
    y = area[3] - len(lines) * lh  # text sits low, symbol high: air between
    box = _draw_text(canvas, lines, f, lh, area[0], y, WHITE, -1, ac)
    mask = _text_mask((W, H), lines, f, lh, area[0], y)
    sym_box = [sym_xy[0], sym_xy[1], sym_xy[0] + side, sym_xy[1] + side]
    return canvas, {"box": box, "font_px": size, "text_color": "#FFFFFF", "symbol": symbol, "symbol_box": sym_box,
                    "idea": "symbol", "graphic_boxes": [[0, 0, W, H]]}, mask


def _hero(bg_img, words, brand: B.Brand, fmt: str, platforms: list[str]):
    W, H = SIZES[fmt]
    sx = saliency_x(bg_img)
    text_left = sx >= 0.5
    ih, iw = bg_img.shape[:2]
    # zoom up to 1.2 on the visual mass (the object is the hero), never upscale a small frame for it
    z = max(1.0, min(1.2, iw / W, ih / H))
    zw, zh = int(iw / z), int(ih / z)
    x0 = int(min(max(0, sx * iw - zw / 2), iw - zw))
    crop = bg_img[(ih - zh) // 2:(ih - zh) // 2 + zh, x0:x0 + zw]
    canvas = Image.fromarray(_cover_fit(crop, W, H, sx if fmt == "9x16" else 0.5, 0.45))
    if fmt == "16x9":
        area = (64, 64, W // 2 - 16, H - 96) if text_left else (W // 2 + 16, 64, W - 64, H - 120)
        start, minimum = 132, 86
    else:
        sz = safe_zone(platforms).rect
        area = _clear_of_exclusions((sz.x + 40, sz.y + 40, sz.x1 - 40, sz.y + int(sz.h * 0.5)), platforms)
        start, minimum = 150, 96
    maxw, maxh = area[2] - area[0], area[3] - area[1]
    f, lines, size, lh = _fit(words, brand.display.path, maxw - 48, maxh - 48, start, minimum, FLOOR_9x16 if fmt == "9x16" else None)
    tw = max(int(f.getlength(" ".join(ln))) for ln in lines)
    th = len(lines) * lh
    px, py = area[0] + 24, area[1] + (maxh - th) // 2
    txt_hex, plate_hex = plate_colors(brand.accent, "#0A0A0A", "#FFFFFF")  # same 7:1 plate rule as video labels
    ac, on_acc = hex_to_rgb(plate_hex), hex_to_rgb(txt_hex)
    mask = _text_mask((W, H), lines, f, lh, px, py)
    ys, xs = np.nonzero(mask)
    pad = max(16, size // 6)
    plate = [int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad, int(ys.max()) + pad] if len(xs) else \
        [px - 24, py - 16, px + tw + 24, py + th + 8]
    ImageDraw.Draw(canvas).rectangle(plate, fill=ac)
    box = _draw_text(canvas, lines, f, lh, px, py, on_acc, -1, ac)
    return canvas, {"box": box, "font_px": size, "text_color": rgb_to_hex(on_acc), "text_left": text_left,
                    "idea": "hero", "graphic_boxes": [plate]}, mask


def _split(a_img, b_img, words, brand: B.Brand, fmt: str, platforms: list[str], solid: bool = False):
    """Two frames, one band with the text. solid=True: the band is the accent plate (7:1 text) - for busy
    frames where white caps on black do not survive the squint test."""
    W, H = SIZES[fmt]
    ac = hex_to_rgb(brand.accent)
    band_col, txt_col = BLACK, WHITE
    if solid:
        t_hex, p_hex = plate_colors(brand.accent, "#0A0A0A", "#FFFFFF", prefer_light=True)
        band_col, txt_col = hex_to_rgb(p_hex), hex_to_rgb(t_hex)
    bar = 10
    if fmt == "16x9":
        band_h = int(H * 0.30)
        top_h = H - band_h
        canvas = Image.new("RGB", (W, H), BLACK)
        canvas.paste(Image.fromarray(_cover_fit(a_img, W // 2, top_h, saliency_x(a_img), 0.45)), (0, 0))
        canvas.paste(Image.fromarray(_cover_fit(b_img, W - W // 2, top_h, saliency_x(b_img), 0.45)), (W // 2, 0))
        ImageDraw.Draw(canvas).rectangle([W // 2 - bar // 2, 0, W // 2 + bar // 2, top_h], fill=ac)
        if solid:
            ImageDraw.Draw(canvas).rectangle([0, top_h, W, H], fill=band_col)
        area = (64, top_h + 12, W - 260, H - 16)
        gboxes = [[0, top_h, W, H]]
        start, minimum = 120, 86
    else:
        sz = safe_zone(platforms).rect
        canvas = Image.new("RGB", (W, H), BLACK)
        half = H // 2
        canvas.paste(Image.fromarray(_cover_fit(a_img, W, half, saliency_x(a_img), 0.45)), (0, 0))
        canvas.paste(Image.fromarray(_cover_fit(b_img, W, H - half, saliency_x(b_img), 0.45)), (0, half))
        band = (0, sz.y + int(sz.h * 0.30), W, sz.y + int(sz.h * 0.70))
        ImageDraw.Draw(canvas).rectangle(band, fill=band_col)
        if not solid:
            ImageDraw.Draw(canvas).rectangle([0, band[1] - bar, W, band[1]], fill=ac)
        area = _clear_of_exclusions((sz.x + 24, band[1] + 24, sz.x1 - 24, band[3] - 24), platforms)
        gboxes = [list(band)]
        start, minimum = 150, 96
    maxw, maxh = area[2] - area[0], area[3] - area[1]
    f, lines, size, lh = _fit(words, brand.display.path, maxw, maxh, start, minimum, FLOOR_9x16 if fmt == "9x16" else None)
    y = area[1] + (maxh - len(lines) * lh) // 2
    acc_txt = ac if contrast(rgb_to_hex(ac), rgb_to_hex(BLACK)) >= 4.5 else WHITE
    if solid:
        acc_txt = txt_col
    box = _draw_text(canvas, lines, f, lh, area[0], y, txt_col, _accent_index(words), acc_txt)
    mask = _text_mask((W, H), lines, f, lh, area[0], y)
    return canvas, {"box": box, "font_px": size, "text_color": rgb_to_hex(txt_col), "idea": "split", "solid_band": solid,
                    "graphic_boxes": gboxes}, mask


def _outline(bg_img, words, brand: B.Brand, fmt: str, platforms: list[str]):
    W, H = SIZES[fmt]
    im = _cover_fit(bg_img, W, H, 0.5, 0.45).astype(np.float32)
    k = min(0.55, 70.0 / max(1.0, float(im.mean())))  # flat dim (no gradient) so white text reads on bright frames
    im = (im * k + np.array(BLACK, np.float32) * (1 - k)).astype(np.uint8)
    canvas = Image.fromarray(im)
    if fmt == "16x9":
        area = (64, 64, W - 64, H - 110)
        start, minimum = 150, 86
    else:
        sz = safe_zone(platforms).rect
        area = _clear_of_exclusions((sz.x + 24, sz.y + 24, sz.x1 - 24, sz.y + int(sz.h * 0.6)), platforms)
        start, minimum = 160, 96
    maxw, maxh = area[2] - area[0], area[3] - area[1]
    f, lines, size, lh = _fit(words, brand.display.path, maxw, maxh, start, minimum, FLOOR_9x16 if fmt == "9x16" else None)
    y = area[1] + (maxh - len(lines) * lh) // 2
    stroke = max(4, size // 18)
    ac = hex_to_rgb(brand.accent)
    box = _draw_text(canvas, lines, f, lh, area[0], y, WHITE, _accent_index(words), ac, stroke=stroke, stroke_col=(0, 0, 0))
    mask = _text_mask((W, H), lines, f, lh, area[0], y)
    return canvas, {"box": box, "font_px": size, "text_color": "#FFFFFF", "idea": "outline",
                    "graphic_boxes": []}, mask


def compose_cover(bg_img: np.ndarray, words: list[str], brand: B.Brand, variant: str, fmt: str, platforms: list[str],
                  second: np.ndarray | None = None, symbol: str = "gear"):
    """Returns (image, info, text_mask). variant: minimal | hero | split | outline (punch = hero, old name)."""
    if variant == "minimal":
        return _minimal(words, brand, fmt, platforms, symbol)
    if variant in ("hero", "punch"):
        return _hero(bg_img, words, brand, fmt, platforms)
    if variant in ("split", "split_band") and second is not None:
        return _split(bg_img, second, words, brand, fmt, platforms, solid=variant == "split_band")
    return _outline(bg_img, words, brand, fmt, platforms)


# ---------------------------------------------------------------- checks

def squint(img: Image.Image) -> dict:
    """Squint test: grey, 320 px wide, blur like a glance. The figure must survive as a separate shape:
    foreground (Otsu minority) 2-55% of the area, one connected blob >= 1.5%, contrast of the two tones >= 3:1."""
    small = np.asarray(img.convert("L").resize((320, max(1, int(320 * img.height / img.width))), Image.BILINEAR))
    g = cv2.GaussianBlur(small, (0, 0), 2.5)
    thr, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg = bw > 0
    if fg.mean() > 0.5:
        fg = ~fg
    share = float(fg.mean())
    lo = float(g[~fg].mean()) if (~fg).any() else 0.0
    hi = float(g[fg].mean()) if fg.any() else 0.0
    def rl(v):
        c = v / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    a, b = rl(max(lo, hi)), rl(min(lo, hi))
    tone = (a + 0.05) / (b + 0.05)
    closed = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))  # letters -> word
    n, lab, stats, _ = cv2.connectedComponentsWithStats(closed, 8)
    blob = float(stats[1:, cv2.CC_STAT_AREA].max() / fg.size) if n > 1 else 0.0
    ok = 0.02 <= share <= 0.55 and blob >= 0.015 and tone >= 3.0
    return {"ok": bool(ok), "share": round(share, 3), "blob": round(blob, 3), "tone": round(tone, 1)}


def glow_around(arr: np.ndarray, mask: np.ndarray) -> float:
    """Luma lift of the 3-12 px ring around the glyphs vs the 16-32 px ring. Flat background ~0, a glow halo 25+."""
    if not mask.any():
        return 0.0
    m = mask.astype(np.uint8)
    d3 = cv2.dilate(m, np.ones((7, 7), np.uint8))
    d12 = cv2.dilate(m, np.ones((25, 25), np.uint8))
    d16 = cv2.dilate(m, np.ones((33, 33), np.uint8))
    d32 = cv2.dilate(m, np.ones((65, 65), np.uint8))
    g = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
    near = (d12 > 0) & (d3 == 0)
    far = (d32 > 0) & (d16 == 0)
    if not near.any() or not far.any():
        return 0.0
    text_l = float(g[mask].mean())
    sign = 1.0 if text_l >= float(g[far].mean()) else -1.0
    return sign * (float(np.median(g[near])) - float(np.median(g[far])))


def check_cover(img: Image.Image, info: dict, words: list[str], fmt: str, platforms: list[str],
                mask: np.ndarray | None = None) -> list[str]:
    errs = []
    W, H = img.size
    if not 3 <= len(words) <= 5:
        errs.append(f"{len(words)} words (need 3-5)")
    cap_px = info["font_px"] * 0.7 * 320 / W  # readable at 320 px wide: cap height >= 14 px
    if cap_px < 14:
        errs.append(f"text too small at 320 px ({cap_px:.0f}px cap height)")
    cap_150 = info["font_px"] * 0.7 * 150 / W
    if cap_150 < 7:
        errs.append(f"text too small at 150 px ({cap_150:.0f}px cap height); visual review required")
    x0, y0, x1, y1 = info["box"]
    arr = np.asarray(img.convert("RGB"))
    if mask is not None and mask.any():
        m = mask.astype(np.uint8)
        ring = (cv2.dilate(m, np.ones((9, 9), np.uint8)) > 0) & (cv2.dilate(m, np.ones((3, 3), np.uint8)) == 0)
        if ring.any():
            bgm = tuple(int(v) for v in np.median(arr[ring], axis=0))
            ratio = contrast(info["text_color"], bgm)
            if ratio < 4.5:
                errs.append(f"text contrast {ratio:.1f}:1 < 4.5:1")
        lift = glow_around(arr, mask)
        info["glow_lift"] = round(lift, 1)
        if lift > 18:
            errs.append(f"glow around text (+{lift:.0f} luma in the halo ring)")
    if fmt == "16x9":
        if x1 > W - 220 and y1 > H - 90:
            errs.append("text in the time-stamp corner")
    else:
        sz = safe_zone(platforms)
        from ..engine.layout import Rect

        if not sz.allows(Rect.from_xyxy(x0, y0, x1, y1), tol=8):
            errs.append("text outside the safe zone")
    # gradients are checked on what the code drew (plates, bands, backgrounds), not on film/photo pixels
    for gb in info.get("graphic_boxes", [[0, 0, W, H]]):
        gx0, gy0, gx1, gy1 = (max(0, int(v)) for v in gb)
        crop = arr[gy0:min(H, gy1), gx0:min(W, gx1)]
        if crop.shape[0] >= 160 or crop.shape[1] >= 160:
            if F.gradient_score(crop, min_run=10, block=16)["gradient"]:
                errs.append(f"gradient detected in {gb}")
                break
    sq = squint(img)
    info["squint"] = sq
    if not sq["ok"]:
        errs.append(f"weak silhouette at 320 px (figure {sq['share']:.0%}, blob {sq['blob']:.1%}, tone {sq['tone']}:1)")
    return errs


def ideas_differ(images: list[Image.Image], min_bits: int = 40) -> list[str]:
    """Three variants must look different, not three crops of one idea (dhash 16x16, bits)."""
    hs = [F.dhash(np.asarray(i.convert("RGB").resize((320, int(320 * i.height / i.width))))) for i in images]
    errs = []
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            dist = F.hamming(hs[i], hs[j])
            if dist < min_bits:
                errs.append(f"variants {chr(65 + i)} and {chr(65 + j)} look alike (dhash {dist} bits < {min_bits})")
    return errs


def native_frame(manifest: dict, name: str) -> np.ndarray | None:
    """The same moment taken from the source film/video at its own resolution and aspect (sharper than the
    vertical render for 16:9 covers). None if the scene is not a local film/video or the file is gone."""
    from ..plan import resolve_ref

    try:
        t_s, sid = name.split(":", 1)[1].split("-", 1)
        t = float(t_s)
    except ValueError:
        return None
    sc = next((x for x in manifest["scenes"] if x["id"] == sid), None)
    src = (sc or {}).get("source") or {}
    if src.get("type") not in ("film", "video") or not src.get("ref"):
        return None
    p = resolve_ref(src["ref"], Path(manifest["plan_dir"]) if manifest.get("plan_dir") else None)
    if not p:
        return None
    st = float(src.get("in") or 0) + max(0.0, t - sc["start"])
    if src.get("out") is not None:
        st = min(st, float(src["out"]) - 0.05)
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{st:.3f}", "-i", str(p), "-frames:v", "1", "-f", "image2pipe",
           "-vcodec", "png", "-"]
    import io
    import subprocess

    r = subprocess.run(cmd, capture_output=True)
    if r.returncode or not r.stdout:
        return None
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB"))


def _tone_texts(text: str | None, meta: dict, words_s: str, plan: dict, manifest: dict, lang: str,
                upper: bool) -> dict[str, str]:
    """tone -> cover text. An explicit --text is used for all three; else metadata cover_texts, else derived from the hook."""
    if text:
        return {t: words_s for t in TONES}
    have = {x["tone"]: x["text"] for x in normalize_cover_texts(meta.get("cover_texts"))}
    if len(have) < 3:
        topic = (plan.get("metadata") or {}).get("topic") or manifest.get("name", "")
        derived = {x["tone"]: x["text"] for x in derive_cover_texts(words_s, topic, lang, upper)}
        derived["loud"] = words_s
        have = {**derived, **have}
    return {t: (have[t].upper() if upper else have[t]) for t in TONES}


def cover_dir(d: Path, image: str | None = None, text: str | None = None, generate: bool = True) -> dict:
    manifest = read_json(d / "manifest.json")
    plan = read_json(d / "plan.resolved.json")
    if manifest.get("format") == "long":
        from ..engine.longform import cover_long
        return cover_long(d, image=image, text=text)
    lang = manifest.get("language", "ru")
    brand = B.resolve(plan["brand"], None, lang)
    meta = read_json(d / "metadata.json") if (d / "metadata.json").exists() else {}
    words_s = text or meta.get("cover_text") or (plan.get("metadata") or {}).get("cover_text") or \
        next((s.get("on_screen_text") for s in plan["scenes"] if s.get("on_screen_text")), "") or manifest["name"]
    words_s = words_s.upper() if brand.upper else words_s
    words = words_s.split()[:5]
    tone_texts = _tone_texts(text, meta, words_s, plan, manifest, lang, brand.upper)
    texts = {letter: tone_texts[tone] for letter, tone in TONE_OF_LETTER.items()}
    topic = " ".join([(plan.get("metadata") or {}).get("topic") or "", words_s, manifest.get("name", "")])
    symbol = (plan.get("metadata") or {}).get("cover_symbol") or \
        symbol_for(topic, [sc["type"] for sc in manifest["scenes"]])
    out = d / "cover"
    out.mkdir(exist_ok=True)
    prov = generator()
    notes = []
    hero_src: tuple[str, np.ndarray] | None = None
    frames: list[tuple[str, np.ndarray]] = []
    if image:
        hero_src = ("user", np.asarray(Image.open(image).convert("RGB")))
    elif prov and generate:
        try:
            pal = manifest["brand"]["palette"]
            p = generate_image(hero_prompt(topic.strip(), pal, plan["meta"].get("emotion") or "trust", "loud"),
                               out / "generated.png", prov)
            hero_src = (f"model:{prov}", np.asarray(Image.open(p).convert("RGB")))
            notes.append(f"hero image generated by {prov} (no text), text drawn by code")
        except Exception as e:  # report and fall back to frames
            notes.append(f"image generator {prov} failed: {str(e)[:120]}")
            log.warning("image generation failed: %s", e)
    text_ids = {sc["id"] for sc in manifest["scenes"] if sc["type"] == "text"}
    frames = [(f"frame:{p.stem}", np.asarray(Image.open(p).convert("RGB")))
              for p in dict.fromkeys(pick_frames(out / "candidates", k=3, skip_ids=text_ids))]
    frames = [(n, nf if (nf := native_frame(manifest, n)) is not None else img) for n, img in frames]
    if not frames:
        frames = [("first", F.frame_at(d / manifest["video"], 0))]
    used = {n for n, _ in frames}
    spare = [(f"frame:{p.stem}", np.asarray(Image.open(p).convert("RGB")))
             for p in pick_frames(out / "candidates", skip_ids=text_ids, ranked=True) if f"frame:{p.stem}" not in used]
    if hero_src is None:
        hero_src = frames[0]
    pool = [f for f in frames if f[0] != hero_src[0]]
    split_pair = (pool[0], pool[1]) if len(pool) >= 2 else ((pool[0], hero_src) if pool else None)
    (out / "prompt.md").write_text(prompt_text(manifest, plan, words_s, lang, symbol, texts), encoding="utf-8")
    plan_v = [("A", "minimal", hero_src, None),
              ("B", "hero", hero_src, None),
              ("C", "split" if split_pair else "outline", split_pair[0] if split_pair else hero_src,
               split_pair[1][1] if split_pair else None)]
    variants, by_fmt = [], {f: [] for f in SIZES}
    for letter, v0, (src_name, src), second in plan_v:
        wv = texts[letter].split()[:5]
        for fmt in SIZES:
            v = v0
            img, info, mask = compose_cover(src, wv, brand, v, fmt, manifest["platforms"], second=second, symbol=symbol)
            errs = check_cover(img, info, wv, fmt, manifest["platforms"], mask)
            if letter == "B" and not hero_src[0].startswith(("model", "user")) and any("weak silhouette" in e for e in errs):
                for name2, a2 in [x for x in frames + spare if x[0] != src_name][:6]:
                    img2, info2, mask2 = compose_cover(a2, wv, brand, "hero", fmt, manifest["platforms"])
                    errs2 = check_cover(img2, info2, wv, fmt, manifest["platforms"], mask2)
                    if not errs2 and not ideas_differ(by_fmt[fmt] + [img2]):
                        notes.append(f"B {fmt}: {src_name} failed the squint test ({'; '.join(errs)}), used {name2}")
                        img, info, mask, errs = img2, info2, mask2, errs2
                        break
            if letter == "C" and any("weak silhouette" in e for e in errs):
                # busy frames hide the text at a glance: try other frame pairs, then one dimmed frame (outline)
                tries = [("split", x[1], y[1]) for x in frames + spare for y in frames + spare if x[0] != y[0]]
                tries += [("outline", x[1], None) for x in frames + spare]
                tries += [("split_band", src, second)] if second is not None else []
                for v2, a2, b2 in tries[:12] + tries[-1:]:
                    img2, info2, mask2 = compose_cover(a2, wv, brand, v2, fmt, manifest["platforms"], second=b2,
                                                       symbol=symbol)
                    errs2 = check_cover(img2, info2, wv, fmt, manifest["platforms"], mask2)
                    if not errs2 and not ideas_differ(by_fmt[fmt] + [img2]):
                        notes.append(f"C {fmt}: first frames failed the squint test ({'; '.join(errs)}), "
                                     f"used other frames ({v2})")
                        img, info, mask, errs, v = img2, info2, mask2, errs2, v2.replace("split_band", "split")
                        break
            p = out / f"cover-{letter}-{v}-{fmt}.jpg"
            img.save(p, quality=92)
            img.resize((320, int(320 * img.height / img.width))).save(out / f"cover-{letter}-{v}-{fmt}-320.png")
            img.resize((150, max(1, int(150 * img.height / img.width)))).save(out / f"cover-{letter}-{v}-{fmt}-150.png")
            by_fmt[fmt].append(img)
            variants.append({"file": p.name, "variant": v, "format": fmt,
                             "source": "code:symbol" if v == "minimal" else src_name, "errors": errs,
                             "tone": TONE_OF_LETTER[letter], "text": texts[letter], "mobile_review": "manual", **info})
    differ = [f"{fmt}: {e}" for fmt, imgs in by_fmt.items() for e in ideas_differ(imgs)]
    res = {"generator": prov, "generated": hero_src[0].startswith("model"), "words": words, "symbol": symbol,
           "ideas": [v[1] for v in plan_v], "tones": dict(TONE_OF_LETTER), "texts": texts, "recommended": B.REGISTER_COVER.get(brand.register, "A"),
           "register": brand.register, "variants": variants, "prompt": "cover/prompt.md", "notes": notes,
           "errors": [f"{x['file']}: {e}" for x in variants for e in x["errors"]] + differ}
    if not res["generated"] and not image:
        res["ask_user"] = ("Генератора картинок нет или он выключен: вариант A нарисован кодом, B и C из кадров ролика. "
                           "Если нужна картинка от нейросети, сгенерируй по cover/prompt.md и пришли файл." if lang == "ru" else
                           "No image generator: A is drawn by code, B and C use frames. For a model image, use cover/prompt.md and send the file.")
    write_json(out / "cover.json", res)
    from .user_package import refresh_if_exists
    refresh_if_exists(d)
    return res
