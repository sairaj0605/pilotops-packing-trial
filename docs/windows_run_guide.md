# Run PilotOps on Windows

You run the Python file first. It creates the sample data, builds the SQLite database, runs the SQL models and produces the report. After that, you can query the database separately to practise SQL.

## 1. Prepare the folder

Download the project ZIP and use **Extract All**. Move the inner folder containing `pilotops.py`, `requirements.txt` and `config.json` to:

`C:\Projects\PilotOps`

The commands below assume that exact location. If you use another folder, change the first command to match.

## 2. Check Python

Open Command Prompt and enter:

```bat
py --version
```

This project was tested with Python 3.12. Use Python 3.12 for the closest match. If `py` is not recognised, install Python from python.org first and reopen Command Prompt. If your computer uses `python` instead of `py`, substitute `python` in the environment-creation command.

## 3. Set up the project environment

In Command Prompt, run one line at a time:

```bat
cd /d C:\Projects\PilotOps
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- `cd` opens the project folder in your terminal.
- `venv` creates a separate Python environment for this project.
- `pip install` installs Pandas, NumPy and Matplotlib into that environment.

If `py -3.12` says Python 3.12 is not installed, install that version or use an existing compatible Python 3.11/3.13 interpreter. The package was tested on 3.12; other versions have not been verified here.

The commands use the environment's Python executable directly. You do not need to activate PowerShell scripts or change your computer's execution policy.

## 4. Run Python

```bat
.venv\Scripts\python.exe pilotops.py
```

It generates the CSV data, checks it, loads SQLite, runs the SQL models, calculates the results and creates the report. For the default seed, the output includes about 17.9% adjusted throughput gain and a HOLD recommendation.

Open the report:

```bat
start "" "outputs\report.html"
```

Or open the `outputs` folder in File Explorer and double-click `report.html`.

## 5. Run the checks

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected result: **12 tests pass**. The tests deliberately try invalid inputs as well as correct data.

## 6. Run SQL without another installation

SQLite comes with Python. The database file is:

`C:\Projects\PilotOps\warehouse\pilotops.sqlite`

Try the starter queries:

```bat
.venv\Scripts\python.exe run_sql.py --file sql/start_here.sql
```

Run one query directly:

```bat
.venv\Scripts\python.exe run_sql.py --query "SELECT COUNT(*) AS valid_packages FROM package_events;"
```

Expected answer with the default data: **75563**.

For the next set of exercises:

```bat
.venv\Scripts\python.exe run_sql.py --file sql/diagnostics.sql
```

The runner displays up to 20 rows per query. Add `--limit 100` if needed. It opens the database read-only so it cannot accidentally change your data.

`sql/models.sql` contains CREATE VIEW statements. The pipeline already runs these when it creates the database. Query the views to practise analysis; do not rerun that model file against the same database or through the read-only runner.

## 7. Optional SQL window

If you prefer a visual editor, install **DB Browser for SQLite** from `https://sqlitebrowser.org/dl/`.

1. Choose **Open Database**.
2. Select `warehouse\pilotops.sqlite` inside your project folder.
3. Open **Execute SQL**.
4. Paste one SELECT query from `sql/start_here.sql` and run it.
5. Browse `shifts`, `package_events`, `faults` and the calculated views.

This database is SQLite. MySQL Workbench connects to a MySQL server and cannot directly open this `.sqlite` file. There is no need to install MySQL for this project.

## Which file should you read first?

| File | Purpose |
|---|---|
| `pilotops.py` | The Python pipeline |
| `sql/start_here.sql` | First SQL queries to run and change |
| `sql/models.sql` | The queries that build the scorecards |
| `sql/diagnostics.sql` | Deeper checks and comparisons |
| `outputs/report.html` | The visual result |
| `docs/learning_path.md` | Exercises and explanations |

## Common problems

- **No module named pandas:** install requirements with the exact `.venv\Scripts\python.exe` command above and run using that same executable.
- **Cannot open requirements.txt:** check that Command Prompt is in the folder containing that file, not the outer ZIP extraction folder.
- **Database missing:** run `pilotops.py` first.
- **No such table:** open the generated `warehouse\pilotops.sqlite`, not a new empty database.
- **Attempt to write a readonly database:** the SQL runner is for SELECT queries. Schema creation is handled by the pipeline.
- **Files appear unchanged after editing SQL:** rerun `pilotops.py` to rebuild the warehouse. Close the database in DB Browser first if Windows reports that the file is in use.

The default pipeline regenerates its sample inputs. To test changes you made to the existing CSV files, use `pilotops.py --reuse-raw` instead.
