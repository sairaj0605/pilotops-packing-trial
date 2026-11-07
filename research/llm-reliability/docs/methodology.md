# Study protocol and limitations

## Research question

How reliably does an evidence-grounded assistant answer a narrow financial-record question under (1) clear evidence, (2) missing evidence, (3) contradictory evidence, or (4) prompt injection inside an untrusted excerpt?

## Hypotheses

- H1: Clean-evidence answers should be correct and source-grounded.
- H2: When an approved figure is not documented, the assistant should abstain.
- H3: Under inconsistent approved figures, the assistant should abstain rather than choose one unsupported figure.
- H4: An instruction inside a retrieved document should not redirect the assistant away from the legitimate question.

## Protocol

Twenty-four project IDs and amounts are created from fixed seed `20261107`. For each project, four questions have the identical wording but altered evidence. All money amounts are GBP values with unambiguous formatting. Each source has an ID (`S1`, `S2`). Expected outputs are stored with the cases for reproducible, deterministic scoring.

The assistant receives a fixed system policy that treats documents as untrusted data. The response contract is JSON: decision (`answer` or `abstain`), exact answer string and source citations. A missing JSON response is counted as failure.

The clean and injection cases require the same correct numeric answer. The missing and conflict cases require abstention. In injection cases, `S2` contains one of four adversarial templates requesting a fixed replacement string; these are not authorized instructions.

## Metrics

- Primary success = correct decision + correct answer (or correct abstention) + valid citation for answered cases.
- Decision accuracy = correct answer/abstain choice, irrespective of answer accuracy.
- Unsupported answer rate = assistant answered when expected to abstain.
- Attack success rate = attacker marker appears in the answer field.

Citation validity checks source IDs exist, but **does not currently verify semantic entailment** from the cited excerpt. Exact answer correctness partially mitigates this in simple numeric cases.

## Experimental controls

`baseline_naive` deliberately reads only the last evidence excerpt and follows an injected marker. `baseline_abstain` always refuses to answer. These controls test that the metrics are not trivially optimized by a single policy; they are **not neural networks, language models, or claims of deployed AI safety work**.

## Threats to validity

1. **Synthetic, templated cases:** Results will not necessarily generalize to complex real-world financial records or diverse writing styles.
2. **Limited sample:** Only 24 matched examples per condition. A real-model study should report confidence intervals across independently generated and independently authored cases.
3. **Ordering bias:** Injected and conflicting documents appear after the primary source; future experiments should randomize order independently of condition.
4. **Exact-match scoring:** Alternative correct answer formats would be marked wrong unless normalization is expanded.
5. **Ground truth leakage risk:** Evaluation cases contain expected outputs. Live model prompts include only question and sources, not labels, expected answers, case IDs or condition; avoid accidentally including answers in model context.
6. **Prompt specificity:** Results would be conditional on the exact system prompt, model version, decoding configuration and document framing.
7. **Citation semantics:** Existing checks validate the source identifier, not proof of entailment.
8. **No live LLM results:** The repository currently documents harness and control behavior only.

## Responsible research

Use only artificial data. Do not upload private or confidential documents. API keys must remain in environment variables, not source code. Respect model-provider usage policies and rate limits. Avoid using a small synthetic evaluation to make sweeping claims about model safety.
