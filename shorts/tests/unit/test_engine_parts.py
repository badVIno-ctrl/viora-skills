import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from shortskit.engine import audio as A
from shortskit.engine import brand as B
from shortskit.engine import graphics as G
from shortskit.engine import layout as L
from shortskit.engine.clips import Camera, SpeedMap
from shortskit.engine.tts import estimate_words
from shortskit.config import asset
from shortskit.qa import frames as F
from shortskit.util import ShortsError, contrast, fit_contrast


def test_qr_generated_decodes_with_quiet_zone():
    img, mod = G.qr_image("https://t.me/VioraStudio", 432, "#000000", "#FFFFFF")
    arr = np.asarray(img.convert("RGB"))
    assert (arr[: 4 * mod, : 4 * mod] == 255).all()  # 4-module quiet zone
    canvas = np.full((1920, 1080, 3), 30, np.uint8)
    canvas[600:600 + arr.shape[0], 300:300 + arr.shape[1]] = arr
    assert F.decode_qr(canvas) == ["https://t.me/VioraStudio"]


def test_cta_qr_sprite_size_and_safe_zone():
    br = B.resolve({"preset": "viora"})
    lay = L.compute({"mode": "three"}, ["youtube_shorts", "tiktok"])
    s = G.cta_qr("https://t.me/x", "t.me/x", br, lay)
    assert s.qr_box.w >= 360 and lay.safe.allows(s.box)


def test_glow_and_gradient_detectors():
    br = B.resolve({"preset": "viora"})
    lay = L.compute({"mode": "center_only"}, ["youtube_shorts"])
    flat = np.asarray(G.label("ТЕСТ", br, lay).img)
    br.effects = {"text_glow": True, "gradient_plate": True}
    bad = np.asarray(G.label("ТЕСТ", br, lay).img)
    assert F.glow_score(flat) < 2.0 and F.glow_score(bad) > 4.0
    assert not F.gradient_score(flat)["gradient"]
    assert F.gradient_score(bad)["gradient"]


def test_dead_zone_detector():
    frames = np.zeros((6, 1920, 1080, 3), np.uint8)
    frames[:, :400] = np.random.default_rng(1).integers(0, 255, (6, 400, 1080, 3))
    dz = F.dead_zones(frames, [i * 0.5 for i in range(6)], bg=(0, 0, 0))
    assert dz["max_share"] > 0.6
    frames[:, 400:] = np.random.default_rng(2).integers(0, 255, (6, 1520, 1080, 3))
    assert F.dead_zones(frames, [i * 0.5 for i in range(6)], bg=(0, 0, 0))["max_share"] < 0.05


def test_contrast_fit():
    c = fit_contrast("#E63946", "#000000", 7.0)
    assert contrast(c, "#000000") >= 7.0


def test_speed_map_and_camera():
    sm = SpeedMap([{"t": 2, "rate": 2.0}, {"t": 4, "rate": 0.5}])
    assert sm.out_at(2) == 2 and sm.out_at(4) == 3 and abs(sm.src_at(3.5) - 4.25) < 1e-9
    cam = Camera.from_clicks(1080, 1152, [(1.0, 500, 500)])
    z0, _, _ = cam.at(0)
    z1, x, y = cam.at(1.2)
    assert z0 == 1.0 and z1 > 1.2 and (x, y) == (500, 500)


def test_sfx_and_loudnorm(tmp_path):
    for n in A.SYNTH_OK:  # 2.2: noise-only drafts (opt-in audio.sfx = synth)
        x = A.synth_sfx(n)
        assert 0.5 < np.abs(x).max() <= 1.0
    for n in A.TONAL:  # pitched sounds (bells, risers, 808 hits) are never synthesized
        with pytest.raises(ShortsError):
            A.synth_sfx(n)
    t = np.arange(48000 * 4) / 48000
    sig = (0.05 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    A._write_wav(tmp_path / "a.wav", np.stack([sig, sig], 1))
    A.loudnorm(tmp_path / "a.wav", tmp_path / "b.wav", -14)
    m = A.measure(tmp_path / "b.wav")
    assert abs(m["lufs"] + 14) < 1.0 and m["true_peak"] <= -1.0


def test_beats_on_bundled_bed():
    b = A.beats(asset("audio/bed.mp3"))
    assert 100 < b["tempo"] < 125 or 50 < b["tempo"] < 62  # 112 bpm (or half)
    assert len(b["downbeats"]) >= 8


def test_estimated_word_timings():
    w = estimate_words("раз два три", 2.0)
    assert len(w) == 3 and w[0]["s"] < w[1]["s"] < w[2]["s"] < 2.0


def test_brand_presets():
    for p in B.PRESETS:
        br = B.resolve({"preset": p}, None, "ru")
        assert len(br.palette) <= 3
        assert not B.default_font_used(br)
    over = B.resolve({"preset": "mono", "palette": {"accent": "#FF0000"}})
    assert over.accent == "#FF0000"
