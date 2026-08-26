#!/usr/bin/env bash
# install-hooks.sh - put the VioraCode pre-commit hook in place.
#
# Usage:
#   bash hooks/install-hooks.sh              # install (backs up anything already there)
#   bash hooks/install-hooks.sh --uninstall  # remove, restoring the backup if one exists
#   bash hooks/install-hooks.sh --check      # say what is installed, change nothing
#
# Respects core.hooksPath if your repo sets it. Never overwrites an existing hook without
# keeping a copy.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/pre-commit"
MODE="install"

case "${1:-}" in
  --uninstall) MODE="uninstall" ;;
  --check)     MODE="check" ;;
  "")          MODE="install" ;;
  -h|--help)   sed -n '2,12p' "$0"; exit 0 ;;
  *) echo "install-hooks.sh: unknown option '$1'" >&2; exit 2 ;;
esac

command -v git >/dev/null 2>&1 || { echo "install-hooks.sh: git not found" >&2; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || { echo "install-hooks.sh: not inside a git repository" >&2; exit 2; }

GIT_DIR="$(git rev-parse --git-dir)"
HOOKS_PATH="$(git config core.hooksPath 2>/dev/null || true)"
if [ -n "$HOOKS_PATH" ]; then
  case "$HOOKS_PATH" in
    /*) TARGET_DIR="$HOOKS_PATH" ;;
    *)  TARGET_DIR="$(git rev-parse --show-toplevel)/$HOOKS_PATH" ;;
  esac
  echo "note: this repo sets core.hooksPath -> $TARGET_DIR"
else
  TARGET_DIR="$GIT_DIR/hooks"
fi
TARGET="$TARGET_DIR/pre-commit"

if [ "$MODE" = "check" ]; then
  if [ ! -e "$TARGET" ]; then
    echo "not installed: $TARGET does not exist"
    exit 0
  fi
  if grep -q "VioraCode pre-commit hook" "$TARGET" 2>/dev/null; then
    echo "installed: $TARGET is the VioraCode hook"
  else
    echo "occupied: $TARGET exists but is NOT the VioraCode hook"
    echo "  first line: $(head -1 "$TARGET")"
  fi
  [ -e "$TARGET.viora-backup" ] && echo "backup present: $TARGET.viora-backup"
  exit 0
fi

if [ "$MODE" = "uninstall" ]; then
  if [ ! -e "$TARGET" ]; then
    echo "nothing to remove: $TARGET does not exist"
    exit 0
  fi
  if ! grep -q "VioraCode pre-commit hook" "$TARGET" 2>/dev/null; then
    echo "refusing to remove $TARGET - it is not the VioraCode hook" >&2
    exit 2
  fi
  rm -f "$TARGET"
  if [ -e "$TARGET.viora-backup" ]; then
    mv "$TARGET.viora-backup" "$TARGET"
    echo "removed, and restored the previous hook from backup"
  else
    echo "removed $TARGET"
  fi
  exit 0
fi

[ -f "$SRC" ] || { echo "install-hooks.sh: cannot find $SRC" >&2; exit 2; }
mkdir -p "$TARGET_DIR" || { echo "install-hooks.sh: cannot create $TARGET_DIR" >&2; exit 2; }

if [ -e "$TARGET" ] && ! grep -q "VioraCode pre-commit hook" "$TARGET" 2>/dev/null; then
  cp "$TARGET" "$TARGET.viora-backup"
  echo "existing hook backed up to $TARGET.viora-backup"
  echo "  If you want both, chain them: call the backup from the top of the new hook."
fi

cp "$SRC" "$TARGET"
chmod +x "$TARGET" 2>/dev/null

echo "installed: $TARGET"
echo
echo "What it will do on your next commit:"
echo "  - block if an open viora run fails 'viora.py check' (unfinished steps, stale evidence,"
echo "    out-of-plan files, open Critical findings)"
echo "  - block on staged merge-conflict markers"
echo "  - block on focused tests (.only / fdescribe / fit)"
echo "  - block over 1000 changed lines; warn over 300"
echo "  - warn on debug residue (print / console.log / breakpoint / dd)"
echo
echo "Bypass once:   VIORA_SKIP=1 git commit -m '...'"
echo "Verify setup:  bash hooks/install-hooks.sh --check"
echo
echo "This is the only part of the protocol that works when the agent forgets it exists."
