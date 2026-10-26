#!/usr/bin/env bash
# Fast offline advertising-contract checks. No network, paid API, publication or model calls.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
"$PY" -m pytest tests/unit/test_advertising_v34.py tests/unit/test_advertising_v341.py tests/unit/test_advertising_v35.py tests/unit/test_advertising_v35_tools.py -q -p no:cacheprovider
"$PY" tools/dash_check.py
"$PY" -m compileall -q tools/shortskit/advertising.py tools/shortskit/costs.py tools/shortskit/adrules.py tools/shortskit/admetrics.py tools/shortskit/adlinks.py tools/shortskit/adrender.py
printf 'AD CONTRACT CHECKS PASSED (not creative-performance or agent-behavior validation)\n'
