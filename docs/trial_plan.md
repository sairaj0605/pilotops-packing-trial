# Trial plan

This is a fictional pre-analysis plan. Its gates were written before examining the generated results. They are illustrative business rules, not Amazon procedures or externally validated standards.

## Decision and hypothesis

Decide whether to continue a controlled follow-up trial of automated packing, remediate it first, or stop. Hypothesis: automation improves packages per staffed hour by at least 10%, with no material deterioration in quality, uptime or cost per good package.

## Collection design

- Site: fictional Site A. Three paired station groups P1/P2/P3 in each arm.
- Control arm: manual packing throughout.
- Pilot arm: manual packing during baseline; automated packing during trial.
- Baseline: 1–14 September 2026. Trial: 15–28 September 2026.
- Exposure: two four-hour shifts per station per day, one operator per station. No staffing reduction is assumed.
- Product classes: standard and bulky. Retain mix, station and shift for diagnostic segmentation.
- One event per completed package, one record per station shift and separate downtime incidents.
- Fixed non-randomized cohorts, not a randomized A/B experiment. Parallel trends, no spillover and no differential unobserved changes would be needed for a causal interpretation; these are not established here.

## Measures and gates

| Measure | Definition | Illustrative gate |
|---|---|---|
| Throughput | Valid completed packages / scheduled staffed hours | Adjusted gain >=10%; lower 95% interval >0 |
| Defects | Defective completed packages / completed packages | Upper 95% adjusted increase <=0.50 percentage points |
| Uptime | 1 − logged downtime / scheduled station seconds | Pilot trial >=95% |
| Data acceptance | Accepted events / raw events, including duplicate rows | >=99.5% |
| Cost/good package | Staff + operating equipment + defect rework costs / non-defective completions | Pilot <= concurrent control |

Snapshot source lag must be <=12 hours. Missing expected shifts or source freshness failure blocks warehouse publication. The scale/readiness decision remains subject to real-world validation even if every analytical gate passes.

## Collection in a real pilot

This project generates records. A real collection plan would require authorized system extracts, package IDs, synchronized event clocks, verified staffed hours, a stable defect definition, aligned fault-log timestamps, and reconciliation to operational totals. Record arrivals and work-in-progress if studying demand constraints or queueing. Do not infer true maximum capacity from observed completed volume alone.

An analyst can prepare time-study sheets, metric definitions and an issue register. Actual pilot operation, pre-trial safety checks and equipment access must follow the site's qualified engineering and safety processes. No physical actions are authorized or represented by this project.

## Owners and review rhythm

- Analyst: validate extracts; refresh scorecards; review exception queue daily.
- Quality owner: verify defect labels and investigate problematic cohorts.
- Equipment owner: verify downtime and equipment hypotheses.
- Site lead: coordinate controlled retest and readiness evidence.
- Finance owner: validate cost assumptions before an investment decision.

Freeze definitions, thresholds, cohort rules and analysis window before a real retest. Review quality/uptime daily; decide only after the predeclared trial window rather than stopping when a favourable result appears.
