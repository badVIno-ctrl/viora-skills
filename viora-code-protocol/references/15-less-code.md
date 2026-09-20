# 15 - Less code

The cheapest line is the one you do not write. The second cheapest is the one you delete.
This reference is about **volume**, not correctness: nothing here says a finding is a bug.

```bash
python3 scripts/less.py .            # ranked cut list, biggest first
python3 scripts/less.py . --top 10
```

## What counts as a cut

| Tag | Shape | Fix line |
|---|---|---|
| `delete:` | nothing reads it - orphan config, dead export, unused file | delete it, run the gates |
| `stdlib:` | the standard library already does this | swap the import, drop the dependency |
| `native:` | the runtime already does this (fetch, Intl, crypto.randomUUID) | use the platform, drop the dependency |
| `yagni:` | one caller, one implementation | inline it; name it again when there are two |
| `shrink:` | a wrapper that only forwards | call the inner function directly |

## The dependency question, asked once

Before adding a package: what does it do that the platform does not, and is that worth a
lockfile entry, an audit surface and an upgrade every quarter? `lodash` → destructuring
and `Array.prototype`. `moment` → `Intl.DateTimeFormat`. `axios` → `fetch`. `uuid` →
`crypto.randomUUID()`. `pytz` → `zoneinfo`. `six` → nothing, Python 2 is gone. `attrs` →
`dataclasses`. `requests` for a single call → `urllib.request`.

## Lazy on purpose, and honest about it

Ship the smallest version that satisfies the contract, then question the rest **in the
same reply**: "Did X; Y covers it. Need full X? Say so." A deliberate simplification with
a known ceiling carries a marker on the line above it:

```python
# viora:ceiling in-memory only, single process; move to Redis when a second worker exists
_cache = {}
```

`scope` counts those markers and `report` lists them under FOLLOW-UPS, so a shortcut is
visible to the next reader instead of being rediscovered as a bug.

## Where laziness is forbidden

Validation at trust boundaries. Error handling that prevents data loss. Security controls.
Accessibility basics. Anything the user explicitly asked for. In those five places the
small version is not lazy, it is wrong. → `references/14-rationalizations.md`

## Order of operations

1. Find the owner (step 2). Extending beats adding.
2. Ask what the platform already does.
3. Write the smallest thing that passes RED.
4. Step 7 CLEAN: run `less.py`, delete what it names, rerun the gates.
5. Mark every deliberate ceiling. Report them.
