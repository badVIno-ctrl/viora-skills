#!/usr/bin/env node
/**
 * Виора Design Skills / gate conductor
 *
 * A gate that is only a line of text in the answer is a gate a model can skip
 * and still claim. This records them on disk, and verify.mjs refuses to print a
 * verdict until the gates this job requires are actually there.
 *
 *   node scripts/gate.mjs start NEW LAND FILE FULL
 *   node scripts/gate.mjs pass G2 "direction: pressroom"
 *   node scripts/gate.mjs status
 *   node scripts/gate.mjs status --json
 *   node scripts/gate.mjs reset
 *   node scripts/gate.mjs log --surface "pricing page" --world pressroom \
 *       --palette 42 --type "Manrope/Inter" --structure "ledger" --nav N3 \
 *       --footer F2 --paper mid --accent warm
 *
 * State lives in .viora/design-run.json next to the work, not in the model's head:
 *   { job, mode, stack, lane, gates: { G0: { at, marker }, ... } }
 *
 * G7 appends one row to .viora/design-log.json. The next project reads it through
 * pick.mjs --avoid-last, so two unrelated surfaces cannot land in the same world
 * by default. Rotation that depends on memory does not happen.
 *
 * status reports, it does not judge: it exits 0 even with gates outstanding, and
 * prints --json for a caller that wants to decide. verify.mjs is what refuses.
 * Exit 2 on a usage error.
 */

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"

export const GATES = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]

/* The gates each job runs, exactly as SKILL.md routes them. Five jobs and the four
   verbs from reference/21-verbs.md, so a HARDEN or CRITIQUE pass can be recorded too. */
export const REQUIRED = {
	NEW: ["G0", "G1", "G2", "G3", "G4", "G5", "G6"],
	REDESIGN: ["G0", "G1", "G2", "G3", "G4", "G5", "G6"],
	CHANGE: ["G1", "G3", "G4", "G5", "G6"],
	FIX: ["G1", "G4", "G6"],
	REVIEW: ["G1", "G6", "G7"],
	HARDEN: ["G1", "G4", "G5", "G6"],
	QUIET: ["G1", "G3", "G4", "G6"],
	BOLD: ["G1", "G3", "G4", "G6"],
	CRITIQUE: ["G1", "G6", "G7"],
	STUDY: ["G1", "G2"],
}

/* LITE is one pass, not eight gates: it records the start, the frame, the verify and
   the report. Holding it to the FULL list would refuse every LITE run. */
export const REQUIRED_LITE = ["G3", "G6", "G7"]

/* G6 is the gate verify.mjs is running, and G7 comes after it. Neither can be on disk
   while the verdict is being computed, so the refusal list stops before them. */
export const PENDING_AT_VERIFY = ["G6", "G7"]

export function requiredFor(run) {
	if (!run || !run.job) return []
	const job = String(run.job).toUpperCase()
	const lane = String(run.lane || "FULL").toUpperCase()
	const full = REQUIRED[job] || []
	if (lane === "LITE") return REQUIRED_LITE
	return full
}

/* what verify.mjs may demand: everything the job owes, minus the gates still in flight */
export function requiredBeforeVerdict(run) {
	return requiredFor(run).filter((g) => !PENDING_AT_VERIFY.includes(g))
}
export const JOBS = Object.keys(REQUIRED)
export const MODES = ["LAND", "APP", "READ", "SHOW"]
export const STACKS = ["FILE", "PARTS", "APP"]
export const LANES = ["FULL", "FULL-NARROW", "LITE"]

export const stateDir = (root = process.cwd()) => join(root, ".viora")
export const statePath = (root = process.cwd()) => join(stateDir(root), "design-run.json")
export const logPath = (root = process.cwd()) => join(stateDir(root), "design-log.json")

export function readLog(root = process.cwd()) {
	const p = logPath(root)
	if (!existsSync(p)) return []
	try {
		const rows = JSON.parse(readFileSync(p, "utf8"))
		return Array.isArray(rows) ? rows : []
	} catch {
		return []
	}
}

export const lastEntry = (root = process.cwd()) => readLog(root).slice(-1)[0] || null

export function readRun(root = process.cwd()) {
	const p = statePath(root)
	if (!existsSync(p)) return null
	try {
		const run = JSON.parse(readFileSync(p, "utf8"))
		if (!run || typeof run !== "object") return null
		if (!run.gates || typeof run.gates !== "object") run.gates = {}
		return run
	} catch {
		return null
	}
}

/* The run belongs to the project, not to the directory the command happens to be
   typed in. G4 is often recorded from inside src/, and verify.mjs walks up the same
   way, so both must resolve to one record instead of forking a second run. */
export function findRunRoot(from = process.cwd()) {
	let dir = resolve(from)
	for (let up = 0; up < 6; up++) {
		if (existsSync(statePath(dir))) return dir
		const parent = dirname(dir)
		if (parent === dir) break
		dir = parent
	}
	return null
}

export const findRun = (from = process.cwd()) => {
	const root = findRunRoot(from)
	return root ? readRun(root) : null
}

export function missingGates(run) {
	return requiredFor(run).filter((g) => !run.gates || !run.gates[g])
}

function writeRun(run, root = process.cwd()) {
	mkdirSync(stateDir(root), { recursive: true })
	writeFileSync(statePath(root), `${JSON.stringify(run, null, 2)}\n`)
}

const PAPER = ["dark", "mid", "light"]
const ACCENT = ["warm", "cool", "neutral", "other"]

export function appendLog(entry, root = process.cwd()) {
	const rows = readLog(root)
	rows.push({ ...entry, at: new Date().toISOString() })
	mkdirSync(stateDir(root), { recursive: true })
	/* keep the tail only: rotation cares about what was just shipped */
	const kept = rows.slice(-40)
	writeFileSync(logPath(root), `${JSON.stringify(kept, null, 2)}\n`)
	return kept[kept.length - 1]
}

/* ------------------------------------------------------------------- cli */

const argv = process.argv.slice(2)
const isMain = Boolean(process.argv[1] && process.argv[1].endsWith("gate.mjs"))

if (isMain) {
	const asJson = argv.includes("--json")
	const args = argv.filter((a) => !a.startsWith("--"))
	const cmd = (args[0] || "status").toLowerCase()
	const die = (line) => {
		console.error(line)
		process.exit(2)
	}

	if (cmd === "start") {
		const [, job, mode, stack, lane] = args
		if (!job || !mode || !stack) {
			die(`usage: node scripts/gate.mjs start <${JOBS.join("|")}> <LAND|APP|READ|SHOW> <FILE|PARTS|APP> [FULL|FULL-NARROW|LITE]`)
		}
		const J = job.toUpperCase()
		if (!JOBS.includes(J)) die(`unknown job "${job}". One of: ${JOBS.join(", ")}`)
		const M = mode.toUpperCase()
		if (!MODES.includes(M)) die(`unknown mode "${mode}". One of: ${MODES.join(", ")}`)
		const S = stack.toUpperCase()
		if (!STACKS.includes(S)) die(`unknown stack "${stack}". One of: ${STACKS.join(", ")}`)
		const L = (lane || "FULL").toUpperCase()
		if (!LANES.includes(L)) die(`unknown lane "${lane}". One of: ${LANES.join(", ")}`)
		const run = { job: J, mode: M, stack: S, lane: L, startedAt: new Date().toISOString(), gates: {} }
		writeRun(run)
		if (asJson) {
			console.log(JSON.stringify(run, null, 2))
		} else {
			console.log(`gate: run started ${J}/${M}/${S}, lane ${L}`)
			console.log(`gate: required ${requiredFor(run).join(" ")}`)
			console.log(`gate: state ${statePath()}`)
		}
		process.exit(0)
	}

	if (cmd === "pass") {
		const id = (args[1] || "").toUpperCase()
		const marker = args.slice(2).join(" ").trim()
		if (!GATES.includes(id)) die(`unknown gate "${args[1] || ""}". One of: ${GATES.join(", ")}`)
		const root = findRunRoot()
		const run = root ? readRun(root) : null
		if (!run) die("no run started. Run: node scripts/gate.mjs start <job> <mode> <stack> <lane>")
		if (!marker) die(`gate ${id} needs its marker text: node scripts/gate.mjs pass ${id} "<marker>"`)
		run.gates[id] = { at: new Date().toISOString(), marker }
		writeRun(run, root)
		const left = missingGates(run)
		if (asJson) {
			console.log(JSON.stringify(run.gates[id], null, 2))
		} else {
			console.log(`${id} ${marker}`)
			console.log(left.length ? `gate: still owed ${left.join(" ")}` : "gate: every required gate is recorded")
		}
		process.exit(0)
	}

	if (cmd === "status") {
		const run = findRun()
		if (!run) {
			if (asJson) console.log(JSON.stringify({ started: false }, null, 2))
			else console.log("gate: no run. Start one: node scripts/gate.mjs start <job> <mode> <stack> <lane>")
			process.exit(0)
		}
		const left = missingGates(run)
		if (asJson) {
			console.log(JSON.stringify({ started: true, ...run, missing: left }, null, 2))
			process.exit(0)
		}
		console.log(`gate: ${run.job}/${run.mode}/${run.stack}, lane ${run.lane}`)
		for (const g of GATES) {
			const hit = run.gates[g]
			const need = requiredFor(run).includes(g)
			if (hit) console.log(`  ${g} pass    ${hit.marker}`)
			else if (need) console.log(`  ${g} MISSING required for ${run.job}`)
		}
		console.log(left.length ? `gate: missing ${left.join(" ")}` : "gate: all required gates passed")
		process.exit(0)
	}

	if (cmd === "reset") {
		rmSync(stateDir(findRunRoot() || process.cwd()), { recursive: true, force: true })
		console.log("gate: run cleared")
		process.exit(0)
	}

	if (cmd === "log") {
		const opt = (name, fallback = "") => {
			const i = argv.findIndex((a) => a === `--${name}` || a.startsWith(`--${name}=`))
			if (i === -1) return fallback
			if (argv[i].includes("=")) return argv[i].split("=").slice(1).join("=")
			const next = argv[i + 1]
			return next && !next.startsWith("--") ? next : fallback
		}
		const logRoot = findRunRoot() || process.cwd()
		const run = readRun(logRoot)
		const paper = opt("paper").toLowerCase()
		const accent = opt("accent").toLowerCase()
		if (paper && !PAPER.includes(paper)) die(`--paper is one of: ${PAPER.join(", ")}`)
		if (accent && !ACCENT.includes(accent)) die(`--accent is one of: ${ACCENT.join(", ")}`)
		const entry = {
			surface: opt("surface") || (run ? `${run.job} ${run.mode}` : "unnamed surface"),
			world: opt("world"),
			palette: opt("palette"),
			type: opt("type"),
			structure: opt("structure"),
			nav: opt("nav"),
			footer: opt("footer"),
			paper,
			accent,
		}
		if (!entry.world) die('gate log needs at least --world: node scripts/gate.mjs log --surface "<what>" --world <name> ...')
		const saved = appendLog(entry, logRoot)
		if (asJson) console.log(JSON.stringify(saved, null, 2))
		else console.log(`gate: logged ${saved.surface}, world ${saved.world}, structure ${saved.structure || "-"} (${logPath(logRoot)})`)
		process.exit(0)
	}

	die("usage: node scripts/gate.mjs <start|pass|status|log|reset> [...]   see the header of this file")
}
