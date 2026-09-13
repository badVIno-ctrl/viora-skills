#!/bin/sh
# CHANNEL SKILL. Смена в Телеграме, один вход.
#
#   sh start-watch.sh          держать смену
#   sh start-watch.sh doctor   проверить доступы
#   sh start-watch.sh login    войти заново
#
# Сам находит Python, сам ставит telethon, сам спрашивает номер один раз.

here=$(cd "$(dirname "$0")" && pwd)
tools="$here/channel-skill/tools"

PYTHONIOENCODING=utf-8
PYTHONUTF8=1
CHANNEL_SECRETS="$here/secrets"
export PYTHONIOENCODING PYTHONUTF8 CHANNEL_SECRETS

env_file="$CHANNEL_SECRETS/watch.env"
if [ -f "$env_file" ]; then
    set -a
    . "$env_file"
    set +a
fi

py=""
for name in python3 python py; do
    if command -v "$name" >/dev/null 2>&1; then
        if "$name" -c 'import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
            py="$name"
            break
        fi
    fi
done
if [ -z "$py" ]; then
    echo "Не нашёл Python 3. Поставь его и запусти файл снова."
    exit 1
fi

if [ ! -f "$tools/tg.py" ]; then
    echo "Рядом нет папки channel-skill/tools. Положи этот файл в корень поставки."
    exit 1
fi

mode="serve"
keep=""
for a in "$@"; do
    key=$(printf '%s' "$a" | sed 's#^[-/]*##' | tr 'A-Z' 'a-z')
    case "$key" in
        doctor) mode="doctor" ;;
        login) mode="login" ;;
        setup) mode="setup" ;;
        *) keep="$keep $a" ;;
    esac
done

if [ "$mode" = "doctor" ]; then
    "$py" "$tools/tg.py" doctor
    echo ""
    exec "$py" "$tools/tg_watch.py" --doctor
fi

if [ "$mode" = "login" ]; then
    exec "$py" "$tools/tg.py" login --force
fi

if ! "$py" "$tools/tg.py" setup; then
    echo ""
    echo "Подключение не доведено до конца. В строках выше сказано, чего не хватает."
    exit 1
fi
if [ "$mode" = "setup" ]; then
    exit 0
fi

# shellcheck disable=SC2086
exec "$py" "$tools/tg_watch.py" $keep
