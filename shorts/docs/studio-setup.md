# Установка студии для анимированных роликов (необязательно)

Нужна только если человек хочет полный путь «как в мануале»: Blender 3D, Remotion, свои SVG-риги. Режим `reference/animation.md` работает и без неё, на ffmpeg-движке 2.0.
Источник: «Промпт 1: установка студии» из «Полевого мануала» (KYLO AI). Версии и команды ниже взяты оттуда; что-то могло устареть, перед установкой сверяй с официальной инструкцией каждого инструмента.
Агент **сам ничего не ставит без «да» человека**: показывает список, что уже стоит (`python3 tools/shorts.py doctor`), и что предлагает добавить. Пароль администратора агенту не давать: он пишет команду, человек вводит её сам.

## Что нужно на компьютере
macOS или Windows (в мануале только они; на Linux те же программы ставятся своим менеджером пакетов, это уже не из мануала), 15-20 ГБ свободного места, вечер на первую установку. Микрофон по желанию: без него голос делает ИИ.

## Папка проекта

Создаётся в текущей папке:

```
survival-studio/
  channel/     стиль канала, герой, собака (общие для всех роликов)
  episodes/    по папке на ролик (python3 tools/shorts.py anim-init NAME --root survival-studio)
  assets_3d/   бесплатные 3D-ассеты
  fonts/       шрифты
  music/       музыка человека (с лицензией)
  tools/       скрипты и голоса (tools/voices/)
  lists.md     50 катастроф и 50 мест: взять из reference/animation-lists.md
```
Дальше пункты ставятся по порядку. Каждый можно пропустить: тогда соответствующая функция заменена (см. таблицу в `reference/animation.md`).

## Инструменты и версии

| # | Инструмент | Версия | Команды из мануала | Нужен для |
|---|---|---|---|---|
| 1 | Менеджер пакетов | Mac: Homebrew (brew.sh); Windows: winget | определить систему | остальных шагов |
| 2 | git, Node.js, Python, ffmpeg | Node 20+, Python 3.11+ | проверить версии | основа; ffmpeg и Python уже нужны движку 2.0 |
| 3 | uv | текущая | Mac `brew install uv`; Windows `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` (в таблице черта экранирована, в терминале пиши без обратной косой), затем `%USERPROFILE%\.local\bin` в PATH | Blender MCP |
| 4 | Blender | 4.x | Mac `brew install --cask blender`; Windows `winget install BlenderFoundation.Blender`; проверка `blender --version` (Mac: `/Applications/Blender.app/Contents/MacOS/Blender`) | 3D, до 25% ролика |
| 5 | Blender MCP | текущая | `uvx blender-mcp install-addon`; `blender --background --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='blender_mcp'); bpy.ops.wm.save_userpref()"`; подключение к агенту: в мануале `claude mcp add blender uvx blender-mcp` (для другого агента команда своя) | управление Blender из чата |
| 6 | Remotion | текущая, лицензия: в мануале «бесплатно для частных лиц и команд до 3 человек» (проверь условия на remotion.dev) | в `survival-studio/`: `npx create-video@latest` (шаблон Blank, TypeScript) в папку `video/`, затем `npm install`; навыки: `npx skills add remotion-dev/skills` | сборка кадров кодом, караоке |
| 7 | svg-creator-skill | репозиторий `upbrew-tech/svg-creator-skill` | `git clone` во временную папку, копия в `.claude/skills/svg-creator` проекта (проверь лицензию и содержимое репозитория перед копированием) | 2D-иллюстрации |
| 8 | Python-окружение `survival-studio/.venv` | Python 3.11+ | `pip install faster-whisper deepfilternet`; на Mac с Apple Silicon дополнительно `pip install mlx-whisper` | слова с таймкодами, шумоподавление |
| 9 | Piper и русский голос | например `ru_RU-denis-medium` | `pip install piper-tts`, скачать голос в `tools/voices/` | озвучка без микрофона (вариант C) |
| 10 | Шрифты с кириллицей | официальные источники (Google Fonts, GitHub rsms/inter, JetBrains) | положить в `fonts/`: Inter Display (Black, ExtraBold), Montserrat (ExtraBold, Black), Oswald (Bold), JetBrains Mono (Regular, Bold), Caveat (Bold) | субтитры, плашки, обложка |
| 11 | 3D-ассеты CC0 | Quaternius, Kenney | в `assets_3d/`: Quaternius: Farm Animal Pack, Animated Animals, Ultimate Nature; Kenney: Nature Kit, City Kit | 3D-сцены |
| 12 | `INSTALL.md` | | записать, что поставлено, какие версии и команды | чтобы следующая сессия не гадала |

## Что делает человек сам (агент зовёт его в этих случаях)

- **Пароль администратора.** Агент пишет команду, человек вводит её сам. Пароль не передаётся агенту.
- **Скачать руками в браузере.** Сайты с 3D-моделями иногда просят нажать кнопку. Защиту не обходим: агент даёт ссылки, человек скачивает.
- **Перезапустить агента**, чтобы появился Blender MCP («перезапусти меня и напиши "продолжай"»).
- **Включить связь в Blender один раз.** Открыть Blender, `N` -> вкладка `MCP for Blender` -> `Start MCP Server` (в некоторых версиях кнопка называется `Connect to Claude`). Blender оставить открытым, пока идёт работа.

## Финальная проверка: три пункта, результат каждого показать

1. Через Blender MCP создать куб на плоскости и отрендерить кадр 1280x720 в PNG.
2. В Remotion отрендерить 3-секундный ролик: белый текст «РАБОТАЕТ» шрифтом Inter Display Black на тёмном фоне; проверить, что кириллица на месте (не квадраты и не подмена шрифта).
3. Распознать 5 секунд любого аудио через faster-whisper с таймкодами слов.

Если что-то не прошло: починить и повторить. Когда всё зелёное, сказать «Студия готова». Пункты 1 и 2 нужны только если соответствующие инструменты ставились.

## Минимальная студия без тяжёлого

Достаточно: `python3 tools/shorts.py doctor` (ffmpeg, Playwright, faster-whisper, TTS), папка `survival-studio/episodes/` через `anim-init`, свои шрифты в `fonts/`, музыка в `music/`. Blender и Remotion можно подключить позже: этапы 4-7 не меняются, меняется только то, чем делаются кадры.
