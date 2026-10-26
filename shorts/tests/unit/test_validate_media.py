"""Item 2 (1.1.0): example plans must validate on a clean machine without their media,
while a missing file is still an error for real plans."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

from shortskit import plan as P

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").glob("*.plan.json"))


def _film_plan() -> dict:
    raw, _ = P.load(ROOT / "examples" / "c-film-edit.plan.json")
    return copy.deepcopy(raw)


def test_examples_have_no_absolute_paths():
    assert EXAMPLES
    for f in EXAMPLES:
        raw = json.loads(f.read_text(encoding="utf-8"))
        for s in raw["scenes"]:
            ref = s["source"].get("ref", "")
            assert not Path(ref).is_absolute(), f"{f.name}: {ref}"


def test_examples_validate_with_allow_missing_media():
    for f in EXAMPLES:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "shorts.py"), "validate", "--allow-missing-media", str(f)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


def test_missing_film_file_is_error_without_flag(tmp_path):
    # BAD case that used to pass: a film scene pointing to a file that does not exist was not checked at all
    raw = _film_plan()
    for s in raw["scenes"]:
        s["source"]["ref"] = "media/nope.mp4"
    issues = P.check(raw, tmp_path)
    assert any(i.code == "media_missing" and i.level == "error" for i in issues)
    relaxed = P.check(raw, tmp_path, allow_missing_media=True)
    assert not P.errors(relaxed)
    assert any(i.code == "media_missing" and i.level == "warn" for i in relaxed)


def test_flag_does_not_hide_other_errors(tmp_path):
    raw = _film_plan()
    raw["scenes"][0]["on_screen_text"] = "BAD \u2014 DASH"
    assert any(i.code == "dash" for i in P.errors(P.check(raw, tmp_path, allow_missing_media=True)))


def test_relative_ref_resolves_from_plan_folder(tmp_path):
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "film.mp4").write_bytes(b"x")
    raw = _film_plan()
    assert not [i for i in P.check(raw, tmp_path) if i.code == "media_missing"]


def test_absolute_path_warns(tmp_path):
    f = tmp_path / "film.mp4"
    f.write_bytes(b"x")
    raw = _film_plan()
    for s in raw["scenes"]:
        s["source"]["ref"] = str(f)
    assert any(i.code == "abs_path" for i in P.check(raw, tmp_path))
