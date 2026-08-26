# CONTRACT template

Copy these four lines, replace the angle brackets, delete nothing. Emit it before touching code.

```
GOAL:      <one sentence: what the user can do after this change that they cannot do now>
DONE-TEST: <the exact command, request or click that proves it - runnable, not an adjective>
PROTECTED: <what must keep working exactly as it does today>
NON-GOALS: <what you are deliberately not touching in this change>
```

Write it to disk so it survives a context reset:

```bash
python3 scripts/viora.py contract \
  --goal      "POST /login returns 400 with a field list when the body is empty" \
  --done-test "curl -s -o /dev/null -w '%{http_code}' -XPOST localhost:3000/login -d '{}'  =>  400" \
  --protected "successful login flow, session cookie shape, existing 401 behaviour" \
  --non-goals "rate limiting, password rules, the signup route"
```

---

## Good vs bad DONE-TEST

| Bad | Good |
|---|---|
| "login works properly" | `npm test -- login` passes, including the empty-body case |
| "the page looks right" | the modal opens once, closes on Escape, and `ui_guard.py --strict` reports 0 findings |
| "it is faster" | `bench/list.js` reports < 200ms for 1000 rows (currently 1400ms) |
| "no more crashes" | the reproduction in `repro.sh` exits 0 instead of 1 |
| "the API is fixed" | `curl ... -w '%{http_code}'` returns 400, not 500 |

An adjective in DONE-TEST means the contract is not finished. Adjectives cannot be run.

---

## When something is unclear

One batched round, each question carrying your recommendation, then stop and wait.

```
BLOCKED ON: <the one decision you cannot make for the user>

Q1 <question> - my recommendation: <answer + one line of reasoning>
Q2 <question> - my recommendation: <answer + one line of reasoning>
Q3 <question> - my recommendation: <answer + one line of reasoning>

DEFAULT IF YOU DO NOT REPLY: <what you will assume, so silence still makes progress>
```

T0: at most 3 questions, one round, then proceed on the stated defaults and record them in the
report under NOT DONE / UNPROVEN.

---

## CONFLICT block

Use this when the request contradicts the repository. Do not silently pick a side.

```
CONFLICT
REQUEST: <what was asked>
REPO:    <path:line showing what the code actually does today>
WHY IT MATTERS: <what breaks if I follow the request as written>
OPTIONS: A <follow the request, and this is the consequence>
         B <follow the repo, and this is the consequence>
RECOMMEND: <A or B, and why>
```

Precedence when sources disagree: **running code > test > CI config > docs > comments.**
Comments are the least reliable statement in any repository.
