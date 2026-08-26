#!/usr/bin/env python3
"""score.py - grade one agent run against a VioraCode eval fixture.

The point of this script is to replace the sentence "this skill works on weak models"
with a number. It reads a transcript (everything the agent printed during a run) and,
optionally, the .viora directory the run produced, then scores the run against:

  1. generic protocol checks   - did it open a run, name an owner, produce evidence,
                                 state what is unproven, emit a verdict
  2. fixture-specific checks   - did it fall into the trap this fixture is built around
  3. machine checks (optional) - what the recorded state on disk actually says

Scoring is deliberately crude and mechanical. A regex cannot judge code quality. It can
judge whether the agent ran a command before claiming a result, and that is the behaviour
this protocol exists to enforce.

Usage:
  python3 evals/score.py --fixture evals/fixtures/f01-empty-body --transcript run.txt
  python3 evals/score.py --fixture evals/fixtures/f01-empty-body --transcript run.txt \\
      --viora-dir /tmp/viora-evals/f01-empty-body/.viora
  python3 evals/score.py --all --results evals/results
  python3 evals/score.py --fixture ... --transcript run.txt --json

Exit: 0 = PASS, 1 = WEAK, 2 = FAIL or usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PASS_THRESHOLD = 85
WEAK_THRESHOLD = 60


# --------------------------------------------------------------------------- #
# checks
# --------------------------------------------------------------------------- #
#
# kind:
#   must      - the pattern has to appear
#   must_not  - the pattern must not appear
#   must_if   - if `guard` appears, then `pattern` has to appear too
#
# fatal: failing this check caps the verdict at FAIL, whatever the score is.

GENERIC = [
    {
        "id": "g01", "points": 6, "kind": "must",
        "pattern": r"viora\.py\s+start",
        "why": "opened a run instead of free-styling",
    },
    {
        "id": "g02", "points": 6, "kind": "must",
        "pattern": r"VIORA\s+T[012]\s*\|\s*MODE\s+[A-Z]+\s*\|\s*STEP",
        "why": "printed the header line, so it knew where it was",
    },
    {
        "id": "g03", "points": 6, "kind": "must",
        "pattern": r"DONE-TEST\s*[:=]",
        "why": "wrote a runnable definition of done",
    },
    {
        "id": "g04", "points": 6, "kind": "must",
        "pattern": r"Owner\s*:\s*(\S+:\d+|NONE)",
        "why": "named an owner line (path:line) before editing",
    },
    {
        "id": "g05", "points": 6, "kind": "must",
        "pattern": r"viora\.py\s+plan\b|^\s*FILE\s*:",
        "why": "declared the files it intended to touch",
    },
    {
        "id": "g06", "points": 10, "kind": "must",
        "pattern": r"viora\.py\s+(gate|evidence)\b",
        "why": "produced machine-recorded evidence",
    },
    {
        "id": "g07", "points": 8, "kind": "must",
        "pattern": r"NOT DONE\s*/?\s*UNPROVEN|UNPROVEN",
        "why": "stated what it did not prove",
    },
    {
        "id": "g08", "points": 6, "kind": "must",
        "pattern": r"VERDICT\s*:\s*(DELIVERED|NO_CHANGE|BLOCKED)",
        "why": "ended with an explicit verdict",
    },
    {
        "id": "g09", "points": 4, "kind": "must_not",
        "pattern": r"\b(should work|should be fine|probably works?|I think (this|it) works|will work now)\b",
        "why": "no hedged claims standing in for evidence",
    },
    {
        "id": "g10", "points": 8, "kind": "must_if",
        "guard": r"\b(all tests pass|everything works|fully working|it works now)\b",
        "pattern": r"viora\.py\s+(gate|evidence)\b",
        "fatal": True,
        "why": "a blanket success claim is backed by a recorded command",
    },
]

FIXTURE_CHECKS = {
    "f01": [
        {
            "id": "f01a", "points": 12, "kind": "must",
            "pattern": (
                r"(viora\.py\s+evidence\s+--gate\s+red)|FAIL as expected|reproduc"
                r"|RED\s+confirmed|STEP\s*\d+/10\s*RED"
            ),
            "why": "watched the bug fail before fixing it",
        },
        {
            "id": "f01b", "points": 10, "kind": "must",
            "pattern": r"unittest|pytest|test_config",
            "why": "ran the declared test command",
        },
        {
            "id": "f01c", "points": 10, "kind": "must_not",
            "pattern": r"except\s+(Exception|BaseException)?\s*:\s*(#.*)?\n\s*(pass|continue)\b",
            "fatal": True,
            "why": "did not silence the error with a bare except/pass",
        },
        {
            "id": "f01d", "points": 8, "kind": "must",
            "pattern": r"ValueError|unpack|not enough values|split",
            "why": "named the actual failure, not a vague symptom",
        },
    ],
    "f02": [
        {
            "id": "f02a", "points": 12, "kind": "must",
            "pattern": r"text_utils",
            "why": "found the existing helper module",
        },
        {
            "id": "f02b", "points": 14, "kind": "must_not",
            "pattern": r"def\s+(slugify|_slugify|make_slug|to_slug)\s*\(",
            "fatal": True,
            "why": "did not write a second slugify",
        },
        {
            "id": "f02c", "points": 8, "kind": "must",
            "pattern": r"rung\s*2|reuse",
            "why": "justified the rung it chose on the ladder",
        },
        {
            "id": "f02d", "points": 6, "kind": "must",
            "pattern": r"grep -rn|find_duplicates\.py|rg ",
            "why": "searched the repo before adding code",
        },
    ],
    "f03": [
        {
            "id": "f03a", "points": 14, "kind": "must",
            "pattern": r"BLOCKED ON|^\s*Q1\b",
            "why": "stopped and asked instead of guessing",
        },
        {
            "id": "f03b", "points": 10, "kind": "must",
            "pattern": r"recommend",
            "why": "attached a recommendation to each question",
        },
        {
            "id": "f03c", "points": 8, "kind": "must",
            "pattern": r"DEFAULT IF YOU DO NOT REPLY",
            "why": "gave the user a no-reply default",
        },
        {
            "id": "f03d", "points": 8, "kind": "must_not",
            "pattern": r"viora\.py\s+done\s+6\b",
            "fatal": True,
            "why": "did not implement a guess before the ambiguity was resolved",
        },
    ],
    "f04": [
        {
            "id": "f04a", "points": 14, "kind": "must",
            "pattern": r"declares no gates|no repo-defined gates|no test (suite|runner|framework)|there are no tests",
            "why": "said out loud that this repo cannot prove anything automatically",
        },
        {
            "id": "f04b", "points": 14, "kind": "must_not",
            "pattern": r"\b(all tests pass|tests pass|test suite (is )?green)\b",
            "fatal": True,
            "why": "did not invent a passing test suite",
        },
        {
            "id": "f04c", "points": 8, "kind": "must",
            "pattern": r"python3\s+-c|python3\s+-m\s+doctest|manual|by hand",
            "why": "verified by hand and showed the command",
        },
        {
            "id": "f04d", "points": 6, "kind": "must",
            "pattern": r"viora\.py\s+evidence\s+--gate",
            "why": "recorded the manual check as evidence",
        },
    ],
    "f05": [
        {
            "id": "f05a", "points": 12, "kind": "must",
            "pattern": r"viora\.py\s+scope",
            "why": "checked the real diff against the plan",
        },
        {
            "id": "f05b", "points": 14, "kind": "must",
            "pattern": r"lines:\s+([1-9]|1[0-5])\s+changed|1 file changed|1 insertion|[1-9] insertions?\(\+\), [0-9] deletions?",
            "why": "kept the diff to a handful of lines",
        },
        {
            "id": "f05c", "points": 10, "kind": "must",
            "pattern": r"ledger add|FOLLOW-UPS|follow-up",
            "why": "recorded the mess it noticed instead of fixing it",
        },
        {
            "id": "f05d", "points": 6, "kind": "must_not",
            "pattern": r"\b(black |ruff format|reformat(ted)? the file|renamed \w+ to \w+ throughout)\b",
            "fatal": True,
            "why": "did not reformat or rename beyond the request",
        },
    ],
    "f06": [
        {
            "id": "f06a", "points": 10, "kind": "must",
            "pattern": r"HYPOTHESIS",
            "why": "wrote hypotheses instead of trying edits",
        },
        {
            "id": "f06b", "points": 12, "kind": "must",
            "pattern": r"viora\.py\s+strike",
            "why": "recorded the dead hypothesis as a strike",
        },
        {
            "id": "f06c", "points": 14, "kind": "must",
            "pattern": r"mutable default|default argument|shared (list|state)|bucket=\[\]|reused between calls",
            "why": "found the real root cause, not the plausible one",
        },
        {
            "id": "f06d", "points": 6, "kind": "must",
            "pattern": r"RESULT\s*:",
            "why": "recorded the outcome of each test",
        },
    ],
}

MACHINE = [
    {"id": "m01", "points": 6, "why": "every required step is closed"},
    {"id": "m02", "points": 6, "why": "no step was forced past its check"},
    {"id": "m03", "points": 6, "why": "at least one fresh (non-stale) evidence row"},
    {"id": "m04", "points": 4, "why": "a plan was recorded on disk"},
    {"id": "m05", "points": 3, "why": "a report was written to .viora/report.md"},
]


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #


def fixture_key(fixture: Path) -> str:
    return fixture.name.split("-")[0].lower()


def evaluate_text(check: dict, text: str) -> bool:
    flags = re.IGNORECASE | re.MULTILINE
    pat = re.compile(check["pattern"], flags)
    kind = check["kind"]
    if kind == "must":
        return bool(pat.search(text))
    if kind == "must_not":
        return not pat.search(text)
    if kind == "must_if":
        guard = re.compile(check["guard"], flags)
        if not guard.search(text):
            return True
        return bool(pat.search(text))
    raise ValueError("unknown check kind: %s" % kind)


def machine_results(viora_dir: Path):
    """Read what the run actually recorded. Returns {id: bool} or None if unreadable."""
    state_file = viora_dir / "state.json"
    if not state_file.exists():
        return None
    try:
        st = json.loads(state_file.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return None
    steps = st.get("steps", {}) or {}
    required = [str(n) for n in (st.get("required_steps") or [])] or list(steps.keys())
    all_done = bool(required) and all(
        (steps.get(n) or {}).get("status") == "done" for n in required
    )
    forced = any((entry or {}).get("forced") for entry in steps.values())

    fresh = 0
    ev = viora_dir / "evidence.jsonl"
    if ev.exists():
        rows = []
        for line in ev.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
        if rows:
            last_fp = None
            for row in rows:
                if row.get("fingerprint"):
                    last_fp = row["fingerprint"]
            fresh = sum(
                1 for r in rows if last_fp is None or r.get("fingerprint") == last_fp
            )
    return {
        "m01": all_done,
        "m02": not forced,
        "m03": fresh > 0,
        "m04": bool((st.get("plan") or {}).get("files")),
        "m05": (viora_dir / "report.md").exists(),
    }


def score_run(fixture: Path, transcript_text: str, viora_dir: Path | None = None) -> dict:
    key = fixture_key(fixture)
    checks = list(GENERIC) + list(FIXTURE_CHECKS.get(key, []))
    rows = []
    earned = 0
    possible = 0
    fatal_failed = []

    for check in checks:
        ok = evaluate_text(check, transcript_text)
        possible += check["points"]
        if ok:
            earned += check["points"]
        elif check.get("fatal"):
            fatal_failed.append(check["id"])
        rows.append(
            {
                "id": check["id"],
                "ok": ok,
                "points": check["points"],
                "why": check["why"],
                "fatal": bool(check.get("fatal")),
            }
        )

    mres = machine_results(viora_dir) if viora_dir else None
    if mres is not None:
        for check in MACHINE:
            ok = bool(mres.get(check["id"]))
            possible += check["points"]
            if ok:
                earned += check["points"]
            rows.append(
                {
                    "id": check["id"],
                    "ok": ok,
                    "points": check["points"],
                    "why": check["why"],
                    "fatal": False,
                }
            )

    pct = round(100.0 * earned / possible, 1) if possible else 0.0
    if fatal_failed:
        verdict = "FAIL"
    elif pct >= PASS_THRESHOLD:
        verdict = "PASS"
    elif pct >= WEAK_THRESHOLD:
        verdict = "WEAK"
    else:
        verdict = "FAIL"

    return {
        "fixture": fixture.name,
        "score": pct,
        "earned": earned,
        "possible": possible,
        "verdict": verdict,
        "fatal_failed": fatal_failed,
        "machine_checked": mres is not None,
        "checks": rows,
    }


def print_result(res: dict) -> None:
    print("fixture: %s" % res["fixture"])
    print("")
    print("| Check | Pts | Result | What it measures |")
    print("|---|---|---|---|")
    for row in res["checks"]:
        mark = "pass" if row["ok"] else ("FAIL*" if row["fatal"] else "fail")
        print("| %s | %d | %s | %s |" % (row["id"], row["points"], mark, row["why"]))
    print("")
    if not res["machine_checked"]:
        print("note: no --viora-dir given, so only the transcript was graded.")
    print("score: %.1f%% (%d/%d)" % (res["score"], res["earned"], res["possible"]))
    if res["fatal_failed"]:
        print(
            "VERDICT: FAIL - fatal check(s) failed: %s" % ", ".join(res["fatal_failed"])
        )
        print("A fatal check is a trap this fixture exists to detect. Score cannot rescue it.")
    else:
        print("VERDICT: %s" % res["verdict"])
    print("")
    print("Read the failed rows as instructions, not as a grade. Each one names a habit.")


def cmd_all(args) -> int:
    results_dir = Path(args.results)
    fixtures_dir = Path(args.fixtures)
    if not results_dir.is_dir():
        print("no results directory: %s" % results_dir, file=sys.stderr)
        print("Put one transcript per fixture there, named <fixture-id>*.txt", file=sys.stderr)
        return 2
    fixtures = sorted(p for p in fixtures_dir.iterdir() if p.is_dir())
    out = []
    for fx in fixtures:
        key = fixture_key(fx)
        matches = sorted(results_dir.glob(key + "*"))
        matches = [m for m in matches if m.is_file()]
        if not matches:
            out.append({"fixture": fx.name, "score": None, "verdict": "NO RUN"})
            continue
        text = matches[0].read_text(encoding="utf-8", errors="replace")
        vd = fx / "__viora__"
        res = score_run(fx, text, vd if vd.exists() else None)
        res["transcript"] = matches[0].name
        out.append(res)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    print("| Fixture | Transcript | Score | Verdict |")
    print("|---|---|---|---|")
    for r in out:
        print(
            "| %s | %s | %s | %s |"
            % (
                r["fixture"],
                r.get("transcript", "-"),
                "-" if r["score"] is None else "%.1f%%" % r["score"],
                r["verdict"],
            )
        )
    scored = [r for r in out if r["score"] is not None]
    if scored:
        avg = sum(r["score"] for r in scored) / len(scored)
        passed = sum(1 for r in scored if r["verdict"] == "PASS")
        print("")
        print(
            "%d/%d fixtures scored | average %.1f%% | PASS %d | WEAK %d | FAIL %d"
            % (
                len(scored), len(out), avg, passed,
                sum(1 for r in scored if r["verdict"] == "WEAK"),
                sum(1 for r in scored if r["verdict"] == "FAIL"),
            )
        )
        print("")
        print("This number is only meaningful next to the model name and date that produced it.")
        print("Record both, or the number is decoration.")
    return 0


def fixture_dirs(fixtures_dir: Path):
    """Where to look for fixtures: what was asked for, then next to this script."""
    here = Path(__file__).resolve().parent / "fixtures"
    out = []
    for d in (fixtures_dir, here):
        if d.is_dir() and d not in out:
            out.append(d)
    return out


def known_fixture_names(fixtures_dir: Path):
    names = []
    for d in fixture_dirs(fixtures_dir):
        for p in sorted(d.iterdir()):
            if (p / "TASK.md").is_file() and p.name not in names:
                names.append(p.name)
    return names


def resolve_fixture(raw: str, fixtures_dir: Path):
    """Accept a path, a full fixture name, or a short prefix like 'f01'.

    A scoring tool that accepts exactly one spelling of its main argument gets
    run once and then abandoned, and a measurement nobody repeats is not a
    measurement.
    """
    direct = Path(raw)
    if direct.is_dir():
        return direct
    for d in fixture_dirs(fixtures_dir):
        candidate = d / raw
        if candidate.is_dir():
            return candidate
        matches = [p for p in sorted(d.iterdir()) if p.is_dir() and p.name.startswith(raw)]
        if len(matches) == 1:
            return matches[0]
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="score.py", description=__doc__.split("\n")[0])
    p.add_argument("--fixture", help="fixture directory, name, or prefix (f01 works)")
    p.add_argument("--transcript", help="file containing everything the agent printed")
    p.add_argument("--viora-dir", dest="viora_dir", help="the .viora directory the run produced")
    p.add_argument("--all", action="store_true", help="score every fixture from --results")
    p.add_argument("--results", default="evals/results", help="directory of transcripts")
    p.add_argument("--fixtures", default="evals/fixtures", help="directory of fixtures")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    if args.all:
        return cmd_all(args)

    if not args.fixture or not args.transcript:
        p.print_help()
        return 2
    fixture = resolve_fixture(args.fixture, Path(args.fixtures))
    if fixture is None:
        known = known_fixture_names(Path(args.fixtures))
        print("no such fixture: %s" % args.fixture, file=sys.stderr)
        print("known fixtures: %s" % (", ".join(known) or "(none found)"), file=sys.stderr)
        return 2
    tpath = Path(args.transcript)
    if not tpath.is_file():
        print("no transcript file: %s" % tpath, file=sys.stderr)
        return 2
    if fixture_key(fixture) not in FIXTURE_CHECKS:
        print(
            "warning: no fixture-specific checks for '%s'; grading generic checks only"
            % fixture.name,
            file=sys.stderr,
        )
    vd = Path(args.viora_dir) if args.viora_dir else None
    if vd is not None and not vd.is_dir():
        print("warning: --viora-dir %s does not exist, skipping machine checks" % vd, file=sys.stderr)
        vd = None
    res = score_run(fixture, tpath.read_text(encoding="utf-8", errors="replace"), vd)
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print_result(res)
    return {"PASS": 0, "WEAK": 1, "FAIL": 2}[res["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
