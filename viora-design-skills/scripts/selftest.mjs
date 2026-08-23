#!/usr/bin/env node
/**
 * Виора Design Skills / self-test
 *
 *   node selftest.mjs
 *
 * Proves two things before you trust the toolchain:
 *   1. every headline rule actually fires on a deliberately bad fixture
 *   2. the shipped starter and token file pass with zero errors
 *
 * viora-allow-file: this script embeds a deliberately bad fixture on purpose,
 * so the linter must not grade it as product code.
 *
 * Run it after editing check.mjs or the assets. Exit 1 means the skill itself
 * is broken, not the project you were designing.
 */

import { spawnSync } from "node:child_process"
import { mkdtempSync, writeFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const skill = join(here, "..")
const check = join(here, "check.mjs")

const BAD_HTML = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Fixture</title></head>
<body>
  <p class="uppercase tracking-widest text-sm">Analytics platform</p>
  <h1 class="bg-gradient-to-r from-violet-500 to-blue-500 bg-clip-text">Unlock Powerful Insights Today</h1>
  <p>Lorem ipsum dolor sit amet, a seamless platform for Acme Inc.</p>
  <p>One clause \u2014 then another.</p>
  <img src="/hero.png" alt="hero">
  <div onclick="go()">Open</div>
  <button style="transition: all .3s">Get Started</button>
  <div class="grid grid-cols-3">
    <div class="rounded-xl border p-6 shadow-sm">One</div>
    <div class="rounded-xl border p-6 shadow-sm">Two</div>
    <div class="rounded-xl border p-6 shadow-sm">Three</div>
  </div>
</body>
</html>
`

const BAD_CSS = `.card { box-shadow: 0 4px 6px rgba(0, 0, 0, .1); gap: 13px }
.hero { filter: blur(60px) }
.title { font-size: 3.5rem }
a:focus { outline: none }
`

const MUST_FIRE = [
	"eyebrow",
	"ai-gradient",
	"gradient-text",
	"title-case-heading",
	"lorem",
	"slop-names",
	"filler-words",
	"em-dash",
	"img-no-dimensions",
	"div-click-target",
	"transition-all",
	"card-monotony",
	"framework-default-shadow",
	"off-rhythm-space",
	"hero-mesh-blob",
	"display-no-tracking",
	"focus-none",
	"tokens-missing",
]

const json = (args) => {
	const r = spawnSync(process.execPath, [check, ...args, "--json"], { encoding: "utf8" })
	try {
		return JSON.parse(r.stdout)
	} catch {
		console.error(r.stdout || r.stderr)
		return null
	}
}

let failures = 0
const tell = (ok, line) => {
	if (!ok) failures++
	console.log(`${ok ? "pass" : "FAIL"}  ${line}`)
}

/* 1. the bad fixture must trip every headline rule ----------------------- */
const dir = mkdtempSync(join(tmpdir(), "viora-selftest-"))
try {
	writeFileSync(join(dir, "bad.html"), BAD_HTML)
	writeFileSync(join(dir, "bad.css"), BAD_CSS)
	const out = json([dir])
	if (!out) {
		tell(false, "checker did not return JSON on the fixture")
	} else {
		const fired = new Set(out.findings.map((f) => f.id))
		for (const id of MUST_FIRE) tell(fired.has(id), `rule fires: ${id}`)
		tell(out.errors > 0, `fixture reports errors (${out.errors})`)
	}
} finally {
	rmSync(dir, { recursive: true, force: true })
}

/* 2. the shipped assets must be clean ------------------------------------ */
const assets = json([join(skill, "assets", "starter.html"), join(skill, "assets", "tokens.css")])
if (!assets) {
	tell(false, "checker did not return JSON on the assets")
} else {
	tell(assets.errors === 0, `assets/starter.html + assets/tokens.css: ${assets.errors} errors`)
	if (assets.warnings > 0) {
		console.log(`      note: ${assets.warnings} warning(s) in the shipped assets`)
		for (const f of assets.findings) console.log(`      ${f.id} ${f.file}:${f.line}`)
	}
}

/* 3. contrast must resolve the token file -------------------------------- */
const contrast = spawnSync(process.execPath, [join(here, "contrast.mjs"), join(skill, "assets", "tokens.css")], {
	encoding: "utf8",
})
tell(contrast.status === 0, `contrast.mjs on assets/tokens.css exits ${contrast.status}`)
if (contrast.status !== 0) console.log(contrast.stdout.split("\n").slice(-14).join("\n"))

console.log("\n" + "-".repeat(66))
console.log(failures === 0 ? "selftest: all checks passed" : `selftest: ${failures} check(s) failed`)
console.log("-".repeat(66))
process.exit(failures === 0 ? 0 : 1)
