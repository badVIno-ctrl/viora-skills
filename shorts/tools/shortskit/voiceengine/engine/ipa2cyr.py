# -*- coding: utf-8 -*-
"""English IPA (espeak-ng) -> approximate Russian Cyrillic with '+' stress.
Used to read Latin-script words inside Russian text (names, brands, English words)."""
import re

_V = {  # vowels / diphthongs (longest first)
    'aɪə': 'айэ', 'aʊə': 'ауэ', 'eɪ': 'эй', 'aɪ': 'ай', 'aʊ': 'ау', 'ɔɪ': 'ой', 'oʊ': 'оу', 'əʊ': 'оу',
    'ɪə': 'иэ', 'eə': 'эа', 'ʊə': 'уэ', 'iː': 'и', 'uː': 'у', 'ɑː': 'а', 'ɔː': 'о', 'ɜː': 'ё', 'i': 'и',
    'ɪ': 'и', 'ᵻ': 'и', 'e': 'е', 'ɛ': 'э', 'æ': 'э', 'ɑ': 'а', 'ɒ': 'о', 'ɔ': 'о', 'o': 'о', 'ʊ': 'у',
    'u': 'у', 'ʌ': 'а', 'ə': 'э', 'ɐ': 'а', 'ɚ': 'эр', 'ɝ': 'ёр', 'a': 'а', 'ɜ': 'ё', 'y': 'ю',
}
_C = {
    'tʃ': 'ч', 'dʒ': 'дж', 'p': 'п', 'b': 'б', 't': 'т', 'd': 'д', 'k': 'к', 'ɡ': 'г', 'g': 'г', 'f': 'ф',
    'v': 'в', 'θ': 'с', 'ð': 'з', 's': 'с', 'z': 'з', 'ʃ': 'ш', 'ʒ': 'ж', 'h': 'х', 'm': 'м', 'n': 'н',
    'ŋ': 'нг', 'l': 'л', 'ɫ': 'л', 'ɹ': 'р', 'r': 'р', 'ɾ': 'т', 'ʔ': '', 'x': 'х', 'ç': 'х', 'w': 'у',
    'j': 'й', 'ʍ': 'у', 'n̩': 'н', 'l̩': 'л',
}
_IOT = {'а': 'я', 'у': 'ю', 'э': 'е', 'о': 'ё', 'е': 'е', 'и': 'и', 'ё': 'ё'}
_VOW_CYR = set('аеёиоуыэюя')


def _tokens(ipa):
    keys = sorted(list(_V) + list(_C), key=len, reverse=True)
    i, out = 0, []
    while i < len(ipa):
        ch = ipa[i]
        if ch in 'ˈˌ':
            out.append(('S', ch)); i += 1; continue
        if ch in 'ː̩̃ʲ‿':
            i += 1; continue
        for k in keys:
            if ipa.startswith(k, i):
                out.append(('V' if k in _V else 'C', k)); i += len(k); break
        else:
            i += 1
    return out


def ipa_word_to_cyr(ipa):
    toks = _tokens(ipa)
    res = []
    stress_next = False
    have_stress = any(t == ('S', 'ˈ') for t in toks)
    i = 0
    while i < len(toks):
        typ, v = toks[i]
        if typ == 'S':
            stress_next = (v == 'ˈ') or (not have_stress and v == 'ˌ')
            i += 1; continue
        if typ == 'C' and v == 'j' and i + 1 < len(toks) and toks[i + 1][0] in ('V', 'S'):
            # j + vowel -> iotated vowel (after consonant add soft sign)
            j = i + 1
            st = False
            if toks[j][0] == 'S':
                st = toks[j][1] == 'ˈ'; j += 1
            if j < len(toks) and toks[j][0] == 'V':
                cyr = _V[toks[j][1]]
                first = _IOT.get(cyr[0], cyr[0])
                prev = res[-1] if res else ''
                if prev and prev[-1] not in _VOW_CYR and prev[-1] != 'ь':
                    res.append('ь')
                res.append(('+' if (st or stress_next) else '') + first + cyr[1:])
                stress_next = False
                i = j + 1; continue
        if typ == 'C' and v == 'w' and i + 1 < len(toks) and toks[i + 1][0] == 'V':
            res.append('у'); i += 1; continue
        if typ == 'V':
            cyr = _V[v]
            if stress_next:
                cyr = '+' + cyr
                stress_next = False
            res.append(cyr)
        else:
            res.append(_C.get(v, ''))
        i += 1
    w = ''.join(res)
    w = re.sub(r'(?<=[бвгджзклмнпрстфхцчшщ])э(?=л$)', '', w)      # 'gəl' -> 'гл' (google)
    w = w.replace('йи', 'и').replace('уу', 'у')
    if w.count('+') > 1:
        k = w.index('+')
        w = w[:k + 1] + w[k + 1:].replace('+', '')
    return w


def ipa_to_cyr(ipa_text):
    return ' '.join(ipa_word_to_cyr(w) for w in ipa_text.split())
