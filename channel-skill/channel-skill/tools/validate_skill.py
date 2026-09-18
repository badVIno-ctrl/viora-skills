#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_skill.py 1.0.0

Проверка скилла по спеке Agent Skills и по внутренним правилам пакета.
Без сети и без сторонних библиотек.

Гонять:
  python3 tools/validate_skill.py
  python3 tools/validate_skill.py --json
  python3 tools/validate_skill.py --strict
  python3 tools/validate_skill.py --selftest

Коды ошибок:
  E-FM-MISSING      нет фронтматтера или нет обязательного поля
  E-NAME-FORMAT     имя не по спеке: только строчные, цифры и дефисы, до 64 знаков
  E-NAME-FOLDER     имя не совпадает с именем папки
  E-DESC-LONG       описание длиннее 1024 знаков
  E-DESC-TRIGGER    в описании нет условия запуска (бери когда, use when)
  E-FILE-MISSING    нет обязательного файла пакета
  E-VERSION-SYNC    версии в разных файлах расходятся
  E-LINK-BROKEN     ссылка в доке ведёт на несуществующий файл
  E-FOOTER-DIFF     футер канала отличается от эталона
  E-PYC             в пакете лежит кэш питона
  E-DASH            длинное тире вне помеченной строки
  E-BADCHAR         битый или невидимый символ в тексте
  W-DISCOVERY       каталог обнаружения не ведёт на скилл: чинит python3 tools/install.py
  E-SUBSKILL-UNREG  под-скилл не зарегистрирован в plugin.json
  W-SKILL-LONG      SKILL.md длиннее 500 строк
  W-DESC-SHORT      описание короче 80 знаков, модель не поймёт когда брать
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile

VERSION = "6.2.1"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|txt|py|sh|json))`")
DASHES = ("\u2014", "\u2013", "\u2015", "\u2012", "\u2212")
DASH_MARK = "dash-demo"
MAIN_SKILL = "channel-skill"

# Символы, которые ломают правила молча: глазом не видно, а строка уже не сматчится.
BAD_CHARS = (
    ("\ufffd", "потерянный байт"),
    ("\u200b", "невидимый пробел"),
    ("\u00a0", "неразрывный пробел"),
    ("\ufeff", "метка порядка байт"),
    ("\u2028", "чужой разделитель строк"),
)
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import profile as P  # noqa: E402

# Эталон футера берём из профиля: у каждого автора он свой.
PROFILE = P.load()


def footer_labels_of(prof):
    """Ярлыки футера вида [ЯРЛЫК](, вместе с устаревшими из профиля."""
    out = [item if item.endswith("(") else "[%s](" % item
           for item in P.footer_labels(prof)]
    return tuple(out) + tuple(P.legacy_labels(prof))


FOOTER = P.footer(PROFILE) if P.footer_enabled(PROFILE) else ""
FOOTER_LABELS = footer_labels_of(PROFILE)
FIRST_LABEL = FOOTER_LABELS[0] if FOOTER_LABELS else "[футера-нет]("

TRIGGERS = ("\u0431\u0435\u0440\u0438", "\u043a\u043e\u0433\u0434\u0430", "use when", "use this")

REQUIRED_FILES = (
    "SKILL.md",
    "QUICKCARD.txt",
    "ROUTER.md",
    "VERSION",
    "CHANGELOG.md",
    ".skillignore",
    "PROMPT-CORE.txt",
    "PROMPT-FULL.txt",
    os.path.join("reference", "formats.md"),
    os.path.join("reference", "antislop.md"),
    os.path.join("reference", "distribution.md"),
    os.path.join("reference", "publish.md"),
    os.path.join("memory", "metrics.md"),
    os.path.join("memory", "post-log.md"),
    os.path.join("tools", "channel.py"),
    os.path.join("tools", "lint_post.py"),
    os.path.join("tools", "score_post.py"),
    os.path.join("tools", "split_post.py"),
    os.path.join("tools", "memory.py"),
    os.path.join("tools", "research.py"),
    os.path.join("tools", "watch.py"),
    os.path.join("tools", "sizes.py"),
    os.path.join("tools", "build_prompt.py"),
    os.path.join("tools", "install.py"),
    os.path.join("tools", "check_all.sh"),
    os.path.join("tools", "profile.py"),
    os.path.join("tools", "onboard.py"),
    os.path.join("profile", "profile.example.json"),
    "ONBOARDING.md",
)

SUBSKILLS = ("channel-research", "channel-video")
DISCOVERY = (
    os.path.join(".claude", "skills"),
    os.path.join(".agents", "skills"),
    os.path.join(".cursor", "skills"),
)


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def parse_frontmatter(text):
    """Маленький разбор YAML-шапки: плоские поля, metadata и складные строки."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    body = text[3:end].strip("\n")
    data = {}
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">", "|", ">-", "|-"):
            chunk = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                chunk.append(lines[i].strip())
                i += 1
            data[key] = " ".join(x for x in chunk if x)
            continue
        if val == "":
            sub = {}
            i += 1
            while i < len(lines) and lines[i].startswith("  "):
                sm = re.match(r"^\s+([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
                if sm:
                    sub[sm.group(1)] = sm.group(2).strip()
                i += 1
            data[key] = sub if sub else ""
            continue
        data[key] = val
        i += 1
    return data


def check_skill_folder(path, package_root=None):
    """Проверки одной папки скилла. Возвращает список (код, текст)."""
    out = []
    folder = os.path.basename(os.path.abspath(path))
    skill_md = os.path.join(path, "SKILL.md")
    if not os.path.exists(skill_md):
        return [("E-FM-MISSING", "%s: нет SKILL.md" % folder)]
    text = read(skill_md)
    fm = parse_frontmatter(text)
    if fm is None:
        return [("E-FM-MISSING", "%s: SKILL.md без фронтматтера" % folder)]

    name = fm.get("name", "")
    desc = fm.get("description", "")
    meta = fm.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}

    if not name:
        out.append(("E-FM-MISSING", "%s: нет поля name" % folder))
    else:
        if not NAME_RE.match(name) or len(name) > 64:
            out.append(("E-NAME-FORMAT", "%s: имя %r не по спеке" % (folder, name)))
        if name != folder:
            out.append(("E-NAME-FOLDER", "%s: имя %r не равно папке %r" % (folder, name, folder)))
    if not desc:
        out.append(("E-FM-MISSING", "%s: нет поля description" % folder))
    else:
        if len(desc) > 1024:
            out.append(("E-DESC-LONG", "%s: описание %d знаков, потолок 1024" % (folder, len(desc))))
        if len(desc) < 80:
            out.append(("W-DESC-SHORT", "%s: описание %d знаков, слабо для автовыбора" % (folder, len(desc))))
        low = desc.lower()
        if not any(t in low for t in TRIGGERS):
            out.append(("E-DESC-TRIGGER", "%s: в описании нет условия запуска" % folder))
    if not fm.get("license"):
        out.append(("E-FM-MISSING", "%s: нет поля license" % folder))
    if not meta.get("version"):
        out.append(("E-FM-MISSING", "%s: нет metadata.version" % folder))

    lines = text.count("\n") + 1
    if lines > 500:
        out.append(("W-SKILL-LONG", "%s: SKILL.md %d строк, порог 500, выноси в reference" % (folder, lines)))

    # ссылки из всех доков папки
    roots = [path]
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        roots.append(parent)
    if package_root:
        roots.append(package_root)
    for base, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "tests", "evals")]
        for n in names:
            if not n.endswith((".md", ".txt")):
                continue
            if n.startswith("PROMPT-") or n == "CHANGELOG.md":
                continue
            doc = os.path.join(base, n)
            for target in set(LINK_RE.findall(read(doc))):
                cands = []
                for r in roots:
                    cands += [os.path.join(r, target),
                              os.path.join(r, "reference", target),
                              os.path.join(r, "tools", target)]
                cands.append(os.path.join(base, target))
                if not any(os.path.exists(c) for c in cands):
                    rel = os.path.relpath(doc, path)
                    out.append(("E-LINK-BROKEN", "%s/%s: ссылка %s никуда не ведёт" % (folder, rel, target)))
    return out


def check_dashes(root):
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "posts", "tests", "runs")]
        for n in names:
            if not n.endswith((".md", ".txt", ".py", ".sh", ".json", ".mdc")):
                continue
            path = os.path.join(base, n)
            in_fence = False
            fence_marked = False
            for i, line in enumerate(read(path).split("\n"), 1):
                if line.strip().startswith("```"):
                    if in_fence:
                        in_fence = False
                        fence_marked = False
                    else:
                        in_fence = True
                        fence_marked = DASH_MARK in line
                    continue
                if DASH_MARK in line:
                    continue
                if in_fence and fence_marked:
                    continue
                for d in DASHES:
                    if d in line:
                        out.append(("E-DASH", "%s:%d длинное тире" % (os.path.relpath(path, root), i)))
                        break
    return out


def check_badchars(root):
    """Ищет битые и невидимые символы.

    Зачем: один потерянный байт в списке слов отключает правило целиком,
    и ни один тест об этом не скажет. read() читает с errors=replace,
    поэтому сюда же попадает и файл с битой кодировкой.
    """
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "runs")]
        for n in names:
            if not n.endswith((".md", ".txt", ".py", ".sh", ".json", ".mdc")):
                continue
            path = os.path.join(base, n)
            text = read(path)
            for char, label in BAD_CHARS:
                if char not in text:
                    continue
                line = text[:text.index(char)].count("\n") + 1
                out.append(("E-BADCHAR", "%s:%d %s, всего %d" % (
                    os.path.relpath(path, root), line, label, text.count(char))))
    return out


def check_footer(root):
    out = []
    if not FOOTER:
        return out
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "posts", "tests", "runs")]
        for n in names:
            if not n.endswith((".md", ".txt")):
                continue
            path = os.path.join(base, n)
            for i, line in enumerate(read(path).split("\n"), 1):
                labels = sum(1 for lab in FOOTER_LABELS if lab in line)
                if FIRST_LABEL not in line or labels < 3:
                    continue
                start = line.index(FIRST_LABEL)
                got = line[start:].strip()
                if got != FOOTER:
                    out.append(("E-FOOTER-DIFF", "%s:%d футер не совпадает с эталоном" % (os.path.relpath(path, root), i)))
    return out


def check_tool_versions(skill):
    """Скрипт не имеет права носить старый номер скилла: разъедется молча.

    Свою внутреннюю версию скрипта не трогаем: ругаемся только на тех, кто взял
    мажорку скилла и при этом отстал от файла VERSION.
    """
    out = []
    vfile = os.path.join(skill, "VERSION")
    tools = os.path.join(skill, "tools")
    if not os.path.exists(vfile) or not os.path.isdir(tools):
        return out
    want = read(vfile).strip()
    if not want:
        return out
    major = want.split(".")[0]
    for name in sorted(os.listdir(tools)):
        if not name.endswith(".py"):
            continue
        found = re.search(r'^VERSION\s*=\s*"(\d+\.\d+\.\d+)"',
                          read(os.path.join(tools, name)), re.M)
        if not found:
            continue
        got = found.group(1)
        if got.split(".")[0] == major and got != want:
            out.append(("E-TOOLVER",
                        "tools/%s: VERSION=%s, а у скилла %s" % (name, got, want)))
    return out


def versions_of_package(pkg, skill):
    """Собирает версии из всех мест, где они зашиты."""
    found = {}
    vfile = os.path.join(skill, "VERSION")
    if os.path.exists(vfile):
        found["VERSION"] = read(vfile).strip()
    fm = parse_frontmatter(read(os.path.join(skill, "SKILL.md"))) or {}
    meta = fm.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("version"):
        found["SKILL.md"] = meta["version"]
    for rel, keys in ((os.path.join(".claude-plugin", "plugin.json"), ("version",)),
                      (os.path.join(".codex-plugin", "plugin.json"), ("version",))):
        p = os.path.join(pkg, rel)
        if os.path.exists(p):
            try:
                data = json.load(open(p, encoding="utf-8"))
            except ValueError:
                found[rel] = "битый json"
                continue
            for k in keys:
                if data.get(k):
                    found[rel] = data[k]
    mp = os.path.join(pkg, ".claude-plugin", "marketplace.json")
    if os.path.exists(mp):
        try:
            data = json.load(open(mp, encoding="utf-8"))
            found["marketplace.json metadata"] = data.get("metadata", {}).get("version", "")
            plugins = data.get("plugins") or []
            if plugins:
                found["marketplace.json plugins[0]"] = plugins[0].get("version", "")
        except ValueError:
            found["marketplace.json"] = "битый json"
    mdc = os.path.join(pkg, ".cursor", "rules", "channel-skill.mdc")
    if os.path.exists(mdc):
        m = re.search(r"(\d+\.\d+\.\d+)", read(mdc))
        found["cursor rule"] = m.group(1) if m else "нет версии"
    ch = os.path.join(skill, "CHANGELOG.md")
    if os.path.exists(ch):
        m = re.search(r"(\d+\.\d+\.\d+)", read(ch)[:600])
        found["CHANGELOG.md"] = m.group(1) if m else "нет версии"
    return found


def check_package(pkg, skill):
    out = []
    for rel in REQUIRED_FILES:
        if not os.path.exists(os.path.join(skill, rel)):
            out.append(("E-FILE-MISSING", "нет файла %s" % rel))
    for rel in ("LICENSE", "AGENTS.md", "README.md",
                os.path.join(".claude-plugin", "plugin.json"),
                os.path.join(".claude-plugin", "marketplace.json"),
                os.path.join(".codex-plugin", "plugin.json"),
                os.path.join("hooks", "hooks.json"),
                ".skillignore", ".gitignore"):
        if not os.path.exists(os.path.join(pkg, rel)):
            out.append(("E-FILE-MISSING", "нет файла пакета %s" % rel))

    vers = versions_of_package(pkg, skill)
    uniq = sorted(set(vers.values()))
    if len(uniq) > 1:
        out.append(("E-VERSION-SYNC", "версии расходятся: " +
                    ", ".join("%s=%s" % (k, v) for k, v in sorted(vers.items()))))

    plug = os.path.join(pkg, ".claude-plugin", "plugin.json")
    if os.path.exists(plug):
        try:
            skills = json.load(open(plug, encoding="utf-8")).get("skills") or []
        except ValueError:
            skills = []
        joined = " ".join(skills if isinstance(skills, list) else [str(skills)])
        for sub in SUBSKILLS:
            if os.path.isdir(os.path.join(skill, sub)) and sub not in joined:
                out.append(("E-SUBSKILL-UNREG", "под-скилл %s не зарегистрирован в plugin.json" % sub))

    skill_name = os.path.basename(os.path.abspath(skill))
    for d in DISCOVERY:
        dest = os.path.join(pkg, d, skill_name)
        if not os.path.exists(os.path.join(dest, "SKILL.md")):
            out.append(("W-DISCOVERY", "%s не ведёт на скилл: поставь копию командой python3 tools/install.py"
                        % os.path.join(d, skill_name)))

    for base, dirs, names in os.walk(pkg):
        dirs[:] = [x for x in dirs if x != ".git"]
        for n in names:
            if n.endswith(".pyc") or os.path.basename(base) == "__pycache__":
                out.append(("E-PYC", "лишний файл %s" % os.path.relpath(os.path.join(base, n), pkg)))
                break
    return out


def validate(pkg, skill):
    findings = []
    findings += check_skill_folder(skill, pkg)
    for sub in SUBSKILLS:
        p = os.path.join(skill, sub)
        if os.path.isdir(p):
            findings += check_skill_folder(p, pkg)
    findings += check_package(pkg, skill)
    findings += check_dashes(skill)
    findings += check_badchars(skill)
    findings += check_footer(skill)
    findings += check_tool_versions(skill)
    return findings


def roots_from(root_arg):
    """Понимает и папку скилла, и корень пакета: ориентир это SKILL.md."""
    if root_arg:
        base = os.path.abspath(root_arg)
    else:
        env = os.environ.get("CHANNEL_SKILL_DIR")
        base = os.path.abspath(env) if env else os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    if os.path.exists(os.path.join(base, "SKILL.md")):
        return os.path.dirname(base), base
    inner = os.path.join(base, MAIN_SKILL)
    if os.path.exists(os.path.join(inner, "SKILL.md")):
        return base, inner
    return os.path.dirname(base), base


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    open(path, "w", encoding="utf-8").write(text)


GOOD_FM = ("---\nname: %s\ndescription: Делает тестовую работу для самопроверки валидатора "
           "и ничего больше. Бери, когда гоняешь самопроверку.\nlicense: MIT\n"
           "metadata:\n  version: 1.0.0\n---\n\n# Тест\n")


def use_demo_profile():
    """Проверки футера гоняем на демо-профиле, а не на чужом бренде."""
    demo = P.load(path=P.EXAMPLE)
    box = globals()
    box["PROFILE"] = demo
    box["FOOTER"] = P.footer(demo)
    box["FOOTER_LABELS"] = footer_labels_of(demo)
    box["FIRST_LABEL"] = box["FOOTER_LABELS"][0]
    return demo


def selftest():
    use_demo_profile()
    fails = []
    done = []

    def check(name, cond, extra=""):
        done.append(name)
        print("%s %s%s" % ("PASS" if cond else "FAIL", name, (" " + extra) if extra and not cond else ""))
        if not cond:
            fails.append(name)

    tmp = tempfile.mkdtemp(prefix="channel-validate-")
    try:
        # чистый скилл
        ok = os.path.join(tmp, "good-skill")
        write(os.path.join(ok, "SKILL.md"), GOOD_FM % "good-skill")
        codes = [c for c, _ in check_skill_folder(ok)]
        check("чистый скилл без замечаний", codes == [], str(codes))

        # нет фронтматтера
        p = os.path.join(tmp, "no-fm")
        write(os.path.join(p, "SKILL.md"), "# Без шапки\n")
        check("ловит отсутствие фронтматтера",
              "E-FM-MISSING" in [c for c, _ in check_skill_folder(p)])

        # имя не равно папке
        p = os.path.join(tmp, "folder-a")
        write(os.path.join(p, "SKILL.md"), GOOD_FM % "other-name")
        check("ловит имя не по папке",
              "E-NAME-FOLDER" in [c for c, _ in check_skill_folder(p)])

        # имя с большой буквы
        p = os.path.join(tmp, "Bad_Name")
        write(os.path.join(p, "SKILL.md"), GOOD_FM % "Bad_Name")
        check("ловит имя не по спеке",
              "E-NAME-FORMAT" in [c for c, _ in check_skill_folder(p)])

        # описание без условия запуска и слишком длинное
        p = os.path.join(tmp, "desc-bad")
        write(os.path.join(p, "SKILL.md"),
              "---\nname: desc-bad\ndescription: %s\nlicense: MIT\nmetadata:\n  version: 1.0.0\n---\n" % ("а" * 1100))
        codes = [c for c, _ in check_skill_folder(p)]
        check("ловит длинное описание", "E-DESC-LONG" in codes, str(codes))
        check("ловит описание без условия запуска", "E-DESC-TRIGGER" in codes, str(codes))

        # битая ссылка в доке
        p = os.path.join(tmp, "link-bad")
        write(os.path.join(p, "SKILL.md"), GOOD_FM % "link-bad" + "\nСмотри `reference/missing-file.md`.\n")
        check("ловит битую ссылку",
              "E-LINK-BROKEN" in [c for c, _ in check_skill_folder(p)])

        # целая ссылка не шумит
        p = os.path.join(tmp, "link-ok")
        write(os.path.join(p, "SKILL.md"), GOOD_FM % "link-ok" + "\nСмотри `reference/exists.md`.\n")
        write(os.path.join(p, "reference", "exists.md"), "текст\n")
        check("целая ссылка молчит",
              "E-LINK-BROKEN" not in [c for c, _ in check_skill_folder(p)])

        # тире и пометка
        p = os.path.join(tmp, "dash")
        write(os.path.join(p, "a.md"), "обычная строка \u2014 вот так\n")
        write(os.path.join(p, "b.md"), "показ \u2014 так нельзя (dash-demo)\n")
        codes = [c for c, _ in check_dashes(p)]
        check("ловит длинное тире", codes.count("E-DASH") == 1, str(codes))

        # футер
        p = os.path.join(tmp, "footer")
        write(os.path.join(p, "ok.md"), FOOTER + "\n")
        write(os.path.join(p, "bad.md"), FOOTER.replace("GITHUB", "ГИТ") + "\n")
        codes = [c for c, _ in check_footer(p)]
        check("ловит чужой футер", codes.count("E-FOOTER-DIFF") == 1, str(codes))

        # разные версии в пакете
        pkg = os.path.join(tmp, "pkg")
        sk = os.path.join(pkg, "channel-skill")
        write(os.path.join(sk, "SKILL.md"), GOOD_FM % "channel-skill")
        write(os.path.join(sk, "VERSION"), "9.9.9\n")
        codes = [c for c, _ in check_package(pkg, sk)]
        check("ловит расхождение версий", "E-VERSION-SYNC" in codes, str(codes))
        check("ловит отсутствие обязательных файлов", "E-FILE-MISSING" in codes)
        check("говорит про пути обнаружения", "W-DISCOVERY" in codes)

        # кэш питона
        write(os.path.join(sk, "tools", "__pycache__", "x.cpython-313.pyc"), "x")
        check("ловит кэш питона",
              "E-PYC" in [c for c, _ in check_package(pkg, sk)])

        # битые и невидимые символы
        p = os.path.join(tmp, "badchar")
        write(os.path.join(p, "clean.md"), "слово без потерь\n")
        codes = [c for c, _ in check_badchars(p)]
        check("чистый текст молчит", codes == [], str(codes))
        write(os.path.join(p, "lost.md"), "слово с поте\ufffdей\n")
        codes = [c for c, _ in check_badchars(p)]
        check("ловит потерянный байт", codes.count("E-BADCHAR") == 1, str(codes))
        write(os.path.join(p, "nbsp.md"), "тут\u00a0неразрывный пробел\n")
        codes = [c for c, _ in check_badchars(p)]
        check("ловит невидимый пробел", codes.count("E-BADCHAR") == 2, str(codes))

        # версия скрипта разъехалась с версией скилла
        tv = os.path.join(tmp, "toolver", MAIN_SKILL)
        write(os.path.join(tv, "VERSION"), "5.1.1\n")
        write(os.path.join(tv, "tools", "lint_post.py"), 'VERSION = "5.1.1"\n')
        codes = [c for c, _ in check_tool_versions(tv)]
        check("совпадение версий скрипта молчит", codes == [], str(codes))
        write(os.path.join(tv, "tools", "lint_post.py"), 'VERSION = "5.0.0"\n')
        codes = [c for c, _ in check_tool_versions(tv)]
        check("ловит версию скрипта не от скилла", "E-TOOLVER" in codes, str(codes))
        write(os.path.join(tv, "tools", "sizes.py"), 'VERSION = "1.0.0"\n')
        codes = [c for c, _ in check_tool_versions(tv)]
        check("своя версия скрипта не мешает", codes.count("E-TOOLVER") == 1, str(codes))

        # корни: и папка скилла, и корень пакета
        rpkg = os.path.join(tmp, "roots")
        rsk = os.path.join(rpkg, MAIN_SKILL)
        write(os.path.join(rsk, "SKILL.md"), GOOD_FM % MAIN_SKILL)
        check("папка скилла разбирается",
              roots_from(rsk) == (os.path.abspath(rpkg), os.path.abspath(rsk)),
              str(roots_from(rsk)))
        check("корень пакета разбирается",
              roots_from(rpkg) == (os.path.abspath(rpkg), os.path.abspath(rsk)),
              str(roots_from(rpkg)))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("Итого: проверок валидатора %d, провалилось %d" % (len(done), len(fails)))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Валидатор упаковки скилла")
    ap.add_argument("--root", help="папка скилла")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="предупреждения тоже валят прогон")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args(argv)

    if args.version:
        print("validate_skill.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()

    pkg, skill = roots_from(args.root)
    findings = validate(pkg, skill)
    errors = [f for f in findings if f[0].startswith("E-")]
    warns = [f for f in findings if f[0].startswith("W-")]

    if args.json:
        print(json.dumps({"package": pkg, "skill": skill,
                          "errors": [{"code": c, "text": t} for c, t in errors],
                          "warnings": [{"code": c, "text": t} for c, t in warns],
                          "versions": versions_of_package(pkg, skill)},
                         ensure_ascii=False, indent=2))
        return 1 if errors or (args.strict and warns) else 0

    print("Пакет: %s" % pkg)
    print("Скилл: %s" % skill)
    vers = versions_of_package(pkg, skill)
    print("Версии: %s" % ", ".join("%s=%s" % (k, v) for k, v in sorted(vers.items())))
    for code, text in errors:
        print("  %-18s %s" % (code, text))
    for code, text in warns:
        print("  %-18s %s" % (code, text))
    if not findings:
        print("Скилл чист: ошибок нет, предупреждений нет.")
    else:
        print("Итого: ошибок %d, предупреждений %d" % (len(errors), len(warns)))
    return 1 if errors or (args.strict and warns) else 0


if __name__ == "__main__":
    sys.exit(main())
