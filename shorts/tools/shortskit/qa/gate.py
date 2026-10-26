"""QA gate (COMMON.md section 11) + the 20-point checklist (research section 9).

Reads DIR/manifest.json, DIR/<video>.mp4, optional DIR/metadata.json and DIR/cover/.
Writes DIR/qa.json, DIR/qa.md, DIR/contact-*.png, DIR/qa-frames/*.png.
A video may be delivered only when `passed` is true. Manual items (eyes, silent retell) are listed for the agent.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from .. import contract as K
from .. import memory as M
from ..engine import layout as L
from ..engine.audio import measure
from ..engine.brand import DEFAULT_FONT_NAMES
from ..util import (contrast, count_emoji, ffprobe, has_long_dash, hex_to_rgb, read_json, script_ratio,
                    write_json)
from . import edit as E
from . import frames as F

CAPTION_SYNC_TOL = 0.15
LUFS_TOL = 1.5
# 1.3 kinetic captions (engine/kinetic.py): other limits than karaoke chunks
KIN_MIN_PX, KIN_MAX_WORDS, KIN_MAX_LINES, KIN_MAX_H, KIN_MIN_WORD_S = 56, 12, 4, 0.45, 0.3
COVERING = ("title_bar", "fact", "arrow")
EARLY_TEXT = ("title_bar", "post", "fact", "label", "kinetic")
LETTERBOX_START_MAX = 3.0   # closed bars at the start longer than this hide the hook
LETTERBOX_SHARE_MAX = 0.5   # bars on for more than half of the video: the vertical screen is wasted
NOTABLE_MAX = 2             # legacy constant retained for import compatibility; not a creative limit
LOOK_CHANGES_MAX = 2
FOREIGN_ONLY_MAX = 15.0     # s of foreign footage without the author's voice or text (research 15, 22)


def _flat_on_purpose(m: dict, dur: float) -> list[tuple[float, float, int, int]]:
    """Rows that are flat by design: closed cinema bars (while closed), the black fields of the band layout,
    post cards while shown."""
    out = []
    lay = m["layout"]
    cy, ch = lay["center"]["y"], lay["center"]["h"]
    lb = (m.get("vfx") or {}).get("letterbox") or {}
    bar = int(lb.get("max_bar_px") or 0)
    for a, b in lb.get("closed") or []:
        out += [(a, b, cy, cy + bar), (a, b, cy + ch - bar, cy + ch)]
    if lay.get("mode") == "band":
        out += [(0.0, dur + 1, 0, cy), (0.0, dur + 1, cy + ch, 1920)]
    for p in m.get("post") or []:   # a post card is a plate with text (its margins are flat on purpose)
        out.append((float(p["t0"]), float(p["t1"]), int(p["box"][1]), int(p["box"][3])))
    return out


@dataclass
class Check:
    id: str
    item: int  # COMMON.md section 11 item number (0 = extra)
    title: str
    status: str = "pass"  # pass | fail | warn | manual | skip
    detail: str = ""
    data: dict = field(default_factory=dict)

    def fail(self, msg: str) -> "Check":
        self.status = "fail"
        self.detail = (self.detail + "; " if self.detail else "") + msg
        return self

    def warn(self, msg: str) -> "Check":
        if self.status == "pass":
            self.status = "warn"
        self.detail = (self.detail + "; " if self.detail else "") + msg
        return self


def check_row(c: "Check") -> dict:
    """One qa.json row. `status` is pass | warn | fail | manual; `ok` is false only for fail
    (warn and manual do not block delivery; manual items are for the agent's eyes)."""
    row = asdict(c)
    if row["status"] == "skip":
        row["status"] = "pass"
    row["ok"] = row["status"] != "fail"
    return row


def _boxes_in_safe(m: dict) -> list[tuple[str, list[int], float, float]]:
    out = []
    for o in m["overlays"]:
        out.append((o["kind"], o["box"], o["t0"], o["t1"]))
        if o.get("qr_box"):
            out.append(("qr", o["qr_box"], o["t0"], o["t1"]))
    for c in m["captions"]["chunks"]:
        out.append(("caption", c["box"], c["start"], c["end"]))
    return out


def _safe(m: dict) -> L.SafeZone:
    s = m["layout"]["safe"]
    r = s["rect"]
    return L.SafeZone(L.Rect(r["x"], r["y"], r["w"], r["h"]), [L.Rect(e["x"], e["y"], e["w"], e["h"]) for e in s["exclusions"]],
                      s["platforms"])


def run_gate(d: Path, strict: bool = False) -> dict:
    d = Path(d)
    m = read_json(d / "manifest.json")
    if m.get("format") == "long":
        from ..engine.longform import qa_long
        return qa_long(d, strict=strict)
    video = d / m["video"]
    checks: list[Check] = []
    qa_frames = d / "qa-frames"
    qa_frames.mkdir(exist_ok=True)

    # sample once at 10 fps (small) for motion, once at 2 fps (full size) for zones
    small, st = F.sample(video, 10, 270, 480)
    full, ft = F.sample(video, 2)
    lay = m["layout"]
    sc = 1080 / 270  # small-frame scale

    # 1 format
    c = Check("format", 1, "Format: 1080x1920, H.264/AAC, native 24/25/30/50/60 fps, duration in target")
    info = ffprobe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = v["avg_frame_rate"].split("/")
    fps = float(num) / float(den)
    dur = float(info["format"]["duration"])
    c.data = {"w": v["width"], "h": v["height"], "vcodec": v["codec_name"], "acodec": a["codec_name"] if a else None,
              "fps": round(fps, 2), "duration": round(dur, 2), "pix_fmt": v.get("pix_fmt")}
    if (v["width"], v["height"]) != (1080, 1920):
        c.fail(f"size {v['width']}x{v['height']}")
    if v["codec_name"] != "h264" or not a or a["codec_name"] != "aac":
        c.fail("codecs must be h264 + aac")
    if not any(abs(fps - f) < 0.05 for f in (24, 25, 30, 50, 60)):
        c.fail(f"fps {fps:.2f}")
    tgt = m.get("duration_target")
    if tgt and not (tgt[0] - 0.5 <= dur <= tgt[1] + 0.5):
        c.fail(f"duration {dur:.1f}s outside target {tgt[0]}-{tgt[1]}s")
    if dur > 180:
        c.fail("Shorts are at most 3 minutes")
    checks.append(c)

    # 2 first frame + motion in the first 1.5 s
    c = Check("first_frame", 2, "First frame is not empty, motion in the first 1.5 s")
    first = F.frame_at(video, 0)
    Image.fromarray(first).save(qa_frames / "first.png")
    b = F.is_blank(first)
    c.data["first"] = b
    if b["blank"]:
        c.fail("first frame is (almost) blank")
    early = [i for i, t in enumerate(st) if t <= 1.5]
    mot = max((float(np.mean(np.abs(F.luma(small[i]) - F.luma(small[i - 1])))) for i in early[1:]), default=0.0)
    c.data["motion_first_1_5s"] = round(mot, 2)
    if mot < 0.8:
        c.fail("no visible motion in the first 1.5 s")
    early_caps = [ch for ch in (m.get("captions") or {}).get("chunks", []) if ch["start"] < 1.5]
    # 1.3: a title bar, post card, fact or kinetic line on screen early also carries the idea
    early_text = [o for o in m.get("overlays") or [] if o.get("kind") in EARLY_TEXT
                  and (o.get("text") or "").strip() and float(o.get("t0", 99)) < 1.5]
    if not (m["scenes"] and m["scenes"][0].get("on_screen_text")) and not early_caps and not early_text:
        c.warn("first scene has no on-screen text: the idea may not read without sound")
    checks.append(c)

    # 3 rhythm
    c = Check("rhythm", 3, "Event at least every 3 s, no still pause > 1 s")
    cy0, cy1 = int(lay["center"]["y"] / sc), int((lay["center"]["y"] + lay["center"]["h"]) / sc)
    vis = F.change_events(small, st, cy0, cy1)
    ev = sorted({round(e["t"], 2) for e in m["events"]} | {round(t, 2) for t in vis} | {0.0})
    gaps = [b - a for a, b in zip(ev, ev[1:] + [dur])]
    max_gap = max(gaps) if gaps else dur
    still = F.static_runs(small, st, cy0, cy1)
    c.data = {"events": len(ev), "max_gap": round(max_gap, 2), "visual_changes": len(vis), **still}
    if max_gap > 3.0:
        c.fail(f"{max_gap:.1f}s without an event")
    if still["longest_still"] > 1.0:
        c.fail(f"centre does not change for {still['longest_still']:.1f}s at {still['at']}s")
    if m.get("pacing") == "meaning":
        c.status = "manual"
        c.title = "Pacing by meaning and genre"
        c.detail = "Review demonstration, pauses and cuts by meaning; fixed intervals are not a quality law"
    checks.append(c)

    # 4 safe zone
    c = Check("safe_zone", 4, "Text, QR and links inside the platform safe zone")
    sz = _safe(m)
    bad = []
    for kind, box, t0, t1 in _boxes_in_safe(m):
        r = L.Rect.from_xyxy(*box)
        if not sz.allows(r, tol=4):
            bad.append(f"{kind} {box} at {t0:.1f}s")
    c.data = {"safe": sz.rect.as_list(), "platforms": sz.platforms, "outside": bad}
    if bad:
        c.fail("outside safe zone: " + ", ".join(bad[:6]))
    checks.append(c)

    # 5 contrast and sizes
    c = Check("contrast", 5, "Text contrast and minimum font sizes")
    cap = m["captions"]
    rows = []
    if cap["enabled"]:
        ratio = contrast(cap["fill"], cap["outline"])
        ratio_hl = contrast(cap["accent"], cap["outline"])
        rows.append(("caption", ratio, ratio_hl))
        if min(ratio, ratio_hl) < 7:
            c.fail(f"caption contrast {min(ratio, ratio_hl):.1f}:1 < 7:1")
        small_caps = [ch["size"] for ch in cap["chunks"] if ch["size"] < (KIN_MIN_PX if ch.get("style") == "kinetic" else 64)]
        if small_caps:
            c.fail(f"caption size {min(small_caps)} px < {KIN_MIN_PX if cap.get('style') == 'kinetic' else 64}")
    for o in m["overlays"]:
        need = 96 if o["kind"] == "label" else 40
        if o["min_font"] and o["min_font"] < need:
            c.fail(f"{o['kind']} font {o['min_font']} px < {need}")
        for fg, bg, req in o["pairs"]:
            r = contrast(fg, bg)
            rows.append((o["kind"], round(r, 2), req))
            if r < req:
                c.fail(f"{o['kind']} contrast {r:.1f}:1 < {req}:1")
    c.data["pairs"] = rows
    checks.append(c)

    # 6 centre >= 55 %, no empty zones > 15 %, panels alive
    c = Check("layout", 6, "Centre >= 55% of height, no empty zone > 15%, panels filled")
    center_pct = lay["center"]["h"] / 1920 * 100
    c.data["center_pct"] = round(center_pct, 1)
    if center_pct < 55 - 0.01:
        c.fail(f"centre {center_pct:.0f}% < 55%")
    for side in ("top", "bottom"):
        if lay[side] and lay[side]["h"] > 1920 * 0.2 + 8:
            c.fail(f"{side} panel {lay[side]['h'] / 19.2:.0f}% > 20%")
    dz = F.dead_zones(full, ft, bg=hex_to_rgb(m['brand']['palette']['bg']), ignore=_flat_on_purpose(m, dur))
    c.data["dead_zone"] = dz
    if dz["max_share"] > 0.15 and E.is_edit(m) and lay.get("mode") == "center_only":
        # full-screen film footage: a dark coat or a night sky is picture, not an empty canvas we forgot to fill
        c.data["dead_zone_note"] = "edit: flat areas are film content"
    elif dz["max_share"] > 0.15:
        c.fail(f"empty zone {dz['max_share'] * 100:.0f}% of frame (flat and static) at {dz['at']}s")
    if lay["top"]:
        act = F.region_activity(small, 0, int(lay["top"]["h"] / sc))
        c.data["top"] = act
        if act["motion"] < 0.5 or act["detail"] < 8 or act["still_share"] > 0.6:
            c.fail(f"top panel is empty or static (motion {act['motion']}, detail {act['detail']})")
        from .. import panels as PN

        y1 = int(lay["top"]["h"] / sc)
        grey = [F.luma(f[:y1]).astype(np.uint8) for f in small]
        ch = PN.change_per_second(grey, list(st))
        void = max((PN.dark_void(g, block=4) for g in grey[::max(1, len(grey) // 12)]), default=0.0)
        act.update({"change_per_second_min": ch["min"], "change_per_second_median": ch["median"],
                    "dark_void": round(void, 3), "loop": (m.get("top") or {}).get("loop")})
        if ch["n"] and ch["min"] < PN.MIN_CHANGE:
            c.fail(f"top panel: only {ch['min']:.0%} of pixels change within a second (need {PN.MIN_CHANGE:.0%}); "
                   "use layout.top.source loop:auto or livelier footage")
        if void > PN.MAX_DARK_VOID:
            c.fail(f"top panel: dark empty area {void:.0%} of the panel (max {PN.MAX_DARK_VOID:.0%})")
    if lay["bottom"]:
        y0 = int(lay["bottom"]["y"] / sc)
        act = F.region_activity(small, y0, 480)
        c.data["bottom"] = act
        bt = m.get("bottom") or {}
        if act["detail"] < 6 or not (bt.get("handle") or bt.get("links")):
            c.fail("bottom panel is empty (no handle or links)")
    checks.append(c)

    # 7 anti-slop
    c = Check("anti_slop", 7, "No glow, no gradient plates, <= 3 colours, no default font, no emoji")
    eff = m.get("effects") or {}
    for k in ("text_glow", "gradient_plate"):
        if eff.get(k):
            c.fail(f"brand.effects.{k} is on")
    glows, grads, fams = [], [], set()
    for p in sorted((d / "graphics").glob("*.png")):
        img = np.asarray(Image.open(p).convert("RGBA"))
        g = F.glow_score(img)
        gr = F.gradient_score(img)
        if g > 4.0:
            glows.append(f"{p.name} ({g:.2f})")
        if gr["gradient"]:
            grads.append(f"{p.name} (run {gr['run']}, delta {gr['delta']})")
        fams.update(f for f in F.dominant_colors(img) if f != "neutral")
    if glows:
        c.fail("glow around graphics: " + ", ".join(glows))
    if grads:
        c.fail("gradient in graphics: " + ", ".join(grads))
    # frame check: big smooth ramps in our own panels (background, bottom panel)
    frame_grads = []
    for i in range(0, len(full), max(1, len(full) // 6)):
        reg = full[i]
        if lay["bottom"]:
            gb = F.gradient_score(reg[lay["bottom"]["y"]:])
            if gb["gradient"]:
                frame_grads.append(f"bottom @{ft[i]:.1f}s")
    if frame_grads:
        c.fail("gradient in panels: " + ", ".join(frame_grads[:3]))
    pal = {p.upper() for p in (m["brand"]["palette"] or {}).values()}
    c.data = {"graphics_colour_families": sorted(fams), "palette": sorted(pal)}
    if len(pal) > 3:
        c.fail(f"{len(pal)} base colours > 3")
    if len(fams) > 2:  # accent + one more hue at most, neutrals are free
        c.fail(f"graphics use {len(fams)} hue families: {sorted(fams)}")
    fam_names = [f.lower() for f in m["brand"]["font_families"].values()]
    if any(any(f.startswith(n) for n in DEFAULT_FONT_NAMES) for f in fam_names) and not m["brand"].get("fonts_reason"):
        c.fail(f"default font without a reason: {fam_names}")
    ass = d / "captions.ass"
    if ass.exists():
        txt = ass.read_text(encoding="utf-8")
        style = [ln for ln in txt.splitlines() if ln.startswith("Style:")]
        anim = (m.get("captions") or {}).get("anim", "pop")
        static_blur = [ln for ln in txt.splitlines() if ln.startswith("Dialogue:") and re.search(r"\\(blur|be)\d", ln)
                       and not (anim == "grow" and "\\t(" in ln)]  # grow-in / blur-out transitions are motion, not glow
        if static_blur or any(ln.split(",")[17].strip() not in ("0", "0.0") for ln in style):
            c.fail("captions use blur or shadow")
    for o in m["overlays"]:
        if count_emoji(o["text"]):
            c.fail(f"emoji in {o['kind']}")
    checks.append(c)

    # 8 QR
    c = Check("qr", 8, "QR decodes from the finished video and matches the link")
    qrs = [o for o in m["overlays"] if o["kind"] == "cta_qr"]
    links = [o for o in m["overlays"] if o["kind"] in ("cta_link", "cta_handle")]
    if not qrs and links:
        c.detail = f"no QR: link/handle plate shown {len(links)}x (QR is almost useless on a phone, research 5.2)"
    elif not qrs:
        if (d / "graphics" / "banner.json").exists():
            c.detail = "Animated banner QR is decoded by the independent live_banner check"
        else:
            c.status, c.detail = "warn", "no QR in this video"
    for o in qrs:
        x0, y0, x1, y1 = o["qr_box"]
        side = min(x1 - x0, y1 - y0)
        mid = o["t0"] + min(1.2, (o["t1"] - o["t0"]) / 2)
        img = F.frame_at(video, mid)
        Image.fromarray(img).save(qa_frames / f"qr-{mid:.1f}.png")
        got = F.decode_qr(img)
        c.data.setdefault("decoded", []).append({"t": round(mid, 2), "got": got, "want": o["url"], "side": side})
        if o["url"] not in got:
            c.fail(f"QR at {mid:.1f}s does not decode to {o['url']} (got {got or 'nothing'})")
        if side < 360:
            c.fail(f"QR side {side} px < 360")
        if not o["text"]:
            c.fail("QR without a text link next to it")
    checks.append(c)

    # 9 captions
    c = Check("captions", 9, "Captions synced (150 ms), no cut words, no overflow")
    if not cap["enabled"]:
        c.status, c.detail = ("warn", "captions are off") if cap["words_spoken"] else ("pass", "no speech in this video")
    else:
        spoken = cap["words_spoken"]
        drift = []
        for ch in cap["chunks"]:
            for w in ch["words"]:
                shown_at = w.get("t0", w["s"])
                near = min((abs(shown_at - s["s"]) for s in spoken), default=9)
                drift.append(near)
        worst = max(drift) if drift else 0
        over = [ch["text"] for ch in cap["chunks"] if ch["overflow"] or ch["box"][0] < 0 or ch["box"][2] > 1080]
        sizes = [len(ch["words"]) for ch in cap["chunks"]]
        c.data = {"chunks": len(sizes), "words_per_chunk": round(float(np.mean(sizes)), 2), "max_drift": round(worst, 3),
                  "single_word_share": round(sum(1 for s in sizes if s == 1) / max(1, len(sizes)), 2)}
        if worst > CAPTION_SYNC_TOL:
            c.fail(f"caption drift {worst * 1000:.0f} ms")
        if over:
            c.fail(f"overflow: {over[:3]}")
        kin = cap.get("style") == "kinetic"
        if kin:
            kr = cap.get("kinetic") or {}
            c.data["kinetic"] = {k: kr.get(k) for k in ("blocks", "max_lines", "max_words", "min_px", "max_height_share", "min_word_s")}
            if kr.get("max_words", 0) > KIN_MAX_WORDS:
                c.fail(f"kinetic block with {kr['max_words']} words > {KIN_MAX_WORDS}")
            if kr.get("max_lines", 0) > KIN_MAX_LINES:
                c.fail(f"kinetic block with {kr['max_lines']} lines > {KIN_MAX_LINES}")
            if kr.get("max_height_share", 0) > KIN_MAX_H + 0.005:
                c.fail(f"kinetic block takes {kr['max_height_share']:.0%} of the height > {KIN_MAX_H:.0%}")
            if kr.get("min_word_s", 1) < KIN_MIN_WORD_S - 0.02:
                c.warn(f"a kinetic word is on screen {kr['min_word_s']:.2f}s < {KIN_MIN_WORD_S}s (speech too fast)")
            for n in (kr.get("notes") or [])[:3]:
                c.warn(n)
        elif max(sizes, default=0) > 4:
            c.fail("chunk with more than 4 words")
        from ..engine import captions as CP

        rep_ch = (CP.chunk_report([CP.Chunk([dict(w) for w in ch["words"]]) for ch in cap["chunks"]], m.get("language", "ru"))
                  if not kin else {"issues": []})
        c.data["breaks"] = rep_ch["issues"]
        if c.data["single_word_share"] > 0.20 and not kin:
            c.warn(f"{c.data['single_word_share']:.0%} single-word chunks (target <= 20%)")
        if rep_ch["issues"]:
            c.warn("bad breaks: " + ", ".join(rep_ch["issues"][:4]))
        est = [s["id"] for s in m["scenes"] if any("estimated" in n for n in s["notes"])]
        if est:
            c.warn(f"word timings estimated in {est}: sync not measured")
        # pixel check: caption really drawn where the manifest says (fill or accent colour present)
        miss = []
        cols = [hex_to_rgb(cap["fill"]), hex_to_rgb(cap["accent"])]
        for ch in cap["chunks"][:: max(1, len(cap["chunks"]) // 5)]:
            t = (ch["start"] + ch["end"]) / 2
            if any(o["t0"] <= t < o["t1"] and o["kind"].startswith("cta") for o in m["overlays"]):
                continue
            img = F.frame_at(video, t)
            if F.text_pixels(img, ch["box"], cols) < 0.04:
                miss.append(f"{ch['text']}@{t:.1f}s")
        if miss:
            c.fail(f"caption not visible in frame: {miss[:3]}")
        # CTA, title bar, fact plates and the arrow must not cover captions
        for o in m["overlays"]:
            if not (o["kind"].startswith("cta") or o["kind"] in COVERING):
                continue
            for ch in cap["chunks"]:
                if ch["start"] < o["t1"] and ch["end"] > o["t0"] and L.Rect.from_xyxy(*o["box"]).intersects(L.Rect.from_xyxy(*ch["box"])):
                    c.fail(f"{o['kind']} covers caption '{ch['text']}'")
                    break
    checks.append(c)

    # 10 loudness
    c = Check("loudness", 10, "Loudness -14 LUFS (+-1.5), true peak <= -1 dBTP, no clipping")
    lm = measure(video)
    c.data = {**lm, **(m.get("audio") or {})}
    if abs(lm["lufs"] - (-14)) > LUFS_TOL:
        c.fail(f"{lm['lufs']:.1f} LUFS")
    if lm["true_peak"] > -1.0 + 0.05:
        c.fail(f"true peak {lm['true_peak']:.1f} dBTP")
    if lm["clipped"]:
        c.fail(f"{lm['clipped']} clipped samples")
    sep = (m.get("audio") or {}).get("voice_minus_music_db")
    if sep is not None and not (8 - 1.5 <= sep <= 12 + 3):
        c.warn(f"voice is {sep} dB over music (target 8-12)")
    checks.append(c)

    checks.append(audio_check(m, d))

    # 11 loop
    c = Check("loop", 11, "Last frame matches the first or leads to part 2")
    last = F.frame_at(video, max(0.0, dur - 1.5 / fps))
    Image.fromarray(last).save(qa_frames / "last.png")
    diff = float(np.mean(np.abs(F.luma(first) - F.luma(last))))
    c.data["first_last_diff"] = round(diff, 2)
    last_text = " ".join([m["scenes"][-1].get("say", ""), m["scenes"][-1].get("on_screen_text", "")]).lower()
    part2 = bool(re.search(r"часть\s*2|part\s*2|продолжение|to be continued", last_text))
    c.data["part2"] = part2
    if diff > 12 and not part2:
        c.fail("end does not loop to the start and does not lead to part 2")
    if m.get("schema_version") == "1.4" and not m.get("loop", True):
        c.status, c.detail = "pass", "Standalone ending explicitly selected; no mandatory loop or part 2"
    elif not m.get("loop", True) and not part2:
        c.warn("loop is off")
    checks.append(c)

    # 12 metadata
    c = Check("metadata", 12, "Titles 5-7 (<= 100 chars), one description, no long dashes, hashtags sane")
    mp = d / "metadata.json"
    if not mp.exists():
        c.status, c.detail = ("fail" if strict else "warn"), "metadata.json missing: run `shorts.py meta DIR`"
    else:
        md = read_json(mp)
        for err in md.get("errors", []):
            c.fail(err)
        c.data = {"titles": len(md.get("titles", [])), "hashtags_unique": md.get("hashtags_unique")}
    checks.append(c)

    # 13 eyes: contact sheet + densest frames
    c = Check("eyes", 13, "Visual review: contact sheet (2 fps) and densest moments")
    pages = F.contact_sheet(video, d / "contact.png")
    K.copy_contact(pages, d)
    density = []
    for i, t in enumerate(ft):
        n = sum(1 for _, _, t0, t1 in _boxes_in_safe(m) if t0 <= t < t1)
        density.append((n, t))
    top3 = sorted(density, reverse=True)[:3]
    dense = []
    for _, t in top3:
        p = qa_frames / f"dense-{t:.1f}.png"
        Image.fromarray(F.frame_at(video, t)).save(p)
        dense.append(str(p.relative_to(d)))
    c.status = "manual"
    c.detail = "open and describe: " + ", ".join(str(p.relative_to(d)) for p in pages) + "; " + ", ".join(dense)
    c.data = {"contact_sheets": [str(p.relative_to(d)) for p in pages], "dense_frames": dense}
    checks.append(c)

    # 14 silent retell
    c = Check("silent", 14, "Without sound: retell the video from picture and captions only")
    story = []
    for s in m["scenes"]:
        if s["skipped"]:
            continue
        caps = [ch["text"] for ch in cap["chunks"] if s["start"] <= ch["start"] < s["start"] + s["length"]]
        story.append(f"{s['start']:.1f}s [{s['type']}] {s.get('on_screen_text') or ''} | {' / '.join(caps)}")
    c.status, c.detail, c.data = "manual", "retell using qa.md 'silent storyboard'", {"storyboard": story}
    checks.append(c)

    # 15 distinct from previous videos
    c = Check("distinct", 15, "Different from the user's previous videos")
    hist = M.history()
    fh = F.dhash(first)
    near = []
    for h in hist:
        if h.get("name") == m["name"]:
            continue
        if h.get("first_hash") and F.hamming(fh, h["first_hash"]) < 20:
            near.append(f"first frame like '{h.get('name')}'")
        if h.get("title") and (d / "metadata.json").exists():
            t0 = read_json(d / "metadata.json").get("recommended_title", "")
            if t0 and _similar(t0, h["title"]) > 0.8:
                near.append(f"title like '{h.get('name')}'")
    c.data = {"first_hash": fh, "compared": len(hist)}
    if near:
        c.fail("; ".join(near[:3]))
    if not hist:
        c.detail = "no previous videos in memory"
    checks.append(c)

    # extra: language and dashes in visible text, CTA rules, hook
    c = Check("text_rules", 0, "Language, no long dashes, CTA rules, hook")
    visible = [o["text"] for o in m["overlays"]] + [ch["text"] for ch in cap["chunks"]]
    joined = " ".join(visible + [s.get("say", "") for s in m["scenes"]])
    if has_long_dash(joined):
        c.fail("long dash in on-screen text or voice")
    sr = script_ratio(joined)
    lang = m["language"]
    spoken = bool(cap["chunks"]) or any(s.get("say") for s in m["scenes"])
    if sr["letters"] > 20 and lang == "ru" and sr["cyrillic"] < 0.5:
        if spoken:
            c.fail("video language is ru but text is mostly Latin")
        else:  # no speech: only a title, handle, link (film names and handles are Latin)
            c.warn("video language is ru but the on-screen text (titles, handle) is Latin; fine for names")
    if sr["letters"] > 20 and lang == "en" and sr["cyrillic"] > 0.1:
        c.fail("video language is en but text has Cyrillic")
    ctas = [o for o in m["overlays"] if o["kind"].startswith("cta")]
    if len(ctas) > 3:
        c.fail("more than 3 CTA flashes")
    for o in ctas:
        if not 1.5 - 0.01 <= o["t1"] - o["t0"] <= 3.01:
            c.fail(f"{o['kind']} lasts {o['t1'] - o['t0']:.1f}s (1.5-3)")
    for a_, b_ in zip(sorted(ctas, key=lambda o: o["t0"]), sorted(ctas, key=lambda o: o["t0"])[1:]):
        if b_["t0"] < a_["t1"]:
            c.fail(f"CTA flashes overlap in time ({a_['kind']} {a_['t0']:.1f}-{a_['t1']:.1f}s and {b_['kind']} "
                   f"{b_['t0']:.1f}-{b_['t1']:.1f}s): in the plan set the second t >= {a_['t1'] + 0.3:.1f} "
                   f"or use anchor/t_pct and let the engine place them")
    for row in m.get("cta_schedule", []):
        if row.get("dropped"):
            c.warn(f"CTA #{row['index'] + 1} ({row['kind']}) dropped: {row['reason']}")
        elif row.get("reason", "as requested") != "as requested":
            c.warn(f"CTA #{row['index'] + 1} ({row['kind']}) {row['requested']:.1f}s -> {row['final']:.1f}s: {row['reason']}")
    link_hits = sum(1 for o in ctas if o["kind"] in ("cta_handle", "cta_qr", "cta_link"))
    c.data = {"cta": len(ctas), "link_in_safe_zone": link_hits, "script": sr}
    if (m.get("bottom") or {}).get("links") and link_hits < 2:
        c.warn("link/handle shown in the safe zone fewer than 2 times")
    if [i for i in m.get("issues", []) if "[error]" in i]:
        c.fail("plan had errors (rendered with --force)")
    for i in m.get("issues", []):
        if "hook" in i or "loop:" in i:
            c.fail(i)
    checks.append(c)

    # extra: edits (film / video): what the shots show, cuts on the beat
    c = Check("edit_content", 0, "Edit: shots differ, no titles or credits, no black frames > 0.5 s")
    if E.is_edit(m):
        r = E.edit_content(m, full, ft, small, st)
        c.data = r
        for p in r["problems"]:
            c.fail(p)
        if r["ok"]:
            c.detail = f"{r['distinct_shots']}/{r['shots']} different shots, no text screens, longest black {r['longest_black_s']}s"
    else:
        c.detail = "not an edit (no film/video scenes)"
        c.data = {"applicable": False}
    checks.append(c)

    c = Check("beat_sync", 0, "Cuts on strong beats (50 ms), slow-mo on the peak")
    if (m.get("music_sync") or {}).get("enabled"):
        r = E.beat_sync(video, m, fps, dur)
        c.data = r
        if not r["beats_known"]:
            c.fail("music is beat-synced but no beat grid in the manifest")
        elif not r["ok"]:
            c.fail(f"{r['hits']}/{r['planned_cuts']} cuts on strong beats ({r['hit_share']:.0%} < {E.BEAT_MIN_HITS:.0%})")
        else:
            c.detail = f"{r['hits']}/{r['planned_cuts']} cuts on strong beats ({r['hit_share']:.0%})"
        if not r["slowmo_scenes"]:
            c.warn("no slow-mo scene on the peak")
    else:
        c.detail = "music is not beat-synced (audio.music.beat_sync is off)"
        c.data = {"applicable": False}
    checks.append(c)

    c = Check("edit_style", 0, "Edit craft: full screen, link in the centre, speed curves, faces centred, drop on the line end")
    r = E.edit_style(m, fps)
    c.data = {k: v for k, v in r.items() if k not in ("problems", "warnings")}
    if r["applicable"]:
        for p in r["problems"]:
            c.fail(p)
        for w in r["warnings"]:
            c.warn(w)
        if not r["problems"] and not r["warnings"]:
            c.detail = (f"speed curves {r['velocity_share']:.0%}, faces centred {r['faces_centred']}/{r['face_shots']}, "
                        f"drop at {r['line']['drop_at']}")
    else:
        c.detail = "no edit scenes"
    checks.append(c)

    checks.append(vfx_check(m, video, dur))
    checks.append(motion_check(video))
    checks.append(author_check(m, d))

    # v1.6: new animation is checked on compressed pixels, not configuration flags.
    banner_path = d / "graphics" / "banner.json"
    if banner_path.exists():
        from .banner import inspect_video
        spec = read_json(banner_path)
        bottom = m["layout"].get("bottom")
        bc = Check("live_banner", 0, "Independent banner motion and final QR")
        try:
            box = [bottom[k] for k in ("x", "y", "w", "h")]
            bc.data = inspect_video(video, spec, box)
            if not bc.data["motion_verified"]:
                bc.fail("One or more banner elements do not visibly change")
            if spec.get("qr_url") and not bc.data["qr_exact_all_samples"]:
                bc.fail("Final compressed QR does not preserve the exact URL at every sampled phase")
        except Exception as e:
            bc.fail(str(e))
        checks.append(bc)
    srt_path = d / "captions.srt"
    if srt_path.exists():
        from ..release import parse_srt, srt_issues
        sc = Check("srt_intervals", 0, "Sequential SRT intervals")
        try:
            issues = srt_issues(parse_srt(srt_path.read_text()), dur)
            if issues: sc.fail("; ".join(issues))
        except ValueError as e:
            sc.fail(str(e))
        checks.append(sc)
    if (d / "release.json").exists():
        from ..release import audit
        rc = Check("publication_release", 0, "Publication acceptance", status="manual")
        rc.data = audit(d)
        if rc.data["ready"]:
            rc.status = "pass"
        else:
            rc.detail = "; ".join(rc.data["issues"])
        checks.append(rc)

    fails = [x for x in checks if x.status == "fail"]
    warns = [x for x in checks if x.status == "warn"]
    manual = [x for x in checks if x.status == "manual"]
    checklist = research_checklist(m, checks, d)
    rep = {
        "passed": not fails, "video": m["video"], "duration": round(dur, 2),
        "summary": f"QA {'PASSED' if not fails else 'FAILED'}: {len(fails)} fail, {len(warns)} warn, {len(manual)} manual; "
                   f"checklist {checklist['auto_yes']}/{checklist['auto_total']} auto, {checklist['manual']} for the agent",
        "checks": [check_row(x) for x in checks], "checklist": checklist,
    }
    rep.update(K.qa_extras(rep["checks"]))
    write_json(d / "qa.json", rep)
    (d / "qa.md").write_text(to_md(rep, m), encoding="utf-8")
    if not fails:
        M.record_video(m["name"], fh, d)
    return rep


def audio_flags(m: dict, d: Path | None = None) -> dict:
    """2.2 sound honesty from a manifest: {synth_sfx: [names], music_synthetic: bool, dropped: n, mode}.
    Manifests before 2.2 have no sfx_policy: every sfx event there was synthesized in code."""
    from ..engine.audio import SYNTHETIC_MUSIC

    pol = m.get("sfx_policy")
    sfx = [e.get("name", "?") for e in (m.get("sfx") or [])]
    if pol is None:
        music = ""
        if d is not None and (Path(d) / "plan.resolved.json").exists():
            try:
                music = str((((read_json(Path(d) / "plan.resolved.json").get("audio") or {}).get("music")) or {})
                            .get("source") or "")
            except Exception:
                music = ""
        return {"mode": "legacy", "synth_sfx": sorted(set(sfx)), "dropped": 0,
                "music_synthetic": Path(music).name in SYNTHETIC_MUSIC if music else False}
    return {"mode": pol.get("mode"), "synth_sfx": list(pol.get("synthetic") or []),
            "dropped": len(pol.get("dropped") or []), "music_synthetic": bool(pol.get("music_synthetic"))}


def audio_check(m: dict, d: Path | None = None) -> Check:
    """2.2: no synthesized tones (bells, risers, 808 hits) and no generated placeholder music in a delivery."""
    c = Check("audio_honesty", 0, "Sound: real recordings only, no synthesized SFX, no placeholder music")
    f = audio_flags(m, d)
    c.data = f
    if f["mode"] == "legacy" and f["synth_sfx"]:
        c.fail(f"synthesized sound effects ({', '.join(f['synth_sfx'])}): re-render with 2.2 (audio.sfx files)")
    elif f["synth_sfx"]:
        c.warn(f"noise-only draft SFX ({', '.join(f['synth_sfx'])}, audio.sfx synth): replace with real recordings")
    if f["music_synthetic"]:
        c.warn("built-in generated music (bed.mp3 / edit.mp3) is a placeholder: deliver blocks it; use a real track "
               "or audio.export without_music")
    return c


def motion_check(video: Path) -> Check:
    """2.1: lag detector. Repeated frames / freezes make a short feel laggy (fps mismatch, stills, uneven resampling)."""
    from .. import smooth
    c = Check("smooth_motion", 0, "No lag: repeated frames and freezes")
    try:
        rep = smooth.motion_report(video, max_dup=0.15, max_freeze=0.8)
    except Exception as e:  # unreadable codec etc.: do not block on the detector itself
        c.status = "warn"
        c.detail = f"motion check skipped: {e}"
        return c
    c.data = rep["panels"]
    for p in rep["problems"]:
        c.fail(p)
    return c


def vfx_check(m: dict, video: Path, dur: float) -> Check:
    """1.3 effects: photosensitive flashes (measured), cinema bars, how many signature moves."""
    c = Check("vfx", 0, "Effects: <= 3 flashes per second (WCAG 2.3.1), bars do not hide the hook, motivated effects")
    vx = m.get("vfx") or {}
    fl = F.flash_report(video, float(m.get("fps", 30)))
    c.data["flashes"] = fl
    if fl["max_flashes"] > F.FLASH_MAX:
        c.fail(f"{fl['max_flashes']:g} flashes within 1 s at {fl['at']:.1f}s ({fl['region']}), max {F.FLASH_MAX}: "
               "lower fx.flicker, a flash transition or the cuts there")
    lb = vx.get("letterbox") or {}
    if lb:
        closed = sum(b - a for a, b in lb.get("closed") or [])
        c.data["letterbox"] = {"closed_at_start_s": lb.get("closed_at_start_s", 0), "closed_share": round(closed / max(dur, 0.1), 2)}
        if lb.get("closed_at_start_s", 0) > LETTERBOX_START_MAX:
            c.warn(f"bars closed for the first {lb['closed_at_start_s']:.1f}s (> {LETTERBOX_START_MAX:g}s): open them by the hook")
        if closed / max(dur, 0.1) > LETTERBOX_SHARE_MAX:
            c.warn(f"bars are on {closed / dur:.0%} of the video: a vertical frame is mostly black")
    notable = vx.get("notable") or []
    c.data["notable"] = notable
    if notable:
        c.data["editorial_review"] = "Explain each effect's role and check visual clutter; effect count alone is not quality"
    lk = vx.get("look_keys") or {}
    if lk.get("changes", 0) > LOOK_CHANGES_MAX:
        c.warn(f"{lk['changes']} colour switches (> {LOOK_CHANGES_MAX})")
    tr = vx.get("transitions") or []
    c.data["transitions"] = len(tr)
    for n in (vx.get("notes") or [])[:4]:
        c.warn(n)
    if not (lb or notable or tr or vx.get("splits")) and c.status == "pass":
        c.detail = f"no 1.3 effects; flashes max {fl['max_flashes']:g}/s"
    return c


def _ver(v) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (1,)


def author_check(m: dict, d: Path) -> Check:
    """Foreign footage (film, game background, someone's clip) needs the author's own layers (research 15, 22)."""
    c = Check("author_layer", 0, "Foreign footage has >= 2 author layers (one core), no long stretch without them, credits")
    al = m.get("author_layer") or {}
    c.data = al
    foreign = al.get("foreign") or []
    if not foreign:
        c.detail = "no foreign footage"
        return c
    strict = _ver(m.get("schema_version", "1")) >= (1, 3)
    no_core = "core" in al and not al["core"]
    if al.get("count", 0) < 2 or no_core:
        why = "none of them voice, thesis, own footage or a comparison" if al.get("count", 0) >= 2 else \
            f"{al.get('count', 0)} author layer(s)"
        msg = (f"foreign footage ({', '.join(foreign[:3])}) with {why}: add voice, "
               "thesis text, own footage or a comparison (author_layer)")
        c.fail(msg) if strict else c.warn(msg)
    if al.get("longest_foreign_only_s", 0) > FOREIGN_ONLY_MAX:
        c.warn(f"{al['longest_foreign_only_s']:.0f}s of foreign footage without your voice or text")
    credits = [x for x in al.get("credits") or [] if x]
    md = read_json(d / "metadata.json") if (d / "metadata.json").exists() else {}
    if credits and md.get("description") and not all(x.split(" (")[0] in md["description"] for x in credits):
        c.warn("background credit is not in the description: " + "; ".join(credits))
    return c


def _similar(a: str, b: str) -> float:
    wa, wb = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return len(wa & wb) / max(1, len(wa | wb))


def research_checklist(m: dict, checks: list[Check], d: Path) -> dict:
    by = {c.id: c for c in checks}

    def ok(cid: str) -> str:
        return "yes" if by[cid].status in ("pass", "warn") else "no"

    md = read_json(d / "metadata.json") if (d / "metadata.json").exists() else {}
    cover = (d / "cover" / "cover.json")
    items = [
        (1, "First frame interesting, not black, not a logo", ok("first_frame"), "auto"),
        (2, "First line gives the result or a question, no greeting", "no" if any("hook" in i for i in m.get("issues", [])) else "yes", "auto"),
        (3, "Idea reads on the first frame, small and without sound", "check", "manual"),
        (4, "Title: key words first, honest, <= 100 chars, <= 1 emoji", "yes" if md and not md.get("errors") else "no", "auto"),
        (5, "Cover: one focus, 3-5 words, readable at 320 px, contrast", "yes" if cover.exists() and not read_json(cover).get("errors") else "check", "auto" if cover.exists() else "manual"),
        (6, "Event every 2-3 s", ok("rhythm"), "auto"),
        (7, "No pause > 1 s without a visual event", ok("rhythm"), "auto"),
        (8, "Promise from the start is kept by the end", "check", "manual"),
        (9, "No goodbye, the end loops or leads to part 2", ok("loop"), "auto"),
        (10, "Clear without sound, captions present", "yes" if by["captions"].status in ("pass", "warn") and m["captions"]["enabled"] or not m["captions"]["words_spoken"] else "no", "auto"),
        (11, "One call to action, after the value", "yes" if len([o for o in m["overlays"] if o["kind"].startswith("cta")]) <= 3 else "no", "auto"),
        (12, "Link/handle in the safe zone twice, QR scans", "yes" if by["qr"].status == "pass" and by["text_rules"].data.get("link_in_safe_zone", 0) >= 2 else "no", "auto"),
        (13, "Pinned comment and description ready", "yes" if md.get("pinned_comment") and md.get("description") else "no", "auto"),
        (14, "Profile ready (remind the user)", "check", "manual"),
        (15, "Everything important inside the safe zone", ok("safe_zone"), "auto"),
        (16, "No slop: glow, gradients, empty zones, default font", "yes" if ok("anti_slop") == "yes" and ok("layout") == "yes" else "no", "auto"),
        (17, "Texts in the right language, no long dashes", ok("text_rules"), "auto"),
        (18, "About -14 LUFS, voice over music", ok("loudness"), "auto"),
        (19, "'Altered or synthetic content' label checked", "check", "manual"),
        (20, "Clearly different from previous videos", ok("distinct"), "auto"),
    ]
    auto = [i for i in items if i[3] == "auto"]
    return {"items": [{"n": n, "text": t, "answer": a, "how": h} for n, t, a, h in items],
            "auto_yes": sum(1 for i in auto if i[2] == "yes"), "auto_total": len(auto),
            "manual": sum(1 for i in items if i[3] == "manual")}


def to_md(rep: dict, m: dict) -> str:
    icon = {"pass": "OK", "fail": "FAIL", "warn": "WARN", "manual": "EYES", "skip": "-"}
    out = [f"# QA: {m['name']}", "", rep["summary"], "", "| # | Check | Result | Detail |", "|---|---|---|---|"]
    for c in rep["checks"]:
        out.append(f"| {c['item'] or '+'} | {c['title']} | {icon[c['status']]} | {c['detail'].replace('|', '/')} |")
    out += ["", "## Checklist (research, section 9)", "", "| # | Item | Answer | How |", "|---|---|---|---|"]
    for i in rep["checklist"]["items"]:
        out.append(f"| {i['n']} | {i['text']} | {i['answer']} | {i['how']} |")
    sil = next(c for c in rep["checks"] if c["id"] == "silent")["data"]["storyboard"]
    out += ["", "## Silent storyboard (picture + captions only)", ""] + [f"- {s}" for s in sil]
    out += ["", "## Agent must still do", "",
            "1. Open the contact sheets and dense frames, write what you saw (item 13).",
            "2. Retell the video from the storyboard without sound (item 14).",
            "3. Answer the manual checklist items (3, 8, 14, 19) honestly.", ""]
    return "\n".join(out)
