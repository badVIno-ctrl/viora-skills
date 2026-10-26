"""2.3 layout (review of a delivered short: the card floated at 912-1232, the lower 36% of the screen was empty blur).

1. organic safe profile: the card stands on the bottom of the visible area (16 px above the 480 px tray)
2. strict profile reproduces the 2.2 numbers (ad templates)
3. automatic top panel is balanced: the main picture keeps >= 62% of top + main
4. a busy bottom (ad bar) moves the card up
5. layout center: blurred full screen + inset picture; no overlap, no dead band with aspect auto
6. dead zones are detected and reported as problems
7. the center layout really renders (inset sharp, corners blurred)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from shortskit import adslot
from shortskit import stack as S

CARD = (760, 320)
TOP = {"src": "g.mp4"}


def _rows_covered(lay):
    rows = np.zeros(1920, bool)
    for r in [lay["top"], lay["main"], lay["bar"], *lay["fill"]]:
        if r:
            rows[r[1]:r[1] + r[3]] = True
    return rows.all()


def test_organic_card_stands_on_the_bottom_of_the_visible_area():
    lay = adslot.resolve({"main": {"pieces": []}, "top": dict(TOP), "banner": {}}, CARD)
    x, y, w, h = lay["card"]
    assert lay["safe"]["name"] == "organic" and lay["slot"] == "below"
    assert y + h == 1920 - 480 - 16
    assert lay["main"][1] + lay["main"][3] == y - adslot.GAP          # the main picture reaches the card
    assert not lay["dead"] and adslot.check(lay) == [] and _rows_covered(lay)
    assert x + w <= 1080 - 150                                          # clear of the like/comment rail


def test_strict_profile_keeps_the_2_2_numbers():
    lay = adslot.resolve({"main": {"pieces": []}, "top": dict(TOP, h=480), "banner": {}, "safe": "strict"}, CARD)
    assert lay["card"][1] == 912 and lay["card"][1] + lay["card"][3] == 1232
    assert lay["top"][3] == 328 and lay["main"] == [0, 328, 1080, 560]


def test_auto_top_panel_is_balanced_and_explicit_height_is_kept():
    auto = adslot.resolve({"main": {"pieces": []}, "top": dict(TOP), "banner": {}}, CARD)
    t, m = auto["top"][3], auto["main"][3]
    assert m >= 0.62 * (t + m) - 1 and t >= adslot.MIN_TOP
    fixed = adslot.resolve({"main": {"pieces": []}, "top": dict(TOP, h=480), "banner": {}}, CARD)
    assert fixed["top"][3] == 480 and fixed["main"][3] >= adslot.MIN_MAIN


def test_busy_bottom_moves_the_card_up():
    lay = adslot.resolve({"main": {"pieces": []}, "top": dict(TOP), "banner": {"slot": "below"},
                          "adbar": {"height": 300}}, CARD)
    assert lay["slot"] == "filler" and lay["card"][1] + lay["card"][3] <= lay["top"][3]
    assert any("bottom is busy" in n for n in lay["notes"])


@pytest.mark.parametrize("shape", ["round", "circle", "rect"])
def test_center_layout_inset_and_card_do_not_touch(shape):
    lay = adslot.resolve({"layout": "center", "main": {"pieces": [], "shape": shape}, "banner": {}}, CARD)
    mx, my, mw, mh = lay["main"]
    assert lay["layout"] == "center" and lay["shape"] == shape and lay["fill"] == [[0, 0, 1080, 1920]]
    assert not adslot.overlap(lay["card"], lay["main"]) and mx > 0 and mx + mw < 1080
    assert lay["card"][1] + lay["card"][3] <= adslot.visible_bottom(lay)
    assert not lay["dead"] and adslot.check(lay) == []


def test_center_with_top_panel():
    lay = adslot.resolve({"layout": "center", "main": {"pieces": []}, "top": dict(TOP), "banner": {}}, CARD)
    assert lay["top"][3] == 400 and lay["main"][1] >= 400 and not lay["dead"]


def test_dead_zone_is_a_problem():
    lay = adslot.resolve({"layout": "center", "main": {"pieces": [], "aspect": "16:9"}, "banner": {}}, CARD)
    assert lay["dead"] and any("dead zone" in p for p in adslot.check(lay))
    old = {"top": [0, 0, 1080, 328], "main": [0, 328, 1080, 560], "bar": None, "card": [112, 912, 760, 320],
           "safe": adslot.resolve({"main": {"pieces": []}}, None)["safe"], "layout": "stack"}
    old["dead"] = [z for z in adslot.dead_zones(old) if z[1] - z[0] > adslot.DEAD_MAX]
    assert old["dead"] == [[1232, 1440]]                               # the 2.2 layout on an organic screen


def _make_src(path: Path, color=(40, 120, 200)):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=3",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(path)], check=True)


def test_center_layout_renders_inset_over_blur(tmp_path):
    _make_src(tmp_path / "main.mp4")
    spec = {"out": str(tmp_path / "c.mp4"), "fps": 25, "layout": "center",
            "main": {"pieces": [{"src": "main.mp4", "start": 0.0, "end": 2.0}], "snap": "off", "shape": "round", "track": "center"},
            "banner": {"brand": "Test", "url": "t.me/test_bot", "qr_url": "https://t.me/test_bot", "start": 0.2,
                       "slides": [{"title": "Тест", "sub": "проверка"}]}}
    res = S.render_stack(spec, tmp_path, check=False)
    lay = res["layout"]
    mx, my, mw, mh = lay["main"]
    cap = cv2.VideoCapture(res["out"])
    cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
    ok, fr = cap.read()
    assert ok
    inner = fr[my + mh // 2 - 40:my + mh // 2 + 40, mx + mw // 2 - 40:mx + mw // 2 + 40]
    outer = fr[my + mh // 2 - 40:my + mh // 2 + 40, 2:20]                 # left margin: blurred background
    sharp = cv2.Laplacian(cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    soft = cv2.Laplacian(cv2.cvtColor(outer, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    assert sharp > 5 * max(soft, 1.0)
    corner = fr[my + 3, mx + 3].astype(int)                               # rounded corner: background shows through
    centre = fr[my + mh // 2, mx + mw // 2].astype(int)
    assert lay["slot"] == "below" and res["ad"]["problems"] == []
    assert corner.sum() < 600 or abs(corner - centre).sum() > 30


def test_custom_safe_numbers_move_the_card_and_grow_the_main_picture():
    base = {"main": {"pieces": [{"src": "a.mp4", "start": 0, "end": 5}]}, "top": dict(TOP)}
    org = adslot.resolve(dict(base), CARD)
    low = adslot.resolve(dict(base, safe={"bottom": 380}), CARD)
    assert low["safe"]["name"] == "custom" and low["card"][1] > org["card"][1]
    assert low["card"][1] + low["card"][3] <= 1920 - 380
    assert low["main"][3] > org["main"][3] and not low["dead"]
    clamp = adslot.profile({"safe": {"bottom": 5}})
    assert clamp["bottom"] == 240                                 # never under the absolute minimum tray
