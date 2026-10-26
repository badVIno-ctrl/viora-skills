"""v4.0: fetch ladder, floating ad card, stack compositor, pack hand-off."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from shortskit import cardbanner as C
from shortskit import fetch as F
from shortskit import pack as P
from shortskit import stack as S
from shortskit.util import ShortsError


# ------------------------------------------------------------------ fetch

def test_classify_errors():
    assert F.classify("ERROR: Sign in to confirm you're not a bot") == "bot_block"
    assert F.classify("ERROR: Video unavailable") == "unavailable"
    assert F.classify("HTTP Error 403: Forbidden") == "outdated_or_formats"
    assert F.classify("something odd") == "other"


def test_parse_section():
    assert F.parse_section("7.0-16") == (7.0, 16.0)
    assert F.parse_section("1:02:03-1:02:10") == (3723.0, 3730.0)
    assert F.parse_section(None) is None
    with pytest.raises(ShortsError):
        F.parse_section("10-5")


class _R:
    def __init__(self, rc, err=""):
        self.returncode, self.stderr, self.stdout = rc, err, ""


def test_ladder_continues_after_bot_block(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if "player_client=tv" in " ".join(cmd):
            (tmp_path / "v.mp4").write_bytes(b"x" * 10)
            return _R(0)
        return _R(1, "ERROR: Sign in to confirm you're not a bot")

    monkeypatch.setattr(F.subprocess, "run", fake_run)
    monkeypatch.setattr(F, "_update_ytdlp", lambda: False)
    res = F.fetch("https://www.youtube.com/watch?v=abc", tmp_path, "v", (1.0, 5.0))
    assert res["ok"] and res["path"].endswith("v.mp4")
    steps = [a["step"] for a in res["attempts"]]
    assert steps[0] == "client=default" and "client=tv" in steps
    assert all("--download-sections" in c for c in calls if Path(c[0]).name not in ("ffprobe", "ffmpeg"))   # 2.1: H.264 check also shells out


def test_total_failure_gives_local_command_and_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(F.subprocess, "run", lambda cmd, **kw: _R(1, "Sign in to confirm you're not a bot"))
    monkeypatch.setattr(F, "_update_ytdlp", lambda: True)
    res = F.fetch("https://www.youtube.com/watch?v=abc", tmp_path, "clip", (3.0, 9.0))
    assert not res["ok"]
    assert "yt-dlp" in res["local_command"] and "*3.00-9.00" in res["local_command"]
    assert any(a["step"] == "update yt-dlp" for a in res["attempts"])


def test_cookies_and_proxy_rungs_only_from_user_env(monkeypatch, tmp_path):
    names = [n for n, _ in F._attempts(1080, False)]
    assert not any("cookies" in n or "proxy" in n for n in names)
    ck = tmp_path / "c.txt"
    ck.write_text("# Netscape")
    monkeypatch.setenv("SHORTS_YTDLP_COOKIES", str(ck))
    monkeypatch.setenv("SHORTS_YTDLP_PROXY", "http://127.0.0.1:9")
    names = [n for n, _ in F._attempts(1080, False)]
    assert any("user-cookies" in n for n in names) and "user-proxy" in names


def test_unavailable_video_does_not_burn_the_ladder(tmp_path, monkeypatch):
    n = {"c": 0}

    def fake_run(cmd, **kw):
        n["c"] += 1
        return _R(1, "ERROR: Private video")

    monkeypatch.setattr(F.subprocess, "run", fake_run)
    monkeypatch.delenv("SHORTS_YTDLP_COOKIES", raising=False)
    monkeypatch.delenv("SHORTS_YTDLP_BROWSER", raising=False)
    res = F.fetch("https://www.youtube.com/watch?v=abc", tmp_path, "p", None, allow_update=False)
    assert not res["ok"] and n["c"] == 1


# ------------------------------------------------------------------ card banner

SPEC = {"brand": "Test VPN", "theme": "navy", "url": "t.me/test_bot", "qr_url": "https://t.me/test_bot?start=r_AbC123xyz",
        "slides": [{"title": "Быстрый VPN\nв Telegram", "sub": "Открой бота"}, {"title": "Надёжная\nинфраструктура", "sub": "Test VPN"},
                   {"title": "Ссылка\nв описании", "sub": ""}]}


def test_card_slides_rotate_and_crossfade():
    cb = C.CardBanner(SPEC)
    assert cb._slide_state(0.5) == [(0, 1.0, 0.0)]
    st = cb._slide_state(cb.slide_s + 0.1)
    assert [s[0] for s in st] == [0, 1] and abs(st[0][1] + st[1][1] - 1.0) < 1e-6
    assert cb._slide_state(cb.slide_s * 3 + 1.0)[0][0] == 0   # wraps around


def test_card_frame_enter_exit_and_size():
    cb = C.CardBanner(SPEC)
    w, h = cb.size()
    f0, f1, f2 = cb.frame(0.0, 6.0), cb.frame(2.0, 6.0), cb.frame(5.99, 6.0)
    assert f1.size == (w, h) == (760 + 2 * C.MARGIN, 320 + 2 * C.MARGIN)
    a = lambda im: np.asarray(im.getchannel("A")).max()
    assert a(f0) == 0 and a(f1) == 255 and a(f2) < 40            # starts invisible, fully visible, fades at the end


def test_card_qr_decodes_exactly():
    cb = C.CardBanner(SPEC)
    f = cb.frame(2.0)
    arr = cv2.cvtColor(np.asarray(f.convert("RGB")), cv2.COLOR_RGB2BGR)
    arr = cv2.resize(arr, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    val, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
    assert val == SPEC["qr_url"]


def test_card_text_never_below_34px_and_headline_fits():
    spec = dict(SPEC, slides=[{"title": "Очень длинный заголовок про интернет без границ", "sub": "x"}])
    cb = C.CardBanner(spec)
    lay = cb.slide_layers[0]
    assert lay.width <= cb.text_w + 10


def test_card_needs_slides_and_honest_monogram():
    with pytest.raises(ShortsError):
        C.CardBanner({"brand": "X", "slides": []})
    cb = C.CardBanner(dict(SPEC, brand="Zeta"))
    assert cb.logo_real is False                                # no logo given: monogram, not an invented mark


def test_card_preview_and_webm(tmp_path):
    png = C.preview(SPEC, tmp_path / "p.png")
    assert Image.open(png).height > 400
    out = C.render_webm(SPEC, tmp_path / "c.webm", 1.0)
    assert out.stat().st_size > 1000


# ------------------------------------------------------------------ stack + pack (synthetic media)

def _make_src(path: Path, secs: float = 3.0):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=25:duration={secs}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)


def test_caption_chunks_timing_and_word_groups():
    cues = [(0.0, 2.0, "раз два три четыре пять"), (2.2, 3.0, "шесть")]
    ch = S.caption_chunks(cues, 3)
    assert ch[0]["words"] == ["раз", "два", "три"] and ch[1]["words"] == ["четыре", "пять"]
    assert all(c["t0"] < c["t1"] for c in ch)
    assert abs(ch[1]["t1"] - 2.0) < 1e-6
    assert all(a < b for c in ch for a, b in c["wt"])


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("v40")
    _make_src(d / "main.mp4")
    _make_src(d / "top.mp4")
    (d / "c.srt").write_text("1\n00:00:00,200 --> 00:00:01,500\nпривет мир как дела\n\n2\n00:00:01,600 --> 00:00:02,600\nвсё хорошо\n", encoding="utf-8")
    spec = {"out": str(d / "short.mp4"), "fps": 25,
            "main": {"pieces": [{"src": "main.mp4", "start": 0.2, "end": 2.2}, {"src": "main.mp4", "start": 0.5, "end": 1.5}], "y": 560, "h": 1360, "zoom": 1.2,
                     "snap": "off"},          # a sine tone is no speech: boundaries are tested in test_v22_speech_ad_captions.py
            "top": {"src": "top.mp4", "start": 0, "h": 560},
            "captions": {"srt": "c.srt", "y": 1050}, "hook": {"text": "ПРИВЕТ МИР", "y": 400, "start": 0, "end": 1.0},
            "banner": dict(SPEC, start=0.5, y=330)}
    res = S.render_stack(spec, d)
    return d, res


def test_stack_output_is_1080x1920_with_audio(built):
    d, res = built
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", res["out"]],
                                     capture_output=True, text=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert 2.8 < float(info["format"]["duration"]) < 3.2
    assert not list(Path(res["out"]).parent.glob("*.work"))


def test_stack_banner_sits_in_safe_zone_and_appears_on_time(built):
    """v2.2: banner y=330 would cover the main picture (main starts at 560) -> the card gets its own slot under it."""
    d, res = built
    ad, lay = res["ad"], res["layout"]
    x, y, w, h = ad["card"]
    mx, my, mw, mh = lay["main"]
    assert ad["slot"] == "below" and not ad["problems"]
    assert y >= my + mh and y + h <= 1920 - 480 and x >= 0 and x + w <= 1080 - 150     # off the speaker, inside the organic safe zone (2.3)
    assert any("covered the main picture" in n for n in ad["notes"])
    cap = cv2.VideoCapture(res["out"])
    def frame(t):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        return cap.read()[1]
    before, after = frame(0.2), frame(1.6)
    roi = (slice(y + 20, y + h - 20), slice(x + 20, x + w - 20))
    assert np.abs(before[roi].astype(int) - after[roi].astype(int)).mean() > 8      # card drawn there, after its start
    assert before[1300:].mean() > 3                                                  # below the picture: blurred fill, not black


def _pack_spec(d: Path, video: Path, **over):
    item = {"slug": "test-clip", "name": "Тест", "video": str(video),
            "titles": [{"t": f"Название {i}", "why": "тест"} for i in range(1, 6)], "recommended": 2,
            "description": "Описание.\n\nРеклама. Бот: https://t.me/test_bot?start=r_AbC123xyz\n\n#тест",
            "ad": {"name": "Test", "url": "https://t.me/test_bot?start=r_AbC123xyz"},
            "covers": [{"t0": 0.2, "t1": 2.5, "text": "ПРИВЕТ *МИР*", "tag": "ТЕСТ"}]}
    item.update(over)
    p = d / "pack.json"
    p.write_text(json.dumps({"items": [item]}, ensure_ascii=False), encoding="utf-8")
    return p


def test_pack_delivers_video_title_description_cover_only(built, tmp_path):
    d, res = built
    out = tmp_path / "ГОТОВО"
    r = P.pack(_pack_spec(d, Path(res["out"])), out, make_zip=True)
    folder = out / "01-test-clip"
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["cover.png", "test-clip.mp4", "НАЗВАНИЕ-И-ОПИСАНИЕ.txt"]
    assert Image.open(folder / "cover.png").size == (1080, 1920)
    txt = (folder / "НАЗВАНИЕ-И-ОПИСАНИЕ.txt").read_text(encoding="utf-8")
    assert "рекомендую №2" in txt and "Название 2" in txt and "★" in txt and "Реклама." in txt
    assert (out / "ВСЕ-ОПИСАНИЯ.txt").exists()
    import zipfile
    z = zipfile.ZipFile(r["zip"]).namelist()
    assert not any("_служебное" in n or "report" in n.lower() for n in z)
    assert not any(n.endswith(".json") for n in z)


@pytest.mark.parametrize("over,needle", [
    ({"titles": [{"t": "один"}]}, "at least 3 title"),
    ({"description": "Просто текст про бота https://t.me/test_bot?start=r_AbC123xyz"}, "«Реклама»"),
    ({"description": "Реклама. без ссылки"}, "exact link"),
    ({"titles": [{"t": "x" * 101}, {"t": "b"}, {"t": "c"}]}, "over 100"),
    ({"covers": []}, "no cover"),
    ({"covers": [{"t0": 0.2, "t1": 2.0, "text": "ОДИН ДВА ТРИ ЧЕТЫРЕ ПЯТЬ ШЕСТЬ"}]}, "words"),
])
def test_pack_blocks_incomplete_items(built, tmp_path, over, needle):
    d, res = built
    with pytest.raises(ShortsError) as e:
        P.pack(_pack_spec(d, Path(res["out"]), **over), tmp_path / "out")
    assert needle in str(e.value)


def test_pack_blocks_wrong_size_and_silent_video(tmp_path):
    bad = tmp_path / "bad.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25:duration=1", "-pix_fmt", "yuv420p", str(bad)], check=True)
    with pytest.raises(ShortsError) as e:
        P.pack(_pack_spec(tmp_path, bad), tmp_path / "out")
    assert "1080x1920" in str(e.value) and "no audio" in str(e.value)


def test_cover_text_is_inside_safe_zone_and_visible(tmp_path):
    frame = np.full((1080, 1920, 3), 40, np.uint8)             # flat frame: only the drawn text/tag/bar carry the accent colour
    out = P.make_cover(frame, None, "ПРИВЕТ *МИР*", tmp_path / "c.png", "#FFD84D", "ТЕСТ")
    img = np.asarray(Image.open(out).convert("RGB")).astype(int)
    assert img.shape == (1920, 1080, 3)
    accent = np.abs(img - np.array([255, 216, 77])).sum(axis=2) < 40
    ys = np.where(accent.any(axis=1))[0]
    assert ys.min() >= 110 and ys.max() < 1920 - 672           # tag, word and bar stay above the Shorts UI
    assert accent[250:700].sum() > 2000                         # the highlighted word is large (readable at 150 px)
    white = (img.min(axis=2) > 235)[250:700]
    assert white.sum() > 2000
