# 08 - Stack-specific traps

Read the section that matches what you are touching. These are the failures that generated code produces most often per stack, on top of the universal rules.

---

## 1. Typed frontend (TypeScript / component frameworks)

- No `any`, no `as unknown as`, no `@ts-ignore` to silence a real mismatch. Model the type or fix the shape.
- Effects: correct dependencies and a cleanup return. An effect without cleanup that subscribes, times, or listens is a leak.
- Derived state is computed, never stored twice. If a value can be derived from props/store, do not copy it into local state - that is how two truths appear on screen.
- Stable list keys (never the array index for reorderable lists).
- One state owner per concern. Local state, global store, URL and server cache must not each hold their own copy of the same fact.
- Do not manipulate the DOM by hand next to a framework that owns it; use refs and the framework's lifecycle.
- One styling approach per repo. Do not introduce a second system beside the existing one.
- Guard module-level side effects: they run again on hot reload and on the server.
- Keep the render path pure: no fetching, no mutation, no `Date.now()`-driven branching that changes every frame.

## 2. Node / backend services

- Validate and normalize input at the boundary; never trust the client, and never spread unvalidated input into a query or object.
- Errors: typed, logged with context, never swallowed; the response says what the caller should do. No stack traces to users.
- Every outbound call gets a timeout; retries use backoff and a cap; retries are only for idempotent operations.
- Wrap multi-step writes in a transaction, or make them idempotent with a key.
- Never block the event loop with sync I/O, big JSON, or crypto in a request handler.
- Paginate every list endpoint. No unbounded `SELECT` feeding a response.
- Secrets come from the environment/secret manager. No keys, tokens or internal hostnames in code or logs. No personal data in logs.
- Graceful shutdown: close servers, drain queues, cancel background tasks.

## 3. Python

- Type hints on public functions; run the repo's type checker if it has one.
- No mutable default arguments (`def f(x=[])`). Use `None` and create inside.
- Resources through context managers (`with`), always. No bare `except:`; catch the specific exception.
- `pathlib` over string paths; no shelling out for what the stdlib does.
- No heavy work or side effects at import time. Keep `if __name__ == "__main__":` thin.
- Dataclasses / typed dicts instead of loose dicts passed between layers.
- Respect the repo's formatter and linter exactly; don't reformat untouched files.

## 4. Databases and data access

- Parameterized queries only. String-built SQL with user input is a defect, always.
- No N+1: batch, join, or prefetch. Check the query count, not just the response time.
- Indexes match the actual query patterns; adding a query pattern means checking the index.
- No `SELECT *` in application code; name the columns you use.
- Migrations are reversible, tested on a copy, and never destructive without explicit approval.
- One owner for the schema truth (migrations), not a second definition drifting in code.

## 5. Mobile / desktop UI

- Every lifecycle-attached resource is released in the paired teardown (listeners, timers, observers, location/sensor subscriptions).
- Lists recycle views; never build all rows at once.
- Nothing heavy on the UI thread: parsing, images, disk, crypto go off-thread.
- Pause animations, timers and polling when the surface goes to background.
- Respect platform back/close semantics; one owner decides what "back" does per screen.
- Assume constrained memory and battery: cache with limits, downscale images to display size.

## 6. Shell and automation scripts

- `set -euo pipefail` at the top; quote every variable (`"$var"`).
- No `rm -rf "$dir"` without validating `$dir`. Destructive commands need a confirmation flag or a dry-run mode.
- Scripts are idempotent: safe to run twice.
- Check that a tool exists before using it; fail with a clear message.
- No secrets in arguments (they land in process lists and history).

## 7. Security minimums (every stack)

```
[ ] input validated at the boundary, output encoded for its destination (HTML/SQL/shell/URL)
[ ] authorization checked on the server for every action, not hidden in the UI
[ ] secrets from environment/secret store; nothing committed
[ ] no eval/exec/dynamic import of user-controlled content
[ ] dependencies pinned; no unvetted new dependency
[ ] errors and logs leak neither secrets nor personal data
[ ] defaults are safe: least privilege, deny by default, expiring tokens
```
