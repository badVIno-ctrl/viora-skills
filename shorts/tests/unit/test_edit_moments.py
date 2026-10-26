"""Item 1 of 1.1.0: an edit must not take credits, title cards or black frames, even when the heatmap says so."""
from __future__ import annotations

import numpy as np

from shortskit.adapters import film as FL
from shortskit.analysis import screens as S

from conftest import SYN_BLACK, SYN_CREDITS, SYN_TITLE, heatmap_on_text


def _overlaps(a: float, b: float, rng: tuple[float, float], pad: float = 0.0) -> bool:
    return a < rng[1] + pad and b > rng[0] - pad


def test_text_detector_finds_title_card_and_credits(synthetic_film):
    r = S.film_screens(synthetic_film, fps=1.0)
    runs = S.text_runs(r["t"], r["text"])
    assert any(a <= SYN_TITLE[0] + 1 and b >= SYN_TITLE[1] - 1 for a, b in runs), runs
    assert any(a <= SYN_CREDITS[0] + 2 and b >= SYN_CREDITS[1] - 1 for a, b in runs), runs
    film_part = [v for t, v in zip(r["t"], r["text"]) if t < SYN_TITLE[0] - 1]
    assert max(film_part) < 0.5  # moving shapes are not text
    blk = [t for t, b in zip(r["t"], r["black"]) if b]
    assert blk and all(SYN_BLACK[0] - 1 <= t <= SYN_BLACK[1] + 1 for t in blk), blk


def test_heatmap_peak_on_credits_is_not_taken(synthetic_film):
    """BAD case that passed in 1.0.0: heatmap peak on the credits -> the edit was all credits."""
    moments = FL.find_moments(str(synthetic_film), n=6, min_len=2.0, max_len=3.0, heatmap=heatmap_on_text())
    assert moments
    for m in moments:
        assert not _overlaps(m["start"], m["end"], SYN_CREDITS, 0.5), m
        assert not _overlaps(m["start"], m["end"], SYN_TITLE, 0.5), m
        assert not _overlaps(m["start"], m["end"], SYN_BLACK, 0.5), m
        assert m["end"] <= 60 * (1 - FL.TAIL_SKIP) + 1e-6 and m["start"] >= 60 * FL.HEAD_SKIP - 1e-6


def test_1_0_0_selection_would_take_the_credits():
    """Proves the test above guards a real bug: without the content penalty the peak wins."""
    grid, score, _ = FL.score_timeline(60, heatmap_on_text(), None, None, None)
    (s, e, _sc), = FL.pick_windows(grid, score, 1, 2.5, gap=1.0, skip_head=1.2, skip_tail=3.6)
    assert _overlaps(s, e, SYN_CREDITS) or _overlaps(s, e, SYN_TITLE)


def test_edit_plan_avoids_text_and_spreads_over_the_film(synthetic_film):
    p = FL.edit_plan(str(synthetic_film), music="builtin", length=12.0, heatmap=heatmap_on_text(), n=8)
    for sc in p["scenes"]:
        a, b = sc["source"]["in"], sc["source"]["out"]
        assert not _overlaps(a, b, SYN_CREDITS) and not _overlaps(a, b, SYN_TITLE), sc
    secs = {m["section"] for m in p["metadata"]["moments"]}
    assert len(secs) >= 3  # different parts of the film


def test_diversity_no_more_than_two_in_a_row_from_one_place():
    moments = [{"start": s, "end": s + 3.5, "peak": s + 1, "score": sc, "section": sec}
               for s, sc, sec in [(10, 0.9, 0), (14, 0.8, 0), (18, 0.7, 0), (100, 0.5, 3), (200, 0.4, 5)]]
    shots = [(i * 1.0, i * 1.0 + 1.0) for i in range(12)]
    out = FL.assemble_shots(moments, shots)
    assert FL.max_run_same_section(out) <= 2
    assert out[0]["role"] == "best" and 11 <= out[0]["in"] <= 13.5  # first frame = peak of the best moment
    assert out[-1]["role"] == "loop" and abs(out[-1]["out"] - out[0]["in"]) < 1e-6  # seamless loop
    hero = [s for s in out if s["role"] == "hero"]
    assert len(hero) == 1 and hero[0]["rate"] < 1  # slow-mo on the peak


def test_pick_windows_respects_hard_mask():
    grid = np.arange(0, 100, 0.5)
    score = np.ones_like(grid)
    score[(grid > 40) & (grid < 50)] = 5
    hard = (grid > 38) & (grid < 52)
    wins = FL.pick_windows(grid, score, 3, 4.0, gap=1.0, hard=hard)
    assert all(not (s < 52 and e > 38) for s, e, _ in wins)
