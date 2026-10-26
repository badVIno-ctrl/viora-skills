"""Item 3 (1.1.0): `all` exit code = QA result. Cover/meta problems are warnings, not exit 1."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def cli(monkeypatch):
    spec = importlib.util.spec_from_file_location("shorts_cli", ROOT / "tools" / "shorts.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "cmd_render", lambda a: 0)
    monkeypatch.setattr(m, "cmd_meta", lambda a: 0)
    return m


def _run(cli, monkeypatch, tmp_path, qa_passed: bool, cover_errors: list[str]) -> tuple[int, dict]:
    import shortskit.meta.cover as C
    import shortskit.qa.gate as G

    monkeypatch.setattr(C, "cover_dir", lambda d, **k: {"variants": [], "errors": cover_errors})
    monkeypatch.setattr(G, "run_gate", lambda d, strict=False: {"passed": qa_passed, "summary": "x"})
    rc = cli.main(["all", "plan.json", "--out", str(tmp_path)])
    return rc, json.loads((tmp_path / "all.json").read_text())


def test_all_qa_passed_cover_weak_is_exit_0(cli, monkeypatch, tmp_path, capsys):
    # BAD case from 1.0.0 reports: QA PASSED, covers B/C "weak silhouette" -> exit code 1
    rc, rep = _run(cli, monkeypatch, tmp_path, True, ["cover-B-minimal-9x16.png: weak silhouette (blurred grey std 20)"])
    assert rc == 0 and rep["qa_passed"]
    assert "WARN cover" in capsys.readouterr().out


def test_all_qa_failed_is_exit_1(cli, monkeypatch, tmp_path):
    rc, rep = _run(cli, monkeypatch, tmp_path, False, [])
    assert rc == 1 and not rep["qa_passed"]


def test_all_cover_crash_is_warning(cli, monkeypatch, tmp_path):
    import shortskit.meta.cover as C
    import shortskit.qa.gate as G

    def boom(d, **k):
        raise RuntimeError("no font")
    monkeypatch.setattr(C, "cover_dir", boom)
    monkeypatch.setattr(G, "run_gate", lambda d, strict=False: {"passed": True, "summary": "x"})
    assert cli.main(["all", "plan.json", "--out", str(tmp_path)]) == 0
