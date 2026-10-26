# Голосовые модели (VoiceEngine)

Один запечатанный файл `voiceengine-models.tar.xz` (125 МБ, внутри 178 МБ моделей). Не открывать, не листать,
не читать: его распаковывает `python tools/shorts.py voice-setup` (или первая озвучка) один раз и проверяет sha256
из `pack.json`. Код движка лежит в `tools/shortskit/voiceengine/`, работа с ним только через `shorts.py voice`
и движок TTS `voiceengine` (по умолчанию для ru/en).

| Что внутри | Лицензия | Источник |
|---|---|---|
| `models/ru/`: Silero TTS v5_cis_base (акустика + вокодер), ONNX | MIT | https://github.com/snakers4/silero-models |
| `models/ru_stress/`: silero-stress (ударения, омографы), веса в numpy | MIT | https://github.com/snakers4/silero-stress |
| `models/ru_stress/`: stressonnx-models (n-граммы и исключения ударений) | Apache-2.0 | https://huggingface.co/TigreGotico/stressonnx-models |
| `models/en/`: Kokoro-82M v1.0 int8 ONNX (+ входы f0_scale / f0_range), стили голосов | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M |
| `models/en/espeak/`: eSpeak NG 1.52 (libespeak-ng + данные, только фонемы английского) | GPL-3.0-or-later | https://github.com/espeak-ng/espeak-ng |

Все голоса оригинальные синтетические (смеси базовых тембров + моделирование возраста), не копии реальных людей.
Полные условия: `tools/shortskit/voiceengine/THIRD_PARTY_LICENSES.md`.
