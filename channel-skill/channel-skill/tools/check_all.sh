#!/usr/bin/env bash
# Один прогон перед тем, как считать скилл рабочим.
# Запуск: bash tools/check_all.sh
set -u

# Кэш питона ломает валидатор упаковки и уезжает в поставку. Проще не создавать.
export PYTHONDONTWRITEBYTECODE=1

cd "$(dirname "$0")/.." || exit 1
fail=0

echo "== тесты линтера постов =="
python3 tools/lint_post.py --selftest || fail=1
echo
echo "== тесты линтера статьи =="
python3 tools/lint_article.py --selftest || fail=1
echo

echo "== тесты автоправки =="
python3 tools/lint_post.py --selftest-fix || fail=1
echo

echo "== тесты оценки поста =="
python3 tools/score_post.py --selftest || fail=1
echo

echo "== тесты памяти канала =="
python3 tools/memory.py --selftest || fail=1
echo

echo "== тесты доктора слопа =="
python3 tools/slop_doctor.py --selftest || fail=1
echo

echo "== тесты линтера речи =="
python3 tools/lint_chat.py --selftest || fail=1
echo

echo "== тесты разреза поста =="
python3 tools/split_post.py --selftest || fail=1
echo

echo "== тесты точки входа =="
python3 tools/channel.py selftest-own || fail=1
echo

echo "== тесты таблиц размеров =="
python3 tools/sizes.py --selftest || fail=1
python3 tools/sizes.py --check || fail=1
echo

echo "== сборка промптов =="
python3 tools/build_prompt.py || fail=1
python3 tools/build_prompt.py --check || fail=1
echo

echo "== образец поста в строгом режиме =="
python3 tools/lint_post.py tools/sample-post.txt --strict || fail=1
echo

echo "== среда и зависимости =="
python3 tools/channel.py doctor --offline || fail=1
echo

echo "== эталоны поведения =="
python3 tools/run_evals.py || fail=1
echo

echo "== установка в чистую папку =="
probe="$(mktemp -d)"
python3 tools/install.py --target "$probe" --dry-run || fail=1
rm -rf "$probe"
echo

echo "== состав поставки =="
python3 tools/package.py --check || fail=1
echo

echo "== упаковка по спеке Agent Skills =="
# Сначала убираем кэш, иначе валидатор честно пожалуется на наш же мусор.
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
python3 tools/validate_skill.py || fail=1
echo

echo "== длинные тире во всём скилле =="
# Строки с меткой dash-demo это нарочные показы, что именно запрещено.
python3 - <<'PY' || fail=1
import os
import sys

DASHES = "\u2014\u2013\u2015\u2012\u2212"
MARK = "dash-demo"
SKIP_DIRS = {".git", "__pycache__", "posts", "tests"}
EXTS = (".md", ".txt", ".py", ".sh", ".json", ".mdc")
bad = []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for name in sorted(files):
        if not name.endswith(EXTS):
            continue
        path = os.path.join(root, name)
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        in_fence = False
        fence_marked = False
        for number, line in enumerate(text.split("\n"), 1):
            if line.strip().startswith("```"):
                if in_fence:
                    in_fence = False
                    fence_marked = False
                else:
                    in_fence = True
                    fence_marked = MARK in line
                continue
            if MARK in line:
                continue
            if in_fence and fence_marked:
                continue
            if any(char in line for char in DASHES):
                bad.append("%s:%d" % (path, number))
if bad:
    print("\u043d\u0430\u0439\u0434\u0435\u043d\u044b \u043d\u0435\u043f\u043e\u043c\u0435\u0447\u0435\u043d\u043d\u044b\u0435 \u0442\u0438\u0440\u0435 (%d):" % len(bad))
    for row in bad[:40]:
        print("  " + row)
    sys.exit(1)
print("\u0442\u0438\u0440\u0435 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b, \u043a\u0440\u043e\u043c\u0435 \u043f\u043e\u043c\u0435\u0447\u0435\u043d\u043d\u044b\u0445 \u0441\u0442\u0440\u043e\u043a \u0438 \u0431\u043b\u043e\u043a\u043e\u0432")
PY
echo

echo "== доступность скриптов ресерча и видео =="
python3 tools/research.py --version || fail=1
python3 tools/watch.py --version || fail=1
echo "сеть и yt-dlp проверяются отдельно: python3 tools/research.py --doctor и python3 tools/watch.py --doctor"
echo

if [ "$fail" = "0" ]; then
	echo "ВСЁ ЧИСТО"
else
	echo "ЕСТЬ ПРОБЛЕМЫ, смотри выше"
fi

exit $fail
