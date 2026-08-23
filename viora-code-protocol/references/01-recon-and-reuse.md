# 01 - Recon and anti-duplication

Read before creating any file, component, class, helper, constant, config key or dependency.

**Core rule: one concept, one owner. Two implementations of one behavior is a defect even when both work.**

Generated code rots mainly because the agent cannot see what already exists, so it writes a second version. The second version drifts from the first, the two fight, and the product gets heavier and less predictable. Recon is the cheapest phase in this protocol and it prevents the most expensive damage.

---

## 1. Orient (2 minutes, always)

1. Read the repository's own instructions if present: any `AGENTS.md`, `CONTRIBUTING.md`, `CONVENTIONS.md`, style docs, or rules file at the root or in the folder you are editing. Repository rules outrank your defaults.
2. Get the map: `python3 scripts/scan_repo.py .`
   - note the stack, the **commands the repo defines** (use those exact commands later), entrypoints, and files already over 400 lines.
3. Note the folder conventions: where components live, where utilities live, where tests live, how files are named. Match them. Do not import a foreign structure into an existing repo.

## 2. Find the owner before you write (mandatory)

For every concept in the task ("date formatting", "modal", "retry", "user settings store"), search with **three name variants plus two behavior keywords**:

```bash
# name variants (camel, kebab, snake, plural, abbreviation)
grep -rn --include=* -i "formatdate\|format_date\|format-date\|datetimeformat" .
# behavior keywords - catches differently named implementations
grep -rn -i "toLocaleDateString\|strftime\|dayjs\|moment(" .
# declarations of the thing you were about to create
grep -rn -E "(function|class|const|def|type|interface) +Modal" .
```

Then run the duplication scanner over the area you will touch:

```bash
python3 scripts/find_duplicates.py . --top 15
```

Write the result as an **ownership map** and keep it visible while you work:

```
Date formatting     -> src/lib/format.ts:14        (canonical, 23 callers)
Modal shell         -> src/ui/Modal.tsx:1          (canonical)
Modal (second copy) -> src/features/billing/Dialog.tsx:1   <- DUPLICATE, consolidate
User settings state -> src/stores/settings.ts:8
Status values       -> src/constants/status.ts:3   (closed set - single source of truth)
```

If you cannot find an owner after a real search, then and only then may a new owner be created - and you say in the report which searches you ran.

## 3. The Solution Ladder - always climb from the bottom

Pick the **lowest rung that fully solves the contract**, and state the rung in your report.

| Rung | Option | Use when |
|---|---|---|
| 0 | **NO CHANGE** | the behavior already exists, or the request is based on a wrong assumption. Report `NO_CHANGE` with proof. |
| 1 | **DELETE or CONFIGURE** | the defect is caused by extra code, a wrong flag, or a config value. Deleting code is the best patch. |
| 2 | **REUSE LOCAL** | a function/component/module in this repo already does it, or does 90% of it - extend it in place. |
| 3 | **PLATFORM / STDLIB** | the language or runtime already provides it (`Intl`, `URL`, `structuredClone`, `pathlib`, `dataclasses`, native CSS). |
| 4 | **INSTALLED DEPENDENCY** | a dependency already in the manifest covers it. Check the manifest before writing an algorithm. |
| 5 | **NEW DEPENDENCY** | only with a stated reason, license sanity, maintenance signal, size cost, and a note in the report. |
| 6 | **MINIMAL CUSTOM CODE** | nothing above fits. Write the smallest correct implementation, in the place the repo's conventions dictate. |

Anti-patterns that skip the ladder: "cleaner to start fresh", "the old one is confusing", "I'll write my own tiny version", "a wrapper makes it nicer". A confusing owner gets improved, not cloned.

## 4. Duplication taxonomy - what to look for

| Kind | Signature | Fix |
|---|---|---|
| Exact clone | copy-pasted block in 2+ places | extract into the existing owner, not a new "utils2" |
| Semantic clone | two names, same behavior (`getUser` / `fetchUserData`) | keep the better-tested one, migrate callers, delete the other |
| Parallel structures | `Dialog`, `Modal`, `Popup` doing one job | one component with props; delete the rest |
| Second source of truth | the same value stored in two places (state + prop + URL) | one owner, others derive |
| Duplicated closed set | status strings, roles, event names, error codes, routes, layer/z-index values, config keys defined in several files | one exported constant/enum, everyone imports it |
| Copy with drift | "almost the same" logic where one copy got a bug fix | consolidate immediately; drift is how bugs come back |
| Duplicate config | the same setting in env, config file and code default | one owner + documented precedence |

## 5. Consolidation procedure (when you find duplicates)

1. Choose the canonical owner: most callers, best tested, best located, least coupled.
2. Diff the copies. Every behavior difference is either a bug or a real requirement - decide explicitly and record it.
3. Move the missing capability into the canonical owner (guarded by a test if the repo has tests).
4. Migrate all callers. `grep` for the old names until zero references remain.
5. **Delete** the duplicate. Not comment it out. Not rename it `_old`.
6. Run the gates. Report what you deleted.

If consolidation is out of scope for the current task, do **not** silently add a third copy: reuse one copy, and report the duplication as a follow-up with exact paths.

## 6. Dependencies

Before adding one: is it in the manifest already? Does the platform do it? Is it 10 lines of local code? Is it maintained? What does it cost in size and transitive deps? If you still add it, name it in the report with the reason.

Never add a dependency to solve a problem you have not yet reproduced.

## 7. Recon exit checklist

```
[ ] repository instruction files read (or confirmed absent)
[ ] scan_repo run; repo's own commands noted
[ ] ownership map written for every concept in the task
[ ] find_duplicates run over the target area; existing duplicates noted
[ ] ladder rung chosen and justified
[ ] no new file/component/constant that duplicates an existing owner
[ ] anything I will delete or replace is listed
```
