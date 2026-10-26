# -*- coding: utf-8 -*-
"""Russian stress + 'ё' restoration, numpy only.

Faithful numpy port of silero-stress v1.5 (MIT License, (c) Silero Team):
  * AccentorNgram  - fastText-like n-gram word accentor (stress + ё);
  * HomoSolver     - small BERT (rubert-tiny style, 3 layers) that picks the
                     right variant of homographs from context (зАмок/замОк,
                     все/всё, стОит/стоИт ...).
Output uses Silero TTS notation: '+' before the stressed vowel.
Words that already contain '+' (or 'ё') are respected.
"""
import gzip
import json
import os
import re
import threading

import numpy as np

from .bert_tokenizer import SimpleBertTokenizer

VOWELS = 'аоуыэиеяёю'


# ----------------------------------------------------------------------------------
# small numpy helpers
def _softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def _erf(x):
    # Abramowitz-Stegun 7.1.26 (|err| < 1.5e-7)
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-a * a)
    return s * y


def _gelu(x):
    return 0.5 * x * (1.0 + _erf(x * 0.7071067811865476))


def _layernorm(x, w, b, eps=1e-12):
    m = x.mean(-1, keepdims=True)
    v = ((x - m) ** 2).mean(-1, keepdims=True)
    return (x - m) / np.sqrt(v + eps) * w + b


# ----------------------------------------------------------------------------------
class AccentorNgram:
    def __init__(self, folder):
        f = lambda n: os.path.join(folder, n)
        z = np.load(f('accentor.npz'))
        self.emb = ((z['emb_q'].astype(np.float32) - z['emb_zp'][0]) * z['emb_scale'][0]).astype(np.float32)
        self.stress_w = [(z['stress_clf.%d.weight' % i], z['stress_clf.%d.bias' % i]) for i in (0, 2, 4, 6)]
        self.yo_w = [(z['yo_clf.%d.weight' % i], z['yo_clf.%d.bias' % i]) for i in (0, 2, 4, 6)]
        with gzip.open(f('ngrams.txt.gz'), 'rt', encoding='utf-8') as fh:
            self.ngram = {g: i for i, g in enumerate(fh.read().split('\n'))}
        self.unk = self.ngram['UNK']
        self.exceptions = {}
        with gzip.open(f('exceptions.txt.gz'), 'rt', encoding='utf-8') as fh:
            for line in fh:
                p = line.split()
                if len(p) == 3:
                    self.exceptions[p[0]] = (int(p[1]), int(p[2]))
        self.stress_token = '+'
        self.re_cond = re.compile(r'[^А-Яа-яёЁ]')
        self.re_split = re.compile(r'([\s.,!?;:<>=()/\\]+)')
        self.vowels = VOWELS

    # --- model -------------------------------------------------------------------
    def _embed(self, words):
        out = np.zeros((len(words), self.emb.shape[1]), np.float32)
        ng = self.ngram
        for k, w in enumerate(words):
            t = '<' + w + '>'
            ids = []
            for n in range(1, len(w) + 4):
                for j in range(len(t) - n + 1):
                    g = t[j:j + n]
                    if g in ng:
                        ids.append(ng[g])
            if not ids:
                ids = [self.unk]
            out[k] = self.emb[ids].mean(axis=0)
        return out

    @staticmethod
    def _mlp(x, layers):
        for i, (w, b) in enumerate(layers):
            x = x @ w.T + b
            if i < len(layers) - 1:
                x = np.maximum(x, 0)
        return x

    def _get_model_preds(self, words):
        e = self._embed(words)
        sp = _softmax(self._mlp(e, self.stress_w), 1)
        yp = _softmax(self._mlp(e, self.yo_w), 1)
        return sp, sp.argmax(1), yp, yp.argmax(1)

    # --- port of AccentorNgram.__call__ -----------------------------------------
    def __call__(self, sentence, put_stress=True, put_yo=True, stress_single_vowel=True,
                 skip_stress_words=None, skip_yo_words=None, words_to_ignore=None):
        skip_stress_words = skip_stress_words or ()
        skip_yo_words = skip_yo_words or ()
        if not (put_stress or put_yo):
            return sentence
        raw_tokens, clean_tokens, mask = self._tokenize(sentence, words_to_ignore)
        if not raw_tokens:
            return sentence
        stress_probs, stress_preds, yo_probs, yo_preds = self._get_model_preds(clean_tokens)
        st = self.stress_token
        out = []
        for wi, (raw_word, clean_word, need) in enumerate(zip(raw_tokens, clean_tokens, mask)):
            low = raw_word.lower()
            if not need:
                out.append(raw_word); continue
            have_stress = st in low
            have_yo = 'ё' in low
            if have_stress and have_yo:
                out.append(raw_word); continue
            if (not have_stress) and have_yo and put_stress:
                if (sum(c in self.vowels for c in low) == 1 and not stress_single_vowel) or \
                        clean_word.replace('ё', 'е') in skip_stress_words:
                    out.append(raw_word); continue
                pos = [i for i, x in enumerate(low) if x == 'ё']
                for i, p in enumerate(pos):
                    raw_word = raw_word[:p + i] + st + raw_word[p + i:]
                out.append(raw_word); continue
            if clean_word in self.exceptions:
                out.append(self._accentuate_exception(clean_word, raw_word, have_stress)); continue
            sv = [int(stress_preds[wi])]
            passed = stress_probs[wi][sv[0]] > (0.5 if put_stress else 1)
            set_stress = passed and not have_stress and (clean_word.replace('ё', 'е') not in skip_stress_words)
            yv = [int(yo_preds[wi])]
            passed_yo = yo_probs[wi][yv[0]] > (0.5 if put_yo else 1)
            set_yo = passed_yo and (clean_word.replace('ё', 'е') not in skip_yo_words)
            if have_stress:
                sv = [sum(map(part.count, self.vowels)) for part in low.split(st)]
            stress_pos, yo_pos, nv, first_v = self._get_positions(low, sv, yv)
            if nv == 0:
                out.append(raw_word); continue
            for yp in yo_pos:
                if yp in stress_pos and set_yo and low[yp] == 'е':
                    raw_word = raw_word[:yp] + ('ё' if raw_word[yp].islower() else 'Ё') + raw_word[yp + 1:]
            if nv == 1:
                stress_pos = [first_v]
                set_stress = stress_single_vowel and put_stress
            if (not have_stress) and set_stress:
                for i, p in enumerate(stress_pos):
                    raw_word = raw_word[:p + i] + st + raw_word[p + i:]
            out.append(raw_word)
        return ''.join(out)

    def _get_positions(self, word, sv, yv):
        vowel_ids = [i for i, c in enumerate(word) if c in self.vowels]
        ye_ids = [i for i, c in enumerate(word) if c == 'е']
        stress_pos = [vowel_ids[i] for i in sv if i < len(vowel_ids) and vowel_ids]
        yo_pos = [ye_ids[i - 1] for i in yv if i > 0 and i - 1 < len(ye_ids) and ye_ids]
        return stress_pos, yo_pos, len(vowel_ids), (vowel_ids[0] if vowel_ids else -1)

    def _accentuate_exception(self, clean_word, raw_word, have_stress):
        es, ey = self.exceptions[clean_word]
        st = self.stress_token
        if have_stress:
            tpos = [i for i, c in enumerate(raw_word) if c == st]
            w = raw_word.replace(st, '')
            if ey != -1 and (ey + 1 in tpos) and ey < len(w):
                w = w[:ey] + ('ё' if w[ey].islower() else 'Ё') + w[ey + 1:]
            for p in tpos:
                w = w[:p] + st + w[p:]
            return w
        if ey != -1 and ey < len(raw_word):
            raw_word = raw_word[:ey] + ('ё' if raw_word[ey].islower() else 'Ё') + raw_word[ey + 1:]
        return raw_word[:es] + st + raw_word[es:]

    def _tokenize(self, sentence, words_to_ignore=None):
        words_to_ignore = words_to_ignore or ()
        tokens, inputs, mask = [], [], []
        for word in self.re_split.split(sentence):
            parts = word.split('-')
            if len(parts) == 1:
                cur, cm = parts, [True]
            else:
                cur = [p + '-' for p in parts[:-1]] + [parts[-1]]
                cm = [True] * (len(parts) - 1) + [parts[-1] != 'то']
            ci = [self.re_cond.sub('', t.lower()) for t in cur]
            cm = [(len(x) > 0 and x not in words_to_ignore) and m for x, m in zip(ci, cm)]
            tokens += cur; inputs += ci; mask += cm
        return tokens, inputs, mask


# ----------------------------------------------------------------------------------
def _capitalize_stress(w):
    i = w.index('+')
    return w[:i] + w[i + 1].capitalize() + w[i + 2:]


def _decapitalize_stress(w):
    for i, c in enumerate(w):
        if c.isupper():
            return w[:i] + '+' + w[i:].lower()


class HomoSolver:
    def __init__(self, folder):
        f = lambda n: os.path.join(folder, n)
        with gzip.open(f('vocab.txt.gz'), 'rt', encoding='utf-8') as fh:
            vocab = fh.read().split('\n')
        if vocab and vocab[-1] == '':
            vocab = vocab[:-1]
        cfg = json.load(open(f('tokenizer.json'), encoding='utf-8'))
        self.tokenizer = SimpleBertTokenizer(vocab, cfg)
        with gzip.open(f('homodict.json.gz'), 'rt', encoding='utf-8') as fh:
            self.homodict = json.load(fh)
        self.yohomodict = {w: v for w, v in self.homodict.items() if any('ё' in x for x in v)}
        with gzip.open(f('phrases.json.gz'), 'rt', encoding='utf-8') as fh:
            pats = json.load(fh)
        self._phrase_src = pats
        self._phrase_cache = {}
        self.compiled_user_phrases = {}
        self.compiled_user_patterns = {}
        self.pattern = re.compile(r'(?=.*[а-яё])[а-яё+]+', re.IGNORECASE)
        self.vowels = VOWELS
        self._re_remove_extra = re.compile(r'[^a-zA-Zа-яА-ЯёЁ0-9\s.!?,\-]')
        self._re_spaces = re.compile(r'\s+')
        self._re_double_dash = re.compile(r'-{2,}')
        self._re_repeat_punct = re.compile(r'([.!?])\1+')
        self._re_repeat_comma = re.compile(r',{2,}')
        self._re_space_before_punct = re.compile(r'\s+([.,!?])')
        self._re_punct_add_space = re.compile(r'([.,!?])(?=\S)')
        self.window_size = cfg.get('window_size', 300)
        z = np.load(f('homo_bert.npz'))
        g = lambda k: z[k].astype(np.float32)
        self.word_q = z['word_q']
        self.word_scale = float(z['word_scale'][0]); self.word_zp = float(z['word_zp'][0])
        self.pos = g('bert.embeddings.position_embeddings.weight')
        self.tt = g('bert.embeddings.token_type_embeddings.weight')
        self.eln = (g('bert.embeddings.LayerNorm.weight'), g('bert.embeddings.LayerNorm.bias'))
        self.layers = []
        i = 0
        while 'bert.encoder.layer.%d.attention.self.query.weight' % i in z:
            p = 'bert.encoder.layer.%d.' % i
            L = {k: g(p + k) for k in [
                'attention.self.query.weight', 'attention.self.query.bias',
                'attention.self.key.weight', 'attention.self.key.bias',
                'attention.self.value.weight', 'attention.self.value.bias',
                'attention.output.dense.weight', 'attention.output.dense.bias',
                'attention.output.LayerNorm.weight', 'attention.output.LayerNorm.bias',
                'intermediate.dense.weight', 'intermediate.dense.bias',
                'output.dense.weight', 'output.dense.bias',
                'output.LayerNorm.weight', 'output.LayerNorm.bias']}
            # fused qkv
            L['qkv_w'] = np.concatenate([L['attention.self.query.weight'], L['attention.self.key.weight'],
                                         L['attention.self.value.weight']], 0).T.copy()
            L['qkv_b'] = np.concatenate([L['attention.self.query.bias'], L['attention.self.key.bias'],
                                         L['attention.self.value.bias']])
            self.layers.append(L)
            i += 1
        self.clf = [(g('homo_clf.0.weight'), g('homo_clf.0.bias')), (g('homo_clf.3.weight'), g('homo_clf.3.bias'))]
        self.n_heads = 12

    def _phrase(self, word):
        if word not in self._phrase_src:
            return None
        p = self._phrase_cache.get(word)
        if p is None:
            p = re.compile(self._phrase_src[word], re.IGNORECASE)
            self._phrase_cache[word] = p
        return p

    # --- BERT forward ----------------------------------------------------------
    def _bert(self, ids):
        B, T = ids.shape
        x = (self.word_q[ids].astype(np.float32) - self.word_zp) * self.word_scale
        x = x + self.tt[0] + self.pos[:T][None]
        x = _layernorm(x, *self.eln)
        H = self.n_heads
        D = x.shape[-1] // H
        for L in self.layers:
            qkv = x @ L['qkv_w'] + L['qkv_b']
            q, k, v = np.split(qkv, 3, axis=-1)
            q = q.reshape(B, T, H, D).transpose(0, 2, 1, 3)
            k = k.reshape(B, T, H, D).transpose(0, 2, 3, 1)
            v = v.reshape(B, T, H, D).transpose(0, 2, 1, 3)
            a = _softmax((q @ k) / np.sqrt(np.float32(D)), -1)
            ctx = (a @ v).transpose(0, 2, 1, 3).reshape(B, T, H * D)
            h = ctx @ L['attention.output.dense.weight'].T + L['attention.output.dense.bias']
            x = _layernorm(h + x, L['attention.output.LayerNorm.weight'], L['attention.output.LayerNorm.bias'])
            h = _gelu(x @ L['intermediate.dense.weight'].T + L['intermediate.dense.bias'])
            h = h @ L['output.dense.weight'].T + L['output.dense.bias']
            x = _layernorm(h + x, L['output.LayerNorm.weight'], L['output.LayerNorm.bias'])
        return x

    def _predict(self, seqs):
        pad = self.tokenizer.pad_token_id
        T = max(len(s) for s in seqs)
        ids = np.full((len(seqs), T), pad, np.int64)
        for i, s in enumerate(seqs):
            ids[i, :len(s)] = s
        hid = self._bert(ids)
        feats = []
        for i, s in enumerate(seqs):
            st = s.index(self.tokenizer.homo_start_id)
            en = s.index(self.tokenizer.homo_end_id)
            marker = hid[i, st]
            seg = hid[i, st + 1:en]
            word = seg.mean(0) if len(seg) else np.full_like(marker, np.nan)
            feats.append(np.concatenate([marker, word]))
        f = np.stack(feats)
        (w0, b0), (w1, b1) = self.clf
        logit = np.maximum(f @ w0.T + b0, 0) @ w1.T + b1
        return (logit[:, 0] > 0).astype(int)

    # --- port of HomoSolver.__call__ -----------------------------------------------
    def __call__(self, sentence, put_stress=True, put_yo=True, stress_single_vowel=True, words_to_ignore=None):
        if not (put_stress or put_yo):
            return sentence
        tagged = self._find_and_tag_homos(sentence, words_to_ignore)
        starts, ends, words, regex_preds, is_neural, seqs = [], [], [], [], [], []
        for start, end, word, wl, raw_mark, raw_clean in tagged:
            if raw_mark is None:
                continue
            rp = None
            if wl in self.compiled_user_patterns:
                rp = self._predict_with_pattern(self.compiled_user_patterns[wl], raw_clean)
            if rp is None and wl in self.compiled_user_phrases:
                rp = self._predict_with_pattern(self.compiled_user_phrases[wl], raw_mark)
            if rp is None:
                pp = self._phrase(wl)
                if pp is not None:
                    rp = self._predict_with_pattern(pp, raw_mark)
            if rp is not None:
                regex_preds.append(rp)
            else:
                if wl not in self.homodict:
                    continue
                seqs.append(self.tokenizer(raw_mark))
            starts.append(start); ends.append(end); words.append(word); is_neural.append(rp is None)
        if not words:
            return sentence
        preds = self._predict(seqs) if seqs else []
        ri = hi = 0
        word_preds = []
        for word, neu in zip(words, is_neural):
            if neu:
                word_preds.append(sorted(self.homodict[word.lower()])[int(preds[hi])]); hi += 1
            else:
                word_preds.append(regex_preds[ri]); ri += 1
        s = sentence
        off = 0
        for start, end, word, wp in zip(starts, ends, words, word_preds):
            start += off; end += off
            wp = wp if put_yo else wp.replace('ё', 'е')
            nv = sum(c.lower() in self.vowels for c in wp)
            si = wp.index('+')
            wp = wp.replace('+', '')
            wp = ''.join([c2.lower() if c1.islower() else c2.upper() for c1, c2 in zip(word, wp)])
            if (nv > 1 or stress_single_vowel) and put_stress:
                wp = wp[:si] + '+' + wp[si:]
                off += 1
            s = s[:start] + wp + s[end:]
        return s

    def _predict_with_pattern(self, pattern, text):
        m = pattern.search(text)
        if m:
            for name, txt in m.groupdict().items():
                if txt is not None:
                    return _decapitalize_stress(name)
        return None

    def _find_and_tag_homos(self, sentence, words_to_ignore=None):
        words_to_ignore = words_to_ignore or ()
        out = []
        half = self.window_size // 2
        for m in self.pattern.finditer(sentence):
            start, end = m.span()
            word = m.group()
            wl = word.lower()
            is_h = ((wl in self.homodict) or (wl in self._phrase_src) or (wl in self.compiled_user_phrases)
                    or (wl in self.compiled_user_patterns)) and (wl not in words_to_ignore)
            if is_h:
                a = self._clean_text(sentence[:start], True)[-half:]
                b = self._clean_text(sentence[end:], False)[:half]
                raw_mark = (a + ' [HOMO] ' + wl + ' [/HOMO] ' + b).strip()
                raw_clean = (a + ' ' + wl + ' ' + b).strip()
            else:
                raw_mark = raw_clean = None
            out.append((start, end, word, wl, raw_mark, raw_clean))
        return out

    def _clean_text(self, text, is_start=True):
        if not text:
            return ''
        text = self._re_remove_extra.sub('', text)
        text = self._re_spaces.sub(' ', text)
        text = self._re_double_dash.sub(' - ', text)
        text = self._re_repeat_punct.sub(r'\1', text)
        text = self._re_repeat_comma.sub(',', text)
        text = self._re_space_before_punct.sub(r'\1', text)
        text = self._re_repeat_punct.sub(r'\1', text)
        text = self._re_repeat_comma.sub(',', text)
        text = self._re_punct_add_space.sub(r'\1 ', text)
        text = self._re_spaces.sub(' ', text).strip()
        if is_start:
            text = text.lstrip(' .,!?-')
            if text:
                text = text[0].upper() + text[1:].lower()
        else:
            if text:
                text = text[0] + text[1:].lower()
            if text and text[-1] not in '.!?':
                text += '.'
        return text

    def load_phrases_dict(self, path):
        """User phrases JSON: {"замок": {"старинный замок": "з+амок", "закрыто на замок": "зам+ок"}}"""
        data = json.load(open(path, encoding='utf-8'))
        comp = {}
        for word, ph2v in data.items():
            v2p = {}
            for ph, v in ph2v.items():
                v2p.setdefault(v, []).append(ph)
            vp = []
            for v, phs in v2p.items():
                phs = sorted(phs, key=len, reverse=True)
                phs = [p.replace(word, f'[HOMO] {word} [/HOMO]').strip() for p in phs]
                vp.append(rf'(?P<{_capitalize_stress(v)}>(?<![а-яА-ЯёЁ\-])(?:{"|".join(map(re.escape, phs))})(?![а-яА-ЯёЁ\-]))')
            comp[word] = re.compile('|'.join(vp), re.IGNORECASE)
        self.compiled_user_phrases.update(comp)


# ----------------------------------------------------------------------------------
class RuStress:
    """accent = RuStress(folder); accent('Всё хорошо, замок закрыт на замок.')"""

    def __init__(self, folder):
        self.folder = folder
        self._lock = threading.Lock()
        self.accentor = None
        self.homosolver = None
        self.user = {}

    def ensure(self):
        if self.accentor is None:
            with self._lock:
                if self.accentor is None:
                    self.homosolver = HomoSolver(self.folder)
                    self.accentor = AccentorNgram(self.folder)
                    p = os.path.join(self.folder, 'user_stress.txt')
                    if os.path.exists(p):
                        self.add_user_dict(p)

    def add_user_dict(self, path):
        """Text file, one word per line with '+' before the stressed vowel, e.g. 'Б+орис'.
        Such words are always pronounced exactly as written."""
        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.split('#')[0].strip()
                if line and '+' in line:
                    for w in line.split():
                        if '+' in w:
                            self.user[w.replace('+', '').lower()] = w.lower()

    def _apply_user(self, text):
        if not self.user:
            return text

        def rep(m):
            w = m.group(0)
            f = self.user.get(w.lower())
            if f is None:
                return w
            out, j = [], 0
            for ch in f:
                if ch == '+':
                    out.append('+'); continue
                o = w[j] if j < len(w) else ch
                out.append(ch.upper() if o.isupper() else ch); j += 1
            return ''.join(out)
        return re.sub(r'(?<![+а-яА-ЯёЁ])[а-яА-ЯёЁ]+(?![+а-яА-ЯёЁ])', rep, text)

    def __call__(self, text, stress_single_vowel=True):
        self.ensure()
        text = self._apply_user(text)
        text = self.homosolver(text, stress_single_vowel=stress_single_vowel)
        return self.accentor(text, stress_single_vowel=stress_single_vowel)
