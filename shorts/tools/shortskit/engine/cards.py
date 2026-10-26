"""Plates drawn by code for schema 1.3 (research 14, sections 2, 8, 9.1, 9.4). Same rules as graphics.py:
real brand fonts, flat colours, outline instead of glow, contrast >= 7:1 for text, 8 px grid, no emoji.

  title_bar   topic plate for the whole video ("ЦЕНА ПРИЗНАНИЯ"), styles plate / outline / underline
  fact        lower third: 1-2 lines on a black plate + accent bar, slides in from the left (Starikov)
  subscribe   "channel + SUBSCRIBE" card, a cursor clicks it, the button turns into "SUBSCRIBED" (9.1)
  arrow       arrow down to the Related video link / profile in the last 2 s (9.4)
  post_card   Reddit / Telegram / comment card that writes itself while the voice reads it (9.2, layout C)
"""
from __future__ import annotations

import re

from PIL import Image, ImageDraw, ImageFont

from ..util import contrast, fit_contrast, hex_to_rgb
from .brand import Brand
from .graphics import Sprite, _fit_text, _text_layer, _wrap, plate_colors
from .layout import Layout, Rect

TITLE_EM, TITLE_MIN = 80, 56
TITLE_MAX_CHARS = 28
FACT_EM, FACT_MIN = 56, 48
SUB_EM = 40


def _font(path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _ink(text: str, font: ImageFont.FreeTypeFont, fill, stroke=None, stroke_w: int = 0) -> Image.Image:
    """Text cropped to its glyph box (+ stroke): optical centring inside plates."""
    bb = font.getbbox(text, stroke_width=stroke_w)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    img = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((-bb[0], -bb[1]), text, font=font, fill=fill, stroke_width=stroke_w,
                             stroke_fill=stroke if stroke else None)
    return img


def _title_colours(brand: Brand) -> tuple[str, str]:
    """White plate with dark text (kinobust look) when it reaches 7:1, else the brand plate colours."""
    if contrast(brand.fg, brand.bg) >= 7:
        return brand.bg, brand.fg
    return plate_colors(brand.accent, brand.bg, brand.fg)


def _title_body(lines: list[str], f: ImageFont.FreeTypeFont, size: int, style: str, brand: Brand):
    pad_x, pad_y = 48, 20
    asc, desc = f.getmetrics()
    lh = int(size * 0.92)
    tw = int(max(f.getlength(ln) for ln in lines))
    stroke = brand.bg if contrast(brand.fg, brand.bg) > 3 else "#000000"
    if style == "plate":
        txt_col, plate = _title_colours(brand)
        body = Image.new("RGBA", (tw + 2 * pad_x, lh * len(lines) + 2 * pad_y), hex_to_rgb(plate) + (255,))
        d = ImageDraw.Draw(body)
        hb = f.getbbox("H")
        cap_h = hb[3] - hb[1]
        for i, ln in enumerate(lines):
            bb = f.getbbox(ln)
            x = (body.width - (bb[2] - bb[0])) // 2 - bb[0]
            y = pad_y + i * lh + (lh - cap_h) // 2 - hb[1]
            d.text((x, y), ln, font=f, fill=hex_to_rgb(txt_col) + (255,))
        return body, [(txt_col, plate, 7.0)], stroke
    layer = _text_layer(lines, f, brand.fg, stroke, 3, tw + 8, line_gap=int(size * 1.04) - (asc + desc))
    if style == "outline":
        body = Image.new("RGBA", (layer.width + 2 * pad_x, layer.height + 2 * pad_y), (0, 0, 0, 0))
        ImageDraw.Draw(body).rectangle([0, 0, body.width - 1, body.height - 1], outline=hex_to_rgb(brand.fg) + (255,),
                                       width=max(4, brand.line_width))
        body.alpha_composite(layer, (pad_x, pad_y))
        return body, [(brand.fg, stroke, 7.0)], stroke
    # underline: text + accent line under it
    bar = 8
    body = Image.new("RGBA", (layer.width, layer.height + 12 + bar), (0, 0, 0, 0))
    body.alpha_composite(layer, (0, 0))
    acc = hex_to_rgb(fit_contrast(brand.accent, brand.bg, 3.0))
    ImageDraw.Draw(body).rectangle([0, layer.height + 12, body.width - 1, layer.height + 12 + bar - 1], fill=acc + (255,))
    return body, [(brand.fg, stroke, 7.0)], stroke


def title_bar(text: str, brand: Brand, lay: Layout, sub: str = "", style: str = "plate",
              top: int | None = None, max_h: int | None = None) -> Sprite:
    """Topic plate for the whole video. top / max_h: the room it must fit (band mode: the black field above the
    picture); it drops to one line and smaller letters (>= 56 px) before it overlaps the picture."""
    t = text.upper() if brand.upper else text
    box = lay.label_box
    maxw = box.w - 2 * 48
    note = ""
    if len(t) > TITLE_MAX_CHARS:
        note = f"title bar '{t}' has {len(t)} chars (> {TITLE_MAX_CHARS}): shorten it to 2-5 words"
    sub_h = 0
    if sub:
        fs = _font(brand.body.path, SUB_EM)
        sub_h = 16 + (fs.getbbox(sub)[3] - fs.getbbox(sub)[1]) + 6
    f, lines, size = _fit_text(t, brand.display.path, TITLE_EM, TITLE_MIN, maxw, 2)
    body, pairs, stroke = _title_body(lines, f, size, style, brand)
    if max_h is not None and body.height + sub_h > max_h:
        for sz in range(size, TITLE_MIN - 1, -4):
            f1 = _font(brand.display.path, sz)
            if f1.getlength(t) <= maxw:
                b1, p1, s1 = _title_body([t], f1, sz, style, brand)
                if b1.height + sub_h <= max_h or sz <= TITLE_MIN + 3:
                    f, lines, size, body, pairs, stroke = f1, [t], sz, b1, p1, s1
                    break
        if body.height + sub_h > max_h:
            note = (note + "; " if note else "") + f"title bar is {body.height + sub_h}px, room {max_h}px: it overlaps the picture"
    min_font = size
    if sub:
        fs = _font(brand.body.path, SUB_EM)
        s_img = _ink(sub, fs, hex_to_rgb(brand.fg) + (255,), hex_to_rgb(stroke) + (255,), 3)
        both = Image.new("RGBA", (max(body.width, s_img.width), body.height + 16 + s_img.height), (0, 0, 0, 0))
        both.alpha_composite(body, ((both.width - body.width) // 2, 0))
        both.alpha_composite(s_img, ((both.width - s_img.width) // 2, body.height + 16))
        body = both
        pairs.append((brand.fg, stroke, 7.0))
        min_font = min(size, SUB_EM)
    x = int(round(box.x + box.w / 2 - body.width / 2))
    y = box.y if top is None else int(top)
    if max_h is not None and top is not None and body.height < max_h:
        y = int(top + (max_h - body.height) // 2)   # centred in its field
    return Sprite("title_bar", body, Rect(x, y, body.width, body.height), t, min_font, pairs, note=note)


def fact(text: str, brand: Brand, lay: Layout, sub: str = "", bottom: int | None = None) -> Sprite:
    """Lower third over the Shorts UI zone: x from the safe left edge, bottom on `bottom` (default safe bottom - 8).
    Lines sit on one baseline grid (anchor "ls"), so descenders (Р, у, g) never shift a line."""
    s = lay.safe.rect
    pad_x, pad_y = 28, 18
    maxw = min(s.w, 840) - 2 * pad_x
    f, lines, size = _fit_text(text, brand.display.path, FACT_EM, FACT_MIN, maxw, 2)
    plate = "#000000"
    txt = brand.fg if contrast(brand.fg, plate) >= 7 else "#FFFFFF"
    cap_top = f.getbbox("H", anchor="ls")[1]  # negative: cap height above the baseline
    cap_h = -cap_top
    desc = f.getmetrics()[1]
    lh = int(round(cap_h * 1.6))
    fs = _font(brand.body.path, SUB_EM) if sub else None
    widths = [f.getlength(ln) for ln in lines] + ([fs.getlength(sub)] if fs else [])
    w = int(max(widths)) + 2 * pad_x
    sub_h = (-fs.getbbox("Hy", anchor="ls")[1] + fs.getmetrics()[1]) if fs else 0
    text_h = cap_h + lh * (len(lines) - 1) + int(desc * 0.6)
    h = pad_y * 2 + text_h + ((sub_h + 12) if fs else 0)
    bar = 8
    img = Image.new("RGBA", (w, h + bar), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], fill=hex_to_rgb(plate) + (235,))
    base = pad_y + cap_h
    for i, ln in enumerate(lines):
        d.text((pad_x, base + i * lh), ln, font=f, fill=hex_to_rgb(txt) + (255,), anchor="ls")
    if fs:
        sb = pad_y + text_h + 12 - fs.getbbox("Hy", anchor="ls")[1]
        d.text((pad_x, sb), sub, font=fs, fill=hex_to_rgb(txt) + (215,), anchor="ls")
    acc = hex_to_rgb(fit_contrast(brand.accent, "#000000", 3.0))
    d.rectangle([0, h, w - 1, h + bar - 1], fill=acc + (255,))
    y1 = (bottom if bottom is not None else s.y1 - 8)
    r = Rect(s.x, int(y1 - img.height), img.width, img.height)
    pairs = [(txt, plate, 7.0)]
    return Sprite("fact", img, r, text + (f" | {sub}" if sub else ""), min(size, SUB_EM) if sub else size, pairs)


# ------------------------------------------------------------------ subscribe card with a cursor (9.1)

SUB_TEXT = {"ru": ("ПОДПИСАТЬСЯ", "ВЫ ПОДПИСАНЫ"), "en": ("SUBSCRIBE", "SUBSCRIBED")}


def _bell(size: int, color) -> Image.Image:
    k = 4
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.pieslice([s * 0.18, s * 0.08, s * 0.82, s * 0.78], 180, 360, fill=color)
    d.rectangle([s * 0.18, s * 0.42, s * 0.82, s * 0.70], fill=color)
    d.polygon([(s * 0.08, s * 0.80), (s * 0.92, s * 0.80), (s * 0.82, s * 0.66), (s * 0.18, s * 0.66)], fill=color)
    d.ellipse([s * 0.40, s * 0.80, s * 0.60, s * 0.96], fill=color)
    return im.resize((size, size), Image.LANCZOS)


def _plane(size: int, color) -> Image.Image:
    from .graphics import _plane as plane

    return plane(size, color[:3])


SUB_MIN_PX = 44  # QA: overlay text >= 40 px; the card copies the platform button, it must read on a phone


def subscribe(name: str, brand: Brand, lay: Layout, lang: str = "ru", target: str = "youtube",
              y: float | str | None = "center") -> tuple[Sprite, Image.Image, Rect]:
    """(sprite before the click, image after the click, button box in frame px)."""
    before_t, after_t = SUB_TEXT.get(lang, SUB_TEXT["en"])
    plate = "#FFFFFF"
    ink = "#0F0F0F"
    acc = brand.accent
    btn_txt = "#FFFFFF" if contrast("#FFFFFF", acc) >= contrast("#000000", acc) else "#000000"
    if contrast(btn_txt, acc) < 4.5:
        _, acc = plate_colors(brand.accent, "#000000", "#FFFFFF", target=4.5)
    done_bg, done_txt = "#E5E5E5", "#0F0F0F"
    maxw = lay.cta_box.w - 16
    pad = 28
    av = 104
    fn = _font(brand.display.path, 56)
    label = name
    while fn.getlength(label) > maxw - 2 * pad - av - 24 and fn.size > SUB_MIN_PX:
        fn = _font(brand.display.path, fn.size - 4)
    fb = _font(brand.display.path, SUB_MIN_PX)
    while fb.getlength(max(before_t, after_t, key=len)) > maxw - 2 * pad - av - 24 - 44 - 16 - 56 and fb.size > 40:
        fb = _font(brand.display.path, fb.size - 2)

    def button(text: str, bg: str, fg: str) -> Image.Image:
        icon = 44
        ti = _ink(text, fb, hex_to_rgb(fg) + (255,))
        w = ti.width + icon + 16 + 2 * 28
        h = 84
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=hex_to_rgb(bg) + (255,))
        ic = _bell(icon, hex_to_rgb(fg) + (255,)) if target != "telegram" else _plane(icon, hex_to_rgb(fg) + (255,))
        im.alpha_composite(ic, (28, (h - icon) // 2))
        im.alpha_composite(ti, (28 + icon + 16, (h - ti.height) // 2))
        return im

    b1, b2 = button(before_t, acc, btn_txt), button(after_t, done_bg, done_txt)
    name_img = _ink(label, fn, hex_to_rgb(ink) + (255,))
    inner_w = max(name_img.width, b1.width, b2.width)
    w = pad + av + 24 + inner_w + pad
    h = pad + max(av, name_img.height + 16 + b1.height) + pad

    def card(btn: Image.Image) -> Image.Image:
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=24, fill=hex_to_rgb(plate) + (255,))
        d.ellipse([pad, (h - av) // 2, pad + av, (h - av) // 2 + av], fill=hex_to_rgb(acc) + (255,))
        letter = (label.lstrip("@")[:1] or "V").upper()
        fl = _font(brand.display.path, 56)
        li = _ink(letter, fl, hex_to_rgb(btn_txt) + (255,))
        im.alpha_composite(li, (pad + (av - li.width) // 2, (h - av) // 2 + (av - li.height) // 2))
        x = pad + av + 24
        top = (h - (name_img.height + 16 + btn.height)) // 2
        im.alpha_composite(name_img, (x, top))
        im.alpha_composite(btn, (x, top + name_img.height + 16))
        return im

    a, b = card(b1), card(b2)
    from .graphics import _place_cta

    r = _place_cta(a, lay, y)
    x_btn = pad + av + 24
    top = (h - (name_img.height + 16 + b1.height)) // 2
    btn_box = Rect(r.x + x_btn, r.y + top + name_img.height + 16, b1.width, b1.height)
    pairs = [(ink, plate, 7.0), (btn_txt, acc, 4.5), (done_txt, done_bg, 7.0)]
    spr = Sprite("cta_subscribe", a, r, f"{label} {before_t}", min(fn.size, fb.size), pairs, url=label)
    if fn.getlength(label) > maxw - 2 * pad - av - 24:
        spr.note = f"channel name '{label}' is too long for the subscribe card at {fn.size}px: shorten it"
    return spr, b, btn_box


def cursor_image(size: int = 64) -> Image.Image:
    """Classic arrow pointer: white with a black outline (reads on any picture), tip at (0, 0)."""
    k = 4
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pts = [(0.06, 0.04), (0.06, 0.80), (0.26, 0.62), (0.40, 0.94), (0.52, 0.89), (0.38, 0.58), (0.64, 0.58)]
    poly = [(x * s, y * s) for x, y in pts]
    d.polygon(poly, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=int(0.045 * s))
    return im.resize((size, size), Image.LANCZOS)


# ------------------------------------------------------------------ arrow down (9.4)

ARROW_TEXT = {"ru": "ССЫЛКА НИЖЕ", "en": "LINK BELOW"}


def arrow(brand: Brand, lay: Layout, text: str | None = None, lang: str = "ru", side: str = "left") -> Sprite:
    t = ARROW_TEXT.get(lang, ARROW_TEXT["en"]) if text is None else text
    t = t.upper() if brand.upper else t
    stroke = "#000000"
    fg = "#FFFFFF" if contrast("#FFFFFF", stroke) >= contrast(brand.fg, stroke) else brand.fg
    k = 4
    aw, ah = 96, 128
    big = Image.new("RGBA", (aw * k, ah * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    shaft = [(0.36, 0.0), (0.64, 0.0), (0.64, 0.56), (0.92, 0.56), (0.5, 1.0), (0.08, 0.56), (0.36, 0.56)]
    pts = [(x * (aw - 12) * k + 6 * k, y * (ah - 12) * k + 6 * k) for x, y in shaft]
    d.polygon(pts, fill=hex_to_rgb(fg) + (255,), outline=hex_to_rgb(stroke) + (255,), width=6 * k)
    ar = big.resize((aw, ah), Image.LANCZOS)
    parts = [ar]
    if t:
        ft = _font(brand.display.path, 44)
        parts.insert(0, _ink(t, ft, hex_to_rgb(fg) + (255,), hex_to_rgb(stroke) + (255,), 4))
    w = max(p.width for p in parts)
    h = sum(p.height for p in parts) + 12 * (len(parts) - 1)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    y = 0
    for p in parts:
        img.alpha_composite(p, ((w - p.width) // 2 if p is not ar else (0 if side == "left" else w - p.width), y))
        y += p.height + 12
    s = lay.safe.rect
    x = s.x + 8 if side == "left" else int(round(540 - w / 2))
    r = Rect(x, s.y1 - 8 - h, w, h)
    return Sprite("arrow", img, r, t, 44 if t else 0, [(fg, stroke, 7.0)] if t else [])


# ------------------------------------------------------------------ post card over a background (9.2, layout C)

POST_AVATAR = {"reddit": "#FF4500", "telegram": "#2AABEE"}       # comment: brand accent
POST_THEMES = {"light": ("#FFFFFF", "#1A1A1B", "#4F5559"), "dark": ("#1A1A1B", "#F2F3F5", "#B9BDC0")}
POST_BODY_EM, POST_BODY_MIN = 48, 42   # QA: overlay text >= 40 px
POST_TITLE_EM, POST_TITLE_MIN = 56, 44
POST_META_PX = 40
POST_MAX_H = 640                       # research 17, layout C: the card lives in the top third (y 300-800, up to 940)
POST_PAD, POST_AV = 32, 84


def post_y(lay: Layout, y=None) -> int:
    """Top of the card: research 17 puts it at y 300 (just under the Shorts top bar); below a top panel or band."""
    if y is not None:
        return int(y)
    return max(300, lay.safe.rect.y + 12, (lay.center.y + 24) if lay.center.y > 0 else 0)


def _clip(text: str, font: ImageFont.FreeTypeFont, maxw: int) -> str:
    """One line: cut with an ellipsis when it does not fit."""
    if not text or font.getlength(text) <= maxw:
        return text
    while text and font.getlength(text + "…") > maxw:
        text = text[:-1]
    return text.rstrip() + "…"


def _icon_up(size: int, color) -> Image.Image:
    k = 4
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(s * 0.5, s * 0.08), (s * 0.92, s * 0.52), (s * 0.66, s * 0.52), (s * 0.66, s * 0.92),
               (s * 0.34, s * 0.92), (s * 0.34, s * 0.52), (s * 0.08, s * 0.52)], fill=color)
    return im.resize((size, size), Image.LANCZOS)


def _icon_bubble(size: int, color) -> Image.Image:
    k = 4
    s = size * k
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([s * 0.06, s * 0.10, s * 0.94, s * 0.72], radius=int(s * 0.18), fill=color)
    d.polygon([(s * 0.22, s * 0.66), (s * 0.46, s * 0.66), (s * 0.18, s * 0.94)], fill=color)
    return im.resize((size, size), Image.LANCZOS)


def post_card(cfg: dict, words: list[dict], t0: float, brand: Brand, lay: Layout,
              ) -> tuple[Sprite, list[tuple[float, Image.Image]], dict]:
    """Reddit / Telegram / comment card that writes itself while the voice reads it (research 14.9.2, 17 layout C).

    cfg: kind (reddit | telegram | comment), name, where, title, text ("voice" = the words of the voice, or a string),
         stats ("12,4k 873": votes and comments), theme (light | dark), y (top px).
    words: the voice words in video time ({"w", "s"}) for text "voice". A word shows up exactly at its start
    (never before the sound). Returns (sprite of the first state, [(time, image)] states, report).
    All states share one canvas (the card grows down, transparent below), so the overlay box never moves."""
    kind = cfg.get("kind", "reddit")
    plate, ink, meta_c = POST_THEMES.get(cfg.get("theme", "light"), POST_THEMES["light"])
    av_c = POST_AVATAR.get(kind) or brand.accent
    av_txt = "#FFFFFF" if contrast("#FFFFFF", av_c) >= contrast("#000000", av_c) else "#000000"
    s = lay.safe.rect
    w = s.w
    y = post_y(lay, cfg.get("y"))
    max_h = max(240, min(POST_MAX_H, s.y1 - 8 - y))
    inner = w - 2 * POST_PAD
    notes: list[str] = []
    # header: avatar + name + where
    name = str(cfg.get("name") or ("u/anonymous" if kind == "reddit" else "anonymous"))
    where = str(cfg.get("where") or "")
    fn = _font(brand.display.path, POST_META_PX)
    fm = _font(brand.body.path, POST_META_PX)
    text_x = POST_PAD + POST_AV + 20
    name_w = inner - POST_AV - 20
    name, where = _clip(name, fn, name_w), _clip(where, fm, name_w)
    name_img = _ink(name, fn, hex_to_rgb(ink) + (255,))
    where_img = _ink(where, fm, hex_to_rgb(meta_c) + (255,)) if where else None
    head_h = max(POST_AV, name_img.height + ((12 + where_img.height) if where_img else 0))
    # title (static, bold)
    title = str(cfg.get("title") or "").strip()
    t_lines, ft, t_size, t_lh = [], None, 0, 0
    if title:
        ft, t_lines, t_size = _fit_text(title, brand.display.path, POST_TITLE_EM, POST_TITLE_MIN, inner, 3)
        if len(t_lines) > 3:
            t_lines = t_lines[:3]
            t_lines[-1] = t_lines[-1].rstrip(".,!?") + "…"
            notes.append("post title longer than 3 lines: cut, shorten it")
        t_lh = int(round(t_size * 1.18))
    # body: the voice words (grow) or a fixed text
    voice = str(cfg.get("text", "voice")).strip().lower() in ("voice", "say")
    tokens = [str(x["w"]) for x in words] if voice else []
    full = " ".join(tokens) if voice else str(cfg.get("text") or "").strip()
    stats = str(cfg.get("stats") or "").strip()
    foot_h = POST_META_PX + 8 if stats else 0
    fixed = POST_PAD + head_h + (20 + len(t_lines) * t_lh if t_lines else 0) + 18 + (20 + foot_h if stats else 0) + POST_PAD
    fb, b_size, lh, max_lines = None, POST_BODY_EM, 0, 1
    if full:
        for size in range(POST_BODY_EM, POST_BODY_MIN - 1, -2):
            fb = _font(brand.body.path, size)
            lh = int(round(size * 1.28))
            max_lines = max(1, (max_h - fixed) // lh)
            b_size = size
            if len(_wrap(full, fb, inner, 999)) <= max_lines:
                break
    total_lines = len(_wrap(full, fb, inner, 999)) if full else 0
    scrolled = total_lines > max_lines
    if scrolled:
        notes.append(f"post text is {total_lines} lines, the card shows the last {max_lines}: it scrolls up "
                     "(shorter text or captions after the card read better)")

    def draw(body: str) -> Image.Image:
        lines = _wrap(body, fb, inner, 999) if (body and fb) else []
        lines = lines[-max_lines:] if len(lines) > max_lines else lines
        n_body = max(1, len(lines)) if full else 0
        h = fixed - (18 if not full else 0) + n_body * lh
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=28, fill=hex_to_rgb(plate) + (255,))
        d.ellipse([POST_PAD, POST_PAD, POST_PAD + POST_AV, POST_PAD + POST_AV], fill=hex_to_rgb(av_c) + (255,))
        letter = (re.sub(r"^(u/|r/|@)", "", name)[:1] or "A").upper()
        li = _ink(letter, _font(brand.display.path, 44), hex_to_rgb(av_txt) + (255,))
        im.alpha_composite(li, (POST_PAD + (POST_AV - li.width) // 2, POST_PAD + (POST_AV - li.height) // 2))
        hy = POST_PAD + (head_h - (name_img.height + ((12 + where_img.height) if where_img else 0))) // 2
        im.alpha_composite(name_img, (text_x, hy))
        if where_img:
            im.alpha_composite(where_img, (text_x, hy + name_img.height + 12))
        yy = POST_PAD + head_h + 20
        if t_lines:
            asc = ft.getmetrics()[0]
            for i, ln in enumerate(t_lines):
                d.text((POST_PAD, yy + i * t_lh + asc), ln, font=ft, fill=hex_to_rgb(ink) + (255,), anchor="ls")
            yy += len(t_lines) * t_lh
        yy += 18
        if lines:
            asc = fb.getmetrics()[0]
            for i, ln in enumerate(lines):
                d.text((POST_PAD, yy + i * lh + asc), ln, font=fb, fill=hex_to_rgb(ink) + (255,), anchor="ls")
        if stats:
            fy = h - POST_PAD - foot_h
            parts = stats.split()
            x = POST_PAD
            for i, part in enumerate(parts[:2]):
                ic = (_icon_up if i == 0 else _icon_bubble)(POST_META_PX - 4, hex_to_rgb(meta_c) + (255,))
                im.alpha_composite(ic, (x, fy + 4))
                x += ic.width + 10
                ti = _ink(part, fm, hex_to_rgb(meta_c) + (255,))
                im.alpha_composite(ti, (x, fy + (foot_h - ti.height) // 2))
                x += ti.width + 40
        return im

    states: list[tuple[float, str]] = [(t0, "")] if voice else [(t0, full)]
    if voice:
        for k, wd in enumerate(words):
            t = max(t0, float(wd["s"]))
            body = " ".join(tokens[:k + 1])
            if states and abs(states[-1][0] - t) < 1e-6:
                states[-1] = (t, body)
            else:
                states.append((t, body))
    imgs = [(t, draw(b)) for t, b in states]
    hmax = max(im.height for _, im in imgs)
    canvas = []
    for t, im in imgs:
        c = Image.new("RGBA", (w, hmax), (0, 0, 0, 0))
        c.alpha_composite(im, (0, 0))
        canvas.append((t, c))
    box = Rect(s.x, y, w, hmax)
    sizes = [POST_META_PX] + ([t_size] if t_lines else []) + ([b_size] if full else [])
    pairs = [(ink, plate, 7.0), (meta_c, plate, 7.0)]
    spr = Sprite("post", canvas[0][1], box, (title + " | " if title else "") + full, min(sizes), pairs)
    if notes:
        spr.note = "; ".join(notes)
    rep = {"kind": kind, "states": len(canvas), "words": len(tokens), "body_px": b_size if full else 0,
           "title_px": t_size, "lines_max": max_lines, "lines_total": total_lines, "scrolled": scrolled,
           "height": hmax, "box": box.as_list(), "voice": voice}
    return spr, canvas, rep
