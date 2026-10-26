"""Follow-up contract tests; synthetic evidence is never actual launch permission."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from shortskit.advertising import audit
from test_advertising_v34 import complete, dump

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_cards_default_to_applicable(tmp_path):
    complete(tmp_path)
    rep = audit(tmp_path, 'launch')
    assert rep['valid'] and rep['not_applicable'] == []


def test_static_na_is_not_false_success(tmp_path):
    c = complete(tmp_path)
    c['creative_type'] = 'static_ad'
    for key in ('motion_audio', 'subtitles'):
        c['qa'][key] = dict(applicability='not_applicable', passed=False,
                            evidence='Synthetic static fixture: no temporal subtitles or audio; inspected still.')
    dump(tmp_path, c)
    for stage in ('draft', 'launch'):
        rep = audit(tmp_path, stage)
        assert rep['valid']
        assert set(rep['not_applicable']) == {'motion_audio', 'subtitles'}
    c['qa']['rights']['passed'] = False
    dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


@pytest.mark.parametrize('kind,key', [
    ('overlay', 'motion_audio'), ('advertising_short', 'subtitles'),
    ('static_ad', 'rights'), ('static_ad', 'cta_route'),
    ('static_ad', 'disclosure'), ('static_ad', 'phone_readability'),
])
def test_na_cannot_bypass_relevant_gates(tmp_path, kind, key):
    c = complete(tmp_path); c['creative_type'] = kind
    c['qa'][key].update(applicability='not_applicable', passed=False)
    dump(tmp_path, c)
    assert not audit(tmp_path)['valid']
    assert not audit(tmp_path, 'launch')['ready_for_launch']


@pytest.mark.parametrize('passed,evidence', [(True, 'Reason'), (False, None), (False, '  ')])
def test_na_requires_honest_nonpass_and_reason(tmp_path, passed, evidence):
    c = complete(tmp_path); c['creative_type'] = 'static_ad'
    c['qa']['motion_audio'].update(applicability='not_applicable', passed=passed, evidence=evidence)
    dump(tmp_path, c)
    assert not audit(tmp_path)['valid']


def test_explicit_applicable_retains_false_blocker(tmp_path):
    c = complete(tmp_path)
    c['qa']['motion_audio'].update(applicability='applicable', passed=False)
    dump(tmp_path, c)
    assert not audit(tmp_path, 'launch')['valid']


def test_training_goal_valid_draft_forbidden_launch(tmp_path):
    c = complete(tmp_path)
    c.update(goal='training_comprehension', training_product=True, monetization='training', destination=None)
    dump(tmp_path, c)
    assert audit(tmp_path)['valid']
    rep = audit(tmp_path, 'launch')
    assert not rep['ready_for_launch'] and 'training product cannot launch' in rep['issues']


@pytest.mark.parametrize('training,monetization', [(False, 'training'), (True, 'own_product'), (False, 'own_product')])
def test_training_goal_requires_training_mode(tmp_path, training, monetization):
    c = complete(tmp_path)
    c.update(goal='training_comprehension', training_product=training, monetization=monetization)
    dump(tmp_path, c)
    assert not audit(tmp_path)['valid']


def test_stage_reports_both_survive(tmp_path):
    complete(tmp_path)
    cli = [sys.executable, str(ROOT / 'tools/shorts.py'), 'ad-check', str(tmp_path)]
    assert subprocess.run(cli + ['--stage', 'draft'], capture_output=True).returncode == 0
    draft = (tmp_path / 'ad-qa-draft.json').read_bytes()
    c = json.loads((tmp_path / 'campaign.json').read_text()); c['training_product'] = True; dump(tmp_path, c)
    assert subprocess.run(cli + ['--stage', 'launch'], capture_output=True).returncode == 1
    assert (tmp_path / 'ad-qa-draft.json').read_bytes() == draft
    assert json.loads((tmp_path / 'ad-qa-launch.json').read_text())['stage'] == 'launch'
    assert (tmp_path / 'ad-qa.json').read_bytes() == (tmp_path / 'ad-qa-launch.json').read_bytes()


def test_training_example_has_training_goal(tmp_path):
    (tmp_path / 'campaign.json').write_bytes((ROOT / 'examples/advertising/campaign.training.json').read_bytes())
    assert json.loads((tmp_path / 'campaign.json').read_text())['goal'] == 'training_comprehension'
    assert audit(tmp_path)['valid']
