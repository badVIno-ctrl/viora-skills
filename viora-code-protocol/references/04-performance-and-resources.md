# 04 - Performance, weight and resources

Read for slowness, jank, memory growth, battery drain, large lists, animations, or any PERF-mode task.

**Core rule: the cheapest optimization is deleting work. Measure, change one thing, measure again, report both numbers.**

---

## 1. Budgets (default targets; the repo's own targets win)

| Dimension | Budget |
|---|---|
| Response to a user input | visible feedback < 100 ms |
| Animation frame | <= 16 ms of work per frame (60 fps); no layout in the loop |
| Blocking main-thread task | < 50 ms; split longer work |
| List rendering | virtualize above ~100 rows; never render 1000 nodes to show 20 |
| Data transferred per view | as small as the repo's existing views; never ship a full table to render a count |
| Server/API response | keep the existing p95; no new N+1 query patterns |
| Memory | flat after 10 open/close cycles of the same surface |
| Idle CPU | ~0; no polling loop or animation running on an idle screen |
| Bundle / dependency size | no new large dependency without a stated reason |

A change that quietly breaks one of these is a defect even if the feature works.

## 2. Known-heavy patterns - prevent, do not "optimize later"

| Pattern | Why it hurts | Do instead |
|---|---|---|
| Heavy computation inside render/draw | runs on every update | compute once, cache by input, or move out of the render path |
| New object/array/function identity in a hot path | invalidates memoization, re-renders children | hoist stable values; pass primitives |
| Unthrottled `scroll`/`resize`/`input`/`mousemove` handlers | dozens of runs per second | throttle/debounce; use passive listeners; prefer observers |
| Read-then-write layout in a loop (offsetHeight then style) | forced synchronous reflow each iteration | batch reads, then batch writes |
| Animating `width`/`top`/`left`/`box-shadow` | layout + paint each frame | animate `transform` / `opacity` |
| Query in a loop (N+1) | 1 + N round trips | one batched query / join / `IN` clause |
| Fetch on every keystroke | floods the network | debounce + cancel the previous request |
| Polling on a timer | constant wakeups, battery | events, subscriptions, or long polling with backoff |
| Unbounded cache / growing array / never-cleared map | memory grows until it dies | bound the size, evict, or scope to the lifetime |
| Whole dataset in memory/state | huge payloads, slow diffs | page it, select only needed fields |
| Synchronous file/JSON work on the main thread | freezes the UI | async, streamed, or off-thread |
| Unsized / unoptimized images and fonts | layout shift, slow paint | explicit dimensions, correct format and size, lazy below the fold |
| Logging inside hot loops | I/O per iteration | log once with a summary |
| `await` in a loop for independent work | serial latency | run in parallel and gather |
| Re-parsing / re-compiling the same input | wasted CPU | parse once at the boundary |

## 3. Order of attack (cheapest first)

1. **Delete the work.** Is it needed at all? Is it computed twice? Is a whole component re-rendering for nothing?
2. **Defer it.** Lazy load, load on interaction, load below the fold, split the bundle.
3. **Do it once.** Memoize with a bounded key, cache with an eviction rule, hoist constants.
4. **Do it in bulk.** Batch requests, batch DOM writes, batch state updates.
5. **Do it faster.** Better algorithm or data structure - only after the four above.
6. **Move it.** Worker, background job, server, build step.

Never start at step 5 or 6. Micro-optimizing code that should not run is wasted effort.

## 4. Measure or do not claim

PERF work without numbers is not PERF work.

```
Baseline:  <command / interaction>  ->  <metric>   (e.g. 1420 ms, 480 MB, 62 queries)
Change:    <one specific change>
Result:    <same command>           ->  <metric>   (e.g. 210 ms, 190 MB, 3 queries)
```

Rules: same input, same environment, more than one run, and report the command so it can be repeated. If you cannot measure here, mark it `UNPROVEN` and state the measurement a human should run. Never present a guess as an improvement, and never claim a percentage you did not compute.

## 5. Resource lifecycle

Every acquisition is paired with a release in the same unit: listeners, timers, animation frames, observers, subscriptions, sockets, file handles, DB connections, workers, object URLs, in-flight requests.

Leak test procedure:
1. Note the baseline (memory, listener count, open handles, timers).
2. Exercise the feature 10 times (open/close, navigate away and back).
3. Compare to baseline. Growth that never returns is a leak - fix it before reporting done.

Server-side equivalents: connections returned to the pool, streams closed, temporary files removed, background tasks cancelled on shutdown, no unbounded queues.

## 6. Device-friendliness (mobile, low-end, battery)

- No animation or timer running while the surface is hidden or backgrounded; pause on `visibilitychange`/background events.
- Respect reduced-motion preferences; heavy blur/shadow/backdrop effects are expensive on low-end GPUs.
- Cap concurrent requests; retry with backoff, not in a tight loop.
- Keep the interactive path light: it is better to show real content in 300 ms than a skeleton for 3 s.
- Assume half the CPU and a third of the memory of your dev machine.

## 7. Performance exit checklist

```
[ ] no new work added to a render/draw/hot path
[ ] every listener, timer, observer, subscription has its teardown
[ ] no N+1 queries, no request per keystroke, no unbounded cache
[ ] large lists virtualized or paged
[ ] budgets in section 1 still met (or the deviation stated)
[ ] for PERF mode: before/after numbers with the exact command
```
