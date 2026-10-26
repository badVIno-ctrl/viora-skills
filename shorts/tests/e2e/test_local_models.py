"""1.1.0 item 10: Piper (offline voice) and faster-whisper (word timings) run locally, models in the cache.
Skipped when the optional packages are not installed (bash tools/install.sh --local). First run downloads
the models (~60 MB voice, ~140 MB whisper base) into SHORTS_CACHE."""
from __future__ import annotations

import importlib.util
import os

import pytest

needs = pytest.mark.skipif(not (importlib.util.find_spec("piper") and importlib.util.find_spec("faster_whisper")),
                           reason="optional: bash tools/install.sh --local")


@pytest.fixture()
def shared_cache(monkeypatch):
    # keep downloaded models between runs (SHORTS_MODELS or the skill's own .cache/models), not in tmp
    if not os.environ.get("SHORTS_MODELS"):
        from shortskit.config import skill_root

        monkeypatch.setenv("SHORTS_MODELS", str(skill_root() / ".cache" / "models"))


@needs
@pytest.mark.parametrize("lang,text", [("ru", "Два бесплатных сайта, и оба пригодятся."),
                                       ("en", "This whole animation is one HTML file.")])
def test_piper_voice_with_whisper_word_timings(shared_cache, monkeypatch, lang, text):
    from shortskit.engine import tts

    monkeypatch.setenv("SHORTS_TTS", "piper")
    sp = tts.synth(text, lang=lang, engine="piper")
    assert sp.engine == "piper" and sp.duration > 1.0
    assert not sp.estimated, "word timings must come from faster-whisper, not the syllable estimate"
    assert [w["w"] for w in sp.words] == text.split()
    starts = [w["s"] for w in sp.words]
    assert starts == sorted(starts) and sp.words[-1]["e"] <= sp.duration + 0.1


@needs
def test_whisper_transcribes_piper_audio(shared_cache, tmp_path, monkeypatch):
    from shortskit.adapters.film import transcribe
    from shortskit.engine import tts

    monkeypatch.setenv("SHORTS_TTS", "piper")
    sp = tts.synth("Смотри до конца, там самое интересное.", lang="ru", engine="piper")
    words = transcribe(sp.wav, lang="ru", cache=False)
    got = " ".join(w["w"] for w in words).lower()
    assert "конца" in got and "интересное" in got, got


def test_doctor_reports_unverified_engines():
    from shortskit.doctor import doctor

    v = doctor()["verification"]
    assert "не проверено" in v["elevenlabs"] and "не проверено" in v["gemini_image"]
    assert "piper" in v and "faster_whisper" in v
