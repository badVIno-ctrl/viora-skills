#!/usr/bin/env node
/**
 * Виора Design Skills / self-test
 *
 *   node selftest.mjs
 *
 * Proves the toolchain before you trust it:
 *   1. every headline craft rule fires on a deliberately bad fixture
 *   2. the shipped starter and token file pass with zero errors
 *   3. contrast.mjs resolves the token file and every required pair passes
 *   4. wig.mjs fires on interface defects and stays quiet on the shipped assets
 *   5. pick.mjs answers a catalog query, in English and in Russian
 *   6. lane.mjs routes known model names to the right lane
 *   7. every rule in both linters has an explanation entry
 *   8. every palette in the library still measures clean
 *   9. the block library lints clean against the token contract
 *  10. ru.mjs fires on Russian defects and stays quiet on the shipped docs
 *  11. score.mjs measures its four axes and install.mjs survives a dry run
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

/* 4. the interface linter must fire, and must stay quiet on the assets --- */
const WIG_BAD = `export default function Panel({ q, id }) {
  const when = d.getMonth() + 1 + "/" + d.getDate()
  return (
    <form>
      <input value={q} type="email" onPaste={(e) => e.preventDefault()} />
      <button onClick={() => deleteRow(id)}>Delete</button>
      <a onClick={go}>Open</a>
      <iframe src="/embed" />
    </form>
  )
}
`

const WIG_MUST_FIRE = [
	"paste-blocked",
	"value-no-onchange",
	"hand-date",
	"link-no-href",
	"iframe-no-title",
	"button-no-type",
	"destructive-bare",
]

const readJson = (args) => {
	const r = spawnSync(process.execPath, args, { encoding: "utf8" })
	try {
		return JSON.parse(r.stdout)
	} catch {
		return null
	}
}

const wigDir = mkdtempSync(join(tmpdir(), "viora-wig-"))
try {
	writeFileSync(join(wigDir, "bad.tsx"), WIG_BAD)
	const out = readJson([join(here, "wig.mjs"), wigDir, "--json"])
	if (!out) {
		tell(false, "wig.mjs did not return JSON on the fixture")
	} else {
		const fired = new Set(out.findings.map((f) => f.id))
		for (const id of WIG_MUST_FIRE) tell(fired.has(id), `wig rule fires: ${id}`)
		tell(out.errors > 0, `wig fixture reports errors (${out.errors})`)
	}
} finally {
	rmSync(wigDir, { recursive: true, force: true })
}

const wigAssets = readJson([
	join(here, "wig.mjs"),
	join(skill, "assets", "starter.html"),
	join(skill, "assets", "tokens.css"),
	"--json",
])
tell(
	Boolean(wigAssets) && wigAssets.errors === 0 && wigAssets.warnings === 0,
	wigAssets
		? `wig.mjs on shipped assets: ${wigAssets.errors} errors, ${wigAssets.warnings} warnings`
		: "wig.mjs did not return JSON on the assets",
)

/* 5. the catalog must answer, in both languages ------------------------- */
const rowsIn = (out, domain) =>
	out && out.results && Array.isArray(out.results[domain]) ? out.results[domain].length : 0

const pickEn = readJson([join(here, "pick.mjs"), "fintech dashboard trust", "--domain", "palette", "-n", "2", "--json"])
tell(rowsIn(pickEn, "palette") > 0, `pick.mjs returns palette rows (${rowsIn(pickEn, "palette")})`)

const pickRu = readJson([join(here, "pick.mjs"), "\u043b\u0435\u043d\u0434\u0438\u043d\u0433 \u0430\u0433\u0435\u043d\u0442\u0441\u0442\u0432\u0430 \u043f\u0440\u0435\u043c\u0438\u0430\u043b\u044c\u043d\u044b\u0439", "--domain", "landing", "-n", "1", "--json"])
tell(rowsIn(pickRu, "landing") > 0, `pick.mjs answers a Russian query (${rowsIn(pickRu, "landing")})`)

const pickCyr = readJson([join(here, "pick.mjs"), "editorial long read", "--domain", "cyrillic", "-n", "2", "--json"])
tell(rowsIn(pickCyr, "cyrillic") > 0, `pick.mjs returns Cyrillic pairings (${rowsIn(pickCyr, "cyrillic")})`)

/* 6. the lane router must decide without asking the model anything ------ */
const runText = (args) => spawnSync(process.execPath, args, { encoding: "utf8" })
const laneScript = join(here, "lane.mjs")
const laneOf = (model) => {
	const asJson = readJson([laneScript, "--model", model, "--json"])
	if (asJson && typeof asJson.lane === "string") return asJson.lane.toUpperCase()
	const r = runText([laneScript, "--model", model])
	const out = `${r.stdout || ""}${r.stderr || ""}`
	const first = out.split("\n").find((l) => /LITE|FULL/.test(l)) || ""
	return /LITE/.test(first) ? "LITE" : /FULL/.test(first) ? "FULL" : "none"
}
tell(laneOf("claude-sonnet-4.5") === "FULL", "lane.mjs sends claude-sonnet-4.5 to FULL")
tell(laneOf("gemini-2.5-flash") === "LITE", "lane.mjs sends gemini-2.5-flash to LITE")
tell(laneOf("someco-tiny-8b") === "LITE", "lane.mjs sends an unknown small model to LITE")

/* 7. a rule nobody can explain is a rule nobody will respect ------------ */
const cov = runText([join(here, "explain.mjs"), "--coverage"])
const covOut = `${cov.stdout || ""}${cov.stderr || ""}`
const covPairs = [...covOut.matchAll(/(\d+) rules, (\d+) entries/g)]
tell(cov.status === 0, cov.status === 0 ? "explain.mjs --coverage exits clean" : `explain.mjs --coverage exit ${cov.status}`)
tell(
	covPairs.length >= 2 && covPairs.every((m) => m[1] === m[2]),
	covPairs.length ? `every rule has an entry (${covPairs.map((m) => `${m[1]}/${m[2]}`).join(", ")})` : "explain.mjs printed no coverage",
)

/* 8. the palette library must still measure clean ----------------------- */
const sweep = runText([join(here, "palettes.mjs")])
const sweepOut = `${sweep.stdout || ""}${sweep.stderr || ""}`
tell(
	sweep.status === 0 && /all \d+ palettes pass/.test(sweepOut),
	sweep.status === 0 ? (sweepOut.match(/all \d+ palettes pass/) || ["palette sweep clean"])[0] : `palette sweep exit ${sweep.status}`,
)

/* 9. blocks must lint clean, but only together with the token file ------ */
const blocks = readJson([check, join(skill, "assets", "blocks"), join(skill, "assets", "tokens.css"), "--json"])
tell(
	Boolean(blocks) && blocks.errors === 0 && blocks.warnings === 0,
	blocks ? `block library lints: ${blocks.errors} errors, ${blocks.warnings} warnings` : "check.mjs returned no JSON for the blocks",
)

/* 10. Russian typography, both directions ------------------------------- */
const RU_BAD = [
	"<p>\u0426\u0435\u043d\u0430 - 5000 \u0440\u0443\u0431. \u0438 3 \u043a\u0433 \u0433\u0440\u0443\u0437\u0430...</p>",
	'<p>"\u041a\u043b\u0438\u043d\u0438\u043a\u0430" \u043d\u0430 \u0443\u043b\u0438\u0446\u0435 \u041b\u0435\u043d\u0438\u043d\u0430</p>',
	"<p>\u0421\u043a\u0438\u0434\u043a\u0430 \u0434\u043b\u044f \u0432\u0441\u0435\u0445 ,\u043a\u0442\u043e \u043f\u0440\u0438\u0434\u0451\u0442</p>",
	"<p>\u041enline \u0437\u0430\u043f\u0438\u0441\u044c</p>",
].join("\n")
const RU_MUST_FIRE = ["quotes-straight", "hyphen-as-dash", "mixed-alphabet", "space-before-punct"]
const ruDir = mkdtempSync(join(tmpdir(), "viora-ru-"))
try {
	writeFileSync(join(ruDir, "bad.html"), RU_BAD)
	const out = readJson([join(here, "ru.mjs"), ruDir, "--json"])
	if (!out) {
		tell(false, "ru.mjs did not return JSON on the fixture")
	} else {
		const fired = new Set(out.findings.map((f) => f.id))
		for (const id of RU_MUST_FIRE) tell(fired.has(id), `ru rule fires: ${id}`)
	}
} finally {
	rmSync(ruDir, { recursive: true, force: true })
}
const ruDocs = runText([join(here, "ru.mjs"), skill])
tell(ruDocs.status === 0, ruDocs.status === 0 ? "ru.mjs stays quiet on the shipped docs" : `ru.mjs flags the skill's own docs (exit ${ruDocs.status})`)

/* 11. the score and the installer ---------------------------------------- */
const score = readJson([join(here, "score.mjs"), join(skill, "assets", "starter.html"), "--json"])
tell(
	Boolean(score) && Array.isArray(score.axes) && score.axes.length === 4,
	score && score.axes ? `score.mjs reports ${score.axes.length} mechanical axes` : "score.mjs returned no axes",
)
tell(
	Boolean(score) && score.measured >= 16,
	score ? `the shipped starter measures ${score.measured}/20` : "score.mjs produced no measurement",
)

const installDir = mkdtempSync(join(tmpdir(), "viora-install-"))
try {
	const dry = runText([join(here, "install.mjs"), "--into", installDir, "--dry-run"])
	const dryOut = `${dry.stdout || ""}${dry.stderr || ""}`
	tell(
		dry.status === 0 && /AGENTS\.md/.test(dryOut),
		dry.status === 0 ? "install.mjs dry run lists its targets" : `install.mjs dry run exit ${dry.status}`,
	)
} finally {
	rmSync(installDir, { recursive: true, force: true })
}

console.log("\n" + "-".repeat(66))
console.log(failures === 0 ? "selftest: all checks passed" : `selftest: ${failures} check(s) failed`)
console.log("-".repeat(66))
process.exit(failures === 0 ? 0 : 1)
