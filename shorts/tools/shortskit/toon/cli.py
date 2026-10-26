"""toon-* commands: new, catalog, check, build, preview, render, cast."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import time
from pathlib import Path

from ..util import ShortsError
from . import catalog
from .story import build, size_of

TEMPLATES = Path(__file__).resolve().parents[3] / "templates" / "toon"


def templates() -> list[str]:
    return sorted(p.stem for p in TEMPLATES.glob("*.json"))


def _load(path: str | Path) -> tuple[dict, Path]:
    p = Path(path)
    if p.is_dir():
        p = p / "episode.json"
    if not p.exists():
        raise ShortsError(f"no episode file: {p}")
    try:
        ep = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ShortsError(f"{p}: invalid JSON ({e})") from e
    return ep, p.parent


def new(directory: str, template: str = "blackout") -> dict:
    src = TEMPLATES / f"{template}.json"
    if not src.exists():
        raise ShortsError(f"no template {template!r}; templates: {', '.join(templates())}")
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    dst = d / "episode.json"
    if dst.exists():
        raise ShortsError(f"{dst} exists (never overwritten)")
    shutil.copyfile(src, dst)
    return {"episode": str(dst), "template": template,
            "next": [f"edit {dst} (say / set / actors / scheme per scene)", f"python3 tools/shorts.py toon-check {d}",
                     f"python3 tools/shorts.py toon-preview {d}   # look at build/sheet.jpg",
                     f"python3 tools/shorts.py toon-render {d}"]}


def _speaker(ep: dict, silent: bool):
    if silent:
        return None
    from .voice import make_speaker
    return make_speaker(ep)


def build_cmd(path: str, silent: bool = False) -> tuple[dict, dict, dict, Path]:
    ep, base = _load(path)
    story, report = build(ep, _speaker(ep, silent))
    out = base / "build"
    out.mkdir(exist_ok=True)
    (out / "story.json").write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = ["| # | time | dur | words | set / scheme | shot | camera | transition | line |", "|---|---|---|---|---|---|---|---|---|"]
    for r, sc, src in zip(report["timing"], story["scenes"], ep.get("scenes", [])):
        shot = sc.get("shot") or ("-" if sc.get("scheme") and sc["scheme"].get("full", True) else "wide")
        shot = shot if isinstance(shot, str) else shot.get("type", "medium") + "*"
        say = (src.get("say") or "").replace("|", "/")[:60]
        rows.append(f"| {r['scene'] + 1} | {r['t0']:.2f}-{r['t1']:.2f} | {r['dur']:.2f} | {r['words']} | {r['scheme'] or r['set']} | {shot} "
                    f"| {r['camera']} | {r['transition'] or '-'} | {say} |")
    (out / "timing.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    chapters = youtube_chapters(ep, story)
    if chapters:
        (out / "chapters.txt").write_text(chapters, encoding="utf-8")
    return ep, story, report, base


def _mmss(t: float) -> str:
    t = int(round(t))
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def youtube_chapters(ep: dict, story: dict) -> str:
    """Description-ready chapter list: YouTube wants the first one at 00:00, >= 3 chapters, each >= 10 s."""
    marks = []
    for src, sc in zip(ep.get("scenes", []), story["scenes"]):
        ch = src.get("chapter")
        if ch:
            ch = ch if isinstance(ch, dict) else {"text": str(ch)}
            title = (f"{ch['num']}. " if ch.get("num") is not None else "") + str(ch.get("text", "")).strip()
            marks.append([sc["t0"], title])
    if not marks:
        return ""
    if marks[0][0] > 0.5:
        marks.insert(0, [0.0, ep.get("intro_title", "Вступление" if ep.get("lang", "ru") == "ru" else "Intro")])
    marks[0][0] = 0.0
    merged = []
    for t, title in marks:                       # chapters shorter than 10 s are merged into the previous one
        if merged and t - merged[-1][0] < 10:
            continue
        merged.append([t, title])
    return "\n".join(f"{_mmss(t)} {title}" for t, title in merged) + "\n"


def check_cmd(path: str) -> dict:
    from .check import check
    ep, _ = _load(path)
    return check(ep)


def _sheet(frames: list[bytes], labels: list[str], W: int, H: int, out: Path, cols: int | None = None) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    from .render import fonts_dir
    portrait = H >= W
    tw = 270 if portrait else 480
    th = int(tw * H / W)
    cols = cols or (6 if portrait else 4)
    cols = min(cols, len(frames))
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + 34)), (16, 18, 24))
    try:
        f = ImageFont.truetype(str(fonts_dir() / "JetBrainsMono-Bold.ttf"), 15)
    except OSError:
        f = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    for i, (fr, lab) in enumerate(zip(frames, labels)):
        im = Image.open(io.BytesIO(fr)).convert("RGB").resize((tw, th))
        x, y = (i % cols) * tw, (i // cols) * (th + 34)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + th + 8), lab[:34], fill=(235, 235, 235), font=f)
    sheet.save(out, quality=88)
    return out


def preview_cmd(path: str, silent: bool = False, at: float = 0.7) -> dict:
    from . import render
    ep, story, report, base = build_cmd(path, silent)
    times = [s["t0"] + (s["t1"] - s["t0"]) * at for s in story["scenes"]]
    frames = render.snapshots(story, times, base / "build")
    labels = [f"{i + 1} {s['t0']:.1f}s {(s.get('scheme') or {}).get('type') or s['set'].get('id')}" for i, s in enumerate(story["scenes"])]
    sheet = _sheet(frames, labels, story["W"], story["H"], base / "build" / "sheet.jpg")
    from .check import check
    rep = check(ep, story, report)
    return {"sheet": str(sheet), "duration": story["duration"], "scenes": len(story["scenes"]), "ok": rep["ok"],
            "errors": rep["errors"], "warnings": rep["warnings"][:12], "timing": str(base / "build" / "timing.md")}


def render_cmd(path: str, out: str | None = None, draft: bool = False, silent: bool = False, fps: int | None = None,
               workers: int | None = None) -> dict:
    from . import render
    from .check import check
    from .voice import mix_audio, mux
    t_start = time.time()
    ep, story, report, base = build_cmd(path, silent)
    rep = check(ep, story, report)
    if not rep["ok"]:
        raise ShortsError("toon-check errors: " + "; ".join(f"scene {e['scene']}: {e['msg']}" for e in rep["errors"][:5]))
    bdir = base / "build"
    rstory = dict(story)
    if draft:
        rstory["W"], rstory["H"] = story["W"] // 2, story["H"] // 2
    fps = fps or (24 if draft else int(story.get("fps", 30)))
    workers = workers or max(2, min(6, (os.cpu_count() or 4) - 1))
    video = bdir / "video.mp4"

    def progress(k, n):
        print(f"  frames {k}/{n}", file=sys.stderr, flush=True)
    render.render_video(rstory, video, bdir, fps=fps, workers=workers, crf=26 if draft else 18, preset="veryfast" if draft else "fast",
                        progress=progress)
    audio_rep = None
    wav = None
    if not silent and report.get("speech"):
        wav = bdir / "audio.wav"
        audio_rep = mix_audio(story, report, ep, base, wav)
    name = out or (base / ((ep.get("slug") or base.name or "episode") + ("-draft" if draft else "") + ".mp4"))
    final = mux(video, wav, Path(name))
    if audio_rep and (audio_rep.get("music_auto") or {}).get("json"):
        try:  # pack finds the credit next to the video wherever it was written
            Path(final).with_suffix(".music.json").write_text(Path(audio_rep["music_auto"]["json"]).read_text(encoding="utf-8"),
                                                             encoding="utf-8")
        except OSError:
            pass
    cov_t = float((ep.get("cover") or {}).get("t", min(story["scenes"][0]["t1"] - 0.05, 1.2)))
    cover = render.snapshots(story, [cov_t], bdir, q=0.95)[0]
    (base / "cover.jpg").write_bytes(cover)
    times = [s["t0"] + (s["t1"] - s["t0"]) * 0.7 for s in story["scenes"]]
    frames = render.snapshots(rstory, times, bdir)
    labels = [f"{i + 1} {s['t0']:.1f}s {(s.get('scheme') or {}).get('type') or s['set'].get('id')}" for i, s in enumerate(story["scenes"])]
    sheet = _sheet(frames, labels, rstory["W"], rstory["H"], bdir / "sheet.jpg")
    return {"video": str(final), "cover": str(base / "cover.jpg"), "sheet": str(sheet), "duration": story["duration"],
            "fps": fps, "size": [rstory["W"], rstory["H"]], "audio": audio_rep, "warnings": rep["warnings"][:12],
            "seconds": round(time.time() - t_start, 1)}


def cast_cmd(path: str) -> dict:
    """Character sheet: every cast member in key poses and emotions (check the looks before rendering)."""
    from . import render
    ep, base = _load(path)
    cast = ep.get("cast") or {"hero": {"look": "hero"}}
    W, H = 1920, 1080
    poses = ["stand", "point", "scared", "think", "phone", "walk"]
    emos = ["neutral", "happy", "scared", "angry", "sad", "surprised"]
    scenes, labels, t = [], [], 0.0
    for cid, c in cast.items():
        look = c.get("look", cid)
        kind_small = look in ("dog", "dog_tan", "cat")
        acts = []
        for j, p in enumerate(poses):
            acts.append({"id": cid, "look": look, "at": [0.09 + j * 0.165, 0.56], "h": 0.20 if kind_small else 0.4, "pose": "walk" if p == "walk" and kind_small else p,
                         "face": "right" if j % 2 else "front", **({"to": [0.09 + j * 0.165 + 0.02, 0.56]} if p == "walk" else {})})
        for j, e in enumerate(emos):
            acts.append({"id": cid, "look": look, "at": [0.09 + j * 0.165, 0.98], "h": 0.20 if kind_small else 0.4, "pose": "stand", "face": "front", "emotion": e})
        scenes.append({"t0": t, "t1": t + 2, "set": {"id": "plain", "time": "paper"}, "camera": "static", "actors": acts,
                       "hud": [{"type": "label", "text": f"{cid} · {look}", "at": [0.5, 0.06], "color": "white"}]})
        labels.append(f"{cid} ({look})")
        t += 2
    story = {"W": W, "H": H, "fps": 30, "duration": t, "style": {"grain": 0, "vignette": 0, "outline": (ep.get("style") or {}).get("outline", "thin")},
             "cast": cast, "words": [], "scenes": scenes}
    bdir = base / "build"
    frames = render.snapshots(story, [s["t0"] + 1.0 for s in scenes], bdir)
    sheet = _sheet(frames, labels, W, H, bdir / "cast.jpg", cols=1)
    return {"cast_sheet": str(sheet), "members": list(cast)}
