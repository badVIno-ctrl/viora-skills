import numpy as np

from shortskit.adapters import film as FL


def test_heatmap_drives_moments():
    heat = [{"start_time": i * 6.0, "end_time": (i + 1) * 6.0, "value": 0.1} for i in range(100)]
    heat[40]["value"] = 1.0  # 240-246 s is the most replayed part
    heat[70]["value"] = 0.8
    grid, score, parts = FL.score_timeline(600, heat, None, None, None)
    wins = FL.pick_windows(grid, score, 2, 4.0, gap=1.0, skip_head=12, skip_tail=36)
    starts = sorted(w[0] for w in wins)
    assert 236 <= starts[0] <= 246 and 416 <= starts[1] <= 426
    assert set(parts) == {"heatmap"}


def test_loudness_and_cuts_without_heatmap():
    t = np.arange(0, 300, 0.5)
    loud = -30 + 20 * np.exp(-((t - 150) ** 2) / 20)
    cuts = [148, 149, 150.5, 151, 152]
    grid, score, parts = FL.score_timeline(300, None, (t, loud), cuts, None)
    (s, e, sc), = FL.pick_windows(grid, score, 1, 4.0, gap=1.0)
    assert 144 <= s <= 152 and set(parts) == {"loudness", "cuts"}


def test_beat_cuts_land_on_beats():
    beat = 60 / 112
    b = {"tempo": 112.0, "beats": [round(i * beat, 3) for i in range(80)],
         "downbeats": [round(i * beat, 3) for i in range(0, 80, 4)]}
    cuts = FL.beat_cuts(b, 0.0, 20.0)
    assert cuts[0] == 0 and cuts[-1] == 20.0
    shots = np.diff(cuts)
    assert 0.9 < np.median(shots) < 2.2  # ~1.6 s target
    strong = FL.strong_beats(b, 0.0, 20.0)
    for c in cuts[1:-1]:
        assert abs(c * 30 - round(c * 30)) < 3e-3  # on a frame
        assert min(abs(c - x) for x in strong) <= 0.5 / 30 + 1e-6  # on a strong beat, frame-snapped


def test_music_window_starts_on_downbeat():
    b = {"energy": {"t": list(np.arange(0, 60, 0.25)), "rms": [0.1] * 120 + [0.9] * 60 + [0.2] * 60},
         "downbeats": [i * 2.0 for i in range(30)], "beats": [], "tempo": 120}
    st = FL.best_music_window(b, 10.0)
    assert st in b["downbeats"] and 26 <= st <= 32
