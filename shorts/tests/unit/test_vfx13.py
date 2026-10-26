"""1.3 pieces without a full render: effects math, plates, kinetic captions, lint rules, QA helpers, bg library."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

import numpy as np
import pytest

from shortskit import bglib as BG
from shortskit import contract as K
from shortskit import plan as P
from shortskit.engine import brand as B
from shortskit.engine import captions as C
from shortskit.engine import cards as CD
from shortskit.engine import kinetic as KN
from shortskit.engine import layout as L
from shortskit.engine import vfx as VX
from shortskit.engine.render import Overlay, fit_band, lift_chunks, plate_overlays
from shortskit.qa import frames as F
from shortskit.qa import gate as QG

BR = B.resolve({"preset": "viora"})


# ---------------------------------------------------------------- time keys

def test_resolve_t_forms():
    assert VX.resolve_t(2.5, 10, None) == 2.5
    assert VX.resolve_t(-1.5, 10, None) == 8.5
    assert VX.resolve_t("drop", 10, 3.2) == 3.2
    assert VX.resolve_t("drop", 10, None) is None
    assert VX.resolve_t("end", 10, None) == 10
    assert VX.resolve_t("50%", 10, None) == 5
    assert VX.resolve_t(99, 10, None) == 10


# ---------------------------------------------------------------- letterbox

def test_letterbox_cinema_slit_opens_on_drop_and_never_paints_input():
    lb = VX.Letterbox([{"t": 0, "ratio": 2.39}, {"t": "drop", "ratio": "full", "dur": 0.5}], 1080, 1920, 10, 2.0, 30)
    assert abs(lb.at(0.0) - (1920 - 1080 / 2.39) / 2) <= 1
    assert lb.at(1.9) == lb.at(0.0)
    assert 0 < lb.at(2.2) < lb.at(0.0)
    assert lb.at(2.6) == 0
    img = np.full((1920, 1080, 3), 200, np.uint8)
    out = lb.apply(img, 0.0)
    assert out[10].max() == 0 and out[960].min() == 200 and img.min() == 200  # the input frame is untouched
    rep = lb.report(10)
    assert rep["closed"][0][0] == 0.0 and 1.9 < rep["closed_at_start_s"] < 2.6


def test_letterbox_kick_returns():
    lb = VX.Letterbox({"keys": [{"t": 0, "ratio": "full"}], "hits": [1.0], "pulse": 60}, 1080, 1920, 5, None, 30)
    assert lb.at(1.0) >= 55 and lb.at(1.2) == 0


# ---------------------------------------------------------------- flicker (WCAG 2.3.1)

def test_flicker_patterns_respect_three_flashes():
    assert VX.pattern_flashes("exposure", "101101") == 3
    fl = VX.Flicker([{"t": 1.0, "kind": "black", "pattern": "10101010"}], 10, None, 30, [])
    assert VX.pattern_flashes("black", fl.events[0].pattern) <= VX.FLASH_LIMIT
    two = VX.Flicker([{"t": 1.0}, {"t": 1.5}, {"t": 3.0}], 10, None, 30, [])
    assert len(two.events) == 2 and any("dropped" in n for n in two.notes)
    many = VX.Flicker([{"t": float(t)} for t in range(1, 20, 2)], 30, None, 30, [])
    assert len(many.events) == VX.FLICKER_MAX_SERIES


def test_flash_transitions_zigzag():
    assert F.transitions([0.1, 0.1, 0.9, 0.9, 0.1, 0.1]) == [2, 4]
    assert len(F.transitions([0.1, 0.9] * 5)) == 9
    assert F.transitions([0.85, 0.95, 0.85, 0.95]) == []      # darker state above 0.8: not a flash
    assert F.transitions([0.30, 0.33, 0.31, 0.34]) == []      # small changes


def _strobe(path, seconds=2.0, every=1):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s=72x128:r=30:d={seconds}",
                    "-vf", f"geq=lum='if(mod(floor(N/{every}),2),235,16)':cb=128:cr=128", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_flash_report_catches_strobe_and_passes_slow_blink(tmp_path):
    fast = F.flash_report(_strobe(tmp_path / "fast.mp4", every=2))      # 7.5 flashes per second
    assert fast["max_flashes"] > F.FLASH_MAX and fast["windows_over"] > 0
    slow = F.flash_report(_strobe(tmp_path / "slow.mp4", every=15))     # 1 flash per second
    assert slow["max_flashes"] <= F.FLASH_MAX


# ---------------------------------------------------------------- colour switch

def test_look_keys_bw_then_colour_wipe():
    lk = VX.LookKeys([{"t": 0, "look": "bw"}, {"t": 2.0, "look": "base", "trans": "wipe", "dur": 0.6}], 10, None)
    assert lk.changes() == 1
    img = np.zeros((64, 36, 3), np.uint8)
    img[..., 0] = 220
    g = lk.apply(img, 0.5)
    assert np.abs(g[..., 0].astype(int) - g[..., 1].astype(int)).max() <= 2   # grey
    c = lk.apply(img, 3.0)
    assert c[..., 0].mean() > 150 and c[..., 1].mean() < 60                   # colour is back


# ---------------------------------------------------------------- transitions

@dataclass
class _S:
    id: str
    start: float
    length: float
    data: dict = field(default_factory=dict)


def _scenes(n, length=2.0, trans=None):
    out = []
    for i in range(n):
        d = {"trans": trans} if (trans and i == 1) else {}
        out.append(_S(f"s{i}", i * length, length, d))
    return out


def test_explicit_and_auto_transitions():
    tr, notes = VX.plan_transitions(_scenes(3, trans="whip"), {}, None)
    assert [(t.kind, t.scene, t.b) for t in tr] == [("whip", 1, 2.0)] and not notes
    tr, _ = VX.plan_transitions(_scenes(11), {"transitions": {"auto": "facts", "share": 0.2}}, None)
    assert 1 <= len(tr) <= 3 and all(t.scene > 0 for t in tr) and all(t.how == "auto" for t in tr)
    scenes = [t.scene for t in tr]
    assert all(b - a >= 3 for a, b in zip(scenes, scenes[1:]))     # heavy moves never on joins in a row


def test_long_transition_is_shortened_for_short_shots():
    sc = [_S("a", 0, 0.4), _S("b", 0.4, 0.4, {"trans": {"kind": "dissolve", "dur": 0.6}})]
    tr, notes = VX.plan_transitions(sc, {}, None)
    assert tr[0].dur < 0.4 and any("too long" in n for n in notes)


@pytest.mark.parametrize("kind", [k for k in VX.TRANS_DUR if k != "cut"])
def test_every_transition_keeps_frame_shape(kind):
    tr = VX.Trans(1.0, kind, VX.TRANS_DUR[kind], "left", 1)
    a = np.full((96, 54, 3), 40, np.uint8)
    b = np.full((96, 54, 3), 210, np.uint8)
    for t in (tr.t0 + 0.01, tr.b - 0.01, tr.b + 0.01, tr.t1 - 0.01):
        img = a if t < tr.b else b
        out = VX.apply_transition(tr, t, img, a, b, int(t * 30))
        assert out.shape == img.shape and out.dtype == np.uint8


# ---------------------------------------------------------------- split screen

def _win(mode, ratio, a_pos):
    return VX.SplitWin(0, 10, mode, ratio, 8, "slide", a_pos, (0.5, 0.42), (0.5, 0.5), 0.12, "bl", "", 0.0, full=True)


def test_split_geometry_fills_the_centre():
    a, b = _win("v2", 0.64, "bottom").geometry(1080, 1920)
    assert a[1] + a[3] == 1920 and b[1] == 0 and b[3] + 8 + a[3] == 1920 and a[3] % 8 == 0
    a, b = _win("h2", 0.5, "left").geometry(1080, 1920)
    assert a[0] == 0 and b[0] == a[2] + 8 and a[2] + 8 + b[2] == 1080
    a, b = _win("pip", 0.0, "top").geometry(1080, 1920)
    assert a == (0, 0, 1080, 1920) and b[2] < 1080 / 2 and b[3] > b[2]


# ---------------------------------------------------------------- overlay motion

def _ov(anim, **kw):
    spr = CD.fact("Факт: 1 млрд", BR, L.compute({"mode": "center_only"}, ["youtube_shorts"]))
    return Overlay(spr, 1.0, 4.0, anim=anim, **kw)


def test_overlay_animations_settle():
    o = _ov("slide_left")
    a, s, dx, dy, rev = o.full(1.01)
    assert dx < -100 and a == 1.0
    assert o.full(2.0) == (1.0, 1.0, 0.0, 0.0, 1.0)
    pb = _ov("pop_back")
    assert pb.full(1.01)[1] < 0.7 and abs(pb.full(1.5)[1] - 1.0) < 1e-6
    ty = _ov("type")
    assert ty.full(1.05)[4] < 0.5 and ty.full(3.0)[4] == 1.0
    assert _ov("none").full(0.5)[0] == 0.0       # outside its time: hidden


# ---------------------------------------------------------------- plates

def test_title_bar_fits_the_band_field():
    lay = L.compute({"mode": "band"}, ["youtube_shorts"])
    top, max_h = lay.safe.rect.y + 8, lay.center.y - 12 - (lay.safe.rect.y + 8)
    spr = CD.title_bar("ЦЕНА ПРИЗНАНИЯ", BR, lay, "", "plate", top, max_h)
    assert spr.box.y >= lay.safe.rect.y and spr.box.y1 <= lay.center.y and spr.min_font >= 56 and not spr.note
    long = CD.title_bar("ОЧЕНЬ ДЛИННЫЙ ЗАГОЛОВОК ДЛЯ ПЛАШКИ ТЕМЫ", BR, lay, "", "plate", top, max_h)
    assert "chars" in long.note and "overlaps" in long.note     # told to shorten; fit_band would move the band
    # a sub line does not fit the default 144 px field: the band moves down (no band_y in the plan)
    plan = {"layout": {"mode": "band", "title_bar": {"text": "ЦЕНА ПРИЗНАНИЯ", "sub": "Джокер (2019)"}}}
    lay2, note = fit_band(plan, lay, BR, ["youtube_shorts"])
    spr2 = CD.title_bar("ЦЕНА ПРИЗНАНИЯ", BR, lay2, "Джокер (2019)", "plate", top, lay2.center.y - 12 - top)
    assert note and lay2.center.y > lay.center.y and lay2.center.h == lay.center.h
    assert spr2.box.y1 <= lay2.center.y and lay2.center.y1 <= 1920 and not spr2.note
    fixed = {"layout": {"mode": "band", "band_y": 432, "title_bar": {"text": "ТЕМА", "sub": "x"}}}
    assert fit_band(fixed, lay, BR, ["youtube_shorts"])[1] is None             # the plan's band_y wins


def test_fact_and_arrow_inside_safe_zone_on_baseline():
    lay = L.compute({"mode": "center_only"}, ["youtube_shorts", "tiktok"])
    f = CD.fact("Ограбление века: 1 млрд", BR, lay, "Москва, 1993")
    assert lay.safe.allows(f.box, tol=4) and f.box.y1 == lay.safe.rect.y1 - 8
    ar = CD.arrow(BR, lay, None, "ru")
    assert lay.safe.allows(ar.box, tol=4) and ar.text


def test_subscribe_card_readable_and_centred():
    lay = L.compute({"mode": "three"}, ["youtube_shorts"])
    spr, after, btn = CD.subscribe("@viora", BR, lay, "ru")
    assert spr.min_font >= 40 and lay.safe.allows(spr.box, tol=4)
    assert spr.box.contains(btn) if hasattr(spr.box, "contains") else spr.box.intersects(btn)
    assert abs((spr.box.x + spr.box.w / 2) - 540) <= 1 and after.size == spr.img.size


def test_plate_overlays_from_plan_and_drop_without_drop_at():
    plan = {"layout": {"mode": "band", "title_bar": {"text": "ТЕМА", "from": "drop"}},
            "overlays": {"facts": [{"t": 1.0, "text": "один два три четыре"}], "arrow": True}}
    lay = L.compute({"mode": "band"}, ["youtube_shorts"])
    ovs, sfx, notes = plate_overlays(plan, lay, BR, 10.0, None, "ru", True)
    kinds = [o.sprite.kind for o in ovs]
    assert "title_bar" not in kinds and any("drop" in n for n in notes)       # 'drop' without drop_at is skipped
    fact = next(o for o in ovs if o.sprite.kind == "fact")
    assert fact.t1 - fact.t0 >= 3.0 and sfx and sfx[0][1] == "whoosh"         # 4 words -> 2 x 1.5 s
    arrow = next(o for o in ovs if o.sprite.kind == "arrow")
    assert arrow.t1 == 10.0 and arrow.anim == "bob"


# ---------------------------------------------------------------- captions around obstacles

def _chunk(text, s, e, box):
    c = C.Chunk([{"w": w, "s": s, "e": e} for w in text.split()])
    c.box = list(box)
    return c


def test_lift_chunks_goes_to_the_nearest_free_row():
    lay = L.compute({"mode": "center_only"}, ["youtube_shorts"])
    cta = L.Rect(220, 864, 641, 197)          # centred card
    arrow = L.Rect(56, 1059, 382, 181)        # bottom left
    c = _chunk("Ссылка ниже.", 8.2, 8.9, [218, 1098, 862, 1222])
    notes = lift_chunks([c], [(6.2, 8.6, cta), (8.4, 10.4, arrow)], None, lay)
    box = L.Rect.from_xyxy(*c.box)
    assert not notes and not box.intersects(cta) and not box.intersects(arrow)
    assert lay.safe.rect.y <= c.box[1] and c.box[3] <= lay.safe.rect.y1


# ---------------------------------------------------------------- kinetic captions

WORDS = [("Ты", 0.0, 0.2), ("не", 0.22, 0.35), ("обязан", 0.4, 0.8), ("быть", 0.85, 1.0), ("идеальным.", 1.05, 1.7),
         ("Сделай", 2.1, 2.4), ("100", 2.45, 2.8), ("попыток", 2.85, 3.3), ("и", 3.35, 3.4), ("смотри.", 3.45, 4.0)]


def test_kinetic_blocks_obey_limits():
    lay = L.compute({"mode": "band"}, ["youtube_shorts"])
    words = [{"w": w, "s": s, "e": e, "scene": "a"} for w, s, e in WORDS]
    blocks = KN.build(words, BR, lay, {"style": "kinetic"}, "ru", [], 5.0)
    assert len(blocks) == 2
    for b in blocks:
        assert len(b.words) <= KN.MAX_WORDS_HARD and len(b.lines) <= 4
        assert (b.box[3] - b.box[1]) <= 0.45 * 1920 + 1
        for w in b.words:
            assert w.size >= KN.MIN_PX and lay.safe.allows(w.box, tol=4)
    kinds = {w.w: w.kind for b in blocks for w in b.words}
    assert kinds["100"] == "accent" and kinds["не"] != "stop" and kinds["и"] == "stop"
    rep = KN.report(blocks)
    assert rep["max_words"] <= 12 and rep["min_px"] >= 56


def test_kinetic_avoids_a_plate():
    lay = L.compute({"mode": "center_only"}, ["youtube_shorts"])
    plate = L.Rect(48, 1092, 826, 148)
    words = [{"w": w, "s": s, "e": e, "scene": "a"} for w, s, e in WORDS[:5]]
    blocks = KN.build(words, BR, lay, {"style": "kinetic"}, "ru", [(0.0, 5.0, plate)], 5.0)
    assert all(not w.box.intersects(plate) for b in blocks for w in b.words)


# ---------------------------------------------------------------- plan rules

def _plan(**over):
    p = {"schema_version": "1.3", "meta": {"name": "x", "language": "ru", "platforms": ["youtube_shorts"]},
         "layout": {"mode": "center_only"}, "brand": {"preset": "viora"}, "captions": {}, "audio": {},
         "scenes": [{"id": "a", "source": {"type": "text", "ref": "x"}}, {"id": "b", "source": {"type": "text", "ref": "y"}}]}
    p.update(over)
    return p


def _codes(issues, level=None):
    return {i.code for i in issues if level is None or i.level == level}


def test_lint_13_rules():
    assert "band" in _codes(P.lint_13(_plan(layout={"mode": "band"})), "error")
    assert "drop" in _codes(P.lint_13(_plan(fx={"look_keys": [{"t": "drop", "look": "bw"}]})), "error")
    bg = {"mode": "three", "top": {"source": "bg:gta_ramp"}}
    assert "author_layer" in _codes(P.lint_13(_plan(layout=bg)), "error")
    assert "author_layer" in _codes(P.lint_13(_plan(layout=bg, schema_version="1")), "warn")
    ok = P.lint_13(_plan(layout=bg, author_layer=[{"kind": "voice"}, {"kind": "thesis"}]))
    assert "author_layer" not in _codes(ok)


def test_author_layer_needs_a_core_kind(tmp_path):
    """Research 14.12 / 15.2: >= 2 own layers AND one of voice / thesis / own_footage / compare. Plates, sound and
    a quiz alone are not enough. validate counts like the render report (voice from say, text from on_screen_text)."""
    bg = {"mode": "three", "top": {"source": "bg:gta_ramp"}}
    weak = [{"kind": "text_point", "note": "plates"}, {"kind": "sound_design", "note": "whoosh"}]
    iss = [i for i in P.lint_13(_plan(layout=bg, author_layer=weak)) if i.code == "author_layer"]
    assert iss and iss[0].level == "error" and "now: sound_design, text_point" in iss[0].msg
    assert "author_layer" not in _codes(P.lint_13(_plan(layout=bg, author_layer=weak[1:] + [{"kind": "thesis"}])))
    talk = [{"id": "a", "say": "Своё мнение", "on_screen_text": "ТЕЗИС", "source": {"type": "text", "ref": "x"}}]
    assert "author_layer" not in _codes(P.lint_13(_plan(layout=bg, scenes=talk)))  # auto voice + text_point
    split = {"mode": "center_only", "split": [{"mode": "v2", "b": "media/clip.mp4"}]}
    assert "author_layer" in _codes(P.lint_13(_plan(layout=split)), "error")  # any second window is foreign
    own = [{"kind": "own_footage", "note": "my stream"}, {"kind": "voice", "note": "my voice in it"}]
    assert "author_layer" not in _codes(P.lint_13(_plan(layout=split, author_layer=own)))
    # QA: the manifest row from the render (core), strict from 1.3, old manifests (no "core") keep the count rule
    def row(schema, **al):
        m = {"schema_version": schema, "author_layer": {"foreign": ["top: gta_ramp"], "count": 2, "credits": [], **al}}
        return QG.author_check(m, tmp_path)
    assert row("1.3", core=[]).status == "fail"
    assert row("1.2", core=[]).status == "warn"
    assert row("1.3", core=["voice"]).status == "pass"
    assert row("1.3").status == "pass"
    assert row("1.3", count=1, core=["voice"]).status == "fail"
    sc = _plan()["scenes"]
    sc[0]["trans"] = "whip"
    assert "trans" in _codes(P.lint_13(_plan(scenes=sc)), "warn")
    many = {"letterbox": [{"t": 0, "ratio": 2.39}], "flicker": [{"t": 1}], "look_keys": [{"t": 0, "look": "bw"}]}
    assert "effects" in _codes(P.lint_13(_plan(fx=many)), "warn")
    assert "dash" in _codes(P.lint_13(_plan(layout={"mode": "band", "title_bar": {"text": "ЦЕНА \u2014 ПРИЗНАНИЯ"}})), "error")


def test_normalize_aliases_13():
    plan, notes = K.normalize({"edit": {"look_keys": [{"t": 0, "look": "bw"}]}, "layout": {"title": {"text": "ТЕМА"}}})
    assert plan["fx"]["look_keys"][0]["look"] == "bw" and plan["layout"]["title_bar"]["text"] == "ТЕМА" and notes


def test_example_schema_accepts_13_fields():
    p = _plan(layout={"mode": "band", "band_h": 1056, "title_bar": {"text": "ТЕМА", "style": "outline"},
                      "split": [{"mode": "v2", "b": "bg:auto", "ratio": 0.64, "a_pos": "bottom"}]},
              fx={"letterbox": [{"t": 0, "ratio": 2.39}], "transitions": {"auto": "facts"}},
              captions={"style": "kinetic", "kinetic": {"max_words": 8}}, audio={"export": "both"})
    assert not P.validate_schema(p)


# ---------------------------------------------------------------- QA helpers

def test_flat_on_purpose_rows_for_bars_and_band():
    m = {"layout": {"mode": "band", "center": {"y": 432, "h": 1056}},
         "vfx": {"letterbox": {"closed": [[0.0, 2.0]], "max_bar_px": 300}}}
    rows = QG._flat_on_purpose(m, 10.0)
    assert (0.0, 2.0, 432, 732) in rows and (0.0, 11.0, 0, 432) in rows and (0.0, 11.0, 1488, 1920) in rows


def test_dead_zones_ignore_rows():
    frames = np.full((8, 1920, 1080, 3), 12, np.uint8)
    frames[:, 600:1300] = np.random.default_rng(1).integers(0, 255, (8, 700, 1080, 3), dtype=np.uint8)
    times = [i * 0.5 for i in range(8)]
    full = F.dead_zones(frames, times, bg=(12, 12, 12))
    assert full["max_share"] > 0.15
    ign = F.dead_zones(frames, times, bg=(12, 12, 12), ignore=[(0, 9, 0, 600), (0, 9, 1300, 1920)])
    assert ign["max_share"] < 0.02


# ---------------------------------------------------------------- background library

def test_bg_library_choose_and_start():
    assert BG.start_for(75.0, 20.0) == 27.5 and BG.start_for(20.0, 19.0) == 0.0
    assert BG.choose("майнкрафт паркур")["id"].startswith("minecraft")
    assert BG.choose("машины и трюки в гта")["id"].startswith("gta")


def test_bg_resolve_offline_never_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("SHORTS_CACHE", str(tmp_path / "empty-cache"))
    monkeypatch.setattr(BG, "fetch", lambda key, force=False: (_ for _ in ()).throw(RuntimeError("blocked")))
    p, info = BG.resolve("bg:gta_ramp_2", "", 20)
    assert p is None and "bg fetch" in info["error"]
    p, info = BG.resolve("bg:no_such_thing", "", 20)
    assert p is None and "unknown" in info["error"]
    p, info = BG.resolve("bg:auto", "майнкрафт", 20)       # nothing cached in the test cache
    assert p is None and "error" in info


def test_bg_auto_falls_back_to_a_cached_item(monkeypatch, tmp_path):
    monkeypatch.setenv("SHORTS_CACHE", str(tmp_path / "cache"))
    src = tmp_path / "g.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)], check=True)
    BG.add("gta_ramp", src)                                  # library id, file from elsewhere (browser recording)
    monkeypatch.setattr(BG, "fetch", lambda key, force=False: (_ for _ in ()).throw(RuntimeError("blocked")))
    p, info = BG.resolve("bg:auto", "майнкрафт паркур", 2.0)   # wants minecraft, it is not cached
    assert p == BG.cache_path("gta_ramp") and "instead" in info["notes"][0]
    assert BG.item("gta_ramp")["credit"].startswith("Gameplay")  # library credit is kept for a library id


def test_bg_add_own_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_CACHE", str(tmp_path / "cache"))
    src = tmp_path / "mine.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)], check=True)
    meta = BG.add("my_run", src, credit="Gameplay: me")
    assert BG.cache_path("my_run").exists() and meta["credit"] == "Gameplay: me"
    it = BG.item("my_run")
    assert it and it.get("own") and it["credit"] == "Gameplay: me"
    p, info = BG.resolve("bg:my_run", "", 3.0)
    assert p == BG.cache_path("my_run") and info["credit"] == "Gameplay: me"
    assert any(r["id"] == "my_run" and r["cached"] for r in BG.describe())


def test_edit_cinema_preset_and_layers():
    """`edit --bars --bw-drop --layer` (research 14.4, 14.6, 15): keyed to the drop, 2 noticeable moves, layers."""
    from shortskit.engine import vfx as VX

    with pytest.raises(ValueError):
        VX.parse_layers(["template:velocity"])  # a template change is not an author layer
    lay = VX.parse_layers(["thesis:the idea", "sound_design: drop on the line end"])
    assert lay == [{"kind": "thesis", "note": "the idea"}, {"kind": "sound_design", "note": "drop on the line end"}]
    with pytest.raises(ValueError):
        VX.edit_cinema({"audio": {"music": {}}}, bars=True)  # no drop: nothing to open on
    plan = {"schema_version": "1.2", "edit": {"reframe": "face"}, "audio": {"music": {"drop_at": 4.2}}, "scenes": []}
    notes = VX.edit_cinema(plan, bars=True, bw=True)
    assert plan["schema_version"] == "1.3"
    lb = plan["fx"]["letterbox"]
    assert lb[0] == {"t": 0, "ratio": 2.39} and lb[1]["t"] == "drop" and lb[1]["ratio"] == "full" and lb[2]["t"] < 0
    lk = plan["fx"]["look_keys"]
    assert lk[0]["look"] == "bw" and lk[1]["t"] == "drop" and lk[1]["trans"] == "radial" and lk[1]["cy"] == 0.42
    assert any("hook > 3 s" in n for n in notes) and any("author layers" in n for n in notes)
    plan2 = {"audio": {"music": {"drop_at": 2.0}}, "scenes": []}
    assert VX.edit_cinema(plan2, bw=True, layers=lay) == []
    weak = VX.parse_layers(["text_point:plates", "sound_design:drop"])  # 2 layers, none of them core
    assert any("author layers" in n for n in VX.edit_cinema({"audio": {"music": {"drop_at": 2.0}}}, bw=True, layers=weak))
    assert plan2["fx"]["look_keys"][1]["trans"] == "wipe" and "letterbox" not in plan2["fx"]
    # the preset is valid 1.3 and counts as exactly 2 noticeable effects (no lint warning about templates)
    from shortskit import plan as P

    full = {"schema_version": "1.3", "meta": {"name": "x", "language": "ru"}, "layout": {"mode": "center_only"},
            "audio": {"music": {"source": "assets/audio/edit.mp3", "drop_at": 2.0}}, "author_layer": lay,
            "scenes": [{"id": "a", "why": "w", "duration": 3, "source": {"type": "text", "ref": "A"}}]}
    VX.edit_cinema(full, bars=True, bw=True)
    assert not [i for i in P.lint_13(full) if i.code in ("effects", "drop", "author_layer")]


def test_music_ducks_under_voice_after_the_drop(tmp_path):
    """1.3: effects keyed to 'drop' need audio.music.drop_at; a voice-over that goes on after the drop must stay on
    top (before 1.3 the music played at the voice level under it). Music = 1 kHz tone, voice = 300 Hz bursts."""
    import wave

    import numpy as np

    from shortskit.engine import audio as A

    sr = A.SR

    def wav(path, x):
        x = np.clip(x, -1, 1)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((x * 32767).astype("<i2").tobytes())
        return path

    t = np.arange(int(7 * sr)) / sr
    music = wav(tmp_path / "m.wav", 0.3 * np.sin(2 * np.pi * 1000 * t))
    tv = np.arange(int(1.2 * sr)) / sr
    voice = wav(tmp_path / "v.wav", 0.5 * np.sin(2 * np.pi * 300 * tv))
    words = [{"w": "раз", "s": 3.0, "e": 3.6}, {"w": "два", "s": 3.6, "e": 4.2}]
    rep = A.mix(6.0, [(3.0, voice)], [], words, {"drop_at": 1.0}, music, [], tmp_path / "out.wav", -14.0)
    assert rep.get("post_drop_duck_db") == -10.0
    y = A.load_audio(tmp_path / "out.wav", mono=True)

    def tone(a, b, f=1000):
        seg = y[int(a * sr):int(b * sr)]
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        k = int(round(f * len(seg) / sr))
        return 20 * np.log10(spec[k - 2:k + 3].max() + 1e-9)

    under, between, before = tone(3.2, 4.0), tone(1.6, 2.4), tone(0.3, 0.8)
    assert between - under >= 5.0          # the music ducks under the phrase after the drop
    assert between - before >= 8.0         # the drop still hits: quiet before it, loud after it
    assert A.post_drop_speech(words, 3.3) == [(3.3, 4.2)] and A.post_drop_speech(words, 5.0) == []


def test_edit_shot_offset_skips_black():
    """Found by the 1.3 edit test: a candidate window over a fade / black gap gave a black shot (QA edit_content fail).
    best_offset never starts a shot on mostly black samples, and the fallback prefers a lit camera shot."""
    from shortskit.adapters.edit2 import best_offset

    t = [i / 8 for i in range(40)]                      # 5 s sampled at 8 fps
    dark = [1.0 <= x < 2.6 for x in t]                  # black gap 1.0-2.6 s
    an = {"t": t, "face_h": [0.0] * 40, "motion": [0.0 if d else 3.0 for d in dark], "dark": dark,
          "segments": [(0.0, 1.0), (1.0, 2.6), (2.6, 5.0)]}
    o, q = best_offset(an, 1.2, 0.5, prefer=1.6)        # prefer points into the black gap
    assert 2.6 <= o <= 5.0 - 1.2 and q > 0
    # no lit segment long enough: the longest LIT one, not the black one
    an2 = dict(an, segments=[(0.0, 1.0), (1.0, 2.6), (2.6, 3.4)])
    o2, _ = best_offset(an2, 3.0, 0.5)
    assert not (1.0 <= o2 < 2.6)
    # old analyses without "dark" still work
    an3 = {k: v for k, v in an.items() if k != "dark"}
    assert best_offset(an3, 1.2, 0.5)[0] is not None


# ---------------------------------------------------------------- layout C: background scene + post card (9.2)

def _post_words(text, t=0.3, step=0.36):
    out = []
    for w in text.split():
        out.append({"w": w, "s": round(t, 3), "e": round(t + 0.3, 3)})
        t += step
    return out


def test_post_card_writes_itself_with_the_voice():
    """Research 14.9.2 / 17 (layout C): the card grows word by word and never before the sound, sits in the safe
    zone in the top third, text >= 40 px at 7:1, all states on one canvas (the box never jumps)."""
    from shortskit.util import contrast

    brand = B.resolve({"preset": "viora"}, None, "ru")
    lay = L.compute({"mode": "center_only"}, ["youtube_shorts"])
    ws = _post_words("Мой сосед три года парковался на моём месте. Вчера я узнал почему.")
    spr, states, rep = CD.post_card({"kind": "reddit", "name": "u/tired", "where": "r/AskReddit", "stats": "12,4k 873",
                                     "title": "Сосед и моё место"}, ws, 0.0, brand, lay)
    assert rep["states"] == len(ws) + 1 and [t for t, _ in states][1:] == [w["s"] for w in ws]
    assert len({im.size for _, im in states}) == 1 and spr.box.y == 300 and lay.safe.allows(spr.box)
    assert spr.box.h <= CD.POST_MAX_H and spr.min_font >= 40 and not rep["scrolled"]
    assert all(contrast(fg, bg) >= req for fg, bg, req in spr.pairs)
    area = [int((np.asarray(im)[..., 3] > 0).sum()) for _, im in states]
    assert area[-1] > area[0] and all(b >= a for a, b in zip(area, area[1:]))   # grows down, never shrinks
    # a long text scrolls (the last lines stay on the card), a fixed text is one state
    spr2, _, rep2 = CD.post_card({"kind": "telegram", "theme": "dark"}, _post_words("слово " * 120), 0.0, brand, lay)
    assert rep2["scrolled"] and "scrolls" in spr2.note and spr2.box.h <= CD.POST_MAX_H
    _, st3, rep3 = CD.post_card({"text": "Готовый текст поста"}, [], 1.0, brand, lay)
    assert len(st3) == 1 and st3[0][0] == 1.0 and not rep3["voice"]
    # under a top banner the card moves below it
    three = L.compute({"mode": "three"}, ["youtube_shorts"])
    assert CD.post_card({}, ws, 0.0, brand, three)[0].box.y >= three.center.y


def test_post_overlay_hides_captions_it_already_shows():
    from shortskit.engine.render import SceneT, post_overlays

    brand = B.resolve({"preset": "viora"}, None, "ru")
    lay = L.compute({"mode": "center_only"}, ["youtube_shorts"])
    a = SceneT({"id": "a", "source": {"type": "video", "ref": "bg:auto"}}, 0)
    b = SceneT({"id": "b", "source": {"type": "video", "ref": "bg:auto"}}, 1)
    a.start, a.length, b.start, b.length = 0.0, 4.0, 4.0, 3.0
    words = _post_words("один два три четыре пять", 0.2, 0.5) + _post_words("шесть семь", 4.3, 0.5)
    ovs, hide, notes, reps = post_overlays({"overlays": {"post": {"kind": "reddit"}}}, lay, brand, [a, b], words, 7.0, None)
    assert len(ovs) == 1 and hide == [(0.0, 4.0)] and reps[0]["max_early_s"] == 0.0
    o = ovs[0]
    assert o.t0 == 0.0 and o.t1 == 4.0 and len(o.steps) == 6
    assert o.image_at(0.0) is not o.image_at(2.3)               # a new state after a new word
    assert o.image_at(0.21).shape == o.image_at(3.9).shape
    _, hide2, _, _ = post_overlays({"overlays": {"post": {"scene": "b", "captions": True}}}, lay, brand, [a, b], words, 7.0, None)
    assert hide2 == []
    _, _, notes3, reps3 = post_overlays({"overlays": {"post": {"scene": "zzz"}}}, lay, brand, [a, b], words, 7.0, None)
    assert not reps3 and "not in the video" in notes3[0]


def test_frame_window_finds_the_motion_for_a_tall_crop(tmp_path):
    """A 9:16 frame from 16:9 gameplay: the code picks the horizontal crop where things move (same QA metric)."""
    src = tmp_path / "right.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=640x360:r=30:d=6",
                    "-f", "lavfi", "-i", "testsrc2=s=160x360:r=30:d=6", "-filter_complex",
                    "[1]scroll=horizontal=0.01:vertical=0.004[m];[0][m]overlay=x=480:y=0,format=yuv420p",
                    "-c:v", "libx264", str(src)], check=True)
    win = BG.frame_window(src, 4.0, 1080, 1920)
    assert win["focus_x"] >= 0.75 and win["focus_y"] == 0.5
    wide = BG.frame_window(src, 4.0, 1080, 400)
    assert wide["focus_x"] == 0.5


def test_background_scene_and_post_rules():
    bgs = [{"id": "a", "say": "Текст поста", "source": {"type": "video", "ref": "bg:gta_ramp"}}]
    base = _plan(scenes=bgs, author_layer=[{"kind": "voice"}, {"kind": "thesis"}])
    assert not [i for i in P.check(base) if i.code in ("media_missing", "scene_bg")]
    bad = _plan(scenes=[{"id": "a", "source": {"type": "video", "ref": "bg:nope"}}])
    assert {"scene_bg"} <= _codes(P.check(bad), "error")
    assert "author_layer" in _codes(P.lint_13(_plan(scenes=[{"id": "a", "duration": 3, "source": {"type": "video", "ref": "bg:auto"}}])), "error")
    ok = _plan(scenes=bgs, overlays={"post": {"kind": "reddit", "title": "Вопрос"}}, author_layer=[{"kind": "thesis"}])
    assert "post" not in _codes(P.lint_13(ok))
    assert "post" in _codes(P.lint_13(_plan(scenes=bgs, overlays={"post": {"scene": "x"}})), "error")
    silent = [{"id": "a", "duration": 3, "source": {"type": "video", "ref": "bg:auto"}}]
    assert "post" in _codes(P.lint_13(_plan(scenes=silent, overlays={"post": {}})), "error")
    assert "post" not in _codes(P.lint_13(_plan(scenes=silent, overlays={"post": {"text": "Пост"}})))
    assert "dash" in _codes(P.lint_13(_plan(scenes=bgs, overlays={"post": {"title": "Да \u2014 нет"}})), "error")
