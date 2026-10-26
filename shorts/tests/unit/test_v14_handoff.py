"""1.4 regression: nontechnical intake, exact copy, honest QA and safe fallback."""
import importlib.util
from pathlib import Path

import pytest

from shortskit import memory as M
from shortskit.meta.user_package import write_package
from shortskit.meta import packaging as PK
from shortskit.util import ShortsError, write_json, read_json
from conftest import mini_plan


def seed(d, lang='ru', **over):
    manifest = {'name': 'plants', 'video': 'plants.mp4', 'language': lang, 'platforms': ['youtube_shorts']}
    plan = mini_plan()
    plan['metadata'] = {'topic': 'Пересадка растений'}
    plan['scenes'][0]['say'] = 'Этот горшок спасёт корни.'
    meta = PK.build(plan, manifest, PK.auto_draft(plan, manifest, lang), M.load())
    meta.update(over)
    for name, data in [('manifest.json', manifest), ('plan.resolved.json', plan), ('metadata.json', meta)]:
        write_json(d / name, data)
    return meta


def test_intake_simple_seven_questions_and_no_technical_terms():
    text = M.intake_message(M.empty())
    assert sum(x[:1].isdigit() for x in text.splitlines()) == 7
    assert all(x not in text for x in ['JSON', '1080', 'раскладка', 'пресет', 'движок'])
    assert 'Telegram' in text and 'для кого' in text and 'продаж' in text and 'выбери сам' in text


def test_visual_preset_does_not_hide_brand_questions():
    M.set_value('brand', {'preset': 'mono'})
    assert 'Кто вы' in M.intake_message(M.load())


def test_nested_brand_roundtrip_keeps_preset_and_pending():
    M.set_value('brand.preset', 'mono')
    M.skip('brand.profile')
    M.skip('brand.goal')
    M.set_value('brand.profile', {'name': 'Анна', 'topic': 'цветы', 'audience': 'начинающие'})
    assert M.load()['brand']['preset'] == 'mono'
    assert M.load()['pending'] == ['brand.goal']
    M.set_value('brand.goal', 'подписки')
    assert M.load()['pending'] == []


def test_no_repeat_brand_questions_and_plain_summary():
    for k, v in {'brand.profile': 'Анна, цветы, новички', 'brand.niche': 'цветы', 'brand.goal': 'подписки', 'brand.telegram': 't.me/x', 'brand.offer': 'цветы',
                 'source': 'text', 'platforms': ['youtube_shorts'], 'language': {'chat': 'ru', 'video': 'ru'},
                 'links': {}, 'qr': False, 'voice': {'engine': 'auto'}, 'brand.style_choice': 'выбери сам'}.items():
        M.set_value(k, v)
    text = M.intake_message(M.load())
    assert text.startswith('Беру настройки') and 'Кто вы' not in text
    assert '{' not in text and 'engine' not in text and 'youtube_shorts' not in text


def test_remember_cli(tmp_path):
    spec = importlib.util.spec_from_file_location('cli14', Path(__file__).resolve().parents[2] / 'tools/shorts.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    assert cli.main(['prefs', 'remember', 'rejected=неоновый стиль']) == 0
    assert M.load()['rejected'][-1]['value'] == 'неоновый стиль'


def test_package_has_copy_and_all_sections(tmp_path):
    meta = seed(tmp_path)
    text = write_package(tmp_path).read_text()
    for heading in ['РЕКОМЕНДУЕМОЕ НАЗВАНИЕ', 'ОПИСАНИЕ ДЛЯ YOUTUBE', 'ЗАКРЕП (3 строки)',
                    'ПОДПИСЬ TIKTOK', 'ОБЛОЖКИ', 'ХЭШТЕГИ', 'ЧЕК-ЛИСТ ЗАГРУЗКИ', 'ЧТО ПРОВЕРЕНО',
                    'ПОСЛЕ ПУБЛИКАЦИИ']:
        assert heading in text
    assert meta['description'].strip() in text and meta['tiktok_caption'] in text
    assert '```' not in text and '|---' not in text and 'metadata.json' not in text
    assert 'Через сутки и через неделю' in text and 'Нарисуй' in text
    assert 'черновик' in text and 'просмотр кадров не подтверждён' in text
    assert 'файл не найден' in text


def test_package_actual_cover_text_and_outline(tmp_path):
    seed(tmp_path)
    write_json(tmp_path / 'cover/cover.json', {'words': ['ОБЩИЙ', 'ТЕКСТ'], 'variants': [
        {'file': 'cover-C-outline-9x16.jpg', 'text': 'НЕ ЗАЛИВАЙ КОРНИ', 'variant': 'outline', 'source': 'frame:a'}]})
    text = write_package(tmp_path).read_text()
    assert 'Текст: НЕ ЗАЛИВАЙ КОРНИ' in text
    assert 'C: затемнённый кадр' in text


def test_package_uses_exact_tag_groups(tmp_path):
    meta = seed(tmp_path)
    text = write_package(tmp_path).read_text()
    assert 'Для низа описания: ' + ' '.join(meta['hashtags']['bottom']) in text


def test_package_does_not_copy_secrets_or_prefs(tmp_path):
    seed(tmp_path)
    M.set_value('secret', 'DO_NOT_COPY_PRIVATE_VALUE')
    assert 'DO_NOT_COPY_PRIVATE_VALUE' not in write_package(tmp_path).read_text()


def test_qa_pass_is_not_visual_review(tmp_path):
    seed(tmp_path)
    write_json(tmp_path / 'qa.json', {'passed': True, 'checks': [{'id': 'eyes', 'status': 'manual'}]})
    text = write_package(tmp_path).read_text()
    assert 'просмотр кадров не подтверждён' in text and 'черновик' in text


def test_recorded_review_is_not_full_playback(tmp_path):
    seed(tmp_path)
    write_json(tmp_path / 'qa.json', {'passed': True, 'checks': [{'id': 'eyes', 'status': 'pass'}, {'id': 'silent', 'status': 'pass'}],
                                    'review': {'saw': 'На первом кадре корни и горшок, далее автор показывает пересадку.', 'silent': 'Пересадка'}})
    text = write_package(tmp_path).read_text()
    assert 'кадры, не непрерывное воспроизведение' in text and 'автор показывает пересадку' in text


def test_user_language_not_video_language(tmp_path):
    seed(tmp_path, 'en')
    M.set_value('language', {'chat': 'ru', 'video': 'en'})
    assert 'РЕКОМЕНДУЕМОЕ НАЗВАНИЕ' in write_package(tmp_path).read_text()
    assert 'RECOMMENDED TITLE' in write_package(tmp_path, lang='en').read_text()


def test_unsupported_language_requires_agent_localization(tmp_path):
    seed(tmp_path)
    with pytest.raises(ShortsError, match='user language'):
        write_package(tmp_path, lang='fr')


def test_missing_input_fails_clearly(tmp_path):
    with pytest.raises(ShortsError, match='render and meta'):
        write_package(tmp_path)


def test_question_title_is_warning_not_error():
    plan = mini_plan()
    m = {'name': 'x', 'platforms': ['youtube_shorts'], 'language': 'ru'}
    draft = PK.auto_draft(plan, m, 'ru')
    draft['titles'][0]['text'] = 'Почему корни сгнили?'
    res = PK.build(plan, m, draft, M.load())
    assert any('question title' in w for w in res['warnings'])
    assert not res['errors']


def test_profile_only_prefs_make_valid_plan_with_default_preset():
    from shortskit.planner import skeleton
    from shortskit import plan as P
    M.set_value('brand.profile', {'name': 'Анна', 'topic': 'цветы', 'audience': 'новички'})
    p = skeleton('text', [], topic='цветы')
    assert p['brand']['preset'] == 'mono' and 'profile' not in p['brand']
    assert p['meta']['audience'] == 'новички'
    assert not P.validate_schema(p)


def test_partial_intake_does_not_repeat_language_or_ask_for_preset():
    M.set_value('language', {'chat': 'ru', 'video': 'ru'})
    M.set_value('brand.profile', 'Анна, цветы, новички')
    text = M.intake_message(M.load())
    assert 'Кто вы' not in text and 'на каком языке' not in text
    assert 'Куда выкладываем?' in text


def test_nested_reminder_is_plain_language():
    M.skip('brand.goal')
    assert 'цель канала' in M.reminder_line(M.load()) and 'brand.goal' not in M.reminder_line(M.load())


def test_auto_checks_have_plain_labels(tmp_path):
    seed(tmp_path)
    write_json(tmp_path / 'qa.json', {'passed': False, 'checks': [
        {'id': 'loudness', 'status': 'pass'}, {'id': 'safe_zone', 'status': 'fail'}]})
    text = write_package(tmp_path).read_text()
    assert 'измеренная громкость' in text
    assert 'Требует внимания: расположение текста' in text
    assert 'safe_zone' not in text


def test_refresh_failure_does_not_break_existing_qa_contract(tmp_path):
    from shortskit.meta.user_package import refresh_if_exists
    seed(tmp_path)
    p = write_package(tmp_path)
    old = p.read_text()
    M.set_value('language', {'chat': 'fr', 'video': 'fr'})
    refresh_if_exists(tmp_path)
    assert p.read_text() == old
