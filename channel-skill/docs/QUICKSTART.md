# Быстрый старт

Цель: первый готовый пост за три минуты. Без платных ключей и без настроек Телеграма.

## Шаг 1. Забрать скилл

```bash
git clone https://github.com/OWNER/channel-skill.git
cd channel-skill
python3 --version   # нужна 3.8 или выше
```

Если скачал архивом, распакуй и зайди в папку с файлом `README.md`.

## Шаг 2. Пройти интервью

```bash
cd channel-skill
python3 tools/onboard.py
```

Пять коротких блоков вопросов: кто ты, о чём и для кого, куда выходит и какие ссылки,
ритм и масштаб, рубрики и публикация. Обязательных ответов всего пять:
имя канала, ник автора, темы, аудитория, тон. Остальное можно пропустить и добавить потом.

Агенту удобнее спросить в чате:

```bash
python3 tools/onboard.py --questions        # отдаёт вопросы в JSON
python3 tools/onboard.py --stdin < ans.json # принимает ответы одним JSON
```

Самый быстрый путь: взять готовый шаблон из папки profiles и поменять поля руками:

```bash
cp profile/profiles/ru-tech-telegram.json profile/profile.json
python3 tools/onboard.py --render
```

## Шаг 3. Проверить профиль

```bash
python3 tools/profile.py --check   # должно быть: Профиль на месте
python3 tools/profile.py --show    # посмотреть карточку канала
python3 tools/profile.py --footer  # увидеть свой футер знак в знак
```

Если видишь предупреждение про демо-профиль, значит интервью не пройдено и скилл работает
на демо-данных DEMO STUDIO. В таком виде посты в свой канал ставить нельзя.

## Шаг 4. Попросить пост

Скажи агенту обычными словами:

```
Сделай пост про новый инструмент для монтажа, рубрика гайд
```

Агент сам поймёт рубрику и каркас. Если сомневается, пусть спросит маршрутизатор:

```bash
python3 tools/channel.py route "нужен пост про новый инструмент"
```

## Шаг 5. Проверить черновик

```bash
python3 tools/channel.py ship draft.txt --rubric гайд
```

Одна команда делает четыре вещи: механическая автоправка, линтер поста, оценка по
цифрам твоего канала и проверка разреза. По отдельности:

```bash
python3 tools/lint_post.py draft.txt --strict
python3 tools/score_post.py draft.txt --rubric гайд
python3 tools/split_post.py draft.txt --check
```

## Шаг 6. Публикация

Публикует автор. Скилл отдаёт текст и говорит, что исправить. Если хочешь доставлять
задачи и черновики через своё Избранное в Телеграме, собери мост: [TELEGRAM.md](TELEGRAM.md).

## Если что-то не так

| Симптом | Что делать |
| --- | --- |
| Агент пишет чужим голосом | `python3 tools/profile.py --check`, проверь brand.tone и brand.audience |
| В тексте длинные тире | `python3 tools/lint_chat.py --text "строка"` и правило ноль в `SKILL.md` |
| Футер не тот | `python3 tools/profile.py --footer`, потом `python3 tools/onboard.py --render` |
| Сломался один из скриптов | `bash tools/check_all.sh` и читать первую красную строку |
| Надо начать с нуля | `python3 tools/onboard.py --force` |

Дальше: [PROFILE.md](PROFILE.md) про все поля, [CUSTOMIZE.md](CUSTOMIZE.md) про свои рубрики,
[ARCHITECTURE.md](ARCHITECTURE.md) про устройство.
