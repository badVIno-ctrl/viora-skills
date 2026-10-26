"""Money and funnel metrics from the advertising instruction (section 'Analytics').

Pure arithmetic on numbers the user supplies. Nothing is fetched or estimated. A result is
'preliminary' until nothing is pending, the hold is over and confirmed rewards are paid.
Thresholds marked [G] are design hypotheses, not statistical or market norms.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .util import ShortsError

COUNTS = ('views', 'profile_clicks', 'link_clicks', 'impressions', 'ad_clicks', 'actions', 'confirmed', 'rejected', 'pending')
MONEY = ('payout_per_action', 'spend_total')
SPEND_KEYS = ('production', 'api', 'subscriptions', 'commissions', 'ads', 'time', 'other')
FLAGS = ('rule_violation', 'wrong_link', 'offer_mismatch')
MIN_CLICKS = 100      # [G]
MIN_CONFIRMED = 10    # [G]
MIN_DAYS = 7          # [G]


def _num(value, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShortsError(f'{label}: number expected, got {value!r}')
    if not math.isfinite(value) or value < 0:
        raise ShortsError(f'{label}: finite non-negative number expected')
    if integer and int(value) != value:
        raise ShortsError(f'{label}: whole number expected')
    return int(value) if integer else float(value)


def wilson(successes, trials, z=1.96):
    """95% Wilson interval in percent, or None without trials."""
    if not trials:
        return None
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return [round(max(centre - half, 0) * 100, 2), round(min(centre + half, 1) * 100, 2)]


def _ratio(a, b, scale=1.0, nd=4):
    return None if not b else round(a / b * scale, nd)


def _spend(data):
    items = data.get('spend') or {}
    if isinstance(items, (int, float)):
        items = {'other': items}
    if not isinstance(items, dict):
        raise ShortsError('spend: object of cost lines expected')
    total = 0.0
    lines = {}
    for k, v in items.items():
        lines[k] = _num(v, 'spend.' + k)
        total += lines[k]
    if 'spend_total' in data:
        declared = _num(data['spend_total'], 'spend_total')
        if lines and abs(declared - total) > 0.005:
            raise ShortsError('spend_total does not equal the sum of spend lines')
        total = declared
    return round(total, 2), lines


def compute(data):
    """Validate input and compute one metrics block."""
    if not isinstance(data, dict):
        raise ShortsError('metrics input must be a JSON object')
    n = {k: _num(data[k], k, True) if k in data and data[k] is not None else None for k in COUNTS}
    z = lambda k: n[k] or 0  # noqa: E731
    errors, warnings = [], []
    decided = z('confirmed') + z('rejected') + z('pending')
    if n['actions'] is not None and decided > n['actions']:
        errors.append('confirmed + rejected + pending exceeds actions')
    if n['actions'] is None and decided:
        n['actions'] = decided
    if n['link_clicks'] is not None and n['views'] is not None and n['link_clicks'] > n['views']:
        warnings.append('link_clicks above views: check that the event and the views are comparable')
    if n['actions'] and not n['link_clicks']:
        warnings.append('actions without link clicks: the click event may be untracked')
    if errors:
        raise ShortsError('; '.join(errors))
    currency = data.get('currency')
    if not currency:
        warnings.append('currency not given: money values are unitless')
    payout = _num(data['payout_per_action'], 'payout_per_action') if data.get('payout_per_action') is not None else None
    reward_in = data.get('reward') or {}
    accrued = _num(reward_in['accrued'], 'reward.accrued') if 'accrued' in reward_in else (None if payout is None or n['actions'] is None else payout * n['actions'])
    confirmed_reward = _num(reward_in['confirmed'], 'reward.confirmed') if 'confirmed' in reward_in else (None if payout is None else payout * z('confirmed'))
    paid = _num(reward_in['paid'], 'reward.paid') if 'paid' in reward_in else None
    spend, lines = _spend(data)
    rates = {
        'link_clicks_per_view_pct': _ratio(z('link_clicks'), n['views'], 100),
        'ad_ctr_pct': _ratio(z('ad_clicks'), n['impressions'], 100),
        'cr_pct': _ratio(z('actions'), n['link_clicks'], 100),
        'approval_pct': _ratio(z('confirmed'), z('confirmed') + z('rejected'), 100),
        'epc': None if confirmed_reward is None else _ratio(confirmed_reward, n['link_clicks'], 1, 4),  # per ONE click (the PDF's definition)
        'epc_per_100_clicks': None if confirmed_reward is None else _ratio(confirmed_reward, n['link_clicks'], 100, 2),  # Admitad Academy's definition
        'cost_per_confirmed': _ratio(spend, n['confirmed']) if spend else (0.0 if n['confirmed'] else None),
    }
    profit = None if confirmed_reward is None else round(confirmed_reward - spend, 2)
    profit_paid = None if paid is None else round(paid - spend, 2)
    out = {
        'currency': currency,
        'counts': {k: v for k, v in n.items() if v is not None},
        'rewards': {'accrued': accrued, 'confirmed': confirmed_reward, 'paid': paid},
        'spend': {'total': spend, 'lines': lines},
        'rates': rates,
        'intervals_95_pct': {
            'link_clicks_per_view': wilson(z('link_clicks'), n['views']) if n['views'] else None,
            'cr': wilson(z('actions'), n['link_clicks']) if n['link_clicks'] else None,
            'approval': wilson(z('confirmed'), z('confirmed') + z('rejected')) if (z('confirmed') + z('rejected')) else None,
        },
        'profit_confirmed': profit,
        'profit_paid': profit_paid,
        'roi_pct': None if profit is None or not spend else round(profit / spend * 100, 2),
        'roi_note': 'ROI is undefined at zero spend' if not spend else 'before taxes; include time cost in spend.time if you value it',
    }
    pending_reasons = []
    if z('pending'):
        pending_reasons.append(f'{z("pending")} actions still pending review')
    if data.get('hold_open'):
        pending_reasons.append('hold period not finished')
    if confirmed_reward is not None and (paid is None or paid + 1e-9 < confirmed_reward):
        pending_reasons.append('confirmed reward not fully paid out yet')
    out['status'] = 'preliminary' if pending_reasons else 'final'
    out['preliminary_because'] = pending_reasons
    if n['link_clicks'] is not None and n['link_clicks'] < MIN_CLICKS:
        warnings.append(f'fewer than {MIN_CLICKS} link clicks [G]: rates are noise, do not conclude')
    if n['confirmed'] is not None and n['confirmed'] < MIN_CONFIRMED:
        warnings.append(f'fewer than {MIN_CONFIRMED} confirmed actions [G]: approval, EPC and ROI are unstable')
    out['warnings'] = warnings
    return out


def diagnose(m):
    """First checks from the symptom table. Returns a list of (symptom, check_first)."""
    c = m['counts']
    views, clicks, actions = c.get('views'), c.get('link_clicks'), c.get('actions')
    rows = []
    if views is not None and views == 0:
        rows.append(('no views', 'topic, hook, originality, quality, account limits; do not declare a shadow ban automatically'))
    if views and clicks == 0:
        rows.append(('views but no clicks', 'audience-product fit, CTA visibility, link availability'))
    if clicks and not actions:
        rows.append(('clicks but no actions', 'landing page, language, price, technical errors, promise match'))
    rates = m['rates']
    if actions and rates['approval_pct'] is not None and rates['approval_pct'] < 50:
        rows.append(('actions but low approval', 'allowed source, GEO, lead quality, duplicates, offer terms'))
    if c.get('confirmed') and m['profit_confirmed'] is not None and m['profit_confirmed'] <= 0:
        rows.append(('actions but no profit', 'payout after checks, full costs, refunds and commissions'))
    return [{'symptom': s, 'check_first': t} for s, t in rows]


def decide(m, data):
    """Decision from pre-registered limits. Never recommends scaling on preliminary or thin data."""
    limits = data.get('limits') or {}
    flags = data.get('flags') or {}
    reasons = []
    stop = []
    for f in FLAGS:
        if flags.get(f):
            stop.append(f'{f}: stop immediately')
    spend = m['spend']['total']
    if limits.get('spend_limit') is not None and spend > _num(limits['spend_limit'], 'limits.spend_limit'):
        stop.append(f'spend {spend} exceeds agreed spend_limit {limits["spend_limit"]}')
    profit = m['profit_confirmed']
    if limits.get('max_loss') is not None and profit is not None and -profit > _num(limits['max_loss'], 'limits.max_loss'):
        stop.append(f'loss {-profit} exceeds agreed max_loss {limits["max_loss"]}')
    if stop:
        return {'decision': 'STOP', 'reasons': stop}
    thin = []
    days = limits.get('elapsed_days')
    if days is not None and _num(days, 'limits.elapsed_days') < _num(limits.get('window_days', MIN_DAYS), 'limits.window_days'):
        thin.append('observation window not finished')
    elif days is not None and days < MIN_DAYS:
        thin.append(f'fewer than {MIN_DAYS} days [G]')
    if limits.get('min_clicks') is not None and (m['counts'].get('link_clicks') or 0) < limits['min_clicks']:
        thin.append('below the min_clicks you set before the test')
    if limits.get('min_actions') is not None and (m['counts'].get('actions') or 0) < limits['min_actions']:
        thin.append('below the min_actions you set before the test')
    thin += [w for w in m['warnings'] if w.startswith('fewer than')]
    if thin:
        return {'decision': 'INSUFFICIENT_DATA', 'reasons': thin + ['continue only inside the agreed limits']}
    if m['status'] == 'preliminary':
        return {'decision': 'HOLD', 'reasons': m['preliminary_because'] + ['do not scale before confirmation and payout']}
    if profit is not None and profit > 0:
        return {'decision': 'REPEAT', 'reasons': ['confirmed and paid profit; repeat once with fresh content before scaling [G]']}
    return {'decision': 'REVISE_OR_STOP', 'reasons': ['no confirmed profit; use the diagnostics, change one early funnel step']}


def run(data):
    m = compute(data)
    result = {'metrics': m, 'diagnostics': diagnose(m), 'decision': decide(m, data)}
    variants = data.get('variants')
    if variants:
        rows = []
        for v in variants:
            vm = compute({**{k: data[k] for k in ('currency', 'payout_per_action') if k in data}, **v})
            rows.append({'id': v.get('id'), 'rates': vm['rates'], 'counts': vm['counts'], 'profit_confirmed': vm['profit_confirmed'],
                         'status': vm['status']})
        result['variants'] = rows
        result['variants_note'] = ('Organic posts reach different audiences: this is a quasi-experiment, not a randomized A/B test. '
                                   'Compare concepts as packages; one thin sample or one viral post proves nothing.')
    return result


def append_log(directory, record):
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    line = {'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **record}
    with (d / 'experiments.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')
    return str(d / 'experiments.jsonl')
