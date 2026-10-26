"""Contract with callers (Viora Studio and others): plan aliases, CTA scheduling, `avoid`, render output files.

See docs/render-output.md. Everything here is additive: plans written for schema 1 keep working.
"""
from __future__ import annotations

import copy
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

# qa.json check ids <- words callers search for (Viora searches by these words)
QA_ALIASES: dict[str, list[str]] = {
    "first": ["first_frame"],
    "motion": ["first_frame", "rhythm", "layout"],   # motion in 1.5 s, no still pause, top panel moves
    "pause": ["rhythm"],
    "safe": ["safe_zone"],
    "qr_decode": ["qr"],
    "slop": ["anti_slop"], "glow": ["anti_slop"], "gradient": ["anti_slop"],
    "lufs": ["loudness"],
    "caption": ["captions"],
    "duration": ["format"],
    "flash": ["vfx"], "effects": ["vfx"],                 # 1.3: <= 3 flashes/s (WCAG 2.3.1), bars, signature moves
    "originality": ["author_layer"], "reused": ["author_layer"],   # 1.3: own layers over foreign footage, credits
}

# 1.3 author layer over foreign footage (research 15, part 2; 14, part 12): >= 2 kinds, one of them a core kind
AUTHOR_KINDS = ("voice", "thesis", "own_footage", "compare", "text_point", "sound_design", "interactive")
AUTHOR_CORE = ("voice", "thesis", "own_footage", "compare")


def author_layers_ok(kinds) -> bool:
    """>= 2 different own layers and at least one of voice / thesis / own_footage / compare."""
    ks = {k for k in kinds if k}
    return len(ks) >= 2 and bool(ks & set(AUTHOR_CORE))

SITE_ACTIONS = ("goto", "wait", "move", "click", "hover", "type", "press", "scroll", "dismiss_cookies")
CTA_GAP = 0.3       # s between two CTA flashes
CTA_MIN = 1.5       # s, shortest flash (schema minimum)
REGISTERS = ("minimal", "punch")


# ------------------------------------------------------------------ aliases

def normalize(plan: dict) -> tuple[dict, list[str]]:
    """Copy of the plan with caller synonyms mapped to official fields. Official fields win.

    x_duration_hint -> scenes[].duration_hint, x_avoid -> scenes[].avoid, x_viora.register -> brand.register,
    edit.look_keys -> fx.look_keys (1.3), layout.title -> layout.title_bar (1.3).
    """
    p = copy.deepcopy(plan)
    notes: list[str] = []
    for s in p.get("scenes") or []:
        for alias, field_ in (("x_duration_hint", "duration_hint"), ("x_avoid", "avoid")):
            if alias in s and field_ not in s:
                s[field_] = s[alias]
                notes.append(f"scene {s.get('id')}: {alias} read as {field_}")
    ed = p.get("edit")
    if isinstance(ed, dict) and ed.get("look_keys") is not None:
        fx = p.setdefault("fx", {})
        if isinstance(fx, dict) and "look_keys" not in fx:
            fx["look_keys"] = ed["look_keys"]
            notes.append("edit.look_keys read as fx.look_keys")
        ed.pop("look_keys", None)
    lay = p.get("layout")
    if isinstance(lay, dict) and "title" in lay and "title_bar" not in lay:
        t = lay.pop("title")
        lay["title_bar"] = {"text": t} if isinstance(t, str) else t
        notes.append("layout.title read as layout.title_bar")
    reg = (p.get("x_viora") or {}).get("register") if isinstance(p.get("x_viora"), dict) else None
    br = p.get("brand")
    if reg and isinstance(br, dict) and "register" not in br:
        br["register"] = reg
        notes.append(f"x_viora.register read as brand.register ({reg})")
    return p, notes


# ------------------------------------------------------------------ avoid

@dataclass
class AvoidRule:
    do: str
    needle: str  # "" = every action of this kind


def parse_avoid(items: list[str] | None) -> tuple[list[AvoidRule], list[str]]:
    """'click' or 'click:3d model' are rules (action name + optional text to find in the action);
    anything else (free text) is a note for the reader only."""
    rules, free = [], []
    for it in items or []:
        head, _, tail = str(it).partition(":")
        head = head.strip().lower()
        if head in SITE_ACTIONS:
            rules.append(AvoidRule(head, tail.strip().lower()))
        else:
            free.append(str(it))
    return rules, free


def apply_avoid(actions: list[dict], avoid: list[str] | None) -> tuple[list[dict], list[str]]:
    """Drop actions that match a rule. Returns (kept actions, notes)."""
    rules, free = parse_avoid(avoid)
    notes = [f"avoid (note only, not a rule): {f}" for f in free]
    kept = []
    for a in actions:
        d = str(a.get("do", "")).lower()
        blob = json.dumps({k: v for k, v in a.items() if k != "do"}, ensure_ascii=False).lower()
        hit = next((r for r in rules if r.do == d and (not r.needle or r.needle in blob)), None)
        if hit:
            notes.append(f"action {d} skipped: matches avoid '{hit.do}{':' + hit.needle if hit.needle else ''}'")
        else:
            kept.append(a)
    return kept, notes


# ------------------------------------------------------------------ CTA times

def cta_time(c: dict, scenes: list[tuple[str, float, float]], total: float) -> tuple[float, str]:
    """Requested start of one CTA: anchor {scene, offset} (offset < 0 counts from the scene end), t_pct (0-1) or t."""
    if c.get("anchor"):
        a = c["anchor"]
        sc = next((s for s in scenes if s[0] == a.get("scene")), None)
        if sc is None:
            fallback = float(c["t"]) if "t" in c else (float(c["t_pct"]) * total if "t_pct" in c else total)
            return fallback, f"anchor scene '{a.get('scene')}' not found (skipped?), used {'t' if 't' in c else 't_pct' if 't_pct' in c else 'the end'}"
        off = float(a.get("offset", 0))
        return (sc[1] + sc[2] + off if off < 0 else sc[1] + off), f"anchor {sc[0]}{off:+.2f}"
    if "t_pct" in c:
        return float(c["t_pct"]) * total, f"t_pct {float(c['t_pct']):.2f}"
    return float(c.get("t", 0.0)), "t"


def _pack(times: list[float], durs: list[float], total: float) -> list[float] | None:
    """Keep the order, push overlapping flashes later (gap CTA_GAP), then pull back from the end. None = no room."""
    t = [min(max(0.0, x), max(0.0, total - d)) for x, d in zip(times, durs)]
    for i in range(1, len(t)):
        t[i] = max(t[i], t[i - 1] + durs[i - 1] + CTA_GAP)
    if t and t[-1] + durs[-1] > total + 1e-6:
        t[-1] = total - durs[-1]
    for i in range(len(t) - 2, -1, -1):
        t[i] = min(t[i], t[i + 1] - CTA_GAP - durs[i])
    return t if all(x >= -1e-6 for x in t) else None


DROP_FIRST = {"text": 0, "handle": 1, "qr": 2}  # when nothing fits, the QR stays longest


def schedule_ctas(ctas: list[dict], scenes: list[tuple[str, float, float]], total: float) -> list[dict]:
    """Final CTA times: inside [0, total - duration], in the requested order, no overlap (gap CTA_GAP).
    Overlapping flashes are moved later (or earlier near the end); if they still do not fit, all are
    shortened to CTA_MIN; then the least important is dropped (text, then handle). Every change has a reason."""
    rows = []
    for i, c in enumerate(ctas):
        req, how = cta_time(c, scenes, total)
        rows.append({"index": i, "kind": c.get("kind"), "requested": round(req, 3), "how": how,
                     "duration": min(float(c.get("duration", 2.5)), total), "dropped": False, "reasons": []})
    live = sorted(rows, key=lambda r: (r["requested"], r["index"]))
    while live:
        times = [r["requested"] for r in live]
        packed = _pack(times, [r["duration"] for r in live], total)
        if packed is None:
            packed = _pack(times, [min(r["duration"], CTA_MIN) for r in live], total)
            if packed is not None:
                for r in live:
                    if r["duration"] > CTA_MIN:
                        r["duration"] = CTA_MIN
                        r["reasons"].append(f"shortened to {CTA_MIN} s: not enough room for all CTAs")
        if packed is None:
            victim = min(live, key=lambda r: (DROP_FIRST.get(r["kind"], 0), r["index"]))
            victim.update(dropped=True, final=None, t=None)
            victim["reasons"].append("dropped: no free window for it next to the other CTAs")
            live.remove(victim)
            continue
        for r, t in zip(live, packed):
            r["t"] = r["final"] = round(t, 3)
            if t < r["requested"] - 1e-3:
                r["reasons"].append("clamped into the video" if r["requested"] + r["duration"] > total
                                    and t >= total - r["duration"] - 1e-3 else "moved earlier: overlapped another CTA")
            elif t > r["requested"] + 1e-3:
                r["reasons"].append("clamped into the video" if r["requested"] < 0 else "moved later: overlapped another CTA")
        break
    for r in rows:
        r["duration"] = round(r["duration"], 3)
        r["reason"] = "; ".join(dict.fromkeys(r.pop("reasons"))) or "as requested"
    return rows


# ------------------------------------------------------------------ render output

def words_out(words_spoken: list[dict]) -> list[dict]:
    """words.json: [{"word", "start", "end"}] in video seconds."""
    return [{"word": w["w"], "start": round(float(w["s"]), 3), "end": round(float(w["e"]), 3)} for w in words_spoken]


def write_render_output(out: Path, manifest: dict, schema_version: str) -> None:
    """words.json and result.json next to the mp4 (docs/render-output.md)."""
    (out / "words.json").write_text(json.dumps(words_out(manifest["captions"]["words_spoken"]), ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    res = {"duration": manifest["duration"], "video": manifest["video"], "fps": manifest["fps"],
           "schema_version": schema_version, "engine": manifest["engine"], "engine_version": manifest["version"],
           "cta_schedule": manifest.get("cta_schedule", [])}
    (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


def qa_extras(rows: list[dict]) -> dict:
    """Fields for qa.json: not_checked (ids a person/agent must still check) and aliases (caller word -> ids)."""
    ids = {r["id"] for r in rows}
    return {"not_checked": [r["id"] for r in rows if r["status"] == "manual"],
            "aliases": {k: [i for i in v if i in ids] for k, v in QA_ALIASES.items()}}


def copy_contact(pages: list[Path], d: Path) -> Path | None:
    """contact.png = first contact sheet page (callers expect one fixed name)."""
    if not pages:
        return None
    dst = d / "contact.png"
    shutil.copyfile(pages[0], dst)
    return dst
