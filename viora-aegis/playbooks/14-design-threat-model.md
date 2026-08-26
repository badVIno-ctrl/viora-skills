# Playbook 14 - DESIGN (threat-model something that does not exist yet)

**Goal:** find the security problems before the code is written, when fixing them
costs a conversation instead of a migration.

```bash
python3 scripts/viora.py plan design
```

---

## The rule

> **You have no code to read, so you have no evidence. Produce requirements and
> questions, never verdicts and never severities.**

A threat model that reports "high severity SQL injection" in a feature that does
not exist is fiction. Write testable requirements instead, and the reviewer of
the eventual pull request can check them one by one.

---

## Steps

1. **Restate the feature in one paragraph:** what it does, who uses it, what data
   it touches, what it can change.

   *ELSE if you cannot fill that in:* **ask the user.** Do not guess. Half of bad
   threat models are careful answers to the wrong question.

2. **List the actors** - including the ones people forget:

   | Actor | The question they represent |
   |---|---|
   | Anonymous visitor | What is reachable with no credentials at all? |
   | Authenticated user | What is the worst thing a *legitimate* user can do deliberately? |
   | **Another tenant** | The most commonly missed actor in any SaaS design |
   | Admin / support | Who can read this in a support tool or a log? |
   | Internal service | Is service-to-service traffic authenticated, or trusted by network position? |
   | Third-party integration | What happens when it is slow, down, or lying? |
   | Compromised dependency | It runs with your process's full privilege |
   | Malicious insider | What is logged, and can the log be edited? |
   | **The model itself** | If an LLM is involved, it is an untrusted actor (Law 1) |

3. **List the assets worth attacking.** Not "the database" - the specific things:
   credentials, session tokens, API keys, PII, payment data, private content,
   compute, the ability to send mail from your domain, the ability to write to the
   repository, the ability to trigger a deploy.

4. **Draw the trust boundaries.** Every line where data changes owner needs
   validation on the *receiving* side: internet -> app, app -> database,
   app -> third party, tenant -> tenant, user -> admin, CI -> production.

5. **Walk the checklist per boundary and produce a REQUIREMENT for each row.**

   | Question | Law | The requirement it produces |
   |---|---|---|
   | Who is allowed to do this? | 3 | Authorisation is checked on the *object*, not just the session |
   | How is identity established? | 3 | Name the mechanism and where it runs |
   | What happens when the check fails or errors? | 4 | Deny on throw, timeout and null |
   | What are the limits? | 9 | An explicit bound on size, rate, count, spend, time |
   | What is logged? | 10 | The security story, with no secret or PII in it |
   | Where do secrets live? | 5 | A secret manager, injected at runtime, never in the repo |
   | What is the blast radius if this is compromised? | 8 | The narrowest credential that still works |
   | What isolates one tenant from another? | 3 | A named mechanism, enforced in one place |

6. **Ask the abuse questions.** These find the design flaws that checklists miss,
   because they are about *sequence* and *quantity* rather than about a single
   call:

   - What is the worst thing an authenticated user could do here on purpose?
   - What if they replay this request? What if they send it twice concurrently?
   - What if they enumerate the IDs?
   - What if step 1 succeeds and step 2 fails - is the state safe, or is money
     moved but not recorded?
   - What if the third party is slow, down, or returns a hostile response?
   - What if the input is 1000x larger than expected?
   - Who can see this in logs, error reports, analytics or a support tool?
   - What happens at the end - deletion, export, account closure, offboarding?

7. **If an LLM or an agent is in the design, add these.** They are not optional
   extras; they are where the new failures are:

   - Where does untrusted text enter the prompt? (user input, retrieved
     documents, tool results, web pages, other users' content, file uploads)
   - **Assume injection succeeds.** What is the damage ceiling? That number is
     the design, because prompt injection is not reliably preventable.
   - What tools can it call - an allowlist, or a wildcard?
   - Is its output used in a decision, a query, a command, a path, or rendered
     HTML? Each of those is a sink (Law 1 and Law 2).
   - Is there a human confirmation before anything irreversible or externally
     visible?
   - What bounds the cost - tokens, calls, loop iterations, spend?
   - Can one user's data reach another's context through memory, a cache, or a
     shared vector store?

8. **Write every requirement as a TESTABLE statement.** Not "handle auth
   properly" but: *"a request for an object the caller does not own returns 404,
   and no field of that object appears in the response body."* The first cannot
   be reviewed; the second can be turned into a test by whoever builds it.

9. **Name the TOP THREE risks** and what would have to be true for each to be
   safe. Three is deliberate. A list of twenty gets skimmed and then ignored, and
   you will have spent your credibility on the wrong items.

---

## Hard stops

- **No verdicts, no severities, no CVE names on hypothetical code.**
- **Do not design the whole system.** You are adding security requirements to
  someone else's design, not replacing it.
- **Do not accept "we will add auth later."** Record it as an explicit accepted
  risk with an owner, or it becomes permanent.
- **Do not accept a prompt as a permission boundary.** "The system prompt tells
  it not to" is not a control.

---

## Output

Use `templates/THREAT_MODEL.md`. Structure:

```
Feature
  <one paragraph>

Actors
  <list, including another tenant and - if applicable - the model>

Assets
  <specific things worth stealing or abusing>

Trust boundaries
  <boundary> -> <what must be validated on the receiving side>

Security requirements (testable)
  R1 <statement>
  R2 <statement>
  ...

Top three risks
  1. <risk> - safe only if <condition>
  2. ...
  3. ...

Open questions for the team
  Q1 <the fact you could not determine and who can answer it>
```

---

**Related:** `references/01-threat-model.md`,
`references/04-ai-agent-security.md`, `references/05-secure-patterns.md`,
`templates/THREAT_MODEL.md`.
