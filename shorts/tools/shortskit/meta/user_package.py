"""One readable handoff, no new dependencies. JSON stays an internal agent interface."""
from __future__ import annotations

from pathlib import Path

from .. import memory as M
from ..util import ShortsError, fix_dashes, read_json


def _read(p: Path) -> dict:
    return read_json(p) if p.exists() else {}


CHECK_LABELS = {
    'format': ('размер, формат и длительность файла', 'file dimensions, format and duration'),
    'first_frame': ('непустое начало и движение', 'nonempty opening and motion'),
    'rhythm': ('ритм смены событий', 'event pacing'),
    'safe_zone': ('расположение текста и ссылок вне кнопок приложения', 'text and links outside app controls'),
    'contrast': ('контраст и размер букв', 'contrast and letter size'),
    'layout': ('размер главного изображения и заполненность кадра', 'main image size and frame use'),
    'anti_slop': ('отсутствие запрещённых эффектов оформления', 'absence of disallowed design effects'),
    'qr': ('проверка QR, если он есть', 'QR check, when present'),
    'captions': ('техническая проверка субтитров', 'technical caption check'),
    'loudness': ('измеренная громкость и отсутствие перегрузки', 'measured loudness and clipping'),
    'loop': ('стык начала и конца', 'opening and ending connection'),
    'metadata': ('формальные ограничения названий и подписей', 'formal title and copy limits'),
    'distinct': ('сравнение с предыдущими роликами в памяти', 'comparison with videos in memory'),
    'text_rules': ('формальные правила текста', 'formal text rules'),
    'edit_content': ('проверка кадров эдита, если применимо', 'edit frame check, when applicable'),
    'beat_sync': ('попадание склеек в бит, если применимо', 'beat alignment, when applicable'),
    'edit_style': ('параметры эдита, если применимо', 'edit settings, when applicable'),
    'vfx': ('частота вспышек и параметры эффектов', 'flash frequency and effect settings'),
    'author_layer': ('заявленные авторские слои, если есть чужой материал', 'declared author layers on reused footage'),
    'eyes': ('просмотр кадров глазами ИИ', 'AI frame review'),
    'silent': ('понимание ролика без звука', 'understanding without sound'),
    'motion_audio': ('непрерывный просмотр движения и прослушивание звука', 'continuous movement and audio review'),
    'decode': ('декодирование всего видео и звука', 'full video and audio decode'),
    'audio_loudness': ('громкость длинного ролика', 'long video loudness'),
    'black_silence': ('поиск чёрных и тихих интервалов', 'black and silent interval detection'),
}


def refresh_if_exists(d: Path) -> None:
    """A TXT refresh must not change the established render/meta/cover/QA exit contract."""
    if (d / 'ПАКЕТ.txt').exists():
        try:
            write_package(d)
        except (ShortsError, OSError, ValueError):
            import logging
            logging.getLogger('shorts').warning('Package needs agent refresh/localization; existing TXT was not replaced.')


def write_package(d: Path, lang: str | None = None) -> Path:
    """Rebuild after the final meta, cover, QA and visual review. Never infer a visual pass."""
    manifest = _read(d / 'manifest.json')
    meta = _read(d / 'metadata.json')
    if not manifest or not meta:
        raise ShortsError('Run render and meta before package (manifest and metadata are required).')
    plan = _read(d / 'plan.resolved.json')
    cover = _read(d / 'cover' / 'cover.json')
    qa = _read(d / 'qa.json')
    prefs = M.load()
    language = (lang or (M.chat_lang(prefs) if 'language' in prefs else manifest.get('language', 'ru')))[:2]
    # Only these built-in labels are translated. Agent localizes the complete handoff for other languages.
    if language not in ('ru', 'en'):
        raise ShortsError('Package labels support ru/en. Agent must write the same plain-text structure in the user language.')
    ru = language == 'ru'
    def tr(a: str, b: str) -> str:
        return a if ru else b
    def section(a: str, b: str):
        out.extend(['', tr(a, b), ''])
    out = [tr('ПАКЕТ ДЛЯ ПУБЛИКАЦИИ', 'PUBLISHING PACKAGE'), str(manifest.get('name', d.name))]
    video = d / manifest.get('video', 'video.mp4')
    checks = qa.get('checks') or []
    manual = [c for c in checks if c.get('id') in ('eyes', 'silent')]
    eyes = next((c for c in manual if c.get('id') == 'eyes'), {})
    reviewed = eyes.get('status') == 'pass' and bool((qa.get('review') or {}).get('saw'))
    ready = (video.is_file() and qa.get('passed') is True and reviewed
             and all(c.get('status') == 'pass' for c in manual) and len(manual) == 2
             and not any(c.get('status') in ('fail', 'manual', 'warn') for c in checks)
             and not meta.get('errors') and not meta.get('auto_draft')
             and bool(cover.get('variants')) and not cover.get('errors')
             and len(meta.get('pinned_comment') or []) == 3)
    # v1.6: technical QA is not publication acceptance.
    from ..release import audit
    release = audit(d) if (d / 'release.json').exists() else {'ready': False}
    ready = ready and release['ready']
    # Creative score and 150px semantics are agent-reviewed, not a code-derived readiness claim.
    out += [tr('Статус: технические материалы собраны; перед выдачей агент завершает смысловую проверку.'
               if ready else 'Статус: черновик, есть незавершённые проверки. Не считать готовым роликом.',
               'Status: technical materials collected; the agent must finish the creative review.'
               if ready else 'Status: draft, some checks are unfinished. Do not treat as a finished video.'),
            tr('Ролик: ', 'Video: ') + (video.name if video.is_file() else tr('файл не найден', 'file not found'))]
    section('РЕКОМЕНДУЕМОЕ НАЗВАНИЕ', 'RECOMMENDED TITLE')
    out += [meta.get('recommended_title') or tr('Пока не выбрано', 'Not selected yet'),
            meta.get('recommended_why') or tr('Причину выбора агент ещё не записал.', 'Selection reason not recorded yet.')]
    section('ВСЕ ВАРИАНТЫ НАЗВАНИЯ', 'ALL TITLE OPTIONS')
    for n, t in enumerate(meta.get('titles') or [], 1):
        out.append(f"{n}. {t.get('title', '')}")
        out.append(tr('Зачем: ', 'Why: ') + (t.get('why') or tr('пояснение ещё не записано', 'reason not recorded yet')))
    section('ОПИСАНИЕ ДЛЯ YOUTUBE (можно копировать)', 'YOUTUBE DESCRIPTION (copy and paste)')
    out.append((meta.get('description') or '').strip())
    section('ЗАКРЕП (3 строки)', 'PINNED COMMENT (3 lines)')
    out.extend(meta.get('pinned_comment') or [tr('Не подготовлен', 'Not prepared')])
    section('ПОДПИСЬ TIKTOK', 'TIKTOK CAPTION')
    out.append(meta.get('tiktok_caption') or tr('Не подготовлена', 'Not prepared'))
    section('ОБЛОЖКИ', 'COVERS')
    if manifest.get('format') != 'long':
        out.append(tr('Первый кадр в Shorts - это и есть обложка в ленте. Отдельные картинки нужны для других мест показа.',
                      'The first frame is the cover in the Shorts feed. Separate cover images serve other surfaces.'))
    variants = cover.get('variants') or []
    for letter, idea_ru, idea_en in [('A', 'один символ на простом фоне', 'one symbol on a plain background'),
                                    ('B', 'главный герой или предмет крупно', 'a close-up of the main subject'),
                                    ('C', 'два состояния рядом: до и после', 'two states side by side: before and after')]:
        vs = [v for v in variants if v.get('file', '').startswith(f'cover-{letter}-')]
        words = (vs[0].get('text') if vs else '') or ' '.join(cover.get('words') or []) or meta.get('cover_text') or tr('текст не выбран', 'text not selected')
        idea = tr('затемнённый кадр с крупным текстом', 'a dimmed frame with a large caption') if vs and vs[0].get('variant') == 'outline' else tr(idea_ru, idea_en)
        if manifest.get('format') == 'long':
            idea = tr('учебный вариант размещения текста на кадре 16:9', 'training text layout on a 16:9 frame')
        out += [f'{letter}: {idea}', tr('Текст: ', 'Text: ') + words]
        if vs:
            out.extend(tr('Файл: cover/', 'File: cover/') + v['file'] for v in vs)
        else:
            out.append(tr('Картинка ещё не подготовлена.', 'Image not prepared yet.'))
        if not cover.get('generated') and not any(v.get('source') == 'user' for v in vs):
            topic = (plan.get('metadata') or {}).get('topic') or meta.get('cover_text') or manifest.get('name', '')
            actual = vs[0].get('variant') if vs else ''
            idea = tr('затемнённый кадр и крупный предмет', 'a dimmed frame with a large subject') if actual == 'outline' else tr(idea_ru, idea_en)
            out.append(tr(f'Промпт: Нарисуй обложку на тему «{topic}»: {idea}. Один заметный объект, простой фон, сильный контраст, без текста, свечения и градиентов. Оставь место для надписи; агент добавит её отдельно.',
                          f'Prompt: Draw a cover about "{topic}": {idea}. One clear subject, plain background, strong contrast, no text, glow or gradients. Leave room for a caption; the agent adds it separately.'))
    if cover.get('errors'):
        out.append(tr('Есть замечания к обложкам: агент должен исправить их до выдачи.',
                      'Cover checks have warnings: the agent must resolve them before delivery.'))
    out.append(tr('Агент проверяет текст и главный объект на превью шириной 150 px; проверка по высоте букв не заменяет просмотр.',
                  'The agent checks text and subject in a 150px preview; letter height is not a visual review.'))
    section('ХЭШТЕГИ', 'HASHTAGS')
    rec = next((t for t in meta.get('titles', []) if t.get('n') == meta.get('recommended')), {})
    out.append(tr('Для названия: ', 'For the title: ') + ' '.join(rec.get('hashtags') or []))
    # build stores the exact final tag groups, no guessing from arbitrary prose
    tags = meta.get('hashtags') or {}
    out.append(tr('Для низа описания: ', 'For the bottom of the description: ') + ' '.join(tags.get('bottom') or []))
    section('ЧЕК-ЛИСТ ЗАГРУЗКИ', 'UPLOAD CHECKLIST')
    out.append(tr('1. Загрузите файл ролика.', '1. Upload the video file.'))
    out += [tr('2. Вставьте рекомендованное название, оно уже содержит выбранные хэштеги.', '2. Paste the recommended title; selected hashtags are already included.'),
            tr('3. Вставьте описание и после публикации закрепите комментарий из трёх строк.', '3. Paste the description and pin the three-line comment after publishing.'),
            tr('4. Выберите обложку; для Shorts выберите подходящий первый кадр доступным способом в приложении.', '4. Select the cover; for Shorts select a suitable first frame using the available app controls.'),
            tr('5. Пометка ИИ-контента: включите, если есть реалистичный синтетический или существенно изменённый контент; иначе решите по текущим правилам площадки. Не отключайте автоматически.', '5. AI label: turn it on for realistic synthetic or materially altered content; otherwise follow current platform rules. Do not switch it off automatically.'),
            tr('6. Проверьте предпросмотр, звук, ссылки и субтитры. Затем публикуйте.', '6. Check the preview, audio, links and captions. Then publish.')]
    section('ЧТО ПРОВЕРЕНО', 'WHAT WAS CHECKED')
    auto = [c for c in checks if c.get('id') not in ('eyes', 'silent') and c.get('status') == 'pass']
    out.append(tr('Кодом: ', 'By code: ') + (tr(f'пройдено {len(auto)} проверок ролика.', f'{len(auto)} video checks passed.') if qa else tr('QA ещё не запускался.', 'QA has not run yet.')))
    # Human-readable check titles must be localized by the agent if not Russian/English.
    for c in auto:
        if c.get('id') in CHECK_LABELS:
            out.append('- ' + tr(*CHECK_LABELS[c['id']]))
    if reviewed:
        out.append(tr('Глазами ИИ (кадры, не непрерывное воспроизведение): ', 'AI visual review (frames, not continuous playback): ') + qa['review']['saw'])
    else:
        out.append(tr('Глазами ИИ: просмотр кадров не подтверждён.', 'AI visual review: frame review is not confirmed.'))
    if (qa.get('review') or {}).get('silent') and all(c.get('status') == 'pass' for c in manual):
        out.append(tr('Без звука: ', 'Without sound: ') + qa['review']['silent'])
    out.append(tr('Не проверено автоматически: правдивость обещания, смысл, число показанных пунктов, читаемость объекта на 150 px, результат публикации. Вау-тест фиксируется агентом отдельно.',
                  'Not checked automatically: promise accuracy, meaning, number of shown items, subject clarity at 150px, publication results. The agent records the creative test separately.'))
    pending = [c for c in checks if c.get('status') != 'pass']
    if pending:
        for c in pending:
            if c.get('id') in CHECK_LABELS:
                out.append(tr('Требует внимания: ', 'Needs attention: ') + tr(*CHECK_LABELS[c['id']]))
        out.append(tr(f'Не закрыто проверок ролика: {len(pending)}. Агент объясняет и устраняет замечания перед выдачей.',
                      f'{len(pending)} video checks remain open. The agent explains and resolves them before delivery.'))
    if meta.get('auto_draft'):
        out.append(tr('Название и подписи пока запасные, собраны автоматически. Агент должен переписать их.',
                      'Titles and copy are automatic fallbacks. The agent must rewrite them.'))
    if meta.get('errors'):
        out.append(tr('Есть ошибки в подписях. Агент должен исправить их.', 'Copy checks have errors. The agent must fix them.'))
    section('ПОСЛЕ ПУБЛИКАЦИИ', 'AFTER PUBLISHING')
    out.append(tr('Через сутки и через неделю пришли мне цифры: показы, сколько досмотрели, лайки, подписки. Если есть - клики, сколько начали смотреть вместо пролистывания, средний процент просмотра и график ухода. Можно прислать скриншоты.',
                  'After one day and one week, send impressions, how many watched to the end, likes and subscribers. If available, add clicks, viewed versus swiped away, average percentage viewed and the retention graph. Screenshots are fine.'))
    out.append(tr('По цифрам выберем одну правку и проверим её на трёх следующих роликах.',
                  'The figures will guide one change, tested across the next three videos.'))
    result = d / 'ПАКЕТ.txt'
    result.write_text(fix_dashes('\n'.join(out).strip()) + '\n', encoding='utf-8')
    return result
