"""Line-art symbols for minimal covers, drawn by code (no stock icons, no model).

Each symbol is a few strokes on a transparent square, supersampled 4x for clean edges (no blur, no glow).
One small part is filled with the accent colour: the single accent of a minimal cover.
`symbol_for(text, source_types)` picks the symbol from the topic words (ru/en stems)."""
from __future__ import annotations

import math
import re

from PIL import Image, ImageDraw

SS = 4  # supersampling

# stem -> symbol; first match in TOPIC order wins, so put specific stems first
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("lock", ("защит", "безопас", "парол", "приват", "взлом", "шифр", "secur", "privacy", "password", "lock", "hack", "vpn")),
    ("key", ("ключ", "доступ", "бесплат", "регистр", "вход", "логин", "free", "access", "key", "login", "api")),
    ("chess", ("шахмат", "стратег", "турнир", "битв", "против", "сравн", "дуэл", "chess", "strateg", "battle", "versus",
               "vs", "tournament", "compare")),
    ("chart", ("рост", "деньг", "доход", "заработ", "подписчик", "просмотр", "статист", "growth", "money", "income",
               "views", "subscriber", "stats")),
    ("chip", ("нейросет", "модел", "ии", "gpt", "ai", "llm", "opus", "claude", "gemini", "model", "neural")),
    ("code", ("код", "html", "программ", "скрипт", "игр", "three", "javascript", "python", "code", "script", "game", "js")),
    ("play", ("фильм", "кино", "видео", "эдит", "ролик", "нарез", "клип", "film", "movie", "video", "edit", "clip")),
    ("browser", ("сайт", "сервис", "браузер", "веб", "онлайн", "приложен", "site", "web", "browser", "app", "online", "url")),
    ("gear", ("настро", "автомат", "инструмент", "движ", "сборк", "tool", "engine", "setup", "workflow", "automat")),
]
ALL = [k for k, _ in KEYWORDS]
BY_SOURCE = {"site": "browser", "html": "code", "film": "play", "video": "play", "text": "gear", "images": "browser"}


def symbol_for(text: str, source_types: list[str] | None = None) -> str:
    words = re.findall(r"\w+", (text or "").lower())
    for name, stems in KEYWORDS:
        for w in words:
            if any(w.startswith(s) if len(s) > 2 else w == s for s in stems):
                return name
    for t in source_types or []:
        if t in BY_SOURCE:
            return BY_SOURCE[t]
    return "gear"


def draw_symbol(name: str, size: int, stroke: int, fg: tuple[int, int, int], accent: tuple[int, int, int]) -> Image.Image:
    """RGBA square `size` px with the symbol drawn in lines `stroke` px wide."""
    if name not in ALL:
        raise ValueError(f"unknown symbol {name}")
    S = size * SS
    w = max(SS, stroke * SS)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    F, A = fg + (255,), accent + (255,)
    u = S / 100.0  # 100-unit grid

    def P(x, y):
        return (x * u, y * u)

    def R(x0, y0, x1, y1):
        return [x0 * u, y0 * u, x1 * u, y1 * u]

    if name == "lock":
        d.rounded_rectangle(R(18, 44, 82, 92), radius=6 * u, outline=F, width=w)
        d.arc(R(30, 10, 70, 58), 180, 360, fill=F, width=w)
        d.line([P(30, 34), P(30, 44)], fill=F, width=w)
        d.line([P(70, 34), P(70, 44)], fill=F, width=w)
        d.ellipse(R(44, 58, 56, 70), fill=A)
        d.polygon([P(47, 66), P(53, 66), P(55, 80), P(45, 80)], fill=A)
    elif name == "key":
        d.ellipse(R(6, 32, 42, 68), outline=F, width=w)
        d.ellipse(R(18, 44, 30, 56), outline=F, width=max(SS, w // 2))
        d.line([P(42, 50), P(94, 50)], fill=F, width=w)
        d.line([P(80, 50), P(80, 64)], fill=A, width=w)
        d.line([P(90, 50), P(90, 60)], fill=A, width=w)
    elif name == "browser":
        d.rectangle(R(8, 16, 92, 84), outline=F, width=w)
        d.line([P(8, 30), P(92, 30)], fill=F, width=w)
        for i, cx in enumerate((15, 22, 29)):
            d.ellipse(R(cx - 2.2, 21, cx + 2.2, 25.4), fill=A if i == 0 else F)
        d.line([P(18, 44), P(62, 44)], fill=F, width=w)
        d.line([P(18, 56), P(50, 56)], fill=F, width=max(SS, w // 2))
        d.rectangle(R(18, 66, 40, 74), fill=A)
    elif name == "chess":  # king
        d.line([P(50, 6), P(50, 20)], fill=A, width=w)
        d.line([P(43, 13), P(57, 13)], fill=A, width=w)
        d.ellipse(R(38, 20, 62, 40), outline=F, width=w)
        d.polygon([P(36, 40), P(64, 40), P(70, 78), P(30, 78)], outline=F, width=w)
        d.rectangle(R(22, 78, 78, 90), outline=F, width=w)
    elif name == "gear":
        cx = cy = 50
        pts = []
        teeth = 8
        for i in range(teeth * 4):
            a = 2 * math.pi * i / (teeth * 4)
            r = 44 if (i % 4) in (1, 2) else 34
            pts.append(P(cx + r * math.cos(a), cy + r * math.sin(a)))
        d.polygon(pts, outline=F, width=w)
        d.ellipse(R(36, 36, 64, 64), outline=A, width=w)
    elif name == "play":
        d.rounded_rectangle(R(8, 20, 92, 80), radius=8 * u, outline=F, width=w)
        d.polygon([P(42, 36), P(66, 50), P(42, 64)], fill=A)
    elif name == "code":
        d.line([P(30, 26), P(8, 50), P(30, 74)], fill=F, width=w, joint="curve")
        d.line([P(70, 26), P(92, 50), P(70, 74)], fill=F, width=w, joint="curve")
        d.line([P(58, 18), P(42, 82)], fill=A, width=w)
    elif name == "chart":
        d.line([P(10, 10), P(10, 90), P(90, 90)], fill=F, width=w, joint="curve")
        d.line([P(20, 74), P(40, 56), P(56, 64), P(84, 26)], fill=F, width=w, joint="curve")
        d.polygon([P(88, 20), P(74, 24), P(85, 35)], fill=A)
    elif name == "chip":
        d.rectangle(R(24, 24, 76, 76), outline=F, width=w)
        d.rectangle(R(40, 40, 60, 60), fill=A)
        for k in (34, 50, 66):
            for a, b in (((k, 8), (k, 24)), ((k, 76), (k, 92)), ((8, k), (24, k)), ((76, k), (92, k))):
                d.line([P(*a), P(*b)], fill=F, width=max(SS, w * 2 // 3))
    return im.resize((size, size), Image.LANCZOS)
