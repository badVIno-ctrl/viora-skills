#!/usr/bin/env node

/* viora-allow-file: this linter quotes Russian punctuation on purpose. Every
   example string here is either a violation or its correction. */

/**
 * ru.mjs - Russian typography, measured
 *
 *   node scripts/ru.mjs <paths>
 *   node scripts/ru.mjs src --summary
 *   node scripts/ru.mjs index.html --fix
 *   node scripts/ru.mjs --list-rules
 *
 * check.mjs bans the long dash because in English copy it is a model habit. In
 * Russian the dash is not a habit, it is grammar, and a hyphen in its place is
 * the single most common mistake on Russian pages. So Russian text gets its own
 * linter: quotes, dashes, non-breaking spaces, mixed alphabets, shouting caps.
 *
 * Only lines that contain Cyrillic are inspected. Code-looking lines are skipped.
 * Suppress one line with a trailing comment: viora-allow: <rule-id> <reason>.
 * Suppress a whole file with viora-allow-file anywhere in it.
 *
 * --fix applies only the mechanical corrections: spacing, non-breaking spaces,
 * ellipsis, dash, quotes. Everything else is a decision and stays yours.
 */

import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs"
import { extname, join, relative, resolve } from "node:path"

const NBSP = "\u00A0"
const THIN = "\u202F"
const DASH = "\u2014"
const ENDASH = "\u2013"
const ELLIPSIS = "\u2026"
const LAQUO = "\u00AB"
const RAQUO = "\u00BB"

const CYR = /[\u0410-\u044F\u0401\u0451]/
const MAX_BYTES = 400_000
const EXT = new Set([".html", ".htm", ".md", ".mdx", ".txt", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".js", ".ts", ".json"])
const SKIP_DIR = new Set([
	"node_modules", ".git", "dist", "build", "out", "coverage", ".next", ".nuxt",
	".svelte-kit", ".astro", ".turbo", ".vercel", ".cache", ".viora-shots", "data",
])

const ACRONYMS = new Set([
	"ООО", "ИНН", "КПП", "ОГРН", "НДС", "ГОСТ", "ФИО", "СНИЛС", "МКАД", "РФ",
	"АО", "ИП", "ЦБ", "ФНС", "ЖКХ", "СМИ", "ВУЗ", "ПДФ", "КАСКО", "ОСАГО", "ТЦК",
])

/* the letters that look identical in both alphabets. A single one of these,
   pasted into a Latin word, survives forever and breaks search silently. */
const HOMOGLYPH = new Set([..."АВЕКМНОРСТУХаеорсухк"])

/* every rule: id, severity, why it exists, how to spot it, how to fix it ---- */

const RULES = [
	{
		id: "quotes-straight",
		sev: "error",
		note: `Russian typography uses ${LAQUO}елочки${RAQUO}. Straight quotes are a typewriter artifact.`,
		custom: (line) => {
			/* a line that already shows the correct pair is teaching the rule, not
			   breaking it. And a quote after = is an attribute delimiter. */
			if (line.includes(LAQUO) || line.includes(RAQUO)) return []
			const re = /(?<![=\w])"([^"\n]*[\u0410-\u044F\u0401\u0451][^"\n]*)"/g
			return re.test(line) ? [`straight quotes around Russian text, use ${LAQUO} ${RAQUO}`] : []
		},
		fix: (line) => line.replace(/(?<![=\w])"([^"\n]*[\u0410-\u044F\u0401\u0451][^"\n]*)"/g, `${LAQUO}$1${RAQUO}`),
	},
	{
		id: "quotes-english",
		sev: "warn",
		note: `English curly quotes in Russian copy. The Russian pair is ${LAQUO} ${RAQUO}, the inner pair is \u201E \u201C.`,
		re: /[\u201C\u201D]/g,
		msg: `English curly quote in Russian text, use ${LAQUO} ${RAQUO}`,
		fix: (line) => line.replace(/\u201C([^\u201D\n]*)\u201D/g, `${LAQUO}$1${RAQUO}`),
	},
	{
		id: "hyphen-as-dash",
		sev: "error",
		note: `A hyphen between words is not a dash. Russian uses ${DASH} with spaces around it.`,
		re: /[\u0410-\u044F\u0401\u0451]\s-\s/g,
		msg: `hyphen used as a dash, Russian needs ${DASH}`,
		fix: (line) => line.replace(/([\u0410-\u044F\u0401\u0451])\s-\s/g, `$1 ${DASH} `),
	},
	{
		id: "range-hyphen",
		sev: "warn",
		note: `A numeric range takes ${ENDASH} with no spaces: 5${ENDASH}7 дней.`,
		re: /\d-\d/g,
		msg: `numeric range with a hyphen, use ${ENDASH}`,
		fix: (line) => line.replace(/(\d)-(\d)/g, `$1${ENDASH}$2`),
	},
	{
		id: "nbsp-money",
		sev: "warn",
		note: "A currency sign must never wrap onto the next line away from its number.",
		re: /\d[ ](?:\u20BD|\u20AC|\$|руб)/g,
		msg: "ordinary space before a currency sign, use a non-breaking space",
		fix: (line) => line.replace(/(\d)[ ](\u20BD|\u20AC|\$|руб)/g, `$1${NBSP}$2`),
	},
	{
		id: "nbsp-unit",
		sev: "warn",
		note: "A unit belongs to its number. Wrapping between them reads as two facts.",
		re: /\d[ ](?:кг|г|км|м|мм|см|мл|л|ч|мин|сек|шт|дней|дня|лет|года?)(?![\u0410-\u044F\u0401\u0451])/g,
		msg: "ordinary space between a number and its unit, use a non-breaking space",
		fix: (line) =>
			line.replace(
				/(\d)[ ](кг|г|км|м|мм|см|мл|л|ч|мин|сек|шт|дней|дня|лет|года?)(?![\u0410-\u044F\u0401\u0451])/g,
				`$1${NBSP}$2`,
			),
	},
	{
		id: "nbsp-abbrev",
		sev: "warn",
		note: "An abbreviation and its number are one unit: ул.\u00A0Ленина, 5\u00A0тыс.",
		re: /\b(?:ул|г|д|стр|кв|тыс|млн|млрд|рис|таб)\.[ ]\S/g,
		msg: "ordinary space after an abbreviation, use a non-breaking space",
		fix: (line) => line.replace(/\b(ул|г|д|стр|кв|тыс|млн|млрд|рис|таб)\.[ ](\S)/g, `$1.${NBSP}$2`),
	},
	{
		id: "thousands-run-on",
		sev: "warn",
		note: `Five digits in a row cannot be read at a glance. Group them: 5${THIN}000.`,
		re: /(?<![\d.,:\-\u2013])\d{5,}(?![\d.,:\-\u2013])/g,
		msg: "long number with no grouping, separate thousands with a thin non-breaking space",
	},
	{
		id: "ellipsis-dots",
		sev: "warn",
		note: `Three periods is not an ellipsis. The character is ${ELLIPSIS}.`,
		re: /\.\.\./g,
		msg: `three periods instead of ${ELLIPSIS}`,
		fix: (line) => line.replace(/\.\.\./g, ELLIPSIS),
	},
	{
		id: "space-before-punct",
		sev: "error",
		note: "No space before a comma, period, colon, question or exclamation mark.",
		re: /[\u0410-\u044F\u0401\u0451][ ]+[,.;:!?]/g,
		msg: "space before punctuation",
		fix: (line) => line.replace(/([\u0410-\u044F\u0401\u0451])[ ]+([,.;:!?])/g, "$1$2"),
	},
	{
		id: "space-after-punct",
		sev: "error",
		note: "A comma or colon is always followed by a space.",
		re: /[\u0410-\u044F\u0401\u0451][,:;](?=[\u0410-\u044F\u0401\u0451])/g,
		msg: "missing space after punctuation",
		fix: (line) => line.replace(/([\u0410-\u044F\u0401\u0451])([,:;])(?=[\u0410-\u044F\u0401\u0451])/g, "$1$2 "),
	},
	{
		id: "double-space",
		sev: "warn",
		note: "Two spaces inside a sentence is a leftover, not a rhythm.",
		re: /[\u0410-\u044F\u0401\u0451][ ]{2,}\S/g,
		msg: "double space inside Russian text",
		fix: (line) => line.replace(/([\u0410-\u044F\u0401\u0451])[ ]{2,}(\S)/g, "$1 $2"),
	},
	{
		id: "mixed-alphabet",
		sev: "error",
		note: "A Latin letter inside a Russian word survives copy-paste and breaks search, spellcheck and screen readers.",
		custom: (line) => {
			const hits = []
			for (const word of line.split(/[^\p{L}]+/u)) {
				if (word.length < 3) continue
				const cyr = (word.match(/[\u0410-\u044F\u0401\u0451]/g) || []).length
				const lat = (word.match(/[A-Za-z]/g) || []).length
				if (cyr === 0 || lat === 0) continue
				/* the defect runs both ways: a Latin letter inside a Russian word, and
				   a Cyrillic look-alike hiding inside a Latin one */
				const latinWithImpostor = lat >= 2 && [...word].every((ch) => !CYR.test(ch) || HOMOGLYPH.has(ch))
				if (cyr >= 2 || latinWithImpostor) hits.push(word)
			}
			return hits.map((w) => `mixed Cyrillic and Latin in one word: ${w}`)
		},
	},
	{
		id: "caps-shouting",
		sev: "warn",
		note: "Russian in all caps loses its word shapes and reads slower. Use weight or size instead.",
		custom: (line) => {
			const hits = []
			for (const word of line.match(/[\u0410-\u042F\u0401]{4,}/g) || []) {
				if (!ACRONYMS.has(word)) hits.push(word)
			}
			return hits.slice(0, 2).map((w) => `Russian word in all caps: ${w}`)
		},
	},
	{
		id: "title-case-ru",
		sev: "warn",
		note: "Russian headings are sentence case. Capitalising Every Word is an English convention.",
		custom: (line) => {
			const heading = line.match(/^#{1,6}\s+(.+)$/) || line.match(/<h[1-6][^>]*>([^<]{4,})<\/h[1-6]>/)
			if (!heading) return []
			const words = heading[1].trim().split(/\s+/)
			if (words.length < 3) return []
			const caps = words.slice(1).filter((w) => /^[\u0410-\u042F\u0401]/.test(w))
			return caps.length >= 2 ? [`Title Case in a Russian heading: ${caps.slice(0, 3).join(" ")}`] : []
		},
	},
]

/* ------------------------------------------------------------------ scanning */

const argv = process.argv.slice(2)
const flags = new Set(argv.filter((a) => a.startsWith("--")))
const has = (name) => flags.has(`--${name}`)
const targets = argv.filter((a) => !a.startsWith("--"))

if (has("list-rules")) {
	for (const r of RULES) console.log(`${r.sev.padEnd(6)} ${r.id.padEnd(20)} ${r.note}`)
	console.log(`\n${RULES.length} rules. Only lines containing Cyrillic are inspected.`)
	process.exit(0)
}
if (targets.length === 0) targets.push(".")

const looksLikeCode = (line) =>
	/=>|===|!==|&&|\|\||\bimport\b|\bexport\b|\bfunction\b|\bconst\b|\blet\b|\breturn\b|^\s*[.#][\w-]+\s*\{|^\s*\/\//.test(line) ||
	/* frontmatter and config values are data, not prose. Rewriting quotes there
	   breaks the file. ASCII keys only, so Russian sentences with a colon stay in. */
	/^\s*[\w-]+:\s+\S/.test(line) ||
	/^\s*"[\w-]+":/.test(line)

const files = []
const walk = (p, depth = 0) => {
	if (depth > 8) return
	let s
	try {
		s = statSync(p)
	} catch {
		return
	}
	if (s.isDirectory()) {
		for (const e of readdirSync(p, { withFileTypes: true })) {
			if (e.isDirectory() && (SKIP_DIR.has(e.name) || e.name.startsWith("."))) continue
			walk(join(p, e.name), depth + 1)
		}
		return
	}
	if (!EXT.has(extname(p))) return
	if (s.size > MAX_BYTES) return
	files.push(p)
}
for (const t of targets) walk(resolve(t))

const findings = []
let scanned = 0
let fixedFiles = 0

for (const file of files) {
	let text = ""
	try {
		text = readFileSync(file, "utf8")
	} catch {
		continue
	}
	if (!CYR.test(text)) continue
	if (text.includes("viora-allow-file")) continue
	scanned++
	const lines = text.split("\n")
	let changed = false
	let inFence = false

	lines.forEach((line, i) => {
		/* fenced code is a command or a snippet, not prose. Rewriting quotes inside
		   a shell line breaks the command it is teaching. */
		if (/^\s*(```|~~~)/.test(line)) {
			inFence = !inFence
			return
		}
		if (inFence) return
		if (!CYR.test(line) || looksLikeCode(line)) return
		const allowed = (line.match(/viora-allow:\s*([a-z-]+)/) || [])[1]
		for (const rule of RULES) {
			if (allowed === rule.id) continue
			const messages = rule.custom
				? rule.custom(line)
				: (line.match(rule.re) || []).length > 0
					? [rule.msg]
					: []
			for (const msg of messages) {
				findings.push({ file, line: i + 1, id: rule.id, sev: rule.sev, msg })
			}
			if (has("fix") && rule.fix && messages.length > 0) {
				const next = rule.fix(lines[i])
				if (next !== lines[i]) {
					lines[i] = next
					changed = true
				}
			}
		}
	})

	if (changed) {
		writeFileSync(file, lines.join("\n"))
		fixedFiles++
	}
}

/* -------------------------------------------------------------------- report */

const errors = findings.filter((f) => f.sev === "error").length
const warnings = findings.length - errors
const rel = (p) => {
	const r = relative(process.cwd(), p)
	return !r || r.startsWith("..") ? p : r
}

if (has("json")) {
	console.log(JSON.stringify({ scanned, errors, warnings, fixedFiles, findings: findings.map((f) => ({ ...f, file: rel(f.file) })) }, null, 2))
	process.exit(errors > 0 || (has("strict") && warnings > 0) ? 1 : 0)
}

if (!has("summary")) {
	for (const f of findings) {
		console.log(`${rel(f.file)}:${f.line}  ${f.sev === "error" ? "error" : "warn "}  ${f.id.padEnd(20)} ${f.msg}`)
	}
	if (findings.length) console.log("")
}

if (findings.length === 0) {
	console.log(`ru: ${scanned} files with Russian text, pass`)
	process.exit(0)
}

console.log(`ru: ${scanned} files with Russian text, ${errors} errors, ${warnings} warnings`)
if (has("fix")) console.log(`fixed mechanically in ${fixedFiles} files. Re-run to see what is left.`)
else console.log("mechanical part is fixable: node scripts/ru.mjs <paths> --fix")
console.log("what --fix will not touch: caps, Title Case, mixed alphabets, long numbers. Those are decisions.")
console.log(`the dash rule here overrides check.mjs em-dash: in Russian ${DASH} is grammar, not slop.`)
process.exit(errors > 0 || (has("strict") && warnings > 0) ? 1 : 0)
