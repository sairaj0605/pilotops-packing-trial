-- Grain: one row per station shift. Aggregate packages BEFORE joining shift facts.
-- A raw event-to-fault join would multiply both package counts and downtime.
CREATE VIEW v_shift_scorecard AS
WITH package_totals AS (
 SELECT shift_id, COUNT(*) AS packages, SUM(defective) AS defects,
        SUM(cycle_seconds) AS cycle_seconds
 FROM package_events GROUP BY shift_id
), downtime_totals AS (
 SELECT shift_id, SUM(seconds) AS downtime_seconds
 FROM faults GROUP BY shift_id
)
SELECT s.*, COALESCE(p.packages,0) AS packages,
       COALESCE(p.defects,0) AS defects,
       p.cycle_seconds,
       COALESCE(f.downtime_seconds,0) AS downtime_seconds,
       s.scheduled_seconds/3600.0 AS staffed_hours,
       COALESCE(p.packages,0)/(s.scheduled_seconds/3600.0) AS packages_per_staffed_hour,
       1.0-COALESCE(f.downtime_seconds,0)*1.0/s.scheduled_seconds AS uptime,
       COALESCE(p.defects,0)*1.0/NULLIF(p.packages,0) AS defect_rate
FROM shifts s
LEFT JOIN package_totals p ON s.shift_id=p.shift_id
LEFT JOIN downtime_totals f ON s.shift_id=f.shift_id;

CREATE VIEW v_daily_scorecard AS
SELECT day, phase, arm, SUM(packages) AS packages, SUM(defects) AS defects,
       SUM(staffed_hours) AS staffed_hours,
       SUM(downtime_seconds) AS downtime_seconds,
       SUM(scheduled_seconds) AS scheduled_seconds,
       SUM(packages)*1.0/SUM(staffed_hours) AS throughput,
       SUM(defects)*1.0/NULLIF(SUM(packages),0) AS defect_rate
FROM v_shift_scorecard GROUP BY day,phase,arm;

-- Window functions compare current performance with the previous observation.
-- LAG is not used to fabricate a missing day. Completeness is checked separately.
CREATE VIEW v_daily_trends AS
SELECT *, LAG(throughput) OVER(PARTITION BY arm ORDER BY day) AS prior_day_throughput,
       AVG(throughput) OVER(PARTITION BY arm ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS rolling_7day_throughput,
       throughput-LAG(throughput) OVER(PARTITION BY arm ORDER BY day) AS day_change
FROM v_daily_scorecard;

CREATE VIEW v_defect_cohorts AS
SELECT s.phase,s.arm,s.station,s.shift_name,e.sku_class,
       COUNT(*) AS packages,SUM(e.defective) AS defects,
       SUM(e.defective)*1.0/COUNT(*) AS defect_rate
FROM package_events e JOIN shifts s ON e.shift_id=s.shift_id
GROUP BY s.phase,s.arm,s.station,s.shift_name,e.sku_class;

CREATE VIEW v_fault_pareto AS
WITH totals AS (
 SELECT f.reason,SUM(f.seconds) AS seconds,COUNT(*) AS incidents
 FROM faults f JOIN shifts s ON f.shift_id=s.shift_id
 WHERE s.phase='trial' AND s.arm='pilot' GROUP BY f.reason
)
SELECT *,SUM(seconds) OVER(ORDER BY seconds DESC,reason ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)*1.0/
             SUM(seconds) OVER() AS cumulative_share
FROM totals ORDER BY seconds DESC,reason;
