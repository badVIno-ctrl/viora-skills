"""Transparent ad overlays (1080x1920, alpha) for editors: CapCut / Premiere / DaVinci.

`python tools/shorts.py ad-overlay overlay.json --out DIR [--mov]`
overlay.json:
  {"kind": "banner", "name": "...", "message": "...", "action": "...", "handle": "...", "qr_url": "https://...",
   "logo": "path.png", "variant": "quattro|bob", "colors": {"bg": "#101419", "accent": "#EE4B4F", "fg": "#FFFFFF"},
   "duration": 12, "reserve_bottom_pct": 6}
  {"kind": "link", "text": "t.me/NAME", "caption": "Подписывайся", "duration": 4,
   "colors": {...}, "y_pct": 50}
Result: DIR/<kind>.webm (VP9 + alpha, small) and with --mov DIR/<kind>.mov (ProRes 4444 + alpha), plus <kind>-preview.png.
The banner is an advert: the disclosure pill is always on. Nothing is published.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

from .config import asset
from .engine.banner import AnimatedBanner, readable_on, rrect, with_alpha, _rgb, keyframe
from .util import ShortsError, read_json, write_json

W, H, FPS = 1080, 1920, 25


def _brand():
    f = asset("fonts")
    return SimpleNamespace(body=SimpleNamespace(path=f / "Manrope-SemiBold.ttf"),
                           display=SimpleNamespace(path=f / "Manrope-Bold.ttf"), logo_text="")


class LinkPill:
    """Slides in from the right edge to the centre, holds, slides out. One link, one caption."""

    def __init__(self, cfg, brand, duration):
        self.dur = duration
        col = cfg.get("colors") or {}
        self.bg = _rgb(col.get("bg") or "#101419"); self.accent = _rgb(col.get("accent") or "#EE4B4F"); self.fg = _rgb(col.get("fg") or "#FFFFFF")
        text = cfg.get("text")
        if not text:
            raise ShortsError("link overlay needs text (the exact link text)")
        cap = cfg.get("caption") or ""
        fb = ImageFont.truetype(str(brand.display.path), 64); fs = ImageFont.truetype(str(brand.body.path), 34)
        wt = int(fb.getlength(text)); wc = int(fs.getlength(cap)) if cap else 0
        pw = min(W-96, max(wt, wc)+96); ph = 150 if cap else 112
        if max(wt, wc)+96 > W-96:
            raise ShortsError("link text too long for one line: shorten it")
        pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        base = rrect(pw, ph, ph//2 if not cap else 40, self.bg+(255,))
        pill.alpha_composite(base)
        d = ImageDraw.Draw(pill)
        if cap:
            d.text((pw//2, 40), cap, font=fs, fill=self.fg+(210,), anchor="mm")
            d.text((pw//2, 98), text, font=fb, fill=self.accent, anchor="mm")
        else:
            d.text((pw//2, ph//2), text, font=fb, fill=self.accent, anchor="mm")
        self.pill = pill; self.y = int(H*float(cfg.get("y_pct", 50))/100-ph/2)
        self.box = ((W-pw)//2, self.y, pw, ph)

    def __call__(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        e = keyframe([{"t": 0, "value": 0}, {"t": .5, "value": 1, "ease": "out_cubic"}], t)
        x = (1-e)
        o = keyframe([{"t": self.dur-.5, "value": 1}, {"t": self.dur, "value": 0, "ease": "in_out"}], t)
        v = min(e, o)
        px = self.box[0]+int((W-self.box[0])*(1-e)) if t < self.dur-.5 else self.box[0]-int((self.box[0]+self.box[2])*(1-o))
        im.alpha_composite(with_alpha(self.pill, v if v < 1 else 1), (px, self.y))
        return im


def _encode(frames, n, out: Path, mov: bool):
    cmds = [["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
             "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28", "-auto-alt-ref", "0", str(out.with_suffix(".webm"))]]
    if mov:
        cmds.append(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                     "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(out.with_suffix(".mov"))])
    procs = [subprocess.Popen(c, stdin=subprocess.PIPE) for c in cmds]
    for k in range(n):
        b = frames(k/FPS).tobytes()
        for p in procs:
            p.stdin.write(b)
    for p in procs:
        p.stdin.close()
    if any(p.wait() != 0 for p in procs):
        raise ShortsError("ffmpeg failed while encoding the overlay (needs libvpx-vp9 / prores_ks)")


def render(spec_path: str, out: str, mov: bool = False) -> dict:
    spec = read_json(spec_path)
    kind = spec.get("kind", "banner")
    brand = _brand()
    outd = Path(out); outd.mkdir(parents=True, exist_ok=True)
    base = Path(spec_path).parent
    if kind == "banner":
        if not spec.get("message") or not spec.get("action"):
            raise ShortsError("banner overlay needs explicit message and action (no default text)")
        logo = spec.get("logo")
        logo = str((base/logo) if logo and not Path(logo).is_absolute() else logo) if logo else None
        cfg = dict(spec); cfg["animation"] = {"variant": spec.get("variant", "quattro"), "cycle": float(spec.get("cycle", 12)),
                                              "safe_right": int(spec.get("safe_right", 120))}
        h = int(spec.get("height", 384)); reserve = int(H*float(spec.get("reserve_bottom_pct", 6))/100)//8*8
        ban = AnimatedBanner(W, h, brand, cfg, logo)
        y = H-h-reserve
        dur = float(spec.get("duration", ban.cycle))
        def frames(t):
            im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.alpha_composite(ban(t), (0, y)); return im
        man = ban.manifest(); man["panel_box"] = [0, y, W, h]
    elif kind == "link":
        dur = float(spec.get("duration", 4))
        lp = LinkPill(spec, brand, dur); frames = lp
        man = {"box": lp.box, "text": spec["text"]}
    else:
        raise ShortsError("kind must be banner or link")
    n = int(round(dur*FPS))
    target = outd/kind
    _encode(frames, n, target, mov)
    prev = Image.new("RGBA", (W, H), (60, 60, 60, 255)); prev.alpha_composite(frames(min(dur-.6, 5.0)))
    prev.convert("RGB").resize((360, 640)).save(outd/f"{kind}-preview.png")
    man.update({"duration": dur, "fps": FPS, "size": [W, H]})
    write_json(outd/f"{kind}.json", man)
    files = sorted(p.name for p in outd.iterdir() if p.name.startswith(kind))
    return {"ok": True, "files": files, "duration": dur, "note": "Наложи поверх видео; ссылка в MP4 не кликабельна - дублируй в описании."}
