#!/usr/bin/env bash
# v2.1 regression test: pre-fix (historical) evidence rows must not deadlock a run,
# and a reproduction alone must never count as proof of repair.
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P=${PKG}
W=/tmp/v21c
rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
git init -q .
git config user.email t@example.com; git config user.name tester
cp -r "$P/scripts" .
mkdir -p src tests
: > src/__init__.py
: > tests/__init__.py
printf 'def add(a, b):\n    return a + b\n' > src/app.py
printf 'import unittest\n\nfrom src.app import add\n\n\nclass TestAdd(unittest.TestCase):\n    def test_rejects_none(self):\n        with self.assertRaisesRegex(TypeError, "does not accept None"):\n            add(None, 1)\n\n\nif __name__ == "__main__":\n    unittest.main()\n' > tests/test_app.py
git add -A && git commit -qm base

PASS=0; FAIL=0
V() { python3 scripts/viora.py "$@"; }
r() { local want="$1"; shift; local out code; out="$(V "$@" 2>&1)"; code=$?
  printf '%s\n' "$out" | tail -n 4
  if [ "$code" = "$want" ]; then echo "  [ok] exit=$code"; PASS=$((PASS+1));
  else echo "  [FAIL] exit=$code, expected $want"; FAIL=$((FAIL+1)); fi; echo; }
has() { local label="$1" needle="$2"; shift 2; local out; out="$(V "$@" 2>&1)"
  if printf '%s' "$out" | grep -qF -- "$needle"; then echo "  [ok] $label"; PASS=$((PASS+1));
  else echo "  [FAIL] $label - no '$needle' in:"; printf '%s\n' "$out" | tail -n 14; FAIL=$((FAIL+1)); fi; }
lacks() { local label="$1" needle="$2"; shift 2; local out; out="$(V "$@" 2>&1)"
  if printf '%s' "$out" | grep -qF -- "$needle"; then echo "  [FAIL] $label - found '$needle' in:"; printf '%s\n' "$out" | tail -n 14; FAIL=$((FAIL+1));
  else echo "  [ok] $label"; PASS=$((PASS+1)); fi; }

echo "===================== setup: open a T0 FIX run ====================="
r 0 tier --set T0
r 0 start --mode FIX --tier T0 --task "add() must reject None instead of raising from +"
r 0 contract --goal "add(None, 1) raises TypeError with a named message" --done-test "python3 -m unittest discover -s tests -t . -q" --protected "add() signature and return type"
r 0 plan --files src/app.py --lines 6

echo "===================== 1. a pre-fix RED row is recorded ====================="
r 0 evidence --gate red --command "python3 -m unittest discover -s tests -t . -q" --result "FAIL as expected: TypeError not raised"

echo "===================== 2. a reproduction alone is NOT proof ====================="
has "check names the pre-fix-only hole" "only pre-fix evidence exists (red)" check
has "check refuses" "NOT READY" check
r 1 check

echo "===================== 3. apply the fix, then run the gates ====================="
printf 'def add(a, b):\n    if a is None or b is None:\n        raise TypeError("add() does not accept None")\n    return a + b\n' > src/app.py
python3 -m unittest discover -s tests -t . -q 2>&1 | tail -2
r 0 gate

echo "===================== 4. the stale RED row must not block anything ====================="
lacks "check does not complain about staleness" "STALE" check
lacks "check no longer reports pre-fix-only" "only pre-fix evidence exists" check
lacks "doctor has no staleness warning" "STALE evidence" doctor

echo "===================== 5. the report labels it pre-fix, not STALE ====================="
for n in 1 2 3 4 5 6 7 8 9 10; do V done "$n" --note "step $n closed by the regression test" >/dev/null 2>&1; done
has "report shows the red row as pre-fix" "| pre-fix |" report --verdict DELIVERED --no-archive
lacks "report has no STALE column value" "| STALE |" report --verdict DELIVERED --no-archive
has "one row per gate: a build row exists" "| build |" report --verdict DELIVERED --no-archive
BUILD_ROWS=$(V report --verdict DELIVERED --no-archive 2>&1 | grep -c '^| build |')
if [ "$BUILD_ROWS" = "1" ]; then echo "  [ok] exactly one build row in the table"; PASS=$((PASS+1));
else echo "  [FAIL] $BUILD_ROWS build rows in the table, expected 1"; FAIL=$((FAIL+1)); fi
echo

echo "===================== 6. rerunning a gate supersedes its stale row ====================="
printf '\n# a comment-only edit, enough to move the fingerprint\n' >> src/app.py
has "the build row is now STALE" "STALE evidence (build)" check
r 0 gate
lacks "the rerun cleared it" "STALE" check
has "and the run is READY again" "READY:" check
r 0 check

echo "===================== 7. gate names are matched case-insensitively ====================="
r 0 evidence --gate REPRO --command "python3 -c 'from src.app import add; add(None, 1)'" --result "TypeError as expected before the second edit"
printf '\n# a second comment-only edit\n' >> src/app.py
has "only the real gate is named stale" "STALE evidence (build)" check
lacks "REPRO is not named among stale gates" "REPRO)" check
lacks "and not at the head of the list either" "(REPRO" check

echo "===================== 8. the append-only log kept every row ====================="
ROWS=$(wc -l < .viora/evidence.jsonl)
echo "  evidence.jsonl rows: $ROWS"
if [ "$ROWS" -ge 4 ]; then echo "  [ok] superseded rows are still on disk"; PASS=$((PASS+1));
else echo "  [FAIL] expected at least 4 rows, found $ROWS"; FAIL=$((FAIL+1)); fi
echo "  gates recorded: $(python3 -c "import json;print(', '.join(json.loads(l)['gate'] for l in open('.viora/evidence.jsonl')))")"
echo

echo "===================== RESULT: $PASS ok, $FAIL failed ====================="
