# Data dictionary

All records are synthetic. Dates/times are naive local site timestamps for this fixed scenario; a production system should store explicit timezone-aware UTC timestamps and a separate site timezone.

## Source tables

| Table | Grain / key | Fields |
|---|---|---|
| shifts | One scheduled station shift / shift_id | day; phase baseline/trial; arm control/pilot; paired station P1/P2/P3; shift_name day/night; scheduled_seconds=14400 |
| package_events | One completed package / event_id | shift_id foreign key; completed_at; sku_class standard/bulky; cycle_seconds; defective 0/1 |
| faults | One downtime incident / fault_id | shift_id foreign key; reason; seconds |

Fault durations represent non-overlapping stoppages in this generator. A real source needs interval overlap handling before summing durations. Each completed package belongs to a single shift. Defects mean a failed first-pass quality check in this example; they do not represent customer returns or safety incidents.

The pilot arm is a station assignment, not an equipment-state label. It is manual in baseline and automated only in trial.

## Generated tables and files

| Item | Meaning |
|---|---|
| quarantine.csv | Rejected non-identical event rows with one primary reason |
| v_shift_scorecard | One shift; package/defect counts, staffed hours, downtime, uptime and throughput |
| v_daily_scorecard | One day/arm; weighted operational totals and rates |
| v_daily_trends | Daily scorecard plus LAG and rolling seven-observation throughput |
| v_defect_cohorts | Phase × arm × station × shift × product-class counts and rates |
| v_fault_pareto | Pilot trial recorded downtime by reason, ranked by minutes, cumulative share |
| alert_queue.csv | Local operating-rule breaches, owner and recommended next action |
| summary.json | Decision, uncertainty intervals, gates, periods and evidence limits |
| pipeline_log.json | Actual step statuses/durations and code/config fingerprint for this local run |

The reports retain denominators. Zero package denominators produce NULL in SQL rather than a misleading zero defect rate; missing/empty shifts block publication in the reference scenario.
