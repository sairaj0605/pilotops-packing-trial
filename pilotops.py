"""Reproducible fictional packing pilot; no Amazon data, systems or equipment.

Run: python pilotops.py
All input and output paths are resolved relative to this file, not the shell cwd.
"""
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import base64
import csv
import hashlib
import html
import json
import sqlite3
import sys
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent
RAW, CLEAN, OUT = ROOT/'data/raw', ROOT/'data/processed', ROOT/'outputs'
DB = ROOT/'warehouse/pilotops.sqlite'
CONFIG = json.loads((ROOT/'config.json').read_text())


def require(condition,message):
    """Input checks must still execute if Python is launched with -O."""
    if not condition:
        raise ValueError(message)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


def generate(seed=42):
    """Generate fixed cohorts: three pairs of stations, two four-hour shifts/day.

    Baseline: both arms pack manually. Trial: pilot arm gets automated equipment.
    Assignment is NOT randomized. The generator deliberately creates a defect
    hotspot; observed cohort associations are not proof of the physical cause.
    """
    rng=np.random.default_rng(seed)
    shifts, events, faults=[],[],[]
    start=datetime(2026,9,1); eid=0; fid=0
    for day_index in range(CONFIG['baseline_days']+CONFIG['trial_days']):
        day=start+timedelta(days=day_index)
        phase='baseline' if day_index<CONFIG['baseline_days'] else 'trial'
        # Common daily shock affects both arms: a reason naive before/after is weak.
        common=float(rng.normal(1.0,.055)) * (1.04 if phase=='trial' else 1)
        for arm in ['control','pilot']:
            for station in ['P1','P2','P3']:
                for shift_name,hour in [('day',8),('night',18)]:
                    shift_id=f'{day:%Y%m%d}_{arm}_{station}_{shift_name}'
                    scheduled=14400
                    downtime=int(rng.integers(200,420))
                    automation=phase=='trial' and arm=='pilot'
                    hotspot=automation and station=='P3' and shift_name=='night'
                    if hotspot:downtime+=int(rng.integers(700,1000))
                    reasons=[('changeover',downtime//3),
                             ('sensor_alarm' if hotspot else 'routine_stop',downtime-downtime//3)]
                    for reason,seconds in reasons:
                        fid+=1;faults.append(dict(fault_id=f'F{fid:05}',shift_id=shift_id,
                                                 reason=reason,seconds=seconds))
                    shifts.append(dict(shift_id=shift_id,day=day.strftime('%Y-%m-%d'),
                                       phase=phase,arm=arm,station=station,shift_name=shift_name,
                                       scheduled_seconds=scheduled))
                    # Two gross throughput drivers: common demand and trial automation.
                    number=int(210*common*(1.19 if automation else 1)*float(rng.normal(1,.025)))
                    if hotspot:number=int(number*.90)
                    elapsed=0.0
                    for _ in range(number):
                        sku_class=str(rng.choice(['standard','bulky'],p=[.72,.28]))
                        cycle=float(rng.lognormal(np.log(42 if automation else 50),.18))
                        if sku_class=='bulky':cycle*=1.10
                        elapsed+=cycle
                        # All event timestamps fit inside the scheduled four-hour shift.
                        if elapsed>scheduled-downtime-60:break
                        eid+=1
                        defect_probability=.014+(.002 if phase=='trial' else 0)
                        if hotspot and sku_class=='bulky':defect_probability+=.21
                        events.append(dict(event_id=f'E{eid:07}',shift_id=shift_id,
                                           completed_at=(day+timedelta(hours=hour,seconds=elapsed)).isoformat(timespec='seconds'),
                                           sku_class=sku_class,cycle_seconds=round(cycle,3),
                                           defective=int(rng.random()<defect_probability)))
    original=len(events)
    # Known, auditable corruption fixtures. Quarantine instead of silently fixing.
    events += [dict(events[i]) for i in range(12)]
    for i in range(4):
        row=dict(events[i+30]);row['event_id']=f'BADNEG{i}';row['cycle_seconds']=-5;events.append(row)
    row=dict(events[60]);row['event_id']='BADFK';row['shift_id']='UNKNOWN';events.append(row)
    row=dict(events[61]);row['event_id']='BADFUTURE';row['completed_at']='2026-10-10T10:00:00';events.append(row)
    row=dict(events[62]);row['event_id']='BADDUP';row['defective']=1-row['defective'];events.append(row)
    other=dict(row);other['defective']=1-row['defective'];events.append(other)
    write_csv(RAW/'shifts.csv',shifts);write_csv(RAW/'events.csv',events);write_csv(RAW/'faults.csv',faults)
    truth={'original_valid_events':original,'exact_duplicates_added':12,
           'invalid_single_rows_added':6,'conflicting_duplicate_rows_added':2,
           'purpose':'Generator fixtures for tests only; excluded from analytical diagnosis.'}
    (RAW/'generator_manifest.json').write_text(json.dumps(truth,indent=2))


def clean_events(frame, shifts, as_of):
    """Return valid events, quarantine and quality counters. No imputation.

    Exact duplicates keep one; ALL versions of conflicting keys are quarantined.
    Each quarantined row receives one primary reason, making reconciliation exact.
    """
    raw_count=len(frame)
    df=frame.copy()
    exact=int(df.duplicated().sum());df=df.drop_duplicates().copy()
    conflict=df.event_id.duplicated(keep=False)
    reason=pd.Series('', index=df.index)
    reason.loc[conflict]='conflicting_event_id'
    def flag(mask,label):reason.loc[(reason=='')&mask]=label
    flag(df.event_id.isna()|df.shift_id.isna(),'missing_key')
    flag(~df.shift_id.isin(shifts.shift_id),'unknown_shift')
    cycles=pd.to_numeric(df.cycle_seconds,errors='coerce')
    defects=pd.to_numeric(df.defective,errors='coerce')
    timestamps=pd.to_datetime(df.completed_at,errors='coerce')
    flag(cycles.isna()|~np.isfinite(cycles)|(cycles<=0)|(cycles>600),'invalid_cycle')
    flag(~defects.isin([0,1]),'invalid_defect_flag')
    flag(~df.sku_class.isin(['standard','bulky']),'invalid_sku_class')
    flag(timestamps.isna(),'invalid_timestamp')
    flag(timestamps>pd.Timestamp(as_of),'future_event')
    # Validate each timestamp against its own shift, not just a global date range.
    shift_lookup=shifts.set_index('shift_id')
    mapped_day=pd.to_datetime(df.shift_id.map(shift_lookup.day),errors='coerce')
    shift_hour=df.shift_id.map(shift_lookup.shift_name).map({'day':8,'night':18})
    begin=mapped_day+pd.to_timedelta(shift_hour,unit='h')
    end=begin+pd.to_timedelta(df.shift_id.map(shift_lookup.scheduled_seconds),unit='s')
    flag((timestamps<begin)|(timestamps>end),'outside_shift')
    quarantine=df.loc[reason!=''].copy();quarantine['reason']=reason.loc[reason!='']
    valid=df.loc[reason==''].copy()
    valid['cycle_seconds']=cycles.loc[valid.index].astype(float)
    valid['defective']=defects.loc[valid.index].astype(int)
    quality={'raw_rows':raw_count,'exact_duplicates_removed':exact,
             'quarantined_rows':len(quarantine),'valid_rows':len(valid),
             'valid_event_fraction':len(valid)/raw_count}
    require(raw_count==len(valid)+len(quarantine)+exact,'Lost or double-counted rows')
    return valid,quarantine,quality


def load_warehouse(as_of):
    shifts=pd.read_csv(RAW/'shifts.csv');faults=pd.read_csv(RAW/'faults.csv')
    # Fail critical reference integrity problems; package errors can be quarantined.
    require(shifts.shift_id.is_unique and faults.fault_id.is_unique,'Duplicate reference keys')
    require(set(shifts.arm)=={'control','pilot'},'Both comparison arms are required')
    require(shifts.scheduled_seconds.gt(0).all(),'Invalid shift duration')
    require(faults.shift_id.isin(shifts.shift_id).all() and faults.seconds.ge(0).all(),'Invalid downtime reference or duration')
    valid,quarantine,quality=clean_events(pd.read_csv(RAW/'events.csv'),shifts,as_of)
    expected_days=CONFIG['baseline_days']+CONFIG['trial_days']
    require(len(shifts)==expected_days*2*3*2,'Missing expected station shifts')
    require(shifts.groupby(['day','arm']).size().eq(6).all(),'Unbalanced shift exposure')
    dates=pd.date_range('2026-09-01',periods=expected_days).strftime('%Y-%m-%d')
    expected={(day,arm,station,shift_name) for day in dates
              for arm in ['control','pilot'] for station in ['P1','P2','P3']
              for shift_name in ['day','night']}
    observed=set(shifts[['day','arm','station','shift_name']].itertuples(index=False,name=None))
    require(observed==expected,'Unexpected or missing collection schedule cells')
    require(shifts.scheduled_seconds.eq(14400).all(),'Scenario requires four-hour staffed shifts')
    trial_start=(pd.Timestamp('2026-09-01')+pd.Timedelta(days=CONFIG['baseline_days'])).strftime('%Y-%m-%d')
    require(shifts.phase.eq(np.where(shifts.day<trial_start,'baseline','trial')).all(),'Phase/date mismatch')
    require(set(valid.shift_id)==set(shifts.shift_id),'A shift has no valid package data')
    latest=pd.to_datetime(valid.completed_at).max()
    quality['source_lag_hours']=(pd.Timestamp(as_of)-latest).total_seconds()/3600
    require(0<=quality['source_lag_hours']<=CONFIG['gates']['maximum_source_lag_hours'],'Source freshness failure')
    CLEAN.mkdir(parents=True,exist_ok=True)
    valid.to_csv(CLEAN/'events.csv',index=False);quarantine.to_csv(CLEAN/'quarantine.csv',index=False)
    # Atomic publish: readers never see a partially replaced SQLite warehouse.
    DB.parent.mkdir(parents=True,exist_ok=True)
    staging=DB.with_suffix('.staging.sqlite')
    if staging.exists():staging.unlink()
    con=sqlite3.connect(staging)
    con.executescript('''PRAGMA foreign_keys=ON;
      CREATE TABLE shifts(shift_id TEXT PRIMARY KEY,day TEXT,phase TEXT,arm TEXT,
        station TEXT,shift_name TEXT,scheduled_seconds INTEGER CHECK(scheduled_seconds>0));
      CREATE TABLE package_events(event_id TEXT PRIMARY KEY,shift_id TEXT REFERENCES shifts,
        completed_at TEXT,sku_class TEXT,cycle_seconds REAL CHECK(cycle_seconds>0),
        defective INTEGER CHECK(defective IN(0,1)));
      CREATE TABLE faults(fault_id TEXT PRIMARY KEY,shift_id TEXT REFERENCES shifts,
        reason TEXT,seconds INTEGER CHECK(seconds>=0));
      CREATE INDEX idx_events_shift ON package_events(shift_id);
      CREATE INDEX idx_faults_shift ON faults(shift_id);''')
    shifts.to_sql('shifts',con,if_exists='append',index=False)
    valid.to_sql('package_events',con,if_exists='append',index=False)
    faults.to_sql('faults',con,if_exists='append',index=False)
    con.executescript((ROOT/'sql/models.sql').read_text())
    checks=pd.read_sql_query('SELECT * FROM v_shift_scorecard',con)
    require(checks.packages.sum()==len(valid),'Fan-out duplicated package facts')
    require(checks.downtime_seconds.sum()==faults.seconds.sum(),'Fan-out duplicated downtime')
    require(checks.uptime.between(0,1).all(),'Downtime exceeds scheduled duration')
    con.commit();con.close();staging.replace(DB)
    return quality


def estimate(blocks):
    """Weighted station-hour throughput and package-weighted quality.

    Return relative ratio-of-ratios throughput gain and additive defect DiD (pp).
    All baseline/trial comparisons retain both arms.
    """
    stats={}
    for phase in ['baseline','trial']:
        for arm in ['control','pilot']:
            x=blocks[(blocks.phase==phase)&(blocks.arm==arm)]
            stats[phase,arm]={'rate':x.packages.sum()/x.staffed_hours.sum(),
                              'defect':x.defects.sum()/x.packages.sum()}
    gain=(stats['trial','pilot']['rate']/stats['trial','control']['rate'])/(
        stats['baseline','pilot']['rate']/stats['baseline','control']['rate'])-1
    defect_pp=100*((stats['trial','pilot']['defect']-stats['baseline','pilot']['defect'])-(
        stats['trial','control']['defect']-stats['baseline','control']['defect']))
    return float(gain),float(defect_pp)


def bootstrap(daily,samples,seed):
    """Resample matched DAYS within phase, preserving both arms and all stations.

    Package rows are not independent trial units. Treating them as independent
    would give misleadingly narrow uncertainty intervals.
    """
    rng=np.random.default_rng(seed);draws=[]
    # Sum arrays per day/arm: packages, defects, staffed hours.
    cubes=[]
    for phase in ['baseline','trial']:
        x=daily[daily.phase==phase]
        days=sorted(x.day.unique())
        cubes.append(np.array([[[float(x[(x.day==day)&(x.arm==arm)][c].iloc[0])
                                  for c in ['packages','defects','staffed_hours']]
                                  for arm in ['control','pilot']] for day in days]))
    for _ in range(samples):
        agg=[cube[rng.integers(0,len(cube),len(cube))].sum(axis=0) for cube in cubes]
        base,trial=agg
        br=base[:,0]/base[:,2];tr=trial[:,0]/trial[:,2]
        bd=base[:,1]/base[:,0];td=trial[:,1]/trial[:,0]
        draws.append([(tr[1]/tr[0])/(br[1]/br[0])-1,100*((td[1]-bd[1])-(td[0]-bd[0]))])
    a=np.array(draws)
    return {'throughput_gain_ci95':np.quantile(a[:,0],[.025,.975]).tolist(),
            'defect_did_pp_ci95':np.quantile(a[:,1],[.025,.975]).tolist()}


def analyse(quality):
    con=sqlite3.connect(DB)
    daily=pd.read_sql_query('SELECT * FROM v_daily_trends ORDER BY day,arm',con)
    shifts=pd.read_sql_query('SELECT * FROM v_shift_scorecard',con)
    cohorts=pd.read_sql_query('SELECT * FROM v_defect_cohorts',con)
    pareto=pd.read_sql_query('SELECT * FROM v_fault_pareto',con)
    con.close()
    gain,defect_pp=estimate(daily)
    metrics={'adjusted_throughput_gain':gain,'adjusted_defect_change_pp':defect_pp,
             **bootstrap(daily,CONFIG['bootstrap_samples'],CONFIG['seed']+1)}
    econ=CONFIG['economics'];periods=[]
    for (phase,arm),x in shifts.groupby(['phase','arm']):
        # The pilot cohort is still manual during baseline: no automation charge.
        equipment=econ['pilot_equipment_cost_per_hour'] if phase=='trial' and arm=='pilot' else econ['control_equipment_cost_per_hour']
        cost=x.staffed_hours.sum()*(econ['staff_cost_per_hour']+equipment)+x.defects.sum()*econ['defect_rework_cost']
        periods.append(dict(phase=phase,arm=arm,packages=int(x.packages.sum()),defects=int(x.defects.sum()),
                            throughput=float(x.packages.sum()/x.staffed_hours.sum()),
                            defect_rate=float(x.defects.sum()/x.packages.sum()),
                            uptime=float(1-x.downtime_seconds.sum()/x.scheduled_seconds.sum()),
                            cost_per_good_package=float(cost/(x.packages.sum()-x.defects.sum()))))
    pilot=next(x for x in periods if x['phase']=='trial' and x['arm']=='pilot')
    control=next(x for x in periods if x['phase']=='trial' and x['arm']=='control')
    px=shifts[(shifts.phase=='trial')&(shifts.arm=='pilot')]
    hours=float(px.staffed_hours.sum());good=float(px.packages.sum()-px.defects.sum())
    fixed=hours*econ['staff_cost_per_hour']+float(px.defects.sum())*econ['defect_rework_cost']
    break_even=(control['cost_per_good_package']*good-fixed)/hours
    metrics['break_even_pilot_equipment_cost_per_hour']=break_even
    sensitivity=[{'pilot_equipment_cost_per_hour':v,'pilot_cost_per_good_package':(fixed+v*hours)/good,
                  'control_cost_per_good_package':control['cost_per_good_package']} for v in [0,25,50,100,180,250]]
    gates=CONFIG['gates']
    checks=[dict(gate='Adjusted throughput gain',passed=gain>=gates['minimum_adjusted_throughput_gain'] and metrics['throughput_gain_ci95'][0]>0,
                 rule=f"Point estimate >={gates['minimum_adjusted_throughput_gain']*100:g}%; 95% interval lower bound >0"),
            dict(gate='Quality non-inferiority',passed=metrics['defect_did_pp_ci95'][1]<=gates['maximum_defect_increase_pp'],
                 rule=f"95% upper bound of adjusted defect change <=+{gates['maximum_defect_increase_pp']:.2f} percentage points"),
            dict(gate='Pilot trial uptime',passed=pilot['uptime']>=gates['minimum_trial_uptime'],rule=f">={gates['minimum_trial_uptime']*100:g}%"),
            dict(gate='Valid input rows',passed=quality['valid_event_fraction']>=gates['minimum_valid_event_fraction'],rule=f">={gates['minimum_valid_event_fraction']*100:g}% of raw rows"),
            dict(gate='Cost per good package',passed=pilot['cost_per_good_package']<=control['cost_per_good_package'],rule='Pilot <= concurrent control under declared cost assumptions')]
    trial=cohorts[(cohorts.phase=='trial')&(cohorts.arm=='pilot')]
    hotspot=trial.sort_values('defect_rate',ascending=False).iloc[0]
    alerts=[]
    for row in daily[daily.phase=='trial'].itertuples():
        if row.arm=='pilot' and row.defect_rate>.02:
            alerts.append(dict(day=row.day,category='quality',severity='review',
                               metric_value=round(row.defect_rate*100,3),
                               rule='Daily pilot defect rate >2% (operating threshold; not statistical significance)',
                               owner='Pilot quality owner',action='Review package mix and station/shift cohorts'))
    for row in shifts[(shifts.phase=='trial')&(shifts.arm=='pilot')&(shifts.uptime<.95)].itertuples():
        alerts.append(dict(day=row.day,category='uptime',severity='review',metric_value=round(row.uptime*100,3),
                           rule=f'{row.station}/{row.shift_name}: shift uptime <95%',
                           owner='Equipment owner',action='Inspect fault logs and verify recovery'))
    conclusion='HOLD — remediate and retest' if not all(x['passed'] for x in checks) else 'Eligible for controlled follow-up trial'
    summary={'simulation_as_of':CONFIG['as_of'],'dataset':'Synthetic; no Amazon data or affiliation',
             'recommendation':conclusion,'metrics':metrics,'data_quality':quality,
             'periods':periods,'gates':checks,'highest_risk_cohort':hotspot.to_dict(),
             'limits':['Non-randomized fixed cohorts; results are descriptive, not proof of causality.',
                       'Only 14 days per phase at one simulated site; no demonstrated multi-site effect.',
                       'Cost assumptions are illustrative and require real finance validation.',
                       'No physical testing or safety approval was performed. Real deployment requires qualified review.']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item()))
    daily.to_csv(OUT/'daily_scorecard.csv',index=False)
    shifts.to_csv(OUT/'shift_scorecard.csv',index=False)
    cohorts.to_csv(OUT/'defect_cohorts.csv',index=False)
    pareto.to_csv(OUT/'fault_pareto.csv',index=False)
    pd.DataFrame(alerts).to_csv(OUT/'alert_queue.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(OUT/'cost_sensitivity.csv',index=False)
    return summary,daily,cohorts,pareto


def charts(summary,daily,cohorts,pareto):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
                         'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(13,8.2),layout='constrained')
    palette={'control':'#66788a','pilot':'#076b65'}
    for arm in ['control','pilot']:
        x=daily[daily.arm==arm];dates=pd.to_datetime(x.day)
        axes[0,0].plot(dates,x.throughput,label=arm.capitalize(),color=palette[arm],lw=2)
        axes[0,1].plot(dates,x.defect_rate*100,label=arm.capitalize(),color=palette[arm],lw=2)
    trial=pd.Timestamp(daily.loc[daily.phase=='trial','day'].min())
    for ax in axes[0]:
        ax.axvline(trial,ls='--',color='#c67b27',label='Trial starts')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        ax.tick_params(axis='x',rotation=25);ax.grid(alpha=.15);ax.legend(fontsize=8)
    axes[0,0].set(title='Throughput rises after automation',ylabel='Packages per staffed hour')
    axes[0,1].set(title='Quality must be evaluated alongside speed',ylabel='Defective packages (%)')
    x=cohorts[(cohorts.phase=='trial')&(cohorts.arm=='pilot')].copy()
    x['label']=x.station+' / '+x.shift_name+' / '+x.sku_class
    x=x.sort_values('defect_rate',ascending=False).head(6).iloc[::-1]
    axes[1,0].barh(x.label,x.defect_rate*100,color='#b65b38')
    axes[1,0].set(title='Pilot defect hotspots (exploratory)',xlabel='Defect rate (%)')
    axes[1,1].bar(pareto.reason,pareto.seconds/60,color='#66788a')
    axes[1,1].set(title='Pilot trial downtime by recorded reason',ylabel='Minutes')
    fig.suptitle('PilotOps | Synthetic automation pilot evaluation',fontsize=17,fontweight='bold')
    fig.savefig(OUT/'pilot_scorecard.png',dpi=170);plt.close(fig)


def render_report(summary):
    m=summary['metrics'];q=summary['data_quality'];h=summary['highest_risk_cohort']
    def pct(x):return f'{x*100:.1f}%'
    gate_rows=''.join(f"<tr><td>{html.escape(g['gate'])}</td><td>{'PASS' if g['passed'] else 'HOLD'}</td><td>{html.escape(g['rule'])}</td></tr>" for g in summary['gates'])
    period_rows=''.join(f"<tr><td>{r['phase']}</td><td>{r['arm']}</td><td>{r['packages']:,}</td><td>{r['throughput']:.1f}</td><td>{pct(r['defect_rate'])}</td><td>{pct(r['uptime'])}</td><td>₹{r['cost_per_good_package']:.2f}</td></tr>" for r in summary['periods'])
    ci=m['throughput_gain_ci95'];di=m['defect_did_pp_ci95']
    image=base64.b64encode((OUT/'pilot_scorecard.png').read_bytes()).decode()
    report=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PilotOps automation pilot review</title><style>
body{{margin:0;background:#f3f5f5;color:#152d35;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:36px 24px}}h1{{font-size:42px;line-height:1.1;margin:12px 0}}h2{{font-size:24px}}.eyebrow{{color:#076b65;font-weight:700;letter-spacing:2px;font-size:12px}}.sub{{color:#536775}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card,section{{background:white;padding:24px;border-radius:10px;margin:20px 0}}.cards .card{{margin:0}}.big{{font-size:32px;font-weight:750}}.decision{{border-left:6px solid #b65b38}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #e3e7e7}}img{{width:100%;height:auto}}.scroll{{overflow:auto}}@media(max-width:700px){{.cards{{grid-template-columns:1fr}}h1{{font-size:32px}}}}@media print{{body{{background:white}}main{{padding:0}}section,.card{{break-inside:avoid}}}}</style>
<main><div class="eyebrow">PILOTOPS / PACKING TRIAL</div><h1>Is the packing trial ready to expand?</h1>
<p class="sub">AI-assisted portfolio project · Synthetic data · Snapshot {summary['simulation_as_of']} · No Amazon affiliation</p>
<section class="decision"><h2>{summary['recommendation']}</h2><p>The pilot packs more items, but quality and cost also matter. Start by reviewing {h['sku_class']} packages at {h['station']} on the {h['shift_name']} shift. This is a useful place to investigate, not a confirmed explanation of the fault.</p></section>
<div class="cards"><div class="card">Adjusted throughput gain<div class="big">{pct(m['adjusted_throughput_gain'])}</div><small>95% day-cluster interval: {pct(ci[0])} to {pct(ci[1])}</small></div>
<div class="card">Adjusted defect change<div class="big">{m['adjusted_defect_change_pp']:+.2f} pp</div><small>95% interval: {di[0]:+.2f} to {di[1]:+.2f} pp</small></div>
<div class="card">Valid source rows<div class="big">{pct(q['valid_event_fraction'])}</div><small>{q['quarantined_rows']} quarantined; {q['exact_duplicates_removed']} exact duplicates removed</small></div></div>
<section><h2>What changed during the trial</h2><img alt="Four charts compare daily throughput, daily defects, pilot defect cohorts and recorded downtime reasons" src="data:image/png;base64,{image}"></section>
<section><h2>Did the pilot meet the targets?</h2><p>These targets were set before reviewing the results. They are assumptions for this project, not Amazon standards.</p><div class="scroll"><table><tr><th>Gate</th><th>Status</th><th>Rule</th></tr>{gate_rows}</table></div></section>
<section><h2>The numbers behind the decision</h2><div class="scroll"><table><tr><th>Phase</th><th>Arm</th><th>Packages</th><th>Packages/hour</th><th>Defects</th><th>Uptime</th><th>Cost/good package</th></tr>{period_rows}</table></div><p>Throughput uses scheduled staffed hours, including downtime. Each station has one operator in this scenario. Cost includes declared staff, equipment and rework assumptions; it excludes capital outlay, deployment and broader business costs.</p></section>
<section><h2>What would need to change on cost?</h2><p>Holding observed output and quality fixed, the pilot equipment charge would need to be at or below <strong>₹{m['break_even_pilot_equipment_cost_per_hour']:.2f}/hour</strong> to match the control cost per good package, compared with the scenario assumption of ₹{CONFIG['economics']['pilot_equipment_cost_per_hour']}/hour. This is a one-variable break-even calculation, not a forecast or procurement quote. See cost_sensitivity.csv.</p></section>
<section><h2>What to do next</h2><ol><li>Quality owner: examine affected packages and verify whether the cohort association persists after product-mix checks.</li><li>Equipment owner: inspect sensor-alarm records and validate suspected causes with physical observations.</li><li>Analyst: rerun a preplanned matched follow-up trial after corrective action, keeping the quality guardrail.</li><li>Site lead: hold expansion until readiness, finance and qualified safety reviews are complete.</li></ol></section>
<section><h2>Data checks and limits</h2><p>Latest source lag: {q['source_lag_hours']:.1f} hours versus the simulated snapshot. Input rows reconcile exactly. The pipeline validates keys, timestamps, value ranges and shift completeness; it publishes the SQLite database atomically.</p><ul>{''.join('<li>'+html.escape(x)+'</li>' for x in summary['limits'])}</ul><p>The run log shows what happened in this local run. It does not measure production availability. Forecasting and machine learning are outside this project’s scope.</p></section></main></html>'''
    (OUT/'report.html').write_text(report,encoding='utf-8')
    memo=f'''# Packing trial review\n\nSynthetic data; no Amazon data or affiliation.\n\n## Recommendation\n{summary['recommendation']}. The decision considers speed, errors and cost together.\n\n## What the results show\nAdjusted throughput increased by {pct(m['adjusted_throughput_gain'])}. The adjusted defect rate increased by {m['adjusted_defect_change_pp']:.2f} percentage points. The 95% ranges are {pct(ci[0])} to {pct(ci[1])} for throughput and {di[0]:+.2f} to {di[1]:+.2f} percentage points for defects.\n\nThese comparisons use the earlier period and the manual group. They help account for common daily changes, but the groups were not randomly assigned.\n\n## Where to look next\nReview {h['sku_class']} packages at {h['station']} on the {h['shift_name']} shift. Check the affected packages and downtime records before deciding what caused the issue. After a fix has been checked, run another planned trial using the same quality targets.\n\n## What this does not tell us\nThe project has no real equipment or floor observations. Costs are assumptions. The hotspot is a lead to investigate, not proof of an equipment fault. See report.html and docs/methodology.md for the details.\n'''
    (OUT/'executive_review.md').write_text(memo)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-raw',action='store_true',help='Validate supplied CSV files instead of regenerating synthetic inputs')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);log=[]
    # Do not leave a previous report posing as this run's successful output.
    for name in ['report.html','summary.json','executive_review.md']:
        (OUT/name).unlink(missing_ok=True)
    def step(name,fn):
        started=time.perf_counter()
        try:
            result=fn();log.append({'step':name,'status':'PASS','seconds':round(time.perf_counter()-started,3)})
            return result
        except Exception as exc:
            log.append({'step':name,'status':'FAILED','error':str(exc)})
            (OUT/'pipeline_log.json').write_text(json.dumps(log,indent=2))
            raise
    if not args.reuse_raw:step('generate synthetic inputs',lambda:generate(CONFIG['seed']))
    quality=step('validate and publish warehouse',lambda:load_warehouse(CONFIG['as_of']))
    summary,daily,cohorts,pareto=step('SQL scorecards and uncertainty',lambda:analyse(quality))
    step('render charts',lambda:charts(summary,daily,cohorts,pareto))
    step('render decision review',lambda:render_report(summary))
    fingerprint=hashlib.sha256((ROOT/'sql/models.sql').read_bytes()+(ROOT/'config.json').read_bytes()+(ROOT/'pilotops.py').read_bytes()).hexdigest()
    (OUT/'pipeline_log.json').write_text(json.dumps({'steps':log,'code_config_sha256':fingerprint,'run_type':'local synthetic snapshot'},indent=2))
    print(json.dumps({'decision':summary['recommendation'],'metrics':summary['metrics'],'quality':quality},indent=2))
    print('Open outputs/report.html. Run python -m unittest discover -s tests -v')


if __name__=='__main__':main()
