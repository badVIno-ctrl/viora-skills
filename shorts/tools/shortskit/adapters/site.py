"""Adapter `site`: walk a website with a visible cursor, record it, zoom the camera on clicks.

Recording uses the Chrome DevTools screencast (sharp frames at device pixels with timestamps).
Pages behind bot protection are skipped with an honest reason: protection is never bypassed.
"""
from __future__ import annotations

import asyncio
import base64
import bisect
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from ..config import browser_args, chrome_executable
from ..engine.clips import Camera, ClipWriter, SpeedMap, cover_resize
from ..util import ShortsError, log

BOT_TITLE = ("just a moment", "attention required", "access denied", "verify you are human", "are you a robot",
             "ddos protection", "security check", "checking your browser", "один момент", "проверка браузера")
BOT_HTML = ("challenges.cloudflare.com", "cf-chl-", "hcaptcha.com", "google.com/recaptcha", "turnstile",
            "captcha-delivery", "px-captcha", "perimeterx", "datadome")

CURSOR_JS = """
(() => {
  if (window.__shortsCursor) return; window.__shortsCursor = true;
  const ACC = "%ACCENT%";
  let el;
  const mk = () => {
    el = document.createElement('div');
    el.style.cssText = 'position:fixed;z-index:2147483647;pointer-events:none;width:36px;height:36px;left:-60px;top:0';
    el.innerHTML = '<svg width="36" height="36" viewBox="0 0 24 24"><path d="M3 2l7 19 3-8 8-3z" fill="#fff" stroke="#000" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(el);
  };
  addEventListener('mousemove', e => { if (!el) mk(); el.style.left = (e.clientX - 4) + 'px'; el.style.top = (e.clientY - 2) + 'px'; }, true);
  addEventListener('mousedown', e => {
    if (!el) mk();
    const r = document.createElement('div');
    r.style.cssText = `position:fixed;z-index:2147483646;pointer-events:none;left:${e.clientX-28}px;top:${e.clientY-28}px;width:56px;height:56px;border-radius:50%;border:4px solid ${ACC};transition:transform .45s cubic-bezier(.2,0,0,1),opacity .45s;opacity:1`;
    document.documentElement.appendChild(r);
    requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
    setTimeout(() => r.remove(), 600);
  }, true);
})();
"""

COOKIE_TEXTS = ("Accept all", "Accept", "I agree", "Allow all", "Got it", "OK", "Принять все", "Принять", "Согласен", "Хорошо")


class SiteBlocked(ShortsError):
    pass


@dataclass
class Capture:
    clip: Path | None
    clicks: list[float] = field(default_factory=list)  # output-time seconds of clicks (for SFX)
    notes: list[str] = field(default_factory=list)
    skipped: str = ""
    audio: Path | None = None


def viewport_for(spec, w: int, h: int) -> tuple[dict, float]:
    if isinstance(spec, dict) and spec.get("w"):
        dpr = w / float(spec["w"])
        return {"width": int(spec["w"]), "height": int(round(h / dpr))}, dpr
    if spec == "desktop":
        dpr = 1.25
    else:
        dpr = 2.0
    return {"width": int(round(w / dpr)), "height": int(round(h / dpr))}, dpr


async def check_blocked(page, response) -> str:
    status = response.status if response else 0
    title = (await page.title() or "").lower()
    try:
        html = (await page.content())[:200000].lower()
    except Exception:
        html = ""
    if any(m in title for m in BOT_TITLE):
        return f"bot protection page ('{title[:60]}')"
    if any(m in html for m in BOT_HTML) and (status in (403, 429, 503) or len(html) < 30000):
        return "captcha / challenge on the page"
    if status in (401, 403, 429):
        return f"HTTP {status}"
    return ""


async def launch(pw):
    exe = chrome_executable()
    return await pw.chromium.launch(executable_path=exe, args=browser_args(), headless=True)


class Screencast:
    def __init__(self, session, folder: Path, w: int, h: int):
        self.s, self.folder, self.w, self.h = session, folder, w, h
        self.frames: list[tuple[float, Path]] = []
        self._tasks: set = set()
        folder.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        self.s.on("Page.screencastFrame", self._on)
        await self.s.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": self.w, "maxHeight": self.h,
                                                    "everyNthFrame": 1})

    def _on(self, p: dict) -> None:
        ts = float(p.get("metadata", {}).get("timestamp") or time.time())
        path = self.folder / f"{len(self.frames):06d}.jpg"
        path.write_bytes(base64.b64decode(p["data"]))
        self.frames.append((ts, path))
        t = asyncio.ensure_future(self.s.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]}))
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        try:
            await self.s.send("Page.stopScreencast")
        except Exception:
            pass
        await asyncio.sleep(0.05)


def frames_to_clip(frames: list[tuple[float, Path]], t0: float, out: Path, w: int, h: int, fps: int, out_len: float,
                   speed: SpeedMap, camera: Camera | None, t_end: float | None = None) -> tuple[int, float]:
    """Sample timestamped frames on the output timeline. Returns (frames written, seconds held at the end)."""
    if not frames:
        raise ShortsError("no frames recorded")
    frames = sorted(frames)
    times = [f[0] for f in frames]
    wr = ClipWriter(out, w, h, fps)
    cache: dict[Path, np.ndarray] = {}
    held = 0.0
    n = max(1, int(round(out_len * fps)))
    for k in range(n):
        t_src = speed.src_at(k / fps)
        wall = t0 + t_src
        i = max(0, bisect.bisect_right(times, wall) - 1)
        # screencast only sends frames when the page changes: a static page is fine until capture ended
        if wall > (t_end if t_end is not None else times[-1]) + 0.2:
            held += 1 / fps
        p = frames[i][1]
        img = cache.get(p)
        if img is None:
            img = cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB)
            if img.shape[1] != w or img.shape[0] != h:
                img = cover_resize(img, w, h, 0.5, 0.0)
            cache.clear()
            cache[p] = img
        wr.write(camera.apply(img, t_src) if camera else img)
    wr.close()
    return n, held


async def _locate(page, a: dict):
    # for "type" the `text` field is what to type, never a locator
    if "text" in a and a.get("do") != "type":
        return page.get_by_text(a["text"], exact=a.get("exact", False)).first
    if "role" in a:
        return page.get_by_role(a["role"], name=a.get("name")).first
    if "label" in a:
        return page.get_by_label(a["label"]).first
    if "placeholder" in a:
        return page.get_by_placeholder(a["placeholder"]).first
    if "sel" in a:
        return page.locator(a["sel"]).first
    if a.get("do") == "type":
        return page.locator("input:visible, textarea:visible, [contenteditable=true]").first
    raise ShortsError(f"action {a.get('do')} needs text/role/label/placeholder/sel")


async def run_actions(page, actions: list[dict], ref: str, dpr: float, t0_box: list, clicks: list, notes: list,
                      crashed: list, timeout_ms: int = 8000) -> None:
    for a in actions:
        if crashed:
            break
        d = a.get("do")
        if t0_box[0] is not None and "t" in a:
            wait = t0_box[0] + float(a["t"]) - time.time()
            if wait > 0:
                await asyncio.sleep(wait)
        try:
            if d == "goto":
                resp = await page.goto(a.get("url") or ref, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_load_state("load", timeout=15000)
                except Exception:
                    notes.append("page did not finish loading in 15 s, continuing")
                reason = await check_blocked(page, resp)
                if reason:
                    raise SiteBlocked(f"{a.get('url') or ref}: {reason}")
                await page.wait_for_timeout(int(a.get("settle", 1.2) * 1000))
                await page.mouse.move(*a.get("from", (page.viewport_size["width"] * 0.6, page.viewport_size["height"] * 0.55)))
                if t0_box[0] is None:
                    t0_box[0] = time.time()
            elif d == "wait":
                await page.wait_for_timeout(int(float(a.get("s", 1.0)) * 1000))
            elif d == "move":
                await page.mouse.move(a["x"], a["y"], steps=a.get("steps", 25))
            elif d in ("click", "hover", "type"):
                loc = await _locate(page, a)
                await loc.scroll_into_view_if_needed(timeout=timeout_ms)
                box = await loc.bounding_box(timeout=timeout_ms)
                if not box:
                    raise ShortsError("element has no box")
                x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                await page.mouse.move(x, y, steps=a.get("steps", 22))
                if d in ("click", "type"):
                    if t0_box[0] is not None:
                        clicks.append((time.time() - t0_box[0], x * dpr, y * dpr))
                    await page.mouse.down()
                    await page.mouse.up()
                if d == "type":
                    await page.keyboard.type(a["text"], delay=a.get("delay", 90))
            elif d == "press":
                await page.keyboard.press(a["key"])
            elif d == "scroll":
                vp = page.viewport_size
                await page.mouse.move(*a.get("at", (vp["width"] * 0.5, vp["height"] * 0.5)), steps=8)
                n = int(a.get("steps", 24))
                for _ in range(n):
                    await page.mouse.wheel(0, float(a.get("dy", 500)) / n)
                    await page.wait_for_timeout(30)
            elif d == "dismiss_cookies":
                for t in COOKIE_TEXTS:
                    btn = page.get_by_role("button", name=t, exact=True)
                    if await btn.count() and await btn.first.is_visible():
                        await btn.first.click(timeout=2000)
                        break
            else:
                notes.append(f"unknown action {d}")
            if "t" not in a and d != "goto":
                await page.wait_for_timeout(int(a.get("after", 0.5) * 1000))
        except SiteBlocked:
            raise
        except Exception as e:
            if a.get("required"):
                raise ShortsError(f"action {d} failed: {e}") from e
            notes.append(f"action {d} skipped: {str(e).splitlines()[0][:120]}")
            log.warning("site action %s failed: %s", d, e)


async def capture(browser, scene: dict, w: int, h: int, fps: int, out_len: float, work: Path, lang: str,
                  accent: str, file_url: str | None = None) -> Capture:
    src = scene["source"]
    ref = file_url or src.get("ref", "")
    from ..contract import apply_avoid

    actions, avoid_notes = apply_avoid(list(src.get("actions") or []), scene.get("avoid"))
    if not actions or actions[0].get("do") != "goto":
        actions.insert(0, {"do": "goto"})
    vp, dpr = viewport_for(src.get("viewport", "mobile"), w, h)
    speed = SpeedMap(scene.get("speed"))
    src_len = speed.src_at(out_len) + 0.4
    ctx = await browser.new_context(viewport=vp, device_scale_factor=dpr, locale="ru-RU" if lang == "ru" else "en-US",
                                    color_scheme="dark", is_mobile=False, has_touch=False)
    await ctx.add_init_script(CURSOR_JS.replace("%ACCENT%", accent))
    page = await ctx.new_page()
    crashed: list = []
    page.on("crash", lambda *_: crashed.append(True))
    cdp = await ctx.new_cdp_session(page)
    sc = Screencast(cdp, work / f"frames-{scene['id']}", w, h)
    await sc.start()
    clicks: list = []
    notes: list = list(avoid_notes)
    t0_box: list = [None]
    try:
        await run_actions(page, actions, ref, dpr, t0_box, clicks, notes, crashed)
        if t0_box[0] is None:
            raise ShortsError("page never loaded")
        rest = t0_box[0] + src_len - time.time()
        if rest > 0 and not crashed:
            await asyncio.sleep(rest)
    except SiteBlocked as e:
        await sc.stop()
        await ctx.close()
        return Capture(None, skipped=str(e))
    finally:
        if crashed:
            notes.append("page crashed in headless mode, kept the frames before the crash")
    t_end = time.time()
    await sc.stop()
    if not sc.frames:
        shot = await page.screenshot(type="jpeg", quality=90)
        p = sc.folder / "still.jpg"
        p.write_bytes(shot)
        sc.frames.append((t0_box[0], p))
    await ctx.close()
    t0 = t0_box[0]
    camera = Camera.from_clicks(w, h, clicks) if src.get("zoom_on_click", True) and clicks else None
    out = work / f"center-{scene['id']}.mp4"
    _, held = frames_to_clip(sc.frames, t0, out, w, h, fps, out_len, speed, camera, t_end)
    if held > 1.0:
        notes.append(f"recording ended {held:.1f}s before the voice; last frame held")
    out_clicks = [speed.out_at(c[0]) for c in clicks if speed.out_at(c[0]) < out_len]
    return Capture(out, out_clicks, notes)


async def probe(url: str, out_dir: Path) -> dict:
    """Open a page, report protection, take a phone-size screenshot, list elements the model can act on."""
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        b = await launch(pw)
        ctx = await b.new_context(viewport={"width": 540, "height": 616}, device_scale_factor=2)
        page = await ctx.new_page()
        res: dict = {"url": url}
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("load", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(2500)  # SPAs render after "load"
            res["status"] = resp.status if resp else None
            res["title"] = await page.title()
            res["blocked"] = await check_blocked(page, resp)
            shot = out_dir / "probe.jpg"
            await page.screenshot(path=str(shot), type="jpeg", quality=85)
            res["screenshot"] = str(shot)
            res["elements"] = await page.evaluate("""() => {
              const out = [];
              const els = document.querySelectorAll('input,textarea,button,a,[role=button],select,[contenteditable=true]');
              for (const e of els) {
                const r = e.getBoundingClientRect();
                if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight * 3) continue;
                const text = (e.innerText || e.value || e.placeholder || e.getAttribute('aria-label') || '').trim().slice(0, 60);
                let sel = e.tagName.toLowerCase();
                if (e.id) sel += '#' + CSS.escape(e.id);
                else if (e.name) sel += `[name="${e.name}"]`;
                else if (e.placeholder) sel += `[placeholder="${e.placeholder}"]`;
                out.push({tag: e.tagName.toLowerCase(), text, sel, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)});
                if (out.length >= 60) break;
              }
              return out;
            }""")
        except Exception as e:
            res["error"] = str(e).splitlines()[0]
        await b.close()
    (out_dir / "probe.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return res
