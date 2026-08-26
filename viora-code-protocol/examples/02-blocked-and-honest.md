# Example 2 - the run that stops, asks, fails twice, and reports BLOCKED

**This is the example most models need.** Every model can produce a happy path. The thing
that makes an agent worth trusting is what it does when the task is vague and the fix does
not work.

Two lessons here:

1. **Stopping to ask is a success state, not a failure.** One batched round of questions
   costs the user 60 seconds. A wrong guess costs them an afternoon.
2. **BLOCKED is a valid verdict.** A precise BLOCKED report is worth more than a
   "DELIVERED" that quietly does not work.

**Situation.** The user writes: *"the dashboard is slow, add caching"*. Nothing else.

---

## Turn 0 - open the run, then refuse to guess

```bash
$ python3 scripts/viora.py tier --set T0
tier pinned: T0  (.viora/tier)

$ python3 scripts/viora.py start --mode FEATURE --task "dashboard is slow, add caching"
VIORA T0 | MODE FEATURE | STEP 1/10 CONTRACT
budget: <= 80 changed lines, <= 1 file(s), 2 doubt round(s), 2 strike(s) then BLOCKED
```

Step 1 is CONTRACT, and a contract needs a DONE-TEST. There is no DONE-TEST here. "Slow"
is not a number, "caching" is not a location, and "the dashboard" is three pages in this
repo. So the correct first action is 20 minutes of reading, then **one** batched round of
questions - not a guess, and not four separate questions across four turns.

What the reading produced:

```bash
$ python3 scripts/viora.py --root . ; python3 scripts/scan_repo.py . --top 6
src/pages/Dashboard.tsx           412 lines   HOTSPOT (over 400-line limit)
src/api/metrics.ts                188 lines
src/api/client.ts                 156 lines
src/hooks/useMetrics.ts            74 lines
...

$ grep -rn "fetch(" src/pages/Dashboard.tsx | wc -l
7

$ grep -rn "cache\|memo\|swr\|react-query" src --include="*.ts*" -l
src/api/client.ts
src/hooks/useMetrics.ts

$ grep -n "cache" src/api/client.ts
41:// TODO: respect Cache-Control here

$ grep -n "useMemo\|useQuery" src/hooks/useMetrics.ts
12:  const value = useMemo(() => transform(raw), [raw]);

$ cat package.json | grep -A6 '"dependencies"'
"dependencies": {
  "react": "18.3.1",
  "react-dom": "18.3.1",
  "@tanstack/react-query": "5.51.1",
```

**Reply to the user:**

> VIORA T0 | MODE FEATURE | STEP 1/10 CONTRACT
>
> **BLOCKED ON: 3 open decisions.** I read the code first so these are real questions, not
> a questionnaire.
>
> What I found: `Dashboard.tsx` makes **7 separate fetch calls** on mount, and
> `@tanstack/react-query` is already a dependency but is not used on this page.
> There is also a `// TODO: respect Cache-Control` at `src/api/client.ts:41`.
> So "add caching" could mean at least three different changes with very different risk.
>
> **Q1. Which slowness are we fixing?** First paint on a cold load, or the delay when you
> switch tabs and come back?
> -> *my recommendation:* tab-return, because that is where the 7 refetches hurt and where
> caching is nearly free.
>
> **Q2. Where should the cache live?** Client-side query cache (react-query, already
> installed, ~30 lines, no infrastructure), or HTTP `Cache-Control` at `client.ts:41` (affects
> every consumer of the API, needs backend agreement)?
> -> *my recommendation:* react-query. Rung 4 on the ladder - the dependency is already there.
>
> **Q3. What counts as done?** I need a number I can measure. Something like
> "returning to the dashboard within 60s makes 0 network requests" is testable.
> "Feels faster" is not, and I will not report it as proven.
> -> *my recommendation:* the 0-requests version, asserted in a test.
>
> **WHAT I DID ANYWAY:** nothing was edited. I only read files and recorded the findings below.
>
> **DEFAULT IF YOU DO NOT REPLY:** I take Q1 = tab-return, Q2 = react-query on
> `useMetrics` only, Q3 = the 0-requests test, and I keep it under 80 lines in one file.
>
> Separately, and out of scope: `Dashboard.tsx` is 412 lines, over this protocol's 400-line
> limit. Not touching it now, recorded as a follow-up.

```bash
$ python3 scripts/viora.py ledger add --severity FYI --where src/pages/Dashboard.tsx:1 \
    --text "412 lines, over the 400 limit; 7 fetch calls on mount"
F1 FYI @ src/pages/Dashboard.tsx:1: 412 lines, over the 400 limit; 7 fetch calls on mount

$ python3 scripts/viora.py ledger add --severity FYI --where src/api/client.ts:41 \
    --text "TODO: respect Cache-Control - unresolved, relevant to any HTTP caching decision"
F2 FYI @ src/api/client.ts:41: TODO: respect Cache-Control - unresolved
```

Note the shape of the questions: **each one has a recommendation attached.** The user can
reply "yes to all three" in four seconds. That is what makes asking cheap enough to be
worth doing.

---

## Turn 1 - the user answers, the contract closes

> User: *"yes to all three, go"*

```bash
$ python3 scripts/viora.py contract \
    --goal "returning to the dashboard within 60s issues 0 network requests for metrics" \
    --done-test "npm test -- useMetrics.test.tsx  (asserts fetch call count is 0 on remount)" \
    --protected "the cold-load path; the shape of useMetrics() return value" \
    --non-goals "HTTP Cache-Control, splitting Dashboard.tsx, the other 6 fetches"
written: .viora/contract.md

$ python3 scripts/viora.py done 1 --note "contract agreed with user after 3 questions; 0-requests-on-remount is the DONE-TEST"
VIORA T0 | MODE FEATURE | STEP 2/10 OWNER
```

---

## Turns 2-5 - owner, ladder, plan, red (condensed)

```bash
$ python3 scripts/viora.py done 2 --note "Owner: src/hooks/useMetrics.ts:12 - the only place metrics are fetched for this page"
$ python3 scripts/viora.py done 3 --note "rung 4: @tanstack/react-query is already installed; rungs 2-3 fail, no local cache exists"
$ python3 scripts/viora.py plan --files src/hooks/useMetrics.ts --lines 60 --frozen "useMetrics() return shape"
PLAN recorded
FILES:  src/hooks/useMetrics.ts
BUDGET: <= 60 changed lines
FROZEN: useMetrics() return shape
$ python3 scripts/viora.py done 4 --note "FILE: src/hooks/useMetrics.ts only; <=60 lines"

$ npm test -- useMetrics.test.tsx
 FAIL  test/useMetrics.test.tsx
  x remount within 60s makes no network request
    expected fetch to be called 0 times, was called 1 time

$ python3 scripts/viora.py evidence --gate red --command "npm test -- useMetrics.test.tsx" --result "FAIL as expected: fetch called 1 time on remount"
$ python3 scripts/viora.py done 5 --note "RED: remount test fails, fetch called 1 time"
VIORA T0 | MODE FEATURE | STEP 6/10 GREEN
```

---

## Turn 6 - strike 1

```bash
$ python3 scripts/viora.py checkpoint --label "before GREEN attempt 1"
checkpoint 20260826-091203 saved - before GREEN attempt 1
```

> HYPOTHESIS: wrapping the fetch in `useQuery` with `staleTime: 60_000` makes the remount
> read from cache.
> TEST: `npm test -- useMetrics.test.tsx`

```bash
$ npm test -- useMetrics.test.tsx
 FAIL  test/useMetrics.test.tsx
  x remount within 60s makes no network request
    expected fetch to be called 0 times, was called 1 time
```

> RESULT: **still 1 call.** Hypothesis dead. Not "almost working" - dead.

```bash
$ python3 scripts/viora.py strike --reason "useQuery + staleTime 60s: fetch still called once on remount"
STRIKE 1/2 - useQuery + staleTime 60s: fetch still called once on remount
One strike left at T0. Change hypothesis, not volume.
Write the next HYPOTHESIS / TEST / RESULT before you touch code again.
```

---

## Turn 7 - strike 2, and the cap

> HYPOTHESIS: the test renders a fresh `QueryClientProvider` per mount, so the cache is
> thrown away between mounts. Hoisting the client to module scope in the test should fix it.
> TEST: same command.

```bash
$ npm test -- useMetrics.test.tsx
 FAIL  test/useMetrics.test.tsx
  x remount within 60s makes no network request
    expected fetch to be called 0 times, was called 1 time

$ grep -rn "QueryClientProvider" src
src/main.tsx:18:  <QueryClientProvider client={new QueryClient()}>
```

> RESULT: still 1 call, and I now see something worse: `src/main.tsx:18` constructs
> `new QueryClient()` **inside the JSX**, so a new client is created on every app render.
> That is almost certainly the real cause - and `src/main.tsx` is **not in my PLAN** and not
> in my contract.

```bash
$ python3 scripts/viora.py strike --reason "hoisting the test QueryClient: no change; found new QueryClient() inline at src/main.tsx:18"
STRIKE 2/2 - hoisting the test QueryClient: no change

STRIKE LIMIT REACHED at T0.
Stop editing. Report BLOCKED with what you tried and what you learned.
Stopping here is a success state: two dead hypotheses recorded honestly are more useful
than a third guess shipped as a fix.

$ python3 scripts/viora.py rollback --yes
rolled back to state at checkpoint 20260826-091203

Now change hypothesis, not volume. Write HYPOTHESIS / TEST / RESULT before the next edit.

$ python3 scripts/viora.py ledger add --severity Critical --where src/main.tsx:18 \
    --text "new QueryClient() constructed inline in JSX - the cache is discarded on every app render; defeats any react-query caching"
F3 Critical @ src/main.tsx:18: new QueryClient() constructed inline in JSX
```

The rollback matters. Without it, the BLOCKED report would be handed over on top of a
working tree full of two failed attempts, and the next session would inherit the mess.

---

## Turn 8 - the BLOCKED report

```bash
$ python3 scripts/viora.py report
VIORA T0 | MODE FEATURE | STEP 6/10 GREEN

VERDICT: BLOCKED
MODE: FEATURE | TIER: T0 | TASK: dashboard is slow, add caching

CONTRACT
- GOAL: returning to the dashboard within 60s issues 0 network requests for metrics
- DONE-TEST: npm test -- useMetrics.test.tsx
- PROTECTED: the cold-load path; the shape of useMetrics() return value

WHAT CHANGED
- 0 file(s) - the working tree was rolled back to the pre-GREEN checkpoint

EVIDENCE
| Gate | Command | Result | Fresh |
|---|---|---|---|
| red | `npm test -- useMetrics.test.tsx` | FAIL as expected: fetch called 1 time | yes |

NOT DONE / UNPROVEN
- step 6 GREEN was never completed
- step 7 CLEAN was never completed
- step 8 PROVE was never completed
- step 9 DOUBT was never completed
- F3 Critical @ src/main.tsx:18 is still OPEN: new QueryClient() constructed inline in JSX
- 2 failed attempt(s) recorded; the root cause may be wider than the fix

FOLLOW-UPS
- F1 FYI @ src/pages/Dashboard.tsx:1: 412 lines, over the 400 limit; 7 fetch calls on mount
- F2 FYI @ src/api/client.ts:41: TODO: respect Cache-Control - unresolved
```

**Reply to the user:**

> VIORA T0 | MODE FEATURE | BLOCKED
>
> I did not deliver this, and I rolled the working tree back to where it started.
>
> **BLOCKED ON:** the cache cannot work inside my declared scope.
> `src/main.tsx:18` builds `new QueryClient()` inline in JSX, so React discards the cache on
> every app render. No amount of `staleTime` in `useMetrics.ts` can survive that.
>
> **ATTEMPTS**
> 1. `useQuery` + `staleTime: 60_000` in `useMetrics.ts` -> remount still fetched once.
> 2. Hoisted the test's `QueryClient` out of the render -> no change; that is when I found
>    the real cause at `main.tsx:18`.
>
> **Q1.** May I change `src/main.tsx:18` to a module-scope `QueryClient`? It is a 2-line
> change, but it is outside the file I agreed to touch and it affects the whole app.
> -> *my recommendation:* yes, and I re-run the full gate set afterwards.
>
> **DEFAULT IF YOU DO NOT REPLY:** I do nothing further. The tree is clean, F3 is recorded.
>
> One honest note: my first hypothesis was wrong and my second was wrong. The 60-second
> conversation in the first turn saved more time than either attempt did.

---

## What to copy from this

1. **Read before you ask.** Three questions grounded in `Dashboard.tsx:7 fetches` and
   `client.ts:41` are worth answering. "What do you mean by caching?" is not.
2. **Batch the questions, attach recommendations, give a default.** One round, three
   questions, four-second reply.
3. **A dead hypothesis is dead.** "Still 1 call" is not partial progress.
4. **Count strikes out loud.** The second strike is what turned flailing into a finding.
5. **Roll back before reporting BLOCKED.** Never hand over a tree full of failed attempts.
6. **Do not silently widen the scope.** `main.tsx` was the fix. Asking took one turn;
   touching it without asking would have broken the contract and hidden the real problem.
7. **The report says 0 files changed.** That is an honest, useful, reusable result.
