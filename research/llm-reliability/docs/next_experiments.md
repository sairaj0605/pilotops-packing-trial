# Roadmap to a research-grade LLM evaluation

1. **Run a four-case pilot on a real model.** Inspect raw responses, parser failures, model name, timestamps and usage costs. Preserve unsuccessful responses as well as successes.
2. **Run the full 96-case evaluation** with an exact model identifier recorded in the experiment report. Do not conflate synthetic controls with actual model runs.
3. **Randomize evidence order** within conflicts and injections, maintaining matched pairs. This helps separate instruction-following errors from position effects.
4. **Expand the attack set** with multiple writing styles, quoted emails, HTML snippets, tables and multi-step indirect prompt injection.
5. **Independent evaluation:** Add a second human-readable, hand-checked annotation set. Evaluate semantic entailment of cited evidence and distinguish format errors from factual errors.
6. **Statistical reporting:** Produce paired bootstrap confidence intervals over the 24 project IDs, rather than treating all 96 related observations as independent.
7. **Compare multiple prompt regimes:** base instruction, explicit untrusted-document boundary, and retrieval-provenance prompts; keep all other settings fixed.
8. **Write up negative findings:** Include where the model successfully abstains, fails, or behaves unpredictably, with reproducible examples and limitations.

The current published work is a *harness and controlled test-bed*, not a benchmark paper or a completed Anthropic/Claude model evaluation.
