# Учебный видео-пример (рекламный шортс, v3.5)

Синтетический ролик «Редактор-пример»: 13,17 с, 1080x1920, H.264/AAC, 30 fps, петля.
Не реальный продукт, не оффер, нет записи настоящего интерфейса, QR ведёт на
`example.invalid`. Не публиковать.

## Файлы
- `plan.json` и `diff-demo.html`: план и собственная HTML-анимация (три сцены).
  Поля нижней панели (name, message, action, qr_url) лежат в `layout.bottom`,
  а не внутри `layout.bottom.animation` (иначе панель покажет текст по умолчанию;
  линтер плана даёт ошибку `banner_fields`).
- `ad-video-training.mp4`: готовый файл. Запечатан `ad-seal` (sha256 в campaign.json).
- `render-qa.md`: QA рендера. Итог: PASSED, 0 fail, 2 warn, 2 manual.
  Warn: 22% субтитров из одного слова (цель до 20%); нет metadata.json.
- `contact-sheet.png`: контакт-лист. Просмотрен визуально: перекрытий нет, панель и QR на месте.
- `captions.srt`, `campaign.json` (advertising-2; draft valid, launch отказывает).

## Измерено
Громкость −14,0 LUFS, пик −2,2 dBFS. Нижняя панель y=1424..1808.

## Не подтверждено
- Звук не слушал человек; просмотр не на телефоне и не в интерфейсе площадки.
- Два пункта EYES из QA (визуальный обзор, пересказ без звука) отмечены как ручные.
- Реальный оффер, права, ссылка, раскрытие и измерение отсутствуют.

## Как повторить
    python3 tools/shorts.py ad-check examples/advertising/video-training --stage draft
    python3 tools/shorts.py render examples/advertising/video-training/plan.json --out OUT_DIR   # нужны ffmpeg и Chromium
