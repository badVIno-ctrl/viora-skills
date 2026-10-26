"""Covers v2.2: three covers that really differ, built around ONE focal face, a big 2-4 word headline, no template look.

Why 2.2: the delivered 2.1 covers (legacy `pack.make_cover`) looked raw: the photo pasted at y=600 under a dark
blurred top, Montserrat with a heavy black outline, a yellow pill tag on every cover, a fixed 240 px underline that
landed under a random letter, the same layout for every video. The legacy path is gone: everything renders here.

pick_distinct(src, t0, t1, k) -> k frames >= min_gap s apart, ranked by face size, sharpness, exposure, colour, open composition
render(frame, faces, text, variant, accent, tag, script=None, tag_style=None) -> (PIL 1080x1920, info)
  A "close":   face big, headline at the top, accent word in colour, warm grade
  B "context": wider shot, headline under the subject (above the feed UI), accent word on a colour plate, neutral grade
  C "poster":  tight crop, colour-pop grade (background almost mono, subject in colour), left-aligned headline
Every cover: full-bleed cover-fit crop (never a pasted rectangle, never blurred bars), exposure set on the face,
gentle local contrast, subject separation (background a little darker, softer and less saturated than the person, a
feathered head+shoulders mask), a soft scrim only behind the text, Unbounded Black caps with a soft shadow (no hard
outline), no underline, no tag pill unless `tag_style` asks for it ("kicker": small spaced caps above the headline).
`*word*` = the accent word; optional `script` = one handwritten word (Great Vibes, accent colour) hanging off the end
of the last headline line, slightly tilted.
Text never on the face (checked: info["text_on_face"]), never in the bottom 30 % (feed UI). `distinct(images)` rejects
near-duplicate covers (dHash distance < 14 bits of 256). Research: reference/cover-packaging.md.
"""
from __future__ import annotations

import colorsys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import asset
from .util import ShortsError, hex_to_rgb

W, H = 1080, 1920
VARIANTS = {
    "A": {"name": "close", "face": 0.30, "cy": 0.60, "text": "top", "accent": "#FFD84D", "grade": "warm", "acc": "color", "align": "center"},
    "B": {"name": "context", "face": 0.21, "cy": 0.40, "text": "low", "accent": "#FF4D3D", "grade": "neutral", "acc": "plate", "align": "center"},
    "C": {"name": "poster", "face": 0.36, "cy": 0.62, "text": "top", "accent": "#35D0FF", "grade": "pop", "acc": "color", "align": "left"},
}
FONT = "Unbounded-Black.ttf"
SCRIPT_FONT = "GreatVibes-Regular.ttf"
TEXT_TOP = 150             # under the status bar / search icon
TEXT_BOTTOM = 1340         # the feed UI (title, channel, buttons) covers the bottom ~30 %
MAX_UP = 2.6


def _detector():
    model = asset("models") / "face_detection_yunet_2023mar.onnx"
    return cv2.FaceDetectorYN.create(str(model), "", (320, 320), 0.7, 0.3, 5000) if model.exists() else None


def faces_in(det, frame: np.ndarray) -> list[tuple[float, float, float, float]]:
    if det is None:
        return []
    h, w = frame.shape[:2]
    sc = 640 / w
    small = cv2.resize(frame, (640, int(h * sc)))
    det.setInputSize((small.shape[1], small.shape[0]))
    _, f = det.detect(small)
    if f is None:
        return []
    out = []
    for r in f:
        eye_d = abs(float(r[6] - r[4])) or 1.0
        yaw = abs(float(r[8] - (r[4] + r[6]) / 2)) / eye_d          # nose off the eye midline: head turned
        out.append((float(r[0] / sc), float(r[1] / sc), float(r[2] / sc), float(r[3] / sc), float(r[14]), yaw))
    return sorted(out, key=lambda r: -r[2] * r[3])


def score_frame(fr: np.ndarray, faces) -> float:
    h, w = fr.shape[:2]
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    face = faces[0] if faces else None
    if face:
        x, y, fw, fh = [int(v) for v in face[:4]]
        roi = g[max(y, 0):y + fh, max(x, 0):x + fw]
        sharp = min(1.0, cv2.Laplacian(roi, cv2.CV_64F).var() / 180.0) if roi.size else 0
        bright = float(roi.mean()) if roi.size else 0
        expo = 1.0 - min(1.0, abs(bright - 125) / 100)
        area = min(1.0, (fh / h) / 0.22)
        cut = face[0] < 0.02 * w or face[0] + face[2] > 0.98 * w or face[1] < 0.01 * h
        conf, yaw = face[4], face[5]              # low confidence = hand/bottle over the face, closed eyes, motion blur
        pen = (0.3 if cut else 1.0) * min(1.0, conf) ** 3 * max(0.45, 1.0 - max(0.0, yaw - 0.25))
        two = 0.7 if len(faces) > 1 and faces[1][2] * faces[1][3] > 0.6 * face[2] * face[3] else 1.0
        sat = float(cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)[..., 1].mean()) / 255
        return (3.0 * area + 1.6 * sharp + 1.0 * expo + 0.6 * sat) * pen * two
    sharp = min(1.0, cv2.Laplacian(g, cv2.CV_64F).var() / 250.0)
    return 0.9 * sharp + 0.5 * min(1.0, float(g.std()) / 60)


def readable(src):
    """OpenCV cannot decode AV1/VP9 (yt-dlp webm). Return a path it can read, transcoding to H.264 once if needed."""
    import hashlib
    import subprocess
    from pathlib import Path

    codec = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(src)],
                           capture_output=True, text=True).stdout.strip()
    if codec in ("h264", "mpeg4", "mjpeg", "hevc"):
        return src
    from .config import cache_dir
    dst = cache_dir("readable") / (hashlib.md5(str(src).encode()).hexdigest()[:10] + ".mp4")
    if not dst.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-pix_fmt", "yuv420p", str(dst)], check=True)
    return Path(dst)


def pick_distinct(src, t0: float, t1: float, k: int = 3, min_gap: float = 3.0, n: int = 72):
    """k best frames, at least min_gap seconds apart. Returns [(frame, t, faces, score)] best first."""
    src = readable(src)
    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        raise ShortsError(f"cannot open {src}")
    det = _detector()
    cands = []
    for i in range(n):
        t = t0 + (t1 - t0) * (i + 0.5) / n
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        fs = faces_in(det, fr)
        cands.append((score_frame(fr, fs), t, fr, fs))
    cap.release()
    if not cands:
        raise ShortsError(f"no readable frames in {src} between {t0} and {t1}")
    cands.sort(key=lambda c: -c[0])
    gap = min(min_gap, max(0.4, (t1 - t0) / (k * 2)))
    chosen = []
    for c in cands:
        if all(abs(c[1] - o[1]) >= gap for o in chosen):
            chosen.append(c)
        if len(chosen) == k:
            break
    for c in cands:                                   # short clips: fill up even when gaps are tight
        if len(chosen) == k:
            break
        if c not in chosen:
            chosen.append(c)
    return [(c[2], c[1], c[3], c[0]) for c in chosen]


# ------------------------------------------------------------------ grading

def _curve(x: np.ndarray, strength: float) -> np.ndarray:
    return np.clip(x + strength * np.sin(2 * np.pi * (x - 0.5)) * 0.5, 0, 1)


def _expose(img: np.ndarray, frect) -> np.ndarray:
    """Gamma so the face (or the frame centre) sits at a healthy mid-tone: dark interview frames stop looking muddy."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if frect:
        x0, y0, x1, y1 = [int(v) for v in frect]
        roi = g[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
    else:
        roi = g[H // 4:3 * H // 4, W // 4:3 * W // 4]
    m = float(np.median(roi)) if roi.size else float(np.median(g))
    m = min(max(m, 8.0), 247.0)
    gamma = float(np.clip(np.log(132 / 255) / np.log(m / 255), 0.72, 1.25))
    lut = np.clip(((np.arange(256) / 255.0) ** gamma) * 255, 0, 255).astype(np.uint8)
    return cv2.LUT(img, lut)


def _grade(img: np.ndarray, kind: str, frect=None) -> np.ndarray:
    img = _expose(img, frect)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(clipLimit=1.3, tileGridSize=(4, 4)).apply(lab[..., 0])
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR).astype(np.float32) / 255
    img = _curve(img, 0.14)
    hsv = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * (1.12 if kind != "pop" else 1.05), 0, 255)
    out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    if kind == "warm":
        out[..., 2] *= 1.04
        out[..., 0] *= 0.95
    return np.clip(out, 0, 255).astype(np.uint8)


def _sharpen(img: np.ndarray, amount: float = 0.7) -> np.ndarray:
    blur = cv2.GaussianBlur(img, (0, 0), 1.4)
    return cv2.addWeighted(img, 1 + amount, blur, -amount, 0)


def subject_mask(frect, shape=(H, W)) -> np.ndarray:
    """Feathered head + shoulders mask (1 = person) from the face box: no segmentation model, no hard edge."""
    h, w = shape
    m = np.zeros((h, w), np.float32)
    if not frect:
        return m + 1.0
    x0, y0, x1, y1 = frect
    fw, fh = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cv2.ellipse(m, (int(cx), int(cy - 0.08 * fh)), (int(fw * 0.95), int(fh * 1.25)), 0, 0, 360, 1.0, -1)
    neck = y1 + 0.05 * fh
    poly = np.array([[cx - 0.55 * fw, neck], [cx + 0.55 * fw, neck], [cx + 2.3 * fw, neck + 1.6 * fh], [cx + 2.6 * fw, h],
                     [cx - 2.6 * fw, h], [cx - 2.3 * fw, neck + 1.6 * fh]], np.int32)
    cv2.fillPoly(m, [poly], 1.0)
    sig = max(8.0, 0.32 * fw)
    return cv2.GaussianBlur(m, (0, 0), sig)


def _separate(img: np.ndarray, mask: np.ndarray, kind: str) -> np.ndarray:
    """Background a bit darker, softer and less saturated than the person (depth without a fake cut-out)."""
    bg = cv2.GaussianBlur(img, (0, 0), 3.5).astype(np.float32)
    hsv = cv2.cvtColor(bg.astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] *= 0.18 if kind == "pop" else 0.82
    hsv[..., 2] *= 0.70 if kind == "pop" else 0.76
    bg = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    k = mask[..., None]
    return np.clip(img.astype(np.float32) * k + bg * (1 - k), 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ text

def _font(size: int, name: str = FONT):
    return ImageFont.truetype(str(asset("fonts") / name), int(size))


def parse_marked(text: str) -> list[tuple[str, bool]]:
    """'ОДИН *НЕИЗВЕСТНЫЙ ДВОР* ВСЕХ' -> [(word, accent)]; *...* may span several words. No marker: the last word is the accent.
    "100 000" stays one word (a number never splits over two lines)."""
    import re
    text = re.sub(r"(\d)\s+(?=\d{3}\b)", "\\1\u00a0", text)
    out, marked = [], False
    for part in re.split(r"(\*[^*]+\*)", text):
        acc = len(part) > 2 and part.startswith("*") and part.endswith("*")
        marked |= acc
        toks = [t for t in re.split(r"[ \t\r\n]+", part.strip("*")) if t]      # not str.split(): it splits on NBSP too
        if toks and out and not part[:1].isspace() and not part.startswith("*"):    # "*ДВА*?" keeps the mark glued to the word
            out[-1] = (out[-1][0] + toks.pop(0).upper(), out[-1][1])
        for w in toks:
            out.append((w.upper(), acc))
    if out and not marked:
        out[-1] = (out[-1][0], True)
    return out


def _wlen(f, w: str) -> float:
    return f.getlength(w.replace("\u00a0", " "))


def _lines(words: list[tuple[str, bool]], font, max_w: int) -> list[list[tuple[str, bool]]]:
    """Fewest lines, then the most even widths (never one short word hanging under a long line)."""
    n = len(words)
    sp = font.getlength(" ")
    best = None

    def width(seg):
        return sum(_wlen(font, w[0]) for w in seg) + sp * (len(seg) - 1)

    for mask in range(1 << max(0, n - 1)):
        cuts = [i + 1 for i in range(n - 1) if mask >> i & 1]
        if len(cuts) > 2:
            continue
        segs, prev = [], 0
        for c in cuts + [n]:
            segs.append(words[prev:c])
            prev = c
        ws = [width(sg) for sg in segs]
        if max(ws) > max_w:
            continue
        key = (len(segs), max(ws) - min(ws) if len(ws) > 1 else 0.0)
        if best is None or key < best[0]:
            best = (key, segs)
    return best[1] if best else [words]


def _fit(words, max_w: int, max_h: int, start: int = 176, floor: int = 84):
    size = start
    while size >= floor:
        f = _font(size)
        ls = _lines(words, f, max_w)
        sp = f.getlength(" ")
        if len(ls) <= 3 and len(ls) * size * 1.06 <= max_h and all(sum(_wlen(f, w[0]) for w in l) + sp * (len(l) - 1) <= max_w for l in ls):
            return f, ls, size
        size -= 4
    raise ShortsError("cover text does not fit: use at most 4 short words")


def _luma(rgb) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def draw_text(base: Image.Image, words, accent, zone: tuple[int, int, int, int], align: str = "center", acc_style: str = "color",
              script: str | None = None, kicker: str | None = None) -> tuple[int, int, int, int]:
    """Headline inside zone (x0, y0, x1, y1), vertically centred. Soft shadow, no outline. Returns the text bbox."""
    x0, y0, x1, y1 = zone
    room = (y1 - y0) - (int(0.55 * 120) if script else 0) - (60 if kicker else 0)
    f, ls, size = _fit(words, x1 - x0, room)
    lh = int(size * 1.06)
    sf = _font(int(size * 1.3), SCRIPT_FONT) if script else None
    s_h = int(size * 0.70) if script else 0
    k_h = 60 if kicker else 0
    total = k_h + len(ls) * lh + s_h
    y = y0 + (y1 - y0 - total) // 2
    txt = Image.new("RGBA", base.size, (0, 0, 0, 0))
    plates = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d, pd = ImageDraw.Draw(txt), ImageDraw.Draw(plates)
    sp = f.getlength(" ")
    on_plate = (17, 17, 17) if _luma(accent) > 140 else (255, 255, 255)
    bx0, by0, bx1, by1 = W, H, 0, 0
    if kicker:
        kf = _font(34, "Manrope-Bold.ttf")
        kt = " ".join(kicker.upper())
        kx = (x0 + x1) / 2 if align == "center" else x0 + 4
        d.text((kx, y + 6), kt, font=kf, fill=(255, 255, 255, 215), anchor="mt" if align == "center" else "lt")
        y += k_h
    for l in ls:
        lw = sum(_wlen(f, w[0]) for w in l) + sp * (len(l) - 1)
        x = (x0 + x1 - lw) / 2 if align == "center" else x0
        bx0, bx1 = min(bx0, int(x)), max(bx1, int(x + lw))
        for wd, acc in l:
            ww = _wlen(f, wd)
            if acc and acc_style == "plate":
                px, py_ = 0.14 * size, 0.10 * size
                pd.rounded_rectangle((x - px, y - py_ * 0.2, x + ww + px, y + size * 1.0 + py_ * 0.6), int(size * 0.16), fill=accent + (255,))
                d.text((x, y), wd.replace("\u00a0", " "), font=f, fill=on_plate + (255,))
            else:
                d.text((x, y), wd.replace("\u00a0", " "), font=f, fill=(accent if acc else (255, 255, 255)) + (255,))
            x += ww + sp
        by0 = min(by0, y)
        by1 = max(by1, y + lh)
        y += lh
    if script:                        # one handwritten word hanging off the end of the last line, slightly tilted
        stxt = Image.new("RGBA", base.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(stxt)
        last = ls[-1]
        lw = sum(_wlen(f, w[0]) for w in last) + sp * (len(last) - 1)
        lx1 = ((x0 + x1 + lw) / 2) if align == "center" else x0 + lw
        sx = min(x1 + 10, lx1 + size * 0.15)
        sy = y - int(size * 0.40)
        sd.text((sx, sy), script, font=sf, fill=accent + (255,), anchor="rt")
        stxt = stxt.rotate(5, resample=Image.BICUBIC, center=(sx, sy))
        txt.alpha_composite(stxt)
        sb = stxt.getbbox()
        if sb:
            bx0, by0, bx1, by1 = min(bx0, sb[0]), min(by0, sb[1]), max(bx1, sb[2]), max(by1, sb[3])
    a = Image.alpha_composite(plates, txt).split()[3]
    for blur, alpha, dy in ((22, 0.55, 10), (4, 0.35, 3)):
        sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
        m = Image.new("L", base.size, 0)
        m.paste(a.filter(ImageFilter.GaussianBlur(blur)).point(lambda v, k=alpha: int(v * k)), (0, dy))
        sh.putalpha(m)
        base.alpha_composite(sh)
    base.alpha_composite(plates)
    base.alpha_composite(txt)
    return bx0, by0, bx1, by1


# ------------------------------------------------------------------ compose

def _crop_for(frame: np.ndarray, face, face_frac: float, cy_frac: float):
    sh, sw = frame.shape[:2]
    if face:
        fx, fy, fw, fh = face[:4]
        fcx, fcy = fx + fw / 2, fy + fh / 2
        s = min(max((face_frac * H) / fh, max(W / sw, H / sh)), max(MAX_UP, max(W / sw, H / sh)))
    else:
        fcx, fcy = sw / 2, sh * 0.42
        s = max(W / sw, H / sh)
        fh = sh * 0.3
    cw, ch = W / s, H / s
    x0 = min(max(fcx - cw / 2, 0), sw - cw)
    y0 = min(max(fcy - ch * cy_frac, 0), sh - ch)
    return x0, y0, cw, ch, s


def _scrim(img: np.ndarray, zone, where: str) -> np.ndarray:
    """Darken only where the text is (a soft band), not the whole top half."""
    yy = np.arange(H, dtype=np.float32)
    z0, z1 = zone[1], zone[3]
    if where == "top":
        a = np.clip(1 - (yy - z1) / 260, 0, 1) * 0.58
        a[: max(0, z0 - 150)] = np.maximum(a[: max(0, z0 - 150)], 0.58)
    else:
        a = np.clip(1 - (z0 - yy) / 260, 0, 1) * 0.62
        a = np.where(yy > z1, np.maximum(0.62 * np.clip(1 - (yy - z1) / 400, 0, 1), 0.30), a)
    a = a ** 1.0
    return (img.astype(np.float32) * (1 - a)[:, None, None]).astype(np.uint8)


def render(frame: np.ndarray, faces, text: str, variant: str = "A", accent: str | None = None, tag: str | None = None,
           script: str | None = None, tag_style: str | None = None) -> tuple[Image.Image, dict]:
    v = VARIANTS[variant]
    acc = hex_to_rgb(accent) if accent else hex_to_rgb(v["accent"])
    words = parse_marked(text)
    if not 1 <= len(words) <= 5:
        raise ShortsError(f"cover text has {len(words)} words: 2-4 read on a phone, 5 is the limit")
    face = faces[0] if faces else None
    x0, y0, cw, ch, s = _crop_for(frame, face, v["face"], v["cy"])
    m = np.array([[s, 0, -x0 * s], [0, s, -y0 * s]], dtype=np.float32)
    img = cv2.warpAffine(frame, m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    frect = None
    if face:
        fx_, fy_ = (face[0] + face[2] / 2 - x0) * s, (face[1] + face[3] / 2 - y0) * s
        frect = (int(fx_ - face[2] * s / 2), int(fy_ - face[3] * s / 2), int(fx_ + face[2] * s / 2), int(fy_ + face[3] * s / 2))
    img = _grade(img, v["grade"], frect)
    if s > 1.6:
        img = _sharpen(img, min(1.0, 0.35 * s))
        noise = np.random.default_rng(7).normal(0, 2.6, img.shape).astype(np.float32)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if frect:
        img = _separate(img, subject_mask(frect), v["grade"])
    vign = 1 - 0.22 * np.clip((np.abs(np.linspace(-1, 1, W, dtype=np.float32))[None, :]) ** 2.4, 0, 1)
    img = (img.astype(np.float32) * vign[..., None]).astype(np.uint8)
    pad = 64 if v["align"] == "center" else 72
    core = face_core(frect) if frect else None
    top_z = (pad, TEXT_TOP, W - pad, int(min(TEXT_TOP + 640, (core[1] - 28) if core else 790)))
    low_z = (pad, int(max(core[3] + 36, 960) if core else 1000), W - pad, TEXT_BOTTOM)
    zones = [top_z, low_z] if v["text"] == "top" else [low_z, top_z]
    zones += [(pad, TEXT_TOP, W - pad, TEXT_TOP + 320), (pad, 1000, W - pad, TEXT_BOTTOM)]     # last resort: may touch the face
    kicker = tag if (tag and tag_style == "kicker") else None
    bbox, used = None, None
    for z in zones:
        if z[3] - z[1] < 200:
            continue
        try:
            f, _, _ = _fit(words, z[2] - z[0], (z[3] - z[1]) - (66 if script else 0) - (60 if kicker else 0))
        except ShortsError:
            continue
        used = z
        break
    if used is None:
        raise ShortsError("cover text does not fit: use at most 4 short words")
    img = _scrim(img, used, "top" if used[1] < 700 else "low")
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).convert("RGBA")
    bbox = draw_text(pil, words, acc, used, v["align"], v["acc"], script, kicker)
    if tag and tag_style == "pill":
        d = ImageDraw.Draw(pil)
        tf = _font(34, "Manrope-Bold.ttf")
        tw = int(tf.getlength(tag.upper())) + 48
        d.rounded_rectangle((pad, 84, pad + tw, 84 + 56), 28, fill=(14, 14, 16, 200))
        d.text((pad + tw / 2, 84 + 29), tag.upper(), font=tf, fill=(255, 255, 255, 255), anchor="mm")
    info = {"variant": variant, "style": v["name"], "scale": round(float(s), 2),
            "face_h_frac": round(float((face[3] * s) / H), 2) if face else None,
            "text_bbox": tuple(int(q) for q in bbox), "face_rect": frect, "upscale_soft": bool(s > MAX_UP),
            "tag": "kicker" if kicker else ("pill" if tag and tag_style == "pill" else ("ignored" if tag else None))}
    info["text_on_face"] = bool(core and not (bbox[2] < core[0] or bbox[0] > core[2] or bbox[3] < core[1] or bbox[1] > core[3]))
    return pil.convert("RGB"), info


def face_core(r):
    """Eyes-nose-mouth part of a face box (x0, y0, x1, y1): text may touch hair and forehead, never this."""
    w, h = r[2] - r[0], r[3] - r[1]
    return (r[0] + 0.08 * w, r[1] + 0.14 * h, r[2] - 0.08 * w, r[3] - 0.04 * h)


def dhash(img: Image.Image, n: int = 16) -> np.ndarray:
    g = np.asarray(img.convert("L").resize((n + 1, n), Image.LANCZOS)).astype(np.int16)
    return (g[:, 1:] > g[:, :-1]).flatten()


def distinct(images: list[Image.Image], min_bits: int = 14) -> list[str]:
    """Problems when two covers look alike (dHash 16x16, hamming < min_bits)."""
    hs = [dhash(i) for i in images]
    out = []
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            b = int((hs[i] != hs[j]).sum())
            if b < min_bits:
                out.append(f"cover {i + 1} and {j + 1} look alike ({b} of 256 bits differ, need {min_bits})")
    return out
