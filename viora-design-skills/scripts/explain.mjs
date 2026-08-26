#!/usr/bin/env node

/**
 * explain.mjs - why a linter rule exists, and what the fix looks like
 *
 *   node scripts/explain.mjs em-dash
 *   node scripts/explain.mjs url-state --json
 *   node scripts/explain.mjs --all
 *   node scripts/explain.mjs --coverage
 *
 * check.mjs and wig.mjs say what is wrong. This says why, with a before and an
 * after, so the next file does not repeat it.
 *
 * Weak model: read the entry for every error you hit, then fix and re-run.
 * Strong model: read the entries you disagree with. If you still disagree,
 * suppress the rule with a written reason. A reason is a decision, silence is not.
 */

import { execFileSync } from "node:child_process"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { CHECK } from "./rules/check-rules.mjs"
import { WIG } from "./rules/wig-rules.mjs"

const HERE = dirname(fileURLToPath(import.meta.url))

const RULES = new Map()
const add = (id, entry, from) => {
	const [why, fix, bad, good] = entry
	RULES.set(id, { id, from, why, fix, bad, good })
}
for (const [id, entry] of Object.entries(CHECK)) add(id, entry, "check")
for (const [id, entry] of Object.entries(WIG)) add(id, entry, "wig")

/* ---------------------------------------------------------------- severity */

function listRules(script) {
	const out = execFileSync("node", [join(HERE, script), "--list-rules"], {
		encoding: "utf8",
		stdio: ["ignore", "pipe", "ignore"],
	})
	const found = new Map()
	for (const line of out.split("\n")) {
		const m = line.match(/^(error|warn)\s+(\S+)/)
		if (m) found.set(m[2], m[1])
	}
	return found
}

function severityOf(rule) {
	try {
		return listRules(rule.from === "wig" ? "wig.mjs" : "check.mjs").get(rule.id) || ""
	} catch {
		return ""
	}
}

/* -------------------------------------------------------------------- args */

const argv = process.argv.slice(2)
const has = (name) => argv.includes(`--${name}`)
const ids = argv.filter((a) => !a.startsWith("-"))

if (has("all") || has("list")) {
	console.log(`viora rule catalogue / ${RULES.size} entries\n`)
	for (const rule of RULES.values()) {
		console.log(`  ${rule.id.padEnd(24)} ${rule.from.padEnd(6)} ${rule.fix}`)
	}
	console.log("\nnode scripts/explain.mjs <rule-id> for the full entry")
	process.exit(0)
}

if (has("coverage")) {
	let bad = 0
	for (const [script, table, label] of [
		["check.mjs", CHECK, "check"],
		["wig.mjs", WIG, "wig"],
	]) {
		let live
		try {
			live = listRules(script)
		} catch (error) {
			console.log(`${label}: could not run ${script} (${error.message.split("\n")[0]})`)
			bad++
			continue
		}
		const have = new Set(Object.keys(table))
		const missing = [...live.keys()].filter((id) => !have.has(id))
		const orphan = [...have].filter((id) => !live.has(id))
		console.log(`${label}: ${live.size} rules, ${have.size} entries`)
		if (missing.length) {
			console.log(`  no entry for: ${missing.join(", ")}`)
			bad += missing.length
		}
		if (orphan.length) {
			console.log(`  entry with no rule: ${orphan.join(", ")}`)
			bad += orphan.length
		}
		if (!missing.length && !orphan.length) console.log("  complete")
	}
	console.log(bad ? `\ncoverage: ${bad} gaps` : "\ncoverage: every rule has an entry")
	process.exit(bad ? 1 : 0)
}

if (!ids.length) {
	console.error("usage: node scripts/explain.mjs <rule-id> [--json]   |   --all   |   --coverage")
	process.exit(2)
}

/* ------------------------------------------------------------------ output */

const near = (id) => {
	const parts = id.split(/[-_]/).filter(Boolean)
	return [...RULES.keys()]
		.filter((k) => k.includes(id) || id.includes(k) || parts.some((p) => p.length > 2 && k.includes(p)))
		.slice(0, 6)
}

const picked = []
for (const id of ids) {
	const rule = RULES.get(id)
	if (rule) {
		picked.push(rule)
		continue
	}
	const guesses = near(id)
	console.error(`no entry for "${id}"`)
	if (guesses.length) console.error(`did you mean: ${guesses.join(", ")}`)
	else console.error("run --all to see every rule id")
	process.exit(2)
}

if (has("json")) {
	console.log(JSON.stringify(picked.length === 1 ? picked[0] : picked, null, 2))
	process.exit(0)
}

for (const rule of picked) {
	const severity = severityOf(rule)
	console.log(`\n${rule.id}   ${rule.from}${severity ? `, ${severity}` : ""}`)
	console.log("=".repeat(72))
	console.log(`why   ${rule.why}`)
	console.log(`fix   ${rule.fix}`)
	console.log(`\nbefore\n  ${rule.bad}`)
	console.log(`after\n  ${rule.good}`)
}

console.log(
	"\nfull rules: reference/09-slop-bans.md (copy and pattern bans), reference/14-interface-rules.md",
)
console.log("working examples: assets/blocks/")
console.log("disagree? suppress with a reason: /* viora-allow: <rule-id> why this is correct here */")
