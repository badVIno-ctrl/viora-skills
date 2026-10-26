"""Speed check for a 20 s film edit: `edit` + `all` with a cold cache, wall time per step.

python3 tools/bench.py --video film.mp4 [--length 20] [--out /tmp/bench]   # target: <= 90 s on 4 cores
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--length", type=float, default=20)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = Path(a.out or tempfile.mkdtemp(prefix="shorts-bench-"))
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    env = dict(os.environ, SHORTS_CACHE=str(out / "cache"), SHORTS_MEMORY=str(out / "memory"),
               SHORTS_IMAGE_PROVIDER="none")
    py = [sys.executable, str(ROOT / "tools" / "shorts.py")]
    steps = {}
    t = time.time()
    subprocess.run(py + ["edit", "--video", a.video, "--length", str(a.length), "--lang", "en", "--title", "BENCH EDIT",
                         "--handle", "VioraStudio", "--link", "https://t.me/VioraStudio", "-o", str(out / "plan.json")],
                   env=env, check=True)
    steps["edit"] = round(time.time() - t, 1)
    t = time.time()
    rc = subprocess.run(py + ["all", str(out / "plan.json"), "--out", str(out / "video")], env=env).returncode
    steps["all"] = round(time.time() - t, 1)
    man = json.loads((out / "video" / "manifest.json").read_text())
    steps["render_inside_all"] = man["render_seconds"]
    rep = {"cores": os.cpu_count(), "steps_s": steps, "total_s": round(steps["edit"] + steps["all"], 1),
           "qa_exit": rc, "video": str(out / "video" / man["video"])}
    print(json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
