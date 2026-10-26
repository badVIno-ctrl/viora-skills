"""Frame and pixel analysis used by the QA gate (numpy + OpenCV only)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

from ..util import ShortsError

BLOCK = 40


def sample(path: Path | str, fps: float, w: int = 1080, h: int = 1920, start: float = 0.0,
           duration: float | None = None) -> tuple[np.ndarray, list[float]]:
    """Decode frames at `fps` (RGB uint8, N x h x w x 3)."""
    cmd = ["ffmpeg", "-loglevel", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(path)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise ShortsError(p.stderr.decode()[-300:])
    n = len(p.stdout) // (w * h * 3)
    arr = np.frombuffer(p.stdout[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)
    return arr, [start + i / fps for i in range(n)]


def frame_at(path: Path | str, t: float) -> np.ndarray:
    cmd = ["ffmpeg", "-loglevel", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(path), "-frames:v", "1",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0 or not p.stdout:
        raise ShortsError(f"cannot read frame at {t:.2f}s")
    return np.frombuffer(p.stdout, np.uint8).reshape(1920, 1080, 3).copy()


def luma(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)


def block_stats(gray: np.ndarray, block: int = BLOCK) -> tuple[np.ndarray, np.ndarray]:
    h, w = gray.shape
    hb, wb = h // block, w // block
    g = gray[: hb * block, : wb * block].reshape(hb, block, wb, block)
    return g.mean(axis=(1, 3)), g.std(axis=(1, 3))


def largest_component(mask: np.ndarray) -> int:
    if not mask.any():
        return 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=4)
    return int(stats[1:, cv2.CC_STAT_AREA].max()) if n > 1 else 0


def block_rgb(img: np.ndarray, block: int = BLOCK) -> np.ndarray:
    h, w = img.shape[:2]
    hb, wb = h // block, w // block
    return img[: hb * block, : wb * block].reshape(hb, block, wb, block, 3).mean(axis=(1, 3))


def dead_zones(frames: np.ndarray, times: list[float], window: float = 2.0, flat_std: float = 3.0,
               static_diff: float = 3.0, bg: tuple[int, int, int] | None = None, bg_tol: float = 24.0,
               ignore: list[tuple[float, float, int, int]] | None = None) -> dict:
    """Largest connected area (share of frame) that is flat, static for `window` s and (if given) of the brand
    background colour, i.e. canvas we painted nothing on. White space of a recorded website is content, not dead air.
    `ignore`: (t0, t1, y0, y1) rows that are flat on purpose while shown (cinema bars, the black fields of
    the band layout); they are not counted in windows that touch [t0, t1)."""
    grays = [luma(f) for f in frames]
    stats = [block_stats(g) for g in grays]
    cols = [block_rgb(f) for f in frames] if bg is not None else None
    if len(times) < 2:
        return {"max_share": 0.0, "at": 0.0}
    step = times[1] - times[0]
    k = max(1, int(round(window / step)))
    hb, wb = stats[0][0].shape
    worst, at = 0.0, 0.0
    for i in range(0, len(frames) - k):
        means = np.stack([stats[j][0] for j in range(i, i + k + 1)])
        stds = np.stack([stats[j][1] for j in range(i, i + k + 1)])
        flat = (stds < flat_std).all(axis=0)
        static = (means.max(axis=0) - means.min(axis=0)) < static_diff
        dead = flat & static
        if cols is not None:
            dead &= np.abs(cols[i] - np.array(bg, np.float32)).max(axis=-1) < bg_tol
        for a, b, y0, y1 in ignore or []:
            if a < times[i + k] + 1e-6 and b > times[i] - 1e-6:
                dead[max(0, y0 // BLOCK): max(0, -(-y1 // BLOCK))] = False
        share = largest_component(dead) / (hb * wb)
        if share > worst:
            worst, at = share, times[i]
    return {"max_share": round(worst, 3), "at": round(at, 2)}


def region_activity(frames: np.ndarray, y0: int, y1: int) -> dict:
    """Is a panel alive? mean temporal change and spatial detail."""
    reg = [luma(f[y0:y1]) for f in frames]
    diffs = [float(np.mean(np.abs(a - b))) for a, b in zip(reg, reg[1:])]
    detail = float(np.mean([r.std() for r in reg]))
    return {"motion": round(float(np.mean(diffs)) if diffs else 0.0, 2),
            "still_share": round(float(np.mean([d < 0.5 for d in diffs])) if diffs else 1.0, 2),
            "detail": round(detail, 2)}


def static_runs(frames: np.ndarray, times: list[float], y0: int, y1: int, thr: float = 0.6) -> dict:
    """Longest run without visible change inside a region."""
    reg = [cv2.resize(luma(f[y0:y1]), (270, max(1, (y1 - y0) // 4))) for f in frames]
    longest, cur, start, at = 0.0, 0.0, 0.0, 0.0
    step = times[1] - times[0] if len(times) > 1 else 0
    for i in range(1, len(reg)):
        d = float(np.mean(np.abs(reg[i] - reg[i - 1])))
        if d < thr:
            if cur == 0:
                start = times[i - 1]
            cur += step
            if cur > longest:
                longest, at = cur, start
        else:
            cur = 0.0
    return {"longest_still": round(longest, 2), "at": round(at, 2)}


def change_events(frames: np.ndarray, times: list[float], y0: int, y1: int, thr: float = 6.0) -> list[float]:
    """Times of visible changes (cuts, zooms, big overlays) inside a region."""
    reg = [cv2.resize(luma(f[y0:y1]), (135, max(1, (y1 - y0) // 8))) for f in frames]
    out = []
    for i in range(1, len(reg)):
        if float(np.mean(np.abs(reg[i] - reg[i - 1]))) > thr:
            if not out or times[i] - out[-1] > 0.3:
                out.append(times[i])
    return out


def is_blank(img: np.ndarray) -> dict:
    g = luma(img)
    return {"mean": round(float(g.mean()), 1), "std": round(float(g.std()), 1),
            "blank": bool(g.std() < 12 or g.mean() < 8)}


def glow_score(rgba: np.ndarray) -> float:
    """Average thickness (px) of the soft semi-transparent edge around opaque content.
    Anti-aliased text or a hard plate: ~0-2 px. A blur glow: 8+ px."""
    a = rgba[..., 3]
    opaque = (a > 230).astype(np.uint8)
    if opaque.sum() == 0:
        return 0.0
    edge = opaque - cv2.erode(opaque, np.ones((3, 3), np.uint8))
    soft = int(((a > 10) & (a <= 230)).sum())
    return soft / max(1, int(edge.sum()))


def gradient_score(img: np.ndarray, min_run: int = 6, block: int = 16) -> dict:
    """Detect smooth colour ramps (gradient plates/backgrounds): runs of smooth blocks whose mean drifts monotonically."""
    rgb = img[..., :3].astype(np.float32)
    if img.shape[-1] == 4:
        mask = img[..., 3] > 230
    else:
        mask = np.ones(img.shape[:2], bool)
    h, w = rgb.shape[:2]
    hb, wb = h // block, w // block
    if hb < min_run and wb < min_run:
        return {"gradient": False, "run": 0, "delta": 0.0}
    r = rgb[: hb * block, : wb * block].reshape(hb, block, wb, block, 3)
    m = mask[: hb * block, : wb * block].reshape(hb, block, wb, block).all(axis=(1, 3))
    means = r.mean(axis=(1, 3))
    stds = r.std(axis=(1, 3)).max(axis=-1)
    smooth = (stds < 4.0) & m
    best = (0, 0.0)

    def scan(lines_means, lines_smooth):
        nonlocal best
        for lm, ls in zip(lines_means, lines_smooth):
            run_start = 0
            for j in range(1, len(lm) + 1):
                ok = j < len(lm) and ls[j] and ls[j - 1]
                if ok:
                    step = np.abs(lm[j] - lm[j - 1]).max()
                    ok = 0.4 < step < 14
                if not ok:
                    n = j - run_start
                    if n >= min_run:
                        seg = lm[run_start:j]
                        total = float(np.abs(seg[-1] - seg[0]).max())
                        diffs = np.diff(seg, axis=0)
                        mono = float(np.mean(np.sign(diffs) == np.sign(seg[-1] - seg[0])))
                        if total > 30 and mono > 0.7 and (n, total) > best:
                            best = (n, total)
                    run_start = j
    scan(means.transpose(1, 0, 2), smooth.T)  # vertical
    scan(means, smooth)  # horizontal
    return {"gradient": best[0] >= min_run, "run": best[0], "delta": round(best[1], 1)}


def dominant_colors(rgba: np.ndarray, min_share: float = 0.04) -> list[str]:
    """Distinct non-neutral colour families covering >= min_share of opaque pixels (neutrals counted separately)."""
    a = rgba[..., 3] > 230 if rgba.shape[-1] == 4 else np.ones(rgba.shape[:2], bool)
    px = rgba[..., :3][a].astype(np.int32)
    if len(px) == 0:
        return []
    hsv = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2HSV).reshape(-1, 3)
    sat = hsv[:, 1] > 60
    fam = []
    neutral_share = 1 - sat.mean()
    if neutral_share > min_share:
        fam.append("neutral")
    hues = hsv[sat, 0] // 15  # 12 hue families
    for hval, cnt in zip(*np.unique(hues, return_counts=True)):
        if cnt / len(px) >= min_share:
            fam.append(f"hue{int(hval) * 30}")
    return fam


def dhash(img: np.ndarray, size: int = 16) -> str:
    g = cv2.resize(luma(img), (size + 1, size))
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return "".join("1" if b else "0" for b in bits)


def hamming(a: str, b: str) -> int:
    return sum(x != y for x, y in zip(a, b)) + abs(len(a) - len(b))


def decode_qr(img: np.ndarray) -> list[str]:
    det = cv2.QRCodeDetector()
    out = []
    for scale in (1.0, 0.75, 0.5):
        im = img if scale == 1.0 else cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        try:
            ok, texts, _, _ = det.detectAndDecodeMulti(cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
        except cv2.error:
            ok, texts = False, []
        if ok:
            out += [t for t in texts if t]
        if out:
            break
        try:
            t, _, _ = det.detectAndDecode(cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
        except cv2.error:
            t = ""
        if t:
            out.append(t)
            break
    return out


def text_pixels(img: np.ndarray, box: list[int], colors: list[tuple[int, int, int]], tol: int = 40) -> float:
    """Share of pixels in box that match any of the given colours."""
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(img.shape[1], x1), min(img.shape[0], y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    reg = img[y0:y1, x0:x1].astype(np.int32)
    m = np.zeros(reg.shape[:2], bool)
    for c in colors:
        m |= (np.abs(reg - np.array(c)).max(axis=-1) < tol)
    return float(m.mean())


def contact_sheet(path: Path | str, out: Path, fps: float = 2.0, cols: int = 8, thumb_w: int = 180) -> list[Path]:
    """Grid PNGs (2 frames per second by default) with time stamps; split into pages of 48 frames."""
    from PIL import Image, ImageDraw

    th = int(thumb_w * 16 / 9)
    frames, times = sample(path, fps, thumb_w, th)
    pages = []
    per = cols * 6
    for p0 in range(0, len(frames), per):
        chunk = frames[p0:p0 + per]
        rows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * thumb_w, rows * (th + 20)), (24, 24, 24))
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(chunk):
            x, y = (i % cols) * thumb_w, (i // cols) * (th + 20)
            sheet.paste(Image.fromarray(f), (x, y + 20))
            d.text((x + 4, y + 4), f"{times[p0 + i]:.1f}s", fill=(230, 230, 230))
        pp = out.parent / f"{out.stem}-{len(pages) + 1}{out.suffix}"
        sheet.save(pp)
        pages.append(pp)
    return pages


# ------------------------------------------------------------------ 1.3: photosensitive flashes (WCAG 2.3.1)

FLASH_DELTA = 0.10   # a change of relative luminance of 10% of the maximum
FLASH_DARK = 0.80    # ... where the darker state is below 0.80
FLASH_MAX = 3        # no more than 3 flashes in any 1 s


def rel_luminance(img: np.ndarray) -> np.ndarray:
    """sRGB -> relative luminance 0..1 (WCAG 2 definition)."""
    c = img.astype(np.float32) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]


def transitions(series: list[float] | np.ndarray, delta: float = FLASH_DELTA, dark: float = FLASH_DARK) -> list[int]:
    """Indices where a luminance swing of >= delta ends (zig-zag with hysteresis); the darker end < dark.
    Two opposite transitions make one flash."""
    s = [float(v) for v in series]
    if len(s) < 2:
        return []
    out: list[int] = []
    piv, ext, ext_i, d = s[0], s[0], 0, 0
    for i, v in enumerate(s[1:], 1):
        if d == 0:
            if abs(v - piv) >= delta:
                d, ext, ext_i = (1 if v > piv else -1), v, i
        elif (v - ext) * d > 0:
            ext, ext_i = v, i
        elif abs(v - ext) >= delta:
            if min(piv, ext) < dark:
                out.append(ext_i)
            piv, ext, ext_i, d = ext, v, i, -d
    if d != 0 and abs(ext - piv) >= delta and min(piv, ext) < dark:
        out.append(ext_i)
    return out


def flash_report(path: Path | str, fps: float = 30.0, w: int = 72, h: int = 128) -> dict:
    """Flashes per 1 s window over the whole frame and each quadrant (a quadrant of a phone screen is
    about the 10 degree field of WCAG at reading distance). Red flashes are not measured separately."""
    frames, times = sample(path, fps, w, h)
    if len(frames) < 2:
        return {"max_flashes": 0, "at": 0.0, "region": "frame", "windows_over": 0}
    lum = np.stack([rel_luminance(f) for f in frames])  # N x h x w
    hh, ww = h // 2, w // 2
    regions = {"frame": lum.mean(axis=(1, 2)), "top_left": lum[:, :hh, :ww].mean(axis=(1, 2)),
               "top_right": lum[:, :hh, ww:].mean(axis=(1, 2)), "bottom_left": lum[:, hh:, :ww].mean(axis=(1, 2)),
               "bottom_right": lum[:, hh:, ww:].mean(axis=(1, 2))}
    win = int(round(fps))
    best, at, reg, over = 0.0, 0.0, "frame", set()
    for name, ser in regions.items():
        tr = transitions(ser)
        for k, i in enumerate(tr):
            j = k
            while j + 1 < len(tr) and tr[j + 1] - i < win:
                j += 1
            flashes = (j - k + 1) / 2
            if flashes > best:
                best, at, reg = flashes, times[i], name
            if flashes > FLASH_MAX:
                over.add(round(times[i], 1))
    return {"max_flashes": best, "at": round(at, 2), "region": reg, "windows_over": len(over),
            "over_at": sorted(over)[:6]}
