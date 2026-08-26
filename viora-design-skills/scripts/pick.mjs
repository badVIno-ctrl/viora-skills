#!/usr/bin/env node
/**
 * viora-design-skills / pick.mjs
 *
 * Offline catalog search over data/*.csv. Zero dependencies, no network, no Python.
 * Node 18+. Replaces guessing with selecting: palettes, type pairs, styles, landing
 * patterns, UX rules, motion tiers, icons, product routing, per stack notes.
 *
 *   node pick.mjs "fintech dashboard trust" --domain palette
 *   node pick.mjs "editorial long read" --domain type
 *   node pick.mjs "russian saas landing" --domain type --cyrillic
 *   node pick.mjs "modal focus trap" --domain ux
 *   node pick.mjs "page transition" --domain motion --tier subtle
 *   node pick.mjs "nextjs" --domain stack
 *   node pick.mjs "b2b analytics for ops teams" --system
 *   node pick.mjs --list-domains
 *
 * Flags: --domain <name>  -n <count>  --tier <text>  --cyrillic  --full  --css  --json
 *
 * The catalog is raw material. The laws in SKILL.md outrank every row it returns.
 */

import { readFileSync, existsSync, readdirSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { dirname, join, basename } from "node:path"

const HERE = dirname(fileURLToPath(import.meta.url))
const DATA = join(HERE, "..", "data")
const TRUNCATE = 300

/* ------------------------------------------------------------------ domains */

const DOMAINS = {
	palette: {
		file: "palettes.csv",
		boost: ["Product Type", "Notes"],
		head: ["Product Type"],
		what: "192 token sets by product type",
	},
	type: {
		file: "type-pairs.csv",
		boost: ["Font Pairing Name", "Category", "Mood/Style Keywords", "Best For"],
		head: ["Font Pairing Name"],
		what: "74 font pairings, Latin first",
	},
	cyrillic: {
		file: "cyrillic-pairs.csv",
		boost: ["Pairing Name", "Register", "Mood Keywords", "Best For"],
		head: ["Pairing Name"],
		what: "26 pairings that actually ship Cyrillic",
	},
	style: {
		file: "styles.csv",
		boost: ["Style Category", "Type", "Keywords", "Aliases", "AI Prompt Keywords"],
		head: ["Style Category", "Type"],
		drop: ["Design System Variables", "Parent Style ID", "Replacement Domain", "Replacement ID"],
		what: "79 named visual styles with what they are wrong for",
	},
	product: {
		file: "products.csv",
		boost: ["Product Type", "Keywords"],
		head: ["Product Type"],
		what: "192 product types routed to style, pattern and palette",
	},
	landing: {
		file: "landing.csv",
		boost: ["Pattern Name", "Keywords", "Aliases"],
		head: ["Pattern Name"],
		what: "34 landing patterns with section order",
	},
	ux: {
		file: "ux-rules.csv",
		boost: ["Category", "Issue", "Platform"],
		head: ["Issue"],
		what: "119 UX rules with good and bad code",
	},
	app: {
		file: "app-interface.csv",
		boost: ["Category", "Issue", "Keywords", "Platform"],
		head: ["Issue"],
		what: "32 in-product interface rules",
	},
	motion: {
		file: "motion.csv",
		boost: ["Category", "Keywords", "Intensity Tier", "Trigger"],
		head: ["Category"],
		what: "17 motion recipes by intensity tier",
	},
	icons: {
		file: "icons.csv",
		boost: ["Icon Name", "Keywords", "Category", "Semantic Role"],
		head: ["Icon Name"],
		what: "105 icons by semantic role",
	},
	charts: { file: "charts.csv", boost: [], head: [], what: "chart selection and data ink" },
	reasoning: {
		file: "ui-reasoning.csv",
		boost: ["UI_Category", "Recommended_Pattern"],
		head: ["UI_Category"],
		what: "192 UI categories with decision rules and anti-patterns",
	},
	react: { file: "react-performance.csv", boost: [], head: [], what: "React performance rules" },
	stack: { stacks: true, what: "22 stacks, implementation notes per framework" },
}

/* ------------------------------------------------------------------- args */

const argv = process.argv.slice(2)
const flag = (name, fallback = false) => {
	const i = argv.findIndex((a) => a === `--${name}` || a.startsWith(`--${name}=`))
	if (i === -1) return fallback
	if (argv[i].includes("=")) return argv[i].split("=").slice(1).join("=")
	const next = argv[i + 1]
	return next && !next.startsWith("-") ? next : true
}
const has = (name) => argv.includes(`--${name}`)

if (has("list-domains")) {
	console.log("viora catalog domains\n")
	for (const [name, d] of Object.entries(DOMAINS)) {
		console.log(`  ${name.padEnd(10)} ${d.what}`)
	}
	console.log("\n  --system   one call that returns a whole starting kit")
	process.exit(0)
}

const VALUE_FLAGS = new Set(["domain", "n", "tier"])
const positional = []
for (let i = 0; i < argv.length; i++) {
	const a = argv[i]
	if (a.startsWith("--")) {
		const name = a.slice(2).split("=")[0]
		if (VALUE_FLAGS.has(name) && !a.includes("=")) i++
		continue
	}
	if (a === "-n") {
		i++
		continue
	}
	if (a.startsWith("-")) continue
	positional.push(a)
}
const query = positional.join(" ").trim()
const wantSystem = has("system")
const asJson = has("json")
const full = has("full")
const cyrillic = has("cyrillic")
const tier = flag("tier", "")
const dashN = argv.indexOf("-n")
const countRaw = dashN !== -1 ? argv[dashN + 1] : flag("n", "")
const limit = Math.max(1, Number(countRaw) || (wantSystem ? 2 : 5))
let domain = String(flag("domain", wantSystem ? "" : "style"))
if (cyrillic && domain === "type") domain = "cyrillic"

if (!existsSync(DATA)) {
	console.error(`no data directory at ${DATA}. The catalog ships inside the skill folder.`)
	process.exit(3)
}
if (!query) {
	console.error('usage: node pick.mjs "<what you are designing>" [--domain palette|type|style|product|landing|ux|app|motion|icons|reasoning|charts|react|stack] [--system] [-n 5] [--cyrillic] [--tier subtle] [--full] [--css] [--json]')
	process.exit(2)
}

/* -------------------------------------------------------------- csv parsing */

function parseCsv(text) {
	const rows = []
	let row = []
	let field = ""
	let quoted = false
	for (let i = 0; i < text.length; i++) {
		const c = text[i]
		if (quoted) {
			if (c === '"') {
				if (text[i + 1] === '"') {
					field += '"'
					i++
				} else quoted = false
			} else field += c
			continue
		}
		if (c === '"') quoted = true
		else if (c === ",") {
			row.push(field)
			field = ""
		} else if (c === "\n") {
			row.push(field)
			rows.push(row)
			row = []
			field = ""
		} else if (c !== "\r") field += c
	}
	if (field.length || row.length) {
		row.push(field)
		rows.push(row)
	}
	return rows.filter((r) => r.some((v) => v && v.trim()))
}

function loadTable(file) {
	const path = join(DATA, file)
	if (!existsSync(path)) return null
	const rows = parseCsv(readFileSync(path, "utf8"))
	if (!rows.length) return null
	const header = rows[0].map((h) => h.trim())
	const records = rows.slice(1).map((r) => {
		const o = {}
		header.forEach((h, i) => {
			o[h] = (r[i] ?? "").trim()
		})
		return o
	})
	return { header, records, file }
}

/* ------------------------------------------------------------- tokenising */

const WORD = /[\p{L}\p{N}]+/gu
const tokenise = (s) => String(s).toLowerCase().match(WORD) || []

/* Russian stems mapped onto the English vocabulary the catalog is written in. */
const STEMS = [
	[["дашборд", "панел", "админ"], "dashboard admin analytics"],
	[["банк", "финтех", "финанс", "платеж", "платёж", "инвест"], "banking fintech finance payments trust"],
	[["магазин", "товар", "корзин", "ecommerce", "маркетплейс"], "ecommerce shop store marketplace retail"],
	[["лендинг", "промо", "презентац"], "landing marketing hero conversion"],
	[["медицин", "здоров", "клиник", "врач", "аптек"], "health medical clinic care"],
	[["образован", "учеб", "курс", "школ", "универ"], "education learning course school"],
	[["игр", "гейм"], "game gaming entertainment"],
	[["путешеств", "турист", "отел", "билет"], "travel hotel booking tourism"],
	[["еда", "ресторан", "кафе", "кухн", "доставк"], "food restaurant cafe delivery"],
	[["спорт", "фитнес", "трениров"], "sport fitness training gym"],
	[["недвижим", "аренд", "жиль"], "real estate property rental"],
	[["юрид", "юрист", "право", "адвокат"], "legal law firm compliance"],
	[["крипт", "блокчейн", "web3", "токен"], "crypto blockchain web3"],
	[["аналитик", "метрик", "отчёт", "отчет", "график", "диаграмм"], "analytics metrics report chart data"],
	[["тёмн", "темн", "ноч"], "dark night"],
	[["светл", "дневн"], "light"],
	[["минимал", "чист", "лакон"], "minimal clean swiss"],
	[["шрифт", "типограф", "гарнитур"], "font typography typeface"],
	[["палитр", "цвет", "колор"], "palette color colour"],
	[["кнопк"], "button cta"],
	[["форм", "ввод", "поле"], "form input field validation"],
	[["таблиц", "список", "строк"], "table list row data grid"],
	[["модальн", "диалог", "попап", "окн"], "modal dialog popup overlay"],
	[["анимац", "движен", "переход"], "animation motion transition"],
	[["мобильн", "телефон", "смартфон"], "mobile phone responsive touch"],
	[["портфол", "галере", "фото"], "portfolio gallery photography showcase"],
	[["агентств", "студи"], "agency studio creative"],
	[["стартап", "саас", "сервис"], "startup saas b2b product"],
	[["корпорат", "предприят", "энтерпрайз"], "enterprise corporate b2b"],
	[["довер", "надежн", "надёжн", "безопасн"], "trust reliable security"],
	[["премиум", "люкс", "роскош", "дорог"], "luxury premium expensive"],
	[["детск", "ребён", "ребен", "школьник"], "kids children playful"],
	[["новост", "меди", "журнал", "стать", "блог"], "news media magazine article blog editorial"],
	[["государств", "госуслуг", "муниципал"], "government civic public sector"],
	[["разработчик", "девелопер", "код", "апи", "api"], "developer devtool api code technical"],
	[["логистик", "склад", "доставка", "перевоз"], "logistics warehouse shipping industrial"],
	[["производств", "заводск", "промышл"], "manufacturing industrial hardware"],
	[["красот", "косметик", "мод", "одежд"], "beauty cosmetics fashion apparel"],
	[["страх"], "insurance finance trust"],
	[["календар", "расписан", "бронир"], "calendar schedule booking"],
	[["чат", "мессендж", "сообщен"], "chat messaging inbox"],
	[["поиск", "фильтр", "сортир"], "search filter sort"],
	[["настройк", "профил", "аккаунт"], "settings profile account"],
	[["тариф", "цен", "подписк", "оплат"], "pricing plans subscription checkout"],
	[["отзыв", "социальн"], "testimonial social proof reviews"],
	[["загрузк", "скорост", "производительн"], "performance loading speed"],
	[["доступн"], "accessibility a11y contrast"],
]

function expand(tokens) {
	const out = new Set(tokens)
	for (const t of tokens) {
		for (const [stems, add] of STEMS) {
			if (stems.some((s) => t.startsWith(s))) {
				for (const w of add.split(" ")) out.add(w)
			}
		}
	}
	return [...out]
}

/* ------------------------------------------------------------------ scoring */

const K1 = 1.4
const B = 0.62

function rank(table, cfg, rawQuery, count, tierFilter) {
	const qTokens = expand(tokenise(rawQuery))
	if (!qTokens.length) return []
	const boostCols = new Set(cfg.boost || [])
	const docs = []
	for (const rec of table.records) {
		if (tierFilter) {
			const blob = Object.values(rec).join(" ").toLowerCase()
			if (!blob.includes(String(tierFilter).toLowerCase())) continue
		}
		const plain = []
		const keyed = []
		for (const [k, v] of Object.entries(rec)) {
			if (!v) continue
			const t = tokenise(`${k} ${v}`)
			if (boostCols.has(k)) keyed.push(...t, ...t)
			plain.push(...t)
		}
		const tf = new Map()
		for (const t of [...plain, ...keyed]) tf.set(t, (tf.get(t) || 0) + 1)
		docs.push({ rec, tf, len: plain.length + keyed.length, blob: Object.values(rec).join(" ").toLowerCase() })
	}
	if (!docs.length) return []
	const avg = docs.reduce((s, d) => s + d.len, 0) / docs.length
	const df = new Map()
	for (const t of new Set(qTokens)) {
		let n = 0
		for (const d of docs) if (d.tf.has(t)) n++
		df.set(t, n)
	}
	const phrase = rawQuery.toLowerCase().trim()
	const scored = docs.map((d) => {
		let score = 0
		for (const t of qTokens) {
			const f = d.tf.get(t)
			if (!f) continue
			const n = df.get(t) || 0
			const idf = Math.log(1 + (docs.length - n + 0.5) / (n + 0.5))
			score += idf * ((f * (K1 + 1)) / (f + K1 * (1 - B + (B * d.len) / avg)))
		}
		if (phrase.length > 5 && d.blob.includes(phrase)) score += 2.5
		return { ...d, score }
	})
	return scored
		.filter((d) => d.score > 0)
		.sort((a, b) => b.score - a.score)
		.slice(0, count)
}

/* ------------------------------------------------------------------ render */

const clip = (s) => (full || s.length <= TRUNCATE ? s : `${s.slice(0, TRUNCATE)} [+${s.length - TRUNCATE} chars, --full]`)

function headline(rec, cfg) {
	const cols = (cfg.head || []).filter((c) => rec[c])
	if (cols.length) return cols.map((c) => rec[c]).join(" / ")
	const first = Object.entries(rec).find(([k, v]) => k !== "No" && v)
	return first ? first[1] : "row"
}

function render(hits, cfg, label) {
	if (!hits.length) {
		console.log(`no rows matched in ${label}. Widen the query or use the digest in reference/16-catalog.md`)
		return
	}
	const drop = new Set(["No", ...(cfg.drop || [])])
	for (const h of hits) {
		const num = h.rec.No ? `#${h.rec.No}` : ""
		console.log(`\n${num} ${headline(h.rec, cfg)}  ${"".padEnd(1)}[${h.score.toFixed(2)}]`)
		for (const [k, v] of Object.entries(h.rec)) {
			if (!v || drop.has(k)) continue
			if ((cfg.head || []).includes(k)) continue
			console.log(`   ${k}: ${clip(v.replace(/\s+/g, " "))}`)
		}
	}
}

/* ------------------------------------------------------------------ stacks */

function stackSearch(q, count) {
	const dir = join(DATA, "stacks")
	if (!existsSync(dir)) {
		console.log("no stack data shipped")
		return
	}
	const files = readdirSync(dir).filter((f) => f.endsWith(".csv"))
	const tokens = tokenise(q)
	const named = files.filter((f) => tokens.some((t) => basename(f, ".csv").toLowerCase().includes(t)))
	const pool = named.length ? named : files
	if (named.length) console.log(`stack files matched: ${named.join(", ")}`)
	let shown = 0
	for (const f of pool) {
		const table = loadTable(join("stacks", f))
		if (!table) continue
		const cfg = { boost: table.header.slice(0, 3), head: [table.header[1] || table.header[0]] }
		const hits = rank(table, cfg, named.length ? q : q, named.length ? count : 2, "")
		if (!hits.length) continue
		console.log(`\n--- ${basename(f, ".csv")} ---`)
		render(hits, cfg, f)
		shown += hits.length
		if (shown >= count * 2) break
	}
	if (!shown) console.log(`no stack rows matched "${q}". Available: ${files.map((f) => basename(f, ".csv")).join(", ")}`)
}

/* -------------------------------------------------------------------- main */

function runOne(name, count, tierFilter) {
	const cfg = DOMAINS[name]
	if (!cfg) {
		console.error(`unknown domain "${name}". Run --list-domains`)
		process.exit(2)
	}
	if (cfg.stacks) {
		stackSearch(query, count)
		return []
	}
	const table = loadTable(cfg.file)
	if (!table) {
		console.log(`data/${cfg.file} is not present in this copy of the skill`)
		return []
	}
	const hits = rank(table, cfg, query, count, tierFilter)
	return hits.map((h) => ({ domain: name, score: Number(h.score.toFixed(3)), row: h.rec }))
}

if (asJson) {
	const domains = wantSystem
		? ["palette", cyrillic ? "cyrillic" : "type", "style", "landing", "motion", "product"]
		: [domain]
	const out = {}
	for (const d of domains) {
		const cfg = DOMAINS[d]
		if (!cfg || cfg.stacks) continue
		const table = loadTable(cfg.file)
		if (!table) continue
		out[d] = rank(table, cfg, query, limit, d === "motion" ? tier : "").map((h) => ({
			score: Number(h.score.toFixed(3)),
			row: h.rec,
		}))
	}
	console.log(JSON.stringify({ query, system: wantSystem, results: out }, null, 2))
	process.exit(0)
}

if (wantSystem) {
	console.log(`viora catalog / starting kit for "${query}"`)
	console.log("=".repeat(72))
	const plan = [
		["1. PALETTE", "palette", 2],
		[`2. TYPE${cyrillic ? " (Cyrillic safe)" : ""}`, cyrillic ? "cyrillic" : "type", 2],
		["3. STYLE", "style", 2],
		["4. LANDING PATTERN", "landing", 1],
		["5. MOTION", "motion", 1],
		["6. PRODUCT ROUTING", "product", 1],
	]
	for (const [title, name, n] of plan) {
		console.log(`\n${title}`)
		console.log("-".repeat(72))
		const cfg = DOMAINS[name]
		const table = loadTable(cfg.file)
		if (!table) {
			console.log(`  data/${cfg.file} missing`)
			continue
		}
		render(rank(table, cfg, query, n, name === "motion" ? tier : ""), cfg, cfg.file)
	}
	console.log(`\n${"=".repeat(72)}`)
	console.log("Before you use any of this:")
	console.log("  1. The thesis comes first. A palette without a thesis is a competent page nobody remembers.")
	console.log("  2. Take the hex values and the font pair. Leave the era decoration behind.")
	console.log("  3. Run: node scripts/contrast.mjs <your token file>. The number decides, not the CSV.")
	console.log("  4. Cyrillic copy needs a Cyrillic face. Use --cyrillic or data/cyrillic-pairs.csv.")
	console.log("  5. If this is the same row you used last project, take the next one.")
	console.log("  6. Write what you took into DESIGN.md so the next session matches instead of re-deciding.")
	process.exit(0)
}

const cfg = DOMAINS[domain]
if (!cfg) {
	console.error(`unknown domain "${domain}". Run --list-domains`)
	process.exit(2)
}
if (cfg.stacks) {
	console.log(`viora catalog / stack notes for "${query}"`)
	stackSearch(query, limit)
	process.exit(0)
}
const table = loadTable(cfg.file)
if (!table) {
	console.log(`data/${cfg.file} is not present in this copy of the skill`)
	process.exit(3)
}
const hits = rank(table, cfg, query, limit, domain === "motion" ? tier : "")
console.log(`viora catalog / ${domain} / "${query}" / ${hits.length} of ${table.records.length} rows`)
render(hits, cfg, cfg.file)
/* ------------------------------------------------------------------- --css */

/* A catalog row is a set of hex values in someone else's naming. --css maps it
   onto the viora token layer so the model pastes an EDIT 1 block instead of
   inventing variable names. The row decides the hues, contrast.mjs decides
   whether they ship. */

const hexOf = (s) => {
	const m = String(s || "").trim().match(/^#?([0-9a-fA-F]{6})$/)
	return m ? `#${m[1].toLowerCase()}` : null
}
const rgbOf = (h) => [1, 3, 5].map((i) => Number.parseInt(h.slice(i, i + 2), 16))
const chan = (c) => {
	const s = c / 255
	return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const lumOf = (h) => {
	const [r, g, b] = rgbOf(h)
	return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)
}
const mixHex = (a, b, t) => {
	const [ar, ag, ab] = rgbOf(a)
	const [br, bg, bb] = rgbOf(b)
	const part = (x, y) =>
		Math.round(x + (y - x) * t)
			.toString(16)
			.padStart(2, "0")
	return `#${part(ar, br)}${part(ag, bg)}${part(ab, bb)}`
}

function paletteCss(rec) {
	const pickHex = (...keys) => {
		for (const k of keys) {
			const h = hexOf(rec[k])
			if (h) return h
		}
		return null
	}
	const ground = pickHex("Background")
	const ink = pickHex("Foreground")
	if (!ground || !ink) {
		console.log("\nthis row carries no usable Background and Foreground hex. Use assets/palettes.css instead: 13 measured palettes, paste ready.")
		return
	}
	const dark = lumOf(ground) < 0.2
	const mode = dark ? "dark" : "light"
	const other = dark ? "light" : "dark"
	const border = pickHex("Border") || mixHex(ground, ink, 0.16)
	const mutedInk = pickHex("Muted Foreground") || mixHex(ink, ground, 0.35)
	const accent = pickHex("Primary", "Accent") || ink
	const rows = [
		["canvas", ground],
		["surface", pickHex("Card") || mixHex(ground, ink, 0.04)],
		["surface-2", pickHex("Muted") || mixHex(ground, ink, 0.08)],
		["hairline", border],
		["hairline-strong", mixHex(border, ink, 0.35)],
		["ink", ink],
		["ink-muted", mutedInk],
		["ink-subtle", mixHex(mutedInk, ground, 0.3)],
		["accent", accent],
		["accent-ink", pickHex("On Primary", "On Accent") || ground],
		["control-border", mixHex(border, ink, 0.45)],
		["danger", pickHex("Destructive") || (dark ? "#ff6b6b" : "#c0261f")], /* viora-allow: raw-hex semantic fallback when the catalog row omits Destructive */
	]
	console.log(`\n/* EDIT 1 from data/${cfg.file} row #${rec.No || "?"}: ${rec["Product Type"] || "palette"}, ${mode} mode */`)
	console.log(":root {")
	for (const [name, value] of rows) console.log(`\t--${name}-${mode}: ${value};`)
	console.log(`\t/* ${other} column: keep the graphite defaults from assets/tokens.css, or take a ${other} palette from assets/palettes.css */`)
	console.log("}")
	const ratio = (a, b) => {
		const [hi, lo] = [lumOf(a), lumOf(b)].sort((x, y) => y - x)
		return (hi + 0.05) / (lo + 0.05)
	}
	const onGround = ratio(accent, ground)
	if (onGround < 3) {
		console.log(`\nwatch out: this row's accent measures ${onGround.toFixed(2)}:1 against the ground. That is a surface colour, not an accent.`)
		const alt = [pickHex("Ring"), pickHex("Accent"), pickHex("Secondary")].find((h) => h && h !== accent && ratio(h, ground) >= 3)
		if (alt) console.log(`use ${alt} instead: ${ratio(alt, ground).toFixed(2)}:1 against the ground.`)
		else console.log("no column in this row clears 3:1. Take the accent from assets/palettes.css, all 13 are measured.")
	}
	console.log(`\nfocus ring: ${pickHex("Ring") || accent}. Semantic success and warning stay as they are in tokens.css.`)
	console.log("then: node scripts/contrast.mjs <your token file>")
	console.log("if a pair fails, move the failing token, not the accent. The palette is a starting point, the ratio is the rule.")
}

if (domain === "palette" && has("css")) paletteCss(hits[0]?.rec || {})
else if (domain === "palette") console.log("\nnext: paste into the token layer, then node scripts/contrast.mjs <token file>. Add --css to get the EDIT 1 block written for you.")
if (domain === "type" && !cyrillic) console.log("\nnote: if the copy has Cyrillic, rerun with --cyrillic. Most fashionable Latin faces have no Cyrillic.")
