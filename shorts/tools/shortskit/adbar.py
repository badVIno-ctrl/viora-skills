"""Bottom ad bar (v2.1): the reference layout - full-width dark panel, thin accent line, РЕКЛАМА tag, logo tile + big brand
name on the left, big white QR on the right, animated logo.

  AdBar({"brand": "Quattro VPN", "sub": "VPN в Telegram", "url": "https://t.me/QuattroVPN_BOT?start=...",
         "logo": "logo.png" | "tg": "QuattroVPN_BOT", "accent": "#E5484D", "height": 300}).frame(t) -> BGR ndarray (h x 1080)

Geometry (1080 px wide, 8 px grid): padding 40; tag 22 px caps; logo tile 120 px, radius 28; brand name 64 px Manrope-Bold
(shrinks to fit); sub 28 px; QR box 260 px white, radius 20, quiet zone 4 modules, integer module size, error correction M.
Logo life (loop 3.2 s): breathing scale 1.00-1.05, one shine sweep, one soft ring pulse. The QR never moves (scannability).
Bar enters with a 0.35 s slide-up; `end` slides it out. Measured by `ad-bar-check`: QR decodes from the final frame.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .cardbanner import accent_from_logo, circle_crop, make_monogram, make_qr, rounded_mask
from .config import asset
from .util import ShortsError, hex_to_rgb

W = 1080
PAD = 40
LOOP = 3.2
BG = (14, 17, 22)


def _font(name: str, size: int):
    return ImageFont.truetype(str(asset("fonts") / name), size)


def _ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def _tile(img: Image.Image, size: int, radius: int) -> Image.Image:
    img = img.convert("RGBA")
    s = min(img.size)
    img = img.crop(((img.width - s) // 2, (img.height - s) // 2, (img.width + s) // 2, (img.height + s) // 2)).resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), rounded_mask(size, size, radius))
    return out


class AdBar:
    def __init__(self, spec: dict, base: Path | None = None):
        base = Path(base or ".")
        self.spec = spec
        self.h = int(spec.get("height", 300))
        self.url = spec.get("url") or ""
        if not self.url:
            raise ShortsError("ad bar needs the exact `url` (QR and caption use it)")
        self.brand = spec.get("brand") or "Brand"
        self.sub = spec.get("sub") or ""
        self.start = float(spec.get("start", 0.0))
        self.end = spec.get("end")
        self.animate = spec.get("animate_logo", True)
        logo = self._logo(spec, base)
        self.accent = hex_to_rgb(spec["accent"]) if spec.get("accent") else self._tame(accent_from_logo(logo))
        self.logo = _tile(logo, 120, 28)
        self.qr_size = int(spec.get("qr", 260))
        self._build()

    @staticmethod
    def _tame(c):
        """Pure #FF0000-style accents look cheap on a dark bar: cap saturation and brightness."""
        import colorsys
        h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
        return tuple(int(x * 255) for x in colorsys.hsv_to_rgb(h, min(s, 0.72), min(max(v, 0.7), 0.93)))

    def _logo(self, spec, base) -> Image.Image:
        p = spec.get("logo")
        if p:
            path = Path(p) if Path(p).is_absolute() else base / p
            if not path.exists():
                raise ShortsError(f"logo not found: {path}")
            return Image.open(path)
        if spec.get("tg"):
            from .fetch import brand_logo
            path = brand_logo(spec["tg"])
            if path:
                return Image.open(path)
        return make_monogram(self.brand, (60, 120, 255))

    def _build(self):
        h = self.h
        img = Image.new("RGB", (W, h), BG)
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, W, 4), fill=self.accent)
        # tag
        tf = _font("Manrope-Bold.ttf", 22)
        tag = "РЕКЛАМА"
        tw = int(tf.getlength(tag)) + 30
        d.rounded_rectangle((PAD, 28, PAD + tw, 28 + 36), 8, outline=(190, 196, 206), width=2)
        d.text((PAD + tw / 2, 28 + 18), tag, font=tf, fill=(215, 220, 228), anchor="mm")
        # logo slot + brand
        self.logo_xy = (PAD, 84 + (h - 84 - 120 - 24) // 2)
        text_x = PAD + 120 + 28
        max_w = (W - PAD - self.qr_size - 36) - text_x
        size = 66
        f = _font("Manrope-Bold.ttf", size)
        while f.getlength(self.brand) > max_w and size > 36:
            size -= 2
            f = _font("Manrope-Bold.ttf", size)
        cy = self.logo_xy[1] + 60
        d.text((text_x, cy - (14 if self.sub else 0)), self.brand, font=f, fill=(245, 247, 250), anchor="lm")
        if self.sub:
            sf = _font("Manrope-SemiBold.ttf", 28)
            sub = self.sub
            while sf.getlength(sub) > max_w and len(sub) > 8:
                sub = sub[:-2]
            d.text((text_x, cy + size // 2 + 4), sub, font=sf, fill=(150, 158, 170), anchor="lm")
        # QR (static, large, white box)
        qr = make_qr(self.url, self.qr_size - 24, dark=(8, 10, 16)).convert("RGB")
        box = self.qr_size
        qx, qy = W - PAD - box, (h - box) // 2 + 6
        d.rounded_rectangle((qx, qy, qx + box, qy + box), 20, fill=(255, 255, 255))
        img.paste(qr, (qx + (box - qr.width) // 2, qy + (box - qr.height) // 2))
        self.qr_rect = (qx, qy, box, box)
        self.static = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
        self.shine_mask = np.asarray(self.logo.split()[3]).astype(np.float32) / 255.0

    def _logo_layer(self, t: float):
        """(rgba float image 200x200 centred on the tile, alpha) for time t."""
        S = 200
        c = S // 2
        lt = (t % LOOP) / LOOP
        scale = 1.0 + (0.05 * (0.5 - 0.5 * math.cos(2 * math.pi * lt)) if self.animate else 0.0)
        tile = np.asarray(self.logo).astype(np.float32)
        if self.animate and 0.55 < lt < 0.78:                       # one shine sweep across the tile
            k = (lt - 0.55) / 0.23
            yy, xx = np.mgrid[0:120, 0:120].astype(np.float32)
            pos = -30 + k * 180
            band = np.clip(1 - np.abs((xx + yy * 0.55) - pos) / 22.0, 0, 1) * 0.55
            tile[..., :3] = tile[..., :3] * (1 - band[..., None]) + 255 * band[..., None]
        canvas = np.zeros((S, S, 4), np.float32)
        canvas[c - 60:c + 60, c - 60:c + 60] = tile
        m = cv2.getRotationMatrix2D((c, c), 0, scale)
        canvas = cv2.warpAffine(canvas, m, (S, S), flags=cv2.INTER_LINEAR)
        if self.animate and lt < 0.4:                                 # soft ring pulse
            k = lt / 0.4
            ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            r = 60 + 22 * _ease_out(k)
            ImageDraw.Draw(ring).rounded_rectangle((c - r, c - r, c + r, c + r), int(28 + 14 * k), outline=self.accent + (int(170 * (1 - k)),), width=4)
            ring = np.asarray(ring).astype(np.float32)
            a = ring[..., 3:4] / 255.0
            canvas[..., :3] = canvas[..., :3] * (1 - a) + ring[..., :3] * a
            canvas[..., 3:4] = np.maximum(canvas[..., 3:4], ring[..., 3:4])
        return canvas

    def frame(self, t: float) -> np.ndarray:
        """Bar pixels at time t relative to the video (BGR h x 1080)."""
        bar = self.static.copy()
        lay = self._logo_layer(t)
        S = lay.shape[0]
        x0, y0 = self.logo_xy[0] - (S - 120) // 2, self.logo_xy[1] - (S - 120) // 2
        a = lay[..., 3:4] / 255.0
        roi = bar[y0:y0 + S, x0:x0 + S].astype(np.float32)
        bar[y0:y0 + S, x0:x0 + S] = (roi * (1 - a) + lay[..., 2::-1] * a).astype(np.uint8)
        return bar

    def offset(self, t: float, total: float | None = None) -> int | None:
        """Pixels the bar is shifted down at time t (0 = fully in); None = not visible."""
        if t < self.start:
            return None
        end = float(self.end) if self.end is not None else total
        e = (t - self.start) / 0.35
        off = int((1 - _ease_out(e)) * self.h) if e < 1 else 0
        if end is not None and t > end - 0.3:
            off = max(off, int(min(1.0, (t - (end - 0.3)) / 0.3) * self.h))
        return None if off >= self.h else off


def preview(spec: dict, out_png: Path, base: Path | None = None, t: float = 1.5) -> Path:
    """Static check image: the bar on a 1080x1920 dark canvas at time t."""
    bar = AdBar(spec, base)
    canvas = np.full((1920, W, 3), 24, np.uint8)
    canvas[1920 - bar.h:] = bar.frame(t)
    Image.fromarray(canvas[..., ::-1]).save(out_png)
    return Path(out_png)


def qr_decodes(frame_bgr: np.ndarray, url: str) -> bool:
    """True when OpenCV reads the same URL from a rendered frame (the bar region of the final video).
    The Aruco-based detector is tried first: the classic one misses some valid version-4 codes at 5 px per module."""
    dets = []
    if hasattr(cv2, "QRCodeDetectorAruco"):
        dets.append(cv2.QRCodeDetectorAruco())
    dets.append(cv2.QRCodeDetector())
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    for det in dets:
        for img in (frame_bgr, gray, cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)):
            try:
                text = det.detectAndDecode(img)[0]
            except cv2.error:
                continue
            if text and text.strip() == url.strip():
                return True
    return False
