import unittest
import json
import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import numpy as np
import pilotops as p


class CleaningTests(unittest.TestCase):
    def setUp(self):
        self.shifts=pd.DataFrame([dict(shift_id='S1',day='2026-09-01',shift_name='day',scheduled_seconds=14400)])
        self.row=dict(event_id='E1',shift_id='S1',completed_at='2026-09-01T09:00:00',
                      sku_class='standard',cycle_seconds=40,defective=0)

    def clean(self,rows,cutoff='2026-09-02T06:00:00'):
        return p.clean_events(pd.DataFrame(rows),self.shifts,cutoff)

    def test_exact_duplicate_removed_without_losing_original(self):
        valid,q,c=self.clean([self.row,dict(self.row)])
        self.assertEqual((len(valid),len(q),c['exact_duplicates_removed']),(1,0,1))

    def test_conflicting_key_quarantines_both_versions(self):
        conflict=dict(self.row,defective=1)
        valid,q,c=self.clean([self.row,conflict])
        self.assertEqual(len(valid),0)
        self.assertEqual(q.reason.tolist(),['conflicting_event_id']*2)

    def test_future_event_cannot_leak_into_analysis(self):
        valid,q,c=self.clean([self.row],cutoff='2026-09-01T08:30:00')
        self.assertEqual(len(valid),0);self.assertEqual(q.reason.iloc[0],'future_event')

    def test_outside_shift_and_bad_foreign_key(self):
        rows=[dict(self.row,event_id='E2',completed_at='2026-09-01T14:00:00'),
              dict(self.row,event_id='E3',shift_id='MISSING')]
        valid,q,c=self.clean(rows)
        self.assertEqual(set(q.reason),{'outside_shift','unknown_shift'})
        self.assertEqual(c['raw_rows'],len(valid)+len(q)+c['exact_duplicates_removed'])

    def test_invalid_numeric_values_rejected(self):
        rows=[dict(self.row,event_id='E2',cycle_seconds=-2),
              dict(self.row,event_id='E3',cycle_seconds=float('inf')),
              dict(self.row,event_id='E4',defective=2)]
        valid,q,c=self.clean(rows)
        self.assertEqual(len(valid),0);self.assertEqual(len(q),3)


class EstimationTests(unittest.TestCase):
    def test_concurrent_control_removes_shared_improvement(self):
        rows=[]
        for phase,days,multiplier in [('baseline',['01','02'],1),('trial',['15','16'],1.2)]:
            for day in days:
                for arm in ['control','pilot']:
                    rows.append(dict(day=f'2026-09-{day}',phase=phase,arm=arm,
                                     packages=100*multiplier,defects=2*multiplier,staffed_hours=4))
        gain,defect=p.estimate(pd.DataFrame(rows))
        self.assertAlmostEqual(gain,0);self.assertAlmostEqual(defect,0)
        result=p.bootstrap(pd.DataFrame(rows),100,42)
        self.assertTrue(np.allclose(result['throughput_gain_ci95'],[0,0]))

    def test_known_treatment_effect_and_bootstrap_reproducibility(self):
        rows=[]
        for phase,days in [('baseline',['01','02']),('trial',['15','16'])]:
            for day in days:
                for arm in ['control','pilot']:
                    packages=120 if phase=='trial' and arm=='pilot' else 100
                    rows.append(dict(day=f'2026-09-{day}',phase=phase,arm=arm,
                                     packages=packages,defects=0,staffed_hours=4))
        frame=pd.DataFrame(rows)
        self.assertAlmostEqual(p.estimate(frame)[0],.2)
        self.assertEqual(p.bootstrap(frame,100,42),p.bootstrap(frame,100,42))


class WarehouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not p.DB.exists():
            p.generate(p.CONFIG['seed']);p.load_warehouse(p.CONFIG['as_of'])

    def test_no_fanout_and_exact_input_reconciliation(self):
        con=sqlite3.connect(p.DB)
        for field,source,aggregate in [('packages','package_events','COUNT(*)'),
                                       ('downtime_seconds','faults','SUM(seconds)')]:
            a=con.execute(f'SELECT SUM({field}) FROM v_shift_scorecard').fetchone()[0]
            b=con.execute(f'SELECT {aggregate} FROM {source}').fetchone()[0]
            self.assertEqual(a,b)
        valid=con.execute('SELECT COUNT(*) FROM package_events').fetchone()[0]
        raw=len(pd.read_csv(p.RAW/'events.csv'))
        quarantined=len(pd.read_csv(p.CLEAN/'quarantine.csv'))
        manifest=json.loads((p.RAW/'generator_manifest.json').read_text())
        self.assertEqual(raw,valid+quarantined+manifest['exact_duplicates_added'])
        self.assertEqual(valid,manifest['original_valid_events'])
        con.close()

    def test_weighted_rate_and_foreign_keys(self):
        con=sqlite3.connect(p.DB)
        x=pd.read_sql_query('SELECT * FROM v_daily_scorecard',con)
        self.assertTrue(np.allclose(x.throughput,x.packages/x.staffed_hours))
        self.assertTrue(np.allclose(x.defect_rate,x.defects/x.packages))
        self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(),[])
        con.close()

    def test_idempotent_warehouse_rebuild(self):
        def totals():
            with sqlite3.connect(p.DB) as con:
                return con.execute('SELECT COUNT(*),SUM(defective),SUM(cycle_seconds) FROM package_events').fetchone()
        before=totals();p.load_warehouse(p.CONFIG['as_of']);self.assertEqual(before,totals())

    def test_missing_shift_blocks_publish_and_preserves_last_warehouse(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);raw=root/'raw';shutil.copytree(p.RAW,raw)
            shifts=pd.read_csv(raw/'shifts.csv');shifts.iloc[1:].to_csv(raw/'shifts.csv',index=False)
            faults=pd.read_csv(raw/'faults.csv')
            faults[faults.shift_id!=shifts.iloc[0].shift_id].to_csv(raw/'faults.csv',index=False)
            db=root/'warehouse.sqlite';db.write_bytes(b'previous successful warehouse')
            with patch.object(p,'RAW',raw),patch.object(p,'CLEAN',root/'clean'),patch.object(p,'DB',db):
                with self.assertRaisesRegex(ValueError,'Missing expected station shifts'):
                    p.load_warehouse(p.CONFIG['as_of'])
                self.assertEqual(db.read_bytes(),b'previous successful warehouse')

    def test_stale_source_blocks_publication(self):
        with self.assertRaisesRegex(ValueError,'Source freshness failure'):
            p.load_warehouse('2026-10-05T06:00:00')


if __name__=='__main__':unittest.main()
