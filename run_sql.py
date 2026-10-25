"""Run read-only SQL against the generated PilotOps SQLite database.

Examples:
    python run_sql.py
    python run_sql.py --file sql/start_here.sql
    python run_sql.py --query "SELECT * FROM v_daily_scorecard LIMIT 5;"
"""
from pathlib import Path
import argparse
import sqlite3
import sys

ROOT=Path(__file__).resolve().parent
DB=ROOT/'warehouse/pilotops.sqlite'


def statements(text):
    pending=''
    for line in text.splitlines(keepends=True):
        pending+=line
        if sqlite3.complete_statement(pending):
            yield pending.strip()
            pending=''
    # Allow a single final query without a semicolon.
    if pending.strip():yield pending.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group()
    source.add_argument('--file',help='SQL file path, relative to the project folder')
    source.add_argument('--query',help='A SQL query in double quotes')
    parser.add_argument('--limit',type=int,default=20,help='Maximum displayed rows per query; default 20')
    args=parser.parse_args()
    if args.limit<1:parser.error('--limit must be positive')
    if not DB.exists():parser.exit(1,'Database missing. Run python pilotops.py first.\n')
    if args.file:
        path=Path(args.file)
        if not path.is_absolute():path=ROOT/path
        text=path.read_text(encoding='utf-8')
    else:text=args.query or 'SELECT * FROM v_daily_scorecard LIMIT 5;'
    try:
        with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as con:
            for number,sql in enumerate(statements(text),1):
                cur=con.execute(sql)
                if cur.description is None:continue
                rows=cur.fetchmany(args.limit+1)
                print(f'\nQuery {number}')
                print(' | '.join(x[0] for x in cur.description))
                for row in rows[:args.limit]:
                    print(' | '.join('NULL' if x is None else str(round(x,4)) if isinstance(x,float) else str(x) for x in row))
                if len(rows)>args.limit:print(f'Displaying first {args.limit} rows. Increase --limit to see more.')
    except sqlite3.Error as exc:
        print(f'SQL error: {exc}',file=sys.stderr);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
