# -*- coding: utf-8 -*-
"""Character presets, emotions and sound effects (all names accept Russian or English)."""
import numpy as np

from . import dsp

# preset fields: gender, age, voice -> defaults (user values win);
# alpha, f0, rate, prange -> multipliers; breath/tremor/jitter/shimmer -> added; fx -> effect list
PRESETS = {
    'робот': dict(desc='робот: монотонный, металлический', prange=0.0, rate=0.95, fx=['robot']),
    'великан': dict(desc='великан/тролль: огромный, очень низкий, гулкий', gender='male', age=45,
                    alpha=0.78, f0=0.62, rate=0.88, prange=1.1, fx=['hall']),
    'монстр': dict(desc='чудовище: рычащий низкий голос', gender='male', age=40, alpha=0.72, f0=0.55,
                   prange=1.2, rate=0.9, fx=['growl', 'room']),
    'дракон': dict(desc='дракон: гигантский, рычащий, с эхом пещеры', gender='male', age=60, alpha=0.66,
                   f0=0.5, prange=1.25, rate=0.85, fx=['growl', 'cave']),
    'гном': dict(desc='гном: маленький бодрый бородач', gender='male', age=55, alpha=1.18, f0=1.25, rate=1.06),
    'мультяшка': dict(desc='мультяшный персонаж: высокий, задорный', gender='female', age=25, alpha=1.32,
                      f0=1.5, prange=1.35, rate=1.08),
    'белка': dict(desc='бурундук/белка: очень высокий и быстрый', gender='female', age=20, alpha=1.5, f0=1.9,
                  prange=1.3, rate=1.15),
    'медведь': dict(desc='добродушный мультяшный медведь: низкий, басовитый, неторопливый', gender='male',
                    age=50, alpha=0.84, f0=0.78, prange=1.2, rate=0.85),
    'лиса': dict(desc='хитрая лиса: вкрадчивый, игривый', gender='female', age=30, alpha=1.1, f0=1.12,
                 prange=1.4, rate=1.03),
    'ведьма': dict(desc='сказочная колдунья-старуха: скрипучая, ехидная', gender='female', age=85,
                   alpha=1.06, f0=1.18, prange=1.5, breath=0.12, fx=['crackle']),
    'злодей': dict(desc='злодей: низкий, вкрадчивый, зловещий', gender='male', age=45, alpha=0.92, f0=0.86,
                   prange=1.15, rate=0.92, fx=['room']),
    'привидение': dict(desc='призрак: шёпот с гулким эхом', fx=['whisper', 'ghost']),
    'инопланетянин': dict(desc='пришелец: металлический, неземной', alpha=1.15, f0=1.2, fx=['alien']),
    'рассказчик': dict(desc='сказочник: тёплый, неторопливый', gender='male', age=62, voice='m1', rate=0.93,
                       prange=1.15),
    'диктор': dict(desc='диктор: чёткий, уверенный', gender='male', age=40, voice='m1', prange=1.08),
    'ведущая': dict(desc='ведущая: чёткий уверенный женский голос', gender='female', age=35, voice='f1',
                    prange=1.08),
}
PRESET_ALIASES = {
    'robot': 'робот', 'giant': 'великан', 'troll': 'великан', 'тролль': 'великан', 'monster': 'монстр',
    'чудовище': 'монстр', 'dragon': 'дракон', 'gnome': 'гном', 'dwarf': 'гном', 'cartoon': 'мультяшка',
    'chipmunk': 'белка', 'бурундук': 'белка', 'squirrel': 'белка', 'bear': 'медведь', 'fox': 'лиса',
    'witch': 'ведьма', 'колдунья': 'ведьма', 'баба-яга': 'ведьма', 'баба яга': 'ведьма', 'villain': 'злодей',
    'ghost': 'привидение', 'призрак': 'привидение', 'alien': 'инопланетянин', 'пришелец': 'инопланетянин',
    'narrator': 'рассказчик', 'сказочник': 'рассказчик', 'storyteller': 'рассказчик', 'announcer': 'диктор',
    'host': 'ведущая',
}

EMOTIONS = {
    'нейтрально': dict(desc='обычная подача'),
    'радостно': dict(desc='радостно, оживлённо', f0=1.06, prange=1.3, rate=1.06),
    'восторженно': dict(desc='восторг, очень эмоционально', f0=1.1, prange=1.45, rate=1.08),
    'грустно': dict(desc='грустно, тихо', f0=0.94, prange=0.7, rate=0.86, breath=0.04, gain=-2.0),
    'сердито': dict(desc='сердито, напористо', f0=1.03, prange=1.25, rate=1.08, tilt=1.5, drive=1.4),
    'испуганно': dict(desc='испуганно, дрожащим голосом', f0=1.12, prange=1.2, rate=1.12, tremor=0.012,
                      tremor_hz=7.0),
    'спокойно': dict(desc='спокойно, размеренно', f0=0.98, prange=0.85, rate=0.93),
    'устало': dict(desc='устало, вяло', f0=0.95, prange=0.7, rate=0.85, breath=0.06),
    'торжественно': dict(desc='торжественно, с расстановкой', f0=0.98, prange=1.15, rate=0.9),
    'шёпотом': dict(desc='шёпотом', rate=0.95, fx=['whisper'], gain=-6.0),
}
EMOTION_ALIASES = {
    'neutral': 'нейтрально', 'happy': 'радостно', 'joy': 'радостно', 'весело': 'радостно',
    'excited': 'восторженно', 'sad': 'грустно', 'печально': 'грустно', 'angry': 'сердито', 'зло': 'сердито',
    'злобно': 'сердито', 'scared': 'испуганно', 'afraid': 'испуганно', 'страшно': 'испуганно',
    'calm': 'спокойно', 'tired': 'устало', 'solemn': 'торжественно', 'whisper': 'шёпотом',
    'шепотом': 'шёпотом', 'шёпот': 'шёпотом', 'шепот': 'шёпотом',
    # Shorts 2.4: words models and people often use for a voice-over
    'бодро': 'радостно', 'cheerful': 'радостно', 'энергично': 'восторженно', 'energetic': 'восторженно',
    'грозно': 'сердито',
}

EFFECTS = {
    'whisper': 'шёпот (без голоса, только дыхание)',
    'phone': 'телефонная трубка',
    'radio': 'рация / walkie-talkie',
    'oldradio': 'старое радио / граммофон',
    'megaphone': 'мегафон / громкоговоритель',
    'room': 'небольшая комната',
    'hall': 'большой зал',
    'cave': 'пещера (гулкое эхо)',
    'echo': 'эхо в горах',
    'robot': 'роботизированный металлический тембр',
    'growl': 'рычание / хрип',
    'ghost': 'призрачное эхо',
    'alien': 'неземной модулированный тембр',
    'crackle': 'скрипучесть, надтреснутость',
    'underwater': 'как из-под воды',
    'radio_noise': 'эфир с шумом',
}
EFFECT_ALIASES = {
    'шёпот': 'whisper', 'шепот': 'whisper', 'телефон': 'phone', 'рация': 'radio', 'радио': 'oldradio',
    'граммофон': 'oldradio', 'мегафон': 'megaphone', 'громкоговоритель': 'megaphone', 'комната': 'room',
    'зал': 'hall', 'пещера': 'cave', 'эхо': 'echo', 'робот': 'robot', 'рык': 'growl', 'рычание': 'growl',
    'хрип': 'growl', 'призрак': 'ghost', 'пришелец': 'alien', 'скрип': 'crackle', 'под водой': 'underwater',
    'подводой': 'underwater', 'под_водой': 'underwater', 'эфир': 'radio_noise', 'reverb': 'hall',
}


def _canon(name, table, aliases):
    if not name:
        return None
    k = str(name).strip().lower().replace('ё', 'ё')
    if k in table:
        return k
    if k in aliases:
        return aliases[k]
    k2 = k.replace('ё', 'е')
    for t in list(table) + list(aliases):
        if t.replace('ё', 'е') == k2:
            return t if t in table else aliases[t]
    return None


def preset_name(n):
    return _canon(n, PRESETS, PRESET_ALIASES)


def emotion_name(n):
    return _canon(n, EMOTIONS, EMOTION_ALIASES)


def effect_name(n):
    return _canon(n, EFFECTS, EFFECT_ALIASES)


def apply_effect(x, sr, name, seed=0):
    rng = np.random.default_rng(seed + 11)
    if name == 'whisper':
        return dsp.whisper(x, sr, seed=seed + 3) * 0.8
    if name == 'phone':
        return dsp.telephone(x, sr, seed=seed + 5)
    if name == 'radio':
        y = dsp.band(x, sr, low=450, high=2700, order=4)
        y = dsp.saturate(y, 3.0)
        return (y + 0.012 * np.abs(y).max() * rng.standard_normal(len(y))).astype(np.float32)
    if name == 'radio_noise':
        y = dsp.band(x, sr, low=200, high=5000, order=2)
        return (y + 0.02 * np.abs(y).max() * dsp.band(rng.standard_normal(len(y)), sr, 300, 6000)).astype(np.float32)
    if name == 'oldradio':
        y = dsp.band(x, sr, low=300, high=3400, order=3)
        y = dsp.saturate(y, 1.8)
        hum = 0.004 * np.sin(2 * np.pi * 50 * np.arange(len(y)) / sr)
        crackle = (rng.random(len(y)) < 0.0004) * rng.standard_normal(len(y)) * 0.08
        return (y + (hum + crackle + 0.006 * rng.standard_normal(len(y))) * np.abs(y).max()).astype(np.float32)
    if name == 'megaphone':
        y = dsp.band(x, sr, low=500, high=4000, order=3)
        y = dsp.peak_eq(y, sr, 1800, 6, 1.5)
        y = dsp.saturate(y, 2.5)
        return dsp.reverb(y, sr, rt60=0.9, wet=0.12, seed=seed + 4)
    if name == 'room':
        return dsp.reverb(x, sr, rt60=0.35, wet=0.12, predelay=0.006, seed=seed + 4)
    if name == 'hall':
        return dsp.reverb(x, sr, rt60=1.6, wet=0.22, predelay=0.02, seed=seed + 4)
    if name == 'cave':
        y = dsp.reverb(x, sr, rt60=2.6, wet=0.3, predelay=0.03, seed=seed + 4)
        return dsp.echo(y, sr, delay=0.32, feedback=0.3, wet=0.22)
    if name == 'echo':
        return dsp.echo(x, sr, delay=0.42, feedback=0.45, wet=0.35)
    if name == 'robot':
        y = dsp.ring_mod(x, sr, freq=55.0, mix=0.45)
        y = dsp.comb(y, sr, delay_ms=3.2, gain=0.5)
        return dsp.peak_eq(y, sr, 2500, 3, 1.0)
    if name == 'growl':
        n = len(x)
        mod = 1 + 0.35 * dsp._smooth_noise(n, sr, 28.0, rng)
        y = x * mod
        y = dsp.saturate(y, 2.2)
        return dsp.tilt(y, sr, -0.8).astype(np.float32)
    if name == 'ghost':
        y = dsp.reverb(x, sr, rt60=2.2, wet=0.35, predelay=0.04, seed=seed + 4)
        return dsp.echo(y, sr, delay=0.28, feedback=0.35, wet=0.25)
    if name == 'alien':
        y = dsp.ring_mod(x, sr, freq=140.0, mix=0.35)
        return dsp.comb(y, sr, delay_ms=1.5, gain=0.45)
    if name == 'crackle':
        y = dsp.pitch_wobble(x, sr, 0, 0, jitter=0.02, seed=seed + 7)
        y = dsp.amp_wobble(y, sr, 0, 0, shimmer=0.12, seed=seed + 8)
        return dsp.saturate(y, 1.6)
    if name == 'underwater':
        y = dsp.band(x, sr, high=700, order=3)
        y = dsp.pitch_wobble(y, sr, 2.0, 0.015, seed=seed + 9)
        return dsp.reverb(y, sr, rt60=0.8, wet=0.25, seed=seed + 4)
    return x
