# Компоненты и лицензии

VoiceEngine (код в `tools/shortskit/voiceengine/engine/`, модели в `assets/voice/voiceengine-models.tar.xz`,
после распаковки папка `models/`) собран из открытых компонентов. Все голоса движка —
оригинальные синтетические смеси эмбеддингов базовых дикторов с параметрическим моделированием возраста;
они не воспроизводят голос какого-либо конкретного человека.

| Компонент | Где | Лицензия | Источник |
|---|---|---|---|
| Silero TTS **v5_cis_base** (акустическая модель + вокодер), переэкспорт в ONNX | `models/ru/` | MIT (базовые CIS-модели, по заявлению авторов) | https://github.com/snakers4/silero-models |
| silero-stress (ударения, омографы) — веса перенесены в numpy | `models/ru_stress/` | MIT | https://github.com/snakers4/silero-stress |
| stressonnx-models (n-gram словарь и исключения ударений) | `models/ru_stress/` | Apache-2.0 | https://huggingface.co/TigreGotico/stressonnx-models |
| Kokoro-82M v1.0 (int8 ONNX, добавлены входы f0_scale / f0_range) и стили голосов | `models/en/` | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M , https://github.com/thewh1teagle/kokoro-onnx |
| eSpeak NG 1.52 (libespeak-ng + данные, только фонемизация английского) | `models/en/espeak/` | GPL-3.0-or-later | https://github.com/espeak-ng/espeak-ng (исходный код там же) |

eSpeak NG поставляется как отдельная динамическая библиотека без изменений и загружается через ctypes;
её исходный код доступен по ссылке выше. При отсутствии/несовместимости библиотеки движок использует
системный espeak-ng.

Полные тексты лицензий: MIT — https://opensource.org/license/mit ; Apache-2.0 — https://www.apache.org/licenses/LICENSE-2.0 ;
GPL-3.0 — https://www.gnu.org/licenses/gpl-3.0.html
