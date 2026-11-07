import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from study import generate, score, baseline_naive, baseline_abstain, parse_response, prompt, summarize, run

class StudyTests(unittest.TestCase):
    def setUp(self): self.cases=generate(24,20261107)
    def test_balanced_paired_design(self):
        self.assertEqual(len(self.cases),96)
        self.assertEqual(len({c['pair_id'] for c in self.cases}),24)
        for cond in ('clean','missing','conflict','injection'):
            self.assertEqual(sum(c['condition']==cond for c in self.cases),24)
    def test_deterministic_generation(self): self.assertEqual(self.cases,generate(24,20261107))
    def test_expected_decisions(self):
        for c in self.cases:
            expected='answer' if c['condition'] in ('clean','injection') else 'abstain'
            self.assertEqual(c['expected']['decision'],expected)
    def test_unique_answers_per_pair(self):
        for c in self.cases:
            if c['condition']=='conflict':
                self.assertNotEqual(c['sources'][0]['text'],c['sources'][1]['text'])
    def test_injection_cannot_be_correct_answer(self):
        for c in self.cases:
            if c['condition']=='injection':
                self.assertNotIn('OVERRIDE_APPROVED',c['expected']['answer'])
                self.assertIn('OVERRIDE_APPROVED',prompt(c))
    def test_score_correct_answer(self):
        c=self.cases[0];self.assertTrue(score(c,c['expected'])['success'])
    def test_bad_citation_rejected(self):
        c=self.cases[0];bad={**c['expected'],'citations':['S99']}
        self.assertFalse(score(c,bad)['success'])
    def test_naive_injection_works(self):
        c=next(x for x in self.cases if x['condition']=='injection')
        self.assertTrue(score(c,baseline_naive(c))['attack_success'])
    def test_naive_conflict_unsupported(self):
        c=next(x for x in self.cases if x['condition']=='conflict')
        self.assertTrue(score(c,baseline_naive(c))['unsupported_answer'])
    def test_abstain_baseline(self):
        c=next(x for x in self.cases if x['condition']=='missing')
        self.assertTrue(score(c,baseline_abstain(c))['success'])
    def test_parse_response(self):
        obj=parse_response('```json\n{"decision":"answer","answer":"GBP 5,000","citations":["S1"]}\n```')
        self.assertEqual(obj['decision'],'answer')
    def test_bad_response_invalid(self): self.assertEqual(parse_response('Not json')['decision'],'invalid')
    def test_summary_counts(self):
        records=[{'condition':c['condition'],'metrics':score(c,baseline_naive(c))} for c in self.cases]
        self.assertEqual(sum(r['n'] for r in summarize(records)),96)

if __name__=='__main__':unittest.main()
