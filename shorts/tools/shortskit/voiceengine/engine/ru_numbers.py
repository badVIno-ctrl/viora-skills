# -*- coding: utf-8 -*-
"""Russian numerals: cardinals, ordinals, decimals, agreement helpers (pure Python)."""
import re

_U = {'m': ['ноль', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять'],
      'f': ['ноль', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять'],
      'n': ['ноль', 'одно', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']}
_TEENS = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать',
          'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
_TENS = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
_HUND = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']
_SCALES = [(10 ** 12, 'm', ('триллион', 'триллиона', 'триллионов')),
           (10 ** 9, 'm', ('миллиард', 'миллиарда', 'миллиардов')),
           (10 ** 6, 'm', ('миллион', 'миллиона', 'миллионов')),
           (10 ** 3, 'f', ('тысяча', 'тысячи', 'тысяч'))]

_OU = ['нулевой', 'первый', 'второй', 'третий', 'четвёртый', 'пятый', 'шестой', 'седьмой', 'восьмой', 'девятый']
_OTEENS = ['десятый', 'одиннадцатый', 'двенадцатый', 'тринадцатый', 'четырнадцатый', 'пятнадцатый',
           'шестнадцатый', 'семнадцатый', 'восемнадцатый', 'девятнадцатый']
_OTENS = ['', '', 'двадцатый', 'тридцатый', 'сороковой', 'пятидесятый', 'шестидесятый', 'семидесятый',
          'восьмидесятый', 'девяностый']
_OHUND = ['', 'сотый', 'двухсотый', 'трёхсотый', 'четырёхсотый', 'пятисотый', 'шестисотый', 'семисотый',
          'восьмисотый', 'девятисотый']
_GEN_PREFIX = {1: '', 2: 'двух', 3: 'трёх', 4: 'четырёх', 5: 'пяти', 6: 'шести', 7: 'семи', 8: 'восьми', 9: 'девяти',
               10: 'десяти', 11: 'одиннадцати', 12: 'двенадцати', 20: 'двадцати', 30: 'тридцати', 40: 'сорока',
               50: 'пятидесяти', 60: 'шестидесяти', 70: 'семидесяти', 80: 'восьмидесяти', 90: 'девяноста',
               100: 'сто', 200: 'двухсот', 300: 'трёхсот', 400: 'четырёхсот', 500: 'пятисот'}
_SCALE_ORD = {10 ** 3: 'тысячный', 10 ** 6: 'миллионный', 10 ** 9: 'миллиардный', 10 ** 12: 'триллионный'}


def plural(n, forms):
    """forms = (1, 2-4, 5+) e.g. ('рубль','рубля','рублей')"""
    n = abs(int(n))
    if 11 <= n % 100 <= 14:
        return forms[2]
    if n % 10 == 1:
        return forms[0]
    if 2 <= n % 10 <= 4:
        return forms[1]
    return forms[2]


def _triple(n, g):
    out = []
    h, r = divmod(n, 100)
    if h:
        out.append(_HUND[h])
    if 10 <= r < 20:
        out.append(_TEENS[r - 10])
    else:
        t, u = divmod(r, 10)
        if t:
            out.append(_TENS[t])
        if u:
            out.append(_U[g][u])
    return out


def cardinal(n, gender='m'):
    n = int(n)
    if n == 0:
        return 'ноль'
    if n < 0:
        return 'минус ' + cardinal(-n, gender)
    out = []
    for val, g, forms in _SCALES:
        if n >= val:
            k, n = divmod(n, val)
            if k >= 1000:
                out.append(cardinal(k, g))
            elif not (k == 1 and val == 1000):
                out += _triple(k, g)
            out.append(plural(k, forms))
    if n:
        out += _triple(n, gender)
    return ' '.join(out)


def _ord_word_lt1000(n):
    """ordinal words for 1..999 (last word ordinal)."""
    h, r = divmod(n, 100)
    words = []
    if r == 0:
        return [_OHUND[h]]
    if h:
        words.append(_HUND[h])
    if 10 <= r < 20:
        words.append(_OTEENS[r - 10])
    else:
        t, u = divmod(r, 10)
        if u == 0:
            words.append(_OTENS[t])
        else:
            if t:
                words.append(_TENS[t])
            words.append(_OU[u])
    return words


def ordinal(n, form='m_nom'):
    """Ordinal numeral. form: m_nom m_gen m_dat m_ins m_prep f_nom f_obl f_acc n_nom pl_nom pl_gen pl_dat pl_ins"""
    n = int(n)
    if n == 0:
        return decline_ordinal('нулевой', form)
    if n < 0:
        return 'минус ' + ordinal(-n, form)
    # find lowest non-zero group
    for val in (10 ** 12, 10 ** 9, 10 ** 6, 10 ** 3):
        if n % val == 0 and n >= val:
            k = n // val
            rest_high = (k // 1000) * 1000
            k_low = k % 1000
            prefix_words = []
            if rest_high:
                prefix_words.append(cardinal(rest_high * val, 'm'))
            if k_low == 1:
                stem = ''
            elif k_low in _GEN_PREFIX:
                stem = _GEN_PREFIX[k_low]
            else:
                h, r = divmod(k_low, 100)
                parts = []
                if h:
                    parts.append(_GEN_PREFIX.get(h * 100, _HUND[h]))
                if r:
                    if r in _GEN_PREFIX:
                        parts.append(_GEN_PREFIX[r])
                    else:
                        t, u = divmod(r, 10)
                        parts.append(_GEN_PREFIX[t * 10] + _GEN_PREFIX[u])
                stem = ''.join(parts)
            w = stem + _SCALE_ORD[val]
            words = prefix_words + [w]
            words[-1] = decline_ordinal(words[-1], form)
            return ' '.join(w for w in words if w)
    high, low = divmod(n, 1000)
    words = []
    if high:
        words.append(cardinal(high * 1000, 'm'))
    words += _ord_word_lt1000(low)
    words[-1] = decline_ordinal(words[-1], form)
    return ' '.join(words)


_ENDINGS_HARD = {'m_nom': None, 'm_gen': 'ого', 'm_dat': 'ому', 'm_ins': 'ым', 'm_prep': 'ом', 'f_nom': 'ая',
                 'f_obl': 'ой', 'f_acc': 'ую', 'n_nom': 'ое', 'pl_nom': 'ые', 'pl_gen': 'ых', 'pl_dat': 'ым',
                 'pl_ins': 'ыми'}
_ENDINGS_SOFT = {'m_nom': 'ий', 'm_gen': 'его', 'm_dat': 'ему', 'm_ins': 'им', 'm_prep': 'ем', 'f_nom': 'я',
                 'f_obl': 'ей', 'f_acc': 'ю', 'n_nom': 'е', 'pl_nom': 'и', 'pl_gen': 'их', 'pl_dat': 'им',
                 'pl_ins': 'ими'}


def decline_ordinal(word, form):
    if form == 'm_nom' or not word:
        return word
    if word == 'третий':
        return 'треть' + _ENDINGS_SOFT[form]
    stem = word[:-2]
    e = _ENDINGS_HARD[form]
    return stem + e


def decimal(int_part, frac_digits):
    """'3', '5' -> 'три целых пять десятых'"""
    n = int(int_part)
    words = cardinal(n, 'f') + ' ' + ('целая' if n % 10 == 1 and n % 100 != 11 else 'целых')
    k = len(frac_digits)
    m = int(frac_digits)
    if k > 3:
        return words + ' ' + ' '.join(_U['m'][int(d)] for d in frac_digits)
    den = {1: ('десятая', 'десятых'), 2: ('сотая', 'сотых'), 3: ('тысячная', 'тысячных')}[k]
    words += ' ' + cardinal(m, 'f') + ' ' + (den[0] if m % 10 == 1 and m % 100 != 11 else den[1])
    return words


def digits(s):
    return ' '.join(_U['m'][int(d)] for d in s if d.isdigit())


# ---------------------------------------------------------------- cardinal cases
_CASE_SMALL = {  # gen, dat, ins, prep
    1: {'m': ('одного', 'одному', 'одним', 'одном'), 'f': ('одной', 'одной', 'одной', 'одной'), 'n': ('одного', 'одному', 'одним', 'одном')},
    2: ('двух', 'двум', 'двумя', 'двух'), 3: ('трёх', 'трём', 'тремя', 'трёх'), 4: ('четырёх', 'четырём', 'четырьмя', 'четырёх'),
    8: ('восьми', 'восьми', 'восемью', 'восьми'), 40: ('сорока', 'сорока', 'сорока', 'сорока'),
    90: ('девяноста', 'девяноста', 'девяноста', 'девяноста'), 100: ('ста', 'ста', 'ста', 'ста'),
}
_CI = {'gen': 0, 'dat': 1, 'ins': 2, 'prep': 3}


def _word_case(w, case, g):
    i = _CI[case]
    nom = {'один': 1, 'одна': 1, 'одно': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'восемь': 8, 'сорок': 40,
           'девяносто': 90, 'сто': 100}
    if w in nom:
        v = _CASE_SMALL[nom[w]]
        if isinstance(v, dict):
            return v['f' if w == 'одна' else ('n' if w == 'одно' else g)][i]
        return v[i]
    if w.endswith('десят'):            # пятьдесят..восемьдесят
        head = w[:-5]
        hc = _word_case(head, case, g)
        return hc + ('ю' if case == 'ins' else '') + 'десяти' if case != 'ins' else hc + 'десятью'
    if w.endswith('сот') or w in ('двести', 'триста', 'четыреста'):
        hmap = {'двести': 2, 'триста': 3, 'четыреста': 4}
        if w in hmap:
            head = _CASE_SMALL[hmap[w]][i]
        else:
            head = _word_case(w[:-3], case, g)
        return head + {'gen': 'сот', 'dat': 'стам', 'ins': 'стами', 'prep': 'стах'}[case]
    if w.endswith('ь'):                # пять, шесть, семь, девять, десять, -надцать, двадцать, тридцать
        return w[:-1] + ('ью' if case == 'ins' else 'и')
    if w in ('тысяча',):
        return {'gen': 'тысячи', 'dat': 'тысяче', 'ins': 'тысячей', 'prep': 'тысяче'}[case]
    if w in ('тысячи', 'тысяч'):
        return {'gen': 'тысяч', 'dat': 'тысячам', 'ins': 'тысячами', 'prep': 'тысячах'}[case]
    if w.startswith('миллион') or w.startswith('миллиард') or w.startswith('триллион'):
        base = w.rstrip('аов') if not w.endswith('ов') else w[:-2]
        base = re.sub(r'(а|ов)$', '', w)
        if w.endswith('ов') or w.endswith('а') and not w.endswith('иона') and False:
            pass
        sing = w in ('миллион', 'миллиард', 'триллион')
        if sing:
            return base + {'gen': 'а', 'dat': 'у', 'ins': 'ом', 'prep': 'е'}[case]
        return base + {'gen': 'ов', 'dat': 'ам', 'ins': 'ами', 'prep': 'ах'}[case]
    return w


def cardinal_case(n, case='nom', gender='m'):
    """Cardinal numeral in a case: nom gen dat ins prep (accusative = nom for inanimate)."""
    w = cardinal(n, gender)
    if case == 'nom':
        return w
    return ' '.join(_word_case(x, case, gender) for x in w.split())
