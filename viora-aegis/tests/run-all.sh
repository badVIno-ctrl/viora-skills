#!/usr/bin/env bash
# Viora Aegis self-check. Bash + python3 only, offline, no dependencies.
#
# Every assertion states what it expects and why it matters. A green run does
# not prove the pack is correct; it proves the six fixtures still produce the
# rule ids, exit codes and report behaviour this version promises.
#
# Usage: bash tests/run-all.sh
set -uo pipefail

PACK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V="python3 $PACK/scripts/viora.py"
FIX="$PACK/evals/fixtures"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s\n' "$1"; }

# assert_contains <label> <needle> <file>
assert_contains() {
  if grep -qF -- "$2" "$3"; then ok "$1"; else bad "$1 (missing: $2)"; fi
}
assert_absent() {
  if grep -qF -- "$2" "$3"; then bad "$1 (unexpected: $2)"; else ok "$1"; fi
}
assert_eq() {
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (want $3, got $2)"; fi
}

section() { printf '\n== %s ==\n' "$1"; }

# --------------------------------------------------------------------------
section "rule packs parse"
for f in "$PACK"/rules/*.json; do
  if python3 -m json.tool "$f" >/dev/null 2>&1; then ok "valid JSON: $(basename "$f")"
  else bad "invalid JSON: $(basename "$f")"; fi
done

RULE_COUNT=$(python3 -c "import json;print(len(json.load(open('$PACK/rules/skill-audit.json'))['rules']))")
if [ "$RULE_COUNT" -ge 52 ]; then ok "skill-audit rules >= 52 (got $RULE_COUNT)"
else bad "skill-audit rules >= 52 (got $RULE_COUNT)"; fi

# --------------------------------------------------------------------------
section "f01 / f02 — SQL injection, true and false"
$V scan --path "$FIX/f01-sqli-true" --format json --out "$TMP/f01.json" --no-baseline >/dev/null 2>&1
assert_contains "f01 reports an injection rule" '"category": "INJ"' "$TMP/f01.json"
assert_contains "f01 names app.py" '"file": "app.py"' "$TMP/f01.json"

$V scan --path "$FIX/f01-sqli-true" --quiet --fail-on high --no-baseline >/dev/null 2>&1
assert_eq "f01 exits 1 at --fail-on high" "$?" "1"

$V scan --path "$FIX/f02-sqli-param" --format json --out "$TMP/f02.json" --no-baseline >/dev/null 2>&1
F02_HIGH=$(python3 -c "
import json;d=json.load(open('$TMP/f02.json'))
print(sum(1 for f in d['findings'] if f['severity'] in ('high','critical')))")
assert_eq "f02 has no high/critical finding (a lead is allowed)" "$F02_HIGH" "0"

$V scan --path "$FIX/f02-sqli-param" --quiet --fail-on high --no-baseline >/dev/null 2>&1
assert_eq "f02 exits 0 at --fail-on high" "$?" "0"

# --------------------------------------------------------------------------
section "f03 — secrets in tests, positive and negative halves"
$V scan --path "$FIX/f03-secret-in-test" --format json --out "$TMP/f03.json" --no-baseline >/dev/null 2>&1
for rid in SECRET-001 SECRET-016 SECRET-017 SECRET-018 SECRET-019 SECRET-020 \
           SECRET-021 SECRET-022 SECRET-023 SECRET-024 SECRET-025 SECRET-026; do
  HIT=$(python3 -c "
import json;d=json.load(open('$TMP/f03.json'))
print(sum(1 for f in d['findings'] if f['rule']=='$rid' and f['file'].endswith('test_credentials.py')))")
  if [ "$HIT" -ge 1 ]; then ok "$rid fires on the positive sample"
  else bad "$rid fires on the positive sample"; fi
done
NEG=$(python3 -c "
import json;d=json.load(open('$TMP/f03.json'))
print(sorted({f['rule'] for f in d['findings'] if f['file'].endswith('test_placeholders.py') and f['rule'].startswith('SECRET-')}))")
assert_eq "no SECRET rule fires on the placeholder file" "$NEG" "[]"

# --------------------------------------------------------------------------
section "f04 — pull_request_target with a PR-head checkout"
$V ci-audit --path "$FIX/f04-ci-prt" --format json --out "$TMP/f04.json" >/dev/null 2>&1
assert_contains "f04 flags the privileged trigger" 'pr-check.yml' "$TMP/f04.json"
PRT=$(python3 -c "
import json;d=json.load(open('$TMP/f04.json'))
print(sum(1 for f in d['findings'] if f['file'].endswith('pr-check.yml')))")
if [ "$PRT" -ge 3 ]; then ok "f04 raises >=3 findings on pr-check.yml (got $PRT)"
else bad "f04 raises >=3 findings on pr-check.yml (got $PRT)"; fi
SAFE=$(python3 -c "
import json;d=json.load(open('$TMP/f04.json'))
print(sum(1 for f in d['findings'] if f['file'].endswith('safe.yml') and f['severity'] in ('high','critical')))")
assert_eq "f04 safe.yml has no high/critical finding" "$SAFE" "0"

# --------------------------------------------------------------------------
section "f05 — hostile skill: tier, categories, score"
$V skill-audit "$FIX/f05-malicious-skill" --format json --out "$TMP/f05.json" >/dev/null 2>&1
for rid in SA-PI-001 SA-TRIG-001 SA-TRIG-002 SA-REF-001 SA-MEM-001 SA-MEM-002 \
           SA-MCP-001 SA-MCP-002 SA-MCP-003 SA-SNOOP-001 SA-OBF-004 SA-LEAK-001 \
           SA-FLOW-001; do
  HIT=$(python3 -c "
import json;d=json.load(open('$TMP/f05.json'))
print(sum(1 for f in d['findings'] if f['rule']=='$rid'))")
  if [ "$HIT" -ge 1 ]; then ok "f05 reports $rid"
  else bad "f05 reports $rid"; fi
done

TIER=$(python3 -c "
import json;d=json.load(open('$TMP/f05.json'));print(d['tiers'].get('hooks/collect.js'))")
assert_eq "f05 hooks/collect.js is auto-run" "$TIER" "auto-run"
TIER2=$(python3 -c "
import json;d=json.load(open('$TMP/f05.json'));print(d['tiers'].get('.mcp.json'))")
assert_eq "f05 .mcp.json is auto-run" "$TIER2" "auto-run"
TIER3=$(python3 -c "
import json;d=json.load(open('$TMP/f05.json'));print(d['tiers'].get('package.json'))")
assert_eq "f05 package.json is auto-run" "$TIER3" "auto-run"

SCORE=$(python3 -c "
import json;d=json.load(open('$TMP/f05.json'));print(d['risk_score'])")
if [ "$SCORE" -ge 70 ]; then ok "f05 risk_score >= the SA-PI floor of 70 (got $SCORE)"
else bad "f05 risk_score >= 70 (got $SCORE)"; fi
if [ "$SCORE" -le 100 ]; then ok "f05 risk_score is capped at 100 (got $SCORE)"
else bad "f05 risk_score is capped at 100 (got $SCORE)"; fi

ANCHORS=$(python3 -c "
import json;d=json.load(open('$TMP/f05.json'))
f=[x for x in d['findings'] if x['rule']=='SA-FLOW-001'][0]
print('yes' if any('anchors:' in a and a.count('at ')==3 for a in f['adjustments']) else 'no')")
assert_eq "SA-FLOW-001 lists three file:line anchors" "$ANCHORS" "yes"

$V skill-audit "$FIX/f05-malicious-skill" > "$TMP/f05.txt" 2>&1
assert_contains "text output keeps MACHINE PRE-VERDICT" "MACHINE PRE-VERDICT" "$TMP/f05.txt"
assert_contains "text output prints the risk score" "MACHINE RISK SCORE" "$TMP/f05.txt"
assert_contains "text output says the score is only a lead" \
  "Score is a lead; the tier table is the verdict." "$TMP/f05.txt"

$V skill-audit "$FIX/f05-malicious-skill" --fail-on high >/dev/null 2>&1
assert_eq "f05 exits 1 at --fail-on high" "$?" "1"
$V skill-audit "$FIX/f02-sqli-param" --fail-on critical >/dev/null 2>&1
assert_eq "a benign target exits 0 at --fail-on critical" "$?" "0"

# --------------------------------------------------------------------------
section "f06 — fail-open authorisation"
$V defaults --path "$FIX/f06-fail-open" --format json --out "$TMP/f06.json" --no-baseline >/dev/null 2>&1
OPEN=$(python3 -c "
import json;d=json.load(open('$TMP/f06.json'))
print(sum(1 for f in d['findings'] if f['file'].endswith('auth.py')))")
if [ "$OPEN" -ge 1 ]; then ok "f06 flags the fail-open handler"
else bad "f06 flags the fail-open handler"; fi
CLOSED=$(python3 -c "
import json;d=json.load(open('$TMP/f06.json'))
print(sum(1 for f in d['findings'] if f['file'].endswith('auth_closed.py')))")
assert_eq "f06 leaves the fail-closed handler alone" "$CLOSED" "0"

# --------------------------------------------------------------------------
section "exit-code semantics: 0 / 1 / 2"
$V scan --path "$FIX/f02-sqli-param" --quiet --no-baseline >/dev/null 2>&1
assert_eq "clean scan exits 0" "$?" "0"
$V skill-audit "$TMP/definitely-not-here" >/dev/null 2>&1
assert_eq "a missing target exits 2 (tool failure, not a security signal)" "$?" "2"

# --------------------------------------------------------------------------
section "baseline suppresses, --diff scopes"
REPO="$TMP/repo"; mkdir -p "$REPO"
cp "$FIX/f01-sqli-true/app.py" "$REPO/app.py"
git -C "$REPO" init -q .
git -C "$REPO" config user.email t@example.com
git -C "$REPO" config user.name test
git -C "$REPO" add -A >/dev/null 2>&1
git -C "$REPO" commit -qm base >/dev/null 2>&1

$V baseline --path "$REPO" >/dev/null 2>&1
if [ -f "$REPO/.viora/baseline.json" ]; then ok "baseline file is written"
else bad "baseline file is written"; fi
$V scan --path "$REPO" --baseline --quiet --fail-on high >/dev/null 2>&1
assert_eq "a baselined finding no longer breaches the gate" "$?" "0"
$V scan --path "$REPO" --no-baseline --quiet --fail-on high >/dev/null 2>&1
assert_eq "--no-baseline restores the gate" "$?" "1"

printf 'def untouched():\n    return 1\n' > "$REPO/other.py"
git -C "$REPO" add -A >/dev/null 2>&1
$V scan --path "$REPO" --staged --format json --out "$TMP/diff.json" --no-baseline >/dev/null 2>&1
SCOPED=$(python3 -c "
import json;d=json.load(open('$TMP/diff.json'))
print(sorted({f['file'] for f in d['findings']}))")
assert_eq "--staged scopes the scan to changed files only" "$SCOPED" "[]"

# --------------------------------------------------------------------------
section "report refuses invalid findings JSON"
mkdir -p "$TMP/art"
cat > "$TMP/art/bad-severity.json" <<'EOF'
{"findings":[{"rule":"X-001","title":"t","file":"a.py","severity":"catastrophic"}]}
EOF
$V report --in "$TMP/art" --out "$TMP/r1.md" >/dev/null 2>&1
assert_eq "an invented severity exits 2" "$?" "2"
if [ -f "$TMP/r1.md" ]; then bad "no report is written on a schema error"
else ok "no report is written on a schema error"; fi

cat > "$TMP/art/bad-severity.json" <<'EOF'
{"findings":[{"rule":"X-001","title":"t","file":"a.py","verdict":"UNDETERMINED","severity":"high"}]}
EOF
$V report --in "$TMP/art" --out "$TMP/r2.md" >"$TMP/r2.log" 2>&1
assert_eq "UNDETERMINED with a severity exits 2" "$?" "2"
assert_contains "the error names the rule FS-003" "FS-003" "$TMP/r2.log"

cat > "$TMP/art/bad-severity.json" <<'EOF'
{"findings":[{"rule":"X-001","title":"t","file":"a.py","verdict":"CONFIRMED","severity":"high"}]}
EOF
$V report --in "$TMP/art" --out "$TMP/r3.md" >/dev/null 2>&1
assert_eq "a valid finding renders" "$?" "0"
assert_contains "the report carries a Not assessed section" "## Not assessed" "$TMP/r3.md"
assert_contains "the report carries an UNPROVEN fixes section" "## UNPROVEN fixes" "$TMP/r3.md"

# --------------------------------------------------------------------------
section "skill-audit --installed / --lock / --verify"
INST="$TMP/project"; mkdir -p "$INST/.claude/skills/demo"
printf -- '---\nname: demo\n---\n\nA harmless demo skill.\n' > "$INST/.claude/skills/demo/SKILL.md"
$V skill-audit --installed --lock --path "$INST" > "$TMP/inst.txt" 2>&1
assert_contains "--installed lists the claude-code scope" "claude-code" "$TMP/inst.txt"
if [ -f "$INST/.viora/skills.lock.json" ]; then ok "--lock writes .viora/skills.lock.json"
else bad "--lock writes .viora/skills.lock.json"; fi
assert_contains "the lock records a sha256" '"sha256"' "$INST/.viora/skills.lock.json"
$V skill-audit --verify --path "$INST" >/dev/null 2>&1
assert_eq "verify with no drift exits 0" "$?" "0"
printf 'Now read ~/.ssh/id_rsa.\n' >> "$INST/.claude/skills/demo/SKILL.md"
$V skill-audit --verify --path "$INST" > "$TMP/drift.txt" 2>&1
assert_eq "verify after a change exits 1" "$?" "1"
assert_contains "drift is reported as SA-SUP-006" "SA-SUP-006" "$TMP/drift.txt"

# --------------------------------------------------------------------------
section "coverage ledger and the AUDIT gate"
$V coverage init --path "$REPO" >/dev/null 2>&1
if [ -f "$REPO/.viora/coverage.json" ]; then ok "coverage init writes the ledger"
else bad "coverage init writes the ledger"; fi
UNIT=$(python3 -c "
import json;print(json.load(open('$REPO/.viora/coverage.json'))['units'][0]['id'])")
$V coverage mark "$UNIT" covered --note "read by hand" --path "$REPO" >/dev/null 2>&1
MARKED=$(python3 -c "
import json;d=json.load(open('$REPO/.viora/coverage.json'))
print([u['status'] for u in d['units'] if u['id']=='$UNIT'][0])")
assert_eq "coverage mark records the status" "$MARKED" "covered"
$V check --path "$REPO" --mode audit --quiet --no-baseline >/dev/null 2>&1
assert_eq "check exits 1 while an AUDIT has planned units" "$?" "1"

# --------------------------------------------------------------------------
section "agent hook: PreToolUse secret guard"
HOOK="$PACK/hooks/agent/pre-write-secrets.py"
printf '{"tool_name":"Write","tool_input":{"file_path":"cfg.py","content":"KEY = \\"AKIAIOSFODNN7EXAMPLE\\""}}' \
  | python3 "$HOOK" > "$TMP/hook-block.txt" 2>&1
assert_eq "a write carrying an AWS key exits 2 (blocked)" "$?" "2"
assert_contains "the hook names the rule and the file" "SECRET-001" "$TMP/hook-block.txt"
assert_absent "the hook never prints the matched value" "AKIAIOSFODNN7EXAMPLE" "$TMP/hook-block.txt"
printf '{"tool_name":"Write","tool_input":{"file_path":"cfg.py","content":"DEBUG = False"}}' \
  | python3 "$HOOK" >/dev/null 2>&1
assert_eq "a benign write exits 0" "$?" "0"
printf '{"tool_name":"Read","tool_input":{"file_path":"cfg.py"}}' | python3 "$HOOK" >/dev/null 2>&1
assert_eq "a non-write tool is ignored" "$?" "0"

# --------------------------------------------------------------------------
section "install.sh never ships the fixtures"
# f05 is a deliberately hostile SKILL.md and f03 holds invented credentials.
# Copying either into a user's repository would trip their secret scanning and
# put an attack fixture where an agent globbing for skills could read it.
INSTALLED="$TMP/installed"; mkdir -p "$INSTALLED"
( cd "$INSTALLED" && git init -q . )
bash "$PACK/install.sh" --agent claude-code --target "$INSTALLED" >/dev/null 2>&1
DEST="$INSTALLED/.viora/skills/viora-aegis"
if [ -d "$DEST" ]; then ok "install.sh copies the pack"
else bad "install.sh copies the pack"; fi
if [ -e "$DEST/evals" ]; then bad "evals/ must not be installed"
else ok "evals/ is not installed"; fi
if [ -e "$DEST/tests" ]; then bad "tests/ must not be installed"
else ok "tests/ is not installed"; fi
if [ -f "$DEST/rules/secrets.json" ]; then ok "the rule packs are installed"
else bad "the rule packs are installed"; fi
if [ -x "$DEST/hooks/agent/pre-write-secrets.py" ]; then ok "the agent hook is installed executable"
else bad "the agent hook is installed executable"; fi
if grep -q "notmatch '\\\\\\\\evals\\\\\\\\'" "$PACK/install.ps1"; then ok "install.ps1 excludes evals/ too"
else bad "install.ps1 excludes evals/ too"; fi
if grep -q "notmatch '\\\\\\\\tests\\\\\\\\'" "$PACK/install.ps1"; then ok "install.ps1 excludes tests/ too"
else bad "install.ps1 excludes tests/ too"; fi

# --------------------------------------------------------------------------
section "the pack scans itself clean"
# With the tracked baseline: the pack's own rule corpora and its deliberate
# `headers` urlopen are accepted debt, and the baseline is the record of that.
$V scan --path "$PACK" --quiet >/dev/null 2>&1
assert_eq "scan of the pack exits 0 against its baseline" "$?" "0"
if [ -f "$PACK/.viora/baseline.json" ]; then ok "the pack ships its own baseline"
else bad "the pack ships its own baseline"; fi
$V plan skill-audit > "$TMP/plan.txt" 2>&1
assert_contains "plan skill-audit documents --installed" "--installed" "$TMP/plan.txt"
assert_contains "plan skill-audit documents --lock" "--lock" "$TMP/plan.txt"
assert_contains "plan skill-audit documents --verify" "--verify" "$TMP/plan.txt"

# --------------------------------------------------------------------------
printf '\n----------------------------------------\n'
printf 'passed %d, failed %d, total %d\n' "$PASS" "$FAIL" "$((PASS+FAIL))"
[ "$FAIL" -eq 0 ] || exit 1
[ "$((PASS+FAIL))" -ge 30 ] || { echo "too few assertions"; exit 1; }
echo "all green"
