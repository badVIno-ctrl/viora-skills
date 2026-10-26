"""Contract with Viora Studio (docs/render-output.md): aliases, avoid, CTA times, label plate 7:1, palette, qa.json."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from shortskit import contract as K
from shortskit import plan as P
from shortskit.config import skill_root
from shortskit.engine import brand as B
from shortskit.engine import graphics as G
from shortskit.engine import layout as L
from shortskit.qa.gate import Check, check_row
from shortskit.util import contrast

ROOT = skill_root()


def _plan(**over) -> dict:
    p = json.loads((ROOT / "schema" / "plan.example.json").read_text(encoding="utf-8"))
    p.update(over)
    return p


# ---------------------------------------------------------------- schema 1.1 fields

def test_schema_accepts_new_optional_fields():
    p = _plan(schema_version="1.1")
    sid = p["scenes"][0]["id"]
    p["scenes"][0]["duration_hint"] = 6
    p["scenes"][0]["avoid"] = ["click:3d model"]
    p["brand"]["register"] = "punch"
    p["layout"]["cta_in_center"] = [{"kind": "text", "text": "ok", "anchor": {"scene": sid, "offset": -2}},
                                    {"kind": "qr", "url": "https://example.com", "t_pct": 0.8}]
    assert not P.validate_schema(p)


def test_schema_v1_plan_still_valid():
    assert not P.validate_schema(_plan())


def test_schema_bad_cases():
    p = _plan()
    p["layout"]["cta_in_center"] = [{"kind": "text", "text": "no time"}]          # no t, anchor or t_pct
    assert P.validate_schema(p)
    p["layout"]["cta_in_center"] = [{"kind": "text", "text": "x", "t_pct": 1.5}]  # outside 0-1
    assert P.validate_schema(p)
    p = _plan()
    p["brand"]["register"] = "loud"
    assert P.validate_schema(p)


def test_lint_anchor_to_unknown_scene_is_error():
    p = _plan()
    p["layout"]["cta_in_center"] = [{"kind": "text", "text": "x", "anchor": {"scene": "nope"}}]
    assert any(i.code == "cta_anchor" and i.level == "error" for i in P.lint(p, ROOT / "schema"))


def test_lint_duration_hint_counts_as_duration():
    p = _plan()
    s = next(s for s in p["scenes"] if s["source"]["type"] == "site")
    s.pop("say", None)
    s.pop("duration", None)
    assert any(i.code == "duration" for i in P.lint(p, ROOT / "schema"))      # bad: no say, no length
    s["duration_hint"] = 5
    assert not any(i.code == "duration" for i in P.lint(p, ROOT / "schema"))


def test_aliases_x_fields():
    p = _plan()
    p["scenes"][0]["x_duration_hint"] = 7
    p["scenes"][0]["x_avoid"] = ["click"]
    p["x_viora"] = {"register": "minimal"}
    q, notes = K.normalize(p)
    assert q["scenes"][0]["duration_hint"] == 7 and q["scenes"][0]["avoid"] == ["click"]
    assert q["brand"]["register"] == "minimal" and len(notes) == 3
    assert "duration_hint" not in p["scenes"][0]  # the input is not changed
    p["scenes"][0]["duration_hint"] = 3            # the official field wins
    assert K.normalize(p)[0]["scenes"][0]["duration_hint"] == 3


# ---------------------------------------------------------------- avoid

def test_avoid_skips_matching_actions_only():
    acts = [{"do": "goto"}, {"do": "click", "text": "3D model"}, {"do": "click", "text": "Search"}, {"do": "scroll"}]
    kept, notes = K.apply_avoid(acts, ["click:3d model", "the page is slow at night"])
    assert [a.get("text") for a in kept if a["do"] == "click"] == ["Search"]
    assert len(kept) == 3
    assert any("skipped" in n for n in notes) and any("note only" in n for n in notes)


def test_avoid_free_text_skips_nothing():
    acts = [{"do": "goto"}, {"do": "click", "text": "3D model"}]
    kept, _ = K.apply_avoid(acts, ["click on a 3D model crashes the page"])  # not a rule: 'click on a 3D model' is no action
    assert kept == acts


# ---------------------------------------------------------------- CTA times

SCENES = [("a", 0.0, 5.0), ("b", 5.0, 6.0), ("c", 11.0, 4.0)]  # total 15 s


def test_cta_anchor_and_pct():
    rows = K.schedule_ctas([{"kind": "text", "anchor": {"scene": "b", "offset": 1}, "duration": 2},
                            {"kind": "qr", "anchor": {"scene": "c", "offset": -3}, "duration": 3},
                            {"kind": "handle", "t_pct": 0.0, "duration": 2}], SCENES, 15.0)
    assert [r["final"] for r in rows] == [6.0, 12.0, 0.0]
    assert all(r["reason"] == "as requested" for r in rows)


def test_cta_overlap_moved_later_with_gap():
    # bad case from 1.0.0: two flashes at the same second were drawn on top of each other
    rows = K.schedule_ctas([{"kind": "handle", "t": 4, "duration": 2.5}, {"kind": "qr", "t": 5, "duration": 3}],
                           SCENES, 15.0)
    a, b = rows
    assert a["final"] == 4 and b["final"] == pytest.approx(4 + 2.5 + K.CTA_GAP)
    assert "later" in b["reason"]
    assert b["final"] >= a["final"] + a["duration"] + K.CTA_GAP - 1e-9


def test_cta_past_end_clamped_and_overlap_moved_earlier():
    rows = K.schedule_ctas([{"kind": "handle", "t": 12.5, "duration": 2.5}, {"kind": "qr", "t": 14, "duration": 3}],
                           SCENES, 15.0)
    a, b = rows
    assert b["final"] == 12.0 and "clamped" in b["reason"]           # 14+3 > 15: the QR stays last, at the end
    assert a["final"] + a["duration"] + K.CTA_GAP <= b["final"] + 1e-9
    assert "earlier" in a["reason"]


def test_cta_no_room_is_dropped_with_reason():
    rows = K.schedule_ctas([{"kind": "text", "t": 0, "duration": 2}, {"kind": "text", "t": 0, "duration": 2},
                            {"kind": "text", "t": 0, "duration": 2}], [("a", 0, 4.0)], 4.0)
    assert sum(r["dropped"] for r in rows) >= 1
    assert any("shortened" in r["reason"] for r in rows if not r["dropped"])
    assert all(r["reason"] for r in rows)
    kept = sorted((r["final"], r["final"] + r["duration"]) for r in rows if not r["dropped"])
    assert all(b0 >= a1 for (_, a1), (b0, _) in zip(kept, kept[1:]))


def test_cta_missing_anchor_falls_back():
    rows = K.schedule_ctas([{"kind": "text", "t": 3, "anchor": {"scene": "gone"}, "duration": 2}], SCENES, 15.0)
    assert rows[0]["final"] == 3 and "not found" in rows[0]["how"]


# ---------------------------------------------------------------- label plate 7:1, palette

def _label(accent: str, style: str | None = None):
    pb = {"preset": "viora", "palette": {"accent": accent}}
    if style:
        pb["label_style"] = style
    br = B.resolve(pb, None, "ru")
    return G.label("ПРОВЕРКА", br, L.compute({"mode": "three"}, ["youtube_shorts"]))


def test_label_plate_lifted_to_7_to_1():
    # bad case from 1.0.0: #E63946 plate with black text was 5.0:1 and QA failed contrast
    assert contrast("#E63946", "#000000") < 7
    spr = _label("#E63946")
    txt, plate, need = spr.pairs[0]
    assert contrast(txt, plate) >= need == 7.0
    assert plate.upper() != "#E63946" and "#E63946" in spr.note and "outline" in spr.note
    px = spr.img.getpixel((4, 4))[:3]
    assert "#%02X%02X%02X" % px == plate.upper()  # the drawn plate is the reported colour


def test_label_plate_strong_accent_untouched():
    spr = _label("#FFD400")  # yellow: 7:1+ with black already
    assert spr.pairs[0][1] == "#FFD400" and spr.note == ""


def test_plate_colors_keeps_hue_close():
    txt, plate = G.plate_colors("#E63946", "#000000", "#F5F5F5")
    r, g, b = int(plate[1:3], 16), int(plate[3:5], 16), int(plate[5:7], 16)
    assert r > g and r > b  # still red


def test_register_sets_label_style_and_cover():
    br = B.resolve({"preset": "viora", "register": "minimal"}, None, "ru")
    assert br.label_style == "outline" and B.REGISTER_COVER["minimal"] == "A"
    br = B.resolve({"preset": "viora", "register": "minimal", "label_style": "plate"}, None, "ru")
    assert br.label_style == "plate"  # explicit label_style wins
    assert B.resolve({"preset": "viora", "register": "punch"}, None, "ru").label_style == "plate"


def test_viora_accent_single_source():
    eng = json.loads((ROOT / "assets" / "brand" / "viora.json").read_text(encoding="utf-8"))
    assert eng["palette"]["accent"].upper() == "#E63946"
    spec = ROOT.parents[1] / "viora-v8" / "spec" / "plan.example.json"
    if not spec.exists():
        pytest.skip("viora-v8 is not next to the skill")
    v = json.loads(spec.read_text(encoding="utf-8"))
    assert v["brand"]["palette"]["accent"].upper() == eng["palette"]["accent"].upper()


# ---------------------------------------------------------------- render output

def test_qa_rows_have_ok_and_status_and_not_checked():
    rows = []
    for cid, st in (("format", "pass"), ("qr", "fail"), ("captions", "warn"), ("eyes", "manual"), ("loop", "skip")):
        c = Check(cid, 0, cid)
        c.status = st
        rows.append(check_row(c))
    assert [(r["status"], r["ok"]) for r in rows] == [("pass", True), ("fail", False), ("warn", True),
                                                      ("manual", True), ("pass", True)]
    ex = K.qa_extras(rows)
    assert ex["not_checked"] == ["eyes"]
    assert ex["aliases"]["qr_decode"] == ["qr"] and ex["aliases"]["duration"] == ["format"]
    assert ex["aliases"]["first"] == []  # only ids that exist in this report


def test_words_json_format(tmp_path):
    m = {"captions": {"words_spoken": [{"w": "Привет", "s": 0.1, "e": 0.5, "scene": "a"}]}, "duration": 3.0,
         "video": "x.mp4", "fps": 30, "engine": "shorts", "version": "1.1.0", "cta_schedule": []}
    K.write_render_output(tmp_path, m, "1.1")
    assert json.loads((tmp_path / "words.json").read_text(encoding="utf-8")) == [{"word": "Привет", "start": 0.1, "end": 0.5}]
    r = json.loads((tmp_path / "result.json").read_text())
    assert r["duration"] == 3.0 and r["schema_version"] == "1.1" and r["engine_version"] == "1.1.0"
