# Видео кодом (SHORTS 2.4)

Анимация пишется как код (HTML + canvas, p5.brush, thinking-orbs, Three.js), рендер снимает её кадр за кадром
через `window.seek(t)` и кладёт поверх голос (VoiceEngine), музыку и субтитры. Подробно: reference/code-video.md.

Создать проект: `python3 tools/shorts.py code-new ПАПКА` (scene.html, plan.json, fonts/, vendor/ с эффектами,
brand.css из memory/brand/brand.md, если он есть).

1. `scene.html`, блок `SCENE`: `kicker`, `title` (слова заголовка), `steps` (шаги: `cue` = слово озвучки,
   на котором шаг начинается, `orb` = состояние орба), `orb` (состояние до первого шага), `seed`.
   Кадр рисует `seek(t)` только от `t`: без `Date.now()`, `performance.now()` и `Math.random` (для случайности `rng(seed)`).
2. `window.SHORTS` даёт рендер: `length`, `fps`, `words` (слова озвучки с таймингами), `beats`, `strong`,
   `drop`, `brand`. Шаг начинается на своём слове; если слова нет, на следующем сильном бите.
3. Главное движение (удар заголовка, полоса акцента, кисть) идёт на `MAIN`: бит, который ты назвал
   (`beats.js` `--main`), иначе дроп трека, иначе 5-й бит.
4. Свой трек: `python3 tools/shorts.py beats трек.mp3 --js beats.js --main 9` (9-й бит несёт основное
   движение) и в plan.json `"music": {"source": "трек.mp3"}`. Без трека: `"auto"`, музыка найдётся на YouTube
   по `mood` и встанет под голос, кредит автора уйдёт в описание.
5. Голос: plan.json `audio.voice.voice` (`ru-male-1`, `ведущая`, `"ж, 30, бодро"`, список: `shorts.py voice --list`).
6. Предпросмотр: открыть `scene.html` в браузере (крутится по кругу, без озвучки слова идут по таймеру).
7. Сборка и проверка: `python3 tools/shorts.py all plan.json --out out`, потом `shorts.py qa out`.

Зоны кадра 1080x1920: надпись и счётчик y 350, заголовок 480-800 (безопасная зона Shorts / TikTok / Reels
y 288-1248), полоса субтитров 928-1248 (её рисует движок, сцена туда ничего не ставит), ниже только декор:
орб y 1500 и эквалайзер, их не жалко закрыть интерфейсом площадки.

Эффекты: `vendor/` (`shorts.py fx-get ...`, лицензии рядом), шрифты: `fonts/` (OFL), стиль: `brand.css`
(`shorts.py brand-md import brand.md`).
