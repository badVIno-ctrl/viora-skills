"""Ad slot (v2.3): the card never covers the main picture AND the visible screen has no dead band.

2.2 -> 2.3 (review of a delivered short, "Быстрый VPN в Telegram"): the card sat at y 912-1232 because the bottom 672 px
(the official AD template, stricter than organic posts) were treated as invisible. The lower 36% of the screen was an
empty blur, the card looked "pushed up" and the speaker was small. 2.3:
  * safe profile (`spec.safe`): `organic` (default) - the bottom tray of organic Shorts/TikTok (channel, Subscribe,
    title, sound) is 420-576 px in 2026 guides, working value 480; right rail 150 px. `strict` - the 2.2 numbers
    (Google ad template 288/672/48/192, Meta 14%/35%/6%) for paid placements and Reels ads.
  * slot `below` (alias `bottom`) anchors the card to the BOTTOM of the visible area (16 px above the tray); the main
    picture grows into the freed space; an automatic top panel (`top.h` absent or "auto") is balanced so the main
    picture gets >= 62% of top + main.
  * layout `center` (`spec.layout`): the whole screen is a blurred copy of the main video, the sharp main picture is an
    inset in the middle (`main.shape`: rect | round | circle, `main.aspect`: "auto" (fills the free height, at most
    4:5) | "16:9" | "1:1" | number), the card under it, the title band (200-316) above it. Optional top panel above.
  * the bottom is busy (ad bar, `bottom` panel) -> `auto` moves the card up: filler (over the top panel) or above.
  * dead zone check: inside the visible area (120 .. tray) no band taller than 80 px (240 in `center`) may be only blur.

resolve(spec, card_wh) -> {"top": rect|None, "main": rect, "bar": rect|None, "card": rect|None, "fill": [rects],
                           "slot": name, "layout": "stack"|"center", "shape": str, "safe": {...}, "dead": [...],
                           "notes": [...]}                       rect = [x, y, w, h]; card = the VISIBLE card (no shadow)
"""
from __future__ import annotations

import math

W, H = 1080, 1920
PROFILES = {
    "organic": {"top": 200, "bottom": 480, "left": 48, "right": 150},
    "strict": {"top": 288, "bottom": 672, "left": 48, "right": 192},
}
SAFE_TOP, SAFE_BOTTOM = 288, H - 672      # the strict (2.2) values, kept for old callers
UI_TOP = 120          # nothing of the card above this (status bar, Shorts search/menu icons)
GAP = 24
MIN_MAIN = 560
MIN_TOP = 240
AUTO_TOP_MAX = 480
MAIN_SHARE = 0.62     # automatic top panel: the main picture keeps >= 62% of top + main
DEAD_MAX = 80
DEAD_MAX_CENTER = 240     # center layout: the band above the inset holds the title / hook
CARD_X_SHIFT = -48    # the card leans left: the right rail holds the like/comment buttons
CENTER_SIDE = 40      # side margin of the inset main picture in the `center` layout


def profile(spec: dict | None) -> dict:
    raw = (spec or {}).get("safe")
    if isinstance(raw, dict) and raw.get("bottom_y") is not None:      # already resolved (layout dict)
        return dict(raw)
    custom = raw if isinstance(raw, dict) else None                    # {"base": "organic", "bottom": 380}: own numbers
    name = str((custom or {}).get("base") if custom else (raw or "organic")).lower()
    if name not in PROFILES:
        name = "organic"
    p = dict(PROFILES[name])
    if custom:
        lim = {"top": (120, 400), "bottom": (240, 800), "left": (0, 120), "right": (0, 240)}
        for k, (lo, hi) in lim.items():
            if isinstance(custom.get(k), (int, float)):
                p[k] = int(min(hi, max(lo, custom[k])))
        name = "custom"
    p.update(name=name, top_y=p["top"], bottom_y=H - p["bottom"])
    return p


def visible_bottom(lay_or_spec: dict) -> int:
    s = lay_or_spec.get("safe") if isinstance(lay_or_spec.get("safe"), dict) else None
    return int(s["bottom_y"]) if s and s.get("bottom_y") is not None else profile(lay_or_spec)["bottom_y"]


def _rect_overlap(a, b) -> int:
    if not a or not b:
        return 0
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = min(ax + aw, bx + bw) - max(ax, bx)
    h = min(ay + ah, by + bh) - max(ay, by)
    return max(0, w) * max(0, h)


def overlap(a, b) -> int:
    return _rect_overlap(a, b)


def _card_x(cw: int, x=None) -> int:
    return int(x) if x is not None else (W - cw) // 2 + CARD_X_SHIFT


def _aspect(v, default: float) -> float:
    if v in (None, "", "auto", "source"):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("x", ":").replace("/", ":")
    if ":" in s:
        a, b = s.split(":", 1)
        return float(a) / float(b)
    return float(s)


def _top_h(top: dict | None, mb: int, notes: list) -> int:
    """Top panel height when the card sits below the main picture (mb = bottom edge of the main picture)."""
    if not top:
        return 0
    req = top.get("h")
    want_main = max(MIN_MAIN, int(math.ceil(MAIN_SHARE * mb)))
    if req in (None, "auto"):
        return max(MIN_TOP, min(AUTO_TOP_MAX, mb - want_main))
    th = int(req)
    if mb - th >= MIN_MAIN:
        return th
    t2 = max(MIN_TOP, mb - MIN_MAIN)
    notes.append(f"top panel {th} -> {t2} px so the main picture ({mb - t2} px) and the card both fit")
    return t2


def resolve(spec: dict, card_wh: tuple[int, int] | None) -> dict:
    """Panel rectangles + the card slot. Without a card: the 2.1 layout (top + main + bar)."""
    prof = profile(spec)
    vb = prof["bottom_y"]
    layout = str(spec.get("layout") or "stack").lower()
    if layout not in ("stack", "center"):
        layout = "stack"
    bar_h = int((spec.get("adbar") or {}).get("height", 300)) if spec.get("adbar") else 0
    top = spec.get("top")
    th = (540 if top.get("h") in (None, "auto") else int(top["h"])) if top else 0
    main = spec["main"]
    notes: list[str] = []
    bottom = H - bar_h
    explicit = main.get("y") is not None or main.get("h") is not None
    py = int(main["y"]) if main.get("y") is not None else th
    ph = int(main["h"]) if main.get("h") is not None else bottom - py
    lay = {"top": [0, 0, W, th] if th else None, "main": [0, py, W, ph], "bar": [0, bottom, W, bar_h] if bar_h else None,
           "card": None, "fill": [], "slot": None, "layout": layout, "shape": "rect",
           "safe": {k: prof[k] for k in ("name", "top", "bottom", "left", "right", "bottom_y")}, "notes": notes}
    b = spec.get("banner") or {}
    slot = str(b.get("slot", "auto")).lower() if card_wh else None
    if slot == "bottom":
        slot = "below"
    busy_bottom = bool(bar_h) or bool(spec.get("bottom"))
    if layout == "center":
        return _center(spec, card_wh, lay, prof, slot, busy_bottom)
    if not card_wh:
        return _finish(lay)
    cw, ch = int(card_wh[0]), int(card_wh[1])
    if b.get("y") is not None and slot == "auto":
        slot = "manual"
    if slot == "manual":
        card = [_card_x(cw, b.get("x")), int(b["y"]), cw, ch]
        if b.get("over_video") or not _rect_overlap(card, lay["main"]):
            lay.update(card=card, slot="manual")
            if b.get("over_video"):
                notes.append("card over the video on purpose (over_video): the face check decides")
            return _finish(lay)
        notes.append(f"banner y={b['y']} covered the main picture ({_rect_overlap(card, lay['main']) // 1000}k px): slot chosen automatically")
        slot = "auto"
    if slot == "below" and busy_bottom:
        notes.append("slot below asked, but the bottom is busy (ad bar / bottom panel): the card goes up")
        slot = "auto"
    if slot in ("auto", "below") and not busy_bottom:
        cy = vb - 16 - ch                         # the card stands on the bottom of the visible area
        mb = cy - GAP
        t2 = _top_h(top, mb, notes)
        if mb - t2 >= MIN_MAIN or slot == "below":
            m_top = max(t2, py) if explicit and mb - max(t2, py) >= MIN_MAIN else t2      # an explicit main y is kept when it fits
            if explicit and (m_top != py or mb - m_top != ph):
                notes.append(f"main y/h {py}/{ph} -> {m_top}/{mb - m_top}: the card sits under the picture")
            lay.update(top=[0, 0, W, t2] if t2 else None, main=[0, m_top, W, mb - m_top], card=[_card_x(cw), cy, cw, ch], slot="below")
            return _finish(lay)
        slot = "auto"
    if slot in ("auto", "filler") and th:
        t2 = max(th, UI_TOP + ch + GAP)
        if t2 != th:
            notes.append(f"top panel {th} -> {t2} px to hold the card")
        mh = (bottom - t2) if not explicit else max(MIN_MAIN, py + ph - t2)
        lay.update(top=[0, 0, W, t2], main=[0, t2, W, mh], card=[_card_x(cw), t2 - GAP - ch, cw, ch], slot="filler")
        return _finish(lay)
    band = UI_TOP + ch + GAP
    mh = bottom - band if not explicit else max(MIN_MAIN, py + ph - band)
    lay.update(main=[0, band, W, mh], card=[_card_x(cw), UI_TOP, cw, ch], slot="above")
    return _finish(lay)


def _center(spec: dict, card_wh, lay: dict, prof: dict, slot: str | None, busy_bottom: bool) -> dict:
    """Blurred full-screen copy of the main video + sharp inset main picture + card under it (or above it)."""
    notes = lay["notes"]
    main, top, vb = spec["main"], spec.get("top"), prof["bottom_y"]
    shape = str(main.get("shape", "round")).lower()
    if shape not in ("rect", "round", "circle"):
        shape = "round"
    bottom = (lay["bar"][1] - GAP) if lay.get("bar") else vb - 16
    card = None
    cw = ch = 0
    if card_wh:
        cw, ch = int(card_wh[0]), int(card_wh[1])
        if slot in ("auto", "below", "manual") and not busy_bottom:
            card = [_card_x(cw), vb - 16 - ch, cw, ch]
            bottom = card[1] - GAP
            lay["slot"] = "below"
            if slot == "manual":
                notes.append("center layout: manual card position replaced by the slot under the picture")
    th = 0
    if top:
        th = top.get("h")
        th = 400 if th in (None, "auto") else int(th)
    if card_wh and card is None:                 # bottom busy / filler / above: the card goes over the top panel or on top
        if th:
            th = max(th, UI_TOP + ch + GAP)
            card = [_card_x(cw), th - GAP - ch, cw, ch]
            lay["slot"] = "filler"
        else:
            card = [_card_x(cw), UI_TOP, cw, ch]
            lay["slot"] = "above"
    r0 = th + GAP if th else (UI_TOP + ch + GAP if lay["slot"] == "above" else prof["top_y"] + 140)
    r1 = bottom
    region = max(200, r1 - r0)
    side = int(main.get("side", CENTER_SIDE))
    if shape == "circle":
        d = int(main.get("size") or min(region, W - 2 * max(side, 110)))
        d = min(d, region)
        mw = mh = d
    else:
        mw = W - 2 * side
        a = _aspect(main.get("aspect"), 0.8)          # auto: fill the free height, never taller than 4:5
        mh = min(region, int(round(mw / a)))
    mx = (W - mw) // 2
    my = r0 + (region - mh) // 2
    lay.update(top=[0, 0, W, th] if th else None, main=[mx, my, mw, mh], card=card, shape=shape)
    if card and _rect_overlap(card, lay["main"]):
        notes.append("center layout: the card touched the inset picture, the picture was moved")
        lay["main"][1] = max(r0, card[1] + ch + GAP) if lay["slot"] != "below" else lay["main"][1]
    return _finish(lay)


def _fills(lay: dict) -> None:
    """Every pixel row that neither the top panel, the main picture nor the bar covers gets a blurred copy of the main
    picture (never black, never a stale frame). In `center` the whole screen is the blurred copy."""
    if lay.get("layout") == "center":
        lay["fill"] = [[0, 0, W, H]]
        return
    used = []
    for k in ("top", "main", "bar"):
        r = lay.get(k)
        if r and r[3] > 0:
            used.append((r[1], r[1] + r[3]))
    used.sort()
    y, fills = 0, []
    for a, b in used:
        if a > y:
            fills.append([0, y, W, a - y])
        y = max(y, b)
    if y < H:
        fills.append([0, y, W, H - y])
    lay["fill"] = fills


def dead_zones(lay: dict) -> list[list[int]]:
    """Bands [y0, y1] inside the visible area (UI_TOP .. bottom of the safe profile) where only blur is shown."""
    vb = visible_bottom(lay)
    rows = [False] * H
    for k in ("top", "main", "bar", "card"):
        r = lay.get(k)
        if r and r[3] > 0:
            for y in range(max(0, r[1]), min(H, r[1] + r[3])):
                rows[y] = True
    out, y = [], UI_TOP
    while y < vb:
        if rows[y]:
            y += 1
            continue
        y0 = y
        while y < vb and not rows[y]:
            y += 1
        out.append([y0, y])
    return out


def _finish(lay: dict) -> dict:
    _fills(lay)
    lim = DEAD_MAX_CENTER if lay.get("layout") == "center" else DEAD_MAX
    lay["dead"] = [z for z in dead_zones(lay) if z[1] - z[0] > lim]
    return lay


def check(lay: dict, faces_by_frame: list | None = None, caption_rects: list | None = None) -> list[str]:
    """Problems: card on the main picture (unless over_video), card outside the screen / under the top UI / in the
    bottom tray, a face under the card in > 2% of frames, a caption on the card, a dead band in the visible area."""
    out = []
    for y0, y1 in lay.get("dead") or []:
        out.append(f"dead zone y {y0}-{y1} ({y1 - y0} px) inside the visible area: only blur there. Give it to the main "
                   f"picture (main.h), let the card stand on the bottom (slot below) or use layout center")
    card = lay.get("card")
    if not card:
        return out
    x, y, w, h = card
    vb = visible_bottom(lay)
    if x < 0 or x + w > W or y < UI_TOP - 1 or y + h > vb:
        out.append(f"card {card} leaves the safe area (x 0-{W}, y {UI_TOP}-{vb}, profile {lay.get('safe', {}).get('name', 'organic')})")
    if lay.get("slot") != "manual" and _rect_overlap(card, lay.get("main")):
        out.append("card covers the main picture")
    if faces_by_frame:
        hit = sum(1 for fs in faces_by_frame if any(_rect_overlap(card, f) > 0.15 * f[2] * f[3] for f in fs))
        if hit > 0.02 * len(faces_by_frame):
            out.append(f"a face is under the card in {hit} of {len(faces_by_frame)} sampled frames")
    for r in caption_rects or []:
        if _rect_overlap(card, r):
            out.append(f"caption {r} is on the card")
            break
    return out
