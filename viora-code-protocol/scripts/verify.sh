#!/usr/bin/env bash
# verify.sh - run the repository's OWN quality gates and print an evidence table.
#
# The protocol forbids claiming "done" without fresh command output. This script
# produces that output in one shot: it detects the stack, runs only gates the
# repository actually defines, and prints PASS / FAIL / SKIP with the exact
# command used, so the result can be pasted into the final report.
#
# Usage:
#   bash verify.sh [ROOT] [--only lint,types,test,build,format] [--list] [--timeout 600]
#
# Exit: 0 = every executed gate passed, 1 = a gate failed, 2 = bad usage.
# Never edits files. Never installs anything. Never reaches the network.

set -uo pipefail

ROOT="."
ONLY=""
LIST_ONLY=0
TIMEOUT="${QCP_TIMEOUT:-600}"

while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    --list) LIST_ONLY=1; shift ;;
    --timeout) TIMEOUT="${2:-600}"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) ROOT="$1"; shift ;;
  esac
done

cd "$ROOT" 2>/dev/null || { echo "verify.sh: cannot enter $ROOT" >&2; exit 2; }

GATE_NAMES=(); GATE_KINDS=(); GATE_CMDS=()

add_gate() { GATE_NAMES+=("$1"); GATE_KINDS+=("$2"); GATE_CMDS+=("$3"); }
has_cmd() { command -v "$1" >/dev/null 2>&1; }
wants() { [ -z "$ONLY" ] && return 0; case ",$ONLY," in *",$1,"*) return 0 ;; *) return 1 ;; esac }

npm_script() {
  # $1 = script name; prints 1 if package.json declares it
  [ -f package.json ] || return 1
  if has_cmd node; then
    node -e "const s=(require('./package.json').scripts)||{};process.exit(s['$1']?0:1)" 2>/dev/null
  else
    grep -q "\"$1\"[[:space:]]*:" package.json
  fi
}

PKG_RUN="npm run"
if [ -f pnpm-lock.yaml ] && has_cmd pnpm; then PKG_RUN="pnpm run"
elif [ -f yarn.lock ] && has_cmd yarn; then PKG_RUN="yarn"
elif [ -f bun.lockb ] && has_cmd bun; then PKG_RUN="bun run"
fi

# ---- Node / TypeScript ------------------------------------------------------
if [ -f package.json ]; then
  for s in format:check format-check fmt:check; do
    if npm_script "$s"; then add_gate "format" "format" "$PKG_RUN $s"; break; fi
  done
  for s in lint lint:all eslint; do
    if npm_script "$s"; then add_gate "lint" "lint" "$PKG_RUN $s"; break; fi
  done
  for s in typecheck type-check types tsc; do
    if npm_script "$s"; then add_gate "types" "types" "$PKG_RUN $s"; break; fi
  done
  if [ ${#GATE_NAMES[@]} -eq 0 ] || ! printf '%s\n' "${GATE_KINDS[@]}" | grep -qx types; then
    if [ -f tsconfig.json ] && has_cmd npx; then add_gate "types" "types" "npx --no-install tsc --noEmit"; fi
  fi
  for s in test test:unit test:ci; do
    if npm_script "$s"; then add_gate "test" "test" "$PKG_RUN $s"; break; fi
  done
  for s in build compile; do
    if npm_script "$s"; then add_gate "build" "build" "$PKG_RUN $s"; break; fi
  done
fi

# ---- Python ----------------------------------------------------------------
HAS_PY=0
for f in pyproject.toml requirements.txt setup.py setup.cfg Pipfile tox.ini; do
  [ -f "$f" ] && HAS_PY=1
done
if [ "$HAS_PY" -eq 0 ]; then
  found_py="$(find . -name '*.py' -not -path './node_modules/*' -not -path './.git/*' -print -quit 2>/dev/null)"
  [ -n "$found_py" ] && HAS_PY=1
fi
if [ "$HAS_PY" -eq 1 ]; then
  if has_cmd ruff; then
    add_gate "lint" "lint" "ruff check ."
    add_gate "format" "format" "ruff format --check ."
  elif has_cmd flake8; then add_gate "lint" "lint" "flake8 ."
  fi
  if has_cmd mypy && { [ -f mypy.ini ] || grep -qs '\[tool.mypy\]' pyproject.toml; }; then
    add_gate "types" "types" "mypy ."
  fi
  if has_cmd pytest && { [ -d tests ] || [ -d test ] || [ -f pytest.ini ] || grep -qs 'pytest' pyproject.toml; }; then
    add_gate "test" "test" "pytest -q"
  fi
  if has_cmd python3; then
    add_gate "build" "build" "python3 -m compileall -q ."
  fi
fi

# ---- Go / Rust / Make ------------------------------------------------------
if [ -f go.mod ] && has_cmd go; then
  add_gate "lint" "lint" "go vet ./..."
  add_gate "build" "build" "go build ./..."
  add_gate "test" "test" "go test ./..."
fi
if [ -f Cargo.toml ] && has_cmd cargo; then
  add_gate "format" "format" "cargo fmt --check"
  add_gate "lint" "lint" "cargo clippy -q -- -D warnings"
  add_gate "test" "test" "cargo test -q"
fi
if [ ${#GATE_NAMES[@]} -eq 0 ] && [ -f Makefile ]; then
  for t in lint test build; do
    grep -qE "^$t:" Makefile && add_gate "$t" "$t" "make $t"
  done
fi

if [ ${#GATE_NAMES[@]} -eq 0 ]; then
  echo "| Gate | Command | Result |"
  echo "|---|---|---|"
  echo "| (none) | no repo-defined gates detected | SKIP |"
  echo
  echo "UNPROVEN: this repository declares no gates this script can detect."
  echo "Find the real commands (CI config, README, docs) and run them explicitly."
  exit 0
fi

if [ "$LIST_ONLY" -eq 1 ]; then
  i=0
  while [ $i -lt ${#GATE_NAMES[@]} ]; do
    echo "${GATE_NAMES[$i]}: ${GATE_CMDS[$i]}"; i=$((i+1))
  done
  exit 0
fi

RESULTS=()
FAILED=0
RUNNER=""
has_cmd timeout && RUNNER="timeout ${TIMEOUT}"

i=0
while [ $i -lt ${#GATE_NAMES[@]} ]; do
  name="${GATE_NAMES[$i]}"; kind="${GATE_KINDS[$i]}"; cmd="${GATE_CMDS[$i]}"
  i=$((i+1))
  if ! wants "$kind"; then RESULTS+=("$name|$cmd|SKIP (filtered)"); continue; fi
  echo "==> $name: $cmd"
  out_file="$(mktemp 2>/dev/null || echo /tmp/qcp_gate_$$)"
  # shellcheck disable=SC2086
  if $RUNNER bash -lc "$cmd" >"$out_file" 2>&1; then
    RESULTS+=("$name|$cmd|PASS")
    tail -n 3 "$out_file"
  else
    code=$?
    FAILED=1
    RESULTS+=("$name|$cmd|FAIL (exit $code)")
    echo "--- last 25 lines ---"
    tail -n 25 "$out_file"
  fi
  rm -f "$out_file"
  echo
done

echo "## Evidence table"
echo
echo "| Gate | Command | Result |"
echo "|---|---|---|"

# Append every row to the evidence log so a later report cannot claim a gate that
# was never run. viora.py report only prints PASS for rows found in this file.
# When viora.py invoked us it sets VIORA_NO_EVIDENCE=1 and records the rows itself,
# stamped with a fingerprint of the working tree, so we must not write duplicates.
EVIDENCE_LOG=""
VIORA_DIR="${VIORA_DIR:-.viora}"
if [ -z "${VIORA_NO_EVIDENCE:-}" ] && mkdir -p "$VIORA_DIR" 2>/dev/null; then
  EVIDENCE_LOG="$VIORA_DIR/evidence.jsonl"
fi
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"

for row in "${RESULTS[@]}"; do
  IFS='|' read -r g c r <<<"$row"
  echo "| $g | \`$c\` | $r |"
  if [ -n "$EVIDENCE_LOG" ]; then
    esc_c="$(printf '%s' "$c" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    printf '{"gate":"%s","command":"%s","result":"%s","at":"%s"}\n' \
      "$g" "$esc_c" "$r" "$STAMP" >>"$EVIDENCE_LOG" 2>/dev/null || true
  fi
done
echo
if [ -n "$EVIDENCE_LOG" ]; then
  echo "Evidence appended to $EVIDENCE_LOG"
  echo
fi
if [ "$FAILED" -eq 1 ]; then
  echo "VERDICT: FAIL - fix the failing gate before claiming completion."
  exit 1
fi
echo "VERDICT: all executed gates PASS. Gates marked SKIP remain UNPROVEN."
exit 0
