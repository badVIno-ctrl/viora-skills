#!/usr/bin/env node

/**
 * docsync.mjs - the skill checking itself
 *
 *   node scripts/docsync.mjs
 *   node scripts/docsync.mjs --json
 *
 * A design skill that contradicts itself teaches contradictions. This checks
 * the parts a reader cannot verify by eye:
 *
 *   paths     every file the docs point at exists
 *   version   one version string across SKILL.md, LITE.md, README.md
 *   gates     G0 to G7 are all defined in SKILL.md
 *   lite      every LITE recipe measures against WCAG, not just the full palettes
 *   explain   every linter rule has a catalogue entry
 *   palettes  every palette in the library still passes
 *   blocks    the paste-in blocks lint clean, with the token file
 *   catalog   every CSV pick.mjs can search is present
 *
 * Exit 1 on any gap. Run it before shipping a change to the skill itself.
 */

import { execFileSync, spawnSync } from "node:child_process"
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(join(HERE, ".."))
const asJson = process.argv.includes("--json")

const stages = []
const push = (name, gaps, note = "") => stages.push({ name, gaps, note })
const read = (p) => {
	try {
		return readFileSync(join(ROOT, p), "utf8")
	} catch {
		return ""
	}
}
const node = (args) => {
	const r = spawnSync(process.execPath, args, { cwd: ROOT, encoding: "utf8" })
	return { code: r.status ?? 1, out: `${r.stdout || ""}${r.stderr || ""}` }
}

/* --------------------------------------------------------------- markdown */

function markdownFiles(dir = ROOT, found = [], depth = 0) {
	if (depth > 3) return found
	for (const e of readdirSync(dir, { withFileTypes: true })) {
		if (e.name.startsWith(".") || e.name === "node_modules") continue
		const p = join(dir, e.name)
		if (e.isDirectory()) {
			markdownFiles(p, found, depth + 1)
			continue
		}
		if (e.name.endsWith(".md")) found.push(p)
	}
	return found
}

const docs = markdownFiles()

/* 1. paths ---------------------------------------------------------------- */
{
	const gaps = []
	const REF = /\b((?:reference|scripts|assets|data|evals)\/[A-Za-z0-9._/-]+)/g
	for (const file of docs) {
		/* ATTRIBUTION.md quotes upstream filenames on purpose: those paths belong
		   to other repositories and are not expected to exist here. */
		if (file.endsWith("ATTRIBUTION.md")) continue
		const text = readFileSync(file, "utf8")
		for (const line of text.split("\n")) {
			if (line.trimStart().startsWith("|")) continue
			for (const m of line.matchAll(REF)) {
				const raw = m[1].replace(/[.,:;)\]`*]+$/, "")
				if (raw.includes("*") || raw.includes("<")) continue
				if (existsSync(join(ROOT, raw))) continue
				gaps.push(`${file.slice(ROOT.length + 1)}: ${raw}`)
			}
		}
	}
	push("paths", [...new Set(gaps)], `${docs.length} docs scanned`)
}

/* 2. version -------------------------------------------------------------- */
{
	const skill = read("SKILL.md")
	/* the frontmatter is the source of truth: "version: 4.1.0" */
	const declared = (skill.match(/^version:\s*(\d+\.\d+\.\d+)/m) || skill.match(/v(\d+\.\d+\.\d+)/) || [])[1] || ""
	const gaps = []
	if (!declared) gaps.push("SKILL.md declares no version")
	else {
		for (const f of ["SKILL.md", "LITE.md", "README.md", "CHANGELOG.md"]) {
			const text = read(f)
			if (!text) continue
			if (f === "CHANGELOG.md") continue
			for (const m of text.matchAll(/(?:^version:\s*|v)(\d+\.\d+\.\d+)/gm)) {
				if (m[1] !== declared) gaps.push(`${f}: ${m[1]} but SKILL.md declares ${declared}`)
			}
		}
	}
	push("version", [...new Set(gaps)], declared ? `v${declared}` : "none")
}

/* 3. gates ---------------------------------------------------------------- */
{
	const skill = read("SKILL.md")
	const gaps = []
	for (let i = 0; i <= 7; i++) if (!skill.includes(`G${i}`)) gaps.push(`SKILL.md never defines G${i}`)
	push("gates", gaps, "G0 to G7")
}

/* 4. lite recipes --------------------------------------------------------- */
{
	/* a LITE recipe is seven hexes in one line: canvas, surface, hairline, ink,
	   ink-muted, accent, accent-ink. The weak lane pastes these without measuring,
	   so they are measured here instead. */
	const chan = (c) => {
		const s = c / 255
		return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
	}
	const lum = (h) => {
		const [r, g, b] = [1, 3, 5].map((i) => Number.parseInt(h.slice(i, i + 2), 16))
		return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)
	}
	const ratio = (a, b) => {
		const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
		return (hi + 0.05) / (lo + 0.05)
	}
	const gaps = []
	let measured = 0
	const text = read("LITE.md")
	for (const line of text.split("\n")) {
		const hexes = (line.match(/#[0-9a-fA-F]{6}\b/g) || []).map((h) => h.toLowerCase())
		if (hexes.length < 7) continue
		const [canvas, , , ink, muted, accent, accentInk] = hexes
		const label = (line.match(/R\d+/) || ["recipe"])[0]
		measured++
		const pairs = [
			["ink on canvas", ratio(ink, canvas), 4.5],
			["ink-muted on canvas", ratio(muted, canvas), 4.5],
			["accent-ink on accent", ratio(accentInk, accent), 4.5],
			["accent on canvas", ratio(accent, canvas), 3],
		]
		for (const [what, value, need] of pairs) {
			if (value < need) gaps.push(`${label}: ${what} is ${value.toFixed(2)}:1, needs ${need}`)
		}
	}
	if (!measured) gaps.push("LITE.md has no recipe line with seven hexes")
	push("lite", gaps, `${measured} recipes measured`)
}

/* 5. explain coverage ----------------------------------------------------- */
{
	const { code, out } = node([join(HERE, "explain.mjs"), "--coverage"])
	const gaps = code === 0 ? [] : out.split("\n").filter((l) => l.includes("no entry") || l.includes("no rule")).map((l) => l.trim())
	push("explain", gaps.length || code === 0 ? gaps : ["explain --coverage failed"], (out.match(/check: .*/) || [""])[0])
}

/* 6. palettes ------------------------------------------------------------- */
{
	if (existsSync(join(ROOT, "assets", "palettes.css"))) {
		const { code, out } = node([join(HERE, "palettes.mjs")])
		const gaps = code === 0 ? [] : out.split("\n").filter((l) => l.includes("FAIL")).map((l) => l.trim())
		push("palettes", gaps.length || code === 0 ? gaps : ["palettes.mjs failed"], (out.match(/\d+ palettes measured|all \d+ palettes pass/) || [""])[0])
	} else push("palettes", ["assets/palettes.css is missing"])
}

/* 7. blocks --------------------------------------------------------------- */
{
	const blocks = join(ROOT, "assets", "blocks")
	if (!existsSync(blocks)) push("blocks", ["assets/blocks is missing"])
	else {
		/* a fragment has no token file of its own, so it is always linted next to
		   assets/tokens.css. Alone it would report tokens-missing, which is a
		   scanning artifact, not a defect. */
		const gaps = []
		const lint = node([join(HERE, "check.mjs"), "assets/blocks", "assets/tokens.css", "--summary"])
		if (lint.code !== 0) gaps.push(...lint.out.split("\n").filter((l) => /\berror\b|\bwarn\b/.test(l)).slice(0, 8).map((l) => l.trim()))
		const interfaceLint = node([join(HERE, "wig.mjs"), "assets/blocks", "--summary"])
		if (interfaceLint.code !== 0) gaps.push(...interfaceLint.out.split("\n").filter((l) => l.trim()).slice(0, 8).map((l) => l.trim()))
		const tokens = read("assets/tokens.css")
		const defined = new Set([...tokens.matchAll(/--([a-z0-9-]+)\s*:/g)].map((m) => m[1].replace(/-(light|dark)$/, "")))
		for (const dir of ["html", "react"]) {
			const full = join(blocks, dir)
			if (!existsSync(full)) continue
			for (const name of readdirSync(full)) {
				const text = readFileSync(join(full, name), "utf8")
				for (const m of text.matchAll(/var\(--([a-z0-9-]+)/g)) {
					if (!defined.has(m[1])) gaps.push(`blocks/${dir}/${name}: var(--${m[1]}) is not in tokens.css`)
				}
			}
		}
		push("blocks", [...new Set(gaps)])
	}
}

/* 8. catalog -------------------------------------------------------------- */
{
	const pick = read("scripts/pick.mjs")
	const gaps = []
	let counted = 0
	for (const m of pick.matchAll(/file:\s*"([A-Za-z0-9._-]+\.csv)"/g)) {
		counted++
		if (!existsSync(join(ROOT, "data", m[1]))) gaps.push(`data/${m[1]} is searched by pick.mjs but missing`)
	}
	const stacks = join(ROOT, "data", "stacks")
	const stackCount = existsSync(stacks) ? readdirSync(stacks).filter((f) => f.endsWith(".csv")).length : 0
	if (stackCount === 0) gaps.push("data/stacks has no CSV files")
	push("catalog", gaps, `${counted} tables, ${stackCount} stacks`)
}

/* ------------------------------------------------------------------ report */

const failed = stages.filter((s) => s.gaps.length > 0)

if (asJson) {
	console.log(JSON.stringify({ root: ROOT, stages, failed: failed.length }, null, 2))
	process.exit(failed.length ? 1 : 0)
}

console.log("viora docsync / the skill checking itself")
console.log("=".repeat(72))
for (const s of stages) {
	const head = `${s.name.padEnd(10)} ${s.gaps.length === 0 ? "ok" : `${s.gaps.length} gap${s.gaps.length === 1 ? "" : "s"}`}`
	console.log(s.note ? `${head.padEnd(22)} ${s.note}` : head)
	for (const gap of s.gaps.slice(0, 12)) console.log(`   ${gap}`)
	if (s.gaps.length > 12) console.log(`   and ${s.gaps.length - 12} more`)
}
console.log("=".repeat(72))
console.log(
	failed.length
		? `${failed.length} stage${failed.length === 1 ? "" : "s"} out of sync. The docs promise something the files do not deliver.`
		: "the skill agrees with itself.",
)
process.exit(failed.length ? 1 : 0)
