# Playbook 04 - TRIAGE and verify

**Goal:** decide whether a claimed finding is real. Your job here is to **try to
refute it**. A finding that survives a genuine attempt at refutation is worth
reporting; one that was never challenged is noise.

```bash
python3 scripts/viora.py plan triage
```

---

## Step 0 - restate the claim in your own words

Do this first, for every finding, before any analysis. In one sentence:

> "This claims that **`<attacker>`** can supply **`<input>`** at **`<entry
> point>`**, which reaches **`<sink>`** at **`<file:line>`**, resulting in
> **`<impact>`**."

If you cannot fill every blank from the report and the code, the claim is
incomplete - say which blank is empty and stop there.

A large share of false positives collapse at this step alone, because the claim
turns out to have no attacker, no path, or no impact. Never skip it.

---

## The three-question gate

```
Q1 Can an attacker control the input?
   -> Name the exact entry point and the parameter.
   -> NO if: constant, internal enum, developer-set config, another trusted service's
      fixed value, or a value already validated by an allowlist upstream.

Q2 Does it reach the dangerous sink?
   -> Write the call path: source -> function -> function -> sink.
   -> NO if: parameterised, escaped at the sink, allowlisted, type-constrained,
      or the path is unreachable.

Q3 What happens if it does?
   -> One sentence of concrete impact. Name what the attacker reads, writes,
      executes or bypasses.
   -> NO if you cannot name a concrete consequence.
```

**Three yes -> CONFIRMED. Any no -> FALSE POSITIVE (say which question failed).
Unresolvable unknown -> UNDETERMINED (say what fact you needed).**

---

## The six refutation gates

Before confirming, answer all six. Each is a genuine attempt to kill the finding.

| Gate | Question | If it fails |
|---|---|---|
| G1 | Is the input genuinely attacker-controlled? | FALSE POSITIVE |
| G2 | Is there validation, an allowlist or parameterisation between source and sink? | FALSE POSITIVE, or DEFENCE-IN-DEPTH if the control is fragile |
| G3 | Is the sink dangerous in **this** API, with **these** arguments? | FALSE POSITIVE |
| G4 | Is the code reachable - not dead, disabled, or test-only? | FALSE POSITIVE (or INFO if it could be enabled) |
| G5 | Does the framework already neutralise it? **Name version and mechanism.** | FALSE POSITIVE if named; unresolved if you cannot name it |
| G6 | Is the impact real, or does it require access the attacker already has? | Downgrade or FALSE POSITIVE |

"The framework probably handles it" is not passing G5. Either name the version
and the mechanism, or the gate is unresolved.

---

## Rationalisations you must reject

These sound like analysis but are excuses. Each one has killed a real bug.

| Excuse | Why it fails |
|---|---|
| "It's internal only." | Internal is a network. SSRF, a compromised pod, or a malicious insider reaches it. |
| "You'd need to be authenticated." | Accounts are cheap. Authenticated RCE is still critical. |
| "The input is validated." | Where? Against what? On **every** path, including the one you are looking at? |
| "Nobody would do that." | Not a control. |
| "It's behind a feature flag." | Flags get flipped. At most a downgrade, never a dismissal. |
| "The framework handles it." | Name the version and mechanism, or it does not. |
| "Only exploitable from the local network." | Still high severity. LAN access is routinely obtained. |
| "It's a test file / PoC / internal tool." | It is in the repo, so it ships and it runs. |
| "It needs a race condition." | Races are winnable, often trivially. |
| "It's just an information leak." | Leaked internals are step one of the chain. |
| "It's a rule definition, not real code." | Correct for scanners **only** - verify by reading the file. |

---

## Batch triage

With many findings, order matters:

1. **Step 0 for all of them first.** Restate every claim before verifying any.
   This exposes duplicates and reveals which claims share a root cause.
2. **Group by root cause.** Twenty hits from one unsafe helper is **one** finding
   with twenty call sites.
3. **Verify each group independently.** Do not let a confirmed finding make you
   generous about the next one.
4. **Then look for chains.** Two mediums that compose into an account takeover
   are a critical. Report chains first.
5. **Report the false positives too**, with the reason. Suppressed knowledge gets
   rediscovered forever.

---

## Output

```
RULE-ID - title
Claim:     <the step-0 restatement>
Q1 input:  yes/no/unknown - <entry point>
Q2 path:   yes/no/unknown - <source -> sink>
Q3 impact: <one sentence>
Gates:     G1 ok  G2 ok  G3 ok  G4 ok  G5 <version+mechanism>  G6 ok
Verdict:   CONFIRMED | LIKELY | DEFENCE-IN-DEPTH | FALSE POSITIVE | UNDETERMINED
Severity:  <impact x reachability>
```

End with the tally: `confirmed=N likely=N defence-in-depth=N false-positive=N
undetermined=N`, and for each undetermined, the fact that would resolve it.
