# Демо SHORTS

## 2.3.0 (2026-10-25): мультики кодом, ИИ-персонаж, новая раскладка рекламы
Видео в архив не кладём. Для каждого: `sheet.jpg` (кадр на сцену), `cover.jpg` (уменьшена вдвое), `timing.md` (сцены по
словам голоса), `report.json` (проверки toon), `result.json` (итог рендера). Песочница: 2 ядра, голос edge-tts.

| Демо | Что | Длина | mp4 1080x1920 | Рендер | Предупреждений |
|---|---|---|---|---|---|
| `e-toon-blackout` | 2D-история выживания (шаблон `blackout`, 27 сцен, схемы дома / воды / подъезда) | 81 с | 54 МБ, -14 LUFS | 195 с | 0 |
| `f-toon-kids` | детский мультик про радугу (шаблон `kids`, квиз, призма) | 55 с | 18 МБ, -14 LUFS | 97 с | 0 |
| `g-persona-valya` | ИИ-персонаж «Баба Валя» (`persona-new -t garden`), выпуск tip «Почему рассада вытягивается»: `persona.json`, `plan.json`, `episode.json`, `meta.txt`, `strip.jpg` (кадры готового mp4) | 31 с | 43 МБ, -14 LUFS | 95 с | 0 |
| `h-ad-layout` | раскладка рекламы: было / стало / центр с размытым фоном / круг (`README.md` с числами) | - | - | - | - |

Пересборка (из папки скилла):
```bash
python3 tools/shorts.py toon-new out/blackout -t blackout && python3 tools/shorts.py toon-render out/blackout
python3 tools/shorts.py toon-new out/kids -t kids && python3 tools/shorts.py toon-render out/kids
python3 tools/shorts.py persona-new out/valya -t garden
python3 tools/shorts.py persona-plan out/valya "Почему рассада вытягивается" -f tip
cp demos/g-persona-valya/plan.json out/valya/episodes/01-pochemu-rassada-vytyagivaetsya/plan.json
python3 tools/shorts.py persona-build out/valya/episodes/01-pochemu-rassada-vytyagivaetsya
python3 tools/shorts.py toon-render out/valya/episodes/01-pochemu-rassada-vytyagivaetsya
```
Что видно глазами: blackout - хук-вопрос, разрезы дома и подъезда, счётчики воды, тёмные сцены читаются; kids - мягкие
цвета, крупные лица, квиз с ответом; Валя - хук одной фразой, смена крупности на каждой фразе, перебивка с горшком
«12-16 часов света», плашка «ИИ-персонаж» в углу. Недочёт: числа в субтитрах словами (как произносит голос).

# Демо SHORTS 1.1.0 (пересобраны с нуля 2026-10-12)

Видео в git не кладём. Здесь для каждого демо: `qa.json` / `qa.md`, `review.md` (что агент увидел глазами),
`metadata.md`, `captions.srt`, `words.json`, `result.json`, контактный лист `contact-*.jpg` (2 кадра/с),
`first-frame.jpg`, обложки `cover/` (3 идеи x 2 формата, уменьшены вдвое) и `cover/cover.json`, manifest и план.

Сборка в песочнице: 2 ядра, без ключей картинок (`SHORTS_IMAGE_PROVIDER=none`). edge-tts в этот день отвечал 403,
поэтому голос - Piper (локально), тайминги слов - faster-whisper.

| Демо | Источник | Раскладка | Язык / платформы | Длина | Размер mp4 | QA (strict) |
|---|---|---|---|---|---|---|
| `a-sites-ru` | learn-anything.xyz + cadlookup.com (`site`, живые сайты) | `three`, сверху `loop:auto` (code) | ru / Shorts + TikTok | 24.6 с | 18.8 МБ | PASSED, 1 warn (QR с t=99 прижат к концу) |
| `b-html-en` | локальный HTML (`orbit.html`), замедление и ускорение, кинетический текст | `top_center`, `loop:spin` | en / Shorts + TikTok + Reels | 14.7 с | 5.4 МБ | PASSED, 1 warn (то же про QR) |
| `c-film-edit` | Big Buck Bunny (CC-BY 3.0), эдит 20 с под бит, только 195-428 с фильма | `center_only` | en / Shorts | 20.3 с | 13.7 МБ | PASSED, 0 warn; `edit_content` 19/19 разных планов, без титров; `beat_sync` 89% |
| `d-long-video-clip` | тот же фильм как длинное видео: окно 251-281 с (`clips`), закадр + субтитры | `center_bottom` | en / Shorts + TikTok | 30.0 с | 16.6 МБ | PASSED, 0 warn |

Пересборка (из папки скилла; фильм: `examples/media/README.md`):
```bash
python3 tools/shorts.py all schema/plan.example.json --out out/demo-a          # сеть: сайты (+ edge-tts, если отвечает)
python3 tools/shorts.py all examples/b-html-film.plan.json --out out/demo-b
python3 tools/shorts.py edit --video examples/media/film.mp4 --length 20 --title "BIG BUCK BUNNY" --lang en \
  --handle VioraStudio --link https://t.me/VioraStudio --brand viora -o c.plan.json   # = examples/c-film-edit.plan.json
python3 tools/shorts.py all examples/c-film-edit.plan.json --out out/demo-c
python3 tools/shorts.py clips --video examples/media/film.mp4 -n 2 --length 30 --lang en -o out/d-clips
python3 tools/shorts.py all examples/d-long-video-clip.plan.json --out out/demo-d    # clip-1 + закадр, CTA через anchor/t_pct
```

## Что видно глазами (полностью - `*/review.md`)
- **a:** сверху живой дождь кода; метка на розовой плашке (акцент #E63946 поднят до 7:1). Ввод "Linux", список
  дистрибутивов; CAD Lookup: запрос и сетка шестерёнок. Недочёт: ник на 14-16 с закрывает заголовок сайта.
- **b:** сверху крутятся кубы, в центре орбиты. Недочёт: на 9 с плашка ника обрезает кинетическое слово "code";
  моноширинные субтитры мелковаты. Обложка A 9:16 с тонким моноширинным шрифтом не прошла "прищур" (предупреждение).
- **c:** 19 разных планов, титров и чёрного нет, петля сходится. Недочёт: близкие моменты одной сцены повторяются
  (белка на 5.5 и 14 с).
- **d:** месть кролика: ловушки, копья. Недочёт: метка висит всю первую сцену (10 с), 14-19 с почти статичный план.

## Что НЕ проверено
- YouTube как источник: с IP песочницы просит вход, эдит по ссылке не перемерен (фильм взят файлом с archive.org).
- Генерация картинок (ключей нет): обложки B и C из кадров, промпт в `cover/prompt.md`.
- ElevenLabs и OpenAI TTS: ключей нет, `doctor` пишет "не проверено". edge-tts в день сборки отвечал 403.