#!/usr/bin/env node
/**
 * Виора Design Skills / lane router
 *
 *   node lane.mjs --model "gemini-2.5-flash"
 *   node lane.mjs --probe
 *   node lane.mjs --a1 "<token>" --a2 <number> --a3 '<json>'
 *   node lane.mjs --list-models
 *   node lane.mjs --downgrade "same rule fired twice"
 *
 * Why this file exists
 * --------------------
 * The old lane check asked the model three questions about itself. That does
 * not work. A model weak enough to lose the plan is exactly the model that
 * answers "yes, I can hold a plan", and it finds out otherwise on gate three,
 * with half a surface built and no way back.
 *
 * So capability is never self-reported here. It is either looked up by model
 * name, or measured by three tasks whose correct answers this script computes
 * from the files on disk and grades by exact match.
 *
 * Verdicts
 *   FULL         SKILL.md, all eight gates, catalog allowed
 *   FULL-NARROW  SKILL.md, one reference file per gate, no catalog
 *   LITE         LITE.md only, one pass, nothing else opened
 *
 * An unknown model means PROBE, never FULL. Guessing up costs more than
 * guessing down: an abandoned plan is worse than a plain finished surface.
 */

import { existsSync, readFileSync, readdirSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = join(HERE, "..")

/* ---------------------------------------------------------------- args -- */

const VALUE_FLAGS = new Set(["model", "a1", "a2", "a3", "downgrade"])
const argv = process.argv.slice(2)
const flags = {}
for (let i = 0; i < argv.length; i++) {
	const arg = argv[i]
	if (!arg.startsWith("--")) continue
	const eq = arg.indexOf("=")
	if (eq !== -1) {
		flags[arg.slice(2, eq)] = arg.slice(eq + 1)
		continue
	}
	const name = arg.slice(2)
	if (VALUE_FLAGS.has(name)) {
		const next = argv[i + 1]
		flags[name] = next === undefined || next.startsWith("--") ? "" : next
		if (flags[name] !== "") i++
		continue
	}
	flags[name] = true
}

const asJson = Boolean(flags.json)

/* -------------------------------------------------------- model lookup -- */

/* Explicit entries beat heuristics. Longest matching pattern wins, so
   "gpt-5-mini" does not get decided by the "gpt-5" row. */
const TABLE = [
	/* -- models that hold a plan across eight gates ---------------------- */
	["claude-opus", "FULL"],
	["claude-3-opus", "FULL"],
	["opus-4", "FULL"],
	["claude-sonnet", "FULL"],
	["sonnet-4", "FULL"],
	["claude-3-7-sonnet", "FULL"],
	["claude-3.7-sonnet", "FULL"],
	["claude-3-5-sonnet", "FULL"],
	["gpt-5", "FULL"],
	["gpt-5.1", "FULL"],
	["gpt-5-codex", "FULL"],
	["gpt-4.1", "FULL"],
	["o1", "FULL"],
	["o3", "FULL"],
	["gemini-2.5-pro", "FULL"],
	["gemini-2.0-pro", "FULL"],
	["gemini-3-pro", "FULL"],
	["grok-3", "FULL"],
	["grok-4", "FULL"],
	["deepseek-r1", "FULL"],
	["deepseek-v3", "FULL"],
	["qwen3-coder", "FULL"],
	["qwen3-235b", "FULL"],
	["qwen-max", "FULL"],
	["kimi-k2", "FULL"],
	["glm-4.5", "FULL"],
	["glm-4.6", "FULL"],
	["minimax-m2", "FULL"],
	["mistral-large", "FULL"],
	["llama-4-behemoth", "FULL"],

	/* -- capable, but not with four files open at once ------------------- */
	["gpt-4o", "FULL-NARROW"],
	["gpt-5-mini", "FULL-NARROW"],
	["gpt-4.1-mini", "FULL-NARROW"],
	["o4-mini", "FULL-NARROW"],
	["o3-mini", "FULL-NARROW"],
	["claude-3-5-haiku", "FULL-NARROW"],
	["llama-4-maverick", "FULL-NARROW"],
	["llama-3.3-70b", "FULL-NARROW"],
	["qwen3-32b", "FULL-NARROW"],
	["mistral-medium", "FULL-NARROW"],
	["devstral-small", "FULL-NARROW"],
	["codestral", "FULL-NARROW"],
	["gemini-2.0-flash-thinking", "FULL-NARROW"],

	/* -- one pass, one page, no plan to lose ----------------------------- */
	["gemini-1.5-flash", "LITE"],
	["gemini-2.0-flash", "LITE"],
	["gemini-2.5-flash", "LITE"],
	["gemini-3-flash", "LITE"],
	["gemini-flash", "LITE"],
	["claude-3-haiku", "LITE"],
	["gpt-4o-mini", "LITE"],
	["gpt-3.5", "LITE"],
	["gemma", "LITE"],
	["phi-", "LITE"],
	["mistral-small", "LITE"],
	["ministral", "LITE"],
	["qwen2.5-coder-7b", "LITE"],
	["deepseek-r1-distill", "LITE"],
]

const LITE_WORDS = ["flash", "haiku", "nano", "lite", "tiny", "distill", "instant", "mini", "small", "turbo"]

const normalize = (name) => String(name).toLowerCase().replace(/[_\s]+/g, "-").trim()

function lookup(rawName) {
	const name = normalize(rawName)
	if (!name) return null

	const hits = TABLE.filter(([pattern]) => name.includes(pattern)).sort(
		(a, b) => b[0].length - a[0].length,
	)
	if (hits.length > 0) return { lane: hits[0][1], why: `table entry "${hits[0][0]}"` }

	const word = LITE_WORDS.find((w) => name.includes(w))
	if (word) return { lane: "LITE", why: `name contains "${word}"` }

	const size = name.match(/(\d+(?:\.\d+)?)\s*b\b/)
	if (size) {
		const billions = Number(size[1])
		if (billions < 30) return { lane: "LITE", why: `${billions}B parameters` }
		if (billions < 100) return { lane: "FULL-NARROW", why: `${billions}B parameters` }
		return { lane: "FULL", why: `${billions}B parameters` }
	}

	return null
}

/* -------------------------------------------------------------- probe --- */

/* Three tasks. Each one measures a thing that actually breaks the FULL lane:
   reading a file precisely, running a command and reading the output back,
   and emitting an exact structure. The answers are computed here, so the
   probe stays correct when the files change. */

function truth() {
	const bans = join(ROOT, "reference", "09-slop-bans.md")
	const palettes = join(ROOT, "data", "palettes.csv")
	const refDir = join(ROOT, "reference")

	const missing = [bans, palettes, refDir].filter((p) => !existsSync(p))
	if (missing.length > 0) return { error: `this copy of the skill is incomplete: ${missing.join(", ")}` }

	const line = readFileSync(bans, "utf8")
		.split("\n")
		.map((l) => l.trim())
		.find((l) => l.split(/\s+/).filter(Boolean).length >= 6)
	const a1 = line ? line.split(/\s+/).filter(Boolean)[2] : ""

	const raw = readFileSync(palettes, "utf8")
	const a2 = (raw.match(/\n/g) || []).length

	const a3 = readdirSync(refDir).filter((f) => f.endsWith(".md")).length

	return { a1, a2, a3 }
}

function printProbe() {
	const t = truth()
	if (t.error) {
		console.log(t.error)
		process.exit(2)
	}
	console.log(`
lane probe / three tasks, graded by exact match
${"=".repeat(70)}

Do all three, then run the command at the bottom. Do not guess, do not round,
do not explain. If a task is impossible for you, pass an empty value for it:
an honest blank scores the same as a wrong answer and costs you less later.

1. In reference/09-slop-bans.md, find the first line that has six or more
   whitespace-separated words. Take its THIRD word, exactly as written,
   punctuation included.

2. Run this and read the number back:

       wc -l < data/palettes.csv

3. Count the files ending in .md directly inside reference/ and put that
   number into this exact structure, same keys, same order, no extra fields:

       {"lane":"probe","md":<number>,"ok":true}

Answer with one command:

    node scripts/lane.mjs --a1 "<word>" --a2 <number> --a3 '{"lane":"probe","md":<number>,"ok":true}'
${"=".repeat(70)}`)
}

function grade() {
	const t = truth()
	if (t.error) {
		console.log(t.error)
		process.exit(2)
	}

	const got1 = String(flags.a1 ?? "").trim()
	const ok1 = got1 !== "" && got1 === t.a1

	const got2 = String(flags.a2 ?? "").trim()
	const ok2 = got2 !== "" && Number(got2) === t.a2

	let parsed = null
	try {
		parsed = JSON.parse(String(flags.a3 ?? ""))
	} catch {
		parsed = null
	}
	const keys = parsed && typeof parsed === "object" ? Object.keys(parsed) : []
	const ok3 =
		Boolean(parsed) &&
		keys.length === 3 &&
		keys[0] === "lane" &&
		keys[1] === "md" &&
		keys[2] === "ok" &&
		parsed.lane === "probe" &&
		parsed.md === t.a3 &&
		parsed.ok === true

	const score = [ok1, ok2, ok3].filter(Boolean).length
	const lane = score === 3 ? "FULL" : score === 2 ? "FULL-NARROW" : "LITE"

	if (asJson) {
		console.log(JSON.stringify({ lane, score, tasks: { read: ok1, run: ok2, structure: ok3 } }, null, 2))
		return lane
	}

	console.log(`
lane probe / result
${"-".repeat(70)}
1 read a file precisely   ${ok1 ? "pass" : `FAIL   expected "${t.a1}", got "${got1}"`}
2 run a command, read it  ${ok2 ? "pass" : `FAIL   expected ${t.a2}, got "${got2}"`}
3 emit an exact structure ${ok3 ? "pass" : `FAIL   expected {"lane":"probe","md":${t.a3},"ok":true}`}

score ${score}/3`)
	return lane
}

/* ------------------------------------------------------------ verdicts -- */

const PLAN = {
	FULL: [
		"Open SKILL.md and run all eight gates, G0 to G7.",
		"One reference file per gate is the budget, two if the gate names two.",
		"The catalog is available: node scripts/pick.mjs \"<brief>\" --system",
	],
	"FULL-NARROW": [
		"Open SKILL.md and run all eight gates, G0 to G7.",
		"Exactly one reference file per gate. Close it before opening the next.",
		"Skip the catalog. Use the thirteen palettes in reference/05-color.md.",
		"If you catch yourself rereading your own output to remember the plan,",
		"run: node scripts/lane.mjs --downgrade \"lost the plan\"",
	],
	LITE: [
		"Open LITE.md and nothing else. It is self-contained on purpose.",
		"Pick one of the eight recipes, copy the hex values, do not invent colour.",
		"Do not open SKILL.md or reference/. Mixing lanes is worse than either lane.",
		"Blocks you can paste instead of inventing: assets/blocks/",
	],
}

const TRIGGERS = [
	"the same rule id fires again after you thought you fixed it",
	"you cannot reproduce a marker line exactly as written",
	"you have three or more reference files open for one gate",
	"you would have to reread your own output to remember the direction",
	"two tool calls in a row failed and you cannot say why",
	"you are about to write a long file and you are not sure it will be complete",
]

function verdict(lane, why) {
	if (asJson) {
		console.log(JSON.stringify({ lane, why: why ?? null, plan: PLAN[lane], downgradeTriggers: TRIGGERS }, null, 2))
		return
	}
	console.log(`
lane: ${lane}${why ? `   (${why})` : ""}
${"-".repeat(70)}`)
	for (const line of PLAN[lane]) console.log(line)
	if (lane !== "LITE") {
		console.log(`
Downgrade to LITE the moment any of these is true. This is not a judgement
call about how smart you are, it is a list of observable events:`)
		for (const t of TRIGGERS) console.log(`  - ${t}`)
		console.log(`
Then run: node scripts/lane.mjs --downgrade "<which one>"`)
	}
	console.log("-".repeat(70))
}

/* --------------------------------------------------------------- main --- */

if (flags["list-models"]) {
	console.log("\nmodel name contains        lane")
	console.log("-".repeat(70))
	for (const [pattern, lane] of TABLE) console.log(`${pattern.padEnd(26)} ${lane}`)
	console.log("-".repeat(70))
	console.log(`any name containing ${LITE_WORDS.join(", ")} falls to LITE.`)
	console.log("a parameter count decides the rest: under 30B LITE, under 100B FULL-NARROW.")
	console.log("anything still unknown goes to --probe, never to FULL.")
	process.exit(0)
}

if (flags.downgrade !== undefined) {
	const reason = String(flags.downgrade || "unspecified")
	console.log(`
switching to LITE / ${reason}
${"-".repeat(70)}
Keep: the token file, the palette, the copy you already wrote.
Drop: the gate plan, the unfinished sections, the reference files you opened.
Do: open LITE.md, start at step 1, treat what exists as a first draft.
Say: one line to the user, "switching to the compact lane to finish cleanly".

Do not go back to SKILL.md in this run. A finished LITE surface beats an
abandoned FULL one, and the user cannot see the difference in ambition,
only the difference in finish.
${"-".repeat(70)}`)
	process.exit(0)
}

if (flags.a1 !== undefined || flags.a2 !== undefined || flags.a3 !== undefined) {
	const lane = grade()
	verdict(lane, "graded probe")
	process.exit(0)
}

if (flags.probe) {
	printProbe()
	process.exit(0)
}

if (flags.model !== undefined && String(flags.model).trim() !== "") {
	const hit = lookup(flags.model)
	if (hit) {
		verdict(hit.lane, `${hit.why}, model "${flags.model}"`)
		process.exit(0)
	}
	if (asJson) {
		console.log(JSON.stringify({ lane: null, why: `unknown model "${flags.model}"`, next: "--probe" }, null, 2))
		process.exit(0)
	}
	console.log(`
unknown model "${flags.model}". Unknown is not FULL.
Run the probe, it takes three answers:

    node scripts/lane.mjs --probe
`)
	process.exit(0)
}

console.log(`
Виора lane router
${"=".repeat(70)}
Two lanes exist because one document cannot serve both a model that holds a
plan across eight gates and a model that does not. Picking the wrong lane
costs more than picking the plain one.

Decide in this order:

1. If you know your own model name:

       node scripts/lane.mjs --model "<your model name>"

2. If you do not know it, or it is not in the table:

       node scripts/lane.mjs --probe

3. If you cannot run node at all, look yourself up in the table at the top of
   reference/17-model-tiers.md, and when in doubt take LITE.md. A model with no
   terminal cannot verify anything mechanically, which is the FULL lane's whole
   point.

See also: --list-models, --downgrade "<reason>", --json
${"=".repeat(70)}`)
