#!/usr/bin/env bash
# v2.2 suite: token discipline (squeeze), three report buckets, decisions,
# expectations/SURPRISE, ceilings, the stop hook and resume.
# Everything runs against the REAL scripts in a throwaway repo under /tmp.
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P=${PKG}
W=/tmp/v22a
rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
git init -q .
git config user.email t@example.com; git config user.name tester
cp -r "$P/scripts" .
mkdir -p src tests
: > src/__init__.py
: > tests/__init__.py
printf 'def add(a, b):\n    return a + b\n' > src/app.py
printf 'import unittest\n\nfrom src.app import add\n\n\nclass T(unittest.TestCase):\n    def test_none(self):\n        with self.assertRaisesRegex(TypeError, "does not accept None"):\n            add(None, 1)\n' > tests/test_app.py
git add -A && git commit -qm base

PASS=0; FAIL=0
V() { python3 scripts/viora.py "$@"; }
ok() { echo "  [ok] $1"; PASS=$((PASS+1)); }
bad() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
# r <expected_exit> <cmd...>
r() { local want="$1"; shift; local out code; out="$(V "$@" 2>&1)"; code=$?
  printf '%s\n' "$out" | tail -n 3
  if [ "$code" = "$want" ]; then ok "exit=$code"; else bad "exit=$code, expected $want"; fi; echo; }
has() { local label="$1" needle="$2"; shift 2; local out; out="$(V "$@" 2>&1)"
  if printf '%s' "$out" | grep -qF -- "$needle"; then ok "$label"
  else bad "$label - no '$needle' in:"; printf '%s\n' "$out" | tail -n 12; fi; }
lacks() { local label="$1" needle="$2"; shift 2; local out; out="$(V "$@" 2>&1)"
  if printf '%s' "$out" | grep -qF -- "$needle"; then bad "$label - found '$needle'"
  else ok "$label"; fi; }
sq() { python3 scripts/squeeze.py "$@"; }

echo "===================== B13.1 squeeze: repeats, frames, windows ====================="
OUT="$(python3 -c "print('\n'.join(['ok']*3+['Error: boom']+['at x (node_modules/a.js:1)']*40+['done']))" | sq)"
printf '%s\n' "$OUT"
printf '%s' "$OUT" | grep -qF 'ok ×3' && ok "identical lines collapse with ×N" || bad "no ×N collapse"
printf '%s' "$OUT" | grep -qF '40 frames in node_modules' && ok "vendor frames collapse to one line" || bad "frames not collapsed"
printf '%s' "$OUT" | grep -qF 'Error: boom' && ok "the failure line survives" || bad "failure line lost"
printf '%s' "$OUT" | grep -qE 'squeezed [0-9]+→[0-9]+ lines' && ok "footer reports the ratio" || bad "no squeezed footer"
echo

echo "===================== B13.2 squeeze: middle elision keeps failures ====================="
OUT="$(python3 -c "
lines=['head %d'%i for i in range(40)]+['FAIL: the decisive line']+['tail %d'%i for i in range(40)]
print('\n'.join(lines))" | sq --keep 5 --tail 5)"
printf '%s' "$OUT" | grep -qF 'FAIL: the decisive line' && ok "a FAIL in the middle is never dropped" || bad "middle FAIL dropped"
printf '%s' "$OUT" | grep -qF 'head 0' && ok "--keep holds the head" || bad "head missing"
printf '%s' "$OUT" | grep -qF 'tail 39' && ok "--tail holds the verdict" || bad "tail missing"
LINES=$(printf '%s\n' "$OUT" | wc -l)
if [ "$LINES" -lt 20 ]; then ok "81 lines squeezed to $LINES"; else bad "still $LINES lines"; fi
echo

echo "===================== B13.3 squeeze: JSON arrays and strings ====================="
OUT="$(python3 -c "
import json;print(json.dumps({'items':list(range(50)),'blob':'x'*500}))" | sq --json)"
printf '%s' "$OUT" | grep -qF '+47' && ok "arrays over 10 keep 3 items + …+N" || bad "array not truncated"
printf '%s' "$OUT" | grep -qF '[500 chars]' && ok "long strings truncate with their length" || bad "string not truncated"
OUT="$(printf '\033[31mred text\033[0m\n' | sq --no-footer)"
if [ "$OUT" = "red text" ]; then ok "ANSI escapes are stripped"; else bad "ANSI survived: $OUT"; fi
echo

echo "===================== B13.4 the gate writes a full log, the row carries the squeeze ====================="
r 0 tier --set T1
r 0 start --mode FIX --tier T1 --task "add() must reject None"
r 0 contract --goal "add(None, 1) raises TypeError" --done-test "python3 -m unittest discover -s tests -t . -q" --protected "add() signature"
has "gate prints the squeezed footer" "squeezed" gate
LOGS=$(ls .viora/logs/*.log 2>/dev/null | wc -l)
if [ "$LOGS" -ge 1 ]; then ok "full log written to .viora/logs ($LOGS file(s))"; else bad "no log file written"; fi
python3 -c "
import json
rows=[json.loads(l) for l in open('.viora/evidence.jsonl')]
assert any(r.get('log') for r in rows), 'no row links a log'
assert any(r.get('squeezed') for r in rows), 'no row stores squeezed text'
print('  rows with logs:', sum(1 for r in rows if r.get('log')))" && ok "evidence rows link the log and store the squeeze" || bad "evidence row missing log/squeezed"
has "report links the full log per row" "full log: .viora/logs/" report --verdict BLOCKED --no-archive
has "evidence --full prints the raw file" "Evidence table" evidence --full
echo

echo "===================== B13.5 --terse prints one line, errors stay exact ====================="
LINES=$(V --terse gate 2>&1 | wc -l)
if [ "$LINES" -le 3 ]; then ok "terse gate is $LINES line(s)"; else bad "terse gate printed $LINES lines"; fi
has "terse doctor still names the tool table" "tools:" doctor --terse
touch .viora/terse
LINES=$(V next 2>&1 | wc -l)
if [ "$LINES" -le 4 ]; then ok ".viora/terse switches next to $LINES line(s)"; else bad "terse file ignored ($LINES lines)"; fi
rm .viora/terse
echo

echo "===================== B14 viora:ceiling markers are counted and reported ====================="
printf 'def add(a, b):\n    # viora:ceiling exact ints only; widen to Decimal when money arrives\n    if a is None or b is None:\n        raise TypeError("add() does not accept None")\n    return a + b\n' > src/app.py
r 0 plan --files src/app.py --lines 20 --risk "src/app.py=the only caller of add() is the export path"
has "plan echoes the risk line" "RISK src/app.py" plan --show
has "scope counts the ceiling" "ceilings: 1 viora:ceiling marker" scope
has "report lists ceilings under FOLLOW-UPS" "ceiling @ src/app.py:2" report --verdict BLOCKED --no-archive
echo

echo "===================== B3 --expect mismatch marks the row SURPRISE ====================="
r 0 gate --only build --expect "no such phrase anywhere in this output"
has "check names the surprise" "is a SURPRISE" check
has "next demands a re-derived plan" "re-derive PLAN" next
for n in 1 2 3 4 5; do V done "$n" --note "step $n closed by the v2.2 suite" >/dev/null 2>&1; done
OUT="$(V done 6 --note "GREEN" 2>&1)"; CODE=$?
printf '%s\n' "$OUT" | tail -n 2
if [ "$CODE" != "0" ]; then ok "done 6 is refused while the SURPRISE is open"; else bad "done 6 closed under an open SURPRISE"; fi
r 0 plan --files src/app.py --lines 20
lacks "a re-derived plan clears it" "SURPRISE" next
r 0 done 6 --note "GREEN: None guard in add()"
echo

echo "===================== B3b a matching --expect is not a surprise ====================="
r 0 gate --only build --expect "PASS"
lacks "no surprise when the expectation holds" "is a SURPRISE" check
echo

echo "===================== B1 three buckets: hedges move to BELIEVED ====================="
r 0 done 7 --note "CLEAN: this should be fine after the refactor"
has "VERIFIED section exists" "VERIFIED (command run after the last edit" report --verdict BLOCKED --no-archive
has "hedged note lands in BELIEVED with its word" "hedge: should" report --verdict BLOCKED --no-archive
has "NOT CHECKED says what it would take" "NOT CHECKED" report --verdict BLOCKED --no-archive
has "check flags the hedged note" "note is hedged (hedge: should)" check
echo

echo "===================== B1b a run whose DONE-TEST is unverified is NOT DONE ====================="
has "verdict is NOT DONE without the done-test" "VERDICT: NOT DONE" report --verdict DELIVERED --no-archive
r 0 evidence --gate done-test --command "python3 -m unittest discover -s tests -t . -q" --result "PASS 1/1"
has "and DELIVERED once the done-test is recorded" "VERDICT: DELIVERED" report --verdict DELIVERED --no-archive
has "the done-test row is in VERIFIED" "done-test: \`python3 -m unittest discover -s tests -t . -q\`" report --verdict DELIVERED --no-archive
echo

echo "===================== B2 decisions ====================="
r 0 decision "soft delete over hard delete because exports still need the rows"
has "report prints a DECISIONS section" "DECISIONS" report --verdict DELIVERED --no-archive
r 0 decision "drop the legacy column because nothing reads it" --irreversible
has "check refuses an unapproved irreversible decision" "irreversible decision without approval" check
r 1 check
r 0 decision "drop the legacy column because nothing reads it" --irreversible --approved
has "an approved one is marked in the report" "[IRREVERSIBLE, approved]" report --verdict DELIVERED --no-archive
echo

echo "===================== B15 the stop hook ====================="
echo '{}' | V check --hook; CODE=$?
if [ "$CODE" = "2" ]; then ok "hook exits 2 while an unapproved decision stands"; else bad "hook exit=$CODE, expected 2"; fi
python3 - <<'PY'
import json, pathlib
p = pathlib.Path('.viora/state.json')
st = json.loads(p.read_text())
st['decisions'] = [d for d in st['decisions'] if not d.get('irreversible') or d.get('approved')]
p.write_text(json.dumps(st, indent=2))
PY
echo '{}' | V check --hook; CODE=$?
if [ "$CODE" = "0" ]; then ok "a clean run does not block the stop"; else bad "hook exit=$CODE, expected 0"; fi
printf '\n# an edit that makes every gate stale\n' >> src/app.py
OUT="$(echo '{}' | V check --hook 2>&1)"; CODE=$?
printf '%s\n' "$OUT" | tail -n 1
if [ "$CODE" = "2" ]; then ok "STALE evidence blocks the stop"; else bad "hook exit=$CODE, expected 2"; fi
if [ "$(printf '%s\n' "$OUT" | wc -l)" -le 2 ]; then ok "the hook reason is one line"; else bad "hook printed more than one line"; fi
r 0 gate
OUT="$(echo '{"last_assistant_message":"All done, it works now."}' | V check --hook 2>&1)"; CODE=$?
printf '%s\n' "$OUT" | tail -n 1
V start --mode FIX --tier T1 --task "a fresh run sits below step 10" --force >/dev/null 2>&1
OUT="$(echo '{"last_assistant_message":"All done, it works now."}' | V check --hook 2>&1)"; CODE=$?
printf '%s\n' "$OUT" | tail -n 1
if [ "$CODE" = "2" ]; then ok "a completion claim below step 10 blocks the stop"; else bad "hook exit=$CODE, expected 2"; fi
OUT="$(echo 'not json at all' | V check --hook 2>&1)"; CODE=$?
if [ "$CODE" != "1" ]; then ok "malformed hook input does not crash the hook (exit=$CODE)"; else bad "hook crashed on bad input"; fi
echo

echo "===================== B9 resume: one screen for a fresh session ====================="
r 0 contract --goal "resume prints the state" --done-test "python3 scripts/viora.py resume" --protected "nothing"
r 0 plan --files src/app.py --lines 20 --risk "src/app.py=single owner of add()"
r 0 decision "keep the guard in add() because callers cannot be changed"
OUT="$(V resume 2>&1)"
printf '%s\n' "$OUT"
for needle in "tier T1" "DONE-TEST:" "plan: src/app.py" "stale rows:" "surprises:" "open decisions:" "ceilings:" "last notes:"; do
  printf '%s' "$OUT" | grep -qF -- "$needle" && ok "resume shows: $needle" || bad "resume missing: $needle"
done
LINES=$(printf '%s\n' "$OUT" | wc -l)
if [ "$LINES" -le 20 ]; then ok "resume fits one screen ($LINES lines)"; else bad "resume is $LINES lines"; fi
echo

echo "===================== B4/B10 doctor: which table and context budget ====================="
has "doctor prints a which table" "which - the tools this stack needs" doctor
has "and names python3 with a path" "python3    /" doctor
mkdir -p .claude/skills/demo
python3 -c "open('AGENTS.md','w').write('word '*30000)"
has "doctor --context warns above 25k tokens" "above 25k tokens" doctor --context
rm -f AGENTS.md
echo

echo "===================== B6 the trigger eval file is real JSON ====================="
python3 - "$P/evals/triggers.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
cases = data["cases"]
should = [c for c in cases if c["should_trigger"]]
shouldnt = [c for c in cases if not c["should_trigger"]]
assert len(cases) == 20, "expected 20 cases, found %d" % len(cases)
assert len(should) == 10 and len(shouldnt) == 10, "expected 10/10, found %d/%d" % (len(should), len(shouldnt))
assert any(any(ch > "\u0400" for ch in c["query"]) for c in should), "no non-latin query"
for c in cases:
    assert c["why"].strip(), "case %s has no why" % c["id"]
print("  20 cases: %d should, %d should-not" % (len(should), len(shouldnt)))
PY
if [ $? = 0 ]; then ok "evals/triggers.json holds 20 labelled cases"; else bad "triggers.json is malformed"; fi
echo

echo "===================== B7 less.py ranks cuts, not bugs ====================="
mkdir -p pkg
printf '{"dependencies":{"lodash":"^4","moment":"^2","axios":"^1","uuid":"^9","left-pad":"^1"}}\n' > package.json
printf 'import six\nimport pytz\n\n\ndef get_user(uid):\n    return fetch_user(uid)\n' > pkg/wrap.py
OUT="$(python3 scripts/less.py . 2>&1)"
printf '%s\n' "$OUT" | tail -n 8
printf '%s' "$OUT" | grep -qF 'stdlib:' && ok "python stdlib replacements are named" || bad "no stdlib: findings"
printf '%s' "$OUT" | grep -qF 'native:' && ok "js platform replacements are named" || bad "no native: findings"
printf '%s' "$OUT" | grep -qF 'lodash' && ok "lodash is called out" || bad "lodash missed"
printf '%s' "$OUT" | grep -qE 'net: -[0-9]+ lines' && ok "footer totals the possible cut" || bad "no net: footer"
python3 scripts/less.py --help 2>&1 | grep -qF 'out of scope' && ok "--help says correctness/security are out of scope" || bad "--help does not scope itself"
rm -f package.json; rm -rf pkg
echo

echo "===================== B12 spec section in REVIEW mode ====================="
r 0 start --mode REVIEW --tier T1 --task "review the None guard" --force
r 0 contract --goal "judge the diff" --done-test "python3 -m unittest discover -s tests -t . -q" --protected "nothing"
has "report says so when no spec was recorded" "no spec available" report --verdict BLOCKED --no-archive
r 0 contract --goal "judge the diff" --done-test "python3 -m unittest discover -s tests -t . -q" --protected "nothing" --spec "https://example.invalid/issue/42"
has "a recorded spec appears in the SPEC section" "https://example.invalid/issue/42" report --verdict BLOCKED --no-archive
has "SPEC section asks the four questions" "holds / contradicts / absent / undocumented" report --verdict BLOCKED --no-archive
echo

echo "===================== RESULT: $PASS ok, $FAIL failed ====================="
