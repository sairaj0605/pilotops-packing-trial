-- Query 1: How many valid completed packages are in the database?
SELECT COUNT(*) AS valid_packages
FROM package_events;

-- Query 2: What happened each day in the two groups?
SELECT day,phase,arm,packages,defects,
       ROUND(throughput,2) AS packages_per_hour,
       ROUND(defect_rate*100,2) AS defect_percent
FROM v_daily_scorecard
ORDER BY day,arm
LIMIT 10;

-- Query 3: Which pilot trial groups had the most defects?
-- Keep the denominator visible so a small group is not misleading.
SELECT station,shift_name,sku_class,packages,defects,
       ROUND(defect_rate*100,2) AS defect_percent
FROM v_defect_cohorts
WHERE phase='trial' AND arm='pilot' AND packages>=500
ORDER BY defect_rate DESC
LIMIT 5;
