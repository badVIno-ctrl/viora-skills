"""Offline advertising evidence gate. Never fetches, publishes, spends or verifies self-reports.
A successful draft is NOT launch approval. All launch evidence is supplied by a reviewer.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from .config import skill_root
from .util import ShortsError
from . import adrules

DEFAULT_MAX_AGE_DAYS = 30
CREATIVE_ATTRIBUTION_HINT_LOWER = CREATIVE_ATTRIBUTION_HINT = ('subid', 'sub_id', 'click id', 'click_id', 'clickid', 'unique page', 'уникальн', 'промокод', 'promo code', 'отдельн')


def initialize(directory):
    root = skill_root()
    d = Path(directory)
    sources = [(root / 'schema/campaign.example.json', d / 'campaign.json')]
    sources += [(p, d / p.name) for p in sorted((root / 'templates/advertising').glob('*.md'))]
    existing = [str(dst) for _, dst in sources if dst.exists()]
    if existing:
        raise ShortsError('ad-init refuses to overwrite: ' + ', '.join(existing))
    d.mkdir(parents=True, exist_ok=True)
    for src, dst in sources:
        dst.write_bytes(src.read_bytes())
    return {'created': [str(dst) for _, dst in sources], 'status': 'draft', 'ready_for_launch': False}


def _reject_constant(value):
    raise ValueError('non-finite JSON number: ' + value)


PLATFORM_LABELS = (
    (r'youtube|shorts|ютуб|шортс', r'paid promotion|studio|платн\w* промо|студи',
     'YouTube: branded content needs the paid promotion declaration in YouTube Studio (YouTube Help 154235 / 17596007, '
     'checked 2026-10-20); say in disclosure.placement that it is set'),
    (r'tiktok|тикток', r'disclosure|paid partnership|promotional|коммерческ|раскрыти',
     'TikTok: branded content needs the commercial content disclosure toggle (TikTok Support, checked 2026-10-20); '
     'say in disclosure.placement that it is set'),
    (r'instagram|reels|инстаграм|рилс', r'paid partnership|партн[её]рств|платн\w* партн',
     'Instagram: branded content, including affiliate links, should carry the paid partnership label (Instagram Help Center, '
     'checked 2026-10-20); say in disclosure.placement that it is set'),
)


def audit(directory, stage='draft', today=None):
    if stage not in ('draft', 'launch'):
        raise ValueError('stage must be draft or launch')
    if isinstance(today, str):
        try:
            today = date.fromisoformat(today)
        except ValueError as exc:
            raise ValueError('today must be YYYY-MM-DD') from exc
    today = today or date.today()
    d = Path(directory)
    errors, warnings = [], []
    report = {'stage': stage, 'valid': False, 'ready_for_launch': False,
              'verification': 'structure and reviewer-declared evidence only; no external verification',
              'issues': errors, 'warnings': warnings}
    try:
        c = json.loads((d / 'campaign.json').read_text(encoding='utf-8'), parse_constant=_reject_constant)
    except (OSError, ValueError) as exc:
        errors.append('campaign.json missing or invalid: ' + str(exc))
        return report
    schema = json.loads((skill_root() / 'schema/campaign.schema.json').read_text(encoding='utf-8'))
    for err in sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(c),
                      key=lambda e: str(list(e.absolute_path))):
        errors.append('schema ' + '.'.join(map(str, err.absolute_path)) + ': ' + err.message)
    if errors:
        return report
    ov = c['overlay']
    a, b, rect = ov['start_seconds'], ov['end_seconds'], ov['rectangle']
    if (a is None) != (b is None):
        errors.append('overlay interval must have both bounds or neither')
    if a is not None and b <= a:
        errors.append('overlay end must be after start')
    if rect is not None:
        x, y, w, h = rect
        if not w or not h or x + w > c['canvas']['width'] or y + h > c['canvas']['height']:
            errors.append('overlay rectangle outside canvas or empty')
    if c['test']['max_loss'] > c['test']['spend_limit']:
        errors.append('max_loss exceeds spend_limit')
    if c['goal'] == 'training_comprehension' and not (c['training_product'] and c['monetization'] == 'training'):
        errors.append('training_comprehension requires training_product=true and monetization=training')
    not_applicable = []
    for key, val in c['qa'].items():
        if val.get('applicability', 'applicable') == 'not_applicable':
            if c['creative_type'] != 'static_ad' or key not in ('motion_audio', 'subtitles'):
                errors.append('qa.' + key + ': not_applicable is only allowed for static motion_audio/subtitles')
            elif val['passed'] or not (val['evidence'] or '').strip():
                errors.append('qa.' + key + ': not_applicable requires passed=false and evidence explaining why')
            else:
                not_applicable.append(key)
    report['not_applicable'] = not_applicable
    lint_errors, lint_warnings = adrules.text_issues(c, stage)
    errors.extend(lint_errors)
    warnings.extend(lint_warnings)
    variants = c.get('variants') or []
    if len({v['id'] for v in variants}) != len(variants):
        errors.append('variants: duplicate id')
    if stage == 'draft':
        if len(variants) < 2:
            warnings.append('variants: prepare 2-3 meaningfully different concepts before launch')
    if stage == 'draft':
        warnings.append('Draft only. Missing offer, rights, route, QA and approval may block launch.')
        report['valid'] = not errors
        return report

    def need(value, label):
        if value is None or (isinstance(value, str) and not value.strip()) or value == []:
            errors.append(label + ' missing')

    def true(value, label):
        if value is not True:
            errors.append(label + ' not confirmed')

    max_age = c.get('evidence_max_age_days', DEFAULT_MAX_AGE_DAYS)

    def stale(iso, label):
        if not iso:
            return
        age = (today - date.fromisoformat(iso)).days
        if age < 0:
            errors.append(label + ' is in the future')
        elif age > max_age:
            errors.append(f'{label} is {age} days old (limit {max_age}); re-check the source before launch')

    def proof(value, label):
        for key in ('reference', 'checked_at', 'scope'):
            need(value[key], label + '.' + key)
        stale(value['checked_at'], label + '.checked_at')

    if c['training_product'] or c['monetization'] == 'training':
        errors.append('training product cannot launch')
    if c['canvas']['status'] != 'final':
        errors.append('canvas must be final')
    for k in ('placement', 'headline', 'cta', 'destination'):
        need(c[k], k)
    for k, v in c['audience'].items():
        need(v, 'audience.' + k)
    offer = c['offer']
    for k, v in offer.items():
        if k not in ('source_status', 'approval_evidence'):
            need(v, 'offer.' + k)
    stale(offer['checked_at'], 'offer.checked_at')
    if offer['source_status'] not in ('allowed', 'approval_required'):
        errors.append('source forbidden or permission unknown')
    if offer['source_status'] == 'approval_required':
        need(offer['approval_evidence'], 'offer.approval_evidence')
    for audience_key, offer_key in [('country', 'audience_country'), ('age', 'audience_age')]:
        if c['audience'][audience_key] != offer[offer_key]:
            errors.append('audience/offer mismatch: ' + audience_key)
    for flag in ('claims_verified', 'rights_verified', 'publication_approved'):
        true(c[flag], flag)
    for collection, flag in [('claims', 'verified'), ('assets', 'rights_verified')]:
        need(c[collection], collection)
        for i, item in enumerate(c[collection]):
            prefix = f'{collection}[{i}]'
            need(item.get('text', item.get('path')), prefix + '.text/path')
            true(item[flag], prefix + '.' + flag)
            proof(item['evidence'], prefix + '.evidence')
    proof(c['rules'], 'rules')
    for key in ('method', 'evidence'):
        need(c['safe_area'][key], 'safe_area.' + key)
    true(c['safe_area']['verified'], 'safe_area.verified')
    true(c['route']['verified'], 'route.verified')
    for key in ('link_point', 'evidence'):
        need(c['route'][key], 'route.' + key)
    lp = str(c['route'].get('link_point') or '')
    if re.search(r'youtube|shorts|ютуб|шортс', ' '.join([str(c.get('placement') or ''), lp]), re.I):
        wants_text_link = re.search(r'comment|description|коммент|описани|закреп', lp, re.I)
        has_clickable = re.search(r'profile|профил|brand ?deal|бренд|post|пост|about|channel link|ссылк\w* канала', lp, re.I)
        if wants_text_link and not has_clickable:
            errors.append('route.link_point: URLs in YouTube Shorts comments and descriptions are non-clickable '
                          '(YouTube Help 13748639, checked 2026-10-20); name a clickable place such as the channel profile link and re-check the current help')
        elif wants_text_link:
            warnings.append('route.link_point mentions a comment or description: in YouTube Shorts those URLs are non-clickable; confirm the route uses the clickable place')
    if c['creative_type'] == 'overlay':
        if a is None or rect is None:
            errors.append('overlay interval/rectangle required for launch')
        if set(ov['avoid']) != {'face', 'product', 'subtitles', 'platform_ui'}:
            errors.append('overlay avoidance review incomplete')
    for key in ('method', 'limitations', 'evidence'):
        need(c['tracking'][key], 'tracking.' + key)
    if c['tracking']['attribution_level'] == 'unknown':
        errors.append('tracking attribution level unknown')
    for k in ('hypothesis', 'primary_metric', 'event_source', 'observation_window', 'stop_condition', 'currency'):
        need(c['test'][k], 'test.' + k)
    for k in ('scope', 'evidence'):
        need(c['authorization'][k], 'authorization.' + k)
    auth = c['authorization']
    if auth['paid_media'] or c['test']['spend_limit'] > 0:
        true(auth['spend_approved'], 'authorization.spend_approved')
        need(auth['stop_method'], 'authorization.stop_method')
    if auth['paid_media'] and c['test']['spend_limit'] <= 0:
        errors.append('paid media requires a positive authorized spend_limit')
    for key, val in c['qa'].items():
        if key in not_applicable:
            continue
        true(val['passed'], 'qa.' + key)
        need(val['evidence'], 'qa.' + key + '.evidence')
    rev = c.get('reviewer') or {}
    if not rev:
        errors.append('reviewer missing: a human must personally confirm the launch evidence')
    else:
        for k in ('name', 'role', 'statement', 'confirmed_at'):
            need(rev.get(k), 'reviewer.' + k)
        true(rev.get('is_human'), 'reviewer.is_human')
        stale(rev.get('confirmed_at'), 'reviewer.confirmed_at')
        author = (c.get('author') or '').strip().casefold()
        if author and author == (rev.get('name') or '').strip().casefold():
            errors.append('reviewer must differ from author (four-eyes rule)')
    if c['monetization'] in ('affiliate', 'fixed_placement'):
        disc = c.get('disclosure') or {}
        need(disc.get('text'), 'disclosure.text')
        true(disc.get('shown_in_creative'), 'disclosure.shown_in_creative')
        need(disc.get('placement'), 'disclosure.placement')
        plc = str(c.get('placement') or '')
        said = ' '.join([str(disc.get('placement') or ''), str(disc.get('text') or '')])
        for pat, done, msg in PLATFORM_LABELS:
            if re.search(pat, plc, re.I) and not re.search(done, said, re.I):
                warnings.append(msg)
    elif not (c.get('disclosure') or {}).get('text'):
        warnings.append('own_product: check whether the platform or country still requires a promotion label')
    if len(variants) < 2:
        errors.append('variants: at least 2 meaningfully different concepts are required')
    else:
        if len({v['concept'] for v in variants}) < 2:
            errors.append('variants: all variants use one concept; change the idea, not only the style')
        if len(variants) > 3:
            warnings.append('variants: more than 3 concepts dilute a first test')
        for v in variants:
            need(v['hypothesis'], 'variants.' + v['id'] + '.hypothesis')
    if c['tracking']['attribution_level'] == 'creative':
        method = (c['tracking']['method'] or '').casefold()
        if not any(h in method for h in CREATIVE_ATTRIBUTION_HINT_LOWER):
            errors.append('attribution_level=creative needs a per-creative mechanism in tracking.method '
                          '(SubID/click ID, unique page or code); otherwise use channel or period')
    artifact = c['final_artifact']
    need(artifact['path'], 'final_artifact.path')
    need(artifact['sha256'], 'final_artifact.sha256')
    if artifact['path']:
        p = (d / artifact['path']).resolve()
        if Path(artifact['path']).is_absolute() or not p.is_relative_to(d.resolve()):
            errors.append('final artifact must be inside campaign directory')
        elif not p.is_file():
            errors.append('final artifact file missing')
        else:
            with p.open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            if digest != artifact['sha256']:
                errors.append('final artifact hash mismatch; repeat QA after changes')
    # If a renderer manifest is present, prevent signing a different file.
    manifest = d / 'manifest.json'
    if manifest.exists():
        try:
            m = json.loads(manifest.read_text(encoding='utf-8'))
            if m.get('video') and (d / m['video']).resolve() != (d / (artifact['path'] or '')).resolve():
                errors.append('campaign final artifact differs from manifest video')
            if b is not None and isinstance(m.get('duration'), (int, float)) and b > m['duration']:
                errors.append('overlay end exceeds final video duration')
        except (OSError, ValueError, TypeError, AttributeError):
            errors.append('cannot read renderer manifest')
    report['valid'] = not errors
    report['ready_for_launch'] = not errors
    return report
