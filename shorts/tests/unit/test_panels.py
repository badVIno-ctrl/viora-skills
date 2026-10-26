"""Item 5 (1.1.0): own top-panel loops. Every loop: >= 30% of pixels change each second, no dark void,
seamless, chosen by topic. The 1.0.0 loop (dark sky, small runner) is the BAD case QA now rejects."""
from __future__ import annotations

import numpy as np
import pytest

from shortskit import panels as PN

PALETTES = [("#0A0A0A", "#FFFFFF", "#FF6A1A"), ("#F4F1EA", "#111111", "#C8102E"), ("#000000", "#FFFFFF", "#E63946")]


def _sample(kind, pal, w=540, h=192, fps=5):
    fr, ts = [], []
    p = PN.Pal(*pal)
    for i in range(int(PN.LOOP * fps)):
        t = i / fps
        fr.append(PN.DRAW[kind](t, w, h, p)[..., ::-1].copy())
        ts.append(t)
    return fr, ts


@pytest.mark.parametrize("pal", PALETTES)
@pytest.mark.parametrize("kind", PN.KINDS)
def test_loop_changes_30pct_every_second_and_no_dark_void(kind, pal):
    fr, ts = _sample(kind, pal)
    m = PN.measure_frames(fr, ts)
    assert m["change_min"] >= PN.MIN_CHANGE, m
    assert m["dark_void"] <= PN.MAX_DARK_VOID, m


@pytest.mark.parametrize("kind", PN.KINDS)
def test_loop_is_seamless(kind):
    """The jump from the last frame to the first is no bigger than the biggest ordinary frame step."""
    p = PN.Pal(*PALETTES[0])
    fps = 15
    fr = [PN.DRAW[kind](i / fps, 270, 96, p).astype(int) for i in range(int(PN.LOOP * fps))]
    steps = [np.abs(a - b).mean() for a, b in zip(fr, fr[1:])]
    seam = np.abs(fr[-1] - fr[0]).mean()
    assert seam <= 1.2 * max(steps), (seam, max(steps))


def test_dull_panel_is_rejected():
    # BAD case like the 1.0.0 loop: dark sky over most of the panel, a small sprite moving
    fr, ts = [], []
    for i in range(50):
        f = np.full((192, 540, 3), 16, np.uint8)
        x = (i * 7) % 500
        f[150:170, x:x + 20] = 240
        fr.append(f)
        ts.append(i / 5)
    m = PN.measure_frames(fr, ts)
    assert not m["ok"] and m["change_min"] < PN.MIN_CHANGE and m["dark_void"] > PN.MAX_DARK_VOID


def test_shift_by_whole_period_per_second_counts_as_no_change():
    # a stripe pattern that moves exactly one period per second looks frozen to a 1 s comparison
    base = np.tile(np.repeat(np.array([40, 200], np.uint8), 20), 14)  # period 40, 560 px
    fr = [np.repeat(np.roll(base, i * 8)[None, :540, None], 192, 0).repeat(3, 2) for i in range(50)]  # 40 px/s
    assert PN.measure_frames(fr, [i / 5 for i in range(50)])["change_min"] < 0.05


@pytest.mark.parametrize("topic,kind", [("Нейросеть пишет код", "code"), ("3D модель детали", "spin"),
                                        ("Какая ИИ быстрее: гонка", "code"), ("Турнир: кто быстрее", "race"),
                                        ("Эдит из фильма", "runner"), ("ничего", "runner")])
def test_choose_kind(topic, kind):
    assert PN.choose_kind(topic) == kind


def test_choose_kind_by_source():
    assert PN.choose_kind("x", ["html"]) == "spin"


def test_make_loop_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTS_CACHE", str(tmp_path))
    p1 = PN.make_loop("runner", 320, 112, 10, PALETTES[0])
    mt = p1.stat().st_mtime
    p2 = PN.make_loop("runner", 320, 112, 10, PALETTES[0])
    assert p1 == p2 and p2.stat().st_mtime == mt
    m = PN.measure_file(p1, 320, 112)
    assert m["ok"], m


def test_unknown_loop_is_plan_error():
    from shortskit import plan as P
    from conftest import mini_plan  # type: ignore

    p = mini_plan(layout={"mode": "three", "top": {"source": "loop:fireworks"}, "bottom": {"handle": "x"}})
    assert any(i.code == "top_source" for i in P.errors(P.check(p)))
