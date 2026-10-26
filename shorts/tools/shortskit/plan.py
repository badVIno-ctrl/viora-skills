"""Plan loading, schema validation and rule lint (things a script can check before rendering)."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from . import contract as K
from .config import skill_root, schema_path
from .engine import layout as L
from .util import ShortsError, count_emoji, has_long_dash, read_json, script_ratio

GREETINGS = {
    "ru": [r"^\s*привет", r"^\s*всем привет", r"^\s*в этом видео", r"^\s*сегодня я (вам )?расскажу", r"^\s*смотрите", r"^\s*здравствуйте"],
    "en": [r"^\s*hi\b", r"^\s*hello\b", r"^\s*hey (guys|everyone)", r"^\s*in this video", r"^\s*today i('| a)m going to", r"^\s*welcome"],
}
GOODBYES = {
    "ru": [r"\bвсем пока\b", r"\bпока[!.]?\s*$", r"\bдо встречи\b", r"\bдо скорого\b", r"\bувидимся\b"],
    "en": [r"\bbye\b", r"\bsee you\b", r"\bthat'?s all\b", r"\bthanks for watching\b"],
}


@dataclass
class Issue:
    level: str  # error | warn
    code: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.code}: {self.msg}"


def load(path: Path | str) -> tuple[dict, Path]:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise ShortsError(f"plan not found: {p}")
    return read_json(p), p.parent


def schema() -> dict:
    return read_json(schema_path("plan.schema.json"))


def validate_schema(plan: dict) -> list[Issue]:
    v = jsonschema.Draft202012Validator(schema())
    out = []
    for e in sorted(v.iter_errors(plan), key=lambda e: list(e.path)):
        where = "/".join(str(x) for x in e.path) or "(root)"
        out.append(Issue("error", "schema", f"{where}: {e.message}"))
    return out


def lang2(plan: dict) -> str:
    return (plan.get("meta", {}).get("language") or "ru")[:2].lower()


def resolve_ref(ref: str, plan_dir: Path | None) -> Path | None:
    p = Path(ref).expanduser()
    if p.is_absolute():
        return p if p.exists() else None
    for b in (plan_dir, skill_root()):
        if b and (b / p).exists():
            return (b / p).resolve()
    return None


def is_local_ref(ref: str) -> bool:
    """A file path, not a URL. Film refs may also be URLs; plain words are not checked."""
    if ref.startswith(("http://", "https://", "html:", "color:")):
        return False
    return "/" in ref or "\\" in ref or bool(Path(ref).suffix)


def src_type(scene: dict) -> str:
    return (scene.get("source") or {}).get("type", "")


def lint(plan: dict, plan_dir: Path | None = None) -> list[Issue]:
    """Rules from COMMON.md that can be checked on the plan alone."""
    if (plan.get("video") or {}).get("format") == "long":
        from .engine.longform import lint_long
        return lint_long(plan, plan_dir)
    out: list[Issue] = []
    lang = lang2(plan)
    lay = plan.get("layout", {})
    mode = lay.get("mode", "three")
    try:
        geo = L.compute(lay, plan["meta"].get("platforms", ["youtube_shorts"]))
        if geo.center_pct < L.CENTER_MIN * 100:
            out.append(Issue("error", "center", f"center is {geo.center_pct:.0f}% of height, must be >= 55%"))
    except ShortsError as e:
        out.append(Issue("error", "layout", str(e)))
    for side in ("top", "bottom"):
        pct = (lay.get(side) or {}).get("height_pct")
        if pct is not None and pct > 20:
            out.append(Issue("error", "panel", f"{side} panel {pct}% > 20%"))
    anim = (lay.get("bottom") or {}).get("animation") or {}
    misplaced = [k for k in ("name", "message", "action", "qr_url", "handle", "tagline", "logo") if k in anim]
    if misplaced:  # these live in layout.bottom, not inside animation; otherwise the banner silently shows its fallback text
        out.append(Issue("error", "banner_fields", "layout.bottom.animation has " + ", ".join(misplaced)
                         + ": move them to layout.bottom, or the banner falls back to default text"))
    if mode in ("three", "top_center"):
        src = (lay.get("top") or {}).get("source")
        if not src:
            out.append(Issue("error", "empty_top", "top panel has no source: give a video or html, or switch layout to center_bottom/center_only"))
        elif src.startswith("color:"):
            out.append(Issue("warn", "empty_top", "top panel is a solid colour: it is an empty panel and will fail QA"))
        elif src.startswith("bg:"):
            from .bglib import item

            if src[3:] not in ("", "auto") and item(src[3:]) is None:
                out.append(Issue("error", "top_source", f"unknown background {src}: see `shorts.py bg list` (or bg:auto)"))
        elif src.startswith("loop:"):
            from .panels import KINDS

            if src[5:] not in KINDS + ("auto", ""):
                out.append(Issue("error", "top_source", f"unknown loop {src}: use loop:auto or loop:{'|'.join(KINDS)}"))
        elif not src.startswith("html:") and not resolve_ref(src, plan_dir):
            out.append(Issue("error", "media_missing", f"top panel source not found: {src}"))
    if mode in ("three", "center_bottom"):
        b = lay.get("bottom") or {}
        if not (b.get("handle") or b.get("links")):
            out.append(Issue("error", "empty_bottom", "bottom panel has no handle or links: ask the user or switch layout"))
    ctas = lay.get("cta_in_center") or []
    if len(ctas) > 3:
        out.append(Issue("error", "cta", "more than 3 CTA flashes"))
    for c in ctas:
        if c["kind"] == "qr" and not c.get("url"):
            out.append(Issue("error", "cta_qr", "QR flash needs url"))
        if c["kind"] in ("handle", "text") and not (c.get("text") or (lay.get("bottom") or {}).get("handle")):
            out.append(Issue("error", "cta_text", f"{c['kind']} flash needs text"))
    scene_ids = {s.get("id") for s in plan.get("scenes", [])}
    for c in ctas:
        a = c.get("anchor")
        if a and a.get("scene") not in scene_ids:
            out.append(Issue("error", "cta_anchor", f"CTA anchor scene '{a.get('scene')}' is not a scene id"))
    timed = sorted((float(c["t"]), float(c.get("duration", 2.5))) for c in ctas if "t" in c and not c.get("anchor") and "t_pct" not in c)
    for (t0, d0), (t1, _) in zip(timed, timed[1:]):
        if t1 < t0 + d0:
            out.append(Issue("warn", "cta_overlap", f"CTA at {t1:g}s starts before the one at {t0:g}s ends ({t0 + d0:g}s): "
                             f"the engine will move it to {t0 + d0 + 0.3:g}s; set t >= {t0 + d0 + 0.3:g} to keep control"))
    for c in ctas:
        if c["kind"] == "link" and not (c.get("text") or c.get("url")):
            out.append(Issue("error", "cta_link", "link flash needs text or url"))
    if ctas and not any(c["kind"] in ("handle", "link", "subscribe") for c in ctas):
        # research v9 5.2: a nick/link people can type beats a QR (a phone cannot scan its own screen);
        # QR only next to the nick, never instead of it
        out.append(Issue("warn", "cta_handle", "no nick/link flash: show the nick or t.me link (twice); QR only next to it"))

    br = plan.get("brand", {})
    eff = br.get("effects") or {}
    for k in ("text_glow", "gradient_plate"):
        if eff.get(k):
            out.append(Issue("error", "slop", f"brand.effects.{k} is on: glow and gradient plates are banned (QA will fail)"))
    pal = br.get("palette") or {}
    if len({v.upper() for v in pal.values() if v}) > 3:
        out.append(Issue("error", "palette", "more than 3 base colours"))

    cap = plan.get("captions", {})
    if cap.get("enabled", True) and cap.get("max_words", 3) > 3:
        out.append(Issue("warn", "captions", "max_words > 3: the rule is 2-3 words per chunk"))
    if cap.get("size") and cap["size"] < 64:
        out.append(Issue("error", "captions", "caption size < 64 px"))

    out += lint_13(plan)

    scenes = plan.get("scenes", [])
    ids = [s.get("id") for s in scenes]
    if len(set(ids)) != len(ids):
        out.append(Issue("error", "scenes", "scene ids must be unique"))
    all_text = []
    for i, s in enumerate(scenes):
        say, ost = s.get("say", ""), s.get("on_screen_text", "")
        all_text += [say, ost]
        for fld, txt in (("say", say), ("on_screen_text", ost)):
            if has_long_dash(txt):
                out.append(Issue("error", "dash", f"scene {s.get('id')}: long dash in {fld}, use '-'"))
        if count_emoji(ost):
            out.append(Issue("error", "emoji", f"scene {s.get('id')}: emoji in on-screen text"))
        if not s.get("why"):
            out.append(Issue("warn", "why", f"scene {s.get('id')}: no 'why' (design rule 7: no answer, remove the layer)"))
        if not say and not s.get("duration") and not s.get("duration_hint") and s["source"]["type"] not in ("video", "film"):
            out.append(Issue("error", "duration", f"scene {s.get('id')}: no say and no duration (or duration_hint)"))
        if s.get("avoid") and src_type(s) == "site":
            from .contract import parse_avoid

            rules, free = parse_avoid(s["avoid"])
            if free and not rules:
                out.append(Issue("warn", "avoid", f"scene {s.get('id')}: avoid has only free text, nothing is skipped; "
                                 "write 'click' or 'click:<text>' to skip an action"))
        src = s["source"]
        if src["type"] == "video" and str(src.get("ref", "")).startswith("bg:"):
            from .bglib import item

            key = src["ref"][3:]
            if key not in ("", "auto") and item(key) is None:
                out.append(Issue("error", "scene_bg", f"scene {s.get('id')}: unknown background {src['ref']}: "
                                 "see `shorts.py bg list` (or bg:auto, or `bg add ID FILE`)"))
            if not (s.get("say") or s.get("duration") or s.get("transcript")):
                out.append(Issue("error", "scene_bg", f"scene {s.get('id')}: a background scene needs say or duration"))
        elif src["type"] in ("html", "video", "images", "film") and src.get("ref") and is_local_ref(src["ref"]):
            if Path(src["ref"]).is_absolute():
                out.append(Issue("warn", "abs_path", f"scene {s.get('id')}: absolute path {src['ref']}: "
                                 "use a path relative to the plan folder so the plan works on another machine"))
            if not resolve_ref(src["ref"], plan_dir):
                out.append(Issue("error", "media_missing", f"scene {s.get('id')}: file not found {src['ref']} "
                                 "(paths are relative to the plan folder)"))
        if src["type"] == "site" and not (src.get("ref") or any(a.get("url") for a in src.get("actions", []))):
            out.append(Issue("error", "source", f"scene {s.get('id')}: site scene needs ref or goto url"))
        for sp in s.get("speed", []):
            if not 0.25 <= sp["rate"] <= 4:
                out.append(Issue("warn", "speed", f"scene {s.get('id')}: rate {sp['rate']} outside 0.25-4"))
    if scenes:
        first = scenes[0].get("say", "")
        for pat in GREETINGS.get(lang, []):
            if re.search(pat, first, re.I):
                out.append(Issue("error", "hook", "first line starts with a greeting: start with the result or a question"))
                break
        last = scenes[-1].get("say", "")
        for pat in GOODBYES.get(lang, []):
            if re.search(pat, last, re.I) and not (plan.get("schema_version") == "1.4" and not plan["meta"].get("loop", True)):
                out.append(Issue("error", "loop", "last line says goodbye: it breaks the loop"))
                break
    joined = " ".join(t for t in all_text if t)
    sr = script_ratio(joined)
    if sr["letters"] > 20:
        if lang == "ru" and sr["cyrillic"] < 0.5:
            out.append(Issue("warn", "language", "plan language is ru but most text is Latin"))
        if lang == "en" and sr["cyrillic"] > 0.2:
            out.append(Issue("warn", "language", "plan language is en but text has Cyrillic"))
    return out


NOTABLE_MAX = 2  # research 14: besides cuts, at most 2 "moves" a viewer notices per video


def _version(plan: dict) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(plan.get("schema_version", "1")).split("."))
    except ValueError:
        return (1,)


def lint_13(plan: dict) -> list[Issue]:
    """Rules for the 1.3 fields (research 14, 15, 17, 22)."""
    out: list[Issue] = []
    lay = plan.get("layout", {})
    fx = plan.get("fx") or {}
    scenes = plan.get("scenes", [])
    types = {src_type(s) for s in scenes}
    if lay.get("mode") == "band" and not lay.get("title_bar"):
        out.append(Issue("error", "band", "layout.mode band needs layout.title_bar (the black field must say the topic)"))
    tb = lay.get("title_bar")
    for it in ([tb] if isinstance(tb, dict) else (tb or [])):
        if len(it.get("text", "")) > 28:
            out.append(Issue("warn", "title_bar", f"title bar '{it.get('text')}' is {len(it.get('text', ''))} chars: 2-5 words, <= 28"))
        if has_long_dash(it.get("text", "") + it.get("sub", "")):
            out.append(Issue("error", "dash", "long dash in layout.title_bar, use '-'"))
    for f in (plan.get("overlays") or {}).get("facts") or []:
        if has_long_dash(f.get("text", "") + f.get("sub", "")):
            out.append(Issue("error", "dash", "long dash in overlays.facts, use '-'"))
        words = len((f.get("text", "") + " " + f.get("sub", "")).split())
        if f.get("dur") is not None and float(f["dur"]) < 1.5 * max(1, -(-words // 3)):
            out.append(Issue("warn", "facts", f"fact '{f.get('text', '')[:24]}' {f['dur']}s for {words} words: >= 1.5 s per 3 words"))
    post = (plan.get("overlays") or {}).get("post")
    ids = [s.get("id") for s in scenes]
    for it in ([post] if isinstance(post, dict) else list(post or [])):
        sid = it.get("scene") or (ids[0] if ids else None)
        sc = next((s for s in scenes if s.get("id") == sid), None)
        if sc is None:
            out.append(Issue("error", "post", f"overlays.post: scene '{sid}' not found"))
            continue
        if has_long_dash(" ".join(str(it.get(k, "")) for k in ("title", "text", "name", "where", "stats"))):
            out.append(Issue("error", "dash", "long dash in overlays.post, use '-'"))
        voice = str(it.get("text", "voice")).strip().lower() in ("voice", "say")
        if voice and not (sc.get("say") or sc.get("transcript")) and "from" not in it:
            out.append(Issue("error", "post", f"overlays.post text 'voice': scene '{sid}' has no say (nothing to write); "
                             "give text or say"))
        n = len(str(sc.get("say") or "").split()) if voice else len(str(it.get("text", "")).split())
        if n > 60:
            out.append(Issue("warn", "post", f"overlays.post: {n} words on the card (it scrolls): the card reads the hook "
                             "(<= 40 words), the story goes on in captions"))
        if len(str(it.get("title", ""))) > 90:
            out.append(Issue("warn", "post", "overlays.post title > 90 chars: it is cut at 3 lines"))
    notable = []
    if fx.get("letterbox"):
        notable.append("letterbox")
    if fx.get("flicker"):
        notable.append("flicker")
    if len({k.get("look") for k in fx.get("look_keys") or []}) > 1 or (fx.get("look_keys") and len(fx["look_keys"]) == 1):
        notable.append("look_keys")
    if lay.get("split"):
        notable.append("split")
    heavy = {"zoom", "flash_blur", "glitch", "spin", "flicker"}
    if any((s.get("trans") if isinstance(s.get("trans"), str) else (s.get("trans") or {}).get("kind")) in heavy for s in scenes) \
            or (isinstance(fx.get("transitions"), dict) and fx["transitions"].get("auto") in ("energy", "phonk")):
        notable.append("heavy transitions")
    if len(notable) > NOTABLE_MAX:
        out.append(Issue("warn", "effects", f"{len(notable)} noticeable effects ({', '.join(notable)}): review each effect role and visual clutter; "
                         "effect count is not a creative limit (v3.3)"))
    if len(fx.get("look_keys") or []) > 3:
        out.append(Issue("warn", "look_keys", "more than 3 look keys: 1-2 colour switches per video"))
    drop = (plan.get("audio", {}).get("music") or {}).get("drop_at")
    def uses_drop(v) -> bool:
        return isinstance(v, str) and v.strip().lower() == "drop"
    keys = [k.get("t") for k in (fx.get("look_keys") or []) + (fx.get("flicker") or [])]
    lb = fx.get("letterbox")
    keys += [k.get("t") for k in (lb if isinstance(lb, list) else (lb or {}).get("keys", []) if isinstance(lb, dict) else [])]
    if drop is None and any(uses_drop(k) for k in keys):
        msrc = (plan.get("audio", {}).get("music") or {}).get("source")
        if isinstance(msrc, str) and msrc.strip().lower() == "auto":
            out.append(Issue("warn", "drop", "effects keyed to 'drop' with music auto: drop_at comes from the found track "
                                             "(or 35% of the length, max 6 s, without music)"))
        else:
            out.append(Issue("error", "drop", "an effect is keyed to 'drop' but audio.music.drop_at is not set"))
    for s in scenes[1:]:
        tr = s.get("trans")
        if isinstance(tr, dict) and float(tr.get("dur", 0)) > 0.5:
            out.append(Issue("warn", "trans", f"scene {s.get('id')}: transition {tr['dur']}s > 0.5 s looks like a slide show"))
    if scenes and scenes[0].get("trans"):
        out.append(Issue("warn", "trans", f"scene {scenes[0].get('id')}: the first scene has no transition into it"))
    cap = plan.get("captions", {})
    if cap.get("style") == "kinetic" and lay.get("split") and any(
            (sp.get("mode", "v2") == "v2") for sp in lay.get("split") or []):
        out.append(Issue("warn", "kinetic", "kinetic captions over a v2 split: the stack covers the seam, karaoke on the seam reads better"))
    # author layer (YouTube reused content, Instagram originality 2026): foreign footage needs >= 2 own layers
    # the same detection as the render report (manifest.author_layer, QA author_layer): film / video scenes,
    # a bg: banner, any split window; voice from `say`, text_point from on_screen_text or title_bar
    foreign = bool(types & {"film", "video"}) or str((lay.get("top") or {}).get("source", "")).startswith("bg:") or \
        bool(lay.get("split"))
    if foreign:
        layers = {x.get("kind") for x in plan.get("author_layer") or []}
        if any(s.get("say") for s in scenes):
            layers.add("voice")
        if any(str(s.get("on_screen_text") or "").strip() for s in scenes) or lay.get("title_bar"):
            layers.add("text_point")
        if not K.author_layers_ok(layers):
            lvl = "error" if _version(plan) >= (1, 3) else "warn"
            have = ", ".join(sorted(k for k in layers if k)) or "none"
            out.append(Issue(lvl, "author_layer", f"foreign material (film/video/background gameplay) needs >= 2 own layers, "
                             f"one of them voice|thesis|own_footage|compare (now: {have}): add author_layer "
                             "[{kind: voice|thesis|own_footage|compare|text_point|sound_design|interactive, note}] "
                             "(reused content risk; your own long video: own_footage)"))
    exp = (plan.get("audio") or {}).get("export")
    if exp in ("both", "without_music") and not ((plan.get("audio") or {}).get("music") or {}).get("source"):
        out.append(Issue("warn", "export", f"audio.export {exp} without audio.music.source: nothing to separate"))
    return out


def check(plan: dict, plan_dir: Path | None = None, allow_missing_media: bool = False) -> list[Issue]:
    """Schema + lint. `allow_missing_media` turns "file not found" into a warning (example plans whose
    media is not in git); every other error stays an error."""
    from .contract import normalize

    plan, _ = normalize(plan)
    issues = validate_schema(plan)
    if "video" in plan and plan.get("schema_version") != "1.4":
        issues.append(Issue("error", "schema_version", "video requires schema_version 1.4"))
    if not plan.get("video") and any("narration" in s for s in plan.get("scenes", [])):
        issues.append(Issue("error", "narration", "narration is supported only by long format 1.4"))
    if not issues:
        issues += lint(plan, plan_dir)
    if allow_missing_media:
        issues = [Issue("warn", i.code, i.msg + " [allowed: --allow-missing-media]") if i.code == "media_missing" else i
                  for i in issues]
    return issues


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]


def with_defaults(plan: dict) -> dict:
    p = copy.deepcopy(plan)
    p["meta"].setdefault("fps", 30)
    p["meta"].setdefault("loop", True)
    p.setdefault("captions", {}).setdefault("enabled", True)
    p["captions"].setdefault("max_words", 3)
    p["captions"].setdefault("highlight", "accent")
    p["captions"].setdefault("subs", {})
    au = p.setdefault("audio", {})
    au.setdefault("voice", {}).setdefault("engine", "auto")
    au.setdefault("target_lufs", -14)
    au.setdefault("sfx_auto", False)  # 2.2: no automatic whoosh/pop/click; see audio.sfx
    au.setdefault("sfx", "files")
    p["layout"].setdefault("cta_in_center", [])
    p.setdefault("metadata", {})
    p.setdefault("fx", {})
    return p
