import json, subprocess, zipfile
from pathlib import Path
from types import SimpleNamespace
import pytest
from shortskit.config import asset
from shortskit.engine.banner import AnimatedBanner, contrast
from shortskit.deliver import deliver, slug


def brand():
    f = asset("fonts")
    return SimpleNamespace(body=SimpleNamespace(path=f / "Manrope-SemiBold.ttf"), display=SimpleNamespace(path=f / "Manrope-Bold.ttf"), logo_text="")


def cfg(**kw):
    c = {"name": "Учебный сервис", "message": "Субтитры без ручного набора", "action": "Открыть пример", "handle": "example_bot",
         "qr_url": "https://example.invalid/x?start=r_Ab", "animation": {"variant": "quattro", "safe_right": 120}}
    c.update(kw)
    return c


def inside(box, w, h):
    x, y, bw, bh = box
    return x >= 0 and y >= 0 and x + bw <= w and y + bh <= h


def test_all_elements_inside_panel_and_not_overlapping_qr():
    b = AnimatedBanner(1080, 384, brand(), cfg())
    m = b.manifest()
    qx, qy, qw, qh = m["qr_box"]
    for name, box in m["element_boxes"].items():
        assert inside(box, 1080, 384), name
        x, y, bw, bh = box
        assert x + bw <= qx, f"{name} touches the QR"
    assert "disclosure" in m["element_boxes"] and m["cta_contrast"] >= 4.5


def test_content_block_vertically_centred():
    b = AnimatedBanner(1080, 384, brand(), cfg())
    boxes = b.manifest()["element_boxes"]
    top = min(v[1] for k, v in boxes.items() if k != "disclosure")
    bottom = max(v[1] + v[3] for k, v in boxes.items() if k != "disclosure")
    assert abs((top - 4) - (384 - bottom)) <= 40  # no big dead space on one side


def test_long_handle_moves_into_text_stack_not_microtype():
    b = AnimatedBanner(1080, 384, brand(), cfg(handle="very_long_bot_name_here"))
    m = b.manifest()
    assert all(inside(v, 1080, 384) for v in m["element_boxes"].values())


def test_too_long_label_is_rejected():
    with pytest.raises(ValueError):
        AnimatedBanner(1080, 384, brand(), cfg(name="Очень длинное название рекламируемого сервиса для баннера"))


def test_risky_claim_warns_without_verification():
    b = AnimatedBanner(1080, 384, brand(), cfg(message="Бесплатно и быстро"))
    assert any("risky" in w for w in b.manifest()["warnings"])
    b2 = AnimatedBanner(1080, 384, brand(), cfg(message="Бесплатно и быстро", claims_verified=True))
    assert not any("risky" in w for w in b2.manifest()["warnings"])


def mk_video(p: Path, w=1080, h=1920, audio=True, dur=2):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=blue:s={w}x{h}:d={dur}:r=25"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=d={dur}", "-shortest"]
    cmd += ["-pix_fmt", "yuv420p", str(p)]
    subprocess.run(cmd, check=True)


def test_deliver_clean_top_level_and_zip(tmp_path):
    v = tmp_path / "raw.mp4"; mk_video(v)
    (tmp_path / "x.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    spec = {"set_title": "Тест", "items": [{"video": str(v), "title": "Первый ролик: тест #шортс", "description": "Реклама. Ссылка: https://e.invalid/a",
                                            "ad": {"name": "E", "url": "https://e.invalid/a"}, "service": [str(tmp_path / "x.srt")]}]}
    sp = tmp_path / "deliver.json"; sp.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    rep = deliver(str(sp), str(tmp_path / "ГОТОВО"), zip_it=True)
    assert rep["ok"], rep
    assert rep["files"] == ["01-Первый ролик тест.mp4", "ОПИСАНИЯ.txt"]
    assert not any(f.endswith((".srt", ".json")) for f in rep["files"])
    names = zipfile.ZipFile(rep["zip"]).namelist()
    assert not any("_служебное" in n for n in names)
    txt = (tmp_path / "ГОТОВО" / "ОПИСАНИЯ.txt").read_text(encoding="utf-8")
    assert "НАЗВАНИЕ:" in txt and "ОПИСАНИЕ:" in txt


def test_deliver_blocks_missing_title_wrong_size_and_undisclosed_ad(tmp_path):
    v = tmp_path / "raw.mp4"; mk_video(v, 720, 1280, audio=False)
    spec = {"items": [{"video": str(v), "title": "", "description": "текст", "ad": {"url": "https://e.invalid/a"}}]}
    sp = tmp_path / "d.json"; sp.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    rep = deliver(str(sp), str(tmp_path / "out"))
    assert not rep["ok"]
    joined = " ".join(rep["errors"])
    assert "нет названия" in joined and "1080x1920" in joined and "звуков" in joined and "Реклама" in joined


def test_slug():
    assert slug('A/B: "x" #tag') == "A B x"
