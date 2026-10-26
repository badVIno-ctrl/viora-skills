#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export SHORTS_IMAGE_PROVIDER=none
export SHORTS_MEMORY="$PWD/acceptance/reproduction-memory"
python3 tools/shorts.py doctor
python3 acceptance/make_fixture.py --long
python3 tools/shorts.py all acceptance/fixture/short.plan.json --out acceptance/out-short
python3 tools/shorts.py all acceptance/fixture/long.plan.json --out acceptance/out-long
python3 tools/shorts.py qa acceptance/out-short --strict
python3 tools/shorts.py qa acceptance/out-long --strict
python3 acceptance/verify_artifacts.py
python3 tools/shorts.py clips --video acceptance/out-long/long-8min-training.mp4 -n 1 --length 15 -o acceptance/clips-generated
python3 -m pytest tests/test_v32_long.py -q
# Отдельно полный тяжёлый регрессионный прогон:
# bash tools/check_all.sh
# Ручные проверки, реальные публикации и независимую сверку базы скрипт не имитирует.
