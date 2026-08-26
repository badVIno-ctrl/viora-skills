#!/usr/bin/env bash
# VioraCode self-test runner.
#
# Every suite builds a throwaway git repo under /tmp and drives the REAL scripts:
# scripts/viora.py, scripts/verify.sh, hooks/pre-commit, evals/score.py.
# Nothing here touches your project, and nothing here needs network access.
#
# Usage:  bash tests/run-all.sh            # all suites
#         bash tests/01-conductor.sh       # one suite, full output
#
# Requirements: bash, git, python3. That is all.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EXPECTED_TOTAL=85
TOTAL_OK=0
TOTAL_FAIL=0
BROKEN=""

for suite in "$HERE"/0*.sh; do
	name="$(basename "$suite")"
	printf '=== %s ' "$name"
	printf '%.0s=' $(seq 1 $((60 - ${#name}))); printf '\n'

	log="$(mktemp -t viora-selftest.XXXXXX)"
	bash "$suite" >"$log" 2>&1
	line="$(grep -E 'RESULT: [0-9]+ ok, [0-9]+ failed' "$log" | tail -1)"

	if [ -z "$line" ]; then
		echo "  no RESULT line - the suite itself crashed. Last 20 lines:"
		tail -n 20 "$log" | sed 's/^/    /'
		BROKEN="$BROKEN $name"
		echo
		continue
	fi

	ok="$(printf '%s' "$line" | sed -n 's/.*RESULT: \([0-9]*\) ok.*/\1/p')"
	bad="$(printf '%s' "$line" | sed -n 's/.*ok, \([0-9]*\) failed.*/\1/p')"
	ok="${ok:-0}"; bad="${bad:-0}"
	TOTAL_OK=$((TOTAL_OK + ok))
	TOTAL_FAIL=$((TOTAL_FAIL + bad))

	if [ "$bad" = "0" ]; then
		echo "  $ok assertion(s) passed"
	else
		echo "  $ok passed, $bad FAILED:"
		grep -F '[FAIL]' "$log" | sed 's/^/  /' | head -n 20
		echo "  full log: $log"
	fi
	echo
done

echo "==========================================================="
if [ -n "$BROKEN" ]; then
	echo "SUITES THAT DID NOT FINISH:$BROKEN"
fi
echo "TOTAL: $TOTAL_OK passed, $TOTAL_FAIL failed  (expected $EXPECTED_TOTAL assertions)"

if [ "$TOTAL_FAIL" != "0" ] || [ -n "$BROKEN" ]; then
	echo
	echo "A red suite means the conductor is not enforcing what the docs promise."
	echo "Fix the code or fix the doc - do not fix the test to make the number green."
	exit 1
fi

if [ "$TOTAL_OK" -lt "$EXPECTED_TOTAL" ]; then
	echo
	echo "Green, but fewer assertions ran than expected. A suite may have exited early."
	exit 1
fi

echo "All green. The refusals in the docs are the refusals in the code."
