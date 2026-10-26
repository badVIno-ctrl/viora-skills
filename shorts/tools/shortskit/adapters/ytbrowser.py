"""YouTube through the agent's shared browser (CDP), for when YouTube blocks the render machine's IP.

Why: yt-dlp runs on the render machine. Datacenter IPs get "Sign in to confirm you're not a bot"
(yt-dlp maintainers: YouTube does not trust the IP; cookies or a PO token only sometimes help there).
The shared browser goes out through another address and plays YouTube normally. A file cannot be
downloaded from the player (it streams pieces), so we RECORD the playing <video> element:
`video.captureStream()` + `MediaRecorder` (MDN "Recording a media element"). This does not defeat any
challenge: if the browser itself shows a captcha or "sign in", we stop and ask the user.

  probe(url)            title, duration, chapters, heatmap ("most replayed"), storyboard spec, captions,
                        quality levels, transcript (one page load, cached)
  storyboard_frames()   the whole film as thumbnails every N s (i.ytimg.com sprite sheets, no video needed)
  record_sections()     exact pieces as mp4 (real time: 1 s of video = 1 s of recording)

Recording rules (all handled here):
  - ads: wait for `.ad-showing` to clear, click "Skip"; an ad in the middle = the piece is recorded again;
  - quality: ask the player for hd1080 (else the best available), report videoWidth/Height;
  - buffering: MediaRecorder pauses on `waiting` and resumes on `playing`, so stalls do not freeze frames;
  - timing: `requestVideoFrameCallback` gives the media time of the first recorded frame; the file is trimmed
    to the exact requested start from that offset.
Env: SHORTS_BROWSER_CDP (or AGENT_BROWSER_CDP) = CDP url of the shared browser.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

from ..config import cache_dir
from ..util import ShortsError, log, run

QUALITY = ["hd1080", "hd720", "large", "medium"]
CHUNK = 4 * 1024 * 1024


def cdp_url() -> str:
    return os.environ.get("SHORTS_BROWSER_CDP") or os.environ.get("AGENT_BROWSER_CDP") or ""


def available() -> bool:
    return bool(cdp_url())


def video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})", url)
    if not m:
        raise ShortsError(f"not a YouTube video url: {url}")
    return m.group(1)


def is_youtube(url: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)/", url))


def is_bot_block(err: str) -> bool:
    e = err.lower()
    return any(s in e for s in ("confirm you", "not a bot", "sign in to confirm", "http error 429", "po token",
                                "requested format is not available"))


# ---------------------------------------------------------------- page scripts

JS_PREP = r"""
async ({wantQuality}) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const P = document.querySelector('#movie_player');
  const v = document.querySelector('video.html5-main-video') || document.querySelector('video');
  if (!P || !v) return {error: 'no player'};
  const isAd = () => P.classList.contains('ad-showing') || P.classList.contains('ad-interrupting');
  let adWait = 0;
  const SKIP = '.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, ' +
               '.ytp-ad-skip-button-container button, .ytp-ad-skip-button-slot button, [id^="skip-button"] button';
  for (let i = 0; i < 240 && isAd(); i++) {
    const b = document.querySelector(SKIP);
    if (b) b.click();
    const av = document.querySelector('video');
    // the ad is cut anyway: muted, fast-forwarded to its end (mid-roll pods of long films can be minutes long)
    try { av.muted = true; if (isFinite(av.duration) && av.duration > 0 && av.duration < 300) av.currentTime = Math.max(0, av.duration - 0.05); } catch (e) {}
    if (av.paused) av.play().catch(() => {});
    adWait += 0.5; await sleep(500);
  }
  if (isAd()) return {error: 'ad did not finish in 2 minutes'};
  const levels = (P.getAvailableQualityLevels && P.getAvailableQualityLevels()) || [];
  const q = wantQuality.find(x => levels.includes(x)) || levels[0] || 'auto';
  try { P.setPlaybackQualityRange && P.setPlaybackQualityRange(q, q); P.setPlaybackQuality && P.setPlaybackQuality(q); } catch (e) {}
  try { P.unMute && P.unMute(); P.setVolume && P.setVolume(100); } catch (e) {}
  try { P.setPlaybackRate && P.setPlaybackRate(1); } catch (e) {}
  v.muted = false; v.volume = 1; v.playbackRate = 1;
  // ORIGINAL audio, never the AI auto-dub: YouTube picks a dubbed track by the browser language
  // (an en-US browser gets an English dub of a Russian film). The original track id has "acont=original".
  let audio = null, dubbed = false;
  try {
    const tracks = (P.getAvailableAudioTracks && P.getAvailableAudioTracks()) || [];
    const meta = t => Object.values(t).find(x => x && typeof x === 'object' && 'isAutoDubbed' in x) || {};
    const isOrig = t => { let id = String(t.id || ''); let dec = '';
      try { dec = atob(id.split(';')[1].replace(/-/g, '+').replace(/_/g, '/')); } catch (e) {}
      return /original/.test(dec) || /original/i.test(meta(t).name || ''); };
    if (tracks.length > 1) {
      const orig = tracks.find(isOrig) || tracks.find(t => meta(t).isAutoDubbed === false);
      const cur = P.getAudioTrack && P.getAudioTrack();
      if (orig && (!cur || cur.id !== orig.id)) { P.setAudioTrack(orig); await sleep(1500); }
      const now = P.getAudioTrack && P.getAudioTrack();
      audio = now ? (meta(now).name || now.id) : null;
      dubbed = !!(now && meta(now).isAutoDubbed);
    }
  } catch (e) { audio = 'error: ' + e; }
  return {levels, quality: q, adWait, audio, dubbed};
}
"""

JS_PROBE = r"""
() => {
  const p = window.ytInitialPlayerResponse || {};
  const d = window.ytInitialData || {};
  const vd = p.videoDetails || {};
  let heat = [];
  try {
    for (const m of ((d.frameworkUpdates || {}).entityBatchUpdate || {}).mutations || []) {
      const e = m.payload && m.payload.macroMarkersListEntity;
      if (e && e.markersList && /HEATMAP/.test(e.markersList.markerType || 'HEATMAP')) {
        heat = e.markersList.markers.map(x => ({start_time: +x.startMillis / 1000,
          end_time: (+x.startMillis + +x.durationMillis) / 1000, value: +x.intensityScoreNormalized}));
      }
    }
  } catch (e) {}
  const s = JSON.stringify(d);
  if (!heat.length) {
    const re = /"heatMarkerRenderer":\{"timeRangeStartMillis":(\d+),"markerDurationMillis":(\d+),"heatMarkerIntensityScoreNormalized":([\d.e-]+)/g;
    let m; while ((m = re.exec(s))) heat.push({start_time: m[1] / 1000, end_time: (+m[1] + +m[2]) / 1000, value: +m[3]});
  }
  const chapters = [];
  { const re = /"chapterRenderer":\{"title":\{"simpleText":"([^"]*)"\},"timeRangeStartMillis":(\d+)/g;
    let m; while ((m = re.exec(s))) chapters.push({title: m[1], start_time: m[2] / 1000}); }
  const tracks = (((p.captions || {}).playerCaptionsTracklistRenderer || {}).captionTracks || [])
      .map(c => (c.languageCode + (c.kind === 'asr' ? ':auto' : '')));
  const P = document.querySelector('#movie_player');
  const ps = p.playabilityStatus || {};
  return {id: vd.videoId, title: vd.title, duration: +vd.lengthSeconds || null, channel: vd.author,
          view_count: +vd.viewCount || null, heatmap: heat.length ? heat : null, chapters,
          storyboard: ((p.storyboards || {}).playerStoryboardSpecRenderer || {}).spec || null,
          captions: tracks, playability: ps.status || null, reason: ps.reason || null,
          qualities: (P && P.getAvailableQualityLevels && P.getAvailableQualityLevels()) || []};
}
"""

JS_RECORD = r"""
async ({t0, dur, mime, bps}) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const P = document.querySelector('#movie_player');
  const v = document.querySelector('video.html5-main-video') || document.querySelector('video');
  const isAd = () => P.classList.contains('ad-showing') || P.classList.contains('ad-interrupting');
  const until = async (fn, ms) => { const e = Date.now() + ms; while (Date.now() < e) { if (fn()) return true; await sleep(40); } return false; };
  const declared = window.ytInitialPlayerResponse?.videoDetails || {};
  const loaded = P.getVideoData ? P.getVideoData() : {};
  if (loaded.video_id && declared.videoId && loaded.video_id !== declared.videoId)
    return {error:'loaded media identity differs from requested publication'};
  if (isFinite(v.duration) && t0 + dur > v.duration + 1)
    return {error:'requested fragment outside loaded media duration: ' + v.duration};
  v.pause();
  P.seekTo(t0, true);
  await sleep(200); v.pause();
  if (!await until(() => !v.seeking && v.readyState >= 3 && Math.abs(v.currentTime - t0) < 0.6, 25000))
    return {error: 'seek timeout', at: v.currentTime};
  await until(() => { for (let i = 0; i < v.buffered.length; i++)
      if (v.buffered.start(i) <= v.currentTime + 0.05 && v.buffered.end(i) >= Math.min(v.currentTime + Math.min(dur, 8), v.duration - 0.2)) return true;
      return false; }, 8000);
  const stream = v.captureStream();
  const type = [mime, 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'].find(t => MediaRecorder.isTypeSupported(t));
  const rec = new MediaRecorder(stream, {mimeType: type, videoBitsPerSecond: bps, audioBitsPerSecond: 192000});
  const chunks = []; rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
  let stalls = 0, adHit = false; const marks = [];
  const onWait = () => { stalls++; if (rec.state === 'recording') rec.pause(); };
  const onPlay = () => { if (rec.state === 'paused') rec.resume(); };
  v.addEventListener('waiting', onWait); v.addEventListener('playing', onPlay);
  const cb = (now, meta) => { if (rec.state === 'recording') marks.push(meta.mediaTime); if (rec.state !== 'inactive') v.requestVideoFrameCallback(cb); };
  rec.start(500);
  v.requestVideoFrameCallback(cb);
  await v.play();
  const ok = await until(() => { if (isAd()) { adHit = true; return true; } return v.currentTime >= t0 + dur || v.ended; }, (dur + 45) * 1000);
  v.pause();
  const stopped = new Promise(r => rec.onstop = r); rec.stop(); await stopped;
  v.removeEventListener('waiting', onWait); v.removeEventListener('playing', onPlay);
  const audio = stream.getAudioTracks().length;
  stream.getTracks().forEach(t => t.stop());
  const blob = new Blob(chunks, {type});
  window.__shortsGrab = blob;
  return {ok, adHit, size: blob.size, type, first: marks.length ? marks[0] : null, last: marks.length ? marks[marks.length - 1] : null,
          frames: marks.length, stalls, width: v.videoWidth, height: v.videoHeight, audio,
          quality: P.getPlaybackQuality ? P.getPlaybackQuality() : ''};
}
"""

JS_CHUNK = r"""
async ({off, len}) => {
  const b = window.__shortsGrab.slice(off, off + len);
  const buf = new Uint8Array(await b.arrayBuffer());
  let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return btoa(s);
}
"""

JS_TRANSCRIPT = r"""
async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const read = () => [...document.querySelectorAll('ytd-transcript-segment-renderer, transcript-segment-view-model')]
      .map(e => e.innerText.replace(/\s+/g, ' ').trim()).filter(Boolean);
  if (!read().length) {
    const ex = document.querySelector('#description-inline-expander #expand, tp-yt-paper-button#expand, #expand');
    if (ex) { ex.click(); await sleep(700); }
    const b = [...document.querySelectorAll('button, yt-button-shape button')]
        .find(b => /transcript|расшифров|текстовая версия/i.test((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')));
    if (!b) return {error: 'no transcript button'};
    b.click();
    for (let i = 0; i < 60 && !read().length; i++) await sleep(250);
  }
  const panel = document.querySelector('ytd-transcript-segment-list-renderer #segments-container, ytd-transcript-renderer #body');
  for (let i = 0, n = -1; panel && i < 300; i++) { const c = read().length; if (c === n) break; n = c; panel.scrollTop = panel.scrollHeight; await sleep(200); }
  return {lines: read()};
}
"""


def _parse_ts(s: str) -> float:
    t = 0
    for p in s.split(":"):
        t = t * 60 + int(p)
    return float(t)


_SPOKEN = re.compile(r"^((\d+\s+(hours?|minutes?|seconds?|час\w*|минут\w*|секунд\w*)),?\s*)+", re.I)


def parse_transcript(lines: list[str]) -> list[dict]:
    """'1:02:03 1 hour, 2 minutes, 3 seconds text' / '0:12 text' -> [{start, end, text}] (end = next start)."""
    out = []
    for ln in lines:
        m = re.match(r"^(\d+(?::\d{1,2}){1,2})\s+(.*)$", ln.strip())
        if not m:
            continue
        text = _SPOKEN.sub("", m.group(2)).strip()
        if text:
            out.append({"start": _parse_ts(m.group(1)), "text": text})
    for a, b in zip(out, out[1:]):
        a["end"] = b["start"]
    if out:
        out[-1]["end"] = out[-1]["start"] + 4.0
    return out


# ---------------------------------------------------------------- browser session

class Session:
    """One own tab in the shared browser. The browser itself is never closed."""

    def __init__(self):
        self.pw = self.browser = self.page = None

    async def __aenter__(self):
        if not available():
            raise ShortsError("no shared browser: set SHORTS_BROWSER_CDP (or run where AGENT_BROWSER_CDP is set)")
        from playwright.async_api import async_playwright

        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.connect_over_cdp(cdp_url())
        ctx = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        self.page = await ctx.new_page()
        try:
            await self.page.set_viewport_size({"width": 1280, "height": 800})
        except Exception:  # noqa: BLE001
            pass
        await self.page.bring_to_front()
        return self

    async def __aexit__(self, *exc):
        try:
            if self.page:
                await self.page.close()
        finally:
            if self.pw:
                await self.pw.stop()  # only disconnects; the shared browser keeps running

    async def open(self, url: str) -> dict:
        page = self.page
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if "consent." in page.url:
            for label in ("Accept all", "Принять все", "Reject all", "Отклонить все"):
                b = page.get_by_role("button", name=label)
                if await b.count():
                    await b.first.click()
                    break
            await page.wait_for_url("**/watch**", timeout=30000)
        await page.wait_for_selector("#movie_player video", state="attached", timeout=45000)
        await page.wait_for_function(
            "() => window.ytInitialPlayerResponse && document.querySelector('#movie_player') && "
            "document.querySelector('#movie_player').getPlayerState", timeout=30000)
        info = await page.evaluate(JS_PROBE)
        if info.get("playability") not in (None, "OK"):
            raise ShortsError(f"YouTube in the browser: {info.get('playability')} {info.get('reason') or ''}. "
                              "Ask the user to sign in in the shared browser (Take control) or to send the file.")
        if not info.get("heatmap"):  # heatmap entities can arrive a moment later
            await page.wait_for_timeout(2500)
            info["heatmap"] = (await page.evaluate(JS_PROBE)).get("heatmap")
        return info

    async def prep(self) -> dict:
        r = await self.page.evaluate(JS_PREP, {"wantQuality": QUALITY})
        if r.get("error"):
            raise ShortsError(f"player: {r['error']}")
        if r.get("dubbed"):
            raise ShortsError(f"only a dubbed audio track is playing ({r.get('audio')}): cannot switch to the original")
        if r.get("audio") and r.get("audio") != getattr(self, "_audio_logged", None):
            log.info("audio track: %s", r["audio"])
            self._audio_logged = r["audio"]
        return r

    async def transcript(self) -> list[dict]:
        r = await self.page.evaluate(JS_TRANSCRIPT)
        return [] if r.get("error") else parse_transcript(r["lines"])

    async def record(self, t0: float, dur: float, out: Path, bps: int = 16_000_000) -> dict:
        await self.page.bring_to_front()
        await self.prep()
        r = await self.page.evaluate(JS_RECORD, {"t0": t0, "dur": dur, "mime": "video/webm;codecs=vp9,opus", "bps": bps})
        if r.get("error"):
            raise ShortsError(f"record {t0:.1f}s: {r['error']}")
        data = bytearray()
        for off in range(0, r["size"], CHUNK):
            data += base64.b64decode(await self.page.evaluate(JS_CHUNK, {"off": off, "len": CHUNK}))
        await self.page.evaluate("() => { window.__shortsGrab = null; }")
        out.write_bytes(bytes(data))
        return r


JS_SEARCH = r"""
() => {
  const out = [];
  const walk = o => { if (!o || typeof o !== 'object') return;
    if (o.videoRenderer) { const v = o.videoRenderer; const len = (v.lengthText || {}).simpleText || '';
      const sec = len.split(':').reduce((a, x) => a * 60 + (+x), 0);
      out.push({id: v.videoId, title: ((v.title || {}).runs || [{}])[0].text, duration: sec || null,
                channel: ((v.ownerText || {}).runs || [{}])[0].text,
                views: +(((v.viewCountText || {}).simpleText || '').replace(/[^0-9]/g, '')) || null}); }
    for (const k in o) walk(o[k]); };
  walk(window.ytInitialData);
  return out;
}
"""


def search(query: str, n: int = 10) -> list[dict]:
    """YouTube search results through the shared browser (same fields as media.search)."""
    import urllib.parse

    async def go():
        async with Session() as s:
            await s.page.goto("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query),
                              wait_until="domcontentloaded", timeout=60000)
            await s.page.wait_for_function("() => window.ytInitialData", timeout=30000)
            return await s.page.evaluate(JS_SEARCH)

    res = asyncio.run(go())[:n]
    for r in res:
        r["url"] = f"https://www.youtube.com/watch?v={r['id']}"
    return res


# ---------------------------------------------------------------- public API

def _meta_path(url: str) -> Path:
    return cache_dir("meta") / f"browser-{video_id(url)}.json"


def probe(url: str, with_transcript: bool = True) -> dict:
    p = _meta_path(url)
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("transcript") is not None or not with_transcript:
            return d

    async def go():
        async with Session() as s:
            info = await s.open(url)
            info["transcript"] = await s.transcript() if with_transcript else None
            return info

    info = asyncio.run(go())
    info["webpage_url"] = f"https://www.youtube.com/watch?v={video_id(url)}"
    info["source"] = "browser"
    p.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    log.info("browser probe: %s, %ss, heatmap %s, storyboard %s, transcript %s lines", info.get("title"),
             info.get("duration"), "yes" if info.get("heatmap") else "no", "yes" if info.get("storyboard") else "no",
             len(info.get("transcript") or []))
    return info


STD_FPS = (23.976, 24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0)


def native_fps(r: dict) -> float:
    """Frame rate of the source from the frame callbacks (the recording itself is variable-rate)."""
    if r.get("frames", 0) > 10 and r.get("last") and r.get("first") is not None and r["last"] > r["first"]:
        est = (r["frames"] - 1) / (r["last"] - r["first"])
        return min(STD_FPS, key=lambda f: abs(f - est))
    return 30.0


def _to_file(src: Path, dst: Path, offset: float, dur: float, max_height: int, audio_only: bool,
             fps: float = 30.0) -> None:
    # -ss after -i = exact (decodes from the start of the short recording, cheap)
    if audio_only:
        run(["ffmpeg", "-y", "-v", "error", "-fflags", "+genpts", "-i", str(src), "-ss", f"{max(0.0, offset):.3f}",
             "-t", f"{dur:.3f}", "-vn", "-ac", "2", "-ar", "48000", str(dst)], timeout=600)
        return
    # keep the film's own frame rate (24/25): duplicated frames would break optical-flow slow motion later
    vf = f"scale=-2:'min({max_height},ih)':flags=lanczos,fps={fps},format=yuv420p"
    run(["ffmpeg", "-y", "-v", "error", "-fflags", "+genpts", "-i", str(src), "-ss", f"{max(0.0, offset):.3f}",
         "-t", f"{dur:.3f}", "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "15",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(dst)], timeout=900)


def record_sections(url: str, sections: list[tuple[float, float]], audio_only: bool = False,
                    max_height: int = 1080, pre: float = 0.6, merge_gap: float = 6.0) -> list[Path]:
    """Record [start, end] pieces in the shared browser (cached per piece). Pieces closer than `merge_gap`
    seconds are recorded in one go (one seek, less buffering)."""
    vid = video_id(url)
    d = cache_dir("downloads")
    want = []
    for s, e in sections:
        key = hashlib.sha1(f"browser|{vid}|{float(s):.2f}|{float(e):.2f}|{audio_only}|{max_height}".encode()).hexdigest()[:16]
        want.append((float(s), float(e), d / f"{key}.{'wav' if audio_only else 'mp4'}"))
    todo = sorted([w for w in want if not w[2].exists()], key=lambda w: w[0])
    if todo:
        groups: list[list] = []
        for w in todo:
            if groups and w[0] - max(x[1] for x in groups[-1]) < merge_gap and w[1] - groups[-1][0][0] < 90:
                groups[-1].append(w)
            else:
                groups.append([w])

        async def go():
            async with Session() as s:
                for g in groups:
                    a, z = max(0.0, g[0][0] - pre), max(x[1] for x in g) + 0.4
                    # Open at the distant chapter before seeking. Some players reset a seek
                    # performed while switching their original audio stream.
                    await s.open(f"https://www.youtube.com/watch?v={vid}&t={int(a)}s")
                    raw = d / f"rec-{vid}-{a:.2f}-{z:.2f}.webm"
                    for attempt in range(3):
                        try:
                            r = await s.record(a, z - a, raw)
                        except ShortsError as e:  # stuck ad / player hiccup: reload the page, try again
                            if attempt == 2 or any(k in str(e) for k in ("dubbed", "seek timeout", "identity differs", "outside loaded media")):
                                raise
                            log.info("%s: reloading the page (%d)", e, attempt + 1)
                            await s.open(url)
                            continue
                        if r["adHit"]:
                            log.info("an ad interrupted the recording at %.1fs, again (%d)", a, attempt + 1)
                            continue
                        if not r["frames"] or r["size"] < 10_000:
                            raise ShortsError("recording is empty: the browser did not play the video")
                        break
                    else:
                        raise ShortsError("ads keep interrupting the recording")
                    if r["height"] and r["height"] < 700 and not audio_only:
                        log.warning("browser gave only %sx%s (%s)", r["width"], r["height"], r["quality"])
                    if not r["audio"]:
                        log.warning("recording has no audio track")
                    first = r["first"] if r["first"] is not None else a
                    for (ws, we, path) in g:
                        _to_file(raw, path, ws - first, we - ws, max_height, audio_only, native_fps(r))
                        receipt = {"url":url,"section":[ws,we],"recording":r,
                                   "method":"public playback capture","listened":False,
                                   "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
                        path.with_suffix(path.suffix + ".source.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
                    log.info("recorded %.1f-%.1fs: %sx%s %s, %d stalls", a, z, r["width"], r["height"], r["quality"], r["stalls"])
                    raw.unlink(missing_ok=True)

        asyncio.run(go())
    return [w[2] for w in want]


def record_section(url: str, start: float, end: float, audio_only: bool = False, max_height: int = 1080) -> Path:
    return record_sections(url, [(start, end)], audio_only=audio_only, max_height=max_height)[0]


# ---------------------------------------------------------------- storyboard

def parse_storyboard(spec: str, duration: float) -> list[dict]:
    """'base|w#h#count#cols#rows#interval_ms#name#sigh|...' (same parsing as invidious storyboard.cr)."""
    parts = spec.split("|")
    base = parts[0]
    levels = []
    for i, sb in enumerate(parts[1:]):
        f = sb.split("#")
        if len(f) < 8:
            continue
        w, h, count, cols, rows, interval = (int(x) for x in f[:6])
        name, sigh = f[6], f[7]
        if interval == 0 and count:
            interval = int(duration * 1000 / count)
        url = base.replace("$L", str(i)).replace("$N", name) + ("&" if "?" in base else "?") + f"sigh={sigh}"
        levels.append({"level": i, "w": w, "h": h, "count": count, "cols": cols, "rows": rows,
                       "interval": interval / 1000.0, "url": url})
    return levels


def storyboard_frames(url: str, info: dict | None = None) -> dict:
    """Thumbnails of the whole video at the biggest storyboard level -> {'t', 'files', 'interval', 'dir'}.
    i.ytimg.com serves images without the player, so this works from the render machine."""
    import cv2
    import numpy as np

    info = info or probe(url, with_transcript=False)
    if not info.get("storyboard"):
        raise ShortsError("no storyboard for this video")
    lv = max(parse_storyboard(info["storyboard"], float(info.get("duration") or 0)), key=lambda x: x["w"])
    out = cache_dir("storyboard") / f"{video_id(url)}-L{lv['level']}"
    out.mkdir(parents=True, exist_ok=True)
    index = out / "index.json"
    if index.exists():
        d = json.loads(index.read_text())
        d["dir"] = str(out)
        return d
    per = lv["cols"] * lv["rows"]
    ts, files = [], []
    for n in range((lv["count"] + per - 1) // per):
        u = lv["url"].replace("$M", str(n))
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.youtube.com/"})
        try:
            raw = urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:  # noqa: BLE001
            raise ShortsError(f"storyboard sheet {n}: {e}")
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        cw, ch = lv["w"], lv["h"]
        for k in range(per):
            idx = n * per + k
            if idx >= lv["count"]:
                break
            r, c = divmod(k, lv["cols"])
            tile = img[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
            if tile.size == 0 or tile.shape[0] < ch // 2:
                continue
            f = out / f"{idx:05d}.jpg"
            cv2.imwrite(str(f), tile, [cv2.IMWRITE_JPEG_QUALITY, 92])
            ts.append(round(idx * lv["interval"], 2))
            files.append(f.name)
    d = {"t": ts, "files": files, "interval": lv["interval"], "w": lv["w"], "h": lv["h"]}
    index.write_text(json.dumps(d))
    d["dir"] = str(out)
    return d
