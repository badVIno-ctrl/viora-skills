#!/usr/bin/env bash
# run.sh - the VioraCode eval driver.
#
# It does the boring half of an eval so you only have to do the interesting half:
#   prepare  - build a throwaway git repo from a fixture, ready for an agent
#   prompt   - print the exact text to paste into the agent under test
#   score    - grade the transcript the agent produced
#
# It deliberately does NOT call any model. There is no API key here, and an eval that
# secretly reformats the prompt is not measuring the skill. You paste, the model works,
# you save what it printed, this scores it.
#
# Usage:
#   bash evals/run.sh list
#   bash evals/run.sh prepare f01
#   bash evals/run.sh prompt  f01
#   bash evals/run.sh score   f01 ~/runs/gemini-flash-f01.txt
#   bash evals/run.sh score-all
#   bash evals/run.sh clean
#
# Exit: 0 ok, 2 usage error.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
FIXTURES="$HERE/fixtures"
RESULTS="${VIORA_EVAL_RESULTS:-$HERE/results}"
WORK="${VIORA_EVAL_WORK:-/tmp/viora-evals}"

die() { echo "run.sh: $*" >&2; exit 2; }

resolve() {
  # accepts f01 or f01-empty-body
  local want="$1" hit=""
  for d in "$FIXTURES"/*/; do
    [ -d "$d" ] || continue
    local name; name="$(basename "$d")"
    case "$name" in
      "$want"|"$want"-*) hit="$name"; break ;;
    esac
  done
  [ -n "$hit" ] || die "no fixture matching '$want'. Try: bash evals/run.sh list"
  echo "$hit"
}

cmd_list() {
  printf '%-24s %-8s %s\n' "FIXTURE" "MODE" "WHAT IT MEASURES"
  for d in "$FIXTURES"/*/; do
    [ -d "$d" ] || continue
    local name mode what
    name="$(basename "$d")"
    mode="$(grep -m1 -oE '^MODE:.*' "$d/TASK.md" 2>/dev/null | sed 's/^MODE:[[:space:]]*//')"
    what="$(grep -m1 -oE '^MEASURES:.*' "$d/EXPECTED.md" 2>/dev/null | sed 's/^MEASURES:[[:space:]]*//')"
    printf '%-24s %-8s %s\n' "$name" "${mode:-?}" "${what:-?}"
  done
  echo
  echo "prepare one with: bash evals/run.sh prepare f01"
}

cmd_prepare() {
  local id; id="$(resolve "$1")" || exit 2
  local src="$FIXTURES/$id/repo"
  [ -d "$src" ] || die "$id has no repo/ directory"
  local dst="$WORK/$id"
  rm -rf "$dst"
  mkdir -p "$dst"
  cp -R "$src/." "$dst/"
  mkdir -p "$dst/scripts"
  cp "$ROOT/scripts/"*.py "$ROOT/scripts/verify.sh" "$dst/scripts/" 2>/dev/null
  if command -v git >/dev/null 2>&1; then
    (
      cd "$dst" || exit 1
      git init -q 2>/dev/null
      git config user.email eval@viora.local 2>/dev/null
      git config user.name "viora eval" 2>/dev/null
      printf '.viora/\n__pycache__/\n' >.gitignore
      git add -A >/dev/null 2>&1
      git commit -qm "fixture baseline" >/dev/null 2>&1
    )
    echo "git baseline committed, so scope / checkpoint / rollback all work here."
  else
    echo "WARNING: git not found. scope and rollback will be degraded in this run."
  fi
  echo "prepared: $dst"
  echo
  echo "Now:"
  echo "  1. cd $dst"
  echo "  2. give the agent the VioraCode skill and the prompt below"
  echo "  3. save everything it printed to a file"
  echo "  4. bash evals/run.sh score $id <that file>"
  echo
  cmd_prompt "$id"
}

cmd_prompt() {
  local id; id="$(resolve "$1")" || exit 2
  echo "----- paste from here -----"
  cat "$FIXTURES/$id/TASK.md"
  echo "----- to here -----"
}

cmd_score() {
  local id; id="$(resolve "$1")" || exit 2
  local transcript="${2:-}"
  [ -n "$transcript" ] || die "usage: run.sh score $id <transcript-file>"
  [ -f "$transcript" ] || die "no such transcript: $transcript"
  local vd="$WORK/$id/.viora"
  local args=(--fixture "$FIXTURES/$id" --transcript "$transcript")
  if [ -d "$vd" ]; then
    args+=(--viora-dir "$vd")
  else
    echo "note: $vd not found, grading the transcript only." >&2
  fi
  mkdir -p "$RESULTS"
  cp "$transcript" "$RESULTS/${id%%-*}-$(basename "$transcript")" 2>/dev/null
  python3 "$HERE/score.py" "${args[@]}"
}

cmd_score_all() {
  [ -d "$RESULTS" ] || die "no results yet in $RESULTS. Score at least one run first."
  python3 "$HERE/score.py" --all --results "$RESULTS" --fixtures "$FIXTURES"
}

cmd_clean() {
  rm -rf "$WORK"
  echo "removed $WORK (results in $RESULTS were kept)"
}

case "${1:-}" in
  list)      cmd_list ;;
  prepare)   shift; [ $# -ge 1 ] || die "usage: run.sh prepare <fixture>"; cmd_prepare "$1" ;;
  prompt)    shift; [ $# -ge 1 ] || die "usage: run.sh prompt <fixture>"; cmd_prompt "$1" ;;
  score)     shift; [ $# -ge 1 ] || die "usage: run.sh score <fixture> <transcript>"; cmd_score "$1" "${2:-}" ;;
  score-all) cmd_score_all ;;
  clean)     cmd_clean ;;
  ""|-h|--help)
    sed -n '2,24p' "$0"
    ;;
  *) die "unknown command '$1'. Try: list, prepare, prompt, score, score-all, clean" ;;
esac
