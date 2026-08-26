#!/usr/bin/env node

/**
 * score.mjs - the four axes a script can honestly score
 *
 *   node scripts/score.mjs <paths>
 *   node scripts/score.mjs src --json
 *
 * evals/rubric.md has eight axes. Four of them are measurements, and a
 * measurement should never be a matter of opinion, so they are computed here:
 * craft floor, colour, typography, states. The other four stay blank, because a
 * script cannot see whether a page has a point of view.
 *
 * This is a report, not a gate. verify.mjs is the gate.
 */

import { spawnSync } from "node:child_process"
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { dirname, extname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const argv = process.argv.slice(2)
const asJson = argv.includes("--json")
const targets = argv.filter((a) => !a.startsWith("--"))
if (targets.length === 0) targets.push(".")

const SKIP = new Set([
	"node_modules", ".git", "dist", "build", "out", "coverage", ".next", ".nuxt",
	".svelte-kit", ".astro", ".turbo", ".vercel", ".cache", ".viora-shots", "data",
])
const STYLEISH = new Set([".css", ".scss", ".less", ".html", ".htm"])

const run = (script, args) => {
	const r = spawnSync(process.execPath, [join(HERE, script), ...args], { encoding: "utf8" })
	return { code: r.status ?? 1, out: `${r.stdout || ""}${r.stderr || ""}` }
}
const runJson = (script, args) => {
	const { out } = run(script, [...args, "--json"])
	try {
		return JSON.parse(out.slice(out.indexOf("{")))
	} catch {
		return null
	}
}

/* ------------------------------------------------------------- measurements */

const check = runJson("check.mjs", targets) || { errors: 0, warnings: 0, findings: [] }
const wig = runJson("wig.mjs", targets) || { errors: 0, warnings: 0, findings: [] }

const all = [...(check.findings || []), ...(wig.findings || [])].map((f) => ({
	id: f.id,
	sev: f.sev || f.level || "warn",
	file: f.file,
	line: f.line,
	msg: f.msg,
}))
const hit = (...ids) => all.filter((f) => ids.includes(f.id))
const errors = (check.errors || 0) + (wig.errors || 0)
const warnings = (check.warnings || 0) + (wig.warnings || 0)

/* find the token file the same way verify.mjs does */
function findTokenFile(root, depth = 0) {
	if (depth > 5) return ""
	let entries = []
	try {
		entries = readdirSync(root, { withFileTypes: true })
	} catch {
		return ""
	}
	for (const e of entries) {
		const p = join(root, e.name)
		if (e.isDirectory()) {
			if (SKIP.has(e.name) || e.name.startsWith(".")) continue
			const found = findTokenFile(p, depth + 1)
			if (found) return found
			continue
		}
		if (!STYLEISH.has(extname(e.name))) continue
		try {
			if (statSync(p).size > 400_000) continue
			const raw = readFileSync(p, "utf8")
			if (/=== PALETTE: /.test(raw)) continue
			const defines = (raw.match(/^\s*--[a-z0-9-]+\s*:/gm) || []).length
			if (defines >= 8 && /--(?:canvas|surface|ink|accent|bg|foreground)\b/.test(raw)) return p
		} catch {
			/* unreadable, not a token file */
		}
	}
	return ""
}

let tokenFile = ""
for (const t of targets) {
	const p = resolve(t)
	if (!existsSync(p)) continue
	tokenFile = statSync(p).isDirectory() ? findTokenFile(p) : STYLEISH.has(extname(p)) ? p : ""
	if (tokenFile) break
}

let contrastFailures = -1
let fontVars = 0
if (tokenFile) {
	const { out } = run("contrast.mjs", [tokenFile])
	const summary = out.match(/(\d+) failures? in (\d+) measured pairs/)
	contrastFailures = summary ? Number(summary[1]) : 0
	fontVars = (readFileSync(tokenFile, "utf8").match(/--font-[a-z-]+\s*:/g) || []).length
}

/* ------------------------------------------------------------------- scoring */

const axis = []

/* 1. craft floor: what the linters found, nothing else */
axis.push({
	name: "craft floor",
	score: errors > 1 ? 1 : errors === 1 ? 2 : warnings > 3 ? 3 : warnings > 0 ? 4 : 5,
	why: `${errors} errors, ${warnings} warnings`,
})

/* 2. colour: measured pairs first, then how disciplined the palette is */
const rawHex = hit("raw-hex")
const hueCount = hit("hue-count")
axis.push({
	name: "colour",
	score:
		contrastFailures < 0
			? 1
			: contrastFailures > 0
				? 2
				: rawHex.length > 0
					? 3
					: hueCount.length > 0
						? 4
						: 5,
	why:
		contrastFailures < 0
			? "no token file found, so nothing was measured"
			: `${contrastFailures} failing pairs, ${rawHex.length} raw hex outside tokens, ${hueCount.length} hue warnings`,
})

/* 3. typography: coverage and discipline, in that order */
const faceMismatch = hit("cyrillic-latin-face", "lang-copy-mismatch", "banned-font")
const tooManyFonts = hit("font-count")
const small = hit("tiny-text")
const looseEnds = hit("display-no-tracking", "off-rhythm-space", "arbitrary-px-class")
axis.push({
	name: "typography",
	score:
		tokenFile && fontVars === 0
			? 1
			: faceMismatch.length > 0 || tooManyFonts.length > 0
				? 2
				: small.length > 0
					? 3
					: looseEnds.length > 0
						? 4
						: 5,
	why:
		tokenFile && fontVars === 0
			? "the token file defines no font families"
			: `${faceMismatch.length} script or face problems, ${tooManyFonts.length} family count warnings, ${small.length} sizes below the floor, ${looseEnds.length} loose ends`,
})

/* 4. states: the ones that make a surface unusable rank first */
const broken = hit("focus-none", "div-click-target", "tabindex-positive", "paste-blocked", "destructive-bare")
const stateWarns = hit(
	"focus-ring-missing",
	"icon-button-unnamed",
	"escape-close-missing",
	"aria-live-missing",
	"drag-no-keyboard",
	"placeholder-as-label",
	"autocomplete-missing",
	"svg-unlabelled",
)
axis.push({
	name: "states",
	score:
		(wig.errors || 0) >= 3
			? 1
			: broken.length > 0
				? 2
				: stateWarns.length > 2
					? 3
					: stateWarns.length > 0
						? 4
						: 5,
	why: `${wig.errors || 0} interface errors, ${broken.length} blocking defects, ${stateWarns.length} state gaps`,
})

const judged = ["direction", "composition", "motion", "copy"]
const measured = axis.reduce((sum, a) => sum + a.score, 0)

/* -------------------------------------------------------------------- report */

if (asJson) {
	console.log(JSON.stringify({ tokenFile, measured, axes: axis, judged, findings: all.slice(0, 40) }, null, 2))
	process.exit(0)
}

console.log(`viora score / ${targets.join(" ")}`)
console.log("=".repeat(72))
for (const a of axis) console.log(`${a.name.padEnd(14)} ${a.score}/5   ${a.why}`)
for (const name of judged) console.log(`${name.padEnd(14)} -/5   judge this one by looking, see evals/rubric.md`)
console.log("=".repeat(72))
console.log(`measured ${measured}/20. Four axes left to judge, twenty points still on the table.`)

const weakest = axis.slice().sort((a, b) => a.score - b.score)[0]
if (weakest.score < 5) {
	console.log(`weakest measured axis: ${weakest.name}. ${weakest.why}.`)
	const top = all.filter((f) => f.sev === "error").slice(0, 5)
	const list = top.length ? top : all.slice(0, 5)
	for (const f of list) console.log(`   ${f.file}:${f.line}  ${f.id}  ${f.msg}`)
	console.log("why any of these rules exist: node scripts/explain.mjs <rule-id>")
} else {
	console.log("all four measured axes are full. Whatever is still wrong is a design decision, not a defect.")
}
if (contrastFailures < 0) console.log("no token file was found in these paths, so colour scored 1 by default.")
