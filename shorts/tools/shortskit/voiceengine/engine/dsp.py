# -*- coding: utf-8 -*-
"""numpy-only audio DSP used to shape age / gender / character of a voice."""
import numpy as np


def _fast_len(n):
    best = 1 << int(np.ceil(np.log2(max(n, 1))))
    a = 1
    while a < best:
        b = a
        while b < best:
            c = b
            while c < best:
                if c >= n:
                    best = min(best, c)
                c *= 5
            b *= 3
        a *= 2
    return best


def resample_len(x, m):
    """Band-limited FFT resampling of x to exactly m samples."""
    x = np.asarray(x, np.float64)
    n = len(x)
    if n == 0 or m == n:
        return x.astype(np.float32)
    pad = min(4096, n)
    xp = np.concatenate([np.zeros(pad), x, np.zeros(pad)])
    N = _fast_len(len(xp))
    X = np.fft.rfft(xp, N)
    M = int(round(N * m / n))
    k = M // 2 + 1
    if k <= len(X):
        Y = X[:k].copy()
        taper = max(8, k // 64)
        Y[-taper:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, taper)))
    else:
        Y = np.zeros(k, complex)
        Y[:len(X)] = X
    y = np.fft.irfft(Y, M) * (M / N)
    p2 = int(round(pad * m / n))
    return y[p2:p2 + m].astype(np.float32)


def resample(x, sr_in, sr_out):
    if sr_in == sr_out:
        return np.asarray(x, np.float32)
    return resample_len(x, int(round(len(x) * sr_out / sr_in)))


def speedup(x, factor):
    """Play `factor` times faster (all frequencies x factor, duration / factor)."""
    if abs(factor - 1.0) < 1e-4:
        return np.asarray(x, np.float32)
    return resample_len(x, int(round(len(x) / factor)))


def _smooth_noise(n, sr, cutoff_hz, rng):
    """zero-mean unit-std low-passed noise"""
    step = max(1, int(sr / (cutoff_hz * 4)))
    k = n // step + 4
    pts = rng.standard_normal(k)
    t = np.arange(n) / step
    y = np.interp(t, np.arange(k), pts)
    # extra smoothing (moving average over one step)
    if step > 1:
        c = np.cumsum(np.concatenate([[0], y]))
        y = (c[step:] - c[:-step]) / step
        y = np.concatenate([y, np.full(n - len(y), y[-1] if len(y) else 0)])
    s = y.std()
    return (y - y.mean()) / (s if s > 1e-9 else 1)


def pitch_wobble(x, sr, tremor_hz=0.0, tremor_depth=0.0, jitter=0.0, seed=0):
    """Frequency modulation by a time-varying delay line.
    tremor_depth / jitter are relative frequency deviations (0.02 = 2 %)."""
    if tremor_depth <= 0 and jitter <= 0:
        return np.asarray(x, np.float32)
    rng = np.random.default_rng(seed)
    n = len(x)
    t = np.arange(n) / sr
    dev = np.zeros(n)
    if tremor_depth > 0 and tremor_hz > 0:
        rate = tremor_hz * (1 + 0.12 * _smooth_noise(n, sr, 0.7, rng))
        phase = 2 * np.pi * np.cumsum(rate) / sr
        amp = tremor_depth * (1 + 0.35 * _smooth_noise(n, sr, 1.0, rng)).clip(0.2, 2)
        dev += amp * np.sin(phase)
    if jitter > 0:
        dev += jitter * _smooth_noise(n, sr, 35.0, rng)
    delay = -np.cumsum(dev) / sr * sr          # samples
    delay -= delay.mean()
    idx = np.arange(n) - delay
    idx = np.clip(idx, 0, n - 1)
    return np.interp(idx, np.arange(n), x).astype(np.float32)


def amp_wobble(x, sr, rate_hz=0.0, depth=0.0, shimmer=0.0, seed=1):
    if depth <= 0 and shimmer <= 0:
        return x
    rng = np.random.default_rng(seed)
    n = len(x)
    g = np.ones(n)
    if depth > 0 and rate_hz > 0:
        rate = rate_hz * (1 + 0.1 * _smooth_noise(n, sr, 0.7, rng))
        g *= 1 + depth * np.sin(2 * np.pi * np.cumsum(rate) / sr + 1.3)
    if shimmer > 0:
        g *= np.exp(shimmer * _smooth_noise(n, sr, 40.0, rng))
    return (x * g).astype(np.float32)


# --------------------------------------------------------------------- STFT tools
def stft(x, n=1024, hop=256):
    w = np.hanning(n + 1)[:-1]
    pad = np.concatenate([np.zeros(n), x, np.zeros(n)])
    frames = np.lib.stride_tricks.sliding_window_view(pad, n)[::hop] * w
    return np.fft.rfft(frames, axis=1), w


def istft(X, w, n_out, n=1024, hop=256):
    fr = np.fft.irfft(X, n, axis=1) * w
    T = fr.shape[0]
    L = (T - 1) * hop + n
    y = np.zeros(L)
    env = np.zeros(L)
    for i in range(T):
        y[i * hop:i * hop + n] += fr[i]
        env[i * hop:i * hop + n] += w ** 2
    y = y / np.maximum(env, 1e-8)
    return y[n:n + n_out]


def _envelope(mag, bins=12):
    k = np.ones(bins) / bins
    return np.apply_along_axis(lambda r: np.convolve(r, k, mode='same'), 1, mag)


def breathiness(x, sr, amount=0.0, seed=2, low_hz=900.0):
    """Add aspiration noise shaped like the voice's own spectral envelope."""
    if amount <= 0:
        return x
    rng = np.random.default_rng(seed)
    n = 1024 if sr >= 32000 else 512
    hop = n // 4
    X, w = stft(np.asarray(x, np.float64), n, hop)
    mag = np.abs(X)
    env = _envelope(mag, max(4, int(600 / (sr / n))))
    f = np.fft.rfftfreq(n, 1 / sr)
    hp = np.clip((f - low_hz) / (2 * low_hz), 0, 1) ** 1.5
    hp *= np.clip((14000 - f) / 4000, 0, 1) if sr > 30000 else 1
    ph = np.exp(2j * np.pi * rng.random(X.shape))
    noise = istft(env * hp * ph, w, len(x), n, hop)
    rms_x = np.sqrt(np.mean(np.asarray(x, np.float64) ** 2) + 1e-12)
    rms_n = np.sqrt(np.mean(noise ** 2) + 1e-12)
    y = x + amount * noise * (rms_x / rms_n) * 0.6
    return y.astype(np.float32)


def whisper(x, sr, seed=3):
    """Turn voiced speech into whisper (noise excitation, same envelope)."""
    rng = np.random.default_rng(seed)
    n = 1024 if sr >= 32000 else 512
    hop = n // 4
    X, w = stft(np.asarray(x, np.float64), n, hop)
    mag = np.abs(X)
    env = _envelope(mag, max(6, int(400 / (sr / n))))
    f = np.fft.rfftfreq(n, 1 / sr)
    shape = np.clip((f - 300) / 900, 0.05, 1.0)
    ph = np.exp(2j * np.pi * rng.random(X.shape))
    y = istft(env * shape * ph, w, len(x), n, hop)
    return (y / (np.abs(y).max() + 1e-9) * (np.abs(x).max() + 1e-9)).astype(np.float32)


def fft_filter(x, sr, gain_fn):
    """Zero-phase filtering with a gain curve gain_fn(freqs)->linear gain."""
    x = np.asarray(x, np.float64)
    N = _fast_len(len(x) + 2048)
    X = np.fft.rfft(x, N)
    f = np.fft.rfftfreq(N, 1 / sr)
    y = np.fft.irfft(X * gain_fn(f), N)[:len(x)]
    return y.astype(np.float32)


def tilt(x, sr, db_per_oct=0.0, pivot=1000.0):
    if abs(db_per_oct) < 0.05:
        return x
    def g(f):
        octs = np.log2(np.maximum(f, 50) / pivot)
        return 10 ** (np.clip(octs, -3, 4) * db_per_oct / 20)
    return fft_filter(x, sr, g)


def band(x, sr, low=None, high=None, order=2.0):
    def g(f):
        gg = np.ones_like(f)
        if low:
            gg *= 1 / np.sqrt(1 + (low / np.maximum(f, 1e-3)) ** (2 * order))
        if high:
            gg *= 1 / np.sqrt(1 + (f / high) ** (2 * order))
        return gg
    return fft_filter(x, sr, g)


def peak_eq(x, sr, freq, gain_db, q=1.0):
    def g(f):
        bw = freq / q
        return 10 ** (gain_db / 20 * np.exp(-0.5 * ((f - freq) / (bw / 2)) ** 2))
    return fft_filter(x, sr, g)


def reverb(x, sr, rt60=0.6, wet=0.25, predelay=0.012, seed=4):
    if wet <= 0:
        return x
    rng = np.random.default_rng(seed)
    L = int(sr * min(3.0, rt60 * 1.2))
    t = np.arange(L) / sr
    ir = rng.standard_normal(L) * np.exp(-6.91 * t / rt60)
    ir = band(ir, sr, low=150, high=6000)
    ir[:int(predelay * sr)] = 0
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    N = _fast_len(len(x) + L)
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x) + L]
    dry = np.concatenate([x, np.zeros(L)])
    out = (1 - wet) * dry + wet * y * 0.9
    return out.astype(np.float32)


def echo(x, sr, delay=0.25, feedback=0.35, wet=0.3):
    d = int(delay * sr)
    n = len(x) + d * 6
    y = np.concatenate([x, np.zeros(n - len(x))]).astype(np.float64)
    out = y.copy()
    g = wet
    for k in range(1, 7):
        out[k * d:] += g * y[:n - k * d]
        g *= feedback
    return out.astype(np.float32)


def ring_mod(x, sr, freq=50.0, mix=0.5):
    t = np.arange(len(x)) / sr
    return ((1 - mix) * x + mix * x * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def comb(x, sr, delay_ms=6.0, gain=0.5):
    d = int(sr * delay_ms / 1000)
    y = np.asarray(x, np.float64).copy()
    y[d:] += gain * x[:-d]
    return (y / (1 + gain)).astype(np.float32)


def telephone(x, sr, seed=5):
    rng = np.random.default_rng(seed)
    y = band(x, sr, low=320, high=3300, order=3)
    y = np.tanh(2.2 * y / (np.abs(y).max() + 1e-9)) * 0.7
    y = y + 0.004 * rng.standard_normal(len(y))
    return y.astype(np.float32)


def saturate(x, drive=2.0):
    m = np.abs(x).max() + 1e-9
    return (np.tanh(drive * x / m) / np.tanh(drive) * m).astype(np.float32)


def trim_bounds(x, sr, thr_db=-48.0, keep=0.04):
    """(a, b) such that trim(x) == x[a:b]; (0, 0) when everything is silent."""
    x = np.asarray(x, np.float32)
    if len(x) == 0:
        return 0, 0
    win = int(0.01 * sr)
    e = np.sqrt(np.convolve(x.astype(np.float64) ** 2, np.ones(win) / win, mode='same') + 1e-12)
    ref = e.max()
    on = np.where(20 * np.log10(e / ref + 1e-12) > thr_db)[0]
    if len(on) == 0:
        return 0, 0
    return max(0, on[0] - int(keep * sr)), min(len(x), on[-1] + int(keep * sr))


def trim(x, sr, thr_db=-48.0, keep=0.04):
    x = np.asarray(x, np.float32)
    a, b = trim_bounds(x, sr, thr_db, keep)
    return x[a:b]


def fade(x, sr, fin=0.005, fout=0.02):
    x = np.asarray(x, np.float32).copy()
    a, b = int(fin * sr), int(fout * sr)
    if len(x) > a + b:
        if a:
            x[:a] *= np.linspace(0, 1, a)
        if b:
            x[-b:] *= np.linspace(1, 0, b)
    return x


def loudness(x, sr, target_db=-19.0, peak=0.93):
    x = np.asarray(x, np.float64)
    if len(x) == 0 or np.abs(x).max() < 1e-7:
        return x.astype(np.float32)
    win = int(0.05 * sr)
    n = len(x) // win
    if n >= 1:
        fr = x[:n * win].reshape(n, win)
        r = np.sqrt((fr ** 2).mean(1) + 1e-12)
        gate = r > r.max() * 0.03
        rms = np.sqrt(np.mean(r[gate] ** 2)) if gate.any() else r.max()
    else:
        rms = np.sqrt(np.mean(x ** 2))
    x = x * (10 ** (target_db / 20) / (rms + 1e-12))
    # soft limiter
    th = 0.75 * peak
    a = np.abs(x)
    over = a > th
    if over.any():
        x[over] = np.sign(x[over]) * (th + (peak - th) * np.tanh((a[over] - th) / (peak - th)))
    return x.astype(np.float32)


def f0_track(x, sr, fmin=60.0, fmax=700.0, hop_s=0.01, win_s=0.04, thr=0.22):
    """YIN-style f0 tracker (numpy only).  Returns array of f0 per frame (0 = unvoiced)."""
    x = np.asarray(x, np.float64)
    if sr != 16000:
        x = resample(x, sr, 16000).astype(np.float64)
        sr = 16000
    W = int(win_s * sr)
    hop = int(hop_s * sr)
    maxlag = int(sr / fmin) + 1
    minlag = max(2, int(sr / fmax))
    if len(x) < W + maxlag + 1:
        return np.zeros(0)
    nfr = (len(x) - W - maxlag) // hop
    idx = np.arange(nfr)[:, None] * hop + np.arange(W + maxlag)[None, :]
    fr = x[idx]
    fr = fr - fr.mean(1, keepdims=True)
    N = 1 << int(np.ceil(np.log2(W + maxlag + W)))
    A = np.fft.rfft(fr, N, axis=1)
    B = np.fft.rfft(fr[:, :W], N, axis=1)
    acf = np.fft.irfft(np.conj(B) * A, N, axis=1)[:, :maxlag + 1]
    c2 = np.concatenate([np.zeros((nfr, 1)), np.cumsum(fr ** 2, axis=1)], axis=1)
    E1 = c2[:, W:W + 1]
    tau = np.arange(maxlag + 1)
    E2 = c2[:, tau + W] - c2[:, tau]
    d = np.maximum(E1 + E2 - 2 * acf, 0)
    cs = np.cumsum(d[:, 1:], axis=1)
    dn = np.ones_like(d)
    dn[:, 1:] = d[:, 1:] * tau[None, 1:] / np.maximum(cs, 1e-12)
    energy = E1[:, 0]
    loud = energy > (energy.max() * 10 ** (-40 / 10) if len(energy) else 0)
    f0 = np.zeros(nfr)
    seg = dn[:, minlag:maxlag]
    for i in range(nfr):
        if not loud[i]:
            continue
        s = seg[i]
        below = np.where(s < thr)[0]
        if len(below) == 0:
            continue
        j = below[0]
        while j + 1 < len(s) and s[j + 1] < s[j]:
            j += 1
        # parabolic interpolation
        k = j + minlag
        if 1 <= j < len(s) - 1:
            a, b, c = s[j - 1], s[j], s[j + 1]
            den = a - 2 * b + c
            off = 0.5 * (a - c) / den if abs(den) > 1e-12 else 0.0
        else:
            off = 0.0
        f0[i] = sr / (k + off)
    return f0


def f0_median(x, sr):
    f = f0_track(x, sr)
    f = f[f > 0]
    return float(np.median(f)) if len(f) else 0.0
