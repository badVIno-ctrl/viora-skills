"""Item 4 (1.1.0): covers. Three different ideas, minimal = black + line symbol + big caps,
checks: 3-5 words, 320 px, squint silhouette, contrast, no gradient, no glow."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from shortskit.engine import brand as B
from shortskit.meta import cover as C
from shortskit.meta.symbols import ALL, draw_symbol, symbol_for

PLAT = ["youtube_shorts"]
WORDS = ["САЙТ", "ЗА", "МИНУТУ"]


@pytest.fixture(scope="module")
def brand():
    return B.resolve({"preset": "mono"}, None, "ru")


def _frame(seed: int = 0) -> np.ndarray:
    """A frame with a clear subject: bright disc on a dark textured background."""
    rng = np.random.default_rng(seed)
    img = (rng.integers(20, 60, (720, 1280, 3))).astype(np.uint8)
    im = Image.fromarray(img)
    ImageDraw.Draw(im).ellipse([700 + seed * 40, 160, 1100 + seed * 40, 560], fill=(230, 200, 120))
    return np.asarray(im)


@pytest.mark.parametrize("text,want", [("Как защитить пароль", "lock"), ("Бесплатный доступ к GPT", "key"),
                                       ("Шахматный турнир нейросетей", "chess"), ("Сайт, который делает logo", "browser"),
                                       ("Эдит из фильма", "play"), ("Игра на three.js", "code"),
                                       ("Рост подписчиков", "chart"), ("Новая модель ИИ", "chip")])
def test_symbol_for_topic(text, want):
    assert symbol_for(text) == want


def test_symbol_fallback_by_source():
    assert symbol_for("Что-то", ["site"]) == "browser"
    assert symbol_for("xyz") == "gear"


@pytest.mark.parametrize("name", ALL)
def test_symbols_draw(name):
    im = draw_symbol(name, 400, 12, (255, 255, 255), (230, 57, 70))
    a = np.asarray(im)[..., 3]
    assert 0.02 < (a > 128).mean() < 0.5  # lines, not a filled blob


@pytest.mark.parametrize("fmt", ["16x9", "9x16"])
def test_minimal_cover_passes(brand, fmt):
    # 1.0.0 BAD case: the minimal cover failed "weak silhouette" (blurred grey std < 25) on a good design
    img, info, mask = C.compose_cover(_frame(), WORDS, brand, "minimal", fmt, PLAT, symbol="lock")
    arr = np.asarray(img)
    assert (arr.reshape(-1, 3).mean(axis=0) < 40).all(), "minimal must be black"
    assert C.check_cover(img, info, WORDS, fmt, PLAT, mask) == []
    assert info["idea"] == "symbol"


@pytest.mark.parametrize("fmt", ["16x9", "9x16"])
def test_three_ideas_differ_and_pass(brand, fmt):
    a, b = _frame(0), _frame(3)
    outs = [C.compose_cover(a, WORDS, brand, "minimal", fmt, PLAT, symbol="browser"),
            C.compose_cover(a, WORDS, brand, "hero", fmt, PLAT),
            C.compose_cover(b, WORDS, brand, "split", fmt, PLAT, second=a)]
    assert len({o[1]["idea"] for o in outs}) == 3
    for img, info, mask in outs:
        assert C.check_cover(img, info, WORDS, fmt, PLAT, mask) == [], info["idea"]
    assert C.ideas_differ([o[0] for o in outs]) == []


def test_same_image_three_times_is_flagged(brand):
    img, _, _ = C.compose_cover(_frame(), WORDS, brand, "hero", "16x9", PLAT)
    assert C.ideas_differ([img, img, img])


def test_word_count(brand):
    six = WORDS + ["И", "ЕЩЁ", "РАЗ"]
    img, info, mask = C.compose_cover(_frame(), six, brand, "minimal", "16x9", PLAT, symbol="key")
    assert any("words" in e for e in C.check_cover(img, info, six, "16x9", PLAT, mask))


def test_tiny_text_fails(brand):
    img, info, mask = C.compose_cover(_frame(), WORDS, brand, "minimal", "16x9", PLAT, symbol="key")
    info = dict(info, font_px=40)
    assert any("320 px" in e for e in C.check_cover(img, info, WORDS, "16x9", PLAT, mask))


def test_glow_is_detected(brand):
    # BAD: soft halo behind the text
    img, info, mask = C.compose_cover(_frame(), WORDS, brand, "minimal", "16x9", PLAT, symbol="key")
    halo = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(10))
    glow = Image.composite(Image.new("RGB", img.size, (200, 200, 200)), img, halo.point(lambda v: int(v * 0.8)))
    glow.paste(img, mask=Image.fromarray((mask * 255).astype(np.uint8)))
    errs = C.check_cover(glow, dict(info), WORDS, "16x9", PLAT, mask)
    assert any("glow" in e for e in errs), errs


def test_low_contrast_text_fails(brand):
    img = Image.new("RGB", (1280, 720), (90, 90, 90))
    f, lines, size, lh = C._fit(WORDS, brand.display.path, 1000, 400, 150, 84)
    ImageDraw.Draw(img).text((80, 200), " ".join(WORDS), font=f, fill=(120, 120, 120))
    mask = C._text_mask(img.size, [WORDS], f, lh, 80, 200)
    info = {"box": [80, 200, 900, 400], "font_px": size, "text_color": "#787878", "graphic_boxes": [[0, 0, 1280, 720]]}
    assert any("contrast" in e for e in C.check_cover(img, info, WORDS, "16x9", PLAT, mask))


def test_noise_without_subject_fails_squint():
    # BAD: busy noise with no figure (nothing survives a squint)
    rng = np.random.default_rng(1)
    img = Image.fromarray(rng.integers(0, 255, (720, 1280, 3)).astype(np.uint8))
    assert not C.squint(img)["ok"]


def test_gradient_plate_is_detected(brand):
    img, info, mask = C.compose_cover(_frame(), WORDS, brand, "minimal", "16x9", PLAT, symbol="gear")
    arr = np.asarray(img).copy()
    ramp = np.linspace(10, 200, 1280).astype(np.uint8)
    arr[:, :, :] = np.maximum(arr, ramp[None, :, None])
    errs = C.check_cover(Image.fromarray(arr), dict(info), WORDS, "16x9", PLAT, mask)
    assert any("gradient" in e for e in errs)


def _fake_out(tmp_path):
    import json
    d = tmp_path / "out"
    (d / "cover" / "candidates").mkdir(parents=True)
    for i, t in enumerate((0.5, 3.0, 6.0)):
        Image.fromarray(_frame(i)).resize((1080, 1920)).save(d / "cover" / "candidates" / f"{t:06.2f}-s{i}.png")
    scenes = [{"id": f"s{i}", "type": "html", "start": i * 3.0, "length": 3.0} for i in range(3)]
    br = B.resolve({"preset": "mono"}, None, "ru")
    (d / "manifest.json").write_text(json.dumps({"name": "demo", "video": "demo.mp4", "language": "ru",
                                                 "platforms": PLAT, "scenes": scenes, "brand": br.to_dict()}))
    (d / "plan.resolved.json").write_text(json.dumps({"brand": {"preset": "mono"}, "meta": {},
                                                     "metadata": {"topic": "защита паролей", "cover_text": "ПАРОЛЬ ЗА МИНУТУ"},
                                                     "scenes": [{"id": "s0", "on_screen_text": "X"}]}))
    return d


def test_cover_dir_with_generator_uses_model_for_hero(tmp_path, monkeypatch):
    d = _fake_out(tmp_path)
    seen = {}

    def fake_gen(prompt, out, provider, landscape=True):
        seen["prompt"], seen["provider"] = prompt, provider
        Image.fromarray(_frame(5)).save(out)
        return out
    monkeypatch.setenv("SHORTS_IMAGE_PROVIDER", "openai")
    monkeypatch.setattr(C, "generate_image", fake_gen)
    res = C.cover_dir(d)
    assert seen["provider"] == "openai" and "text" in seen["prompt"].lower() and "not" in seen["prompt"].lower()
    assert res["generated"] and res["symbol"] == "lock"
    hero = [v for v in res["variants"] if v["variant"] == "hero"]
    assert all(v["source"] == "model:openai" for v in hero)
    assert res["ideas"] == ["minimal", "hero", "split"]
    assert not res["errors"], res["errors"]


def test_cover_dir_without_generator_writes_prompts(tmp_path, monkeypatch):
    d = _fake_out(tmp_path)
    monkeypatch.setenv("SHORTS_IMAGE_PROVIDER", "none")
    res = C.cover_dir(d)
    assert not res["generated"] and "ask_user" in res
    pr = (d / "cover" / "prompt.md").read_text()
    assert "## A minimal" in pr and "## B hero" in pr and "## C split" in pr and "lock" in pr
    assert len(res["variants"]) == 6


# ---------------------------------------------------------------- 1.1.0 contract fixes

TT = ["youtube_shorts", "tiktok"]


@pytest.mark.parametrize("variant", ["minimal", "hero", "split", "outline"])
def test_tiktok_cover_text_clear_of_action_column(brand, variant):
    # BAD case (found on the offline fixture): on 9:16 for TikTok the caps ran into the like/comment column
    words = ["ОДИН", "ФАЙЛ", "АНИМАЦИЯ"]
    img, info, mask = C.compose_cover(_frame(0), words, brand, variant, "9x16", TT, second=_frame(3), symbol="code")
    assert "text outside the safe zone" not in C.check_cover(img, info, words, "9x16", TT, mask)
    ys, xs = np.nonzero(mask)
    assert not ((xs >= 780) & (ys >= 840)).any()


def _busy(seed: int) -> np.ndarray:
    """White rings on black: the text drowns in them at 320 px (what the offline fixture produced)."""
    im = Image.new("RGB", (1280, 720), (8, 8, 8))
    d = ImageDraw.Draw(im)
    for r in range(60, 700, 55):
        d.ellipse([640 - r + seed * 9, 360 - r, 640 + r + seed * 9, 360 + r], outline=(240, 240, 240), width=6)
    return np.asarray(im)


def test_split_band_survives_busy_frames():
    br = B.resolve({"preset": "viora"}, None, "ru")
    words = ["ОДИН", "ФАЙЛ", "АНИМАЦИЯ"]
    img, info, mask = C.compose_cover(_busy(0), words, br, "split", "9x16", TT, second=_busy(4))
    assert any("silhouette" in e for e in C.check_cover(img, info, words, "9x16", TT, mask))  # the bad case
    img, info, mask = C.compose_cover(_busy(0), words, br, "split_band", "9x16", TT, second=_busy(4))
    assert C.check_cover(img, info, words, "9x16", TT, mask) == []
    assert info["solid_band"] and info["idea"] == "split"


def test_hero_plate_is_7_to_1_with_weak_accent():
    from shortskit.util import contrast
    br = B.resolve({"preset": "viora"}, None, "ru")  # #E63946: 5:1 with black
    img, info, mask = C.compose_cover(_frame(0), WORDS, br, "hero", "16x9", PLAT)
    gx0, gy0, _, _ = info["graphic_boxes"][0]
    plate = "#%02X%02X%02X" % img.getpixel((gx0 + 2, gy0 + 2))[:3]
    assert contrast(plate, info["text_color"]) >= 7.0


@pytest.mark.parametrize("variant", ["minimal", "split"])
def test_long_word_shrinks_instead_of_spilling(brand, variant):
    # BAD case (demo a): "БЕСПЛАТНО" at the minimum size ran past the TikTok action column
    words = ["2", "САЙТА", "БЕСПЛАТНО"]
    img, info, mask = C.compose_cover(_frame(0), words, brand, variant, "9x16", TT, second=_frame(3), symbol="browser")
    errs = C.check_cover(img, info, words, "9x16", TT, mask)
    assert "text outside the safe zone" not in errs and not any("too small" in e for e in errs), errs
