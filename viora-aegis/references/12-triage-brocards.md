# 12 - Triage: the maxims that stop false positives

A scanner hit is a **lead**. A finding is a claim you are willing to defend. The
distance between them is triage, and it is the single highest-value step in the
whole workflow - because a report full of unverified leads gets ignored
wholesale, taking the one real bug with it.

This reference backs `plan triage` and `playbooks/04-triage-verify.md`.

---

## The maxims

Short rules, meant to be quoted. Say the number when you invoke one.

> **M1. A regex hit is a lead, not a finding.** (Law 1)
>
> **M2. Restate the claim in one sentence before you investigate.**
> Roughly half of all false positives collapse at this step, because the claim
> turns out to be unstateable.
>
> **M3. No line read, no finding.** Not the snippet the tool printed - the file.
>
> **M4. Name the attacker, or drop it.** "An attacker" is not an actor. Say who,
> and what they control.
>
> **M5. An absence of proof is `UNDETERMINED`, never `FALSE POSITIVE`.**
> Those are different verdicts and reporting one as the other is how real bugs
> get closed.
>
> **M6. Group by root cause, not by file.** Twenty call sites of one bad helper
> is one finding.
>
> **M7. Severity is exploitability, not scariness.** Local-only is not
> automatically low: a local-network-only path can still be high.
>
> **M8. If you cannot write the fix, you do not understand the bug yet.**
>
> **M9. Defence-in-depth is a real verdict.** Report it as such and mark it low.
> Do not inflate it into a vulnerability, and do not silently drop it.
>
> **M10. Your own tooling is subject to Law 1.** A noisy detector is a bug in the
> detector.

---

## Step 0: restate the claim

Before any investigation, write one sentence in this exact shape:

> *An actor who controls **X** can cause **Y** by reaching **Z**.*

Worked example:

> An unauthenticated HTTP caller who controls the `filename` query parameter can
> read arbitrary files on the host by reaching `open(path)` at
> `api/files.py:88`.

If you cannot fill in all three slots, you do not yet have a finding. That is not
a failure - it is the cheapest possible outcome, reached in thirty seconds
instead of thirty minutes.

---

## The three questions

Every lead must answer all three. Any "no" is a rejection; any "unknown" that you
cannot resolve is `UNDETERMINED`.

| # | Question | What counts as an answer |
|---|---|---|
| **Q1** | Is the data actually attacker-controlled? | The entry point, by name and file:line |
| **Q2** | Does it reach the dangerous sink unsanitised? | Each hop, with file:line. Name every guard you passed and why it does not stop this |
| **Q3** | What happens if it does? | A concrete consequence: which data, whose account, which host |

---

## The six gates

Apply in order. Each gate is a place a lead legitimately dies.

| Gate | Test | Fails when |
|---|---|---|
| **G1 Reachability** | Is this code on a live path? | Dead code, unregistered route, disabled feature, an example in docs, a test fixture |
| **G2 Control** | Does an actor genuinely control the value? | It is a constant, an enum, config the attacker cannot set, or a server-generated id |
| **G3 Path** | Does the value arrive intact? | A validator, parameterised query, allowlist, encoder or type coercion sits in between |
| **G4 Effect** | Is the outcome security-relevant? | It crashes a worker with no impact; it exposes data the actor already had |
| **G5 Precondition** | What is already required? | It needs admin rights the attacker would only have post-compromise - drop the severity, keep the finding |
| **G6 Novelty** | Is it already reported or already mitigated? | Duplicate, a known accepted risk, a documented suppression with a reason |

Record which gate rejected each lead. That list is what makes your report
auditable, and it stops the next reviewer from redoing your work.

---

## Rationalisations to refuse

Each of these is a sentence people use to close a real bug. Each has a
counter-question you must answer with evidence, not reasoning.

| Excuse | Counter-question |
|---|---|
| "It is internal only" | Who can reach the internal network? Name the boundary and the control that enforces it |
| "The framework escapes it" | Which function, on which sink, for which context? Show the call |
| "That input is validated upstream" | Where? Is that the *only* caller? What happens on the direct path |
| "It is only reachable by an admin" | Is the admin check on *this* route? Is it authorisation or just authentication (Law 3) |
| "It has been like that for years" | Irrelevant to exploitability. Age is not a control |
| "It is just a dev or test path" | Is it shipped? Is it reachable in production? Is the flag default-on (Law 4) |
| "Nobody would send that" | Attackers are not users |
| "A WAF blocks it" | Show the rule. Then explain what happens when it is bypassed |
| "It needs a specific version" | Which versions are deployed? Check the lockfile |
| "It is not our code" | It is your dependency and your users |

---

## Batch triage

With more than about fifteen leads, do not triage them one at a time.

1. **Cluster by root cause.** All hits that trace to the same helper, the same
   missing middleware, or the same unsafe default form one cluster.
2. **Verify the cluster once**, at the root. Establish the shape of the bug.
3. **Then confirm each site cheaply** against that shape: same sink, same lack of
   guard, reachable.
4. **Report one finding per root cause**, listing confirmed sites, and say how
   many candidates you rejected.
5. **Escalate the cluster's severity** if the sites compose - a single class of
   bug in ten reachable places is worse than one instance.

This is also how you avoid the most common credibility failure: a fifty-item
report that is really four bugs and forty-six echoes.

---

## Exploit chains

Two findings that are individually low can be critical together. Look for these
shapes explicitly, because no scanner will:

- Information leak plus a guessable identifier - IDOR at scale
- Open redirect plus an OAuth flow - token theft
- Weak reset flow plus user enumeration - account takeover
- Path traversal for reading plus a writable config - remote code execution
- Prompt injection plus a credentialed tool - the agent becomes the attacker

When you report a chain, give the severity to the chain and cross-reference the
links. Do not report a critical chain as two separate lows.

---

## Output of triage

```
Triage summary
  Leads examined:   N
  Confirmed:        N   (report these)
  Likely:           N   (report, state the residual doubt)
  Defence-in-depth: N   (report as low)
  Undetermined:     N   (report with what would settle it)
  Rejected:         N   (list with the gate that rejected each)
```

The rejected list is not padding. It is the evidence that the confirmed list
means something.

---

## Attribution

The structure of this reference - restate-the-claim as step zero, mandatory
verification gates, an explicit table of rationalisations, batch triage by root
cause, and the requirement to write up rejected leads - follows the
false-positive-checking and vulnerability-triage methodology published by
[Trail of Bits](https://github.com/trailofbits/skills), which is licensed
CC-BY-SA-4.0. **No text has been copied**: the methodology is restated here in
our own words and adapted to this pack's verdict scale, so that Viora Aegis can
remain MIT-licensed. The confidence discipline in Q3 and the
"exploitability, not scariness" rule also reflect the reporting standard used by
[Anthropic's claude-code-security-review](https://github.com/anthropics/claude-code-security-review).
