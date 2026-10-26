"""v2.1: fps policy, camera path, lag detector, ad bar QR, covers, subtitles."""
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from shortskit import adbar, covers2, smooth, subs  # noqa: E402


def _src(path: Path, rate=60, secs=4, size="640x360"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={secs}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={secs}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", str(path)], check=True)


def test_pick_fps_keeps_main_picture_untouched():
    assert [smooth.pick_fps(x) for x in (23.976, 25, 29.97, 30, 50, 59.94, 60, 15)] == [24, 25, 30, 30, 25, 30, 30, 30]


def test_resample_filter_blends_only_on_non_integer_ratio():
    assert smooth.resample_filter(60, 30) == "fps=30"
    assert smooth.resample_filter(60, 25).startswith("framerate=")
    assert smooth.resample_filter(25, 25) == "fps=25"


def test_smooth_segment_has_no_steps():
    raw = np.r_[np.full(30, 100.0), np.full(30, 140.0)]
    out = smooth.smooth_segment(raw, 4.0, 3.0)
    assert np.abs(np.diff(out)).max() < 6.0          # a 40 px jump becomes a glide, not a step
    assert abs(out[0] - 100) < 5 and abs(out[-1] - 140) < 5


def test_crop_resize_is_subpixel():
    img = np.random.default_rng(1).integers(0, 255, (360, 640, 3), dtype=np.uint8)
    a = smooth.crop_resize(img, 320.0, 0, 200, 360, 540, 972)
    b = smooth.crop_resize(img, 320.4, 0, 200, 360, 540, 972)
    assert a.shape == (972, 540, 3) and np.abs(a.astype(int) - b.astype(int)).mean() > 0.5   # moves by a fraction, not snapped


def test_motion_report_flags_uneven_resample(tmp_path):
    _src(tmp_path / "s60.mp4", 60, 4)
    bad, good = tmp_path / "bad.mp4", tmp_path / "good.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp_path / "s60.mp4"), "-vf", "fps=25", "-an", str(bad)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp_path / "s60.mp4"), "-vf", "fps=30", "-an", str(good)], check=True)
    assert smooth.motion_report(good)["ok"]
    _src(tmp_path / "s30.mp4", 30, 4)
    dup = tmp_path / "dup.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp_path / "s30.mp4"), "-vf", "fps=60", "-an", str(dup)], check=True)
    assert not smooth.motion_report(dup)["ok"]       # every frame doubled


def test_adbar_qr_decodes_and_text_fits():
    url = "https://t.me/bobvpn_robot?start=ref_5771810401"
    bar = adbar.AdBar({"brand": "Bob VPN", "sub": "VPN в Telegram", "url": url, "accent": "#E5484D"})
    for t in (0.0, 1.0, 2.1):
        fr = bar.frame(t)
        assert fr.shape == (300, 1080, 3)
        assert adbar.qr_decodes(fr, url)
    assert bar.offset(0.1) is not None and bar.offset(1.0) == 0 and bar.offset(-1) is None
    with pytest.raises(Exception):
        adbar.AdBar({"brand": "x"})


def test_logo_actually_animates():
    bar = adbar.AdBar({"brand": "Q", "url": "https://t.me/q?start=1"})
    x, y = bar.logo_xy
    a, b = bar.frame(0.1)[y - 40:y + 160, x - 40:x + 160], bar.frame(1.9)[y - 40:y + 160, x - 40:x + 160]
    assert np.abs(a.astype(int) - b.astype(int)).mean() > 0.3
    q = bar.qr_rect
    assert np.array_equal(bar.frame(0.1)[q[1]:q[1] + q[3], q[0]:q[0] + q[2]], bar.frame(1.9)[q[1]:q[1] + q[3], q[0]:q[0] + q[2]])


def test_vtt_words_to_srt():
    vtt = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nпривет\nпривет<00:00:01.400><c> мир</c><00:00:01.900><c> как</c>\n\n"
           "00:00:03.000 --> 00:00:05.000\nпривет мир как\nдела.<00:00:03.500><c> Хорошо</c>\n")
    w = subs.vtt_words(vtt)
    assert [x[1] for x in w] == ["привет", "мир", "как", "дела.", "Хорошо"]
    srt = subs.words_to_srt(w, 0.0, 10.0)
    assert "привет мир как" in srt and "дела." in srt and "Хорошо" in srt.split("\n\n")[-1]


def test_cover_text_markers_and_distinct():
    assert covers2.parse_marked("один *двор* всех") == [("ОДИН", False), ("ДВОР", True), ("ВСЕХ", False)]
    assert covers2.parse_marked("слово пацана")[-1][1] is True
    a = covers2.Image.new("RGB", (1080, 1920), (10, 10, 10))
    assert covers2.distinct([a, a.copy()])


def test_cover_variants_differ_and_text_avoids_face(tmp_path):
    _src(tmp_path / "v.mp4", 25, 6, "1280x720")
    cap = cv2.VideoCapture(str(tmp_path / "v.mp4"))
    imgs = []
    for i, t in enumerate((0.5, 2.5, 4.5)):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        _, fr = cap.read()
        face = (500.0, 150.0, 140.0, 180.0)
        im, info = covers2.render(fr, [face], "ОДИН *ДВОР*", "ABC"[i])
        assert im.size == (1080, 1920) and not info["text_on_face"]
        imgs.append(im)
    assert not covers2.distinct(imgs, 8)
    with pytest.raises(Exception):
        covers2.render(fr, [], "раз два три четыре пять шесть", "A")


def test_mask_profanity_masks_mat_and_keeps_normal_words():
    from shortskit.subs import mask_profanity
    assert mask_profanity("нахуй приедет трахнет") == "н**** приедет трахнет"
    assert mask_profanity("чтоб долбоёба не вырос") == "чтоб д******* не вырос"
    assert mask_profanity("ребёнок хуже себя гребёт") == "ребёнок хуже себя гребёт"
    assert mask_profanity("ну бля, ебать") == "ну б**, е****"


def test_vtt_words_drops_bleep_and_sound_tags():
    from shortskit.subs import _keep_word
    assert [w for w in ["се", "[", "__", "]", "[Музыка]", ">>", "♪", "выступал"] if _keep_word(w)] == ["се", "выступал"]


def test_best_offset_avoid_gives_a_different_window():
    from shortskit.adapters.edit2 import best_offset
    t = [i / 8 for i in range(40)]
    an = {"t": t, "face_h": [0.4] * 40, "motion": [6.0] * 40, "segments": [(0.0, 5.0)], "dark": [False] * 40}
    o1, _ = best_offset(an, 0.75, 0.5)
    o2, q2 = best_offset(an, 0.75, 0.5, avoid=[(o1, 0.75)])
    assert o2 is not None and abs(o2 - o1) >= 0.75
    taken, _q = [], None
    for _ in range(10):
        o, q = best_offset(an, 0.75, 0.5, avoid=taken)
        if o is None:
            break
        taken.append((o, 0.75))
    assert 3 <= len(taken) <= 6 and q == -1.0
