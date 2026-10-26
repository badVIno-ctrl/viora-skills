"""Titles, description, pinned comment, TikTok caption (COMMON.md 8, research 2.3).

The model writes the words (taste), this module keeps the rules:
  DIR/metadata.draft.json (written by the agent, optional):
    {"titles": [{"text": "...", "loudness": 1, "for": "intrigue", "why": "..."}, ...],   5-7, loud -> conservative
     "descriptions": [{"tone": "loud|medium|calm", "psychology": "trigger used", "text": "first 2 lines stand alone"}] x 3,
     "cover_texts": [{"tone": "loud", "text": "3-5 WORDS"}, {"tone": "medium", ...}, {"tone": "calm", ...}],
     "summary": "1-2 sentences, key words first", "cta": "",
     "hashtags": {"title": [...], "top": [...], "bottom": [...], "tiktok": [...]},
     "pinned": ["line 1", "line 2", "line 3"], "recommended": 2, "recommended_description": "loud|medium|calm"}
  Titles: 5-7, loud -> calm, all three tiers present. Loud pattern: CAPS hook + one emoji + #shorts and niche tags.
  Descriptions: exactly 3 (loud, medium, calm), 3-5 hashtags at the very end, links/credits/chapters added here.
  If there is no draft, a rule-based draft is made from the plan (works, but the model should improve it).
Links come only from the plan/prefs (never invented). Output: DIR/metadata.json + DIR/metadata.md.
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

from .. import memory as M
from ..util import HASHTAG, count_emoji, fix_dashes, has_long_dash, read_json, write_json
from .tones import TONES, derive_cover_texts, loudness_of, normalize_cover_texts, tone_name, tone_of

MAX_TITLE = 100
DEFAULT_TAGS = {
    "ru": {"title": ["#shorts", "#нейросети", "#ии"], "bottom": ["#shorts", "#ии", "#ai", "#полезное"]},
    "en": {"title": ["#shorts", "#ai", "#tech"], "bottom": ["#shorts", "#ai", "#tools", "#productivity"]},
}
CTA = {"ru": "", "en": ""}
EMOJI_LOUD = "\U0001F631"  # the author's pattern uses one emoji in the loud variant
AD_WORD = re.compile(r"реклам|\bad\b|#ad\b|advertis|sponsor|спонсор|paid partnership", re.I)
HOOK_CHARS = 40  # the loud hook must land before this position (the feed cuts the title)


def _tag(t: str) -> str:
    t = t.strip()
    if not t:
        return ""
    t = "#" + re.sub(r"[^\w]", "", t.lstrip("#"), flags=re.U).lower()
    return t if len(t) > 1 else ""


def _uniq(tags: list[str]) -> list[str]:
    out, seen = [], set()
    for t in tags:
        t = _tag(t)
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out


def _caps_ratio(text: str) -> float:
    letters = [c for c in HASHTAG.sub("", text) if c.isalpha()]
    return sum(c.isupper() for c in letters) / max(1, len(letters))


def _topic(plan: dict, manifest: dict) -> tuple[str, str]:
    md = plan.get("metadata") or {}
    topic = md.get("topic") or ""
    hook = ""
    for s in plan["scenes"]:
        if s.get("on_screen_text"):
            hook = s["on_screen_text"]
            break
    if not topic:
        topic = hook or (plan["scenes"][0].get("say", "").split(".")[0])
    return fix_dashes(topic.strip()), fix_dashes(hook.strip())


def written(text: str, subs: dict[str, str]) -> str:
    """Spoken form -> written form using captions.subs (e.g. 'эйч ти эм эл' -> 'HTML')."""
    for spoken, wr in sorted(subs.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(r"(?<!\w)" + re.escape(spoken) + r"(?!\w)", wr, text, flags=re.I | re.U)
    return re.sub(r"\s{2,}", " ", text).strip()


def auto_draft(plan: dict, manifest: dict, lang: str) -> dict:
    """Rule-based fallback. Honest: only words that are in the plan."""
    topic, hook = _topic(plan, manifest)
    subs = (plan.get("captions") or {}).get("subs") or {}
    first_say = written(fix_dashes(plan["scenes"][0].get("say", "")), subs)
    tags = _uniq((plan.get("metadata") or {}).get("hashtags") or DEFAULT_TAGS.get(lang, DEFAULT_TAGS["en"])["title"])
    base = _short(hook or topic, HOOK_CHARS)
    t = topic.rstrip(".!?")
    if _caps_ratio(t) > 0.6:  # calm variants never shout: sentence case
        t = t[:1].upper() + t[1:].lower()
    if lang == "ru":
        titles = [
            {"text": f"{base.upper()} {EMOJI_LOUD}", "loudness": 1, "for": "intrigue", "why": "капс, эмодзи, крупное обещание"},
            {"text": f"{base.upper()}", "loudness": 2, "for": "intrigue", "why": "капс без эмодзи, для ленты"},
            {"text": f"{t[:1].upper() + t[1:]}: смотри, как это работает", "loudness": 3, "for": "intrigue", "why": "любопытство, без капса"},
            {"text": f"{t[:1].upper() + t[1:]}", "loudness": 4, "for": "search", "why": "суть в начале"},
            {"text": f"{t[:1].upper() + t[1:]} - коротко и по делу", "loudness": 5, "for": "search", "why": "поисковая фраза, спокойно"},
        ]
    else:
        titles = [
            {"text": f"{base.upper()} {EMOJI_LOUD}", "loudness": 1, "for": "intrigue", "why": "caps, one emoji, big promise"},
            {"text": f"{base.upper()}", "loudness": 2, "for": "intrigue", "why": "caps without emoji, for the feed"},
            {"text": f"{t[:1].upper() + t[1:]}: watch how it works", "loudness": 3, "for": "intrigue", "why": "curiosity, no caps"},
            {"text": f"{t[:1].upper() + t[1:]}", "loudness": 4, "for": "search", "why": "key words first"},
            {"text": f"{t[:1].upper() + t[1:]} - quick guide", "loudness": 5, "for": "search", "why": "search phrase, calm"},
        ]
    # one more middle variant from the first spoken line (often the strongest hook)
    if first_say:
        sentence = re.split(r"(?<=[.!?])\s", first_say)[0].rstrip(".")
        titles.insert(2, {"text": sentence, "loudness": 3, "for": "intrigue", "why": "first line of the video" if lang != "ru" else "первая фраза ролика"})
    for x in titles:
        x["hashtags"] = tags[:{"loud": 6, "medium": 3, "calm": 2}[tone_of(x["loudness"])]]
    summary = first_say or topic
    ad = _ad_info(plan, {})
    descriptions = auto_descriptions(hook or topic, topic, summary, lang, ad, tags, _uniq(DEFAULT_TAGS.get(lang, DEFAULT_TAGS["en"])["bottom"]))
    covers = derive_cover_texts(hook, topic, lang, upper=True)
    return {"titles": titles, "summary": summary, "cta": CTA.get(lang, CTA["en"]),
            "descriptions": descriptions, "cover_texts": covers,
            "hashtags": {"title": tags, "top": tags[1:4] or tags[:3],
                         "bottom": _uniq(DEFAULT_TAGS.get(lang, DEFAULT_TAGS["en"])["bottom"])},
            "recommended": 1, "cover_text": covers[0]["text"], "auto": True}


def _short(text: str, limit: int) -> str:
    """Cut at a word boundary so the hook fits the first `limit` chars."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip(" ,:;-")


def _end(s: str) -> str:
    s = s.strip()
    return s if not s or s[-1] in ".!?" else s + "."


def _ad_info(plan: dict, draft: dict) -> dict | None:
    """Ad plan -> {"name", "url"}; None when it is not an ad. Sources: draft.ad, plan.metadata.ad / advertising."""
    md = plan.get("metadata") or {}
    ad = draft.get("ad") or md.get("ad")
    if isinstance(ad, dict):
        return {"name": ad.get("name", ""), "url": ad.get("url", "")}
    if ad or md.get("advertising") is True:
        return {"name": "", "url": ""}
    return None


def auto_descriptions(hook: str, topic: str, summary: str, lang: str, ad: dict | None,
                      title_tags: list[str], bottom: list[str]) -> list[dict]:
    """Rule-based loud/medium/calm descriptions. Only plan words plus generic calls to action, no invented facts."""
    ru = lang == "ru"
    h = hook.rstrip(".!? ").upper()
    tp = topic.rstrip(".!? ")
    tp = tp[:1].upper() + (tp[1:].lower() if _caps_ratio(tp) > 0.6 else tp[1:])
    sm = _end(summary)
    if ru:
        bodies = {
            "loud": (f"{h} - досмотри до конца, чтобы не пропустить главное.\n{sm} Сохрани, пока не потерял, и отправь тому, кому это нужно.",
                     "любопытство + страх упустить: обещание в первой строке, призыв сохранить"),
            "medium": (f"{tp}: смотри, как это работает на деле.\n{sm} Что показать следующим? Пиши в комментариях.",
                       "любопытство + вовлечение: вопрос зрителю в конце"),
            "calm": (f"{tp}. Коротко о главном.\n{sm} Коротко и по делу, без лишнего.",
                     "информативно: суть сразу, без давления"),
        }
    else:
        bodies = {
            "loud": (f"{h} - watch to the end so you don't miss the main part.\n{sm} Save it before you lose it and send it to someone who needs it.",
                     "curiosity gap + fear of missing out: promise in line one, save prompt"),
            "medium": (f"{tp}: see how it works in practice.\n{sm} What should I show next? Tell me in the comments.",
                       "curiosity + engagement: a question to the viewer"),
            "calm": (f"{tp}. The short version.\n{sm} Short and to the point.",
                     "informative: the point first, no pressure"),
        }
    pool = _uniq(bottom + [t for t in title_tags if t not in bottom])
    count = {"loud": 5, "medium": 4, "calm": 3}
    out = []
    for tone in TONES:
        text, why = bodies[tone]
        if ad is not None:
            who = f" {ad['name']}" if ad.get("name") else ""
            link = f" {ad['url']}" if ad.get("url") else ""
            text += f"\n{'Реклама.' if ru else 'Ad.'}{who}{link}".rstrip()
        out.append({"tone": tone, "psychology": why, "text": text, "hashtags": pool[:count[tone]]})
    return out


def _links(plan: dict, prefs: dict) -> list[tuple[str, str]]:
    bottom = ((plan.get("layout") or {}).get("bottom") or {})
    explicit = list(bottom.get("links") or [])
    if bottom.get("qr_url"):
        explicit.append(bottom["qr_url"])
    for c in (plan.get("layout") or {}).get("cta_in_center", []):
        if c.get("url"):
            explicit.append(c["url"])
        elif c.get("kind") == "link" and c.get("text", "").startswith(("https://", "http://", "t.me/")):
            explicit.append(c["text"] if c["text"].startswith("http") else "https://" + c["text"])
    if explicit:
        return [("", v) for v in dict.fromkeys(explicit)]
    foreign = any((s.get("source") or {}).get("type") in ("film", "video") for s in plan.get("scenes", []))
    if foreign and not (plan.get("metadata") or {}).get("include_profile_links", False):
        return []  # never carry another job's ad into an ad-free movie edit
    pl = prefs.get("links") or {}
    if isinstance(pl, dict):
        return [(k,v) for k,v in pl.items() if isinstance(v,str) and v]
    return [("",v) for v in pl if isinstance(v,str) and v]


def _label(name: str, url: str) -> str:
    if name:
        return name[:1].upper() + name[1:]
    host = urllib.parse.urlsplit(url).netloc.lower()
    if "t.me" in host or "telegram" in host:
        return "Telegram"
    if "youtube" in host or "youtu.be" in host:
        return "YouTube"
    if "tiktok" in host:
        return "TikTok"
    if "instagram" in host:
        return "Instagram"
    return host.replace("www.", "") or "Link"


def _utm(url: str, name: str, source: str) -> str:
    if "t.me/" in url or not url.startswith("http"):
        return url
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(u.query) + [("utm_source", source), ("utm_medium", "short"), ("utm_campaign", name)]
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, urllib.parse.urlencode(q), u.fragment))


def _rec_tone(draft: dict, titles: list[dict], rec: int) -> str:
    v = draft.get("recommended_description")
    if isinstance(v, int) and 1 <= v <= 3:
        return TONES[v - 1]
    return tone_name(v) or (titles[rec]["tone"] if titles else "loud")


def _trailing_tags(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split trailing hashtag-only lines off a body: (body lines, tags found there)."""
    tags: list[str] = []
    while lines and (not lines[-1].strip() or not HASHTAG.sub("", lines[-1]).strip()):
        tags = HASHTAG.findall(lines[-1]) + tags
        lines = lines[:-1]
    return lines, tags


def _descriptions(plan: dict, manifest: dict, draft: dict, titles: list[dict], rec: int, links: list[tuple[str, str]],
                  cta: str, summary: str, bottom: list[str], title_tags: list[str], lang: str,
                  errors: list[str], warnings: list[str]) -> tuple[list[dict], list[str]]:
    """Exactly three descriptions (loud, medium, calm): body from the draft, then CTA, links, credits, chapters, 3-5 hashtags."""
    from ..release import chapters_issues, description_issues
    md = plan.get("metadata") or {}
    ad = _ad_info(plan, draft)
    default_bottom = _uniq(DEFAULT_TAGS.get(lang, DEFAULT_TAGS["en"])["bottom"])
    raw = draft.get("descriptions")
    if not raw:
        topic, hook = _topic(plan, manifest)
        warnings.append("draft has no descriptions: rule-based loud/medium/calm variants were used, write your own in metadata.draft.json")
        raw = auto_descriptions(hook or topic, topic, summary or topic, lang, ad, title_tags, bottom or default_bottom)
    if not isinstance(raw, list) or len(raw) != 3:
        errors.append(f"need exactly 3 descriptions (loud, medium, calm), got {len(raw) if isinstance(raw, list) else 0}")
        raw = [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []
    credits = (manifest.get("author_layer") or {}).get("credits") or []
    chapters = [str(c) for c in md.get("chapters") or []]
    if chapters:
        errors.extend(chapters_issues(md.get("chapters") or [], float(manifest.get("duration", 0))))
    out, used_tags, seen = [], [], set()
    for i, d in enumerate(raw):
        tone = tone_name(d.get("tone"))
        if not tone:
            errors.append(f"description {i + 1}: tone must be loud, medium or calm")
            tone = TONES[min(i, 2)]
        if tone in seen:
            errors.append(f"description tone {tone} is used twice: need one loud, one medium and one calm")
        seen.add(tone)
        body_lines, own = _trailing_tags(fix_dashes(d.get("text") or "").strip().splitlines())
        body = "\n".join(body_lines).strip()
        if not body:
            errors.append(f"description {tone}: text is empty")
            continue
        if not (d.get("psychology") or "").strip():
            warnings.append(f"description {tone}: no psychology note (which trigger it uses)")
        explicit = _uniq(d.get("hashtags") or own)
        if len(explicit) > 5:
            errors.append(f"description {tone}: {len(explicit)} hashtags at the end, need 3-5")
        tags = explicit[:5]
        if len(tags) < 3:
            if explicit:
                warnings.append(f"description {tone}: {len(tags)} hashtags, padded to 3")
            tags = _uniq(tags + bottom + title_tags + default_bottom)[:max(3, len(tags))]
        lines = [body]
        extra = ([cta] if cta and cta not in body else []) + [f"{lbl}: {u}" for lbl, u in links]
        if extra:
            lines += ["", *extra]
        if credits:  # background footage (game, satisfying): the author is named (research 17, section 7)
            lines += ["", ("Фон: " if lang == "ru" else "Background: ") + "; ".join(credits)]
        if chapters:
            lines += ["", *chapters]
        lines += ["", " ".join(tags)]
        text = "\n".join(lines).strip() + "\n"
        first = [x for x in text.splitlines() if x.strip()][:2]
        if any(re.search(r"https?://|t\.me/|#\w", x) for x in first):
            warnings.append(f"description {tone}: first 2 lines must stand alone, no links or hashtags before 'show more'")
        if sum(len(x) for x in first) > 220:
            warnings.append(f"description {tone}: first 2 lines are {sum(len(x) for x in first)} chars, the rest hides behind 'show more'")
        errors.extend(e for e in description_issues(text, md.get("full_video_url")) if e not in errors)
        if ad is not None:
            if not AD_WORD.search(text):
                errors.append(f"description {tone}: ad plan needs an ad disclosure (word 'Реклама' / 'Ad') in every variant")
            if ad.get("url") and ad["url"] not in text:
                errors.append(f"description {tone}: ad plan needs the exact ad link {ad['url']}")
        if has_long_dash(text):
            errors.append(f"long dash in description {tone}")
        out.append({"tone": tone, "psychology": (d.get("psychology") or "").strip(), "text": text, "chars": len(text),
                    "hashtags": tags})
        used_tags += tags
    if not out and not any("description" in e for e in errors):
        errors.append("description has no text")
    if len(seen) < 3 and len(raw) == 3 and not any("twice" in e or "tone must" in e for e in errors):
        errors.append("descriptions must cover loud, medium and calm")
    out.sort(key=lambda x: TONES.index(x["tone"]))
    return out, used_tags


def _cover_texts(plan: dict, manifest: dict, draft: dict, lang: str, errors: list[str], warnings: list[str]) -> list[dict]:
    """Three 3-5 word cover texts, loud -> calm. Legacy `cover_text` becomes the loud one."""
    raw = draft.get("cover_texts")
    if raw:
        items = normalize_cover_texts(raw)
        if [x["tone"] for x in items] != list(TONES):
            errors.append("cover_texts: need exactly 3 texts, one loud, one medium and one calm")
    else:
        topic, hook = _topic(plan, manifest)
        items = derive_cover_texts(hook, topic, lang)
        if draft.get("cover_text"):
            items[0]["text"] = " ".join(str(draft["cover_text"]).split())
    for x in items:
        n = len(x["text"].split())
        if n > 5:
            errors.append(f"cover text {x['tone']}: {n} words, need 3-5")
        elif n < 3:
            warnings.append(f"cover text {x['tone']}: {n} words, need 3-5")
        x["chars"] = len(x["text"])
    return items


def build(plan: dict, manifest: dict, draft: dict, prefs: dict) -> dict:
    lang = manifest.get("language", "ru")
    errors: list[str] = []
    warnings: list[str] = []
    tags_d = draft.get("hashtags") or {}
    title_tags = _uniq(tags_d.get("title") or [])
    titles = []
    for i, t in enumerate(draft.get("titles") or []):
        text = fix_dashes(t["text"]).strip()
        own = _uniq(HASHTAG.findall(text))
        text = HASHTAG.sub("", text).strip()
        tags = own or _uniq(t.get("hashtags") or title_tags)
        if "youtube_shorts" in manifest.get("platforms", []) and "#shorts" not in tags:
            tags = ["#shorts"] + tags
        tags = tags[:6]
        if "?" in text:
            warnings.append(f"title {i + 1}: question title may be weaker than an intriguing statement; test on your data")
        if len(text) > (60 if "youtube_shorts" in manifest.get("platforms", []) else 70):
            warnings.append(f"title {i + 1}: length guideline is about 49 for Shorts or 65-70 for long video; test on your data")
        full = (text + " " + " ".join(tags)).strip()
        while len(full) > MAX_TITLE and len(tags) > 3:
            tags = tags[:-1]
            full = (text + " " + " ".join(tags)).strip()
        loud = loudness_of(t.get("loudness"), min(5, i + 1))
        item = {"n": i + 1, "title": full, "text": text, "hashtags": tags, "loudness": loud, "tone": tone_of(loud),
                "for": t.get("for", ""), "why": t.get("why", ""), "chars": len(full)}
        if len(full) > MAX_TITLE:
            errors.append(f"title {i + 1} is {len(full)} chars > {MAX_TITLE}")
        if count_emoji(full) > 1:
            errors.append(f"title {i + 1} has more than one emoji")
        if loud >= 3 and _caps_ratio(text) > 0.6:
            errors.append(f"title {i + 1}: caps only in the loudest variants (loudness 1-2)")
        if loud >= 4 and count_emoji(text):
            errors.append(f"title {i + 1}: conservative variant with emoji")
        if loud <= 3 and not 3 <= len(tags) <= 6:
            warnings.append(f"title {i + 1}: {len(tags)} hashtags (pattern: 3-6)")
        if loud > 3 and len(tags) > 3:
            warnings.append(f"title {i + 1}: calm title with {len(tags)} hashtags (pattern: 1-3 or none)")
        if loud == 1:
            hook_end = text.find(next((c for c in text if count_emoji(c)), "")) if count_emoji(text) else len(text)
            if not count_emoji(text):
                warnings.append(f"title {i + 1}: loud title without emoji (pattern: CAPS hook + one emoji + hashtags)")
            if hook_end > HOOK_CHARS:
                warnings.append(f"title {i + 1}: the hook ends at char {hook_end}, keep it in the first {HOOK_CHARS}")
        titles.append(item)
    titles.sort(key=lambda x: x["loudness"])
    for k, x in enumerate(titles, 1):
        x["n"] = k
    if not 5 <= len(titles) <= 7:
        errors.append(f"{len(titles)} titles, need 5-7")
    missing = [t for t in TONES if titles and t not in {x["tone"] for x in titles}]
    if missing:
        errors.append("titles must cover loud, medium and calm tiers (loudness 1-2, 3, 4-5); missing: " + ", ".join(missing))
    rec = int(draft.get("recommended", 1))
    rec = min(max(rec, 0), len(titles) - 1) if titles else 0

    name = manifest.get("name", "short")
    utm = bool((plan.get("metadata") or {}).get("utm"))
    platform = (manifest.get("platforms") or ["youtube_shorts"])[0]
    links = [(_label(n, u), _utm(u, name, platform) if utm else u) for n, u in _links(plan, prefs)]
    if not links:
        warnings.append("no links in prefs or plan: description and pinned comment go without links")
    top: list[str] = []  # legacy: hashtags above the text are gone, the 3-5 tags sit at the very end of each description
    bottom = _uniq((tags_d.get("bottom") or []) + (tags_d.get("top") or []))[:6]
    summary = fix_dashes(draft.get("summary", "")).strip()
    cta = fix_dashes(draft.get("cta") or "").strip()
    md = plan.get("metadata") or {}
    if re.search(r"полное видео|full video", cta, re.I) and not md.get("full_video_url"):
        errors.append("Full-video CTA requires metadata.full_video_url")
    descriptions, all_desc_tags = _descriptions(plan, manifest, draft, titles, rec, links, cta, summary, bottom, title_tags,
                                                lang, errors, warnings)
    description = next((x["text"] for x in descriptions if x["tone"] == _rec_tone(draft, titles, rec)), "")
    if not description and descriptions:
        description = descriptions[0]["text"]
    all_tags = _uniq(all_desc_tags + [h for x in titles for h in x["hashtags"]])
    if len(all_tags) > 15:
        warnings.append(f"{len(all_tags)} unique hashtags (keep about 15 or fewer)")
    if len(all_tags) > 60:
        errors.append("more than 60 hashtags: YouTube ignores all of them")
    covers = _cover_texts(plan, manifest, draft, lang, errors, warnings)
    summary = summary or (description.splitlines()[0] if description else "")

    pinned = draft.get("pinned")
    if not pinned:
        link = links[0][1] if links else ""
        if lang == "ru":
            pinned = [summary.split(".")[0][:90] + ".", f"Ссылка: {link}" if link else "Продолжение - в следующем ролике.",
                      "Что показать следующим? Пиши в комментах."]
        else:
            pinned = [summary.split(".")[0][:90] + ".", f"Link: {link}" if link else "More in the next video.",
                      "Which one should I show next? Tell me in the comments."]
    pinned = [fix_dashes(x) for x in pinned][:3]
    tk_tags = _uniq(tags_d.get("tiktok") or [t for t in (title_tags + bottom) if t != "#shorts"])[:5]
    tiktok = f"{fix_dashes(titles[rec]['text']) if titles else summary} {' '.join(tk_tags)}".strip()
    if len(tk_tags) > 5:
        errors.append("TikTok: more than 5 hashtags")
    for fld, txt in (("description", description), ("pinned", "\n".join(pinned)), ("tiktok", tiktok)):
        if has_long_dash(txt):
            errors.append(f"long dash in {fld}")
    srt = ""
    return {
        "titles": titles, "recommended": rec + 1 if titles else None,
        "recommended_title": titles[rec]["title"] if titles else "",
        "recommended_why": titles[rec]["why"] if titles else "",
        "description": description, "descriptions": descriptions,
        "recommended_description": _rec_tone(draft, titles, rec),
        "cover_texts": covers, "pinned_comment": pinned, "tiktok_caption": tiktok,
        "hashtags": {"title": title_tags, "top": top, "bottom": bottom, "tiktok": tk_tags},
        "hashtags_unique": len(all_tags), "links": links, "cover_text": draft.get("cover_text") or (covers[0]["text"] if covers else ""),
        "auto_draft": bool(draft.get("auto")), "errors": errors, "warnings": warnings, "srt": srt,
        "ai_label_reminder": True,
    }


def to_md(meta: dict, lang: str, manifest: dict) -> str:
    ru = lang == "ru"
    out = ["# " + ("Подписи" if ru else "Packaging") + f": {manifest.get('name')}", ""]
    out.append("## " + ("Названия (от громкого к спокойному)" if ru else "Titles (loud to conservative)"))
    out.append("")
    for t in meta["titles"]:
        mark = " **<- рекомендую**" if ru and t["n"] == meta["recommended"] else (" **<- recommended**" if t["n"] == meta["recommended"] else "")
        tone = {"loud": "громкое", "medium": "среднее", "calm": "спокойное"}[t["tone"]] if ru else t["tone"]
        out.append(f"{t['n']}. `{t['title']}`  ({tone}, {'громкость' if ru else 'loudness'} {t['loudness']}, {t['for']}, {t['chars']} {'зн.' if ru else 'chars'}){mark}")
        if t["why"]:
            out.append(f"   - {t['why']}")
    out += ["", ("Почему рекомендую: " if ru else "Why: ") + (meta["recommended_why"] or "-"), ""]
    tone_ru = {"loud": "громкое", "medium": "среднее", "calm": "спокойное"}
    out += ["## " + ("Описания (от громкого к спокойному)" if ru else "Descriptions (loud to calm)"), ""]
    for i, x in enumerate(meta.get("descriptions") or [], 1):
        mark = (" **<- рекомендую**" if ru else " **<- recommended**") if x["tone"] == meta.get("recommended_description") else ""
        out += [f"### {i}. {tone_ru[x['tone']] if ru else x['tone']}{mark}", ""]
        if x.get("psychology"):
            out += [("Приём: " if ru else "Trigger: ") + x["psychology"], ""]
        out += ["```", x["text"].rstrip(), "```", ""]
    out += ["## " + ("Тексты на обложках (от громкого к спокойному)" if ru else "Cover texts (loud to calm)"), ""]
    for x in meta.get("cover_texts") or []:
        out.append(f"- {tone_ru[x['tone']] if ru else x['tone']}: `{x['text']}`")
    out.append("")
    out += ["## " + ("Закреплённый комментарий" if ru else "Pinned comment"), "", "```", *meta["pinned_comment"], "```", ""]
    out += ["## TikTok", "", "```", meta["tiktok_caption"], "```", ""]
    out += ["## " + ("Файлы" if ru else "Files"), "", "- captions.srt " + ("(загрузить в YouTube как субтитры)" if ru else "(upload to YouTube as subtitles)")]
    if meta["auto_draft"]:
        out += ["", ("> Черновик собран правилами. Модель должна переписать названия в metadata.draft.json и перезапустить meta."
                     if ru else "> Rule-based draft. The model should rewrite titles in metadata.draft.json and re-run meta.")]
    out += ["", ("Перед загрузкой: проверь пометку «изменённый или синтетический контент» (реалистичный ИИ-контент)."
                 if ru else "Before upload: check the 'altered or synthetic content' label (realistic AI content).")]
    for e in meta["errors"]:
        out.append(f"- ERROR: {e}")
    for w in meta["warnings"]:
        out.append(f"- warn: {w}")
    return "\n".join(out) + "\n"


def package_dir(d: Path, topic: str | None = None, hashtags: list[str] | None = None, cta: str | None = None) -> dict:
    manifest = read_json(d / "manifest.json")
    plan = read_json(d / "plan.resolved.json")
    if topic:
        plan.setdefault("metadata", {})["topic"] = topic
    if hashtags:
        plan.setdefault("metadata", {})["hashtags"] = hashtags
    lang = manifest.get("language", "ru")
    draft_p = d / "metadata.draft.json"
    draft = read_json(draft_p) if draft_p.exists() else auto_draft(plan, manifest, lang)
    if cta:
        draft["cta"] = cta
    if not draft_p.exists():
        write_json(draft_p, draft)
    meta = build(plan, manifest, draft, M.load())
    write_json(d / "metadata.json", meta)
    (d / "metadata.md").write_text(to_md(meta, lang, manifest), encoding="utf-8")
    from .user_package import refresh_if_exists
    refresh_if_exists(d)
    meta["ok"] = not meta["errors"]
    return meta
