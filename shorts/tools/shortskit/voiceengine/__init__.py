"""VoiceEngine embedded in Shorts (offline RU + EN TTS, any gender / age / character, emotions, effects).

Do not call this package directly: use `python tools/shorts.py voice ...` or the TTS engine "voiceengine"
(shortskit.voice). Code: engine/ (numpy + onnxruntime). Models: one sealed pack
assets/voice/voiceengine-models.tar.xz, unpacked once by shortskit.voice.ensure_models().
"""
