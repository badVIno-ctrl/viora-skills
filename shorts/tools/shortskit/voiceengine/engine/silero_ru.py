# -*- coding: utf-8 -*-
"""Russian acoustic model + vocoder (Silero TTS v5_cis_base, MIT License,
(c) Silero Team), re-exported to ONNX.  numpy + onnxruntime only.

Speakers are plain embedding vectors, so voices can be blended
(weighted mix of several speakers = a new, non-existing voice)."""
import os
import re
import threading

import numpy as np

SYMBOLS = "_~|!'+,-.:;?hабвгдежзийклмнопрстуфхцчшщъыьэюяёєіїјўґғҕҗҙқҝҡңҥҫүұҳҷҹһӑӗәӝӟӣӥӧөӯӱӳӵӏ—… "
SYM2ID = {s: i for i, s in enumerate(SYMBOLS)}
_ALLOWED = re.compile(r'[^' + re.escape(SYMBOLS[4:]) + r'\^]')   # same set Silero keeps: '+,-.:;?' letters '—…' space
SR = 48000
HOP = 600          # vocoder hop: one duration frame = 600 samples = 12.5 ms


def clean_text(text):
    """Replicates Silero's prepare_text_input for plain text (after our own normalisation)."""
    text = text.strip()
    text = re.sub(r"\n", lambda m: " " if m.start() > 0 and text[m.start() - 1] in ",;:.!?" else ". ", text)
    text = text.lower()
    text = text.replace('—', '–').replace('–', '–').replace('‑', '-')
    text = _ALLOWED.sub('', text)
    text = text.replace('^', ' ^')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class SileroRU:
    def __init__(self, model_dir, threads=None):
        self.dir = model_dir
        self.threads = threads or min(4, os.cpu_count() or 2)
        self._lock = threading.Lock()
        self.S = None
        Z = np.load(os.path.join(model_dir, 'ru_speakers.npz'))
        self.W_t, self.W_d, self.W_p, self.msc = Z['W_t'], Z['W_d'], Z['W_p'], Z['msc']
        self.names = [str(x) for x in Z['names']]
        self.window = Z['window'].astype(np.float64)
        self.name2id = {n: i for i, n in enumerate(self.names)}

    def _load(self):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = self.threads
        so.inter_op_num_threads = 1
        so.log_severity_level = 3
        self.S = {k: ort.InferenceSession(os.path.join(self.dir, 'ru_%s.onnx' % k), so,
                                          providers=['CPUExecutionProvider'])
                  for k in ('pred', 'enc', 'dec_a', 'dec_b', 'dec_c', 'voc')}

    def ensure(self):
        if self.S is None:
            with self._lock:
                if self.S is None:
                    self._load()

    # ------------------------------------------------------------------ voices
    def voice(self, mix):
        """mix: {'ru_karina': 0.7, 'ru_vika': 0.3} or a single name -> voice dict."""
        if isinstance(mix, str):
            mix = {mix: 1.0}
        ids, w = [], []
        for n, a in mix.items():
            if n not in self.name2id:
                raise ValueError('unknown base speaker %s' % n)
            ids.append(self.name2id[n]); w.append(float(a))
        w = np.array(w, np.float32)
        w = w / w.sum()
        f = lambda M: (w[:, None] * M[ids]).sum(0, keepdims=True).astype(np.float32)
        return {'t': f(self.W_t), 'd': f(self.W_d), 'p': f(self.W_p), 'msc': float((w * self.msc[ids]).sum())}

    # ------------------------------------------------------------------ synthesis
    @staticmethod
    def _post_durs(logdur, rate):
        d = np.exp(logdur) - 1.0
        d[d < 0] = 0
        d = np.round(d)
        if d[0, 0] > 5: d[0, 0] = 5
        d = np.round(d / rate)
        if d[0, 0] > 5: d[0, 0] = 5
        if d[0, -1] > 7: d[0, -1] = 7
        d[0, -2] = 13
        if d[0, -3] > 13: d[0, -3] = 13
        return d

    @staticmethod
    def _upd_pitch(pitch, coef, msc, prange=None):
        pitch = pitch.copy()
        pitch[np.abs(pitch) < 0.001] = 0
        if prange is not None:
            pitch = pitch * prange
        c = coef.copy()
        pc = pitch * c
        c[:, np.where(c[0] == 0)[0]] = 1.0
        shift = (c - 1.0) * msc
        shift[pc[0] == 0] = 0
        return pc + shift

    def _istft(self, re_, im_):
        spec = re_.astype(np.float64) + 1j * im_.astype(np.float64)
        n_fft, hop, win = 2400, 600, 2400
        fr = np.fft.irfft(spec, n=n_fft, axis=0) * self.window[:, None]
        T = spec.shape[1]
        out = (T - 1) * hop + win
        idx = (np.arange(T)[:, None] * hop + np.arange(win)[None, :]).reshape(-1)
        y = np.bincount(idx, weights=fr.T.reshape(-1), minlength=out)
        env = np.bincount(idx, weights=np.tile(self.window ** 2, T), minlength=out)
        pad = (win - hop) // 2
        return (y[pad:-pad] / np.maximum(env[pad:-pad], 1e-11)).astype(np.float32)

    def ids(self, stressed_text):
        seq = '|' + stressed_text + '~'
        return np.array([[SYM2ID[c] for c in seq if c in SYM2ID]], np.int64)

    def synth(self, stressed_text, voice, rate=1.0, pitch=1.0, pitch_range=1.0,
              rate_curve=None, pitch_curve=None, return_mel=False, durs_out=None):
        """stressed_text: cleaned lower-case text with '+' stress marks.
        rate: >1 faster.  pitch: f0 multiplier.  pitch_range: intonation depth.
        rate_curve / pitch_curve: optional per-symbol multipliers (len == len(text)+2).
        durs_out: optional list; gets the frames per symbol of '|' + text + '~' (one frame = HOP samples).
        Shorts uses it for exact word timings (subtitles)."""
        self.ensure()
        seq = self.ids(stressed_text)
        T = seq.shape[1]
        r = np.full((1, T), rate, np.float32)
        c = np.full((1, T), pitch, np.float32)
        if rate_curve is not None:
            r = r * np.asarray(rate_curve, np.float32)[None, :T]
        if pitch_curve is not None:
            c = c * np.asarray(pitch_curve, np.float32)[None, :T]
        logdur, pit = self.S['pred'].run(None, {'seq': seq, 'spk_dur': voice['d'], 'spk_pitch': voice['p']})
        dur = self._post_durs(logdur, r)
        pit = self._upd_pitch(pit, c, voice['msc'],
                              None if pitch_range == 1.0 else pitch_range).astype(np.float32)
        cond = self.S['enc'].run(None, {'seq': seq, 'spk': voice['t'], 'pitch': pit})[0]
        reps = (dur[0] + 0.5).astype(np.int64)
        if durs_out is not None:
            durs_out.append(reps.copy())
        x = np.repeat(cond[0], reps, axis=0)[None].astype(np.float32)
        L = x.shape[1]
        if L == 0:
            return np.zeros(0, np.float32)
        a = self.S['dec_a'].run(None, {'x': x})[0]
        a = np.pad(a, ((0, 0), (0, (-L) % 3), (0, 0)))
        b = self.S['dec_b'].run(None, {'x': a})[0][:, :L]
        mel = self.S['dec_c'].run(None, {'x': np.ascontiguousarray(b)})[0]
        if return_mel:
            return mel
        return self.vocode(mel)

    def vocode(self, mel):
        self.ensure()
        re_, im_ = self.S['voc'].run(None, {'mel': mel.astype(np.float32)})
        return self._istft(re_[0], im_[0])
