# Результат рендера: что лежит в папке `--out`

Договор движка SHORTS с теми, кто его вызывает (Viora Studio и другие). Версия движка 1.3.0,
схема плана `schema_version` "1", "1.1", "1.2" или "1.3". Всё ниже только добавлялось: старые файлы и поля на месте.

```bash
python3 tools/shorts.py render plan.json --out DIR    # ролик + words.json + result.json + manifest.json
python3 tools/shorts.py qa DIR                         # qa.json, qa.md, contact.png, contact-*.png
python3 tools/shorts.py all plan.json --out DIR        # render + qa + meta + cover, код выхода = итог QA
```

## Файлы

| Файл | Кто пишет | Что внутри |
|---|---|---|
| `<name>.mp4` | render | ролик 1080x1920, H.264 + AAC |
| `<name>.nomusic.mp4` | render | 1.3, `audio.export: both`: тот же ролик, звук без музыки (голос + звуки) |
| `music_cue.json` | render | 1.3, `audio.export: both` или `without_music`: `{music, start, offset, drop_at, beats, note}` |
| `words.json` | render | `[{"word": str, "start": s, "end": s}]` - слова озвучки (или транскрипта) во времени ролика. Без речи: `[]` |
| `result.json` | render | `{"duration": s, "video": "<name>.mp4", "fps": 30, "schema_version": "1.1", "engine": "shorts", "engine_version": "1.1.0", "cta_schedule": [...]}` - реальная длина после озвучки |
| `captions.srt`, `captions.ass` | render | субтитры (srt по порциям, ass с подсветкой слова) |
| `manifest.json` | render | всё, что нарисовано, где и когда (по нему работает QA) |
| `plan.resolved.json` | render | план с подставленными значениями по умолчанию |
| `qa.json` | qa | итог проверки, формат ниже |
| `qa.md` | qa | то же для человека + чеклист |
| `contact.png` | qa | контактный лист 2 кадра в секунду (первая страница) |
| `contact-1.png`, `contact-2.png`... | qa | все страницы контактного листа (48 кадров на странице) |
| `qa-frames/*.png` | qa | самые плотные кадры для просмотра глазами |
| `metadata.json`, `metadata.md` | meta | названия, описание, хэштеги |
| `cover/*.jpg`, `cover/cover.json` | cover | 3 обложки (A минимал, B герой, C сплит), `recommended` - какую показать первой |
| `all.json` | all | итог `all`: QA, предупреждения обложек и метаданных |

Любой файл может отсутствовать, если шаг не запускали: вызывающий помечает пункт как "не проверено".

## qa.json

```json
{
  "passed": true,
  "video": "name.mp4",
  "duration": 24.5,
  "summary": "QA PASSED: 0 fail, 2 warn, 2 manual; ...",
  "checks": [
    {"id": "first_frame", "item": 2, "title": "...", "status": "pass", "ok": true, "detail": "...", "data": {}}
  ],
  "not_checked": ["eyes", "silent"],
  "aliases": {"first": ["first_frame"], "qr_decode": ["qr"], "...": []},
  "checklist": {}
}
```

- У КАЖДОЙ проверки есть и `status`, и `ok`.
  `status`: `pass` | `warn` | `fail` | `manual`. `ok` = `false` только при `fail`
  (предупреждение и ручной пункт не мешают выдаче).
- `passed` = нет ни одного `fail`.
- `not_checked` - id пунктов, которые код не проверяет: их смотрит агент глазами (`review DIR --saw "..."`).

## Имена проверок и слова, по которым ищет Viora

| Слово Viora | id в qa.json | Что проверяет |
|---|---|---|
| `first` | `first_frame` | первый кадр не пустой, движение в первые 1.5 с |
| `motion` | `first_frame`, `rhythm`, `layout` | движение в начале, нет паузы > 1 с, верхняя панель живая (>= 30% пикселей в секунду) |
| `pause` | `rhythm` | событие не реже раза в 3 с, нет застывшего кадра > 1 с |
| `safe` | `safe_zone` | текст, QR и ссылки в безопасной зоне платформы |
| `qr_decode` | `qr` | QR читается из готового ролика и ведёт на ссылку |
| `slop`, `glow`, `gradient` | `anti_slop` | нет свечения, градиентных плашек, лишних цветов, эмодзи |
| `lufs` | `loudness` | -14 LUFS, пик не выше -1 dBTP |
| `caption` | `captions` | субтитры в такт (150 мс), не режут слова, не вылезают |
| `duration` | `format` | 1080x1920, кодеки, fps, длина в цели |
| `flash`, `effects` | `vfx` | 1.3: не больше 3 вспышек в секунду (WCAG 2.3.1), полосы кино не закрывают хук, не больше 2 заметных приёмов |
| `originality`, `reused` | `author_layer` | 1.3: чужой материал с минимум 2 слоями автора (один ключевой), подпись фона в описании |

Остальные id: `contrast`, `loop`, `metadata`, `eyes`, `silent`, `distinct`, `text_rules`, `edit_content`, `beat_sync`, `edit_style` (1.2).
Та же таблица лежит в каждом `qa.json` в поле `aliases` (только id, которые есть в этом отчёте).

## Поля схемы 1.1 (все необязательные)

| Поле | Смысл |
|---|---|
| `scenes[].duration_hint` | минимум экранного времени, с. Длина сцены = max(речь + пауза, `duration`, `duration_hint`). Без `say` сцена длится `duration_hint` |
| `scenes[].avoid` | ловушки сайта. `"click"` или `"click:<текст>"` - движок пропускает такие действия (текст ищется в полях действия без учёта регистра) и пишет заметку в `manifest.scenes[].notes`. Свободный текст - только заметка |
| `layout.cta_in_center[].anchor` | `{"scene": "<id>", "offset": s}`: от начала сцены, при `offset < 0` от конца сцены |
| `layout.cta_in_center[].t_pct` | доля реальной длины ролика, 0-1 |
| `brand.register` | `minimal` (белый капс на чёрном, метки без плашки, первой рекомендуется обложка A) или `punch` (герой + плашка акцента, обложка B) |

У вспышки CTA нужно одно из: `t`, `anchor`, `t_pct`. Движок считает время после озвучки,
держит вспышку внутри ролика и раздвигает пересекающиеся (зазор 0.3 с, порядок сохраняется;
если места нет - укорачивает до 1.5 с, потом убирает самую неважную: текст, потом ник, QR последним).
Что получилось, лежит в `manifest.json` и `result.json` в `cta_schedule`
(`requested`, `final`, `duration`, `reason`), сдвиги видны предупреждением в QA `text_rules`.

Синонимы, которые движок тоже понимает (официальное поле важнее):
`scenes[].x_duration_hint` -> `duration_hint`, `scenes[].x_avoid` -> `avoid`, `x_viora.register` -> `brand.register`.
Остальные поля `x_*` движок не трогает.

## Поля схемы 1.3 (все необязательные)

Монтаж и подача: `layout.mode: band`, `layout.title_bar`, `layout.split`, `layout.top.fit`, `bg:` в `layout.top.source`,
CTA `subscribe`, `captions.style: kinetic`, `overlays.facts`/`arrow`, `fx.letterbox`/`flicker`/`look_keys`/`transitions`,
`scenes[].trans`, `audio.export`, `author_layer`. Смысл и примеры: `reference/vfx.md`.
С `schema_version` "1.3" чужой материал (сцены `film`/`video`, фон `bg:`) без 2 слоёв автора = ошибка `validate`
и `fail` QA `author_layer`; в старых версиях плана это предупреждение.

Что пишется в `manifest.json` (1.3):
- `vfx`: `letterbox` (`keys`, `kicks`, `closed`, `closed_at_start_s`), `flicker.series`, `look_keys`, `transitions`
  (`t`, `kind`, `dur`, `how`: `plan` или `auto`), `splits`, `clip_size`, `notable`, `notes` (заметки движка: что сдвинуто, уменьшено).
- `audio_export`: `export`, `files` (какие файлы лежат в `--out`).
- `author_layer`: `foreign`, `declared`, `detected`, `count`, `core` (ключевые слои: voice / thesis / own_footage / compare), `longest_foreign_only_s`, `credits`.
- `post`: карточки поста (`kind`, `t0`, `t1`, `scene`, `states`, `words`, `box`, `scrolled`, `captions_hidden`,
  `first_word_s`, `max_early_s` = насколько слово появилось раньше звука, всегда 0).
- `top.bg` (id, подпись, url) и `top.focus_report` для `bg:`: `how: window` = окно кадра выбрано по движению
  (`start`, `focus_y`, `change_min` = худшая секунда, `dark_void`).

## Время и пути

- `scenes[].speed[].t` - время ИСХОДНИКА от начала сцены (секунды записи сайта или таймлайна HTML),
  а не время готового ролика. С момента `t` исходник идёт со скоростью `rate`.
- `scenes[].sfx[].t` - время ролика от начала сцены.
- `layout.cta_in_center[].t` - время готового ролика.
- Относительные пути (`brand.fonts`, `layout.top.source`, `scenes[].source.ref`, `audio.music.source`, логотип)
  считаются от папки, где лежит `plan.json`, потом от папки скилла.

## Палитра VIORA

Один источник правды: `assets/brand/viora.json` движка (акцент `#E63946`). `tools/sync_engine.py`
у Viora копирует движок вместе с этим файлом; Viora берёт цвета оттуда, а не держит свои.
Тест `tests/unit/test_contract.py::test_viora_accent_single_source` сверяет с `viora-v8/spec/plan.example.json`.

Акцент `#E63946` с чёрным текстом даёт 5:1, а для меток нужно 7:1. Движок сам подбирает цвет плашки
того же оттенка (светлее под тёмный текст или темнее под светлый, что ближе к акценту), пишет это
в заметку сцены. Нужен точный цвет - поставьте `brand.label_style: "outline"`.

## Где лежит схема

`schema/plan.schema.json` движка. Копия в `viora-v8/spec/plan.schema.json` обновляется вместе с ней.
Переносить схему в другую папку только с записью в CHANGELOG.

## Расширение 1.4 / движок 1.5.0

Старые версии схемы и публичные команды render/qa/all остаются совместимыми.
video.format=long использует отдельный профиль, не геометрию 1080x1920. Размер
1280x720 или 1920x1080, нормальная скорость, локальные источники. Подробнее
reference/long-videos.md. В этом профиле слова и SRT могут быть пустыми, если
в исходнике нет предоставленного transcript и нет TTS; распознавание не выдумывается.
Новые ID QA: decode, audio_loudness, black_silence, metadata, covers, motion_audio.
Последний всегда manual до реального непрерывного просмотра/прослушивания,
review по кадрам его не закрывает. Passed/ok - технический статус, не творческий.
Для текущего запуска приёмка частична; дальнейшее подтверждение фиксировать
отдельным ручным актом, не подменять наличием файла review.md.
Контактный лист длинного ограничен выборкой до 32 кадров; полный decode проводится
отдельно. Наличие контактного листа не доказывает просмотр всех кадров глазами.
meta.pacing и meta.genre применяются только в 1.4. Ритм meaning - ручной пункт.
Старая внешняя копия схемы Viora в этом проекте не нужна; канон находится здесь.
