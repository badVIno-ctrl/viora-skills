"""Generate the skill's own assets (CC0, made by code): the music bed.
Top-panel loops are drawn at render time (shortskit/panels.py) and cached.

python3 tools/make_assets.py            # writes assets/audio/bed.mp3, edit.mp3 (+ edit.json: bpm, drop, beats)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shortskit.config import asset  # noqa: E402
from shortskit.engine.audio import SR, _write_wav  # noqa: E402
from shortskit.util import run  # noqa: E402


def music_bed(seconds: float = 32.0, bpm: float = 112.0, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    beat = 60.0 / bpm
    out = np.zeros(n)
    # kick on every beat
    kick_n = int(0.25 * SR)
    kt = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * np.cumsum(120 * np.exp(-kt * 30) + 42) / SR) * np.exp(-kt * 12)
    hat_n = int(0.05 * SR)
    hat = rng.standard_normal(hat_n) * np.exp(-np.arange(hat_n) / SR * 90)
    hat = np.diff(hat, prepend=0)
    roots = [45, 45, 41, 43]  # A, A, F, G (midi-ish offsets for bass)
    i = 0
    tb = 0.0
    while tb < seconds:
        s = int(tb * SR)
        out[s:s + kick_n] += kick[: max(0, min(kick_n, n - s))] * 0.9
        h = int((tb + beat / 2) * SR)
        if h < n:
            out[h:h + hat_n] += hat[: max(0, min(hat_n, n - h))] * 0.25
        bar = int(tb / (beat * 4)) % 4
        f = 440 * 2 ** ((roots[bar] - 69 + 12) / 12) / 2
        bn = int(beat * 0.9 * SR)
        bt = np.arange(min(bn, n - s)) / SR
        out[s:s + len(bt)] += 0.28 * np.sign(np.sin(2 * np.pi * f * bt)) * np.exp(-bt * 3.5)
        i += 1
        tb += beat
    # soft chord pad per bar
    for b in range(int(seconds / (beat * 4)) + 1):
        s = int(b * beat * 4 * SR)
        e = min(n, int((b + 1) * beat * 4 * SR))
        if s >= n:
            break
        pt = np.arange(e - s) / SR
        root = roots[b % 4] + 12
        pad = sum(np.sin(2 * np.pi * 440 * 2 ** ((root + iv - 69) / 12) * pt) for iv in (0, 3, 7))
        env = np.minimum(1, pt / 0.4) * np.minimum(1, (pt[-1] - pt) / 0.4 + 0.05)
        out[s:e] += 0.06 * pad * env
    # simple one-pole low-pass for warmth
    y = np.zeros_like(out)
    acc = 0.0
    a = 0.35
    for k in range(n):
        acc += a * (out[k] - acc)
        y[k] = acc
    y /= np.max(np.abs(y)) + 1e-9
    return np.stack([y, y], axis=1).astype(np.float32) * 0.8


def _sat(x: np.ndarray, drive: float = 1.6) -> np.ndarray:
    return np.tanh(x * drive) / np.tanh(drive)


def _lp(x: np.ndarray, a: float) -> np.ndarray:
    """One-pole low-pass (vectorised with lfilter if scipy is present, else a loop)."""
    try:
        from scipy.signal import lfilter

        return lfilter([a], [1, -(1 - a)], x)
    except Exception:  # noqa: BLE001
        y = np.zeros_like(x)
        acc = 0.0
        for k in range(len(x)):
            acc += a * (x[k] - acc)
            y[k] = acc
        return y


def music_edit(bpm: float = 140.0, intro_bars: int = 4, drop_bars: int = 12, seed: int = 7) -> tuple[np.ndarray, dict]:
    """Edit track (phonk-like, CC0, made by code): quiet dark intro under the dialogue, one beat of silence,
    then the DROP: 808 with glide, kick, clap on 2 and 4, hats with rolls, cowbell riff. Returns (stereo, info):
    info = {bpm, drop (s), beats, downbeats} - the planner puts the drop exactly at the end of the dialogue."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar = beat * 4
    drop = intro_bars * bar
    seconds = drop + drop_bars * bar + 1.5
    n = int(seconds * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    def put(buf, x, t, g=1.0):
        s = int(t * SR)
        if s >= n or s < 0:
            return
        k = min(len(x), n - s)
        buf[s:s + k] += x[:k] * g

    def both(x, t, g=1.0, pan=0.0):
        put(L, x, t, g * (1 - max(0, pan)))
        put(R, x, t, g * (1 + min(0, pan)))

    def tone(freq, dur, kind="sin"):
        tt = np.arange(int(dur * SR)) / SR
        ph = 2 * np.pi * freq * tt
        if kind == "sq":
            return np.sign(np.sin(ph)) * 0.6 + np.sin(ph) * 0.4
        return np.sin(ph)

    # A minor: A1=55 Hz roots per bar of a 4-bar loop
    roots = [55.0, 55.0, 43.65, 49.0]  # A, A, F, G
    # --- intro: dark pad + vinyl crackle + filtered riff hint
    for b in range(intro_bars):
        f0 = roots[b % 4] * 4
        tt = np.arange(int(bar * SR)) / SR
        pad = sum(np.sin(2 * np.pi * f0 * r * tt + rng.random() * 6) for r in (1, 1.189, 1.498, 2.0))
        pad *= np.minimum(1, tt / 0.5) * np.minimum(1, (bar - tt) / 0.3)
        both(_lp(pad, 0.08), b * bar, 0.10)
    crack = (rng.random(int(drop * SR)) > 0.9993).astype(float) * rng.standard_normal(int(drop * SR))
    both(_lp(crack, 0.5), 0.0, 0.15)
    # filter-opening noise riser in the last intro bar, ending one beat before the drop (gap = tension)
    rlen = bar - beat
    tt = np.arange(int(rlen * SR)) / SR
    nz = rng.standard_normal(len(tt))
    rise = np.concatenate([_lp(nz[i:i + 2205], 0.02 + 0.5 * (i / len(tt)) ** 2) for i in range(0, len(tt), 2205)])[:len(tt)]
    both(rise * (tt / rlen) ** 2, drop - bar, 0.35)
    # --- drop
    kick_t = np.arange(int(0.35 * SR)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 180 * np.exp(-kick_t * 35)) / SR) * np.exp(-kick_t * 9)
    kick[: int(0.004 * SR)] += rng.standard_normal(int(0.004 * SR)) * 0.5
    clap_t = np.arange(int(0.22 * SR)) / SR
    clap = rng.standard_normal(len(clap_t)) * (np.exp(-clap_t * 28) + 0.6 * np.exp(-((clap_t - 0.012) % 0.011) * 300) * (clap_t < 0.035))
    clap = clap - _lp(clap, 0.12)
    hat_t = np.arange(int(0.04 * SR)) / SR
    hat = np.diff(rng.standard_normal(len(hat_t)), prepend=0) * np.exp(-hat_t * 110)
    bell_t = np.arange(int(0.28 * SR)) / SR

    def bell(f):
        x = np.sign(np.sin(2 * np.pi * f * bell_t)) + np.sign(np.sin(2 * np.pi * f * 1.48 * bell_t))
        return _lp(x, 0.35) * np.exp(-bell_t * 14)

    # cowbell riff (A minor), 8 eighths per bar, None = rest
    riff = [[880, None, 1046.5, 880, None, 783.99, 880, None],
            [880, None, 1046.5, 1174.7, None, 1046.5, 880, None],
            [698.46, None, 880, 698.46, None, 659.26, 698.46, None],
            [783.99, None, 987.77, 783.99, None, 880, 783.99, 659.26]]
    sub = np.zeros(n)
    for b in range(drop_bars):
        t0 = drop + b * bar
        last = b == drop_bars - 1
        # kick: 1, 2&, 3 (phonk-ish), clap on 2 and 4
        for k in (0.0, 1.5, 2.0, 3.25) if b % 2 else (0.0, 1.5, 2.0):
            both(kick, t0 + k * beat, 0.95)
        for k in (1, 3):
            both(clap, t0 + k * beat, 0.45)
        # hats: eighths, a 1/16 roll at the end of every second bar
        for k in range(8):
            both(hat, t0 + k * beat / 2, 0.18 if k % 2 else 0.12, pan=0.3)
        if b % 2:
            for k in range(6):
                both(hat, t0 + 3 * beat + k * beat / 6, 0.10 + 0.02 * k, pan=-0.3)
        # 808: long note per bar on the root with a glide into the next bar's root
        f_now, f_next = roots[b % 4], roots[(b + 1) % 4]
        tt = np.arange(int(bar * SR)) / SR
        glide = np.where(tt > bar - beat * 0.5, (tt - (bar - beat * 0.5)) / (beat * 0.5), 0.0)
        f = f_now * (f_next / f_now) ** glide
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, tt / 0.005) * (0.55 + 0.45 * np.exp(-tt * 1.2))
        if last:
            x *= np.exp(-tt * 2.5)
        put(sub, x, t0)
        # cowbell
        for k, fr in enumerate(riff[b % 4]):
            if fr is not None:
                pan = -0.25 if k % 2 else 0.25
                both(bell(fr), t0 + k * beat / 2, 0.16, pan=pan)
                both(bell(fr), t0 + k * beat / 2 + beat * 0.75, 0.05, pan=-pan)  # dotted echo
    sub = _sat(sub, 2.2) * 0.55
    L += sub
    R += sub
    # sidechain: everything except kick/sub pumps a little on the beat (the drop part)
    y = np.stack([L, R], 1)
    y = _sat(y / (np.max(np.abs(y)) + 1e-9), 1.3)
    y /= np.max(np.abs(y)) + 1e-9
    y = (y * 0.89).astype(np.float32)
    nb = int(round((seconds - 1.5) / beat))
    beats = [round(i * beat, 4) for i in range(nb)]
    info = {"bpm": bpm, "drop": round(drop, 4), "beat": round(beat, 5), "beats": beats,
            "downbeats": beats[::4], "duration": round(seconds, 3),
            "sections": [{"t": 0.0, "name": "intro (quiet, under the dialogue)"},
                         {"t": round(drop - beat, 4), "name": "gap (1 beat of silence)"},
                         {"t": round(drop, 4), "name": "drop"}]}
    return y, info


def main() -> None:
    wav = asset("audio/bed.wav")
    asset("audio").mkdir(parents=True, exist_ok=True)
    _write_wav(wav, music_bed())
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "96k", asset("audio/bed.mp3")])
    wav.unlink()
    print("ok:", asset("audio/bed.mp3"))
    y, info = music_edit()
    wav = asset("audio/edit.wav")
    _write_wav(wav, y)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k", asset("audio/edit.mp3")])
    wav.unlink()
    import json

    asset("audio/edit.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print("ok:", asset("audio/edit.mp3"), "drop at", info["drop"])


if __name__ == "__main__":
    main()
