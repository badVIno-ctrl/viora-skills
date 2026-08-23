# 02 - Design, limits and surgical implementation

Read when planning files and interfaces, when a limit is being exceeded, and while writing the change.

**Core rule: decide the structure before writing lines. Structure decided while typing becomes sprawl.**

---

## 1. File plan (write it before coding)

One line per file, in the order you will touch them:

```
src/features/export/csv.ts       NEW     builds CSV rows from report items   (~90 lines)
src/features/export/index.ts     EDIT    wire the new builder into the existing export menu
src/features/export/menu.tsx     EDIT    add one entry; no other change
tests/export/csv.test.ts         NEW     main path + empty-input boundary
```

Rules:
- **One responsibility per file.** If you cannot state it in one line without "and", split it.
- **Files that change together live together.** Feature-local code stays in the feature folder; shared code moves out only after a second real consumer exists.
- **A new file needs a reason**: either it is a genuinely new responsibility, or the natural owner would exceed 400 lines. Say which.
- Match the repository's naming and folder conventions exactly.
- No "utils.ts", "helpers.py", "misc", "common" dumping grounds. Name files after what they do.

## 2. Freeze the interfaces first

For every unit you add or change, write what it **consumes** and **produces** before implementing. This is what prevents half-wired code and mismatched types across a multi-step change.

```
buildCsv(items: ReportItem[], opts?: { delimiter?: string }) -> string
  consumes: ReportItem (existing type in src/types/report.ts:12)
  produces: CSV text, no trailing newline; throws nothing; empty items -> header only
```

If the interface must change later, update the plan explicitly and check every caller. Never let two steps of your own work assume different shapes.

## 3. Step sizing

Break the work into steps of a few minutes each, each ending in a state that compiles/parses. After each step you can answer: "is the tree still valid?" Never leave a step half-applied while starting the next one. No placeholders, no `pass # implement later`, no fake return values presented as working code.

## 4. Hard limits and how to respect them properly

| Limit | Value | Correct response when exceeded |
|---|---|---|
| File | 400 lines | split along a **responsibility seam**, not at an arbitrary line |
| Function | 50 lines | extract a named helper that describes intent, keep it beside the caller |
| Nesting | 3 levels | guard clauses, early returns, invert conditions |
| Parameters | 4 | one options object/struct with named fields |
| Duplicated block | 8 lines | consolidate into the existing owner |
| Cyclomatic branches per function | ~10 | table/lookup instead of a branch ladder |
| Magic literals | 0 | one named constant with one owner |
| Nested ternaries, chained one-liners | 0 | plain `if` blocks; clarity beats brevity |

Wrong ways to satisfy a limit: splitting one coherent function across three files; renaming a long function into two functions that must always be called together; hiding complexity behind a wrapper that adds no meaning. If a limit genuinely fights clarity, exceed it deliberately and say why in the report - a stated tradeoff is acceptable, a silent one is not.

## 5. Abstraction discipline

- **Rule of two consumers**: no abstraction, base class, generic helper, plugin system, event bus or config-driven layer until a second real consumer exists. One caller means inline it.
- **Grep test** before adding an option/flag/hook: search for a real call site. If there is none, delete the idea.
- No wrapper that only renames another function. No interface with a single implementation "for testability" when the concrete type is testable.
- Prefer explicit data flow (arguments and return values) over hidden coupling (globals, singletons, module state, implicit context).
- Delete instead of parameterizing: an unused branch is a maintenance cost with no benefit.

## 6. Clarity rules

- Boring, explicit names. No abbreviations except repository-established ones. Names say what, not how.
- Booleans read as statements: `isVisible`, `hasAccess`, `shouldRetry`. No negative names (`notReady`).
- Functions do one thing; the name matches all of it. If the name needs "and", split it.
- Error handling is explicit: never swallow an error, never catch what you do not understand, never log-and-continue on a corrupted state. If a failure is expected, handle it and say what the user sees.
- No `console.log`/`print` debugging left behind. No commented-out code. No `TODO` without a concrete note in the report.
- Comments explain **why**, never what the line already says.
- Keep formatting to the repo's formatter; never reformat untouched lines (it hides the real diff).

## 7. Surgical change rules

- Change the existing owner in place. Do not create a parallel path "to be safe".
- **Delete what you supersede**, in the same change. Old code kept "just in case" becomes a second owner tomorrow.
- **Leave no orphan.** Every new unit must be wired the moment it is created:
  ```
  [ ] imported/exported where it is used
  [ ] registered (route, menu, DI container, index barrel, plugin list, config)
  [ ] reachable by a real user action or caller
  [ ] covered by at least one check, or explicitly listed as UNPROVEN
  ```
- No drive-by refactors, renames, dependency bumps or formatting sweeps outside the plan. Record them as follow-ups.
- Do not change a public interface, schema, or on-disk format that was not part of the request. Ask first.
- Migrations, deletions of user data, and destructive commands: never without explicit approval.

## 8. Design exit checklist

```
[ ] file plan written; every new file justified
[ ] interfaces (consumes/produces) fixed before implementation
[ ] limits respected, or deliberate exceptions stated
[ ] no abstraction without a second consumer
[ ] superseded code deleted, not commented
[ ] every new unit wired and reachable
[ ] diff contains nothing outside the plan
```
