# beautiful-ui

One design skill for coding agents. Replaces six.

Built for Claude Code, Codex, Antigravity, Cursor, Gemini CLI, Windsurf, Cline, OpenCode and anything else that reads a `SKILL.md`. Designed so that a mid-tier 2025 model produces work that looks decided rather than generated.

---

# Русская версия

## Что это

Один скилл вместо шести. Внутри - маршрутизатор на восемь шагов (G0-G7), двенадцать справочных файлов, которые загружаются **по одному, только когда нужны**, и два скрипта проверки без зависимостей. Модель никогда не держит в контексте больше двух справочников одновременно.

## Установка

Положите папку `beautiful-ui` в каталог скиллов вашего инструмента:

| Инструмент | Куда положить |
|---|---|
| Claude Code (проект) | `.claude/skills/beautiful-ui/` |
| Claude Code (глобально) | `~/.claude/skills/beautiful-ui/` |
| Codex | `.codex/skills/beautiful-ui/` |
| Antigravity / Gemini CLI | `.gemini/skills/beautiful-ui/` |
| Cursor | `.cursor/skills/beautiful-ui/` |
| OpenCode | `.opencode/skills/beautiful-ui/` |
| GitHub Copilot | `.github/skills/beautiful-ui/` |

Важно: копируйте **всю папку целиком**, вместе с `reference/`, `assets/` и `scripts/`. Один `SKILL.md` без них работать не будет.

Если ваш инструмент не поддерживает скиллы, добавьте одну строку в `AGENTS.md`, `CLAUDE.md` или `.cursor/rules`:

```md
Любая работа с интерфейсом: сначала прочитай .claude/skills/beautiful-ui/SKILL.md и следуй ему.
```

## Как пользоваться

Ничего специального делать не нужно. Скилл подхватывается сам, когда вы просите что-то нарисовать, сверстать, отредизайнить или починить. Просто пишите задачу:

```
Сделай лендинг для сервиса аналитики. Аудитория - технические руководители.
```

```
Переделай дашборд. Сейчас выглядит как шаблон.
```

```
Пройдись по /app/settings и доведи до нормального качества.
```

Что даёт лучший результат:

1. **Скажите, для кого это.** "для технических руководителей" меняет результат сильнее, чем "сделай красиво".
2. **Закрепите то, что нельзя менять.** Бренд, цвет, шрифт, референс. Закреплённое всегда побеждает дефолты скилла.
3. **Дайте настоящий текст и настоящие картинки,** если они есть. Тонкий контент - главный признак сгенерированного интерфейса, его не спасает никакая вёрстка.
4. **Не просите "добавить анимаций".** Скилл сам решит, где движение уместно. Просьба "побольше анимации" ухудшает результат.

## Что появится в проекте

- `tokens.css` - токены: цвет, типографика, отступы, радиусы, тени, кривые анимации, плюс то, что почти никто не настраивает: цвет выделения текста, каретка, скроллбар, фокус-ринг, табличные цифры, `prefers-reduced-motion`, печать.
- `DESIGN.md` - контракт дизайна проекта. Это память: следующая сессия не придумывает стиль заново, а читает его. Именно за счёт этого файла экономится контекст на слабых моделях.

В самом скилле есть два файла, которые нужно копировать, а не читать:

- `assets/starter.html` - однофайловая заготовка, которая уже проходит все проверки: токены на светлую и тёмную темы, skip-link, sticky-навигация, hero, hairline-таблица с табулярными цифрами, форма с настоящими label, одно подписное движение и полный блок `prefers-reduced-motion`. Начинать с неё быстрее, чем с пустого файла.
- `assets/snippets.md` - десять базовых компонентов (кнопка, поле, карточка, таблица, модалка, пустое состояние, скелетон, тост, иконки, утилиты) со всеми состояниями и фокус-рингом на месте.

## Проверка качества

В скилле есть линтер без зависимостей. Модель запускает его сама на шаге проверки, но вы можете и вручную:

```bash
node .claude/skills/beautiful-ui/scripts/check.mjs .
node .claude/skills/beautiful-ui/scripts/check.mjs . --summary
node .claude/skills/beautiful-ui/scripts/check.mjs --list-rules
node .claude/skills/beautiful-ui/scripts/contrast.mjs tokens.css
```

Правил 51. Он ловит то, что проверяется механически: длинное тире, `transition: all`, `100vh`, снятый фокус, `Lorem`, `Acme`, `John Doe`, градиентный текст, надзаголовки-кикеры, отсутствие `prefers-reduced-motion`, `<img>` без `alt`, запрет зума, положительный `tabindex`, шрифты-дефолты, латинский шрифт под кириллицей, больше трёх цветовых тонов, два семейства радиусов, анимация лейаута, иконка-кнопка без имени, placeholder вместо label, два `h1`, пропущенный уровень заголовка.

Формат вывода не зашит в скилл, он выбирается на G0 из трёх вариантов по одному признаку: где будет жить код. `FILE` один самодостаточный HTML, `PARTS` компоненты в существующий проект, `APP` проект с роутами и данными. Если признаков нет, берётся файл, который просто открывается.

Язык интерфейса всегда равен языку запроса, и это проверяется машинно, а не просится в инструкции. Документ без `lang` и документ, который объявляет английский при кириллическом тексте, падают с ошибкой. К ним примыкает старое правило про кириллицу под латинским начертанием: вместе они закрывают самый частый способ убить русский макет.

Второй скрипт, `contrast.mjs`, делает то, что поиском по тексту не проверить: раскрывает `var()`, `color-mix()`, `oklch()` и `hsl()` в светлой и тёмной темах и измеряет все пары контраста по WCAG. Не «вроде читаемо», а цифра.

`0 errors` и `0 failures` - механический минимум пройден. Дальше скилл делает один прогон скриншотов (десктоп, мобайл, размытый силуэт и иконка), прогон по десяти эвристикам и проход на вычитание, и правит всё найденное одной пачкой.

Если какое-то правило в вашем случае неприменимо, это не подавляется молча:

```css
/* bui-allow: neon-glow неоновая обводка здесь часть заданного стиля */
```

Скриншоты:

```bash
node .claude/skills/beautiful-ui/scripts/shot.mjs http://localhost:3000
node .claude/skills/beautiful-ui/scripts/shot.mjs http://localhost:3000 --squint   # размытый чёрно-белый силуэт
node .claude/skills/beautiful-ui/scripts/shot.mjs http://localhost:3000 --icon     # 0.2x, читается ли вообще
```

## Почему это работает на слабых моделях

- **Всегда в контексте только `SKILL.md`.** Остальное - по одному файлу на шаг.
- **Меню вместо изобретения.** 14 визуальных миров, 13 готовых палитр с точными hex, 10 шрифтовых пар с отметкой про кириллицу, 12 семейств секций. Выбрать из списка слабая модель умеет намного лучше, чем придумать с нуля.
- **Скрипт вместо самопроверки.** Модель не умеет честно ревьюить свой код. Линтер умеет.
- **`DESIGN.md` как память.** Один раз решили - дальше только читаем.
- **Жёсткое правило остановки.** Один прогон правок, одно подтверждение, стоп. Без бесконечной полировки.

---

# English

## Install

Drop the whole `beautiful-ui` folder into your tool's skills directory:

| Tool | Path |
|---|---|
| Claude Code (project) | `.claude/skills/beautiful-ui/` |
| Claude Code (global) | `~/.claude/skills/beautiful-ui/` |
| Codex | `.codex/skills/beautiful-ui/` |
| Antigravity / Gemini CLI | `.gemini/skills/beautiful-ui/` |
| Cursor | `.cursor/skills/beautiful-ui/` |
| OpenCode | `.opencode/skills/beautiful-ui/` |
| GitHub Copilot | `.github/skills/beautiful-ui/` |

Copy the **entire folder**, including `reference/`, `assets/` and `scripts/`. `SKILL.md` alone will not work.

For tools without skill support, add one line to `AGENTS.md`, `CLAUDE.md` or `.cursor/rules`:

```md
For any UI work, read .claude/skills/beautiful-ui/SKILL.md first and follow it.
```

## Architecture

```
SKILL.md            always loaded. Router, ten laws, eight gates. Nothing else.
reference/01..12    one concern per file, loaded one at a time, on demand
assets/tokens.css   drop-in token contract and craft floor
assets/starter.html  a page that already passes every check, ready to edit
assets/snippets.md   ten components with every state written out
assets/DESIGN.md    project memory template
scripts/check.mjs   mechanical linter, zero dependencies
scripts/shot.mjs    screenshots: desktop, mobile, --squint, --icon
scripts/contrast.mjs  WCAG resolver: var(), color-mix(), oklch(), both themes
```

The eight gates, `G0` to `G7`: **route, read, direct, frame, build, detail, verify, report.** Each gate names exactly one file to load and one thing to produce, and prints a one-line marker. A model that drifts is visibly off-script.

G0 also picks the **stack**, so the output format is a decision with criteria instead of a habit: `FILE` for one self-contained page, `PARTS` for components inside an existing repo, `APP` only when routes and real data are asked for. The interface language follows the language of the request, and two rules enforce it: `html-lang-missing` and `lang-copy-mismatch`.

## Context budget

| Loaded | When |
|---|---|
| `SKILL.md` (198 lines) | always |
| one reference file | per gate, then released |
| never | the whole `reference/` folder |
| skipped entirely | `01-direction.md`, once `DESIGN.md` exists |

Maximum two reference files in context at once. That ceiling is what makes it usable on weaker models.

## What it produces

- A committed visual direction, named, chosen from 14 worlds instead of invented.
- One token file: 13 ready palettes with exact hex for light and dark, a control-border role that actually clears 3:1, a type scale with matched tracking, a 4px space rhythm, one radius family, a four-step tinted shadow scale, tokenised easings and durations.
- The browser surfaces almost nobody sets: selection, caret, scrollbar, focus ring, underline offset, tabular numerals, autofill, reduced motion, reduced transparency, print.
- Complete states: hover, focus-visible, active, disabled, loading, empty, error, offline, first run.
- Accessibility by construction, measured rather than claimed: 4.5:1 body contrast and 3:1 control borders checked by `contrast.mjs`, 44px targets, full keyboard operation, visible focus, 200% zoom, 320px width.
- One or two authored motion moments, never motion everywhere.
- `DESIGN.md`, so the next session inherits the decision instead of re-deriving it.

## Checker

```bash
node scripts/check.mjs .                 # scan the project
node scripts/check.mjs . --summary       # counts only
node scripts/check.mjs . --json          # machine readable
node scripts/check.mjs --list-rules      # every rule and its message
node scripts/check.mjs . --ignore-rule banned-font,raw-hex
node scripts/contrast.mjs tokens.css     # every contrast pair, both themes
node scripts/contrast.mjs tokens.css --pair ink:accent
```

Exit code 1 means errors remain. Suppress a rule where it genuinely does not apply, with a reason:

```css
/* bui-allow: neon-glow the brief pins a neon aesthetic */
```

## What it merges

Six skills went in. Each contributed the thing it did best:

| Source | What it contributed | Now lives in |
|---|---|---|
| Direction and craft-floor skill | direction commitment, the craft floor, the refusal list, bounded verification | `SKILL.md`, `01-direction.md`, `02-tokens.md`, `10-review.md` |
| Taste skill | counted layout ceilings, the spent-hex list, section families, Core Web Vitals targets | `03-layout.md`, `05-color.md`, `08-states-a11y.md` |
| Impeccable | the gate structure itself, the distil and delight passes, the subtraction rule | `SKILL.md`, `10-review.md` |
| UI/UX pro max | ten-heuristic scoring, severity levels, persona walkthroughs, touch and icon minimums | `10-review.md`, `07-components.md`, `08-states-a11y.md` |
| Animation and library skills | the animation decision framework, easing and duration doctrine, library routing | `06-motion.md`, `07-components.md` |
| awesome-design-md | the `DESIGN.md` schema and its frontmatter convention | `12-design-md.md`, `assets/DESIGN.template.md` |

What was dropped: duplicate advice, prose that read well but changed no decision, unverifiable claims, and anything requiring a Python runtime, a CSV data bundle, or a network fetch at build time. What was added on top of all six: two verification scripts, a working starter page, a component library with real states, and a mechanical mapping from each of the ten design laws to the gate that enforces it.

## License

MIT.
