"""Synthetic blogger (AI persona), shorts 2.3.

persona.json (the bible: look, place, voice, series, disclosure) -> `persona-plan` (episode skeleton by format)
-> the agent fills the lines -> `persona-check` -> `persona-build` (toon episode.json, or AI-video prompt pack)
-> `persona-cut` (AI clips + captions + "ИИ-персонаж" label via `stack`).

Honest by design (checked by code, errors block the build):
- the persona is disclosed as AI (bio, description, label) and never claims to be a real human;
- no first-hand product testimonials from a persona that does not exist (FTC 16 CFR 465.2), ads are marked
  (RU: "Реклама" + advertiser + erid, US: #ad), ad claims need a source;
- no medical promises; numbers in advice want a source;
- nothing here automates accounts, devices or posting: no device farms, ADB, anti-detect, fake engagement
  (platform rules, FTC 16 CFR 465.8). Publishing is manual or through official APIs/schedulers."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from ..util import ShortsError

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "templates" / "persona"
WPS = 2.4                 # spoken words per second (ru TTS / AI video dialogue), for estimates and chunk limits
BEAT_PAUSE = 0.35

# format -> (duration range s, beats: id, shot, toon pose, hint for the agent)
FORMATS: dict[str, dict] = {
    "tip": {"range": (25, 50), "beats": [
        ("hook", "close", "point", "Хук до 2 с: результат или ошибка зрителя, одна фраза"),
        ("why", "medium", "think", "Почему так происходит: 1-2 фразы, факт из источника"),
        ("how", "medium", "hold", "Как сделать: 2-3 коротких шага"),
        ("proof", "wide", "cheer", "Что получится: результат, который видно в кадре"),
        ("loop", "close", "wave", "Вопрос зрителю или связка к началу (без «подпишись»)")]},
    "list": {"range": (35, 60), "beats": [
        ("hook", "close", "point", "Хук: «3 ошибки, из-за которых ...»"),
        ("one", "medium", "hold", "Ошибка 1 и как правильно"),
        ("two", "medium", "think", "Ошибка 2 и как правильно"),
        ("three", "close", "point", "Ошибка 3, самая частая, и как правильно"),
        ("loop", "close", "shrug", "Какую ошибку делали вы? Или связка к началу")]},
    "story": {"range": (40, 75), "beats": [
        ("hook", "close", "scared", "Хук: странный момент из середины истории"),
        ("setup", "wide", "stand", "Кто, где, чего хотели"),
        ("conflict", "medium", "facepalm", "Что пошло не так"),
        ("turn", "close", "think", "Неожиданное решение"),
        ("lesson", "medium", "point", "Вывод, который пригодится зрителю"),
        ("loop", "close", "wave", "Вопрос или намёк на следующую серию")]},
    "reply": {"range": (20, 45), "beats": [
        ("comment", "medium", "phone", "Прочитать комментарий зрителя (реальный, без имени, если нет разрешения)"),
        ("answer", "close", "point", "Короткий ответ"),
        ("demo", "medium", "hold", "Показать, как сделать"),
        ("loop", "close", "wave", "Попросить следующий вопрос")]},
    "myth": {"range": (25, 50), "beats": [
        ("hook", "close", "shrug", "«Все так делают, а зря»: миф одной фразой"),
        ("myth", "medium", "think", "В чём миф"),
        ("truth", "medium", "point", "Как на самом деле и почему (источник)"),
        ("do", "medium", "hold", "Что делать вместо этого"),
        ("loop", "close", "wave", "Вопрос зрителю")]},
}

AI_WORDS = re.compile(r"(\bии\b|\bai\b|нейросет|виртуальн|синтетическ|сгенерирован|цифров\w* персонаж)", re.I)
PLACEHOLDER = re.compile(r"<[^<>]{2,}>")
HUMAN_CLAIM = re.compile(
    r"\b(я|мы)\s+(живой|живая|живые|настоящ\w+|реальн\w+)\s+(человек|люди|бабушк\w+|дедушк\w+|блогер\w*|женщин\w+|мужчин\w+)"
    r"|\bя\s+не\s+(ии|ai|бот|нейросеть|робот|персонаж)\b|\bэто\s+не\s+(ии|нейросеть)\b|\bбез\s+нейросет\w*\b", re.I)
TESTIMONIAL = re.compile(
    r"\b(я|мы)\s+(сам\w*\s+)?(попробовал\w*|пробовал\w*|пользуюсь|пользуемся|пользовал\w*сь|использую|используем|купил\w*|"
    r"заказал\w*|покупаю|покупаем|беру\s+только|проверил\w*\s+на\s+себе|проверил\w*)\b|\bмне\s+помогл\w*|\bу\s+меня\s+(вырос\w*|получил\w*)\s+после\b",
    re.I)
MEDICAL = re.compile(
    r"\b(лечит|вылечит|вылечил\w*|излечит\w*|исцел\w*|от\s+рака|от\s+давлени\w+|от\s+диабет\w+|вместо\s+(врача|лекарств\w*)|"
    r"антибиотик\w*|похуде\w*\s+на\s+\d+)", re.I)
GUARANTEE = re.compile(r"(гарантир\w*|100\s*%|сто\s+процентов|точно\s+вырастет|никогда\s+не\s+болеет)", re.I)
EVASION = re.compile(
    r"(\badb\b|magisk|xposed|антидетект\w*|anti-?detect|ферм\w*\s+(телефон\w*|устройств\w*|аккаунт\w*)|device\s+farm|"
    r"мультиаккаунт\w*|multi-?account|накрут\w*|прогрев\w*\s+аккаунт\w*|обход\w*\s+(детект\w*|модерац\w*|блокир\w*|лимит\w*|алгоритм\w*)|"
    r"подмен\w*\s+(imei|отпечат\w*|fingerprint)|ротаци\w*\s+прокси|бот\w*\s+для\s+(лайк\w*|просмотр\w*|подписчик\w*|комментари\w*))", re.I)
CTA_KIDS = re.compile(r"(подпиш|лайк|коммент|ставь|жми|колокольч)", re.I)
DIGITS = re.compile(r"\d")


def templates() -> list[str]:
    return sorted(p.stem for p in TEMPLATES.glob("*.json"))


def _read(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ShortsError(f"no file {p}") from None
    except json.JSONDecodeError as e:
        raise ShortsError(f"{p}: invalid JSON ({e})") from e


def _write(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _slug(text: str) -> str:
    tr = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p",
                                                     "r", "s", "t", "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
    s = "".join(tr.get(c, c) for c in text.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:40].rstrip("-")) or "episode"


def words(text: str) -> int:
    return len(re.findall(r"[\wёЁ]+(?:[-'][\wёЁ]+)*", text or ""))


def speech_sec(text: str) -> float:
    return round(words(text) / WPS, 2)


# ------------------------------------------------------------------------------------------------ persona-new
def new(directory: str, template: str = "garden", name: str | None = None) -> dict:
    src = TEMPLATES / f"{template}.json"
    if not src.exists():
        raise ShortsError(f"no persona template {template!r}; templates: {', '.join(templates())}")
    d = Path(directory)
    dst = d / "persona.json"
    if dst.exists():
        raise ShortsError(f"{dst} exists (never overwritten)")
    p = _read(src)
    if name:
        p["name"] = name
    _write(dst, p)
    (d / "episodes").mkdir(parents=True, exist_ok=True)
    return {"persona": str(dst), "template": template,
            "next": [f"edit {dst}: name, handle, look, place, voice, series (keep kind=synthetic and the disclosure block)",
                     f"python3 tools/shorts.py persona-check {d}",
                     f"python3 tools/shorts.py persona-plan {d} \"тема ролика\" --format tip"]}


def load_persona(path: str | Path) -> tuple[dict, Path]:
    p = Path(path)
    for cand in (p / "persona.json", p.parent / "persona.json", p.parent.parent / "persona.json", p.parent.parent.parent / "persona.json"):
        if cand.exists():
            return _read(cand), cand.parent
    if p.is_file() and p.name == "persona.json":
        return _read(p), p.parent
    raise ShortsError(f"no persona.json at or above {p}")


# ------------------------------------------------------------------------------------------------ persona-plan
def plan(directory: str, topic: str, fmt: str = "tip", engine: str | None = None, slug: str | None = None,
         ad: bool = False) -> dict:
    persona, root = load_persona(directory)
    if fmt not in FORMATS:
        raise ShortsError(f"format {fmt!r}: use {', '.join(FORMATS)}")
    eng = engine or persona.get("engine", "toon")
    if eng not in ("toon", "ai"):
        raise ShortsError("engine: toon (free, drawn by code) | ai (prompt pack for an AI video model + persona-cut)")
    eps = root / "episodes"
    n = len([x for x in eps.glob("*") if x.is_dir()]) + 1 if eps.exists() else 1
    ed = eps / f"{n:02d}-{slug or _slug(topic)}"
    if (ed / "plan.json").exists():
        raise ShortsError(f"{ed / 'plan.json'} exists (never overwritten)")
    beats = []
    for bid, shot, pose, hint in FORMATS[fmt]["beats"]:
        b = {"id": bid, "shot": shot, "say": f"<{hint}>"}
        if eng == "toon":
            b.update({"pose": pose, "emotion": "smile" if bid in ("hook", "loop", "proof") else "calm"})
        else:
            b["action"] = "<что делает персонаж в кадре (одно действие)>"
        beats.append(b)
    pl = {"schema": "persona-episode/1", "topic": topic, "format": fmt, "engine": eng, "audience": persona.get("audience_kind", "general"),
          "range": list(FORMATS[fmt]["range"]), "beats": beats,
          "sources": ["<ссылка на источник фактов (агроном, институт, инструкция производителя); убрать, если цифр и фактов нет>"],
          "ad": None}
    if ad:
        pl["ad"] = {"market": persona.get("market", "ru"), "advertiser": "<юрлицо или ИП рекламодателя>", "erid": "<токен erid из ОРД>",
                    "product": "<что рекламируем>", "claims": [{"claim": "<свойство товара>", "source": "<где это подтверждено>"}],
                    "banner": None}
    _write(ed / "plan.json", pl)
    return {"plan": str(ed / "plan.json"), "format": fmt, "engine": eng, "range_s": FORMATS[fmt]["range"],
            "next": [f"fill every <...> in {ed / 'plan.json'} (lines in the persona voice, short; facts need sources)",
                     f"python3 tools/shorts.py persona-check {ed}", f"python3 tools/shorts.py persona-build {ed}"]}


# ------------------------------------------------------------------------------------------------ persona-check
def _texts_persona(p: dict) -> list[tuple[str, str]]:
    out = [("name", str(p.get("name", ""))), ("bio", str((p.get("disclosure") or {}).get("bio", "")))]
    for k in ("catchphrases", "topics"):
        out += [(f"{k}[{i}]", str(x)) for i, x in enumerate(p.get(k) or [])]
    out.append(("voice", json.dumps(p.get("voice") or {}, ensure_ascii=False)))
    out.append(("publishing", json.dumps({k: v for k, v in (p.get("publishing") or {}).items() if k != "never"}, ensure_ascii=False)))
    return out


def check_persona(p: dict, base: Path | None = None) -> list[dict]:
    pr: list[dict] = []

    def add(level, where, msg):
        pr.append({"level": level, "where": where, "msg": msg})
    if p.get("kind") != "synthetic":
        add("error", "kind", "kind must be \"synthetic\": the persona is an AI character and is presented as one")
    dis = p.get("disclosure") or {}
    if not AI_WORDS.search(str(dis.get("bio", ""))):
        add("error", "disclosure.bio", "bio must say the persona is AI (например: «ИИ-персонаж. Видео созданы с помощью нейросетей»)")
    if not str(dis.get("label", "")).strip():
        add("error", "disclosure.label", "on-screen label is required (\"ИИ-персонаж\")")
    if not AI_WORDS.search(str(dis.get("description_line", ""))):
        add("error", "disclosure.description_line", "every description needs one line that says the video is made with AI")
    look = p.get("look") or {}
    if look.get("real_person") and not look.get("consent"):
        add("error", "look.real_person", "looks like a real person: only with written consent (look.consent = file), never a celebrity")
    voice = p.get("voice") or {}
    if voice.get("clone_of") and not voice.get("consent"):
        add("error", "voice.clone_of", "a cloned real voice needs written consent of that person (voice.consent)")
    for where, t in _texts_persona(p):
        if HUMAN_CLAIM.search(t):
            add("error", where, "the persona must not claim to be a real human")
        if EVASION.search(t):
            add("error", where, "account/device automation, fake engagement or detection evasion is not supported "
                                "(platform rules, FTC 16 CFR 465.8): publish manually or via official APIs")
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if not str(k).startswith("_"):
                    yield from walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from walk(v, f"{path}[{i}]")
        elif isinstance(o, str):
            yield path, o
    for where, t in walk(p, ""):
        if PLACEHOLDER.search(t):
            add("error", where, f"fill the placeholder {PLACEHOLDER.search(t).group(0)[:50]}")
    if not (p.get("series") or []):
        add("warn", "series", "add 2-3 recurring series (format + name): a persona grows on repeatable formats")
    if p.get("audience_kind") == "kids":
        add("info", "audience_kind", "kids: mark videos as made for kids, no calls to comment/like/subscribe, no ads")
    return pr


def _beats_text(pl: dict) -> list[tuple[str, str]]:
    out = []
    for i, b in enumerate(pl.get("beats") or []):
        out.append((f"beats[{i}].say", str(b.get("say", ""))))
        if b.get("action"):
            out.append((f"beats[{i}].action", str(b["action"])))
        if b.get("title"):
            out.append((f"beats[{i}].title", str(b["title"])))
    return out


def check_episode(pl: dict, persona: dict) -> tuple[list[dict], dict]:
    pr: list[dict] = []

    def add(level, where, msg):
        pr.append({"level": level, "where": where, "msg": msg})
    beats = pl.get("beats") or []
    if not beats:
        add("error", "beats", "no beats")
    texts = _beats_text(pl)
    for where, t in texts + [("topic", str(pl.get("topic", "")))]:
        if PLACEHOLDER.search(t):
            add("error", where, f"unfilled placeholder: {PLACEHOLDER.search(t).group(0)[:60]}")
        if HUMAN_CLAIM.search(t):
            add("error", where, "the persona must not claim to be a real human")
        if MEDICAL.search(t):
            add("error", where, f"medical promise ({MEDICAL.search(t).group(0)}): an AI persona gives no medical advice")
        if GUARANTEE.search(t):
            add("warn", where, f"guarantee ({GUARANTEE.search(t).group(0)}): soften or prove")
        if EVASION.search(t):
            add("error", where, "automation / fake engagement / evasion is not supported")
    srcs = [s for s in (pl.get("sources") or []) if s and not PLACEHOLDER.search(str(s))]
    if any(DIGITS.search(t) for w, t in texts if w.endswith(".say")) and not srcs:
        add("warn", "sources", "numbers in the advice: add a source (agronomist, manufacturer instruction, study)")
    if any(PLACEHOLDER.search(str(s)) for s in (pl.get("sources") or [])):
        add("error", "sources", "replace or delete the <source> placeholder")
    eng = pl.get("engine", "toon")
    total = 0.0
    chunk = float((persona.get("ai") or {}).get("chunk", 8))
    for i, b in enumerate(beats):
        sec = speech_sec(b.get("say", ""))
        total += sec + BEAT_PAUSE
        if eng == "ai" and sec > chunk:
            add("error", f"beats[{i}].say", f"{sec:.1f} s of speech > {chunk:.0f} s clip limit (ai.chunk): split the beat")
        if eng == "ai" and not str(b.get("action", "")).strip():
            add("warn", f"beats[{i}].action", "describe one action for the clip")
    if beats:
        hw = words(beats[0].get("say", ""))
        if hw > 12:
            add("warn", "beats[0].say", f"hook has {hw} words: keep it under 12 (about 2-3 s)")
    lo, hi = (pl.get("range") or FORMATS.get(pl.get("format", "tip"), FORMATS["tip"])["range"])
    if beats and not PLACEHOLDER.search(" ".join(t for _, t in texts)) and not (lo * 0.8 <= total <= hi * 1.15):
        add("warn", "duration", f"about {total:.0f} s of speech, format wants {lo}-{hi} s")
    ad = pl.get("ad")
    kids = (pl.get("audience") or persona.get("audience_kind")) == "kids"
    if kids:
        for where, t in texts:
            if where.endswith(".say") and CTA_KIDS.search(t):
                add("error", where, "kids: no calls to like / comment / subscribe")
        if ad:
            add("error", "ad", "kids: no advertising inside videos made for kids")
    if ad:
        market = str(ad.get("market", "ru")).lower()
        for k in ("advertiser", "product"):
            if not str(ad.get(k, "")).strip() or PLACEHOLDER.search(str(ad.get(k, ""))):
                add("error", f"ad.{k}", f"ad needs {k}")
        if market == "ru" and (not str(ad.get("erid", "")).strip() or PLACEHOLDER.search(str(ad.get("erid", "")))):
            add("error", "ad.erid", "RU ad: token erid from an ОРД is required (38-ФЗ ст. 18.1), plus «Реклама» and the advertiser")
        for j, c in enumerate(ad.get("claims") or []):
            if not str((c or {}).get("source", "")).strip() or PLACEHOLDER.search(str((c or {}).get("source", ""))):
                add("error", f"ad.claims[{j}]", "every product claim needs a source (official page, test, certificate)")
        for where, t in texts:
            if TESTIMONIAL.search(t):
                add("error", where, f"first-hand testimonial ({TESTIMONIAL.search(t).group(0)}): an AI persona has not used the "
                                    "product (FTC 16 CFR 465.2). Say what the product is and what the source says")
    dis = persona.get("disclosure") or {}
    plat = {"youtube": "YouTube Studio > Сведения > «Использование ИИ» (AI use): Да, если персонаж реалистичный",
            "tiktok": "TikTok: переключатель «Контент создан ИИ» (AI-generated content) при публикации",
            "vk": "VK / RUTUBE / Дзен: отметка ИИ, если площадка её даёт (243-ФЗ: площадки от 500 тыс. дают инструмент), иначе строка в описании",
            "bio": dis.get("bio", ""), "label": dis.get("label", ""), "description_line": dis.get("description_line", "")}
    info = {"speech_s": round(total, 1), "beats": len(beats), "engine": eng, "disclosure": plat}
    if ad:
        info["ad_marking"] = ("RU: «Реклама. <рекламодатель>. erid: <токен>» в кадре и в описании; блогер с 10 000+ подписчиков "
                              "должен быть в реестре РКН, иначе рекламу размещать нельзя" if str(ad.get("market", "ru")).lower() == "ru"
                              else "US/EU: #ad / «Paid partnership» в начале описания и в кадре, без отзывов «я попробовала»")
    return pr, info


def check(path: str) -> dict:
    p = Path(path)
    persona, root = load_persona(p)
    probs = [dict(x, file="persona.json") for x in check_persona(persona, root)]
    info: dict = {}
    eps = []
    if p.is_dir() and (p / "plan.json").exists():
        eps = [p / "plan.json"]
    elif p.is_file() and p.name == "plan.json":
        eps = [p]
    elif p.is_dir() and (p / "persona.json").exists():
        eps = sorted((p / "episodes").glob("*/plan.json"))
    for e in eps:
        pr, inf = check_episode(_read(e), persona)
        probs += [dict(x, file=str(e.relative_to(root))) for x in pr]
        info[str(e.relative_to(root))] = inf
    errors = [x for x in probs if x["level"] == "error"]
    return {"ok": not errors, "errors": len(errors), "problems": probs, "episodes": info}


# ------------------------------------------------------------------------------------------------ persona-build
def _cap(x: str) -> str:
    x = (x or "").strip().rstrip(".")
    return x[:1].upper() + x[1:]


def _character_block(p: dict) -> str:
    lk = p.get("look") or {}
    parts = [f"{p.get('name', 'персонаж')}: {lk.get('age', '')}".strip(": "), lk.get("face", ""), lk.get("hair", ""),
             lk.get("wardrobe", ""), lk.get("signature", "")]
    return ". ".join(_cap(x) for x in parts if x and x.strip()) + "."


HOOK_SEC, LONG_SEC = 3.4, 4.5     # toon-check wants the hook scene <= 3.5 s; longer beats get a cut per sentence
ALT_SHOT = {"close": "medium", "medium": "close", "wide": "medium"}
SHOT_NEXT = {"close": "medium", "medium": "wide", "wide": "close"}


def _has_anchor(o) -> bool:
    if isinstance(o, dict):
        return any((k == "on" and not isinstance(v, bool)) or k.endswith("_on") or _has_anchor(v) for k, v in o.items())
    return isinstance(o, list) and any(_has_anchor(v) for v in o)


def _pieces(say: str, first: bool) -> list[str]:
    """Sentences of one beat as separate scenes (a cut every sentence): the hook gets its first sentence alone."""
    if speech_sec(say) <= (HOOK_SEC if first else LONG_SEC):
        return [say]
    out: list[str] = []
    for part in re.split(r"(?<=[.!?…])\s+", say.strip()):
        if out and (words(part) < 3 or words(out[-1]) < 3):
            out[-1] = out[-1] + " " + part
        else:
            out.append(part)
    return out


def _title_piece(parts: list[str], title: str) -> int:
    """The title plate goes on the sentence that says it ("12-16 часов света" -> "Свети ... часов")."""
    stems = {w[:4].lower() for w in re.findall(r"[\wёЁ]{3,}", title or "")}
    best = [len(stems & {w[:4].lower() for w in re.findall(r"[\wёЁ]{3,}", x)}) for x in parts]
    return best.index(max(best)) if best and max(best) > 0 else 0


def _toon_episode(pl: dict, p: dict, slug: str) -> dict:
    """Host episode: the persona talks to camera; every sentence of a long beat is a new shot size (never two equal
    shots in a row) and a titled beat (not the hook) cuts to a close-up card of the persona's item (`toon.cutaway`)."""
    tn = p.get("toon") or {}
    host = dict({"look": "granny"}, **(tn.get("cast") or {}))
    host.setdefault("name", p.get("name", ""))
    cut = tn.get("cutaway") or {}
    scenes, prev = [], None
    for i, b in enumerate(pl["beats"]):
        actor = {"id": "host", "pose": b.get("pose", "stand"), "emotion": b.get("emotion", "calm"), "face": "front", "gaze": "camera", "at": 0.5}
        if b.get("hold"):
            actor["hold"] = b["hold"]
        extra = {k: b[k] for k in ("props", "scheme", "fx", "camera", "transition") if b.get(k)}
        parts = [b["say"]] if _has_anchor(extra) else _pieces(b["say"], i == 0)
        base = b.get("shot", "medium")
        tj = _title_piece(parts, b.get("title", ""))
        for j, say in enumerate(parts):
            if i and j == tj and b.get("title") and (cut.get("item") or cut.get("icon")) and "scheme" not in extra:
                card = {"type": "closeup", "bg": cut.get("bg", "paper"), "title": b["title"]}
                card.update({k: cut[k] for k in ("item", "icon", "color", "on") if k in cut})
                if b.get("title_sub"):
                    card["sub"] = b["title_sub"]
                scenes.append({"say": say, "scheme": card})
                prev = None
                continue
            shot = base if j == 0 else ALT_SHOT.get(base, "medium")
            if shot == prev:
                shot = SHOT_NEXT[shot]
            prev = shot
            sc = {"say": say, "shot": shot, "actors": [dict(actor)]}
            if i == 0 and j == 0:
                sc["set"] = tn.get("set", "dacha") if isinstance(tn.get("set", "dacha"), dict) else {"id": tn.get("set", "dacha"), "time": tn.get("time", "day")}
            if b.get("set") and j == 0:
                sc["set"] = b["set"]
            if b.get("title") and j == tj:
                sc["hud"] = [{"type": "title", "text": b["title"]}]
            for k, v in extra.items():
                if j == 0 or k not in ("camera", "transition"):
                    sc[k] = v
            scenes.append(sc)
    dis = p.get("disclosure") or {}
    ep = {"title": pl["topic"], "slug": slug, "aspect": tn.get("aspect", "9:16"), "lang": p.get("language", "ru"),
          "voice": tn.get("voice", "ru-female-1"), "speed": float(tn.get("speed", 1.0)),
          "brand": " · ".join(x for x in (p.get("handle", ""), dis.get("label", "")) if x),
          "style": dict({"captions": "caps"}, **(tn.get("style") or {})), "cast": {"host": host}, "scenes": scenes}
    if (pl.get("audience") or p.get("audience_kind")) == "kids":
        ep["audience"] = "kids"
    return ep


def _ai_pack(pl: dict, p: dict) -> tuple[list[dict], str, str]:
    ai = p.get("ai") or {}
    chunk = float(ai.get("chunk", 8))
    aspect = ai.get("aspect", "9:16")
    who = _character_block(p)
    place = _cap((p.get("place") or {}).get("main", ""))
    style = ai.get("style", "реалистичное видео со смартфона, мягкий дневной свет, естественные цвета")
    neg = ai.get("negative", "текст в кадре, субтитры, логотипы, водяные знаки, лишние пальцы, другое лицо, другая одежда, музыка")
    voice = (p.get("voice") or {}).get("tone", "")
    shots, md = [], []
    md.append(f"# Пакет промптов: {pl['topic']}\n")
    md.append("Сначала один раз: лист персонажа (character sheet) и 2-3 референса места. Их же прикладывать к КАЖДОМУ клипу "
              "(reference / ingredients / omni reference), чтобы лицо и одежда не менялись.\n")
    md.append(f"## Лист персонажа (картинка)\n{who} Вид спереди, в три четверти и в профиль на нейтральном фоне, рост целиком "
              f"и крупный план лица, одна и та же одежда. {style}. Без текста.\n")
    md.append(f"## Место (картинка)\n{place}. Вертикальный кадр {aspect}, без людей. {_cap(style)}.\n")
    for i, b in enumerate(pl["beats"], 1):
        dur = max(3.0, min(chunk, round(speech_sec(b["say"]) + 1.2, 1)))
        shot_ru = {"close": "крупный план", "medium": "средний план", "wide": "общий план"}.get(b.get("shot", "medium"), "средний план")
        act = _cap(b.get("action", ""))
        start = f"{who} {act}. {place}. {_cap(shot_ru)}, вертикальный кадр {aspect}. {_cap(style)}. Без текста."
        video = (f"Используй референсы персонажа и места без изменений. {act}. Персонаж говорит по-русски"
                 f"{', ' + voice if voice else ''}: «{b['say']}». Камера: {shot_ru}, лёгкая ручная съёмка. "
                 f"Длительность {dur:.0f} с. Синхрон губ с речью. Без музыки и без субтитров.")
        shots.append({"n": i, "beat": b["id"], "say": b["say"], "seconds": dur, "file": f"clips/{i:02d}.mp4",
                      "frame_prompt": start, "video_prompt": video})
        md.append(f"## Клип {i:02d} ({b['id']}, {dur:.0f} с) -> clips/{i:02d}.mp4\n**Стартовый кадр:** {start}\n\n**Видео:** {video}\n\n"
                  f"**Не надо:** {neg}\n")
    md.append("## Сборка\nКлипы положить в `clips/` (01.mp4, 02.mp4, ...), затем `python3 tools/shorts.py persona-cut ЭПИЗОД`: "
              "склейка, субтитры, плашка «ИИ-персонаж», громкость -14 LUFS.\n"
              "Платные модели: только с разрешения человека (SHORTS_ALLOW_PAID=1 и бюджет) или он генерирует сам в своём аккаунте.\n")
    script = "\n".join(b["say"] for b in pl["beats"]) + "\n"
    return shots, "\n".join(md), script


def _meta(pl: dict, p: dict) -> str:
    dis = p.get("disclosure") or {}
    ad = pl.get("ad")
    lines = [f"Тема: {pl['topic']}", "", "Описание (основа, добавить 1-2 фразы о пользе ролика):"]
    if ad:
        if str(ad.get("market", "ru")).lower() == "ru":
            lines.append(f"Реклама. {ad.get('advertiser', '')}. erid: {ad.get('erid', '')}")
        else:
            lines.append("#ad Paid partnership")
    lines += [dis.get("description_line", ""), *([f"Источник: {s}" for s in pl.get("sources") or []]), "",
              f"Био канала: {dis.get('bio', '')}", "", "При публикации (вручную или через официальный планировщик площадки):",
              "- YouTube: Сведения > «Использование ИИ» (AI use) = Да для реалистичного персонажа (для рисованного по желанию);",
              "- TikTok: включить «Контент создан ИИ» (AI-generated content);",
              "- VK / RUTUBE / Дзен: отметка ИИ, если есть, иначе строка в описании выше;",
              "- никаких покупных просмотров, лайков, подписчиков и сеток аккаунтов."]
    if ad:
        lines.append("- реклама: плашка «Реклама» в кадре, рекламодатель и erid в описании; отзывы от лица персонажа запрещены.")
    if (pl.get("audience") or p.get("audience_kind")) == "kids":
        lines.append("- дети: отметить «Для детей», без призывов и без рекламы.")
    return "\n".join(lines) + "\n"


def build(path: str, force: bool = False) -> dict:
    ed = Path(path)
    if ed.is_file():
        ed = ed.parent
    pl = _read(ed / "plan.json")
    persona, root = load_persona(ed)
    rep = check(str(ed))
    if not rep["ok"] and not force:
        raise ShortsError("persona-check has errors, fix them first:\n" + "\n".join(
            f"- {x['where']}: {x['msg']}" for x in rep["problems"] if x["level"] == "error"))
    slug = ed.name
    out: dict = {"episode": str(ed), "engine": pl.get("engine", "toon"), "check": {"ok": rep["ok"], "errors": rep["errors"]}}
    epf, stamp = ed / "episode.json", ed / ".episode.sha1"       # stamp = hash of the episode.json this command wrote
    toon = pl.get("engine", "toon") == "toon"
    if toon and epf.exists() and not force:
        if not stamp.exists() or stamp.read_text().strip() != hashlib.sha1(epf.read_bytes()).hexdigest():
            raise ShortsError(f"{epf} was edited by hand after the last build: keep it (toon-preview / toon-render) "
                              "or rebuild with --force (hand edits are lost)")
    (ed / "meta.txt").write_text(_meta(pl, persona), encoding="utf-8")
    out["meta"] = str(ed / "meta.txt")
    if toon:
        ep = _toon_episode(pl, persona, slug)
        _write(epf, ep)
        stamp.write_text(hashlib.sha1(epf.read_bytes()).hexdigest() + "\n")
        from ..toon.cli import check_cmd
        tc = check_cmd(str(ed))
        out.update({"toon_episode": str(ed / "episode.json"), "toon_check": {"ok": tc["ok"], "problems": tc.get("problems", [])[:12]},
                    "next": [f"python3 tools/shorts.py toon-preview {ed}   # смотреть build/sheet.jpg",
                             f"python3 tools/shorts.py toon-render {ed}"]})
    else:
        shots, md, script = _ai_pack(pl, persona)
        _write(ed / "shots.json", shots)
        (ed / "prompts.md").write_text(md, encoding="utf-8")
        (ed / "script.txt").write_text(script, encoding="utf-8")
        (ed / "clips").mkdir(exist_ok=True)
        out.update({"shots": str(ed / "shots.json"), "prompts": str(ed / "prompts.md"), "clips_expected": [s["file"] for s in shots],
                    "next": ["generate the clips with the prompts (the human's own account, or paid API only with permission)",
                             f"python3 tools/shorts.py persona-cut {ed}"]})
    return out


# ------------------------------------------------------------------------------------------------ persona-cut
def _dur(f: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise ShortsError(f"cannot read {f}") from None


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def spread_srt(lines: list[str], durs: list[float], lead: float = 0.25) -> str:
    """Captions from the planned lines, one line per clip, words spread over the clip (no ASR needed)."""
    out, t0, n = [], 0.0, 1
    for text, d in zip(lines, durs):
        ws = text.split()
        if ws:
            span = max(0.5, d - lead - 0.3)
            per = span / len(ws)
            for j in range(0, len(ws), 3):
                a = t0 + lead + j * per
                b = t0 + lead + min(len(ws), j + 3) * per
                out.append(f"{n}\n{_srt_time(a)} --> {_srt_time(b)}\n{' '.join(ws[j:j + 3])}\n")
                n += 1
        t0 += d
    return "\n".join(out)


def cut(path: str, clips: str | None = None, out: str | None = None, check_render: bool = True) -> dict:
    ed = Path(path)
    if ed.is_file():
        ed = ed.parent
    pl = _read(ed / "plan.json")
    persona, _ = load_persona(ed)
    rep = check(str(ed))
    if not rep["ok"]:
        raise ShortsError("persona-check has errors: fix them before assembling")
    cdir = Path(clips) if clips else ed / "clips"
    files = sorted(f for f in cdir.glob("*.mp4") if f.is_file())
    if not files:
        raise ShortsError(f"no clips in {cdir} (01.mp4, 02.mp4, ...): generate them from prompts.md first")
    lines = [re.sub(r"\*", "", b.get("say", "")) for b in pl.get("beats", [])]
    notes = []
    if len(files) != len(lines):
        notes.append(f"{len(files)} clips for {len(lines)} beats: captions follow the clip order")
    durs = [_dur(f) for f in files]
    build_dir = ed / "build"
    build_dir.mkdir(exist_ok=True)
    srt = build_dir / "captions.srt"
    srt.write_text(spread_srt(lines[:len(files)] + [""] * max(0, len(files) - len(lines)), durs), encoding="utf-8")
    dis = persona.get("disclosure") or {}
    spec = {"out": str(Path(out).resolve()) if out else str((ed / f"{ed.name}.mp4").resolve()),
            "main": {"pieces": [{"src": str(f.resolve()), "start": 0.0, "end": round(d - 0.02, 3)} for f, d in zip(files, durs)],
                     "track": "group", "snap": "off", "words": "none"},
            "captions": {"srt": str(srt.resolve()), "timebase": "final", "style": (persona.get("captions") or {}).get("style", "clean"),
                         "accent": (persona.get("captions") or {}).get("accent", "#FFD84D")},
            "label": [{"text": dis.get("label", "ИИ-персонаж"), "pos": "tl"}]}
    ad = pl.get("ad")
    if ad:
        mark = (f"Реклама. {ad.get('advertiser', '')}. erid: {ad.get('erid', '')}" if str(ad.get("market", "ru")).lower() == "ru"
                else "#ad Paid partnership")
        spec["label"].append({"text": mark, "pos": "tl", "size": 26})
        if ad.get("banner"):
            spec["banner"] = dict(ad["banner"])
    _write(build_dir / "stack.json", spec)
    from ..stack import render_stack
    res = render_stack(spec, ed, Path(spec["out"]), check=check_render)
    return {"out": spec["out"], "clips": len(files), "duration": res.get("duration"), "labels": [x["text"] for x in spec["label"]],
            "spec": str(build_dir / "stack.json"), "notes": notes, "meta": str(ed / "meta.txt")}
