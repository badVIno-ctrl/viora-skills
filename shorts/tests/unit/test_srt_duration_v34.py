"""Regression for an inherited final-cue padding bug found by the full render suite."""
import pytest
from shortskit.engine.captions import to_srt
from shortskit.release import parse_srt, srt_issues


def test_final_srt_padding_clamped_to_duration():
    words=[{'w':'Без', 's':7.4, 'e':7.8}, {'w':'монтажа', 's':7.9, 'e':8.3}, {'w':'руками.', 's':8.4, 'e':9.0}]
    cues=parse_srt(to_srt(words,duration=9.0))
    assert cues[-1]['e']==9.0 and not srt_issues(cues,9.0)


def test_real_word_after_end_is_not_hidden_by_padding_fix():
    with pytest.raises(ValueError,match='Word exceeds'):
        to_srt([{'w':'Ответ.', 's':8.0, 'e':9.3}],duration=9.0)


def test_neighbouring_cue_and_final_duration_both_respected():
    words=[{'w':'Первый.', 's':0, 'e':1}, {'w':'Второй.', 's':1.05, 'e':2}]
    cues=parse_srt(to_srt(words,duration=2))
    assert cues[0]['e']==1.05 and cues[1]['e']==2
    assert not srt_issues(cues,2)


@pytest.mark.parametrize('value',[0,-1,float('inf'),float('nan')])
def test_invalid_duration_rejected(value):
    with pytest.raises(ValueError):
        to_srt([{'w':'Тест.', 's':0, 'e':1}],duration=value)
