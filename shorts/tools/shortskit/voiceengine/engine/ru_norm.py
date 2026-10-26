# -*- coding: utf-8 -*-
"""Russian text normalisation for TTS: numbers, units, symbols, abbreviations,
Latin-script words (read via English phonemes), stress marks (+ or U+0301)."""
import re
import unicodedata

from .ru_numbers import cardinal, ordinal, decimal, digits, plural, cardinal_case

_RU_VOW = 'аеёиоуыэюяАЕЁИОУЫЭЮЯ'

# unit -> (forms 1/2-4/5+, gender, genitive-singular for decimals)
UNITS = {
    '%': (('процент', 'процента', 'процентов'), 'm'),
    '‰': (('промилле', 'промилле', 'промилле'), 'n'),
    '₽': (('рубль', 'рубля', 'рублей'), 'm'),
    'руб': (('рубль', 'рубля', 'рублей'), 'm'),
    'р': (('рубль', 'рубля', 'рублей'), 'm'),
    'коп': (('копейка', 'копейки', 'копеек'), 'f'),
    '$': (('доллар', 'доллара', 'долларов'), 'm'),
    '€': (('евро', 'евро', 'евро'), 'n'),
    '£': (('фунт', 'фунта', 'фунтов'), 'm'),
    '¥': (('юань', 'юаня', 'юаней'), 'm'),
    '₴': (('гривна', 'гривны', 'гривен'), 'f'),
    '₸': (('тенге', 'тенге', 'тенге'), 'n'),
    'кг': (('килограмм', 'килограмма', 'килограммов'), 'm'),
    'г': (('грамм', 'грамма', 'граммов'), 'm'),
    'мг': (('миллиграмм', 'миллиграмма', 'миллиграммов'), 'm'),
    'т': (('тонна', 'тонны', 'тонн'), 'f'),
    'км': (('километр', 'километра', 'километров'), 'm'),
    'м': (('метр', 'метра', 'метров'), 'm'),
    'см': (('сантиметр', 'сантиметра', 'сантиметров'), 'm'),
    'мм': (('миллиметр', 'миллиметра', 'миллиметров'), 'm'),
    'л': (('литр', 'литра', 'литров'), 'm'),
    'мл': (('миллилитр', 'миллилитра', 'миллилитров'), 'm'),
    'ч': (('час', 'часа', 'часов'), 'm'),
    'мин': (('минута', 'минуты', 'минут'), 'f'),
    'сек': (('секунда', 'секунды', 'секунд'), 'f'),
    'с': (('секунда', 'секунды', 'секунд'), 'f'),
    'мс': (('миллисекунда', 'миллисекунды', 'миллисекунд'), 'f'),
    '°c': (('градус Цельсия', 'градуса Цельсия', 'градусов Цельсия'), 'm'),
    '°с': (('градус Цельсия', 'градуса Цельсия', 'градусов Цельсия'), 'm'),
    '°': (('градус', 'градуса', 'градусов'), 'm'),
    'км/ч': (('километр в час', 'километра в час', 'километров в час'), 'm'),
    'м/с': (('метр в секунду', 'метра в секунду', 'метров в секунду'), 'm'),
    'кб': (('килобайт', 'килобайта', 'килобайт'), 'm'),
    'мб': (('мегабайт', 'мегабайта', 'мегабайт'), 'm'),
    'гб': (('гигабайт', 'гигабайта', 'гигабайт'), 'm'),
    'тб': (('терабайт', 'терабайта', 'терабайт'), 'm'),
    'гц': (('герц', 'герца', 'герц'), 'm'),
    'кгц': (('килогерц', 'килогерца', 'килогерц'), 'm'),
    'вт': (('ватт', 'ватта', 'ватт'), 'm'),
    'квт': (('киловатт', 'киловатта', 'киловатт'), 'm'),
    'тыс': (('тысяча', 'тысячи', 'тысяч'), 'f'),
    'млн': (('миллион', 'миллиона', 'миллионов'), 'm'),
    'млрд': (('миллиард', 'миллиарда', 'миллиардов'), 'm'),
    'трлн': (('триллион', 'триллиона', 'триллионов'), 'm'),
    'чел': (('человек', 'человека', 'человек'), 'm'),
    'шт': (('штука', 'штуки', 'штук'), 'f'),
    'стр': (('страница', 'страницы', 'страниц'), 'f'),
    'лет': (('год', 'года', 'лет'), 'm'),
}
_UNIT_RE = '|'.join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))

_MONTHS = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября',
           'ноября', 'декабря')
_GEN_PREP = {'до', 'с', 'со', 'от', 'после', 'около', 'из', 'без', 'для', 'у', 'кроме', 'начиная', 'вплоть'}
_DAT_PREP = {'к', 'ко', 'по'}
_PREP_PREP = {'в', 'во', 'о', 'об', 'при'}
_NOM_CTX = {'сегодня', 'завтра', 'вчера', 'уже', 'это', 'было', 'будет', 'наступило', 'наступит', 'наступает', 'дата', 'число'}

ABBR = [
    (r'\bт\.\s?е\.', 'то есть'), (r'\bт\.\s?к\.', 'так как'), (r'\bи\s+т\.\s?д\.', 'и так далее'),
    (r'\bи\s+т\.\s?п\.', 'и тому подобное'), (r'\bт\.\s?н\.', 'так называемый'), (r'\bв\s+т\.\s?ч\.', 'в том числе'),
    (r'\bт\.\s?о\.', 'таким образом'), (r'\bдо\s+н\.\s?э\.', 'до нашей эры'), (r'\bн\.\s?э\.', 'нашей эры'),
    (r'\bи\s+др\.', 'и другие'), (r'\bи\s+пр\.', 'и прочее'), (r'\bнапр\.', 'например'), (r'\bсм\.(?=\s+[А-Яа-яЁё])', 'смотри'),
    (r'\bул\.', 'улица'), (r'\bпросп\.', 'проспект'), (r'\bпер\.', 'переулок'), (r'\bпл\.', 'площадь'),
    (r'\bд\.(?=\s*\d)', 'дом'), (r'\bкв\.(?=\s*\d)', 'квартира'), (r'\bим\.', 'имени'), (r'\bакад\.', 'академик'),
    (r'\bпроф\.', 'профессор'), (r'\bдоц\.', 'доцент'), (r'\bтел\.', 'телефон'), (r'\bг-н\b', 'господин'),
    (r'\bг-жа\b', 'госпожа'), (r'\bок\.(?=\s*\d)', 'около'), (r'\bприм\.', 'примечание'), (r'\bсокр\.', 'сокращённо'),
    (r'\bгг\.', 'годы'), (r'\bвв\.', 'века'), (r'\bрис\.', 'рисунок'), (r'\bтабл\.', 'таблица'), (r'\bгл\.', 'глава'),
    (r'\bобл\.', 'область'), (r'\bр-н\b', 'район'), (r'\bр\.(?=\s+[А-ЯЁ])', 'река'), (r'\bоз\.(?=\s+[А-ЯЁ])', 'озеро'),
    (r'\bзам\.', 'заместитель'), (r'\bмлн\.?(?!\w)', 'миллионов'), (r'\bмлрд\.?(?!\w)', 'миллиардов'),
    (r'\bтыс\.(?!\w)', 'тысяч'), (r'\bруб\.(?!\w)', 'рублей'), (r'\bкоп\.(?!\w)', 'копеек'),
]
_ABBR = [(re.compile(a, re.IGNORECASE), b) for a, b in ABBR]
_ABBR_PRE = [(re.compile(a, re.IGNORECASE), b) for a, b in ABBR if '\\d' in a]
_CASE_PREP = {'до': 'gen', 'от': 'gen', 'около': 'gen', 'из': 'gen', 'без': 'gen', 'для': 'gen', 'у': 'gen',
              'после': 'gen', 'кроме': 'gen', 'с': 'gen', 'со': 'gen', 'свыше': 'gen', 'более': 'gen',
              'менее': 'gen', 'больше': 'gen', 'меньше': 'gen', 'среди': 'gen', 'против': 'gen', 'возле': 'gen',
              'к': 'dat', 'ко': 'dat', 'благодаря': 'dat', 'согласно': 'dat', 'о': 'prep', 'об': 'prep', 'при': 'prep'}

# Cyrillic acronyms that are spelled letter by letter
_LETTERS = {'А': 'а', 'Б': 'бэ', 'В': 'вэ', 'Г': 'гэ', 'Д': 'дэ', 'Е': 'е', 'Ё': 'ё', 'Ж': 'жэ', 'З': 'зэ', 'И': 'и',
            'Й': 'и краткое', 'К': 'ка', 'Л': 'эл', 'М': 'эм', 'Н': 'эн', 'О': 'о', 'П': 'пэ', 'Р': 'эр', 'С': 'эс',
            'Т': 'тэ', 'У': 'у', 'Ф': 'эф', 'Х': 'ха', 'Ц': 'цэ', 'Ч': 'чэ', 'Ш': 'ша', 'Щ': 'ща', 'Ъ': 'твёрдый знак',
            'Ы': 'ы', 'Ь': 'мягкий знак', 'Э': 'э', 'Ю': 'ю', 'Я': 'я'}
_ACR_SPECIAL = {'США': 'сэ-шэ-+а', 'СССР': 'эс-эс-эс-+эр', 'МГУ': 'эм-гэ-+у', 'ЖКХ': 'жэ-ка-х+а', 'РФ': 'эр-+эф',
                'ФСБ': 'эф-эс-б+э', 'ГИБДД': 'гэ-и-бэ-дэ-д+э', 'ДТП': 'дэ-тэ-п+э', 'МЧС': 'эм-чэ-+эс', 'ВВП': 'вэ-вэ-п+э',
                'НДС': 'эн-дэ-+эс', 'ООО': 'о-о-+о', 'ЗАО': 'зэ-а-+о', 'ОАО': 'о-а-+о', 'ИП': 'и-п+э', 'ПК': 'пэ-к+а',
                'ТВ': 'тэ-в+э', 'ИИ': 'и-+и', 'ЧП': 'чэ-п+э', 'РЖД': 'эр-жэ-д+э', 'ЦСКА': 'цэ-эс-к+а', 'СМС': 'эс-эм-+эс',
                'ЕС': 'е-+эс', 'ООН': 'о-+он', 'НЛО': 'эн-эл-+о', 'ЛДПР': 'эл-дэ-пэ-+эр', 'КПРФ': 'ка-пэ-эр-+эф',
                'МВД': 'эм-вэ-д+э', 'МИД': 'м+ид', 'ВУЗ': 'в+уз', 'ГОСТ': 'г+ост', 'ЗАГС': 'з+агс', 'МКАД': 'мк+ад',
                'СИЗО': 'сиз+о', 'ТАСС': 'т+асс', 'НАТО': 'н+ато', 'СНГ': 'эс-эн-г+э', 'ВОЗ': 'в+оз', 'ВКонтакте': 'вконт+акте'}


def _acronym(w):
    if w in _ACR_SPECIAL:
        return _ACR_SPECIAL[w]
    vow = sum(c in _RU_VOW for c in w)
    # pronounceable acronyms (consonant-vowel alternation) are read as words
    if vow >= 1 and len(w) >= 3 and re.fullmatch(r'([^АЕЁИОУЫЭЮЯ]?[АЕЁИОУЫЭЮЯ][^АЕЁИОУЫЭЮЯ]?)+', w) and not re.search(r'[^АЕЁИОУЫЭЮЯ]{3}', w):
        return w.lower()
    parts = [_LETTERS.get(c, c.lower()) for c in w]
    if parts:
        last = parts[-1]
        vi = [i for i, c in enumerate(last) if c.lower() in _RU_VOW]
        if vi and '+' not in last:
            parts[-1] = last[:vi[0]] + '+' + last[vi[0]:]
    return '-'.join(parts)


class RuNormalizer:
    def __init__(self, latin_reader=None):
        """latin_reader: callable(str)->str converting Latin words to Cyrillic (optional)."""
        self.latin_reader = latin_reader

    # --- stress marks -------------------------------------------------------------
    @staticmethod
    def _stress_marks(t):
        t = unicodedata.normalize('NFC', t)
        # combining acute / grave after a vowel -> '+' before vowel
        t = re.sub(r'([аеёиоуыэюяАЕЁИОУЫЭЮЯ])[\u0301\u0300]', r'+\1', t)
        t = t.replace('\u0301', '').replace('\u0300', '')
        # precomposed accented Cyrillic vowels (и́ etc. are decomposed by NFC already)
        return t

    def _numbers(self, t):
        t = re.sub(r'(^|[\s(])[-−–](?=\d)', r'\1минус ', t)
        t = re.sub(r'(^|[\s(])\+(?=\d)', r'\1плюс ', t)
        # phone numbers: +7 (916) 123-45-67, 8-916-123-45-67, 89161234567
        def phone(m):
            d = re.sub(r'\D', '', m.group(0))
            if len(d) == 11:
                groups = [d[0], d[1:4], d[4:7], d[7:9], d[9:11]]
            elif len(d) == 10:
                groups = [d[0:3], d[3:6], d[6:8], d[8:10]]
            else:
                groups = [d[i:i + 2] for i in range(0, len(d), 2)]
            out = []
            for g in groups:
                out.append(('ноль ' * (len(g) - len(g.lstrip('0')))) + (cardinal(int(g)) if g.lstrip('0') else '').strip() if g.startswith('0') else cardinal(int(g)))
            return ', '.join(o.strip() for o in out if o.strip())
        t = re.sub(r'(?<![\d])(?:плюс\s*)?\d[\d\s\-()]{8,16}\d(?![\d])', lambda m: phone(m) if 10 <= len(re.sub(r'\D', '', m.group(0))) <= 12 and re.search(r'[\-()]', m.group(0) + ' ') or len(re.sub(r'\D', '', m.group(0))) == 11 and re.fullmatch(r'(?:плюс\s*)?[78]\d{10}', m.group(0).replace(' ', '')) else m.group(0), t)
        # thousands separated by spaces / thin spaces: 13 274 285
        t = re.sub(r'(?<![\d.,])(\d{1,3})((?:[ \u00a0\u2009\u202f]\d{3})+)(?![\d])',
                   lambda m: m.group(1) + re.sub(r'\D', '', m.group(2)), t)
        # time 14:30
        t = re.sub(r'\b([01]?\d|2[0-3]):([0-5]\d)\b',
                   lambda m: cardinal(int(m.group(1))) + ' ' + (('ноль ' + cardinal(int(m.group(2)))) if m.group(2).startswith('0') and m.group(2) != '00' else ('ровно' if m.group(2) == '00' else cardinal(int(m.group(2))))), t)
        t = re.sub(r'\b(\d{1,3}):(\d{1,3})\b', r'\1-\2', t)
        # dates 25.12.2023
        def date(m):
            d, mo, y = int(m.group(1)), int(m.group(2)), m.group(3)
            if not (1 <= d <= 31 and 1 <= mo <= 12):
                return m.group(0)
            yy = int(y) if len(y) == 4 else 2000 + int(y)
            return ordinal(d, 'm_gen') + ' ' + _MONTHS[mo - 1] + ' ' + ordinal(yy, 'm_gen') + ' года'
        t = re.sub(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})\b', date, t)
        # short dates 25.12 / 01.05 (two-digit month, not a price / measurement) -> "25 декабря"
        t = re.sub(r'(?<![\d.,])(0?[1-9]|[12]\d|3[01])\.(0[1-9]|1[0-2])(?!\d|[.,]\d)'
                   r'(?!\s*(?:%|руб|р\.|₽|\$|€|£|коп|кг|км|м\b|см|мм|г\b|гр|л\b|мл|шт|тыс|млн|млрд|°|градус))',
                   lambda m: '%d %s' % (int(m.group(1)), _MONTHS[int(m.group(2)) - 1]), t)
        # roman centuries: XX век
        def roman(m):
            r = m.group(1).upper()
            vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
            n = 0
            for i, ch in enumerate(r):
                v = vals[ch]
                n += -v if i + 1 < len(r) and vals[r[i + 1]] > v else v
            w = m.group(2).lower()
            form = {'век': 'm_nom', 'века': 'm_gen', 'веке': 'm_prep', 'веку': 'm_dat', 'веком': 'm_ins',
                    'в.': 'm_nom', 'вв.': 'pl_nom', 'столетие': 'n_nom', 'съезд': 'm_nom', 'съезда': 'm_gen'}.get(w, 'm_nom')
            word = {'в.': 'век', 'вв.': 'века'}.get(w, m.group(2))
            return ordinal(n, form) + ' ' + word
        t = re.sub(r'\b([IVXLC]{1,7})\s+(век[а-я]*|в\.|вв\.|столетие|съезда?)', roman, t)
        # ordinal with suffix: 5-й, 21-го, 3-я
        sfx = {'й': 'm_nom', 'ый': 'm_nom', 'ий': 'm_nom', 'ой': 'm_nom', 'го': 'm_gen', 'ого': 'm_gen',
               'его': 'm_gen', 'му': 'm_dat', 'ому': 'm_dat', 'ему': 'm_dat', 'м': 'm_prep', 'ом': 'm_prep',
               'ем': 'm_prep', 'ым': 'm_ins', 'им': 'm_ins', 'я': 'f_nom', 'ая': 'f_nom', 'ья': 'f_nom',
               'ю': 'f_acc', 'ую': 'f_acc', 'е': 'n_nom', 'ое': 'n_nom', 'ье': 'n_nom', 'х': 'pl_gen',
               'ых': 'pl_gen', 'их': 'pl_gen', 'ми': 'pl_ins', 'ыми': 'pl_ins', 'ей': 'f_obl', 'ой ': 'f_obl', 'е ': 'n_nom'}
        t = re.sub(r'\b(\d*0)-(е|ые|х|ых|м|ым|ми|ыми)\b',
                   lambda m: ordinal(int(m.group(1)), {'е': 'pl_nom', 'ые': 'pl_nom', 'х': 'pl_gen', 'ых': 'pl_gen',
                                                       'м': 'pl_dat', 'ым': 'pl_dat', 'ми': 'pl_ins', 'ыми': 'pl_ins'}[m.group(2)]), t)
        t = re.sub(r'\b(\d+)-(ый|ий|ой|й|ого|его|го|ому|ему|му|ом|ем|м|ым|им|ая|ья|я|ую|ю|ое|ье|е|ых|их|х|ыми|ми|ей)\b',
                   lambda m: ordinal(int(m.group(1)), sfx[m.group(2)]), t)
        # years: 1999 год / году / года / г.
        def year(m):
            pre = (m.group(1) or '').strip().lower()
            n = int(m.group(2))
            w = m.group(3).lower()
            if len(m.group(2)) < 3 and w not in ('г.', 'гг.'):
                c = _CASE_PREP.get(pre, 'nom')
                return (m.group(1) or '') + cardinal_case(n, c) + ' ' + m.group(3)
            if w in ('г.', 'г'):
                form = 'm_prep' if pre in _PREP_PREP else ('m_dat' if pre in _DAT_PREP else 'm_gen')
                word = {'m_prep': 'году', 'm_dat': 'году', 'm_gen': 'года'}[form]
            elif w in ('гг.', 'гг'):
                form, word = 'pl_nom', 'годы'
            else:
                form = {'год': 'm_nom', 'года': 'm_gen', 'году': 'm_prep' if pre in _PREP_PREP else 'm_dat',
                        'годом': 'm_ins', 'годах': 'pl_gen', 'годы': 'pl_nom', 'годов': 'pl_gen'}.get(w, 'm_nom')
                if w == 'годах':
                    form = 'pl_prep'
                word = m.group(3)
            if form == 'pl_prep':
                return (m.group(1) or '') + ordinal(n, 'pl_gen') + ' ' + word
            return (m.group(1) or '') + ordinal(n, form) + ' ' + word
        t = re.sub(r'(\b[А-Яа-яЁё]+\s+)?\b(\d{1,4})\s*(год|года|году|годом|годах|годы|годов|гг\.|г\.)(?![а-яё])', year, t)
        # day + month (+ year)
        def daymonth(m):
            pre = (m.group(1) or '').strip().lower()
            form = 'm_dat' if pre in _DAT_PREP else ('n_nom' if pre in _NOM_CTX else 'm_gen')
            s = (m.group(1) or '') + ordinal(int(m.group(2)), form) + ' ' + m.group(3)
            if m.group(4):
                s += ' ' + ordinal(int(m.group(4)), 'm_gen') + (' года' if not m.group(5) else '')
            return s
        t = re.sub(r'(\b[А-Яа-яЁё]+\s+)?\b(\d{1,2})\s+(' + '|'.join(_MONTHS) + r')(?:\s+(\d{4})(\s*года|\s*г\.)?)?', daymonth, t)
        t = re.sub(r'(года)\s*г\.', r'\1', t)
        # currency prefix: $100
        t = re.sub(r'([$€£¥₽])\s?(\d+(?:[.,]\d+)?)', r'\2 \1', t)
        # number + unit
        def unit(m):
            pre, num, frac, u = (m.group(1) or ''), m.group(2), m.group(3), m.group(4)
            key = u.lower().rstrip('.')
            if key not in UNITS:
                key = u.lower()
            forms, g = UNITS[key]
            if frac:
                return pre + decimal(num, frac) + ' ' + forms[1]
            n = int(num)
            c = _CASE_PREP.get(pre.strip().lower(), 'nom')
            if c == 'gen':
                noun = forms[1] if (n % 10 == 1 and n % 100 != 11) else forms[2]
                return pre + cardinal_case(n, 'gen', g) + ' ' + noun
            return pre + cardinal(n, g) + ' ' + plural(n, forms)
        t = re.sub(r'(\b[А-Яа-яЁё]{1,8}\s+)?(?<![\w.,])(\d+)(?:[.,](\d+))?\s?(' + _UNIT_RE + r')\.?(?![А-Яа-яЁёA-Za-z])', unit, t, flags=re.IGNORECASE)
        # signs
        t = re.sub(r'(?<=\d)\s*\+\s*(?=\d)', ' плюс ', t)
        t = re.sub(r'(?<=\d)\s*[×*xх]\s*(?=\d)', ' на ', t)
        t = re.sub(r'(?<=\d)\s*=\s*(?=\d)', ' равно ', t)
        t = re.sub(r'(?<=\d)\s*/\s*(?=\d)', ' из ', t)
        t = re.sub(r'(?<=\d)\s*[-–—]\s*(?=\d)', '-', t)
        # decimals
        t = re.sub(r'(?<![\d.,])(\d+)[.,](\d+)(?![\d.,]*\d)', lambda m: decimal(m.group(1), m.group(2)), t)
        # № and plain numbers
        t = re.sub(r'№\s*', 'номер ', t)
        def plain_case(m):
            pre, s = m.group(1), m.group(2)
            c = _CASE_PREP.get(pre.lower(), 'nom')
            if len(s) > 15 or (len(s) > 1 and s.startswith('0')):
                return m.group(0)
            return pre + ' ' + cardinal_case(int(s), c)
        t = re.sub(r'(?<![А-Яа-яЁё])([А-Яа-яЁё]{1,8})\s+(\d+)(?![\d.,:])', plain_case, t)
        def plain(m):
            s = m.group(0)
            if len(s) > 15 or (len(s) > 1 and s.startswith('0')):
                return digits(s)
            return cardinal(int(s))
        t = re.sub(r'\d+', plain, t)
        return t

    def _latin(self, t):
        if not re.search(r'[A-Za-z]', t):
            return t
        def rep(m):
            w = m.group(0)
            if self.latin_reader is not None:
                try:
                    r = self.latin_reader(w)
                    if r:
                        return ' ' + r + ' '
                except Exception:
                    pass
            return ' ' + _simple_translit(w) + ' '
        return re.sub(r"[A-Za-z][A-Za-z'’\-]*(?:\s+[A-Za-z][A-Za-z'’\-]*)*", rep, t)

    def __call__(self, text):
        t = self._stress_marks(text)
        t = t.replace('\r', '')
        t = re.sub(r'[«»„“”"]', '', t)
        t = t.replace('...', '…').replace('?!', '?').replace('!?', '?')
        t = re.sub(r'([a-zA-Zа-яА-ЯёЁ])(\d)', r'\1 \2', t)
        t = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', t)
        for rx, rep in _ABBR_PRE:
            t = rx.sub(rep, t)
        t = self._numbers(t)
        for rx, rep in _ABBR:
            t = rx.sub(rep, t)
        t = re.sub(r'\b[А-ЯЁ]{2,6}\b', lambda m: _acronym(m.group(0)), t)
        t = self._latin(t)
        t = t.replace('&', ' и ').replace('@', ' собака ').replace('#', ' решётка ')
        t = re.sub(r'\s*!+', '.', t)            # model has no '!' -> sentence end
        t = re.sub(r'\s*;\s*', ', ', t)
        t = re.sub(r'[()\[\]{}]', ', ', t)
        t = re.sub(r'\s+([,.?:…])', r'\1', t)
        t = re.sub(r',\s*,', ',', t)
        t = re.sub(r'[ \t]+', ' ', t)
        return t.strip()


_TR = {'a': 'а', 'b': 'б', 'c': 'к', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'г', 'h': 'х', 'i': 'и', 'j': 'дж', 'k': 'к',
       'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р', 's': 'с', 't': 'т', 'u': 'у', 'v': 'в',
       'w': 'в', 'x': 'кс', 'y': 'й', 'z': 'з'}


def _simple_translit(w):
    w = w.lower()
    for a, b in (('sh', 'ш'), ('ch', 'ч'), ('th', 'т'), ('oo', 'у'), ('ee', 'и'), ('ph', 'ф'), ('ck', 'к')):
        w = w.replace(a, b)
    return ''.join(_TR.get(c, c) for c in w)
