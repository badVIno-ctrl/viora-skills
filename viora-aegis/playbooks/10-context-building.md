# Playbook 10 - CONTEXT (understand before hunting)

**Goal:** be able to describe what this system does, where its data comes from,
and who is allowed to do what - **before** you look for a single bug.

```bash
python3 scripts/viora.py plan context
```

---

## The rule of this mode

> **You are building understanding, not verdicts.**

In this mode you do **not**:

- name vulnerabilities
- suggest fixes
- write proofs of concept
- assign severities

If you notice something alarming, record it as a **plain observation** and move
on: *"The order handler fetches by ID from the request; no owner comparison
appears in this function."* That is a fact. Turning it into a finding is the next
mode's job, and doing it here corrupts your map with premature conclusions.

When the code counts on something and nothing appears to check it, write that
down plainly and keep going.

---

## Steps

1. **Recon.**
   ```bash
   python3 scripts/viora.py doctor
   ```
   Languages, frameworks, package managers, entry files, git state.

2. **What is this thing?** One paragraph, in your own words, from reading code -
   not from the README. The README describes intentions; the code describes
   behaviour.

3. **Map the entry points.** Every path by which data from outside enters. Be
   exhaustive - this list bounds every later audit, and anything missing here is
   invisible for the rest of the work:
   - HTTP routes and their methods
   - GraphQL resolvers, gRPC services
   - CLI arguments, stdin
   - queue and event consumers, webhooks
   - scheduled jobs and their inputs
   - file uploads and imports
   - environment and config files
   - third-party callbacks (OAuth, payments)
   - **LLM output**, if the system consumes any

4. **Map the authorisation model.** Three separate questions - do not collapse
   them, because collapsing them is the mistake that produces Law 3 bugs:
   - Where is **identity established**? (login, token parsing, session)
   - Where is **permission enforced**? Name the files and the mechanism -
     middleware, decorator, per-handler check, database row filter.
   - What are the **roles or tenancy boundaries**? Who must never see whose data?

   Then answer the load-bearing question: **is authorisation enforced in one
   place, or repeated per handler?** If it is repeated, it is going to be missing
   somewhere. That single fact directs the whole audit.

5. **Map the data.** What is stored, where, and which parts are sensitive:
   credentials, tokens, PII, payment data, health data, private content. Note
   where secrets come from - env, file, secret manager, or hardcoded.

6. **Map the trust boundaries.** Draw the lines where data changes owner:
   internet -> app, app -> database, app -> third party, tenant -> tenant, user ->
   admin, CI -> production. Every boundary needs validation on the receiving
   side, and boundaries are where bugs live.

7. **Map the dangerous sinks.** Where does the code execute, query, read, write,
   render or fetch? Locations only - no judgement yet.

8. **Note the framework's built-in protections** and their versions. This is what
   later lets you answer refutation gate G5 without guessing.

9. **Write the map.** Use `templates/THREAT_MODEL.md`. Keep it short enough to
   re-read - one page per area.

10. **Record what you could not determine.** Generated code, an opaque binary, a
    service whose source you do not have. These become "not assessed" in every
    later report.

---

## When to use this mode

- The codebase is unfamiliar and larger than you can read.
- You cannot answer "where is authorisation enforced?" - the single best
  predictor that an audit will produce confident nonsense.
- A previous audit produced many findings and no confirmations. That is the
  signature of pattern-matching without understanding.

CONTEXT is cheap. A wrong audit is expensive, and worse, it is convincing.

---

## Output

```
System:          <one paragraph, from the code>
Entry points:    <list, grouped by kind>
Identity:        <where established, mechanism, files>
Authorisation:   <where enforced, mechanism, files, central or per-handler>
Roles/tenancy:   <the boundaries>
Data stores:     <what, where, sensitivity>
Secrets:         <source of each>
Trust boundaries:<the lines>
Sinks:           <locations by kind>
Framework:       <name, version, protections it provides>
Observations:    <plain facts, no verdicts>
Undetermined:    <what you could not read, and why>
```

Hand this to AUDIT (`02-audit-repo.md`) as its step 2.
