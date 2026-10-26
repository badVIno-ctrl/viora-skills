"""2.4 commands: VoiceEngine voice-over, music "auto" (YouTube), code video (template, effects, brand.md)."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from .util import ShortsError


def _attrs(a) -> str:
    parts = [a.attrs] if a.attrs else []
    parts += [x for x in (a.gender, str(a.age) if a.age else None) if x]
    if a.voice:
        parts.append(a.voice if re.fullmatch(r"[mfмж]\d", a.voice, re.I) or "=" in a.voice or a.voice in _alias_names()
                     else f"voice={a.voice}")
    parts += [x for x in (a.preset, a.emotion) if x]
    if a.effect:
        parts.append("effect=" + "+".join(e.strip() for e in re.split(r"[,+]", a.effect) if e.strip()))
    for k in ("pitch", "formant"):
        if getattr(a, k):
            parts.append(f"{k}={getattr(a, k)}")
    if a.lang == "auto":
        parts.append("lang=auto")
    return ", ".join(parts)


def _alias_names() -> set[str]:
    from . import voice as V
    return set(V.ALIASES)


def cmd_voice(a) -> int:
    from . import voice as V
    if a.list:
        print(V.list_all())
        return 0
    attrs = _attrs(a)
    if a.describe and not (a.text or a.file or a.script):
        print(V.describe(attrs or None, a.lang if a.lang != "auto" else "ru"))
        return 0
    if V.disabled():
        raise ShortsError("VoiceEngine is off (SHORTS_VOICEENGINE=off)")
    miss = V.deps_missing()
    if miss:
        raise ShortsError("VoiceEngine needs: pip install " + " ".join(miss))
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out if out.suffix.lower() in ("", ".wav") else out.with_suffix(".tmp.wav")
    if a.script:
        script = Path(a.script).read_text(encoding="utf-8")
        r = V.speak_script(script, wav, defaults=attrs or None, lang=None if a.lang == "auto" else a.lang,
                           save_lines=a.save_lines)
    else:
        text = Path(a.file).read_text(encoding="utf-8") if a.file else " ".join(a.text or [])
        if not text.strip():
            raise ShortsError("give the text: shorts.py voice \"ТЕКСТ\" ... (or -f file.txt, -s script.txt)")
        lang = a.lang if a.lang != "auto" else ("ru" if re.search(r"[а-яё]", text, re.I) else "en")
        r = V.speak(text, wav, voice=attrs or None, lang=lang, speed=a.speed)
    final = V.to_file(wav, out)
    if wav != out and wav.exists():
        wav.unlink()
    rep = {"file": str(final), "duration": round(r["duration"], 2), "words": len(r["words"]),
           "timings": "estimated" if r["estimated"] else "exact", "voice": r.get("voice") or attrs or "default"}
    if r.get("warnings"):
        rep["not_recognized"] = r["warnings"]
    if a.srt:
        Path(a.srt).write_text(V.srt(r["words"]), encoding="utf-8")
        rep["srt"] = a.srt
    if a.words:
        Path(a.words).write_text(json.dumps(r["words"], ensure_ascii=False, indent=1), encoding="utf-8")
        rep["words_json"] = a.words
    if a.describe:
        rep["describe"] = V.describe(attrs or None, a.lang if a.lang != "auto" else "ru")
    if r.get("lines"):
        rep["lines"] = r["lines"] if isinstance(r["lines"], list) and len(r["lines"]) < 40 else len(r["lines"])
    print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_voice_setup(a) -> int:
    from . import voice as V
    st = V.status()
    if V.disabled():
        print(json.dumps({"ok": False, **st}, ensure_ascii=False, indent=2))
        return 1
    miss = V.deps_missing()
    if miss:
        print(json.dumps({"ok": False, "missing": miss, "fix": "pip install " + " ".join(miss)}, ensure_ascii=False, indent=2))
        return 1
    d = V.ensure_models()
    rep = {"models": str(d)}
    if not a.no_test:
        rep.update(V.selftest(Path(a.out)))
    else:
        rep["ok"] = True
    print(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
    return 0 if rep.get("ok") else 1


def _target(path: str | None) -> tuple[str, Path | None, dict | None]:
    """--for PATH -> (kind, file, data): plan.json | toon episode (dir or episode.json)."""
    if not path:
        return "none", None, None
    p = Path(path)
    if p.is_dir():
        p = p / "episode.json" if (p / "episode.json").exists() else p / "plan.json"
    if not p.exists():
        raise ShortsError(f"not found: {path}")
    d = json.loads(p.read_text(encoding="utf-8"))
    return ("plan" if "scenes" in d and "layout" in d else "episode"), p, d


def cmd_music_find(a) -> int:
    from . import music as MU
    kind, file, data = _target(a.target)
    ctx, length, voice = a.context or "", a.length, not a.no_voice
    spec: dict = {}
    if kind == "plan":
        spec = dict((data.get("audio") or {}).get("music") or {}) if isinstance((data.get("audio") or {}).get("music"), dict) else {}
        ctx = ctx or MU.plan_context(data)
        dt = (data.get("meta") or {}).get("duration_target")
        length = length or (float(dt[1]) if isinstance(dt, list) and len(dt) == 2 else 30.0)
        voice = voice and any(s.get("say") for s in data.get("scenes") or [])
    elif kind == "episode":
        m = data.get("music")
        spec = dict(m) if isinstance(m, dict) else {}
        ctx = ctx or MU.episode_context(data)
        length = length or float(data.get("duration") or 0) or max(20.0, 3.2 * len(data.get("scenes") or []))
    length = float(length or 30.0)
    mood = a.mood or spec.get("mood")
    genre = a.genre or spec.get("genre")
    query = a.query or spec.get("query")
    out_dir = Path(a.out) if a.out else (file.parent if file else Path("out/music"))
    if a.dry:
        rep = MU.find(length=length, voice=voice, mood=mood, genre=genre, query=query, context=ctx, out_dir=out_dir,
                      lang=a.lang, dry=True)
    else:
        rep = MU.resolve({"source": "auto", "mood": mood, "genre": genre, "query": query}, length=length, voice=voice,
                         context=ctx, base=out_dir, lang=a.lang, force=a.force)
    if a.apply and rep.get("ok") and file is not None:
        rel = Path(rep["file"]).resolve()
        try:
            rel = rel.relative_to(file.parent.resolve())
        except ValueError:
            pass
        if kind == "plan":
            m = dict((data.setdefault("audio", {}).get("music") or {}))
            m = m if isinstance(m, dict) else {}
            for k in ("mood", "genre", "query"):
                m.pop(k, None)
            m.update(source=str(rel), start=rep.get("start", 0.0), credit=rep.get("credit"))
            data["audio"]["music"] = m
        else:
            data["music"] = {"file": str(rel), "start": rep.get("start", 0.0)}
        file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rep["applied_to"] = str(file)
    show = {k: rep.get(k) for k in ("status", "ok", "mood", "track", "file", "start", "drop", "tempo", "credit", "json",
                                    "hint", "local_commands", "pick") if rep.get(k) is not None}
    show["alternatives"] = (rep.get("alternatives") or [])[:4]
    show["summary"] = MU.summary(rep) if not a.dry else f"search only: {len(rep.get('alternatives') or [])} candidates"
    print(json.dumps(show, ensure_ascii=False, indent=2, default=str))
    return 0 if (rep.get("ok") or a.dry and rep.get("status") == "searched") else 1


def cmd_fx_get(a) -> int:
    from . import fxlib as FX
    if a.list or not a.spec:
        print(json.dumps(FX.list_bundled(), ensure_ascii=False, indent=2))
        return 0
    rep = FX.get(a.spec, a.to)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


def cmd_brand_md(a) -> int:
    from . import brandmd as BM
    if a.action == "template":
        if a.output:
            p = Path(a.output)
            if p.exists() and not a.force:
                raise ShortsError(f"{p} exists (use --force)")
            p.write_text(BM.TEMPLATE, encoding="utf-8")
            print(p)
        else:
            print(BM.TEMPLATE)
        return 0
    if a.action == "import":
        if not a.file:
            raise ShortsError("brand-md import FILE")
        rep = BM.import_md(a.file, a.output)
        if not a.output:   # imported into memory: the user's style for every next plan (prefs brand.preset)
            from . import memory as M
            M.set_value("brand.preset", rep["brand_json"])
            if rep.get("voice"):
                cur = M.load().get("voice")
                M.set_value("voice", {"engine": "auto", "speed": 1.05, **(cur if isinstance(cur, dict) else {}),
                                      "voice": rep["voice"]})
            mu = re.sub(r"\s*\(.*?\)", "", str(rep.get("music") or "")).strip()
            if mu:
                from . import music as MU
                if re.match(r"https?://", mu) or Path(mu).suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
                    M.set_value("music", {"source": mu})
                elif MU.is_none(mu):
                    M.set_value("music", {"source": "none"})
                else:   # a mood or a genre: the YouTube search uses it
                    mood = MU.mood_of(mu, default="")
                    M.set_value("music", {"source": "auto", **({"mood": mood} if mood else {"genre": mu})})
            rep["remembered"] = "prefs: brand.preset" + (" + voice" if rep.get("voice") else "") + (" + music" if mu else "")
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(BM.show(a.file), ensure_ascii=False, indent=2))
    return 0


def cmd_code_new(a) -> int:
    """templates/code-video -> DIR: scene.html + plan.json + fonts (+ effects, brand.css). Never overwrites."""
    from . import brandmd as BM
    from . import fxlib as FX
    from .config import skill_root
    root = skill_root()
    dst = Path(a.dir)
    if (dst / "scene.html").exists() and not a.force:
        raise ShortsError(f"{dst}/scene.html exists (use --force)")
    dst.mkdir(parents=True, exist_ok=True)
    tpl = root / "templates" / "code-video"
    for name in ("scene.html", "plan.json", "README.md"):
        shutil.copyfile(tpl / name, dst / name)
    (dst / "fonts").mkdir(exist_ok=True)
    for f in ("Montserrat-ExtraBold.ttf", "Manrope-SemiBold.ttf", "OFL-Montserrat.txt", "OFL-Manrope.txt"):
        shutil.copyfile(root / "assets" / "fonts" / f, dst / "fonts" / f)
    got = []
    for fx in [x for x in re.split(r"[,\s]+", a.fx or "") if x]:
        got.append(FX.get(fx, dst)["name"])
    brand = None
    src = Path(a.brand) if a.brand else (BM.default_dir() / "brand.md")
    if a.brand or src.exists():
        rep = BM.import_md(src, dst / "brand") if src.exists() else None
        if rep:
            shutil.copyfile(rep["brand_css"], dst / "brand.css")
            plan = json.loads((dst / "plan.json").read_text(encoding="utf-8"))
            plan["brand"] = {"preset": "brand/brand.json"}
            if rep.get("voice"):
                plan["audio"]["voice"]["voice"] = rep["voice"]
            if rep.get("music"):
                plan["audio"]["music"]["mood"] = re.sub(r"\s*\(.*?\)", "", rep["music"]).strip()
            (dst / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            brand = rep["brand_json"]
    print(json.dumps({"dir": str(dst), "files": sorted(p.name for p in dst.iterdir()), "fx": got, "brand": brand,
                      "next": ["edit SCENE in scene.html (text, cue words, orb state) and say in plan.json",
                               "open scene.html in a browser to preview (it loops)",
                               f"python3 tools/shorts.py all {dst / 'plan.json'} --out {dst / 'out'}"]},
                     ensure_ascii=False, indent=2))
    return 0


def register(sub) -> None:
    s = sub.add_parser("voice", help="2.4 VoiceEngine: any age / gender / character, emotions, effects, dialogue scripts")
    s.add_argument("text", nargs="*"); s.add_argument("-f", "--file", help="text file"); s.add_argument("-s", "--script", help="dialogue script file")
    s.add_argument("-o", "--output", default="out/voice.wav", help=".wav/.mp3/.m4a/.ogg/.flac")
    s.add_argument("--attrs", help="all in one line: \"ж, 90, шёпотом, voice=Нюра, speed=0.9\"")
    s.add_argument("-g", "--gender"); s.add_argument("-a", "--age", type=float); s.add_argument("-v", "--voice", help="m1..m6, f1..f6, any name, or an old alias")
    s.add_argument("-p", "--preset", help="мультяшка, дракон, ведьма, робот, рассказчик, диктор, ведущая... (--list)")
    s.add_argument("-e", "--emotion", help="радостно, восторженно, грустно, сердито, испуганно, спокойно, устало, торжественно, шёпотом")
    s.add_argument("--effect", help="phone, radio, cave, echo, robot, ghost... (a,b)"); s.add_argument("--speed", type=float, default=1.0)
    s.add_argument("--pitch", type=float); s.add_argument("--formant", type=float)
    s.add_argument("--lang", default="auto", choices=["auto", "ru", "en"]); s.add_argument("--srt"); s.add_argument("--words", help="words.json")
    s.add_argument("--save-lines", help="script: each line also as its own file in this folder")
    s.add_argument("--list", action="store_true"); s.add_argument("--describe", action="store_true")
    s.set_defaults(fn=cmd_voice)
    s = sub.add_parser("voice-setup", help="2.4: unpack the VoiceEngine models (once, ~10 s) and run the self-test")
    s.add_argument("--out", default="out/voice-selftest"); s.add_argument("--no-test", action="store_true")
    s.set_defaults(fn=cmd_voice_setup)
    s = sub.add_parser("music-find", help="2.4: find a fitting track on YouTube (what render does for music \"auto\")")
    s.add_argument("--for", dest="target", help="plan.json or toon episode dir: mood, length, voice from it")
    s.add_argument("--mood"); s.add_argument("--genre"); s.add_argument("--query"); s.add_argument("--context")
    s.add_argument("--length", type=float); s.add_argument("--no-voice", action="store_true", help="music-led video (no voice-over)")
    s.add_argument("--out"); s.add_argument("--lang", default="ru"); s.add_argument("--apply", action="store_true", help="write the file into the plan / episode")
    s.add_argument("--dry", action="store_true", help="search and rank only"); s.add_argument("--force", action="store_true", help="another search even if music.json exists")
    s.set_defaults(fn=cmd_music_find)
    s = sub.add_parser("fx-get", help="2.4: effect for a code video into DIR/vendor/ (p5.brush, thinking-orbs, GitHub repo, npm:pkg)")
    s.add_argument("spec", nargs="?"); s.add_argument("--to", default="."); s.add_argument("--list", action="store_true")
    s.set_defaults(fn=cmd_fx_get)
    s = sub.add_parser("brand-md", help="2.4: brand.md (colours, fonts, motion rules) -> brand.json + brand.css")
    s.add_argument("action", choices=["template", "import", "show"]); s.add_argument("file", nargs="?")
    s.add_argument("-o", "--output"); s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_brand_md)
    s = sub.add_parser("code-new", help="2.4: code video skeleton (scene.html with seek(t), plan.json, fonts, effects, brand)")
    s.add_argument("dir"); s.add_argument("--fx", default="p5.brush,thinking-orbs", help="comma list, \"\" = none")
    s.add_argument("--brand", help="brand.md (default: memory/brand/brand.md when it exists)"); s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_code_new)


def beats_js(src: str, out: str, start: float = 0.0, length: float | None = None, main: str | None = None) -> dict:
    """beats of a track -> beats.js (window.BEATS) for an html scene; times = track time - start."""
    from .adapters.film import music_beats
    b = music_beats(src)
    end = start + (length or 1e9)
    sh = lambda x: round(float(x) - start, 3)  # noqa: E731
    beats = [sh(x) for x in b.get("beats") or [] if start - 1e-6 <= x <= end]
    downs = [sh(x) for x in b.get("downbeats") or [] if start - 1e-6 <= x <= end]
    rep: dict = {"tempo": round(float(b.get("tempo") or 0), 2), "start": start, "beats": beats, "strong": downs}
    try:
        from .adapters.edit2 import detect_drop
        d = float(detect_drop(b)) - start
        if 0 < d < (length or 1e9):
            rep["drop"] = round(d, 3)
    except Exception:  # noqa: BLE001 - drop is optional
        pass
    if main:
        m = str(main).strip().lower()
        if m == "drop" and "drop" in rep:
            rep["main"] = rep["drop"]
        elif re.fullmatch(r"\d+", m) and beats:
            rep["main"] = beats[min(len(beats) - 1, max(0, int(m) - 1))]       # n-th beat, from 1
        elif re.fullmatch(r"bar\s*\d+", m) and downs:
            rep["main"] = downs[min(len(downs) - 1, max(0, int(m[3:].strip()) - 1))]
        else:
            try:
                rep["main"] = round(float(m.rstrip("s")), 3)                  # seconds
            except ValueError as e:
                raise ShortsError("--main: drop | N (beat number) | barN | seconds") from e
    Path(out).write_text("// shorts.py beats: times in seconds of the video (track time - start)\nwindow.BEATS = "
                         + json.dumps(rep) + ";\n", encoding="utf-8")
    return {"js": out, "tempo": rep["tempo"], "beats": len(beats), "strong": len(downs), "drop": rep.get("drop"),
            "main": rep.get("main")}


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)
