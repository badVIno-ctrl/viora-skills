"""2.4 brand.md: the user's style in one text file (colours, fonts, motion rules), thrown into the chat at the start.

  brand-md template [-o brand.md]       empty brand.md to fill in (Russian headings, English keys work too)
  brand-md import brand.md [-o DIR]     -> DIR/brand.json (plan "brand": {"preset": "DIR/brand.json"}),
                                           DIR/brand.css (CSS variables for HTML / canvas scenes), DIR/brand.md (copy)
  brand-md show [brand.md]              what was understood: palette, fonts, motion rules

Default DIR = memory/brand (kept between videos, git-ignored with the rest of memory). The agent reads the motion
rules from brand.md before writing scene code and follows them (durations, easing, what never moves).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .config import memory_dir, skill_root
from .util import ShortsError

TEMPLATE = """# Бренд

## Цвета
- фон: #0B0B0B
- текст: #F2F2F2
- акцент: #FF5A1F

## Шрифты
- заголовки: Montserrat ExtraBold
- текст: Manrope SemiBold

## Движение
- входы 300-500 мс, выходы короче входов
- easing: cubic-bezier(0.16, 1, 0.3, 1)
- главный акцент один раз за сцену, на сильную долю
- без свечения, без градиентов, без тряски текста
- логотип не двигается

## Голос и музыка
- голос: м, 32, m4
- музыка: tech (или конкретный трек)
"""

ROLE_WORDS = {
    "bg": ("фон", "background", "bg", "подлож", "base"),
    "fg": ("текст", "text", "fg", "foreground", "основной цвет текста", "шрифт цвет", "ink"),
    "accent": ("акцент", "accent", "главный", "primary", "brand", "фирмен", "highlight", "cta"),
}
BUNDLED = {
    "montserrat": ("assets/fonts/Montserrat-ExtraBold.ttf", "assets/fonts/Montserrat-SemiBold.ttf"),
    "manrope": ("assets/fonts/Manrope-Bold.ttf", "assets/fonts/Manrope-SemiBold.ttf"),
    "jost": ("assets/fonts/Jost-Medium.ttf", "assets/fonts/Jost-Light.ttf"),
    "oswald": ("assets/fonts/Oswald-Bold.ttf", "assets/fonts/Oswald-Bold.ttf"),
    "jetbrains mono": ("assets/fonts/JetBrainsMono-Bold.ttf", "assets/fonts/JetBrainsMono-Medium.ttf"),
    "pt serif": ("assets/fonts/PTSerif-Bold.ttf", "assets/fonts/PTSerif-Bold.ttf"),
    "unbounded": ("assets/fonts/Unbounded-Black.ttf", "assets/fonts/Unbounded-Black.ttf"),
    "great vibes": ("assets/fonts/GreatVibes-Regular.ttf", "assets/fonts/GreatVibes-Regular.ttf"),
}
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def default_dir() -> Path:
    return memory_dir() / "brand"


def _sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"": []}
    cur = ""
    for line in text.splitlines():
        h = re.match(r"\s{0,3}#{1,6}\s*(.+?)\s*#*\s*$", line)
        if h:
            cur = h.group(1).strip().lower()
            out.setdefault(cur, [])
            continue
        if line.strip():
            out.setdefault(cur, []).append(line.strip().lstrip("-*•").strip())
    return out


def _sec(secs: dict[str, list[str]], *keys: str) -> list[str]:
    rows: list[str] = []
    for name, lines in secs.items():
        if any(k in name for k in keys):
            rows += lines
    return rows


def _full_hex(h: str) -> str:
    h = h.upper()
    return "#" + "".join(c * 2 for c in h[1:]) if len(h) == 4 else h


def parse(text: str) -> dict:
    """brand.md text -> {palette, extra_colors, fonts, motion, voice, music, notes}."""
    secs = _sections(text)
    color_rows = _sec(secs, "цвет", "color", "colour", "палитр", "palette") or [r for r in sum(secs.values(), []) if HEX.search(r)]
    pal: dict[str, str] = {}
    extra: list[str] = []
    for row in color_rows:
        hexes = HEX.findall(row)
        if not hexes:
            continue
        low = row.lower()
        role = next((r for r, ws in ROLE_WORDS.items() if r not in pal and any(w in low for w in ws)), None)
        if role:
            pal[role] = _full_hex(hexes[0])
            extra += [_full_hex(h) for h in hexes[1:]]
        else:
            extra += [_full_hex(h) for h in hexes]
    for role in ("bg", "fg", "accent"):
        if role not in pal and extra:
            pal[role] = extra.pop(0)
    font_rows = _sec(secs, "шрифт", "font", "типограф", "typograph")
    fonts: dict[str, str] = {}
    for row in font_rows:
        low = row.lower()
        name = re.split(r"[:=\u2014\u2013-]\s*", row, maxsplit=1)[-1].strip() if re.search(r"[:=]", row) else row
        if any(w in low for w in ("заголов", "display", "heading", "title", "акцидент")):
            fonts.setdefault("display", name)
        elif any(w in low for w in ("текст", "body", "основн", "text")):
            fonts.setdefault("body", name)
        else:
            fonts.setdefault("display" if "display" not in fonts else "body", name)
    motion = _sec(secs, "движен", "motion", "анимац", "animation", "моушн")
    vm = _sec(secs, "голос", "voice", "музык", "music", "звук", "sound")
    voice = next((re.split(r"[:=]\s*", r, maxsplit=1)[1] for r in vm if re.match(r"(голос|voice)\s*[:=]", r, re.I)), None)
    music = next((re.split(r"[:=]\s*", r, maxsplit=1)[1] for r in vm if re.match(r"(музыка|music)\s*[:=]", r, re.I)), None)
    ease = next((m.group(0) for r in motion for m in [re.search(r"cubic-bezier\([^)]*\)", r)] if m), None)
    durs = [int(x) for r in motion for x in re.findall(r"(\d{2,4})\s*(?:мс|ms)", r)]
    return {"palette": pal, "extra_colors": extra[:6], "fonts": fonts, "motion": motion, "ease": ease,
            "durations_ms": sorted(set(durs))[:6], "voice": voice, "music": music}


def _font_file(name: str | None, kind: str) -> tuple[str | None, str | None]:
    if not name:
        return None, None
    low = name.lower()
    for fam, (disp, body) in BUNDLED.items():
        if fam in low:
            return (disp if kind == "display" else body), None
    return None, f"font \"{name}\" is not bundled: put its .ttf (with Cyrillic and an embedding licence) next to brand.json"


def to_css(b: dict) -> str:
    p = b["palette"]
    lines = [":root {"]
    for k, var in (("bg", "--bg"), ("fg", "--fg"), ("accent", "--accent")):
        if p.get(k):
            lines.append(f"  {var}: {p[k]};")
    for i, c in enumerate(b.get("extra_colors") or [], 1):
        lines.append(f"  --c{i}: {c};")
    if b.get("ease"):
        lines.append(f"  --ease: {b['ease']};")
    for i, d in enumerate(b.get("durations_ms") or [], 1):
        lines.append(f"  --dur-{i}: {d}ms;")
    lines.append("}")
    for kind in ("display", "body"):
        f = (b.get("font_files") or {}).get(kind)
        if f:
            lines.append(f"@font-face {{ font-family: {'Display' if kind == 'display' else 'Body'}; src: url(\"{f}\"); }}")
    if b.get("motion"):
        lines.append("/* motion rules (brand.md):")
        lines += [f"   - {m.replace('*/', '')}" for m in b["motion"]]
        lines.append("*/")
    return "\n".join(lines) + "\n"


def import_md(src: str | Path, out_dir: str | Path | None = None) -> dict:
    sp = Path(src)
    if not sp.exists():
        raise ShortsError(f"brand.md not found: {src}")
    text = sp.read_text(encoding="utf-8")
    b = parse(text)
    if not b["palette"]:
        raise ShortsError("brand.md has no colours (#RRGGBB): add lines like \"- фон: #0B0B0B\"")
    out = Path(out_dir) if out_dir else default_dir()
    out.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    fonts, files = {}, {}
    for kind in ("display", "body"):
        rel, warn = _font_file(b["fonts"].get(kind), kind)
        if rel:
            fonts[kind] = str((skill_root() / rel).resolve())
            files[kind] = (skill_root() / rel).resolve().as_uri()
        if warn:
            warnings.append(warn)
    if len({v for v in b["palette"].values()}) < 3:
        warnings.append("fewer than 3 colours: the preset fills the rest (mono)")
    if b["extra_colors"]:
        warnings.append(f"{len(b['extra_colors'])} extra colour(s) kept only in brand.css (--c1...): the video rules allow 3 base colours")
    bj = {"name": sp.stem, "base": "mono", "palette": b["palette"], "upper": True,
          "source": "brand.md (shorts.py brand-md import)"}
    if fonts:
        bj["fonts"] = dict(fonts)
        bj["fonts"].setdefault("logo", fonts.get("display") or fonts.get("body"))
        for k in ("display", "body"):
            bj["fonts"].setdefault(k, fonts.get("display") or fonts.get("body"))
    if b["motion"]:
        bj["motion"] = b["motion"]
    (out / "brand.json").write_text(json.dumps(bj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    b["font_files"] = files
    (out / "brand.css").write_text(to_css(b), encoding="utf-8")
    if sp.resolve() != (out / "brand.md").resolve():
        shutil.copyfile(sp, out / "brand.md")
    return {"dir": str(out), "brand_json": str(out / "brand.json"), "brand_css": str(out / "brand.css"),
            "palette": b["palette"], "fonts": b["fonts"], "motion": b["motion"], "voice": b["voice"], "music": b["music"],
            "warnings": warnings,
            "use": {"plan": {"brand": {"preset": str(out / "brand.json")}},
                    "html": "copy brand.css next to scene.html (code-new --brand does it)",
                    "voice": b["voice"], "music": b["music"]}}


def show(src: str | Path | None = None) -> dict:
    p = Path(src) if src else default_dir() / "brand.md"
    if not p.exists():
        return {"found": False, "hint": "no brand.md yet: `brand-md template -o brand.md`, fill it, `brand-md import brand.md`"}
    return {"found": True, "file": str(p), **parse(p.read_text(encoding="utf-8"))}
