"""Panel-stack compositor (v2.2): [top loop video] + [speaker-follow main video] + captions + hook + ad card / ad bar.

`python tools/shorts.py stack spec.json [--out FILE]`

spec = {
  "out": "01-interview.mp4",                      # fps is chosen from the MAIN source (24/25/30; 50/60 halve): no uneven resampling
  "main": {"pieces": [{"src": "a.mp4", "start": 0.8, "end": 8.2}, ...], "track": "group|biggest|center", "zoom": 1.0,
           "punch": 0.06,
           "snap": "sentence",                   # v2.2 speech boundaries: sentence (default) | word | off  (speech.py)
           "words": "auto",                      # word timings: auto (whisper > <srt>.words.json > SRT) | whisper | srt | none
           "words_json": "words.json",           # optional: ready word list [{w, s, e}] in source seconds (beats all of the above)
           "allow_open_end": false},             # true = the last piece may end mid-sentence (a deliberate cliffhanger)
                                                 # y/h optional: default fills everything between top panel and ad bar
  "top": {"src": "car.mp4", "start": 10, "h": 540},                          # optional, muted, loops, any source fps
  "captions": {"srt": "x.srt", "style": "clean|aesthetic|karaoke", "accent": "#FFD84D"},   # capstyle.py; SRT in SOURCE time
  "hook": {"text": "БОЛЬШЕ $100 000 ЗА *интервью*", "start": 0.0, "end": 2.2, "style": "headline|classic"},
  "adbar": {"brand": "Quattro VPN", "url": "https://t.me/...", "tg": "QuattroVPN_BOT", "sub": "VPN в Telegram"},   # reference bar
  "banner": {..., "slot": "auto|below|filler|above|manual"},                 # floating card: NEVER over the main picture (adslot.py)
  "label": {"text": "ИИ-персонаж", "pos": "tl|tr", "start": 0, "end": null},   # 2.3 disclosure pill(s) (AI / ad marking), or a list
}
v2.2: the ad card gets its own slot (adslot.resolve), cuts snap to word/sentence boundaries and the video ends after
the last word with a silent tail (speech.py), captions are placed off faces and off the card (capstyle.py).
Smoothness rules: camera path is precomputed (6 fps detection, per-frame sub-pixel crop, deadband + Gaussian, snap on
cuts); the top video is resampled with the blending `framerate` filter when ratios are not integer; the result is
measured (`motion`), the QR is decoded from a rendered frame (`adbar_qr`), the sound is checked at every join and at
the end (`speech.audio_qa`). Panels, card and speech report are written to `<out>.layout.json`.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import adslot, capstyle, smooth, speech
from .adbar import AdBar, qr_decodes
from .cardbanner import CardBanner, MARGIN
from .config import asset
from .util import ShortsError, hex_to_rgb, log

W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 288, 1920 - 672


def _read_raw(args_in: list, vf: str, w: int, h: int):
    """Yield BGR frames from ffmpeg (exact trimming, constant fps)."""
    cmd = ["ffmpeg", "-v", "quiet", *args_in, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    finally:
        p.stdout.close()
        p.terminate()
        p.wait()


def _probe_wh(path: Path) -> tuple[int, int]:
    i = smooth.probe(path)
    return i["w"], i["h"]


# ------------------------------------------------------------------ captions

def parse_srt(path: Path) -> list[tuple[float, float, str]]:
    def ts(s):
        h, m, r = s.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(r)
    cues = []
    for block in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8").strip()):
        lines = block.strip().split("\n")
        if len(lines) >= 3 and "-->" in lines[1]:
            a, b = [x.strip() for x in lines[1].split("-->")]
            cues.append((ts(a), ts(b), " ".join(lines[2:]).strip()))
    return cues


def caption_chunks(cues, words_per_chunk=3, max_chars=22):
    """Cue -> short chunks with per-word timing proportional to word length (karaoke-style highlight)."""
    chunks = []
    for i, (t0, t1, text) in enumerate(cues):
        nxt = cues[i + 1][0] if i + 1 < len(cues) else t1 + 0.5
        t1 = min(max(t1, t0 + 0.4), nxt - 0.02) if nxt - t1 < 0.35 else t1
        words = text.split()
        groups, cur = [], []
        for w in words:
            if cur and (len(cur) >= words_per_chunk or len(" ".join(cur + [w])) > max_chars):
                groups.append(cur)
                cur = []
            cur.append(w)
        if cur:
            groups.append(cur)
        total = sum(len(w) + 1 for w in words) or 1
        t = t0
        for g in groups:
            share = sum(len(w) + 1 for w in g) / total * (t1 - t0)
            wt, acc = [], t
            gl = sum(len(w) + 1 for w in g)
            for w in g:
                d = share * (len(w) + 1) / gl
                wt.append((acc, acc + d))
                acc += d
            chunks.append({"t0": t, "t1": t + share, "words": g, "wt": wt})
            t += share
    return chunks


def _text_layer(words, active, size, accent, max_w=960):
    font = ImageFont.truetype(str(asset("fonts") / "Montserrat-ExtraBold.ttf"), size)
    sp = font.getlength(" ")
    widths = [font.getlength(w) for w in words]
    total = sum(widths) + sp * (len(words) - 1)
    scale = min(1.0, max_w / total)
    if scale < 1.0:
        font = ImageFont.truetype(str(asset("fonts") / "Montserrat-ExtraBold.ttf"), int(size * scale))
        sp = font.getlength(" ")
        widths = [font.getlength(w) for w in words]
        total = sum(widths) + sp * (len(words) - 1)
    pad = 16
    lay = Image.new("RGBA", (int(total) + pad * 2, int(size * 1.5)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x = pad
    for i, w in enumerate(words):
        col = accent if i == active else (255, 255, 255)
        d.text((x, size * 0.2), w, font=font, fill=col + (255,), stroke_width=max(5, size // 10), stroke_fill=(0, 0, 0, 255))
        x += widths[i] + sp
    return lay


def remap_cues(cues, pieces):
    """SRT times of the SOURCE file -> times of the final video (pieces are cut and joined). Cues are clipped to the pieces."""
    out, off = [], 0.0
    for p in pieces:
        a, b = float(p["start"]), float(p["end"])
        for t0, t1, text in cues:
            lo, hi = max(t0, a), min(t1, b)
            if hi - lo >= 0.12:
                out.append((off + lo - a, off + hi - a, text))
        off += b - a
    return sorted(out)


class Captions:
    def __init__(self, cfg: dict, base: Path, pieces: list | None = None):
        srt = Path(cfg["srt"])
        srt = srt if srt.is_absolute() else base / srt
        cues = parse_srt(srt)
        if cfg.get("mask", True):
            from .subs import mask_profanity
            cues = [(a, b, mask_profanity(t)) for a, b, t in cues]
        if pieces and cfg.get("timebase", "source") == "source" and len({str(p["src"]) for p in pieces}) == 1:
            cues = remap_cues(cues, pieces)       # "final" timebase: SRT already matches the finished video
        self.chunks = caption_chunks(cues, int(cfg.get("words", 3)))
        self.y = int(cfg.get("y", 1040))
        self.size = int(cfg.get("size", 66))
        self.accent = hex_to_rgb(cfg.get("accent", "#FFD84D"))
        self.cache: dict = {}

    def layer_at(self, t: float):
        for c in self.chunks:
            if c["t0"] <= t < c["t1"] + 0.04:
                act = 0
                for i, (a, b) in enumerate(c["wt"]):
                    if t >= a:
                        act = i
                key = (id(c), act)
                if key not in self.cache:
                    self.cache[key] = _text_layer(c["words"], act, self.size, self.accent)
                fade = min(1.0, (t - c["t0"]) / 0.07)
                return self.cache[key], fade
        return None, 0.0


def _blend(canvas: np.ndarray, layer: Image.Image, x: int, y: int, alpha: float = 1.0):
    """Alpha-blend an RGBA PIL layer onto a BGR canvas at (x, y) with clipping."""
    lw, lh = layer.size
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + lw, canvas.shape[1]), min(y + lh, canvas.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    arr = np.asarray(layer.crop((x0 - x, y0 - y, x1 - x, y1 - y)))
    a = (arr[..., 3:4].astype(np.float32) / 255.0) * alpha
    roi = canvas[y0:y1, x0:x1].astype(np.float32)
    rgb = arr[..., 2::-1].astype(np.float32)
    canvas[y0:y1, x0:x1] = (roi * (1 - a) + rgb * a).astype(np.uint8)



# ------------------------------------------------------------------ main

def layout_for(spec: dict) -> dict:
    """Panel rectangles without an ad card (2.1 API). Nothing is left empty: top video (if any) + main picture + ad bar,
    uncovered rows are listed in `fill` (blurred copy of the main picture)."""
    return adslot.resolve(spec, None)


class _Words:
    """Word timings per source window (source seconds), best first:
    whisper (precise, punctuation) > SRT text aligned to `<srt>.words.json` (YouTube word starts) > SRT cues spread by length.
    Caption TEXT prefers the SRT (it may be corrected by hand), its TIMES come from the best timing source."""

    def __init__(self, spec: dict, res, lang: str):
        main, caps = spec["main"], spec.get("captions") or {}
        self.mode = str(main.get("words", "auto")).lower()
        if self.mode not in ("auto", "whisper", "srt", "none", "off"):
            raise ShortsError(f"main.words '{self.mode}': use auto | whisper | srt | none")
        self.lang, self.res = lang, res
        srcs = {str(p["src"]) for p in main["pieces"]}
        self.srt_by_src: dict[str, Path] = {str(p["src"]): res(p["srt"]) for p in main["pieces"] if p.get("srt")}
        if caps.get("srt") and caps.get("timebase", "source") == "source" and len(srcs) == 1:
            self.srt_by_src.setdefault(next(iter(srcs)), res(caps["srt"]))
        self.json_by_src: dict[str, Path] = {str(p["src"]): res(p["words_json"]) for p in main["pieces"] if p.get("words_json")}
        if main.get("words_json") and len(srcs) == 1:
            self.json_by_src.setdefault(next(iter(srcs)), res(main["words_json"]))
        self._cues: dict = {}
        self._json: dict = {}
        self.used: set[str] = set()

    def cues(self, srt: Path):
        if srt not in self._cues:
            self._cues[srt] = parse_srt(srt) if srt.exists() else []
        return self._cues[srt]

    def srt_text(self, src, a: float, b: float) -> list[dict] | None:
        srt = self.srt_by_src.get(str(src))
        if not srt:
            return None
        return speech.words_from_srt([c for c in self.cues(srt) if c[1] > a and c[0] < b])

    def timing(self, src, a: float, b: float) -> list[dict] | None:
        if self.mode in ("none", "off"):
            return None
        jf = self.json_by_src.get(str(src))
        if jf:                                   # word list given (whisper `transcribe` output etc.), source seconds
            if jf not in self._json:
                d = json.loads(jf.read_text(encoding="utf-8"))
                self._json[jf] = d.get("words", d) if isinstance(d, dict) else d
            self.used.add("words_json")
            return [w for w in self._json[jf] if a <= float(w["s"]) <= b]
        if self.mode in ("auto", "whisper"):
            ws = speech.whisper_words(self.res(src), a, b, self.lang)
            if ws is None and self.mode == "whisper":
                raise ShortsError("main.words=whisper, but faster-whisper is not available (pip install faster-whisper)")
            if ws:
                self.used.add("whisper")
                return ws
        txt = self.srt_text(src, a, b)
        if not txt:
            return None
        side = speech.sidecar_words(self.srt_by_src.get(str(src)))
        if side:
            self.used.add("srt + youtube word times")
            return speech.align_text(txt, [w for w in side if a - 1 <= float(w["s"]) <= b + 1])
        self.used.add("srt cues (approximate)")
        return txt

    def display(self, piece: dict) -> list[dict]:
        """Caption words of a (snapped) piece, source seconds."""
        a, b = float(piece["start"]), float(piece["end"])
        ctx = piece.get("_ctx")
        if ctx is None:
            ctx = speech._clean(self.timing(piece["src"], a - 1, b + 1) or [])
        txt = self.srt_text(piece["src"], a - 1, b + 1)
        if txt:
            return speech.align_text(txt, ctx) if ctx else txt
        return ctx


def _timeline_words(pieces: list[dict], per_piece: list[list[dict]]) -> list[dict]:
    """Source-second words of every piece -> final-video seconds (only words said inside the kept, audible range)."""
    out, off = [], 0.0
    for p, ws in zip(pieces, per_piece):
        a, b = float(p["start"]), float(p["end"])
        m = float(p.get("mute_from") or b)
        for w in ws or []:
            s, e = float(w["s"]), float(w.get("e", float(w["s"]) + 0.3))
            if s >= a - 0.03 and s < m - 0.06:
                s, e = max(s, a), min(e, m)
                out.append({"w": w["w"], "s": round(off + s - a, 3), "e": round(off + max(e, s + 0.06) - a, 3)})
        off += (b - a) + float(p.get("hold") or 0.0)
    return out


def _glued(pieces: list[dict], i: int, j: int) -> bool:
    return (0 <= i < len(pieces) and 0 <= j < len(pieces) and str(pieces[i]["src"]) == str(pieces[j]["src"])
            and abs(float(pieces[i]["end"]) - float(pieces[j]["start"])) < 0.05)


def _audio_chain(i: int, p: dict, pieces: list[dict], length: float) -> str:
    """Per-piece sound: 12 ms fade-in / 20 ms fade-out at every real join (no clicks), the cut-off next word faded out
    (`mute_from`), the final tail faded softly, silence padded for `hold`."""
    a, b = float(p["start"]), float(p["end"])
    d = b - a
    f = [f"[{i}:a]aresample=48000", "aformat=channel_layouts=stereo"]
    if not _glued(pieces, i - 1, i):
        f.append("afade=t=in:st=0:d=0.012")
    if p.get("mute_from"):
        f.append(f"afade=t=out:st={max(0.0, float(p['mute_from']) - a):.3f}:d=0.03")
    elif i == len(pieces) - 1:
        ws = p.get("_words") or []
        last_e = max((float(w["e"]) for w in ws), default=b - 0.4) - a
        st = min(max(last_e + 0.08, d - 0.3), max(0.0, d - 0.05))
        f.append(f"afade=t=out:st={st:.3f}:d={max(0.05, d - st):.3f}")
    elif not _glued(pieces, i, i + 1):
        f.append(f"afade=t=out:st={max(0.0, d - 0.02):.3f}:d=0.02")
    f.append(f"apad,atrim=end={length:.3f},asetpts=N/SR/TB[a{i}]")
    return ",".join(f)


def _crop_geom(sw: int, sh: int, fx: float, fy: float, zoom: float, pz: float, ph: int, pw: int = W):
    """Crop window of the main picture (same maths as the frame loop): x0, y0, cw, ch in source px."""
    z = zoom * pz
    ch = sh / z
    cw = ch * pw / ph
    if cw > sw:
        cw, ch = sw, sw * ph / pw
    cy_top = fy - ch * 0.38 if z > 1.01 or ch < sh - 1 else (sh - ch) / 2
    x0 = min(max(fx - cw / 2, 0.0), sw - cw)
    y0 = min(max(cy_top, 0.0), sh - ch)
    return x0, y0, cw, ch, cy_top


def render_stack(spec: dict, base: Path, out: Path | None = None, check: bool = True) -> dict:
    main = spec["main"]
    base = Path(base)
    out = Path(out or base / spec.get("out", "short.mp4"))
    out.parent.mkdir(parents=True, exist_ok=True)
    lang = str(spec.get("lang") or (spec.get("captions") or {}).get("lang") or "ru")

    def res(p):
        p = Path(p)
        return p if p.is_absolute() else base / p

    raw_pieces = [dict(p) for p in main["pieces"]]
    if not raw_pieces:
        raise ShortsError("main.pieces is empty")
    src_info = {}
    for p in raw_pieces:
        if str(p["src"]) not in src_info:
            src_info[str(p["src"])] = smooth.probe(res(p["src"]))

    # ---- speech boundaries (before anything is rendered: a cut inside a word is an error, not a QA note)
    snap = str(main.get("snap", "sentence")).lower()
    if snap not in ("sentence", "word", "off"):
        raise ShortsError(f"main.snap '{snap}': use sentence | word | off")
    words = _Words(spec, res, lang)
    env_cache: dict = {}

    def env_of(src, a, b):
        key = (str(src), round(a, 2), round(b, 2))
        if key not in env_cache:
            env_cache[key] = speech.envelope(res(src), a, b)
        return env_cache[key]

    pieces, adjust = speech.snap_pieces(raw_pieces, words.timing, env_of, snap,
                                        {k: v["duration"] for k, v in src_info.items() if v.get("duration")})
    problems = speech.check_pieces(pieces, snap, bool(main.get("allow_open_end", False))) if snap != "off" else []
    errors = [p for p in problems if p["level"] == "error"]
    if errors:
        raise ShortsError("speech boundaries: " + "; ".join(f"piece {p['piece'] + 1}: {p['what']}" for p in errors)
                          + ". Set the piece end to one of the possible ends, or main.snap=word for edited speech without"
                          " pauses, or main.allow_open_end=true for a deliberate open end")
    for r in adjust:
        if r["start"] or r["end"]:
            log.info("speech: piece %d %s -> %s %s %s", r["piece"] + 1, r["from"], r["to"], r["start"], r["end"])

    durs = [float(p["end"]) - float(p["start"]) for p in pieces]
    holds = [float(p.get("hold") or 0.0) for p in pieces]
    infos = [src_info[str(p["src"])] for p in pieces]
    fps = int(spec["fps"]) if spec.get("fps") else smooth.pick_fps(infos[0]["fps"])
    bounds = np.concatenate([[0.0], np.cumsum([d + h for d, h in zip(durs, holds)])])
    nb = [int(round(x * fps)) for x in bounds]
    n_piece = [nb[i + 1] - nb[i] for i in range(len(pieces))]
    n_play = [min(n_piece[i], int(round(durs[i] * fps))) for i in range(len(pieces))]
    n_total = nb[-1]
    total = n_total / fps

    # ---- layout: the ad card first, then the panels around it
    banner = None
    bcfg = spec.get("banner")
    if bcfg:
        banner = CardBanner(bcfg, base)
    lay = adslot.resolve(spec, (banner.w, banner.h) if banner else None)
    mx, py, mw, ph = lay["main"]
    vis_bottom = adslot.visible_bottom(lay)
    center = lay.get("layout") == "center"
    zoom = float(main.get("zoom", 1.0))
    punch = float(main.get("punch", 0.0))

    work = out.with_suffix(".work")
    work.mkdir(exist_ok=True)
    wav = work / "audio.wav"
    ins, fc = [], []
    for i, p in enumerate(pieces):
        ins += ["-ss", f"{float(p['start']):.3f}", "-t", f"{durs[i]:.3f}", "-i", str(res(p["src"]))]
        fc.append(_audio_chain(i, p, pieces, n_piece[i] / fps))
    chain = "".join(f"[a{i}]" for i in range(len(pieces))) + f"concat=n={len(pieces)}:v=0:a=1[a]"
    af = "[a]loudnorm=I=-14:TP=-1.5:LRA=11[o]" if spec.get("loudnorm", True) else "[a]anull[o]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fc) + ";" + chain + ";" + af,
                    "-map", "[o]", "-ar", "48000", str(wav)], check=True)
    jidx = [i for i in range(len(pieces) - 1) if not _glued(pieces, i, i + 1)]
    joins = [nb[i + 1] / fps for i in jidx]
    clean = [speech.join_is_clean(pieces[i], pieces[i + 1]) for i in jidx]
    aqa = speech.audio_qa(wav, joins, total, clean) if snap != "off" else {"ok": True, "skipped": "snap off"}

    # ---- camera paths (one per piece) + where the faces are on the canvas
    track = main.get("track", True)
    mode = "group" if track in (True, "group") else ("biggest" if track == "biggest" else "center")
    ratio = mw / ph
    capcfg = spec.get("captions") or {}
    want_faces = bool(capcfg) or bool(bcfg and bcfg.get("over_video"))
    paths = []
    for i, p in enumerate(pieces):
        ch0 = infos[i]["h"] / zoom
        cwf = min(1.0, ch0 * ratio / max(infos[i]["w"], 1))
        paths.append(smooth.build_path(res(p["src"]), float(p["start"]), durs[i], fps, mode, crop_w_frac=cwf,
                                       want_faces=want_faces))

    def geom(i, k):
        sw_, sh_ = infos[i]["w"], infos[i]["h"]
        fx, fy = paths[i].at(min(k, n_play[i] - 1))
        pz = 1.0 + punch * max(0.0, 1.0 - (k / fps) / 0.35) if punch else 1.0     # short push-in at the start of a piece
        if k >= n_play[i] and n_piece[i] > n_play[i]:                              # held last frame: slow push-in, never a dead freeze
            pz *= 1.0 + 0.035 * (k - n_play[i] + 1) / max(1, n_piece[i] - n_play[i])
        return fx, fy, pz, _crop_geom(sw_, sh_, fx, fy, zoom, pz, ph, mw)

    face_rects: list[list] = []          # per output frame: faces in canvas px (x0, y0, x1, y1), clipped to the main panel
    for i in range(len(pieces)):
        for k in range(n_piece[i]):
            fs = paths[i].faces_at(min(k, n_play[i] - 1)) if want_faces else []
            if not fs:
                face_rects.append([])
                continue
            _, _, _, (x0, y0, cw, ch, _) = geom(i, k)
            sx, sy = mw / cw, ph / ch
            rr = []
            for bx0, by0, bx1, by1 in fs:
                r = (mx + (bx0 - x0) * sx, py + (by0 - y0) * sy, mx + (bx1 - x0) * sx, py + (by1 - y0) * sy)
                if r[2] > mx and r[0] < mx + mw and r[3] > py and r[1] < py + ph:
                    rr.append(r)
            face_rects.append(rr)

    def faces(t0, t1):
        a, b = max(0, int(t0 * fps)), min(len(face_rects), int(t1 * fps) + 1)
        seen = []
        for n in range(a, b, 2):
            seen += face_rects[n]
        return seen

    # ---- overlays: card, hook, captions (placed around faces, the card and the hook)
    obstacles = []
    if banner:
        b_start = float(bcfg.get("start", 2.0))
        b_end = float(bcfg["end"]) if bcfg.get("end") is not None else None
        cx_, cy_, cw_, chh = lay["card"]
        obstacles.append(((cx_ - 12, cy_ - 12, cx_ + cw_ + 12, cy_ + chh + 12), b_start, b_end if b_end is not None else total + 1))
    labels = []                           # 2.3 disclosure pills: dict or list of dicts {text, pos tl|tr, y, size, start, end}
    lab_y = {"tl": 136, "tr": 136}
    for lb in ([spec["label"]] if isinstance(spec.get("label"), dict) else list(spec.get("label") or [])):
        lb = dict(lb)
        if not str(lb.get("text", "")).strip():
            continue
        img = _label_layer(str(lb["text"]).strip(), int(lb.get("size", 34)))
        pos = "tr" if lb.get("pos") == "tr" else "tl"
        lx = 48 if pos == "tl" else W - 48 - img.width
        ly = int(lb["y"]) if lb.get("y") is not None else lab_y[pos]
        lab_y[pos] = ly + img.height + 10
        lb.update({"start": float(lb.get("start", 0.0)), "xy": (lx, ly), "img": img})
        labels.append(lb)
        obstacles.append(((lx, ly, lx + img.width, ly + img.height), lb["start"],
                          float(lb["end"]) if lb.get("end") is not None else 1e9))
    label_bottom = max((lb["xy"][1] + lb["img"].height for lb in labels), default=0)
    hook = dict(spec["hook"]) if spec.get("hook") else None
    hook_img = None
    if hook:
        hstyle = hook.get("style", "headline")
        hook_img = capstyle.headline_layer(hook["text"], int(hook.get("size", 96 if hstyle == "headline" else 84)),
                                           hook.get("accent") or capcfg.get("accent") or "#FFD84D", style=hstyle)
        hook.setdefault("start", 0.0)
        hook.setdefault("end", 2.2)
        bb = hook_img.getbbox() or (0, 0, W, hook_img.height)
        if hook.get("y") is None:         # top of the main picture, else the seam / the top of the screen: never the face
            fs_h = faces(float(hook["start"]), float(hook["end"]))
            y_min = 150 if not labels else max(150, label_bottom + 10 - bb[1])
            cands = [max(py + 40, y_min)] + ([max(y_min, lay["top"][3] - (bb[3] - bb[1]) // 2 - bb[1])] if lay["top"] else []) + [y_min]
            if center:                    # the title band above the inset picture comes first
                cands.insert(0, max(y_min, py - (bb[3] - bb[1]) - bb[1] - 18))

            def _hits(y):
                r = (bb[0], y + bb[1], bb[2], y + bb[3])
                return sum(capstyle._ov(r, capstyle._core(f)) for f in fs_h)
            hook["y"] = min(cands, key=lambda y: (_hits(y) > 0, _hits(y), cands.index(y)))
        obstacles.append(((bb[0], int(hook["y"]) + bb[1], bb[2], int(hook["y"]) + bb[3]), float(hook["start"]), float(hook["end"]) + 0.3))
    track_caps = None
    cap_rep = None
    if capcfg and capcfg.get("enabled", True) is not False:
        if capcfg.get("timebase", "source") == "final" and capcfg.get("srt"):
            srt = res(capcfg["srt"])
            tw = speech.words_from_srt(parse_srt(srt))
            side = speech.sidecar_words(srt)
            tl_words = speech.align_text(tw, side) if side else tw
        else:
            tl_words = _timeline_words(pieces, [words.display(p) for p in pieces])
        zone = (max(40, mx + 20), max(py, capstyle.TEXT_TOP), min(W - 40, mx + mw - 20), min(py + ph, vis_bottom))
        if lay.get("bar"):
            zone = (zone[0], zone[1], zone[2], min(zone[3], lay["bar"][1] - 20))
        seam_zones = []
        if lay["top"] and capcfg.get("seam", True) is not False:
            th_ = lay["top"][3]               # fallback: the seam between the panels (bottom of the top picture)
            if th_ >= 200:
                seam_zones.append((40, max(capstyle.TEXT_TOP, th_ - 200), W - 40, min(th_ + 110, zone[3])))
        if tl_words:
            track_caps = capstyle.CaptionTrack(tl_words, capcfg, zone, faces, obstacles, lang, extra=seam_zones)
            on_face, on_face_at, in_seam = 0, [], 0
            for ch in track_caps.chunks:
                r = (ch.x, ch.y, ch.x + ch.bw, ch.y + ch.bh)
                if any(capstyle._ov(r, capstyle._core(f)) > 0.04 * ch.bw * ch.bh for f in faces(ch.t0, ch.t1)):
                    on_face += 1
                    on_face_at.append(round(ch.t0, 2))
                if r[1] < zone[1] or r[3] > zone[3]:
                    in_seam += 1
            cap_rep = {"style": track_caps.style, "chunks": len(track_caps.chunks), "words": len(tl_words),
                       "on_face": on_face, "zone": list(zone),
                       **({"on_face_at": on_face_at} if on_face_at else {}),
                       **({"compact": True} if track_caps.compact else {}),
                       **({"seam": [list(z) for z in seam_zones], "in_seam": in_seam} if seam_zones else {}),
                       "text": [[round(c.t0, 2), " ".join(w.text for w in c.words)] for c in track_caps.chunks[:120]]}
        else:
            cap_rep = {"style": capcfg.get("style", "clean"), "chunks": 0, "words": 0,
                       "note": "no words for captions (no SRT, whisper unavailable)"}
    bar = AdBar(spec["adbar"], base) if spec.get("adbar") else None

    top_iter = None
    topcfg = spec.get("top")
    th = lay["top"][3] if lay["top"] else 0
    if topcfg and th:
        ti = smooth.probe(res(topcfg["src"]))
        z = float(topcfg.get("zoom", 1.0))   # >1 crops in: hides channel watermarks
        vf = (smooth.resample_filter(ti["fps"], fps) + f",scale={int(W * z)}:{int(th * z)}:force_original_aspect_ratio=increase,"
              f"crop={W}:{th}:x=(iw-ow)/2:y=(ih-oh)/2")
        args = ["-stream_loop", "-1", "-ss", str(topcfg.get("start", 0)), "-i", str(res(topcfg["src"])), "-t", f"{total + 1:.3f}"]
        top_iter = _read_raw(args, vf, W, th)

    def main_frames():
        for i, p in enumerate(pieces):
            sw, sh = infos[i]["w"], infos[i]["h"]
            args = ["-ss", f"{float(p['start']):.3f}", "-t", f"{durs[i]:.3f}", "-i", str(res(p["src"]))]
            vf = smooth.resample_filter(infos[i]["fps"], fps)
            k, last = 0, None
            for fr in _read_raw(args, vf, sw, sh):
                if k >= n_play[i]:
                    break
                yield i, k, fr
                last, k = fr, k + 1
            if last is None:
                last = np.zeros((sh, sw, 3), np.uint8)
            while k < n_piece[i]:              # source ran short / `hold`: the last frame (slow push-in in geom)
                yield i, k, last
                k += 1

    enc = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", spec.get("preset", "medium"), "-crf", "17",
           "-maxrate", "14M", "-bufsize", "28M", "-g", str(fps * 2), "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)]
    inset_mask, inset_shadow = _inset_masks(mw, ph, lay.get("shape", "rect")) if center else (None, None)
    proc = subprocess.Popen(enc, stdin=subprocess.PIPE)
    seam_shadow = np.linspace(0.55, 0.0, 28, dtype=np.float32)[:, None, None]
    fills = [r for r in lay.get("fill") or [] if r[3] > 0]
    n = 0
    canvas = np.zeros((H, W, 3), np.uint8)
    try:
        for i, k, fr in main_frames():
            if n >= n_total:
                break
            t = n / fps
            fx, fy, pz, (x0, y0, cw, ch, cy_top) = geom(i, k)
            panel = smooth.crop_resize(fr, fx, cy_top, cw, ch, mw, ph)
            if center:                                  # 2.3: blurred full-screen copy + sharp inset picture with a soft shadow
                canvas[:] = _center_bg(panel)
                _paste_inset(canvas, panel, mx, py, inset_mask, inset_shadow)
            else:
                canvas[py:py + ph] = panel[: H - py] if py + ph > H else panel
            if fills and not center:                    # rows no panel covers: blurred copy of the main picture, never black
                small = cv2.GaussianBlur(cv2.resize(panel, (54, 96), interpolation=cv2.INTER_AREA), (0, 0), 2)
                bg = (cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32) * 0.55).astype(np.uint8)
                for _, fy0, _, fh in fills:
                    canvas[fy0:fy0 + fh] = bg[fy0:fy0 + fh]
                    if fy0 == py + ph and fh > 28:      # soft shadow under the main picture
                        seg = canvas[fy0:fy0 + 28].astype(np.float32)
                        canvas[fy0:fy0 + 28] = (seg * (1 - seam_shadow)).astype(np.uint8)
            if top_iter is not None:
                tf = next(top_iter, None)
                if tf is not None:
                    canvas[0:th] = tf
                    seg = canvas[th:th + 28].astype(np.float32)
                    canvas[th:th + 28] = (seg * (1 - seam_shadow)).astype(np.uint8)
            if hook and float(hook["start"]) <= t < float(hook["end"]) + 0.3:
                kk = _ease(min(1.0, (t - float(hook["start"])) / 0.18))
                if t > float(hook["end"]):
                    kk *= max(0.0, 1 - (t - float(hook["end"])) / 0.3)
                _blend(canvas, hook_img, 0, int(hook["y"]) + int((1 - kk) * 14), kk)
            if track_caps is not None:
                track_caps.draw(canvas, t, _blend)
            for lb in labels:
                if lb["start"] <= t and (lb.get("end") is None or t < float(lb["end"])):
                    _blend(canvas, lb["img"], lb["xy"][0], lb["xy"][1], 0.92)
            if bar is not None:
                canvas[H - bar.h:] = (14, 17, 22)
                off = bar.offset(t, total)
                if off is not None:
                    y0b = H - bar.h + off
                    canvas[y0b:H] = bar.frame(t - bar.start)[: H - y0b]
            if banner and t >= b_start and (b_end is None or t < b_end):
                cx_, cy_, _, _ = lay["card"]
                _blend(canvas, banner.frame(t - b_start, None if b_end is None else b_end - b_start), cx_ - MARGIN, cy_ - MARGIN)
            proc.stdin.write(canvas.tobytes())
            n += 1
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise ShortsError("ffmpeg failed while encoding the stack")
    for f in work.glob("*"):
        f.unlink()
    work.rmdir()

    ad = None
    if banner:
        sampled = [[[r[0], r[1], r[2] - r[0], r[3] - r[1]] for r in face_rects[m]] for m in range(0, len(face_rects), 5)]
        caprects = [r for t0, t1, r in (track_caps.rects() if track_caps else [])
                    if t1 > b_start and (b_end is None or t0 < b_end)]
        ad = {"slot": lay["slot"], "card": lay["card"], "notes": lay["notes"],
              "problems": adslot.check(lay, sampled if bcfg.get("over_video") else None, caprects)}
    speech_rep = {"snap": snap, "words": sorted(words.used) or ["none"], "adjustments": adjust, "problems": problems,
                  "joins": speech.join_texts(pieces), "audio_qa": aqa,
                  "pieces": [{"src": str(p["src"]), "start": p["start"], "end": p["end"],
                              **({"hold": p["hold"]} if p.get("hold") else {}),
                              **({"mute_from": p["mute_from"]} if p.get("mute_from") else {})} for p in pieces]}
    result = {"out": str(out), "frames": n, "fps": fps, "duration": round(n / fps, 2), "layout": lay,
              "speech": speech_rep, **({"ad": ad} if ad else {}), **({"captions": cap_rep} if cap_rep else {})}
    side = {"fps": fps, "panels": lay, "adbar": bool(bar), "url": (spec.get("adbar") or {}).get("url"),
            "speech": speech_rep, **({"ad": ad} if ad else {}), **({"captions": cap_rep} if cap_rep else {})}
    if labels:
        result["labels"] = side["labels"] = [{"text": lb["text"], "xy": list(lb["xy"]), "start": lb["start"], "end": lb.get("end")} for lb in labels]
    if len({str(p["src"]) for p in pieces}) == 1:       # covers are cut from the raw source, never from the finished stack
        side["main_src"] = str(res(pieces[0]["src"]).resolve())
        side["main_range"] = [min(float(p["start"]) for p in pieces), max(float(p["end"]) for p in pieces)]
    out.with_suffix(".layout.json").write_text(json.dumps(side, ensure_ascii=False), encoding="utf-8")
    if check:
        result.update(check_stack(out, lay, (spec.get("adbar") or {}).get("url") if bar else None, bar.start if bar else 0.0))
        extra = []
        if not aqa.get("ok", True):
            extra += [f"sound: {x}" for x in aqa.get("problems", [])]
        if ad and ad["problems"]:
            extra += [f"ad: {x}" for x in ad["problems"]]
        if cap_rep and cap_rep.get("on_face"):
            extra.append(f"captions: {cap_rep['on_face']} chunk(s) touch a face")
        if extra:
            result["ok"] = False
            result["motion"]["problems"] += extra
    return result


def _center_bg(panel: np.ndarray) -> np.ndarray:
    """Full-screen background for the `center` layout: a 9:16 cover crop of the panel, heavily blurred and dimmed."""
    ph_, pw_ = panel.shape[:2]
    cw = min(pw_, int(ph_ * W / H))
    x0 = (pw_ - cw) // 2
    small = cv2.resize(panel[:, x0:x0 + cw], (54, 96), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 2.2)
    return (cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32) * 0.52).astype(np.uint8)


def _inset_masks(w: int, h: int, shape: str):
    """Alpha mask of the inset picture (rect / round 36 px / circle) and a soft shadow mask around it (pad 40 px)."""
    sc = 3
    m = Image.new("L", (w * sc, h * sc), 0)
    d = ImageDraw.Draw(m)
    if shape == "circle":
        d.ellipse((0, 0, w * sc - 1, h * sc - 1), fill=255)
    elif shape == "round":
        d.rounded_rectangle((0, 0, w * sc - 1, h * sc - 1), radius=36 * sc, fill=255)
    else:
        d.rectangle((0, 0, w * sc - 1, h * sc - 1), fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    mask = np.asarray(m, np.float32)[:, :, None] / 255.0
    pad = 40
    sh = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    sh.paste(m, (pad, pad + 10))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    shadow = np.asarray(sh, np.float32)[:, :, None] / 255.0 * 0.6
    return mask, shadow


def _paste_inset(canvas: np.ndarray, panel: np.ndarray, x: int, y: int, mask: np.ndarray, shadow: np.ndarray) -> None:
    pad = 40
    h, w = panel.shape[:2]
    y0, y1, x0, x1 = max(0, y - pad), min(H, y + h + pad), max(0, x - pad), min(W, x + w + pad)
    sh = shadow[y0 - (y - pad):y1 - (y - pad), x0 - (x - pad):x1 - (x - pad)]
    seg = canvas[y0:y1, x0:x1].astype(np.float32)
    canvas[y0:y1, x0:x1] = (seg * (1 - sh)).astype(np.uint8)
    yy0, yy1, xx0, xx1 = max(0, y), min(H, y + h), max(0, x), min(W, x + w)
    p = panel[yy0 - y:yy1 - y, xx0 - x:xx1 - x].astype(np.float32)
    a = mask[yy0 - y:yy1 - y, xx0 - x:xx1 - x]
    seg = canvas[yy0:yy1, xx0:xx1].astype(np.float32)
    canvas[yy0:yy1, xx0:xx1] = (p * a + seg * (1 - a)).astype(np.uint8)


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def check_stack(video: Path, lay: dict, url: str | None, bar_t: float = 0.0) -> dict:
    """Measured, not assumed: duplicate frames per panel and a QR that really decodes from a rendered frame."""
    regions = {k: v for k, v in (("top", lay.get("top")), ("main", lay.get("main"))) if v}
    rep = smooth.motion_report(video, regions)
    out = {"motion": rep, "ok": rep["ok"]}
    if url and lay.get("bar"):
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        nfr = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        ok = False
        for t in (bar_t + 1.2, bar_t + 2.4, bar_t + 0.8):
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(int(t * fps), max(nfr - 2, 0)))
            good, fr = cap.read()
            if good and qr_decodes(fr[lay["bar"][1]:], url):
                ok = True
                break
        cap.release()
        out["adbar_qr"] = ok
        if not ok:
            out["ok"] = False
            rep["problems"].append("ad bar QR does not decode from the rendered video")
    return out


def _label_layer(text: str, size: int = 34) -> Image.Image:
    """Small rounded pill (AI disclosure / ad marking): white text on a dark translucent plate."""
    f = capstyle.font("Montserrat-ExtraBold.ttf", size)
    tw = int(f.getlength(text))
    w, h = tw + 2 * int(size * 0.7), int(size * 1.7)
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=(10, 12, 16, 170), outline=(255, 255, 255, 90), width=2)
    d.text((w / 2, h / 2), text, font=f, fill=(255, 255, 255, 255), anchor="mm")
    return lay


def _hook_layer(text: str, size: int) -> Image.Image:
    font = ImageFont.truetype(str(asset("fonts") / "Montserrat-ExtraBold.ttf"), size)
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= W - 160 or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    lay = Image.new("RGBA", (W, int(size * 1.25 * len(lines)) + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = 6
    for l in lines:
        d.text((W / 2, y), l, font=font, fill=(255, 255, 255, 255), anchor="mt", stroke_width=9, stroke_fill=(0, 0, 0, 255))
        y += int(size * 1.25)
    return lay
