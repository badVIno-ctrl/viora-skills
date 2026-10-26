# -*- coding: utf-8 -*-
"""English acoustic model: Kokoro-82M v1.0 (Apache-2.0, (c) hexgrad), int8 ONNX
with two extra inputs added by this package: f0_scale (pitch multiplier) and
f0_range (intonation depth).  Phonemes come from bundled espeak-ng.
numpy + onnxruntime only.  Output: 24 kHz float32."""
import json
import os
import re
import threading

import numpy as np

from .espeak_ipa import EspeakIPA

SR = 24000
# punctuation splits phonemizer chunks; '.' and ',' between digits stay inside numbers (3.5, 1,000)
_SPLIT = re.compile(r'((?:[;:!?¡¿—…"«»“”()\[\]{}]|[.,](?!\d)|(?<!\d)[.,])+)')
_ACCENTS = {'en-gb': 'en', 'en-uk': 'en', 'gb': 'en', 'uk': 'en', 'british': 'en', 'en': 'en',
            'en-us': 'en-us', 'us': 'en-us', 'american': 'en-us'}


class KokoroEN:
    def __init__(self, model_dir, threads=None):
        self.dir = model_dir
        self.threads = threads or min(4, os.cpu_count() or 2)
        with open(os.path.join(model_dir, 'kokoro_vocab.json'), encoding='utf-8') as fh:
            self.vocab = json.load(fh)
        Z = np.load(os.path.join(model_dir, 'kokoro_voices_en.npz'))
        self.base = {k: Z[k].astype(np.float32) for k in Z.files}   # name -> [510, 256]
        self.names = sorted(self.base)
        self.sess = None
        self.esp = None
        self._lock = threading.Lock()

    def ensure(self):
        if self.sess is None:
            with self._lock:
                if self.sess is None:
                    import onnxruntime as ort
                    so = ort.SessionOptions()
                    so.intra_op_num_threads = self.threads
                    so.inter_op_num_threads = 1
                    so.log_severity_level = 3
                    self.sess = ort.InferenceSession(
                        os.path.join(self.dir, 'kokoro-v1.0.int8.f0.onnx'), so,
                        providers=['CPUExecutionProvider'])
        if self.esp is None:
            self.esp = EspeakIPA(os.path.join(self.dir, 'espeak'), 'en-us')

    # ------------------------------------------------------------------ voices
    def voice(self, mix):
        """mix: 'af_heart' or {'af_heart': 0.6, 'af_bella': 0.4} -> style table [510, 256]."""
        if isinstance(mix, str):
            mix = {mix: 1.0}
        tot = float(sum(mix.values()))
        v = None
        for n, a in mix.items():
            if n not in self.base:
                raise ValueError('unknown English base voice %s' % n)
            t = self.base[n] * (float(a) / tot)
            v = t if v is None else v + t
        return v

    # ------------------------------------------------------------------ text
    def phonemize(self, text, accent='en-us'):
        self.ensure()
        accent = _ACCENTS.get(str(accent).lower(), 'en-us')
        text = text.replace('\n', ' ').strip()
        out = []
        for part in _SPLIT.split(text):
            if not part:
                continue
            if _SPLIT.fullmatch(part):
                p = re.sub(r'[()\[\]{}]', ',', part)
                out.append(p + ' ')
            elif part.strip():
                out.append(self.esp.phonemize_chunk(part, accent) + ' ')
        ph = ''.join(out)
        ph = re.sub(r'\s+([;:,.!?…])', r'\1', ph)
        ph = re.sub(r',+\s*([;:.!?…])', r'\1', ph)      # "(word)." -> "word."
        ph = re.sub(r'(,\s*)+,', ',', ph)
        ph = re.sub(r'^[\s,]+', '', ph)
        ph = re.sub(r'\s+', ' ', ph).strip()
        return ''.join(c for c in ph if c in self.vocab)

    def _split_long(self, ph, limit=500):
        if len(ph) <= limit:
            return [ph]
        parts, cur = [], ''
        for tok in re.split(r'(?<=[,;:.!?…])\s+', ph):
            if len(cur) + len(tok) + 1 > limit and cur:
                parts.append(cur)
                cur = tok
            else:
                cur = (cur + ' ' + tok).strip()
        if cur:
            parts.append(cur)
        res = []
        for p in parts:
            while len(p) > limit:
                cut = p.rfind(' ', 0, limit)
                cut = cut if cut > 50 else limit
                res.append(p[:cut]); p = p[cut:].strip()
            if p:
                res.append(p)
        return res

    # ------------------------------------------------------------------ synthesis
    def synth_phonemes(self, ph, voice, speed=1.0, pitch=1.0, pitch_range=1.0):
        self.ensure()
        chunks = self._split_long(ph)
        outs = []
        for ch in chunks:
            ids = [self.vocab[c] for c in ch if c in self.vocab]
            if not ids:
                continue
            style = voice[min(len(ids) - 1, len(voice) - 1)][None, :].astype(np.float32)
            feed = {'tokens': np.array([[0] + ids + [0]], np.int64), 'style': style,
                    'speed': np.array([speed], np.float32),
                    'f0_scale': np.array([pitch], np.float32),
                    'f0_range': np.array([pitch_range], np.float32)}
            outs.append(self.sess.run(None, feed)[0].astype(np.float32).reshape(-1))
        if not outs:
            return np.zeros(0, np.float32)
        return np.concatenate(outs)

    def synth(self, text, voice, speed=1.0, pitch=1.0, pitch_range=1.0, accent='en-us'):
        return self.synth_phonemes(self.phonemize(text, accent), voice, speed, pitch, pitch_range)
