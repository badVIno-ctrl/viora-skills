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

/* 12. the 4.2.0 rules: each one fires on a positive sample and stays quiet on
   the negative one. A rule that cannot tell them apart is not a rule. --------- */

const CRAFT_CSS = `.poster { box-shadow: 6px 6px 0 var(--ink) }
.field { background: repeating-linear-gradient(45deg, var(--surface) 0 10px, var(--canvas) 10px 20px) }
.ghost { border: 1px solid var(--hairline); box-shadow: 0 10px 30px rgba(17, 17, 20, 0.08) }
.shout { letter-spacing: -0.06em }
.deck { box-shadow: 0 10px 20px rgba(0, 0, 0, 0.25) }
:root { --font-display: system-ui; }
`

const CRAFT_HTML = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Craft fixture</title></head>
<body>
  <svg><filter id="grain"><feTurbulence baseFrequency="0.8" /></filter></svg>
  <button>\u2192</button>
  <footer>
    <div class="col"><a href="/a">A</a></div>
    <div class="col"><a href="/b">B</a></div>
    <div class="col"><a href="/c">C</a></div>
    <div class="col"><a href="/d">D</a></div>
    <a href="https://twitter.com/x">Twitter</a>
  </footer>
</body>
</html>
`

const CRAFT_CLEAN_CSS = `.card { box-shadow: 0 8px 24px -6px hsl(220 20% 10% / 0.10); border-radius: var(--radius-md) }
.title { letter-spacing: -0.03em }
.field { background: var(--surface-2); border-top: 1px solid var(--hairline) }
:root { --font-display: "Manrope", ui-sans-serif, system-ui, sans-serif; }
`

const CRAFT_MUST_FIRE = [
	"offset-shadow",
	"stripe-bg",
	"ghost-card",
	"over-tracking",
	"shadow-opacity",
	"system-display-face",
	"svg-grain",
	"glyph-icon",
	"stock-footer",
]

const craftDir = mkdtempSync(join(tmpdir(), "viora-craft-"))
try {
	writeFileSync(join(craftDir, "bad.css"), CRAFT_CSS)
	writeFileSync(join(craftDir, "bad.html"), CRAFT_HTML)
	const out = json([craftDir])
	if (!out) {
		tell(false, "checker did not return JSON on the craft fixture")
	} else {
		const fired = new Set(out.findings.map((f) => f.id))
		for (const id of CRAFT_MUST_FIRE) tell(fired.has(id), `rule fires: ${id}`)
	}
} finally {
	rmSync(craftDir, { recursive: true, force: true })
}

const craftCleanDir = mkdtempSync(join(tmpdir(), "viora-craft-ok-"))
try {
	writeFileSync(join(craftCleanDir, "ok.css"), CRAFT_CLEAN_CSS)
	const out = json([craftCleanDir])
	const fired = out ? new Set(out.findings.map((f) => f.id)) : new Set(CRAFT_MUST_FIRE)
	const noisy = CRAFT_MUST_FIRE.filter((id) => fired.has(id))
	tell(noisy.length === 0, noisy.length ? `craft rules fire on clean CSS: ${noisy.join(", ")}` : "craft rules stay quiet on clean CSS")
} finally {
	rmSync(craftCleanDir, { recursive: true, force: true })
}

/* the template rhythm and the KPI wall need a whole page to recognise */
const TEMPLATE_HTML = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Template fixture</title></head>
<body>
  <section class="hero"><h1>Ship the release</h1></section>
  <section class="grid grid-cols-3">
    <div class="rounded-xl border p-6">One</div>
    <div class="rounded-xl border p-6">Two</div>
    <div class="rounded-xl border p-6">Three</div>
  </section>
  <section class="cta"><a href="/start">Start</a></section>
  <section class="numbers">
    <div><span>99%</span><span>uptime last quarter</span></div>
    <div><span>340</span><span>workspaces running</span></div>
    <div><span>12</span><span>integrations shipped</span></div>
    <div><span>3</span><span>minutes to first draft</span></div>
  </section>
</body>
</html>
`

const TEMPLATE_CLEAN_HTML = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Shaped fixture</title></head>
<body>
  <section class="hero"><h1>Ship the release</h1></section>
  <section class="rows">
    <div class="row"><span>Draft</span><p>Written the moment the pull request merges.</p></div>
    <div class="row"><span>Review</span><p>One approver, in the tool they already use.</p></div>
  </section>
  <footer><p>Kvartal, Riga. Contact, legal, 2026.</p></footer>
</body>
</html>
`

const tmplDir = mkdtempSync(join(tmpdir(), "viora-tmpl-"))
try {
	writeFileSync(join(tmplDir, "page.html"), TEMPLATE_HTML)
	const out = json([tmplDir])
	const fired = out ? new Set(out.findings.map((f) => f.id)) : new Set()
	tell(fired.has("template-rhythm"), "rule fires: template-rhythm")
	tell(fired.has("kpi-clones"), "rule fires: kpi-clones")
} finally {
	rmSync(tmplDir, { recursive: true, force: true })
}

const tmplOkDir = mkdtempSync(join(tmpdir(), "viora-tmpl-ok-"))
try {
	writeFileSync(join(tmplOkDir, "page.html"), TEMPLATE_CLEAN_HTML)
	const out = json([tmplOkDir])
	const fired = out ? new Set(out.findings.map((f) => f.id)) : new Set(["template-rhythm"])
	const noisy = ["template-rhythm", "kpi-clones", "stock-footer"].filter((id) => fired.has(id))
	tell(noisy.length === 0, noisy.length ? `structure rules fire on a shaped page: ${noisy.join(", ")}` : "structure rules stay quiet on a shaped page")
} finally {
	rmSync(tmplOkDir, { recursive: true, force: true })
}

/* the new interface rules ------------------------------------------------- */

const WIG_CRAFT_HTML = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Interface fixture</title>
<style>
  .head { position: sticky; top: 0 }
  .btn:hover { background: var(--accent) }
  .a { will-change: transform }
  .b { will-change: opacity }
  .c { will-change: transform }
  .d { will-change: filter }
</style>
</head>
<body>
  <header class="head"><a href="#pricing">Pricing</a></header>
  <div class="drawer is-closed"><a href="/docs">Docs</a></div>
  <h1>Release notes that ship themselves</h1>
  <h2 id="pricing">Pricing</h2>
  <input type="tel" name="phone" autocomplete="tel" />
</body>
</html>
`

const WIG_CRAFT_CLEAN = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Interface fixture</title>
<style>
  .head { position: sticky; top: 0 }
  [id] { scroll-margin-top: 5rem }
  h1, h2 { text-wrap: balance }
  .btn:hover, .btn:focus-visible { background: var(--accent) }
  .btn:disabled { opacity: 0.5 }
</style>
</head>
<body>
  <header class="head"><a href="#pricing">Pricing</a></header>
  <div class="drawer is-closed" inert><a href="/docs">Docs</a></div>
  <h1>Release notes that ship themselves</h1>
  <h2 id="pricing">Pricing</h2>
  <input type="tel" name="phone" inputmode="tel" enterkeyhint="next" autocomplete="tel" />
</body>
</html>
`

const WIG_CRAFT_MUST_FIRE = [
	"overlay-inert",
	"input-mode",
	"anchor-scroll-margin",
	"will-change-sprinkle",
	"heading-wrap",
	"component-states",
]

const wigCraftDir = mkdtempSync(join(tmpdir(), "viora-wig-craft-"))
try {
	writeFileSync(join(wigCraftDir, "bad.html"), WIG_CRAFT_HTML)
	const out = readJson([join(here, "wig.mjs"), wigCraftDir, "--json"])
	if (!out) {
		tell(false, "wig.mjs did not return JSON on the craft fixture")
	} else {
		const fired = new Set(out.findings.map((f) => f.id))
		for (const id of WIG_CRAFT_MUST_FIRE) tell(fired.has(id), `wig rule fires: ${id}`)
	}
} finally {
	rmSync(wigCraftDir, { recursive: true, force: true })
}

const wigCleanDir = mkdtempSync(join(tmpdir(), "viora-wig-ok-"))
try {
	writeFileSync(join(wigCleanDir, "ok.html"), WIG_CRAFT_CLEAN)
	const out = readJson([join(here, "wig.mjs"), wigCleanDir, "--json"])
	const fired = out ? new Set(out.findings.map((f) => f.id)) : new Set(WIG_CRAFT_MUST_FIRE)
	const noisy = WIG_CRAFT_MUST_FIRE.filter((id) => fired.has(id))
	tell(noisy.length === 0, noisy.length ? `interface rules fire on the fixed page: ${noisy.join(", ")}` : "interface rules stay quiet once fixed")
} finally {
	rmSync(wigCleanDir, { recursive: true, force: true })
}

/* 13. the gate conductor: start, pass, status, and the verdict it refuses --- */

const gateDir = mkdtempSync(join(tmpdir(), "viora-gate-"))
try {
	const gate = join(here, "gate.mjs")
	const start = spawnSync(process.execPath, [gate, "start", "NEW", "LAND", "FILE", "FULL"], { cwd: gateDir, encoding: "utf8" })
	tell(start.status === 0 && /NEW\/LAND\/FILE/.test(start.stdout), "gate.mjs start records the run")

	const passed = spawnSync(process.execPath, [gate, "pass", "G0", "route: NEW/LAND/FILE"], { cwd: gateDir, encoding: "utf8" })
	tell(passed.status === 0 && /G0 route/.test(passed.stdout), "gate.mjs pass records a marker")

	const status = spawnSync(process.execPath, [gate, "status", "--json"], { cwd: gateDir, encoding: "utf8" })
	let run = null
	try {
		run = JSON.parse(status.stdout)
	} catch {
		/* left null, reported below */
	}
	tell(
		Boolean(run) && run.gates && run.gates.G0 && run.gates.G0.marker === "route: NEW/LAND/FILE",
		run && run.gates && run.gates.G0 ? "gate.mjs status round trips the marker" : "gate.mjs status lost the marker",
	)
	tell(
		Boolean(run) && Array.isArray(run.missing) && run.missing.includes("G6"),
		run && run.missing ? `gate.mjs names what is still owed (${run.missing.join(" ")})` : "gate.mjs reported no missing gates",
	)

	const refused = spawnSync(process.execPath, [join(here, "verify.mjs"), ".", "--no-shots"], { cwd: gateDir, encoding: "utf8" })
	const refusedOut = `${refused.stdout || ""}${refused.stderr || ""}`
	tell(
		refused.status === 2 && /missing G1/.test(refusedOut) && !/mechanical floor passed/.test(refusedOut),
		refused.status === 2 ? "verify.mjs refuses a verdict while gates are missing" : `verify.mjs printed a verdict anyway (exit ${refused.status})`,
	)
} finally {
	rmSync(gateDir, { recursive: true, force: true })
}

/* 14. PRODUCT.md gates the numbers in the copy --------------------------- */

const productDir = mkdtempSync(join(tmpdir(), "viora-product-"))
try {
	writeFileSync(
		join(productDir, "PRODUCT.md"),
		"# PRODUCT.md\n\n| Claim | Wording | Source |\n|---|---|---|\n| draft speed | 3 min | telemetry |\n| adoption | 340 workspaces | billing |\n| close rate | 92% | telemetry |\n",
	)
	writeFileSync(
		join(productDir, "page.html"),
		'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>Claims</title></head><body>\n<p>92% of reviews close the same day.</p>\n<p>Teams ship 7x more release notes.</p>\n</body></html>\n',
	)
	const r = spawnSync(process.execPath, [check, ".", "--json"], { cwd: productDir, encoding: "utf8" })
	let out = null
	try {
		out = JSON.parse(r.stdout)
	} catch {
		/* reported below */
	}
	const hits = out ? out.findings.filter((f) => f.id === "unsourced-number") : []
	tell(hits.length === 1, hits.length === 1 ? "rule fires: unsourced-number, once, on the number PRODUCT.md does not carry" : `unsourced-number fired ${hits.length} time(s)`)
} finally {
	rmSync(productDir, { recursive: true, force: true })
}

console.log("\n" + "-".repeat(66))
console.log(failures === 0 ? "selftest: all checks passed" : `selftest: ${failures} check(s) failed`)
console.log("-".repeat(66))
process.exit(failures === 0 ? 0 : 1)
