#!/usr/bin/env node
/**
 * viora-design-skills / contrast.mjs
 *
 * Measures WCAG contrast over a token file so "4.5:1" is a fact, not a claim.
 * Zero dependencies. Node 18+.
 *
 *   node contrast.mjs assets/tokens.css          check the pair contract
 *   node contrast.mjs src/styles/tokens.css --json
 *   node contrast.mjs tokens.css --all           every ink/surface combination
 *   node contrast.mjs --pair "#5b5b5b" "#ffffff"
 *
 * Understands hex, rgb(), hsl(), oklch(), var() references and
 * color-mix(in oklab|srgb, A p%, B) - the forms the token file actually uses.
 *
 * Exit 1 means at least one required pair failed. Change the palette, not the target.
 */

import { readFileSync, existsSync } from "node:fs"

/* --------------------------------------------------------------- colour math */

const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x)

const srgbToLinear = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
const linearToSrgb = (c) =>
	c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(clamp01(c), 1 / 2.4) - 0.055

function linearToOklab([r, g, b]) {
	const l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
	const m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
	const s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
	const l_ = Math.cbrt(l)
	const m_ = Math.cbrt(m)
	const s_ = Math.cbrt(s)
	return [
		0.2104542553 * l_ + 0.793617785 * m_ - 0.0040720468 * s_,
		1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_,
		0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_,
	]
}

function oklabToLinear([L, A, B]) {
	const l_ = L + 0.3963377774 * A + 0.2158037573 * B
	const m_ = L - 0.1055613458 * A - 0.0638541728 * B
	const s_ = L - 0.0894841775 * A - 1.291485548 * B
	const l = l_ * l_ * l_
	const m = m_ * m_ * m_
	const s = s_ * s_ * s_
	return [
		4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
		-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
		-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
	]
}

function oklchToLinear(L, C, Hdeg) {
	const h = (Hdeg * Math.PI) / 180
	return oklabToLinear([L, C * Math.cos(h), C * Math.sin(h)])
}

function hslToLinear(h, s, l) {
	h = ((h % 360) + 360) % 360
	const c = (1 - Math.abs(2 * l - 1)) * s
	const hp = h / 60
	const x = c * (1 - Math.abs((hp % 2) - 1))
	let rgb
	if (hp < 1) rgb = [c, x, 0]
	else if (hp < 2) rgb = [x, c, 0]
	else if (hp < 3) rgb = [0, c, x]
	else if (hp < 4) rgb = [0, x, c]
	else if (hp < 5) rgb = [x, 0, c]
	else rgb = [c, 0, x]
	const m = l - c / 2
	return rgb.map((v) => srgbToLinear(clamp01(v + m)))
}

/* linear-light rgb is the internal currency; everything resolves to it */

const luminance = ([r, g, b]) => 0.2126 * r + 0.7152 * g + 0.0722 * b

function contrast(a, b) {
	const la = luminance(a)
	const lb = luminance(b)
	const hi = Math.max(la, lb)
	const lo = Math.min(la, lb)
	return (hi + 0.05) / (lo + 0.05)
}

const toHex = (lin) =>
	"#" +
	lin
		.map((c) => Math.round(clamp01(linearToSrgb(c)) * 255).toString(16).padStart(2, "0"))
		.join("")

/* --------------------------------------------------------------- colour parse */

const NAMED = {
	white: "#ffffff",
	black: "#000000",
	transparent: null,
}

function splitTop(str) {
	const out = []
	let depth = 0
	let cur = ""
	for (const ch of str) {
		if (ch === "(") depth++
		if (ch === ")") depth--
		if (ch === "," && depth === 0) {
			out.push(cur.trim())
			cur = ""
			continue
		}
		cur += ch
	}
	if (cur.trim()) out.push(cur.trim())
	return out
}

/** resolve a CSS colour value to linear rgb, or null when it cannot be measured */
function resolve(value, vars, seen = new Set(), depth = 0) {
	if (value == null || depth > 12) return null
	let v = String(value).trim().replace(/;$/, "").trim()
	if (!v) return null

	if (NAMED[v.toLowerCase()] !== undefined) {
		const named = NAMED[v.toLowerCase()]
		return named ? resolve(named, vars, seen, depth + 1) : null
	}

	// var(--name, fallback)
	const varMatch = v.match(/^var\(\s*(--[a-z0-9-]+)\s*(?:,([\s\S]*))?\)$/i)
	if (varMatch) {
		const name = varMatch[1]
		if (seen.has(name)) return null
		const next = new Set(seen).add(name)
		if (vars.has(name)) {
			const got = resolve(vars.get(name), vars, next, depth + 1)
			if (got) return got
		}
		return varMatch[2] ? resolve(varMatch[2], vars, next, depth + 1) : null
	}

	// #rgb #rrggbb #rrggbbaa
	const hex = v.match(/^#([0-9a-f]{3,8})$/i)
	if (hex) {
		let h = hex[1]
		if (h.length === 3 || h.length === 4) h = h.slice(0, 3).split("").map((c) => c + c).join("")
		if (h.length >= 6) {
			return [0, 2, 4].map((i) => srgbToLinear(parseInt(h.slice(i, i + 2), 16) / 255))
		}
		return null
	}

	// rgb() / rgba()
	const rgb = v.match(/^rgba?\(([^)]+)\)$/i)
	if (rgb) {
		const parts = rgb[1].split(/[\s,/]+/).filter(Boolean).slice(0, 3)
		if (parts.length < 3) return null
		return parts.map((p) =>
			srgbToLinear(clamp01(p.endsWith("%") ? parseFloat(p) / 100 : parseFloat(p) / 255)),
		)
	}

	// hsl() / hsla()
	const hsl = v.match(/^hsla?\(([^)]+)\)$/i)
	if (hsl) {
		const p = hsl[1].split(/[\s,/]+/).filter(Boolean)
		if (p.length < 3) return null
		return hslToLinear(parseFloat(p[0]), parseFloat(p[1]) / 100, parseFloat(p[2]) / 100)
	}

	// oklch()
	const oklch = v.match(/^oklch\(([^)]+)\)$/i)
	if (oklch) {
		const p = oklch[1].split(/[\s,/]+/).filter(Boolean)
		if (p.length < 3) return null
		const L = p[0].endsWith("%") ? parseFloat(p[0]) / 100 : parseFloat(p[0])
		const C = parseFloat(p[1])
		const H = parseFloat(p[2]) || 0
		return oklchToLinear(L, C, H)
	}

	// color-mix(in <space>, A p%, B q%)
	const mix = v.match(/^color-mix\(([\s\S]+)\)$/i)
	if (mix) {
		const parts = splitTop(mix[1])
		if (parts.length < 3) return null
		const space = parts[0].replace(/^in\s+/i, "").trim().toLowerCase()
		const read = (spec) => {
			const pct = spec.match(/(-?[\d.]+)%\s*$/)
			const colour = pct ? spec.slice(0, pct.index).trim() : spec.trim()
			return { colour, pct: pct ? parseFloat(pct[1]) : null }
		}
		const a = read(parts[1])
		const b = read(parts[2])
		const ca = resolve(a.colour, vars, seen, depth + 1)
		const cb = resolve(b.colour, vars, seen, depth + 1)
		if (!ca || !cb) return null
		let wa = a.pct
		let wb = b.pct
		if (wa == null && wb == null) (wa = 50), (wb = 50)
		else if (wa == null) wa = 100 - wb
		else if (wb == null) wb = 100 - wa
		const sum = wa + wb || 100
		const t = wb / sum // weight of the second colour
		if (space.startsWith("oklab") || space.startsWith("oklch")) {
			const la = linearToOklab(ca)
			const lb = linearToOklab(cb)
			return oklabToLinear(la.map((x, i) => x * (1 - t) + lb[i] * t))
		}
		return ca.map((x, i) => x * (1 - t) + cb[i] * t)
	}

	return null
}

/* ---------------------------------------------------------------- token parse */

/**
 * Collect custom properties per scope. Later declarations win inside a scope,
 * which matches the cascade closely enough for a token file.
 */
function parseScopes(css) {
	const scopes = new Map() // label -> Map(name -> value)
	const stack = []
	let i = 0
	let buf = ""

	const label = () => {
		const sel = stack.filter(Boolean).join(" ")
		if (/prefers-color-scheme:\s*dark/.test(sel) || /\bdark\b/.test(sel)) return "dark"
		if (/prefers-contrast|forced-colors|print/.test(sel)) return "skip"
		return "light"
	}

	const put = (name, value) => {
		const key = label()
		if (key === "skip") return
		if (!scopes.has(key)) scopes.set(key, new Map())
		scopes.get(key).set(name, value)
	}

	const flush = () => {
		const decl = buf.trim()
		buf = ""
		if (!decl) return
		const m = decl.match(/^(--[a-z0-9-]+)\s*:\s*([\s\S]+)$/i)
		if (m) put(m[1], m[2].trim())
	}

	while (i < css.length) {
		const ch = css[i]
		if (ch === "/" && css[i + 1] === "*") {
			const end = css.indexOf("*/", i + 2)
			i = end === -1 ? css.length : end + 2
			continue
		}
		if (ch === "{") {
			stack.push(buf.trim())
			buf = ""
			i++
			continue
		}
		if (ch === "}") {
			flush()
			stack.pop()
			i++
			continue
		}
		if (ch === ";") {
			flush()
			i++
			continue
		}
		buf += ch
		i++
	}
	return scopes
}

/* ------------------------------------------------------------------ contract */

// [foreground, background, minimum, what it is]
const CONTRACT = [
	["--ink", "--canvas", 4.5, "body ink on canvas"],
	["--ink", "--surface", 4.5, "body ink on surface"],
	["--ink-muted", "--canvas", 4.5, "secondary text on canvas"],
	["--ink-muted", "--surface", 4.5, "secondary text on surface"],
	["--ink-subtle", "--canvas", 3.0, "tertiary label on canvas"],
	["--accent-ink", "--accent", 4.5, "label on the accent fill"],
	["--accent", "--canvas", 3.0, "accent edge on canvas"],
	["--focus", "--canvas", 3.0, "focus ring on canvas"],
	["--focus", "--surface", 3.0, "focus ring on surface"],
	["--danger", "--canvas", 4.5, "error text on canvas"],
	["--success", "--canvas", 3.0, "success mark on canvas"],
	["--warning", "--canvas", 3.0, "warning mark on canvas"],
	["--control-border", "--canvas", 3.0, "control boundary on canvas"],
	["--control-border", "--surface", 3.0, "control boundary on surface"],
	/* Advisory: a structural hairline only owes 3:1 when it is the only
	   affordance of a control. Reported so the decision is conscious, never fatal.
	   If an input's border is your only affordance, use --control-border. */
	["--hairline-strong", "--canvas", 3.0, "structural hairline (advisory)", true],
]

/* ---------------------------------------------------------------------- main */

const argv = process.argv.slice(2)
const flags = new Set(argv.filter((a) => a.startsWith("--")))
const positional = argv.filter((a) => !a.startsWith("--"))
const json = flags.has("--json")

const pairIndex = argv.indexOf("--pair")
if (pairIndex !== -1) {
	const fg = argv[pairIndex + 1]
	const bg = argv[pairIndex + 2]
	const a = resolve(fg, new Map())
	const b = resolve(bg, new Map())
	if (!a || !b) {
		console.error(`viora-design-skills contrast: cannot parse ${!a ? fg : bg}`)
		process.exit(2)
	}
	const ratio = contrast(a, b)
	if (json) {
		console.log(JSON.stringify({ fg, bg, ratio: Number(ratio.toFixed(2)) }, null, 2))
	} else {
		console.log(
			`${fg} on ${bg}: ${ratio.toFixed(2)}:1  ` +
				`body ${ratio >= 4.5 ? "pass" : "FAIL"}, large/UI ${ratio >= 3 ? "pass" : "FAIL"}`,
		)
	}
	process.exit(ratio >= 3 ? 0 : 1)
}

const target = positional[0]
if (!target) {
	console.error("viora-design-skills contrast: pass a token file, or --pair <fg> <bg>")
	process.exit(2)
}
if (!existsSync(target)) {
	console.error(`viora-design-skills contrast: file not found: ${target}`)
	process.exit(2)
}

const css = readFileSync(target, "utf8")
const scopes = parseScopes(css)
const light = scopes.get("light") || new Map()
const darkOverrides = scopes.get("dark") || new Map()
const dark = new Map([...light, ...darkOverrides])

const themes = [["light", light]]
if (darkOverrides.size > 0) themes.push(["dark", dark])

const rows = []
for (const [theme, vars] of themes) {
	for (const [fg, bg, min, what, advisory] of CONTRACT) {
		if (!vars.has(fg) || !vars.has(bg)) continue
		const a = resolve(`var(${fg})`, vars)
		const b = resolve(`var(${bg})`, vars)
		if (!a || !b) {
			rows.push({ theme, fg, bg, what, min, ratio: null, status: "unmeasurable" })
			continue
		}
		const ratio = contrast(a, b)
		rows.push({
			theme,
			fg,
			bg,
			what,
			min,
			ratio: Number(ratio.toFixed(2)),
			fgHex: toHex(a),
			bgHex: toHex(b),
			status: ratio >= min ? "pass" : advisory ? "advisory" : "FAIL",
		})
	}
}

if (flags.has("--all")) {
	const inks = [...light.keys()].filter((k) => /^--ink/.test(k))
	const grounds = [...light.keys()].filter((k) => /^--(canvas|surface)/.test(k))
	for (const [theme, vars] of themes) {
		for (const fg of inks) {
			for (const bg of grounds) {
				const a = resolve(`var(${fg})`, vars)
				const b = resolve(`var(${bg})`, vars)
				if (!a || !b) continue
				const ratio = contrast(a, b)
				rows.push({
					theme,
					fg,
					bg,
					what: "combination",
					min: 0,
					ratio: Number(ratio.toFixed(2)),
					status: "info",
				})
			}
		}
	}
}

const failures = rows.filter((r) => r.status === "FAIL")
const advisories = rows.filter((r) => r.status === "advisory")
const unmeasurable = rows.filter((r) => r.status === "unmeasurable")

if (json) {
	console.log(
		JSON.stringify(
			{ file: target, checked: rows.length, failures: failures.length, rows },
			null,
			2,
		),
	)
	process.exit(failures.length > 0 ? 1 : 0)
}

if (rows.length === 0) {
	console.log(
		"viora-design-skills contrast: no known token names found. Expected --ink, --canvas,\n" +
			"--surface, --accent, --accent-ink, --focus. Rename to the contract, or measure\n" +
			"pairs directly with --pair <fg> <bg>.",
	)
	process.exit(2)
}

let lastTheme = null
for (const r of rows) {
	if (r.theme !== lastTheme) {
		console.log(`\n${r.theme} theme`)
		lastTheme = r.theme
	}
	const ratio = r.ratio == null ? "  ?  " : `${r.ratio.toFixed(2)}:1`.padStart(7)
	const need = r.min ? `need ${r.min.toFixed(1)}` : ""
	const mark = r.status === "FAIL" ? "FAIL" : r.status === "pass" ? "pass" : r.status
	console.log(
		`  ${ratio}  ${mark.padEnd(12)} ${`${r.fg} on ${r.bg}`.padEnd(38)} ${need.padEnd(9)} ${r.what}`,
	)
}

const bar = "-".repeat(66)
console.log("\n" + bar)
console.log(
	`viora-design-skills contrast: ${failures.length} failure${failures.length === 1 ? "" : "s"}` +
		` in ${rows.length} measured pair${rows.length === 1 ? "" : "s"}` +
		(advisories.length ? `, ${advisories.length} advisory` : "") +
		(unmeasurable.length ? `, ${unmeasurable.length} unmeasurable` : ""),
)
if (failures.length === 0) {
	console.log("palette passes. contrast is measured, not claimed.")
} else {
	console.log("darken the ink or lighten the ground. Never lower the target.")
}
if (advisories.length > 0) {
	console.log(
		"advisory rows are decisions, not defects: a hairline below 3:1 is fine for\n" +
			"structure, and wrong as a control's only affordance. Use --control-border there.",
	)
}
console.log(bar)

process.exit(failures.length > 0 ? 1 : 0)
