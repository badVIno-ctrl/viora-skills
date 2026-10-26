"""Offline contract tests, not agent behavior or advertising-performance tests."""
import copy
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from shortskit.advertising import audit, initialize
from shortskit.release import audit as release_audit
from shortskit.util import ShortsError

ROOT = Path(__file__).resolve().parents[2]


def dump(d, c):
    (d / 'campaign.json').write_text(json.dumps(c, ensure_ascii=False), encoding='utf-8')


def complete(d):
    """Fabricated reviewer evidence for code tests ONLY; never a publishable asset."""
    c = json.loads((ROOT / 'schema/campaign.example.json').read_text())
    proof = {'reference': 'https://example.invalid/fixture-terms', 'checked_at': datetime.date.today().isoformat(),
             'scope': 'Synthetic test only, not actual official verification'}
    c.update(training_product=False, monetization='own_product', placement='synthetic_account',
             destination='https://example.invalid/demo', headline='Проверить текст', cta='Открыть пример',
             claims_verified=True, rights_verified=True, publication_approved=True)
    c['audience'] = dict(country='fixture-country', age='18+', language='ru', need='fixture need')
    for key in c['offer']:
        c['offer'][key] = 'fixture written terms; not real approval'
    c['offer'].update(official_terms_url=proof['reference'], checked_at=proof['checked_at'],
                      source_status='allowed', audience_country='fixture-country', audience_age='18+')
    c['canvas']['status'] = 'final'
    c['overlay'].update(start_seconds=1, end_seconds=6, rectangle=[40, 100, 1000, 250])
    c['safe_area'] = dict(method='fixture preview', verified=True, evidence='synthetic UI review')
    c['claims'] = [{'text': 'Synthetic function claim', 'verified': True, 'evidence': copy.deepcopy(proof)}]
    c['assets'] = [{'path': 'synthetic.txt', 'rights_verified': True, 'evidence': copy.deepcopy(proof)}]
    c['rules'] = copy.deepcopy(proof)
    c['tracking'] = dict(method='channel log', attribution_level='channel',
                         limitations='No per-creative conversion attribution', evidence='fixture event definitions')
    c['route'] = dict(link_point='profile', verified=True, evidence='fixture route report')
    c['test'].update(hypothesis='Clearer function demo helps', primary_metric='confirmed actions per click',
                     event_source='fixture click and action logs', observation_window='same cohort, 7 days plus hold',
                     stop_condition='wrong link or noncompliance: stop immediately', currency='RUB')
    c['author'] = 'fixture-agent'
    c['reviewer'] = {'name': 'Fixture Human Reviewer', 'role': 'fixture owner', 'is_human': True,
                     'confirmed_at': datetime.date.today().isoformat(), 'statement': 'Synthetic test statement only'}
    c['variants'] = [{'id': 'A', 'concept': 'demonstration', 'headline': 'Проверить текст перед публикацией', 'cta': 'Открыть пример', 'hypothesis': 'Clear demo helps'},
                     {'id': 'B', 'concept': 'problem_solution', 'headline': 'Одно слово меняет смысл', 'cta': 'Сверить текст', 'hypothesis': 'Problem framing helps'}]
    c['authorization'].update(scope='synthetic account, one post, 2020-01-01, no spend', evidence='fixture authorization')
    for item in c['qa'].values():
        item.update(passed=True, evidence='synthetic reviewer evidence, not an actual creative review')
    (d / 'synthetic.txt').write_bytes(b'synthetic test artifact - not an MP4 or advertisement')
    c['final_artifact'] = {'path': 'synthetic.txt', 'sha256': hashlib.sha256((d / 'synthetic.txt').read_bytes()).hexdigest()}
    dump(d, c)
    return c


def test_schema_valid():
    schema = json.loads((ROOT / 'schema/campaign.schema.json').read_text())
    Draft202012Validator.check_schema(schema)


def test_ad_init_creates_draft_and_all_templates(tmp_path):
    r = initialize(tmp_path)
    assert len(r['created']) == 6
    assert (tmp_path / 'storyboard.md').exists()
    assert audit(tmp_path)['valid'] and not audit(tmp_path)['ready_for_launch']
    assert not audit(tmp_path, 'launch')['ready_for_launch']


def test_ad_init_never_overwrites_partial_or_full_work(tmp_path):
    (tmp_path / 'brief.md').write_text('keep me')
    with pytest.raises(ShortsError):
        initialize(tmp_path)
    assert (tmp_path / 'brief.md').read_text() == 'keep me'
    assert not (tmp_path / 'campaign.json').exists()


def test_declared_complete_evidence_passes(tmp_path):
    complete(tmp_path)
    r = audit(tmp_path, 'launch')
    assert r['valid'] and r['ready_for_launch']
    assert 'no external verification' in r['verification']


@pytest.mark.parametrize('status,approved,passed', [
    ('unknown', None, False), ('forbidden', 'fake approval', False),
    ('approval_required', None, False), ('approval_required', 'fixture approval', True),
    ('allowed', None, True),
])
def test_permission_states(tmp_path, status, approved, passed):
    c = complete(tmp_path)
    c['offer'].update(source_status=status, approval_evidence=approved)
    dump(tmp_path, c)
    assert audit(tmp_path, 'launch')['ready_for_launch'] is passed


@pytest.mark.parametrize('field', ['claims_verified', 'rights_verified', 'publication_approved'])
def test_false_global_flags_block_launch(tmp_path, field):
    c = complete(tmp_path); c[field] = False; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['ready_for_launch']


@pytest.mark.parametrize('field', ['country', 'age'])
def test_geo_age_mismatch_blocks(tmp_path, field):
    c = complete(tmp_path); c['audience'][field] = 'different'; dump(tmp_path, c)
    assert any('mismatch' in i for i in audit(tmp_path, 'launch')['issues'])


@pytest.mark.parametrize('key', ['claims', 'assets'])
def test_item_evidence_required_even_with_true_global_flag(tmp_path, key):
    c = complete(tmp_path); c[key][0]['evidence']['reference'] = ' '; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


def test_unverified_claim_blocks(tmp_path):
    c = complete(tmp_path); c['claims'][0]['verified'] = False; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


def test_unknown_rights_block(tmp_path):
    c = complete(tmp_path); c['assets'][0]['rights_verified'] = False; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


@pytest.mark.parametrize('field', ['claims', 'assets'])
def test_empty_registry_blocks(tmp_path, field):
    c = complete(tmp_path); c[field] = []; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


@pytest.mark.parametrize('key', ['phone_readability', 'motion_audio', 'landing', 'disclosure', 'measurement'])
def test_missing_review_blocks(tmp_path, key):
    c = complete(tmp_path); c['qa'][key]['passed'] = False; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


def test_training_can_draft_never_launch(tmp_path):
    c = complete(tmp_path); c.update(training_product=True, monetization='training'); dump(tmp_path, c)
    assert audit(tmp_path)['valid']
    assert not audit(tmp_path, 'launch')['ready_for_launch']


@pytest.mark.parametrize('level', ['channel', 'period', 'creative'])
def test_honest_attribution_levels_allowed(tmp_path, level):
    c = complete(tmp_path); c['tracking']['attribution_level'] = level
    if level == 'creative':
        c['tracking']['method'] = 'SubID per creative passed by the network, checked in test click'
    dump(tmp_path, c)
    assert audit(tmp_path, 'launch')['valid']


def test_unknown_attribution_blocks(tmp_path):
    c = complete(tmp_path); c['tracking']['attribution_level'] = 'unknown'; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


@pytest.mark.parametrize('approved', [False, True])
def test_paid_spend_requires_separate_approval(tmp_path, approved):
    c = complete(tmp_path); c['authorization'].update(paid_media=True, spend_approved=approved, stop_method='fixture stop')
    c['test'].update(spend_limit=100, max_loss=50); dump(tmp_path, c)
    assert audit(tmp_path, 'launch')['valid'] is approved


def test_paid_media_cannot_launch_zero_budget(tmp_path):
    c = complete(tmp_path); c['authorization'].update(paid_media=True, spend_approved=True, stop_method='stop'); dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


def test_production_budget_also_requires_approval(tmp_path):
    c = complete(tmp_path); c['test']['spend_limit'] = 100; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


@pytest.mark.parametrize('overlay', [
    {'start_seconds': 2, 'end_seconds': 1}, {'start_seconds': None, 'end_seconds': 3},
    {'rectangle': [0, 0, 2000, 200]}, {'rectangle': [0, 0, 0, 200]},
])
def test_invalid_overlay_rejected_in_draft(tmp_path, overlay):
    c = complete(tmp_path); c['overlay'].update(overlay); dump(tmp_path, c)
    assert not audit(tmp_path)['valid']


def test_blank_overlay_permitted_in_draft_not_launch(tmp_path):
    c = complete(tmp_path); c['overlay'].update(start_seconds=None, end_seconds=None, rectangle=None); dump(tmp_path, c)
    assert audit(tmp_path)['valid'] and not audit(tmp_path, 'launch')['valid']


def test_static_ad_no_fake_video_required(tmp_path):
    c = complete(tmp_path); c['creative_type'] = 'static_ad'
    c['overlay'].update(start_seconds=None, end_seconds=None, rectangle=None)
    c['qa']['motion_audio']['evidence'] = 'not applicable: synthetic static fixture inspected'
    dump(tmp_path, c)
    assert audit(tmp_path, 'launch')['valid']


def test_final_file_changes_invalidate_review(tmp_path):
    complete(tmp_path); (tmp_path / 'synthetic.txt').write_bytes(b'changed')
    assert any('hash mismatch' in i for i in audit(tmp_path, 'launch')['issues'])


@pytest.mark.parametrize('path', ['../outside', '/etc/hostname'])
def test_artifact_outside_job_rejected(tmp_path, path):
    c = complete(tmp_path); c['final_artifact']['path'] = path; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


def test_missing_artifact_blocks(tmp_path):
    complete(tmp_path); (tmp_path / 'synthetic.txt').unlink()
    assert not audit(tmp_path, 'launch')['valid']


def test_manifest_binds_to_same_artifact(tmp_path):
    complete(tmp_path); (tmp_path / 'manifest.json').write_text(json.dumps({'video':'different.mp4','duration':30}))
    assert any('differs from manifest' in i for i in audit(tmp_path, 'launch')['issues'])


def test_interval_exceeds_final_timeline(tmp_path):
    complete(tmp_path); (tmp_path / 'manifest.json').write_text(json.dumps({'video':'synthetic.txt','duration':2}))
    assert any('duration' in i for i in audit(tmp_path, 'launch')['issues'])


@pytest.mark.parametrize('value', ['bad', '2020-99-99', '2999-01-01'])
def test_invalid_or_future_dates_block(tmp_path, value):
    c = complete(tmp_path); c['rules']['checked_at'] = value; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


@pytest.mark.parametrize('value', ['{bad json', '[]', '{"unknown":1}'])
def test_bad_json_and_schema_fail_closed(tmp_path, value):
    (tmp_path / 'campaign.json').write_text(value)
    assert not audit(tmp_path, 'launch')['valid']


def write_release(d):
    m = dict(duration=10, contains_speech=False, chapters=[], motion_reviewed=True,
             audio_listened=True, editorial_accepted=True, sources_verified=True,
             ui_overlay_reviewed=True, music_required=False, qr_required=False)
    (d / 'release.json').write_text(json.dumps(m))
    (d / 'ОПИСАНИЕ.txt').write_text('Описание синтетического теста.')
    return m


def test_legacy_non_ad_release_unchanged(tmp_path):
    write_release(tmp_path)
    assert release_audit(tmp_path)['ready']


def test_marked_ad_missing_campaign_fails_release(tmp_path):
    m = write_release(tmp_path); m['advertising'] = True
    (tmp_path / 'release.json').write_text(json.dumps(m))
    assert not release_audit(tmp_path)['ready']


def test_campaign_presence_requires_ad_gate_even_without_flag(tmp_path):
    write_release(tmp_path); initialize(tmp_path)
    assert not release_audit(tmp_path)['ready']


def test_complete_campaign_passes_combined_declared_gate(tmp_path):
    write_release(tmp_path); complete(tmp_path)
    assert release_audit(tmp_path)['ready']


def test_cli_init_draft_launch_and_overwrite(tmp_path):
    cli = [sys.executable, str(ROOT / 'tools/shorts.py')]
    d = tmp_path / 'cli'
    assert subprocess.run(cli + ['ad-init', str(d)], capture_output=True).returncode == 0
    r = subprocess.run(cli + ['ad-check', str(d), '--stage', 'draft'], capture_output=True, text=True)
    assert r.returncode == 0 and not json.loads(r.stdout)['ready_for_launch']
    assert subprocess.run(cli + ['ad-check', str(d), '--stage', 'launch'], capture_output=True).returncode == 1
    assert subprocess.run(cli + ['ad-init', str(d)], capture_output=True).returncode == 2
    assert (d / 'ad-qa.json').exists()


def test_entrypoint_routes_and_complete_pdf_source_present():
    skill = (ROOT / 'SKILL.md').read_text()
    assert 'reference/advertising.md' in skill and 'не требовать рекламный продукт' in skill
    for name in ('advertising', 'ad-creative', 'ad-offers-traffic', 'ad-analytics', 'ad-qa'):
        assert (ROOT / f'reference/{name}.md').exists()
    assert (ROOT / 'research/advertising/agent-banners-traffic-v1.0.pdf').exists()


@pytest.mark.parametrize('token', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_json_numbers_rejected(tmp_path, token):
    c = complete(tmp_path)
    text = json.dumps(c).replace('"spend_limit": 0', '"spend_limit": ' + token)
    (tmp_path / 'campaign.json').write_text(text)
    assert not audit(tmp_path)['valid']


@pytest.mark.parametrize('kind', ['tts', 'cover'])
def test_paid_http_requests_fail_before_network_without_consent(tmp_path, monkeypatch, kind):
    from shortskit.engine import tts
    from shortskit.meta import cover
    monkeypatch.delenv('SHORTS_ALLOW_PAID', raising=False)
    def forbidden(*a, **k):
        pytest.fail('network must never be called without paid consent')
    monkeypatch.setattr('urllib.request.urlopen', forbidden)
    fn = tts._http_json if kind == 'tts' else cover._post
    with pytest.raises(ShortsError, match='Paid API disabled'):
        fn('https://example.invalid', {}, {})


@pytest.mark.parametrize('kind', ['tts', 'cover'])
def test_scoped_paid_opt_in_allows_mock_request(monkeypatch, tmp_path, kind):
    from shortskit.engine import tts
    from shortskit.meta import cover
    monkeypatch.setenv('SHORTS_ALLOW_PAID', '1')
    monkeypatch.setenv('SHORTS_PAID_BUDGET', '5')
    monkeypatch.setenv('SHORTS_PAID_LEDGER', str(tmp_path / 'ledger.json'))
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{}'
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: Response())
    if kind == 'tts':
        assert tts._http_json('https://example.invalid', {}, {}) == b'{}'
    else:
        assert cover._post('https://example.invalid', {}, {}) == {}


def test_rules_require_a_source_url(tmp_path):
    c = complete(tmp_path); c['rules']['reference'] = 'Trust an old blog summary'; dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']
