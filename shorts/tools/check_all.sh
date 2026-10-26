#!/usr/bin/env bash
# One command for all checks. Fails on any error.
#   bash tools/check_all.sh            offline: compile, schema, unit, integration, e2e, bad cases
#   SHORTS_NETWORK=1 bash tools/check_all.sh    + network tests (sites, YouTube, TTS service)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

echo "== doctor"
"$PY" tools/shorts.py doctor > /dev/null || { "$PY" tools/shorts.py doctor; echo "doctor: missing required tools"; exit 1; }

echo "== compile"
"$PY" -m compileall -q tools tests

echo "== schema + example plans"
"$PY" tools/shorts.py validate schema/plan.example.json
"$PY" tools/shorts.py validate tests/fixtures/plan.offline.json
for f in examples/*.plan.json; do
  [ -e "$f" ] || continue
  "$PY" tools/shorts.py validate --allow-missing-media "$f"   # media is not in git: examples/media/README.md
done

echo "== no long dashes in user-facing skill texts"
# Python, not grep: grep with $'\u2014' matched nothing under LANG=C / POSIX (the check passed silently)
"$PY" tools/dash_check.py || { echo "long dash found"; exit 1; }

echo "== evals file"
"$PY" -c "import json;d=json.load(open('evals/cases.json'));assert len(d['cases'])>=10;print(len(d['cases']),'cases')"

echo "== tests"
"$PY" -m pytest tests -q -p no:cacheprovider
echo "ALL CHECKS PASSED"
