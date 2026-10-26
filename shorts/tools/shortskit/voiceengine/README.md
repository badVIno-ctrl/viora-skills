# VoiceEngine внутри Shorts

Офлайн-озвучка RU + EN любым полом и возрастом (2-105), персонажи, эмоции, эффекты. Сеть, GPU и ключи не нужны.

Не запускать отсюда. Единственный вход:

```bash
python tools/shorts.py voice-setup                       # один раз: распаковать модели + самопроверка
python tools/shorts.py voice "Текст" --attrs "ж, 90" -o out/babushka.wav --srt out/babushka.srt
python tools/shorts.py voice -s dialog.txt -o out/dialog.mp3
python tools/shorts.py voice --list
```

В планах, мультиках и стеке голос задаётся строкой атрибутов (`"voice": "м, 7, радостно"`), движок `auto`
сам берёт VoiceEngine. Правила и таблицы: `reference/voice.md`.

- `engine/` код движка (numpy + onnxruntime), правки Shorts: точные тайминги слов (durs_out, marks).
- `user_stress.txt` словарь ударений движка; свой словарь пользователя: `memory/stress.txt` (з+амок).
- Модели: `assets/voice/voiceengine-models.tar.xz` (запечатан, не открывать), `assets/voice/SOURCES.md`.
- Лицензии: `THIRD_PARTY_LICENSES.md`.
