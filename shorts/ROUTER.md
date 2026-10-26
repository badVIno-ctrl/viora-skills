# ROUTER: что читать в какой задаче

| Задача | Читай | Команды |
|---|---|---|
| 2.4: озвучка любым голосом (пол, возраст 2-105, персонаж, эмоция, эффект, диалог на роли), офлайн | `reference/voice.md` | `voice`, `voice --list`, `voice --describe`, `voice-setup` |
| 2.4: видео кодом (HTML / canvas / p5.js / Three.js -> MP4 + голос + музыка), 4 приёма, claudevideo.org | `reference/code-video.md` | `code-new`, `beats --js --main`, `fx-get`, `render`, `qa` |
| 2.4: музыка не дана: найти на YouTube самому и поставить, автор в описании | `reference/audio.md` (Музыка) | `music-find`, `render` (`music: auto`) |
| 2.4: стиль человека одним файлом brand.md (цвета, шрифты, правила движения) | `reference/brand.md` | `brand-md template`, `brand-md import`, `brand-md show` |
| 2.4: эффект с GitHub или npm для HTML-сцены (p5.brush, thinking-orbs, любой с лицензией) | `assets/fx/README.md`, `reference/code-video.md` | `fx-get` |
| 2.3: какой формат выбрать (шортс, мультик, 3D, длинное, ИИ-персонаж) | `reference/formats.md` | - |
| 2.3: реклама внизу, спикер крупнее, размытый фон + резкая вставка, плашка раскрытия | `reference/stack.md` (2.3) | `stack` (`safe`, `top.h: auto`, `layout: center`, `label`) |
| 2.3: 2D-мультик кодом (выживание, зомби, блэкаут, детский, объяснялка, длинный 16:9) | `reference/toon.md` | `toon-new`, `toon-check`, `toon-preview`, `toon-render`, `toon-cast`, `toon-catalog --examples` |
| 2.3: 3D-мультик | `reference/3d.md` | `persona-new -t cartoon3d`, `persona-plan --engine ai`, `persona-cut` |
| 2.3: синтетический блогер (ИИ-персонаж), раскрытие ИИ, реклама у персонажа | `reference/persona.md` | `persona-new`, `persona-plan`, `persona-check`, `persona-build`, `persona-cut` |
| 2.3: длинный рисованный ролик, главы YouTube, концовка | `reference/long-videos.md`, `reference/toon.md` | `toon-new -t long` (`build/chapters.txt`) |
| Скачать исходник, музыку, кусок фильма самому | `reference/youtube-access.md` | `fetch`, `fetch --probe` |
| Собрать шортс: верх + главное видео + субтитры + карточка | `reference/stack.md` | `stack` |
| 2.2: реклама не на спикере (слот карточки), стыки и конец по границам речи | `reference/stack.md`, `reference/dialogue-editing.md` | `stack` (`banner.slot`, `main.snap`) |
| 2.2: красивые субтитры (стили clean / aesthetic, образцы E0BvqC3MY1E, VOuZxWAeXgs), хук-заголовок | `reference/captions.md` | `stack` (`captions.style`, `hook.style`) |
| 2.2: обложки для `pack` без шаблонного вида (A close, B context, C poster) | `reference/cover-packaging.md` | `pack` |
| 2.2: звук без синтеза (только реальные записи, музыка обязательна для эдита; 2.4: без `--music` найдётся сама) | `reference/audio.md`, `assets/audio/SOURCES.md` | `edit --music`, `qa` (`audio_honesty`) |
| Баннер-карточка (эталон: плавающая, QR, слайды) | `reference/ad-banner-standard.md` | `ad-card` |
| Выдать видео + названия + описание + обложку | `reference/handoff.md` | `pack` |
| Первый запуск, вопросы, память, напоминания | `reference/intake.md` | `prefs`, `intake` |
| Раскладка, панели, safe-зоны | `reference/layout.md` | `validate` |
| Свой стиль, пресеты, "сегодня строго ч/б" | `reference/brand.md` | - |
| Формат плана, действия на сайте, скорость, SFX | `reference/plan-format.md` | `plan`, `validate` |
| Ролик про сайты и сервисы | `reference/adapters.md#site` | `site-probe`, `render` |
| HTML-файл (игра, анимация, three.js, фильм) | `reference/adapters.md#html`, `reference/code-video.md` | `render` |
| Длинное видео -> шортсы | `reference/adapters.md#video`, `reference/edits-film.md` | `clips` |
| Эдит из фильма или роликов YouTube | `reference/edits-film.md` | `film-lines`, `edit --line`, `yt-search`, `beats` |
| YouTube не отдаёт видео ("not a bot"), запись из браузера | `reference/youtube-access.md` | - |
| Ролик из темы или текста | `reference/adapters.md#text` | `plan --source text` |
| Скриншоты в движении | `reference/adapters.md#images` | - |
| Субтитры по словам, словарь произношения | `reference/captions.md` | - |
| Монтаж: переходы по настроению, полосы кино, ч/б -> цвет на дропе, мерцание (1.3) | `reference/vfx.md` | `validate` |
| Баннер из геймплея сверху (GTA, Minecraft), сплит sludge, картинка в картинке, история Reddit поверх геймплея (1.3) | `reference/vfx.md`, `assets/footage/SOURCES.md` | `bg list`, `bg fetch`, `bg add` |
| Монолог "кинобаст": чёрные поля, плашка темы, кинетические субтитры (1.3) | `reference/vfx.md` | - |
| Плашки фактов, стрелка к ссылке, CTA "подписаться" (1.3) | `reference/vfx.md` | - |
| Чужой материал: авторский слой, подпись автора фона (1.3) | `reference/vfx.md` | - |
| Версия без музыки под трендовый звук (1.3) | `reference/vfx.md`, `reference/audio.md` | - |
| Голос, музыка, звуки, громкость | `reference/audio.md`, `reference/voice.md` | `beats`, `voice`, `music-find` |
| Реклама: баннер, шортс, ник, ссылка, QR | `reference/advertising.md`, `reference/ad-creative.md`, `reference/qr.md` | `ad-init`, `ad-check`, `ad-render`, `ad-seal`, `ad-links`, `ad-metrics`, `paid` |
| Названия, описание, закреп, TikTok | `reference/metadata.md` | `meta` |
| Обложка | `reference/cover.md` | `cover` |
| QA не прошёл, что значит пункт | `reference/qa.md` | `qa` |
| Старый ролик не набирает, ремонт | `reference/growth-loop.md`, `reference/wow-transformer.md` | выбор: пересборка / гипотеза; для гипотезы три ролика и замер |
| Плохое сырьё, новая концепция | `reference/wow-transformer.md`, `reference/plan-format.md` | `validate`, `review` |
| Новый бренд, новая ниша, придумай сам | `reference/intake.md`, `reference/niche-entry.md` | `prefs`, `intake` |
| Длинное готовое видео на 10 минут | `reference/long-videos.md` | schema 1.4, render / qa / all, реальный MP4 |
| Простой файл со всей упаковкой | `reference/user-package.md` | `package DIR` |
| После публикации: цифры, эксперимент | `reference/growth-loop.md` | - |
| Почему так устроено, источники | `docs/architecture.md`, `docs/research-log.md` | - |

Проект самодостаточен. Канон базы: `research/traffic-v3.1/00 ПРОЧТИ СНАЧАЛА.txt`;
имя папки сохранено для совместимости. Изменения v3.2: файл 30.
Тейки -> reference/plan-format.md и файл 26 р.13; каждый следующий ролик -> niche-entry.md.

## Приоритетные исправления v3.3

- Получение источников: `reference/source-recovery.md`.
- Живая реклама: `reference/live-banner.md`.
- Разговорный монтаж: `reference/dialogue-editing.md`.
- Музыкальный эдит: `reference/editorial-edit.md`.
- Публикация: `reference/publication-clean.md`, `release-check DIR`.
- При противоречии старых эвристик и этих правил применять v3.3; миграция: `docs/migration-1.6.md`.

## Рекламный маршрут v3.4 (приоритет над старой базой)

| Задача | Обязательно читать | Инструменты |
|---|---|---|
| Доделать скилл, встроить PDF, научить будущий ИИ | advertising.md, docs/advertising-source-map.md | код/тесты/архив; НЕ рекламный бриф |
| Рекламный баннер / самостоятельный рекламный шортс | advertising.md, ad-creative.md | ad-init, ad-render (статика), validate/render/qa (видео) |
| Реклама или геймплейная полоса? | advertising.md раздел 2 | сначала определить смысл |
| Партнёрка, оффер, монетизация, выбор воронки | ad-offers-traffic.md | campaign.json |
| Переходы, SubID, деньги, эксперимент | ad-analytics.md | experiment.md, ad-links, ad-metrics |
| Можно ли запускать рекламу? | ad-qa.md | ad-check --stage launch + release-check для видео (автодетект рекламы) |

Все имена .md в этой таблице - в reference/, кроме явно указанного docs/.


## v3.6
- Выдача человеку: reference/delivery.md (`deliver`).
- Баннер/плашка/оверлей: reference/ad-banner-standard.md (`ad-overlay`, `ad-render`).
- Запрос «сделай N шортсов»: SKILL.md#старт-без-простоя-v36.

## v2.0
- Что взято из других скиллов и почему: `docs/research-log.md` (раздел 2.0), `docs/ideas-2.0-backlog.md`.
- Три названия-тона, три описания, три обложки: `reference/handoff.md`, `reference/metadata.md`, `reference/cover.md`, `reference/cover-packaging.md`.
- Анимированные ролики про выживание: `reference/animation.md`, `docs/studio-setup.md`, команды `anim-pick`, `anim-init`, `anim-check`.
- Как люди делают эдиты (CapCut, маркеры, кривые скорости): `reference/edits-film.md#как-делают-эдит-люди-разбор-двух-туториалов-capcut-20`.
- Бренд для баннеров (Telegram, чем занимаетесь): `reference/intake.md`, `prefs`, `intake`.
