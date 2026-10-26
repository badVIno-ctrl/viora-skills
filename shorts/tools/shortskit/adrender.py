"""Static advertising banner renderer. Typeset text over simple shapes, never text inside a generated image.

Reads campaign.json (headline, cta, creative, disclosure, canvas) and writes, per aspect ratio, a
colour PNG, a monochrome draft PNG, a 360 px preview and a layout report. It checks what a script can
check: contrast, text overflow, minimum phone size, platform safe zones, declared assets. It does NOT
check meaning, honesty, rights, or the real platform UI; the human review still decides.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import skill_root
from .util import ShortsError

RATIOS = {'9x16': (1080, 1920), '1x1': (1080, 1080), '4x5': (1080, 1350), '16x9': (1920, 1080)}
SS = 2  # supersampling
BOLD = 'assets/fonts/Manrope-Bold.ttf'
SEMI = 'assets/fonts/Manrope-SemiBold.ttf'
DEFAULT_BRAND = {'bg': '#FAF9F7', 'fg': '#202124', 'accent': '#1A5FC1'}
MONO_BRAND = {'bg': '#FFFFFF', 'fg': '#000000', 'accent': '#000000'}
PHONE_MIN_BODY = 14 / 360   # share of the short side: 14 px on a 360 px phone width [G]
PHONE_MIN_LABEL = 10 / 360


class Overflow(ShortsError):
    pass


def _hex(c):
    c = c.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _lum(rgb):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(_hex(a)), _lum(_hex(b))), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def _on(color):
    return '#FFFFFF' if contrast(color, '#FFFFFF') >= contrast(color, '#000000') else '#000000'


def _tint(color, bg, share=0.12):
    a, b = _hex(color), _hex(bg)
    return '#%02X%02X%02X' % tuple(round(b[i] * (1 - share) + a[i] * share) for i in range(3))


def _font(path, size):
    return ImageFont.truetype(str(skill_root() / path), max(int(size), 1))


def _wrap(text, font, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if font.getlength(w) > width:
            raise Overflow('word wider than box')
        trial = (cur + ' ' + w).strip()
        if font.getlength(trial) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(text, path, width, max_lines, size_max, size_min, leading=1.2):
    """Largest size in [size_min, size_max] whose wrapped text fits width and max_lines."""
    size = int(size_max)
    while size >= size_min:
        font = _font(path, size)
        try:
            lines = _wrap(text, font, width)
        except Overflow:
            lines = None
        if lines is not None and len(lines) <= max_lines:
            return {'font': font, 'lines': lines, 'size': size, 'h': int(len(lines) * size * leading), 'leading': leading, 'path': path}
        size -= 2
    raise Overflow(f'text does not fit at the minimum size {size_min}px: {text[:40]!r}')


def safe_box(w, h, platforms):
    """(left, top, right, bottom, exclusions, note) in canvas px."""
    zones = json.loads((skill_root() / 'schema/safe_zones.json').read_text(encoding='utf-8'))
    if (w, h) != (1080, 1920):
        m = int(min(w, h) * 0.06)
        return m, m, w - m, h - m, [], 'generic 6% margin; not a platform template for this ratio'
    top = bottom = left = right = 0
    excl = []
    used = []
    for name in platforms:
        z = zones.get(name)
        if z and 'alias' in z:
            z = zones[z['alias']]
        if not z:
            raise ShortsError(f'unknown platform {name!r}; known: ' + ', '.join(k for k in zones if not k.startswith('_')))
        top, bottom, left, right = max(top, z['top']), max(bottom, z['bottom']), max(left, z['left']), max(right, z['right'])
        excl += z.get('exclusions', [])
        used.append(f"{name} (checked {z.get('checked', '?')})")
    return left, top, w - right, h - bottom, excl, 'intersection of ' + ', '.join(used) + '; confirm with the real preview'


class Painter:
    def __init__(self, w, h, brand):
        self.w, self.h, self.brand = w, h, brand
        self.img = Image.new('RGB', (w * SS, h * SS), _hex(brand['bg']))
        self.d = ImageDraw.Draw(self.img)
        self.boxes = []

    def rect(self, box, fill=None, outline=None, radius=0, width=0, label=None):
        x0, y0, x1, y1 = (v * SS for v in box)
        self.d.rounded_rectangle((x0, y0, x1, y1), radius=radius * SS, fill=fill, outline=outline, width=width * SS)
        if label:
            self.boxes.append({'label': label, 'box': [round(v) for v in box]})

    def text(self, x, y, block, color, label, align='left', width=None):
        lead = block['size'] * block['leading']
        for i, line in enumerate(block['lines']):
            f = _font(block['path'], block['size'] * SS)
            lx = x
            if align == 'center' and width:
                lx = x + (width - block['font'].getlength(line)) / 2
            self.d.text((lx * SS, (y + i * lead) * SS), line, font=f, fill=color)
        w = max(block['font'].getlength(l) for l in block['lines'])
        self.boxes.append({'label': label, 'box': [round(x), round(y), round(x + w), round(y + block['h'])], 'size_px': block['size']})

    def finish(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def _cover(path, w, h):
    im = Image.open(path).convert('RGB')
    r = max(w / im.width, h / im.height)
    im = im.resize((max(int(im.width * r), 1), max(int(im.height * r), 1)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def compose(c, ratio, brand, base_dir, platforms, mono=False, k=1.0):
    W, H = RATIOS[ratio]
    u = min(W, H) / 1080.0
    left, top, right, bottom, excl, note = safe_box(W, H, platforms)
    cr = c.get('creative') or {}
    proof = cr.get('proof') or {'type': 'none'}
    ptype = proof.get('type', 'none')
    land = W > H
    pad = int(36 * u)
    gap = int(28 * u * max(k, 0.6))
    col_right = right if not land else left + int((right - left) * (0.50 if ptype != 'none' else 0.92))
    width = col_right - left
    painter = Painter(W, H, brand)
    fg, acc, bg = brand['fg'], brand['accent'], brand['bg']
    issues = []
    sizes = {}

    def mk(label, text, path, lines, smax, smin, lead=1.2, wmax=None):
        if not text:
            return None
        block = fit(text, path, (wmax or width), lines, max(smax * k, smin) * u, smin * u, lead)
        sizes[label] = block['size']
        return block

    badge_text = cr.get('badge') or ('Учебный макет' if c.get('training_product') else None)
    badge = mk('badge', badge_text, SEMI, 1, 38, 32 * 1.0, 1.1, width - 2 * pad) if badge_text else None
    kicker = mk('kicker', cr.get('kicker'), SEMI, 2, 40, 34, 1.2)
    headline = mk('headline', c['headline'], BOLD, 4, 116, 60, 1.12)
    sub = mk('subline', cr.get('subline'), SEMI, 3, 52, 42, 1.28)
    cta_w = width
    cta = mk('cta', c['cta'], BOLD, 1, 58, 44, 1.1, cta_w - 2 * pad)
    foot_text = ' '.join(t for t in [cr.get('footnote'), (c.get('disclosure') or {}).get('text')] if t) or None
    foot = mk('footnote', foot_text, SEMI, 3, 34, 30, 1.25) if foot_text else None

    def px(v):
        return int(v)

    # vertical flow
    y = top
    elems = []
    if badge:
        bh = badge['h'] + int(24 * u)
        elems.append(('badge', y, bh)); y += bh + gap
    if kicker:
        elems.append(('kicker', y, kicker['h'])); y += kicker['h'] + int(12 * u)
    elems.append(('headline', y, headline['h'])); y += headline['h'] + gap
    if sub:
        elems.append(('subline', y, sub['h'])); y += sub['h'] + gap
    cta_h = cta['h'] + int(56 * u)
    foot_h = foot['h'] if foot else 0
    foot_y = bottom - foot_h
    cta_y = foot_y - (gap if foot else 0) - cta_h
    text_end = y

    # proof area
    proof_box = None
    if ptype != 'none':
        if land:
            proof_box = (col_right + gap * 2, top, right, bottom)
        else:
            proof_box = (left, text_end, right, cta_y - gap)
            if proof_box[3] - proof_box[1] < 300 * u:
                raise Overflow('not enough room for the proof block on this ratio: shorten texts or choose another ratio')
    if land:
        cta_y = foot_y - (gap if foot else 0) - cta_h
        if cta_y < text_end:
            raise Overflow('landscape text column too tall: shorten texts')
    elif ptype == 'none' and cta_y < text_end:
        raise Overflow('texts too long for this ratio')

    # paint
    for name, ey, eh in elems:
        if name == 'badge':
            tw = max(badge['font'].getlength(l) for l in badge['lines'])
            painter.rect((left, ey, left + tw + 2 * pad, ey + eh), fill=_tint(acc, bg, 0.14) if not mono else '#EEEEEE', radius=int(20 * u), label='badge_box')
            painter.text(left + pad, ey + int(12 * u), badge, acc if not mono else '#000000', 'badge')
        elif name == 'kicker':
            painter.text(left, ey, kicker, fg, 'kicker')
        elif name == 'headline':
            painter.text(left, ey, headline, fg, 'headline')
        elif name == 'subline':
            painter.text(left, ey, sub, fg, 'subline')
    if proof_box:
        _paint_proof(painter, c, proof, proof_box, base_dir, brand, u, mono, mk_fit=fit, sizes=sizes, issues=issues, land=land, k=k)
    on_acc = _on(acc)
    painter.rect((left, cta_y, col_right, cta_y + cta_h), fill=acc, radius=int(cta_h / 2), label='cta_button')
    painter.text(left, cta_y + (cta_h - cta['h']) / 2, cta, on_acc, 'cta', align='center', width=col_right - left)
    if foot:
        painter.text(left, foot_y, foot, fg, 'footnote')
    return painter, {'safe_box': [left, top, right, bottom], 'exclusions': excl, 'safe_note': note, 'sizes_px': sizes, 'issues': issues,
                     'on_accent': on_acc}


def _paint_proof(p, c, proof, box, base_dir, brand, u, mono, mk_fit, sizes, issues, land, k=1.0):
    x0, y0, x1, y1 = box
    fg, acc, bg = brand['fg'], brand['accent'], brand['bg']
    if proof['type'] == 'image':
        img_path = (Path(base_dir) / (proof.get('image') or '')).resolve()
        if not proof.get('image') or not img_path.is_file() or not img_path.is_relative_to(Path(base_dir).resolve()):
            raise ShortsError('proof.image missing or outside the campaign directory')
        w, h = int(x1 - x0), int(y1 - y0)
        tile = _cover(img_path, w * SS, h * SS)
        mask = Image.new('L', tile.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, tile.width, tile.height), radius=int(28 * u) * SS, fill=255)
        p.img.paste(tile, (int(x0) * SS, int(y0) * SS), mask)
        p.boxes.append({'label': 'proof_image', 'box': [int(x0), int(y0), int(x1), int(y1)]})
        if proof.get('image') not in {a.get('path') for a in c.get('assets', [])}:
            issues.append(f'proof image {proof["image"]!r} is not declared in assets[]: rights are not recorded')
        return
    # compare cards
    cards = [('before', proof.get('before_label'), proof.get('before'), False), ('after', proof.get('after_label'), proof.get('after'), True)]
    cards = [t for t in cards if t[2]]
    if len(cards) < 2:
        raise ShortsError('proof.type=compare needs before and after texts')
    gap = int(24 * u)
    if land:
        ch = (y1 - y0 - gap) / 2
        rects = [(x0, y0 + i * (ch + gap), x1, y0 + i * (ch + gap) + ch) for i in range(2)]
    else:
        ch = (y1 - y0 - gap) / 2
        rects = [(x0, y0 + i * (ch + gap), x1, y0 + i * (ch + gap) + ch) for i in range(2)]
    pad = int(22 * u)
    for (name, label, body, hot), r in zip(cards, rects):
        fill = _tint(acc, bg, 0.12) if hot and not mono else ('#F0F0F0' if hot else '#FFFFFF' if bg != '#FFFFFF' else bg)
        outline = acc if hot else _tint(fg, bg, 0.25)
        p.rect(r, fill=fill, outline=outline, radius=int(24 * u), width=int(4 * u) if hot else int(3 * u), label=name + '_card')
        inner_w = int(r[2] - r[0] - 2 * pad)
        lab = mk_fit((label or '').upper(), SEMI, inner_w, 1, 34 * u, 30 * u, 1.1) if label else None
        body_b = mk_fit(body, BOLD if hot else SEMI, inner_w, 4, max(64 * k, 42) * u, 42 * u, 1.18)
        total = (lab['h'] + int(8 * u) if lab else 0) + body_b['h']
        if total > (r[3] - r[1]) - 1.2 * pad:
            raise Overflow('compare card text does not fit: shorten it')
        yy = r[1] + ((r[3] - r[1]) - total) / 2
        if lab:
            p.text(r[0] + pad, yy, lab, acc if hot else fg, name + '_label'); yy += lab['h'] + int(8 * u)
        p.text(r[0] + pad, yy, body_b, fg, name + '_text')
        sizes[name + '_text'] = body_b['size']
        if lab:
            sizes[name + '_label'] = lab['size']


def _check(c, ratio, painter, meta, brand):
    W, H = RATIOS[ratio]
    u = min(W, H)
    left, top, right, bottom = meta['safe_box']
    problems, notes = list(meta['issues']), []
    for b in painter.boxes:
        x0, y0, x1, y1 = b['box']
        if x0 < left - 1 or y0 < top - 1 or x1 > right + 1 or y1 > bottom + 1:
            problems.append(f"{b['label']} leaves the safe box {meta['safe_box']}")
        for e in meta['exclusions']:
            if x0 < e[2] and x1 > e[0] and y0 < e[3] and y1 > e[1] and b['label'] not in ('cta_button',):
                problems.append(f"{b['label']} overlaps platform UI exclusion {e}")
    for label, size in meta['sizes_px'].items():
        floor = PHONE_MIN_LABEL if label in ('footnote', 'badge', 'kicker', 'before_label', 'after_label') else PHONE_MIN_BODY
        if size < floor * u - 0.5:
            problems.append(f'{label} {size}px is below the phone minimum {round(floor * u)}px')
    ratios = {'text_on_bg': contrast(brand['fg'], brand['bg']), 'accent_on_bg': contrast(brand['accent'], brand['bg']),
              'button_text': contrast(brand['accent'], meta['on_accent'])}
    if ratios['text_on_bg'] < 4.5:
        problems.append(f"text contrast {ratios['text_on_bg']} < 4.5")
    if ratios['button_text'] < 4.5:
        problems.append(f"button text contrast {ratios['button_text']} < 4.5")
    if ratios['accent_on_bg'] < 3:
        notes.append(f"accent on background contrast {ratios['accent_on_bg']} < 3: accent text/outlines may be weak")
    disc = (c.get('disclosure') or {}).get('text')
    if disc and not any(b['label'] == 'footnote' for b in painter.boxes):
        problems.append('disclosure text was not rendered')
    return {'contrast': ratios, 'problems': problems, 'notes': notes}


def render(directory, ratios=('9x16',), platforms=('youtube_shorts',), out_dir=None):
    d = Path(directory)
    try:
        c = json.loads((d / 'campaign.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ShortsError('campaign.json missing or invalid: ' + str(exc)) from exc
    for k in ('headline', 'cta'):
        if not (c.get(k) or '').strip():
            raise ShortsError(f'campaign.{k} is empty')
    out = Path(out_dir) if out_dir else d / 'banners'
    out.mkdir(parents=True, exist_ok=True)
    brand = {**DEFAULT_BRAND, **((c.get('creative') or {}).get('brand') or {})}
    report = {'tool': 'ad-render', 'verification': 'layout, contrast, size and safe-zone arithmetic only; meaning, honesty and rights need human review',
              'platforms': list(platforms), 'outputs': []}
    ok = True
    for ratio in ratios:
        if ratio not in RATIOS:
            raise ShortsError(f'unknown ratio {ratio!r}; use ' + ', '.join(RATIOS))
        entry = {'ratio': ratio, 'size': list(RATIOS[ratio])}
        for mono in (False, True):
            br = MONO_BRAND if mono else brand
            painter = meta = None
            last = None
            for k in (1.0, 0.85, 0.72, 0.62, 0.55):
                try:
                    painter, meta = compose(c, ratio, br, d, platforms, mono=mono, k=k)
                    break
                except Overflow as exc:
                    last = exc
            if painter is None:
                raise Overflow(f'{ratio}: {last}')
            entry['shrink_factor'] = k
            name = f'banner-{ratio}' + ('-mono' if mono else '')
            img = painter.finish()
            path = out / (name + '.png')
            img.save(path, optimize=True)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            chk = _check(c, ratio, painter, meta, br)
            entry['mono' if mono else 'color'] = {'file': path.name, 'sha256': digest, 'boxes': painter.boxes, 'sizes_px': meta['sizes_px'], **chk}
            if not mono:
                entry['safe_zone'] = {'box': meta['safe_box'], 'note': meta['safe_note']}
                prev = img.resize((360, round(360 * RATIOS[ratio][1] / RATIOS[ratio][0])), Image.LANCZOS)
                prev_path = out / f'preview-{ratio}-360.png'
                prev.save(prev_path)
                entry['preview_360'] = prev_path.name
            if chk['problems']:
                ok = False
        report['outputs'].append(entry)
    report['ok'] = ok
    report['next'] = ('Open the colour, mono and 360 px files yourself. This report is not the QA evidence: record your own review in '
                      'campaign.qa and seal the file with ad-seal.')
    (out / 'banner-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    return report


def seal(directory, artifact):
    """Record final_artifact path + sha256 in campaign.json. Does not approve anything."""
    d = Path(directory)
    p = (d / artifact).resolve()
    if not p.is_file() or not p.is_relative_to(d.resolve()):
        raise ShortsError('artifact must be an existing file inside the campaign directory')
    c = json.loads((d / 'campaign.json').read_text(encoding='utf-8'))
    c['final_artifact'] = {'path': str(p.relative_to(d.resolve())), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    (d / 'campaign.json').write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding='utf-8')
    return c['final_artifact']
