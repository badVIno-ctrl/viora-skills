#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка поставки скилла CHANNEL SKILL в один zip.

    python3 tools/package.py              собрать dist/channel-skill-5.1.1.zip
    python3 tools/package.py --links      лёгкий архив, ссылки остаются ссылками
    python3 tools/package.py --check      ничего не писать, только проверить состав
    python3 tools/package.py --selftest   проверить сам сборщик

Зачем отдельный скрипт, а не обычный zip. В пакете три папки обнаружения:
.claude/skills, .agents/skills и .cursor/skills. Именно по ним среда находит скилл
сама, поэтому в поставке они обязаны быть непустыми.

Режима два, и это главное про сборку:
    по умолчанию (--windows)  вместо трёх ссылок в архив ложатся три настоящие
        папки скилла. Состав внутри тот же, что кладёт tools/install.py: рантайм
        без промптов, эталонов и тестов. Такой архив распаковывает что угодно,
        включая проводник Windows и 7-Zip.
    --links                   ссылки остаются ссылками, архив легче вчетверо.
        Годится только для unzip на Linux и macOS. 7-Zip и проводник Windows
        ссылку с ".." выбрасывают и пишут "Dangerous link path was ignored",
        а папки обнаружения после распаковки остаются пустыми.

Собранный архив проверяется на переносимость: ни путей с "..", ни обратных
слешей, ни зарезервированных имён Windows, ни запрещённых символов в именах.

Про `.skillignore`: он управляет установкой (`tools/install.py`) и составом трёх
папок обнаружения в режиме копий, а не составом всей поставки. Автору в архиве
нужно всё: и промпты, и эталоны, и архив постов. Поэтому из корня выкидываем
только мусор: кэш питона, .git, старые сборки и служебный сор ОС.
"""

import argparse
import fnmatch
import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile

VERSION = "6.2.1"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SKILL_NAME = "channel-skill"

SKIP_DIRS = {".git", ".github", "__pycache__", "dist", "out", ".venv",
             "node_modules", ".pytest_cache", ".idea", ".mypy_cache"}
SKIP_NAMES = {".DS_Store", "Thumbs.db", ".channel-install.json"}
SKIP_PATTERNS = ("*.pyc", "*.pyo", "*.log", "*.tmp", "*.swp", "*.orig", "*.rej")

# Без этих файлов поставка битая, собирать её нельзя.
REQUIRED = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "README.md",
    "LICENSE",
    ".cursorrules",
    os.path.join(".cursor", "rules", "channel-skill.mdc"),
    os.path.join(".claude-plugin", "plugin.json"),
    os.path.join(".claude-plugin", "marketplace.json"),
    os.path.join(".codex-plugin", "plugin.json"),
    os.path.join("hooks", "hooks.json"),
    os.path.join(SKILL_NAME, "SKILL.md"),
    os.path.join(SKILL_NAME, "QUICKCARD.txt"),
    os.path.join(SKILL_NAME, "ROUTER.md"),
    os.path.join(SKILL_NAME, "VERSION"),
    os.path.join(SKILL_NAME, "CHANGELOG.md"),
    os.path.join(SKILL_NAME, "PROMPT-CORE.txt"),
    os.path.join(SKILL_NAME, "PROMPT-FULL.txt"),
    os.path.join(SKILL_NAME, "tools", "channel.py"),
    os.path.join(SKILL_NAME, "tools", "check_all.sh"),
    os.path.join(SKILL_NAME, "evals", "cases.json"),
    os.path.join(SKILL_NAME, "reference", "formats.md"),
    os.path.join(SKILL_NAME, "memory", "metrics.md"),
    os.path.join(SKILL_NAME, "channel-research", "SKILL.md"),
    os.path.join(SKILL_NAME, "channel-video", "SKILL.md"),
)

# Три ссылки, из-за которых и написан этот скрипт.
LINKS = (
    os.path.join(".claude", "skills", SKILL_NAME),
    os.path.join(".agents", "skills", SKILL_NAME),
    os.path.join(".cursor", "skills", SKILL_NAME),
)

SYMLINK_ATTR = (stat.S_IFLNK | 0o777) << 16
MARKER = ".channel-install.json"

# Windows не умеет эти имена и символы, а архив должен открываться везде.
WIN_BAD_CHARS = ':*?"<>|'
WIN_RESERVED = ({"con", "prn", "aux", "nul"}
                | set("com%d" % n for n in range(1, 10))
                | set("lpt%d" % n for n in range(1, 10)))
MAX_ARC_PATH = 200


def skipped(name):
    if name in SKIP_NAMES:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in SKIP_PATTERNS)


def version_of(skill):
    path = os.path.join(skill, "VERSION")
    if os.path.exists(path):
        text = open(path, encoding="utf-8").read().strip()
        if text:
            return text
    return "0.0.0"


def arc(top, rel):
    """Имя внутри архива всегда с прямыми слешами, даже на Windows."""
    parts = [part for part in rel.split(os.sep) if part not in ("", ".")]
    return "/".join([top] + parts)


def collect(pkg):
    """Обходит пакет. Отдаёт (файлы, ссылки), пути относительные."""
    files = []
    links = []
    for base, dirs, names in os.walk(pkg):
        rel_base = os.path.relpath(base, pkg)
        if rel_base == ".":
            rel_base = ""
        keep = []
        for name in sorted(dirs):
            full = os.path.join(base, name)
            rel = os.path.join(rel_base, name) if rel_base else name
            if name in SKIP_DIRS:
                continue
            if os.path.islink(full):
                # Внутрь ссылки не заходим: иначе скилл ляжет в архив четыре раза.
                links.append((rel, os.readlink(full)))
                continue
            keep.append(name)
        dirs[:] = keep
        for name in sorted(names):
            full = os.path.join(base, name)
            rel = os.path.join(rel_base, name) if rel_base else name
            if skipped(name):
                continue
            if os.path.islink(full):
                links.append((rel, os.readlink(full)))
            elif os.path.isfile(full):
                files.append(rel)
    return sorted(files), sorted(links)


def missing_links(files, links, pkg=None):
    """Каких папок обнаружения рядом нет. Для репозитория это норма."""
    have_links = set(rel for rel, _ in links)
    out = []
    for rel in LINKS:
        if rel in have_links:
            continue
        if pkg and os.path.exists(os.path.join(pkg, rel, "SKILL.md")):
            continue
        out.append(rel)
    return out


def missing_required(files, links, pkg=None, include_links=True):
    """Папка обнаружения годится и ссылкой, и распакованной копией."""
    have_files = set(files)
    gone = [rel for rel in REQUIRED if rel not in have_files]
    if include_links:
        gone.extend(missing_links(files, links, pkg))
    return gone


def installer():
    """Правила установки лежат в install.py. Вторую копию логики не держим."""
    path = os.path.join(HERE, "install.py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location("channel_install_rules", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


def installed_files(skill):
    """Состав, который install.py положил бы в папку обнаружения."""
    module = installer()
    if module is not None and hasattr(module, "collect"):
        return module.collect(skill, module.read_patterns(skill), False)
    out = []  # запас на случай, если install.py унесли из tools/
    for base, dirs, names in os.walk(skill):
        dirs[:] = [d for d in sorted(dirs) if d not in SKIP_DIRS]
        rel_base = os.path.relpath(base, skill)
        rel_base = "" if rel_base == "." else rel_base
        for name in sorted(names):
            if skipped(name):
                continue
            out.append(os.path.join(rel_base, name) if rel_base else name)
    return out


def marker_text(skill, count):
    """Маркер нашей установки: по нему install.py --uninstall узнаёт своё."""
    data = {"skill": SKILL_NAME, "version": version_of(skill),
            "source": "поставка zip", "mode": "copy", "files": count}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def unsafe_entries(names):
    """Имена, на которых архив ломается на Windows или уезжает из своей папки."""
    bad = []
    for name in names:
        parts = name.split("/")
        if "\\" in name or name.startswith("/") or ".." in parts:
            bad.append((name, "путь уводит из архива"))
            continue
        if len(name) > MAX_ARC_PATH:
            bad.append((name, "путь длиннее %d знаков" % MAX_ARC_PATH))
            continue
        for part in parts:
            if any(char in part for char in WIN_BAD_CHARS):
                bad.append((name, "запрещённый символ в имени"))
                break
            if part != part.rstrip(". "):
                bad.append((name, "точка или пробел в конце имени"))
                break
            if part.split(".")[0].lower() in WIN_RESERVED:
                bad.append((name, "зарезервированное имя Windows"))
                break
    return bad


def weight(pkg, files):
    total = 0
    for rel in files:
        try:
            total += os.path.getsize(os.path.join(pkg, rel))
        except OSError:
            pass
    return total


def human(size):
    if size >= 1024 * 1024:
        return "%.1f МБ" % (size / 1024.0 / 1024.0)
    if size >= 1024:
        return "%.0f КБ" % (size / 1024.0)
    return "%d Б" % size


def build(pkg, out_dir, files, links, version, top, mode="copy", skill=None):
    """Кладёт архив и возвращает путь до него.

    mode="copy"  три папки обнаружения ложатся настоящими копиями скилла;
                 распакует любой архиватор на любой системе.
    mode="links" три папки обнаружения ложатся ссылками; только для unzip.
    """
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    target = os.path.join(out_dir, "channel-skill-%s.zip" % version)
    if os.path.exists(target):
        os.remove(target)
    if skill is None:
        skill = os.path.join(pkg, SKILL_NAME)
    body = files
    subset = []
    if mode == "copy":
        # Если пакет сам распакован из копийного архива, старые копии не дублируем.
        skip = tuple(rel + os.sep for rel in LINKS)
        body = [rel for rel in files if not rel.startswith(skip)]
        subset = installed_files(skill)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in body:
            zf.write(os.path.join(pkg, rel), arc(top, rel))
        if mode == "copy":
            for rel in LINKS:
                for inner in subset:
                    zf.write(os.path.join(skill, inner),
                             arc(top, os.path.join(rel, inner)))
                zf.writestr(arc(top, os.path.join(rel, MARKER)),
                            marker_text(skill, len(subset)))
            return target
        for rel, dest in links:
            info = zipfile.ZipInfo(arc(top, rel))
            info.create_system = 3  # unix, иначе биты режима никто не прочитает
            info.external_attr = SYMLINK_ATTR
            zf.writestr(info, dest)
    return target


def link_entries(path):
    """Имена записей архива, которые лежат именно ссылками."""
    out = []
    with zipfile.ZipFile(path) as zf:
        for info in zf.infolist():
            if stat.S_ISLNK(info.external_attr >> 16):
                out.append((info.filename, zf.read(info.filename).decode("utf-8")))
    return out


def roots_from(root_arg):
    """Принимает и папку скилла, и корень пакета."""
    if root_arg:
        base = os.path.abspath(root_arg)
    else:
        env = os.environ.get("CHANNEL_SKILL_DIR")
        base = os.path.abspath(env) if env else SKILL
    if os.path.exists(os.path.join(base, "SKILL.md")):
        return os.path.dirname(base), base
    inner = os.path.join(base, SKILL_NAME)
    if os.path.exists(os.path.join(inner, "SKILL.md")):
        return base, inner
    return os.path.dirname(base), base


def report(pkg, files, links, gone, as_json, target=None, mode="copy", extra=0):
    if as_json:
        print(json.dumps({"version": VERSION, "package": pkg, "files": len(files),
                          "links": [{"path": rel, "target": dest} for rel, dest in links],
                          "bytes": weight(pkg, files), "missing": gone,
                          "mode": mode, "discovery_files": extra,
                          "archive": target},
                         ensure_ascii=False, indent=2))
        return
    print("Пакет: %s" % pkg)
    print("Файлов: %d, ссылок: %d, вес без сжатия: %s"
          % (len(files), len(links), human(weight(pkg, files))))
    for rel, dest in links:
        print("  ссылка %s -> %s" % (rel, dest))
    if mode == "copy":
        print("Режим: копии. В каждую папку обнаружения ляжет файлов: %d." % extra)
    else:
        print("Режим: ссылки. Распаковывать только через unzip на Linux или macOS.")
    if gone:
        print("Не хватает для поставки (%d):" % len(gone))
        for rel in gone:
            print("  " + rel)
    if target:
        print("Собрано: %s (%s)" % (target, human(os.path.getsize(target))))


def selftest():
    fails = []
    done = []

    def check(name, cond, extra=""):
        done.append(name)
        print("%s %s%s" % ("PASS" if cond else "FAIL", name,
                           (" " + extra) if extra and not cond else ""))
        if not cond:
            fails.append(name)

    tmp = tempfile.mkdtemp(prefix="channel-package-")
    try:
        pkg = os.path.join(tmp, "Pack")
        skill = os.path.join(pkg, SKILL_NAME)
        for rel in REQUIRED:
            path = os.path.join(pkg, rel)
            folder = os.path.dirname(path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder)
            open(path, "w", encoding="utf-8").write("текст для самопроверки\n")
        open(os.path.join(skill, "VERSION"), "w", encoding="utf-8").write("9.9.9\n")

        junk = os.path.join(skill, "tools", "__pycache__")
        os.makedirs(junk)
        open(os.path.join(junk, "x.cpython-313.pyc"), "w").write("x")
        open(os.path.join(skill, ".DS_Store"), "w").write("x")
        os.makedirs(os.path.join(pkg, "dist"))
        open(os.path.join(pkg, "dist", "staraya.zip"), "w").write("x")

        for rel in LINKS:
            folder = os.path.join(pkg, os.path.dirname(rel))
            if not os.path.isdir(folder):
                os.makedirs(folder)
            os.symlink(os.path.join("..", "..", SKILL_NAME), os.path.join(pkg, rel))

        files, links = collect(pkg)
        dirty = [rel for rel in files
                 if "__pycache__" in rel or rel.endswith(".pyc")
                 or ".DS_Store" in rel or rel.startswith("dist")]
        check("мусор не попал в состав", dirty == [], str(dirty))
        check("три ссылки найдены", len(links) == 3, str(links))
        check("внутрь ссылки не зашли",
              not [rel for rel in files if rel.startswith(".claude" + os.sep)], str(files[:4]))
        check("состав полный", missing_required(files, links, pkg) == [],
              str(missing_required(files, links, pkg)))
        check("версия берётся из файла", version_of(skill) == "9.9.9", version_of(skill))

        target = build(pkg, os.path.join(pkg, "dist"), files, links, version_of(skill), "Pack",
                       mode="links", skill=skill)
        check("имя архива с версией", target.endswith("channel-skill-9.9.9.zip"), target)
        with zipfile.ZipFile(target) as zf:
            names = zf.namelist()
        check("в архиве есть SKILL.md", "Pack/%s/SKILL.md" % SKILL_NAME in names, str(names[:4]))
        check("в архиве нет мусора",
              not [n for n in names if "__pycache__" in n or n.endswith(".pyc")])
        stored = dict(link_entries(target))
        check("ссылки лежат ссылками", len(stored) == 3, str(stored))
        wanted = "Pack/" + "/".join(LINKS[0].split(os.sep))
        check("ссылка ведёт на скилл",
              stored.get(wanted, "").endswith(SKILL_NAME), str(stored.get(wanted)))

        again = build(pkg, os.path.join(pkg, "dist"), files, links, version_of(skill), "Pack",
                      mode="links", skill=skill)
        check("повторная сборка не плодит файлы",
              again == target and len([n for n in os.listdir(os.path.join(pkg, "dist"))
                                      if n.startswith("channel-skill-")]) == 1)

        # Главное про режим копий: архив без ссылок и без пустых папок.
        portable = build(pkg, os.path.join(pkg, "dist"), files, links, version_of(skill), "Pack",
                         mode="copy", skill=skill)
        with zipfile.ZipFile(portable) as zf:
            pnames = zf.namelist()
        check("в переносимом архиве ссылок нет", link_entries(portable) == [],
              str(link_entries(portable)))
        for rel in LINKS:
            want = "Pack/" + "/".join(rel.split(os.sep)) + "/SKILL.md"
            check("папка обнаружения полная: %s" % rel, want in pnames, want)
        check("имена в архиве переносимы", unsafe_entries(pnames) == [],
              str(unsafe_entries(pnames)[:3]))
        check("состав папки обнаружения как у установщика",
              len([n for n in pnames if n.startswith("Pack/.claude/skills/")])
              == len(installed_files(skill)) + 1,
              str(len([n for n in pnames if n.startswith("Pack/.claude/skills/")])))
        check("маркер установки на месте",
              "Pack/.claude/skills/%s/%s" % (SKILL_NAME, MARKER) in pnames)
        check("копии не дублируются при повторной сборке",
              len(pnames) == len(set(pnames)))
        bad = unsafe_entries(["Pack/../evil.txt", "Pack/aux.md", "Pack/a:b.txt",
                              "Pack/имя.", "Pack\\win.txt"])
        check("ловит непереносимые имена", len(bad) == 5, str(bad))

        # Корни ищутся по SKILL.md, поэтому проверяем их до того, как ломаем пакет.
        pkg2, skill2 = roots_from(pkg)
        check("корень пакета разбирается", (pkg2, skill2) == (pkg, skill), "%s %s" % (pkg2, skill2))
        pkg3, skill3 = roots_from(skill)
        check("папка скилла разбирается", (pkg3, skill3) == (pkg, skill), "%s %s" % (pkg3, skill3))

        os.remove(os.path.join(skill, "SKILL.md"))
        files2, links2 = collect(pkg)
        check("ловит неполный состав",
              any(rel.endswith("SKILL.md") for rel in missing_required(files2, links2, pkg)))
        os.remove(os.path.join(pkg, LINKS[1]))
        files3, links3 = collect(pkg)
        check("ловит потерю папки обнаружения", LINKS[1] in missing_required(files3, links3, pkg),
              str(missing_required(files3, links3, pkg)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("Итого: проверок сборщика %d, провалилось %d" % (len(done), len(fails)))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Сборка поставки скилла CHANNEL SKILL")
    ap.add_argument("--root", help="корень пакета или папка скилла")
    ap.add_argument("--out", help="куда класть архив, по умолчанию dist/ в корне пакета")
    ap.add_argument("--check", action="store_true", help="только проверить состав, ничего не писать")
    ap.add_argument("--windows", action="store_true",
                    help="копии вместо ссылок, распакуется везде (по умолчанию)")
    ap.add_argument("--links", action="store_true",
                    help="ссылки оставить ссылками: легче, но только для unzip")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args(argv)

    if args.version:
        print("package.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()
    if args.links and args.windows:
        print("Выбери одно: --windows или --links.")
        return 1

    mode = "links" if args.links else "copy"
    pkg, skill = roots_from(args.root)
    files, links = collect(pkg)
    gone = missing_required(files, links, pkg, include_links=False)
    soft = missing_links(files, links, pkg)
    extra = len(installed_files(skill)) if mode == "copy" else 0

    if args.check:
        report(pkg, files, links, gone, args.json, mode=mode, extra=extra)
        if soft and not args.json:
            print("Папок обнаружения рядом нет: %s" % ", ".join(soft))
            print("Это норма для репозитория: копии скилла в гит не кладём.")
            print("Поставить себе локально: python3 tools/install.py")
        if gone:
            if not args.json:
                print("Собирать нельзя: верни файлы и папки из списка выше.")
            return 1
        if not args.json:
            print("Состав полный. Собрать: python3 tools/package.py")
        return 0

    if gone:
        report(pkg, files, links, gone, args.json, mode=mode, extra=extra)
        if not args.json:
            print("Сборка отменена: поставка неполная.")
        return 1

    out_dir = os.path.abspath(args.out) if args.out else os.path.join(pkg, "dist")
    target = build(pkg, out_dir, files, links, version_of(skill), os.path.basename(pkg),
                   mode=mode, skill=skill)

    # Собрали и тут же проверили: отдавать непереносимый архив нельзя.
    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
    bad = unsafe_entries(names)
    stored = link_entries(target)
    if bad:
        print("Архив непереносимый, имён с проблемой: %d" % len(bad))
        for name, why in bad[:10]:
            print("  %s: %s" % (name, why))
        return 1
    if mode == "copy":
        if stored:
            print("В архиве остались ссылки: %s" % ", ".join(n for n, _ in stored))
            return 1
        for rel in LINKS:
            want = arc(os.path.basename(pkg), os.path.join(rel, "SKILL.md"))
            if want not in names:
                print("Папка обнаружения пустая: %s" % rel)
                return 1

    report(pkg, files, links, gone, args.json, target=target, mode=mode, extra=extra)
    if not args.json:
        if mode == "copy":
            print("Ссылок в архиве нет: распакует и проводник Windows, и 7-Zip, и unzip.")
        else:
            print("Ссылки лежат ссылками: распаковывать только командой unzip.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
