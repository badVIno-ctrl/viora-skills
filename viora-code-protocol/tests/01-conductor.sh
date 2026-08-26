#!/usr/bin/env bash
# v2.1 conductor smoke test - real git repo, exit codes captured correctly
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P=${PKG}
W=/tmp/v21a2
rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
git init -q .
git config user.email t@example.com; git config user.name tester
mkdir -p src tests
printf 'def add(a, b):\n    return a + b\n' > src/app.py
: > src/__init__.py
: > tests/__init__.py
printf 'import unittest\nfrom src.app import add\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n' > tests/test_app.py
cp -r "$P/scripts" .
git add -A && git commit -qm base

V="python3 scripts/viora.py"
PASS=0; FAIL=0

# r <expected_exit> <lines_to_show> <cmd...>
r() {
  local want="$1"; shift
  local show="$1"; shift
  echo "\$ $*"
  local out code
  out="$("$@" 2>&1)"; code=$?
  printf '%s\n' "$out" | tail -n "$show"
  if [ "$want" = "-" ] || [ "$code" = "$want" ]; then
    echo "  [ok] exit=$code"; PASS=$((PASS+1))
  else
    echo "  [FAIL] exit=$code, expected $want"; FAIL=$((FAIL+1))
  fi
  echo
}
# expect <label> <needle> <cmd...>
expect() {
  local label="$1" needle="$2"; shift 2
  local out
  out="$("$@" 2>&1)"
  if printf '%s' "$out" | grep -q -- "$needle"; then
    echo "  [ok] $label: found '$needle'"; PASS=$((PASS+1))
  else
    echo "  [FAIL] $label: '$needle' not in output"; FAIL=$((FAIL+1))
    printf '%s\n' "$out" | tail -n 10
  fi
}

echo "===================== 1. doctor ====================="
r 0 8 $V doctor

echo "===================== 2. open the run ====================="
r 0 2 $V tier --set T0
r 0 3 $V start --mode FIX --tier T0 --task "add() must reject None with a clear message"
r 0 4 $V next
r 0 3 $V contract --goal "add() rejects None with a clear TypeError" --done-test "python3 -m unittest discover -s tests -t . -q" --protected "add(int,int) keeps working" --non-goals "no refactor of the module"
r 0 2 $V done 1 --note "CONTRACT written"
r 0 2 $V done 2 --note "Owner: src/app.py:1"
r 0 2 $V done 3 --note "Rung 2 - extend add(), no new module"

echo "===================== 3. plan: refusal at the T0 file cap ====================="
r 2 3 $V plan --files src/app.py,tests/test_app.py --lines 40
r 0 3 $V plan --files src/app.py,tests/test_app.py --lines 40 --frozen "add() signature" --force
r 0 4 $V plan --show
r 0 2 $V done 4 --note "PLAN recorded: 2 files, forced with a reason"

echo "===================== 4. RED (genuinely red) ====================="
printf 'import unittest\nfrom src.app import add\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n\n    def test_none(self):\n        with self.assertRaisesRegex(TypeError, "does not accept None"):\n            add(None, 1)\n' > tests/test_app.py
echo "\$ python3 -m unittest discover -s tests -t . -q"
python3 -m unittest discover -s tests -t . -q 2>&1 | tail -4
r 0 2 $V done 5 --note "RED: test_none fails - message is 'unsupported operand type(s)'"

echo "===================== 5. checkpoint + GREEN + scope ====================="
r 0 3 $V checkpoint --label "before GREEN"
printf 'def add(a, b):\n    if a is None or b is None:\n        raise TypeError("add() does not accept None")\n    return a + b\n' > src/app.py
echo "\$ python3 -m unittest discover -s tests -t . -q"
python3 -m unittest discover -s tests -t . -q 2>&1 | tail -3
echo "--- deliberately create __pycache__ junk, scope must ignore it ---"
python3 -m compileall -q . >/dev/null 2>&1
find . -name '__pycache__' -type d | head -3
r 0 4 $V scope
expect "scope ignores generated files" "SCOPE OK" $V scope
echo
r 0 2 $V done 6 --note "GREEN: 3-line guard in add()"

echo "===================== 6. scope catches a real undeclared file ====================="
printf '# a helper nobody asked for\n' > src/extra.py
r 1 5 $V scope
expect "undeclared file named" "src/extra.py" $V scope
r 2 4 $V done 7 --note "CLEAN"
rm src/extra.py
r 0 3 $V scope
r 0 2 $V done 7 --note "CLEAN: no dead code, the guard reads once"

echo "===================== 7. gate, then staleness ====================="
r 0 8 $V gate
echo "--- evidence.jsonl ---"; cat .viora/evidence.jsonl | head -4; echo
r 1 6 $V check
expect "check names the missing steps" "step 8" $V check
echo
echo "--- now edit one comment into the file, nothing else ---"
printf 'def add(a, b):\n    # reject None early - see .viora/contract.md\n    if a is None or b is None:\n        raise TypeError("add() does not accept None")\n    return a + b\n' > src/app.py
expect "staleness detected" "STALE" $V check
echo
r 0 3 $V evidence --gate manual-check --command "python3 -c 'from src.app import add; add(None, 1)'" --result "TypeError: add() does not accept None"
r 0 4 $V gate
expect "no stale rows after rerun" "fresh" $V gate
echo

echo "===================== 8. strikes and demote ====================="
r 0 3 $V strike --reason "isinstance() check needed - rejected, None is the only bad input"
r 0 4 $V strike --reason "custom exception class needed - rejected, TypeError is correct"
r 2 4 $V strike --reason "third strike at T0 must be refused"
r 0 2 $V strike --reset
r 2 3 $V demote --reason "cannot demote below T0"

echo "===================== 9. close out, report, check ====================="
r 0 2 $V done 8 --note "PROVE: gates rerun after the last edit, 2 fresh rows"
r 0 2 $V done 9 --note "DOUBT: 5 questions answered, no second owner created"
r 0 2 $V done 10 --note "REPORT emitted"
r 0 42 $V report
expect "report is DELIVERED" "VERDICT: DELIVERED" $V report --no-archive
r 0 4 $V check
expect "check says ready" "READY:" $V check
echo
r 0 10 $V status
r 0 12 $V handoff

echo "===================== 10. rollback refusals ====================="
r 0 4 $V rollback --list
r 2 4 $V rollback
r 0 5 $V rollback --yes
echo "--- src/app.py after rollback (should be the pre-GREEN version) ---"
cat src/app.py
echo
git add -A >/dev/null 2>&1; git commit -qm "move head" --no-verify >/dev/null 2>&1
r 0 3 $V checkpoint --label "after head move"
git commit -q --allow-empty -m "head moves again" --no-verify
r 2 4 $V rollback --yes
r 0 4 $V rollback --yes --force

echo "===================== 11. second run + stats ====================="
r 0 3 $V start --mode TRIVIAL --tier T0 --task "second run so stats has two rows" --force
r 0 2 $V done 1 --note "CONTRACT: trivial change, no code"
r 1 6 $V report --verdict NO_CHANGE
r 0 20 $V stats
echo "--- runs.jsonl ---"; wc -l .viora/runs.jsonl

echo
echo "===================== RESULT: $PASS ok, $FAIL failed ====================="
