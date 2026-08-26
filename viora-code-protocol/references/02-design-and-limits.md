# 02 - Design, limits, simplification and surgical implementation

Read when planning files and interfaces, when a limit is being exceeded, and while writing the change.

**Core rule: decide the structure before writing lines. Structure decided while typing becomes sprawl.**

---

## 0. Size the change before planning it

A change that is too large cannot be reviewed, cannot be reverted cleanly, and cannot be proven.

| Changed lines | Meaning |
|---|---|
| ~100 | the target. Reviewable in one pass, revertable in one command. |
| ~300 | the ceiling at T1/T2. Needs a stated reason. |
| 1000+ | split it. Not "try to split it" - split it. |
| T0 ceiling | 80 lines, 1 file. |

Generated code makes 1000-line diffs easy to produce and impossible to verify. Volume is not progress.

**How to split, in order of preference:**

| Strategy | Use when |
|---|---|
| **Stack** | the parts depend on each other: refactor first, then the feature on top. Each part ships and passes on its own. |
| **File group** | independent areas move together: split by module, not by arbitrary line count. |
| **Horizontal** | a shared layer is needed by several callers: land the layer with its tests, then the callers. |
| **Vertical slice** | end-to-end but narrow: one route, one field, one state - working through every layer. Best default for features. |

Each split part must be independently reviewable and independently revertable. "Part 2 of 4, does not compile alone" is not a split, it is a suspended change.

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

At **T0** the plan is three lines and one file:

```
FILE:   src/api/login.ts
BUDGET: <= 80 changed lines
FROZEN: LoginResponse, POST /login
```

Needing a second file at T0 is a signal to stop and ask, not to quietly grow the plan.

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

Wrong ways to satisfy a limit: splitting one coherent function across three files; renaming a long function into two functions that must always be called together; hiding complexity behind a wrapper that adds no meaning. If a limit genuinely fights clarity, exceed it deliberately and say why in the report - a stated trade-off is acceptable, a silent one is not.

## 5. Simplification: five principles

Step 7 CLEAN runs these. Behaviour must not change while you do.

**1. Delete before you add.** The best simplification is removal: unused branches, dead options, unreachable defaults, wrappers that only rename, comments restating the code. Ask what breaks if this goes away - nothing means it should.

**2. Reduce concepts, not lines.** Count what a reader must hold in their head to follow the function. A one-line nested ternary has fewer lines and more concepts than five clear lines, so it is not simpler. **Moving complexity into a new file with a nice name is relocation, not reduction** - the reader still meets it.

**3. Flatten control flow.** Guard clauses over nesting; early return over an `else` tail; a lookup table over a branch ladder; one loop over three passes. Depth is what makes code unreadable, not length.

**4. Make the data shape do the work.** Most branch ladders are a missing type or a missing table. A map from key to handler, a discriminated union, a normalised record - each deletes whole families of `if`. Prefer explicit arguments and return values over globals, singletons, module state and implicit context.

**5. Name it so the comment becomes unnecessary.** `if (u.a && !u.b && u.c > 0)` becomes `if (canRenewSubscription(user))`. Comments explain **why**, never what the line already says.

### Over-simplification is a real failure

| Trap | Why it is worse |
|---|---|
| removed a check because "that can't happen" | it happens in production, silently |
| collapsed two similar functions with different edge cases | you shipped a bug in the differences |
| replaced explicit code with a clever one-liner | slower to read, harder to debug |
| deleted an error path because nothing tested it | the failure is now invisible |
| inlined something used in five places | five copies to keep in sync |

The test: **would a competent newcomer understand this faster than before?** If not, it is not simpler.

### The rule of 500

About to make the same mechanical edit in more than ~500 places (a rename, an import rewrite, a signature migration)? Do not hand-edit. Write the script, run it on one file, verify, then run it on all - and commit the script. Hand-editing at that scale produces silent misses that no review catches.

## 6. Abstraction discipline

- **Rule of two consumers**: no abstraction, base class, generic helper, plugin system, event bus or config-driven layer until a second real consumer exists. One caller means inline it.
- **Grep test** before adding an option/flag/hook: search for a real call site. If there is none, delete the idea.
- No wrapper that only renames another function. No interface with a single implementation "for testability" when the concrete type is testable.
- Delete instead of parameterising: an unused branch is a maintenance cost with no benefit.

## 7. Clarity rules

- Boring, explicit names. No abbreviations except repository-established ones. Names say what, not how.
- Booleans read as statements: `isVisible`, `hasAccess`, `shouldRetry`. No negative names (`notReady`).
- Functions do one thing; the name matches all of it. If the name needs "and", split it.
- Error handling is explicit: never swallow an error, never catch what you do not understand, never log-and-continue on a corrupted state. If a failure is expected, handle it and say what the user sees.
- No `console.log`/`print` debugging left behind. No commented-out code. No `TODO` without a concrete note in the report.
- Keep formatting to the repo's formatter; never reformat untouched lines (it hides the real diff).

## 8. Structural remedies - name the move, not the mood

When something is "too complex", the useful output is a named restructuring:

| Symptom | Remedy |
|---|---|
| long conditional chain on a type field | typed dispatch: map key -> handler |
| two branches that differ in one value | one path, that value as a parameter |
| orchestration mixed with logic | pure function for the logic, thin caller for the wiring |
| feature logic inside a shared module | move it to the feature; keep shared code generic |
| a class that is one function | make it a function |
| a wrapper with no behaviour | delete it, call through |
| deep prop/parameter drilling | pass the shaped object, or move the consumer |
| repeated fetch-transform-render | one hook/helper, three call sites |
| a file over 400 lines | split at the responsibility seam, not the midpoint |

## 9. Surgical change rules

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
- **One change, one purpose.** A refactor and a feature in one diff means neither can be reviewed or reverted.

## 10. Design exit checklist

```
[ ] change sized: <= 80 lines (T0) or <= 300 with a reason (T1/T2); larger => split plan written
[ ] file plan written; every new file justified
[ ] interfaces (consumes/produces) fixed before implementation
[ ] limits respected, or deliberate exceptions stated
[ ] no abstraction without a second consumer
[ ] simplification reduced concepts, not just lines
[ ] superseded code deleted, not commented
[ ] every new unit wired and reachable
[ ] diff contains nothing outside the plan
```
