"""Paired-world construction, public-only policies, accounting and logging."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.agents.records import RunLog,read_events
from budgeted_science.paired_claim_audit import core,policies,pilot
from budgeted_science.multi_claim_audit import mixed


class PairedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=core.build_catalog()

    def test_six_cases_and_opposite_target_claims(self):
        self.assertEqual(len(self.catalog['cases']),6)
        for i in range(0,6,2):
            a,b=[x['study'] for x in self.catalog['cases'][i:i+2]]
            self.assertEqual(a['public'],b['public'])
            for c in a['public']['claims']:
                if c['scope']=='fixed_target':
                    self.assertNotEqual(a['private']['truth'][c['id']]['verdict'],b['private']['truth'][c['id']]['verdict'])
            self.assertLess(self.catalog['diagnostics'][i//2]['early_max_difference'],1e-8)

    def test_truth_varies_for_every_template(self):
        labels={}
        for case in self.catalog['cases']:
            for claim in case['study']['public']['claims']:
                labels.setdefault(claim['kind'],set()).add(case['study']['private']['truth'][claim['id']]['verdict'])
        self.assertTrue(all(x=={'ACCEPT','REJECT'} for x in labels.values()))

    def test_report_numbers_and_independent_references(self):
        for case in self.catalog['cases']:
            study=case['study']
            for claim in study['public']['claims']:
                if claim['kind']=='numerical_point':
                    expected=mixed.printed(mixed.quantity('numerical_point',study['public']['original']))
                    self.assertEqual(claim['reported_value'],expected)
            for ref in study['private']['references'].values():
                self.assertLess(ref['max_solver_disagreement'],1e-7)
                self.assertLess(ref['max_service_disagreement'],1e-6)

    def test_identical_early_inputs_and_different_later_evidence(self):
        for budget in (24,32):
            for i in range(0,6,2):
                a,b=[core.Audit(c['study'],budget=budget) for c in self.catalog['cases'][i:i+2]]
                self.assertEqual(a.evidence(),b.evidence())
                ra=a.dispatch('measure_target',{'variable':'x','time':4.})
                rb=b.dispatch('measure_target',{'variable':'x','time':4.})
                self.assertGreater(abs(ra['value']-rb['value']),1)
                self.assertEqual(ra['charge'],12)

    def test_budget_cache_invalid_and_original_parameter_identity(self):
        study=self.catalog['cases'][0]['study']
        env=core.Audit(study,budget=24)
        original=env.dispatch('simulate_low',{'theta':study['public']['report_parameters']})
        self.assertEqual(original['charge'],0)
        x=env.dispatch('measure_target',{'variable':'x','time':4.})
        repeat=env.dispatch('measure_target',{'variable':'x','time':4.})
        self.assertEqual(x['value'],repeat['value'])
        self.assertEqual(repeat['charge'],0)
        env.dispatch('measure_target',{'variable':'y','time':6.})
        r=env.dispatch('simulate_high',{'theta':study['public']['report_parameters']})
        self.assertEqual(r['status'],'unaffordable')
        self.assertEqual(env.status()['spent'],24)
        with self.assertRaises(ValueError): env.dispatch('measure_target',{'variable':'x','time':4.,'theta':[1,2,3]})

    def test_failed_work_is_charged_and_reused(self):
        env=core.Audit(self.catalog['cases'][0]['study'],budget=24)
        theta=env.public['candidate_fits'][1]
        with patch('budgeted_science.resource_planning.environment._solve_low',side_effect=ValueError('failure')) as fn:
            a=env.dispatch('simulate_low',{'theta':theta})
            b=env.dispatch('simulate_low',{'theta':theta})
            self.assertEqual(a['status'],'failed')
            self.assertEqual((a['charge'],b['charge']),(1,0))
            self.assertEqual(fn.call_count,1)

    def test_deduplication_and_interrupted_logs(self):
        with tempfile.TemporaryDirectory() as root:
            log=RunLog(root,'test')
            try:
                s=core.Session(self.catalog['cases'][0]['study'],24,log)
                s.execute('same','measure_target',{'variable':'x','time':4.})
                s.execute('same','measure_target',{'variable':'x','time':4.})
                self.assertEqual(s.environment.status()['spent'],12)
                s.deadline=0
                with self.assertRaises(RuntimeError): s.call('get_status')
            finally: log.close()
            events,torn=read_events(log.path)
            self.assertFalse(torn)
            self.assertTrue(any(x['kind']=='tool_result' for x in events))

    def test_utility_decision_thresholds(self):
        self.assertEqual(policies.verdict(.5),'ABSTAIN')
        self.assertEqual(policies.verdict(.7),'ACCEPT')
        self.assertEqual(policies.verdict(.3),'REJECT')
        self.assertAlmostEqual(policies.utility(.7),.1)
        self.assertEqual(policies.utility(0),1)

    def belief(self,study):
        env=core.Audit(study,budget=32)
        belief=policies.Belief(env.public)
        for name,theta in [('simulate_high',belief.baseline),('simulate_low',belief.other)]:
            result=env.dispatch(name,{'theta':list(theta)})
            belief.ingest(name,result)
        return env,belief

    def test_fantasies_no_solver_no_target_no_mutation(self):
        env,belief=self.belief(self.catalog['cases'][0]['study'])
        before=deepcopy(belief.__dict__)
        status=env.status()
        with patch('budgeted_science.resource_planning.environment._solve_high',side_effect=AssertionError('unpaid')), \
             patch('budgeted_science.resource_planning.environment._solve_low',side_effect=AssertionError('unpaid')):
            for name,args,_ in belief.actions(23):
                self.assertTrue(np.isfinite(belief.expected_gain(name,args)))
        self.assertEqual(before,belief.__dict__)
        self.assertEqual(status,env.status())

    def test_measurement_changes_belief_between_matched_worlds(self):
        weights=[]
        for case in self.catalog['cases'][:2]:
            env,belief=self.belief(case['study'])
            belief.ingest('measure_target',env.dispatch('measure_target',{'variable':'x','time':4.}))
            weights.append(belief.weights())
        self.assertGreater(np.max(np.abs(weights[0]-weights[1])),.8)

    def test_policy_receives_only_public_inputs_and_paid_calls(self):
        case=self.catalog['cases'][0]
        with tempfile.TemporaryDirectory() as root:
            for method in ('simulation_first','adaptive_utility'):
                result=pilot.run_case(case,24,method,root)
                self.assertTrue(result['completed'])
                self.assertLessEqual(result['scientific_status']['spent'],24)
                self.assertEqual(result['utility'],result['correct']-2*result['wrong'])
                public=pilot.read(result['path']+'/public/input.json')
                self.assertNotIn('private',public)
                self.assertNotIn('truth',str(public))
                self.assertNotIn('target_parameters',str(public))
                before=Path(result['path'],'transcript.md').read_bytes()
                with patch.object(core,'build_catalog',side_effect=AssertionError('no regeneration solve')):
                    pilot.render_case(result['path'])
                self.assertEqual(before,Path(result['path'],'transcript.md').read_bytes())

    def test_aggregate_fixture(self):
        rows=[{'budget':24,'method':'fixture','total':6,'correct':3,'wrong':1,'abstained':2,
               'incomplete_claims':0,'utility':1,'completed':True,'scientific_status':{'spent':20},'runtime_seconds':1}]*2
        r=pilot.summarize(rows)[0]
        self.assertEqual((r['claims'],r['correct'],r['utility'],r['mean_spent']),(12,6,2,20))

    def test_offline_aggregate_render_with_relative_directory(self):
        with tempfile.TemporaryDirectory() as root:
            log=RunLog(root,'fixture')
            row={'budget':24,'method':'fixture','case_id':'example','total':6,'correct':3,
                 'wrong':1,'abstained':2,'incomplete_claims':0,'utility':1,'completed':True,
                 'scientific_status':{'spent':20},'runtime_seconds':1,
                 'path':str(log.path/'episodes'/'fixture')}
            log.write_json('results.json',[row])
            log.close()
            with patch('os.getcwd',return_value=str(log.path)):
                report=pilot.render('.')
            self.assertIn('episodes/fixture/transcript.md',report.read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()
