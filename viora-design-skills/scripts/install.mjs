#!/usr/bin/env node

/**
 * install.mjs - put this skill where the agent will actually find it
 *
 *   node scripts/install.mjs                 install into the current directory
 *   node scripts/install.mjs --into ../app   install into another project
 *   node scripts/install.mjs --dry-run       print the plan and change nothing
 *   node scripts/install.mjs --only agents    one target only
 *
 * A skill nobody loads is a folder nobody reads. Every agent looks in a
 * different place, so this writes the pointer in each of them:
 *
 *   .claude/skills/viora-design-skills/   full copy, Claude Code loads it by name
 *   AGENTS.md                             Codex, Amp, Jules, and most CLI agents
 *   GEMINI.md                             Gemini CLI
 *   .cursor/rules/viora-design.mdc        Cursor
 *   .github/copilot-instructions.md       Copilot
 *
 * The pointer block is delimited by markers, so running this twice replaces the
 * block instead of appending a second copy. Everything outside the markers is
 * left exactly as it was.
 */

import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { basename, dirname, join, relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const SKILL = resolve(join(HERE, ".."))
const NAME = basename(SKILL)

const argv = process.argv.slice(2)
const value = (flag, fallback = "") => {
	const i = argv.findIndex((a) => a === `--${flag}` || a.startsWith(`--${flag}=`))
	if (i === -1) return fallback
	if (argv[i].includes("=")) return argv[i].split("=").slice(1).join("=")
	return argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : fallback
}
const dryRun = argv.includes("--dry-run")
const only = String(value("only", ""))
const project = resolve(String(value("into", process.cwd())))

if (project === SKILL) {
	console.error("install: the target is the skill folder itself. Run this from the project you are designing,")
	console.error(`or pass one: node ${relative(process.cwd(), join(HERE, "install.mjs")) || "scripts/install.mjs"} --into ../my-app`)
	process.exit(2)
}
if (!existsSync(project)) {
	console.error(`install: no such directory: ${project}`)
	process.exit(2)
}

const START = "<!-- viora-design-skills: start -->"
const END = "<!-- viora-design-skills: end -->"

/* Where the copy will live, and how a document should point at it. The pointer
   has to survive a model that reads nothing else, so it carries the four rules
   that matter most and the two commands that make everything else discoverable. */
const copyTarget = join(project, ".claude", "skills", NAME)
const installedPath = existsSync(copyTarget) || !dryRun ? join(".claude", "skills", NAME) : NAME

const pointer = (path) =>
	[
		START,
		`## Design work: use ${NAME}`,
		"",
		`Any request to design, build, restyle, review or fix an interface goes through this skill. It lives at \`${path}\`.`,
		"",
		`1. Decide the lane first: \`node ${path}/scripts/lane.mjs --probe\`. Answer its three questions from the files, not from memory. Three right answers means read \`${path}/SKILL.md\` and work the full seven gates. Fewer means read \`${path}/LITE.md\` and only that file.`,
		`2. Never mix lanes. LITE is one file and eight recipes. FULL routes across \`${path}/reference/\`.`,
		`3. Verify with the scripts, not with adjectives: \`node ${path}/scripts/verify.mjs <paths>\`. Errors are not optional, and a page nobody looked at is not verified.`,
		`4. Do not read \`${path}/data/*.csv\` or \`${path}/assets/tokens.css\` into context. Query the catalog with \`node ${path}/scripts/pick.mjs "<what you are building>" --system\`, copy the token file into the project.`,
		"",
		"Hard floor, whatever the lane: no long dashes as punctuation, no eyebrow labels above headings, no gradient text, no scroll cues, one accent colour, `transition` names its properties, every colour comes from a token, and `prefers-reduced-motion` ships in the same commit as the animation.",
		END,
	].join("\n")

const plan = []

/* 1. the copy Claude Code loads by name */
if (!only || only === "claude") {
	plan.push({
		what: join(".claude", "skills", NAME),
		how: existsSync(copyTarget) ? "replace folder" : "copy folder",
		run: () => {
			mkdirSync(dirname(copyTarget), { recursive: true })
			cpSync(SKILL, copyTarget, {
				recursive: true,
				filter: (src) => !/(^|\/)(\.git|node_modules|\.viora-shots)(\/|$)/.test(src),
			})
		},
	})
}

/* 2. the documents every other agent reads */
const docs = [
	["agents", "AGENTS.md"],
	["gemini", "GEMINI.md"],
	["cursor", join(".cursor", "rules", "viora-design.mdc")],
	["copilot", join(".github", "copilot-instructions.md")],
]
for (const [key, file] of docs) {
	if (only && only !== key) continue
	const full = join(project, file)
	const exists = existsSync(full)
	const current = exists ? readFileSync(full, "utf8") : ""
	const already = current.includes(START)
	plan.push({
		what: file,
		how: !exists ? "create with pointer" : already ? "replace pointer block" : "append pointer block",
		run: () => {
			mkdirSync(dirname(full), { recursive: true })
			const block = pointer(installedPath)
			if (already) {
				const head = current.slice(0, current.indexOf(START))
				const tail = current.slice(current.indexOf(END) + END.length)
				writeFileSync(full, `${head}${block}${tail}`)
				return
			}
			/* Cursor rules need frontmatter to apply automatically */
			const frontmatter =
				file.endsWith(".mdc") && !current
					? "---\ndescription: Design and build interfaces with the Viora design skill\nalwaysApply: true\n---\n\n"
					: ""
			const spacer = current && !current.endsWith("\n\n") ? (current.endsWith("\n") ? "\n" : "\n\n") : ""
			writeFileSync(full, `${current}${spacer}${frontmatter}${block}\n`)
		},
	})
}

if (!plan.length) {
	console.error(`install: --only ${only} matched nothing. Use claude, agents, gemini, cursor or copilot.`)
	process.exit(2)
}

/* ------------------------------------------------------------------- report */

console.log(`${NAME} -> ${project}`)
console.log("-".repeat(72))
for (const step of plan) {
	if (dryRun) {
		console.log(`would ${step.how.padEnd(22)} ${step.what}`)
		continue
	}
	try {
		step.run()
		console.log(`${step.how.padEnd(22)} ${step.what}`)
	} catch (error) {
		console.log(`failed                 ${step.what}: ${error.message}`)
		process.exitCode = 1
	}
}
console.log("-".repeat(72))
if (dryRun) {
	console.log("dry run, nothing was written. Drop --dry-run to apply.")
	process.exit(0)
}
console.log("installed. Two things to check once:")
console.log(`  1. node ${installedPath}/scripts/selftest.mjs   the skill's own scripts still run here`)
console.log(`  2. node ${installedPath}/scripts/lane.mjs --probe   the lane the current model belongs in`)
console.log("Commit the pointer files. An agent that cannot see the pointer will invent its own design system.")
