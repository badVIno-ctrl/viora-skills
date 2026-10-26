"""2.2 (review of the delivered shorts): speech boundaries, ad slot, caption styles, covers, sound policy.

1. the ad card covered the speaker      -> adslot.resolve gives it its own slot
2. the video ended on "...тогда в личке" -> speech.snap_pieces / check_pieces, stack ends after the last word
3. raw covers (pill tag, underline)      -> covers2.render: no tag by default, text off the face
4. captions                              -> capstyle: clean / aesthetic, off faces and off the card
5. synthesized "bells" in the edit       -> audio.sfx_policy, no tonal synthesis, edits need a real track
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from shortskit import adslot, capstyle, covers2, speech, subs
from shortskit import stack as S
from shortskit.engine import audio as A
from shortskit.util import ShortsError


def _w(w, s, e):
    return {"w": w, "s": s, "e": e}


# "...тогда в личке" is NOT the end of the thought: the speaker goes on "напишу подробно."
WORDS = [_w("Короче", 0.20, 0.60), _w("я", 0.65, 0.75), _w("написал", 0.80, 1.30), _w("ему.", 1.35, 1.80),
         _w("Если", 2.60, 2.90), _w("что,", 2.95, 3.30), _w("тогда", 3.35, 3.70), _w("в", 3.75, 3.82),
         _w("личке", 3.85, 4.30), _w("напишу", 4.35, 4.90), _w("подробно.", 4.95, 5.70), _w("Вот", 6.60, 6.90)]


def _speech_signal(words, total=8.0, sr=16000):
    rng = np.random.default_rng(0)
    x = rng.normal(0, 0.001, int(total * sr)).astype(np.float32)
    for w in words:
        a, b = int(w["s"] * sr), int(w["e"] * sr)
        x[a:b] += rng.normal(0, 0.3, b - a).astype(np.float32)
    return x


ENV = speech.envelope_of(_speech_signal(WORDS), 16000, 0.0)


def _snap(pieces, words=WORDS, mode="sentence", durations=None):
    return speech.snap_pieces(pieces, lambda src, a, b: [w for w in words if a <= w["s"] <= b],
                              lambda src, a, b: ENV, mode, durations)


def _inside_any(t, words, pad=0.02):
    return [w["w"] for w in words if w["s"] + pad < t < w["e"] - pad]


# ------------------------------------------------------------------ 2. speech boundaries

def test_end_inside_a_word_moves_to_the_end_of_the_sentence_with_a_tail():
    out, rep = _snap([{"src": "a.mp4", "start": 0.1, "end": 4.0}])     # 4.0 = inside "личке", sentence goes on
    end = out[0]["end"]
    assert end >= 5.70 + speech.MIN_TAIL_END                            # after "подробно." with a real tail
    assert end < 6.60                                                  # but not into the next sentence
    assert "forward" in rep[0]["end"]
    assert not [p for p in speech.check_pieces(out) if p["level"] == "error"]


def test_start_inside_a_sentence_moves_to_its_start():
    out, rep = _snap([{"src": "a.mp4", "start": 3.0, "end": 5.8}])     # 3.0 = inside "что,"
    assert 1.80 <= out[0]["start"] <= 2.60 - 0.02                      # before "Если", after "ему."
    assert rep[0]["start"]


def test_join_never_cuts_a_word_and_lands_on_a_sentence_end():
    out, _ = _snap([{"src": "a.mp4", "start": 0.1, "end": 3.5}, {"src": "a.mp4", "start": 6.5, "end": 6.95}])
    a = out[0]
    assert not _inside_any(a["end"], WORDS) and not _inside_any(a["start"], WORDS)
    last = [w for w in a["_words"]][-1]
    assert last["w"].endswith(".")                                     # "ему." or "подробно."
    assert not [p for p in speech.check_pieces(out) if "mid-sentence" in p["what"] and p["piece"] == 0]


def test_check_pieces_reports_the_2_1_cut():
    """The 2.1 behaviour (no snapping): the video stops inside "личке", mid-sentence, without a tail."""
    probs = speech.check_pieces([{"src": "a.mp4", "start": 0.1, "end": 4.0, "_ctx": WORDS}])
    whats = " | ".join(p["what"] for p in probs if p["level"] == "error")
    assert "ends inside the word 'личке'" in whats
    assert "mid-sentence" in whats or "after the last word" in whats
    open_end = speech.check_pieces([{"src": "a.mp4", "start": 0.1, "end": 4.0, "_ctx": WORDS}], allow_open_end=True,
                                   mode="word")
    assert any("inside the word" in p["what"] for p in open_end)       # an open end is allowed, a cut word never


def test_edited_speech_without_full_stops_ends_at_a_phrase_pause():
    """Jump-cut monologue (no pauses, only commas): the nearest phrase end is used and it is a warning, not a dead end."""
    ws = [_w("выделять", 0.0, 0.5), _w("акцентные", 0.5, 1.1), _w("слова,", 1.1, 1.6), _w("небесящей", 1.9, 2.6),
          _w("анимации", 2.6, 3.1), _w("располагать", 3.1, 3.8), _w("субтитры", 3.8, 4.3), _w("в", 4.3, 4.4),
          _w("разных", 4.4, 4.9), _w("местах", 4.9, 5.5), _w("и", 5.5, 5.6), _w("пару", 5.6, 6.0),
          _w("слов", 6.0, 6.4), _w("выделить", 6.4, 7.0), _w("рукописным", 7.0, 7.7), _w("шрифтом", 7.7, 8.3),
          _w("вы", 8.3, 8.5), _w("спросите", 8.5, 9.0)]                  # speech runs on past the search window
    env = speech.envelope_of(_speech_signal(ws, 9.5), 16000, 0.0)
    out, rep = speech.snap_pieces([{"src": "a.mp4", "start": 0.0, "end": 2.0}],
                                  lambda src, a, b: [w for w in ws if a <= w["s"] <= b], lambda src, a, b: env)
    assert "pause after 'слова,'" in rep[0]["end"]
    audible = out[0].get("mute_from", out[0]["end"])               # the picture runs on, the sound fades before "небесящей"
    assert not _inside_any(audible, ws) and audible <= 1.9 and out[0]["end"] - 1.6 >= speech.MIN_TAIL_END
    probs = speech.check_pieces(out)
    assert probs and all(p["level"] == "warn" for p in probs)
    hints = speech.end_hints(ws, 3.5)
    assert "слова," in hints or "местах" in hints


def test_word_mode_only_avoids_cutting_words():
    out, _ = _snap([{"src": "a.mp4", "start": 0.1, "end": 3.5}, {"src": "a.mp4", "start": 6.5, "end": 6.95}], mode="word")
    assert not _inside_any(out[0]["end"], WORDS)
    assert out[0]["end"] < 4.0                                         # no sentence extension in word mode


def test_end_past_the_source_becomes_a_held_frame():
    out, rep = _snap([{"src": "a.mp4", "start": 0.1, "end": 5.5}], durations={"a.mp4": 5.9})
    assert out[0]["end"] <= 5.9 and out[0].get("hold", 0) > 0.04
    assert "held" in rep[0]["end"]


def test_align_text_keeps_srt_text_and_takes_whisper_times():
    text = speech.words_from_srt([(0.0, 2.0, "Короче я написал ему")])
    out = speech.align_text(text, WORDS[:4])
    assert [w["w"] for w in out] == ["Короче", "я", "написал", "ему"]
    assert [(w["s"], w["e"]) for w in out] == [(w["s"], w["e"]) for w in WORDS[:4]]
    assert not any(w.get("approx") for w in out)


def test_sentence_end_without_punctuation_uses_pauses():
    ws = [_w("тогда", 0.0, 0.3), _w("в", 0.35, 0.4), _w("личке", 0.45, 0.9), _w("и", 1.0, 1.1), _w("всё", 1.2, 1.5),
          _w("дальше", 2.4, 2.8)]
    assert not speech.sentence_end(ws, 2)        # "...личке | и" - a conjunction runs on
    assert speech.sentence_end(ws, 4)            # 0.9 s pause


def test_youtube_word_sidecar_next_to_the_srt(tmp_path):
    srt = tmp_path / "a.srt"
    side = subs.write_words_sidecar([(10.0, "привет"), (10.4, "мир"), (12.0, "ещё")], 10.0, 13.0, srt)
    rows = json.loads(side.read_text(encoding="utf-8"))
    assert side.name == "a.words.json" and [r["w"] for r in rows] == ["привет", "мир", "ещё"]
    assert rows[0]["s"] == 0.0 and rows[0]["e"] <= 0.4 and all(r["e"] > r["s"] for r in rows)
    assert speech.sidecar_words(srt) == rows


# ------------------------------------------------------------------ 1. ad slot

CARD = (760, 320)


def test_card_goes_under_the_speaker_not_over_it():
    """The Morgenshtern layout: gameplay 0-480 on top, the card used to sit at 900-1240 over the speaker."""
    lay = adslot.resolve({"main": {"pieces": []}, "top": {"h": 480}, "banner": {}}, CARD)
    x, y, w, h = lay["card"]
    assert lay["slot"] == "below" and not adslot.overlap(lay["card"], lay["main"])
    assert y + h <= adslot.visible_bottom(lay) and lay["main"][3] >= adslot.MIN_MAIN     # 2.3: organic tray (480 px)
    assert lay["top"][3] >= adslot.MIN_TOP
    assert adslot.check(lay) == []


def test_manual_y_over_the_speaker_is_ignored_with_a_note():
    lay = adslot.resolve({"main": {"pieces": []}, "top": {"h": 480}, "banner": {"y": 900}}, CARD)
    assert lay["slot"] != "manual" and not adslot.overlap(lay["card"], lay["main"])
    assert any("covered the main picture" in n for n in lay["notes"])


def test_over_video_is_kept_but_a_face_under_the_card_is_a_problem():
    lay = adslot.resolve({"main": {"pieces": []}, "banner": {"y": 900, "over_video": True}}, CARD)
    assert lay["slot"] == "manual" and lay["card"][1] == 900
    face = [400, 950, 200, 220]
    assert any("face is under the card" in p for p in adslot.check(lay, [[face]] * 10))


def test_filler_slot_keeps_the_main_picture_free():
    lay = adslot.resolve({"main": {"pieces": []}, "top": {"h": 540}, "banner": {"slot": "filler"}}, CARD)
    assert lay["slot"] == "filler" and not adslot.overlap(lay["card"], lay["main"])
    assert lay["card"][1] + lay["card"][3] <= lay["top"][3] and lay["card"][1] >= adslot.UI_TOP


def test_every_row_is_covered_by_a_panel_or_a_blurred_fill():
    for spec in ({"main": {"pieces": []}, "top": {"h": 480}, "banner": {}},
                 {"main": {"pieces": [], "y": 150, "h": 1000}, "banner": {}},
                 {"main": {"pieces": []}, "banner": {"slot": "above"}}):
        lay = adslot.resolve(spec, CARD)
        rows = np.zeros(1920, bool)
        for r in [lay["top"], lay["main"], lay["bar"], *lay["fill"]]:
            if r:
                rows[r[1]:r[1] + r[3]] = True
        assert rows.all(), spec


# ------------------------------------------------------------------ 4. captions

SPOKEN = [_w("я", 0.0, 0.1), _w("заработал", 0.15, 0.6), _w("100", 0.7, 1.0), _w("тысяч", 1.05, 1.4),
          _w("долларов.", 1.45, 2.0), _w("Это", 2.8, 3.0), _w("было", 3.05, 3.3), _w("легко.", 3.35, 3.9)]


def test_clean_style_lowercase_one_to_three_words_on_time():
    ch = capstyle.build_chunks(SPOKEN, "clean")
    assert ch and all(1 <= len(c.words) <= 3 for c in ch)
    assert all(w.text == w.text.lower() for c in ch for w in c.words)
    assert all(c.t0 >= c.words[0].s - 0.05 for c in ch)                     # never before the sound
    assert all(a.t1 <= b.t0 + 1e-6 for a, b in zip(ch, ch[1:]))              # one chunk at a time
    assert sum(w.acc for c in ch for w in c.words) >= 1                      # "100" / "долларов" get the accent


def test_karaoke_keeps_the_2_1_caps_look():
    ch = capstyle.build_chunks(SPOKEN, "karaoke")
    assert all(w.text == w.text.upper() for c in ch for w in c.words)


@pytest.mark.parametrize("style", ["clean", "aesthetic"])
def test_captions_never_on_the_face_or_the_card(style):
    zone = (0, 288, 1080, 1248)
    face = (380, 640, 700, 1010)                       # x0 y0 x1 y1, right where the clean style would go
    card = (112, 912, 872, 1232)
    tr = capstyle.CaptionTrack(SPOKEN, {"style": style}, zone, lambda a, b: [face], [(card, 0.0, 10.0)])
    core = capstyle._core(face)
    for t0, t1, (x, y, w, h) in tr.rects():
        r = (x, y, x + w, y + h)
        assert capstyle._ov(r, core) == 0, (style, r)
        assert capstyle._ov(r, card) == 0, (style, r)
        assert zone[1] <= y and y + h <= zone[3]


def test_tight_split_screen_panel_never_pushes_captions_onto_the_card():
    """e2e on real footage: a 560 px speaker panel (close-up) under a gameplay panel, card right below. 2.2.0-dev put a
    two-line 100 px chunk half over the card; now: compact one line, inside the panel or on the seam, off the face."""
    zone = (40, 328, 1040, 888)
    face = (300, 380, 780, 860)                        # the face fills the panel
    card = (100, 900, 884, 1244)
    seam = [(40, 170, 1040, 438)]
    tr = capstyle.CaptionTrack(SPOKEN, {"style": "clean"}, zone, lambda a, b: [face], [(card, 0.0, 10.0)], extra=seam)
    assert tr.compact and tr.st["lines"] == 1 and tr.st["size"] <= 86
    core = capstyle._core(face)
    for ch in tr.chunks:
        r = (ch.x, ch.y, ch.x + ch.bw, ch.y + ch.bh)
        assert capstyle._ov(r, card) == 0, r
        assert capstyle._ov(r, core) == 0, r
        inside = [z for z in [zone] + seam if z[0] <= r[0] and r[2] <= z[2] and z[1] <= r[1] and r[3] <= z[3]]
        assert inside, r
        assert len({w.y for w in ch.words}) == 1                       # one line


def test_explicit_size_keeps_two_lines_even_in_a_small_panel():
    tr = capstyle.CaptionTrack(SPOKEN, {"style": "clean", "size": 100}, (40, 328, 1040, 888), lambda a, b: [], [])
    assert not tr.compact and tr.st["lines"] == 2


def test_source_cut_off_on_a_preposition_is_not_a_sentence_end():
    """VOuZ reference: the file ends on 'а они уже ждут вас в...' - whisper's '...' after 'в' is a cut, not a stop."""
    ws = [_w("с", 14.88, 14.96), _w("субтитром,", 14.96, 15.42), _w("а", 15.78, 15.84), _w("они", 15.84, 16.02),
          _w("уже", 16.02, 16.2), _w("ждут", 16.2, 16.56), _w("вас", 16.56, 16.7), _w("в...", 16.7, 16.82)]
    assert speech.cut_off("в...") and speech.cut_off("and\u2026") and not speech.cut_off("личке.")
    assert not speech.sentence_end(ws, len(ws) - 1) and not speech.phrase_end(ws, len(ws) - 1)
    end, why, mute = speech.snap_end(16.83, ws, None, last=True)
    assert "субтитром" in why and mute is not None and mute < 15.78          # the sound never says "а они..."
    p = [{"src": "x", "start": 14.88, "end": end, "mute_from": mute, "_ctx": ws}]
    probs = speech.check_pieces(p, "sentence")
    assert probs and all(q["level"] == "warn" for q in probs)


def test_last_known_word_without_a_full_stop_is_not_a_sentence_end_in_punctuated_text():
    ws = [_w("Привет.", 0.0, 0.5), _w("Сегодня", 0.8, 1.2), _w("мы", 1.25, 1.4), _w("идём", 1.45, 1.9)]
    assert not speech.sentence_end(ws, 3)
    assert speech.sentence_end([_w("привет", 0.0, 0.5), _w("мир", 0.6, 1.0)], 1)       # no punctuation: a guess


def test_music_under_the_voice_at_a_clean_join_is_a_note_not_a_problem(tmp_path):
    sr = 16000
    rng = np.random.default_rng(1)
    x = (rng.normal(0, 0.05, 4 * sr)).astype(np.float32)              # a steady bed: the level never drops
    x[: sr // 2] *= 0.01
    wav = tmp_path / "a.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    p = {"start": 0.0, "end": 2.0, "_ctx": [_w("раз.", 1.2, 1.7)]}
    q = {"start": 5.0, "end": 7.0, "_ctx": [_w("Два", 5.1, 5.5)]}
    assert speech.join_is_clean(p, q) is True
    assert speech.join_is_clean(dict(p, end=1.5), q) is False            # "раз." would be cut
    qa = speech.audio_qa(wav, [2.0], 4.0, [True])
    assert not any("join" in m for m in qa["problems"]) and qa.get("notes")
    qa = speech.audio_qa(wav, [2.0], 4.0, [None])
    assert any("join" in m for m in qa["problems"])


def test_unknown_caption_style_is_an_error():
    with pytest.raises(ValueError):
        capstyle.CaptionTrack(SPOKEN, {"style": "neon"}, (0, 288, 1080, 1248), lambda a, b: [], [])


def test_headline_hook_and_numbers_that_never_split():
    im = capstyle.headline_layer("БОЛЬШЕ $100 000 ЗА *интервью*", 96, "#FFD84D")
    a = np.array(im)[..., 3]
    assert im.size[0] == 1080 and a.max() == 255
    words = covers2.parse_marked("БОЛЬШЕ *$100 000*?")
    assert ("$100\u00a0000?", True) in words


# ------------------------------------------------------------------ 3. covers

def _frame():
    rng = np.random.default_rng(3)
    img = (rng.normal(110, 25, (1080, 1920, 3))).clip(0, 255).astype(np.uint8)
    img[300:760, 820:1120] = (90, 120, 190)            # the "person"
    return img, [(860, 330, 220, 260)]                 # x, y, w, h


def test_cover_has_no_pill_tag_and_no_text_on_the_face():
    fr, faces = _frame()
    im, info = covers2.render(fr, faces, "ОДИН *НЕИЗВЕСТНЫЙ*", "A", None, "ИНТЕРВЬЮ")
    assert im.size == (1080, 1920)
    assert info["tag"] == "ignored" and not info["text_on_face"]
    assert info["text_bbox"][3] <= covers2.TEXT_BOTTOM


def test_cover_tag_only_on_request_and_script_word():
    fr, faces = _frame()
    _, info = covers2.render(fr, faces, "ДЕНЬГИ ЗА", "B", None, "интервью", script="интервью", tag_style="kicker")
    assert info["tag"] == "kicker" and not info["text_on_face"]


def test_three_variants_really_differ():
    fr, faces = _frame()
    ims = [covers2.render(fr, faces, "БОЛЬШЕ *$100 000*?", v)[0] for v in "ABC"]
    assert covers2.distinct(ims) == []


def test_cover_text_limit():
    fr, faces = _frame()
    with pytest.raises(ShortsError):
        covers2.render(fr, faces, "ОДИН ДВА ТРИ ЧЕТЫРЕ ПЯТЬ ШЕСТЬ", "A")


# ------------------------------------------------------------------ 5. sound

def test_sfx_policy_plays_only_real_recordings(tmp_path, monkeypatch):
    lib = tmp_path / "audio" / "sfx"
    lib.mkdir(parents=True)
    A._write_wav(lib / "whoosh.wav", np.zeros((4800, 2), np.float32) + 0.01)
    monkeypatch.setattr(A, "asset", lambda rel: tmp_path / rel)
    ev = [(0.5, "riser"), (1.0, "hit"), (2.0, "whoosh"), (3.0, "click")]
    kept, rep = A.sfx_policy(ev, {})
    assert kept == [(2.0, "whoosh")] and rep["mode"] == "files"
    assert {d["name"] for d in rep["dropped"]} == {"riser", "hit", "click"}
    kept, rep = A.sfx_policy(ev, {"sfx": "synth"})
    assert [n for _, n in kept] == ["whoosh", "click"] and rep["synthetic"] == ["click"]   # tonal ones still dropped
    assert A.sfx_policy(ev, {"sfx": "off"})[0] == []
    with pytest.raises(ShortsError):
        A.sfx_policy(ev, {"sfx": "bells"})


def test_no_tonal_synthesis_and_noise_click():
    for n in A.TONAL:
        with pytest.raises(ShortsError):
            A.synth_sfx(n)
    x = A.synth_sfx("click")
    spec = np.abs(np.fft.rfft(x))
    peak = spec.max() / (spec.mean() + 1e-9)
    assert peak < 40                                  # broadband noise, no ringing tone


def test_builtin_music_is_flagged_and_edits_need_a_real_track():
    from shortskit.adapters import edit2 as E2
    from shortskit.qa import gate as G

    assert A.music_is_synthetic("assets/audio/edit.mp3") and A.music_is_synthetic("assets/audio/bed.mp3")
    assert not A.music_is_synthetic("/music/track.mp3")
    with pytest.raises(ShortsError):
        E2.need_music(None)
    assert E2.need_music("builtin") == (E2.DEFAULT_MUSIC, True)
    legacy = G.audio_check({"sfx": [{"t": 4.7, "name": "riser"}, {"t": 5.0, "name": "hit"}]})
    assert legacy.status == "fail"
    now = G.audio_check({"sfx": [], "sfx_policy": {"mode": "files", "kept": 0, "dropped": [], "synthetic": [],
                                                    "music_synthetic": True}})
    assert now.status == "warn"


def test_deliver_blocks_placeholder_music(tmp_path):
    from shortskit import deliver as D

    man = {"sfx": [], "sfx_policy": {"mode": "files", "kept": 0, "dropped": [], "synthetic": [], "music_synthetic": True}}
    probe = {"w": 1080, "h": 1920, "audio": True, "dur": 20.0}
    item = {"title": "Название", "description": "Описание", "_manifest": (man, tmp_path)}
    errs, _ = D.validate(item, 1, probe)
    assert any("заглушка" in e for e in errs)
    errs, _ = D.validate(dict(item, placeholder_audio_ok=True), 1, probe)
    assert not any("заглушка" in e for e in errs)


def test_edit_plan_has_no_synthesized_sfx():
    import inspect

    from shortskit.adapters import edit2 as E2

    src = inspect.getsource(E2.edit_plan)
    for name in ("riser", "\"hit\"", "whoosh"):
        assert name not in src


# ------------------------------------------------------------------ 2. stack end to end

def _speech_source(path: Path, words, total=8.0):
    sr = 48000
    x = _speech_signal(words, total, sr)
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    wav = path.with_suffix(".wav")
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=25:duration={total}",
                    "-i", str(wav), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
                   check=True)


def test_stack_ends_after_the_last_word_not_on_it(tmp_path):
    _speech_source(tmp_path / "a.mp4", WORDS)
    (tmp_path / "words.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    spec = {"out": "s.mp4", "fps": 25,
            "main": {"pieces": [{"src": "a.mp4", "start": 0.1, "end": 4.0}], "words_json": "words.json"}}
    res = S.render_stack(spec, tmp_path, check=False)
    sp = res["speech"]
    assert sp["words"] == ["words_json"] and not [p for p in sp["problems"] if p["level"] == "error"]
    end = sp["pieces"][-1]["end"]
    assert end >= 5.70 + speech.MIN_TAIL_END and res["duration"] >= 5.6
    assert sp["audio_qa"].get("ok", True)
    side = json.loads((tmp_path / "s.layout.json").read_text(encoding="utf-8"))
    assert side["speech"]["adjustments"][0]["end"]


def test_stack_refuses_a_cut_it_cannot_fix(tmp_path):
    words = [_w(f"слово{i}", 0.2 + 0.5 * i, 0.6 + 0.5 * i) for i in range(14)]      # no pause, no full stop
    _speech_source(tmp_path / "b.mp4", words)
    (tmp_path / "w.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    spec = {"out": "s.mp4", "fps": 25,
            "main": {"pieces": [{"src": "b.mp4", "start": 0.1, "end": 3.0}], "words_json": "w.json"}}
    with pytest.raises(ShortsError, match="speech boundaries"):
        S.render_stack(spec, tmp_path, check=False)
    spec["main"]["allow_open_end"] = True                # a deliberate cliffhanger is allowed
    res = S.render_stack(spec, tmp_path, check=False)
    assert res["duration"] > 2.5
