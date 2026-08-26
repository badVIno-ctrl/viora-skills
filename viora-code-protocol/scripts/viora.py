#!/usr/bin/env python3
"""viora.py - the VioraCode conductor.

Why this exists: a strong model can hold a ten-step protocol in its head. A fast or
small model cannot, and it does not fail by refusing - it fails by drifting, then
reporting success. This script moves the protocol out of the model's memory and onto
disk, so the step, the plan, the evidence, the attempt count and the findings survive
context loss, and so a report cannot claim a gate that was never run.

Three things here are not advice, they are mechanism:

  1. Evidence is bound to a fingerprint of the working tree. Edit code after running a
     gate and that evidence row turns STALE - the report says so, out loud.
  2. The plan is machine-readable. `scope` compares the real diff against it and fails
     on files you never declared or a line budget you blew through.
  3. `checkpoint` / `rollback` give a weak model one-command undo, so a mess does not
     become five turns of dig-deeper.

Typical loop (run it every turn at T0):

    python3 scripts/viora.py doctor
    python3 scripts/viora.py start --mode FIX --tier T1 --task "login 500s on empty body"
    python3 scripts/viora.py next
    python3 scripts/viora.py done 1 --note "contract written"
    python3 scripts/viora.py plan --files src/api/login.ts --lines 80
    python3 scripts/viora.py checkpoint --label "before GREEN"
    python3 scripts/viora.py scope
    python3 scripts/viora.py gate
    python3 scripts/viora.py check
    python3 scripts/viora.py report

Everything lives in ./.viora/ (state.json, contract.md, ledger.md, evidence.jsonl,
runs.jsonl, checkpoints/). No network. No writes outside .viora/ except rollback,
which restores files you asked it to restore. Stdlib only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

VERSION = "2.1"

TIERS = ("T0", "T1", "T2")
MODES = ("TRIVIAL", "FIX", "FEATURE", "REFACTOR", "UI", "PERF", "REVIEW", "DEBUG")

# Which of the ten steps each mode must complete.
MODE_STEPS = {
    "TRIVIAL": [1, 6, 8, 10],
    "FIX": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "FEATURE": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "REFACTOR": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "UI": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "PERF": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "REVIEW": [1, 2, 9, 10],
    "DEBUG": [1, 2, 5, 6, 8, 10],
}

LINE_BUDGET = {"T0": 80, "T1": 300, "T2": 300}
FILE_BUDGET = {"T0": 1, "T1": 3, "T2": 8}
DOUBT_ROUNDS = {"T0": 2, "T1": 3, "T2": 5}
MAX_STRIKES = {"T0": 2, "T1": 3, "T2": 3}
SEVERITIES = ("Critical", "Required", "Optional", "Nit", "FYI")
BLOCKING = ("Critical", "Required")

# Directories that never count as source when fingerprinting a non-git tree.
IGNORED_DIRS = {
    ".git", ".viora", "node_modules", "__pycache__", ".venv", "venv", "dist",
    "build", ".next", ".nuxt", "target", ".gradle", ".idea", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "coverage", ".turbo", "vendor", "Pods",
}

STEPS = [
    {
        "n": 1,
        "key": "CONTRACT",
        "produces": "four lines - GOAL / DONE-TEST / PROTECTED / NON-GOALS",
        "ref": "references/09-clarify-and-grill.md",
        "T0": [
            "Fill this template exactly, changing nothing but the angle brackets:",
            "  GOAL:      <one sentence: what the user can do afterwards>",
            "  DONE-TEST: <the exact command or click that proves it>",
            "  PROTECTED: <what must keep working>",
            "  NON-GOALS: <what you are not touching>",
            "A DONE-TEST containing an adjective ('works properly') is not finished. Use a command.",
            "Anything genuinely unclear: ask at most 3 questions, each with your recommended answer, then wait.",
        ],
        "T1": [
            "Write the four contract lines. DONE-TEST must be a command, a request, or a click.",
            "Restate the request in your own words and compare: any drift is a question, not an assumption.",
            "Unclear? Ask one batched round of up to 5 questions, each with a recommendation.",
        ],
        "T2": [
            "Write the four contract lines.",
            "Compute the decision frontier and GRILL in rounds until nothing is silently assumed.",
            "Read facts from the repo yourself; ask only what needs the user's preference or authority.",
        ],
        "commands": [
            "python3 scripts/viora.py contract --goal '...' --done-test '...' --protected '...' --non-goals '...'"
        ],
        "done_when": "the four lines exist and DONE-TEST is runnable",
        "note_hint": "contract written; DONE-TEST=<command>",
        "requires_note": True,
    },
    {
        "n": 2,
        "key": "OWNER",
        "produces": "'Owner: path:line' for the behaviour, or 'Owner: NONE'",
        "ref": "references/01-recon-and-reuse.md",
        "T0": [
            "Run the two commands below and paste their real output.",
            "Copy ONE line out of that output as your owner line: 'Owner: path/file.ext:123'.",
            "Found nothing? Write 'Owner: NONE' - and that is a real answer, not a failure.",
            "An owner exists => you extend it. Writing a second implementation is the defect this step prevents.",
        ],
        "T1": [
            "Search 3 name variants + 2 behaviour keywords for the concept.",
            "Read the top hit before deciding. Write 'Owner: path:line' or 'Owner: NONE'.",
            "Also note any near-duplicate that would collide with your change.",
        ],
        "T2": [
            "Map ownership: who owns the behaviour, who owns the data, who owns the surface.",
            "Check for existing constants, helpers, styles and routes that already encode this concept.",
            "Write the ownership map, then the single 'Owner:' line you will extend.",
        ],
        "commands": [
            "python3 scripts/scan_repo.py .",
            "python3 scripts/find_duplicates.py . --top 15",
            "grep -rn '<main-word>' . --include='*.*' -l | head -20",
        ],
        "done_when": "an 'Owner:' line exists, backed by pasted search output",
        "note_hint": "Owner: src/auth/login.ts:140",
        "requires_note": True,
    },
    {
        "n": 3,
        "key": "LADDER",
        "produces": "the rung you chose + why the cheaper rung fails",
        "ref": "references/01-recon-and-reuse.md",
        "T0": [
            "Pick the LOWEST line that solves the task and say why the line above it does not:",
            "  0 NO CHANGE          - it already works, or it was not asked for",
            "  1 DELETE / CONFIGURE - a flag, a constant, removing code",
            "  2 REUSE local        - extend what this repo already has",
            "  3 PLATFORM / STDLIB  - the language or framework already does this",
            "  4 INSTALLED DEP      - something in the lockfile already does this",
            "  5 NEW DEP            - needs the user's explicit yes",
            "  6 NEW CODE           - last resort, smallest possible version",
        ],
        "T1": ["Choose the rung and write one line: 'Rung N because rung N-1 fails: <reason>'."],
        "T2": ["Choose the rung, and list the rungs you rejected with the reason each was rejected."],
        "commands": [],
        "done_when": "one line naming the rung and why the cheaper rung fails",
        "note_hint": "rung 2 - extending existing validateBody(); rung 1 fails: no flag exists",
        "requires_note": True,
    },
    {
        "n": 4,
        "key": "PLAN",
        "produces": "a recorded, machine-checked file list + line budget + frozen interfaces",
        "ref": "references/02-design-and-limits.md",
        "T0": [
            "Your plan is exactly ONE file. Record it so the machine can hold you to it:",
            "  python3 scripts/viora.py plan --files <one path> --lines 80 --frozen '<public names>'",
            "Need a second file, a dependency, a schema or an API change? Stop this turn and ask.",
            "From now on, `scope` FAILS if you touch a file that is not in that list. That is the point.",
        ],
        "T1": [
            "Record every file you will touch (<= 3) with `plan --files a,b,c --lines 300`.",
            "Say in one line each what changes in each file, and name the interfaces you are freezing.",
            "Files outside this list are a scope violation later, so list them now or not at all.",
        ],
        "T2": [
            "Record the plan, then write the frozen public surface, the data flow, and the rollback path.",
            "Over ~300 changed lines: split it now - stack it, split by file group, build the shared layer first, or slice vertically.",
        ],
        "commands": [
            "python3 scripts/viora.py plan --files src/api/login.ts --lines 80 --frozen 'LoginResponse'"
        ],
        "done_when": "the plan is recorded on disk before any edit, and `scope` is clean",
        "note_hint": "FILE: src/api/login.ts (<=80 lines); FROZEN: LoginResponse",
        "requires_note": True,
    },
    {
        "n": 5,
        "key": "RED",
        "produces": "a check that fails NOW, for the right reason",
        "ref": "references/05-tests-and-evidence.md",
        "T0": [
            "Write ONE check for the behaviour, then run it and watch it FAIL.",
            "Paste the failure. It must fail because the behaviour is missing, not because of a typo or import error.",
            "No test runner in this repo? RED is any command whose output is wrong today - paste that wrong output.",
        ],
        "T1": [
            "Write 1-2 tests at the public boundary, run them, watch them fail for the right reason.",
            "FIX mode: the test reproduces the reported bug exactly.",
            "REFACTOR mode: RED is the existing suite green before you touch anything - record that baseline.",
            "PERF mode: RED is a measurement, with the number written down.",
        ],
        "T2": [
            "Name the seam you are testing at and confirm it is a public boundary.",
            "One vertical slice at a time: one test, one implementation, repeat. Avoid writing the whole suite upfront.",
            "Check the test for the three anti-patterns: implementation-coupled, tautological, horizontally sliced.",
        ],
        "commands": [
            "# the repo's own focused test command - take it from scan_repo.py output",
            "python3 scripts/viora.py evidence --gate red --command '<test cmd>' --result 'FAIL as expected: <msg>'",
        ],
        "done_when": "you have pasted a real failure caused by the missing behaviour",
        "note_hint": "RED: test/login.test.ts:22 fails - expected 400, got 500",
        "requires_note": True,
    },
    {
        "n": 6,
        "key": "GREEN",
        "produces": "the smallest edit inside the owner that turns RED green",
        "ref": "references/02-design-and-limits.md",
        "T0": [
            "First, one command so a mess is undoable: python3 scripts/viora.py checkpoint --label 'before GREEN'",
            "Then edit ONE file. Make the smallest change that passes the check.",
            "Add nothing you were not asked for: no extra options, no flags, no 'while I am here'.",
            "Run the same command again until it passes, then paste the passing output.",
            "Made it worse? python3 scripts/viora.py rollback --yes  - then try a different hypothesis.",
        ],
        "T1": [
            "Checkpoint first, then implement inside the owner from step 2, staying inside the recorded plan.",
            "Keep to the hard limits: file <= 400, function <= 50, nesting <= 3, params <= 4, 0 magic literals.",
            "Run the focused check after each meaningful edit, not once at the end.",
        ],
        "T2": [
            "Implement minimally, then extend only as later tests demand it.",
            "Every changed line must trace to the contract. Anything else belongs in FOLLOW-UPS.",
        ],
        "commands": [
            "python3 scripts/viora.py checkpoint --label 'before GREEN'",
            "python3 scripts/viora.py scope",
        ],
        "done_when": "the RED check passes, output pasted, and `scope` reports no file outside the plan",
        "note_hint": "GREEN: login.ts:88 guard added; test/login.test.ts:22 passes",
        "requires_note": True,
    },
    {
        "n": 7,
        "key": "CLEAN",
        "produces": "identical behaviour, fewer concepts, no residue",
        "ref": "references/02-design-and-limits.md",
        "T0": [
            "Check your diff against these numbers and fix what fails:",
            "  file <= 400 lines | function <= 50 | nesting <= 3 | params <= 4",
            "  0 magic numbers/strings | 0 nested ternaries | 0 debug prints",
            "  0 commented-out code | 0 unused imports | 0 files outside the plan",
            "Change behaviour here and you have left step 7 - the tests must still pass unmodified.",
        ],
        "T1": [
            "One simplification at a time, running the tests after each.",
            "Preserve behaviour exactly: same output, same errors, same side effects, same ordering.",
            "Match this repo's conventions rather than your own preferences.",
            "Then sweep residue: debug output, dead branches, unused imports, stale comments and docs.",
        ],
        "T2": [
            "Simplify, then verify the concept count actually dropped - relocated complexity is not reduced complexity.",
            "List any dead code the change created and ask before deleting anything you are unsure about.",
        ],
        "commands": [
            "python3 scripts/viora.py scope",
            "git --no-pager diff --stat",
            "python3 scripts/ui_guard.py . --strict   # UI mode only",
        ],
        "done_when": "limits pass, residue gone, tests still green without being edited",
        "note_hint": "CLEAN: 1 file, 34 lines, no residue; limits pass",
        "requires_note": True,
    },
    {
        "n": 8,
        "key": "PROVE",
        "produces": "fresh gate output, bound to this exact diff",
        "ref": "references/05-tests-and-evidence.md",
        "T0": [
            "Run the gate command below and paste the whole table.",
            "Every SKIP is unproven - write it down as unproven, do not round it up to a pass.",
            "Evidence is stamped with a fingerprint of your working tree. Touch any file after this and",
            "the row goes STALE and the report will say so. If you edit again, run the gates again.",
        ],
        "T1": [
            "Run the full gates. Fix anything red before continuing.",
            "Then verify the DONE-TEST from your contract, by hand, and paste that output too.",
            "Finish with `check`: it is the thing that tells you whether you are allowed to say 'done'.",
        ],
        "T2": [
            "Full gates, plus a runtime check of the real path a user takes.",
            "Regression test: revert the fix, watch the test fail, restore it, watch it pass. Record both.",
        ],
        "commands": [
            "python3 scripts/viora.py gate",
            "python3 scripts/viora.py check",
        ],
        "done_when": "a fresh, non-stale evidence row exists for every gate you claim",
        "note_hint": "gates recorded via viora.py gate",
        "requires_note": False,
    },
    {
        "n": 9,
        "key": "DOUBT",
        "produces": "findings from a hostile re-read of your own diff",
        "ref": "references/11-doubt-and-second-opinion.md",
        "T0": [
            "Answer all five, one short line each:",
            "  1 Which command output proves this works? (quote it)",
            "  2 What did I change that nobody asked for?",
            "  3 What happens on empty / null / huge / wrong-typed input?",
            "  4 Is there now a second place doing this same thing?",
            "  5 What am I about to call done that I never ran?",
            "Any uncomfortable answer sends you back to the step that owns it.",
        ],
        "T1": [
            "Read the diff as a document, as if a stranger wrote it: git --no-pager diff",
            "Eight lenses: correctness, evidence, ownership, scope, simplicity, structure, blast radius, residue.",
            "Write findings into the ledger before fixing any of them.",
        ],
        "T2": [
            "Send ARTIFACT + CONTRACT to a clean context (sub-agent or a written-out diff). Never send your claim or your reasoning.",
            "Ask 'find what fails under this contract', never 'is this good'.",
            "Offer a cross-model second opinion; confirm the exact command before running any external CLI.",
            "Classify each finding: contract gap / actionable / trade-off / noise. Stop after 3 cycles.",
        ],
        "commands": [
            "git --no-pager diff",
            "python3 scripts/viora.py ledger add --severity Critical --where f.ts:12 --text '...'",
            "python3 scripts/viora.py ledger list --open",
        ],
        "done_when": "every finding has a verdict, and blocking findings are fixed and re-proven",
        "note_hint": "doubt pass done: 2 findings, both FIXED",
        "requires_note": True,
    },
    {
        "n": 10,
        "key": "REPORT",
        "produces": "the fixed report contract",
        "ref": "references/06-review-and-report.md",
        "T0": [
            "Generate the report from what was recorded, then paste it:",
            "  python3 scripts/viora.py report",
            "NOT DONE / UNPROVEN is never empty on a real task. Empty means you did not look.",
            "Do not edit the generated UNPROVEN list into something shorter. That is fabrication.",
        ],
        "T1": ["Generate the report, then add HOW IT WAS SOLVED and FOLLOW-UPS in your own words."],
        "T2": ["Generate the report; add the trade-offs you accepted and the follow-ups you are deliberately deferring."],
        "commands": ["python3 scripts/viora.py report"],
        "done_when": "the report is emitted with a fresh evidence table and a non-empty unproven list",
        "note_hint": "report emitted",
        "requires_note": False,
    },
]

STEP_BY_N = {s["n"]: s for s in STEPS}


# --------------------------------------------------------------------------- #
# paths and state
# --------------------------------------------------------------------------- #


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def vdir(root: str) -> Path:
    return Path(root) / ".viora"


def state_path(root: str) -> Path:
    return vdir(root) / "state.json"


def evidence_path(root: str) -> Path:
    return vdir(root) / "evidence.jsonl"


def runs_path(root: str) -> Path:
    return vdir(root) / "runs.jsonl"


def tier_path(root: str) -> Path:
    return vdir(root) / "tier"


def checkpoints_dir(root: str) -> Path:
    return vdir(root) / "checkpoints"


def die(msg: str, code: int = 2):
    sys.stderr.write("viora: " + msg + "\n")
    raise SystemExit(code)


def load_state(root: str, required: bool = True):
    p = state_path(root)
    if not p.exists():
        if required:
            die(
                "no run in progress. Start one:\n"
                "  python3 scripts/viora.py start --mode FIX --task \"<the task>\""
            )
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        die("cannot read %s (%s). Delete it and start again." % (p, exc))


def save_state(root: str, st: dict) -> None:
    d = vdir(root)
    d.mkdir(parents=True, exist_ok=True)
    st["updated"] = now()
    st["version"] = VERSION
    state_path(root).write_text(
        json.dumps(st, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def read_tier_file(root: str):
    p = tier_path(root)
    if p.exists():
        val = p.read_text(encoding="utf-8").strip().upper()
        if val in TIERS:
            return val
    return None


def resolve_tier(root: str, explicit=None) -> str:
    """Pinned file first, then the caller's flag, then the fail-safe default."""
    pinned = read_tier_file(root)
    if pinned:
        return pinned
    if explicit:
        return explicit
    return "T1"


def required_steps(st: dict):
    return MODE_STEPS.get(st.get("mode", "FIX"), MODE_STEPS["FIX"])


def step_status(st: dict, n: int) -> str:
    return st.get("steps", {}).get(str(n), {}).get("status", "pending")


def current_step(st: dict):
    for n in required_steps(st):
        if step_status(st, n) != "done":
            return n
    return None


def header(st: dict) -> str:
    cur = current_step(st)
    steps = required_steps(st)
    if cur:
        pos = "%d/%d" % (steps.index(cur) + 1, len(steps))
        name = STEP_BY_N[cur]["key"]
    else:
        pos = "%d/%d" % (len(steps), len(steps))
        name = "REPORTED"
    return "VIORA %s | MODE %s | STEP %s %s" % (st["tier"], st["mode"], pos, name)


# --------------------------------------------------------------------------- #
# git + fingerprint: this is what makes evidence honest
# --------------------------------------------------------------------------- #


def run_git(root: str, args, timeout: int = 30):
    """Return stdout, or None if git is unavailable or the command failed."""
    try:
        p = subprocess.run(
            ["git"] + list(args), cwd=root, capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    return p.stdout


def has_git(root: str) -> bool:
    return run_git(root, ["rev-parse", "--is-inside-work-tree"]) is not None


def iter_source_files(root: str, cap: int = 4000):
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
        for name in sorted(filenames):
            if name.startswith(".") or name.endswith((".pyc", ".lock", ".log")):
                continue
            seen += 1
            if seen > cap:
                return
            yield Path(dirpath) / name


def fingerprint(root: str) -> str:
    """A short digest of the current working tree.

    With git: HEAD + the full uncommitted diff + the content of untracked files.
    Without git: path, size and mtime of every source file.
    Either way, any hand edit to the code changes this string - which is exactly
    how a stale gate result gets caught. Generated files are excluded on purpose:
    `gate` writes .pyc files itself, and if those counted, running the gates would
    mark the very rows it had just written as STALE.
    """
    h = hashlib.sha256()
    if has_git(root):
        h.update((run_git(root, ["rev-parse", "HEAD"]) or "no-head").encode("utf-8"))
        h.update((run_git(root, ["diff", "HEAD"]) or "").encode("utf-8"))
        untracked = (run_git(root, ["ls-files", "--others", "--exclude-standard"]) or "").split("\n")
        for rel in sorted(x for x in untracked if x.strip()):
            if path_ignored(rel):
                continue
            h.update(rel.encode("utf-8"))
            try:
                h.update((Path(root) / rel).read_bytes())
            except OSError:
                pass
        return "git:" + h.hexdigest()[:12]
    for path in iter_source_files(root):
        try:
            stat = path.stat()
        except OSError:
            continue
        h.update(str(path).encode("utf-8"))
        h.update(("%d:%d" % (stat.st_size, int(stat.st_mtime))).encode("utf-8"))
    return "fs:" + h.hexdigest()[:12]


def path_ignored(rel: str) -> bool:
    """True for generated junk, caches and our own state directory.

    Without this, a single `python3 -m compileall` writes a dozen .pyc files into
    __pycache__ and every one of them looks like a file you touched but never
    declared. A scope guard that cries wolf is a scope guard that gets ignored,
    so it has to stay quiet about files nobody wrote by hand.
    """
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    if not parts:
        return True
    if parts[0] == ".viora":
        return True
    for part in parts:
        if part in IGNORED_DIRS:
            return True
    return parts[-1].endswith(
        (".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".log", ".orig", ".rej")
    )


def changed_files(root: str, base=None):
    """Files touched relative to base (default HEAD), or None if git is unavailable."""
    if not has_git(root):
        return None
    ref = base or "HEAD"
    tracked = run_git(root, ["diff", "--name-only", ref])
    if tracked is None:
        return None
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"]) or ""
    out = []
    for line in (tracked + "\n" + untracked).split("\n"):
        line = line.strip()
        if line and not path_ignored(line):
            out.append(line)
    return sorted(set(out))


def changed_line_count(root: str, base=None):
    """Added + deleted lines relative to base, or None if git is unavailable."""
    if not has_git(root):
        return None
    ref = base or "HEAD"
    out = run_git(root, ["diff", "--numstat", ref])
    if out is None:
        return None
    total = 0
    for line in out.split("\n"):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        if path_ignored(parts[2].strip()):
            continue
        for cell in parts[:2]:
            if cell.strip().isdigit():
                total += int(cell)
    for rel in (run_git(root, ["ls-files", "--others", "--exclude-standard"]) or "").split("\n"):
        rel = rel.strip()
        if not rel or path_ignored(rel):
            continue
        try:
            with (Path(root) / rel).open("rb") as fh:
                total += sum(1 for _ in fh)
        except OSError:
            pass
    return total


# --------------------------------------------------------------------------- #
# evidence
# --------------------------------------------------------------------------- #


def read_evidence(root: str, mark_stale: bool = True):
    p = evidence_path(root)
    rows = []
    if not p.exists():
        return rows
    current = fingerprint(root) if mark_stale else None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = {"gate": "unparsed", "command": line[:120], "result": "?"}
        if mark_stale:
            fp = row.get("fingerprint")
            row["stale"] = bool(fp) and fp != current
        rows.append(row)
    return rows


def fresh_evidence(rows):
    return [r for r in rows if not r.get("stale")]


# Gates whose whole job is to describe the tree BEFORE the fix. A `red` row is
# supposed to go stale the moment the bug is fixed: that staleness is evidence the
# fix changed something, not a debt to be repaid by rerunning it.
HISTORICAL_GATES = ("red", "repro", "reproduce", "baseline", "before")


def historical_gate(row) -> bool:
    return str(row.get("gate", "")).strip().lower() in HISTORICAL_GATES


def current_stale(rows):
    """Stale rows that actually threaten the claim - historical ones excluded."""
    return [r for r in rows if r.get("stale") and not historical_gate(r)]


def gate_names(rows) -> str:
    """Name the gates in a complaint. 'Some rows are stale' is not actionable."""
    return ", ".join(str(r.get("gate", "?")) for r in rows)


def latest_by_gate(rows):
    """The newest row for each gate name, in first-seen order.

    Rerunning a gate never erases the old row - the log is append-only, which is
    what makes it auditable. But a row that has been superseded by a fresh run of
    the same gate is history, not debt: reporting it as STALE would demand a rerun
    that already happened, and no amount of rerunning could ever clear it.
    Judge the run by the newest row per gate.
    """
    order = []
    latest = {}
    for row in rows:
        gate = row.get("gate", "?")
        if gate not in latest:
            order.append(gate)
        latest[gate] = row
    return [latest[g] for g in order]


def append_evidence(root: str, gate: str, command: str, result: str, st=None) -> dict:
    d = vdir(root)
    d.mkdir(parents=True, exist_ok=True)
    row = {
        "gate": gate,
        "command": command,
        "result": result,
        "at": now(),
        "fingerprint": fingerprint(root),
    }
    if st:
        row["tier"] = st.get("tier")
        cur = current_step(st)
        row["step"] = cur if cur else 10
    with evidence_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def open_findings(st: dict, blocking_only: bool = False):
    out = []
    for f in st.get("findings", []):
        if f.get("verdict", "OPEN") != "OPEN":
            continue
        if blocking_only and f.get("severity") not in BLOCKING:
            continue
        out.append(f)
    return out


def write_ledger(root: str, st: dict) -> None:
    lines = [
        "# Findings ledger",
        "",
        "Task: %s" % st.get("task", ""),
        "Mode: %s | Tier: %s | Updated: %s" % (st.get("mode"), st.get("tier"), now()),
        "",
        "| ID | Severity | Where | Finding | Verdict | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for f in st.get("findings", []):
        lines.append(
            "| %s | %s | %s | %s | %s | %s |"
            % (
                f["id"],
                f.get("severity", ""),
                f.get("where", ""),
                f.get("text", "").replace("|", "/"),
                f.get("verdict", "OPEN"),
                f.get("evidence", "-").replace("|", "/"),
            )
        )
    lines += [
        "",
        "A verdict is final. FIXED requires evidence. No pin, no FIXED.",
        "",
    ]
    vdir(root).mkdir(parents=True, exist_ok=True)
    (vdir(root) / "ledger.md").write_text("\n".join(lines), encoding="utf-8")


def plan_of(st: dict):
    return st.get("plan") or {}


def scope_report(root: str, st: dict, base=None):
    """Compare the real diff against the recorded plan and the tier budget."""
    tier = st["tier"]
    plan = plan_of(st)
    declared = [f.strip() for f in plan.get("files", []) if f.strip()]
    line_cap = int(plan.get("lines") or LINE_BUDGET[tier])
    tier_file_cap = FILE_BUDGET[tier]
    # The tier cap is enforced at plan time, where `plan` refuses and makes you
    # pass --force with a reason. After that the recorded plan IS the budget.
    # Re-applying the tier cap here would deadlock the run: every step from 6
    # onwards would refuse to close and no honest action could clear it.
    file_cap = max(tier_file_cap, len(declared)) if declared else tier_file_cap
    touched = changed_files(root, base)
    lines = changed_line_count(root, base)
    problems = []
    if touched is None:
        return {
            "git": False,
            "touched": None,
            "lines": None,
            "declared": declared,
            "problems": [],
            "unknown": True,
        }
    if declared:
        extra = [f for f in touched if f not in declared]
        for f in extra:
            problems.append("file outside the plan: %s" % f)
        untouched = [f for f in declared if f not in touched]
    else:
        extra, untouched = [], []
        if touched:
            problems.append(
                "no plan recorded, but %d file(s) already changed - record it: viora.py plan --files %s"
                % (len(touched), ",".join(touched[:3]))
            )
    if len(touched) > file_cap:
        if declared and file_cap > tier_file_cap:
            problems.append(
                "%d file(s) changed, the recorded plan covers %d"
                % (len(touched), file_cap)
            )
        else:
            problems.append(
                "%d file(s) changed, tier %s allows %d"
                % (len(touched), tier, file_cap)
            )
    if lines is not None and lines > line_cap:
        problems.append("%d changed lines, budget is %d" % (lines, line_cap))
    return {
        "git": True,
        "touched": touched,
        "lines": lines,
        "declared": declared,
        "extra": extra,
        "untouched": untouched,
        "line_cap": line_cap,
        "file_cap": file_cap,
        "tier_file_cap": tier_file_cap,
        "problems": problems,
        "unknown": False,
    }


# --------------------------------------------------------------------------- #
# commands: run lifecycle
# --------------------------------------------------------------------------- #


def cmd_tier(args) -> int:
    root = args.root
    if args.set:
        val = args.set.upper()
        if val not in TIERS:
            die("tier must be one of %s" % ", ".join(TIERS))
        vdir(root).mkdir(parents=True, exist_ok=True)
        tier_path(root).write_text(val + "\n", encoding="utf-8")
        st = load_state(root, required=False)
        if st:
            st["tier"] = val
            save_state(root, st)
        print("tier pinned: %s  (%s)" % (val, tier_path(root)))
        print(
            "budget: <= %d changed lines, <= %d file(s), %d doubt round(s), %d strike(s)"
            % (LINE_BUDGET[val], FILE_BUDGET[val], DOUBT_ROUNDS[val], MAX_STRIKES[val])
        )
        return 0
    pinned = read_tier_file(root)
    print("pinned tier: %s" % (pinned or "(none - default T1 applies)"))
    print("T0 MICRO - fast/small models: one action per turn, script-driven, hard stops")
    print("T1 LITE  - solid mid models: full ten steps, compact judgment (default)")
    print("T2 FULL  - frontier models: adds grilling, cross-model doubt, deep review")
    print("set it with: python3 scripts/viora.py tier --set T0")
    print("not sure which? run the 60-second probe in references/07-model-tiers.md")
    return 0


def cmd_start(args) -> int:
    root = args.root
    mode = args.mode.upper()
    if mode not in MODES:
        die("mode must be one of %s" % ", ".join(MODES))
    tier = resolve_tier(root, args.tier.upper() if args.tier else None)
    prev = load_state(root, required=False)
    if prev and not args.force and current_step(prev) is not None:
        die(
            "a run is already open (%s, step %s). Finish it, or pass --force to replace it."
            % (prev.get("mode"), current_step(prev))
        )
    if prev and args.force:
        archive_run(root, prev, "replaced")
    st = {
        "task": args.task,
        "mode": mode,
        "tier": tier,
        "started": now(),
        "steps": {},
        "strikes": 0,
        "demotions": [],
        "findings": [],
        "plan": {},
        "checkpoints": [],
        "history": [{"at": now(), "event": "start", "detail": "%s / %s" % (mode, tier)}],
    }
    save_state(root, st)
    # A fresh run must not inherit the previous run's proof.
    if evidence_path(root).exists() and not args.keep_evidence:
        evidence_path(root).replace(vdir(root) / "evidence.prev.jsonl")
    print(header(st))
    print("task: %s" % args.task)
    print("steps for %s: %s" % (mode, " -> ".join(str(n) for n in required_steps(st))))
    print(
        "budget: <= %d changed lines, <= %d file(s), %d doubt round(s), %d strike(s) then BLOCKED"
        % (LINE_BUDGET[tier], FILE_BUDGET[tier], DOUBT_ROUNDS[tier], MAX_STRIKES[tier])
    )
    if not has_git(root):
        print("note: no git here, so scope and rollback are limited. Fingerprints still work.")
    print("")
    print("Print the header line above at the top of every reply. Then run: viora.py next")
    return 0


def cmd_next(args) -> int:
    root = args.root
    st = load_state(root)
    n = current_step(st)
    print(header(st))
    if n is None:
        print("")
        print("All required steps are done. Emit the report: python3 scripts/viora.py report")
        return 0
    s = STEP_BY_N[n]
    tier = st["tier"]
    print("")
    print("STEP %d - %s" % (s["n"], s["key"]))
    print("produces: %s" % s["produces"])
    print("")
    for line in s[tier]:
        print("  " + line)
    if s["commands"]:
        print("")
        print("  run:")
        for c in s["commands"]:
            print("    %s" % c)
    print("")
    print("done when: %s" % s["done_when"])
    print("deeper: %s" % s["ref"])
    print("")
    if tier == "T0":
        print("T0 rule: do THIS step only, then stop and report the result in one short block.")
    print('then: python3 scripts/viora.py done %d --note "%s"' % (s["n"], s["note_hint"]))
    return 0


def cmd_done(args) -> int:
    root = args.root
    st = load_state(root)
    n = args.n
    if n not in STEP_BY_N:
        die("step must be 1-10")
    if n not in required_steps(st):
        die(
            "step %d is not part of mode %s (steps: %s)"
            % (n, st["mode"], ", ".join(str(x) for x in required_steps(st)))
        )
    s = STEP_BY_N[n]
    cur = current_step(st)
    if cur is not None and n > cur and not args.force:
        die("step %d is still open. Close it first, or pass --force and say why in the report." % cur)
    if s["requires_note"] and not args.note and not args.force:
        die(
            'step %d needs a --note holding what it produced, e.g.\n  --note "%s"'
            % (n, s["note_hint"])
        )

    # gate 1: PLAN must be machine-readable, not prose
    if n == 4 and not plan_of(st).get("files") and not args.force:
        die(
            "step 4 PLAN is not recorded, so nothing can hold you to it.\n"
            "  python3 scripts/viora.py plan --files <path[,path]> --lines %d"
            % LINE_BUDGET[st["tier"]]
        )

    # gate 2: GREEN and CLEAN must stay inside the declared scope
    if n in (6, 7) and not args.force:
        sc = scope_report(root, st)
        if sc["problems"]:
            die(
                "step %d cannot close - scope check failed:\n  - %s\n"
                "  fix the diff, or widen the plan on purpose: viora.py plan --files ... --lines ..."
                % (n, "\n  - ".join(sc["problems"]))
            )

    # gate 3: no PROVE without fresh recorded evidence
    if n == 8 and not args.force:
        rows = read_evidence(root)
        fresh = fresh_evidence(rows)
        if not rows:
            die(
                "step 8 PROVE has no recorded evidence, so completion cannot be claimed.\n"
                "  run the gates:   python3 scripts/viora.py gate\n"
                "  or record one:   python3 scripts/viora.py evidence --gate test "
                '--command "<cmd>" --result "PASS 12/12"'
            )
        if not fresh:
            die(
                "every evidence row is STALE - the code changed after those gates ran.\n"
                "  rerun them: python3 scripts/viora.py gate"
            )

    # gate 4: no REPORT while blocking findings are open
    if n == 10 and not args.force:
        blocking = open_findings(st, blocking_only=True)
        if blocking:
            ids = ", ".join(f["id"] for f in blocking)
            die(
                "cannot close step 10: %d blocking finding(s) still OPEN (%s).\n"
                "  fix and re-prove, or resolve them explicitly:\n"
                '  python3 scripts/viora.py ledger resolve %s --verdict DEFERRED --evidence "<why>"'
                % (len(blocking), ids, blocking[0]["id"])
            )

    st.setdefault("steps", {})[str(n)] = {
        "status": "done",
        "note": args.note or "",
        "forced": bool(args.force),
        "at": now(),
    }
    st.setdefault("history", []).append(
        {
            "at": now(),
            "event": "done",
            "detail": "step %d %s%s" % (n, s["key"], " (forced)" if args.force else ""),
        }
    )
    save_state(root, st)
    print(header(st))
    print(
        "step %d %s: done%s"
        % (n, s["key"], " (FORCED - it will be listed under UNPROVEN)" if args.force else "")
    )
    nxt = current_step(st)
    if nxt is None:
        print("all steps closed. run: python3 scripts/viora.py report")
    else:
        print("next: step %d %s   (python3 scripts/viora.py next)" % (nxt, STEP_BY_N[nxt]["key"]))
    return 0


def cmd_contract(args) -> int:
    root = args.root
    st = load_state(root, required=False)
    tier = st["tier"] if st else resolve_tier(root)
    body = [
        "# CONTRACT",
        "",
        "GOAL:      %s" % args.goal,
        "DONE-TEST: %s" % args.done_test,
        "PROTECTED: %s" % (args.protected or "(nothing named - fill this in)"),
        "NON-GOALS: %s" % (args.non_goals or "(nothing named - fill this in)"),
        "",
        "Tier: %s | Written: %s" % (tier, now()),
        "",
        "This file is the definition of done. Anything outside it is a FOLLOW-UP, not this task.",
        "",
    ]
    vdir(root).mkdir(parents=True, exist_ok=True)
    (vdir(root) / "contract.md").write_text("\n".join(body), encoding="utf-8")
    if st is not None:
        st["contract"] = {
            "goal": args.goal,
            "done_test": args.done_test,
            "protected": args.protected or "",
            "non_goals": args.non_goals or "",
        }
        save_state(root, st)
    print("\n".join(body[2:6]))
    print("")
    print("written: %s" % (vdir(root) / "contract.md"))
    weak = ("work", "works", "properly", "correctly", "better", "good", "fine", "ok", "nice", "fixed")
    if any(w in args.done_test.lower().split() for w in weak):
        print(
            "WARNING: DONE-TEST reads like an adjective, not a check. "
            "Replace it with a command, a request, or a click."
        )
    return 0


def cmd_evidence(args) -> int:
    root = args.root
    st = load_state(root, required=False)
    row = append_evidence(root, args.gate, args.command, args.result, st)
    print("evidence recorded: %s | %s | %s" % (args.gate, args.command, args.result))
    print("bound to working tree %s" % row["fingerprint"])
    rows = read_evidence(root)
    print(
        "rows: %d total, %d fresh (%s)"
        % (len(rows), len(fresh_evidence(rows)), evidence_path(root))
    )
    print("Edit any source file after this and the row becomes STALE. That is intentional.")
    return 0


def cmd_gate(args) -> int:
    root = args.root
    st = load_state(root, required=False)
    script = Path(__file__).resolve().with_name("verify.sh")
    if not script.exists():
        die(
            "verify.sh not found next to viora.py (%s). "
            "Record evidence manually with the 'evidence' command." % script
        )
    cmd = ["bash", str(script), "."]
    if args.only:
        cmd += ["--only", args.only]
    env = dict(os.environ)
    env["VIORA_NO_EVIDENCE"] = "1"  # viora.py records the rows itself, with fingerprints
    try:
        proc = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, timeout=args.timeout, env=env
        )
    except subprocess.TimeoutExpired:
        append_evidence(root, "gates", " ".join(cmd), "TIMEOUT after %ss" % args.timeout, st)
        die("gates timed out after %ss. That is a real result: report it as UNPROVEN." % args.timeout, 1)
    out = (proc.stdout or "") + (proc.stderr or "")
    sys.stdout.write(out)
    if out and not out.endswith("\n"):
        sys.stdout.write("\n")
    recorded = 0
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 3 or cells[0].lower() == "gate":
            continue
        gate, command, result = cells[0], cells[1].strip("`"), cells[2]
        append_evidence(root, gate, command, result, st)
        recorded += 1
    rows = read_evidence(root)
    print("")
    print(
        "recorded %d gate row(s); evidence now %d fresh / %d total -> %s"
        % (recorded, len(fresh_evidence(rows)), len(rows), evidence_path(root))
    )
    if recorded == 0:
        print("no gate table found in the output. Record what you ran by hand with 'evidence'.")
    if proc.returncode != 0:
        print("a gate FAILED. Fix it before claiming anything is done.")
    return proc.returncode


def cmd_strike(args) -> int:
    root = args.root
    st = load_state(root)
    cap = MAX_STRIKES[st["tier"]]
    if args.reset:
        st["strikes"] = 0
        save_state(root, st)
        print("strikes reset to 0/%d (new hypothesis family)" % cap)
        return 0
    st["strikes"] = int(st.get("strikes", 0)) + 1
    st.setdefault("history", []).append({"at": now(), "event": "strike", "detail": args.reason or ""})
    save_state(root, st)
    n = st["strikes"]
    print("strike %d/%d%s" % (n, cap, (" - " + args.reason) if args.reason else ""))
    if n >= cap:
        print("")
        print("STRIKE LIMIT REACHED. Stop editing. Report BLOCKED with:")
        print("  - the hypotheses you tested and the output that killed each one")
        print("  - the narrowest question that would unblock you, with your recommendation")
        print("  - what you left in the working tree")
        print("Consider undoing the mess first: python3 scripts/viora.py rollback --yes")
        print("Stopping here is a success state, not a failure.")
        if n > cap:
            print("")
            print("This strike is past the cap. There is no honest next edit - report BLOCKED.")
            return 2
    else:
        print("next attempt must test a DIFFERENT hypothesis. Write HYPOTHESIS / TEST / RESULT first.")
    return 0


def cmd_demote(args) -> int:
    root = args.root
    st = load_state(root)
    order = list(TIERS)
    cur = st["tier"]
    if cur == "T0":
        print("already at T0 MICRO. Do not go lower - narrow the task instead, or stop and ask.")
        return 2
    new = order[order.index(cur) - 1]
    st["tier"] = new
    st.setdefault("demotions", []).append(
        {"at": now(), "from": cur, "to": new, "reason": args.reason}
    )
    st.setdefault("history", []).append(
        {"at": now(), "event": "demote", "detail": "%s -> %s: %s" % (cur, new, args.reason)}
    )
    save_state(root, st)
    if args.pin:
        vdir(root).mkdir(parents=True, exist_ok=True)
        tier_path(root).write_text(new + "\n", encoding="utf-8")
    print("DEMOTE -> %s (%s)" % (new, args.reason))
    print("Print that line in your reply, then re-run the CURRENT step under %s rails." % new)
    print(
        "new budget: <= %d changed lines, <= %d file(s), %d strike(s)"
        % (LINE_BUDGET[new], FILE_BUDGET[new], MAX_STRIKES[new])
    )
    print("next: python3 scripts/viora.py next")
    return 0


def cmd_ledger(args) -> int:
    root = args.root
    st = load_state(root)
    st.setdefault("findings", [])
    if args.ledger_cmd == "add":
        raw = args.severity.strip()
        sev = "FYI" if raw.upper() == "FYI" else raw.capitalize()
        if sev not in SEVERITIES:
            die("severity must be one of %s" % ", ".join(SEVERITIES))
        fid = "F%d" % (len(st["findings"]) + 1)
        st["findings"].append(
            {
                "id": fid,
                "severity": sev,
                "where": args.where,
                "text": args.text,
                "verdict": "OPEN",
                "evidence": "-",
                "at": now(),
            }
        )
        save_state(root, st)
        write_ledger(root, st)
        print("%s %s @ %s: %s" % (fid, sev, args.where, args.text))
        if sev in BLOCKING:
            print("blocking: step 10 stays closed until this has a verdict.")
        return 0

    if args.ledger_cmd == "list":
        rows = st["findings"]
        if args.open:
            rows = [f for f in rows if f.get("verdict", "OPEN") == "OPEN"]
        if not rows:
            print("ledger empty%s." % (" (no open findings)" if args.open else ""))
            return 0
        print("| ID | Severity | Where | Finding | Verdict |")
        print("|---|---|---|---|---|")
        for f in rows:
            print(
                "| %s | %s | %s | %s | %s |"
                % (
                    f["id"],
                    f["severity"],
                    f["where"],
                    f["text"].replace("|", "/"),
                    f.get("verdict", "OPEN"),
                )
            )
        still_open = [f for f in rows if f.get("verdict", "OPEN") == "OPEN"]
        blocking = [f for f in still_open if f["severity"] in BLOCKING]
        print("")
        print("open: %d | blocking: %d" % (len(still_open), len(blocking)))
        return 0

    if args.ledger_cmd == "resolve":
        verdict = args.verdict.upper()
        if verdict not in ("FIXED", "REJECTED", "DEFERRED"):
            die("verdict must be FIXED, REJECTED or DEFERRED")
        target = None
        for f in st["findings"]:
            if f["id"].upper() == args.id.upper():
                target = f
                break
        if target is None:
            die("no finding %s. See: python3 scripts/viora.py ledger list" % args.id)
        if target.get("verdict", "OPEN") != "OPEN" and not args.force:
            die("%s already has verdict %s. A verdict is final." % (target["id"], target["verdict"]))
        if verdict == "FIXED" and not args.evidence:
            die(
                "FIXED needs --evidence: the command output that proves it.\n"
                "  no pin, no FIXED. Use --verdict DEFERRED if you did not fix it."
            )
        if verdict in ("REJECTED", "DEFERRED") and not args.evidence:
            die("%s needs --evidence carrying the reason." % verdict)
        target["verdict"] = verdict
        target["evidence"] = args.evidence
        target["resolved_at"] = now()
        save_state(root, st)
        write_ledger(root, st)
        print("%s -> %s (%s)" % (target["id"], verdict, args.evidence))
        print("blocking findings still open: %d" % len(open_findings(st, blocking_only=True)))
        return 0

    die("ledger needs a subcommand: add | list | resolve")


# --------------------------------------------------------------------------- #
# commands: plan, scope, checkpoint, rollback
# --------------------------------------------------------------------------- #


def archive_run(root: str, st: dict, outcome: str) -> None:
    """Append a one-line summary of a finished run, so `stats` can learn from it."""
    rows = read_evidence(root, mark_stale=False)
    steps = required_steps(st)
    entry = {
        "at": now(),
        "started": st.get("started"),
        "task": st.get("task", "")[:160],
        "mode": st.get("mode"),
        "tier": st.get("tier"),
        "outcome": outcome,
        "steps_done": [n for n in steps if step_status(st, n) == "done"],
        "steps_missing": [n for n in steps if step_status(st, n) != "done"],
        "steps_forced": [
            n for n in steps if st.get("steps", {}).get(str(n), {}).get("forced")
        ],
        "strikes": st.get("strikes", 0),
        "demotions": st.get("demotions", []),
        "findings_total": len(st.get("findings", [])),
        "findings_blocking_open": len(open_findings(st, blocking_only=True)),
        "evidence_rows": len(rows),
    }
    vdir(root).mkdir(parents=True, exist_ok=True)
    with runs_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cmd_plan(args) -> int:
    root = args.root
    st = load_state(root)
    if args.show or not args.files:
        plan = plan_of(st)
        if not plan.get("files"):
            print("no plan recorded.")
            print(
                "  python3 scripts/viora.py plan --files <path[,path]> --lines %d --frozen '<names>'"
                % LINE_BUDGET[st["tier"]]
            )
            return 1 if args.show else 2
        print("FILES:  %s" % ", ".join(plan["files"]))
        print("BUDGET: <= %s changed lines" % plan.get("lines"))
        print("FROZEN: %s" % (plan.get("frozen") or "(nothing frozen)"))
        print("recorded: %s" % plan.get("at"))
        return 0

    files = []
    for chunk in args.files:
        for part in chunk.split(","):
            part = part.strip()
            if part:
                files.append(part)
    if not files:
        die("--files needs at least one path")
    tier = st["tier"]
    cap = FILE_BUDGET[tier]
    if len(files) > cap and not args.force:
        die(
            "%d files declared, tier %s allows %d.\n"
            "  Split the task, or say why this is one atomic change and pass --force."
            % (len(files), tier, cap)
        )
    lines = int(args.lines) if args.lines else LINE_BUDGET[tier]
    if lines > LINE_BUDGET[tier] and not args.force:
        die(
            "line budget %d exceeds the %s ceiling of %d. Split it, or pass --force."
            % (lines, tier, LINE_BUDGET[tier])
        )
    missing = [f for f in files if not (Path(root) / f).exists()]
    st["plan"] = {
        "files": files,
        "lines": lines,
        "frozen": args.frozen or "",
        "at": now(),
        "new_files": missing,
    }
    st.setdefault("history", []).append(
        {"at": now(), "event": "plan", "detail": "%d file(s), <=%d lines" % (len(files), lines)}
    )
    save_state(root, st)
    print("PLAN recorded")
    print("FILES:  %s" % ", ".join(files))
    print("BUDGET: <= %d changed lines" % lines)
    print("FROZEN: %s" % (args.frozen or "(nothing frozen)"))
    if missing:
        print("new file(s) to be created: %s" % ", ".join(missing))
    print("")
    print("From now on `scope` fails on any file outside this list. Check it before you claim GREEN.")
    return 0


def cmd_scope(args) -> int:
    root = args.root
    st = load_state(root)
    sc = scope_report(root, st, args.base)
    print(header(st))
    print("")
    if sc["unknown"]:
        print("scope: UNKNOWN - no git repository here, so the diff cannot be measured.")
        print("Declare the files you touched in the report by hand, and keep the change tiny.")
        return 0
    declared = sc["declared"]
    print("declared: %s" % (", ".join(declared) if declared else "(nothing recorded)"))
    print("touched:  %s" % (", ".join(sc["touched"]) if sc["touched"] else "(no changes yet)"))
    print(
        "lines:    %s changed (budget %d) | files: %d (tier cap %d)"
        % (sc["lines"], sc["line_cap"], len(sc["touched"]), sc["file_cap"])
    )
    if sc.get("untouched"):
        print("declared but untouched: %s" % ", ".join(sc["untouched"]))
    print("")
    if sc["problems"]:
        print("SCOPE FAIL - %d problem(s):" % len(sc["problems"]))
        for p in sc["problems"]:
            print("  - %s" % p)
        print("")
        print("Two honest ways out: shrink the diff, or widen the plan on purpose and say so.")
        print("  python3 scripts/viora.py plan --files <the real list> --lines <n>")
        return 1
    print("SCOPE OK - every changed file was declared, and the budget holds.")
    return 0


def cmd_checkpoint(args) -> int:
    root = args.root
    st = load_state(root, required=False)
    if not has_git(root):
        print("checkpoint needs git, and this is not a git repository.")
        print("Fallback: copy the files you are about to edit somewhere safe before you edit them.")
        return 1
    head = (run_git(root, ["rev-parse", "HEAD"]) or "").strip()
    if not head:
        print("this repository has no commits yet, so there is no base to return to.")
        print("Fallback: git add -A && git commit -m 'baseline' before you start editing.")
        return 1
    diff = run_git(root, ["diff", "HEAD"]) or ""
    untracked = [
        x.strip()
        for x in (run_git(root, ["ls-files", "--others", "--exclude-standard"]) or "").split("\n")
        if x.strip() and not x.strip().startswith(".viora")
    ]
    cid = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    d = checkpoints_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / (cid + ".patch")).write_text(diff, encoding="utf-8")
    meta = {
        "id": cid,
        "head": head,
        "label": args.label or "",
        "at": now(),
        "untracked": untracked,
        "patch_bytes": len(diff),
        "fingerprint": fingerprint(root),
    }
    (d / (cid + ".json")).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    if st is not None:
        st.setdefault("checkpoints", []).append(meta)
        save_state(root, st)
    print("checkpoint %s saved%s" % (cid, (" - " + args.label) if args.label else ""))
    print("base commit: %s | uncommitted diff: %d bytes" % (head[:10], len(diff)))
    print("undo everything since this point: python3 scripts/viora.py rollback --yes")
    return 0


def _load_checkpoints(root: str):
    d = checkpoints_dir(root)
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    return out


def cmd_rollback(args) -> int:
    root = args.root
    cps = _load_checkpoints(root)
    if not cps:
        print("no checkpoints. Next time, run `checkpoint` before you start editing.")
        return 1
    if args.list:
        print("| ID | When | Label | Base | Patch |")
        print("|---|---|---|---|---|")
        for c in cps:
            print(
                "| %s | %s | %s | %s | %d B |"
                % (c["id"], c["at"], c.get("label", "") or "-", c["head"][:10], c.get("patch_bytes", 0))
            )
        return 0
    target = cps[-1]
    if args.id:
        match = [c for c in cps if c["id"] == args.id]
        if not match:
            die("no checkpoint %s. List them: python3 scripts/viora.py rollback --list" % args.id)
        target = match[0]
    if not args.yes:
        print("This would discard every uncommitted change made after checkpoint %s." % target["id"])
        print("  label: %s" % (target.get("label") or "(none)"))
        print("  base commit: %s" % target["head"][:10])
        print("Re-run with --yes if that is what you want.")
        return 2
    if not has_git(root):
        die("rollback needs git.")
    head = (run_git(root, ["rev-parse", "HEAD"]) or "").strip()
    if head != target["head"] and not args.force:
        die(
            "HEAD moved since that checkpoint (%s -> %s). Rolling back could destroy commits.\n"
            "  Inspect it yourself, or pass --force if you are certain."
            % (target["head"][:10], head[:10])
        )
    if run_git(root, ["checkout", "--", "."]) is None:
        die("git checkout failed; nothing was changed.")
    patch = checkpoints_dir(root) / (target["id"] + ".patch")
    restored = "clean tree at %s" % head[:10]
    if patch.exists() and patch.stat().st_size > 0:
        try:
            proc = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", str(patch)],
                cwd=root, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            die("could not reapply the checkpoint patch (%s). Tree is at %s." % (exc, head[:10]), 1)
        if proc.returncode != 0:
            print("WARNING: the checkpoint patch did not reapply cleanly:")
            print((proc.stderr or "").strip()[:600])
            print("The tree is now the clean commit %s. The patch is kept at %s" % (head[:10], patch))
            return 1
        restored = "state at checkpoint %s" % target["id"]
    now_untracked = [
        x.strip()
        for x in (run_git(root, ["ls-files", "--others", "--exclude-standard"]) or "").split("\n")
        if x.strip() and not x.strip().startswith(".viora")
    ]
    added = [f for f in now_untracked if f not in target.get("untracked", [])]
    print("rolled back to %s" % restored)
    if added:
        print("")
        print("These untracked files were created after the checkpoint and were NOT removed:")
        for f in added:
            print("  %s" % f)
        print("Delete them yourself if they were part of the mess.")
    print("")
    print("Now change hypothesis, not volume. Write HYPOTHESIS / TEST / RESULT before the next edit.")
    return 0


# --------------------------------------------------------------------------- #
# commands: doctor, stats
# --------------------------------------------------------------------------- #


def _detect_monorepo(root: str):
    signals = []
    p = Path(root)
    pkg = p / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            if data.get("workspaces"):
                signals.append("package.json workspaces")
        except ValueError:
            pass
    for name, label in (
        ("pnpm-workspace.yaml", "pnpm workspace"),
        ("lerna.json", "lerna"),
        ("turbo.json", "turborepo"),
        ("nx.json", "nx"),
        ("go.work", "go workspace"),
    ):
        if (p / name).exists():
            signals.append(label)
    cargo = p / "Cargo.toml"
    if cargo.exists():
        try:
            if "[workspace]" in cargo.read_text(encoding="utf-8", errors="replace"):
                signals.append("cargo workspace")
        except OSError:
            pass
    return signals


def cmd_doctor(args) -> int:
    root = args.root
    ok, warn, fail = [], [], []

    v = sys.version_info
    if v >= (3, 8):
        ok.append("python %d.%d.%d" % (v[0], v[1], v[2]))
    else:
        fail.append("python %d.%d is too old; this script needs 3.8+" % (v[0], v[1]))

    here = Path(__file__).resolve().parent
    for name in ("verify.sh", "scan_repo.py", "find_duplicates.py", "ui_guard.py"):
        if (here / name).exists():
            ok.append("script present: %s" % name)
        else:
            warn.append("missing script: %s (that capability is unavailable)" % name)

    if has_git(root):
        ok.append("git repository detected - scope, budget and rollback all work")
        head = (run_git(root, ["rev-parse", "HEAD"]) or "").strip()
        if not head:
            warn.append("no commits yet, so checkpoint/rollback have no base. Make a baseline commit.")
        dirty = (run_git(root, ["status", "--porcelain"]) or "").strip()
        if dirty:
            warn.append("working tree is already dirty; your diff will include someone else's changes")
    else:
        warn.append(
            "not a git repository: `scope` cannot measure the diff and `rollback` is unavailable"
        )

    try:
        d = vdir(root)
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        ok.append("state directory is writable: %s" % d)
    except OSError as exc:
        fail.append("cannot write to .viora (%s) - the protocol cannot record anything" % exc)

    pinned = read_tier_file(root)
    if pinned:
        ok.append("tier pinned: %s" % pinned)
    else:
        warn.append(
            "no tier pinned; T1 is assumed. If you are a fast/small model, run: tier --set T0"
        )

    gates = []
    script = here / "verify.sh"
    if script.exists():
        try:
            proc = subprocess.run(
                ["bash", str(script), ".", "--list"],
                cwd=root, capture_output=True, text=True, timeout=120,
            )
            gates = [l.strip() for l in (proc.stdout or "").splitlines() if l.strip()]
        except (OSError, subprocess.SubprocessError) as exc:
            warn.append("could not list gates (%s)" % exc)
    if gates:
        ok.append("%d gate(s) detected" % len(gates))
    else:
        warn.append(
            "no gates detected: nothing here can prove your change. "
            "Everything you ship is UNPROVEN until you add a check or run one by hand."
        )

    mono = _detect_monorepo(root)
    if mono:
        warn.append(
            "monorepo detected (%s): run gates in the package you changed, not only at the root"
            % ", ".join(mono)
        )

    st = load_state(root, required=False)
    if st:
        cur = current_step(st)
        ok.append(
            "run in progress: %s / %s, step %s"
            % (st.get("mode"), st.get("tier"), cur if cur else "all closed")
        )
        rows = latest_by_gate(read_evidence(root))
        stale = current_stale(rows)
        if stale:
            warn.append(
                "%d of %d gate(s) have STALE evidence - rerun them: viora.py gate"
                % (len(stale), len(rows))
            )
    else:
        ok.append("no run in progress")

    print("VioraCode doctor - v%s" % VERSION)
    print("root: %s" % Path(root).resolve())
    print("")
    for line in ok:
        print("  OK    %s" % line)
    for line in warn:
        print("  WARN  %s" % line)
    for line in fail:
        print("  FAIL  %s" % line)
    print("")
    if gates:
        print("gates this repo declares:")
        for g in gates:
            print("  %s" % g)
        print("")
    if fail:
        print("Fix the FAIL lines before working. The protocol cannot function without them.")
        return 1
    if warn:
        print("Usable. Read each WARN line - every one of them is a way your report could mislead.")
    else:
        print("Everything the protocol needs is present.")
    print("next: python3 scripts/viora.py start --mode FIX --task \"<the task>\"")
    return 0


def cmd_stats(args) -> int:
    root = args.root
    p = runs_path(root)
    if not p.exists():
        print("no finished runs recorded yet. `report` writes one line per run to %s" % p)
        return 0
    runs = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except ValueError:
            continue
    if not runs:
        print("runs file exists but holds no parsable entries.")
        return 0
    total = len(runs)
    by_outcome = {}
    by_tier = {}
    missing_counter = {}
    forced_counter = {}
    strikes = 0
    demotions = 0
    no_evidence = 0
    for r in runs:
        by_outcome[r.get("outcome", "?")] = by_outcome.get(r.get("outcome", "?"), 0) + 1
        by_tier[r.get("tier", "?")] = by_tier.get(r.get("tier", "?"), 0) + 1
        for n in r.get("steps_missing", []):
            missing_counter[n] = missing_counter.get(n, 0) + 1
        for n in r.get("steps_forced", []):
            forced_counter[n] = forced_counter.get(n, 0) + 1
        strikes += int(r.get("strikes", 0) or 0)
        demotions += len(r.get("demotions", []) or [])
        if not r.get("evidence_rows"):
            no_evidence += 1
    print("VioraCode stats - %d run(s) recorded" % total)
    print("")
    print("outcome:  %s" % ", ".join("%s %d" % (k, v) for k, v in sorted(by_outcome.items())))
    print("tier:     %s" % ", ".join("%s %d" % (k, v) for k, v in sorted(by_tier.items())))
    print("strikes:  %d total (%.1f per run)" % (strikes, strikes / float(total)))
    print("demotions: %d" % demotions)
    print("runs with zero evidence: %d" % no_evidence)
    if missing_counter:
        print("")
        print("steps most often left undone:")
        for n, c in sorted(missing_counter.items(), key=lambda kv: -kv[1])[:5]:
            key = STEP_BY_N.get(int(n), {}).get("key", "?") if str(n).isdigit() else "?"
            print("  step %s %-9s %d run(s)" % (n, key, c))
    if forced_counter:
        print("")
        print("steps most often forced past their check:")
        for n, c in sorted(forced_counter.items(), key=lambda kv: -kv[1])[:5]:
            key = STEP_BY_N.get(int(n), {}).get("key", "?") if str(n).isdigit() else "?"
            print("  step %s %-9s %d run(s)" % (n, key, c))
    print("")
    print("Read this as a map of where this model actually breaks, and tighten those steps.")
    print("A step that keeps getting forced or skipped is a step whose instructions are too vague.")
    return 0


# --------------------------------------------------------------------------- #
# commands: report, check, handoff, status
# --------------------------------------------------------------------------- #


def cmd_report(args) -> int:
    root = args.root
    st = load_state(root)
    rows = latest_by_gate(read_evidence(root))
    fresh = fresh_evidence(rows)
    stale = current_stale(rows)
    steps = required_steps(st)
    missing = [n for n in steps if step_status(st, n) != "done"]
    forced = [n for n in steps if st.get("steps", {}).get(str(n), {}).get("forced")]
    blocking = open_findings(st, blocking_only=True)
    # A `red` row is SUPPOSED to say FAIL - that is the reproduction, not a defect.
    failed = [
        r for r in fresh
        if not historical_gate(r) and "FAIL" in str(r.get("result", "")).upper()
    ]
    skipped = [
        r for r in fresh
        if not historical_gate(r) and "SKIP" in str(r.get("result", "")).upper()
    ]
    sc = scope_report(root, st)

    if args.verdict:
        verdict = args.verdict.upper()
    elif missing or blocking or failed or not fresh:
        verdict = "BLOCKED"
    else:
        verdict = "DELIVERED"

    out = []
    out.append(header(st))
    out.append("")
    out.append("VERDICT: %s" % verdict)
    out.append("MODE: %s | TIER: %s | TASK: %s" % (st["mode"], st["tier"], st.get("task", "")))
    c = st.get("contract") or {}
    if c:
        out.append("")
        out.append("CONTRACT")
        out.append("- GOAL: %s" % c.get("goal", ""))
        out.append("- DONE-TEST: %s" % c.get("done_test", ""))
        if c.get("protected"):
            out.append("- PROTECTED: %s" % c["protected"])
    out.append("")
    out.append("WHAT CHANGED")
    if not sc["unknown"] and sc["touched"]:
        out.append(
            "- %d file(s), %s changed line(s): %s"
            % (len(sc["touched"]), sc["lines"], ", ".join(sc["touched"]))
        )
    any_note = False
    for n in steps:
        note = st.get("steps", {}).get(str(n), {}).get("note", "")
        if note:
            any_note = True
            out.append("- %d %s: %s" % (n, STEP_BY_N[n]["key"], note))
    if not any_note:
        out.append("- (nothing recorded - the steps were closed without notes)")
    out.append("")
    out.append("EVIDENCE")
    if rows:
        out.append("| Gate | Command | Result | Fresh |")
        out.append("|---|---|---|---|")
        for r in rows:
            out.append(
                "| %s | `%s` | %s | %s |"
                % (
                    r.get("gate", "?"),
                    r.get("command", "?"),
                    r.get("result", "?"),
                    ("pre-fix" if historical_gate(r) else "STALE") if r.get("stale") else "yes",
                )
            )
    else:
        out.append("- NONE RECORDED. Nothing here is proven; do not claim it works.")
    out.append("")
    out.append("NOT DONE / UNPROVEN")
    unproven = []
    for n in missing:
        unproven.append("- step %d %s was never completed" % (n, STEP_BY_N[n]["key"]))
    for n in forced:
        unproven.append("- step %d %s was forced past its check" % (n, STEP_BY_N[n]["key"]))
    if stale:
        unproven.append(
            "- %d gate(s) have STALE evidence (%s): the code changed after they ran, "
            "so they prove nothing about the current diff"
            % (len(stale), ", ".join(str(r.get("gate")) for r in stale))
        )
    for r in skipped:
        unproven.append("- gate '%s' was SKIPPED, so that surface is unproven" % r.get("gate"))
    for r in failed:
        unproven.append("- gate '%s' FAILED: %s" % (r.get("gate"), r.get("result")))
    for f in blocking:
        unproven.append(
            "- %s %s @ %s is still OPEN: %s" % (f["id"], f["severity"], f["where"], f["text"])
        )
    for p in sc["problems"]:
        unproven.append("- scope: %s" % p)
    if sc["unknown"]:
        unproven.append("- no git here, so the real size and shape of this diff was never measured")
    if st.get("strikes"):
        unproven.append(
            "- %d failed attempt(s) recorded; the root cause may be wider than the fix"
            % st["strikes"]
        )
    if not unproven:
        unproven.append(
            "- untested paths outside DONE-TEST; anything the gates marked SKIP; "
            "performance, concurrency and error paths were not measured"
        )
    out += unproven
    res = [f for f in st.get("findings", []) if f.get("verdict", "OPEN") != "OPEN"]
    if res:
        out.append("")
        out.append("FINDINGS RESOLVED")
        for f in res:
            out.append(
                "- %s %s -> %s (%s)" % (f["id"], f["severity"], f["verdict"], f.get("evidence", ""))
            )
    deferred = [f for f in st.get("findings", []) if f.get("verdict") == "DEFERRED"]
    others = [f for f in open_findings(st) if f["severity"] not in BLOCKING]
    out.append("")
    out.append("FOLLOW-UPS")
    if deferred or others:
        for f in deferred + others:
            out.append("- %s %s @ %s: %s" % (f["id"], f["severity"], f["where"], f["text"]))
    else:
        out.append("- (none recorded)")
    if st.get("demotions"):
        out.append("")
        out.append("TIER HISTORY")
        for d in st["demotions"]:
            out.append("- %s -> %s: %s" % (d["from"], d["to"], d["reason"]))
    out.append("")
    text = "\n".join(out)
    vdir(root).mkdir(parents=True, exist_ok=True)
    (vdir(root) / "report.md").write_text(text, encoding="utf-8")
    if not args.no_archive:
        archive_run(root, st, verdict)
    print(text)
    print("written: %s" % (vdir(root) / "report.md"))
    print(
        "Paste this report as-is. Shortening a machine-generated UNPROVEN list is fabrication."
    )
    return 0 if verdict == "DELIVERED" else 1


def cmd_check(args) -> int:
    root = args.root
    st = load_state(root)
    problems = []
    steps = required_steps(st)
    for n in steps:
        if step_status(st, n) != "done":
            problems.append("step %d %s is not done" % (n, STEP_BY_N[n]["key"]))
        elif st.get("steps", {}).get(str(n), {}).get("forced"):
            problems.append("step %d %s was forced, not proven" % (n, STEP_BY_N[n]["key"]))
    if not (vdir(root) / "contract.md").exists():
        problems.append("no contract.md - the definition of done was never written")
    rows = latest_by_gate(read_evidence(root))
    # Only rows that are meant to describe the CURRENT tree can prove anything about it.
    proving = [r for r in rows if not historical_gate(r)]
    fresh = fresh_evidence(proving)
    stale = [r for r in proving if r.get("stale")]
    if not rows:
        problems.append("evidence log is empty - no claim in the report can be supported")
    elif not proving:
        problems.append(
            "only pre-fix evidence exists (%s) - nothing proves the CURRENT tree. "
            "Run: viora.py gate" % gate_names(rows)
        )
    elif not fresh:
        problems.append(
            "all %d gate(s) have STALE evidence (%s) - the code changed after they ran"
            % (len(stale), gate_names(stale))
        )
    elif stale:
        problems.append(
            "%d of %d gate(s) have STALE evidence (%s) - rerun those gates: viora.py gate"
            % (len(stale), len(proving), gate_names(stale))
        )
    for r in fresh:
        if "FAIL" in str(r.get("result", "")).upper():
            problems.append("gate '%s' is recorded as FAIL" % r.get("gate"))
    for f in open_findings(st, blocking_only=True):
        problems.append("%s %s is still OPEN: %s" % (f["id"], f["severity"], f["text"]))
    sc = scope_report(root, st)
    for p in sc["problems"]:
        problems.append("scope: %s" % p)
    print(header(st))
    print("")
    if problems:
        print("NOT READY - %d problem(s):" % len(problems))
        for p in problems:
            print("  - %s" % p)
        print("")
        print("Fix these before you use the word 'done'. If you cannot, report BLOCKED with this list.")
        return 1
    print(
        "READY: every required step closed and proven, contract written, "
        "%d fresh evidence row(s), scope clean, no open blocking findings." % len(fresh)
    )
    print("Still state what remains unproven - green gates are not the same as correct behaviour.")
    return 0


def cmd_handoff(args) -> int:
    root = args.root
    st = load_state(root)
    rows = read_evidence(root)
    cur = current_step(st)
    c = st.get("contract") or {}
    plan = plan_of(st)
    print("HANDOFF - paste this into the next session as the first message")
    print("")
    print("TASK: %s" % st.get("task", ""))
    print("MODE: %s | TIER: %s | PROTOCOL: VioraCode v%s" % (st["mode"], st["tier"], VERSION))
    print("GOAL: %s" % c.get("goal", "(no contract written)"))
    print("DONE-TEST: %s" % c.get("done_test", "(none)"))
    print("PROTECTED: %s" % c.get("protected", "(none)"))
    if plan.get("files"):
        print("PLAN FILES: %s (<= %s lines)" % (", ".join(plan["files"]), plan.get("lines")))
    print("")
    print("DONE SO FAR")
    for n in required_steps(st):
        if step_status(st, n) == "done":
            note = st.get("steps", {}).get(str(n), {}).get("note", "")
            forced = " [FORCED]" if st.get("steps", {}).get(str(n), {}).get("forced") else ""
            print("- %d %s%s: %s" % (n, STEP_BY_N[n]["key"], forced, note or "(no note)"))
    print("")
    print("CURRENT STEP: %s" % ("%d %s" % (cur, STEP_BY_N[cur]["key"]) if cur else "all closed"))
    print("STRIKES: %d/%d" % (st.get("strikes", 0), MAX_STRIKES[st["tier"]]))
    print("")
    print("PROVEN (fresh command output on disk)")
    if rows:
        for r in latest_by_gate(rows):
            print(
                "- %s: %s (%s)%s"
                % (r.get("gate"), r.get("result"), r.get("command"), " [STALE]" if r.get("stale") else "")
            )
    else:
        print("- nothing proven yet")
    print("")
    print("OPEN FINDINGS")
    op = open_findings(st)
    if op:
        for f in op:
            print("- %s %s @ %s: %s" % (f["id"], f["severity"], f["where"], f["text"]))
    else:
        print("- none")
    print("")
    print("DO NOT redo finished steps. Do not re-explore what is written above.")
    print("FIRST ACTION FOR YOU: python3 scripts/viora.py next")
    print("State on disk: %s" % vdir(root))
    return 0


def cmd_status(args) -> int:
    root = args.root
    st = load_state(root, required=False)
    if st is None:
        print("no run in progress.")
        print("pinned tier: %s" % (read_tier_file(root) or "(none - default T1)"))
        print('start one: python3 scripts/viora.py start --mode FIX --task "<task>"')
        return 0
    rows = read_evidence(root)
    fresh = fresh_evidence(rows)
    print(header(st))
    print("task: %s" % st.get("task", ""))
    print("")
    for n in required_steps(st):
        entry = st.get("steps", {}).get(str(n), {})
        mark = "x" if entry.get("status") == "done" else " "
        if entry.get("forced"):
            mark = "!"
        print("  [%s] %2d %-9s %s" % (mark, n, STEP_BY_N[n]["key"], entry.get("note", "")))
    print("")
    plan = plan_of(st)
    if plan.get("files"):
        print("plan: %s (<= %s lines)" % (", ".join(plan["files"]), plan.get("lines")))
    sc = scope_report(root, st)
    if not sc["unknown"]:
        print(
            "diff: %d file(s), %s line(s) | scope %s"
            % (len(sc["touched"]), sc["lines"], "FAIL" if sc["problems"] else "OK")
        )
    print(
        "evidence: %d fresh / %d total | strikes: %d/%d | open findings: %d (blocking: %d)"
        % (
            len(fresh), len(rows), st.get("strikes", 0), MAX_STRIKES[st["tier"]],
            len(open_findings(st)), len(open_findings(st, blocking_only=True)),
        )
    )
    cps = st.get("checkpoints") or []
    if cps:
        print("checkpoints: %d (latest %s)" % (len(cps), cps[-1]["id"]))
    print(
        "budget: <= %d changed lines, <= %d file(s)"
        % (LINE_BUDGET[st["tier"]], FILE_BUDGET[st["tier"]])
    )
    return 0


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="viora.py",
        description=(
            "VioraCode conductor v%s: keeps the protocol on disk so a weak model cannot "
            "drift off it, and cannot report a pass it never earned." % VERSION
        ),
    )
    p.add_argument("--root", default=".", help="repository root (default: .)")
    p.add_argument("--version", action="version", version="VioraCode conductor %s" % VERSION)
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("doctor", help="check the install, the repo, and what can be proven here")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("tier", help="show or pin the tier (T0/T1/T2)")
    s.add_argument("--set", help="pin a tier into .viora/tier")
    s.set_defaults(func=cmd_tier)

    s = sub.add_parser("start", help="open a run")
    s.add_argument("--mode", required=True, help="one of: " + ", ".join(MODES))
    s.add_argument("--tier", help="T0 | T1 | T2 (a pinned .viora/tier wins)")
    s.add_argument("--task", required=True, help="the request in one line")
    s.add_argument("--force", action="store_true", help="replace an open run")
    s.add_argument(
        "--keep-evidence", action="store_true",
        help="do not rotate the previous run's evidence log",
    )
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("next", help="print the current step, written for the active tier")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("done", help="close a step (four steps refuse without proof)")
    s.add_argument("n", type=int, help="step number 1-10")
    s.add_argument("--note", help="what the step produced")
    s.add_argument("--force", action="store_true", help="override a refusal; it lands in UNPROVEN")
    s.set_defaults(func=cmd_done)

    s = sub.add_parser("contract", help="write the four contract lines")
    s.add_argument("--goal", required=True)
    s.add_argument("--done-test", required=True, dest="done_test")
    s.add_argument("--protected")
    s.add_argument("--non-goals", dest="non_goals")
    s.set_defaults(func=cmd_contract)

    s = sub.add_parser("plan", help="record the file list and line budget so scope can enforce it")
    s.add_argument("--files", action="append", help="comma-separated paths; repeatable")
    s.add_argument("--lines", help="changed-line budget")
    s.add_argument("--frozen", help="public names you will not rename")
    s.add_argument("--show", action="store_true", help="print the recorded plan")
    s.add_argument("--force", action="store_true", help="exceed the tier budget on purpose")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("scope", help="compare the real diff against the plan and the budget")
    s.add_argument("--base", help="git ref to diff against (default HEAD)")
    s.set_defaults(func=cmd_scope)

    s = sub.add_parser("checkpoint", help="save an undo point before editing")
    s.add_argument("--label", help="why you took it")
    s.set_defaults(func=cmd_checkpoint)

    s = sub.add_parser("rollback", help="restore the working tree to a checkpoint")
    s.add_argument("id", nargs="?", help="checkpoint id (default: the latest)")
    s.add_argument("--list", action="store_true", help="list checkpoints")
    s.add_argument("--yes", action="store_true", help="required: confirm the discard")
    s.add_argument("--force", action="store_true", help="roll back even though HEAD moved")
    s.set_defaults(func=cmd_rollback)

    s = sub.add_parser("gate", help="run verify.sh and record every row as fingerprinted evidence")
    s.add_argument("--only", help="comma list: lint,types,test,build,format")
    s.add_argument("--timeout", type=int, default=900)
    s.set_defaults(func=cmd_gate)

    s = sub.add_parser("evidence", help="record one command result by hand")
    s.add_argument("--gate", required=True)
    s.add_argument("--command", required=True)
    s.add_argument("--result", required=True)
    s.set_defaults(func=cmd_evidence)

    s = sub.add_parser("strike", help="count a failed attempt; caps at the tier limit")
    s.add_argument("--reason", help="the hypothesis that died")
    s.add_argument("--reset", action="store_true", help="new hypothesis family")
    s.set_defaults(func=cmd_strike)

    s = sub.add_parser("demote", help="drop one tier after an observable failure")
    s.add_argument("--reason", required=True)
    s.add_argument("--pin", action="store_true", help="also pin the new tier for future runs")
    s.set_defaults(func=cmd_demote)

    s = sub.add_parser("ledger", help="findings journal for the review loop")
    lsub = s.add_subparsers(dest="ledger_cmd")
    a = lsub.add_parser("add")
    a.add_argument("--severity", required=True, help="Critical | Required | Optional | Nit | FYI")
    a.add_argument("--where", required=True, help="path:line")
    a.add_argument("--text", required=True)
    a = lsub.add_parser("list")
    a.add_argument("--open", action="store_true", help="only findings without a verdict")
    a = lsub.add_parser("resolve")
    a.add_argument("id")
    a.add_argument("--verdict", required=True, help="FIXED | REJECTED | DEFERRED")
    a.add_argument("--evidence", help="proof for FIXED, reason for REJECTED/DEFERRED")
    a.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_ledger)

    s = sub.add_parser("report", help="emit the report contract from what was recorded")
    s.add_argument("--verdict", help="override: DELIVERED | NO_CHANGE | BLOCKED")
    s.add_argument("--no-archive", action="store_true", help="do not append to runs.jsonl")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("check", help="refuse-to-lie check before you claim completion")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("handoff", help="print a context-loss handoff block")
    s.set_defaults(func=cmd_handoff)

    s = sub.add_parser("status", help="one-screen state of the run")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("stats", help="where runs actually fail, across runs")
    s.set_defaults(func=cmd_stats)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    if args.command == "ledger" and not getattr(args, "ledger_cmd", None):
        die("ledger needs a subcommand: add | list | resolve")
    if not Path(args.root).is_dir():
        die("--root %s is not a directory" % args.root)
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\nviora: interrupted. State on disk is still valid.\n")
        raise SystemExit(130)
