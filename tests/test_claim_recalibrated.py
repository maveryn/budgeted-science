"""Frozen severity selection and actual extrapolation-submission contracts."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budgeted_science.agents.records import RunLog
from budgeted_science.claim_verification.numerics import Backend
from budgeted_science.claim_verification.studies import validate_study
from budgeted_science.claim_verification_incremental.environment import IncrementalEpisode
from budgeted_science.claim_verification_incremental.policies import run_policy
from budgeted_science.claim_verification_incremental import recalibrated as pilot
from test_claim_incremental import study


@lru_cache()
def commissioned():
    with tempfile.TemporaryDirectory() as directory:
        log=RunLog(Path(directory),'commission-test')
        try:
            selected,failures=pilot.commission_system(log,Backend(),'development',7100,0)
            sweep=json.loads((log.path/'private/sweeps/7100.json').read_text(encoding='utf-8'))
            return selected,failures,sweep
        finally:
            log.close()


def candidate(order,error,family='integration',integration=.03,sampling=-.01):
    return {'order':order,'relative_error':error,'family':family,'status':'success',
            'integration_component':integration,'sampling_component':sampling}


class SelectionTests(unittest.TestCase):
    def test_frozen_cohorts_disjoint_and_prices_unchanged(self):
        p=pilot.protocol()
        self.assertFalse(set(p['cohorts']['development']) & set(p['cohorts']['fresh']))
        self.assertEqual((p['budget'],p['tolerance'],p['estimator']),(8,.05,'extrapolation'))
        self.assertEqual(len(p['slots']),6)
        self.assertIn(.16,p['steps']); self.assertIn(.32,p['steps'])

    def test_nearest_severity_and_stable_ties(self):
        rows=[candidate(4,.02),candidate(2,.02),candidate(1,.03),candidate(0,.08)]
        self.assertEqual(pilot.select_candidate(rows,'integration','valid')['order'],2)
        self.assertEqual(pilot.select_candidate(rows,'integration','invalid')['order'],0)

    def test_no_silent_widening_or_policy_based_selection(self):
        rows=[candidate(0,.049),candidate(1,.059),candidate(2,.151)]
        self.assertIsNone(pilot.select_candidate(rows,'integration','valid'))
        self.assertIsNone(pilot.select_candidate(rows,'integration','invalid'))
        rows=[candidate(0,.02),candidate(1,.03)]
        rows[0]['policy_correct']=True; rows[1]['policy_correct']=False
        self.assertEqual(pilot.select_candidate(rows,'integration','valid')['order'],0)

    def test_mixed_selection_requires_both_error_components(self):
        rows=[candidate(0,.02,'mixed',.025,-.005),candidate(1,.025,'mixed',.06,-.035)]
        self.assertEqual(pilot.select_candidate(rows,'mixed','valid')['order'],1)
        self.assertIsNone(pilot.select_candidate(rows[:1],'mixed','valid'))

    def test_all_sweep_settings_and_selection_decisions_retained(self):
        studies,failures,sweep=commissioned()
        self.assertEqual(len(sweep['sweep']),95)
        self.assertEqual(len(studies)+len(failures),6)
        self.assertEqual(len(sweep['selections']),len(studies))
        self.assertEqual(len({s['case_id'] for s in studies}),len(studies))
        for selected in sweep['selections']:
            expected=pilot.select_candidate(sweep['sweep'],*selected['slot'])
            self.assertEqual(expected['order'],selected['order'])

    def test_admitted_reports_are_real_consistent_and_private(self):
        studies,_,_=commissioned()
        for s in studies:
            validate_study(s)
            self.assertEqual(s['run']['config']['method'],'Euler')
            text=json.dumps(s['artifacts'])
            for private in ('integration_component','claim_valid','selection_order','reference_q'):
                self.assertNotIn(private,text)
            error=s['private']['relative_error']
            label='valid' if s['private']['claim_valid'] else 'invalid'
            lo,hi,_=pilot.BANDS[label]
            self.assertTrue(lo<=error<=hi)


class EvaluationTests(unittest.TestCase):
    def test_primary_submission_uses_extrapolation_not_last_run(self):
        ep=IncrementalEpisode(study())
        estimate={'q':study()['reported_q']/1.2,'axes_extrapolated':[0,1],'certified':False}
        with patch('budgeted_science.claim_verification_incremental.policies.convergence_estimate',return_value=estimate):
            result=run_policy(ep.tools.call,'fixed_IIS',estimator='extrapolation')
        self.assertEqual(ep.submission['verdict'],'REJECT')
        self.assertEqual(ep.submission['verdict'],result['extrapolated_verdict'])
        self.assertEqual(ep.spent,8)
        self.assertIn('extrapolated peak',ep.submission['justification'])

    def test_unavailable_extrapolation_abstains_without_fallback(self):
        ep=IncrementalEpisode(study())
        with patch('budgeted_science.claim_verification_incremental.policies.convergence_estimate',return_value=None):
            run_policy(ep.tools.call,'fixed_IIS',estimator='extrapolation')
        self.assertTrue(ep.evaluate()['abstained'])
        with self.assertRaises(ValueError):
            run_policy(lambda *a: self.fail('invalid estimator reached tools'),'fixed_IIS',estimator='oracle')

    def test_metadata_control_does_not_fit_to_fresh_labels(self):
        a=deepcopy(study()); b=deepcopy(study())
        a['run']['config']['dt']=.01; a['private']['claim_valid']=True
        b['run']['config']['dt']=.32; b['private']['claim_valid']=False
        fresh=deepcopy(a); fresh['private']['claim_valid']=False
        one=pilot.metadata_control([a,b],[fresh])
        fresh['private']['claim_valid']=True
        two=pilot.metadata_control([a,b],[fresh])
        self.assertEqual(one['threshold'],two['threshold'])
        self.assertEqual(one['left_accept'],two['left_accept'])
        self.assertNotEqual(one['fresh_correct'],two['fresh_correct'])

    def test_offline_render_uses_actual_submissions_and_no_solvers(self):
        s=deepcopy(study()); s['private'].update(cohort='development',family='integration')
        with tempfile.TemporaryDirectory() as directory:
            log=RunLog(Path(directory),'render-test')
            path=log.path
            try:
                log.write_json('manifest.json',pilot.protocol())
                log.write_json('private/catalog.json',{'studies':[s],'failures':[]})
                log.write_json('private/reachable.json',[])
                log.write_json('metadata_control.json',{})
                for i,policy in enumerate(pilot.POLICIES):
                    pilot.evaluate_policy(log,s,policy,i,Backend(),estimator='extrapolation')
            finally:
                log.close()
            with patch.object(Backend,'get',side_effect=AssertionError('offline render executed tool')):
                summary=pilot.render(path)
                first=(path/'report.md').read_bytes()
                self.assertEqual(summary,pilot.render(path))
                self.assertEqual(first,(path/'report.md').read_bytes())
            self.assertEqual(summary['cohorts']['development']['studies'],1)
            self.assertEqual(summary['cohorts']['fresh']['studies'],0)
            self.assertIn('tool_call',(path/'episodes/000/transcript.md').read_text())


if __name__=='__main__':
    unittest.main()
