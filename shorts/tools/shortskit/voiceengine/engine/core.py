# -*- coding: utf-8 -*-
"""VoiceEngine core: any text -> speech with any age / gender / character (Russian + English), offline.

    from engine.core import Engine
    eng = Engine()
    audio = eng.say('Привет!', gender='female', age=90)        # float32 numpy array, eng.sr Hz
    eng.save('Привет!', 'out.wav', gender='female', age=90)
    eng.save_script(open('dialog.txt').read(), 'dialog.wav')
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import wave

import numpy as np

from . import dsp
from .characters import PRESETS, EMOTIONS, EFFECTS, preset_name, emotion_name, effect_name, apply_effect
from .script import load_script, parse_attrs, parse_gender, guess_from_name, PAUSE_RE
from .voices import (BANK, RU_POOL, EN_POOL, RU_KID, EN_KID, RU_YOUNG, RU_ELDER, EN_YOUNG, EN_ELDER,
                     age_profile, identity, blend)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
FX_ORDER = {'whisper': 0, 'robot': 1, 'growl': 1, 'alien': 1, 'crackle': 1, 'phone': 2, 'radio': 2,
            'oldradio': 2, 'megaphone': 2, 'underwater': 2, 'radio_noise': 2, 'room': 3, 'hall': 3, 'cave': 3,
            'echo': 4, 'ghost': 4}
PAUSES = {'.': 0.38, '?': 0.42, '!': 0.40, '…': 0.60, ':': 0.30, ';': 0.30, ',': 0.20, '': 0.30}
PARAGRAPH_PAUSE = 0.75
TURN_PAUSE = 0.30

# ----------------------------------------------------------------------------- text helpers
_CYR = re.compile(r'[А-Яа-яЁё]')
_LAT = re.compile(r'[A-Za-z]')
_SENT_END = re.compile(r'([.!?…]+[»"”)\]]*)(\s+)(?=[«"„“(\[—–-]?\s*[A-ZА-ЯЁ0-9])')
_INITIAL = re.compile(r'(?:^|[\s(«"])[A-ZА-ЯЁ]\.$')
_ABBR_END = re.compile(
    r'(?:^|[\s(«"])(?:т\.\s?[екдпн]|н\.\s?э|др|пр|см|ср|г|гг|ул|д|кв|корп|стр|им|проф|акад|доц|тыс|млн|млрд|руб|'
    r'коп|рис|гл|ст|пер|пл|обл|напр|англ|рус|лат|вв|Mr|Mrs|Ms|Dr|Prof|St|Jr|Sr|vs|etc|e\.\s?g|i\.\s?e|No|'
    r'approx|Dept|Mt|Ave|Inc|Ltd|Co|Corp|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.$', re.I)


def _join_lines(par):
    """Single line breaks: a sentence boundary if the next line starts like a sentence, else a space."""
    lines = [ln.strip() for ln in par.split('\n') if ln.strip()]
    out = ''
    for ln in lines:
        if not out:
            out = ln
        elif re.search(r'[.!?…:;,]["»”)\]]*$', out):
            out += ' ' + ln
        elif re.match(r'[«"„“(\[—–-]?\s*[A-ZА-ЯЁ0-9]', ln):
            out += '. ' + ln
        else:
            out += ' ' + ln
    return out


def split_sentences(text):
    parts, last = [], 0
    for m in _SENT_END.finditer(text):
        left = text[last:m.end(1)]
        if m.group(1) == '.' and (_INITIAL.search(left) or _ABBR_END.search(left)):
            continue
        parts.append(left.strip())
        last = m.end()
    tail = text[last:].strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if re.search(r'\w', p)]


def split_pauses(text):
    """'a [пауза 2] b' -> ['a', 2.0, 'b']"""
    out, last = [], 0
    for m in PAUSE_RE.finditer(text):
        if text[last:m.start()].strip():
            out.append(text[last:m.start()])
        if m.group(1):
            sec = float(m.group(1).replace(',', '.'))
        elif m.group(2):
            sec = float(m.group(2)) / (1000.0 if (m.group(3) or 's') == 'ms' else 1.0)
        else:
            sec = 0.8
        out.append(sec)
        last = m.end()
    if text[last:].strip():
        out.append(text[last:])
    return out


def detect_lang(s, forced=None):
    if forced == 'ru':
        return 'ru'
    if forced == 'en':                       # the English model cannot read Cyrillic
        return 'ru' if _CYR.search(s) and not _LAT.search(s) else 'en'
    if _CYR.search(s):
        return 'ru'
    if _LAT.search(s):
        return 'en'
    return None


def _ending(s):
    s = re.sub(r'[\s»"”)\]]+$', '', s)
    if s.endswith('...') or s.endswith('…'):
        return '…'
    if re.search(r'[?][!?.]*$', s) or re.search(r'![?]+$', s):
        return '?'
    if s.endswith('!'):
        return '!'
    return s[-1:] if s[-1:] in PAUSES else ''


def _chunks(t, limit=240):
    if len(t) <= limit:
        return [t]
    parts = re.split(r'(?<=[,;:])\s+', t)
    out, cur = [], ''
    for p in parts:
        if cur and len(cur) + 1 + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur = (cur + ' ' + p).strip()
    if cur:
        out.append(cur)
    res = []
    for c in out:
        while len(c) > limit:
            k = c.rfind(' ', 0, limit)
            k = k if k > 40 else limit
            res.append(c[:k].rstrip(' ,') + ',')
            c = c[k:].strip()
        if c:
            res.append(c)
    return res


HOP = 600                                   # Silero vocoder hop at 48 kHz (12.5 ms per duration frame)
_WORD_CORE = re.compile(r"[\w+](?:[\w+'-]*[\w+])?")


def ru_word_frames(ch, reps):
    """Words of a prepared chunk -> [(word, first_frame, end_frame)] from the per-symbol durations of
    '|' + ch + '~' (characters the model does not know are skipped, like SileroRU.ids())."""
    from .silero_ru import SYM2ID
    seq = '|' + ch + '~'
    idx, k = [], 0
    for c in seq:
        if c in SYM2ID:
            idx.append(k)
            k += 1
        else:
            idx.append(None)
    reps = np.asarray(reps).reshape(-1)
    if len(reps) != k:
        return []
    cum = np.concatenate([[0], np.cumsum(reps)])
    out = []
    for m in re.finditer(r'\S+', ch):
        core = _WORD_CORE.search(m.group(0))
        if not core or not re.search(r'[^\W\d_]', core.group(0)):
            continue
        c0 = 1 + m.start() + core.start()
        c1 = 1 + m.start() + core.end() - 1
        i0 = next((idx[j] for j in range(c0, c1 + 1) if idx[j] is not None), None)
        i1 = next((idx[j] for j in range(c1, c0 - 1, -1) if idx[j] is not None), None)
        if i0 is None or i1 is None:
            continue
        out.append((core.group(0).replace('+', ''), int(cum[i0]), int(cum[i1 + 1])))
    return out


def _seed(*parts):
    return int(hashlib.sha1('|'.join(str(p) for p in parts).encode('utf-8')).hexdigest()[:8], 16) % 100000


def _f(v, default=None):
    if v is None or v == '':
        return default
    return float(str(v).replace(',', '.'))


def silence(sec, sr=SR):
    return np.zeros(int(max(0.0, sec) * sr), np.float32)


# ----------------------------------------------------------------------------- audio files
def _write_wav(path, x, sr):
    y = (np.clip(np.asarray(x, np.float32), -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(y.tobytes())


def write_audio(path, x, sr=SR, out_sr=None):
    """WAV natively; mp3 / ogg / opus / flac / m4a through ffmpeg (if installed). Returns the written path."""
    x = np.asarray(x, np.float32)
    if len(x) == 0:
        x = silence(0.1, sr)
    if out_sr and int(out_sr) != sr:
        x = dsp.resample(x, sr, int(out_sr))
        sr = int(out_sr)
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    ext = os.path.splitext(path)[1].lower()
    if ext in ('', '.wav', '.wave'):
        _write_wav(path, x, sr)
        return path
    ff = shutil.which('ffmpeg')
    if not ff:
        alt = os.path.splitext(path)[0] + '.wav'
        _write_wav(alt, x, sr)
        print('[voice_engine] ffmpeg not found -> saved WAV instead: %s' % alt)
        return alt
    fd, tmp = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        _write_wav(tmp, x, sr)
        codec = {'.mp3': ['-codec:a', 'libmp3lame', '-q:a', '2'], '.ogg': ['-codec:a', 'libvorbis', '-q:a', '6'],
                 '.opus': ['-codec:a', 'libopus', '-b:a', '64k'], '.m4a': ['-codec:a', 'aac', '-b:a', '160k'],
                 '.aac': ['-codec:a', 'aac', '-b:a', '160k']}.get(ext, [])
        r = subprocess.run([ff, '-y', '-loglevel', 'error', '-i', tmp] + codec + [path], capture_output=True)
        if r.returncode != 0:
            subprocess.run([ff, '-y', '-loglevel', 'error', '-i', tmp, path], check=True, capture_output=True)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


# ----------------------------------------------------------------------------- engine
class Engine:
    def __init__(self, models_dir=None, threads=None, user_dicts=None):
        self.models = models_dir or os.path.join(ROOT, 'models')
        self.threads = threads
        # stress dictionaries: one word per line, З+амок (Shorts adds memory/stress.txt of the user)
        self.user_dicts = list(user_dicts) if user_dicts is not None else [os.path.join(ROOT, 'user_stress.txt')]
        self.sr = SR
        self._lock = threading.RLock()
        self._ru = self._en = self._stress = self._norm = self._esp = None
        self._vcache = {}
        self.f0 = {}
        with open(os.path.join(self.models, 'ru', 'speaker_f0.json'), encoding='utf-8') as fh:
            self.f0['ru'] = json.load(fh)
        with open(os.path.join(self.models, 'en', 'voice_f0.json'), encoding='utf-8') as fh:
            self.f0['en'] = json.load(fh)
        self.pool_f0 = {}
        for lang, pools, kid in (('ru', RU_POOL, RU_KID), ('en', EN_POOL, EN_KID)):
            p = {g: float(np.mean([self.f0[lang][s] for s in pools[g]])) for g in pools}
            p['kid'] = float(np.mean([self.f0[lang][s] for s in kid]))
            self.pool_f0[lang] = p

    # ------------------------------------------------------------------ lazy components
    @property
    def esp(self):
        if self._esp is None:
            with self._lock:
                if self._esp is None:
                    from .espeak_ipa import EspeakIPA
                    self._esp = EspeakIPA(os.path.join(self.models, 'en', 'espeak'), 'en-us')
        return self._esp

    @property
    def ru(self):
        if self._ru is None:
            with self._lock:
                if self._ru is None:
                    from .silero_ru import SileroRU
                    self._ru = SileroRU(os.path.join(self.models, 'ru'), self.threads)
        return self._ru

    @property
    def en(self):
        if self._en is None:
            with self._lock:
                if self._en is None:
                    from .kokoro_en import KokoroEN
                    k = KokoroEN(os.path.join(self.models, 'en'), self.threads)
                    k.esp = self.esp
                    self._en = k
        return self._en

    @property
    def stress(self):
        if self._stress is None:
            with self._lock:
                if self._stress is None:
                    from .ru_stress import RuStress
                    st = RuStress(os.path.join(self.models, 'ru_stress'))
                    for user in self.user_dicts:                       # user dictionary: one word per line, З+амок
                        if user and os.path.exists(user):
                            st.add_user_dict(user)
                    self._stress = st
        return self._stress

    @property
    def norm(self):
        if self._norm is None:
            with self._lock:
                if self._norm is None:
                    from .ru_norm import RuNormalizer
                    self._norm = RuNormalizer(latin_reader=self._latin_reader)
        return self._norm

    def _latin_reader(self, words):
        from .ipa2cyr import ipa_to_cyr
        return ipa_to_cyr(self.esp.phonemize_chunk(words, 'en-us'))

    def base_speakers(self, lang):
        return sorted(self.f0[lang])

    # ------------------------------------------------------------------ voice design
    def _mix_f0(self, mix, lang):
        tot = sum(mix.values())
        return sum(w * self.f0[lang][s] for s, w in mix.items()) / tot

    def _custom_mix(self, voice, lang):
        """'ru_albina' / 'ru_albina:0.6+ru_zara:0.4' / {'af_heart': .5, ...} -> mix for this language or None"""
        if not voice:
            return None
        if isinstance(voice, dict):
            items = list(voice.items())
        else:
            s = str(voice).strip()
            if not re.fullmatch(r'[a-z]{2,4}_[a-z]+(?:\s*[:*=]\s*[\d.]+)?(?:\s*[+,]\s*[a-z]{2,4}_[a-z]+(?:\s*[:*=]\s*[\d.]+)?)*', s):
                return None
            items = []
            for part in re.split(r'\s*[+,]\s*', s):
                m = re.match(r'([a-z]{2,4}_[a-z]+)(?:\s*[:*=]\s*([\d.]+))?$', part)
                items.append((m.group(1), float(m.group(2) or 1.0)))
        mix = {k: float(w) for k, w in items if k in self.f0[lang] and float(w) > 0}
        return mix or None

    def resolve(self, spec=None, name=None):
        """spec: gender, age, voice, preset, emotion, effect, speed, pitch, formant, lang, pause, accent, attrs.
        Returns a dict with every synthesis parameter (see describe())."""
        sp = {k: v for k, v in dict(spec or {}).items() if v is not None and v != '' and v != []}
        if sp.get('attrs'):
            sp = parse_attrs(sp.pop('attrs'), sp)
        name = name or sp.pop('_name', None) or sp.pop('name', None)
        warn = [str(u) for u in (sp.pop('_unknown', None) or [])]
        voice = sp.get('voice')
        vkey = str(voice).strip().lower() if voice is not None and not isinstance(voice, dict) else None
        # character preset (explicit, or a word of the character name: "Злой дракон")
        pname = None
        if sp.get('preset'):
            pname = preset_name(sp['preset'])
            if not pname:
                warn.append('неизвестный персонаж/preset: %s' % sp['preset'])
        if not pname and name:
            for w in re.split(r'[\s_]+', str(name)):
                pname = preset_name(w.strip('.,!?:;()[]«»"'))
                if pname:
                    break
        P = PRESETS.get(pname, {}) if pname else {}
        if P.get('voice') and not voice:
            voice = P['voice']
            vkey = voice
        g_hint, a_hint = guess_from_name(name) if name else (None, None)
        gender = parse_gender(sp['gender']) if sp.get('gender') else None
        if gender is None and vkey in BANK:
            gender = BANK[vkey]['gender']
        gender = gender or P.get('gender') or g_hint or 'female'
        age = _f(sp.get('age'))
        if age is None:
            age = float(P.get('age') or a_hint or 30)
        age = float(np.clip(age, 2, 105))
        prof = age_profile(age, gender)
        child, pool = prof['child'], prof['pool']
        ename = None
        if sp.get('emotion'):
            ename = emotion_name(sp['emotion'])
            if not ename:
                warn.append('неизвестная эмоция: %s' % sp['emotion'])
        E = EMOTIONS.get(ename, {}) if ename else {}
        seed_name = vkey if vkey else (str(name).strip().lower() if name else None)
        speed = _f(sp.get('speed'), 1.0)
        pitch = _f(sp.get('pitch'), 1.0)
        formant = _f(sp.get('formant'), 1.0)
        # identity (same multipliers for both languages)
        mix_ru0, f0m, am, rm, pm = identity(seed_name, pool, 'ru', child)
        mix_en0 = identity(seed_name, pool, 'en', child)[0]
        alpha = prof['alpha'] * am * P.get('alpha', 1.0) * formant
        rate = prof['rate'] * rm * P.get('rate', 1.0) * E.get('rate', 1.0) * speed
        prange = min(1.65, prof['prange'] * pm * P.get('prange', 1.0) * E.get('prange', 1.0))
        langs = {}
        for lang, mix0 in (('ru', mix_ru0), ('en', mix_en0)):
            custom = self._custom_mix(voice, lang)
            mix = custom or mix0
            f_id = self._mix_f0(mix, lang)
            if not custom and (prof['elder_w'] > 0 or prof['young_w'] > 0):
                el = (RU_ELDER if lang == 'ru' else EN_ELDER)[pool]
                yo = (RU_YOUNG if lang == 'ru' else EN_YOUNG)[pool]
                mix = blend((mix, 1 - prof['elder_w'] - prof['young_w']), ({s: 1.0 for s in el}, prof['elder_w']),
                            ({s: 1.0 for s in yo}, prof['young_w']))
            f_base = self._mix_f0(mix, lang)
            f_pool = self.pool_f0[lang]['kid' if child else pool]
            f_target = (prof['f0_ref'] * (f_id / f_pool) ** prof['f0_keep'] * f0m * P.get('f0', 1.0)
                        * E.get('f0', 1.0) * pitch)
            c = float(np.clip(f_target / (alpha * f_base), 0.75, 2.2))
            accent = None
            if lang == 'en':
                accent = sp.get('accent') or ('en-gb' if sum(w for s, w in mix.items() if s[:1] == 'b')
                                              > 0.5 * sum(mix.values()) else 'en-us')
            langs[lang] = dict(mix={k: round(v / sum(mix.values()), 4) for k, v in mix.items()}, f_base=f_base,
                               f0=f_target, c=c, f0_real=c * alpha * f_base, accent=accent)
        fx = list(P.get('fx', [])) + list(E.get('fx', []))
        eff = sp.get('effect') or []
        if isinstance(eff, str):
            eff = [e for e in re.split(r'[+,/\s]+', eff) if e]
        for e in eff:
            n = effect_name(e)
            if n:
                fx.append(n)
            else:
                warn.append('неизвестный эффект: %s' % e)
        fx = sorted(dict.fromkeys(fx), key=lambda n: FX_ORDER.get(n, 5))
        flang = str(sp.get('lang') or 'auto').lower()
        return dict(
            name=name, gender=gender, age=age, child=child, preset=pname, emotion=ename, voice=seed_name,
            alpha=alpha, rate=rate, prange=prange, lang=langs, forced_lang=flang if flang in ('ru', 'en') else None,
            tremor=prof['tremor'] + P.get('tremor', 0.0) + E.get('tremor', 0.0),
            tremor_hz=E.get('tremor_hz') or P.get('tremor_hz') or prof['tremor_hz'],
            jitter=prof['jitter'] + P.get('jitter', 0.0) + E.get('jitter', 0.0),
            shimmer=prof['shimmer'] + P.get('shimmer', 0.0) + E.get('shimmer', 0.0),
            breath=prof['breath'] + P.get('breath', 0.0) + E.get('breath', 0.0),
            tilt=P.get('tilt', 0.0) + E.get('tilt', 0.0), drive=E.get('drive') or P.get('drive'),
            gain=P.get('gain', 0.0) + E.get('gain', 0.0), fx=fx,
            pause=prof['pause'] * _f(sp.get('pause'), 1.0) / max(0.3, speed * E.get('rate', 1.0)),
            seed=_seed(seed_name or '', gender, int(age)), warnings=warn)

    def describe(self, v, lang=None):
        g = {'male': 'мужской', 'female': 'женский'}[v['gender']]
        langs = [lang] if lang else ['ru', 'en']
        s = '%s: %s, %g лет' % (v['name'] or 'голос', g, round(v['age'], 1))
        if v['preset']:
            s += ', персонаж «%s»' % v['preset']
        if v['emotion']:
            s += ', эмоция «%s»' % v['emotion']
        s += '\n  высота ≈ %d Гц, тембр (форманты) ×%.2f, темп ×%.2f, интонация ×%.2f' % (
            round(v['lang'][langs[0]]['f0_real']), v['alpha'], v['rate'], v['prange'])
        extra = []
        if v['tremor'] > 0:
            extra.append('дрожание %.1f%%' % (v['tremor'] * 100))
        if v['breath'] > 0:
            extra.append('придыхание %.2f' % v['breath'])
        if v['fx']:
            extra.append('эффекты: ' + ', '.join(v['fx']))
        if extra:
            s += '\n  ' + ', '.join(extra)
        for L in langs:
            mix = ', '.join('%s %d%%' % (k, round(w * 100)) for k, w in sorted(v['lang'][L]['mix'].items(), key=lambda t: -t[1]))
            s += '\n  смесь базовых тембров %s: %s' % (L.upper(), mix)
        if v['warnings']:
            s += '\n  ! не распознано: ' + '; '.join(v['warnings'])
        return s

    # ------------------------------------------------------------------ synthesis
    def _ru_voice(self, mix):
        key = ('ru',) + tuple(sorted(mix.items()))
        if key not in self._vcache:
            self._vcache[key] = self.ru.voice(mix)
        return self._vcache[key]

    def _en_voice(self, mix):
        key = ('en',) + tuple(sorted(mix.items()))
        if key not in self._vcache:
            self._vcache[key] = self.en.voice(mix)
        return self._vcache[key]

    def ru_prepare(self, sent):
        """Raw Russian sentence -> normalised, stress-marked, Silero-clean text."""
        from .silero_ru import clean_text
        t = self.norm(sent)
        t = re.sub(r'\s*[—–]+\s*', ', ', t)
        t = re.sub(r'\s+-+\s+', ', ', t)
        t = re.sub(r'^[\s,.:;-]+', '', t)
        t = self.stress(t)
        t = clean_text(t)
        t = re.sub(r',(\s*,)+', ',', t)
        t = re.sub(r'[,:;]\s*([.?…])', r'\1', t)
        t = t.strip()
        if t and t[-1] not in '.?…':
            t = t.rstrip(',:;- ') + '.'
        return t

    def _synth_ru(self, sent, v, excl=False, info=None):
        """info: optional dict, gets 'text' (what the model read) and 'words' [(word, start_s, end_s)] measured
        from the model's own symbol durations (exact, not estimated)."""
        t = self.ru_prepare(sent)
        if not re.search(r'[а-яё]', t):
            return None
        L = v['lang']['ru']
        c, pr, rate = L['c'], max(0.05, v['prange']), v['rate']
        if excl:                        # the model has no '!': livelier intonation instead
            c, pr, rate = c * 1.05, pr * 1.2, rate * 1.03
        voice = self._ru_voice(L['mix'])
        outs, words, pos = [], [], 0
        for ch in _chunks(t):
            durs = [] if info is not None else None
            x = self.ru.synth(ch, voice, rate=rate / v['alpha'], pitch=c, pitch_range=pr, durs_out=durs)
            a, b = dsp.trim_bounds(x, SR, -50.0, 0.03)
            x = x[a:b]
            if len(x):
                if outs:
                    outs.append(silence(0.12))
                    pos += len(outs[-1])
                if durs:
                    for w, f0, f1 in ru_word_frames(ch, durs[0]):
                        s0 = min(max(f0 * HOP - a, 0), len(x))
                        s1 = min(max(f1 * HOP - a, 0), len(x))
                        words.append((w, pos + s0, pos + s1))
                outs.append(x)
                pos += len(x)
        if not outs:
            return None
        y = dsp.speedup(np.concatenate(outs), v['alpha'])
        if info is not None:
            k = len(y) / float(max(1, pos))
            info['text'] = t
            info['words'] = [(w, s * k / SR, e * k / SR) for w, s, e in words]
        return y

    def _synth_en(self, sent, v):
        from .en_norm import normalize_en
        t = normalize_en(sent)
        if not re.search(r'[A-Za-z0-9]', t):
            return None
        L = v['lang']['en']
        style = self._en_voice(L['mix'])
        x = self.en.synth(t, style, speed=v['rate'] / v['alpha'], pitch=L['c'],
                          pitch_range=max(0.05, v['prange']), accent=L['accent'])
        x = dsp.trim(x, 24000, -50.0, 0.03)
        if not len(x):
            return None
        return dsp.resample_len(x, int(round(len(x) * 2 / v['alpha'])))

    def _post_fx(self, x, v, k=0):
        """Voice quality (age), emotion colour and effects for one block of a turn (no loudness)."""
        sd = v['seed'] + 101 * k
        if v['tremor'] > 0 or v['jitter'] > 0:
            x = dsp.pitch_wobble(x, SR, v['tremor_hz'], v['tremor'], v['jitter'], seed=sd)
        if v['tremor'] > 0 or v['shimmer'] > 0:
            x = dsp.amp_wobble(x, SR, v['tremor_hz'], min(0.5, 2.5 * v['tremor']), v['shimmer'], seed=sd + 1)
        if v['breath'] > 0:
            x = dsp.breathiness(x, SR, v['breath'], seed=sd + 2)
        if v['tilt']:
            x = dsp.tilt(x, SR, v['tilt'])
        if v['drive']:
            x = dsp.saturate(x, v['drive'])
        for fx in v['fx']:
            x = apply_effect(x, SR, fx, seed=sd)
        return np.asarray(x, np.float32)

    def render(self, text, v, block_sec=20.0, marks=None):
        """Text of one speaker turn (may contain paragraphs and [пауза N]) -> processed audio.
        Long texts are processed in ~20 s blocks (bounded memory); effect tails overlap the next block.
        marks: optional list, gets one dict per spoken sentence: text, lang, s, e (seconds in the result) and
        words [(word, s, e)] for Russian (from the model durations) or None (English: no durations)."""
        blocks, cur, cur_n = [], [], 0
        limit = int(block_sec * SR)
        tpos = 0

        def push(a):
            nonlocal cur, cur_n, tpos
            cur.append(a)
            cur_n += len(a)
            tpos += len(a)
            if cur_n >= limit and np.any(a == 0) and not np.any(a):     # cut blocks only at pauses
                blocks.append(cur)
                cur, cur_n = [], 0

        prev_lang = v['forced_lang']
        paras = [p for p in re.split(r'\n\s*\n', str(text).replace('\r', '')) if p.strip()]
        for pi, par in enumerate(paras):
            if pi and (cur or blocks):
                push(silence(PARAGRAPH_PAUSE * v['pause']))
            for seg in split_pauses(_join_lines(par)):
                if isinstance(seg, float):
                    push(silence(seg))
                    continue
                for sent in split_sentences(seg):
                    lang = detect_lang(sent, v['forced_lang']) or prev_lang or 'ru'
                    prev_lang = lang
                    end = _ending(sent)
                    inf = {} if marks is not None else None
                    x = self._synth_ru(sent, v, end == '!', inf) if lang == 'ru' else self._synth_en(sent, v)
                    if x is None or not len(x):
                        continue
                    if marks is not None:
                        s0 = tpos / float(SR)
                        marks.append(dict(text=sent, lang=lang, s=s0, e=s0 + len(x) / float(SR),
                                          words=[(w, s0 + a, s0 + b) for w, a, b in inf['words']]
                                          if inf.get('words') else None))
                    push(x)
                    push(silence(PAUSES.get(end, 0.3) * v['pause']))
        if cur:
            blocks.append(cur)
        while blocks:                                   # drop trailing silence
            while blocks[-1] and not np.any(blocks[-1][-1]):
                blocks[-1].pop()
            if blocks[-1]:
                break
            blocks.pop()
        if not blocks:
            return np.zeros(0, np.float32)
        offs, outs, pos = [], [], 0
        for k, b in enumerate(blocks):
            a = np.concatenate(b)
            offs.append(pos)
            pos += len(a)
            outs.append(self._post_fx(a, v, k))
        y = np.zeros(max(o + len(a) for o, a in zip(offs, outs)), np.float32)
        for o, a in zip(offs, outs):
            y[o:o + len(a)] += a
        del outs
        if v['fx']:                                     # cut the silent part of reverb / echo tails
            idx = np.where(np.abs(y) > np.abs(y).max() * 10 ** (-62 / 20.0))[0]
            if len(idx):
                y = y[:min(len(y), idx[-1] + int(0.05 * SR))]
        y = dsp.fade(y, SR, 0.003, 0.03)
        return dsp.loudness(y, SR, -19.0 + v['gain'])

    # ------------------------------------------------------------------ public API
    def voice(self, gender=None, age=None, voice=None, preset=None, emotion=None, effect=None, speed=None,
              pitch=None, formant=None, lang=None, pause=None, accent=None, name=None, attrs=None):
        spec = dict(gender=gender, age=age, voice=voice, preset=preset, emotion=emotion, effect=effect, speed=speed,
                    pitch=pitch, formant=formant, lang=lang, pause=pause, accent=accent, attrs=attrs)
        return self.resolve(spec, name)

    def say(self, text, **kw):
        """Text -> float32 audio at self.sr.  Keywords: see voice()."""
        return self.render(text, self.voice(**kw))

    def save(self, text, path, sr=None, **kw):
        return write_audio(path, self.say(text, **kw), SR, sr)

    def script(self, text, defaults=None, save_lines=None, sr=None, log=None, describe=False, marks=None):
        """Dialogue script (text or JSON, see reference/voice.md) -> (audio, list of line info).
        marks: optional list of sentence marks like render(), plus 'speaker'."""
        items, _ = load_script(text)
        seen = set()
        defaults = {k: v for k, v in dict(defaults or {}).items() if v is not None and v != ''}
        named_only = ('voice', 'gender', 'age', 'preset', 'name')
        out, info = [], []
        n = 0
        for it in items:
            if it['type'] == 'pause':
                out.append(silence(PARAGRAPH_PAUSE if it['sec'] is None else it['sec']))
                continue
            spec = {k: v for k, v in defaults.items() if not (it.get('name') and k in named_only)}
            spec.update(it.get('spec') or {})
            spec.update(it.get('line_spec') or {})
            v = self.resolve(spec, it.get('name'))
            if describe and log and (it.get('name') or '') not in seen:
                seen.add(it.get('name') or '')
                log(self.describe(v, detect_lang(it['text'], v['forced_lang']) or 'ru'))
            sub = [] if marks is not None else None
            x = self.render(it['text'], v, marks=sub)
            if not len(x):
                continue
            n += 1
            if out and np.any(out[-1]):
                out.append(silence(TURN_PAUSE * v['pause']))
            if marks is not None:
                t0 = sum(len(a) for a in out) / float(SR)
                for m in sub:
                    m = dict(m, s=m['s'] + t0, e=m['e'] + t0, speaker=it.get('name') or '',
                             words=[(w, a + t0, b + t0) for w, a, b in m['words']] if m['words'] else None)
                    marks.append(m)
            out.append(x)
            rec = dict(n=n, speaker=it.get('name') or '(рассказчик)', text=it['text'], sec=round(len(x) / SR, 2))
            if save_lines:
                os.makedirs(save_lines, exist_ok=True)
                safe = re.sub(r'[^\wА-Яа-яЁё-]+', '_', rec['speaker'])[:30]
                rec['file'] = write_audio(os.path.join(save_lines, '%03d_%s.wav' % (n, safe)), x, SR, sr)
            info.append(rec)
            if log:
                log('%3d. %s: %s' % (n, rec['speaker'], it['text'][:70]))
        while out and not np.any(out[-1]):
            out.pop()
        audio = np.concatenate(out) if out else np.zeros(0, np.float32)
        return audio, info

    def save_script(self, text, path, defaults=None, save_lines=None, sr=None, log=None, describe=False):
        audio, info = self.script(text, defaults, save_lines, sr, log, describe)
        return write_audio(path, audio, SR, sr), info
