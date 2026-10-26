# Миграция 1.7.0 / traffic v3.5

## Что станет строже
- **launch** требует reviewer (человек, не совпадает с author, роль, дата, заявление),
  не менее 2 variants, раскрытие рекламы (disclosure), свежие доказательства оффера, прав и
  правил (`evidence_max_age_days`, по умолчанию 30 дней). Для атрибуции уровня creative нужен метод.
- На YouTube Shorts ссылка в описании или комментарии некликабельна: если `route.link_point`
  указывает на них без кликабельного места, launch блокируется.
- Платные API (TTS, обложки) работают только при `SHORTS_ALLOW_PAID=1` и `SHORTS_PAID_BUDGET>0`;
  расходы пишутся в paid-ledger.json (оценка, не биллинг). Проверка: `shorts.py paid status`.
- `release-check` сам находит признаки рекламы (промокод, партнёрская, #ad, utm и т.п) и
  блокирует выпуск без campaign.json либо без `advertising=false` с `advertising_reason`.
- `plan.py lint`: ошибка `banner_fields`, если name/message/action/qr_url лежат внутри
  `layout.bottom.animation`, а не в `layout.bottom`.

## Совместимость
- Схема `advertising-2` (author, reviewer, disclosure, variants, evidence_max_age_days, creative,
  claims[].covers). `advertising-1` принимается (draft), но launch потребует новые поля.
- Чтобы старый launch-пример снова проходил структуру, добавьте reviewer, variants, disclosure,
  свежие даты. Это ожидаемое ужесточение, а не регрессия.

## Изменения существующих тестов (честно)
- `test_advertising_v34.py`: фикстура complete() получила author, reviewer, variants и свежую
  дату вместо 2020-01-01; кейс attribution=creative получил метод; платный mock-тест задаёт бюджет.
  Это следствие нового требования, проверки не ослаблены.
- `test_meta.py::test_english_template`: прежнее ожидание фразы «Full video on the channel.»
  без URL противоречило политике запрета выдуманного полного видео (v3.3). Ожидание исправлено,
  добавлен тест, что обещание допустимо только с реальным `full_video_url`.

## Новые команды
`ad-render`, `ad-seal`, `ad-links`, `ad-metrics`, `paid status|reset`, `ad-check --today`.
EPC: в инструкции это доход за 1 клик, в Admitad за 100 кликов; `ad-metrics` выводит оба значения.
