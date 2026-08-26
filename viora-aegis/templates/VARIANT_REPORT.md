# Variant analysis - {{ROOT_CAUSE_SHORT}}

**Date:** {{DATE}}
**Seed finding:** <!-- the CONFIRMED bug this started from: RULE-ID, file:line -->
**Scope searched:** <!-- directories, languages, and what you deliberately excluded -->

---

## Root cause

<!-- State the CAUSE, not the symptom.

     Symptom (wrong): "SQL injection in getUser()"
     Root cause (right): "query strings are built by f-string concatenation
     throughout db/, because there is no parameterised helper and nothing makes
     the safe path the easy one."

     The root cause tells you what to search for. The symptom does not. -->

**Why it happened here:** <!-- missing helper? optional safe API? copied pattern?
     unclear ownership? This determines whether the class fix is a code change or
     an API change. -->

---

## Result in one line

> **One root cause, {{N}} confirmed sites, {{M}} rejected.**

Not "{{N}} findings". Reporting N independent findings implies N independent
fixes, when a single class fix closes all of them.

---

## Search passes

Generalise **one element at a time** and record the noise level after each pass.
Stop the moment more than half the hits are noise - that means you generalised
past the *habit* and are now matching the *language*.

| Pass | What was generalised | Query / pattern | Hits | Confirmed | Noise | Kept going? |
|---|---|---|---|---|---|---|
| 0 | exact known instance | | | | | yes |
| 1 | same function, other call sites | | | | | |
| 2 | same sink, other verbs | | | | | |
| 3 | same pattern, other string-building forms | | | | | |
| 4 | same mistake, other sinks | | | | | |
| 5 | same mistake, other languages | | | | | |

**Stopped at pass {{P}} because:** <!-- noise exceeded half the hits / scope
     exhausted / budget. Say which - the next reviewer needs to know whether the
     search was completed or truncated. -->

---

## Confirmed variants

Each row was read at its line and passed the three-question gate independently.
A hit that matches the pattern is not automatically a bug - the input may be a
constant here, or already validated there.

| # | Where | Reachable from | Q1 input controlled | Q2 reaches sink | Q3 impact | Severity |
|---|---|---|---|---|---|---|
| 1 | `file:line` | | yes | yes | | |
| 2 | | | | | | |

---

## Rejected hits

Why each one is *not* a variant. This section is what makes the analysis
trustworthy - a variant report with no rejections usually means nothing was
verified.

| Where | Matched because | Not a variant because |
|---|---|---|
| | | |

---

## Patterns that found nothing

Record these. They tell the next reviewer which shapes are already clean, so the
same ground is not searched twice.

| Pattern | Intent | Result |
|---|---|---|
| | | 0 hits |

---

## The inverse check

> **Where the codebase does it correctly, is the correct way actually available
> everywhere?**

- **Safe pattern found at:** <!-- file:line -->
- **Call sites using it:** {{X}} of {{Y}}
- **Conclusion:** <!-- If a safe helper exists but only 3 of 20 call sites use it,
     the real finding is that the safe path is OPTIONAL. Fixing 17 call sites
     without fixing that leaves the 21st to be written wrong. -->

---

## Class fix

**The fix:** <!-- the single change that closes all confirmed sites -->

**Make the safe path the only path:**
<!-- e.g. remove the raw-query export, make the unsafe helper private, add a
     required parameter, or fail the build on the old signature. A convention is
     not a control. -->

**Order of work:**

1. <!-- highest-exploitability site first -->
2.
3.

**Migration risk:** <!-- what could break, who is affected -->

---

## The rule left behind

A variant analysis that does not leave a rule will be repeated in six months.

**Added to `rules/patterns.json`:**

```json
{
  "id": "{{RULE-ID}}",
  "title": "{{title}}",
  "category": "{{CATEGORY}}",
  "severity": "{{severity}}",
  "pattern": "{{regex}}",
  "note": "{{why this shape is dangerous here}}",
  "fix": "{{the safe form}}"
}
```

**Both fixtures are mandatory:**

```
# ruleid: {{RULE-ID}}
<a line that MUST match>

# ok: {{RULE-ID}}
<a line that must NOT match>
```

The negative fixture is the more valuable of the two. A rule with no negative
test becomes a noise generator, a noisy rule gets disabled, and a disabled rule
protects nothing.

- [ ] Positive fixture matches
- [ ] Negative fixture does not match
- [ ] Rule runs clean on the rest of the repo (no new false positives)

---

## Not searched

<!-- Directories, languages, generated code, vendored code, or binaries excluded
     from the search - and why. An absent measurement is never a clean verdict. -->

---

*Produced with Viora Aegis (`plan variants`). Every confirmed variant above was
read at its line and verified independently.*
