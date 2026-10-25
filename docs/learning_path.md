# Working through PilotOps

The easiest way to learn this project is to follow one record from the CSV to the final report. These steps turn the reference code into something you can explain and change yourself.

## 1. Start with one shift

Open `shifts.csv`, `events.csv` and `faults.csv` in `data/raw` after running the project. Pick one shift ID and find the package records and downtime entries linked to it.

Calculate its packages per hour, defect rate and uptime yourself. Compare your answers with `outputs/shift_scorecard.csv`.

Check you can explain why the pilot group is still manual during the first 14 days.

## 2. Work through the SQL

Read `sql/models.sql`. Run its queries in a SQL editor or through Python's sqlite3 module.

Practise writing these without copying:

1. Count completed and defective packages by day and group.
2. Calculate defect rates by station and shift, keeping the package counts visible.
3. Find the three highest-risk groups with at least 500 packages.
4. Join packages directly to fault records and see what goes wrong with the counts.
5. Fix the join by adding up each source first.

Then explain `LAG`, `PARTITION BY` and the rolling seven-row average. Why do we check for missing days before calling it a seven-day average?

## 3. Follow the Python checks

Read `clean_events` in `pilotops.py`. Focus on duplicate checks, numeric conversion, dates and the reason attached to each rejected row.

Make a separate copy of the project. Remove a shift from its raw file and run:

```bash
python pilotops.py --reuse-raw
```

Look at the error, restore the source and rerun. Check `pipeline_log.json`. Explain why the program should stop rather than publish incomplete results.

## 4. Understand the comparison

Read `estimate` and `bootstrap`. Write down what each calculation does in ordinary language before trying to memorise the code.

- Why compare against a manual group as well as the earlier period?
- What is the difference between a percentage change and a percentage-point change?
- Why resample whole days rather than individual packages?
- Why is the station hotspot a clue rather than a confirmed cause?

Try changing the hourly equipment cost in a copy of `config.json`. Rerun and explain the cost result. Keep the original decision thresholds so the comparison stays fair.

## 5. Explain the result

Write a short recommendation covering what improved, what got worse, what you would investigate and what evidence is missing.

Practise a two-minute walkthrough with the report open. Then close the report, open the code and try changing a SQL query or validation rule. That is a better readiness check than memorising a description.

## Useful additions

- An Excel PivotTable and a sheet checking the totals against SQL.
- A Power BI page using the exported scorecards.
- A product-mix comparison to check whether bulky items explain part of the result.
- A second fictional site to explore whether the result carries over.

Keep a record of the changes you actually make and the reasoning behind them. There is no need to add machine learning or an AI agent unless it solves a clear problem.
