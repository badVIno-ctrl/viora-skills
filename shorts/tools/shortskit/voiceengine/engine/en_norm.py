# -*- coding: utf-8 -*-
"""Small English text normaliser (things espeak-ng reads badly)."""
import re

_ONES = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven',
         'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
_TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
_TENS_PL = {'ten': 'tens', 'twenty': 'twenties', 'thirty': 'thirties', 'forty': 'forties', 'fifty': 'fifties',
            'sixty': 'sixties', 'seventy': 'seventies', 'eighty': 'eighties', 'ninety': 'nineties'}


def _two(n):
    if n < 20:
        return _ONES[n]
    t, o = divmod(n, 10)
    return _TENS[t] + ('-' + _ONES[o] if o else '')


def year_words(y):
    y = int(y)
    hi, lo = divmod(y, 100)
    if 2000 <= y <= 2009:
        return 'two thousand' + (' ' + _ONES[lo] if lo else '')
    if lo == 0:
        return _two(hi) + ' hundred'
    if lo < 10:
        return _two(hi) + ' oh ' + _ONES[lo]
    return _two(hi) + ' ' + _two(lo)


_ABBR = [
    (r'\bMrs\.', 'Missus'), (r'\bMr\.', 'Mister'), (r'\bMs\.', 'Miz'), (r'\bDr\.', 'Doctor'),
    (r'\bProf\.', 'Professor'), (r'\bSt\.(?=\s+[A-Z])', 'Saint'), (r'\bJr\.', 'Junior'), (r'\bSr\.', 'Senior'),
    (r'\bvs\.?(?=\s)', 'versus'), (r'\be\.g\.', 'for example'), (r'\bi\.e\.', 'that is'),
    (r'\bNo\.\s*(?=\d)', 'number '), (r'\bapprox\.', 'approximately'), (r'\bDept\.', 'Department'),
    (r'\bMt\.', 'Mount'), (r'\bAve\.', 'Avenue'), (r'\bInc\.', 'Incorporated'), (r'\bLtd\.', 'Limited'),
]
_YEAR_CTX = r'(?:in|since|of|by|from|to|until|till|year|around|after|before|circa|early|late|mid|the|summer|winter|spring|autumn|fall)'


def _money(m, unit, sub):
    whole = m.group(1).replace(',', '')
    frac = m.group(2)
    big = m.group(3)
    if big:
        return '%s %s %s' % (m.group(1) + ('.' + frac if frac else ''), big, unit + 's')
    w = int(whole) if whole else 0
    s = '%s %s' % (whole, unit + ('' if w == 1 else 's'))
    if frac and int(frac):
        f = int(frac.ljust(2, '0')[:2])
        s += ' and %d %s' % (f, sub[0] if f == 1 else sub[1])
    return s


def normalize_en(t):
    t = t.replace('’', "'").replace('‘', "'")
    t = re.sub(r'[«»„“”"]', '', t)
    t = t.replace('...', '…')
    for rx, rep in _ABBR:
        t = re.sub(rx, rep, t)
    t = re.sub(r'\betc\.(\s+[A-Z]|\s*$)', r'et cetera.\1', t)
    t = re.sub(r'\betc\.', 'et cetera', t)
    big = r'(?:\s*(million|billion|trillion|thousand))?'
    t = re.sub(r'\$(\d[\d,]*)(?:\.(\d+))?' + big, lambda m: _money(m, 'dollar', ('cent', 'cents')), t)
    t = re.sub(r'£(\d[\d,]*)(?:\.(\d+))?' + big, lambda m: _money(m, 'pound', ('penny', 'pence')), t)
    t = re.sub(r'€(\d[\d,]*)(?:\.(\d+))?' + big, lambda m: _money(m, 'euro', ('cent', 'cents')), t)
    # decades: 1990s, '90s
    t = re.sub(r"\b(1[1-9]|20)(\d)0'?s\b", lambda m: (year_words(int(m.group(1) + m.group(2) + '0')).rsplit(' ', 1)[0] + ' ' +
               _TENS_PL.get(_two(int(m.group(2) + '0')), _two(int(m.group(2) + '0')) + 's')) if m.group(2) != '0'
               else _two(int(m.group(1))) + ' hundreds', t)
    t = re.sub(r"'([1-9])0s\b", lambda m: _TENS_PL.get(_two(int(m.group(1) + '0')), ''), t)
    # years after a context word or with AD/BC
    t = re.sub(r'\b(' + _YEAR_CTX + r')\s+(1[1-9]\d\d|20[1-9]\d)\b(?![.,]\d|%)',
               lambda m: m.group(1) + ' ' + year_words(m.group(2)), t, flags=re.I)
    t = re.sub(r'\b(1[0-9]\d\d|20\d\d)\s*(AD|BC|BCE|CE)\b', lambda m: year_words(m.group(1)) + ' ' + ' '.join(m.group(2)), t)
    t = re.sub(r'(\d),(\d{3})\b', r'\1\2', t)
    t = re.sub(r'(\d),(\d{3})\b', r'\1\2', t)
    t = t.replace('&', ' and ').replace('@', ' at ').replace('#', ' number ')
    t = re.sub(r'[ \t]+', ' ', t)
    return t.strip()
