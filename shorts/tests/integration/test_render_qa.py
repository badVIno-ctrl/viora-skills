"""Integration on offline fixtures: deterministic HTML capture, full render + QA, and the bad cases that MUST fail QA."""
from __future__ import annotations

import asyncio
import copy
import json
import subprocess

import numpy as np
import pytest

from shortskit.engine.render import render
from shortskit.meta.cover import cover_dir
from shortskit.meta.packaging import package_dir
from shortskit.qa.gate import run_gate
from shortskit.qa import frames as F

from conftest import FIX, mini_plan, write_plan


def failed(rep: dict) -> set[str]:
    return {c["id"] for c in rep["checks"] if c["status"] == "fail"}


def test_html_capture_is_deterministic(tmp_path):
    from playwright.async_api import async_playwright

    from shortskit.adapters.html import render_deterministic
    from shortskit.adapters.site import launch

    async def go(out):
        async with async_playwright() as pw:
            b = await launch(pw)
            hook = await render_deterministic(b, (FIX / "orbit.html").as_uri(), 270, 288, 10, 1.0, out)
            await b.close()
            return hook

    h1 = asyncio.run(go(tmp_path / "1.mp4"))
    asyncio.run(go(tmp_path / "2.mp4"))
    assert h1 == "vt"  # page uses rAF + performance.now: the time shim drives it
    a, _ = F.sample(tmp_path / "1.mp4", 10, 270, 288)
    b, _ = F.sample(tmp_path / "2.mp4", 10, 270, 288)
    assert a.shape == b.shape and np.abs(a.astype(int) - b.astype(int)).mean() < 1.0
    assert np.abs(a[0].astype(int) - a[-1].astype(int)).mean() > 1.0  # it moves


@pytest.mark.slow
def test_e2e_offline_plan_passes_qa_and_qr_decodes(tmp_path):
    out = tmp_path / "out"
    m = render(FIX / "plan.offline.json", out)
    assert (out / "offline-demo.mp4").exists() and (out / "captions.srt").exists()
    meta = package_dir(out)
    assert meta["ok"], meta["errors"]
    cov = cover_dir(out)
    assert len(cov["variants"]) == 6 and not cov["errors"], cov["errors"]
    rep = run_gate(out, strict=True)
    assert rep["passed"], [(c["id"], c["detail"]) for c in rep["checks"] if c["status"] == "fail"]
    qr = next(c for c in rep["checks"] if c["id"] == "qr")
    assert qr["data"]["decoded"][0]["got"] == ["https://t.me/VioraStudio"]
    assert m["layout"]["center_pct"] >= 55
    assert (out / "contact-1.png").exists()


def _render_qa(tmp_path, plan, force=False):
    p = write_plan(tmp_path, plan)
    out = tmp_path / "out"
    render(p, out, force=force)
    return run_gate(out)


def test_good_mini_passes(tmp_path):
    rep = _render_qa(tmp_path, mini_plan())
    assert rep["passed"], [(c["id"], c["detail"]) for c in rep["checks"] if c["status"] == "fail"]


def test_bad_narrow_center_fails(tmp_path):
    plan = mini_plan(layout={"mode": "three", "top": {"height_pct": 30, "source": "loop:auto"},
                             "bottom": {"height_pct": 22, "handle": "x", "links": ["https://t.me/x"]}})
    rep = _render_qa(tmp_path, plan, force=True)
    assert "layout" in failed(rep)


def test_bad_text_in_forbidden_zone_fails(tmp_path):
    plan = mini_plan()
    plan["captions"]["y"] = 1840  # bottom 672 px are covered by the YouTube UI
    rep = _render_qa(tmp_path, plan)
    assert "safe_zone" in failed(rep)


def test_bad_glow_fails(tmp_path):
    plan = mini_plan()
    plan["brand"]["effects"] = {"text_glow": True}
    rep = _render_qa(tmp_path, plan, force=True)
    assert "anti_slop" in failed(rep)
    det = next(c for c in rep["checks"] if c["id"] == "anti_slop")["detail"]
    assert "glow around graphics" in det  # caught on pixels, not only by the flag


def test_bad_gradient_plate_fails(tmp_path):
    plan = mini_plan()
    plan["brand"]["effects"] = {"gradient_plate": True}
    rep = _render_qa(tmp_path, plan, force=True)
    det = next(c for c in rep["checks"] if c["id"] == "anti_slop")["detail"]
    assert "gradient in graphics" in det


def test_bad_empty_panels_fail(tmp_path):
    plan = mini_plan(layout={"mode": "three", "top": {"height_pct": 20, "source": "color:#1A1A1A"},
                             "bottom": {"height_pct": 16}})
    rep = _render_qa(tmp_path, plan, force=True)
    det = next(c for c in rep["checks"] if c["id"] == "layout")["detail"]
    assert "top panel is empty" in det and "bottom panel is empty" in det


def test_bad_unreadable_qr_fails(tmp_path):
    plan = mini_plan()
    plan["layout"]["cta_in_center"] = [{"t": 3.0, "duration": 3.0, "kind": "qr", "url": "https://t.me/VioraStudio"}]
    p = write_plan(tmp_path, plan)
    out = tmp_path / "out"
    m = render(p, out)
    assert run_gate(out)["passed"]
    # damage the QR area (like a heavy blur / overlay would) and re-check the same manifest
    x0, y0, x1, y1 = m["overlays"][-1]["qr_box"]
    vid = out / m["video"]
    bad = out / "bad.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid), "-filter_complex",
                    f"[0:v]crop={x1 - x0}:{y1 - y0}:{x0}:{y0},boxblur=12:2[b];[0:v][b]overlay={x0}:{y0}",
                    "-c:a", "copy", str(bad)], check=True)
    bad.replace(vid)
    rep = run_gate(out)
    assert "qr" in failed(rep)


def test_bad_language_and_dash_fail(tmp_path):
    plan = mini_plan()
    plan["meta"]["language"] = "en"
    rep = _render_qa(tmp_path, plan)
    assert "text_rules" in failed(rep)


def test_layout_modes_render(tmp_path):
    """three / top_center / center_bottom / center_only all pass the centre rule."""
    for mode in ("three", "top_center", "center_bottom"):
        plan = mini_plan()
        plan["meta"]["name"] = f"mode-{mode.replace('_', '-')}"
        plan["layout"] = {"mode": mode, "top": {"source": "loop:auto"},
                          "bottom": {"handle": "VioraStudio", "links": ["https://t.me/VioraStudio"]}}
        d = tmp_path / mode
        d.mkdir()
        rep = _render_qa(d, plan)
        lay = next(c for c in rep["checks"] if c["id"] == "layout")
        assert lay["status"] != "fail", (mode, lay["detail"])
        assert lay["data"]["center_pct"] >= 55


def test_cli_validate_and_render_contract(tmp_path):
    """Public interface used by Viora Studio: `shorts.py render plan.json --out DIR` and `qa DIR`."""
    import sys

    from shortskit.config import skill_root

    p = write_plan(tmp_path, mini_plan())
    cli = str(skill_root() / "tools" / "shorts.py")
    assert subprocess.run([sys.executable, cli, "validate", str(p)]).returncode == 0
    assert subprocess.run([sys.executable, cli, "render", str(p), "--out", str(tmp_path / "o")]).returncode == 0
    assert subprocess.run([sys.executable, cli, "qa", str(tmp_path / "o")]).returncode == 0
    bad = copy.deepcopy(mini_plan())
    bad["scenes"][0]["say"] = "Привет всем, в этом видео"
    pb = write_plan(tmp_path, bad, "bad.json")
    assert subprocess.run([sys.executable, cli, "render", str(pb), "--out", str(tmp_path / "b")]).returncode == 2
    json.loads((tmp_path / "o" / "qa.json").read_text())


def _dull_panel(path):
    """Like the 1.0.0 loop: dark sky, a small sprite moving. Must now fail QA."""
    import subprocess

    import numpy as np

    pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1080x384",
                           "-r", "30", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    for i in range(300):
        f = np.full((384, 1080, 3), 16, np.uint8)
        x = (i * 9) % 1000
        f[300:350, x:x + 50] = 240
        f[360:384] = 70
        pr.stdin.write(f.tobytes())
    pr.stdin.close()
    pr.wait()
    return path


def test_bad_dull_top_panel_fails(tmp_path):
    vid = _dull_panel(tmp_path / "dull.mp4")
    plan = mini_plan()
    plan["layout"] = {"mode": "three", "top": {"source": str(vid)},
                      "bottom": {"handle": "VioraStudio", "links": ["https://t.me/VioraStudio"]}}
    rep = _render_qa(tmp_path, plan)
    lay = next(c for c in rep["checks"] if c["id"] == "layout")
    assert lay["status"] == "fail" and "top panel" in lay["detail"], lay["detail"]


def test_loop_top_panel_measured_in_qa(tmp_path):
    plan = mini_plan()
    plan["layout"] = {"mode": "three", "top": {"source": "loop:code"},
                      "bottom": {"handle": "VioraStudio", "links": ["https://t.me/VioraStudio"]}}
    rep = _render_qa(tmp_path, plan)
    top = next(c for c in rep["checks"] if c["id"] == "layout")["data"]["top"]
    assert top["loop"] == "code" and top["change_per_second_min"] >= 0.30 and top["dark_void"] <= 0.25, top


@pytest.mark.parametrize("plat", ["tiktok", "reels"])
def test_qa_safe_zone_per_platform(tmp_path, plat):
    """1.1.0 item 9: the QA gate uses the TikTok / Reels zones: engine placement passes, captions under the
    platform's bottom line fail."""
    good = mini_plan()
    good["meta"]["platforms"] = [plat]
    (tmp_path / "good").mkdir()
    rep = _render_qa(tmp_path / "good", good)
    sz = next(c for c in rep["checks"] if c["id"] == "safe_zone")
    assert sz["status"] == "pass" and sz["data"]["platforms"] == [plat], sz
    bad = mini_plan()
    bad["meta"]["platforms"] = [plat]
    bad["captions"]["y"] = 1300  # below 1260 (TikTok) / 1248 (Reels)
    (tmp_path / "bad").mkdir()
    rep = _render_qa(tmp_path / "bad", bad)
    assert "safe_zone" in failed(rep)
