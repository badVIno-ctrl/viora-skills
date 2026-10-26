"""Offline text and data rules for advertising cards. Heuristics, not legal review.

Every hit is a prompt for a human decision. A clean result never proves that a text is honest.
No network, no model calls. Russian and English stems; extend the tables, keep ids stable.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, unquote, urlsplit

# Claims that need a verified claim entry (stage launch: error, draft: warning).
RISKY = {
    'free': r'бесплатн|даром\b|\bfree\b|без\s+оплаты',
    'discount': r'скидк|акци[яиюе]\b|распродаж|\bsale\b|\d+\s*%',
    'no_fee': r'без\s+комисси|no\s+fee|zero\s+fee',
    'superlative': r'лучш|№\s*1|номер\s+один|\bbest\b|#\s*1\b|единственн|самы[йеая]\s+(быстр|дешев|дёшев|надеж|надёж|безопасн|точн)',
    'speed': r'мгновенн|за\s+\d+\s*(секунд|мин|час|дн)|\binstant|в\s+один\s+клик',
    'safety': r'безопасн|без\s+риска|risk[- ]free|надёжн|надежн|проверенн',
    'money': r'заработ|доход|прибыл|окупа|кэшбэк|кешбэк|cash\s*back|\bearn\b|\bprofit\b|пассивн',
    'authority': r'официальн|сертифицирован|одобрен|рекоменду(ют|ет)',
    'scarcity': r'только\s+сегодня|успей|осталось\s+\d|последн\w+\s+(шанс|мест)|ограниченн|до\s+конца\s+(дня|недели|месяца|акции)|today\s+only|limited\s+time|hurry',
    'promo': r'промокод|promo\s*code|подарок|бонус|\bbonus\b|\bgift\b',
    'guarantee': r'гарант|guarantee',
    'testimonial': r'отзыв|тысячи\s+(клиентов|пользователей)|тысяч\s+довольн|\d+\s*(тыс|000)\+?\s*(клиент|пользовател)',
}

# Never allowed in an advertising text, at any stage.
FORBIDDEN = {
    'guaranteed_income': (r'гарантирован\w*\s+(доход|заработ|прибыл|окупа|результат)|гарантируем\s+(доход|заработ|прибыл|окупа)|'
                          r'guaranteed\s+(income|profit|earnings|return)|100\s*%\s*(окупа|прибыл|доход)|быстрые\s+деньги|get\s+rich|'
                          r'без\s+вложений.{0,24}заработ'),
    'fake_authority': (r'врач\w*\s+(в\s+шоке|ненавидят|рекоменду)|эксперт\w*\s+(в\s+шоке|скрывают)|doctors?\s+hate|'
                       r'знаменитост|celebrit|скриншот\w*\s+(дохода|выплат)|income\s+screenshot|скрин\w*\s+выплат'),
}

GAMBLING = r'азарт|казино|букмекер|ставк\w*\s+на\s+спорт|\bcasino\b|\bbetting\b|\bgambl|\bслот(ы|ов)?\b|покер|лотере'
EARNING = r'заработ|доход|выигр|win\b|\bearn\b|прибыл'
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE = re.compile(r'(?<!\d)\+?\d[\d\s().-]{8,}\d(?!\d)')
SIGN_KEYS = {'sign', 'signature', 'sig', 'hash', 'token', 'hmac'}


def _norm(text):
    return re.sub(r'\s+', ' ', (text or '')).lower().replace('ё', 'е')


def risky_hits(text):
    """Return [(category, matched_text)] for risky phrases."""
    t = _norm(text)
    hits = []
    for cat, pattern in RISKY.items():
        for m in re.finditer(pattern.replace('ё', 'е'), t):
            hits.append((cat, m.group(0)))
    return hits


def forbidden_hits(text):
    t = _norm(text)
    return [(cat, m.group(0)) for cat, pattern in FORBIDDEN.items()
            for m in re.finditer(pattern.replace('ё', 'е'), t)]


def covered(hit, claims):
    """A hit is covered by a verified claim that names its category in covers or contains the matched stem."""
    cat, token = hit
    token = _norm(token)
    for claim in claims:
        if claim.get('verified') is not True:
            continue
        if cat in (claim.get('covers') or []):
            return True
        if token and token in _norm(claim.get('text')):
            return True
    return False


def word_count(text):
    return len(re.findall(r"[\wЁё][\wЁё'’-]*", text or ''))


def min_age(value):
    """Lower age bound from strings like '18+', '16-24', 'adults'. None if unknown."""
    if not value:
        return None
    t = _norm(str(value))
    m = re.search(r'\d{1,2}', t)
    if m:
        return int(m.group(0))
    if re.search(r'взросл|adult', t):
        return 18
    return None


def collect_texts(c):
    """All viewer-facing texts of a card: (label, text)."""
    out = [('headline', c.get('headline')), ('cta', c.get('cta'))]
    cr = c.get('creative') or {}
    for key in ('kicker', 'subline', 'badge', 'footnote'):
        out.append(('creative.' + key, cr.get(key)))
    proof = cr.get('proof') or {}
    for key in ('title', 'before_label', 'before', 'after_label', 'after', 'caption'):
        out.append(('creative.proof.' + key, proof.get(key)))
    for i, v in enumerate(c.get('variants') or []):
        out.append((f'variants[{i}].headline', v.get('headline')))
        out.append((f'variants[{i}].cta', v.get('cta')))
    return [(k, v) for k, v in out if isinstance(v, str) and v.strip()]


def url_privacy_issues(url, label='destination'):
    """PII in a URL (email, phone) or an unsafe parameter on a signed link."""
    errors, warnings = [], []
    if not url:
        return errors, warnings
    parts = urlsplit(url)
    decoded = unquote(url)
    if EMAIL.search(decoded):
        errors.append(f'{label} contains an e-mail address: never put personal data in UTM/SubID/links')
    query_text = unquote(parts.query)
    if PHONE.search(query_text):
        errors.append(f'{label} query contains a phone-like number: never put personal data in UTM/SubID/links')
    keys = {k.lower() for k, _ in parse_qsl(parts.query, keep_blank_values=True)}
    if keys & SIGN_KEYS and any(k.startswith('utm_') for k in keys):
        warnings.append(f'{label} has a signature-like parameter together with utm_*: '
                        'do not append parameters to a signed partner link without checking network rules')
    return errors, warnings


def text_issues(c, stage):
    """Lint viewer-facing texts. Returns (errors, warnings)."""
    errors, warnings = [], []
    claims = c.get('claims') or []
    for label, text in collect_texts(c):
        for cat, token in forbidden_hits(text):
            errors.append(f'{label}: forbidden promise/authority pattern [{cat}] "{token}"')
        for hit in risky_hits(text):
            if not covered(hit, claims):
                msg = f'{label}: "{hit[1]}" [{hit[0]}] needs a verified claim (claims[].text or covers)'
                (errors if stage == 'launch' else warnings).append(msg)
    heads = [('headline', c.get('headline'))] + [(f'variants[{i}].headline', v.get('headline')) for i, v in enumerate(c.get('variants') or [])]
    ctas = [('cta', c.get('cta'))] + [(f'variants[{i}].cta', v.get('cta')) for i, v in enumerate(c.get('variants') or [])]
    for label, text in heads:
        if text and not 3 <= word_count(text) <= 7:
            warnings.append(f'{label}: {word_count(text)} words; starting hypothesis is 3-7 [Г], check readability at real size')
    for label, text in ctas:
        if text and not 2 <= word_count(text) <= 4:
            warnings.append(f'{label}: {word_count(text)} words; starting hypothesis is 2-4 [Г]')
    gamble_text = ' '.join(filter(None, [c['offer'].get('name'), c['offer'].get('source'), c.get('headline'), c.get('cta'),
                                          c['offer'].get('payable_action')]))
    if re.search(GAMBLING, _norm(gamble_text)):
        viewer = ' '.join(t for _, t in collect_texts(c))
        if re.search(EARNING, _norm(viewer)):
            errors.append('gambling must not be presented as a way for the viewer to earn')
        ages = [min_age(c['audience'].get('age')), min_age(c['offer'].get('audience_age'))]
        if any(a is None or a < 18 for a in ages):
            (errors if stage == 'launch' else warnings).append('age-restricted (gambling-like) offer needs a confirmed audience of 18+')
    e, w = url_privacy_issues(c.get('destination'))
    errors += e
    warnings += w
    return errors, warnings
