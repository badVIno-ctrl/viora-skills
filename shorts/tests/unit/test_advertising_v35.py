"""Offline contract tests for 1.7.0 / traffic v3.5: text rules, freshness, reviewer, variants, budget ledger."""
import copy
import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_advertising_v34 import complete, dump, ROOT  # noqa: E402
from shortskit import adrules
from shortskit.advertising import audit
from shortskit.util import ShortsError


def errs(d, stage='launch', **kw):
    return audit(d, stage, **kw)['issues']


def has(issues, needle):
    return any(needle in i for i in issues)


# ---------- risky and forbidden texts ----------
@pytest.mark.parametrize('text,cat', [('Бесплатно для всех', 'free'), ('Скидка на подписку', 'discount'),
                                       ('Лучший сервис', 'superlative'), ('Без комиссии', 'no_fee'),
                                       ('Только сегодня', 'scarcity'), ('Промокод в профиле', 'promo')])
def test_risky_headline_needs_verified_claim_at_launch(tmp_path, text, cat):
    c = complete(tmp_path); c['headline'] = text; dump(tmp_path, c)
    assert has(errs(tmp_path), f'[{cat}]')
    assert not has(errs(tmp_path, 'draft'), f'[{cat}]')  # draft only warns
    assert has(audit(tmp_path, 'draft')['warnings'], f'[{cat}]')


def test_verified_claim_with_covers_unblocks_risky_text(tmp_path):
    c = complete(tmp_path); c['headline'] = 'Бесплатно для новых'
    c['claims'][0]['covers'] = ['free']; dump(tmp_path, c)
    assert not has(errs(tmp_path), '[free]')


def test_unverified_claim_does_not_cover(tmp_path):
    c = complete(tmp_path); c['headline'] = 'Бесплатно для новых'
    c['claims'].append({'text': 'Бесплатно: тариф без оплаты', 'verified': False, 'evidence': copy.deepcopy(c['claims'][0]['evidence'])})
    dump(tmp_path, c)
    assert has(errs(tmp_path), '[free]')


@pytest.mark.parametrize('text', ['Гарантированный доход за неделю', 'Врачи рекомендуют этот сервис', 'Скриншот дохода внутри',
                                   'Guaranteed profit in 7 days'])
@pytest.mark.parametrize('stage', ['draft', 'launch'])
def test_forbidden_promises_block_at_every_stage(tmp_path, text, stage):
    c = complete(tmp_path); c['headline'] = text; dump(tmp_path, c)
    assert has(errs(tmp_path, stage), 'forbidden')


def test_clean_text_has_no_risky_hits():
    assert adrules.risky_hits('Проверь текст перед публикацией') == []


def test_variant_texts_are_linted_too(tmp_path):
    c = complete(tmp_path); c['variants'][1]['headline'] = 'Лучший способ проверить'; dump(tmp_path, c)
    assert has(errs(tmp_path), 'variants[1].headline')


def test_creative_layers_are_linted(tmp_path):
    c = complete(tmp_path); c['creative'] = {'subline': 'Бесплатно навсегда'}; dump(tmp_path, c)
    assert has(errs(tmp_path), 'creative.subline')


def test_word_count_hints_are_warnings_only(tmp_path):
    c = complete(tmp_path); c['headline'] = 'Один'; c['cta'] = 'Нажми сюда прямо сейчас пожалуйста'; dump(tmp_path, c)
    r = audit(tmp_path, 'launch')
    assert r['valid'] and has(r['warnings'], 'headline') and has(r['warnings'], 'cta')


# ---------- privacy, gambling ----------
def test_pii_in_destination_blocks_both_stages(tmp_path):
    c = complete(tmp_path); c['destination'] = 'https://example.invalid/p?utm_content=anna@example.com'; dump(tmp_path, c)
    assert has(errs(tmp_path, 'draft'), 'e-mail') and has(errs(tmp_path), 'e-mail')


def test_phone_in_query_blocks(tmp_path):
    c = complete(tmp_path); c['destination'] = 'https://example.invalid/p?subid=%2B7%20912%20345-67-89'; dump(tmp_path, c)
    assert has(errs(tmp_path, 'draft'), 'phone')


def test_signed_link_with_utm_warns(tmp_path):
    c = complete(tmp_path); c['destination'] = 'https://example.invalid/p?sign=abc&utm_source=yt'; dump(tmp_path, c)
    assert has(audit(tmp_path, 'launch')['warnings'], 'signature-like')


def test_gambling_as_earning_blocked_and_age_required(tmp_path):
    c = complete(tmp_path); c['offer']['name'] = 'Казино бонус'; c['headline'] = 'Заработай на казино'; dump(tmp_path, c)
    assert has(errs(tmp_path, 'draft'), 'gambling must not be presented')
    c = complete(tmp_path); c['offer']['name'] = 'Casino partner'
    c['audience']['age'] = c['offer']['audience_age'] = '16+'; dump(tmp_path, c)
    assert has(errs(tmp_path), '18+')


def test_min_age_parser():
    assert adrules.min_age('18+') == 18 and adrules.min_age('16-24') == 16 and adrules.min_age('adults') == 18
    assert adrules.min_age(None) is None


# ---------- freshness ----------
def test_stale_evidence_blocks_launch(tmp_path):
    c = complete(tmp_path); dump(tmp_path, c)
    future = datetime.date.today() + datetime.timedelta(days=31)
    assert has(errs(tmp_path, today=future), 'days old')


def test_evidence_limit_is_configurable_but_capped(tmp_path):
    c = complete(tmp_path); c['evidence_max_age_days'] = 90; dump(tmp_path, c)
    assert audit(tmp_path, 'launch', today=datetime.date.today() + datetime.timedelta(days=60))['valid']
    c['evidence_max_age_days'] = 365; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']  # schema cap


@pytest.mark.parametrize('path', [('offer', 'checked_at'), ('rules', 'checked_at')])
def test_each_dated_source_is_checked_for_age(tmp_path, path):
    c = complete(tmp_path); c[path[0]][path[1]] = '2020-01-01'; dump(tmp_path, c)
    assert has(errs(tmp_path), path[0] + '.' + path[1])


# ---------- reviewer ----------
def test_reviewer_required_and_must_be_human(tmp_path):
    c = complete(tmp_path); del c['reviewer']; dump(tmp_path, c)
    assert has(errs(tmp_path), 'reviewer missing')
    c = complete(tmp_path); c['reviewer']['is_human'] = False; dump(tmp_path, c)
    assert has(errs(tmp_path), 'reviewer.is_human')


def test_reviewer_cannot_be_author(tmp_path):
    c = complete(tmp_path); c['author'] = c['reviewer']['name'].lower(); dump(tmp_path, c)
    assert has(errs(tmp_path), 'four-eyes')


# ---------- disclosure, variants, attribution ----------
def test_affiliate_requires_disclosure(tmp_path):
    c = complete(tmp_path); c['monetization'] = 'affiliate'; dump(tmp_path, c)
    assert has(errs(tmp_path), 'disclosure.text')
    c['disclosure'] = {'text': 'Реклама. Партнёрская ссылка', 'shown_in_creative': True, 'placement': 'footer of banner'}; dump(tmp_path, c)
    assert audit(tmp_path, 'launch')['valid']


def test_variants_required_and_must_differ(tmp_path):
    c = complete(tmp_path); c['variants'] = []; dump(tmp_path, c)
    assert has(errs(tmp_path), 'at least 2')
    c = complete(tmp_path); c['variants'][1]['concept'] = c['variants'][0]['concept']; dump(tmp_path, c)
    assert has(errs(tmp_path), 'one concept')
    c = complete(tmp_path); c['variants'][1]['id'] = 'A'; dump(tmp_path, c)
    assert has(errs(tmp_path, 'draft'), 'duplicate id')


def test_creative_attribution_needs_mechanism(tmp_path):
    c = complete(tmp_path); c['tracking']['attribution_level'] = 'creative'; c['tracking']['method'] = 'guess from views'; dump(tmp_path, c)
    assert has(errs(tmp_path), 'per-creative mechanism')


def test_schema_accepts_both_versions(tmp_path):
    for v in ('advertising-1', 'advertising-2'):
        c = complete(tmp_path); c['schema_version'] = v; dump(tmp_path, c)
        assert audit(tmp_path, 'draft')['valid'], v


# ---------- paid budget ledger ----------
@pytest.fixture
def paid(monkeypatch, tmp_path):
    monkeypatch.setenv('SHORTS_PAID_LEDGER', str(tmp_path / 'ledger.json'))
    monkeypatch.setenv('SHORTS_ALLOW_PAID', '1')
    from shortskit import costs
    return costs


def test_budget_required_with_consent(paid, monkeypatch):
    monkeypatch.delenv('SHORTS_PAID_BUDGET', raising=False)
    with pytest.raises(ShortsError, match='approved budget'):
        paid.require_paid_approval('image')


def test_budget_blocks_before_overspend_and_records(paid, monkeypatch):
    monkeypatch.setenv('SHORTS_PAID_BUDGET', '0.50')
    assert paid.require_paid_approval('image') == pytest.approx(0.25)
    assert paid.require_paid_approval('image') == pytest.approx(0.25)
    with pytest.raises(ShortsError, match='budget would be exceeded'):
        paid.require_paid_approval('image')
    st = paid.status()
    assert st['requests'] == 2 and st['estimated_spent_usd'] == pytest.approx(0.5) and st['remaining_estimated_usd'] == 0


def test_tts_estimate_scales_with_characters(paid, monkeypatch):
    monkeypatch.setenv('SHORTS_PAID_BUDGET', '10')
    assert paid.estimate('tts', 2000) == pytest.approx(0.6)


@pytest.mark.parametrize('bad', ['abc', 'nan', '-1'])
def test_bad_budget_value_rejected(paid, monkeypatch, bad):
    monkeypatch.setenv('SHORTS_PAID_BUDGET', bad)
    with pytest.raises(ShortsError):
        paid.require_paid_approval('image')


def test_corrupt_ledger_fails_closed(paid, monkeypatch, tmp_path):
    monkeypatch.setenv('SHORTS_PAID_BUDGET', '5')
    (tmp_path / 'ledger.json').write_text('{broken')
    with pytest.raises(ShortsError, match='ledger unreadable'):
        paid.require_paid_approval('image')


def test_reset_ledger(paid, monkeypatch):
    monkeypatch.setenv('SHORTS_PAID_BUDGET', '5')
    paid.require_paid_approval('image'); paid.reset_ledger()
    assert paid.status()['requests'] == 0


# ---------- unrecognised advertising in release-check ----------
def _rel(tmp_path, desc, **extra):
    from test_advertising_v34 import write_release
    m = write_release(tmp_path)
    m.update(extra)
    (tmp_path / 'release.json').write_text(json.dumps(m))
    (tmp_path / 'ОПИСАНИЕ.txt').write_text(desc)
    from shortskit.release import audit as release_audit
    return release_audit(tmp_path)


@pytest.mark.parametrize('desc', ['Промокод SHORTS10 даёт скидку', 'Ссылка: https://x.invalid/a?utm_source=yt',
                                   'Партнёрская ссылка в профиле', '#ad full review', 'Подписывайтесь, это реклама'])
def test_release_blocks_unrecognised_ad_wording(tmp_path, desc):
    r = _rel(tmp_path, desc)
    assert not r['ready'] and any('possible advertising wording' in i for i in r['issues'])


def test_release_ad_wording_needs_explicit_decision_with_reason(tmp_path):
    assert not _rel(tmp_path, 'Промокод в описании', advertising=False)['ready']          # no reason
    assert not _rel(tmp_path, 'Промокод в описании', advertising=False, advertising_reason='ok')['ready']  # too short
    r = _rel(tmp_path, 'Промокод в описании', advertising=False, advertising_reason='Слово из цитаты фильма, не реклама (проверено)')
    assert r['ready']


def test_release_plain_description_still_passes(tmp_path):
    assert _rel(tmp_path, 'Два сайта для учебы. Подписывайтесь.')['ready']


def test_release_ad_wording_in_release_json_title_is_caught(tmp_path):
    r = _rel(tmp_path, 'Описание без маркеров', title='Скидка на курс')
    assert not r['ready']


# ---------- YouTube Shorts: URLs in descriptions and comments are non-clickable ----------
@pytest.mark.parametrize('point', ['ссылка в описании', 'link in pinned comment', 'закреплённый комментарий с ссылкой'])
def test_youtube_shorts_description_or_comment_link_blocked(tmp_path, point):
    c = complete(tmp_path); c['placement'] = 'YouTube Shorts'; c['route']['link_point'] = point; dump(tmp_path, c)
    assert has(errs(tmp_path), 'non-clickable')


def test_youtube_shorts_profile_link_ok_and_mixed_warns(tmp_path):
    c = complete(tmp_path); c['placement'] = 'YouTube Shorts'; c['route']['link_point'] = 'ссылка в профиле канала'; dump(tmp_path, c)
    assert not has(errs(tmp_path), 'non-clickable')
    c['route']['link_point'] = 'профиль канала; ещё упомянуть в описании'; dump(tmp_path, c)
    assert not has(errs(tmp_path), 'non-clickable')
    assert has(audit(tmp_path, 'launch')['warnings'], 'non-clickable')


def test_other_platform_comment_link_not_blocked_by_youtube_rule(tmp_path):
    c = complete(tmp_path); c['placement'] = 'synthetic_account'; c['route']['link_point'] = 'link in comment'; dump(tmp_path, c)
    assert not has(errs(tmp_path), 'non-clickable')


def test_youtube_affiliate_warns_when_studio_declaration_not_mentioned(tmp_path):
    c = complete(tmp_path); c['monetization'] = 'affiliate'; c['placement'] = 'YouTube Shorts'
    c['disclosure'] = {'text': 'Реклама', 'shown_in_creative': True, 'placement': 'в кадре'}; dump(tmp_path, c)
    assert has(audit(tmp_path, 'launch')['warnings'], 'paid promotion declaration')
    c['disclosure']['placement'] = 'в кадре и галочка «платная реклама» в YouTube Studio'; dump(tmp_path, c)
    assert not has(audit(tmp_path, 'launch')['warnings'], 'paid promotion declaration')


@pytest.mark.parametrize('plc,said,needle', [('TikTok', 'в кадре', 'TikTok'), ('Instagram Reels', 'в кадре', 'Instagram')])
def test_other_platform_label_warnings(tmp_path, plc, said, needle):
    c = complete(tmp_path); c['monetization'] = 'affiliate'; c['placement'] = plc
    c['disclosure'] = {'text': 'Реклама', 'shown_in_creative': True, 'placement': said}; dump(tmp_path, c)
    assert has(audit(tmp_path, 'launch')['warnings'], needle + ':')
