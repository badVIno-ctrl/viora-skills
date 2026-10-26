"""2.0: animation episodes: init skeleton, scenario picker, offline anim-check."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from shortskit import anim as A
from shortskit.util import ShortsError

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "templates" / "animation" / "example-blackout"


@pytest.fixture
def ep(tmp_path):
    d = tmp_path / "ep"
    shutil.copytree(EXAMPLE, d)
    return d


def check(d, **kw):
    return A.check_episode(d, **kw)


def edit_shotlist(d, fn):
    p = d / "shotlist.md"
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(fn(lines)) + "\n", encoding="utf-8")


def set_cell(line, idx, value):
    cells = line.split("|")
    cells[idx + 1] = f" {value} "
    return "|".join(cells)


def rows(lines):
    return [i for i, ln in enumerate(lines) if ln.startswith("| ") and ln[2].isdigit()]


def has(rep, key, kind="errors"):
    return any(key in m for m in rep[kind])


# ------------------------------------------------------------------ good

def test_example_episode_passes(ep):
    rep = check(ep)
    assert rep["ok"], rep["errors"]
    assert rep["warnings"] == []
    st = rep["stats"]
    assert 2.4 <= st["words_per_s"] <= 2.7
    assert len(st["schemes"]) >= 3 and st["share_3d"] <= 0.25 and st["longest_scene_s"] <= 3.0


def test_script_stage_ignores_shotlist_and_words(ep):
    (ep / "shotlist.md").unlink()
    (ep / "words.json").unlink()
    assert check(ep, stage="script")["ok"]
    assert not check(ep)["ok"]


def test_spoken_words_skips_headings_tables_directions_comments():
    t = "# Заголовок\n<!-- один два\nтри -->\n[ДЕНЬ 1 - 18:04]\n> заметка\n| a | b |\nРаз два-три. Четыре!\n"
    assert A.spoken_words(t) == ["Раз", "два-три", "Четыре"]


def test_parse_time_forms():
    assert A.parse_time("1:05.5") == 65.5
    assert A.parse_time("2,4") == 2.4
    assert A.parse_range("0.0-2.4") == (0.0, 2.4)
    assert A.parse_range("0:05 - 0:08") == (5.0, 8.0)
    with pytest.raises(ValueError):
        A.parse_range("5-3")


# ------------------------------------------------------------------ bad

def test_fresh_skeleton_fails(tmp_path):
    A.init_episode("x", tmp_path)
    rep = check(tmp_path / "episodes" / "x")
    assert not rep["ok"]
    assert has(rep, "script.md") and has(rep, "shotlist.md") and has(rep, "words.json")


def test_script_too_short_and_too_long(ep):
    p = ep / "script.md"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.split("## 3.")[0], encoding="utf-8")
    rep = check(ep)
    assert not rep["ok"] and has(rep, "words/s")
    p.write_text(text + "\n" + "слово " * 120 + "\n", encoding="utf-8")
    assert has(check(ep), "words/s")


def test_pace_edge_is_warning_not_error(ep):
    b = json.loads((ep / "brief.json").read_text(encoding="utf-8"))
    b["duration_s"] = 72  # 195 words / 72 s = 2.71
    (ep / "brief.json").write_text(json.dumps(b), encoding="utf-8")
    rep = check(ep)
    assert not has(rep, "words/s") and has(rep, "words/s", "warnings")


@pytest.mark.parametrize("dur", [50, 120])
def test_duration_out_of_range(ep, dur):
    b = json.loads((ep / "brief.json").read_text(encoding="utf-8"))
    b["duration_s"] = dur
    (ep / "brief.json").write_text(json.dumps(b), encoding="utf-8")
    assert has(check(ep), "duration_s")


def test_gap_between_scene_changes(ep):
    def f(lines):
        i = rows(lines)[10]
        a, b = lines[i].split("|")[1].strip().split("-")
        lines[i] = set_cell(lines[i], 0, f"{a}-{float(b) + 0.8:.1f}")
        return lines
    edit_shotlist(ep, f)
    rep = check(ep)
    assert not rep["ok"] and has(rep, "overlap")

    shutil.rmtree(ep)
    shutil.copytree(EXAMPLE, ep)
    edit_shotlist(ep, lambda ls: [x for k, x in enumerate(ls) if k != rows(ls)[10]])
    assert has(check(ep), "gap")


def test_picture_holds_longer_than_3s(ep):
    def f(lines):
        i, j = rows(lines)[4:6]
        a, _ = lines[i].split("|")[1].strip().split("-")
        _, b = lines[j].split("|")[1].strip().split("-")
        lines[i] = set_cell(lines[i], 0, f"{a}-{b}")
        del lines[j]
        return lines
    edit_shotlist(ep, f)
    assert has(check(ep), "change it at least every")


def test_fewer_than_three_schemes(ep):
    edit_shotlist(ep, lambda ls: [x.replace("схема: лестница", "2D").replace("схема: радиус", "2D").replace("схема: шахта", "2D")
                                  .replace("схема: цепочка", "2D").replace("схема: шкала", "2D") for x in ls])
    rep = check(ep)
    assert has(rep, "different scheme")


def test_same_scheme_name_counts_once(ep):
    edit_shotlist(ep, lambda ls: [x.replace("схема: лестница", "схема: разрез").replace("схема: радиус", "схема: разрез")
                                  .replace("схема: шахта", "схема: разрез").replace("схема: цепочка", "схема: разрез")
                                  .replace("схема: шкала", "схема: разрез") for x in ls])
    assert has(check(ep), "1 different scheme")


def test_3d_share_over_quarter(ep):
    def f(lines):
        for n, i in enumerate(rows(lines)):
            if n % 3 == 0:
                lines[i] = set_cell(lines[i], 3, "3D")
        return lines
    edit_shotlist(ep, f)
    assert has(check(ep), "3D takes")


def test_small_text_size(ep):
    def f(lines):
        i = rows(lines)[1]
        lines[i] = set_cell(lines[i], 7, "ЭТАЖ 20 / 28px")
        return lines
    edit_shotlist(ep, f)
    assert has(check(ep), "below 34 px")
    b = json.loads((ep / "brief.json").read_text(encoding="utf-8"))
    b["text_min_px"] = 30
    (ep / "brief.json").write_text(json.dumps(b), encoding="utf-8")
    assert has(check(ep), "text_min_px")


def test_missing_required_cell_and_column(ep):
    def f(lines):
        i = rows(lines)[2]
        lines[i] = set_cell(lines[i], 8, "-")
        return lines
    edit_shotlist(ep, f)
    assert has(check(ep), "'sound' is empty")
    text = (ep / "shotlist.md").read_text(encoding="utf-8").replace("Слои", "Что-то")
    (ep / "shotlist.md").write_text(text, encoding="utf-8")
    assert has(check(ep), "no column(s) layers")


def test_words_json_problems(ep):
    p = ep / "words.json"
    words = json.loads(p.read_text(encoding="utf-8"))
    bad = [dict(w) for w in words]
    bad[10]["s"], bad[10]["e"] = bad[4]["s"], bad[4]["e"] + 0.1
    p.write_text(json.dumps(bad), encoding="utf-8")
    assert has(check(ep), "goes back")
    bad = [dict(w) for w in words]
    bad[3]["e"] = bad[3]["s"] - 0.1
    p.write_text(json.dumps(bad), encoding="utf-8")
    assert has(check(ep), "before start")
    p.write_text("[]", encoding="utf-8")
    assert has(check(ep), "empty")
    p.write_text("{oops", encoding="utf-8")
    assert has(check(ep), "invalid JSON")
    p.write_text(json.dumps(words[:50]), encoding="utf-8")
    assert has(check(ep), "re-run recognition", "warnings")
    p.unlink()
    assert has(check(ep), "words.json: file is missing")


def test_warnings_for_style(ep):
    p = ep / "script.md"
    p.write_text(p.read_text(encoding="utf-8").replace("Не беги вниз.", "Давайте разберёмся, не беги вниз."), encoding="utf-8")
    assert has(check(ep), "cliche", "warnings")
    edit_shotlist(ep, lambda ls: [x.replace("смена крупности", "склейка по действию") for x in ls])
    assert has(check(ep), "same transition", "warnings")


def test_missing_dir_and_bad_stage(tmp_path):
    with pytest.raises(ShortsError):
        A.check_episode(tmp_path / "none")
    with pytest.raises(ShortsError):
        A.check_episode(tmp_path, stage="x")


# ------------------------------------------------------------------ init / pick

def test_init_creates_and_never_overwrites(tmp_path):
    rep = A.init_episode("blackout", tmp_path)
    ep = tmp_path / "episodes" / "blackout"
    for fn in ("script.md", "shotlist.md", "words.json", "brief.json", "notes.md"):
        assert (ep / fn).is_file()
    assert json.loads((ep / "brief.json").read_text(encoding="utf-8"))["episode"] == "blackout"
    assert json.loads((ep / "words.json").read_text(encoding="utf-8")) == []
    (ep / "script.md").write_text("мой текст", encoding="utf-8")
    rep = A.init_episode("blackout", tmp_path)
    assert (ep / "script.md").read_text(encoding="utf-8") == "мой текст"
    assert rep["created"] == [] and len(rep["skipped_existing"]) == 5


@pytest.mark.parametrize("name", ["", "../x", "a/b", ".."])
def test_init_rejects_bad_names(tmp_path, name):
    with pytest.raises(ShortsError):
        A.init_episode(name, tmp_path)


def test_lists_are_complete_and_pick_is_deterministic():
    sc = json.loads((ROOT / "templates" / "animation" / "scenarios.json").read_text(encoding="utf-8"))
    assert [d["id"] for d in sc["disasters"]] == list(range(1, 51))
    assert [p["id"] for p in sc["places"]] == list(range(1, 51))
    md = (ROOT / "reference" / "animation-lists.md").read_text(encoding="utf-8")
    for d in sc["disasters"] + sc["places"]:
        assert d["name"] in md
    a, b = A.pick(3, seed=5), A.pick(3, seed=5)
    assert a == b and len(a["pairs"]) == 3
    assert len({p["disaster_id"] for p in a["pairs"]}) == 3 and len({p["place_id"] for p in a["pairs"]}) == 3


def test_pick_avoids_incompatible_pairs():
    sc = A._scenarios()
    iss = next(p for p in sc["places"] if p["name"].startswith("Международная"))
    tsunami = next(d for d in sc["disasters"] if d["name"] == "Цунами")
    assert not A.compatible(sc, tsunami, iss)
    for seed in range(40):
        for pr in A.pick(10, seed=seed)["pairs"]:
            d = next(x for x in sc["disasters"] if x["id"] == pr["disaster_id"])
            p = next(x for x in sc["places"] if x["id"] == pr["place_id"])
            assert A.compatible(sc, d, p)


# ------------------------------------------------------------------ CLI

def test_cli_exit_codes(tmp_path, capsys):
    import shorts
    assert shorts.main(["anim-init", "e1", "--root", str(tmp_path)]) == 0
    assert shorts.main(["anim-check", str(tmp_path / "episodes" / "e1")]) == 1
    assert shorts.main(["anim-check", str(EXAMPLE)]) == 0
    assert shorts.main(["anim-pick", "--seed", "1", "--n", "2"]) == 0
    assert shorts.main(["anim-check", str(tmp_path / "missing")]) == 2
    out = capsys.readouterr().out
    assert "Прорыв" in out or "pairs" in out


def test_example_plan_validates():
    from shortskit import plan as P
    f = ROOT / "templates" / "animation" / "plan.example.json"
    raw, d = P.load(f)
    assert not P.errors(P.check(raw, d, allow_missing_media=True))
