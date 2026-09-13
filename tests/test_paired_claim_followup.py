"""Follow-up science, public-only estimation, budget and replay contracts."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from budgeted_science.paired_claim_audit import core,followup_core as science
from budgeted_science.paired_claim_audit import followup_policies as policy,followup
from budgeted_science.agents.records import RunLog,read_events


class FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=science.build_catalog()

    def test_six_existing_worlds_and_paired_public_identity(self):
        self.assertEqual(len(self.catalog['cases']),6)
        for i in range(0,6,2):
            a,b=[science.Audit(c['study']) for c in self.catalog['cases'][i:i+2]]
            self.assertEqual(a.evidence(),b.evidence())
            self.assertNotEqual(a._study['private']['target_parameters'],b._study['private']['target_parameters'])

    def test_original_study_unchanged(self):
        old=core.build_catalog()
        self.assertEqual(old['version'],core.VERSION)
        self.assertIn('target_agreement',[c['kind'] for c in old['cases'][0]['study']['public']['claims']])
        self.assertNotIn('followup_version',old['cases'][0]['study']['public'])

    def test_reference_labels_arithmetic_and_inequalities(self):
        for case in self.catalog['cases']:
            s=case['study']; refs=s['private']['references']
            for c in s['public']['claims']:
                if c['scope']=='fixed_target':
                    q=science.target_quantity(c['kind'],refs['target'])
                    self.assertEqual(science.classify(c,q)['verdict'],s['private']['truth'][c['id']]['verdict'])
            for ref in refs.values(): self.assertLess(ref['max_solver_disagreement'],1e-7)
        c={'operator':'le','threshold':.1}
        self.assertEqual(science.classify(c,.1)['verdict'],'ACCEPT')
        self.assertEqual(science.classify(c,.11)['verdict'],'REJECT')

    def initialized(self,case=0):
        env=science.Audit(self.catalog['cases'][case]['study'])
        belief=policy.Belief(env.public)
        for name,theta in [('simulate_high',belief.baseline),('simulate_low',belief.other)]:
            belief.ingest(name,env.dispatch(name,{'theta':list(theta)}))
        return env,belief

    def test_followup_competition_and_free_reuse(self):
        env,b=self.initialized()
        record=env.dispatch('measure_target',{'variable':'x','time':4.})
        self.assertEqual(env.status()['remaining'],11)
        self.assertEqual(env.dispatch('measure_target',{'variable':'x','time':4.})['value'],record['value'])
        env.dispatch('simulate_high',{'theta':list(b.intervention)})
        other=env.dispatch('simulate_high',{'theta':list(b.other)})
        self.assertEqual(other['status'],'unaffordable')
        self.assertEqual(env.status()['spent'],29)
        with self.assertRaises(ValueError): env.dispatch('measure_target',{'theta':list(b.other),'variable':'x','time':4.})

    def test_aggregate_and_late_window_use_purchased_values(self):
        env,b=self.initialized()
        table,_=b.table(b.baseline)
        self.assertAlmostEqual(b.target_quantity(b.baseline,'target_integral')[0],science.target_quantity('target_integral',table))
        self.assertAlmostEqual(b.target_quantity(b.baseline,'target_late_recovery')[0],science.target_quantity('target_late_recovery',table))
        before=b.target_quantity(b.other,'target_integral')
        b.ingest('measure_target',env.dispatch('measure_target',{'variable':'x','time':4.}))
        self.assertEqual(before,b.target_quantity(b.other,'target_integral'))

    def test_hypotheticals_do_not_query_truth_or_mutate(self):
        env,b=self.initialized()
        before=deepcopy(b.__dict__); status=env.status()
        with (patch('budgeted_science.resource_planning.environment._solve_high',side_effect=AssertionError('unpaid')),
              patch('budgeted_science.resource_planning.environment._solve_low',side_effect=AssertionError('unpaid'))):
            for name,args,_ in b.actions(23): self.assertTrue(np.isfinite(b.expected_gain(name,args)))
        self.assertEqual(before,b.__dict__); self.assertEqual(status,env.status())

    def test_all_fixed_measurement_choices_present(self):
        self.assertEqual(len(policy.MEASUREMENTS),30)
        self.assertEqual(len(policy.FIXED),90)
        self.assertEqual(len(set(policy.METHODS)),len(policy.METHODS))
        self.assertNotIn(('x',1.),policy.MEASUREMENTS)

    def test_intervention_matched_coarse_and_fine_verdicts_differ(self):
        for case in self.catalog['cases']:
            s=case['study']; c=next(c for c in s['public']['claims'] if c['kind']=='intervention_effect')
            coarse=s['private']['matched_coarse_intervention_effect']
            self.assertNotEqual(science.classify(c,coarse)['verdict'],s['private']['truth'][c['id']]['verdict'])

    def test_intervention_belief_uses_matched_not_mixed_fidelity(self):
        _,b=self.initialized()
        c=next(c for c in b.actual_claims if c['kind']=='intervention_effect')
        s=b.public['intervention_summary']; ratio=s['intervention_grid_peak']/s['baseline_grid_peak']
        expected=policy.old.probability(c,1-ratio,policy.old.LOW_RELATIVE_SD*ratio)
        self.assertAlmostEqual(b.probabilities()[c['id']],expected)

    def test_cheap_intervention_controls_are_paid_and_literal(self):
        with tempfile.TemporaryDirectory() as root:
            for mode in ('fit_plugin','fit_accept','fit_reject'):
                r=followup.run_case(self.catalog['cases'][0],f'fixed:x:4:{mode}',root)
                self.assertTrue(r['completed']); self.assertEqual(r['scientific_status']['spent'],29)
                row=next(row for row in r['rows'] if row['kind']=='intervention_effect')
                self.assertEqual(row['verdict'],'ACCEPT' if mode=='fit_accept' else 'REJECT')

    def test_public_only_run_and_offline_render(self):
        with tempfile.TemporaryDirectory() as root:
            result=followup.run_case(self.catalog['cases'][0],'adaptive_followup',root)
            self.assertTrue(result['completed'])
            self.assertLessEqual(result['scientific_status']['spent'],32)
            public=followup.original.read(Path(result['path'])/'public/input.json')
            self.assertNotIn('truth',str(public)); self.assertNotIn('target_parameters',str(public))
            before=Path(result['path'],'transcript.md').read_bytes()
            with patch.object(science,'build_catalog',side_effect=AssertionError('no solver')):
                followup.original.render_case(result['path'])
            self.assertEqual(before,Path(result['path'],'transcript.md').read_bytes())
            self.assertEqual(result['utility'],result['correct']-2*result['wrong'])
            events,torn=read_events(result['path']); self.assertFalse(torn)
            self.assertEqual(sum(e['result'].get('charge',0) for e in events if e['kind']=='tool_result'),result['scientific_status']['spent'])

    def test_call_dedup_and_incomplete_preservation(self):
        with tempfile.TemporaryDirectory() as root:
            log=RunLog(root,'fixture')
            try:
                session=science.Session(self.catalog['cases'][0]['study'],32,log)
                args={'variable':'x','time':4.}
                session.execute('same','measure_target',args); session.execute('same','measure_target',args)
                self.assertEqual(session.environment.status()['spent'],12)
            finally: log.close()
            with patch.object(policy.Belief,'expected_gain',side_effect=RuntimeError('controlled')):
                r=followup.run_case(self.catalog['cases'][0],'adaptive_followup',root)
            self.assertFalse(r['completed']); self.assertEqual(r['incomplete_claims'],6)
            self.assertTrue(Path(r['path'],'transcript.md').exists())

    def test_partial_commissioning_no_claim_of_complete_comparison(self):
        self.assertFalse(followup.commissioning([])['complete'])

    def test_complete_commissioning_aggregate_fixture(self):
        rows=[]
        for method in policy.METHODS:
            for pair in range(3):
                for member in range(2):
                    correct=5 if method=='adaptive_followup' else 4
                    rows.append({'method':method,'pair':pair,'member':member,'correct':correct,
                                 'wrong':0,'abstained':6-correct,'utility':correct,'completed':True,
                                 'scientific_status':{'spent':29},'path':'fixture',
                                 'purchases':[{}, {}, {}, {'theta':[member]}]})
        result=followup.commissioning(rows)
        self.assertTrue(result['complete']); self.assertTrue(result['switches_in_all_pairs'])
        self.assertEqual(result['utility_gain_over_best_global_fixed'],6)
        self.assertEqual(result['utility_gain_over_hindsight_pair_specific_fixed'],6)

    def test_pilot_checkpoints_are_unique_and_final_results_survive(self):
        catalog={'version':science.VERSION,'cases':[{'case_id':'a'},{'case_id':'b'}]}
        def fake(case,method,root):
            return {'case_id':case['case_id'],'method':method,'budget':32,'correct':3,'wrong':1,
                    'abstained':2,'utility':1,'completed':True,'total':6,'incomplete_claims':0,
                    'scientific_status':{'spent':29},'runtime_seconds':0,'path':str(Path(root)/case['case_id'])}
        with tempfile.TemporaryDirectory() as root, \
             patch.object(followup,'METHODS',('all_accept',)), \
             patch.object(followup,'build_catalog',return_value=catalog), \
             patch.object(followup.original,'provenance',return_value={'source_manifest_hash':'fixture'}), \
             patch.object(followup,'run_case',side_effect=fake):
            prepared=followup.prepare(root)
            path=followup.run(prepared,root)
            self.assertEqual(len(list((path/'checkpoints').glob('*.json'))),2)
            self.assertEqual(len(followup.original.read(path/'results.json')),2)
            before=(path/'report.md').read_bytes()
            followup.render(path)
            self.assertEqual(before,(path/'report.md').read_bytes())

    def test_pilot_interruption_retains_completed_episode_results(self):
        catalog={'version':science.VERSION,'cases':[{'case_id':'a'},{'case_id':'b'}]}
        row={'case_id':'a','correct':1,'wrong':0,'abstained':5,'path':'fixture'}
        with tempfile.TemporaryDirectory() as root, \
             patch.object(followup,'METHODS',('all_accept',)), \
             patch.object(followup,'build_catalog',return_value=catalog), \
             patch.object(followup.original,'provenance',return_value={'source_manifest_hash':'fixture'}), \
             patch.object(followup,'run_case',side_effect=[row,RuntimeError('interrupt')]):
            prepared=followup.prepare(root)
            with self.assertRaises(RuntimeError): followup.run(prepared,root)
            path=next(Path(root).glob('*followup-pilot*'))
            self.assertEqual(followup.original.read(path/'results.json'),[row])


if __name__=='__main__': unittest.main()
