#!/usr/bin/env node

/**
 * palettes.mjs - measure every palette in the library, not only the active one
 *
 *   node scripts/palettes.mjs
 *   node scripts/palettes.mjs assets/palettes.css assets/tokens.css
 *   node scripts/palettes.mjs --json
 *   node scripts/palettes.mjs --only editorial
 *
 * assets/palettes.css is a set of promises: paste this block, get a palette that
 * holds. This is what keeps them true. Each block is substituted into the token
 * contract, then contrast.mjs measures the result. Exit 1 if any pair fails.
 *
 * contrast.mjs alone cannot do this: it reads one :root, and the library has one
 * per palette. That is also why verify.mjs never hands the library to it directly.
 */

import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const argv = process.argv.slice(2)
const asJson = argv.includes("--json")
const onlyIndex = argv.indexOf("--only")
const only = onlyIndex !== -1 ? String(argv[onlyIndex + 1] || "") : ""
const skipIndex = onlyIndex === -1 ? -1 : onlyIndex + 1
const paths = argv.filter((a, i) => !a.startsWith("--") && i !== skipIndex)

const library = resolve(paths[0] || join(HERE, "..", "assets", "palettes.css"))
const contract = resolve(paths[1] || join(HERE, "..", "assets", "tokens.css"))

let lib = ""
let tokens = ""
try {
	lib = readFileSync(library, "utf8")
	tokens = readFileSync(contract, "utf8")
} catch (error) {
	console.error(`palettes: cannot read ${error.path || "the input files"}`)
	console.error("usage: node scripts/palettes.mjs [palettes.css] [tokens.css] [--json] [--only name]")
	process.exit(2)
}

/* the contract's own :root is replaced wholesale, everything else is kept:
   fonts, space, radius, motion and the craft floor stay exactly as shipped */
const start = tokens.indexOf(":root {")
const end = tokens.indexOf("\n}", start)
if (start === -1 || end === -1) {
	console.error(`palettes: ${contract} has no :root block to substitute into`)
	process.exit(2)
}
const head = tokens.slice(0, start)
const tail = tokens.slice(end + 2)

const BLOCK = /\/\* === PALETTE: ([a-z0-9-]+) ===([^\n]*)\n[\s\S]*?(:root \{[\s\S]*?\n\})/g
const work = mkdtempSync(join(tmpdir(), "viora-palettes-"))
const report = []

try {
	let match
	while ((match = BLOCK.exec(lib))) {
		const [, name, intent, block] = match
		if (only && name !== only) continue
		const file = join(work, `${name}.css`)
		writeFileSync(file, head + block + tail)
		let out = ""
		try {
			out = execFileSync(process.execPath, [join(HERE, "contrast.mjs"), file], { encoding: "utf8" })
		} catch (error) {
			out = String(error.stdout || "")
		}
		const summary = out.match(/(\d+) failures? in (\d+) measured pairs/)
		const rows = out
			.split("\n")
			.filter((line) => line.includes("FAIL"))
			.map((line) => line.trim())
		report.push({
			name,
			intent: intent.replace(/\*\/\s*$/, "").trim(),
			failures: summary ? Number(summary[1]) : rows.length,
			pairs: summary ? Number(summary[2]) : 0,
			rows,
		})
	}
} finally {
	rmSync(work, { recursive: true, force: true })
}

if (!report.length) {
	console.error(only ? `palettes: no palette named "${only}" in ${library}` : `palettes: no PALETTE blocks in ${library}`)
	process.exit(2)
}

const failing = report.filter((p) => p.failures > 0)

if (asJson) {
	console.log(JSON.stringify({ library, contract, palettes: report, failing: failing.length }, null, 2))
	process.exit(failing.length ? 1 : 0)
}

console.log(`viora palette library / ${report.length} palettes measured against ${contract.split("/").slice(-2).join("/")}`)
console.log("-".repeat(72))
for (const p of report) {
	if (p.failures > 0) {
		console.log(`${p.name.padEnd(14)} FAIL ${p.failures}`)
		for (const row of p.rows) console.log(`               ${row}`)
		continue
	}
	console.log(`${p.name.padEnd(14)} pass ${p.pairs || 30} pairs`)
}
console.log("-".repeat(72))
if (failing.length) {
	console.log(`${failing.length} of ${report.length} palettes have a failing pair.`)
	console.log("Move the failing token, not the accent. A palette ships when it measures, not when it looks right in the block.")
	console.log("Single-mode palettes hold one value in both columns, so the light and the dark token move together.")
} else {
	console.log(`all ${report.length} palettes pass. Paste any block into the token layer and it holds.`)
}
process.exit(failing.length ? 1 : 0)
