#!/usr/bin/env node
/**
 * viora-design-skills / wig.mjs
 *
 * Web interface rules linter. Grades the implementation, not the design.
 * check.mjs catches slop and craft. This one catches the interface defects a reviewer
 * points at with a file and a line: blocked paste, unlabelled controls, hand rolled
 * date formatting, layout reads in render, missing safe areas, a hero image marked lazy.
 *
 * Zero dependencies. Node 18+. No network.
 *
 *   node wig.mjs .
 *   node wig.mjs src/components app/page.tsx
 *   node wig.mjs . --summary
 *   node wig.mjs . --json
 *   node wig.mjs . --github
 *   node wig.mjs . --strict          warnings fail too
 *   node wig.mjs . --ignore-rule nbsp-units,button-no-type
 *   node wig.mjs --list-rules
 *
 * Suppress a finding with a comment containing "viora-allow: rule-id reason" on the
 * offending line or the line above it. Suppress a whole file with a comment containing
 * "viora-allow-file: reason" in the first 2000 characters.
 *
 * Exit 1 means at least one error remains. Rules are in reference/14-interface-rules.md.
 */

import { readFileSync, statSync, readdirSync, existsSync } from "node:fs"
import { join, extname, basename, relative } from "node:path"

/* ------------------------------------------------------------------ scope */

const SKIP_DIRS = new Set([
	"node_modules", ".git", ".svn", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit",
	"coverage", ".turbo", ".vercel", ".cache", "vendor", "target", ".viora-shots",
	"viora-design-skills", ".claude", ".codex", ".cursor", ".gemini", ".opencode", ".github",
])
const SELF = new Set(["wig.mjs", "pick.mjs", "check.mjs", "contrast.mjs", "shot.mjs", "verify.mjs", "selftest.mjs"])

const MARKUP = new Set([".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".php", ".erb", ".twig"])
const SCRIPT = new Set([".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro"])
const STYLE = new Set([".css", ".scss", ".sass", ".less", ".pcss"])
const JSXY = new Set([".jsx", ".tsx", ".vue", ".svelte", ".astro"])
const ALL = new Set([...MARKUP, ...SCRIPT, ...STYLE])
const MAX_BYTES = 400_000

/* ------------------------------------------------------------------ rules */

const L = (id, sev, ext, re, msg, opts = {}) => ({ kind: "line", id, sev, ext, re, msg, ...opts })
const F = (id, sev, ext, has, lacks, at, msg) => ({ kind: "file", id, sev, ext, has, lacks, at, msg })

const RULES = [
	/* --- accessibility and forms ---------------------------------------- */
	L("paste-blocked", "error", SCRIPT, /on[Pp]aste[^\n]{0,80}preventDefault/, "paste blocked, password managers break"),
	L("zoom-blocked", "error", MARKUP, /user-scalable\s*=\s*(no|0)|maximum-scale\s*=\s*["']?1(\.0)?["']?/, "zoom blocked in the viewport meta"),
	L("value-no-onchange", "error", JSXY, /<input(?=[^>]*\svalue=\{)(?![^>]*(onChange|onInput|readOnly|readonly|disabled))[^>]*>/, "controlled input without onChange, use defaultValue"),
	L("autocomplete-missing", "warn", MARKUP, /<input(?=[^>]*type=["'](email|password|tel|url)["'])(?![^>]*autocomplete)[^>]*>/i, "input without autocomplete"),
	L("spellcheck-on-token", "warn", MARKUP, /<input(?=[^>]*(type=["']email["']|name=["'](email|username|code|token|otp)["']))(?![^>]*spellcheck)[^>]*>/i, "email or code input without spellcheck=false"),
	L("submit-gated", "warn", JSXY, /disabled=\{\s*!\s*(isValid|valid|isDirty|canSubmit|formValid)/, "submit disabled before submit, keep it enabled and show the error"),
	L("button-no-type", "warn", JSXY, /<button(?![^>]*type=)[^>]*>/, "button without type, defaults to submit inside a form"),
	L("link-no-href", "error", MARKUP, /<a(?![^>]*href=)[^>]*on[Cc]lick/, "anchor with a click handler and no href"),
	L("link-hash-onclick", "warn", MARKUP, /<a[^>]*href=["']#["'][^>]*on[Cc]lick/, "href=# with a handler, use a button"),
	L("iframe-no-title", "warn", MARKUP, /<iframe(?![^>]*title=)/i, "iframe without title"),
	L("autofocus", "warn", MARKUP, /\bautoFocus\b|\bautofocus\b/, "autofocus, desktop only and one input at most"),

	/* --- content and copy ----------------------------------------------- */
	L("three-periods", "warn", MARKUP, /[\p{L}\p{N}]\.{3}(?!\.)/u, "three periods, use the ellipsis character"),
	L("loading-no-ellipsis", "warn", MARKUP, /\b(Loading|Saving|Uploading|Deleting|Sending|Processing|\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430|\u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0435|\u041e\u0442\u043f\u0440\u0430\u0432\u043a\u0430)\s*(?=<\/|["'`}])/, "progress label without a trailing ellipsis"),
	L("nbsp-units", "warn", MARKUP, /(?:^|[>\s"'`])\d+ (MB|KB|GB|TB|ms|px|pt)\b/, "unit split from its number, use a non breaking space"),
	L("flex-truncate-minw", "warn", MARKUP, /flex[^"'`\n]{0,80}\b(truncate|line-clamp-\d)/, "truncating flex child without min-w-0", { not: /min-w-0/ }),

	/* --- locale and formatting ------------------------------------------ */
	L("hand-date", "error", SCRIPT, /getMonth\(\)\s*\+\s*1|\bMM\/DD\/YYYY\b|\bDD\/MM\/YYYY\b|\bDD\.MM\.YYYY\b/, "hand formatted date, use Intl.DateTimeFormat"),
	L("hand-number", "warn", SCRIPT, /["'`]\$["'`]\s*\+|\+\s*["'`]\s*\$|toFixed\(2\)\s*\+/, "hand formatted currency, use Intl.NumberFormat"),

	/* --- performance and rendering -------------------------------------- */
	L("lazy-priority-conflict", "error", MARKUP, /loading=["']lazy["'][^>]*fetchpriority=["']high["']|fetchpriority=["']high["'][^>]*loading=["']lazy["']/, "image is both lazy and high priority"),
	L("gif-media", "warn", ALL, /["'(][^"'()\s]+\.gif\b/i, "animated gif, use a muted looping video"),
	L("layout-read", "warn", SCRIPT, /getBoundingClientRect\(|\.offsetHeight\b|\.offsetWidth\b|\.scrollHeight\b/, "layout read outside an effect or handler", { context: /useEffect|useLayoutEffect|requestAnimationFrame|addEventListener|onClick|onScroll|handle|function |=>\s*\{/, contextSpan: 6 }),
	L("random-in-render", "warn", JSXY, /\{[^{}]*Math\.random\(\)[^{}]*\}/, "random value in render, hydration mismatch"),
	L("date-in-render", "warn", JSXY, /\{[^{}]*new Date\(\)\s*\.[A-Za-z]+\([^{}]*\}/, "current time rendered directly, hydration mismatch"),

	/* --- state and destruction ------------------------------------------ */
	L("destructive-bare", "warn", JSXY, /on(?:Click|Press)=\{[^}\n]*\b(delete|remove|destroy|drop)[A-Za-z_]*\(/i, "destructive action without confirmation or undo in this file", { fileLacks: /confirm|Confirm|undo|Undo|AlertDialog|areYouSure/ }),
	L("url-state", "warn", JSXY, /useState[^\n]*\b(tab|activeTab|filter|filters|page|sort|sortBy|query|search)\b/i, "shareable state in useState, put it in the URL", { fileLacks: /useSearchParams|searchParams|URLSearchParams|pushState|useRouter|\$route|nuqs/ }),

	/* --- file level ------------------------------------------------------ */
	F("overscroll-missing", "warn", STYLE, /\.(modal|dialog|drawer|sheet|overlay)\b|\[role=["']dialog/, /overscroll-behavior/, /\.(modal|dialog|drawer|sheet|overlay)\b|\[role=["']dialog/, "overlay without overscroll-behavior: contain"),
	F("color-scheme-missing", "warn", STYLE, /prefers-color-scheme:\s*dark|\.dark\s*[,{]|\[data-theme=["']dark/, /color-scheme/, /prefers-color-scheme:\s*dark|\.dark\s*[,{]|\[data-theme=["']dark/, "dark theme without color-scheme, native controls stay light"),
	F("safe-area-missing", "warn", STYLE, /position:\s*fixed/, /env\(safe-area-inset/, /position:\s*fixed/, "fixed layer without env(safe-area-inset-*)"),
	F("touch-action-missing", "warn", STYLE, /cursor:\s*pointer/, /touch-action/, /cursor:\s*pointer/, "interactive styles without touch-action: manipulation"),
	F("text-wrap-missing", "warn", STYLE, /(^|[\s,>])h[12]\s*[,{]/m, /text-wrap/, /(^|[\s,>])h[12]\s*[,{]/m, "headings without text-wrap: balance"),
	F("font-display-missing", "warn", STYLE, /@font-face/, /font-display/, /@font-face/, "@font-face without font-display: swap"),
	F("preconnect-missing", "warn", MARKUP, /fonts\.googleapis\.com|fonts\.gstatic\.com/, /rel=["']preconnect/, /fonts\.googleapis\.com|fonts\.gstatic\.com/, "remote fonts without preconnect"),
	F("theme-color-missing", "warn", new Set([".html", ".htm"]), /<head[\s>]/, /name=["']theme-color/, /<head[\s>]/, "no theme-color meta, browser chrome fights the page"),
	F("aria-live-missing", "warn", MARKUP, /toast|snackbar|notification|Toast|Snackbar/, /aria-live|role=["'](status|alert)/, /toast|snackbar|notification|Toast|Snackbar/, "async message region without aria-live"),
	F("escape-close-missing", "warn", MARKUP, /role=["']dialog|<dialog|Modal|Drawer|Sheet/, /Escape|keydown|onKeyDown|<dialog|useDialog|showModal/, /role=["']dialog|<dialog|Modal|Drawer|Sheet/, "overlay with no Escape handling"),
	F("drag-no-keyboard", "warn", MARKUP, /onDrag(Start|End|Over)?=|draggable=["']true/, /onKeyDown|onKeyUp|keydown/, /onDrag(Start|End|Over)?=|draggable=["']true/, "drag interaction with no keyboard alternative"),
	F("tabular-nums-missing", "warn", MARKUP, /<td[^>]*>\s*[\d\u2212-]/, /tabular-nums|tabular_nums|font-variant-numeric/, /<td[^>]*>\s*[\d\u2212-]/, "numeric table without tabular-nums"),
]

/* ------------------------------------------------------------------ args */

const argv = process.argv.slice(2)
const wants = (n) => argv.includes(`--${n}`)
const valueOf = (n, fb = "") => {
	const i = argv.findIndex((a) => a === `--${n}` || a.startsWith(`--${n}=`))
	if (i === -1) return fb
	if (argv[i].includes("=")) return argv[i].split("=").slice(1).join("=")
	return argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : fb
}

if (wants("explain")) {
	const { spawnSync } = await import("node:child_process")
	const id = process.argv.slice(2).find((a) => !a.startsWith("-"))
	const run = spawnSync(
		process.execPath,
		[new URL("./explain.mjs", import.meta.url).pathname, ...(id ? [id] : ["--all"])],
		{ stdio: "inherit" },
	)
	process.exit(run.status ?? 0)
}

if (wants("list-rules")) {
	for (const r of RULES) console.log(`${r.sev.padEnd(6)}${r.id.padEnd(24)}${r.msg}`)
	process.exit(0)
}

const ignored = new Set(String(valueOf("ignore-rule", "")).split(",").map((s) => s.trim()).filter(Boolean))
const strict = wants("strict")
const asJson = wants("json")
const summaryOnly = wants("summary")
const targets = []
for (let i = 0; i < argv.length; i++) {
	const a = argv[i]
	if (a.startsWith("--")) {
		if (a === "--ignore-rule") i++
		continue
	}
	targets.push(a)
}
if (!targets.length) targets.push(".")

/* ------------------------------------------------------------------ walk */

function walk(dir, out) {
	let entries
	try {
		entries = readdirSync(dir, { withFileTypes: true })
	} catch {
		return out
	}
	for (const e of entries) {
		if (e.name.startsWith(".") && e.name !== ".") {
			if (!SKIP_DIRS.has(e.name)) {
				/* hidden folders are skipped unless explicitly targeted */
			}
			if (e.isDirectory()) continue
		}
		const p = join(dir, e.name)
		if (e.isDirectory()) {
			if (SKIP_DIRS.has(e.name)) continue
			walk(p, out)
		} else if (ALL.has(extname(e.name).toLowerCase()) && !SELF.has(basename(e.name))) {
			out.push(p)
		}
	}
	return out
}

const files = []
for (const t of targets) {
	if (!existsSync(t)) {
		console.error(`not found: ${t}`)
		process.exit(2)
	}
	const st = statSync(t)
	if (st.isDirectory()) walk(t, files)
	else if (ALL.has(extname(t).toLowerCase())) files.push(t)
}

/* ------------------------------------------------------------------ scan */

const findings = []
let clean = 0
let scanned = 0

for (const file of files) {
	let content
	try {
		if (statSync(file).size > MAX_BYTES) continue
		content = readFileSync(file, "utf8")
	} catch {
		continue
	}
	if (content.slice(0, 2000).includes("viora-allow-file")) continue
	scanned++
	const ext = extname(file).toLowerCase()
	const lines = content.split("\n")
	const before = findings.length

	const suppressed = (i, id) => {
		const here = lines[i] || ""
		const above = lines[i - 1] || ""
		const tag = `viora-allow:`
		for (const l of [here, above]) {
			const at = l.indexOf(tag)
			if (at !== -1 && l.slice(at + tag.length, at + tag.length + 60).includes(id)) return true
		}
		return false
	}

	for (const rule of RULES) {
		if (ignored.has(rule.id)) continue
		if (!rule.ext.has(ext)) continue

		if (rule.kind === "file") {
			if (!rule.has.test(content)) continue
			if (rule.lacks.test(content)) continue
			let at = 0
			for (let i = 0; i < lines.length; i++) {
				if (rule.at.test(lines[i])) {
					at = i
					break
				}
			}
			if (suppressed(at, rule.id)) continue
			findings.push({ file, line: at + 1, id: rule.id, sev: rule.sev, msg: rule.msg })
			continue
		}

		if (rule.fileLacks && rule.fileLacks.test(content)) continue
		for (let i = 0; i < lines.length; i++) {
			const line = lines[i]
			if (!line || line.length > 2000) continue
			if (!rule.re.test(line)) continue
			if (rule.not && rule.not.test(line)) continue
			if (rule.context) {
				const span = rule.contextSpan || 5
				const near = lines.slice(Math.max(0, i - span), i + span).join("\n")
				if (rule.context.test(near)) continue
			}
			if (suppressed(i, rule.id)) continue
			findings.push({ file, line: i + 1, id: rule.id, sev: rule.sev, msg: rule.msg })
		}
	}
	if (findings.length === before) clean++
}

/* ---------------------------------------------------------------- report */

const errors = findings.filter((f) => f.sev === "error").length
const warnings = findings.length - errors

if (wants("github")) {
	/* GitHub Actions annotations: every interface defect gets a line in the diff */
	for (const f of findings) {
		const kind = f.sev === "error" ? "error" : "warning"
		const where = relative(process.cwd(), f.file) || f.file
		console.log(`::${kind} file=${where},line=${Math.max(1, f.line || 1)},title=viora ${f.id}::${String(f.msg).replace(/\s+/g, " ")}`)
	}
	console.log(`viora wig: ${errors} errors, ${warnings} warnings across ${scanned} files`)
	process.exit(errors > 0 || (strict && warnings > 0) ? 1 : 0)
}

if (asJson) {
	console.log(JSON.stringify({ scanned, clean, errors, warnings, findings }, null, 2))
	process.exit(errors > 0 || (strict && warnings > 0) ? 1 : 0)
}

if (summaryOnly) {
	const byRule = new Map()
	for (const f of findings) byRule.set(f.id, (byRule.get(f.id) || 0) + 1)
	console.log(`wig: ${scanned} files, ${errors} errors, ${warnings} warnings`)
	console.log("why: node scripts/explain.mjs <rule-id>")
	for (const [id, n] of [...byRule.entries()].sort((a, b) => b[1] - a[1])) {
		const rule = RULES.find((r) => r.id === id)
		console.log(`  ${String(n).padStart(3)}  ${rule.sev.padEnd(6)}${id}`)
	}
	process.exit(errors > 0 || (strict && warnings > 0) ? 1 : 0)
}

if (!findings.length) {
	console.log(`wig: ${scanned} files, pass`)
	process.exit(0)
}

const grouped = new Map()
for (const f of findings) {
	if (!grouped.has(f.file)) grouped.set(f.file, [])
	grouped.get(f.file).push(f)
}
for (const [file, list] of grouped) {
	console.log(`\n## ${relative(process.cwd(), file) || file}`)
	console.log("")
	for (const f of list.sort((a, b) => a.line - b.line)) {
		const rel = relative(process.cwd(), f.file) || f.file
		console.log(`${rel}:${f.line} - ${f.msg} [${f.id}]`)
	}
}
console.log(`\n${errors} error(s), ${warnings} warning(s) across ${grouped.size} file(s). ${clean} file(s) clean.`)
if (errors) {
	const worst = findings.find((f) => f.sev === "error")
	console.log(`start with: ${relative(process.cwd(), worst.file) || worst.file}:${worst.line} ${worst.msg}`)
}
process.exit(errors > 0 || (strict && warnings > 0) ? 1 : 0)
