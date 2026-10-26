"""Paid API gate with a local, conservative budget ledger.

Two explicit opt-ins are required for any potentially billable HTTP request:
  SHORTS_ALLOW_PAID=1        scoped consent for this job (an API key is never consent)
  SHORTS_PAID_BUDGET=<n>     approved ceiling in USD for this job (positive number)

Each request is checked BEFORE the network call against budget minus ledger total. The cost of a
request is an ESTIMATE (defaults below, override with SHORTS_PAID_EST_TTS_PER_1K_CHARS and
SHORTS_PAID_EST_IMAGE). It is not provider billing: check the provider dashboard. The ledger
(SHORTS_PAID_LEDGER, default <SHORTS_MEMORY>/paid-ledger.json) is a plain file and is not tamper proof.
Reset it for a new approved job with `shorts.py paid reset`.
"""
import json
import os
import time
from pathlib import Path

from .util import ShortsError

DEFAULT_EST = {'tts_per_1k_chars': 0.30, 'image': 0.25, 'other': 0.10}


def _env_float(name, default):
    raw = os.environ.get(name)
    if raw is None or raw == '':
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ShortsError(f'{name} must be a number, got {raw!r}') from exc
    if value != value or value in (float('inf'), float('-inf')) or value < 0:
        raise ShortsError(f'{name} must be a finite non-negative number')
    return value


def ledger_path():
    explicit = os.environ.get('SHORTS_PAID_LEDGER')
    if explicit:
        return Path(explicit)
    base = os.environ.get('SHORTS_MEMORY') or os.path.join(os.environ.get('SHORTS_HOME', '.'), 'memory')
    return Path(base) / 'paid-ledger.json'


def load_ledger():
    p = ledger_path()
    if not p.exists():
        return {'currency': 'USD', 'estimated_total': 0.0, 'entries': []}
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        float(data['estimated_total'])
        data['entries']
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ShortsError(f'paid ledger unreadable ({p}); fix or reset it explicitly: {exc}') from exc


def estimate(kind, units=1.0):
    if kind == 'tts':
        return _env_float('SHORTS_PAID_EST_TTS_PER_1K_CHARS', DEFAULT_EST['tts_per_1k_chars']) * max(units, 1.0) / 1000.0
    if kind == 'image':
        return _env_float('SHORTS_PAID_EST_IMAGE', DEFAULT_EST['image']) * max(units, 1.0)
    return DEFAULT_EST['other'] * max(units, 1.0)


def require_paid_approval(kind='other', units=1.0, label=''):
    """Raise before any network call unless consent + budget allow it; record the estimate on success."""
    if os.environ.get('SHORTS_ALLOW_PAID') != '1':
        raise ShortsError('Paid API disabled. Obtain scoped user approval and budget first; '
                          'then set SHORTS_ALLOW_PAID=1 and SHORTS_PAID_BUDGET=<usd> for this job only. '
                          'API keys are not consent.')
    budget = _env_float('SHORTS_PAID_BUDGET', 0.0)
    if budget <= 0:
        raise ShortsError('Paid API needs an approved budget: set SHORTS_PAID_BUDGET=<usd, positive> '
                          'together with SHORTS_ALLOW_PAID=1.')
    cost = estimate(kind, units)
    ledger = load_ledger()
    total = float(ledger['estimated_total'])
    if total + cost > budget + 1e-9:
        raise ShortsError(f'Paid budget would be exceeded: spent(est) {total:.2f} + request(est) {cost:.2f} '
                          f'> approved {budget:.2f} USD. Ask the user to raise the limit explicitly.')
    ledger['estimated_total'] = round(total + cost, 6)
    ledger['entries'].append({'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'kind': kind, 'units': units,
                              'estimated_usd': round(cost, 6), 'label': label})
    p = ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(p)
    return cost


def reset_ledger():
    p = ledger_path()
    if p.exists():
        p.unlink()
    return {'reset': str(p)}


def status():
    ledger = load_ledger()
    budget = _env_float('SHORTS_PAID_BUDGET', 0.0)
    return {'allow_paid': os.environ.get('SHORTS_ALLOW_PAID') == '1', 'budget_usd': budget,
            'estimated_spent_usd': ledger['estimated_total'], 'requests': len(ledger['entries']),
            'remaining_estimated_usd': round(max(budget - float(ledger['estimated_total']), 0.0), 6),
            'note': 'estimates only; not provider billing'}
