# Methodology and limitations

## Weighted operational metrics

Throughput = sum(completed packages) / sum(scheduled staffed hours).

Defect rate = sum(defective packages) / sum(completed packages).

Uptime = 1 − sum(downtime seconds) / sum(scheduled station seconds).

Use ratios of sums, not unweighted averages of station defect percentages. For example, a 10-package station should not carry the same defect-rate weight as a 1,000-package station. Under the fixed staffing schedule, station hours also equal staffed hours; that equivalence would break if a real site used different operator counts.

The measure is realized throughput, not proven equipment capacity. Incoming demand, work-in-progress and staffing constraints could affect it. Good packages exclude the initially defective completion; reworked output is not counted again.

## Adjusting the before/after comparison

Let T be pilot-arm throughput and C be control-arm throughput. Subscripts 0/1 denote baseline/trial.

Adjusted relative throughput gain = (T1 / C1) / (T0 / C0) − 1.

For defect rates D, use an additive difference-in-differences:

Adjusted defect change in percentage points = 100 × [(DT1 − DT0) − (DC1 − DC0)].

A 1 percentage-point increase is different from a 1% relative increase. The report labels these separately.

These calculations help adjust for a common time shock. They do **not** establish causality: cohorts are fixed, not randomized, and one simulated site cannot demonstrate external validity. No p-value or causal effectiveness claim is made.

## Uncertainty

Each bootstrap draw resamples 14 matched day blocks independently within each phase. Both arms and all station/shift observations remain in the selected day. The 2.5th and 97.5th percentiles of 2,000 draws form the descriptive 95% interval.

Days, not packages, are the resampling units. Days are assumed exchangeable within phase. With only 14 days, intervals are approximate. Persistent station effects, serial dependence, learning curves and carryover could require randomized switchbacks, more sites and time-block bootstrap methods in a real study. The implementation is a learning example, not a formal non-inferiority trial design.

## Data-quality policy

1. Keep one copy of a fully identical event row.
2. Quarantine every version of a conflicting event ID. Do not arbitrarily choose the latest unless a documented source rule permits it.
3. Reject missing keys, unknown shifts, invalid product classes, impossible numeric values, bad defect flags, malformed timestamps, future events and events outside their shift.
4. Attach one primary rejection reason per row so the accounting is exact: raw = valid + quarantined + exact duplicates removed.
5. Fail publication on missing reference data, missing shifts, invalid downtime, unexpected schedules or stale sources.
6. Aggregate package and downtime facts separately before joining them to shifts.

`generator_manifest.json` documents deliberately injected corruption for the test suite. It is not used to infer operational causes. In a real source, package counts would need reconciliation to an independent upstream total; row acceptance alone cannot detect events never delivered by the source.

## Alerts versus statistical conclusions

The alert queue flags daily pilot defects above 2% and pilot shift uptime below 95%. These are operating rules, not statistical control limits or significance tests. Alerts can repeat across days because they form a review queue; deduplication, notification delivery, acknowledgements and on-call escalation are not implemented.

The project has a 7-day moving average, **not** a validated statistical process control chart. Do not call it an SPC control chart on a CV.

## Root cause analysis

The cohort table helps locate unusually high rates. Compare rates **and denominators** by station, shift and product class; inspect baseline and control, not only the pilot trial. The downtime Pareto ranks recorded reasons by minutes lost, not incident count.

A sensor alarm is a recorded symptom. It does not prove a defective sensor caused quality loss. Proposed follow-up: inspect affected units, verify label validity and collection consistency, inspect equipment records, identify testable setup/material/operator hypotheses, then run a controlled corrective-action trial. Use a 5 Whys worksheet only when each link has evidence. If a link is unknown, mark it unknown.

## Economics

Assumptions: INR 250/operator-hour, INR 180/pilot equipment-hour, zero incremental control equipment charge, INR 60/defective package rework cost. These are fictional placeholders, not market quotes. Costs exclude capital acquisition, finance, deployment, maintenance contracts, indirect staffing, training, space, demand elasticity and future savings. Do not interpret cost per good package as a capital-investment ROI or payback calculation.

## Reliability and safety

Data freshness is evaluated against the **simulated as-of time**, not the computer's current date. The warehouse is published via an atomic staging-file replacement. Logs cover this local run only; no scheduling, production SLA or 100% availability is claimed. A failed run removes the previous current HTML/summary/memo to avoid presenting them as the latest successful run; its failure is logged.

No Amazon DWP jobs, internal data tools, real AMRs or packing equipment are connected. No physical testing or safety approval occurred. A real scale decision needs qualified site safety/engineering approval and additional evidence.
