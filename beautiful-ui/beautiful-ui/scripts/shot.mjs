#!/usr/bin/env node
/**
 * beautiful-ui / screenshot helper for the verify gate
 *
 * One round, desktop and mobile together. Never two rounds.
 *
 *   node shot.mjs http://localhost:3000
 *   node shot.mjs http://localhost:3000 --out .bui-shots
 *   node shot.mjs ./dist/index.html --full
 *   node shot.mjs http://localhost:5173 --sizes 1440x900,390x844,768x1024
 *   node shot.mjs http://localhost:3000 --squint    silhouette test: grayscale + blur
 *   node shot.mjs http://localhost:3000 --icon      scale test: the page at 20 percent
 *
 * --squint answers "is this still recognisable as this product with the type gone".
 * --icon answers "does the hierarchy and the primary action survive being small".
 * Both are design tests, not screenshots. Look at them, do not just save them.
 *
 * Tries, in order:
 *   1. playwright, if installed in the project
 *   2. puppeteer, if installed in the project
 *   3. a chromium binary on PATH, via --headless --screenshot
 *
 * If none is available it prints exactly what to ask the user for, and exits 3.
 * Do not skip the visual check because the tooling was awkward.
 */

import { spawnSync } from "node:child_process"
import { mkdirSync, existsSync, writeFileSync, rmSync } from "node:fs"
import { resolve, join, basename } from "node:path"

const argv = process.argv.slice(2)
const positional = argv.filter((a) => !a.startsWith("--"))
const getFlag = (name, fallback) => {
	const i = argv.findIndex((a) => a === `--${name}` || a.startsWith(`--${name}=`))
	if (i === -1) return fallback
	if (argv[i].includes("=")) return argv[i].split("=").slice(1).join("=")
	return argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : true
}

let target = positional[0]
if (!target) {
	console.error(
		"usage: node shot.mjs <url|file> [--out dir] [--sizes 1440x900,390x844] [--full] [--squint] [--icon] [--scale n]",
	)
	process.exit(2)
}
if (!/^https?:\/\//.test(target) && !target.startsWith("file://")) {
	target = "file://" + resolve(target)
}

const outDir = resolve(String(getFlag("out", ".bui-shots")))
const fullPage = Boolean(getFlag("full", false))
const squint = Boolean(getFlag("squint", false))
const iconMode = Boolean(getFlag("icon", false))
const scale = Number(getFlag("scale", iconMode ? 0.2 : 2)) || (iconMode ? 0.2 : 2)
const SQUINT_CSS = "html { filter: grayscale(1) blur(2.5px) }"
const sizes = String(getFlag("sizes", "1440x900,390x844"))
	.split(",")
	.map((s) => s.trim())
	.filter(Boolean)
	.map((s) => {
		const [w, h] = s.split("x").map(Number)
		return { w: w || 1440, h: h || 900, label: `${w || 1440}x${h || 900}` }
	})

if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true })

const suffix = `${squint ? "-squint" : ""}${iconMode ? "-icon" : ""}`
const name = (s) =>
	join(outDir, `${s.w >= 1024 ? "desktop" : s.w >= 700 ? "tablet" : "mobile"}-${s.label}${suffix}.png`)

// playwright can be installed while its bundled browser is not downloaded.
// Try the bundled binary, then a system Chrome or Chromium, then give up quietly
// so the next backend gets its turn. A verify gate that crashes is worse than
// a verify gate that degrades.
// A filter that fails to attach turns the silhouette test into a normal
// screenshot that looks fine. Attach it, then read back the computed value and
// say so out loud if it did not take.
async function applySquint(page) {
	if (!squint) return
	const filter = await page
		.evaluate(() => {
			const tag = document.createElement("style")
			tag.textContent = "html { filter: grayscale(1) blur(2.5px) !important }"
			document.documentElement.appendChild(tag)
			return getComputedStyle(document.documentElement).filter
		})
		.catch(() => "none")
	if (!filter || filter === "none") {
		console.error("note: --squint filter did not attach. Treat the saved shot as unfiltered.")
		return
	}
	await page.waitForTimeout(120)
}

// Chromium refuses a deviceScaleFactor below 0.5, so the icon test is done by
// re-rendering the finished capture at the requested fraction inside a wrapper
// page. Same pixels the eye would get on a tab strip.
async function shrink(page, file, s) {
	const w = Math.max(1, Math.round(s.w * scale))
	const h = Math.max(1, Math.round(s.h * scale))
	const wrapper = join(outDir, ".bui-icon.html")
	writeFileSync(
		wrapper,
		`<style>html,body{margin:0;background:#fff}img{display:block;width:${w}px}</style><img src="${basename(file)}" alt="">`,
	)
	try {
		await page.setViewportSize({ width: w, height: h })
		await page.goto("file://" + wrapper, { waitUntil: "load", timeout: 10_000 })
		await page.waitForTimeout(150)
		await page.screenshot({ path: file })
	} catch {
		console.error("note: --icon downscale failed. The shot is at the smallest scale chromium allows.")
	} finally {
		rmSync(wrapper, { force: true })
	}
}

async function launchPlaywright(pw) {
	const attempts = [{ args: ["--no-sandbox"] }]
	const local = findChrome()
	if (local) attempts.push({ executablePath: local, chromiumSandbox: false, args: ["--no-sandbox"] })
	attempts.push({ channel: "chrome", args: ["--no-sandbox"] })
	for (const opts of attempts) {
		try {
			return await pw.chromium.launch(opts)
		} catch {}
	}
	return null
}

async function tryPlaywright() {
	let pw
	try {
		pw = await import("playwright")
	} catch {
		try {
			pw = await import("playwright-core")
		} catch {
			return false
		}
	}
	const browser = await launchPlaywright(pw)
	if (!browser) {
		console.error("note: playwright is installed but no browser binary launched. Trying the next backend.")
		return false
	}
	try {
	for (const s of sizes) {
		const ctx = await browser.newContext({
			viewport: { width: s.w, height: s.h },
			deviceScaleFactor: iconMode ? 1 : scale,
			isMobile: s.w < 700,
			hasTouch: s.w < 700,
		})
		const page = await ctx.newPage()
		// load, not networkidle: a blocked webfont must not stall the gate for 30s
		await page.goto(target, { waitUntil: "load", timeout: 20_000 }).catch(() => {})
		await page.waitForLoadState("networkidle", { timeout: 3_000 }).catch(() => {})
		await page.waitForTimeout(400)
		await applySquint(page)
		await page.screenshot({ path: name(s), fullPage })
		if (iconMode) await shrink(page, name(s), s)
		await ctx.close()
		console.log("wrote " + name(s))
	}
	} catch (err) {
		console.error("note: playwright capture failed (" + String(err && err.message ? err.message.split("\n")[0] : err) + "). Trying the next backend.")
		await browser.close().catch(() => {})
		return false
	}
	await browser.close()
	return true
}

async function tryPuppeteer() {
	let pp
	try {
		pp = await import("puppeteer")
	} catch {
		return false
	}
	let browser
	try {
		browser = await (pp.default ?? pp).launch({ args: ["--no-sandbox"] })
	} catch {
		return false
	}
	for (const s of sizes) {
		const page = await browser.newPage()
		await page.setViewport({ width: s.w, height: s.h, deviceScaleFactor: scale, isMobile: s.w < 700 })
		await page.goto(target, { waitUntil: "networkidle2", timeout: 30_000 }).catch(() => {})
		await new Promise((r) => setTimeout(r, 400))
		if (squint) await page.addStyleTag({ content: SQUINT_CSS }).catch(() => {})
		await page.screenshot({ path: name(s), fullPage })
		await page.close()
		console.log("wrote " + name(s))
	}
	await browser.close()
	return true
}

function findChrome() {
	const candidates = [
		process.env.BUI_CHROME,
		process.env.CHROME_PATH,
		"google-chrome",
		"google-chrome-stable",
		"chromium",
		"chromium-browser",
		"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
		"/Applications/Chromium.app/Contents/MacOS/Chromium",
		"/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
	].filter(Boolean)
	for (const c of candidates) {
		const probe = spawnSync(c, ["--version"], { encoding: "utf8" })
		if (probe.error || probe.status !== 0) continue
		if (c.includes("/")) return c
		// playwright needs a real path. A bare name works for the CLI fallback and
		// fails silently as an executablePath, which is how the squint test got lost.
		const which = spawnSync("which", [c], { encoding: "utf8" })
		const resolved = which.status === 0 ? String(which.stdout).trim().split("\n")[0] : ""
		return resolved || c
	}
	return null
}

function tryChromeCli() {
	const chrome = findChrome()
	if (!chrome) return false
	if (squint) {
		console.error("note: --squint needs playwright or puppeteer. This fallback captured the page unfiltered.")
	}
	if (iconMode) {
		console.error("note: chromium floors the scale factor at 0.5, so this fallback icon shot is larger than 20 percent.")
	}
	for (const s of sizes) {
		const res = spawnSync(
			chrome,
			[
				"--headless=new",
				"--disable-gpu",
				"--no-sandbox",
				"--hide-scrollbars",
				`--force-device-scale-factor=${scale}`,
				`--window-size=${s.w},${s.h}`,
				`--screenshot=${name(s)}`,
				"--virtual-time-budget=4000",
				target,
			],
			{ encoding: "utf8", timeout: 60_000 },
		)
		if (res.status === 0 || existsSync(name(s))) console.log("wrote " + name(s))
		else console.error("chrome failed for " + s.label + (res.stderr ? ": " + res.stderr.trim().split("\n")[0] : ""))
	}
	return true
}

const ok = (await tryPlaywright()) || (await tryPuppeteer()) || tryChromeCli()

if (!ok) {
	console.error(
		[
			"",
			"No screenshot backend found. Options, cheapest first:",
			"",
			"  1. npx playwright install chromium   then rerun this script",
			"  2. npm i -D puppeteer                then rerun this script",
			"  3. Ask the user for two screenshots of " + target + ":",
			"     desktop at 1440 wide and mobile at 390 wide.",
			"",
			"Do not skip the visual check. It catches what the linter cannot.",
			"",
		].join("\n"),
	)
	process.exit(3)
}

console.log(
	[
		"",
		"Now look at the images and answer these, honestly:",
		"  1 does the first screen say what this is in two seconds",
		"  2 is there one obvious next action",
		"  3 does any section look like a placeholder",
		"  4 is the left alignment edge held down the page",
		"  5 is space above headings larger than below",
		"  6 do any two adjacent sections share the same shape and width",
		"  7 mobile: anything overflowing, clipped, or under 44px",
		"  8 does the type hierarchy survive a squint",
		"  9 anything accidental: stray gap, misaligned icon, orphan word",
		" 10 would a designer say this was decided, or generated",
		"",
		"Then run --squint and --icon and answer two more:",
		" 11 squint: with the type unreadable, is the silhouette still this product and not any product",
		" 12 icon: at 20 percent, does one thing still dominate and is the primary action still findable",
		"",
		"Fix everything found in ONE batch, take one confirming shot, then stop.",
		"",
	].join("\n"),
)
