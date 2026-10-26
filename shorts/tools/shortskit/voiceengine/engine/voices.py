# -*- coding: utf-8 -*-
"""Voice design.

Every voice is ORIGINAL: a weighted blend of several base-speaker embeddings
(it does not exist as a real person), then shaped by simple voice physics:
  * vocal-tract length  -> formant scale `alpha` (children / small creatures > 1)
  * fundamental frequency f0 (age & gender curves)
  * tempo, intonation range, tremor, jitter, shimmer, breathiness (age)
"""
import hashlib

import numpy as np

# ----------------------------------------------------------------------------- base pools
RU_POOL = {
    'male': ['bel_anatoliy', 'erz_alexandr', 'ru_miyau', 'bak_miyau', 'ru_roman', 'ru_marat', 'ru_alexandr',
             'ukr_igor', 'ru_kejilgan', 'tat_marat', 'ukr_roman', 'bel_dmitriy'],
    'female': ['ru_albina', 'ru_zara', 'ru_alfia', 'bak_aigul', 'sah_zinaida', 'bak_alfia', 'ru_aigul',
               'ru_zhadyra', 'ru_zinaida', 'kaz_zhazira', 'uzb_saida', 'ru_kermen', 'ru_nurgul'],
}
RU_YOUNG = {'male': ['erz_alexandr', 'ru_alexandr', 'ru_roman', 'ukr_roman'],
            'female': ['ru_zhadyra', 'ru_zhazira', 'kaz_zhadyra', 'ru_albina']}
RU_ELDER = {'male': ['ru_eduard', 'kbd_eduard'],
            'female': ['bak_ramilia', 'ru_ramilia', 'kat_vika']}
RU_KID = ['kaz_zhazira', 'ru_kermen', 'ru_zara', 'ru_alfia', 'bak_alfia', 'ru_zhazira', 'ru_zhadyra']

EN_POOL = {
    'male': ['am_michael', 'am_fenrir', 'am_puck', 'bm_george', 'bm_fable', 'am_echo', 'am_eric', 'am_liam',
             'bm_lewis', 'am_onyx'],
    'female': ['af_heart', 'af_bella', 'af_nicole', 'af_aoede', 'af_kore', 'af_sarah', 'af_nova', 'bf_emma',
               'bf_isabella'],
}
EN_YOUNG = {'male': ['am_puck', 'am_echo', 'am_liam'], 'female': ['af_bella', 'af_nova', 'af_sky']}
EN_ELDER = {'male': ['am_santa', 'bm_george'], 'female': ['af_nicole', 'bf_emma']}
EN_KID = ['af_bella', 'af_heart', 'af_sarah', 'af_jessica', 'bf_isabella', 'af_aoede']

# ----------------------------------------------------------------------------- curated original voices
BANK = {
    'm1': dict(gender='male', desc='ровный тёплый баритон, дикторский',
               ru={'bel_anatoliy': .5, 'ru_miyau': .3, 'erz_alexandr': .2},
               en={'am_michael': .5, 'am_fenrir': .3, 'bm_george': .2}),
    'm2': dict(gender='male', desc='низкий, басовитый, спокойный',
               ru={'ru_kejilgan': .5, 'ru_roman': .3, 'bak_miyau': .2},
               en={'am_onyx': .45, 'am_fenrir': .35, 'am_michael': .2}),
    'm3': dict(gender='male', desc='молодой, светлый, лёгкий',
               ru={'erz_alexandr': .5, 'ru_alexandr': .3, 'ukr_roman': .2},
               en={'am_puck': .6, 'am_echo': .4}),
    'm4': dict(gender='male', desc='энергичный, чуть выше среднего',
               ru={'ru_marat': .5, 'tat_marat': .3, 'bel_dmitriy': .2},
               en={'am_eric': .5, 'am_liam': .5}),
    'm5': dict(gender='male', desc='с хрипотцой, характерный',
               ru={'ukr_igor': .45, 'bak_miyau': .3, 'ru_bogdan': .25},
               en={'bm_lewis': .4, 'am_fenrir': .35, 'am_onyx': .25}),
    'm6': dict(gender='male', desc='мягкий, разговорный (брит. акцент в EN)',
               ru={'ru_roman': .4, 'ukr_roman': .3, 'ru_dmitriy': .3},
               en={'bm_george': .55, 'bm_fable': .45}),
    'f1': dict(gender='female', desc='ясный, дикторский',
               ru={'ru_zara': .4, 'ru_alfia': .35, 'sah_zinaida': .25},
               en={'af_heart': .6, 'af_bella': .4}),
    'f2': dict(gender='female', desc='низкий, бархатный',
               ru={'ru_albina': .6, 'ru_zinaida': .4},
               en={'af_nicole': .5, 'af_kore': .5}),
    'f3': dict(gender='female', desc='звонкий, высокий',
               ru={'kaz_zhazira': .4, 'ru_kermen': .35, 'bak_alfia': .25},
               en={'af_bella': .5, 'af_aoede': .5}),
    'f4': dict(gender='female', desc='молодой, мягкий',
               ru={'ru_zhadyra': .5, 'ru_albina': .25, 'ru_zhazira': .25},
               en={'af_sarah': .5, 'af_nova': .5}),
    'f5': dict(gender='female', desc='тёплый, разговорный',
               ru={'bak_aigul': .4, 'ru_aigul': .3, 'ru_nurgul': .3},
               en={'af_heart': .5, 'af_kore': .5}),
    'f6': dict(gender='female', desc='уверенный, деловой (брит. акцент в EN)',
               ru={'uzb_saida': .35, 'ru_alfia': .35, 'ru_zara': .3},
               en={'bf_emma': .6, 'bf_isabella': .4}),
}
DEFAULT_VOICE = {'male': 'm1', 'female': 'f1'}


def interp(x, table):
    xs = [p[0] for p in table]
    ys = [p[1] for p in table]
    return float(np.interp(x, xs, ys))


# ----------------------------------------------------------------------------- age / gender physics
F0_FEMALE = [(2, 310), (4, 300), (6, 287), (8, 272), (10, 258), (12, 244), (14, 230), (16, 220), (18, 213),
             (22, 207), (30, 201), (40, 197), (50, 190), (60, 182), (70, 176), (80, 171), (90, 167), (105, 164)]
F0_MALE = [(2, 305), (4, 296), (6, 282), (8, 266), (10, 252), (12, 240), (13, 228), (14, 178), (15, 152),
           (16, 139), (17, 131), (18, 127), (22, 122), (30, 118), (45, 116), (55, 118), (65, 123), (75, 129),
           (85, 135), (105, 141)]
POOL_F0 = {'female': 197.0, 'male': 117.0}
ALPHA_KID = [(2, 1.36), (4, 1.31), (6, 1.26), (8, 1.20), (10, 1.15), (12, 1.10), (14, 1.05), (16, 1.03),
             (18, 1.02), (22, 1.01), (30, 1.0), (50, 1.0), (70, 0.99), (90, 0.98), (105, 0.975)]
ALPHA_MALE = [(14, 1.10), (15, 1.07), (16, 1.05), (17, 1.035), (18, 1.025), (22, 1.012), (30, 1.0),
              (50, 0.995), (70, 0.985), (90, 0.975), (105, 0.97)]
RATE = [(2, 0.78), (4, 0.84), (6, 0.90), (8, 0.94), (10, 0.97), (12, 1.0), (16, 1.03), (25, 1.03), (40, 1.0),
        (55, 0.97), (65, 0.93), (75, 0.88), (85, 0.83), (95, 0.79), (105, 0.76)]
PRANGE = [(2, 1.35), (5, 1.33), (8, 1.25), (11, 1.18), (14, 1.10), (18, 1.05), (30, 1.0), (55, 0.96), (70, 0.92),
          (85, 0.87), (105, 0.85)]
TREMOR = [(58, 0.0), (65, 0.005), (75, 0.012), (85, 0.02), (95, 0.028), (105, 0.032)]
JITTER = [(58, 0.0), (70, 0.004), (85, 0.009), (105, 0.014)]
SHIMMER = [(58, 0.0), (70, 0.03), (85, 0.07), (105, 0.10)]
BREATH = [(2, 0.05), (10, 0.03), (14, 0.0), (58, 0.0), (65, 0.05), (75, 0.10), (85, 0.16), (105, 0.22)]
ELDER_W = [(50, 0.0), (65, 0.25), (80, 0.4), (95, 0.5)]
YOUNG_W = [(13, 0.45), (18, 0.4), (25, 0.25), (32, 0.0)]
PAUSE = [(2, 1.2), (10, 1.0), (60, 1.05), (80, 1.25), (95, 1.4)]


def age_profile(age, gender):
    """Physical parameters for a speaker of this age / gender."""
    a = float(np.clip(age, 2, 105))
    male = gender == 'male'
    p = {}
    if male and a >= 14:
        p['pool'] = 'male'
        p['alpha'] = interp(a, ALPHA_MALE)
    else:
        p['pool'] = 'female'           # children of both sexes and women: female base timbres
        p['alpha'] = interp(a, ALPHA_KID) * (0.975 if male else 1.0)
    p['child'] = a < 13 or (not male and a < 14)
    p['f0_ref'] = interp(a, F0_MALE if male else F0_FEMALE)
    # how much the identity's own pitch is kept (children cluster tighter)
    p['f0_keep'] = interp(a, [(10, 0.5), (16, 1.0)])
    p['rate'] = interp(a, RATE)
    p['prange'] = interp(a, PRANGE)
    p['tremor'] = interp(a, TREMOR)
    p['tremor_hz'] = float(np.clip(5.6 - (a - 60) * 0.03, 4.3, 5.6))
    p['jitter'] = interp(a, JITTER)
    p['shimmer'] = interp(a, SHIMMER)
    p['breath'] = interp(a, BREATH)
    p['elder_w'] = interp(a, ELDER_W)
    p['young_w'] = 0.0 if p['child'] else interp(a, YOUNG_W)
    p['pause'] = interp(a, PAUSE)
    return p


# ----------------------------------------------------------------------------- identities
def _seed(*parts):
    h = hashlib.sha1('|'.join(str(x).strip().lower() for x in parts).encode('utf-8')).hexdigest()
    return int(h[:12], 16)


def identity(name, gender, lang, child=False):
    """Stable original timbre for any name: returns (mix, f0_mult, alpha_mult, rate_mult, prange_mult)."""
    pools = RU_POOL if lang == 'ru' else EN_POOL
    kid_pool = RU_KID if lang == 'ru' else EN_KID
    if name and name.lower() in BANK and not child:
        b = BANK[name.lower()]
        if b['gender'] == gender:
            return dict(b[lang]), 1.0, 1.0, 1.0, 1.0
    if not name:
        if child:
            return ({'kaz_zhazira': .4, 'ru_kermen': .3, 'ru_zara': .3} if lang == 'ru'
                    else {'af_bella': .5, 'af_heart': .3, 'af_sarah': .2}), 1.0, 1.0, 1.0, 1.0
        return dict(BANK[DEFAULT_VOICE[gender]][lang]), 1.0, 1.0, 1.0, 1.0
    rng = np.random.default_rng(_seed(name, gender, 'kid' if child else 'adult'))
    pool = kid_pool if child else pools[gender]
    k = 3 if len(pool) >= 3 else len(pool)
    sel = list(rng.choice(pool, k, replace=False))
    w = rng.dirichlet([1.2] * k)
    mix = {s: float(x) for s, x in zip(sel, w)}
    f0m = float(np.exp(rng.normal(0, 0.05)))
    am = float(np.exp(rng.normal(0, 0.02)))
    rm = float(np.exp(rng.normal(0, 0.035)))
    pm = float(np.exp(rng.normal(0, 0.08)))
    return mix, f0m, am, rm, pm


def blend(*weighted):
    """blend((mixA, wA), (mixB, wB), ...) -> normalised mix"""
    out = {}
    for mix, w in weighted:
        if w <= 0 or not mix:
            continue
        tot = sum(mix.values())
        for k, v in mix.items():
            out[k] = out.get(k, 0.0) + w * v / tot
    s = sum(out.values())
    return {k: v / s for k, v in out.items()}
