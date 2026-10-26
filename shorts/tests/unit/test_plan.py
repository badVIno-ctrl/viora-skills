import copy
import json

from shortskit import plan as P
from shortskit.config import skill_root

from conftest import FIX, mini_plan


def codes(plan, d=None):
    return {i.code for i in P.check(plan, d)}


def test_example_and_offline_plans_are_valid():
    ex = json.loads((skill_root() / "schema" / "plan.example.json").read_text())
    assert not P.validate_schema(ex)
    off = json.loads((FIX / "plan.offline.json").read_text())
    assert not P.errors(P.check(off, FIX))


def test_original_contract_example_still_validates():
    """Viora Studio writes plans against viora-v8/spec: schema v1 must stay backward compatible."""
    p = skill_root().parent.parent / "viora-v8" / "spec" / "plan.example.json"
    if p.exists():
        assert not P.validate_schema(json.loads(p.read_text()))


def test_schema_rejects_wide_panels():
    p = mini_plan(layout={"mode": "three", "top": {"height_pct": 30, "source": "x.mp4"}})
    assert "schema" in codes(p)


def test_lint_rules():
    base = mini_plan()
    assert not P.errors(P.check(base, FIX))
    p = copy.deepcopy(base)
    p["scenes"][0]["say"] = "Привет, в этом видео покажу сайт"
    assert "hook" in codes(p, FIX)
    p = copy.deepcopy(base)
    p["scenes"][0]["say"] = "Вот и всё, всем пока!"
    assert "loop" in codes(p, FIX)
    p = copy.deepcopy(base)
    p["scenes"][0]["on_screen_text"] = "САЙТ \u2014 ТОП"
    assert "dash" in codes(p, FIX)
    p = copy.deepcopy(base)
    p["scenes"][0]["on_screen_text"] = "ТОП \U0001F525"
    assert "emoji" in codes(p, FIX)
    p = copy.deepcopy(base)
    p["brand"]["effects"] = {"text_glow": True}
    assert "slop" in codes(p, FIX)
    p = copy.deepcopy(base)
    p["layout"] = {"mode": "three", "top": {"source": "loop:auto"}, "bottom": {}}
    assert "empty_bottom" in codes(p, FIX)
    p = copy.deepcopy(base)
    p["layout"] = {"mode": "top_center"}
    assert "empty_top" in codes(p, FIX)
    p = copy.deepcopy(base)
    p["layout"]["cta_in_center"] = [{"t": 1, "kind": "qr"}]
    assert "cta_qr" in codes(p, FIX)


def test_defaults():
    d = P.with_defaults(mini_plan())
    assert d["captions"]["enabled"] is True and d["audio"]["target_lufs"] == -14 and d["meta"]["fps"] == 30
