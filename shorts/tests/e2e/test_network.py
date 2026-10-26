"""Network tests (sites, edge-tts, YouTube). Skipped unless SHORTS_NETWORK=1."""
import pytest

from shortskit.config import skill_root
from shortskit.engine.render import render
from shortskit.meta.packaging import package_dir
from shortskit.qa.gate import run_gate

pytestmark = pytest.mark.network


def test_plan_example_sites_e2e(tmp_path):
    """schema/plan.example.json: two real sites, real TTS -> QA passes and the QR decodes."""
    out = tmp_path / "a"
    m = render(skill_root() / "schema" / "plan.example.json", out)
    assert not [s for s in m["scenes"] if s["skipped"]]
    package_dir(out)
    rep = run_gate(out, strict=True)
    assert rep["passed"], [(c["id"], c["detail"]) for c in rep["checks"] if c["status"] == "fail"]


def test_edge_tts_word_boundaries():
    from shortskit.engine.tts import synth

    s = synth("Два бесплатных сайта, и оба пригодятся.", lang="ru", engine="edge", speed=1.0)
    assert not s.estimated and len(s.words) == 6 and s.duration > 1.5


def test_site_probe_detects_page():
    import asyncio

    from shortskit.adapters.site import probe

    r = asyncio.run(probe("https://www.cadlookup.com/", tmp := __import__("pathlib").Path("/tmp/shorts-probe")))
    assert r.get("status") == 200 and not r.get("blocked") and r.get("elements")
    del tmp


def test_youtube_search_and_heatmap():
    """YouTube may ask server IPs to sign in; then pass SHORTS_YTDLP_COOKIES (no bypass)."""
    from shortskit.adapters.media import search, video_meta
    from shortskit.util import ShortsError

    res = search("big buck bunny blender", 3)
    assert res and res[0]["id"]
    try:
        meta = video_meta("https://www.youtube.com/watch?v=aqz-KE-bpKQ")
    except ShortsError as e:
        if "Sign in to confirm" in str(e):
            pytest.skip("YouTube asks this IP to sign in: set SHORTS_YTDLP_COOKIES")
        raise
    assert meta["duration"] > 600 and meta.get("heatmap")
