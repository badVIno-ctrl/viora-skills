# 01 - Recon and anti-duplication

Read before creating any file, component, class, helper, constant, config key or dependency.

**Core rule: one concept, one owner. Two implementations of one behaviour is a defect even when both work.**

Generated code rots mainly because the agent cannot see what already exists, so it writes a second version. The second version drifts from the first, the two fight, and the product gets heavier and less predictable. Recon is the cheapest phase in this protocol and it prevents the most expensive damage.

---

## 0. The minimum, by tier

This whole file collapses to one output: **an owner line**.

```
Owner: src/lib/format.ts:14        <- extend this
Owner: NONE                        <- you may create one, and you say which searches you ran
```

| Tier | What recon looks like |
|---|---|
| **T0** | run `scan_repo.py`, run one `grep` for the main word, paste the output, copy one line out of it as the owner line. Nothing more. |
| **T1** | 3 name variants + 2 behaviour keywords + `find_duplicates.py` over the target area. Read the top hit before deciding. |
| **T2** | full ownership map below: behaviour owner, data owner, surface owner, plus existing constants/styles/routes that already encode the concept. |

At T0, do these as **separate turns**: search, then read the output, then write the owner line. Batching them is how a small model ends up writing a second implementation while claiming it searched.

---

## 1. Orient (2 minutes, always)

1. Read the repository's own instructions if present: any `AGENTS.md`, `CONTRIBUTING.md`, `CONVENTIONS.md`, style docs, or rules file at the root or in the folder you are editing. Repository rules outrank your defaults.
2. Get the map: `python3 scripts/scan_repo.py .`
   - note the stack, the **commands the repo defines** (use those exact commands later), entrypoints, and files already over 400 lines.
3. Note the folder conventions: where components live, where utilities live, where tests live, how files are named. Match them. Do not import a foreign structure into an existing repo.

## 2. Find the owner before you write (mandatory)

For every concept in the task ("date formatting", "modal", "retry", "user settings store"), search with **three name variants plus two behaviour keywords**:

```bash
# name variants (camel, kebab, snake, plural, abbreviation)
grep -rn --include=* -i "formatdate\|format_date\|format-date\|datetimeformat" .
# behaviour keywords - catches differently named implementations
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

**"I searched" is a claim.** Like every other claim in this protocol, it needs pasted output behind it.

## 3. The Solution Ladder - always climb from the bottom

Pick the **lowest rung that fully solves the contract**, and state the rung in your report.

| Rung | Option | Use when |
|---|---|---|
| 0 | **NO CHANGE** | the behaviour already exists, or the request is based on a wrong assumption. Report `NO_CHANGE` with proof. |
| 1 | **DELETE or CONFIGURE** | the defect is caused by extra code, a wrong flag, or a config value. Deleting code is the best patch. |
| 2 | **REUSE LOCAL** | a function/component/module in this repo already does it, or does 90% of it - extend it in place. |
| 3 | **PLATFORM / STDLIB** | the language or runtime already provides it (`Intl`, `URL`, `structuredClone`, `pathlib`, `dataclasses`, native CSS). |
| 4 | **INSTALLED DEPENDENCY** | a dependency already in the manifest covers it. Check the manifest before writing an algorithm. |
| 5 | **NEW DEPENDENCY** | only with the user's explicit yes, plus license sanity, maintenance signal, size cost, and a note in the report. |
| 6 | **MINIMAL CUSTOM CODE** | nothing above fits. Write the smallest correct implementation, in the place the repo's conventions dictate. |

State it in one line: `Rung 2 because rung 1 fails: there is no flag for this.`

Anti-patterns that skip the ladder: "cleaner to start fresh", "the old one is confusing", "I'll write my own tiny version", "a wrapper makes it nicer". A confusing owner gets improved, not cloned.

## 4. Duplication taxonomy - what to look for

| Kind | Signature | Fix |
|---|---|---|
| Exact clone | copy-pasted block in 2+ places | extract into the existing owner, not a new "utils2" |
| Semantic clone | two names, same behaviour (`getUser` / `fetchUserData`) | keep the better-tested one, migrate callers, delete the other |
| Parallel structures | `Dialog`, `Modal`, `Popup` doing one job | one component with props; delete the rest |
| Second source of truth | the same value stored in two places (state + prop + URL) | one owner, others derive |
| Duplicated closed set | status strings, roles, event names, error codes, routes, layer/z-index values, config keys defined in several files | one exported constant/enum, everyone imports it |
| Copy with drift | "almost the same" logic where one copy got a bug fix | consolidate immediately; drift is how bugs come back |
| Duplicate config | the same setting in env, config file and code default | one owner + documented precedence |

## 5. Consolidation procedure (when you find duplicates)

1. Choose the canonical owner: most callers, best tested, best located, least coupled.
2. Diff the copies. Every behaviour difference is either a bug or a real requirement - decide explicitly and record it.
3. Move the missing capability into the canonical owner (guarded by a test if the repo has tests).
4. Migrate all callers. `grep` for the old names until zero references remain.
5. **Delete** the duplicate. Not comment it out. Not rename it `_old`.
6. Run the gates. Report what you deleted.

If consolidation is out of scope for the current task, do **not** silently add a third copy: reuse one copy, and report the duplication as a follow-up with exact paths.

## 6. Before you delete: Chesterton's Fence

Code that looks pointless sometimes is not. Before removing a check, a branch, a retry, a timeout, a sleep, or a defensive default:

```bash
git --no-pager log -S'<the removed text>' --oneline -- <path>
git --no-pager blame -L <start>,<end> <path>
```

A commit message mentioning `fix`, `security`, `CVE`, `race`, `overflow`, `hotfix` or a ticket id means that line is a **scar from a real incident**. Leave it, or replace its protection explicitly and say so. When you cannot find out why it exists and it is not in your way, leave it and note it - one unexplained line costs less than a re-introduced outage.

## 7. Dependencies

Before adding one: is it in the manifest already? Does the platform do it? Is it 10 lines of local code? Is it maintained (recent releases, open issues answered)? What does it cost in size and transitive deps? Is the licence compatible?

A new dependency needs the user's explicit yes at every tier. Never add one to solve a problem you have not yet reproduced, and never bump an unrelated version "while you are there" - version bumps are their own change, with their own verification.

## 8. Recon exit checklist

```
[ ] repository instruction files read (or confirmed absent)
[ ] scan_repo run; repo's own commands noted
[ ] owner line written for every concept in the task, backed by pasted search output
[ ] find_duplicates run over the target area (T1/T2); existing duplicates noted
[ ] ladder rung chosen, with one line on why the cheaper rung fails
[ ] no new file/component/constant that duplicates an existing owner
[ ] anything I will delete or replace is listed, and blamed if it looks defensive
```
