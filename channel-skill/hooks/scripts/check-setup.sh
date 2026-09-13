#!/usr/bin/env bash
# Короткая проверка на старте сессии. Молчит, когда всё в порядке.
# Говорит только о том, что может сломать работу скилла.
# Всегда выходит с кодом 0: сессию не блокируем никогда.

set -u

root="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$root" ]; then
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi
skill="$root/channel-skill"

warn=""

if ! command -v python3 >/dev/null 2>&1; then
  warn="CHANNEL SKILL: нет python3, скрипты tools не пойдут. Пиши без них по QUICKCARD.txt"
elif [ ! -f "$skill/QUICKCARD.txt" ] || [ ! -f "$skill/tools/channel.py" ]; then
  warn="CHANNEL SKILL: папка скилла неполная в $skill. Переустанови: python3 tools/install.py --target ."
elif [ ! -f "$skill/profile/profile.json" ]; then
  warn="CHANNEL SKILL: профиля автора нет. Пройди интервью: python3 channel-skill/tools/onboard.py"
fi

if [ -n "$warn" ]; then
  echo "$warn"
fi

exit 0
