"""UTM / SubID plan per creative. Analytics labels, not partner attribution.

UTM alone does not attribute partner conversions: only a network-supported SubID/click ID does.
A signed partner link is never modified. No personal data in any label.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import adrules
from .util import ShortsError

TRANSLIT = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't', 'u', 'f', 'h', 'c',
                     'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))


def slug(text, limit=40):
    t = ''.join(TRANSLIT.get(ch, ch) for ch in (text or '').lower())
    t = re.sub(r'[^a-z0-9]+', '-', t).strip('-')
    return t[:limit].strip('-')


def build(destination, ids, campaign, source='youtube_shorts', medium='organic_video', signed=False,
          subid_param=None, shared_profile_link=False):
    if not destination or not re.match(r'^https?://\S+$', destination):
        raise ShortsError('destination URL missing in campaign.json')
    if not ids:
        raise ShortsError('give at least one creative id')
    seen, rows = set(), []
    for raw in ids:
        if adrules.EMAIL.search(raw) or adrules.PHONE.search(raw):
            raise ShortsError(f'id {raw!r} looks like personal data; use neutral ids')
        cid = slug(raw)
        if not cid or cid in seen:
            raise ShortsError(f'id {raw!r} is empty or duplicates another after normalisation')
        seen.add(cid)
        rows.append(cid)
    camp = slug(campaign) or 'campaign'
    notes = []
    parts = urlsplit(destination)
    existing = parse_qsl(parts.query, keep_blank_values=True)
    out = []
    for cid in rows:
        if signed:
            url = destination
        else:
            q = list(existing)
            have = {k for k, _ in q}
            for k, v in (('utm_source', slug(source)), ('utm_medium', slug(medium)), ('utm_campaign', camp), ('utm_content', cid)):
                if k not in have:
                    q.append((k, v))
            if subid_param and subid_param not in have:
                q.append((subid_param, cid))
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))
        errors, _ = adrules.url_privacy_issues(url)
        if errors:
            raise ShortsError('; '.join(errors))
        out.append({'creative_id': cid, 'utm_source': '' if signed else slug(source), 'utm_medium': '' if signed else slug(medium),
                    'utm_campaign': '' if signed else camp, 'utm_content': '' if signed else cid,
                    'subid': cid if (subid_param and not signed) else '', 'url': url})
    if signed:
        notes.append('Signed link left untouched. Per-creative attribution needs a network-supported SubID configured in the network, '
                     'not appended here.')
        level = 'channel'
    elif subid_param and not shared_profile_link:
        level = 'creative'
        notes.append('Creative level only if the network really returns this SubID in conversion reports: test it with a real click first.')
    else:
        level = 'channel'
        notes.append('UTM labels help your analytics, they do not attribute partner conversions.')
    if shared_profile_link:
        level = 'channel'
        notes.append('All creatives share one profile link and the platform does not pass the video id: report at channel or period level, '
                     'or use allowed unique pages/codes.')
    if re.search(r'youtube|shorts', f'{source} {medium}', re.I):
        notes.append('YouTube Shorts: URLs in Shorts descriptions and comments are non-clickable; clickable places are the channel profile '
                     'links (up to 14), brand deal links and Posts (YouTube Help 13748639, checked 2026-10-20; re-check before use). '
                     'Showing URL text inside the video is also covered by the External links policy.')
    return {'attribution_level_suggested': level, 'rows': out, 'notes': notes}


def write(directory, plan):
    d = Path(directory)
    with (d / 'links.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(plan['rows'][0].keys()))
        w.writeheader()
        w.writerows(plan['rows'])
    lines = ['# Links per creative', '', f'Suggested attribution level: **{plan["attribution_level_suggested"]}**', '']
    lines += [f'- {n}' for n in plan['notes']]
    lines += ['', '| creative | url |', '|---|---|'] + [f'| {r["creative_id"]} | {r["url"]} |' for r in plan['rows']]
    (d / 'links.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return [str(d / 'links.csv'), str(d / 'links.md')]
