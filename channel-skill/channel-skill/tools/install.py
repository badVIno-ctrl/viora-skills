#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install.py 1.0.0

Ставит скилл CHANNEL SKILL в каталоги обнаружения агентов.
Без сторонних библиотек, только стандартная поставка питона.

Куда ставит:
  .claude/skills/channel-skill    Claude Code
  .agents/skills/channel-skill    спека Agent Skills, Codex и прочие
  .cursor/skills/channel-skill    Cursor

Как гонять:
  python3 tools/install.py --target /путь/к/проекту
  python3 tools/install.py --global
  python3 tools/install.py --target . --dry-run
  python3 tools/install.py --target . --link
  python3 tools/install.py --target . --uninstall
  python3 tools/install.py --selftest

По умолчанию копирует файлы: копия работает везде, включая Windows.
С флагом --link ставит симлинки: правки в исходнике сразу видны агенту.
"""

import argparse
import fnmatch
import json
import os
import shutil
import sys
import tempfile

VERSION = "6.1.0"

SKILL_NAME = "channel-skill"
TARGET_DIRS = (
    os.path.join(".claude", "skills"),
    os.path.join(".agents", "skills"),
    os.path.join(".cursor", "skills"),
)
MARKER = ".channel-install.json"

# Что обязательно должно оказаться в установленной копии.
REQUIRED = (
    "SKILL.md",
    "QUICKCARD.txt",
    "ROUTER.md",
    "VERSION",
    "ONBOARDING.md",
    os.path.join("profile", "profile.example.json"),
    os.path.join("tools", "profile.py"),
    os.path.join("tools", "onboard.py"),
    os.path.join("reference", "formats.md"),
    os.path.join("memory", "metrics.md"),
    os.path.join("tools", "lint_post.py"),
    os.path.join("tools", "channel.py"),
    os.path.join("channel-research", "SKILL.md"),
    os.path.join("channel-video", "SKILL.md"),
)


def die(msg):
    sys.stderr.write("ОШИБКА: %s\n" % msg)
    sys.exit(1)


def skill_root():
    """Папка скилла: та самая, где лежит SKILL.md рядом с tools/."""
    env = os.environ.get("CHANNEL_SKILL_DIR")
    if env:
        root = os.path.abspath(env)
    else:
        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    if not os.path.exists(os.path.join(root, "SKILL.md")):
        die("не вижу SKILL.md в %s. Задай CHANNEL_SKILL_DIR" % root)
    return root


def read_patterns(root):
    """Шаблоны из .skillignore самого скилла."""
    path = os.path.join(root, ".skillignore")
    out = ["__pycache__/", "*.pyc", ".DS_Store"]
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def is_ignored(rel, patterns):
    rel = rel.replace(os.sep, "/")
    parts = rel.split("/")
    for pat in patterns:
        p = pat.rstrip("/")
        if pat.endswith("/"):
            if p in parts:
                return True
            if rel.startswith(p + "/"):
                return True
            continue
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(parts[-1], p):
            return True
        if rel.startswith(p + "/"):
            return True
    return False


def collect(root, patterns, full):
    """Список относительных путей к копированию."""
    files = []
    for base, dirs, names in os.walk(root):
        rel_base = os.path.relpath(base, root)
        if rel_base == ".":
            rel_base = ""
        dirs.sort()
        keep = []
        for d in dirs:
            rel = os.path.join(rel_base, d) if rel_base else d
            if full or not is_ignored(rel + "/", patterns):
                keep.append(d)
        dirs[:] = keep
        for n in sorted(names):
            rel = os.path.join(rel_base, n) if rel_base else n
            if not full and is_ignored(rel, patterns):
                continue
            files.append(rel)
    return files


def version_of(root):
    path = os.path.join(root, "VERSION")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read().strip()
    return "0.0.0"


def targets_for(base):
    return [os.path.join(base, d, SKILL_NAME) for d in TARGET_DIRS]


def ours(dest):
    """Наша ли это установка: есть маркер или имя скилла в SKILL.md."""
    if os.path.islink(dest):
        return True
    if os.path.exists(os.path.join(dest, MARKER)):
        return True
    skill = os.path.join(dest, "SKILL.md")
    if os.path.exists(skill):
        head = open(skill, encoding="utf-8", errors="replace").read(400)
        return ("name: " + SKILL_NAME) in head
    return False


def remove(dest):
    if os.path.islink(dest) or os.path.isfile(dest):
        os.unlink(dest)
    elif os.path.isdir(dest):
        shutil.rmtree(dest)


def do_install(root, base, mode, dry, force, full):
    patterns = read_patterns(root)
    files = collect(root, patterns, full)
    actions = []
    for dest in targets_for(base):
        exists = os.path.islink(dest) or os.path.exists(dest)
        if exists and not force:
            if not ours(dest):
                die("в %s лежит чужое содержимое. Добавь --force, если точно надо" % dest)
        action = {"dest": dest, "mode": mode, "files": len(files), "replaced": bool(exists)}
        actions.append(action)
        if dry:
            continue
        if exists:
            if not ours(dest) and not force:
                die("отказ перезаписывать %s" % dest)
            remove(dest)
        parent = os.path.dirname(dest)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        if mode == "link":
            rel = os.path.relpath(root, parent)
            os.symlink(rel, dest)
        else:
            os.makedirs(dest)
            for rel in files:
                src = os.path.join(root, rel)
                dst = os.path.join(dest, rel)
                d = os.path.dirname(dst)
                if d and not os.path.isdir(d):
                    os.makedirs(d)
                shutil.copy2(src, dst)
            marker = {
                "skill": SKILL_NAME,
                "version": version_of(root),
                "source": root,
                "mode": mode,
                "files": len(files),
            }
            with open(os.path.join(dest, MARKER), "w", encoding="utf-8") as fh:
                json.dump(marker, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
    return actions, files


def do_uninstall(base, dry):
    actions = []
    for dest in targets_for(base):
        if not (os.path.islink(dest) or os.path.exists(dest)):
            actions.append({"dest": dest, "removed": False, "reason": "нету"})
            continue
        if not ours(dest):
            actions.append({"dest": dest, "removed": False, "reason": "чужое"})
            continue
        if not dry:
            remove(dest)
        actions.append({"dest": dest, "removed": True, "reason": ""})
    return actions


def check_installed(dest):
    """Проверка, что установленная копия работоспособна."""
    missing = [r for r in REQUIRED if not os.path.exists(os.path.join(dest, r))]
    return missing


def selftest():
    root = skill_root()
    fails = []

    def check(name, cond):
        print("%s %s" % ("PASS" if cond else "FAIL", name))
        if not cond:
            fails.append(name)

    tmp = tempfile.mkdtemp(prefix="channel-install-")
    try:
        # сухой прогон ничего не пишет
        do_install(root, tmp, "copy", True, False, False)
        check("dry-run ничего не создаёт", os.listdir(tmp) == [])

        actions, files = do_install(root, tmp, "copy", False, False, False)
        check("три каталога обнаружения", len(actions) == 3)
        dests = [a["dest"] for a in actions]
        check("все три на месте", all(os.path.isdir(d) for d in dests))
        missing = []
        for d in dests:
            missing += check_installed(d)
        check("обязательные файлы скопировались", not missing)
        if missing:
            print("   не хватает: %s" % ", ".join(sorted(set(missing))))
        first = dests[0]
        check("кэш питона не попал",
              not any("__pycache__" in r for r in os.listdir(os.path.join(first, "tools"))))
        check("тесты не попали без --full",
              not os.path.exists(os.path.join(first, "tools", "tests")))
        check("маркер установки есть", os.path.exists(os.path.join(first, MARKER)))
        marker = json.load(open(os.path.join(first, MARKER), encoding="utf-8"))
        check("в маркере версия скилла", marker.get("version") == version_of(root))

        # повторная установка поверх своего же
        actions2, _ = do_install(root, tmp, "copy", False, False, False)
        check("повторная установка заменяет своё", all(a["replaced"] for a in actions2))

        # чужое содержимое не трогаем
        alien = os.path.join(tmp, ".claude", "skills", "alien-skill")
        os.makedirs(alien)
        open(os.path.join(alien, "SKILL.md"), "w", encoding="utf-8").write("---\nname: alien-skill\n---\n")
        acts = do_uninstall(tmp, False)
        check("снос убрал три копии", sum(1 for a in acts if a["removed"]) == 3)
        check("чужой скилл цел", os.path.exists(os.path.join(alien, "SKILL.md")))
        check("после сноса наших папок нет",
              not any(os.path.exists(d) for d in dests))

        # режим симлинков
        if hasattr(os, "symlink"):
            do_install(root, tmp, "link", False, True, False)
            check("симлинк ведёт на скилл",
                  os.path.islink(dests[0]) and os.path.exists(os.path.join(dests[0], "SKILL.md")))
            check("через симлинк видны под-скиллы",
                  os.path.exists(os.path.join(dests[0], "channel-research", "SKILL.md")))
            do_uninstall(tmp, False)
            check("симлинки сняты, источник цел",
                  not os.path.exists(dests[0]) and os.path.exists(os.path.join(root, "SKILL.md")))

        # --full тянет тесты и промпты
        do_install(root, tmp, "copy", False, True, True)
        check("--full тянет tools/tests",
              os.path.isdir(os.path.join(dests[0], "tools", "tests")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("Итого: провалилось %d" % len(fails))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True, description="Установка скилла CHANNEL SKILL")
    ap.add_argument("--target", help="корень проекта, куда ставим")
    ap.add_argument("--global", dest="glob", action="store_true", help="ставить в домашний каталог")
    ap.add_argument("--link", action="store_true", help="симлинки вместо копий")
    ap.add_argument("--full", action="store_true", help="копировать всё, включая тесты и промпты")
    ap.add_argument("--dry-run", dest="dry", action="store_true", help="только показать план")
    ap.add_argument("--force", action="store_true", help="перезаписать то, что уже есть")
    ap.add_argument("--uninstall", action="store_true", help="снять установку")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument("--selftest", action="store_true", help="самопроверка установщика")
    ap.add_argument("--version", action="store_true", help="версия скрипта")
    args = ap.parse_args(argv)

    if args.version:
        print("install.py %s" % VERSION)
        return 0
    if args.selftest:
        return selftest()

    root = skill_root()
    if args.glob:
        base = os.path.expanduser("~")
    elif args.target:
        base = os.path.abspath(args.target)
    else:
        die("задай --target ПУТЬ или --global")
    if not os.path.isdir(base):
        die("нет такого каталога: %s" % base)

    if args.uninstall:
        actions = do_uninstall(base, args.dry)
        if args.json:
            print(json.dumps({"action": "uninstall", "base": base, "targets": actions},
                             ensure_ascii=False, indent=2))
        else:
            for a in actions:
                mark = "снято" if a["removed"] else ("пропуск: " + a["reason"])
                print("%-52s %s" % (a["dest"], mark))
            print("Готово." if not args.dry else "Сухой прогон, ничего не тронуто.")
        return 0

    mode = "link" if args.link else "copy"
    actions, files = do_install(root, base, mode, args.dry, args.force, args.full)
    if args.json:
        print(json.dumps({"action": "install", "base": base, "mode": mode,
                          "version": version_of(root), "files": len(files),
                          "targets": actions, "dryRun": args.dry},
                         ensure_ascii=False, indent=2))
        return 0

    print("Скилл: %s %s" % (SKILL_NAME, version_of(root)))
    print("Источник: %s" % root)
    print("Режим: %s, файлов: %d" % ("симлинк" if mode == "link" else "копия", len(files)))
    for a in actions:
        state = "замена" if a["replaced"] else "новое"
        print("  %-52s %s" % (a["dest"], state))
    if args.dry:
        print("Сухой прогон: ни один файл не записан.")
        return 0
    problems = []
    for a in actions:
        problems += check_installed(a["dest"])
    if problems:
        print("Не хватает файлов: %s" % ", ".join(sorted(set(problems))))
        return 1
    print("Готово. Агент увидит скилл после перезапуска сессии.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
