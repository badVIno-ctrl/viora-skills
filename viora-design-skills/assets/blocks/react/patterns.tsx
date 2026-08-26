/*
  Виора block library / React patterns

  These are the six places where generated React goes wrong: state that should
  live in the URL, uncontrolled inputs, a sort that recomputes on every render,
  numbers formatted by hand, a dialog that traps nothing and ignores Escape,
  and a toast that no screen reader ever hears.

  Styling: reuse the classes from assets/blocks/html/app.html, or map them to
  your own utilities. No colour, size or duration is written here on purpose,
  so a palette change never touches this file.

  Checked by: node scripts/check.mjs assets/blocks/react/patterns.tsx assets/tokens.css
              node scripts/wig.mjs   assets/blocks/react/patterns.tsx
*/

import {
	useCallback,
	useEffect,
	useId,
	useMemo,
	useRef,
	useState,
	type ReactNode,
} from "react"

/* Formatters are built once. Building them in render is slow, and formatting by
   hand is how a server and a client end up disagreeing about a comma. */
const count = new Intl.NumberFormat("en-US")
const day = new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short" })
const clock = new Intl.DateTimeFormat("en-US", { hour: "2-digit", minute: "2-digit" })

/* ------------------------------------------------------------------------- */
/* 1. State a person can send to a colleague                                 */
/* ------------------------------------------------------------------------- */

/**
 * Tab, filter, sort and query belong in the URL. If reloading the page loses
 * the view, the view was never real. Keep useState for things nobody would
 * ever link to: an open menu, a hovered row, a pending keystroke.
 */
export function useUrlState(key: string, fallback: string) {
	const read = useCallback(() => {
		if (typeof window === "undefined") return fallback
		return new URLSearchParams(window.location.search).get(key) ?? fallback
	}, [key, fallback])

	const [value, setValue] = useState(read)

	useEffect(() => {
		const sync = () => setValue(read())
		window.addEventListener("popstate", sync)
		return () => window.removeEventListener("popstate", sync)
	}, [read])

	const set = useCallback(
		(next: string) => {
			setValue(next)
			const url = new URL(window.location.href)
			if (next === fallback) url.searchParams.delete(key)
			else url.searchParams.set(key, next)
			window.history.replaceState(null, "", url)
		},
		[key, fallback],
	)

	return [value, set] as const
}

/* ------------------------------------------------------------------------- */
/* 2. Tabs: one tab stop, arrows move, the panel is labelled                 */
/* ------------------------------------------------------------------------- */

export type Tab = { id: string; label: string }

export function Tabs({
	tabs,
	value,
	onChange,
	label,
}: {
	tabs: Tab[]
	value: string
	onChange: (id: string) => void
	label: string
}) {
	const refs = useRef<Record<string, HTMLButtonElement | null>>({})

	const move = (step: number) => {
		const index = tabs.findIndex((tab) => tab.id === value)
		const next = tabs[(index + step + tabs.length) % tabs.length]
		onChange(next.id)
		refs.current[next.id]?.focus()
	}

	return (
		<div className="a-tabs" role="tablist" aria-label={label}>
			{tabs.map((tab) => {
				const selected = tab.id === value
				return (
					<button
						key={tab.id}
						ref={(node) => {
							refs.current[tab.id] = node
						}}
						className="a-tab"
						type="button"
						role="tab"
						id={`tab-${tab.id}`}
						aria-selected={selected}
						aria-controls={`panel-${tab.id}`}
						tabIndex={selected ? 0 : -1}
						onClick={() => onChange(tab.id)}
						onKeyDown={(event) => {
							if (event.key === "ArrowRight") {
								event.preventDefault()
								move(1)
							}
							if (event.key === "ArrowLeft") {
								event.preventDefault()
								move(-1)
							}
						}}
					>
						{tab.label}
					</button>
				)
			})}
		</div>
	)
}

/* ------------------------------------------------------------------------- */
/* 3. Table: sorted in a memo, numbers aligned, long text clipped safely     */
/* ------------------------------------------------------------------------- */

export type Note = {
	id: string
	title: string
	repository: string
	state: "published" | "waiting" | "rolled-back"
	/* An ISO string from the server. Never a Date built during render. */
	publishedAt: string
	readers: number
}

const STATE_LABEL: Record<Note["state"], string> = {
	published: "Published",
	waiting: "Waiting on approval",
	"rolled-back": "Rolled back",
}

const STATE_CLASS: Record<Note["state"], string> = {
	published: "a-pill a-pill-live",
	waiting: "a-pill a-pill-hold",
	"rolled-back": "a-pill a-pill-back",
}

export function NotesTable({
	notes,
	sort,
	onSortChange,
}: {
	notes: Note[]
	sort: "recent" | "readers"
	onSortChange: (next: "recent" | "readers") => void
}) {
	const rows = useMemo(() => {
		const copy = [...notes]
		copy.sort((a, b) =>
			sort === "readers"
				? b.readers - a.readers
				: b.publishedAt.localeCompare(a.publishedAt),
		)
		return copy
	}, [notes, sort])

	return (
		<div className="a-tablewrap">
			<table className="a-table">
				<caption>Published notes. Readers counted in the first 48 hours.</caption>
				<thead>
					<tr>
						<th scope="col" aria-sort={sort === "recent" ? "descending" : "none"}>
							<button className="a-sort" type="button" onClick={() => onSortChange("recent")}>
								Note
							</button>
						</th>
						<th scope="col">Repository</th>
						<th scope="col">State</th>
						<th scope="col">Published</th>
						<th scope="col" className="a-num" aria-sort={sort === "readers" ? "descending" : "none"}>
							<button className="a-sort" type="button" onClick={() => onSortChange("readers")}>
								Readers
							</button>
						</th>
					</tr>
				</thead>
				<tbody>
					{rows.map((note) => {
						const at = new Date(note.publishedAt)
						return (
							<tr key={note.id}>
								<td>
									{/* min-width: 0 is what makes the ellipsis appear inside a flex or grid cell */}
									<a className="a-clip" href={`/releases/${note.id}`}>
										{note.title}
									</a>
								</td>
								<td className="a-clip">{note.repository}</td>
								<td>
									<span className={STATE_CLASS[note.state]}>{STATE_LABEL[note.state]}</span>
								</td>
								<td>
									<time dateTime={note.publishedAt}>
										{day.format(at)}, {clock.format(at)}
									</time>
								</td>
								<td className="a-num">{count.format(note.readers)}</td>
							</tr>
						)
					})}
				</tbody>
			</table>
		</div>
	)
}

/* ------------------------------------------------------------------------- */
/* 4. Empty state: what happened, why it is fine, one way forward            */
/* ------------------------------------------------------------------------- */

export function EmptyState({
	title,
	body,
	action,
}: {
	title: string
	body: string
	action?: ReactNode
}) {
	return (
		<section className="a-empty">
			<h3>{title}</h3>
			<p>{body}</p>
			{action}
		</section>
	)
}

/* ------------------------------------------------------------------------- */
/* 5. Form: controlled, labelled, validated where the mistake was made       */
/* ------------------------------------------------------------------------- */

export function TokenForm({
	initialToken,
	onSave,
}: {
	initialToken: string
	onSave: (token: string) => Promise<void>
}) {
	const id = useId()
	const [token, setToken] = useState(initialToken)
	const [pending, setPending] = useState(false)
	const [error, setError] = useState<string | null>(null)

	const tokenId = `${id}-token`
	const errorId = `${id}-token-error`
	const hintId = `${id}-token-hint`

	return (
		<form
			className="a-panel"
			noValidate
			onSubmit={async (event) => {
				event.preventDefault()
				const value = token.trim()
				if (!value.startsWith("hal_")) {
					/* Validate on submit, not on every keystroke. Nobody wants to be
					   corrected while still typing the second character. */
					setError("Publish tokens start with hal_. Copy it from Settings, API tokens.")
					document.getElementById(tokenId)?.focus()
					return
				}
				setError(null)
				setPending(true)
				try {
					await onSave(value)
				} catch {
					setError("That token was rejected. Generate a new one and paste it again.")
				} finally {
					setPending(false)
				}
			}}
		>
			<div className="a-row">
				<label htmlFor={tokenId}>Publish token</label>
				<input
					className="a-field"
					id={tokenId}
					name="token"
					type="text"
					value={token}
					onChange={(event) => setToken(event.target.value)}
					autoComplete="off"
					spellCheck={false}
					aria-invalid={error ? true : undefined}
					aria-describedby={error ? errorId : hintId}
				/>
				{error ? (
					<span className="a-err" id={errorId} role="alert">
						{error}
					</span>
				) : (
					<span className="a-hint" id={hintId}>
						Rotating a token stops the old one within a minute.
					</span>
				)}
			</div>

			<div className="a-panel-actions">
				{/* The submit button is never disabled: a person must be able to press
				   it and be told what is wrong. Only the pending state locks it. */}
				<button className="a-btn a-btn-solid" type="submit" aria-busy={pending}>
					{pending ? "Saving\u2026" : "Save token"}
				</button>
			</div>
		</form>
	)
}

/* ------------------------------------------------------------------------- */
/* 6. Dialog: native element, Escape closes, focus comes back               */
/* ------------------------------------------------------------------------- */

export function ConfirmDialog({
	open,
	title,
	body,
	confirmWord,
	confirmLabel,
	onConfirm,
	onClose,
}: {
	open: boolean
	title: string
	body: string
	confirmWord: string
	confirmLabel: string
	onConfirm: () => void
	onClose: () => void
}) {
	const ref = useRef<HTMLDialogElement>(null)
	const id = useId()
	const [typed, setTyped] = useState("")

	useEffect(() => {
		const dialog = ref.current
		if (!dialog) return
		if (open && !dialog.open) {
			/* showModal gives the focus trap, the backdrop and Escape for free.
			   A div with a fixed position gives none of them. */
			dialog.showModal()
			setTyped("")
		}
		if (!open && dialog.open) dialog.close()
	}, [open])

	const ready = typed.trim() === confirmWord

	return (
		<dialog
			className="a-dialog"
			ref={ref}
			aria-labelledby={`${id}-title`}
			/* Fires for Escape too, so the parent state never drifts from the DOM */
			onClose={onClose}
			onCancel={onClose}
		>
			<h2 id={`${id}-title`}>{title}</h2>
			<p>{body}</p>

			<div className="a-row">
				<label htmlFor={`${id}-word`}>Type {confirmWord} to confirm</label>
				<input
					className="a-field"
					id={`${id}-word`}
					name="confirm"
					type="text"
					value={typed}
					onChange={(event) => setTyped(event.target.value)}
					autoComplete="off"
					spellCheck={false}
				/>
			</div>

			<div className="a-dialog-actions">
				<button className="a-btn a-btn-line" type="button" onClick={onClose}>
					Keep it
				</button>
				<button
					className="a-btn a-btn-danger"
					type="button"
					aria-disabled={!ready}
					onClick={() => {
						if (ready) onConfirm()
					}}
				>
					{confirmLabel}
				</button>
			</div>
		</dialog>
	)
}

/* ------------------------------------------------------------------------- */
/* 7. Toasts: heard, not just seen                                          */
/* ------------------------------------------------------------------------- */

export type Toast = { id: number; text: string }

export function useToasts(ttl = 6000) {
	const [toasts, setToasts] = useState<Toast[]>([])
	const seq = useRef(0)
	const timers = useRef<number[]>([])

	useEffect(
		() => () => {
			for (const timer of timers.current) window.clearTimeout(timer)
		},
		[],
	)

	const push = useCallback(
		(text: string) => {
			/* A counter, not Math.random: the same input gives the same key, so
			   server and client markup match. */
			seq.current += 1
			const id = seq.current
			setToasts((list) => [...list, { id, text }])
			const timer = window.setTimeout(() => {
				setToasts((list) => list.filter((toast) => toast.id !== id))
			}, ttl)
			timers.current.push(timer)
		},
		[ttl],
	)

	const dismiss = useCallback((id: number) => {
		setToasts((list) => list.filter((toast) => toast.id !== id))
	}, [])

	return { toasts, push, dismiss }
}

export function ToastRegion({
	toasts,
	onDismiss,
}: {
	toasts: Toast[]
	onDismiss: (id: number) => void
}) {
	return (
		/* The region exists before the first toast, or the announcement is lost */
		<div role="status" aria-live="polite">
			{toasts.map((toast) => (
				<div className="a-toast" key={toast.id}>
					<span>{toast.text}</span>
					<button
						className="a-btn a-btn-icon"
						type="button"
						aria-label="Dismiss"
						onClick={() => onDismiss(toast.id)}
					>
						<svg
							width="16"
							height="16"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							strokeWidth="1.5"
							aria-hidden="true"
						>
							<path d="M6 6l12 12M18 6 6 18" />
						</svg>
					</button>
				</div>
			))}
		</div>
	)
}

/* ------------------------------------------------------------------------- */
/* Putting it together                                                       */
/* ------------------------------------------------------------------------- */

export function ReleasesScreen({ notes }: { notes: Note[] }) {
	const [tab, setTab] = useUrlState("state", "published")
	const [sort, setSort] = useUrlState("sort", "recent")
	const [confirming, setConfirming] = useState(false)
	const { toasts, push, dismiss } = useToasts()

	const visible = useMemo(
		() => notes.filter((note) => (tab === "published" ? note.state === "published" : note.state !== "published")),
		[notes, tab],
	)

	return (
		<div className="a-main">
			<div className="a-bar">
				<Tabs
					label="Release state"
					value={tab}
					onChange={setTab}
					tabs={[
						{ id: "published", label: "Published" },
						{ id: "open", label: "Waiting on approval" },
					]}
				/>
				<button className="a-btn a-btn-danger" type="button" onClick={() => setConfirming(true)}>
					Delete changelog
				</button>
			</div>

			{visible.length > 0 ? (
				<NotesTable
					notes={visible}
					sort={sort === "readers" ? "readers" : "recent"}
					onSortChange={setSort}
				/>
			) : (
				<EmptyState
					title="No notes are waiting on you"
					body="Drafts appear here the moment a pull request merges into a tracked branch."
					action={
						<a className="a-btn a-btn-line" href="/repositories">
							Track another repository
						</a>
					}
				/>
			)}

			<ConfirmDialog
				open={confirming}
				title="Delete this changelog?"
				body="Published notes stay reachable at their old links for 30 days, then go."
				confirmWord="kvartal"
				confirmLabel="Delete changelog"
				onClose={() => setConfirming(false)}
				onConfirm={() => {
					setConfirming(false)
					push("Changelog deleted. Links redirect for 30 days.")
				}}
			/>

			<ToastRegion toasts={toasts} onDismiss={dismiss} />
		</div>
	)
}
