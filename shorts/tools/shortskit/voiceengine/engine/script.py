# -*- coding: utf-8 -*-
"""Dialogue / script parsing and attribute parsing ("ж, 90, шёпотом, voice=Нюра")."""
import json
import re

from .characters import preset_name, emotion_name, effect_name
from .voices import BANK

GENDER_WORDS = {
    'м': 'male', 'м.': 'male', 'муж': 'male', 'муж.': 'male', 'мужской': 'male', 'мужчина': 'male',
    'male': 'male', 'm': 'male', 'man': 'male', 'мж': 'male',
    'ж': 'female', 'ж.': 'female', 'жен': 'female', 'жен.': 'female', 'женский': 'female', 'женщина': 'female',
    'female': 'female', 'f': 'female', 'w': 'female', 'woman': 'female', 'lady': 'female',
}
# role word -> (gender, age)
ROLES = {
    'бабушка': ('female', 80), 'бабуля': ('female', 80), 'бабка': ('female', 78), 'старушка': ('female', 82),
    'бабуся': ('female', 80), 'granny': ('female', 80), 'grandma': ('female', 80), 'grandmother': ('female', 80),
    'дедушка': ('male', 80), 'дед': ('male', 76), 'дедуля': ('male', 80), 'старик': ('male', 80),
    'grandpa': ('male', 80), 'grandfather': ('male', 80),
    'малыш': ('male', 4), 'малышка': ('female', 4), 'ребёнок': ('female', 6), 'ребенок': ('female', 6),
    'kid': ('female', 7), 'child': ('female', 7), 'baby': ('female', 3),
    'мальчик': ('male', 8), 'мальчишка': ('male', 10), 'boy': ('male', 8),
    'девочка': ('female', 8), 'девчонка': ('female', 10), 'girl': ('female', 8),
    'внук': ('male', 8), 'внучек': ('male', 7), 'внучок': ('male', 7), 'внучка': ('female', 8),
    'сын': ('male', 10), 'сынок': ('male', 9), 'son': ('male', 10), 'дочь': ('female', 10),
    'дочка': ('female', 9), 'daughter': ('female', 10),
    'подросток': ('male', 15), 'teen': ('male', 15), 'teenager': ('male', 15),
    'школьник': ('male', 12), 'школьница': ('female', 12),
    'парень': ('male', 20), 'юноша': ('male', 19), 'guy': ('male', 22), 'девушка': ('female', 20),
    'студент': ('male', 20), 'студентка': ('female', 20),
    'мама': ('female', 38), 'мать': ('female', 42), 'mom': ('female', 38), 'mother': ('female', 42),
    'папа': ('male', 42), 'отец': ('male', 45), 'dad': ('male', 42), 'father': ('male', 45),
    'мужчина': ('male', 40), 'женщина': ('female', 40), 'тётя': ('female', 45), 'тетя': ('female', 45),
    'дядя': ('male', 45), 'учитель': ('male', 45), 'учительница': ('female', 45),
    'король': ('male', 55), 'king': ('male', 55), 'королева': ('female', 50), 'queen': ('female', 50),
    'царь': ('male', 60), 'царица': ('female', 45), 'принц': ('male', 20), 'prince': ('male', 20),
    'принцесса': ('female', 18), 'princess': ('female', 18), 'рыцарь': ('male', 30), 'knight': ('male', 30),
    'солдат': ('male', 25), 'капитан': ('male', 45), 'пират': ('male', 40),
}
MALE_A = set('никита илья фома кузьма лука савва миша мишка саша паша гоша петя вася коля ваня дима серёжа '
             'сережа лёша леша женя слава валера юра толя боря федя гриша витя лёва лева стёпа степа митя '
             'костя тёма тема вова сеня данила гаврила добрыня кеша жора лёня леня гена'.split())
KEYS = {
    'voice': 'voice', 'голос': 'voice', 'gender': 'gender', 'пол': 'gender', 'age': 'age', 'возраст': 'age',
    'preset': 'preset', 'персонаж': 'preset', 'тип': 'preset', 'emotion': 'emotion', 'эмоция': 'emotion',
    'effect': 'effect', 'effects': 'effect', 'эффект': 'effect', 'fx': 'effect', 'speed': 'speed',
    'скорость': 'speed', 'темп': 'speed', 'pitch': 'pitch', 'тон': 'pitch', 'высота': 'pitch',
    'formant': 'formant', 'тембр': 'formant', 'lang': 'lang', 'язык': 'lang', 'pause': 'pause',
    'пауза': 'pause', 'name': 'voice', 'seed': 'voice',
}
_NUM = re.compile(r'^(\d+(?:[.,]\d+)?)(?:-?(?:лет|год|года|летний|летняя|y|yo|y\.o\.|years?))?$')
PAUSE_RE = re.compile(r'\[\s*(?:пауза|pause|тишина|silence)\s*(\d+(?:[.,]\d+)?)?\s*(?:с|сек|s|sec)?\s*\]'
                      r'|<\s*break\s+time\s*=\s*["\']?(\d+(?:\.\d+)?)\s*(ms|s)?["\']?\s*/?>', re.I)


def parse_gender(g):
    if g is None:
        return None
    k = str(g).strip().lower()
    if k in GENDER_WORDS:
        return GENDER_WORDS[k]
    if k in ROLES:
        return ROLES[k][0]
    raise ValueError('unknown gender %r (use male/female, м/ж)' % g)


def guess_from_name(name):
    """(gender, age) hints from a character name like 'Бабушка Нюра' or 'Вася'."""
    if not name:
        return None, None
    words = [w.strip('.,!?;:()[]"«»').lower() for w in re.split(r'[\s_]+', name) if w.strip()]
    for w in words:
        if w in ROLES:
            return ROLES[w]
        p = preset_name(w)
        if p:
            return None, None
    w = words[0] if words else ''
    if w in MALE_A:
        return 'male', None
    if re.search(r'[а-яё]', w):
        return ('female' if re.search(r'[ая]$', w) else 'male'), None
    if re.search(r'[a-z]', w):
        return ('female' if re.search(r'(a|ah|ie|ine|elle|ette|een|ey|lyn)$', w) else 'male'), None
    return None, None


def parse_attrs(s, spec=None):
    """'ж, 90, шёпотом, voice=Нюра, speed=0.9' -> dict(gender='female', age=90, emotion='шёпотом', ...)"""
    spec = dict(spec or {})
    if not s:
        return spec
    unknown = []

    def kv(m):
        k = KEYS.get(m.group(1).lower())
        v = m.group(2).strip('"\'')
        if k is None:
            unknown.append(m.group(0))
            return ' '
        if k in ('age', 'speed', 'pitch', 'formant', 'pause'):
            spec[k] = float(v.replace(',', '.'))
        elif k == 'effect':
            spec['effect'] = (spec.get('effect') or []) + [e for e in re.split(r'[+/]', v) if e]
        elif k == 'gender':
            spec['gender'] = parse_gender(v)
        else:
            spec[k] = v
        return ' '

    s = re.sub(r'([A-Za-zА-Яа-яЁё_]+)\s*[=:]\s*("[^"]*"|\'[^\']*\'|[^,;|\s]+)', kv, s)
    for tok in re.split(r'[,;|/\s]+', s):
        t = tok.strip().lower()
        if not t or t in ('лет', 'год', 'года', 'years', 'year', 'old', 'yo'):
            continue
        m = _NUM.match(t)
        if m:
            spec['age'] = float(m.group(1).replace(',', '.'))
            continue
        if t in GENDER_WORDS:
            spec['gender'] = GENDER_WORDS[t]
            continue
        if t in ROLES:
            g, a = ROLES[t]
            spec.setdefault('gender', g)
            spec.setdefault('age', a)
            continue
        if t in BANK:
            spec['voice'] = t
            continue
        if t in ('ru', 'en', 'auto'):
            spec['lang'] = t
            continue
        p = preset_name(t)
        if p:
            spec['preset'] = p
            continue
        e = emotion_name(t)
        if e:
            spec['emotion'] = e
            continue
        fx = effect_name(t)
        if fx:
            spec['effect'] = (spec.get('effect') or []) + [fx]
            continue
        unknown.append(tok)
    if unknown:
        spec.setdefault('_unknown', []).extend(unknown)
    return spec


def _split_name_attrs(b):
    m = re.match(r'^\s*([^|,(]+?)\s*(?:[|,(]\s*(.*?))?\s*\)?\s*$', b)
    if not m:
        return b.strip(), ''
    return m.group(1).strip(), (m.group(2) or '')


_LINE_B = re.compile(r'^\s*\[(?P<b>[^\]]+)\]\s*:?\s*(?P<t>.*)$')
_LINE_N = re.compile(r'^\s*(?P<n>[^:\[\]()<>"«]{1,40}?)\s*(?:\((?P<a>[^)]*)\))?\s*:\s+(?P<t>.*\S.*)$')
_DECL = re.compile(r'^\s*@\s*(?P<n>[^:=]+?)\s*[:=]\s*(?P<a>.*)$')


def _plausible_name(n, declared):
    if n.lower() in declared:
        return True
    words = n.split()
    if not words or len(words) > 3:
        return False
    if any(w.strip('.').lower() in ROLES or preset_name(w) for w in words):
        return True
    if not words[0][:1].isupper():
        return False
    return len(words) == 1 or all(w[:1].isupper() for w in words)


def parse_text_script(text):
    """Returns list of items: {'type':'line','speaker':name,'spec':{...},'text':...} or {'type':'pause','sec':x}.
    Character specs are accumulated in 'characters'."""
    chars = {}
    items = []
    cur = None
    for raw in text.replace('\r', '').split('\n'):
        line = raw.strip()
        if not line:
            if items and items[-1]['type'] == 'line':
                items.append({'type': 'pause', 'sec': None})       # paragraph pause (default)
            continue
        if line.startswith('#') or line.startswith('//'):
            continue
        pm = PAUSE_RE.fullmatch(line)
        if pm:
            items.append({'type': 'pause', 'sec': _pause_sec(pm)})
            continue
        m = _DECL.match(line)
        if m:
            n = m.group('n').strip()
            chars[n.lower()] = parse_attrs(m.group('a'), chars.get(n.lower()))
            chars[n.lower()]['_name'] = n
            continue
        name, attrs, body = None, '', line
        mb = _LINE_B.match(line)
        if mb and not PAUSE_RE.match('[' + mb.group('b') + ']'):
            name, attrs = _split_name_attrs(mb.group('b'))
            body = mb.group('t')
        else:
            mn = _LINE_N.match(line)
            if mn and _plausible_name(mn.group('n').strip(), chars):
                name, attrs, body = mn.group('n').strip(), mn.group('a') or '', mn.group('t')
        line_spec = {}
        if name is not None:
            key = name.lower()
            known = key in chars
            base = dict(chars.get(key, {'_name': name}))
            if attrs:
                a = parse_attrs(attrs)
                # emotion in a line is for this line only; effects too, once the character is known
                if 'emotion' in a:
                    line_spec['emotion'] = a.pop('emotion')
                if known and 'effect' in a:
                    line_spec['effect'] = a.pop('effect')
                if a.get('_unknown') and base.get('_unknown'):
                    a['_unknown'] = base['_unknown'] + a['_unknown']
                base.update(a)
            chars[key] = base
            cur = key
        # leading "(шёпотом)" style stage direction
        sd = re.match(r'^\s*\(([^)]{1,40})\)\s*(.*)$', body)
        if sd:
            a = parse_attrs(sd.group(1))
            if not a.get('_unknown'):
                line_spec.update(a)
                body = sd.group(2)
        body = re.sub(r'^\s*[—–-]\s*', '', body)
        if not body.strip():
            continue
        items.append({'type': 'line', 'speaker': cur, 'line_spec': line_spec, 'text': body})
    # resolve speaker specs
    for it in items:
        if it['type'] == 'line':
            sp = dict(chars.get(it['speaker'], {})) if it['speaker'] else {}
            it['name'] = sp.pop('_name', None) if sp else None
            it['spec'] = sp
    return items, chars


def _pause_sec(m):
    if m.group(1):
        return float(m.group(1).replace(',', '.'))
    if m.group(2):
        v = float(m.group(2))
        return v / 1000.0 if (m.group(3) or 's') == 'ms' else v
    return 0.8


def parse_json_script(obj):
    """JSON: [{"speaker": "...", "gender": "female", "age": 90, "text": "..."}, {"pause": 1.0}, ...]
    or {"characters": {"Бабушка": {"gender": "female", "age": 90}}, "lines": [...]}."""
    chars = {}
    lines = obj
    if isinstance(obj, dict):
        for n, a in (obj.get('characters') or obj.get('voices') or {}).items():
            chars[n.lower()] = _json_spec(a)
            chars[n.lower()]['_name'] = n
        lines = obj.get('lines') or obj.get('script') or []
    items = []
    for ln in lines:
        if isinstance(ln, str):
            items.append({'type': 'line', 'speaker': None, 'name': None, 'spec': {}, 'line_spec': {}, 'text': ln})
            continue
        if 'pause' in ln and not ln.get('text'):
            items.append({'type': 'pause', 'sec': float(ln['pause'])})
            continue
        sp = ln.get('speaker') or ln.get('name') or ln.get('character')
        base = dict(chars.get(sp.lower(), {})) if sp else {}
        base.update(_json_spec(ln))
        name = base.pop('_name', sp)
        items.append({'type': 'line', 'speaker': sp.lower() if sp else None, 'name': name, 'spec': base,
                      'line_spec': {}, 'text': ln.get('text', '')})
        if ln.get('pause_after'):
            items.append({'type': 'pause', 'sec': float(ln['pause_after'])})
    return items, chars


def _json_spec(a):
    sp = {}
    for k, v in a.items():
        kk = KEYS.get(str(k).lower(), str(k).lower())
        if kk in ('voice', 'preset', 'emotion', 'lang'):
            sp[kk] = v
        elif kk == 'gender':
            sp['gender'] = parse_gender(v)
        elif kk in ('age', 'speed', 'pitch', 'formant'):
            sp[kk] = float(v)
        elif kk == 'effect':
            sp['effect'] = v if isinstance(v, list) else [e for e in re.split(r'[+/,\s]+', str(v)) if e]
        elif kk == 'attrs':
            sp = parse_attrs(v, sp)
    return sp


def load_script(text):
    t = text.lstrip('\ufeff').strip()
    if t[:1] in '[{':
        try:
            return parse_json_script(json.loads(t))
        except ValueError:
            pass
    return parse_text_script(t)
