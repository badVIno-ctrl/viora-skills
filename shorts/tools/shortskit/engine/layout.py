"""Frame geometry: panels, platform safe zone, where captions, labels and CTA flashes go.

All numbers are px on a 1080x1920 frame and multiples of 8.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..config import H, W, schema_path
from ..util import ShortsError, read_json, snap8

CENTER_MIN = 0.55
PANEL_MAX = 0.20
DEFAULT_TOP_PCT = 20.0
DEFAULT_BOTTOM_PCT = 16.0
MODES = ("three", "top_center", "center_bottom", "center_only", "band")
BAND_MIN = 1056  # band mode: the picture band is >= 55% of the height (same rule as the centre)


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def x1(self) -> int:
        return self.x + self.w

    @property
    def y1(self) -> int:
        return self.y + self.h

    def contains(self, o: "Rect", tol: int = 0) -> bool:
        return o.x >= self.x - tol and o.y >= self.y - tol and o.x1 <= self.x1 + tol and o.y1 <= self.y1 + tol

    def intersects(self, o: "Rect") -> bool:
        return not (o.x >= self.x1 or o.x1 <= self.x or o.y >= self.y1 or o.y1 <= self.y)

    def as_list(self) -> list[int]:
        return [self.x, self.y, self.x1, self.y1]

    @staticmethod
    def from_xyxy(x0: float, y0: float, x1: float, y1: float) -> "Rect":
        return Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))


@dataclass
class SafeZone:
    rect: Rect
    exclusions: list[Rect] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)

    def allows(self, box: Rect, tol: int = 0) -> bool:
        if not self.rect.contains(box, tol):
            return False
        return not any(ex.intersects(box) for ex in self.exclusions)


@dataclass
class Layout:
    mode: str
    top: Rect | None
    center: Rect
    bottom: Rect | None
    safe: SafeZone
    caption_band: Rect
    label_box: Rect
    cta_box: Rect

    @property
    def center_pct(self) -> float:
        return self.center.h / H * 100

    def to_dict(self) -> dict:
        d = asdict(self)
        d["center_pct"] = round(self.center_pct, 2)
        return d


def load_safe_zones() -> dict:
    return read_json(schema_path("safe_zones.json"))


def safe_zone(platforms: list[str]) -> SafeZone:
    zones = load_safe_zones()
    top = bottom = left = right = 0
    excl: list[Rect] = []
    used = []
    for p in platforms or ["youtube_shorts"]:
        z = zones.get(p)
        if z is None:
            raise ShortsError(f"unknown platform: {p}")
        if "alias" in z:
            z = zones[z["alias"]]
        if z.get("top") is None:
            raise ShortsError(f"safe zone for {p} is not filled in schema/safe_zones.json")
        top, bottom = max(top, z["top"]), max(bottom, z["bottom"])
        left, right = max(left, z["left"]), max(right, z["right"])
        excl += [Rect.from_xyxy(*e) for e in z.get("exclusions", [])]
        used.append(p)
    return SafeZone(Rect.from_xyxy(left, top, W - right, H - bottom), excl, used)


def _centred(r: Rect, exclusions: list[Rect]) -> Rect:
    """Widest strip of r symmetric around the frame centre; left-aligned in front of an exclusion if one cuts in."""
    for ex in exclusions:
        if ex.intersects(r):
            return Rect(r.x, r.y, max(0, ex.x - r.x), r.h)
    half = min(W // 2 - r.x, r.x1 - W // 2)
    return Rect(W // 2 - half, r.y, 2 * half, r.h)


def compute(plan_layout: dict, platforms: list[str]) -> Layout:
    mode = plan_layout.get("mode", "three")
    if mode not in MODES:
        raise ShortsError(f"layout.mode must be one of {MODES}")
    has_top = mode in ("three", "top_center")
    has_bottom = mode in ("three", "center_bottom")
    top_h = snap8(H * float((plan_layout.get("top") or {}).get("height_pct", DEFAULT_TOP_PCT)) / 100) if has_top else 0
    bot_h = snap8(H * float((plan_layout.get("bottom") or {}).get("height_pct", DEFAULT_BOTTOM_PCT)) / 100) if has_bottom else 0
    reserve = snap8(H * float((plan_layout.get("bottom") or {}).get("reserve_bottom_pct", 0)) / 100) if has_bottom else 0
    if reserve < 0 or top_h + bot_h + reserve >= H:
        raise ShortsError("Invalid reserved interface area")
    center = Rect(0, top_h, W, H - top_h - bot_h - reserve)
    sz = safe_zone(platforms)
    s = sz.rect
    if mode == "band":
        # "kinobust" frame: black fields, the picture band in the middle, a title plate in the top field
        bh = max(BAND_MIN, min(H, snap8(float(plan_layout.get("band_h", BAND_MIN)))))
        y0 = plan_layout.get("band_y")
        y0 = snap8((H - bh) / 2) if y0 is None else max(0, min(H - bh, snap8(float(y0))))
        center = Rect(0, y0, W, bh)

    # captions: lower third of the safe zone. Text is centred on the FRAME centre (x = 540), not on the
    # safe-zone centre: the Shorts zone is asymmetric (48 px left, 192 px right), and centring on it put
    # links and captions ~70 px left of the middle ("the link came out crooked"). The box is the widest
    # symmetric strip inside the zone; only an exclusion (TikTok button column) moves it off-centre.
    band_y0 = snap8(s.y + s.h * 2 / 3)
    band = _centred(Rect(s.x, band_y0, s.w, s.y1 - band_y0), sz.exclusions)
    label = _centred(Rect(s.x, s.y + 16, s.w, 240), sz.exclusions)
    cta_y1 = band.y - 16
    cta = _centred(Rect(s.x, s.y + 16, s.w, cta_y1 - (s.y + 16)), sz.exclusions)
    return Layout(mode, Rect(0, 0, W, top_h) if has_top else None, center,
                  Rect(0, H - bot_h - reserve, W, bot_h) if has_bottom else None, sz, band, label, cta)
