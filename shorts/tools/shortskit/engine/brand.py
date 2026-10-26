"""Brand tokens: preset + plan overrides -> one resolved brand used by every drawing step."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

from ..config import asset, skill_root
from ..util import ShortsError, contrast, fit_contrast, hex_to_rgb, log

PRESETS = ("mono", "editorial", "terminal", "punch", "viora")
DEFAULT_FONT_NAMES = ("dejavu", "arial", "helvetica", "inter", "roboto", "liberation", "freesans", "noto sans", "segoe")
CAPTION_OUTLINE = "#000000"
# register -> default label style when the plan does not set label_style: minimal = white caps on black, punch = accent plate
REGISTER_LABEL = {"minimal": "outline", "punch": "plate"}
# register -> cover variant to recommend first
REGISTER_COVER = {"minimal": "A", "punch": "B"}


@dataclass
class Font:
    path: Path
    family: str
    upem: int
    ass_ratio: float  # libass size / em size (libass sizes by winAscent+winDescent)

    def ass_size(self, em_px: float) -> int:
        return int(round(em_px * self.ass_ratio))


@dataclass
class Brand:
    name: str
    bg: str
    fg: str
    accent: str
    display: Font
    body: Font
    logo: Font
    line_width: int = 4
    radius: int = 0
    highlight_mode: str = "color"
    label_style: str = "plate"
    upper: bool = True
    caption_fill: str = "#FFFFFF"
    caption_accent: str = "#FFFFFF"
    caption_outline: str = CAPTION_OUTLINE
    effects: dict = field(default_factory=dict)
    logo_text: str = ""
    logo_sub: str = ""
    logo_tracking: float = 0.3
    fonts_reason: str = ""
    register: str = ""  # minimal | punch (VIORA two registers); sets default label_style and cover
    warnings: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def palette(self) -> list[str]:
        return sorted({self.bg.upper(), self.fg.upper(), self.accent.upper()})

    def to_dict(self) -> dict:
        return {
            "name": self.name, "palette": {"bg": self.bg, "fg": self.fg, "accent": self.accent},
            "fonts": {"display": str(self.display.path), "body": str(self.body.path), "logo": str(self.logo.path)},
            "font_families": {"display": self.display.family, "body": self.body.family},
            "caption": {"fill": self.caption_fill, "accent": self.caption_accent, "outline": self.caption_outline,
                        "highlight_mode": self.highlight_mode},
            "line_width": self.line_width, "radius": self.radius, "label_style": self.label_style,
            "upper": self.upper, "register": self.register, "effects": self.effects, "fonts_reason": self.fonts_reason, "warnings": self.warnings,
        }


@lru_cache(maxsize=64)
def load_font(path: str) -> Font:
    f = TTFont(path, lazy=True)
    name = f["name"].getDebugName(1) or Path(path).stem
    upem = f["head"].unitsPerEm
    os2 = f["OS/2"]
    asc, desc = os2.usWinAscent, os2.usWinDescent
    if not asc:
        asc, desc = f["hhea"].ascent, -f["hhea"].descent
    return Font(Path(path), name, upem, (asc + desc) / upem)


def font_has(path: Path, chars: str) -> bool:
    cmap = TTFont(str(path), lazy=True).getBestCmap()
    return all(ord(c) in cmap for c in chars if not c.isspace())


def preset_data(name: str) -> dict:
    p = asset(f"brand/{name}.json")
    if not p.exists():
        raise ShortsError(f"unknown brand preset '{name}'. Presets: {', '.join(PRESETS)} or a path to brand.json")
    return json.loads(p.read_text(encoding="utf-8"))


def _resolve_path(ref: str, base_dirs: list[Path]) -> Path | None:
    p = Path(ref).expanduser()
    if p.is_absolute():
        return p if p.exists() else None
    for b in base_dirs:
        if (b / p).exists():
            return (b / p).resolve()
    return None


def resolve(plan_brand: dict, plan_dir: Path | None = None, language: str = "ru") -> Brand:
    bases = [d for d in (plan_dir, skill_root()) if d]
    preset = plan_brand.get("preset", "mono")
    if preset.endswith(".json"):
        bp = _resolve_path(preset, bases)
        if not bp:
            raise ShortsError(f"brand file not found: {preset}")
        data = json.loads(bp.read_text(encoding="utf-8"))
        base = preset_data(data.get("base", "mono"))
        base.update(data)
        data = base
        bases.insert(0, bp.parent)
    else:
        data = preset_data(preset)
    warnings: list[str] = []
    pal = dict(data["palette"])
    pal.update({k: v for k, v in (plan_brand.get("palette") or {}).items() if v})
    fonts = dict(data["fonts"])
    reason = plan_brand.get("fonts", {}).get("reason") or data.get("fonts_reason", "")
    for k, v in (plan_brand.get("fonts") or {}).items():
        if k == "reason" or not v:
            continue
        found = _resolve_path(v, bases)
        if found:
            fonts[k] = str(found)
        else:
            warnings.append(f"font '{v}' not found, using preset font {Path(fonts.get(k, fonts['display'])).name}")
    resolved = {}
    for k in ("display", "body", "logo"):
        ref = fonts.get(k) or fonts["display"]
        p = _resolve_path(ref, bases)
        if not p:
            raise ShortsError(f"font file missing: {ref}")
        resolved[k] = load_font(str(p))
    if language.startswith(("ru", "uk", "be", "bg", "sr", "kk")):
        for k, f in resolved.items():
            if not font_has(f.path, "АБВЖЩЫЁабвжщыё"):
                raise ShortsError(f"{k} font {f.path.name} has no Cyrillic, pick another font")
    for c in pal.values():
        hex_to_rgb(c)
    eff = dict(data.get("effects") or {})
    eff.update(plan_brand.get("effects") or {})
    hl = data.get("highlight_mode", "color")
    fill = "#FFFFFF"
    accent = pal["accent"]
    cap_accent = fill if hl == "underline" else fit_contrast(accent, CAPTION_OUTLINE, 7.0)
    if hl == "color" and cap_accent.upper() != accent.upper():
        log.info("caption highlight %s lifted to %s for 7:1 contrast", accent, cap_accent)
    if contrast(cap_accent, CAPTION_OUTLINE) < 7.0:
        warnings.append("caption accent below 7:1")
    register = plan_brand.get("register") or data.get("register", "")
    style = plan_brand.get("label_style") or REGISTER_LABEL.get(register) or data.get("label_style", "plate")
    return Brand(
        name=data.get("name", preset), bg=pal["bg"], fg=pal["fg"], accent=accent,
        display=resolved["display"], body=resolved["body"], logo=resolved["logo"],
        line_width=int(plan_brand.get("line_width", data.get("line_width", 4))),
        radius=int(plan_brand.get("radius", data.get("radius", 0))),
        highlight_mode=hl, label_style=style, register=register,
        upper=bool(plan_brand.get("upper", data.get("upper", True))),
        caption_fill=fill, caption_accent=cap_accent, effects=eff,
        logo_text=data.get("logo_text", ""), logo_sub=data.get("logo_sub", ""),
        logo_tracking=float(data.get("logo_tracking", 0.3)), fonts_reason=reason, warnings=warnings, raw=data,
    )


def default_font_used(brand: Brand) -> list[str]:
    bad = []
    for f in (brand.display, brand.body):
        fam = f.family.lower()
        if any(fam.startswith(n) for n in DEFAULT_FONT_NAMES) and not brand.fonts_reason:
            bad.append(f.family)
    return bad
