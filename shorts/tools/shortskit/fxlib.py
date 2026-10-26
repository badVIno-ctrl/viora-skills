"""2.4 effects for code videos (HTML / canvas / p5.js / Three.js): vendored next to the scene with their licence.

  fx-get p5.brush --to DIR          bundled copy (assets/fx): MIT, standalone WebGL2 build dist/brush.js + llms.txt
  fx-get thinking-orbs --to DIR     bundled copy: MIT, 9 orb states on a 2D canvas, classic script orbs.js
  fx-get github.com/OWNER/REPO      any repo: licence, readme, package.json and built files (dist/, build/, lib/)
  fx-get npm:NAME[@VERSION]         any npm package: the published files

Everything lands in DIR/vendor/<name>/ with SOURCE.md (URL, licence, date, entry files). A repo without a
licence file is refused: code without a licence may not be shipped in a video page. The html adapter serves
pages with module scripts from their own folder, so vendor/ must sit inside the scene folder.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

from .config import asset
from .util import ShortsError

BUNDLED = {
    "p5.brush": {"url": "https://github.com/acamposuribe/p5.brush", "license": "MIT", "version": "2.2.4",
                 "entry": ["brush.js", "p5.brush.js"],
                 "use": "<script src=\"vendor/p5.brush/brush.js\"></script> -> global `brush` (standalone, WebGL2, no p5.js): "
                        "brush.load(canvas); brush.seed(n) each frame; brush.clear(bg) ... brush.render(). "
                        "p5.brush.js needs p5.js 2.x. Full API for the model: vendor/p5.brush/llms.txt"},
    "thinking-orbs": {"url": "https://github.com/Jakubantalik/Libraries.dev (npm thinking-orbs)", "license": "MIT",
                      "version": "0.3.2", "entry": ["orbs.js"],
                      "use": "<script src=\"vendor/thinking-orbs/orbs.js\"></script> -> window.ThinkingOrbs: "
                             "r = resolvePreset(state, 64); MODE_DRAWS[r.mode](ctx, 64, t * r.speed, dark, r.opts). "
                             "States: working searching solving listening connecting weaving composing breathing shaping"},
}
ALIASES = {"p5brush": "p5.brush", "brush": "p5.brush", "orbs": "thinking-orbs", "thinkingorbs": "thinking-orbs"}
PERMISSIVE = ("MIT", "Apache", "BSD", "ISC", "Zlib", "Unlicense", "CC0", "MPL")
KEEP_DIRS = ("dist", "build", "lib", "umd", "min")
KEEP_EXT = (".js", ".mjs", ".cjs", ".css", ".wasm", ".json", ".glsl", ".frag", ".vert", ".txt", ".md")
MAX_BYTES = 40 * 1024 * 1024
UA = {"User-Agent": "shorts-skill/2.4 (+fx-get)"}


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https hosts
            data = r.read(MAX_BYTES + 1)
    except Exception as e:  # noqa: BLE001
        raise ShortsError(f"download failed: {url}: {e}") from e
    if len(data) > MAX_BYTES:
        raise ShortsError(f"{url}: more than {MAX_BYTES // 1024 // 1024} MB, take the built file by hand")
    return data


def license_of(text: str) -> str:
    t = text[:3000]
    for name, pat in (("MIT", r"\bMIT License\b|Permission is hereby granted, free of charge"),
                      ("Apache-2.0", r"Apache License"), ("BSD", r"\bBSD\b|Redistribution and use in source and binary"),
                      ("ISC", r"\bISC\b"), ("MPL-2.0", r"Mozilla Public License"), ("Unlicense", r"unlicense|public domain"),
                      ("GPL", r"GNU GENERAL PUBLIC"), ("LGPL", r"GNU LESSER"), ("AGPL", r"GNU AFFERO"),
                      ("CC0", r"CC0")):
        if re.search(pat, t, re.I):
            return name
    return "unknown"


def _source_md(dest: Path, name: str, url: str, lic: str, version: str, entry: list[str], use: str = "") -> None:
    lines = [f"# {name}", "", f"- source: {url}", f"- licence: {lic} (file next to this one; keep it with the copy)",
             f"- version: {version or 'repository HEAD'}", f"- taken: {time.strftime('%Y-%m-%d')}",
             f"- entry: {', '.join(entry) if entry else 'see the folder'}"]
    if use:
        lines += ["", use]
    lines += ["", "Credit in the video description is a courtesy: \"Effect: " + name + " (" + lic + ")\"."]
    (dest / "SOURCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _entries(dest: Path) -> list[str]:
    files = [p for p in dest.rglob("*") if p.is_file() and p.suffix in (".js", ".mjs")]
    def rank(p: Path) -> tuple:
        n = p.name.lower()
        return (0 if p.parent.name in KEEP_DIRS else 1, 0 if ("umd" in n or n.endswith(".min.js")) else 1, len(str(p)))
    return [str(p.relative_to(dest)) for p in sorted(files, key=rank)[:6]]


def _check_license(dest: Path, name: str) -> str:
    lic_files = [p for p in dest.iterdir() if p.is_file() and re.match(r"(licen[cs]e|copying)", p.name, re.I)]
    if not lic_files:
        shutil.rmtree(dest, ignore_errors=True)
        raise ShortsError(f"{name}: no LICENSE file: code without a licence may not be used in a published video")
    lic = license_of(lic_files[0].read_text(encoding="utf-8", errors="ignore"))
    return lic


def from_github(spec: str, root: Path) -> dict:
    m = re.search(r"(?:github\.com[/:])?([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([\w./-]+))?/?$", spec.strip())
    if not m:
        raise ShortsError(f"not a GitHub repo: {spec} (github.com/OWNER/REPO)")
    owner, repo, ref = m.group(1), m.group(2), m.group(3) or "HEAD"
    data = _get(f"https://github.com/{owner}/{repo}/archive/{ref}.zip", timeout=120)
    dest = root / repo
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        top = z.namelist()[0].split("/")[0]
        for info in z.infolist():
            rel = info.filename[len(top) + 1:]
            if not rel or info.is_dir():
                continue
            parts = rel.split("/")
            low = parts[-1].lower()
            keep = (len(parts) == 1 and (re.match(r"(licen[cs]e|copying|readme|package\.json|llms\.txt)", low)))
            keep = keep or (parts[0] in KEEP_DIRS and low.endswith(KEEP_EXT) and not low.endswith(".map"))
            if keep:
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(info))
    lic = _check_license(dest, repo)
    version = ""
    pj = dest / "package.json"
    if pj.exists():
        try:
            version = json.loads(pj.read_text(encoding="utf-8")).get("version", "")
        except ValueError:
            pass
    ent = _entries(dest)
    _source_md(dest, repo, f"https://github.com/{owner}/{repo}", lic, version or ref, ent)
    return {"name": repo, "dir": str(dest), "license": lic, "entry": ent, "built": bool(ent),
            "note": None if ent else "no built files (dist/, build/, lib/): the repo needs a build step; pick its CDN file or npm:"}


def from_npm(spec: str, root: Path) -> dict:
    name = spec.split(":", 1)[1]
    ver = "latest"
    if "@" in name[1:]:
        name, ver = name[0] + name[1:].split("@", 1)[0], name[1:].split("@", 1)[1]
    meta = json.loads(_get(f"https://registry.npmjs.org/{name.replace('/', '%2F')}/{ver}"))
    data = _get(meta["dist"]["tarball"], timeout=120)
    dest = root / name.split("/")[-1]
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile() or m.name.endswith(".map"):
                continue
            rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            f = tf.extractfile(m)
            if f:
                out.write_bytes(f.read())
    lic = _check_license(dest, name)
    if lic == "unknown" and meta.get("license"):
        lic = str(meta["license"])
    ent = _entries(dest)
    _source_md(dest, name, f"https://www.npmjs.com/package/{name}", lic, meta.get("version", ver), ent)
    note = None
    if (meta.get("peerDependencies") or {}).get("react"):
        note = "React component: for a plain HTML scene use its framework-free part (engine / core file) or a CDN build"
    if not any(e.endswith(".js") and "umd" in e.lower() for e in ent):
        note = (note + "; " if note else "") + "ES modules: load with <script type=\"module\"> (the page is then served on 127.0.0.1)"
    return {"name": name, "dir": str(dest), "license": lic, "version": meta.get("version"), "entry": ent, "note": note}


def get(spec: str, to: str | Path = ".") -> dict:
    """Vendor an effect into <to>/vendor/<name>/ (bundled copy, GitHub repo or npm package)."""
    root = Path(to) / "vendor"
    root.mkdir(parents=True, exist_ok=True)
    key = ALIASES.get(spec.strip().lower(), spec.strip())
    if key in BUNDLED:
        b = BUNDLED[key]
        src = asset(f"fx/{key}")
        dest = root / key
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", ".*"))
        note = dest / "SOURCE.md"
        if note.exists():  # the bundled note lists the changes made to the copy: keep it, add the date and usage
            note.write_text(note.read_text(encoding="utf-8").rstrip() + f"\n\n- taken: {time.strftime('%Y-%m-%d')}\n"
                            f"- use: {b['use']}\n", encoding="utf-8")
        else:
            _source_md(dest, key, b["url"], b["license"], b["version"], b["entry"], b["use"])
        rep = {"name": key, "dir": str(dest), "license": b["license"], "entry": b["entry"], "use": b["use"], "bundled": True}
    elif spec.startswith("npm:"):
        rep = from_npm(spec, root)
    else:
        rep = from_github(spec, root)
    lic = str(rep.get("license") or "unknown")
    rep["license_ok"] = any(lic.upper().startswith(p.upper()) for p in PERMISSIVE)
    if not rep["license_ok"]:
        rep["warning"] = (f"licence {lic}: check it before publishing (GPL / AGPL code in a page is usually fine for a "
                          "rendered video, but read the terms; unknown = ask the author)")
    return rep


def list_bundled() -> list[dict]:
    return [{"name": k, "license": v["license"], "version": v["version"], "use": v["use"]} for k, v in BUNDLED.items()]
