"""Plan skeletons from prefs: the agent fills say / on_screen_text / actions, the script fills the rules."""
from __future__ import annotations

import re

from . import memory as M



def _music_pref(p: dict) -> dict:
    """2.4: the user's track when they named one; otherwise "auto" (found on YouTube at render).
    The old saved default (generated bed.mp3) counts as "not chosen"."""
    m = p.get("music") if isinstance(p.get("music"), dict) else ({"source": p["music"]} if p.get("music") else {})
    src = str(m.get("source") or "").strip()
    if not src or src.endswith(("audio/bed.mp3", "audio/edit.mp3")):
        src = "auto"
    out = {"source": src}
    for k in ("mood", "genre", "query"):
        if m.get(k):
            out[k] = m[k]
    return out

def _lang(p: dict) -> str:
    lang = p.get("language")
    if isinstance(lang, dict):
        return (lang.get("video") or lang.get("chat") or "ru")[:2]
    return (lang or "ru")[:2]


def _links(p: dict) -> list[str]:
    links = p.get("links") or {}
    if isinstance(links, dict):
        return [v for v in links.values() if isinstance(v, str) and v.startswith("http")]
    return [v for v in links if isinstance(v, str)]


def skeleton(source: str, refs: list[str], name: str = "short", topic: str = "") -> dict:
    p = M.load()
    lang = _lang(p)
    platforms = p.get("platforms") or ["youtube_shorts"]
    mode = p.get("layout") or ("center_only" if source in ("film", "video") else "three")
    panels = p.get("panels") or {}
    links = _links(p)
    handle = (p.get("handle") or panels.get("handle") or "").lstrip("@")
    layout: dict = {"mode": mode, "cta_in_center": []}
    if mode in ("three", "top_center"):
        layout["top"] = {"height_pct": 20, "source": panels.get("top") or "loop:auto"}
    if mode in ("three", "center_bottom"):
        layout["bottom"] = {"height_pct": 16, "handle": handle, "links": links[:1]}
    target = [20, 40]
    if handle:
        layout["cta_in_center"].append({"t": 14, "duration": 2.5, "kind": "handle", "text": handle})
    if links and p.get("qr", True):
        layout["cta_in_center"].append({"t": 27, "duration": 3, "kind": "qr", "url": links[0]})
    scenes = []
    say_hook = "TODO: result or question in the first second, no greeting" if lang != "ru" else \
        "TODO: результат или вопрос в первую секунду, без приветствия"
    if source == "site":
        for i, r in enumerate(refs or ["https://example.com"]):
            scenes.append({"id": "hook" if i == 0 else f"site-{i}", "say": say_hook if i == 0 else "TODO",
                           "on_screen_text": "TODO 2-4 WORDS" if i == 0 else "", "why": "result first" if i == 0 else "demo",
                           "source": {"type": "site", "ref": r, "viewport": "mobile",
                                      "actions": [{"do": "goto"}, {"do": "dismiss_cookies"}, {"do": "scroll", "dy": 600, "t": 2.0}]}})
    elif source in ("html", "images", "video", "film"):
        for i, r in enumerate(refs or ["TODO"]):
            src: dict = {"type": source, "ref": r}
            if source == "images":
                src = {"type": "images", "images": [r], "focus": [0.5, 0.4]}
            if source in ("video", "film"):
                src.update({"in": 0, "out": 6})
            scenes.append({"id": f"s{i + 1}", "say": say_hook if i == 0 else "TODO", "why": "TODO", "source": src,
                           **({"on_screen_text": "TODO"} if i == 0 else {})})
    else:
        scenes.append({"id": "hook", "say": say_hook, "on_screen_text": "TODO", "why": "result first",
                       "source": {"type": "text", "ref": topic or "TODO | phrase two | phrase three"}})
    br = p.get("brand") or {"preset": "mono"}
    if isinstance(br, dict):
        # Profile is memory, not visual configuration. A profile-only intake still has a usable preset.
        br = {k: v for k, v in br.items() if k not in ("profile", "niche", "niche_profile", "goal", "style_choice")}
        br.setdefault("preset", "mono")
    plan = {
        "schema_version": "1",
        "meta": {"name": re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "short", "language": lang,
                 "platforms": platforms, "duration_target": target, "emotion": "trust", "audience": ((p.get("brand") or {}).get("profile", {}).get("audience", "TODO")
                  if isinstance(p.get("brand"), dict) and isinstance(p["brand"].get("profile"), dict) else "TODO"), "loop": True},
        "layout": layout,
        "brand": br if isinstance(br, dict) else {"preset": str(br)},
        "captions": {"enabled": True, "max_words": 3, "highlight": "accent", "subs": {}},
        "audio": {"voice": p.get("voice") or {"engine": "auto", "speed": 1.05},
                  "music": {**_music_pref(p), "duck_db": -10},
                  "target_lufs": -14},
        "scenes": scenes,
        "metadata": {"topic": topic, "niche_context": M.niche_context(p)},
    }
    return plan
