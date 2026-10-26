"""Offline tests for ad-render, ad-seal, ad-links, ad-metrics and the CLI wiring (1.7.0 / traffic v3.5)."""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from test_advertising_v34 import complete, dump, ROOT  # noqa: E402
from shortskit import adlinks, admetrics, adrender
from shortskit.advertising import audit
from shortskit.util import ShortsError

CLI = [sys.executable, str(ROOT / 'tools/shorts.py')]


def campaign(tmp_path, **creative):
    c = complete(tmp_path)
    c['training_product'] = True
    c['monetization'] = 'training'
    c['headline'] = 'Проверка текста до публикации'
    c['cta'] = 'Открыть пример'
    c['creative'] = {'kicker': 'Учебный пример', 'subline': 'Читаемость на телефоне', 'proof': {'type': 'none'}, **creative}
    dump(tmp_path, c)
    return c


def cli(*args):
    return subprocess.run(CLI + [str(a) for a in args], capture_output=True, text=True, timeout=120)


# ---------- ad-render ----------
def test_render_outputs_color_mono_preview_and_report(tmp_path):
    campaign(tmp_path)
    rep = adrender.render(tmp_path, ('9x16', '1x1'))
    for name in ('banner-9x16.png', 'banner-9x16-mono.png', 'preview-9x16-360.png', 'banner-1x1.png', 'banner-report.json'):
        assert (tmp_path / 'banners' / name).is_file(), name
    assert Image.open(tmp_path / 'banners/banner-9x16.png').size == (1080, 1920)
    assert Image.open(tmp_path / 'banners/banner-1x1.png').size == (1080, 1080)
    assert Image.open(tmp_path / 'banners/preview-9x16-360.png').width == 360
    assert rep['ok'] is True
    assert 'meaning' in rep['verification']  # states what it does NOT check


def test_render_is_deterministic(tmp_path):
    campaign(tmp_path)
    a = adrender.render(tmp_path, ('1x1',))['outputs'][0]['color']['sha256']
    b = adrender.render(tmp_path, ('1x1',))['outputs'][0]['color']['sha256']
    assert a == b


def test_render_low_contrast_brand_is_reported(tmp_path):
    campaign(tmp_path, brand={'bg': '#777777', 'fg': '#888888', 'accent': '#7a7a7a'})
    rep = adrender.render(tmp_path, ('1x1',))
    assert rep['ok'] is False
    assert any('contrast' in p for p in rep['outputs'][0]['color']['problems'])


def test_render_unknown_platform_and_ratio_fail(tmp_path):
    campaign(tmp_path)
    with pytest.raises(ShortsError, match='unknown platform'):
        adrender.render(tmp_path, ('9x16',), ('no_such_platform',))
    with pytest.raises(ShortsError, match='unknown ratio'):
        adrender.render(tmp_path, ('3x7',))


def test_render_empty_headline_fails(tmp_path):
    c = campaign(tmp_path)
    c['headline'] = '  '
    dump(tmp_path, c)
    with pytest.raises(ShortsError, match='headline'):
        adrender.render(tmp_path)


def test_render_absurdly_long_headline_overflows_or_shrinks_honestly(tmp_path):
    c = campaign(tmp_path)
    c['headline'] = 'очень ' * 60
    dump(tmp_path, c)
    try:
        rep = adrender.render(tmp_path, ('1x1',))
    except adrender.Overflow:
        return
    assert rep['outputs'][0]['shrink_factor'] < 1.0 or rep['ok'] is False


def test_render_proof_image_must_stay_inside_campaign_dir(tmp_path):
    outside = tmp_path.parent / 'outside.png'
    Image.new('RGB', (40, 40), 'red').save(outside)
    camp = tmp_path / 'camp'
    camp.mkdir()
    campaign(camp, proof={'type': 'image', 'image': '../outside.png'})
    with pytest.raises(ShortsError, match='outside'):
        adrender.render(camp, ('1x1',))


def test_render_proof_image_undeclared_asset_is_a_problem(tmp_path):
    Image.new('RGB', (200, 120), '#335577').save(tmp_path / 'shot.png')
    campaign(tmp_path, proof={'type': 'image', 'image': 'shot.png', 'caption': 'Пример экрана'})
    rep = adrender.render(tmp_path, ('1x1',))
    assert any('not declared in assets' in p for p in rep['outputs'][0]['color']['problems'])


def test_render_training_product_gets_training_badge(tmp_path):
    campaign(tmp_path)
    rep = adrender.render(tmp_path, ('1x1',))
    labels = [b['label'] for b in rep['outputs'][0]['color']['boxes']]
    assert 'badge' in labels


def test_render_disclosure_is_rendered_or_flagged(tmp_path):
    c = campaign(tmp_path)
    c['disclosure'] = {'text': 'Реклама. Учебный макет.', 'shown_in_creative': True, 'placement': 'footer'}
    dump(tmp_path, c)
    rep = adrender.render(tmp_path, ('1x1',))
    labels = [b['label'] for b in rep['outputs'][0]['color']['boxes']]
    assert 'footnote' in labels


def test_render_never_modifies_campaign_json(tmp_path):
    campaign(tmp_path)
    before = (tmp_path / 'campaign.json').read_bytes()
    adrender.render(tmp_path, ('9x16',))
    assert (tmp_path / 'campaign.json').read_bytes() == before


# ---------- ad-seal ----------
def test_seal_records_hash_and_approves_nothing(tmp_path):
    campaign(tmp_path)
    adrender.render(tmp_path, ('1x1',))
    before = json.loads((tmp_path / 'campaign.json').read_text())
    res = adrender.seal(tmp_path, 'banners/banner-1x1.png')
    after = json.loads((tmp_path / 'campaign.json').read_text())
    assert res['sha256'] == hashlib.sha256((tmp_path / 'banners/banner-1x1.png').read_bytes()).hexdigest()
    assert after['final_artifact'] == res
    for k in ('claims_verified', 'rights_verified', 'publication_approved', 'qa', 'reviewer'):
        assert after[k] == before[k]


def test_seal_rejects_missing_and_outside_files(tmp_path):
    camp = tmp_path / 'camp'
    camp.mkdir()
    campaign(camp)
    (tmp_path / 'x.png').write_bytes(b'x')
    with pytest.raises(ShortsError):
        adrender.seal(camp, 'nope.png')
    with pytest.raises(ShortsError):
        adrender.seal(camp, '../x.png')


def test_seal_then_edit_breaks_launch_hash(tmp_path):
    campaign(tmp_path)
    adrender.render(tmp_path, ('1x1',))
    adrender.seal(tmp_path, 'banners/banner-1x1.png')
    with (tmp_path / 'banners/banner-1x1.png').open('ab') as f:
        f.write(b'tamper')
    assert any('hash' in i.lower() or 'sha256' in i.lower() for i in audit(tmp_path, 'launch')['issues'])


# ---------- ad-links ----------
def test_links_one_per_creative_with_utm():
    plan = adlinks.build('https://example.invalid/p', ['Демо A', 'b'], 'Моя кампания')
    assert len(plan['rows']) == 2
    urls = [r['url'] for r in plan['rows']]
    assert len(set(urls)) == 2
    assert all('utm_content=' in u and 'utm_source=youtube-shorts' in u for u in urls)


def test_links_signed_url_is_not_modified():
    plan = adlinks.build('https://partner.invalid/c/abc123/', ['a', 'b'], 'k', signed=True)
    assert all(r['url'] == 'https://partner.invalid/c/abc123/' for r in plan['rows'])
    assert any('untouched' in n.lower() for n in plan['notes'])


def test_links_subid_param_added_per_creative():
    plan = adlinks.build('https://example.invalid/p', ['a', 'b'], 'k', subid_param='subid')
    assert 'subid=a' in plan['rows'][0]['url'] and 'subid=b' in plan['rows'][1]['url']


def test_links_pii_ids_and_destination_rejected():
    with pytest.raises(ShortsError):
        adlinks.build('https://example.invalid/p', ['ivan@example.com'], 'k')
    with pytest.raises(ShortsError):
        adlinks.build('https://example.invalid/p?email=ivan@example.com', ['a'], 'k')


def test_links_duplicate_ids_after_normalisation_rejected():
    with pytest.raises(ShortsError):
        adlinks.build('https://example.invalid/p', ['A b', 'a-b'], 'k')
    with pytest.raises(ShortsError):
        adlinks.build('https://example.invalid/p', [], 'k')
    with pytest.raises(ShortsError):
        adlinks.build('', ['a'], 'k')


def test_links_shared_profile_link_downgrades_attribution():
    plan = adlinks.build('https://example.invalid/p', ['a', 'b'], 'k', shared_profile_link=True)
    assert plan['attribution_level_suggested'] != 'creative'


def test_links_write_files(tmp_path):
    plan = adlinks.build('https://example.invalid/p', ['a', 'b'], 'k')
    files = adlinks.write(tmp_path, plan)
    assert all(Path(f).is_file() for f in files)
    rows = list(csv.DictReader((tmp_path / 'links.csv').open(encoding='utf-8')))
    assert [r['creative_id'] for r in rows] == ['a', 'b']


# ---------- ad-metrics ----------
PDF_EXAMPLE = {'currency': 'RUB', 'link_clicks': 100, 'actions': 5, 'confirmed': 3, 'pending': 0, 'rejected': 2,
               'payout_per_action': 3000, 'spend_total': 1200}


def test_metrics_money_arithmetic():
    m = admetrics.compute({'currency': 'RUB', 'link_clicks': 100, 'actions': 5, 'confirmed': 3, 'rejected': 2, 'pending': 0,
                           'payout_per_action': 3000, 'spend_total': 1200})
    assert m['rewards']['confirmed'] == 9000.0
    assert m['rates']['cr_pct'] == 5.0
    assert m['rates']['approval_pct'] == 60.0
    assert m['rates']['epc'] == 90.0


def test_metrics_rejects_bad_numbers():
    for bad in (-1, float('nan'), float('inf'), True, '5', 2.5):
        with pytest.raises(ShortsError):
            admetrics.compute({**PDF_EXAMPLE, 'link_clicks': bad})


def test_metrics_confirmed_cannot_exceed_actions():
    with pytest.raises(ShortsError):
        admetrics.compute({**PDF_EXAMPLE, 'confirmed': 9})


def test_metrics_small_sample_is_preliminary_and_not_a_verdict():
    res = admetrics.run(PDF_EXAMPLE)
    assert res['metrics']['status'] == 'preliminary'
    assert res['decision']['decision'] in ('INSUFFICIENT_DATA', 'HOLD')


def test_metrics_stop_on_compliance_flag():
    for flag in ('rule_violation', 'wrong_link', 'offer_mismatch'):
        res = admetrics.run({**PDF_EXAMPLE, 'flags': {flag: True}})
        assert res['decision']['decision'] == 'STOP', flag


def test_metrics_stop_on_agreed_limits():
    res = admetrics.run({**PDF_EXAMPLE, 'limits': {'spend_limit': 1000}})
    assert res['decision']['decision'] == 'STOP'
    res = admetrics.run({**PDF_EXAMPLE, 'spend_total': 10000, 'limits': {'max_loss': 100}})
    assert res['decision']['decision'] == 'STOP'


def test_metrics_variants_marked_as_quasi_experiment():
    res = admetrics.run({**PDF_EXAMPLE, 'variants': [{'id': 'A', 'link_clicks': 50, 'actions': 2, 'confirmed': 1, 'rejected': 0, 'pending': 1},
                                                      {'id': 'B', 'link_clicks': 50, 'actions': 3, 'confirmed': 2, 'rejected': 0, 'pending': 1}]})
    assert [v['id'] for v in res['variants']] == ['A', 'B']
    assert 'quasi-experiment' in res['variants_note']


def test_metrics_log_is_append_only(tmp_path):
    admetrics.append_log(tmp_path, {'a': 1})
    admetrics.append_log(tmp_path, {'a': 2})
    lines = (tmp_path / 'experiments.jsonl').read_text().strip().splitlines()
    assert [json.loads(x)['a'] for x in lines] == [1, 2]


def test_metrics_zero_denominators_give_none_not_crash():
    m = admetrics.compute({'currency': 'RUB'})
    assert m['rates']['cr_pct'] is None


# ---------- CLI ----------
def test_cli_render_seal_check_roundtrip(tmp_path):
    campaign(tmp_path)
    r = cli('ad-render', tmp_path, '--ratios', '1x1')
    assert r.returncode == 0, r.stderr + r.stdout
    r = cli('ad-seal', tmp_path, '--artifact', 'banners/banner-1x1.png')
    assert r.returncode == 0, r.stderr
    r = cli('ad-check', tmp_path, '--stage', 'draft', '--today', '2026-10-20')
    assert r.returncode in (0, 1)
    assert json.loads(r.stdout)['stage'] == 'draft'


def test_cli_links_and_metrics_and_paid(tmp_path):
    c = campaign(tmp_path)
    r = cli('ad-links', tmp_path, '--ids', 'a,b')
    assert r.returncode == 0, r.stderr
    assert (tmp_path / 'links.csv').is_file()
    m = tmp_path / 'm.json'
    m.write_text(json.dumps(PDF_EXAMPLE))
    r = cli('ad-metrics', m, '--log', tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / 'experiments.jsonl').is_file()
    r = cli('paid', 'status')
    assert r.returncode == 0 and json.loads(r.stdout)['allow_paid'] in (True, False)


def test_cli_usage_errors_exit_2(tmp_path):
    assert cli('ad-render', tmp_path / 'missing').returncode == 2
    assert cli('ad-seal', tmp_path, '--artifact', 'x').returncode == 2
    bad = tmp_path / 'bad.json'
    bad.write_text('{not json')
    assert cli('ad-metrics', bad).returncode == 2


# ---------- plan lint: banner fields in the wrong place ----------
def test_plan_lint_flags_banner_fields_inside_animation():
    from shortskit.plan import lint
    plan = json.loads((ROOT / 'tests/fixtures/plan.offline.json').read_text())
    plan['layout']['bottom']['animation'] = {'enabled': True, 'name': 'X', 'message': 'Y', 'action': 'Z'}
    assert any(i.code == 'banner_fields' for i in lint(plan, ROOT / 'tests/fixtures'))
    plan['layout']['bottom']['animation'] = {'enabled': True}
    assert not any(i.code == 'banner_fields' for i in lint(plan, ROOT / 'tests/fixtures'))


def test_links_youtube_note_about_non_clickable_urls():
    plan = adlinks.build('https://example.invalid/p', ['a'], 'k')
    assert any('non-clickable' in n for n in plan['notes'])
    plan = adlinks.build('https://example.invalid/p', ['a'], 'k', source='other_platform', medium='social')
    assert not any('non-clickable' in n for n in plan['notes'])


def test_metrics_pdf_training_example_and_template_file():
    data = json.loads((ROOT / 'templates/advertising/metrics.example.json').read_text())
    res = admetrics.run(data)
    m = res['metrics']
    assert m['rates']['epc'] == 15.0 and m['rates']['epc_per_100_clicks'] == 1500.0
    assert m['rates']['cr_pct'] == 5.0 and m['rates']['approval_pct'] == 60.0 and m['rates']['cost_per_confirmed'] == 200.0
    assert m['profit_confirmed'] == 1800.0
    assert m['status'] == 'preliminary'
    assert 'roi_pct' in json.dumps(m) and '150' in json.dumps(m)
