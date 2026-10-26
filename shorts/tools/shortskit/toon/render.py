"""Render a toon story: one self-contained HTML page (runtime JS + fonts + story JSON) driven by window.__seek(t),
captured frame by frame from a headless Chromium canvas (JPEG data URLs), piped to ffmpeg. Deterministic."""
from __future__ import annotations

import asyncio
import base64
import json
import shutil
import subprocess
from pathlib import Path

from ..util import ShortsError

HERE = Path(__file__).resolve().parent
RUNTIME = HERE / "runtime"
ORDER = ["core.js", "chars.js", "props.js", "sets.js", "fx.js", "schemes.js", "ui.js"]
FONTS = {"Montserrat": ("Montserrat-ExtraBold.ttf", 800), "Unbounded": ("Unbounded-Black.ttf", 900),
         "JetBrains Mono": ("JetBrainsMono-Bold.ttf", 700), "Manrope": ("Manrope-Bold.ttf", 700),
         "Oswald": ("Oswald-Bold.ttf", 700), "PT Serif": ("PTSerif-Bold.ttf", 700)}


async def _launch(pw):
    """CPU raster Chromium. The shared browser args force SwiftShader GL (for WebGL screencasts); a 2D canvas on
    SwiftShader is ~50x slower than plain Skia, so the toon renderer launches its own browser without it."""
    from ..config import browser_args, chrome_executable
    drop = {"--ignore-gpu-blocklist", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"}
    args = [a for a in browser_args() if a not in drop] + ["--disable-gpu", "--disable-accelerated-2d-canvas",
                                                           "--disable-gpu-compositing", "--disable-software-rasterizer"]
    return await pw.chromium.launch(executable_path=chrome_executable(), args=args, headless=True)


def fonts_dir() -> Path:
    return HERE.parents[2] / "assets" / "fonts"


def runtime_js() -> str:
    parts = []
    for name in ORDER:
        p = RUNTIME / name
        if p.exists():
            parts.append(f"/* ---- {name} ---- */\n" + p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def font_css() -> str:
    css = []
    for fam, (fn, weight) in FONTS.items():
        p = fonts_dir() / fn
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            css.append(f"@font-face{{font-family:'{fam}';src:url(data:font/ttf;base64,{b64}) format('truetype');font-weight:{weight};font-style:normal;}}")
    return "\n".join(css)


def build_html(story: dict) -> str:
    data = json.dumps(story, ensure_ascii=False).replace("</", "<\\/")
    probe = "".join(f"<span style=\"font-family:'{f}';font-weight:{w}\">Аа Zz 0</span>" for f, (_, w) in FONTS.items())
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_css()}
html,body{{margin:0;background:#000;overflow:hidden}}canvas{{display:block}}#fp{{position:absolute;left:-9999px;top:0}}</style></head>
<body><canvas id="c"></canvas><div id="fp">{probe}</div><script>{runtime_js()}
TOON.init({data});</script></body></html>"""


async def _open(browser, html_path: Path, w: int, h: int):
    ctx = await browser.new_context(viewport={"width": min(w, 1920), "height": min(h, 1920)}, device_scale_factor=1)
    page = await ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    await page.goto(Path(html_path).resolve().as_uri(), wait_until="load", timeout=120000)
    await page.evaluate("async () => { await document.fonts.ready; const fs=['800 40px Montserrat','900 40px Unbounded','700 40px \"JetBrains Mono\"','700 40px Manrope'];"
                        " for (const f of fs) { try { await document.fonts.load(f, 'Аа'); } catch(e) {} } return true; }")
    if errors:
        raise ShortsError("toon runtime error: " + "; ".join(errors[:3]))
    return ctx, page, errors


async def _frames(html_path: Path, w: int, h: int, times: list[float], q: float = 0.92) -> list[bytes]:
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        br = await _launch(pw)
        try:
            ctx, page, errors = await _open(br, html_path, w, h)
            out = []
            for t in times:
                b64 = await page.evaluate("([t, q]) => { window.__seek(t); return TOON.frameJPEG(q); }", [t, q])
                if errors:
                    raise ShortsError("toon runtime error at t=%.2f: %s" % (t, "; ".join(errors[:3])))
                out.append(base64.b64decode(b64))
            await ctx.close()
            return out
        finally:
            await br.close()


async def _evaluate(html_path: Path, w: int, h: int, js: str):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        br = await _launch(pw)
        try:
            ctx, page, errors = await _open(br, html_path, w, h)
            out = await page.evaluate("() => " + js)
            await ctx.close()
            return out
        finally:
            await br.close()


def evaluate(story: dict, js: str, work: Path):
    """Evaluate a JS expression in a loaded runtime page (catalogue dump, tests)."""
    work.mkdir(parents=True, exist_ok=True)
    html = work / "toon-eval.html"
    html.write_text(build_html(story), encoding="utf-8")
    return asyncio.run(_evaluate(html, story["W"], story["H"], js))


def snapshots(story: dict, times: list[float], work: Path, q: float = 0.92) -> list[bytes]:
    work.mkdir(parents=True, exist_ok=True)
    html = work / "toon.html"
    html.write_text(build_html(story), encoding="utf-8")
    return asyncio.run(_frames(html, story["W"], story["H"], times, q))


async def _render_range(br, html_path, w, h, fps, k0, k1, sink, errors_out):
    ctx, page, errors = await _open(br, html_path, w, h)
    try:
        for k in range(k0, k1):
            b64 = await page.evaluate("([t, q]) => { window.__seek(t); return TOON.frameJPEG(q); }", [k / fps, 0.9])
            if errors:
                errors_out.extend(errors)
                return
            await sink(k, base64.b64decode(b64))
    finally:
        await ctx.close()


async def _render_all(html_path: Path, w: int, h: int, fps: int, n: int, out_video: Path, workers: int, crf: int, preset: str,
                      progress=None) -> None:
    from playwright.async_api import async_playwright
    ff = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ff, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(out_video)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    pending: dict[int, bytes] = {}
    nxt = [0]
    lock = asyncio.Lock()

    async def sink(k, data):
        async with lock:
            pending[k] = data
            while nxt[0] in pending:
                proc.stdin.write(pending.pop(nxt[0]))
                nxt[0] += 1
                if progress and nxt[0] % 60 == 0:
                    progress(nxt[0], n)
    errors: list[str] = []
    async with async_playwright() as pw:
        br = await _launch(pw)
        try:
            # interleaved chunks keep memory low and the writer busy: worker i renders chunks i, i+W, ...
            chunk = 24
            chunks = [(a, min(n, a + chunk)) for a in range(0, n, chunk)]
            queue: asyncio.Queue = asyncio.Queue()
            for c in chunks:
                queue.put_nowait(c)

            async def worker():
                ctx, page, errs = await _open(br, html_path, w, h)
                try:
                    while not queue.empty():
                        a, b = queue.get_nowait()
                        while a - nxt[0] > chunk * workers * 3:      # do not run too far ahead of the writer
                            await asyncio.sleep(0.05)
                        for k in range(a, b):
                            b64 = await page.evaluate("([t, q]) => { window.__seek(t); return TOON.frameJPEG(q); }", [k / fps, 0.9])
                            if errs:
                                errors.extend(errs)
                                return
                            await sink(k, base64.b64decode(b64))
                finally:
                    await ctx.close()
            await asyncio.gather(*[worker() for _ in range(max(1, workers))])
        finally:
            await br.close()
    proc.stdin.close()
    rc = proc.wait()
    if errors:
        raise ShortsError("toon runtime error: " + "; ".join(errors[:3]))
    if rc != 0 or nxt[0] != n:
        raise ShortsError(f"toon render failed (ffmpeg rc={rc}, frames {nxt[0]}/{n})")


def render_video(story: dict, out_video: Path, work: Path, fps: int | None = None, workers: int = 3, crf: int = 18,
                 preset: str = "medium", t_end: float | None = None, progress=None) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    html = work / "toon.html"
    html.write_text(build_html(story), encoding="utf-8")
    fps = fps or int(story.get("fps", 30))
    dur = t_end or story["duration"]
    n = max(1, int(round(dur * fps)))
    asyncio.run(_render_all(html, story["W"], story["H"], fps, n, out_video, workers, crf, preset, progress))
    return out_video
