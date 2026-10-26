"""Caption chunking report on real words: share of one-word chunks, cut-off function words, split names/numbers.

python3 tools/caption_stats.py demos/*/manifest.json   # re-chunks the words of each demo with the current rules
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shortskit.engine import brand as B  # noqa: E402
from shortskit.engine import captions as CP  # noqa: E402
from shortskit.engine import layout as L  # noqa: E402


def rechunk(manifest_path: Path) -> tuple[list[CP.Chunk], str]:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = json.loads((manifest_path.parent / "plan.resolved.json").read_text(encoding="utf-8"))
    words = [w for c in m["captions"]["chunks"] for w in c["words"]]
    lang = m.get("language", "ru")
    brand = B.resolve(plan["brand"], None, lang)
    lay = L.compute(plan["layout"], m["platforms"])
    return CP.build(words, brand, lay, plan.get("captions", {}), lang), lang


def main(paths: list[str]) -> int:
    tot = one = 0
    for p in paths:
        try:
            chunks, lang = rechunk(Path(p))
        except (KeyError, FileNotFoundError):
            continue
        if not chunks:
            continue
        rep = CP.chunk_report(chunks, lang)
        tot += rep["chunks"]
        one += rep["one_word"]
        print(f"{p}: {rep['chunks']} chunks, one-word {rep['one_word_share']:.0%}, issues {rep['issues']}")
        print("   " + " | ".join(c.text for c in chunks))
    if tot:
        print(f"TOTAL one-word {one}/{tot} = {one / tot:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
