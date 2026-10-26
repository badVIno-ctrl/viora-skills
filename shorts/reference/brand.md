# Стиль бренда

## Как получить стиль (вопрос 6 при первом запуске)
1. **Файлы** (логотип, цвета, шрифты, примеры): сделай `brand.json` рядом с планом:
   ```json
   {"name": "my", "base": "mono", "palette": {"bg": "#000000", "fg": "#FFFFFF", "accent": "#FF3B30"},
    "fonts": {"display": "fonts/MyDisplay.ttf", "body": "fonts/MyBody.ttf", "logo": "fonts/MyLogo.ttf"},
    "logo_text": "MY", "logo_sub": "STUDIO", "upper": true, "label_style": "plate", "line_width": 4, "radius": 0,
    "emotion_default": "trust", "tone": "calm"}
   ```
   В плане: `"brand": {"preset": "brand.json"}`. Шрифты только с лицензией на встраивание и кириллицей
   (движок проверяет кириллицу и падает с понятной ошибкой).
2. **Ссылка** на канал/сайт/Телеграм: открой (`site-probe`), выпиши 2-3 цвета (фон, текст, один акцент),
   характер шрифта, покажи пользователю токены на согласование, потом сохрани как в п.1.
3. **Пресет**: `mono` (ч/б), `editorial` (бумага, засечки, красный), `terminal` (моно-шрифт, плоский зелёный,
   без неона), `punch` (чёрный, узкий капс, жёлтый), `viora` (чёрный воздух, белый капс, оранжево-красный акцент,
   тонкий широкий логотип).
4. **brand.md в чате (2.4)**: человек кидает текстовый файл со стилем (цвета, шрифты, правила движения, голос, музыка).
   Сохранить его и выполнить `python3 tools/shorts.py brand-md import brand.md`: в `memory/brand/` появятся `brand.json`
   (в плане `"brand": {"preset": "memory/brand/brand.json"}`), `brand.css` (переменные для HTML-сцен) и копия `brand.md`;
   `code-new` берёт их сам. Бланк: `brand-md template -o brand.md`, что понято: `brand-md show`. Правила движения
   (длительности, easing, что никогда не двигается) читать перед кодом сцены и соблюдать (`reference/code-video.md`).
5. **Не сейчас**: `mono` + `prefs skip brand`.

Стиль под один ролик: в плане `"brand": {"preset": "mono"}` или переопредели `palette` и `fonts` прямо в плане.

## Что запрещено (QA проверяет)
- свечение (blur-тень) на тексте и объектах; градиентные плашки и фоны;
- шрифты по умолчанию (DejaVu, Arial, Inter, Roboto...) без явной причины в `fonts.reason`;
- эмодзи как элемент кадра; больше 3 основных цветов; пустые панели и мёртвые зоны больше 15% кадра.

## Шрифты в комплекте (OFL, кириллица)
Montserrat ExtraBold/SemiBold, Jost Light/Medium, Manrope SemiBold/Bold, Oswald Bold, JetBrains Mono, PT Serif Bold.
Лицензии: `assets/fonts/OFL-*.txt`.
