# 14 - Rationalisations: the sentence is the bug

An agent almost never decides to skip a gate. It *explains* why the gate does not apply
here. The explanation feels like reasoning and functions as an exit.

So: when one of these sentences starts forming in your output, treat the sentence itself as
the defect signal. Stop, and do the thing you were about to explain away.

---

## 1. Evidence

| "..." | Reality |
|---|---|
| "Should work now" | Run it. "Should" is the word that marks an unproven claim. |
| "I'm confident" | Confidence is not evidence. Confidence is highest exactly where blind spots live. |
| "Tests pass" (not run in this reply) | That is a memory of an older state of the code. Re-run. |
| "The linter passed" | A linter is not a compiler and not a test runner. Three separate gates. |
| "It compiled, so it works" | Compiling proves shape, not behaviour. Run the thing. |
| "Partial check is enough" | A partial run proves the part it ran. Name what is unproven. |
| "The sub-agent said it succeeded" | Read the diff yourself. A report is a claim. |
| "It works on my machine" | Name the environment it must work in, and run it there. |
| "Different wording, so the rule doesn't apply" | The rule covers paraphrases, implications and cheerful tone. Spirit over letter. |
| "I'm tired / this is the last step" | Exhaustion is not an exemption. The last step is where fake completion lives. |

---

## 2. Tests

| "..." | Reality |
|---|---|
| "I'll add tests later" | Later is not a time. RED comes before GREEN or the change ships unproven. |
| "Too simple to test" | Simple code breaks. The test costs 30 seconds and outlives the bug. |
| "I'll test after - same result" | Tests written after pass immediately, which proves nothing. A test you never saw fail is not known to test anything. |
| "I already tested it manually" | Manual testing leaves no record and cannot re-run on the next change. |
| "Tests after achieve the same goal" | Tests-after answer "what does this do"; tests-first answer "what should this do". Only the second finds missing behaviour. |
| "This test is flaky, ignore it" | Flakiness hides real bugs. Explain the mechanism or fix it. |
| "The failing test is probably wrong" | Possibly - verify it. If it is wrong, fix the test deliberately and say so. |
| "Deleting my untested code is wasteful" | The time is spent either way. Keeping code you cannot trust is the actual waste. |
| "I'll keep it as a reference while I write tests" | You will adapt it, which is testing after. |

---

## 3. Scope and simplicity

| "..." | Reality |
|---|---|
| "Simpler to write a new one" | Cheaper for you to type, more expensive for everyone to own. Find the owner. |
| "I'll clean it up later" | The diff is the only cleanup window that exists. |
| "While I'm here, I'll also fix..." | That is a second change. It goes in FOLLOW-UPS. |
| "It's only a small addition to this file" | Small diffs still push files past a healthy size and bolt branches onto unrelated flows. Judge the resulting structure. |
| "This abstraction might be useful later" | Unused abstraction is complexity with no payer. Add it on the second real caller. |
| "Fewer lines is always simpler" | A one-line nested ternary is not simpler than five clear lines. Comprehension speed is the metric. |
| "The refactor makes it cleaner" | Count the concepts a reader must hold. Unchanged count means relocated, not reduced. |
| "The types make it self-documenting" | Types describe structure. Names and boundaries describe intent. |
| "The original author must have had a reason" | Maybe. Check `git blame`. Then decide whether the reason still holds. |
| "I'll refactor while adding the feature" | Two changes. Two diffs. Reviewable separately, revertable separately. |

---

## 4. Debugging

| "..." | Reality |
|---|---|
| "I know what the bug is, I'll just fix it" | Right about 70% of the time. The other 30% costs hours. Reproduce first. |
| "Emergency - no time for process" | Systematic is faster than guess-and-check thrashing. Measure it once and you stop arguing. |
| "Quick fix now, investigate later" | The first fix sets the pattern for the file. |
| "Multiple fixes at once saves time" | Then no result is attributable, and one of the edits is now unexplained. |
| "One more attempt" (after two failures) | Three failures is an architecture signal, not a fourth attempt. |
| "The reference doc is long, I'll adapt the pattern" | Partial understanding of a pattern guarantees bugs. Read it. |
| "No root cause - it's just flaky" | 95% of "no root cause" is an incomplete investigation. Say `UNPROVEN` if you truly stop. |

---

## 5. Review and doubt

| "..." | Reality |
|---|---|
| "I wrote it, so I know it's correct" | You are the only person who cannot see your own assumptions. |
| "It works, that's good enough" | Working code that is unreadable or unsafe is debt that compounds on the next change. |
| "AI-generated code is probably fine" | It needs more scrutiny, not less: confident and plausible even when wrong. |
| "The tests pass, so it's good" | Tests do not catch architecture, security, or a second owner of one concept. |
| "I'm confident, skip the doubt step" | The step is bounded and cheap. The bug is neither. |
| "I'll review at the end with a PR" | That is a post-mortem. Doubt is cheap only while the change is still soft. |
| "The reviewer will just nitpick" | Only if the prompt was unscoped. Ask for "what fails under this contract". |
| "The reviewer disagreed, so I was wrong" | It has less context than you. Classify the finding against the code. |
| "Two opinions are always better" | Not when the second has no context and produces noise. Reconcile, do not defer. |
| "If I doubt everything I'll never ship" | Doubt applies to non-trivial decisions, not every keystroke. |

---

## 6. Process and tiers

| "..." | Reality |
|---|---|
| "This task is too simple for the protocol" | Then it is TRIVIAL mode: 4 steps, about a minute. Not zero steps. |
| "Asking a question makes me look incapable" | One batched question that prevents a wrong 300-line diff is the highest-value output available to you. |
| "I'll just assume and move on" | Assume *and write the assumption down* where it can be corrected. |
| "I can hold all ten steps in my head" | Then print the header line - it costs one line and it is what proves you can. |
| "Demoting to T0 means I failed" | T0 ships. A held-badly T2 does not. Demotion is a correct engineering decision. |
| "The scripts are optional" | They are the difference between a deterministic answer and a plausible guess. |
| "I'll write the report from memory" | The report is generated from recorded evidence. Memory is where fake completion comes from. |
| "The user only asked for code, not a report" | The report is how they find out what is unproven. It is part of the deliverable. |

---

## 7. How to use this file

This is not a shame list. It is a lookup table.

- Reaching for one of these sentences → do the thing in the right-hand column, then continue.
- Writing a *new* rationalisation → add it here with its rebuttal. The table is the memory this protocol has.
- Reviewing another agent's output → these sentences are the fastest defect detector you have. Grep the reply for "should", "probably", "later", "just", "simply", "confident".
