"""Speed curves for edits ("velocity"): the clip flies in fast, hangs in slow motion, flies out.

How editors do it (CapCut "Curve" speed, AE time remap): points (position in the clip, speed). Our version:
points (tau 0..1 of the OUTPUT shot, rate), smooth between points in log-rate (speed changes feel even),
source time = integral of rate. The slowest part ("hang") is put on the peak of the moment.
"""
from __future__ import annotations

import numpy as np

_trapz = getattr(np, "trapezoid", None) or np.trapz

PRESETS: dict[str, list[tuple[float, float]]] = {
    # tutorial curve (Tifofey, CapCut): ~10x -> ~0.5x -> back up. Softer ends: we cut on the beat anyway.
    "velocity": [(0.0, 6.0), (0.2, 0.5), (0.7, 0.5), (1.0, 5.0)],
    # hero shot on the loudest part: longer, deeper hang
    "hero": [(0.0, 4.0), (0.18, 0.3), (0.82, 0.3), (1.0, 3.5)],
    # fast in, slow tail into the next cut (good before a drop)
    "ramp_out": [(0.0, 1.0), (0.55, 1.0), (0.8, 0.35), (1.0, 0.3)],
    "flat": [(0.0, 1.0), (1.0, 1.0)],
}
N = 2001


def points(spec) -> list[tuple[float, float]]:
    if spec is None or spec is False or spec == "none":
        return PRESETS["flat"]
    if isinstance(spec, str):
        if spec not in PRESETS:
            raise ValueError(f"unknown velocity preset {spec!r}: {', '.join(PRESETS)}")
        return PRESETS[spec]
    pts = sorted((float(a), float(b)) for a, b in spec)
    if pts[0][0] > 0:
        pts.insert(0, (0.0, pts[0][1]))
    if pts[-1][0] < 1:
        pts.append((1.0, pts[-1][1]))
    if any(r <= 0 for _, r in pts):
        raise ValueError("velocity rates must be > 0")
    return pts


def rate_curve(spec, n: int = N) -> tuple[np.ndarray, np.ndarray]:
    pts = points(spec)
    tau = np.linspace(0, 1, n)
    xs = np.array([p[0] for p in pts])
    lr = np.log(np.array([p[1] for p in pts]))
    out = np.empty(n)
    for i, t in enumerate(tau):
        k = min(max(int(np.searchsorted(xs, t, side="right")) - 1, 0), len(xs) - 2)
        a, b = xs[k], xs[k + 1]
        u = 0.0 if b <= a else (t - a) / (b - a)
        u = u * u * (3 - 2 * u)  # smoothstep
        out[i] = np.exp(lr[k] + (lr[k + 1] - lr[k]) * u)
    return tau, out


def mean_rate(spec) -> float:
    tau, r = rate_curve(spec)
    return float(_trapz(r, tau))


def source_span(spec, out_len: float, scale: float = 1.0) -> float:
    """Seconds of source a shot of `out_len` seconds eats."""
    return mean_rate(spec) * out_len * scale


def hang_tau(spec) -> float:
    """Middle of the slowest part (where the peak of the moment goes)."""
    tau, r = rate_curve(spec)
    lo = r.min() * 1.05
    idx = np.where(r <= lo)[0]
    return float(tau[idx].mean())


class Remap:
    """Output time -> source time for one shot. `scale` stretches all rates (fit into a short shot)."""

    def __init__(self, spec, out_len: float, scale: float = 1.0):
        self.out_len = float(out_len)
        self.tau, r = rate_curve(spec)
        self.r = r * scale
        cum = np.concatenate([[0.0], np.cumsum((self.r[1:] + self.r[:-1]) / 2 * np.diff(self.tau))])
        self.cum = cum * self.out_len  # source seconds at tau
        self.span = float(self.cum[-1])

    def src(self, t_out: float) -> float:
        return float(np.interp(t_out / max(self.out_len, 1e-9), self.tau, self.cum))

    def rate(self, t_out: float) -> float:
        return float(np.interp(t_out / max(self.out_len, 1e-9), self.tau, self.r))

    def src_at_hang(self, spec) -> float:
        return self.src(hang_tau(spec) * self.out_len)


def fit_scale(spec, out_len: float, available: float, min_scale: float = 0.35) -> float | None:
    """Scale so the shot fits into `available` seconds of one camera shot; None if it would be too slow."""
    need = source_span(spec, out_len)
    if need <= available:
        return 1.0
    s = available / need
    return s if s >= min_scale else None
