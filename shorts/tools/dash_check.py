"""Long dashes (U+2014, U+2013) in user-facing skill texts. Python, so the check works in any locale
(grep with $'\u2014' silently matched nothing under LANG=C / POSIX)."""
import pathlib
import sys

roots = [pathlib.Path(p) for p in ("SKILL.md", "ROUTER.md", "reference", "tools/shortskit/meta")]
bad = []
for root in roots:
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in (".md", ".py", ".json", ".txt"))
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if "\u2014" in line or "\u2013" in line:
                bad.append(f"{f}:{i}: {line.strip()[:120]}")
print("\n".join(bad))
sys.exit(1 if bad else 0)
