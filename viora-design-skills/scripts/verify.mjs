#!/usr/bin/env node
/**
 * Виора Design Skills / one-command verification for G6
 *
 *   node verify.mjs .
 *   node verify.mjs . --url http://localhost:3000
 *   node verify.mjs . --url ./dist/index.html --strict
 *   node verify.mjs src app --url http://localhost:5173
 *
 * Runs, in this order:
 *   1. check.mjs        the mechanical craft linter
 *   2. contrast.mjs     WCAG measurement on every token file it can find
 *   3. shot.mjs         desktop + mobile, then --squint, then --icon
 *
 * Prints one verdict. Exit 1 means the mechanical floor is not passed.
 * Fix everything reported in ONE batch, run this once more, then stop.
 * Do not open a third round: at that point look at the screenshots instead.
 */

import { spawnSync } from "node:child_process"
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, extname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const argv = process.argv.slice(2)

const getFlag = (name) => {
	const i = argv.findIndex((a) => a === `--${name}` || a.startsWith(`--${name}=`))
	if (i === -1) return undefined
	if (argv[i].includes("=")) return argv[i].split("=").slice(1).join("=")
	const next = argv[i + 1]
	return next && !next.startsWith("--") ? next : true
}

const url = getFlag("url")
const strict = Boolean(getFlag("strict"))
const skipShots = Boolean(getFlag("no-shots"))
const consumed = new Set([String(url), String(getFlag("out"))])
const targets = argv.filter((a) => !a.startsWith("--") && !consumed.has(a))
if (targets.length === 0) targets.push(".")

const SKIP = new Set([
	"node_modules", ".git", ".next", ".nuxt", ".svelte-kit", ".astro", "dist",
	"build", "out", "coverage", ".turbo", ".vercel", ".cache", ".viora-shots",
	".claude", ".codex", ".cursor", ".gemini", ".opencode", ".github",
	"viora-design-skills",
])
const STYLEISH = new Set([".css", ".scss", ".less", ".html", ".htm"])

/* a token file is one that defines the contract, not one that merely uses it */
function findTokenFiles(root, found = [], depth = 0) {
	if (depth > 6 || found.length >= 6) return found
	let entries = []
	try {
		entries = readdirSync(root, { withFileTypes: true })
	} catch {
		return found
	}
	for (const e of entries) {
		const p = join(root, e.name)
		if (e.isDirectory()) {
			if (SKIP.has(e.name) || e.name.startsWith(".")) continue
			findTokenFiles(p, found, depth + 1)
			continue
		}
		if (!STYLEISH.has(extname(e.name))) continue
		try {
			if (statSync(p).size > 400_000) continue
			const raw = readFileSync(p, "utf8")
			const defines = (raw.match(/^\s*--[a-z0-9-]+\s*:/gm) || []).length
			if (defines >= 8 && /--(?:canvas|surface|ink|accent|bg|foreground)\b/.test(raw)) found.push(p)
		} catch {
			/* unreadable file, not a token file */
		}
	}
	return found
}

const run = (label, file, args) => {
	console.log(`\n>>> ${label}`)
	const r = spawnSync(process.execPath, [join(here, file), ...args], { stdio: "inherit" })
	return r.status === null ? 2 : r.status
}

const results = []

/* 1. mechanical linter -------------------------------------------------- */
results.push([
	"check",
	run("check.mjs", "check.mjs", strict ? [...targets, "--strict"] : targets),
])

/* 2. contrast ----------------------------------------------------------- */
const tokenFiles = []
for (const t of targets) {
	const p = resolve(t)
	if (!existsSync(p)) continue
	if (statSync(p).isDirectory()) findTokenFiles(p, tokenFiles)
	else if (STYLEISH.has(extname(p))) tokenFiles.push(p)
}
if (tokenFiles.length === 0) {
	console.log("\n>>> contrast.mjs")
	console.log("no token file found. Every colour decision must live in one token file.")
	console.log("Copy assets/tokens.css into the project before continuing.")
	results.push(["contrast", 1])
} else {
	let worst = 0
	for (const f of [...new Set(tokenFiles)]) {
		worst = Math.max(worst, run(`contrast.mjs ${f}`, "contrast.mjs", [f]))
	}
	results.push(["contrast", worst])
}

/* 3. screenshots -------------------------------------------------------- */
if (url && !skipShots) {
	const u = String(url)
	const shots = [
		run("shot.mjs desktop + mobile", "shot.mjs", [u, "--sizes", "1440x900,390x844"]),
		run("shot.mjs --squint (silhouette)", "shot.mjs", [u, "--squint"]),
		run("shot.mjs --icon (scale test)", "shot.mjs", [u, "--icon"]),
	]
	results.push(["shots", Math.max(...shots)])
} else if (!skipShots) {
	console.log("\n>>> shot.mjs")
	console.log("no --url given, so nothing was looked at. Pass --url <url|file> and run again.")
	console.log("A page nobody looked at is not verified.")
	results.push(["shots", 1])
}

/* verdict --------------------------------------------------------------- */
const bar = "=".repeat(66)
console.log("\n" + bar)
for (const [name, code] of results) {
	console.log(`${name.padEnd(10)} ${code === 0 ? "pass" : code === 3 ? "unavailable" : "FAIL"}`)
}
const hard = results.filter(([, c]) => c !== 0 && c !== 3)
if (hard.length === 0) {
	console.log("\nmechanical floor passed. Now look at the shots: silhouette, icon,")
	console.log("mobile. Then run the subtraction pass and report. Do not re-verify.")
} else {
	console.log("\nnot verified yet. Fix everything above in one batch, then run this once more.")
}
console.log(bar)
process.exit(hard.length === 0 ? 0 : 1)
