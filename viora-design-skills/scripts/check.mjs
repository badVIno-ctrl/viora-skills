#!/usr/bin/env node
/**
 * viora-design-skills / mechanical craft checker
 *
 * Zero dependencies. Node 18+.
 *
 *   node check.mjs .                    scan the current project
 *   node check.mjs src app              scan specific paths
 *   node check.mjs . --summary          counts only
 *   node check.mjs . --json             machine readable
 *   node check.mjs . --github           GitHub Actions annotations, one per finding
 *   node check.mjs . --strict           warnings fail too, use before handing work over
 *   node check.mjs . --ignore-rule banned-font,raw-hex
 *   node check.mjs --list-rules
 *
 * Suppress one finding by putting this on the line, or the line above:
 *   /* viora-allow: rule-id short reason *\/
 *   /* viora-allow-file: reason *\/   in the first 2000 chars, exempts the whole
 *                                   file. For fixtures and docs that teach an
 *                                   anti-pattern on purpose, never for product code.
 *
 * Exit code 1 means at least one ERROR remains. Fix every error.
 * Decide consciously on every warning: fix it, or suppress it with a reason.
 */

import { readdirSync, readFileSync, statSync, existsSync } from "node:fs"
import { join, extname, basename, relative, resolve } from "node:path"

/* ------------------------------------------------------------------ setup */

const SKIP_DIRS = new Set([
	"node_modules", ".git", ".next", ".nuxt", ".svelte-kit", ".astro",
	"dist", "build", "out", "coverage", ".turbo", ".vercel", ".cache",
	"vendor", "target", "__pycache__", ".venv", "venv", ".viora-shots",
	/* skill folders: never lint the skill's own reference material */
	".claude", ".codex", ".cursor", ".gemini", ".opencode", ".github",
	"viora-design-skills",
])
const SKIP_FILES = new Set(["check.mjs", "shot.mjs", "contrast.mjs"])

const STYLE = new Set([".css", ".scss", ".sass", ".less"])
const MARKUP = new Set([".html", ".htm", ".vue", ".svelte", ".astro"])
const SCRIPT = new Set([".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"])
const COMPONENT = new Set([".jsx", ".tsx", ".vue", ".svelte", ".astro"])
const ALL = new Set([...STYLE, ...MARKUP, ...SCRIPT])
const COPY = new Set([".md", ".mdx"])
/* every file the walker opens: code plus shipped prose */
const SCAN = new Set([...ALL, ...COPY])
/* rules about words, not code. Prose ships to the user too. */
const TEXT = SCAN
/* anywhere colour, radius or type is actually applied, including one-file HTML */
const PAINT = new Set([...STYLE, ...MARKUP, ...COMPONENT])

const args = process.argv.slice(2)
const flags = new Set(args.filter((a) => a.startsWith("--")))
const ignoreArgIndex = args.findIndex((a) => a === "--ignore-rule" || a.startsWith("--ignore-rule="))
let ignored = new Set()
if (ignoreArgIndex !== -1) {
	const raw = args[ignoreArgIndex].includes("=")
		? args[ignoreArgIndex].split("=")[1]
		: args[ignoreArgIndex + 1] || ""
	ignored = new Set(raw.split(",").map((s) => s.trim()).filter(Boolean))
}
const targets = args.filter((a, i) => {
	if (a.startsWith("--")) return false
	if (ignoreArgIndex !== -1 && i === ignoreArgIndex + 1 && !args[ignoreArgIndex].includes("=")) return false
	return true
})
if (targets.length === 0) targets.push(".")

/* ------------------------------------------------------------------ rules */

const between = (line, i, cls) => cls.test(line[i - 1] || "") && cls.test(line[i + 1] || "")

const CYRILLIC = /[\u0400-\u04FF]/

/* Faces with no Cyrillic coverage. Naming one over Cyrillic copy ships a system
   fallback instead of the design. Extend the list, never silence the rule. */
const LATIN_ONLY = [
	"Geist", "Geist Mono", "Schibsted Grotesk", "Instrument Sans", "Instrument Serif",
	"Bricolage Grotesque", "Archivo", "Public Sans", "Libre Franklin", "Hanken Grotesk",
	"Satoshi", "Switzer", "General Sans", "Gambetta", "Cabinet Grotesk", "Clash Display",
	"Outfit", "Plus Jakarta Sans", "Poppins", "Space Grotesk", "Bebas Neue", "Sohne",
]

/* hue in degrees for a chromatic colour, null for neutrals and near-neutrals */
function chromaticHue(hex) {
	const r = parseInt(hex.slice(0, 2), 16) / 255
	const g = parseInt(hex.slice(2, 4), 16) / 255
	const b = parseInt(hex.slice(4, 6), 16) / 255
	const max = Math.max(r, g, b)
	const min = Math.min(r, g, b)
	const l = (max + min) / 2
	const d = max - min
	if (d < 0.06 || l < 0.06 || l > 0.96) return null
	const s = d / (1 - Math.abs(2 * l - 1))
	if (s < 0.22) return null
	let h
	if (max === r) h = ((g - b) / d) % 6
	else if (max === g) h = (b - r) / d + 2
	else h = (r - g) / d + 4
	return Math.round((((h * 60) % 360) + 360) % 360)
}

/* group hues into families: neighbours within 30 degrees are one colour */
function hueFamilies(hues) {
	const list = [...hues].sort((a, b) => a - b)
	if (list.length === 0) return 0
	const groups = []
	for (const h of list) {
		const last = groups[groups.length - 1]
		if (last && h - last[last.length - 1] <= 30) last.push(h)
		else groups.push([h])
	}
	if (groups.length > 1) {
		const first = groups[0]
		const last = groups[groups.length - 1]
		if (360 - last[last.length - 1] + first[0] <= 30) groups.pop()
	}
	return groups.length
}

function radiusValues(decl) {
	return String(decl)
		.split(/[\s/]+/)
		.map((v) => v.trim())
		.filter((v) => /^\d+(\.\d+)?(px|rem)$/.test(v))
		.filter((v) => !/^0(px|rem)?$/.test(v))
		.filter((v) => parseFloat(v) < 100)
}

const RULES = [
	/* ---------------------------------------------------------- text tells */
	{
		id: "em-dash",
		level: "error",
		ext: TEXT,
		msg: "em or en dash used as punctuation. The single loudest machine tell. Use a comma, colon or period. En dash only between numbers. Russian copy is exempt and is checked by scripts/ru.mjs, where the long dash is grammar.",
		scan(line) {
			/* Russian owns the long dash: there it is punctuation, not a machine
			   tell. Cyrillic lines belong to scripts/ru.mjs, which asks for it. */
			if (/[\u0410-\u044F\u0401\u0451]/.test(line)) return []
			const hits = []
			for (let i = 0; i < line.length; i++) {
				const c = line[i]
				if (c === "\u2014") hits.push(i)
				if (c === "\u2013" && !between(line, i, /[0-9]/)) hits.push(i)
			}
			return hits
		},
	},
	{
		id: "lorem",
		level: "error",
		ext: TEXT,
		re: /lorem\s+ipsum|dolor\s+sit\s+amet/gi,
		msg: "placeholder latin in shipped copy. Write the real sentence.",
	},
	{
		id: "slop-names",
		level: "error",
		ext: TEXT,
		re: /\b(Acme(\s+(Inc|Corp|Co))?|John\s+Doe|Jane\s+Doe|John\s+Smith|Jane\s+Smith|Your\s+Brand|Company\s+Name|Lorem\s+Inc|Nexus(Flow|Hub)?|SmartFlow|TaskFlow|CloudSync|Cloudly|InnovateHub|TechFlow|DataFlow)\b/g,
		msg: "generated placeholder name. Use a plausible real-sounding name matched to the audience.",
	},
	{
		id: "fake-stat",
		level: "warn",
		ext: TEXT,
		re: /(99\.9{1,2}\s*%|\b10,?000\+|\b1,234,567\b|\b100,?000\+|\b24\/7\b)/g,
		msg: "invented-perfect statistic. Use a real figure or drop the claim.",
	},
	{
		id: "filler-words",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx", ...COPY]),
		re: /\b(seamless(ly)?|robust|cutting[- ]edge|revolutionar(y|ise|ize)|game[- ]chang(er|ing)|unlock\s+the|elevate\s+your|supercharge|delve\s+into|synergy)\b/gi,
		msg: "filler adjective carrying no information. Replace with a concrete claim, a number, or a mechanism.",
	},
	{
		id: "scroll-cue",
		level: "error",
		ext: TEXT,
		re: /scroll\s*(to\s*(explore|discover|continue)|down\s*(to|for)?)\b/gi,
		msg: "scroll cue. If the page reads as scrollable, it is. Delete it.",
	},
	{
		id: "section-number",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx", ...COPY]),
		re: /(>\s*0[1-9]\s*(\/|\u00b7|\u2022)|\b(Step|Stage|Phase|Chapter|Pass)\s+(\d+|One|Two|Three|Four)\s*[:\u2013\u2014-]\s*[A-Z])/g,
		msg: "decorative section number. Let type scale and space carry hierarchy. (Real progress like 'Step 2 of 3' is fine.)",
	},

	/* --------------------------------------------------------- layout tells */
	{
		id: "eyebrow",
		level: "error",
		ext: ALL,
		re: /(uppercase[^"'`\n]{0,40}tracking-|tracking-[^"'`\n]{0,40}uppercase|text-transform:\s*uppercase[^;\n]*;\s*letter-spacing)/g,
		msg: "kicker / eyebrow label. Banned. Put the context in the heading itself.",
	},
	{
		id: "gradient-text",
		level: "error",
		ext: ALL,
		re: /(bg-clip-text|background-clip:\s*text|-webkit-background-clip:\s*text)/g,
		msg: "gradient text. Banned. Use solid ink and carry emphasis with weight or size.",
	},
	{
		id: "neon-glow",
		level: "warn",
		ext: ALL,
		re: /box-shadow:\s*(inset\s+)?0\s+0\s+\d/g,
		msg: "zero-offset shadow is a halo, not depth. Use offset plus blur, tinted from the ink hue.",
	},
	{
		id: "unsplash-hotlink",
		level: "warn",
		ext: ALL,
		re: /images\.unsplash\.com|source\.unsplash\.com/g,
		msg: "hotlinked stock URL will rot. Use a documented placeholder service and flag it as a placeholder in the report.",
	},

	/* --------------------------------------------------------- type tells */
	{
		id: "banned-font",
		level: "warn",
		ext: ALL,
		re: /\b(Playfair\s*Display|Fraunces|Instrument\s*Serif|Cormorant|DM\s*Serif|Newsreader|Space\s*Grotesk|Plus\s*Jakarta|Poppins|Montserrat|Raleway|Bebas\s*Neue)\b/g,
		msg: "default-reflex typeface. Allowed only when pinned by the user or justified in one line.",
	},
	{
		id: "tiny-text",
		level: "warn",
		ext: ALL,
		re: /(font-size:\s*(0?\.[0-6]\d*rem|([0-9]|10|11)px)|text-\[(10|11|9)px\])/g,
		msg: "text below 12px. 12px is the absolute floor, 16px is the body floor.",
	},

	/* -------------------------------------------------------- motion tells */
	{
		id: "transition-all",
		level: "error",
		ext: ALL,
		re: /(transition:\s*all|\btransition-all\b)/g,
		msg: "transition: all animates properties you never intended, including layout. Name each property.",
	},
	{
		id: "scale-zero",
		level: "error",
		ext: ALL,
		re: /(scale\(\s*0\s*\)|scale:\s*0\s*[;,)]|\bscale-0\b)/g,
		msg: "material appearing from nothing looks fake. Use scale(0.96) to scale(1).",
	},
	{
		id: "ease-in-enter",
		level: "warn",
		ext: ALL,
		re: /\bease-in\b(?!-out)/g,
		msg: "ease-in starts slow, which reads as lag. Use ease-out for anything the user triggers. ease-in is for exits only.",
	},
	{
		id: "transition-layout",
		level: "warn",
		ext: ALL,
		re: /transition(-property)?:\s*[^;{\n]*\b(width|height|top|left|right|bottom|margin|padding)\b/g,
		msg: "animating layout properties causes jank. Use transform, or interpolate-size for height.",
	},
	{
		id: "slow-motion",
		level: "warn",
		ext: ALL,
		re: /(transition|animation)(-duration)?:[^;{\n]*\b([6-9]\d\d|[1-9]\d{3,})ms\b/g,
		msg: "over 500ms. In-app motion caps at 300ms. Long durations read as a slow interface.",
	},
	{
		id: "scroll-listener",
		level: "error",
		ext: new Set([...SCRIPT, ...MARKUP]),
		re: /addEventListener\(\s*["'`]scroll["'`]/g,
		msg: "scroll-driven animation on the main thread. Use CSS animation-timeline: view() or IntersectionObserver.",
	},
	{
		id: "motion-axis-keys",
		level: "warn",
		ext: COMPONENT,
		re: /(animate|initial|exit)=\{\{[^}]*\b(x|y|scale|rotate)\s*:/g,
		msg: "separate transform keys can interpolate out of sync and wobble. Write the full transform string.",
	},
	{
		id: "hover-ungated",
		level: "warn",
		ext: new Set([...STYLE, ...MARKUP]),
		whole: true,
		re: /:hover\s*\{[^}]*\b(transform|translate|scale)\s*:/g,
		msg: "hover transform without a (hover: hover) gate fires on tap and sticks on touch devices.",
		fileSkip: (content) => /@media[^{]*\(\s*hover\s*:\s*hover/.test(content),
	},

	/* ----------------------------------------------------- colour and code */
	{
		id: "pure-black-text",
		level: "error",
		ext: ALL,
		re: /(color:\s*(#000{1,4}\b|#000000\b|rgb\(\s*0\s*,\s*0\s*,\s*0\s*\)|black\b)|\btext-black\b)/g,
		msg: "pure black text vibrates against white. Use near-black ink from the palette.",
	},
	{
		id: "raw-hex",
		level: "warn",
		ext: PAINT,
		re: /#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b/g,
		msg: "raw hex outside the token layer. Declare the colour once as a custom property, then reference the token.",
		fileSkip: (_c, path) => /token|theme|palette|config|colors?|constants/i.test(basename(path)),
		lineSkip: (line) => /--[a-z0-9-]+\s*:/i.test(line),
	},
	{
		id: "important",
		level: "warn",
		ext: ALL,
		re: /!important/g,
		msg: "!important means the specificity is wrong. Fix the cascade.",
		lineSkip: (line) =>
			/(animation|transition)-duration|animation-iteration-count|scroll-behavior|display:\s*none/.test(line),
	},
	{
		id: "zindex-high",
		level: "warn",
		ext: ALL,
		msg: "arbitrary z-index. Use the five-step scale: --z-1 through --z-5.",
		scan(line) {
			const hits = []
			const re = /z-index:\s*(\d+)|\bz-\[(\d+)\]/g
			let m
			while ((m = re.exec(line))) {
				const v = Number(m[1] ?? m[2])
				if (v > 50) hits.push(m.index)
			}
			return hits
		},
	},
	{
		id: "vh-height",
		level: "error",
		ext: ALL,
		re: /(\bh-screen\b|\bmin-h-screen\b|(height|min-height):\s*100vh\b)/g,
		msg: "100vh is wrong on mobile browsers. Use 100dvh, or let content set the height.",
	},

	/* ------------------------------------------------------- accessibility */
	{
		id: "focus-none",
		level: "error",
		ext: ALL,
		re: /(outline:\s*(none|0)\b|\boutline-none\b)/g,
		msg: "focus outline removed and this file defines no focus-visible replacement. Keyboard users lose the interface.",
		fileSkip: (content) => /focus-visible/.test(content),
	},
	{
		id: "img-no-alt",
		level: "error",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		msg: "img without alt. Describe it, or use alt=\"\" if it is genuinely decorative.",
		scan(line) {
			const hits = []
			const re = /<img\b[^>]*>/g
			let m
			while ((m = re.exec(line))) {
				if (!/\balt\s*=/.test(m[0])) hits.push(m.index)
			}
			return hits
		},
	},
	{
		id: "viewport-no-zoom",
		level: "error",
		ext: ALL,
		re: /(user-scalable\s*=\s*["']?no|maximum-scale\s*=\s*["']?1(\.0)?\b)/g,
		msg: "blocking zoom. Users must be able to zoom.",
	},
	{
		id: "tabindex-positive",
		level: "error",
		ext: ALL,
		re: /tabindex\s*=\s*["'{]?\s*[1-9]/gi,
		msg: "positive tabindex destroys tab order. Use 0 or -1 and fix the DOM order.",
	},
	{
		id: "icon-button-unnamed",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		msg: "icon-only button with no accessible name. Add aria-label or visually hidden text.",
		scan(line) {
			const hits = []
			const re = /<button\b[^>]*>\s*<(svg|Icon|[A-Z][A-Za-z]*Icon)\b[^>]*\/?>\s*<\/button>/g
			let m
			while ((m = re.exec(line))) {
				if (!/aria-label|aria-labelledby|sr-only|title=/.test(m[0])) hits.push(m.index)
			}
			return hits
		},
	},
	{
		id: "emoji-icon",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		re: /[\u{1F300}-\u{1FAFF}\u{2705}\u{274C}\u{2728}\u{1F680}]/gu,
		msg: "emoji used as an icon reads as a chat message, not a product. Use one real icon set.",
		lineSkip: (line) => !/[<>]/.test(line),
	},

	/* ------------------------------------------------------ copy and voice */
	{
		id: "poetic-label",
		level: "warn",
		ext: TEXT,
		re: /\b(field notes|from the field|on our desks|currently on the bench|quietly (in use|trusted)\s+(at|by)|loose plates)\b/gi,
		msg: "performative-craftsman label. Use the plain functional name, or drop the label.",
	},
	{
		id: "middle-dot-strip",
		level: "warn",
		ext: TEXT,
		msg: "metadata glued together with middle dots. One separator per line, then use space, hairlines or columns.",
		scan(line) {
			let count = 0
			let first = -1
			for (let i = 0; i < line.length; i++) {
				if (line[i] === "\u00b7" || line[i] === "\u2022") {
					count++
					if (first === -1) first = i
				}
			}
			return count >= 3 ? [Math.max(0, first)] : []
		},
	},
	{
		id: "locale-strip",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx", ...COPY]),
		re: /\b\d{1,2}:\d{2}\s*(\u00b7|\||,)?\s*[-+]?\d{1,2}\s*\u00b0/g,
		msg: "atmospheric time and weather strip. Decoration pretending to be information.",
	},
	{
		id: "version-stamp",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		re: /(>\s*(v\d+\.\d+(\.\d+)?([-.][a-z0-9]+)*|BETA|ALPHA|EARLY ACCESS|INVITE[- ]ONLY)\s*<)/g,
		msg: "version or status stamp used as decoration. Ship it only when the release state is the message.",
	},

	/* --------------------------------------------------- hierarchy and form */
	{
		id: "pure-black-surface",
		level: "warn",
		ext: ALL,
		re: /(background(-color)?:\s*(#000{1,4}\b|#000000\b|black\b)|\bbg-black\b)/g,
		msg: "pure black ground kills every shadow and edge. Use the palette's darkest surface.",
	},
	{
		id: "image-hover",
		level: "warn",
		ext: new Set([...STYLE, ...MARKUP]),
		whole: true,
		re: /(img|picture|figure)[^{};]{0,40}:hover\s*\{[^}]*\b(transform|scale|translate)\s*:/g,
		msg: "an image is not an action target. Move the hover feedback to its container.",
	},
	{
		id: "placeholder-as-label",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		msg: "input with a placeholder and no label. The placeholder disappears exactly when the user needs it.",
		scan(line) {
			const hits = []
			const re = /<input\b[^>]*>/g
			let m
			while ((m = re.exec(line))) {
				if (/placeholder\s*=/.test(m[0]) && !/aria-label|aria-labelledby|\bid\s*=/.test(m[0])) {
					hits.push(m.index)
				}
			}
			return hits
		},
	},
	{
		id: "h1-multiple",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		whole: true,
		msg: "more than one h1 in one document. A hierarchy has a single top.",
		wholeScan(all, lineAt) {
			const found = []
			const re = /<h1\b/gi
			let m
			while ((m = re.exec(all))) found.push(m.index)
			return found.length > 1 ? found.slice(1).map(lineAt) : []
		},
	},
	{
		id: "heading-skip",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		whole: true,
		msg: "heading level skipped. The outline is read by screen readers, not the font size.",
		wholeScan(all, lineAt) {
			const idxs = []
			const re = /<h([1-6])\b/gi
			let m
			let prev = 0
			while ((m = re.exec(all))) {
				const level = Number(m[1])
				if (prev && level > prev + 1) idxs.push(lineAt(m.index))
				prev = level
			}
			return idxs
		},
	},
	{
		id: "html-lang-missing",
		level: "error",
		ext: new Set([...MARKUP]),
		whole: true,
		msg: "the document declares no language. Screen readers guess the voice, and hyphenation and quotes follow the wrong locale. Set lang on <html>.",
		wholeScan(all, lineAt) {
			const m = /<html\b[^>]*>/i.exec(all)
			if (!m) return []
			return /\blang\s*=/i.test(m[0]) ? [] : [lineAt(m.index)]
		},
	},
	{
		id: "lang-copy-mismatch",
		level: "error",
		ext: new Set([...MARKUP]),
		whole: true,
		msg: "the document declares English while the copy is Cyrillic. The interface must declare the language it actually speaks.",
		wholeScan(all, lineAt) {
			const m = /<html\b[^>]*>/i.exec(all)
			if (!m) return []
			if (!/\blang\s*=\s*["\']?en\b/i.test(m[0])) return []
			return /[\u0400-\u04FF]{4,}/.test(all) ? [lineAt(m.index)] : []
		},
	},

	/* ------------------------------------------- the 2026 generated-UI tells */
	{
		id: "ai-gradient",
		level: "error",
		ext: ALL,
		re: /from-(?:purple|violet|indigo|fuchsia)-\d{3}[^"'`\n]{0,60}to-(?:blue|indigo|purple|violet|pink|cyan|fuchsia)-\d{3}/g,
		msg: "the default generated gradient (violet to blue). It dates the work instantly. One solid accent from the palette.",
	},
	{
		id: "framework-default-shadow",
		level: "warn",
		ext: PAINT,
		re: /box-shadow:\s*[^;{}\n]*rgba?\(\s*0\s*,\s*0\s*,\s*0\s*[,/)]/g,
		msg: "untinted black shadow, the framework default. Tint the shadow from the ink hue and give it offset plus blur.",
	},
	{
		id: "hero-mesh-blob",
		level: "warn",
		ext: ALL,
		re: /\bblur-(?:2xl|3xl)\b|filter:\s*blur\(\s*(?:[4-9]\d|\d{3,})px/g,
		msg: "a giant blur is the mesh-gradient blob behind the hero. Use a real image, a flat field, or nothing.",
	},
	{
		id: "center-everything",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		whole: true,
		msg: "nearly everything is centered, so nothing has an edge to hold. Center the hero at most, then align one edge down the page.",
		wholeScan(all, lineAt) {
			const hits = [...all.matchAll(/\btext-center\b|text-align:\s*center/g)]
			return hits.length >= 7 ? [lineAt(hits[6].index)] : []
		},
	},
	{
		id: "card-monotony",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		whole: true,
		msg: "the same card markup repeated three or more times by hand. Equal cards read as a layout stub. Vary the section family, or use hairline rows.",
		wholeScan(all, lineAt) {
			const seen = new Map()
			for (const m of all.matchAll(/class(?:Name)?="([^"]{25,200})"/g)) {
				const v = m[1].trim()
				if (!/rounded|border|shadow/.test(v)) continue
				if (!/\bp-|padding|gap/.test(v)) continue
				if (!seen.has(v)) seen.set(v, [])
				seen.get(v).push(m.index)
			}
			for (const [, idxs] of seen) {
				if (idxs.length >= 3) return [lineAt(idxs[2])]
			}
			return []
		},
	},
	{
		id: "div-click-target",
		level: "error",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		re: /<(?:div|span)\b(?![^>]*\b(?:role|tabindex|tabIndex)\s*=)[^>]*\bon:?[Cc]lick/g,
		msg: "click handler on a div or span. The keyboard cannot reach it. Use a button, or add role, tabindex and a key handler.",
	},
	{
		id: "svg-unlabelled",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		re: /<svg\b(?![^>]*(?:aria-hidden|aria-label|aria-labelledby|role\s*=\s*["']img))[^>]*>/g,
		msg: "svg with no aria state. Decorative icons need aria-hidden, meaningful ones need a label.",
	},
	{
		id: "img-no-dimensions",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		re: /<img\b(?![^>]*\bwidth\s*=)(?![^>]*aspect)[^>]*>/g,
		msg: "image with no intrinsic size. The layout jumps while it loads. Set width and height, or an aspect-ratio.",
	},
	{
		id: "overflow-x-hack",
		level: "warn",
		ext: PAINT,
		re: /overflow-x:\s*hidden|\boverflow-x-hidden\b/g,
		msg: "hiding horizontal overflow hides a layout bug. Find what overflows at 320px and fix that.",
	},
	{
		id: "off-rhythm-space",
		level: "warn",
		ext: PAINT,
		msg: "spacing off the rhythm. A 13px gap is a value nobody chose. Use the space tokens.",
		lineSkip: (line) => /--space|:root|@media/.test(line),
		scan(line) {
			if (!/(?:padding|margin|gap)/.test(line)) return []
			const hits = []
			for (const m of line.matchAll(/(?:padding|margin|row-gap|column-gap|gap)[a-z-]*:\s*([^;{}]+)/g)) {
				for (const n of m[1].matchAll(/(\d+)px/g)) {
					const v = Number(n[1])
					if (v > 4 && v % 2 !== 0) hits.push(m.index)
				}
			}
			return hits
		},
	},
	{
		id: "arbitrary-px-class",
		level: "warn",
		ext: new Set([...MARKUP, ...COMPONENT]),
		re: /\b(?:p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|gap|w|h|text|rounded|top|left|right|bottom)-\[\d+px\]/g,
		msg: "arbitrary pixel value in a class. Add it to the scale or use an existing step.",
	},
	{
		id: "display-no-tracking",
		level: "warn",
		ext: PAINT,
		whole: true,
		msg: "display-size type at default tracking. Above roughly 40px, set letter-spacing between -0.02em and -0.04em or the headline reads as unset.",
		wholeScan(all, lineAt) {
			const hits = []
			for (const m of all.matchAll(/\{([^{}]*)\}/g)) {
				const body = m[1]
				if (/letter-spacing|--tracking|tracking:/.test(body)) continue
				/* only the font-size declaration counts: a min-width in rem is not type */
				const decl = /font-size\s*:\s*([^;}]+)/.exec(body)
				if (!decl) continue
				let biggest = 0
				for (const s of decl[1].matchAll(/([\d.]+)rem/g)) biggest = Math.max(biggest, Number(s[1]))
				for (const s of decl[1].matchAll(/([\d.]+)px/g)) biggest = Math.max(biggest, Number(s[1]) / 16)
				if (biggest >= 2.5) hits.push(lineAt(m.index))
			}
			return hits
		},
	},
	{
		id: "title-case-heading",
		level: "warn",
		ext: new Set([...MARKUP, ".jsx", ".tsx"]),
		re: /<h[1-3][^>]*>\s*(?:[A-Z][a-z]+\s+){2,}[A-Z][a-z]+/g,
		msg: "Title Case heading. Marketing-deck voice. Use sentence case.",
	},
]

/* ------------------------------------------------------- repo-level rules */

const REPO_RULES = [
	{
		id: "reduced-motion-missing",
		level: "error",
		msg: "the project animates but never handles prefers-reduced-motion. Ship it in the same commit.",
		test(stats) {
			return stats.hasMotion && !stats.hasReducedMotion
		},
	},
	{
		id: "marquee-multi",
		level: "warn",
		msg: "more than one marquee on the project. One is a device, two is a tic.",
		test(stats) {
			return stats.marquee > 1
		},
	},
	{
		id: "focus-ring-missing",
		level: "warn",
		msg: "no :focus-visible style found anywhere. Keyboard users have no visible focus.",
		test(stats) {
			return stats.styleFiles > 0 && !stats.hasFocusVisible
		},
	},
	{
		id: "cyrillic-latin-face",
		level: "error",
		msg: "the copy contains Cyrillic but the type stack names a Latin-only face. The page falls back to a system font and the design is gone. Pick a face that ships Cyrillic.",
		test(stats) {
			return stats.hasCyrillic && stats.latinOnly.size > 0
		},
		detail(stats) {
			return [...stats.latinOnly].join(", ")
		},
	},
	{
		id: "hue-count",
		level: "warn",
		msg: "more than two chromatic families outside the semantic colours. Neutrals plus two colours, maximum.",
		test(stats) {
			return hueFamilies(stats.hues) > 2
		},
		detail(stats) {
			return `${hueFamilies(stats.hues)} colour families`
		},
	},
	{
		id: "radius-family",
		level: "warn",
		msg: "hard-coded corner radii in more than two sizes. Pick one radius family, put it in tokens, reference it.",
		test(stats) {
			return stats.radii.size > 2
		},
		detail(stats) {
			return [...stats.radii].join(", ")
		},
	},
	{
		id: "font-count",
		level: "warn",
		msg: "more than three families in the project. Display, text, mono is the ceiling.",
		test(stats) {
			return stats.families.size > 3
		},
		detail(stats) {
			return [...stats.families].join(", ")
		},
	},
	{
		id: "icon-stroke-mixed",
		level: "warn",
		msg: "icons drawn at more than one stroke weight. One weight everywhere, or the set reads as borrowed.",
		test(stats) {
			return stats.strokes.size > 1
		},
		detail(stats) {
			return [...stats.strokes].join(", ")
		},
	},
	{
		id: "glass-overuse",
		level: "warn",
		msg: "translucent glass on more than two surfaces. Glass is one highlight, not a material for the whole product.",
		test(stats) {
			return stats.glass > 2
		},
		detail(stats) {
			return `${stats.glass} blurred surfaces`
		},
	},
	{
		id: "tokens-missing",
		level: "error",
		msg: "colour, size, radius, shadow and duration are not tokenised. Components must reference one token file, not raw values.",
		test(stats) {
			return stats.paintFiles > 0 && stats.customProps < 8
		},
		detail(stats) {
			return `${stats.customProps} custom properties found`
		},
	},
]

/* ------------------------------------------------------------------ utils */

function maskComments(content, ext) {
	const chars = content.split("")
	const blank = (from, to) => {
		for (let i = from; i < to && i < chars.length; i++) {
			if (chars[i] !== "\n") chars[i] = " "
		}
	}
	if (COPY.has(ext)) {
		/* mask fenced and inline code so documented anti-patterns do not fire */
		const re = /```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`/g
		let m
		while ((m = re.exec(content))) blank(m.index, m.index + m[0].length)
		return chars.join("")
	}
	if (STYLE.has(ext) || SCRIPT.has(ext) || MARKUP.has(ext)) {
		let i = 0
		while (i < content.length - 1) {
			if (content[i] === "/" && content[i + 1] === "*") {
				const end = content.indexOf("*/", i + 2)
				const stop = end === -1 ? content.length : end + 2
				blank(i, stop)
				i = stop
				continue
			}
			if (
				!STYLE.has(ext) &&
				content[i] === "/" &&
				content[i + 1] === "/" &&
				content[i - 1] !== ":" &&
				content[i - 1] !== "/"
			) {
				const end = content.indexOf("\n", i)
				const stop = end === -1 ? content.length : end
				blank(i, stop)
				i = stop
				continue
			}
			if (content.startsWith("<!--", i)) {
				const end = content.indexOf("-->", i + 4)
				const stop = end === -1 ? content.length : end + 3
				blank(i, stop)
				i = stop
				continue
			}
			i++
		}
	}
	return chars.join("")
}

function walk(dir, out) {
	let entries
	try {
		entries = readdirSync(dir, { withFileTypes: true })
	} catch {
		return out
	}
	for (const e of entries) {
		if (e.name.startsWith(".") && e.name !== "." && !SCAN.has(extname(e.name))) {
			if (e.isDirectory()) continue
		}
		const full = join(dir, e.name)
		if (e.isDirectory()) {
			if (SKIP_DIRS.has(e.name)) continue
			walk(full, out)
		} else if (e.isFile()) {
			if (SKIP_FILES.has(e.name)) continue
			if (/\.min\.(js|css)$/.test(e.name)) continue
			if (SCAN.has(extname(e.name))) out.push(full)
		}
	}
	return out
}

/* ------------------------------------------------------------------- main */

if (flags.has("--explain")) {
	const { spawnSync } = await import("node:child_process")
	const id = process.argv.slice(2).find((a) => !a.startsWith("-"))
	const run = spawnSync(
		process.execPath,
		[new URL("./explain.mjs", import.meta.url).pathname, ...(id ? [id] : ["--all"])],
		{ stdio: "inherit" },
	)
	process.exit(run.status ?? 0)
}

if (flags.has("--list-rules")) {
	for (const r of [...RULES, ...REPO_RULES]) {
		console.log(`${r.level.padEnd(5)}  ${r.id.padEnd(22)}  ${r.msg}`)
	}
	process.exit(0)
}

const files = []
for (const t of targets) {
	const p = resolve(t)
	if (!existsSync(p)) {
		console.error(`viora-design-skills: path not found: ${t}`)
		process.exit(2)
	}
	if (statSync(p).isDirectory()) walk(p, files)
	else if (SCAN.has(extname(p))) files.push(p)
}

const findings = []
const stats = {
	glass: 0,
	paintFiles: 0,
	customProps: 0,
	hasMotion: false,
	hasReducedMotion: false,
	hasFocusVisible: false,
	styleFiles: 0,
	marquee: 0,
	hasCyrillic: false,
	hues: new Set(),
	radii: new Set(),
	families: new Set(),
	strokes: new Set(),
	latinOnly: new Set(),
}

for (const file of files) {
	const ext = extname(file)
	let raw
	try {
		raw = readFileSync(file, "utf8")
	} catch {
		continue
	}
	if (raw.length > 800_000) continue
	/* a fixture or a teaching file may declare its whole content deliberate */
	if (/viora-allow-file/i.test(raw.slice(0, 2000))) continue

	if (STYLE.has(ext)) stats.styleFiles++
	if (PAINT.has(ext)) {
		stats.paintFiles++
		const glassHits = raw.match(/backdrop-filter:\s*[^;{}\n]*blur|\bbackdrop-blur\b/g)
		if (glassHits) stats.glass += glassHits.length
		const propHits = raw.match(/^\s*--[a-z0-9-]+\s*:/gm)
		if (propHits) stats.customProps += propHits.length
	}
	if (/@keyframes|transition:|animation:|transition-duration|animate-/.test(raw)) stats.hasMotion = true
	if (/prefers-reduced-motion/.test(raw)) stats.hasReducedMotion = true
	if (/focus-visible/.test(raw)) stats.hasFocusVisible = true
	if (ALL.has(ext)) {
		/* only count marquees in code. Prose that names the pattern is not a marquee. */
		const marqueeHits = raw.match(/marquee/gi)
		if (marqueeHits) stats.marquee += marqueeHits.length
	}
	if (CYRILLIC.test(raw)) stats.hasCyrillic = true

	if (PAINT.has(ext)) {
		for (const line of raw.split("\n")) {
			/* semantic colours are exempt from the palette ceiling */
			if (/success|warning|danger|error|info|shadow|scrim/i.test(line)) continue
			for (const m of line.matchAll(/#([0-9a-fA-F]{6})\b/g)) {
				const h = chromaticHue(m[1])
				if (h !== null) stats.hues.add(h)
			}
		}
		for (const m of raw.matchAll(/border-radius:\s*([^;{}\n]+)/g)) {
			if (/var\(/.test(m[1])) continue
			for (const r of radiusValues(m[1])) stats.radii.add(r)
		}
		for (const m of raw.matchAll(/rounded-\[(\d+)px\]/g)) stats.radii.add(m[1] + "px")
	}

	for (const m of raw.matchAll(/(?:font-family|--font-[a-z0-9-]+)\s*:\s*([^;{}\n]+)/g)) {
		const first = String(m[1]).split(",")[0].trim().replace(/^["']|["']$/g, "")
		if (!first) continue
		if (/^var\(|^inherit$|^initial$|^ui-|^system-ui$|^-apple-system$|^monospace$|^sans-serif$|^serif$/i.test(first)) continue
		stats.families.add(first)
		if (LATIN_ONLY.some((f) => f.toLowerCase() === first.toLowerCase())) stats.latinOnly.add(first)
	}
	for (const m of raw.matchAll(/stroke-?[wW]idth\s*[=:]\s*["'{]?\s*([\d.]+)/g)) stats.strokes.add(m[1])

	const rawLines = raw.split("\n")
	const masked = maskComments(raw, ext).split("\n")

	// suppression map, read from the ORIGINAL text since it lives in comments
	const allowed = rawLines.map((l) => {
		const m = l.match(/viora-allow:\s*([a-z0-9-,*\s]+)/i)
		if (!m) return null
		return new Set(m[1].split(/[,\s]+/).map((s) => s.trim()).filter(Boolean))
	})
	const isAllowed = (idx, id) => {
		for (const at of [idx, idx - 1]) {
			const set = allowed[at]
			if (set && (set.has(id) || set.has("*"))) return true
		}
		return false
	}

	for (const rule of RULES) {
		if (ignored.has(rule.id)) continue
		if (!rule.ext.has(ext)) continue
		if (rule.fileSkip && rule.fileSkip(raw, file)) continue

		// rules that must see across line breaks: a CSS block, or a document outline
		if (rule.whole) {
			const all = masked.join("\n")
			const lineAt = (index) => all.slice(0, index).split("\n").length - 1
			const report = (idx) => {
				if (isAllowed(idx, rule.id)) return
				findings.push({
					file,
					line: idx + 1,
					col: 1,
					count: 1,
					id: rule.id,
					level: rule.level,
					msg: rule.msg,
					snippet: (rawLines[idx] || "").trim().slice(0, 100),
				})
			}
			if (rule.wholeScan) {
				for (const idx of rule.wholeScan(all, lineAt) || []) report(idx)
				continue
			}
			rule.re.lastIndex = 0
			let wm
			while ((wm = rule.re.exec(all))) {
				report(lineAt(wm.index))
				if (wm.index === rule.re.lastIndex) rule.re.lastIndex++
			}
			continue
		}

		for (let i = 0; i < masked.length; i++) {
			const line = masked[i]
			if (!line || !line.trim()) continue
			if (rule.lineSkip && rule.lineSkip(line)) continue

			let cols = []
			if (rule.scan) {
				cols = rule.scan(line) || []
			} else {
				rule.re.lastIndex = 0
				let m
				while ((m = rule.re.exec(line))) {
					cols.push(m.index)
					if (m.index === rule.re.lastIndex) rule.re.lastIndex++
				}
			}
			if (cols.length === 0) continue
			if (isAllowed(i, rule.id)) continue

			findings.push({
				file,
				line: i + 1,
				col: cols[0] + 1,
				count: cols.length,
				id: rule.id,
				level: rule.level,
				msg: rule.msg,
				snippet: rawLines[i].trim().slice(0, 100),
			})
		}
	}
}

for (const rule of REPO_RULES) {
	if (ignored.has(rule.id)) continue
	if (rule.test(stats)) {
		findings.push({
			file: "(project)",
			line: 0,
			col: 0,
			count: 1,
			id: rule.id,
			level: rule.level,
			msg: rule.msg,
			snippet: rule.detail ? rule.detail(stats) : "",
		})
	}
}

/* ----------------------------------------------------------------- output */

const errors = findings.filter((f) => f.level === "error")
const warns = findings.filter((f) => f.level === "warn")
const cwd = process.cwd()
const rel = (p) => (p === "(project)" ? p : relative(cwd, p) || basename(p))

if (flags.has("--github")) {
	/* one annotation per finding, so a warning lands on the diff instead of in a
	   log nobody opens. Project-level findings carry no file or line. */
	for (const f of findings) {
		const kind = f.level === "error" ? "error" : "warning"
		const where =
			f.file === "(project)" ? "" : `file=${rel(f.file)},line=${Math.max(1, f.line || 1)},col=${Math.max(1, f.col || 1)},`
		console.log(`::${kind} ${where}title=viora ${f.id}::${String(f.msg).replace(/\s+/g, " ")}`)
	}
	console.log(`viora check: ${errors.length} errors, ${warns.length} warnings in ${files.length} files`)
	process.exit(errors.length > 0 || (flags.has("--strict") && warns.length > 0) ? 1 : 0)
}

if (flags.has("--json")) {
	console.log(
		JSON.stringify(
			{
				filesScanned: files.length,
				errors: errors.length,
				warnings: warns.length,
				findings: findings.map((f) => ({ ...f, file: rel(f.file) })),
			},
			null,
			2,
		),
	)
	process.exit(errors.length > 0 ? 1 : 0)
}

if (!flags.has("--summary")) {
	const byFile = new Map()
	for (const f of findings) {
		if (!byFile.has(f.file)) byFile.set(f.file, [])
		byFile.get(f.file).push(f)
	}
	for (const [file, list] of byFile) {
		console.log("\n" + rel(file))
		list.sort((a, b) => a.line - b.line)
		for (const f of list) {
			const loc = f.line ? `${f.line}:${f.col}` : "-"
			const n = f.count > 1 ? ` (x${f.count})` : ""
			console.log(`  ${loc.padEnd(9)} ${f.level.padEnd(5)} ${f.id.padEnd(22)} ${f.msg}${n}`)
			if (f.snippet) console.log(`  ${" ".repeat(9)}       > ${f.snippet}`)
		}
	}
}

const bar = "-".repeat(66)
console.log("\n" + bar)
console.log(
	`viora-design-skills: ${errors.length} error${errors.length === 1 ? "" : "s"}, ` +
		`${warns.length} warning${warns.length === 1 ? "" : "s"} in ${files.length} file${files.length === 1 ? "" : "s"}`,
)
if (errors.length === 0 && warns.length === 0) {
	console.log("clean. mechanical floor passed. now do the screenshot round.")
} else {
	console.log("fix every error. decide on every warning, or suppress it with")
	console.log("a reason: /* viora-allow: rule-id why this is correct here */")
	console.log("why a rule exists, with a before and an after: node scripts/explain.mjs <rule-id>")
}
console.log(bar)

const strict = flags.has("--strict")
process.exit(errors.length > 0 || (strict && warns.length > 0) ? 1 : 0)
