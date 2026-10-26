import pytest

from shortskit.config import H
from shortskit.engine import layout as L


def test_center_at_least_55_percent_in_every_mode():
    for mode in L.MODES:
        lay = L.compute({"mode": mode}, ["youtube_shorts"])
        assert lay.center_pct >= 55, mode
        assert lay.center.y % 8 == 0 and lay.center.h % 8 == 0


def test_panel_sizes_and_removal():
    lay = L.compute({"mode": "three", "top": {"height_pct": 20}, "bottom": {"height_pct": 16}}, ["youtube_shorts"])
    assert lay.top.h == 384 and lay.bottom.h == 304 and lay.center.h == H - 384 - 304
    assert L.compute({"mode": "center_only"}, ["youtube_shorts"]).top is None
    assert L.compute({"mode": "top_center"}, ["youtube_shorts"]).bottom is None
    assert L.compute({"mode": "center_bottom"}, ["youtube_shorts"]).top is None


def test_safe_zone_youtube_numbers():
    z = L.safe_zone(["youtube_shorts"]).rect
    assert (z.x, z.y, z.x1, z.y1) == (48, 288, 1080 - 192, 1920 - 672)


def test_safe_zone_intersection_and_tiktok_column():
    z = L.safe_zone(["youtube_shorts", "tiktok", "reels"])
    assert z.rect.x == 120 and z.rect.y == 288 and z.rect.y1 == 1920 - 672
    assert z.exclusions  # tiktok action column
    lay = L.compute({"mode": "three"}, ["youtube_shorts", "tiktok"])
    # caption band is clipped left of the TikTok action column and stays inside the zone
    assert lay.caption_band.x1 <= 780
    assert z.allows(lay.caption_band)
    assert z.allows(lay.cta_box)


def test_caption_band_is_lower_third_of_safe_zone():
    lay = L.compute({"mode": "three"}, ["youtube_shorts"])
    s = lay.safe.rect
    assert lay.caption_band.y >= s.y + s.h * 0.6
    assert lay.caption_band.y1 <= 1920 - 672  # never in the bottom 672 px


# ---------------------------------------------------------------- 1.1.0 item 9: TikTok and Reels from official sources

def test_tiktok_zone_matches_official_template():
    z = L.safe_zone(["tiktok"])
    assert (z.rect.x, z.rect.y, z.rect.x1, z.rect.y1) == (120, 240, 960, 1260)
    assert [(e.x, e.y, e.x1, e.y1) for e in z.exclusions] == [(780, 840, 1080, 1920)]


def test_reels_zone_is_meta_percentages():
    z = L.safe_zone(["reels"]).rect
    assert (z.x, z.y, z.x1, z.y1) == (65, 269, 1080 - 65, 1920 - 672)
    assert round(269 / 1920, 2) == 0.14 and round(672 / 1920, 2) == 0.35 and round(65 / 1080, 2) == 0.06


@pytest.mark.parametrize("plat,box,ok", [
    ("tiktok", (200, 900, 700, 1000), True),
    ("tiktok", (600, 900, 900, 1000), False),   # runs into the like/comment column
    ("tiktok", (200, 1270, 700, 1350), False),  # under the caption/music line
    ("tiktok", (60, 500, 400, 600), False),     # too close to the left edge
    ("reels", (100, 300, 980, 400), True),
    ("reels", (100, 200, 980, 260), False),     # top 14 %
    ("reels", (100, 1260, 980, 1330), False),   # bottom 35 %
    ("youtube_shorts", (100, 1260, 700, 1330), False),
])
def test_boxes_against_platform_zones(plat, box, ok):
    assert L.safe_zone([plat]).allows(L.Rect.from_xyxy(*box)) is ok


def test_every_zone_has_source_and_check_date():
    import json

    from shortskit.config import skill_root

    d = json.loads((skill_root() / "schema" / "safe_zones.json").read_text(encoding="utf-8"))
    for k in ("youtube_shorts", "tiktok", "reels"):
        assert d[k]["source"].startswith("https://") and d[k]["checked"], k
        assert all(isinstance(d[k][s], int) for s in ("top", "bottom", "left", "right")), k


def test_viora_spec_copy_matches():
    import json

    from shortskit.config import skill_root

    viora = skill_root().parent.parent / "viora-v8" / "spec" / "safe_zones.json"
    if not viora.exists():
        pytest.skip("skill copied without the viora-v8 folder")
    a = json.loads((skill_root() / "schema" / "safe_zones.json").read_text(encoding="utf-8"))
    b = json.loads(viora.read_text(encoding="utf-8"))
    for k in ("youtube_shorts", "tiktok", "reels"):
        assert {x: a[k][x] for x in ("top", "bottom", "left", "right")} == {x: b[k][x] for x in ("top", "bottom", "left", "right")}
