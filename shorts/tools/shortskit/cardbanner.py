"""Floating ad card ("плашка" 2.0): rounded glass-like card with rotating headlines, logo, QR.

Modelled on real Shorts ad inserts (rounded dark card with a glossy ribbon, brand + 2-line bold
headline + small URL, a hero object on the right, headlines that rotate every ~2.6 s). It floats in
the upper safe zone (not in the bottom 672 px that the Shorts UI covers).

Spec (all optional except brand and slides):
  {"brand": "Quattro VPN", "tg": "QuattroVPN_BOT", "logo": "file.png",
   "slides": [{"title": "Быстрый VPN\\nв Telegram", "sub": "Открой бота"}, ...],
   "url": "t.me/QuattroVPN_BOT", "qr_url": "https://t.me/...", "label": "Реклама",
   "theme": "quattro|bob|auto|navy", "colors": {"bg1": "#..", "bg2": "#..", "accent": "#..", "glow": "#.."},
   "size": [760, 320], "slide_s": 2.6, "enter_s": 0.5}
`logo` wins over `tg`; with neither, an honest monogram is drawn (never an invented logo).
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .config import asset
from .util import ShortsError, hex_to_rgb

THEMES = {
    "quattro": {"bg1": "#0B0D1E", "bg2": "#241046", "accent": "#FF4B5C", "glow": "#7B5CFF"},
    "bob": {"bg1": "#06111F", "bg2": "#0B3150", "accent": "#35D6FF", "glow": "#6C7BFF"},
    "navy": {"bg1": "#050B1E", "bg2": "#10307A", "accent": "#3AA0FF", "glow": "#6A5CFF"},
}
SS = 2          # supersampling for the static shapes
MARGIN = 56     # room for the shadow around the card


def ease_out_cubic(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def ease_out_back(x: float) -> float:
    x = min(1.0, max(0.0, x))
    c1, c3 = 1.4, 2.4
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_in_out(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _rgb(h) -> tuple[int, int, int]:
    return tuple(h) if isinstance(h, (tuple, list)) else hex_to_rgb(h)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(asset("fonts") / name), size)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def rounded_mask(w: int, h: int, r: int, ss: int = 4) -> Image.Image:
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def circle_crop(img: Image.Image, size: int) -> Image.Image:
    img = img.convert("RGBA")
    s = min(img.size)
    img = img.crop(((img.width - s) // 2, (img.height - s) // 2, (img.width + s) // 2, (img.height + s) // 2))
    img = img.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), rounded_mask(size, size, size // 2))
    return out


def accent_from_logo(logo: Image.Image) -> tuple[int, int, int]:
    """Most saturated, reasonably bright colour of the logo (brand accent)."""
    small = logo.convert("RGB").resize((48, 48))
    best, score = (58, 160, 255), -1.0
    for px in small.getdata():
        mx, mn = max(px), min(px)
        sat = (mx - mn) / (mx + 1e-6)
        s = sat * (mx / 255.0) * (1.0 if 90 < mx else 0.4)
        if s > score:
            best, score = px, s
    r, g, b = best
    if max(best) < 150:                       # lift dark brand colours so text pills stay lively
        k = 190 / max(max(best), 1)
        r, g, b = (min(255, int(c * k)) for c in best)
    return (r, g, b)


def make_monogram(text: str, color: tuple[int, int, int], size: int = 256) -> Image.Image:
    img = Image.new("RGBA", (size, size), color + (255,))
    d = ImageDraw.Draw(img)
    f = _font("Montserrat-ExtraBold.ttf", int(size * 0.56))
    d.text((size / 2, size / 2 + size * 0.02), (text.strip() or "?")[0].upper(), font=f, fill=(255, 255, 255, 255), anchor="mm")
    return circle_crop(img, size)


def make_qr(url: str, px: int, dark=(10, 12, 26)) -> Image.Image:
    """QR with a 4-module quiet zone; integer module size so edges stay sharp after scaling."""
    import segno
    q = segno.make(url, error="m", boost_error=False)
    rows = [list(r) for r in q.matrix]
    n = len(rows)
    mod = max(1, px // (n + 8))
    size = (n + 8) * mod
    img = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    for y, row in enumerate(rows):
        for x, v in enumerate(row):
            if v:
                d.rectangle(((x + 4) * mod, (y + 4) * mod, (x + 5) * mod - 1, (y + 5) * mod - 1), fill=dark + (255,))
    return img


def wrap_lines(text: str, font: ImageFont.FreeTypeFont, width: int, max_lines: int = 2) -> list[str]:
    if "\n" in text:
        return [s.strip() for s in text.split("\n") if s.strip()][:max_lines]
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class CardBanner:
    def __init__(self, spec: dict, base_dir: Path | None = None):
        self.spec = spec
        base = Path(base_dir or ".")
        self.w, self.h = (spec.get("size") or [760, 320])
        self.slide_s = float(spec.get("slide_s", 2.6))
        self.enter_s = float(spec.get("enter_s", 0.5))
        slides = spec.get("slides") or []
        if not slides:
            raise ShortsError("card banner needs at least one slide: {title, sub}")
        self.slides = slides
        self.brand = spec.get("brand") or ""
        self.label = spec.get("label", "Реклама")
        self.url = spec.get("url") or ""
        logo = self._load_logo(spec, base)
        self.logo_real = logo is not None
        theme = spec.get("theme") or "navy"
        pal = dict(THEMES.get(theme, THEMES["navy"]))
        if theme == "auto" and logo is not None:
            acc = accent_from_logo(logo)
            pal.update({"accent": "#%02x%02x%02x" % acc, "bg1": "#07091A",
                        "bg2": "#%02x%02x%02x" % _lerp((10, 10, 30), acc, 0.28), "glow": "#%02x%02x%02x" % _lerp(acc, (255, 255, 255), 0.15)})
        pal.update(spec.get("colors") or {})
        self.c = {k: _rgb(v) for k, v in pal.items()}
        if logo is None:
            logo = make_monogram(self.brand, self.c["accent"])
        self.logo = logo
        self.qr = make_qr(spec["qr_url"], 176) if spec.get("qr_url") else None
        self._build_static()

    # ------------------------------------------------------------ assets
    def _load_logo(self, spec, base: Path):
        p = spec.get("logo")
        if p:
            path = Path(p) if Path(p).is_absolute() else base / p
            if not path.exists():
                raise ShortsError(f"logo not found: {path}")
            return circle_crop(Image.open(path), 256)
        if spec.get("tg"):
            from .fetch import brand_logo
            path = brand_logo(spec["tg"])
            if path:
                return circle_crop(Image.open(path), 256)
        return None

    # ------------------------------------------------------------ static layers
    def _build_static(self):
        w, h, m = self.w, self.h, MARGIN
        W2, H2 = w * SS, h * SS
        c1, c2, ac, gl = self.c["bg1"], self.c["bg2"], self.c["accent"], self.c["glow"]
        yy, xx = np.mgrid[0:H2, 0:W2].astype(np.float32)
        t = np.clip((xx / W2) * 0.62 + (yy / H2) * 0.38, 0, 1)[..., None]
        bg = np.array(c1, np.float32) * (1 - t) + np.array(c2, np.float32) * t
        # soft radial glow behind the hero side
        rg = np.exp(-(((xx - W2 * 0.82) / (W2 * 0.35)) ** 2 + ((yy - H2 * 0.45) / (H2 * 0.7)) ** 2))[..., None]
        bg = bg + rg * np.array(gl, np.float32) * 0.22
        base = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
        # ribbons on an oversized layer so they can drift (parallax) per frame
        rw, rh = W2 + 160 * SS, H2
        rib = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        glow = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))

        def band(img, x0, width, ang, c_a, c_b, alpha):
            layer = Image.new("RGBA", (rw, rh * 2), (0, 0, 0, 0))
            arr = np.zeros((rh * 2, width, 4), np.uint8)
            tt = np.linspace(0, 1, width)[None, :, None]
            col = np.array(c_a, np.float32) * (1 - tt) + np.array(c_b, np.float32) * tt
            arr[..., :3] = np.repeat(col, rh * 2, axis=0).astype(np.uint8)
            edge = np.minimum(tt, 1 - tt) * 2
            arr[..., 3] = np.repeat((np.clip(edge * 3, 0, 1) * alpha * 255), rh * 2, axis=0)[..., 0].astype(np.uint8)
            strip = Image.fromarray(arr, "RGBA")
            layer.paste(strip, (x0, 0))
            layer = layer.rotate(ang, resample=Image.BICUBIC, center=(x0 + width // 2, rh))
            img.alpha_composite(layer.crop((0, rh // 2, rw, rh // 2 + rh)))

        band(glow, int(rw * 0.60), 150 * SS, 24, ac, gl, 0.9)
        band(rib, int(rw * 0.62), 54 * SS, 24, _lerp(ac, (255, 255, 255), 0.25), gl, 0.95)
        band(rib, int(rw * 0.74), 30 * SS, 38, gl, _lerp(gl, (255, 255, 255), 0.5), 0.85)
        glow = glow.filter(ImageFilter.GaussianBlur(26 * SS))
        rib = rib.filter(ImageFilter.GaussianBlur(1.2 * SS))
        rib = Image.alpha_composite(glow, rib)
        self._ribbon = rib.resize((rib.width // SS, rib.height // SS), Image.LANCZOS)
        # left vignette = contrast for text
        vg = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
        va = (np.clip(1 - xx / (W2 * 0.7), 0, 1) ** 1.4 * 150).astype(np.uint8)
        vg.putalpha(Image.fromarray(va, "L"))
        self._bg = base.resize((w, h), Image.LANCZOS)
        self._vignette = vg.resize((w, h), Image.LANCZOS)
        r = 36
        self._mask = rounded_mask(w, h, r)
        # shadow + glass edge
        sh = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
        sh_m = Image.new("L", sh.size, 0)
        sh_m.paste(self._mask.point(lambda v: int(v * 0.55)), (m, m + 14))
        sh.putalpha(sh_m.filter(ImageFilter.GaussianBlur(20)))
        self._shadow = sh
        edge = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        ImageDraw.Draw(edge).rounded_rectangle((1, 1, w * SS - 2, h * SS - 2), r * SS, outline=(255, 255, 255, 46), width=2 * SS)
        self._edge = edge.resize((w, h), Image.LANCZOS)
        # shine strip (diagonal soft band)
        sw = 170
        sa = np.zeros((h + 80, sw), np.float32)
        tt = np.linspace(-1, 1, sw)[None, :]
        sa[:] = np.clip(1 - np.abs(tt), 0, 1) ** 2 * 70
        shine = Image.new("RGBA", (sw, h + 80), (255, 255, 255, 0))
        shine.putalpha(Image.fromarray(sa.astype(np.uint8), "L"))
        self._shine = shine.rotate(-18, resample=Image.BICUBIC, expand=True)
        self._build_layout()

    def _build_layout(self):
        w, h = self.w, self.h
        pad = 38
        right_w = (self.qr.width if self.qr else 190) + 28
        self.text_w = w - pad * 2 - right_w - 6
        self.pad = pad
        fh = _font("Montserrat-ExtraBold.ttf", 50)
        fs = _font("Manrope-Bold.ttf", 26)
        # slides rendered once as RGBA layers, shrunk until they fit
        self.slide_layers = []
        for s in self.slides:
            size = 52
            while True:
                fh = _font("Montserrat-ExtraBold.ttf", size)
                lines = wrap_lines(s["title"], fh, self.text_w)
                if (len(lines) <= 2 and all(fh.getlength(l) <= self.text_w for l in lines)) or size <= 34:
                    break
                size -= 2
            lay = Image.new("RGBA", (self.text_w + 10, 170), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            y = 0
            lh = int(size * 1.16)
            for l in lines:
                d.text((0, y), l, font=fh, fill=(255, 255, 255, 255))
                y += lh
            if s.get("sub"):
                d.text((0, y + 6), s["sub"], font=fs, fill=_lerp(self.c["accent"], (255, 255, 255), 0.38) + (255,))
            self.slide_layers.append(lay)
        # static foreground (brand row, url, label, qr tile)
        fg = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(fg)
        fb = _font("Manrope-Bold.ttf", 25)
        self.logo_small = self.logo.resize((48, 48), Image.LANCZOS)
        d.text((pad + 48 + 12, 52), self.brand, font=fb, fill=(255, 255, 255, 235), anchor="lm")
        if self.url:
            fu = _font("Manrope-SemiBold.ttf", 21)
            d.text((pad, h - 36), self.url, font=fu, fill=(255, 255, 255, 150), anchor="lm")
        if self.label:
            fl = _font("Manrope-Bold.ttf", 22)
            tw = int(fl.getlength(self.label)) + 28
            lx = w - 30 - tw
            d.rounded_rectangle((lx, 24, lx + tw, 24 + 34), 17, fill=(255, 255, 255, 40), outline=(255, 255, 255, 90), width=1)
            d.text((lx + tw / 2, 24 + 17), self.label, font=fl, fill=(255, 255, 255, 235), anchor="mm")
        self._fg = fg
        self.hero_pos = None
        if self.qr:
            qs = self.qr.width
            tile = Image.new("RGBA", (qs + 24, qs + 24), (0, 0, 0, 0))
            tm = rounded_mask(qs + 24, qs + 24, 26)
            white = Image.new("RGBA", tile.size, (255, 255, 255, 255))
            tile.paste(white, (0, 0), tm)
            tile.paste(self.qr, (12, 12))
            self._tile = tile
            self.hero_pos = (w - 30 - tile.width, 72 + (h - 72 - 30 - tile.height) // 2)
        else:
            self._tile = None
            self.hero_pos = (w - 30 - 190, 76 + (h - 76 - 40 - 190) // 2)

    # ------------------------------------------------------------ frame
    def size(self) -> tuple[int, int]:
        return self.w + 2 * MARGIN, self.h + 2 * MARGIN

    def _slide_state(self, t: float):
        """[(slide index, alpha, y offset)]: the old headline lifts out while the next rises in (0.38 s)."""
        n = len(self.slides)
        if n == 1:
            return [(0, 1.0, 0.0)]
        k_idx = int(t // self.slide_s)
        idx, local, fade = k_idx % n, t - k_idx * self.slide_s, 0.38
        if local < fade and k_idx > 0:
            k = ease_out_cubic(local / fade)
            return [((idx - 1) % n, 1 - k, -k * 26), (idx, k, (1 - k) * 26)]
        return [(idx, 1.0, 0.0)]

    def frame(self, t: float, total: float | None = None, exit_s: float = 0.35) -> Image.Image:
        w, h, m = self.w, self.h, MARGIN
        # entrance / exit
        e = ease_out_back(t / self.enter_s) if self.enter_s > 0 else 1.0
        alpha = min(1.0, t / (self.enter_s * 0.6)) if self.enter_s > 0 else 1.0
        dy = (1 - e) * -46
        if total is not None and t > total - exit_s:
            k = ease_in_out((t - (total - exit_s)) / exit_s)
            alpha *= 1 - k
            dy += -26 * k
        card = self._bg.copy()
        drift = int(18 * math.sin(t * 0.9))
        card.alpha_composite(self._ribbon.crop((60 + drift, 0, 60 + drift + w, h)))
        card.alpha_composite(self._vignette)
        # shine sweep every 4.4 s
        ph = (t % 4.4) / 1.1
        if 0 <= ph <= 1:
            sx = int(-self._shine.width + ph * (w + self._shine.width * 1.2))
            tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            tmp.alpha_composite(self._shine, (max(sx, 0), 0), (max(-sx, 0), 0))
            card.alpha_composite(tmp)
        # logo row
        pulse = 0.5 + 0.5 * math.sin(t * 3.0)
        ring = Image.new("RGBA", (68, 68), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((2, 2, 65, 65), outline=self.c["accent"] + (int(70 + 120 * pulse),), width=3)
        card.alpha_composite(ring, (self.pad - 10, 52 - 34))
        card.alpha_composite(self.logo_small, (self.pad, 52 - 24))
        card.alpha_composite(self._fg)
        # hero (QR tile or big logo), gently floating
        bob = int(round(3 * math.sin(t * 2.2)))
        hx, hy = self.hero_pos
        if self._tile is not None:
            glow = Image.new("RGBA", self._tile.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).rounded_rectangle((0, 0, self._tile.width - 1, self._tile.height - 1), 26, outline=self.c["accent"] + (int(90 + 100 * pulse),), width=3)
            card.alpha_composite(self._tile, (hx, hy + bob))
            card.alpha_composite(glow, (hx, hy + bob))
        else:
            sz = int(180 + 6 * pulse)
            big = self.logo.resize((sz, sz), Image.LANCZOS)
            card.alpha_composite(big, (hx + (190 - sz) // 2, hy + bob + (190 - sz) // 2))
        # headline slides
        base_y = 84
        for idx, a, off in self._slide_state(t):
            lay = self.slide_layers[idx]
            if a < 1.0:
                lay = lay.copy()
                lay.putalpha(lay.getchannel("A").point(lambda v, a=a: int(v * a)))
            card.alpha_composite(lay, (self.pad, int(base_y + off)))
        # slide dots
        n = len(self.slides)
        if n > 1:
            cur = int(t // self.slide_s) % n
            d = ImageDraw.Draw(card)
            x0 = self.pad + self.text_w - (n * 16)
            for i in range(n):
                on = i == cur
                d.ellipse((x0 + i * 16, h - 42, x0 + i * 16 + 9, h - 33), fill=(self.c["accent"] + (255,)) if on else (255, 255, 255, 70))
        card.putalpha(ImageChops.multiply(card.getchannel("A"), self._mask))
        card.alpha_composite(self._edge)
        out = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
        out.alpha_composite(self._shadow)
        out.alpha_composite(card, (m, m + int(dy)))
        if alpha < 1.0:
            out.putalpha(out.getchannel("A").point(lambda v: int(v * alpha)))
        return out


def preview(spec: dict, out_png: Path, base_dir: Path | None = None) -> Path:
    """Contact sheet: one frame per slide on a mid-grey checker so the transparency is visible."""
    cb = CardBanner(spec, base_dir)
    cw, ch = cb.size()
    n = len(cb.slides)
    sheet = Image.new("RGB", (cw, ch * n), (60, 60, 70))
    for i in range(n):
        f = cb.frame(i * cb.slide_s + cb.slide_s * 0.7)
        sheet.paste(f, (0, i * ch), f)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    return out_png


def render_webm(spec: dict, out: Path, duration: float, fps: int = 25, base_dir: Path | None = None, canvas=(1080, 1920), xy=(None, 380)) -> Path:
    """Transparent 1080x1920 overlay (VP9 + alpha) for any editor."""
    cb = CardBanner(spec, base_dir)
    cw, ch = cb.size()
    W, H = canvas
    x = (W - cw) // 2 if xy[0] is None else xy[0]
    y = xy[1]
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "30", "-auto-alt-ref", "0", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(duration * fps)):
        f = cb.frame(i / fps, duration)
        full = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        full.alpha_composite(f, (x, y))
        p.stdin.write(full.tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise ShortsError("ffmpeg failed while writing the card overlay")
    return out
