-- Run each query separately against warehouse/pilotops.sqlite.

-- 1. Rank exploratory pilot trial defect cohorts, retaining denominator sizes.
SELECT *, DENSE_RANK() OVER(ORDER BY defect_rate DESC) AS risk_rank
FROM v_defect_cohorts
WHERE phase='trial' AND arm='pilot' AND packages>=500
ORDER BY risk_rank;

-- 2. Product mix: different proportions can change aggregate defect rates.
WITH counts AS (
 SELECT s.phase,s.arm,e.sku_class,COUNT(*) AS packages
 FROM package_events e JOIN shifts s USING(shift_id)
 GROUP BY s.phase,s.arm,e.sku_class
)
SELECT *,packages*1.0/SUM(packages) OVER(PARTITION BY phase,arm) AS product_mix
FROM counts ORDER BY phase,arm,sku_class;

-- 3. Matched cohort risk differences, before and after the trial.
-- This is exploratory segmentation, not a corrected multiple-testing analysis.
WITH rates AS (
 SELECT station,shift_name,sku_class,
   MAX(CASE WHEN phase='baseline' AND arm='pilot' THEN defect_rate END) AS pilot_before,
   MAX(CASE WHEN phase='trial' AND arm='pilot' THEN defect_rate END) AS pilot_after,
   MAX(CASE WHEN phase='baseline' AND arm='control' THEN defect_rate END) AS control_before,
   MAX(CASE WHEN phase='trial' AND arm='control' THEN defect_rate END) AS control_after
 FROM v_defect_cohorts GROUP BY station,shift_name,sku_class
)
SELECT *,100*((pilot_after-pilot_before)-(control_after-control_before)) AS adjusted_change_pp
FROM rates ORDER BY adjusted_change_pp DESC;

-- 4. Demonstrate the dangerous join using a single shift.
-- Compare COUNT(*) below with SELECT packages FROM v_shift_scorecard for that shift.
-- Multiple downtime incidents multiply every package. Never use this as a KPI.
SELECT e.shift_id,COUNT(*) AS INCORRECT_package_count
FROM package_events e JOIN faults f USING(shift_id)
WHERE e.shift_id=(SELECT MIN(shift_id) FROM shifts)
GROUP BY e.shift_id;
