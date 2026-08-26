#!/usr/bin/env bash
# v2.1 hooks + evals smoke test
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P=${PKG}
W=/tmp/v21b
rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
git init -q .
git config user.email t@example.com; git config user.name tester
cp -r "$P/scripts" .
printf 'def f():\n    return 1\n' > a.py
git add -A && git commit -qm base
PASS=0; FAIL=0
c() { # c <expected> <label> <commit args...>
  local want="$1" label="$2"; shift 2
  local out code
  out="$("$@" 2>&1)"; code=$?
  printf '%s\n' "$out" | tail -n 6
  if [ "$code" = "$want" ]; then echo "  [ok] $label exit=$code"; PASS=$((PASS+1));
  else echo "  [FAIL] $label exit=$code, expected $want"; FAIL=$((FAIL+1)); fi
  echo
}

echo "===================== HOOK: install ====================="
bash "$P/hooks/install-hooks.sh" | tail -8; echo
bash "$P/hooks/install-hooks.sh" --check; echo

echo "===================== HOOK: no open run -> allowed ====================="
printf 'def g():\n    return 2\n' >> a.py
git add -A
c 0 "commit with no run" git commit -qm "no run open"

echo "===================== HOOK: open, not-ready run -> blocked ====================="
python3 scripts/viora.py tier --set T0 >/dev/null 2>&1
python3 scripts/viora.py start --mode FIX --tier T0 --task "hook test" >/dev/null 2>&1
printf 'def h():\n    return 3\n' >> a.py
git add -A
c 1 "commit with unready run" git commit -qm "should be blocked"

echo "===================== HOOK: VIORA_SKIP bypass ====================="
c 0 "bypass" env VIORA_SKIP=1 git commit -qm "bypassed on purpose"
rm -rf .viora

echo "===================== HOOK: conflict markers -> blocked ====================="
printf '<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> other\n' > c.txt
git add c.txt
c 1 "conflict markers" git commit -qm "conflict markers"
git reset -q; rm -f c.txt

echo "===================== HOOK: focused test -> blocked ====================="
printf "describe('x', () => {\n  it.only('y', () => {})\n})\n" > t.spec.js
git add t.spec.js
c 1 "focused test" git commit -qm "focused test"
git reset -q; rm -f t.spec.js

echo "===================== HOOK: debug residue -> warn only ====================="
printf 'def dbg():\n    print("here")\n    return 4\n' >> a.py
git add -A
c 0 "debug residue warns" git commit -qm "debug residue"

echo "===================== HOOK: foreign hook is backed up ====================="
bash "$P/hooks/install-hooks.sh" --uninstall | tail -2
printf '#!/bin/sh\necho "someone else was here"\n' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
bash "$P/hooks/install-hooks.sh" | head -5
ls -1 .git/hooks/ | grep pre-commit
bash "$P/hooks/install-hooks.sh" --uninstall | tail -2
echo "--- restored hook: ---"; head -2 .git/hooks/pre-commit
echo

echo "===================== EVALS: list ====================="
export VIORA_EVAL_WORK=/tmp/v21evals
export VIORA_EVAL_RESULTS=/tmp/v21results
rm -rf "$VIORA_EVAL_WORK" "$VIORA_EVAL_RESULTS"
bash "$P/evals/run.sh" list; echo "exit=$?"

echo
echo "===================== EVALS: prepare f01 ====================="
bash "$P/evals/run.sh" prepare f01 2>&1 | tail -20; echo "exit=$?"
echo "--- prepared tree ---"; ls -1 "$VIORA_EVAL_WORK"/f01-empty-body 2>/dev/null | head -10
echo "--- git baseline ---"; git -C "$VIORA_EVAL_WORK/f01-empty-body" log --oneline 2>&1 | head -2
echo "--- the declared DONE-TEST actually runs ---"
(cd "$VIORA_EVAL_WORK/f01-empty-body" && python3 -m unittest discover -s tests -t . -q 2>&1 | tail -3)

echo
echo "===================== EVALS: prompt f04 ====================="
bash "$P/evals/run.sh" prompt f04 2>&1 | head -14

echo
echo "===================== EVALS: score a good transcript ====================="
mkdir -p /tmp/v21tr
cat > /tmp/v21tr/good.md <<'TRANSCRIPT'
VIORA T0 | MODE FIX | STEP 1/10 CONTRACT

$ python3 scripts/viora.py doctor
VioraCode doctor - v2.1
$ python3 scripts/viora.py tier --set T0
$ python3 scripts/viora.py start --mode FIX --tier T0 --task "parse_config crashes on a blank line"

GOAL: parse_config skips blank lines instead of raising
DONE-TEST: python3 -m unittest discover -s tests -t . -q
PROTECTED: existing key=value parsing, the three passing tests
NON-GOALS: no rewrite of the parser, no new file

VIORA T0 | MODE FIX | STEP 2/10 OWNER
Owner: config.py:8
The split lives in parse_config, and nothing else parses config lines.

VIORA T0 | MODE FIX | STEP 3/10 LADDER
Rung 1 because rung 0 fails: the crash is real. A guard clause, no new abstraction.

VIORA T0 | MODE FIX | STEP 4/10 PLAN
$ python3 scripts/viora.py plan --files config.py --lines 8
FILE: config.py - skip empty lines in the loop
BUDGET: 8 lines
FROZEN: parse_config signature and return type

VIORA T0 | MODE FIX | STEP 5/10 RED
$ python3 -m unittest discover -s tests -t . -q
ValueError: not enough values to unpack (expected 2, got 1)
RED confirmed, and for the right reason: the blank line reaches split.

VIORA T0 | MODE FIX | STEP 6/10 GREEN
$ python3 scripts/viora.py checkpoint --label "before GREEN"
Two lines added: skip a line that is empty after strip. No try/except, because a
blank line is expected input, not an error to swallow.

VIORA T0 | MODE FIX | STEP 8/10 PROVE
$ python3 scripts/viora.py gate
==> build: python3 -m compileall -q . | PASS
==> test: python3 -m unittest discover -s tests -t . -q | PASS 4/4

VIORA T0 | MODE FIX | STEP 10/10 REPORT
VERDICT: DELIVERED
MODE: FIX | TIER: T0

EVIDENCE
| Gate | Command | Result | Fresh |
|---|---|---|---|
| test | python3 -m unittest discover -s tests -t . -q | PASS 4/4 | yes |

NOT DONE / UNPROVEN
- comment-only lines starting with # are still parsed as key=value; not in scope, not tested
- no test covers a line containing only a tab
TRANSCRIPT
python3 "$P/evals/score.py" --fixture f01-empty-body --transcript /tmp/v21tr/good.md; echo "exit=$?"

echo
echo "===================== EVALS: score a bad transcript ====================="
cat > /tmp/v21tr/bad.md <<'TRANSCRIPT'
I looked at config.py and fixed the crash. It should work now.

    try:
        key, value = line.split("=")
    except: pass

Tests pass. Let me know if you need anything else!
TRANSCRIPT
python3 "$P/evals/score.py" --fixture f01-empty-body --transcript /tmp/v21tr/bad.md; echo "exit=$? (expect 2)"

echo
echo "===================== EVALS: json + run.sh score + score-all ====================="
python3 "$P/evals/score.py" --fixture f01-empty-body --transcript /tmp/v21tr/bad.md --json | head -20
bash "$P/evals/run.sh" score f01 /tmp/v21tr/good.md 2>&1 | tail -6; echo "exit=$?"
ls -1 "$VIORA_EVAL_RESULTS" 2>/dev/null | head -4
bash "$P/evals/run.sh" score-all 2>&1 | tail -10; echo "exit=$?"
bash "$P/evals/run.sh" clean 2>&1 | tail -2; echo "exit=$?"

echo
echo "===================== RESULT: $PASS ok, $FAIL failed ====================="
